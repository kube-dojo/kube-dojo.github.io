#!/bin/bash
# Hook: PostToolUse — monitors context size and warns Claude before auto-compact
# triggers, demanding a lean MD session-handoff brief to
# .agent/session-state/YYYY-MM-DD-session-NN-<topic>.md + a .agent/STATUS.md index
# update (s196 convention — local agent state, never through git/PRs).
#
# Tiers (% of autoCompactWindow):
#   75% -> heads-up: prepare handoff soon
#   85% -> critical: finish current task, write handoff, end session
#   95% -> emergency: stop now, write handoff this turn, /exit immediately
#
# Compaction is far more expensive than session handoff: handoff is just a
# small handoff file the next session reads on startup; compaction is a
# billed model call summarizing your entire conversation.

# Skip in non-interactive contexts
if [ -n "$CLAUDE_NON_INTERACTIVE" ] || [ -n "$KUBEDOJO_PIPELINE" ] || [ -n "$GEMINI_SESSION" ]; then
  exit 0
fi

# Read hook input (JSON on stdin)
INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
[ -z "$SESSION_ID" ] && exit 0

# Resolve project + transcript path
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PROJECT_SLUG=$(printf '%s' "$PROJECT_DIR" | sed 's|/|-|g')
TRANSCRIPT="$HOME/.claude/projects/${PROJECT_SLUG}/${SESSION_ID}.jsonl"

[ ! -f "$TRANSCRIPT" ] && exit 0

# Estimate tokens from transcript size. Calibrated against /context output:
# transcript jsonl carries heavy JSON metadata + tool-result wrapping, so the
# real chars-per-context-token ratio is ~7 (not the prose-only ~4).
SIZE=$(wc -c < "$TRANSCRIPT" 2>/dev/null || echo 0)
TOKENS=$((SIZE / 7))

# Read autoCompactWindow from settings; default to platform default 650k
SETTINGS_FILE="$PROJECT_DIR/.claude/settings.json"
WINDOW=650000
if [ -f "$SETTINGS_FILE" ]; then
  CONFIGURED=$(jq -r '.autoCompactWindow // empty' "$SETTINGS_FILE" 2>/dev/null)
  if [ -n "$CONFIGURED" ] && [ "$CONFIGURED" -gt 0 ] 2>/dev/null; then
    WINDOW=$CONFIGURED
  fi
fi

[ "$WINDOW" -le 0 ] && exit 0
PCT=$((TOKENS * 100 / WINDOW))

# Build tiered message via printf to avoid heredoc-in-cmdsub paren issues
if [ "$PCT" -ge 95 ]; then
  MSG=$(printf '%s\n%s\n%s\n%s\n%s\n' \
    "EMERGENCY: Context at ${PCT}% of auto-compact window [~${TOKENS}/${WINDOW} tokens]. AUTO-COMPACT IS IMMINENT." \
    "" \
    "STOP all current work THIS TURN. Do not start any new tool calls beyond what is needed to:" \
    "1. Write or update the lean MD handoff brief .agent/session-state/YYYY-MM-DD-session-NN-<topic>.md NOW with: latest commit hash on main, any background tasks still running [PIDs + log paths], what was just completed, what is left to do, and the EXACT next-step commands the new session should run. Then update .agent/STATUS.md (the live index) per the session-handoff-writer skill. NO git add/commit/PR — handoffs are local agent state." \
    "2. Tell the user to /exit immediately and start a fresh session that reads the new .agent/session-state/ brief first. Auto-compaction is a billed model call that summarizes your entire conversation: much more expensive than a ~3KB brief the next session reads cheaply.")
elif [ "$PCT" -ge 85 ]; then
  MSG=$(printf '%s\n%s\n%s\n%s\n%s\n%s\n' \
    "CRITICAL: Context at ${PCT}% of auto-compact window [~${TOKENS}/${WINDOW} tokens]." \
    "" \
    "Finish your current task ASAP, then:" \
    "1. Write or update the lean MD handoff brief .agent/session-state/YYYY-MM-DD-session-NN-<topic>.md with commit hashes, in-flight tasks, next steps, restart commands. Then update .agent/STATUS.md (the live index). NO git add/commit/PR — handoffs are local agent state." \
    "2. Tell the user to /exit and start fresh." \
    "Do NOT start any new multi-step work or large operations. Handoff is much cheaper than the auto-compact that is about to trigger.")
elif [ "$PCT" -ge 75 ]; then
  MSG=$(printf '%s\n%s\n%s\n' \
    "HEADS UP: Context at ${PCT}% of auto-compact window [~${TOKENS}/${WINDOW} tokens]." \
    "" \
    "Wrap up your current logical unit of work soon. Once it lands, prepare the lean MD handoff brief .agent/session-state/YYYY-MM-DD-session-NN-<topic>.md (and update .agent/STATUS.md as the live index) — NO git add/commit/PR, handoffs are local agent state — so we can hand off to a fresh session before auto-compact triggers. The brief costs ~3KB; compaction costs a full model summarization call.")
else
  exit 0
fi

# Inject the warning back into Claude's context
jq -n --arg msg "$MSG" '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":$msg}}'
