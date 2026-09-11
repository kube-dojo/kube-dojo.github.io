---
title: "RAG Evaluation & Optimization"
slug: ai-ml-engineering/vector-rag/module-1.4-rag-evaluation-optimization
sidebar:
  order: 405
---

> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 4-5 hours
>
> **Prerequisites**: RAG architecture from modules 1.2–1.3, Python, labeled evaluation datasets, and basic information-retrieval metrics (recall, precision, ranking).

## What You'll Be Able to Do

By the end of this module, you will be able to evaluate and improve Retrieval-Augmented Generation systems with the same discipline you would apply to search, reliability, and production software changes. These outcomes focus on measurement, diagnosis, and controlled iteration rather than on adding more retrieval patterns by instinct.

- **Choose and compute** retrieval metrics such as recall@k, precision@k, hit-rate, MRR, and nDCG for a labeled RAG evaluation set.
- **Evaluate** generated answers with faithfulness, groundedness, answer relevance, context precision, and context recall checks.
- **Build** golden and synthetic evaluation sets that separate offline regression testing from online production monitoring.
- **Apply** LLM-as-judge methods with rubrics, calibration, pairwise comparisons, multiple judges, and bias controls.
- **Gate** RAG changes in CI by running the measure -> diagnose -> tune -> re-measure loop against stable thresholds.

## Why This Module Matters

Hypothetical scenario: a product team builds a support assistant over a private knowledge base. The first demo is excellent because the sample questions were chosen from recently indexed documents, the answers are short, and the team already knows which source pages should be retrieved. After launch, the corpus changes, old documents remain in the index, a prompt edit weakens citation discipline, and a new embedding model slightly shifts the ranking. The assistant still sounds confident, so the regression is not obvious until users start escalating tickets that the demo never covered.

That kind of failure is not unusual because RAG systems are compound systems. Retrieval can miss the right evidence. Ranking can bury the right evidence below weaker chunks. The generator can ignore relevant context, overuse irrelevant context, or cite a source that does not support the answer. Long prompts can hide the key passage in the middle. A cost optimization can lower `k` and silently hurt rare query classes. A prompt that improves one product line can make another product line worse. Without measurement, every "optimization" is mostly a story.

Reliable RAG teams treat evaluation as a continuous discipline, not as a one-time launch review. They keep a golden set of questions, expected answers, expected source documents, and known failure classes. They run offline evaluations before deployment, monitor online behavior after deployment, and keep regression gates so a fix for one query does not quietly break another. The best evaluation programs do not worship one score. They combine retrieval metrics, generation metrics, human labels, LLM-assisted judging, latency, cost, and user feedback into a practical engineering loop.

The analogy is an instrumented aircraft cockpit. A pilot does not "feel" altitude, fuel, heading, and engine temperature by confidence alone; the cockpit exposes measurements that make diagnosis possible before a bad decision compounds. A RAG system needs the same cockpit. Retrieval recall tells you whether the right evidence entered the candidate set. Ranking metrics tell you whether it was near the top. Faithfulness checks tell you whether the answer stayed inside the evidence. Latency and cost metrics tell you whether the quality gain can survive production traffic.

This module deliberately does not re-teach the retrieval architecture patterns themselves. For the retrieval patterns themselves, see [Module 1.3: Advanced RAG Patterns](../module-1.3-advanced-rag-patterns/). Here, the question is different: once you have a RAG system, how do you know whether it works, how do you diagnose why it fails, and how do you improve it without losing control of correctness, cost, and latency?

## Evaluation Starts with a Test Collection

RAG evaluation begins before metric formulas. You need a test collection: questions, relevant evidence, expected behavior, and sometimes expected answers. Traditional information retrieval evaluation uses a collection of documents, a set of information needs, and relevance judgments. RAG adds a generation layer, but the foundation is the same. If you do not know which chunks or documents should be considered relevant for a query, recall and ranking metrics become guesses instead of measurements.

A practical RAG evaluation record usually has five fields. The `question` is the user-facing input. The `relevant_doc_ids` field identifies the source chunks or parent documents that should be retrieved. The `reference_answer` captures the answer a well-grounded assistant should produce, preferably written or reviewed by a domain expert. The `must_cite` field records evidence that must appear in citations or support checks. The `tags` field labels failure classes such as exact identifier lookup, policy conflict, multi-document synthesis, freshness, long-context placement, or out-of-scope abstention.

The tags matter because a single average score can hide the most important failures. A retrieval system can score well on common conceptual questions while failing exact part numbers, error codes, or legal citations. A generator can appear faithful on short answers while failing conflict-resolution questions where two documents disagree. Segmenting the eval set by query class lets you see whether a change improves the easy majority while harming the rare but costly minority.

Golden datasets are slow to build because someone has to decide what "right" means. That labor is still cheaper than debugging production by anecdote. Start with real query logs after removing private or sensitive data. Add known support escalations, questions from subject-matter experts, policy-edge cases, and examples where the current system fails. Keep the first set small enough that humans can audit it carefully. A 100-question set with clean labels is usually more useful than a 5,000-question set with ambiguous relevance judgments.

Synthetic eval generation can help expand coverage, but it should not replace human review. A common workflow is to sample source documents, ask a model to propose questions that require those documents, ask another pass to identify the supporting passages, and then have a human accept, reject, or edit the cases. Synthetic questions are valuable for broad coverage and regression stress tests. They are risky when treated as ground truth because the generator may write questions that are too easy, too artificial, or accidentally answerable from the wrong source.

Offline evaluation runs before deployment against a frozen corpus, a frozen pipeline configuration, and a stable eval set. It answers questions such as "does this embedding model improve recall on our policy corpus?" or "does this reranker improve top-three citation quality without unacceptable latency?" Online evaluation runs in production through logs, sampled human review, user feedback, A/B experiments, and drift monitoring. It answers questions such as "are real users asking new question types?" and "did yesterday's document ingestion change answer behavior?"

