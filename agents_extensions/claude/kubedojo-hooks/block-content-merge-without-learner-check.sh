#!/bin/bash
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/../hooks/_lib.sh"
set -euo pipefail

# Hook: PreToolUse (Bash) — block `gh pr merge` for content PRs that lack a
# verifiable "Learner check" quote. Forces the orchestrator to actually read
# the module before merging instead of trusting verifier output alone.
#
# Pass condition: PR body contains a `## Learner check` section with a
# markdown blockquote (`> ...`) whose text appears verbatim in at least one
# of the `src/content/docs/**` files the PR touches.
#
# A metadata-only touch of content files (e.g. an `en_commit` provenance
# backfill) changes no teaching prose, so the Learner-check requirement is
# skipped when EVERY touched `src/content/docs/**` file is metadata-only vs the
# PR base. If the base can't be resolved the file is treated as real content, so
# the gate is never weaker than before.
#
# Test overrides:
#   KUBEDOJO_HOOK_GH_JSON           Path to JSON file replacing `gh pr view`.
#   KUBEDOJO_HOOK_FILE_FIXTURE_DIR  Directory holding HEAD file contents keyed by
#                                   the PR's relative paths (replaces
#                                   `git show <headOid>:<path>`).
#   KUBEDOJO_HOOK_BASE_FIXTURE_DIR  Same, but for BASE contents (replaces
#                                   `git show origin/<baseRefName>:<path>`).

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
    PR_JSON=$(gh pr view "$PR_REF" --json body,files,headRefOid,baseRefName,title,number 2>/dev/null || true)
  else
    # No explicit PR ref: gh auto-detects from the current branch. Resolve the
    # effective cwd by walking `cd X` segments — the harness-reported cwd can
    # be the primary tree even when the user is running
    # `cd .worktrees/X && gh pr merge` from a worktree. Same bug class as
    # #1321 (false-negative-allow direction instead of false-positive-deny).
    EFFECTIVE_DIR=$(python3 "$HOOK_DIR/_lib_resolve_cwd.py" "$COMMAND" "$CWD" gh 2>/dev/null || printf '%s' "$CWD")
    PR_JSON=$(cd "$EFFECTIVE_DIR" 2>/dev/null && gh pr view --json body,files,headRefOid,baseRefName,title,number 2>/dev/null || true)
  fi
  if [ -z "$PR_JSON" ]; then
    exit 0
  fi
fi
VERDICT=$(KUBEDOJO_HOOK_FILE_FIXTURE_DIR="${KUBEDOJO_HOOK_FILE_FIXTURE_DIR:-}" \
  KUBEDOJO_HOOK_BASE_FIXTURE_DIR="${KUBEDOJO_HOOK_BASE_FIXTURE_DIR:-}" \
  python3 "$HOOK_DIR/_lib_pr_check.py" learner "$PR_JSON" || true)

VERDICT_KIND=${VERDICT%%$'\t'*}
VERDICT_MSG=${VERDICT#*$'\t'}

if [ "$VERDICT_KIND" = "DENY" ]; then
  deny \
    "content merge blocked: $VERDICT_MSG" \
    "Add a '## Learner check' section with a markdown blockquote (> ...) >= 30 chars copied verbatim from a touched module." \
    "feedback_teaching_not_listicles.md"
fi

exit 0
