#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from checks import ukrainian
from quality.calque_review_stamp import read_status as read_calque_review_status
from uk_sync import fix_module as uk_fix_module
from uk_sync import translate_new_module as uk_translate_new_module

GEMINI_WRITER_MODEL = "gemini-3.1-pro-high"
DEFAULT_BUDGETS_PATH = None


class ControlPlane:
    """Stand-in for the removed pipeline control plane."""

    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
UK_ROOT = DOCS_ROOT / "uk"
DEFAULT_DB_PATH = REPO_ROOT / ".pipeline" / "translation_v2.db"
TRANSLATE_MODEL = GEMINI_WRITER_MODEL
TRANSLATE_ESTIMATED_USD = 0.0350
VERIFY_MODEL = "deterministic-ukrainian-checks"
DEFAULT_LEASE_SECONDS = 1200
DEFAULT_MAX_WRITE_ATTEMPTS = 3
DEFAULT_MAX_VERIFY_ATTEMPTS = 3
_MODULE_REF_RE = re.compile(r"(?:module|модуль)\s+([\d.]+)", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _extract_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _, _, rest = text.partition("---\n")
    frontmatter, _, _ = rest.partition("\n---\n")
    try:
        data = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _git_head_for_file(repo_root: Path, path: Path) -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _normalize_module_key(module_key: str) -> str:
    return module_key[:-3] if module_key.endswith(".md") else module_key


def _en_path_for_module_key(repo_root: Path, module_key: str) -> Path:
    key = _normalize_module_key(module_key)
    return repo_root / "src" / "content" / "docs" / f"{key}.md"


def _uk_path_for_module_key(repo_root: Path, module_key: str) -> Path:
    key = _normalize_module_key(module_key)
    return repo_root / "src" / "content" / "docs" / "uk" / f"{key}.md"


def _module_key_for_en_path(repo_root: Path, en_path: Path) -> str:
    rel = en_path.relative_to(repo_root / "src" / "content" / "docs").as_posix()
    return rel[:-3] if rel.endswith(".md") else rel


def _iter_en_modules(repo_root: Path, *, section: str | None = None) -> list[Path]:
    docs_root = repo_root / "src" / "content" / "docs"
    base = docs_root / section if section else docs_root
    return sorted(
        path
        for path in base.glob("**/module-*.md")
        if path.is_file() and "/uk/" not in path.as_posix() and ".staging." not in path.name
    )


def detect_module_state(repo_root: Path, module_key: str) -> dict[str, Any]:
    en_path = _en_path_for_module_key(repo_root, module_key)
    uk_path = _uk_path_for_module_key(repo_root, module_key)
    result: dict[str, Any] = {
        "module_key": _normalize_module_key(module_key),
        "en_path": en_path.as_posix(),
        "uk_path": uk_path.as_posix(),
        "status": "missing",
        "issues": [],
    }
    if not en_path.exists():
        result["status"] = "unknown"
        result["issues"].append("missing_en_source")
        return result
    if not uk_path.exists():
        result["status"] = "missing"
        result["en_commit"] = _git_head_for_file(repo_root, en_path)
        result["issues"].append("missing_uk_file")
        return result

    frontmatter = _extract_frontmatter(uk_path)
    tracked_en_file = str(frontmatter.get("en_file", "")).strip().strip('"')
    tracked_en_commit = str(frontmatter.get("en_commit", "")).strip().strip('"')
    expected_en_file = en_path.relative_to(repo_root).as_posix()
    en_commit = _git_head_for_file(repo_root, en_path)
    result["en_commit"] = en_commit
    result["uk_en_commit"] = tracked_en_commit

    if tracked_en_file != expected_en_file:
        result["status"] = "stale"
        result["issues"].append("en_file_mismatch")
    elif tracked_en_commit and en_commit and tracked_en_commit == en_commit:
        result["status"] = "synced"
    elif not tracked_en_commit or not en_commit:
        result["status"] = "unknown"
        result["issues"].append("missing_commit_tracking")
    else:
        result["status"] = "stale"
        result["issues"].append("stale_commit")

    return result


_CURRICULUM_TRACK_ORDER = (
    "prerequisites",
    "linux",
    "cloud",
    "k8s",
    "platform",
    "on-premises",
    "ai",
    "ai-ml-engineering",
    "ai-history",
    "root",
)


def _body_without_frontmatter(text: str) -> str:
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        return text[4:].split("\n---\n", 1)[1]
    return text


def _word_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return len(_body_without_frontmatter(text).split())


def _en_file_matches(tracked_en_file: str, rel: str) -> bool:
    tracked = str(tracked_en_file or "").strip().strip('"')
    if not tracked:
        return True
    rel_norm = rel.replace("\\", "/")
    candidates = {
        rel_norm,
        f"src/content/docs/{rel_norm}",
    }
    return tracked in candidates or tracked.replace("\\", "/").endswith(f"/{rel_norm}")


def _track_for_rel(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) == 1:
        return "root"
    first = parts[0]
    if first in _CURRICULUM_TRACK_ORDER and first != "root":
        return first
    return first


def _track_sort_key(track: str) -> tuple[int, int | str]:
    try:
        return (0, _CURRICULUM_TRACK_ORDER.index(track))
    except ValueError:
        return (1, track)


def _iter_en_pages(repo_root: Path) -> list[Path]:
    docs_root = repo_root / "src" / "content" / "docs"
    if not docs_root.is_dir():
        return []
    pages: list[Path] = []
    for path in docs_root.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".mdx"}:
            continue
        rel_str = path.relative_to(docs_root).as_posix()
        if rel_str.startswith("uk/") or ".staging." in path.name:
            continue
        pages.append(path)
    return sorted(pages, key=lambda p: p.relative_to(docs_root).as_posix())


