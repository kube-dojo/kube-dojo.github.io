"""Unit tests for `.claude/lib/_lib_resolve_cwd.py`.

The helper walks `cd <path>` segments in a shell command, starting from a
harness-reported cwd, and prints the effective cwd at the point where a
named target command is reached. Used by the `gh pr merge` hooks to fix
the same bug class as #1321 (false-negative-allow direction).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / ".claude" / "lib" / "_lib_resolve_cwd.py"


def run_helper(command: str, harness_cwd: str, target: str) -> str:
    result = subprocess.run(
        [sys.executable, str(HELPER), command, harness_cwd, target],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_no_cd_returns_harness_cwd() -> None:
    assert run_helper("gh pr merge 1234 --squash", "/primary", "gh") == "/primary"


def test_cd_relative_resolves_under_harness_cwd() -> None:
    assert (
        run_helper("cd .worktrees/feat-x && gh pr merge --squash", "/primary", "gh")
        == "/primary/.worktrees/feat-x"
    )


def test_cd_absolute_overrides_harness_cwd() -> None:
    assert (
        run_helper("cd /tmp/worktree && gh pr merge", "/primary", "gh")
        == "/tmp/worktree"
    )


def test_cd_chain_resolves_to_last_segment() -> None:
    assert (
        run_helper("cd .worktrees && cd feat-y && gh pr merge", "/primary", "gh")
        == "/primary/.worktrees/feat-y"
    )


def test_cd_after_target_is_ignored() -> None:
    # cd that happens AFTER the target command should not affect the
    # effective cwd of the target. The walker stops at the target.
    assert (
        run_helper("gh pr merge && cd /other", "/primary", "gh")
        == "/primary"
    )


def test_unparseable_command_falls_back_to_harness_cwd() -> None:
    # Quotes unbalanced → shlex raises ValueError → helper returns harness cwd.
    assert run_helper('cd "unterminated && gh', "/primary", "gh") == "/primary"


def test_target_never_appears_returns_last_seen_effective_dir() -> None:
    # If the target is never reached, we still return the running effective
    # dir. The hook treats this as a best-effort fallback.
    assert (
        run_helper("cd .worktrees/feat-x && echo hello", "/primary", "gh")
        == "/primary/.worktrees/feat-x"
    )


def test_cd_dot_dot_resolves() -> None:
    # /primary + cd .worktrees/x → /primary/.worktrees/x
    # + cd ../.. → up 2 levels → /primary
    assert (
        run_helper("cd .worktrees/x && cd ../.. && gh pr merge", "/primary", "gh")
        == "/primary"
    )


def test_target_with_different_name_works() -> None:
    # Helper is generic over the target name.
    assert (
        run_helper("cd /repo && git -C . status", "/primary", "git")
        == "/repo"
    )
