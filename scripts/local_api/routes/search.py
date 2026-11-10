from __future__ import annotations

import html as _html
import sqlite3
import time
from pathlib import Path
from typing import Any

try:
    from local_api.bridge_fts import setup_fts_tables
    from local_api.routes.decisions import _refresh_decisions_fts
except ModuleNotFoundError:
    from scripts.local_api.bridge_fts import setup_fts_tables
    from scripts.local_api.routes.decisions import _refresh_decisions_fts


RouteResponse = tuple[int, Any, str]
_VALID_KINDS = {"channels", "decisions", "all"}
_MARK_START = "__KDJO_MARK_START__"
_MARK_END = "__KDJO_MARK_END__"


def _json_response(status: int, payload: dict[str, Any]) -> RouteResponse:
    return status, payload, "application/json; charset=utf-8"


def _safe_snippet(value: str | None) -> str:
    if not value:
        return ""
    marked = value.replace("<mark>", _MARK_START).replace("</mark>", _MARK_END)
    escaped = _html.escape(marked)
    return escaped.replace(_MARK_START, "<mark>").replace(_MARK_END, "</mark>")


def _sanitize_fts_query(raw: str) -> str | None:
    query = " ".join(raw.replace("\x00", " ").split()).strip()
    query = query.lstrip("*^()[]").strip()
    if not query:
        return None

    terms: list[str] = []
    for token in query.split():
        cleaned = token.strip("*^()[]").strip()
        if not cleaned or not any(char.isalnum() for char in cleaned):
            continue
        terms.append(f'"{cleaned.replace("\"", "\"\"")}"')
    return " ".join(terms) if terms else None


def _parse_limit(query: dict[str, list[str]]) -> tuple[int | None, str | None]:
    raw = query.get("limit", ["20"])[0]
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return None, "invalid_limit"
    if limit < 1 or limit > 100:
        return None, "invalid_limit"
    return limit, None


def _ensure_fts(conn: sqlite3.Connection) -> None:
    setup_fts_tables(conn)
    conn.commit()


def _query_channel_results(
    conn: sqlite3.Connection,
    fts_query: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT
              channel,
              thread_id,
              message_id,
              from_agent,
              snippet(channel_messages_fts, 0, '<mark>', '</mark>', '...', 18) AS snippet,
              bm25(channel_messages_fts) AS rank
            FROM channel_messages_fts
            WHERE channel_messages_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    return [
        {
            "kind": "channel",
            "channel": row["channel"],
            "thread_id": row["thread_id"],
            "message_id": row["message_id"],
            "from_agent": row["from_agent"],
            "snippet": _safe_snippet(row["snippet"]),
            "rank": float(row["rank"]),
            "url": f"/channels/{row['thread_id']}",
        }
        for row in rows
    ]


def _query_decision_results(
    conn: sqlite3.Connection,
    fts_query: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT
              title,
              filename,
              snippet(decisions_fts, -1, '<mark>', '</mark>', '...', 18) AS snippet,
              bm25(decisions_fts) AS rank
            FROM decisions_fts
            WHERE decisions_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    return [
        {
            "kind": "decision",
            "filename": row["filename"],
            "title": row["title"],
            "snippet": _safe_snippet(row["snippet"]),
            "rank": float(row["rank"]),
            "url": f"/decisions#card-{row['filename']}",
        }
        for row in rows
    ]


def build_search_payload(
    repo_root: Path,
    query: dict[str, list[str]],
    *,
    bridge_db_path: Path,
) -> RouteResponse:
    raw_query = query.get("q", [""])[0]
    if raw_query is None or not raw_query.strip():
        return _json_response(400, {"error": "query required"})
    if len(raw_query) > 256:
        return _json_response(400, {"error": "query too long"})

    kind = query.get("kind", ["all"])[0] or "all"
    if kind not in _VALID_KINDS:
        return _json_response(400, {"error": "invalid kind", "supported": sorted(_VALID_KINDS)})
    limit, limit_error = _parse_limit(query)
    if limit_error or limit is None:
        return _json_response(400, {"error": "invalid limit", "max": 100})

    fts_query = _sanitize_fts_query(raw_query)
    if fts_query is None:
        return _json_response(400, {"error": "query required"})

    started = time.perf_counter()
    if kind in {"decisions", "all"}:
        _refresh_decisions_fts(repo_root, db_path=bridge_db_path)

    bridge_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(bridge_db_path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_fts(conn)
        results: list[dict[str, Any]] = []
        if kind in {"channels", "all"}:
            results.extend(_query_channel_results(conn, fts_query, limit=limit))
        if kind in {"decisions", "all"}:
            results.extend(_query_decision_results(conn, fts_query, limit=limit))
    except sqlite3.OperationalError as exc:
        if "fts5" in str(exc).lower() or "syntax error" in str(exc).lower():
            return _json_response(400, {"error": "invalid query"})
        raise
    finally:
        conn.close()

    results.sort(key=lambda item: (float(item["rank"]), str(item["kind"])))
    took_ms = int((time.perf_counter() - started) * 1000)
    return _json_response(
        200,
        {
            "query": raw_query,
            "kind": kind,
            "took_ms": took_ms,
            "results": results[:limit],
        },
    )


def route_search_request(
    repo_root: Path,
    path: str,
    query: dict[str, list[str]],
    *,
    bridge_db_path: Path,
) -> RouteResponse | None:
    if path != "/api/search":
        return None
    return build_search_payload(repo_root, query, bridge_db_path=bridge_db_path)
