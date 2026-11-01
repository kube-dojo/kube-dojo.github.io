from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_benchmarks_ui", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


LANES = [
    "code-review",
    "code-writing",
    "content-review",
    "debugging",
    "fact-check",
    "orchestrating",
    "planning",
    "refactoring",
    "research",
    "summarization",
    "testing",
    "translation",
]
MODELS = [
    "claude-haiku-4-5",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.5-flash-high",
    "gpt-5.3-codex-spark",
    "gpt-5.4-mini",
    "gpt-5.5",
    "grok-4.3",
    "qwen3.6",
    "qwen3.6-plus",
]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_benchmark_reports(repo_root: Path, *, include_stability: bool = True) -> None:
    _write(
        repo_root / "calibration" / "v1" / "reports" / "2026-05-20" / "index.html",
        "<title>Previous</title>",
    )
    latest = repo_root / "calibration" / "v1" / "reports" / "2026-05-21"
    _write(latest / "index.html", "<title>Latest</title>")
    _write(latest / "matrix.html", "<title>Matrix</title>")
    _write(latest / "wave-ab-report.html", "<title>Wave AB</title>")
    if include_stability:
        _write(latest / "stability.html", "<title>Stability</title>")
        _write(repo_root / "calibration" / "v1" / "reports" / "stability-candidates.json", "[]")
    for lane in LANES:
        _write(latest / "per-lane" / f"{lane}.html", f"<title>{lane}</title>")
    for model in MODELS:
        _write(latest / "per-model" / f"{model}.html", f"<title>{model}</title>")

    ledger_path = repo_root / "calibration" / "v1" / "ledger.db"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ledger_path)
    try:
        conn.execute("CREATE TABLE cells (cell_id TEXT, model_id TEXT, lane TEXT)")
        conn.execute("CREATE TABLE scores (cell_id TEXT)")
        cells = [
            (f"{lane}-{model}", model, lane)
            for lane in LANES
            for model in MODELS
        ]
        conn.executemany("INSERT INTO cells (cell_id, model_id, lane) VALUES (?, ?, ?)", cells)
        conn.executemany("INSERT INTO scores (cell_id) VALUES (?)", [(cell_id,) for cell_id, _, _ in cells])
        conn.commit()
    finally:
        conn.close()


def test_benchmarks_page_renders_latest_report_dashboard(tmp_path: Path) -> None:
    _seed_benchmark_reports(tmp_path)

    status, body, content_type = local_api.route_request(tmp_path, "/benchmarks")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "2026-05-21" in body
    assert "168" in body
    assert "14 models" in body
    assert "12 lanes" in body
    assert 'href="/artifacts/calibration/v1/reports/2026-05-21/per-lane/code-review.html"' in body
    assert 'href="/artifacts/calibration/v1/reports/2026-05-21/stability.html"' in body
    assert 'data-search-widget' in body


def test_benchmarks_page_disables_missing_stability_report(tmp_path: Path) -> None:
    _seed_benchmark_reports(tmp_path, include_stability=False)

    status, body, content_type = local_api.route_request(tmp_path, "/benchmarks")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert '<span class="bench-tile disabled">' in body
    assert 'href="/artifacts/calibration/v1/reports/2026-05-21/stability.html"' not in body
    assert "stability-candidates.json" not in body
    assert 'data-search-widget' in body


def test_benchmarks_top_nav_link_appears_on_existing_ui_routes(tmp_path: Path) -> None:
    for route in ("/operations", "/quality"):
        status, body, content_type = local_api.route_request(tmp_path, route)

        assert status == 200
        assert content_type == "text/html; charset=utf-8"
        assert 'href="/benchmarks">Benchmarks</a>' in body


def test_homepage_keeps_benchmarks_in_secondary_tools(tmp_path: Path) -> None:
    _seed_benchmark_reports(tmp_path)

    status, body, content_type = local_api.route_request(tmp_path, "/")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Benchmarks" in body
    assert 'href="/benchmarks"' in body
    menu = body.split('<div class="nav-menu">', 1)[1].split('</details>', 1)[0]
    assert 'href="/benchmarks"' in menu
    assert 'benchmarks-summary-card' not in body
