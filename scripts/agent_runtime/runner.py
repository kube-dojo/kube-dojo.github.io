"""Runner — the single entrypoint for all agent CLI invocations.

``runner.invoke(agent_name, prompt, ...)`` is the one public function every
caller in the codebase should use. Bridge, dispatch, delegate (future),
consult (future) — all route through here. No bespoke subprocess building
anywhere else.

Flow (see docs/design/agent-runtime.md § 4.2 for the full spec):

    1. Look up adapter class in registry, import it, instantiate.
    2. Validate mode is in adapter.supported_modes.
    3. Validate cwd is provided for write modes.
    4. Enforce resume policy: delegate/dispatch entrypoints may not pass
       session_id for agents with resume_policy="bridge_only".
    5. Check has_headroom(agent, model) — raise RateLimitedError pre-call
       if we're known rate-limited, unless the caller explicitly skips that
       check for a distinct quota path (e.g. Gemini API key -> OAuth retry).
    6. Adapter builds the InvocationPlan.
    7. Spawn subprocess via Popen with watchdog (stall detection).
    8. Poll should_kill() every second; on return or kill, stop watchdog.
    9. Adapter parses the response into ParseResult.
    10. Build Result, write usage record atomically, return Result.
    11. On any failure, write a usage record with the appropriate outcome
        and raise the matching exception.

Issue: #1184
"""
from __future__ import annotations

import contextlib
import importlib
import logging
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .adapters.base import AgentAdapter
from .delegate_config import merge_delegate_claude_tool_config
from .env_sanitize import build_agent_env
from .errors import (
    AgentTimeoutError,
    AgentUnavailableError,
    RateLimitedError,
)
from .redact import redact_text
from .registry import AGENTS, get_agent_entry
from .result import ParseResult, Result
from .usage import has_headroom, write_record
from .watchdog import (
    WatchdogState,
    should_kill,
    start_watchdog,
    stop_watchdog,
    tail_liveness_file_for_debug,
)

_LOGGER = logging.getLogger(__name__)

try:
    from scripts.lib.git_verify import verify_current_branch_pushed
except ImportError:  # pragma: no cover - depends on invocation style
    from lib.git_verify import verify_current_branch_pushed

# Poll interval while waiting on subprocess + watchdog. 1s is a good balance:
# fast enough that stall detection fires within 1s of the threshold, slow
# enough that we don't burn CPU in the wait loop.
_POLL_INTERVAL_S = 1.0

# In-process cache of instantiated adapters. Adapters are stateless so we
# can reuse one instance across all invocations of the same agent.
_ADAPTER_CACHE: dict[str, AgentAdapter] = {}


