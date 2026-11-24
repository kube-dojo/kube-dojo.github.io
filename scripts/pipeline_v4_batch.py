#!/usr/bin/env python3
"""Sequential-by-default runner for pipeline_v4 across a module set.

Selects low-scored modules from the local-api quality scores and runs
pipeline_v4 on each. Each module is claimed via a per-module SQLite
lease in .pipeline/v2.db so two separate batch processes (e.g. two
terminals, or a crashed batch restarting) never touch the same module
at the same time.

**Default --workers is 1.** Pipeline v4 internally dispatches Gemini
(no_quiz + thin expansion) and a pipeline_v3 subprocess (citation_v3
— also uses Gemini). Gemini rate-limits on parallel calls and returns
429 MODEL_CAPACITY_EXHAUSTED. 2 or 3 workers can be safe when no
other Gemini workloads (translations, reviews) are running.
--workers is hard-capped at MAX_WORKERS=3 — values above that are
clamped with a warning. The lease coordination matters primarily
across processes (resumable, crash-safe), not for within-process
parallelism.

Usage:
    .venv/bin/python scripts/pipeline_v4_batch.py --track /ai --limit 5
    .venv/bin/python scripts/pipeline_v4_batch.py \\
        --track ai-ml-engineering/ai-infrastructure --limit 5
    .venv/bin/python scripts/pipeline_v4_batch.py --limit 1 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, SCRIPTS_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

import local_api  # noqa: E402
import pipeline_v4  # noqa: E402
import rubric_gaps  # noqa: E402

DB_PATH = REPO_ROOT / ".pipeline" / "v2.db"
DEFAULT_LEASE_SECONDS = 1800
# Gemini rate-limits on parallel calls (429 MODEL_CAPACITY_EXHAUSTED),
# and pipeline_v4's internal dispatches to Gemini are the dominant
# cost. Default is sequential; raising to 2-3 can be safe when the
# user has no other Gemini workloads running, but anything above 3
# hits rate limits hard. The hard cap enforces that — the script
# clamps any --workers > MAX_WORKERS down to MAX_WORKERS with a
# stderr warning.
DEFAULT_WORKERS = 1
MAX_WORKERS = 3
DEFAULT_MAX_SCORE = 4.0

LEASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS v4_batch_leases (
    module_key TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    leased_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    completed_at INTEGER,
    outcome TEXT
);
CREATE INDEX IF NOT EXISTS idx_v4_batch_expires ON v4_batch_leases(expires_at);
"""

OUTCOME_SKIPPED_LOCKED = "skipped_locked"
OUTCOME_ERROR = "error"
OUTCOME_CLEAN = "clean"
# ATX H2 named "Sources", anchored to start-of-line, trailing whitespace OK.
# Mirrors the convention used in other repo checkers; tolerates
# `## Sources  \n` and EOF-without-final-newline per Codex #359 review.
SOURCES_HEADER_RE = re.compile(r"^##\s+Sources\s*$", re.MULTILINE)

_INIT_LOCK = threading.Lock()
_INITIALIZED_DBS: set[str] = set()


@dataclass
class ModuleCandidate:
    module_key: str
    score: float
    path: str
    primary_issue: str


def _ensure_schema() -> None:
    """Create the v4_batch_leases table once per DB path.

    Running CREATE TABLE IF NOT EXISTS from multiple threads on a single
    sqlite file can race: concurrent executescript() calls contend for
    the write lock and one raises OperationalError("database is locked").
    Serializing schema creation per path avoids that without impacting
    row-level operations, which use WAL-mode BEGIN IMMEDIATE and are
    safe to interleave."""
    key = str(DB_PATH)
    if key in _INITIALIZED_DBS:
        return
    with _INIT_LOCK:
        if key in _INITIALIZED_DBS:
            return
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        setup = sqlite3.connect(DB_PATH, timeout=30)
        try:
            setup.execute("PRAGMA journal_mode=WAL")
            setup.executescript(LEASE_SCHEMA)
            setup.commit()
        finally:
            setup.close()
        _INITIALIZED_DBS.add(key)


