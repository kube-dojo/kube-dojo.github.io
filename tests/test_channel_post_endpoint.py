from __future__ import annotations

import importlib
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def _load_local_api():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_channel_post", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_local_api()


def _use_bridge_db(monkeypatch, db_path: Path) -> None:
    bridge_db = importlib.import_module("ai_agent_bridge._db")
    monkeypatch.setenv("AB_DB_PATH", str(db_path))
    monkeypatch.setattr(bridge_db, "DB_PATH", db_path)


def _create_channel(name: str) -> None:
    channels = importlib.import_module("ai_agent_bridge._channels")
    channels.create_channel(name, subscribers=["claude", "gemini", "codex"])


def test_post_endpoint_writes_message(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / ".bridge" / "messages.db"
    _use_bridge_db(monkeypatch, db_path)
    _create_channel("shared")

    status, payload, content_type = local_api.route_post_request(
        tmp_path,
        "/api/channel/shared/post",
        body_bytes=json.dumps({"body": "hello", "from_agent": "user"}).encode(),
        content_type="application/json",
    )

    assert status == 200
    assert "application/json" in content_type
    assert payload["ok"] is True
    assert payload["message_id"]
    assert payload["thread_id"]
    assert payload["ts"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        message = conn.execute(
            "SELECT * FROM channel_messages WHERE message_id = ?",
            (payload["message_id"],),
        ).fetchone()
        assert message is not None
        assert message["channel"] == "shared"
        assert message["from_agent"] == "user"
        assert message["body"] == "hello"
    finally:
        conn.close()


def test_post_endpoint_rejects_invalid_body(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / ".bridge" / "messages.db"
    _use_bridge_db(monkeypatch, db_path)
    _create_channel("shared")

    status, payload, _ = local_api.route_post_request(
        tmp_path,
        "/api/channel/shared/post",
        body_bytes=b"body=%20%20%20",
        content_type="application/x-www-form-urlencoded",
    )

    assert status == 400
    assert payload == {"ok": False, "error": "body_required"}


def test_post_endpoint_rejects_missing_channel(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / ".bridge" / "messages.db"
    _use_bridge_db(monkeypatch, db_path)

    status, payload, _ = local_api.route_post_request(
        tmp_path,
        "/api/channel/no-such-channel/post",
        body_bytes=b"body=hello",
        content_type="application/x-www-form-urlencoded",
    )

    assert status == 404
    assert payload == {"ok": False, "error": "channel_not_found"}
