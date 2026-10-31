# KubeDojo Quality Rubric

**Purpose**: Measurable scoring system for rating module and lab quality. Used during audits and reviews.

Apply `docs/review-contract.md` for researched scope, topic coverage and page-kind omissions. Word, density, template and citation counts are planning diagnostics, not passing evidence or targets to pad. Independently verify outcome-to-teaching/practice/assessment coverage and material topic omissions. The eight-dimension module and five-dimension lab score floors below remain unchanged; source, execution and final acceptance are separate gates. Report legacy verifier disagreements during #3744 migration explicitly.

## Citation Gate (Mandatory Before Scoring)

Before a module can be counted as `4/5` or `5/5`, it must pass a citation and evidence hygiene check.

Minimum requirements:
- every war story must include an explicit citation or `Source:` line
- concrete factual claims that matter to trust, safety, chronology, pricing, policy, law, standards, or product capability must be traceable to cited sources
- each upgraded module must include a `## Sources` section
- uncited modules may be improved, but they are still **not review-passed**

This gate applies before the 8-dimension score is considered valid.

---

## Complexity Marker Convention (locked)

Every module carries exactly one **complexity marker** in its top-of-module banner.
The canonical form is a **backticked bracketed tier** inside the body blockquote:

```
> **Complexity**: `[MEDIUM]`
```

- **Controlled vocabulary — five tiers only:** `[QUICK]`, `[MEDIUM]`, `[COMPLEX]`,
  `[ADVANCED]`, `[EXPERT]`. Do not invent tiers or use bare words
  ("Intermediate", "Advanced"), bare brackets (`[MEDIUM]` without backticks), or
  a `complexity:` frontmatter key. The **body marker is the single source of truth**;
  the legacy `complexity:` frontmatter key is dropped.
- **`[ADVANCED]` is sanctioned** as the tier between `[COMPLEX]` and `[EXPERT]`
  (production engineering at senior scale) — see Dimension 8, which scores
  `[COMPLEX]`/`[ADVANCED]`/`[EXPERT]` on the same practitioner-depth band.