Regression testing connects both worlds. Every serious RAG change should run against a stable eval set and report metric deltas by tag. If a chunking change improves broad conceptual recall but breaks exact identifier queries, the CI report should make that visible before the branch ships. If a prompt change improves answer tone but increases unsupported claims, the generation gate should fail. Evaluation is not a trophy score; it is a guardrail for controlled change.

## Retrieval Metrics: Did the Right Evidence Arrive?

Retrieval metrics evaluate the context selection stage before the LLM writes anything. This separation is essential because an answer can fail for different reasons. If the right evidence never entered the context window, the generator cannot reliably produce a grounded answer. If the right evidence was retrieved but ranked too low, the generator may miss it or the prompt may truncate it. If the right evidence was present and prominent, the failure likely belongs to generation, instruction following, citation discipline, or long-context use.

`recall@k` asks what fraction of the relevant documents appeared in the top `k` retrieved results. It is the most important first-pass metric when missing evidence is expensive. If a user asks about a policy that has three relevant clauses and only one appears in the top five, recall@5 is one third. High recall does not mean the context is clean; it means the needed evidence has a chance to reach the generator.

`precision@k` asks what fraction of the top `k` retrieved results are relevant. It matters when context budget is tight or irrelevant context creates hallucination risk. A retriever that returns one correct chunk and nine distracting chunks may have acceptable hit-rate but poor precision@10. That can hurt generation because the model must decide which evidence to trust under token pressure.

`hit-rate@k` asks whether at least one relevant document appeared in the top `k`. It is useful for dashboards because it is easy to interpret: did the retriever surface any usable evidence? It is less informative than recall when a query needs multiple sources. A multi-policy synthesis question can have hit-rate@5 equal to 1 while still missing the clause that changes the answer.

`MRR`, or mean reciprocal rank, rewards systems that place the first relevant document early. For each query, find the rank of the first relevant result and take `1 / rank`. A query whose first relevant result is rank 1 gets 1.0; rank 4 gets 0.25; no relevant result gets 0.0. MRR is useful for assistants that usually need one decisive source, such as "what is the refund deadline?" or "where is this error documented?"

`nDCG`, or normalized discounted cumulative gain, handles graded relevance and ranking position. It is useful when some documents are fully relevant, some are partially relevant, and some are only background. The metric discounts lower-ranked results because evidence at rank 8 is less likely to be used than evidence at rank 1. Normalization compares your ranking to the ideal ranking for that query, so scores land on a 0 to 1 scale.

The following code computes the core retrieval metrics against labeled eval cases. It uses document identifiers, not raw text, because real evaluation should compare stable source IDs instead of brittle string snippets. The `relevance_grades` map is optional for nDCG; use binary relevance when your labels only know "relevant" and "not relevant."

```python
from __future__ import annotations

from dataclasses import dataclass
from math import log2


@dataclass(frozen=True)
class RetrievalCase:
    question: str
    retrieved_doc_ids: list[str]
    relevant_doc_ids: set[str]
    relevance_grades: dict[str, int]


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return sum(1 for doc_id in top_k if doc_id in relevant) / len(top_k)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    top_k = retrieved[:k]
    return sum(1 for doc_id in top_k if doc_id in relevant) / len(relevant)


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    return 1.0 if any(doc_id in relevant for doc_id in top_k) else 0.0


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for index, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / index
    return 0.0


def dcg_at_k(ranking: list[str], relevance_grades: dict[str, int], k: int) -> float:
    score = 0.0
    for index, doc_id in enumerate(ranking[:k], start=1):
        grade = relevance_grades.get(doc_id, 0)
        score += (2**grade - 1) / log2(index + 1)
    return score


def ndcg_at_k(retrieved: list[str], relevance_grades: dict[str, int], k: int) -> float:
    ideal = sorted(relevance_grades, key=lambda doc_id: relevance_grades[doc_id], reverse=True)
    ideal_score = dcg_at_k(ideal, relevance_grades, k)
    if ideal_score == 0.0:
        return 0.0
    return dcg_at_k(retrieved, relevance_grades, k) / ideal_score


def summarize_retrieval(cases: list[RetrievalCase], k: int = 5) -> dict[str, float]:
    totals = {
        "precision_at_k": 0.0,
        "recall_at_k": 0.0,
        "hit_rate_at_k": 0.0,
        "mrr": 0.0,
        "ndcg_at_k": 0.0,
    }
    for case in cases:
        totals["precision_at_k"] += precision_at_k(case.retrieved_doc_ids, case.relevant_doc_ids, k)
        totals["recall_at_k"] += recall_at_k(case.retrieved_doc_ids, case.relevant_doc_ids, k)
        totals["hit_rate_at_k"] += hit_rate_at_k(case.retrieved_doc_ids, case.relevant_doc_ids, k)
        totals["mrr"] += reciprocal_rank(case.retrieved_doc_ids, case.relevant_doc_ids)
        totals["ndcg_at_k"] += ndcg_at_k(case.retrieved_doc_ids, case.relevance_grades, k)
    return {name: value / len(cases) for name, value in totals.items()}
```

The right metric depends on the product question. For a developer assistant where one exact runbook page is usually enough, MRR and hit-rate@3 may be the primary signals. For a compliance assistant that must collect every relevant clause, recall@10 and context recall matter more. For a research assistant where some evidence is central and some is background, nDCG captures ranking quality better than binary precision. Metric choice should match user harm, not what the library prints by default.

## Generation Metrics: Did the Answer Stay Grounded?

Generation evaluation asks whether the final answer is useful, relevant, and supported by the retrieved context. RAGAS-style evaluation popularized a helpful decomposition: evaluate the retrieved context, evaluate the answer, and evaluate the relationship between the two. The exact tooling changes quickly, but the conceptual components are durable. You want to know whether the answer is faithful to the context, whether it answers the user question, whether the context was precise, and whether the context covered the needed evidence.

Faithfulness, often called groundedness, asks whether claims in the answer are supported by the retrieved context. This catches the classic RAG failure where the retriever found useful documents but the model added unsupported facts, overgeneralized a policy, or invented a condition that was not present. Faithfulness does not require the answer to be complete. It only asks whether the claims that appear are backed by evidence.

