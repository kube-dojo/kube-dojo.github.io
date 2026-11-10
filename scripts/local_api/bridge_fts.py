"""FTS5 setup for bridge-backed local API search.

KubeDojo product code: the shared bridge (lu_machinery.ai_agent_bridge) has no
full-text index, so the local API owns the index it searches.
"""

from __future__ import annotations

import sqlite3

_CHANNEL_MESSAGES_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS channel_messages_fts USING fts5(
    body,
    channel UNINDEXED,
    thread_id UNINDEXED,
    message_id UNINDEXED,
    from_agent UNINDEXED,
    created_at UNINDEXED,
    content='channel_messages',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS channel_messages_fts_ins
AFTER INSERT ON channel_messages
BEGIN
    INSERT INTO channel_messages_fts(
        rowid, body, channel, thread_id, message_id, from_agent, created_at
    )
    VALUES (
        new.rowid, new.body, new.channel, new.thread_id,
        new.message_id, new.from_agent, new.created_at
    );
END;

CREATE TRIGGER IF NOT EXISTS channel_messages_fts_del
AFTER DELETE ON channel_messages
BEGIN
    INSERT INTO channel_messages_fts(
        channel_messages_fts, rowid, body, channel, thread_id,
        message_id, from_agent, created_at
    )
    VALUES (
        'delete', old.rowid, old.body, old.channel, old.thread_id,
        old.message_id, old.from_agent, old.created_at
    );
END;

CREATE TRIGGER IF NOT EXISTS channel_messages_fts_upd
AFTER UPDATE ON channel_messages
BEGIN
    INSERT INTO channel_messages_fts(
        channel_messages_fts, rowid, body, channel, thread_id,
        message_id, from_agent, created_at
    )
    VALUES (
        'delete', old.rowid, old.body, old.channel, old.thread_id,
        old.message_id, old.from_agent, old.created_at
    );
    INSERT INTO channel_messages_fts(
        rowid, body, channel, thread_id, message_id, from_agent, created_at
    )
    VALUES (
        new.rowid, new.body, new.channel, new.thread_id,
        new.message_id, new.from_agent, new.created_at
    );
END;
"""

_DECISIONS_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
    title,
    body,
    filename UNINDEXED,
    mtime UNINDEXED,
    status UNINDEXED
);
"""


def _object_exists(conn: sqlite3.Connection, object_type: str, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ? LIMIT 1",
        (object_type, name),
    ).fetchone()
    return row is not None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return _object_exists(conn, "table", name)


def _channel_fts_indexed_count(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "channel_messages_fts_docsize"):
        return 0
    row = conn.execute("SELECT COUNT(*) FROM channel_messages_fts_docsize").fetchone()
    return int(row[0] if row else 0)


def setup_channel_messages_fts(conn: sqlite3.Connection) -> None:
    """Create and backfill the channel message FTS index if possible."""
    if not _table_exists(conn, "channel_messages"):
        return

    created = not _table_exists(conn, "channel_messages_fts")
    triggers_missing = any(
        not _object_exists(conn, "trigger", name)
        for name in (
            "channel_messages_fts_ins",
            "channel_messages_fts_del",
            "channel_messages_fts_upd",
        )
    )
    if created or triggers_missing:
        conn.executescript(_CHANNEL_MESSAGES_FTS_SCHEMA)

    source_count_row = conn.execute("SELECT COUNT(*) FROM channel_messages").fetchone()
    source_count = int(source_count_row[0] if source_count_row else 0)
    if source_count and (created or _channel_fts_indexed_count(conn) == 0):
        conn.execute("INSERT INTO channel_messages_fts(channel_messages_fts) VALUES ('rebuild')")


def setup_decisions_fts(conn: sqlite3.Connection) -> None:
    """Create the filesystem-backed decision-card FTS index."""
    if not _table_exists(conn, "decisions_fts"):
        conn.executescript(_DECISIONS_FTS_SCHEMA)


def setup_fts_tables(conn: sqlite3.Connection) -> None:
    """Idempotently install all FTS tables used by the local API."""
    setup_channel_messages_fts(conn)
    setup_decisions_fts(conn)
