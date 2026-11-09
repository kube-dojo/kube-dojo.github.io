from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pipeline_v4  # noqa: E402


@dataclass
class ExpandResult:
    module_key: str
    gaps_processed: list[str]
    gaps_filled: list[str]
    gaps_failed: list[tuple[str, str]]
    loc_before: int
    loc_after: int
    diff: str
    provenance_blocks_added: int


MODULE_KEY = "platform/foo/module-1.1-pipeline-v4-fixture"
MODULE_TEXT = """---
title: "Pipeline v4 Fixture"
sidebar:
  order: 1
---

## Why This Module Matters

Operators need a stable fixture for pipeline orchestration tests.

## Deep Dive

This section is intentionally short.

## Sources

- [Fixture Source](https://example.com/fixture)
"""


def _write_module(root: Path, module_key: str = MODULE_KEY, text: str = MODULE_TEXT) -> Path:
    path = root / "src" / "content" / "docs" / f"{module_key}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _patch_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pipeline_v4, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pipeline_v4, "DOCS_ROOT", tmp_path / "src" / "content" / "docs")
    monkeypatch.setattr(pipeline_v4, "PIPELINE_V4_DIR", tmp_path / ".pipeline" / "v4")
    monkeypatch.setattr(pipeline_v4, "RUNS_DIR", tmp_path / ".pipeline" / "v4" / "runs")


def _expand_result(
    module_key: str = MODULE_KEY,
    *,
    gaps_filled: list[str] | None = None,
    gaps_failed: list[tuple[str, str]] | None = None,
    loc_before: int = 200,
    loc_after: int = 600,
) -> ExpandResult:
    return ExpandResult(
        module_key=module_key,
        gaps_processed=list(gaps_filled or []),
        gaps_filled=list(gaps_filled or []),
        gaps_failed=list(gaps_failed or []),
        loc_before=loc_before,
        loc_after=loc_after,
        diff="",
        provenance_blocks_added=1 if gaps_filled else 0,
    )


def _patch_rescore_sequence(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[dict[str, object]],
) -> None:
    queue = [
        {
            "score": float(item["score"]),
            "gaps": list(item.get("gaps", [])),
            "primary_issue": item.get("primary_issue", ""),
            "entry": {"path": f"{MODULE_KEY}.md"},
        }
        for item in responses
    ]

    def _rescore(module_key: str) -> dict[str, object]:
        assert module_key == MODULE_KEY
        if not queue:
            raise AssertionError("unexpected extra rescore")
        return queue.pop(0)

    monkeypatch.setattr(pipeline_v4, "_rescore_module", _rescore)


def _patch_citation_ok(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def _invoke(module_key: str) -> dict[str, object]:
        calls.append(module_key)
        return {"exit_code": 0, "stdout_tail": ["citation ok"], "stderr_tail": []}

    monkeypatch.setattr(pipeline_v4, "_invoke_citation_pipeline", _invoke)
    return calls


def test_stage_1_skip_goes_directly_to_citation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 4.5, "gaps": [], "target_loc": 600},
    )

    expand_calls: list[str] = []

    def _unexpected_expand(*args, **kwargs):
        expand_calls.append("expand")
        raise AssertionError("expand_module should not run for already-stable modules")

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _unexpected_expand)
    _patch_rescore_sequence(monkeypatch, [{"score": 4.6, "gaps": []}])
    citation_calls = _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert expand_calls == []
    assert citation_calls == [MODULE_KEY]
    assert result.outcome == "skipped_already_stable"
    assert result.stage_reached == "DONE"
    assert "EXPAND" not in [event["stage"] for event in result.events]
    assert "CITATION_V3" in [event["stage"] for event in result.events]


def test_stage_2_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {
            "score": 2.0,
            "gaps": ["thin", "no_quiz"],
            "target_loc": 600,
        },
    )
    expand_calls: list[tuple[list[str], int, bool]] = []

    def _expand(module_key: str, gaps: list[str], target_loc: int = 600, dry_run: bool = False):
        expand_calls.append((list(gaps), target_loc, dry_run))
        return _expand_result(gaps_filled=["thin", "no_quiz"], loc_after=600)

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _expand)
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 4.5, "gaps": []},
            {"score": 4.5, "gaps": []},
        ],
    )
    _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert expand_calls == [(["thin", "no_quiz"], 600, False)]
    assert result.outcome == "clean"
    assert result.stage_reached == "DONE"
    assert result.retry_count == 0
    assert result.citation_v3_exit == 0


