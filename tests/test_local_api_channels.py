from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_local_api():
    module_path = SCRIPTS_DIR / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_channels", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_local_api()
channels_route = local_api._CHANNEL_ROUTES


def _init_channel_events_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS channel_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              delivery_id TEXT,
              thread_id TEXT NOT NULL,
              event TEXT NOT NULL,
              payload_json TEXT,
              ts TEXT NOT NULL
            );
            """
        )
    finally:
        conn.commit()
        conn.close()


def _init_channel_messages_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS channel_messages (
              message_id TEXT PRIMARY KEY,
              channel TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              parent_id TEXT,
              correlation_id TEXT,
              round_index INTEGER DEFAULT 0,
              from_agent TEXT NOT NULL,
              from_model TEXT,
              kind TEXT DEFAULT 'post',
              body TEXT NOT NULL,
              attachments TEXT,
              context_rev_shared TEXT,
              context_rev_channel TEXT,
              monitor_state_snapshot TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
    finally:
        conn.commit()
        conn.close()


def _seed_channel_events(db_path: Path, events: list[dict[str, Any]], *, thread_id: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            """
            INSERT INTO channel_events (delivery_id, thread_id, event, payload_json, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    event.get("delivery_id"),
                    thread_id,
                    event["event"],
                    json.dumps(event["payload"]),
                    event["ts"],
                )
                for event in events
            ],
        )
    finally:
        conn.commit()
        conn.close()


def _use_bridge_db(monkeypatch, db_path: Path) -> None:
    import importlib

    bridge_config = importlib.import_module("ai_agent_bridge._config")
    bridge_db = importlib.import_module("ai_agent_bridge._db")
    monkeypatch.setenv("AB_DB_PATH", str(db_path))
    monkeypatch.setattr(bridge_config, "DB_PATH", db_path)
    monkeypatch.setattr(bridge_db, "DB_PATH", db_path)


