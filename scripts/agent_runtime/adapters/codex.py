"""CodexAdapter — wraps ``codex exec`` for the agent runtime.

First real adapter. Proves the protocol shape works against a real CLI.
Lifted from the prior art in ``scripts/ai_agent_bridge/_codex.py`` and
``scripts/build/dispatch.py`` (Codex branch) — same flag semantics, now
routed through the unified runtime.

Key design points:

- **CLI resume support.** CodexAdapter follows the registry resume
  policy and accepts ``session_id`` for bridge sessions by invoking
  ``codex resume <id>`` when provided.
- **One mode: danger only.** read-only and workspace-write are forbidden —
  Codex needs network + filesystem to fact-check and to use the live web
  tool. See PR #981 (mode=danger mandatory) and this PR (workspace-write
  escape hatch removed).
- **Output file always used.** ``codex exec -o <tmpfile>`` writes the final
  agent message to a file; we read it in ``parse_response``. The file path
  goes into ``liveness_signal_paths`` so the runner's mtime poller catches
  Codex writing progress even when stdout is quiet.
- **Session ID parsed from stdout.** The CLI prints "session id: <uuid>"
  somewhere in stdout; we extract it for the usage record and may reuse it
  for subsequent bridge rounds.

Issue: #1184
"""
from __future__ import annotations

import json
import re
import shutil
import os
import tempfile
from pathlib import Path

from ..result import ParseResult
from .base import InvocationPlan

# Matches the session id line in Codex stdout. Case-insensitive.
_SESSION_RE = re.compile(r"session id:\s*([0-9a-f-]{8,})", re.IGNORECASE)
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")

# Stderr phrases that indicate the provider rate-limited us. Ordered
# roughly by specificity — specific phrases first, generic last.
_RATE_LIMIT_PATTERNS = (
    r"usage limit reached",
    r"rate limit",
    r"rate_limit",
    r"quota exceeded",
    r"too many requests",
    r"\bHTTP 429\b",
    r"\bstatus 429\b",
    r"\b429\b",
)
_RATE_LIMIT_RE = re.compile("|".join(_RATE_LIMIT_PATTERNS), re.IGNORECASE)

# Matches a dashes-only line (at least 3 dashes, nothing else on the
# line). Used to split Codex's stderr into segments so we can isolate
# the post-prompt portion for rate-limit pattern matching. MULTILINE
# so ^/$ match at each line boundary.
_CODEX_DIVIDER_LINE_RE = re.compile(r"^-{3,}\s*$", re.MULTILINE)


def _strip_codex_prompt_echo(stderr: str) -> str:
    """Return only the portion of Codex stderr that is safe to
    pattern-match for rate-limit errors.

    Codex CLI (with -o <file>) lays out stderr as a sequence of
    sections separated by dashes-only lines::

        OpenAI Codex v0.118.0 ...       ← banner
        --------
        workdir: ...
        model: ...
        --------
        user                            ← echoed prompt starts
        <entire user prompt>
        --------
        codex                           ← Codex's own output
        <reasoning + final message>
        tokens used
        <n>

    On a rate-limit error, Codex exits non-zero and writes the error
    message AFTER the last divider — in the "codex" or equivalent
    section. The echoed user prompt can contain ANY text, including
    legitimate inline dashes-only lines (a code block showing a
    divider, a Markdown horizontal rule, a consultation prompt
    literally discussing rate limits). Any regex that tries to
    identify "the prompt block" by matching between two dividers can
    be defeated by a prompt containing its own dividers.

    Fix: don't try to strip the prompt at all. Instead, take the
    stderr body AFTER the LAST divider line — that region is
    guaranteed to be Codex's own output, never echoed prompt, because
    the prompt echo always appears before Codex's response section.
    If there are no dividers at all (degenerate cases: truncated
    output, early crash before banner), fall back to the whole
    stderr.

    See #1184 Gemini 2026-04-10 review for the incident that led here.
    """
    if not stderr:
        return stderr
    # Find the position right after the LAST divider line.
    last_divider = None
    for m in _CODEX_DIVIDER_LINE_RE.finditer(stderr):
        last_divider = m
    if last_divider is None:
        # No dividers — return as-is. Likely a very early crash.
        return stderr
    return stderr[last_divider.end():]


