from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import local_api
from pipeline_common.review_audit import append_review_audit
from pipeline_v2.cli import _build_status_report
from pipeline_v2.control_plane import ControlPlane
from pipeline_v2.review_worker import (
    DEEP_CHECK_IDS,
    REVIEW_FALLBACK_MODEL,
    REVIEW_MODEL,
    ReviewWorker,
)

GOOD_MODULE = """---
title: Review Worker Test
slug: /review-worker-test
sidebar:
  order: 1
---

# Review Worker Test

This module explains why review workers should run deterministic checks first.

## Learning Outcomes

- Explain the pre-flight gate.
- Understand review model routing.

## Content

Avoid deprecated APIs and keep the prose emoji free.
"""

PLAN = {"module_kind": "module", "outcomes": ["Explain the pre-flight gate."],
        "essential_topics": ["review gates"],
        "source_basis": [{"uri": "git:review-worker", "locator": "run_once", "excerpt": "Run preflight first."}]}


def _teaching_evidence():
    quote = "This module explains why review workers should run deterministic checks first."
    return {"dimensions": {f"D{n}": 5 for n in range(1, 9)},
            "dimension_evidence": {f"D{n}": quote for n in range(1, 9)}, "must_fix": [],
            "coverage": {"outcomes": [{"outcome": PLAN["outcomes"][0], "teaching": quote,
                                        "practice": quote, "assessment": quote}],
                         "topics": [{"topic": "review gates", "teaching": quote}]},
            "scope_assessment": {"basis_checked": True, "unjustified_omissions": [], "rationale": "Fixture scope."}}


