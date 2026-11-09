from __future__ import annotations

import html as _html
import json as _json
import logging as _logging
import os as _os
import re as _re
import threading as _threading
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote

try:
    from local_api.routes.decisions import _is_decision_card
    from local_api.routes.ui_fragments import (
        AFK_NOTIFY_CSS,
        render_afk_notify_markup,
        render_search_widget,
    )
except ModuleNotFoundError:
    from scripts.local_api.routes.decisions import _is_decision_card
    from scripts.local_api.routes.ui_fragments import (
        AFK_NOTIFY_CSS,
        render_afk_notify_markup,
        render_search_widget,
    )


RouteResponse = tuple[int, Any, str]
_LOG = _logging.getLogger(__name__)
_POST_DB_LOCK = _threading.Lock()
_VOTE_RE = _re.compile(r"\[(AGREE|OPTION [A-Z][\w'’′‘]?|DEFER|NEEDS[- ]CHANGES)\]")


def _int_from_env(name: str, default: int) -> int:
    try:
        return int(_os.environ.get(name, str(default)))
    except ValueError:
        return default


_SUPPLEMENTARY_EVENTS_LIMIT = _int_from_env("KUBEDOJO_CHANNEL_EVENTS_LIMIT", 10000)


def _json_response(status: int, payload: dict[str, Any]) -> RouteResponse:
    return status, payload, "application/json; charset=utf-8"


