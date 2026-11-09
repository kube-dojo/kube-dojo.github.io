"""Database initialization and session management.

The broker DB stores two subsystems:

**Legacy 1:1 message bus** (``messages``, ``sessions``) — used by the
``ask-claude``/``ask-gemini``/``ask-codex`` commands. Stays unchanged
while the channel bridge (#1190) is being rolled out.

**Channel bridge** (``channels``, ``channel_messages``, ``deliveries``) —
the new multi-agent primitive. A post = 1 ``channel_messages`` row +
N ``deliveries`` rows (one per recipient). Replies are just new
``channel_messages`` rows with ``parent_id`` pointing at the original;
they do NOT update the delivery row — delivery tracks outbound
routing state only (pending → dispatched → delivered → failed), not
inbound response content. This separation was Gemini's #1 correction
in the B.1 design round (task bridge-b1-schema-design, 2026-04-11).
"""

import sqlite3
from datetime import UTC, datetime
from typing import Literal, overload

from ._config import DB_PATH
from ._fts import setup_fts_tables

# ── Schema definitions ─────────────────────────────────────────────────
# Kept at module scope so tests and tooling can import them.

_LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    from_llm TEXT NOT NULL,
    to_llm TEXT NOT NULL,
    message_type TEXT DEFAULT 'message',
    content TEXT NOT NULL,
    data TEXT,
    timestamp TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS sessions (
    task_id TEXT PRIMARY KEY,
    claude_session_id TEXT,
    gemini_session_id TEXT,
    codex_session_id TEXT,
    claude_cwd TEXT,
    claude_sandbox_mode TEXT,
    gemini_cwd TEXT,
    gemini_sandbox_mode TEXT,
    codex_cwd TEXT,
    codex_sandbox_mode TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# ── Channel bridge tables (#1190 Phase B.1) ───────────────────────────
#
# Design decisions locked in after Gemini critique:
# 1. BEGIN IMMEDIATE for fanout inserts (queues writers gracefully on
#    the 5000ms busy_timeout instead of deadlocking)
# 2. Replies = new channel_messages rows with parent_id, NOT updates
#    to deliveries — deliveries is strictly an outbound state machine
# 3. thread_id defaults to message_id for originating posts
#    (self-reference → no NULL edge cases in thread queries)
# 4. context_rev_* stored as TEXT sha256 hex (auto-computed, no manual
#    counters to forget, survives git pulls across machines)
# 5. monitor_state_snapshot stays as plain TEXT JSON — debuggable,
#    supports SQLite's json_extract() later
# 6. correlation_id kept separate from thread_id to trace system-level
#    fanout events (e.g. "these N dispatches came from one ab discuss")
_CHANNELS_SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    name TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    description TEXT DEFAULT '',
    include TEXT DEFAULT '',          -- comma-sep channels to auto-include (e.g. "shared")
    subscribers TEXT DEFAULT '',      -- comma-sep agents (e.g. "claude,gemini,codex")
    context_sha256 TEXT DEFAULT ''    -- last-seen sha256 of {channel}/context.md
);

