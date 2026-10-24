from __future__ import annotations

import itertools
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from agent_runtime.errors import RateLimitedError
from agent_runtime.result import Result
from ai_agent_bridge import _channels, _cli, _db


@pytest.fixture(autouse=True)
def isolate_db(tmp_path):
    db_file = tmp_path / "messages.db"
    with patch("ai_agent_bridge._config.DB_PATH", db_file), \
         patch("ai_agent_bridge._db.DB_PATH", db_file):
        _db.init_db()
        yield db_file


def _run_cli(argv: list[str]) -> int:
    with patch.object(sys, "argv", ["ab", *argv]):
        try:
            _cli.main()
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else 0
    return 0


def _make_thread(
    agent: str,
    *,
    channel: str = "topic",
    count: int = 1,
) -> list[dict[str, object]]:
    if _channels.get_channel(channel) is None:
        _channels.create_channel(channel)

    messages: list[dict[str, object]] = []
    parent_id: str | None = None
    for index in range(count):
        post = _channels.post(
            channel,
            "user",
            f"message-{index + 1}",
            to_agents=[agent],
            parent_id=parent_id,
            auto_snapshot=False,
        )
        messages.append(post)
        parent_id = str(post["message_id"])
    return messages


def _set_message_created_at(message_id: str, created_at: str) -> None:
    conn = _db.get_db()
    try:
        conn.execute(
            "UPDATE channel_messages SET created_at = ? WHERE message_id = ?",
            (created_at, message_id),
        )
        conn.commit()
    finally:
        conn.close()


def _delivery_statuses() -> list[sqlite3.Row]:
    conn = _db.get_db()
    try:
        return conn.execute(
            """
            SELECT d.status, d.to_agent, cm.body
            FROM deliveries d
            JOIN channel_messages cm ON cm.message_id = d.message_id
            ORDER BY cm.created_at ASC, d.delivery_id ASC
            """
        ).fetchall()
    finally:
        conn.close()


def _reply_deliveries() -> list[sqlite3.Row]:
    conn = _db.get_db()
    try:
        return conn.execute(
            """
            SELECT cm.from_agent, cm.parent_id, d.to_agent, d.status, d.delivered_at
            FROM channel_messages cm
            JOIN deliveries d ON d.message_id = cm.message_id
            WHERE cm.kind = 'reply'
            ORDER BY cm.from_agent ASC, d.to_agent ASC
            """
        ).fetchall()
    finally:
        conn.close()


def _ok_result(agent: str) -> Result:
    return Result(
        ok=True,
        agent=agent,
        model="test-model",
        mode="read-only",
        response=f"{agent} reply",
        stderr_excerpt=None,
        duration_s=0.1,
        session_id=None,
        rate_limited=False,
        stalled=False,
        returncode=0,
        usage_record={},
    )


