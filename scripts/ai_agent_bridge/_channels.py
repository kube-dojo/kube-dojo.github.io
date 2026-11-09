"""Channel bridge — Phase B.1 (#1190).

This module provides the storage-layer primitives for the channel-based
agent bridge. It is INTENTIONALLY decoupled from the legacy 1:1 message
bus in ``_messaging.py`` — both subsystems share the same SQLite DB
(``_db.py``) but operate on disjoint tables, so ``ab ask-claude`` keeps
working throughout the migration.

See issue #1190 for the design rationale and acceptance criteria.

## Key design choices (post-Gemini critique)

- **Three tables, not one.** ``channels`` holds static topic metadata;
  ``channel_messages`` holds immutable prose (posts and replies, both
  linked by ``parent_id``); ``deliveries`` is an outbound state machine
  (pending → dispatched → delivered → failed) per (message, recipient).
  Replies are NEW ``channel_messages`` rows with ``parent_id`` pointing
  at the original — they do NOT update the delivery row.

- **BEGIN IMMEDIATE for fanout inserts.** Writing 1 message + N delivery
  rows needs a write lock upfront to avoid SQLITE_BUSY under concurrency.
  ``busy_timeout=5000`` then queues concurrent writers gracefully.

- **Context snapshots are SHA256 hex, not counters.** Bumping a manual
  integer after every ``context.md`` edit invites human error. Hashing
  the file contents at post-time is automatic, deterministic, and
  survives git pulls across machines.

- **Monitor state is captured per message.** When we POST, we fetch
  ``GET /api/state/summary`` (Monitor API, see ``docs/MONITOR-API.md``)
  and store the JSON blob verbatim in ``monitor_state_snapshot``. This
  gives deterministic replay of the project state that the agent saw.

## Module API surface

The functions in this module are deliberately small and imperative.
They return plain dicts / lists of dicts, not ORM objects — the channel
bridge is a message log, not a domain model.

High-level:
    create_channel(name, *, description, include, subscribers)
    post(channel, from_agent, body, *, to_agents, parent_id, ...)
    read(channel, *, tail, thread_id)
    list_channels()
    get_channel(name)
    mark_delivery(delivery_id, status, *, error, delivered_at)
    context_sha256(path)
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_runtime.redact import redact_jsonable, redact_text

from ._config import REPO_ROOT
from ._db import get_db

# ── Constants ──────────────────────────────────────────────────────────

VALID_AGENTS = (
    "agy",
    "claude",
    "codex",
    "cursor",
    "deepseek",
    "gemini",
    "hermes",
    "opencode",
    "qwen",
    "user",
)
VALID_KINDS = ("post", "reply", "system", "fanout_start", "fanout_end")
VALID_DELIVERY_STATUSES = (
    "pending",
    "processing",
    "dispatched",
    "delivered",
    "failed",
)
VALID_DELIVERY_ERROR_KINDS = (
    "rate_limited",
    "timeout",
    "unavailable",
    "tool_error",
    "parse_error",
    "unknown",
)
DEFAULT_DELIVERY_LEASE_SECONDS = 600
DEFAULT_MAX_DELIVERY_ATTEMPTS = 3
DEFAULT_RATE_LIMIT_RETRY_SECONDS = 300

# Default channel that every other channel includes unless overridden.
# Holds project-wide pinned context that agents need on every message
# (coding conventions, current sprint summary, etc.).
SHARED_CHANNEL = "shared"

# ── B.2: Context injection + Monitor API fetch (#1190) ────────────────

# Root directory for channel context files. In-repo, git-tracked,
# reviewable — context drift becomes a first-class commit history.
# Each channel gets its own subdirectory: docs/agent-channels/{channel}/
CONTEXT_ROOT = Path(
    os.environ.get("AB_CONTEXT_DIR", str(REPO_ROOT / "docs" / "agent-channels"))
)
WAKE_ROOT = Path(
    os.environ.get("AB_WAKE_DIR", str(REPO_ROOT / ".agent" / "wake"))
)

# Monitor API endpoint for dynamic project state.
# See docs/MONITOR-API.md. Short timeout because the API is on the same
# machine — if it's not responding in 2 seconds, it's down, not slow.
# Default keeps the original learn-ukrainian URL so interactive `ab post`
# works without env setup. Projects without a Monitor API get a graceful
# 2-second timeout + None return (fetch_monitor_state already handles this).
# Override with AB_MONITOR_URL="" to disable explicitly.
MONITOR_API_URL = os.environ.get(
    "AB_MONITOR_URL", "http://localhost:8768/api/status/summary"
)
MONITOR_FETCH_TIMEOUT_S = 2.0

# Character budget for message history when building an agent prompt.
# Reused from _messaging.get_conversation_context() pattern — truncate
# by char count, not message count, so a single 400-line script doesn't
# blow up the budget. Pattern attributed to Gemini's B.1 design review.
DEFAULT_MAX_HISTORY_CHARS = 6000

# Hard ceiling on the assembled agent prompt. If the context chain +
# history + new body exceeds this, we drop history aggressively to fit.
# This exists so a deep include chain can't accidentally blow up one
# post to >50KB — the whole point of channels is to SAVE tokens.
DEFAULT_MAX_PROMPT_CHARS = 24000


# ── Helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    """Generate a new opaque ID for messages/deliveries/etc."""
    return uuid.uuid4().hex


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso_after(value: str, *, seconds: int) -> str:
    return (_parse_iso(value) + timedelta(seconds=seconds)).isoformat()


def context_sha256(path: Path) -> str:
    """Compute sha256 hex of a context.md file.

    Returns empty string if the file doesn't exist or is unreadable —
    we'd rather log an empty rev than block a post on a missing
    context file. The absence itself is meaningful signal during debug.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, FileNotFoundError):
        return ""


