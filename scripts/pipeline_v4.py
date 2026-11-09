#!/usr/bin/env python3
"""Pipeline v4 Stage-1-to-5 orchestrator.

Stages:
    1. RUBRIC_SCAN
    2. EXPAND
    3. RUBRIC_RECHECK
    4. CITATION_V3
    5. FINAL_RECHECK
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, SCRIPTS_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

import local_api  # noqa: E402
import rubric_gaps  # noqa: E402


class _RemovedExpandModule:
    """Stage 2 routing stays; the dispatcher call is gone.

    ``can_expand`` is the pure gap check pipeline_v4 uses to skip Stage 2.
    ``expand_module`` is the call that used to dispatch a writer.
    """

    _HANDLERS = {
        "no_quiz",
        "no_mistakes",
        "no_exercise",
        "thin",
        "no_outcomes",
    }

    @classmethod
    def can_expand(cls, gaps):
        return any(gap in cls._HANDLERS for gap in gaps)

    @staticmethod
    def expand_module(*_args, **_kwargs):
        raise RuntimeError("legacy dispatcher removed")


expand_module = _RemovedExpandModule()

DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
PIPELINE_V4_DIR = REPO_ROOT / ".pipeline" / "v4"
RUNS_DIR = PIPELINE_V4_DIR / "runs"

STAGE_RUBRIC_SCAN = "RUBRIC_SCAN"
STAGE_EXPAND = "EXPAND"
STAGE_RUBRIC_RECHECK = "RUBRIC_RECHECK"
STAGE_CITATION_V3 = "CITATION_V3"
STAGE_FINAL_RECHECK = "FINAL_RECHECK"
STAGE_DONE = "DONE"

OUTCOME_CLEAN = "clean"
OUTCOME_SKIPPED = "skipped_already_stable"
OUTCOME_RESIDUALS_FILED = "residuals_filed"
OUTCOME_FAILED = "failed"


@dataclass
class PipelineV4Result:
    module_key: str
    started_at: str
    finished_at: str
    stage_reached: str
    outcome: str
    reason: str
    score_before: float
    score_after: float | None
    gaps_before: list[str]
    gaps_after: list[str]
    retry_count: int
    citation_v3_exit: int | None
    events: list[dict[str, Any]] = field(default_factory=list)


class PipelineV4Error(RuntimeError):
    """Raised when pipeline v4 cannot complete due to a local orchestration error."""


def _iso_utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _normalize_module_key(module_key: str) -> str:
    return module_key[:-3] if module_key.endswith(".md") else module_key


def _module_path(module_key: str) -> Path:
    return DOCS_ROOT / f"{_normalize_module_key(module_key)}.md"


def _module_flat_key(module_key: str) -> str:
    return _normalize_module_key(module_key).replace("/", "__")


def _pipeline_python() -> str:
    for ancestor in (REPO_ROOT, *REPO_ROOT.parents):
        candidate = ancestor / ".venv" / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    return local_api._venv_python_for_repo(REPO_ROOT)


def _tail_lines(text: str, limit: int = 50) -> list[str]:
    if not text:
        return []
    return text.splitlines()[-limit:]


def _stderr_log(message: str) -> None:
    print(message, file=sys.stderr)


def _append_event(
    result: PipelineV4Result,
    stage: str,
    event: str,
    detail: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    record = {
        "ts": _iso_utc(),
        "stage": stage,
        "event": event,
        "detail": detail,
    }
    result.events.append(record)
    if not dry_run:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        run_path = RUNS_DIR / f"{_module_flat_key(result.module_key)}.jsonl"
        with run_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _stage_start(
    result: PipelineV4Result,
    stage: str,
    detail: dict[str, Any] | None = None,
    *,
    dry_run: bool,
) -> None:
    result.stage_reached = stage
    payload = {} if detail is None else detail
    _stderr_log(f"[pipeline_v4] {stage} start {json.dumps(payload, ensure_ascii=False)}")
    _append_event(result, stage, "start", payload, dry_run=dry_run)


def _stage_finish(
    result: PipelineV4Result,
    stage: str,
    detail: dict[str, Any] | None = None,
    *,
    dry_run: bool,
) -> None:
    payload = {} if detail is None else detail
    _stderr_log(f"[pipeline_v4] {stage} finish {json.dumps(payload, ensure_ascii=False)}")
    _append_event(result, stage, "finish", payload, dry_run=dry_run)


def _result_with_finish(result: PipelineV4Result) -> PipelineV4Result:
    result.finished_at = _iso_utc()
    return result


def _fail_result(
    result: PipelineV4Result,
    *,
    outcome: str,
    reason: str,
    score_after: float | None = None,
) -> PipelineV4Result:
    result.outcome = outcome
    result.reason = reason
    if score_after is not None:
        result.score_after = score_after
    return _result_with_finish(result)


def _lookup_quality_entry(payload: dict[str, Any], module_key: str) -> dict[str, Any]:
    normalized = _normalize_module_key(module_key)
    modules = payload.get("modules")
    if not isinstance(modules, list):
        raise PipelineV4Error("local_api.build_quality_scores() returned no modules list")
    for entry in modules:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        entry_key = path[:-3] if isinstance(path, str) and path.endswith(".md") else path
        if entry_key == normalized:
            return entry
    raise PipelineV4Error(f"module not found in quality scores: {normalized}")


def _rescore_module(module_key: str) -> dict[str, Any]:
    entry = _lookup_quality_entry(local_api.build_quality_scores(REPO_ROOT), module_key)
    raw_score = entry.get("score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise PipelineV4Error(f"invalid score for {module_key}: {raw_score!r}") from exc
    primary_issue = entry.get("primary_issue")
    primary_issue_text = primary_issue.strip() if isinstance(primary_issue, str) else ""
    return {
        "score": score,
        "gaps": rubric_gaps.parse_primary_issue(primary_issue_text),
        "primary_issue": primary_issue_text,
        "entry": entry,
    }


def _stage_1_gap_scan(module_key: str) -> dict[str, Any]:
    try:
        item = rubric_gaps.gaps_for_module(module_key)
    except rubric_gaps.QualityScoresError:
        item = None
    if item is not None:
        return item

    entry = _lookup_quality_entry(local_api.build_quality_scores(REPO_ROOT), module_key)
    path = entry.get("path")
    if not isinstance(path, str) or not path:
        raise PipelineV4Error(f"quality scores entry missing path for {module_key}")
    raw_score = entry.get("score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise PipelineV4Error(f"invalid score for {module_key}: {raw_score!r}") from exc
    primary_issue = entry.get("primary_issue")
    primary_issue_text = primary_issue.strip() if isinstance(primary_issue, str) else ""
    return {
        "module_key": _normalize_module_key(module_key),
        "path": path,
        "module": entry.get("module"),
        "score": score,
        "severity": entry.get("severity"),
        "primary_issue": primary_issue_text,
        "gaps": rubric_gaps.parse_primary_issue(primary_issue_text),
        "target_loc": rubric_gaps.target_loc_for_path(path),
    }


def _invoke_citation_pipeline(module_key: str) -> dict[str, Any]:
    cmd = [_pipeline_python(), "scripts/pipeline_v3.py", _normalize_module_key(module_key)]
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout),
        "stderr_tail": _tail_lines(completed.stderr),
        "payload": _parse_citation_payload(_tail_lines(completed.stdout)),
    }


def _parse_citation_payload(stdout_tail: list[str]) -> dict[str, Any] | None:
    """Extract pipeline_v3's final JSON payload from stdout tail."""
    if not stdout_tail:
        return None
    text = "\n".join(stdout_tail)
    start = text.find("{")
    if start < 0:
        return None
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_citation_status(stdout_tail: list[str]) -> str | None:
    """Extract the `status` field from pipeline_v3's stdout JSON payload.

    pipeline_v3 prints a JSON object on completion. We only have the
    tail (last 50 lines) but that's enough for a single-module run.
    Returns the status string (e.g. "clean", "residuals_queued") or
    None if the payload can't be parsed."""
    payload = _parse_citation_payload(stdout_tail)
    status = payload.get("status") if isinstance(payload, dict) else None
    return str(status) if isinstance(status, str) else None


