from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import yaml


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test User")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _module_frontmatter(*, lab_id: str | None = None) -> str:
    lines = ["---", 'title: "Example"']
    if lab_id:
        lines.extend(
            [
                "lab:",
                f'  id: "{lab_id}"',
                f'  url: "https://killercoda.com/kubedojo/scenario/{lab_id}"',
                '  duration: "20 min"',
                '  difficulty: "beginner"',
                '  environment: "ubuntu"',
            ]
        )
    lines.extend(["---", "", "body"])
    return "\n".join(lines)


def test_venv_python_for_repo_cap_stops_after_five_levels(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g" / "h"
    repo_root.mkdir(parents=True)

    call_count = {"n": 0}
    original_exists = local_api.Path.exists

    def exists_and_count(self) -> bool:
        if self.name == "python" and self.parent.name == "bin" and self.parent.parent.name == ".venv":
            call_count["n"] += 1
        return original_exists(self)

    monkeypatch.setattr(local_api.Path, "exists", exists_and_count)

    import pytest

    with pytest.raises(FileNotFoundError, match="Could not locate \\.venv/bin/python"):
        local_api._venv_python_for_repo(repo_root)

    assert call_count["n"] == 6


def _seed_quality_module(
    repo: Path,
    rel: str,
    *,
    title: str,
    filler_lines: int = 40,
    quiz: bool = False,
    exercise: bool = False,
    diagram: bool = False,
    citations: bool = True,
) -> None:
    path = repo / "src" / "content" / "docs" / f"{rel}.md"
    lines = ["---", f'title: "{title}"']
    lines.extend(["---", "", "## Overview", ""])
    lines.extend(f"Line {i}" for i in range(filler_lines))
    if diagram:
        lines.extend(["", "```mermaid", "graph TD", "A-->B", "```"])
    if quiz:
        lines.extend(["", "## Quiz", "", "- Question"])
    if exercise:
        lines.extend(["", "## Hands-On Exercise", "", "1. Do thing"])
    if citations:
        lines.extend(["", "## Sources", "", "- [Upstream docs](https://example.com/docs)"])
    _write(path, "\n".join(lines) + "\n")


def _init_v2_db(path: Path, *, module_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE jobs (
              id INTEGER PRIMARY KEY,
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
            INSERT INTO jobs
            (module_key, phase, model, queue_state, requested_calls, estimated_usd, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (module_key, "review", "codex", "completed", 1, 0.01, f"{module_key}-job"),
        )
        conn.execute(
            "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
            (module_key, "review_completed", '{"verdict":"APPROVE"}', 1),
        )
        conn.commit()
    finally:
        conn.close()


def _init_translation_v2_db(path: Path, *, module_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE jobs (
              id INTEGER PRIMARY KEY,
              module_key TEXT NOT NULL,
              phase TEXT NOT NULL,
              model TEXT,
              queue_state TEXT NOT NULL
            );
            CREATE TABLE events (
              id INTEGER PRIMARY KEY,
              module_key TEXT NOT NULL,
              type TEXT NOT NULL,
              payload_json TEXT DEFAULT '{}'
            );
            """
        )
        conn.execute(
            "INSERT INTO jobs (module_key, phase, model, queue_state) VALUES (?, ?, ?, ?)",
            (module_key, "write", "gemini", "completed"),
        )
        conn.execute(
            "INSERT INTO events (module_key, type, payload_json) VALUES (?, ?, ?)",
            (module_key, "translation_verified", '{"status":"synced"}'),
        )
        conn.commit()
    finally:
        conn.close()


def _setup_repo(repo_root: Path) -> tuple[str, Path]:
    _init_repo(repo_root)
    en_path = repo_root / "src/content/docs/prerequisites/zero-to-terminal/module-0.1-alpha.md"
    _write(en_path, _module_frontmatter(lab_id="prereq-0.1-alpha"))
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "add english")
    en_commit = _git(repo_root, "log", "-1", "--format=%H", "--", str(en_path))
    _write(
        repo_root / "src/content/docs/uk/prerequisites/zero-to-terminal/module-0.1-alpha.md",
        "\n".join(
            [
                "---",
                f'en_commit: "{en_commit}"',
                f'en_file: "{en_path.relative_to(repo_root).as_posix()}"',
                "---",
                "",
                "body",
            ]
        ),
    )
    _write(repo_root / ".pipeline/fact-ledgers/prerequisites__zero-to-terminal__module-0.1-alpha.json", "{}")
    _write(
        repo_root / ".pipeline/lab-state.yaml",
        yaml.dump(
            {
                "labs": {
                    "prereq-0.1-alpha": {
                        "phase": "done",
                        "severity": "clean",
                        "module": "prerequisites/zero-to-terminal/module-0.1-alpha",
                    }
                }
            },
            sort_keys=False,
        ),
    )
    module_key = "prerequisites/zero-to-terminal/module-0.1-alpha"
    _init_v2_db(repo_root / ".pipeline/v2.db", module_key=module_key)
    _init_translation_v2_db(repo_root / ".pipeline/translation_v2.db", module_key=module_key)

    # Add pending modules for list verification
    conn_v2 = sqlite3.connect(repo_root / ".pipeline/v2.db")
    conn_v2.execute(
        "INSERT INTO jobs (module_key, phase, queue_state) VALUES (?, ?, ?)",
        ("pending/v2/review", "review", "pending"),
    )
    conn_v2.execute(
        "INSERT INTO jobs (module_key, phase, queue_state) VALUES (?, ?, ?)",
        ("pending/v2/write", "write", "pending"),
    )
    conn_v2.commit()
    conn_v2.close()

    conn_trans = sqlite3.connect(repo_root / ".pipeline/translation_v2.db")
    conn_trans.execute(
        "INSERT INTO jobs (module_key, phase, queue_state) VALUES (?, ?, ?)",
        ("pending/trans/review", "review", "pending"),
    )
    conn_trans.execute(
        "INSERT INTO jobs (module_key, phase, queue_state) VALUES (?, ?, ?)",
        ("pending/trans/write", "write", "pending"),
    )
    conn_trans.commit()
    conn_trans.close()

    return module_key, en_path


def test_build_worktree_status_classifies_source_and_generated_changes(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)
    _write(repo_root / "src/content/docs/prerequisites/zero-to-terminal/module-0.1-alpha.md", _module_frontmatter())
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "initial")

    _write(repo_root / "src/content/docs/prerequisites/zero-to-terminal/module-0.1-alpha.md", "changed\n")
    _write(repo_root / "dist/index.html", "generated\n")

    status = local_api.build_worktree_status(repo_root)

    assert status["ok"] is True
    assert status["dirty"] is True
    assert status["categories"]["source"] == 1
    assert status["categories"]["generated"] == 1


def test_route_request_serves_summary_and_module_endpoints(tmp_path: Path) -> None:
    repo_root = tmp_path
    module_key, _ = _setup_repo(repo_root)

    status_code, summary, content_type = local_api.route_request(repo_root, "/api/status/summary")
    assert status_code == 200
    assert content_type.startswith("application/json")
    # Dashboard hot path skips ZTT and translation freshness for perf.
    assert summary["zero_to_terminal"] is None
    assert summary["translations"] is None
    assert summary["translation_v2_pipeline"] is None
    assert "missing_modules" in summary
    # New per-track rollup is present and covers the known tracks.
    assert isinstance(summary.get("tracks"), list)
    track_slugs = {t["slug"] for t in summary["tracks"]}
    assert {"prerequisites", "k8s"} <= track_slugs
    # V2 pipeline is enriched with per-track groupings.
    assert isinstance(summary["v2_pipeline"].get("per_track"), list)

    status_code, missing_modules, _ = local_api.route_request(repo_root, "/api/missing-modules/status")
    assert status_code == 200
    assert missing_modules["active_exact"]["missing"] > 0
    assert missing_modules["deferred"]["missing_min"] == 3

    status_code, services, _ = local_api.route_request(repo_root, "/api/runtime/services")
    assert status_code == 200
    assert services["stopped"] >= 1
    # New shape: total/running/stopped/stale always present; per-service fields include uptime + stale flag.
    assert services["total"] == services["running"] + services["stopped"] + services["stale"]
    api_entry = next(s for s in services["services"] if s["name"] == "api")
    assert api_entry["status"] == "stopped"
    assert api_entry["uptime_seconds"] is None
    assert api_entry["stale_pid_file"] is False
    assert api_entry["known"] is True

    status_code, module_state, _ = local_api.route_request(
        repo_root, f"/api/module/{module_key}/state"
    )
    assert status_code == 200
    assert module_state["english_exists"] is True
    assert module_state["ukrainian_state"]["status"] == "synced"
    assert module_state["lab"]["state"]["severity"] == "clean"

    status_code, latest, _ = local_api.route_request(
        repo_root, f"/api/module/{module_key}/orchestration/latest"
    )
    assert status_code == 200
    assert latest["v2"]["latest_job"]["phase"] == "review"
    assert latest["translation_v2"]["latest_event"]["type"] == "translation_verified"


def test_route_request_serves_recent_activity_and_navigation_status(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)

    en_index = repo_root / "src/content/docs/ai/index.md"
    module_path = repo_root / "src/content/docs/ai/foundations/module-1.1-what-is-ai.md"
    _write(en_index, "---\ntitle: AI\n---\n")
    _write(module_path, _module_frontmatter())
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "add ai track")

    watch_path = repo_root / ".pipeline" / "issue-watch" / "248.json"
    watch_path.parent.mkdir(parents=True, exist_ok=True)
    watch_path.write_text(
        json.dumps(
            {
                "number": 248,
                "title": "Review batch",
                "url": "https://example.test/issues/248",
                "state": "OPEN",
                "updatedAt": "2026-04-16T09:00:00Z",
                "comments": [
                    {
                        "url": "https://example.test/issues/248#issuecomment-1",
                        "createdAt": "2026-04-16T09:00:00Z",
                        "author": {"login": "user1"},
                        "body": "feedback",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    status_code, recent, _ = local_api.route_request(repo_root, "/api/activity/recent")
    assert status_code == 200
    assert recent["recent_commits"]
    assert recent["recent_commits"][0]["subject"] == "add ai track"
    assert recent["watched_issue"]["number"] == 248

    status_code, navigation, _ = local_api.route_request(repo_root, "/api/navigation/status")
    assert status_code == 200
    ai_track = next(item for item in navigation["top_level_tracks"] if item["slug"] == "ai")
    assert ai_track["english_index_exists"] is True
    assert ai_track["ukrainian_index_exists"] is False
    assert "ai" in navigation["missing_uk_top_level"]
    assert navigation["candidate_stale_count"] >= 1
    assert any(item["index"].endswith("src/content/docs/ai/index.md") for item in navigation["candidate_stale_indexes"])


def test_route_request_serves_delivery_status(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)
    _write(repo_root / "src/content/docs/prerequisites/index.md", "---\ntitle: P\n---\n")
    _write(repo_root / "dist/index.html", "built\n")
    _write(
        repo_root / "scripts/check_site_health.py",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "print('RESULTS: 0 errors, 3 warnings')",
                "print('STATS:   10 files, 4 modules, 20 links checked')",
            ]
        ),
    )

    status_code, payload, _ = local_api.route_request(repo_root, "/api/delivery/status")
    assert status_code == 200
    assert payload["build"]["dist_exists"] is True
    assert payload["build"]["dist_file_count"] >= 1
    assert payload["site_health"]["ok"] is True
    assert payload["site_health"]["warnings"] == 3
    assert payload["site_health"]["stats"]["modules"] == 4


def test_runtime_services_detects_stale_pid_and_discovers_unknown_workers(tmp_path: Path) -> None:
    repo_root = tmp_path
    pids_dir = repo_root / ".pids"
    pids_dir.mkdir()

    # Stale known service: pid file points at a PID that's definitely not alive.
    (pids_dir / "api.pid").write_text("999999\n", encoding="utf-8")
    # Running known service: use our own PID so the existence probe succeeds.
    import os as _os
    (pids_dir / "dev.pid").write_text(f"{_os.getpid()}\n", encoding="utf-8")
    # Discovered (not in RUNTIME_SERVICES) stale worker.
    (pids_dir / "adhoc-worker.pid").write_text("999998\n", encoding="utf-8")

    payload = local_api.build_runtime_services_status(repo_root)

    by_name = {s["name"]: s for s in payload["services"]}
    assert by_name["api"]["status"] == "stale"
    assert by_name["api"]["stale_pid_file"] is True
    assert by_name["dev"]["status"] == "running"
    assert by_name["dev"]["uptime_seconds"] is not None
    assert by_name["dev"]["uptime_seconds"] >= 0
    assert "adhoc-worker" in by_name
    assert by_name["adhoc-worker"]["known"] is False
    assert by_name["adhoc-worker"]["status"] == "stale"

    assert payload["stale"] >= 2
    assert payload["running"] >= 1
    assert payload["total"] == payload["running"] + payload["stopped"] + payload["stale"]


def test_route_request_supports_translation_section_and_missing_db(tmp_path: Path) -> None:
    repo_root = tmp_path
    _setup_repo(repo_root)

    # Fast path (default): freshness is skipped.
    status_code, translation, _ = local_api.route_request(
        repo_root,
        "/api/translation/v2/status?section=prerequisites/zero-to-terminal",
    )
    assert status_code == 200
    assert translation["freshness"] is None
    assert "pending/trans/review" in translation["queue"]["pending_review"]
    assert "pending/trans/write" in translation["queue"]["pending_write"]
    assert isinstance(translation["queue"].get("per_track"), list)

    # Opt in to the full freshness walk.
    status_code, translation_full, _ = local_api.route_request(
        repo_root,
        "/api/translation/v2/status?section=prerequisites/zero-to-terminal&freshness=1",
    )
    assert status_code == 200
    assert translation_full["freshness"]["section"] == "prerequisites/zero-to-terminal"

    status_code, v2, _ = local_api.route_request(repo_root, "/api/pipeline/v2/status")
    assert status_code == 200
    assert "pending/v2/review" in v2["pending_review"]
    assert "pending/v2/write" in v2["pending_write"]

    (repo_root / ".pipeline" / "v2.db").unlink()
    status_code, payload, _ = local_api.route_request(repo_root, "/api/pipeline/v2/status")
    assert status_code == 404
    assert payload["error"] == "missing_db"


def test_route_request_serves_dashboard_and_issue_watch(tmp_path: Path) -> None:
    repo_root = tmp_path
    _setup_repo(repo_root)
    watch_path = repo_root / ".pipeline" / "issue-watch" / "248.json"
    watch_path.parent.mkdir(parents=True, exist_ok=True)
    watch_path.write_text(
        json.dumps(
            {
                "number": 248,
                "title": "Review batch",
                "url": "https://example.test/issues/248",
                "state": "OPEN",
                "updatedAt": "2026-04-16T09:00:00Z",
                "comments": [
                    {
                        "url": "https://example.test/issues/248#issuecomment-1",
                        "createdAt": "2026-04-16T09:00:00Z",
                        "author": {"login": "user1"},
                        "body": "feedback",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    status_code, html, content_type = local_api.route_request(repo_root, "/")
    assert status_code == 200
    assert content_type.startswith("text/html")
    assert "KubeDojo Local Monitor" in html
    assert "quality-summary-counts" in html
    assert "id=\"quality-summary-badge\"" in html
    assert "id=\"quality-board\"" not in html
    assert "qb-search" not in html

    status_code, payload, content_type = local_api.route_request(repo_root, "/api/issue-watch/248")
    assert status_code == 200
    assert content_type.startswith("application/json")
    assert payload["comments_count"] == 1


def test_route_request_serves_quality_board_and_module_detail(tmp_path: Path) -> None:
    module_key, _en_path = _setup_repo(tmp_path)
    repo_root = tmp_path
    status_code, html, content_type = local_api.route_request(repo_root, "/quality")
    assert status_code == 200
    assert content_type.startswith("text/html")
    assert "Quality Board" in html
    assert "<title>Quality Board - KubeDojo Local Monitor</title>" in html

    status_code, html, content_type = local_api.route_request(
        repo_root, f"/quality/{module_key}"
    )
    assert status_code == 200
    assert content_type.startswith("text/html")
    assert "Quality summary" in html
    assert "← Quality Board" in html


def test_quality_board_redirect_points_to_quality(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)

    import http.client
    from threading import Thread

    handler_cls = local_api.make_handler(repo_root)
    server = local_api.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn_http = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn_http.request("GET", "/quality-board")
        resp = conn_http.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 301
        assert resp.getheader("Location") == "/quality"
        assert body.strip() == "/quality"
    finally:
        server.shutdown()
        server.server_close()


def test_module_endpoints_reject_path_traversal(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)

    hostile_keys = [
        "../../../../etc/passwd",
        "../../.agents/skills/platform-expert/SKILL",
        "..%2F..%2Fetc%2Fpasswd",  # URL-encoded traversal
        "foo/../bar",
        ".hidden/module",
        "foo//bar",  # empty middle segment
        "UPPERCASE/module",  # uppercase not allowed in slugs
        "foo/bar$baz",  # disallowed char
    ]

    for hostile in hostile_keys:
        status_state, payload_state, _ = local_api.route_request(
            repo_root, f"/api/module/{hostile}/state"
        )
        assert status_state == 400, (hostile, payload_state)
        assert payload_state["error"] in {"invalid_module_key", "missing_module_key"}

        status_orch, payload_orch, _ = local_api.route_request(
            repo_root, f"/api/module/{hostile}/orchestration/latest"
        )
        assert status_orch == 400, (hostile, payload_orch)
        assert payload_orch["error"] in {"invalid_module_key", "missing_module_key"}


def test_module_endpoints_accept_legitimate_keys(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)
    # Legit slugs should pass validation and reach the handler even if the
    # file doesn't exist (the handler reports english_exists: False).
    status_code, payload, _ = local_api.route_request(
        repo_root, "/api/module/prerequisites/zero-to-terminal/module-0.1-alpha/state"
    )
    assert status_code == 200
    assert payload["english_exists"] is False


def test_route_request_returns_json_error_on_sqlite_schema_drift(tmp_path: Path) -> None:
    """If a v2 DB exists but has a broken schema, the handler must return a
    JSON error envelope via do_GET, not raise into the HTTP server."""
    repo_root = tmp_path
    _init_repo(repo_root)
    v2_db = repo_root / ".pipeline" / "v2.db"
    v2_db.parent.mkdir(parents=True, exist_ok=True)
    # Create a DB with a jobs table missing the queue_state column the reader needs.
    conn = sqlite3.connect(v2_db)
    try:
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    # route_request will raise sqlite3.OperationalError on this broken schema.
    # The handler must wrap that into a 500 JSON envelope.
    import http.client
    from threading import Thread

    handler_cls = local_api.make_handler(repo_root)
    server = local_api.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn_http = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn_http.request("GET", "/api/pipeline/v2/status")
        resp = conn_http.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 500
        payload = json.loads(body)
        assert payload["error"] in {"sqlite_error", "internal_error"}
        assert "path" in payload
    finally:
        server.shutdown()
        server.server_close()


def test_pid_reuse_detection_marks_old_process_as_stale(
    tmp_path: Path, monkeypatch
) -> None:
    """If the live process started long before the pid file was written, the
    pid file is treated as stale (PID was reused by an unrelated process)."""
    import os as _os

    pid_path = tmp_path / "reused.pid"
    pid_path.write_text(f"{_os.getpid()}\n", encoding="utf-8")
    # Stub process age to simulate a long-running process that predates the
    # pid file by much more than the reuse slack.
    monkeypatch.setattr(
        local_api,
        "_process_age_seconds",
        lambda pid: local_api._PID_REUSE_SLACK_SECONDS + 3600.0,
    )
    probe = local_api._inspect_pid_file(pid_path)
    assert probe["status"] == "stale"
    assert probe["stale_pid_file"] is True


def test_pid_fresh_process_reports_running(tmp_path: Path, monkeypatch) -> None:
    import os as _os

    pid_path = tmp_path / "fresh.pid"
    pid_path.write_text(f"{_os.getpid()}\n", encoding="utf-8")
    # Process age within the slack window -> should report running.
    monkeypatch.setattr(local_api, "_process_age_seconds", lambda pid: 5.0)
    probe = local_api._inspect_pid_file(pid_path)
    assert probe["status"] == "running"
    assert probe["stale_pid_file"] is False
    assert probe["uptime_seconds"] == 5.0


def test_pid_reuse_helper_handles_missing_process() -> None:
    # Very high PID that's almost certainly not a live process.
    assert local_api._process_age_seconds(999_999) is None


def test_api_schema_advertises_new_endpoints() -> None:
    schema = local_api.build_api_schema()
    assert schema["version"] == 1
    paths = {e["path"] for e in schema["endpoints"]}
    # Must advertise new endpoints so agents can discover them without
    # reading this file.
    assert "/api/briefing/session" in paths
    assert "/api/schema" in paths
    assert "/api/git/worktrees" in paths
    assert "/api/git/worktree" in paths  # singular still there
    assert "/api/activity/recent" in paths
    assert "/api/navigation/status" in paths
    assert "/api/delivery/status" in paths
    assert "conventions" in schema
    assert "errors" in schema["conventions"]


def test_388_batches_reconciles_held_prs_merged_on_main(tmp_path: Path, monkeypatch) -> None:
    _init_repo(tmp_path)
    _write(
        tmp_path / "logs/388_batch.jsonl",
        "\n".join(
            [
                json.dumps({"event": "pilot_start", "ts": 10, "count": 3, "input": "batch.txt"}),
                json.dumps({"event": "merged", "ts": 20, "pr": 100, "module": "a"}),
                json.dumps(
                    {
                        "event": "merge_held",
                        "ts": 30,
                        "pr": 101,
                        "module": "b",
                        "verdict": "NEEDS_CHANGES",
                    }
                ),
                json.dumps(
                    {
                        "event": "merge_held_nits",
                        "ts": 40,
                        "pr": 102,
                        "module": "c",
                        "verdict": "APPROVE_WITH_NITS",
                    }
                ),
                json.dumps({"event": "pilot_done", "ts": 50}),
            ]
        )
        + "\n",
    )
    _write(tmp_path / "README.md", "merged\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "feat(388): rewrite module b (#101)")
    monkeypatch.setattr(local_api, "_fetch_388_pr_states", lambda: {})

    status_code, payload, _ = local_api.route_request(tmp_path, "/api/388/batches")

    assert status_code == 200
    batch = payload["batches"][0]
    assert batch["event_counts"]["merged"] == 1
    assert batch["event_counts"]["merge_held"] == 1
    assert batch["counts"]["merged"] == 2
    assert batch["counts"]["merge_held"] == 0
    assert batch["counts"]["merge_held_nits"] == 1
    assert batch["held_rollup"] == {
        "total": 2,
        "open": 0,
        "merged": 1,
        "closed": 0,
        "unknown": 1,
        "resolved": 1,
        "resolution_source": "git_log",
    }


def test_388_batch_detail_uses_github_pr_state_when_available(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "logs/388_batch.jsonl",
        "\n".join(
            [
                json.dumps({"event": "pilot_start", "ts": 10, "count": 2, "input": "batch.txt"}),
                json.dumps({"event": "merge_held", "ts": 20, "pr": 201, "module": "a"}),
                json.dumps({"event": "merge_held_nits", "ts": 30, "pr": 202, "module": "b"}),
                json.dumps({"event": "pilot_done", "ts": 40}),
            ]
        )
        + "\n",
    )
    monkeypatch.setattr(
        local_api,
        "_fetch_388_pr_states",
        lambda: {
            201: {"state": "MERGED", "merged_at": "2026-05-03T18:00:00Z", "url": "https://x/201"},
            202: {"state": "CLOSED", "merged_at": None, "url": "https://x/202"},
        },
    )

    status_code, payload, _ = local_api.route_request(tmp_path, "/api/388/batch/388_batch")

    assert status_code == 200
    assert payload["counts"]["merged"] == 1
    assert payload["counts"]["merge_held"] == 0
    assert payload["counts"]["merge_held_nits"] == 0
    assert payload["event_counts"]["merge_held"] == 1
    assert payload["event_counts"]["merge_held_nits"] == 1
    assert payload["held_rollup"]["resolved"] == 2
    assert payload["held_rollup"]["resolution_source"] == "github"
    assert [pr["resolution_status"] for pr in payload["held_prs"]] == ["merged", "closed"]


def test_weak_etag_stable_for_identical_bytes() -> None:
    a = local_api._weak_etag(b"hello world")
    b = local_api._weak_etag(b"hello world")
    c = local_api._weak_etag(b"hello worlds")
    assert a == b
    assert a != c
    assert a.startswith('W/"sha256:')


def test_match_etag_handles_list_weak_and_star() -> None:
    etag = 'W/"sha256:abc123"'
    assert local_api._match_etag(etag, etag) is True
    assert local_api._match_etag("*", etag) is True
    assert local_api._match_etag('W/"sha256:nope"', etag) is False
    # Strong/weak equivalence for comparison.
    assert local_api._match_etag('"sha256:abc123"', etag) is True
    # Comma-separated list.
    assert local_api._match_etag(f'"other", {etag}, "other2"', etag) is True
    assert local_api._match_etag("", etag) is False


def test_normalized_cache_key_is_order_invariant() -> None:
    k1 = local_api._normalized_cache_key("/x", {"a": ["1"], "b": ["2"]})
    k2 = local_api._normalized_cache_key("/x", {"b": ["2"], "a": ["1"]})
    assert k1 == k2
    assert local_api._normalized_cache_key("/x", {}) == "/x"


def test_sqlite_version_key_changes_on_write(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    # Absent DB has an absent sentinel.
    absent = local_api._sqlite_version_key(db_path)
    assert absent[0] == "absent"
    # Create + insert = new version key.
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()
    v1 = local_api._sqlite_version_key(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    v2 = local_api._sqlite_version_key(db_path)
    assert v1 != v2
    assert v1[0] != "absent"


def test_cached_response_reuses_entry_until_version_bump(tmp_path: Path) -> None:
    # Use a unique key so test isolation holds across tests.
    key = f"/test/cache/{id(tmp_path)}"
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return 200, {"hits": calls["n"]}, "application/json; charset=utf-8"

    version_state = {"v": 1}

    def version():
        return ("v", version_state["v"])

    code_a, body_a, _ct, etag_a = local_api.cached_response(
        key, ttl_seconds=60, version_fn=version, builder=builder
    )
    assert code_a == 200
    assert calls["n"] == 1

    # Second call within TTL + same version -> cached.
    code_b, body_b, _ct, etag_b = local_api.cached_response(
        key, ttl_seconds=60, version_fn=version, builder=builder
    )
    assert calls["n"] == 1
    assert body_b is body_a or body_b == body_a
    assert etag_b == etag_a

    # Version bump -> rebuild.
    version_state["v"] = 2
    code_c, body_c, _ct, etag_c = local_api.cached_response(
        key, ttl_seconds=60, version_fn=version, builder=builder
    )
    assert calls["n"] == 2
    assert etag_c != etag_a


def test_cached_response_does_not_cache_errors(tmp_path: Path) -> None:
    key = f"/test/errors/{id(tmp_path)}"
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return 500, {"error": "boom"}, "application/json; charset=utf-8"

    code, _body, _ct, _etag = local_api.cached_response(
        key, ttl_seconds=60, version_fn=lambda: ("v",), builder=builder
    )
    assert code == 500
    # Second call should also go through the builder (no poisoning).
    local_api.cached_response(key, ttl_seconds=60, version_fn=lambda: ("v",), builder=builder)
    assert calls["n"] == 2


def test_build_worktrees_list_returns_primary(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)
    _write(repo_root / "README.md", "hi\n")
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "initial")
    result = local_api.build_worktrees_list(repo_root)
    assert result["ok"] is True
    assert result["count"] >= 1
    paths = [w["path"] for w in result["worktrees"]]
    assert str(repo_root) in paths


def test_session_briefing_serves_compact_snapshot(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    # Write a STATUS.md that the briefing will parse.
    _write(
        tmp_path / "STATUS.md",
        "# status\n\n## TODO\n\n- [ ] finish alpha\n- [ ] finish beta\n\n"
        "## Blockers\n\n- slow CI\n",
    )
    briefing = local_api.build_session_briefing(tmp_path)
    assert set(briefing).issuperset(
        {"snapshot", "workspace", "services", "pipelines", "focus", "blockers", "next_reads"}
    )
    assert briefing["focus"][:2] == ["finish alpha", "finish beta"]
    assert briefing["blockers"] == ["slow CI"]

    # Compact drops next_reads, links, and the worktrees list.
    compact = local_api._compact_briefing(briefing)
    assert "next_reads" not in compact
    assert "links" not in compact
    assert "worktrees" not in compact["workspace"]
    assert compact["workspace"]["worktrees_total"] == briefing["workspace"]["worktrees_total"]


def test_serve_request_sets_etag_and_matches_on_replay(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    _write(
        tmp_path / "STATUS.md",
        "# status\n\n## TODO\n\n- [ ] task one\n",
    )
    code1, body1, _ct1, etag1 = local_api.serve_request(tmp_path, "/api/schema")
    assert code1 == 200
    assert etag1.startswith('W/"sha256:')
    # Replay should return the same bytes + same etag (cache hit).
    code2, body2, _ct2, etag2 = local_api.serve_request(tmp_path, "/api/schema")
    assert code2 == 200
    assert etag2 == etag1
    assert body1 == body2
    # And If-None-Match match semantics should accept it.
    assert local_api._match_etag(etag1, etag2)


def test_background_snapshot_exposes_freshness_metadata() -> None:
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return {"value": calls["n"]}

    snap = local_api.BackgroundSnapshot(
        key="test-snap-1",
        interval_seconds=60.0,
        builder=builder,
    )
    # Before any refresh runs.
    data, meta = snap.get()
    assert data is None
    assert meta["freshness_state"] == "refreshing"

    snap.refresh_blocking()
    data, meta = snap.get()
    assert data == {"value": 1}
    assert meta["freshness_state"] == "fresh"
    assert meta["refresh_error"] is None
    assert meta["refresh_duration_ms"] is not None
    assert meta["refresh_in_flight"] is False


def test_sqlite_version_key_detects_wal_only_write(tmp_path: Path) -> None:
    """Regression: PR #259 round 1 used PRAGMA data_version which is a
    per-connection counter and therefore unreliable across fresh
    connections. Version key must change on a WAL-mode write."""
    db_path = tmp_path / "wal.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()
    local_api._close_all_sqlite_version_connections()
    v1 = local_api._sqlite_version_key(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()
    v2 = local_api._sqlite_version_key(db_path)

    assert v1 != v2, "WAL-mode write must change the version key"


def test_sqlite_version_key_detects_same_size_write(tmp_path: Path) -> None:
    """Codex round-2 blocker: (mtime, size) missed same-size writes.
    The fix uses PRAGMA data_version on a persistent connection, which
    increments on every commit regardless of file-level changes.

    Write, then UPDATE a row in place so the file size is unchanged.
    Without a reliable detector, the version key would collide.
    """
    db_path = tmp_path / "same_size.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    local_api._close_all_sqlite_version_connections()
    size_before = db_path.stat().st_size
    v1 = local_api._sqlite_version_key(db_path)

    # In-place update: row count and stored int width are both unchanged.
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE t SET x = 2")
    conn.commit()
    conn.close()
    size_after = db_path.stat().st_size
    v2 = local_api._sqlite_version_key(db_path)

    # The whole point of this test is the "same size" case; prove it.
    assert size_before == size_after, (
        f"test presumption broken: size changed {size_before}->{size_after}"
    )
    assert v1 != v2, "in-place UPDATE must change the version key"


def test_sqlite_version_key_detects_db_replacement(tmp_path: Path) -> None:
    """Non-blocking polish from Codex round-3: if the DB file is
    REPLACED (different inode) rather than modified in place, the
    cached persistent connection would otherwise keep reporting the
    old counter until TTL rebuilt the cache. The inode check drops
    the stale handle so the first call after replacement gives a
    fresh, correct key.
    """
    db_path = tmp_path / "rotated.db"
    other = tmp_path / "other.db"

    # DB A — one row, version V_a.
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    local_api._close_all_sqlite_version_connections()
    v_a = local_api._sqlite_version_key(db_path)

    # DB B — different physical file, then rename over db_path.
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE t (x INTEGER, y TEXT)")
    conn.execute("INSERT INTO t VALUES (42, 'b')")
    conn.execute("INSERT INTO t VALUES (43, 'bb')")
    conn.commit()
    conn.close()
    # Rename replaces the inode at db_path without going through
    # sqlite's own rewrite path.
    other.replace(db_path)

    v_b = local_api._sqlite_version_key(db_path)
    assert v_a != v_b, "DB replacement must change the version key"


def test_sqlite_version_key_stable_without_writes(tmp_path: Path) -> None:
    """Repeated calls with no intervening write must return the same key."""
    db_path = tmp_path / "stable.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    local_api._close_all_sqlite_version_connections()
    v1 = local_api._sqlite_version_key(db_path)
    v2 = local_api._sqlite_version_key(db_path)
    v3 = local_api._sqlite_version_key(db_path)
    assert v1 == v2 == v3


def test_cache_keyed_by_repo_root(tmp_path: Path) -> None:
    """Regression: PR #259 round 1 used process-global caches that
    ignored repo_root. Two repos hitting the same URL path would share
    a cache entry.
    """
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    key_a = local_api._normalized_cache_key("/api/schema", {}, repo_root=repo_a)
    key_b = local_api._normalized_cache_key("/api/schema", {}, repo_root=repo_b)
    assert key_a != key_b
    # With no repo_root the key falls back to path only (backward-compat).
    assert local_api._normalized_cache_key("/api/schema", {}) == "/api/schema"


def test_status_md_cache_isolates_per_path(tmp_path: Path) -> None:
    """Regression: STATUS.md cache was process-global, one entry.
    Different repos' STATUS.md files must resolve independently.
    """
    status_a = tmp_path / "a" / "STATUS.md"
    status_b = tmp_path / "b" / "STATUS.md"
    status_a.parent.mkdir()
    status_b.parent.mkdir()
    status_a.write_text(
        "# a\n\n## TODO\n\n- [ ] task from A\n", encoding="utf-8"
    )
    status_b.write_text(
        "# b\n\n## TODO\n\n- [ ] task from B\n", encoding="utf-8"
    )
    data_a = local_api._parse_status_md(status_a)
    data_b = local_api._parse_status_md(status_b)
    assert data_a["focus"] == ["task from A"]
    assert data_b["focus"] == ["task from B"]


def test_background_snapshot_serializes_concurrent_builds() -> None:
    """Regression: the "single in-flight" guarantee required a build
    lock. refresh_blocking() called from one thread while the daemon
    thread also tries to refresh must not produce overlapping builders.

    Deterministic — no sleeps. An instrumented build lock signals when
    the second caller reaches lock contention, so the test proves that
    B actually attempted entry before A released (not just that B
    happened not to finish first).
    """
    import threading

    class _InstrumentedLock:
        """Substitute for ``BackgroundSnapshot._build_lock`` that records
        a ``waiter_entered`` event the second time ``acquire`` is called
        while the lock is held, so the test can synchronize on ``B is
        now waiting`` without sleeping."""

        def __init__(self) -> None:
            self._inner = threading.Lock()
            self.waiter_entered = threading.Event()
            self._acquire_attempts = 0
            self._counter_lock = threading.Lock()

        def acquire(self, timeout: float = -1.0) -> bool:
            with self._counter_lock:
                self._acquire_attempts += 1
                attempt = self._acquire_attempts
            if attempt >= 2 and self._inner.locked():
                # Signal BEFORE the blocking acquire so the driver can
                # release A after confirming B has reached contention.
                self.waiter_entered.set()
            if timeout < 0:
                self._inner.acquire()
                return True
            return self._inner.acquire(timeout=timeout)

        def release(self) -> None:
            self._inner.release()

    running_now = {"n": 0}
    max_concurrent = {"n": 0}
    release_builder = threading.Event()
    in_builder = threading.Event()
    counter_lock = threading.Lock()

    def slow_builder():
        with counter_lock:
            running_now["n"] += 1
            max_concurrent["n"] = max(max_concurrent["n"], running_now["n"])
        in_builder.set()
        # Park inside the builder until the test explicitly releases.
        release_builder.wait(timeout=5.0)
        with counter_lock:
            running_now["n"] -= 1
        return {"ok": True}

    snap = local_api.BackgroundSnapshot(
        key="concurrency-test",
        interval_seconds=60.0,
        builder=slow_builder,
    )
    instrumented = _InstrumentedLock()
    snap._build_lock = instrumented  # type: ignore[assignment]

    # Thread A enters the builder and parks there.
    t_a = threading.Thread(target=snap.refresh_blocking)
    t_a.start()
    assert in_builder.wait(timeout=3.0), "builder A never entered"

    # Thread B also attempts to acquire the build lock. It must block.
    t_b = threading.Thread(target=snap.refresh_blocking)
    t_b.start()
    assert instrumented.waiter_entered.wait(timeout=3.0), (
        "B did not reach lock contention before A released — test invalid"
    )

    # Release A; B proceeds into the builder sequentially.
    release_builder.set()
    t_a.join(timeout=3.0)
    t_b.join(timeout=3.0)
    assert not t_a.is_alive() and not t_b.is_alive()
    assert max_concurrent["n"] == 1, "two builders ran concurrently"


def test_refresh_blocking_honors_timeout() -> None:
    """refresh_blocking(timeout=...) must return False if the build
    lock cannot be acquired before the timeout elapses."""
    import threading

    release = threading.Event()
    in_builder = threading.Event()

    def slow_builder():
        in_builder.set()
        release.wait(timeout=3.0)
        return {"ok": True}

    snap = local_api.BackgroundSnapshot(
        key="timeout-test",
        interval_seconds=60.0,
        builder=slow_builder,
    )
    # Thread A holds the build lock.
    t_a = threading.Thread(target=snap.refresh_blocking)
    t_a.start()
    assert in_builder.wait(timeout=3.0)

    # Caller B asks with a small timeout. Lock is held; return False fast.
    ok = snap.refresh_blocking(timeout=0.05)
    assert ok is False, "timeout path must return False"

    release.set()
    t_a.join(timeout=3.0)
    # Once A releases, a follow-up call succeeds.
    assert snap.refresh_blocking(timeout=3.0) is True


def test_background_snapshot_reports_degraded_on_builder_error() -> None:
    def builder():
        raise RuntimeError("boom")

    snap = local_api.BackgroundSnapshot(
        key="test-snap-2",
        interval_seconds=60.0,
        builder=builder,
    )
    snap.refresh_blocking()
    data, meta = snap.get()
    assert data is None
    assert meta["freshness_state"] == "degraded"
    assert "RuntimeError: boom" in (meta["refresh_error"] or "")


def test_pipeline_leases_lists_active_only(tmp_path: Path) -> None:
    """Codex round-1 bug: we were using ms; the control-plane stores
    Unix epoch SECONDS. Everything below is in seconds."""
    module_key, _ = _setup_repo(tmp_path)
    now_s = 1_700_000_000  # Realistic seconds-since-epoch value.

    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (module_key, "write", "leased", "codex", "lease-a", now_s - 1, now_s + 60),
    )
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("other/module-stale", "write", "leased", "claude", "lease-b",
         now_s - 10_000, now_s - 1),
    )
    conn.commit()
    conn.close()

    result = local_api.build_pipeline_leases(tmp_path, now_seconds=now_s)
    assert result["exists"] is True
    assert result["count"] == 1
    assert result["active"][0]["lease_id"] == "lease-a"
    assert result["active"][0]["seconds_to_expiry"] == 60


def test_pipeline_leases_returns_empty_when_db_missing(tmp_path: Path) -> None:
    result = local_api.build_pipeline_leases(tmp_path)
    assert result["exists"] is False
    assert result["count"] == 0
    assert result["active"] == []


def test_module_lease_reports_held_vs_free(tmp_path: Path) -> None:
    module_key, _ = _setup_repo(tmp_path)
    now_s = 1_700_000_000
    r = local_api.build_module_lease(tmp_path, module_key, now_seconds=now_s)
    assert r["held"] is False

    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (module_key, "review", "leased", "gemini", "lease-x", now_s - 1, now_s + 120),
    )
    conn.commit()
    conn.close()
    r = local_api.build_module_lease(tmp_path, module_key, now_seconds=now_s)
    assert r["held"] is True
    assert r["lease"]["leased_by"] == "gemini"
    assert r["lease"]["seconds_to_expiry"] == 120


def test_pipeline_events_filters_and_limits(tmp_path: Path) -> None:
    module_key, _ = _setup_repo(tmp_path)
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    for i in range(5):
        conn.execute(
            "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
            (module_key, f"type_{i}", f'{{"i":{i}}}', 1000 + i),
        )
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("other/module", "x", "{}", 9999),
    )
    conn.commit()
    conn.close()

    scoped = local_api.build_pipeline_events(tmp_path, module_key=module_key, since_seconds=None, limit=3)
    assert scoped["count"] == 3
    assert all(e["module_key"] == module_key for e in scoped["events"])
    ids = [e["id"] for e in scoped["events"]]
    assert ids == sorted(ids, reverse=True)
    assert isinstance(scoped["events"][0]["payload_json"], dict)

    windowed = local_api.build_pipeline_events(tmp_path, module_key=module_key, since_seconds=1002, limit=10)
    ats = [e["at"] for e in windowed["events"]]
    assert all(a >= 1002 for a in ats)


def test_pipeline_stuck_catches_expired_and_silent_jobs_in_seconds(tmp_path: Path) -> None:
    """Bug-fix regression: Codex caught the ms-vs-seconds mismatch.
    Threshold is now honored in seconds against seconds-valued
    timestamps from the real control-plane."""
    module_key, _ = _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Expired lease -> stuck_leased
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("stuck/one", "write", "leased", "codex", "lex-1",
         now_s - 1_000, now_s - 10),
    )
    # In-flight with no recent event for current attempt -> stuck_in_state
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, leased_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("stuck/silent", "review", "running", "claude", "lex-silent", now_s - 10_000),
    )
    conn.execute(
        "INSERT INTO events (module_key, type, lease_id, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("stuck/silent", "attempt_started", "lex-silent", "{}", now_s - 10_000),
    )
    # Fresh in-flight -> not stuck (has recent event for its lease)
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, leased_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("fresh/one", "review", "running", "claude", "lex-fresh", now_s),
    )
    conn.execute(
        "INSERT INTO events (module_key, type, lease_id, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("fresh/one", "attempt_started", "lex-fresh", "{}", now_s - 10),
    )
    conn.commit()
    conn.close()

    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    stuck_leased_keys = {j["module_key"] for j in r["stuck_leased"]}
    stuck_in_state_keys = {j["module_key"] for j in r["stuck_in_state"]}
    assert "stuck/one" in stuck_leased_keys
    assert "stuck/silent" in stuck_in_state_keys
    assert "fresh/one" not in stuck_in_state_keys


def test_pipeline_stuck_surfaces_unresolved_dead_letters(tmp_path: Path) -> None:
    """Codex round-3 bug: briefing's ``pipeline_dead_letter`` reason
    in top_modules pointed at /api/pipeline/v2/stuck, but that
    endpoint only returned stuck_leased + stuck_in_state. The drill-
    down was half-wired. Now /api/pipeline/v2/stuck also returns a
    ``dead_lettered`` section derived from events."""
    _setup_repo(tmp_path)
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Unresolved dead-letter: module_dead_lettered with no recovery.
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("still/dead", "module_dead_lettered", '{"reason":"quality"}', 1),
    )
    # Resolved: dead-lettered then recovered — must NOT appear.
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("was/dead", "module_dead_lettered", "{}", 2),
    )
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("was/dead", "dead_letter_recovered", "{}", 3),
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=100)
    dead_keys = {row["module_key"] for row in r["dead_lettered"]}
    assert "still/dead" in dead_keys
    assert "was/dead" not in dead_keys
    assert r["dead_lettered_count"] == len(r["dead_lettered"])


def test_pipeline_stuck_reraises_unrelated_module_not_found(
    tmp_path: Path, monkeypatch
) -> None:
    """Codex round-6 bug: ``except ModuleNotFoundError`` also caught
    transitive missing-import errors from inside pipeline_v2.cli
    (broken install, missing dep). A dead-letter endpoint that
    quietly returns ``[]`` on a broken install would hide modules
    needing human triage. Narrowed by ``exc.name`` so only
    "pipeline_v2[.cli] not installed" is tolerated; everything else
    must propagate."""
    _setup_repo(tmp_path)
    # Plant a real dead-letter event so the import branch is reached.
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("dead/one", "module_dead_lettered", "{}", 1),
    )
    conn.commit()
    conn.close()

    import builtins as _builtins
    real_import = _builtins.__import__

    def _broken_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pipeline_v2.cli" or (name == "pipeline_v2" and fromlist and "cli" in fromlist):
            raise ModuleNotFoundError(
                "No module named 'some_unrelated_dep'",
                name="some_unrelated_dep",
            )
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(_builtins, "__import__", _broken_import)

    import pytest as _pytest
    with _pytest.raises(ModuleNotFoundError) as exc_info:
        local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=100)
    assert exc_info.value.name == "some_unrelated_dep"


def test_pipeline_stuck_tolerates_missing_pipeline_v2(
    tmp_path: Path, monkeypatch
) -> None:
    """The flip side of the narrowing: when pipeline_v2 itself is
    genuinely not installed, the endpoint still returns gracefully
    with an empty dead-letter list (the rest of the stuck payload is
    unaffected)."""
    _setup_repo(tmp_path)
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("dead/two", "module_dead_lettered", "{}", 1),
    )
    conn.commit()
    conn.close()

    import builtins as _builtins
    import sys
    real_import = _builtins.__import__

    def _missing_top_level(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pipeline_v2.cli" or (name == "pipeline_v2" and fromlist and "cli" in fromlist):
            raise ModuleNotFoundError(
                "No module named 'pipeline_v2'",
                name="pipeline_v2",
            )
        return real_import(name, globals, locals, fromlist, level)

    # Remove any cached import so the __import__ hook is actually hit.
    for k in list(sys.modules):
        if k.startswith("pipeline_v2"):
            monkeypatch.delitem(sys.modules, k, raising=False)
    monkeypatch.setattr(_builtins, "__import__", _missing_top_level)

    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=100)
    assert r["dead_lettered"] == []
    assert r["dead_lettered_count"] == 0
    assert r["exists"] is True  # rest of the endpoint still works


def test_pipeline_stuck_dead_letter_honors_at_timestamp_not_just_id(
    tmp_path: Path,
) -> None:
    """Codex round-4 bug: the reducer walked events in id-ASC order
    (sqlite default). If events are inserted with out-of-order ``at``
    timestamps (backfill, clock drift, multi-writer skew), a later-
    id-but-earlier-at dead-letter could be wrongly cancelled by an
    earlier-id-but-later-at recovery. Source of truth in
    pipeline_v2.cli._current_dead_letter_rows sorts by (at, id); this
    endpoint must agree.

    Scenario: module was recovered at at=1 (id=1) then dead-lettered
    AGAIN at at=10 (id=2). id-ordered walk would see recovery first,
    then dead-letter → unresolved (correct). But the reverse order
    (id=1 dead-letter at=10, id=2 recovery at=1) should NOT cancel
    the dead-letter because the recovery is chronologically earlier.
    """
    _setup_repo(tmp_path)
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # id=1 is a dead-letter at at=10.
    conn.execute(
        "INSERT INTO events (id, module_key, type, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        (1001, "backfilled/dead", "module_dead_lettered", "{}", 10),
    )
    # id=2 is a recovery at at=1 — EARLIER than the dead-letter.
    # In a (at, id)-sorted walk the recovery happens first and the
    # dead-letter remains unresolved.
    conn.execute(
        "INSERT INTO events (id, module_key, type, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        (1002, "backfilled/dead", "dead_letter_recovered", "{}", 1),
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=100)
    dead_keys = {row["module_key"] for row in r["dead_lettered"]}
    assert "backfilled/dead" in dead_keys


def test_pipeline_stuck_correlates_events_by_lease_id(tmp_path: Path) -> None:
    """Codex round-4 bug: correlating events by module_key alone let
    a fresh event from an EARLIER lease mask a hung current lease."""
    _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Current (hung) lease: running, no event for THIS lease_id.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, leased_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("rolled/over", "write", "running", "claude", "current-lease", now_s - 10_000),
    )
    # Old event from a PREVIOUS lease for the same module — should NOT
    # make the current attempt look healthy.
    conn.execute(
        "INSERT INTO events (module_key, type, lease_id, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("rolled/over", "attempt_started", "previous-lease", "{}", now_s - 1),
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    assert any(j["module_key"] == "rolled/over" for j in r["stuck_in_state"])


# ---- Phase D: stale-worker roll-up in /api/pipeline/v2/stuck ----


def test_stale_workers_groups_active_leases_by_worker(tmp_path: Path) -> None:
    """A worker holding multiple non-expired leases with no recent
    events on ANY of them shows up once as a zombie, with every module
    key it currently holds listed."""
    _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Two active (non-expired) leases for the same worker, both silent.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/cka/mod-a", "review", "running", "claude", "lex-a",
         now_s - 5000, now_s + 3600),
    )
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/cka/mod-b", "review", "running", "claude", "lex-b",
         now_s - 5000, now_s + 3600),
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    assert r["stale_workers_count"] == 1
    worker = r["stale_workers"][0]
    assert worker["leased_by"] == "claude"
    assert worker["active_lease_count"] == 2
    assert set(worker["module_keys"]) == {"k8s/cka/mod-a", "k8s/cka/mod-b"}
    # Never emitted any event -> idle_seconds = None.
    assert worker["idle_seconds"] is None


def test_stale_workers_uses_latest_event_across_leases(tmp_path: Path) -> None:
    """A heartbeat on ONE of the worker's active leases must prevent the
    worker from being flagged stale (idle_seconds < threshold)."""
    _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/mod-a", "review", "running", "codex", "lex-a",
         now_s - 5000, now_s + 3600),
    )
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/mod-b", "review", "running", "codex", "lex-b",
         now_s - 5000, now_s + 3600),
    )
    # Recent event on lex-b keeps the worker alive.
    conn.execute(
        "INSERT INTO events (module_key, type, lease_id, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("k8s/mod-b", "attempt_progress", "lex-b", "{}", now_s - 10),
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    assert r["stale_workers_count"] == 0


def test_stale_workers_excludes_expired_leases(tmp_path: Path) -> None:
    """Expired leases belong to ``stuck_leased``, not ``stale_workers``
    — a worker whose only lease has already expired isn't a zombie, it's
    just gone. Bucketing both makes the count meaningless."""
    _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/expired", "review", "running", "gemini", "lex-exp",
         now_s - 5000, now_s - 1),  # expired 1s ago
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    assert r["stale_workers_count"] == 0
    # And the expired lease still appears in stuck_leased.
    assert any(j["module_key"] == "k8s/expired" for j in r["stuck_leased"])


def test_stale_workers_ties_break_by_leased_by(tmp_path: Path) -> None:
    """Codex Phase D review: ties on idle_seconds must break
    deterministically (here: ``leased_by`` ASC) so a polling operator
    doesn't see the order flip between otherwise-identical calls."""
    _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Two workers, same idle profile (never emitted, same leased_at).
    conn.executemany(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("k8s/a", "review", "leased", "worker-z", "lex-z",
             now_s - 5000, now_s + 3600),
            ("k8s/b", "review", "leased", "worker-a", "lex-a",
             now_s - 5000, now_s + 3600),
        ],
    )
    conn.commit()
    conn.close()
    r1 = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    r2 = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    assert [w["leased_by"] for w in r1["stale_workers"]] == ["worker-a", "worker-z"]
    assert [w["leased_by"] for w in r1["stale_workers"]] == [
        w["leased_by"] for w in r2["stale_workers"]
    ]


def test_stale_workers_sorts_never_emitted_before_finite_idle(tmp_path: Path) -> None:
    """A worker that has never emitted an event is strictly more
    concerning than one that emitted recently-ish. The former must sort
    above the latter."""
    _setup_repo(tmp_path)
    now_s = 10_000
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Worker A: long-idle but has emitted.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/a", "review", "running", "old-worker", "lex-a",
         now_s - 9000, now_s + 3600),
    )
    conn.execute(
        "INSERT INTO events (module_key, type, lease_id, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("k8s/a", "attempt_started", "lex-a", "{}", now_s - 500),
    )
    # Worker B: never emitted at all.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("k8s/b", "review", "running", "zombie-worker", "lex-b",
         now_s - 9000, now_s + 3600),
    )
    conn.commit()
    conn.close()
    r = local_api.build_pipeline_stuck(tmp_path, threshold_seconds=60, now_seconds=now_s)
    assert r["stale_workers_count"] == 2
    # Never-emitted worker comes first.
    assert r["stale_workers"][0]["leased_by"] == "zombie-worker"
    assert r["stale_workers"][0]["idle_seconds"] is None
    assert r["stale_workers"][1]["leased_by"] == "old-worker"
    assert r["stale_workers"][1]["idle_seconds"] == 500


