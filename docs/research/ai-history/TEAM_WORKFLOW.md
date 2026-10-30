# AI History Team Workflow

This is a living operating document for the AI History book. Update it when the team learns a better practice. Do not treat it as frozen policy.

## Operating Principle

Honesty over output is the highest rule. The team should still strive for the intended 4,000-7,000 word range when the subject can support it, but expansion must come from verified evidence, not filler. Agents must not invent scenes, dialogue, institutional motives, deployment numbers, hardware details, or causal links to satisfy a word target.

## Roles

- Human editor: sets ambition and book-level direction, resolves material scope or taste disagreements, and spot-reads within available time. Record the material actually read and any decisions; never infer a whole-chapter read or a human verdict.
- GPT-6.1 Sol: owns the verified factual and conceptual spine, chapter contract, evidence boundaries and author-side semantic check of the prose and its qualifiers.
- GPT-6.1 Terra: writes and revises clear prose within the verified spine and anchored capacity plan.
- Claude Opus 5.5: independently challenges eligible OpenAI-authored work, using separate fresh contexts for the mandatory source-fidelity and prose-quality judgments. Both contexts require the relevant source material, contract and exact prose revision.

Sol and Terra are one author family; Sol's semantic check is author QA, not independent review. The two Opus contexts share a reviewer family: this provides two-family, not three-family, diversity. When #3719's policy PR #3720 has been independently reviewed and merged, it explicitly replaces the historical requirement that the source-fidelity and prose-quality reviewers also be from different families from each other, using the models the user permits; this is not evidence of equivalent empirical quality. Sonnet, Astra, Fable and a third-family route are not authorized by this workflow.

Authorship is assessed by family: all Claude models share the Claude family; Sol, Terra and earlier Codex models share the OpenAI family. For each review, record the families that authored the retained contract and prose, and assign a reviewer outside every family that authored the material being reviewed. For these Opus stages, retained Claude-authored material is ineligible for Opus review; Claude-authored, mixed-family and unknown-provenance material stays blocked under #2288 pending an explicit eligible review plan. Preserve good content and provenance: rewriting or relabeling does not erase authorship. Do not infer a third-family grant.

When #3719's policy PR #3720 has been independently reviewed and merged, the former human final pass as a full-chapter prerequisite is replaced by editorial direction and recorded spot reading. Material unresolved scope or taste choices still require the user's decision. A feedback platform or recurring digest is not a gate. This policy change clears no legacy chapter or pilot, resets no spent invocation count, and does not change the separate canonical whole-page source/editorial audit, applicable execution, publication or lead gates.

Agents should help each other by naming gaps plainly. A useful refusal or downgrade is better than a confident but unsupported expansion.

## Chapter Lifecycle

### 0. GitOps Coordination: One Branch, One PR, One Phase

To prevent merge conflicts, keep cross-family reviews isolated, and protect `main`, all agents must strictly follow the "One Branch, One PR, One Phase" model:
- **Research Phase PR:** Use a fresh branch from `origin/main`; complete the contract and extract real anchors. Sol checks anchors as author QA; an eligible independent Opus context verifies capacity-plan anchors, research gaps and prose capacity. Both must be green for the research deliverable; contract approval alone does not unlock prose. Never fabricate historical data or page numbers.
- **Prose Phase PR:** Once the research PR is merged and the chapter is prose-ready, use a new branch. Draft within the approved Prose Capacity Plan without padding. Separate source-fidelity and prose-quality reviews at the exact prose revision are required before merge.
- **NEVER** use massive batch PRs or long-lived epic branches.

### 1. Research Contract

Create or fill the standard chapter files:

- `brief.md`
- `sources.md`
- `timeline.md`
- `people.md`
- `infrastructure-log.md`
- `scene-sketches.md`
- `open-questions.md`
- `status.yaml`

The contract must include:

- thesis and scope
- boundary contract for what not to overclaim
- primary and secondary source table
- scene-level claim table with Green/Yellow/Red status
- timeline and people map
- infrastructure constraints
- open questions
- a `## Prose Capacity Plan` section in `brief.md` (see capacity-plan gate below)

Research-contract approval means the structure and source plan are good enough to continue research. It does not mean prose drafting may begin.

#### Prose Capacity Plan gate

Every `brief.md` must contain a `## Prose Capacity Plan` section. The plan is a contract for what the chapter is *allowed* to spend words on, not a wishlist:

- Each evidence layer is a bullet of the form `N-M words: <topic>` and must reference at least one specific scene from `scene-sketches.md` and at least one anchored entry in `sources.md` (page number, section, or stable identifier — not just the source title).
- Layer budgets must reflect evidence depth, not equal splits. A scene with 3 page anchors carries more words than a scene with 1.
- Sum of layer budgets is the chapter's allowed range. Writers cannot land outside it.
- The total range must match one of the Word Count Discipline labels (`4k-7k supported`, `4k-7k stretch`, `3k-5k likely`, `2k-4k natural`, `short chapter recommended`).
- The plan ends with a one-line honesty close: "If the verified evidence runs out, cap the chapter."

