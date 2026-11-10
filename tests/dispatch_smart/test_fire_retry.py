"""Regression tests for #2099 — agy headless-dispatch retry hardening.

Covers the exponential-backoff retry loop added to ``dispatch_smart.fire`` so a
transient agy dispatch flake recovers instead of failing the whole run, and
confirms non-agy agents keep single-attempt behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import dispatch_smart
from lu_machinery.agent_runtime.errors import AgentTimeoutError


def _stub_dispatch_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    task_id: str,
) -> None:
    """Avoid slow side effects while still exercising fire() control flow."""

    monkeypatch.setattr(dispatch_smart.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(dispatch_smart, "append_log", lambda *_args, **_kwargs: None)
    dummy_path = dispatch_smart.PRIMARY_REPO / "logs" / "dispatch_responses" / f"{task_id}.txt"
    monkeypatch.setattr(
        dispatch_smart,
        "persist_response",
        lambda *_args, **_kwargs: dummy_path,
    )


def test_dispatch_smart_fire_retries_agy_after_timeout(monkeypatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A write-class agy call retries a transient timeout. Review and search are refused (#3746)."""

    _stub_dispatch_side_effects(monkeypatch, task_id="agy-retry")

    calls: list[int] = [0]

    def fake_invoke(*_args, **_kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise AgentTimeoutError("agy", 1)
        return SimpleNamespace(
            ok=True,
            response="OK",
            session_id="session-1",
            stderr_excerpt="",
        )

    monkeypatch.setattr("lu_machinery.agent_runtime.runner.invoke", fake_invoke)

    code = dispatch_smart.fire(
        agent="agy",
        task_class="edit",
        prompt="test prompt",
        mode="danger",
        model="gpt-5.5",
        worktree=None,
        task_id="agy-retry",
        timeout_s=1,
    )
    captured = capsys.readouterr()

    assert code == 0
    assert calls[0] == 2
    assert "retrying 1/3" in captured.out
    assert "OK: True" in captured.out


def test_dispatch_smart_fire_non_agy_does_not_retry_after_failed_result(
    monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Agents other than agy keep max_retries=1 for failed non-exception results."""

    _stub_dispatch_side_effects(monkeypatch, task_id="codex-no-retry")

    calls: list[int] = [0]

    def fake_invoke(*_args, **_kwargs):
        calls[0] += 1
        return SimpleNamespace(
            ok=False,
            response="",
            session_id=None,
            stderr_excerpt="not ok",
        )

    monkeypatch.setattr("lu_machinery.agent_runtime.runner.invoke", fake_invoke)

    code = dispatch_smart.fire(
        agent="codex",
        task_class="draft",
        prompt="test prompt",
        mode="danger",
        model="gpt-5.5",
        worktree=None,
        task_id="codex-no-retry",
        timeout_s=1,
    )
    captured = capsys.readouterr()

    assert code == 1
    assert calls[0] == 1
    assert "retrying" not in captured.out
    assert "OK: False" in captured.out
