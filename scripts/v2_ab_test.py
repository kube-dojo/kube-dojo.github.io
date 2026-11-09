from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from migrate_v1_to_v2 import DEFAULT_STATE_PATH
from v1_pipeline import find_module_path, review_audit_path_for_key

DEFAULT_BUDGETS_PATH = None
WRITE_MODEL = "removed"
REVIEW_MODEL = "removed"
WRITE_ESTIMATED_USD = 0.0
PATCH_ESTIMATED_USD = 0.0


class ControlPlane:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


class WriteWorker:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


class ReviewWorker:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


class PatchWorker:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = str((REPO_ROOT / ".venv" / "bin" / "python").resolve())
DEFAULT_COUNT = 50
MODEL_ESTIMATED_USD = {
    WRITE_MODEL: WRITE_ESTIMATED_USD,
    REVIEW_MODEL: 0.0050,
    "gpt-5.4": PATCH_ESTIMATED_USD,
}


@dataclass(frozen=True)
class SelectedModule:
    raw_key: str
    module_key: str
    module_path: Path


@dataclass(frozen=True)
class TrialResult:
    cohort: str
    raw_key: str
    module_key: str
    converged: bool
    passes: int
    cost_usd: float
    wall_time_s: float
    terminal_state: str
    notes: str = ""


@dataclass(frozen=True)
class AbTestReport:
    count_requested: int
    modules_filter: str | None
    seed: int
    selected_count: int
    results: list[TrialResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count_requested": self.count_requested,
            "modules_filter": self.modules_filter,
            "seed": self.seed,
            "selected_count": self.selected_count,
            "summary": _summaries_by_cohort(self.results),
            "results": [result.__dict__ for result in self.results],
        }

    def render_text(self) -> str:
        summaries = _summaries_by_cohort(self.results)
        lines = [
            "v1 vs v2 A/B comparison",
            f"requested sample size: {self.count_requested}",
            f"selected modules: {self.selected_count}",
            f"track filter: {self.modules_filter or '(all review modules)'}",
            f"seed: {self.seed}",
            "",
        ]
        for cohort in ("v1", "v2"):
            summary = summaries.get(cohort) or {}
            lines.extend(
                [
                    f"{cohort}:",
                    f"  modules: {summary.get('modules', 0)}",
                    f"  converged: {summary.get('converged', 0)}",
                    f"  avg passes/module: {summary.get('avg_passes', 0.0):.2f}",
                    f"  total cost usd: {summary.get('total_cost_usd', 0.0):.4f}",
                    f"  avg wall time s: {summary.get('avg_wall_time_s', 0.0):.2f}",
                    "",
                ]
            )

        lines.append("per-module results:")
        for result in self.results:
            lines.append(
                f"- {result.cohort} {result.raw_key}: converged={result.converged} "
                f"passes={result.passes} cost=${result.cost_usd:.4f} "
                f"wall={result.wall_time_s:.2f}s terminal={result.terminal_state}"
                + (f" notes={result.notes}" if result.notes else "")
            )
        return "\n".join(lines)


def run_ab_test(
    *,
    count: int = DEFAULT_COUNT,
    modules_filter: str | None = None,
    state_path: Path = DEFAULT_STATE_PATH,
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
    seed: int = 239,
    max_iterations: int = 24,
    show_progress: bool = True,
) -> AbTestReport:
    selected = select_review_modules(
        state_path=state_path,
        count=count,
        modules_filter=modules_filter,
        seed=seed,
    )
    midpoint = len(selected) // 2
    v1_group = selected[:midpoint]
    v2_group = selected[midpoint:]
    total_trials = len(selected)

    if show_progress:
        print("Starting v1 vs v2 A/B comparison", flush=True)
        print(
            f"total={total_trials} requested={count} filter={modules_filter or '(all review modules)'} "
            f"seed={seed} max_iterations={max_iterations}",
            flush=True,
        )
        print(f"state={state_path} budgets={budgets_path}", flush=True)

    results: list[TrialResult] = []
    trial_number = 0

    for item in v1_group:
        trial_number += 1
        if show_progress:
            print(f"[{trial_number}/{total_trials} v1] {item.raw_key} - running...", flush=True)
        result = run_v1_trial(item, state_path=state_path)
        results.append(result)
        if show_progress:
            status = "PASS" if result.converged else "FAIL"
            print(
                f"[{trial_number}/{total_trials} v1] {status} "
                f"({result.passes} iters, ${result.cost_usd:.3f}, {int(round(result.wall_time_s))}s)",
                flush=True,
            )
            if trial_number % 5 == 0:
                passed = sum(1 for entry in results if entry.converged)
                failed = len(results) - passed
                avg_cost = sum(entry.cost_usd for entry in results) / len(results)
                avg_time = sum(entry.wall_time_s for entry in results) / len(results)
                print(
                    f"[tally {trial_number}/{total_trials}] {passed} passed, {failed} failed, "
                    f"avg cost ${avg_cost:.3f}, avg time {int(round(avg_time))}s",
                    flush=True,
                )

    for item in v2_group:
        trial_number += 1
        if show_progress:
            print(f"[{trial_number}/{total_trials} v2] {item.raw_key} - running...", flush=True)
        result = run_v2_trial(
            item,
            budgets_path=budgets_path,
            max_iterations=max_iterations,
        )
        results.append(result)
        if show_progress:
            status = "PASS" if result.converged else "FAIL"
            print(
                f"[{trial_number}/{total_trials} v2] {status} "
                f"({result.passes} iters, ${result.cost_usd:.3f}, {int(round(result.wall_time_s))}s)",
                flush=True,
            )
            if trial_number % 5 == 0:
                passed = sum(1 for entry in results if entry.converged)
                failed = len(results) - passed
                avg_cost = sum(entry.cost_usd for entry in results) / len(results)
                avg_time = sum(entry.wall_time_s for entry in results) / len(results)
                print(
                    f"[tally {trial_number}/{total_trials}] {passed} passed, {failed} failed, "
                    f"avg cost ${avg_cost:.3f}, avg time {int(round(avg_time))}s",
                    flush=True,
                )

    return AbTestReport(
        count_requested=count,
        modules_filter=modules_filter,
        seed=seed,
        selected_count=len(selected),
        results=results,
    )


