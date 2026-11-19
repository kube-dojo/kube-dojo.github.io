"""Unit tests for `.claude/lib/_lib_parse_pr_ref.py`.

Extracts the PR ref from a `gh pr merge <ref>` shell command. The
extracted helper replaces a 20-line inline parser duplicated between
the two `gh pr merge` quality hooks. The previous parser had a latent
bug (always returned the literal string `pr` as PR_REF) that silently
failed every explicit-PR-ref merge open.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / ".claude" / "lib" / "_lib_parse_pr_ref.py"


def run_helper(command: str) -> str:
    result = subprocess.run(
        [sys.executable, str(HELPER), command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_positional_ref_after_merge() -> None:
    assert run_helper("gh pr merge 1234 --squash") == "1234"


def test_flag_then_ref() -> None:
    assert run_helper("gh pr merge --squash 5678") == "5678"


def test_url_ref() -> None:
    assert (
        run_helper("gh pr merge --auto https://github.com/owner/repo/pull/9")
        == "https://github.com/owner/repo/pull/9"
    )


def test_branch_ref() -> None:
    assert run_helper("gh pr merge feature/foo --rebase") == "feature/foo"


def test_no_ref_returns_empty() -> None:
    assert run_helper("gh pr merge --squash") == ""


def test_cd_prefix_does_not_confuse_parser() -> None:
    assert run_helper("cd .worktrees/feat-x && gh pr merge 1234 --squash") == "1234"


def test_sudo_prefix_does_not_confuse_parser() -> None:
    assert run_helper("sudo gh pr merge 4242 --squash") == "4242"


def test_env_prefix_does_not_confuse_parser() -> None:
    assert run_helper("GH_TOKEN= gh pr merge 7 --squash") == "7"


def test_old_bug_regression_pr_is_not_returned() -> None:
    # The previous parser returned the literal `pr` token from `gh pr merge`.
    # Make this assertion explicit so any future refactor that re-introduces
    # the bug trips this test instead of silently passing.
    ref = run_helper("gh pr merge 9 --squash")
    assert ref == "9"
    assert ref != "pr"


def test_unparseable_command_returns_empty() -> None:
    # Unbalanced quotes → shlex.ValueError → helper prints nothing.
    assert run_helper('cd "unterminated && gh pr merge 1') == ""


def test_no_gh_pr_merge_present_returns_empty() -> None:
    assert run_helper("git status") == ""
    assert run_helper("gh pr view 1234") == ""
    assert run_helper("gh issue create") == ""
