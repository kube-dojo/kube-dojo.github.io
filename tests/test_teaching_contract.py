from __future__ import annotations

import copy
import math

import pytest

from scripts.pipeline_common.teaching_contract import validate_teaching_review

TEXT = "Explain apples. Practice sorting. Check the result."
PLAN = {
    "module_kind": "module",
    "outcomes": ["Explain apples", "Sort apples"],
    "essential_topics": ["identification", "sorting"],
    "source_basis": [{"uri": "https://example.test/source", "locator": "p. 1", "excerpt": "An apple."}],
}
PAYLOAD = {
    "dimensions": {f"D{i}": 5 for i in range(1, 9)},
    "dimension_evidence": {f"D{i}": "Explain apples." for i in range(1, 9)},
    "must_fix": [],
    "coverage": {
        "outcomes": [{"outcome": outcome, "teaching": "Explain apples.", "practice": "Practice sorting.",
                      "assessment": "Check the result."} for outcome in PLAN["outcomes"]],
        "topics": [{"topic": topic, "teaching": "Explain apples."} for topic in PLAN["essential_topics"]],
    },
    "scope_assessment": {"basis_checked": True, "unjustified_omissions": [], "rationale": "Both topics covered."},
}


def validate(payload=PAYLOAD, text=TEXT, plan=PLAN):
    return validate_teaching_review(payload, text, plan)


def test_concise_supported_fixture_passes_without_length_floor():
    assert validate() == []


@pytest.mark.parametrize("scores", [
    {**PAYLOAD["dimensions"], "D1": 3},
    {f"D{i}": 4 for i in range(1, 9)},
    {**PAYLOAD["dimensions"], "D1": True},
    {**PAYLOAD["dimensions"], "D1": math.nan},
    {**PAYLOAD["dimensions"], "D1": math.inf},
    {**PAYLOAD["dimensions"], "D1": "5"},
    {f"D{i}": 5 for i in range(1, 8)},
    {**PAYLOAD["dimensions"], "D9": 5},
])
def test_scores_cannot_hide_weak_missing_or_malformed_dimensions(scores):
    payload = copy.deepcopy(PAYLOAD)
    payload["dimensions"] = scores
    assert any("dimensions" in error for error in validate(payload))


@pytest.mark.parametrize("finding", [["material correction"], None, ""])
def test_material_or_malformed_must_fix_blocks(finding):
    payload = copy.deepcopy(PAYLOAD)
    payload["must_fix"] = finding
    assert any("must_fix" in error for error in validate(payload))


@pytest.mark.parametrize("plan", [None, {}, {**PLAN, "module_kind": ""}, {**PLAN, "module_kind": "hub"}, {**PLAN, "source_basis": []},
                                  {**PLAN, "source_basis": [{"uri": "url", "locator": "", "excerpt": "x"}]},
                                  {**PLAN, "outcomes": ["same", " same "]}])
def test_missing_research_or_invalid_plan_fails(plan):
    assert validate(plan=plan)


def test_omitted_essential_topic_blocks_even_with_every_outcome_covered():
    payload = copy.deepcopy(PAYLOAD)
    payload["coverage"]["topics"].pop()
    errors = validate(payload)
    assert any("coverage.topics" in error for error in errors)
    assert not any("coverage.outcomes" in error for error in errors)


@pytest.mark.parametrize("section", ["dimension", "teaching", "practice", "assessment", "topic"])
def test_evidence_must_be_literal_candidate_quote(section):
    payload = copy.deepcopy(PAYLOAD)
    if section == "dimension":
        payload["dimension_evidence"]["D8"] = "Not in candidate"
    elif section == "topic":
        payload["coverage"]["topics"][0]["teaching"] = "Not in candidate"
    else:
        payload["coverage"]["outcomes"][0][section] = "Not in candidate"
    assert any("must quote" in error for error in validate(payload))


def test_duplicate_outcome_and_unjustified_scope_block():
    payload = copy.deepcopy(PAYLOAD)
    payload["coverage"]["outcomes"].append(copy.deepcopy(payload["coverage"]["outcomes"][0]))
    payload["scope_assessment"]["unjustified_omissions"] = ["missing topic"]
    errors = validate(payload)
    assert any("coverage.outcomes" in error for error in errors)
    assert any("scope_assessment" in error for error in errors)


def test_unknown_topic_and_missing_dimension_evidence_block():
    payload = copy.deepcopy(PAYLOAD)
    payload["coverage"]["topics"].append({"topic": "unknown", "teaching": "Explain apples."})
    del payload["dimension_evidence"]["D2"]
    errors = validate(payload)
    assert any("coverage.topics" in error for error in errors)
    assert any("dimension_evidence" in error for error in errors)
