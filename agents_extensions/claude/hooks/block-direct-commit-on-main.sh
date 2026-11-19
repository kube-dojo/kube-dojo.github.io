#!/bin/bash
# shellcheck source=.claude/hooks/_lib.sh
source "${BASH_SOURCE[0]%/*}/_lib.sh"
set -euo pipefail

# Hook: PreToolUse (Bash) — Block direct commits to main unless the subject is pipeline-owned or PR-backed.
#
# Effective-tree resolution: the hook checks the branch of the directory the
# `git commit` will ACTUALLY land in, not the harness-reported cwd. Two
# patterns are recognised:
#   1. `git -C <path> commit ...`     -> check <path>
#   2. `cd <path> [&&|;] git commit`  -> check <path> (relative to harness cwd)
# Other patterns fall back to the harness-reported cwd. This avoids
# false-positive denies on legitimate worktree-branch commits.

RAW_PAYLOAD=$(cat)

TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$RAW_PAYLOAD")
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

PAYLOAD=$(read_tool_payload <<<"$RAW_PAYLOAD")
COMMAND=${PAYLOAD%%$'\t'*}
CWD=${PAYLOAD#*$'\t'}

if [ -z "$COMMAND" ]; then
  exit 0
fi

if ! echo "$COMMAND" | grep -Eq '(^|[;&|[:space:]])git[[:space:]]+([^[:space:]]+[[:space:]]+)*commit([[:space:]]|$)'; then
  exit 0
fi

PARSE_RESULT=$(python3 -c '
import os
import shlex
import sys

command = sys.argv[1]
harness_cwd = sys.argv[2]


def resolve(base: str, candidate: str) -> str:
    if os.path.isabs(candidate):
        return os.path.normpath(candidate)
    return os.path.normpath(os.path.join(base, candidate))


try:
    tokens = shlex.split(command)
except ValueError as exc:
    print(f"UNKNOWN\t{harness_cwd}\tcould not parse shell command ({exc})")
    raise SystemExit


# Walk tokens left-to-right tracking:
#   effective_dir - updated by leading `cd <path>` segments before the git invocation
#   git_idx       - index of the `git` token whose subcommand is `commit`
effective_dir = harness_cwd
git_idx = None
i = 0
while i < len(tokens):
    tok = tokens[i]
    # Step over shell separators so a chain like `cd X && git commit` is
    # treated as two segments.
    if tok in (";", "&&", "||", "|"):
        i += 1
        continue
    if tok == "cd" and i + 1 < len(tokens):
        effective_dir = resolve(effective_dir, tokens[i + 1])
        i += 2
        continue
    if tok == "git" and i + 1 < len(tokens):
        # Look ahead for an optional `-C <path>` before the subcommand.
        j = i + 1
        local_dir = effective_dir
        while j < len(tokens) and tokens[j].startswith("-"):
            if tokens[j] == "-C" and j + 1 < len(tokens):
                local_dir = resolve(effective_dir, tokens[j + 1])
                j += 2
                continue
            if tokens[j].startswith("-C") and tokens[j] != "-C":
                local_dir = resolve(effective_dir, tokens[j][2:])
                j += 1
                continue
            # Some other git-level flag (e.g. --no-pager); ignore but advance.
            j += 1
        if j < len(tokens) and tokens[j] == "commit":
            effective_dir = local_dir
            git_idx = j
            break
    i += 1

if git_idx is None:
    print(f"UNKNOWN\t{effective_dir}\tmatched git commit text, but could not locate argv")
    raise SystemExit

args = tokens[git_idx + 1 :]

expanded_args = []
for token in args:
    if (
        token.startswith("-")
        and not token.startswith("--")
        and len(token) > 2
        and "m" in token
        and token[-1] == "m"
    ):
        expanded_args.append(token[:-1])
        expanded_args.append("-m")
    else:
        expanded_args.append(token)
args = expanded_args

for index, token in enumerate(args):
    if token in {"-F", "--file"}:
        print(f"FILE_MSG\t{effective_dir}\tcommit message comes from a file")
        raise SystemExit
    if token.startswith("-F") and token != "-F":
        print(f"FILE_MSG\t{effective_dir}\tcommit message comes from a file")
        raise SystemExit
    if token.startswith("--file="):
        print(f"FILE_MSG\t{effective_dir}\tcommit message comes from a file")
        raise SystemExit

subject = None
for index, token in enumerate(args):
    if token in {"-m", "--message"}:
        if index + 1 >= len(args):
            print(f"NO_SUBJECT\t{effective_dir}\t-m was present without a statically visible message")
            raise SystemExit
        subject = args[index + 1]
        break
    if token.startswith("-m") and token != "-m":
        subject = token[2:]
        break
    if token.startswith("--message="):
        subject = token.split("=", 1)[1]
        break

if subject is None:
    if "--amend" in args and "--no-edit" in args:
        print(f"AMEND\t{effective_dir}\tcommit amend keeps the existing message")
    else:
        print(f"NO_SUBJECT\t{effective_dir}\tno statically visible -m commit subject")
    raise SystemExit

if subject.startswith("$("):
    print(f"DYNAMIC\t{effective_dir}\tcommit subject is dynamically built with command substitution")
    raise SystemExit

print(f"SUBJECT\t{effective_dir}\t" + (subject.splitlines()[0] if subject else ""))
' "$COMMAND" "$CWD" || true)

PARSE_KIND=${PARSE_RESULT%%$'\t'*}
PARSE_REST=${PARSE_RESULT#*$'\t'}
EFFECTIVE_DIR=${PARSE_REST%%$'\t'*}
PARSE_DETAIL=${PARSE_REST#*$'\t'}

if [ -z "${EFFECTIVE_DIR}" ]; then
  EFFECTIVE_DIR=$CWD
fi

BRANCH=$(git -C "$EFFECTIVE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
if [ "$BRANCH" != "main" ]; then
  exit 0
fi

case "$PARSE_KIND" in
  FILE_MSG|AMEND|DYNAMIC|NO_SUBJECT|UNKNOWN)
    printf '[hook note] direct commit to main not introspected: %s; allowing.\n' "$PARSE_DETAIL" >&2
    exit 0
    ;;
esac

SUBJECT=$PARSE_DETAIL

case "$SUBJECT" in
  backfill:* | backfill\ * | handoff:* | handoff\ * | docs\(status\):*)
    exit 0
    ;;
esac

if printf '%s\n' "$SUBJECT" | grep -Eq '\(#[0-9]+\)'; then
  exit 0
fi

deny \
  "direct commit to main without PR ref is blocked." \
  "subject must start with one of [backfill, handoff, docs(status):] OR contain (#N)." \
  "feedback_no_direct_push_to_main.md"
