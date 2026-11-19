#!/bin/bash
# Hook: PostToolUse (Edit/Write) — auto-format .py files with ruff after writes.
# Scope: .py files in the primary tree only; skip dispatched sessions,
# worktrees, logs, dist, node_modules, .venv, and src/content/docs.
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/_lib.sh"

RAW_PAYLOAD=$(cat)

# Only fire for Edit or Write tool calls
TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
  exit 0
fi

# Skip inside dispatch pipelines (set by scripts/dispatch*.py)
if [ "${KUBEDOJO_DISPATCHED:-0}" = "1" ]; then
  exit 0
fi

FILE_PATH=$(jq -r '.tool_input.file_path // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Must be a Python file
case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac

# Resolve primary tree root
PRIMARY_DIR=$(normalize_path "$(detect_primary_dir)")
if [ -z "$PRIMARY_DIR" ]; then
  exit 0
fi

# Resolve to absolute path if relative
if [ "${FILE_PATH:0:1}" != "/" ]; then
  FILE_PATH="$PRIMARY_DIR/$FILE_PATH"
fi

# File must exist (tool_input path should always be valid, but fail-open)
[ -f "$FILE_PATH" ] || exit 0

# Skip files outside the primary tree (e.g. those inside .worktrees/)
if ! is_inside_primary "$FILE_PATH"; then
  exit 0
fi

# Skip excluded directories
case "$FILE_PATH" in
  */logs/*|*/dist/*|*/node_modules/*|*/.venv/*|*/.worktrees/*|*/src/content/docs/*)
    exit 0
    ;;
esac

# Use ruff from the project venv only; skip silently if not installed
RUFF="$PRIMARY_DIR/.venv/bin/ruff"
if [ ! -x "$RUFF" ]; then
  exit 0
fi

# Check if ruff would reformat (exit 1) vs already formatted (exit 0) vs error (2+)
CHECK_RESULT=0
"$RUFF" format --check --quiet "$FILE_PATH" 2>/dev/null || CHECK_RESULT=$?

if [ "$CHECK_RESULT" = "1" ]; then
  "$RUFF" format --quiet "$FILE_PATH" 2>/dev/null || true
  jq -n --arg f "$FILE_PATH" \
    '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":("ruff auto-formatted " + $f + " — whitespace/style only; re-read if you need the exact final state")}}'
fi

exit 0
