"""LLM dispatch — thin wrapper over ``lu_machinery.agent_runtime`` with round-robin.

Contract:

* :func:`dispatch` is a single call site for Codex / Claude / Gemini (via AGY).
* :func:`writer_for_index` assigns writer + reviewer by **permanent**
  module index so the assignment is stable across re-bootstraps and
  SIGKILL-recovery.
* :class:`DispatcherUnavailable` is raised when Claude's peak-hours
  guard / budget / rate-limit refuses the call. Callers keep the
  module in a retryable stage (not ``FAILED``) because the LLM is
  temporarily off, not the module.

Delegates to :func:`lu_machinery.agent_runtime.runner.invoke` directly so each
call uses the installed ``lu-machinery`` runtime and inherits its budget,
watchdog, and rate-limit handling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lu_machinery.agent_runtime.errors import (
    AgentRuntimeError,
    AgentTimeoutError,
    AgentUnavailableError,
    RateLimitedError,
)
from lu_machinery.agent_runtime.runner import invoke

from .worktree import primary_checkout_root

_REPO_ROOT = primary_checkout_root(Path(__file__).resolve().parents[2])

# "agy" is the Google lane (Antigravity) that replaced the retired gemini-cli
# (#2125). "gemini" is retained as a still-accepted agent string for the legacy
# dispatch path / opt-in callers; no default routes to it (see tiebreaker_agent).
Agent = Literal["codex", "claude", "agy", "gemini"]

VALID_AGENTS: frozenset[str] = frozenset({"codex", "claude", "agy", "gemini"})

# Timeouts by role, not agent. The citation-verify path is per-URL so
# it gets a short timeout; writer/reviewer dispatches are per-module so
# they get a long one. Callers that need different values pass explicit
# ``timeout=`` kwargs.
DEFAULT_TIMEOUTS: dict[str, int] = {
    "write": 900,
    "review": 900,
    "citation_verify": 60,
}


class DispatcherUnavailable(RuntimeError):
    """Dispatcher refused a call due to peak-hours / budget / rate-limit.

    Callers must distinguish this from a real failure: the module should
    stay in a retryable stage rather than advancing to ``FAILED``. A
    bulk run that crossed Claude peak hours (14:00–20:00 weekdays)
    without this signal would silently drain modules from the queue.
    """


@dataclass(frozen=True)
class DispatchResult:
    """Structured dispatch return — replaces the older ``tuple[bool, str]`` shape."""

    ok: bool
    stdout: str
    stderr: str
    returncode: int
    duration_sec: float
    agent: str
    model: str | None


# Stderr fragments that indicate a temporary "dispatcher off" condition
# rather than a real failure. Kept in sync with ``citation_backfill``'s
# list. Substring-and-case-insensitive match so small wording changes in
# ``dispatch.py`` don't silently reclassify unavailability as failure.
_UNAVAILABLE_MARKERS = (
    "peak hours in effect",
    "claude peak hours",
    "call budget",
    "claude budget",
    "claude unavailable",
    "claudeunavailableerror",
    "rate_limit",
    "rate limited",
)


def _looks_unavailable(text: str) -> bool:
    s = (text or "").lower()
    return any(m in s for m in _UNAVAILABLE_MARKERS)


def dispatch(
    agent: Agent,
    prompt: str,
    *,
    timeout: int,
    model: str | None = None,
    cwd: Path | None = None,
    tools_disabled: bool = False,
) -> DispatchResult:
    """Invoke ``agent`` through :func:`lu_machinery.agent_runtime.runner.invoke`.

    ``cwd`` defaults to the primary checkout. Pass the worktree path when
    dispatching a writer — Codex's file operations anchor to cwd.

    Every call runs in ``read-only`` mode. Codex enforces that with its
    read-only sandbox; AGY gets the release's bounded read-only route when
    the call passes no ``tool_config`` (lu-machinery >= 0.1.64), and a
    partial hand-built config is refused there. Claude's read-only mode still
    honours allow rules from checkout settings, so ``tools_disabled=True``
    (text-only writer/reviewer output) asks the runtime for its read-only
    tool set (``--tools Read,Grep,Glob,LS``): no edit, write or shell tool
    exists in that run. Legacy ``"gemini"`` callers route through the
    ``"agy"`` adapter while preserving ``agent="gemini"`` on the returned
    :class:`DispatchResult`.

    Raises :class:`DispatcherUnavailable` when the runtime signals a
    temporary refusal (rate limit, budget, peak hours, unavailable).
    Returns :class:`DispatchResult` with ``ok=False`` for genuine failures
    (crashes, timeouts, non-zero exits without availability markers).
    """
    if agent not in VALID_AGENTS:
        raise ValueError(f"unknown agent {agent!r}; expected one of {sorted(VALID_AGENTS)}")

    runtime_agent = "agy" if agent == "gemini" else agent
    tool_config: dict[str, bool] | None = None
    if runtime_agent == "claude" and tools_disabled:
        tool_config = {"discussion_readonly": True}

    t0 = time.monotonic()
    try:
        res = invoke(
            runtime_agent,
            prompt,
            mode="read-only",
            cwd=cwd or _REPO_ROOT,
            model=model,
            entrypoint="quality_pipeline",
            hard_timeout=timeout,
            tool_config=tool_config,
        )
    except AgentTimeoutError:
        return DispatchResult(
            ok=False,
            stdout="",
            stderr=f"dispatch_timeout_after_{timeout}s",
            returncode=-1,
            duration_sec=time.monotonic() - t0,
            agent=agent,
            model=model,
        )
    except (RateLimitedError, AgentUnavailableError) as exc:
        raise DispatcherUnavailable(f"{agent} refused the call: {str(exc)[:400]}") from exc
    except AgentRuntimeError as exc:
        return DispatchResult(
            ok=False,
            stdout="",
            stderr=f"dispatch_runtime_error: {str(exc)[:400]}",
            returncode=-1,
            duration_sec=time.monotonic() - t0,
            agent=agent,
            model=model,
        )

    stdout = res.response or ""
    stderr = res.stderr_excerpt or ""
    duration = time.monotonic() - t0

    if not res.ok and _looks_unavailable(stderr + "\n" + stdout):
        raise DispatcherUnavailable(
            f"{agent} refused the call: {(stderr or stdout).strip()[:400]}"
        )

    rc = 0 if res.ok else (res.returncode if res.returncode is not None else 1)
    return DispatchResult(
        ok=res.ok,
        stdout=stdout,
        stderr=stderr,
        returncode=rc,
        duration_sec=duration,
        agent=agent,
        model=res.model or model,
    )


def writer_for_index(module_index: int) -> tuple[Agent, Agent]:
    """Return ``(writer, reviewer)`` — codex writes, claude reviews.

    The earlier even/odd alternation was abandoned 2026-04-25 after
    empirical evidence that claude-as-writer lands ~440-line modules
    (below the 600-line minimum in ``module-quality.md``) while codex
    consistently lands 1500–2000+ lines at rubric ≥4.0. Claude is
    redirected to coding/review tasks where it's strong. Cross-family
    review per ``docs/review-protocol.md`` is still satisfied because
    claude reviews codex (different model families).

    The ``module_index`` parameter is kept in the signature so callers
    don't break; it's no longer used to choose roles.

    Gemini is never a writer or reviewer here — it's reserved for the
    teaching audit (pre-pipeline) and citation verification (per-URL)
    and as tiebreaker after 2 retries (via :func:`tiebreaker_agent`).
    """
    del module_index
    return ("codex", "claude")


def tiebreaker_agent() -> Agent:
    """Agent invoked when Codex↔Claude retry loop hits the cap.

    The agy (Antigravity) Google lane is the third party — outside the
    codex/claude writer/reviewer rotation, so its verdict is structurally
    independent (replaces the retired gemini-cli, #2125). The tiebreaker is
    dispatched via ``dispatch(reviewer, ...)`` in stages.py WITHOUT an explicit
    model, so it resolves to the lu-machinery release's default AGY model.
    To pin a review model here the tiebreaker dispatch would pass ``model=``.
    """
    return "agy"
