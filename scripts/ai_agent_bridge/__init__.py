"""AI Agent Bridge - Multi-agent communication bridge via MCP Message Broker.

This package provides bidirectional communication between AI agents (Gemini, Claude)
using a shared SQLite database.

Configuration:
- ``AB_REPO_ROOT``: defaults to the package's containing repo root.
- ``AB_DB_PATH``: defaults to ``{REPO_ROOT}/.mcp/servers/message-broker/messages.db``.
- ``AB_PID_DIR``: defaults to ``{REPO_ROOT}/.mcp/servers/message-broker/pids``.
- ``AB_CONTEXT_DIR``: defaults to ``{REPO_ROOT}/docs/agent-channels``.
- ``AB_WAKE_DIR``: defaults to ``{REPO_ROOT}/.agent/wake``.
- ``AB_MONITOR_URL``: defaults to empty string (Monitor API disabled).
- ``AB_GEMINI_MODEL``: defaults to ``batch_gemini_config.FLASH_MODEL`` when importable,
  else ``gemini-3-flash-preview``.
- ``AB_GEMINI_REVIEW_MODEL``: defaults to ``gemini-3.1-pro-preview``.
- ``AB_GEMINI_FALLBACK_MODEL``: defaults to ``gemini-3-flash-preview``.
- ``AB_PYTHON``: defaults to ``$VIRTUAL_ENV/bin/python`` when set,
  else ``.venv/bin/python``.
- ``AB_PIPELINE_ENV_KEY``: defaults to ``LEARN_UKRAINIAN_PIPELINE``.

All public functions are re-exported here for backward compatibility.
"""

# Re-export everything that was previously importable from ai_agent_bridge
from ._broker import (
    _git_status_snapshot,
    _is_task_locked,
    _remove_pid_file,
    _validate_file_writes,
    _write_pid_file,
    bridge_status,
    broker_cleanup,
)
from ._claude import ask_claude, process_for_claude
from ._codex import ask_codex, process_all_codex, process_for_codex
from ._cursor import ask_cursor
from ._config import (
    _MODEL_CACHE,
    _MODEL_CACHE_TTL,
    _PARENT_ENV,
    CLAUDE_CMD,
    CODEX_CLI,
    DB_PATH,
    GEMINI_CLI,
    GEMINI_DEFAULT_MODEL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_REVIEW_MODEL,
    GH_CHAR_LIMIT,
    PID_DIR,
    PYTHON_CMD,
    REPO_ROOT,
    agent_child_env,
)
from ._db import get_db, get_session, init_db, set_session
from ._gemini import ask_gemini, process_and_respond
from ._github import (
    _format_review_chunk,
    _gh_comment,
    _post_review_to_github,
    _split_content,
)
from ._messaging import (
    _extract_issue_number,
    acknowledge,
    acknowledge_all,
    check_inbox,
    detect_sender,
    get_conversation,
    read_message,
    send_message,
    send_to_codex,
    send_to_gemini,
)
from ._model import _detect_model_error, check_model
from ._prompts import build_claude_prompt, build_codex_prompt, build_gemini_prompt

__all__ = [
    "CLAUDE_CMD",
    "CODEX_CLI",
    # Config
    "DB_PATH",
    "GEMINI_CLI",
    "GEMINI_DEFAULT_MODEL",
    "GEMINI_FALLBACK_MODEL",
    "GEMINI_REVIEW_MODEL",
    "GH_CHAR_LIMIT",
    "PID_DIR",
    "PYTHON_CMD",
    "REPO_ROOT",
    "_MODEL_CACHE",
    "_MODEL_CACHE_TTL",
    "_PARENT_ENV",
    "_detect_model_error",
    "_extract_issue_number",
    # GitHub
    "_format_review_chunk",
    "_gh_comment",
    # Broker
    "_git_status_snapshot",
    "_is_task_locked",
    "_post_review_to_github",
    "_remove_pid_file",
    "_split_content",
    "_validate_file_writes",
    "_write_pid_file",
    "acknowledge",
    "acknowledge_all",
    "agent_child_env",
    # Claude
    "ask_claude",
    "ask_codex",
    "ask_cursor",
    # Gemini
    "ask_gemini",
    "bridge_status",
    "broker_cleanup",
    "build_claude_prompt",
    "build_codex_prompt",
    # Prompts
    "build_gemini_prompt",
    # Messaging
    "check_inbox",
    # Model
    "check_model",
    "detect_sender",
    "get_conversation",
    "get_db",
    "get_session",
    # DB
    "init_db",
    "process_all_codex",
    "process_and_respond",
    "process_for_claude",
    "process_for_codex",
    "read_message",
    "send_message",
    "send_to_codex",
    "send_to_gemini",
    "set_session",
]