- **`[BEGINNER]` is not a tier.** It maps to `[QUICK]` (the introductory band).
- Non-canonical spellings map deterministically: `Intermediate`/`[INTERMEDIATE]` →
  `[MEDIUM]`, `Advanced` → `[ADVANCED]`, `Complex` → `[COMPLEX]`; a range maps to
  its **ceiling** ("Beginner to intermediate" → `[MEDIUM]`, "Intermediate to
  Advanced" → `[ADVANCED]`).
- The banner blockquote format is specified in `.claude/rules/module-quality.md`.

**Enforcement:** `scripts/normalize_complexity_markers.py` rewrites any drifted
marker token to canonical form and drops the `complexity:` frontmatter key
(`--check` reports drift, `--write` fixes it). This normalizer is **format-only** —
it never re-levels a module based on content judgement; a genuinely mislabeled tier
(e.g. a `[QUICK]` module whose content is medior) is tracked as a separate content
follow-up, not silently re-tiered. Locked via #2141 / #2146 / #2181 / #2187 / #2195.

> **Pipeline note (v2 quality pipeline)**: the v2 cross-family review (`scripts/quality/prompts.py::review_prompt`) deliberately **suspends** the Citation Gate during the rewrite/review phase because citation insertion is owned by a separate downstream stage (`scripts/citation_backfill.py`). The writer is instructed to preserve any pre-existing `## Sources` section verbatim and not to add a new one. After v2 reaches `COMMITTED`, run `python -m scripts.quality.pipeline backfill-pending` (or invoke `scripts/citation_backfill.py research/inject` per slug) to satisfy the gate. A v2-rewritten module that has not yet been backfilled is **expected** to score low on this rubric until backfill runs — that is not a v2 bug, it is the seam between the two pipelines.

---

## Module Rubric (8 Dimensions, 1-5 Scale)

### Dimension 1: Learning Outcomes

| Score | Description |
|-------|-------------|
| **1** | No learning outcomes stated. Reader has no idea what they'll learn. |
| **2** | Vague outcomes ("understand Kubernetes networking"). Not measurable. |
| **3** | Outcomes stated but only at Bloom's Level 1-2 (remember/understand). |
| **4** | Clear, measurable outcomes at Level 3+ (apply/analyze). Aligned with content. |
| **5** | Outcomes explicitly use action verbs, are testable, and the module delivers on every one. Includes Level 4-6 outcomes. |

### Dimension 2: Scaffolding & Structure

| Score | Description |
|-------|-------------|
| **1** | No logical order. Sections could be rearranged randomly. Dump of disconnected facts. |
| **2** | Some ordering but no narrative bridges. Reader must infer connections. |
| **3** | Logical progression from simple to complex. Prerequisites mentioned. |
| **4** | Clear scaffolding: each section builds on the last. Explicit bridges between sections. References prior modules when building on concepts. |
| **5** | Expert scaffolding: worked examples before practice, complexity gradually increases, expertise reversal considered (different depth for different audiences). |

### Dimension 3: Active Learning

| Score | Description |
|-------|-------------|
| **1** | Pure reading. No exercises, no questions, no interactivity. The learner is passive. |
| **2** | Exercise at the end only. Module body is entirely passive reading. |
| **3** | Exercise + quiz present. Some scenario-based questions. |
| **4** | Multiple active learning touchpoints: prediction prompts in the body, "what would happen if" scenarios, decision-making exercises. Quiz tests understanding not recall. |
| **5** | Active learning woven throughout: embedded questions, try-it-yourself moments before solutions are shown, comparison exercises, design challenges. Learner constructs knowledge, not just reads it. |

### Dimension 4: Real-World Connection

| Score | Description |
|-------|-------------|
| **1** | No real-world context. Pure theory or command reference. |
| **2** | Mentions "in production" but gives no concrete context, consequence, or tradeoff. |
| **3** | Connects the concept to a concrete use case, consequence, or decision; examples may remain generic. |
| **4** | Explains practical relevance with specific, evidence-backed context, consequences, failure modes, or tradeoffs; common mistakes are tied to realistic decisions. |
| **5** | Integrates practical context throughout with accurate, bounded examples, competing tradeoffs, and decision guidance; the explanation makes when and why the concept matters clear. |

### Dimension 5: Assessment Alignment

| Score | Description |
|-------|-------------|
| **1** | No quiz or exercise. No way to test learning. |
| **2** | Quiz present but questions test recall only ("What command does X?"). |
| **3** | Quiz has mix of recall and understanding questions. Exercise is "follow these steps." |
| **4** | Quiz tests analysis/evaluation (Bloom's 4-5). Exercise requires problem-solving, not just command execution. Solutions explain WHY, not just WHAT. |
| **5** | Assessment perfectly aligned with outcomes: every stated learning outcome is tested. Exercise has progressive difficulty. Quiz answers are thorough explanations. Learner can self-assess genuine understanding. |

### Dimension 6: Cognitive Load Management

| Score | Description |
|-------|-------------|
| **1** | Information dump. Too many concepts introduced at once. No chunking. |
| **2** | Some organization but concepts pile up without breaks. No worked examples. |
| **3** | Reasonable chunking. Concepts introduced one at a time. Some diagrams help. |
| **4** | Good cognitive load management: prerequisites taught before combining, diagrams integrated with text, worked examples before practice, clear section boundaries. |
| **5** | Expert load management: split-attention eliminated (labels on diagrams, not separate), complexity gradient appropriate for target audience, dual coding (visual + verbal), completion problems before full problems. |

### Dimension 7: Engagement & Motivation

| Score | Description |
|-------|-------------|
| **1** | Tone or organization obstructs learning; prose is confusing or inaccessible. |
| **2** | Functional but flat or inconsistent; explanations are readable but weakly signposted. |
| **3** | Clear, respectful tone with purposeful signposting and examples; engagement comes from relevance and active practice. |
| **4** | Conversational, authoritative, well-paced explanation with precise examples and useful emphasis; optional devices, when used, are accurate and restrained. |
| **5** | Memorable through exceptional clarity, cohesion, and usefulness; examples and emphasis deepen the explanation without relying on stories, analogies, humor, mystery, or gamification. |

### Dimension 8: Practitioner Depth (complexity-scaled)

This dimension scales with the module's complexity tag. A `[QUICK]` introductory module is not expected to teach decision frameworks; a `[COMPLEX]` advanced module must.

**For `[QUICK]` modules** (introductory, foundational concepts):
| Score | Description |
|-------|-------------|
| **1** | Definition without context. Reader doesn't know why this matters. |
| **2** | Defines the concept but no tradeoffs or alternatives mentioned. |
| **3** | Explains why the concept exists and when it applies. Mentions one alternative or limitation. |
| **4** | Theory before mechanics — explains the WHY before the HOW. Mentions tradeoffs honestly. References when this approach is wrong. Reader understands the *purpose*, not just the *syntax*. |
| **5** | Concept is anchored to a real problem. Tradeoffs are discussed. Reader leaves with intuition, not just facts. Even a beginner module teaches *thinking*, not just naming. |

**For `[MEDIUM]` modules** (applied techniques, intermediate practitioners):
| Score | Description |
|-------|-------------|
| **1** | Command reference only. "Run X, then Y." No explanation of why, when, or what could go wrong. |
| **2** | Some context around commands but no decision frameworks. Reader knows HOW but not WHEN or WHY NOT. |
| **3** | Includes tradeoff mentions and comparison tables. Some "when to use X vs Y" guidance. Patterns mentioned but not explained in depth. |
| **4** | Dedicated sections for: patterns (proven approaches with rationale), anti-patterns (what fails and why), and a comparison table or decision guide. Theory explains the WHY before showing the HOW. Prose explains concepts between code blocks. |
| **5** | Patterns and anti-patterns are concrete with consequences. Decision guidance is actionable. Theory and practice balanced — neither textbook nor cookbook. Reader can defend their choices in a design review. |

**For `[COMPLEX]` / `[ADVANCED]` / `[EXPERT]` modules** (production engineering, senior practitioners):
| Score | Description |
|-------|-------------|
| **1** | Surface-level coverage of an advanced topic. Misses the actual hard parts. |
| **2** | Covers basics but no scaling, failure modes, or architectural reasoning. |
| **3** | Tradeoffs mentioned. Some patterns discussed. Reader gets the gist but couldn't implement at scale. |
| **4** | Dedicated patterns, anti-patterns, decision framework, and architectural reasoning sections. Failure modes documented. Scaling considerations addressed. Reader could implement this in production. |
| **5** | Practitioner-grade throughout: every technique comes with tradeoffs discussed honestly, edge cases covered, failure modes documented, scaling considerations addressed. Reader could defend their architecture in a senior design review. An experienced engineer would learn something new. |

---

## Lab Rubric (5 Dimensions, 1-5 Scale)

### Dimension L1: Scenario-Based Design

| Score | Description |
|-------|-------------|
| **1** | "Run these commands in order." No context or motivation. |
| **2** | Brief context paragraph then "run these commands." |
| **3** | Scenario sets up a problem but steps are prescriptive (copy-paste). |
| **4** | Scenario presents a real problem. Learner must figure out approach with guidance. Steps describe WHAT to achieve, not exactly HOW. |
| **5** | Immersive scenario. Learner makes real decisions. Multiple valid approaches. Environment starts in a "broken" or "incomplete" state that reflects production reality. |

### Dimension L2: Progressive Difficulty

| Score | Description |
|-------|-------------|
| **1** | All steps same difficulty. No progression. |
| **2** | Roughly easy→hard but jumps in difficulty between steps. |
| **3** | Clear easy→medium→hard progression. Each step builds on the last. |
| **4** | Smooth difficulty curve. Early steps build confidence. Later steps require combining multiple concepts. Optional "stretch" challenge for advanced learners. |
| **5** | Expert progression: warm-up → core challenge → integration → "what if" extension. Difficulty matches the module's Bloom's level targets. |

### Dimension L3: Understanding Over Memorization

| Score | Description |
|-------|-------------|
| **1** | Validates only output format ("did the pod start?"). Tests command memorization. |
| **2** | Validates correct behavior but doesn't test understanding of WHY. |
| **3** | Some "why" questions. Validation checks behavior, not just existence. |
| **4** | Requires the learner to explain or predict behavior. Validation tests correct configuration AND understanding. Includes "what would break if you changed X?" |
| **5** | Lab IS the reasoning exercise. Learner must diagnose, decide, implement, and verify. Tests transfer — could the learner apply this to a different but related scenario? |

### Dimension L4: Hint & Feedback Quality

| Score | Description |
|-------|-------------|
| **1** | No hints. Learner is stuck or looks up the answer externally. |
| **2** | Hints are just the answer in a `<details>` tag. |
| **3** | Tiered hints: concept hint → component hint → command hint. |
| **4** | Hints teach, not just tell. First hint explains the concept, second narrows the approach, third gives specific guidance. Error messages are helpful. |
| **5** | Feedback loop: hints adapt to common mistakes. "If you see error X, it means Y — try Z." Hints reference the module's teaching for reinforcement. |

### Dimension L5: Transfer Potential

| Score | Description |
|-------|-------------|
| **1** | Learner can complete the lab but couldn't apply the skill elsewhere. |
| **2** | Some transferable skills but tightly coupled to the specific scenario. |
| **3** | Core skill is transferable. Learner understands the general approach. |
| **4** | Lab explicitly discusses generalization: "This same pattern applies when..." Reflection question at the end. |
| **5** | Lab ends with an open-ended challenge: "Now apply this approach to [different but related problem]." Learner practices transfer, not just repetition. |

---

## Scoring Template

Copy this template when auditing a module:

```markdown
## Module: [Title]
**File**: [path]
**Lines**: [count]
**Track**: [track]

### Module Scores (1-5)

**Pass threshold**: sum >= 33/40 AND every dimension >= 4

| Dimension | Score | Notes |
|-----------|-------|-------|
| D1 Learning Outcomes | /5 | |
| D2 Scaffolding | /5 | |
| D3 Active Learning | /5 | |
| D4 Real-World Connection | /5 | |
| D5 Assessment Alignment | /5 | |
| D6 Cognitive Load | /5 | |
| D7 Engagement | /5 | |
| D8 Practitioner Depth | /5 | (complexity-scaled) |
| **Sum** | **/40** | |

### Lab Scores (1-5)

**Pass threshold**: sum >= 21/25 AND every dimension >= 4

| Dimension | Score | Notes |
|-----------|-------|-------|
| L1 Scenario-Based Design | /5 | |
| L2 Progressive Difficulty | /5 | |
| L3 Understanding Over Memorization | /5 | |
| L4 Hint & Feedback Quality | /5 | |
| L5 Transfer Potential | /5 | |
| **Sum** | **/25** | |

### Key Strengths
- 

### Key Weaknesses
- 

### Action Required
- [ ] None / Low / Medium / High / Critical
- [ ] Specific fixes needed:
```

```markdown
## Lab: [Title]
**File**: [path]
**Track**: [track]

### Lab Scores (1-5)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Scenario-Based Design | /5 | |
| Progressive Difficulty | /5 | |
| Understanding Over Memorization | /5 | |
| Hint & Feedback Quality | /5 | |
| Transfer Potential | /5 | |
| **Average** | **/5** | |

### Action Required
- [ ] None / Low / Medium / High / Critical
```

---

## Score Interpretation

Scoring uses **sum of all 8 dimensions** (max 40) with a **per-dimension floor**.

| Sum | Rating | Action |
|-----|--------|--------|
| **33-40** | Pass | Ship it. Must excel in at least one dimension. |
| **25-32** | Needs polish | Close — fix the weakest dimensions. |
| **17-24** | Needs work | Significant gaps across multiple dimensions. |
| **8-16** | Rewrite | Fundamentally broken. Start over. |

This numeric rubric is separate from the binary per-track deterministic gates
(structural, citation, Ukrainian checks): those gates pass or fail outright,
while the rubric scores a module 1-5 per dimension. Both must be satisfied
independently.

### Scoring Tool

```bash
.venv/bin/python scripts/score_module.py 4 5 4 4 5 4 4 4          # interactive
.venv/bin/python scripts/score_module.py 4 5 4 4 5 4 4 4 --json   # machine-readable
echo "4 5 4 4 5 4 4 4" | .venv/bin/python scripts/score_module.py -  # stdin
.venv/bin/python scripts/check_citations.py src/content/docs/ai/foundations/module-1.1-what-is-ai.md
```

Dimension order: D1 Outcomes, D2 Scaffolding, D3 Active Learning, D4 Real-World, D5 Assessment, D6 Cognitive Load, D7 Engagement, D8 Practitioner Depth.

`score_module.py` is a standalone manual scorer for one module at a time. It
is not currently invoked by the runtime pipelines (v1 defines the path but
does not call it; v4 reads scalar scores and gaps via `local_api.build_quality_scores`), and nothing here
implies a corpus-wide rescore.

---

## Line Count Policy

Visual aids supplement explanation and must serve the taught outcomes; they do not replace reasoning or adequate coverage. Line counts, including the prose/visual split, are diagnostics. Judge completeness against the researched scope and outcome map, never a count-only pass or failure.

---

## Threshold for "Passing"

A module passes the quality bar when **both** conditions are met:

1. **Every dimension >= 4** — a score of 3 or below in ANY dimension is an automatic fail, regardless of sum. Every dimension matters equally. You cannot compensate for weak real-world connection with strong quizzes.

2. **Sum >= 33 out of 40** — all 4s (sum=32) is not enough. At least one dimension must be at 5, meaning the module excels somewhere, not just meets the bar everywhere.

A module that scores 3-5-5-5-5-5-5-5 (sum=38) **fails** — the floor is violated.
A module that scores 4-4-4-4-4-4-4-4 (sum=32) **fails** — it needs to excel somewhere.
