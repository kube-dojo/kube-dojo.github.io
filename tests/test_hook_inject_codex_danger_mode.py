import json
import os
import shlex
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "kubedojo-hooks" / "inject-codex-danger-mode.sh"
BASH = "/bin/bash"


def run_hook_payload(
    payload: dict[str, object],
    primary: Path,
    *,
    env_overrides: dict[str, str] | None = None,
    executable: str = "/bin/bash",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(primary)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=primary,
    )


def run_hook(command: str, primary: Path) -> subprocess.CompletedProcess[str]:
    return run_hook_payload({"tool_name": "Bash", "tool_input": {"command": command}}, primary)


def assert_injected_mode(result: subprocess.CompletedProcess[str], expected_prompt: str) -> None:
    assert result.returncode == 0
    assert result.stdout != ""
    payload = json.loads(result.stdout)
    updated = payload["hookSpecificOutput"]["updatedInput"]["command"]
    tokens = shlex.split(updated)
    assert tokens[:4] == ["codex", "exec", "--mode", "danger"]
    assert " ".join(tokens[4:]) == expected_prompt


def test_codex_exec_with_git_push_in_prompt_no_mode_injects_danger(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    prompt = "do work then git push origin main"
    result = run_hook(f'codex exec "{prompt}"', primary)

    assert result.returncode == 0
    assert_injected_mode(result, prompt)


def test_codex_exec_with_gh_pr_create_in_prompt_no_mode_injects_danger(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    prompt = "draft fix, then gh pr create --title 'x'"
    result = run_hook(f'codex exec "{prompt}"', primary)

    assert result.returncode == 0
    assert_injected_mode(result, prompt)


def test_codex_exec_with_workspace_write_mode_and_git_push_in_prompt_upgrades_to_danger(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    command = 'codex exec --mode workspace-write "git push origin main"'
    result = run_hook(command, primary)
    assert result.returncode == 0
    assert result.stdout != ""
    payload = json.loads(result.stdout)
    updated = payload["hookSpecificOutput"]["updatedInput"]["command"]
    tokens = shlex.split(updated)
    assert tokens[:4] == ["codex", "exec", "--mode", "danger"]
    assert " ".join(tokens[4:]) == "git push origin main"


def test_codex_exec_with_danger_mode_already_set_no_change(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    result = run_hook('codex exec --mode danger "git push origin main"', primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_codex_exec_without_git_or_gh_in_prompt_no_inject(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    command = "codex exec \"analyze the codebase\""
    result = run_hook(command, primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_codex_exec_via_stdin_dash_fail_open_no_inject(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    result = run_hook("cat /tmp/brief.md | codex exec -", primary)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "FAIL_OPEN\tprompt source not statically visible" in result.stderr


def test_codex_exec_via_file_substitution_fail_open(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    result = run_hook("codex exec - < /tmp/brief.md", primary)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "FAIL_OPEN\tprompt source not statically visible" in result.stderr


def test_non_codex_bash_command_ignored(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    result = run_hook("python scripts/test_pipeline.py git push", primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_codex_via_python_dispatch_wrapper_ignored(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    result = run_hook('python scripts/dispatch_smart.py edit --agent codex --mode danger "..."', primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_json_payload_fails_open(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    env = os.environ.copy()
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
    assert result.stdout == ""