CREATE TABLE IF NOT EXISTS channel_messages (
    message_id TEXT PRIMARY KEY,          -- uuid4 hex
    channel TEXT NOT NULL,
    thread_id TEXT NOT NULL,              -- defaults to message_id for origins
    parent_id TEXT,                       -- nullable, reply threading
    correlation_id TEXT,                  -- nullable, fanout event ID
    round_index INTEGER DEFAULT 0,        -- 0 = origin, 1+ = replies
    from_agent TEXT NOT NULL,             -- claude/gemini/codex/user
    from_model TEXT,                      -- exact model ID
    kind TEXT DEFAULT 'post',             -- post/reply/system/fanout_start/fanout_end
    body TEXT NOT NULL,
    attachments TEXT,                     -- JSON array
    context_rev_shared TEXT,              -- sha256 hex of shared/context.md at post-time
    context_rev_channel TEXT,             -- sha256 hex of {channel}/context.md at post-time
    monitor_state_snapshot TEXT,          -- JSON blob from /api/state/summary
    created_at TEXT NOT NULL,
    FOREIGN KEY (channel) REFERENCES channels(name),
    FOREIGN KEY (parent_id) REFERENCES channel_messages(message_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_messages_channel_time
    ON channel_messages(channel, created_at);
CREATE INDEX IF NOT EXISTS idx_channel_messages_thread
    ON channel_messages(thread_id, round_index);
CREATE INDEX IF NOT EXISTS idx_channel_messages_correlation
    ON channel_messages(correlation_id);
CREATE INDEX IF NOT EXISTS idx_channel_messages_parent
    ON channel_messages(parent_id);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,         -- uuid4 hex
    message_id TEXT NOT NULL,             -- FK → channel_messages.message_id
    to_agent TEXT NOT NULL,               -- claude/gemini/codex
    to_model TEXT,                        -- target model (nullable)
    status TEXT DEFAULT 'pending',        -- pending/processing/dispatched/delivered/failed
    dispatched_at TEXT,
    delivered_at TEXT,
    error TEXT,
    lease_until TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    retry_after TEXT,
    last_error_kind TEXT,
    FOREIGN KEY (message_id) REFERENCES channel_messages(message_id)
);

CREATE INDEX IF NOT EXISTS idx_deliveries_message
    ON deliveries(message_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_agent_queue
    ON deliveries(to_agent, status, dispatched_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_claim
    ON deliveries(to_agent, status, retry_after, lease_until);
"""

_CHANNEL_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS channel_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id TEXT,
    thread_id TEXT NOT NULL,
    event TEXT NOT NULL,
    payload_json TEXT,
    ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_channel_events_thread_event
    ON channel_events(thread_id, event_id);
"""

# message_posted was removed. An existing database may still carry
# idx_channel_events_message_posted. That partial index constrains only
# rows whose event is 'message_posted', so leaving it does not affect
# other events or channel_messages. New databases do not create it, and
# get_db() does not drop it.


def _tune_connection(conn: sqlite3.Connection) -> None:
    """Apply PRAGMAs needed by both legacy and channel paths.

    WAL mode is essential for the channel bridge: it allows concurrent
    readers while a writer is active, so ``ab p`` and ``ab r`` don't
    block each other. ``busy_timeout`` gives writers up to 5 seconds
    to queue on contended inserts before raising ``SQLITE_BUSY``.

    Row factory is ``sqlite3.Row`` — supports both integer-index access
    (for legacy messages queries that use ``row[0]``) AND dict-style
    access (``row["name"]``) for channel queries. Ported on Gemini's
    B.1 review recommendation (task bridge-b1-review) to eliminate
    tuple-index fragility in the ``_row_to_*`` helpers.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row


def init_db():
    """Initialize database if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    _tune_connection(conn)
    conn.executescript(_LEGACY_SCHEMA)
    conn.executescript(_CHANNELS_SCHEMA)
    conn.executescript(_CHANNEL_EVENTS_SCHEMA)
    setup_fts_tables(conn)
    conn.commit()
    return conn


def get_db():
    """Get database connection with auto-migration (#604, #1190)."""
    if not DB_PATH.exists():
        return init_db()
    conn = sqlite3.connect(DB_PATH)
    _tune_connection(conn)

    try:
        cursor = conn.cursor()

        # --- Legacy messages table migration (#604) ---
        cursor.execute("PRAGMA table_info(messages)")
        columns = [row[1] for row in cursor.fetchall()]
        if not columns:
            # Table doesn't exist yet — create everything from scratch
            conn.executescript(_LEGACY_SCHEMA)
        elif "status" not in columns:
            print("🔧 Migrating database: adding 'status' column to 'messages' table")
            conn.execute("ALTER TABLE messages ADD COLUMN status TEXT DEFAULT 'pending'")

        # --- Sessions table migration (#604) ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                task_id TEXT PRIMARY KEY,
                claude_session_id TEXT,
                gemini_session_id TEXT,
                codex_session_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("PRAGMA table_info(sessions)")
        session_columns = [row[1] for row in cursor.fetchall()]
        if "codex_session_id" not in session_columns:
            print("🔧 Migrating database: adding 'codex_session_id' column to 'sessions' table")
            conn.execute("ALTER TABLE sessions ADD COLUMN codex_session_id TEXT")
        new_session_columns = [
            "claude_cwd",
            "claude_sandbox_mode",
            "gemini_cwd",
            "gemini_sandbox_mode",
            "codex_cwd",
            "codex_sandbox_mode",
        ]
        for column in new_session_columns:
            if column not in session_columns:
                print(
                    "🔧 Migrating database: adding '{0}' column to 'sessions' table"
                    .format(column)
                )
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} TEXT")

        # --- Channel bridge tables (#1190) ---
        # GATED by table-existence check. Running executescript() on
        # every connection — even with IF NOT EXISTS — parses the DDL
        # and bumps SQLite's schema cookie, which invalidates cached
        # prepared statements across ALL open connections and crashes
        # concurrent readers with "database schema has changed". This
        # was Gemini's #1 blocker in the B.1 adversarial review
        # (task bridge-b1-review). Same mitigation pattern as the
        # legacy messages-table migration above.
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='channels'"
        )
        if not cursor.fetchone():
            conn.executescript(_CHANNELS_SCHEMA)
        else:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='deliveries'"
            )
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(deliveries)")
                delivery_columns = [row[1] for row in cursor.fetchall()]

                if "lease_until" not in delivery_columns:
                    conn.execute("ALTER TABLE deliveries ADD COLUMN lease_until TEXT")
                if "attempt_count" not in delivery_columns:
                    conn.execute(
                        "ALTER TABLE deliveries ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
                    )
                if "retry_after" not in delivery_columns:
                    conn.execute("ALTER TABLE deliveries ADD COLUMN retry_after TEXT")
                if "last_error_kind" not in delivery_columns:
                    conn.execute(
                        "ALTER TABLE deliveries ADD COLUMN last_error_kind TEXT"
                    )

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='channel_events'"
                )
                if not cursor.fetchone():
                    conn.executescript(_CHANNEL_EVENTS_SCHEMA)

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_deliveries_claim'"
                )
                if not cursor.fetchone():
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_deliveries_claim
                        ON deliveries(to_agent, status, retry_after, lease_until)
                        """
                    )

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_channel_events_thread_event'"
                )
                if not cursor.fetchone():
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_channel_events_thread_event
                        ON channel_events(thread_id, event_id)
                        """
                    )

        setup_fts_tables(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return conn


def get_session(task_id: str) -> dict:
    """Get session IDs for a task."""
    if not task_id:
        return {
            "claude_session_id": None,
            "gemini_session_id": None,
            "codex_session_id": None,
            "claude_cwd": None,
            "claude_sandbox_mode": None,
            "gemini_cwd": None,
            "gemini_sandbox_mode": None,
            "codex_cwd": None,
            "codex_sandbox_mode": None,
        }

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        (
            "SELECT "
            "claude_session_id, gemini_session_id, codex_session_id, "
            "claude_cwd, claude_sandbox_mode, "
            "gemini_cwd, gemini_sandbox_mode, "
            "codex_cwd, codex_sandbox_mode "
            "FROM sessions WHERE task_id = ?"
        ),
        (task_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "claude_session_id": row["claude_session_id"],
            "gemini_session_id": row["gemini_session_id"],
            "codex_session_id": row["codex_session_id"],
            "claude_cwd": row["claude_cwd"],
            "claude_sandbox_mode": row["claude_sandbox_mode"],
            "gemini_cwd": row["gemini_cwd"],
            "gemini_sandbox_mode": row["gemini_sandbox_mode"],
            "codex_cwd": row["codex_cwd"],
            "codex_sandbox_mode": row["codex_sandbox_mode"],
        }
    return {
        "claude_session_id": None,
        "gemini_session_id": None,
        "codex_session_id": None,
        "claude_cwd": None,
        "claude_sandbox_mode": None,
        "gemini_cwd": None,
        "gemini_sandbox_mode": None,
        "codex_cwd": None,
        "codex_sandbox_mode": None,
    }


def _session_column(agent: str) -> str:
    """Map agent name to session table column."""
    columns = {
        "claude": "claude_session_id",
        "gemini": "gemini_session_id",
        "codex": "codex_session_id",
    }
    if agent not in columns:
        raise ValueError(f"Unknown session agent: {agent}")
    return columns[agent]


@overload
def set_session(
    task_id: str,
    agent: Literal["claude", "gemini", "codex"],
    session_id: str,
    *,
    claude_session_id: None = None,
    gemini_session_id: None = None,
    codex_session_id: None = None,
    claude_cwd: str | None = None,
    claude_sandbox_mode: str | None = None,
    gemini_cwd: str | None = None,
    gemini_sandbox_mode: str | None = None,
    codex_cwd: str | None = None,
    codex_sandbox_mode: str | None = None,
) -> None:
    ...


@overload
def set_session(
    task_id: str,
    agent: None = None,
    session_id: None = None,
    *,
    claude_session_id: str | None = None,
    gemini_session_id: str | None = None,
    codex_session_id: str | None = None,
) -> None:
    ...


def set_session(
    task_id: str,
    agent: str | None = None,
    session_id: str | None = None,
    *,
    claude_session_id: str | None = None,
    gemini_session_id: str | None = None,
    codex_session_id: str | None = None,
    claude_cwd: str | None = None,
    claude_sandbox_mode: str | None = None,
    gemini_cwd: str | None = None,
    gemini_sandbox_mode: str | None = None,
    codex_cwd: str | None = None,
    codex_sandbox_mode: str | None = None,
):
    """Set session IDs for one or more agents on a task."""
    if not task_id:
        return

    conn = get_db()
    cursor = conn.cursor()
    timestamp = datetime.now(UTC).isoformat()
    updates: dict[str, str] = {}

    if agent is not None:
        if session_id is not None:
            if isinstance(session_id, str):
                updates[_session_column(agent)] = session_id
        for key in ("cwd", "sandbox_mode"):
            col = f"{agent}_{key}"
            if key == "cwd":
                value = {
                    "claude": claude_cwd,
                    "gemini": gemini_cwd,
                    "codex": codex_cwd,
                }[agent]
            else:
                value = {
                    "claude": claude_sandbox_mode,
                    "gemini": gemini_sandbox_mode,
                    "codex": codex_sandbox_mode,
                }[agent]
            if isinstance(value, str):
                updates[col] = value

    legacy_aliases = {
        "claude_session_id": claude_session_id,
        "gemini_session_id": gemini_session_id,
        "codex_session_id": codex_session_id,
        "claude_cwd": claude_cwd,
        "claude_sandbox_mode": claude_sandbox_mode,
        "gemini_cwd": gemini_cwd,
        "gemini_sandbox_mode": gemini_sandbox_mode,
        "codex_cwd": codex_cwd,
        "codex_sandbox_mode": codex_sandbox_mode,
    }
    for column, value in legacy_aliases.items():
        if isinstance(value, str):
            updates[column] = value

    if not updates:
        return

    # Upsert session
    update_clause = ", ".join(
        f"{column} = excluded.{column}"
        for column in updates
    )
    columns = ", ".join(["task_id", *updates.keys(), "created_at", "updated_at"])
    placeholders = ", ".join(["?"] * (len(updates) + 3))
    cursor.execute(
        (
            f"INSERT INTO sessions ({columns}) VALUES ({placeholders}) "
            "ON CONFLICT(task_id) DO UPDATE SET "
            f"{update_clause}, updated_at = excluded.updated_at"
        ),
        [task_id, *updates.values(), timestamp, timestamp],
    )

    conn.commit()
    conn.close()
    # Legacy-compatible log hook for manual operations.
    if updates:
        first_agent = next(iter(updates))
        first_value = next(iter(updates.values()))
        if first_value:
            print(f"📌 Stored {first_agent} session: {first_value[:8]}... for task {task_id}")
