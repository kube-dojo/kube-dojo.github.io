"""AgentAdapter protocol + InvocationPlan dataclass.

The protocol defines the three methods every agent adapter must implement.
The InvocationPlan dataclass is the return type of ``build_invocation()`` —
everything the runner needs to spawn one subprocess.

Design rationale (from consultation, see docs/design/agent-runtime.md v1 Changelog):

- ``build_invocation`` takes ``session_id`` and ``tool_config`` as inputs —
  Gemini review #1 and #3 caught that omitting these would silently break
  dispatch.py MCP tool restrictions and bridge resume semantics.
- ``parse_response`` returns a rich ``ParseResult`` instead of 3 separate
  protocol methods — Codex review #1 showed the v0 design
  (``detect_rate_limit()`` + ``extract_session_id()`` as separate methods)
  didn't fit all three agents (Claude creates session ID pre-launch, Codex
  parses post-exec, Gemini does neither).
- ``liveness_signal_paths`` is NEW in v1 — enables file-mtime stall detection
  as a fallback when stdout is redirected to ``-o <file>`` or otherwise
  buffered, complementing the runner's primary stdout streaming watchdog.

Issue: #1184
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..result import ParseResult


@dataclass(frozen=True)
class InvocationPlan:
    """Everything needed to spawn one agent subprocess.

    Returned by ``adapter.build_invocation()``. The runner consumes it and
    passes the fields to ``subprocess.Popen``.

    Fields:
        cmd: The argv list, ready for Popen. Includes all flags, model
            overrides, output redirection, etc. First element is the binary
            name (e.g. ``"codex"``, ``"npx"``, ``"gemini"``).
        cwd: Working directory the runner will set on Popen. Adapters must
            stamp this with the ``cwd`` they received in ``build_invocation``
            so that later protocol methods — particularly
            ``liveness_signal_paths(plan)`` — can derive cwd-dependent paths
            (e.g. Gemini's ``~/.gemini/tmp/<basename>/``) without reading
            the ambient process cwd via ``os.getcwd()``. Added 2026-04-10
            to remove the hack that coupled adapters to process state.
        stdin_payload: Text to pipe to the subprocess's stdin. Empty string
            if the prompt is embedded in ``cmd`` instead.
        output_file: Path where the subprocess will write its final output,
            if any. Adapters that use ``codex exec -o <file>`` or
            ``gemini --output-path <file>`` populate this; the runner reads
            it on completion. None if output goes to stdout.
        env_overrides: Env vars to add to or remove from the subprocess
            environment. Merged onto a sanitized environment snapshot fresh
            per invocation. Set a value to ``None`` to remove that variable
            for this child only (e.g. strip Gemini API keys so the CLI falls
            through to OAuth). Values set here leak nowhere else.
        liveness_paths: Files whose mtime indicates the agent is alive.
            Used by the runner's stall detector as a fallback when stdout
            is buffered/redirected. Can be empty; if so, only stdout
            streaming is used for liveness.
    """
    cmd: list[str]
    cwd: Path
    stdin_payload: str = ""
    output_file: Path | None = None
    env_overrides: dict[str, str | None] = field(default_factory=dict)
    liveness_paths: tuple[Path, ...] = ()


@runtime_checkable
class AgentAdapter(Protocol):
    """Protocol every agent adapter must implement.

    Adapters are stateless — instance methods, no self-mutation between calls.
    The runner instantiates an adapter once per process and reuses it across
    ``invoke()`` calls.

    Class attributes (MUST be defined at class level, not on instances):
        name: Registry key. Matches the key in ``registry.AGENTS``. Examples:
            ``"codex"``, ``"claude"``, ``"gemini"``, ``"qwen"``.
        default_model: Model string passed to the CLI when the caller
            doesn't specify one. Example: ``"gpt-5.4"`` for Codex.
        supported_modes: Subset of ``{"read-only", "workspace-write", "danger"}``.
            The runner rejects invocations requesting a mode not in this set.

    Optional class attribute (probed by the runner via ``getattr``, so adapters
    that don't need it may omit it entirely):

        require_file_change_on_write: If ``True``, the runner treats a
            write-mode invocation (``mode in {"workspace-write", "danger"}``)
            that parses ``ok`` but leaves the worktree byte-identical (git HEAD
            unchanged AND ``git status --porcelain -uall`` identical before/after)
            as a failure (``outcome="error"``, ``Result.ok=False``) rather than a
            silent false-success. Set on adapters whose CLI can exit 0 having
            written nothing — e.g. AgyAdapter, for the intermittent headless
            no-write flake (#2099). Defaults to ``False`` when unset.

            Write-class intent assumed: the flag means "a write-mode run is
            EXPECTED to change the worktree." It is safe because callers route
            read-class tasks (review/search) to ``read-only`` — where the guard
            never runs. Do NOT pass a read-class prompt through
            ``runner.invoke(mode="danger")`` on a flagged adapter: a review that
            legitimately writes nothing would false-fire as a no-write error.
    """
    name: str
    default_model: str
    supported_modes: frozenset[str]

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
        """Build the full InvocationPlan for spawning this agent.

        Args:
            prompt: The prompt text to send.
            mode: One of the adapter's supported_modes.
            cwd: Working directory for the subprocess. Mandatory for write
                modes; runner validates this before calling.
            model: Model override, or None to use self.default_model.
            task_id: Optional task identifier for session tracking / logging.
            session_id: Session to resume, if the adapter's resume_policy
                allows it. Adapters with resume_policy="never" (Codex)
                MUST defensively ignore this even if passed.
            tool_config: Adapter-specific tool configuration. For Claude and
                Gemini this carries MCP server names and allowed tools.
                Structure is adapter-defined; keys the adapter doesn't
                understand are silently ignored.

        Returns:
            InvocationPlan ready for subprocess.Popen.

        Raises:
            ValueError: If ``mode`` is not in self.supported_modes, or
                required inputs for this mode are missing (e.g. cwd
                for workspace-write).
        """
        ...

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
        """Interpret raw subprocess output into a ParseResult.

        Adapters own all CLI-specific output parsing: which file has the
        final message, how to detect rate-limiting from stderr patterns,
        whether the CLI emits a parseable session ID, etc.

        Args:
            stdout: Captured stdout from the subprocess.
            stderr: Captured stderr from the subprocess.
            returncode: Subprocess exit code (may be None if killed).
            output_file: The path the adapter set in its InvocationPlan,
                or None. The runner passes it back unchanged; the adapter
                reads it if it's the canonical output location.
            plan: The full InvocationPlan the runner used to spawn the
                subprocess. Adapters that need to recover work from
                out-of-band locations (e.g. Gemini's session file at
                ``~/.gemini/tmp/<project>/chats/``) read `plan.cwd` to
                derive those paths. Added 2026-04-10 so the Gemini
                adapter can recover responses from the session file
                when stdout is empty or the CLI was killed mid-flush.
            call_start_time: Monotonic timestamp of when the subprocess
                was spawned. Used by adapters that need to distinguish
                "this call's output" from stale files on disk. None if
                the runner doesn't track it.

        Returns:
            ParseResult with ok, response, stderr_excerpt, rate_limited,
            session_id, and tokens fields.
        """
        ...

    # --- OPTIONAL method (not part of the structural Protocol) ---
    #
    # Adapters MAY implement ``check_early_reap(plan, call_start_time)
    # -> bool``. If present, the runner calls it periodically in its
    # poll loop. A True return value means "the response is on disk,
    # kill the subprocess NOW". The readiness signal must belong to that
    # exact invocation. Codex disables early reap because shared rollout
    # files do not establish ownership across resume and child agents.
    #
    # Not declared on the Protocol because structural typing would
    # then require EVERY adapter to implement it, including the ones
    # that don't need early reaping (Gemini, Claude). The runner
    # uses getattr() to probe for the method at call time.
    #
    # Signature if implemented::
    #
    #     def check_early_reap(
    #         self,
    #         plan: InvocationPlan,
    #         *,
    #         call_start_time: float | None = None,
    #     ) -> bool: ...

    def liveness_signal_paths(
        self,
        plan: InvocationPlan,
    ) -> tuple[Path, ...]:
        """Return paths the runner should poll for activity (mtime bumps).

        Called once after ``build_invocation`` returns. The returned paths
        are polled by the runner's stall watchdog every ~5s; any mtime
        bump is treated as "agent is alive" and resets the stall clock.

        Typical implementations:

        - Codex: return the ``-o <file>`` path + ``~/.codex/logs_1.sqlite``.
        - Gemini: return the active ``~/.gemini/tmp/<proj>/chats/<session>.json``.
        - Claude: return the active ``~/.claude/projects/.../<session>.jsonl``.
        - Qwen (hermes): return ().

        Args:
            plan: The InvocationPlan returned by build_invocation(). Adapters
                may read its output_file or other fields.

        Returns:
            A tuple of Path objects. Returning an empty tuple means
            "stall detection uses only stdout streaming for this adapter."
            Cap at ~5 paths for polling overhead reasons.
        """
        ...
