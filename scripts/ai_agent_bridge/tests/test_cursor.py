from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_cursor_command_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from ai_agent_bridge import _cursor

    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="CURSOR OK\n", stderr="")

    monkeypatch.setenv("KUBEDOJO_CURSOR_CMD", "cursor-agent")
    monkeypatch.setattr(_cursor.subprocess, "run", fake_run)

    ok, response, stderr = _cursor._invoke_cursor(
        "hello world",
        "composer-2.5",
        timeout_s=3,
        cwd=tmp_path,
    )

    assert ok is True
    assert response == "CURSOR OK"
    assert stderr == ""
    assert captured["cmd"] == [
        "cursor-agent",
        "--print",
        "--force",
        "--trust",
        "--model",
        "composer-2.5",
        "--output-format",
        "text",
        "--",
        "hello world",
    ]
    assert captured["kwargs"]["input"] == ""
    assert captured["kwargs"]["cwd"] == tmp_path
    assert captured["kwargs"]["timeout"] == 3
    assert captured["kwargs"]["capture_output"] is True


def test_build_command_end_of_options_before_monitor_state_prompt() -> None:
    """Regression test for #1488 — ab discuss monitor-state prefix parsed as flags.

    cursor-agent uses commander.js, which treats any argv element beginning
    with ``--`` as an option flag even after positional args have started.
    The discuss prompt assembled by ``_channels.py:466`` always starts with
    ``--- monitor: project state (volatile) ---``, so every cursor invocation
    in an ``ab discuss`` channel failed with ``error: unknown option ...``
    until the POSIX ``--`` end-of-options marker was inserted before the
    prompt argv. See GitHub issue #1488 for the full root-cause writeup.
    """

    from ai_agent_bridge import _cursor

    prompt = '--- monitor: project state (volatile) ---\n{"x": 1}'
    command = _cursor._build_command(prompt, "composer-2.5")

    assert command[-2] == "--"
    assert command[-1] == prompt


def test_cursor_default_model_is_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    monkeypatch.delenv("AB_CURSOR_MODEL", raising=False)
    import ai_agent_bridge._cursor as _cursor

    importlib.reload(_cursor)

    assert _cursor._DEFAULT_MODEL == "auto"


def test_cursor_default_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    monkeypatch.setenv("AB_CURSOR_MODEL", "composer-2.5-fast")
    import ai_agent_bridge._cursor as _cursor

    importlib.reload(_cursor)

    assert _cursor._DEFAULT_MODEL == "composer-2.5-fast"


def test_cursor_binary_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEDOJO_CURSOR_CMD", "/opt/alt/bin/cursor-agent")

    from ai_agent_bridge import _cursor

    assert _cursor._cursor_binary() == "/opt/alt/bin/cursor-agent"
