#!/usr/bin/env bash
# Regression test for `agents_extensions/deploy.sh --check` — the drift detector
# behind the extensions-sync CI gate. Self-contained: builds a throwaway
# agents_extensions/.claude tree in a temp dir (deploy.sh derives its root from
# BASH_SOURCE), never touches the real repo. Covers the three detection classes
# plus read-only-ness (the last two added after codex review of #2115).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REAL_DEPLOY="$SCRIPT_DIR/../../agents_extensions/deploy.sh"
TMP=$(mktemp -d)
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# --- minimal source + deployed tree: one content skill + one executable hook ---
mkdir -p "$TMP/agents_extensions/claude/skills/demo" "$TMP/.claude/skills/demo"
mkdir -p "$TMP/agents_extensions/claude/hooks" "$TMP/.claude/hooks"
cp "$REAL_DEPLOY" "$TMP/agents_extensions/deploy.sh"
printf 'hello\n' > "$TMP/agents_extensions/claude/skills/demo/SKILL.md"
printf 'hello\n' > "$TMP/.claude/skills/demo/SKILL.md"
printf '#!/bin/bash\necho hi\n' > "$TMP/agents_extensions/claude/hooks/demo.sh"; chmod +x "$TMP/agents_extensions/claude/hooks/demo.sh"
printf '#!/bin/bash\necho hi\n' > "$TMP/.claude/hooks/demo.sh";                  chmod +x "$TMP/.claude/hooks/demo.sh"

fail=0
ok()   { echo "  ok   $1"; }
bad()  { echo "  FAIL $1"; fail=1; }
run_check() { bash "$TMP/agents_extensions/deploy.sh" --check --target claude --quiet >/dev/null 2>&1; }
redeploy()  { bash "$TMP/agents_extensions/deploy.sh" --target claude --quiet >/dev/null 2>&1; }
# Full state snapshot: structure + content checksum + executable bit per file.
snapshot()  { ( cd "$TMP/.claude" && find . | sort && find . -type f | sort | while read -r f; do printf '%s ' "$(cksum "$f")"; [ -x "$f" ] && echo "x:$f" || echo "-:$f"; done ); }

# 1. in sync → exit 0
run_check && ok "in-sync → exit 0" || bad "in-sync should exit 0"

# 2. read-only: --check must not change structure, content, or modes
before=$(snapshot); run_check || true; after=$(snapshot)
[ "$before" = "$after" ] && ok "--check is read-only (structure + content + modes)" || bad "--check mutated the tree"

# 3. content drift → exit 1
printf 'drift\n' >> "$TMP/.claude/skills/demo/SKILL.md"
run_check && bad "content drift should exit 1" || ok "content drift → exit 1"
redeploy; run_check && ok "deploy re-syncs content → exit 0" || bad "deploy did not re-sync content"

# 4. executable-bit drift (content matches, deployed lost +x) → exit 1
chmod -x "$TMP/.claude/hooks/demo.sh"
run_check && bad "exec-bit drift should exit 1" || ok "exec-bit drift → exit 1"
redeploy; run_check && ok "deploy restores +x → exit 0" || bad "deploy did not restore +x"

# 5. content-type orphan (deployed skill with no source) → exit 1
mkdir -p "$TMP/.claude/skills/orphan"; printf 'x\n' > "$TMP/.claude/skills/orphan/SKILL.md"
run_check && bad "content orphan should exit 1" || ok "content orphan → exit 1"
rm -rf "$TMP/.claude/skills/orphan"
run_check && ok "orphan removed → exit 0" || bad "still drifted after orphan removed"

# 6. deployed hook with NO source must NOT be flagged (hooks carry direct-committed files)
printf '#!/bin/bash\n' > "$TMP/.claude/hooks/standalone.sh"; chmod +x "$TMP/.claude/hooks/standalone.sh"
run_check && ok "source-less hook NOT flagged (exit 0)" || bad "source-less hook wrongly flagged"
rm -f "$TMP/.claude/hooks/standalone.sh"

# 7. missing deployed copy → exit 1
rm -f "$TMP/.claude/skills/demo/SKILL.md"
run_check && bad "missing deployed should exit 1" || ok "missing deployed → exit 1"
printf 'hello\n' > "$TMP/.claude/skills/demo/SKILL.md"

# 8. companion markdown next to SKILL.md is copied and drift-checked
printf 'ref\n' > "$TMP/agents_extensions/claude/skills/demo/dual-repo.md"
redeploy
[ -f "$TMP/.claude/skills/demo/dual-repo.md" ] && ok "companion file deployed" || bad "companion file not copied"
printf 'drift\n' >> "$TMP/.claude/skills/demo/dual-repo.md"
run_check && bad "companion drift should exit 1" || ok "companion drift → exit 1"
redeploy; run_check && ok "deploy re-syncs companion → exit 0" || bad "deploy did not re-sync companion"

if [ "$fail" -ne 0 ]; then echo "[deploy-check-test] FAIL"; exit 1; fi
echo "[deploy-check-test] PASS"
