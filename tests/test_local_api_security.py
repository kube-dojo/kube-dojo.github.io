from __future__ import annotations

import http.client
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Thread

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api_security", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _with_server(repo_root: Path, callback: Callable[[int], None]) -> None:
    server = local_api.ThreadingHTTPServer(("127.0.0.1", 0), local_api.make_handler(repo_root))
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        callback(port)
    finally:
        server.shutdown()
        server.server_close()


def test_reviews_route_rejects_traversal_module_key(tmp_path: Path) -> None:
    status_code, payload, _ = local_api.route_request(tmp_path, "/api/reviews?module=../../etc/passwd")

    assert status_code == 400
    assert payload == {"error": "invalid_module_key"}
    assert "/etc/passwd" not in json.dumps(payload)


def test_review_path_builder_rejects_traversal_module_key(tmp_path: Path) -> None:
    (tmp_path / ".pipeline" / "reviews").mkdir(parents=True)

    assert local_api.build_module_reviews(tmp_path, "../../etc/passwd") is None


def test_static_path_resolution_failure_returns_typed_not_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("KUBEDOJO_UI_ROOT", raising=False)
    static = tmp_path / "static"
    static.mkdir()
    asset = static / "fixture.css"
    asset.write_bytes(b"/* fixture */")

    for path in ("../fixture.css", str(asset), "bad\x00name.css"):
        assert local_api.serve_static_file(tmp_path, path) == (
            404, {"error": "not_found"}, "application/json; charset=utf-8"
        )


