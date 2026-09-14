"""Agy interaction: ask_agy and process_for_agy."""

from __future__ import annotations

import json
import os
import time

from agent_runtime import runner as agent_runner
from agent_runtime.errors import (
    AgentStalledError,
    AgentTimeoutError,
    AgentUnavailableError,
    RateLimitedError,
)
from agent_runtime.registry import get_agent_entry

from ._config import REPO_ROOT
from ._db import get_db
from ._messaging import acknowledge, send_message

_AGENT_NAME = "agy"
_AGENT_TITLE = "Agy"
_DEFAULT_BRIDGE_TIMEOUT_SECONDS = 900
_NO_TIMEOUT_BRIDGE_TIMEOUT_SECONDS = 24 * 60 * 60
_DEFAULT_MODEL = str(
    get_agent_entry(_AGENT_NAME)["default_model"] or "gemini-3.8-flash-high"
)
_TIMEOUT_ENV = "AGY_BRIDGE_TIMEOUT"


def _resolve_bridge_timeout(no_timeout: bool = False) -> int:
    """Resolve the hard timeout from CLI flag/env with a safe fallback."""
    if no_timeout:
        return _NO_TIMEOUT_BRIDGE_TIMEOUT_SECONDS

    raw = os.environ.get(_TIMEOUT_ENV)
    if raw is None:
        return _DEFAULT_BRIDGE_TIMEOUT_SECONDS

    value = raw.strip().lower()
    if value in {"0", "none", "off", "false", "no"}:
        return _NO_TIMEOUT_BRIDGE_TIMEOUT_SECONDS

    try:
        timeout = int(value)
    except ValueError:
        print(
            f"⚠️  Invalid {_TIMEOUT_ENV}={raw!r} "
            f"— falling back to {_DEFAULT_BRIDGE_TIMEOUT_SECONDS}s"
        )
        return _DEFAULT_BRIDGE_TIMEOUT_SECONDS

    if timeout <= 0:
        return _NO_TIMEOUT_BRIDGE_TIMEOUT_SECONDS
    return timeout


def ask_agy(
    content: str,
    task_id: str | None = None,
    msg_type: str = "query",
    data: str | None = None,
    new_session: bool = False,
    from_llm: str = "gemini",
    from_model: str | None = None,
    to_model: str | None = None,
    no_timeout: bool = False,
    review: bool = False,
):
    """Send a message to Agy and invoke it to process the message."""
    msg_id = send_message(
        content,
        task_id,
        msg_type,
        data,
        from_llm=from_llm,
        to_llm=_AGENT_NAME,
        from_model=from_model,
        to_model=to_model,
    )
    print(f"\n🚀 Invoking {_AGENT_TITLE} to process message #{msg_id}...")
    process_for_agy(msg_id, new_session, no_timeout, review=review)
    return msg_id