def test_reviews_index_and_single(tmp_path: Path) -> None:
    reviews_dir = tmp_path / ".pipeline" / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "cka__module-2.8-scheduler.md").write_text(
        "# Review\n\n## 2026-01-02 — `REVIEW` — `APPROVE`\n\n**Checks**: 4/4 passed (PRES NO_EMOJI K8S_API FACT_CHECK)\n",
        encoding="utf-8",
    )
    (reviews_dir / "ztt__module-0.1.md").write_text(
        "# Review\n\n## 2026-01-03 — `REVIEW` — `APPROVE`\n\n**Checks**: 4/4 passed (PRES NO_EMOJI K8S_API FACT_CHECK)\n\n**Feedback**:\n> unverified: could not confirm version claim\n",
        encoding="utf-8",
    )
    (reviews_dir / "bad__fact.md").write_text(
        "# Review\n\n## 2026-01-04 — `REVIEW` — `REJECT`\n\n**Checks**: 3/4 passed (PRES NO_EMOJI K8S_API) | **Failed**: FACT_CHECK\n\n**Failed check evidence**:\n- **FACT_CHECK**: API version claim is wrong\n",
        encoding="utf-8",
    )

    index = local_api.build_reviews_index(tmp_path)
    assert index["exists"] is True
    assert index["count"] == 3
    statuses = {r["module_key"]: r["fact_check_status"] for r in index["reviews"]}
    keys = set(statuses)
    assert "cka/module-2.8-scheduler" in keys
    assert "ztt/module-0.1" in keys
    assert statuses["cka/module-2.8-scheduler"] == "verified"
    assert statuses["ztt/module-0.1"] == "unverified"
    assert statuses["bad/fact"] == "failed"
    assert local_api.build_reviews_index(tmp_path, fact_check_status="unverified")["reviews"][0]["module_key"] == "ztt/module-0.1"

    single = local_api.build_module_reviews(tmp_path, "cka/module-2.8-scheduler")
    assert single is not None
    assert "FACT_CHECK" in single["body"]
    assert single["truncated"] is False
    assert single["fact_check_status"] == "verified"

    unverified = local_api.build_module_reviews(tmp_path, "ztt/module-0.1")
    assert unverified is not None
    assert unverified["fact_check_status"] == "unverified"
    assert unverified["unverified_evidence"][0].startswith("unverified:")

    # Truncation path. ``size`` is the actual on-disk size (per Codex
    # round-4 polish: truncated responses must not lie about file
    # size); ``max_bytes`` carries the cap applied.
    big_content = "x" * 50_000
    (reviews_dir / "big__one.md").write_text(big_content, encoding="utf-8")
    trunc = local_api.build_module_reviews(tmp_path, "big/one", max_bytes=1000)
    assert trunc is not None
    assert trunc["truncated"] is True
    assert trunc["size"] == 50_000
    assert trunc["max_bytes"] == 1000
    assert trunc["body_size"] == 1000