Answer relevance asks whether the answer addresses the user's question. A response can be faithful to the context and still fail relevance by summarizing the wrong section, refusing unnecessarily, or answering a nearby question. This matters when the retriever returns broadly related documents and the generator produces a generic answer that sounds plausible but does not resolve the user's actual intent.

Context precision asks how much of the retrieved context is useful for the question. Low context precision means the prompt is padded with distractors. Distractors increase token cost and can create contradictions, especially when the corpus contains stale documents or similar policies for different products. Context precision is a retrieval quality metric expressed from the generator's perspective: did we feed the model focused evidence?

Context recall asks whether the retrieved context contains enough information to answer the question. A system can have high context precision but low context recall if it retrieves one perfectly relevant clause while missing the second clause needed to answer safely. Context recall is especially important for synthesis questions, policy exceptions, multi-document workflows, and any case where abstention is better than a partially grounded answer.

Reference answer similarity can be useful, but it should not dominate RAG evaluation. Many valid answers use different wording from the reference. A concise answer with correct citations may be better than a verbose answer that copies the reference. When you use reference answers, judge semantics and required facts rather than exact phrasing. For regulated or safety-sensitive domains, prefer explicit required facts and prohibited claims over fuzzy similarity alone.

The following code sketches a RAGAS-style faithfulness check. It extracts atomic claims from the answer, asks a judge whether each claim is supported by the retrieved contexts, and returns a score plus unsupported claims. In production, you would calibrate the judge against human labels, pin the model version, log prompts and verdicts, and treat the result as one signal rather than as a proof of truth.

```python
from __future__ import annotations

import json
from typing import Protocol


class JudgeModel(Protocol):
    def complete(self, prompt: str) -> str:
        """Return a JSON string from a deterministic, low-temperature judge call."""


def faithfulness_prompt(question: str, answer: str, contexts: list[str]) -> str:
    numbered_contexts = "\n\n".join(
        f"Context {index}: {context}" for index, context in enumerate(contexts, start=1)
    )
    return f"""
You are evaluating whether an answer is supported by retrieved context.
Break the answer into atomic factual claims. For each claim, decide whether
the claim is fully supported by the provided context. Do not use outside knowledge.

Question:
{question}

Retrieved context:
{numbered_contexts}

Answer:
{answer}

Return JSON with this schema:
{{
  "claims": [
    {{"claim": "short claim text", "supported": true, "evidence_context_ids": [1]}}
  ]
}}
"""


def score_faithfulness(judge: JudgeModel, question: str, answer: str, contexts: list[str]) -> dict:
    raw = judge.complete(faithfulness_prompt(question, answer, contexts))
    parsed = json.loads(raw)
    claims = parsed.get("claims", [])
    if not claims:
        return {"faithfulness": 0.0, "unsupported_claims": ["judge returned no claims"]}
    supported = [claim for claim in claims if claim.get("supported") is True]
    unsupported = [claim.get("claim", "") for claim in claims if claim.get("supported") is not True]
    return {
        "faithfulness": len(supported) / len(claims),
        "unsupported_claims": unsupported,
        "claim_count": len(claims),
    }
```

Notice what the code does not claim. It does not prove that the context itself is true. It does not prove that the judge is unbiased. It does not guarantee that every claim was extracted perfectly. It simply makes a hidden failure mode visible: the answer contains claims, some claims have evidence, and some do not. That visibility is enough to drive useful engineering decisions when paired with retrieval metrics and human review.

## LLM-as-Judge: Useful Tool, Not an Oracle

LLM-as-judge evaluation uses a model to score or compare model outputs. In RAG, a judge may rate faithfulness, relevance, citation support, abstention quality, or answer completeness. This is attractive because natural-language answers are hard to score with exact-match rules. A judge can read the question, retrieved context, reference answer, and generated answer, then produce a structured verdict. The danger is that the judge is also a model with failure modes.

Position bias appears when a judge prefers the answer shown first or second in a pairwise comparison because of placement rather than quality. Verbosity bias appears when a judge rewards longer answers even when the extra words add no supported information. Self-preference appears when a judge favors outputs from its own model family or style. Non-determinism appears when repeated judge calls return different verdicts because the prompt, sampling, provider behavior, or model version changed. These pitfalls do not make LLM judges useless; they mean judge design must be engineered.

Rubrics are the first defense. Do not ask "is this answer good?" Ask small, observable questions: "Does every factual claim have supporting context?", "Does the answer cite the source IDs it used?", "Does the answer refuse when context is insufficient?", and "Does the answer directly answer the user's question?" Atomic criteria reduce the judge's freedom to reward style over correctness. They also produce actionable failure labels.

Pairwise judging is often more stable than asking for a raw numeric score, but pairwise judging must randomize answer order and record which variant appeared in each slot. If answer A wins only when it appears second, you have detected a judge artifact, not a product improvement. For high-impact gates, run both orders and require the same winner or treat the result as uncertain. This costs more, but it prevents a biased comparison from steering the roadmap.

Multiple judges can improve robustness when their errors are not perfectly correlated. A small panel might combine one large general model, one smaller calibrated evaluator, and deterministic checks for citations and exact identifiers. The value is not magical voting. The value is disagreement. When judges split, send the case to human review or keep the old pipeline until the failure is understood.

Calibration against human labels is mandatory for production confidence. Sample cases, have domain reviewers label them, and compare judge verdicts to those labels. Track false positives, false negatives, disagreement by query tag, and drift over time. A judge that agrees with humans on FAQ questions but fails policy-conflict questions should not gate policy-conflict launches. Keep calibration cases private from prompt-tuning experiments so you do not overfit the judge.

The following harness shows a safer pattern for LLM-assisted judging. It evaluates atomic criteria, randomizes pairwise order, supports multiple judges, and keeps raw records for audit. The code is intentionally framework-neutral; you can implement the `complete` method with your provider, local model, or evaluation framework of choice.

