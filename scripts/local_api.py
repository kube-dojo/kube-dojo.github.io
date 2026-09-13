#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import shutil
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_local_api_submodule(short_name: str, filename: str) -> Any:
    """Generic loader for local_api/ submodules (routes + repo_guard).

    Uses a stable sys.modules key so repeated imports are cheap and
    the module is executed only once per process. The dance supports
    both "python -m" / package import and direct script execution.
    """
    module_name = f"_local_api_{short_name}"
    loaded = sys.modules.get(module_name)
    if loaded is not None:
        return loaded
    module_path = Path(__file__).resolve().with_name("local_api") / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        # Produce a readable error like the original per-loader messages
        # (e.g. "cannot load channels from ..." or "cannot load guard from ...")
        # instead of the ugly "cannot load routes_channels from ...".
        display = short_name.replace("routes_", "").replace("repo_", "").replace("_", " ")
        raise ImportError(f"cannot load {display} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_channel_routes_module() -> Any:
    return _load_local_api_submodule("routes_channels", "routes/channels.py")


def _load_decision_routes_module() -> Any:
    return _load_local_api_submodule("routes_decisions", "routes/decisions.py")


def _load_search_routes_module() -> Any:
    return _load_local_api_submodule("routes_search", "routes/search.py")


def _load_ui_fragments_module() -> Any:
    return _load_local_api_submodule("routes_ui_fragments", "routes/ui_fragments.py")


def _load_repo_guard_module() -> Any:
    return _load_local_api_submodule("repo_guard", "repo_guard.py")


def _ui_fragments_module() -> Any:
    return _load_ui_fragments_module()


def _repo_guard_module() -> Any:
    return _load_repo_guard_module()


def _design_system_link() -> str:
    return _ui_fragments_module().DESIGN_SYSTEM_LINK


def _render_page_chrome(*, include_afk: bool = False) -> str:
    return _ui_fragments_module().render_global_chrome(include_search=True, include_afk=include_afk)


def _poll_stale_css() -> str:
    return _ui_fragments_module().POLL_STALE_CSS


def _render_poll_stale_script() -> str:
    return _ui_fragments_module().render_poll_stale_script()


_CHANNEL_ROUTES = _load_channel_routes_module()
_DECISION_ROUTES = _load_decision_routes_module()
_SEARCH_ROUTES = _load_search_routes_module()

# Heavy imports (pipeline_v2, status, translation_v2, ztt_status) are deferred
# into the handlers that actually need them. Measured: moving these out of the
# module top saves ~150 ms from server startup and keeps /healthz and
# /api/runtime/services paths dependency-free. See issue #258.


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8768
DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
GH_REPO = "kube-dojo/kube-dojo.github.io"
GH_CACHE_TTL_SECONDS = 60.0
GENERATED_PREFIXES = (
    ".astro/",
    ".dispatch-logs/",
    ".review-results/",
    "dist/",
    "logs/",
    "site/",
)
PIPELINE_PREFIXES = (
    ".bridge/",
    ".pipeline/",
    ".pids/",
)
DEFAULT_FEEDBACK_ISSUE = 248
RUNTIME_SERVICES = (
    {"name": "dev", "pid_file": ".pids/dev.pid", "port": 4333, "label": "Astro Dev Server"},
    {"name": "api", "pid_file": ".pids/api.pid", "port": 8768, "label": "Deterministic Local API"},
    {"name": "feedback", "pid_file": ".pids/feedback.pid", "port": None, "label": "GitHub Issue Watcher"},
    {"name": "v2-write-worker", "pid_file": ".pids/v2-write-worker.pid", "port": None, "label": "V2 Write Worker"},
    {"name": "v2-review-worker", "pid_file": ".pids/v2-review-worker.pid", "port": None, "label": "V2 Review Worker"},
    {"name": "v2-patch-worker", "pid_file": ".pids/v2-patch-worker.pid", "port": None, "label": "V2 Patch Worker"},
)
RUNTIME_SERVICE_ORDER = tuple(svc["name"] for svc in RUNTIME_SERVICES)

# Module keys are hierarchical slugs under src/content/docs, e.g.
# "prerequisites/zero-to-terminal/module-0.1-alpha". Segments only allow
# lowercase ascii, digits, dots, dashes, and underscores. NO "..", no "/"
# at the edges, no absolute paths. The per-segment check rejects traversal
# attempts like "..", ".", or leading-dot hidden names.
_MODULE_KEY_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ETAG_HEADER_RE = re.compile(r'^(?:W/)?"[A-Za-z0-9_./:-]+"$')
_HANDOFF_FILENAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<label>.+)\.(?P<format>md|html)$")


def _validate_module_key(repo_root: Path, raw: str) -> str | None:
    """Normalize and validate a module-key slug.

    Returns the normalized key (".md" suffix stripped) if safe, else None.
    Rejects path-traversal patterns and anything that would resolve outside
    src/content/docs.
    """
    if not raw:
        return None
    normalized = raw[:-3] if raw.endswith(".md") else raw
    if not normalized or normalized.startswith("/") or normalized.endswith("/"):
        return None
    segments = normalized.split("/")
    for segment in segments:
        if segment in ("", ".", "..") or not _MODULE_KEY_SEGMENT_RE.match(segment):
            return None
    docs_root = (repo_root / "src" / "content" / "docs").resolve()
    try:
        candidate = (docs_root / f"{normalized}.md").resolve()
        candidate.relative_to(docs_root)
    except (OSError, ValueError):
        return None
    return normalized


def _header_value_has_crlf(value: str) -> bool:
    return "\r" in value or "\n" in value


def _safe_header_value(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def _safe_etag_header_value(etag: str) -> str:
    safe = _safe_header_value(etag)
    if _ETAG_HEADER_RE.match(safe):
        return safe
    return _weak_etag(safe.encode("utf-8"))


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


# ============================================================
# Build jobs (/api/build/run + /api/build/status)
# ============================================================


_BUILD_JOBS_LOCK = threading.Lock()
_BUILD_JOBS_STATE: dict[str, dict[str, Any]] = {}
_BUILD_JOBS_FILENAME = ".cache/build_jobs.json"
_BUILD_JOBS_MAX = 10
_BUILD_TAIL_LINES = 30
_WARNING_LINE_RE = re.compile(r"\bwarning\b", re.IGNORECASE)


def _build_jobs_path(repo_root: Path) -> Path:
    return repo_root / _BUILD_JOBS_FILENAME


def _read_build_jobs(repo_root: Path) -> list[dict[str, Any]]:
    path = _build_jobs_path(repo_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("jobs", [])
    if not isinstance(payload, list):
        return []
    return [job for job in payload if isinstance(job, dict)]


def _write_build_jobs(repo_root: Path, jobs: list[dict[str, Any]]) -> None:
    path = _build_jobs_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(jobs[-_BUILD_JOBS_MAX :], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _reset_build_jobs_state() -> None:
    """Test helper: drop in-memory build-job state across repos."""
    with _BUILD_JOBS_LOCK:
        _BUILD_JOBS_STATE.clear()


def _trim_tail(lines: list[str]) -> list[str]:
    return lines[-_BUILD_TAIL_LINES :]


def _normalize_warning_line(line: str) -> str | None:
    normalized = " ".join(line.strip().split())
    if not normalized or not _WARNING_LINE_RE.search(normalized):
        return None
    return normalized


def _find_build_job_locked(state: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    for job in reversed(state["jobs"]):
        if job.get("job_id") == job_id:
            return job
    return None


def _persist_build_state_locked(repo_root: Path, state: dict[str, Any]) -> None:
    state["jobs"] = state["jobs"][-_BUILD_JOBS_MAX :]
    _write_build_jobs(repo_root, state["jobs"])


def _load_build_state(repo_root: Path) -> dict[str, Any]:
    repo_key = str(repo_root.resolve())
    with _BUILD_JOBS_LOCK:
        state = _BUILD_JOBS_STATE.get(repo_key)
        if state is not None:
            return state
        jobs = _read_build_jobs(repo_root)[-_BUILD_JOBS_MAX :]
        repaired = False
        now = time.time()
        for job in jobs:
            if job.get("state") != "running":
                continue
            started_at = float(job.get("started_at") or now)
            tail = list(job.get("last_30_lines") or [])
            tail.append("local_api: build job marked failed after API restart")
            job["state"] = "fail"
            job["finished_at"] = now
            job["duration_s"] = round(max(0.0, now - started_at), 3)
            job["last_30_lines"] = _trim_tail(tail)
            job["new_warnings"] = sorted(set(job.get("new_warnings") or []))
            repaired = True
        state = {"jobs": jobs, "active_job_id": None}
        if repaired:
            _persist_build_state_locked(repo_root, state)
        _BUILD_JOBS_STATE[repo_key] = state
        return state


def _spawn_build_process(repo_root: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["npm", "run", "build"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def _build_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    started_at = float(job["started_at"])
    if job.get("state") == "running":
        duration_s = round(max(0.0, time.time() - started_at), 3)
    else:
        duration_s = job.get("duration_s")
    return {
        "job_id": job["job_id"],
        "started_at": started_at,
        "state": job["state"],
        "duration_s": duration_s,
        "last_30_lines": list(job.get("last_30_lines") or []),
        "new_warnings": list(job.get("new_warnings") or []),
        "finished_at": job.get("finished_at"),
    }


def _monitor_build_job(repo_root: Path, job_id: str, process: subprocess.Popen[str]) -> None:
    state = _load_build_state(repo_root)
    if process.stdout is not None:
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            warning = _normalize_warning_line(line)
            with _BUILD_JOBS_LOCK:
                job = _find_build_job_locked(state, job_id)
                if job is None:
                    continue
                tail = list(job.get("last_30_lines") or [])
                tail.append(line)
                job["last_30_lines"] = _trim_tail(tail)
                warning_set = set(job.get("warning_set") or [])
                if warning is not None:
                    warning_set.add(warning)
                baseline = set(job.get("baseline_warning_set") or [])
                job["warning_set"] = sorted(warning_set)
                job["new_warnings"] = sorted(warning_set - baseline)
                _persist_build_state_locked(repo_root, state)
        process.stdout.close()

    return_code = process.wait()
    finished_at = time.time()
    with _BUILD_JOBS_LOCK:
        job = _find_build_job_locked(state, job_id)
        if job is None:
            return
        baseline = set(job.get("baseline_warning_set") or [])
        warning_set = set(job.get("warning_set") or [])
        job["state"] = "pass" if return_code == 0 else "fail"
        job["finished_at"] = finished_at
        job["duration_s"] = round(max(0.0, finished_at - float(job["started_at"])), 3)
        job["new_warnings"] = sorted(warning_set - baseline)
        job.pop("baseline_warning_set", None)
        if state.get("active_job_id") == job_id:
            state["active_job_id"] = None
        _persist_build_state_locked(repo_root, state)


def start_build_job(repo_root: Path) -> tuple[int, Any, str]:
    state = _load_build_state(repo_root)
    with _BUILD_JOBS_LOCK:
        active_job_id = state.get("active_job_id")
        if active_job_id:
            active_job = _find_build_job_locked(state, active_job_id)
            if active_job is not None and active_job.get("state") == "running":
                return (
                    409,
                    {
                        "error": "build_in_progress",
                        "job_id": active_job_id,
                        "started_at": active_job.get("started_at"),
                    },
                    "application/json; charset=utf-8",
                )
            state["active_job_id"] = None

        previous_green_warnings: set[str] = set()
        for previous_job in reversed(state["jobs"]):
            if previous_job.get("state") == "pass":
                previous_green_warnings = set(previous_job.get("warning_set") or [])
                break

        started_at = time.time()
        job_id = f"build-{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "started_at": started_at,
            "state": "running",
            "duration_s": None,
            "finished_at": None,
            "last_30_lines": [],
            "warning_set": [],
            "baseline_warning_set": sorted(previous_green_warnings),
            "new_warnings": [],
        }
        state["jobs"].append(job)
        state["active_job_id"] = job_id
        _persist_build_state_locked(repo_root, state)

    try:
        process = _spawn_build_process(repo_root)
    except OSError as exc:
        finished_at = time.time()
        with _BUILD_JOBS_LOCK:
            failed_job = _find_build_job_locked(state, job_id)
            if failed_job is not None:
                failed_job["state"] = "fail"
                failed_job["finished_at"] = finished_at
                failed_job["duration_s"] = round(max(0.0, finished_at - started_at), 3)
                failed_job["last_30_lines"] = [f"local_api: failed to start build: {exc}"]
                failed_job.pop("baseline_warning_set", None)
                state["active_job_id"] = None
                _persist_build_state_locked(repo_root, state)
        return (
            500,
            {"error": "build_spawn_failed", "job_id": job_id, "message": str(exc)},
            "application/json; charset=utf-8",
        )

    threading.Thread(
        target=_monitor_build_job,
        args=(repo_root, job_id, process),
        daemon=True,
    ).start()
    return 202, {"job_id": job_id, "started_at": started_at}, "application/json; charset=utf-8"


def get_build_job_status(repo_root: Path, job_id: str) -> tuple[int, Any, str]:
    state = _load_build_state(repo_root)
    with _BUILD_JOBS_LOCK:
        job = _find_build_job_locked(state, job_id)
        if job is None:
            return 404, {"error": "build_job_not_found", "job_id": job_id}, "application/json; charset=utf-8"
        return 200, _build_job_payload(job), "application/json; charset=utf-8"


# ============================================================
# Response cache + ETag + background snapshot
# ============================================================
#
# Design notes (per reviewer feedback on issue #258):
#   - Cache stores response BYTES, not payload dicts. ETag = weak hash of
#     bytes. Reusing cached bytes makes ETag stable and 304 cheap.
#   - Cache key = normalized (repo_root, path, sorted-query). Avoids
#     cross-repo contamination when two repos share one process.
#   - Invalidation combines TTL + per-endpoint dependency versions. For
#     sqlite deps the version is ``PRAGMA data_version`` on a persistent
#     per-path read-only connection (the documented/reliable usage — see
#     _sqlite_version_key). The connection is also probed for inode/device
#     changes so a replaced DB file is detected.
#   - Background snapshots use fixed-*delay* (not fixed-interval): sleep
#     runs AFTER the refresh completes, so an overrun does not cause
#     overlapping runs. A per-instance build lock enforces single-in-
#     flight across refresh_blocking() and the daemon thread.


_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, "_CacheEntry"] = {}


class _CacheEntry:
    __slots__ = (
        "body_bytes",
        "content_type",
        "etag",
        "expires_at",
        "version_key",
        "built_at",
    )

    def __init__(
        self,
        body_bytes: bytes,
        content_type: str,
        etag: str,
        expires_at: float,
        version_key: tuple,
        built_at: float,
    ) -> None:
        self.body_bytes = body_bytes
        self.content_type = content_type
        self.etag = etag
        self.expires_at = expires_at
        self.version_key = version_key
        self.built_at = built_at


def _weak_etag(body_bytes: bytes) -> str:
    return 'W/"sha256:' + hashlib.sha256(body_bytes).hexdigest()[:16] + '"'


def _path_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _venv_python_for_repo(repo_root: Path) -> str:
    # Candidate roots intentionally include ancestry to cope with
    # git worktree layouts (module under .worktrees/<branch>/),
    # while preventing runaway traversal toward `/`.
    max_ancestry = 5
    base = repo_root
    for _ in range(max_ancestry + 1):
        candidate = base / ".venv" / "bin" / "python"
        if candidate.exists():
            return str(candidate)
        if base == Path("/") or base == base.parent:
            break
        base = base.parent
    raise FileNotFoundError(
        f"Could not locate .venv/bin/python within {max_ancestry} parent levels of {repo_root}"
    )


# Persistent read-only sqlite connections keyed by absolute db path.
# ``PRAGMA data_version`` returns a monotonic counter on a specific
# connection that increments whenever ANOTHER connection commits a
# write. So a single persistent connection, queried repeatedly, is a
# reliable change signal — unlike round-1's fresh-connection misuse.
# The dict lock serializes access; sqlite itself is single-writer,
# and we only keep one persistent reader per db for bookkeeping.
#
# We also cache ``(st_dev, st_ino)`` alongside each connection. If the
# DB file is REPLACED (rename/copy rather than in-place modify) the
# inode changes and we must drop the cached connection — otherwise it
# stays attached to the old inode and keeps reporting the old version.
_SQLITE_VERSION_CONNECTIONS: dict[str, tuple[sqlite3.Connection, tuple]] = {}
_SQLITE_VERSION_LOCK = threading.Lock()


def _close_all_sqlite_version_connections() -> None:
    """Test helper: drop cached read-only connections (e.g. between
    tests that recreate DB files at the same path)."""
    with _SQLITE_VERSION_LOCK:
        for conn, _ident in _SQLITE_VERSION_CONNECTIONS.values():
            try:
                conn.close()
            except sqlite3.Error:
                pass
        _SQLITE_VERSION_CONNECTIONS.clear()


def _file_identity(path: Path) -> tuple:
    """Return ``(st_dev, st_ino)`` or ``None`` fallback. Used to detect
    whether a file at the same path is the *same* file or a replacement."""
    try:
        s = path.stat()
    except OSError:
        return (0, 0)
    return (s.st_dev, s.st_ino)


def _sqlite_version_key(db_path: Path) -> tuple:
    """Fingerprint a sqlite DB using ``PRAGMA data_version`` on a
    persistent read-only connection.

    Contract: two calls return the same key iff no other connection
    has committed between them *and* the file at ``db_path`` is the
    same inode. If the file has been replaced (different inode), the
    cached connection is dropped and reopened. This catches every
    form of write (WAL append, WAL reuse after checkpoint, in-place
    DELETE/MEMORY writes, rapid same-size writes inside one mtime
    granule) plus DB replacement — none of which ``(mtime, size)``
    alone can distinguish.
    """
    if not db_path.exists():
        return ("absent",)

    key = str(db_path.resolve())
    identity = _file_identity(db_path)
    with _SQLITE_VERSION_LOCK:
        cached = _SQLITE_VERSION_CONNECTIONS.get(key)
        if cached is not None:
            conn, cached_identity = cached
            if cached_identity != identity:
                # File was replaced (different inode). Close the stale
                # handle and open a new one below.
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
                _SQLITE_VERSION_CONNECTIONS.pop(key, None)
                cached = None
        if cached is None:
            try:
                conn = sqlite3.connect(
                    f"file:{db_path}?mode=ro",
                    uri=True,
                    timeout=1.0,
                    check_same_thread=False,
                )
            except sqlite3.Error:
                return ("open_failed", _path_mtime(db_path))
            _SQLITE_VERSION_CONNECTIONS[key] = (conn, identity)
        else:
            conn, _ = cached

        try:
            row = conn.execute("PRAGMA data_version").fetchone()
            data_version = int(row[0]) if row is not None else 0
        except sqlite3.Error:
            # Connection poisoned — drop so the next call opens fresh.
            _SQLITE_VERSION_CONNECTIONS.pop(key, None)
            try:
                conn.close()
            except sqlite3.Error:
                pass
            return ("error", _path_mtime(db_path))

    return ("v", identity, data_version)


def _normalized_cache_key(
    path: str,
    query: dict[str, list[str]],
    repo_root: Path | None = None,
) -> str:
    """Normalize (repo_root, path, sorted-query) for stable cache/ETag keys.

    ``repo_root`` is included so two different repos sharing one Python
    process (e.g. the test suite) don't cross-contaminate each other's
    cache. The default of ``None`` keeps backward-compat for callers that
    only key by path + query.
    """
    prefix = f"{Path(repo_root).resolve()}::" if repo_root is not None else ""
    if not query:
        return prefix + path
    parts = []
    for k in sorted(query):
        for v in query[k]:
            parts.append(f"{k}={v}")
    return prefix + path + "?" + "&".join(parts)


def _serialize_payload(payload: Any, content_type: str) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if content_type.startswith("application/json"):
        return json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode("utf-8")
    if content_type.startswith("text/html"):
        return str(payload).encode("utf-8")
    return str(payload).encode("utf-8")


def cached_response(
    cache_key: str,
    ttl_seconds: float,
    version_fn: Callable[[], tuple],
    builder: Callable[[], tuple[int, Any, str]],
    etag_builder: Callable[[Any, bytes], str] | None = None,
) -> tuple[int, bytes, str, str]:
    """Serve a response through the cache. Returns (status, body_bytes, content_type, etag).

    Cache is skipped on non-2xx responses.
    """
    now = time.time()
    version_key = version_fn()
    with _CACHE_LOCK:
        entry = _CACHE.get(cache_key)
        if (
            entry is not None
            and entry.expires_at > now
            and entry.version_key == version_key
        ):
            return 200, entry.body_bytes, entry.content_type, entry.etag

    status_code, payload, content_type = builder()
    body_bytes = _serialize_payload(payload, content_type)
    etag = etag_builder(payload, body_bytes) if etag_builder is not None else _weak_etag(body_bytes)

    if 200 <= status_code < 300:
        with _CACHE_LOCK:
            _CACHE[cache_key] = _CacheEntry(
                body_bytes=body_bytes,
                content_type=content_type,
                etag=etag,
                expires_at=now + ttl_seconds,
                version_key=version_key,
                built_at=now,
            )
    return status_code, body_bytes, content_type, etag


def _cache_stats() -> dict[str, Any]:
    with _CACHE_LOCK:
        return {
            "entries": len(_CACHE),
            "keys": sorted(_CACHE.keys()),
        }


def _gh_json_fields(*fields: str) -> str:
    return ",".join(fields)


def _gh_repo_cmd(*args: str) -> list[str]:
    return ["gh", *args, "--repo", GH_REPO]


def _run_gh_json(*args: str, timeout: int = 10) -> tuple[int, Any]:
    try:
        result = subprocess.run(
            _gh_repo_cmd(*args),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return 503, {"error": "gh CLI not available"}
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Could not resolve to an issue or pull request" in stderr:
            return 404, {"error": "not_found"}
        return 502, {"error": "gh command failed", "message": stderr or "gh command failed"}
    try:
        return 200, json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return 502, {"error": "invalid_gh_json", "message": str(exc)}


def _normalize_gh_item(item: dict[str, Any]) -> dict[str, Any]:
    labels = item.get("labels") or []
    assignees = item.get("assignees") or []
    comments = item.get("comments") or []
    return {
        "number": item.get("number"),
        "title": item.get("title", ""),
        "state": item.get("state", ""),
        "labels": [
            label.get("name")
            for label in labels
            if isinstance(label, dict) and label.get("name")
        ],
        "assignees": [
            assignee.get("login")
            for assignee in assignees
            if isinstance(assignee, dict) and assignee.get("login")
        ],
        "comments_count": len(comments) if isinstance(comments, list) else 0,
        "updated_at": item.get("updatedAt", ""),
        "url": item.get("url", ""),
    }


def _normalize_gh_comments(comments: Any) -> list[dict[str, Any]]:
    if not isinstance(comments, list):
        return []
    normalized: list[dict[str, Any]] = []
    for comment in comments[-5:]:
        if not isinstance(comment, dict):
            continue
        author = comment.get("author") or {}
        normalized.append(
            {
                "author": author.get("login", "") if isinstance(author, dict) else "",
                "body": comment.get("body", ""),
                "created_at": comment.get("createdAt", ""),
                "url": comment.get("url", ""),
            }
        )
    return normalized


def _build_gh_list(kind: str, state: str, limit: int) -> tuple[int, Any, str]:
    status_code, payload = _run_gh_json(
        kind,
        "list",
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        _gh_json_fields("number", "title", "state", "labels", "assignees", "comments", "updatedAt", "url"),
    )
    if status_code != 200:
        return status_code, payload, "application/json; charset=utf-8"
    items = [
        _normalize_gh_item(item)
        for item in payload
        if isinstance(item, dict)
    ]
    return 200, {
        "repo": GH_REPO,
        "state": state,
        "limit": limit,
        "count": len(items),
        "items": items,
    }, "application/json; charset=utf-8"


def _build_gh_detail(kind: str, number: int) -> tuple[int, Any, str]:
    fields = ["number", "title", "state", "labels", "assignees", "comments", "updatedAt", "url"]
    if kind == "pr":
        fields.append("mergeable")
    status_code, payload = _run_gh_json(
        kind,
        "view",
        str(number),
        "--json",
        _gh_json_fields(*fields),
    )
    if status_code != 200:
        return status_code, payload, "application/json; charset=utf-8"
    if not isinstance(payload, dict):
        return 502, {"error": "invalid_gh_json", "message": "expected object"}, "application/json; charset=utf-8"
    item = _normalize_gh_item(payload)
    item["comments"] = _normalize_gh_comments(payload.get("comments"))
    if kind == "pr":
        item["mergeable"] = payload.get("mergeable")
    return 200, item, "application/json; charset=utf-8"


def _is_gh_path(path: str) -> bool:
    return (
        path in {"/api/gh/issues", "/api/gh/prs"}
        or path.startswith("/api/gh/issues/")
        or path.startswith("/api/gh/prs/")
    )


def _gh_payload_etag(path: str, payload: Any) -> str:
    latest = "empty"
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            updated_values = [
                item.get("updated_at", "")
                for item in items
                if isinstance(item, dict) and item.get("updated_at")
            ]
            if updated_values:
                latest = max(updated_values)
        elif payload.get("updated_at"):
            latest = str(payload["updated_at"])
    return _weak_etag(f"{path}:{latest}".encode("utf-8"))


# --- Background snapshot ---


class BackgroundSnapshot:
    """Fixed-delay background refresher for an expensive builder.

    Guarantees:
        - Never more than one refresh in flight.
        - Atomic snapshot swap: callers see either the old or new snapshot,
          never a partial one.
        - Exposes freshness metadata so callers can detect staleness.
    """

    def __init__(
        self,
        key: str,
        interval_seconds: float,
        builder: Callable[[], Any],
        stale_threshold_seconds: float | None = None,
    ) -> None:
        self.key = key
        self.interval_seconds = interval_seconds
        self.builder = builder
        # Default stale threshold: 5x refresh interval, min 60s.
        self.stale_threshold_seconds = (
            stale_threshold_seconds
            if stale_threshold_seconds is not None
            else max(60.0, interval_seconds * 5)
        )
        # ``_lock`` protects metadata reads; ``_build_lock`` enforces
        # single-in-flight so ``refresh_blocking()`` and the background
        # thread cannot overlap each other's build.
        self._lock = threading.Lock()
        self._build_lock = threading.Lock()
        self._snapshot: Any = None
        self._started_at: float | None = None
        self._completed_at: float | None = None
        self._duration_ms: float | None = None
        self._last_error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name=f"snapshot-{self.key}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._refresh_once()
            # Fixed-delay: sleep AFTER completion so overruns never overlap.
            self._stop.wait(self.interval_seconds)

    def _refresh_once_locked(self) -> None:
        """Core refresh, assuming ``_build_lock`` is already held."""
        started = time.time()
        with self._lock:
            self._started_at = started
        try:
            snapshot = self.builder()
            err: str | None = None
        except Exception as exc:  # noqa: BLE001
            snapshot = None
            err = f"{type(exc).__name__}: {exc}"
        completed = time.time()
        with self._lock:
            if snapshot is not None:
                self._snapshot = snapshot
            self._completed_at = completed
            self._duration_ms = (completed - started) * 1000.0
            self._last_error = err

    def _refresh_once(self) -> None:
        """Serialize all builders through ``_build_lock``. The real
        enforcement of the "single in-flight" guarantee."""
        with self._build_lock:
            self._refresh_once_locked()

    def refresh_blocking(self, timeout: float | None = None) -> bool:
        """Trigger one refresh in the calling thread. Returns True if
        the refresh ran, False if ``timeout`` elapsed while waiting
        for the build lock. ``timeout=None`` waits forever."""
        lock_timeout = -1.0 if timeout is None else float(timeout)
        acquired = self._build_lock.acquire(timeout=lock_timeout)
        if not acquired:
            return False
        try:
            self._refresh_once_locked()
        finally:
            self._build_lock.release()
        return True

    def get(self) -> tuple[Any, dict[str, Any]]:
        now = time.time()
        with self._lock:
            snapshot = self._snapshot
            started = self._started_at
            completed = self._completed_at
            duration = self._duration_ms
            error = self._last_error
        stale_seconds = (now - completed) if completed is not None else None
        in_flight = (
            started is not None and (completed is None or started > completed)
        )
        if snapshot is None and completed is None:
            # Never completed a refresh — the caller will have to build sync.
            state = "refreshing"
        elif snapshot is None and error is not None:
            state = "degraded"
        elif stale_seconds is not None and stale_seconds > self.stale_threshold_seconds:
            state = "stale"
        else:
            state = "fresh"
        meta = {
            "refresh_started_at": started,
            "refresh_completed_at": completed,
            "refresh_duration_ms": duration,
            "refresh_error": error,
            "stale_seconds": stale_seconds,
            "stale_threshold_seconds": self.stale_threshold_seconds,
            "freshness_state": state,
            "refresh_in_flight": in_flight,
        }
        return snapshot, meta


# Registry of background snapshots. Started lazily on first access so that
# unit tests and `--help` invocations don't spawn threads.
_SNAPSHOTS: dict[str, BackgroundSnapshot] = {}
_SNAPSHOTS_LOCK = threading.Lock()


def _register_snapshot(
    key: str,
    interval_seconds: float,
    builder: Callable[[], Any],
    stale_threshold_seconds: float | None = None,
) -> BackgroundSnapshot:
    with _SNAPSHOTS_LOCK:
        existing = _SNAPSHOTS.get(key)
        if existing is not None:
            return existing
        snap = BackgroundSnapshot(key, interval_seconds, builder, stale_threshold_seconds)
        _SNAPSHOTS[key] = snap
    return snap


def _classify_path(path: str) -> str:
    if path.startswith(GENERATED_PREFIXES):
        return "generated"
    if path.startswith(PIPELINE_PREFIXES):
        return "pipeline"
    if path.startswith("src/") or path.startswith("scripts/") or path.startswith("tests/") or path.startswith("docs/"):
        return "source"
    return "other"


def build_worktree_status(repo_root: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--branch"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "repo_root": str(repo_root),
            "ok": False,
            "error": f"git status unavailable: {type(exc).__name__}",
        }
    if result.returncode != 0:
        return {
            "repo_root": str(repo_root),
            "ok": False,
            "error": result.stderr.strip() or "git status failed",
        }

    lines = result.stdout.splitlines()
    branch = ""
    ahead = 0
    behind = 0
    if lines and lines[0].startswith("## "):
        branch_line = lines[0][3:]
        branch = branch_line
        if "..." in branch_line:
            branch = branch_line.split("...", 1)[0]
        if "[ahead " in branch_line:
            ahead = int(branch_line.split("[ahead ", 1)[1].split("]", 1)[0].split(",")[0])
        if "[behind " in branch_line:
            behind = int(branch_line.split("[behind ", 1)[1].split("]", 1)[0].split(",")[0])

    entries: list[dict[str, Any]] = []
    counts = {
        "total": 0,
        "staged": 0,
        "unstaged": 0,
        "untracked": 0,
        "conflicted": 0,
    }
    categories = {"source": 0, "generated": 0, "pipeline": 0, "other": 0}

    for line in lines[1:]:
        if not line.strip():
            continue
        if line.startswith("?? "):
            path = line[3:]
            staged = False
            unstaged = False
            untracked = True
            conflicted = False
            index_status = "?"
            worktree_status = "?"
        else:
            index_status = line[0]
            worktree_status = line[1]
            path = line[3:]
            staged = index_status not in {" ", "?"}
            unstaged = worktree_status not in {" ", "?"}
            untracked = False
            conflicted = index_status == "U" or worktree_status == "U"
        category = _classify_path(path)
        counts["total"] += 1
        counts["staged"] += int(staged)
        counts["unstaged"] += int(unstaged)
        counts["untracked"] += int(untracked)
        counts["conflicted"] += int(conflicted)
        categories[category] += 1
        entries.append(
            {
                "path": path,
                "index_status": index_status,
                "worktree_status": worktree_status,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "conflicted": conflicted,
                "category": category,
            }
        )

    return {
        "repo_root": str(repo_root),
        "ok": True,
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "dirty": counts["total"] > 0,
        "counts": counts,
        "categories": categories,
        "entries": entries,
    }


def build_worktrees_list(repo_root: Path) -> dict[str, Any]:
    """List every worktree attached to the primary repo.

    Parses ``git worktree list --porcelain``. Returns a compact payload
    suitable for agent cold-start: agents need to know about sibling
    worktrees (e.g. ``codex-wt-*``) to avoid colliding on the same branch.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "error": f"git worktree list unavailable: {type(exc).__name__}",
            "worktrees": [],
        }
    if result.returncode != 0:
        return {
            "ok": False,
            "error": result.stderr.strip() or "git worktree list failed",
            "worktrees": [],
        }

    worktrees: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in result.stdout.splitlines():
        if not line:
            if current is not None:
                worktrees.append(current)
                current = None
            continue
        if line.startswith("worktree "):
            if current is not None:
                worktrees.append(current)
            current = {
                "path": line[len("worktree ") :],
                "branch": None,
                "head": None,
                "detached": False,
                "locked": False,
                "prunable": False,
            }
        elif current is None:
            continue
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            # Format: ``branch refs/heads/<name>``.
            ref = line[len("branch ") :]
            if ref.startswith("refs/heads/"):
                current["branch"] = ref[len("refs/heads/") :]
            else:
                current["branch"] = ref
        elif line == "detached":
            current["detached"] = True
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    if current is not None:
        worktrees.append(current)

    # Enrich each entry with a dirty-counts summary. This is the
    # signal operators actually want ("which worktree is lively?")
    # and without it agents had to shell into every worktree.
    #
    # ``dirty`` is tri-state: True/False when counts were obtained,
    # ``None`` when we couldn't read the worktree (missing path,
    # permission error, prunable ref). "unknown" and "clean" are
    # materially different; a False here would be a false negative.
    for wt in worktrees:
        wt_path = Path(wt["path"])
        counts = _worktree_dirty_counts(wt_path) if wt_path.exists() else None
        wt["counts"] = counts
        if counts is None:
            wt["dirty"] = None
        else:
            wt["dirty"] = bool(counts.get("total", 0))

    primary_path = str(repo_root)
    return {
        "ok": True,
        "primary": primary_path,
        "count": len(worktrees),
        "worktrees": worktrees,
    }


def _worktree_dirty_counts(worktree_path: Path) -> dict[str, Any] | None:
    """Run ``git status --porcelain=v1`` inside ``worktree_path`` and
    return a summary of counts. Returns ``None`` on failure so callers
    can distinguish "unknown" from "clean".

    ``total`` counts each PATH once (matching the primary-worktree
    ``build_worktree_status`` semantics), so a file that is both
    staged and unstaged adds 1, not 2. ``staged`` / ``unstaged`` /
    ``untracked`` remain per-status counts for operators who want
    breakdowns — those may overlap.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    staged = unstaged = untracked = conflicted = 0
    total_paths = 0
    for line in result.stdout.splitlines():
        if not line:
            continue
        total_paths += 1
        if line.startswith("?? "):
            untracked += 1
            continue
        idx = line[0] if line else " "
        wt = line[1] if len(line) > 1 else " "
        if idx == "U" or wt == "U":
            conflicted += 1
        if idx not in (" ", "?"):
            staged += 1
        if wt not in (" ", "?"):
            unstaged += 1
    return {
        # ``total`` is unique-path count (matches primary-worktree
        # ``build_worktree_status``). staged/unstaged/untracked are
        # per-status counts and may overlap — a file with both a
        # staged and an unstaged change is in both sub-counts but
        # contributes 1 to total.
        "total": total_paths,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "conflicted": conflicted,
    }


def build_git_cleanup_report(repo_root: Path) -> dict[str, Any]:
    """Local branches + worktrees safe to prune.

    A branch is prunable if it's merged into ``main`` (explicit merge commit)
    OR its upstream is marked ``[gone]`` — the repo has ``delete_branch_on_merge``
    enabled on GitHub, so a gone upstream means a squash/rebase-merged PR.

    A worktree is prunable if its branch is prunable AND it has zero
    TRACKED dirty entries (untracked ``.venv``/``.cache`` artifacts are ignored).
    """
    merged: set[str] = set()
    try:
        r = subprocess.run(
            ["git", "branch", "--merged", "main", "--format=%(refname:short)"],
            cwd=repo_root, capture_output=True, text=True, check=False, timeout=5,
        )
        if r.returncode == 0:
            for name in r.stdout.splitlines():
                name = name.strip()
                if name and name != "main":
                    merged.add(name)
    except (OSError, subprocess.TimeoutExpired):
        pass

    gone: set[str] = set()
    try:
        r = subprocess.run(
            ["git", "for-each-ref",
             "--format=%(refname:short)\t%(upstream:track)",
             "refs/heads/"],
            cwd=repo_root, capture_output=True, text=True, check=False, timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                parts = line.rstrip().split("\t", 1)
                if len(parts) == 2 and "[gone]" in parts[1]:
                    gone.add(parts[0])
    except (OSError, subprocess.TimeoutExpired):
        pass

    prunable = sorted(merged | gone)
    reasons: dict[str, list[str]] = {}
    for b in prunable:
        r_ = []
        if b in merged:
            r_.append("merged")
        if b in gone:
            r_.append("upstream-gone")
        reasons[b] = r_

    wt_list = build_worktrees_list(repo_root).get("worktrees", [])
    prunable_worktrees: list[dict[str, Any]] = []
    primary = str(repo_root)
    for wt in wt_list:
        if wt.get("path") == primary:
            continue
        br = wt.get("branch")
        counts = wt.get("counts") or {}
        tracked_dirty = (
            counts.get("staged", 0)
            + counts.get("unstaged", 0)
            + counts.get("conflicted", 0)
        )
        if br and br in (merged | gone) and not tracked_dirty:
            prunable_worktrees.append({
                "path": wt["path"],
                "branch": br,
                "reasons": reasons.get(br, []),
            })

    return {
        "ok": True,
        "prunable_branches": [{"name": b, "reasons": reasons[b]} for b in prunable],
        "prunable_worktrees": prunable_worktrees,
        "counts": {
            "branches": len(prunable),
            "worktrees": len(prunable_worktrees),
        },
        "hint": "git cleanup-merged  # aliased; removes gone-upstream local branches",
    }


def _db_latest_for_module(db_path: Path, module_key: str) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        job = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE module_key = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (module_key,),
        ).fetchone()
        event = conn.execute(
            """
            SELECT *
            FROM events
            WHERE module_key = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (module_key,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "db_path": str(db_path),
        "latest_job": dict(job) if job is not None else None,
        "latest_event": (
            {**dict(event), "payload_json": _load_json(str(event["payload_json"]))}
            if event is not None
            else None
        ),
    }


def build_module_state(repo_root: Path, module_key: str) -> dict[str, Any]:
    from status import _build_lab_summary, _extract_frontmatter, _git_head_for_file
    from translation_v2 import detect_module_state

    # Defense in depth: module_key reaches the filesystem below (en_path.exists(),
    # _extract_frontmatter(en_path)). Both current callers pre-validate via
    # _validate_module_key, but re-validate here so the function is safe
    # regardless of caller and cannot be coerced into reading outside
    # src/content/docs via "../" traversal (CodeQL py/path-injection, alert #32).
    normalized = _validate_module_key(repo_root, module_key)
    if normalized is None:
        raise ValueError(f"unsafe or invalid module_key: {module_key!r}")
    en_path = repo_root / "src" / "content" / "docs" / f"{normalized}.md"
    uk_path = repo_root / "src" / "content" / "docs" / "uk" / f"{normalized}.md"
    frontmatter = _extract_frontmatter(en_path) if en_path.exists() else {}
    lab = frontmatter.get("lab")
    lab_id = None
    if isinstance(lab, str) and lab.strip():
        lab_id = lab.strip()
    elif isinstance(lab, dict):
        for key in ("id", "name", "slug"):
            value = lab.get(key)
            if isinstance(value, str) and value.strip():
                lab_id = value.strip()
                break

    fact_ledger = repo_root / ".pipeline" / "fact-ledgers" / f"{normalized.replace('/', '__')}.json"
    lab_summary = _build_lab_summary(repo_root)
    lab_state = next((item for item in lab_summary["items"] if item["lab_id"] == lab_id), None) if lab_id else None

    state = {
        "module_key": normalized,
        "track": normalized.split("/", 1)[0] if "/" in normalized else normalized,
        "english_path": str(en_path),
        "english_exists": en_path.exists(),
        "english_commit": _git_head_for_file(repo_root, en_path) if en_path.exists() else "",
        "ukrainian_path": str(uk_path),
        "ukrainian_exists": uk_path.exists(),
        "ukrainian_state": detect_module_state(repo_root, normalized) if en_path.exists() else None,
        "frontmatter": frontmatter,
        "fact_ledger": {
            "path": str(fact_ledger),
            "exists": fact_ledger.exists(),
        },
        "lab": {
            "lab_id": lab_id,
            "state": lab_state,
        },
    }

    # Fold orchestration + lease inline so "why is X blocked" is one
    # call (the /api/module/{key}/orchestration/latest and /lease
    # endpoints remain for back-compat and for callers who only want
    # that slice).
    state["orchestration"] = build_module_orchestration_latest(repo_root, normalized)
    state["lease"] = build_module_lease(repo_root, normalized)

    state["diagnostics"] = build_module_diagnostics(repo_root, normalized, state)

    # Add orchestration-derived diagnostics. We do this AFTER the
    # base diagnostics so pipeline signals append rather than
    # duplicate what ``build_module_diagnostics`` already produced.
    latest_job = (state["orchestration"].get("v2") or {}).get("latest_job") or {}
    queue_state = latest_job.get("queue_state")
    if queue_state == "rejected":
        state["diagnostics"].append(_diag(
            severity="critical",
            code="pipeline_rejected",
            summary="Pipeline v2 rejected the last run",
            source="pipeline_v2.jobs",
            next_action=f"GET /api/pipeline/v2/events?module={normalized}",
        ))
    elif queue_state == "dead_letter":
        state["diagnostics"].append(_diag(
            severity="critical",
            code="pipeline_dead_letter",
            summary="Module is in pipeline dead-letter",
            source="pipeline_v2.jobs",
            next_action=f"GET /api/pipeline/v2/events?module={normalized}",
        ))
    if state["lease"].get("held"):
        lease_info = state["lease"].get("lease") or {}
        leased_by = lease_info.get("leased_by", "unknown")
        secs = lease_info.get("seconds_to_expiry")
        state["diagnostics"].append(_diag(
            severity="info",
            code="lease_held",
            summary=f"Leased by {leased_by} ({secs}s to expiry)" if secs else f"Leased by {leased_by}",
            source="pipeline_v2.jobs",
            next_action="wait for lease to release before claiming work",
        ))
    review = build_module_reviews(repo_root, normalized, max_bytes=50_000)
    if review and review.get("fact_check_status") == "unverified":
        state["diagnostics"].append(_diag(
            severity="warn",
            code="fact_check_unverified",
            summary="Latest review contains unverified fact claims",
            source="reviews",
            next_action=f"GET /api/reviews?module={normalized}",
        ))

    return state


def build_module_orchestration_latest(repo_root: Path, module_key: str) -> dict[str, Any]:
    normalized = module_key[:-3] if module_key.endswith(".md") else module_key
    return {
        "module_key": normalized,
        "v2": _db_latest_for_module(repo_root / ".pipeline" / "v2.db", normalized),
        "translation_v2": _db_latest_for_module(repo_root / ".pipeline" / "translation_v2.db", normalized),
    }


# ============================================================
# Phase C: leases, diagnostics, quality, pipeline events/stuck,
# reviews, bridge messages
# ============================================================


def _query_sqlite_rows(
    db_path: Path,
    sql: str,
    params: tuple = (),
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Run a read-only query and return rows as dicts. Empty list if
    the DB is missing or the referenced table doesn't exist; every
    other sqlite error propagates so the handler can surface it as a
    500 (silently swallowing hides schema-drift bugs)."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchmany(limit)]
    except sqlite3.OperationalError as exc:
        # "no such table" is an expected "feature not yet provisioned"
        # state (e.g. bridge DB absent before first message). Anything
        # else — "no such column", type mismatch, etc. — is a bug the
        # caller needs to see.
        if "no such table" in str(exc):
            return []
        raise
    finally:
        conn.close()


# Timestamps in .pipeline/v2.db are Unix epoch SECONDS (SQLite's
# strftime('%s','now') — see scripts/pipeline_v2/control_plane.py). All
# comparisons here must use the same unit.


def build_pipeline_leases(repo_root: Path, *, now_seconds: int | None = None) -> dict[str, Any]:
    """Active pipeline leases (from ``jobs`` table).

    A lease is active when ``leased_by`` is set and ``lease_expires_at``
    is in the future. Payload ordered by expiry so the most-at-risk
    leases are first.
    """
    db_path = repo_root / ".pipeline" / "v2.db"
    if not db_path.exists():
        return {"db_path": str(db_path), "active": [], "count": 0, "exists": False}

    now_seconds = now_seconds if now_seconds is not None else int(time.time())
    rows = _query_sqlite_rows(
        db_path,
        """
        SELECT module_key, phase, queue_state, model, priority,
               leased_by, lease_id, leased_at, lease_expires_at
        FROM jobs
        WHERE leased_by IS NOT NULL
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at > ?
        ORDER BY lease_expires_at ASC
        """,
        (now_seconds,),
    )
    for row in rows:
        exp = row.get("lease_expires_at")
        if isinstance(exp, (int, float)):
            row["seconds_to_expiry"] = max(0, int(exp) - now_seconds)
    return {
        "db_path": str(db_path),
        "exists": True,
        "count": len(rows),
        "active": rows,
        "queried_at_seconds": now_seconds,
    }


def build_module_lease(
    repo_root: Path, module_key: str, *, now_seconds: int | None = None
) -> dict[str, Any]:
    """Lease state for one module. Returns ``{held: False}`` when no
    active lease exists (vs 404 semantics, which would be ambiguous
    between 'no lease' and 'no pipeline DB')."""
    db_path = repo_root / ".pipeline" / "v2.db"
    if not db_path.exists():
        return {
            "module_key": module_key,
            "held": False,
            "reason": "missing_db",
            "db_path": str(db_path),
        }
    now_seconds = now_seconds if now_seconds is not None else int(time.time())
    rows = _query_sqlite_rows(
        db_path,
        """
        SELECT module_key, phase, queue_state, model, priority,
               leased_by, lease_id, leased_at, lease_expires_at
        FROM jobs
        WHERE module_key = ?
          AND leased_by IS NOT NULL
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at > ?
        ORDER BY lease_expires_at DESC
        LIMIT 1
        """,
        (module_key, now_seconds),
    )
    if not rows:
        return {"module_key": module_key, "held": False}
    row = rows[0]
    exp = row.get("lease_expires_at")
    if isinstance(exp, (int, float)):
        row["seconds_to_expiry"] = max(0, int(exp) - now_seconds)
    return {"module_key": module_key, "held": True, "lease": row}


# ---- pipeline events / stuck ----


def build_pipeline_events(
    repo_root: Path,
    module_key: str | None,
    since_seconds: int | None,
    limit: int = 200,
) -> dict[str, Any]:
    """Timeline view of ``.pipeline/v2.db`` events.

    Filter by ``module_key`` (optional) and ``since_seconds`` (optional,
    inclusive Unix-epoch seconds to match the control-plane's time
    unit). Newest-first, capped by ``limit`` (default 200, max 2000).
    """
    db_path = repo_root / ".pipeline" / "v2.db"
    if not db_path.exists():
        return {"db_path": str(db_path), "exists": False, "count": 0, "events": []}
    capped = max(1, min(int(limit), 2000))
    clauses: list[str] = []
    params: list[Any] = []
    if module_key:
        clauses.append("module_key = ?")
        params.append(module_key)
    if since_seconds is not None:
        clauses.append("at >= ?")
        params.append(int(since_seconds))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = _query_sqlite_rows(
        db_path,
        f"""
        SELECT id, type, module_key, lease_id, payload_json, at
        FROM events
        {where}
        ORDER BY id DESC
        LIMIT {capped}
        """,
        tuple(params),
    )
    for row in rows:
        payload = row.get("payload_json")
        if isinstance(payload, str):
            row["payload_json"] = _load_json(payload)
    return {
        "db_path": str(db_path),
        "exists": True,
        "module_key": module_key,
        "since_seconds": since_seconds,
        "limit": capped,
        "count": len(rows),
        "events": rows,
    }


# Phases considered "in-flight" when computing stuck modules. A job
# that's been sitting in one of these states longer than the threshold
# is a candidate for human attention.
_STUCK_IN_FLIGHT_STATES = ("leased", "running", "in_progress")
_DEFAULT_STUCK_THRESHOLD_SECONDS = 3600  # 1 hour


def build_pipeline_stuck(
    repo_root: Path,
    *,
    threshold_seconds: int = _DEFAULT_STUCK_THRESHOLD_SECONDS,
    now_seconds: int | None = None,
) -> dict[str, Any]:
    """Stuck/dead-letter view of pipeline v2.

    Three signals are surfaced:

    - ``stuck_leased``: jobs whose lease has expired OR whose
      ``leased_at`` is older than the threshold.
    - ``stuck_in_state``: jobs in an in-flight ``queue_state`` with no
      recent event *for the current attempt*. Events are correlated
      to the job's current ``lease_id`` — a recent event from an
      earlier lease for the same module must not mask a hung
      current lease.
    - ``dead_lettered``: modules with a ``module_dead_lettered``
      event that has not been superseded by a later
      ``dead_letter_recovered`` event. These are modules the
      pipeline explicitly gave up on and need human triage or
      ``pipeline_v2 recover-dead-letters`` before they will make
      progress.
    """
    db_path = repo_root / ".pipeline" / "v2.db"
    if not db_path.exists():
        return {
            "db_path": str(db_path),
            "exists": False,
            "stuck_leased": [],
            "stuck_in_state": [],
            "dead_lettered": [],
        }

    now_seconds = now_seconds if now_seconds is not None else int(time.time())
    cutoff = now_seconds - threshold_seconds

    stuck_leased = _query_sqlite_rows(
        db_path,
        """
        SELECT module_key, phase, queue_state, leased_by, lease_id,
               leased_at, lease_expires_at
        FROM jobs
        WHERE leased_by IS NOT NULL
          AND (
              (lease_expires_at IS NOT NULL AND lease_expires_at < ?)
              OR (leased_at IS NOT NULL AND leased_at < ?)
          )
        ORDER BY leased_at ASC
        LIMIT 500
        """,
        (now_seconds, cutoff),
    )

    # Correlate events by lease_id (and fall back to module_key for
    # jobs without a lease_id) so a fresh event from a previous
    # attempt can't mask a hung current attempt.
    stuck_in_state = _query_sqlite_rows(
        db_path,
        f"""
        SELECT j.module_key, j.phase, j.queue_state, j.leased_by,
               j.lease_id, j.leased_at,
               (
                   SELECT MAX(at) FROM events e
                   WHERE (j.lease_id IS NOT NULL AND e.lease_id = j.lease_id)
                      OR (j.lease_id IS NULL AND e.module_key = j.module_key)
               ) AS last_event_at
        FROM jobs j
        WHERE j.queue_state IN ({','.join('?' for _ in _STUCK_IN_FLIGHT_STATES)})
        ORDER BY j.leased_at ASC
        LIMIT 500
        """,
        tuple(_STUCK_IN_FLIGHT_STATES),
    )
    # Keep only those whose last event for the current attempt is
    # older than the threshold (NULL/0 counts as stuck — a running
    # job that has emitted zero events is stuck by definition).
    stuck_in_state = [
        row for row in stuck_in_state
        if (row.get("last_event_at") or 0) < cutoff
    ]

    # Dead-lettered modules. We defer to ``pipeline_v2.cli.
    # _current_dead_letter_rows`` for the reducer so this endpoint
    # agrees with the pipeline's own needs_human_count. That helper
    # sorts by ``(at, id)`` and compares recovery-event order against
    # dead-letter-event order, so out-of-order ``at`` timestamps or
    # ``(id)`` vs ``(at)`` skew don't cause this endpoint to
    # disagree with the source of truth.
    dead_events = _query_sqlite_rows(
        db_path,
        """
        SELECT id, module_key, type, payload_json, at
        FROM events
        WHERE type IN (
            'module_dead_lettered',
            'needs_human_intervention',
            'dead_letter_recovered'
        )
        """,
    )
    # Only swallow the "pipeline_v2 not installed at all" case,
    # narrowed by ``exc.name`` so a transitive import failure inside
    # pipeline_v2.cli (broken install, missing dep) doesn't silently
    # degrade to ``dead_lettered = []`` and hide modules that need
    # human triage. A renamed/removed ``_current_dead_letter_rows``
    # raises ImportError (not ModuleNotFoundError) and propagates.
    _current_dead_letter_rows = None
    try:
        from pipeline_v2.cli import _current_dead_letter_rows
    except ModuleNotFoundError as exc:
        if exc.name not in {"pipeline_v2", "pipeline_v2.cli"}:
            raise
    if _current_dead_letter_rows is not None and dead_events:
        dead_lettered = _current_dead_letter_rows(dead_events)
    else:
        dead_lettered = []

    # Phase D stale-worker view: per-``leased_by`` roll-up. A worker may
    # hold several non-expired leases but have gone silent across all of
    # them — that's a zombie that the per-module ``stuck_in_state`` view
    # doesn't surface cleanly because a bursty event on a sibling lease
    # can hide it. We group by worker and take the most recent event
    # from ANY of their current leases as the heartbeat. ``idle_seconds``
    # = None means "never emitted" and ranks as strictly staler than any
    # finite idle time.
    active_lease_rows = _query_sqlite_rows(
        db_path,
        """
        SELECT j.leased_by, j.lease_id, j.module_key, j.phase,
               j.leased_at, j.lease_expires_at,
               (
                   SELECT MAX(at) FROM events e
                   WHERE e.lease_id = j.lease_id
               ) AS last_event_at
        FROM jobs j
        WHERE j.leased_by IS NOT NULL
          AND (j.lease_expires_at IS NULL OR j.lease_expires_at >= ?)
        ORDER BY j.leased_by ASC, j.lease_id ASC, j.id ASC
        """,
        (now_seconds,),
    )
    by_worker: dict[str, dict[str, Any]] = {}
    for row in active_lease_rows:
        worker = row.get("leased_by")
        if not worker:
            continue
        bucket = by_worker.setdefault(str(worker), {
            "leased_by": str(worker),
            "active_lease_count": 0,
            "module_keys": [],
            "last_event_at": None,
        })
        bucket["active_lease_count"] += 1
        mk = row.get("module_key")
        if mk and mk not in bucket["module_keys"]:
            bucket["module_keys"].append(mk)
        le = row.get("last_event_at")
        if isinstance(le, (int, float)):
            if bucket["last_event_at"] is None or le > bucket["last_event_at"]:
                bucket["last_event_at"] = int(le)

    stale_workers: list[dict[str, Any]] = []
    for bucket in by_worker.values():
        le = bucket["last_event_at"]
        if le is None:
            idle: int | None = None
        else:
            idle = max(0, now_seconds - int(le))
        # Stale if the worker has never emitted an event on any active
        # lease, OR its most recent heartbeat is older than the threshold.
        if idle is None or idle > threshold_seconds:
            bucket["idle_seconds"] = idle
            stale_workers.append(bucket)
    # Rank "never emitted" as strictly staler than any finite idle, then
    # longest-idle first, with ``leased_by`` as a deterministic tiebreaker
    # so two workers at the same idle-seconds don't rearrange across
    # calls. (Codex Phase D review: finite-idle ties were non-
    # deterministic.)
    stale_workers.sort(
        key=lambda w: (
            0 if w.get("idle_seconds") is None else 1,
            -(w.get("idle_seconds") or 0),
            str(w.get("leased_by") or ""),
        )
    )

    return {
        "db_path": str(db_path),
        "exists": True,
        "threshold_seconds": threshold_seconds,
        "queried_at_seconds": now_seconds,
        "stuck_leased_count": len(stuck_leased),
        "stuck_leased": stuck_leased,
        "stuck_in_state_count": len(stuck_in_state),
        "stuck_in_state": stuck_in_state,
        "dead_lettered_count": len(dead_lettered),
        "dead_lettered": dead_lettered,
        "stale_workers_count": len(stale_workers),
        "stale_workers": stale_workers,
    }


# ---- reviews audit log ----


_REVIEW_AUDIT_DIR = Path(".pipeline") / "reviews"
_VALID_FACT_CHECK_STATUSES = {"verified", "unverified", "failed", "none"}

def _is_safe_review_filename(filename: str) -> bool:
    """Validate review filename format without using user-driven regexes."""
    if "/" in filename or "\\" in filename:
        return False
    if not filename.endswith(".md") or filename == ".md":
        return False
    stem = filename[:-3]
    for segment in stem.split("__"):
        if not segment:
            return False
        if segment[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
            return False
        for ch in segment:
            if ch in "abcdefghijklmnopqrstuvwxyz0123456789._-":
                continue
            return False
    return True
_LATEST_REVIEW_RE = re.compile(r"^## .*?— `REVIEW`.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
_FAILED_FACT_CHECK_RE = re.compile(r"^- \*\*FACT_CHECK\*\*:\s*(.+)$", re.MULTILINE)
_UNVERIFIED_CLAIM_RE = re.compile(r"unverified:\s*(.+)", re.IGNORECASE)


def _review_filename_to_module_key(filename: str) -> str:
    """Filenames use ``__`` as path separators. Strip trailing
    ``.md`` / ``.lock``."""
    name = filename
    for suffix in (".md", ".lock"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.replace("__", "/")


def _module_key_to_review_filename(module_key: str) -> str:
    return module_key.replace("/", "__") + ".md"


def _safe_review_path_for_module_key(repo_root: Path, module_key: str) -> Path | None:
    normalized = _validate_module_key(repo_root, module_key)
    if normalized is None:
        return None
    try:
        reviews_dir = (repo_root / _REVIEW_AUDIT_DIR).resolve()
    except OSError:
        return None
    filename = _module_key_to_review_filename(normalized)
    if not _is_safe_review_filename(filename):
        return None
    if not reviews_dir.is_dir():
        return None
    for candidate in reviews_dir.glob("*.md"):
        if candidate.name != filename:
            continue
        try:
            path = candidate.resolve()
            path.relative_to(reviews_dir)
        except (OSError, RuntimeError, ValueError):
            return None
        return path
    return None


def _fact_check_summary(review_body: str) -> dict[str, Any]:
    latest = next(iter(_LATEST_REVIEW_RE.findall(review_body)), "")
    failed = [m.strip() for m in _FAILED_FACT_CHECK_RE.findall(latest)]
    if failed:
        return {"fact_check_status": "failed", "unverified_evidence": []}
    unverified = [f"unverified: {m.strip()}" for m in _UNVERIFIED_CLAIM_RE.findall(latest)]
    if unverified:
        return {"fact_check_status": "unverified", "unverified_evidence": unverified[:3]}
    return {
        "fact_check_status": "verified" if "FACT_CHECK" in latest else "none",
        "unverified_evidence": [],
    }


def build_reviews_index(
    repo_root: Path,
    *,
    fact_check_status: str | None = None,
) -> dict[str, Any]:
    """List every review artifact with its module key and last-modified
    timestamp. Callers fetch the body via ``/api/reviews?module=...``."""
    reviews_dir = repo_root / _REVIEW_AUDIT_DIR
    if not reviews_dir.is_dir():
        return {"reviews_dir": str(reviews_dir), "exists": False, "count": 0, "reviews": []}
    reviews: list[dict[str, Any]] = []
    for path in sorted(reviews_dir.glob("*.md")):
        try:
            mtime = path.stat().st_mtime
            size = path.stat().st_size
            summary = _fact_check_summary(path.read_text(encoding="utf-8"))
        except OSError:
            mtime, size = 0.0, 0
            summary = {"fact_check_status": "none", "unverified_evidence": []}
        if fact_check_status and summary["fact_check_status"] != fact_check_status:
            continue
        reviews.append({
            "module_key": _review_filename_to_module_key(path.name),
            "filename": path.name,
            "size": size,
            "mtime": mtime,
            **summary,
        })
    reviews.sort(key=lambda item: item["mtime"], reverse=True)
    return {
        "reviews_dir": str(reviews_dir),
        "exists": True,
        "count": len(reviews),
        "reviews": reviews,
    }


def build_module_reviews(
    repo_root: Path,
    module_key: str,
    *,
    max_bytes: int = 200_000,
) -> dict[str, Any] | None:
    """Return the full review log for a module, capped at ``max_bytes``.

    The log is a markdown file produced by the pipeline with one
    section per review pass (writer, plan, duration, reviewer,
    severity, etc.). We return it as a single ``body`` string so
    agents can parse what they need without the API pretending to
    understand every variation of the format.
    """
    path = _safe_review_path_for_module_key(repo_root, module_key)
    if path is None:
        return None
    if not path.is_file():
        return None
    try:
        stat = path.stat()
        on_disk_size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        on_disk_size, mtime = 0, 0.0
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    truncated = False
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
        truncated = True
    try:
        body = raw.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        body = raw.decode("latin-1", errors="replace")
    summary = _fact_check_summary(body)
    return {
        "module_key": module_key,
        "path": str(path),
        "size": on_disk_size,
        "body_size": len(body.encode("utf-8")),
        "truncated": truncated,
        "max_bytes": max_bytes if truncated else None,
        "mtime": mtime,
        **summary,
        "body": body,
    }


# ---- bridge messages ----


def _resolve_bridge_db_path(repo_root: Path) -> Path:
    """Locate ``messages.db`` the same way the bridge CLI does.

    Precedence:
      1. ``$AB_DB_PATH`` — unconditional. An explicit override must
         win even if the file doesn't yet exist; the caller surfaces
         ``exists=False`` when that happens. (Codex round-2 caught that
         previously we only honored AB_DB_PATH when the file already
         existed — quietly reading the wrong DB on a fresh override.)
      2. ``.bridge/messages.db`` — set by the ``scripts/ab`` wrapper
         and by the repo setup guide; the repo convention.
      3. ``.mcp/servers/message-broker/messages.db`` — the upstream
         Python default when no wrapper is used.
    Within 2 and 3, the first existing file wins; if neither exists,
    the convention path (2) is returned.
    """
    explicit = os.environ.get("AB_DB_PATH")
    if explicit:
        return Path(explicit)
    candidates = [
        repo_root / ".bridge" / "messages.db",
        repo_root / ".mcp" / "servers" / "message-broker" / "messages.db",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def build_bridge_messages(
    repo_root: Path,
    since: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Recent agent-bridge messages from the bridge DB.

    Filter ``since`` is an ISO-8601 timestamp (string comparison is
    safe — the bridge stores ISO-8601 UTC). ``limit`` caps at 500 rows
    so a single call can't overwhelm a polling agent.
    """
    db_path = _resolve_bridge_db_path(repo_root)
    if not db_path.exists():
        return {"db_path": str(db_path), "exists": False, "count": 0, "messages": []}
    capped = max(1, min(int(limit), 500))
    if since:
        rows = _query_sqlite_rows(
            db_path,
            f"""
            SELECT id, task_id, from_llm, to_llm, message_type,
                   content, timestamp, acknowledged, status
            FROM messages
            WHERE timestamp >= ?
            ORDER BY id DESC
            LIMIT {capped}
            """,
            (since,),
            limit=capped,
        )
    else:
        rows = _query_sqlite_rows(
            db_path,
            f"""
            SELECT id, task_id, from_llm, to_llm, message_type,
                   content, timestamp, acknowledged, status
            FROM messages
            ORDER BY id DESC
            LIMIT {capped}
            """,
            limit=capped,
        )
    # Truncate message content to a readable preview so a burst of
    # long messages doesn't blow up the response. Full content stays
    # accessible via the bridge CLI.
    for row in rows:
        content = row.get("content")
        if isinstance(content, str) and len(content) > 400:
            row["content_preview"] = content[:400] + "… (truncated)"
            row["content_full_length"] = len(content)
            row.pop("content", None)
    return {
        "db_path": str(db_path),
        "exists": True,
        "since": since,
        "limit": capped,
        "count": len(rows),
        "messages": rows,
    }


def _build_channel_threads_index(
    repo_root: Path,
    *,
    list_channels_fn,
) -> dict[str, Any]:
    return _CHANNEL_ROUTES.build_channel_threads_index(
        repo_root,
        list_channels_fn=list_channels_fn,
        resolve_bridge_db_path_fn=_resolve_bridge_db_path,
        query_sqlite_rows_fn=_query_sqlite_rows,
    )


def _build_channel_events_payload(
    thread_id: str,
    read_channel_events_fn,
    since_event_id: int = 0,
) -> dict[str, Any]:
    return _CHANNEL_ROUTES.build_channel_events_payload(
        thread_id,
        read_channel_events_fn=read_channel_events_fn,
        since_event_id=since_event_id,
    )


# ---- #388 dispatcher batch progress ----
#
# scripts/quality/dispatch_388_pilot.py writes a JSONL event log per batch
# under logs/388_*.jsonl. Read-only roll-up: "complete" if pilot_done seen,
# "errored" if tail is an *_error and idle >= 30 min, else "in_flight".

_388_IDLE_ERROR_SECONDS = 30 * 60
_388_COUNT_KINDS = (
    "merged", "merge_held_nits", "merge_held", "module_skip",
    "codex_error", "gemini_error", "worktree_error",
)
_388_PR_NUMBER_RE = re.compile(r"#(\d+)")


def _load_388_events(log_path: Path) -> list[dict[str, Any]]:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _summarize_388_events(
    events: list[dict[str, Any]], *, now_seconds: float | None = None
) -> dict[str, Any]:
    """Roll dispatch_388 events into a batch summary (event-derived fields only)."""
    last_pilot_start_idx = max(
        (i for i, e in enumerate(events) if e.get("event") == "pilot_start"),
        default=-1,
    )
    events_to_summarize = events[last_pilot_start_idx:] if last_pilot_start_idx >= 0 else events

    counts: dict[str, int] = {k: 0 for k in _388_COUNT_KINDS}
    started_at = ended_at = last_event_at = None
    last_event_kind = current_module = input_file = None
    module_count = None
    held_prs: list[dict[str, Any]] = []

    for ev in events_to_summarize:
        kind = ev.get("event")
        ts = ev.get("ts")
        if isinstance(ts, (int, float)):
            last_event_at = ts
            last_event_kind = kind
        if kind == "pilot_start":
            if started_at is None and isinstance(ts, (int, float)):
                started_at = ts
            if input_file is None and isinstance(ev.get("input"), str):
                input_file = ev["input"]
            if module_count is None and isinstance(ev.get("count"), int):
                module_count = ev["count"]
        elif kind == "pilot_done" and isinstance(ts, (int, float)):
            ended_at = ts
        elif kind == "module_start" and isinstance(ev.get("module"), str):
            current_module = ev["module"]
        elif kind in counts:
            counts[kind] += 1
        if kind in ("merge_held_nits", "merge_held"):
            held_prs.append({
                "pr": ev.get("pr"), "module": ev.get("module"),
                "verdict": ev.get("verdict"),
                "kind": "nits" if kind == "merge_held_nits" else "full",
            })

    if ended_at is not None:
        state = "complete"
    else:
        now = now_seconds if now_seconds is not None else time.time()
        idle_for = (now - last_event_at) if last_event_at is not None else None
        if (last_event_kind in {"codex_error", "gemini_error", "worktree_error"}
                and idle_for is not None and idle_for >= _388_IDLE_ERROR_SECONDS):
            state = "errored"
        else:
            state = "in_flight"
    return {
        "input_file": input_file, "module_count": module_count,
        "started_at": started_at, "ended_at": ended_at, "state": state,
        "last_event_at": last_event_at,
        "current_module": current_module if state == "in_flight" else None,
        "counts": counts, "held_prs": held_prs,
    }


def _388_log_paths(repo_root: Path) -> list[Path]:
    logs_dir = repo_root / "logs"
    return sorted(logs_dir.glob("388_*.jsonl")) if logs_dir.is_dir() else []


def _388_rel(repo_root: Path, log_path: Path) -> str:
    try:
        return str(log_path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(log_path)


def _merged_pr_numbers_from_git(repo_root: Path) -> set[int]:
    try:
        result = subprocess.run(
            ["git", "log", "--format=%s", "--grep=388", "--regexp-ignore-case"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {
        int(match)
        for subject in result.stdout.splitlines()
        for match in _388_PR_NUMBER_RE.findall(subject)
    }


def _fetch_388_pr_states() -> dict[int, dict[str, Any]]:
    status_code, payload = _run_gh_json(
        "pr",
        "list",
        "--state",
        "all",
        "--search",
        "388 in:title",
        "--limit",
        "200",
        "--json",
        _gh_json_fields("number", "state", "mergedAt", "url"),
        timeout=15,
    )
    if status_code != 200 or not isinstance(payload, list):
        return {}

    states: dict[int, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            continue
        states[item["number"]] = {
            "state": item.get("state"),
            "merged_at": item.get("mergedAt") or None,
            "url": item.get("url") or "",
        }
    return states


def _annotate_388_held_prs(
    repo_root: Path,
    held_prs: list[dict[str, Any]],
    *,
    pr_states: dict[int, dict[str, Any]] | None = None,
    merged_from_git: set[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    if pr_states is None:
        pr_states = _fetch_388_pr_states()
    if merged_from_git is None:
        merged_from_git = set() if pr_states else _merged_pr_numbers_from_git(repo_root)
    source = "github" if pr_states else "git_log"
    annotated: list[dict[str, Any]] = []
    rollup = {"total": 0, "open": 0, "merged": 0, "closed": 0, "unknown": 0, "resolved": 0}

    for held in held_prs:
        item = dict(held)
        pr = item.get("pr")
        if not isinstance(pr, int):
            status = "unknown"
        elif pr in pr_states:
            gh_state = str(pr_states[pr].get("state") or "").lower()
            merged_at = pr_states[pr].get("merged_at")
            item["url"] = pr_states[pr].get("url", "")
            status = "merged" if merged_at or gh_state == "merged" else gh_state or "unknown"
        elif pr in merged_from_git:
            status = "merged"
        else:
            status = "unknown"

        if status not in {"open", "merged", "closed"}:
            status = "unknown"
        item["resolution_status"] = status
        item["resolved"] = status in {"merged", "closed"}
        annotated.append(item)

        rollup["total"] += 1
        rollup[status] += 1
        if item["resolved"]:
            rollup["resolved"] += 1

    return annotated, rollup, source


def _apply_388_live_counts(
    event_counts: dict[str, int], held_prs: list[dict[str, Any]]
) -> dict[str, int]:
    counts = dict(event_counts)
    for held in held_prs:
        if not held.get("resolved"):
            continue
        kind = "merge_held_nits" if held.get("kind") == "nits" else "merge_held"
        counts[kind] = max(0, counts.get(kind, 0) - 1)
        if held.get("resolution_status") == "merged":
            counts["merged"] = counts.get("merged", 0) + 1
    return counts


def _list_388_batches(repo_root: Path) -> list[dict[str, Any]]:
    summaries: list[tuple[Path, dict[str, Any]]] = [
        (log_path, _summarize_388_events(_load_388_events(log_path)))
        for log_path in _388_log_paths(repo_root)
    ]
    has_held_prs = any(summary["held_prs"] for _, summary in summaries)
    pr_states = _fetch_388_pr_states() if has_held_prs else {}
    merged_from_git = set() if pr_states or not has_held_prs else _merged_pr_numbers_from_git(repo_root)

    batches: list[dict[str, Any]] = []
    for log_path, summary in summaries:
        held_prs, held_rollup, resolution_source = _annotate_388_held_prs(
            repo_root,
            summary["held_prs"],
            pr_states=pr_states,
            merged_from_git=merged_from_git,
        )
        summary["event_counts"] = dict(summary["counts"])
        summary["counts"] = _apply_388_live_counts(summary["counts"], held_prs)
        summary["held_rollup"] = held_rollup | {"resolution_source": resolution_source}
        summary.pop("held_prs", None)
        summary["log_path"] = _388_rel(repo_root, log_path)
        summary["log_stem"] = log_path.stem
        batches.append(summary)
    return batches


def _load_388_batch(repo_root: Path, log_stem: str) -> dict[str, Any] | None:
    target = next((p for p in _388_log_paths(repo_root) if p.stem == log_stem), None)
    if target is None:
        return None
    events = _load_388_events(target)
    summary = _summarize_388_events(events)
    held_prs, held_rollup, resolution_source = _annotate_388_held_prs(repo_root, summary["held_prs"])
    summary["held_prs"] = held_prs
    summary["event_counts"] = dict(summary["counts"])
    summary["counts"] = _apply_388_live_counts(summary["counts"], held_prs)
    summary["held_rollup"] = held_rollup | {"resolution_source": resolution_source}
    summary["log_path"] = _388_rel(repo_root, target)
    summary["log_stem"] = target.stem
    # Drop large excerpts from per-event timeline so /batch/{stem} stays small.
    summary["events"] = [
        {k: v for k, v in ev.items() if k not in {"response_excerpt", "review_excerpt"}}
        for ev in events
    ]
    return summary


# ---- quality scores ----


_QUALITY_AUDIT_CACHE: dict[str, dict[str, Any]] = {}
_QUALITY_AUDIT_CACHE_LOCK = threading.Lock()
_CITATION_STATUS_CACHE: dict[str, dict[str, Any]] = {}
_CITATION_STATUS_CACHE_LOCK = threading.Lock()


_QUALITY_TITLE_RE = re.compile(r'^title:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)
_QUALITY_SOURCES_HEADING_RE = re.compile(r"^##\s+Sources\s*$", re.MULTILINE)
_QUALITY_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_QUALITY_BARE_URL_RE = re.compile(r"https?://\S+")
_QUALITY_BOX_DRAWING_LINE_RE = re.compile(
    r"^[^\n]*[─-╿][^\n]*$",
    re.MULTILINE,
)
_QUALITY_BOX_DRAWING_MIN_LINES = 5
_QUALITY_TRACK_LABELS = {
    "ai": "AI",
    "ai-history": "AI History",
    "ai-ml-engineering": "AI/ML Engineering",
    "cloud": "Cloud",
    "linux": "Linux",
    "on-premises": "On-Premises",
    "platform": "Platform",
    "prerequisites": "Prerequisites",
}
_QUALITY_REDIRECT_STUB_RE = re.compile(
    r"^\s*this module has moved\b",
    re.IGNORECASE | re.MULTILINE,
)


def _quality_severity(score: float) -> str:
    if score < 2.0:
        return "critical"
    if score < 2.5:
        return "poor"
    if score < 3.5:
        return "needs_work"
    if score < 4.5:
        return "good"
    return "excellent"


def _quality_track_label(rel: Path) -> str:
    parts = rel.parts
    if not parts:
        return ""
    first = parts[0]
    if len(parts) >= 2 and first == "k8s" and parts[1] in _CERT_TRACKS:
        return parts[1].upper()
    top = _QUALITY_TRACK_LABELS.get(first, first.replace("-", " ").title())
    if first == "ai-history":
        return top
    if len(parts) >= 2 and not parts[1].startswith(("module-", "part")):
        return f"{top} {parts[1].replace('-', ' ').title()}"
    return top


def _quality_body_without_frontmatter(text: str) -> str:
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        return text[4:].split("\n---\n", 1)[1]
    return text


def _quality_is_redirect_stub(text: str) -> bool:
    body = _quality_body_without_frontmatter(text)
    non_blank_lines = [line for line in body.splitlines() if line.strip()]
    return len(non_blank_lines) < 30 and bool(_QUALITY_REDIRECT_STUB_RE.search(body))


def _quality_title_and_label(rel: Path, text: str) -> tuple[str, str]:
    frontmatter = text[4:].split("\n---\n", 1)[0] if text.startswith("---\n") and "\n---\n" in text[4:] else ""
    match = _QUALITY_TITLE_RE.search(frontmatter)
    title = (match.group(1).strip() if match else "") or rel.stem.replace("-", " ").title()
    title = re.sub(r"^Module\s+[0-9]+(?:\.[0-9]+)*:\s*", "", title).strip()
    track = _quality_track_label(rel)
    number_match = _MODULE_NUMBER_RE.search(rel.stem)
    if track.lower() in _CERT_TRACKS and number_match:
        return title, f"{track} {number_match.group(1)}: {title}"
    return title, f"{track}: {title}"


def build_quality_scores(repo_root: Path) -> dict[str, Any]:
    """Build live heuristic quality scores from current EN module files.

    Signals stay intentionally cheap and debuggable: line count drives
    the base score, then valid frontmatter/title, quiz/knowledge-check,
    exercises/labs, and diagrams/mermaid add structure bonuses.
    """
    docs_root = repo_root / "src" / "content" / "docs"
    if not docs_root.exists():
        return {"exists": False, "source": "heuristic", "generated_at": time.time(), "modules": [], "count": 0}

    paths = sorted(
        path
        for path in docs_root.glob("**/module-*.md")
        if ".staging." not in path.name and not path.relative_to(docs_root).as_posix().startswith("uk/")
    )
    sig = hashlib.sha1()
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        sig.update(path.relative_to(docs_root).as_posix().encode("utf-8"))
        sig.update(f":{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
    signature = sig.hexdigest()
    key = str(docs_root.resolve())
    with _QUALITY_AUDIT_CACHE_LOCK:
        entry = _QUALITY_AUDIT_CACHE.get(key)
        if entry is not None and entry["signature"] == signature:
            return entry["data"]

    modules: list[dict[str, Any]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _quality_is_redirect_stub(text):
            continue
        lines_count = len(text.splitlines())
        has_title = text.startswith("---\n") and bool(_QUALITY_TITLE_RE.search(text[4:].split("\n---\n", 1)[0]))
        has_quiz = bool(
            re.search(
                r"^##+\s+(quiz|quick quiz|quiz yourself|test yourself|module quiz|knowledge check)\b",
                text,
                re.IGNORECASE | re.MULTILINE,
            )
        )
        has_exercise = bool(re.search(r"^##+\s+(exercise|hands-on|practice|lab)\b", text, re.IGNORECASE | re.MULTILINE))
        has_diagram = (
            "```mermaid" in text
            or "<details>" in text
            or len(_QUALITY_BOX_DRAWING_LINE_RE.findall(text)) >= _QUALITY_BOX_DRAWING_MIN_LINES
        )
        sources_match = _QUALITY_SOURCES_HEADING_RE.search(text)
        if sources_match:
            after_sources = text[sources_match.end():]
            next_h2 = re.search(r"^##\s+", after_sources, re.MULTILINE)
            sources_block = after_sources[: next_h2.start()] if next_h2 else after_sources
        else:
            sources_block = ""
        has_citations = bool(sources_match) and (
            bool(_QUALITY_MARKDOWN_LINK_RE.search(sources_block)) or bool(_QUALITY_BARE_URL_RE.search(sources_block))
        )
        base = 0.4 if lines_count < 60 else 0.9 if lines_count < 120 else 1.4 if lines_count < 220 else 1.8 if lines_count < 300 else 2.1
        score = min(5.0, round(base + (0.6 if has_title else 0.0) + (0.8 if has_quiz else 0.0) + (0.8 if has_exercise else 0.0) + (0.7 if has_diagram else 0.0), 1))
        if not has_citations:
            score = min(score, 1.5)
        severity = _quality_severity(score)
        action = {
            "critical": "Critical",
            "poor": "Rewrite",
            "needs_work": "Improve",
            "good": "Polish",
            "excellent": "Strong",
        }[severity]
        issues = []
        if not has_citations:
            issues.append("no citations")
        if lines_count < 220:
            issues.append("thin")
        if not has_quiz:
            issues.append("no quiz")
        if not has_exercise:
            issues.append("no exercise")
        if not has_diagram:
            issues.append("no diagram")
        _, module = _quality_title_and_label(path.relative_to(docs_root), text)
        rel_path = path.relative_to(docs_root).as_posix()
        modules.append({
            "module": module,
            "path": rel_path,
            "track": _quality_track_label(path.relative_to(docs_root)),
            "lines": lines_count,
            "score": score,
            "severity": severity,
            "action": action,
            "primary_issue": ", ".join(issues[:2]) if issues else "balanced",
        })

    scores = [m["score"] for m in modules]
    avg = round(sum(scores) / len(scores), 2) if scores else None
    critical = [m for m in modules if m["severity"] == "critical"]
    poor = [m for m in modules if m["severity"] == "poor"]
    data = {
        "exists": True,
        "source": "heuristic",
        "generated_at": time.time(),
        "signature": signature[:12],
        "docs_root": str(docs_root),
        "count": len(modules),
        "average": avg,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "critical": critical,
        "critical_count": len(critical),
        "poor_count": len(poor),
        "modules": modules,
    }
    with _QUALITY_AUDIT_CACHE_LOCK:
        _QUALITY_AUDIT_CACHE[key] = {"signature": signature, "data": data}
    return data


def build_quality_upgrade_plan(repo_root: Path, *, target: float = 4.0) -> dict[str, Any]:
    """Return an upgrade-planning view for modules below a rubric target.

    This turns the historical audit into an actionable queue for the
    4/5 and 5/5 upgrade epics:

    - target < 5.0  -> issue #180
    - target >= 5.0 -> issue #181

    Only scored modules can be classified precisely; the response also
    reports how many repo modules remain unscored/unknown.
    """
    try:
        quality = build_quality_scores(repo_root)
    except Exception as exc:  # noqa: BLE001
        return {
            "exists": False,
            "generated_at": int(time.time()),
            "error": f"quality_scores_failed: {type(exc).__name__}",
            "target": target,
        }

    docs_root = repo_root / "src" / "content" / "docs"
    total_modules = 0
    if docs_root.exists():
        total_modules = sum(
            1
            for path in docs_root.glob("**/module-*.md")
            if ".staging." not in path.name and not path.relative_to(docs_root).as_posix().startswith("uk/")
        )

    modules = list(quality.get("modules") or [])
    scored_count = len(modules)
    unscored_unknown_count = max(0, total_modules - scored_count)
    needs_upgrade = [m for m in modules if float(m.get("score") or 0.0) < target]
    needs_upgrade.sort(key=lambda m: (float(m.get("score") or 0.0), str(m.get("module") or "")))

    by_track: dict[str, list[dict[str, Any]]] = {}
    severity_counts: dict[str, int] = {}
    for module in needs_upgrade:
        track = str(module.get("track") or "Unknown")
        by_track.setdefault(track, []).append(module)
        sev = str(module.get("severity") or "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    track_groups = [
        {
            "track": track,
            "count": len(items),
            "average_score": round(sum(float(i.get("score") or 0.0) for i in items) / len(items), 2),
            "modules": items,
        }
        for track, items in sorted(
            by_track.items(),
            key=lambda kv: (
                min(float(i.get("score") or 0.0) for i in kv[1]),
                kv[0].lower(),
            ),
        )
    ]

    epic_issue = 181 if target >= 5.0 else 180
    return {
        "exists": bool(quality.get("exists")),
        "generated_at": int(time.time()),
        "source": quality.get("source"),
        "target": target,
        "epic_issue": epic_issue,
        "epic_issue_url": f"https://github.com/kube-dojo/kube-dojo.github.io/issues/{epic_issue}",
        "scored_count": scored_count,
        "total_repo_modules": total_modules,
        "unscored_unknown_count": unscored_unknown_count,
        "coverage_pct": round(100.0 * scored_count / total_modules, 1) if total_modules else 0.0,
        "needs_upgrade_count": len(needs_upgrade),
        "severity_counts": severity_counts,
        "tracks": track_groups,
        "top_worst": needs_upgrade[:10],
        "scope_note": (
            "This plan is based on live heuristic scores from current English module content."
        ),
    }


def build_citation_status(repo_root: Path) -> dict[str, Any]:
    """Return deterministic citation coverage for English module files."""
    from check_citations import check_file

    docs_root = repo_root / "src" / "content" / "docs"
    if not docs_root.exists():
        return {
            "exists": False,
            "error": f"docs_root_missing: {docs_root}",
        }

    module_paths = sorted(
        path
        for path in docs_root.glob("**/module-*.md")
        if ".staging." not in path.name and not path.relative_to(docs_root).as_posix().startswith("uk/")
    )
    latest_mtime = max((path.stat().st_mtime for path in module_paths), default=0.0)
    cache_key = str(docs_root.resolve())
    with _CITATION_STATUS_CACHE_LOCK:
        entry = _CITATION_STATUS_CACHE.get(cache_key)
        if entry and entry.get("mtime") == latest_mtime:
            return entry["data"]

    results = [check_file(path) for path in module_paths]
    failing = [item for item in results if not item.get("passes")]
    by_track: dict[str, list[dict[str, Any]]] = {}
    for item in failing:
        rel = Path(item["path"]).relative_to(docs_root).as_posix()
        track = rel.split("/", 1)[0]
        module_key = rel.removesuffix(".md")
        track_item = {
            "module": module_key,
            "issues": item.get("issues") or [],
            "sources_count": item.get("sources_count") or 0,
        }
        by_track.setdefault(track, []).append(track_item)

    track_groups = []
    for track, items in sorted(by_track.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        issue_counts: dict[str, int] = {}
        for item in items:
            for issue in item.get("issues") or []:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        track_groups.append({
            "track": track,
            "count": len(items),
            "issue_counts": issue_counts,
            "modules": items,
        })

    data = {
        "exists": True,
        "total_repo_modules": len(module_paths),
        "passes_count": len(results) - len(failing),
        "failing_count": len(failing),
        "coverage_pct": round(100.0 * (len(results) - len(failing)) / len(results), 1) if results else 0.0,
        "tracks": track_groups,
        "top_missing": failing[:20],
        "scope_note": (
            "Deterministic citation gate: modules need a Sources section, war-story sources, "
            "and traceable citation markers before they count as review-passed."
        ),
    }
    with _CITATION_STATUS_CACHE_LOCK:
        _CITATION_STATUS_CACHE[cache_key] = {"mtime": latest_mtime, "data": data}
    return data


# ---- module diagnostics ----


def _diag(
    severity: str,
    code: str,
    summary: str,
    source: str,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Build a structured diagnostic entry.

    Shape per Codex round-5 review: ``severity`` (info|warn|critical),
    ``code`` (stable string agents can switch on), ``summary`` (human-
    readable one-liner), ``source`` (which subsystem flagged it), and
    ``next_action`` (suggested drill-down command or endpoint). The
    dict shape is richer than a plain string tag and lets agents both
    triage and act without a second lookup.
    """
    entry: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "summary": summary,
        "source": source,
    }
    if next_action is not None:
        entry["next_action"] = next_action
    return entry


def build_module_diagnostics(
    repo_root: Path,
    module_key: str,
    base_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Actionable diagnostics for a module.

    Each entry is a dict ``{severity, code, summary, source, next_action?}``
    so agents can triage by severity, switch on the stable ``code``, and
    follow ``next_action`` without guessing where to look next.
    """
    diagnostics: list[dict[str, Any]] = []

    if not base_state.get("english_exists"):
        diagnostics.append(_diag(
            severity="critical",
            code="english_missing",
            summary="Module path has no EN source file",
            source="filesystem",
            next_action="git log -- src/content/docs/<module>",
        ))
        return diagnostics

    frontmatter = base_state.get("frontmatter") or {}
    if not isinstance(frontmatter, dict) or not frontmatter:
        diagnostics.append(_diag(
            severity="warn",
            code="frontmatter_missing",
            summary="EN file parses with empty/invalid frontmatter",
            source="frontmatter",
            next_action="read the first ~10 lines of english_path",
        ))
    elif not frontmatter.get("title"):
        diagnostics.append(_diag(
            severity="warn",
            code="frontmatter_no_title",
            summary="Frontmatter is missing a `title:` key",
            source="frontmatter",
            next_action="read the first ~10 lines of english_path",
        ))

    lab = base_state.get("lab") or {}
    if not lab.get("lab_id"):
        diagnostics.append(_diag(
            severity="info",
            code="no_lab",
            summary="Module has no killercoda/lab attached",
            source="frontmatter.lab",
            next_action="GET /api/labs/status",
        ))

    fact = base_state.get("fact_ledger") or {}
    if not fact.get("exists"):
        diagnostics.append(_diag(
            severity="info",
            code="no_fact_ledger",
            summary="Module has no .pipeline/fact-ledgers/ entry yet",
            source="pipeline_v2",
            next_action="pipeline enqueue — scripts/pipeline_v2 CLI",
        ))

    if not base_state.get("ukrainian_exists"):
        diagnostics.append(_diag(
            severity="info",
            code="uk_translation_missing",
            summary="No Ukrainian translation present",
            source="filesystem",
            next_action="GET /api/translation/v2/status",
        ))
    else:
        uk_state = base_state.get("ukrainian_state") or {}
        if isinstance(uk_state, dict):
            status = uk_state.get("status") or uk_state.get("state")
            happy = {"ok", "current", "fresh", "synced"}
            if status and status not in happy:
                diagnostics.append(_diag(
                    severity="warn",
                    code=f"uk_state_{status}",
                    summary=f"Ukrainian translation state: {status}",
                    source="translation_v2",
                    next_action=f"GET /api/translation/v2/status (filter for {status})",
                ))

    # Rubric severity from live quality scores.
    try:
        quality = build_quality_scores(repo_root)
    except Exception:  # noqa: BLE001
        quality = {"modules": []}
    sev = _rubric_severity_for_module(module_key, quality.get("modules", []))
    if sev in ("critical", "poor"):
        diagnostics.append(_diag(
            severity="critical" if sev == "critical" else "warn",
            code=f"rubric_{sev}",
            summary=f"Rubric score marks this module as {sev}",
            source=f"quality_scores:{quality.get('source', 'unknown')}",
            next_action="GET /api/quality/scores",
        ))

    # Orchestration-driven diagnostics (pipeline stuck / dead-letter)
    # are attached by ``build_module_state`` after orchestration data
    # is fetched, so we don't duplicate the sqlite round-trip here.
    return diagnostics


_MODULE_NUMBER_RE = re.compile(r"module-([0-9]+(?:\.[0-9]+)*)")
# Used to strip ``module-X.Y-`` prefix from a slug to get a readable
# name token set.
_MODULE_NUMBER_PREFIX_RE = re.compile(r"^module-[0-9]+(?:\.[0-9]+)*-")
_PART_PREFIX_RE = re.compile(r"^part[0-9]+-?")

# Track slugs → strings likely to appear (case-insensitive) in the
# audit doc's track column. Kept narrow so we don't false-match
# (e.g. "cka" matching "kcna" substrings).
_TRACK_ALIASES: dict[str, tuple[str, ...]] = {
    "cka": ("cka",),
    "ckad": ("ckad",),
    "cks": ("cks",),
    "kcna": ("kcna",),
    "kcsa": ("kcsa",),
    "prerequisites": (
        "prerequisites", "k8s basics", "cloud native 101", "modern devops",
        "zero to terminal", "philosophy", "design",
    ),
    "linux": ("linux",),
    "cloud": ("cloud",),
    "platform": ("platform", "toolkit", "sre", "gitops", "devsecops", "mlops", "aiops"),
    "on-prem": ("on-prem", "on-premises"),
    "on-premises": ("on-prem", "on-premises"),
    "ai-ml-engineering": (
        "ai/ml", "ai-ml", "ai/ml engineering", "mlops", "genai",
        "advanced genai", "multimodal", "deep learning", "classical ml",
    ),
}

# Tokens that are too generic to contribute to the name-overlap match
# (e.g. "module", "part", "intro"). ``basics`` was removed in round-3:
# it can be the only distinguishing token in short unnumbered labels.
_NAME_TOKEN_STOPLIST = frozenset({
    "module", "part", "the", "a", "an", "and", "of", "to", "for", "with",
    "intro", "introduction", "overview",
})


# Labels typically look like ``<Track>[ <number>][:-] <Name>``.
# Capture the leading track prefix so we can match even when the
# audit ``Track`` column is a subtrack like "Workloads" or "AWS".
_LABEL_TRACK_PREFIX_RE = re.compile(
    r"^\s*(?P<track>[A-Za-z][A-Za-z/\- ]*?)\s*(?:[0-9]+(?:\.[0-9]+)*)?\s*[:\-]"
)


def _audit_row_track_tokens(row: dict[str, Any]) -> set[str]:
    """Return every track-like string attached to an audit row.

    Combines the ``Track`` column (typically a subtrack like
    ``Workloads`` or ``AWS``) with the ``Track:`` prefix of the
    ``Module`` label (``CKA 2.8: ...``, ``Platform: ...``).
    """
    out: set[str] = set()
    track_col = str(row.get("track", "")).strip().lower()
    if track_col:
        out.add(track_col)
    module_label = str(row.get("module", ""))
    m = _LABEL_TRACK_PREFIX_RE.match(module_label)
    if m:
        out.add(m.group("track").strip().lower())
    return out


def _alias_matches(alias: str, candidates: set[str]) -> bool:
    """Whole-word check so ``cka`` doesn't match ``ckad``."""
    pattern = re.compile(r"\b" + re.escape(alias) + r"\b")
    return any(pattern.search(c) for c in candidates)


_CERT_TRACKS = frozenset({"cka", "ckad", "cks", "kcna", "kcsa"})


def _track_word_set(track_slug: str | None, aliases: tuple[str, ...]) -> set[str]:
    """Tokens that should NOT count as a non-track overlap signal.

    Used to make the name-overlap match meaningful: an overlap of
    ``{platform, sre}`` between a module path and a "Platform: SRE…"
    label is vacuous when both are track tokens for this module.
    """
    out: set[str] = set()
    if track_slug:
        out |= _normalize_name_tokens(track_slug)
    for alias in aliases:
        out |= _normalize_name_tokens(alias)
    # Cert paths share a ``k8s/`` parent segment that's structural,
    # not semantic. Without this the label "CKA: k8s.io Navigation"
    # matches any k8s/cka/* module via the vacuous ``{cka, k8s}``
    # overlap.
    if track_slug in _CERT_TRACKS:
        out.add("k8s")
    return out


def _normalize_name_tokens(text: str) -> set[str]:
    """Split a string into a lowercase-alphanumeric token set suitable
    for overlap comparison. Drops pure numbers and stop-words."""
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    return {
        tok
        for tok in tokens
        if tok
        and not tok.isdigit()
        and tok not in _NAME_TOKEN_STOPLIST
    }


def _rubric_severity_for_module(
    module_key: str, audit_modules: list[dict[str, Any]]
) -> str | None:
    """Best-effort match from a module path to an audit-doc entry.

    Matching has three stages, each requiring a STRICT track match
    when the module path has a recognized track — we never fall back
    to "any track matches" (that was a round-2 false-positive source).

    1. Numbered match. Extract ``(track, number)`` from the path.
       Require the audit ``track`` column to match a track alias
       AND the audit ``module`` label to contain the number with
       word boundaries (so "2.8" doesn't match "12.8"). Accepts
       labels like "CKA 2.8: ...", "... 2.8 - ...", "... 2.8) ...".

    2. Name-overlap match. For audit rows that have no module
       number (e.g. ``Platform: Systems Thinking``), compute the
       overlap between the module path's name tokens and the
       label's tokens. Require ≥ 2 shared tokens plus a track-
       alias match. This covers the non-numbered rubric entries
       that round-2 flagged.

    3. Return None. Unknown track → no match, to avoid the
       "any row wins" false positive.
    """
    segments = module_key.split("/")
    last_raw = segments[-1]
    last = last_raw.lower()
    num_match = _MODULE_NUMBER_RE.search(last)
    number = num_match.group(1) if num_match else None

    # Detect the track from the path.
    track_slug = None
    for seg in segments:
        key = seg.lower()
        if key in _TRACK_ALIASES:
            track_slug = key
            break
    aliases = _TRACK_ALIASES.get(track_slug, ()) if track_slug else ()

    if not aliases:
        # Unknown track → no match (round-2 caught "any row wins"
        # false positives).
        return None

    # Track tokens for THIS module. Used both to filter audit rows
    # (whole-word match to avoid cka/ckad collision) and to compute
    # "non-track overlap" in stage 2.
    track_word_set = _track_word_set(track_slug, aliases)

    def _row_track_matches(row: dict[str, Any]) -> bool:
        candidates = _audit_row_track_tokens(row)
        return any(_alias_matches(alias, candidates) for alias in aliases)

    # ----- stage 1: numbered match -----
    if number:
        number_re = re.compile(
            r"(?:^|[\s(])" + re.escape(number) + r"(?=[\s:\-\)—.,])"
        )
        for entry in audit_modules:
            label = str(entry.get("module", ""))
            if not number_re.search(label):
                continue
            if _row_track_matches(entry):
                return entry.get("severity")

    # ----- stage 2: name-overlap match -----
    name_slug = _MODULE_NUMBER_PREFIX_RE.sub("", last)
    path_tokens = _normalize_name_tokens(name_slug)
    for seg in segments[:-1]:
        if _PART_PREFIX_RE.match(seg):
            continue
        path_tokens |= _normalize_name_tokens(seg)
    if not path_tokens:
        return None

    best: tuple[int, str | None] = (0, None)
    for entry in audit_modules:
        if not _row_track_matches(entry):
            continue
        label_tokens = _normalize_name_tokens(str(entry.get("module", "")))
        overlap = path_tokens & label_tokens
        # Require ≥ 2 overlap AND at least one NON-track-alias token
        # in the overlap; otherwise ``{platform, sre}`` alone would
        # attach any "Platform: ... SRE ..." row to every platform
        # module containing "sre".
        if len(overlap) < 2:
            continue
        non_track = overlap - track_word_set
        if not non_track:
            continue
        score = len(overlap) + len(non_track)
        if score > best[0]:
            best = (score, entry.get("severity"))
    return best[1]


def build_issue_watch_state(repo_root: Path, issue_number: int) -> dict[str, Any] | None:
    path = repo_root / ".pipeline" / "issue-watch" / f"{issue_number}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "issue_number": issue_number,
            "error": "invalid_state_json",
            "path": str(path),
        }
    if not isinstance(payload, dict):
        return {
            "issue_number": issue_number,
            "error": "invalid_state_shape",
            "path": str(path),
        }
    comments = payload.get("comments", [])
    last_comment = comments[-1] if isinstance(comments, list) and comments else None
    return {
        "issue_number": issue_number,
        "path": str(path),
        "title": payload.get("title", ""),
        "url": payload.get("url", ""),
        "state": payload.get("state", ""),
        "updated_at": payload.get("updatedAt", ""),
        "comments_count": len(comments) if isinstance(comments, list) else 0,
        "last_comment": last_comment,
    }


def _process_age_seconds(pid: int) -> float | None:
    """Return the process's elapsed running time in seconds, or None if unknown.

    Uses POSIX `ps -o etime=` (portable across Linux and macOS). Parsing
    handles the `[[DD-]HH:]MM:SS` format `ps` emits.
    """
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etime="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    etime = result.stdout.strip()
    if not etime:
        return None
    try:
        days = 0
        if "-" in etime:
            days_str, etime = etime.split("-", 1)
            days = int(days_str)
        parts = etime.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = (int(p) for p in parts)
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = (int(p) for p in parts)
        else:
            return None
    except ValueError:
        return None
    return float(days * 86400 + hours * 3600 + minutes * 60 + seconds)


# If a process's age exceeds the pid-file age by more than this many seconds,
# treat the PID as reused (the real owner exited and a new process inherited
# the PID). 60s absorbs normal pid-file write jitter.
_PID_REUSE_SLACK_SECONDS = 60.0


def _inspect_pid_file(pid_path: Path) -> dict[str, Any]:
    """Read a pid file and probe the process. Returns pid, status, uptime, stale flag.

    Detects PID reuse: if the live process started meaningfully before the
    pid file was written, the pid file is treated as stale rather than
    claiming a healthy service.
    """
    pid: int | None = None
    status = "stopped"
    uptime_seconds: float | None = None
    stale_pid_file = False
    pid_file_mtime: float | None = None

    if not pid_path.exists():
        return {
            "pid": None,
            "status": "stopped",
            "uptime_seconds": None,
            "stale_pid_file": False,
            "pid_file_mtime": None,
        }

    try:
        stat_result = pid_path.stat()
        pid_file_mtime = stat_result.st_mtime
    except OSError:
        pid_file_mtime = None

    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid = None

    if pid is not None:
        try:
            os.kill(pid, 0)  # Signal 0 probes existence without delivering a signal.
        except OSError:
            status = "stale"
            stale_pid_file = True
        else:
            proc_age = _process_age_seconds(pid)
            if proc_age is not None and pid_file_mtime is not None:
                pid_file_age = max(0.0, time.time() - pid_file_mtime)
                if proc_age > pid_file_age + _PID_REUSE_SLACK_SECONDS:
                    # Process existed long before the pid file was written -> reused PID.
                    status = "stale"
                    stale_pid_file = True
                else:
                    status = "running"
                    uptime_seconds = proc_age
            else:
                status = "running"
                if pid_file_mtime is not None:
                    uptime_seconds = max(0.0, time.time() - pid_file_mtime)
    else:
        status = "stale"
        stale_pid_file = True

    return {
        "pid": pid,
        "status": status,
        "uptime_seconds": uptime_seconds,
        "stale_pid_file": stale_pid_file,
        "pid_file_mtime": pid_file_mtime,
    }


def _humanize_service_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def build_runtime_services_status(repo_root: Path) -> dict[str, Any]:
    services: list[dict[str, Any]] = []
    running = 0
    stopped = 0
    stale = 0

    seen_names: set[str] = set()
    for svc in RUNTIME_SERVICES:
        pid_path = repo_root / svc["pid_file"]
        probe = _inspect_pid_file(pid_path)
        seen_names.add(svc["name"])
        if probe["status"] == "running":
            running += 1
        elif probe["status"] == "stale":
            stale += 1
        else:
            stopped += 1
        services.append(
            {
                "name": svc["name"],
                "label": svc["label"],
                "status": probe["status"],
                "pid": probe["pid"],
                "port": svc["port"],
                "pid_file": str(pid_path),
                "uptime_seconds": probe["uptime_seconds"],
                "stale_pid_file": probe["stale_pid_file"],
                "known": True,
            }
        )

    # Auto-discover pid files not covered by the curated list so operators can
    # see workers spawned by scripts that haven't been registered yet.
    pids_dir = repo_root / ".pids"
    if pids_dir.is_dir():
        for pid_path in sorted(pids_dir.glob("*.pid")):
            name = pid_path.stem
            if name in seen_names:
                continue
            probe = _inspect_pid_file(pid_path)
            if probe["status"] == "running":
                running += 1
            elif probe["status"] == "stale":
                stale += 1
            else:
                stopped += 1
            services.append(
                {
                    "name": name,
                    "label": _humanize_service_name(name),
                    "status": probe["status"],
                    "pid": probe["pid"],
                    "port": None,
                    "pid_file": str(pid_path),
                    "uptime_seconds": probe["uptime_seconds"],
                    "stale_pid_file": probe["stale_pid_file"],
                    "known": False,
                }
            )

    return {
        "running": running,
        "stopped": stopped,
        "stale": stale,
        "total": running + stopped + stale,
        "services": services,
        "repo": _repo_guard_module().inspect_repo_root(repo_root),
    }


def build_recent_activity(repo_root: Path) -> dict[str, Any]:
    """Recent operator-relevant activity across git, pipeline, bridge, and watched issue.

    Keeps the payload compact and deterministic so humans and agents can answer
    "what changed recently?" without stitching together git log, queue reads,
    bridge DB tails, and issue-watch files themselves.
    """
    commits = _recent_commits(repo_root, limit=10)

    try:
        pipeline = build_pipeline_events(repo_root, None, None, limit=15)
    except Exception as exc:  # noqa: BLE001
        pipeline = {"error": f"{type(exc).__name__}: {exc}", "events": []}

    pipeline_events = []
    if isinstance(pipeline, dict):
        for event in (pipeline.get("events") or [])[:10]:
            pipeline_events.append(
                {
                    "id": event.get("id"),
                    "type": event.get("type"),
                    "module_key": event.get("module_key"),
                    "at": event.get("at"),
                }
            )

    try:
        bridge = build_bridge_messages(repo_root, None, limit=10)
    except Exception as exc:  # noqa: BLE001
        bridge = {"error": f"{type(exc).__name__}: {exc}", "messages": []}

    bridge_messages = []
    if isinstance(bridge, dict):
        for msg in (bridge.get("messages") or [])[:8]:
            bridge_messages.append(
                {
                    "id": msg.get("id"),
                    "created_at": msg.get("created_at"),
                    "from_agent": msg.get("from_agent"),
                    "to_agent": msg.get("to_agent"),
                    "kind": msg.get("kind"),
                    "task_id": msg.get("task_id"),
                }
            )

    issue = build_issue_watch_state(repo_root, DEFAULT_FEEDBACK_ISSUE)
    watched_issue = None
    if issue:
        watched_issue = {
            "number": issue.get("number") or DEFAULT_FEEDBACK_ISSUE,
            "title": issue.get("title"),
            "state": issue.get("state"),
            "updated_at": issue.get("updated_at") or issue.get("updatedAt"),
            "comments_count": issue.get("comments_count") or len(issue.get("comments") or []),
            "latest_comment_preview": issue.get("latest_comment_preview"),
            "url": issue.get("url") or issue.get("html_url"),
        }

    return {
        "generated_at": time.time(),
        "recent_commits": commits,
        "pipeline_events": pipeline_events,
        "bridge_messages": bridge_messages,
        "watched_issue": watched_issue,
    }


_ACTIVITY_DEFAULT_SINCE_SECONDS = 86400  # 24h
_ACTIVITY_MAX_LIMIT = 500


def _iso_to_epoch(value: Any) -> int | None:
    """Parse an ISO-8601 timestamp to Unix-epoch seconds.

    Accepts the bridge's ``YYYY-MM-DDTHH:MM:SS[.ffffff][Z|+00:00]`` shape.
    Returns ``None`` on unparseable / absent input so the caller can drop
    the item rather than anchoring the feed at epoch-0.
    """
    if not isinstance(value, str) or not value:
        return None
    from datetime import datetime, timezone
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _recent_commits_with_time(
    repo_root: Path,
    *,
    since_seconds: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Like ``_recent_commits`` but each row carries a committer-time ``at``.

    Used by the merged activity feed so commits can be sorted against
    pipeline events and bridge messages on a single axis. ``since_seconds``
    is applied via ``git log --since=@<epoch>`` (inclusive).
    """
    capped = max(1, min(int(limit), 500))
    cmd = ["git", "log", f"-n{capped}", "--pretty=format:%h%x09%ct%x09%s"]
    if since_seconds is not None:
        cmd.insert(2, f"--since=@{int(since_seconds)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    commits: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        sha, ct, subject = parts
        try:
            at = int(ct)
        except ValueError:
            continue
        commits.append({"sha": sha, "at": at, "subject": subject})
    return commits


def build_activity_feed(
    repo_root: Path,
    *,
    since_seconds: int | None = None,
    limit: int = 50,
    now_seconds: int | None = None,
) -> dict[str, Any]:
    """Merged chronological feed: git commits + pipeline v2 events + bridge messages.

    Everything is normalized to one item shape so operators see a single
    timeline. Each source is fetched with a per-source cap of ``4 * limit``
    (min 50) before merging so a quiet source isn't crowded out at the
    merge boundary. Items with an unparseable timestamp are dropped, not
    anchored at 0 — otherwise they'd always rank last in ascending order
    or first in descending, hiding real recent activity.

    Defaults: ``since_seconds`` = now − 24 h, ``limit`` = 50 (max 500).
    """
    now_seconds = now_seconds if now_seconds is not None else int(time.time())
    if since_seconds is None:
        since_seconds = now_seconds - _ACTIVITY_DEFAULT_SINCE_SECONDS
    capped = max(1, min(int(limit), _ACTIVITY_MAX_LIMIT))
    per_source_cap = max(capped * 4, 50)

    items: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {
        "commit": 0,
        "pipeline_event": 0,
        "bridge_message": 0,
    }
    errors: dict[str, str] = {}

    try:
        commits = _recent_commits_with_time(
            repo_root, since_seconds=since_seconds, limit=per_source_cap
        )
    except Exception as exc:  # noqa: BLE001
        commits = []
        errors["commit"] = f"{type(exc).__name__}: {exc}"
    for c in commits:
        items.append({
            "source": "commit",
            "at": c.get("at"),
            "kind": "commit",
            "module_key": None,
            "summary": c.get("subject"),
            "ref": {"sha": c.get("sha")},
        })
        source_counts["commit"] += 1

    # Pipeline events: order by ``at`` DESC (NOT ``id`` DESC). Event
    # rows can be backfilled with an older ``at`` than their ``id`` —
    # ``build_pipeline_events`` uses ``id`` ordering for its own
    # purposes, but using that here would let a high-id/low-at
    # backfill consume a per-source slot and push a genuinely newer
    # event out of the merge candidates. See Codex Phase D review.
    try:
        db_path = repo_root / ".pipeline" / "v2.db"
        if db_path.exists():
            event_rows = _query_sqlite_rows(
                db_path,
                """
                SELECT id, type, module_key, lease_id, at
                FROM events
                WHERE at >= ?
                ORDER BY at DESC
                LIMIT ?
                """,
                (int(since_seconds), int(per_source_cap)),
            )
        else:
            event_rows = []
    except Exception as exc:  # noqa: BLE001
        event_rows = []
        errors["pipeline_event"] = f"{type(exc).__name__}: {exc}"
    for e in event_rows:
        items.append({
            "source": "pipeline_event",
            "at": e.get("at"),
            "kind": e.get("type"),
            "module_key": e.get("module_key"),
            "summary": None,
            "ref": {"event_id": e.get("id"), "lease_id": e.get("lease_id")},
        })
        source_counts["pipeline_event"] += 1

    # Bridge messages: fetch newest-first WITHOUT a SQL ``since`` filter,
    # then filter in Python via ``_iso_to_epoch``. The SQL filter is a
    # lexical string compare against an ISO timestamp column that may
    # contain fractional seconds or ``+00:00`` offsets — a ``...Z``
    # cutoff lexically drops ``...0.500Z`` and ``...+00:00`` rows even
    # when they represent later absolute times. See Codex Phase D review.
    try:
        bridge = build_bridge_messages(repo_root, None, limit=per_source_cap)
    except Exception as exc:  # noqa: BLE001
        bridge = {"messages": []}
        errors["bridge_message"] = f"{type(exc).__name__}: {exc}"
    for m in (bridge.get("messages") or []):
        at = _iso_to_epoch(m.get("timestamp"))
        if at is None or at < since_seconds:
            continue
        items.append({
            "source": "bridge_message",
            "at": at,
            "kind": m.get("message_type"),
            "module_key": None,
            "summary": f"{m.get('from_llm') or '?'}→{m.get('to_llm') or '?'}",
            "ref": {"message_id": m.get("id"), "task_id": m.get("task_id")},
        })
        source_counts["bridge_message"] += 1

    # Drop items with no usable timestamp (would cluster at the top/bottom
    # depending on sort direction and mislead operators).
    items = [it for it in items if isinstance(it.get("at"), (int, float))]
    items.sort(key=lambda it: int(it["at"]), reverse=True)
    items = items[:capped]

    payload: dict[str, Any] = {
        "generated_at": now_seconds,
        "since_seconds": since_seconds,
        "limit": capped,
        "count": len(items),
        "source_counts": source_counts,
        "items": items,
    }
    if errors:
        payload["errors"] = errors
    return payload


# ---- Phase D: per-section track readiness ----


def _section_for_key(module_key: str) -> str:
    """Second path segment of a module key; ``_root`` for top-level modules.

    Examples: ``k8s/cka/module-1.1-foo`` → ``cka``; ``prerequisites/
    module-1.1-foo`` → ``_root``. Keeps top-level tracks from crashing
    the grid while still bucketing them as a real section.
    """
    parts = str(module_key).split("/")
    if len(parts) < 3:
        return "_root"
    return parts[1]


# ---- quality board (per-module status grid for the operator dashboard) ----


_QUALITY_BOARD_IN_FLIGHT_STAGES = frozenset({
    "WRITE_PENDING",
    "WRITE_IN_PROGRESS",
    "REVIEW_PENDING",
    "REVIEW_IN_PROGRESS",
    "CITATION_VERIFY",
    "MERGE_PENDING",
    "REVIEW_APPROVED",
})
_QUALITY_BOARD_DONE_STAGES = frozenset({"COMMITTED", "SKIPPED"})
_QUALITY_BOARD_STATUS_KEYS = ("done", "needs_rewrite", "needs_review", "shipped_unreviewed", "both", "in_flight")
_QUALITY_BOARD_REVISION_RE = re.compile(r"^revision_pending\s*:\s*true", re.MULTILINE)
_QUALITY_BOARD_REVIEW_VERDICT_RE = re.compile(
    r"^## .*?— `REVIEW`(?: — `(?P<verdict>APPROVE|REJECT)`)?.*?$",
    re.MULTILINE,
)


def _quality_board_slug_for_path(rel_path: str) -> str:
    """Slug used for ``.pipeline/quality-pipeline/<slug>.json`` files.

    Mirrors the convention emitted by ``scripts/quality/queue.py``: drop
    the ``.md`` suffix and replace ``/`` with ``-`` on the docs-relative
    path. Example: ``ai/foundations/module-1.1-what-is-ai.md`` →
    ``ai-foundations-module-1.1-what-is-ai``.
    """
    stem = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    return stem.replace("/", "-")


def _quality_board_has_revision_banner(text: str) -> bool:
    """``revision_pending: true`` line inside the leading frontmatter
    block (we only check the head so a literal banner string buried in
    prose can't trigger it)."""
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---", 4)
    head = text[: end + 4] if end >= 0 else text[:2000]
    return bool(_QUALITY_BOARD_REVISION_RE.search(head))


def _quality_board_load_states(repo_root: Path, *, exclude_slugs: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """Load every ``.pipeline/quality-pipeline/<slug>.json`` (skip
    ``*.lock`` siblings). Indexed by slug. Malformed files are silently
    skipped — the board has to keep rendering even if one state file is
    half-written by an in-flight worker."""
    state_dir = repo_root / ".pipeline" / "quality-pipeline"
    out: dict[str, dict[str, Any]] = {}
    if not state_dir.is_dir():
        return out
    for path in state_dir.glob("*.json"):
        if path.name.endswith(".lock"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        slug = str(data.get("slug") or path.stem)
        if exclude_slugs and slug in exclude_slugs:
            continue
        out[slug] = data
    return out


def _quality_board_load_post_review_queue(repo_root: Path) -> set[str]:
    queue_path = repo_root / ".pipeline" / "quality-pipeline" / "post-review-queue.txt"
    if not queue_path.is_file():
        return set()
    try:
        text = queue_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {line.strip() for line in text.splitlines() if line.strip()}


def _quality_board_count_revision_pending_docs(docs_root: Path) -> int:
    if not docs_root.exists():
        return 0
    count = 0
    for path in docs_root.rglob("*.md"):
        if path.name == "index.md":
            continue
        try:
            if _quality_board_has_revision_banner(path.read_text(encoding="utf-8")):
                count += 1
        except OSError:
            continue
    return count


def _quality_board_latest_review_verdicts(repo_root: Path) -> dict[str, str]:
    """Latest explicit REVIEW verdict from ``.pipeline/reviews`` logs.

    The audit format is append-only markdown. Older entries may omit a
    verdict in the heading, so only explicit APPROVE/REJECT markers are
    returned.
    """
    reviews_dir = repo_root / _REVIEW_AUDIT_DIR
    if not reviews_dir.is_dir():
        return {}
    verdicts: dict[str, str] = {}
    for path in reviews_dir.glob("*.md"):
        if path.name.endswith(".lock"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        explicit = [
            match.group("verdict").lower()
            for match in _QUALITY_BOARD_REVIEW_VERDICT_RE.finditer(text)
            if match.group("verdict")
        ]
        if explicit:
            verdicts[_review_filename_to_module_key(path.name)] = explicit[-1]
    return verdicts


def _quality_board_classify(
    *,
    score: float | None,
    revision_pending: bool,
    stage: str | None,
    auto_approved: bool,
    in_post_review_queue: bool,
    latest_verdict: str | None,
) -> str:
    """Apply the precedence ladder from issue #389.

    Order is mutually exclusive — first match wins:
      in_flight > both > needs_review > shipped_unreviewed > needs_rewrite > done.

    ``shipped_unreviewed`` separates ad-hoc-shipped modules
    (stage=UNAUDITED + score>=4 + no banner) from active mid-pipeline
    review queue items so the operator can tell bookkeeping debt apart
    from in-flight reviews.
    """
    score_val = float(score) if score is not None else 0.0
    needs_deferred_review = auto_approved and in_post_review_queue
    if stage in _QUALITY_BOARD_IN_FLIGHT_STAGES:
        return "in_flight"
    if needs_deferred_review and (score_val < 4.0 or revision_pending):
        return "both"
    if needs_deferred_review:
        return "needs_review"
    if revision_pending or score_val < 3.0 or stage == "FAILED":
        return "needs_rewrite"
    if (
        score_val >= 4.0
        and not revision_pending
        and (stage is None or stage in _QUALITY_BOARD_DONE_STAGES)
        and (latest_verdict is None or latest_verdict == "approve")
    ):
        return "done"
    # Ad-hoc-shipped modules: passed the structural rubric (score >= 4.0)
    # and merged on main, but the pipeline state machine never recorded
    # an independent-family review. Distinct from `needs_review` (which
    # is mid-pipeline/awaiting-reviewer) so the operator can tell
    # "shipped without review" apart from "review in flight". Same
    # actionable category — needs cross-family review — but separates
    # the bookkeeping debt from the active review queue.
    if score_val >= 4.0 and not revision_pending and stage == "UNAUDITED":
        return "shipped_unreviewed"
    # Anything left over (e.g. score 3.0–3.9 with no banner, no review,
    # no auto-approve, no FAILED) is a soft "needs_review" — surface it
    # so the operator sees it instead of silently hiding modules from
    # the board.
    return "needs_review"


def _quality_board_classify_book_chapter(*, latest_verdict: str | None) -> str:
    """Classify narrative book chapters without applying module scoring.

    AI History chapters are live site content but are not pipeline modules.
    With no review log they are shipped-but-unreviewed, not structurally
    ``done`` because there is no module rubric score or pipeline state.
    """
    if latest_verdict == "approve":
        return "done"
    if latest_verdict == "reject":
        return "needs_rewrite"
    return "shipped_unreviewed"


def _quality_board_empty_totals() -> dict[str, int]:
    return {**dict.fromkeys(_QUALITY_BOARD_STATUS_KEYS, 0), "total": 0}


def build_quality_board(repo_root: Path) -> dict[str, Any]:
    """Per-module status grid joining heuristic scores, pipeline state,
    revision banners, the post-review queue, and review verdicts.

    Status precedence (first match wins): ``in_flight`` >
    ``both`` > ``needs_review`` > ``shipped_unreviewed`` >
    ``needs_rewrite`` > ``done``.
    See issue #389 for the contract.

    ``shipped_unreviewed`` is for modules that passed the structural
    rubric (score >= 4.0) and merged on main but have stage=UNAUDITED —
    i.e. ad-hoc shipments the pipeline state machine never tracked.
    Same actionable category as ``needs_review`` (cross-family review
    pending) but separated so the operator can distinguish bookkeeping
    debt from active in-flight reviews.
    """
    docs_root = repo_root / "src" / "content" / "docs"
    if not docs_root.exists():
        return {
            "generated_at": int(time.time()),
            "totals": _quality_board_empty_totals(),
            "book_totals": _quality_board_empty_totals(),
            "tracks": [],
            "modules": [],
        }

    # Reuse heuristic scores so the rubric numbers stay consistent
    # with /api/quality/scores. Index by docs-relative path.
    quality = build_quality_scores(repo_root)
    score_by_path: dict[str, dict[str, Any]] = {}
    for entry in quality.get("modules") or []:
        rel = str(entry.get("path") or "")
        if rel:
            score_by_path[rel] = entry

    # Iterate every EN module on disk so we cover modules with no state
    # file (e.g. UNAUDITED) and modules with no review log yet. AI
    # History chapters are additive board entries, not quality-score
    # modules, so they get a distinct content_type and separate totals.
    module_paths = sorted(
        path
        for path in docs_root.glob("**/module-*.md")
        if ".staging." not in path.name
        and not path.relative_to(docs_root).as_posix().startswith("uk/")
    )
    book_paths = sorted(
        path
        for path in (docs_root / "ai-history").glob("ch-*.md")
        if ".staging." not in path.name
    )
    board_paths: list[tuple[Path, str]] = [(path, "module") for path in module_paths] + [
        (path, "book_chapter") for path in book_paths
    ]
    redirect_stub_slugs: set[str] = set()
    for path, _content_type in board_paths:
        rel_str = path.relative_to(docs_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _quality_is_redirect_stub(text):
            redirect_stub_slugs.add(_quality_board_slug_for_path(rel_str))

    states = _quality_board_load_states(repo_root, exclude_slugs=redirect_stub_slugs)
    post_review_queue = _quality_board_load_post_review_queue(repo_root) - redirect_stub_slugs
    latest_review_verdicts = _quality_board_latest_review_verdicts(repo_root)

    modules: list[dict[str, Any]] = []
    track_buckets: dict[str, dict[str, Any]] = {}
    totals = _quality_board_empty_totals()
    book_totals = _quality_board_empty_totals()
    source_counts = {
        "quality_pipeline_records": len(states),
        "committed_full_review": sum(
            1 for state in states.values() if state.get("stage") == "COMMITTED" and (state.get("review") or {}).get("auto_approved") is not True
        ),
        "committed_auto_approved": sum(
            1 for state in states.values() if state.get("stage") == "COMMITTED" and (state.get("review") or {}).get("auto_approved") is True
        ),
        "revision_pending": _quality_board_count_revision_pending_docs(docs_root),
        "english_module_revision_pending": 0,
        "book_chapter_revision_pending": 0,
        "english_book_chapters": 0,
        "post_review_queue": len(post_review_queue),
    }

    for path, content_type in board_paths:
        rel = path.relative_to(docs_root)
        rel_str = rel.as_posix()
        slug = _quality_board_slug_for_path(rel_str)
        if slug in redirect_stub_slugs:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        revision_pending = _quality_board_has_revision_banner(text)
        if revision_pending:
            if content_type == "book_chapter":
                source_counts["book_chapter_revision_pending"] += 1
            else:
                source_counts["english_module_revision_pending"] += 1
        if content_type == "book_chapter":
            source_counts["english_book_chapters"] += 1

        score_entry = score_by_path.get(rel_str) if content_type == "module" else None
        score = float(score_entry["score"]) if score_entry and score_entry.get("score") is not None else None

        state = states.get(slug) or {}
        stage_raw = state.get("stage")
        stage = str(stage_raw) if stage_raw else ("none" if content_type == "book_chapter" else "UNAUDITED")
        review = state.get("review") or {}
        auto_approved = review.get("auto_approved") is True
        verdict_raw = review.get("verdict")
        latest_verdict = (
            str(verdict_raw).strip().lower() if isinstance(verdict_raw, str) and verdict_raw else None
        )

        title, module_key_label = _quality_title_and_label(rel, text)
        track = _quality_track_label(rel)

        # Review-log lookup uses the docs-relative key without the .md
        # suffix (matches _module_key_to_review_filename semantics).
        review_key = rel_str[:-3] if rel_str.endswith(".md") else rel_str
        if latest_verdict is None:
            latest_verdict = latest_review_verdicts.get(review_key)

        if content_type == "book_chapter":
            status = _quality_board_classify_book_chapter(latest_verdict=latest_verdict)
        else:
            status = _quality_board_classify(
                score=score,
                revision_pending=revision_pending,
                stage=stage_raw if stage_raw else None,
                auto_approved=auto_approved,
                in_post_review_queue=slug in post_review_queue,
                latest_verdict=latest_verdict,
            )

        module = {
            "module_key": module_key_label,
            "title": title,
            "slug": slug,
            "path": rel_str,
            "track": track,
            "status": status,
            "score": score,
            "revision_pending": revision_pending,
            "stage": stage,
            "auto_approved": auto_approved,
            "in_post_review_queue": slug in post_review_queue,
            "latest_review_verdict": latest_verdict,
        }
        if content_type == "book_chapter":
            module["content_type"] = "book_chapter"
        modules.append(module)

        subtotal = book_totals if content_type == "book_chapter" else totals
        subtotal[status] += 1
        subtotal["total"] += 1
        bucket = track_buckets.setdefault(
            track,
            {
                **_quality_board_empty_totals(),
                "modules": [],
            },
        )
        bucket[status] += 1
        bucket["total"] += 1
        bucket["modules"].append(module)

    tracks = [
        {
            "track": track,
            "totals": {k: v for k, v in counts.items() if k != "modules"},
            **counts,
        }
        for track, counts in sorted(track_buckets.items(), key=lambda item: item[0].lower())
    ]

    return {
        "generated_at": int(time.time()),
        "totals": totals,
        "book_totals": book_totals,
        "content_totals": {"module": totals, "book_chapter": book_totals},
        "source_counts": source_counts,
        "tracks": tracks,
        "modules": modules,
    }


def _load_source_acceptance_bind():
    """Fail closed if the receipt evaluator cannot be imported."""
    try:
        from quality.content_inventory import _load_receipts
        from quality.source_acceptance import (
            EVIDENCE_LEDGER,
            SEEDS_DIR,
            bind_source_acceptance,
            load_seed_bytes,
            nested_source_receipt,
        )
    except ImportError:
        return None
    return {
        "load_receipts": _load_receipts,
        "ledger": EVIDENCE_LEDGER,
        "seeds": SEEDS_DIR,
        "bind": bind_source_acceptance,
        "load_seed": load_seed_bytes,
        "nested": nested_source_receipt,
    }


def _source_accepted_for_page(
    bind: dict[str, Any] | None,
    receipts: dict[str, Any],
    seeds_dir: Path | None,
    page_rel: str,
    page_bytes: bytes,
) -> bool:
    if bind is None:
        return False
    result = bind["bind"](
        bind["nested"](receipts.get(page_rel)),
        page_bytes=page_bytes,
        seed_bytes=bind["load_seed"](seeds_dir, page_rel),
    )
    return result.get("accepted") is True


def build_tracks_readiness(repo_root: Path) -> dict[str, Any]:
    """Per-track, per-section readiness grid for the operator dashboard.

    Buckets every English module on disk into one of:
      - ``cleared`` — frontmatter says ``revision_pending`` is not true and ``citations_verified`` is true
      - ``not_yet_enqueued`` — every other state

    ``source_accepted`` is independent of ``cleared`` and increments only
    for a complete applicable receipt bound to the live page and seed.

    Readiness % = ``cleared / total``. Tracks come out in the canonical
    ``TRACK_ORDER``; within a track, sections are alphabetical so the
    grid layout is stable across calls.
    """
    started_at = time.perf_counter()
    docs_root = repo_root / "src" / "content" / "docs"
    from status import TRACK_ORDER, _extract_frontmatter, _iter_en_modules, _track_for_key

    read_errors = 0
    bind = _load_source_acceptance_bind()
    receipts: dict[str, Any] = {}
    seeds_dir: Path | None = None
    if bind is not None:
        ledger = repo_root / bind["ledger"]
        receipts, _, invalid = bind["load_receipts"](ledger if ledger.is_file() else None)
        if invalid:
            receipts = {}
        candidate = repo_root / bind["seeds"]
        seeds_dir = candidate if candidate.is_dir() else None

    # track_slug -> section_slug -> counts
    grid: dict[str, dict[str, dict[str, int]]] = {}
    # Keep the old buckets so downstream dashboards stay compatible.
    # Unclear cases are represented as not-yet-enqueued until A^4 catchup.
    # Track-level in_flight/dead_letter are always 0 under A^4.

    for path in _iter_en_modules(docs_root):
        rel = path.relative_to(docs_root).as_posix()
        module_key = rel[:-3] if rel.endswith(".md") else rel
        try:
            page_bytes = path.read_bytes()
        except OSError:
            read_errors += 1
            continue
        frontmatter = _extract_frontmatter(path)
        # Non-bool values produce spec-correct but surprising behavior:
        #   revision_pending: "yes" → not True → counts as cleared
        #   citations_verified: 1   → not True → counts as uncleared
        # This is intentional: only literal True/False/absent are valid frontmatter states.
        cleared = (
            frontmatter.get("revision_pending") is not True
            and frontmatter.get("citations_verified") is True
        )
        track = _track_for_key(module_key)
        section = _section_for_key(module_key)
        bucket = "cleared" if cleared else "not_yet_enqueued"
        t = grid.setdefault(track, {})
        s = t.setdefault(
            section,
            {
                "total": 0,
                "cleared": 0,
                "source_accepted": 0,
                "in_flight": 0,
                "dead_letter": 0,
                "not_yet_enqueued": 0,
            },
        )
        s["total"] += 1
        s[bucket] += 1
        if _source_accepted_for_page(bind, receipts, seeds_dir, rel, page_bytes):
            s["source_accepted"] += 1

    track_labels = dict(TRACK_ORDER)
    canonical_order = [slug for slug, _ in TRACK_ORDER]
    # Preserve canonical order; append "other" and any unknown slugs at
    # the tail so a surprise top-level directory isn't swallowed.
    seen = set(canonical_order)
    extras = [t for t in grid if t not in seen]
    track_order = canonical_order + sorted(extras)

    out_tracks: list[dict[str, Any]] = []
    grand: dict[str, Any] = {
        "total": 0,
        "cleared": 0,
        "source_accepted": 0,
        "in_flight": 0,
        "dead_letter": 0,
        "not_yet_enqueued": 0,
    }
    for slug in track_order:
        sections_map = grid.get(slug)
        if not sections_map:
            continue
        sections: list[dict[str, Any]] = []
        track_total = 0
        track_cleared = 0
        track_source_accepted = 0
        track_in_flight = 0
        track_dead = 0
        track_notenq = 0
        for section_slug in sorted(sections_map.keys()):
            counts = sections_map[section_slug]
            total = counts["total"]
            cleared = counts["cleared"]
            source_accepted = counts["source_accepted"]
            readiness_pct = round(100.0 * cleared / total, 1) if total else 0.0
            sections.append({
                "slug": section_slug,
                "total": total,
                "cleared": cleared,
                "source_accepted": source_accepted,
                "in_flight": counts["in_flight"],
                "dead_letter": counts["dead_letter"],
                "not_yet_enqueued": counts["not_yet_enqueued"],
                "readiness_pct": readiness_pct,
            })
            track_total += total
            track_cleared += cleared
            track_source_accepted += source_accepted
            track_in_flight += counts["in_flight"]
            track_dead += counts["dead_letter"]
            track_notenq += counts["not_yet_enqueued"]
        out_tracks.append({
            "slug": slug,
            "label": track_labels.get(slug, slug.replace("-", " ").title()),
            "total": track_total,
            "cleared": track_cleared,
            "source_accepted": track_source_accepted,
            "in_flight": track_in_flight,
            "dead_letter": track_dead,
            "not_yet_enqueued": track_notenq,
            "readiness_pct": round(100.0 * track_cleared / track_total, 1) if track_total else 0.0,
            "sections": sections,
        })
        grand["total"] += track_total
        grand["cleared"] += track_cleared
        grand["source_accepted"] += track_source_accepted
        grand["in_flight"] += track_in_flight
        grand["dead_letter"] += track_dead
        grand["not_yet_enqueued"] += track_notenq

    grand["readiness_pct"] = (
        round(100.0 * grand["cleared"] / grand["total"], 1) if grand["total"] else 0.0
    )
    errors: dict[str, int] = {}
    if read_errors:
        errors["frontmatter_read_errors"] = read_errors
    return {
        "generated_at": int(time.time()),
        "duration_ms": round(1000.0 * (time.perf_counter() - started_at), 3),
        "errors": errors,
        "totals": grand,
        "tracks": out_tracks,
    }


def build_navigation_status(repo_root: Path) -> dict[str, Any]:
    """Detect route/nav surfaces that still require manual inspection.

    Signals:
    - top-level English track directories and whether they have matching UK hubs
    - candidate-stale index pages: any ``index.md`` older than content beneath it
    """
    docs_root = repo_root / "src" / "content" / "docs"
    uk_root = docs_root / "uk"

    top_level_tracks = []
    missing_uk_top_level = []
    for child in sorted(docs_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in {"uk", "test"}:
            continue
        en_index = child / "index.md"
        uk_index = uk_root / child.name / "index.md"
        module_count = sum(
            1
            for path in child.rglob("*.md")
            if path.name != "index.md"
        )
        item = {
            "slug": child.name,
            "english_index_exists": en_index.exists(),
            "ukrainian_index_exists": uk_index.exists(),
            "module_count": module_count,
        }
        top_level_tracks.append(item)
        if en_index.exists() and not uk_index.exists():
            missing_uk_top_level.append(child.name)

    stale_indexes = []
    for index_path in sorted(docs_root.rglob("index.md")):
        if "/uk/" in index_path.as_posix():
            continue
        try:
            index_mtime = index_path.stat().st_mtime
        except OSError:
            continue
        subtree_files = [
            path
            for path in index_path.parent.rglob("*.md")
            if path != index_path and "/uk/" not in path.as_posix()
        ]
        if not subtree_files:
            continue
        newest_child = max(subtree_files, key=lambda path: path.stat().st_mtime if path.exists() else 0.0)
        try:
            newest_child_mtime = newest_child.stat().st_mtime
        except OSError:
            continue
        if newest_child_mtime <= index_mtime:
            continue
        stale_indexes.append(
            {
                "index": str(index_path.relative_to(repo_root)),
                "newest_child": str(newest_child.relative_to(repo_root)),
                "lag_seconds": int(newest_child_mtime - index_mtime),
            }
        )

    stale_indexes.sort(key=lambda item: item["lag_seconds"], reverse=True)

    return {
        "generated_at": time.time(),
        "top_level_tracks": top_level_tracks,
        "missing_uk_top_level": missing_uk_top_level,
        "candidate_stale_indexes": stale_indexes[:100],
        "candidate_stale_count": len(stale_indexes),
    }


def _parse_site_health_output(output: str) -> dict[str, Any]:
    errors_match = re.search(r"RESULTS:\s+(\d+)\s+errors,\s+(\d+)\s+warnings", output)
    stats_match = re.search(
        r"STATS:\s+(\d+)\s+files,\s+(\d+)\s+modules,\s+(\d+)\s+links checked",
        output,
    )
    errors = int(errors_match.group(1)) if errors_match else None
    warnings = int(errors_match.group(2)) if errors_match else None
    stats = None
    if stats_match:
        stats = {
            "files": int(stats_match.group(1)),
            "modules": int(stats_match.group(2)),
            "links_checked": int(stats_match.group(3)),
        }
    return {
        "errors": errors,
        "warnings": warnings,
        "ok": errors == 0 if errors is not None else None,
        "stats": stats,
    }


def build_delivery_status(repo_root: Path) -> dict[str, Any]:
    """Delivery-facing readiness surface for build + health status.

    Answers the operator question: is the published output roughly current, and
    is the content tree structurally healthy, without requiring manual command
    runs and log parsing.
    """
    docs_root = repo_root / "src" / "content" / "docs"
    dist_root = repo_root / "dist"
    docs_files = [p for p in docs_root.rglob("*.md") if p.is_file()]
    newest_source = max((_path_mtime(p) for p in docs_files), default=0.0)
    dist_files = [p for p in dist_root.rglob("*") if p.is_file()] if dist_root.exists() else []
    newest_dist = max((_path_mtime(p) for p in dist_files), default=0.0)

    build_state = {
        "dist_exists": dist_root.exists(),
        "dist_file_count": len(dist_files),
        "newest_source_mtime": newest_source,
        "newest_dist_mtime": newest_dist,
        "up_to_date": bool(dist_files) and newest_dist >= newest_source,
    }

    try:
        try:
            health_exe = _venv_python_for_repo(repo_root)
        except FileNotFoundError:
            health_exe = shutil.which("python") or "python"
        health_cmd = [health_exe, "scripts/check_site_health.py"]
        result = subprocess.run(
            health_cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        health = _parse_site_health_output(result.stdout)
        health["exit_code"] = result.returncode
        health["summary_line"] = next(
            (line.strip() for line in result.stdout.splitlines() if line.startswith("RESULTS:")),
            None,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        health = {
            "ok": None,
            "errors": None,
            "warnings": None,
            "stats": None,
            "exit_code": None,
            "summary_line": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "generated_at": time.time(),
        "build": build_state,
        "site_health": health,
    }


_TOP_NAV_CSS = """
    :root {
      --topnav-h: 45px;
    }
    .topnav {
      position: sticky; top: 0; z-index: 60; min-height: var(--topnav-h);
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      padding: 12px 24px; background: rgba(17,24,39,0.84);
      border-bottom: 1px solid var(--border); backdrop-filter: blur(8px);
    }
    .topnav a { text-decoration: none; }
    .topnav .brand {
      color: var(--text); font-weight: 800; margin-right: 8px;
      letter-spacing: 0; font-size: 14px;
    }
    .topnav .navlink {
      color: var(--text-secondary, #9ca3af); padding: 5px 10px;
      border-radius: var(--radius-sm); font-size: 13px; font-weight: 600;
    }
    .topnav .navlink:hover {
      color: var(--text); background: var(--surface-1);
    }
    .topnav .navlink.active {
      color: var(--accent); background: var(--accent-muted, rgba(56,189,248,0.12)); font-weight: 700;
    }
"""


def _render_top_nav(active: str) -> str:
    links = [
        ("operator", "/operator", "Operator"),
        ("artifacts", "/artifacts", "Artifacts"),
        ("quality", "/quality", "Quality"),
        ("uk", "/uk", "Translation"),
        ("pipeline", "/pipeline", "Pipeline"),
        ("activity", "/activity", "Activity"),
        ("benchmarks", "/benchmarks", "Benchmarks"),
        ("agents", "/agents", "Agents"),
        ("telemetry", "/telemetry", "Telemetry"),
        ("headroom", "/headroom", "Headroom"),
        ("channels", "/channels", "Channels"),
        ("decisions", "/decisions", "Decisions"),
        ("health", "/health", "Health"),
    ]
    rendered_links = "\n  ".join(
        f'<a class="navlink{" active" if key == active else ""}" href="{href}">{label}</a>'
        for key, href, label in links
    )
    return f"""<nav class="topnav" role="navigation" aria-label="Local-API sections">
  <a class="brand" href="/">KubeDojo Local Monitor</a>
  {rendered_links}
</nav>"""


_BENCHMARK_REPORTS_REL = "calibration/v1/reports"
_BENCHMARK_LEDGER_REL = "calibration/v1/ledger.db"
_BENCHMARK_REPORT_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_ARTIFACT_ALLOWED_DIRS = (
    ".agent/session-state",
    "audit",
    "calibration/v1/reports",
    "docs/architecture",
    "docs/migrations",
    "docs/session-state",
    "docs/decisions",
    "docs/sessions",
    "docs/research",
    "docs/audits",
    "docs/references",
    "docs/briefs",
    "docs/bug-autopsies",
    "docs/dispatch-briefs",
)
_ARTIFACT_ASSET_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
}
_ARTIFACT_SECTION_SPECS = (
    ("Reports", "audit", ("**/*.html", "**/*.md")),
    ("Calibration reports", "calibration/v1/reports", ("**/*.html",)),
    ("Architecture", "docs/architecture", ("**/*.html",)),
    ("Migrations", "docs/migrations", ("**/*.html", "**/*.md")),
    ("Handoffs (live, local)", ".agent/session-state", ("*.html", "*.md")),
    ("Handoffs (pre-s196 history)", "docs/session-state", ("*.html", "*.md")),
    ("Decisions", "docs/decisions", ("**/*.html", "**/*.md")),
    ("Sessions", "docs/sessions", ("**/*.html", "**/*.md")),
    ("Research", "docs/research", ("**/*.html", "**/*.md")),
    ("Audits", "docs/audits", ("**/*.html", "**/*.md")),
    ("References", "docs/references", ("**/*.html", "**/*.md")),
    ("Briefs", "docs/briefs", ("**/*.html", "**/*.md")),
    ("Bug autopsies", "docs/bug-autopsies", ("**/*.html", "**/*.md")),
    ("Dispatch briefs", "docs/dispatch-briefs", ("**/*.html", "**/*.md")),
    ("Docs", "docs", ("*.md",)),
    ("Repository root", ".", ("*.md",)),
)
_ARTIFACT_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
_ARTIFACT_MARKDOWN_CACHE: dict[str, tuple[int, int, str]] = {}
_ARTIFACT_INDEX_CACHE: dict[str, tuple[float, dict[str, list[dict[str, Any]]]]] = {}
_ARTIFACT_INDEX_CACHE_TTL_SECONDS = 30.0
_ARTIFACT_DEFERRED_INDEX_CATEGORIES = {"Research"}
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _artifact_content_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    return _ARTIFACT_ASSET_TYPES.get(suffix)


def _artifact_allowed_roots(repo_root: Path) -> list[Path]:
    return [(repo_root / rel).resolve() for rel in _ARTIFACT_ALLOWED_DIRS]


def _artifact_allowed_top_level_markdown(repo_root: Path, candidate: Path) -> bool:
    if candidate.suffix.lower() != ".md":
        return False
    repo = repo_root.resolve()
    docs = (repo_root / "docs").resolve()
    return candidate.parent in {repo, docs}


def _resolve_artifact_path(repo_root: Path, rel_path: str) -> Path | None:
    if not rel_path or rel_path.startswith("/") or "\\" in rel_path:
        return None
    parts = rel_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None

    candidate = (repo_root / rel_path).resolve()
    if _artifact_allowed_top_level_markdown(repo_root, candidate):
        return candidate
    for allowed_dir in _artifact_allowed_roots(repo_root):
        try:
            candidate.relative_to(allowed_dir)
        except ValueError:
            continue
        return candidate
    return None


def _extract_artifact_title(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(2048)
    except OSError:
        return path.stem.replace("-", " ").replace("_", " ").title()
    match = _ARTIFACT_TITLE_RE.search(head)
    if match is None:
        return path.stem.replace("-", " ").replace("_", " ").title()
    title = " ".join(html.unescape(match.group(1)).split())
    return title or path.stem.replace("-", " ").replace("_", " ").title()


def _extract_markdown_artifact_title(path: Path) -> str:
    fallback = path.stem.replace("-", " ").replace("_", " ").title()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fallback

    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:80]:
            stripped = line.strip()
            if stripped == "---":
                break
            if stripped.startswith("title:"):
                title = stripped.split(":", 1)[1].strip().strip("\"'")
                return title or fallback

    title = _extract_markdown_h1(text)
    return title or fallback


def _extract_artifact_display_title(path: Path) -> str:
    if path.suffix.lower() == ".md":
        return _extract_markdown_artifact_title(path)
    return _extract_artifact_title(path)


def _relative_time(timestamp: float, *, now: float | None = None) -> str:
    delta = max(0, int((time.time() if now is None else now) - timestamp))
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = delta // 60
        return f"{minutes}m ago"
    if delta < 86400:
        hours = delta // 3600
        return f"{hours}h ago"
    days = delta // 86400
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{days // 365}y ago"


def _query_is_true(query: dict[str, list[str]], name: str) -> bool:
    raw = query.get(name, [""])[0].strip().lower()
    return raw in {"1", "true", "yes", "on"}


def build_artifacts_index(repo_root: Path, *, include_deferred: bool = False) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    allowed_suffixes = {".html", ".md"}
    for category, base_rel, patterns in _ARTIFACT_SECTION_SPECS:
        if category in _ARTIFACT_DEFERRED_INDEX_CATEGORIES and not include_deferred:
            continue
        base = repo_root / base_rel
        if not base.is_dir():
            if category in {"Reports", "Migrations", "Handoffs", "References"}:
                grouped[category] = []
            continue
        items: list[dict[str, Any]] = []
        seen: set[Path] = set()
        for pattern in patterns:
            for path in base.glob(pattern):
                if path in seen or not path.is_file() or path.suffix.lower() not in allowed_suffixes:
                    continue
                seen.add(path)
                try:
                    resolved = path.resolve()
                    resolved.relative_to(base.resolve())
                    stat = resolved.stat()
                    rel = resolved.relative_to(repo_root.resolve()).as_posix()
                except (OSError, ValueError):
                    continue
                items.append(
                    {
                        "title": _extract_artifact_display_title(resolved),
                        "path": rel,
                        "url": f"/artifacts/{rel}",
                        "format": resolved.suffix.lower().lstrip("."),
                        "mtime": stat.st_mtime,
                        "size_bytes": stat.st_size,
                        "category": category,
                    }
                )
        if items or category not in {"Briefs", "Bug autopsies", "Dispatch briefs"}:
            grouped[category] = sorted(items, key=lambda item: item["mtime"], reverse=True)
    return grouped


def _get_artifacts_index(
    repo_root: Path,
    query: dict[str, list[str]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    include_deferred = False
    if query is not None:
        include_deferred = _query_is_true(query, "include_research") or (
            query.get("include", [""])[0].strip().lower() == "research"
        )
    cache_key = f"{repo_root.resolve()}::deferred={include_deferred}"
    now = time.monotonic()
    cached = _ARTIFACT_INDEX_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _ARTIFACT_INDEX_CACHE_TTL_SECONDS:
        return cached[1]
    index = build_artifacts_index(repo_root, include_deferred=include_deferred)
    _ARTIFACT_INDEX_CACHE[cache_key] = (now, index)
    return index


def _latest_handoff_url(repo_root: Path) -> str | None:
    session = build_current_session(repo_root)
    latest = session.get("latest")
    if isinstance(latest, dict):
        rel = latest.get("path")
        if isinstance(rel, str) and rel:
            return f"/artifacts/{rel}"
    return None


def _collect_recent_artifacts(
    artifacts: dict[str, list[dict[str, Any]]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    flat = [item for items in artifacts.values() for item in items]
    flat.sort(key=lambda item: float(item.get("mtime", 0)), reverse=True)
    return flat[:limit]


def _strip_markdown_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for idx, line in enumerate(lines[1:120], start=1):
        if line.strip() == "---":
            return "\n".join(lines[idx + 1 :]).lstrip()
    return text


def _markdown_inline(text: str) -> str:
    code_spans: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_spans.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\0CODE{len(code_spans) - 1}\0"

    protected = re.sub(r"`([^`]+)`", stash_code, text)
    rendered = html.escape(protected)

    def link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    rendered = _MARKDOWN_LINK_RE.sub(link, rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", rendered)
    for idx, code in enumerate(code_spans):
        rendered = rendered.replace(f"\0CODE{idx}\0", code)
    return rendered


def _highlight_code_block(code: str, language: str) -> str:
    lang_class = html.escape(language, quote=True)
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, get_lexer_by_name
    except ImportError:
        return f'<pre><code class="language-{lang_class}">{html.escape(code)}</code></pre>'

    try:
        lexer = get_lexer_by_name(language) if language else TextLexer()
    except Exception:
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=True, noclasses=True)
    highlighted = highlight(code, lexer, formatter)
    return f'<pre><code class="language-{lang_class}">{highlighted}</code></pre>'


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _render_markdown_table(lines: list[str], start: int) -> tuple[str, int] | None:
    if start + 1 >= len(lines) or not _MARKDOWN_TABLE_SEPARATOR_RE.match(lines[start + 1]):
        return None
    header = _split_markdown_table_row(lines[start])
    rows: list[list[str]] = []
    idx = start + 2
    while idx < len(lines) and "|" in lines[idx].strip():
        rows.append(_split_markdown_table_row(lines[idx]))
        idx += 1
    header_html = "".join(f"<th>{_markdown_inline(cell)}</th>" for cell in header)
    row_html = []
    for row in rows:
        cells = row + [""] * max(0, len(header) - len(row))
        row_html.append("".join(f"<td>{_markdown_inline(cell)}</td>" for cell in cells[: len(header)]))
    body = "".join(f"<tr>{row}</tr>" for row in row_html)
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body}</tbody></table>", idx


def _render_markdown_fallback(text: str) -> str:
    lines = _strip_markdown_frontmatter(text).splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{_markdown_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_type
        if list_type is not None:
            out.append(f"</{list_type}>")
            list_type = None

    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                out.append(_highlight_code_block("\n".join(code_lines), code_lang))
                code_lines = []
                code_lang = ""
                in_code = False
            else:
                flush_paragraph()
                close_list()
                code_lang = stripped[3:].strip().split(" ", 1)[0]
                in_code = True
            idx += 1
            continue
        if in_code:
            code_lines.append(raw)
            idx += 1
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            idx += 1
            continue
        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            close_list()
            out.append("<hr>")
            idx += 1
            continue
        table = _render_markdown_table(lines, idx)
        if table is not None:
            flush_paragraph()
            close_list()
            table_html, idx = table
            out.append(table_html)
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_markdown_inline(heading.group(2).strip())}</h{level}>")
            idx += 1
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            quote_lines = []
            while idx < len(lines) and lines[idx].strip().startswith(">"):
                quote_lines.append(lines[idx].strip().lstrip(">").strip())
                idx += 1
            out.append(f"<blockquote><p>{_markdown_inline(' '.join(quote_lines))}</p></blockquote>")
            continue
        unordered = re.match(r"^\s*[-*]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            wanted = "ul" if unordered else "ol"
            if list_type != wanted:
                close_list()
                out.append(f"<{wanted}>")
                list_type = wanted
            body = (unordered or ordered).group(1)
            out.append(f"<li>{_markdown_inline(body)}</li>")
            idx += 1
            continue
        close_list()
        paragraph.append(stripped)
        idx += 1

    if in_code:
        out.append(_highlight_code_block("\n".join(code_lines), code_lang))
    flush_paragraph()
    close_list()
    return "\n".join(out)


def _render_markdown_body(text: str) -> str:
    stripped = _strip_markdown_frontmatter(text)
    try:
        import markdown as markdown_lib
    except ImportError:
        return _render_markdown_fallback(text)

    extensions = ["extra", "sane_lists", "toc"]
    extension_configs: dict[str, Any] = {}
    try:
        import pygments  # noqa: F401
    except ImportError:
        pass
    else:
        extensions.append("codehilite")
        extension_configs["codehilite"] = {"guess_lang": False, "noclasses": True}
    return str(markdown_lib.markdown(stripped, extensions=extensions, extension_configs=extension_configs))


def _cached_markdown_body(path: Path) -> str:
    stat = path.stat()
    cache_key = str(path.resolve())
    cached = _ARTIFACT_MARKDOWN_CACHE.get(cache_key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    text = path.read_text(encoding="utf-8", errors="replace")
    rendered = _render_markdown_body(text)
    _ARTIFACT_MARKDOWN_CACHE[cache_key] = (stat.st_mtime_ns, stat.st_size, rendered)
    return rendered


def _render_artifact_breadcrumbs(rel_path: str) -> str:
    parts = rel_path.split("/")
    crumbs = ['<a href="/artifacts">Artifacts</a>']
    for part in parts[:-1]:
        crumbs.append(f"<span>/</span><span>{html.escape(part)}</span>")
    crumbs.append(f"<span>/</span><span>{html.escape(parts[-1])}</span>")
    return "".join(crumbs)


def render_markdown_artifact_html(repo_root: Path, path: Path) -> str:
    rel = path.relative_to(repo_root.resolve()).as_posix()
    title = _extract_markdown_artifact_title(path)
    stat = path.stat()
    generated = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
    body = _cached_markdown_body(path)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - KubeDojo Artifact</title>
  {_design_system_link()}
  <style>
    :root {{
      --bg:#0e1116; --panel:#161b22; --panel-2:#1c232c; --panel-3:#21262d;
      --border:#30363d; --border-soft:#21262d; --fg:#e6edf3; --fg-dim:#8b949e; --fg-faint:#6e7681;
      --green:#3fb950; --green-bg:#0f2c1a; --yellow:#d29922; --yellow-bg:#2d2206;
      --red:#f85149; --red-bg:#2d0e0e; --blue:#58a6ff; --blue-bg:#0f1d2e;
      --purple:#a371f7; --purple-bg:#1f1830; --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
      --text:var(--fg); --text-secondary:var(--fg-dim); --text-dim:var(--fg-faint);
      --surface-0:var(--panel); --surface-1:var(--panel-2); --surface-2:var(--panel-3);
      --accent:var(--blue); --accent-muted:var(--blue-bg); --radius-sm:8px;
    }}
    * {{ box-sizing:border-box; }}
    html,body {{ margin:0; padding:0; background:var(--bg); color:var(--fg); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; line-height:1.58; }}
{_TOP_NAV_CSS}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    code,pre {{ font-family:var(--mono); font-size:0.92em; }}
    .wrap {{ max-width:1100px; margin:0 auto; padding:28px 24px 64px; }}
    .crumbs {{ display:flex; flex-wrap:wrap; gap:7px; color:var(--fg-faint); font-family:var(--mono); font-size:12px; margin-bottom:16px; }}
    .crumbs a {{ color:var(--fg-dim); }}
    .hero {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; border-bottom:1px solid var(--border); padding-bottom:20px; margin-bottom:24px; }}
    h1 {{ margin:0 0 8px; font-size:28px; letter-spacing:0; line-height:1.15; }}
    .sub {{ color:var(--fg-dim); font-size:13px; overflow-wrap:anywhere; }}
    .meta {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; min-width:260px; }}
    .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; letter-spacing:0; border:1px solid; white-space:nowrap; }}
    .pill.neutral {{ color:var(--fg-dim); background:var(--panel-2); border-color:var(--border); }}
    .pill.blue {{ color:var(--blue); background:var(--blue-bg); border-color:rgba(88,166,255,0.4); }}
    article {{ max-width:860px; }}
    article h1,article h2,article h3,article h4 {{ letter-spacing:0; line-height:1.25; }}
    article h1 {{ font-size:26px; margin:28px 0 10px; }}
    article h2 {{ font-size:21px; margin:32px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
    article h3 {{ font-size:17px; margin:24px 0 8px; }}
    article h4 {{ font-size:15px; margin:20px 0 6px; }}
    article p,article li {{ font-size:14px; color:var(--fg); }}
    article ul,article ol {{ padding-left:24px; }}
    article li {{ margin:5px 0; }}
    article blockquote {{ margin:16px 0; padding:10px 16px; border-left:4px solid var(--blue); background:linear-gradient(135deg,var(--blue-bg),var(--panel)); color:var(--fg); border-radius:0 8px 8px 0; }}
    article table {{ width:100%; border-collapse:collapse; margin:16px 0; background:var(--panel); border:1px solid var(--border); border-radius:8px; overflow:hidden; display:block; overflow-x:auto; }}
    article th,article td {{ padding:9px 11px; border-bottom:1px solid var(--border-soft); text-align:left; vertical-align:top; font-size:13px; }}
    article th {{ background:var(--panel-2); color:var(--fg-dim); font-size:11px; text-transform:uppercase; letter-spacing:0; }}
    article tr:last-child td {{ border-bottom:0; }}
    article code {{ background:var(--panel-2); border:1px solid var(--border); border-radius:4px; padding:1px 5px; }}
    article pre {{ background:#070b12; border:1px solid var(--border); border-radius:8px; padding:13px 14px; overflow:auto; }}
    article pre code {{ background:transparent; border:0; padding:0; display:block; }}
    article hr {{ border:0; border-top:1px solid var(--border); margin:24px 0; }}
    .codehilite {{ background:#070b12; border:1px solid var(--border); border-radius:8px; padding:13px 14px; overflow:auto; }}
    @media (max-width:720px) {{
      .wrap {{ padding:20px 14px 44px; }}
      .hero {{ display:block; }}
      .meta {{ justify-content:flex-start; margin-top:12px; min-width:0; }}
      h1 {{ font-size:23px; }}
    }}
  </style>
</head>
<body>
{_render_top_nav("artifacts")}
{_render_page_chrome()}
<main class="wrap">
  <nav class="crumbs" aria-label="Breadcrumbs">{_render_artifact_breadcrumbs(rel)}</nav>
  <header class="hero">
    <div>
      <h1>{html.escape(title)}</h1>
      <div class="sub">{html.escape(rel)}</div>
    </div>
    <div class="meta" aria-label="Artifact metadata">
      <span class="pill blue">Markdown</span>
      <span class="pill neutral">{stat.st_size / 1024:.1f} KB</span>
      <span class="pill neutral">Updated {_relative_time(stat.st_mtime)}</span>
      <span class="pill neutral">Rendered {html.escape(generated)}</span>
    </div>
  </header>
  <article>
    {body}
  </article>
</main>
</body></html>"""


def _artifact_format_counts(artifacts: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    counts = {"html": 0, "md": 0}
    for items in artifacts.values():
        for item in items:
            fmt = str(item.get("format", ""))
            if fmt in counts:
                counts[fmt] += 1
    return counts


def _artifact_category_anchor(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")


def render_html_artifact_shell(repo_root: Path, rel_path: str, raw_bytes: bytes) -> str:
    candidate = _resolve_artifact_path(repo_root, rel_path)
    title = _extract_artifact_display_title(candidate) if candidate is not None else Path(rel_path).stem
    safe_rel = html.escape(rel_path)
    raw_href = html.escape(f"/artifacts/{rel_path}?raw=1", quote=True)
    iframe_src = raw_href
    breadcrumbs = _render_artifact_breadcrumbs(rel_path)
    benchmarks_action = ""
    if rel_path.startswith("calibration/v1/reports/"):
        benchmarks_action = '<a class="shell-action" href="/benchmarks">Benchmarks</a>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - KubeDojo Artifact</title>
  {_design_system_link()}
  <style>
    :root {{ --bg:#0e1116; --panel:#161b22; --border:#30363d; --fg:#e6edf3; --fg-dim:#8b949e; --blue:#58a6ff; --mono:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--fg); }}
{_TOP_NAV_CSS}
    .wrap {{ max-width:1200px; margin:0 auto; padding:20px 24px 32px; }}
    .crumbs {{ display:flex; flex-wrap:wrap; gap:7px; color:var(--fg-dim); font-family:var(--mono); font-size:12px; margin-bottom:12px; }}
    .shell-toolbar {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:12px; }}
    .shell-action {{ display:inline-flex; align-items:center; padding:6px 10px; border:1px solid var(--border); border-radius:8px; color:var(--fg); font-size:12px; font-weight:700; text-decoration:none; background:var(--panel); }}
    .shell-action:hover {{ border-color:var(--blue); color:var(--blue); text-decoration:none; }}
    .artifact-shell {{ border:1px solid var(--border); border-radius:10px; overflow:hidden; background:#070b12; min-height:70vh; }}
    .artifact-frame {{ display:block; width:100%; min-height:70vh; border:0; background:#fff; }}
  </style>
</head>
<body>
{_render_top_nav("artifacts")}
{_render_page_chrome()}
<main class="wrap">
  <nav class="crumbs" aria-label="Breadcrumbs">{breadcrumbs}</nav>
  <div class="shell-toolbar">
    <a class="shell-action" href="{raw_href}">Open raw (?raw=1)</a>
    {benchmarks_action}
    <span class="shell-action" aria-hidden="true">{safe_rel}</span>
  </div>
  <section class="artifact-shell">
    <iframe class="artifact-frame" title="{html.escape(title)}" src="{iframe_src}"></iframe>
  </section>
</main>
</body></html>"""


def render_artifacts_index_html(
    repo_root: Path,
    query: dict[str, list[str]] | None = None,
) -> str:
    artifacts = _get_artifacts_index(repo_root, query)
    generated = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
    total = sum(len(items) for items in artifacts.values())
    format_counts = _artifact_format_counts(artifacts)
    recent = _collect_recent_artifacts(artifacts)
    handoff_url = _latest_handoff_url(repo_root)
    include_research = query is not None and (
        _query_is_true(query, "include_research") or query.get("include", [""])[0].strip().lower() == "research"
    )
    research_query = "?include=research" if not include_research else ""

    recent_rows = []
    for item in recent:
        recent_rows.append(
            f"""<tr data-artifact-row data-title="{html.escape(str(item['title']).lower(), quote=True)}" data-path="{html.escape(str(item['path']).lower(), quote=True)}" data-format="{html.escape(str(item.get('format', 'html')), quote=True)}" data-category="{html.escape(str(item.get('category', '')).lower(), quote=True)}" data-mtime="{float(item['mtime'])}">
      <td><a href="{html.escape(str(item['url']), quote=True)}">{html.escape(str(item['title']))}</a></td>
      <td class="mono path">{html.escape(str(item['path']))}</td>
      <td><span class="pill {'blue' if item.get('format') == 'md' else 'green'}">{html.escape(str(item.get('format', 'html')).upper())}</span></td>
      <td><span class="pill neutral">{html.escape(_relative_time(float(item['mtime'])))}</span></td>
    </tr>"""
        )
    recent_body = (
        "\n".join(recent_rows)
        if recent_rows
        else '<tr><td colspan="4" class="empty">No artifacts found.</td></tr>'
    )

    category_pills = ['<a class="pill-pill active" href="#" data-category="">All</a>']
    for category in artifacts:
        anchor = _artifact_category_anchor(category)
        category_pills.append(
            f'<a class="pill-pill" href="#{html.escape(anchor, quote=True)}" data-category="{html.escape(category.lower(), quote=True)}">{html.escape(category)}</a>'
        )

    section_html = []
    for category, items in artifacts.items():
        if not items and category in {"Briefs", "Bug autopsies", "Dispatch briefs"}:
            continue
        rows = []
        for item in items:
            title = html.escape(str(item["title"]))
            rel_path = html.escape(str(item["path"]))
            url = html.escape(str(item["url"]))
            fmt = html.escape(str(item.get("format", "html")).upper())
            fmt_class = "blue" if item.get("format") == "md" else "green"
            age = html.escape(_relative_time(float(item["mtime"])))
            size_kb = f"{item['size_bytes'] / 1024:.1f} KB"
            rows.append(
                f"""<tr data-artifact-row data-title="{title.lower()}" data-path="{rel_path.lower()}" data-format="{html.escape(str(item.get('format', 'html')), quote=True)}" data-category="{html.escape(category.lower(), quote=True)}" data-mtime="{float(item['mtime'])}">
      <td><a href="{url}">{title}</a></td>
      <td class="mono path">{rel_path}</td>
      <td><span class="pill {fmt_class}">{fmt}</span></td>
      <td><span class="pill neutral">{age}</span></td>
      <td class="num">{size_kb}</td>
    </tr>"""
            )
        body = "\n".join(rows) if rows else '<tr><td colspan="5" class="empty">No artifacts found.</td></tr>'
        anchor = _artifact_category_anchor(category)
        section_html.append(
            f"""<section class="panel artifact-section" id="{html.escape(anchor)}" data-category="{html.escape(category.lower(), quote=True)}">
  <details open>
  <summary class="panel-head">
    <h2>{html.escape(category)}</h2>
    <span class="pill neutral">{len(items)}</span>
  </summary>
  <div class="table-wrap">
    <table class="matrix">
      <thead><tr><th>Title</th><th>Path</th><th>Type</th><th>Modified</th><th>Size</th></tr></thead>
      <tbody>
    {body}
      </tbody>
    </table>
  </div>
  </details>
</section>"""
        )

    handoff_cta = ""
    if handoff_url:
        handoff_cta = (
            f'<a class="handoff-cta" href="{html.escape(handoff_url, quote=True)}">Latest handoff &rarr;</a>'
        )
    research_note = ""
    if not include_research:
        research_note = (
            f'<p class="research-note">Research artifacts are hidden by default. '
            f'<a href="/artifacts{research_query}">Include research</a>.</p>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Artifacts - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
    :root {{
      --bg:#0e1116; --panel:#161b22; --panel-2:#1c232c; --panel-3:#21262d;
      --border:#30363d; --border-soft:#21262d; --fg:#e6edf3; --fg-dim:#8b949e; --fg-faint:#6e7681;
      --green:#3fb950; --green-bg:#0f2c1a; --blue:#58a6ff; --blue-bg:#0f1d2e;
      --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
      --text:var(--fg); --text-secondary:var(--fg-dim); --text-dim:var(--fg-faint);
      --surface-0:var(--panel); --surface-1:var(--panel-2); --surface-2:var(--panel-3);
      --accent:var(--blue); --accent-muted:var(--blue-bg); --radius-sm:8px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif;
      background:var(--bg); color:var(--text); line-height:1.5; -webkit-font-smoothing:antialiased;
    }}
{_TOP_NAV_CSS}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .wrap {{ max-width:1200px; margin:0 auto; padding:32px 24px 64px; }}
    .page-head {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-end; margin-bottom:18px; }}
    h1 {{ margin:0; font-size:30px; letter-spacing:0; }}
    .page-sub {{ margin-top:4px; color:var(--fg-dim); font-size:14px; max-width:780px; }}
    .handoff-cta {{ display:inline-flex; align-items:center; padding:8px 12px; border-radius:8px; border:1px solid rgba(88,166,255,0.45); background:var(--blue-bg); color:var(--blue); font-size:13px; font-weight:700; text-decoration:none; }}
    .research-note {{ color:var(--fg-dim); font-size:13px; margin:0 0 12px; }}
    .artifact-tools {{ display:grid; grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(120px,0.5fr)); gap:10px; margin:16px 0; }}
    .artifact-tools input,.artifact-tools select {{ width:100%; height:36px; border:1px solid var(--border); border-radius:8px; background:var(--panel-2); color:var(--fg); padding:0 10px; font-size:13px; }}
    .category-pills {{ display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 18px; }}
    .pill-pill {{ display:inline-flex; padding:5px 10px; border-radius:999px; border:1px solid var(--border); color:var(--fg-dim); font-size:12px; font-weight:700; text-decoration:none; }}
    .pill-pill.active,.pill-pill:hover {{ color:var(--blue); border-color:rgba(88,166,255,0.45); background:var(--blue-bg); text-decoration:none; }}
    .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin:18px 0; }}
    .kpi {{ border:1px solid var(--border); border-radius:8px; background:var(--panel); padding:14px 16px; }}
    .kpi .value {{ display:block; font-size:26px; font-weight:600; line-height:1; color:var(--blue); }}
    .kpi .label {{ display:block; margin-top:6px; color:var(--fg-dim); font-size:11px; font-weight:600; letter-spacing:0; text-transform:uppercase; }}
    .panel {{ border:1px solid var(--border); border-radius:8px; background:var(--panel); margin-top:14px; overflow:hidden; }}
    details {{ display:block; }}
    summary {{ cursor:pointer; list-style:none; }}
    summary::-webkit-details-marker {{ display:none; }}
    .panel-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding:14px 18px; border-bottom:1px solid var(--border); }}
    .panel-head::before {{ content:"v"; color:var(--fg-faint); font-size:12px; }}
    details:not([open]) .panel-head {{ border-bottom:0; }}
    details:not([open]) .panel-head::before {{ content:">"; }}
    .panel-head h2 {{ flex:1; margin:0; font-size:16px; letter-spacing:0; }}
    .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; letter-spacing:0; border:1px solid; white-space:nowrap; }}
    .pill.neutral {{ color:var(--fg-dim); background:var(--panel-2); border-color:var(--border); }}
    .pill.green {{ color:var(--green); background:var(--green-bg); border-color:rgba(63,185,80,0.4); }}
    .pill.blue {{ color:var(--blue); background:var(--blue-bg); border-color:rgba(88,166,255,0.4); }}
    .table-wrap {{ overflow-x:auto; }}
    table.matrix {{ width:100%; border-collapse:collapse; }}
    table.matrix th,table.matrix td {{ padding:10px 12px; border-bottom:1px solid var(--border-soft); text-align:left; vertical-align:top; font-size:13px; }}
    table.matrix th {{ color:var(--fg-dim); font-size:11px; font-weight:500; text-transform:uppercase; letter-spacing:0; background:var(--panel-2); }}
    table.matrix tr:last-child td {{ border-bottom:0; }}
    .mono {{ font-family:var(--mono); }}
    .path {{ color:var(--fg-dim); min-width:320px; overflow-wrap:anywhere; }}
    .num {{ text-align:right; white-space:nowrap; }}
    .empty {{ color:var(--text-dim); text-align:center; padding:22px; }}
    .artifact-section.hidden {{ display:none; }}
    tr[data-artifact-row].hidden {{ display:none; }}
    @media (max-width: 720px) {{
      .wrap {{ padding:20px 14px 40px; }}
      .page-head {{ display:block; }}
      .artifact-tools {{ grid-template-columns:1fr; }}
      th,td {{ padding:9px 10px; }}
      .num {{ text-align:left; }}
    }}
  </style>
</head>
<body>
{_render_top_nav("artifacts")}
{_render_page_chrome()}
<main class="wrap">
  <header class="page-head">
    <div>
      <h1>Artifacts</h1>
      <div class="page-sub">Unified browser for HTML and Markdown orchestrator artifacts served through the local API.</div>
    </div>
    <div>{handoff_cta}<span class="pill neutral">Generated {html.escape(generated)}</span></div>
  </header>
  {research_note}
  <section class="artifact-tools" aria-label="Artifact filters">
    <input id="artifact-search" type="search" placeholder="Filter artifacts by title or path" autocomplete="off">
    <select id="artifact-format-filter" aria-label="Format filter">
      <option value="">All formats</option>
      <option value="html">HTML</option>
      <option value="md">Markdown</option>
    </select>
    <select id="artifact-sort" aria-label="Sort order">
      <option value="mtime-desc">Newest first</option>
      <option value="mtime-asc">Oldest first</option>
      <option value="title-asc">Title A-Z</option>
    </select>
    <select id="artifact-category-filter" aria-label="Category filter">
      <option value="">All categories</option>
      {"".join(f'<option value="{html.escape(category.lower(), quote=True)}">{html.escape(category)}</option>' for category in artifacts)}
    </select>
  </section>
  <div class="category-pills">{"".join(category_pills)}</div>
  <section class="kpis" aria-label="Artifact summary">
    <div class="kpi"><span class="value">{total}</span><span class="label">Total artifacts</span></div>
    <div class="kpi"><span class="value">{format_counts["html"]}</span><span class="label">HTML files</span></div>
    <div class="kpi"><span class="value">{format_counts["md"]}</span><span class="label">Markdown files</span></div>
    <div class="kpi"><span class="value">{len(artifacts)}</span><span class="label">Sections</span></div>
  </section>
  <section class="panel" id="recent-artifacts">
    <div class="panel-head"><h2>Recently updated</h2><span class="pill neutral">{len(recent)}</span></div>
    <div class="table-wrap">
      <table class="matrix" id="recent-artifacts-table">
        <thead><tr><th>Title</th><th>Path</th><th>Type</th><th>Modified</th></tr></thead>
        <tbody>{recent_body}</tbody>
      </table>
    </div>
  </section>
  {"".join(section_html)}
</main>
<script>
(() => {{
  const search = document.getElementById("artifact-search");
  const formatFilter = document.getElementById("artifact-format-filter");
  const sortSelect = document.getElementById("artifact-sort");
  const categoryFilter = document.getElementById("artifact-category-filter");
  const rows = () => Array.from(document.querySelectorAll("[data-artifact-row]"));
  const sections = () => Array.from(document.querySelectorAll(".artifact-section"));
  function applyFilters() {{
    const q = (search?.value || "").trim().toLowerCase();
    const fmt = formatFilter?.value || "";
    const category = categoryFilter?.value || "";
    rows().forEach((row) => {{
      const title = row.dataset.title || "";
      const path = row.dataset.path || "";
      const rowFmt = row.dataset.format || "";
      const rowCategory = row.dataset.category || "";
      const visible = (!q || title.includes(q) || path.includes(q))
        && (!fmt || rowFmt === fmt)
        && (!category || rowCategory === category);
      row.classList.toggle("hidden", !visible);
    }});
    sections().forEach((section) => {{
      const sectionCategory = section.dataset.category || "";
      const hasVisible = Array.from(section.querySelectorAll("[data-artifact-row]:not(.hidden)")).length > 0;
      section.classList.toggle("hidden", category && sectionCategory !== category ? true : !hasVisible);
    }});
    document.querySelectorAll(".pill-pill").forEach((pill) => {{
      pill.classList.toggle("active", (pill.dataset.category || "") === category);
    }});
  }}
  function applySort() {{
    const mode = sortSelect?.value || "mtime-desc";
    document.querySelectorAll("table.matrix tbody").forEach((tbody) => {{
      const sorted = rows().filter((row) => tbody.contains(row)).sort((a, b) => {{
        if (mode === "title-asc") return (a.dataset.title || "").localeCompare(b.dataset.title || "");
        const am = Number(a.dataset.mtime || 0);
        const bm = Number(b.dataset.mtime || 0);
        return mode === "mtime-asc" ? am - bm : bm - am;
      }});
      sorted.forEach((row) => tbody.appendChild(row));
    }});
  }}
  search?.addEventListener("input", applyFilters);
  formatFilter?.addEventListener("change", applyFilters);
  categoryFilter?.addEventListener("change", applyFilters);
  sortSelect?.addEventListener("change", () => {{ applySort(); applyFilters(); }});
  document.querySelectorAll(".pill-pill").forEach((pill) => {{
    pill.addEventListener("click", (event) => {{
      event.preventDefault();
      if (categoryFilter) categoryFilter.value = pill.dataset.category || "";
      applyFilters();
    }});
  }});
  applySort();
  applyFilters();
}})();
</script>
</body></html>"""


def _truncate_text(text: str, *, limit: int = 600) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _html_fragment_to_text(fragment: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", fragment)
    return html.unescape(re.sub(r"\s+", " ", no_tags)).strip()


def _strip_html_noncontent(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    # End-tag patterns use `</script\b[^>]*>` (not `</script\s*>`): browsers
    # accept end tags with trailing junk like `</script\t\n bar>`, so the strict
    # form would leave script/style content un-stripped (CodeQL py/bad-tag-filter,
    # alert #31). `\b` keeps `</scriptx>` from matching a different tag name.
    text = re.sub(r"<script\b[^>]*>.*?</script\b[^>]*>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"<style\b[^>]*>.*?</style\b[^>]*>", " ", text, flags=re.IGNORECASE | re.DOTALL)


def _extract_html_h1(text: str) -> str | None:
    text = _strip_html_noncontent(text)
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = _html_fragment_to_text(match.group(1))
    return title or None


def _extract_markdown_h1(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            return title or None
    return None


def _extract_html_tldr(text: str) -> str | None:
    text = _strip_html_noncontent(text)
    tldr_section = re.search(
        r"<(?:h2|h3|p)\b[^>]*>\s*(?:TL;DR|TLDR)\s*</(?:h2|h3|p)>\s*<p\b[^>]*>(.*?)</p>",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if tldr_section:
        tldr = _html_fragment_to_text(tldr_section.group(1))
        if tldr:
            return _truncate_text(tldr)
    paragraph = re.search(r"<p\b[^>]*>(.*?)</p>", text, re.IGNORECASE | re.DOTALL)
    if paragraph:
        tldr = _html_fragment_to_text(paragraph.group(1))
        if tldr:
            return _truncate_text(tldr)
    return None


def _extract_markdown_tldr(text: str) -> str | None:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^#{1,3}\s*(?:TL;DR|TLDR)\b", stripped, re.IGNORECASE):
            body: list[str] = []
            for candidate in lines[idx + 1 :]:
                candidate = candidate.strip()
                if not candidate:
                    if body:
                        break
                    continue
                if candidate.startswith("#"):
                    break
                body.append(candidate)
            if body:
                return _truncate_text(" ".join(body))
        if re.match(r"^(?:\*\*)?TL;DR(?:\*\*)?\s*[:-]\s*", stripped, re.IGNORECASE):
            tldr = re.sub(r"^(?:\*\*)?TL;DR(?:\*\*)?\s*[:-]\s*", "", stripped, flags=re.IGNORECASE)
            if tldr:
                return _truncate_text(tldr)

    paragraph: list[str] = []
    in_frontmatter = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---" and not paragraph:
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not stripped or stripped.startswith("#") or stripped.startswith("|"):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    if paragraph:
        return _truncate_text(" ".join(paragraph))
    return None


def _handoff_metadata(repo_root: Path, path: Path, *, include_detail: bool) -> dict[str, Any] | None:
    match = _HANDOFF_FILENAME_RE.match(path.name)
    if not match or path.name.startswith("archive-pre-"):
        return None
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        return None
    metadata: dict[str, Any] = {
        "filename": path.name,
        "path": rel,
        "date": match.group("date"),
        "session_label": match.group("label"),
        "format": match.group("format"),
    }
    if not include_detail:
        return metadata

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    is_html = metadata["format"] == "html"
    title = _extract_html_h1(text) if is_html else _extract_markdown_h1(text)
    tldr = _extract_html_tldr(text) if is_html else _extract_markdown_tldr(text)
    raw_url = (
        f"/artifacts/{rel}"
        if rel.startswith(("docs/session-state/", ".agent/session-state/"))
        else None
    )
    metadata.update(
        {
            "render_url": f"http://127.0.0.1:8910/{rel}",
            "raw_url": raw_url,
            "title": title,
            "tldr": tldr,
        }
    )
    return metadata


def build_current_session(repo_root: Path) -> dict[str, Any]:
    # Live handoffs are LOCAL agent state in the gitignored ``.agent/session-state/``
    # (s196, user 2026-07-07 — learn-ukrainian parity #3768/#4704: handoffs never go
    # through git/PRs); ``docs/session-state/`` holds the tracked pre-s196 history.
    # Scan BOTH; date-prefixed filenames sort chronologically across dirs.
    handoff_dirs = (
        repo_root / ".agent" / "session-state",
        repo_root / "docs" / "session-state",
    )
    entries: list[tuple[dict[str, Any], Path]] = []
    for handoff_dir in handoff_dirs:
        if not handoff_dir.is_dir():
            continue
        for path in handoff_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".md", ".html"}:
                continue
            metadata = _handoff_metadata(repo_root, path, include_detail=False)
            if metadata is not None:
                entries.append((metadata, path))

    entries.sort(key=lambda item: item[0]["filename"], reverse=True)
    latest = None
    predecessors: list[dict[str, Any]] = []
    if entries:
        latest = _handoff_metadata(repo_root, entries[0][1], include_detail=True)
        predecessors = [meta for meta, _ in entries[1:11]]

    return {
        "latest": latest,
        "predecessors": predecessors,
        "total_handoffs": len(entries),
    }


def _benchmark_report_dirs(repo_root: Path) -> list[Path]:
    reports_dir = repo_root / _BENCHMARK_REPORTS_REL
    if not reports_dir.is_dir():
        return []
    dirs = [
        path
        for path in reports_dir.iterdir()
        if path.is_dir() and _BENCHMARK_REPORT_DIR_RE.fullmatch(path.name)
    ]
    return sorted(dirs, key=lambda path: path.name, reverse=True)


def _benchmark_report_summary(repo_root: Path, report_dir: Path) -> dict[str, str]:
    rel_dir = report_dir.relative_to(repo_root).as_posix()
    return {
        "date": report_dir.name,
        "directory": rel_dir,
        "render_url": f"http://127.0.0.1:8768/artifacts/{rel_dir}/index.html",
    }


def _benchmark_artifact_url(repo_root: Path, path: Path) -> str:
    return f"/artifacts/{path.relative_to(repo_root).as_posix()}"


def _benchmark_file_url_if_present(repo_root: Path, report_dir: Path, filename: str) -> str | None:
    path = report_dir / filename
    if not path.is_file():
        return None
    return _benchmark_artifact_url(repo_root, path)


def _benchmark_html_file_urls(repo_root: Path, directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return [
        _benchmark_artifact_url(repo_root, path)
        for path in sorted(directory.glob("*.html"), key=lambda item: item.name)
        if path.is_file()
    ]


def _build_benchmark_files(repo_root: Path, report_dir: Path) -> dict[str, Any]:
    return {
        "index": _benchmark_file_url_if_present(repo_root, report_dir, "index.html"),
        "matrix": _benchmark_file_url_if_present(repo_root, report_dir, "matrix.html"),
        "wave_ab": _benchmark_file_url_if_present(repo_root, report_dir, "wave-ab-report.html"),
        "stability": _benchmark_file_url_if_present(repo_root, report_dir, "stability.html"),
        "per_lane": _benchmark_html_file_urls(repo_root, report_dir / "per-lane"),
        "per_model": _benchmark_html_file_urls(repo_root, report_dir / "per-model"),
    }


def _build_benchmark_ledger(repo_root: Path) -> dict[str, Any]:
    ledger = {
        "path": _BENCHMARK_LEDGER_REL,
        "cells_total": 0,
        "cells_scored": 0,
        "models": 0,
        "lanes": 0,
    }
    db_path = repo_root / _BENCHMARK_LEDGER_REL
    if not db_path.is_file():
        return ledger

    queries = {
        "cells_total": "SELECT COUNT(*) FROM cells",
        "cells_scored": "SELECT COUNT(DISTINCT cell_id) FROM scores",
        "models": "SELECT COUNT(DISTINCT model_id) FROM cells",
        "lanes": "SELECT COUNT(DISTINCT lane) FROM cells",
    }
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except (OSError, sqlite3.Error):
        return ledger
    try:
        for key, sql in queries.items():
            row = conn.execute(sql).fetchone()
            ledger[key] = int(row[0] or 0) if row else 0
    except sqlite3.Error:
        return {
            "path": _BENCHMARK_LEDGER_REL,
            "cells_total": 0,
            "cells_scored": 0,
            "models": 0,
            "lanes": 0,
        }
    finally:
        conn.close()
    return ledger


def _latest_benchmark_staleness_seconds(repo_root: Path, report_dir: Path) -> float | None:
    index_path = report_dir / "index.html"
    db_path = repo_root / _BENCHMARK_LEDGER_REL
    if not index_path.is_file() or not db_path.is_file():
        return None

    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except (OSError, sqlite3.Error):
        return None
    try:
        row = conn.execute("SELECT MAX(scored_at) FROM scores").fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    if row is None or row[0] is None:
        return None

    try:
        scored_at = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if scored_at.tzinfo is None:
        scored_at = scored_at.replace(tzinfo=UTC)
    try:
        rendered_at = index_path.stat().st_mtime
    except OSError:
        return None
    return float(scored_at.timestamp() - rendered_at)


def build_latest_benchmarks(repo_root: Path) -> dict[str, Any]:
    report_dirs = _benchmark_report_dirs(repo_root)
    if not report_dirs:
        return {"latest": None, "predecessors": [], "total_runs": 0}

    latest_dir = report_dirs[0]
    latest: dict[str, Any] = _benchmark_report_summary(repo_root, latest_dir)
    latest["files"] = _build_benchmark_files(repo_root, latest_dir)
    latest["ledger"] = _build_benchmark_ledger(repo_root)
    latest["staleness_seconds"] = _latest_benchmark_staleness_seconds(repo_root, latest_dir)

    return {
        "latest": latest,
        "predecessors": [_benchmark_report_summary(repo_root, path) for path in report_dirs[1:11]],
        "total_runs": len(report_dirs),
    }


def _benchmark_report_tile(label: str, href: str | None, subtitle: str = "") -> str:
    safe_label = html.escape(label)
    safe_subtitle = html.escape(subtitle) if subtitle else ""
    subtitle_html = f'<span class="bench-tile-sub">{safe_subtitle}</span>' if safe_subtitle else ""
    if not href:
        return (
            '<span class="bench-tile disabled">'
            f'<span class="bench-tile-title">{safe_label}</span>'
            '<span class="bench-tile-sub">not generated</span></span>'
        )
    safe_href = html.escape(href, quote=True)
    return (
        f'<a class="bench-tile" href="{safe_href}">'
        f'<span class="bench-tile-title">{safe_label}</span>{subtitle_html}</a>'
    )


def _benchmark_label_from_url(url: str) -> str:
    stem = Path(urlsplit(url).path).stem
    return stem or url


def _benchmark_index_href(run: dict[str, Any]) -> str | None:
    directory = run.get("directory")
    if not isinstance(directory, str) or not directory:
        return None
    return f"/artifacts/{directory}/index.html"


def _render_benchmarks_page(repo_root: Path) -> str:
    payload = build_latest_benchmarks(repo_root)
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else None
    if latest is None:
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmarks - KubeDojo Local Monitor</title>
  <link rel="stylesheet" href="/static/design-system.css" />
</head>
<body>
{_render_top_nav("benchmarks")}
{_render_page_chrome()}
<main class="wrap">
  <header class="hero">
    <div><h1>Benchmarks</h1><div class="sub">Calibration report dashboard.</div></div>
  </header>
  <section class="kpi"><div class="label">Latest run</div><div class="value">No runs</div><div class="sub">No calibration reports found.</div></section>
</main>
</body></html>"""

    files = latest.get("files") if isinstance(latest.get("files"), dict) else {}
    ledger = latest.get("ledger") if isinstance(latest.get("ledger"), dict) else {}
    date = str(latest.get("date") or "unknown")
    cells_scored = ledger.get("cells_scored", 0)
    cells_total = ledger.get("cells_total", 0)
    models = ledger.get("models", 0)
    lanes = ledger.get("lanes", 0)
    summary = f"{cells_scored}/{cells_total} cells scored × {models} models × {lanes} lanes ({date})"
    top_tiles = "\n".join(
        [
            _benchmark_report_tile("Index", files.get("index"), "run overview"),
            _benchmark_report_tile("Matrix", files.get("matrix"), "lane × model grid"),
            _benchmark_report_tile("Wave AB", files.get("wave_ab"), "paired comparison"),
            _benchmark_report_tile("Stability", files.get("stability"), "replicate variance"),
        ]
    )
    lane_tiles = "\n".join(
        _benchmark_report_tile(_benchmark_label_from_url(url), url)
        for url in files.get("per_lane", []) or []
        if isinstance(url, str)
    )
    model_tiles = "\n".join(
        _benchmark_report_tile(_benchmark_label_from_url(url), url)
        for url in files.get("per_model", []) or []
        if isinstance(url, str)
    )
    predecessors = payload.get("predecessors") if isinstance(payload.get("predecessors"), list) else []
    history_rows = "\n".join(
        f'<li><a href="{html.escape(href, quote=True)}">{html.escape(str(run.get("date") or "unknown"))}</a></li>'
        for run in predecessors
        if isinstance(run, dict) and (href := _benchmark_index_href(run))
    )
    history_html = f'<ul class="bench-history">{history_rows}</ul>' if history_rows else '<p class="empty-state">No prior runs</p>'
    stability_candidates_html = ""
    if files.get("stability"):
        stability_candidates_html = (
            ' The raw stability selector output is available as '
            '<a href="/artifacts/calibration/v1/reports/stability-candidates.json">'
            "stability-candidates.json</a>."
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmarks - KubeDojo Local Monitor</title>
  <link rel="stylesheet" href="/static/design-system.css" />
  <style>
    .bench-head {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-end; background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); padding:20px 22px; margin-bottom:20px; }}
    .bench-head h1 {{ margin:0 0 4px; font-size:26px; letter-spacing:0; }}
    .bench-summary {{ color:var(--accent); font-size:15px; font-weight:800; text-align:right; }}
    .bench-run-date {{ color:var(--fg-dim); font-size:12px; text-align:right; margin-top:4px; }}
    .bench-kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:22px; }}
    .bench-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:12px 0 22px; }}
    .bench-grid.compact {{ grid-template-columns:repeat(auto-fit,minmax(138px,1fr)); }}
    .bench-tile {{ min-height:68px; display:flex; flex-direction:column; justify-content:center; gap:4px; padding:13px 14px; background:var(--surface-0); border:1px solid var(--border); border-radius:8px; color:var(--text); text-decoration:none; }}
    .bench-tile:hover {{ background:var(--surface-1); text-decoration:none; }}
    .bench-tile.disabled {{ color:var(--fg-dim); opacity:.72; }}
    .bench-tile-title {{ font-weight:800; overflow-wrap:anywhere; }}
    .bench-tile-sub {{ color:var(--fg-dim); font-size:12px; }}
    .bench-section h2 {{ margin-top:24px; }}
    .bench-history {{ list-style:none; margin:10px 0 24px; padding:0; display:flex; gap:8px; flex-wrap:wrap; }}
    .bench-history a {{ display:inline-flex; padding:6px 10px; border:1px solid var(--border); border-radius:999px; background:var(--surface-0); font-size:13px; }}
    .bench-methodology {{ margin-top:30px; padding-top:18px; border-top:1px solid var(--border); color:var(--fg-dim); font-size:13px; }}
    @media (max-width:720px) {{ .bench-head {{ align-items:flex-start; flex-direction:column; }} .bench-summary,.bench-run-date {{ text-align:left; }} .bench-kpis {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
  </style>
</head>
<body>
{_render_top_nav("benchmarks")}
{_render_page_chrome()}
<main class="wrap">
  <section class="bench-head">
    <div>
      <h1>Benchmarks</h1>
      <div class="sub">Curated calibration report dashboard for the latest model-and-lane run.</div>
    </div>
    <div>
      <div class="bench-summary">{html.escape(summary)}</div>
      <div class="bench-run-date">Run date {html.escape(date)}</div>
    </div>
  </section>

  <div class="bench-kpis">
    <div class="kpi"><div class="label">Cells scored</div><div class="value">{html.escape(str(cells_scored))}</div><div class="sub">of {html.escape(str(cells_total))} cells</div></div>
    <div class="kpi"><div class="label">Models</div><div class="value">{html.escape(str(models))}</div><div class="sub">per run</div></div>
    <div class="kpi"><div class="label">Lanes</div><div class="value">{html.escape(str(lanes))}</div><div class="sub">evaluation lanes</div></div>
    <div class="kpi"><div class="label">Latest run</div><div class="value">{html.escape(date)}</div><div class="sub">{html.escape(str(payload.get("total_runs", 0)))} total runs</div></div>
  </div>

  <section class="bench-section">
    <h2>Top Reports</h2>
    <div class="bench-grid">{top_tiles}</div>
  </section>

  <section class="bench-section">
    <h2>Per-Lane Reports</h2>
    <div class="bench-grid compact">{lane_tiles or '<p class="empty-state">No per-lane reports</p>'}</div>
  </section>

  <section class="bench-section">
    <h2>Per-Model Reports</h2>
    <div class="bench-grid compact">{model_tiles or '<p class="empty-state">No per-model reports</p>'}</div>
  </section>

  <section class="bench-section">
    <h2>History</h2>
    {history_html}
  </section>

  <footer class="bench-methodology">
    The calibration dashboard tracks a {html.escape(str(lanes))}-lane × {html.escape(str(models))}-model × ~2-scorer shape, with each run publishing the aggregate index, matrix, wave-ab comparison, stability report, per-lane slices, and per-model slices.{stability_candidates_html}
  </footer>
</main>
</body></html>"""


def build_state_manifest() -> dict[str, Any]:
    """Pointer-only index for canonical cold-start state discovery."""
    return {
        "version": 1,
        "categories": [
            {
                "category": "cold_start",
                "entries": [
                    {
                        "name": "Session briefing",
                        "path": "/api/briefing/session",
                        "purpose": "Full agent orientation snapshot with current actions, blockers, and repo state.",
                        "type": "api",
                    },
                    {
                        "name": "Compact session briefing",
                        "path": "/api/briefing/session?compact=1",
                        "purpose": "Token-light briefing for first contact on a fresh agent session.",
                        "type": "api",
                    },
                    {
                        "name": "Current session handoff",
                        "path": "/api/session/current",
                        "purpose": "Most recent session handoff plus predecessor chain.",
                        "type": "api",
                    },
                    {
                        "name": "API schema",
                        "path": "/api/schema",
                        "purpose": "Machine-readable index of local API routes and query conventions.",
                        "type": "api",
                    },
                    {
                        "name": "Orientation punch-line",
                        "path": "/api/orient",
                        "purpose": "Single primary action + up to 3 alternatives + blockers/alerts. Maximum signal-to-token.",
                        "type": "api",
                    },
                ],
            },
            {
                "category": "dashboards",
                "entries": [
                    {"name": "Operator dashboard", "path": "/", "purpose": "Top-level local monitor summary.", "type": "html"},
                    {"name": "Quality board", "path": "/quality", "purpose": "Per-module quality status dashboard.", "type": "html"},
                    {"name": "Pipeline board", "path": "/pipeline", "purpose": "Pipeline v2 queue and event dashboard.", "type": "html"},
                    {"name": "Activity feed", "path": "/activity", "purpose": "Recent commits, pipeline events, and bridge messages.", "type": "html"},
                    {"name": "Health dashboard", "path": "/health", "purpose": "Runtime services, worktrees, and delivery health.", "type": "html"},
                    {"name": "Artifacts browser", "path": "/artifacts", "purpose": "Browse HTML and Markdown orchestrator artifacts.", "type": "html_artifact"},
                    {"name": "Decisions board", "path": "/decisions", "purpose": "Decision cards with lineage and pending status.", "type": "html"},
                    {"name": "Channels browser", "path": "/channels", "purpose": "Bridge conversations and deliberation threads.", "type": "html"},
                    {"name": "Benchmarks dashboard", "path": "/benchmarks", "purpose": "Latest calibration run and predecessor history.", "type": "html"},
                ],
            },
            {
                "category": "collaboration",
                "entries": [
                    {"name": "Channels", "path": "/channels", "purpose": "Bridge conversations and live deliberation threads.", "type": "html"},
                    {"name": "Decisions", "path": "/decisions", "purpose": "Decision cards, pending queue, and lineage.", "type": "html"},
                    {"name": "Pending decisions API", "path": "/api/decisions/pending", "purpose": "Pending and stale decision files for notifications.", "type": "api"},
                ],
            },
            {
                "category": "git_and_build",
                "entries": [
                    {"name": "Git worktrees", "path": "/api/git/worktrees", "purpose": "Attached worktrees and cleanup candidates.", "type": "api"},
                    {"name": "Build job status", "path": "/api/build/status", "purpose": "Poll Astro build job progress by job_id.", "type": "api"},
                ],
            },
            {
                "category": "pipeline",
                "entries": [
                    {
                        "name": "Pipeline leases",
                        "path": "/api/pipeline/leases",
                        "purpose": "Active leases to check before claiming pipeline work.",
                        "type": "api",
                    },
                    {
                        "name": "Module state",
                        "path": "/api/module/{key}/state",
                        "purpose": "Structured diagnostics to check before fixing a module.",
                        "type": "api",
                    },
                    {
                        "name": "Review audit log",
                        "path": "/api/reviews",
                        "purpose": "Existing review records to check before re-reviewing a module.",
                        "type": "api",
                    },
                    {
                        "name": "Track readiness",
                        "path": "/api/tracks/readiness",
                        "purpose": "Per-track cleared, in-flight, dead-letter, and pending counts.",
                        "type": "api",
                    },
                ],
            },
            {
                "category": "artifacts",
                "entries": [
                    {
                        "name": "Artifacts index",
                        "path": "/artifacts",
                        "purpose": "Browseable HTML and Markdown artifact index, including current handoffs.",
                        "type": "html_artifact",
                    },
                    {
                        "name": "Artifacts JSON",
                        "path": "/api/artifacts",
                        "purpose": "JSON index of HTML and Markdown artifacts served by the artifacts route.",
                        "type": "api",
                    },
                ],
            },
            {
                "category": "benchmarks",
                "ui": "/benchmarks",
                "entries": [
                    {
                        "name": "Latest calibration benchmark report",
                        "path": "/api/benchmarks/latest",
                        "purpose": "Latest calibration report artifact plus predecessor reports, ledger coverage counts, and render staleness.",
                        "type": "api",
                    },
                    {
                        "name": "Benchmarks dashboard",
                        "path": "/benchmarks",
                        "purpose": "Curated UI for the latest calibration run, report slices, and predecessor history.",
                        "type": "html",
                    },
                ],
            },
        ],
    }


def serve_static_file(repo_root: Path, rel_path: str) -> tuple[int, Any, str]:
    decoded = unquote(rel_path)
    parts = decoded.split("/")
    if not decoded or any(p in ("", ".", "..") for p in parts):
        return 404, {"error": "not_found"}, "application/json; charset=utf-8"
    static_dir = (repo_root / "static").resolve()
    candidate = (static_dir / decoded).resolve()
    try:
        candidate.relative_to(static_dir)
    except ValueError:
        return 404, {"error": "not_found"}, "application/json; charset=utf-8"
    if not candidate.is_file():
        return 404, {"error": "not_found"}, "application/json; charset=utf-8"
    ct = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8"}.get(candidate.suffix.lower())
    if ct is None:
        return 404, {"error": "not_found"}, "application/json; charset=utf-8"
    try:
        return 200, candidate.read_bytes(), ct
    except OSError:
        return 404, {"error": "not_found"}, "application/json; charset=utf-8"


def serve_artifact_file(
    repo_root: Path,
    rel_path: str,
    query: dict[str, list[str]] | None = None,
) -> tuple[int, Any, str]:
    decoded = unquote(rel_path)
    candidate = _resolve_artifact_path(repo_root, decoded)
    if candidate is None:
        return 404, {"error": "not_found", "path": decoded}, "application/json; charset=utf-8"
    if candidate.suffix.lower() == ".md":
        if not candidate.is_file():
            return 404, {"error": "not_found", "path": decoded}, "application/json; charset=utf-8"
        try:
            return 200, render_markdown_artifact_html(repo_root, candidate), "text/html; charset=utf-8"
        except OSError:
            return 404, {"error": "not_found", "path": decoded}, "application/json; charset=utf-8"
    content_type = _artifact_content_type(candidate)
    if content_type is None:
        return 404, {"error": "not_found", "path": decoded}, "application/json; charset=utf-8"
    if not candidate.is_file():
        return 404, {"error": "not_found", "path": decoded}, "application/json; charset=utf-8"
    try:
        raw_bytes = candidate.read_bytes()
    except OSError:
        return 404, {"error": "not_found", "path": decoded}, "application/json; charset=utf-8"
    if content_type == "text/html; charset=utf-8" and not _query_is_true(query or {}, "raw"):
        return 200, render_html_artifact_shell(repo_root, decoded, raw_bytes), "text/html; charset=utf-8"
    return 200, raw_bytes, content_type


_OPERATOR_PAGE_CSS = """
    :root { --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --surface-2:#1f2b3d; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --green:#4ade80; --green-muted:rgba(74,222,128,0.12); --amber:#fbbf24; --amber-muted:rgba(251,191,36,0.10); --red:#f87171; --red-muted:rgba(248,113,113,0.10); --border:rgba(255,255,255,0.06); --border-subtle:rgba(255,255,255,0.03); --radius:12px; --radius-sm:8px; }
    *, *::before, *::after { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); line-height:1.5; -webkit-font-smoothing:antialiased; }
    .main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 40px; }
    .page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .page-title { margin:0; font-size:26px; letter-spacing:0; }
    .page-sub { margin-top:4px; color:var(--text-secondary); font-size:13px; }
    .page-actions { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
    .status-pill { display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:999px; background:var(--green-muted); color:var(--green); font-size:12px; font-weight:600; }
    .dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
    .last-updated { font-size:11px; color:var(--text-dim); }
    .refresh-btn { display:flex; align-items:center; gap:6px; border:1px solid var(--border); background:var(--surface-1); color:var(--text); border-radius:var(--radius-sm); padding:8px 12px; font-size:12px; font-weight:600; cursor:pointer; }
    .refresh-btn:hover { background:var(--surface-2); }
    .panel { background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; box-shadow:0 12px 34px rgba(0,0,0,0.18); }
    .panel-header { display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid var(--border); }
    .panel-title { display:flex; align-items:center; gap:10px; font-weight:700; }
    .panel-icon { width:24px; height:24px; border-radius:var(--radius-sm); display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; background:var(--accent-muted); color:var(--accent); }
    .panel-badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; background:var(--accent-muted); color:var(--accent); }
    .op-hero { display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:14px 18px 18px; border-bottom:1px solid var(--border-subtle); }
    .op-hero-block { min-width:0; }
    .op-hero-title { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; color:var(--text-dim); margin-bottom:6px; }
    .op-hero-list { font-size:13px; color:var(--text-secondary); list-style:none; margin:0; padding:0; }
    .op-hero-list li { padding:4px 0; border-bottom:1px dashed var(--border-subtle); }
    .op-hero-list li:last-child { border-bottom:0; }
    .op-hero-list .alert { color:var(--amber); }
    .op-hero-list .blocker { color:var(--red); }
    .op-hero-empty { color:var(--text-dim); font-style:italic; font-size:12px; }
    .op-cols { display:grid; grid-template-columns:repeat(3, 1fr); gap:0; }
    .op-col { border-right:1px solid var(--border-subtle); padding:14px 18px; min-height:140px; }
    .op-col:last-child { border-right:0; }
    .op-col-title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; margin:0 0 10px; }
    .op-col-title.now { color:var(--accent); }
    .op-col-title.blocked { color:var(--red); }
    .op-col-title.next { color:var(--green); }
    .op-col-list { list-style:none; margin:0; padding:0; font-size:13px; }
    .op-col-list li { padding:6px 0; border-bottom:1px solid var(--border-subtle); color:var(--text-secondary); word-break:break-word; }
    .op-col-list li:last-child { border-bottom:0; }
    .op-col-list a { color:var(--accent); text-decoration:none; font-family:'SF Mono','Fira Code','Cascadia Code',ui-monospace,monospace; font-size:11px; }
    .op-col-list a:hover { text-decoration:underline; }
    @media (max-width: 900px) {
      .page-head { flex-direction:column; }
      .page-actions { justify-content:flex-start; }
      .op-hero, .op-cols { grid-template-columns:1fr; }
      .op-col { border-right:0; border-bottom:1px solid var(--border-subtle); }
      .op-col:last-child { border-bottom:0; }
    }
"""


_OPERATOR_SUMMARY_CSS = """
    .op-summary-card {
      display: grid;
      grid-template-columns: repeat(2, minmax(120px, 1fr)) auto;
      align-items: center;
      gap: 14px;
      padding: 16px 18px;
      color: var(--text);
      text-decoration: none;
    }
    .op-summary-card:hover { background: rgba(255,255,255,0.02); }
    .op-summary-stat { min-width: 0; }
    .op-summary-value {
      display: block;
      font-size: 24px;
      line-height: 1;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .op-summary-label {
      display: block;
      margin-top: 4px;
      color: var(--text-dim);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .op-summary-link { color: var(--accent); font-size: 13px; font-weight: 700; white-space: nowrap; }
    @media (max-width: 640px) {
      .op-summary-card { grid-template-columns: 1fr; }
      .op-summary-link { justify-self: start; }
    }
"""


_QUALITY_SUMMARY_CSS = """
    .quality-summary-card {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 12px;
      padding: 16px 18px;
      text-decoration: none;
      color: var(--text);
      min-height: 76px;
    }
    .quality-summary-card:hover { background: rgba(255,255,255,0.02); }
    .quality-summary-main { min-width: 0; }
    .quality-summary-title {
      display: block;
      font-size: 12px;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .quality-summary-counts {
      display: block;
      color: var(--text-secondary);
      font-size: 13px;
      font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .quality-summary-link {
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
    }

    @media (max-width: 640px) {
      .quality-summary-card { grid-template-columns: 1fr; }
      .quality-summary-link { justify-self: start; }
    }
"""


_PIPELINE_SUMMARY_CSS = """
    .pipeline-summary-card {
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr)) auto;
      align-items: center;
      gap: 14px;
      padding: 16px 18px;
      color: var(--text);
      text-decoration: none;
    }
    .pipeline-summary-card:hover { background: rgba(255,255,255,0.02); }
    .pipeline-summary-value {
      display: block;
      font-size: 22px;
      line-height: 1;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .pipeline-summary-label {
      display: block;
      margin-top: 4px;
      color: var(--text-dim);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .pipeline-summary-link { color: var(--accent); font-size: 13px; font-weight: 700; white-space: nowrap; }
    @media (max-width: 760px) {
      .pipeline-summary-card { grid-template-columns: 1fr 1fr; }
      .pipeline-summary-link { justify-self: start; }
    }
"""


_ACTIVITY_SUMMARY_CSS = """
    .activity-summary-card { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; gap:14px; padding:12px 18px; color:var(--text); text-decoration:none; }
    .activity-summary-card:hover { background:rgba(255,255,255,0.02); }
    .activity-summary-list { list-style:none; margin:0; padding:0; min-width:0; }
    .activity-summary-item { display:grid; grid-template-columns:18px 64px minmax(0,1fr); gap:8px; align-items:center; padding:3px 0; font-size:12px; color:var(--text-secondary); }
    .activity-summary-src { width:18px; height:18px; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; font-weight:800; font-size:10px; background:var(--amber-muted); color:var(--amber); }
    .activity-summary-src.commit { background:var(--accent-muted); color:var(--accent); }
    .activity-summary-src.pipeline_event { background:var(--teal-muted); color:var(--teal); }
    .activity-summary-time { color:var(--text-dim); font-size:11px; font-family:'SF Mono','Fira Code',ui-monospace,monospace; white-space:nowrap; }
    .activity-summary-text { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .activity-summary-link { color:var(--accent); font-size:13px; font-weight:700; white-space:nowrap; }
    @media (max-width:640px) { .activity-summary-card { grid-template-columns:1fr; } .activity-summary-link { justify-self:start; } }
"""


_HEALTH_SUMMARY_CSS = """
    .health-summary-card {
      grid-template-columns: minmax(0, 1fr) auto;
      min-height: 64px;
    }
    .health-summary-copy {
      min-width: 0;
      color: var(--text-secondary);
      font-size: 13px;
      font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    @media (max-width: 640px) {
      .health-summary-copy { white-space: normal; }
    }
"""


_ACTIVITY_FEED_CSS = """
    .activity-feed { list-style:none; margin:0; padding:0; max-height:560px; overflow-y:auto; }
    .activity-feed li { display:grid; grid-template-columns:18px 80px 120px 1fr; gap:10px; padding:8px 18px; font-size:12px; border-bottom:1px solid var(--border-subtle); align-items:center; }
    .activity-feed li:last-child { border-bottom:0; }
    .activity-src { width:18px; height:18px; border-radius:4px; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:10px; }
    .activity-src.commit { background:var(--accent-muted); color:var(--accent); }
    .activity-src.pipeline_event { background:var(--teal-muted); color:var(--teal); }
    .activity-src.bridge_message { background:var(--amber-muted); color:var(--amber); }
    .activity-time, .activity-meta { font-family:'SF Mono','Fira Code',ui-monospace,monospace; color:var(--text-dim); font-size:11px; }
    .activity-text { color:var(--text-secondary); word-break:break-word; min-width:0; }
    .activity-text .mod { color:var(--accent); }
"""


_ACTIVITY_PAGE_CSS = """
    :root { --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --surface-2:#1f2b3d; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --teal:#2dd4bf; --teal-muted:rgba(45,212,191,0.12); --green:#4ade80; --green-muted:rgba(74,222,128,0.12); --amber:#fbbf24; --amber-muted:rgba(251,191,36,0.10); --red:#f87171; --red-muted:rgba(248,113,113,0.10); --border:rgba(255,255,255,0.06); --border-subtle:rgba(255,255,255,0.03); --radius:12px; --radius-sm:8px; }
    *, *::before, *::after { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; line-height:1.5; }
    .mono { font-family:'SF Mono','Fira Code','Cascadia Code',ui-monospace,monospace; }
    .main { max-width:1180px; margin:0 auto; padding:28px 24px 40px; }
    .page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .page-title { margin:0; font-size:26px; letter-spacing:0; }
    .page-sub { margin-top:4px; color:var(--text-secondary); font-size:13px; }
    .panel { background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
    .panel-header { display:flex; justify-content:space-between; align-items:center; gap:14px; padding:14px 18px; border-bottom:1px solid var(--border); }
    .panel-title { display:flex; align-items:center; gap:10px; font-weight:700; }
    .panel-icon { width:24px; height:24px; border-radius:var(--radius-sm); display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; }
    .panel-badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; background:var(--amber-muted); color:var(--amber); white-space:nowrap; }
    .activity-tools { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .activity-select { background:var(--surface-1); color:var(--text); border:1px solid var(--border); border-radius:var(--radius-sm); padding:7px 10px; font-size:12px; outline:none; }
    .activity-select:focus { border-color:rgba(56,189,248,0.55); }
    .empty-state { padding:24px; text-align:center; color:var(--text-dim); font-size:13px; }
    @media (max-width:760px) { .page-head, .panel-header { flex-direction:column; align-items:flex-start; } .activity-feed li { grid-template-columns:18px 68px 1fr; } .activity-meta { display:none; } }
"""


_ACTIVITY_PAGE_JS = r"""
    const $ = (sel) => document.querySelector(sel);
    const AGENTS = ['claude', 'codex', 'gemini', 'autopilot'];
    const SRC_ABBR = {commit: 'C', pipeline_event: 'P', bridge_message: 'B'};
    let activityData = null;
    async function fetchJson(url) { const r = await fetch(url); return r.ok ? r.json() : {error: `HTTP ${r.status}`, url}; }
    function esc(s) { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }
    function shortenKey(key) { return String(key || '').replace(/^src\/content\/docs\//, '').replace(/\.md$/, ''); }
    function formatRelTime(epoch, nowEpoch) {
      const dt = Math.max(0, nowEpoch - epoch);
      if (dt < 60) return `${dt}s`;
      if (dt < 3600) return `${Math.floor(dt / 60)}m`;
      if (dt < 86400) return `${Math.floor(dt / 3600)}h`;
      return `${Math.floor(dt / 86400)}d`;
    }
    function activityTrack(item) {
      const key = shortenKey(item.module_key || '').toLowerCase();
      if (key.startsWith('prerequisites/') || key.startsWith('linux/')) return 'fundamentals';
      if (key.startsWith('cloud/')) return 'cloud';
      if (key.startsWith('k8s/')) return 'certifications';
      if (key.startsWith('platform/')) return 'platform';
      return 'other';
    }
    function activityAgent(item) {
      const hay = [item.actor, item.from_agent, item.to_agent, item.from_llm, item.to_llm, item.source, item.kind, item.summary, item.ref?.task_id]
        .map(v => String(v || '').toLowerCase()).join(' ');
      return AGENTS.find(agent => hay.includes(agent)) || 'unknown';
    }
    function activityDescription(item) {
      if (item.source === 'commit') return `<span class="mono">${esc(item.ref?.sha || '')}</span> ${esc(item.summary || '')}`;
      if (item.source === 'pipeline_event') {
        const mod = item.module_key ? `<span class="mod mono">${esc(shortenKey(item.module_key))}</span> ` : '';
        return `${mod}${esc(item.kind || '')}`;
      }
      return `${esc(item.summary || '')} <span class="mono" style="color:var(--text-dim)">${esc(item.kind || '')}</span>`;
    }
    function renderActivityRows() {
      const el = $('#activity-body');
      if (!activityData || activityData.error) {
        el.innerHTML = `<div class="empty-state">${esc(activityData?.error || 'No data')}</div>`;
        $('#activity-badge').textContent = 'Unknown';
        return;
      }
      const items = activityData.items || [];
      const track = $('#activity-track-filter').value;
      const agent = $('#activity-agent-filter').value;
      const shown = items.filter(item => (!track || activityTrack(item) === track) && (!agent || activityAgent(item) === agent));
      const counts = activityData.source_counts || {};
      const parts = [['commit', 'commits'], ['pipeline_event', 'events'], ['bridge_message', 'msgs']]
        .filter(([k]) => counts[k]).map(([k, label]) => `${counts[k]} ${label}`);
      $('#activity-badge').textContent = `${shown.length === items.length ? '' : `${shown.length}/${items.length} shown / `}${parts.join(' / ') || 'Quiet'}`;
      setPollTs($('#activity-badge'), activityData);
      if (!shown.length) { el.innerHTML = '<div class="empty-state">No activity matches these filters</div>'; return; }
      const now = activityData.generated_at || Math.floor(Date.now() / 1000);
      el.innerHTML = `<ul class="activity-feed">${shown.map(item => {
        const src = String(item.source || '');
        return `<li><span class="activity-src ${src}">${SRC_ABBR[src] || '?'}</span><span class="activity-time">${formatRelTime(item.at, now)} ago</span><span class="activity-meta">${esc(`${activityTrack(item)} / ${activityAgent(item)}`)}</span><span class="activity-text">${activityDescription(item)}</span></li>`;
      }).join('')}</ul>`;
    }
    async function loadActivityPage() { activityData = await fetchJson('/api/activity?limit=120'); renderActivityRows(); }
    $('#activity-track-filter').addEventListener('change', renderActivityRows);
    $('#activity-agent-filter').addEventListener('change', renderActivityRows);
    loadActivityPage().catch(err => { activityData = {error: 'Activity data unavailable'}; renderActivityRows(); console.error('Activity page load failed:', err); });
"""


_HEALTH_PAGE_CSS = """
    :root { --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --surface-2:#1f2b3d; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --green:#4ade80; --green-muted:rgba(74,222,128,0.12); --amber:#fbbf24; --amber-muted:rgba(251,191,36,0.10); --red:#f87171; --red-muted:rgba(248,113,113,0.10); --border:rgba(255,255,255,0.06); --border-subtle:rgba(255,255,255,0.03); --radius:12px; --radius-sm:8px; --radius-xs:6px; }
    *, *::before, *::after { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; line-height:1.5; }
    .mono { font-family:'SF Mono','Fira Code','Cascadia Code',ui-monospace,monospace; }
    .main { max-width:1180px; margin:0 auto; padding:28px 24px 40px; }
    .page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .page-title { margin:0; font-size:26px; letter-spacing:0; }
    .page-sub { margin-top:4px; color:var(--text-secondary); font-size:13px; }
    .health-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .section-full { grid-column:1 / -1; }
    .panel { background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
    .panel-header { display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid var(--border); gap:14px; }
    .panel-title { display:flex; align-items:center; gap:10px; font-weight:700; }
    .panel-icon { width:24px; height:24px; border-radius:var(--radius-sm); display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; }
    .panel-badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; background:var(--accent-muted); color:var(--accent); white-space:nowrap; }
    .panel-body { padding:16px 18px; }
    .panel-body-flush { padding:0; }
    .empty-state { padding:24px; text-align:center; color:var(--text-dim); font-size:13px; }
    .svc-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:0; }
    .svc-item { padding:14px 18px; border-right:1px solid var(--border); display:flex; align-items:center; gap:12px; }
    .svc-item:last-child { border-right:0; }
    .svc-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
    .svc-dot.running { background:var(--green); box-shadow:0 0 8px rgba(74,222,128,0.4); }
    .svc-dot.stopped { background:var(--text-dim); }
    .svc-dot.stale { background:var(--red); box-shadow:0 0 8px rgba(248,113,113,0.45); }
    .svc-info { min-width:0; flex:1; }
    .svc-name { font-size:13px; font-weight:500; display:flex; align-items:center; gap:6px; }
    .svc-detail { font-size:11px; color:var(--text-dim); }
    .svc-chip { display:inline-block; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; }
    .svc-chip.stale { background:var(--red-muted); color:var(--red); }
    .svc-chip.discovered { background:var(--accent-muted); color:var(--accent); }
    .wt-summary { display:flex; gap:16px; padding:12px 18px; border-bottom:1px solid var(--border); flex-wrap:wrap; }
    .wt-stat { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--text-secondary); }
    .wt-stat-val { font-weight:600; color:var(--text); }
    .wt-table { width:100%; border-collapse:collapse; }
    .wt-table th { text-align:left; padding:8px 14px; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-dim); border-bottom:1px solid var(--border); background:rgba(0,0,0,0.15); }
    .wt-table td { padding:6px 14px; font-size:12px; border-bottom:1px solid var(--border-subtle); }
    .wt-table tr:last-child td { border-bottom:0; }
    .wt-path { color:var(--text-secondary); word-break:break-all; }
    .wt-badge { display:inline-block; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:600; text-transform:uppercase; }
    .wt-badge.M { background:var(--amber-muted); color:var(--amber); }
    .wt-badge.A { background:var(--green-muted); color:var(--green); }
    .wt-badge.D, .wt-badge.U { background:var(--red-muted); color:var(--red); }
    .wt-badge.Q { background:var(--accent-muted); color:var(--accent); }
    .wt-scroll { max-height:420px; overflow:auto; }
    .missing-group { margin-bottom:12px; }
    .missing-group:last-child { margin-bottom:0; }
    .missing-group-title { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-dim); margin-bottom:8px; display:flex; align-items:center; gap:8px; }
    .missing-list { margin:0; padding:0; list-style:none; }
    .missing-item { padding:5px 10px; font-size:12px; color:var(--text-secondary); border-radius:var(--radius-xs); margin-bottom:2px; }
    .missing-item:hover { background:rgba(255,255,255,0.03); }
    .clr-red { color:var(--red); }
    @media (max-width:900px) { .health-grid, .svc-grid { grid-template-columns:1fr; } .section-full { grid-column:auto; } .svc-item { border-right:0; border-bottom:1px solid var(--border); } .svc-item:last-child { border-bottom:0; } .page-head, .panel-header { flex-direction:column; align-items:flex-start; } }
"""


_HEALTH_PAGE_JS = r"""
    const $ = (sel) => document.querySelector(sel);
    async function fetchJson(url) { const r = await fetch(url); return r.ok ? r.json() : {error: `HTTP ${r.status}`, url}; }
    function esc(s) { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }
    function formatUptime(seconds) {
      if (seconds == null || !isFinite(seconds) || seconds < 0) return '';
      const s = Math.floor(seconds);
      if (s < 60) return `${s}s`;
      const m = Math.floor(s / 60);
      if (m < 60) return `${m}m`;
      const h = Math.floor(m / 60);
      if (h < 48) return `${h}h ${m % 60}m`;
      const d = Math.floor(h / 24);
      return `${d}d ${h % 24}h`;
    }

    function renderServices(data) {
      const el = $('#services');
      const badge = $('#svc-badge');
      if (!data || data.error) {
        el.innerHTML = `<div class="empty-state clr-red">${esc(data?.error || 'No data')}</div>`;
        badge.textContent = 'Unknown';
        return;
      }
      if (!data.services || data.services.length === 0) {
        el.innerHTML = '<div class="empty-state">No services configured</div>';
        badge.textContent = 'Empty';
        return;
      }
      const total = data.total ?? (data.running + data.stopped + (data.stale || 0));
      badge.textContent = `${data.running} / ${total} running${data.stale ? ` · ${data.stale} stale` : ''}`;
      badge.style.background = data.stale ? 'var(--red-muted)' : (data.stopped === 0 ? 'var(--green-muted)' : 'var(--amber-muted)');
      badge.style.color = data.stale ? 'var(--red)' : (data.stopped === 0 ? 'var(--green)' : 'var(--amber)');
      el.innerHTML = data.services.map(s => {
        const chips = [];
        if (s.status === 'stale') chips.push('<span class="svc-chip stale">Stale PID</span>');
        if (s.known === false) chips.push('<span class="svc-chip discovered">Discovered</span>');
        let detail = 'Stopped';
        if (s.status === 'running') {
          const up = formatUptime(s.uptime_seconds);
          detail = `PID ${s.pid}${up ? ` &middot; up ${up}` : ''}`;
        } else if (s.status === 'stale') {
          detail = s.pid != null ? `PID ${s.pid} not responding` : 'Unreadable PID file';
        }
        if (s.port) detail += ` &middot; :${s.port}`;
        return `<div class="svc-item">
          <span class="svc-dot ${esc(s.status)}"></span>
          <div class="svc-info">
            <div class="svc-name">${esc(s.label)}${chips.join('')}</div>
            <div class="svc-detail mono">${detail}</div>
          </div>
        </div>`;
      }).join('');
    }

    function renderWorktrees(data) {
      const el = $('#worktrees');
      const badge = $('#worktrees-badge');
      if (!data || data.error) {
        el.innerHTML = `<div class="empty-state clr-red">${esc(data?.error || 'No data')}</div>`;
        badge.textContent = 'Unknown';
        return;
      }
      const rows = data.worktrees || [];
      const dirty = rows.filter(w => w.dirty === true).length;
      const unknown = rows.filter(w => w.dirty == null).length;
      badge.textContent = `${rows.length} worktrees${dirty ? ` · ${dirty} dirty` : ''}${unknown ? ` · ${unknown} unknown` : ''}`;
      badge.style.background = dirty || unknown ? 'var(--amber-muted)' : 'var(--green-muted)';
      badge.style.color = dirty || unknown ? 'var(--amber)' : 'var(--green)';
      if (!rows.length) {
        el.innerHTML = '<div class="empty-state">No worktrees found</div>';
        return;
      }
      const primary = data.primary || '';
      const body = rows.map(w => {
        const counts = w.counts || {};
        const dirtyText = w.dirty == null ? 'unknown' : (w.dirty ? `${counts.total || 0} files` : 'clean');
        const state = w.locked ? ['locked', 'D'] : (w.prunable ? ['prunable', 'D'] : (w.detached ? ['detached', 'M'] : ['active', 'A']));
        const branch = w.branch || (w.detached ? 'detached' : 'unknown');
        return `<tr>
          <td><span class="wt-badge ${state[1]}">${state[0]}</span></td>
          <td class="mono">${esc(branch)}</td>
          <td>${esc(dirtyText)}</td>
          <td class="wt-path mono">${esc(w.path)}${w.path === primary ? ' <span class="wt-badge Q">primary</span>' : ''}</td>
        </tr>`;
      }).join('');
      el.innerHTML = `<div class="wt-summary">
          <div class="wt-stat">Total: <span class="wt-stat-val">${rows.length}</span></div>
          <div class="wt-stat">Dirty: <span class="wt-stat-val">${dirty}</span></div>
          <div class="wt-stat">Unknown: <span class="wt-stat-val">${unknown}</span></div>
        </div>
        <div class="wt-scroll"><table class="wt-table">
          <thead><tr><th>State</th><th>Branch</th><th>Dirty</th><th>Path</th></tr></thead>
          <tbody>${body}</tbody>
        </table></div>`;
    }

    function renderMissing(data) {
      const el = $('#missing');
      const badge = $('#missing-badge');
      if (!data || data.error) {
        el.innerHTML = `<div class="empty-state clr-red">${esc(data?.error || 'No data')}</div>`;
        badge.textContent = 'Unknown';
        return;
      }
      const activeList = data.active_exact?.modules ?? [];
      const deferredList = data.deferred?.modules ?? [];
      const total = activeList.length + deferredList.length;
      badge.textContent = total === 0 ? 'Complete' : `${total} missing`;
      badge.style.background = total === 0 ? 'var(--green-muted)' : 'var(--amber-muted)';
      badge.style.color = total === 0 ? 'var(--green)' : 'var(--amber)';
      if (total === 0) {
        el.innerHTML = '<div class="empty-state">All modules present</div>';
        return;
      }
      let html = '';
      if (activeList.length) {
        html += `<div class="missing-group">
          <div class="missing-group-title"><span class="wt-badge M">Active</span> ${activeList.length} missing</div>
          <ul class="missing-list">${activeList.map(m => `<li class="missing-item mono">${esc(m)}</li>`).join('')}</ul>
        </div>`;
      }
      if (deferredList.length) {
        html += `<div class="missing-group">
          <div class="missing-group-title"><span class="wt-badge Q">Deferred</span> ${deferredList.length} estimated</div>
          <ul class="missing-list">${deferredList.slice(0, 20).map(m => `<li class="missing-item mono">${esc(m)}</li>`).join('')}</ul>
          ${deferredList.length > 20 ? `<div class="empty-state">+${deferredList.length - 20} more</div>` : ''}
        </div>`;
      }
      el.innerHTML = html;
    }

    async function loadHealthPage() {
      const [services, worktrees, missing] = await Promise.all([
        fetchJson('/api/runtime/services'),
        fetchJson('/api/git/worktrees'),
        fetchJson('/api/missing-modules/status'),
      ]);
      renderServices(services);
      renderWorktrees(worktrees);
      renderMissing(missing);
      setPollTs($('#svc-badge'), services);
    }
    loadHealthPage().catch(err => {
      $('#services').innerHTML = '<div class="empty-state">Health data unavailable</div>';
      $('#worktrees').innerHTML = '<div class="empty-state">Worktree data unavailable</div>';
      $('#missing').innerHTML = '<div class="empty-state">Missing-module data unavailable</div>';
      console.error('Health page load failed:', err);
    });
"""


_PIPELINE_PAGE_CSS = """
    :root { --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --surface-2:#1f2b3d; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --teal:#2dd4bf; --teal-muted:rgba(45,212,191,0.12); --green:#4ade80; --green-muted:rgba(74,222,128,0.12); --amber:#fbbf24; --amber-muted:rgba(251,191,36,0.10); --red:#f87171; --red-muted:rgba(248,113,113,0.10); --border:rgba(255,255,255,0.06); --border-subtle:rgba(255,255,255,0.03); --radius:12px; --radius-sm:8px; }
    *, *::before, *::after { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; line-height:1.5; }
    .mono { font-family:'SF Mono','Fira Code','Cascadia Code',ui-monospace,monospace; }
    .main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 40px; }
    .page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .page-title { margin:0; font-size:26px; letter-spacing:0; }
    .page-sub { margin-top:4px; color:var(--text-secondary); font-size:13px; }
    .panel { background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; margin-bottom:16px; }
    .panel-header { display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid var(--border); }
    .panel-title { display:flex; align-items:center; gap:10px; font-weight:700; }
    .panel-icon { width:24px; height:24px; border-radius:var(--radius-sm); display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; }
    .panel-badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; background:var(--accent-muted); color:var(--accent); }
    .panel-body, .panel-body-flush { padding:0; }
    .empty-state { padding:24px; text-align:center; color:var(--text-dim); font-size:13px; }
    .queue-summary { padding:14px 18px; border-bottom:1px solid var(--border); display:grid; grid-template-columns:repeat(4,1fr); gap:0; text-align:center; }
    .queue-stat { border-right:1px solid var(--border-subtle); padding:2px 8px; }
    .queue-stat:last-child { border-right:0; }
    .queue-stat-val { font-size:20px; font-weight:700; letter-spacing:0; line-height:1; }
    .queue-stat-label { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-dim); margin-top:6px; }
    .queue-per-track { padding:0; }
    .qpt-row { display:grid; grid-template-columns:1fr auto; padding:8px 18px; border-bottom:1px solid var(--border-subtle); font-size:12px; align-items:center; gap:12px; }
    .qpt-name { color:var(--text-secondary); }
    .qpt-status { font-size:11px; color:var(--text-dim); text-align:right; }
    .qpt-status .pill { display:inline-block; padding:1px 7px; border-radius:10px; font-size:10px; font-weight:600; margin-left:4px; }
    .qpt-status .pill.w { background:var(--accent-muted); color:var(--accent); }
    .qpt-status .pill.r { background:var(--amber-muted); color:var(--amber); }
    .qpt-status .pill.p { background:var(--teal-muted); color:var(--teal); }
    .qpt-status .pill.d { background:var(--red-muted); color:var(--red); }
    .qpt-top { padding:12px 18px; border-top:1px solid var(--border); background:rgba(0,0,0,0.12); }
    .qpt-top-title { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-dim); margin-bottom:8px; }
    .qpt-top-list { margin:0; padding:0; list-style:none; }
    .qpt-top-list li { padding:3px 0; font-size:12px; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .qpt-top-kind { display:inline-block; width:14px; font-weight:700; font-size:10px; text-transform:uppercase; }
    .qpt-top-kind.w { color:var(--accent); } .qpt-top-kind.r { color:var(--amber); } .qpt-top-kind.p { color:var(--teal); } .qpt-top-kind.d { color:var(--red); }
    .autopilot-grid { padding:14px 18px; display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; }
    .autopilot-kv { border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface-1); padding:8px 10px; min-width:0; }
    .autopilot-label { color:var(--text-dim); font-size:11px; text-transform:uppercase; letter-spacing:0.04em; }
    .autopilot-value { margin-top:3px; color:var(--text); font-size:13px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .event-list { list-style:none; margin:0; padding:0; max-height:360px; overflow:auto; }
    .event-list li { display:grid; grid-template-columns:70px 1fr 130px; gap:10px; padding:8px 18px; border-bottom:1px solid var(--border-subtle); font-size:12px; align-items:center; }
    .event-kind { color:var(--teal); font-weight:700; }
    .event-module { color:var(--text-secondary); min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .event-time { color:var(--text-dim); text-align:right; }
    @media (max-width: 760px) {
      .page-head { flex-direction:column; }
      .queue-summary, .autopilot-grid { grid-template-columns:1fr 1fr; }
      .event-list li { grid-template-columns:1fr; gap:4px; }
      .event-time { text-align:left; }
    }
"""


_QUALITY_BOARD_PAGE_CSS = """
    :root { --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --surface-2:#1f2b3d; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --teal:#2dd4bf; --teal-muted:rgba(45,212,191,0.12); --green:#4ade80; --green-muted:rgba(74,222,128,0.12); --amber:#fbbf24; --amber-muted:rgba(251,191,36,0.10); --red:#f87171; --red-muted:rgba(248,113,113,0.10); --border:rgba(255,255,255,0.06); --border-subtle:rgba(255,255,255,0.03); --radius:12px; --radius-sm:8px; --radius-xs:6px; }
    *, *::before, *::after { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; line-height:1.5; }
    .main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 40px; }
    .page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .page-title { margin:0; font-size:26px; letter-spacing:0; }
    .page-sub { margin-top:4px; color:var(--text-secondary); font-size:13px; }
    .page-actions { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
    .status-pill { display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:999px; font-size:12px; font-weight:600; background:var(--green-muted); color:var(--green); }
    .dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
    .refresh-btn { display:flex; align-items:center; gap:6px; border:1px solid var(--border); background:var(--surface-1); color:var(--text); border-radius:var(--radius-sm); padding:8px 12px; font-size:12px; font-weight:600; cursor:pointer; }
    .refresh-btn:hover { background:var(--surface-2); }
    .panel { background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
    .panel-header { display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid var(--border); }
    .panel-title { display:flex; align-items:center; gap:10px; font-weight:700; }
    .panel-icon { width:24px; height:24px; border-radius:var(--radius-sm); display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; background:var(--accent-muted); color:var(--accent); }
    .panel-badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; background:var(--accent-muted); color:var(--accent); }
    .panel-body { padding: 16px 18px; }

    .qb-wrap { padding: 14px 18px 18px; }
    .qb-stack { display: flex; height: 14px; overflow: hidden; border-radius: 999px; background: var(--surface-1); border: 1px solid var(--border); margin-bottom: 12px; }
    .qb-seg { min-width: 2px; height: 100%; }
    .qb-done { background: var(--green); }
    .qb-needs_rewrite { background: var(--red); }
    .qb-needs_review { background: var(--amber); }
    .qb-shipped_unreviewed { background: #f97316; }
    .qb-both { background: #c084fc; }
    .qb-in_flight { background: var(--accent); }
    .qb-legend {
      display: flex; flex-wrap: wrap; gap: 8px 12px; margin-bottom: 14px;
      font-size: 11px; color: var(--text-secondary);
    }
    .qb-legend span { display: inline-flex; align-items: center; gap: 5px; }
    .qb-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
    .qb-tracks { display: grid; grid-template-columns: repeat(auto-fill,minmax(210px,1fr)); gap: 8px; margin-bottom: 14px; }
    .qb-track {
      background: var(--surface-1); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 8px 10px; min-width: 0;
    }
    .qb-track-head { display:flex; justify-content:space-between; gap:8px; margin-bottom: 7px; font-size: 12px; }
    .qb-track-name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .qb-track-total { color: var(--text-dim); font-variant-numeric: tabular-nums; }
    .qb-mini { display:flex; height: 5px; overflow: hidden; border-radius: 999px; background: var(--border); margin-bottom: 7px; }
    .qb-track-counts {
      display: flex; gap: 7px; flex-wrap: wrap; font-size: 10px;
      color: var(--text-dim); font-family: 'SF Mono', 'Fira Code', ui-monospace, monospace;
    }
    .qb-tools {
      display: grid; grid-template-columns: minmax(180px, 1fr) 170px 170px;
      gap: 8px; margin-bottom: 10px;
    }
    .qb-input, .qb-select {
      width: 100%; background: var(--surface-1); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 12px; outline: none;
    }
    .qb-input:focus, .qb-select:focus { border-color: rgba(56,189,248,0.55); }
    .qb-table-wrap { max-height: 430px; overflow: auto; border: 1px solid var(--border); border-radius: var(--radius-sm); }
    .qb-table { width: 100%; border-collapse: collapse; }
    .qb-table th {
      position: sticky; top: 0; z-index: 1; background: var(--surface-1); color: var(--text-dim);
      text-align: left; padding: 8px 10px; font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.04em; border-bottom: 1px solid var(--border);
    }
    .qb-table td { padding: 7px 10px; font-size: 12px; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary); }
    .qb-table tr:last-child td { border-bottom: 0; }
    .qb-table tr:hover td { background: rgba(255,255,255,0.02); }
    .qb-module { color: var(--text); font-weight: 500; }
    .qb-path { color: var(--text-dim); font-size: 11px; }
    .qb-num { text-align: right; font-variant-numeric: tabular-nums; }
    .qb-chip {
      display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 10px;
      font-weight: 700; text-transform: uppercase; white-space: nowrap;
    }
    .qb-chip.done { background: var(--green-muted); color: var(--green); }
    .qb-chip.needs_rewrite { background: var(--red-muted); color: var(--red); }
    .qb-chip.needs_review { background: var(--amber-muted); color: var(--amber); }
    .qb-chip.shipped_unreviewed { background: rgba(249,115,22,0.14); color: #f97316; }
    .qb-chip.both { background: rgba(192,132,252,0.14); color: #c084fc; }
    .qb-chip.in_flight { background: var(--accent-muted); color: var(--accent); }
    .qb-module-link { color: var(--accent); text-decoration: none; font-size: 11px; }
    .qb-module-link:hover { text-decoration: underline; }
    .qb-detail {
      margin-top: 10px;
      background: var(--surface-1);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 10px;
      display: grid;
      grid-template-columns: 1.2fr repeat(5, auto);
      gap: 10px;
      align-items: center;
      font-size: 12px;
    }
    .qb-detail-title { font-weight: 600; color: var(--text); min-width: 0; }
    .qb-detail-kv { color: var(--text-dim); font-size: 11px; white-space: nowrap; }
    .qb-detail-kv strong { color: var(--text-secondary); font-weight: 600; }
    .empty-state { padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px; }
    .module-detail-summary {
      padding: 12px 18px; display:grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap:10px; border-top:1px solid var(--border);
    }
    .module-kv {
      display:grid; gap:3px;
      border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-1); padding: 8px 10px;
    }
    .module-kv-label { color:var(--text-dim); font-size:11px; text-transform: uppercase; letter-spacing: 0.04em; }
    .module-kv-value { color:var(--text); font-size:13px; font-weight:600; }
    .module-kv a { color: var(--accent); text-decoration: none; }
    .module-kv a:hover { text-decoration: underline; }
    .gate-list { margin: 0; padding: 0 0 0 16px; }
    .gate-list li { font-size: 12px; color: var(--text-secondary); padding: 3px 0; }
    .gate-list li.critical { color: #f87171; }
    .gate-list li.warn { color: #fbbf24; }
    .gate-list li.info { color: #2dd4bf; }
    .back-link { color: var(--text-dim); text-decoration:none; font-size:13px; }
    .back-link:hover { color: var(--accent); }
    @media (max-width: 900px) {
      .qb-tools { grid-template-columns: 1fr; }
      .qb-detail { grid-template-columns: 1fr 1fr; }
      .module-detail-summary { grid-template-columns: 1fr; }
      .page-head { flex-direction: column; }
      .page-actions { justify-content: flex-start; }
    }
"""

_QUALITY_BOARD_PAGE_JS = r"""
    const $ = (sel) => document.querySelector(sel);

    async function fetchJson(url) {
      const r = await fetch(url);
      if (!r.ok) return { error: `HTTP ${r.status}`, url };
      return r.json();
    }

    function esc(s) {
      const d = document.createElement('div');
      d.textContent = String(s ?? '');
      return d.innerHTML;
    }

    const QB_STATUS = ['done', 'needs_rewrite', 'needs_review', 'shipped_unreviewed', 'both', 'in_flight'];
    const QB_LABEL = {
      done: 'Done',
      needs_rewrite: 'Rewrite',
      needs_review: 'Review',
      shipped_unreviewed: 'Shipped (unreviewed)',
      both: 'Both',
      in_flight: 'In flight',
    };
    let qualityBoardData = null;
    let qualityBoardSelected = null;

    function qbSegs(counts, total, mini = false) {
      const denom = Math.max(1, total || 0);
      return QB_STATUS.map(status => {
        const n = counts?.[status] || 0;
        if (!n) return '';
        const pct = Math.max(mini ? 1.5 : 0.5, n / denom * 100);
        return `<div class="qb-seg qb-${status}" title="${QB_LABEL[status]}: ${n}" style="width:${pct}%"></div>`;
      }).join('');
    }

    function qbChip(status) {
      return `<span class="qb-chip ${esc(status)}">${QB_LABEL[status] || status}</span>`;
    }

    function renderQualityBoardDetail(module) {
      const el = $('#qb-detail');
      if (!el) return;
      if (!module) {
        el.innerHTML = '<div class="qb-detail-title">No entry selected</div>';
        return;
      }
      const typeLabel = module.content_type === 'book_chapter' ? 'Book chapter' : 'Module';
      el.innerHTML = `
        <div>
          <div class="qb-detail-title">${esc(module.title || module.module_key || module.path)}</div>
          <div class="qb-path mono">${esc(module.path || module.slug)}</div>
        </div>
        <div class="qb-detail-kv">Status<br><strong>${QB_LABEL[module.status] || module.status}</strong></div>
        <div class="qb-detail-kv">Type<br><strong>${typeLabel}</strong></div>
        <div class="qb-detail-kv">Score<br><strong>${module.score == null ? 'n/a' : Number(module.score).toFixed(1)}</strong></div>
        <div class="qb-detail-kv">Banner<br><strong>${module.revision_pending ? 'pending' : 'clear'}</strong></div>
        <div class="qb-detail-kv">Stage<br><strong>${esc(module.stage || 'none')}</strong></div>
        <div class="qb-detail-kv">Review<br><strong>${esc(module.latest_review_verdict || (module.auto_approved ? 'auto' : 'none'))}</strong></div>
        <div class="qb-detail-kv">Queue<br><strong>${module.in_post_review_queue ? 'yes' : 'no'}</strong></div>`;
    }

    function encodeQualityPath(relPath) {
      return String(relPath || '')
        .replace(/\\.md$/i, '')
        .split('/')
        .map(encodeURIComponent)
        .join('/');
    }

    function renderQualityBoardTable() {
      if (!qualityBoardData) return;
      const modules = qualityBoardData.modules || [];
      const q = ($('#qb-search')?.value || '').trim().toLowerCase();
      const track = $('#qb-track')?.value || '';
      const status = $('#qb-status')?.value || '';
      const statusRank = Object.fromEntries(QB_STATUS.map((s, i) => [s, i]));

      const rows = modules
        .filter(m => !track || m.track === track)
        .filter(m => !status || m.status === status)
        .filter(m => {
          if (!q) return true;
          return String(m.title || '').toLowerCase().includes(q)
            || String(m.module_key || '').toLowerCase().includes(q)
            || String(m.path || '').toLowerCase().includes(q)
            || String(m.slug || '').toLowerCase().includes(q);
        })
        .sort((a, b) => (statusRank[a.status] ?? 99) - (statusRank[b.status] ?? 99)
          || String(a.track).localeCompare(String(b.track))
          || String(a.title || a.path).localeCompare(String(b.title || b.path)));

      $('#qb-count').textContent = `${rows.length} shown`;
      const selected = rows.find(m => m.slug === qualityBoardSelected) || rows[0] || null;
      qualityBoardSelected = selected?.slug || null;
      const body = rows.map(m => {
        const detailPath = encodeQualityPath(m.path || `${m.slug}.md`);
        const typeLabel = m.content_type === 'book_chapter' ? 'Book chapter' : 'Module';
        return `<tr data-slug="${esc(m.slug)}" class="${m.slug === qualityBoardSelected ? 'selected' : ''}">
          <td>${qbChip(m.status)}</td>
          <td>
            <div class="qb-module"><a class="qb-module-link" href="/quality/${detailPath}">${esc(m.title || m.module_key)}</a></div>
            <div class="qb-path mono">${esc(typeLabel)} · ${esc(m.path)}</div>
          </td>
          <td>${esc(m.track || '')}</td>
          <td class="mono">${esc(m.stage || 'none')}</td>
          <td class="qb-num">${m.score == null ? '' : Number(m.score).toFixed(1)}</td>
        </tr>`;
      }).join('');
      $('#qb-table-body').innerHTML = body || '<tr><td colspan="5" class="empty-state">No entries match filters</td></tr>';
      for (const tr of document.querySelectorAll('#qb-table-body tr[data-slug]')) {
        tr.addEventListener('click', () => {
          qualityBoardSelected = tr.dataset.slug;
          const picked = modules.find(m => m.slug === qualityBoardSelected);
          renderQualityBoardTable();
          renderQualityBoardDetail(picked);
        });
      }
      renderQualityBoardDetail(selected);
    }

    function renderQualityBoard(data) {
      const el = $('#quality-board');
      const badge = $('#qb-badge');

      if (!data || data.error) {
        el.innerHTML = `<div class="empty-state">${esc(data?.error || 'No data')}</div>`;
        badge.textContent = 'Unknown';
        return;
      }

      qualityBoardData = data;
      const totals = data.totals || {};
      const total = totals.total || 0;
      const bookTotals = data.book_totals || {};
      const bookTotal = bookTotals.total || 0;
      const needs = (totals.needs_rewrite || 0) + (totals.needs_review || 0) + (totals.shipped_unreviewed || 0) + (totals.both || 0);
      const bookNeeds = (bookTotals.needs_rewrite || 0) + (bookTotals.needs_review || 0) + (bookTotals.shipped_unreviewed || 0) + (bookTotals.both || 0);
      const bookText = bookTotal ? ` · ${bookTotal} book chapters tracked` : '';
      badge.textContent = `${totals.done || 0} / ${total} modules done · ${needs} left${bookText}`;
      badge.style.background = (needs || bookNeeds) ? 'var(--amber-muted)' : 'var(--green-muted)';
      badge.style.color = (needs || bookNeeds) ? 'var(--amber)' : 'var(--green)';

      const tracks = data.tracks || [];
      const trackOptions = tracks
        .map(t => `<option value="${esc(t.track)}">${esc(t.track)} (${t.total || t.totals?.total || 0})</option>`)
        .join('');

      const legend = QB_STATUS.map(s => {
        const n = totals[s] || 0;
        return `<span><i class="qb-dot qb-${s}"></i>${QB_LABEL[s]} <strong>${n}</strong></span>`;
      }).join('');

      const trackCards = tracks.map(t => {
        const c = t.totals || t;
        const tTotal = c.total || 0;
        const counts = QB_STATUS.map(s => c[s] ? `<span>${QB_LABEL[s]}:${c[s]}</span>` : '').filter(Boolean).join('');
        return `<div class="qb-track">
          <div class="qb-track-head">
            <span class="qb-track-name">${esc(t.track)}</span>
            <span class="qb-track-total">${c.done || 0}/${tTotal}</span>
          </div>
          <div class="qb-mini">${qbSegs(c, tTotal, true)}</div>
          <div class="qb-track-counts">${counts || '<span>empty</span>'}</div>
        </div>`;
      }).join('');

      el.innerHTML = `
        <div class="qb-wrap">
          <div class="qb-stack">${qbSegs(totals, total)}</div>
          <div class="qb-legend">${legend}</div>
          <div class="qb-tracks">${trackCards || '<div class="empty-state">No tracks</div>'}</div>
          <div class="qb-tools">
            <input class="qb-input" id="qb-search" type="search" placeholder="Search entries">
            <select class="qb-select" id="qb-track"><option value="">All tracks</option>${trackOptions}</select>
            <select class="qb-select" id="qb-status">
              <option value="">All statuses</option>
              ${QB_STATUS.map(s => `<option value="${s}">${QB_LABEL[s]}</option>`).join('')}
            </select>
          </div>
          <div class="qb-table-wrap">
            <table class="qb-table">
              <thead><tr><th>Status</th><th>Entry</th><th>Track</th><th>Stage</th><th class="qb-num">Score</th></tr></thead>
              <tbody id="qb-table-body"></tbody>
            </table>
          </div>
          <div class="qb-detail" id="qb-detail"></div>
          <div class="mono qb-path" id="qb-count" style="margin-top:8px"></div>
        </div>`;

      $('#qb-search').addEventListener('input', renderQualityBoardTable);
      $('#qb-track').addEventListener('change', renderQualityBoardTable);
      $('#qb-status').addEventListener('change', renderQualityBoardTable);
      renderQualityBoardTable();
    }

    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      const btn = $('#refresh');
      btn.classList.add('loading');
      try {
        const board = await fetchJson('/api/quality/board');
        renderQualityBoard(board);
        setPollTs($('#last-updated'), board);
        $('#last-updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
      } catch (err) {
        console.error('Quality board refresh failed:', err);
      } finally {
        refreshing = false;
        btn.classList.remove('loading');
      }
    }

    $('#refresh').addEventListener('click', refresh);
    refresh();
    setInterval(refresh, 60000);
"""

_UK_BOARD_PAGE_CSS = """
    :root { --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --surface-2:#1f2b3d; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --green:#4ade80; --green-muted:rgba(74,222,128,0.12); --amber:#fbbf24; --amber-muted:rgba(251,191,36,0.10); --red:#f87171; --red-muted:rgba(248,113,113,0.10); --border:rgba(255,255,255,0.06); --border-subtle:rgba(255,255,255,0.03); --radius:12px; --radius-sm:8px; }
    *, *::before, *::after { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; line-height:1.5; }
    .main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 40px; }
    .page-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .page-title { margin:0; font-size:26px; letter-spacing:0; }
    .page-sub { margin-top:4px; color:var(--text-secondary); font-size:13px; }
    .page-actions { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
    .status-pill { display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:999px; font-size:12px; font-weight:600; background:var(--green-muted); color:var(--green); }
    .dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
    .refresh-btn { display:flex; align-items:center; gap:6px; border:1px solid var(--border); background:var(--surface-1); color:var(--text); border-radius:var(--radius-sm); padding:8px 12px; font-size:12px; font-weight:600; cursor:pointer; }
    .refresh-btn:hover { background:var(--surface-2); }
    .panel { background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
    .panel-header { display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid var(--border); }
    .panel-title { display:flex; align-items:center; gap:10px; font-weight:700; }
    .panel-icon { width:24px; height:24px; border-radius:var(--radius-sm); display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; background:var(--accent-muted); color:var(--accent); }
    .panel-badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; background:var(--accent-muted); color:var(--accent); }
    .uk-wrap { padding: 16px 18px 18px; }
    .uk-headline { font-size: 34px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 6px; color: var(--text); }
    .uk-headline span { color: var(--green); }
    .uk-subcounts { color: var(--text-secondary); font-size: 14px; margin-bottom: 6px; }
    .uk-note { color: var(--text-dim); font-size: 12px; margin-bottom: 16px; }
    .uk-table-wrap { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
    .uk-table { width: 100%; border-collapse: collapse; }
    .uk-table th {
      background: var(--surface-1); color: var(--text-dim); text-align: left;
      padding: 8px 10px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
      border-bottom: 1px solid var(--border);
    }
    .uk-table td { padding: 8px 10px; font-size: 12px; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary); vertical-align: middle; }
    .uk-table tr:last-child td { border-bottom: 0; }
    .uk-num { text-align: right; font-variant-numeric: tabular-nums; }
    .uk-mini { display:flex; height: 6px; overflow: hidden; border-radius: 999px; background: var(--border); min-width: 72px; }
    .uk-seg-current { background: var(--green); }
    .uk-seg-stale { background: var(--amber); }
    .uk-seg-missing { background: var(--red); }
    .uk-track-row { cursor: pointer; }
    .uk-track-row:hover td { background: rgba(255,255,255,0.02); }
    .uk-expand { color: var(--text-dim); font-size: 11px; }
    .uk-page-list { margin: 0; padding: 8px 12px 10px 28px; background: var(--surface-1); list-style: none; }
    .uk-page-item { display: flex; align-items: center; gap: 10px; padding: 4px 0; font-size: 12px; color: var(--text-secondary); }
    .uk-page-path { font-family: 'SF Mono', 'Fira Code', ui-monospace, monospace; color: var(--text-dim); font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .uk-page-words { font-variant-numeric: tabular-nums; color: var(--text-dim); font-size: 11px; white-space: nowrap; }
    .uk-chip {
      display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 10px;
      font-weight: 700; text-transform: uppercase; white-space: nowrap;
    }
    .uk-chip.current { background: var(--green-muted); color: var(--green); }
    .uk-chip.stale { background: var(--amber-muted); color: var(--amber); }
    .uk-chip.missing { background: var(--red-muted); color: var(--red); }
    .uk-calque { font-size: 11px; white-space: nowrap; font-weight: 600; }
    .uk-calque small { font-weight: 500; opacity: 0.85; margin-left: 4px; }
    .uk-calque.pending { color: var(--text-dim); }
    .uk-calque.stale { color: var(--amber); }
    .uk-calque.reviewed { color: var(--green); }
    .empty-state { padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px; }
    @media (max-width: 900px) {
      .page-head { flex-direction: column; }
      .page-actions { justify-content: flex-start; }
    }
"""

_UK_BOARD_PAGE_JS = r"""
    const $ = (sel) => document.querySelector(sel);

    async function fetchJson(url) {
      const r = await fetch(url);
      if (!r.ok) return { error: `HTTP ${r.status}`, url };
      return r.json();
    }

    function esc(s) {
      const d = document.createElement('div');
      d.textContent = String(s ?? '');
      return d.innerHTML;
    }

    function ukChip(status) {
      return `<span class="uk-chip ${esc(status)}">${esc(status)}</span>`;
    }

    function ukCalqueReview(page) {
      const review = page.calque_review;
      if (!review) return '<span class="uk-calque pending">⏳ pending</span>';
      if (review.stale) return '<span class="uk-calque stale">⚠ stale</span>';
      const version = review.detector_version ? `<small>${esc(review.detector_version)}</small>` : '';
      return `<span class="uk-calque reviewed">✓ reviewed${version}</span>`;
    }

    function ukMiniBar(track) {
      const total = Math.max(1, track.total || 0);
      const segments = [
        { key: 'current', n: track.current || 0 },
        { key: 'stale', n: track.stale || 0 },
        { key: 'missing', n: track.missing || 0 },
      ];
      return segments.map(seg => {
        if (!seg.n) return '';
        const pct = Math.max(1.5, seg.n / total * 100);
        return `<div class="uk-seg-${seg.key}" title="${seg.key}: ${seg.n}" style="width:${pct}%"></div>`;
      }).join('');
    }

    function renderUkBoard(data) {
      const el = $('#uk-board');
      const badge = $('#uk-badge');
      if (!data || data.error) {
        el.innerHTML = `<div class="empty-state">${esc(data?.error || 'No data')}</div>`;
        badge.textContent = 'Unknown';
        return;
      }

      const totals = data.totals || {};
      const total = totals.total || 0;
      const current = totals.current || 0;
      const stale = totals.stale || 0;
      const missing = totals.missing || 0;
      const currentPct = totals.current_pct || 0;
      const reviewed = totals.reviewed || 0;
      const reviewedPct = totals.reviewed_pct || 0;
      const toGo = stale + missing;
      badge.textContent = `${current} / ${total} current · ${reviewed} / ${total} calque-reviewed`;
      badge.style.background = currentPct >= 60 ? 'var(--green-muted)' : 'var(--amber-muted)';
      badge.style.color = currentPct >= 60 ? 'var(--green)' : 'var(--amber)';

      const tracks = data.tracks || [];
      const rows = tracks.map(track => {
        const pages = (track.pages || []).map(page => `
          <li class="uk-page-item">
            ${ukChip(page.status)}
            <span class="uk-page-path">${esc(page.rel)}</span>
            <span class="uk-page-words">${page.uk_words || 0}/${page.en_words || 0} (${Number(page.ratio || 0).toFixed(2)})</span>
            ${ukCalqueReview(page)}
          </li>`).join('');
        return `<tbody>
          <tr class="uk-track-row" data-track="${esc(track.track)}">
            <td><strong>${esc(track.track)}</strong> <span class="uk-expand">▸ pages</span></td>
            <td class="uk-num">${track.total || 0}</td>
            <td class="uk-num">${track.current || 0}</td>
            <td class="uk-num">${track.stale || 0}</td>
            <td class="uk-num">${track.missing || 0}</td>
            <td class="uk-num">${track.current_pct || 0}%</td>
            <td class="uk-num">${track.reviewed || 0}</td>
            <td class="uk-num">${track.reviewed_pct || 0}%</td>
            <td><div class="uk-mini">${ukMiniBar(track)}</div></td>
          </tr>
          <tr class="uk-pages-row" data-track="${esc(track.track)}" hidden>
            <td colspan="9" style="padding:0;border:0">
              <ul class="uk-page-list">${pages}</ul>
            </td>
          </tr>
        </tbody>`;
      }).join('');

      el.innerHTML = `
        <div class="uk-wrap">
          <h2 class="uk-headline"><span>${currentPct}%</span> current — goal 100%</h2>
          <div class="uk-subcounts">${current} current · ${stale} stale · ${missing} missing · ${total} pages · ${toGo} to go · calque-reviewed: ${reviewed} / ${total} (${reviewedPct}%)</div>
          <div class="uk-note">Currency measured by word-ratio (UK &lt; 60% of current EN = stale), not file existence.</div>
          <div class="uk-note">Calque review tracks human-reviewed calque fixes via frontmatter stamp; stale when page body changes after review.</div>
          <div class="uk-note">Nothing is excluded — every page will be translated. The AI tracks (ai / ai-ml-engineering / ai-history) and parts of platform / on-premises are translated LAST, after their English stabilizes, to avoid immediate re-staleness.</div>
          <div class="uk-table-wrap">
            <table class="uk-table">
              <thead>
                <tr>
                  <th>Track</th><th class="uk-num">Pages</th><th class="uk-num">Current</th>
                  <th class="uk-num">Stale</th><th class="uk-num">Missing</th><th class="uk-num">Current%</th>
                  <th class="uk-num">Calque rev.</th><th class="uk-num">Calque%</th><th>Progress</th>
                </tr>
              </thead>
              ${rows || '<tbody><tr><td colspan="9" class="empty-state">No tracks</td></tr></tbody>'}
            </table>
          </div>
        </div>`;

      for (const row of el.querySelectorAll('.uk-track-row')) {
        row.addEventListener('click', () => {
          const track = row.dataset.track;
          const pagesRow = el.querySelector(`.uk-pages-row[data-track="${track}"]`);
          if (!pagesRow) return;
          const open = pagesRow.hidden;
          pagesRow.hidden = !open;
          const marker = row.querySelector('.uk-expand');
          if (marker) marker.textContent = open ? '▾ pages' : '▸ pages';
        });
      }
    }

    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      const btn = $('#refresh');
      btn.classList.add('loading');
      try {
        const board = await fetchJson('/api/uk/board');
        renderUkBoard(board);
        setPollTs($('#last-updated'), board);
        $('#last-updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
      } catch (err) {
        console.error('UK board refresh failed:', err);
      } finally {
        refreshing = false;
        btn.classList.remove('loading');
      }
    }

    $('#refresh').addEventListener('click', refresh);
    refresh();
    setInterval(refresh, 60000);
"""


def render_uk_board_page_html() -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Ukrainian Translation - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
{_TOP_NAV_CSS}
{_UK_BOARD_PAGE_CSS}
{_poll_stale_css()}
  </style>
</head>
<body>
 {_render_top_nav("uk")}
{_render_page_chrome()}
<main class=\"main\">
  <div class=\"page-head\">
    <div>
      <h1 class=\"page-title\">Ukrainian Translation</h1>
      <div class=\"page-sub\">UK translation currency by word-ratio and calque-review coverage against current English sources.</div>
    </div>
    <div class=\"page-actions\">
      <span class=\"status-pill\" id=\"conn-status\"><span class=\"dot\"></span> Connected</span>
      <span class=\"status-pill\" id=\"last-updated\"></span>
      <button class=\"refresh-btn\" id=\"refresh\">Refresh</button>
    </div>
  </div>

  <div class=\"panel\">
    <div class=\"panel-header\">
      <div class=\"panel-title\">
        <span class=\"panel-icon\" style=\"background:var(--green-muted);color:var(--green);\">UK</span>
        Translation Board</div>
      <span class=\"panel-badge\" id=\"uk-badge\" style=\"background:var(--green-muted);color:var(--green);\">&nbsp;</span>
    </div>
    <div class=\"panel-body-flush\" id=\"uk-board\"><div class=\"empty-state\">Loading&hellip;</div></div>
  </div>
</main>
<script>
{_UK_BOARD_PAGE_JS}
</script>
{_render_poll_stale_script()}
</body>
</html>"""


_OPERATOR_PAGE_JS = """
    const $ = (sel) => document.querySelector(sel);

    async function fetchJson(url) {
      const r = await fetch(url);
      if (!r.ok) return { error: `HTTP ${r.status}`, url };
      return r.json();
    }

    function esc(s) {
      const d = document.createElement('div');
      d.textContent = String(s ?? '');
      return d.innerHTML;
    }

    function actionRows(briefing) {
      if (Array.isArray(briefing?.action_rows) && briefing.action_rows.length) {
        return briefing.action_rows;
      }
      const bag = [];
      for (const bucket of ['active', 'blocked', 'next']) {
        for (const label of (briefing?.actions?.[bucket] || [])) {
          bag.push({bucket, label, module_key: null, phase: null, reason: null, endpoint: null});
        }
      }
      return bag;
    }

    function renderOperator(briefing) {
      const alerts = briefing?.alerts || [];
      const focus = briefing?.focus || [];
      const blockers = briefing?.blockers || [];
      const alertItems = [
        ...blockers.map(s => `<li class="blocker">${esc(s)}</li>`),
        ...alerts.map(s => `<li class="alert">${esc(s)}</li>`),
      ];
      const focusItems = focus.map(s => `<li>${esc(s)}</li>`);
      $('#op-hero').innerHTML = `
        <div class="op-hero-block">
          <div class="op-hero-title">Alerts &amp; Blockers</div>
          ${alertItems.length ? `<ul class="op-hero-list">${alertItems.join('')}</ul>` : '<div class="op-hero-empty">None</div>'}
        </div>
        <div class="op-hero-block">
          <div class="op-hero-title">Focus</div>
          ${focusItems.length ? `<ul class="op-hero-list">${focusItems.join('')}</ul>` : '<div class="op-hero-empty">None</div>'}
        </div>`;

      const rowsSrc = actionRows(briefing);
      const renderRow = (r) => {
        const label = esc(r.label || '');
        const link = r.endpoint
          ? ` <a href="${esc(r.endpoint)}" title="${esc(r.endpoint)}" target="_blank" rel="noopener">[drill]</a>`
          : '';
        return `<li>${label}${link}</li>`;
      };
      const renderCol = (bucket) => {
        const rows = rowsSrc.filter(r => r.bucket === bucket);
        return rows.length ? rows.map(renderRow).join('') : '<li class="op-hero-empty">Nothing here</li>';
      };

      $('#op-now').innerHTML = renderCol('active');
      $('#op-blocked').innerHTML = renderCol('blocked');
      $('#op-next').innerHTML = renderCol('next');

      const counts = {active: 0, blocked: 0, next: 0};
      for (const r of rowsSrc) {
        if (counts[r.bucket] !== undefined) counts[r.bucket]++;
      }
      const total = counts.active + counts.blocked + counts.next;
      const badge = $('#op-badge');
      badge.textContent = total ? `${total} items` : 'Idle';
      if (counts.blocked) {
        badge.style.background = 'var(--red-muted)';
        badge.style.color = 'var(--red)';
      } else if (total) {
        badge.style.background = 'var(--accent-muted)';
        badge.style.color = 'var(--accent)';
      } else {
        badge.style.background = 'var(--green-muted)';
        badge.style.color = 'var(--green)';
      }
    }

    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      const btn = $('#refresh');
      btn.classList.add('loading');
      try {
        const briefing = await fetchJson('/api/briefing/session?compact=1');
        if (briefing.error) throw new Error(briefing.error);
        renderOperator(briefing);
        setPollTs($('#last-updated'), briefing);
        $('#last-updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
        const pill = $('#conn-status');
        pill.innerHTML = '<span class="dot"></span> Connected';
        pill.style.background = 'var(--green-muted)';
        pill.style.color = 'var(--green)';
      } catch (err) {
        const pill = $('#conn-status');
        pill.innerHTML = '<span class="dot"></span> Error';
        pill.style.background = 'var(--red-muted)';
        pill.style.color = 'var(--red)';
        console.error('Operator refresh failed:', err);
      } finally {
        refreshing = false;
        btn.classList.remove('loading');
      }
    }

    $('#refresh').addEventListener('click', refresh);
    refresh();
    setInterval(refresh, 60000);
"""


_PIPELINE_PANEL_JS = r"""
    const TRACK_LABEL = {
      'prerequisites': 'Prerequisites',
      'linux': 'Linux',
      'k8s': 'Kubernetes',
      'cloud': 'Cloud',
      'platform': 'Platform Engineering',
      'on-premises': 'On-Premises',
      'ai-ml-engineering': 'AI/ML Engineering',
      'other': 'Other',
    };

    function shortenKey(key) {
      return String(key || '').replace(/^src\/content\/docs\//, '').replace(/\.md$/, '');
    }

    function renderPipelinePanel(bodyId, badgeId, data, label) {
      const el = $(bodyId);
      const badge = $(badgeId);
      if (!data || data.error) {
        badge.textContent = 'Unknown';
        badge.style.background = 'var(--amber-muted)';
        badge.style.color = 'var(--amber)';
        el.innerHTML = `<div class="empty-state">${data?.error ? esc(data.error) : 'No data'}</div>`;
        return;
      }
      const counts = data.counts || {};
      const totalPending = (counts.pending_write || 0) + (counts.pending_review || 0) + (counts.pending_patch || 0);
      const dead = counts.dead_letter || 0;
      if (totalPending === 0 && dead === 0) {
        badge.textContent = 'Idle';
        badge.style.background = 'var(--green-muted)';
        badge.style.color = 'var(--green)';
      } else {
        const parts = [];
        if (totalPending) parts.push(`${totalPending} pending`);
        if (dead) parts.push(`${dead} dead`);
        badge.textContent = parts.join(' · ');
        badge.style.background = dead ? 'var(--red-muted)' : 'var(--amber-muted)';
        badge.style.color = dead ? 'var(--red)' : 'var(--amber)';
      }

      const done = counts.done ?? 0;
      const tracked = done + totalPending + dead + (counts.in_progress ?? 0);
      const conv = tracked > 0 ? (done / tracked * 100) : (data.convergence_rate ?? 0);
      let html = `
        <div class="queue-summary">
          <div class="queue-stat"><div class="queue-stat-val">${done}</div><div class="queue-stat-label">Done</div></div>
          <div class="queue-stat"><div class="queue-stat-val">${totalPending}</div><div class="queue-stat-label">Pending</div></div>
          <div class="queue-stat"><div class="queue-stat-val">${dead}</div><div class="queue-stat-label">Dead</div></div>
          <div class="queue-stat"><div class="queue-stat-val">${conv.toFixed(1)}%</div><div class="queue-stat-label">Converged</div></div>
        </div>`;

      const perTrack = data.per_track || [];
      const active = perTrack.filter(t => {
        const c = t.counts || {};
        return (c.pending_write || 0) + (c.pending_review || 0) + (c.pending_patch || 0) + (c.dead_letter || 0) > 0;
      });
      html += '<div class="queue-per-track">';
      if (active.length === 0) {
        html += `<div class="empty-state">All tracks idle</div>`;
      } else {
        for (const t of active) {
          const c = t.counts || {};
          const bits = [];
          if (c.pending_write) bits.push(`<span class="pill w">${c.pending_write}W</span>`);
          if (c.pending_review) bits.push(`<span class="pill r">${c.pending_review}R</span>`);
          if (c.pending_patch) bits.push(`<span class="pill p">${c.pending_patch}P</span>`);
          if (c.dead_letter) bits.push(`<span class="pill d">${c.dead_letter}D</span>`);
          html += `<div class="qpt-row">
            <span class="qpt-name">${esc(TRACK_LABEL[t.slug] || t.slug)}</span>
            <span class="qpt-status">${bits.join(' ')}</span>
          </div>`;
        }
      }
      html += '</div>';

      const topItems = [];
      for (const t of perTrack) {
        if (!t.modules) continue;
        for (const kind of ['dead_letter', 'pending_review', 'pending_write', 'pending_patch']) {
          for (const m of (t.modules[kind] || [])) {
            topItems.push({kind, path: m});
          }
        }
      }
      const kindLabel = {dead_letter: 'D', pending_review: 'R', pending_write: 'W', pending_patch: 'P'};
      if (topItems.length > 0) {
        const shown = topItems.slice(0, 6);
        html += `<div class="qpt-top">
          <div class="qpt-top-title">Top items (${shown.length} of ${topItems.length})</div>
          <ul class="qpt-top-list mono">
            ${shown.map(i => `<li><span class="qpt-top-kind ${kindLabel[i.kind].toLowerCase()}">${kindLabel[i.kind]}</span> ${esc(shortenKey(i.path))}</li>`).join('')}
          </ul>
        </div>`;
      }

      el.innerHTML = html;
    }
"""


def _fmt_duration(seconds: float | int | None) -> str:
    if seconds is None or seconds < 0:
        return "n/a"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    minutes = s // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h {minutes % 60}m"
    days = hours // 24
    return f"{days}d {hours % 24}h"


def _load_autopilot_v3_health(repo_root: Path, *, now_seconds: float | None = None) -> dict[str, Any]:
    heartbeat_path = repo_root / ".pipeline" / "v3" / "autopilot" / "heartbeat.json"
    now = time.time() if now_seconds is None else now_seconds
    if not heartbeat_path.exists():
        return {"exists": False, "up": False, "status": "Missing", "path": str(heartbeat_path)}
    try:
        data = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"exists": True, "up": False, "status": "Unreadable", "error": f"{type(exc).__name__}: {exc}"}
    ts = data.get("ts")
    age = now - float(ts) if isinstance(ts, int | float) else None
    up = age is not None and age <= 90
    return {
        "exists": True,
        "up": up,
        "status": "Up" if up else "Stale",
        "age_seconds": age,
        "pid": data.get("pid"),
        "uptime_seconds": data.get("uptime_s"),
        "path": str(heartbeat_path),
    }


def _autopilot_v3_badge(health: dict[str, Any]) -> str:
    return "Up" if health.get("up") else str(health.get("status") or "Down")


def _render_autopilot_v3_panel(repo_root: Path) -> str:
    health = _load_autopilot_v3_health(repo_root)
    up = bool(health.get("up"))
    badge_tone = "green" if up else "amber"
    status = html.escape(_autopilot_v3_badge(health))
    age = _fmt_duration(health.get("age_seconds"))
    uptime = _fmt_duration(health.get("uptime_seconds"))
    pid = html.escape(str(health.get("pid") or "n/a"))
    path = html.escape(str(health.get("path") or "n/a"))
    if health.get("error"):
        path = html.escape(str(health["error"]))
    return f"""
      <div class="panel" id="autopilot-v3-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="panel-icon" style="background:var(--teal-muted);color:var(--teal);">A</span>
            Autopilot v3 Health
          </div>
          <span class="panel-badge" id="autopilot-v3-badge" style="background:var(--{badge_tone}-muted);color:var(--{badge_tone});">{status}</span>
        </div>
        <div class="autopilot-grid" id="autopilot-v3-body">
          <div class="autopilot-kv"><div class="autopilot-label">Heartbeat age</div><div class="autopilot-value">{age}</div></div>
          <div class="autopilot-kv"><div class="autopilot-label">PID</div><div class="autopilot-value mono">{pid}</div></div>
          <div class="autopilot-kv"><div class="autopilot-label">Uptime</div><div class="autopilot-value">{uptime}</div></div>
          <div class="autopilot-kv"><div class="autopilot-label">Source</div><div class="autopilot-value mono" title="{path}">{path}</div></div>
        </div>
      </div>"""


def _find_quality_board_module(repo_root: Path, module_key: str) -> dict[str, Any] | None:
    board = build_quality_board(repo_root)
    rel = module_key[:-3] if module_key.endswith(".md") else module_key
    rel_file = f"{rel}.md"
    slug = _quality_board_slug_for_path(rel)
    for item in board.get("modules", []):
        if item.get("path") == rel_file or item.get("slug") == slug or item.get("module_key") == module_key:
            return item
    return None


def render_quality_board_page_html() -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Quality Board - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
{_TOP_NAV_CSS}
{_QUALITY_BOARD_PAGE_CSS}
{_poll_stale_css()}
  </style>
</head>
<body>
 {_render_top_nav("quality")}
{_render_page_chrome()}
<main class=\"main\">
  <div class=\"page-head\">
    <div>
      <h1 class=\"page-title\">Quality Board</h1>
      <div class=\"page-sub\">Module and book chapter review health, score bands, and gates.</div>
    </div>
    <div class=\"page-actions\">
      <span class=\"status-pill\" id=\"conn-status\"><span class=\"dot\"></span> Connected</span>
      <span class=\"status-pill\" id=\"last-updated\"></span>
      <button class=\"refresh-btn\" id=\"refresh\">Refresh</button>
    </div>
  </div>

  <div class=\"panel\">
    <div class=\"panel-header\">
      <div class=\"panel-title\">
        <span class=\"panel-icon\" style=\"background:var(--accent-muted);color:var(--accent);\">Q</span>
        Board</div>
      <span class=\"panel-badge\" id=\"qb-badge\" style=\"background:var(--accent-muted);color:var(--accent);\">&nbsp;</span>
    </div>
    <div class=\"panel-body-flush\" id=\"quality-board\"><div class=\"empty-state\">Loading&hellip;</div></div>
  </div>
</main>
<script>
{_QUALITY_BOARD_PAGE_JS}
</script>
{_render_poll_stale_script()}
</body>
</html>"""


def render_quality_module_not_found_page_html(module_key: str) -> str:
    safe_key = module_key.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Quality Module Not Found - KubeDojo Local Monitor</title>
  <style>
    :root {{ --bg:#0a0f1a; --surface-0:#111827; --surface-1:#1a2332; --text:#e5e7eb; --text-secondary:#9ca3af; --text-dim:#6b7280; --accent:#38bdf8; --accent-muted:rgba(56,189,248,0.12); --green-muted:rgba(74,222,128,0.12); --border:rgba(255,255,255,0.06); --radius-sm:8px; --radius:12px; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }}
{_TOP_NAV_CSS}
    .main {{ max-width: 920px; margin:0 auto; padding: 24px; }}
    .panel {{ background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); padding: 18px; }}
    .panel a {{ color:var(--accent); }}
  </style>
</head>
<body>
{_render_top_nav("quality")}
<main class=\"main\">
  <div class=\"panel\">
    <h1>Quality module not found</h1>
    <p>Could not locate quality data for <code>{safe_key}</code>.</p>
    <p><a href=\"/quality\">← Back to Quality Board</a></p>
  </div>
</main>
</body>
</html>"""


def render_quality_module_page_html(repo_root: Path, module_key: str) -> str | None:
    module = _find_quality_board_module(repo_root, module_key)
    if module is None:
        return None

    state = build_module_state(repo_root, module_key)
    rel = module_key[:-3] if module_key.endswith('.md') else module_key
    diagnostics = state.get("diagnostics") if isinstance(state.get("diagnostics"), list) else []
    orchestration = state.get("orchestration") if isinstance(state.get("orchestration"), dict) else {}
    v2_orchestration = orchestration.get("v2") if isinstance(orchestration.get("v2"), dict) else {}
    translation_orchestration = (
        orchestration.get("translation_v2") if isinstance(orchestration.get("translation_v2"), dict) else {}
    )
    module_state = v2_orchestration.get("latest_job") or {}
    translation_state = translation_orchestration.get("latest_job") or {}

    def _cls(item: Any) -> str:
        return str(item.get("severity")) if isinstance(item, dict) else ""

    def _text(item: Any) -> str:
        if not isinstance(item, dict):
            return ""
        parts = [
            str(item.get("summary") or ""),
            str(item.get("source") or ""),
            str(item.get("next_action") or ""),
        ]
        return " · ".join(part for part in parts if part)

    def _relative_path(raw_path: Any) -> str:
        if not raw_path:
            return ""
        # raw_path is built as repo_root / src/content/docs / <validated key>.md,
        # so it is already absolute under repo_root. Compute the display path
        # purely lexically — no .resolve()/filesystem access on a request-derived
        # value (CodeQL py/path-injection, alert #32) — and reject anything that
        # escapes repo_root.
        try:
            rel = Path(str(raw_path)).relative_to(repo_root)
        except ValueError:
            return ""
        if ".." in rel.parts:
            return ""
        return rel.as_posix()

    gate_items = []
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        s = _text(item)
        if not s:
            continue
        gate_items.append(f"<li class=\"{_cls(item)}\">{s}</li>")

    title = str(module.get("title") or "Unknown module").replace("<", "&lt;").replace(">", "&gt;")
    tracks = str(module.get("track") or "")
    status = str(module.get("status") or "unknown")
    score = module.get("score")
    score_text = f"{float(score):.1f}" if isinstance(score, int | float) else "n/a"
    english_path = _relative_path(state.get("english_path"))
    ukrainian_path = _relative_path(state.get("ukrainian_path"))
    source_links = (
        f'<a href="/{english_path}">english</a> / <a href="/{ukrainian_path}">ukrainian</a>'
        if english_path and ukrainian_path
        else (
            f'<a href="/{english_path}">english</a>'
            if english_path
            else "<span class=\"dim\">not synced</span>"
        )
    )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Quality · {title} - KubeDojo Local Monitor</title>
  <style>
{_TOP_NAV_CSS}
{_QUALITY_BOARD_PAGE_CSS}
  </style>
</head>
<body>
{_render_top_nav("quality")}
<main class=\"main\">
  <div class=\"page-head\">
    <div>
      <h1 class=\"page-title\">{title}</h1>
      <div class=\"page-sub\">{tracks} · {state.get('module_key', rel)}</div>
    </div>
    <div class=\"page-actions\"><a href=\"/quality\" class=\"back-link\">← Quality Board</a></div>
  </div>

  <section class=\"panel\">
    <div class=\"panel-header\">
      <div class=\"panel-title\">Quality summary</div>
      <span class=\"panel-badge\">{status}</span>
    </div>
    <div class=\"module-detail-summary\">
      <div class=\"module-kv\"><span class=\"module-kv-label\">Score</span><span class=\"module-kv-value\">{score_text}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">Revision banner</span><span class=\"module-kv-value\">{"pending" if module.get("revision_pending") else "clear"}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">Stage</span><span class=\"module-kv-value\">{module.get("stage", "none")}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">Review</span><span class=\"module-kv-value\">{module.get("latest_review_verdict") or "none"}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">Post-review queue</span><span class=\"module-kv-value\">{"yes" if module.get("in_post_review_queue") else "no"}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">V2 pipeline</span><span class=\"module-kv-value\">{module_state.get("phase", "none") or "n/a"} · {module_state.get("queue_state", "n/a")}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">Translation V2</span><span class=\"module-kv-value\">{translation_state.get("phase", "none") or "n/a"} · {translation_state.get("queue_state", "n/a")}</span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">API</span><span class=\"module-kv-value\"><a href=\"/api/module/{rel}/state\">module state</a> · <a href=\"/api/module/{rel}/orchestration/latest\">orchestration</a></span></div>
      <div class=\"module-kv\"><span class=\"module-kv-label\">Source</span><span class=\"module-kv-value\">{source_links}</span></div>
    </div>
  </section>

  <section class=\"panel\" style=\"margin-top:18px;\">
    <div class=\"panel-header\"><div class=\"panel-title\">Gates</div></div>
    <div class=\"panel-body\">
      <ul class=\"gate-list\">{''.join(gate_items) or '<li>No active gates</li>'}</ul>
    </div>
  </section>
</main>
</body>
</html>"""


def render_operator_page_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Operator - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
{_TOP_NAV_CSS}
{_OPERATOR_PAGE_CSS}
{_poll_stale_css()}
  </style>
</head>
<body>
  {_render_top_nav("operator")}
  {_render_page_chrome()}
  <main class="main">
    <div class="page-head">
      <div>
        <h1 class="page-title">Operator</h1>
        <div class="page-sub">Triage view for active work, blockers, and next actions.</div>
      </div>
      <div class="page-actions">
        <span class="status-pill" id="conn-status"><span class="dot"></span> Connected</span>
        <span class="last-updated" id="last-updated"></span>
        <button class="refresh-btn" id="refresh">Refresh</button>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-icon">O</span>
          Operator Triage
        </div>
        <span class="panel-badge" id="op-badge">&nbsp;</span>
      </div>
      <div class="op-hero" id="op-hero">
        <div class="op-hero-block">
          <div class="op-hero-title">Alerts</div>
          <div class="op-hero-empty">Loading&hellip;</div>
        </div>
        <div class="op-hero-block">
          <div class="op-hero-title">Focus</div>
          <div class="op-hero-empty">Loading&hellip;</div>
        </div>
      </div>
      <div class="op-cols">
        <div class="op-col">
          <h4 class="op-col-title now">Now</h4>
          <ul class="op-col-list" id="op-now"><li class="op-hero-empty">Loading&hellip;</li></ul>
        </div>
        <div class="op-col">
          <h4 class="op-col-title blocked">Blocked</h4>
          <ul class="op-col-list" id="op-blocked"><li class="op-hero-empty">Loading&hellip;</li></ul>
        </div>
        <div class="op-col">
          <h4 class="op-col-title next">Next</h4>
          <ul class="op-col-list" id="op-next"><li class="op-hero-empty">Loading&hellip;</li></ul>
        </div>
      </div>
    </div>
  </main>
  <script>
{_OPERATOR_PAGE_JS}
  </script>
{_render_poll_stale_script()}
</body>
</html>"""


def render_pipeline_page_html(repo_root: Path, *, tail: int = 30) -> str:
    tail = max(1, min(int(tail), 2000))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pipeline - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
{_TOP_NAV_CSS}
{_PIPELINE_PAGE_CSS}
{_poll_stale_css()}
  </style>
</head>
<body>
  {_render_top_nav("pipeline")}
  {_render_page_chrome()}
  <main class="main">
    <div class="page-head">
      <div>
        <h1 class="page-title">Pipeline</h1>
        <div class="page-sub">V2 queue state, autopilot v3 liveness, and recent pipeline events.</div>
      </div>
    </div>

    <section class="panel">
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-icon" style="background:var(--accent-muted);color:var(--accent);">P</span>
          V2 Pipeline
        </div>
        <span class="panel-badge" id="v2-badge"></span>
      </div>
      <div class="panel-body-flush" id="v2-body"><div class="empty-state">Loading&hellip;</div></div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-icon" style="background:var(--amber-muted);color:var(--amber);">E</span>
          Recent pipeline events
        </div>
        <span class="panel-badge" id="pipeline-events-badge">tail {tail}</span>
      </div>
      <div class="panel-body-flush" id="pipeline-events"><div class="empty-state">Loading&hellip;</div></div>
    </section>

    {_render_autopilot_v3_panel(repo_root)}
  </main>
  <script>
    const $ = (sel) => document.querySelector(sel);
    const EVENT_TAIL = {tail};

    async function fetchJson(url) {{
      const r = await fetch(url);
      if (!r.ok) return {{ error: `HTTP ${{r.status}}`, url }};
      return r.json();
    }}

    function esc(s) {{
      const d = document.createElement('div');
      d.textContent = String(s ?? '');
      return d.innerHTML;
    }}

{_PIPELINE_PANEL_JS}

    function formatRelTime(epoch, nowEpoch) {{
      if (!epoch) return 'n/a';
      const dt = Math.max(0, nowEpoch - epoch);
      if (dt < 60) return `${{dt}}s`;
      if (dt < 3600) return `${{Math.floor(dt / 60)}}m`;
      if (dt < 86400) return `${{Math.floor(dt / 3600)}}h`;
      return `${{Math.floor(dt / 86400)}}d`;
    }}

    function renderPipelineEvents(data) {{
      const el = $('#pipeline-events');
      const badge = $('#pipeline-events-badge');
      if (!data || data.error) {{
        badge.textContent = 'Unknown';
        el.innerHTML = `<div class="empty-state">${{esc(data?.error || 'No data')}}</div>`;
        return;
      }}
      const events = (data.events || []).slice(0, EVENT_TAIL);
      badge.textContent = `${{events.length}} shown`;
      if (events.length === 0) {{
        el.innerHTML = '<div class="empty-state">No recent pipeline events</div>';
        return;
      }}
      const now = Math.floor(Date.now() / 1000);
      el.innerHTML = `<ul class="event-list">${{events.map(ev => `
        <li>
          <span class="event-kind mono">${{esc(ev.type || ev.kind || 'event')}}</span>
          <span class="event-module mono">${{esc(shortenKey(ev.module_key || ''))}}</span>
          <span class="event-time">${{formatRelTime(ev.at, now)}} ago</span>
        </li>`).join('')}}</ul>`;
    }}

    async function loadPipelinePage() {{
      const [v2Status, events] = await Promise.all([
        fetchJson('/api/pipeline/v2/status'),
        fetchJson(`/api/pipeline/v2/events?limit=${{EVENT_TAIL}}`),
      ]);
      renderPipelinePanel('#v2-body', '#v2-badge', v2Status, 'V2 Pipeline');
      renderPipelineEvents(events);
      setPollTs($('#v2-badge'), v2Status);
    }}

    loadPipelinePage().catch(err => {{
      $('#v2-body').innerHTML = '<div class="empty-state">Pipeline data unavailable</div>';
      $('#pipeline-events').innerHTML = '<div class="empty-state">No recent pipeline events</div>';
      console.error('Pipeline page load failed:', err);
    }});
  </script>
{_render_poll_stale_script()}
</body>
</html>"""


def render_activity_page_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Activity - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
{_TOP_NAV_CSS}
{_ACTIVITY_PAGE_CSS}
{_ACTIVITY_FEED_CSS}
{_poll_stale_css()}
  </style>
</head>
<body>
  {_render_top_nav("activity")}
  {_render_page_chrome()}
  <main class="main">
    <div class="page-head">
      <div>
        <h1 class="page-title">Activity</h1>
        <div class="page-sub">Merged commits, pipeline events, and bridge messages from /api/activity.</div>
      </div>
    </div>

    <section class="panel">
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-icon" style="background:var(--amber-muted);color:var(--amber);">A</span>
          Activity feed
        </div>
        <div class="activity-tools">
          <select class="activity-select" id="activity-track-filter" aria-label="Track filter">
            <option value="">All tracks</option>
            <option value="fundamentals">Fundamentals</option>
            <option value="cloud">Cloud</option>
            <option value="certifications">Certifications</option>
            <option value="platform">Platform</option>
            <option value="other">Other</option>
          </select>
          <select class="activity-select" id="activity-agent-filter" aria-label="Agent filter">
            <option value="">All</option>
            <option value="claude">claude</option>
            <option value="codex">codex</option>
            <option value="gemini">gemini</option>
            <option value="grok">grok</option>
            <option value="deepseek">deepseek</option>
            <option value="qwen">qwen</option>
            <option value="cursor">cursor</option>
            <option value="composer">composer</option>
            <option value="autopilot">autopilot</option>
          </select>
          <span class="panel-badge" id="activity-badge">&nbsp;</span>
        </div>
      </div>
      <div class="panel-body-flush" id="activity-body">
        <div class="empty-state">Loading&hellip;</div>
      </div>
    </section>
  </main>
  <script>
{_ACTIVITY_PAGE_JS}
  </script>
{_render_poll_stale_script()}
</body>
</html>"""


def render_health_page_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Health - KubeDojo Local Monitor</title>
  {_design_system_link()}
  <style>
{_TOP_NAV_CSS}
{_HEALTH_PAGE_CSS}
{_poll_stale_css()}
  </style>
</head>
<body>
  {_render_top_nav("health")}
  {_render_page_chrome()}
  <main class="main">
    <div class="page-head">
      <div>
        <h1 class="page-title">Health</h1>
        <div class="page-sub">Operational triage for local services, attached worktrees, and missing-module drift.</div>
      </div>
    </div>

    <div class="health-grid">
      <section class="panel section-full" id="health-services-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="panel-icon" style="background:var(--green-muted);color:var(--green);">S</span>
            Runtime Services
          </div>
          <span class="panel-badge" id="svc-badge"></span>
        </div>
        <div class="panel-body-flush">
          <div class="svc-grid" id="services"></div>
        </div>
      </section>

      <section class="panel" id="health-worktrees-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="panel-icon" style="background:var(--amber-muted);color:var(--amber);">W</span>
            Worktrees
          </div>
          <span class="panel-badge" id="worktrees-badge"></span>
        </div>
        <div class="panel-body-flush" id="worktrees"><div class="empty-state">Loading&hellip;</div></div>
      </section>

      <section class="panel" id="health-missing-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="panel-icon" style="background:var(--amber-muted);color:var(--amber);">M</span>
            Missing / Dead Letters
          </div>
          <span class="panel-badge" id="missing-badge"></span>
        </div>
        <div class="panel-body" id="missing"><div class="empty-state">Loading&hellip;</div></div>
      </section>
    </div>
  </main>
  <script>
{_HEALTH_PAGE_JS}
  </script>
{_render_poll_stale_script()}
</body>
</html>"""


def render_dashboard_html(repo_root: Path = REPO_ROOT, *, issue_number: int = DEFAULT_FEEDBACK_ISSUE) -> str:
    autopilot = _load_autopilot_v3_health(repo_root)
    autopilot_label = html.escape(_autopilot_v3_badge(autopilot))
    benchmarks = build_latest_benchmarks(repo_root)
    benchmark_latest = benchmarks.get("latest") if isinstance(benchmarks.get("latest"), dict) else {}
    benchmark_ledger = (
        benchmark_latest.get("ledger") if isinstance(benchmark_latest.get("ledger"), dict) else {}
    )
    benchmark_date = html.escape(str(benchmark_latest.get("date") or "n/a"))
    benchmark_cells = html.escape(
        f"{benchmark_ledger.get('cells_scored', 0)}/{benchmark_ledger.get('cells_total', 0)}"
    )
    benchmark_models = html.escape(str(benchmark_ledger.get("models", 0)))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KubeDojo Local Monitor</title>
  <link rel="stylesheet" href="/static/design-system.css" />
  <style>
    .header {{ position:sticky; top:var(--topnav-h,45px); z-index:50; border-bottom:1px solid var(--border); background:rgba(10,15,26,0.96); backdrop-filter:blur(12px); }}
    .header-inner {{ max-width:1180px; margin:0 auto; padding:18px 24px; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
    .header-brand {{ display:flex; align-items:center; gap:12px; min-width:0; }}
    .logo {{ width:32px; height:32px; border-radius:8px; background:linear-gradient(135deg,var(--accent),var(--teal)); display:flex; align-items:center; justify-content:center; color:#0a0f1a; font-weight:800; }}
    .title {{ font-size:16px; font-weight:700; }}
    .sub {{ color:var(--text-dim); font-size:12px; }}
    .header-right {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
    .status-pill,.panel-badge {{ display:inline-flex; align-items:center; gap:6px; padding:3px 9px; border-radius:999px; font-size:11px; font-weight:700; background:var(--green-muted); color:var(--green); white-space:nowrap; }}
    .dot {{ width:6px; height:6px; border-radius:50%; background:currentColor; }}
    .last-updated {{ color:var(--text-dim); font-size:11px; }}
    .refresh-btn {{ border:1px solid var(--border); background:var(--surface-1); color:var(--text); border-radius:var(--radius-sm); padding:7px 12px; font-size:12px; font-weight:700; cursor:pointer; }}
    .refresh-btn:hover {{ background:var(--surface-2); }}
    .refresh-btn.loading {{ opacity:.6; pointer-events:none; }}
    .main {{ max-width:1180px; margin:0 auto; padding:24px; }}
    .summary-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
    .summary-shell {{ background:var(--surface-0); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }}
    .summary-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; padding:13px 16px; border-bottom:1px solid var(--border); }}
    .summary-title {{ display:flex; align-items:center; gap:9px; font-size:13px; font-weight:700; }}
    .summary-icon {{ width:20px; height:20px; border-radius:6px; display:inline-flex; align-items:center; justify-content:center; font-size:11px; font-weight:800; }}
    .op-summary-card,.quality-summary-card,.pipeline-summary-card,.activity-summary-card,.channels-summary-card,.benchmarks-summary-card,.artifacts-summary-card,.decisions-summary-card {{ display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; gap:14px; min-height:78px; padding:15px 16px; color:var(--text); text-decoration:none; }}
    .op-summary-card,.pipeline-summary-card,.benchmarks-summary-card {{ grid-template-columns:repeat(3,minmax(82px,1fr)) auto; }}
    .op-summary-card:hover,.quality-summary-card:hover,.pipeline-summary-card:hover,.activity-summary-card:hover,.channels-summary-card:hover,.benchmarks-summary-card:hover,.artifacts-summary-card:hover,.decisions-summary-card:hover {{ background:rgba(255,255,255,0.02); }}
    .op-summary-value,.pipeline-summary-value,.summary-value {{ display:block; font-size:23px; line-height:1; font-weight:800; font-variant-numeric:tabular-nums; }}
    .op-summary-label,.pipeline-summary-label,.summary-label {{ display:block; margin-top:5px; color:var(--text-dim); font-size:10px; font-weight:800; letter-spacing:0; text-transform:uppercase; }}
    .quality-summary-title {{ display:block; color:var(--text-dim); font-size:10px; font-weight:800; letter-spacing:0; text-transform:uppercase; margin-bottom:6px; }}
    .quality-summary-counts,.summary-copy,.health-summary-copy {{ display:block; color:var(--text-secondary); font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .activity-summary-list {{ list-style:none; margin:0; padding:0; min-width:0; }}
    .activity-summary-item {{ display:grid; grid-template-columns:18px 58px minmax(0,1fr); gap:8px; align-items:center; padding:2px 0; font-size:12px; color:var(--text-secondary); }}
    .activity-summary-src {{ width:18px; height:18px; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; font-weight:800; font-size:10px; background:var(--amber-muted); color:var(--amber); }}
    .activity-summary-src.commit {{ background:var(--accent-muted); color:var(--accent); }}
    .activity-summary-src.pipeline_event {{ background:var(--teal-muted); color:var(--teal); }}
    .activity-summary-time {{ color:var(--text-dim); font-size:11px; white-space:nowrap; }}
    .activity-summary-text {{ min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .op-summary-link,.quality-summary-link,.pipeline-summary-link,.activity-summary-link,.summary-link {{ color:var(--accent); font-size:13px; font-weight:800; white-space:nowrap; }}
    @media (max-width:860px) {{ .summary-grid {{ grid-template-columns:1fr; }} .op-summary-card,.pipeline-summary-card,.benchmarks-summary-card {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .op-summary-link,.pipeline-summary-link {{ justify-self:start; }} }}
    @media (max-width:640px) {{ .main {{ padding:16px; }} .header-inner {{ padding:16px; align-items:flex-start; flex-direction:column; }} .op-summary-card,.quality-summary-card,.pipeline-summary-card,.activity-summary-card,.channels-summary-card,.benchmarks-summary-card,.artifacts-summary-card,.decisions-summary-card {{ grid-template-columns:1fr; }} .quality-summary-counts,.summary-copy,.health-summary-copy {{ white-space:normal; }} }}
    {_poll_stale_css()}
  </style>
</head>
<body>
  {_render_top_nav("home")}
  {_render_page_chrome()}
  <header class="header">
    <div class="header-inner">
      <div class="header-brand"><div class="logo">K</div><div><div class="title">KubeDojo Local Monitor</div><div class="sub">Overview cards · details live on dedicated routes</div></div></div>
      <div class="header-right"><span class="status-pill" id="conn-status"><span class="dot"></span> Connected</span><span class="last-updated" id="last-updated"></span><button class="refresh-btn" id="refresh">Refresh</button></div>
    </div>
  </header>

  <main class="main">
    <div class="summary-grid">
      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--accent-muted);color:var(--accent);">O</span>Operator</div><span class="panel-badge" id="op-badge">&nbsp;</span></div>
        <a class="op-summary-card" href="/operator"><span><span class="op-summary-value" id="op-active-count">0</span><span class="op-summary-label">Active</span></span><span><span class="op-summary-value" id="op-blocked-count">0</span><span class="op-summary-label">Blocked</span></span><span><span class="op-summary-value" id="op-next-count">0</span><span class="op-summary-label">Next</span></span><span class="op-summary-link">View &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--accent-muted);color:var(--accent);">Q</span>Quality</div><span class="panel-badge" id="quality-summary-badge">&nbsp;</span></div>
        <a class="quality-summary-card" href="/quality"><span><span class="quality-summary-title">Aggregate quality</span><span class="quality-summary-counts" id="quality-summary-counts">Loading&hellip;</span></span><span class="quality-summary-link">View board &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--accent-muted);color:var(--accent);">P</span>Pipeline</div><span class="panel-badge" id="pipeline-summary-badge">&nbsp;</span></div>
        <a class="pipeline-summary-card" href="/pipeline"><span><span class="pipeline-summary-value" id="pipeline-queue-depth">0</span><span class="pipeline-summary-label">Queue</span></span><span><span class="pipeline-summary-value" id="pipeline-inflight">0</span><span class="pipeline-summary-label">Active</span></span><span><span class="pipeline-summary-value">{autopilot_label}</span><span class="pipeline-summary-label">Autopilot</span></span><span class="pipeline-summary-link">View pipeline &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--teal-muted);color:var(--teal);">B</span>Benchmarks</div><span class="panel-badge">Latest</span></div>
        <a class="benchmarks-summary-card" href="/benchmarks"><span><span class="summary-value">{benchmark_cells}</span><span class="summary-label">Cells scored</span></span><span><span class="summary-value">{benchmark_models}</span><span class="summary-label">Models</span></span><span><span class="summary-value">{benchmark_date}</span><span class="summary-label">Latest run</span></span><span class="summary-link">View benchmarks &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--amber-muted);color:var(--amber);">A</span>Activity</div><span class="panel-badge" id="activity-summary-state">&nbsp;</span></div>
        <a class="activity-summary-card" href="/activity"><ul class="activity-summary-list" id="activity-summary-items"><li class="activity-summary-item"><span class="activity-summary-src">A</span><span class="activity-summary-time">now</span><span class="activity-summary-text">Loading&hellip;</span></li></ul><span class="activity-summary-link">View activity &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--green-muted);color:var(--green);">H</span>Health</div><span class="panel-badge" id="health-summary-state">&nbsp;</span></div>
        <a class="op-summary-card health-summary-card" href="/health"><span class="health-summary-copy" id="health-summary-copy">Services: 0 running / 0 total &middot; Worktrees: 0 &middot; Missing: 0</span><span class="op-summary-link">View health &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--accent-muted);color:var(--accent);">A</span>Artifacts</div><span class="panel-badge">Browse</span></div>
        <a class="artifacts-summary-card" href="/artifacts"><span><span class="summary-copy">HTML and Markdown orchestrator artifacts, handoffs, audits, and reports.</span></span><span class="summary-link">View artifacts &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--amber-muted);color:var(--amber);">D</span>Decisions</div><span class="panel-badge">Cards</span></div>
        <a class="decisions-summary-card" href="/decisions"><span><span class="summary-copy">Decision cards with pending/stale status and git lineage.</span></span><span class="summary-link">View decisions &rarr;</span></a>
      </section>

      <section class="summary-shell">
        <div class="summary-head"><div class="summary-title"><span class="summary-icon" style="background:var(--teal-muted);color:var(--teal);">C</span>Channels</div><span class="panel-badge" id="channels-summary-badge">Open</span></div>
        <a class="channels-summary-card" href="/channels"><span><span class="summary-copy" id="channels-summary-copy">Bridge conversations and live deliberation threads.</span></span><span class="summary-link">View channels &rarr;</span></a>
      </section>

    </div>
  </main>

  <script>
    const ISSUE = {issue_number};
    const $ = (sel) => document.querySelector(sel);
    async function fetchJson(url) {{ const r = await fetch(url); return r.ok ? r.json() : {{error:`HTTP ${{r.status}}`, url}}; }}
    function esc(s) {{ const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }}
    function tone(el, name) {{ const map = {{green:['var(--green-muted)','var(--green)'], amber:['var(--amber-muted)','var(--amber)'], red:['var(--red-muted)','var(--red)'], accent:['var(--accent-muted)','var(--accent)'], teal:['var(--teal-muted)','var(--teal)']}}; [el.style.background, el.style.color] = map[name] || map.accent; }}
    function shortenKey(key) {{ return String(key || '').replace('src/content/docs/', '').replace(/\\.md$/, ''); }}
    function relTime(epoch, now) {{ const dt = Math.max(0, now - epoch); if (dt < 60) return `${{dt}}s`; if (dt < 3600) return `${{Math.floor(dt/60)}}m`; if (dt < 86400) return `${{Math.floor(dt/3600)}}h`; return `${{Math.floor(dt/86400)}}d`; }}

    function renderOperator(briefing) {{
      const rows = Array.isArray(briefing?.action_rows) && briefing.action_rows.length ? briefing.action_rows : [];
      const counts = {{active:0, blocked:0, next:0}};
      if (rows.length) rows.forEach(r => {{ if (counts[r.bucket] !== undefined) counts[r.bucket]++; }});
      else for (const k of Object.keys(counts)) counts[k] = (briefing?.actions?.[k] || []).length;
      $('#op-active-count').textContent = counts.active; $('#op-blocked-count').textContent = counts.blocked; $('#op-next-count').textContent = counts.next;
      const total = counts.active + counts.blocked + counts.next;
      const b = $('#op-badge'); b.textContent = total ? `${{total}} items` : 'Idle'; tone(b, counts.blocked ? 'red' : total ? 'accent' : 'green');
    }}

    function renderQuality(data) {{
      const b = $('#quality-summary-badge'), c = $('#quality-summary-counts');
      if (!data || data.error) {{ b.textContent = 'Unavailable'; c.textContent = 'No quality data'; tone(b, 'red'); return; }}
      const t = data.totals || {{}};
      const left = (t.needs_rewrite || 0) + (t.needs_review || 0) + (t.shipped_unreviewed || 0) + (t.both || 0);
      b.textContent = `${{t.done || 0}} / ${{t.total || 0}} done`; tone(b, left ? 'amber' : 'green');
      c.textContent = `rewrite=${{t.needs_rewrite || 0}} · review=${{t.needs_review || 0}} · shipped=${{t.shipped_unreviewed || 0}} · both=${{t.both || 0}}`;
    }}

    function renderPipeline(data) {{
      const b = $('#pipeline-summary-badge');
      if (!data || data.error) {{ b.textContent = 'Unknown'; tone(b, 'amber'); return; }}
      const c = data.counts || {{}};
      const q = (c.pending_write || 0) + (c.pending_review || 0) + (c.pending_patch || 0);
      $('#pipeline-queue-depth').textContent = q; $('#pipeline-inflight').textContent = c.in_progress || 0;
      b.textContent = q || c.in_progress || c.dead_letter ? `${{q}} queued · ${{c.in_progress || 0}} active · ${{c.dead_letter || 0}} dead` : 'Idle';
      tone(b, c.dead_letter ? 'red' : q || c.in_progress ? 'amber' : 'green');
    }}

    function renderActivity(data) {{
      const b = $('#activity-summary-state'), el = $('#activity-summary-items');
      if (!data || data.error) {{ b.textContent = 'Unknown'; el.innerHTML = '<li class="activity-summary-item"><span class="activity-summary-src">!</span><span class="activity-summary-time">n/a</span><span class="activity-summary-text">No data</span></li>'; tone(b, 'amber'); return; }}
      const counts = data.source_counts || {{}};
      b.textContent = [counts.commit && `${{counts.commit}} commits`, counts.pipeline_event && `${{counts.pipeline_event}} events`, counts.bridge_message && `${{counts.bridge_message}} msgs`].filter(Boolean).join(' / ') || 'Quiet';
      const now = data.generated_at || Math.floor(Date.now() / 1000);
      const abbr = {{commit:'C', pipeline_event:'P', bridge_message:'B'}};
      const rows = (data.items || []).slice(0, 3).map(it => `<li class="activity-summary-item"><span class="activity-summary-src ${{esc(it.source)}}">${{abbr[it.source] || '?'}}</span><span class="activity-summary-time">${{relTime(it.at, now)}} ago</span><span class="activity-summary-text">${{esc(it.source === 'pipeline_event' ? shortenKey(it.module_key) + ' ' + (it.kind || '') : (it.summary || it.kind || ''))}}</span></li>`).join('');
      el.innerHTML = rows || '<li class="activity-summary-item"><span class="activity-summary-src">A</span><span class="activity-summary-time">n/a</span><span class="activity-summary-text">No recent activity</span></li>';
    }}

    function renderHealth(briefing, missingData) {{
      const b = $('#health-summary-state'), line = $('#health-summary-copy');
      const services = briefing?.services || {{}}, workspace = briefing?.workspace || {{}}, missing = missingData || {{}};
      const running = services.running ?? 0, total = services.total ?? running + (services.stopped ?? 0) + (services.stale ?? 0);
      const missingCount = missing.active_exact?.missing ?? missing.active_exact?.modules?.length ?? 0;
      line.textContent = `Services: ${{running}} running / ${{total}} total · Worktrees: ${{workspace.worktrees_total ?? 0}} · Missing: ${{missingCount}}`;
      const attention = (services.stale ?? 0) + (services.stopped ?? 0) + missingCount;
      b.textContent = attention ? `${{attention}} needs attention` : 'Healthy'; tone(b, attention ? 'amber' : 'green');
    }}

    async function refresh() {{
      const btn = $('#refresh'); btn.classList.add('loading');
      try {{
        const [missing, pipelineStatus, briefing, qualityBoard, activitySummary] = await Promise.all([
          fetchJson('/api/missing-modules/status'), fetchJson('/api/pipeline/v2/status'), fetchJson('/api/briefing/session?compact=1'), fetchJson('/api/quality/board'), fetchJson('/api/activity?limit=3')
        ]);
        renderOperator(briefing); renderQuality(qualityBoard); renderPipeline(pipelineStatus); renderActivity(activitySummary); renderHealth(briefing, missing);
        setPollTs($('#last-updated'), briefing);
        $('#last-updated').textContent = `Updated ${{new Date().toLocaleTimeString()}}`;
        const pill = $('#conn-status'); pill.innerHTML = '<span class="dot"></span> Connected'; tone(pill, 'green');
      }} catch (err) {{ const pill = $('#conn-status'); pill.innerHTML = '<span class="dot"></span> Error'; tone(pill, 'red'); console.error('Dashboard refresh failed:', err); }}
      finally {{ btn.classList.remove('loading'); }}
    }}
    $('#refresh').addEventListener('click', refresh); refresh(); setInterval(refresh, 60000);
  </script>
{_render_poll_stale_script()}
</body>
</html>"""



# ============================================================
# Agent orientation: /api/briefing/session + /api/schema
# ============================================================


# Keyed by resolved path so different repos' STATUS.md files never alias.
_STATUS_MD_CACHE: dict[str, dict[str, Any]] = {}
_STATUS_MD_CACHE_LOCK = threading.Lock()


def _live_status_path(repo_root: Path) -> Path:
    """Resolve the LIVE status index: ``.agent/STATUS.md`` when present.

    Session handoffs + the live status index are LOCAL agent state, not
    curriculum (user directive s190b, memory
    ``feedback_handoff_commit_direct_no_worktree``). The live per-session
    index lives in the gitignored ``.agent/STATUS.md`` so ending a session
    never dirties git; the tracked ``STATUS.md`` keeps the durable sections
    (Active policies, historical index snapshot) and is updated via PR only.
    Falls back to the tracked file when no live copy exists (fresh clones,
    CI, worktrees).
    """
    live = repo_root / ".agent" / "STATUS.md"
    if live.is_file():
        return live
    return repo_root / "STATUS.md"


def _parse_status_md(status_path: Path) -> dict[str, Any]:
    """Extract focus + blockers + a light summary from STATUS.md.

    Caches by absolute path + mtime to keep briefing cheap and to stay
    safe when multiple repos share one Python process.
    """
    try:
        mtime = status_path.stat().st_mtime
    except OSError:
        return {"focus": [], "blockers": [], "exists": False}

    cache_key = str(status_path.resolve())
    with _STATUS_MD_CACHE_LOCK:
        entry = _STATUS_MD_CACHE.get(cache_key)
        if entry is not None and entry["mtime"] == mtime:
            return entry["data"]

    try:
        text = status_path.read_text(encoding="utf-8")
    except OSError:
        return {"focus": [], "blockers": [], "exists": False}

    focus: list[str] = []
    blockers: list[str] = []
    section = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if heading.startswith("todo"):
                section = "todo"
            elif heading.startswith("blocker"):
                section = "blocker"
            else:
                section = None
            continue
        if section == "todo":
            # Only collect unchecked items: - [ ] ...
            if line.lstrip().startswith("- [ ]"):
                bullet = line.lstrip()[5:].strip()
                if bullet and len(focus) < 10:
                    focus.append(bullet)
        elif section == "blocker":
            if line.lstrip().startswith("- "):
                bullet = line.lstrip()[2:].strip()
                if bullet and len(blockers) < 10:
                    blockers.append(bullet)

    data = {"focus": focus, "blockers": blockers, "exists": True}
    with _STATUS_MD_CACHE_LOCK:
        _STATUS_MD_CACHE[cache_key] = {"mtime": mtime, "data": data}
    return data


_AI_HISTORY_PARTS: tuple[dict[str, Any], ...] = (
    {"part": 1, "name": "The Mathematical Foundations", "range": (1, 5), "issue": 399},
    {"part": 2, "name": "The Analog Dream & Digital Blank Slate", "range": (6, 10), "issue": 400},
    {"part": 3, "name": "The Birth of Symbolic AI & Early Optimism", "range": (11, 16), "issue": 401},
    {"part": 4, "name": "The First Winter & The Shift to Knowledge", "range": (17, 23), "issue": 402},
    {"part": 5, "name": "The Mathematical Resurrection", "range": (24, 31), "issue": 403},
    {"part": 6, "name": "The Rise of Data & Distributed Compute", "range": (32, 40), "issue": 404},
    {"part": 7, "name": "The Deep Learning Revolution & GPU Coup", "range": (41, 49), "issue": 405},
    {"part": 8, "name": "The Transformer, Scale & Open Source", "range": (50, 58), "issue": 406},
    {"part": 9, "name": "The Product Shock & Physical Limits", "range": (59, 72), "issue": 407},
)

_BOOK_NUMERIC_KEYS = frozenset({"part", "chapter", "green_claims", "yellow_claims", "red_claims"})


def _parse_status_yaml(path: Path) -> dict[str, Any]:
    """Minimal tolerant parser for chapter status.yaml top-level scalars.

    The codebase deliberately avoids a yaml dependency. Chapter status
    files use a small subset: ``key: value`` pairs plus an occasional
    ``notes: |`` block scalar. We only need the top-level scalars
    (status, owner, part, chapter, review_state, last_updated, and the
    Green/Yellow/Red counts), so a line-based parser is sufficient.

    Returns an empty dict if the file is missing or unreadable.
    """
    out: dict[str, Any] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out

    for raw in text.splitlines():
        # Indented lines belong to nested dicts or block scalars; skip.
        if raw.startswith((" ", "\t")):
            continue
        line = raw.rstrip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # Strip a trailing `# comment` when the value is unquoted. We don't
        # support `#` inside values (none of our chapter scalars need it).
        if value and not value.startswith(('"', "'")):
            hash_idx = value.find(" #")
            if hash_idx >= 0:
                value = value[:hash_idx].rstrip()
        # Block-scalar markers (`|`, `>`) and bare empty values mean the
        # value is on subsequent indented lines, which we skip.
        if value in ("", "|", ">", "|-", ">-"):
            continue
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if key in _BOOK_NUMERIC_KEYS:
            try:
                out[key] = int(value)
                continue
            except ValueError:
                pass
        out[key] = value
    return out


def build_book_briefing(repo_root: Path) -> dict[str, Any]:
    """Aggregate status across all AI-history book chapters.

    Scans ``docs/research/ai-history/chapters/ch-NN-<slug>/status.yaml``
    and groups chapters into the 9 Parts. Each chapter entry carries
    number, slug, status, owner, review_state, last_updated, and (when
    present) Green/Yellow/Red claim counts. Each part rolls up status
    counts and the set of owners observed.

    Cheap to compute (68 small files, no parsing dependencies) so this
    is not background-refreshed; it just reads on every call.
    """
    chapters_dir = repo_root / "docs" / "research" / "ai-history" / "chapters"
    chapters_by_num: dict[int, dict[str, Any]] = {}
    if chapters_dir.is_dir():
        for entry in sorted(chapters_dir.iterdir()):
            if not entry.is_dir() or not entry.name.startswith("ch-"):
                continue
            stem = entry.name[len("ch-") :]
            num_part, _, slug_tail = stem.partition("-")
            try:
                ch_num = int(num_part)
            except ValueError:
                continue
            data = _parse_status_yaml(entry / "status.yaml")
            chapters_by_num[ch_num] = {
                "chapter": ch_num,
                "slug": entry.name,
                "title_slug": slug_tail,
                "status": data.get("status"),
                "owner": data.get("owner"),
                "review_state": data.get("review_state"),
                "green_claims": data.get("green_claims"),
                "yellow_claims": data.get("yellow_claims"),
                "red_claims": data.get("red_claims"),
                "last_updated": data.get("last_updated"),
                "prose_state": data.get("prose_state"),
                "reader_aids": data.get("reader_aids"),
                "lifecycle_updated": data.get("lifecycle_updated"),
            }

    parts_out: list[dict[str, Any]] = []
    total_status: dict[str, int] = {}
    total_published = 0
    total_aids_landed = 0
    for spec in _AI_HISTORY_PARTS:
        lo, hi = spec["range"]
        chapters = [chapters_by_num[n] for n in range(lo, hi + 1) if n in chapters_by_num]
        rollup: dict[str, int] = {}
        owners_seen: set[str] = set()
        published_count = 0
        aids_landed_count = 0
        for ch in chapters:
            status_value = ch.get("status") or "unknown"
            rollup[status_value] = rollup.get(status_value, 0) + 1
            total_status[status_value] = total_status.get(status_value, 0) + 1
            owner = ch.get("owner")
            if owner:
                owners_seen.add(owner)
            if ch.get("prose_state") == "published_on_main":
                published_count += 1
                total_published += 1
            if ch.get("reader_aids") == "landed":
                aids_landed_count += 1
                total_aids_landed += 1
        parts_out.append(
            {
                "part": spec["part"],
                "name": spec["name"],
                "chapter_range": [lo, hi],
                "tracking_issue": spec["issue"],
                "owners_seen": sorted(owners_seen),
                "chapter_count": len(chapters),
                "published_count": published_count,
                "aids_landed_count": aids_landed_count,
                "status_rollup": rollup,
                "chapters": chapters,
            }
        )

    expected = sum(spec["range"][1] - spec["range"][0] + 1 for spec in _AI_HISTORY_PARTS)
    return {
        "epic_issue": 394,
        "chapter_count": sum(p["chapter_count"] for p in parts_out),
        "expected_chapter_count": expected,
        "published_count": total_published,
        "aids_landed_count": total_aids_landed,
        "total_status_rollup": total_status,
        "parts": parts_out,
    }


def _recent_commits(repo_root: Path, limit: int = 5) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["git", "log", f"-n{limit}", "--pretty=format:%h%x09%s"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if result.returncode != 0:
        return []
    commits: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if "\t" in line:
            sha, subject = line.split("\t", 1)
        else:
            sha, subject = line[:8], line[8:].lstrip()
        commits.append({"sha": sha, "subject": subject})
    return commits


def _pipeline_summary_safe(repo_root: Path) -> dict[str, Any] | None:
    """Return pipeline v2 summary. None if DB absent; error dict if broken.

    Shape map from ``pipeline_v2.cli._build_status_report``:
      - ``counts``: {pending_review, pending_write, pending_patch,
                     in_progress, dead_letter, done}
      - ``needs_human_count``: dead-letter count after resolution
      - ``total_modules``, ``convergence_rate``, ``flapping_count``

    ``queue_head`` collapses those into actionable buckets callers can
    promote into briefing actions:
      - ``ready`` = pending_review + pending_write + pending_patch
      - ``in_progress`` = ``counts.in_progress``
      - ``dead_letter`` = ``counts.dead_letter`` (a.k.a. needs-human)
    """
    db_path = repo_root / ".pipeline" / "v2.db"
    if not db_path.exists():
        return None
    try:
        from pipeline_v2.cli import _build_status_report as build_v2_status_report
        report = build_v2_status_report(db_path)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(report, dict):
        return {"error": "non_dict_report"}

    counts = report.get("counts") or {}
    ready = sum(
        int(counts.get(k, 0))
        for k in ("pending_review", "pending_write", "pending_patch")
    )
    queue_head = {
        "ready": ready,
        "in_progress": int(counts.get("in_progress", 0)),
        "dead_letter": int(counts.get("dead_letter", 0)),
    }
    # Briefing is a cold-start hot path; keep the payload compact.
    # Full ``counts`` / ``convergence_rate`` live on
    # /api/pipeline/v2/status; here we expose only the actionable
    # summary an agent needs before deciding what to do.
    return {
        "total_modules": report.get("total_modules"),
        "needs_human_count": report.get("needs_human_count"),
        "queue_head": queue_head,
    }


def _git_hygiene_signals(
    repo_root: Path,
    worktree: dict[str, Any],
    worktrees: dict[str, Any],
) -> list[str]:
    """Alerts for git state that rots silently until someone trips over it.

    Complements build_git_cleanup_report (prunable branches/worktrees) by
    catching the three drift patterns that have actually bitten us:
    forgotten stashes, detached-HEAD worktrees, and uncommitted files on
    main (pipeline or pilot residuals leak here).
    """
    out: list[str] = []

    try:
        r = subprocess.run(
            ["git", "stash", "list", "--format=%ct"],
            cwd=repo_root, capture_output=True, text=True, check=False, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            now = time.time()
            ages = [
                now - int(line.strip())
                for line in r.stdout.splitlines()
                if line.strip().isdigit()
            ]
            ancient = sum(1 for a in ages if a > 7 * 86400)
            stale = sum(1 for a in ages if a > 86400) - ancient
            if ancient:
                out.append(
                    f"git hygiene: {ancient} stash(es) older than 7 days "
                    "— inspect with `git stash list --date=relative` or drop"
                )
            elif stale:
                out.append(
                    f"git hygiene: {stale} stash(es) older than 24h "
                    "— forgotten stashes become landmines"
                )
    except (OSError, subprocess.TimeoutExpired):
        pass

    detached_paths = [
        wt.get("path")
        for wt in (worktrees.get("worktrees") or [])
        if wt.get("detached")
    ]
    if detached_paths:
        shown = ", ".join(str(p) for p in detached_paths[:3] if p)
        more = f" (+{len(detached_paths) - 3} more)" if len(detached_paths) > 3 else ""
        out.append(
            f"git hygiene: {len(detached_paths)} worktree(s) in detached HEAD"
            + (f": {shown}{more}" if shown else "")
        )

    if (
        worktree.get("ok")
        and worktree.get("branch") == "main"
        and worktree.get("dirty")
    ):
        counts = worktree.get("counts") or {}
        total = counts.get("total") or 0
        out.append(
            f"git hygiene: {total} uncommitted file(s) on main "
            "— pipeline/pilot residuals sometimes land here; verify before committing"
        )

    return out


def _count_review_backfill_pending(repo_root: Path) -> dict[str, Any]:
    chapters_root = repo_root / "docs" / "research" / "ai-history" / "chapters"
    pending: list[str] = []
    for status_path in sorted(chapters_root.glob("ch-*/status.yaml")):
        try:
            text = status_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"(?m)^  backfill_pending: true$", text):
            pending.append(status_path.parent.name)
    return {"count": len(pending), "chapters": pending[:5]}


def build_session_briefing(repo_root: Path) -> dict[str, Any]:
    """Compact control-plane snapshot for agent orientation.

    Target: ≤ 2K tokens. Designed to be the *first* call a fresh agent
    makes, replacing the usual ``cat STATUS.md + git log + ls`` crawl.
    See issue #258.
    """
    status_md = _parse_status_md(_live_status_path(repo_root))
    worktree = build_worktree_status(repo_root)
    worktrees = build_worktrees_list(repo_root)
    services = build_runtime_services_status(repo_root)
    commits = _recent_commits(repo_root, limit=5)
    pipeline = _pipeline_summary_safe(repo_root)
    review_backfill = _count_review_backfill_pending(repo_root)

    alerts: list[str] = []
    if services.get("stale", 0):
        alerts.append(f"{services['stale']} stale pid file(s) — process exited without cleanup")
    if isinstance(pipeline, dict) and "error" in pipeline:
        alerts.append(f"pipeline v2 status unavailable: {pipeline['error']}")

    # Phase C: surface stuck pipeline jobs and critical rubric scores so
    # agents see high-signal issues without polling additional endpoints.
    try:
        stuck = build_pipeline_stuck(repo_root)
    except Exception:  # noqa: BLE001
        stuck = None
    if isinstance(stuck, dict) and stuck.get("exists"):
        leased = stuck.get("stuck_leased_count", 0)
        in_state = stuck.get("stuck_in_state_count", 0)
        dead_letter_stuck = stuck.get("dead_lettered_count", 0)
        stale_worker_count = stuck.get("stale_workers_count", 0)
        if leased:
            alerts.append(f"{leased} job(s) with expired/stale lease — worker may have crashed")
        if in_state:
            alerts.append(f"{in_state} job(s) stuck in-flight with no recent event")
        if dead_letter_stuck:
            alerts.append(
                f"{dead_letter_stuck} module(s) dead-lettered (unresolved) — need human triage"
            )
        if stale_worker_count:
            alerts.append(
                f"{stale_worker_count} worker(s) holding leases but silent — possible zombie"
            )

    try:
        quality = build_quality_scores(repo_root)
    except Exception:  # noqa: BLE001
        quality = None
    try:
        reviews = build_reviews_index(repo_root, fact_check_status="unverified")
    except Exception:  # noqa: BLE001
        reviews = None
    critical_quality: list[str] = []
    if isinstance(quality, dict) and quality.get("exists"):
        if quality.get("critical_count"):
            alerts.append(
                f"{quality['critical_count']} module(s) at critical rubric score (<2.0)"
            )
        critical_quality = [
            f"{m['module']} [{m['track']}] score {m['score']}"
            for m in (quality.get("critical") or [])[:5]
        ]
    if isinstance(reviews, dict) and reviews.get("count"):
        alerts.append(f"{reviews['count']} module(s) with unverified fact claims")

    # Git hygiene rot: only alert when the pile crosses a threshold, so
    # the single-leftover worktree after a merge doesn't spam the panel.
    try:
        cleanup = build_git_cleanup_report(repo_root)
        cb = cleanup.get("counts", {}).get("branches", 0)
        cw = cleanup.get("counts", {}).get("worktrees", 0)
        if cb >= 5 or cw >= 2:
            alerts.append(
                f"git hygiene: {cb} prunable branch(es), {cw} prunable worktree(s) "
                "— run `git cleanup-merged` (see /api/git/cleanup)"
            )
    except Exception:  # noqa: BLE001
        pass

    try:
        alerts.extend(_git_hygiene_signals(repo_root, worktree, worktrees))
    except Exception:  # noqa: BLE001
        pass

    # Action-oriented triage lists. Agents ask "what should I touch"
    # not "what's the global state"; the lists below answer that in
    # the same call as the briefing.
    #
    # ``active``  — what is CURRENTLY owned / in flight. Read-only from
    #               a deciding-agent's view; you don't grab these.
    # ``blocked`` — things the pipeline can't make progress on without
    #               a human or a re-enqueue.
    # ``next``    — things ready to pick up right now.
    #
    # Structured row shape per ``action_rows[]``:
    #   ``{bucket, label, module_key, phase, reason, endpoint}``
    # The dashboard reads this directly. Agents that want the old flat
    # list view still get ``actions.{active,blocked,next}`` (derived
    # from ``action_rows`` below) plus ``top_modules[]``, both preserved
    # for backward compat.
    action_rows: list[dict[str, Any]] = []
    top_modules: list[dict[str, Any]] = []

    def _add_row(
        bucket: str,
        label: str,
        *,
        module_key: str | None = None,
        phase: str | None = None,
        reason: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        action_rows.append({
            "bucket": bucket,
            "label": label,
            "module_key": module_key,
            "phase": phase,
            "reason": reason,
            "endpoint": endpoint,
        })
        # ``top_modules[]`` keeps its historical shape (module_key may
        # be None for repo-level rows like ``ready_queue``).
        if reason and endpoint:
            top_modules.append({
                "module_key": module_key,
                "phase": phase,
                "reason": reason,
                "endpoint": endpoint,
            })

    try:
        leases = build_pipeline_leases(repo_root)
    except Exception:  # noqa: BLE001
        leases = None
    if isinstance(leases, dict) and leases.get("exists"):
        for lease in (leases.get("active") or [])[:5]:
            secs = lease.get("seconds_to_expiry")
            mk = lease.get("module_key")
            _add_row(
                "active",
                f"{lease.get('leased_by','?')} → {mk or '?'} "
                f"({lease.get('phase','?')}, {secs}s left)",
                module_key=mk,
                phase=lease.get("phase"),
                reason="active_lease",
                endpoint=f"/api/module/{mk}/state" if mk else None,
            )

    if isinstance(stuck, dict) and stuck.get("exists"):
        for job in (stuck.get("stuck_leased") or [])[:5]:
            mk = job.get("module_key")
            _add_row(
                "blocked",
                f"{mk or '?'} stale lease (held by {job.get('leased_by','?')})",
                module_key=mk,
                phase=job.get("phase"),
                reason="stale_lease",
                endpoint=f"/api/pipeline/v2/events?module={mk}" if mk else None,
            )
        for job in (stuck.get("stuck_in_state") or [])[:5]:
            mk = job.get("module_key")
            _add_row(
                "blocked",
                f"{mk or '?'} stuck in {job.get('queue_state','?')}",
                module_key=mk,
                phase=job.get("phase"),
                reason="stuck_in_state",
                endpoint=f"/api/pipeline/v2/events?module={mk}" if mk else None,
            )

    if isinstance(reviews, dict) and reviews.get("exists"):
        for review in (reviews.get("reviews") or [])[:5]:
            mk = review.get("module_key")
            _add_row(
                "blocked",
                f"{mk or '?'} has unverified fact claim",
                module_key=mk,
                reason="fact_check_unverified",
                endpoint=f"/api/reviews?module={mk}" if mk else None,
            )

    if isinstance(pipeline, dict) and pipeline.get("queue_head"):
        queue_head = pipeline["queue_head"] or {}
        ready = int(queue_head.get("ready") or 0)
        if ready:
            _add_row(
                "next",
                f"{ready} job(s) ready to pick up in pipeline v2",
                reason="ready_queue",
                endpoint="/api/pipeline/v2/status",
            )
        dead_letter = int(queue_head.get("dead_letter") or 0)
        if dead_letter:
            _add_row(
                "blocked",
                f"{dead_letter} job(s) in dead-letter — needs human or re-enqueue",
                reason="pipeline_dead_letter",
                endpoint="/api/pipeline/v2/stuck",
            )

    if review_backfill["count"]:
        _add_row(
            "next",
            f"{review_backfill['count']} AI History chapter(s) need review backfill",
            reason="ai_history_review_backfill",
            endpoint="docs/research/ai-history/REVIEW_COVERAGE.md",
        )

    actions_active = [r["label"] for r in action_rows if r["bucket"] == "active"]
    actions_blocked = [r["label"] for r in action_rows if r["bucket"] == "blocked"]
    actions_next = [r["label"] for r in action_rows if r["bucket"] == "next"]

    return {
        "snapshot": {
            "generated_at": time.time(),
            "generator": "local_api.build_session_briefing",
            "version": 1,
        },
        "workspace": {
            "primary_branch": worktree.get("branch") if worktree.get("ok") else None,
            "dirty": worktree.get("dirty") if worktree.get("ok") else None,
            "counts": worktree.get("counts") if worktree.get("ok") else None,
            "ahead": worktree.get("ahead") if worktree.get("ok") else None,
            "behind": worktree.get("behind") if worktree.get("ok") else None,
            "worktrees_total": worktrees.get("count", 0),
            "worktrees": [
                {
                    "path": wt.get("path"),
                    "branch": wt.get("branch"),
                    "detached": wt.get("detached", False),
                }
                for wt in (worktrees.get("worktrees") or [])
            ],
        },
        "services": {
            "running": services["running"],
            "stopped": services["stopped"],
            "stale": services["stale"],
            "total": services["total"],
        },
        "pipelines": {"v2": pipeline},
        "recent_commits": commits,
        "focus": status_md.get("focus", []),
        "blockers": status_md.get("blockers", []),
        "alerts": alerts,
        "critical_quality": critical_quality,
        "review_backfill": review_backfill,
        "actions": {
            # ``active`` — currently owned / in flight (read-only).
            # ``blocked`` — needs human or re-enqueue.
            # ``next`` — ready to pick up.
            "active": actions_active,
            "blocked": actions_blocked,
            "next": actions_next,
        },
        # Structured twin of ``actions.*``. Each row has {bucket,
        # label, module_key, phase, reason, endpoint}. Dashboards and
        # UI consumers read this directly — scanning ``label`` strings
        # to infer drill-down endpoints is fragile and misroutes when
        # the same module appears in multiple buckets (Codex Phase D
        # review round 3).
        "action_rows": action_rows,
        "top_modules": top_modules,
        "next_reads": [
            {"rel": "schema", "endpoint": "/api/schema", "desc": "Full endpoint index"},
            {"rel": "status", "endpoint": "/api/status/summary", "desc": "Full repo status"},
            {"rel": "pipeline", "endpoint": "/api/pipeline/v2/status", "desc": "Pipeline v2 queue"},
            {"rel": "translation", "endpoint": "/api/translation/v2/status", "desc": "UK translation queue"},
            {"rel": "services", "endpoint": "/api/runtime/services", "desc": "Runtime pids / ports"},
            {"rel": "worktrees", "endpoint": "/api/git/worktrees", "desc": "All attached worktrees"},
            {"rel": "module-state", "endpoint": "/api/module/{key}/state", "desc": "Per-module EN+UK+lab+frontmatter"},
            {"rel": "module-orchestration", "endpoint": "/api/module/{key}/orchestration/latest", "desc": "Per-module latest pipeline job/event"},
        ],
        "links": {
            "status_md": "STATUS.md",
            "claude_md": "CLAUDE.md",
            "dashboard": "/",
        },
    }


def _compact_briefing(briefing: dict[str, Any]) -> dict[str, Any]:
    """Drop fields that aren't actionable for agents to shave tokens further.

    Keeps ``actions`` and ``top_modules`` — those are THE actionable
    fields — and drops navigation aids (``next_reads``, ``links``) and
    the full worktrees list (``worktrees_total`` is enough).
    """
    compact = dict(briefing)
    compact.pop("next_reads", None)
    compact.pop("links", None)
    if "workspace" in compact and isinstance(compact["workspace"], dict):
        ws = dict(compact["workspace"])
        ws.pop("worktrees", None)
        compact["workspace"] = ws
    return compact


def build_orient(repo_root: Path) -> dict[str, Any]:
    """Maximum-signal, minimum-token orientation: what to do RIGHT NOW.

    Projects the session briefing into a single ``primary`` action +
    up to 3 ``alternatives`` + raw ``blockers`` / ``alerts``. Reach for
    ``/api/briefing/session?compact=1`` when the full snapshot is needed.
    """
    briefing, freshness = get_or_build_session_briefing(repo_root)
    rows = briefing.get("action_rows") or []
    blockers = briefing.get("blockers") or []
    alerts = briefing.get("alerts") or []
    workspace = briefing.get("workspace") or {}
    snapshot = briefing.get("snapshot") or {}

    def _row_to_action(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": row.get("bucket") or "next",
            "headline": row.get("label"),
            "module_key": row.get("module_key"),
            "endpoint": row.get("endpoint"),
            "reason": row.get("reason"),
            "phase": row.get("phase"),
        }

    if rows:
        primary = _row_to_action(rows[0])
        alternatives = [_row_to_action(r) for r in rows[1:4]]
    else:
        primary = {
            "action": "idle",
            "headline": "queue empty — propose work or check blockers for unblock candidates",
            "module_key": None,
            "endpoint": None,
            "reason": None,
            "phase": None,
        }
        alternatives = []

    return {
        "version": 1,
        "primary": primary,
        "alternatives": alternatives,
        "blockers": blockers,
        "alerts": alerts,
        "workspace_dirty": bool(workspace.get("dirty")),
        "freshness_state": (freshness or {}).get("freshness_state"),
        "generated_at": snapshot.get("generated_at"),
    }


# Registry keyed by resolved ``repo_root`` so multiple repos sharing one
# Python process (test suite, multi-repo servers) never cross-contaminate.
_SESSION_BRIEFING_SNAPSHOTS: dict[str, BackgroundSnapshot] = {}
_SESSION_BRIEFING_SNAPSHOT_LOCK = threading.Lock()


def get_or_build_session_briefing(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (briefing, freshness_meta). Uses a background snapshot so
    the briefing endpoint is always cheap."""
    key = str(repo_root.resolve())
    with _SESSION_BRIEFING_SNAPSHOT_LOCK:
        snap = _SESSION_BRIEFING_SNAPSHOTS.get(key)
        if snap is None:
            snap = _register_snapshot(
                f"briefing_session::{key}",
                interval_seconds=15.0,
                builder=lambda: build_session_briefing(repo_root),
            )
            # Prime synchronously on the first request so the first caller
            # sees real data instead of ``freshness_state=refreshing``.
            snap.refresh_blocking()
            snap.start()
            _SESSION_BRIEFING_SNAPSHOTS[key] = snap
    payload, freshness = snap.get()
    if payload is None:
        # Degraded path — build synchronously once.
        payload = build_session_briefing(repo_root)
    return payload, freshness


# ---- /api/schema ----


def build_api_schema() -> dict[str, Any]:
    """Machine-readable endpoint index. Lets agents discover the API
    without reading this 1.7K-LOC file."""
    return {
        "version": 1,
        "conventions": {
            "errors": 'JSON envelope: {"error": "<code>", ...optional context}.',
            "cache": "Weak ETag returned on cacheable responses; send If-None-Match to get 304.",
            "compact": "/api/briefing/session supports ?compact=1 to drop non-actionable fields.",
            "freshness": "Background-refreshed endpoints embed a 'freshness' dict with freshness_state and stale_seconds.",
        },
        "endpoints": [
            {"path": "/", "desc": "HTML dashboard", "content_type": "text/html"},
            {"path": "/artifacts", "desc": "Browseable HTML and Markdown artifact index", "content_type": "text/html", "query": ["include=research", "include_research=1"]},
            {
                "path": "/artifacts/{rel-path}",
                "desc": "Static HTML/assets and server-rendered Markdown from approved artifact directories",
                "content_type": "text/html or asset MIME type",
            },
            {"path": "/quality", "desc": "Full-quality board and per-module summary table", "content_type": "text/html"},
            {"path": "/pipeline", "desc": "Pipeline v2 queue, recent events, and autopilot v3 health", "content_type": "text/html"},
            {"path": "/benchmarks", "desc": "Calibration benchmark dashboard", "content_type": "text/html"},
            {"path": "/activity", "desc": "Activity feed with client-side track and agent filters", "content_type": "text/html"},
            {"path": "/health", "desc": "Runtime services, worktrees, and missing-module operational health", "content_type": "text/html"},
            {
                "path": "/healthz",
                "desc": "Liveness probe with repo-root inspection. ok=false when repo_root is not the primary checkout or .pids/api.pid references a dead/unreadable process.",
                "fields": ["ok", "repo_root", "primary_repo_root", "warnings"],
            },
            {"path": "/api/schema", "desc": "This document"},
            {
                "path": "/api/state/manifest",
                "desc": "Pointer-only cold-start state index grouped by purpose",
                "content_type": "application/json",
            },
            {
                "path": "/api/orient",
                "desc": "Single primary action + up to 3 alternatives + blockers/alerts. Punch-line orientation derived from the session briefing.",
                "content_type": "application/json",
            },
            {"path": "/api/artifacts", "desc": "JSON index of HTML and Markdown artifacts served by /artifacts. Research category omitted by default for performance; opt in with ?include=research or ?include_research=1.", "query": ["include=research", "include_research=1"]},
            {
                "path": "/api/briefing/session",
                "desc": "Agent cold-start orientation snapshot. First call for fresh agents.",
                "query": ["compact=1"],
                "freshness": "background-refreshed every 15s",
            },
            {
                "path": "/api/session/current",
                "desc": "Latest session handoff with render/raw URLs plus up to 10 predecessors",
                "content_type": "application/json",
            },
            {
                "path": "/api/benchmarks/latest",
                "desc": "Latest calibration benchmark report, predecessor reports, ledger coverage counts, and render staleness",
                "content_type": "application/json",
            },
            {
                "path": "/api/briefing/book",
                "desc": "AI-history book chapter status rollup. Scans chapters/ch-NN-*/status.yaml and groups by Part (1-9). Each part includes status_rollup, owners_seen, tracking_issue, and a per-chapter list with Green/Yellow/Red counts when present.",
            },
            {"path": "/api/status/summary", "desc": "Repo status (fast)"},
            {"path": "/api/missing-modules/status", "desc": "Modules missing from nav/sidebar"},
            {"path": "/api/activity/recent", "desc": "Recent commits, pipeline events, bridge messages, watched issue (grouped by source)"},
            {
                "path": "/api/activity",
                "desc": "Merged chronological feed (commits + pipeline events + bridge messages), newest-first",
                "query": [
                    "since=<Unix-epoch seconds | ISO-8601> (default: 24 h ago)",
                    "limit=... (default 50, max 500)",
                ],
            },
            {"path": "/api/navigation/status", "desc": "Top-level route coverage and candidate-stale index pages"},
            {"path": "/api/delivery/status", "desc": "Build freshness and site-health status"},
            {
                "path": "/api/tracks/readiness",
                "desc": "Per-track, per-section production-readiness grid (cleared/source_accepted/in_flight/dead_letter/not_yet_enqueued)",
            },
            {
                "path": "/api/runtime/services",
                "desc": "Runtime services (pids, uptime, ports) plus repo-root inspection.",
                "fields": ["running", "stopped", "stale", "total", "services", "repo"],
                "repo": {
                    "fields": ["repo_root", "primary_repo_root", "process_cwd", "warnings"],
                    "desc": (
                        "inspect_repo_root() output: repo_root is the served checkout; "
                        "primary_repo_root is git common-dir parent (null when git unavailable); "
                        "process_cwd is os.getcwd(); warnings when repo_root != primary, "
                        "cwd is under .worktrees/, or .pids/api.pid is stale/unreadable."
                    ),
                },
            },
            {"path": "/api/build/run", "desc": "Spawn `npm run build` in the background", "method": "POST"},
            {"path": "/api/build/status", "desc": "Build job status + tail + warning diff", "query": ["job_id=..."]},
            {"path": "/api/pipeline/v2/status", "desc": "Pipeline v2 queue + per-track"},
            {
                "path": "/api/translation/v2/status",
                "desc": "UK translation queue",
                "query": ["section=...", "freshness=1 (slow git walk)"],
            },
            {
                "path": "/api/translation/v2/enqueue",
                "desc": "Enqueue done modules from quality board into translation queue",
                "query": ["from_quality=done", "dry_run=1"],
            },
            {"path": "/api/labs/status", "desc": "Labs summary"},
            {"path": "/api/ztt/status", "desc": "Zero-to-Terminal pilot status"},
            {"path": "/api/git/worktree", "desc": "Dirty entries in the PRIMARY repo only"},
            {"path": "/api/git/worktrees", "desc": "All attached worktrees (plural)"},
            {"path": "/api/git/cleanup", "desc": "Prunable local branches + worktrees (merged or gone-upstream). Run 'git cleanup-merged' to act."},
            {
                "path": "/api/gh/issues",
                "desc": "Cached GitHub issue list for agent orientation",
                "query": ["state=open|closed|all (default open)", "limit=... (default 50, max 200)"],
            },
            {
                "path": "/api/gh/issues/{n}",
                "desc": "Single GitHub issue with the last 5 comments",
            },
            {
                "path": "/api/gh/prs",
                "desc": "Cached GitHub pull request list for agent orientation",
                "query": ["state=open|closed|merged|all (default open)", "limit=... (default 50, max 200)"],
            },
            {
                "path": "/api/gh/prs/{n}",
                "desc": "Single GitHub pull request with the last 5 comments and mergeable state",
            },
            {"path": "/api/issue-watch/{n}", "desc": "Single watched GH issue state"},
            {"path": "/api/module/{key}/state", "desc": "Per-module EN+UK+lab+frontmatter+diagnostics"},
            {"path": "/api/module/{key}/orchestration/latest", "desc": "Per-module latest pipeline job+event"},
            {"path": "/api/module/{key}/lease", "desc": "Current pipeline lease for one module"},
            {"path": "/api/pipeline/leases", "desc": "Active pipeline leases (ordered by expiry)"},
            {
                "path": "/api/pipeline/v2/events",
                "desc": "Pipeline v2 event timeline",
                "query": [
                    "module=...",
                    "since_seconds=... (Unix epoch seconds; matches v2.db unit)",
                    "limit=... (max 2000)",
                ],
            },
            {
                "path": "/api/pipeline/v2/stuck",
                "desc": "Stuck/stalled jobs + dead-lettered modules + zombie-worker roll-up (stale_workers[])",
                "query": ["threshold_seconds=... (default 3600)"],
            },
            {
                "path": "/api/reviews",
                "desc": "Review audit index (omit query) or single-module log (?module=...)",
                "query": ["module=...", "fact_check_status=verified|unverified|failed|none"],
            },
            {
                "path": "/api/bridge/messages",
                "desc": ".bridge/messages.db tail",
                "query": ["since=<ISO-8601>", "limit=... (max 500)"],
            },
            {"path": "/api/channels", "desc": "List deliberation channels with thread event rollups"},
            {
                "path": "/api/channel/{thread_id}/events",
                "desc": "Channel thread event timeline",
                "query": ["since_event_id=..."],
            },
            {"path": "/decisions", "desc": "Decision index with lineage counts", "content_type": "text/html"},
            {"path": "/decisions/{filename}", "desc": "Plain decision markdown renderer", "content_type": "text/html"},
            {"path": "/api/decisions", "desc": "List decision files with status and lineage counts"},
            {"path": "/api/decisions/pending", "desc": "Pending/stale decision count for cold-start agents"},
            {"path": "/api/decision/{filename}/lineage", "desc": "Decision lineage scanner result"},
            {"path": "/api/search", "desc": "FTS5 search across channel messages and decision cards"},
            {"path": "/api/quality/scores", "desc": "Live heuristic rubric scores from current English module files"},
            {
                "path": "/api/quality/board",
                "desc": "Per-module status grid (done / needs_rewrite / needs_review / both / in_flight) joining heuristic scores, pipeline state, revision banners, post-review queue, and review verdicts",
            },
            {
                "path": "/api/quality/upgrade-plan",
                "desc": "Upgrade queue derived from rubric scores for #180 (4/5) or #181 (5/5)",
                "query": ["target=4.0|5.0"],
            },
            {"path": "/api/citations/status", "desc": "Citation gate coverage and missing-source queue by track/module"},
            {
                "path": "/api/388/batches",
                "desc": "List of #388 dispatcher batches parsed from logs/388_*.jsonl. Each entry has state (in_flight|complete|errored), counts, current_module, started_at/ended_at.",
            },
            {
                "path": "/api/388/batch/{log_stem}",
                "desc": "Single #388 batch detail (full event timeline + held_prs roll-up). Stem is the log filename without .jsonl, e.g. 388_day3_bucket1_2026-05-02.",
            },
            {"path": "/api/cache/stats", "desc": "Response-cache introspection"},
        ],
    }


def render_channels_index_html() -> str:
    return _CHANNEL_ROUTES.render_channels_index_html(
        top_nav_css=_TOP_NAV_CSS,
        render_top_nav_fn=_render_top_nav,
    )


def render_channel_thread_html(thread_id: str) -> str:
    return _CHANNEL_ROUTES.render_channel_thread_html(
        thread_id,
        top_nav_css=_TOP_NAV_CSS,
        render_top_nav_fn=_render_top_nav,
    )


def route_request(repo_root: Path, raw_path: str) -> tuple[int, Any, str]:
    parsed = urlsplit(raw_path)
    path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query)

    if path.startswith("/static/"):
        return serve_static_file(repo_root, path[len("/static/"):])
    if path in {"/", "/dashboard"}:
        return 200, render_dashboard_html(repo_root), "text/html; charset=utf-8"
    if path == "/operator":
        return 200, render_operator_page_html(), "text/html; charset=utf-8"
    if path == "/artifacts":
        return 200, render_artifacts_index_html(repo_root, query), "text/html; charset=utf-8"
    if path.startswith("/artifacts/"):
        return serve_artifact_file(repo_root, path[len("/artifacts/"):], query)
    if path == "/quality":
        return 200, render_quality_board_page_html(), "text/html; charset=utf-8"
    if path == "/uk":
        return 200, render_uk_board_page_html(), "text/html; charset=utf-8"
    if path.startswith("/quality/"):
        module_key = _validate_module_key(repo_root, unquote(path[len("/quality/"):]).strip("/"))
        if not module_key:
            return 400, {"error": "invalid_module_key"}, "application/json; charset=utf-8"
        html = render_quality_module_page_html(repo_root, module_key)
        if html is None:
            return 404, render_quality_module_not_found_page_html(module_key), "text/html; charset=utf-8"
        return 200, html, "text/html; charset=utf-8"
    if path == "/quality-board":
        return 301, "/quality", "text/plain; charset=utf-8"
    if path == "/pipeline":
        try:
            tail = int(query.get("tail", ["30"])[0])
        except (TypeError, ValueError):
            tail = 30
        return 200, render_pipeline_page_html(repo_root, tail=tail), "text/html; charset=utf-8"
    if path == "/benchmarks":
        return 200, _render_benchmarks_page(repo_root), "text/html; charset=utf-8"
    if path == "/activity":
        return 200, render_activity_page_html(), "text/html; charset=utf-8"
    if path == "/health":
        return 200, render_health_page_html(), "text/html; charset=utf-8"
    if path == "/agents":
        from agent_telemetry_page import render_agents_page_html
        return 200, render_agents_page_html(
            top_nav=_render_top_nav("agents"),
            nav_css=_TOP_NAV_CSS,
            ds_link=_design_system_link(),
        ), "text/html; charset=utf-8"
    if path == "/api/telemetry/agents":
        from agent_telemetry import build_agent_telemetry
        since_raw = query.get("since", [None])[0]
        since_val = None
        if since_raw:
            try:
                since_val = int(since_raw)
            except (TypeError, ValueError):
                since_val = None
        return 200, build_agent_telemetry(repo_root, since=since_val), "application/json; charset=utf-8"
    if path == "/headroom":
        from headroom_stats_page import render_headroom_stats_page_html

        return 200, render_headroom_stats_page_html(
            top_nav=_render_top_nav("headroom"),
            nav_css=_TOP_NAV_CSS,
            ds_link=_design_system_link(),
        ), "text/html; charset=utf-8"
    if path == "/telemetry":
        from module_build_telemetry_page import render_module_builds_page_html

        return 200, render_module_builds_page_html(
            top_nav=_render_top_nav("telemetry"),
            nav_css=_TOP_NAV_CSS,
            ds_link=_design_system_link(),
        ), "text/html; charset=utf-8"
    if path == "/api/headroom/stats":
        import urllib.request as _hr_u
        import os as _hr_os

        _hr_host = _hr_os.environ.get("HEADROOM_HOST", "127.0.0.1")
        _hr_port = _hr_os.environ.get("HEADROOM_PORT", "8787")
        _hr_url = f"http://{_hr_host}:{_hr_port}/stats"
        try:
            with _hr_u.urlopen(_hr_url, timeout=3) as _hr_resp:
                _hr_raw = json.loads(_hr_resp.read().decode("utf-8"))
            _hr_payload = {
                "ok": True,
                "url": _hr_url,
                "summary": _hr_raw.get("summary", {}),
                "agent_usage": _hr_raw.get("agent_usage", {}),
            }
        except Exception as _hr_exc:  # noqa: BLE001 - graceful proxy-down state
            _hr_payload = {"ok": False, "url": _hr_url, "error": f"{type(_hr_exc).__name__}: {_hr_exc}"}
        return 200, _hr_payload, "application/json; charset=utf-8"
    if path == "/api/telemetry/module-builds":
        from telemetry_store import build_module_build_payload

        track_raw = query.get("track", [None])[0]
        slug_raw = query.get("slug", [None])[0]
        swarm_raw = query.get("swarm_used", [None])[0]
        limit_raw = query.get("limit", ["100"])[0]
        swarm_used = None
        if swarm_raw is not None:
            swarm_used = str(swarm_raw).strip().lower() in {"1", "true", "yes"}
        try:
            limit_val = int(limit_raw)
        except (TypeError, ValueError):
            limit_val = 100
        return 200, build_module_build_payload(
            repo_root,
            track=track_raw,
            slug=slug_raw,
            swarm_used=swarm_used,
            limit=limit_val,
        ), "application/json; charset=utf-8"
    if path.startswith("/api/telemetry/module-builds/"):
        from telemetry_store import build_module_build_detail_payload

        remainder = path[len("/api/telemetry/module-builds/") :].strip("/")
        if not remainder or "/" not in remainder:
            return 404, {"error": "not_found", "path": path}, "application/json; charset=utf-8"
        track_part, slug_part = remainder.rsplit("/", 1)
        limit_raw = query.get("limit", ["20"])[0]
        try:
            limit_val = int(limit_raw)
        except (TypeError, ValueError):
            limit_val = 20
        return 200, build_module_build_detail_payload(
            repo_root,
            track=track_part,
            slug=slug_part,
            limit=limit_val,
        ), "application/json; charset=utf-8"
    if path == "/api/telemetry/tool-timings":
        from telemetry_store import build_tool_timing_payload

        window_raw = query.get("window", ["1h"])[0] or "1h"
        tool_raw = query.get("tool", [None])[0]
        return 200, build_tool_timing_payload(
            repo_root,
            window=str(window_raw),
            tool=tool_raw,
        ), "application/json; charset=utf-8"
    if path == "/api/telemetry/runtime/usage":
        from runtime_usage import build_runtime_usage_payload

        days_raw = query.get("days", ["7"])[0]
        agent_raw = query.get("agent", [None])[0]
        task_class_raw = query.get("task_class", [None])[0]
        try:
            days_val = int(days_raw)
        except (TypeError, ValueError):
            days_val = 7
        return 200, build_runtime_usage_payload(
            repo_root,
            days=days_val,
            agent=agent_raw or None,
            task_class=task_class_raw or None,
        ), "application/json; charset=utf-8"
    if path == "/api/telemetry/runtime/recent":
        from runtime_usage import build_runtime_recent_payload

        limit_raw = query.get("limit", ["50"])[0]
        try:
            limit_val = int(limit_raw)
        except (TypeError, ValueError):
            limit_val = 50
        return 200, build_runtime_recent_payload(
            repo_root,
            limit=limit_val,
        ), "application/json; charset=utf-8"
    decision_page = _DECISION_ROUTES.route_decision_page_request(
        repo_root,
        path,
        top_nav_css=_TOP_NAV_CSS,
        render_top_nav_fn=_render_top_nav,
        render_markdown_fn=_render_markdown_body,
    )
    if decision_page is not None:
        return decision_page
    channel_page = _CHANNEL_ROUTES.route_channel_page_request(
        repo_root,
        path,
        top_nav_css=_TOP_NAV_CSS,
        render_top_nav_fn=_render_top_nav,
        resolve_bridge_db_path_fn=_resolve_bridge_db_path,
        query_sqlite_rows_fn=_query_sqlite_rows,
    )
    if channel_page is not None:
        return channel_page
    if path == "/healthz":
        return 200, _repo_guard_module().build_healthz_payload(repo_root), "application/json; charset=utf-8"
    if path == "/api/artifacts":
        return 200, _get_artifacts_index(repo_root, query), "application/json; charset=utf-8"
    if path == "/api/status/summary":
        # Dashboard hot path: skip the git-per-file translation + ZTT passes
        # (~2min total). Full versions served by /api/translation/v2/status
        # and /api/ztt/status.
        from status import build_repo_status
        return 200, build_repo_status(repo_root, fast=True), "application/json; charset=utf-8"
    if path == "/api/missing-modules/status":
        from status import _build_missing_modules_summary
        return 200, _build_missing_modules_summary(repo_root), "application/json; charset=utf-8"
    if path == "/api/activity/recent":
        return 200, build_recent_activity(repo_root), "application/json; charset=utf-8"
    if path == "/api/activity":
        since_raw = query.get("since", [None])[0]
        since_seconds: int | None = None
        if since_raw:
            try:
                # Accept epoch seconds...
                since_seconds = int(since_raw)
            except (TypeError, ValueError):
                # ...or an ISO-8601 timestamp.
                since_seconds = _iso_to_epoch(since_raw)
                if since_seconds is None:
                    return 400, {"error": "invalid_since"}, "application/json; charset=utf-8"
        try:
            limit = int(query.get("limit", ["50"])[0])
        except (TypeError, ValueError):
            limit = 50
        return (
            200,
            build_activity_feed(repo_root, since_seconds=since_seconds, limit=limit),
            "application/json; charset=utf-8",
        )
    if path == "/api/navigation/status":
        return 200, build_navigation_status(repo_root), "application/json; charset=utf-8"
    if path == "/api/delivery/status":
        return 200, build_delivery_status(repo_root), "application/json; charset=utf-8"
    if path == "/api/tracks/readiness":
        return 200, build_tracks_readiness(repo_root), "application/json; charset=utf-8"
    if path == "/api/runtime/services":
        return 200, build_runtime_services_status(repo_root), "application/json; charset=utf-8"
    if path == "/api/build/status":
        job_id = query.get("job_id", [None])[0]
        if not job_id:
            return 400, {"error": "missing_job_id"}, "application/json; charset=utf-8"
        return get_build_job_status(repo_root, job_id)
    if path == "/api/pipeline/v2/status":
        db_path = repo_root / ".pipeline" / "v2.db"
        if not db_path.exists():
            return 404, {"error": "missing_db", "db_path": str(db_path)}, "application/json; charset=utf-8"
        from pipeline_v2.cli import _build_status_report as build_v2_status_report
        from status import _enrich_v2_with_per_track
        return 200, _enrich_v2_with_per_track(build_v2_status_report(db_path)), "application/json; charset=utf-8"
    if path == "/api/translation/v2/enqueue":
        from translation_v2 import (
            ControlPlane,
            TRANSLATE_ESTIMATED_USD,
            TRANSLATE_MODEL,
            _has_pending_or_leased_job,
        )

        from_quality = query.get("from_quality", [None])[0]
        if from_quality != "done":
            return (
                400,
                {"error": "invalid_from_quality", "supported": ["done"]},
                "application/json; charset=utf-8",
            )

        raw_dry_run = query.get("dry_run", ["0"])[0]
        dry_run = raw_dry_run not in ("0", "false", "False", "FALSE", "")

        board = build_quality_board(repo_root)
        modules = board.get("modules")
        if not isinstance(modules, list):
            modules = []

        total_modules = len(modules)
        done_modules = [
            item.get("module_key")
            for item in modules
            if str(item.get("status") or "").lower() == "done"
        ]
        done_modules = [key for key in done_modules if isinstance(key, str)]

        db_path = repo_root / ".pipeline" / "translation_v2.db"
        control_plane = ControlPlane(repo_root=repo_root, db_path=db_path)

        skipped_reasons = {
            "already_pending_or_leased": 0,
            "already_completed": 0,
            "previously_failed": 0,
            "not_done": max(total_modules - len(done_modules), 0),
        }
        enqueued: list[str] = []

        if db_path.exists():
            conn = sqlite3.connect(db_path)
            try:
                for module_key in done_modules:
                    if _has_pending_or_leased_job(db_path, module_key):
                        skipped_reasons["already_pending_or_leased"] += 1
                        continue

                    terminal_row = conn.execute(
                        "SELECT queue_state FROM jobs WHERE module_key = ? AND queue_state IN ('failed', 'completed') LIMIT 1",
                        (module_key,),
                    ).fetchone()
                    if terminal_row is not None:
                        if terminal_row[0] == "completed":
                            skipped_reasons["already_completed"] += 1
                        else:
                            skipped_reasons["previously_failed"] += 1
                        continue

                    if not dry_run:
                        control_plane.enqueue(
                            module_key,
                            phase="write",
                            model=TRANSLATE_MODEL,
                            priority=100 + len(enqueued),
                            requested_calls=1,
                            estimated_usd=TRANSLATE_ESTIMATED_USD,
                        )
                    enqueued.append(module_key)
            finally:
                conn.close()
        else:
            if not dry_run:
                for module_key in done_modules:
                    control_plane.enqueue(
                        module_key,
                        phase="write",
                        model=TRANSLATE_MODEL,
                        priority=100 + len(enqueued),
                        requested_calls=1,
                        estimated_usd=TRANSLATE_ESTIMATED_USD,
                    )
                    enqueued.append(module_key)
            else:
                enqueued = done_modules

        return (
            200,
            {
                "enqueued": len(enqueued),
                "skipped": (
                    skipped_reasons["already_pending_or_leased"]
                    + skipped_reasons["already_completed"]
                    + skipped_reasons["previously_failed"]
                    + skipped_reasons["not_done"]
                ),
                "skipped_reasons": skipped_reasons,
                "dry_run": dry_run,
            },
            "application/json; charset=utf-8",
        )
    if path == "/api/translation/v2/status":
        section = query.get("section", [None])[0]
        # Dashboard hot path skips the git-per-file freshness walk; callers
        # that need it can pass ?freshness=1.
        want_freshness = query.get("freshness", ["0"])[0] not in ("0", "false", "")
        db_path = repo_root / ".pipeline" / "translation_v2.db"
        from status import _enrich_translation_v2_with_per_track
        if want_freshness:
            from translation_v2 import build_status as build_translation_status
            t2 = build_translation_status(repo_root, db_path=db_path, section=section)
        else:
            from translation_v2 import _build_translation_queue_status
            t2 = {
                "repo_root": str(repo_root),
                "db_path": str(db_path),
                "section": section,
                "freshness": None,
                "queue": _build_translation_queue_status(db_path) if db_path.exists() else None,
            }
        return 200, _enrich_translation_v2_with_per_track(t2), "application/json; charset=utf-8"
    if path == "/api/labs/status":
        from status import _build_lab_summary
        return 200, _build_lab_summary(repo_root), "application/json; charset=utf-8"
    if path == "/api/ztt/status":
        from ztt_status import build_status as build_ztt_status
        return 200, build_ztt_status(repo_root), "application/json; charset=utf-8"
    if path == "/api/git/worktree":
        return 200, build_worktree_status(repo_root), "application/json; charset=utf-8"
    if path == "/api/git/worktrees":
        return 200, build_worktrees_list(repo_root), "application/json; charset=utf-8"
    if path == "/api/git/cleanup":
        return 200, build_git_cleanup_report(repo_root), "application/json; charset=utf-8"
    if path == "/api/gh/issues":
        state = query.get("state", ["open"])[0] or "open"
        if state not in {"open", "closed", "all"}:
            state = "open"
        try:
            limit = int(query.get("limit", ["50"])[0])
        except (TypeError, ValueError):
            limit = 50
        return _build_gh_list("issue", state, max(1, min(limit, 200)))
    if path.startswith("/api/gh/issues/"):
        try:
            number = int(path.split("/")[-1])
        except ValueError:
            return 400, {"error": "invalid_issue_number"}, "application/json; charset=utf-8"
        return _build_gh_detail("issue", number)
    if path == "/api/gh/prs":
        state = query.get("state", ["open"])[0] or "open"
        if state not in {"open", "closed", "merged", "all"}:
            state = "open"
        try:
            limit = int(query.get("limit", ["50"])[0])
        except (TypeError, ValueError):
            limit = 50
        return _build_gh_list("pr", state, max(1, min(limit, 200)))
    if path.startswith("/api/gh/prs/"):
        try:
            number = int(path.split("/")[-1])
        except ValueError:
            return 400, {"error": "invalid_pr_number"}, "application/json; charset=utf-8"
        return _build_gh_detail("pr", number)
    if path == "/api/schema":
        return 200, build_api_schema(), "application/json; charset=utf-8"
    if path == "/api/state/manifest":
        return 200, build_state_manifest(), "application/json; charset=utf-8"
    if path == "/api/briefing/session":
        compact = query.get("compact", ["0"])[0] not in ("0", "false", "")
        briefing, freshness = get_or_build_session_briefing(repo_root)
        briefing = dict(briefing)
        briefing["freshness"] = freshness
        if compact:
            briefing = _compact_briefing(briefing)
        return 200, briefing, "application/json; charset=utf-8"
    if path == "/api/orient":
        return 200, build_orient(repo_root), "application/json; charset=utf-8"
    if path == "/api/session/current":
        return 200, build_current_session(repo_root), "application/json; charset=utf-8"
    if path == "/api/benchmarks/latest":
        return 200, build_latest_benchmarks(repo_root), "application/json; charset=utf-8"
    if path == "/api/briefing/book":
        return 200, build_book_briefing(repo_root), "application/json; charset=utf-8"
    if path == "/api/cache/stats":
        return 200, _cache_stats(), "application/json; charset=utf-8"
    if path == "/api/pipeline/leases":
        return 200, build_pipeline_leases(repo_root), "application/json; charset=utf-8"
    if path == "/api/pipeline/v2/stuck":
        try:
            threshold = int(query.get("threshold_seconds", [str(_DEFAULT_STUCK_THRESHOLD_SECONDS)])[0])
        except (TypeError, ValueError):
            threshold = _DEFAULT_STUCK_THRESHOLD_SECONDS
        threshold = max(60, min(threshold, 24 * 3600))
        return 200, build_pipeline_stuck(repo_root, threshold_seconds=threshold), "application/json; charset=utf-8"
    if path == "/api/pipeline/v2/events":
        mk = query.get("module", [None])[0]
        module_key: str | None = None
        if mk:
            module_key = _validate_module_key(repo_root, mk)
            if module_key is None:
                return 400, {"error": "invalid_module_key"}, "application/json; charset=utf-8"
        try:
            since_seconds = int(query.get("since_seconds", ["0"])[0]) or None
        except (TypeError, ValueError):
            since_seconds = None
        try:
            limit = int(query.get("limit", ["200"])[0])
        except (TypeError, ValueError):
            limit = 200
        return 200, build_pipeline_events(repo_root, module_key, since_seconds, limit), "application/json; charset=utf-8"
    if path == "/api/reviews":
        fact_check_status = query.get("fact_check_status", [None])[0]
        if fact_check_status and fact_check_status not in _VALID_FACT_CHECK_STATUSES:
            return 400, {"error": "invalid_fact_check_status"}, "application/json; charset=utf-8"
        mk = query.get("module", [None])[0]
        if mk:
            module_key = _validate_module_key(repo_root, mk)
            if module_key is None:
                return 400, {"error": "invalid_module_key"}, "application/json; charset=utf-8"
            payload = build_module_reviews(repo_root, module_key)
            if payload is None:
                return 404, {"error": "review_not_found", "module_key": module_key}, "application/json; charset=utf-8"
            return 200, payload, "application/json; charset=utf-8"
        return 200, build_reviews_index(repo_root, fact_check_status=fact_check_status), "application/json; charset=utf-8"
    if path == "/api/bridge/messages":
        since = query.get("since", [None])[0]
        try:
            limit = int(query.get("limit", ["100"])[0])
        except (TypeError, ValueError):
            limit = 100
        return 200, build_bridge_messages(repo_root, since, limit), "application/json; charset=utf-8"
    search_api = _SEARCH_ROUTES.route_search_request(
        repo_root,
        path,
        query,
        bridge_db_path=_resolve_bridge_db_path(repo_root),
    )
    if search_api is not None:
        return search_api
    decision_api = _DECISION_ROUTES.route_decision_api_request(repo_root, path)
    if decision_api is not None:
        return decision_api
    channel_api = _CHANNEL_ROUTES.route_channel_api_request(
        repo_root,
        path,
        query,
        resolve_bridge_db_path_fn=_resolve_bridge_db_path,
        query_sqlite_rows_fn=_query_sqlite_rows,
    )
    if channel_api is not None:
        return channel_api
    if path == "/api/quality/scores":
        return 200, build_quality_scores(repo_root), "application/json; charset=utf-8"
    if path == "/api/quality/board":
        return 200, build_quality_board(repo_root), "application/json; charset=utf-8"
    if path == "/api/uk/board":
        from translation_v2 import build_translation_board

        return 200, build_translation_board(repo_root), "application/json; charset=utf-8"
    if path == "/api/quality/upgrade-plan":
        try:
            target = float(query.get("target", ["4.0"])[0])
        except (TypeError, ValueError):
            return 400, {"error": "invalid_target"}, "application/json; charset=utf-8"
        if target <= 0:
            return 400, {"error": "invalid_target"}, "application/json; charset=utf-8"
        return 200, build_quality_upgrade_plan(repo_root, target=target), "application/json; charset=utf-8"
    if path == "/api/citations/status":
        return 200, build_citation_status(repo_root), "application/json; charset=utf-8"
    if path == "/api/388/batches":
        batches = _list_388_batches(repo_root)
        return 200, {"batches": batches, "count": len(batches)}, "application/json; charset=utf-8"
    if path.startswith("/api/388/batch/"):
        log_stem = unquote(path[len("/api/388/batch/"):]).strip("/")
        if not log_stem or "/" in log_stem:
            return 400, {"error": "invalid_log_stem"}, "application/json; charset=utf-8"
        payload = _load_388_batch(repo_root, log_stem)
        if payload is None:
            return 404, {"error": "not_found", "log_stem": log_stem}, "application/json; charset=utf-8"
        return 200, payload, "application/json; charset=utf-8"
    if path.startswith("/api/module/") and path.endswith("/lease"):
        raw_key = unquote(path[len("/api/module/") : -len("/lease")]).strip("/")
        if not raw_key:
            return 400, {"error": "missing_module_key"}, "application/json; charset=utf-8"
        module_key = _validate_module_key(repo_root, raw_key)
        if module_key is None:
            return 400, {"error": "invalid_module_key"}, "application/json; charset=utf-8"
        return 200, build_module_lease(repo_root, module_key), "application/json; charset=utf-8"
    if path.startswith("/api/issue-watch/"):
        try:
            issue_number = int(path.split("/")[-1])
        except ValueError:
            return 400, {"error": "invalid_issue_number"}, "application/json; charset=utf-8"
        payload = build_issue_watch_state(repo_root, issue_number)
        if payload is None:
            return 404, {"error": "missing_issue_watch_state", "issue_number": issue_number}, "application/json; charset=utf-8"
        return 200, payload, "application/json; charset=utf-8"
    if path.startswith("/api/module/") and path.endswith("/state"):
        raw_key = unquote(path[len("/api/module/") : -len("/state")]).strip("/")
        if not raw_key:
            return 400, {"error": "missing_module_key"}, "application/json; charset=utf-8"
        module_key = _validate_module_key(repo_root, raw_key)
        if module_key is None:
            return 400, {"error": "invalid_module_key"}, "application/json; charset=utf-8"
        return 200, build_module_state(repo_root, module_key), "application/json; charset=utf-8"
    if path.startswith("/api/module/") and path.endswith("/orchestration/latest"):
        raw_key = unquote(path[len("/api/module/") : -len("/orchestration/latest")]).strip("/")
        if not raw_key:
            return 400, {"error": "missing_module_key"}, "application/json; charset=utf-8"
        module_key = _validate_module_key(repo_root, raw_key)
        if module_key is None:
            return 400, {"error": "invalid_module_key"}, "application/json; charset=utf-8"
        return 200, build_module_orchestration_latest(repo_root, module_key), "application/json; charset=utf-8"
    return 404, {"error": "not_found", "path": path}, "application/json; charset=utf-8"


def route_post_request(
    repo_root: Path,
    raw_path: str,
    *,
    body_bytes: bytes | None = None,
    content_type: str = "",
) -> tuple[int, Any, str]:
    path = urlsplit(raw_path).path.rstrip("/") or "/"
    if path == "/api/build/run":
        return start_build_job(repo_root)
    channel_post = _CHANNEL_ROUTES.route_channel_post_request(
        path,
        body_bytes=body_bytes,
        content_type=content_type,
        bridge_db_path=_resolve_bridge_db_path(repo_root),
    )
    if channel_post is not None:
        return channel_post
    if path == "/api/telemetry/module-builds":
        from telemetry_store import upsert_run

        if not body_bytes:
            return 400, {"error": "empty body"}, "application/json; charset=utf-8"
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"error": "invalid JSON"}, "application/json; charset=utf-8"
        try:
            run_id = upsert_run(repo_root, payload)
        except ValueError as exc:
            return 400, {"error": str(exc)}, "application/json; charset=utf-8"
        return 200, {"ok": True, "run_id": run_id}, "application/json; charset=utf-8"
    if path == "/api/telemetry/tool-timings":
        from telemetry_store import ingest_tool_timing

        if not body_bytes:
            return 400, {"error": "empty body"}, "application/json; charset=utf-8"
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"error": "invalid JSON"}, "application/json; charset=utf-8"
        try:
            ingest_tool_timing(repo_root, payload)
        except ValueError as exc:
            return 400, {"error": str(exc)}, "application/json; charset=utf-8"
        return 200, {"ok": True}, "application/json; charset=utf-8"
    return 404, {"error": "not_found", "path": path}, "application/json; charset=utf-8"


# ============================================================
# Cache policy + request pipeline
# ============================================================
#
# TTLs are tuned for the dashboard (60s refresh) and agent polling. They are
# short enough that human interactivity never sees stale state beyond a few
# seconds, but long enough to absorb thundering-herd polls. sqlite-backed
# routes add a ``PRAGMA data_version``-based dep check so a write from the
# pipeline supervisor invalidates the cache immediately.


def _v_v2_db(repo_root: Path) -> tuple:
    return ("v2", _sqlite_version_key(repo_root / ".pipeline" / "v2.db"))


def _v_translation_db(repo_root: Path) -> tuple:
    return ("t2", _sqlite_version_key(repo_root / ".pipeline" / "translation_v2.db"))


def _v_uk_board(repo_root: Path) -> tuple:
    docs_root = repo_root / "src" / "content" / "docs"
    sig = hashlib.sha1()
    if docs_root.is_dir():
        for path in sorted(docs_root.rglob("*")):
            if not path.is_file() or path.suffix not in {".md", ".mdx"}:
                continue
            try:
                rel = path.relative_to(docs_root).as_posix()
                stat = path.stat()
            except OSError:
                continue
            sig.update(f"{rel}:{stat.st_mtime_ns}:{stat.st_size}\n".encode())
    return ("uk_board", sig.hexdigest())


def _v_quality_board(repo_root: Path) -> tuple:
    docs_root = repo_root / "src" / "content" / "docs"
    state_dir = repo_root / ".pipeline" / "quality-pipeline"
    reviews_dir = repo_root / _REVIEW_AUDIT_DIR
    sig = hashlib.sha1()

    for base, pattern in (
        # Count reconciliation scans all docs Markdown, so the ETag must too.
        (docs_root, "**/*.md"),
        (state_dir, "*.json"),
        (reviews_dir, "*.md"),
    ):
        if not base.is_dir():
            continue
        for path in sorted(base.glob(pattern)):
            try:
                rel = path.relative_to(repo_root).as_posix()
                stat = path.stat()
            except OSError:
                continue
            sig.update(rel.encode("utf-8"))
            sig.update(f":{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))

    queue_path = state_dir / "post-review-queue.txt"
    try:
        stat = queue_path.stat()
    except OSError:
        pass
    else:
        sig.update(queue_path.relative_to(repo_root).as_posix().encode("utf-8"))
        sig.update(f":{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))

    return ("quality-board", sig.hexdigest())


def _v_docs_frontmatter(repo_root: Path) -> tuple:
    docs_root = repo_root / "src" / "content" / "docs"
    from status import _iter_en_modules

    sig = hashlib.sha1()
    for path in _iter_en_modules(docs_root):
        try:
            rel = path.relative_to(repo_root).as_posix()
            stat = path.stat()
        except OSError:
            continue
        sig.update(rel.encode("utf-8"))
        sig.update(f":{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
    extras = [repo_root / "docs" / "content-upgrade" / "evidence.json"]
    seeds = repo_root / "docs" / "citation-seeds"
    if seeds.is_dir():
        extras.extend(sorted(seeds.glob("*.json")))
    for extra in extras:
        try:
            rel = extra.relative_to(repo_root).as_posix()
            stat = extra.stat()
        except OSError:
            continue
        sig.update(rel.encode("utf-8"))
        sig.update(f":{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
    return ("docs-frontmatter", sig.hexdigest())


# Map fixed paths (query-independent beyond ``?compact=1``) to policies.
# (ttl_seconds, version_fn_or_None)
CACHE_POLICY: dict[str, tuple[float, Callable[[Path], tuple] | None]] = {
    "/healthz": (60.0, None),
    "/artifacts": (30.0, None),
    "/api/artifacts": (30.0, None),
    "/api/schema": (600.0, None),
    "/api/state/manifest": (600.0, None),
    "/api/session/current": (30.0, None),
    "/api/benchmarks/latest": (30.0, None),
    "/api/status/summary": (10.0, _v_v2_db),
    "/api/missing-modules/status": (30.0, None),
    "/api/activity/recent": (5.0, _v_v2_db),
    "/api/navigation/status": (30.0, None),
    "/api/delivery/status": (30.0, None),
    "/api/runtime/services": (2.0, None),
    "/api/pipeline/v2/status": (5.0, _v_v2_db),
    "/api/translation/v2/status": (5.0, _v_translation_db),
    "/api/labs/status": (10.0, None),
    "/api/quality/board": (30.0, _v_quality_board),
    "/api/uk/board": (30.0, _v_uk_board),
    "/api/quality/upgrade-plan": (30.0, None),
    "/api/tracks/readiness": (5.0, _v_docs_frontmatter),
    "/api/citations/status": (30.0, None),
    "/api/ztt/status": (30.0, None),
    "/api/git/worktree": (2.0, None),
    "/api/git/worktrees": (5.0, None),
    "/api/git/cleanup": (10.0, None),
    "/api/briefing/session": (5.0, None),  # background-refreshed; TTL just caps rebuild rate
    "/api/orient": (5.0, None),  # cheap projection over the same background-refreshed briefing
}


def _match_etag(if_none_match: str, etag: str) -> bool:
    """Return True if the client's If-None-Match header matches our ETag.

    Handles comma-separated lists and leading ``W/`` weak marker.
    """
    if not if_none_match:
        return False
    candidates = [tok.strip() for tok in if_none_match.split(",") if tok.strip()]
    # Strip W/ prefix on both sides for weak-compare semantics.
    our = etag[2:] if etag.startswith("W/") else etag
    for cand in candidates:
        if cand == "*":
            return True
        normalized = cand[2:] if cand.startswith("W/") else cand
        if normalized == our:
            return True
    return False


def serve_request(
    repo_root: Path, raw_path: str
) -> tuple[int, bytes, str, str]:
    """Compute ``(status, body_bytes, content_type, etag)`` for ``raw_path``.

    Serves from cache for paths registered in ``CACHE_POLICY``. Builds on miss.
    ETag is always set from the response bytes so 304 works for every 2xx
    response, cached or not.
    """
    parsed = urlsplit(raw_path)
    path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query)

    if _is_gh_path(path):
        cache_key = _normalized_cache_key(path, query, repo_root=repo_root)

        def _build() -> tuple[int, Any, str]:
            return route_request(repo_root, raw_path)

        return cached_response(
            cache_key,
            GH_CACHE_TTL_SECONDS,
            lambda: ("gh",),
            _build,
            lambda payload, _body: _gh_payload_etag(path, payload),
        )

    policy = CACHE_POLICY.get(path)
    if policy is not None:
        ttl, version_fn = policy
        cache_key = _normalized_cache_key(path, query, repo_root=repo_root)

        def _version() -> tuple:
            return version_fn(repo_root) if version_fn is not None else ("ttl",)

        def _build() -> tuple[int, Any, str]:
            return route_request(repo_root, raw_path)

        return cached_response(cache_key, ttl, _version, _build)

    status_code, payload, content_type = route_request(repo_root, raw_path)
    body_bytes = _serialize_payload(payload, content_type)
    etag = _weak_etag(body_bytes)
    return status_code, body_bytes, content_type, etag


def make_handler(repo_root: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:  # noqa: N802
            try:
                status_code, body, content_type, etag = serve_request(repo_root, self.path)
            except Exception:  # noqa: BLE001 - HEAD should mirror GET without surfacing stack traces
                status_code = 500
                body = b""
                content_type = "application/json; charset=utf-8"
                etag = _weak_etag(body)

            location = None
            if 300 <= status_code < 400:
                decoded_body = body.decode("utf-8", errors="replace").strip()
                if decoded_body.startswith("/"):
                    location = decoded_body

            content_type = _safe_header_value(content_type)
            etag = _safe_etag_header_value(etag)
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if location is not None:
                location = _safe_header_value(location)
                self.send_header("Location", location)
            if 200 <= status_code < 300:
                self.send_header("ETag", etag)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            try:
                status_code, body, content_type, etag = serve_request(repo_root, self.path)
            except sqlite3.Error as exc:
                status_code = 500
                payload = {
                    "error": "sqlite_error",
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "path": self.path,
                }
                content_type = "application/json; charset=utf-8"
                body = _serialize_payload(payload, content_type)
                etag = _weak_etag(body)
            except Exception as exc:  # noqa: BLE001 - surface all read failures as JSON
                status_code = 500
                payload = {
                    "error": "internal_error",
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "path": self.path,
                }
                content_type = "application/json; charset=utf-8"
                body = _serialize_payload(payload, content_type)
                etag = _weak_etag(body)

            if 200 <= status_code < 300:
                inm = self.headers.get("If-None-Match", "")
                if _header_value_has_crlf(inm):
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                etag = _safe_etag_header_value(etag)
                if _match_etag(inm, etag):
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

            location = None
            if 300 <= status_code < 400:
                try:
                    decoded_body = body.decode("utf-8", errors="replace").strip()
                except (AttributeError, UnicodeDecodeError):
                    decoded_body = ""
                if decoded_body.startswith("/"):
                    location = decoded_body

            try:
                content_type = _safe_header_value(content_type)
                etag = _safe_etag_header_value(etag)
                self.send_response(status_code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                if location is not None:
                    location = _safe_header_value(location)
                    self.send_header("Location", location)
                if 200 <= status_code < 300:
                    self.send_header("ETag", etag)
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # Client disconnected mid-response. Swallowing keeps the
                # worker thread alive; the server itself is unaffected.
                return

        def do_POST(self) -> None:  # noqa: N802
            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
                body_bytes = self.rfile.read(max(0, content_length))
                request_content_type = self.headers.get("Content-Type", "")
                status_code, payload, content_type = route_post_request(
                    repo_root,
                    self.path,
                    body_bytes=body_bytes,
                    content_type=request_content_type,
                )
            except Exception as exc:  # noqa: BLE001 - surface all write failures as JSON
                status_code = 500
                payload = {
                    "error": "internal_error",
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "path": self.path,
                }
                content_type = "application/json; charset=utf-8"

            body = _serialize_payload(payload, content_type)
            content_type = _safe_header_value(content_type)
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def serve(repo_root: Path, host: str, port: int) -> None:
    inspection = _repo_guard_module().inspect_repo_root(repo_root)
    for warning in inspection.get("warnings", []):
        if isinstance(warning, str):
            print(warning, file=sys.stderr)
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), make_handler(repo_root))
    print(json.dumps({"repo_root": str(repo_root), "host": host, "port": port}, sort_keys=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic local API for KubeDojo state")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    serve(args.repo_root.resolve(), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
