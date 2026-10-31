#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(cd "$ROOT/../.." && pwd)/.venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "smoketest_review_verifier: missing .venv/bin/python" >&2
  exit 1
fi

mkdir -p "$ROOT/.agent"
FIXTURE_DIR="$(mktemp -d "${ROOT}/.agent/review-verifier-smoke.XXXXXX")"
trap 'rm -rf "$FIXTURE_DIR"' EXIT

cat >"$FIXTURE_DIR/fixture.py" <<'EOF'
alpha = 1
beta = 2
gamma = 3
EOF

FIXTURE_PATH="${FIXTURE_DIR#"$ROOT"/}/fixture.py"

REVIEW="$(cat <<EOF
FINDING: verified quote
FILE:LINE: ${FIXTURE_PATH}:2
CURRENT CODE:
  beta = 2
WHY: example
FIX: n/a

FINDING: hallucinated quote
FILE:LINE: ${FIXTURE_PATH}:4
CURRENT CODE:
  delta = 99
WHY: example
FIX: n/a
EOF
)"

# Documented runbook path: stdin review + --pr (no --from-pr).
REVIEW_FILE="$FIXTURE_DIR/review.txt"
printf '%s\n' "$REVIEW" >"$REVIEW_FILE"
set +e
CLI_OUT="$("$PYTHON" scripts/verify_review.py --pr 0 <"$REVIEW_FILE" 2>&1)"
CLI_RC=$?
set -e

if [[ "$CLI_RC" -ne 1 ]]; then
  echo "smoketest_review_verifier: expected exit 1 (quote_missing), got ${CLI_RC}" >&2
  exit 1
fi

if ! grep -q '1 verified, 0 line_mismatch, 1 quote_missing' <<<"$CLI_OUT"; then
  echo "smoketest_review_verifier: unexpected verifier summary:" >&2
  echo "$CLI_OUT" >&2
  exit 1
fi

if ! grep -q '`verified` '"$FIXTURE_PATH"':2' <<<"$CLI_OUT"; then
  echo "smoketest_review_verifier: missing verified row in output" >&2
  exit 1
fi

if ! grep -q '`quote_missing` '"$FIXTURE_PATH"':4' <<<"$CLI_OUT"; then
  echo "smoketest_review_verifier: missing quote_missing row in output" >&2
  exit 1
fi

# Anti-regression: empty stdin must not be mistaken for a clean verification pass.
set +e
EMPTY_OUT="$("$PYTHON" scripts/verify_review.py --pr 0 </dev/null 2>&1)"
EMPTY_RC=$?
set -e
if [[ "$EMPTY_RC" -eq 0 ]] || ! grep -q 'Review verification failed: empty review' <<<"$EMPTY_OUT"; then
  echo "smoketest_review_verifier: empty stdin did not fail explicitly" >&2
  exit 1
fi

# Parser surface must exist (runbook documents --from-pr).
if ! "$PYTHON" scripts/verify_review.py --help | grep -q -- '--from-pr'; then
  echo "smoketest_review_verifier: verify_review.py missing --from-pr flag" >&2
  exit 1
fi

echo "smoketest_review_verifier: ok (verified,quote_missing via CLI)"