```python
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Protocol


class ChatJudge(Protocol):
    name: str

    def complete(self, prompt: str) -> str:
        """Return JSON with criterion-level pass or fail decisions."""


@dataclass(frozen=True)
class JudgeCase:
    question: str
    contexts: list[str]
    reference_answer: str
    candidate_answer: str


CRITERIA = [
    "Every factual claim in the candidate is supported by the contexts.",
    "The candidate directly answers the user question.",
    "The candidate cites source identifiers when it uses source-specific facts.",
    "The candidate refuses or scopes the answer when the contexts are insufficient.",
]


def rubric_prompt(case: JudgeCase) -> str:
    criteria_text = "\n".join(f"{index}. {criterion}" for index, criterion in enumerate(CRITERIA, start=1))
    contexts = "\n\n".join(f"Source {index}: {text}" for index, text in enumerate(case.contexts, start=1))
    return f"""
Evaluate the candidate answer using only the supplied sources and rubric.

Question:
{case.question}

Sources:
{contexts}

Reference answer for calibration, not for copying:
{case.reference_answer}

Candidate answer:
{case.candidate_answer}

Rubric:
{criteria_text}

Return JSON:
{{
  "criteria": [
    {{"id": 1, "pass": true, "reason": "brief evidence-based reason"}}
  ],
  "overall_pass": true
}}
"""


def judge_single(judge: ChatJudge, case: JudgeCase) -> dict:
    parsed = json.loads(judge.complete(rubric_prompt(case)))
    return {"judge": judge.name, "verdict": parsed}


def pairwise_prompt(question: str, contexts: list[str], answers: list[tuple[str, str]]) -> str:
    sources = "\n\n".join(f"Source {index}: {text}" for index, text in enumerate(contexts, start=1))
    answer_text = "\n\n".join(f"{label}: {answer}" for label, answer in answers)
    return f"""
Choose the better answer for the question using only the sources.
Prefer the answer that is more faithful, more directly relevant, and better cited.
Do not reward extra length unless it adds supported information.

Question:
{question}

Sources:
{sources}

Answers:
{answer_text}

Return JSON: {{"winner": "A", "reason": "brief reason"}}
"""


def judge_pairwise(judge: ChatJudge, question: str, contexts: list[str], first: str, second: str) -> dict:
    answers = [("A", first), ("B", second)]
    random.shuffle(answers)
    raw = judge.complete(pairwise_prompt(question, contexts, answers))
    parsed = json.loads(raw)
    winner_label = parsed["winner"]
    winner_text = dict(answers)[winner_label]
    return {
        "judge": judge.name,
        "slot_order": [label for label, _ in answers],
        "winner_is_first_candidate": winner_text == first,
        "reason": parsed.get("reason", ""),
    }


def panel_vote(judges: list[ChatJudge], case: JudgeCase) -> dict:
    records = [judge_single(judge, case) for judge in judges]
    passes = sum(1 for record in records if record["verdict"].get("overall_pass") is True)
    return {
        "overall_pass": passes >= (len(judges) // 2 + 1),
        "judge_records": records,
    }
```

Dated tooling note, June 2026: RAGAS, TruLens, DeepEval, promptfoo, and similar projects can all be used to express parts of this evaluation workflow, but they should be treated as peer implementation options rather than as a permanent ranking. Pin versions, log judge prompts, keep raw outputs, and keep the conceptual tests portable so a tooling migration does not rewrite your quality standard.

## Building Eval Sets That Catch Real Regressions

A golden eval set is a curated collection of cases whose expected behavior is stable enough to gate changes. It should include normal user questions, adversarial edge cases, abstention cases, stale-document cases, and questions that require exact source attribution. The point is not to cover every future user query. The point is to represent the product promises you are unwilling to break silently.

Good golden cases are concrete. A weak case says "How does authentication work?" and marks a broad wiki page as relevant. A stronger case says "Which environment variable controls token expiration for the staging API?" and marks the exact runbook section plus the current deployment note as relevant. The stronger case tells retrieval what must be found and tells generation what fact must be supported.

Every case should carry source version information. If the policy document changes, the expected answer may need to change too. Keep document IDs, revision hashes, dates, or content checksums where possible. Otherwise, you can accidentally punish the RAG system for answering from an updated source while the eval set still expects an older answer. Evaluation data is production data; it needs ownership, review, and change control.

Synthetic cases are useful for coverage expansion. A controlled synthetic workflow can generate candidate questions from each document section, require the model to cite the exact source span, and then run a filter that rejects questions answerable without that span. Human reviewers can then approve a subset. This is much more reliable than asking a model to invent a whole benchmark with no grounding. The source span is the anchor that keeps the synthetic case tied to the corpus.

Online evaluation should not wait for explicit thumbs-up and thumbs-down feedback. Users rarely provide enough labels for full coverage, and unhappy users often leave silently. Log retrieval results, context IDs, prompt versions, answer citations, latency, token counts, refusal decisions, and user follow-up behavior. Sample production traces for human review, especially after corpus migrations, model changes, ingestion bugs, or unexpected traffic shifts.

Regression testing should preserve known failures even after they are fixed. When a user escalation reveals that the assistant missed an exception clause, add that query to the eval set with the expected source and answer behavior. The next pipeline change should prove it did not reintroduce the failure. This habit turns incidents into durable test cases rather than temporary fixes.

Separate development, validation, and holdout slices. Use the development slice while tuning chunk sizes, retrieval weights, prompts, or thresholds. Use the validation slice to choose a candidate configuration. Keep a small holdout slice for periodic sanity checks and human review. If every threshold is tuned directly against the same cases, the system can overfit the eval set while failing fresh user questions.

## Diagnosing Failures from Metric Signatures

The most useful evaluation report does more than print scores. It turns score patterns into failure hypotheses. A low recall@k across many tags suggests missing documents, broken ingestion, mismatched embedding versions, overly aggressive metadata filters, or chunk boundaries that split evidence away from its meaning. A high recall@50 with low recall@5 suggests the evidence exists but ranking is weak. High retrieval scores with low faithfulness suggests the generator is ignoring or misusing the context. Strong offline scores with poor production feedback suggests the eval set no longer represents live traffic.

