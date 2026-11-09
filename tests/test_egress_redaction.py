from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from agent_runtime.redact import REDACTION, redact_jsonable, redact_text
from ai_agent_bridge import _channels, _db, _github, _messaging

GH_PAT = "github_pat_012345678901234567890123456789"
OPENAI_KEY = "sk-012345678901234567890123456789"
GEMINI_KEY = "AIza012345678901234567890123456789"


def test_redact_text_catches_token_values_and_assignments():
    text = (
        f"GITHUB_TOKEN={GH_PAT}\n"
        f"OPENAI_API_KEY: {OPENAI_KEY}\n"
        f"plain {GEMINI_KEY}"
    )

    redacted = redact_text(text)

    assert GH_PAT not in redacted
    assert OPENAI_KEY not in redacted
    assert GEMINI_KEY not in redacted
    assert redacted.count(REDACTION) >= 3


def test_redact_text_catches_quoted_secret_assignments():
    text = 'GITHUB_TOKEN="custom format secret" PASSWORD=\'another custom secret\''

    redacted = redact_text(text)

    assert "custom format secret" not in redacted
    assert "another custom secret" not in redacted
    assert redacted == f"GITHUB_TOKEN={REDACTION} PASSWORD={REDACTION}"


def test_redact_jsonable_recurses_nested_payloads():
    payload = {"outer": [{"token": GH_PAT}], "safe": "keep"}

    redacted = redact_jsonable(payload)

    assert redacted["outer"][0]["token"] == REDACTION
    assert redacted["safe"] == "keep"


def test_redact_jsonable_redacts_values_when_key_is_sensitive():
    payload = {
        "PASSWORD": "custom format secret",
        "nested": {"client_secret": "not token shaped"},
        "safe": "keep",
    }

    redacted = redact_jsonable(payload)

    assert redacted["PASSWORD"] == REDACTION
    assert redacted["nested"]["client_secret"] == REDACTION
    assert redacted["safe"] == "keep"


def test_github_comment_redacts_body_before_posting():
    completed = subprocess.CompletedProcess(
        ["gh"], 0, stdout="", stderr="",
    )

    with patch("ai_agent_bridge._github.subprocess.run", return_value=completed) as run:
        assert _github._gh_comment(123, f"leak {GH_PAT}") is True

    posted = run.call_args.kwargs["input"]
    assert GH_PAT not in posted
    assert REDACTION in posted


def test_message_broker_redacts_content_and_data(tmp_path):
    db_file = tmp_path / "messages.db"
    with patch("ai_agent_bridge._config.DB_PATH", db_file), patch(
        "ai_agent_bridge._db.DB_PATH", db_file,
    ), patch("ai_agent_bridge._messaging.subprocess.run"):
        _db.init_db()
        msg_id = _messaging.send_message(
            f"content {GH_PAT}",
            data=json.dumps({"key": OPENAI_KEY}),
            quiet=True,
        )
        msg = _messaging.read_message(msg_id, quiet=True)

    assert GH_PAT not in msg["content"]
    assert REDACTION in msg["content"]
    assert OPENAI_KEY not in msg["data"]
    assert REDACTION in msg["data"]


def test_channel_post_redacts_body_attachments_and_monitor_snapshot(tmp_path):
    db_file = tmp_path / "messages.db"
    with patch("ai_agent_bridge._config.DB_PATH", db_file), patch(
        "ai_agent_bridge._db.DB_PATH", db_file,
    ):
        _db.init_db()
        _channels.create_channel("topic")
        _channels.post(
            "topic",
            "gemini",
            f"body {GH_PAT}",
            attachments=[{"token": OPENAI_KEY}],
            monitor_state_snapshot={"token": GEMINI_KEY},
            auto_snapshot=False,
        )
        msg = _channels.read("topic")[0]

    assert GH_PAT not in msg["body"]
    assert msg["attachments"][0]["token"] == REDACTION
    assert msg["monitor_state_snapshot"]["token"] == REDACTION
