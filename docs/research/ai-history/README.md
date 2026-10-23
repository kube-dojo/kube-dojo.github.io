# AI History Research Wiki

## Status Board

This directory contains the operational research files for the 73-chapter AI History book. The English chapter sources and public index each contain Chapters 1–73; research contracts currently cover Chapters 1–72 only.

Chapter 73, **The Algorithmic Response**, is the book's technical coda. Its prose and index entry exist, but its research contract and contract-backed readiness remain pending under #2288. Inventory inclusion does not establish accepted status or review clearance.

The 72 existing contracts currently record **40 `accepted`, 11 `prose_ready`, and 21 `capacity_plan_anchored`** top-level statuses. These are recorded workflow labels, not fresh source or editorial acceptance. Reconciliation of the supporting review records remains open under #2288; this inventory does not promote any chapter.

<details>
<summary>Earlier era-specific status notes (historical; not the current status board)</summary>

- **Golden Research (Parts 1-2, Chapters 1-10):** Currently under revision based on cross-family review (downgraded to `reviewing` while we convert to claim-level anchoring and resolve factual disputes).
- **Part 3 (The Birth of Symbolic AI):** Ch11-14 prose `accepted`; Ch15 dual-cleared `prose_ready` 2026-04-28; Ch16 still researching (now Codex-owned per 2026-04-29 split).
- **Part 6 (The Rise of Data & Distributed Compute):** Ch32-37 dual-cleared `prose_ready` 2026-04-28 (caps 5,600 / 4,900 / 5,200 / 4,300 / 5,000 / 5,000); Ch38-40 not yet rebuilt.
- **Part 4 (The First Winter):** Ch17-23 cross-family cleared for capped prose drafting; Ch21 carries a Yellow-caveated Bachant/McDermott mirror-source guardrail.
- **Part 5 (The Mathematical Resurrection):** Ch24-31 prose `accepted`.
- **Part 8 (The Transformer, Scale & Open Source):** Ch50-58 dual-cleared `prose_ready`; Ch58 cap is 5,200 words.
- **Part 9 (The Product Shock & Physical Limits):** Ch59-Ch72 dual-cleared `prose_ready` with 5,700-, 5,800-, 5,800-, 4,800-, 4,500-, 5,000-, 5,300-, 5,400-, 5,400-, 5,500-, 6,000-, 6,000-, 6,200-, and 6,400-word caps.

</details>

All drafting is paused for any chapter whose contract is not at `prose_ready` or beyond.

The team workflow is maintained in `TEAM_WORKFLOW.md`. It defines the gates between research contracts, gap analysis, anchor extraction, prose readiness, drafting, and cross-family review.

## Structure

*   `source-catalog.md`: Shared bibliography for recurring sources (e.g., Hodges, Gleick, Dyson).
*   `comprehensive-roadmap-72-chapters.md`: Current 73-chapter roadmap; the historical filename is retained.
*   `modern-coverage-matrix.md`: Routing table for late-era themes added during the modern coverage pass.
*   `chapters/`: The 72 research-contract directories for Chapters 1–72, each containing the eight standard contract files. Chapter 73 has no contract directory yet. File presence alone does not establish readiness: each contract must hit the KubeDojo sourcing standard (claim-level anchors, page/section references, independent confirmation) before unlocking for prose drafting.

## Role Split (effective 2026-04-29 — prose pipeline pivot)