def test_public_run_pipeline_v4_accepts_skip_citation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {
            "score": 2.0,
            "gaps": ["thin", "no_quiz"],
            "target_loc": 600,
        },
    )
    monkeypatch.setattr(
        pipeline_v4.expand_module,
        "expand_module",
        lambda module_key, gaps, target_loc=600, dry_run=False: _expand_result(
            gaps_filled=["thin", "no_quiz"],
            loc_after=600,
        ),
    )
    _patch_rescore_sequence(monkeypatch, [{"score": 4.4, "gaps": []}])

    def _unexpected_citation(module_key: str) -> dict[str, object]:
        raise AssertionError("skip_citation=True should not invoke citation_v3")

    monkeypatch.setattr(pipeline_v4, "_invoke_citation_pipeline", _unexpected_citation)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY, skip_citation=True)

    assert result.outcome == "clean"
    assert result.stage_reached == "DONE"
    assert result.citation_v3_exit is None


def test_stage_3_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 2.0, "gaps": ["thin", "no_quiz"], "target_loc": 600},
    )
    expand_calls: list[list[str]] = []

    def _expand(module_key: str, gaps: list[str], target_loc: int = 600, dry_run: bool = False):
        expand_calls.append(list(gaps))
        return _expand_result(gaps_filled=gaps, loc_after=600)

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _expand)
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 3.5, "gaps": ["thin"]},
            {"score": 4.5, "gaps": []},
            {"score": 4.5, "gaps": []},
        ],
    )
    _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert expand_calls == [["thin", "no_quiz"], ["thin"]]
    assert result.retry_count == 1
    assert result.outcome == "clean"


def test_stage_3_retry_uses_newly_surfaced_gap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Dogfood scenario: rescore surfaces a gap that wasn't in the original list.

    Attempt 0 fills the original gaps (thin, no_quiz). Stage 3 rescore
    drops those but surfaces no_exercise — a gap that was shadowed by the
    original compound issue. The retry must act on [no_exercise], not on
    the stale original list.
    """
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 2.0, "gaps": ["thin", "no_quiz"], "target_loc": 600},
    )
    expand_calls: list[list[str]] = []

    def _expand(module_key: str, gaps: list[str], target_loc: int = 600, dry_run: bool = False):
        expand_calls.append(list(gaps))
        return _expand_result(gaps_filled=gaps, loc_after=600)

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _expand)
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 3.9, "gaps": ["no_exercise"]},
            {"score": 4.3, "gaps": []},
            {"score": 4.3, "gaps": []},
        ],
    )
    _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert expand_calls == [["thin", "no_quiz"], ["no_exercise"]]
    assert result.retry_count == 1
    assert result.outcome == "clean"
    assert result.gaps_before == ["thin", "no_quiz"]


def test_stage_3_retry_budget_exhausted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 2.0, "gaps": ["thin"], "target_loc": 600},
    )
    expand_calls: list[int] = []

    def _expand(module_key: str, gaps: list[str], target_loc: int = 600, dry_run: bool = False):
        expand_calls.append(len(expand_calls))
        return _expand_result(gaps_filled=gaps, loc_after=500)

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _expand)
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 3.2, "gaps": ["thin"]},
            {"score": 3.3, "gaps": ["thin"]},
            {"score": 3.4, "gaps": ["thin"]},
        ],
    )

    def _unexpected_citation(module_key: str) -> dict[str, object]:
        raise AssertionError("citation_v3 should not run when rubric retries are exhausted")

    monkeypatch.setattr(pipeline_v4, "_invoke_citation_pipeline", _unexpected_citation)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY, max_rubric_retries=2)

    assert len(expand_calls) == 3
    assert result.retry_count == 2
    assert result.outcome == "residuals_filed"
    assert result.reason == "rubric_stage_3_unmet"
    assert result.stage_reached == "RUBRIC_RECHECK"


def test_skip_stage_2_when_only_stage_4_gaps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If Stage 1 surfaces only gaps that expand_module can't handle
    (no_citations / no_diagram), skip Stage 2 entirely and go to
    Stage 4. Otherwise we waste the whole retry budget on no-op
    expansions and fail rubric_stage_3_unmet without ever running
    citation_v3."""
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 1.5, "gaps": ["no_citations"], "target_loc": 600},
    )

    def _unexpected_expand(*args, **kwargs):
        raise AssertionError("expand_module should not run when gaps are stage-4-only")

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _unexpected_expand)
    _patch_rescore_sequence(monkeypatch, [{"score": 3.8, "gaps": []}])
    citation_calls = _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert citation_calls == [MODULE_KEY]
    assert result.retry_count == 0
    assert result.outcome == "clean"
    stages = [event["stage"] for event in result.events]
    assert "EXPAND" not in stages
    assert "RUBRIC_RECHECK" not in stages
    assert "CITATION_V3" in stages


