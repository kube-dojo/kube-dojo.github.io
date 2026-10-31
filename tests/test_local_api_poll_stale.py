from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_poll_stale", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_ui_fragments():
    module_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "local_api" / "routes" / "ui_fragments.py"
    )
    spec = importlib.util.spec_from_file_location("ui_fragments_poll_stale", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _set_poll_ts_body(script: str) -> str:
    match = re.search(
        r"window\.setPollTs = function setPollTs\(el, payload\) \{.*?\n  \};",
        script,
        re.DOTALL,
    )
    assert match is not None
    return match.group(0)


local_api = _load_module()
ui_fragments = _load_ui_fragments()


POLL_PAGES = ("/quality",)

SET_POLL_TS_CALL_SITES = (
    ("/quality", "setPollTs($('#last-updated'), board)"),
)


def test_poll_stale_script_marks_elements_older_than_24h() -> None:
    script = ui_fragments.render_poll_stale_script()
    assert "setPollTs" in script
    assert "poll-stale" in script
    assert "24 * 60 * 60 * 1000" in script


def test_set_poll_ts_toggles_stale_immediately() -> None:
    script = ui_fragments.render_poll_stale_script()
    body = _set_poll_ts_body(script)
    assert "STALE_MS" in body
    assert 'classList.toggle("poll-stale", stale)' in body
    assert "classList.remove" not in body


def test_set_poll_ts_reapplies_stale_for_old_cached_timestamp() -> None:
    """Stale cached refresh must not clear poll-stale until data is fresh."""
    script = ui_fragments.render_poll_stale_script()
    body = _set_poll_ts_body(script)
    assert "Date.now() - tsMs > STALE_MS" in body
    assert "el.dataset.pollTs" in body
    assert 'classList.toggle("poll-stale", stale)' in body


def test_auto_refresh_pages_include_poll_stale_assets(tmp_path: Path) -> None:
    for route in POLL_PAGES:
        status, body, content_type = local_api.route_request(tmp_path, route)
        assert status == 200, route
        assert "text/html" in content_type, route
        assert ".poll-stale" in body, route
        assert "setPollTs" in body, route
        assert "markStalePolls" in body, route


@pytest.mark.parametrize("route,needle", SET_POLL_TS_CALL_SITES)
def test_auto_refresh_page_wires_set_poll_ts_in_refresh_handler(
    tmp_path: Path, route: str, needle: str
) -> None:
    status, body, _ = local_api.route_request(tmp_path, route)
    assert status == 200, route
    assert needle in body, route