def process_for_agy(
    message_id: int,
    new_session: bool = False,
    no_timeout: bool = False,
    review: bool = False,
):
    """Read a message addressed to Agy, invoke the runtime, and reply."""
    msg = _fetch_message(message_id)
    if not msg:
        return

    _ = new_session  # The current Agy adapter starts fresh per bridge call.
    timeout_val = _resolve_bridge_timeout(no_timeout)
    model = _extract_target_model(msg) or _DEFAULT_MODEL
    prompt = _build_prompt(msg, review)

    print(f"📨 Message #{msg['id']}")
    print(f"   From: {msg['from']} → To: {msg['to']}")
    print(f"   Type: {msg['type']}")
    print(f"   Task: {msg['task_id'] or 'N/A'}")
    print(f"   Model: {model}")
    if timeout_val == _NO_TIMEOUT_BRIDGE_TIMEOUT_SECONDS:
        print("   Hard timeout: no-timeout requested (24h ceiling)")
    else:
        print(f"   Hard timeout: {timeout_val}s")

    max_retries = 3
    base_delay = 10
    
    for attempt in range(max_retries):
        try:
            result = agent_runner.invoke(
                _AGENT_NAME,
                prompt,
                mode="read-only",
                cwd=REPO_ROOT,
                model=model,
                task_id=msg["task_id"],
                session_id=None,
                tool_config=None,
                entrypoint="bridge",
                hard_timeout=timeout_val,
                stall_timeout=min(600, timeout_val),
            )
        except RateLimitedError as exc:
            if attempt < max_retries - 1:
                print(f"⚠️  {_AGENT_TITLE} rate limited ({exc}), retrying {attempt+1}/{max_retries}...")
                time.sleep(base_delay * (2 ** attempt))
                continue
            _handle_error(msg, message_id, f"{_AGENT_TITLE} rate limited: {exc}")
            return
        except AgentStalledError as exc:
            if attempt < max_retries - 1:
                print(f"⚠️  {_AGENT_TITLE} stalled ({exc}), retrying {attempt+1}/{max_retries}...")
                time.sleep(base_delay * (2 ** attempt))
                continue
            _handle_error(msg, message_id, f"{_AGENT_TITLE} stalled: {exc}")
            return
        except AgentTimeoutError as exc:
            if attempt < max_retries - 1:
                print(f"⚠️  {_AGENT_TITLE} hard timeout ({exc}), retrying {attempt+1}/{max_retries}...")
                time.sleep(base_delay * (2 ** attempt))
                continue
            _handle_error(msg, message_id, f"{_AGENT_TITLE} hard timeout: {exc}")
            return
        except AgentUnavailableError as exc:
            if attempt < max_retries - 1:
                print(f"⚠️  {_AGENT_TITLE} unavailable ({exc}), retrying {attempt+1}/{max_retries}...")
                time.sleep(base_delay * (2 ** attempt))
                continue
            _handle_error(msg, message_id, f"{_AGENT_TITLE} unavailable: {exc}")
            return

        if not result.ok or not result.response:
            err_text = result.stderr_excerpt or f"{_AGENT_TITLE} returned no final message"
            if attempt < max_retries - 1:
                print(f"⚠️  {_AGENT_TITLE} failed ({err_text}), retrying {attempt+1}/{max_retries}...")
                time.sleep(base_delay * (2 ** attempt))
                continue
            _handle_error(
                msg,
                message_id,
                err_text,
            )
            return
            
        break

    response = result.response

    print(f"\n✅ {_AGENT_TITLE} finished ({len(response)} chars)")
    reply_id = send_message(
        content=response,
        task_id=msg["task_id"],
        msg_type="response",
        from_llm=_AGENT_NAME,
        to_llm=msg["from"],
    )
    acknowledge(message_id)
    acknowledge(reply_id)


def _fetch_message(message_id: int) -> dict | None:
    """Fetch a message addressed to this agent from the database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, task_id, from_llm, to_llm, message_type, content, data, timestamp
        FROM messages
        WHERE id = ? AND to_llm = ?
        """,
        (message_id, _AGENT_NAME),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(
            f"❌ Message {message_id} not found or not addressed to {_AGENT_TITLE}"
        )
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
        return None
    model = payload.get("to_model")
    return str(model) if model else None


def _build_prompt(msg: dict, review: bool = False) -> str:
    """Build a direct one-shot bridge prompt."""
    prompt = f"""You are {_AGENT_TITLE}, receiving a message from {msg['from'].title()} via the message broker.

---
Task ID: {msg['task_id'] or 'none'}
Type: {msg['type']}
From: {msg['from']}

{msg['content']}
"""
    if msg["data"]:
        prompt += f"""
---
Attached data:
{msg['data']}
"""
    prompt += """

---

Standing rules for bridge Q&A:
- Respond directly. Be concise. This bridge is for quick questioning
  and short coordination, not long-running task execution.
- Do NOT use broker or MCP messaging tools to send your response.
  Output your response directly.
"""
    return _prepend_review_protocol(prompt, review)


def _prepend_review_protocol(prompt: str, review: bool) -> str:
    """Prepend docs/review-protocol.md when --review is requested."""
    if not review:
        return prompt
    prefix = (REPO_ROOT / "docs" / "review-protocol.md").read_text(
        encoding="utf-8"
    ).rstrip()
    return f"{prefix}\n\n{prompt}"


def _handle_error(msg: dict, message_id: int, reason: str) -> None:
    """Record an agent failure as an error response and acknowledge it."""
    print(f"\n❌ {_AGENT_TITLE} error for message #{message_id}: {reason}")
    reply_id = send_message(
        content=f"[{_AGENT_TITLE} error] {reason}",
        task_id=msg["task_id"],
        msg_type="error",
        from_llm=_AGENT_NAME,
        to_llm=msg["from"],
    )
    acknowledge(message_id)
    acknowledge(reply_id)
