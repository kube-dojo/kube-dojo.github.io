#!/bin/bash
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/_lib.sh"
set -euo pipefail

# Hook: PreToolUse (Agent) — block worktree isolation.

RAW_PAYLOAD=$(cat)

TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)
if [ "$TOOL_NAME" != "Agent" ]; then
  exit 0
fi

ISOLATION=$(jq -r '.tool_input.isolation // ""' <<<"$RAW_PAYLOAD" 2>/dev/null || true)

if [ "$ISOLATION" = "worktree" ]; then
  deny \
    "Agent calls with isolation='worktree' are blocked — parallel agent worktree fan-out has a GC race that lost 5/8 agents on Part 5 night-2 (2026-04-30)." \
    "Run agents inline/sequential instead. Recovery procedure if you've already cherry-picked work: see memory/reference_agent_worktree_recovery.md" \
    "feedback_no_parallel_agent_fanout.md (TOP PRIORITY memory)"
fi

exit 0