def _parse_citation_payload_queued_findings(payload: dict[str, Any] | None) -> dict[str, int]:
    if payload is None or not isinstance(payload.get("queued_findings"), dict):
        return {}
    raw = payload["queued_findings"]
    return {
        key: len(value)
        for key, value in raw.items()
        if isinstance(value, list)
    }


def _new_result(module_key: str) -> PipelineV4Result:
    started_at = _iso_utc()
    return PipelineV4Result(
        module_key=_normalize_module_key(module_key),
        started_at=started_at,
        finished_at=started_at,
        stage_reached=STAGE_RUBRIC_SCAN,
        outcome=OUTCOME_FAILED,
        reason="",
        score_before=0.0,
        score_after=None,
        gaps_before=[],
        gaps_after=[],
        retry_count=0,
        citation_v3_exit=None,
        events=[],
    )


def _run_pipeline_v4(
    module_key: str,
    *,
    max_rubric_retries: int = 2,
    generated_loc_threshold: float = 0.5,
    dry_run: bool = False,
    skip_citation: bool = False,
) -> PipelineV4Result:
    result = _new_result(module_key)
    normalized_key = result.module_key
    module_path = _module_path(normalized_key)

    try:
        if not module_path.exists():
            raise PipelineV4Error(f"module file not found: {module_path}")

        _stage_start(result, STAGE_RUBRIC_SCAN, {"module_key": normalized_key}, dry_run=dry_run)
        stage1 = _stage_1_gap_scan(normalized_key)
        result.score_before = float(stage1.get("score"))
        result.gaps_before = list(stage1.get("gaps") or [])
        target_loc = int(stage1.get("target_loc") or rubric_gaps.target_loc_for_path(f"{normalized_key}.md"))
        _stage_finish(
            result,
            STAGE_RUBRIC_SCAN,
            {
                "score": result.score_before,
                "gaps": result.gaps_before,
                "target_loc": target_loc,
            },
            dry_run=dry_run,
        )

        stable_before_citation = result.score_before >= 4.0 and not result.gaps_before
        # Skip Stage 2 entirely when none of the starting gaps are things
        # expand_module can handle (e.g. only no_citations / no_diagram).
        # Retry-looping through no-op expansions wastes the whole budget
        # and then fails at rubric_stage_3_unmet before ever reaching
        # Stage 4, where no_citations would actually get filled.
        stage_2_applicable = expand_module.can_expand(result.gaps_before)

        if stable_before_citation:
            result.gaps_after = []
            result.score_after = result.score_before
        elif not stage_2_applicable:
            result.gaps_after = list(result.gaps_before)
            result.score_after = result.score_before
        else:
            attempt = 0
            current_gaps = list(result.gaps_before)
            while True:
                _stage_start(
                    result,
                    STAGE_EXPAND,
                    {"attempt": attempt, "gaps": current_gaps, "target_loc": target_loc},
                    dry_run=dry_run,
                )
                expand_result = expand_module.expand_module(
                    normalized_key,
                    current_gaps,
                    target_loc=target_loc,
                    dry_run=dry_run,
                )
                _stage_finish(
                    result,
                    STAGE_EXPAND,
                    {
                        "attempt": attempt,
                        "gaps_filled": expand_result.gaps_filled,
                        "gaps_failed": expand_result.gaps_failed,
                        "loc_before": expand_result.loc_before,
                        "loc_after": expand_result.loc_after,
                        "provenance_blocks_added": expand_result.provenance_blocks_added,
                    },
                    dry_run=dry_run,
                )

                _stage_start(result, STAGE_RUBRIC_RECHECK, {"attempt": attempt}, dry_run=dry_run)
                rescored = _rescore_module(normalized_key)
                score_after_expand = float(rescored["score"])
                gaps_after_expand = list(rescored["gaps"])
                result.score_after = score_after_expand
                result.gaps_after = gaps_after_expand
                _stage_finish(
                    result,
                    STAGE_RUBRIC_RECHECK,
                    {
                        "attempt": attempt,
                        "score": score_after_expand,
                        "gaps": gaps_after_expand,
                        "retry_count": result.retry_count,
                    },
                    dry_run=dry_run,
                )
                if score_after_expand >= 4.0:
                    break
                # If the only remaining gaps are Stage-4 territory
                # (no_citations / no_diagram), further Stage 2 retries
                # can't move the needle. Fall through to Stage 4.
                if not expand_module.can_expand(gaps_after_expand):
                    break
                if result.retry_count >= max_rubric_retries:
                    return _fail_result(
                        result,
                        outcome=OUTCOME_RESIDUALS_FILED,
                        reason="rubric_stage_3_unmet",
                        score_after=score_after_expand,
                    )
                result.retry_count += 1
                attempt += 1
                current_gaps = gaps_after_expand

        score_before_citation = result.score_after if result.score_after is not None else result.score_before
        citation_status: str | None = None

        if dry_run or skip_citation:
            skip_reason = "dry_run" if dry_run else "skip_citation"
            _stage_start(result, STAGE_CITATION_V3, {"reason": skip_reason}, dry_run=dry_run)
            _stage_finish(
                result,
                STAGE_CITATION_V3,
                {"skipped": True, "reason": skip_reason},
                dry_run=dry_run,
            )
            result.stage_reached = STAGE_DONE
            result.outcome = OUTCOME_SKIPPED if stable_before_citation else OUTCOME_CLEAN
            result.reason = ""
            return _result_with_finish(result)

        _stage_start(
            result,
            STAGE_CITATION_V3,
            {"generated_loc_threshold": generated_loc_threshold},
            dry_run=dry_run,
        )
        citation_result = _invoke_citation_pipeline(normalized_key)
        result.citation_v3_exit = int(citation_result["exit_code"])
        citation_status = _parse_citation_status(citation_result["stdout_tail"])
        citation_payload = (
            citation_result.get("payload")
            if isinstance(citation_result.get("payload"), dict)
            else None
        )
        queued_findings = _parse_citation_payload_queued_findings(citation_payload)
        _stage_finish(
            result,
            STAGE_CITATION_V3,
            {
                "generated_loc_threshold": generated_loc_threshold,
                "exit_code": result.citation_v3_exit,
                "status": citation_status,
                "queued_findings": queued_findings,
                "stdout_tail": citation_result["stdout_tail"],
                "stderr_tail": citation_result["stderr_tail"],
            },
            dry_run=dry_run,
        )
        # Pipeline_v3 exits non-zero when it can't fully auto-resolve.
        # status="residuals_queued" means it ran, audited, and routed
        # un-fixable items to human review — that's a successful run
        # with human follow-up, NOT a pipeline failure. Only treat
        # other non-zero exits as failures.
        if result.citation_v3_exit != 0 and citation_status != "residuals_queued":
            return _fail_result(
                result,
                outcome=OUTCOME_FAILED,
                reason="citation_v3_failed",
                score_after=score_before_citation,
            )

        _stage_start(
            result,
            STAGE_FINAL_RECHECK,
            {"score_before_citation": score_before_citation},
            dry_run=dry_run,
        )
        final_rescore = _rescore_module(normalized_key)
        final_score = float(final_rescore["score"])
        final_gaps = list(final_rescore["gaps"])
        result.score_after = final_score
        result.gaps_after = final_gaps
        _stage_finish(
            result,
            STAGE_FINAL_RECHECK,
            {
                "score_after": final_score,
                "gaps": final_gaps,
                "delta_from_pre_citation": round(final_score - score_before_citation, 4),
            },
            dry_run=dry_run,
        )
        if final_score < score_before_citation - 0.2:
            return _fail_result(
                result,
                outcome=OUTCOME_FAILED,
                reason="final_rescore_regressed",
                score_after=final_score,
            )

        result.stage_reached = STAGE_DONE
        # residuals_queued means pipeline_v3 ran cleanly but routed some
        # items to human review. Not a failure, not fully clean — flag
        # as residuals_filed so summaries distinguish it from modules
        # that closed out without residual follow-up.
        if citation_status == "residuals_queued":
            result.outcome = OUTCOME_RESIDUALS_FILED
            result.reason = "citation_residuals_queued"
        else:
            result.outcome = OUTCOME_SKIPPED if stable_before_citation else OUTCOME_CLEAN
            result.reason = ""
        return _result_with_finish(result)
    except Exception as exc:
        if isinstance(exc, PipelineV4Error):
            return _fail_result(result, outcome=OUTCOME_FAILED, reason=str(exc), score_after=result.score_after)
        return _fail_result(
            result,
            outcome=OUTCOME_FAILED,
            reason=f"{type(exc).__name__}: {exc}",
            score_after=result.score_after,
        )