def test_reviews_route_rejects_invalid_module_param(tmp_path: Path) -> None:
    tmp_path.joinpath(".pipeline", "reviews").mkdir(parents=True)
    status_code, payload, _ = local_api.route_request(
        tmp_path,
        "/api/reviews?module=../../etc/passwd",
    )
    assert status_code == 400
    assert payload["error"] == "invalid_module_key"


def test_safe_review_filename_validation() -> None:
    assert local_api._is_safe_review_filename(
        "prerequisites__zero-to-terminal__module-0.1-alpha.md"
    ) is True
    assert local_api._is_safe_review_filename("bad__name/with__slash.md") is False
    assert local_api._is_safe_review_filename("bad__name_with__slash.md") is True
    assert local_api._is_safe_review_filename("UPPER__x.md") is False
    assert local_api._is_safe_review_filename("bad__name__") is False
    assert (
        local_api._is_safe_review_filename("0__0__0__0__0.md") is True
    )


def test_reviews_route_filter_module_state_diag_and_briefing_unverified(tmp_path: Path) -> None:
    module_key, _ = _setup_repo(tmp_path)
    _write(
        tmp_path / ".pipeline/reviews/prerequisites__zero-to-terminal__module-0.1-alpha.md",
        "# Review\n\n## 2026-01-03 — `REVIEW` — `APPROVE`\n\n**Checks**: 4/4 passed (PRES NO_EMOJI K8S_API FACT_CHECK)\n\n**Feedback**:\n> unverified: could not confirm version claim\n",
    )

    status_code, payload, _ = local_api.route_request(tmp_path, "/api/reviews?fact_check_status=unverified")
    assert status_code == 200
    assert payload["count"] == 1
    assert payload["reviews"][0]["module_key"] == module_key

    state = local_api.build_module_state(tmp_path, module_key)
    assert "fact_check_unverified" in _diag_codes(state["diagnostics"])

    briefing = local_api.build_session_briefing(tmp_path)
    assert any("unverified fact claims" in alert for alert in briefing["alerts"])
    assert any(row.get("reason") == "fact_check_unverified" for row in briefing["action_rows"])


