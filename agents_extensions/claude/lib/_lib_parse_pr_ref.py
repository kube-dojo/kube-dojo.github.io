"""Extract the PR ref from a `gh pr merge <ref>` shell command.

Walks tokens left-to-right looking for the literal triple ``gh pr merge``,
then prints the first non-flag token after it. Empty stdout means no
explicit ref was on the command — caller should fall back to gh's
auto-detect-from-current-branch behaviour.

Used by both `gh pr merge` quality hooks
(``block-content-merge-without-learner-check.sh``,
``block-bugfix-merge-without-regression-test.sh``). Extracted in the
same PR that fixed the parser's latent bug — the previous inline
version stopped immediately on matching ``gh`` and then consumed the
next iteration's ``pr`` token, so PR_REF was always the literal string
``"pr"`` and ``gh pr view pr`` 404'd, silently failing the hook open.

Usage:
    python3 _lib_parse_pr_ref.py <command>

Prints the PR ref (number / URL / branch) on stdout, or nothing if
absent / unparseable.
"""
from __future__ import annotations

import shlex
import sys


def parse_pr_ref(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    i = 0
    while i < len(tokens):
        if (
            tokens[i] == "gh"
            and i + 2 < len(tokens)
            and tokens[i + 1] == "pr"
            and tokens[i + 2] == "merge"
        ):
            j = i + 3
            while j < len(tokens):
                if tokens[j].startswith("-"):
                    j += 1
                    continue
                return tokens[j]
            return None
        i += 1
    return None


def main() -> None:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: _lib_parse_pr_ref.py <command>\n")
        sys.exit(2)
    ref = parse_pr_ref(sys.argv[1])
    if ref is not None:
        print(ref)


if __name__ == "__main__":
    main()