def _safe_json_for_script(value: Any) -> str:
    return (
        _json.dumps(value)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _channel_event_sort_key(channel: dict[str, Any]) -> str:
    value = channel.get("last_event_ts") or channel.get("created_at") or ""
    return str(value)


def extract_thread_vote(body: str) -> str | None:
    """Return a protocol vote from the final non-empty line only.

    ``[DISAGREE]`` is intentionally not a protocol token. Count only
    ``[AGREE]``, ``[OPTION X]`` variants, ``[DEFER]``, and
    ``[NEEDS CHANGES]`` / ``[NEEDS-CHANGES]``.
    """
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return None
    matches = _VOTE_RE.findall(lines[-1])
    return matches[-1] if matches else None


def _float_from_payload(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key, 0)
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _thread_status(rounds: list[dict[str, Any]]) -> str:
    if not rounds:
        return "in_flight"
    final_turns = rounds[-1]["turns"]
    final_votes = [
        str(turn.get("vote"))
        for turn in final_turns
        if isinstance(turn.get("vote"), str)
    ]
    if (
        final_votes
        and len(final_votes) == len(final_turns)
        and all(vote == "AGREE" for vote in final_votes)
    ):
        return "converged"
    option_votes = {
        vote
        for vote in final_votes
        if vote.startswith("OPTION ")
    }
    if len(option_votes) >= 2:
        return "diverged"
    return "in_flight"


def _default_view_for_summary(summary: dict[str, Any]) -> str:
    if summary.get("status") == "converged" or summary.get("decision_id"):
        return "graph"
    return "chat"


def _decision_frontmatter_or_first_section(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    if lines[0].strip() == "---":
        for idx, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[: idx + 1])
        return "\n".join(lines[:80])
    section: list[str] = []
    saw_h1 = False
    for line in lines:
        if line.startswith("# "):
            if saw_h1:
                break
            saw_h1 = True
        elif saw_h1 and line.startswith("## "):
            break
        section.append(line)
    return "\n".join(section or lines[:20])


def find_decision_id_for_thread(repo_root: Path, thread_id: str) -> str | None:
    decisions_dir = repo_root / "docs" / "decisions"
    if not thread_id or not decisions_dir.exists():
        return None
    decision_paths = [
        path
        for pattern in ("*.md", "pending/*.md")
        for path in sorted(decisions_dir.glob(pattern))
        if _is_decision_card(path)
    ]
    for path in decision_paths:
        if thread_id in _decision_frontmatter_or_first_section(path):
            return path.relative_to(decisions_dir).as_posix()
    return None


def _finalize_channel_rollup(
    channels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    for channel in channels.values():
        threads = channel.get("threads")
        if not isinstance(threads, list):
            threads = []
            channel["threads"] = threads
        channel["thread_count"] = len(threads)
        channel["message_count"] = sum(
            int(thread.get("message_count") or 0)
            for thread in threads
            if isinstance(thread, dict)
        )
        channel["event_count"] = sum(
            int(thread.get("event_count") or 0)
            for thread in threads
            if isinstance(thread, dict)
        )
        channel["last_event_ts"] = max(
            (
                str(thread.get("last_event_ts") or "")
                for thread in threads
                if isinstance(thread, dict)
            ),
            default=channel.get("created_at") or "",
        )
    return {
        "channels": sorted(
            channels.values(),
            key=_channel_event_sort_key,
            reverse=True,
        )
    }


def build_channel_threads_index(
    repo_root: Path,
    *,
    list_channels_fn: Callable[[], list[dict[str, Any]]],
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build deliberation thread rollups from ``channel_messages``.

    ``channel_messages`` is the transcript source of truth. ``channel_events``
    is optional metadata for progress state and visualization hints.
    """
    db_path = resolve_bridge_db_path_fn(repo_root)
    channels_raw = list_channels_fn()

    channels: dict[str, dict[str, Any]] = {
        channel["name"]: {
            "name": channel["name"],
            "created_at": channel.get("created_at"),
            "threads": [],
        }
        for channel in channels_raw
        if isinstance(channel, dict)
    }

    thread_rows = query_sqlite_rows_fn(
        db_path,
        """
        SELECT
          cm.channel AS channel,
          cm.thread_id AS thread_id,
          MIN(cm.created_at) AS thread_started_at,
          MAX(cm.created_at) AS thread_last_at,
          COUNT(*) AS message_count,
          (
            SELECT substr(cm2.body, 1, 80)
            FROM channel_messages cm2
            WHERE cm2.channel = cm.channel
              AND cm2.thread_id = cm.thread_id
            ORDER BY cm2.rowid ASC
            LIMIT 1
          ) AS subject
        FROM channel_messages cm
        GROUP BY cm.channel, cm.thread_id
        ORDER BY cm.channel ASC, MAX(cm.created_at) DESC
        """,
    )

    thread_index: dict[tuple[str, str], dict[str, Any]] = {}
    thread_keys_by_id: dict[str, list[tuple[str, str]]] = {}
    for row in thread_rows:
        channel = row.get("channel")
        thread_id = row.get("thread_id")
        if not isinstance(channel, str) or not isinstance(thread_id, str):
            continue
        thread_started_at = row.get("thread_started_at")
        thread_last_at = row.get("thread_last_at")
        thread_entry = {
            "thread_id": thread_id,
            "subject": (row.get("subject") or "").strip(),
            "thread_started_at": thread_started_at,
            "thread_last_at": thread_last_at,
            "message_count": int(row.get("message_count") or 0),
            "first_event_ts": None,
            "last_event_ts": thread_last_at,
            "event_count": 0,
            "agents": [],
            "model_cascades": [],
            "reply_state": None,
            "vote_counts": {
                "agree": 0,
                "defer": 0,
                "options": {},
            },
        }
        thread_key = (channel, thread_id)
        thread_index[thread_key] = thread_entry
        thread_keys_by_id.setdefault(thread_id, []).append(thread_key)
        entry = channels.setdefault(
            channel,
            {"name": channel, "created_at": None, "threads": []},
        )
        entry["threads"].append(thread_entry)

    if thread_index:
        event_rows = query_sqlite_rows_fn(
            db_path,
            """
            SELECT event_id, thread_id, event, payload_json, ts
            FROM channel_events
            ORDER BY event_id ASC
            """,
            # The progress stream is supplementary to channel_messages; this
            # high cap keeps busy deliberations enriched without paginating.
            limit=_SUPPLEMENTARY_EVENTS_LIMIT,
        )
        if len(event_rows) >= _SUPPLEMENTARY_EVENTS_LIMIT:
            _LOG.warning(
                "channel events query hit limit (%d rows); raise "
                "KUBEDOJO_CHANNEL_EVENTS_LIMIT to see more",
                _SUPPLEMENTARY_EVENTS_LIMIT,
            )
        agents_by_thread: dict[str, set[str]] = {}
        latest_reply_state: dict[str, tuple[int, dict[str, Any]]] = {}
        for event_row in event_rows:
            thread_id = event_row.get("thread_id")
            if not isinstance(thread_id, str) or thread_id not in thread_keys_by_id:
                continue
            entries = [
                thread_index[thread_key]
                for thread_key in thread_keys_by_id[thread_id]
            ]
            ts = event_row.get("ts")
            for entry in entries:
                entry["first_event_ts"] = entry["first_event_ts"] or ts
                entry["last_event_ts"] = ts or entry["last_event_ts"]
                entry["event_count"] += 1

            payload_raw = event_row.get("payload_json")
            try:
                payload = _json.loads(payload_raw) if payload_raw else {}
            except _json.JSONDecodeError:
                payload = {}
            event = event_row.get("event")
            event_id = int(event_row.get("event_id") or 0)

            if event == "reply_started":
                agent = payload.get("agent")
                if isinstance(agent, str):
                    agents_by_thread.setdefault(thread_id, set()).add(agent)
                latest_reply_state[thread_id] = (
                    event_id,
                    {"event": event, "ts": ts, **payload},
                )
            elif event == "reply_complete":
                agent = payload.get("agent")
                if isinstance(agent, str):
                    agents_by_thread.setdefault(thread_id, set()).add(agent)
                latest_reply_state[thread_id] = (
                    event_id,
                    {"event": event, "ts": ts, **payload},
                )
                body = payload.get("body")
                if isinstance(body, str):
                    for entry in entries:
                        entry["vote_counts"]["agree"] += len(
                            _re.findall(r"\[AGREE\]", body)
                        )
                        entry["vote_counts"]["defer"] += len(
                            _re.findall(r"\[DEFER\]", body)
                        )
                        options = entry["vote_counts"]["options"]
                        for match in _re.findall(r"\[OPTION ([A-Z0-9]+)\]", body):
                            options[match] = int(options.get(match, 0)) + 1
            elif event == "model_cascade":
                for entry in entries:
                    entry["model_cascades"].append({"ts": ts, **payload})

        for thread_id, agents in agents_by_thread.items():
            for thread_key in thread_keys_by_id.get(thread_id, []):
                thread_index[thread_key]["agents"] = sorted(agents)
        for thread_id, (_, state) in latest_reply_state.items():
            for thread_key in thread_keys_by_id.get(thread_id, []):
                thread_index[thread_key]["reply_state"] = state
        return _finalize_channel_rollup(channels)

    # Legacy fallback for event-only databases created before channel_messages
    # existed. New rollups never depend on this path.
    fallback_threads = query_sqlite_rows_fn(
        db_path,
        """
        SELECT
          thread_id,
          MIN(ts) AS first_event_ts,
          MAX(ts) AS last_event_ts,
          COUNT(event_id) AS event_count
        FROM channel_events
        GROUP BY thread_id
        ORDER BY thread_id
        """,
    )
    if not fallback_threads:
        return _finalize_channel_rollup(channels)

    threads: list[dict[str, Any]] = []
    for row in fallback_threads:
        thread_id = row.get("thread_id")
        if not isinstance(thread_id, str):
            continue
        threads.append({
            "thread_id": thread_id,
            "subject": None,
            "thread_started_at": None,
            "thread_last_at": None,
            "message_count": None,
            "first_event_ts": row.get("first_event_ts"),
            "last_event_ts": row.get("last_event_ts"),
            "event_count": int(row.get("event_count") or 0),
            "agents": [
                agent_row["agent"]
                for agent_row in query_sqlite_rows_fn(
                    db_path,
                    """
                    SELECT DISTINCT json_extract(payload_json, '$.agent') AS agent
                    FROM channel_events
                    WHERE thread_id = ?
                      AND event = 'reply_started'
                      AND json_extract(payload_json, '$.agent') IS NOT NULL
                    ORDER BY agent ASC
                    """,
                    (thread_id,),
                )
                if isinstance(agent_row.get("agent"), str)
            ],
            "model_cascades": None,
            "reply_state": None,
            "vote_counts": None,
        })

    return _finalize_channel_rollup(
        {
            "all-threads": {
                "name": "all-threads",
                "created_at": None,
                "threads": threads,
            }
        }
    )


def build_channel_events_payload(
    thread_id: str,
    read_channel_events_fn: Callable[..., list[dict[str, Any]]],
    since_event_id: int = 0,
) -> dict[str, Any]:
    events_raw = read_channel_events_fn(thread_id, after_event_id=since_event_id)
    events: list[dict[str, Any]] = []
    next_since_event_id = since_event_id

    for event in events_raw:
        event_id = int(event.get("_event_id", 0))
        payload = dict(event)
        payload.pop("_event_id", None)
        payload.pop("thread_id", None)
        payload["event_id"] = event_id
        events.append(payload)
        next_since_event_id = max(next_since_event_id, event_id)

    return {
        "thread_id": thread_id,
        "events": events,
        "next_since_event_id": next_since_event_id,
    }


def build_channel_thread_summary(
    repo_root: Path,
    thread_id: str,
    *,
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    db_path = resolve_bridge_db_path_fn(repo_root)
    rows = query_sqlite_rows_fn(
        db_path,
        """
        SELECT
          cm.message_id,
          cm.channel,
          cm.thread_id,
          cm.round_index,
          cm.from_agent,
          cm.from_model,
          cm.body,
          cm.created_at,
          mc.cost_usd AS cascade_cost_usd,
          mc.elapsed_s AS cascade_elapsed_s
        FROM channel_messages cm
        LEFT JOIN (
          SELECT
            thread_id,
            json_extract(payload_json, '$.message_id') AS message_id,
            SUM(COALESCE(json_extract(payload_json, '$.cost_usd'), 0)) AS cost_usd,
            SUM(COALESCE(json_extract(payload_json, '$.elapsed_s'), 0)) AS elapsed_s
          FROM channel_events
          WHERE event = 'model_cascade'
            AND json_extract(payload_json, '$.message_id') IS NOT NULL
          GROUP BY thread_id, json_extract(payload_json, '$.message_id')
        ) mc
          ON mc.thread_id = cm.thread_id
         AND mc.message_id = cm.message_id
        WHERE cm.thread_id = ?
        ORDER BY cm.round_index ASC, cm.created_at ASC, cm.rowid ASC
        """,
        (thread_id,),
        limit=_SUPPLEMENTARY_EVENTS_LIMIT,
    )

    channel = ""
    subject = ""
    turns_by_round_idx: dict[int, list[dict[str, Any]]] = {}
    total_cost_usd = 0.0
    total_elapsed_s = 0.0

    for row in rows:
        if not channel and isinstance(row.get("channel"), str):
            channel = str(row["channel"])
        body = row.get("body") if isinstance(row.get("body"), str) else ""
        if not subject:
            subject = body.strip()[:200]

        agent = row.get("from_agent")
        if not isinstance(agent, str) or agent == "user":
            continue

        cost_usd = _float_from_payload({"cost_usd": row.get("cascade_cost_usd")}, "cost_usd")
        elapsed_s = _float_from_payload({"elapsed_s": row.get("cascade_elapsed_s")}, "elapsed_s")
        total_cost_usd += cost_usd
        total_elapsed_s += elapsed_s

        turns_by_round_idx.setdefault(int(row.get("round_index") or 0), []).append(
            {
                "agent": agent,
                "model": row.get("from_model"),
                "vote": extract_thread_vote(body),
                "body_preview": body[:200],
                "body": body,
                "message_id": row.get("message_id"),
                "cost_usd": cost_usd,
                "elapsed_s": elapsed_s,
                "ts": row.get("created_at"),
            }
        )

    rounds: list[dict[str, Any]] = []

    def append_round(turns: list[dict[str, Any]]) -> None:
        rounds.append(
            {
                "round_idx": len(rounds) + 1,
                "turns": turns,
                "cost_usd": round(
                    sum(float(turn.get("cost_usd") or 0) for turn in turns),
                    6,
                ),
                "elapsed_s": round(
                    sum(float(turn.get("elapsed_s") or 0) for turn in turns),
                    3,
                ),
            }
        )

    for round_idx in sorted(turns_by_round_idx):
        current_turns: list[dict[str, Any]] = []
        seen_agents: set[str] = set()
        for turn in turns_by_round_idx[round_idx]:
            agent = str(turn.get("agent") or "")
            if agent in seen_agents and current_turns:
                append_round(current_turns)
                current_turns = []
                seen_agents = set()
            current_turns.append(turn)
            seen_agents.add(agent)
        if current_turns:
            append_round(current_turns)

    return {
        "thread_id": thread_id,
        "channel": channel,
        "subject": subject,
        "rounds": rounds,
        "status": _thread_status(rounds),
        "decision_id": find_decision_id_for_thread(repo_root, thread_id),
        "total_cost_usd": round(total_cost_usd, 6),
        "total_elapsed_s": round(total_elapsed_s, 3),
    }


def build_channel_timeline_payload(
    repo_root: Path,
    channel_name: str,
    *,
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
    since_event_id: int = 0,
    since_ts: str | None = None,
    since_message_rowid: int = 0,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Return progress events plus transcript rows from ``channel_messages``.

    Progress stays in ``channel_events``. The chat transcript is the message
    table, so a post with no progress event still appears. Messages already
    linked from an event payload are not repeated.
    """
    db_path = resolve_bridge_db_path_fn(repo_root)
    if thread_id:
        channel_rows = query_sqlite_rows_fn(
            db_path,
            """
            SELECT channel
            FROM channel_messages
            WHERE thread_id = ?
            ORDER BY round_index ASC, created_at ASC, rowid ASC
            LIMIT 1
            """,
            (thread_id,),
            limit=1,
        )
        if channel_rows and isinstance(channel_rows[0].get("channel"), str):
            channel_name = channel_rows[0]["channel"]
        scope_clause = """
        ce.thread_id = ?
        AND EXISTS (
          SELECT 1
          FROM channel_messages cm
          WHERE cm.thread_id = ce.thread_id
        )
        """
        params: list[Any] = [thread_id, since_event_id]
    else:
        scope_clause = """
        EXISTS (
          SELECT 1
          FROM channel_messages cm
          WHERE cm.channel = ?
            AND cm.thread_id = ce.thread_id
        )
        """
        params = [channel_name, since_event_id]
    since_clause = ""
    if since_ts:
        since_clause = "AND ce.ts > ?"
        params.append(since_ts)

    rows = query_sqlite_rows_fn(
        db_path,
        f"""
        SELECT
          ce.event_id,
          ce.delivery_id,
          ce.thread_id,
          ce.event,
          ce.payload_json,
          ce.ts,
          posted.message_id AS message_id,
          posted.from_agent AS message_from_agent,
          posted.from_model AS message_from_model,
          posted.kind AS message_kind,
          posted.body AS message_body,
          posted.created_at AS message_created_at
        FROM channel_events ce
        LEFT JOIN channel_messages posted
          ON posted.message_id = json_extract(ce.payload_json, '$.message_id')
        WHERE {scope_clause}
          AND ce.event_id > ?
          {since_clause}
        ORDER BY ce.event_id ASC
        """,
        tuple(params),
        limit=_SUPPLEMENTARY_EVENTS_LIMIT,
    )

    events: list[dict[str, Any]] = []
    next_since_event_id = since_event_id
    for row in rows:
        event_id = int(row.get("event_id") or 0)
        payload_raw = row.get("payload_json")
        try:
            payload = _json.loads(payload_raw) if payload_raw else {}
        except _json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        event = {
            "event_id": event_id,
            "delivery_id": row.get("delivery_id"),
            "thread_id": row.get("thread_id"),
            "event": row.get("event"),
            "ts": row.get("ts"),
            **payload,
        }
        if row.get("message_id"):
            event.update(
                {
                    "message_id": row.get("message_id"),
                    "from_agent": row.get("message_from_agent"),
                    "from_model": row.get("message_from_model"),
                    "kind": row.get("message_kind"),
                    "body": row.get("message_body"),
                    "created_at": row.get("message_created_at"),
                }
            )
        events.append(event)
        next_since_event_id = max(next_since_event_id, event_id)

    if thread_id:
        message_scope = "cm.thread_id = ?"
        message_params: list[Any] = [thread_id, since_message_rowid]
    else:
        message_scope = "cm.channel = ?"
        message_params = [channel_name, since_message_rowid]
    message_since = ""
    if since_ts:
        message_since = "AND cm.created_at > ?"
        message_params.append(since_ts)
    message_rows = query_sqlite_rows_fn(
        db_path,
        f"""
        SELECT
          cm.rowid AS message_rowid,
          cm.message_id,
          cm.thread_id,
          cm.from_agent,
          cm.from_model,
          cm.kind,
          cm.body,
          cm.created_at,
          EXISTS (
            SELECT 1 FROM channel_events ce
            WHERE json_extract(ce.payload_json, '$.message_id') = cm.message_id
          ) AS linked
        FROM channel_messages cm
        WHERE {message_scope}
          AND cm.rowid > ?
          {message_since}
        ORDER BY cm.rowid ASC
        """,
        tuple(message_params),
        limit=_SUPPLEMENTARY_EVENTS_LIMIT,
    )
    next_since_message_rowid = since_message_rowid
    for row in message_rows:
        rowid = int(row.get("message_rowid") or 0)
        next_since_message_rowid = max(next_since_message_rowid, rowid)
        if row.get("linked"):
            continue
        created_at = row.get("created_at")
        events.append(
            {
                "event": "transcript",
                "message_rowid": rowid,
                "message_id": row.get("message_id"),
                "thread_id": row.get("thread_id"),
                "from_agent": row.get("from_agent"),
                "from_model": row.get("from_model"),
                "kind": row.get("kind"),
                "body": row.get("body"),
                "created_at": created_at,
                "ts": created_at,
            }
        )
    events.sort(
        key=lambda item: (
            str(item.get("ts") or ""),
            0 if item.get("event") == "transcript" else 1,
        )
    )

    return {
        "channel": channel_name,
        "thread_id": thread_id,
        "events": events,
        "count": len(events),
        "next_since_event_id": next_since_event_id,
        "next_since_message_rowid": next_since_message_rowid,
    }


def channel_exists_in_db(
    repo_root: Path,
    channel_name: str,
    *,
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
) -> bool:
    rows = query_sqlite_rows_fn(
        resolve_bridge_db_path_fn(repo_root),
        "SELECT 1 AS found FROM channels WHERE name = ? LIMIT 1",
        (channel_name,),
    )
    return bool(rows)


def thread_exists_in_db(
    repo_root: Path,
    thread_id: str,
    *,
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
) -> bool:
    rows = query_sqlite_rows_fn(
        resolve_bridge_db_path_fn(repo_root),
        "SELECT 1 AS found FROM channel_messages WHERE thread_id = ? LIMIT 1",
        (thread_id,),
    )
    return bool(rows)


def render_channels_chat_html(
    selected_channel: str | None,
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
    default_view: str = "chat",
) -> str:
    selected_js = _safe_json_for_script(selected_channel)
    title_channel = selected_channel or "Channels"
    escaped_title = _html.escape(title_channel, quote=True)
    escaped_default_view = _html.escape(default_view, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title} - Agent Deliberations</title>
  <style>
    :root{{--bg:#101112;--panel:#17191b;--panel-2:#202326;--line:#30343a;--text:#f3f4f2;--muted:#9ca3a3;--teal:#3dd6c6;--orange:#f59e0b;--blue:#69a7ff;--green:#55d17f;--violet:#b99cff;--red:#fb7185;--topnav-h:45px}}
    *{{box-sizing:border-box;margin:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);line-height:1.45;-webkit-font-smoothing:antialiased}}
{top_nav_css}
    .channels-app{{height:calc(100dvh - var(--topnav-h, 45px) - var(--search-widget-h, 53px));display:grid;grid-template-columns:240px minmax(0,1fr);border-top:1px solid var(--line)}}
    .channels-sidebar{{background:#121416;border-right:1px solid var(--line);padding:14px 10px;overflow:auto}}
    .sidebar-title{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:4px 10px 10px}}
    .channel-link{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;color:var(--text);text-decoration:none;border-radius:6px;padding:7px 10px;font-size:13px;min-height:34px}}
    .channel-link:hover,.channel-link.active{{background:var(--panel-2)}}
{AFK_NOTIFY_CSS}
    .channel-name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
    .unread-badge{{display:none;min-width:18px;padding:1px 6px;border-radius:999px;background:var(--orange);color:#16120a;font-size:11px;font-weight:800;text-align:center}}
    .unread-badge.visible{{display:inline-block}}
    .sidebar-meta{{font-size:11px;color:var(--muted);padding:10px}}
    .channel-main{{min-width:0;display:grid;grid-template-rows:auto minmax(0,1fr) auto;background:var(--bg)}}
    .channel-header{{border-bottom:1px solid var(--line);background:rgba(23,25,27,.96);padding:14px 18px;display:flex;justify-content:space-between;align-items:center;gap:14px}}
    .channel-heading{{min-width:0}}
    .channel-header h1{{font-size:18px;font-weight:750;letter-spacing:0}}
    .channel-header p{{font-size:12px;color:var(--muted);margin-top:2px}}
    .view-toggle{{display:inline-grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:#111315;flex:0 0 auto}}
    .view-toggle button{{border:0;border-left:1px solid var(--line);background:transparent;color:var(--muted);padding:7px 12px;font-size:12px;font-weight:800;cursor:pointer}}
    .view-toggle button:first-child{{border-left:0}}
    .view-toggle button.active{{background:var(--teal);color:#071211}}
    .view-shell{{min-width:0;min-height:0;position:relative;overflow:hidden}}
    .messages{{overflow:auto;padding:16px 18px 28px;scrollbar-gutter:stable}}
    .messages[hidden],.graph-view[hidden]{{display:none}}
    .empty{{color:var(--muted);font-size:13px;padding:28px 4px}}
    .event-row{{max-width:900px;margin:0 0 12px;border-left:3px solid var(--line);padding-left:10px}}
    .event-row.claude{{border-left-color:var(--blue)}}.event-row.codex{{border-left-color:var(--green)}}.event-row.gemini{{border-left-color:var(--violet)}}
    .event-row.user{{border-left-color:var(--orange);background:rgba(245,158,11,.08);padding:10px 12px;border-radius:0 6px 6px 0}}
    .message-meta{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-bottom:4px}}
    .agent-name{{font-weight:800}}.agent-name.claude{{color:var(--blue)}}.agent-name.codex{{color:var(--green)}}.agent-name.gemini{{color:var(--violet)}}.agent-name.user{{color:var(--orange)}}
    .model-tag,.event-pill{{background:var(--panel-2);border:1px solid var(--line);border-radius:5px;padding:1px 6px;font-size:10px;color:var(--muted)}}
    .message-body{{font-size:13px;white-space:pre-wrap;word-break:break-word;color:var(--text)}}
    .event-note{{color:var(--muted);font-size:12px;padding:2px 0}}
    .post-form{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;border-top:1px solid var(--line);background:var(--panel);padding:12px 18px}}
    .post-input{{width:100%;min-height:44px;max-height:150px;resize:vertical;border:1px solid var(--line);border-radius:6px;background:#0f1011;color:var(--text);padding:10px 12px;font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}}
    .post-input:focus{{outline:2px solid rgba(61,214,198,.35);border-color:var(--teal)}}
    .post-button{{border:1px solid rgba(245,158,11,.6);background:var(--orange);color:#171207;border-radius:6px;padding:0 16px;font-size:13px;font-weight:800;cursor:pointer}}
    .post-button:disabled{{opacity:.55;cursor:not-allowed}}
    .form-status{{grid-column:1 / -1;color:var(--muted);font-size:12px;min-height:16px}}
    .graph-view{{height:100%;overflow:auto;padding:16px 18px 28px}}
    .graph-banner{{border:1px solid rgba(245,158,11,.45);background:rgba(245,158,11,.1);color:#f8d9a0;border-radius:6px;padding:12px 14px;font-size:13px;margin-bottom:14px}}
    .graph-card{{min-width:680px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel)}}
    .decision-graph{{width:100%;border-collapse:collapse;table-layout:fixed}}
    .decision-graph th,.decision-graph td{{border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:10px;vertical-align:top;font-size:12px}}
    .decision-graph th{{background:#121416;color:var(--muted);text-align:left;text-transform:uppercase;letter-spacing:.06em;font-size:10px}}
    .decision-graph tr:last-child td{{border-bottom:0}}
    .round-label{{font-weight:850;color:var(--text);white-space:nowrap}}
    .round-cost{{display:block;color:var(--muted);font-size:10px;font-weight:600;margin-top:2px}}
    .vote-chip{{border:1px solid var(--line);border-radius:999px;background:#111315;color:var(--text);padding:5px 8px;font-size:11px;font-weight:850;cursor:pointer;max-width:100%;white-space:normal;text-align:left}}
    .vote-chip.agree{{border-color:rgba(85,209,127,.55);background:rgba(85,209,127,.12);color:#9ef0b7}}
    .vote-chip.defer,.vote-chip.needs{{border-color:rgba(245,158,11,.55);background:rgba(245,158,11,.12);color:#f8d9a0}}
    .vote-chip.option{{border-color:rgba(105,167,255,.6);background:rgba(105,167,255,.12);color:#a9cfff}}
    .vote-chip.null{{color:var(--muted)}}
    .missed{{color:var(--muted);font-style:italic}}
    .decision-footer{{border-top:1px solid var(--line);padding:12px 14px;color:var(--muted);font-size:13px}}
    .decision-footer strong{{color:var(--text)}}
    .decision-lineage{{display:block;margin-top:6px;color:var(--muted)}}
    .decision-lineage a{{color:var(--teal);text-decoration:none;font-weight:800}}
    .decision-lineage a:hover{{text-decoration:underline}}
    .modal-backdrop{{position:fixed;inset:0;background:rgba(0,0,0,.62);display:grid;place-items:center;padding:24px;z-index:20}}
    .modal-backdrop[hidden]{{display:none}}
    .turn-modal{{width:min(1100px,96vw);max-height:88vh;display:grid;grid-template-rows:auto minmax(0,1fr);background:#101112;border:1px solid var(--line);border-radius:8px;box-shadow:0 24px 80px rgba(0,0,0,.45);overflow:hidden}}
    .modal-header{{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding:12px 14px;background:var(--panel)}}
    .modal-title{{font-size:13px;font-weight:850}}
    .modal-close{{border:1px solid var(--line);background:#111315;color:var(--text);border-radius:6px;width:30px;height:30px;cursor:pointer;font-size:18px;line-height:1}}
    .modal-body{{overflow:auto;padding:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
    .event-row.kbd-focused{{border-left-color:var(--red);box-shadow:inset 3px 0 0 var(--red);background:rgba(251,113,133,.1);padding-top:8px;padding-bottom:8px;border-radius:0 6px 6px 0}}
    .kbd-modal{{width:min(560px,94vw);max-height:82vh;display:grid;grid-template-rows:auto minmax(0,1fr);background:#101112;border:1px solid var(--line);border-radius:8px;box-shadow:0 24px 80px rgba(0,0,0,.48);overflow:hidden}}
    .kbd-modal-body{{overflow:auto;padding:14px}}
    .switcher-input{{width:100%;border:1px solid var(--line);border-radius:6px;background:#0f1011;color:var(--text);padding:10px 12px;font:14px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;margin-bottom:10px}}
    .switcher-input:focus{{outline:2px solid rgba(61,214,198,.35);border-color:var(--teal)}}
    .switcher-list{{display:grid;gap:4px}}
    .switcher-result{{border:1px solid transparent;background:transparent;color:var(--text);border-radius:6px;padding:9px 10px;text-align:left;font-size:13px;cursor:pointer}}
    .switcher-result.active,.switcher-result:hover{{border-color:rgba(61,214,198,.5);background:rgba(61,214,198,.12)}}
    .switcher-empty{{color:var(--muted);font-size:13px;padding:14px 4px}}
    .help-list{{display:grid;gap:8px;font-size:13px}}
    .help-row{{display:grid;grid-template-columns:86px minmax(0,1fr);gap:12px;align-items:center;border-bottom:1px solid var(--line);padding:9px 0}}
    .help-row:last-child{{border-bottom:0}}
    .help-key{{justify-self:start;border:1px solid var(--line);background:#111315;border-radius:5px;padding:3px 7px;font:12px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--teal)}}
    .turn-body{{min-width:0;border:1px solid var(--line);border-radius:6px;background:#0d0f10;overflow:hidden}}
    .turn-body h3{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);padding:8px 10px;border-bottom:1px solid var(--line);background:#121416}}
    .turn-body pre{{white-space:pre-wrap;word-break:break-word;color:var(--text);font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;padding:10px;max-height:62vh;overflow:auto}}
    @media(max-width:760px){{.channels-app{{grid-template-columns:1fr;height:auto;min-height:calc(100dvh - var(--topnav-h, 45px) - var(--search-widget-h, 53px))}}.channels-sidebar{{max-height:210px;border-right:0;border-bottom:1px solid var(--line)}}.channel-main{{min-height:70vh}}.channel-header{{align-items:flex-start;flex-direction:column}}.view-toggle{{width:100%}}}}
  </style>
</head>
<body>
{render_top_nav_fn("channels")}
{render_search_widget()}
{render_afk_notify_markup()}
<div class="channels-app" data-selected-channel="{_html.escape(selected_channel or "", quote=True)}" data-default-view="{escaped_default_view}">
  <nav class="channels-sidebar" aria-label="Channels">
    <div class="sidebar-title">Channels</div>
    <div id="channelList"></div>
    <div class="sidebar-meta" id="sidebarMeta">Loading...</div>
  </nav>
  <main class="channel-main">
    <header class="channel-header">
      <div class="channel-heading">
        <h1 id="channelTitle">Agent Deliberations</h1>
        <p><span id="channelMeta">Select a channel</span> · <span id="pollState">idle</span></p>
      </div>
      <div class="view-toggle" aria-label="Thread view">
        <button type="button" data-view-toggle="chat">Chat</button>
        <button type="button" data-view-toggle="graph">Graph</button>
      </div>
    </header>
    <div class="view-shell">
      <!-- delta-render: message nodes use data-message-id and renderedMsgIds; existing nodes are never overwritten -->
      <section class="messages" id="messageList" aria-live="polite">
        <div class="empty" id="emptyState">Waiting for channel activity...</div>
      </section>
      <section class="graph-view" id="graphView" hidden>
        <div class="graph-banner" id="graphFallback" hidden>This thread has no structured votes — switch to Chat view to read the discussion.</div>
        <div id="graphMount"></div>
      </section>
    </div>
    <form class="post-form" id="postForm">
      <textarea class="post-input" id="postBody" name="body" maxlength="8000" placeholder="Post to the selected channel"></textarea>
      <button class="post-button" id="postButton" type="submit">Post</button>
      <div class="form-status" id="formStatus"></div>
    </form>
  </main>
</div>
<div class="modal-backdrop" id="turnModal" hidden>
  <div class="turn-modal" role="dialog" aria-modal="true" aria-labelledby="turnModalTitle">
    <div class="modal-header">
      <div class="modal-title" id="turnModalTitle">Turn body</div>
      <button class="modal-close" id="turnModalClose" type="button" aria-label="Close">×</button>
    </div>
    <div class="modal-body" id="turnModalBody"></div>
  </div>
</div>
<div class="modal-backdrop" id="channel-switcher-modal" hidden>
  <div class="kbd-modal" role="dialog" aria-modal="true" aria-labelledby="channelSwitcherTitle">
    <div class="modal-header">
      <div class="modal-title" id="channelSwitcherTitle">Switch channel</div>
      <button class="modal-close" id="channelSwitcherClose" type="button" aria-label="Close">×</button>
    </div>
    <div class="kbd-modal-body">
      <input class="switcher-input" id="channelSwitcherInput" type="text" autocomplete="off" spellcheck="false" placeholder="Type a channel name">
      <div class="switcher-list" id="channelSwitcherList"></div>
    </div>
  </div>
</div>
<div class="modal-backdrop" id="keybindings-help-modal" hidden>
  <div class="kbd-modal" role="dialog" aria-modal="true" aria-labelledby="keybindingsHelpTitle">
    <div class="modal-header">
      <div class="modal-title" id="keybindingsHelpTitle">Keyboard shortcuts</div>
      <button class="modal-close" id="keybindingsHelpClose" type="button" aria-label="Close">×</button>
    </div>
    <div class="kbd-modal-body">
      <div class="help-list">
        <div class="help-row"><span class="help-key">⌘K / Ctrl+K</span><span>Open the channel switcher.</span></div>
        <div class="help-row"><span class="help-key">j / k</span><span>Move the focused message indicator.</span></div>
        <div class="help-row"><span class="help-key">gg / G</span><span>Jump to the top or bottom of the message list.</span></div>
        <div class="help-row"><span class="help-key">?</span><span>Show or hide this shortcuts panel.</span></div>
      </div>
    </div>
  </div>
</div>
<script>
const INITIAL_CHANNEL = {selected_js};
const DEFAULT_VIEW = document.querySelector(".channels-app")?.dataset.defaultView || "chat";
const INITIAL_PARAMS = new URLSearchParams(window.location.search);
const REQUESTED_VIEW = ["chat","graph"].includes(INITIAL_PARAMS.get("view")) ? INITIAL_PARAMS.get("view") : null;
const DEFAULT_POLL_MS = 5000;
const TIGHT_POLL_MS = 1000;
const QUIET_RESET_MS = 30000;
let selectedChannel = INITIAL_CHANNEL;
let sinceId = 0;
let sinceMessageRowId = 0;
let currentFetchId = 0;
let pollTimer = null;
let lastEventType = "";
let lastNewEventAt = 0;
let channels = [];
let hasBooted = false;
let currentView = REQUESTED_VIEW || DEFAULT_VIEW;
let threadSummary = null;
let summaryFetchId = 0;
let focusedMessageIndex = -1;
let lastGKeyAt = 0;
const renderedMsgIds = new Set();
const channelList = document.getElementById("channelList");
const messageList = document.getElementById("messageList");
const emptyState = document.getElementById("emptyState");
const graphView = document.getElementById("graphView");
const graphMount = document.getElementById("graphMount");
const graphFallback = document.getElementById("graphFallback");
const postForm = document.getElementById("postForm");
const postBody = document.getElementById("postBody");
const postButton = document.getElementById("postButton");
const formStatus = document.getElementById("formStatus");
const turnModal = document.getElementById("turnModal");
const turnModalTitle = document.getElementById("turnModalTitle");
const turnModalBody = document.getElementById("turnModalBody");
const turnModalClose = document.getElementById("turnModalClose");
const channelSwitcherModal = document.getElementById("channel-switcher-modal");
const channelSwitcherInput = document.getElementById("channelSwitcherInput");
const channelSwitcherList = document.getElementById("channelSwitcherList");
const channelSwitcherClose = document.getElementById("channelSwitcherClose");
const keybindingsHelpModal = document.getElementById("keybindings-help-modal");
const keybindingsHelpClose = document.getElementById("keybindingsHelpClose");
function lastVisitedKey(name){{return "kdjo_channel_lastvisited_"+name;}}
function timeAgo(iso){{if(!iso)return"no activity";const d=Math.floor((Date.now()-new Date(iso))/1000);if(d<60)return d+"s ago";if(d<3600)return Math.floor(d/60)+"m ago";if(d<86400)return Math.floor(d/3600)+"h ago";return Math.floor(d/86400)+"d ago";}}
function setText(el,value){{el.textContent=value == null ? "" : String(value);}}
function rememberVisited(name){{if(name)localStorage.setItem(lastVisitedKey(name),new Date().toISOString());}}
function computePollDelayMs(now=Date.now()){{if((lastEventType==="reply_started"||lastEventType==="heartbeat")&&lastNewEventAt&&now-lastNewEventAt<QUIET_RESET_MS)return TIGHT_POLL_MS;return DEFAULT_POLL_MS;}}
function isNearBottom(){{return messageList.scrollHeight-messageList.scrollTop-messageList.clientHeight<48;}}
function resetMessages(){{renderedMsgIds.clear();sinceId=0;sinceMessageRowId=0;lastEventType="";lastNewEventAt=0;focusedMessageIndex=-1;messageList.replaceChildren(emptyState);emptyState.style.display="block";}}
function hasStructuredVotes(summary){{return !!(summary&&summary.rounds&&summary.rounds.some(round=>(round.turns||[]).some(turn=>turn.vote)));}}
function defaultViewForSummary(summary){{if(REQUESTED_VIEW)return REQUESTED_VIEW;if(summary&&(summary.status==="converged"||summary.decision_id))return"graph";return DEFAULT_VIEW;}}
function shortThreadId(value){{return String(value||"").slice(0,8);}}
function updateThreadHeading(summary){{if(!summary||!summary.thread_id||selectedChannel!==summary.thread_id||!summary.channel)return;threadSummary=summary;const title=document.getElementById("channelTitle");const meta=document.getElementById("channelMeta");title.textContent="# "+summary.channel;const pieces=["thread "+shortThreadId(summary.thread_id)];if(summary.rounds&&summary.rounds.length)pieces.push(summary.rounds.length+" round"+(summary.rounds.length===1?"":"s"));if(summary.decision_id)pieces.push("decision linked");meta.textContent=pieces.join(" · ");renderSidebar();}}
function setView(view,updateUrl=true){{currentView=view==="graph"?"graph":"chat";messageList.hidden=currentView!=="chat";graphView.hidden=currentView!=="graph";document.querySelectorAll("[data-view-toggle]").forEach(btn=>btn.classList.toggle("active",btn.dataset.viewToggle===currentView));if(updateUrl){{const url=new URL(window.location.href);url.searchParams.set("view",currentView);history.replaceState(null,"",url);}}}}
function voteClass(vote){{if(!vote)return"null";if(vote==="AGREE")return"agree";if(vote==="DEFER")return"defer";if(vote.startsWith("NEEDS"))return"needs";if(vote.startsWith("OPTION "))return"option";return"null";}}
function agentColumns(summary){{const seen=new Set();(summary.rounds||[]).forEach(round=>(round.turns||[]).forEach(turn=>seen.add(turn.agent)));return Array.from(seen).sort((a,b)=>{{const order={{claude:0,codex:1,gemini:2}};return (order[a]??100)-(order[b]??100)||a.localeCompare(b);}});}}
function formatMoney(value){{const n=Number(value||0);return n?"$"+n.toFixed(3):"$0";}}
function formatElapsed(value){{const n=Number(value||0);return n?Math.round(n)+"s":"0s";}}
function selectedDecision(summary){{const rounds=summary&&summary.rounds||[];const last=rounds.length?rounds[rounds.length-1]:null;const votes=last?(last.turns||[]).map(t=>t.vote).filter(Boolean):[];const options=votes.filter(v=>v&&v.startsWith("OPTION "));if(options.length)return options[options.length-1].replace("OPTION ","OPT ");if(votes.every(v=>v==="AGREE")&&votes.length)return"AGREE";return String(summary.status||"in_flight");}}
function basename(path){{return String(path||"").split("/").pop();}}
function githubCommitUrl(sha){{return "https://github.com/kube-dojo/kube-dojo.github.io/commit/"+encodeURIComponent(sha);}}
function githubPrUrl(number){{return "https://github.com/kube-dojo/kube-dojo.github.io/pull/"+encodeURIComponent(number);}}
function renderLineage(footer,decisionId){{if(!decisionId)return;const line=document.createElement("span");line.className="decision-lineage";line.textContent="Influenced: loading...";footer.appendChild(line);fetch("/api/decision/"+encodeURIComponent(basename(decisionId))+"/lineage").then(r=>r.json()).then(data=>{{const lineage=data.lineage||{{}};const prs=lineage.prs||[];const prShas=new Set(prs.map(pr=>pr.sha).filter(Boolean));const commits=(lineage.commits||[]).filter(commit=>!prShas.has(commit.sha));const parts=[];prs.forEach(pr=>{{const a=document.createElement("a");a.href=githubPrUrl(pr.number);a.textContent="PR #"+pr.number;parts.push(a);}});commits.slice(0,6).forEach(commit=>{{const a=document.createElement("a");a.href=githubCommitUrl(commit.sha);a.textContent="commit "+String(commit.sha||"").slice(0,8);parts.push(a);}});line.textContent="Influenced: ";if(!parts.length){{line.appendChild(document.createTextNode("none found"));return;}}parts.forEach((part,idx)=>{{if(idx)line.appendChild(document.createTextNode(" · "));line.appendChild(part);}});}}).catch(()=>{{line.textContent="Influenced: unavailable";}});}}
function renderGraph(summary){{threadSummary=summary;graphMount.replaceChildren();const structured=hasStructuredVotes(summary);graphFallback.hidden=structured;if(!summary||!structured)return;const agents=agentColumns(summary);const card=document.createElement("div");card.className="graph-card";const table=document.createElement("table");table.className="decision-graph";const thead=document.createElement("thead");const headRow=document.createElement("tr");["Round",...agents].forEach(label=>{{const th=document.createElement("th");th.textContent=label;headRow.appendChild(th);}});thead.appendChild(headRow);table.appendChild(thead);const tbody=document.createElement("tbody");(summary.rounds||[]).forEach(round=>{{const tr=document.createElement("tr");const label=document.createElement("td");label.innerHTML="<span class='round-label'>ROUND "+String(round.round_idx)+"</span><span class='round-cost'>"+formatMoney(round.cost_usd)+" · "+formatElapsed(round.elapsed_s)+"</span>";tr.appendChild(label);agents.forEach(agent=>{{const td=document.createElement("td");const turn=(round.turns||[]).find(item=>item.agent===agent);if(turn){{const btn=document.createElement("button");btn.type="button";btn.className="vote-chip "+voteClass(turn.vote);btn.textContent=agent+": ["+(turn.vote||"NO VOTE")+"]";btn.addEventListener("click",()=>openTurnModal(round,turn));td.appendChild(btn);}}else{{const missed=document.createElement("span");missed.className="missed";missed.textContent="<missed>";td.appendChild(missed);}}tr.appendChild(td);}});tbody.appendChild(tr);}});table.appendChild(tbody);card.appendChild(table);const footer=document.createElement("div");footer.className="decision-footer";footer.innerHTML="<strong>DECISION</strong> → Selected: "+selectedDecision(summary)+(summary.decision_id?" · Linked: "+summary.decision_id:" · Linked: none")+" · Total: "+formatMoney(summary.total_cost_usd)+" / "+formatElapsed(summary.total_elapsed_s);renderLineage(footer,summary.decision_id);card.appendChild(footer);graphMount.appendChild(card);}}
function loadSummary(){{const myFetchId=++summaryFetchId;threadSummary=null;graphMount.replaceChildren();graphFallback.hidden=true;if(!selectedChannel){{setView("chat",false);return;}}fetch("/api/channel/"+encodeURIComponent(selectedChannel)+"/summary").then(r=>r.json()).then(summary=>{{if(myFetchId!==summaryFetchId)return;updateThreadHeading(summary);renderGraph(summary);setView(defaultViewForSummary(summary),false);}}).catch(()=>{{if(myFetchId===summaryFetchId){{graphFallback.hidden=false;setView("chat",false);}}}});}}
function openTurnModal(round,turn){{turnModalTitle.textContent="Round "+String(round.round_idx)+" · "+String(turn.agent||"turn");turnModalBody.replaceChildren();const turns=(round.turns||[]).length>1?round.turns:[turn];turns.forEach(item=>{{const wrap=document.createElement("section");wrap.className="turn-body";const h=document.createElement("h3");h.textContent=String(item.agent||"agent")+" · "+String(item.vote||"no vote")+" · "+String(item.model||"");const pre=document.createElement("pre");pre.textContent=String(item.body||item.body_preview||"");wrap.append(h,pre);turnModalBody.appendChild(wrap);}});turnModal.hidden=false;turnModalClose.focus();}}
function closeTurnModal(){{turnModal.hidden=true;turnModalBody.replaceChildren();}}
function renderSidebar(){{channelList.replaceChildren();let syntheticThreads=0;channels.forEach(ch=>{{const a=document.createElement("a");a.className="channel-link"+(ch.name===selectedChannel?" active":"");a.href="/channels/"+encodeURIComponent(ch.name);a.dataset.channelName=ch.name;const name=document.createElement("span");name.className="channel-name";if(ch.name===selectedChannel&&threadSummary&&threadSummary.thread_id===selectedChannel&&threadSummary.channel){{syntheticThreads+=1;name.textContent="thread "+shortThreadId(selectedChannel)+" · # "+threadSummary.channel;}}else{{name.textContent="# "+ch.name;}}const badge=document.createElement("span");badge.className="unread-badge";badge.dataset.unreadFor=ch.name;a.append(name,badge);a.addEventListener("click",()=>rememberVisited(ch.name));channelList.appendChild(a);}});const channelCount=Math.max(0,channels.length-syntheticThreads);document.getElementById("sidebarMeta").textContent=channelCount+" channel"+(channelCount===1?"":"s")+(syntheticThreads?" · "+syntheticThreads+" thread"+(syntheticThreads===1?"":"s"):"");updateUnreadBadges();}}
function updateUnreadBadges(){{channels.forEach(ch=>{{const badge=channelList.querySelector(`[data-unread-for="${{CSS.escape(ch.name)}}"]`);if(!badge)return;const last=localStorage.getItem(lastVisitedKey(ch.name));if(ch.name===selectedChannel||!ch.last_event_ts||last&&new Date(ch.last_event_ts)<=new Date(last)){{badge.classList.remove("visible");badge.textContent="";return;}}if(!last){{badge.textContent=String(ch.event_count||1);badge.classList.add("visible");return;}}fetch("/api/channel/"+encodeURIComponent(ch.name)+"/events?since_ts="+encodeURIComponent(last)).then(r=>r.json()).then(data=>{{const n=(data.events||[]).length;if(n>0){{badge.textContent=String(n);badge.classList.add("visible");}}else{{badge.classList.remove("visible");badge.textContent="";}}}}).catch(()=>{{badge.textContent="!";badge.classList.add("visible");}});}});}}
function appendMeta(parent,ev,agent){{const meta=document.createElement("div");meta.className="message-meta";const name=document.createElement("span");name.className="agent-name "+agent;name.textContent=agent==="user"?"👤 user":agent;meta.appendChild(name);if(ev.from_model||ev.model){{const model=document.createElement("span");model.className="model-tag";model.textContent=ev.from_model||ev.model;meta.appendChild(model);}}const stamp=document.createElement("span");stamp.textContent=(ev.ts||ev.created_at||"").slice(0,19).replace("T"," ");meta.appendChild(stamp);parent.appendChild(meta);}}
function appendBody(parent,body){{const div=document.createElement("div");div.className="message-body";div.textContent=body||"";parent.appendChild(div);}}
function appendNote(ev,text,cls=""){{const key=String(ev.event_id||"")+"-"+String(ev.ts||"");if(renderedMsgIds.has(key))return;renderedMsgIds.add(key);const row=document.createElement("div");row.className="event-row "+cls;row.dataset.eventId=String(ev.event_id||"");const note=document.createElement("div");note.className="event-note";note.textContent=text;row.appendChild(note);messageList.appendChild(row);}}
function appendMessage(ev){{const key=ev.message_id||String(ev.event_id||"")+"-"+String(ev.ts||"");if(renderedMsgIds.has(key))return;renderedMsgIds.add(key);const agent=(ev.from_agent||ev.agent||"unknown").toLowerCase();const cls=["claude","codex","gemini","user"].includes(agent)?agent:"";const row=document.createElement("article");row.className="event-row "+cls;row.dataset.messageId=key;row.dataset.eventId=String(ev.event_id||"");appendMeta(row,ev,agent);appendBody(row,ev.body||"");messageList.appendChild(row);}}
function renderEvent(ev){{if(emptyState)emptyState.style.display="none";if(ev.message_id&&ev.body!==undefined)appendMessage(ev);else if(ev.event==="reply_complete")appendMessage(ev);else if(ev.event==="reply_started")appendNote(ev,(ev.agent||"agent")+" started replying","");else if(ev.event==="heartbeat")appendNote(ev,"heartbeat elapsed="+(ev.elapsed_s||"?")+"s","");else if(ev.event==="delivery_failed")appendNote(ev,"delivery failed "+(ev.error_kind||""),"");else if(ev.event==="delivery_delivered")appendNote(ev,"delivered "+(ev.delivery_id||""),"");else if(ev.event==="model_cascade")appendNote(ev,"cascade "+(ev.from||"")+" -> "+(ev.to||""),"");}}
function applyEvents(events,nextSince,nextMessageRowId){{sinceId=Math.max(sinceId,nextSince||sinceId);sinceMessageRowId=Math.max(sinceMessageRowId,nextMessageRowId||0);if(!events.length)return;const stick=isNearBottom();events.forEach(renderEvent);lastEventType=events[events.length-1].event||"";lastNewEventAt=Date.now();document.getElementById("channelMeta").textContent=events.length+" new event"+(events.length===1?"":"s")+" · last "+timeAgo(events[events.length-1].ts);if(stick)messageList.scrollTop=messageList.scrollHeight;rememberVisited(selectedChannel);updateUnreadBadges();}}
function schedulePoll(){{clearTimeout(pollTimer);pollTimer=setTimeout(poll,computePollDelayMs());document.getElementById("pollState").textContent="next poll "+computePollDelayMs()/1000+"s";}}
function poll(){{if(!selectedChannel){{schedulePoll();return;}}const myFetchId=++currentFetchId;fetch("/api/channel/"+encodeURIComponent(selectedChannel)+"/events?since_event_id="+sinceId+"&since_message_rowid="+sinceMessageRowId).then(r=>r.json()).then(data=>{{if(myFetchId!==currentFetchId)return;applyEvents(data.events||[],data.next_since_event_id,data.next_since_message_rowid);}}).catch(()=>{{if(myFetchId===currentFetchId)document.getElementById("pollState").textContent="API unavailable";}}).finally(()=>{{if(myFetchId===currentFetchId)schedulePoll();}});}}
function chooseChannel(name){{selectedChannel=name;if(!selectedChannel&&channels.length)selectedChannel=channels[0].name;document.getElementById("channelTitle").textContent=selectedChannel?"# "+selectedChannel:"Agent Deliberations";postButton.disabled=!selectedChannel;resetMessages();loadSummary();rememberVisited(selectedChannel);renderSidebar();poll();}}
function loadChannels(){{fetch("/api/channels").then(r=>r.json()).then(data=>{{channels=data.channels||[];if(selectedChannel&&!channels.some(ch=>ch.name===selectedChannel))channels.unshift({{name:selectedChannel,event_count:0,last_event_ts:null,threads:[]}});renderSidebar();if(!hasBooted){{hasBooted=true;chooseChannel(selectedChannel);}}}}).catch(()=>{{document.getElementById("sidebarMeta").textContent="API unavailable";}});}}
// D4.5 keybindings
function isKeybindingInputTarget(event){{return event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA';}}
function messageRows(){{return Array.from(messageList.querySelectorAll(".event-row"));}}
function focusMessageAt(index){{const rows=messageRows();if(!rows.length)return;const next=(index+rows.length)%rows.length;rows.forEach(row=>row.classList.remove("kbd-focused"));focusedMessageIndex=next;rows[next].classList.add("kbd-focused");rows[next].scrollIntoView({{block:"nearest",behavior:"smooth"}});}}
function moveFocusedMessage(delta){{const rows=messageRows();if(!rows.length)return;const start=focusedMessageIndex<0?(delta>0?-1:0):focusedMessageIndex;focusMessageAt(start+delta);}}
function jumpToMessageEdge(edge){{const rows=messageRows();if(rows.length)focusMessageAt(edge==="top"?0:rows.length-1);messageList.scrollTo({{top:edge==="top"?0:messageList.scrollHeight,behavior:"smooth"}});}}
function channelsFromSidebar(){{return Array.from(document.querySelectorAll(".channel-link")).map(link=>({{name:link.dataset.channelName||link.textContent.replace(/^#\\s*/,"").trim()}})).filter(channel=>channel.name);}}
function filteredSwitcherChannels(){{const query=channelSwitcherInput.value.toLowerCase();return channelsFromSidebar().filter(channel=>channel.name.toLowerCase().includes(query));}}
function renderChannelSwitcherResults(){{const matches=filteredSwitcherChannels();channelSwitcherList.replaceChildren();if(!matches.length){{const empty=document.createElement("div");empty.className="switcher-empty";empty.textContent="No matching channels";channelSwitcherList.appendChild(empty);return;}}matches.forEach((channel,index)=>{{const button=document.createElement("button");button.type="button";button.className="switcher-result"+(index===0?" active":"");button.textContent="# "+channel.name;button.dataset.channelName=channel.name;button.addEventListener("click",()=>navigateToSwitcherChannel(channel.name));channelSwitcherList.appendChild(button);}});}}
function activeSwitcherIndex(){{return Array.from(channelSwitcherList.querySelectorAll(".switcher-result")).findIndex(button=>button.classList.contains("active"));}}
function moveSwitcherHighlight(delta){{const buttons=Array.from(channelSwitcherList.querySelectorAll(".switcher-result"));if(!buttons.length)return;let next=activeSwitcherIndex();next=next<0?0:(next+delta+buttons.length)%buttons.length;buttons.forEach(button=>button.classList.remove("active"));buttons[next].classList.add("active");buttons[next].scrollIntoView({{block:"nearest"}});}}
function navigateToSwitcherChannel(name){{if(!name)return;window.location.href="/channels/"+encodeURIComponent(name);}}
function openChannelSwitcher(){{renderChannelSwitcherResults();channelSwitcherModal.hidden=false;channelSwitcherInput.value="";renderChannelSwitcherResults();channelSwitcherInput.focus();}}
function closeChannelSwitcher(){{channelSwitcherModal.hidden=true;}}
function toggleKeybindingsHelp(){{keybindingsHelpModal.hidden=!keybindingsHelpModal.hidden;if(!keybindingsHelpModal.hidden)keybindingsHelpClose.focus();}}
function closeKeybindingsHelp(){{keybindingsHelpModal.hidden=true;}}
channelSwitcherInput.addEventListener("input",renderChannelSwitcherResults);
channelSwitcherInput.addEventListener("keydown",event=>{{if(event.key==="ArrowDown"){{event.preventDefault();moveSwitcherHighlight(1);}}else if(event.key==="ArrowUp"){{event.preventDefault();moveSwitcherHighlight(-1);}}else if(event.key==="Enter"){{event.preventDefault();const active=channelSwitcherList.querySelector(".switcher-result.active");navigateToSwitcherChannel(active?active.dataset.channelName:"");}}else if(event.key==="Escape"){{event.preventDefault();closeChannelSwitcher();}}}});
channelSwitcherClose.addEventListener("click",closeChannelSwitcher);
channelSwitcherModal.addEventListener("click",event=>{{if(event.target===channelSwitcherModal)closeChannelSwitcher();}});
keybindingsHelpClose.addEventListener("click",closeKeybindingsHelp);
keybindingsHelpModal.addEventListener("click",event=>{{if(event.target===keybindingsHelpModal)closeKeybindingsHelp();}});
document.addEventListener('keydown', event=>{{if((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'){{event.preventDefault();openChannelSwitcher();return;}}if(isKeybindingInputTarget(event))return;if(event.key==="Escape"){{if(!channelSwitcherModal.hidden){{closeChannelSwitcher();return;}}if(!keybindingsHelpModal.hidden){{closeKeybindingsHelp();return;}}}}if(event.key === '?'){{event.preventDefault();toggleKeybindingsHelp();return;}}if(event.key === 'j'){{event.preventDefault();moveFocusedMessage(1);return;}}if(event.key === 'k'){{event.preventDefault();moveFocusedMessage(-1);return;}}if(event.key === 'G'){{event.preventDefault();jumpToMessageEdge("bottom");return;}}if(event.key === 'g'){{const now=Date.now();if(now-lastGKeyAt<500){{event.preventDefault();lastGKeyAt=0;jumpToMessageEdge("top");return;}}lastGKeyAt=now;}}}});
postForm.addEventListener("submit",ev=>{{ev.preventDefault();if(!selectedChannel)return;const body=postBody.value;if(!body.trim()){{formStatus.textContent="Body is required.";return;}}postButton.disabled=true;formStatus.textContent="Posting...";fetch("/api/channel/"+encodeURIComponent(selectedChannel)+"/post",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{body,from_agent:"user"}})}}).then(async r=>{{const data=await r.json();if(!r.ok)throw new Error(data.error||"post failed");postBody.value="";formStatus.textContent="Posted.";rememberVisited(selectedChannel);poll();loadChannels();}}).catch(err=>{{formStatus.textContent=err.message;}}).finally(()=>{{postButton.disabled=false;postBody.focus();}});}});
document.querySelectorAll("[data-view-toggle]").forEach(btn=>btn.addEventListener("click",()=>setView(btn.dataset.viewToggle,true)));
turnModalClose.addEventListener("click",closeTurnModal);
turnModal.addEventListener("click",ev=>{{if(ev.target===turnModal)closeTurnModal();}});
document.addEventListener("keydown",ev=>{{if(ev.key==="Escape"&&!turnModal.hidden)closeTurnModal();}});
setView(currentView,false);
loadChannels();
</script>
</body></html>"""


def render_channels_index_html(
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
) -> str:
    return render_channels_chat_html(
        None,
        top_nav_css=top_nav_css,
        render_top_nav_fn=render_top_nav_fn,
    )


def render_channel_thread_html(
    channel_name: str,
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
    default_view: str = "chat",
) -> str:
    return render_channels_chat_html(
        channel_name,
        top_nav_css=top_nav_css,
        render_top_nav_fn=render_top_nav_fn,
        default_view=default_view,
    )


def _parse_post_body(body_bytes: bytes | None, content_type: str) -> dict[str, Any]:
    raw = (body_bytes or b"").decode("utf-8", errors="replace")
    if "application/json" in content_type:
        try:
            payload = _json.loads(raw or "{}")
        except _json.JSONDecodeError as exc:
            raise ValueError("invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("invalid_json")
        return payload

    parsed = parse_qs(raw, keep_blank_values=True)
    payload: dict[str, Any] = {}
    for key, values in parsed.items():
        if key == "to":
            payload[key] = values
        else:
            payload[key] = values[-1] if values else ""
    return payload


def _parse_to_agents(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [agent.strip() for agent in value.split(",") if agent.strip()]
    if isinstance(value, list):
        agents: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                agents.append(item.strip())
        return agents
    raise ValueError("invalid_to")


def route_channel_post_request(
    path: str,
    *,
    body_bytes: bytes | None,
    content_type: str,
    bridge_db_path: Path | None = None,
) -> RouteResponse | None:
    if not (path.startswith("/api/channel/") and path.endswith("/post")):
        return None

    raw_channel = path[len("/api/channel/") : -len("/post")]
    channel_name = unquote(raw_channel).strip("/")
    if not channel_name:
        return _json_response(400, {"ok": False, "error": "missing_channel"})

    try:
        payload = _parse_post_body(body_bytes, content_type)
        body_value = payload.get("body")
        body = body_value if isinstance(body_value, str) else ""
        if not body.strip():
            return _json_response(400, {"ok": False, "error": "body_required"})
        if len(body) > 8000:
            return _json_response(400, {"ok": False, "error": "body_too_long"})
        from_agent = payload.get("from_agent", "user")
        if from_agent != "user":
            return _json_response(400, {"ok": False, "error": "invalid_from_agent"})
        to_agents = _parse_to_agents(payload.get("to"))
    except ValueError as exc:
        return _json_response(400, {"ok": False, "error": str(exc)})

    try:
        from ai_agent_bridge import _db as bridge_db
        from ai_agent_bridge._channels import get_channel, post

        with _POST_DB_LOCK:
            old_db_path = bridge_db.DB_PATH
            if bridge_db_path is not None:
                bridge_db.DB_PATH = bridge_db_path
            try:
                target_channel = channel_name
                parent_id = None
                if get_channel(channel_name) is None:
                    conn = bridge_db.get_db()
                    try:
                        thread_row = conn.execute(
                            """
                            SELECT channel, message_id
                            FROM channel_messages
                            WHERE thread_id = ?
                            ORDER BY round_index ASC, created_at ASC, rowid ASC
                            LIMIT 1
                            """,
                            (channel_name,),
                        ).fetchone()
                    finally:
                        conn.close()
                    if thread_row is None:
                        return _json_response(404, {"ok": False, "error": "channel_not_found"})
                    target_channel = thread_row["channel"]
                    parent_id = thread_row["message_id"]
                result = post(
                    channel=target_channel,
                    from_agent="user",
                    body=body,
                    to_agents=to_agents,
                    parent_id=parent_id,
                    auto_snapshot=False,
                    context_rev_shared="",
                    context_rev_channel="",
                    monitor_state_snapshot=None,
                )
            finally:
                bridge_db.DB_PATH = old_db_path
    except Exception as exc:  # noqa: BLE001 - endpoint contract requires JSON 500
        return _json_response(
            500,
            {
                "ok": False,
                "error": "internal_error",
                "exception": type(exc).__name__,
                "message": str(exc),
            },
        )

    return _json_response(
        200,
        {
            "ok": True,
            "message_id": result.get("message_id"),
            "thread_id": result.get("thread_id"),
            "parent_id": result.get("parent_id"),
            "ts": result.get("created_at"),
        },
    )


def route_channel_page_request(
    repo_root: Path,
    path: str,
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
) -> RouteResponse | None:
    if path == "/channels":
        return 200, render_channels_index_html(
            top_nav_css=top_nav_css,
            render_top_nav_fn=render_top_nav_fn,
        ), "text/html; charset=utf-8"
    if path.startswith("/channels/"):
        raw_tid = unquote(path[len("/channels/"):]).strip("/")
        summary = build_channel_thread_summary(
            repo_root,
            raw_tid,
            resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
            query_sqlite_rows_fn=query_sqlite_rows_fn,
        )
        return 200, render_channel_thread_html(
            raw_tid,
            top_nav_css=top_nav_css,
            render_top_nav_fn=render_top_nav_fn,
            default_view=_default_view_for_summary(summary),
        ), "text/html; charset=utf-8"
    return None


def route_channel_api_request(
    repo_root: Path,
    path: str,
    query: dict[str, list[str]],
    *,
    resolve_bridge_db_path_fn: Callable[[Path], Path],
    query_sqlite_rows_fn: Callable[..., list[dict[str, Any]]],
) -> RouteResponse | None:
    if path == "/api/channels":
        from ai_agent_bridge._channels import list_channels
        return (
            200,
            build_channel_threads_index(
                repo_root,
                list_channels_fn=list_channels,
                resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
                query_sqlite_rows_fn=query_sqlite_rows_fn,
            ),
            "application/json; charset=utf-8",
        )
    if path.startswith("/api/channel/") and path.endswith("/summary"):
        raw_thread_id = path[len("/api/channel/") : -len("/summary")]
        thread_id = unquote(raw_thread_id).strip("/")
        if not thread_id:
            return 400, {"error": "missing_thread_id"}, "application/json; charset=utf-8"
        return (
            200,
            build_channel_thread_summary(
                repo_root,
                thread_id,
                resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
                query_sqlite_rows_fn=query_sqlite_rows_fn,
            ),
            "application/json; charset=utf-8",
        )
    if path.startswith("/api/channel/") and path.endswith("/events"):
        raw_name = path[len("/api/channel/") : -len("/events")]
        name = unquote(raw_name).strip("/")
        if not name:
            return 400, {"error": "missing_channel_or_thread"}, "application/json; charset=utf-8"
        try:
            since_raw = query.get("since_event_id", ["0"])[0]
            if since_raw is None:
                raise TypeError
            since_event_id = int(since_raw)
        except (TypeError, ValueError):
            return 400, {"error": "invalid_since_event_id"}, "application/json; charset=utf-8"
        try:
            message_raw = query.get("since_message_rowid", ["0"])[0]
            if message_raw is None:
                raise TypeError
            since_message_rowid = int(message_raw)
        except (TypeError, ValueError):
            return 400, {"error": "invalid_since_message_rowid"}, "application/json; charset=utf-8"
        since_ts = query.get("since_ts", [None])[0]
        if channel_exists_in_db(
            repo_root,
            name,
            resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
            query_sqlite_rows_fn=query_sqlite_rows_fn,
        ):
            return (
                200,
                build_channel_timeline_payload(
                    repo_root,
                    name,
                    resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
                    query_sqlite_rows_fn=query_sqlite_rows_fn,
                    since_event_id=since_event_id,
                    since_ts=since_ts,
                    since_message_rowid=since_message_rowid,
                ),
                "application/json; charset=utf-8",
            )
        if thread_exists_in_db(
            repo_root,
            name,
            resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
            query_sqlite_rows_fn=query_sqlite_rows_fn,
        ):
            return (
                200,
                build_channel_timeline_payload(
                    repo_root,
                    "",
                    resolve_bridge_db_path_fn=resolve_bridge_db_path_fn,
                    query_sqlite_rows_fn=query_sqlite_rows_fn,
                    since_event_id=since_event_id,
                    since_ts=since_ts,
                    since_message_rowid=since_message_rowid,
                    thread_id=name,
                ),
                "application/json; charset=utf-8",
            )
        from ai_agent_bridge._channels_watch import read_channel_events
        return (
            200,
            build_channel_events_payload(
                name,
                read_channel_events_fn=read_channel_events,
                since_event_id=since_event_id,
            ),
            "application/json; charset=utf-8",
        )
    return None
