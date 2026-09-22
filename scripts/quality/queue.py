"""Queue with writer stickiness for site-wide quality rewrite (v5).

Sits on top of :mod:`state` — adds a ``queue`` sub-document to each module's
state file. Stickiness rule:

* When the assigned writer hits a transient error (rate limit, auth, 5xx),
  the queue marks the module ``blocked`` with exponential backoff and
  retries the **same** writer later. **Never** falls back to the other
  writer family on transient errors — cross-writer fallback would defeat
  the site-wide style consistency goal.
* Only after ``MAX_PRIMARY_ATTEMPTS`` (5) failed attempts does the queue
  escalate to the tertiary writer (Claude). Tertiary is intentionally
  expensive and rare — it should only fire when the primary writer is
  genuinely incapable on this module, not when the API was flaky.

The queue does NOT subsume the v2 quality stage machine. v2 stages
(``UNAUDITED`` → … → ``COMMITTED``) still drive the rewrite step by step;
the queue layer chooses *which writer* to dispatch and *when* to retry.
"""
from __future__ import annotations

import calendar
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import state as _state
from .state import (
    load_state,
    now_iso,
    save_state,
    state_lease,
)

# --- Routing rule -----------------------------------------------------------
#
# Frontmatter ``complexity`` tag wins. Otherwise track-based fallback. If
# neither resolves, default to tertiary so a human picks instead of silently
# routing to whichever the order ended up.

# Primary writer is now the agy (Antigravity) Google lane, model
# gemini-3.1-pro-high — gemini-cli is retired (#2125). The model id is an agy
# display slug, dispatched via the `agy` subcommand in scripts/dispatch.py.
PRIMARY_BEGINNER = "gemini-3.1-pro-high"
PRIMARY_ADVANCED = "gemini-3.1-pro-high"
TERTIARY = "claude-opus-5-5"

# Map writer-model identifiers (returned by route_writer / stored in the
# queue doc) onto the (agent, model) tuple that ``dispatchers.dispatch``
# expects. Kept here, not in dispatchers.py, so the queue owns the
# vocabulary. Adding a writer means adding an entry here AND a
# corresponding case in scripts/dispatch.py.
_MODEL_TO_AGENT: dict[str, tuple[str, str]] = {
    PRIMARY_BEGINNER: ("agy", PRIMARY_BEGINNER),
    TERTIARY: ("claude", TERTIARY),
    # Queue rows recorded before Opus 5.5 became the default still resolve.
    "claude-opus-4-8": ("claude", TERTIARY),
}


def model_to_agent(model: str) -> tuple[str, str]:
    """Translate a queue writer-model id to a ``(agent, model)`` dispatch tuple.

    Raises ``ValueError`` on an unknown model — callers must not silently
    swap an unknown model for a default. The whole point of stickiness is
    that the queue's writer choice survives unchanged through retries.
    """
    if model not in _MODEL_TO_AGENT:
        raise ValueError(f"unknown writer model: {model!r} (known: {sorted(_MODEL_TO_AGENT)})")
    return _MODEL_TO_AGENT[model]

