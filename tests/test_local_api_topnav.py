"""Regression tests for local-API top navigation routes."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_topnav", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _route(tmp_path: Path, path: str) -> str:
    status, body, content_type = local_api.route_request(tmp_path, path)
    assert status == 200
    assert "text/html" in content_type
    return body


def test_three_primary_areas_and_grouped_tools(tmp_path: Path) -> None:
    for route, active in (('/', '/'), ('/operations', '/operations'), ('/quality', '/quality')):
        page = _route(tmp_path, route)
        nav = page.split('<nav class="topnav"', 1)[1].split('</nav>', 1)[0]
        primary, tools = nav.split('<details class="nav-tools">', 1)
        assert len(re.findall(r'class="navlink', primary)) == 3
        assert f'href="{active}" aria-current="page"' in primary
        assert 'href="/channels"' in tools and 'href="/decisions"' in tools
        assert 'href="/health"' not in nav and 'href="/pipeline"' not in nav


def test_secondary_pages_keep_navigation_and_current_location(tmp_path: Path) -> None:
    for route in ('/channels', '/channels/thread-123', '/decisions', '/artifacts'):
        page = _route(tmp_path, route)
        key = '/' + route.strip('/').split('/')[0]
        assert f'href="{key}" aria-current="page"' in page
        assert 'href="/operations"' in page and 'href="/quality"' in page


def test_quality_retains_canonical_and_legacy_inspection(tmp_path: Path) -> None:
    page = _route(tmp_path, '/quality')
    for key in ('cc-summary', 'cc-work-summary', 'cc-rows', 'quality-board'):
        assert f'id="{key}"' in page
    assert 'Legacy pipeline progress (secondary)' in page
