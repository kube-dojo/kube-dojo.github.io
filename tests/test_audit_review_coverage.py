import pytest

from scripts import audit_review_coverage as audit
from scripts.audit_review_coverage import _expected_lane_fields, _lane_satisfied


def test_part6_claude_research_requires_codex_and_gemini_reviews():
    assert _expected_lane_fields(32, "research") == {"codex_anchor", "gemini_gap"}
    assert _expected_lane_fields(37, "research") == {"codex_anchor", "gemini_gap"}


def test_part6_exception_does_not_apply_after_ch37():
    assert _expected_lane_fields(38, "research") == {"claude_anchor", "gemini_gap"}


def test_part6_codex_gemini_research_markers_satisfy_cross_family_rule():
    values = {
        "claude_anchor": "n/a",
        "gemini_gap": "done",
        "codex_anchor": "done",
    }

    assert _lane_satisfied(values, 32, "research") is True


@pytest.mark.parametrize("lane", ["research", "prose", "unknown"])
@pytest.mark.parametrize("values", [{}, {"claude_anchor": "n/a"}, {"grok_prose": "done", "deepseek_prose": "done"}])
def test_missing_lane_evidence_is_not_coverage(lane, values):
    assert not _lane_satisfied(values, 73, lane)


@pytest.mark.parametrize("title", [None, "docs: Chapter 73 research contract", "research: Ch73", "prose: Ch73"])
@pytest.mark.parametrize("evidence", ["none", "failed", "wrong_phase"])
def test_missing_pr_or_comments_stays_pending(tmp_path, monkeypatch, title, evidence):
    chapter = tmp_path / "ch-73-test"
    chapter.mkdir()
    (chapter / "status.yaml").write_text("status: researching\n")
    monkeypatch.setattr(audit, "CHAPTER_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_fetch_prs", lambda: [] if title is None else [{"number": 1, "title": title}])
    prefix = "verdict" if title == "research: Ch73" else "prose review"
    if evidence == "wrong_phase":
        prefix = "prose review" if prefix == "verdict" else "verdict"
    comments = [f"<!-- {prefix} {family} -->\n\n_FAILED_\n\n_dispatch failed_: timeout" if evidence == "failed" else f"<!-- {prefix} {family} -->" for family in ("claude", "gemini")]
    monkeypatch.setattr(audit, "_fetch_comment_bodies", lambda _: comments if evidence != "none" else [])
    coverage = audit._build_coverage(strict_gh=True)[73]
    assert audit._summary_rows({73: coverage})[0][1:4] == (False, False, True)
    assert "done" not in (*coverage.research.values(), *coverage.prose.values())
    assert "pending" in coverage.research.values() and "pending" in coverage.prose.values()
    assert "  backfill_pending: true" in audit._coverage_block(coverage)


@pytest.mark.parametrize("chapter_num", [11, 16, 38, 73])
@pytest.mark.parametrize("status", ["researching", "accepted"])
def test_offline_labels_and_pending_verdicts_are_not_evidence(tmp_path, monkeypatch, chapter_num, status):
    path = tmp_path / f"ch-{chapter_num}-test" / "status.yaml"
    path.parent.mkdir()
    text = f"status: {status}\nverdicts:\n  claude: null\n  gemini: pending\n  codex: null\nnotes: review approved\n"
    path.write_text(text)
    monkeypatch.setattr(audit, "CHAPTER_ROOT", tmp_path)
    def unavailable():
        raise RuntimeError("offline")
    monkeypatch.setattr(audit, "_fetch_prs", unavailable)
    coverage = audit._build_coverage(strict_gh=False)[chapter_num]
    assert audit._summary_rows({chapter_num: coverage})[0][1:] == (False, False, True, "offline")
    monkeypatch.setattr("sys.argv", ["audit", "--write"])
    with pytest.raises(RuntimeError, match="offline"):
        audit.main()
    assert path.read_text() == text


@pytest.mark.parametrize("chapter_num,anchor", [(32, "codex"), (73, "claude")])
def test_observed_markers_accumulate_without_implying_approval(chapter_num, anchor):
    coverage = audit.ChapterCoverage(chapter_num, "test")
    audit._apply_comment_markers(coverage, "research", [f"<!-- verdict {anchor} --> NEEDS_CHANGES", "<!-- verdict gemini -->"])
    assert _lane_satisfied(coverage.research, chapter_num, "research")
    audit._apply_comment_markers(coverage, "prose", ["<!-- prose review claude --> NEEDS_CHANGES"])
    assert not _lane_satisfied(coverage.prose, chapter_num, "prose")
    audit._apply_comment_markers(coverage, "prose", ["<!-- prose review codex -->"])
    audit._apply_comment_markers(coverage, "prose", [])
    assert coverage.prose["claude_source_fidelity"] == coverage.prose["codex_prose_quality"] == "done"
    assert _lane_satisfied(coverage.prose, chapter_num, "prose")