After Gemini self-admitted to systemic URL/anchor hallucination across his prior research work (epic commit `03640e20`, Issue #421), research duties were taken away from Gemini and redistributed. On 2026-04-29 the prose-expansion role moved from Claude opus to Codex (gpt-5.5) on Codex's own recommendation: gpt-5.5 has wider weekly bandwidth, its source-discipline instinct is the strongest of the three families, and the expansion task ("shape, tighten, enforce source discipline") plays to Codex's strengths.

- **Claude — research lead + source-fidelity reviewer.** Owns the chapter contracts (brief.md, sources.md, scene-sketches.md, timeline.md, people.md, infrastructure-log.md, open-questions.md, status.yaml) for Parts 1, 2, 3, 6, 7. Extracts anchors via `curl` + `pdftotext` + `pdfgrep` directly. Reviews expanded prose for source fidelity (independent fresh session). Prose expansion fallback when Codex bandwidth is exhausted; the same strict-source rule applies (see `TEAM_WORKFLOW.md` § 5b).
- **Codex — research lead + default prose expander.** Owns the chapter contracts for Parts 4, 5, 8, **9** (Part 9 transferred from Claude on 2026-04-29). Default prose expander for Parts 1, 2, 3, 6, 7 after Gemini drafts: takes Gemini's tight ~3k-word first draft, expands to verdict cap, enforces source discipline. Drafts and expands prose for Codex-owned Parts 4, 5, 8, 9. Cross-family reviewer for Claude- and Gemini-authored work.
- **Gemini — gap auditor + first-draft prose writer.** Stops touching sources entirely. Continues to gap-audit every chapter (his strength: detecting narrative gaps, missing scenes, capacity-plan honesty). Drafts first-pass prose for Parts 1, 2, 6, 7 from an approved contract (~3,000 words, anchor-strict, no source additions). Reviews prose quality after Codex expansion when narrative coherence is the chief concern.
- **Cross-family verdict** rule unchanged: every chapter requires a `READY_TO_DRAFT` or `READY_TO_DRAFT_WITH_CAP` verdict from BOTH cross-family reviewers (one not from the author's family) before drafting unlocks.

### Prose pipeline (Parts 1, 2, 3, 6, 7)

```
Approved contract → Gemini first draft (~3k) → Codex expansion to cap (default)
                                                Claude expansion (fallback)
                                              → Claude source-fidelity review
                                              → Gemini OR Claude prose-quality review
                                              → merge
```

Strict-source rule applies to BOTH expansion paths: use only the provided contract and claim matrix; if evidence is missing for a scene, leave the scene thin rather than filling it.

Why the split: Gemini fabricated URLs and page anchors; Codex's shell tooling extracts real anchors; Claude has the same tooling and integration discipline. Gemini's drafting and gap-audit value remains real — sourcing was the broken seam.

## Ownership & Tracking Issues

Coordination happens across 9 Part Tracking issues linked to Epic #394. The "Research" column owns the contract; the "Prose" column owns first-draft writing; both go through cross-family review:

| Part | Issue | Era | Research lead | Prose drafter |
|---|---|---|---|---|
| 1 | [#399](https://github.com/kube-dojo/kube-dojo.github.io/issues/399) | The Mathematical Foundations (Ch 1-5) | **Claude** (was Gemini) | **Gemini** → Claude expansion |
| 2 | [#400](https://github.com/kube-dojo/kube-dojo.github.io/issues/400) | The Analog Dream & Digital Blank Slate (Ch 6-10) | **Claude** (was Gemini) | **Gemini** → Claude expansion |
| 3 | [#401](https://github.com/kube-dojo/kube-dojo.github.io/issues/401) | The Birth of Symbolic AI (Ch 11-16) | **Claude** | **Codex** → Claude expansion |
| 4 | [#402](https://github.com/kube-dojo/kube-dojo.github.io/issues/402) | The First Winter (Ch 17-23) | **Codex** | **Codex** |
| 5 | [#403](https://github.com/kube-dojo/kube-dojo.github.io/issues/403) | The Mathematical Resurrection (Ch 24-31) | **Codex** | **Codex** |
| 6 | [#404](https://github.com/kube-dojo/kube-dojo.github.io/issues/404) | The Rise of Data & Distributed Compute (Ch 32-40) | **Claude** (was Gemini) | **Gemini** → Claude expansion |
| 7 | [#405](https://github.com/kube-dojo/kube-dojo.github.io/issues/405) | The Deep Learning Revolution & GPU Coup (Ch 41-49) | **Claude** (was Gemini) | **Gemini** → Claude expansion |
| 8 | [#406](https://github.com/kube-dojo/kube-dojo.github.io/issues/406) | The Transformer, Scale & Open Source (Ch 50-58) | **Codex** | **Codex** |
| 9 | [#407](https://github.com/kube-dojo/kube-dojo.github.io/issues/407) | The Product Shock & Physical Limits (Ch 59-72) | **Codex** (was Claude — transferred 2026-04-29) | **Codex** |

Note: The 630 changed files in the original PR included automatically generated placeholder directories for the first 68 chapters to ensure proper boundaries. The modern-era coverage pass later expanded the roadmap to 72 chapters so RAG/tool use, multimodal systems, benchmark politics, and data labor/copyright are not forced into unrelated chapters. The current inventory also includes Chapter 73's coda; the tracking table above covers Chapters 1–72 and does not assign or clear its missing contract.
