"""Result dataclasses for the agent runtime.

Two dataclasses:

- ``ParseResult`` — returned by adapter.parse_response(). Rich typed
  result that replaces v0's separate protocol methods (detect_rate_limit,
  extract_session_id). One method returns one object; cleaner shape.
- ``Result`` — returned by runner.invoke() to callers. Carries everything
  a caller might want: response text, timing, session ID, error excerpt,
  outcome classification, and the full usage record written to disk.

Both are frozen dataclasses. Frozen = hashable, immutable, mypy-strict clean.

Issue: #1184
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParseResult:
    """Adapter's interpretation of the raw subprocess output.

    Adapters return this from ``parse_response(stdout, stderr, returncode, output_file)``.
    The runner consumes it, writes a usage record, and builds the caller-facing Result.

    Fields:
        ok: True iff the adapter considers the invocation successful.
            An adapter may return ok=True with returncode != 0 if the CLI
            writes useful output despite a non-zero exit (rare but allowed).
        response: Clean text output, ready to forward to the caller.
            Empty string on failure.
        stderr_excerpt: First ~500 chars of stderr (or the output file's
            contents on error) for debugging. None if no diagnostic output.
        rate_limited: True iff the adapter's rate-limit pattern matched
            stderr or output_file contents. Drives runner's RateLimitedError.
        session_id: Provider session ID parsed from trusted CLI metadata, if it
            exposes one. Claude and Codex do; Gemini doesn't. None otherwise.
        tokens: Prompt+completion token count if the CLI reports it. We
            deliberately leave this None when the CLI doesn't expose tokens,
            rather than invent numbers. Populated opportunistically.
    """
    ok: bool
    response: str
    stderr_excerpt: str | None = None
    rate_limited: bool = False
    session_id: str | None = None
    tokens: int | None = None


@dataclass(frozen=True)
class Result:
    """Caller-facing result from runner.invoke().

    Contains everything a caller might need, including the raw usage_record
    dict that was written to batch_state/api_usage/. Callers that want to
    make retry or backoff decisions can inspect ``rate_limited``, ``stalled``,
    and ``returncode`` directly.

    Fields:
        ok: True iff the invocation succeeded end-to-end (no exceptions,
            no stall, no hard timeout, adapter.parse_response returned ok).
        agent: Registry name of the agent that served this call.
        model: Actual model used (adapter.default_model if none passed).
        mode: Sandbox mode requested ("read-only", "workspace-write", "danger").
        response: Clean text output (empty on failure).
        stderr_excerpt: Diagnostic stderr tail on failure, None on success.
        duration_s: Wall-clock time from spawn to return, in seconds.
        session_id: Provider session ID (Claude/Codex) or None.
        rate_limited: True iff the failure was provider rate limiting.
            Mutually exclusive with stalled and hard_timeout as failure modes.
        stalled: True iff the failure was stall detection firing.
            Distinguishes "agent went silent" from "agent hit wall clock."
        returncode: Subprocess exit code, or None if killed before exit.
        usage_record: The exact dict written to batch_state/api_usage/. Callers
            can log or aggregate this. Follows the schema in design doc § 4.5.
    """
    ok: bool
    agent: str
    model: str
    mode: str
    response: str
    stderr_excerpt: str | None
    duration_s: float
    session_id: str | None
    rate_limited: bool
    stalled: bool
    returncode: int | None
    stderr: str | None = None
    usage_record: dict[str, Any] = field(default_factory=dict)
