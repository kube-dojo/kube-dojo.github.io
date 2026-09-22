"""Shared constants and environment configuration for the AI Agent Bridge."""

import os
import shutil
from pathlib import Path

try:
    from agent_runtime.env_sanitize import build_agent_env
except ImportError:  # pragma: no cover - package import mode
    from scripts.agent_runtime.env_sanitize import build_agent_env

# Repo root for path resolution
REPO_ROOT = Path(
    os.environ.get("AB_REPO_ROOT", str(Path(__file__).parent.parent.parent))
)

def _resolve_db_path() -> Path:
    explicit = os.environ.get("AB_DB_PATH")
    if explicit:
        return Path(explicit)

    bridge_path = REPO_ROOT / ".bridge" / "messages.db"
    mcp_path = REPO_ROOT / ".mcp" / "servers" / "message-broker" / "messages.db"
    for path in (bridge_path, mcp_path):
        if path.exists():
            return path
    return bridge_path


DB_PATH = _resolve_db_path()
PID_DIR = Path(
    os.environ.get(
        "AB_PID_DIR",
        str(REPO_ROOT / ".mcp" / "servers" / "message-broker" / "pids"),
    )
)

# Resolve CLI paths at import time (before detached children lose PATH)
# Use npx to run Claude Code — avoids bugs in the globally installed version.
# Returns a list: ["npx", "@anthropic-ai/claude-code"] to use as cmd prefix.
CLAUDE_CMD = ["npx", "@anthropic-ai/claude-code@latest"]
GEMINI_CLI = shutil.which("gemini") or "gemini"
CODEX_CLI = shutil.which("codex") or "codex"
CLAUDE_DEFAULT_MODEL = os.environ.get("AB_CLAUDE_MODEL", "claude-opus-5-5")
PYTHON_CMD = os.environ.get("AB_PYTHON", "")
if not PYTHON_CMD:
    if virtual_env := os.environ.get("VIRTUAL_ENV"):
        PYTHON_CMD = str(Path(virtual_env) / "bin" / "python")
    else:
        PYTHON_CMD = ".venv/bin/python"
GEMINI_REVIEW_MODEL = os.environ.get(
    "AB_GEMINI_REVIEW_MODEL", "gemini-3.1-pro-preview"
)
GEMINI_FALLBACK_MODEL = os.environ.get(
    "AB_GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview"
)
GEMINI_DEFAULT_MODEL = os.environ.get("AB_GEMINI_MODEL", "")
if not GEMINI_DEFAULT_MODEL:
    try:
        from batch_gemini_config import FLASH_MODEL

        GEMINI_DEFAULT_MODEL = FLASH_MODEL
    except ImportError:
        GEMINI_DEFAULT_MODEL = GEMINI_FALLBACK_MODEL

_PIPELINE_ENV_KEY = os.environ.get(
    "AB_PIPELINE_ENV_KEY", "KUBEDOJO_PIPELINE"
)
_BASE_AGENT_ENV_OVERRIDES = {
    "GEMINI_SESSION": "1",
    _PIPELINE_ENV_KEY: "1",  # Suppress inbox hooks during pipeline runs.
}


def agent_child_env(
    provider: str | None = None,
    overrides: dict[str, str | None] | None = None,
) -> dict[str, str]:
    """Return a sanitized env scoped to one bridge child provider."""
    merged_overrides = {**_BASE_AGENT_ENV_OVERRIDES}
    if overrides:
        merged_overrides.update(overrides)
    env = build_agent_env(provider=provider, overrides=merged_overrides)
    if provider == "gemini" and os.environ.get("KUBEDOJO_GEMINI_SUBSCRIPTION") == "1":
        env.pop("GEMINI_API_KEY", None)
        env.pop("GOOGLE_API_KEY", None)
    return env


# Generic sanitized snapshot for compatibility. Provider subprocesses should
# call agent_child_env("gemini"|"claude"|"codex") instead of using this.
_PARENT_ENV = agent_child_env()
# Gemini auth: CLI prefers GEMINI_API_KEY when set; otherwise falls
# through to OAuth/subscription creds in ~/.gemini/oauth_creds.json.
# When the API-key tier is rate-limited, set
# KUBEDOJO_GEMINI_SUBSCRIPTION=1 to strip the key from child env so
# dispatches use the subscription path instead.
if os.environ.get("KUBEDOJO_GEMINI_SUBSCRIPTION") == "1":
    _PARENT_ENV.pop("GEMINI_API_KEY", None)
    _PARENT_ENV.pop("GOOGLE_API_KEY", None)

# Model availability cache: {model: (available: bool, timestamp: float)}
# Avoids burning API quota on repeated checks within the same session.
_MODEL_CACHE: dict[str, tuple[bool, float]] = {}
_MODEL_CACHE_TTL = 3600  # 1 hour — re-check after this

# GitHub comment/body limit is 65,536 chars. Use 64K with 1.5K safety margin for headers.
GH_CHAR_LIMIT = 64000
