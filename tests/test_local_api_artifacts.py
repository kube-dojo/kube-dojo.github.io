from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_artifacts", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_calibration_reports_are_allowed_artifacts() -> None:
    assert "calibration/v1/reports" in local_api._ARTIFACT_ALLOWED_DIRS


def test_artifacts_index_lists_seeded_html_by_category(tmp_path: Path) -> None:
    first = tmp_path / "audit" / "report.html"
    second = tmp_path / "docs" / "migrations" / "html-first" / "_design-system.html"
    third = tmp_path / "docs" / "decisions" / "decision-card.md"
    _write(first, "<!doctype html><title>Audit Report</title><h1>Report</h1>")
    _write(second, "<!doctype html><title>Design System</title><h1>Design</h1>")
    _write(third, "# Keep Markdown Browseable\n\nDecision body.")
    now = time.time()
    os.utime(first, (now - 7200, now - 7200))
    os.utime(second, (now - 60, now - 60))
    os.utime(third, (now - 30, now - 30))

    status, body, content_type = local_api.route_request(tmp_path, "/artifacts")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Audit Report" in body
    assert "Design System" in body
    assert "Keep Markdown Browseable" in body
    assert "/artifacts/audit/report.html" in body
    assert "/artifacts/docs/migrations/html-first/_design-system.html" in body
    assert "/artifacts/docs/decisions/decision-card.md" in body
    assert "Markdown files" in body
    assert '<a class="navlink active" href="/artifacts"' in body
    assert 'id="artifact-search"' in body
    assert "Recently updated" in body


def test_api_artifacts_returns_json_shape(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "session-state" / "handoff.md", "# Handoff\n\nNotes.")

    status, body, content_type = local_api.route_request(tmp_path, "/api/artifacts")

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    artifact = body["Handoffs (pre-s196 history)"][0]
    assert artifact["title"] == "Handoff"
    assert artifact["path"] == "docs/session-state/handoff.md"
    assert artifact["url"] == "/artifacts/docs/session-state/handoff.md"
    assert artifact["format"] == "md"
    assert isinstance(artifact["mtime"], float)
    assert isinstance(artifact["size_bytes"], int)


def test_artifact_html_uses_shell_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "references" / "external" / "ref.html", "<title>Reference</title>")

    status, body, content_type = local_api.route_request(
        tmp_path,
        "/artifacts/docs/references/external/ref.html",
    )

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert isinstance(body, str)
    assert 'class="artifact-shell"' in body
    assert 'class="artifact-frame"' in body
    assert "?raw=1" in body


def test_artifact_html_raw_query_serves_bytes(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "references" / "external" / "ref.html", "<title>Reference</title>")

    status, body, content_type = local_api.route_request(
        tmp_path,
        "/artifacts/docs/references/external/ref.html?raw=1",
    )

    assert status == 200
    assert body == b"<title>Reference</title>"
    assert content_type == "text/html; charset=utf-8"


def test_research_excluded_from_default_index(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "research" / "paper.html", "<title>Research Paper</title>")

    status, body, _ = local_api.route_request(tmp_path, "/artifacts")
    assert status == 200
    assert "Research Paper" not in body

    status, body, _ = local_api.route_request(tmp_path, "/artifacts?include=research")
    assert status == 200
    assert "Research Paper" in body


def test_artifact_markdown_renders_with_html_content_type(tmp_path: Path) -> None:
    _write(
        tmp_path / "STATUS.md",
        "# Session Status\n\n- First item\n\n```python\nprint('ok')\n```",
    )

    status, body, content_type = local_api.route_request(tmp_path, "/artifacts/STATUS.md")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "<h1>Session Status</h1>" in body
    assert "<li>First item</li>" in body
    assert "print" in body
    assert '<a class="navlink active" href="/artifacts"' in body


def test_artifact_assets_serve_only_from_allowed_tree(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "migrations" / "html-first" / "style.css", "body{}")
    _write(tmp_path / "src" / "content" / "docs" / "style.css", "body{}")

    status, body, content_type = local_api.route_request(
        tmp_path,
        "/artifacts/docs/migrations/html-first/style.css",
    )
    blocked_status, _, _ = local_api.route_request(
        tmp_path,
        "/artifacts/src/content/docs/style.css",
    )

    assert status == 200
    assert body == b"body{}"
    assert content_type == "text/css; charset=utf-8"
    assert blocked_status == 404


def test_artifact_path_traversal_returns_404(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "migrations" / "index.html", "<title>Index</title>")

    status, _, _ = local_api.route_request(
        tmp_path,
        "/artifacts/docs/migrations/../migrations/index.html",
    )

    assert status == 404


def test_artifact_nonexistent_returns_404(tmp_path: Path) -> None:
    status, _, _ = local_api.route_request(tmp_path, "/artifacts/audit/missing.html")

    assert status == 404


def test_home_groups_artifacts_and_decisions_in_tools(tmp_path: Path) -> None:
    status, body, content_type = local_api.route_request(tmp_path, "/")

    assert status == 200
    assert "text/html" in content_type
    assert '<a class="navlink" href="/artifacts">Artifacts</a>' in body
    menu = body.split('<div class="nav-menu">', 1)[1].split('</details>', 1)[0]
    assert 'href="/decisions"' in menu and 'href="/artifacts"' in menu
    assert 'summary-card' not in body


def test_schema_documents_research_artifact_deferral() -> None:
    schema = local_api.build_api_schema()
    endpoints = {entry["path"]: entry for entry in schema["endpoints"]}
    api_artifacts = endpoints["/api/artifacts"]
    html_artifacts = endpoints["/artifacts"]
    assert "Research" in api_artifacts["desc"]
    assert "include=research" in api_artifacts["query"]
    assert "include_research=1" in api_artifacts["query"]
    assert "include=research" in html_artifacts["query"]


def test_architecture_diagram_is_served_and_indexed(tmp_path: Path) -> None:
    diagram = tmp_path / "docs" / "architecture" / "codebase-diagram.html"
    _write(diagram, "<!doctype html><title>KubeDojo Codebase Architecture</title><h1>Architecture</h1>")

    status, body, content_type = local_api.route_request(
        tmp_path,
        "/artifacts/docs/architecture/codebase-diagram.html",
    )
    assert status == 200
    assert "text/html" in content_type
    assert "Architecture" in body

    status, index, _ = local_api.route_request(tmp_path, "/api/artifacts")
    assert status == 200
    assert "Architecture" in index
    assert index["Architecture"][0]["path"] == "docs/architecture/codebase-diagram.html"