def test_resolve_bridge_db_path_precedence(tmp_path: Path, monkeypatch) -> None:
    """Codex round-1 bug: we hardcoded .bridge/messages.db but the
    Python bridge default is .mcp/servers/message-broker/messages.db.
    Resolution must honor $AB_DB_PATH first, then fall through."""
    repo = tmp_path
    monkeypatch.delenv("AB_DB_PATH", raising=False)
    p = local_api._resolve_bridge_db_path(repo)
    assert p == repo / ".bridge" / "messages.db"

    mcp_path = repo / ".mcp" / "servers" / "message-broker" / "messages.db"
    mcp_path.parent.mkdir(parents=True)
    mcp_path.write_bytes(b"")
    assert local_api._resolve_bridge_db_path(repo) == mcp_path

    bridge_path = repo / ".bridge" / "messages.db"
    bridge_path.parent.mkdir(parents=True)
    bridge_path.write_bytes(b"")
    assert local_api._resolve_bridge_db_path(repo) == bridge_path

    override = tmp_path / "custom.db"
    override.write_bytes(b"")
    monkeypatch.setenv("AB_DB_PATH", str(override))
    assert local_api._resolve_bridge_db_path(repo) == override


def test_resolve_bridge_db_path_honors_nonexistent_override(
    tmp_path: Path, monkeypatch
) -> None:
    """Codex round-2 bug: $AB_DB_PATH must win even when the override
    file doesn't yet exist. Previously we only used it when present,
    silently reading the wrong DB on a fresh override."""
    repo = tmp_path
    bridge_path = repo / ".bridge" / "messages.db"
    bridge_path.parent.mkdir(parents=True)
    bridge_path.write_bytes(b"")
    not_yet_created = tmp_path / "future.db"
    monkeypatch.setenv("AB_DB_PATH", str(not_yet_created))
    resolved = local_api._resolve_bridge_db_path(repo)
    assert resolved == not_yet_created
    assert not resolved.exists()


