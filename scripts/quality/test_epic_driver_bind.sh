#!/usr/bin/env bash
# Regression tests for scripts/lib/epic_driver_bind.sh — thin --epic launcher bind.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../lib/epic_driver_bind.sh"
# shellcheck source=../lib/epic_driver_bind.sh
source "$LIB"

fail=0
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    printf '  ok   %-50s [%s]\n' "$label" "$actual"
  else
    printf '  FAIL %-50s expected [%s] got [%s]\n' "$label" "$expected" "$actual"
    fail=1
  fi
}

assert_eq "single --epic <N>"           "2272" "$(epic_number_from_argv --epic 2272)"
assert_eq "--epic=<N>"                  "2272" "$(epic_number_from_argv --epic=2272)"
assert_eq "stops at --"                 ""     "$(epic_number_from_argv -- --epic 2272)"
assert_eq "epic before -- still wins"   "2272" "$(epic_number_from_argv --epic 2272 -- rest)"
assert_eq "repeated: last wins"         "99"   "$(epic_number_from_argv --epic 1 --epic 99)"
assert_eq "no --epic"                   ""     "$(epic_number_from_argv --chrome)"
assert_eq "empty argv"                  ""     "$(epic_number_from_argv)"

strip="$(epic_strip_from_argv --epic 2272 --chrome --permission-mode bypassPermissions | tr '\n' ' ')"
assert_eq "strip removes --epic N"      "--chrome --permission-mode bypassPermissions " "$strip"

strip2="$(epic_strip_from_argv --epic=2272 --agent epic-driver | tr '\n' ' ')"
assert_eq "strip removes --epic=N"      "--agent epic-driver " "$strip2"

if epic_validate_number 2272; then
  assert_eq "validate ok 2272" "0" "0"
else
  assert_eq "validate ok 2272" "0" "1"
fi
if epic_validate_number 0 >/dev/null 2>&1; then
  assert_eq "validate rejects 0" "1" "0"
else
  assert_eq "validate rejects 0" "1" "1"
fi
if epic_validate_number abc >/dev/null 2>&1; then
  assert_eq "validate rejects abc" "1" "0"
else
  assert_eq "validate rejects abc" "1" "1"
fi

prompt="$(epic_driver_prompt 2272)"
case "$prompt" in
  *'epic #2272'*|*'#2272'*) assert_eq "prompt names epic" "yes" "yes" ;;
  *) assert_eq "prompt names epic" "yes" "no" ;;
esac
case "$prompt" in
  *codexbar*|*'CodexBar'*) assert_eq "prompt requires CodexBar" "yes" "yes" ;;
  *) assert_eq "prompt requires CodexBar" "yes" "no" ;;
esac
case "$prompt" in
  *dispatch_smart*|*'fleet'*) assert_eq "prompt requires fleet" "yes" "yes" ;;
  *) assert_eq "prompt requires fleet" "yes" "no" ;;
esac
case "$prompt" in
  *drive-epic*) assert_eq "prompt loads drive-epic" "yes" "yes" ;;
  *) assert_eq "prompt loads drive-epic" "yes" "no" ;;
esac

( set -e; source "$LIB"; n="$(epic_number_from_argv --epic 5)"; epic_validate_number "$n" )
assert_eq "set -e: helpers return 0" "0" "$?"

if [ "$fail" -ne 0 ]; then
  echo "[epic-driver-bind-test] FAIL"
  exit 1
fi
echo "[epic-driver-bind-test] PASS"
