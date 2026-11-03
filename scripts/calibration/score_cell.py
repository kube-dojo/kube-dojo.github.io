"""Per-lane deterministic scoring and optional LLM judge wiring."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

from . import schema
from .models import model_by_canonical
from .run_cell import (
    DEFAULT_DB_PATH,
    DEFAULT_OUTPUT_ROOT,
    REPO_ROOT,
    DispatchResult,
    dispatch_prompt,
)
from .scorers import respected_inline_return

GROUND_TRUTH_ROOT = REPO_ROOT / "scripts" / "calibration" / "ground-truth" / "v1"
PROSE_LANES: frozenset[str] = frozenset(
    {
        "orchestrating",
        "refactoring",
        "summarization",
        "content-writing-long",
        "architecting",
        # mcp-use / harness-following: ratio-gates can be keyword-gamed; judge unconditionally.
        "mcp-use",
        "harness-following",
        "content-review",
        "fact-check",
    },
)


class LaneScorer(Protocol):
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        ...

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        ...


def _contains_all(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return all(term.lower() in lowered for term in terms)


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _term_present(text: str, term: "str | dict[str, Any]") -> bool:
    """Check if a term (flat string or alias-dict) appears in text."""
    if isinstance(term, dict):
        aliases = list(term.get("aliases", []))
        return _contains_any(text, aliases) if aliases else False
    return _contains_any(text, [term])


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _extract_fenced_code(response: str, language: str = "python") -> str:
    pattern = re.compile(
        rf"```(?:{re.escape(language)})?\s*\n(.*?)```",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(response)
    if match:
        return match.group(1).strip() + "\n"
    return response.strip() + "\n"


def run_command(
    args: list[str],
    *,
    cwd: Path,
    timeout_s: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


class CodeWritingScorer:
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        code = _extract_fenced_code(response)
        tests_py = str(ground_truth["tests_py"])
        with tempfile.TemporaryDirectory(prefix="calibration-code-writing-") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "solution.py").write_text(code, encoding="utf-8")
            (tmp_path / "test_solution.py").write_text(tests_py, encoding="utf-8")
            pytest_result = run_command(
                [".venv/bin/python", "-m", "pytest", str(tmp_path / "test_solution.py")],
                cwd=REPO_ROOT,
            )
            ruff_result = run_command(
                [".venv/bin/ruff", "check", str(tmp_path / "solution.py")],
                cwd=REPO_ROOT,
            )
        return {
            "pytest_exit": pytest_result.returncode == 0,
            "ruff_exit": ruff_result.returncode == 0,
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return None


class CodeReviewScorer:
    """Code-review scoring with ratio-gates, not binary AND.

    The v1 design (binary AND of ``ground_truth_findings`` + ``no_hallucinations``)
    collapsed to exactly 0.50 across all 8 Wave A+B models — every model hit some
    findings AND coughed up at least one hallucination term, so both gates were
    half-pass and the AND was always exactly 0.5. v1.2 replaces this with:

      - ``finding_recall``: fraction of planted findings hit (pass @ ≥0.6, the
        Wave-A floor; raise to ≥0.75 once data shows a tier separation).
      - ``hallucination_rate``: fraction of hallucination terms present
        (pass @ ≤0.25 — i.e., at most one bogus term in a 4-term list).

    Two ratio gates instead of two binary gates means the joint score range is
    {0.0, 0.5, 1.0} instead of just 0.5 — restores discrimination.
    """

    FINDING_RECALL_THRESHOLD = 0.6
    HALLUCINATION_RATE_THRESHOLD = 0.25

    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        findings = list(ground_truth.get("findings", []))
        if not findings:
            recall_ratio = 1.0
        else:
            hits = sum(
                1
                for finding in findings
                if _contains_any(response, list(finding.get("aliases", [])))
            )
            recall_ratio = hits / len(findings)

        hallucination_terms = list(ground_truth.get("hallucination_terms", []))
        if not hallucination_terms:
            hallucination_ratio = 0.0
        else:
            present = sum(
                1
                for term in hallucination_terms
                if _contains_any(response, [term])
            )
            hallucination_ratio = present / len(hallucination_terms)

        return {
            "finding_recall": recall_ratio >= self.FINDING_RECALL_THRESHOLD,
            "hallucination_rate": hallucination_ratio <= self.HALLUCINATION_RATE_THRESHOLD,
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return None


class ContentWritingLongScorer:
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        # Since #3744 the verifier tier follows blocking defects only; length,
        # density and template counts no longer move it, so this gate does
        # not reward or punish a response for being long or short.
        tier = _verifier_tier(response)
        accepted_tiers = set(ground_truth.get("accepted_verifier_tiers", ["T0", "T1"]))
        mermaid_pattern = re.compile(r"```\s*mermaid\b.*?```", re.IGNORECASE | re.DOTALL)
        topic_terms = list(ground_truth.get("topic_terms", []))
        return {
            "verifier_t0_t1": tier in accepted_tiers,
            "mermaid_block": bool(mermaid_pattern.search(response)),
            "topic_relevance": not topic_terms or _contains_any(response, topic_terms),
            "no_simply": not re.search(r"\bsimply\b", response, re.IGNORECASE),
            "bloom_l3_outcomes": _contains_any(
                response,
                list(ground_truth.get("bloom_l3_terms", [])),
            ),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        default_instruction = (
            "Score whether the module actually teaches the topic, not "
            "just rephrases upstream docs."
        )
        instruction = ground_truth.get("judge_instruction", default_instruction)
        return _judge_prompt(
            "pedagogy",
            response,
            instruction,
            ground_truth,
        )


class ContentReviewScorer:
    """Content-review scoring with ratio-gates, not binary AND.

    The v1 design (binary AND of ``planted_flaw_recall`` + ``review_precision``)
    collapsed to exactly 0.50 across all 14 Wave A models — every model hit some
    flaws AND mentioned at least one hallucination term, so both gates were
    half-pass and the AND was always exactly 0.5. v1.2 replaces this with:

      - ``finding_recall``: fraction of planted flaws hit (pass @ ≥0.6).
      - ``hallucination_rate``: fraction of hallucination terms present
        (pass @ ≤0.25 — at most one bogus term in a 4-term list).

    Two ratio gates instead of two binary gates means the joint score range is
    {0.0, 0.5, 1.0} instead of just 0.5 — restores discrimination.
    """

    PLANTED_FLAW_RECALL_THRESHOLD = 0.6
    HALLUCINATION_RATE_THRESHOLD = 0.25

    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        flaws = list(ground_truth.get("planted_flaws", []))
        if not flaws:
            recall_ratio = 1.0
        else:
            found = sum(
                1
                for flaw in flaws
                if _contains_any(response, list(flaw.get("aliases", [])))
            )
            recall_ratio = found / len(flaws)

        hallucination_terms = list(ground_truth.get("hallucination_terms", []))
        if not hallucination_terms:
            hallucination_ratio = 0.0
        else:
            present = sum(
                1
                for term in hallucination_terms
                if _contains_any(response, [term])
            )
            hallucination_ratio = present / len(hallucination_terms)

        return {
            "finding_recall": recall_ratio >= self.PLANTED_FLAW_RECALL_THRESHOLD,
            "hallucination_rate": hallucination_ratio <= self.HALLUCINATION_RATE_THRESHOLD,
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "content-review",
            response,
            (
                "Score the review's quality at distinguishing real flaws from "
                "stylistic noise. Reward concrete file:line evidence, correct "
                "flaw class attribution, and verdict severity that matches the "
                "actual planted defect. Penalize generic 'looks good' verdicts, "
                "hallucinated flaws not in the planted set, and missed flaws "
                "of high severity."
            ),
            ground_truth,
        )


class FactCheckScorer:
    """Fact-check scoring with a ratio verdict gate and robust JSON parsing.

    v1 had two issues:
      - ``verdict_class_match`` required ALL verdicts correct (binary AND), so a
        single wrong verdict collapsed the score — same 0.5-floor antipattern as
        ContentReviewScorer. v1.2 replaces this with ``verdict_recall``: fraction
        of claims matched (pass @ ≥0.75).
      - ``_parse_json_response`` failed on prose-prefixed JSON (qwen3.6, grok-4.3,
        dsv4-flash all prefix the JSON array with a sentence). v1.2 adds a
        balanced bracket scanner as a third extraction path after fenced-block.
    """

    VERDICT_RECALL_THRESHOLD = 0.75

    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        verdicts = _parse_json_response(response)
        expected = {
            claim["claim_id"]: claim["verdict"]
            for claim in ground_truth.get("claims", [])
        }
        matched = 0
        cited = 0
        for item in verdicts:
            claim_id = item.get("claim_id")
            verdict = item.get("verdict")
            rationale = str(item.get("rationale", ""))
            if expected.get(claim_id) == verdict:
                matched += 1
            if "http://" in rationale or "https://" in rationale:
                cited += 1
        total = len(expected)
        return {
            "verdict_recall": total > 0 and matched / total >= self.VERDICT_RECALL_THRESHOLD,
            "citation_grounding": total > 0 and cited >= int(ground_truth.get("min_citations", 3)),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "fact-check",
            response,
            (
                "Score the rationale-grounding quality of partial-verdict cells. "
                "Reward primary-source citations (project docs, RFCs, release "
                "notes), specific dates/versions, and verdict reasoning that "
                "tracks the actual claim. Penalize unsourced confidence, vague "
                "'common knowledge' appeals, and citations that don't actually "
                "support the verdict."
            ),
            ground_truth,
        )


class ArchitectingScorer:
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        required = list(ground_truth.get("required_categories", []))
        covered = [category for category in required if _contains_any(response, [category])]
        novel_terms = list(ground_truth.get("novel_risk_terms", []))
        required_ratio = len(covered) / len(required) if required else 1.0
        return {
            "required_category_ratio": required_ratio >= 0.75,
            "novel_risk_bonus": _contains_any(response, novel_terms),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "architecture",
            response,
            "Score design clarity, failure-mode coverage, and operational fit.",
            ground_truth,
        )


class OrchestratingScorer:
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        routes = ground_truth.get("expected_routes", [])
        if not routes:
            # Vacuous pass — matches the empty-set convention every other
            # ratio scorer uses (CodeReview / Mcp / Harness / Summarization).
            # Caught by the challenge-round pilot on PR #1376: this used to
            # silently mark every model as failed when a fixture shipped
            # without expected_routes.
            routing_ratio = 1.0
        else:
            hits = 0
            for route in routes:
                aliases = [route["subtask"], *route.get("aliases", [])]
                if _contains_any(response, aliases) and _contains_all(
                    response,
                    [route["model_class"], route["lane"]],
                ):
                    hits += 1
            routing_ratio = hits / len(routes)
        return {
            "routing_accuracy": routing_ratio >= 0.75,
            "cost_awareness": _contains_any(
                response,
                [
                    "cost",
                    "cheap",
                    "budget",
                    "spend",
                    "expensive",
                    "price",
                    "weekly cap",
                ],
            ),
            "decision_card_discipline": _contains_any(
                response,
                [
                    "decision card",
                    "disagreement",
                    "tradeoff",
                    "trade-off",
                    "option a",
                    "option b",
                    "ab discuss",
                    "deliberat",
                ],
            ),
            "same_family_serialized": _contains_any(
                response,
                [
                    "serialize",
                    "same-family",
                    "same family",
                    "sequential",
                    "in-order",
                    "one at a time",
                    "one lane",
                    "single inflight",
                    "max 1 inflight",
                ],
            ),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "orchestration",
            response,
            "Score plan coherence, parallelization discipline, and routing judgment.",
            ground_truth,
        )


class DebuggingScorer:
    """Debugging-lane scoring with ratio gates instead of binary OR.

    The v1 design used ``_contains_any`` on ``fix_terms`` and
    ``root_cause_terms`` — a binary OR that fires on ANY single keyword hit.
    A model that paraphrases ("zone mismatch" vs "topology mismatch") all-fails
    even when the diagnosis is correct; one incidental keyword all-passes.
    The ``broad_rewrite_terms`` gate had the same problem inverted: one
    incidental mention of "delete the PVC" flipped ``minimal_patch`` to False.

    v1.3 replaces all three binary gates with ratio gates (#1441 phase 1.3),
    mirroring the ContentReviewScorer pattern from PR #1443:

      - ``patch_targets_bug``: fraction of ``fix_terms`` hit (pass @
        ≥ PATCH_TERM_RECALL_THRESHOLD = 0.5).
      - ``root_cause_identified``: fraction of ``root_cause_terms`` hit (pass
        @ ≥ ROOT_CAUSE_RECALL_THRESHOLD = 0.5).
      - ``minimal_patch``: fraction of ``broad_rewrite_terms`` must be LOW
        (pass @ ≤ BROAD_REWRITE_THRESHOLD = 0.25 — at most 1-in-4 broad-patch
        signals present).

    Each term entry can be a flat string or a dict with an ``aliases`` list;
    ``_term_present`` handles both shapes.  ``tests_pass`` stays deterministic
    from ``_run_optional_command``.  ``llm_judge_prompt`` returns ``None`` —
    debugging is a mechanical lane; ratio recall IS truth per #1441.
    """

    PATCH_TERM_RECALL_THRESHOLD = 0.5
    ROOT_CAUSE_RECALL_THRESHOLD = 0.5
    BROAD_REWRITE_THRESHOLD = 0.25

    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        fix_terms = list(ground_truth.get("fix_terms", []))
        if not fix_terms:
            patch_ratio = 1.0
        else:
            found = sum(1 for t in fix_terms if _term_present(response, t))
            patch_ratio = found / len(fix_terms)

        root_terms = list(ground_truth.get("root_cause_terms", []))
        if not root_terms:
            root_ratio = 1.0
        else:
            found = sum(1 for t in root_terms if _term_present(response, t))
            root_ratio = found / len(root_terms)

        broad_terms = list(ground_truth.get("broad_rewrite_terms", []))
        if not broad_terms:
            broad_ratio = 0.0
        else:
            found = sum(1 for t in broad_terms if _term_present(response, t))
            broad_ratio = found / len(broad_terms)

        test_result = _run_optional_command(ground_truth.get("pytest_command"))
        return {
            "root_cause_identified": root_ratio >= self.ROOT_CAUSE_RECALL_THRESHOLD,
            "patch_targets_bug": patch_ratio >= self.PATCH_TERM_RECALL_THRESHOLD,
            "tests_pass": test_result,
            "minimal_patch": broad_ratio <= self.BROAD_REWRITE_THRESHOLD,
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return None


class RefactoringScorer:
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        original_loc = int(ground_truth.get("original_loc", 200))
        response_loc = len(_extract_fenced_code(response).splitlines())
        tests_pass = _run_optional_command(ground_truth.get("test_command"))
        lint_clean = _run_optional_command(ground_truth.get("lint_command"))
        behavior_aliases = list(ground_truth.get("behavior_aliases", []))
        return {
            "tests_still_pass": tests_pass,
            "loc_reduction": response_loc < original_loc,
            "lint_clean": lint_clean,
            "behavior_preserved": _contains_any(
                response,
                list(ground_truth.get("behavior_terms", []))
                + behavior_aliases,
            ),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "refactoring",
            response,
            (
                "Score whether the refactor preserves the requested behavior, "
                "reduces complexity, and remains testable."
            ),
            ground_truth,
        )


class SummarizationScorer:
    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        must_mentions = list(ground_truth.get("must_mentions", []))
        banned = list(ground_truth.get("banned_hallucinations", []))
        # Instruction-following for a fixture whose own prompt says "Stay
        # within 180-220 words" (both tails); not a curriculum length quota.
        min_words = int(ground_truth.get("min_words", 180))
        max_words = int(ground_truth.get("max_words", 220))
        words = _word_count(response)
        must_mentions_lower = [mention.lower() for mention in must_mentions]
        response_lower = response.lower()
        must_mention_ratio = (
            sum(1 for term in must_mentions_lower if term in response_lower) / len(must_mentions)
            if must_mentions
            else 1.0
        )
        return {
            # Require at least 75% of required points to balance model paraphrase drift.
            "must_mention_recall": must_mention_ratio >= 0.75,
            "length_compliance": min_words <= words <= max_words,
            "no_hallucination": not _contains_any(response, banned),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "summary coherence",
            response,
            "Score whether the handoff is coherent, useful, and faithful.",
            ground_truth,
        )


class McpUseScorer:
    """Score tool-use plans against an expected tool-call list.

    The model is asked to plan (not execute) a sequence of MCP tool calls. The
    deterministic side checks:
      - whether each expected tool name appears at least once;
      - whether each expected parameter signal (e.g., a source URL, a flag,
        a CLI name) appears;
      - whether forbidden / hallucinated tools are absent.
    The judge then scores plan coherence and selection-rationale quality.
    """

    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        expected_tools = list(ground_truth.get("expected_tools", []))
        required_params = list(ground_truth.get("required_param_signals", []))
        forbidden_tools = list(ground_truth.get("forbidden_tools", []))

        tool_hits = sum(
            1
            for tool in expected_tools
            if _contains_any(response, [tool["name"], *tool.get("aliases", [])])
        )
        tool_ratio = tool_hits / len(expected_tools) if expected_tools else 1.0

        param_hits = sum(
            1
            for param in required_params
            if _contains_any(response, [param])
        )
        param_ratio = param_hits / len(required_params) if required_params else 1.0

        return {
            "tool_selection_recall": tool_ratio >= 0.75,
            "parameter_grounding": param_ratio >= 0.6,
            "no_phantom_tools": not _contains_any(response, forbidden_tools),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "MCP tool-use plan",
            response,
            (
                "Score whether the plan picks the right MCP tools, calls them "
                "in the right order, and supplies the parameters that the "
                "task actually needs. Penalize phantom tools and overly broad "
                "single-call answers when the task needs a multi-step plan."
            ),
            ground_truth,
        )


class HarnessFollowingScorer:
    """Score whether a model recognizes + obeys project rules.

    The fixture frames a request that violates one or more KubeDojo CLAUDE.md
    or memory-file rules. The model passes when it explicitly refuses or
    redirects, naming the rule it is honoring. The model fails when it
    silently complies with the rule-violating ask.
    """

    def deterministic_gates(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> dict[str, bool]:
        required_rules = list(ground_truth.get("required_rule_citations", []))
        rule_hits = sum(
            1
            for rule in required_rules
            if _contains_any(response, [rule["name"], *rule.get("aliases", [])])
        )
        rule_ratio = rule_hits / len(required_rules) if required_rules else 1.0

        required_actions = list(ground_truth.get("required_action_signals", []))
        action_hits = sum(
            1
            for action in required_actions
            if _contains_any(response, [action])
        )
        action_ratio = (
            action_hits / len(required_actions) if required_actions else 1.0
        )

        forbidden = list(ground_truth.get("forbidden_compliance_signals", []))
        return {
            "rule_recall": rule_ratio >= 0.5,
            "redirect_action": action_ratio >= 0.5,
            "no_silent_compliance": not _contains_any(response, forbidden),
        }

    def llm_judge_prompt(
        self,
        response: str,
        ground_truth: dict[str, Any],
    ) -> str | None:
        return _judge_prompt(
            "harness-following",
            response,
            (
                "Score whether the response actually honors the project rules "
                "named in the rubric, names the rule by id or short label, "
                "and proposes a concrete redirect (dispatch / PR / decision "
                "card / refuse). Penalize bare refusals with no plan and "
                "responses that comply with the rule-violating ask."
            ),
            ground_truth,
        )


SCORERS: dict[str, LaneScorer] = {
    "code-writing": CodeWritingScorer(),
    "code-review": CodeReviewScorer(),
    "content-writing-long": ContentWritingLongScorer(),
    "content-review": ContentReviewScorer(),
    "fact-check": FactCheckScorer(),
    "architecting": ArchitectingScorer(),
    "orchestrating": OrchestratingScorer(),
    "debugging": DebuggingScorer(),
    "refactoring": RefactoringScorer(),
    "summarization": SummarizationScorer(),
    "mcp-use": McpUseScorer(),
    "harness-following": HarnessFollowingScorer(),
}


def _assert_lane_set_consistency() -> None:
    """Catch the 'added a lane to LANES but forgot SCORERS' regression.

    Run at module load so any drift fails fast — before any cell dispatches.
    run_wave.LANE_FIXTURES is checked from the other module (plus fixture file
    resolution) to avoid a circular import; see ``scripts/calibration/run_wave.py``.
    """
    from .models import LANES as _LANES

    lanes_in_models: set[str] = {str(lane) for lane in _LANES}
    lanes_in_scorers: set[str] = set(SCORERS)
    if lanes_in_models != lanes_in_scorers:
        missing_in_scorers = lanes_in_models - lanes_in_scorers
        missing_in_models = lanes_in_scorers - lanes_in_models
        raise RuntimeError(
            "calibration lane drift: "
            f"LANES \\ SCORERS = {sorted(missing_in_scorers)}; "
            f"SCORERS \\ LANES = {sorted(missing_in_models)}"
        )


_assert_lane_set_consistency()


def _parse_json_response(response: str) -> list[dict[str, Any]]:
    def _to_list(parsed: Any) -> list[dict[str, Any]]:
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
            return [item for item in parsed["claims"] if isinstance(item, dict)]
        return []

    # 1. Direct JSON parse.
    try:
        return _to_list(json.loads(response))
    except json.JSONDecodeError:
        pass

    # 2. Fenced ```json ... ``` block.
    match = re.search(r"```(?:json)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return _to_list(json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass

    # 3. Balanced bracket scan — handles prose-prefixed JSON (qwen3.6, grok-4.3,
    #    dsv4-flash all emit a sentence before the JSON array). Tracks `[`/`]` depth
    #    only; nested `{}` inside the array do not affect the counter.
    depth = 0
    start = -1
    candidates = 0
    for i, ch in enumerate(response):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start != -1:
                candidates += 1
                try:
                    return _to_list(json.loads(response[start : i + 1]))
                except json.JSONDecodeError:
                    pass
                if candidates >= 50:
                    break
                start = -1

    return []


def _run_optional_command(command: object) -> bool:
    if not command:
        return True
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        return False
    result = run_command(command, cwd=REPO_ROOT, timeout_s=120)
    return result.returncode == 0


def _verifier_tier(response: str) -> str:
    """Return verify_module.py tier when response looks like a module.

    Short unit-test snippets and malformed model outputs fall back to an
    explicit ``T0``/``T1`` marker search so the scorer still records a gate
    rather than crashing before the ledger write.
    """
    if response.lstrip().startswith("---"):
        with tempfile.TemporaryDirectory(prefix="calibration-module-") as tmp:
            module_path = Path(tmp) / "module.md"
            module_path.write_text(response, encoding="utf-8")
            result = run_command(
                [
                    ".venv/bin/python",
                    "scripts/quality/verify_module.py",
                    str(module_path),
                    "--skip-source-check",
                    "--tier-only",
                ],
                cwd=REPO_ROOT,
                timeout_s=120,
            )
        if result.returncode == 0:
            match = re.search(r"\bT[0-4]\b", result.stdout)
            if match:
                return match.group(0)
    tier_match = re.search(r"\bT([0-4])\b", response)
    return f"T{tier_match.group(1)}" if tier_match else ""


def _judge_prompt(
    dimension: str,
    response: str,
    instruction: str,
    ground_truth: dict[str, Any],
) -> str:
    rubric = ground_truth.get("llm_rubric", "Return JSON: {\"score\": 0-10, \"rationale\": \"...\"}.")
    return (
        f"You are a calibration judge for {dimension}.\n\n"
        f"{instruction}\n\n"
        f"Rubric:\n{rubric}\n\n"
        f"Model response:\n{response}\n"
    )


def load_ground_truth(lane: str, fixture_id: str) -> dict[str, Any]:
    path = GROUND_TRUTH_ROOT / lane / f"{fixture_id}.yaml"
    if not path.exists():
        legacy_path = GROUND_TRUTH_ROOT / lane / f"{fixture_id}.legacy.yaml"
        if legacy_path.exists():
            path = legacy_path
    if not path.exists():
        raise FileNotFoundError(f"missing calibration ground truth: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"ground truth must be a mapping: {path}")
    return payload


def _latest_dispatch(conn: Any, cell_id: str) -> Any:
    row = conn.execute(
        """
        SELECT *
        FROM dispatches
        WHERE cell_id = ?
        ORDER BY dispatch_ts DESC
        LIMIT 1
        """,
        (cell_id,),
    ).fetchone()
    if row is None:
        raise FileNotFoundError(f"no dispatch response recorded for {cell_id}")
    return row


def _response_path_from_dispatch(dispatch: Any) -> Path:
    path = Path(dispatch["response_path"])
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _latest_response_path(conn: Any, cell_id: str) -> Path:
    return _response_path_from_dispatch(_latest_dispatch(conn, cell_id))


class JudgeParseError(ValueError):
    """Raised when a judge response is not valid score JSON."""


def _parse_judge_score(response: str) -> float:
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as exc:
        match = re.search(r"```(?:json)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
        if not match:
            raise JudgeParseError(
                f"judge response does not contain JSON: {response[:120]}"
            ) from exc
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError as fenced_exc:
            raise JudgeParseError(
                f"judge fenced JSON is malformed: {response[:120]}"
            ) from fenced_exc
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        parsed = parsed[0]
    if not isinstance(parsed, dict) or "score" not in parsed:
        raise JudgeParseError(f"judge JSON missing score field: {response[:120]}")
    try:
        score = float(parsed["score"])
    except (TypeError, ValueError) as exc:
        raise JudgeParseError(f"judge score is not numeric: {response[:120]}") from exc
    if not 0.0 <= score <= 10.0:
        raise JudgeParseError(f"judge score outside 0..10: {score}")
    return score


JudgeRawResult = str | DispatchResult
JudgeFn = Callable[[str, str], JudgeRawResult]

# Per-lane judge dispatch ceilings. A hanging judge stalls the family thread
# in run_wave for this long, so keep the ceilings tight. Numbers are derived
# from the Wave A/B observed p95 latency (sonnet judge ~25s; gemini judge ~40s
# pre-collapse). 1800s was the v1 default and was too loose — one collapse
# blocked 24 cells for 30 minutes.
JUDGE_TIMEOUTS_S: dict[str, int] = {
    "mcp-use": 90,
    "harness-following": 90,
    "summarization": 120,
    "orchestrating": 180,
    "architecting": 180,
    "content-writing-long": 180,
    "refactoring": 180,
    "content-review": 180,
    "fact-check": 120,
}
DEFAULT_JUDGE_TIMEOUT_S = 180


def dispatch_judge(
    judge_model: str,
    prompt: str,
    timeout_s: int = DEFAULT_JUDGE_TIMEOUT_S,
) -> DispatchResult:
    model = model_by_canonical(judge_model)
    return dispatch_prompt(model, prompt, REPO_ROOT, timeout_s)


def _judge_accepts_timeout(judge_fn: JudgeFn) -> bool:
    """True if the callable's signature has a ``timeout_s`` keyword.

    Test mocks use a 2-arg ``(model, prompt)`` callable. The real judge has a
    3rd ``timeout_s`` kwarg with a default. We probe rather than widen the
    public ``JudgeFn`` type so calibration tests don't need to grow.
    """
    import inspect
    try:
        sig = inspect.signature(judge_fn)
    except (TypeError, ValueError):
        return False
    return "timeout_s" in sig.parameters


def score_cell(
    *,
    cell_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    judge1: str = "claude-sonnet-4-6",
    judge2: str = "gemini-3.5-flash-high",
    judge_fn: JudgeFn = dispatch_judge,
    replicate_seq: int = 0,
) -> dict[str, bool]:
    if replicate_seq < 0:
        raise ValueError("replicate_seq must be >= 0")
    judge_models = (judge1, judge2)
    schema.init_db(db_path)
    with schema.connect(db_path) as conn:
        cell = schema.fetch_cell(conn, cell_id)
        dispatch = _latest_dispatch(conn, cell_id)
        response_path = _response_path_from_dispatch(dispatch)
        response = response_path.read_text(encoding="utf-8")
        ground_truth = load_ground_truth(str(cell["lane"]), str(cell["fixture_id"]))
        lane = str(cell["lane"])
        scorer = SCORERS[lane]
        gates = scorer.deterministic_gates(response, ground_truth)
        schema.insert_scores(
            conn,
            cell_id=cell_id,
            gates=gates,
            replicate_seq=replicate_seq,
        )
        if lane == "content-writing-long":
            inline_result = respected_inline_return.score_dispatch(
                dispatch,
                repo_root=REPO_ROOT,
            )
            schema.insert_score(
                conn,
                cell_id=cell_id,
                gate_name=respected_inline_return.GATE_NAME,
                gate_pass=inline_result.gate_pass,
                score_value=inline_result.score_value,
                scorer=respected_inline_return.GATE_NAME,
                stderr_excerpt=inline_result.stderr_excerpt,
                replicate_seq=replicate_seq,
            )

        prompt = scorer.llm_judge_prompt(response, ground_truth)
        if prompt is None:
            return gates

        if lane not in PROSE_LANES and not all(gates.values()):
            # Mechanical lanes keep deterministic-gate-as-gate behavior.
            for model_name in judge_models:
                schema.insert_score(
                    conn,
                    cell_id=cell_id,
                    gate_name="llm_judge_score",
                    gate_pass=False,
                    score_value=None,
                    scorer=f"llm-judge:{model_name}",
                    gate_failure_reason="scorer_skipped_by_two_stage_rule",
                    replicate_seq=replicate_seq,
                )
            return gates

    # Judges run outside the DB transaction so they can fan out in parallel
    # without blocking on a single sqlite connection. Each call is an
    # independent CLI dispatch to a different family (claude + gemini), so
    # there is no contention between them.
    judge_timeout_s = JUDGE_TIMEOUTS_S.get(lane, DEFAULT_JUDGE_TIMEOUT_S)

    def _run_one_judge(
        model_name: str,
    ) -> tuple[str, float | None, str, str | None]:
        try:
            # Real judges accept timeout_s; mocked judges in tests don't.
            # Pass it via inspect so tests don't have to grow a signature.
            raw_result = (
                judge_fn(model_name, prompt, timeout_s=judge_timeout_s)  # type: ignore[call-arg]
                if _judge_accepts_timeout(judge_fn)
                else judge_fn(model_name, prompt)
            )
        except Exception as exc:  # noqa: BLE001 — judge crash ≠ cell crash
            return model_name, None, "scorer_crashed", repr(exc)
        if isinstance(raw_result, DispatchResult):
            if raw_result.returncode not in (None, 0):
                return (
                    model_name,
                    None,
                    "scorer_crashed",
                    raw_result.stderr_excerpt or f"returncode={raw_result.returncode}",
                )
            judge_response = raw_result.response
            stderr_excerpt = raw_result.stderr_excerpt
        else:
            judge_response = raw_result
            stderr_excerpt = None
        try:
            judge_score = _parse_judge_score(judge_response)
        except JudgeParseError as exc:
            return model_name, None, "scorer_unparseable_output", str(exc)
        normalized_score = judge_score / 10.0
        reason = (
            "gate_passed"
            if normalized_score >= 0.5
            else "gate_failed_legitimately"
        )
        return model_name, judge_score, reason, stderr_excerpt

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(judge_models)) as pool:
        judge_outcomes = list(pool.map(_run_one_judge, judge_models))

    judge_scores: list[float] = []
    with schema.connect(db_path) as conn:
        for model_name, judge_score, reason, stderr_excerpt in judge_outcomes:
            if judge_score is not None:
                judge_scores.append(judge_score)
            schema.insert_score(
                conn,
                cell_id=cell_id,
                gate_name="llm_judge_score",
                gate_pass=judge_score is not None and judge_score >= 7.0,
                score_value=judge_score,
                scorer=f"llm-judge:{model_name}",
                stderr_excerpt=stderr_excerpt,
                gate_failure_reason=reason,
                replicate_seq=replicate_seq,
            )
        if len(judge_scores) == 2 and abs(judge_scores[0] - judge_scores[1]) > 1.0:
            schema.insert_score(
                conn,
                cell_id=cell_id,
                gate_name="human_spot_check",
                gate_pass=False,
                score_value=abs(judge_scores[0] - judge_scores[1]),
                scorer="deterministic",
                replicate_seq=replicate_seq,
            )
    return gates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score one calibration cell")
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--judge1", default="claude-sonnet-4-6")
    parser.add_argument("--judge2", default="gemini-3.5-flash-high")
    parser.add_argument("--replicate-seq", type=int, default=0)
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Skip rendering calibration HTML reports after scoring.",
    )
    return parser


def _cell_run_date(db_path: Path, cell_id: str) -> str:
    with schema.connect(db_path) as conn:
        return str(schema.fetch_cell(conn, cell_id)["run_date"])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gates = score_cell(
        cell_id=args.cell_id,
        db_path=args.db_path,
        judge1=args.judge1,
        judge2=args.judge2,
        replicate_seq=args.replicate_seq,
    )
    print(json.dumps(gates, sort_keys=True))
    if not args.no_render:
        from . import report

        run_date = _cell_run_date(args.db_path, args.cell_id)
        out_dir = report.report_dir_for_run(run_date, output_root=args.output_root)
        print(f"rendering calibration reports to {out_dir}", file=sys.stderr)
        written = report.render_reports(
            db_path=args.db_path,
            out_dir=out_dir,
            run_date=run_date,
        )
        print(
            f"rendered calibration reports: {len(written)} file(s)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
