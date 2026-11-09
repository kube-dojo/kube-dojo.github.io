from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

DEFAULT_BUDGETS_PATH = None
DEFAULT_DB_PATH = None
REVIEW_MODEL = "removed"
WRITE_MODEL = "removed"


class ControlPlane:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


def _record_event(*_args, **_kwargs):
    raise RuntimeError("legacy dispatcher removed")


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = REPO_ROOT / ".pipeline" / "state.yaml"


@dataclass
class MigrationSummary:
    state_path: str
    dry_run: bool
    total_modules: int = 0
    migrated_done: int = 0
    enqueued_review: int = 0
    enqueued_write: int = 0
    marked_manual_triage: int = 0
    skipped_existing: int = 0
    skipped_missing_path: int = 0

    @property
    def migrated(self) -> int:
        return (
            self.migrated_done
            + self.enqueued_review
            + self.enqueued_write
            + self.marked_manual_triage
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_path": self.state_path,
            "dry_run": self.dry_run,
            "total_modules": self.total_modules,
            "migrated": self.migrated,
            "migrated_done": self.migrated_done,
            "enqueued_review": self.enqueued_review,
            "enqueued_write": self.enqueued_write,
            "marked_manual_triage": self.marked_manual_triage,
            "skipped_existing": self.skipped_existing,
            "skipped_missing_path": self.skipped_missing_path,
        }

    def render_text(self) -> str:
        mode = "DRY RUN" if self.dry_run else "APPLIED"
        return "\n".join(
            [
                f"v1 -> v2 migration summary ({mode})",
                f"state: {self.state_path}",
                f"total modules: {self.total_modules}",
                f"migrated: {self.migrated}",
                f"  done events: {self.migrated_done}",
                f"  review jobs: {self.enqueued_review}",
                f"  write jobs: {self.enqueued_write}",
                f"  manual triage: {self.marked_manual_triage}",
                f"skipped existing: {self.skipped_existing}",
                f"skipped missing path: {self.skipped_missing_path}",
            ]
        )


