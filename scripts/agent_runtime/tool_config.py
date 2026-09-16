"""Shared MCP tool_config builders for agent_runtime callers."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MCP_CONFIG_PATH = _REPO_ROOT / ".mcp.json"
_AGY_APP_DATA_ENV = "AGY_APP_DATA_DIR"
_DEFAULT_AGY_APP_DATA_DIR = "~/.gemini/antigravity-cli"
_HERMES_CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"
_RESOLUTION_STATUSES = {"ok", "config_missing", "config_empty", "servers_not_found"}
_CODEX_MCP_SERVER_FIELDS = frozenset(
    {
        "url",
        "command",
        "args",
        "env",
        "bearer_token_env_var",
    }
)
_HERMES_LANE_AGENTS = frozenset({"qwen"})  # residual hermes transport; deepseek/grok/hermes retired


def _canonical_agent_name(agent: str) -> str | None:
    """Normalize caller-facing agent labels to runtime adapter names."""
    if agent.startswith("claude"):
        return "claude"
    if agent.startswith("codex"):
        return "codex"
    if agent.startswith("grok-build"):
        return "grok-build"
    if agent.startswith("grok"):
        return "grok"
    if agent.startswith("deepseek"):
        return "deepseek"
    if agent.startswith("qwen"):
        return "qwen"
    if agent.startswith("hermes"):
        return "hermes"
    if agent.startswith("agy"):
        return "agy"
    if agent.startswith("cursor"):
        return "cursor"
    return None


def _resolved_mcp_config_path(mcp_config_path: Path | None) -> Path:
    """Return the configured ``.mcp.json`` path, defaulting to repo root."""
    return (mcp_config_path or _DEFAULT_MCP_CONFIG_PATH).resolve()


def _resolved_agy_mcp_config_path() -> Path:
    """Return agy's global Antigravity MCP config path."""
    app_data_dir = os.environ.get(_AGY_APP_DATA_ENV, _DEFAULT_AGY_APP_DATA_DIR)
    return (Path(app_data_dir).expanduser() / "mcp_config.json").resolve()


def _codex_sanitize_server_config(server_config: dict) -> dict:
    """Drop fields codex CLI's mcp_servers schema does not recognize."""
    return {k: v for k, v in server_config.items() if k in _CODEX_MCP_SERVER_FIELDS}


