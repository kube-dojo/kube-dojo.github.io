"""Regression tests: codex always runs in danger mode.

read-only starved Codex of network/filesystem and caused rc=-9 stale-rollout
salvage — three failures in a single session 2026-05-07. These tests ensure
the guard cannot be silently undone.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
WORKTREE_ROOT = Path(__file__).resolve().parent.parent
# .venv lives at the primary repo root, not the worktree root — use git common-dir.
_git_common_dir = subprocess.check_output(
    ["git", "-C", str(WORKTREE_ROOT), "rev-parse", "--git-common-dir"],
    text=True,
).strip()
REPO_ROOT = Path(_git_common_dir).parent.resolve()
VENV_PYTHON = str(REPO_ROOT / ".venv/bin/python")


def test_codex_adapter_rejects_read_only_mode():
    """runner.invoke('codex', ..., mode='read-only') must raise ValueError.

    CodexAdapter.supported_modes no longer includes 'read-only'. The runner
    validates mode pre-spawn (step 2 of the invoke flow), so no subprocess
    is ever launched.
    """
    from agent_runtime.runner import invoke

    with pytest.raises(ValueError, match="does not support mode"):
        invoke(
            "codex",
            "x",
            mode="read-only",
            cwd=None,
            model=None,
            task_id=None,
        )


def test_dispatch_smart_codex_forces_danger_mode():
    """dispatch_smart.py review --agent codex --dry-run always resolves mode=danger.

    Regardless of the 'review' task class default (read-only), codex
    dispatches must be overridden to danger before any validation runs.
    """
    result = subprocess.run(
        [
            VENV_PYTHON,
            str(SCRIPTS_DIR / "dispatch_smart.py"),
            "review",
            "--agent", "codex",
            "--dry-run",
            "-",
        ],
        input="x",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"dispatch_smart.py exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "mode=danger" in result.stdout, (
        f"Expected 'mode=danger' in stdout but got:\n{result.stdout}"
    )


def _load_dispatch() -> object:
    import importlib.util
    spec = importlib.util.spec_from_file_location("dispatch", SCRIPTS_DIR / "dispatch.py")
    dispatch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dispatch)  # type: ignore[union-attr]
    return dispatch


def _load_dispatch_smart() -> object:
    import importlib
    import sys

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return importlib.import_module("dispatch_smart")


def _load_codex_adapter():
    import importlib
    import sys

    # Import via package path so codex.py's sibling-relative imports resolve.
    sys.path.insert(0, str(REPO_ROOT))
    mod = importlib.import_module("agent_runtime.adapters.codex")
    return mod


def _capture_cmd(dispatch_fn, *args, **kwargs) -> list[str]:
    """Call dispatch_fn, intercept _run_with_process_group, return captured cmd."""
    dispatch = _load_dispatch()

    captured_cmd: list[str] = []

    def fake_run(cmd, *_args, **_kwargs):
        captured_cmd.extend(cmd)
        raise FileNotFoundError("no codex cli in test")

    dispatch._run_with_process_group = fake_run  # type: ignore[attr-defined]
    fn = getattr(dispatch, dispatch_fn)
    fn(*args, **kwargs)
    return captured_cmd


def _codex_invocation_cmd(
    search_env: str | None,
    session_id: str | None = None,
) -> list[str]:
    return _codex_invocation_plan(search_env=search_env, session_id=session_id).cmd


def _codex_invocation_plan(
    search_env: str | None,
    session_id: str | None = None,
    prompt: str = "x",
):
    import os

    adapter_module = _load_codex_adapter()
    adapter = adapter_module.CodexAdapter()

    old = os.environ.get("KUBEDOJO_CODEX_SEARCH")
    old_effort = os.environ.get("KUBEDOJO_CODEX_EFFORT")
    try:
        if search_env is None:
            os.environ.pop("KUBEDOJO_CODEX_SEARCH", None)
        else:
            os.environ["KUBEDOJO_CODEX_SEARCH"] = search_env
        os.environ.pop("KUBEDOJO_CODEX_EFFORT", None)
        return adapter.build_invocation(
            prompt=prompt,
            mode="danger",
            cwd=REPO_ROOT,
            model=None,
            task_id=None,
            session_id=session_id,
            tool_config=None,
        )
    finally:
        if old is None:
            os.environ.pop("KUBEDOJO_CODEX_SEARCH", None)
        else:
            os.environ["KUBEDOJO_CODEX_SEARCH"] = old
        if old_effort is None:
            os.environ.pop("KUBEDOJO_CODEX_EFFORT", None)
        else:
            os.environ["KUBEDOJO_CODEX_EFFORT"] = old_effort


def test_codex_adapter_rejects_workspace_write_mode():
    """runner.invoke('codex', ..., mode='workspace-write') must raise ValueError.

    CodexAdapter.supported_modes now only contains 'danger'. workspace-write
    blocks .git/worktrees index.lock and api.github.com — danger is required.
    """
    from agent_runtime.runner import invoke

    with pytest.raises(ValueError, match="does not support mode"):
        invoke(
            "codex",
            "x",
            mode="workspace-write",
            cwd=None,
            model=None,
            task_id=None,
        )


def test_dispatch_codex_sandbox_env_ignored():
    """KUBEDOJO_CODEX_SANDBOX env var is now ignored; cmd is always danger.

    The env override was removed in this PR — the var no longer affects
    command construction. Verify the flag is still danger even when the
    env var is set to workspace-write.
    """
    import os
    env_backup = os.environ.get("KUBEDOJO_CODEX_SANDBOX")
    try:
        os.environ["KUBEDOJO_CODEX_SANDBOX"] = "workspace-write"
        cmd = _capture_cmd("dispatch_codex", "test prompt")
    finally:
        if env_backup is None:
            os.environ.pop("KUBEDOJO_CODEX_SANDBOX", None)
        else:
            os.environ["KUBEDOJO_CODEX_SANDBOX"] = env_backup

    assert "--dangerously-bypass-approvals-and-sandbox" in cmd, (
        f"Expected danger flag even with KUBEDOJO_CODEX_SANDBOX=workspace-write, got: {cmd}"
    )
    assert "--full-auto" not in cmd, (
        f"--full-auto must not appear when env var is ignored, got: {cmd}"
    )


def test_dispatch_codex_default_is_danger():
    """dispatch_codex() builds a --dangerously-bypass-approvals-and-sandbox command.

    Env var is gone; the flag is unconditional.
    """
    import os
    os.environ.pop("KUBEDOJO_CODEX_SANDBOX", None)
    cmd = _capture_cmd("dispatch_codex", "test prompt")
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd, (
        f"Expected danger flag in cmd but got: {cmd}"
    )
    assert "--sandbox" not in cmd, (
        f"--sandbox should not appear in danger-mode cmd, got: {cmd}"
    )


def test_codex_adapter_respects_search_env_off():
    """CodexAdapter includes --search only when env var is set to 1."""
    assert "--search" not in _codex_invocation_cmd(None), (
        f"Expected --search OFF when KUBEDOJO_CODEX_SEARCH is unset: "
        f"{_codex_invocation_cmd(None)}"
    )
    assert "--search" not in _codex_invocation_cmd("0"), (
        f"Expected --search OFF when KUBEDOJO_CODEX_SEARCH=0: "
        f"{_codex_invocation_cmd('0')}"
    )


def test_codex_adapter_respects_search_env_on():
    """CodexAdapter includes --search when KUBEDOJO_CODEX_SEARCH=1."""
    assert "--search" in _codex_invocation_cmd("1"), (
        f"Expected --search when KUBEDOJO_CODEX_SEARCH=1: {_codex_invocation_cmd('1')}"
    )


def test_codex_adapter_uses_resume_action():
    cmd = _codex_invocation_cmd(None, session_id="stored-codex-session")
    assert cmd[1] == "exec"
    assert cmd[2] == "resume"
    assert cmd[3] == "stored-codex-session"


def test_codex_adapter_resume_includes_output_file():
    cmd = _codex_invocation_cmd(None, session_id="stored-codex-session")
    assert "-o" in cmd
    output_index = cmd.index("-o")
    assert output_index + 1 < len(cmd), (
        f"Expected resume cmd include output path after -o, got: {cmd}"
    )
    assert cmd[output_index + 1], (
        f"Expected non-empty output path after -o, got: {cmd[output_index + 1:]}"
    )


def test_codex_adapter_resume_includes_model_and_mode_flags():
    cmd = _codex_invocation_cmd(None, session_id="stored-codex-session")
    assert "-m" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd


def test_codex_adapter_resume_uses_stdin_for_prompt():
    plan = _codex_invocation_plan(
        None,
        session_id="stored-codex-session",
        prompt="x",
    )
    assert plan.cmd[-1] == "-"
    assert plan.stdin_payload == "x"


def test_codex_adapter_effort_is_config_override_before_exec():
    import os

    adapter_module = _load_codex_adapter()
    adapter = adapter_module.CodexAdapter()
    old = os.environ.get("KUBEDOJO_CODEX_EFFORT")
    try:
        os.environ["KUBEDOJO_CODEX_EFFORT"] = "high"
        plan = adapter.build_invocation(
            prompt="x",
            mode="danger",
            cwd=REPO_ROOT,
            model="gpt-6-luna",
            task_id=None,
            session_id=None,
            tool_config=None,
        )
    finally:
        if old is None:
            os.environ.pop("KUBEDOJO_CODEX_EFFORT", None)
        else:
            os.environ["KUBEDOJO_CODEX_EFFORT"] = old
    cmd = plan.cmd
    assert cmd[1:3] == ["-c", 'model_reasoning_effort="high"']
    assert cmd.index("-c") < cmd.index("exec")
    assert cmd[cmd.index("-m") + 1] == "gpt-6-luna"


def test_codex_adapter_resume_search_flag_order():
    cmd = _codex_invocation_cmd("1", session_id="stored-codex-session")
    assert cmd[1] == "--search"
    assert cmd[2] == "exec"
    assert cmd[3] == "resume"


def test_dispatch_smart_codex_sets_search_for_draft():
    """dispatch_smart sets search ON for draft class dispatches."""
    dispatch_smart = _load_dispatch_smart()

    observed: dict[str, str] = {}

    def fake_invoke(*_args, **_kwargs):
        import os

        observed["search"] = os.environ.get("KUBEDOJO_CODEX_SEARCH", "")
        return SimpleNamespace(
            ok=True,
            response="ok",
            session_id=None,
            stderr_excerpt="",
        )

    with patch("agent_runtime.runner.invoke", side_effect=fake_invoke):
        dispatch_smart.fire(
            agent="codex",
            task_class="draft",
            prompt="x",
            mode="danger",
            model="gpt-5.4-mini",
            worktree=None,
            task_id="t1",
            timeout_s=1,
        )
    assert observed["search"] == "1"


def test_dispatch_smart_codex_clears_search_for_review():
    """dispatch_smart sets search OFF for review class dispatches."""
    dispatch_smart = _load_dispatch_smart()

    observed: dict[str, str] = {}

    def fake_invoke(*_args, **_kwargs):
        import os

        observed["search"] = os.environ.get("KUBEDOJO_CODEX_SEARCH", "")
        return SimpleNamespace(
            ok=True,
            response="ok",
            session_id=None,
            stderr_excerpt="",
        )

    with patch("agent_runtime.runner.invoke", side_effect=fake_invoke):
        dispatch_smart.fire(
            agent="codex",
            task_class="review",
            prompt="x",
            mode="read-only",
            model="gpt-5.5",
            worktree=None,
            task_id="t2",
            timeout_s=1,
        )
    assert observed["search"] == "0"


def test_dispatch_codex_includes_search():
    """dispatch_codex() includes --search and danger mode flags."""
    cmd = _capture_cmd("dispatch_codex", "test prompt")
    assert "--search" in cmd, f"Expected --search in dispatch_codex cmd: {cmd}"
    assert cmd[1] == "--search", f"Expected top-level --search in cmd: {cmd}"
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd, (
        f"Expected danger flag in dispatch_codex cmd: {cmd}"
    )


def test_dispatch_codex_review_no_search():
    """dispatch_codex_review() keeps --search off."""
    cmd = _capture_cmd("dispatch_codex_review", "test prompt")
    assert "--search" not in cmd, f"Expected no --search in review cmd: {cmd}"
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd, (
        f"Expected danger flag in review cmd: {cmd}"
    )


def test_dispatch_codex_patch_includes_search():
    """dispatch_codex_patch() includes --search and danger mode flags."""
    cmd = _capture_cmd("dispatch_codex_patch", "test prompt")
    assert "--search" in cmd, f"Expected --search in patch cmd: {cmd}"
    assert cmd[1] == "--search", f"Expected top-level --search in patch cmd: {cmd}"
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd, (
        f"Expected danger flag in patch cmd: {cmd}"
    )


def test_codex_bridge_runtime_mode_always_danger():
    """_codex_bridge_runtime_mode() returns 'danger' regardless of CODEX_BRIDGE_MODE env."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "ai_agent_bridge._codex",
        SCRIPTS_DIR / "ai_agent_bridge" / "_codex.py",
    )
    # Module imports from agent_runtime — guard against import errors in test env.
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except (ImportError, ModuleNotFoundError):
        pytest.skip("ai_agent_bridge deps not available in this test env")

    for env_val in ("workspace-write", "safe", "full-auto", "danger", None):
        if env_val is None:
            os.environ.pop("CODEX_BRIDGE_MODE", None)
        else:
            os.environ["CODEX_BRIDGE_MODE"] = env_val
        result = mod._codex_bridge_runtime_mode()  # type: ignore[attr-defined]
        assert result == "danger", (
            f"Expected 'danger' for CODEX_BRIDGE_MODE={env_val!r}, got {result!r}"
        )
    os.environ.pop("CODEX_BRIDGE_MODE", None)
