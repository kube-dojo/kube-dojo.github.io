"""Resolve the effective cwd at the point of a target command.

Walks tokens left-to-right starting from a harness-reported cwd. Tracks
`cd <path>` segments (relative to the running effective dir) until a token
matching ``target_name`` is reached. Prints the resolved effective dir.

This mirrors the same-class fix introduced in
``block-direct-commit-on-main.sh`` (PR #1321) but is intentionally smaller:
it only needs to handle ``cd <path>`` segments. ``gh`` (the only consumer)
has no ``-C`` flag, so there is no per-invocation tree override to honour.

Usage:
    python3 _lib_resolve_cwd.py <command> <harness_cwd> <target_name>

Prints the resolved effective dir on stdout. Falls back to ``harness_cwd``
if the command cannot be parsed or the target is never found.
"""
from __future__ import annotations

import os
import shlex
import sys


def _resolve(base: str, candidate: str) -> str:
    if os.path.isabs(candidate):
        return os.path.normpath(candidate)
    return os.path.normpath(os.path.join(base, candidate))


def resolve_effective_cwd(command: str, harness_cwd: str, target_name: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return harness_cwd

    effective_dir = harness_cwd
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in (";", "&&", "||", "|"):
            i += 1
            continue
        if tok == "cd" and i + 1 < len(tokens):
            effective_dir = _resolve(effective_dir, tokens[i + 1])
            i += 2
            continue
        if tok == target_name:
            break
        i += 1

    return effective_dir


def main() -> None:
    if len(sys.argv) != 4:
        sys.stderr.write(
            "usage: _lib_resolve_cwd.py <command> <harness_cwd> <target_name>\n"
        )
        sys.exit(2)
    command, harness_cwd, target_name = sys.argv[1], sys.argv[2], sys.argv[3]
    print(resolve_effective_cwd(command, harness_cwd, target_name))


if __name__ == "__main__":
    main()