A plan whose bullets reference no `sources.md` page anchors is a *templated plan*, not an anchored plan. Templated plans pass `capacity_plan_drafted` but do not unlock prose drafting. See `chapters/ch-24-the-math-that-waited-for-the-machine/brief.md` for the canonical anchored-plan example.

### 2. Research Gap Analysis

After research-contract approval, request or create a gap analysis before prose readiness. The gap analysis should answer:

- Which claims remain Yellow or Red?
- Which page, section, figure, table, or archival anchors are missing?
- Which sources are primary, secondary, tertiary, or merely convenient?
- Which narrative scenes are strong enough to draft?
- Which scenes are too thin or speculative?
- What word count is naturally supported by verified evidence?
- What would be required to reach 4,000-7,000 words without bloat?
- Which chapter ambitions should be reduced?
- Which missing sources need further research or an editor's scope decision?

Gap analysis should be concrete. "Need more sources" is weak. "Need Pearl 1986 page anchor for local propagation in singly connected networks" is useful.

### 3. Anchor Extraction

Before prose readiness, extract exact anchors for high-value claims:

- page numbers for books and PDFs
- section names for HTML sources
- theorem, figure, table, or equation identifiers where useful
- DOI, stable URL, archival URL, or bibliographic identifier

Do not upgrade a claim to Green just because a source is famous. Upgrade it only when the specific claim is anchored.

### 4. Prose-Readiness Review

Ask a reviewer outside all families that authored the reviewed material to review the full contract plus gap analysis, including capacity-plan anchors. Record retained contract and prose author families for the assignment. The expected verdicts are:

- `READY_TO_DRAFT`: page anchors and gaps are sufficient for a faithful chapter.
- `READY_TO_DRAFT_WITH_CAP`: draft, but cap the word count below the target.
- `NEEDS_ANCHORS`: source list is good, but page/section anchors are missing.
- `NEEDS_RESEARCH`: source list or scope is inadequate.
- `SCOPE_DOWN`: the chapter should be shorter or narrower.

Only `READY_TO_DRAFT` and `READY_TO_DRAFT_WITH_CAP` unlock prose drafting.

### 5. Drafting and author-side meaning check

Sol prepares the verified factual/conceptual spine and Terra turns it into readable prose. Sol then checks the changed claims, attribution, tense and qualifications against the anchored sources and produces an exact-prose-revision material-claim inventory with the owning review; correct mismatches before independent review. Revisions follow the source-backed capacity plan, not a word-filling quota.

**Strict source rule (applies throughout drafting):**

> Use only the provided contract and claim matrix. If evidence is missing for a scene, leave the scene thin rather than filling it. Do not add sources, do not introduce new page anchors, do not upgrade Yellow claims, do not invent examples or institutional details, and do not expand beyond the approved Prose Capacity Plan. If you can't anchor a claim, weaken the claim — never invent a source.

The expansion budget is for the layers the contract's Prose Capacity Plan named: technical density, infrastructure detail, anchored biographical scenes, conflict notes. Not for generic textbook explanation, repeated summary, modern hindsight, or unanchored deployment scale.

If a chapter cannot honestly reach the cap, write the natural chapter length and document why. The target is quality, not padding.

The executable verifier's 5,000-word default and any conflict with a chapter cap remain unresolved under #2274. This workflow does not bypass or alter a runtime gate; reconcile the mismatch through separately reviewed policy and tooling work.

### 6. Source-Fidelity Review (independent Opus context)

An independent fresh Opus 5.5 context, outside all families that authored the reviewed material, reviews the exact prose revision and its material-claim inventory against accessible source material and the anchored contract. The reviewer independently checks inventory completeness against the prose; a missing or incomplete inventory makes the judgment incomplete:

- factual overclaims vs the contract's anchored claims
- unsupported scenes / unanchored beats
- source misuse — anchors that don't match what the prose attributes
- Yellow/Red discipline (Yellow hedged, Red absent)
- boundary contract held (no later-chapter forward-references creeping in)
- whether prose outpaced the research contract

Verify the actual source passages and locators, not just URLs or titles. Unavailable source material leaves the affected judgment incomplete. Record reviewer identity, exact prose/source revisions, findings and verdict: `READY_TO_MERGE` / `NEEDS_FIX_AND_MERGE` / `NEEDS_REWRITE`.

### 7. Prose-Quality Review (separate independent Opus context)

A separate fresh Opus 5.5 context, outside all families that authored the reviewed material, reviews the same exact prose revision with its contract and supporting sources. Missing contract or needed source material makes the judgment incomplete. It checks:

- narrative coherence scene-to-scene
- pacing, sentence variety, paragraph rhythm
- whether the chapter transitions and part-level arc work
- word-count inflation vs cap discipline
- book-level continuity

Record its identity, exact prose/source bindings, findings and verdict separately from source fidelity. Neither context receives the other's findings or verdict before its own independent verdict. They are separate judgments, not different reviewer families; do not describe them as three-family review. Preserve prior failed or incomplete reviews and existing spent invocation counts across revisions.