def migrate_v1_to_v2(
    control_plane: ControlPlane,
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    dry_run: bool = False,
    module_resolver: Callable[[str], Path | None] | None = None,
) -> MigrationSummary:
    raw_state = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    modules = raw_state.get("modules") or {}
    summary = MigrationSummary(state_path=str(state_path), dry_run=dry_run)

    for raw_key, module_state in sorted(modules.items()):
        summary.total_modules += 1
        try:
            module_key = _resolve_module_key(
                str(raw_key),
                repo_root=control_plane.repo_root,
                module_resolver=module_resolver,
            )
        except FileNotFoundError:
            summary.skipped_missing_path += 1
            continue

        normalized_phase = _normalize_phase(module_state)
        if _module_already_migrated(control_plane.db_path, module_key):
            summary.skipped_existing += 1
            continue

        if not dry_run:
            _migrate_module(
                control_plane,
                module_key=module_key,
                raw_module_key=str(raw_key),
                module_state=module_state,
                normalized_phase=normalized_phase,
            )

        if normalized_phase == "done":
            summary.migrated_done += 1
        elif normalized_phase == "review":
            summary.enqueued_review += 1
        elif normalized_phase in {"pending", "audit"}:
            summary.enqueued_write += 1
        elif normalized_phase == "data_conflict":
            summary.marked_manual_triage += 1
        else:
            summary.enqueued_write += 1

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate v1 state.yaml into v2.db")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to .pipeline/v2.db")
    parser.add_argument(
        "--budgets",
        type=Path,
        default=DEFAULT_BUDGETS_PATH,
        help="Path to .pipeline/budgets.yaml",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to v1 .pipeline/state.yaml",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan migration without writing v2.db")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    control_plane = ControlPlane(db_path=args.db, budgets_path=args.budgets)
    summary = migrate_v1_to_v2(control_plane, state_path=args.state, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    else:
        print(summary.render_text())
    return 0


def _resolve_module_key(
    raw_key: str,
    *,
    repo_root: Path,
    module_resolver: Callable[[str], Path | None] | None,
) -> str:
    if raw_key.endswith(".md"):
        candidate = Path(raw_key)
        if not candidate.is_absolute():
            candidate = repo_root / raw_key
        if candidate.exists():
            return str(candidate.resolve().relative_to(repo_root.resolve()))

    resolver = module_resolver or _default_module_resolver
    resolved = resolver(raw_key)
    if resolved is None or not resolved.exists():
        raise FileNotFoundError(raw_key)
    return str(resolved.resolve().relative_to(repo_root.resolve()))


def _default_module_resolver(raw_key: str) -> Path | None:
    from v1_pipeline import find_module_path

    return find_module_path(raw_key)


def _normalize_phase(module_state: dict[str, Any]) -> str:
    phase = str(module_state.get("phase", "pending") or "pending")
    if phase == "write":
        return "pending"
    return phase


def _module_already_migrated(db_path: Path, module_key: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT
                EXISTS(SELECT 1 FROM events WHERE module_key = ?) AS has_events,
                EXISTS(SELECT 1 FROM jobs WHERE module_key = ?) AS has_jobs
            """,
            (module_key, module_key),
        ).fetchone()
        assert row is not None
        return bool(row[0] or row[1])
    finally:
        conn.close()


def _migrate_module(
    control_plane: ControlPlane,
    *,
    module_key: str,
    raw_module_key: str,
    module_state: dict[str, Any],
    normalized_phase: str,
) -> None:
    conn = control_plane._connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if _module_already_migrated_in_conn(conn, module_key):
            conn.commit()
            return

        base_payload = {
            "source": "v1_state",
            "synthetic": True,
            "v1_phase": str(module_state.get("phase", "pending") or "pending"),
            "v1_module_key": raw_module_key,
        }
        _record_event(
            conn,
            "module_created",
            module_key=module_key,
            payload=base_payload,
        )

        if normalized_phase == "done":
            _record_event(
                conn,
                "done",
                module_key=module_key,
                payload=base_payload,
            )
        elif normalized_phase == "review":
            _record_event(
                conn,
                "attempt_succeeded",
                module_key=module_key,
                payload={**base_payload, "phase": "write"},
            )
            _insert_job(
                conn,
                module_key=module_key,
                phase="review",
                model=REVIEW_MODEL,
                queue_state="pending",
                priority=100,
                idempotency_key=f"migrate-v1:{module_key}:review",
                payload={**base_payload, "phase": "review", "model": REVIEW_MODEL},
            )
        elif normalized_phase in {"pending", "audit"}:
            _insert_job(
                conn,
                module_key=module_key,
                phase="write",
                model=WRITE_MODEL,
                queue_state="pending",
                priority=100,
                idempotency_key=f"migrate-v1:{module_key}:write",
                payload={**base_payload, "phase": "write", "model": WRITE_MODEL},
            )
        elif normalized_phase == "data_conflict":
            job_id = _insert_job(
                conn,
                module_key=module_key,
                phase="write",
                model=WRITE_MODEL,
                queue_state="failed",
                priority=100,
                idempotency_key=f"migrate-v1:{module_key}:failed",
                payload=None,
            )
            failure_payload = {**base_payload, "job_id": job_id, "reason": "data_conflict"}
            _record_event(
                conn,
                "needs_human_intervention",
                module_key=module_key,
                payload=failure_payload,
            )
            _record_event(
                conn,
                "module_dead_lettered",
                module_key=module_key,
                payload=failure_payload,
            )
        else:
            _insert_job(
                conn,
                module_key=module_key,
                phase="write",
                model=WRITE_MODEL,
                queue_state="pending",
                priority=100,
                idempotency_key=f"migrate-v1:{module_key}:write",
                payload={**base_payload, "phase": "write", "model": WRITE_MODEL},
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _module_already_migrated_in_conn(conn: sqlite3.Connection, module_key: str) -> bool:
    row = conn.execute(
        """
        SELECT
            EXISTS(SELECT 1 FROM events WHERE module_key = ?) AS has_events,
            EXISTS(SELECT 1 FROM jobs WHERE module_key = ?) AS has_jobs
        """,
        (module_key, module_key),
    ).fetchone()
    assert row is not None
    return bool(row[0] or row[1])


def _insert_job(
    conn: sqlite3.Connection,
    *,
    module_key: str,
    phase: str,
    model: str,
    queue_state: str,
    priority: int,
    idempotency_key: str,
    payload: dict[str, Any] | None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO jobs (
            module_key, phase, model, priority, queue_state,
            requested_calls, estimated_usd, idempotency_key
        ) VALUES (?, ?, ?, ?, ?, 1, 0, ?)
        """,
        (
            module_key,
            phase,
            model,
            priority,
            queue_state,
            idempotency_key,
        ),
    )
    job_id = int(cursor.lastrowid)
    if queue_state == "pending" and payload is not None:
        _record_event(
            conn,
            "job_enqueued",
            module_key=module_key,
            payload={
                "job_id": job_id,
                "phase": phase,
                "model": model,
                "priority": priority,
                "requested_calls": 1,
                "estimated_usd": 0.0,
                "idempotency_key": idempotency_key,
                **payload,
            },
        )
    return job_id


if __name__ == "__main__":
    raise SystemExit(main())