def select_review_modules(
    *,
    state_path: Path,
    count: int,
    modules_filter: str | None,
    seed: int,
) -> list[SelectedModule]:
    state = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    modules = state.get("modules") or {}
    candidates: list[SelectedModule] = []
    for raw_key, module_state in sorted(modules.items()):
        if str(module_state.get("phase")) != "review":
            continue
        if modules_filter and not str(raw_key).startswith(modules_filter):
            continue
        module_path = find_module_path(str(raw_key))
        if module_path is None or not module_path.exists():
            continue
        candidates.append(
            SelectedModule(
                raw_key=str(raw_key),
                module_key=str(module_path.resolve().relative_to(REPO_ROOT.resolve())),
                module_path=module_path,
            )
        )

    rng = random.Random(seed)
    rng.shuffle(candidates)
    return candidates[: min(count, len(candidates))]


def run_v1_trial(item: SelectedModule, *, state_path: Path) -> TrialResult:
    module_backup = item.module_path.read_text(encoding="utf-8")
    state_backup = state_path.read_text(encoding="utf-8")
    audit_path = review_audit_path_for_key(item.raw_key)
    audit_backup = audit_path.read_text(encoding="utf-8") if audit_path.exists() else None
    before_stats = _parse_audit_stats(audit_backup or "")
    start = time.monotonic()
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{REPO_ROOT / 'scripts'}:{existing_pythonpath}"
        if existing_pythonpath
        else str(REPO_ROOT / "scripts")
    )
    try:
        completed = subprocess.run(
            [VENV_PYTHON, str(REPO_ROOT / "scripts" / "v1_pipeline.py"), "run", item.raw_key],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        wall_time_s = time.monotonic() - start
        current_state = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        current_module_state = (current_state.get("modules") or {}).get(item.raw_key) or {}
        after_text = audit_path.read_text(encoding="utf-8") if audit_path.exists() else ""
        after_stats = _parse_audit_stats(after_text)
        converged = bool(current_module_state.get("passes")) or str(current_module_state.get("phase")) == "done"
        notes = ""
        if completed.returncode != 0:
            notes = (completed.stderr or completed.stdout).strip().splitlines()[-1] if (completed.stderr or completed.stdout).strip() else "v1 subprocess failed"
        return TrialResult(
            cohort="v1",
            raw_key=item.raw_key,
            module_key=item.module_key,
            converged=converged,
            passes=max(0, after_stats["total_passes"] - before_stats["total_passes"]),
            cost_usd=max(0.0, round(after_stats["estimated_usd"] - before_stats["estimated_usd"], 4)),
            wall_time_s=round(wall_time_s, 3),
            terminal_state=str(current_module_state.get("phase", "unknown")),
            notes=notes,
        )
    finally:
        item.module_path.write_text(module_backup, encoding="utf-8")
        state_path.write_text(state_backup, encoding="utf-8")
        if audit_backup is None:
            audit_path.unlink(missing_ok=True)
        else:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(audit_backup, encoding="utf-8")


def run_v2_trial(
    item: SelectedModule,
    *,
    budgets_path: Path,
    max_iterations: int,
) -> TrialResult:
    module_backup = item.module_path.read_text(encoding="utf-8")
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="v2-ab-", dir=str(REPO_ROOT / ".pipeline")) as tmp_dir:
        db_path = Path(tmp_dir) / "v2.db"
        control_plane = ControlPlane(repo_root=REPO_ROOT, db_path=db_path, budgets_path=budgets_path)
        control_plane.emit_event(
            "module_created",
            module_key=item.module_key,
            payload={"source": "ab_test", "synthetic": True, "v1_phase": "review"},
        )
        control_plane.emit_event(
            "attempt_succeeded",
            module_key=item.module_key,
            payload={"source": "ab_test", "synthetic": True, "phase": "write"},
        )
        control_plane.enqueue(item.module_key, phase="review", model=REVIEW_MODEL)

        review_worker = ReviewWorker(control_plane, worker_id="ab-review")
        patch_worker = PatchWorker(control_plane, worker_id="ab-patch")
        write_worker = WriteWorker(control_plane, worker_id="ab-write")

        converged = False
        terminal_state = "review"
        notes = ""
        for _ in range(max_iterations):
            review_outcome = review_worker.run_once()
            if review_outcome.status != "idle":
                terminal_state = review_outcome.status
                if review_outcome.status == "approved":
                    converged = True
                    break
                if review_outcome.status in {"attempt_failed"}:
                    notes = str(review_outcome.details or {})

            patch_outcome = patch_worker.run_once()
            if patch_outcome.status != "idle":
                terminal_state = patch_outcome.status
                if patch_outcome.status == "needs_human_intervention":
                    break

            write_outcome = write_worker.run_once()
            if write_outcome.status != "idle":
                terminal_state = write_outcome.status

            if review_outcome.status == patch_outcome.status == write_outcome.status == "idle":
                break

        wall_time_s = time.monotonic() - start
        total_cost = float(
            control_plane.fetch_value("SELECT COALESCE(SUM(actual_usd), 0) FROM usage") or 0.0
        )
        passes = int(
            control_plane.fetch_value(
                "SELECT COUNT(*) FROM events WHERE module_key = ? AND type = 'attempt_started'",
                (item.module_key,),
            )
            or 0
        )
    item.module_path.write_text(module_backup, encoding="utf-8")
    return TrialResult(
        cohort="v2",
        raw_key=item.raw_key,
        module_key=item.module_key,
        converged=converged,
        passes=passes,
        cost_usd=round(total_cost, 4),
        wall_time_s=round(wall_time_s, 3),
        terminal_state=terminal_state,
        notes=notes,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a v1 vs v2 pipeline A/B sample")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of review modules to sample")
    parser.add_argument("--modules", help="Only include review modules whose key starts with this prefix")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH, help="Path to v1 .pipeline/state.yaml")
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS_PATH, help="Path to .pipeline/budgets.yaml")
    parser.add_argument("--seed", type=int, default=239, help="Random seed for repeatable sampling")
    parser.add_argument("--max-iterations", type=int, default=24, help="Max v2 worker cycles per module")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_ab_test(
        count=args.count,
        modules_filter=args.modules,
        state_path=args.state,
        budgets_path=args.budgets,
        seed=args.seed,
        max_iterations=args.max_iterations,
        show_progress=not args.json,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0


def _parse_audit_stats(text: str) -> dict[str, float]:
    total_passes_match = re.search(r"^\*\*Total passes\*\*:\s*(\d+)\s*$", text, re.MULTILINE)
    total_passes = int(total_passes_match.group(1)) if total_passes_match else 0

    estimated_usd = 0.0
    current_event: str | None = None
    for line in text.splitlines():
        section_match = re.match(r"^## .*`([^`]+)`\s*$", line)
        if section_match:
            current_event = section_match.group(1)
            continue
        model_match = re.match(r"^\*\*(Writer|Reviewer)\*\*:\s*(.+)\s*$", line)
        if model_match and current_event is not None:
            model = model_match.group(2).strip()
            estimated_usd += MODEL_ESTIMATED_USD.get(model, 0.0)

    return {
        "total_passes": total_passes,
        "estimated_usd": round(estimated_usd, 4),
    }


def _summaries_by_cohort(results: list[TrialResult]) -> dict[str, dict[str, float]]:
    summaries: dict[str, dict[str, float]] = {}
    for cohort in ("v1", "v2"):
        cohort_results = [result for result in results if result.cohort == cohort]
        if not cohort_results:
            summaries[cohort] = {
                "modules": 0,
                "converged": 0,
                "avg_passes": 0.0,
                "total_cost_usd": 0.0,
                "avg_wall_time_s": 0.0,
            }
            continue
        summaries[cohort] = {
            "modules": len(cohort_results),
            "converged": sum(1 for result in cohort_results if result.converged),
            "avg_passes": round(
                sum(result.passes for result in cohort_results) / len(cohort_results),
                2,
            ),
            "total_cost_usd": round(sum(result.cost_usd for result in cohort_results), 4),
            "avg_wall_time_s": round(
                sum(result.wall_time_s for result in cohort_results) / len(cohort_results),
                2,
            ),
        }
    return summaries


if __name__ == "__main__":
    raise SystemExit(main())