def test_bridge_messages_filters_and_previews(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AB_DB_PATH", raising=False)
    db_path = tmp_path / ".bridge" / "messages.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE messages (
          id INTEGER PRIMARY KEY,
          task_id TEXT, from_llm TEXT, to_llm TEXT, message_type TEXT,
          content TEXT, data TEXT, timestamp TEXT, acknowledged INTEGER,
          status TEXT
        )
        """
    )
    long_content = "y" * 800
    for i, ts in enumerate(["2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z"]):
        conn.execute(
            "INSERT INTO messages (task_id, from_llm, to_llm, message_type, content, timestamp, "
            "acknowledged, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"t{i}", "claude", "codex", "review", long_content, ts, 0, "sent"),
        )
    conn.commit()
    conn.close()

    all_ = local_api.build_bridge_messages(tmp_path, since=None, limit=10)
    assert all_["count"] == 3
    # Long content trimmed to preview.
    first = all_["messages"][0]
    assert "content" not in first  # replaced by preview
    assert first["content_full_length"] == 800
    assert first["content_preview"].endswith("(truncated)")

    since = local_api.build_bridge_messages(tmp_path, since="2026-02-01T00:00:00Z", limit=10)
    assert since["count"] == 2


def test_quality_scores_use_current_modules_not_stale_audit_markdown(tmp_path: Path) -> None:
    audit = tmp_path / "docs" / "quality-audit-results.md"
    audit.parent.mkdir(parents=True)
    audit.write_text(
        "| Module | Track | Lines | Score | Action | Issue |\n"
        "|---|---|---|---|---|---|\n"
        "| CKA 2.8: Scheduler Lifecycle Theory | CKA | 55 | **1.3** | Critical | stale |\n",
        encoding="utf-8",
    )
    _seed_quality_module(
        tmp_path,
        "k8s/cka/module-2.8-scheduler-lifecycle-theory",
        title="Module 2.8: Scheduler Lifecycle Theory",
        filler_lines=320,
        quiz=True,
        exercise=True,
        diagram=True,
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    r = local_api.build_quality_scores(tmp_path)
    assert r["exists"] is True
    assert r["source"] == "heuristic"
    assert r["count"] == 1
    assert r["critical_count"] == 0
    assert isinstance(r["generated_at"], float)
    assert {"modules", "average", "critical", "critical_count", "count"} <= set(r)
    scores = {m["module"]: m for m in r["modules"]}
    assert "CKA 2.8: Scheduler Lifecycle Theory" in scores
    assert scores["CKA 2.8: Scheduler Lifecycle Theory"]["severity"] == "excellent"
    assert all(isinstance(entry.get("path"), str) for entry in r["modules"])
    assert scores["CKA 2.8: Scheduler Lifecycle Theory"]["path"] == "k8s/cka/module-2.8-scheduler-lifecycle-theory.md"


def test_quality_upgrade_plan_groups_modules_below_target(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _seed_quality_module(tmp_path, "ai/foundations/module-1.1-what-is-ai", title="What Is AI?", filler_lines=100, diagram=True)
    _seed_quality_module(
        tmp_path, "ai/foundations/module-1.2-llms", title="LLMs Explained", filler_lines=320, quiz=True, exercise=True, diagram=True
    )
    _seed_quality_module(
        tmp_path, "ai/ai-building/module-1.1-from-chat-to-ai-systems", title="From Chat to AI Systems", filler_lines=320, quiz=True, exercise=True, diagram=True
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    plan = local_api.build_quality_upgrade_plan(tmp_path, target=4.0)
    assert plan["target"] == 4.0
    assert plan["epic_issue"] == 180
    assert plan["total_repo_modules"] == 3
    assert plan["scored_count"] == 3
    assert plan["needs_upgrade_count"] == 1
    assert plan["coverage_pct"] == 100.0
    assert plan["severity_counts"]["poor"] == 1
    assert plan["tracks"][0]["track"] == "AI Foundations"
    module = plan["tracks"][0]["modules"][0]
    assert module["module"] == "AI Foundations: What Is AI?"
    assert module["action"] == "Rewrite"
    assert "thin" in module["primary_issue"]


def test_route_request_serves_quality_upgrade_plan_and_target_5_maps_to_issue_181(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _seed_quality_module(tmp_path, "ai/foundations/module-1.1-what-is-ai", title="What Is AI?", filler_lines=320, quiz=True, diagram=True)
    _seed_quality_module(tmp_path, "ai/foundations/module-1.2-llms", title="LLMs Explained", filler_lines=240, quiz=True)
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    status_code, payload, content_type = local_api.route_request(
        tmp_path,
        "/api/quality/upgrade-plan?target=5.0",
    )
    assert status_code == 200
    assert content_type == "application/json; charset=utf-8"
    assert payload["target"] == 5.0
    assert payload["epic_issue"] == 181
    assert payload["needs_upgrade_count"] == 2
    assert payload["top_worst"][0]["module"] == "AI Foundations: LLMs Explained"


def test_route_request_rejects_invalid_quality_upgrade_target(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    status_code, payload, _ = local_api.route_request(
        tmp_path,
        "/api/quality/upgrade-plan?target=bogus",
    )
    assert status_code == 400
    assert payload["error"] == "invalid_target"


def _diag_codes(diagnostics: list[dict[str, object]]) -> set[str]:
    """Helper: extract the stable ``code`` field from a diagnostics list."""
    return {str(entry.get("code")) for entry in diagnostics if isinstance(entry, dict)}


def test_module_state_diagnostics_are_structured_dicts(tmp_path: Path) -> None:
    """Schema-tweak #263: diagnostics changed from ``list[str]`` to
    ``list[dict]`` with ``{severity, code, summary, source, next_action?}``.
    Agents switch on ``severity`` / ``code`` and drill in via
    ``next_action``, which the old string tags could not carry."""
    module_key, _ = _setup_repo(tmp_path)
    state = local_api.build_module_state(tmp_path, module_key)
    diagnostics = state.get("diagnostics")
    assert isinstance(diagnostics, list)
    for entry in diagnostics:
        assert isinstance(entry, dict)
        # Required fields.
        assert entry.get("severity") in {"info", "warn", "critical"}
        assert isinstance(entry.get("code"), str) and entry["code"]
        assert isinstance(entry.get("summary"), str) and entry["summary"]
        assert isinstance(entry.get("source"), str) and entry["source"]
        # next_action is optional but when present must be a string.
        if "next_action" in entry:
            assert isinstance(entry["next_action"], str)


def test_module_state_flags_missing_lab_and_ledger(tmp_path: Path) -> None:
    # Minimal repo: no lab, no fact ledger, no UK.
    repo = tmp_path
    _init_repo(repo)
    _write(
        repo / "src/content/docs/k8s/cka/module-x-stub.md",
        "---\ntitle: stub\n---\nbody\n",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    # Lowercase key: build_module_state now re-validates via _validate_module_key
    # (lowercase-only slugs), matching the real curriculum (all 1504 keys lowercase).
    state = local_api.build_module_state(repo, "k8s/cka/module-x-stub")
    codes = _diag_codes(state["diagnostics"])
    assert "no_lab" in codes
    assert "no_fact_ledger" in codes
    assert "uk_translation_missing" in codes


def test_rubric_diagnostics_matches_by_track_and_number(tmp_path: Path) -> None:
    """Codex round-4 bug: rubric matching compared raw slugs like
    'module-2.8-scheduler-lifecycle-theory' to live labels like
    'CKA 2.8: Scheduler Lifecycle Theory' and never matched."""
    _seed_quality_module(
        tmp_path,
        "k8s/cka/part2-workloads-scheduling/module-2.8-scheduler-lifecycle-theory",
        title="Module 2.8: Scheduler Lifecycle Theory",
        filler_lines=30,
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    _init_repo(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    state = local_api.build_module_state(
        tmp_path, "k8s/cka/part2-workloads-scheduling/module-2.8-scheduler-lifecycle-theory"
    )
    assert "rubric_critical" in _diag_codes(state["diagnostics"])


def test_rubric_diagnostics_matches_non_numbered_entry(tmp_path: Path) -> None:
    """Codex round-2 bug: live entries like 'Platform: Systems Thinking'
    (no module number) were never matched. Now resolved via name-token
    overlap when ≥2 tokens are shared AND the track alias matches."""
    _seed_quality_module(
        tmp_path, "platform/foundations/module-1-systems-thinking", title="Systems Thinking", filler_lines=320, quiz=True, exercise=True, diagram=True
    )
    _seed_quality_module(
        tmp_path, "prerequisites/modern-devops/module-5-gitops", title="GitOps", filler_lines=180, quiz=True
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    _init_repo(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    # Severity is "excellent" so no rubric_* tag is expected. But the
    # match must have happened; verify by directly probing the helper.
    quality = local_api.build_quality_scores(tmp_path)
    sev = local_api._rubric_severity_for_module(
        "platform/foundations/module-1-systems-thinking",
        quality["modules"],
    )
    assert sev == "excellent"

    # Prerequisites: GitOps → "needs_work" (3.5 > 2.9 >= 2.5). Not
    # critical/poor, so no tag in diagnostics either; probe the helper.
    sev2 = local_api._rubric_severity_for_module(
        "prerequisites/modern-devops/module-5-gitops",
        quality["modules"],
    )
    assert sev2 == "needs_work"


def test_rubric_diagnostics_matches_via_label_prefix(tmp_path: Path) -> None:
    """Codex round-3 bug: the Track column is often a SUBtrack
    ('Workloads', 'AWS', 'Foundations'). The top-level track is in
    the Module label prefix ('CKA:', 'Platform:', 'Prerequisites:').
    The matcher must consult both."""
    _seed_quality_module(
        tmp_path, "k8s/cka/part2-workloads-scheduling/module-6-autoscaling", title="Autoscaling", filler_lines=100, diagram=True
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()
    quality = local_api.build_quality_scores(tmp_path)
    sev = local_api._rubric_severity_for_module(
        "k8s/cka/part2-workloads-scheduling/module-6-autoscaling",
        quality["modules"],
    )
    # Track col is "Workloads" (no CKA alias) but the label prefix
    # carries "CKA:" — the matcher must see it.
    assert sev == "poor"


def test_build_quality_scores_counts_quiz_aliases(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/content/docs/ai/open-models/module-1.1-quiz-alias.md",
        "\n".join(
            [
                "---",
                'title: "Quiz Alias"',
                "---",
                "",
                "## Overview",
                "",
                *[f"Line {i}" for i in range(180)],
                "",
                "## Quick Quiz",
                "",
                "- Question",
                "",
                "## Hands-On Exercise",
                "",
                "1. Do thing",
                "",
                "## Sources",
                "",
                "- [Docs](https://example.com/docs)",
            ]
        )
        + "\n",
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    quality = local_api.build_quality_scores(tmp_path)
    module = next(item for item in quality["modules"] if item["path"] == "ai/open-models/module-1.1-quiz-alias.md")

    assert module["score"] == 3.6
    assert module["primary_issue"] == "thin, no diagram"


def test_quality_scores_accepts_bare_urls_in_sources(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/content/docs/ai/open-models/module-1.1-bare-urls.md",
        "\n".join(
            [
                "---",
                'title: "Bare URL Sources"',
                "---",
                "",
                "## Overview",
                "",
                *[f"Line {i}" for i in range(120)],
                "",
                "## Quick Quiz",
                "",
                "- Question",
                "",
                "## Hands-On",
                "",
                "1. Do thing",
                "",
                "## Sources",
                "",
                "- https://example.com/docs",
                "- https://reference.example.org/guide",
            ]
        )
        + "\n",
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    quality = local_api.build_quality_scores(tmp_path)
    module = next(
        item for item in quality["modules"] if item["path"] == "ai/open-models/module-1.1-bare-urls.md"
    )

    assert module["score"] > 1.5
    assert not module["primary_issue"].startswith("no citations")


def test_quality_scores_accepts_markdown_sources_links(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/content/docs/ai/open-models/module-1.2-markdown-link-only.md",
        "\n".join(
            [
                "---",
                'title: "Markdown Link Sources"',
                "---",
                "",
                "## Overview",
                "",
                *[f"Line {i}" for i in range(120)],
                "",
                "## Quick Quiz",
                "",
                "- Question",
                "",
                "## Hands-On",
                "",
                "1. Do thing",
                "",
                "## Sources",
                "",
                "- [Docs](https://example.com/docs)",
            ]
        )
        + "\n",
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    quality = local_api.build_quality_scores(tmp_path)
    module = next(
        item for item in quality["modules"] if item["path"] == "ai/open-models/module-1.2-markdown-link-only.md"
    )

    assert module["score"] > 1.5
    assert not module["primary_issue"].startswith("no citations")


def test_quality_scores_accepts_mixed_sources_citations(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/content/docs/ai/open-models/module-1.3-mixed-links.md",
        "\n".join(
            [
                "---",
                'title: "Mixed Source Citations"',
                "---",
                "",
                "## Overview",
                "",
                *[f"Line {i}" for i in range(120)],
                "",
                "## Quick Quiz",
                "",
                "- Question",
                "",
                "## Hands-On",
                "",
                "1. Do thing",
                "",
                "## Sources",
                "",
                "- [Docs](https://example.com/docs)",
                "- https://reference.example.org/guide",
            ]
        )
        + "\n",
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    quality = local_api.build_quality_scores(tmp_path)
    module = next(
        item for item in quality["modules"] if item["path"] == "ai/open-models/module-1.3-mixed-links.md"
    )

    assert module["score"] > 1.5
    assert not module["primary_issue"].startswith("no citations")


def test_quality_scores_caps_score_without_sources_heading(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/content/docs/ai/open-models/module-1.4-no-sources-heading.md",
        "\n".join(
            [
                "---",
                'title: "No Sources Heading"',
                "---",
                "",
                "## Overview",
                "",
                *[f"Line {i}" for i in range(120)],
                "",
                "## Quick Quiz",
                "",
                "- Question",
                "",
                "## Hands-On",
                "",
                "1. Do thing",
                "",
                "https://example.com/no-heading",
            ]
        )
        + "\n",
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    quality = local_api.build_quality_scores(tmp_path)
    module = next(
        item
        for item in quality["modules"]
        if item["path"] == "ai/open-models/module-1.4-no-sources-heading.md"
    )

    assert module["score"] == 1.5
    assert module["primary_issue"].startswith("no citations")


def test_quality_scores_ignores_links_outside_sources_section(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/content/docs/ai/open-models/module-1.5-outside-sources.md",
        "\n".join(
            [
                "---",
                'title: "Links Outside Sources"',
                "---",
                "",
                "## Overview",
                "",
                *[f"Line {i}" for i in range(120)],
                "",
                "## Sources",
                "",
                "",
                "## Hands-On",
                "[run kind](https://kind.sigs.k8s.io/)",
            ]
        )
        + "\n",
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    quality = local_api.build_quality_scores(tmp_path)
    module = next(
        item for item in quality["modules"] if item["path"] == "ai/open-models/module-1.5-outside-sources.md"
    )

    assert module["score"] == 1.5
    assert module["primary_issue"].startswith("no citations")


def test_rubric_diagnostics_cka_does_not_match_ckad(tmp_path: Path) -> None:
    """Codex round-3 bug: raw substring ``'cka' in 'CKAD'`` is True,
    letting a CKAD audit row attach to a CKA module path. Matcher
    must use word boundaries."""
    _seed_quality_module(tmp_path, "k8s/ckad/module-3.5-api-deprecations", title="Module 3.5: API Deprecations", filler_lines=100, diagram=True)
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()
    quality = local_api.build_quality_scores(tmp_path)
    sev = local_api._rubric_severity_for_module(
        "k8s/cka/part3-services-networking/module-3.5-gateway-api",
        quality["modules"],
    )
    assert sev is None  # CKA module must NOT pick up the CKAD row.

    # And the CKAD path DOES match.
    sev_ckad = local_api._rubric_severity_for_module(
        "k8s/ckad/module-3.5-api-deprecations",
        quality["modules"],
    )
    assert sev_ckad == "poor"


def test_rubric_diagnostics_track_only_overlap_is_not_a_match(tmp_path: Path) -> None:
    """Codex round-3 bug: overlap of ``{platform, sre}`` — both track
    tokens — must NOT match. Matcher requires ≥ 1 NON-track token in
    the overlap."""
    _seed_quality_module(
        tmp_path, "platform/sre/module-1-site-reliability-engineering-sre", title="Site Reliability Engineering (SRE)", filler_lines=100, diagram=True
    )
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()
    quality = local_api.build_quality_scores(tmp_path)
    # A platform module whose name just says "sre basics" shouldn't
    # inherit the severity from a generic "Platform: ... SRE" row.
    sev = local_api._rubric_severity_for_module(
        "platform/foundations/module-1-sre-basics",
        quality["modules"],
    )
    assert sev is None


def test_rubric_diagnostics_unrecognized_track_never_matches(tmp_path: Path) -> None:
    """Codex round-2 bug: when the path's track wasn't in the alias
    table, matching silently became permissive and could attach a
    random rubric row. Now unknown tracks always return None."""
    _seed_quality_module(tmp_path, "k8s/cka/module-2.8-scheduler-lifecycle-theory", title="Module 2.8: Scheduler Lifecycle Theory", filler_lines=30)
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()
    quality = local_api.build_quality_scores(tmp_path)
    # Path track "exotic" is not in _TRACK_ALIASES. Must not match
    # ANY row, regardless of number overlap.
    sev = local_api._rubric_severity_for_module(
        "exotic/module-2.8-scheduler",
        quality["modules"],
    )
    assert sev is None


def test_rubric_diagnostics_no_false_match_for_different_track(tmp_path: Path) -> None:
    """A module path like k8s/kcna/module-2.8-... must not pick up a
    'CKA 2.8:' rubric entry (track disambiguation)."""
    _seed_quality_module(tmp_path, "k8s/cka/module-2.8-scheduler-lifecycle-theory", title="Module 2.8: Scheduler Lifecycle Theory", filler_lines=30)
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()

    _seed_quality_module(tmp_path, "k8s/kcna/module-2.8-something-unrelated", title="Module 2.8: Something Unrelated", filler_lines=240, quiz=True)
    _init_repo(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    state = local_api.build_module_state(tmp_path, "k8s/kcna/module-2.8-something-unrelated")
    assert "rubric_critical" not in _diag_codes(state["diagnostics"])


def test_query_sqlite_rows_propagates_schema_drift(tmp_path: Path) -> None:
    """Bug-fix regression: 'no such column' must NOT silently return
    empty — that was how the priority-column bug stayed hidden."""
    db_path = tmp_path / "schema.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE jobs (id INTEGER, module_key TEXT)")
    conn.commit()
    conn.close()
    import pytest as _pytest
    with _pytest.raises(sqlite3.OperationalError) as exc_info:
        local_api._query_sqlite_rows(db_path, "SELECT ghost_column FROM jobs")
    assert "no such column" in str(exc_info.value)


def test_query_sqlite_rows_tolerates_missing_table(tmp_path: Path) -> None:
    db_path = tmp_path / "missing_table.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE other (id INTEGER)")
    conn.commit()
    conn.close()
    result = local_api._query_sqlite_rows(db_path, "SELECT * FROM does_not_exist")
    assert result == []


def test_module_state_includes_orchestration_and_lease_inline(tmp_path: Path) -> None:
    """Schema-tweak #263: ``build_module_state`` folds in orchestration
    + lease so "why is X blocked" is one call, not three.

    The individual endpoints stay for callers that only want a slice,
    but the one-call path is the happy path for agent drill-down."""
    module_key, _ = _setup_repo(tmp_path)
    state = local_api.build_module_state(tmp_path, module_key)
    assert "orchestration" in state
    assert "lease" in state
    # Orchestration has the two sub-keys mirroring the dedicated endpoint.
    orch = state["orchestration"]
    assert "v2" in orch
    assert "translation_v2" in orch
    # Lease returns ``{held: bool, ...}``.
    assert "held" in state["lease"]


def test_module_state_orchestration_surfaces_pipeline_rejection(tmp_path: Path) -> None:
    """A pipeline-rejected module must get a ``pipeline_rejected``
    diagnostic so agents see the reason without fetching the events
    endpoint separately."""
    module_key, _ = _setup_repo(tmp_path)
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Overwrite the fixture's first job with rejected state.
    conn.execute(
        "UPDATE jobs SET queue_state = ? WHERE module_key = ?",
        ("rejected", module_key),
    )
    # Add a second, newer rejected job so ORDER BY id DESC picks it.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, model) "
        "VALUES (?, ?, ?, ?)",
        (module_key, "review", "rejected", "gemini"),
    )
    conn.commit()
    conn.close()
    state = local_api.build_module_state(tmp_path, module_key)
    codes = _diag_codes(state["diagnostics"])
    assert "pipeline_rejected" in codes


def test_briefing_has_actions_and_top_modules(tmp_path: Path) -> None:
    """Schema-tweak #263: briefing gains ``actions.active/blocked/next``
    and ``top_modules`` so Codex and Claude both see what to touch next."""
    _setup_repo(tmp_path)
    _write(
        tmp_path / "STATUS.md",
        "# status\n\n## TODO\n\n- [ ] task one\n",
    )
    import time as _time
    now_s = int(_time.time())
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("active/module", "write", "leased", "codex", "l-live", now_s - 10, now_s + 300),
    )
    conn.commit()
    conn.close()
    briefing = local_api.build_session_briefing(tmp_path)
    assert "actions" in briefing
    # Codex round-2 request: ``active`` instead of ``now`` — that bucket
    # is read-only ("currently owned"), not "what I should touch".
    assert set(briefing["actions"].keys()) == {"active", "blocked", "next"}
    assert any("codex" in entry for entry in briefing["actions"]["active"])
    assert "top_modules" in briefing
    reasons = {m.get("reason") for m in briefing["top_modules"]}
    assert "active_lease" in reasons


def test_briefing_action_rows_carry_structured_bucket_and_endpoint(tmp_path: Path) -> None:
    """Codex Phase D review round 3: the dashboard was reverse-parsing
    label strings to find drill endpoints, which misroutes when the
    same module appears in multiple buckets and drops links for
    non-module rows. ``action_rows[]`` carries {bucket, label,
    module_key, phase, reason, endpoint} per row so consumers render
    directly."""
    _setup_repo(tmp_path)
    _write(tmp_path / "STATUS.md", "# s\n\n## TODO\n\n- [ ] x\n")
    now_s = int(time.time())
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    # Active lease -> action_rows entry in 'active' bucket with a
    # /api/module/{key}/state endpoint.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("live/mod", "write", "leased", "codex", "l-1", now_s - 10, now_s + 600),
    )
    # Stale lease on a different module -> action_rows entry in
    # 'blocked' bucket with a /api/pipeline/v2/events?module= endpoint.
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state, leased_by, lease_id, "
        "leased_at, lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("stale/mod", "review", "leased", "claude", "l-2",
         now_s - 10_000, now_s + 600),
    )
    conn.commit()
    conn.close()

    briefing = local_api.build_session_briefing(tmp_path)
    rows = briefing.get("action_rows")
    assert isinstance(rows, list) and rows, "action_rows must be present"

    active = [r for r in rows if r["bucket"] == "active"]
    blocked = [r for r in rows if r["bucket"] == "blocked"]
    assert any(r.get("module_key") == "live/mod" for r in active)
    assert any(r.get("module_key") == "stale/mod" for r in blocked)

    live_row = next(r for r in active if r.get("module_key") == "live/mod")
    assert live_row.get("reason") == "active_lease"
    assert live_row.get("endpoint") == "/api/module/live/mod/state"

    stale_row = next(r for r in blocked if r.get("module_key") == "stale/mod")
    assert stale_row.get("reason") in {"stale_lease", "stuck_in_state"}
    # Must point at the events timeline, NOT the state endpoint.
    assert "pipeline/v2/events" in (stale_row.get("endpoint") or "")

    # Labels must equal the strings in actions.{bucket} so the old
    # flat view is still derivable from action_rows.
    active_labels = [r["label"] for r in active]
    assert list(briefing["actions"]["active"]) == active_labels


def test_briefing_action_rows_link_non_module_rows(tmp_path: Path) -> None:
    """Codex Phase D review round 3 bug 2: rows with no ``module_key``
    (e.g. ``N job(s) ready to pick up``) previously dropped their drill
    endpoint in the dashboard because the JS only kept endpoints for
    rows with a module key. ``action_rows[]`` must carry the endpoint
    even when module_key is None."""
    _setup_repo(tmp_path)
    _write(tmp_path / "STATUS.md", "# s\n\n## TODO\n\n- [ ] x\n")
    # Seed a pending job so queue_head.ready > 0 and the ``ready_queue``
    # next row fires.
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state) VALUES (?, ?, ?)",
        ("ready/one", "write", "pending"),
    )
    conn.commit()
    conn.close()

    briefing = local_api.build_session_briefing(tmp_path)
    rows = briefing.get("action_rows") or []
    ready_rows = [r for r in rows if r.get("reason") == "ready_queue"]
    assert ready_rows, "ready_queue row must appear in action_rows"
    r = ready_rows[0]
    assert r["bucket"] == "next"
    assert r.get("module_key") is None
    assert r.get("endpoint") == "/api/pipeline/v2/status"


def test_briefing_top_modules_surfaces_pipeline_dead_letter(
    tmp_path: Path,
) -> None:
    """Codex round-2 comment: briefing should surface pipeline
    dead-letter count as a structured reason in top_modules, not
    buried in pipelines.v2."""
    _setup_repo(tmp_path)
    _write(tmp_path / "STATUS.md", "# s\n\n## TODO\n\n- [ ] x\n")

    # The v2 pipeline classifies a module as dead-letter when it has
    # seen a ``module_dead_lettered`` event and no ``dead_letter_
    # recovered`` since. Fixture a minimal job + event pair so
    # ``_build_status_report`` returns ``counts.dead_letter == 1``.
    conn = sqlite3.connect(tmp_path / ".pipeline/v2.db")
    conn.execute(
        "INSERT INTO jobs (module_key, phase, queue_state) VALUES (?, ?, ?)",
        ("dead/one", "write", "failed"),
    )
    conn.execute(
        "INSERT INTO events (module_key, type, payload_json, at) VALUES (?, ?, ?, ?)",
        ("dead/one", "module_dead_lettered", "{}", 1),
    )
    conn.commit()
    conn.close()

    briefing = local_api.build_session_briefing(tmp_path)
    reasons = {m.get("reason") for m in briefing["top_modules"]}
    assert "pipeline_dead_letter" in reasons


def test_briefing_critical_quality_not_in_actions_next(tmp_path: Path) -> None:
    """Critical-rubric modules stay on ``critical_quality`` + alerts;
    they must not crowd ``actions.next`` (gaps-first orchestration)."""
    _setup_repo(tmp_path)
    _write(tmp_path / "STATUS.md", "# s\n\n## TODO\n\n- [ ] x\n")
    _seed_quality_module(tmp_path, "k8s/cka/module-2.8-bad-stub", title="Module 2.8: Bad Stub", filler_lines=30)
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()
    briefing = local_api.build_session_briefing(tmp_path)
    assert briefing["critical_quality"], "critical modules must surface on dedicated field"
    next_rows = [r for r in briefing.get("action_rows") or [] if r.get("bucket") == "next"]
    assert not any(r.get("reason") == "critical_quality" for r in next_rows)
    assert not any(
        "rubric-critical rewrite" in (label or "")
        for label in briefing["actions"]["next"]
    )
    top_reasons = {m.get("reason") for m in briefing["top_modules"]}
    assert "critical_quality" not in top_reasons


def test_quality_scores_live_repo_no_citations_force_critical() -> None:
    """Modules without a ``## Sources`` section with external links now
    auto-fail (critical severity, 'no citations' as primary_issue).
    Issue #303's original guarantee — that the structure-rich CKA/KCNA
    modules aren't critical by length/structure heuristics — still
    holds, but citations is now an independent floor. Until content is
    backfilled with real Sources blocks, every untouched module is
    critical, which is the intentional surface-the-truth state."""
    with local_api._QUALITY_AUDIT_CACHE_LOCK:
        local_api._QUALITY_AUDIT_CACHE.clear()
    quality = local_api.build_quality_scores(local_api.REPO_ROOT)
    assert quality["source"] == "heuristic"
    by_module = {m["module"]: m for m in quality["modules"]}
    assert all(isinstance(entry.get("path"), str) for entry in quality["modules"])
    by_path = {m["path"]: m for m in quality["modules"]}
    assert "ai/foundations/module-1.1-what-is-ai.md" in by_path
    # Guard against content drift: keep assertion at least one module
    # without citations is still enforced as critical severity.
    no_citations_modules = [
        m
        for m in by_module.values()
        if "no citations" in (m.get("primary_issue") or "").lower()
    ]
    assert no_citations_modules, (
        "Expected at least one module with no citations to be flagged "
        "as a critical issue."
    )
    for entry in no_citations_modules[:5]:
        assert entry["severity"] == "critical"


def test_compact_briefing_keeps_actions_and_top_modules(tmp_path: Path) -> None:
    """Compact mode strips navigation aids but MUST keep the
    actionable fields — that's the whole point."""
    _setup_repo(tmp_path)
    _write(tmp_path / "STATUS.md", "# status\n\n## TODO\n\n- [ ] x\n")
    briefing = local_api.build_session_briefing(tmp_path)
    compact = local_api._compact_briefing(briefing)
    assert "actions" in compact
    assert "top_modules" in compact
    assert "next_reads" not in compact
    assert "links" not in compact


