"""Tests for `.claude/kubedojo-hooks/block-bugfix-merge-without-regression-test.sh`.

The hook fires on `gh pr merge` for bugfix PRs (title starts with ``fix:`` /
``fix(...)``: OR body has ``Fixes #N`` / ``Closes #N``). It requires a
``Regression test:`` line in the body that points to a test file which
(a) is in this PR's files list and (b) references the issue number.

Pytest is intentionally NOT run by the hook — CI's job. The hook is a
fast (<1s) mechanical receipt that the regression test exists.
"""
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "kubedojo-hooks" / "block-bugfix-merge-without-regression-test.sh"
BASH = "/bin/bash"


def run_hook(
    command: str,
    *,
    pr_json: dict | None,
    fixture_files: dict[str, str] | None,
    tmp_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    if pr_json is not None:
        pr_json_path = tmp_path / "pr.json"
        pr_json_path.write_text(json.dumps(pr_json))
        env["KUBEDOJO_HOOK_GH_JSON"] = str(pr_json_path)
    if fixture_files is not None:
        fixture_dir = tmp_path / "fixtures"
        for rel, contents in fixture_files.items():
            target = fixture_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        env["KUBEDOJO_HOOK_FILE_FIXTURE_DIR"] = str(fixture_dir)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command, "cwd": str(tmp_path)},
    }
    return subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=tmp_path,
    )


TEST_FILE_WITH_ISSUE = (
    "import pytest\n\n"
    "# Regression test for issue #1212 (citation backfill cascade-fail).\n"
    "def test_inject_failure_restores_seed_json():\n"
    "    assert True\n"
)

TEST_FILE_WITHOUT_ISSUE = (
    "import pytest\n\n"
    "def test_inject_failure_restores_seed_json():\n"
    "    assert True\n"
)


def test_non_bash_tool_is_ignored(tmp_path: Path) -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}}
    result = subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 0