BEGINNER_TRACKS = (
    "ai/foundations",
    "ai/open-models-local-inference",
)
ADVANCED_TRACKS = (
    "platform/disciplines/data-ai",
    "on-premises/ai-ml-infrastructure",
    "platform/toolkits/data-ai-platforms",
    "ai-ml-engineering",
    "platform/disciplines",
    "platform/toolkits",
    "k8s",
    "linux",
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_COMPLEXITY_RE = re.compile(r"complexity\s*[:=]\s*[`'\"]?\[?(\w+)\]?", re.IGNORECASE)
_REVISION_LINE_RE = re.compile(r"^revision_pending\s*:.*\n", re.MULTILINE)
_QA_LINE_RE = re.compile(r"^qa_pending\s*:.*\n", re.MULTILINE)
_CITATIONS_VERIFIED_LINE_RE = re.compile(r"^citations_verified\s*:.*\n?", re.MULTILINE)


def _read_complexity(module_path: Path) -> str | None:
    """Return frontmatter complexity tag (lowercased) or None.

    Looks at structured frontmatter first, then a freeform ``Complexity:``
    blockquote/heading line in the first 30 lines (the convention varies
    across older vs newer modules).
    """
    text = module_path.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if fm:
        m = _COMPLEXITY_RE.search(fm.group(1))
        if m:
            return m.group(1).lower()
    head = "\n".join(text.splitlines()[:30])
    m = _COMPLEXITY_RE.search(head)
    if m:
        return m.group(1).lower()
    return None


def _beginner_writer() -> str:
    """Resolve the beginner-track writer, honouring a runtime degraded
    fallback.
    """
    fallback = os.environ.get("KUBEDOJO_BEGINNER_FALLBACK", "").lower().strip()
    if fallback in {"claude", "claude-opus", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5-5"}:
        return TERTIARY
    return PRIMARY_BEGINNER


def _tertiary_writer() -> str:
    """Resolve the tertiary writer, honouring a runtime degraded fallback.
    """
    fallback = os.environ.get("KUBEDOJO_TERTIARY_FALLBACK", "").lower().strip()
    if fallback in {"gemini", "agy", "gemini-3.1-pro-preview", "gemini-3.1-pro-high"}:
        return PRIMARY_BEGINNER
    return TERTIARY


def route_writer(module_path: Path) -> str:
    """Return the assigned writer for a module per the routing rule.

    Frontmatter complexity tag wins (``[QUICK]`` / ``[COMPLEX]`` etc.). If
    absent, falls back to track-based heuristics. If neither classifies the
    module, returns the tertiary writer so a human review will catch it.
    """
    complexity = _read_complexity(module_path)
    if complexity in {"quick", "beginner", "easy", "intro"}:
        return _beginner_writer()
    if complexity in {"complex", "advanced", "deep"}:
        return PRIMARY_ADVANCED

    # Resolve CONTENT_ROOT dynamically so test monkeypatches on
    # ``state.CONTENT_ROOT`` reach this caller.
    rel = module_path.resolve().relative_to(_state.CONTENT_ROOT).as_posix()
    section = "/".join(rel.split("/")[:2])
    for t in BEGINNER_TRACKS:
        if section.startswith(t):
            return _beginner_writer()
    for t in ADVANCED_TRACKS:
        if section.startswith(t):
            return PRIMARY_ADVANCED
    return _tertiary_writer()


# --- Backoff schedule -------------------------------------------------------
#
# Exponential, intentionally slow. The user is OK waiting hours for a flaky
# writer to recover — that's better than burning the cross-writer fallback.

BACKOFF_SECONDS = (
    5 * 60,        # 1st transient failure → 5 min
    30 * 60,       # 2nd → 30 min
    2 * 3600,      # 3rd → 2 hr
    8 * 3600,      # 4th → 8 hr
    24 * 3600,     # 5th → 24 hr (then escalate on next failure)
)
MAX_PRIMARY_ATTEMPTS = len(BACKOFF_SECONDS)


# --- Queue sub-document schema ----------------------------------------------


def new_queue_doc(assigned_writer: str) -> dict[str, Any]:
    return {
        "assigned_writer": assigned_writer,
        "writer_attempts": 0,
        "total_attempts": 0,
        "escalation_level": 0,           # 0=primary, 1=tertiary
        "blocked_until": None,           # ISO timestamp or None
        "last_block_reason": None,
        "revision_pending": True,        # banner to learners
        "queued_at": now_iso(),
        "completed_at": None,
    }


# --- High-level operations (each holds a state.lease internally) ------------


@dataclass(frozen=True)
class ClaimResult:
    """Returned by :func:`claim`. Tells the caller what writer to use, or why not."""
    writer: str | None
    blocked_until: str | None
    reason: str | None  # human-readable when writer is None


def ensure_queued(
    slug: str,
    module_path: Path,
    *,
    set_banner: bool = True,
) -> dict[str, Any]:
    """Idempotently attach a queue doc to a module's state.

    Routes the writer per :func:`route_writer` if no queue doc exists yet,
    or returns the existing one (writer assignment is sticky across calls).

    When ``set_banner=True`` (the default — used by the ``triage --apply``
    CLI subcommand), also sets ``revision_pending: true`` on the module's
    frontmatter so the Starlight banner renders for learners during the
    queue lifetime. The pipeline's :mod:`stages.route_one` passes
    ``set_banner=False`` because banner placement is a one-shot triage
    decision committed in its own PR — mutating frontmatter inside
    ``route_one`` would dirty the primary checkout and break
    ``merge_one``'s pre-flight check.
    """
    with state_lease(slug):
        state = load_state(slug)
        if state is None:
            raise FileNotFoundError(f"state for {slug!r} missing — run pipeline bootstrap first")
        if "queue" not in state:
            state["queue"] = new_queue_doc(route_writer(module_path))
            save_state(state)
        if set_banner:
            # Frontmatter mutation lives outside the JSON state but is tied
            # to it. Idempotent — no-op if already set.
            set_revision_pending_frontmatter(module_path)
        return state["queue"]


def claim(slug: str, *, now: float | None = None) -> ClaimResult:
    """Try to claim this module for processing.

    Returns the writer to use, or None with a reason if the queue says
    we should wait. Does NOT change state — call :func:`record_attempt_start`
    once the dispatch actually launches.
    """
    state = load_state(slug)
    if state is None or "queue" not in state:
        return ClaimResult(writer=None, blocked_until=None, reason="not queued")
    q = state["queue"]
    if q.get("completed_at"):
        return ClaimResult(writer=None, blocked_until=None, reason="already completed")
    blocked = q.get("blocked_until")
    if blocked:
        cur = now if now is not None else time.time()
        if _iso_to_epoch(blocked) > cur:
            return ClaimResult(writer=None, blocked_until=blocked, reason=f"blocked until {blocked}")
    return ClaimResult(writer=q["assigned_writer"], blocked_until=None, reason=None)


def _record_attempt_start_in_state(st: dict[str, Any]) -> None:
    """Mutate the queue subdoc of ``st`` in place; caller saves.

    Codex round-2 must #1: the previous lease-less helper loaded and
    saved its own copy of state, then the caller's later
    ``state.transition(st, ...)`` would save behind it with the older
    in-memory ``st`` — losing every queue mutation. Mutating ``st``
    directly so the caller's eventual ``save_state(st)`` (typically via
    ``state.transition``) carries the queue updates forward.
    """
    q = st.get("queue") if isinstance(st, dict) else None
    if not q:
        raise FileNotFoundError(f"queue for {st.get('slug') if st else '<unknown>'!r} missing")
    q["writer_attempts"] = int(q.get("writer_attempts", 0)) + 1
    q["total_attempts"] = int(q.get("total_attempts", 0)) + 1
    q["blocked_until"] = None  # we're attempting now


def record_attempt_start(slug: str) -> None:
    """Increment attempt counters. Call right before launching the writer dispatch."""
    with state_lease(slug):
        st = load_state(slug)
        if st is None or "queue" not in st:
            raise FileNotFoundError(f"queue for {slug!r} missing")
        _record_attempt_start_in_state(st)
        save_state(st)


def _record_block_in_state(st: dict[str, Any], reason: str) -> str:
    """Mutate the queue subdoc of ``st`` in place; caller saves.

    Same lifecycle contract as :func:`_record_attempt_start_in_state` —
    the caller already holds the lease and will save ``st`` either by
    ``save_state`` directly or by an enclosing ``state.transition``.
    Returns the new ``blocked_until`` timestamp or ``"ESCALATED"``.
    """
    q = st.get("queue") if isinstance(st, dict) else None
    if not q:
        raise FileNotFoundError(f"queue for {st.get('slug') if st else '<unknown>'!r} missing")
    attempts = int(q.get("writer_attempts", 0))
    if attempts >= MAX_PRIMARY_ATTEMPTS and q.get("escalation_level", 0) == 0:
        q["escalation_level"] = 1
        q["assigned_writer"] = TERTIARY
        q["writer_attempts"] = 0
        q["blocked_until"] = None
        q["last_block_reason"] = f"escalated after {attempts} primary attempts: {reason}"
        return "ESCALATED"
    idx = min(attempts - 1, len(BACKOFF_SECONDS) - 1)
    delay = BACKOFF_SECONDS[max(idx, 0)]
    until_epoch = time.time() + delay
    until_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(until_epoch))
    q["blocked_until"] = until_iso
    q["last_block_reason"] = reason
    return until_iso


def record_block(slug: str, reason: str) -> str:
    """Mark the module blocked (transient writer error) with backoff.

    Backoff index uses the writer's per-writer attempts; if we've used up
    the schedule, escalate to tertiary instead. Returns the new blocked_until
    timestamp (or "ESCALATED" if we tipped over).
    """
    with state_lease(slug):
        st = load_state(slug)
        if st is None or "queue" not in st:
            raise FileNotFoundError(f"queue for {slug!r} missing")
        outcome = _record_block_in_state(st, reason)
        save_state(st)
        return outcome


def record_completion(slug: str, module_path: Path | None = None) -> None:
    """Mark the queue entry done AND remove the banner from frontmatter.

    Pass ``module_path`` so the frontmatter can be cleared. If omitted, the
    state is updated but the banner stays — caller is responsible for the
    banner cleanup later (e.g. a separate batch script).
    """
    with state_lease(slug):
        state = load_state(slug)
        if state is None or "queue" not in state:
            raise FileNotFoundError(f"queue for {slug!r} missing")
        q = state["queue"]
        q["completed_at"] = now_iso()
        q["revision_pending"] = False
        q["blocked_until"] = None
        save_state(state)
    if module_path is not None:
        clear_revision_pending_frontmatter(module_path)


# --- Helpers ----------------------------------------------------------------


def _iso_to_epoch(iso: str) -> float:
    """Decode a ``YYYY-MM-DDTHH:MM:SSZ`` UTC ISO string to a UNIX epoch.

    Must use ``calendar.timegm`` (UTC-aware) and NOT ``time.mktime``
    (local-timezone). The string is produced via
    ``time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))`` which
    is UTC; round-tripping through ``time.mktime`` would shift the
    epoch by the local timezone offset, causing blocks to "expire"
    early on +UTC machines and persist past schedule on -UTC machines.
    """
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))