def _validate_agent(agent: str) -> None:
    if agent not in VALID_AGENTS:
        raise ValueError(
            f"Unknown agent '{agent}'. Expected one of {VALID_AGENTS}."
        )


def _validate_kind(kind: str) -> None:
    if kind not in VALID_KINDS:
        raise ValueError(
            f"Unknown kind '{kind}'. Expected one of {VALID_KINDS}."
        )


def _validate_error_kind(error_kind: str) -> None:
    if error_kind not in VALID_DELIVERY_ERROR_KINDS:
        raise ValueError(
            f"Unknown delivery error kind '{error_kind}'. "
            f"Expected one of {VALID_DELIVERY_ERROR_KINDS}."
        )


def _touch_wake_file(agent: str) -> None:
    """Best-effort wake hint for #1192 OS-level inbox watchers.

    The file is replaced atomically per recipient after the post
    transaction commits, so watchers never observe a partially-written
    wake file and a wake failure never rolls back the message insert.
    """
    try:
        WAKE_ROOT.mkdir(parents=True, exist_ok=True)
        wake_path = WAKE_ROOT / agent
        tmp_path = WAKE_ROOT / f".{agent}.{uuid.uuid4().hex}.tmp"
        tmp_path.write_text(_now_iso(), encoding="utf-8")
        tmp_path.replace(wake_path)
    except OSError:
        return


def _row_to_pending_delivery(row) -> dict[str, Any]:
    """Convert a joined delivery/message row to the queue payload shape."""
    return {
        "delivery_id": row["delivery_id"],
        "message_id": row["message_id"],
        "to_agent": row["to_agent"],
        "to_model": row["to_model"],
        "status": row["status"],
        "dispatched_at": row["dispatched_at"],
        "delivered_at": row["delivered_at"],
        "error": row["error"],
        "body": row["body"],
        "from_agent": row["cm_from_agent"],
        "channel": row["cm_channel"],
        "created_at": row["cm_created_at"],
    }