Build the report so an engineer can read it like a diagnostic panel. For each eval case, store the retrieved IDs, their ranks, their scores, the expected IDs, the answer, the citations, the prompt version, the retriever version, the corpus version, and the failure tags. Aggregate metrics are useful for release gates, but the per-case trace is what makes debugging possible. Without the trace, a failed threshold only says "quality is down." With the trace, the same failure can say "the new chunker removed the section heading from four policy-exception cases."

A retrieval miss has a distinctive shape. The relevant source ID is absent from top-k and often absent from a much larger candidate pool. Before changing the model, verify that the source exists in the index, the metadata filter permits it, the document version is current, and the query and document embeddings were produced by compatible model versions. Many expensive RAG "quality" projects have started as simple indexing bugs. Evaluation should make those bugs visible quickly.

A chunking failure often appears as partial recall with poor answer quality. The retriever finds a chunk that contains a keyword or entity, but the chunk omits the definition, exception, date, or preceding paragraph that makes the answer safe. In those cases, changing the generator prompt will not reliably fix the problem because the model never receives the missing context. The right experiment is to compare chunk size, overlap, semantic boundaries, parent-section reconstruction, and source metadata while measuring both retrieval precision and answer faithfulness.

A ranking failure appears when the expected source is retrievable but buried. The candidate pool contains the right document at rank 18, while the prompt only includes the top six. This failure is common when semantic similarity rewards broad topical overlap while the actual answer depends on exact identifiers, current dates, or policy authority. The right experiment is to inspect rank movement after lexical weighting, reranking, freshness boosts, or candidate diversification. Always compare the before and after ranking for the same case; otherwise, you cannot tell whether the new layer helped or merely changed the failure.

A generation failure appears when the right sources are present near the top, yet the answer is unsupported, incomplete, or poorly cited. This is where claim-level checks are most valuable. Split the answer into claims, link each claim to a source, and classify unsupported claims by type: invented number, wrong date, overbroad policy, missing exception, unsupported recommendation, or citation mismatch. Each category suggests a different fix. An invented number may need stricter source quoting, while a missing exception may need an answer schema that forces the model to list constraints before conclusions.

An abstention failure deserves its own tag. Some RAG products are safer when they say they do not have enough information. Evaluation should include questions whose correct answer is a refusal, a clarification request, or a scoped answer. If all golden cases are answerable, the assistant can learn to answer everything. In production, that behavior is dangerous because out-of-scope questions are inevitable. Measure false refusals and false answers separately, because improving one can worsen the other.

A citation failure is not always the same as a factual failure. An answer may state the right fact but cite a source that does not support it, or cite a broad index page when the exact policy paragraph was required. In audit-heavy systems, that is still a failure because users and reviewers need provenance. Treat citations as structured outputs, not decorative links. Validate that every citation ID exists in the retrieved context, points to an allowed source, and supports the nearby claim.

A freshness failure appears when an older source outranks a newer authoritative source. These failures are common in corpora with historical documents, release notes, archived policies, or duplicated pages across product versions. The fix may be retrieval metadata, source authority rules, ingestion deletion, or prompt instructions for conflict handling. The eval case should include both old and new sources so the gate verifies the system chooses the current authority rather than succeeding only in a cleaned corpus.

Human review is still part of the diagnostic loop. Use humans where judgment is expensive but important: calibrating judge labels, reviewing ambiguous failures, approving synthetic cases, and adjudicating changes to high-risk thresholds. Do not ask reviewers to read every trace. Give them focused packets: the question, expected source, retrieved sources, generated answer, judge verdict, and the specific disagreement. Good tooling makes human review sharper instead of turning it into manual log archaeology.

Dashboards should separate release gating from operations. A CI report can be strict, deterministic, and tied to a fixed eval set. A production dashboard must handle drift, sampling, privacy, and changing traffic. It should show query volume by tag, retrieval miss rate, citation failure rate, refusal rate, latency percentiles, token cost, and representative failed traces. If online data reveals a new query class, add reviewed examples to the offline eval set. That feedback loop keeps the benchmark alive.

Finally, write evaluation findings in the same language as engineering tickets. "Faithfulness dropped three points" is less actionable than "policy-conflict cases now cite the archived handbook instead of the approved handbook." The metric is the smoke alarm, not the repair plan. A strong RAG evaluation culture translates numbers into failure labels, failure labels into targeted experiments, and experiments into regression tests that stay in the suite after the immediate incident is gone.

## The Optimization Loop: Measure, Diagnose, Tune, Re-measure

Optimization starts after measurement, not before. The loop is simple: measure the current system, diagnose the failure layer, tune the smallest appropriate knob, and re-measure the same cases. The discipline is resisting the urge to change retrieval, ranking, prompt, and model all at once. Compound changes can improve the headline score while making the root cause invisible.

A retrieval miss means the relevant document never entered the candidate set. Check indexing first. The document might be absent, stale, filtered by metadata, embedded with the wrong model version, or split so badly that the relevant phrase no longer has enough context. Good first knobs are ingestion freshness, metadata filters, chunk boundaries, chunk overlap, embedding model choice, and retrieval `k`. If recall@50 is low, reranking cannot fix the problem because the evidence never reached the reranker.

A ranking or reranking miss means the relevant document was retrieved somewhere but not placed high enough. If recall@50 is good and recall@5 is poor, tune ranking. Good knobs include retrieval score normalization, hybrid lexical-semantic weighting, candidate diversity, reranker choice, reranker candidate count, and source freshness boosts. The key is to compare pre-rerank and post-rerank rankings. If the reranker demotes exact evidence, it may be optimizing semantic fluency instead of domain relevance.

A generation or grounding failure means the right context was present but the answer still made unsupported claims, missed required facts, or cited weak evidence. Good knobs include stricter prompts, citation-required output schemas, abstention rules, answer length limits, evidence-before-answer formatting, and claim-level post-checks. Do not use prompt language such as "be accurate" as your only fix. Make the model show which source supports each factual claim, then reject or repair answers that cannot provide support.

