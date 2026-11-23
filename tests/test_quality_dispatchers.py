"""Tests for ``scripts.quality.dispatchers``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.quality import dispatchers  # noqa: E402


def test_writer_for_index_returns_codex_writes_claude_reviews_for_every_index() -> None:
    """Even/odd alternation was retired 2026-04-25 after empirical evidence
    that claude-as-writer lands ~440-line modules vs codex's 1500–2000+.

    Regression guard: every index — even, odd, large, zero — must return
    ``("codex", "claude")``. Cross-family review is still satisfied
    (different model families).
    """
    for idx in (0, 1, 2, 50, 100, 741, 742, 1000):
        assert dispatchers.writer_for_index(idx) == ("codex", "claude"), idx


def test_tiebreaker_is_agy() -> None:
    # gemini-cli retired (#2125); the independent third-party lane is now agy.
    assert dispatchers.tiebreaker_agent() == "agy"


def test_dispatch_rejects_unknown_agent() -> None:
    with pytest.raises(ValueError, match="unknown agent"):
        dispatchers.dispatch("madeup", "prompt", timeout=10)  # type: ignore[arg-type]


def test_looks_unavailable_detects_budget() -> None:
    assert dispatchers._looks_unavailable("ClaudeUnavailableError: call budget exhausted")


def test_looks_unavailable_detects_rate_limit() -> None:
    assert dispatchers._looks_unavailable("gemini: RATE_LIMIT — slow down")


def test_looks_unavailable_false_for_real_errors() -> None:
    assert not dispatchers._looks_unavailable("SyntaxError: unexpected token")
    assert not dispatchers._looks_unavailable("")


def test_dispatcher_unavailable_is_runtime_error() -> None:
    # Sanity — callers rely on catching RuntimeError for retry logic.
    assert issubclass(dispatchers.DispatcherUnavailable, RuntimeError)


class _FakeRuntimeResult:
    def __init__(self, *, ok: bool = True, response: str = "", stderr_excerpt: str = "", returncode: int | None = 0):
        self.ok = ok
        self.response = response
        self.stderr_excerpt = stderr_excerpt
        self.returncode = returncode


def test_dispatch_result_fields_populated(monkeypatch) -> None:
    """Dispatch surfaces response/stderr/returncode/duration from agent_runtime."""
    captured: dict = {}

    def fake_invoke(agent, prompt, **kwargs):
        captured["agent"] = agent
        captured["kwargs"] = kwargs
        return _FakeRuntimeResult(ok=True, response="verdict output", stderr_excerpt="", returncode=0)

    monkeypatch.setattr(dispatchers, "invoke", fake_invoke)
    result = dispatchers.dispatch("gemini", "prompt", timeout=10)
    assert captured["agent"] == "agy"
    assert result.ok is True
    assert result.stdout == "verdict output"
    assert result.returncode == 0
    assert result.agent == "gemini"
    assert result.duration_sec >= 0


def test_dispatch_raises_unavailable_on_marker(monkeypatch) -> None:
    monkeypatch.setattr(
        dispatchers,
        "invoke",
        lambda *a, **k: _FakeRuntimeResult(ok=False, response="", stderr_excerpt="Claude call budget exhausted", returncode=1),
    )
    with pytest.raises(dispatchers.DispatcherUnavailable):
        dispatchers.dispatch("claude", "prompt", timeout=10)


def test_dispatch_raises_unavailable_on_rate_limited_error(monkeypatch) -> None:
    def raise_rl(*a, **k):
        raise dispatchers.RateLimitedError("claude", "claude-sonnet-5-5", "429 quota")

    monkeypatch.setattr(dispatchers, "invoke", raise_rl)
    with pytest.raises(dispatchers.DispatcherUnavailable):
        dispatchers.dispatch("claude", "prompt", timeout=10)


def test_dispatch_returns_failure_not_unavailable_for_real_errors(monkeypatch) -> None:
    """Non-zero exit without an unavailability marker must surface as
    ``ok=False``, not raise — caller decides retry vs FAILED."""
    monkeypatch.setattr(
        dispatchers,
        "invoke",
        lambda *a, **k: _FakeRuntimeResult(ok=False, response="", stderr_excerpt="SyntaxError in prompt", returncode=1),
    )
    result = dispatchers.dispatch("codex", "prompt", timeout=10)
    assert result.ok is False
    assert "SyntaxError" in result.stderr


def test_dispatch_timeout_returns_failure(monkeypatch) -> None:
    def raise_timeout(*a, **k):
        raise dispatchers.AgentTimeoutError("agy", 10)

    monkeypatch.setattr(dispatchers, "invoke", raise_timeout)
    result = dispatchers.dispatch("gemini", "prompt", timeout=10)
    assert result.ok is False
    assert "timeout" in result.stderr.lower()


def test_dispatch_passes_empty_allowed_tools_for_claude_when_tools_disabled(monkeypatch) -> None:
    """Claude writer/reviewer dispatches must disable tools via ``tool_config``
    so the CLI returns text-only output rather than editing files in cwd."""
    captured: dict = {}

    def capture_invoke(agent, prompt, **kwargs):
        captured["agent"] = agent
        captured["kwargs"] = kwargs
        return _FakeRuntimeResult(ok=True, response="ok")

    monkeypatch.setattr(dispatchers, "invoke", capture_invoke)
    dispatchers.dispatch("claude", "prompt", timeout=10, tools_disabled=True)
    assert captured["kwargs"]["tool_config"] == {"allowed_tools": ""}


def test_dispatch_omits_tool_config_when_not_requested(monkeypatch) -> None:
    """Default (citation_verify, translation, etc.) must leave tool_config=None."""
    captured: dict = {}

    def capture_invoke(agent, prompt, **kwargs):
        captured["kwargs"] = kwargs
        return _FakeRuntimeResult(ok=True, response="ok")

    monkeypatch.setattr(dispatchers, "invoke", capture_invoke)
    dispatchers.dispatch("claude", "prompt", timeout=10)
    assert captured["kwargs"]["tool_config"] is None


def test_dispatch_tools_disabled_only_for_claude(monkeypatch) -> None:
    """Codex/Gemini do not set Claude tool_config when tools_disabled=True."""
    captured: dict = {}

    def capture_invoke(agent, prompt, **kwargs):
        captured["kwargs"] = kwargs
        return _FakeRuntimeResult(ok=True, response="ok")

    monkeypatch.setattr(dispatchers, "invoke", capture_invoke)
    dispatchers.dispatch("codex", "prompt", timeout=10, tools_disabled=True)
    assert captured["kwargs"]["tool_config"] is None
    captured.clear()
    dispatchers.dispatch("gemini", "prompt", timeout=10, tools_disabled=True)
    assert captured["kwargs"]["tool_config"] is None