def _connect() -> sqlite3.Connection:
    _ensure_schema()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def acquire_lease(module_key: str, worker_id: str, lease_seconds: int) -> bool:
    """Atomically claim module_key. Returns False if another worker holds a
    non-expired non-completed lease.

    Stale leases (expired or completed) are evicted inside the same transaction
    so repeat batch runs don't accumulate dead rows."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            DELETE FROM v4_batch_leases
            WHERE module_key = ?
              AND (completed_at IS NOT NULL
                   OR expires_at <= CAST(strftime('%s','now') AS INTEGER))
            """,
            (module_key,),
        )
        try:
            conn.execute(
                """
                INSERT INTO v4_batch_leases
                  (module_key, worker_id, leased_at, expires_at)
                VALUES (
                    ?, ?,
                    CAST(strftime('%s','now') AS INTEGER),
                    CAST(strftime('%s','now') AS INTEGER) + ?
                )
                """,
                (module_key, worker_id, lease_seconds),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            return False
    finally:
        conn.close()


def complete_lease(module_key: str, worker_id: str, outcome: str) -> None:
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE v4_batch_leases
            SET completed_at = CAST(strftime('%s','now') AS INTEGER),
                outcome = ?
            WHERE module_key = ? AND worker_id = ?
            """,
            (outcome, module_key, worker_id),
        )
        conn.commit()
    finally:
        conn.close()


def release_lease(module_key: str, worker_id: str) -> None:
    """Drop an active lease without marking it complete (e.g. on crash)."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            DELETE FROM v4_batch_leases
            WHERE module_key = ?
              AND worker_id = ?
              AND completed_at IS NULL
            """,
            (module_key, worker_id),
        )
        conn.commit()
    finally:
        conn.close()


def _normalize_track(track: str | None) -> str | None:
    if not track:
        return None
    trimmed = track.strip().strip("/")
    return trimmed or None


def select_candidates(
    *,
    track: str | None = None,
    limit: int | None = None,
    min_score: float | None = None,
    max_score: float = DEFAULT_MAX_SCORE,
    skip_citation: bool = False,
    quality_fetch: Callable[[Path], dict[str, Any]] | None = None,
) -> list[ModuleCandidate]:
    """Pull candidates from local_api quality scores and filter by
    track / min-score / max-score. Sorted lowest-score first so the
    neediest modules run first."""
    fetch = quality_fetch or local_api.build_quality_scores
    payload = fetch(REPO_ROOT)
    modules = payload.get("modules") or []
    track_prefix = _normalize_track(track)
    candidates: list[ModuleCandidate] = []
    for entry in modules:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            continue
        if track_prefix and not path.startswith(f"{track_prefix}/"):
            continue
        raw_score = entry.get("score")
        if raw_score is None:
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if score >= max_score:
            continue
        if min_score is not None and score < min_score:
            continue
        module_key = path[:-3] if path.endswith(".md") else path
        primary_issue = entry.get("primary_issue") or ""
        gaps = rubric_gaps.parse_primary_issue(str(primary_issue))
        # With --skip-citation, Stage 4 won't run, so a module needs at
        # least one expand-handlable gap to be worth selecting. Pure
        # Stage-4-only gap lists (["no_citations"], ["no_diagram"]) get
        # excluded; mixed lists like ["no_citations", "no_quiz"] stay,
        # because Stage 2 can still fill the quiz.
        if skip_citation and gaps and not pipeline_v4.expand_module.can_expand(gaps):
            continue
        candidates.append(
            ModuleCandidate(
                module_key=module_key,
                score=score,
                path=path,
                primary_issue=str(primary_issue),
            )
        )
    candidates.sort(key=lambda c: (c.score, c.module_key))
    if limit is not None:
        candidates = candidates[:limit]
    return candidates


def _run_one(
    candidate: ModuleCandidate,
    *,
    worker_id: str,
    dry_run: bool,
    skip_citation: bool,
    lease_seconds: int,
    runner: Callable[..., pipeline_v4.PipelineV4Result] = pipeline_v4.run_pipeline_v4,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "module_key": candidate.module_key,
        "worker_id": worker_id,
        "score_before": candidate.score,
    }
    if not acquire_lease(candidate.module_key, worker_id, lease_seconds):
        return {**base, "outcome": OUTCOME_SKIPPED_LOCKED}
    try:
        result = runner(
            candidate.module_key,
            dry_run=dry_run,
            skip_citation=skip_citation,
        )
        payload: dict[str, Any] = {
            **base,
            "outcome": result.outcome,
            "stage_reached": result.stage_reached,
            "score_after": result.score_after,
            "gaps_before": list(result.gaps_before),
            "gaps_after": list(result.gaps_after),
            "retry_count": result.retry_count,
            "citation_v3_exit": result.citation_v3_exit,
            "reason": result.reason,
        }
        complete_lease(candidate.module_key, worker_id, result.outcome)
        return payload
    except Exception as exc:
        release_lease(candidate.module_key, worker_id)
        return {
            **base,
            "outcome": OUTCOME_ERROR,
            "error": f"{type(exc).__name__}: {exc}",
        }


def audit_missing_sources(
    results: list[dict[str, Any]],
    *,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Return module_keys reported `outcome=clean` whose file has no
    ``## Sources`` section (GH #351).

    Context: during PR #350 (batch-c cloud), citation_v3 silently left
    two of 78 modules with no Sources section at all while reporting
    them clean. A post-batch audit makes that class of silent failure
    loud — and cheap: `(str | PurePath).read_text().__contains__()`
    per module.

    Leading newline guards against false-positives where "## Sources"
    appears mid-line in a code block or prose.
    """
    violations: list[str] = []
    for r in results:
        if r.get("outcome") != OUTCOME_CLEAN:
            continue
        module_key = r.get("module_key")
        if not module_key:
            continue
        module_path = repo_root / "src" / "content" / "docs" / f"{module_key}.md"
        if not module_path.exists():
            violations.append(module_key)
            continue
        text = module_path.read_text(encoding="utf-8")
        # MULTILINE regex against an ATX H2 named "Sources" with optional
        # trailing whitespace. Start-of-line anchor avoids false-positives
        # from the string appearing mid-prose; trailing \s* tolerates the
        # `## Sources  ` (trailing spaces) and EOF-without-newline cases
        # Codex flagged on PR #359.
        if not SOURCES_HEADER_RE.search(text):
            violations.append(module_key)
    return violations


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_outcome: dict[str, int] = {}
    score_delta_total = 0.0
    processed_with_delta = 0
    for r in results:
        outcome = str(r.get("outcome", "unknown"))
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        score_after = r.get("score_after")
        score_before = r.get("score_before")
        if (
            score_after is not None
            and isinstance(score_before, (int, float))
            and isinstance(score_after, (int, float))
        ):
            score_delta_total += float(score_after) - float(score_before)
            processed_with_delta += 1
    avg_delta = (
        score_delta_total / processed_with_delta if processed_with_delta else 0.0
    )
    return {
        "processed": len(results),
        "by_outcome": by_outcome,
        "score_delta_total": round(score_delta_total, 3),
        "score_delta_avg": round(avg_delta, 3),
    }


def run_batch(
    *,
    track: str | None = None,
    limit: int | None = None,
    workers: int = DEFAULT_WORKERS,
    min_score: float | None = None,
    max_score: float = DEFAULT_MAX_SCORE,
    dry_run: bool = False,
    skip_citation: bool = False,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    runner: Callable[..., pipeline_v4.PipelineV4Result] | None = None,
    quality_fetch: Callable[[Path], dict[str, Any]] | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if workers > MAX_WORKERS:
        print(
            f"[pipeline_v4_batch] WARNING: --workers {workers} exceeds "
            f"MAX_WORKERS={MAX_WORKERS}; clamping. Gemini rate-limits on "
            "parallel calls; more than 3 concurrent pipelines will hit "
            "429 MODEL_CAPACITY_EXHAUSTED.",
            file=sys.stderr,
        )
        workers = MAX_WORKERS
    if workers > 1 and not dry_run and runner is None:
        print(
            f"[pipeline_v4_batch] NOTE: --workers {workers} fires "
            f"{workers} concurrent Gemini dispatches. Safe only when no "
            "other Gemini workloads (translations, reviews) are running.",
            file=sys.stderr,
        )
    started_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    candidates = select_candidates(
        track=track,
        limit=limit,
        min_score=min_score,
        max_score=max_score,
        skip_citation=skip_citation,
        quality_fetch=quality_fetch,
    )
    _emit = emit or (lambda payload: print(json.dumps(payload, ensure_ascii=False), flush=True))

    if not candidates:
        summary = {
            "started_at": started_at,
            "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "processed": 0,
            "by_outcome": {},
            "score_delta_total": 0.0,
            "score_delta_avg": 0.0,
            "reason": "no_candidates",
        }
        _emit({"summary": summary})
        return summary

    run_kwargs: dict[str, Any] = {
        "dry_run": dry_run,
        "skip_citation": skip_citation,
        "lease_seconds": lease_seconds,
    }
    if runner is not None:
        run_kwargs["runner"] = runner

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                _run_one,
                cand,
                worker_id=f"v4_batch_{os.getpid()}_{idx}",
                **run_kwargs,
            ): cand
            for idx, cand in enumerate(candidates)
        }
        for fut in as_completed(futures):
            try:
                res = fut.result()
            except Exception as exc:
                cand = futures[fut]
                res = {
                    "module_key": cand.module_key,
                    "score_before": cand.score,
                    "outcome": OUTCOME_ERROR,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            results.append(res)
            _emit(res)

    summary = {
        "started_at": started_at,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        **_summarize(results),
        "results": results,
    }
    _emit({"summary": summary})
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--track",
        default=None,
        help="Filter modules whose path starts with this prefix (e.g. /ai, /k8s/cka).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N modules.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            f"Concurrent worker count (default {DEFAULT_WORKERS}, max "
            f"{MAX_WORKERS}). Gemini rate-limits on parallel calls: "
            "2-3 workers is OK when no other Gemini workloads are running, "
            "above 3 trips 429s. Values above the cap are clamped with a "
            "warning."
        ),
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Only run modules scored at or above this threshold.",
    )
    parser.add_argument(
        "--max-score",
        type=float,
        default=DEFAULT_MAX_SCORE,
        help=f"Only run modules scored below this threshold (default {DEFAULT_MAX_SCORE}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run through to pipeline_v4 (skip disk writes and citation).",
    )
    parser.add_argument(
        "--skip-citation",
        action="store_true",
        help="Pass --skip-citation through to pipeline_v4 (run Stages 1-3 only).",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=DEFAULT_LEASE_SECONDS,
        help=f"Lease TTL per module in seconds (default {DEFAULT_LEASE_SECONDS}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = run_batch(
        track=args.track,
        limit=args.limit,
        workers=args.workers,
        min_score=args.min_score,
        max_score=args.max_score,
        dry_run=args.dry_run,
        skip_citation=args.skip_citation,
        lease_seconds=args.lease_seconds,
    )
    exit_code = 0 if summary["by_outcome"].get(OUTCOME_ERROR, 0) == 0 else 1
    # Post-batch silent-failure audit (GH #351): a module reported
    # `outcome=clean` but missing a `## Sources` section is the
    # regression class we hit in PR #350. Surface it loudly so the
    # operator sees it before running another bulk batch.
    #
    # Skip the audit for:
    #   - `--dry-run`: no module edits occurred, violations would be spurious.
    #   - `--skip-citation`: pipeline_v4 explicitly skips Stage 4
    #     (citation_v3) and can still return outcome=clean when the
    #     module lifts from no-quiz / no-exercise work alone. A missing
    #     Sources section is the operator's choice in that mode, not a
    #     regression. See Codex #359 review, must-fix #1.
    if not args.dry_run and not args.skip_citation:
        violations = audit_missing_sources(summary.get("results") or [])
        if violations:
            print(
                f"\nPost-batch audit FAILED: {len(violations)} module(s) "
                "reported outcome=clean but have no `## Sources` section:",
                file=sys.stderr,
            )
            for module_key in violations:
                print(f"  - {module_key}", file=sys.stderr)
            exit_code = max(exit_code, 1)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