def set_revision_pending_frontmatter(module_path: Path) -> bool:
    """Add ``revision_pending: true`` to a module's frontmatter (idempotent).

    Inserted just after the opening ``---`` so the banner state is the first
    thing a reviewer sees in git diffs. Returns True if the file changed.
    """
    text = module_path.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        # No frontmatter — refuse silently rather than guess where to inject.
        return False
    if _REVISION_LINE_RE.search(fm.group(0)):
        return False  # already set
    new_fm = fm.group(0).replace("---\n", "---\nrevision_pending: true\n", 1)
    new_text = new_fm + text[fm.end():]
    module_path.write_text(new_text, encoding="utf-8")
    return True


def clear_revision_pending_frontmatter(module_path: Path) -> bool:
    """Remove the ``revision_pending`` line from a module's frontmatter."""
    text = module_path.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return False
    new_fm = _REVISION_LINE_RE.sub("", fm.group(0), count=1)
    if new_fm == fm.group(0):
        return False  # nothing to remove
    new_text = new_fm + text[fm.end():]
    module_path.write_text(new_text, encoding="utf-8")
    return True


def set_qa_pending_frontmatter(module_path: Path) -> bool:
    """Add ``qa_pending: true`` to a module's frontmatter (idempotent).

    Set when a rewrite landed under KUBEDOJO_SKIP_REVIEW — the writer
    gates passed but the LLM cross-family review was deferred. Cleared by
    :mod:`scripts.quality_post_review` once a real reviewer approves; on
    CHANGES the module flips back to ``revision_pending``.
    """
    text = module_path.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return False
    if _QA_LINE_RE.search(fm.group(0)):
        return False  # already set
    new_fm = fm.group(0).replace("---\n", "---\nqa_pending: true\n", 1)
    new_text = new_fm + text[fm.end():]
    module_path.write_text(new_text, encoding="utf-8")
    return True


