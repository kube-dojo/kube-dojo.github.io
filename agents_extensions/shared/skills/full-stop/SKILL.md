---
name: full-stop
description: Prepare a protected KubeDojo PR for another owner to merge, stopping at a verified ready-to-merge handoff. Use only when the brief explicitly requests full-stop or a ready-to-merge handoff, not for ordinary stop or cancel requests.
---

# Full stop

- This is the protected handoff workflow adapted from Learn Ukrainian. An ordinary request to stop or cancel work is not an instruction to start or continue it.
- Carry the authorized work through implementation and verification, and run [review-loop](../review-loop/SKILL.md), preserving owned work and evidence. Never merge, enqueue, arm auto-merge, push to main, or ask another agent to do so on your behalf.
- Before editing an existing PR, verify it is held against automatic landing; for a new PR establish and verify the hold as soon as it exists. Recheck hold, auto-merge and queue state before pushes and at handoff. If protection cannot be established, stop and report the blocker.
- Report ready only when the open PR is protected and its live head has the required exact-head independent review, passing applicable checks and completed proof. Future merge or deployment checks remain unproven; a changed head requires renewed review.
- Hand the receiving owner the PR, head, protection state, review and findings, verification, named residuals and next action. Otherwise report the specific blocked or waiting state; if already merged externally, report that fact and merge revision.