def test_channel_threads_index_warns_when_supplementary_events_hit_limit(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    db_path = tmp_path / "messages.db"
    _init_channel_messages_db(db_path)
    _init_channel_events_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO channel_messages (
              message_id, channel, thread_id, from_agent, body, created_at
            )
            VALUES ('m1', 'topic', 'thread-1', 'user', 'subject', '2026-05-08T00:00:00Z')
            """
        )
        conn.commit()
    finally:
        conn.close()
    _seed_channel_events(
        db_path,
        [
            {
                "event": "reply_started",
                "payload": {"agent": "codex"},
                "ts": f"2026-05-08T00:00:0{idx}Z",
            }
            for idx in range(4)
        ],
        thread_id="thread-1",
    )

    monkeypatch.setattr(channels_route, "_SUPPLEMENTARY_EVENTS_LIMIT", 3)
    with caplog.at_level("WARNING", logger=channels_route.__name__):
        payload = channels_route.build_channel_threads_index(
            tmp_path,
            list_channels_fn=lambda: [{"name": "topic", "created_at": None}],
            resolve_bridge_db_path_fn=lambda _repo_root: db_path,
            query_sqlite_rows_fn=local_api._query_sqlite_rows,
        )

    assert payload["channels"][0]["threads"][0]["event_count"] == 3
    assert "channel events query hit limit (3 rows)" in caplog.text


def test_api_channels_returns_empty_shape(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "messages.db"
    _use_bridge_db(monkeypatch, db_path)
    status_code, payload, _ = local_api.route_request(tmp_path, "/api/channels")
    assert status_code == 200
    assert payload == {"channels": []}


def test_api_channels_legacy_event_fallback_uses_full_thread_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "messages.db"
    _use_bridge_db(monkeypatch, db_path)
    _init_channel_events_db(db_path)
    _seed_channel_events(
        db_path,
        [
            {
                "event": "reply_started",
                "payload": {"agent": "codex"},
                "ts": "2026-05-07T15:00:00+00:00",
            },
        ],
        thread_id="legacy-thread",
    )

    status_code, payload, _ = local_api.route_request(tmp_path, "/api/channels")

    assert status_code == 200
    thread = payload["channels"][0]["threads"][0]
    for key in (
        "subject",
        "thread_started_at",
        "thread_last_at",
        "message_count",
        "model_cascades",
        "reply_state",
        "vote_counts",
    ):
        assert key in thread
        assert thread[key] is None


def test_channel_page_default_view_attribute_reflects_thread_status(
    tmp_path: Path,
) -> None:
    def _render_top_nav(_active: str) -> str:
        return ""

    def _resolve(_repo_root: Path) -> Path:
        return tmp_path / "messages.db"

    def _rows_for_converged(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "message_id": "m1",
                "channel": "topic",
                "thread_id": "thread-1",
                "round_index": 1,
                "from_agent": "claude",
                "from_model": "test",
                "body": "Ready\n[AGREE]",
                "created_at": "2026-05-07T15:00:00+00:00",
                "cascade_cost_usd": 0,
                "cascade_elapsed_s": 0,
            },
            {
                "message_id": "m2",
                "channel": "topic",
                "thread_id": "thread-1",
                "round_index": 1,
                "from_agent": "codex",
                "from_model": "test",
                "body": "Ready\n[AGREE]",
                "created_at": "2026-05-07T15:00:01+00:00",
                "cascade_cost_usd": 0,
                "cascade_elapsed_s": 0,
            },
        ]

    status, html, _ = channels_route.route_channel_page_request(
        tmp_path,
        "/channels/thread-1",
        top_nav_css="",
        render_top_nav_fn=_render_top_nav,
        resolve_bridge_db_path_fn=_resolve,
        query_sqlite_rows_fn=_rows_for_converged,
    )
    assert status == 200
    assert 'data-default-view="graph"' in html

    status, html, _ = channels_route.route_channel_page_request(
        tmp_path,
        "/channels/thread-2",
        top_nav_css="",
        render_top_nav_fn=_render_top_nav,
        resolve_bridge_db_path_fn=_resolve,
        query_sqlite_rows_fn=lambda *_args, **_kwargs: [],
    )
    assert status == 200
    assert 'data-default-view="chat"' in html


def test_api_channel_events_returns_events_in_order(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "messages.db"
    _use_bridge_db(monkeypatch, db_path)
    _init_channel_events_db(db_path)
    thread_id = "thread-123"
    _seed_channel_events(
        db_path,
        [
            {
                "event": "reply_started",
                "payload": {"agent": "codex", "model": "gpt-5.5"},
                "ts": "2026-05-07T15:00:00+00:00",
            },
            {
                "event": "heartbeat",
                "payload": {"delivery_id": "d-1", "elapsed_s": 30},
                "ts": "2026-05-07T15:00:30+00:00",
            },
            {
                "event": "model_cascade",
                "payload": {"agent": "gemini", "model": "gpt-5.5"},
                "ts": "2026-05-07T15:01:00+00:00",
            },
        ],
        thread_id=thread_id,
    )
    status_code, payload, _ = local_api.route_request(tmp_path, f"/api/channel/{thread_id}/events")
    assert status_code == 200
    assert payload["thread_id"] == thread_id
    assert payload["events"] == [
        {
            "event_id": 1,
            "event": "reply_started",
            "ts": "2026-05-07T15:00:00+00:00",
            "agent": "codex",
            "model": "gpt-5.5",
        },
        {
            "event_id": 2,
            "event": "heartbeat",
            "ts": "2026-05-07T15:00:30+00:00",
            "delivery_id": "d-1",
            "elapsed_s": 30,
        },
        {
            "event_id": 3,
            "event": "model_cascade",
            "ts": "2026-05-07T15:01:00+00:00",
            "agent": "gemini",
            "model": "gpt-5.5",
        },
    ]
    assert payload["next_since_event_id"] == 3


def test_api_channel_events_since_event_id_filters(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "messages.db"
    _use_bridge_db(monkeypatch, db_path)
    _init_channel_events_db(db_path)
    thread_id = "thread-123"
    _seed_channel_events(
        db_path,
        [
            {
                "event": "reply_started",
                "payload": {"agent": "codex"},
                "ts": "2026-05-07T15:00:00+00:00",
            },
            {
                "event": "heartbeat",
                "payload": {"delivery_id": "d-1"},
                "ts": "2026-05-07T15:00:30+00:00",
            },
            {
                "event": "reply_complete",
                "payload": {"agent": "gemini"},
                "ts": "2026-05-07T15:01:00+00:00",
            },
        ],
        thread_id=thread_id,
    )
    status_code, payload, _ = local_api.route_request(
        tmp_path,
        f"/api/channel/{thread_id}/events?since_event_id=2",
    )
    assert status_code == 200
    assert payload["events"] == [
        {
            "event_id": 3,
            "event": "reply_complete",
            "ts": "2026-05-07T15:01:00+00:00",
            "agent": "gemini",
        }
    ]
    assert payload["next_since_event_id"] == 3


def _seed_bridge_thread(db_path: Path, monkeypatch) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    import importlib

    _use_bridge_db(monkeypatch, db_path)
    bridge_channels = importlib.import_module("ai_agent_bridge._channels")
    bridge_db = importlib.import_module("ai_agent_bridge._db")
    bridge_db.init_db().close()
    bridge_channels.create_channel("deliberation-ui-roadmap")
    root = bridge_channels.post(
        "deliberation-ui-roadmap",
        "claude",
        "Root decision prompt",
        auto_snapshot=False,
    )
    reply = bridge_channels.post(
        "deliberation-ui-roadmap",
        "codex",
        "[AGREE] Reply with implementation detail",
        parent_id=root["message_id"],
        auto_snapshot=False,
    )
    return bridge_db, root, reply


def test_api_channel_thread_post_replies_into_existing_thread(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "messages.db"
    bridge_db, root, _ = _seed_bridge_thread(db_path, monkeypatch)

    status_code, payload, _ = local_api.route_post_request(
        tmp_path,
        f"/api/channel/{root['thread_id']}/post",
        body_bytes=json.dumps({"body": "Human follow-up"}).encode(),
        content_type="application/json",
    )

    assert status_code == 200
    assert payload["ok"] is True
    assert payload["thread_id"] == root["thread_id"]
    assert payload["parent_id"] == root["message_id"]
    conn = bridge_db.get_db()
    try:
        row = conn.execute(
            """
            SELECT channel, thread_id, parent_id, from_agent, body
            FROM channel_messages
            WHERE message_id = ?
            """,
            (payload["message_id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["channel"] == "deliberation-ui-roadmap"
    assert row["thread_id"] == root["thread_id"]
    assert row["parent_id"] == root["message_id"]
    assert row["from_agent"] == "user"
    assert row["body"] == "Human follow-up"