def set_citations_verified_frontmatter(module_path: Path, verified: bool = True) -> None:
    """Set or remove the citations_verified field on a module's frontmatter.

    Args:
        module_path: absolute path to the .md module file.
        verified: if True, sets ``citations_verified: true``.
            If False, removes the key entirely (absent = not verified).

    ``_backfill_one`` does not establish claim/source verification:

    * inject success or nothing_to_do → verified=False (remove inherited key)
    * inject failure → not called (the caller restores partial file changes)

    Setting the key to True requires independent source evidence; this helper
    only mutates frontmatter and does not validate that evidence.
    """
    text = module_path.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return
    fm_text = fm.group(0)
    if verified:
        if _CITATIONS_VERIFIED_LINE_RE.search(fm_text):
            new_fm = _CITATIONS_VERIFIED_LINE_RE.sub(
                "citations_verified: true\n", fm_text, count=1
            )
        else:
            new_fm = fm_text.replace("---\n", "---\ncitations_verified: true\n", 1)
    else:
        new_fm = _CITATIONS_VERIFIED_LINE_RE.sub("", fm_text, count=1)
    if new_fm == fm_text:
        return
    module_path.write_text(new_fm + text[fm.end():], encoding="utf-8")


def clear_qa_pending_frontmatter(module_path: Path) -> bool:
    """Remove the ``qa_pending`` line from a module's frontmatter."""
    text = module_path.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return False
    new_fm = _QA_LINE_RE.sub("", fm.group(0), count=1)
    if new_fm == fm.group(0):
        return False
    new_text = new_fm + text[fm.end():]
    module_path.write_text(new_text, encoding="utf-8")
    return True


