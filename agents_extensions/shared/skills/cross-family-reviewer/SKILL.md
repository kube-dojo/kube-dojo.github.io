---
name: cross-family-reviewer
description: Independently review a KubeDojo PR against the current review contract and return evidence-backed findings.
---

# Cross-family Reviewer Skill

Run a rigorous PR review under [`docs/review-contract.md`](../../../docs/review-contract.md) and [`docs/review-protocol.md`](../../../docs/review-protocol.md). Independent review requires a different actual model family from the author; a fresh same-family red team is useful additional evidence and must be labeled `same_family_red_team`.

This skill describes the **review contract**. For pedagogical content scoring against the 8-dim rubric (D1-D8), layer in [[module-quality-reviewer]].

## Reviewer selection

Grok, Gemini and Claude are the primary pool; Muse and DeepSeek are additional options. Codex can independently review non-OpenAI work. Verify the actual family, model, harness, route health and quota live; never infer independence from a product or endpoint name, or silently substitute a model.

The lead may make a scoped, prospective exclusion after an independently adjudicated critical miss or integrity failure, or a reproducible pattern of material errors. Record the evidence and reassessment condition; preserve and adjudicate prior adverse findings. Timeouts, unavailable routes and quota/authentication failures are not model-quality verdicts. A negative review alone is not grounds for exclusion.

The contract permits explicitly authorized low-risk delivery with independent review deferred and final acceptance pending. High-risk security, privacy, permission, admission and destructive changes retain the independent gate. Record the scope, revision and authorization; never label a deferred or same-family review independent.

## How to run a review (R1)

1. **Pull the PR locally** (or read the diff via `gh pr diff <N>`).
2. **Read changed files in full**, not just the hunk. A diff hides surrounding-context bugs.
3. **For curriculum content**: also run [[module-quality-reviewer]] (8-dim rubric).
4. **For code**: run the relevant linter + tests (`.venv/bin/ruff check`, `npx tsc --noEmit`, `npx eslint`, `.venv/bin/pytest`, `npm test`).
5. **For workflows** (`.github/workflows/**`): `uvx zizmor --offline --strict-collection .github/` ([[.claude/rules/github-actions-security]]).
6. **For modules**: run `.venv/bin/python scripts/quality/verify_module.py <path>` and report actual output; count and density metrics do not establish teaching coverage.
7. **For lab content**: actually run the `bash`/`kubectl`/`yaml` snippets in a sandbox.
8. **Verify material citations and claims** against relevant sources. Unsupported claims need correction; fetch failures and ambiguous evidence are unknown and block the affected verification.
9. **Grep for sibling failures** — same anti-pattern likely elsewhere.
10. **Output the verdict** in the format below.

Report evidence-backed material findings and optional nits. Mark uncertain observations as questions until substantiated; do not turn preference or unverifiable claims into blockers.

## Output format

Return the canonical finding envelope and companion provenance required by `docs/review-contract.md`. Use the exact reviewed commit head or page digest and one verdict: `APPROVE`, `APPROVE_WITH_NITS`, `NEEDS_CHANGES`, or `BLOCKED`. Each finding needs its severity, path, line, actual quote, consequence and proposed fix.

Record author and reviewer families, actual model/provider/harness and effective route, scope, run identity, performed versus supplied checks, limits and remaining review budget. Preserve negative, incomplete and failed runs; changing a head or provider does not reset the stream. A failed or incomplete run is not an approval. The normal per-PR maximum is five invocations, including failures; observe any stricter task limit.

## Evidence limits

Check actual tool capabilities for this run rather than assuming web, shell, filesystem or MCP access. Verify version-specific claims and schema details from appropriate sources when available; otherwise mark them unverified for the lead. A verifier pass does not prove source truth, example execution or learner outcomes.

## Anti-patterns to flag (codebase-wide)

- Tests that mock the database when an integration target exists — favor a real DB / fixtures over mocks for boundary tests.
- Hard-coded SHAs as version pins without comment (must be `# vX.Y.Z` for Dependabot) ([[.claude/rules/github-actions-security §1]]).
- `persist-credentials: true` (default) on `actions/checkout` without a push need ([[.claude/rules/github-actions-security §3]]).
- Workflow-level `permissions:` with privileged scopes ([[.claude/rules/github-actions-security §4]]).
- Comments explaining WHAT instead of WHY.
- Dead code (unused imports, orphaned functions) — flag for cleanup before structural refactor.
- Backwards-compat shims for code you're certain is unused — delete instead.

## R2 cycle (after fix-pass)

1. Re-read the changed lines + sibling files (cleanup may have introduced new issues).
2. Re-run the applicable checks and report actual results, including source or runtime limits.
3. **Verify each R1 finding was addressed** — explicitly check off the list, don't just say "looks good".
4. Return a verdict for the new exact revision. Reassess severity from evidence, not automatically from the round number.

## When to escalate to a Decision Card

For contested NEEDS_CHANGES, the lead adjudicates the evidence or uses the decision-card process with authorized, available reviewers. Do not silently force a particular provider or add an unbudgeted invocation.

## References

- [[module-quality-reviewer]] — pedagogical 8-dim rubric for content reviews.
- [[curriculum-writer]] — what the author was contracted to deliver.
- [[dispatch-router]] — picking the right reviewer agent.
- [`docs/review-protocol.md`](../../../docs/review-protocol.md) — cross-family review contract.
- [`.claude/rules/decision-card.md`](../../rules/decision-card.md) — escalation pattern for contested reviews.
- [`.claude/rules/github-actions-security.md`](../../rules/github-actions-security.md) — workflow review rules.
