# #388 Module Rewriter — Teaching-First Brief Addendum
Configured body-word budget for THIS module: {{BODY_WORDS_TARGET}}. A declared per-module budget, when dispatch supplies one, is a planning and reporting signal only: the verifier reports it and never gates on it. This prompt does not change any executable check or acceptance state.

This addendum is layered on top of `scripts/prompts/module-writer.md`. It is binding for all #388 site-wide rewrite dispatches. The protections here come from the Codex architectural consult of 2026-05-01 (bridge messages #3384 and #3386); the paragraph-density thresholds that consult derived were retired as gates by #3744 and are now reviewer diagnostics.

The brief has historically optimized for visible structure and quotas (DYK count, sections, and sources). That conditioning produces choppy single-sentence prose, and the opposite fix produces padding. This addendum asks for both corrections at once.

## BALANCE: CUT PADDING AND EXPLAIN WHAT THE LEARNER NEEDS

Two failures carry equal weight, and either one makes a rewrite unacceptable:

- **Bloat**: padding, repetition, restated theses, duplicated material, off-topic background, filler transitions.
- **Under-explanation**: a term used before it is explained, a skipped reasoning step, a list where the learner needs the why, a missing worked example for a key skill, an abrupt unexplained transition.

Cut padding and repetition, AND explain every term, step and reason the learner needs, with worked examples. A cut must never remove the only explanation, example or step for a learning outcome, and every addition must serve a stated outcome. Word, paragraph, sentence and template counts are diagnostics that flag both tails (unusually short or choppy; unusually long or walled) for the reviewer. They never reject or reward a page, so do not write toward or away from a number.

## NO SOURCE H1

