"""Regression: headless Claude delegate/dispatch must not load user MCP schemas."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dispatch_smart
from dispatch_smart import (
    CLAUDE_DELEGATE_ALLOWED_TOOLS,
    CLAUDE_DELEGATE_MCP_CONFIG,
    merge_delegate_claude_tool_config,
)


def test_delegate_mcp_fixture_is_empty_servers() -> None:
    assert CLAUDE_DELEGATE_MCP_CONFIG.is_file()
    payload = json.loads(CLAUDE_DELEGATE_MCP_CONFIG.read_text(encoding="utf-8"))
    assert payload == {"mcpServers": {}}


def test_merge_skips_non_claude_and_bridge() -> None:
    assert merge_delegate_claude_tool_config("codex", "delegate", None) is None
    assert merge_delegate_claude_tool_config(
        "claude",
        "bridge",
        {"is_new_session": True},
    ) == {"is_new_session": True}


def test_merge_respects_caller_override() -> None:
    custom = {
        "mcp_config_path": "/tmp/custom.mcp.json",
        "allowed_tools": "mcp__rag__verify_word,Read",
    }
    assert merge_delegate_claude_tool_config("claude", "delegate", custom) == custom


@pytest.mark.parametrize("entrypoint", ["delegate", "dispatch"])
def test_merge_applies_minimal_mcp_for_claude_delegate(entrypoint: str) -> None:
    merged = merge_delegate_claude_tool_config("claude", entrypoint, None)
    assert merged is not None
    assert merged["mcp_config_path"] == str(CLAUDE_DELEGATE_MCP_CONFIG)
    assert merged["allowed_tools"] == CLAUDE_DELEGATE_ALLOWED_TOOLS
    assert "mcp__" not in merged["allowed_tools"]


def test_merge_skips_when_fixture_missing() -> None:
    """If the minimal MCP fixture is absent, the merge is a no-op (graceful)."""
    fake_missing = SimpleNamespace(is_file=lambda: False)
    with patch.object(dispatch_smart, "CLAUDE_DELEGATE_MCP_CONFIG", fake_missing):
        assert merge_delegate_claude_tool_config("claude", "delegate", None) is None
        passthrough = {"is_new_session": True}
        assert (
            merge_delegate_claude_tool_config("claude", "delegate", passthrough)
            is passthrough
        )


def test_claude_adapter_emits_mcp_flags_for_delegate_tool_config() -> None:
    # Pins the in-tree fork adapter's argv for the delegate config; the shared
    # ClaudeAdapter's equivalent is not yet verifiable (see the package-5 census).
    from agent_runtime.adapters.claude import ClaudeAdapter

    tc = merge_delegate_claude_tool_config("claude", "delegate", None)
    plan = ClaudeAdapter().build_invocation(
        prompt="brief",
        mode="danger",
        cwd=Path.cwd(),
        model="claude-sonnet-4-6",
        task_id="t1",
        session_id=None,
        tool_config=tc,
    )
    assert "--mcp-config" in plan.cmd
    idx = plan.cmd.index("--mcp-config")
    assert plan.cmd[idx + 1] == str(CLAUDE_DELEGATE_MCP_CONFIG)
    tools_idx = plan.cmd.index("--allowedTools")
    allowed = plan.cmd[tools_idx + 1]
    assert allowed == CLAUDE_DELEGATE_ALLOWED_TOOLS
    assert "mcp__" not in allowed


def test_fire_passes_delegate_mcp_tool_config_to_runtime(monkeypatch, tmp_path) -> None:
    """The shared runtime does not merge the KubeDojo delegate default; fire does."""
    captured: dict[str, object] = {}

    def fake_invoke(agent, prompt, **kw):
        captured["agent"] = agent
        captured["tool_config"] = kw["tool_config"]
        captured["entrypoint"] = kw["entrypoint"]
        return SimpleNamespace(ok=True, response="ok", session_id=None, stderr_excerpt="")

    monkeypatch.setattr("lu_machinery.agent_runtime.runner.invoke", fake_invoke)
    monkeypatch.setattr(dispatch_smart, "append_log", lambda *_a, **_k: None)
    monkeypatch.setattr(
        dispatch_smart,
        "persist_response",
        lambda task_id, *_a, **_k: dispatch_smart.PRIMARY_REPO / "logs" / f"{task_id}.txt",
    )

    code = dispatch_smart.fire(
        agent="claude",
        task_class="search",
        prompt="search task",
        mode="read-only",
        model="claude-haiku-4-5-20251001",
        worktree=None,
        task_id="t-delegate",
        timeout_s=1,
    )

    assert code == 0
    assert captured["agent"] == "claude"
    assert captured["entrypoint"] == "delegate"
    tc = captured["tool_config"]
    assert isinstance(tc, dict)
    assert tc["mcp_config_path"] == str(CLAUDE_DELEGATE_MCP_CONFIG)
    assert "mcp__" not in tc["allowed_tools"]
