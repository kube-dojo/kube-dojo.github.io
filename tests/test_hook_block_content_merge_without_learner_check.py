"""Tests for `.claude/kubedojo-hooks/block-content-merge-without-learner-check.sh`.

The hook fires on `gh pr merge` Bash commands. For content PRs (any file
under ``src/content/docs/**``), it requires the PR body to contain a
``## Learner check`` section with a markdown blockquote of >= 30 chars
whose text appears verbatim in at least one touched module file.

These tests bypass the live `gh` CLI via two env overrides:

- ``KUBEDOJO_HOOK_GH_JSON`` — path to a JSON file used in place of
  ``gh pr view --json …`` output.
- ``KUBEDOJO_HOOK_FILE_FIXTURE_DIR`` — directory holding the touched
  files' contents at the same relative paths, used in place of
  ``git show <oid>:<path>``.
"""
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "kubedojo-hooks" / "block-content-merge-without-learner-check.sh"
BASH = "/bin/bash"


def run_hook(
    command: str,
    *,
    pr_json: dict | None,
    fixture_files: dict[str, str] | None,
    tmp_path: Path,
    base_fixture_files: dict[str, str] | None = None,
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
    if base_fixture_files is not None:
        base_dir = tmp_path / "base_fixtures"
        for rel, contents in base_fixture_files.items():
            target = base_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        env["KUBEDOJO_HOOK_BASE_FIXTURE_DIR"] = str(base_dir)
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


MODULE_BODY = (
    "---\ntitle: Intro to Pods\n---\n\n"
    "A Pod is the smallest deployable compute unit in Kubernetes. "
    "Pods host one or more tightly coupled containers that share network "
    "and storage. Most workloads run inside a single-container Pod managed "
    "by a Deployment.\n\n"
    "## Why beginners stumble\n\n"
    "The biggest source of confusion is that a Pod is not a container — "
    "the container runs inside the Pod, and Kubernetes never schedules a "
    "container directly.\n"
)


def test_non_bash_tool_is_ignored(tmp_path: Path) -> None:
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "/etc/hosts"},
    }
    result = subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_command_without_pr_merge_is_ignored(tmp_path: Path) -> None:
    result = run_hook(
        "git status",
        pr_json=None,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0


def test_non_content_pr_is_allowed(tmp_path: Path) -> None:
    pr = {
        "body": "Refactors the auth helper.",
        "files": [{"path": "scripts/auth.py"}],
        "headRefOid": "abc123",
        "title": "feat: extract auth helper",
        "number": 9001,
    }
    result = run_hook(
        "gh pr merge 9001 --squash",
        pr_json=pr,
        fixture_files=None,
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_content_pr_without_learner_check_is_denied(tmp_path: Path) -> None:
    pr = {
        "body": "## Summary\n\nRewrites the Pod intro.\n",
        "files": [{"path": "src/content/docs/k8s/cka/module-intro-pods.md"}],
        "headRefOid": "abc123",
        "title": "content: rewrite pod intro",
        "number": 9002,
    }
    result = run_hook(
        "gh pr merge 9002 --squash",
        pr_json=pr,
        fixture_files={
            "src/content/docs/k8s/cka/module-intro-pods.md": MODULE_BODY,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_learner_check_too_short_is_denied(tmp_path: Path) -> None:
    pr = {
        "body": (
            "## Summary\n\nRewrites the Pod intro.\n\n"
            "## Learner check\n\n"
            "> too short\n\n"
            "Beginners get this.\n"
        ),
        "files": [{"path": "src/content/docs/k8s/cka/module-intro-pods.md"}],
        "headRefOid": "abc123",
        "title": "content: rewrite pod intro",
        "number": 9003,
    }
    result = run_hook(
        "gh pr merge 9003 --squash",
        pr_json=pr,
        fixture_files={
            "src/content/docs/k8s/cka/module-intro-pods.md": MODULE_BODY,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert ">= 30 chars" in result.stderr


def test_learner_check_quote_not_in_file_is_denied(tmp_path: Path) -> None:
    fake_quote = "Pods are wrappers around the kubelet daemon's runtime API."
    pr = {
        "body": (
            "## Summary\n\nRewrites the Pod intro.\n\n"
            "## Learner check\n\n"
            f"> {fake_quote}\n\n"
            "Beginners think this is wrong.\n"
        ),
        "files": [{"path": "src/content/docs/k8s/cka/module-intro-pods.md"}],
        "headRefOid": "abc123",
        "title": "content: rewrite pod intro",
        "number": 9004,
    }
    result = run_hook(
        "gh pr merge 9004 --squash",
        pr_json=pr,
        fixture_files={
            "src/content/docs/k8s/cka/module-intro-pods.md": MODULE_BODY,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "No quote in '## Learner check' was found verbatim" in result.stderr


def test_learner_check_quote_in_file_is_allowed(tmp_path: Path) -> None:
    real_quote = (
        "A Pod is the smallest deployable compute unit in Kubernetes."
    )
    pr = {
        "body": (
            "## Summary\n\nRewrites the Pod intro.\n\n"
            "## Learner check\n\n"
            f"> {real_quote}\n\n"
            "A first-time reader needs to know this line frames the "
            "rest of the module.\n"
        ),
        "files": [{"path": "src/content/docs/k8s/cka/module-intro-pods.md"}],
        "headRefOid": "abc123",
        "title": "content: rewrite pod intro",
        "number": 9005,
    }
    result = run_hook(
        "gh pr merge 9005 --squash",
        pr_json=pr,
        fixture_files={
            "src/content/docs/k8s/cka/module-intro-pods.md": MODULE_BODY,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_learner_check_quote_in_one_of_many_files_is_allowed(tmp_path: Path) -> None:
    real_quote = (
        "The biggest source of confusion is that a Pod is not a container"
    )
    pr = {
        "body": (
            "## Learner check\n\n"
            f"> {real_quote}\n"
        ),
        "files": [
            {"path": "src/content/docs/k8s/cka/module-intro-pods.md"},
            {"path": "src/content/docs/k8s/cka/module-pod-lifecycle.md"},
        ],
        "headRefOid": "abc123",
        "title": "content: rewrite pod intro + lifecycle",
        "number": 9006,
    }
    result = run_hook(
        "gh pr merge 9006 --squash",
        pr_json=pr,
        fixture_files={
            "src/content/docs/k8s/cka/module-intro-pods.md": MODULE_BODY,
            "src/content/docs/k8s/cka/module-pod-lifecycle.md": "lifecycle module body\n",
        },
        tmp_path=tmp_path,
    )
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
    silently bypasses this content-quality gate. Same bug class as #1321
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


# --- metadata-only awareness (#2237 gate-collision follow-up) -----------------

_META_BASE = (
    "---\ntitle: Модуль 8.2\nslug: uk/cloud/x\nsidebar:\n  order: 3\n---\n\n"
    "Тіло документа, яке не змінюється у цьому PR. Достатньо довгий рядок.\n"
)
# same body, one ASCII `en_commit` provenance line added to frontmatter
_META_HEAD = _META_BASE.replace(
    "  order: 3\n---",
    "  order: 3\nen_commit: a4a4935b266ce46eefb0682ff97beb7279f2f869\n---",
)


def test_metadata_only_content_change_is_allowed(tmp_path: Path) -> None:
    """An en_commit-style frontmatter-only touch changes no teaching prose, so
    no Learner check section is required."""
    pr = {
        "body": "## Summary\n\nBackfill en_commit provenance.\n",
        "files": [{"path": "src/content/docs/uk/cloud/x.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "chore(uk): backfill provenance",
        "number": 9101,
    }
    result = run_hook(
        "gh pr merge 9101 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/uk/cloud/x.md": _META_HEAD},
        base_fixture_files={"src/content/docs/uk/cloud/x.md": _META_BASE},
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_cyrillic_frontmatter_edit_still_requires_check(tmp_path: Path) -> None:
    """Editing translated frontmatter prose (title) adds Cyrillic → NOT
    metadata-only → the Learner check is still required."""
    base = "---\ntitle: Модуль 8.2\n---\n\nТіло.\n"
    head = "---\ntitle: Модуль 8.2 та мережі\n---\n\nТіло.\n"
    pr = {
        "body": "## Summary\n\nRetitle.\n",
        "files": [{"path": "src/content/docs/uk/cloud/x.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs(uk): retitle",
        "number": 9102,
    }
    result = run_hook(
        "gh pr merge 9102 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/uk/cloud/x.md": head},
        base_fixture_files={"src/content/docs/uk/cloud/x.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_mixed_metadata_and_real_content_requires_check(tmp_path: Path) -> None:
    """One metadata-only file + one real body change → still gated."""
    real_base = "---\ntitle: A\n---\n\nOld body prose line long enough here.\n"
    real_head = "---\ntitle: A\n---\n\nNEW body prose line long enough here now.\n"
    pr = {
        "body": "## Summary\n\nMixed change.\n",
        "files": [
            {"path": "src/content/docs/uk/cloud/x.md"},
            {"path": "src/content/docs/uk/cloud/y.md"},
        ],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs(uk): mixed",
        "number": 9103,
    }
    result = run_hook(
        "gh pr merge 9103 --rebase",
        pr_json=pr,
        fixture_files={
            "src/content/docs/uk/cloud/x.md": _META_HEAD,
            "src/content/docs/uk/cloud/y.md": real_head,
        },
        base_fixture_files={
            "src/content/docs/uk/cloud/x.md": _META_BASE,
            "src/content/docs/uk/cloud/y.md": real_base,
        },
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_new_content_file_still_requires_check(tmp_path: Path) -> None:
    """A NEW content file has no base blob → treated as real content → gated."""
    pr = {
        "body": "## Summary\n\nNew module.\n",
        "files": [{"path": "src/content/docs/uk/cloud/new.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs(uk): new module",
        "number": 9104,
    }
    result = run_hook(
        "gh pr merge 9104 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/uk/cloud/new.md": _META_HEAD},
        base_fixture_files={},  # base dir exists but file absent → new file
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_ascii_description_edit_still_requires_check(tmp_path: Path) -> None:
    """An EN module's `description:` (learner-facing: nav/search prose) edited
    with body unchanged is NOT structural metadata → gate stays. (codex R1.)"""
    base = "---\ntitle: Pods\ndescription: Intro to Pods\n---\n\nBody stays.\n"
    head = "---\ntitle: Pods\ndescription: A gentle intro to Pods\n---\n\nBody stays.\n"
    pr = {
        "body": "## Summary\n\nTweak the description.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs: reword pod description",
        "number": 9105,
    }
    result = run_hook(
        "gh pr merge 9105 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_frontmatter_prose_deletion_requires_check(tmp_path: Path) -> None:
    """Deleting a learner-facing frontmatter line (`description:`) is caught by
    the symmetric diff → gate stays. (codex R1.)"""
    base = "---\ntitle: Pods\ndescription: Intro to Pods\n---\n\nBody stays.\n"
    head = "---\ntitle: Pods\n---\n\nBody stays.\n"
    pr = {
        "body": "## Summary\n\nDrop the description.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs: drop description",
        "number": 9106,
    }
    result = run_hook(
        "gh pr merge 9106 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_structural_slug_order_change_still_requires_check(tmp_path: Path) -> None:
    """The metadata-only allowlist is deliberately minimal (`en_commit` only):
    a slug / sidebar.order change is NOT skipped and keeps the learner check.
    (Scope narrowed after the codex R4 reparenting finding.)"""
    base = "---\ntitle: Pods\nslug: k8s/pods\nsidebar:\n  order: 3\n---\n\nBody.\n"
    head = "---\ntitle: Pods\nslug: k8s/cka/pods\nsidebar:\n  order: 5\n---\n\nBody.\n"
    pr = {
        "body": "## Summary\n\nFix slug + order.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "chore: fix slug + sidebar order",
        "number": 9107,
    }
    result = run_hook(
        "gh pr merge 9107 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_reparented_frontmatter_label_requires_check(tmp_path: Path) -> None:
    """Swapping `sidebar.label` and `prev.label` between sections leaves the
    line SET identical but changes the visible sidebar label. The order-
    sensitive remainder comparison catches the reparent → gate stays. (codex R4.)"""
    base = (
        "---\ntitle: Page\nsidebar:\n  label: Old sidebar label\n"
        "prev:\n  label: Previous page label\n---\n\nBody stays.\n"
    )
    head = (
        "---\ntitle: Page\nprev:\n  label: Old sidebar label\n"
        "sidebar:\n  label: Previous page label\n---\n\nBody stays.\n"
    )
    pr = {
        "body": "## Summary\n\nReparent the labels.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs: reparent labels",
        "number": 9110,
    }
    result = run_hook(
        "gh pr merge 9110 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_flow_style_sidebar_label_requires_check(tmp_path: Path) -> None:
    """Flow-style YAML `sidebar: { label: … }` inlines prose on the allowlisted
    `sidebar` line — the `{`/`[` guard must keep the gate. (codex R2.)"""
    base = "---\nsidebar: { label: Old visible label, order: 1 }\n---\n\nBody stays.\n"
    head = "---\nsidebar: { label: New visible label, order: 1 }\n---\n\nBody stays.\n"
    pr = {
        "body": "## Summary\n\nReword the nav label.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs: reword nav label",
        "number": 9108,
    }
    result = run_hook(
        "gh pr merge 9108 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_yaml_alias_sidebar_requires_check(tmp_path: Path) -> None:
    """A YAML alias on the allowlisted `sidebar` line (`sidebar: *new`) resolves
    to a changed nested label. The plain-scalar value allowlist rejects the
    `*`-prefixed value → gate stays. (codex R3.)"""
    base = (
        "---\ntitle: Pods\nnav_a: &a { label: Old, order: 1 }\n"
        "nav_b: &b { label: New, order: 1 }\nsidebar: *a\n---\n\nBody stays.\n"
    )
    head = base.replace("sidebar: *a", "sidebar: *b")
    pr = {
        "body": "## Summary\n\nRepoint the sidebar alias.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs: repoint sidebar alias",
        "number": 9109,
    }
    result = run_hook(
        "gh pr merge 9109 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_en_commit_inside_block_scalar_requires_check(tmp_path: Path) -> None:
    """An INDENTED `en_commit:` is the block-scalar CONTENT of a prose field
    (`description: |`), not a top-level key — it must NOT be stripped, so a
    change to that description keeps the gate. (codex R5.)"""
    base = (
        "---\ntitle: Pods\ndescription: |\n"
        "  en_commit: Old visible description for learners\n---\n\nBody stays.\n"
    )
    head = (
        "---\ntitle: Pods\ndescription: |\n"
        "  en_commit: New visible description for learners\n---\n\nBody stays.\n"
    )
    pr = {
        "body": "## Summary\n\nReword the description.\n",
        "files": [{"path": "src/content/docs/k8s/cka/pods.md"}],
        "headRefOid": "head1",
        "baseRefName": "main",
        "title": "docs: reword description",
        "number": 9111,
    }
    result = run_hook(
        "gh pr merge 9111 --rebase",
        pr_json=pr,
        fixture_files={"src/content/docs/k8s/cka/pods.md": head},
        base_fixture_files={"src/content/docs/k8s/cka/pods.md": base},
        tmp_path=tmp_path,
    )
    assert result.returncode == 2
    assert "missing a '## Learner check' section" in result.stderr


def test_gh_failure_fails_open(tmp_path: Path) -> None:
    # When `gh pr view` itself fails (auth, network, no PR on branch), the
    # hook must fail open — a quality gate should not trap the orchestrator
    # behind transient infra. We simulate the failure by passing a stub PR
    # JSON file that doesn't parse, which the hook treats as "couldn't
    # resolve PR" → PASS.
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
