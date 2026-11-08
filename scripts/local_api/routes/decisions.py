from __future__ import annotations

import html as _html
import hashlib
import json as _json
import os
import re as _re
import sqlite3
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

try:
    from local_api.bridge_fts import setup_decisions_fts
    from local_api.routes.ui_fragments import (
        AFK_NOTIFY_CSS,
        DESIGN_SYSTEM_LINK,
        render_afk_notify_markup,
        render_common_theme,
        render_search_widget,
    )
except ModuleNotFoundError:
    from scripts.local_api.bridge_fts import setup_decisions_fts
    from scripts.local_api.routes.ui_fragments import (
        AFK_NOTIFY_CSS,
        DESIGN_SYSTEM_LINK,
        render_afk_notify_markup,
        render_common_theme,
        render_search_widget,
    )


RouteResponse = tuple[int, Any, str]
_THREAD_ID_RE = _re.compile(r"\b[a-f0-9]{32}\b", _re.IGNORECASE)
_THREAD_LINE_RE = _re.compile(r"\*\*Thread:\*\*\s*`?([a-f0-9]{32})`?", _re.IGNORECASE)
_PR_RE = _re.compile(r"\(#(\d+)\)")
_ISSUE_REF_RE = _re.compile(r"#(\d+)")
_PHASE_CELL_RE = _re.compile(r"^\|\s*(D\d+)\s*\|")
_SAFE_DECISION_FILENAME_RE = _re.compile(r"^[A-Za-z0-9._-]+\.md$")
_DECISION_CARD_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
_STALE_SECONDS = 24 * 3600
_CACHE_VERSION = 6
_CACHE_LOCK = threading.Lock()
_DECISIONS_FTS_LOCK = threading.Lock()
_DECISIONS_FTS_META: dict[str, dict[str, float]] = {}


def _json_response(status: int, payload: dict[str, Any]) -> RouteResponse:
    return status, payload, "application/json; charset=utf-8"


def _decision_cache_path(repo_root: Path) -> Path:
    return repo_root / ".pipeline" / "decision-lineage-cache.json"


