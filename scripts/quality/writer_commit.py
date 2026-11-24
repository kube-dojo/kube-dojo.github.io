"""Decide whether THIS writer run produced the requested, committed artifact.

The lu-machinery runner reports a parsed provider success for a write-mode run
without checking that the run produced anything (the in-tree fork's no-write
and pushed-commit checks did not move to the release). The KubeDojo writers
(AI-History prose and research, the #388 pilot) deliver a local commit, so
their callers prove the delivery from git state instead:

* :func:`snapshot` runs before dispatch. It records the start commit of the
  ref the writer must advance, and every commit a ref or reflog entry pointed
  at, in any worktree of the repository.
* :func:`produced` runs after a reported success. It accepts the checked
  commit only when it strictly descends from the start, at least one commit
  in its history touches the artifact and was reachable from none of the
  pre-dispatch tips (or from a known prior output such as an earlier published
  PR head), the artifact differs from the start, and the artifact exists.

An idle run, an uncommitted write, a commit followed by its reversal, a reset
to an older commit, a fast-forward to output that existed before dispatch and
an unrelated commit are each refused with a typed reason.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Snapshot:
    """Pre-dispatch state: the start commit and every commit tip known then."""

    start: str | None
    prior_tips: tuple[str, ...]


def _git(worktree: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=worktree, input=stdin, capture_output=True, text=True, check=False,
    )


def rev(worktree: Path, ref: str) -> str | None:
    """The commit ``ref`` names, or ``None``."""
    r = _git(worktree, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


def snapshot(worktree: Path, ref: str = "HEAD", prior_outputs: tuple[str | None, ...] = ()) -> Snapshot:
    """Record the start commit of ``ref`` and every commit tip known before dispatch.

    ``prior_outputs`` adds commits known from elsewhere, such as the head a PR
    branch already had on GitHub. A failed read yields ``start=None``, which
    :func:`produced` refuses.
    """
    start = rev(worktree, ref)
    r = _git(worktree, "rev-list", "--all", "--reflog", "--no-walk")
    if start is None or r.returncode != 0:
        return Snapshot(None, ())
    tips = {start, *r.stdout.split(), *(s for s in prior_outputs if s)}
    return Snapshot(start, tuple(sorted(tips)))


def _known_commits(worktree: Path, shas: tuple[str, ...]) -> list[str]:
    if not shas:
        return []
    r = _git(worktree, "cat-file", "--batch-check=%(objectname) %(objecttype)", stdin="".join(f"{s}\n" for s in shas))
    if r.returncode != 0:
        return []
    return [line.split()[0] for line in r.stdout.splitlines() if line.endswith(" commit")]


def produced(worktree: Path, before: Snapshot, artifact: str, ref: str = "HEAD") -> tuple[str | None, str | None]:
    """Return ``(checked commit, None)`` when ``ref`` holds new work on ``artifact``.

    Otherwise return ``(checked commit or None, reason)`` with reason one of
    ``no_new_commit``, ``not_descendant``, ``no_new_artifact_commit``,
    ``no_net_change``, ``artifact_missing`` or ``git_error``.
    """
    final = rev(worktree, ref)
    if before.start is None or final is None or final == before.start:
        return final, "no_new_commit"
    if _git(worktree, "merge-base", "--is-ancestor", before.start, final).returncode != 0:
        return final, "not_descendant"
    excluded = _known_commits(worktree, before.prior_tips)
    if before.start not in excluded:
        return final, "git_error"
    fresh = _git(worktree, "rev-list", "--stdin", final, "--", artifact,
                 stdin="".join(f"^{s}\n" for s in excluded))
    if fresh.returncode != 0:
        return final, "git_error"
    if not fresh.stdout.strip():
        return final, "no_new_artifact_commit"
    diff = _git(worktree, "diff", "--name-only", before.start, final, "--", artifact)
    if diff.returncode != 0:
        return final, "git_error"
    if not diff.stdout.strip():
        return final, "no_net_change"
    tree = _git(worktree, "ls-tree", "-r", "--name-only", final, "--", artifact)
    if tree.returncode != 0 or not tree.stdout.strip():
        return final, "artifact_missing"
    return final, None
