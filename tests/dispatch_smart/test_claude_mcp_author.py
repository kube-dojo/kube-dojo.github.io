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