def _load_cache(repo_root: Path) -> dict[str, Any]:
    path = _decision_cache_path(repo_root)
    try:
        data = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(repo_root: Path, cache: dict[str, Any]) -> None:
    path = _decision_cache_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        _json.dumps(cache, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _repo_revision_key(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname):%(objectname)", "refs/heads", "refs/remotes"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return hashlib.sha1(result.stdout.encode("utf-8")).hexdigest()


def _relative_decision_path(repo_root: Path, decision_path: str | Path) -> tuple[Path, str]:
    path = Path(decision_path)
    if not path.is_absolute():
        path = repo_root / path
    resolved_repo = repo_root.resolve()
    resolved_path = path.resolve()
    rel = resolved_path.relative_to(resolved_repo).as_posix()
    if not (rel.startswith("docs/decisions/") and rel.endswith(".md")):
        raise ValueError("invalid_decision_path")
    return resolved_path, rel


def _extract_thread_id(body: str) -> str | None:
    line_match = _THREAD_LINE_RE.search(body)
    if line_match:
        return line_match.group(1)
    match = _THREAD_ID_RE.search(body)
    return match.group(0) if match else None


def _search_terms(body: str, slug: str) -> list[str]:
    terms: list[str] = []
    thread_id = _extract_thread_id(body)
    if thread_id:
        terms.append(thread_id)
    terms.append(slug)

    # The original roadmap ADR predates backlink discipline in merge messages.
    # Phase issue refs keep historical D-series PRs visible without pulling in
    # unrelated reference-section issues from the same document.
    for line in body.splitlines():
        if _re.match(r"\|\s*D\d", line):
            terms.extend(f"#{number}" for number in _ISSUE_REF_RE.findall(line))
            phase_match = _PHASE_CELL_RE.match(line)
            if phase_match:
                terms.append(f"{phase_match.group(1)}.5")

    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        if term and term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _run_git_log(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "--all", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _parse_git_log(output: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        sha, sep, rest = line.partition("|")
        if not sep:
            continue
        subject, sep, ts = rest.rpartition("|")
        if not sep:
            continue
        commits.append({"sha": sha, "subject": subject, "ts": ts})
    return commits


def _merge_commits(existing: dict[str, dict[str, str]], commits: list[dict[str, str]]) -> None:
    for commit in commits:
        sha = commit.get("sha")
        if sha and sha not in existing:
            existing[sha] = commit


def _status_for_path(rel_path: str, mtime: float) -> str:
    if rel_path.startswith("docs/decisions/pending/"):
        return "stale" if time.time() - mtime > _STALE_SECONDS else "pending"
    return "decided"


def _is_decision_card(path: Path) -> bool:
    return bool(_DECISION_CARD_RE.match(path.name))


def _lineage_from_commits(commits: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    prs: dict[str, dict[str, str]] = {}
    for commit in commits:
        subject = commit.get("subject", "")
        matches = _PR_RE.findall(subject)
        if not matches:
            continue
        number = matches[-1]
        prs.setdefault(
            number,
            {
                "number": number,
                "subject": subject,
                "sha": commit.get("sha", ""),
            },
        )
    return {"commits": commits, "prs": list(prs.values())}


def scan_decision_lineage(repo_root: Path, decision_path: str | Path) -> dict[str, Any]:
    decision_file, rel_path = _relative_decision_path(repo_root, decision_path)
    try:
        mtime = decision_file.stat().st_mtime
    except OSError as exc:
        raise FileNotFoundError(rel_path) from exc

    repo_rev = _repo_revision_key(repo_root)
    with _CACHE_LOCK:
        cache = _load_cache(repo_root)
        cached = cache.get(rel_path)
        if (
            isinstance(cached, dict)
            and cached.get("mtime") == mtime
            and cached.get("repo_rev") == repo_rev
            and cached.get("version") == _CACHE_VERSION
        ):
            lineage = cached.get("lineage")
            if isinstance(lineage, dict):
                payload = dict(lineage)
                payload["status"] = _status_for_path(rel_path, mtime)
                return payload

    body = decision_file.read_text(encoding="utf-8")
    slug = decision_file.stem
    thread_id = _extract_thread_id(body)
    commits_by_sha: dict[str, dict[str, str]] = {}
    pretty = "--pretty=format:%H|%s|%ci"

    for term in _search_terms(body, slug):
        output = _run_git_log(
            repo_root,
            [
                f"--grep={term}",
                "--since=90 days ago",
                pretty,
                "-50",
            ],
        )
        _merge_commits(commits_by_sha, _parse_git_log(output))

    touched_output = _run_git_log(
        repo_root,
        [
            "--since=90 days ago",
            pretty,
            "-50",
            "--",
            rel_path,
        ],
    )
    _merge_commits(commits_by_sha, _parse_git_log(touched_output))

    commits = list(commits_by_sha.values())
    lineage = _lineage_from_commits(commits)
    payload = {
        "decision_path": rel_path,
        "thread_id": thread_id,
        "status": _status_for_path(rel_path, mtime),
        "lineage": lineage,
    }
    with _CACHE_LOCK:
        cache = _load_cache(repo_root)
        cache[rel_path] = {
            "mtime": mtime,
            "repo_rev": repo_rev,
            "lineage": payload,
            "scanned_at": datetime.now(UTC).isoformat(),
            "version": _CACHE_VERSION,
        }
        _write_cache(repo_root, cache)
    return payload


def _decision_files(repo_root: Path) -> list[Path]:
    decisions_dir = repo_root / "docs" / "decisions"
    files: list[Path] = []
    if decisions_dir.exists():
        files.extend(path for path in sorted(decisions_dir.glob("*.md")) if _is_decision_card(path))
    pending_dir = decisions_dir / "pending"
    if pending_dir.exists():
        files.extend(path for path in sorted(pending_dir.glob("*.md")) if _is_decision_card(path))
    return files


def _bridge_db_path(repo_root: Path) -> Path:
    return repo_root / ".bridge" / "messages.db"


def _decision_title(body: str, filename: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or filename
    return filename


def _decision_date(body: str, filename: str) -> str:
    match = _re.search(r"^\*\*Date:\*\*\s*(.+)$", body, _re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename[:10] if len(filename) >= 10 else ""


def _refresh_decisions_fts(
    repo_root: Path,
    *,
    db_path: Path | None = None,
    create_db: bool = True,
) -> dict[str, Any]:
    """Refresh changed decision markdown rows in ``decisions_fts``."""
    target_db = db_path or _bridge_db_path(repo_root)
    if not create_db and not target_db.exists():
        return {"scanned": 0, "updated": [], "deleted": []}

    files = _decision_files(repo_root)
    current_names = {path.name for path in files}
    cache_key = f"{repo_root.resolve()}::{target_db.resolve()}"

    with _DECISIONS_FTS_LOCK:
        target_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target_db)
        try:
            setup_decisions_fts(conn)
            meta = _DECISIONS_FTS_META.setdefault(cache_key, {})
            updated: list[str] = []
            deleted: list[str] = []
            existing_names = {
                str(row[0])
                for row in conn.execute("SELECT filename FROM decisions_fts").fetchall()
            }

            for filename in sorted((set(meta) | existing_names) - current_names):
                conn.execute("DELETE FROM decisions_fts WHERE filename = ?", (filename,))
                meta.pop(filename, None)
                deleted.append(filename)

            for path in files:
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                filename = path.name
                if meta.get(filename) == mtime and filename in existing_names:
                    continue
                try:
                    body = path.read_text(encoding="utf-8")
                    rel = path.relative_to(repo_root).as_posix()
                except OSError:
                    continue
                conn.execute("DELETE FROM decisions_fts WHERE filename = ?", (filename,))
                conn.execute(
                    """
                    INSERT INTO decisions_fts(title, body, filename, mtime, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _decision_title(body, filename),
                        body,
                        filename,
                        repr(mtime),
                        _status_for_path(rel, mtime),
                    ),
                )
                meta[filename] = mtime
                updated.append(filename)
            conn.commit()
            return {"scanned": len(files), "updated": updated, "deleted": deleted}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def build_decisions_index(repo_root: Path) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    counts = {"decided": 0, "pending": 0, "stale": 0}
    for path in _decision_files(repo_root):
        try:
            rel = path.relative_to(repo_root).as_posix()
            body = path.read_text(encoding="utf-8")
            lineage_payload = scan_decision_lineage(repo_root, rel)
        except (OSError, ValueError):
            continue
        status = str(lineage_payload.get("status") or "decided")
        if status in counts:
            counts[status] += 1
        thread_id = lineage_payload.get("thread_id")
        filename = path.name
        href = (
            f"/channels/{thread_id}?view=graph"
            if isinstance(thread_id, str) and thread_id
            else f"/decisions/{'pending/' if '/pending/' in rel else ''}{filename}"
        )
        lineage = lineage_payload.get("lineage") if isinstance(lineage_payload.get("lineage"), dict) else {}
        commits = lineage.get("commits") if isinstance(lineage, dict) else []
        prs = lineage.get("prs") if isinstance(lineage, dict) else []
        decisions.append(
            {
                "filename": filename,
                "decision_path": rel,
                "title": _decision_title(body, filename),
                "date": _decision_date(body, filename),
                "thread_id": thread_id,
                "status": status,
                "href": href,
                "lineage_counts": {
                    "commits": len(commits) if isinstance(commits, list) else 0,
                    "prs": len(prs) if isinstance(prs, list) else 0,
                },
            }
        )
    decisions.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("filename") or "")), reverse=True)
    return {"decisions": decisions, "counts": {**counts, "total": len(decisions)}}


def build_pending_decisions(repo_root: Path) -> dict[str, Any]:
    pending_dir = repo_root / "docs" / "decisions" / "pending"
    files: list[dict[str, Any]] = []
    stale = 0
    pending = 0
    if pending_dir.exists():
        for path in sorted(pending_dir.glob("*.md")):
            if not _is_decision_card(path):
                continue
            try:
                rel = path.relative_to(repo_root).as_posix()
                mtime = path.stat().st_mtime
            except OSError:
                continue
            status = _status_for_path(rel, mtime)
            is_stale = status == "stale"
            if status == "stale":
                stale += 1
            else:
                pending += 1
            files.append(
                {
                    "filename": path.name,
                    "decision_path": rel,
                    "status": status,
                    "mtime": mtime,
                    "is_stale": is_stale,
                }
            )
    return {"pending": pending, "stale": stale, "files": files}


def _status_badge(status: str) -> str:
    label = status.upper()
    safe = _html.escape(status, quote=True)
    return f'<span class="status-badge {safe}">{_html.escape(label)}</span>'


def render_decisions_index_html(
    repo_root: Path,
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
) -> str:
    payload = build_decisions_index(repo_root)
    decisions = payload["decisions"]
    counts = payload["counts"]
    pending_total = int(counts.get("pending", 0)) + int(counts.get("stale", 0))
    banner = ""
    if pending_total:
        stale = int(counts.get("stale", 0))
        banner_cls = "banner stale" if stale else "banner"
        noun = "decision" if pending_total == 1 else "decisions"
        banner = f'<div class="{banner_cls}">{pending_total} {noun} awaiting your call.</div>'

    rows = []
    for item in decisions:
        row_id = "card-" + str(item["filename"])
        rows.append(
            f'<tr class="decision-card" id="{_html.escape(row_id, quote=True)}">'
            f'<td><a href="{_html.escape(str(item["href"]), quote=True)}">{_html.escape(str(item["title"]))}</a>'
            f'<span>{_html.escape(str(item["decision_path"]))}</span></td>'
            f'<td>{_html.escape(str(item["date"]))}</td>'
            f'<td>{_status_badge(str(item["status"]))}</td>'
            f'<td>{int(item["lineage_counts"]["commits"])}</td>'
            f'<td>{int(item["lineage_counts"]["prs"])}</td>'
            "</tr>"
        )
    body_rows = "\n".join(rows) or '<tr><td colspan="5" class="empty">No decision files found.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Decisions - KubeDojo Local Monitor</title>
  <style>
{render_common_theme()}
{top_nav_css}
    main{{max-width:1120px;margin:0 auto;padding:28px 24px 44px}}
    .page-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;margin-bottom:18px}}
    h1{{font-size:24px;margin:0;letter-spacing:0}}
    .meta{{color:var(--muted);font-size:13px;margin-top:4px}}
    .banner{{border:1px solid rgba(245,158,11,.55);background:rgba(245,158,11,.11);color:#f8d9a0;border-radius:6px;padding:12px 14px;margin-bottom:16px;font-weight:750}}
    .banner.stale{{border-color:rgba(251,113,133,.65);background:rgba(251,113,133,.11);color:#fecdd3}}
{AFK_NOTIFY_CSS}
    table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
    th,td{{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;font-size:13px;vertical-align:middle}}
    th{{background:#121416;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em}}
    tr:last-child td{{border-bottom:0}}
    td a{{color:var(--text);font-weight:800;text-decoration:none}}
    td a:hover{{color:var(--teal)}}
    td span{{display:block;color:var(--muted);font-size:11px;margin-top:2px}}
    .status-badge{{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:10px;font-weight:850;letter-spacing:.04em}}
    .status-badge.decided{{background:rgba(85,209,127,.13);color:#9ef0b7}}
    .status-badge.pending{{background:rgba(245,158,11,.14);color:#f8d9a0}}
    .status-badge.stale{{background:rgba(251,113,133,.14);color:#fecdd3}}
    tr.decision-card:target{{animation:decision-target-highlight 3s ease-out}}
    @keyframes decision-target-highlight{{0%,70%{{outline:2px solid #fde047;background:rgba(253,224,71,.16)}}100%{{outline:2px solid transparent;background:transparent}}}}
    .empty{{color:var(--muted);text-align:center;padding:30px}}
    @media(max-width:760px){{.page-head{{align-items:flex-start;flex-direction:column}}table{{display:block;overflow:auto}}}}
  </style>
</head>
<body>
{render_top_nav_fn("decisions")}
{render_search_widget()}
<main>
  <div class="page-head">
    <div><h1>Decisions</h1><div class="meta">{int(counts["total"])} total · {int(counts["decided"])} decided · {int(counts["pending"])} pending · {int(counts["stale"])} stale</div></div>
  </div>
  {banner}
  <table>
    <thead><tr><th>Title</th><th>Date</th><th>Status</th><th>Citing commits</th><th>Citing PRs</th></tr></thead>
    <tbody>{body_rows}</tbody>
  </table>
</main>
{render_afk_notify_markup()}
</body>
</html>"""


try:
    _refresh_decisions_fts(Path(__file__).resolve().parents[3], create_db=False)
except Exception:
    pass


def _render_markdownish(body: str) -> str:
    lines: list[str] = []
    in_list = False
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h1>{_html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h2>{_html.escape(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            if not in_list:
                lines.append("<ul>")
                in_list = True
            lines.append(f"<li>{_html.escape(line[2:].strip())}</li>")
        elif not line:
            if in_list:
                lines.append("</ul>")
                in_list = False
        else:
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<p>{_html.escape(line)}</p>")
    if in_list:
        lines.append("</ul>")
    return "\n".join(lines)


def _resolve_decision_render_path(repo_root: Path, raw: str) -> Path | None:
    cleaned = unquote(raw).strip("/")
    if cleaned.startswith("pending/"):
        filename = cleaned[len("pending/") :]
        base = repo_root / "docs" / "decisions" / "pending"
    else:
        filename = cleaned
        base = repo_root / "docs" / "decisions"
    if not _SAFE_DECISION_FILENAME_RE.match(filename):
        return None
    path = (base / filename).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        return None
    return path


def _render_decision_not_found_html(
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
    raw_decision: str,
) -> str:
    safe = _html.escape(raw_decision or "unknown", quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Decision not found - KubeDojo Local Monitor</title>
  {DESIGN_SYSTEM_LINK}
  <style>
    :root{{--bg:#101112;--text:#f3f4f2;--muted:#9ca3a3;--topnav-h:45px}}
    body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}}
{top_nav_css}
    main{{max-width:720px;margin:0 auto;padding:48px 24px}}
    h1{{margin:0 0 12px;font-size:24px}}
    p{{color:var(--muted)}}
    a{{color:#3dd6c6}}
  </style>
</head>
<body>
{render_top_nav_fn("decisions")}
<main>
  <h1>Decision not found</h1>
  <p>No decision file matched <code>{safe}</code>.</p>
  <p><a href="/decisions">&larr; Back to decisions</a></p>
</main>
</body>
</html>"""


def render_decision_detail_html(
    repo_root: Path,
    raw_decision: str,
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
    render_markdown_fn: Callable[[str], str] | None = None,
) -> RouteResponse:
    path = _resolve_decision_render_path(repo_root, raw_decision)
    if path is None or not path.exists():
        return (
            404,
            _render_decision_not_found_html(
                top_nav_css=top_nav_css,
                render_top_nav_fn=render_top_nav_fn,
                raw_decision=raw_decision,
            ),
            "text/html; charset=utf-8",
        )
    body = path.read_text(encoding="utf-8")
    title = _decision_title(body, path.name)
    rel = path.relative_to(repo_root).as_posix()
    rendered_body = render_markdown_fn(body) if render_markdown_fn is not None else _render_markdownish(body)
    body_tag = "article" if render_markdown_fn is not None else "div"
    return 200, f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html.escape(title)} - Decisions</title>
  {DESIGN_SYSTEM_LINK}
  <style>
    :root{{--bg:#101112;--panel:#17191b;--line:#30343a;--text:#f3f4f2;--muted:#9ca3a3;--teal:#3dd6c6;--topnav-h:45px}}
    body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}
{top_nav_css}
    main{{max-width:860px;margin:0 auto;padding:28px 24px 52px}}
    a{{color:var(--teal)}}
    .path{{color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;margin-bottom:18px}}
    h1{{font-size:28px;letter-spacing:0;margin:0 0 8px}}
    h2{{font-size:18px;margin:28px 0 8px}}
    p,li{{font-size:14px;color:#e5e7eb}}
    ul{{padding-left:20px}}
  </style>
</head>
<body>
{render_top_nav_fn("decisions")}
<main>
  <a href="/decisions">&larr; Decisions</a>
  <div class="path">{_html.escape(rel)}</div>
  <{body_tag}>{rendered_body}</{body_tag}>
</main>
</body>
</html>""", "text/html; charset=utf-8"


def route_decision_page_request(
    repo_root: Path,
    path: str,
    *,
    top_nav_css: str,
    render_top_nav_fn: Callable[[str], str],
    render_markdown_fn: Callable[[str], str] | None = None,
) -> RouteResponse | None:
    if path == "/decisions":
        return 200, render_decisions_index_html(
            repo_root,
            top_nav_css=top_nav_css,
            render_top_nav_fn=render_top_nav_fn,
        ), "text/html; charset=utf-8"
    if path.startswith("/decisions/"):
        raw = path[len("/decisions/") :]
        return render_decision_detail_html(
            repo_root,
            raw,
            top_nav_css=top_nav_css,
            render_top_nav_fn=render_top_nav_fn,
            render_markdown_fn=render_markdown_fn,
        )
    return None


def route_decision_api_request(repo_root: Path, path: str) -> RouteResponse | None:
    if path == "/api/decisions":
        return _json_response(200, build_decisions_index(repo_root))
    if path == "/api/decisions/pending":
        return _json_response(200, build_pending_decisions(repo_root))
    if path.startswith("/api/decision/") and path.endswith("/lineage"):
        raw = path[len("/api/decision/") : -len("/lineage")]
        filename = unquote(raw).strip("/")
        if not _SAFE_DECISION_FILENAME_RE.match(filename):
            return _json_response(400, {"error": "invalid_decision_filename"})
        decision_path = repo_root / "docs" / "decisions" / filename
        if not decision_path.exists():
            decision_path = repo_root / "docs" / "decisions" / "pending" / filename
        if not decision_path.exists():
            return _json_response(404, {"error": "decision_not_found", "filename": filename})
        try:
            return _json_response(200, scan_decision_lineage(repo_root, decision_path))
        except (FileNotFoundError, ValueError):
            return _json_response(404, {"error": "decision_not_found", "filename": filename})
    return None
