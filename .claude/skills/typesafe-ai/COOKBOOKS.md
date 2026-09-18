# TypeSafe cookbooks — KubeDojo inventory

**Fetched:** 2026-09-18 from https://docs.typesafe.ai/cookbooks/ (18 pages; index via https://docs.typesafe.ai/llms.txt).  
**Purpose:** durable map of which recipes we adopt in KubeDojo vs park. Re-check live docs when API/model pins change.

**Adopted in code today** (`scripts/jev_epic_triage.py`, `scripts/typesafe_client.py`):

| Pattern | Source cookbook | Where |
| --- | --- | --- |
| Batch N questions / 1 call | [parallel_questions](https://docs.typesafe.ai/cookbooks/parallel_questions.md) | triage fan-out |
| Choice auto-act iff `max(probabilities) ≥ 0.60` | [consistency_choice](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook.md) | `MIN_CHOICE_TOP_PROB` |
| Noul parallel band `<0.35` serialize / `>0.65` parallel | (fleet policy + noul uncertainty) | `PARALLEL_NO` / `PARALLEL_YES` |
| Citation relation Choice + conf gate | [citation_check](https://docs.typesafe.ai/cookbooks/citation_check.md) | `typesafe_client.check_claim_against_excerpt` |
| Shared top_prob helper | consistency_choice | `typesafe_client.choice_top_prob` / `choice_is_uncertain` |

---

## Build next (when a wave needs it)

| Cookbook | Pattern | KD hook |
| --- | --- | --- |
| [skill_suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion.md) | Rank catalog + “needs skill?”; 2nd pass top-3 | Load ≤1 skill into agent system prompt |
| [llm_guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails.md) | Hazard Nouls + severity Score → pass/review/block | Dispatch / bridge ingress |
| [consistency_noul](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook.md) | Repeat Nouls; route unstable P(yes) | Gap Catcher D-scores; keep raw noul |
| [sde_cascade](https://docs.typesafe.ai/cookbooks/sde_cascade.md) | mini → verify → reason | Cheap extract of issue/PR facts |

## Strong later (curriculum / RAG)

| Cookbook | Pattern | KD hook |
| --- | --- | --- |
| [classifying_rag_passages](https://docs.typesafe.ai/cookbooks/classifying_rag_passages.md) | Score passages; drop injection / flag contradiction | RAG on curriculum / pins |
| [semantic_find](https://docs.typesafe.ai/cookbooks/semantic_find.md) | Choice over line IDs + Noul `exists` | Answer lines in long modules/RFCs |
| [rerank_typesafe](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md) | BM25 shortlist → TypeSafe re-rank | “which module covers X” |
| [classification_using_confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence.md) | Choice + conf → narrow or roll up | Track taxonomy when unsure |
| [hierarchical_classification](https://docs.typesafe.ai/cookbooks/hierarchical_classification.md) | Beam over Choice probs | Deep trees (platform toolkits) |
| [autoformat](https://docs.typesafe.ai/cookbooks/autoformat.md) | Recover Markdown structure | Import / paste cleanup |

## Park (low KD fit now)

| Cookbook | Why park |
| --- | --- |
| [function_calling](https://docs.typesafe.ai/cookbooks/function_calling.md) | Closed-set tool dispatch — only if we typed fleet tools |
| [entity_alignment](https://docs.typesafe.ai/cookbooks/entity_alignment.md) | Entity merge/curator — catalog dedupe only |
| [pre_parsed_value_extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md) | Regex → Choice pick (email/phone/$) |
| [date_extraction](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook.md) | Date parts via Choice; calendar in code |
| [autoresearch_feature_discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery.md) | Autoresearch → CatBoost — research lab |

---

## Shared recipes (steal everywhere)

1. **Batch** independent questions in one `system_one` (document-dominated workloads ≈ Nx cheaper).
2. Gate on **`top_prob` / `confidence`**, not just the winning label.
3. Prefer an explicit **middle outcome** (uncertain / curator / broader label) over forced picks.
4. Keep **math, thresholds, side effects in code** after Choice/Score/Noul.
5. **String-match first** when checking quotes; model only for support vs contradict.
6. Jev **advises**; CF ≠ author + exact-head CI remain merge authority.

## One-liner index (all 18)

| Slug | One-liner |
| --- | --- |
| `parallel_questions` | 13 Qs / 1 call ≈ 12× cheaper, same answers |
| `skill_suggestion` | Pick ≤1 skill from large catalog; cut wrong loads |
| `citation_check` | Quote in source? + supports/contradicts/says_nothing |
| `llm_guardrails` | In/out message hazard + severity → pass/review/block |
| `sde_cascade` | Small model extract → verify → escalate to reasoner |
| `classifying_rag_passages` | Passage scores; drop injection; flag contradiction |
| `consistency_noul_cookbook` | Repeat Nouls; unstable → human; keep P(yes) visible |
| `consistency_choice_cookbook` | top_prob band → uncertain / auto-act |
| `function_calling` | NL → closed-set tool + args with confidences |
| `rerank_typesafe` | BM25 shortlist re-ranked by TypeSafe |
| `semantic_find` | Line-ID Choice + exists Noul for “not in doc” |
| `autoformat` | Plain text → Markdown structure recovery |
| `entity_alignment` | Score merge / curator / drop on entity pairs |
| `hierarchical_classification` | Beam search over taxonomy Choice probs |
| `classification_using_confidence` | Unsure → report parent division |
| `pre_parsed_value_extraction_cookbook` | Regex candidates → Choice pick verbatim |
| `date_extraction_cookbook` | Date parts Choice; resolve in code |
| `autoresearch_feature_discovery` | Propose questions as features for CatBoost |

Live SSOT: https://docs.typesafe.ai/llms.txt — prefer live pages if this inventory drifts.
