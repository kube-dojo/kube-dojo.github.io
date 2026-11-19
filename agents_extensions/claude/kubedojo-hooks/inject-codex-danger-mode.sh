#!/bin/bash
# Hook: PreToolUse (Bash) — Inject --mode danger for codex exec prompts that contain git push / gh pr create.
source "${BASH_SOURCE[0]%/*}/../hooks/_lib.sh"
set -euo pipefail

RAW_PAYLOAD=$(cat)

TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

COMMAND=$(jq -r '.tool_input.command // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ -z "$COMMAND" ]; then
  exit 0
fi

# Extract task class from the dispatch_smart.py command. The pipeline
# returns exit 1 when grep finds no match (normal for non-dispatch_smart
# Bash calls); without `|| true`, `set -euo pipefail` kills the hook
# silently and the harness reports "PreToolUse:Bash hook error" noise.
TASK_CLASS=$(echo "$COMMAND" | grep -oE 'dispatch_smart\.py[[:space:]]+[a-z]+' | awk '{print $NF}' || true)
# Skip read-only task classes — they don't need a worktree.
if [[ "$TASK_CLASS" == "review" || "$TASK_CLASS" == "search" ]]; then
  exit 0
fi

PARSE_RESULT=$(python3 - "$COMMAND" <<'PY'
import shlex
import sys

command = sys.argv[1]

try:
    tokens = shlex.split(command)
except ValueError as exc:
    print(f"FAIL_OPEN\tcould not parse shell command ({exc})")
    raise SystemExit

codex_index = None
for index in range(len(tokens) - 1):
    if tokens[index] == "codex" and tokens[index + 1] == "exec":
        codex_index = index
        break

if codex_index is None:
    print("NO_CHANGE")
    raise SystemExit

args_start = codex_index + 2
args = tokens[args_start:]
i = 0
prompt_seen = False
prompt = None
mode_token_index = None
mode_value = None

while i < len(args):
    token = args[i]

    if token == "--":
        i += 1
        if i >= len(args):
            break
        prompt = args[i]
        prompt_seen = True
        break

    if token == "-":
        print("FAIL_OPEN\tprompt source not statically visible")
        raise SystemExit

    if token == "<":
        print("FAIL_OPEN\tprompt source not statically visible")
        raise SystemExit

    if token in {"-f", "--file"}:
        print("FAIL_OPEN\tprompt source not statically visible")
        raise SystemExit

    if token.startswith("--file="):
        print("FAIL_OPEN\tprompt source not statically visible")
        raise SystemExit

    if token == "--mode":
        if i + 1 >= len(args):
            print("NO_CHANGE")
            raise SystemExit
        mode_token_index = args_start + i
        mode_value = args[i + 1]
        i += 2
        continue

    if token.startswith("--mode="):
        mode_token_index = args_start + i
        mode_value = token.split("=", 1)[1]
        i += 1
        continue

    if token.startswith("-") and token != "-":
        i += 1
        continue

    prompt = token
    prompt_seen = True
    break

if not prompt_seen or prompt is None:
    print("NO_CHANGE")
    raise SystemExit

if "git push" not in prompt and "gh pr create" not in prompt:
    print("NO_CHANGE")
    raise SystemExit

if mode_token_index is not None:
    if mode_value == "danger":
        print("NO_CHANGE")
        raise SystemExit

    if tokens[mode_token_index].startswith("--mode="):
        tokens[mode_token_index] = "--mode=danger"
    elif mode_token_index + 1 < len(tokens):
        tokens[mode_token_index + 1] = "danger"
    print("UPDATE\t" + shlex.join(tokens))
    raise SystemExit

insert_at = args_start
tokens.insert(insert_at, "--mode")
tokens.insert(insert_at + 1, "danger")
print("UPDATE\t" + shlex.join(tokens))
PY
) || true

if [ -z "$PARSE_RESULT" ]; then
  exit 0
fi

PARSE_KIND=${PARSE_RESULT%%$'\t'*}

if [ "$PARSE_KIND" = "UPDATE" ]; then
  UPDATED_COMMAND=${PARSE_RESULT#*$'\t'}
  printf '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "updatedInput": {"command": %s}
    }
  }\n' "$(printf '%s' "$UPDATED_COMMAND" | jq -Rs '.')"
  exit 0
fi

if [ "$PARSE_KIND" = "FAIL_OPEN" ]; then
  printf '%s\n' "$PARSE_RESULT" >&2
  exit 0
fi

exit 0