A lost-in-the-middle failure means the answer changes when the same evidence appears at different positions in a long context. Diagnose it by moving the expected source to the beginning, middle, and end while holding everything else constant. Good knobs include reducing context size, ordering sources by relevance, placing required evidence near the answer instruction, using source manifests, splitting tasks into retrieve-then-synthesize stages, or using long-context strategies from the next module when the task truly needs broad evidence.

A data conflict failure means the retrieved context contains multiple plausible answers from different versions, tenants, products, or dates. Good knobs include metadata filters, source authority ranking, freshness windows, conflict-aware prompts, and explicit answer policies such as "prefer the newest approved policy document unless the question asks for historical behavior." The evaluation case should include the conflicting sources so the system is tested on the real ambiguity rather than a cleaned-up version.

The correct knob is usually the one closest to the failure. If the corpus lacks a document, change ingestion. If the document is present but not found, change retrieval. If it is found but buried, change ranking. If it is visible but ignored, change prompt and grounding checks. If the answer is faithful but too slow, change economics. This layer-by-layer diagnosis keeps optimization from becoming random architecture churn.

Thresholds should be explicit and tag-aware. A team might require recall@10 of 0.90 overall, recall@10 of 0.98 for policy-critical cases, faithfulness of 0.95 for customer-facing answers, and p95 latency below a product-specific limit. These numbers must be chosen from product risk and baseline behavior, not copied from another project. A threshold that blocks every deploy will be bypassed. A threshold that permits known harmful failures is not a gate.

## Latency and Cost Optimization Without Quality Blindness

RAG quality improvements often add cost. More retrieved candidates increase vector database work. Larger `k` increases prompt tokens. Reranking improves precision but adds a second model pass. LLM judges improve evaluation coverage but can become expensive when run against every production trace. Optimization therefore needs two dashboards: one for quality and one for economics. A cheaper system that fails silently is not cheaper; it has moved cost into user harm and support work.

Rerank only a bounded top-N candidate set. If recall@100 is high, you can test whether reranking the top 50 produces nearly the same nDCG as reranking the top 100. If it does, the smaller candidate count saves latency and model cost. If it does not, segment by query type because exact identifier queries and broad conceptual queries may need different candidate budgets.

Cache deterministic work. Embeddings for repeated queries, retrieval results for popular questions, source manifests for stable documents, and evaluation judge outputs for unchanged cases can often be cached. Cache keys must include model version, corpus version, prompt version, filters, and tenant scope. A cache that ignores corpus version can preserve stale retrieval results after the index changes, turning an optimization into a correctness bug.

Use asynchronous evaluation where possible. Production answers often need fast retrieval and generation, while deeper judge-based evaluation can run on sampled traces after the response. The online path can enforce deterministic gates such as citation presence, source ID validity, and refusal rules. The asynchronous path can run claim-level faithfulness checks, multiple judges, and human-review sampling without adding user-visible latency.

Keep evaluation cost proportional to risk. Run full judge panels on release candidates, high-risk tags, and sampled production traces. Run cheaper deterministic checks on every request. Run retrieval metrics on every CI change because they are inexpensive when the eval set is local. This layered approach preserves strong quality control without sending every trace through the most expensive evaluator.

Optimize prompts with evidence budgets. A prompt that includes 20 chunks may perform worse and cost more than a prompt with six well-ranked chunks and source metadata. Track token counts per source, answer length, citation count, and unsupported claim rate. If adding context lowers faithfulness, the system may be drowning the model in distractors. Context is not free just because it fits.

Finally, treat cost changes as eval changes. Lowering retrieval `k`, reducing reranker candidates, changing chunk size, removing a judge, or shortening the prompt should trigger the same regression suite as a quality improvement. Many production regressions come from "small" cost cleanups that were not evaluated because they did not look like feature changes.

## Did You Know?

- **RAG evaluation separates retrieval from generation**: a bad answer can come from missing evidence, poor ranking, weak prompt constraints, or unsupported generation, and each failure needs a different fix.
- **nDCG supports graded relevance**: it can reward a ranking that places essential evidence above merely background evidence, which binary hit-rate cannot express.
- **LLM judges need calibration**: judge prompts, model versions, answer order, and rubric wording can change verdicts, so human-labeled calibration sets remain important.
- **Regression cases become assets**: every production miss can become a permanent eval case that prevents the same query class from breaking again.

## Common Mistakes

| Mistake | Why it fails | Better approach |
|---|---|---|
| Optimizing one headline score | Averages hide failures in rare but important query classes such as exact identifiers, conflicts, or policy exceptions. | Report metrics by tag, risk level, product area, and query type before accepting a change. |
| Treating hit-rate as enough | Finding one relevant source does not prove that all required evidence reached the generator. | Use recall@k and context recall for questions that require multiple supporting sources. |
| Judging answers without retrieved context | The evaluator may reward a correct-looking answer that was not actually supported by the RAG pipeline. | Give the judge the question, retrieved context, candidate answer, and citation requirements. |
| Letting the judge be vague | Broad prompts reward style, length, and confidence rather than grounded correctness. | Use atomic rubrics with explicit pass or fail criteria and short evidence-based reasons. |
| Changing several knobs at once | A combined chunking, prompt, model, and reranker change can improve the total score while hiding the real cause. | Change one layer at a time unless an incident requires a coordinated rollback. |
| Ignoring latency and token cost | A high-quality eval result may be unusable if it doubles p95 latency or sends too much context to the model. | Track quality, latency, candidate count, prompt tokens, judge cost, and cache hit rate together. |
| Reusing stale golden labels | Source documents change, but old reference answers can keep expecting outdated behavior. | Version eval cases with source revisions and review labels when authoritative documents change. |

## Knowledge Check

<details>
<summary>1. Your retriever has recall@50 of 0.94 but recall@5 of 0.41 on policy questions. Which layer should you inspect first?</summary>

