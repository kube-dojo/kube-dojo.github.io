---
name: review-loop
description: Run a bounded independent review cycle for a specific KubeDojo change through an exact-head verdict. Use when asked for a review loop or to manage review rounds and findings.
---

# Review loop

- The accountable lead freezes the scope, acceptance criteria, non-goals, review brief, base and head before review; record a bounded round budget and carry it forward with the findings.
- Resolve an available reviewer from live routing under AGENTS.md and use [cross-family-reviewer](../cross-family-reviewer/SKILL.md) for a real independent review outside the author's model family at the exact pushed head. Record reviewer identity, family, head, verdict and evidence on the PR within the round budget when authorized.
- Keep stable finding IDs, evidence, severity and dispositions. Resolve material findings or document a supported disagreement; optional nits must not trigger endless automatic rounds.
- A changed head invalidates the prior exact-head verdict: review the new head and relevant fixes within the remaining budget. Preserve the original brief and finding ledger.
- A valid exact-head approval returned within budget remains usable on the final allowed round. Exhaustion alone grants no clearance: missing, failed, contested or inconclusive review, an unavailable reviewer, or no valid verdict before the budget ends requires reporting the evidence, remaining findings and responsible owner; do not manufacture approval.
- For curriculum, distinguish a scoped delivery review from full-page acceptance, which requires the applicable source, rubric and practice evidence. Report what was and was not reviewed.