def _delivery_queue_row(
    conn,
    delivery_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT d.delivery_id, d.message_id, d.to_agent, d.to_model,
               d.status, d.dispatched_at, d.delivered_at, d.error,
               d.lease_until, d.attempt_count, d.retry_after, d.last_error_kind,
               cm.body, cm.from_agent AS cm_from_agent,
               cm.channel AS cm_channel, cm.created_at AS cm_created_at
        FROM deliveries d
        JOIN channel_messages cm ON cm.message_id = d.message_id
        WHERE d.delivery_id = ?
        """,
        (delivery_id,),
    ).fetchone()
    return _row_to_pending_delivery(row) if row else None


# ── B.2: Context loading ──────────────────────────────────────────────


def channel_context_path(channel: str) -> Path:
    """Return the filesystem path to a channel's pinned context file.

    Channels live at ``docs/agent-channels/{channel}/context.md``.
    The file does NOT have to exist — ``context_sha256`` returns
    empty string for missing files, and ``load_channel_context``
    treats a missing file as "no pinned context" rather than erroring.
    """
    return CONTEXT_ROOT / channel / "context.md"


def load_channel_context(
    channel: str,
    *,
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    """Load a channel's pinned context plus all recursive includes.

    Walks the ``include`` chain depth-first, resolving each included
    channel's ``context.md`` and concatenating them in include-order
    (shared-first if ``shared`` is included). Cycles are broken by
    tracking the ``_seen`` set — recursion never revisits a channel.

    Returns a dict:
        {
            "body": str,                    # concatenated context text
            "revs": {channel: sha256_hex},  # per-file revisions for audit
            "missing": [channel, ...],      # channels whose context.md doesn't exist
        }

    The ``revs`` dict is intended for storing in the ``channel_messages``
    row so that a message's context is replayable deterministically.

    **Missing context files are soft errors.** They return empty body
    and are recorded in ``missing``. A post will still succeed with
    an empty context — the idea is that channels can be created
    before their context.md is written, and the system should be
    usable without any pinned context at all.
    """
    _seen = _seen if _seen is not None else set()
    if channel in _seen:
        return {"body": "", "revs": {}, "missing": []}
    _seen.add(channel)

    ch = get_channel(channel)
    if ch is None:
        # Channel doesn't exist in DB — treat as empty. Callers that
        # care (e.g. post()) will fail upstream with a clearer error.
        return {"body": "", "revs": {}, "missing": [channel]}

    revs: dict[str, str] = {}
    missing: list[str] = []
    parts: list[str] = []

    # 1. Recursively resolve all included channels first (shared, etc.)
    #    so the final output reads: [shared] → [included_1] → [self].
    for include in ch["include"]:
        sub = load_channel_context(include, _seen=_seen)
        if sub["body"]:
            parts.append(sub["body"])
        revs.update(sub["revs"])
        missing.extend(sub["missing"])

    # 2. Load this channel's own context.md.
    ctx_path = channel_context_path(channel)
    rev = context_sha256(ctx_path)
    revs[channel] = rev
    try:
        own_body = ctx_path.read_text("utf-8")
        if own_body.strip():
            parts.append(
                f"--- context: {channel} (sha256: {rev[:12]}) ---\n{own_body.rstrip()}\n"
            )
    except (OSError, FileNotFoundError):
        missing.append(channel)

    return {
        "body": "\n".join(parts),
        "revs": revs,
        "missing": missing,
    }


# ── B.2: Monitor API fetch ────────────────────────────────────────────


def fetch_monitor_state(
    *,
    timeout: float = MONITOR_FETCH_TIMEOUT_S,
    url: str = MONITOR_API_URL,
) -> dict[str, Any] | None:
    """Fetch current project state from the Monitor API.

    Returns the decoded JSON dict on success, or None on ANY failure
    (connection refused, timeout, non-200 status, malformed JSON).
    The Monitor API is on the same machine — if it's not responding
    in 2 seconds, it's down, not slow. Callers treat None as "no
    snapshot available" and proceed without blocking the post.

    This is the dynamic-state half of Gemini's correction in the B.1
    design review: the pinned context.md is STABLE state (conventions,
    rules); the Monitor API snapshot is VOLATILE state (current sprint,
    active tickets, recent commits, build state). Both get recorded
    into the message row so replay is deterministic.
    """
    if not url:
        return None

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ai-agent-bridge-channels/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        # Broad catch is deliberate (Gemini B.2 review non-blocker #2):
        # urllib.error.URLError covers most network errors but not
        # UnicodeDecodeError (subclass of ValueError) or some
        # http.client.HTTPException subclasses like IncompleteRead.
        # A freak network corruption should never crash an active post.
        return None


# ── B.2: History truncation (char budget, not message count) ─────────


def truncate_history_by_budget(
    messages: list[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_HISTORY_CHARS,
) -> tuple[list[dict[str, Any]], int]:
    """Trim a message list to fit within a character budget.

    Pattern ported from ``_messaging.get_conversation_context()`` —
    iterate newest-first, accumulate until budget is exhausted, drop
    oldest first. This is Gemini's B.1 #3 correction: count bytes,
    not messages. A single 400-line script in the history would blow
    past a naive ``K=5`` cap, so we truncate by char count instead.

    Returns ``(kept_messages, dropped_count)`` ordered oldest→newest.
    The caller is responsible for rendering the result into the final
    prompt (so the "... [N older messages omitted] ..." marker is
    placed consistently with whatever formatting they use).
    """
    if not messages:
        return [], 0
    # Rough character estimate = body + small envelope for metadata.
    kept_rev: list[dict[str, Any]] = []
    total = 0
    for msg in reversed(messages):
        entry_size = len(msg.get("body", "")) + 80  # +80 for round/agent/timestamp envelope
        if total + entry_size > max_chars and kept_rev:
            break
        kept_rev.append(msg)
        total += entry_size
    dropped = len(messages) - len(kept_rev)
    kept_rev.reverse()
    return kept_rev, dropped


# ── B.2: Agent prompt assembly ────────────────────────────────────────


def build_agent_prompt(
    channel: str,
    body: str,
    *,
    history_tail: int = 10,
    max_history_chars: int = DEFAULT_MAX_HISTORY_CHARS,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    include_monitor_state: bool = True,
) -> dict[str, Any]:
    """Assemble the full text an agent sees for a post in this channel.

    Returns a dict with the assembled text plus metadata useful for
    storing on the message row:

        {
            "prompt": str,                   # the full text to send to the agent
            "context_revs": {chan: sha256},  # which context files were seen
            "monitor_state": dict | None,    # Monitor API snapshot at post-time
            "history_dropped": int,          # # of older messages truncated
            "total_chars": int,              # prompt length
        }

    Assembly order (oldest-first, highest-priority sections LAST so
    they're near the end of the prompt where attention peaks):

        1. Pinned context (shared + channel includes + channel self)
        2. Monitor state snapshot (volatile project state)
        3. Message history for the channel (truncated to budget)
        4. The new post body

    If the assembled prompt exceeds ``max_prompt_chars``, history is
    dropped first (oldest-first). If even zero history won't fit,
    the pinned context is truncated from the end. We never drop the
    new post body — if the body alone exceeds the budget, we raise
    ValueError so the caller knows to split or shorten it.
    """
    # 1. Pinned context from this channel and its includes
    ctx = load_channel_context(channel)
    context_text = ctx["body"]

    # 2. Monitor state
    monitor_state = fetch_monitor_state() if include_monitor_state else None
    monitor_text = ""
    if monitor_state:
        monitor_text = (
            "--- monitor: project state (volatile) ---\n"
            + json.dumps(monitor_state, indent=2, ensure_ascii=False)
            + "\n"
        )

    # 3. Channel history (newest N, truncated by char budget)
    raw_history = read(channel, tail=history_tail)
    kept, dropped = truncate_history_by_budget(
        raw_history, max_chars=max_history_chars
    )
    history_text = ""
    if kept:
        lines = [f"--- history: last {len(kept)} messages in {channel} ---"]
        if dropped:
            lines.append(f"... [{dropped} older messages omitted] ...")
        for msg in kept:
            lines.append(
                f"[{msg['created_at'][:19]}] {msg['from_agent']} "
                f"(round {msg['round_index']}): {msg['body']}"
            )
        history_text = "\n".join(lines) + "\n"

    # 4. The new post body
    body_text = f"--- new post ({channel}) ---\n{body}\n"

    # Assemble and enforce the hard ceiling
    sections = [context_text, monitor_text, history_text, body_text]
    prompt = "\n".join(s for s in sections if s.strip())

    if len(prompt) > max_prompt_chars:
        # Drop history first (oldest-first already truncated above,
        # now drop all of it if needed).
        prompt_no_history = "\n".join(
            s for s in [context_text, monitor_text, body_text] if s.strip()
        )
        if len(prompt_no_history) <= max_prompt_chars:
            prompt = prompt_no_history
            dropped = len(raw_history)  # all dropped
            history_text = ""
        else:
            # Even with zero history we're over budget. Drop monitor
            # state AND truncate context. If the body alone is over
            # budget, that's a caller error — raise.
            body_len = len(body_text)
            if body_len > max_prompt_chars:
                raise ValueError(
                    f"post body alone is {body_len} chars, "
                    f"exceeds max_prompt_chars={max_prompt_chars}. "
                    f"Split it into smaller posts or increase the budget."
                )

            # Budget math (post B.2 review — Gemini found a negative-
            # slice bug in the original, and the fix introduced a
            # second bug where the "[context truncated]" marker itself
            # ate into the budget). Now we explicitly account for the
            # marker length and guarantee the final prompt fits.
            marker = "\n... [context truncated to fit budget] ...\n"
            marker_len = len(marker)
            non_body_budget = max_prompt_chars - body_len

            # We need room for: marker + at least a few chars of context.
            # If non_body_budget can't even fit the marker, drop context
            # entirely and return just the body (can't lie about truncation
            # if we have nothing to truncate TO).
            min_context_chars = 1  # at least 1 char of context to be useful
            if non_body_budget >= marker_len + min_context_chars:
                remaining_for_ctx = non_body_budget - marker_len
                if remaining_for_ctx < len(context_text):
                    truncated_ctx = context_text[:remaining_for_ctx]
                    prompt = f"{truncated_ctx}{marker}{body_text}"
                else:
                    # Context already fits without truncation
                    prompt = (
                        f"{context_text}\n{body_text}"
                        if context_text.strip()
                        else body_text
                    )
            else:
                # No room for marker + context; body only
                prompt = body_text

            dropped = len(raw_history)
            monitor_state = None  # dropped to save space

    return {
        "prompt": prompt,
        "context_revs": ctx["revs"],
        "monitor_state": monitor_state,
        "history_dropped": dropped,
        "total_chars": len(prompt),
    }


# ── Channel management ────────────────────────────────────────────────


def create_channel(
    name: str,
    *,
    description: str = "",
    include: list[str] | None = None,
    subscribers: list[str] | None = None,
    exist_ok: bool = True,
) -> dict[str, Any]:
    """Create a new channel (topic).

    ``include`` lists other channel names whose context should be
    auto-prepended to posts in this channel (commonly ``["shared"]``).
    ``subscribers`` lists which agents can be default recipients of
    broadcast posts; it does NOT restrict who can post.

    Raises ValueError on duplicate if ``exist_ok=False``. Otherwise,
    this is an upsert — already-existing channels are left untouched
    and the current row is returned.
    """
    if not name or not name.strip():
        raise ValueError("channel name cannot be empty")
    if name != name.strip().lower().replace(" ", "-"):
        raise ValueError(
            f"channel name must be lowercase-kebab-case; got '{name}'"
        )

    include = include or []
    subscribers = subscribers or []
    for agent in subscribers:
        _validate_agent(agent)

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT name, description, include, subscribers, created_at "
            "FROM channels WHERE name = ?",
            (name,),
        ).fetchone()
        if existing:
            if not exist_ok:
                raise ValueError(f"channel '{name}' already exists")
            return _row_to_channel(existing)

        conn.execute(
            "INSERT INTO channels (name, created_at, description, include, "
            "subscribers, context_sha256) VALUES (?, ?, ?, ?, ?, ?)",
            (
                name,
                _now_iso(),
                description,
                ",".join(include),
                ",".join(subscribers),
                "",
            ),
        )
        conn.commit()
        return {
            "name": name,
            "description": description,
            "include": include,
            "subscribers": subscribers,
            "created_at": _now_iso(),
        }
    finally:
        conn.close()


def get_channel(name: str) -> dict[str, Any] | None:
    """Fetch a channel by name, or return None if it doesn't exist."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, description, include, subscribers, created_at "
            "FROM channels WHERE name = ?",
            (name,),
        ).fetchone()
        return _row_to_channel(row) if row else None
    finally:
        conn.close()


def list_channels() -> list[dict[str, Any]]:
    """Return all channels, ordered by creation time (oldest first)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT name, description, include, subscribers, created_at "
            "FROM channels ORDER BY created_at ASC"
        ).fetchall()
        return [_row_to_channel(r) for r in rows]
    finally:
        conn.close()


def _row_to_channel(row) -> dict[str, Any]:
    """Convert a ``sqlite3.Row`` to a channel dict.

    Uses dict-style key access so a SELECT column reorder can't silently
    break this helper — Gemini's B.1 review non-blocker #2.
    """
    return {
        "name": row["name"],
        "description": row["description"],
        "include": [s for s in row["include"].split(",") if s],
        "subscribers": [s for s in row["subscribers"].split(",") if s],
        "created_at": row["created_at"],
    }


# ── Posting ───────────────────────────────────────────────────────────


def post(
    channel: str,
    from_agent: str,
    body: str,
    *,
    to_agents: list[str] | None = None,
    parent_id: str | None = None,
    correlation_id: str | None = None,
    kind: str = "post",
    from_model: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    context_rev_shared: str | None = None,
    context_rev_channel: str | None = None,
    monitor_state_snapshot: dict[str, Any] | None = None,
    auto_snapshot: bool = True,
    pre_delivered: bool = False,
) -> dict[str, Any]:
    """Create a new channel_messages row + N deliveries rows atomically.

    Returns ``{"message_id": ..., "thread_id": ..., "delivery_ids": [...]}``.

    Atomicity is enforced by ``BEGIN IMMEDIATE`` — under concurrent posts,
    the second caller queues on the 5-second ``busy_timeout`` rather than
    racing. This matches Gemini's #1 correction in the B.1 design review.

    ``to_agents`` may be an empty list; in that case no deliveries are
    created and the message is a pure "log entry" (useful for
    system/audit posts). ``parent_id`` links a reply to its origin;
    the reply's ``thread_id`` is inherited from the parent. If
    ``pre_delivered=True``, any created delivery rows are inserted in
    terminal ``delivered`` state immediately instead of ``pending``.

    **B.2 context auto-snapshot (#1190):** if ``auto_snapshot=True``
    (default) and the ``context_rev_*`` / ``monitor_state_snapshot``
    kwargs are left at their sentinel ``None``, the function reads
    the current pinned context files and fetches the Monitor API,
    storing both in the message row. This makes message history
    deterministically replayable. Callers that want manual control
    (tests, synthetic posts, system announcements) can pass explicit
    values or set ``auto_snapshot=False``.
    """
    body = redact_text(body)
    attachments = redact_jsonable(attachments) if attachments else None
    monitor_state_snapshot = (
        redact_jsonable(monitor_state_snapshot)
        if monitor_state_snapshot is not None
        else None
    )

    _validate_agent(from_agent)
    _validate_kind(kind)
    for agent in to_agents or []:
        _validate_agent(agent)

    # B.2: Auto-populate context snapshots if not provided.
    # The "" vs None distinction matters — empty string is an explicit
    # "no context", None is "please auto-fetch". Tests and system posts
    # can pass explicit empty strings to skip the filesystem/network I/O.
    if auto_snapshot:
        if context_rev_shared is None:
            shared_path = channel_context_path(SHARED_CHANNEL)
            context_rev_shared = context_sha256(shared_path)
            # Loud warning on missing shared context — agents need
            # project-wide rules/conventions, and posting blind is a
            # worse failure mode than printing to stderr. Gemini's
            # non-blocker #1 in the B.1 review (task bridge-b1-review).
            if not context_rev_shared and channel != SHARED_CHANNEL:
                import sys as _sys
                print(
                    f"⚠️  channel-bridge: shared context file is missing at "
                    f"{shared_path} — agent will post without project-wide "
                    f"rules. Create it with `ab context shared --edit`.",
                    file=_sys.stderr,
                )
        if context_rev_channel is None:
            context_rev_channel = context_sha256(
                channel_context_path(channel)
            )
        if monitor_state_snapshot is None:
            # Best-effort — returns None on any failure, which is fine.
            monitor_state_snapshot = redact_jsonable(fetch_monitor_state())

    # Normalize sentinel Nones so the DB stores empty string rather
    # than nullable columns having inconsistent semantics.
    context_rev_shared = context_rev_shared or ""
    context_rev_channel = context_rev_channel or ""

    message_id = _new_id()
    created_at = _now_iso()
    attachments_json = json.dumps(attachments) if attachments else None
    monitor_json = (
        json.dumps(monitor_state_snapshot) if monitor_state_snapshot else None
    )

    conn = get_db()
    try:
        # BEGIN IMMEDIATE acquires the write lock FIRST, then does all
        # reads and writes under the same transaction. Gemini's #2
        # blocker in the B.1 adversarial review: doing reads before
        # BEGIN IMMEDIATE leaves a TOCTOU window where a concurrent
        # writer could delete/rename the channel between the existence
        # check and the insert, violating the FK. Solved by moving
        # every read under the write lock. Under concurrency the
        # second caller queues on busy_timeout rather than deadlocking.
        conn.execute("BEGIN IMMEDIATE")

        # Verify the channel exists before inserting — the FK would
        # catch it, but an explicit check gives a better error message.
        ch = conn.execute(
            "SELECT name FROM channels WHERE name = ?", (channel,)
        ).fetchone()
        if not ch:
            raise ValueError(f"channel '{channel}' does not exist")

        # Resolve thread_id: inherit from parent if replying, else
        # self-reference (Gemini's correction — avoids NULL edge cases).
        if parent_id:
            parent = conn.execute(
                "SELECT thread_id, round_index FROM channel_messages WHERE message_id = ?",
                (parent_id,),
            ).fetchone()
            if not parent:
                raise ValueError(f"parent message '{parent_id}' not found")
            thread_id = parent["thread_id"]
            round_index = parent["round_index"] + 1
        else:
            thread_id = message_id
            round_index = 0

        conn.execute(
            """
            INSERT INTO channel_messages (
                message_id, channel, thread_id, parent_id, correlation_id,
                round_index, from_agent, from_model, kind, body,
                attachments, context_rev_shared, context_rev_channel,
                monitor_state_snapshot, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id, channel, thread_id, parent_id, correlation_id,
                round_index, from_agent, from_model, kind, body,
                attachments_json, context_rev_shared, context_rev_channel,
                monitor_json, created_at,
            ),
        )

        delivery_ids = []
        for agent in to_agents or []:
            dlv_id = _new_id()
            delivery_ids.append(dlv_id)
            if pre_delivered:
                conn.execute(
                    """
                    INSERT INTO deliveries (
                        delivery_id, message_id, to_agent, status, delivered_at
                    ) VALUES (?, ?, ?, 'delivered', ?)
                    """,
                    (dlv_id, message_id, agent, created_at),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO deliveries (
                        delivery_id, message_id, to_agent, status
                    ) VALUES (?, ?, ?, 'pending')
                    """,
                    (dlv_id, message_id, agent),
                )

        conn.commit()

        if not pre_delivered:
            for agent in set(to_agents or []):
                _touch_wake_file(agent)

        return {
            "message_id": message_id,
            "thread_id": thread_id,
            "parent_id": parent_id,
            "correlation_id": correlation_id,
            "round_index": round_index,
            "delivery_ids": delivery_ids,
            "created_at": created_at,
        }
    except Exception:
        # Catches both sqlite3.Error (insert failure) AND ValueError
        # from the now-inside-transaction channel/parent checks.
        # Previously this was sqlite3.Error only, which left an orphan
        # lock when a ValueError escaped inside the transaction.
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Reading ───────────────────────────────────────────────────────────


def read(
    channel: str,
    *,
    tail: int = 20,
    thread_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read messages from a channel.

    If ``thread_id`` is given, returns all messages in that thread
    (ordered by round_index, then created_at). Otherwise returns the
    last ``tail`` messages in the channel ordered oldest→newest.
    """
    conn = get_db()
    try:
        if thread_id:
            rows = conn.execute(
                """
                SELECT message_id, channel, thread_id, parent_id, correlation_id,
                       round_index, from_agent, from_model, kind, body,
                       attachments, context_rev_shared, context_rev_channel,
                       monitor_state_snapshot, created_at
                FROM channel_messages
                WHERE channel = ? AND thread_id = ?
                ORDER BY round_index ASC, created_at ASC
                """,
                (channel, thread_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT message_id, channel, thread_id, parent_id, correlation_id,
                       round_index, from_agent, from_model, kind, body,
                       attachments, context_rev_shared, context_rev_channel,
                       monitor_state_snapshot, created_at
                FROM (
                    SELECT * FROM channel_messages
                    WHERE channel = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC
                """,
                (channel, tail),
            ).fetchall()
        return [_row_to_message(r) for r in rows]
    finally:
        conn.close()


def thread_exists(channel: str, thread_id: str) -> bool:
    """Return whether a thread exists in a channel."""
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM channel_messages
            WHERE channel = ? AND thread_id = ?
            LIMIT 1
            """,
            (channel, thread_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _row_to_message(row) -> dict[str, Any]:
    """Convert a ``sqlite3.Row`` to a message dict (dict-style access)."""
    return {
        "message_id": row["message_id"],
        "channel": row["channel"],
        "thread_id": row["thread_id"],
        "parent_id": row["parent_id"],
        "correlation_id": row["correlation_id"],
        "round_index": row["round_index"],
        "from_agent": row["from_agent"],
        "from_model": row["from_model"],
        "kind": row["kind"],
        "body": redact_text(row["body"]),
        "attachments": (
            redact_jsonable(json.loads(row["attachments"]))
            if row["attachments"]
            else None
        ),
        "context_rev_shared": row["context_rev_shared"],
        "context_rev_channel": row["context_rev_channel"],
        "monitor_state_snapshot": (
            redact_jsonable(json.loads(row["monitor_state_snapshot"]))
            if row["monitor_state_snapshot"]
            else None
        ),
        "created_at": row["created_at"],
    }


# ── Delivery state ────────────────────────────────────────────────────


def mark_delivery(
    delivery_id: str,
    status: str,
    *,
    error: str | None = None,
    delivered_at: str | None = None,
) -> None:
    """Update a delivery's status (outbound state machine)."""
    if status not in VALID_DELIVERY_STATUSES:
        raise ValueError(
            f"invalid delivery status '{status}'. "
            f"Expected one of {VALID_DELIVERY_STATUSES}."
        )

    now = _now_iso()
    conn = get_db()
    try:
        if status == "dispatched":
            conn.execute(
                """
                UPDATE deliveries
                SET status=?, dispatched_at=?, error=?, lease_until=NULL
                WHERE delivery_id=?
                """,
                (status, now, error, delivery_id),
            )
        elif status == "delivered":
            conn.execute(
                """
                UPDATE deliveries
                SET status=?, delivered_at=?, error=?, lease_until=NULL, retry_after=NULL
                WHERE delivery_id=?
                """,
                (status, delivered_at or now, error, delivery_id),
            )
        elif status == "failed":
            conn.execute(
                """
                UPDATE deliveries
                SET status=?, error=?, lease_until=NULL, retry_after=NULL
                WHERE delivery_id=?
                """,
                (status, error, delivery_id),
            )
        else:  # pending — should not usually be explicit, but allow
            conn.execute(
                """
                UPDATE deliveries
                SET status=?, error=?, lease_until=NULL
                WHERE delivery_id=?
                """,
                (status, error, delivery_id),
            )
        conn.commit()
    finally:
        conn.close()


def claim_next_delivery(
    agent: str,
    *,
    lease_seconds: int = DEFAULT_DELIVERY_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_DELIVERY_ATTEMPTS,
    now: str | None = None,
) -> dict[str, Any] | None:
    """Atomically claim the oldest eligible pending delivery for an agent."""
    _validate_agent(agent)
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be > 0")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be > 0")

    now = now or _now_iso()
    lease_until = _iso_after(now, seconds=lease_seconds)

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT d.delivery_id
            FROM deliveries d
            JOIN channel_messages cm ON cm.message_id = d.message_id
            WHERE d.to_agent = ?
              AND d.attempt_count < ?
              AND (d.retry_after IS NULL OR d.retry_after <= ?)
              AND (
                    d.status = 'pending'
                    OR (d.status = 'processing' AND d.lease_until <= ?)
              )
            ORDER BY cm.created_at ASC, d.delivery_id ASC
            LIMIT 1
            """,
            (agent, max_attempts, now, now),
        ).fetchone()
        if not row:
            conn.commit()
            return None

        conn.execute(
            """
            UPDATE deliveries
            SET status='processing',
                lease_until=?,
                attempt_count=attempt_count + 1
            WHERE delivery_id=?
            """,
            (lease_until, row["delivery_id"]),
        )
        claimed = _delivery_queue_row(conn, row["delivery_id"])
        conn.commit()
        return claimed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_delivery_delivered(
    delivery_id: str,
    reply_message_id: str,
    *,
    now: str | None = None,
) -> None:
    """Mark a claimed delivery as terminally delivered."""
    now = now or _now_iso()
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status FROM deliveries WHERE delivery_id = ?",
            (delivery_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"delivery '{delivery_id}' not found")
        if row["status"] in {"delivered", "failed"}:
            conn.commit()
            return

        # reply_message_id is part of the worker API contract for the
        # next phase, but the current deliveries schema does not yet
        # persist reply linkage separately.
        _ = reply_message_id
        conn.execute(
            """
            UPDATE deliveries
            SET status='delivered',
                delivered_at=?,
                error=NULL,
                lease_until=NULL,
                retry_after=NULL,
                last_error_kind=NULL
            WHERE delivery_id=?
            """,
            (now, delivery_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_message_delivery_delivered(
    message_id: str,
    to_agent: str,
    reply_message_id: str,
    *,
    now: str | None = None,
) -> int:
    """Mark a message delivery to one agent as terminally delivered.

    ``ab discuss`` invokes agents inline instead of through the inbox
    worker, so it has a reply message but no claimed delivery id. This
    bridges that path without changing the delivery schema.
    """
    _validate_agent(to_agent)
    now = now or _now_iso()
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # reply_message_id is the caller's evidence that the delivery
        # produced a channel reply. The schema still has no reply linkage
        # column, so keep the argument for API symmetry with
        # mark_delivery_delivered() and future migration compatibility.
        _ = reply_message_id
        cursor = conn.execute(
            """
            UPDATE deliveries
            SET status='delivered',
                delivered_at=?,
                error=NULL,
                lease_until=NULL,
                retry_after=NULL,
                last_error_kind=NULL
            WHERE message_id=?
              AND to_agent=?
              AND status NOT IN ('delivered', 'failed')
            """,
            (now, message_id, to_agent),
        )
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_delivery_failed(
    delivery_id: str,
    error_kind: str,
    error_text: str,
    *,
    reschedule_after: str | None = None,
    now: str | None = None,
) -> None:
    """Mark a claimed delivery as failed or rescheduled."""
    _validate_error_kind(error_kind)
    now = now or _now_iso()

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, attempt_count FROM deliveries WHERE delivery_id = ?",
            (delivery_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"delivery '{delivery_id}' not found")
        if row["status"] in {"delivered", "failed"}:
            conn.commit()
            return

        retry_after = reschedule_after
        if error_kind == "rate_limited" and retry_after is None:
            retry_after = _iso_after(now, seconds=DEFAULT_RATE_LIMIT_RETRY_SECONDS)

        exhausted = row["attempt_count"] >= DEFAULT_MAX_DELIVERY_ATTEMPTS
        if retry_after is None or exhausted:
            conn.execute(
                """
                UPDATE deliveries
                SET status='failed',
                    error=?,
                    lease_until=NULL,
                    retry_after=NULL,
                    last_error_kind=?
                WHERE delivery_id=?
                """,
                (error_text, error_kind, delivery_id),
            )
        else:
            conn.execute(
                """
                UPDATE deliveries
                SET status='pending',
                    error=?,
                    lease_until=NULL,
                    retry_after=?,
                    last_error_kind=?
                WHERE delivery_id=?
                """,
                (error_text, retry_after, error_kind, delivery_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def release_expired_leases(now: str | None = None) -> int:
    """Reclaim deliveries stuck in processing after their lease expires."""
    now = now or _now_iso()
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE deliveries
            SET status='pending',
                lease_until=NULL
            WHERE status='processing'
              AND lease_until < ?
            """,
            (now,),
        )
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deliveries_for_message(message_id: str) -> list[dict[str, Any]]:
    """Return all deliveries for a message (pending or otherwise)."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT delivery_id, message_id, to_agent, to_model, status,
                   dispatched_at, delivered_at, error,
                   lease_until, attempt_count, retry_after, last_error_kind
            FROM deliveries
            WHERE message_id = ?
            ORDER BY delivery_id
            """,
            (message_id,),
        ).fetchall()
        return [
            {
                "delivery_id": r["delivery_id"],
                "message_id": r["message_id"],
                "to_agent": r["to_agent"],
                "to_model": r["to_model"],
                "status": r["status"],
                "dispatched_at": r["dispatched_at"],
                "delivered_at": r["delivered_at"],
                "error": r["error"],
                "lease_until": r["lease_until"],
                "attempt_count": r["attempt_count"],
                "retry_after": r["retry_after"],
                "last_error_kind": r["last_error_kind"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def pending_deliveries_for(agent: str) -> list[dict[str, Any]]:
    """Return pending deliveries for an agent, oldest-first.

    Uses the compound index ``idx_deliveries_agent_queue`` on
    ``(to_agent, status, dispatched_at)``.
    """
    _validate_agent(agent)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT d.delivery_id, d.message_id, d.to_agent, d.to_model,
                   d.status, d.dispatched_at, d.delivered_at, d.error,
                   d.lease_until, d.attempt_count, d.retry_after, d.last_error_kind,
                   cm.body, cm.from_agent AS cm_from_agent,
                   cm.channel AS cm_channel, cm.created_at AS cm_created_at
            FROM deliveries d
            JOIN channel_messages cm ON cm.message_id = d.message_id
            WHERE d.to_agent = ? AND d.status = 'pending'
            ORDER BY cm.created_at ASC
            """,
            (agent,),
        ).fetchall()
        return [_row_to_pending_delivery(r) for r in rows]
    finally:
        conn.close()
