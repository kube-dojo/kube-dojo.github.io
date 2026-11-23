import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "kubedojo-hooks" / "block-agent-worktree-isolation.sh"
BASH = "/bin/bash"


def run_hook_payload(
    payload: dict[str, object],
    primary: Path,
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
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


def test_agent_with_worktree_isolation_denied(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_hook_payload(
        {
            "tool_name": "Agent",
            "tool_input": {
                "isolation": "worktree",
                "description": "x",
                "prompt": "y",
            },
        },
        primary,
    )

    assert result.returncode == 2
    assert "blocked" in result.stderr


def test_agent_without_isolation_allowed(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_hook_payload(
        {
            "tool_name": "Agent",
            "tool_input": {
                "description": "x",
                "prompt": "y",
            },
        },
        primary,
    )

    assert result.returncode == 0


def test_agent_with_empty_isolation_allowed(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_hook_payload(
        {
            "tool_name": "Agent",
            "tool_input": {
                "isolation": "",
                "description": "x",
                "prompt": "y",
            },
        },
        primary,
    )

    assert result.returncode == 0


def test_agent_with_container_isolation_allowed(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_hook_payload(
        {
            "tool_name": "Agent",
            "tool_input": {
                "isolation": "container",
                "description": "x",
                "prompt": "y",
            },
        },
        primary,
    )

    assert result.returncode == 0


def test_non_agent_tool_ignored(tmp_path: Path) -> None:
    primary = tmp_path / "kubedojo"
    primary.mkdir()

    result = run_hook_payload(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": "parallel: use Agent with isolation=worktree",
            },
        },
        primary,
    )

    assert result.returncode == 0


def test_agent_malformed_payload_fails_open(tmp_path: Path) -> None:
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
