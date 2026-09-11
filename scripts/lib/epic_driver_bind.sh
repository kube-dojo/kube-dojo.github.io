#!/usr/bin/env bash
# Thin epic-driver binding for KubeDojo launchers (not a LU lease/canary port).
#
# Parses --epic N from argv, exports SESSION_EPIC + KUBEDOJO_ISSUE, and builds
# the cold-start prompt that loads drive-epic, checks CodexBar, and drives via
# the fleet (dispatch_smart) — not solo volume.
#
# Used by: start-claude.sh, start-codex.sh, start-cursor-driver.sh
# SessionStart (.claude/hooks/session-setup.sh) honors SESSION_EPIC when set.

# epic_number_from_argv "$@"
# Echo the last --epic <N> / --epic=<N> before `--`, or nothing.
# Does NOT consume argv; callers strip separately. LAST-wins (commander-style).
epic_number_from_argv() {
  local prev='' arg='' found=''
  for arg in "$@"; do
    if [ "$arg" = "--" ]; then
      break
    fi
    case "$arg" in
      --epic=*)
        found="${arg#--epic=}"
        ;;
    esac
    if [ "$prev" = "--epic" ]; then
      found="$arg"
    fi
    prev="$arg"
  done
  printf '%s' "$found"
}

# epic_strip_from_argv "$@"
# Echo remaining argv with --epic / --epic=N removed (before `--`).
# Prints one arg per line so callers can mapfile / while-read safely.
epic_strip_from_argv() {
  local prev_was_epic=0
  local seen_dd=0
  local arg=''
  for arg in "$@"; do
    if [ "$seen_dd" = "1" ]; then
      printf '%s\n' "$arg"
      continue
    fi
    if [ "$arg" = "--" ]; then
      seen_dd=1
      printf '%s\n' "$arg"
      continue
    fi
    if [ "$prev_was_epic" = "1" ]; then
      prev_was_epic=0
      continue
    fi
    case "$arg" in
      --epic)
        prev_was_epic=1
        continue
        ;;
      --epic=*)
        continue
        ;;
    esac
    printf '%s\n' "$arg"
  done
}

# epic_validate_number <N>
# Exit 2 with a message on stderr if N is not a positive integer.
epic_validate_number() {
  local n="${1:-}"
  if [[ ! "$n" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Error: --epic requires a positive integer issue number (got %q)\n' "$n" >&2
    return 2
  fi
  return 0
}

# epic_export_env <N>
# Export SESSION_EPIC + KUBEDOJO_ISSUE (issue env wins if already set to same N).
epic_export_env() {
  local n="$1"
  epic_validate_number "$n" || return $?
  export SESSION_EPIC="$n"
  export KUBEDOJO_ISSUE="$n"
}

# epic_driver_prompt <N>
# One-shot / initialPrompt text: load drive-epic, cold-start, CodexBar, fleet.
epic_driver_prompt() {
  local n="$1"
  cat <<EOF
You are the epic driver for GitHub epic #${n}.

1. Load the drive-epic skill first (Read agents_extensions/shared/skills/drive-epic/SKILL.md or .claude/skills/drive-epic/SKILL.md) and follow it — method only; live roster/caps from tools.
2. Cold-start for this epic: \`KUBEDOJO_ISSUE=${n} bash scripts/cold-start.sh\` (or \`bash scripts/cold-start.sh --issue ${n}\`). SessionStart may already have run it — still act on the epic, not the default curriculum UK DO-NEXT.
3. Before any dispatch wave: run CodexBar capacity checks (\`codexbar usage --provider both --no-color\`, plus cursor/antigravity as needed) and write a CAPACITY_CARD (pick / avoid / free). Never habit-route Codex when pace-deficit; prefer cool idle seats.
4. Drive epic #${n} end-to-end via the fleet: inventory children on kube-dojo/kube-dojo.github.io AND kube-dojo/kubedojo-labs, dispose every open child, \`dispatch_smart\` in worktrees, exact-head cross-family review as a PR comment (not gh approve), CI green on the same SHA, rebase-merge. Do not solo-implement volume work.
5. State in one line what you are picking up on #${n}, then proceed — do not wait to be told to orient.
EOF
}
