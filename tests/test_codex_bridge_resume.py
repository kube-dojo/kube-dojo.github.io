from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from agent_runtime.errors import (
    AgentStalledError,
    AgentTimeoutError,
    AgentUnavailableError,
    RateLimitedError,
)
from ai_agent_bridge import _cli, _codex, _config, _db, _messaging


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.delenv("AB_DB_PATH", raising=False)
    db_path = tmp_path / "messages.db"
    monkeypatch.setattr(_config, "DB_PATH", db_path)
    monkeypatch.setattr(_db, "DB_PATH", db_path)
    _db.init_db()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(_codex, "REPO_ROOT", repo)
    monkeypatch.setattr(_codex, "PID_DIR", tmp_path / "pids")
    monkeypatch.setattr(_codex, "has_codex_headroom", lambda _model: (True, ""))
    monkeypatch.setattr(_messaging, "subprocess", SimpleNamespace(run=lambda *_a, **_kw: None))
    invoke = Mock(return_value=SimpleNamespace(
        ok=True, response="reply", session_id="session-new", stderr_excerpt="", rate_limited=False,
    ))
    monkeypatch.setattr(_codex.agent_runner, "invoke", invoke)

    def message(task="task-1"):
        return _messaging.send_message(
            "question", task_id=task, from_llm="claude", to_llm="codex", quiet=True,
        )

    return SimpleNamespace(repo=repo, invoke=invoke, message=message)


def _stored(task="task-1"):
    row = _db.get_session(task)
    return {key: row[key] for key in ("codex_session_id", "codex_cwd", "codex_sandbox_mode")}


def _seed(repo, task="task-1", **overrides):
    fields = {"codex_session_id": "session-old", "codex_cwd": str(repo), "codex_sandbox_mode": "danger"}
    fields.update(overrides)
    _db.set_session(task, **fields)


def test_two_turns_resume_only_the_scoped_task(bridge):
    first = bridge.message()
    _codex.process_for_codex(first)
    _codex.process_for_codex(bridge.message())
    calls = bridge.invoke.call_args_list
    assert [call.kwargs["session_id"] for call in calls] == [None, "session-new"]
    assert all(call.kwargs["cwd"] == bridge.repo for call in calls)
    assert all(call.kwargs["mode"] == "danger" for call in calls)
    assert all(call.kwargs["entrypoint"] == "bridge" for call in calls)
    assert _stored() == {
        "codex_session_id": "session-new", "codex_cwd": str(bridge.repo), "codex_sandbox_mode": "danger",
    }
    conn = _db.get_db()
    try:
        assert conn.execute("SELECT acknowledged FROM messages WHERE id = ?", (first,)).fetchone()[0] == 1
    finally:
        conn.close()
    _codex.process_for_codex(bridge.message("another-task"))
    assert bridge.invoke.call_args.kwargs["session_id"] is None


@pytest.mark.parametrize("new_session", [False, True])
def test_fresh_call_without_returned_id_cannot_resurrect_old_session(bridge, new_session):
    _seed(bridge.repo, codex_sandbox_mode="danger" if new_session else "read-only")

    def fresh(*_args, **kwargs):
        assert kwargs["session_id"] is None
        assert _stored() == {"codex_session_id": "", "codex_cwd": "", "codex_sandbox_mode": ""}
        return SimpleNamespace(ok=True, response="reply", session_id=None)

    bridge.invoke.side_effect = fresh
    _codex.process_for_codex(bridge.message(), new_session=new_session)
    _codex.process_for_codex(bridge.message())
    assert bridge.invoke.call_count == 2
    assert _stored()["codex_session_id"] == ""


@pytest.mark.parametrize("scope", ["missing-cwd", "missing-mode", "missing-dir", "other-cwd", "other-mode", "empty-id"])
def test_missing_or_mismatched_scope_starts_fresh(bridge, scope):
    other = bridge.repo.parent / "other"
    other.mkdir()
    overrides = {
        "missing-cwd": {"codex_cwd": ""},
        "missing-mode": {"codex_sandbox_mode": ""},
        "missing-dir": {"codex_cwd": str(other / "missing")},
        "other-cwd": {"codex_cwd": str(other)},
        "other-mode": {"codex_sandbox_mode": "read-only"},
        "empty-id": {"codex_session_id": ""},
    }[scope]
    _seed(bridge.repo, **overrides)
    _codex.process_for_codex(bridge.message())
    assert bridge.invoke.call_args.kwargs["session_id"] is None


def test_canonical_cwd_match_and_missing_resumed_output_id(bridge):
    alias = bridge.repo.parent / "alias"
    alias.symlink_to(bridge.repo, target_is_directory=True)
    _seed(alias)
    bridge.invoke.return_value.session_id = None
    _codex.process_for_codex(bridge.message())
    assert bridge.invoke.call_args.kwargs["session_id"] == "session-old"
    assert _stored()["codex_session_id"] == "session-old"
    assert _stored()["codex_cwd"] == str(bridge.repo)


@pytest.mark.parametrize("task", [None, "", " \t", "discuss:thread"])
def test_taskless_and_discussion_keys_never_read_or_write_session(bridge, task):
    _seed(bridge.repo, task=task)
    before = _stored(task)
    _codex.process_for_codex(bridge.message(task))
    assert bridge.invoke.call_args.kwargs["session_id"] is None
    assert _stored(task) == before


