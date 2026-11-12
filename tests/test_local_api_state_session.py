from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_state_session", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _manifest_entries(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for category in body["categories"]
        for entry in category["entries"]
    ]


def _seed_handoffs(repo_root: Path) -> None:
    _write(
        repo_root / "docs" / "session-state" / "2026-05-09-cka-part1-and-html-migration-pivot.html",
        """
        <!doctype html>
        <html>
        <body>
        <h1>CKA Part 1 and HTML Migration Pivot</h1>
        <p>Latest HTML handoff summary for cold-start routing.</p>
        </body>
        </html>
        """,
    )
    _write(
        repo_root / "docs" / "session-state" / "2026-05-08-4-content-green-canary.md",
        """
        # Content Green Canary

        TL;DR: Previous handoff summary.
        """,
    )
    _write(repo_root / "docs" / "session-state" / "archive-pre-2026-04-28.md", "# Archive")
    _write(repo_root / "docs" / "session-state" / "handoff-without-prefix.html", "<h1>Ignored</h1>")


def test_state_manifest_contains_cold_start_critical_paths(tmp_path: Path) -> None:
    status, body, content_type = local_api.route_request(tmp_path, "/api/state/manifest")

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    paths = {entry["path"] for entry in _manifest_entries(body)}
    assert "/api/briefing/session" in paths
    assert "/api/briefing/session?compact=1" in paths
    assert "/api/schema" in paths
    assert "/api/session/current" in paths
    assert "/api/benchmarks/latest" not in paths


def test_state_manifest_entries_are_well_formed(tmp_path: Path) -> None:
    status, body, _ = local_api.route_request(tmp_path, "/api/state/manifest")

    assert status == 200
    for entry in _manifest_entries(body):
        assert entry["name"]
        assert entry["path"]
        assert entry["purpose"]


def test_current_session_returns_latest_key(tmp_path: Path) -> None:
    _seed_handoffs(tmp_path)

    status, body, content_type = local_api.route_request(tmp_path, "/api/session/current")

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert "latest" in body
    assert body["latest"]["filename"] == "2026-05-09-cka-part1-and-html-migration-pivot.html"


def test_current_session_latest_date_matches_filename_prefix(tmp_path: Path) -> None:
    _seed_handoffs(tmp_path)

    _, body, _ = local_api.route_request(tmp_path, "/api/session/current")

    latest = body["latest"]
    assert latest["date"] == re.match(r"^\d{4}-\d{2}-\d{2}", latest["filename"]).group(0)


def test_current_session_predecessor_is_not_newer_than_latest(tmp_path: Path) -> None:
    _seed_handoffs(tmp_path)

    _, body, _ = local_api.route_request(tmp_path, "/api/session/current")

    assert body["predecessors"][0]["date"] <= body["latest"]["date"]


def test_current_session_excludes_archive_and_prefixless_files(tmp_path: Path) -> None:
    _seed_handoffs(tmp_path)

    _, body, _ = local_api.route_request(tmp_path, "/api/session/current")

    filenames = {body["latest"]["filename"], *(item["filename"] for item in body["predecessors"])}
    assert "archive-pre-2026-04-28.md" not in filenames
    assert "handoff-without-prefix.html" not in filenames
    assert body["total_handoffs"] == 2


def test_current_session_contains_at_least_one_html_handoff(tmp_path: Path) -> None:
    _seed_handoffs(tmp_path)

    _, body, _ = local_api.route_request(tmp_path, "/api/session/current")

    handoffs = [body["latest"], *body["predecessors"]]
    assert any(item["format"] == "html" for item in handoffs)
