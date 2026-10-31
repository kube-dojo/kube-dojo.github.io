# Review and teaching coverage contract

Owner: accountable change lead. Delivery: #2274, #3741–#3746. This contract
defines review meaning; the live installed catalog defines executable routes.

## Review roles and reviewer pool

Grok (xAI), Gemini (Google) and Claude (Anthropic) are the primary independent
reviewer pool. Muse (Meta) and DeepSeek are additional options. Resolve the
actual model family, harness, health and quota before dispatch; a product name
or API endpoint is not an independent family. Never silently substitute models.
Use one suitable independent reviewer per bounded change, not every provider.
Codex may independently review non-OpenAI authors; it is not independent of an
OpenAI author. The primary pool is a preference, not proof of review quality.

A fresh same-family red-team review is useful additional adversarial evidence.
Label it `same_family_red_team`; it cannot be reported as cross-family review.
The independent merge review remains outside the author's actual model family,
For low-risk scoped delivery only, explicit written user authorization may defer
that gate: record the exact scope/revision, authorization link and expiry at
delivery; keep final acceptance pending and never label it independent review.
This exception does not satisfy the gate for security, privacy, permission,
admission or destructive-operation changes. Optional nits do not justify another
round after valid approval.

The lead may exclude a model from a review role after documented material
misses, unsupported findings or evidence-integrity failures. Record the model,
role/scope, evidence, reason and reassessment condition. Substantiate a critical
miss/integrity failure, or a repeated material error pattern, using reproducible
checks or independent adjudication. A negative review is not grounds to exclude
its reviewer. Exclusion is prospective; existing findings require separate
adjudication and remain unresolved meanwhile. A broken route, timeout,
quota or authentication failure establishes availability/completion limits,
not a model-quality verdict. No brand receives automatic approval or exclusion.

## Evidence and decisions

Freeze scope, author/reviewer identities and families, actual model/harness,
review kind, exact commit/page digest, prior findings and remaining invocation
budget. Preserve incomplete/negative runs; neither a new branch nor another
provider resets a stream's allowance. Separate supplied evidence from checks
the reviewer actually performed. A read count proves transport, not correctness.

Canonical verdicts are `APPROVE`, `APPROVE_WITH_NITS`, `NEEDS_CHANGES`, `BLOCKED`.
They mean requirements met, optional follow-up only, material changes required,
or required evidence missing/stale/inconclusive, respectively. Run failures,
unavailability and incomplete output are completion statuses, never approval.
Legacy `REJECT`/`FAIL` mean changes required or blocked with the reason recorded;
they are not canonical approval payloads. Narrative wording cannot override JSON.
Every material finding needs its location, actual quote, consequence, evidence
and proposed remedy. An uncertain finding is a question until substantiated.
Personal preferences and equally valid alternatives are not material blockers.

For tooling, the canonical finding envelope is:

```json
{"verdict":"APPROVE","head":"<full commit SHA>","findings":[]}
```

Nonempty findings use `id`, `severity`, `path`, `line`, `quote`, `why`, `fix`.
Independent approval also requires a companion record: author/reviewer identity
and actual family; provider/model/harness and effective-route evidence; review
kind/scope, commit/page digest, complete run identity, performed versus supplied
checks, limits and invocation budget. Missing provenance blocks the independent
gate. The finding envelope alone is not a merge approval or acceptance receipt.
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
outcome to teaching and suitable practice/assessment evidence; our project design
inference is to use worked explanations/examples where appropriate. Outcome
clusters may share examples and assessments; do not manufacture one per bullet.
The independent reviewer checks the topic inventory against relevant primary
references/blueprints and audience needs, not only the author's chosen outcomes.
Material omissions require justified scope limits or changes, despite high scores.
Review for mechanisms, decisions, misconceptions, failure recovery, transfer,
repetition, unsupported specificity and abrupt unexplained transitions.

Modules require taught outcomes and practice/assessment mapping; labs may link
prior theory but require executable verification/cleanup; navigation hubs may
omit theory/quizzes/labs but require audience/route/link checks; references and
release notes may omit exercises but require scoped source/version checks.
Book chapters follow their separate narrative/source/editor workflow. Record
omission grounds before authoring; the independent reviewer must accept them.
Unjustified/unaccepted omissions are `NEEDS_CHANGES`, not self-approved exemptions.

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