@lru_cache(maxsize=1)
def _load_mcp_config(mcp_config_path: Path) -> dict[str, Any] | None:
    """Load ``.mcp.json`` once per process for Codex MCP config shaping."""
    try:
        raw = json.loads(mcp_config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _basic_diagnostics(
    *,
    mcp_config_path: Path,
    requested_servers: list[str] | None,
    resolved_servers: list[str] | None,
    resolution_status: str,
    missing_server_names: list[str] | None = None,
) -> dict[str, Any]:
    assert resolution_status in _RESOLUTION_STATUSES
    return {
        "requested_servers": list(requested_servers or []),
        "resolved_servers": list(resolved_servers or []),
        "config_path": str(mcp_config_path),
        "resolution_status": resolution_status,
        "missing_server_names": list(missing_server_names or []),
    }


def _codex_server_is_usable(server_config: Any) -> bool:
    """Reject known-stale Codex MCP endpoint shapes before dispatch."""
    if not isinstance(server_config, dict):
        return False
    server_type = str(server_config.get("type") or "").strip().lower()
    url = str(server_config.get("url") or "").strip()
    command = str(server_config.get("command") or "").strip()
    if server_type == "sse":
        return False
    if url.rstrip("/").endswith("/sse"):
        return False
    return bool(url or command)


def _codex_mcp_servers(
    mcp_config_path: Path,
    requested_servers: list[str] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return Codex's nested ``mcp_servers`` config plus resolution diagnostics."""
    requested = list(requested_servers or [])

    def diagnostics(
        *,
        resolved_servers: list[str] | None = None,
        resolution_status: str,
        missing_server_names: list[str] | None = None,
    ) -> dict[str, Any]:
        assert resolution_status in _RESOLUTION_STATUSES
        return {
            "requested_servers": requested,
            "resolved_servers": resolved_servers or [],
            "config_path": str(mcp_config_path),
            "resolution_status": resolution_status,
            "missing_server_names": missing_server_names or [],
        }

    data = _load_mcp_config(mcp_config_path)
    if not data:
        return None, diagnostics(resolution_status="config_missing")

    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        return None, diagnostics(resolution_status="config_empty")

    usable_servers = {
        server_name: server_config
        for server_name, server_config in servers.items()
        if _codex_server_is_usable(server_config)
    }

    if not requested:
        if usable_servers:
            return (
                {
                    name: _codex_sanitize_server_config(cfg)
                    for name, cfg in usable_servers.items()
                },
                diagnostics(
                    resolved_servers=list(usable_servers),
                    resolution_status="ok",
                ),
            )
        return None, diagnostics(
            resolution_status="servers_not_found",
            missing_server_names=list(servers),
        )

    selected = {
        server_name: _codex_sanitize_server_config(usable_servers[server_name])
        for server_name in requested
        if server_name in usable_servers
    }
    missing = [server_name for server_name in requested if server_name not in selected]
    if not selected:
        return None, diagnostics(
            resolution_status="servers_not_found",
            missing_server_names=missing,
        )
    return selected, diagnostics(
        resolved_servers=list(selected),
        resolution_status="ok",
        missing_server_names=missing,
    )


def _agy_server_is_usable(server_config: Any) -> bool:
    """Return true for Antigravity streamable-HTTP or stdio MCP server entries."""
    if not isinstance(server_config, dict):
        return False
    http_url = str(server_config.get("httpUrl") or "").strip()
    url = str(server_config.get("url") or "").strip()
    command = str(server_config.get("command") or "").strip()
    return bool(http_url or url or command)


def _agy_mcp_servers(
    mcp_config_path: Path,
    requested_servers: list[str] | None,
) -> tuple[dict[str, list[str]] | None, dict[str, Any]]:
    """Return agy's requested MCP server names plus resolution diagnostics."""
    requested = list(requested_servers or [])

    data = _load_mcp_config(mcp_config_path)
    if not data:
        return None, _basic_diagnostics(
            mcp_config_path=mcp_config_path,
            requested_servers=requested,
            resolved_servers=None,
            resolution_status="config_empty",
        )

    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        return None, _basic_diagnostics(
            mcp_config_path=mcp_config_path,
            requested_servers=requested,
            resolved_servers=None,
            resolution_status="config_empty",
        )

    usable_server_names = [
        server_name
        for server_name, server_config in servers.items()
        if _agy_server_is_usable(server_config)
    ]
    if not requested or not usable_server_names:
        return None, _basic_diagnostics(
            mcp_config_path=mcp_config_path,
            requested_servers=requested,
            resolved_servers=None,
            resolution_status="config_empty",
            missing_server_names=requested,
        )

    usable_servers = set(usable_server_names)
    selected = [server_name for server_name in requested if server_name in usable_servers]
    missing = [server_name for server_name in requested if server_name not in usable_servers]
    if not selected:
        return None, _basic_diagnostics(
            mcp_config_path=mcp_config_path,
            requested_servers=requested,
            resolved_servers=None,
            resolution_status="servers_not_found",
            missing_server_names=missing,
        )

    return {"mcp_server_names": selected}, _basic_diagnostics(
        mcp_config_path=mcp_config_path,
        requested_servers=requested,
        resolved_servers=selected,
        resolution_status="ok",
        missing_server_names=missing,
    )


def _hermes_lane_tool_config(
    mcp_servers: list[str] | None,
) -> tuple[dict[str, list[str]] | None, dict[str, Any]]:
    """Return Hermes-lane MCP observability payload plus diagnostics."""
    requested = list(mcp_servers or [])
    if not requested:
        return None, _basic_diagnostics(
            mcp_config_path=_HERMES_CONFIG_PATH,
            requested_servers=requested,
            resolved_servers=None,
            resolution_status="config_empty",
        )
    return (
        {"hermes_mcp_servers": requested},
        _basic_diagnostics(
            mcp_config_path=_HERMES_CONFIG_PATH,
            requested_servers=requested,
            resolved_servers=requested,
            resolution_status="ok",
        ),
    )


def build_mcp_tool_config(
    agent: str,
    *,
    mcp_servers: list[str] | None = None,
    allowed_tools: str | None = None,
    mcp_config_path: Path | None = None,
) -> tuple[dict | None, dict[str, Any]]:
    """Build adapter-appropriate tool_config dict for MCP access.

    Returns ``(None, diagnostics)`` when the requested agent cannot be
    configured for MCP.
    """
    resolved_config_path = _resolved_mcp_config_path(mcp_config_path)
    canonical_agent = _canonical_agent_name(agent)
    if canonical_agent is None:
        return None, _basic_diagnostics(
            mcp_config_path=resolved_config_path,
            requested_servers=mcp_servers,
            resolved_servers=None,
            resolution_status="servers_not_found",
            missing_server_names=mcp_servers,
        )

    if canonical_agent == "claude":
        if not allowed_tools or not resolved_config_path.exists():
            return None, _basic_diagnostics(
                mcp_config_path=resolved_config_path,
                requested_servers=mcp_servers,
                resolved_servers=None,
                resolution_status=(
                    "config_missing"
                    if not resolved_config_path.exists()
                    else "config_empty"
                ),
            )
        return (
            {
                "mcp_config_path": str(resolved_config_path),
                "allowed_tools": allowed_tools,
            },
            _basic_diagnostics(
                mcp_config_path=resolved_config_path,
                requested_servers=mcp_servers,
                resolved_servers=mcp_servers,
                resolution_status="ok",
            ),
        )

    if canonical_agent == "agy":
        return _agy_mcp_servers(_resolved_agy_mcp_config_path(), mcp_servers)

    if canonical_agent in _HERMES_LANE_AGENTS:
        return _hermes_lane_tool_config(mcp_servers)

    if canonical_agent == "grok-build":
        if not mcp_servers:
            return None, _basic_diagnostics(
                mcp_config_path=Path.home() / ".grok" / "mcp.json",
                requested_servers=mcp_servers,
                resolved_servers=None,
                resolution_status="config_empty",
            )
        return (
            {
                "always_approve": True,
                "mcp_server_names": mcp_servers,
            },
            _basic_diagnostics(
                mcp_config_path=Path.home() / ".grok" / "mcp.json",
                requested_servers=mcp_servers,
                resolved_servers=mcp_servers,
                resolution_status="ok",
            ),
        )

    if canonical_agent == "cursor":
        workspace_mcp_path = Path.cwd() / ".cursor" / "mcp.json"
        return (
            {
                "output_format": "stream-json",
                "approve_mcps": True,
                "mcp_config_path": str(resolved_config_path),
                "mcp_server_names": mcp_servers,
            },
            _basic_diagnostics(
                mcp_config_path=workspace_mcp_path,
                requested_servers=mcp_servers,
                resolved_servers=mcp_servers,
                resolution_status="ok" if mcp_servers else "config_empty",
            ),
        )

    codex_servers, diagnostics = _codex_mcp_servers(resolved_config_path, mcp_servers)
    return ({"mcp_servers": codex_servers} if codex_servers else None), diagnostics
