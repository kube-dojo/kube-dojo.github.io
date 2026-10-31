"""Tests for ``scripts.quality.prompts`` — shape + key-phrase assertions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.quality import prompts


def test_rewrite_prompt_contains_module_path() -> None:
    out = prompts.rewrite_prompt(
        module_path="src/content/docs/k8s/cka/module-1.1.md",
        module_text="---\ntitle: Foo\n---\n\nBody.\n",
        teaching_gaps=["Quiz is too easy", "No worked example"],
    )
    assert "src/content/docs/k8s/cka/module-1.1.md" in out


def test_rewrite_prompt_lists_every_gap() -> None:
    gaps = ["Quiz too easy", "No worked example", "Thin exercise"]
    out = prompts.rewrite_prompt(module_path="x.md", module_text="x", teaching_gaps=gaps)
    for g in gaps:
        assert g in out


def test_rewrite_prompt_protects_visual_aids() -> None:
    out = prompts.rewrite_prompt(module_path="x.md", module_text="x", teaching_gaps=[])
    assert "protected assets" in out or "never remove" in out


def test_rewrite_prompt_preserves_existing_sources_and_forbids_new() -> None:
    """Two-pipeline contract: writer must NEVER touch an existing `## Sources`
    section, and must NOT add a new one when none exists. Citation insertion
    runs in a separate downstream stage (`scripts/citation_backfill.py`).

    Regression guard against the v2 round-5 design hole: 241 modules already
    have a Sources section from prior backfill runs; an instruction that just
    says "don't add Sources" caused writers to silently drop existing ones."""
    out = prompts.rewrite_prompt(module_path="x.md", module_text="x", teaching_gaps=[])
    assert "Sources" in out
    # Preservation directive
    assert "verbatim" in out.lower()
    # No-new-when-absent directive
    assert "NEW" in out and "separate" in out.lower()


def test_structural_prompt_preserves_existing_sources_and_forbids_new() -> None:
    out = prompts.structural_prompt(
        module_path="x.md", module_text="---\ntitle: T\n---\nBody.\n",
        missing_sections=["quiz"],
    )
    assert "Sources" in out
    assert "verbatim" in out.lower()
    assert "NEW" in out


def test_rewrite_prompt_preserves_style_without_banning_arbitrary_numbers() -> None:
    out = prompts.rewrite_prompt(module_path="x.md", module_text="x", teaching_gaps=[])
    assert "Do NOT use the number 47" not in out
    assert "emoji" in out.lower()


def test_actual_authoring_inputs_share_coverage_and_shortfall_contract(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(prompts, "_RULES_PATH", root / ".claude/rules/module-quality.md")
    monkeypatch.setattr(prompts, "_FRAMEWORK_PATH", root / "docs/pedagogical-framework.md")
    outputs = [prompts.rewrite_prompt(module_path="x.md", module_text="47 objects", teaching_gaps=[]),
               prompts.structural_prompt(module_path="x.md", module_text="47 objects", missing_sections=["quiz"]),
               (root / "scripts/prompts/module-writer.md").read_text()]
    contradictions = ("exactly 4 facts", "6-8 rows", "6-8 quiz questions", "NO recall questions",
                      "No recall questions", "Do NOT repeat the number 47", "Do NOT use the number 47",
                      "Do NOT write quiz questions that test recall")
    for text in outputs:
        assert not any(phrase in text for phrase in contradictions)
        assert "coverage_plan" in text and "shortfall" in text and "docs/citation-seeds" in text
        assert "#3744" in text and "padding" in text


def test_defined_evidence_shortfall_cannot_be_extracted_as_a_publishable_module() -> None:
    from scripts.quality.extractors import ModuleExtractError, extract_module_markdown

    report = "EVIDENCE_SHORTFALL: Research unavailable\nMissing inputs: source_basis\nNext action: lead supplies plan"
    with pytest.raises(ModuleExtractError):
        extract_module_markdown(report)


def test_structural_prompt_lists_missing_sections() -> None:
    missing = ["quiz", "hands-on-exercise"]
    out = prompts.structural_prompt(
        module_path="x.md", module_text="---\ntitle: T\n---\nBody.\n", missing_sections=missing
    )
    for s in missing:
        assert s in out
    assert "do NOT rewrite existing content" in out or "Preserve every existing line" in out


def test_review_prompt_names_writer_and_track() -> None:
    out = prompts.review_prompt(
        module_path="x.md",
        module_text="---\ntitle: T\n---\n",
        writer_agent="codex",
        track="rewrite",
        original_gaps=["Quiz weak"],
    )
    assert "codex" in out
    assert "rewrite" in out
    assert "Quiz weak" in out


def test_review_prompt_specifies_approve_gate() -> None:
    out = prompts.review_prompt(
        module_path="x.md", module_text="x", writer_agent="claude", track="structural",
        original_gaps=[],
    )
    # 4.0 gate on both axes — regression guard.
    assert "teaching_score >= 4.0" in out
    assert "rubric_score >= 4.0" in out


def test_review_prompt_ignores_sources_section() -> None:
    out = prompts.review_prompt(
        module_path="x.md", module_text="x", writer_agent="claude", track="rewrite",
        original_gaps=[],
    )
    # v1 had this leak: rubric text penalized missing Sources while the
    # prompt told the reviewer to ignore them. Regression guard —
    # ignore wording must be present.
    assert "Sources" in out
    assert "ignore" in out.lower() or "do not penalize" in out.lower()


def test_review_prompt_asks_for_json_at_end() -> None:
    """Regression guard for extractor-#8: prompt must tell the LLM to
    put the verdict JSON LAST so ``extract_last_json`` wins."""
    out = prompts.review_prompt(
        module_path="x.md", module_text="x", writer_agent="claude", track="rewrite",
        original_gaps=[],
    )
    assert "LAST" in out or "END of your response" in out


def test_review_prompt_specifies_structural_preservation() -> None:
    out = prompts.review_prompt(
        module_path="x.md", module_text="x", writer_agent="codex", track="structural",
        original_gaps=[],
    )
    assert "PRESERVED" in out or "preserve" in out.lower()


def test_citation_verify_prompt_strict_language() -> None:
    out = prompts.citation_verify_prompt(
        page_content="Some page markdown", claim="Kubernetes was announced in 2014", url="https://example.com/",
    )
    # Strict wording: must carry through the "we don't publish lies" policy.
    assert "STRICT" in out
    assert "CLEARLY AND EXPLICITLY" in out
    assert "supports" in out
    assert "partial" in out
    assert "no" in out


def test_citation_verify_prompt_truncates_long_pages() -> None:
    long_page = "x" * 100_000
    out = prompts.citation_verify_prompt(
        page_content=long_page, claim="a claim", url="https://example.com/",
    )
    assert "truncated" in out.lower()
    # The whole page didn't make it in — prompt stays under ~16k of page content.
    assert out.count("x") < 20_000


def test_citation_verify_prompt_includes_url_and_claim() -> None:
    out = prompts.citation_verify_prompt(
        page_content="page", claim="a specific claim", url="https://example.org/path",
    )
    assert "https://example.org/path" in out
    assert "a specific claim" in out


def test_build_audit_context_handles_none() -> None:
    assert prompts.build_audit_context(None) == []


def test_build_audit_context_reads_teaching_gaps() -> None:
    audit = {"teaching_gaps": ["Quiz weak", "No exercise"]}
    assert prompts.build_audit_context(audit) == ["Quiz weak", "No exercise"]


def test_build_audit_context_falls_back_to_gaps_key() -> None:
    audit = {"gaps": ["Only a draft"]}
    assert prompts.build_audit_context(audit) == ["Only a draft"]


def test_assert_required_docs_raises_when_missing(tmp_path, monkeypatch) -> None:
    """Startup-time check — missing framework / rubric must fail fast."""
    monkeypatch.setattr(prompts, "_RUBRIC_PATH", tmp_path / "missing-rubric.md")
    with pytest.raises(FileNotFoundError, match="missing prompt docs"):
        prompts.assert_required_docs_exist()