def test_break_to_stage_4_when_retry_gaps_become_stage_4_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """After Stage 2 fills the expandable gaps, if the rescore's
    remaining gaps are only no_citations / no_diagram, proceed to
    Stage 4 instead of retrying Stage 2."""
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {
            "score": 1.5,
            "gaps": ["no_quiz", "no_citations"],
            "target_loc": 600,
        },
    )
    expand_calls: list[list[str]] = []

    def _expand(module_key: str, gaps: list[str], target_loc: int = 600, dry_run: bool = False):
        expand_calls.append(list(gaps))
        return _expand_result(gaps_filled=["no_quiz"])

    monkeypatch.setattr(pipeline_v4.expand_module, "expand_module", _expand)
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 3.7, "gaps": ["no_citations"]},
            {"score": 3.9, "gaps": []},
        ],
    )
    _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert len(expand_calls) == 1, "should not retry after no_citations-only rescore"
    assert result.retry_count == 0
    assert result.outcome == "clean"


def test_generated_loc_threshold_is_deprecated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    generated_text = "\n".join(
        [
            "---",
            'title: "Generated Fixture"',
            "sidebar:",
            "  order: 1",
            "---",
            "## Intro",
            "One human line.",
            "<!-- v4:generated type=thin model=gemini turn=1 -->",
            *[f"generated line {index}" for index in range(1, 21)],
            "<!-- /v4:generated -->",
            "",
        ]
    )
    _write_module(tmp_path, text=generated_text)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 4.5, "gaps": [], "target_loc": 600},
    )
    called = []

    def _invoke_citation(module_key: str) -> dict[str, object]:
        called.append(module_key)
        return {"exit_code": 0, "stdout_tail": ['{"status": "clean"}'], "stderr_tail": []}

    monkeypatch.setattr(pipeline_v4, "_invoke_citation_pipeline", _invoke_citation)
    _patch_rescore_sequence(monkeypatch, [{"score": 4.5, "gaps": []}, {"score": 4.5, "gaps": []}])

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY, generated_loc_threshold=0.5)

    assert called == [MODULE_KEY]
    assert result.outcome == "skipped_already_stable"
    assert result.reason == ""
    assert result.stage_reached == "DONE"


def test_citation_residuals_queued_is_residuals_filed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """pipeline_v3 exits non-zero with status="residuals_queued" when
    it's audited the module and routed un-auto-fixable items to human
    review. That's a legitimate outcome, not a pipeline failure, so
    pipeline_v4 should classify it as residuals_filed and still run the
    final rescore — not short-circuit out as failed."""
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 1.5, "gaps": ["no_citations"], "target_loc": 600},
    )

    def _residuals(module_key: str) -> dict[str, object]:
        return {
            "exit_code": 1,
            "stdout_tail": [
                "{",
                f'  "module_key": "{MODULE_KEY}",',
                '  "status": "residuals_queued",',
                '  "overstatement_applied": 0,',
                '  "off_topic_deleted": 0,',
                '  "queued_total": 3',
                "}",
            ],
            "stderr_tail": [],
        }

    monkeypatch.setattr(pipeline_v4, "_invoke_citation_pipeline", _residuals)
    _patch_rescore_sequence(monkeypatch, [{"score": 1.5, "gaps": ["no_citations"]}])

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert result.outcome == "residuals_filed"
    assert result.reason == "citation_residuals_queued"
    assert result.stage_reached == "DONE"
    assert result.citation_v3_exit == 1


