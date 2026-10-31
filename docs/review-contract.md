# Review and teaching coverage contract

Owner: accountable change lead. Delivery: #2274, #3741–#3746. This contract
defines review meaning; the live installed catalog defines executable routes.

## Review roles and reviewer pool

Grok (xAI), Gemini (Google) and Claude (Anthropic) are the primary independent
reviewer pool. Muse (Meta) and DeepSeek are additional options. Resolve the
actual model family, harness, health and quota before dispatch; a product name
or API endpoint is not an independent family. Never silently substitute models.
Use one suitable independent reviewer per bounded change, not every provider.

A fresh same-family red-team review is useful additional adversarial evidence.
Label it `same_family_red_team`; it cannot be reported as cross-family review.
The independent merge review remains outside the author's actual model family,
unless the user explicitly authorizes a documented scoped exception. Security,
privacy, permission, admission and destructive-operation changes retain the
independent gate. Optional nits do not justify another round after valid approval.

The lead may exclude a model from a review role after documented material
misses, unsupported findings or evidence-integrity failures. Record the model,
role/scope, evidence, reason and reassessment condition. A broken route, timeout,
quota or authentication failure establishes availability/completion limits,
not a model-quality verdict. No brand receives automatic approval or exclusion.

## Evidence and decisions

Freeze scope, author/reviewer identities and families, actual model/harness,
review kind, exact commit/page digest, prior findings and remaining invocation
budget. Preserve incomplete/negative runs; neither a new branch nor another
provider resets a stream's allowance. Separate supplied evidence from checks
the reviewer actually performed. A read count proves transport, not correctness.

`changes_required` means a supported material defect must be fixed.
`blocked` means required evidence is missing, stale, incomplete or inconclusive.
`approve_with_nits` permits delivery with clearly optional follow-up suggestions.
Every material finding needs its location, actual quote, consequence, evidence
and proposed remedy. An uncertain finding is a question until substantiated.
Personal preferences and equally valid alternatives are not material blockers.

For tooling, the canonical finding envelope is:

```json
{"verdict":"APPROVE","head":"<full commit SHA>","findings":[]}
```

Nonempty findings use `id`, `severity`, `path`, `line`, `quote`, `why`, `fix`.
An unrecognized payload is not an empty approval. Quote verification validates
the cited text, not the finding's semantic correctness or reviewer independence.

## Research basis and limits

- [CMU constructive alignment](https://www.cmu.edu/teaching/assessment/basics/alignment.html)
  connects outcomes, instruction and assessment; require an explicit mapping.
- [IES practice guide](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) recommends
  worked examples with problem solving, integrated representations, retrieval
  and explanatory questions; require appropriate opportunities, not decoration.
- [Freeman et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4060654/)
  synthesizes undergraduate STEM active-learning studies. This informs activity
  design; it does not measure this curriculum's effect on its readers.

These sources do not establish a universal module length, trivia quota or
passing rubric number. Choosing evidence-backed coverage over a default word
floor is our design inference. Actual learner-effect claims need learner data.

## Teaching coverage and acceptance

Before authoring, state learner prerequisites, intended scope, essential topic
concepts, source basis and deliberate exclusions. Before approval, map every
outcome to actual teaching, a worked explanation/example, suitable learner
practice and an assessment/verification opportunity. A missing element needs
an explicit page-kind justification; it cannot vanish behind a high average.
Review for mechanisms, decisions, misconceptions, failure recovery, transfer,
repetition, unsupported specificity and abrupt unexplained transitions.

Use exact candidate-text evidence for coverage judgments. Counted headings,
keywords, links, words or generated output cannot establish adequate coverage.
Concise material may pass; long material with unsupported or untaught outcomes
must not. Length/density/template counts are diagnostics, not a default quota.
Explicit per-page workload constraints need their rationale and scope recorded.
Do not pad, manufacture numbered facts or repeat prose to satisfy a metric.

The canonical module rubric remains all eight D1–D8 scores >=4 and total>=33/40;
applicable lab review remains all five L1–L5 scores>=4 and total>=21/25.
Scalar-only legacy review is insufficient for these judgments. Evidence-backed
editorial approval is provisional until required claim/source checks complete.
Real examples need verified versions, expected/observed labels and applicable
execution/cleanup evidence. A source-fetch failure is unknown, not proof false.

Scoped code/content delivery and whole-page acceptance are different decisions.
Keep source, editorial, practice, deployment and lead acceptance separate and
revision-bound. Record published corrections as work without restamping old
acceptance. Book-specific source/editor/cap rules retain their separate scope.

## Prevention and measurement

Keep offline regression cases for incomplete rubric/coverage, padded but
unsupported material, concise supported material, malformed/stale reviews,
later delivery comments, substituted models and publication without acceptance.
Run them in normal CI without provider credentials or inference calls.
Assess reviewers on representative blinded defects and clean controls; record
material misses, false positives, completion, evidence quality and latency.
One small calibration or successful page review does not certify all task types.
