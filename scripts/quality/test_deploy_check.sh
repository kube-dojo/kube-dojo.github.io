#!/usr/bin/env bash
# Regression test for `agents_extensions/deploy.sh --check` — the drift detector
# against the enrolled KubeDojo sources in a throwaway Git checkout.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
: "${LEARN_UKRAINIAN_PYTHON:?Set the installed machinery interpreter}"
TMP=$(mktemp -d)
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

git -C "$TMP" init -q
cp -a "$ROOT/agents_extensions" "$TMP/"
skill="$TMP/.claude/skills/kubedojo-drive-epic"
hook="$TMP/.claude/hooks/kubedojo-session-setup.sh"

fail=0
ok()   { echo "  ok   $1"; }
bad()  { echo "  FAIL $1"; fail=1; }
run_check() { bash "$TMP/agents_extensions/deploy.sh" --check >/dev/null 2>&1; }
redeploy()  { bash "$TMP/agents_extensions/deploy.sh" >/dev/null; }
# Full state snapshot: structure + content checksum + executable bit per file.
snapshot()  { ( cd "$TMP/.claude" && find . | sort && find . -type f | sort | while read -r f; do printf '%s ' "$(cksum "$f")"; [ -x "$f" ] && echo "x:$f" || echo "-:$f"; done ); }

# 1. in sync → exit 0
redeploy
run_check && ok "in-sync → exit 0" || bad "in-sync should exit 0"

# 2. read-only: --check must not change structure, content, or modes
before=$(snapshot); run_check || true; after=$(snapshot)
[ "$before" = "$after" ] && ok "--check is read-only (structure + content + modes)" || bad "--check mutated the tree"

# 3. content drift → exit 1
printf 'drift\n' >> "$skill/SKILL.md"
run_check && bad "content drift should exit 1" || ok "content drift → exit 1"
redeploy; run_check && ok "deploy re-syncs content → exit 0" || bad "deploy did not re-sync content"

# 4. executable-bit drift (content matches, deployed lost +x) → exit 1
chmod 0644 "$hook"
run_check && bad "exec-bit drift should exit 1" || ok "exec-bit drift → exit 1"
redeploy; run_check && ok "deploy restores +x → exit 0" || bad "deploy did not restore +x"

# 5. content-type orphan (deployed skill with no source) → exit 1
mkdir -p "$TMP/.claude/skills/orphan"; printf 'x\n' > "$TMP/.claude/skills/orphan/SKILL.md"
run_check && bad "content orphan should exit 1" || ok "content orphan → exit 1"
rm -rf "$TMP/.claude/skills/orphan"
run_check && ok "orphan removed → exit 0" || bad "still drifted after orphan removed"

# 6. Hooks without a source also count as unowned outputs.
printf '#!/bin/bash\n' > "$TMP/.claude/hooks/standalone.sh"; chmod +x "$TMP/.claude/hooks/standalone.sh"
run_check && bad "source-less hook should fail" || ok "source-less hook detected"
rm -f "$TMP/.claude/hooks/standalone.sh"

# 7. missing deployed copy → exit 1
rm -f "$skill/SKILL.md"
run_check && bad "missing deployed should exit 1" || ok "missing deployed → exit 1"

# 8. companion markdown next to SKILL.md is copied and drift-checked
redeploy
[ -f "$skill/dual-repo.md" ] && ok "companion file deployed" || bad "companion file not copied"
printf 'drift\n' >> "$skill/dual-repo.md"
run_check && bad "companion drift should exit 1" || ok "companion drift → exit 1"
redeploy; run_check && ok "deploy re-syncs companion → exit 0" || bad "deploy did not re-sync companion"

if [ "$fail" -ne 0 ]; then echo "[deploy-check-test] FAIL"; exit 1; fi
echo "[deploy-check-test] PASS"