def test_citation_v3_hard_failure_still_marked_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A non-zero citation_v3 exit with no recognizable status (crash,
    malformed output, etc.) is still a hard failure — don't treat
    anything except status="residuals_queued" as non-fatal."""
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 1.5, "gaps": ["no_citations"], "target_loc": 600},
    )
    monkeypatch.setattr(
        pipeline_v4,
        "_invoke_citation_pipeline",
        lambda module_key: {
            "exit_code": 2,
            "stdout_tail": ["Traceback (most recent call last):", "RuntimeError: oops"],
            "stderr_tail": [],
        },
    )

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)
    assert result.outcome == "failed"
    assert result.reason == "citation_v3_failed"


def test_parse_citation_status(monkeypatch: pytest.MonkeyPatch) -> None:
    assert pipeline_v4._parse_citation_status([]) is None
    assert pipeline_v4._parse_citation_status(["no json here"]) is None
    tail = ["{", '  "status": "residuals_queued",', '  "queued_total": 4', "}"]
    assert pipeline_v4._parse_citation_status(tail) == "residuals_queued"
    clean_tail = ['{"status": "clean"}']
    assert pipeline_v4._parse_citation_status(clean_tail) == "clean"


def test_stage_5_regression(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 2.0, "gaps": ["thin"], "target_loc": 600},
    )
    monkeypatch.setattr(
        pipeline_v4.expand_module,
        "expand_module",
        lambda module_key, gaps, target_loc=600, dry_run=False: _expand_result(gaps_filled=["thin"], loc_after=600),
    )
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 4.5, "gaps": []},
            {"score": 4.0, "gaps": []},
        ],
    )
    _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert result.outcome == "failed"
    assert result.reason == "final_rescore_regressed"
    assert result.score_after == 4.0


def test_stage_5_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 2.0, "gaps": ["thin"], "target_loc": 600},
    )
    monkeypatch.setattr(
        pipeline_v4.expand_module,
        "expand_module",
        lambda module_key, gaps, target_loc=600, dry_run=False: _expand_result(gaps_filled=["thin"], loc_after=600),
    )
    _patch_rescore_sequence(
        monkeypatch,
        [
            {"score": 4.5, "gaps": []},
            {"score": 4.4, "gaps": []},
        ],
    )
    _patch_citation_ok(monkeypatch)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY)

    assert result.outcome == "clean"
    assert result.reason == ""
    assert result.score_after == 4.4


def test_dry_run_skips_stage_log_writes_and_citation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 4.5, "gaps": [], "target_loc": 600},
    )

    def _unexpected_citation(module_key: str) -> dict[str, object]:
        raise AssertionError("dry-run should not invoke citation_v3")

    monkeypatch.setattr(pipeline_v4, "_invoke_citation_pipeline", _unexpected_citation)

    result = pipeline_v4.run_pipeline_v4(MODULE_KEY, dry_run=True)

    assert result.outcome == "skipped_already_stable"
    assert result.citation_v3_exit is None
    assert not pipeline_v4.RUNS_DIR.exists()


def test_cli_emits_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_module(tmp_path)
    monkeypatch.setattr(
        pipeline_v4.rubric_gaps,
        "gaps_for_module",
        lambda module_key: {"score": 4.5, "gaps": [], "target_loc": 600},
    )
    result = pipeline_v4.PipelineV4Result(
        module_key=MODULE_KEY,
        started_at="2026-04-21T12:00:00+00:00",
        finished_at="2026-04-21T12:00:01+00:00",
        stage_reached="DONE",
        outcome="skipped_already_stable",
        reason="",
        score_before=4.5,
        score_after=4.5,
        gaps_before=[],
        gaps_after=[],
        retry_count=0,
        citation_v3_exit=None,
        events=[],
    )
    monkeypatch.setattr(pipeline_v4, "_run_pipeline_v4", lambda *args, **kwargs: result)

    exit_code = pipeline_v4.main([MODULE_KEY, "--dry-run"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["module_key"] == MODULE_KEY
    assert payload["outcome"] == "skipped_already_stable"


def test_invoke_citation_pipeline_uses_repo_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: Stage 4 should run citation_v3 using the repo venv python
    path (which is discoverable from worktrees), not the ambient
    interpreter."""
    captured: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def _fake_run(cmd: list[str], **kwargs: object) -> _Completed:
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        return _Completed()

    monkeypatch.setattr(pipeline_v4.subprocess, "run", _fake_run)

    pipeline_v4._invoke_citation_pipeline(MODULE_KEY)

    cmd = captured["cmd"]
    assert isinstance(cmd, list) and cmd, "subprocess.run called with no command"
    assert str(cmd[0]).endswith(".venv/bin/python"), f"expected venv python, got {cmd[0]!r}"
    assert cmd[1].endswith("pipeline_v3.py")
