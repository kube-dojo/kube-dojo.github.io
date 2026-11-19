#!/bin/bash
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/_lib.sh"
set -euo pipefail

# Hook: PreToolUse (Edit/Write) — block direct orchestrator edits to src/content/docs.

RAW_PAYLOAD=$(cat)

TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
  exit 0
fi

FILE_PATH=$(jq -r '.tool_input.file_path // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

PROJECT_ROOT="${BASH_SOURCE[0]%/.claude/hooks/*}"
if [ "${FILE_PATH:0:1}" = "/" ]; then
  REL_PATH="${FILE_PATH#"$PROJECT_ROOT"/}"
else
  REL_PATH="$FILE_PATH"
fi

if [[ "$REL_PATH" == src/content/docs/* ]]; then
  if [ "${KUBEDOJO_DISPATCHED:-0}" != "1" ]; then
    deny \
      "Edit/Write on src/content/docs/** from orchestrator is blocked; dispatch a codex/claude headless agent instead." \
      "Use scripts/dispatch_smart.py edit --agent codex --worktree .worktrees/<task> --new-branch <branch>" \
      "feedback_dispatch_codex_for_code_changes.md (TOP PRIORITY memory)"
  fi
fi

exit 0
