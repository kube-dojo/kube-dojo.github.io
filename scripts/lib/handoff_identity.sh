#!/usr/bin/env bash
# Map a Claude Code `--agent` selection to its cold-start handoff identity
# (SESSION_HANDOFF_AGENT). Ported from learn-ukrainian (#2113, parity).
#
# WHY: every Claude session launched as plain `claude` defaults to the single
# curriculum-orchestrator identity that .claude/hooks/session-setup.sh hardcodes,
# and there is only one handoff lane. To run a SECOND lane (e.g. an infra /
# tooling orchestrator working on scripts, hooks, the local API, CI) from the
# SAME launcher without it clobbering the curriculum lane's orientation, the
# launcher derives SESSION_HANDOFF_AGENT from the selected `--agent`. The
# SessionStart hook honors that value to emit a lane-specific identity and read
# the lane's OWN .agent/<id>-thread-handoff.md slot. ONE launcher, many lanes,
# no per-lane wrapper script.
#
# Add a new lane by adding ONE case arm to handoff_identity_for_agent below.
# Unknown / absent agents fall back to the default curriculum lane (echo
# nothing) — the hook already defaults to it, so the existing single-lane
# behavior is preserved byte-for-byte.

# handoff_agent_from_argv "$@"
# Echo the value of `--agent <v>` / `--agent=<v>` from an argv list, or nothing.
# Does NOT consume the argument — the caller still forwards "$@" to claude
# unchanged. Matches how `claude` itself resolves the flag, so the derived
# handoff identity can never disagree with the agent claude actually selects:
#   - Stop at `--`: everything after it is passthrough DATA, not options.
#   - LAST occurrence wins (commander-style), not first.
handoff_agent_from_argv() {
  local prev='' arg='' found=''
  for arg in "$@"; do
    if [ "$arg" = "--" ]; then
      break
    fi
    case "$arg" in
      --agent=*)
        found="${arg#--agent=}"
        ;;
    esac
    if [ "$prev" = "--agent" ]; then
      found="$arg"
    fi
    prev="$arg"
  done
  printf '%s' "$found"
}

# handoff_identity_for_agent "<agent-name>"
# Echo the SESSION_HANDOFF_AGENT slot for an --agent name, or nothing for the
# default curriculum lane (the hook already defaults to it).
handoff_identity_for_agent() {
  case "${1:-}" in
    infra-orchestrator) printf '%s' 'claude-infra' ;;
    epic-driver) printf '%s' 'claude-epic' ;;
    # curriculum-orchestrator / curriculum-writer / unset → default lane.
    *) ;;
  esac
}
