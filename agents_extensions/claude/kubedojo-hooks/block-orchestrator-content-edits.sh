#!/bin/bash
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/../hooks/_lib.sh"
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

PROJECT_ROOT="${BASH_SOURCE[0]%/.claude/kubedojo-hooks/*}"
if [ "${FILE_PATH:0:1}" = "/" ]; then
  REL_PATH="${FILE_PATH#"$PROJECT_ROOT"/}"
  if [ "$REL_PATH" = "$FILE_PATH" ] && [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    REL_PATH="${FILE_PATH#"${CLAUDE_PROJECT_DIR%/}"/}"
  fi
else
  REL_PATH="$FILE_PATH"
fi
while [[ "$REL_PATH" == ./* ]]; do
  REL_PATH="${REL_PATH#./}"
done

if [[ "$REL_PATH" == src/content/docs/* ]]; then
  # Dispatched workers receive LEARN_UKRAINIAN_DISPATCH_TASK_ID from the
  # installed lu_machinery dispatcher (lu_machinery/dispatcher/environment.py:163,
  # worker.py:575, write_boundary.py:1072). Empty/whitespace fails closed.
  DISPATCH_TASK_ID="${LEARN_UKRAINIAN_DISPATCH_TASK_ID:-}"
  DISPATCH_TASK_ID="${DISPATCH_TASK_ID//[[:space:]]/}"
  if [ -z "$DISPATCH_TASK_ID" ]; then
    deny \
      "Edit/Write on src/content/docs/** from orchestrator is blocked; dispatch a worker instead." \
      "Use \"\$LEARN_UKRAINIAN_PYTHON\" -m lu_machinery.dispatch dispatch --repo kube-dojo --worktree ..." \
      "installed drive-epic skill and kubedojo-drive-epic overlay"
  fi
fi

exit 0
