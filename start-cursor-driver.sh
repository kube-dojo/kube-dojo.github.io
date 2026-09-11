#!/usr/bin/env bash
# Thin Cursor epic-driver launcher (no LU lease/canary stack).
# Exports SESSION_EPIC + KUBEDOJO_ISSUE, then starts an interactive cursor-agent
# session with the drive-epic bind prompt (CodexBar + fleet).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/epic_driver_bind.sh
source "$ROOT/scripts/lib/epic_driver_bind.sh"

EPIC="$(epic_number_from_argv "$@")"
if [ -z "$EPIC" ]; then
  cat <<'EOF' >&2
Usage: ./start-cursor-driver.sh --epic <N> [cursor-agent args...]

Loads drive-epic, cold-starts issue N, requires CodexBar capacity before
dispatch, and drives the epic via the fleet (dispatch_smart).
EOF
  exit 2
fi
epic_export_env "$EPIC" || exit $?

FORWARD=()
while IFS= read -r line; do
  [ -n "$line" ] || continue
  FORWARD+=("$line")
done < <(epic_strip_from_argv "$@")

cd "$ROOT"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
hash -r 2>/dev/null || true

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "Error: cursor-agent not found on PATH." >&2
  echo "  Install the Cursor agent CLI, or open the IDE from a shell that" >&2
  echo "  already exported SESSION_EPIC=$EPIC (SessionStart honors it)." >&2
  exit 1
fi

PROMPT="$(epic_driver_prompt "$EPIC")"
echo "Starting Cursor epic driver for #$EPIC..."
echo "SESSION_EPIC=$SESSION_EPIC KUBEDOJO_ISSUE=$KUBEDOJO_ISSUE"
echo "CodexBar + fleet bind is in the initial prompt."

# Interactive agent session (no --print). Remaining args forward; prompt last.
exec cursor-agent --force "${FORWARD[@]}" "$PROMPT"
