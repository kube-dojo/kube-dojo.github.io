---
name: review-loop
description: Run a bounded independent review cycle for a specific KubeDojo change through an exact-head verdict. Use when asked for a review loop or to manage review rounds and findings.
---

# Review loop

- The accountable lead freezes the scope, acceptance criteria, non-goals, review brief, base and head before review; record the planned rounds, automatic ceiling and spent invocations, and carry them forward with the findings.
- Allow up to five independent review invocations automatically per review stream, including PR reviews and whole-page source/editorial audits managed by this skill. Continue necessary fixes and exact-head or exact-page/seed re-review through R5 without requesting permission merely because the initial plan used fewer rounds. Honor an explicit smaller user cap or stop; a later user authorization can raise that cap. Failed, incomplete and inconclusive invocations count; preparation that stops before invocation does not. Changing the head, seed or packet name never resets the counter for the same review stream.
- Resolve an available reviewer from live routing under AGENTS.md; embedded dated model tables are not live routing authority. Use [cross-family-reviewer](../cross-family-reviewer/SKILL.md) for a real independent review outside the author's model family at the exact pushed head. Record reviewer identity, family, head, verdict and evidence on the PR within the round budget when authorized.
- Keep stable finding IDs, evidence, severity and dispositions. Resolve material findings; a supported disagreement remains open and blocking pending resolution under drive-epic's escalation rule, and is not approval. Stop after a valid unchanged-head approval with no unresolved material findings; optional nits alone must not trigger another round.
- A changed head invalidates the prior exact-head verdict: review the new head and relevant fixes within the remaining budget. Preserve the original brief and finding ledger.
- A valid approval for this unchanged pushed head returned within budget remains usable on the final allowed round. Exhaustion alone grants no clearance: missing, failed, contested or inconclusive review, an unavailable reviewer, or no valid verdict before the budget ends requires reporting the evidence, remaining findings and responsible owner; do not manufacture approval.
- Exceed five only when an explicit user authorization covers the additional invocation; otherwise obtain it for the concrete remaining review. Automatic continuation grants no permission to skip independent identity, complete evidence, material-finding resolution, CI, publication or acceptance gates, and never permits constructing or rebinding a source receipt.
- For curriculum, distinguish a scoped delivery review from full-page acceptance, which requires the applicable source, rubric and practice evidence. Report what was and was not reviewed.
