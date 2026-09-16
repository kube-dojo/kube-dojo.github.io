from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from agent_runtime.tool_config import build_mcp_tool_config


def test_build_mcp_tool_config_qwen_residual_hermes_lane() -> None:
    """Only residual qwen still advertises hermes_mcp_servers observability."""
    tool_config, diagnostics = build_mcp_tool_config("qwen", mcp_servers=["sources"])

    assert tool_config == {"hermes_mcp_servers": ["sources"]}
    assert diagnostics["resolution_status"] == "ok"
    assert diagnostics["requested_servers"] == ["sources"]
    assert diagnostics["resolved_servers"] == ["sources"]
    assert diagnostics["config_path"].endswith(".hermes/config.yaml")


def test_build_mcp_tool_config_deepseek_no_longer_hermes_lane() -> None:
    """DeepSeek now rides opencode — not the hermes MCP observability path."""
    tool_config, diagnostics = build_mcp_tool_config("deepseek", mcp_servers=["sources"])
    # Without a matching non-hermes MCP builder, deepseek should not get
    # hermes_mcp_servers stamped (canonical agent falls through).
    assert tool_config is None or "hermes_mcp_servers" not in (tool_config or {})
    assert diagnostics["resolution_status"] in {
        "ok",
        "config_missing",
        "config_empty",
        "servers_not_found",
    }


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