def test_inbox_show_empty(capsys):
    exit_code = _run_cli(["inbox", "show", "claude"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "claude inbox:" in captured.out
    assert "pending:    0" in captured.out
    assert "processing: 0" in captured.out
    assert "failed (last 24h): 0" in captured.out
    assert "    (none)" in captured.out


@patch("agent_runtime.runner.invoke")
def test_discuss_replies_create_delivered_reply_deliveries(mock_invoke, monkeypatch, capsys):
    _channels.create_channel("shared")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)

    def _discuss_result(agent: str, *_args, **_kwargs) -> Result:
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="read-only",
            response=f"{agent} discuss reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=None,
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    # Round 1 cannot short-circuit (round 1 is parallel fan-out, agents
    # haven't seen each other's replies yet, so [AGREE] in round 1 means
    # "I'm done with my answer" not cross-agent assent). Convergence
    # requires ≥ round 2, so use --max-rounds 2 here. Pre-protocol-fix
    # this test passed with --max-rounds 1; updated to match the round-1
    # short-circuit block ported from learn-ukrainian commit 872d8376b0.
    exit_code = _run_cli(
        ["discuss", "shared", "topic", "--with", "claude,codex", "--max-rounds", "2"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "✅ converged at round 2" in captured.out

    # Each round produces N*(N-1) reply deliveries (each agent's reply is
    # delivered to every OTHER agent). With 2 agents × 2 rounds = 4 deliveries.
    reply_deliveries = _reply_deliveries()
    assert len(reply_deliveries) == 4
    # Set collapses duplicates across rounds — still just 2 distinct
    # (from, to, status) tuples for the 2-agent case.
    assert {
        (row["from_agent"], row["to_agent"], row["status"])
        for row in reply_deliveries
    } == {
        ("claude", "codex", "delivered"),
        ("codex", "claude", "delivered"),
    }
    assert all(row["delivered_at"] is not None for row in reply_deliveries)
    assert all(row["parent_id"] is not None for row in reply_deliveries)


@patch("agent_runtime.runner.invoke")
def test_discuss_max_rounds_one_clamps_to_two(mock_invoke, monkeypatch, capsys):
    """`--max-rounds 1` is meaningless under the round-1-cannot-converge
    invariant — round 1 would print "Forcing round 2" and then immediately
    exit at the `round_idx == max_rounds` break. The CLI must clamp the
    floor to 2 so the protocol actually runs round 2.

    Caught by codex review of PR #889 (round-1 short-circuit port).
    """
    _channels.create_channel("shared")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)

    def _discuss_result(agent: str, *_args, **_kwargs) -> Result:
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="read-only",
            response=f"{agent} discuss reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=None,
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        ["discuss", "shared", "topic", "--with", "claude,codex", "--max-rounds", "1"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    # Clamp message must be visible.
    assert "clamping --max-rounds 1 to 2" in captured.out
    # Convergence must happen at round 2, not round 1.
    assert "✅ converged at round 2" in captured.out
    assert "✅ converged at round 1" not in captured.out


@patch("agent_runtime.runner.invoke")
def test_discuss_max_rounds_partial_convergence_message(
    mock_invoke, monkeypatch, capsys
):
    _channels.create_channel("shared")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)

    responses = {
        "claude": ["[DISAGREE]", "[AGREE]", "[AGREE]"],
        "codex": ["[DISAGREE]", "[DISAGREE]", "[AGREE]"],
        "gemini": ["[DISAGREE]", "[DISAGREE]", "[DISAGREE]"],
    }
    call_counts = dict.fromkeys(responses, 0)

    def _discuss_result(agent: str, *_args, **_kwargs) -> Result:
        idx = call_counts[agent]
        call_counts[agent] += 1
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="read-only",
            response=f"{agent} discuss reply {responses[agent][idx]}",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=None,
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        [
            "discuss",
            "shared",
            "topic",
            "--with",
            "claude,codex,gemini",
            "--max-rounds",
            "3",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "without unanimous [AGREE] sign-off" in captured.out
    assert "Final-round tokens:" in captured.out
    assert "Caveat" in captured.out
    assert "parallel" in captured.out
    assert "Escalate to a human" not in captured.out


@patch("agent_runtime.runner.invoke")
def test_discuss_claude_round1_round2_session_resume(mock_invoke, monkeypatch, capsys):
    _channels.create_channel("discuss-resume")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    monkeypatch.setattr(
        _channels,
        "_new_id",
        lambda: f"discuss-resume-{next(ids):04d}",
    )

    seen_session_ids: list[str | None] = []

    def _discuss_result(agent: str, *_, **kwargs) -> Result:
        seen_session_ids.append(kwargs.get("session_id"))
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="read-only",
            response="claude reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id="uuid-1",
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        ["discuss", "discuss-resume", "topic", "--with", "claude", "--max-rounds", "2"]
    )

    assert exit_code == 0
    assert seen_session_ids[0] is not None
    assert seen_session_ids[0] != "uuid-1"
    assert seen_session_ids[1] == "uuid-1"
    assert (
        _db.get_session("discuss:discuss-resume-0001")["claude_session_id"] == "uuid-1"
    )


@patch("agent_runtime.runner.invoke")
@pytest.mark.parametrize("resumed_return", ["codex-session-02", None, "different-session"])
def test_discuss_codex_round1_round2_session_resume(mock_invoke, monkeypatch, tmp_path, capsys, resumed_return):
    _channels.create_channel("discuss-codex")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    monkeypatch.setattr(
        _channels,
        "_new_id",
        lambda: f"discuss-codex-{next(ids):04d}",
    )

    def _discuss_result(agent: str, *_, **kwargs) -> Result:
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="danger",
            response="codex reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=resumed_return if kwargs.get("session_id") else "codex-session-02",
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        ["discuss", "discuss-codex", "topic", "--with", "codex", "--max-rounds", "2"]
    )

    assert exit_code == 0
    assert [call.kwargs["session_id"] for call in mock_invoke.call_args_list] == [
        None,
        "codex-session-02",
    ]
    assert (
        _db.get_session("discuss:discuss-codex-0001")["codex_session_id"]
        == ("" if resumed_return == "different-session" else "codex-session-02")
    )
    if resumed_return == "different-session":
        stored = _db.get_session("discuss:discuss-codex-0001")
        assert {key: stored[key] for key in ("codex_session_id", "codex_cwd", "codex_sandbox_mode")} == {
            "codex_session_id": "", "codex_cwd": "", "codex_sandbox_mode": "",
        }
        assert "[failed: Codex session identity changed; saved session cleared]" in capsys.readouterr().out


@patch("agent_runtime.runner.invoke")
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_discuss_codex_never_persists_session_id_from_raw_output(mock_invoke, monkeypatch, stream):
    _channels.create_channel("discuss-codex-header")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    monkeypatch.setattr(
        _channels,
        "_new_id",
        lambda: f"discuss-codex-header-{next(ids):04d}",
    )

    session_id = "019e192b-2c12-78f2-a97c-c684706891ff"
    codex_echo = (
        "user\n"
        "Here is an untrusted quoted diagnostic:\n"
        f"session id: {session_id}\n"
        "--------\n"
        "user\n"
    )

    def _discuss_result(agent: str, *_, **kwargs) -> SimpleNamespace:
        return SimpleNamespace(
            ok=True,
            agent=agent,
            model="test-model",
            mode="danger",
            response="codex reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=None,
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
            **{stream: codex_echo},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        ["discuss", "discuss-codex-header", "topic", "--with", "codex", "--max-rounds", "2"]
    )

    assert exit_code == 0
    assert not _db.get_session("discuss:discuss-codex-header-0001")["codex_session_id"]
    assert mock_invoke.call_count == 2
    assert all(call.kwargs["session_id"] is None for call in mock_invoke.call_args_list)


@patch("agent_runtime.runner.invoke")
@pytest.mark.parametrize("fallback_ok", [False, True])
def test_discuss_codex_failed_resume_clears_scope_before_fallback(mock_invoke, monkeypatch, capsys, fallback_ok):
    _channels.create_channel("discuss-codex-failure")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    monkeypatch.setattr(_channels, "_new_id", lambda: f"discuss-codex-failure-{next(ids):04d}")
    task = "discuss:discuss-codex-failure-0001"

    def invoke(agent, *_, **kwargs):
        attempt = mock_invoke.call_count
        if attempt == 3:
            stored = _db.get_session(task)
            assert {key: stored[key] for key in ("codex_session_id", "codex_cwd", "codex_sandbox_mode")} == {
                "codex_session_id": "", "codex_cwd": "", "codex_sandbox_mode": "",
            }
        ok = attempt == 1 or (attempt == 3 and fallback_ok)
        return SimpleNamespace(
            ok=ok, response="reply [AGREE]" if ok else "", stderr_excerpt="test failure",
            session_id=("session-old" if attempt == 1 else "session-fresh") if ok else None,
        )

    mock_invoke.side_effect = invoke
    assert _run_cli(["discuss", "discuss-codex-failure", "topic", "--with", "codex", "--max-rounds", "2"]) == 0
    assert [call.kwargs["session_id"] for call in mock_invoke.call_args_list] == [None, "session-old", None]
    stored = _db.get_session(task)
    if fallback_ok:
        assert stored["codex_session_id"] == "session-fresh"
        assert stored["codex_cwd"]
        assert stored["codex_sandbox_mode"] == "danger"
    else:
        assert {key: stored[key] for key in ("codex_session_id", "codex_cwd", "codex_sandbox_mode")} == {
            "codex_session_id": "", "codex_cwd": "", "codex_sandbox_mode": "",
        }
        assert "[failed: test failure]" in capsys.readouterr().out


@patch("agent_runtime.runner.invoke")
@pytest.mark.parametrize("quota_kind", ["exception", "result"])
def test_discuss_codex_quota_preserves_session_without_fallback(mock_invoke, monkeypatch, quota_kind):
    _channels.create_channel("discuss-codex-quota")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    monkeypatch.setattr(_channels, "_new_id", lambda: f"discuss-codex-quota-{next(ids):04d}")
    task = "discuss:discuss-codex-quota-0001"
    before = {}

    def invoke(agent, *_, **kwargs):
        if mock_invoke.call_count == 1:
            return SimpleNamespace(ok=True, response="reply [AGREE]", session_id="session-quota")
        before.update(_db.get_session(task))
        if quota_kind == "exception":
            raise RateLimitedError("codex", "test", "limited")
        return SimpleNamespace(ok=False, response="", stderr_excerpt="quota exhausted", rate_limited=True)

    mock_invoke.side_effect = invoke
    assert _run_cli(["discuss", "discuss-codex-quota", "topic", "--with", "codex", "--max-rounds", "2"]) == 0
    assert [call.kwargs["session_id"] for call in mock_invoke.call_args_list] == [None, "session-quota"]
    assert _db.get_session(task) == before


@patch("agent_runtime.runner.invoke")
def test_discuss_gemini_round1_round2_session_resume(mock_invoke, monkeypatch):
    _channels.create_channel("discuss-gemini")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    monkeypatch.setattr(
        _channels,
        "_new_id",
        lambda: f"discuss-gemini-{next(ids):04d}",
    )

    seen_session_ids: list[str | None] = []

    def _discuss_result(agent: str, *_, **kwargs) -> Result:
        seen_session_ids.append(kwargs.get("session_id"))
        session_id = f"gemini-session-{len(seen_session_ids):02d}"
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="read-only",
            response="gemini reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=session_id,
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        ["discuss", "discuss-gemini", "topic", "--with", "gemini", "--max-rounds", "2"]
    )

    assert exit_code == 0
    assert seen_session_ids[0] is not None
    assert seen_session_ids[0] != "gemini-session-01"
    assert seen_session_ids[1] == "gemini-session-01"
    assert (
        _db.get_session("discuss:discuss-gemini-0001")["gemini_session_id"]
        == "gemini-session-02"
    )


