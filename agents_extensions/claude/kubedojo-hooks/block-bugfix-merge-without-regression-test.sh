#!/bin/bash
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/../hooks/_lib.sh"
set -euo pipefail

# Hook: PreToolUse (Bash) — block `gh pr merge` for bugfix PRs that lack a
# verifiable regression test pointer.
#
# Pass condition: PR is a bugfix (title starts with `fix:` / `fix(...)`: OR
# body has `Fixes #N` / `Closes #N`) AND the body contains a
# `Regression test:` line pointing to a test file that:
#   1. Is part of this PR's files (added or modified, not pre-existing).
#   2. References the bug's issue number(s) in its source.
#
# We deliberately do NOT run pytest here — a merge hook must stay fast.
# The mechanical check is that a regression test exists, was edited in
# this PR, and names the issue it covers; running it is CI's job.
#
# Test overrides:
#   KUBEDOJO_HOOK_GH_JSON           Path to JSON file replacing `gh pr view`.
#   KUBEDOJO_HOOK_FILE_FIXTURE_DIR  Directory holding fixture file contents
#                                   keyed by the same relative path the PR
#                                   reports (replaces `git show <oid>:<path>`).

RAW_PAYLOAD=$(cat)

TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD")
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

PAYLOAD=$(read_tool_payload <<<"$RAW_PAYLOAD")
COMMAND=${PAYLOAD%%$'\t'*}
CWD=${PAYLOAD#*$'\t'}

if [ -z "$COMMAND" ]; then
  exit 0
fi

if ! printf '%s\n' "$COMMAND" | grep -Eq '(^|[;&|[:space:]])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)'; then
  exit 0
fi

HOOK_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd -P)
PR_REF=$(python3 "$HOOK_DIR/_lib_parse_pr_ref.py" "$COMMAND" 2>/dev/null || true)

if [ -n "${KUBEDOJO_HOOK_GH_JSON:-}" ] && [ -f "${KUBEDOJO_HOOK_GH_JSON}" ]; then
  PR_JSON=$(cat "${KUBEDOJO_HOOK_GH_JSON}")
else
  if ! command -v gh >/dev/null 2>&1; then
    exit 0
  fi
  if [ -n "$PR_REF" ]; then
    PR_JSON=$(gh pr view "$PR_REF" --json body,files,headRefOid,title,number 2>/dev/null || true)
  else
    # No explicit PR ref: gh auto-detects from the current branch. Resolve the
    # effective cwd by walking `cd X` segments — the harness-reported cwd can
    # be the primary tree even when the user is running
    # `cd .worktrees/X && gh pr merge` from a worktree. Same bug class as
    # #1321 (false-negative-allow direction instead of false-positive-deny).
    EFFECTIVE_DIR=$(python3 "$HOOK_DIR/_lib_resolve_cwd.py" "$COMMAND" "$CWD" gh 2>/dev/null || printf '%s' "$CWD")
    PR_JSON=$(cd "$EFFECTIVE_DIR" 2>/dev/null && gh pr view --json body,files,headRefOid,title,number 2>/dev/null || true)
  fi
  if [ -z "$PR_JSON" ]; then
    exit 0
  fi
fi
VERDICT=$(KUBEDOJO_HOOK_FILE_FIXTURE_DIR="${KUBEDOJO_HOOK_FILE_FIXTURE_DIR:-}" \
  python3 "$HOOK_DIR/_lib_pr_check.py" regression "$PR_JSON" || true)

VERDICT_KIND=${VERDICT%%$'\t'*}
VERDICT_MSG=${VERDICT#*$'\t'}

if [ "$VERDICT_KIND" = "DENY" ]; then
  deny \
    "bugfix merge blocked: $VERDICT_MSG" \
    "Add a 'Regression test: tests/test_xxx.py' line pointing to a test added or modified by this PR that references the issue number." \
    "feedback_quality_discipline.md"
fi

exit 0
