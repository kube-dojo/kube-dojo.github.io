"""Unit tests for KimiAdapter (ACP oneshot wrapper)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_runtime.adapters.kimi import _ONESHOT, KimiAdapter


def test_build_invocation_uses_acp_oneshot_and_stdin() -> None:
    adapter = KimiAdapter()
    plan = adapter.build_invocation(
        prompt="do the thing",
        mode="danger",
        cwd=Path("/tmp/wt"),
        model="kimi-code/k3-256k",
        task_id="t1",
        session_id=None,
        tool_config={"hard_timeout": 900},
    )
    assert plan.stdin_payload == "do the thing"
    assert plan.cwd == Path("/tmp/wt")
    assert str(_ONESHOT) in plan.cmd
    assert "--model" in plan.cmd
    assert plan.cmd[plan.cmd.index("--model") + 1] == "kimi-code/k3-256k"
    assert plan.cmd[plan.cmd.index("--timeout") + 1] == "900"
    assert "-p" not in plan.cmd  # never kimi -p


def test_parse_ok_and_failure() -> None:
    adapter = KimiAdapter()
    plan = adapter.build_invocation(
        prompt="x",
        mode="read-only",
        cwd=Path("/tmp"),
        model=None,
        task_id=None,
        session_id=None,
        tool_config=None,
    )
    ok = adapter.parse_response(
        stdout="hello",
        stderr="",
        returncode=0,
        output_file=None,
        plan=plan,
    )
    assert ok.ok is True
    assert ok.response == "hello"

    bad = adapter.parse_response(
        stdout="",
        stderr="rate limit hit",
        returncode=1,
        output_file=None,
        plan=plan,
    )
    assert bad.ok is False
    assert bad.rate_limited is True
