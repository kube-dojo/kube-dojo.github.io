# Review Protocol

## Reviewer Assignment (cross-family rule)

The [review and coverage contract](review-contract.md) defines current roles,
refusal states and evidence requirements. Grok/Gemini/Claude are the primary
pool; Muse/DeepSeek are additional routes. Use live model-family resolution and
health, not the historical examples below, to choose an executable reviewer.
Fresh same-family red-team checks are useful and must be labeled honestly;
they do not substitute for an explicitly required independent review.

Every PR review must come from a **different model family** than the author.

**Families:**
- **Claude** (Anthropic) — opus-4-x, sonnet-4-x, haiku-4-x
- **Codex / GPT** (OpenAI) — gpt-5-codex, gpt-5
- **Gemini** (Google) — gemini-3.x, gemini-2.x

**Why:** same-family self-review shares failure modes. A Claude reviewer misses the same bugs a Claude author wrote because both models share training corpus, hallucination patterns, and blind spots. Cross-family review catches what single-family review cannot.

**Default pairings:**
- Claude-authored → Codex reviewer (Codex has been more rigorous on content batches; see STATUS.md 2026-04-23 data point on PR #350)
- Codex-authored → Claude or Gemini reviewer
- Gemini-authored → Claude or Codex reviewer

**Never:** Claude reviewing Claude, Codex reviewing Codex, Gemini reviewing Gemini — including sub-model variants (opus reviewing sonnet still counts as Claude→Claude).

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
1. Verdict: APPROVE / NEEDS CHANGES / REJECT
2. Must-Fix findings in the mandatory format
3. Nits in the same format when useful
4. Concise focus on what needs changing

## Universal Review Loop

Any orchestrator can run the review loop the same way:

1. Run the reviewer with this protocol prepended to the task.
2. Verify the review text with `.venv/bin/python scripts/verify_review.py --pr <N> --branch <ref>` or pass `--from-pr` to fetch the latest PR comment directly.
3. Treat `quote_missing` as hallucinated evidence. Treat `line_mismatch` as a citation accuracy problem. `verified` means the quoted code exists at the cited location.
4. Optionally post the verifier summary with `--post-comment`.
5. Decide manually. The verifier is passive evidence-checking only; it warns, but it does not block merge automatically.
