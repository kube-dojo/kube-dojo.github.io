"""Unit tests for the ``DeepSeekAdapter`` opencode / deepseek-direct integration."""
from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.adapters.deepseek import DeepSeekAdapter


def _build(monkeypatch, *, model=None, mode="read-only", tool_config=None, prompt="p"):
    monkeypatch.setattr("agent_runtime.adapters.deepseek.shutil.which", lambda _: "opencode")
    return DeepSeekAdapter().build_invocation(
        prompt=prompt,
        mode=mode,
        cwd=Path("/tmp"),
        model=model,
        task_id=None,
        session_id=None,
        tool_config=tool_config,
    )


def test_build_invocation_read_only(monkeypatch) -> None:
    plan = _build(monkeypatch)
    cmd = plan.cmd
    assert cmd[:6] == [
        "opencode",
        "run",
        "--format",
        "json",
        "-m",
        "deepseek-direct/deepseek-flash",
    ]
    assert "--auto" not in cmd
    assert cmd[-1] == "-"
    assert plan.stdin_payload == "p"
    assert "--variant" in cmd
    assert cmd[cmd.index("--variant") + 1] == "high"


def test_build_invocation_workspace_write_auto(monkeypatch) -> None:
    plan = _build(monkeypatch, mode="workspace-write")
    assert "--auto" in plan.cmd


def test_build_invocation_danger_auto(monkeypatch) -> None:
    plan = _build(monkeypatch, mode="danger")
    assert "--auto" in plan.cmd


def test_model_routes_legacy_flash_alias(monkeypatch) -> None:
    plan = _build(monkeypatch, model="deepseek-v4-flash")
    assert plan.cmd[plan.cmd.index("-m") + 1] == "deepseek-direct/deepseek-v4-flash"


def test_model_routes_pro_override(monkeypatch) -> None:
    plan = _build(monkeypatch, model="deepseek-v4-pro")
    assert plan.cmd[plan.cmd.index("-m") + 1] == "deepseek-direct/deepseek-v4-pro"


def test_explicit_provider_prefix_passes_through(monkeypatch) -> None:
    plan = _build(monkeypatch, model="deepseek-direct/deepseek-flash")
    assert plan.cmd[plan.cmd.index("-m") + 1] == "deepseek-direct/deepseek-flash"


def test_effort_override_maps_to_variant(monkeypatch) -> None:
    plan = _build(monkeypatch, tool_config={"effort": "xhigh"})
    assert plan.cmd[plan.cmd.index("--variant") + 1] == "max"


def test_parse_response_ndjson_text() -> None:
    adapter = DeepSeekAdapter()
    events = "\n".join(
        [
            json.dumps(
                {
                    "type": "text",
                    "part": {"messageID": "m1", "text": "Hello"},
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {"messageID": "m1", "reason": "stop"},
                }
            ),
        ]
    )
    result = adapter.parse_response(
        stdout=events,
        stderr="",
        returncode=0,
        output_file=None,
    )
    assert result.ok is True
    assert result.response == "Hello"


def test_parse_response_detects_rate_limit() -> None:
    adapter = DeepSeekAdapter()
    result = adapter.parse_response(
        stdout="",
        stderr="rate limit exceeded",
        returncode=1,
        output_file=None,
    )
    assert result.rate_limited is True
    assert result.ok is False


def test_parse_response_nonzero_exit_fails() -> None:
    adapter = DeepSeekAdapter()
    result = adapter.parse_response(
        stdout="partial",
        stderr="boom",
        returncode=1,
        output_file=None,
    )
    assert result.ok is False
    assert result.stderr_excerpt is not None
