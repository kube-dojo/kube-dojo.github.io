#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_ROOT))

import translation_v2
import uk_sync


class ControlPlane:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / ".pipeline" / "translation_v2.db"


def _drift(repo_root: Path, en_commit: str, en_path: Path) -> int:
    out = subprocess.run(["git", "diff", "--numstat", f"{en_commit}..HEAD", "--", str(en_path)], cwd=repo_root, capture_output=True, text=True, check=False).stdout.splitlines()
    if not out:
        return 0
    p = out[0].split("\t", 2)
    if len(p) < 2:
        return 0
    try:
        return (0 if p[0] == "-" else int(p[0])) + (0 if p[1] == "-" else int(p[1]))
    except ValueError:
        return 0


def detect_uk_divergence(*, repo_root: Path, threshold: int = 5, dry_run: bool = False, limit: int | None = None, db_path: Path = DEFAULT_DB_PATH) -> dict:
    uk_root = repo_root / "src/content/docs/uk"
    en_root = repo_root / "src/content/docs"
    uk_files = uk_sync._find_content_files(uk_root, uk=True)
    stale: list[dict] = []
    missing_en_commit = []
    enqueued = []
    cp = None
    # When --limit is hit we stop enqueuing but keep iterating so stale/missing_en_commit
    # counts reflect the full scan rather than a truncated view.
    enqueue_cap_reached = False

    for uk_path in uk_files:
        commit = uk_sync._get_uk_synced_commit(uk_path.read_text(encoding="utf-8"))
        if not commit:
            missing_en_commit.append({"module_key": str(uk_path.relative_to(uk_root).with_suffix("")), "uk_path": str(uk_path.relative_to(repo_root))})
            continue

        en_path = en_root / uk_path.relative_to(uk_root)
        if not en_path.exists():
            continue

        module_key = translation_v2._module_key_for_en_path(repo_root, en_path)
        drift_lines = _drift(repo_root, commit, en_path)
        if drift_lines <= threshold:
            continue

        stale.append({"module_key": module_key, "en_commit_uk": commit[:8], "en_head": uk_sync._get_en_file_commit(en_path)[:8], "drift_lines": drift_lines})
        if dry_run or enqueue_cap_reached or translation_v2._has_pending_or_leased_job(db_path, module_key):
            continue

        if cp is None:
            cp = ControlPlane(repo_root=repo_root, db_path=db_path)
        cp.enqueue(module_key, phase="write", model=translation_v2.TRANSLATE_MODEL, requested_calls=1, estimated_usd=translation_v2.TRANSLATE_ESTIMATED_USD, priority=100 + len(enqueued))
        enqueued.append(module_key)
        if limit is not None and len(enqueued) >= limit:
            enqueue_cap_reached = True

    summary = {"scanned_at": datetime.now(timezone.utc).isoformat(), "total_uk_files": len(uk_files), "stale": stale, "missing_en_commit": missing_en_commit, "enqueued": enqueued}
    out = repo_root / ".pipeline/translation_divergence.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--threshold", type=int, default=5)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = parse_args(argv)
    s = detect_uk_divergence(repo_root=REPO_ROOT, threshold=a.threshold, dry_run=a.dry_run, limit=a.limit, db_path=a.db)
    if a.json:
        print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
