"""Regression tests for the slim local-API home page."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_home_slim", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _home(tmp_path: Path) -> str:
    status, body, content_type = local_api.route_request(tmp_path, "/")
    assert status == 200
    assert "text/html" in content_type
    return body


def test_home_body_stays_under_26kb(tmp_path: Path) -> None:
    assert len(_home(tmp_path).encode()) < 26_624


def test_home_keeps_topnav_and_route_summary_cards(tmp_path: Path) -> None:
    html = _home(tmp_path)

    for href in ["/operator", "/quality", "/pipeline", "/activity", "/health", "/channels"]:
        assert f'href="{href}"' in html

    assert 'class="op-summary-card" href="/operator"' in html
    assert 'class="quality-summary-card" href="/quality"' in html
    assert 'class="pipeline-summary-card" href="/pipeline"' in html
    assert 'class="activity-summary-card" href="/activity"' in html
    assert 'class="op-summary-card health-summary-card" href="/health"' in html
    assert 'class="channels-summary-card" href="/channels"' in html
    assert 'class="artifacts-summary-card" href="/artifacts"' in html
    assert 'class="decisions-summary-card" href="/decisions"' in html


def test_home_does_not_render_tables(tmp_path: Path) -> None:
    assert "<table" not in _home(tmp_path).lower()


def test_home_drops_moved_panel_markers(tmp_path: Path) -> None:
    html = _home(tmp_path)

    moved_markers = [
        'id="quality-board"',
        "qb-",
        'id="v2-body"',
        'id="v2-badge"',
        "v2-",
        'id="activity-body"',
        'id="activity-badge"',
        "activity-feed",
        'id="health-services-panel"',
        'id="health-worktrees-panel"',
        'id="health-missing-panel"',
        'id="services"',
        'id="worktrees"',
        'id="missing"',
        'id="tracks-body"',
        'id="trans-body"',
        'id="book-body"',
        'id="completion-body"',
        'id="reviews"',
        'id="feedback"',
    ]
    for marker in moved_markers:
        assert marker not in html


def test_coverage_card_renders_counts_and_unknown_without_false_zero(tmp_path: Path) -> None:
    html = _home(tmp_path)
    assert 'href="/api/content/coverage"' in html
    assert "Legacy pipeline labels, not full-page acceptance" in html
    assert '<script src="/static/content-coverage.js"></script>' in html
    status, source, content_type = local_api.route_request(Path(__file__).resolve().parents[1], "/static/content-coverage.js")
    assert status == 200 and "javascript" in content_type
    function = source.decode()
    script = """
const nodes = {};
const $ = key => nodes[key] ||= {textContent: ''};
function tone() {}
""" + function + """
renderCoverage({content_coverage: {
  status:'needs_attention',coverage_health:'known',
  locales:{en:{total:1089,review_recorded:8,needs_revision:8,acceptance_recorded:0}},
  milestones:{prerequisites_linux:{total:100,review_recorded:6,acceptance_recorded:0}}
}});
const known = JSON.parse(JSON.stringify(nodes));
renderCoverage({content_coverage: {status:'needs_attention',coverage_health:'unknown',
  locales:{en:{total:1089,review_recorded:0,needs_revision:0,acceptance_recorded:0,stale:8,invalid:0}},
  milestones:{prerequisites_linux:{total:100,review_recorded:0,acceptance_recorded:0}},receipt_error_count:8}});
const stale = JSON.parse(JSON.stringify(nodes));
renderCoverage({});
console.log(JSON.stringify({known,stale,unknown:nodes}));
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    states = json.loads(result.stdout)
    assert "8 / 1089" in states["known"]["#coverage-counts"]["textContent"]
    assert "0 acceptance records" in states["known"]["#coverage-counts"]["textContent"]
    assert "6 / 100" in states["known"]["#coverage-milestone"]["textContent"]
    assert states["stale"]["#coverage-badge"]["textContent"] == "Health unknown"
    assert "8 stale" in states["stale"]["#coverage-counts"]["textContent"]
    assert "8 evidence errors" in states["stale"]["#coverage-counts"]["textContent"]
    assert states["unknown"]["#coverage-badge"]["textContent"] == "Unknown"
    assert states["unknown"]["#coverage-counts"]["textContent"] == "Coverage evidence unavailable"