def test_static_resolved_path_must_stay_inside_base_before_stat(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("KUBEDOJO_UI_ROOT", raising=False)
    static = tmp_path / "static"
    static.mkdir()
    sibling = tmp_path / "static-fixtures"
    sibling.mkdir()
    asset = sibling / "fixture.css"
    asset.touch()
    (static / "fixture.css").symlink_to(asset)

    def unexpected_stat(_path: Path) -> bool:
        pytest.fail("A rejected path reached the file-type probe")

    with monkeypatch.context() as fs:
        fs.setattr(Path, "is_file", unexpected_stat)
        for path in ("fixture.css", "../static-fixtures/fixture.css", str(asset)):
            assert local_api.serve_static_file(tmp_path, path) == (
                404, {"error": "not_found"}, "application/json; charset=utf-8"
            )


def test_static_base_must_be_the_declared_directory_before_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("KUBEDOJO_UI_ROOT", raising=False)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    asset = fixtures / "fixture.css"
    asset.touch()
    (tmp_path / "static").symlink_to(fixtures, target_is_directory=True)

    def unexpected_read(_path: Path) -> bytes:
        pytest.fail("A rejected static base reached the file reader")

    with monkeypatch.context() as fs:
        fs.setattr(Path, "read_bytes", unexpected_read)
        for path in ("fixture.css", "../fixtures/fixture.css", str(asset)):
            assert local_api.serve_static_file(tmp_path, path) == (
                404, {"error": "not_found"}, "application/json; charset=utf-8"
            )


def test_get_response_headers_do_not_split_on_crlf(monkeypatch, tmp_path: Path) -> None:
    malicious_etag = 'W/"abc"\r\nX-Injected-Etag: 1'

    def fake_serve_request(_repo_root: Path, _path: str):
        return 200, b"{}", "application/json\r\nX-Injected-Type: 1", malicious_etag

    monkeypatch.setattr(local_api, "serve_request", fake_serve_request)

    def request(port: int) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/schema")
        response = conn.getresponse()
        response.read()

        assert response.status == 200
        assert response.getheader("X-Injected-Type") is None
        assert response.getheader("X-Injected-Etag") is None
        assert "\r" not in response.getheader("Content-Type", "")
        assert "\n" not in response.getheader("Content-Type", "")
        assert "\r" not in response.getheader("ETag", "")
        assert "\n" not in response.getheader("ETag", "")

    _with_server(tmp_path, request)


def test_not_modified_etag_header_does_not_split_on_crlf(monkeypatch, tmp_path: Path) -> None:
    malicious_etag = 'W/"abc"\r\nX-Injected-Not-Modified: 1'
    safe_etag = local_api._safe_etag_header_value(malicious_etag)

    def fake_serve_request(_repo_root: Path, _path: str):
        return 200, b"{}", "application/json; charset=utf-8", malicious_etag

    monkeypatch.setattr(local_api, "serve_request", fake_serve_request)

    def request(port: int) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/schema", headers={"If-None-Match": safe_etag})
        response = conn.getresponse()
        response.read()

        assert response.status == 304
        assert response.getheader("X-Injected-Not-Modified") is None
        assert "\r" not in response.getheader("ETag", "")
        assert "\n" not in response.getheader("ETag", "")

    _with_server(tmp_path, request)


def test_post_response_headers_do_not_split_on_crlf(monkeypatch, tmp_path: Path) -> None:
    def fake_route_post_request(_repo_root: Path, _path: str, **_kwargs: object):
        return 202, {"ok": True}, "application/json\r\nX-Injected-Post: 1"

    monkeypatch.setattr(local_api, "route_post_request", fake_route_post_request)

    def request(port: int) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/build/run")
        response = conn.getresponse()
        response.read()

        assert response.status == 202
        assert response.getheader("X-Injected-Post") is None
        assert "\r" not in response.getheader("Content-Type", "")
        assert "\n" not in response.getheader("Content-Type", "")

    _with_server(tmp_path, request)


def test_build_module_state_rejects_traversal_module_key(tmp_path: Path) -> None:
    # CodeQL py/path-injection (#32): build_module_state re-validates module_key
    # (defense in depth) so a "../" traversal raises before reaching the
    # filesystem reads (en_path.exists() / frontmatter extraction) below it.
    with pytest.raises(ValueError):
        local_api.build_module_state(tmp_path, "../../../../etc/passwd")


def test_relative_path_returns_empty_for_path_outside_repo_root(
    monkeypatch: Callable[..., None],
    tmp_path: Path,
) -> None:
    module_key = "module-key"

    def fake_find_quality_board_module(_repo_root: Path, _module_key: str) -> dict[str, str]:
        return {"title": "Module", "track": "prerequisites", "status": "unknown", "score": "100"}

    def fake_build_module_state(_repo_root: Path, _module_key: str) -> dict[str, object]:
        return {"english_path": "/etc/passwd", "ukrainian_path": None}

    monkeypatch.setattr(local_api, "_find_quality_board_module", fake_find_quality_board_module)
    monkeypatch.setattr(local_api, "build_module_state", fake_build_module_state)

    html = local_api.render_quality_module_page_html(tmp_path, module_key)
    assert html is not None
    assert "/etc/passwd" not in html
    assert '<a href="//etc/passwd">english</a>' not in html


def test_relative_path_returns_empty_for_nonexistent_path(
    monkeypatch: Callable[..., None],
    tmp_path: Path,
) -> None:
    module_key = "module-key"

    def fake_find_quality_board_module(_repo_root: Path, _module_key: str) -> dict[str, str]:
        return {"title": "Module", "track": "prerequisites", "status": "unknown", "score": "100"}

    def fake_build_module_state(_repo_root: Path, _module_key: str) -> dict[str, object]:
        return {"english_path": "/totally/made/up/file", "ukrainian_path": None}

    monkeypatch.setattr(local_api, "_find_quality_board_module", fake_find_quality_board_module)
    monkeypatch.setattr(local_api, "build_module_state", fake_build_module_state)

    html = local_api.render_quality_module_page_html(tmp_path, module_key)
    assert html is not None
    assert "/totally/made/up/file" not in html
    assert "<a href=\"//totally/made/up/file\">english</a>" not in html


def test_head_response_sanitizes_crlf_in_location(monkeypatch, tmp_path: Path) -> None:
    malicious_location = "/ok\r\nX-Injected-Location: 1"

    def fake_serve_request(_repo_root: Path, _path: str):
        return 302, malicious_location.encode("utf-8"), "text/plain", ""

    monkeypatch.setattr(local_api, "serve_request", fake_serve_request)

    def request(port: int) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("HEAD", "/api/schema")
        response = conn.getresponse()
        response.read()

        assert response.status == 302
        assert response.getheader("Location") == local_api._safe_header_value(malicious_location)
        assert response.getheader("X-Injected-Location") is None
        assert "\r" not in response.getheader("Location", "")
        assert "\n" not in response.getheader("Location", "")

    _with_server(tmp_path, request)


def test_get_response_sanitizes_crlf_in_location(monkeypatch, tmp_path: Path) -> None:
    malicious_location = "/ok\r\nX-Injected-Location: 1"

    def fake_serve_request(_repo_root: Path, _path: str):
        return 302, malicious_location.encode("utf-8"), "text/plain", ""

    monkeypatch.setattr(local_api, "serve_request", fake_serve_request)

    def request(port: int) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/schema")
        response = conn.getresponse()
        response.read()

        assert response.status == 302
        assert response.getheader("Location") == local_api._safe_header_value(malicious_location)
        assert response.getheader("X-Injected-Location") is None
        assert "\r" not in response.getheader("Location", "")
        assert "\n" not in response.getheader("Location", "")

    _with_server(tmp_path, request)
