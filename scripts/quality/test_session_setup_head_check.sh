#!/usr/bin/env bash
set -euo pipefail

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_SOURCE="$SCRIPT_DIR/../../agents_extensions/claude/hooks/kubedojo-session-setup.sh"
WORKROOT=$(mktemp -d)
WORKROOT_OK=""
STDERR_FILE=$(mktemp)
cleanup() {
  rm -rf "$WORKROOT"
  if [ -n "$WORKROOT_OK" ]; then
    rm -rf "$WORKROOT_OK"
  fi
  rm -f "$STDERR_FILE"
}
trap cleanup EXIT

mkdir -p "$WORKROOT/.claude/hooks"
cp "$HOOK_SOURCE" "$WORKROOT/.claude/hooks/session-setup.sh"
chmod +x "$WORKROOT/.claude/hooks/session-setup.sh"

git -C "$WORKROOT" init -q
git -C "$WORKROOT" config user.email "ci@example.com"
git -C "$WORKROOT" config user.name "CI"
echo "bootstrap" > "$WORKROOT/file.txt"
git -C "$WORKROOT" add file.txt
git -C "$WORKROOT" commit -q -m "session-setup test seed"
git -C "$WORKROOT" checkout -b feature

if bash "$WORKROOT/.claude/hooks/session-setup.sh" >/dev/null 2>"$STDERR_FILE"; then
  echo "[session-setup-test] expected guard to fail on non-main branch"
  exit 1
fi

grep -q "PRIMARY TREE NOT ON main" "$STDERR_FILE" || {
  echo "[session-setup-test] missing primary branch guard message"
  cat "$STDERR_FILE"
  exit 1
}

grep -q "currently 'feature'" "$STDERR_FILE" || {
  echo "[session-setup-test] missing branch detail in guard message"
  cat "$STDERR_FILE"
  exit 1
}

echo "[session-setup-test] PASS"

# happy path: main branch should not error
WORKROOT_OK=$(mktemp -d)
mkdir -p "$WORKROOT_OK/.claude/hooks"
cp "$HOOK_SOURCE" "$WORKROOT_OK/.claude/hooks/session-setup.sh"
chmod +x "$WORKROOT_OK/.claude/hooks/session-setup.sh"

git -C "$WORKROOT_OK" init -q -b main
git -C "$WORKROOT_OK" config user.email "ci@example.com"
git -C "$WORKROOT_OK" config user.name "CI"
git -C "$WORKROOT_OK" commit --allow-empty -qm init

mkdir -p "$WORKROOT_OK/bin" "$WORKROOT_OK/home"
printf '#!/bin/sh\nprintf "200"\n' > "$WORKROOT_OK/bin/curl"
printf '#!/bin/sh\nprintf "[]\\n"\n' > "$WORKROOT_OK/bin/gh"
chmod +x "$WORKROOT_OK/bin/"{curl,gh}
export PATH="$WORKROOT_OK/bin:$PATH"
export HOME="$WORKROOT_OK/home"

if ! bash "$WORKROOT_OK/.claude/hooks/session-setup.sh" >/dev/null 2>&1; then
  echo "[session-setup-test] hook errored on primary=main"
  exit 1
fi

echo "[session-setup-test] PASS (main)"