def queue_summary() -> dict[str, Any]:
    """Aggregate counts for ``status`` display. No lease — read-only snapshot."""
    from .state import iter_state_slugs

    by_writer: dict[str, dict[str, int]] = {}
    by_status: dict[str, int] = {"queued": 0, "blocked": 0, "completed": 0, "escalated": 0}
    total = 0
    for slug in iter_state_slugs():
        state = load_state(slug)
        if state is None or "queue" not in state:
            continue
        q = state["queue"]
        total += 1
        w = q.get("assigned_writer", "unknown")
        d = by_writer.setdefault(w, {"queued": 0, "blocked": 0, "completed": 0})
        if q.get("completed_at"):
            d["completed"] += 1
            by_status["completed"] += 1
        elif q.get("blocked_until"):
            d["blocked"] += 1
            by_status["blocked"] += 1
        else:
            d["queued"] += 1
            by_status["queued"] += 1
        if q.get("escalation_level", 0) > 0:
            by_status["escalated"] += 1
    return {"total": total, "by_writer": by_writer, "by_status": by_status}


__all__ = [
    "BACKOFF_SECONDS",
    "MAX_PRIMARY_ATTEMPTS",
    "PRIMARY_ADVANCED",
    "PRIMARY_BEGINNER",
    "TERTIARY",
    "ClaimResult",
    "claim",
    "clear_qa_pending_frontmatter",
    "clear_revision_pending_frontmatter",
    "ensure_queued",
    "model_to_agent",
    "queue_summary",
    "record_attempt_start",
    "record_block",
    "record_completion",
    "route_writer",
    "set_citations_verified_frontmatter",
    "set_qa_pending_frontmatter",
    "set_revision_pending_frontmatter",
]