class CodexAdapter:
    """Adapter for ``codex exec`` (OpenAI ChatGPT Codex CLI)."""

    name: str = "codex"
    default_model: str = "gpt-6-sol"
    supported_modes: frozenset[str] = frozenset({"danger"})

    def build_invocation(
        self,
        *,
        prompt: str,
        mode: str,
        cwd: Path,
        model: str | None,
        task_id: str | None,
        session_id: str | None,
        tool_config: dict | None,
    ) -> InvocationPlan:
        """Build the codex exec invocation.

        Uses ``session_id`` as ``codex resume <id>`` when present.
        Supports ``tool_config`` flags from bridge:

        - ``{"enable_search": True}`` enables web grounding in `codex`.
        - Any other keys are ignored.
        """
        tc = tool_config or {}

        # Reset per-invocation state so _read_latest_rollout_task_complete
        # uses a fresh rollout snapshot (prevents cross-contamination
        # between consecutive calls on the same adapter instance).
        # Codex 2026-04-10 audit.
        self._reset_per_invocation_state()

        # Resolve binary. shutil.which handles PATH lookup; fall back to
        # bare "codex" if not on PATH so subprocess.Popen can report the
        # error clearly.
        codex_bin = shutil.which("codex") or "codex"

        # Pick a unique output file inside /tmp.
        # Include task_id for human debuggability, but sanitize it:
        # arbitrary task_id strings (issue slugs, URLs, user input)
        # could contain slashes, nulls, or path separators that would
        # make NamedTemporaryFile create files in unintended locations
        # or fail entirely. Strip everything that isn't alphanumeric
        # or a safe punctuation char. Codex 2026-04-10 audit finding.
        safe_suffix = ""
        if task_id:
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in task_id)
            safe_suffix = f"-{safe[:60]}"  # cap length too
        with tempfile.NamedTemporaryFile(
            prefix=f"codex-runtime{safe_suffix}-",
            suffix=".txt",
            delete=False,
        ) as output_fd:
            output_path = Path(output_fd.name)

        # --search enables Codex's live web tool. Top-level flag, not an
        # exec subflag. Driven by KUBEDOJO_CODEX_SEARCH so dispatch_smart
        # can set it per task class.
        # Default OFF for non-bridge callers; explicit tool_config from
        # bridge enables web grounding for investigation.
        if "enable_search" in tc:
            use_search = bool(tc.get("enable_search"))
        else:
            use_search = os.environ.get("KUBEDOJO_CODEX_SEARCH", "0") == "1"
        cmd: list[str] = [codex_bin]
        effort = os.environ.get("KUBEDOJO_CODEX_EFFORT", "").strip()
        if effort:
            cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
        if session_id:
            if use_search:
                cmd.append("--search")
            cmd.extend(
                [
                    "exec",
                    "resume",
                    session_id,
                    "--skip-git-repo-check",
                    "-o", str(output_path),
                    "-m", model or self.default_model,
                ]
            )
            cmd.extend(self._mode_flags(mode))
            cmd.append("-")
            return InvocationPlan(
                cmd=cmd,
                cwd=cwd,
                stdin_payload=prompt,
                output_file=output_path,
                env_overrides={},
                liveness_paths=(output_path,),
            )

        if use_search:
            cmd.append("--search")
        cmd.extend(
            [
                "exec",
                "--skip-git-repo-check",
                "-C", str(cwd),
                "--color", "never",
                "-o", str(output_path),
                "-m", model or self.default_model,
            ]
        )
        cmd.extend(self._mode_flags(mode))
        cmd.append("-")  # Read prompt from stdin.

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload=prompt,
            output_file=output_path,
            env_overrides={},
            liveness_paths=(output_path,),
        )

    def parse_response(
        self,
        *,
        stdout: str,
        stderr: str,
        returncode: int,
        output_file: Path | None,
        plan: InvocationPlan | None = None,
        call_start_time: float | None = None,
    ) -> ParseResult:
        """Parse the codex exec output into a ParseResult.

        Codex writes its final message to the ``-o <file>`` path. We read
        it regardless of returncode — some failure modes still leave a
        useful partial message in the file, and it's often more informative
        than stderr.

        Fallback recovery (added 2026-04-10): codex-cli 0.118 has a
        post-completion hang bug where the CLI generates the full answer,
        writes a ``task_complete`` event to
        ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``, then hangs at
        0% CPU without ever flushing ``-o <file>`` or exiting. Previously
        this meant the runtime waited the full hard_timeout and returned
        an empty response. Now, if ``-o <file>`` is empty, we scan the
        newest rollout file for a ``task_complete`` event and extract
        its ``last_agent_message``. Parallels the Gemini adapter's
        session-file fallback.
        """
        # Read the output file if it exists. Tolerate all errors.
        file_output = ""
        if output_file is not None and output_file.exists():
            try:
                file_output = output_file.read_text("utf-8", errors="replace").strip()
            except OSError:
                file_output = ""

        # Fallback: if the -o file is empty, scan the rollout JSONL for
        # a task_complete event. This handles the 0.118 post-completion
        # hang where Codex has the answer on disk but never flushes -o.
        rollout_response = ""
        rollout_source_note: str | None = None
        if not file_output and plan is not None:
            rollout_response = self._read_latest_rollout_task_complete(
                plan, call_start_time=call_start_time,
            )
            if rollout_response:
                reason = (
                    "rc=0 but -o empty (post-completion hang)"
                    if returncode == 0
                    else f"rc={returncode}, -o empty"
                )
                rollout_source_note = (
                    f"recovered {len(rollout_response)} chars from "
                    f"~/.codex/sessions/.../rollout-*.jsonl (reason: {reason})"
                )

        # durable_output is the response we'll return on success:
        # either the -o file or the rollout-recovered answer.
        durable_output = file_output or rollout_response

        # Rate-limit detection — with THREE critical caveats.
        #
        # Codex CLI (with -o <file>) writes everything to stderr: the
        # startup banner, the echoed user prompt, the reasoning trace,
        # AND real error messages. Pattern-matching stderr naively is
        # broken because user prompts can contain ANY human-language
        # phrase, including "rate limit" and "usage limit reached" (our
        # own bridge standing rules literally do).
        #
        # Fix 1 (prompt echo sanitization): take the stderr body AFTER
        # the last "--------" divider line. The closing prompt divider
        # always has Codex's own output after it, so anything past the
        # last divider is guaranteed to be Codex's actual response,
        # never echoed user prompt. See _strip_codex_prompt_echo.
        #
        # Fix 2 (success guard): even after sanitization, rate_limited
        # is only TRUE when the call actually failed (returncode != 0
        # OR empty output file). A successful Codex exec with a
        # non-empty final message in the -o file CANNOT be rate-limited,
        # period. This mirrors the same guard we have on GeminiAdapter.
        #
        # Fix 3 (signal-killed processes, Codex 2026-04-10 review):
        # a negative returncode means the process was killed by a
        # signal (SIGTERM, SIGKILL, SIGINT — Python/POSIX convention
        # reports -SIGNUM for signaled exits). If we killed the process
        # ourselves (hard_timeout, cancel, exception mid-poll), its
        # stderr may contain ONLY a partial prompt echo — no closing
        # divider, no Codex response section — and my "take stderr
        # after last divider" heuristic will return the prompt body
        # itself. To prevent that class of false positive, skip
        # pattern matching entirely on signaled exits. A signaled
        # exit is classified as "failed", never as "rate_limited",
        # because we KNOW why the process died: we killed it.
        if returncode is not None and returncode < 0:
            # Signaled exit — don't even look at stderr for rate limits.
            rate_limited = False
        else:
            stderr_for_check = _strip_codex_prompt_echo(stderr)
            combined_for_rl_check = "\n".join(
                part for part in (stdout, stderr_for_check, durable_output) if part
            )
            pattern_hit = bool(_RATE_LIMIT_RE.search(combined_for_rl_check))
            # Call failed if neither -o nor rollout gave us content.
            call_failed = returncode != 0 or not durable_output
            rate_limited = pattern_hit and call_failed

        # Session id comes from stdout in Codex.
        session_id: str | None = None
        session_match = _SESSION_RE.search(stdout or "")
        if session_match:
            session_id = session_match.group(1)
        if session_id is None and plan is not None:
            session_id = self._read_latest_rollout_session_id(
                plan,
                call_start_time=call_start_time,
            )

        # Success classification: we have content (from either -o or the
        # rollout fallback) AND we're not rate-limited. Note that a
        # post-completion hang will have returncode == -9 (because WE
        # killed it after the early-reap detector fires) but durable_output
        # will be populated from rollout. That's a successful recovery,
        # NOT a failure. So returncode is no longer a veto — content is.
        ok = bool(durable_output) and not rate_limited
        response = durable_output if ok else ""
        stderr_excerpt: str | None = None
        if not ok:
            # Build a useful excerpt: stderr first, then file_output as
            # fallback (Codex often puts errors in the output file).
            excerpt_parts: list[str] = []
            if stderr.strip():
                excerpt_parts.append(stderr.strip())
            if not stderr.strip() and file_output:
                excerpt_parts.append(f"[codex output file]\n{file_output}")
            stderr_excerpt = "\n".join(excerpt_parts)[:500] or None
        elif rollout_source_note:
            # We recovered from the rollout file. Surface the note so
            # logs/usage records show it.
            stderr_excerpt = rollout_source_note

        return ParseResult(
            ok=ok,
            response=response,
            stderr_excerpt=stderr_excerpt,
            rate_limited=rate_limited,
            session_id=session_id,
            tokens=None,  # codex exec does not expose token counts.
        )

    # ---------------------------------------------------------------------
    # Early reap — break out of Codex CLI's post-completion hang
    # ---------------------------------------------------------------------

    def check_early_reap(
        self,
        plan: InvocationPlan,
        *,
        call_start_time: float | None = None,
    ) -> bool:
        """Return True if the Codex rollout JSONL has a task_complete event.

        This is the fix for the Codex 0.118.0 post-completion hang.
        Verified empirically 2026-04-10: all Codex threads end up in
        _pthread_cond_wait on an internal Tokio runtime condition
        variable AFTER writing task_complete to the rollout file. The
        process never exits on its own. Without this method the runner
        would wait the full hard_timeout (1h+) on every such hang.

        The runner calls this periodically (every few poll ticks). When
        it returns True, the runner kills the subprocess and falls
        through to ``parse_response()``, which recovers the response
        via ``_read_latest_rollout_task_complete()``.

        Optimizations to keep overhead negligible:
        1. Warmup window: don't scan before 5 seconds elapsed.
           Codex can't possibly have emitted task_complete that early.
        2. Throttle: at most one scan every 2 seconds per adapter
           instance.
        3. Mtime gate: skip the scan if the rollout directory mtime
           hasn't changed since the last scan. The sessions dir bumps
           on every file creation inside it, and the rollout file's
           OWN mtime bumps on every write. We snapshot the newest
           rollout file's mtime and only re-scan when it advances.
        """
        import time as _time
        now = _time.monotonic()

        # Guard 1: warmup window.
        if call_start_time is not None and (now - call_start_time) < 5.0:
            return False

        # Guard 2: throttle.
        last_check = getattr(self, "_last_early_reap_check", 0.0)
        if now - last_check < 2.0:
            return False
        self._last_early_reap_check = now

        # Guard 3: mtime gate — quick stat instead of a full file scan.
        from datetime import UTC, datetime
        today = datetime.now(UTC)
        sessions_today = (
            Path.home() / ".codex" / "sessions"
            / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
        )
        try:
            if not sessions_today.exists():
                return False
            rollouts = list(sessions_today.glob("rollout-*.jsonl"))
            if not rollouts:
                return False
            newest = max(rollouts, key=lambda p: p.stat().st_mtime)
            current_mtime = newest.stat().st_mtime
        except OSError:
            return False

        last_mtime = getattr(self, "_last_early_reap_mtime", 0.0)
        if current_mtime <= last_mtime:
            # File hasn't advanced since last scan — task_complete
            # can't have been added. Skip the scan.
            return False
        self._last_early_reap_mtime = current_mtime

        # All guards passed — do the actual scan.
        msg = self._read_latest_rollout_task_complete(
            plan, call_start_time=call_start_time,
        )
        return bool(msg)

    # ---------------------------------------------------------------------
    # Rollout-file recovery (post-completion hang fallback)
    # ---------------------------------------------------------------------

    def _candidate_rollout_dirs(self) -> list[Path]:
        """Return today's and yesterday's sessions dirs.

        Yesterday is included so a call that starts at 23:59 UTC and
        finishes at 00:01 UTC doesn't miss its own rollout when the
        day directory rolls over. Codex 2026-04-10 audit finding.
        """
        from datetime import UTC, datetime, timedelta
        base = Path.home() / ".codex" / "sessions"
        dirs: list[Path] = []
        for delta in (0, 1):
            d = datetime.now(UTC) - timedelta(days=delta)
            candidate = base / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}"
            if candidate.exists():
                dirs.append(candidate)
        return dirs

    def _snapshot_preexisting_rollouts(self) -> set[Path]:
        """Snapshot rollout files that exist BEFORE our call starts.

        Stored on the adapter instance the first time check_early_reap
        runs for a given invocation. Any rollout file NOT in the
        snapshot, when a new check happens, is a candidate for "this
        call's rollout" — avoiding the critical cross-contamination bug
        where two concurrent Codex runs would see each other's results.
        Codex 2026-04-10 audit finding.

        Note: adapters are logically stateless across calls, but
        check_early_reap + parse_response are guaranteed to both see
        the same invocation (the runner doesn't reuse an adapter
        instance mid-call). The snapshot is reset on each new
        invocation via _reset_per_invocation_state().
        """
        preexisting: set[Path] = set()
        for d in self._candidate_rollout_dirs():
            try:
                preexisting.update(d.glob("rollout-*.jsonl"))
            except OSError:
                continue
        return preexisting

    def _reset_per_invocation_state(self) -> None:
        """Clear per-invocation caches AND take a fresh snapshot of
        pre-existing rollout files. Called from build_invocation.

        Taking the snapshot eagerly (in build_invocation) instead of
        lazily (on the first check_early_reap call) is correct: we
        want to capture the state of the sessions dir at the MOMENT
        the call begins, not at some arbitrary later time when the
        new rollout may already have been created. Any file present
        when build_invocation runs is "pre-existing" and therefore
        cannot be the current call's rollout.
        """
        self._last_early_reap_check = 0.0
        self._last_early_reap_mtime = 0.0
        self._rollout_snapshot = self._snapshot_preexisting_rollouts()
        self._bound_rollout = None

    def _read_latest_rollout_task_complete(
        self,
        plan: InvocationPlan,
        *,
        call_start_time: float | None = None,
    ) -> str:
        """Extract the ``last_agent_message`` from THIS invocation's
        rollout JSONL.

        Per-invocation identification (fixed 2026-04-10 after Codex
        audit): we do NOT pick the newest rollout file globally,
        because concurrent Codex runs in the same repo would
        cross-contaminate. Instead we:

        1. Snapshot the set of rollout files that existed at the
           moment check_early_reap first runs (stored on the adapter
           as ``_rollout_snapshot``).
        2. On every scan, ignore any file in the snapshot.
        3. From the non-snapshot candidates, pick the one with the
           newest mtime. This is guaranteed to be a file Codex created
           AFTER our call started.
        4. Once we find a candidate, we cache it as ``_bound_rollout``
           — any future calls return the SAME file, so the runner's
           parse_response always sees the rollout scoped to THIS
           invocation.

        Also checks yesterday's sessions dir for UTC-midnight rollover.

        Returns ``last_agent_message`` or ''.
        """
        try:
            rollout_to_scan = self._latest_rollout_file_for_invocation(
                plan,
                call_start_time=call_start_time,
            )
            if rollout_to_scan is None:
                return ""

            # 4. Scan our bound rollout for task_complete
            last_message = ""
            with open(rollout_to_scan, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") != "event_msg":
                        continue
                    payload = event.get("payload") or {}
                    if payload.get("type") != "task_complete":
                        continue
                    msg = payload.get("last_agent_message")
                    if isinstance(msg, str) and msg:
                        last_message = msg

            return last_message
        except Exception:
            # Last-resort fallback: never let a rollout-parse error
            # bubble out of parse_response. Swallow everything and
            # fall back to the primary code path.
            return ""

    def _latest_rollout_file_for_invocation(
        self,
        plan: InvocationPlan,
        *,
        call_start_time: float | None = None,
    ) -> Path | None:
        """Return the bound rollout file for this invocation."""
        _ = call_start_time  # call window narrowing handled by check_early_reap.
        _ = plan  # reserved for future tighter matching by plan.task_id.

        try:
            snapshot: set[Path] = getattr(self, "_rollout_snapshot", None) or set()

            bound: Path | None = getattr(self, "_bound_rollout", None)
            if bound is not None and bound.exists():
                return bound

            all_candidates: list[Path] = []
            for d in self._candidate_rollout_dirs():
                try:
                    all_candidates.extend(d.glob("rollout-*.jsonl"))
                except OSError:
                    continue

            new_candidates = [p for p in all_candidates if p not in snapshot]
            if not new_candidates:
                return None

            rollout_to_scan = max(
                new_candidates,
                key=lambda p: p.stat().st_mtime,
            )
            self._bound_rollout = rollout_to_scan
            return rollout_to_scan
        except Exception:
            return None

    def _read_latest_rollout_session_id(
        self,
        plan: InvocationPlan,
        *,
        call_start_time: float | None = None,
    ) -> str | None:
        """Extract session_id from this invocation's rollout JSONL."""
        rollout_to_scan = self._latest_rollout_file_for_invocation(
            plan,
            call_start_time=call_start_time,
        )
        if rollout_to_scan is None:
            return None

        try:
            with open(rollout_to_scan, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    for key in ("session_id", "sessionId", "id", "sid"):
                        value = event.get(key)
                        if isinstance(value, str) and _UUID_RE.fullmatch(value):
                            return value

                    payload = event.get("payload")
                    if isinstance(payload, dict):
                        for key in ("session_id", "sessionId", "id"):
                            value = payload.get(key)
                            if isinstance(value, str) and _UUID_RE.fullmatch(value):
                                return value
            filename_match = _UUID_RE.search(rollout_to_scan.name)
            if filename_match:
                return filename_match.group(0)
        except Exception:
            return None
        return None

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        """Return paths the runner should poll for mtime changes.

        Note 2026-04-10: stall detection is no longer a kill condition
        (see watchdog.py::should_kill). The mtime poller still runs to
        populate WatchdogState.last_activity for observability — so
        getting the paths RIGHT still matters for future diagnostic
        logging and for the async delegate.py work, even though a
        missed signal no longer kills the process.

        Codex CLI 0.118.0 storage layout (verified empirically):
          - ``sessions/YYYY/MM/DD/rollout-*.jsonl`` is the ACTUAL live
            file. It grows throughout the run as reasoning messages
            and tool calls are streamed to disk. Confirmed: a 9-minute
            consultation run had its rollout file at 409KB and still
            growing.
          - ``sessions/YYYY/MM/DD/`` (the directory) only bumps on
            child file *creation*, not on content writes. Useful for
            catching the startup signal but goes silent during the run.
          - ``state_5.sqlite`` bumps intermittently (not reliably on
            every message). Kept as a secondary signal.
          - ``logs_1.sqlite``, ``history.jsonl`` are stale in 0.118+
            but kept as fallbacks for older CLI versions.
          - ``plan.output_file`` is the -o target; empty during the run
            and only written at the very end on success, but kept as
            a signal for the "Codex is writing the final response" moment.

        We pick the NEWEST rollout-*.jsonl inside today's sessions dir
        and return it directly (same pattern as the Gemini adapter's
        newest session-*.json file), so the mtime poller sees every
        content write, not just directory-level events.
        """
        from datetime import UTC, datetime

        paths: list[Path] = []
        if plan.output_file is not None:
            paths.append(plan.output_file)

        codex_home = Path.home() / ".codex"

        # Secondary / fallback signals
        for rel in ("state_5.sqlite", "history.jsonl", "logs_1.sqlite"):
            candidate = codex_home / rel
            if candidate.exists():
                paths.append(candidate)

        # Today's sessions directory (catches startup via dir mtime
        # bump, but does NOT track subsequent content writes).
        today = datetime.now(UTC)
        sessions_today = (
            codex_home / "sessions" / f"{today.year:04d}"
            / f"{today.month:02d}" / f"{today.day:02d}"
        )
        if sessions_today.exists():
            paths.append(sessions_today)

        # Note: we deliberately do NOT include the newest rollout-*.jsonl
        # file here. Earlier versions tried to track it for
        # last_activity updates, but glob-at-build-time is wrong: the
        # file matching "newest" is the PREVIOUS run's rollout, not
        # this run's (which doesn't exist yet). The wrong file both
        # (a) never updates during our run so provides no liveness
        # signal, and (b) would leak the wrong trace into
        # tail_liveness_file_for_debug() on failure. Removed after
        # Gemini review, 2026-04-10. The directory mtime above still
        # bumps when Codex creates its new rollout file at startup,
        # which is good enough for the dispatch-once-at-start signal
        # the mtime poller actually uses.
        #
        # Proper fix (deferred): pass a glob pattern or a build-time
        # snapshot into the runner and let the poller dynamically
        # resolve "any file matching ROLLOUT_GLOB whose mtime changed
        # after POLL_START". Bigger API change; filed as follow-up.

        return tuple(paths)

    @staticmethod
    def _mode_flags(mode: str) -> list[str]:
        """Map runtime mode → codex exec sandbox flags."""
        if mode == "danger":
            return ["--dangerously-bypass-approvals-and-sandbox"]
        raise ValueError(
            f"CodexAdapter: mode {mode!r} is not supported. "
            "Codex always runs in danger mode (sandbox bypass + live web). "
            f"Supported: {sorted(CodexAdapter.supported_modes)}"
        )
