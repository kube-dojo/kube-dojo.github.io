from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _load_local_api():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_channels_d0", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_local_api()


def _reload_bridge_modules():
    import ai_agent_bridge._channels as bridge_channels
    import ai_agent_bridge._channels_watch as channels_watch
    import ai_agent_bridge._config as bridge_config
    import ai_agent_bridge._db as bridge_db

    importlib.reload(bridge_config)
    importlib.reload(bridge_db)
    importlib.reload(bridge_channels)
    importlib.reload(channels_watch)
    return bridge_db, bridge_channels, channels_watch


def _init_bridge_schema(db_path: Path, bridge_db) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(bridge_db._LEGACY_SCHEMA)
        conn.executescript(bridge_db._CHANNELS_SCHEMA)
        conn.executescript(bridge_db._CHANNEL_EVENTS_SCHEMA)
        conn.execute(
            """
            INSERT INTO channels (name, created_at, description)
            VALUES ('ops', '2026-05-07T12:00:00+00:00', 'Operations')
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_api_channels_reads_bridge_db_without_ab_db_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        with monkeypatch.context() as m:
            m.setenv("AB_REPO_ROOT", str(tmp_path))
            m.delenv("AB_DB_PATH", raising=False)
            bridge_db, _, _ = _reload_bridge_modules()
            _init_bridge_schema(tmp_path / ".bridge" / "messages.db", bridge_db)

            status_code, payload, _ = local_api.route_request(tmp_path, "/api/channels")

            assert status_code == 200
            assert [channel["name"] for channel in payload["channels"]] == ["ops"]
    finally:
        _reload_bridge_modules()