def test_non_merge_command_is_ignored(tmp_path: Path) -> None:
    result = run_hook(
        "git status",
        pr_json=None,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0


def test_non_fix_pr_is_allowed(tmp_path: Path) -> None:
    pr = {
        "body": "Adds a new helper.",
        "files": [{"path": "scripts/helper.py"}],
        "headRefOid": "abc123",
        "title": "feat: new helper",
        "number": 9100,
    }
    result = run_hook(
        "gh pr merge 9100 --squash",
        pr_json=pr,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_fix_pr_without_regression_test_is_denied(tmp_path: Path) -> None:
    pr = {
        "body": "Fixes #1212 — restores the seed JSON on inject failure.",
        "files": [{"path": "scripts/quality/pipeline.py"}],
        "headRefOid": "abc123",
        "title": "fix(pipeline): restore seed on inject failure",
        "number": 9101,
    }
    result = run_hook(
        "gh pr merge 9101 --squash",
        pr_json=pr,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a 'Regression test:' line" in result.stderr


def test_fix_pr_with_test_not_in_pr_is_denied(tmp_path: Path) -> None:
    pr = {
        "body": (
            "Fixes #1212.\n\n"
            "Regression test: tests/test_backfill_seed_restore.py\n"
        ),
        "files": [
            {"path": "scripts/quality/pipeline.py"},
            # Note: test file not in PR files list.
        ],
        "headRefOid": "abc123",
        "title": "fix(pipeline): restore seed on inject failure",
        "number": 9102,
    }
    result = run_hook(
        "gh pr merge 9102 --squash",
        pr_json=pr,
        fixture_files={
            "tests/test_backfill_seed_restore.py": TEST_FILE_WITH_ISSUE,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "is not part of this PR" in result.stderr


def test_fix_pr_with_test_missing_issue_ref_is_denied(tmp_path: Path) -> None:
    pr = {
        "body": (
            "Fixes #1212.\n\n"
            "Regression test: tests/test_backfill_seed_restore.py\n"
        ),
        "files": [
            {"path": "scripts/quality/pipeline.py"},
            {"path": "tests/test_backfill_seed_restore.py"},
        ],
        "headRefOid": "abc123",
        "title": "fix(pipeline): restore seed on inject failure",
        "number": 9103,
    }
    result = run_hook(
        "gh pr merge 9103 --squash",
        pr_json=pr,
        fixture_files={
            "tests/test_backfill_seed_restore.py": TEST_FILE_WITHOUT_ISSUE,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "does not reference any of the issues" in result.stderr


def test_fix_pr_with_valid_regression_test_is_allowed(tmp_path: Path) -> None:
    pr = {
        "body": (
            "Fixes #1212 — the citation backfill cascade-fail bug.\n\n"
            "Regression test: tests/test_backfill_seed_restore.py\n"
        ),
        "files": [
            {"path": "scripts/quality/pipeline.py"},
            {"path": "tests/test_backfill_seed_restore.py"},
        ],
        "headRefOid": "abc123",
        "title": "fix(pipeline): restore seed on inject failure",
        "number": 9104,
    }
    result = run_hook(
        "gh pr merge 9104 --squash",
        pr_json=pr,
        fixture_files={
            "tests/test_backfill_seed_restore.py": TEST_FILE_WITH_ISSUE,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_fix_title_with_paren_issue_ref_recognized(tmp_path: Path) -> None:
    # Some bugfix PRs ref the issue only in the title via `(#N)` rather
    # than via Fixes: in the body. The hook should still treat them as
    # bugfix PRs and check for a regression test.
    pr = {
        "body": (
            "Restores the seed JSON on inject failure.\n\n"
            "Regression test: tests/test_backfill_seed_restore.py\n"
        ),
        "files": [
            {"path": "scripts/quality/pipeline.py"},
            {"path": "tests/test_backfill_seed_restore.py"},
        ],
        "headRefOid": "abc123",
        "title": "fix(pipeline): restore seed on inject failure (#1212)",
        "number": 9105,
    }
    result = run_hook(
        "gh pr merge 9105 --squash",
        pr_json=pr,
        fixture_files={
            "tests/test_backfill_seed_restore.py": TEST_FILE_WITH_ISSUE,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_fix_title_no_issue_anywhere_accepts_test_if_in_pr(tmp_path: Path) -> None:
    # Edge case: title is `fix:` but no issue number is referenced anywhere.
    # The hook accepts the test as long as it's in the PR — we can't enforce
    # an issue ref that doesn't exist.
    pr = {
        "body": (
            "Fixes a small typo bug in the logger.\n\n"
            "Regression test: tests/test_logger_typo.py\n"
        ),
        "files": [
            {"path": "scripts/logger.py"},
            {"path": "tests/test_logger_typo.py"},
        ],
        "headRefOid": "abc123",
        "title": "fix(logger): correct log level constant",
        "number": 9106,
    }
    result = run_hook(
        "gh pr merge 9106 --squash",
        pr_json=pr,
        fixture_files={
            "tests/test_logger_typo.py": "def test_logger():\n    assert True\n",
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_fix_pr_with_test_in_files_but_unreadable_is_denied(tmp_path: Path) -> None:
    # File is listed in PR files but absent from the fixture dir — exercises
    # the `_fetch_file` returns None path (e.g. moved/inaccessible at PR head).
    pr = {
        "body": (
            "Fixes #1212.\n\n"
            "Regression test: tests/test_backfill_seed_restore.py\n"
        ),
        "files": [
            {"path": "scripts/quality/pipeline.py"},
            {"path": "tests/test_backfill_seed_restore.py"},
        ],
        "headRefOid": "abc123",
        "title": "fix(pipeline): restore seed on inject failure",
        "number": 9107,
    }
    result = run_hook(
        "gh pr merge 9107 --squash",
        pr_json=pr,
        fixture_files={
            # Test file omitted on purpose; only the source file is provided.
            "scripts/quality/pipeline.py": "pass\n",
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "Could not read regression test file" in result.stderr


def test_non_fix_title_with_fixes_keyword_in_body_is_allowed(tmp_path: Path) -> None:
    # Issue #1387: the body-keyword path used to trigger the hook on any PR
    # containing "Fixes #N" / "Closes #N", which blocked feat:/chore:/docs:
    # PRs that close feature-request issues. The trigger is now narrowed to
    # `fix:` title prefix only; body keywords no longer trigger.
    pr = {
        "body": (
            "Fixes issue #1212 — restores the seed JSON on inject failure.\n"
        ),
        "files": [{"path": "scripts/quality/pipeline.py"}],
        "headRefOid": "abc123",
        "title": "chore: restore seed on inject failure",
        "number": 9108,
    }
    result = run_hook(
        "gh pr merge 9108 --squash",
        pr_json=pr,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_feat_pr_with_paren_issue_ref_in_title_is_allowed(tmp_path: Path) -> None:
    # Issue #1387 regression: a `feat:` PR that closes a feature-request
    # issue via the squash-merge `(#N)` convention used to trigger the
    # bugfix-hook because the title-`(#N)` regex populated `issue_refs`
    # which alone activated the gate. Now only `fix:` titles trigger.
    pr = {
        "body": "Adds Module 1.6 GPU Memory Hierarchy and Bandwidth Math.\n",
        "files": [
            {"path": "src/content/docs/platform/llm-inference/module-1.6-gpu-memory.md"},
        ],
        "headRefOid": "abc123",
        "title": "feat: Module 1.6 GPU Memory Hierarchy and Bandwidth Math (#1377)",
        "number": 9111,
    }
    result = run_hook(
        "gh pr merge 9111 --squash",
        pr_json=pr,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_feat_pr_with_closes_in_body_is_allowed(tmp_path: Path) -> None:
    # Issue #1387 regression: `feat:` PR closing a feature-request issue
    # with `Closes #N` in body used to trigger the gate. Now allowed.
    pr = {
        "body": "Adds a new helper.\n\nCloses #1377.\n",
        "files": [{"path": "scripts/helper.py"}],
        "headRefOid": "abc123",
        "title": "feat: add helper",
        "number": 9112,
    }
    result = run_hook(
        "gh pr merge 9112 --squash",
        pr_json=pr,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_git_show_fallback_exercises_subprocess_when_no_fixture(tmp_path: Path) -> None:
    # Without KUBEDOJO_HOOK_FILE_FIXTURE_DIR, `_fetch_file` falls back to
    # `git show <oid>:<path>`. Build a real git repo, commit the test file,
    # and verify the hook reads it through that path. This is the only
    # test that exercises the production read path.
    subprocess.run(
        ["git", "init", "-b", "main", str(tmp_path)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "agent@example.test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Agent"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_real.py").write_text(TEST_FILE_WITH_ISSUE)
    subprocess.run(
        ["git", "add", "tests/test_real.py"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    head_oid = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()

    pr_json_path = tmp_path / "pr.json"
    pr_json_path.write_text(json.dumps({
        "body": "Fixes #1212.\n\nRegression test: tests/test_real.py\n",
        "files": [{"path": "tests/test_real.py"}],
        "headRefOid": head_oid,
        "title": "fix: real bug",
        "number": 9109,
    }))
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    env["KUBEDOJO_HOOK_GH_JSON"] = str(pr_json_path)
    env.pop("KUBEDOJO_HOOK_FILE_FIXTURE_DIR", None)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr merge 9109 --squash", "cwd": str(tmp_path)},
    }
    result = subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True, capture_output=True, check=False,
        env=env, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_command_starting_with_dash_e_not_swallowed_by_echo(tmp_path: Path) -> None:
    # On bash 3.2 (/bin/bash on macOS), `echo` consumes leading -n/-e flags.
    # The hook uses `printf '%s\n'` to defend against this. Verify by passing
    # a command string that starts with `-e` and confirm the hook still
    # detects `gh pr merge`.
    pr = {
        "body": "Fixes #1212.\n\nRegression test: tests/t.py\n",
        "files": [
            {"path": "scripts/quality/pipeline.py"},
            {"path": "tests/t.py"},
        ],
        "headRefOid": "abc123",
        "title": "fix: thing",
        "number": 9110,
    }
    result = run_hook(
        '-e ; gh pr merge 9110 --squash',
        pr_json=pr,
        fixture_files={"tests/t.py": TEST_FILE_WITH_ISSUE},
        tmp_path=tmp_path,
    )
    # printf-based detection should match `gh pr merge` regardless of
    # leading dash-flag-looking tokens; with valid test the hook allows.
    assert result.returncode == 0, result.stderr


def test_explicit_pr_ref_is_passed_to_gh_view(tmp_path: Path) -> None:
    """Regression test for a latent bug in the PR_REF parser. The previous
    parser stopped immediately on matching `gh` and printed the next
    non-flag token — which was always the literal `pr` token. As a
    result `gh pr view pr` 404'd and the hook silently failed open for
    every explicit-PR-ref merge. The fixed parser skips past the
    `gh pr merge` triple and prints the first non-flag token after it.

    Behavioural test: a fake `gh` shim records its argv. The assertion
    is that the recorded argv contains the correct PR number, not `pr`.
    """
    primary = tmp_path / "primary"
    primary.mkdir()

    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    argv_log = tmp_path / "gh_argv.log"
    shim = shim_dir / "gh"
    shim.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\0" "$@" >> "{argv_log}"\n'
        'printf "\\n" >> "' + str(argv_log) + '"\n'
        "exit 1\n"
    )
    shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env.get('PATH', '')}"
    env["CLAUDE_PROJECT_DIR"] = str(primary)
    env.pop("KUBEDOJO_HOOK_GH_JSON", None)

    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "gh pr merge 1234 --squash",
            "cwd": str(primary),
        },
    }
    result = subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=primary,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_log.read_bytes().split(b"\x00")
    # Expect `gh pr view 1234 --json body,files,headRefOid,title,number`.
    # The buggy parser returned `pr` as PR_REF → argv[2] would be `b"pr"`.
    # The fixed parser returns `1234` → argv[2] is `b"1234"`.
    assert argv[:3] == [b"pr", b"view", b"1234"], (
        f"Old PR_REF parser bug regression: expected gh argv[:3] == "
        f"[b'pr', b'view', b'1234'], got argv={argv!r}"
    )


def test_no_pr_ref_resolves_cwd_via_cd_segments(tmp_path: Path) -> None:
    """When `gh pr merge` is invoked without an explicit PR number, gh
    auto-detects the PR from the current branch — so the hook must run
    `gh pr view` from the EFFECTIVE cwd resolved by walking `cd X`
    segments in the command, not the harness-reported cwd. Otherwise a
    `cd .worktrees/X && gh pr merge --squash` invocation from a worktree
    silently bypasses this bugfix-regression gate. Same bug class as #1321
    (false-negative-allow direction).

    Behavioural test: a fake `gh` shim records the cwd it was called from.
    The assertion is that the recorded cwd is the worktree, not the
    primary tree (harness cwd).
    """
    primary = tmp_path / "primary"
    worktree = primary / ".worktrees" / "feat-x"
    worktree.mkdir(parents=True)

    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    cwd_log = tmp_path / "gh_cwd.log"
    shim = shim_dir / "gh"
    shim.write_text(
        "#!/bin/bash\n"
        f'pwd -P >> "{cwd_log}"\n'
        "exit 1\n"
    )
    shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env.get('PATH', '')}"
    env["CLAUDE_PROJECT_DIR"] = str(primary)
    env.pop("KUBEDOJO_HOOK_GH_JSON", None)
    env.pop("KUBEDOJO_HOOK_FILE_FIXTURE_DIR", None)

    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "cd .worktrees/feat-x && gh pr merge --squash",
            "cwd": str(primary),
        },
    }
    result = subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=primary,
    )

    assert result.returncode == 0, result.stderr
    recorded = cwd_log.read_text().strip()
    assert recorded == str(worktree.resolve()), (
        f"Expected gh invoked from worktree {worktree.resolve()}, got {recorded!r}"
    )


def test_gh_failure_fails_open(tmp_path: Path) -> None:
    pr_json_path = tmp_path / "pr.json"
    pr_json_path.write_text("not valid json {{{")
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    env["KUBEDOJO_HOOK_GH_JSON"] = str(pr_json_path)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr merge 1 --squash", "cwd": str(tmp_path)},
    }
    result = subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
