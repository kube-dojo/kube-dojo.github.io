"""Regression tests for #2134 — clean Sonnet + sources-MCP author lane.

Covers the three gaps closed by #2134:
  1. draft/edit are MCP-enabled task classes for claude and resolve the
     WRITE-capable author allowlist (Write/Edit/MultiEdit) rather than the
     read-only review allowlist.
  2. the curated tool names target the live ``sources`` server
     (``mcp__sources__*``), not the dead ``mcp__rag__*`` prefix.
  3. reasoning effort is plumbed to Claude Code's ``--effort`` flag, including
     via a ``-high``/``-medium``/``-low`` model-slug suffix.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import dispatch_smart


def test_draft_and_edit_are_claude_mcp_task_classes() -> None:
    assert {"draft", "edit"} <= dispatch_smart.CLAUDE_MCP_TASK_CLASSES
    assert {"review", "search"} <= dispatch_smart.CLAUDE_MCP_TASK_CLASSES
    assert dispatch_smart.CLAUDE_MCP_AUTHOR_TASK_CLASSES == frozenset({"draft", "edit"})


def test_author_classes_get_write_capable_tools() -> None:
    _, draft_tools = dispatch_smart._import_dispatch_mcp_constants("draft")
    _, edit_tools = dispatch_smart._import_dispatch_mcp_constants("edit")
    for tools in (draft_tools, edit_tools):
        assert "Write" in tools.split(",")
        assert "Edit" in tools.split(",")
        assert "MultiEdit" in tools.split(",")
        # authors still get the sources verification tools
        assert "mcp__sources__verify_word" in tools


def test_read_classes_stay_read_only() -> None:
    _, review_tools = dispatch_smart._import_dispatch_mcp_constants("review")
    tool_set = review_tools.split(",")
    assert "Write" not in tool_set
    assert "Edit" not in tool_set
    assert "MultiEdit" not in tool_set
    assert "mcp__sources__verify_word" in tool_set


def test_tools_target_sources_server_not_dead_rag_prefix() -> None:
    _, review_tools = dispatch_smart._import_dispatch_mcp_constants("review")
    _, author_tools = dispatch_smart._import_dispatch_mcp_constants("draft")
    for tools in (review_tools, author_tools):
        assert "mcp__rag__" not in tools
        assert "mcp__sources__" in tools


def _fork_claude_adapter():
    """The in-tree fork ClaudeAdapter these effort tests pin.

    The shared lu_machinery ClaudeAdapter is not yet verifiable here (see the
    package-5 census), so only these adapter tests still need the fork.
    """
    from agent_runtime.adapters.claude import ClaudeAdapter

    return ClaudeAdapter()


def _model_and_effort(cmd: list[str]) -> tuple[str | None, str | None]:
    model = cmd[cmd.index("--model") + 1] if "--model" in cmd else None
    effort = cmd[cmd.index("--effort") + 1] if "--effort" in cmd else None
    return model, effort


def test_effort_suffix_is_stripped_to_effort_flag() -> None:
    plan = _fork_claude_adapter().build_invocation(
        prompt="x", mode="workspace-write", cwd=Path("."),
        model="claude-sonnet-5-high", task_id="t", session_id=None,
        tool_config={},
    )
    assert _model_and_effort(plan.cmd) == ("claude-sonnet-5", "high")


def test_plain_model_id_is_not_stripped() -> None:
    plan = _fork_claude_adapter().build_invocation(
        prompt="x", mode="read-only", cwd=Path("."),
        model="claude-opus-4-8", task_id="t", session_id=None,
        tool_config={},
    )
    model, effort = _model_and_effort(plan.cmd)
    assert model == "claude-opus-4-8"
    assert effort is None


def test_explicit_effort_in_tool_config_wins() -> None:
    plan = _fork_claude_adapter().build_invocation(
        prompt="x", mode="read-only", cwd=Path("."),
        model="claude-sonnet-5", task_id="t", session_id=None,
        tool_config={"effort": "medium"},
    )
    assert _model_and_effort(plan.cmd) == ("claude-sonnet-5", "medium")


def test_suffix_is_stripped_even_when_explicit_effort_set() -> None:
    """Model slug carries a -high suffix AND explicit effort is given: the suffix
    must still be stripped from --model (it is not a real model id), and the
    explicit effort wins. Regression for the codex R1 finding on #2227/#2134."""
    plan = _fork_claude_adapter().build_invocation(
        prompt="x", mode="read-only", cwd=Path("."),
        model="claude-sonnet-5-high", task_id="t", session_id=None,
        tool_config={"effort": "medium"},
    )
    assert _model_and_effort(plan.cmd) == ("claude-sonnet-5", "medium")