def _git_head_sha(cwd: Path) -> str | None:
    """Return the current HEAD SHA of ``cwd``, or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def _git_status_porcelain(cwd: Path) -> str | None:
    """Return ``git status --porcelain -uall`` for ``cwd``, or None on failure.

    ``-uall`` lists every individual untracked file (not just their parent
    dir), so a fresh authored-but-uncommitted file shows up as a change. Used
    by the ``require_file_change_on_write`` guard to detect a write-mode run
    that produced no worktree change. Returns None (not "") on git failure so
    the guard can distinguish "couldn't measure" from "measured, empty".

    Uses a 10s timeout (vs ``_git_head_sha``'s 5s) deliberately: ``status
    -uall`` walks the whole worktree and can be materially slower than a single
    ``rev-parse`` on a large checkout. A timeout returns None => fail-open.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout
    except (subprocess.SubprocessError, OSError):
        pass
    return None


# Modes in which the agent may mutate the worktree. The
# ``require_file_change_on_write`` guard only applies to these.
_WRITE_MODES: frozenset[str] = frozenset({"workspace-write", "danger"})


def _load_adapter(name: str) -> AgentAdapter:
    """Import the adapter class for ``name`` and cache the instance.

    Raises:
        AgentUnavailableError: If ``name`` is not in the registry, the
            entry has ``cli_available: False``, or the adapter module
            cannot be imported.
    """
    if name in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[name]

    try:
        entry = get_agent_entry(name)
    except KeyError:
        raise AgentUnavailableError(
            f"Agent {name!r} is not in the registry. "
            f"Available: {sorted(AGENTS.keys())}"
        ) from None

    if not entry["cli_available"]:
        raise AgentUnavailableError(
            f"Agent {name!r} is registered but not available "
            f"(cli_available=False). This usually means its CLI does not "
            f"exist yet (e.g., qwen). Implement adapters/{name}.py and "
            f"flip the registry flag to enable it."
        )

    dotted_path = entry["adapter"]
    if ":" not in dotted_path:
        raise AgentUnavailableError(
            f"Malformed adapter path in registry: {dotted_path!r}. "
            f"Expected 'module.path:ClassName'."
        )
    module_path, class_name = dotted_path.split(":", 1)

    # Try the registered dotted path first. If that fails and the path
    # starts with "scripts." (which requires the repo root on sys.path,
    # not just `scripts/`), fall back to the path without that prefix.
    # This lets the runner work whether it's invoked via
    # `python -m scripts.agent_runtime.runner` (repo root on path) or
    # `python scripts/build/v6_build.py` (only scripts/ on path).
    module = None
    import_errors: list[str] = []
    candidates = [module_path]
    if module_path.startswith("scripts."):
        candidates.append(module_path.removeprefix("scripts."))
    for candidate in candidates:
        try:
            module = importlib.import_module(candidate)
            break
        except ImportError as exc:
            import_errors.append(f"{candidate!r}: {exc}")
    if module is None:
        raise AgentUnavailableError(
            f"Failed to import adapter for agent {name!r}. Tried: "
            + "; ".join(import_errors)
            + ". This usually means the adapter file hasn't been implemented yet."
        )

    try:
        adapter_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise AgentUnavailableError(
            f"Adapter class {class_name!r} not found in module "
            f"{module_path!r} for agent {name!r}."
        ) from exc

    adapter: AgentAdapter = adapter_cls()
    _ADAPTER_CACHE[name] = adapter
    return adapter


def _enforce_resume_policy(
    agent_name: str,
    session_id: str | None,
    entrypoint: str,
) -> None:
    """Enforce resume policy from the registry.

    Bridge-only agents, including Codex, may resume scoped conversations.
    Delegate/dispatch/consult never resume; each task gets fresh context.

    If a caller tries to pass ``session_id`` when policy forbids it, we
    raise ValueError. This is a hard invariant — we'd rather crash loudly
    at the boundary than let a coding-task invocation silently carry
    stale context from a different worktree.
    """
    if session_id is None:
        return  # No resume requested → nothing to enforce.

    entry = get_agent_entry(agent_name)
    policy = entry["resume_policy"]

    if policy == "never":
        raise ValueError(
            f"Agent {agent_name!r} has resume_policy='never' but a session_id "
            f"was passed. This is a hard constraint (see docs/design/"
            f"agent-runtime.md § 6.3). If you believe this is wrong, change "
            f"the registry, not the call site."
        )

    if policy == "bridge_only" and entrypoint not in ("bridge",):
        raise ValueError(
            f"Agent {agent_name!r} has resume_policy='bridge_only' but "
            f"session_id was passed from entrypoint={entrypoint!r}. Only "
            f"the 'bridge' entrypoint may use session resume for this "
            f"agent. delegate/dispatch/consult must always start fresh."
        )


def _build_usage_record(
    *,
    agent: str,
    entrypoint: str,
    model: str,
    mode: str,
    task_id: str | None,
    cwd: Path,
    session_id: str | None,
    session_id_out: str | None = None,
    duration_s: float,
    input_chars: int,
    output_chars: int,
    returncode: int | None,
    outcome: str,
    rate_limited: bool,
    stalled: bool,
    stderr_excerpt: str | None,
    tokens: int | None,
) -> dict[str, Any]:
    """Assemble the usage record dict per design doc § 4.5 schema."""
    # Ensure unbounded strings are capped so the JSON stays under POSIX PIPE_BUF (4KB)
    # to maintain atomic append guarantees in usage.py.
    safe_cwd = str(cwd)[-250:] if cwd else ""
    safe_task_id = task_id[:100] if task_id else None
    safe_session_id = session_id[:100] if session_id else None
    session_mode = "none"
    if session_id is None and session_id_out is not None:
        session_mode = "new"
    elif session_id is not None and session_id_out is not None:
        session_mode = "resume"
    elif session_id is not None and session_id_out is None:
        session_mode = "none"

    return {
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent,
        "entrypoint": entrypoint,
        "task_id": safe_task_id,
        "cwd": safe_cwd,
        "model": model,
        "mode": mode,
        "session_id": safe_session_id,
        "session_mode": session_mode,
        "duration_s": round(duration_s, 2),
        "input_chars": input_chars,
        "output_chars": output_chars,
        "returncode": returncode,
        "outcome": outcome,
        "rate_limited": rate_limited,
        "stalled": stalled,
        "stderr_excerpt": (
            redact_text(stderr_excerpt)[:500] if stderr_excerpt else None
        ),
        "tokens": tokens,
    }


def invoke(
    agent_name: str,
    prompt: str,
    *,
    mode: str = "read-only",
    cwd: Path | None = None,
    model: str | None = None,
    task_id: str | None = None,
    session_id: str | None = None,
    tool_config: dict | None = None,
    entrypoint: str = "runtime",
    hard_timeout: int = 3600,
    stall_timeout: int = 180,  # accepted but ignored; see docstring
    skip_headroom_check: bool = False,
) -> Result:
    """Single entry point for all agent CLI invocations.

    Args:
        agent_name: Registry key. Must be in AGENTS and have
            ``cli_available: True``.
        prompt: Prompt text to send to the agent. Adapters decide whether
            to pipe this via stdin or embed it in the command.
        mode: Sandbox mode. One of ``{"read-only", "workspace-write", "danger"}``.
            Must be in ``adapter.supported_modes``.
        cwd: Working directory for the subprocess. MANDATORY for write
            modes (``workspace-write``, ``danger``). Optional for
            ``read-only``. Runner validates this.
        model: Model override. If None, uses ``adapter.default_model``.
        task_id: Optional task identifier carried into the usage record
            and passed to the adapter for session tracking.
        session_id: Session to resume, if the caller's entrypoint and the
            adapter's ``resume_policy`` both allow it. See § 6.3.
        tool_config: Adapter-specific tool configuration dict. For Claude
            and Gemini this carries MCP server names and allowed-tools
            strings. Adapters ignore keys they don't understand.
        entrypoint: Who called us — drives resume policy enforcement and
            usage record labeling. One of: ``"bridge"``, ``"dispatch"``,
            ``"delegate"``, ``"consult"``, ``"runtime"``.
        hard_timeout: Absolute wall-clock max in seconds. Default 30 min.
            Triggers AgentTimeoutError on overflow.
        stall_timeout: Accepted for backward compatibility but NO LONGER
            USED as a kill condition. Removed from the kill path on
            2026-04-10 after repeated production incidents where
            successful long-running calls were killed as false-positive
            stalls. See watchdog.py::should_kill() docstring for the
            full incident chain. hard_timeout is the only safety net now.
        skip_headroom_check: Skip the pre-call rate-limit cache. Use only when
            the caller has deliberately switched to a different quota/auth path
            from the cached failure, such as Gemini API-key quota exhaustion
            falling back to OAuth/subscription credentials.

    Returns:
        Result with ok, response, timing, session_id, and the full usage
        record that was written to disk.

    Raises:
        AgentUnavailableError: Unknown agent or adapter import failed.
        ValueError: Invalid mode, missing cwd for write mode, or resume
            policy violation.
        RateLimitedError: has_headroom() reports recent rate limit, OR
            adapter.parse_response() classified the failure as rate-limited.
        AgentTimeoutError: Wall-clock runtime exceeded hard_timeout.
    """
    # ---------- 1. Resolve adapter ----------
    adapter = _load_adapter(agent_name)

    # ---------- 2. Validate mode ----------
    if mode not in adapter.supported_modes:
        raise ValueError(
            f"Agent {agent_name!r} does not support mode {mode!r}. "
            f"Supported modes: {sorted(adapter.supported_modes)}"
        )

    # ---------- 3. Validate cwd for write modes ----------
    if mode in ("workspace-write", "danger") and cwd is None:
        raise ValueError(
            f"cwd is mandatory for mode={mode!r}. Write-capable invocations "
            f"must pin their working directory to prevent cross-worktree "
            f"contamination."
        )
    effective_cwd = cwd or Path.cwd()

    # ---------- 4. Resume policy ----------
    _enforce_resume_policy(agent_name, session_id, entrypoint)

    # ---------- 5. Pre-call rate-limit check ----------
    effective_model = model or adapter.default_model
    ok, reason = (True, "") if skip_headroom_check else has_headroom(
        agent_name,
        effective_model,
    )
    if not ok:
        # Record the short-circuit for observability — the caller didn't
        # burn a quota slot, but we still want the usage log to show it.
        record = _build_usage_record(
            agent=agent_name,
            entrypoint=entrypoint,
            model=effective_model,
            mode=mode,
            task_id=task_id,
            cwd=effective_cwd,
            session_id=session_id,
            session_id_out=None,
            duration_s=0.0,
            input_chars=len(prompt),
            output_chars=0,
            returncode=None,
            outcome="rate_limited",
            rate_limited=True,
            stalled=False,
            stderr_excerpt=f"pre-call headroom check: {reason}",
            tokens=None,
        )
        write_record(record)
        raise RateLimitedError(agent_name, effective_model, reason)

    # ---------- 6. Build invocation plan ----------
    effective_tool_config = merge_delegate_claude_tool_config(
        agent_name,
        entrypoint,
        tool_config,
    )
    if agent_name == "agy":
        tc = dict(effective_tool_config or {})
        tc.setdefault("hard_timeout", hard_timeout)
        effective_tool_config = tc
    plan = adapter.build_invocation(
        prompt=prompt,
        mode=mode,
        cwd=effective_cwd,
        model=effective_model,
        task_id=task_id,
        session_id=session_id,
        tool_config=effective_tool_config,
    )

    # Build a sanitized child environment. We do NOT mutate os.environ itself:
    # the parent may need broad orchestration credentials, but model child
    # processes should only inherit normal shell settings plus the credential
    # for the provider being invoked. ``None`` in env_overrides removes a name
    # for this child only, used by Gemini OAuth fallback to strip API keys.
    env = build_agent_env(provider=agent_name, overrides=plan.env_overrides)

    # ---------- 7–9. Run the subprocess with watchdog ----------
    # The file-change guard (require_file_change_on_write) needs a HEAD +
    # porcelain baseline for any write mode; the push-verify block below needs
    # a HEAD baseline for danger mode. Snapshot HEAD when either applies.
    require_file_change = (
        mode in _WRITE_MODES
        and bool(getattr(adapter, "require_file_change_on_write", False))
    )
    head_before = (
        _git_head_sha(effective_cwd)
        if (mode == "danger" or require_file_change)
        else None
    )
    porcelain_before = (
        _git_status_porcelain(effective_cwd) if require_file_change else None
    )
    start_time = time.monotonic()
    proc: subprocess.Popen | None = None
    watchdog_state: WatchdogState | None = None
    watchdog_threads: list = []  # threading.Thread, loose-typed to avoid import

    try:
        try:
            proc = subprocess.Popen(
                plan.cmd,
                stdin=subprocess.PIPE if plan.stdin_payload else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(effective_cwd),
                env=env,
                # bufsize=1 = line-buffered. Critical for stall watchdog: the
                # default (-1 = io.DEFAULT_BUFFER_SIZE, typically 8KB) makes
                # the stdout streamer thread wait for a full buffer before
                # seeing *any* lines. Quiet CLIs like Codex `-o <file>` emit
                # only a few short lines over many minutes; with default
                # buffering the streamer sees nothing for the whole run and
                # the watchdog falsely stalls. (Fixed 2026-04-10.)
                bufsize=1,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            # Popen failed at spawn time — most commonly because the
            # CLI binary isn't on PATH. The public contract documents
            # AgentUnavailableError for this case; without this
            # translation we'd raise a raw FileNotFoundError and skip
            # writing a usage record. Codex 2026-04-10 audit finding.
            record = _build_usage_record(
                agent=agent_name,
                entrypoint=entrypoint,
                model=effective_model,
                mode=mode,
                task_id=task_id,
                cwd=effective_cwd,
                session_id=session_id,
                session_id_out=None,
                duration_s=time.monotonic() - start_time,
                input_chars=len(prompt),
                output_chars=0,
                returncode=None,
                outcome="error",
                rate_limited=False,
                stalled=False,
                stderr_excerpt=(
                    f"Popen failed: {type(exc).__name__}: {exc}"
                )[:500],
                tokens=None,
            )
            write_record(record)
            raise AgentUnavailableError(
                f"{agent_name!r} Popen failed: {type(exc).__name__}: {exc}"
            ) from exc

        # Write stdin non-blockingly (we'll drain via watchdog threads,
        # so we can close stdin right after writing the payload).
        if plan.stdin_payload and proc.stdin is not None:
            try:
                proc.stdin.write(plan.stdin_payload)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Subprocess died before reading stdin; watchdog will catch it.

        # Start watchdog threads (stdout streamer + mtime poller).
        liveness_paths = list(adapter.liveness_signal_paths(plan))
        if plan.output_file is not None and plan.output_file not in liveness_paths:
            liveness_paths.append(plan.output_file)
        watchdog_state, watchdog_threads = start_watchdog(proc, liveness_paths)

        # Poll loop — wait for subprocess to exit OR hard_timeout to fire
        # OR the adapter's early-reap detector to fire.
        #
        # Stall detection was removed from the kill path on 2026-04-10
        # (see watchdog.py::should_kill docstring). Hard timeout is the
        # wall-clock safety net.
        #
        # Early reap (2026-04-10): adapters MAY implement
        # check_early_reap(plan, call_start_time) -> bool. If present
        # and True, the runner kills the subprocess immediately and
        # falls through to parse_response, which is expected to recover
        # the response from the adapter's persistent state file. This
        # is the fix for Codex 0.118 post-completion hangs — the CLI
        # writes its answer to the rollout file then sits in Tokio
        # cond_wait forever. CodexAdapter returns True the moment a
        # task_complete event appears in the rollout JSONL, which
        # unblocks the call in ~10s instead of the full hard_timeout.
        early_reap_check = getattr(adapter, "check_early_reap", None)
        kill_reason: str | None = None
        while True:
            returncode = proc.poll()
            if returncode is not None:
                break

            # Early reap — adapter-provided readiness check.
            if early_reap_check is not None:
                try:
                    if early_reap_check(plan, call_start_time=start_time):
                        # Response ready on disk. Kill and reap.
                        returncode = proc.poll()
                        if returncode is not None:
                            # Race: process exited between poll and
                            # early_reap_check. Normal exit, no kill.
                            kill_reason = None
                            break
                        kill_reason = "early_reap"
                        proc.kill()
                        with contextlib.suppress(subprocess.TimeoutExpired):
                            proc.wait(timeout=5.0)
                        break
                except Exception:
                    # An adapter bug in check_early_reap must never
                    # crash the whole invocation. Fall through to
                    # normal poll/kill logic.
                    _LOGGER.exception("Adapter early-reap probe failed")

            kill_reason = should_kill(watchdog_state, stall_timeout, hard_timeout)
            if kill_reason is not None:
                # Race-check (Gemini review finding #1): the subprocess may
                # have exited between proc.poll() above and should_kill()
                # returning True. Re-check before killing, because killing
                # a process that already exited successfully and then
                # classifying the run as a kill would discard a good result.
                returncode = proc.poll()
                if returncode is not None:
                    kill_reason = None
                    break
                proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=5.0)
                break
            time.sleep(_POLL_INTERVAL_S)

        duration_s = time.monotonic() - start_time

        # Watchdog state is guaranteed non-None here because start_watchdog
        # always returns a state (it was called unconditionally above).
        assert watchdog_state is not None

        # Drain both streamer threads before reading captured lines.
        # Without these joins, the final tail of stdout/stderr may still
        # be sitting in the OS pipe buffer, causing truncated responses
        # on fast-exiting subprocesses. (Gemini review finding #2,
        # extended to stderr on 2026-04-10 after discovering that
        # proc.stderr.read() at completion time was the ROOT CAUSE of
        # Codex post-completion hangs for tool-heavy tasks — the stderr
        # pipe filled up during the run and blocked Codex's writes.)
        for t in watchdog_threads:
            if "stdout" in t.name or "stderr" in t.name:
                t.join(timeout=5.0)

        # Read captured stdout AND stderr from watchdog state. We no
        # longer call proc.stderr.read() because the _stderr_streamer
        # thread now drains stderr in parallel with stdout during the
        # run, preventing pipe-buffer backpressure from blocking the
        # subprocess. See watchdog.py::_stderr_streamer for the full
        # incident chain.
        stdout_text = "".join(watchdog_state.stdout_lines)
        stderr_text = "".join(watchdog_state.stderr_lines)

        # ---------- Parse response FIRST, then decide kill outcome ----------
        #
        # CRITICAL (2026-04-10): we MUST call adapter.parse_response() even
        # when the subprocess was hard-killed. Otherwise we throw away the
        # adapter's ability to recover work that was already completed and
        # written to disk before the kill.
        #
        # Specifically: the Gemini CLI can block-buffer stdout for minutes
        # while actively streaming its response into
        # ~/.gemini/tmp/<project>/chats/session-*.json. On a hard_timeout
        # kill, stdout is empty but the session file has the full (or
        # partial-but-usable) response. GeminiAdapter.parse_response reads
        # that file and returns ok=True with the recovered response.
        #
        # The old flow raised AgentTimeoutError immediately on kill and
        # never gave the adapter a chance to recover. That forced the
        # dispatcher's cascade to retry the same call on a different
        # model — wasting another 15 minutes on work that was ALREADY
        # DONE and sitting on disk.
        #
        # New flow: always parse, then raise only if parse_response couldn't
        # recover anything meaningful (ok == False).
        stop_watchdog(watchdog_state, watchdog_threads, proc=proc)
        parse: ParseResult = adapter.parse_response(
            stdout=stdout_text,
            stderr=stderr_text,
            returncode=proc.returncode if proc.returncode is not None else -1,
            output_file=plan.output_file,
            plan=plan,
            call_start_time=start_time,
        )

        # ---------- Handle hard_timeout AFTER parse_response ----------
        if kill_reason == "hard_timeout" and not parse.ok:
            # Parse could not recover a usable response from disk. This
            # is a true hard timeout — raise so the caller can cascade
            # to a different model.
            record = _build_usage_record(
                agent=agent_name,
                entrypoint=entrypoint,
                model=effective_model,
                mode=mode,
                task_id=task_id,
                cwd=effective_cwd,
                session_id=session_id,
                session_id_out=parse.session_id,
                duration_s=duration_s,
                input_chars=len(prompt),
                output_chars=len(stdout_text),
                returncode=proc.returncode,
                outcome="hard_timeout",
                rate_limited=False,
                stalled=False,
                stderr_excerpt=(
                    parse.stderr_excerpt
                    or stderr_text[:500]
                    or tail_liveness_file_for_debug(liveness_paths)[:500]
                ),
                tokens=None,
            )
            write_record(record)
            raise AgentTimeoutError(agent_name, hard_timeout)

        # If parse.ok after a hard_timeout kill, we successfully recovered
        # from disk. Fall through to the normal success path — the usage
        # record will show outcome=ok but the stderr_excerpt carries the
        # adapter's "recovered N chars from ..." note so the recovery is
        # visible in logs.

        # "stalled" kill branch removed 2026-04-10 — should_kill() no
        # longer returns "stalled". Only hard_timeout is in the kill
        # path now. AgentStalledError remains importable from errors.py
        # for backward compatibility with test mocks, but is never raised.

        # ---------- Classify outcome ----------
        if parse.rate_limited:
            outcome = "rate_limited"
        elif parse.ok:
            outcome = "ok"
        else:
            outcome = "error"

        push_verify_error: str | None = None
        if mode == "danger" and parse.ok:
            head_after = _git_head_sha(effective_cwd)
            if not (
                head_before is not None
                and head_after is not None
                and head_before == head_after
            ):
                # Defense in depth: any agent in danger mode that lands commits
                # could silent-fail-push (e.g., sandbox env issue). Codex was the
                # original observed case (PR #907 round-2), but the verify is
                # cheap (one git ls-remote) and applies to all agents.
                push_ok, push_verify_error = verify_current_branch_pushed(effective_cwd)
                if not push_ok:
                    outcome = "error"

        # File-change guard: adapters that set require_file_change_on_write (agy,
        # for the #2099 headless no-write flake) must not report a silent
        # false-success. If a write-mode run parsed ok but left the worktree
        # byte-identical (HEAD unchanged AND porcelain identical before/after),
        # downgrade to a retryable error. agy writes files WITHOUT committing, so
        # the HEAD-only danger guard above passes trivially on an empty run —
        # this porcelain check is what actually catches it. Gated on parse.ok so
        # a genuine agent error keeps its own diagnostics.
        no_file_change_error: str | None = None
        if require_file_change and parse.ok and push_verify_error is None:
            head_after = _git_head_sha(effective_cwd)
            porcelain_after = _git_status_porcelain(effective_cwd)
            head_unchanged = (
                head_before is not None
                and head_after is not None
                and head_before == head_after
            )
            porcelain_unchanged = (
                porcelain_before is not None
                and porcelain_after is not None
                and porcelain_before == porcelain_after
            )
            # Only fire when we could actually MEASURE both dimensions and both
            # show no change. If git failed (None), we can't prove no-write, so
            # we don't punish the run.
            if head_unchanged and porcelain_unchanged:
                no_file_change_error = (
                    f"{agent_name} reported success but produced no file change "
                    "in the worktree — likely headless no-write flake (#2099); "
                    "retry."
                )
                outcome = "error"

        verify_error = push_verify_error or no_file_change_error

        record = _build_usage_record(
            agent=agent_name,
            entrypoint=entrypoint,
            model=effective_model,
            mode=mode,
            task_id=task_id,
            cwd=effective_cwd,
            session_id=session_id,
            session_id_out=parse.session_id,
            duration_s=duration_s,
            input_chars=len(prompt),
            output_chars=len(parse.response),
            returncode=proc.returncode,
            outcome=outcome,
            rate_limited=parse.rate_limited,
            stalled=False,
            stderr_excerpt=verify_error or parse.stderr_excerpt,
            tokens=parse.tokens,
        )
        write_record(record)

        if parse.rate_limited:
            raise RateLimitedError(
                agent_name,
                effective_model,
                reason=(parse.stderr_excerpt or "")[:200],
            )

        return Result(
            ok=parse.ok and verify_error is None,
            agent=agent_name,
            model=effective_model,
            mode=mode,
            response=parse.response,
            stderr_excerpt=verify_error or parse.stderr_excerpt,
            duration_s=duration_s,
            stderr=stderr_text,
            session_id=parse.session_id,
            rate_limited=parse.rate_limited,
            stalled=False,
            returncode=proc.returncode,
            usage_record=record,
        )

    finally:
        # Cleanup ordering matters (Gemini 2026-04-10 review finding):
        #
        # 1. If proc is still alive (e.g. a KeyboardInterrupt or unexpected
        #    exception fired mid-poll), we MUST kill it before closing
        #    stdout. Closing stdout on an alive proc gives the child
        #    SIGPIPE on its next write, and more importantly leaks an
        #    orphan if we never explicitly kill.
        #
        # 2. Only after proc has exited do we call stop_watchdog(proc=proc),
        #    which closes proc.stdout to unblock the streamer thread.
        #
        # proc may be None if Popen itself raised — skip the kill.
        if proc is not None and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=5.0)

        if watchdog_state is not None:
            stop_watchdog(watchdog_state, watchdog_threads, proc=proc)
        # Clean up the output file if the adapter created one and parse
        # succeeded — callers get the content in Result.response, no need
        # to keep the tempfile. On error, leave it for debugging.
        if (
            plan is not None  # type: ignore[possibly-undefined]
            and plan.output_file is not None
            and proc is not None
            and proc.returncode == 0
            and plan.output_file.exists()
            and str(plan.output_file).startswith("/tmp/")
        ):
            with contextlib.suppress(OSError):
                plan.output_file.unlink()