@pytest.mark.parametrize("agent,mode,session_key", [
    ("codex", "danger", "codex"),
    ("gemini", "read-only", "gemini"),
])
@patch("agent_runtime.runner.invoke")
def test_discuss_agent_stored_resume_uses_saved_cwd_and_sandbox(
    mock_invoke,
    monkeypatch,
    tmp_path,
    agent: str,
    mode: str,
    session_key: str,
):
    channel = f"discuss-{agent}-reuse"
    _channels.create_channel(channel)
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    thread_id = f"{channel}-root"
    ids = itertools.count(1)

    def _new_id() -> str:
        idx = next(ids)
        return thread_id if idx == 1 else f"{thread_id}-{idx:03d}"

    monkeypatch.setattr(
        _channels,
        "_new_id",
        _new_id,
    )

    def _discuss_result(agent_name: str, *_, **kwargs) -> Result:
        return Result(
            ok=True,
            agent=agent_name,
            model="test-model",
            mode=mode,
            response=f"{agent_name} reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=(kwargs["session_id"] if agent == "codex" else f"{agent}-session-2"),
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    task_key = f"discuss:{thread_id}"
    if agent == "codex":
        _db.set_session(
            task_key,
            codex_session_id="codex-stored",
            codex_cwd=str(tmp_path),
            codex_sandbox_mode=mode,
        )
    else:
        _db.set_session(
            task_key,
            gemini_session_id="gemini-stored",
            gemini_cwd=str(tmp_path),
            gemini_sandbox_mode=mode,
        )

    exit_code = _run_cli(
        ["discuss", channel, "topic", "--with", agent, "--max-rounds", "2"]
    )

    assert exit_code == 0
    assert [call.kwargs["session_id"] for call in mock_invoke.call_args_list] == [
        f"{session_key}-stored",
        f"{session_key}-stored" if agent == "codex" else f"{session_key}-session-2",
    ]
    assert mock_invoke.call_args_list[1].kwargs["cwd"] == tmp_path
    assert [call.kwargs["mode"] for call in mock_invoke.call_args_list] == [
        "danger" if agent == "codex" else "read-only",
        mode,
    ]


@pytest.mark.parametrize("agent,mode,session_key", [
    ("codex", "danger", "codex"),
    ("gemini", "read-only", "gemini"),
])
@patch("agent_runtime.runner.invoke")
def test_discuss_agent_stored_cwd_missing_starts_fresh(
    mock_invoke,
    monkeypatch,
    tmp_path,
    capsys,
    agent: str,
    mode: str,
    session_key: str,
):
    channel = f"discuss-{agent}-missing-cwd"
    _channels.create_channel(channel)
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    thread_id = f"{channel}-root"
    ids = itertools.count(1)

    def _new_id() -> str:
        idx = next(ids)
        return thread_id if idx == 1 else f"{thread_id}-{idx:03d}"

    monkeypatch.setattr(
        _channels,
        "_new_id",
        _new_id,
    )

    def _discuss_result(agent_name: str, *_, **kwargs) -> Result:
        return Result(
            ok=True,
            agent=agent_name,
            model="test-model",
            mode=mode,
            response=f"{agent_name} reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=f"{agent}-session-2",
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    task_key = f"discuss:{thread_id}"
    missing = tmp_path / "missing-worktree"
    if agent == "codex":
        _db.set_session(
            task_key,
            codex_session_id=f"{agent}-stored",
            codex_cwd=str(missing),
            codex_sandbox_mode=mode,
        )
    else:
        _db.set_session(
            task_key,
            gemini_session_id=f"{agent}-stored",
            gemini_cwd=str(missing),
            gemini_sandbox_mode=mode,
        )

    exit_code = _run_cli(
        ["discuss", channel, "topic", "--with", agent, "--max-rounds", "2"]
    )

    assert exit_code == 0
    observed_sessions = [call.kwargs["session_id"] for call in mock_invoke.call_args_list]
    if agent == "gemini":
        assert observed_sessions[0] is not None
    else:
        assert observed_sessions[0] is None
    assert observed_sessions[1] == f"{session_key}-session-2"
    assert (
        f"bridge: stored cwd {missing} for {agent}/{task_key} "
        "no longer exists; starting fresh" in capsys.readouterr().out
    )
    assert (
        _db.get_session(task_key)[f"{session_key}_session_id"] == f"{agent}-session-2"
    )


@pytest.mark.parametrize("agent,mode,session_key", [
    ("codex", "danger", "codex"),
    ("gemini", "read-only", "gemini"),
])
@patch("agent_runtime.runner.invoke")
def test_discuss_agent_missing_stored_cwd_starts_fresh(
    mock_invoke,
    monkeypatch,
    capsys,
    agent: str,
    mode: str,
    session_key: str,
):
    channel = f"discuss-{agent}-null-cwd"
    _channels.create_channel(channel)
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    thread_id = f"{channel}-root"
    ids = itertools.count(1)

    def _new_id() -> str:
        idx = next(ids)
        return thread_id if idx == 1 else f"{thread_id}-{idx:03d}"

    monkeypatch.setattr(
        _channels,
        "_new_id",
        _new_id,
    )

    def _discuss_result(agent_name: str, *_, **kwargs) -> Result:
        return Result(
            ok=True,
            agent=agent_name,
            model="test-model",
            mode=mode,
            response=f"{agent_name} reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=f"{agent}-session-2",
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    task_key = f"discuss:{thread_id}"
    if agent == "codex":
        _db.set_session(task_key, codex_session_id=f"{agent}-stored")
    else:
        _db.set_session(task_key, gemini_session_id=f"{agent}-stored")

    exit_code = _run_cli(
        ["discuss", channel, "topic", "--with", agent, "--max-rounds", "2"]
    )

    assert exit_code == 0
    observed_sessions = [call.kwargs["session_id"] for call in mock_invoke.call_args_list]
    if agent == "gemini":
        assert observed_sessions[0] is not None
    else:
        assert observed_sessions[0] is None
    assert observed_sessions[1] == f"{session_key}-session-2"
    assert (
        f"bridge: stored session for {agent}/{task_key} has no cwd; starting fresh"
        in capsys.readouterr().out
    )
    assert (
        _db.get_session(task_key)[f"{session_key}_session_id"] == f"{agent}-session-2"
    )


@pytest.mark.parametrize("agent,mode,session_key", [
    ("codex", "danger", "codex"),
    ("gemini", "read-only", "gemini"),
])
@patch("agent_runtime.runner.invoke")
def test_discuss_agent_resume_error_falls_back_to_fresh(
    mock_invoke,
    monkeypatch,
    tmp_path,
    capsys,
    agent: str,
    mode: str,
    session_key: str,
):
    channel = f"discuss-{agent}-resume-error"
    _channels.create_channel(channel)
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    thread_id = f"{channel}-root"
    ids = itertools.count(1)

    def _new_id() -> str:
        idx = next(ids)
        return thread_id if idx == 1 else f"{thread_id}-{idx:03d}"

    monkeypatch.setattr(
        _channels,
        "_new_id",
        _new_id,
    )

    attempts: list[str | None] = []

    def _discuss_result(agent_name: str, *_, **kwargs) -> Result:
        attempts.append(kwargs.get("session_id"))
        if kwargs.get("session_id") == f"{agent}-stored":
            raise RuntimeError("stored session invalid")
        return Result(
            ok=True,
            agent=agent_name,
            model="test-model",
            mode=mode,
            response=f"{agent_name} reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=f"{agent}-session-2",
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    task_key = f"discuss:{thread_id}"
    if agent == "codex":
        _db.set_session(
            task_key,
            codex_session_id=f"{agent}-stored",
            codex_cwd=str(tmp_path),
            codex_sandbox_mode=mode,
        )
    else:
        _db.set_session(
            task_key,
            gemini_session_id=f"{agent}-stored",
            gemini_cwd=str(tmp_path),
            gemini_sandbox_mode=mode,
        )

    exit_code = _run_cli(
        ["discuss", channel, "topic", "--with", agent, "--max-rounds", "2"]
    )

    assert exit_code == 0
    assert attempts[0] == f"{agent}-stored"
    if agent == "gemini":
        assert attempts[1] is not None
        assert attempts[1] != f"{agent}-stored"
    else:
        assert attempts[1] is None
    assert attempts[2] == f"{agent}-session-2"
    assert mock_invoke.call_count == 3
    captured = capsys.readouterr()
    assert (
        f"bridge: stored session {agent}-stored for {agent}/{task_key} "
        "failed: [error: RuntimeError: stored session invalid]; starting fresh"
        in captured.out
    )
    assert (
        _db.get_session(task_key)[f"{session_key}_session_id"] == f"{agent}-session-2"
    )


@patch("agent_runtime.runner.invoke")
def test_discuss_resume_rejects_missing_session(mock_invoke, monkeypatch, capsys):
    _channels.create_channel("resume-missing")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    first = True

    def _new_id() -> str:
        nonlocal first
        if first:
            first = False
            return "pre-tier2-thread"
        return f"pre-tier2-{next(ids):04d}"

    monkeypatch.setattr(
        _channels,
        "_new_id",
        _new_id,
    )
    _channels.post(
        "resume-missing",
        "user",
        "starting point",
        to_agents=["claude"],
        auto_snapshot=False,
    )

    exit_code = _run_cli(
        [
            "discuss",
            "resume-missing",
            "topic",
            "--with",
            "claude",
            "--resume-thread",
            "pre-tier2-thread",
            "--max-rounds",
            "2",
        ]
    )

    assert exit_code == 1
    assert "no resumable session" in capsys.readouterr().err
    assert mock_invoke.call_count == 0


@patch("agent_runtime.runner.invoke")
def test_discuss_resume_rejects_codex_only_session(mock_invoke, monkeypatch, capsys):
    _channels.create_channel("resume-codex-only")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(range(1, 1000))
    first = True

    def _new_id() -> str:
        nonlocal first
        if first:
            first = False
            return "codex-only-thread"
        return f"codex-only-{next(ids):04d}"

    monkeypatch.setattr(
        _channels,
        "_new_id",
        _new_id,
    )
    _channels.post(
        "resume-codex-only",
        "user",
        "starting point",
        to_agents=["claude"],
        auto_snapshot=False,
    )

    _db.set_session("discuss:codex-only-thread", codex_session_id="corrupt-codex-uuid")

    exit_code = _run_cli(
        [
            "discuss",
            "resume-codex-only",
            "topic",
            "--with",
            "claude",
            "--resume-thread",
            "codex-only-thread",
            "--max-rounds",
            "2",
        ]
    )

    assert exit_code == 1
    assert "no resumable session" in capsys.readouterr().err
    assert mock_invoke.call_count == 0


@patch("agent_runtime.runner.invoke")
def test_discuss_resume_reuses_thread_and_trace(
    mock_invoke,
    monkeypatch,
    tmp_path,
    capsys,
):
    _channels.create_channel("resume-threaded")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = iter(
        [
            "resumable-thread",
            "resumable-reply",
            "resumable-round1",
            "resumable-round2",
            "resumable-round3",
            "resumable-round4",
        ]
    )
    monkeypatch.setattr(
        _channels,
        "_new_id",
        lambda: next(ids),
    )
    _channels.post(
        "resume-threaded",
        "user",
        "starting point",
        to_agents=["claude"],
        auto_snapshot=False,
    )
    _db.set_session("discuss:resumable-thread", claude_session_id="claude-uuid")
    # Newer resume behavior requires cwd + sandbox metadata to resume.
    # Seed it explicitly so this case validates true session restore.
    _db.set_session(
        "discuss:resumable-thread",
        claude_cwd=str(tmp_path),
        claude_sandbox_mode="read-only",
    )

    seen_session_ids: list[str | None] = []

    def _discuss_result(agent: str, *_, **kwargs) -> Result:
        seen_session_ids.append(kwargs.get("session_id"))
        return Result(
            ok=True,
            agent=agent,
            model="test-model",
            mode="read-only",
            response="claude reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id="next-uuid",
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        [
            "discuss",
            "resume-threaded",
            "topic",
            "--with",
            "claude",
            "--resume-thread",
            "resumable-thread",
            "--max-rounds",
            "2",
        ]
    )

    assert exit_code == 0
    assert seen_session_ids[0] == "claude-uuid"
    captured = capsys.readouterr()
    assert "resuming thread resumable-th" in captured.out
    thread = _channels.read("resume-threaded", thread_id="resumable-thread")
    assert all(msg["thread_id"] == "resumable-thread" for msg in thread)
    assert mock_invoke.call_args_list[0].kwargs["task_id"].startswith(
        "discuss-resumabl-r1-claude"
    )


@patch("agent_runtime.runner.invoke")
def test_discuss_round1_round2_all_agents_persists_sessions_and_metadata(
    mock_invoke,
    monkeypatch,
):
    _channels.create_channel("discuss-warmresume")
    monkeypatch.setattr(_channels, "fetch_monitor_state", lambda: None)
    ids = itertools.count(1)
    monkeypatch.setattr(
        _channels,
        "_new_id",
        lambda: f"discuss-warmresume-{next(ids):04d}",
    )

    seen_calls: list[tuple[str, str | None]] = []
    attempts: dict[str, int] = {}

    def _discuss_result(agent_name: str, *_, **kwargs) -> Result:
        seen_calls.append((agent_name, kwargs.get("session_id")))
        attempts[agent_name] = attempts.get(agent_name, 0) + 1
        return Result(
            ok=True,
            agent=agent_name,
            model="test-model",
            mode="danger" if agent_name == "codex" else "read-only",
            response=f"{agent_name} reply [AGREE]",
            stderr_excerpt=None,
            duration_s=0.1,
            session_id=(
                kwargs.get("session_id") if agent_name == "codex" and kwargs.get("session_id")
                else f"{agent_name}-session-{attempts[agent_name]:02d}"
            ),
            rate_limited=False,
            stalled=False,
            returncode=0,
            usage_record={},
        )

    mock_invoke.side_effect = _discuss_result

    exit_code = _run_cli(
        [
            "discuss",
            "discuss-warmresume",
            "topic",
            "--with",
            "claude,codex,gemini",
            "--max-rounds",
            "2",
        ]
    )

    by_agent: dict[str, list[str | None]] = {
        "claude": [],
        "codex": [],
        "gemini": [],
    }
    for agent_name, session_id in seen_calls:
        by_agent[agent_name].append(session_id)

    assert exit_code == 0
    assert len(mock_invoke.call_args_list) == 6
    assert by_agent["claude"][0] is not None
    assert by_agent["codex"][0] is None
    assert by_agent["gemini"][0] is not None
    assert by_agent["claude"][1] == "claude-session-01"
    assert by_agent["codex"][1] == "codex-session-01"
    assert by_agent["gemini"][1] == "gemini-session-01"

    row = _db.get_session("discuss:discuss-warmresume-0001")
    assert row["claude_session_id"]
    assert row["claude_cwd"]
    assert row["claude_sandbox_mode"]
    assert row["gemini_session_id"]
    assert row["gemini_cwd"]
    assert row["gemini_sandbox_mode"]
    assert row["codex_session_id"] == "codex-session-01"
    assert row["codex_cwd"]
    assert row["codex_sandbox_mode"]


@patch("agent_runtime.runner.invoke")
def test_discuss_resume_rejects_typo_thread_id(mock_invoke, capsys):
    _channels.create_channel("resume-typo")
    exit_code = _run_cli(
        [
            "discuss",
            "resume-typo",
            "topic",
            "--with",
            "claude",
            "--resume-thread",
            "typo-thread",
            "--max-rounds",
            "2",
        ]
    )

    assert exit_code == 1
    assert mock_invoke.call_count == 0
    assert "not found in channel" in capsys.readouterr().err


def test_inbox_show_with_pending_and_failed(capsys):
    _channels.create_channel("topic")
    first = _channels.post("topic", "user", "first pending", to_agents=["claude"], auto_snapshot=False)
    second = _channels.post("topic", "user", "second pending", to_agents=["claude"], auto_snapshot=False)
    third = _channels.post("topic", "user", "third pending", to_agents=["claude"], auto_snapshot=False)
    failed = _channels.post("topic", "user", "failed message", to_agents=["claude"], auto_snapshot=False)
    _channels.mark_delivery(failed["delivery_ids"][0], "failed", error="boom")
    old_ts = (datetime.now(UTC) - timedelta(minutes=12)).isoformat()
    _set_message_created_at(str(first["message_id"]), old_ts)

    exit_code = _run_cli(["inbox", "show", "claude"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "pending:    3 (oldest 12m ago)" in captured.out
    assert "failed (last 24h): 1" in captured.out
    assert "[topic/" in captured.out
    assert 'user → "first pending"' in captured.out
    assert second["message_id"] != third["message_id"]


@patch("ai_agent_bridge._inbox.runtime_invoke")
def test_inbox_run_once_processes_one_thread(mock_invoke, capsys):
    first = _make_thread("claude", count=1)
    second = _make_thread("claude", count=1)
    mock_invoke.return_value = _ok_result("claude")

    exit_code = _run_cli(["inbox", "run", "claude", "--once"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "processed: 1 deliveries | 1 threads | 0 failed | duration:" in captured.out
    statuses = _delivery_statuses()
    assert statuses[0]["status"] == "delivered"
    assert statuses[1]["status"] == "pending"
    assert mock_invoke.call_count == 1
    assert first[0]["thread_id"] != second[0]["thread_id"]


@patch("ai_agent_bridge._inbox.runtime_invoke")
def test_sync_all_iterates_known_agents(mock_invoke, capsys):
    for agent in _channels.VALID_AGENTS:
        _make_thread(agent, channel=f"{agent}-topic", count=1)
    mock_invoke.side_effect = [_ok_result(agent) for agent in _channels.VALID_AGENTS]

    exit_code = _run_cli(["sync", "--all"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert mock_invoke.call_count == len(_channels.VALID_AGENTS)
    assert [call.args[0] for call in mock_invoke.call_args_list] == list(_channels.VALID_AGENTS)
    assert captured.out.count("processed: 1 deliveries | 1 threads | 0 failed | duration:") == len(
        _channels.VALID_AGENTS
    )


def test_backlog_banner_triggers_for_old_pending_delivery(monkeypatch, capsys):
    thread = _make_thread("codex", count=1)
    monkeypatch.setenv("AB_BACKLOG_WARN_HOURS", "2")
    old_ts = (datetime.now(UTC) - timedelta(hours=6, minutes=12)).isoformat()
    _set_message_created_at(str(thread[0]["message_id"]), old_ts)

    exit_code = _run_cli(["inbox", "show", "claude"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "⚠️  codex has 1 pending deliveries (oldest 6h12m)." in captured.err
    assert "Run 'ab inbox run codex' to drain." in captured.err


def test_backlog_banner_does_not_trigger_for_fresh_pending_delivery(monkeypatch, capsys):
    _make_thread("codex", count=1)
    monkeypatch.setenv("AB_BACKLOG_WARN_HOURS", "2")

    exit_code = _run_cli(["inbox", "show", "claude"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""


def test_get_db_adds_cwd_and_sandbox_columns_to_legacy_sessions(tmp_path: Path) -> None:
    db_file = tmp_path / "legacy-messages.db"
    created_at = datetime.now(UTC).isoformat()

    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE sessions (
            task_id TEXT PRIMARY KEY,
            claude_session_id TEXT,
            gemini_session_id TEXT,
            codex_session_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO sessions
            (task_id, claude_session_id, gemini_session_id, codex_session_id, created_at, updated_at)
        VALUES
            ('legacy-task', 'legacy-claude', 'legacy-gemini', 'legacy-codex', ?, ?)
        """,
        (created_at, created_at),
    )
    conn.commit()
    conn.close()

    with patch("ai_agent_bridge._config.DB_PATH", db_file), patch("ai_agent_bridge._db.DB_PATH", db_file):
        migrated = _db.get_db()
        try:
            columns = [
                row[1]
                for row in migrated.execute("PRAGMA table_info(sessions)").fetchall()
            ]
            assert "claude_cwd" in columns
            assert "claude_sandbox_mode" in columns
            assert "gemini_cwd" in columns
            assert "gemini_sandbox_mode" in columns
            assert "codex_cwd" in columns
            assert "codex_sandbox_mode" in columns

            row = _db.get_session("legacy-task")
            assert row["claude_session_id"] == "legacy-claude"
            assert row["gemini_session_id"] == "legacy-gemini"
            assert row["codex_session_id"] == "legacy-codex"
            assert row["claude_cwd"] is None
            assert row["gemini_cwd"] is None
            assert row["codex_cwd"] is None
        finally:
            migrated.close()
