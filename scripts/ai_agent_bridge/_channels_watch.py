"""Event persistence + watch command for channel-thread progress streams."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from typing import Any, TextIO

from ._db import get_db

VALID_CHANNEL_EVENTS = (
    "reply_started",
    "heartbeat",
    "model_cascade",
    "reply_complete",
    "delivery_delivered",
    "delivery_failed",
)
DEFAULT_WATCH_POLL_INTERVAL_S = 0.5


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _validate_event_name(event: str) -> None:
    if event not in VALID_CHANNEL_EVENTS:
        raise ValueError(
            f"unknown channel event '{event}'. Expected one of {VALID_CHANNEL_EVENTS}."
        )


def append_channel_event(
    event: str,
    *,
    thread_id: str,
    delivery_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ts: str | None = None,
) -> None:
    """Append one channel event row."""
    _validate_event_name(event)
    if not thread_id or not thread_id.strip():
        raise ValueError("thread_id is required")

    payload = payload or {}
    reserved = {"event", "thread_id", "ts"}
    overlap = reserved & payload.keys()
    if overlap:
        raise ValueError(
            f"channel event payload may not override reserved keys: {sorted(overlap)}"
        )

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO channel_events (delivery_id, thread_id, event, payload_json, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                delivery_id,
                thread_id,
                event,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ts or _now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def emit_reply_started(thread_id: str, *, agent: str, model: str | None) -> None:
    append_channel_event(
        "reply_started",
        thread_id=thread_id,
        payload={
            "agent": agent,
            "model": model or "",
        },
    )


def emit_heartbeat(
    thread_id: str,
    *,
    delivery_id: str,
    elapsed_s: int,
) -> None:
    append_channel_event(
        "heartbeat",
        thread_id=thread_id,
        delivery_id=delivery_id,
        payload={
            "delivery_id": delivery_id,
            "elapsed_s": elapsed_s,
        },
    )


def emit_model_cascade(
    thread_id: str,
    *,
    from_model: str,
    to_model: str,
    reason: str,
) -> None:
    append_channel_event(
        "model_cascade",
        thread_id=thread_id,
        payload={
            "from": from_model,
            "to": to_model,
            "reason": reason,
        },
    )


def emit_reply_complete(
    thread_id: str,
    *,
    agent: str,
    chars: int,
    body: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "agent": agent,
        "chars": chars,
    }
    if body is not None:
        payload["body"] = body
    append_channel_event(
        "reply_complete",
        thread_id=thread_id,
        payload=payload,
    )


def emit_delivery_delivered(thread_id: str, *, delivery_id: str) -> None:
    append_channel_event(
        "delivery_delivered",
        thread_id=thread_id,
        delivery_id=delivery_id,
        payload={"delivery_id": delivery_id},
    )


def emit_delivery_failed(
    thread_id: str,
    *,
    delivery_id: str,
    error_kind: str,
) -> None:
    append_channel_event(
        "delivery_failed",
        thread_id=thread_id,
        delivery_id=delivery_id,
        payload={
            "delivery_id": delivery_id,
            "error_kind": error_kind,
        },
    )


def read_channel_events(
    thread_id: str,
    *,
    after_event_id: int = 0,
) -> list[dict[str, Any]]:
    """Read channel events for one thread in append order."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT event_id, delivery_id, thread_id, event, payload_json, ts
            FROM channel_events
            WHERE thread_id = ? AND event_id > ?
            ORDER BY event_id ASC
            """,
            (thread_id, after_event_id),
        ).fetchall()
    finally:
        conn.close()

    events: list[dict[str, Any]] = []
    for row in rows:
        payload_raw = row["payload_json"]
        payload = json.loads(payload_raw) if payload_raw else {}
        event = {
            "event": row["event"],
            **payload,
            "thread_id": row["thread_id"],
            "ts": row["ts"],
            "_event_id": int(row["event_id"]),
        }
        events.append(event)
    return events


def _format_human_event(event: dict[str, Any]) -> str:
    ts = str(event["ts"])[:19]
    event_name = str(event["event"])
    payload = [
        f"{key}={value}"
        for key, value in event.items()
        if key not in {"event", "thread_id", "ts", "_event_id"}
    ]
    suffix = f" {' '.join(payload)}" if payload else ""
    return f"[{ts}] {event_name}{suffix}"


def _write_event(
    event: dict[str, Any],
    *,
    event_stream: bool,
    out: TextIO,
) -> None:
    if event_stream:
        payload = {key: value for key, value in event.items() if key != "_event_id"}
        out.write(json.dumps(payload, ensure_ascii=False) + "\n")
    else:
        out.write(_format_human_event(event) + "\n")
    out.flush()


def watch_channel_events(
    thread_id: str,
    *,
    follow: bool = False,
    event_stream: bool = False,
    poll_interval_s: float = DEFAULT_WATCH_POLL_INTERVAL_S,
    out: TextIO | None = None,
    max_events: int | None = None,
) -> int:
    """Replay and optionally follow channel events for one thread."""
    if not thread_id or not thread_id.strip():
        raise ValueError("thread_id is required")
    if poll_interval_s <= 0:
        raise ValueError("poll_interval_s must be > 0")

    writer = out or sys.stdout
    if writer is sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    emitted = 0
    last_event_id = 0
    try:
        while True:
            events = read_channel_events(thread_id, after_event_id=last_event_id)
            for event in events:
                _write_event(event, event_stream=event_stream, out=writer)
                emitted += 1
                last_event_id = max(last_event_id, int(event["_event_id"]))
                if max_events is not None and emitted >= max_events:
                    return 0

            if not follow:
                return 0

            time.sleep(poll_interval_s)
    except KeyboardInterrupt:
        return 0