def test_worktrees_list_includes_dirty_counts(tmp_path: Path) -> None:
    """Schema-tweak #263: each worktree entry now carries a ``counts``
    dict so operators see which worktree is lively without shelling
    into each one."""
    repo = tmp_path
    _init_repo(repo)
    _write(repo / "README.md", "hi\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _write(repo / "README.md", "hi\n\nmore\n")

    result = local_api.build_worktrees_list(repo)
    assert result["ok"] is True
    assert result["count"] >= 1
    first = result["worktrees"][0]
    assert "counts" in first
    counts = first["counts"]
    assert counts is not None
    assert counts["total"] >= 1
    assert counts["unstaged"] >= 1
    assert first["dirty"] is True


def test_worktree_counts_total_counts_paths_not_statuses(tmp_path: Path) -> None:
    """Codex round-2 bug: counts.total used staged+unstaged+untracked,
    which double-counts a file that is both staged AND unstaged. That
    made sibling-worktree counts incomparable with the primary
    worktree's. Fix: total is the number of unique paths reported by
    ``git status --porcelain=v1``."""
    repo = tmp_path
    _init_repo(repo)
    _write(repo / "README.md", "v1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    # Stage a change, then edit the same file again so git reports
    # both a staged and an unstaged modification for one path.
    _write(repo / "README.md", "v2\n")
    _git(repo, "add", "README.md")
    _write(repo / "README.md", "v3\n")

    counts = local_api._worktree_dirty_counts(repo)
    assert counts is not None
    assert counts["total"] == 1  # one path, not two
    assert counts["staged"] >= 1
    assert counts["unstaged"] >= 1


def test_worktree_counts_dirty_is_none_when_unreadable(tmp_path: Path) -> None:
    """Codex round-2 bug: a failed ``git status`` was folded into
    dirty=False, which is a false negative. Unreadable worktrees must
    surface as dirty=None so "unknown" and "clean" are distinguishable."""
    # Path that exists but isn't a git repo.
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()
    counts = local_api._worktree_dirty_counts(non_repo)
    assert counts is None


def test_schema_lists_phase_c_endpoints() -> None:
    schema = local_api.build_api_schema()
    paths = {e["path"] for e in schema["endpoints"]}
    for expected in (
        "/api/pipeline/leases",
        "/api/pipeline/v2/events",
        "/api/pipeline/v2/stuck",
        "/api/reviews",
        "/api/bridge/messages",
        "/api/quality/scores",
        "/api/quality/upgrade-plan",
        "/api/module/{key}/lease",
    ):
        assert expected in paths, f"/api/schema missing {expected}"


def test_schema_lists_phase_d_endpoints() -> None:
    schema = local_api.build_api_schema()
    paths = {e["path"] for e in schema["endpoints"]}
    for expected in ("/api/activity",):
        assert expected in paths, f"/api/schema missing {expected}"


# ---- Phase D: merged activity feed ----


def test_activity_feed_empty_repo_returns_no_items(tmp_path: Path) -> None:
    """Nothing committed, no pipeline v2 db, no bridge db — feed returns
    empty items with zeroed source counts, not a crash."""
    _init_repo(tmp_path)
    result = local_api.build_activity_feed(tmp_path, limit=10)
    assert result["count"] == 0
    assert result["items"] == []
    assert result["source_counts"] == {
        "commit": 0,
        "pipeline_event": 0,
        "bridge_message": 0,
    }


def test_activity_feed_merges_commits_and_pipeline_events_sorted(tmp_path: Path) -> None:
    """Commits + pipeline events must come back in a single newest-first
    stream with the declared source labels."""
    repo = tmp_path
    _init_repo(repo)
    _write(repo / "README.md", "v1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "first commit")
    _write(repo / "README.md", "v2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second commit")

    db_path = repo / ".pipeline" / "v2.db"
    _init_v2_db(db_path, module_key="k8s/cka/module-1.1-foo")
    now = int(time.time())
    # Re-timestamp the seeded event into the window so it shows up.
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE events SET at = ? WHERE module_key = ?",
                 (now - 60, "k8s/cka/module-1.1-foo"))
    conn.commit()
    conn.close()

    feed = local_api.build_activity_feed(repo, limit=20, now_seconds=now)
    sources = [it["source"] for it in feed["items"]]
    assert "commit" in sources
    assert "pipeline_event" in sources
    ats = [int(it["at"]) for it in feed["items"]]
    assert ats == sorted(ats, reverse=True), "items must be newest-first"
    assert feed["source_counts"]["commit"] >= 2
    assert feed["source_counts"]["pipeline_event"] >= 1


def test_activity_feed_since_filter_excludes_old_commits(tmp_path: Path) -> None:
    """``since_seconds`` must be passed through to ``git log --since=@``
    so a tight window doesn't return the entire repo history."""
    repo = tmp_path
    _init_repo(repo)
    _write(repo / "README.md", "v1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "old commit")
    future = int(time.time()) + 10_000
    feed = local_api.build_activity_feed(
        repo, since_seconds=future, limit=20, now_seconds=future + 60
    )
    assert feed["source_counts"]["commit"] == 0
    assert feed["count"] == 0


def test_activity_feed_rejects_invalid_since_via_route(tmp_path: Path) -> None:
    """The /api/activity handler returns 400 for garbage ``since`` values
    rather than anchoring the feed at epoch 0."""
    _init_repo(tmp_path)
    status, payload, _ = local_api.route_request(tmp_path, "/api/activity?since=not-a-date")
    assert status == 400
    assert payload["error"] == "invalid_since"


def test_activity_feed_orders_pipeline_events_by_at_not_id(tmp_path: Path) -> None:
    """Codex Phase D review: the activity feed must pull pipeline-event
    candidates ordered by ``at`` DESC, not ``id`` DESC. Otherwise a
    backfilled row (high ``id``, old ``at``) can fill the per-source
    cap and push a genuinely newer event out of the candidate set, so
    the merged top-N wouldn't actually be chronological."""
    repo = tmp_path
    _init_repo(repo)
    db_path = repo / ".pipeline" / "v2.db"
    _init_v2_db(db_path, module_key="seed/mod")

    now = 1_000_000
    # Stream three rows in (id-ascending) order:
    #   id=1   at=now-100   ← oldest
    #   id=2   at=now-3000  ← BACKFILL (high id, old at)
    #   id=3   at=now-50    ← newest
    # ``id DESC`` would yield [3, 2, 1]. With limit=2, that drops id=1
    # but keeps the backfill. ``at DESC`` must yield [3, 1, 2], so
    # limit=2 keeps [id=3, id=1] — the two truly newest rows.
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM events")
    conn.executemany(
        "INSERT INTO events (id, module_key, type, lease_id, payload_json, at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (101, "seed/mod", "attempt_started", None, "{}", now - 100),
            (102, "seed/mod", "backfilled",      None, "{}", now - 3000),
            (103, "seed/mod", "attempt_ended",   None, "{}", now - 50),
        ],
    )
    conn.commit()
    conn.close()

    feed = local_api.build_activity_feed(
        repo, since_seconds=now - 5000, limit=2, now_seconds=now
    )
    event_items = [it for it in feed["items"] if it["source"] == "pipeline_event"]
    kinds = [it["kind"] for it in event_items]
    # The newest two by ``at`` are id=103 (attempt_ended) and id=101
    # (attempt_started). The backfill (id=102) must NOT win over them.
    assert "attempt_ended" in kinds
    assert "attempt_started" in kinds
    assert "backfilled" not in kinds


def test_activity_feed_bridge_filter_keeps_fractional_and_offset_iso(tmp_path: Path) -> None:
    """Codex Phase D review: bridge-row filtering used a lexical string
    compare against an ISO ``...Z`` cutoff. That drops rows whose
    absolute time is LATER but whose ISO string sorts BEFORE (fractional
    seconds, ``+00:00`` offsets). Filtering must run through
    ``_iso_to_epoch`` on the Python side."""
    repo = tmp_path
    _init_repo(repo)
    bridge_dir = repo / ".bridge"
    bridge_dir.mkdir()
    bdb = bridge_dir / "messages.db"
    conn = sqlite3.connect(bdb)
    conn.executescript(
        """
        CREATE TABLE messages (
          id INTEGER PRIMARY KEY,
          task_id TEXT,
          from_llm TEXT,
          to_llm TEXT,
          message_type TEXT,
          content TEXT,
          timestamp TEXT,
          acknowledged INTEGER DEFAULT 0,
          status TEXT
        );
        """
    )
    # Cutoff is 2026-01-01T00:00:00Z (= epoch 1767225600). These two
    # messages are at +0.5s and +0.000001s after the cutoff — both
    # must be KEPT. A lexical compare against "2026-01-01T00:00:00Z"
    # drops them because ``.``/``+`` sort before ``Z``.
    conn.executemany(
        "INSERT INTO messages (id, task_id, from_llm, to_llm, message_type, "
        "content, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "t", "a", "b", "query", "hi", "2026-01-01T00:00:00.500Z", "delivered"),
            (2, "t", "a", "b", "query", "hi", "2026-01-01T00:00:00.000001+00:00", "delivered"),
            # This one IS before the cutoff and must be dropped.
            (3, "t", "a", "b", "query", "hi", "2025-12-31T23:59:00Z", "delivered"),
        ],
    )
    conn.commit()
    conn.close()

    cutoff = 1767225600  # 2026-01-01T00:00:00Z
    feed = local_api.build_activity_feed(
        repo, since_seconds=cutoff, limit=50, now_seconds=cutoff + 3600
    )
    bridge_ids = {it["ref"]["message_id"] for it in feed["items"] if it["source"] == "bridge_message"}
    assert 1 in bridge_ids
    assert 2 in bridge_ids
    assert 3 not in bridge_ids


def test_activity_feed_accepts_iso_since(tmp_path: Path) -> None:
    """ISO-8601 ``since`` values should parse the same as epoch seconds."""
    _init_repo(tmp_path)
    _write(tmp_path / "README.md", "v1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial")
    status, payload, _ = local_api.route_request(
        tmp_path, "/api/activity?since=1970-01-01T00:00:00Z&limit=5"
    )
    assert status == 200
    assert isinstance(payload, dict)
    assert payload["since_seconds"] == 0


# ---- Phase D: per-section track readiness ----


def _seed_module(
    repo: Path,
    rel: str,
    *,
    frontmatter: dict[str, object] | None = None,
) -> None:
    """Create a minimal ``module-*.md`` under ``src/content/docs/<rel>.md``.

    ``rel`` is the docs-relative path without the ``.md`` suffix, e.g.
    ``k8s/cka/module-1.1-foo``.
    """
    path = repo / "src" / "content" / "docs" / f"{rel}.md"
    fm: dict[str, object] = {"title": "t"}
    if frontmatter:
        fm.update(frontmatter)
    payload = yaml.safe_dump(fm, sort_keys=False).strip()
    _write(path, f"---\n{payload}\n---\n\nbody\n")


def _seed_v2_job(
    db_path: Path,
    *,
    module_key: str,
    queue_state: str,
    phase: str = "review",
    lease_id: str | None = None,
    leased_by: str | None = None,
    leased_at: int | None = None,
) -> None:
    """Insert a ``jobs`` row with the given state. Fixture DB must have
    ``jobs`` + ``events`` tables already created (see ``_init_v2_db``).

    Note: the fixture table doesn't enforce the production CHECK
    constraint on ``queue_state``, but tests should still pass values
    from the real vocabulary (``pending | leased | completed | failed``)
    so the reducer-driven readiness endpoint exercises the same paths
    as the live pipeline.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO jobs
            (module_key, phase, model, queue_state, leased_by, lease_id,
             leased_at, enqueued_at, requested_calls, estimated_usd, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module_key,
                phase,
                "codex",
                queue_state,
                leased_by,
                lease_id,
                leased_at,
                int(time.time()),
                1,
                0.01,
                f"{module_key}-{queue_state}-{time.time_ns()}",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_v2_event(
    db_path: Path,
    *,
    module_key: str,
    event_type: str,
    at: int = 1,
    payload_json: str = "{}",
    lease_id: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO events (module_key, type, lease_id, payload_json, at) "
            "VALUES (?, ?, ?, ?, ?)",
            (module_key, event_type, lease_id, payload_json, at),
        )
        conn.commit()
    finally:
        conn.close()


def test_tracks_readiness_empty_repo(tmp_path: Path) -> None:
    """No docs directory, no frontmatter-based readiness data — returns zeroed totals and no tracks."""
    _init_repo(tmp_path)
    result = local_api.build_tracks_readiness(tmp_path)
    assert result["tracks"] == []
    assert result["totals"]["total"] == 0
    assert result["totals"]["source_accepted"] == 0
    assert result["totals"]["readiness_pct"] == 0.0


def test_tracks_readiness_frontmatter_predicate_cleared_states(tmp_path: Path) -> None:
    """A module is cleared iff ``revision_pending`` is falsey and
    ``citations_verified`` is true."""
    cases = (
        ("k8s/cka/module-1.1-foo", {"revision_pending": False, "citations_verified": True}, True),
        ("k8s/cka/module-1.2-bar", {"revision_pending": True, "citations_verified": True}, False),
        ("k8s/cka/module-1.3-baz", {"revision_pending": False}, False),
        ("k8s/cka/module-1.4-qux", {"citations_verified": True}, True),
        ("k8s/cka/module-1.5-quux", {}, False),
        ("k8s/cka/module-1.6-quuz", {"revision_pending": True}, False),
    )
    for rel, frontmatter_data, should_clear in cases:
        case_root = tmp_path / f"case-{rel.replace('/', '-')}"
        case_root.mkdir(parents=True, exist_ok=True)
        _init_repo(case_root)
        _seed_module(case_root, rel, frontmatter=frontmatter_data)
        result = local_api.build_tracks_readiness(case_root)
        k8s = next(t for t in result["tracks"] if t["slug"] == "k8s")
        cka = next(s for s in k8s["sections"] if s["slug"] == "cka")
        assert cka["cleared"] == (1 if should_clear else 0)
        assert cka["not_yet_enqueued"] == (0 if should_clear else 1)


def test_tracks_readiness_frontmatter_aggregate_counts(tmp_path: Path) -> None:
    """Three modules in one track/section aggregate with mixed states."""
    _init_repo(tmp_path)
    _seed_module(
        tmp_path,
        "k8s/cka/module-1.1-alpha",
        frontmatter={"revision_pending": False, "citations_verified": True},
    )
    _seed_module(
        tmp_path,
        "k8s/cka/module-1.2-beta",
        frontmatter={"revision_pending": True, "citations_verified": True},
    )
    _seed_module(
        tmp_path,
        "k8s/cka/module-1.3-gamma",
        frontmatter={"revision_pending": False},
    )

    result = local_api.build_tracks_readiness(tmp_path)
    k8s = next(t for t in result["tracks"] if t["slug"] == "k8s")
    cka = next(s for s in k8s["sections"] if s["slug"] == "cka")
    assert k8s["total"] == 3
    assert k8s["cleared"] == 1
    assert k8s["source_accepted"] == 0
    assert k8s["not_yet_enqueued"] == 2
    assert cka["total"] == 3
    assert cka["source_accepted"] == 0
    assert cka["readiness_pct"] == 33.3
    assert result["totals"]["source_accepted"] == 0


def test_v_docs_frontmatter_changes_on_module_edit(tmp_path: Path) -> None:
    """The cache version key must change when ANY EN module's frontmatter changes."""
    _init_repo(tmp_path)
    _seed_module(
        tmp_path,
        "k8s/cka/module-1.1-alpha",
        frontmatter={"revision_pending": False, "citations_verified": True},
    )
    v1 = local_api._v_docs_frontmatter(tmp_path)

    _seed_module(
        tmp_path,
        "k8s/cka/module-1.1-alpha",
        frontmatter={"revision_pending": True, "citations_verified": True},
    )
    v2 = local_api._v_docs_frontmatter(tmp_path)
    assert v1 != v2, "version key must change when frontmatter changes"

    _seed_module(
        tmp_path,
        "k8s/cka/module-1.2-beta",
        frontmatter={"revision_pending": False, "citations_verified": True},
    )
    v3 = local_api._v_docs_frontmatter(tmp_path)
    assert v2 != v3, "version key must change when a new module is added"


def test_tracks_readiness_cache_invalidation_from_frontmatter_change(tmp_path: Path) -> None:
    """Changes to module frontmatter invalidate the readiness cache key."""
    _init_repo(tmp_path)
    _seed_module(
        tmp_path,
        "k8s/cka/module-1.1-alpha",
        frontmatter={"revision_pending": True, "citations_verified": True},
    )
    first_status, first_payload, _ = local_api.route_request(
        tmp_path, "/api/tracks/readiness"
    )
    assert first_status == 200
    k8s_first = next(t for t in first_payload["tracks"] if t["slug"] == "k8s")
    assert k8s_first["cleared"] == 0

    _seed_module(
        tmp_path,
        "k8s/cka/module-1.1-alpha",
        frontmatter={"revision_pending": False, "citations_verified": True},
    )
    second_status, second_payload, _ = local_api.route_request(
        tmp_path, "/api/tracks/readiness"
    )
    assert second_status == 200
    k8s_second = next(t for t in second_payload["tracks"] if t["slug"] == "k8s")
    assert k8s_second["cleared"] == 1


def test_tracks_readiness_top_level_module_uses_root_section(tmp_path: Path) -> None:
    """``prerequisites/module-*.md`` has no intermediate section directory
    — it must land in a ``_root`` bucket rather than crashing."""
    _init_repo(tmp_path)
    _seed_module(
        tmp_path,
        "prerequisites/module-0-welcome",
        frontmatter={"revision_pending": False, "citations_verified": True},
    )
    result = local_api.build_tracks_readiness(tmp_path)
    prereq = next(t for t in result["tracks"] if t["slug"] == "prerequisites")
    root = next(s for s in prereq["sections"] if s["slug"] == "_root")
    assert root["total"] == 1


def test_schema_lists_tracks_readiness() -> None:
    paths = {e["path"] for e in local_api.build_api_schema()["endpoints"]}
    assert "/api/tracks/readiness" in paths


def test_iso_to_epoch_round_trip() -> None:
    """``_iso_to_epoch`` must accept both ``Z`` and ``+00:00`` forms."""
    assert local_api._iso_to_epoch("1970-01-01T00:00:00Z") == 0
    assert local_api._iso_to_epoch("1970-01-01T00:00:00+00:00") == 0
    assert local_api._iso_to_epoch("bogus") is None
    assert local_api._iso_to_epoch(None) is None
    assert local_api._iso_to_epoch("") is None


def test_cli_starts_server_and_reports_host_port(tmp_path: Path) -> None:
    repo_root = tmp_path
    _init_repo(repo_root)
    process = subprocess.Popen(
        [
            sys.executable,
            "scripts/local_api.py",
            "--host",
            "127.0.0.1",
            "--port",
            "8876",
            "--repo-root",
            str(repo_root),
        ],
        cwd="/Users/krisztiankoos/projects/kubedojo",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        line = process.stdout.readline().strip()
        data = json.loads(line)
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 8876
    finally:
        process.terminate()
        process.wait(timeout=5)


def _seed_commit(repo: Path) -> None:
    _init_repo(repo)
    (repo / "a.txt").write_text("seed", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed")
    # Normalize: `git init` defaults to `master` on older git; the hygiene
    # check keys on `main`. Force it so tests don't silently depend on the
    # host machine's init.defaultBranch setting.
    _git(repo, "branch", "-M", "main")


def _stash_with_date(repo: Path, ts: int, message: str) -> None:
    """Create a stash whose committer timestamp is `ts` (unix seconds).

    `git stash push` honors GIT_COMMITTER_DATE / GIT_AUTHOR_DATE, so we
    can back-date a stash for age-bucket tests without mutating refs by
    hand. Uses -u so a fresh untracked file qualifies — without it, git
    exits 0 with "No local changes to save" and the caller silently gets
    an empty stash list.
    """
    env = {
        **os.environ,
        "GIT_COMMITTER_DATE": f"@{ts} +0000",
        "GIT_AUTHOR_DATE": f"@{ts} +0000",
    }
    (repo / f"stash-{ts}.txt").write_text("modified", encoding="utf-8")
    subprocess.run(
        ["git", "stash", "push", "-u", "-m", message],
        cwd=repo, env=env, check=True, capture_output=True,
    )
    r = subprocess.run(
        ["git", "stash", "list"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    if not r.stdout.strip():
        raise RuntimeError("stash push did not actually create a stash")


def test_git_hygiene_clean_repo_emits_nothing(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    worktree = local_api.build_worktree_status(tmp_path)
    worktrees = local_api.build_worktrees_list(tmp_path)
    assert local_api._git_hygiene_signals(tmp_path, worktree, worktrees) == []


def test_git_hygiene_flags_stash_older_than_seven_days(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    _stash_with_date(tmp_path, int(time.time()) - 10 * 86400, "ancient")
    worktree = local_api.build_worktree_status(tmp_path)
    worktrees = local_api.build_worktrees_list(tmp_path)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, worktrees)
    assert any("older than 7 days" in a for a in alerts)


def test_git_hygiene_flags_stash_older_than_one_day(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    _stash_with_date(tmp_path, int(time.time()) - 2 * 86400, "stale")
    worktree = local_api.build_worktree_status(tmp_path)
    worktrees = local_api.build_worktrees_list(tmp_path)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, worktrees)
    # 2-day-old stash is "stale" not "ancient"; 7-day wording should not appear.
    assert any("older than 24h" in a for a in alerts)
    assert not any("older than 7 days" in a for a in alerts)


def test_git_hygiene_ignores_fresh_stash(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    _stash_with_date(tmp_path, int(time.time()) - 60, "fresh")
    worktree = local_api.build_worktree_status(tmp_path)
    worktrees = local_api.build_worktrees_list(tmp_path)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, worktrees)
    # Under 24h — no stash-age alert should fire.
    assert not any("stash(es)" in a for a in alerts)


def test_git_hygiene_ancient_suppresses_stale_message(tmp_path: Path) -> None:
    # When a repo has BOTH >7-day and >24h stashes, only the >7-day line
    # fires — we'd rather the operator see the worst offender than two
    # competing lines about the same pile. The ancient-count excludes
    # stale-only stashes (counts aren't double-counted).
    _seed_commit(tmp_path)
    _stash_with_date(tmp_path, int(time.time()) - 10 * 86400, "ancient")
    _stash_with_date(tmp_path, int(time.time()) - 2 * 86400, "merely-stale")
    worktree = local_api.build_worktree_status(tmp_path)
    worktrees = local_api.build_worktrees_list(tmp_path)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, worktrees)
    ancient_lines = [a for a in alerts if "older than 7 days" in a]
    stale_lines = [a for a in alerts if "older than 24h" in a]
    assert len(ancient_lines) == 1
    assert stale_lines == []
    assert "1 stash(es)" in ancient_lines[0]  # only the >7d one counted


def test_git_hygiene_tolerates_malformed_stash_list_output(
    tmp_path: Path, monkeypatch
) -> None:
    # `git stash list --format=%ct` should always be one unix-timestamp
    # per line, but we guard against weird states (half-broken stash
    # ref, future git version) so a freak output never crashes the
    # briefing. Pin that best-effort behavior.
    _seed_commit(tmp_path)
    worktree = local_api.build_worktree_status(tmp_path)
    worktrees = local_api.build_worktrees_list(tmp_path)

    ancient_ts = int(time.time()) - 10 * 86400
    real_run = local_api.subprocess.run

    def fake_run(cmd, **kwargs):
        if list(cmd[:4]) == ["git", "stash", "list", "--format=%ct"]:
            class _R:
                returncode = 0
                stdout = f"garbage\n{ancient_ts}\n\nnot-a-number\n"
            return _R()
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(local_api.subprocess, "run", fake_run)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, worktrees)
    # One valid numeric line interpreted as a real >7d stash; junk ignored.
    assert any("older than 7 days" in a and "1 stash(es)" in a for a in alerts)


def test_git_hygiene_flags_detached_worktree(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    worktree = local_api.build_worktree_status(tmp_path)
    fake = {
        "worktrees": [
            {"path": str(tmp_path), "branch": "main", "detached": False},
            {"path": "/tmp/stale-detached", "branch": None, "detached": True},
        ]
    }
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, fake)
    assert any("detached HEAD" in a for a in alerts)


def test_git_hygiene_flags_dirty_main(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    (tmp_path / "b.txt").write_text("uncommitted leak", encoding="utf-8")
    _git(tmp_path, "add", "b.txt")
    worktree = local_api.build_worktree_status(tmp_path)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, {"worktrees": []})
    assert any("uncommitted" in a and "on main" in a for a in alerts)


def test_git_hygiene_silent_on_dirty_non_main_branch(tmp_path: Path) -> None:
    _seed_commit(tmp_path)
    _git(tmp_path, "checkout", "-b", "feature-x")
    (tmp_path / "b.txt").write_text("wip", encoding="utf-8")
    worktree = local_api.build_worktree_status(tmp_path)
    alerts = local_api._git_hygiene_signals(tmp_path, worktree, {"worktrees": []})
    # Dirty branches other than main are normal working state, not drift.
    assert not any("uncommitted" in a for a in alerts)


def test_session_briefing_surfaces_git_hygiene_alert(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    _stash_with_date(tmp_path, int(time.time()) - 10 * 86400, "ancient-audit-work")
    briefing = local_api.build_session_briefing(tmp_path)
    assert any(
        "git hygiene" in a and "older than 7 days" in a
        for a in briefing["alerts"]
    )


def _seed_book_chapter(
    repo_root: Path,
    chapter_num: int,
    slug: str,
    *,
    status: str | None = "researching",
    owner: str | None = None,
    review_state: str | None = None,
    green: int | None = None,
    yellow: int | None = None,
    red: int | None = None,
    last_updated: str | None = None,
    notes_block: bool = False,
) -> None:
    chapters_dir = repo_root / "docs" / "research" / "ai-history" / "chapters"
    chapter_dir = chapters_dir / f"ch-{chapter_num:02d}-{slug}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if status is not None:
        lines.append(f"status: {status}")
    if owner is not None:
        lines.append(f"owner: {owner}")
    lines.append(f"chapter: {chapter_num}")
    if review_state is not None:
        lines.append(f"review_state: {review_state}")
    if green is not None:
        lines.append(f"green_claims: {green}")
    if yellow is not None:
        lines.append(f"yellow_claims: {yellow}")
    if red is not None:
        lines.append(f"red_claims: {red}")
    if last_updated is not None:
        lines.append(f"last_updated: {last_updated}")
    if notes_block:
        # Block-scalar; the parser must skip the indented continuation.
        lines.append("notes: |")
        lines.append("  Free-form notes line one.")
        lines.append("  Should be ignored by the top-level parser.")
    (chapter_dir / "status.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_briefing_book_groups_chapters_by_part_with_rollup(tmp_path: Path) -> None:
    _seed_book_chapter(tmp_path, 1, "the-laws-of-thought", status="ready_to_draft_with_cap", owner="Gemini")
    _seed_book_chapter(tmp_path, 6, "the-cybernetics-movement", status="accepted", owner="Gemini")
    _seed_book_chapter(
        tmp_path,
        11,
        "the-summer-ai-named-itself",
        status="capacity_plan_anchored",
        owner="Claude",
        review_state="codex_approved_2026-04-27",
        green=13,
        yellow=12,
        red=1,
        notes_block=True,
    )
    _seed_book_chapter(
        tmp_path,
        24,
        "the-math-that-waited-for-the-machine",
        status="prose_ready",
        owner="Codex",
        last_updated="2026-04-27",
    )
    _seed_book_chapter(tmp_path, 50, "attention-is-all-you-need", status="researching", owner="Codex")
    _seed_book_chapter(tmp_path, 72, "the-infinite-datacenter", status="researching", owner="Claude")

    status_code, payload, content_type = local_api.route_request(tmp_path, "/api/briefing/book")
    assert status_code == 200
    assert content_type.startswith("application/json")
    assert isinstance(payload, dict)
    assert payload["epic_issue"] == 394
    assert payload["expected_chapter_count"] == 72
    assert payload["chapter_count"] == 6
    assert len(payload["parts"]) == 9

    parts_by_num = {p["part"]: p for p in payload["parts"]}
    # Part 3 (Ch 11-16): one anchored chapter with all the GYR counts.
    part3 = parts_by_num[3]
    assert part3["chapter_range"] == [11, 16]
    assert part3["tracking_issue"] == 401
    assert part3["chapter_count"] == 1
    assert part3["status_rollup"] == {"capacity_plan_anchored": 1}
    assert part3["owners_seen"] == ["Claude"]
    ch11 = part3["chapters"][0]
    assert ch11["chapter"] == 11
    assert ch11["green_claims"] == 13
    assert ch11["yellow_claims"] == 12
    assert ch11["red_claims"] == 1
    assert ch11["review_state"] == "codex_approved_2026-04-27"

    # Empty parts still appear with zero counts so consumers can render the grid.
    part4 = parts_by_num[4]
    assert part4["chapter_count"] == 0
    assert part4["status_rollup"] == {}
    assert part4["owners_seen"] == []
    assert part4["chapters"] == []

    # Total rollup aggregates across all parts.
    assert payload["total_status_rollup"] == {
        "ready_to_draft_with_cap": 1,
        "accepted": 1,
        "capacity_plan_anchored": 1,
        "prose_ready": 1,
        "researching": 2,
    }


def test_briefing_book_handles_missing_or_malformed_status_files(tmp_path: Path) -> None:
    chapters_dir = tmp_path / "docs" / "research" / "ai-history" / "chapters"
    chapters_dir.mkdir(parents=True)

    # Chapter dir present, no status.yaml.
    (chapters_dir / "ch-12-logic-theorist-gps").mkdir()

    # Chapter dir with non-numeric prefix — must be ignored.
    (chapters_dir / "ch-foo-bar").mkdir()

    # Chapter with a status.yaml that uses comments and quoted values.
    weird = chapters_dir / "ch-13-the-list-processor"
    weird.mkdir()
    (weird / "status.yaml").write_text(
        '# leading comment\nstatus: "researching"\nowner: \'Claude\'\nchapter: 13\n',
        encoding="utf-8",
    )

    payload = local_api.build_book_briefing(tmp_path)
    parts_by_num = {p["part"]: p for p in payload["parts"]}
    part3 = parts_by_num[3]
    # ch-12 has no status.yaml — its status field is None and rolled up under "unknown".
    statuses_in_part3 = sorted(
        (c["chapter"], c["status"]) for c in part3["chapters"]
    )
    assert (12, None) in statuses_in_part3
    assert (13, "researching") in statuses_in_part3
    assert part3["status_rollup"].get("unknown") == 1
    assert part3["status_rollup"].get("researching") == 1

    # The non-numeric directory must not appear anywhere.
    all_slugs = {c["slug"] for p in payload["parts"] for c in p["chapters"]}
    assert "ch-foo-bar" not in all_slugs


def test_briefing_book_returns_empty_skeleton_when_directory_missing(tmp_path: Path) -> None:
    payload = local_api.build_book_briefing(tmp_path)
    assert payload["chapter_count"] == 0
    assert payload["expected_chapter_count"] == 72
    assert payload["published_count"] == 0
    assert payload["aids_landed_count"] == 0
    assert len(payload["parts"]) == 9
    assert all(p["chapter_count"] == 0 for p in payload["parts"])
    assert all(p["published_count"] == 0 for p in payload["parts"])
    assert all(p["aids_landed_count"] == 0 for p in payload["parts"])
    assert payload["total_status_rollup"] == {}


def test_briefing_book_endpoint_listed_in_schema(tmp_path: Path) -> None:
    status_code, payload, _ = local_api.route_request(tmp_path, "/api/schema")
    assert status_code == 200
    assert any(
        ep.get("path") == "/api/briefing/book" for ep in payload["endpoints"]
    ), "schema must advertise /api/briefing/book"