def _classify_page_status(
    repo_root: Path,
    en_path: Path,
    uk_path: Path,
    rel: str,
) -> tuple[str, int, int, float]:
    en_words = _word_count(en_path)
    if not uk_path.is_file():
        return "missing", en_words, 0, 0.0

    uk_words = _word_count(uk_path)
    if en_words == 0:
        ratio = 1.0 if uk_words == 0 else 0.0
    else:
        ratio = uk_words / en_words

    frontmatter = _extract_frontmatter(uk_path)
    tracked_en_file = str(frontmatter.get("en_file", ""))
    metadata_stale = not _en_file_matches(tracked_en_file, rel)

    if ratio < 0.60 or metadata_stale:
        return "stale", en_words, uk_words, round(ratio, 2)
    return "current", en_words, uk_words, round(ratio, 2)


def _is_calque_reviewed(review: dict[str, Any] | None) -> bool:
    if review is None:
        return False
    return review.get("status") in {"reviewed", "clean"} and not review.get("stale", True)


def build_translation_board(repo_root: Path) -> dict[str, Any]:
    """Per-page UK translation currency board keyed by EN docs-relative paths.

    Currency is measured by word-ratio (UK < 60% of current EN = stale), not
    file existence. See issue #1911.
    """
    docs_root = repo_root / "src" / "content" / "docs"
    track_pages: dict[str, list[dict[str, Any]]] = {}
    totals = {
        "total": 0,
        "current": 0,
        "stale": 0,
        "missing": 0,
        "current_pct": 0,
        "reviewed": 0,
        "reviewed_pct": 0,
    }

    for en_path in _iter_en_pages(repo_root):
        rel = en_path.relative_to(docs_root).as_posix()
        uk_path = docs_root / "uk" / rel
        status, en_words, uk_words, ratio = _classify_page_status(repo_root, en_path, uk_path, rel)
        review = read_calque_review_status(uk_path) if uk_path.exists() else None
        track = _track_for_rel(rel)
        page = {
            "rel": rel,
            "status": status,
            "en_words": en_words,
            "uk_words": uk_words,
            "ratio": ratio,
            "calque_review": review,
        }
        track_pages.setdefault(track, []).append(page)
        totals["total"] += 1
        totals[status] += 1
        if _is_calque_reviewed(review):
            totals["reviewed"] += 1

    tracks: list[dict[str, Any]] = []
    for track in sorted(track_pages, key=_track_sort_key):
        pages = sorted(track_pages[track], key=lambda p: p["rel"])
        track_total = len(pages)
        current = sum(1 for p in pages if p["status"] == "current")
        stale = sum(1 for p in pages if p["status"] == "stale")
        missing = sum(1 for p in pages if p["status"] == "missing")
        reviewed = sum(1 for p in pages if _is_calque_reviewed(p.get("calque_review")))
        tracks.append(
            {
                "track": track,
                "total": track_total,
                "current": current,
                "stale": stale,
                "missing": missing,
                "current_pct": round(100 * current / track_total) if track_total else 0,
                "reviewed": reviewed,
                "reviewed_pct": round(100 * reviewed / track_total) if track_total else 0,
                "pages": pages,
            }
        )

    total = totals["total"]
    totals["current_pct"] = round(100 * totals["current"] / total) if total else 0
    totals["reviewed_pct"] = round(100 * totals["reviewed"] / total) if total else 0

    return {
        "generated_at": int(time.time()),
        "totals": totals,
        "tracks": tracks,
    }


