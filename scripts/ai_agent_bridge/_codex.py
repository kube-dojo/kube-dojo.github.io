"""Codex interaction: ask_codex and process_for_codex.

Legacy task messages may resume a session only within the same cwd and mode.
Discussion sessions have their own owner; delegate/dispatch remain fresh.
"""

import fcntl
import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from agent_runtime import runner as agent_runner
from agent_runtime.errors import (
    AgentStalledError,
    AgentTimeoutError,
    AgentUnavailableError,
    RateLimitedError,
)

from ._config import PID_DIR, REPO_ROOT
from ._db import get_db, get_session, set_session
from ._messaging import acknowledge, send_message
from ._prompts import build_codex_prompt

_LOGGER = logging.getLogger(__name__)


def _codex_bridge_mode() -> str:
    """Resolve Codex sandbox mode for ai_agent_bridge calls.

    Always returns "danger" — workspace-write and read-only both starve Codex
    of network/filesystem. CODEX_BRIDGE_MODE env var is ignored; callers that
    set it will see a warning on stderr.
    """
    env_val = os.environ.get("CODEX_BRIDGE_MODE") or os.environ.get("CODEX_CLI_MODE")
    if env_val and env_val.strip().lower() != "danger":
        print(
            f"WARNING: CODEX_BRIDGE_MODE='{env_val}' is ignored — "
            "Codex always runs in danger mode. Remove the env var.",
            flush=True,
            file=sys.stderr,
        )
    return "danger"


def _codex_bridge_runtime_mode() -> str:
    """Return the runtime mode for Codex bridge calls — always "danger"."""
    return _codex_bridge_mode()


def ask_codex(content: str, task_id: str | None = None, msg_type: str = "query",
              data: str | None = None, new_session: bool = False,
              from_llm: str = "gemini", from_model: str | None = None,
              to_model: str | None = None):
    """Send message to Codex AND invoke Codex to process it."""
    msg_id = send_message(content, task_id, msg_type, data, from_llm=from_llm,
                          to_llm="codex", from_model=from_model, to_model=to_model)
    print(f"\n🚀 Invoking Codex to process message #{msg_id}...")
    # Self-addressed messages are auto-acknowledged at insertion and never
    # enter the batch queue. This explicit ask still owns its new message.
    status = process_for_codex(msg_id, new_session, force=from_llm == "codex")
    if from_llm == "codex" and status in {"skipped", "deferred"}:
        print(f"Self-addressed request did not run. Retry explicitly: ab process-codex {msg_id} --force")
    return msg_id


def has_codex_headroom(model: str | None = None) -> tuple[bool, str]:
    """Return whether Codex has quota headroom for a new bridge call."""
    from agent_runtime.usage import has_headroom

    effective_model = model or "gpt-5.4"
    return has_headroom("codex", effective_model)