This points to a ranking or reranking problem rather than a raw indexing problem. The relevant evidence is entering the wider candidate set, so the next step is to compare pre-rerank and post-rerank positions, candidate diversity, hybrid weighting, freshness boosts, and reranker behavior on the affected query tags.
</details>

<details>
<summary>2. Why can an answer be faithful but still irrelevant?</summary>

Faithfulness only checks whether the answer's claims are supported by the supplied context. The answer can accurately summarize a retrieved source while failing to address the user's actual question, especially when retrieval returned a broadly related document and the generator followed the wrong thread.
</details>

<details>
<summary>3. A pairwise LLM judge always prefers the answer shown second. What should you do before trusting the comparison?</summary>

Randomize answer order, run both orderings, and inspect whether the winner changes with position. If position changes the outcome, treat the result as uncertain and use a stricter rubric, multiple judges, deterministic checks, or human labels before using the comparison as a deployment gate.
</details>

<details>
<summary>4. When is synthetic eval generation useful, and what is the main risk?</summary>

Synthetic generation is useful for expanding coverage across many source documents, especially when each generated question is anchored to a cited source span and then reviewed. The main risk is treating model-generated labels as unquestioned truth, which can create artificial, easy, or incorrectly grounded cases.
</details>

<details>
<summary>5. Your faithfulness score drops after increasing retrieval k from 5 to 20. What diagnosis is plausible?</summary>

The additional context may be lowering context precision by adding distractors, stale documents, or conflicting passages. The generator now has more text but weaker signal. Inspect unsupported claims, cited source IDs, prompt token allocation, and whether the most relevant sources are still near the top of the context bundle.
</details>

<details>
<summary>6. Why should CI gates report metrics by query tag instead of only reporting one average?</summary>

One average can hide regressions in small but high-risk slices. A change that improves common FAQ questions can break exact-match identifiers, conflict-resolution cases, or abstention cases. Tag-level reporting exposes those tradeoffs before a branch ships and makes threshold decisions defensible.
</details>

## Hands-On Exercise: Deploying a RAG Evaluation Pipeline on Kubernetes

In this lab, you will deploy a small evaluation API to a local Kubernetes v1.35 cluster. The service does not call an external LLM because the goal is to make the evaluation gate deterministic and cheap enough for CI. It computes retrieval metrics, runs a simple groundedness check against expected source IDs, and fails the response when thresholds are not met. In a real system, you would replace the mock candidate answers with outputs from your RAG pipeline and optionally add the LLM judge harness from earlier in the module.

### Step 1: Prepare the cluster and namespace

- [ ] Create a local Kind cluster targeting the course Kubernetes version, create a namespace, and confirm that the control plane is reachable before building the evaluation service.

```bash
kind create cluster --name rag-eval-cluster --image kindest/node:v1.35.0
kubectl create namespace rag-system
kubectl get nodes
```

### Step 2: Create the evaluation service

- [ ] Create a file named `rag_eval_service.py` with the following FastAPI application. The app holds a tiny golden set, computes recall@k, precision@k, hit-rate, MRR, and nDCG, and applies explicit thresholds before returning a pass or fail result.

```python
from __future__ import annotations

from math import log2

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="RAG Evaluation Gate")


class CandidateRun(BaseModel):
    retrieved_doc_ids: list[str]
    answer: str
    cited_doc_ids: list[str]


class EvaluationRequest(BaseModel):
    run: dict[str, CandidateRun]


GOLDEN = {
    "q1": {
        "question": "Which document explains access denied error 0x80070005?",
        "relevant": {"runbook-permissions", "windows-error-index"},
        "grades": {"runbook-permissions": 3, "windows-error-index": 2},
        "required_phrase": "access denied",
    },
    "q2": {
        "question": "What should the assistant do when no source supports an answer?",
        "relevant": {"rag-answer-policy"},
        "grades": {"rag-answer-policy": 3},
        "required_phrase": "refuse",
    },
}


THRESHOLDS = {
    "recall_at_3": 0.75,
    "precision_at_3": 0.50,
    "hit_rate_at_3": 1.00,
    "mrr": 0.75,
    "ndcg_at_3": 0.75,
    "groundedness": 0.75,
}


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return sum(1 for doc_id in top_k if doc_id in relevant) / len(top_k)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    return sum(1 for doc_id in retrieved[:k] if doc_id in relevant) / len(relevant)


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if any(doc_id in relevant for doc_id in retrieved[:k]) else 0.0


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def dcg_at_k(ranking: list[str], grades: dict[str, int], k: int) -> float:
    return sum((2 ** grades.get(doc_id, 0) - 1) / log2(rank + 1) for rank, doc_id in enumerate(ranking[:k], start=1))


def ndcg_at_k(retrieved: list[str], grades: dict[str, int], k: int) -> float:
    ideal = sorted(grades, key=lambda doc_id: grades[doc_id], reverse=True)
    ideal_score = dcg_at_k(ideal, grades, k)
    if ideal_score == 0.0:
        return 0.0
    return dcg_at_k(retrieved, grades, k) / ideal_score


def groundedness(case: dict, candidate: CandidateRun) -> float:
    cites_relevant_source = any(doc_id in case["relevant"] for doc_id in candidate.cited_doc_ids)
    # Teaching simplification: real systems use claim-level faithfulness (see faithfulness_prompt above), not substring matching
    answer_mentions_required_fact = case["required_phrase"].lower() in candidate.answer.lower()
    return (float(cites_relevant_source) + float(answer_mentions_required_fact)) / 2


@app.post("/evaluate")
def evaluate(request: EvaluationRequest) -> dict:
    totals = {metric: 0.0 for metric in THRESHOLDS}
    per_case = {}
    for case_id, case in GOLDEN.items():
        candidate = request.run[case_id]
        retrieved = candidate.retrieved_doc_ids
        relevant = case["relevant"]
        scores = {
            "recall_at_3": recall_at_k(retrieved, relevant, 3),
            "precision_at_3": precision_at_k(retrieved, relevant, 3),
            "hit_rate_at_3": hit_rate_at_k(retrieved, relevant, 3),
            "mrr": reciprocal_rank(retrieved, relevant),
            "ndcg_at_3": ndcg_at_k(retrieved, case["grades"], 3),
            "groundedness": groundedness(case, candidate),
        }
        per_case[case_id] = scores
        for metric, value in scores.items():
            totals[metric] += value

    aggregate = {metric: value / len(GOLDEN) for metric, value in totals.items()}
    failed = {metric: value for metric, value in aggregate.items() if value < THRESHOLDS[metric]}
    return {
        "pass": not failed,
        "thresholds": THRESHOLDS,
        "aggregate": aggregate,
        "failed_metrics": failed,
        "per_case": per_case,
    }
```

