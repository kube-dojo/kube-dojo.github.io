"""Regression tests for the slim local-API home page."""
from __future__ import annotations

import importlib.util
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


def test_home_stays_small_and_loads_the_visual_overview(tmp_path: Path) -> None:
    page = _home(tmp_path)
    assert len(page.encode()) < 26_624
    assert 'data-monitor-view="overview"' in page
    assert 'id="coverage-body"' in page and 'id="work-body"' in page
    assert page.index('/static/content-coverage.js') < page.index('/static/monitor.js')
    assert 'summary-card' not in page


def test_quality_discloses_definitions_and_legacy_board() -> None:
    page = local_api.render_quality_board_page_html()
    assert '<details><summary>Coverage definitions</summary>' in page
    assert '<details class="panel"><summary>Legacy pipeline progress (secondary)</summary>' in page
    assert page.index('/static/content-coverage.js') < page.index('/static/quality-coverage.js')


def test_operations_shows_leases_and_pipeline_and_keeps_deep_links(tmp_path: Path) -> None:
    status, page, content_type = local_api.route_request(tmp_path, '/operations')
    assert status == 200 and 'text/html' in content_type
    assert 'data-monitor-view="operations"' in page
    for section in ('leases', 'pipeline'):
        assert f'id="{section}"' in page and f'id="{section}-body"' in page
    for removed in ('activity', 'services'):
        assert f'id="{removed}"' not in page
    for old, section in {'operator':'leases', 'pipeline':'pipeline'}.items():
        status, location, _ = local_api.route_request(tmp_path, '/' + old)
        assert status == 302 and location == '/operations#' + section
    status, dashboard, _ = local_api.route_request(tmp_path, '/dashboard')
    assert status == 200 and 'data-monitor-view="overview"' in dashboard


def test_specialist_records_are_secondary_not_duplicate_cards(tmp_path: Path) -> None:
    page = _home(tmp_path)
    assert 'nav-tools' not in page
    for href in ('/', '/quality', '/operations', '/artifacts', '/telemetry', '/uk'):
        assert f'href="{href}"' in page
    for href in ('/decisions', '/channels', '/benchmarks', '/agents', '/headroom'):
        assert f'href="{href}"' not in page
    assert 'operator-summary' not in page and 'pipeline-summary' not in page


def test_monitor_uses_static_data_fetchers_and_preserves_api_schema(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    status, body, _ = local_api.route_request(repo, '/static/monitor.js')
    assert status == 200
    for endpoint in ('/api/content/coverage', '/api/pipeline/leases', '/api/pipeline/v2/status'):
        assert endpoint in body.decode()
    for endpoint in ('/api/runtime/services', '/api/activity'):
        assert endpoint not in body.decode()
    schema = {item['path']: item for item in local_api.build_api_schema()['endpoints']}
    assert '/operations' in schema
    assert 'redirect' in schema['/pipeline']['desc']
    assert '/activity' not in schema and '/health' not in schema


def test_manifest_lists_primary_screens_and_actual_legacy_redirects(tmp_path: Path) -> None:
    manifest = local_api.build_state_manifest()
    categories = {category['category']: category['entries'] for category in manifest['categories']}
    dashboards = {entry['path']: entry for entry in categories['dashboards']}
    for route, name in (('/', 'Overview'), ('/quality', 'Curriculum'), ('/operations', 'Operations')):
        assert dashboards[route]['name'] == name and dashboards[route]['type'] == 'html'
        assert local_api.route_request(tmp_path, route)[0] == 200
    for route in ('/operator', '/pipeline'):
        status, target, _ = local_api.route_request(tmp_path, route)
        assert status == 302 and dashboards[route]['type'] == 'redirect'
        assert dashboards[route]['target'] == target
    diagnostic_apis = {entry['path'] for entry in categories['git_and_build'] if entry['type'] == 'api'}
    assert {'/api/git/worktrees', '/api/missing-modules/status'} <= diagnostic_apis


def test_all_monitor_entry_points_share_the_app_nav_and_no_search(tmp_path: Path) -> None:
    for route in ('/', '/dashboard', '/operations'):
        status, page, _ = local_api.route_request(tmp_path, route)
        assert status == 200
        for href in ('http://localhost:8765/machinery', 'http://localhost:8765/', 'http://localhost:8768/'):
            assert f'href="{href}"' in page
        assert 'Search messages and decisions' not in page and '/api/search' not in page
        assert len(page.encode()) < 26_624
