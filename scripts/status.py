#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from translation_v2 import build_status as build_translation_v2_status
from ztt_status import build_status as build_ztt_status

GEMINI_WRITER_MODEL = "gemini-3.1-pro-high"



def _current_dead_letter_rows(event_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_dead_by_module: dict[str, dict[str, Any]] = {}
    latest_recovery_order: dict[str, tuple[int, int]] = {}
    for event in sorted(event_rows, key=lambda row: (int(row["at"]), int(row.get("id", 0)))):
        module_key = str(event["module_key"])
        event_type = str(event["type"])
        at = int(event["at"])
        event_id = int(event.get("id", 0))
        if event_type == "dead_letter_recovered":
            latest_recovery_order[module_key] = (at, event_id)
            continue
        if event_type not in {"needs_human_intervention", "module_dead_lettered"}:
            continue
        payload = json.loads(str(event["payload_json"] or "{}"))
        latest_dead_by_module[module_key] = {
            "module_key": module_key,
            "id": event_id,
            "reason": payload.get("reason"),
            "rewrite_attempts": payload.get("rewrite_attempts"),
            "at": at,
        }
    unresolved = [
        row
        for module_key, row in latest_dead_by_module.items()
        if latest_recovery_order.get(module_key, (-1, -1))
        < (int(row["at"]), int(row.get("id", 0)))
    ]
    return sorted(unresolved, key=lambda row: (row["module_key"], int(row["at"])))


def _module_status(
    job_state: dict[str, Any] | None,
    event_types: set[str],
    *,
    dead_lettered: bool,
) -> str:
    pending_phases = set(job_state["pending_phases"]) if job_state else set()
    has_leased = bool(job_state and job_state["has_leased"])
    has_completed = bool(job_state and job_state["has_completed"])

    if dead_lettered:
        return "dead_letter"
    if has_leased:
        return "in_progress"
    if "patch" in pending_phases:
        return "pending_patch"
    if pending_phases.intersection({"review", "check_pre"}):
        return "pending_review"
    if "write" in pending_phases:
        return "pending_write"
    if pending_phases:
        return "pending_review"
    if "done" in event_types or has_completed:
        return "done"
    return "pending_write"


def _build_status_report(db_path: Path) -> dict[str, Any]:
    phase_order = [
        "pending_review",
        "pending_write",
        "pending_patch",
        "done",
        "dead_letter",
        "in_progress",
    ]
    counts = {phase: 0 for phase in phase_order}
    modules: set[str] = set()
    job_state_by_module: dict[str, dict[str, Any]] = {}
    event_types_by_module: dict[str, set[str]] = {}
    attempt_counts: dict[str, int] = {}
    dead_letter_rows: list[dict[str, Any]] = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        job_rows = conn.execute(
            """
            SELECT module_key, phase, queue_state
            FROM jobs
            WHERE module_key IS NOT NULL
            ORDER BY id ASC
            """
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT id, module_key, type, payload_json, at
            FROM events
            WHERE module_key IS NOT NULL
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    for row in job_rows:
        module_key = str(row["module_key"])
        phase = str(row["phase"])
        queue_state = str(row["queue_state"])
        modules.add(module_key)
        state = job_state_by_module.setdefault(
            module_key,
            {
                "pending_phases": set(),
                "has_leased": False,
                "has_failed": False,
                "has_completed": False,
            },
        )
        if queue_state == "pending":
            state["pending_phases"].add(phase)
        elif queue_state == "leased":
            state["has_leased"] = True
        elif queue_state == "failed":
            state["has_failed"] = True
        elif queue_state == "completed":
            state["has_completed"] = True

    for row in event_rows:
        module_key = str(row["module_key"])
        event_type = str(row["type"])
        modules.add(module_key)
        event_types_by_module.setdefault(module_key, set()).add(event_type)
        if event_type == "attempt_started":
            attempt_counts[module_key] = attempt_counts.get(module_key, 0) + 1
        if event_type in {"needs_human_intervention", "module_dead_lettered", "dead_letter_recovered"}:
            dead_letter_rows.append(
                {
                    "module_key": module_key,
                    "id": int(row["id"]),
                    "type": event_type,
                    "payload_json": str(row["payload_json"] or "{}"),
                    "at": int(row["at"]),
                }
            )

    unresolved_dead_letters = {
        row["module_key"]
        for row in _current_dead_letter_rows(dead_letter_rows)
    }

    for module_key in modules:
        job_state = job_state_by_module.get(module_key)
        event_types = event_types_by_module.get(module_key, set())
        counts[_module_status(job_state, event_types, dead_lettered=module_key in unresolved_dead_letters)] += 1

    pending_review_list = sorted([
        m for m in modules
        if _module_status(job_state_by_module.get(m), event_types_by_module.get(m, set()), dead_lettered=m in unresolved_dead_letters) == "pending_review"
    ])
    pending_write_list = sorted([
        m for m in modules
        if _module_status(job_state_by_module.get(m), event_types_by_module.get(m, set()), dead_lettered=m in unresolved_dead_letters) == "pending_write"
    ])

    total_modules = len(modules)
    done_count = counts["done"]
    convergence_rate = (done_count / total_modules * 100.0) if total_modules else 0.0
    flapping_count = sum(1 for attempts in attempt_counts.values() if attempts > 3)

    return {
        "db_path": str(db_path),
        "phase_order": phase_order,
        "counts": counts,
        "total_modules": total_modules,
        "convergence_rate": convergence_rate,
        "flapping_count": flapping_count,
        "needs_human_count": len(unresolved_dead_letters),
        "pending_review": pending_review_list,
        "pending_write": pending_write_list,
    }


build_v2_status_report = _build_status_report


ACTIVE_MODULE_GROUPS = (
    {
        "key": "ai_ml_learner_path",
        "issue": 244,
        "label": "AI/ML learner-path",
        "paths": (
            "src/content/docs/ai-ml-engineering/prerequisites/module-1.2-home-ai-workstation-fundamentals.md",
            "src/content/docs/ai-ml-engineering/prerequisites/module-1.3-reproducible-python-cuda-rocm-environments.md",
            "src/content/docs/ai-ml-engineering/prerequisites/module-1.4-notebooks-scripts-project-layouts.md",
            "src/content/docs/ai-ml-engineering/vector-rag/module-1.6-home-scale-rag-systems.md",
            "src/content/docs/ai-ml-engineering/mlops/module-1.11-notebooks-to-production-for-ml-llms.md",
            "src/content/docs/ai-ml-engineering/mlops/module-1.12-small-team-private-ai-platform.md",
            "src/content/docs/ai-ml-engineering/advanced-genai/module-1.10-single-gpu-local-fine-tuning.md",
            "src/content/docs/ai-ml-engineering/advanced-genai/module-1.11-multi-gpu-home-lab-fine-tuning.md",
            "src/content/docs/ai-ml-engineering/ai-infrastructure/module-1.4-local-inference-stack-for-learners.md",
            "src/content/docs/ai-ml-engineering/ai-infrastructure/module-1.5-home-ai-operations-cost-model.md",
        ),
    },
    {
        "key": "cert_prep",
        "issue": 182,
        "label": "Certification prep",
        "paths": (
            "src/content/docs/k8s/lfcs/module-1.1-exam-strategy-and-workflow.md",
            "src/content/docs/k8s/lfcs/module-1.2-essential-commands-practice.md",
            "src/content/docs/k8s/lfcs/module-1.3-running-systems-and-networking-practice.md",
            "src/content/docs/k8s/lfcs/module-1.4-storage-services-and-users-practice.md",
            "src/content/docs/k8s/lfcs/module-1.5-full-mock-exam.md",
            "src/content/docs/k8s/cnpe/module-1.1-exam-strategy-and-environment.md",
            "src/content/docs/k8s/cnpe/module-1.2-gitops-and-delivery-lab.md",
            "src/content/docs/k8s/cnpe/module-1.3-platform-apis-and-self-service-lab.md",
            "src/content/docs/k8s/cnpe/module-1.4-observability-security-and-operations-lab.md",
            "src/content/docs/k8s/cnpe/module-1.5-full-mock-exam.md",
            "src/content/docs/k8s/cnpa/module-1.1-exam-strategy-and-blueprint-review.md",
            "src/content/docs/k8s/cnpa/module-1.2-core-platform-fundamentals-review.md",
            "src/content/docs/k8s/cnpa/module-1.3-delivery-apis-and-observability-review.md",
            "src/content/docs/k8s/cnpa/module-1.4-practice-questions-set-1.md",
            "src/content/docs/k8s/cnpa/module-1.5-practice-questions-set-2.md",
            "src/content/docs/k8s/cgoa/module-1.1-exam-strategy-and-blueprint-review.md",
            "src/content/docs/k8s/cgoa/module-1.2-gitops-principles-review.md",
            "src/content/docs/k8s/cgoa/module-1.3-patterns-and-tooling-review.md",
            "src/content/docs/k8s/cgoa/module-1.4-practice-questions-set-1.md",
            "src/content/docs/k8s/cgoa/module-1.5-practice-questions-set-2.md",
        ),
    },
)

DEFERRED_MODULE_GROUPS = (
    {
        "key": "cka_mock_exams",
        "issue": 183,
        "label": "CKA mock exams",
        "paths": (
            "src/content/docs/k8s/cka/part6-mock-exams/module-6.1-cluster-architecture-and-troubleshooting.md",
            "src/content/docs/k8s/cka/part6-mock-exams/module-6.2-workloads-networking-and-storage.md",
            "src/content/docs/k8s/cka/part6-mock-exams/module-6.3-full-mixed-domain-mock-exam.md",
        ),
    },
)


def _iter_en_modules(docs_root: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in docs_root.glob("**/module-*.md")
            if "/uk/" not in path.as_posix()
            and ".staging." not in path.name
        ]
    )


TRACK_ORDER = (
    ("prerequisites", "Prerequisites"),
    ("linux", "Linux"),
    ("k8s", "Kubernetes"),
    ("cloud", "Cloud"),
    ("platform", "Platform Engineering"),
    ("on-premises", "On-Premises"),
    ("ai", "AI"),
    ("ai-ml-engineering", "AI/ML Engineering"),
)
TRACK_SLUGS = {slug for slug, _ in TRACK_ORDER}


def _track_for_key(module_key: str) -> str:
    """Classify a module path or key into a top-level track slug.

    Accepts both full repo paths (src/content/docs/...) and internal v2 keys
    that may have been normalized to the docs-relative form.
    """
    s = str(module_key or "").replace("\\", "/")
    prefix = "src/content/docs/"
    if prefix in s:
        s = s.split(prefix, 1)[1]
    s = s.lstrip("/")
    top = s.split("/", 1)[0] if s else ""
    return top if top in TRACK_SLUGS else "other"


def _build_track_rollup(docs_root: Path) -> list[dict[str, Any]]:
    en_counts: dict[str, int] = {slug: 0 for slug, _ in TRACK_ORDER}
    en_counts["other"] = 0
    for path in _iter_en_modules(docs_root):
        rel = path.relative_to(docs_root).as_posix()
        top = rel.split("/", 1)[0] if "/" in rel else rel
        if top in en_counts:
            en_counts[top] += 1
        else:
            en_counts["other"] += 1

    uk_counts: dict[str, int] = {slug: 0 for slug, _ in TRACK_ORDER}
    uk_counts["other"] = 0
    uk_root = docs_root / "uk"
    for path in _iter_uk_modules(docs_root):
        rel = path.relative_to(uk_root).as_posix()
        top = rel.split("/", 1)[0] if "/" in rel else rel
        if top in uk_counts:
            uk_counts[top] += 1
        else:
            uk_counts["other"] += 1

    rollup = [
        {
            "slug": slug,
            "label": label,
            "module_count": en_counts[slug],
            "uk_module_count": uk_counts[slug],
        }
        for slug, label in TRACK_ORDER
    ]
    if en_counts["other"] or uk_counts["other"]:
        rollup.append({
            "slug": "other",
            "label": "Other",
            "module_count": en_counts["other"],
            "uk_module_count": uk_counts["other"],
        })
    return rollup


def _iter_uk_modules(docs_root: Path) -> list[Path]:
    uk_root = docs_root / "uk"
    if not uk_root.exists():
        return []
    return sorted(
        path
        for path in uk_root.glob("**/module-*.md")
        if ".staging." not in path.name
    )


def _extract_frontmatter(path: Path) -> dict:
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


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _build_translation_summary(repo_root: Path) -> dict[str, Any]:
    docs_root = repo_root / "src" / "content" / "docs"
    en_modules = _iter_en_modules(docs_root)
    uk_root = docs_root / "uk"

    modules: list[dict[str, Any]] = []
    counts = {"synced": 0, "missing": 0, "stale": 0, "unknown": 0}

    for en_path in en_modules:
        rel = en_path.relative_to(docs_root)
        uk_path = uk_root / rel
        module_key = rel.as_posix()[:-3]
        if not uk_path.exists():
            status = "missing"
            counts[status] += 1
            modules.append(
                {
                    "module_key": module_key,
                    "status": status,
                    "uk_path": uk_path.as_posix(),
                }
            )
            continue

        uk_frontmatter = _extract_frontmatter(uk_path)
        tracked_en_file = uk_frontmatter.get("en_file")
        tracked_en_commit = str(uk_frontmatter.get("en_commit", "")).strip().strip('"')
        en_head = _git_head_for_file(repo_root, en_path)
        expected_en_file = en_path.relative_to(repo_root).as_posix()

        if tracked_en_file != expected_en_file:
            status = "stale"
        elif tracked_en_commit and en_head and tracked_en_commit == en_head:
            status = "synced"
        elif not tracked_en_commit or not en_head:
            status = "unknown"
        else:
            status = "stale"

        counts[status] += 1
        modules.append(
            {
                "module_key": module_key,
                "status": status,
                "en_commit": en_head,
                "uk_en_commit": tracked_en_commit,
                "uk_path": uk_path.as_posix(),
            }
        )

    return {
        "total_english_modules": len(en_modules),
        "uk_module_files_present": len(_iter_uk_modules(docs_root)),
        "synced": counts["synced"],
        "missing": counts["missing"],
        "stale": counts["stale"],
        "unknown": counts["unknown"],
        "sync_clean": counts["missing"] == 0 and counts["stale"] == 0 and counts["unknown"] == 0,
        "writer": f"{GEMINI_WRITER_MODEL} via uk_sync.py",
        "modules": modules,
    }


def _build_lab_summary(repo_root: Path) -> dict[str, Any]:
    lab_state = _load_yaml(repo_root / ".pipeline" / "lab-state.yaml").get("labs", {})
    counts = {
        "tracked": 0,
        "done_clean": 0,
        "done_nonclean": 0,
        "pending": 0,
    }
    items: list[dict[str, Any]] = []
    for lab_id, raw in lab_state.items():
        if not isinstance(raw, dict):
            continue
        phase = str(raw.get("phase", "pending"))
        severity = str(raw.get("severity", "-"))
        counts["tracked"] += 1
        if phase == "done" and severity == "clean":
            counts["done_clean"] += 1
        elif phase == "done":
            counts["done_nonclean"] += 1
        else:
            counts["pending"] += 1
        items.append(
            {
                "lab_id": lab_id,
                "phase": phase,
                "severity": severity,
                "module": raw.get("module"),
            }
        )
    items.sort(key=lambda item: item["lab_id"])
    return {**counts, "items": items}


def _build_missing_modules_summary(repo_root: Path) -> dict[str, Any]:
    active_groups: list[dict[str, Any]] = []
    active_total = 0
    active_present = 0
    active_missing = 0

    for group in ACTIVE_MODULE_GROUPS:
        items = []
        present = 0
        missing = 0
        for rel_path in group["paths"]:
            exists = (repo_root / rel_path).exists()
            present += int(exists)
            missing += int(not exists)
            items.append({"path": rel_path, "exists": exists})
        total = len(group["paths"])
        active_total += total
        active_present += present
        active_missing += missing
        active_groups.append(
            {
                "key": group["key"],
                "issue": group["issue"],
                "label": group["label"],
                "total_expected": total,
                "present": present,
                "missing": missing,
                "complete": missing == 0,
                "items": items,
            }
        )

    deferred_groups: list[dict[str, Any]] = []
    deferred_min = 0
    deferred_max = 0
    for group in DEFERRED_MODULE_GROUPS:
        items = []
        present = 0
        for rel_path in group["paths"]:
            exists = (repo_root / rel_path).exists()
            present += int(exists)
            items.append({"path": rel_path, "exists": exists})
        expected = len(group["paths"])
        missing = expected - present
        missing_min = max(missing, 0)
        missing_max = max(missing, 0)
        deferred_min += missing_min
        deferred_max += missing_max
        deferred_groups.append(
            {
                "key": group["key"],
                "issue": group["issue"],
                "label": group["label"],
                "total_expected": expected,
                "present": present,
                "items": items,
                "missing_min": missing_min,
                "missing_max": missing_max,
            }
        )

    return {
        "active_exact": {
            "total_expected": active_total,
            "present": active_present,
            "missing": active_missing,
            "complete": active_missing == 0,
            "groups": active_groups,
        },
        "deferred": {
            "missing_min": deferred_min,
            "missing_max": deferred_max,
            "groups": deferred_groups,
        },
    }


def _per_track_buckets() -> dict[str, dict[str, int]]:
    buckets: dict[str, dict[str, int]] = {
        slug: {
            "pending_write": 0,
            "pending_review": 0,
            "pending_patch": 0,
            "done": 0,
            "dead_letter": 0,
            "in_progress": 0,
        }
        for slug, _ in TRACK_ORDER
    }
    buckets["other"] = {
        "pending_write": 0,
        "pending_review": 0,
        "pending_patch": 0,
        "done": 0,
        "dead_letter": 0,
        "in_progress": 0,
    }
    return buckets


def _enrich_v2_with_per_track(v2: dict[str, Any]) -> dict[str, Any]:
    """Add per-track groupings to a v2 status report.

    Buckets module keys in each queue list by top-level track.
    """
    buckets = _per_track_buckets()
    track_modules: dict[str, dict[str, list[str]]] = {
        slug: {"pending_write": [], "pending_review": [], "pending_patch": [], "dead_letter": []}
        for slug in list(buckets)
    }
    for queue_name in ("pending_write", "pending_review", "pending_patch", "dead_letter"):
        for module_key in v2.get(queue_name, []) or []:
            track = _track_for_key(module_key)
            buckets[track][queue_name] += 1
            track_modules[track][queue_name].append(module_key)
    counts = v2.get("counts", {}) or {}
    enriched = dict(v2)
    enriched["per_track"] = [
        {
            "slug": slug,
            "counts": buckets[slug],
            "modules": track_modules[slug],
        }
        for slug in [s for s, _ in TRACK_ORDER] + (["other"] if buckets["other"]["pending_write"] + buckets["other"]["pending_review"] + buckets["other"]["pending_patch"] + buckets["other"]["dead_letter"] else [])
    ]
    enriched["counts"] = counts
    return enriched


def _enrich_translation_v2_with_per_track(t2: dict[str, Any]) -> dict[str, Any]:
    """Same per-track grouping for the translation v2 queue.

    Translation v2 nests its queue data under ``queue``.
    """
    enriched = dict(t2)
    queue = t2.get("queue") or {}
    if not queue:
        return enriched
    buckets = _per_track_buckets()
    queue_names = ("pending_write", "pending_review", "in_progress", "done", "dead_letter")
    track_modules: dict[str, dict[str, list[str]]] = {
        slug: {name: [] for name in queue_names}
        for slug in list(buckets)
    }
    # Ensure buckets has same keys as track_modules (the default _per_track_buckets
    # comes from content pipeline schema which includes pending_patch we don't use here).
    for slug in buckets:
        for name in queue_names:
            buckets[slug].setdefault(name, 0)
    for queue_name in queue_names:
        for module_key in queue.get(queue_name, []) or []:
            track = _track_for_key(module_key)
            buckets[track][queue_name] += 1
            track_modules[track][queue_name].append(module_key)
    track_freshness: dict[str, dict[str, int] | None] = {slug: None for slug in buckets}
    freshness = t2.get("freshness") or {}
    if freshness:
        for slug in track_freshness:
            track_freshness[slug] = {
                "up_to_date_count": 0,
                "stale_count": 0,
                "missing_count": 0,
                "dead_letter_count": buckets[slug]["dead_letter"],
            }
        for item in freshness.get("modules", []) or []:
            status = str(item.get("status", ""))
            track = _track_for_key(str(item.get("module_key", "")))
            if track_freshness[track] is None:
                continue
            if status == "missing":
                track_freshness[track]["missing_count"] += 1
            elif status == "synced":
                track_freshness[track]["up_to_date_count"] += 1
            else:
                track_freshness[track]["stale_count"] += 1
    enriched_queue = dict(queue)
    enriched_queue["per_track"] = [
        {
            "slug": slug,
            "counts": buckets[slug],
            "modules": track_modules[slug],
            "freshness": track_freshness[slug],
        }
        for slug in [s for s, _ in TRACK_ORDER] + (["other"] if any(buckets["other"].values()) else [])
    ]
    enriched["queue"] = enriched_queue
    return enriched


def build_repo_status(repo_root: Path, *, fast: bool = False) -> dict[str, Any]:
    """Build the combined status payload.

    ``fast=True`` skips the expensive git-per-file translation passes
    (translation_summary, translation_v2 status, ZTT status) so the
    dashboard hot path returns in milliseconds instead of ~2 minutes.
    Callers that need those views fetch them via dedicated endpoints.
    """
    docs_root = repo_root / "src" / "content" / "docs"
    translations = None if fast else _build_translation_summary(repo_root)
    labs = _build_lab_summary(repo_root)
    missing_modules = _build_missing_modules_summary(repo_root)
    ztt = None if fast else build_ztt_status(repo_root)

    v2_db = repo_root / ".pipeline" / "v2.db"
    v2 = build_v2_status_report(v2_db) if v2_db.exists() else None
    translation_v2_db = repo_root / ".pipeline" / "translation_v2.db"
    translation_v2 = (
        None
        if fast or not translation_v2_db.exists()
        else build_translation_v2_status(repo_root, db_path=translation_v2_db)
    )

    tracks = _build_track_rollup(docs_root)
    if v2:
        v2 = _enrich_v2_with_per_track(v2)
    if translation_v2:
        translation_v2 = _enrich_translation_v2_with_per_track(translation_v2)
    return {
        "repo_root": str(repo_root),
        "english_modules": len(_iter_en_modules(docs_root)),
        "uk_modules_present": len(_iter_uk_modules(docs_root)),
        "tracks": tracks,
        "v2_pipeline": v2,
        "translation_v2_pipeline": translation_v2,
        "translations": translations,
        "labs": labs,
        "missing_modules": missing_modules,
        "zero_to_terminal": ztt,
        "ownership": {
            "v2_pipeline": "english content write/review/patch",
            "translation": (
                "translation v2 queue + uk_sync worker"
                if translation_v2 is not None
                else f"{GEMINI_WRITER_MODEL} via uk_sync.py"
            ),
        },
    }


def _print_status(data: dict[str, Any]) -> None:
    v2 = data["v2_pipeline"]
    translation_v2 = data["translation_v2_pipeline"]
    translations = data["translations"]
    labs = data["labs"]
    missing_modules = data["missing_modules"]
    ztt = data["zero_to_terminal"]

    print("KubeDojo Status")
    print()
    print(f"English modules: {data['english_modules']}")
    print(f"Ukrainian module files present: {data['uk_modules_present']}")
    print()
    print("Ownership")
    print(f"  v2 pipeline: {data['ownership']['v2_pipeline']}")
    print(f"  translation: {data['ownership']['translation']}")
    print()

    if v2 is None:
        print("V2 Pipeline")
        print("  status: missing .pipeline/v2.db")
    else:
        print("V2 Pipeline")
        print(f"  total modules: {v2['total_modules']}")
        print(f"  convergence: {v2['convergence_rate']:.1f}%")
        print(
            "  counts:"
            f" review={v2['counts']['pending_review']}"
            f" write={v2['counts']['pending_write']}"
            f" patch={v2['counts']['pending_patch']}"
            f" done={v2['counts']['done']}"
            f" dead_letter={v2['counts']['dead_letter']}"
            f" in_progress={v2['counts']['in_progress']}"
        )
    print()

    if translation_v2 is None:
        print("Translation v2")
        print("  status: missing .pipeline/translation_v2.db")
    else:
        freshness = translation_v2["freshness"]
        queue = translation_v2["queue"]
        print("Translation v2")
        print(
            f"  freshness: synced={freshness['synced']} missing={freshness['missing']}"
            f" stale={freshness['stale']} unknown={freshness['unknown']}"
        )
        print(
            f"  queue: total={queue['total_modules']} convergence={queue['convergence_rate']:.1f}%"
        )
        print(
            f"  counts: review={queue['counts']['pending_review']}"
            f" write={queue['counts']['pending_write']}"
            f" done={queue['counts']['done']}"
            f" dead_letter={queue['counts']['dead_letter']}"
            f" in_progress={queue['counts']['in_progress']}"
        )
    print()

    print("Translations")
    print(
        f"  synced={translations['synced']}"
        f" missing={translations['missing']}"
        f" stale={translations['stale']}"
        f" unknown={translations['unknown']}"
        f" clean={'YES' if translations['sync_clean'] else 'NO'}"
    )
    print()

    print("Labs")
    print(
        f"  tracked={labs['tracked']}"
        f" clean={labs['done_clean']}"
        f" done_nonclean={labs['done_nonclean']}"
        f" pending={labs['pending']}"
    )
    print()

    print("Missing Modules")
    print(
        f"  active exact: present={missing_modules['active_exact']['present']}"
        f" total={missing_modules['active_exact']['total_expected']}"
        f" missing={missing_modules['active_exact']['missing']}"
        f" complete={'YES' if missing_modules['active_exact']['complete'] else 'NO'}"
    )
    print(
        f"  deferred: min={missing_modules['deferred']['missing_min']}"
        f" max={missing_modules['deferred']['missing_max']}"
    )
    print()

    print("Zero to Terminal")
    print(
        f"  english production bar: {'YES' if ztt['ready']['english_production_bar'] else 'NO'}"
    )
    print(
        f"  ukrainian sync clean: {'YES' if ztt['ready']['ukrainian_sync_clean'] else 'NO'}"
    )
    print(
        f"  theory={ztt['theory']['audited']}/{ztt['theory']['present']} audited"
        f" labs={ztt['labs']['clean']}/{ztt['labs']['total']} clean"
        f" uk_synced={ztt['ukrainian']['synced']}/{ztt['ukrainian']['total']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show unified KubeDojo repo status")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human output")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    data = build_repo_status(args.repo_root.resolve())
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        _print_status(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
