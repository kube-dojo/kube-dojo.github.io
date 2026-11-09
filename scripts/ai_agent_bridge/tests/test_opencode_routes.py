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


def test_openrouter_prefix_routes_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ``openrouter/`` model slug selects the OpenRouter provider.

    #3872 deleted ``ai_agent_bridge._hermes._detect_provider``. The live
    mapping with the same prefix contract is
    ``dispatch_smart._hermes_provider_for_model``.
    """
    from dispatch_smart import _hermes_provider_for_model

    monkeypatch.delenv("KUBEDOJO_HERMES_PROVIDER", raising=False)
    assert (
        _hermes_provider_for_model("openrouter/anthropic/claude-opus-4-6")
        == "openrouter"
    )
    assert (
        _hermes_provider_for_model("openrouter/qwen/qwen3.7-max")
        == "openrouter"
    )


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
    """OpenCode stays in the supported-agent list.

    The deleted combined check also asserted per-class OpenCode model
    slugs and Hermes seats. Hermes assertions are omitted. The OpenCode
    slugs are absent from ``TASK_CLASSES`` (removed in 76d107f60, before
    #3872), so those equalities are not restored: they fail on live code.
    """
    from dispatch_smart import SUPPORTED_AGENTS

    assert "opencode" in SUPPORTED_AGENTS
