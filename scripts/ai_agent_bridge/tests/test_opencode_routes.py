from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_opencode_command_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from ai_agent_bridge import _opencode

    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="OPENCODE OK\n", stderr="")

    monkeypatch.setenv("KUBEDOJO_OPENCODE_CMD", "opencode")
    monkeypatch.setattr(_opencode.subprocess, "run", fake_run)

    ok, response, stderr = _opencode._invoke_opencode(
        "prompt",
        "openrouter/qwen/qwen3.7-max",
        timeout_s=3,
        cwd=tmp_path,
    )

    assert ok is True
    assert response == "OPENCODE OK"
    assert stderr == ""
    assert captured["cmd"] == [
        "opencode",
        "run",
        "-m",
        "openrouter/qwen/qwen3.7-max",
        "-",
    ]
    assert captured["kwargs"]["input"] == "prompt"
    assert captured["kwargs"]["cwd"] == tmp_path
    assert captured["kwargs"]["timeout"] == 3
    assert captured["kwargs"]["capture_output"] is True


def test_task_classes_include_opencode() -> None:
    """OpenCode stays on the live bridge agent lists."""
    from ai_agent_bridge._channels import VALID_AGENTS
    from ai_agent_bridge._cli import AGENT_CHOICES

    assert "opencode" in AGENT_CHOICES
    assert "opencode" in VALID_AGENTS