Starlight renders the page H1 from frontmatter `title:`. Do NOT write a `# Module X.Y: <Title>` heading anywhere in the body. The first heading after the frontmatter blockquote must be `## What You'll Be Able to Do` (or whatever the section's house standard is). A source `# ` line right after the frontmatter is flagged by the verifier (`gate_no_source_h1` looks at the first content line); one later in the body is still not allowed.

## PARAGRAPH STYLE

Write body sections as flowing instructional prose, not punchy note blocks. Let each paragraph carry a complete idea (claim, reason, example) rather than a one-line note. A single-sentence paragraph is for deliberate emphasis only and should not sit next to another one. Paragraph length is reported, not gated, so never lengthen or split paragraphs to reach a number.

## NO STACCATO RUNS

Do not create sequences of standalone transition lines, thesis lines, warning lines, or recap lines. If adjacent paragraphs are each a single short line, merge them into the surrounding explanation unless one is a heading, table row, list item, quiz option, code comment, or source entry.

## NO RESTATEMENT ACROSS H2 SECTIONS

Every core `## ` body section must contribute a **net-new** mechanism, example, comparison, or decision rule. Later sections may not restate the same thesis in different prose. If a section can be deleted without losing a concrete artifact (a command, a YAML, a worked decision-rule, an ASCII diagram, a table comparison, a quiz scenario), it is restatement padding — cut it before finalizing.

Specifically:

- **`Patterns & Anti-Patterns`, `Decision Framework`, `Senior Judgment`, `From Beginner to Senior`, `Worked Example` synthesis tails, and "best practices" closings** are allowed only if they introduce net-new criteria or examples not in the earlier teaching sections. If they would just rephrase the prior sections in more philosophical language, omit them.
- **Worked Example tails:** end the worked example at the first complete walked-through outcome. Do not append a paragraph or three of "stepping back, the lesson here is..." synthesis prose. The reader either understood the example or did not — the synthesis adds words, not understanding.
- **Theme rehashing:** scan every body paragraph before finalizing. If you find a paragraph that repeats the same engineering point made in an earlier section using different vocabulary, delete the later occurrence. The point is made; the reader does not need it again.

This rule does not ban legitimate conceptual build-up. The section is valid only if it teaches a thing the reader did not already know from the prior section. If it only paraphrases or re-emphasizes, remove it.

## SYNTHESIZE COVERAGE BULLETS

The topic coverage bullets in the dispatch brief are inputs, not an outline. Do not create one section or one paragraph per bullet. Combine related bullets into a coherent teaching arc with cause, consequence, tradeoff, and operational decision-making in the same paragraphs.

## STRUCTURE IS SECONDARY TO TEACHING FLOW

Include the sections the template requires, but do not let section counts shape the surrounding prose into checklist writing, and never invent facts, mistakes or questions to fill a count (counts are reported only). The main theory sections must read like a continuous lesson written by an expert instructor.

## PRE-FINALIZATION SCAN

Before finalizing, read the module twice as the target learner, using only the prerequisites the module states. Bloat pass: cut paragraphs that repeat an earlier point, background no outcome needs, and filler transitions. Clarity pass: find every term used before it is explained, skipped reasoning step, list that needs the why, key skill without a worked example, and abrupt transition, and fix each. Do both; finishing one pass does not excuse skipping the other.

## DEPTH AND EVIDENCE

Set depth from the topic, outcomes, assessment, and verified material. A declared budget, if any, is a planning and reporting signal: do not satisfy it with short lines, fragmented paragraphs, decorative structure, or restated content, and do not cut needed explanation to stay under it. That number is not proof of factual support, learning, or publication acceptance. If evidence cannot support the requested scope, report the shortfall in the required output rather than inventing detail or claiming completion; do not create a placeholder.

## RUNNABILITY, FABRICATION, AND PRACTICE QUESTIONS

Do NOT rely on shell aliases in runnable Bash examples. Specifically: do NOT write `alias k=kubectl` or use `k <subcommand>` (e.g., `k get`, `k describe`) inside fenced ```bash / ```sh / ```shell / ```zsh blocks. Aliases do not expand in non-interactive shells, so a learner who copies the block into a script will see `command not found`. Always use the full `kubectl` binary name in copy-paste examples. Prose like "many engineers alias kubectl to k for interactive use" is fine; running `k <cmd>` in a code block is not.

## Image-binary compatibility (lab-runnability contract)

Every `kubectl exec POD -- BIN` you write must satisfy BIN ∈ POD's image binary set. The verifier (`scripts/quality/verify_module.py` → `lab_runnability_metrics`) checks this deterministically against an allowlist of known images (it skips an image it does not know, so the rule binds regardless); the reviewer (LAB RUNNABILITY dimension (a)) checks it with citation.

Common image cheat-sheet (verified against Docker Hub overview pages):

| Image | Has wget | Has curl | Has bash | Notes |
|---|---|---|---|---|
| `nginx` (= `nginx:latest`, debian-slim) | ✗ | ✗ | ✗ | has `sh`, `cat`, `head`, `tail`, `grep`, `nginx` |
| `nginx:alpine` | ✓ (busybox) | ✗ | ✗ | alpine base; busybox provides wget by default |
| `busybox` | ✓ | ✗ | ✗ | wget, sh, ash, ls, cat, grep, find, nc |
| `alpine` | ✓ (busybox) | ✗ | ✗ | + `apk` package manager |
| `curlimages/curl` | ✗ | ✓ | ✗ | purpose-built — `curl`, `sh` |
| `debian:bookworm-slim` | ✗ | ✗ | ✓ | bash present; wget/curl require `apt install` |
| `nicolaka/netshoot` | ✓ | ✓ | ✓ | network debugging toolkit — wget, curl, dig, tcpdump |
| `python:3.12-slim` | ✗ | ✗ | ✓ | `python3`, `pip` |

If your lab needs `kubectl exec POD -- wget ...`, choose `nginx:alpine` over `nginx`. If your lab needs `kubectl exec POD -- curl ...` and the pod should also serve HTTP, choose `nginx:alpine` (no curl) + use `wget` instead, or use `curlimages/curl` + `--command -- sleep 3600` if the pod doesn't need to serve. Never write `--image=nginx` followed by an exec wget/curl — this is the exact bug #1257 shipped with and #1229 precedent.

Reference: `docs/agent-matrix/calibration-2026-05-19-review-lane.md` § 4 (the #1257 anatomy context).

Do NOT invent business incidents, client stories, anonymized companies, or "war story" anecdotes. A scenario is allowed only if (a) it is clearly labeled hypothetical with a `Hypothetical scenario:` or `Exercise scenario:` prefix, OR (b) it is a sourced real incident with enough specific detail to verify against the cited source. Do not imply an event happened with phrasing like "a payments company once...", "a team I worked with...", "a customer reported...", "War story:..." unless the incident is real and sourced. The incident-dedup gate only catches catalog matches; this rule catches the rest.

For practice-question / mock-exam modules, preserve exam-style MCQ structure. Each question must include four visible answer options labeled `1-4` or `A-D` (visible in the rendered question, NOT hidden in `<details>`), followed by answer reasoning that explains why the correct option is correct AND why each distractor is wrong. The reasoning may live in `<details>` blocks; the numbered options must remain visible.

## VERIFICATION (blocking gates vs reported diagnostics)

The verifier (`scripts/quality/verify_module.py`, `gate_results`) computes these **blocking gate keys**. Its output, not this summary, decides whether each one passed. Several gates are narrow heuristics, so a pass does not show that this brief's rules were followed, and a rule in this brief binds even where its gate would not fire. All gates must pass before commit:

1. `gate_no_source_h1`: see NO SOURCE H1 above.
2. `structure_sections_present`, `structure_order_correct`: section presence and order. Read the verifier's output for these two; `module-writer.md` is the authoring rule.
3. `structure_quiz_answers_have_details`: every quiz item carries a `<details>` answer block. The verifier checks presence only; the answer must still explain why, not just name the fix.
4. `sources_all_reachable`: no link under the Sources heading is a 404 or fetch failure (not computed under `--skip-source-check`; a page with no links passes this gate).
5. `anti_leak`: leaked tokens, emojis and the number 47.
6. `runnable_no_kubectl_alias`: the alias rule under RUNNABILITY.
7. `lab_image_binary_match`: the image-binary compatibility section.
8. `anti_fabrication_no_unsourced_anecdote`: the unsourced-anecdote rule.
9. `practice_mcq_four_options_with_distractors`: the practice-question rule (practice-question modules only).
10. `outcomes_aligned`: every Learning Outcome bullet must be taught in a core section and assessed by a quiz item or lab task. The verifier checks this by key-term overlap, so it is a heuristic and not proof that the outcome is taught.

Content rules the verifier does not check still bind: `## Sources` is the last H2 before `## Next Module`; every source is primary/vendor documentation (bare `- https://...` or `- [title](https://...)`) and supports the claims it is cited for, with no minimum count; K8s 1.35+ for exam-pinned cert modules (see `module-writer.md`); runnable commands; explanatory quiz answers.

**Reported only, never a gate:** body words, mean/median words per paragraph, short-paragraph rate, consecutive-short runs, mean sentence length, the counts of Did You Know, Common Mistakes, quiz items, hands-on checkboxes and sources, the declared-budget status, and `length_attention` (words per outcome, flagged `unusually_short_for_outcomes` or `unusually_long_for_outcomes`). They flag unusually short or choppy and unusually long or walled pages for the reviewer and never reject, tier or reward. The structural template in `module-writer.md` still applies.

## TIER ROUTING

Tiers follow the verifier's blocking gates only (length and density never move a tier). Classify each `revision_pending: true` module:

- **T0** — no blocking gate fails. Action: clear the `revision_pending: true` flag. No content change.
- **T1** — only one or two `structure_*` gates fail (missing section, wrong order, quiz item without `<details>`). Action: targeted structural patch; alignment must still pass post-patch.
- **T2** — only `lab_image_binary_match` fails. Action: fix the lab image/binary pairing.
- **T3** — every other failing combination, including a single `anti_leak`, sources, anecdote or alignment failure. Action: full rewrite preserving salvageable assets (labs, diagrams, code blocks, source URLs) extracted by the deterministic salvage parser.

## REPORTING

After draft, the dispatched agent must report:
- Which blocking gates passed/failed
- The reported diagnostics (mean_wpp, median_wpp, short_paragraph_rate, max_consecutive_short_run, body_words, paragraph_count, mean_sentence_length, `length_attention`) before and after, the declared-budget status, and, if the draft sits in either tail, why the page is still complete without padding
- Salvageable assets preserved (count of code blocks, diagrams, tables before/after)
- Forbidden tokens grep result
- Sources verification status (200/redirect/404 + relevance assessment)

If a blocking gate fails, revise when verified material supports the needed correction; otherwise report the failed gate and material shortfall instead of claiming completion. The orchestrator's verifier re-checks before commit. This prompt-level honesty exception does not create a new machine-enforced publication guard.
