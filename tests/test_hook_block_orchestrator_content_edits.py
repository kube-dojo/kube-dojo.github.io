import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "kubedojo-hooks" / "block-orchestrator-content-edits.sh"
BASH = "/bin/bash"


def run_hook_payload(
    payload: dict[str, object],
    primary: Path,
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("LEARN_UKRAINIAN_DISPATCH_TASK_ID", None)
    env["CLAUDE_PROJECT_DIR"] = str(primary)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=primary,
    )


def run_edit_hook(
    tool_name: str,
    file_path: str,
    primary: Path,
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_hook_payload(
        {
            "tool_name": tool_name,
            "tool_input": {
                "file_path": file_path,
            },
        },
        primary,
        env_overrides=env_overrides,
    )


def test_edit_src_content_docs_denied_when_undispatched(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook("Edit", "src/content/docs/foo.md", primary)

    assert result.returncode == 2
    assert "blocked" in result.stderr
    assert "lu_machinery.dispatch" in result.stderr
    assert "dispatch_smart.py" not in result.stderr


def test_edit_src_content_docs_denied_when_dispatch_task_id_blank(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    for blank in ("", "   \t "):
        result = run_edit_hook(
            "Edit",
            "src/content/docs/foo.md",
            primary,
            env_overrides={"LEARN_UKRAINIAN_DISPATCH_TASK_ID": blank},
        )
        assert result.returncode == 2
        assert "blocked" in result.stderr


def test_edit_src_content_docs_allowed_when_dispatched(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook(
        "Edit",
        "src/content/docs/foo.md",
        primary,
        env_overrides={"LEARN_UKRAINIAN_DISPATCH_TASK_ID": "kd-content-task-1"},
    )

    assert result.returncode == 0


def test_write_src_content_docs_denied_when_undispatched(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook("Write", "src/content/docs/foo.md", primary)

    assert result.returncode == 2
    assert "blocked" in result.stderr


def test_write_src_content_docs_allowed_when_dispatched(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook(
        "Write",
        "src/content/docs/foo.md",
        primary,
        env_overrides={"LEARN_UKRAINIAN_DISPATCH_TASK_ID": "kd-content-task-2"},
    )

    assert result.returncode == 0


def test_edit_outside_src_content_docs_allowed(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook("Edit", "docs/research/foo.html", primary)
    result_with_env = run_edit_hook(
        "Edit",
        "docs/research/foo.html",
        primary,
        env_overrides={"LEARN_UKRAINIAN_DISPATCH_TASK_ID": "kd-content-task-3"},
    )

    assert result.returncode == 0
    assert result_with_env.returncode == 0


def test_edit_status_md_allowed(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook("Edit", "STATUS.md", primary)

    assert result.returncode == 0


def test_bash_tool_call_ignored(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook("Bash", "src/content/docs/foo.md", primary)

    assert result.returncode == 0


def test_edit_with_absolute_path_to_src_content_docs_denied(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_edit_hook("Edit", str(REPO_ROOT / "src/content/docs/foo.md"), primary)

    assert result.returncode == 2
    assert "blocked" in result.stderr


def test_edit_malformed_payload_fails_open(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    env = os.environ.copy()
    env.pop("LEARN_UKRAINIAN_DISPATCH_TASK_ID", None)
    env["CLAUDE_PROJECT_DIR"] = str(primary)
    result = subprocess.run(
        [BASH, str(HOOK)],
        input="this is not JSON",
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=primary,
    )

    assert result.returncode == 0
