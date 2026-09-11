#!/usr/bin/env bash
# Regression test for scripts/lib/handoff_identity.sh — the multi-lane launcher
# argv parser (#2113). Locks the edge cases raised in the cross-family review of
# PR #2114: parsing must STOP at `--`, and repeated `--agent` is LAST-wins, so
# the derived SESSION_HANDOFF_AGENT can never disagree with the agent `claude`
# itself selects. Fast + pure (no claude launch, no network).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../lib/handoff_identity.sh"

# shellcheck source=../lib/handoff_identity.sh
source "$LIB"

fail=0
# assert_eq <label> <expected> <actual>
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    printf '  ok   %-46s [%s]\n' "$label" "$actual"
  else
    printf '  FAIL %-46s expected [%s] got [%s]\n' "$label" "$expected" "$actual"
    fail=1
  fi
}

# --- handoff_agent_from_argv ---
assert_eq "single --agent <v>"          "infra-orchestrator" "$(handoff_agent_from_argv --chrome --agent infra-orchestrator)"
assert_eq "--agent=<v>"                 "infra-orchestrator" "$(handoff_agent_from_argv --agent=infra-orchestrator)"
assert_eq "stops at -- (no match)"      ""                   "$(handoff_agent_from_argv -- --agent infra-orchestrator)"
assert_eq "agent before -- still wins"  "infra-orchestrator" "$(handoff_agent_from_argv --agent infra-orchestrator -- somefile)"
assert_eq "repeated: last wins (B)"     "infra-orchestrator" "$(handoff_agent_from_argv --agent curriculum-orchestrator --agent infra-orchestrator)"
assert_eq "repeated reverse: last (A)"  "curriculum-orchestrator" "$(handoff_agent_from_argv --agent infra-orchestrator --agent curriculum-orchestrator)"
assert_eq "--agent as last arg, no val" ""                   "$(handoff_agent_from_argv --chrome --agent)"
assert_eq "no --agent present"          ""                   "$(handoff_agent_from_argv --chrome --permission-mode bypassPermissions)"
assert_eq "empty argv"                  ""                   "$(handoff_agent_from_argv)"

# --- handoff_identity_for_agent ---
assert_eq "slot: infra-orchestrator"    "claude-infra"       "$(handoff_identity_for_agent infra-orchestrator)"
assert_eq "slot: epic-driver"           "claude-epic"        "$(handoff_identity_for_agent epic-driver)"
assert_eq "slot: curriculum (default)"  ""                   "$(handoff_identity_for_agent curriculum-orchestrator)"
assert_eq "slot: unknown (default)"     ""                   "$(handoff_identity_for_agent something-else)"
assert_eq "slot: empty (default)"       ""                   "$(handoff_identity_for_agent '')"

# --- set -e safety: the parser must never abort the launcher (start-claude.sh
#     runs `set -e`); command substitution of either function must return 0. ---
( set -e; source "$LIB"; s="$(handoff_agent_from_argv -- --agent x)"; t="$(handoff_identity_for_agent "$s")"; : "$s$t" )
assert_eq "set -e: parser returns 0"    "0"                  "$?"

if [ "$fail" -ne 0 ]; then
  echo "[handoff-identity-test] FAIL"
  exit 1
fi
echo "[handoff-identity-test] PASS"