def build_freshness_report(repo_root: Path, *, section: str | None = None) -> dict[str, Any]:
    modules = [detect_module_state(repo_root, _module_key_for_en_path(repo_root, p)) for p in _iter_en_modules(repo_root, section=section)]
    counts = {"synced": 0, "missing": 0, "stale": 0, "unknown": 0}
    for item in modules:
        status = str(item["status"])
        if status in counts:
            counts[status] += 1
    return {
        "section": section,
        "total": len(modules),
        **counts,
        "sync_clean": counts["missing"] == 0 and counts["stale"] == 0 and counts["unknown"] == 0,
        "modules": modules,
    }


def build_status(repo_root: Path, *, db_path: Path, section: str | None = None) -> dict[str, Any]:
    freshness = build_freshness_report(repo_root, section=section)
    queue = _build_translation_queue_status(db_path) if db_path.exists() else None
    return {
        "repo_root": str(repo_root),
        "db_path": str(db_path),
        "section": section,
        "freshness": freshness,
        "queue": queue,
    }


def _build_translation_queue_status(db_path: Path) -> dict[str, Any]:
    phase_order = [
        "pending_review",
        "pending_write",
        "done",
        "dead_letter",
        "in_progress",
    ]
    counts = {phase: 0 for phase in phase_order}
    modules: set[str] = set()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        job_rows = conn.execute(
            """
            SELECT id, module_key, phase, queue_state
            FROM jobs
            WHERE module_key IS NOT NULL
            ORDER BY id ASC
            """
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT id, module_key, type
            FROM events
            WHERE module_key IS NOT NULL
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    latest_job_by_module: dict[str, sqlite3.Row] = {}
    latest_event_by_module: dict[str, tuple[int, str]] = {}
    attempt_counts = {"write": {}, "review": {}}  # phase -> module -> count

    for row in job_rows:
        module_key = str(row["module_key"])
        modules.add(module_key)
        latest_job_by_module[module_key] = row

    for row in event_rows:
        module_key = str(row["module_key"])
        event_type = str(row["type"])
        modules.add(module_key)
        latest_event_by_module[module_key] = (int(row["id"]), event_type)
        if event_type == "translation_write_started":
            attempt_counts["write"][module_key] = attempt_counts["write"].get(module_key, 0) + 1
        elif event_type == "translation_verify_started":
            attempt_counts["review"][module_key] = attempt_counts["review"].get(module_key, 0) + 1

    def get_status(m: str) -> str:
        latest_job = latest_job_by_module.get(m)
        latest_event = latest_event_by_module.get(m, (0, ""))
        queue_state = str(latest_job["queue_state"]) if latest_job else ""
        phase = str(latest_job["phase"]) if latest_job else ""
        latest_event_type = latest_event[1]

        if queue_state == "leased":
            return "in_progress"
        if queue_state == "pending":
            return "pending_review" if phase == "review" else "pending_write"
        if latest_event_type in {"translation_verified", "translation_noop"}:
            return "done"
        if latest_event_type in {"needs_human_intervention", "module_dead_lettered"}:
            return "dead_letter"
        if queue_state == "completed" and latest_event_type in {"translation_written", "translation_verify_failed"}:
            return "pending_write" if phase == "review" else "pending_review"
        return "done"

    status_by_module = {module_key: get_status(module_key) for module_key in modules}
    for status in status_by_module.values():
        counts[status] += 1

    pending_review_list = sorted([m for m, status in status_by_module.items() if status == "pending_review"])
    pending_write_list = sorted([m for m, status in status_by_module.items() if status == "pending_write"])
    in_progress_list = sorted([m for m, status in status_by_module.items() if status == "in_progress"])
    done_list = sorted([m for m, status in status_by_module.items() if status == "done"])
    dead_letter_list = sorted([m for m, status in status_by_module.items() if status == "dead_letter"])

    total_modules = len(modules)
    done_count = counts["done"]
    convergence_rate = (done_count / total_modules * 100.0) if total_modules else 0.0
    flapping_count = sum(1 for phase_counts in attempt_counts.values() for c in phase_counts.values() if c > 3)
    needs_human_count = counts["dead_letter"]

    return {
        "db_path": str(db_path),
        "phase_order": phase_order,
        "counts": counts,
        "total_modules": total_modules,
        "convergence_rate": convergence_rate,
        "flapping_count": flapping_count,
        "needs_human_count": needs_human_count,
        "pending_review": pending_review_list,
        "pending_write": pending_write_list,
        "in_progress": in_progress_list,
        "done": done_list,
        "dead_letter": dead_letter_list,
    }


def _has_pending_or_leased_job(db_path: Path, module_key: str) -> bool:
    if not db_path.exists():
        return False
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM jobs
            WHERE module_key = ?
              AND queue_state IN ('pending', 'leased')
            LIMIT 1
            """,
            (_normalize_module_key(module_key),),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def enqueue_translation_targets(
    control_plane: ControlPlane,
    *,
    section: str,
    limit: int | None = None,
    priority_base: int = 100,
) -> list[str]:
    enqueued: list[str] = []
    freshness = build_freshness_report(control_plane.repo_root, section=section)
    candidates = [
        item for item in freshness["modules"] if item["status"] in {"missing", "stale"}
    ]
    for item in candidates:
        module_key = str(item["module_key"])
        if _has_pending_or_leased_job(control_plane.db_path, module_key):
            continue
        control_plane.enqueue(
            module_key,
            phase="write",
            model=TRANSLATE_MODEL,
            priority=priority_base + len(enqueued),
            requested_calls=1,
            estimated_usd=TRANSLATE_ESTIMATED_USD,
        )
        enqueued.append(module_key)
        if limit is not None and len(enqueued) >= limit:
            break
    return enqueued


def _count_attempts(control_plane: ControlPlane, module_key: str, event_type: str) -> int:
    attempts = 0
    for event in control_plane.iter_events(event_type):
        if str(event["module_key"]) == _normalize_module_key(module_key):
            attempts += 1
    return attempts


def _frontmatter_value(frontmatter: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in frontmatter:
            return frontmatter[key]
    return None


def _normalize_lab_metadata_value(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field == "complexity":
        return str(value).strip().upper()
    if field == "time":
        text = " ".join(str(value).split())
        numbers = tuple(re.findall(r"\d+", text))
        return numbers if numbers else text.lower()
    if field == "prerequisites":
        if isinstance(value, list):
            return tuple(_normalize_lab_metadata_value(field, item) for item in value)
        text = " ".join(str(value).split())
        links = tuple(link.strip().lower() for link in _MARKDOWN_LINK_RE.findall(text))
        if links:
            return links
        modules = tuple(match.lower() for match in _MODULE_REF_RE.findall(text))
        return modules if modules else text.lower()
    return value


def _lab_metadata_mismatches(repo_root: Path, module_key: str) -> list[str]:
    en_frontmatter = _extract_frontmatter(_en_path_for_module_key(repo_root, module_key))
    uk_frontmatter = _extract_frontmatter(_uk_path_for_module_key(repo_root, module_key))
    mismatches: list[str] = []
    for label, keys in (
        ("complexity", ("complexity",)),
        ("time", ("time", "time_to_complete")),
        ("prerequisites", ("prerequisites",)),
    ):
        en_value = _frontmatter_value(en_frontmatter, *keys)
        uk_value = _frontmatter_value(uk_frontmatter, *keys)
        if en_value is None and uk_value is None:
            continue
        if _normalize_lab_metadata_value(label, en_value) != _normalize_lab_metadata_value(label, uk_value):
            mismatches.append(label)
    return mismatches


def _verify_translation(repo_root: Path, module_key: str) -> tuple[bool, dict[str, Any]]:
    state = detect_module_state(repo_root, module_key)
    uk_path = _uk_path_for_module_key(repo_root, module_key)
    details: dict[str, Any] = {
        "state": state["status"],
        "issues": list(state.get("issues", [])),
        "uk_path": uk_path.as_posix(),
    }
    if state["status"] != "synced":
        return False, details
    if not uk_path.exists():
        details["issues"].append("missing_uk_file_after_write")
        return False, details

    text = uk_path.read_text(encoding="utf-8")
    quality_errors = [
        check.message
        for check in ukrainian.run_all(text, uk_path)
        if not check.passed and check.severity == "ERROR"
    ]
    if quality_errors:
        details["issues"].extend(quality_errors)
        return False, details
    metadata_mismatches = _lab_metadata_mismatches(repo_root, module_key)
    if metadata_mismatches:
        details["lab_metadata_mismatches"] = metadata_mismatches
        details["issues"].extend(f"lab_metadata_mismatch:{field}" for field in metadata_mismatches)
        return False, details
    return True, details


@dataclass(frozen=True)
class TranslationRunOutcome:
    status: str
    module_key: str | None = None
    lease_id: str | None = None
    details: dict[str, Any] | None = None


class TranslationWorker:
    def __init__(
        self,
        control_plane: ControlPlane,
        *,
        worker_id: str = "translation-worker",
        max_attempts: int = DEFAULT_MAX_WRITE_ATTEMPTS,
        translate_new_fn: Callable[[Path], bool] = uk_translate_new_module,
        fix_fn: Callable[..., bool] = uk_fix_module,
    ):
        self.control_plane = control_plane
        self.worker_id = worker_id
        self.max_attempts = max_attempts
        self.translate_new_fn = translate_new_fn
        self.fix_fn = fix_fn

    def run_once(self) -> TranslationRunOutcome:
        lease = self.control_plane.lease_next_job(
            self.worker_id,
            phase="write",
            requested_calls=1,
            estimated_usd=TRANSLATE_ESTIMATED_USD,
            lease_seconds=DEFAULT_LEASE_SECONDS,
        )
        if lease is None:
            return TranslationRunOutcome(status="idle")

        module_key = _normalize_module_key(lease.module_key)
        self.control_plane.emit_event(
            "translation_write_started",
            module_key=module_key,
            lease_id=lease.lease_id,
            payload={"job_id": lease.job_id, "phase": lease.phase, "worker_id": self.worker_id},
        )
        en_path = _en_path_for_module_key(self.control_plane.repo_root, module_key)
        uk_path = _uk_path_for_module_key(self.control_plane.repo_root, module_key)
        state_before = detect_module_state(self.control_plane.repo_root, module_key)
        mode = "new" if state_before["status"] == "missing" else "fix"

        try:
            if not en_path.exists():
                self.control_plane.fail_lease_terminal(
                    lease.lease_id,
                    reason="missing_en_source",
                    event_payload={"module_key": module_key, "en_path": en_path.as_posix()},
                )
                return TranslationRunOutcome(
                    status="dead_letter",
                    module_key=module_key,
                    lease_id=lease.lease_id,
                    details={"reason": "missing_en_source"},
                )

            if state_before["status"] == "synced":
                self._enqueue_verify(module_key, priority=lease.job_id)
                self.control_plane.complete_lease(
                    lease.lease_id,
                    actual_calls=0,
                    actual_usd=0.0,
                    outcome="translation_written",
                    event_payload={"mode": "noop", "module_key": module_key},
                )
                return TranslationRunOutcome(
                    status="queued_for_verify",
                    module_key=module_key,
                    lease_id=lease.lease_id,
                    details={"mode": "noop"},
                )

            if mode == "new":
                ok = self.translate_new_fn(en_path)
            else:
                ok = self.fix_fn(uk_path, strict_commit=True)

            if ok:
                state_after = detect_module_state(self.control_plane.repo_root, module_key)
            else:
                state_after = {
                    "status": "unknown",
                    "issues": ["translation_call_failed"],
                    "uk_path": uk_path.as_posix(),
                }

            if ok and state_after["status"] == "synced":
                self._enqueue_verify(module_key, priority=lease.job_id)
                self.control_plane.complete_lease(
                    lease.lease_id,
                    actual_calls=1,
                    actual_usd=TRANSLATE_ESTIMATED_USD,
                    outcome="translation_written",
                    event_payload={"mode": mode, **state_after},
                )
                return TranslationRunOutcome(
                    status="queued_for_verify",
                    module_key=module_key,
                    lease_id=lease.lease_id,
                    details={"mode": mode, **state_after},
                )

            attempts = _count_attempts(self.control_plane, module_key, "translation_write_started")
            payload = {"mode": mode, "attempts": attempts, **state_after}
            if attempts >= self.max_attempts:
                self.control_plane.fail_lease_terminal(
                    lease.lease_id,
                    reason="translation_write_failed",
                    event_payload=payload,
                )
                return TranslationRunOutcome(
                    status="dead_letter",
                    module_key=module_key,
                    lease_id=lease.lease_id,
                    details=payload,
                )

            self.control_plane.release_lease(lease.lease_id, reason="translation_verify_failed")
            self.control_plane.emit_event(
                "translation_retry_scheduled",
                module_key=module_key,
                payload=payload,
            )
            return TranslationRunOutcome(
                status="retry_scheduled",
                module_key=module_key,
                lease_id=lease.lease_id,
                details=payload,
            )
        except Exception as exc:
            attempts = _count_attempts(self.control_plane, module_key, "translation_write_started")
            payload = {"mode": mode, "attempts": attempts, "error": str(exc)}
            if attempts >= self.max_attempts:
                self.control_plane.fail_lease_terminal(
                    lease.lease_id,
                    reason="translation_worker_error",
                    event_payload=payload,
                )
                return TranslationRunOutcome(
                    status="dead_letter",
                    module_key=module_key,
                    lease_id=lease.lease_id,
                    details=payload,
                )
            self.control_plane.release_lease(lease.lease_id, reason="translation_worker_error")
            self.control_plane.emit_event(
                "translation_retry_scheduled",
                module_key=module_key,
                payload=payload,
            )
            return TranslationRunOutcome(
                status="retry_scheduled",
                module_key=module_key,
                lease_id=lease.lease_id,
                details=payload,
            )

    def loop_forever(self, *, sleep_seconds: float = 5.0) -> None:
        while True:
            outcome = self.run_once()
            if outcome.status == "idle":
                time.sleep(sleep_seconds)

    def _enqueue_verify(self, module_key: str, *, priority: int) -> None:
        self.control_plane.enqueue(
            module_key,
            phase="review",
            model=VERIFY_MODEL,
            priority=priority,
            requested_calls=1,
            estimated_usd=0.0,
        )


class VerifyWorker:
    def __init__(
        self,
        control_plane: ControlPlane,
        *,
        worker_id: str = "translation-verify-worker",
        max_attempts: int = DEFAULT_MAX_VERIFY_ATTEMPTS,
    ):
        self.control_plane = control_plane
        self.worker_id = worker_id
        self.max_attempts = max_attempts

    def run_once(self) -> TranslationRunOutcome:
        lease = self.control_plane.lease_next_job(
            self.worker_id,
            phase="review",
            requested_calls=1,
            estimated_usd=0.0,
            lease_seconds=300,
        )
        if lease is None:
            return TranslationRunOutcome(status="idle")

        module_key = _normalize_module_key(lease.module_key)
        self.control_plane.emit_event(
            "translation_verify_started",
            module_key=module_key,
            lease_id=lease.lease_id,
            payload={"job_id": lease.job_id, "phase": lease.phase, "worker_id": self.worker_id},
        )

        verified, details = _verify_translation(self.control_plane.repo_root, module_key)
        details = {"attempts": _count_attempts(self.control_plane, module_key, "translation_verify_started"), **details}
        if verified:
            self.control_plane.complete_lease(
                lease.lease_id,
                actual_calls=0,
                actual_usd=0.0,
                outcome="translation_verified",
                event_payload=details,
            )
            return TranslationRunOutcome(
                status="completed",
                module_key=module_key,
                lease_id=lease.lease_id,
                details=details,
            )

        if details["attempts"] >= self.max_attempts:
            self.control_plane.fail_lease_terminal(
                lease.lease_id,
                reason="translation_verify_failed",
                event_payload=details,
            )
            return TranslationRunOutcome(
                status="dead_letter",
                module_key=module_key,
                lease_id=lease.lease_id,
                details=details,
            )

        self.control_plane.enqueue(
            module_key,
            phase="write",
            model=TRANSLATE_MODEL,
            priority=lease.job_id,
            requested_calls=1,
            estimated_usd=TRANSLATE_ESTIMATED_USD,
        )
        self.control_plane.complete_lease(
            lease.lease_id,
            actual_calls=0,
            actual_usd=0.0,
            outcome="translation_verify_failed",
            event_payload={**details, "retry_scheduled": True},
        )
        self.control_plane.emit_event(
            "translation_retry_scheduled",
            module_key=module_key,
            payload=details,
        )
        return TranslationRunOutcome(
            status="retry_scheduled",
            module_key=module_key,
            lease_id=lease.lease_id,
            details=details,
        )

    def loop_forever(self, *, sleep_seconds: float = 5.0) -> None:
        while True:
            outcome = self.run_once()
            if outcome.status == "idle":
                time.sleep(sleep_seconds)


def _print_status(data: dict[str, Any]) -> None:
    freshness = data["freshness"]
    queue = data["queue"]
    section = data["section"] or "(all)"
    print("Translation v2 Status")
    print()
    print(f"Section: {section}")
    print(
        f"Freshness: synced={freshness['synced']} missing={freshness['missing']} "
        f"stale={freshness['stale']} unknown={freshness['unknown']} clean={'YES' if freshness['sync_clean'] else 'NO'}"
    )
    if queue is None:
        print("Queue: missing DB")
        return
    print(
        f"Queue: total={queue['total_modules']} convergence={queue['convergence_rate']:.1f}% "
        f"in_progress={queue['counts']['in_progress']} dead_letter={queue['counts']['dead_letter']}"
    )
    print(
        "  "
        f"verify={queue['counts']['pending_review']} "
        f"translate={queue['counts']['pending_write']} "
        f"done={queue['counts']['done']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translation v2 control plane")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show queue + freshness status")
    status.add_argument("--section")
    status.add_argument("--json", action="store_true")

    enqueue = subparsers.add_parser("enqueue-section", help="Enqueue missing/stale modules in a section")
    enqueue.add_argument("section")
    enqueue.add_argument("--limit", type=int)

    enqueue_module = subparsers.add_parser("enqueue-module", help="Enqueue a single module explicitly")
    enqueue_module.add_argument("module_key")
    enqueue_module.add_argument("--phase", choices=["write", "review"], default="write")

    worker = subparsers.add_parser("worker", help="Run translation worker")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    worker_run = worker_sub.add_parser("run", help="Translate one queued module")
    worker_run.add_argument("--worker-id", default="translation-worker")
    worker_run.add_argument("--json", action="store_true")
    worker_run.add_argument("--max-calls", type=int)
    worker_loop = worker_sub.add_parser("loop", help="Run translation worker loop")
    worker_loop.add_argument("--worker-id", default="translation-worker")
    worker_loop.add_argument("--sleep-seconds", type=float, default=5.0)
    worker_loop.add_argument("--max-calls", type=int)

    verify_worker = subparsers.add_parser("verify-worker", help="Run translation verify worker")
    verify_sub = verify_worker.add_subparsers(dest="verify_worker_command", required=True)
    verify_run = verify_sub.add_parser("run", help="Verify one translated module")
    verify_run.add_argument("--worker-id", default="translation-verify-worker")
    verify_run.add_argument("--json", action="store_true")
    verify_loop = verify_sub.add_parser("loop", help="Run translation verify worker loop")
    verify_loop.add_argument("--worker-id", default="translation-verify-worker")
    verify_loop.add_argument("--sleep-seconds", type=float, default=5.0)

    watchdog = subparsers.add_parser("watchdog", help="Release expired leases")
    watchdog_sub = watchdog.add_subparsers(dest="watchdog_command", required=True)
    watchdog_sub.add_parser("sweep", help="Release expired leases once")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    def _worker_log_outcome(outcome: TranslationRunOutcome) -> None:
        attempts = None
        if outcome.details:
            attempts = outcome.details.get("attempts")
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module_key": outcome.module_key,
            "status": outcome.status,
            "lease_id": outcome.lease_id,
            "attempts": attempts,
        }
        print(f"[worker] {json.dumps(payload, sort_keys=True)}")

    def _worker_summary(successful_calls: int, max_calls: int | None) -> None:
        if max_calls is None:
            return
        print(f"worker summary: max_calls={max_calls} successful_calls={successful_calls}")

    if args.command == "status":
        report = build_status(args.repo_root, db_path=args.db, section=args.section)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_status(report)
        return 0

    control_plane = ControlPlane(repo_root=args.repo_root, db_path=args.db, budgets_path=args.budgets)

    if args.command == "enqueue-section":
        enqueued = enqueue_translation_targets(control_plane, section=args.section, limit=args.limit)
        print(f"enqueued {len(enqueued)} modules")
        for module_key in enqueued:
            print(module_key)
        return 0

    if args.command == "enqueue-module":
        control_plane.enqueue(
            _normalize_module_key(args.module_key),
            phase=args.phase,
            model=TRANSLATE_MODEL if args.phase == "write" else VERIFY_MODEL,
            requested_calls=1,
            estimated_usd=TRANSLATE_ESTIMATED_USD if args.phase == "write" else 0.0,
        )
        print(f"enqueued {_normalize_module_key(args.module_key)} ({args.phase})")
        return 0

    if args.command == "worker":
        worker = TranslationWorker(control_plane, worker_id=args.worker_id)
        if args.worker_command == "run":
            outcome = worker.run_once()
            successful_calls = 1 if outcome.status == "queued_for_verify" else 0
            if args.json:
                print(json.dumps(outcome.__dict__, indent=2, sort_keys=True))
            else:
                print(outcome.status)
                if outcome.module_key:
                    print(outcome.module_key)
                if args.max_calls is not None and successful_calls >= args.max_calls:
                    _worker_summary(successful_calls, args.max_calls)
            return 0
        if args.worker_command == "loop":
            successful_calls = 0
            while True:
                outcome = worker.run_once()
                _worker_log_outcome(outcome)
                if outcome.status == "queued_for_verify":
                    successful_calls += 1
                    if args.max_calls is not None and successful_calls >= args.max_calls:
                        _worker_summary(successful_calls, args.max_calls)
                        return 0
                if outcome.status == "idle":
                    time.sleep(args.sleep_seconds)
            return 0

    if args.command == "verify-worker":
        worker = VerifyWorker(control_plane, worker_id=args.worker_id)
        if args.verify_worker_command == "run":
            outcome = worker.run_once()
            if args.json:
                print(json.dumps(outcome.__dict__, indent=2, sort_keys=True))
            else:
                print(outcome.status)
                if outcome.module_key:
                    print(outcome.module_key)
            return 0
        if args.verify_worker_command == "loop":
            worker.loop_forever(sleep_seconds=args.sleep_seconds)
            return 0

    if args.command == "watchdog" and args.watchdog_command == "sweep":
        released = control_plane.sweep_once()
        print(f"released {released} leases")
        return 0

    parser.error(f"Unhandled command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
