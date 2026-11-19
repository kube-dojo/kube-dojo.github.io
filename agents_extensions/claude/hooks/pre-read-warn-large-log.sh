#!/bin/bash
# Hook: PreToolUse (Read) — warn when reading large dispatch log files cold.
# Informational only — never blocks. Suggests jq query alternatives to avoid
# flooding Claude's context with multi-MB JSONL or response text files.

RAW_PAYLOAD=$(cat)

# Only fire for Read tool calls
TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ "$TOOL_NAME" != "Read" ]; then
  exit 0
fi

FILE_PATH=$(jq -r '.tool_input.file_path // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Match only known dispatch log files (handles both absolute and relative paths)
IS_LOG=0
case "$FILE_PATH" in
  *logs/smart_dispatch.jsonl|*logs/dispatch_responses/*.txt)
    IS_LOG=1
    ;;
esac

if [ "$IS_LOG" = "0" ]; then
  exit 0
fi

# File must exist to stat it
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

FILE_SIZE=$(wc -c < "$FILE_PATH" 2>/dev/null || echo 0)
LIMIT_BYTES=102400  # 100 KB

if [ "$FILE_SIZE" -le "$LIMIT_BYTES" ]; then
  exit 0
fi

FILE_KB=$((FILE_SIZE / 1024))

if [[ "${FILE_PATH}" == *.jsonl ]]; then
  MSG="Log file ${FILE_PATH} is ${FILE_KB} KB — reading it whole will flood context.
Consider targeted queries instead:
  jq 'select(.status==\"error\")' \"${FILE_PATH}\" | head -20    # filter errors
  jq -r '.module_key' \"${FILE_PATH}\" | sort | uniq -c           # module counts
  tail -n 20 \"${FILE_PATH}\" | jq '.'                            # recent entries
Proceeding with Read — this is advisory only."
else
  MSG="Log file ${FILE_PATH} is ${FILE_KB} KB — reading it whole will flood context.
Consider targeted queries instead (plain-text response file):
  tail -n 100 \"${FILE_PATH}\"                                    # recent output
  grep -nE 'VERDICT|BLOCKERS|ERROR' \"${FILE_PATH}\"              # extract verdict/errors
  head -n 50 \"${FILE_PATH}\"                                     # opening summary
Proceeding with Read — this is advisory only."
fi

jq -n --arg msg "$MSG" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":$msg}}'

exit 0
