"""Unit tests for the ``AgyAdapter`` Antigravity CLI integration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_runtime.adapters.agy import AgyAdapter


def _build(mode: str, *, tool_config: dict | None = None) -> list[str]:
    adapter = AgyAdapter()
    plan = adapter.build_invocation(
        prompt="p",
        mode=mode,
        cwd=Path("/tmp"),
        model="gemini-3.8-flash-high",
        task_id=None,
        session_id=None,
        tool_config=tool_config,
    )
    return plan.cmd


def test_write_modes_explicitly_include_permission_bypass(monkeypatch) -> None:
    """The existing write route stays explicit; it is not read-only."""
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", lambda _: "agy")

    for mode in ("workspace-write", "danger"):
        cmd = _build(mode)
        assert cmd == [
            "agy",
            "-p",
            "p",
            "--dangerously-skip-permissions",
            "--add-dir",
            "/tmp",
            "--print-timeout",
            "3590s",
            "--model",
            "Gemini 3.8 Flash (High)",
        ], (
            f"mode={mode} must produce the same cmd because agy has no "
            f"mode-specific permission flag"
        )


def test_build_invocation_print_timeout_derived_from_dispatch_hard_timeout(
    monkeypatch,
) -> None:
    """``--print-timeout`` tracks ``tool_config['hard_timeout']`` minus margin.

    Draft-class dispatches use a 3600s outer timeout; agy must receive a
    matching print-timeout so long-form authoring survives past the CLI's
    5m default (#2099).
    """
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", lambda _: "agy")
    adapter = AgyAdapter()

    plan = adapter.build_invocation(
        prompt="p",
        mode="danger",
        cwd=Path("/repo/.worktrees/x"),
        model="gemini-3.1-pro-high",
        task_id=None,
        session_id=None,
        tool_config={"hard_timeout": 3600},
    )

    idx = plan.cmd.index("--print-timeout")
    assert plan.cmd[idx + 1] == "3590s"


def test_build_invocation_maps_model_slug(monkeypatch) -> None:
    """A runtime model slug is mapped to agy's `--model` display string."""
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", lambda _: "agy")
    adapter = AgyAdapter()

    plan = adapter.build_invocation(
        prompt="p",
        mode="workspace-write",
        cwd=Path("/tmp"),
        model="gemini-3.1-pro-high",
        task_id=None,
        session_id=None,
        tool_config=None,
    )

    assert "--model" in plan.cmd
    assert plan.cmd[plan.cmd.index("--model") + 1] == "Gemini 3.1 Pro (High)"


def test_build_invocation_accepts_display_string(monkeypatch) -> None:
    """Passing the canonical display string maps to itself (idempotent)."""
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", lambda _: "agy")
    adapter = AgyAdapter()

    plan = adapter.build_invocation(
        prompt="p",
        mode="workspace-write",
        cwd=Path("/tmp"),
        model="Gemini 3.1 Pro (High)",
        task_id=None,
        session_id=None,
        tool_config=None,
    )

    assert plan.cmd[plan.cmd.index("--model") + 1] == "Gemini 3.1 Pro (High)"


@pytest.mark.parametrize("model", ["tui-controlled", "gemini-4-nonexistent", ""])
def test_explicit_unknown_models_never_substitute(model) -> None:
    with pytest.raises(ValueError, match="no substitution"):
        AgyAdapter()._resolve_model_flag(model)


def test_argon_model_resolves_exactly() -> None:
    for model in ("gemini-4-argon-high", "Gemini 4 Argon (High)"):
        assert AgyAdapter()._resolve_model_flag(model) == "Gemini 4 Argon (High)"


def test_read_only_route_refuses_before_binary_lookup(monkeypatch) -> None:
    def unexpected_lookup(_):
        pytest.fail("read-only route must refuse before binary lookup or spawn")
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", unexpected_lookup)
    with pytest.raises(ValueError, match="read-only route disabled"):
        _build("read-only")


def test_build_invocation_with_session_id(monkeypatch) -> None:
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", lambda _: "agy")
    adapter = AgyAdapter()
    session_id = "123e4567-e89b-12d3-a456-426614174000"

    plan = adapter.build_invocation(
        prompt="p",
        mode="workspace-write",
        cwd=Path("/tmp"),
        model="gemini-3.8-flash-high",
        task_id=None,
        session_id=session_id,
        tool_config=None,
    )

    assert f"--conversation={session_id}" in plan.cmd


def test_build_invocation_uses_home_fallback(monkeypatch) -> None:
    monkeypatch.setattr("agent_runtime.adapters.agy.shutil.which", lambda _: None)
    adapter = AgyAdapter()

    plan = adapter.build_invocation(
        prompt="p",
        mode="workspace-write",
        cwd=Path("/tmp"),
        model=None,
        task_id=None,
        session_id=None,
        tool_config=None,
    )

    assert plan.cmd[0].endswith("/.local/bin/agy")
    assert plan.stdin_payload == ""


def test_parse_response_happy_path() -> None:
    adapter = AgyAdapter()
    result = adapter.parse_response(
        stdout="Answer\n",
        stderr="",
        returncode=0,
        output_file=None,
    )

    assert result.ok is True
    assert result.response == "Answer"
    assert result.rate_limited is False
    assert result.session_id is None
    assert result.tokens is None
    # stderr_excerpt is documented as a diagnostic signal — None when no
    # diagnostic output. Don't pollute it with informational notes.
    assert result.stderr_excerpt is None


def test_parse_response_empty_stdout_happy_returncode_fails() -> None:
    """Successful exit + no stdout is not a successful call."""
    adapter = AgyAdapter()
    result = adapter.parse_response(
        stdout="",
        stderr="",
        returncode=0,
        output_file=None,
    )

    assert result.ok is False
    assert result.response == ""
    assert result.rate_limited is False
    assert result.stderr_excerpt is None


def test_parse_response_detects_rate_limit() -> None:
    adapter = AgyAdapter()
    result = adapter.parse_response(
        stdout="",
        stderr="RESOURCE_EXHAUSTED: quota exceeded",
        returncode=1,
        output_file=None,
    )

    assert result.rate_limited is True
    assert result.ok is False
    assert result.response == ""


def test_adapter_requires_file_change_on_write() -> None:
    """AgyAdapter opts into the runner's file-change guard.

    agy `-p` can exit 0 having written no file (the #2099 headless no-write
    flake). The capability flag tells the runner to treat a write-mode run
    that left the worktree byte-identical as a retryable error instead of a
    silent false-success.
    """
    assert AgyAdapter.require_file_change_on_write is True
