from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _init_translation_queue_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_key TEXT NOT NULL,
                phase TEXT NOT NULL,
                model TEXT,
                priority INTEGER,
                queue_state TEXT NOT NULL,
                leased_by TEXT,
                lease_id TEXT,
                leased_at INTEGER,
                lease_expires_at INTEGER,
                enqueued_at INTEGER,
                requested_calls INTEGER,
                estimated_usd REAL,
                idempotency_key TEXT
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY,
                module_key TEXT NOT NULL,
                type TEXT NOT NULL,
                lease_id TEXT,
                payload_json TEXT DEFAULT '{}',
                at INTEGER
            );
            """
        )
        conn.execute(
            """
            INSERT INTO jobs (
                module_key, phase, model, priority, queue_state,
                leased_by, lease_id, leased_at, lease_expires_at, enqueued_at,
                requested_calls, estimated_usd, idempotency_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "done/leased",
                "write",
                "gemini",
                10,
                "leased",
                "worker-a",
                "lease-001",
                1,
                999,
                1,
                1,
                0.01,
                "leased-done",
            ),
        )
    finally:
        conn.commit()
        conn.close()


def _mock_quality_board(_repo_root: Path) -> dict[str, list[dict[str, str]]]:
    return {
        "modules": [
            {"module_key": "done/ok-1", "status": "done"},
            {"module_key": "done/ok-2", "status": "done"},
            {"module_key": "done/ok-3", "status": "done"},
            {"module_key": "done/leased", "status": "done"},
            {"module_key": "not_done/needs-review", "status": "needs_review"},
        ]
    }


def test_translation_v2_enqueue_happy_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_api, "build_quality_board", _mock_quality_board)

    repo_root = tmp_path
    db_path = repo_root / ".pipeline" / "translation_v2.db"
    _init_translation_queue_db(db_path)

    status_code, payload, _ = local_api.route_request(
        repo_root,
        "/api/translation/v2/enqueue?from_quality=done",
    )
    assert status_code == 410
    assert payload == {"error": "legacy dispatcher removed"}

    conn = sqlite3.connect(db_path)
    try:
        pending_rows = conn.execute(
            "SELECT module_key FROM jobs WHERE queue_state = 'pending'",
        ).fetchall()
    finally:
        conn.close()
    assert pending_rows == []


def test_translation_v2_enqueue_dry_run_does_not_mutate_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_api, "build_quality_board", _mock_quality_board)

    repo_root = tmp_path
    db_path = repo_root / ".pipeline" / "translation_v2.db"
    _init_translation_queue_db(db_path)

    status_code, payload, _ = local_api.route_request(
        repo_root,
        "/api/translation/v2/enqueue?from_quality=done&dry_run=1",
    )
    assert status_code == 410
    assert payload == {"error": "legacy dispatcher removed"}

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE queue_state='pending'",
        ).fetchone()
    finally:
        conn.close()
    assert rows is not None
    assert rows[0] == 0


def test_translation_v2_enqueue_rejects_invalid_from_quality(tmp_path: Path) -> None:
    status_code, payload, _ = local_api.route_request(
        tmp_path,
        "/api/translation/v2/enqueue?from_quality=invalid",
    )
    assert status_code == 400
    assert payload["error"] == "invalid_from_quality"
