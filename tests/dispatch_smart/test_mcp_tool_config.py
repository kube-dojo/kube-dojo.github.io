from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def test_mcp_supported_agents_claude_only_after_hermes_retirement() -> None:
    """Hermes MCP retired with --agent hermes / deepseek-opencode move (#2131)."""
    import importlib

    dispatch_smart = importlib.import_module("dispatch_smart")

    assert dispatch_smart.MCP_SUPPORTED_AGENTS == frozenset({"claude"})
    assert dispatch_smart.HERMES_MCP_AGENTS == frozenset()
    assert "deepseek" not in dispatch_smart.MCP_SUPPORTED_AGENTS
    assert "grok" not in dispatch_smart.MCP_SUPPORTED_AGENTS
    assert "qwen" not in dispatch_smart.MCP_SUPPORTED_AGENTS


def test_available_hermes_mcp_servers_always_empty() -> None:
    """Hermes MCP discovery helper is a retired stub."""
    import importlib

    dispatch_smart = importlib.import_module("dispatch_smart")
    assert dispatch_smart._available_hermes_mcp_servers() == []
