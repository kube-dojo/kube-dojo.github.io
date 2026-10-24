from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from agent_runtime.adapters.codex import CodexAdapter

SESSION = "12345678-1234-5678-9abc-123456789abc"
OTHER = "87654321-4321-8765-abcd-987654321abc"


@pytest.mark.parametrize("stderr, expected", [
    (f"OpenAI Codex v0.164.0\n--------\nsession id: {SESSION}\n--------\nuser\nquestion", SESSION),
    (f"OpenAI Codex v0.164.0\n--------\nsession id: {SESSION}\n--------\nuser\nsession id: {OTHER}", SESSION),
    (f"OpenAI Codex v0.164.0\n--------\nmodel: test\n--------\nuser\nsession id: {OTHER}", None),
    (f"user\nsession id: {OTHER}", None),
    ("OpenAI Codex v0.164.0\n--------\nsession id: abcdef12\n--------\nuser\nquestion", None),
])
def test_session_id_is_read_only_from_stderr_startup_metadata(tmp_path, stderr, expected):
    output = tmp_path / "response"
    output.write_text("reply")
    result = CodexAdapter().parse_response(
        stdout="", stderr=stderr, returncode=0, output_file=output,
    )
    assert result.ok
    assert result.response == "reply"
    assert result.session_id == expected


@pytest.mark.parametrize("stdout", [f"session id: {OTHER}", f"OpenAI Codex v0.164.0\n--------\nsession id: {OTHER}\n--------\n"])
def test_model_stdout_cannot_supply_or_override_the_session_id(tmp_path, stdout):
    output = tmp_path / "response"
    output.write_text("reply")
    result = CodexAdapter().parse_response(
        stdout=stdout, stderr="", returncode=0, output_file=output,
    )
    assert result.session_id is None
    result = CodexAdapter().parse_response(
        stdout=stdout, stderr=f"OpenAI Codex v0.164.0\n--------\nsession id: {SESSION}\n--------\n",
        returncode=0, output_file=output,
    )
    assert result.session_id == SESSION


def test_duplicate_session_lines_are_not_accepted(tmp_path):
    output = tmp_path / "response"
    output.write_text("reply")
    result = CodexAdapter().parse_response(
        stdout="", stderr=f"OpenAI Codex v0.164.0\n--------\nsession id: {SESSION}\nsession id: {OTHER}\n--------\n",
        returncode=0, output_file=output,
    )
    assert result.session_id is None


@pytest.mark.parametrize("resumed", [False, True])
def test_foreign_rollout_never_reaps_or_supplies_output(tmp_path, monkeypatch, resumed):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    adapter = CodexAdapter()
    plan = adapter.build_invocation(
        prompt="owned prompt", mode="danger", cwd=tmp_path, model=None,
        task_id="owned", session_id=SESSION if resumed else None, tool_config=None,
    )
    original_output = plan.output_file
    output = tmp_path / "owned-output"
    output.write_text("")
    plan = replace(plan, output_file=output)
    today = datetime.now(UTC)
    rollouts = tmp_path / ".codex/sessions" / f"{today:%Y/%m/%d}"
    rollouts.mkdir(parents=True)
    (rollouts / f"rollout-foreign-{OTHER}.jsonl").write_text(json.dumps({
        "type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "FOREIGN ANSWER"},
    }) + "\n")
    try:
        assert not adapter.check_early_reap(plan, call_start_time=time.monotonic() - 10)
        result = adapter.parse_response(
            stdout="", stderr="", returncode=0, output_file=output, plan=plan,
        )
        assert not result.ok
        assert result.response == ""
        assert result.session_id is None
    finally:
        original_output.unlink()
