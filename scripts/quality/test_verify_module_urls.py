"""HTTP boundary tests; local test prerequisites are pytest and requests.

The runtime verifier keeps requests optional. These tests use its real exception
classes and redirect parser, with mocked transport and browser-process boundaries.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality import verify_module


def test_url_check_missing_requests_is_fetch_failure(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "requests", None)
    with patch("subprocess.run") as browser:
        assert verify_module._check_url("https://example.com") == "fetch_failed"
        browser.assert_not_called()


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError, requests.TooManyRedirects])
def test_url_head_transport_failure_does_not_attempt_browser(failure) -> None:
    with patch("requests.Session") as factory, patch("subprocess.run") as browser:
        factory.return_value.head.side_effect = failure("transport failure")
        assert verify_module._check_url("https://example.com") == "fetch_failed"
        factory.return_value.get.assert_not_called()
        browser.assert_not_called()


@pytest.mark.parametrize("history,expected", [([], "200"), ([object()], "redirect")])
def test_url_head_success_preserves_redirect_result(history, expected) -> None:
    with patch("requests.Session") as factory, patch("subprocess.run") as browser:
        factory.return_value.head.return_value = SimpleNamespace(status_code=200, history=history)
        assert verify_module._check_url("https://example.com") == expected
        factory.return_value.get.assert_not_called()
        browser.assert_not_called()


@pytest.mark.parametrize("status", [403, 404, 405, 501])
def test_url_get_recovers_head_botblock(status) -> None:
    with patch("requests.Session") as factory, patch("subprocess.run") as browser:
        factory.return_value.head.return_value.status_code = status
        response = Mock(status_code=200, history=[])
        factory.return_value.get.return_value = response
        assert verify_module._check_url("https://example.com") == "200"
        response.close.assert_called_once_with()
        browser.assert_not_called()


@pytest.mark.parametrize(
    "result,expected",
    [(SimpleNamespace(returncode=0, stdout="page"), "200"),
     (SimpleNamespace(returncode=0, stdout="  "), "404"),
     (SimpleNamespace(returncode=1, stdout="error"), "404"),
     (FileNotFoundError(), "404"),
     (subprocess.TimeoutExpired("lightpanda", 15), "404")],
)
def test_url_get_transport_failure_preserves_browser_fallback(result, expected) -> None:
    with patch("requests.Session") as factory, patch("subprocess.run") as browser:
        factory.return_value.head.return_value.status_code = 403
        factory.return_value.get.side_effect = requests.Timeout("GET timeout")
        if isinstance(result, BaseException):
            browser.side_effect = result
        else:
            browser.return_value = result
        assert verify_module._check_url("https://example.com") == expected
        browser.assert_called_once_with(
            ["lightpanda", "fetch", "--dump", "markdown", "https://example.com"],
            capture_output=True, text=True, timeout=15, check=False,
        )


@pytest.mark.parametrize("method", ["head", "get"])
@pytest.mark.parametrize("error", [TypeError, AttributeError])
def test_url_check_does_not_mask_programming_errors(method, error) -> None:
    with patch("requests.Session") as factory, patch("subprocess.run") as browser:
        factory.return_value.head.return_value.status_code = 403
        getattr(factory.return_value, method).side_effect = error("programming error")
        with pytest.raises(error, match="programming error"):
            verify_module._check_url("https://example.com")
        browser.assert_not_called()


@pytest.mark.parametrize("method,expected", [("head", "fetch_failed"), ("get", "200")])
def test_malformed_redirect_is_remote_input_failure(method, expected) -> None:
    session = requests.Session()
    response = requests.Response()
    response.status_code = 302
    response.headers["Location"] = "http://[bad/"
    response.url = "https://example.com"
    response._content = b""
    prepared = requests.Request("HEAD", response.url).prepare()

    def malformed_redirect(*args, **kwargs):
        return list(session.resolve_redirects(response, prepared))

    with patch("requests.Session") as factory, patch("subprocess.run") as browser:
        factory.return_value.head.return_value.status_code = 403
        getattr(factory.return_value, method).side_effect = malformed_redirect
        browser.return_value = SimpleNamespace(returncode=0, stdout="page")
        assert verify_module._check_url(response.url) == expected
        assert browser.call_count == (method == "get")