Source-fidelity and prose-quality contexts share the existing whole-page source/editorial invocation counter; purpose, context and phase labels do not reset it. PR review counters remain separate. Each paired cycle consumes two whole-page calls; the usual five-call ceiling allows at most two full pairs plus one call. Exhaustion grants no clearance; a further invocation needs an explicit user grant unless an existing larger grant covers it. Follow `agents_extensions/shared/skills/review-loop/SKILL.md` for applicable limits and spent calls.

Do not merge prose on tests alone. Both review steps (6 and 7) must approve the same unchanged final prose/source revision with material findings resolved. Any prose or source-binding change invalidates both verdicts; both contexts must review the new exact revision within the existing shared budget.

### 8. Human editorial direction and spot reading

The editor sets direction and decides material unresolved scope or taste disagreements, including:

- whether the chapter's natural length is acceptable
- whether to source more material or scope down
- whether tone and pacing match the book
- whether unresolved questions can remain as future work

The editor chooses what to spot-read; agents may suggest material but not restrict that choice. Record the actual chapter, revision, sections, date and any decision on the owning issue or PR; unread material remains recorded as unread. A full human read of every chapter is not required; never invent human acceptance or reader response. A pending material scope or taste referral blocks `accepted` and merge, and the chapter stays in `prose_review`. Neither author nor reviewer decides for the editor. Record the referral and editor's decision with chapter, revision and date on the owning issue or PR.

## Status Terms

- `researching`: contract or anchors are still incomplete.
- `capacity_plan_drafted`: brief.md has a Prose Capacity Plan section but layers do not yet reference sources.md page anchors. Does not unlock drafting.
- `capacity_plan_anchored`: every plan layer references at least one page anchor in sources.md. Eligible for `research_contract_approved` review.
- `research_contract_approved`: reviewer approved the research plan, but prose is not unlocked.
- `gap_analysis_requested`: reviewer has been asked to identify missing anchors and weak scenes.
- `anchors_in_progress`: exact page/section anchors are being extracted.
- `prose_ready`: reviewer says drafting may begin.
- `drafting`: prose is being written.
- `prose_review`: draft is under cross-family review.
- `accepted`: applicable source-fidelity and prose-quality reviews have cleared the exact chapter revision and no material scope or taste referral to the editor remains undecided. This workflow status is not canonical full-page acceptance or a publication unlock; applicable execution, publication and lead gates remain separately required. Record editorial decisions and actual spot reads without inferring a full human read.

Labels recorded before this policy used earlier definitions and are not re-evidenced by it; reconciliation remains under #2288.

A drafted chapter (prose already exists) whose `brief.md` plan is templated, not anchored, regresses to `capacity_plan_drafted` until sources.md is upgraded. The existing prose stays on disk; it just cannot be cited as "accepted" while the contract behind it is incomplete.

## Word Count Discipline

The default ambition is 4,000-7,000 words for major chapters, but agents must not min-max by either padding to the target or prematurely shrinking the scope. Use a two-number plan:

- `core range`: what the verified evidence can support today.
- `stretch range`: what the chapter could support if specific missing evidence is found.

Expansion must follow an evidence ladder:

- primary-source anchors
- deployment or institutional detail
- infrastructure and hardware constraints
- competing interpretations or priority disputes
- consequences and later reception
- clear explanation of technical ideas tied to historical sources

Expansion must not come from:

- generic textbook explanation unrelated to the historical event
- invented lab scenes or motives
- repeated summary of the same claim
- modern hindsight that the chapter's sources do not support
- unanchored deployment scale, hardware, or business impact

Use these labels in briefs and gap analyses:

- `4k-7k supported`: verified sources already support a long narrative without padding.
- `4k-7k stretch`: possible if named gaps are filled.
- `3k-5k likely`: chapter has enough evidence, but some scenes should stay compact.
- `2k-4k natural`: conceptually important but structurally compact.
- `short chapter recommended`: expansion would require filler or unrelated material.

When in doubt, do not simply lower the target. First identify the missing evidence that could support responsible expansion. Lower the target only after the team agrees the missing layer is unavailable, out of scope, or not worth the narrative cost.

## Review Request Template

Use this shape when asking for gap analysis or prose readiness:

```text
Please review Chapter N as [gap analysis / prose-readiness review].

Focus files:
- docs/research/ai-history/chapters/ch-XX-.../brief.md
- docs/research/ai-history/chapters/ch-XX-.../sources.md
- docs/research/ai-history/chapters/ch-XX-.../open-questions.md

Questions:
1. Which claims remain Yellow/Red and why?
2. Which exact page/section anchors are required before prose?
3. Which scenes are strong enough to draft, and which are thin?
4. What natural word-count range is supported by verified evidence?
5. What specific evidence would let this reach 4,000-7,000 words without bloat?
6. What should another agent or the human editor help source?

Please post a structured comment with concrete gaps and a verdict:
- READY_TO_DRAFT
- READY_TO_DRAFT_WITH_CAP
- NEEDS_ANCHORS
- NEEDS_RESEARCH
- SCOPE_DOWN
```

## Change Rule

This document should evolve through small PRs. When the team discovers a repeatable failure mode, add a rule here and cite the chapter or PR that exposed it.