def _write_budgets(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "models": {
                    REVIEW_MODEL: {
                        "max_concurrent": 2,
                        "weekly_calls": 200,
                        "hourly_calls": 50,
                        "weekly_budget_usd": 40.0,
                        "cooldown_after_rate_limit": 300,
                    }
                },
                "defaults": {
                    "max_concurrent": 1,
                    "weekly_calls": 25,
                    "hourly_calls": 10,
                    "weekly_budget_usd": 5.0,
                    "cooldown_after_rate_limit": 300,
                    "weekly_window": "rolling_7d",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _make_control_plane(tmp_path: Path) -> ControlPlane:
    budgets_path = tmp_path / ".pipeline" / "budgets.yaml"
    db_path = tmp_path / ".pipeline" / "v2.db"
    _write_budgets(budgets_path)
    return ControlPlane(repo_root=tmp_path, db_path=db_path, budgets_path=budgets_path)


def _write_module(tmp_path: Path, name: str = "module-1.1-review-worker.md") -> Path:
    module_path = tmp_path / "docs" / name
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(GOOD_MODULE, encoding="utf-8")
    seeds = tmp_path / "docs/citation-seeds"
    seeds.mkdir(parents=True, exist_ok=True)
    (seeds / f"docs-{Path(name).stem}.json").write_text(json.dumps({
        "module_path": f"src/content/docs/docs/{name}", "module_key": f"docs/{Path(name).stem}",
        "coverage_plan": PLAN,
    }))
    return module_path


def _completed_process(cmd: list[str], *, returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def _preflight_side_effect(*args, **kwargs):
    cmd = args[0]
    if cmd[:2] == ["npx", "markdownlint-cli2"]:
        return _completed_process(cmd)
    if cmd[:1] == ["yamllint"]:
        return _completed_process(cmd)
    raise AssertionError(f"Unexpected subprocess call: {cmd}")


def _simple_response(check_id: str, *, passed: bool = True) -> str:
    return json.dumps(
        {
            "verdict": "APPROVE" if passed else "REJECT",
            "checks": [
                {
                    "id": check_id,
                    "passed": passed,
                    "evidence": f"{check_id} {'ok' if passed else 'failed'}",
                    "fix_hint": "" if passed else f"Fix {check_id}",
                    "line_range": [1, 1],
                }
            ],
            "feedback": f"{check_id} {'passed' if passed else 'failed'}",
        }
    )


def _deep_response(
    *,
    cov: bool = True,
    depth: bool = True,
    why: bool = True,
    fact_check: bool = True,
    fact_evidence: str | None = None,
) -> str:
    checks = [
        {
            "id": "COV",
            "passed": cov,
            "evidence": "coverage ok" if cov else "coverage gap",
            "fix_hint": "" if cov else "Cover every learning outcome",
            "line_range": [2, 4],
        },
        {
            "id": "DEPTH",
            "passed": depth,
            "evidence": "depth ok" if depth else "missing operational nuance",
            "fix_hint": "" if depth else "Add practitioner-grade nuance",
            "line_range": [5, 8],
        },
        {
            "id": "WHY",
            "passed": why,
            "evidence": "why ok" if why else "missing rationale",
            "fix_hint": "" if why else "Explain the rationale for design choices",
            "line_range": [9, 10],
        },
        {
            "id": "FACT_CHECK",
            "passed": fact_check,
            "evidence": fact_evidence or ("facts verified" if fact_check else "could not verify current facts"),
            "fix_hint": "" if fact_check else "Verify claims against current live sources",
            "line_range": [11, 12],
        },
    ]
    return json.dumps(
        {
            "verdict": "APPROVE" if all(item["passed"] for item in checks) else "REJECT",
            **_teaching_evidence(),
            "checks": checks,
            "feedback": "deep checks passed" if all(item["passed"] for item in checks) else "deep checks failed",
        }
    )


def _fetch_rows(db_path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


@pytest.mark.parametrize("case", ["missing_plan", "scalar", "weak", "all4", "invented_quote",
                                  "missing_topic", "must_fix", "candidate_drift", "plan_drift", "outside", "traversal"])
def test_teaching_approval_cannot_bypass_researched_evidence(tmp_path, case):
    plane = _make_control_plane(tmp_path)
    path = _write_module(tmp_path)
    seed = next((tmp_path / "docs/citation-seeds").glob("*.json"))
    key = "/outside/module.md" if case == "outside" else "../outside.md" if case == "traversal" else str(path.relative_to(tmp_path))
    plane.enqueue(key, phase="review", model=REVIEW_MODEL)
    payload = json.loads(_deep_response())
    if case == "missing_plan":
        seed.unlink()
    elif case == "scalar":
        payload = {key: payload[key] for key in ("verdict", "checks", "feedback")}
    elif case in ("weak", "all4"):
        payload["dimensions"] = {f"D{n}": 4 for n in range(1, 9)}
        if case == "weak":
            payload["dimensions"]["D8"] = 3
    elif case == "invented_quote":
        payload["dimension_evidence"]["D2"] = "Not in this candidate."
    elif case == "missing_topic":
        payload["coverage"]["topics"] = []
    elif case == "must_fix":
        payload["must_fix"] = ["Untaught outcome"]
    def dispatch(prompt, **kwargs):
        if "Review ONLY the " in prompt:
            check = next(key for key in ("PRES", "NO_EMOJI", "K8S_API") if f"Review ONLY the {key}" in prompt)
            return True, _simple_response(check)
        assert "review gates" in prompt and "source_basis" in prompt
        if case == "candidate_drift":
            path.write_text(GOOD_MODULE + "\nChanged while reviewing.\n")
        elif case == "plan_drift":
            seed.write_text(seed.read_text().replace("review gates", "different topic"))
        return True, json.dumps(payload)
    mock = Mock(side_effect=dispatch)
    with patch("subprocess.run", side_effect=_preflight_side_effect):
        result = ReviewWorker(plane, dispatch_fn=mock).run_once()
    assert result.status == "blocked" and result.details["errors"]
    assert mock.call_count == (0 if case in ("missing_plan", "outside", "traversal") else 4)
    assert not _fetch_rows(plane.db_path, "SELECT * FROM jobs WHERE phase='patch'")
    assert not plane.iter_events("check_passed")


@pytest.mark.parametrize("case", ["minimum", "reject", "snapshot"])
def test_minimum_passing_rubric_is_bound_to_candidate_and_plan(tmp_path, case):
    reject = case == "reject"
    plane = _make_control_plane(tmp_path)
    path = _write_module(tmp_path)
    plane.enqueue(str(path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    deep = json.loads(_deep_response())
    deep["dimensions"] = {f"D{n}": 4 if n < 8 else 5 for n in range(1, 9)}
    if reject:
        deep["verdict"] = "REJECT"
        deep.update(dimensions={f"D{n}": 3 for n in range(1, 9)}, must_fix=["Untaught topic"], coverage={})
    responses = [_simple_response(key) for key in ("PRES", "NO_EMOJI", "K8S_API")]
    responses.append(json.dumps(deep))
    def dispatch(prompt, **kwargs):
        assert "unreviewed replacement" not in prompt
        path.write_text(GOOD_MODULE)
        return True, responses.pop(0)
    def preflight(*args, **kwargs):
        if case == "snapshot":
            path.write_text(GOOD_MODULE + " unreviewed replacement")
        return _preflight_side_effect(*args, **kwargs)
    with patch("subprocess.run", side_effect=preflight):
        result = ReviewWorker(plane, dispatch_fn=dispatch).run_once()
    assert result.status == ("rejected" if reject else "approved")
    assert bool(plane.iter_events("check_passed")) is not reject
    assert len(result.details["candidate_sha256"]) == len(result.details["coverage_plan_sha256"]) == 64
    assert result.details["review_role"] == "stage-check"
    assert result.details["independent_review"] is False
    assert result.details["teaching_review"]["must_fix"] == (["Untaught topic"] if reject else [])


def test_preflight_markdownlint_failure_skips_llm_and_enqueues_patch(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    dispatch = Mock()
    worker = ReviewWorker(control_plane, dispatch_fn=dispatch)

    def failing_subprocess(*args, **kwargs):
        cmd = args[0]
        if cmd[:2] == ["npx", "markdownlint-cli2"]:
            return _completed_process(
                cmd,
                returncode=1,
                stdout=f"{module_path}:12 MD032/blanks-around-lists Lists should be surrounded by blank lines",
            )
        return _completed_process(cmd)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=failing_subprocess), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        outcome = worker.run_once()

    assert outcome.status == "preflight_failed"
    dispatch.assert_not_called()
    failed_event = control_plane.iter_events("check_failed")[-1]
    payload = json.loads(failed_event["payload_json"])
    assert payload["source"] == "preflight"
    assert payload["checks"][0]["id"] == "MARKDOWNLINT"
    queued_patch = _fetch_rows(
        control_plane.db_path,
        "SELECT phase, queue_state FROM jobs WHERE phase = 'patch'",
    )
    assert len(queued_patch) == 1
    assert queued_patch[0]["queue_state"] == "pending"


def test_preflight_pass_dispatches_llm_review(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    dispatch = Mock(
        side_effect=[
            (True, _simple_response("PRES")),
            (True, _simple_response("NO_EMOJI")),
            (True, _simple_response("K8S_API")),
            (True, _deep_response()),
        ]
    )
    worker = ReviewWorker(control_plane, dispatch_fn=dispatch)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        outcome = worker.run_once()

    assert outcome.status == "approved"
    assert dispatch.call_count == 4


def test_malformed_json_retries_once_then_attempt_failed(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    dispatch = Mock(side_effect=[(True, "not json"), (True, "still not json")])
    worker = ReviewWorker(control_plane, dispatch_fn=dispatch)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        outcome = worker.run_once()

    assert outcome.status == "attempt_failed"
    assert dispatch.call_count == 2
    failed_event = control_plane.iter_events("attempt_failed")[-1]
    payload = json.loads(failed_event["payload_json"])
    assert payload["reason"] == "malformed_json"
    assert control_plane.fetch_value("SELECT COUNT(*) FROM jobs WHERE phase = 'patch'") == 0


def test_review_usage_limit_falls_back_to_gpt_5_4(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    dispatch = Mock(
        side_effect=[
            (True, "ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark."),
            (True, _simple_response("PRES")),
            (True, _simple_response("NO_EMOJI")),
            (True, _simple_response("K8S_API")),
            (True, _deep_response()),
        ]
    )
    worker = ReviewWorker(control_plane, dispatch_fn=dispatch)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        outcome = worker.run_once()

    assert outcome.status == "approved"
    models = [call.kwargs["model"] for call in dispatch.call_args_list]
    assert models == [
        REVIEW_MODEL,
        REVIEW_FALLBACK_MODEL,
        REVIEW_FALLBACK_MODEL,
        REVIEW_FALLBACK_MODEL,
        REVIEW_FALLBACK_MODEL,
    ]


def test_review_worker_enforces_review_outcomes(tmp_path):
    # (status, responses, enqueued_phase_or_None, verdict, failed_check)
    # GH #354: APPROVE no longer enqueues a `check_pre` job — that job
    # had no worker, leaving every APPROVE stuck in `pending_review`.
    # `check_passed` is now the terminal event; no follow-up phase.
    cases = [
        ("approved", [_simple_response("PRES"), _simple_response("NO_EMOJI"), _simple_response("K8S_API"), _deep_response()], None, "APPROVE", None),
        ("rejected", [_simple_response("PRES", passed=False), _simple_response("NO_EMOJI"), _simple_response("K8S_API"), _deep_response()], "patch", "REJECT", "PRES"),
        ("rejected", [_simple_response("PRES"), _simple_response("NO_EMOJI"), _simple_response("K8S_API"), _deep_response(fact_evidence="unverified: could not confirm Kubernetes 1.99 claim")], "patch", "REJECT", "FACT_CHECK"),
    ]
    for i, (status, responses, phase, verdict, failed_check) in enumerate(cases):
        case_root = tmp_path / f"case-{i}"
        control_plane = _make_control_plane(case_root)
        module_path = _write_module(case_root)
        control_plane.enqueue(str(module_path.relative_to(case_root)), phase="review", model=REVIEW_MODEL)
        worker = ReviewWorker(control_plane, dispatch_fn=Mock(side_effect=[(True, r) for r in responses]))
        with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
            "pipeline_v2.preflight._resolve_link_statuses",
            return_value={},
        ):
            outcome = worker.run_once()
        assert outcome.status == status
        event_type = "check_passed" if status == "approved" else "check_failed"
        payload = json.loads(control_plane.iter_events(event_type)[-1]["payload_json"])
        assert payload["verdict"] == verdict
        if failed_check:
            assert payload["failed_checks"][0]["id"] == failed_check
        if failed_check == "FACT_CHECK":
            assert json.loads(control_plane.iter_events("fact_check_unverified")[-1]["payload_json"])["unverified_claims"][0]["id"] == "FACT_CHECK"
        if phase is None:
            # GH #354: APPROVE enqueues no follow-up phase job.
            check_pre_rows = _fetch_rows(control_plane.db_path, "SELECT phase FROM jobs WHERE phase = 'check_pre'")
            assert check_pre_rows == []
            # And the user-visible symptom is fixed: the reducer resolves
            # the approved module to `done`, not `pending_review` (Codex
            # review nit — assert the actual regression, not just the
            # missing row).
            report = _build_status_report(control_plane.db_path)
            assert report["counts"]["done"] == 1
            assert report["counts"]["pending_review"] == 0
        else:
            queued = _fetch_rows(control_plane.db_path, "SELECT phase, model, queue_state FROM jobs WHERE phase = ?", (phase,))
            assert len(queued) == 1
            assert queued[0]["queue_state"] == "pending"
        review = local_api._load_local_api_monolith().build_module_reviews(case_root, str(module_path.relative_to(case_root)).removesuffix(".md"))
        assert review is not None
        assert review["fact_check_status"] == ("unverified" if failed_check == "FACT_CHECK" else "verified")


def test_review_worker_audit_dedupes_same_job(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    job = control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    worker = ReviewWorker(
        control_plane,
        dispatch_fn=Mock(side_effect=[(True, _simple_response("PRES")), (True, _simple_response("NO_EMOJI")), (True, _simple_response("K8S_API")), (True, _deep_response())]),
    )
    with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        assert worker.run_once().status == "approved"
    lease_id = control_plane.iter_events("check_passed")[-1]["lease_id"]
    append_review = Path(tmp_path / ".pipeline" / "reviews" / "docs__module-1.1-review-worker.md")
    before = append_review.read_text(encoding="utf-8")
    append_review_audit(module_path, "REVIEW", module_key=str(module_path.relative_to(tmp_path)).removesuffix(".md"), reviewer=REVIEW_MODEL, attempt=1, severity="none", checks=json.loads(_deep_response())["checks"], feedback="deep checks passed", verdict="APPROVE", job_id=job.job_id, lease_id=lease_id)
    assert append_review.read_text(encoding="utf-8") == before


def test_audit_preserves_v1_written_header_metadata(tmp_path):
    """v2 appending must not overwrite v1's phase/reviewer/severity header fields."""
    module_path = _write_module(tmp_path)
    review_path = tmp_path / ".pipeline" / "reviews" / "docs__module-1.1-review-worker.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        "# Review Audit: docs/module-1.1-review-worker\n\n"
        "**Path**: `docs/module-1.1-review-worker.md`\n"
        "**First pass**: 2026-04-18T09:00:00Z\n"
        "**Last pass**: 2026-04-18T09:00:00Z\n"
        "**Total passes**: 1\n"
        "**Current phase**: review\n"
        "**Current reviewer**: codex-gpt-5.4\n"
        "**Current severity**: medium\n\n"
        "---\n\n"
        "## 2026-04-18T09:00:00Z — `REVIEW` — `APPROVE`\n\n"
        "**Reviewer**: codex-gpt-5.4\n**Attempt**: 1\n**Severity**: medium\n"
        "**Checks**: 7/7 passed\n**Job Id**: v1-job-1\n**Lease Id**: v1-lease-1\n",
        encoding="utf-8",
    )
    append_review_audit(
        module_path, "REVIEW",
        module_key="docs/module-1.1-review-worker",
        reviewer="gpt-5.3-codex-spark", attempt=2, severity="none",
        checks=json.loads(_deep_response())["checks"],
        feedback="v2 added", verdict="APPROVE",
        job_id="v2-job-1", lease_id="v2-lease-1",
    )
    after = review_path.read_text(encoding="utf-8")
    # v1's header metadata must survive — NOT be replaced with "pending" / "-" / "-"
    assert "**Current phase**: review" in after
    assert "**Current reviewer**: codex-gpt-5.4" in after
    assert "**Current severity**: medium" in after
    # v2's new entry is prepended
    assert after.index("v2-job-1") < after.index("v1-job-1")
    # Duration field present in v2 entry
    assert "**Duration**:" in after
    # Both entries present
    assert "v1-job-1" in after and "v2-job-1" in after


def test_three_simple_dispatches_then_one_deep(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    dispatch = Mock(
        side_effect=[
            (True, _simple_response("PRES")),
            (True, _simple_response("NO_EMOJI")),
            (True, _simple_response("K8S_API")),
            (True, _deep_response()),
        ]
    )
    worker = ReviewWorker(control_plane, dispatch_fn=dispatch)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        worker.run_once()

    models = [call.kwargs["model"] for call in dispatch.call_args_list]
    assert models == [REVIEW_MODEL] * 4
    prompts = [call.args[0] for call in dispatch.call_args_list]
    for check_id, prompt in zip(("PRES", "NO_EMOJI", "K8S_API"), prompts[:3]):
        assert f"check_id={check_id}" in prompt or check_id in prompt
    assert "COV" in prompts[3] and "FACT_CHECK" in prompts[3]


def test_fact_check_is_deep_check():
    assert "FACT_CHECK" in DEEP_CHECK_IDS


def test_review_worker_completes_lease_and_records_usage(tmp_path):
    control_plane = _make_control_plane(tmp_path)
    module_path = _write_module(tmp_path)
    control_plane.enqueue(str(module_path.relative_to(tmp_path)), phase="review", model=REVIEW_MODEL)
    dispatch = Mock(
        side_effect=[
            (True, _simple_response("PRES")),
            (True, _simple_response("NO_EMOJI")),
            (True, _simple_response("K8S_API")),
            (True, _deep_response()),
        ]
    )
    worker = ReviewWorker(control_plane, dispatch_fn=dispatch)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=_preflight_side_effect), patch(
        "pipeline_v2.preflight._resolve_link_statuses",
        return_value={},
    ):
        outcome = worker.run_once()

    assert outcome.status == "approved"
    assert control_plane.fetch_value("SELECT COUNT(*) FROM reservations") == 0
    assert control_plane.fetch_value("SELECT COUNT(*) FROM active_leases") == 0
    assert control_plane.fetch_value("SELECT COUNT(*) FROM usage") == 1
    assert control_plane.fetch_value(
        "SELECT actual_calls FROM usage ORDER BY id DESC LIMIT 1",
    ) == 4
    assert control_plane.fetch_value(
        "SELECT queue_state FROM jobs WHERE phase = 'review' ORDER BY id ASC LIMIT 1",
    ) == "completed"
