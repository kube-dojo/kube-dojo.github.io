from __future__ import annotations

import sys
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


def test_legacy_stdout_session_metadata_still_works(tmp_path):
    output = tmp_path / "response"
    output.write_text("reply")
    result = CodexAdapter().parse_response(
        stdout=f"session id: {SESSION}", stderr="", returncode=0, output_file=output,
    )
    assert result.session_id == SESSION