### Step 3: Build and load the container image

- [ ] Create a `requirements.txt` file and `Dockerfile`, then build the image locally and load it into the Kind node so the deployment does not depend on an external registry.

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
```

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY rag_eval_service.py /app/rag_eval_service.py

EXPOSE 8000
CMD ["uvicorn", "rag_eval_service:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t rag-eval-gate:latest .
kind load docker-image rag-eval-gate:latest --name rag-eval-cluster
```

### Step 4: Deploy the evaluator

- [ ] Create `rag-eval-deployment.yaml`, apply it, and wait until Kubernetes reports the deployment as available.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-eval-gate
  namespace: rag-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rag-eval-gate
  template:
    metadata:
      labels:
        app: rag-eval-gate
    spec:
      containers:
        - name: api
          image: rag-eval-gate:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: rag-eval-gate
  namespace: rag-system
spec:
  selector:
    app: rag-eval-gate
  ports:
    - name: http
      port: 80
      targetPort: 8000
```

```bash
kubectl apply -f rag-eval-deployment.yaml
kubectl wait --for=condition=available deployment/rag-eval-gate --namespace rag-system --timeout=120s
```

### Step 5: Run a passing evaluation

- [ ] Forward the service to your workstation, send a candidate run that retrieves and cites the right sources, and confirm that the evaluation gate passes.

```bash
kubectl port-forward service/rag-eval-gate 8080:80 --namespace rag-system
```

```bash
curl -s -X POST http://127.0.0.1:8080/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "run": {
      "q1": {
        "retrieved_doc_ids": ["runbook-permissions", "windows-error-index", "general-troubleshooting"],
        "answer": "Error 0x80070005 is an access denied issue.",
        "cited_doc_ids": ["runbook-permissions"]
      },
      "q2": {
        "retrieved_doc_ids": ["rag-answer-policy", "prompt-style-guide", "fallback-copy"],
        "answer": "When no source supports the answer, the assistant should refuse or ask for better context.",
        "cited_doc_ids": ["rag-answer-policy"]
      }
    }
  }'
```

### Step 6: Run a failing evaluation and inspect why

- [ ] Send a candidate run with weak retrieval and unsupported citations, then identify which metric failed before changing the pipeline.

```bash
curl -s -X POST http://127.0.0.1:8080/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "run": {
      "q1": {
        "retrieved_doc_ids": ["general-troubleshooting", "network-overview", "release-notes"],
        "answer": "The error is probably a network issue.",
        "cited_doc_ids": ["network-overview"]
      },
      "q2": {
        "retrieved_doc_ids": ["prompt-style-guide", "fallback-copy", "general-faq"],
        "answer": "The assistant should answer confidently.",
        "cited_doc_ids": ["general-faq"]
      }
    }
  }'
```

The failing response should show low recall, low hit-rate, low MRR, low nDCG, and low groundedness. That output is the optimization map. The first fix is not "use a bigger model." The first fix is to restore retrieval of `runbook-permissions`, `windows-error-index`, and `rag-answer-policy`, then re-run the same gate before touching the answer prompt.

### Step 7: Clean up the lab environment

- [ ] Remove the namespace or cluster when you are finished so the local machine does not keep running unused resources.

```bash
kubectl delete namespace rag-system
kind delete cluster --name rag-eval-cluster
```

## Next Module

[Module 1.5: Long-Context LLMs and Prompt Caching](../module-1.5-long-context-prompt-caching/) continues the sub-track by comparing retrieval against long-context strategies, explaining lost-in-the-middle behavior in more depth, and showing how prompt caching changes cost and latency tradeoffs.

## Sources

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) - Foundational RAG paper describing parametric and non-parametric memory for knowledge-intensive generation.
- [Ragas: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217) - Primary source for RAGAS-style decomposition of retrieval and generation evaluation dimensions.
- [ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems](https://arxiv.org/abs/2311.09476) - Research framework for automated RAG evaluation using generated labels and lightweight judges.
- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) - Core LLM-as-judge reference discussing model-based evaluation and judge bias concerns.
- [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634) - Reference for structured LLM-based evaluation of generated text and alignment with human judgments.
- [Evaluating Verifiability in Generative Search Engines](https://arxiv.org/abs/2304.09848) - Groundedness and citation-support reference for generated answers over retrieved sources.
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) - Empirical reference for position-sensitive context use in long inputs.
- [Evaluation in Information Retrieval](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html) - Stanford IR book chapter covering test collections and retrieval evaluation principles.
- [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663) - Retrieval benchmark reference for evaluating search systems across diverse tasks.
- [MTEB: Massive Text Embedding Benchmark](https://arxiv.org/abs/2210.07316) - Embedding evaluation reference useful when choosing or comparing embedding models.
- [Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) - Ranking-fusion reference relevant when combining lexical and semantic retrieval signals.
- [RAGAS Documentation](https://docs.ragas.io/en/stable/) - Tooling reference for implementing RAG evaluation metrics while keeping concepts portable (accessed 2026-06).
- [TruLens Documentation](https://www.trulens.org/getting_started/) - Tooling reference for feedback functions and RAG evaluation instrumentation (accessed 2026-06).
- [DeepEval Documentation](https://docs.confident-ai.com/) - Tooling reference for test-style LLM application evaluation (accessed 2026-06).
- [promptfoo Documentation](https://www.promptfoo.dev/docs/intro/) - Tooling reference for prompt and model regression tests in development workflows (accessed 2026-06).