def run_pipeline_v4(
    module_key: str,
    *,
    max_rubric_retries: int = 2,
    generated_loc_threshold: float = 0.5,
    dry_run: bool = False,
    skip_citation: bool = False,
) -> PipelineV4Result:
    return _run_pipeline_v4(
        module_key,
        max_rubric_retries=max_rubric_retries,
        generated_loc_threshold=generated_loc_threshold,
        dry_run=dry_run,
        skip_citation=skip_citation,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module_key", help="Module key without the .md suffix.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing stage logs or invoking citation_v3.")
    parser.add_argument("--skip-citation", action="store_true", help="Stop after Stages 1-3.")
    parser.add_argument("--max-rubric-retries", type=int, default=2, help="Retry budget after the initial Stage-2 attempt.")
    parser.add_argument(
        "--generated-loc-threshold",
        type=float,
        default=0.5,
        help="Deprecated: retained for compatibility; threshold is no longer enforced.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = _run_pipeline_v4(
        args.module_key,
        max_rubric_retries=args.max_rubric_retries,
        generated_loc_threshold=args.generated_loc_threshold,
        dry_run=args.dry_run,
        skip_citation=args.skip_citation,
    )
    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0 if result.outcome in {OUTCOME_CLEAN, OUTCOME_SKIPPED} else 1


if __name__ == "__main__":
    raise SystemExit(main())