@contextmanager
def _codex_task_lock(task_key: str) -> Iterator[bool]:
    """Serialize a task across processes without interpreting its key as a path."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    lock_name = hashlib.sha256(task_key.encode()).hexdigest()
    # Retain the inode after unlocking: unlinking could let another process
    # acquire a new file while a waiter still holds the original inode.
    with (PID_DIR / f"codex-{lock_name}.lock").open("a") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def process_for_codex(
    message_id: int, new_session: bool = False, no_timeout: bool = False, *, force: bool = False,
) -> str:
    """Process a task message with scoped bridge-only resume, unless forced new."""
    msg = _fetch_codex_message(message_id)
    if not msg:
        return "skipped"

    task_key = (msg["task_id"] or "").strip()
    with _codex_task_lock(task_key or f"message:{message_id}") as acquired:
        if not acquired:
            print(f"⏸️  Codex task for message {message_id} is already being processed.")
            return "skipped"
        # Another caller may have finished after our initial fetch. Check
        # acknowledgment again while holding the task lock, before replaying.
        msg = _fetch_codex_message(message_id)
        if not msg or (msg["acknowledged"] and not force):
            print(f"⏭️  Codex message {message_id} is already acknowledged or unavailable.")
            return "skipped"
        # Discussions own their session rows even if a legacy message borrows
        # the task name. Never read or overwrite those sessions here.
        is_review = msg["type"] == "review"
        session_key = task_key if task_key and not task_key.startswith("discuss:") and not is_review else None
        return _process_codex_message(msg, message_id, session_key, new_session or is_review, no_timeout)


def _process_codex_message(
    msg: dict, message_id: int, task_key: str | None, new_session: bool, no_timeout: bool,
) -> str:
    timeout_val = 1800 if no_timeout else 900  # runner has its own hard_timeout
    try:
        model = _extract_target_model(msg)
    except (ValueError, TypeError):
        _handle_codex_error(msg, message_id, "Invalid target model identifier")
        return "failed"
    has_room, reason = has_codex_headroom(model)
    if not has_room:
        _handle_codex_rate_limited(msg, message_id, reason)
        return "deferred"

    cwd = REPO_ROOT.resolve()
    mode = _codex_bridge_runtime_mode()
    session_id = None
    stored = get_session(task_key) if task_key else {}
    stored_cwd = stored.get("codex_cwd")
    if (
        not new_session
        and stored.get("codex_session_id")
        and stored_cwd
        and stored.get("codex_sandbox_mode") == mode
        and Path(stored_cwd).is_dir()
        and Path(stored_cwd).resolve() == cwd
    ):
        session_id = stored["codex_session_id"]

    def clear_session() -> None:
        if task_key:
            # set_session ignores None, so explicit empty strings invalidate
            # the ID and its scope atomically, including on a failed fresh run.
            set_session(task_key, codex_session_id="", codex_cwd="", codex_sandbox_mode="")
            if session_id:
                print("Saved Codex session cleared; the next call will start fresh.")

    if session_id is None:
        clear_session()

    prompt = build_codex_prompt(msg)

    print(f"📨 Message #{msg['id']}")
    print(f"   From: {msg['from']} → To: {msg['to']}")
    print(f"   Type: {msg['type']}")
    print(f"   Task: {msg['task_id'] or 'N/A'}")
    print(f"   Session: {session_id[:8] + '...' if session_id else 'NEW'}")

    try:
        result = agent_runner.invoke(
            "codex",
            prompt,
            mode=mode,
            cwd=cwd,
            model=model,
            task_id=msg["task_id"],
            session_id=session_id,
            tool_config=None,
            entrypoint="bridge",
            hard_timeout=timeout_val,
            # The runner watches this invocation's output and stderr;
            # the hard timeout bounds calls that do not finish.
            stall_timeout=min(600, timeout_val),
        )
    except RateLimitedError as exc:
        _handle_codex_rate_limited(msg, message_id, f"Rate limited: {exc}")
        return "deferred"
    except AgentStalledError as exc:
        clear_session()
        _handle_codex_error(msg, message_id, f"Codex stalled: {exc}")
        return "failed"
    except AgentTimeoutError as exc:
        clear_session()
        _handle_codex_error(msg, message_id, f"Codex hard timeout: {exc}")
        return "failed"
    except AgentUnavailableError as exc:
        clear_session()
        _handle_codex_error(msg, message_id, f"Codex unavailable: {exc}")
        return "failed"
    except Exception:
        clear_session()
        _LOGGER.exception("Codex bridge runtime invocation failed")
        raise

    if not result.ok:
        if getattr(result, "rate_limited", False):
            _handle_codex_rate_limited(msg, message_id, result.stderr_excerpt or "Rate limited")
            return "deferred"
        clear_session()
        _handle_codex_error(
            msg,
            message_id,
            result.stderr_excerpt or "Codex returned no final message",
        )
        return "failed"

    response = result.response
    if not response:
        clear_session()
        _handle_codex_error(msg, message_id, "Codex returned no final message")
        return "failed"

    # The adapter explicitly passes -m on both paths; model selection remains
    # per-call. Session continuity is scoped by task, cwd, and sandbox mode.
    if session_id and result.session_id and result.session_id != session_id:
        _LOGGER.warning("Codex session identity changed; clearing the saved session")
        clear_session()
        _handle_codex_error(msg, message_id, "Session identity changed; saved session cleared. This call was not retried.")
        return "failed"
    returned_session_id = session_id or result.session_id
    if task_key and returned_session_id:
        set_session(
            task_key, "codex", returned_session_id,
            codex_cwd=str(cwd), codex_sandbox_mode=mode,
        )

    print(f"\n✅ Codex finished ({len(response)} chars)")
    reply_id = send_message(
        content=response,
        task_id=msg["task_id"],
        msg_type="response",
        from_llm="codex",
        to_llm=msg["from"],
    )
    acknowledge(message_id)
    acknowledge(reply_id)
    return "done"


def _fetch_codex_message(message_id: int) -> dict | None:
    """Fetch a message addressed to Codex from the database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_id, from_llm, to_llm, message_type, content, data, timestamp, acknowledged
        FROM messages
        WHERE id = ? AND to_llm = 'codex'
    """, (message_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"❌ Message {message_id} not found or not addressed to Codex")
        return None

    return {
        "id": row[0],
        "task_id": row[1],
        "from": row[2],
        "to": row[3],
        "type": row[4],
        "content": row[5],
        "data": row[6],
        "timestamp": row[7],
        "acknowledged": bool(row[8]),
    }


def _extract_target_model(msg: dict) -> str | None:
    """Read optional to_model from message metadata JSON."""
    data = msg.get("data")
    if not data:
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        raise TypeError("Invalid message metadata")
    model = payload.get("to_model")
    if model is not None:
        if not isinstance(model, str):
            raise TypeError("Invalid target model identifier")
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", model):
            raise ValueError("Invalid target model identifier")
    return model


def _handle_codex_error(msg: dict, message_id: int, error_msg: str) -> None:
    """Send bridge error back to sender."""
    print(f"\n❌ Codex CLI error: {error_msg[:500]}")
    err_id = send_message(
        content=f"[Bridge Error] Codex CLI failed:\n{error_msg[:500]}",
        task_id=msg["task_id"],
        msg_type="error",
        from_llm="codex",
        to_llm=msg["from"],
        from_model="codex-bridge-error",
    )
    acknowledge(message_id)
    acknowledge(err_id)


def _handle_codex_rate_limited(msg: dict, message_id: int, reason: str) -> None:
    """Defer a rate-limited message without acknowledging the inbound row."""
    print(f"\n⛔ Codex rate limited - message {message_id} deferred")
    print(f"   Reason: {reason}")
    retry_hint = (
        f"This self-addressed message is already acknowledged. Once headroom returns, "
        f"retry explicitly: ab process-codex {message_id} --force"
        if msg["from"] == "codex" else
        f"The incoming message (id={message_id}) remains in Codex's inbox and will be retried "
        "automatically when headroom returns. Sender should NOT retry manually."
    )
    err_id = send_message(
        content=(
            "[Codex rate limited] Usage limit hit.\n"
            f"Reason: {reason}\n\n"
            f"{retry_hint}"
        ),
        task_id=msg["task_id"],
        msg_type="error",
        from_llm="codex",
        to_llm=msg["from"],
        from_model="codex-bridge-rate-limited",
    )
    acknowledge(err_id)


def process_all_codex(new_session: bool = False):
    """Process ALL unread messages for Codex in batch."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_id, from_llm, message_type, substr(content, 1, 50)
        FROM messages
        WHERE to_llm = 'codex' AND acknowledged = 0
        ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("📭 No unread messages for Codex to process")
        return

    print(f"📬 Processing {len(rows)} unread message(s) for Codex...\n")
    counts = {"done": 0, "failed": 0, "skipped": 0, "deferred": 0}

    for row in rows:
        msg_id, _task_id, from_llm, _msg_type, preview = row
        preview = preview.replace("\n", " ")[:40]
        print(f"━━━ Processing [{msg_id}] from {from_llm}: {preview}...")
        try:
            status = process_for_codex(msg_id, new_session)
            counts[status] += 1
            print(f"    {status}\n")
        except Exception as e:
            _LOGGER.exception("Codex bridge batch message failed")
            counts["failed"] += 1
            print(f"    ❌ Failed: {e}\n")

    print(f"\n{'═' * 50}")
    print(
        f"📊 Results: {counts['done']} succeeded, {counts['failed']} failed, "
        f"{counts['skipped']} skipped, {counts['deferred']} deferred out of {len(rows)} total"
    )
