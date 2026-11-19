"""Tests for quality hooks: post-write-py-autoformat and pre-read-warn-large-log."""

import json
import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASH = "/bin/bash"
AUTO_FORMAT_HOOK = REPO_ROOT / ".claude" / "hooks" / "post-write-py-autoformat.sh"
LOG_WARN_HOOK = REPO_ROOT / ".claude" / "kubedojo-hooks" / "pre-read-warn-large-log.sh"


def run_hook(
    hook: Path,
    payload: dict,
    primary: Path,
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("KUBEDOJO_DISPATCHED", None)
    env["CLAUDE_PROJECT_DIR"] = str(primary)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [BASH, str(hook)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=str(primary),
    )


def make_ruff_mock(venv_bin: Path, *, check_exits: int = 0) -> None:
    """Install a fake ruff that controls --check exit code."""
    venv_bin.mkdir(parents=True, exist_ok=True)
    ruff = venv_bin / "ruff"
    ruff.write_text(
        f'#!/bin/bash\n'
        f'for arg in "$@"; do [ "$arg" = "--check" ] && exit {check_exits}; done\n'
        f'exit 0\n'
    )
    ruff.chmod(ruff.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def make_py_payload(file_path: str, tool_name: str = "Edit") -> dict:
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "tool_response": {"type": "result", "result": "ok"},
    }


def make_read_payload(file_path: str) -> dict:
    return {
        "tool_name": "Read",
        "tool_input": {"file_path": file_path},
    }


# ── post-write-py-autoformat tests ────────────────────────────────────────


def test_autoformat_triggers_and_emits_context(tmp_path: Path) -> None:
    """Ruff reports file needs formatting → hook formats and emits hookSpecificOutput."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=1)
    py_file = primary / "scripts" / "foo.py"
    py_file.parent.mkdir()
    py_file.write_text("x=1\n")

    result = run_hook(AUTO_FORMAT_HOOK, make_py_payload(str(py_file)), primary)

    assert result.returncode == 0
    assert "hookSpecificOutput" in result.stdout
    assert "ruff auto-formatted" in result.stdout


def test_autoformat_silent_when_already_formatted(tmp_path: Path) -> None:
    """Ruff reports no changes needed → hook exits silently, no stdout."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=0)
    py_file = primary / "scripts" / "foo.py"
    py_file.parent.mkdir()
    py_file.write_text("x = 1\n")

    result = run_hook(AUTO_FORMAT_HOOK, make_py_payload(str(py_file)), primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_autoformat_skips_non_py_file(tmp_path: Path) -> None:
    """Non-.py extension → hook exits 0 immediately without invoking ruff."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=1)

    result = run_hook(
        AUTO_FORMAT_HOOK,
        make_py_payload(str(primary / "docs" / "guide.md")),
        primary,
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_autoformat_skips_when_dispatched(tmp_path: Path) -> None:
    """KUBEDOJO_DISPATCHED=1 → hook skips entirely, no ruff invoked."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=1)
    py_file = primary / "scripts" / "foo.py"
    py_file.parent.mkdir()
    py_file.write_text("x=1\n")

    result = run_hook(
        AUTO_FORMAT_HOOK,
        make_py_payload(str(py_file)),
        primary,
        env_overrides={"KUBEDOJO_DISPATCHED": "1"},
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_autoformat_skips_file_in_worktrees(tmp_path: Path) -> None:
    """File inside .worktrees/ → hook skips (not in primary tree)."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=1)
    wt_file = primary / ".worktrees" / "feature-1" / "scripts" / "foo.py"
    wt_file.parent.mkdir(parents=True)
    wt_file.write_text("x=1\n")

    result = run_hook(AUTO_FORMAT_HOOK, make_py_payload(str(wt_file)), primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_autoformat_skips_when_ruff_not_installed(tmp_path: Path) -> None:
    """No .venv/bin/ruff → hook exits 0 silently (fail-open)."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    # Deliberately no .venv/bin/ruff
    py_file = primary / "scripts" / "foo.py"
    py_file.parent.mkdir()
    py_file.write_text("x=1\n")

    result = run_hook(AUTO_FORMAT_HOOK, make_py_payload(str(py_file)), primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_autoformat_skips_venv_path(tmp_path: Path) -> None:
    """File inside .venv/ → hook skips (excluded directory)."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=1)
    venv_file = primary / ".venv" / "lib" / "python3.11" / "site-packages" / "foo.py"
    venv_file.parent.mkdir(parents=True)
    venv_file.write_text("x=1\n")

    result = run_hook(AUTO_FORMAT_HOOK, make_py_payload(str(venv_file)), primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_autoformat_write_tool_also_triggers(tmp_path: Path) -> None:
    """Write tool (not just Edit) also triggers autoformat."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    make_ruff_mock(primary / ".venv" / "bin", check_exits=1)
    py_file = primary / "scripts" / "new_file.py"
    py_file.parent.mkdir()
    py_file.write_text("x=1\n")

    result = run_hook(AUTO_FORMAT_HOOK, make_py_payload(str(py_file), "Write"), primary)

    assert result.returncode == 0
    assert "ruff auto-formatted" in result.stdout


# ── pre-read-warn-large-log tests ─────────────────────────────────────────


def test_log_filter_warns_on_large_smart_dispatch_jsonl(tmp_path: Path) -> None:
    """Large smart_dispatch.jsonl → hook emits advisory hookSpecificOutput."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    log_file = primary / "logs" / "smart_dispatch.jsonl"
    log_file.parent.mkdir()
    log_file.write_bytes(b"x" * 110_000)  # > 100 KB

    result = run_hook(LOG_WARN_HOOK, make_read_payload(str(log_file)), primary)

    assert result.returncode == 0
    assert "hookSpecificOutput" in result.stdout
    assert "jq" in result.stdout


def test_log_filter_silent_on_small_dispatch_log(tmp_path: Path) -> None:
    """Small smart_dispatch.jsonl → hook exits 0 with no stdout."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    log_file = primary / "logs" / "smart_dispatch.jsonl"
    log_file.parent.mkdir()
    log_file.write_bytes(b"x" * 1_000)  # < 100 KB

    result = run_hook(LOG_WARN_HOOK, make_read_payload(str(log_file)), primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_log_filter_warns_on_large_dispatch_response_txt(tmp_path: Path) -> None:
    """Large dispatch_responses/*.txt → hook emits advisory warning.

    Note the .txt branch suggests grep/tail (NOT jq, since the file is plain
    text and jq would parse-fail). The jq advisory only fires for .jsonl.
    """
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    response_file = primary / "logs" / "dispatch_responses" / "run-001.txt"
    response_file.parent.mkdir(parents=True)
    response_file.write_bytes(b"x" * 200_000)  # > 100 KB

    result = run_hook(LOG_WARN_HOOK, make_read_payload(str(response_file)), primary)

    assert result.returncode == 0
    assert "hookSpecificOutput" in result.stdout
    # .txt files get tail/grep alternatives (plain-text), not jq
    assert "tail " in result.stdout or "grep" in result.stdout
    assert "jq " not in result.stdout


def test_log_filter_skips_non_log_file(tmp_path: Path) -> None:
    """Non-log file, even if large → hook exits 0 with no output."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    doc_file = primary / "docs" / "some_report.html"
    doc_file.parent.mkdir()
    doc_file.write_bytes(b"x" * 200_000)

    result = run_hook(LOG_WARN_HOOK, make_read_payload(str(doc_file)), primary)

    assert result.returncode == 0
    assert result.stdout == ""


def test_log_filter_never_blocks(tmp_path: Path) -> None:
    """Hook never returns exit code 2 (blocking) — always advisory."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    log_file = primary / "logs" / "smart_dispatch.jsonl"
    log_file.parent.mkdir()
    log_file.write_bytes(b"x" * 10_000_000)  # 10 MB

    result = run_hook(LOG_WARN_HOOK, make_read_payload(str(log_file)), primary)

    assert result.returncode == 0  # never 2


def test_log_filter_skips_non_read_tool(tmp_path: Path) -> None:
    """Non-Read tool_name → hook exits 0 immediately."""
    primary = tmp_path / "kubedojo"
    primary.mkdir()
    log_file = primary / "logs" / "smart_dispatch.jsonl"
    log_file.parent.mkdir()
    log_file.write_bytes(b"x" * 200_000)

    payload = {"tool_name": "Bash", "tool_input": {"command": f"cat {log_file}"}}
    result = run_hook(LOG_WARN_HOOK, payload, primary)

    assert result.returncode == 0
    assert result.stdout == ""