@pytest.mark.parametrize("error", [
    AgentStalledError("codex", 1, 2), AgentTimeoutError("codex", 1), AgentUnavailableError("failed"),
])
def test_failed_resume_clears_scope_and_reports_error_without_retry(bridge, error):
    _seed(bridge.repo)
    bridge.invoke.side_effect = error
    message_id = bridge.message()
    _codex.process_for_codex(message_id)
    assert bridge.invoke.call_count == 1
    assert _stored() == {"codex_session_id": "", "codex_cwd": "", "codex_sandbox_mode": ""}
    conn = _db.get_db()
    try:
        assert conn.execute("SELECT acknowledged FROM messages WHERE id = ?", (message_id,)).fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.parametrize("rate_limited", [False, True])
def test_failed_result_only_preserves_session_on_rate_limit(bridge, rate_limited):
    _seed(bridge.repo)
    bridge.invoke.return_value = SimpleNamespace(
        ok=False, response="", session_id=None, stderr_excerpt="failed", rate_limited=rate_limited,
    )
    _codex.process_for_codex(bridge.message())
    assert bridge.invoke.call_count == 1
    assert _stored()["codex_session_id"] == ("session-old" if rate_limited else "")


def test_rate_limited_resume_preserves_session_and_leaves_message_pending(bridge):
    _seed(bridge.repo)
    bridge.invoke.side_effect = RateLimitedError("codex", "test", "limited")
    message_id = bridge.message()
    _codex.process_for_codex(message_id)
    assert bridge.invoke.call_count == 1
    assert _stored()["codex_session_id"] == "session-old"
    conn = _db.get_db()
    try:
        assert conn.execute("SELECT acknowledged FROM messages WHERE id = ?", (message_id,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_task_lock_blocks_duplicate_calls_and_releases_after_error(bridge):
    _seed(bridge.repo)
    message_id = bridge.message()
    with _codex._codex_task_lock("task-1") as acquired:
        assert acquired
        _codex.process_for_codex(message_id)
        bridge.invoke.assert_not_called()
    bridge.invoke.side_effect = RuntimeError("unexpected")
    with pytest.raises(RuntimeError, match="unexpected"):
        _codex.process_for_codex(message_id)
    assert _stored()["codex_session_id"] == ""
    bridge.invoke.side_effect = None
    _codex.process_for_codex(message_id)
    assert bridge.invoke.call_count == 2
    assert bridge.invoke.call_args.kwargs["session_id"] is None


def test_task_key_is_never_used_as_a_lock_path(bridge):
    with _codex._codex_task_lock("../../outside") as acquired:
        assert acquired
        assert len(list(_codex.PID_DIR.glob("codex-*.lock"))) == 1
    assert not (bridge.repo.parent / "outside").exists()


def test_acknowledged_message_is_skipped_unless_force_is_explicit(bridge):
    message_id = bridge.message()
    assert _codex.process_for_codex(message_id) == "done"
    assert _codex.process_for_codex(message_id) == "skipped"
    assert bridge.invoke.call_count == 1
    assert _codex.process_for_codex(message_id, force=True) == "done"
    assert bridge.invoke.call_count == 2


def test_explicit_self_addressed_ask_still_runs_once(bridge):
    message_id = _codex.ask_codex("question", task_id="task-1", from_llm="codex")
    assert bridge.invoke.call_count == 1
    assert _codex.process_for_codex(message_id) == "skipped"
    assert bridge.invoke.call_count == 1


def test_cli_force_explicitly_reprocesses_an_acknowledged_message(bridge, monkeypatch):
    message_id = bridge.message()
    _codex.process_for_codex(message_id)
    monkeypatch.setattr(sys, "argv", ["ab", "process-codex", str(message_id), "--force"])
    _cli.main()
    assert bridge.invoke.call_count == 2


def test_batch_reports_a_locked_message_as_skipped(bridge, capsys):
    bridge.message()
    with _codex._codex_task_lock("task-1"):
        _codex.process_all_codex()
    bridge.invoke.assert_not_called()
    assert "0 succeeded, 0 failed, 1 skipped, 0 deferred" in capsys.readouterr().out


def test_acknowledgment_is_rechecked_inside_the_task_lock(bridge, monkeypatch):
    message_id = bridge.message()
    fetch = _codex._fetch_codex_message

    def racing_fetch(mid):
        msg = fetch(mid)
        _messaging.acknowledge(mid)
        return msg

    monkeypatch.setattr(_codex, "_fetch_codex_message", racing_fetch)
    assert _codex.process_for_codex(message_id) == "skipped"
    bridge.invoke.assert_not_called()


def test_review_flag_is_fresh_and_preserves_the_implementation_session(bridge, monkeypatch):
    _seed(bridge.repo)
    before = _stored()
    monkeypatch.setattr(sys, "argv", ["ab", "ask-codex", "review this", "--review", "--task-id", "task-1"])
    _cli.main()
    assert bridge.invoke.call_args.kwargs["session_id"] is None
    assert _stored() == before


def test_resumed_id_is_retained_on_mismatched_returned_id(bridge, caplog):
    _seed(bridge.repo)
    _codex.process_for_codex(bridge.message())
    assert _stored()["codex_session_id"] == "session-old"
    assert "retaining the requested session" in caplog.text


@pytest.mark.parametrize("model", ["bad\nsession id: injected", "bad model", [], 123])
def test_invalid_model_metadata_is_rejected_before_invocation(bridge, model):
    import json

    message_id = _messaging.send_message(
        "question", task_id="task-1", from_llm="claude", to_llm="codex",
        data=json.dumps({"to_model": model}), quiet=True,
    )
    assert _codex.process_for_codex(message_id) == "failed"
    bridge.invoke.assert_not_called()
