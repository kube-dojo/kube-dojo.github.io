# Review Protocol

## Reviewer Assignment (cross-family rule)

The [review and coverage contract](review-contract.md) defines current roles,
refusal states and evidence requirements. Grok/Gemini/Claude are the primary
pool; Muse/DeepSeek are additional routes. Use live model-family resolution and
health, not the historical examples below, to choose an executable reviewer.
Fresh same-family red-team checks are useful and must be labeled honestly;
they do not substitute for an explicitly required independent review.

Every PR review must come from a **different model family** than the author.

Families include Anthropic/Claude, OpenAI/Codex, Google/Gemini, xAI/Grok,
Meta/Muse and DeepSeek. Resolve actual identities from the live route, not
historical model aliases. Choose a healthy primary-pool reviewer outside the
author's family, or a suitable additional route from the contract. Codex may
independently review a non-OpenAI author. Diversity is a defense against shared
mistakes, not proof of correctness. Same-family work is permitted as explicitly
labeled red-team evidence; never count it as the independent merge review.

**Operator workflow (not automated enforcement).** `scripts/ab ask-{codex,gemini,claude}` with `--review` records the author family via `--from` and targets the reviewer family via the subcommand chosen — but the CLI does not currently reject a same-family invocation. `scripts/verify_review.py` is passive quote/line verification only. Family separation today is enforced by **convention and reviewer discipline**, not by a hard CLI check. Pick an `ask-*` subcommand whose family differs from `--from`; if a real guard is added later, this section can be renamed back to "Enforcement."

## Prompt Context

PROJECT CONTEXT:
KubeDojo is a free, open-source Kubernetes curriculum with 700+ modules:
- Certification tracks: CKA, CKAD, CKS, KCNA, KCSA (exam-aligned, K8s 1.35)
- Platform Engineering: SRE, GitOps, DevSecOps, MLOps
- On-Premises Kubernetes, Cloud, Linux, and AI tracks
- Quality standard: learning outcomes, inline prompts, scenario-based quizzes

REVIEW RULES:
1. DIFF vs FILE: a diff only shows what changed. Lines absent from the diff may still exist in the file.
   Before claiming something is missing, verify absence in the actual branch file, not just the diff.
2. Mandatory format for every must-fix finding:
   FINDING: <one-line summary>
   FILE:LINE: <path>:<N>
   CURRENT CODE:
     <verbatim quote from the branch>
   WHY: <specific failure mode>
   FIX: <concrete change>
3. "Missing" claims require proof of absence. If you cannot quote the file or show a search proving absence, delete the finding or demote it to a question.
4. Do not invent line numbers. Every cited line must exist on the reviewed branch.
5. Self-check before submit: if the code might exist outside the diff, read/search the file before reporting.
6. cite verify_word output before asserting word/form-existence claims or spelling/declension rules. Stylistic and naturalness judgments (e.g., 'reads as translationese' or 'awkward') do not require verification.

OUTPUT:
1. Canonical verdict: APPROVE / APPROVE_WITH_NITS / NEEDS_CHANGES / BLOCKED, using the contract's JSON envelope and required companion provenance. Legacy REJECT/FAIL is non-approval and needs an explicit material-defect or evidence-gap reason.
2. Must-Fix findings in the mandatory format
3. Nits in the same format when useful
4. Concise focus on what needs changing

## Universal Review Loop

Any orchestrator can run the review loop the same way:

1. Run the reviewer with this protocol prepended to the task.
2. Select the actual review explicitly and pass it on stdin to `.venv/bin/python scripts/verify_review.py --pr <N> --branch <reviewed-ref>`. Canonical JSON uses `verdict` (`APPROVE`, `APPROVE_WITH_NITS`, or `NEEDS_CHANGES`), full `head` SHA, and `findings` containing `id`, `severity`, relative `path`, positive `line`, exact `quote`, `why`, and `fix`. An empty `findings` list requires an approval verdict. Legacy FINDING blocks remain supported; Markdown findings without exact evidence are reported as unsupported, not verified. The legacy `--from-pr` still selects the last non-verifier comment; it does not establish comment identity or reviewed revision.
3. Treat `quote_missing` as hallucinated evidence. Treat `line_mismatch` as a citation accuracy problem. `verified` means the quoted code exists at the cited location.
4. Optionally post the verifier summary with `--post-comment`.
5. Decide manually. The verifier is passive evidence-checking only; it warns, but it does not block merge automatically.
