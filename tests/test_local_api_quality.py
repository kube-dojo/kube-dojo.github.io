"""Regression tests for the local-API quality page split."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_quality", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def test_quality_route_remains_real_page(tmp_path: Path) -> None:
    status, body, content_type = local_api.route_request(tmp_path, "/quality")
    assert status == 200
    assert "text/html" in content_type
    assert 'id="quality-board"' in body
    assert '<a class="navlink active" href="/quality"' in body
    assert 'href="/static/design-system.css"' in body
    assert 'data-search-widget' not in body

