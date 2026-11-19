#!/bin/bash
source "${BASH_SOURCE[0]%/*}/_lib.sh"
set -euo pipefail

# Hook: PreToolUse (Bash) — Block branch creation in the primary repo dir.

PAYLOAD=$(read_tool_payload)
COMMAND=${PAYLOAD%%$'\t'*}
CWD=${PAYLOAD#*$'\t'}

if [ -z "$COMMAND" ]; then
  exit 0
fi

if ! echo "$COMMAND" | grep -Eq '(^|[;&|[:space:]])git[[:space:]]+checkout([^;&|]*)[[:space:]]+-[bB]([[:space:]]|$)|(^|[;&|[:space:]])git[[:space:]]+switch([^;&|]*)[[:space:]]+-[cC]([[:space:]]|$)'; then
  exit 0
fi

PRIMARY_DIR=$(normalize_path "$(detect_primary_dir)")
CWD=$(normalize_path "$CWD")

if is_inside_primary "$CWD"; then
  deny \
    "branch creation in the primary repo dir is blocked." \
    "Use a worktree under \`.worktrees/\` instead." \
    "feedback_never_branch_in_primary_dir.md"
fi

exit 0
