# Reader Aids — Layout for AI History Chapters

This document defines the canonical reader-aid layout for the AI History book, established by the Chapter 1 prototype (Issue #561). Chapters 2–72 follow this template within the existing contract and review requirements.

The current book contains 73 English chapters. Chapter 73, **The Algorithmic Response**, has prose and a public-index entry but no research-contract directory. Its reader aids await that contract and the applicable source and editorial reviews below; existing prose or aids do not establish approval. References to “every chapter” in this layout retain the Chapters 1–72 applicability boundary until that gap is resolved under #2288. This inventory clarification does not extend Tier 2 selections or waive Tier 3's per-element adversarial approval.

## Hard rule — prose body is bit-identical to the verified draft

Reader aids are **additions**, never edits. They sit before the first prose paragraph and after the last. They never replace, abridge, or reword the existing prose body. After landing aids on a chapter, run:

```bash
git diff main -- src/content/docs/ai-history/ch-XX-*.md | grep '^-[^-]'
```

If anything returns, a prose line was deleted or modified — revert and try again.

## Layout

### Tier 1 — every chapter

These four aids land on every chapter. They serve readers who want a fast on-ramp, a roster, a calendar, or a plain-words door into specialised vocabulary.

1. **TL;DR callout** — `:::tip[In one paragraph]` Starlight aside, **≤80 words**. Visible by default. Sits immediately after the frontmatter close. Summarises the chapter's load-bearing claim, names the central figure(s) and date, and points to the historiographical correction the chapter carries (if any).
2. **Cast of characters** — `<details><summary><strong>Cast of characters</strong></summary>` collapsible. **6 rows max**. Columns: Name | Lifespan | Role. Sourced strictly from the chapter's `people.md`. Use `—` in the Lifespan column when the contract does not give dates; do not invent.
3. **Timeline** — `<details><summary><strong>Timeline (year-range)</strong></summary>` collapsible. Mermaid `timeline` directive (Mermaid 11.14, in production use across the site). Include only events listed under "In scope" in the chapter's `timeline.md`. Do **not** include excluded or forward-pointing events; those exist as boundary markers in the contract, not narrative beats.
4. **Plain-words glossary** — `<details><summary><strong>Plain-words glossary</strong></summary>` collapsible. **5–7 terms**, each with a 1–2 sentence plain-English definition. Pick terms a non-specialist would stumble on while reading the prose. Definitions must trace to the contract or to the chapter's primary sources.

### "Why this still matters today" — every chapter

Sits after the last prose paragraph.

5. **Why this still matters today** — `:::note[Why this still matters today]` Starlight aside, **≤120 words**. Bridges the chapter's content to today's practitioner-visible technology using inspected, accepted evidence. A specific named example with a supporting citation is welcome when it makes the connection clearer. Distinguish a conceptual analogy, a technical application and documented historical influence: similarity alone does not establish ancestry. Broad claims require evidence too. This is the single place forward-pointing language is permitted.

### Tier 2 — selected chapters only

These aids apply only when the topic genuinely benefits from them. Don't add them to chapters where they would be filler.

6. **The math, on demand** — `<details><summary><strong>The math, on demand</strong></summary>` collapsible. Mathematical notation, equations, derivations relevant to the chapter, listed as bullets with brief commentary. Use `$…$` inline math (the renderer accepts dollar-delimited LaTeX as a stylistic convention; see `grep '\$' <chapter>` for in-prose usage). Apply to: **Ch01, Ch04, Ch15, Ch24, Ch25, Ch27, Ch29, Ch44, Ch50, Ch55, Ch58.**
7. **Architecture sketch** — A diagram (Mermaid `flowchart`, `sequenceDiagram`, or block diagram) of the system the chapter describes. Apply to: **Ch41, Ch42, Ch49, Ch50, Ch52, Ch58.** Form to be finalised in those chapters; not part of the Ch01 prototype.

### Tier 3 — selective, by adversarial review only

These aids are *opt-in per chapter and per element*. They are not added by checklist. The author proposes; a cross-family reviewer adversarially evaluates each candidate; only the elements the reviewer approves land in prose.

8. **Inline parenthetical definition (Starlight tooltip).** Reserved for a future tooltip component. Plain HTML `<abbr title="…">` violates the bit-identity rule because it modifies the prose line. Until a non-destructive component lands (custom Astro `<Tooltip>` reading from a sidecar terms file, or equivalent), this element is **SKIPPED on every chapter**. The collapsible *Plain-words glossary* (Tier 1, item 4) covers the same job non-destructively.

9. **Pull-quote** — at most one per chapter. Render as a `:::note` callout immediately *after* the paragraph the quote comes from, with the sentence in a `>` blockquote and a 1-sentence annotation that does *new* work (provenance, stakes, intellectual lineage — not paraphrase). **Refuse if (a) no candidate sentence is genuinely quote-worthy, or (b) the prose paragraph already quotes the sentence verbatim** — duplicating it as a callout creates adjacent repetition. The Ch01 prototype skipped its pull-quote on (b): the chapter's load-bearing sentence was already quoted in-prose.

10. **Selective dense-paragraph asides** — 1-3 per chapter, **`:::tip[Plain reading]`** callout inserted immediately after the dense paragraph. Use only on paragraphs that are *symbolically* dense (mathematical formulas, derivations, abstract definitions stacked) — **not** narratively dense (history, biography, who-said-what). The aside paraphrases the *gist* in 1-3 sentences, doing work the surrounding prose does *not*. Refuse on chapters where no paragraph is genuinely dense, and refuse the *individual* aside if its commentary would only repeat the surrounding prose.

#### Tier 3 workflow — author proposes, cross-family adversary reviews

Forced Tier 3 elements produce filler. The workflow is therefore explicitly adversarial:

1. The chapter's primary author drafts a `tier3-proposal.md` in the chapter's contract directory listing each candidate as PROPOSED or SKIPPED, with insertion anchor and rationale for each PROPOSED.
2. The proposal is sent for adversarial review to a different model family (`scripts/ab ask-codex` from a Claude-authored chapter; `scripts/ab ask-claude` from a Codex- or Gemini-authored chapter), with explicit instructions to be willing to reject.
3. The reviewer returns APPROVE / REJECT (with reason) / REVISE (with suggestion) for each PROPOSED element. The response is saved to `tier3-review.md` in the same directory.
4. The author applies only APPROVE-d elements, applies the suggested revision for REVISE-d elements, and skips REJECT-ed and originally SKIPPED elements.
5. The PR body documents which Tier 3 elements landed, which were skipped, and the adversarial verdicts (one-line summary per element).

The Ch01 prototype demonstrated the workflow exactly: 5 elements proposed (1 skip + 4 candidates); Codex rejected 1 (pull-quote, on adjacent-repetition grounds), revised 1 (Venn-diagram framing for the inclusive-OR aside), approved 2, agreed with 2 skips. **2 of 5 candidates landed.** That ratio is the right calibration — Tier 3 is the place to refuse.

## Source discipline

Every claim in every aid must trace to one of:

- the chapter's `brief.md`
- the chapter's `people.md`
- the chapter's `timeline.md`
- the chapter's `sources.md`

If a fact is not in the contract, it does not appear in the aids, including the closing "Why this still matters today" aside. An independently reviewed supplemental source packet can extend the contract: record the exact claim, inspected source and locator, source class, access limits and review provenance in the chapter's research materials, and link the packet from `sources.md`. A reachable URL, a source label or an existing citation is not evidence that the proposed claim was verified. Source acceptance does not accept the resulting prose; the aid still needs a distinct editorial review for fidelity, clarity and fit. Never invent a connection or citation to supply a closing note.

When the contract conflicts (e.g. two sources disagree on a date), use the locution the chapter prose uses, or the resolution in `brief.md → Conflict Notes`. Do not promote a single-source ("Yellow") fact to a confident-sounding aid.

## Caps and constraints

| Aid | Cap |
|---|---|
| TL;DR (`:::tip[]`) | ≤80 words |
| Cast of characters | 6 rows max |
| Timeline | in-scope events only; no excluded events |
| Plain-words glossary | 5–7 terms |
| "The math, on demand" | bullets only; one-sentence commentary per equation |
| "Why this still matters today" (`:::note[]`) | ≤120 words |
| Pull-quote (`:::note[]`) | at most 1 per chapter; ≤60 words including annotation |
| Plain-reading aside (`:::tip[Plain reading]`) | 1–3 per chapter; 1–3 sentences each |

## Markdown syntax reference

```markdown
:::tip[In one paragraph]
…content…
:::

<details>
<summary><strong>Cast of characters</strong></summary>

| Name | Lifespan | Role |
|---|---|---|
| … | … | … |

</details>

<details>
<summary><strong>Timeline (1815–1864)</strong></summary>

\`\`\`mermaid
timeline
    title …
    1815 : Born …
\`\`\`

</details>

:::note[Why this still matters today]
…content…
:::
```

Inline math uses `$x^2 = x$`. The renderer treats `$…$` as a stylistic convention; see existing chapter prose (`grep '\$' src/content/docs/ai-history/ch-XX-*.md`) for live examples.

## Default visibility

- `:::tip[]` and `:::note[]` asides are **visible by default**. They are the first and last things a casual reader sees; they must work as a standalone summary.
- `<details>` blocks are **collapsed by default**. Readers expand them on demand. The chapter prose stands on its own without the aids — the aids are aids, not load-bearing content.

## Verification before commit

1. `npm run build` runs clean (0 errors, ~56s).
2. `.venv/bin/python scripts/check_site_health.py` returns 0 errors.
3. `git diff main -- src/content/docs/ai-history/ch-XX-*.md | grep '^-[^-]'` returns empty.

## Prototype reference

The Ch01 prototype (`src/content/docs/ai-history/ch-01-the-laws-of-thought.md`) is the canonical reference implementation. When in doubt about formatting, syntax, or tone, copy from there.
