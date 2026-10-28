"""Regression tests for the slim local-API home page."""
from __future__ import annotations

import importlib.util
import json
import os
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

def test_quality_discloses_definitions_and_legacy_board() -> None:
    html = local_api.render_quality_board_page_html()
    assert '<details><summary>Coverage definitions</summary>' in html
    assert '<details class="panel"><summary>Legacy pipeline progress (secondary)</summary>' in html
    assert html.index('/static/content-coverage.js') < html.index('/static/quality-coverage.js')


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
    assert "English acceptance" in html
    assert "Canonical page acceptance" in html
    assert html.count("renderCoverage(null)") == 2
    assert '<script src="/static/content-coverage.js"></script>' in html
    status, source, content_type = local_api.route_request(Path(__file__).resolve().parents[1], "/static/content-coverage.js")
    assert status == 200 and "javascript" in content_type
    function = source.decode()
    script = """
const nodes = {};
const $ = key => nodes[key] ||= {textContent: ''};
function tone() {}
""" + function + """
const good = {content_coverage: {
  status:'needs_attention',coverage_health:'known',
  locales:{en:{total:1089,review_recorded:41,needs_revision:30,acceptance_recorded:10,unreviewed:1048,stale:1,invalid:0},
    uk:{total:562,review_recorded:0,needs_revision:0,acceptance_recorded:0,unreviewed:562,stale:0,invalid:0}}, parked_locales:['uk'],
  milestones:{prerequisites_linux:{total:100,review_recorded:6,acceptance_recorded:0}}
}}; renderCoverage(good);
const known = JSON.parse(JSON.stringify(nodes));
renderCoverage({content_coverage: {status:'needs_attention',coverage_health:'unknown',
  locales:{en:{total:1089,review_recorded:0,needs_revision:0,acceptance_recorded:0,unreviewed:1089,stale:8,invalid:0},
    uk:{total:562,review_recorded:0,needs_revision:0,acceptance_recorded:0,unreviewed:562,stale:0,invalid:0}}, parked_locales:['uk'],
  milestones:{prerequisites_linux:{total:100,review_recorded:0,acceptance_recorded:0}},receipt_error_count:8}});
const stale = JSON.parse(JSON.stringify(nodes));
renderCoverage({});
const unknown = JSON.parse(JSON.stringify(nodes));
""" + "\nconst page = " + json.dumps(html) + ";\n" + """
const pending = [];
let calls = 0, refreshVersion = 0;
nodes['#refresh'] = {classList:{add(){},remove(){}}};
const fetchJson = () => calls++ < 4 ? new Promise(resolve => pending.push(resolve)) : Promise.reject(new Error('offline'));
const renderOperator = () => {}, renderPipeline = () => {}, renderActivity = () => {}, renderHealth = () => {}, setPollTs = () => {};
const start = page.indexOf('    async function refresh()'), end = page.indexOf("    $('#refresh').addEventListener", start);
const refresh = eval('(' + page.slice(start, end).trim() + ')');
(async () => {
  const old = refresh(); await refresh(); pending.forEach(resolve => resolve(good)); await old;
  console.log(JSON.stringify({known,stale,unknown,race:nodes}));
})();
"""
    node = os.environ.get("KUBEDOJO_NODE") or "node"
    result = subprocess.run([str(node), "-e", script], capture_output=True, text=True, check=True,
                            env={**os.environ, "NODE_DISABLE_COMPILE_CACHE": "1"})
    states = json.loads(result.stdout)
    assert "10 / 1089 accepted · 0.9%" in states["known"]["#coverage-counts"]["textContent"]
    assert states["known"]["#coverage-progress"]["value"] == 10
    assert states["known"]["#coverage-progress"]["max"] == 1089
    assert "30 need revision" in states["known"]["#coverage-milestone"]["textContent"]
    assert "UK parked: 0/562" in states["known"]["#coverage-milestone"]["textContent"]
    assert states["stale"]["#coverage-badge"]["textContent"] == "Health unknown"
    assert "8 stale" in states["stale"]["#coverage-milestone"]["textContent"]
    assert states["known"]["#quality-summary-counts"]["textContent"] == states["known"]["#coverage-counts"]["textContent"]
    assert states["unknown"]["#coverage-badge"]["textContent"] == "Unknown"
    assert states["unknown"]["#coverage-counts"]["textContent"] == "Coverage evidence unavailable"
    assert states["unknown"]["#quality-summary-counts"]["textContent"] == "Coverage evidence unavailable"
    assert states["unknown"]["#coverage-progress"]["hidden"] is True
    assert states["race"]["#coverage-badge"]["textContent"] == "Unknown"
