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
  PR head), the artifact exists, and its committed content (paths and blob
  ids; file modes are ignored) differs both from the start and from every
  pre-dispatch commit the new commits build on (the prior-output boundary).

An idle run, an uncommitted write, a commit followed by its reversal, a reset
to an older commit, a fast-forward to output that existed before dispatch
(also when followed by an edit and its reversal) and an unrelated commit are
each refused with a typed reason. Every git call is bounded; an expired or
failed call refuses with ``git_error``.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ArtifactKind = Literal["file", "dir"]
_REGULAR_MODES = (b"100644", b"100755")


@dataclass(frozen=True)
class Snapshot:
    """Pre-dispatch state: the start commit and every commit tip known then."""

    start: str | None
    prior_tips: tuple[str, ...]


GIT_TIMEOUT_S = 120


def _git(worktree: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run git with raw bytes in and out (paths may be any bytes); bounded."""
    argv = ["git", *args]
    try:
        return subprocess.run(
            argv, cwd=worktree, input=stdin, capture_output=True, check=False, timeout=GIT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, b"", b"git timed out")


def _ids(raw: bytes) -> list[str]:
    """Object ids from git output (hex only)."""
    return raw.decode("ascii", "replace").split()


def _exclusions(shas: list[str]) -> bytes:
    return "".join(f"^{s}\n" for s in shas).encode("ascii")


def rev(worktree: Path, ref: str) -> str | None:
    """The commit ``ref`` names, or ``None``."""
    r = _git(worktree, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    ids = _ids(r.stdout) if r.returncode == 0 else []
    return ids[0] if len(ids) == 1 else None


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
    tips = {start, *_ids(r.stdout), *(s for s in prior_outputs if s)}
    return Snapshot(start, tuple(sorted(tips)))


def _content(worktree: Path, commit: str, artifact: str, kind: ArtifactKind) -> frozenset[tuple[bytes, bytes, bytes]] | None:
    """The artifact's committed entries at ``commit``: ``(raw path, type, blob id)`` triples.

    ``kind="file"`` lists the exact path only (``ls-tree`` without ``-r``), so
    a directory or a symlink standing at that path shows as itself.
    ``kind="dir"`` lists every entry below the directory. The type is
    ``b"file"`` for a regular file of either mode (an executable-bit change is
    not new content) and the raw mode for anything else (symlink, submodule,
    tree). ``None`` means git failed.
    """
    args = ["ls-tree", "-z", commit, "--", artifact] if kind == "file" else ["ls-tree", "-r", "-z", commit, "--", artifact]
    r = _git(worktree, *args)
    if r.returncode != 0:
        return None
    entries = set()
    for entry in r.stdout.split(b"\0"):
        meta, _, path = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3:
            continue
        mode, _otype, oid = fields
        if kind == "file" and path != os.fsencode(artifact):
            continue
        entries.add((path, b"file" if mode in _REGULAR_MODES else mode, oid))
    return frozenset(entries)


def _known_commits(worktree: Path, shas: tuple[str, ...]) -> list[str]:
    if not shas:
        return []
    r = _git(worktree, "cat-file", "--batch-check=%(objectname) %(objecttype)",
             stdin="".join(f"{s}\n" for s in shas).encode("ascii"))
    if r.returncode != 0:
        return []
    known = []
    for line in r.stdout.decode("ascii", "replace").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1] == "commit":
            known.append(fields[0])
    return known


def produced(
    worktree: Path, before: Snapshot, artifact: str, ref: str = "HEAD", *, kind: ArtifactKind,
) -> tuple[str | None, str | None]:
    """Return ``(checked commit, None)`` when ``ref`` holds new work on ``artifact``.

    Otherwise return ``(checked commit or None, reason)`` with reason one of
    ``no_new_commit``, ``not_descendant``, ``no_new_artifact_commit``,
    ``no_net_change``, ``artifact_missing``, ``artifact_type_mismatch`` or
    ``git_error``. ``kind`` names what the caller asked for: one regular file
    at exactly ``artifact``, or a directory whose entries are all regular
    files.
    """
    final = rev(worktree, ref)
    if before.start is None or final is None or final == before.start:
        return final, "no_new_commit"
    if _git(worktree, "merge-base", "--is-ancestor", before.start, final).returncode != 0:
        return final, "not_descendant"
    excluded = _known_commits(worktree, before.prior_tips)
    if before.start not in excluded:
        return final, "git_error"
    fresh = _git(worktree, "rev-list", "--stdin", final, "--", artifact, stdin=_exclusions(excluded))
    if fresh.returncode != 0:
        return final, "git_error"
    if not fresh.stdout.strip():
        return final, "no_new_artifact_commit"
    boundary = _git(worktree, "rev-list", "--boundary", "--stdin", final, stdin=_exclusions(excluded))
    if boundary.returncode != 0:
        return final, "git_error"
    final_content = _content(worktree, final, artifact, kind)
    if final_content is None:
        return final, "git_error"
    if not final_content:
        return final, "artifact_missing"
    if any(entry_type != b"file" for _path, entry_type, _oid in final_content):
        return final, "artifact_type_mismatch"
    bases = {before.start} | {line[1:] for line in _ids(boundary.stdout) if line.startswith("-")}
    for base in sorted(bases):
        base_content = _content(worktree, base, artifact, kind)
        if base_content is None:
            return final, "git_error"
        if base_content == final_content:
            return final, "no_net_change"
    return final, None


def select_product_root(primary: Path) -> str:
    """Name the product checkout for the release runtime before a writer runs.

    The installed lu-machinery runtime has no implicit product: write
    admission refuses unless ``LU_PRODUCT_ROOT`` names one. A direct
    KubeDojo CLI run selects its primary checkout through that variable,
    unless the operator already set it, and the selected value gets the
    release's own check (an absolute path to an existing directory) before
    any worktree is set up. Returns the selected root; raises ``ValueError``
    with the reason otherwise.
    """
    if not os.environ.get("LU_PRODUCT_ROOT"):
        os.environ["LU_PRODUCT_ROOT"] = str(primary)
    value = os.environ["LU_PRODUCT_ROOT"]
    if "\0" in value or not os.path.isabs(value) or not os.path.isdir(value):
        raise ValueError(f"LU_PRODUCT_ROOT={value!r} must be an absolute path to an existing directory")
    return value
