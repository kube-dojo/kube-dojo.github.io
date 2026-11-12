"""Tests for module-build telemetry store + ingest validation (#1973 P1)."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_telemetry_store():
    module_path = SCRIPTS_DIR / "telemetry_store.py"
    spec = importlib.util.spec_from_file_location("telemetry_store", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


telemetry_store = _load_telemetry_store()


def _load_local_api():
    module_path = SCRIPTS_DIR / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_telemetry", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "module_builds.db"
    monkeypatch.setattr(telemetry_store, "_db_path_override", db_path)
    return db_path


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


def test_schema_init_idempotent(temp_db: Path, repo_root: Path) -> None:
    with closing(telemetry_store._connect(temp_db)) as conn:
        telemetry_store._ensure_schema(conn)
        telemetry_store._ensure_schema(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "module_build_runs" in tables
    assert "module_build_participants" in tables


def _sample_payload(*, run_id: str = "run-1", swarm_used: bool = True) -> dict:
    return {
        "run_id": run_id,
        "recorded_at": "2026-06-14T12:00:00Z",
        "track": "platform/disciplines/core-platform/leadership",
        "slug": "module-1.1-platform-team-building",
        "module_title": "Platform Team Building",
        "branch": "feat/platform-team",
        "commit_sha": "abc123",
        "pr_number": 1973,
        "pr_url": "https://github.com/kube-dojo/kube-dojo.github.io/pull/1973",
        "status": "merged",
        "swarm_used": swarm_used,
        "swarm_label": "thin",
        "swarm_note": "Used bounded reviewers and validation runner.",
        "wall_clock_minutes": 30.5,
        "source": "codex-final",
        "participants": [
            {
                "role": "main",
                "agent": "codex",
                "model": "gpt-5.5",
                "prompt_tokens": 120000,
                "response_tokens": 18000,
                "token_source": "estimated",
            },
            {
                "role": "helper",
                "agent": "gemini",
                "model": "gemini-3.1-pro-preview",
                "total_tokens": 42000,
                "token_source": "estimated",
                "cost_usd_est": 0.12,
            },
        ],
    }


def test_upsert_and_readback(repo_root: Path) -> None:
    telemetry_store.upsert_run(repo_root, _sample_payload())

    runs = telemetry_store.query_runs(
        repo_root,
        track="platform/disciplines/core-platform/leadership",
        slug="module-1.1-platform-team-building",
    )
    assert len(runs) == 1
    run = runs[0]
    assert run["track"] == "platform/disciplines/core-platform/leadership"
    assert run["swarm_used"] is True
    assert run["totals"]["participants"] == 2
    assert run["totals"]["prompt_tokens"] == 120000
    assert run["totals"]["response_tokens"] == 18000
    assert run["totals"]["total_tokens"] == 180000
    assert run["totals"]["cost_usd_est"] == 0.12


def test_upsert_replaces_participants(repo_root: Path) -> None:
    base = _sample_payload(run_id="replace-me", swarm_used=False)
    telemetry_store.upsert_run(
        repo_root,
        {
            **base,
            "participants": [
                {"role": "main", "agent": "codex", "total_tokens": 100, "token_source": "estimated"}
            ],
        },
    )
    telemetry_store.upsert_run(
        repo_root,
        {
            **base,
            "participants": [
                {"role": "main", "agent": "codex", "total_tokens": 250, "token_source": "actual"}
            ],
        },
    )

    runs = telemetry_store.query_runs(repo_root, slug="module-1.1-platform-team-building")
    assert len(runs) == 1
    assert runs[0]["participants"] == [
        {
            "role": "main",
            "agent": "codex",
            "model": None,
            "effort": None,
            "label": None,
            "calls": None,
            "prompt_tokens": None,
            "response_tokens": None,
            "total_tokens": 250,
            "token_source": "actual",
            "cost_usd_est": None,
            "notes": None,
        }
    ]
    with closing(sqlite3.connect(str(telemetry_store.db_path(repo_root)))) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM module_build_participants WHERE run_id = ?",
            ("replace-me",),
        ).fetchone()[0]
    assert count == 1


def test_query_runs_filters(repo_root: Path) -> None:
    for run_id, swarm_used in (("solo", False), ("swarm", True)):
        telemetry_store.upsert_run(
            repo_root,
            {
                "run_id": run_id,
                "track": "platform/disciplines/sre",
                "slug": "filter-demo",
                "swarm_used": swarm_used,
                "swarm_label": "thin" if swarm_used else "none",
                "swarm_note": "swarm used" if swarm_used else "solo run; no swarm used",
                "source": "manual",
            },
        )

    solo_runs = telemetry_store.query_runs(repo_root, slug="filter-demo", swarm_used=False)
    assert len(solo_runs) == 1
    assert solo_runs[0]["run_id"] == "solo"

    track_runs = telemetry_store.query_runs(repo_root, track="platform/disciplines/sre")
    assert len(track_runs) == 2


def test_rollup_math(repo_root: Path) -> None:
    telemetry_store.upsert_run(repo_root, _sample_payload(run_id="swarm", swarm_used=True))
    telemetry_store.upsert_run(
        repo_root,
        {
            "run_id": "solo",
            "track": "k8s/cka",
            "slug": "solo-demo",
            "swarm_used": False,
            "swarm_note": "solo run; no swarm used",
            "source": "manual",
            "participants": [
                {"role": "main", "agent": "cursor", "total_tokens": 1000, "token_source": "estimated"}
            ],
        },
    )

    runs = telemetry_store.query_runs(repo_root, limit=10)
    totals = telemetry_store.rollup(runs)
    assert totals["runs"] == 2
    assert totals["swarm_runs"] == 1
    assert totals["solo_runs"] == 1
    assert totals["participants"] == 3
    assert totals["total_tokens"] == 181000
    assert totals["cost_usd_est"] == 0.12


def test_validate_requires_swarm_note() -> None:
    with pytest.raises(ValueError, match="swarm_note must not be blank"):
        telemetry_store.validate_module_build_ingest(
            {
                "track": "k8s/cka",
                "slug": "solo-demo",
                "swarm_used": False,
                "source": "manual",
            }
        )


def test_validate_rejects_blank_swarm_note() -> None:
    with pytest.raises(ValueError, match="swarm_note must not be blank"):
        telemetry_store.validate_module_build_ingest(
            {
                "track": "k8s/cka",
                "slug": "solo-demo",
                "swarm_used": False,
                "swarm_note": "   ",
                "source": "manual",
            }
        )


def test_validate_requires_source_and_slug() -> None:
    with pytest.raises(ValueError, match="source must not be blank"):
        telemetry_store.validate_module_build_ingest(
            {
                "track": "k8s/cka",
                "slug": "solo-demo",
                "swarm_used": False,
                "swarm_note": "solo run",
                "source": " ",
            }
        )
    with pytest.raises(ValueError, match="slug must not be blank"):
        telemetry_store.validate_module_build_ingest(
            {
                "track": "k8s/cka",
                "slug": " ",
                "swarm_used": False,
                "swarm_note": "solo run",
                "source": "manual",
            }
        )


def test_post_ingest_validator(repo_root: Path) -> None:
    local_api = _load_local_api()

    status, payload, _ = local_api.route_post_request(
        repo_root,
        "/api/telemetry/module-builds",
        body_bytes=json.dumps(_sample_payload()).encode("utf-8"),
        content_type="application/json",
    )
    assert status == 200
    assert payload == {"ok": True, "run_id": "run-1"}

    status, payload, _ = local_api.route_post_request(
        repo_root,
        "/api/telemetry/module-builds",
        body_bytes=json.dumps(
            {
                "track": "k8s/cka",
                "slug": "solo-demo",
                "swarm_used": False,
                "source": "manual",
            }
        ).encode("utf-8"),
        content_type="application/json",
    )
    assert status == 400
    assert payload["error"] == "swarm_note must not be blank"


def _load_runtime_usage():
    module_path = SCRIPTS_DIR / "runtime_usage.py"
    spec = importlib.util.spec_from_file_location("runtime_usage", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime_usage = _load_runtime_usage()


@pytest.fixture
def tool_timings_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "tool_timings.db"
    monkeypatch.setattr(telemetry_store, "_tool_timings_db_path_override", db_path)
    return db_path


def test_tool_timing_percentiles(repo_root: Path, tool_timings_db: Path) -> None:
    for duration_ms in (10, 20, 30, 40, 50):
        telemetry_store.ingest_tool_timing(
            repo_root,
            {"tool_name": "Bash", "duration_ms": duration_ms},
        )

    summary = telemetry_store.tool_timing_summary(repo_root, window="1h")
    bash = next(item for item in summary if item["tool_name"] == "Bash")
    assert bash["count"] == 5
    assert bash["p50_ms"] == 30
    assert bash["p95_ms"] == 48
    assert bash["p99_ms"] == 50
    assert bash["mean_ms"] == 30
    assert bash["failure_count"] == 0

    telemetry_store.ingest_tool_timing(
        repo_root,
        {"tool_name": "Bash", "duration_ms": 100, "failed": True},
    )
    summary = telemetry_store.tool_timing_summary(repo_root, window="1h")
    bash = next(item for item in summary if item["tool_name"] == "Bash")
    assert bash["failure_count"] == 1


def test_tool_timing_window_excludes_old_rows(
    repo_root: Path, tool_timings_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        telemetry_store,
        "_tool_timing_window_start",
        lambda window: ("1h", "2026-06-14T11:00:00Z"),
    )

    telemetry_store.ingest_tool_timing(
        repo_root,
        {"ts": "2026-06-14T11:30:00Z", "tool_name": "Read", "duration_ms": 50},
    )
    telemetry_store.ingest_tool_timing(
        repo_root,
        {"ts": "2026-06-14T10:00:00Z", "tool_name": "Read", "duration_ms": 999},
    )

    summary = telemetry_store.tool_timing_summary(repo_root, window="1h")
    read = next(item for item in summary if item["tool_name"] == "Read")
    assert read["count"] == 1
    assert read["mean_ms"] == 50


def test_tool_timing_empty_window_is_safe(repo_root: Path, tool_timings_db: Path) -> None:
    assert telemetry_store.tool_timing_summary(repo_root, window="5m") == []
    payload = telemetry_store.build_tool_timing_payload(repo_root, window="5m")
    assert payload["window"] == "5m"
    assert payload["tools"] == []


def test_tool_timing_unknown_window_defaults_to_1h(repo_root: Path, tool_timings_db: Path) -> None:
    telemetry_store.ingest_tool_timing(
        repo_root,
        {"tool_name": "Grep", "duration_ms": 12},
    )
    payload = telemetry_store.build_tool_timing_payload(repo_root, window="bad")
    assert payload["window"] == "1h"
    assert len(payload["tools"]) == 1


@pytest.fixture
def dispatch_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    logs = tmp_path / "logs"
    logs.mkdir()
    log_path = logs / "smart_dispatch.jsonl"
    monkeypatch.setattr(runtime_usage, "_dispatch_log_override", log_path)
    return log_path


def _write_dispatch_fixture(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_runtime_usage_aggregation(repo_root: Path, dispatch_log: Path) -> None:
    now = int(time.time())
    _write_dispatch_fixture(
        dispatch_log,
        [
            {
                "ts": now - 3600,
                "agent": "codex",
                "model": "gpt-5.5",
                "task_class": "review",
                "ok": True,
                "response_chars": 100,
                "elapsed_s": 10.0,
                "task_id": "t1",
            },
            {
                "ts": now - 7200,
                "agent": "codex",
                "model": "gpt-5.5",
                "task_class": "draft",
                "ok": False,
                "response_chars": 0,
                "elapsed_s": 20.0,
                "task_id": "t2",
            },
            {
                "ts": now - (9 * 86400),
                "agent": "cursor",
                "model": "auto",
                "task_class": "edit",
                "ok": True,
                "response_chars": 50,
                "elapsed_s": 5.0,
                "task_id": "old",
            },
        ],
    )

    payload = runtime_usage.build_runtime_usage_payload(repo_root, days=7)
    assert payload["totals"]["calls"] == 2
    assert payload["totals"]["failed"] == 1
    assert payload["totals"]["ok"] == 1
    assert payload["totals"]["mean_elapsed_s"] == 15.0

    codex = next(item for item in payload["agents"] if item["agent"] == "codex")
    assert codex["calls"] == 2
    assert codex["failed"] == 1
    assert codex["rate_failed"] == 0.5
    assert codex["by_class"]["review"] == 1
    assert codex["by_class"]["draft"] == 1
    assert codex["models"] == ["gpt-5.5"]


def test_runtime_recent_ordering(repo_root: Path, dispatch_log: Path) -> None:
    _write_dispatch_fixture(
        dispatch_log,
        [
            {"ts": 100, "agent": "a", "model": "m1", "task_class": "edit", "ok": True, "elapsed_s": 1, "task_id": "old"},
            {"ts": 300, "agent": "b", "model": "m2", "task_class": "review", "ok": True, "elapsed_s": 2, "task_id": "new"},
        ],
    )

    payload = runtime_usage.build_runtime_recent_payload(repo_root, limit=10)
    assert [row["task_id"] for row in payload["records"]] == ["new", "old"]


def test_runtime_usage_days_filter(repo_root: Path, dispatch_log: Path) -> None:
    now = int(time.time())
    _write_dispatch_fixture(
        dispatch_log,
        [
            {"ts": now - 86400, "agent": "codex", "ok": True, "response_chars": 1, "elapsed_s": 1, "task_id": "d1"},
            {"ts": now - (3 * 86400), "agent": "codex", "ok": True, "response_chars": 1, "elapsed_s": 1, "task_id": "d2"},
        ],
    )

    one_day = runtime_usage.build_runtime_usage_payload(repo_root, days=1)
    seven_day = runtime_usage.build_runtime_usage_payload(repo_root, days=7)
    assert one_day["totals"]["calls"] == 1
    assert seven_day["totals"]["calls"] == 2
