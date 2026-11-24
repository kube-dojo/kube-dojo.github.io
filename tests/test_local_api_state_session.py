from __future__ import annotations

import importlib.util
import subprocess
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


def _manifest_entries(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for category in body["categories"]
        for entry in category["entries"]
    ]


def test_state_manifest_contains_product_discovery_paths_only(tmp_path: Path) -> None:
    status, body, content_type = local_api.route_request(tmp_path, "/api/state/manifest")

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    paths = {entry["path"] for entry in _manifest_entries(body)}
    assert "/api/schema" in paths
    assert "/api/pipeline/leases" in paths
    assert "/api/tracks/readiness" in paths
    for removed in (
        "/api/briefing/session",
        "/api/briefing/session?compact=1",
        "/api/session/current",
        "/api/orient",
        "/api/git/worktrees",
        "/api/benchmarks/latest",
    ):
        assert removed not in paths


def test_state_manifest_entries_are_well_formed(tmp_path: Path) -> None:
    status, body, _ = local_api.route_request(tmp_path, "/api/state/manifest")

    assert status == 200
    for entry in _manifest_entries(body):
        assert entry["name"]
        assert entry["path"]
        assert entry["purpose"]


def test_removed_machinery_routes_return_404(tmp_path: Path) -> None:
    for path in (
        "/api/briefing/session",
        "/api/orient",
        "/api/session/current",
        "/api/runtime/services",
        "/api/activity",
        "/api/activity/recent",
        "/api/git/worktree",
        "/api/git/worktrees",
        "/api/git/cleanup",
        "/api/gh/issues",
        "/api/gh/issues/1",
    ):
        status, payload, _ = local_api.route_request(tmp_path, path)
        assert status == 404, f"expected 404 for {path}, got {status}"
        assert payload["error"] == "not_found"


def test_healthz_reports_primary_checkout_from_git(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q"], cwd=primary, check=True, timeout=60)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "base"], cwd=primary, check=True, timeout=60)
    worktree = tmp_path / "wt1"
    subprocess.run([*git, "worktree", "add", "-q", str(worktree)], cwd=primary, check=True, timeout=60)

    status_ok, payload_ok, _ = local_api.route_request(primary, "/healthz")
    assert status_ok == 200
    assert payload_ok["ok"] is True
    assert payload_ok["primary_repo_root"] == str(primary.resolve())

    status_wt, payload_wt, _ = local_api.route_request(worktree, "/healthz")
    assert status_wt == 200
    assert payload_wt["ok"] is False
    assert payload_wt["primary_repo_root"] == str(primary.resolve())
    assert any("not the primary checkout" in w for w in payload_wt["warnings"])
