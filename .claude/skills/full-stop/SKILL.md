---
name: full-stop
description: Prepare a protected KubeDojo PR for another owner to merge, stopping at a verified ready-to-merge handoff. Use only when the brief explicitly requests full-stop or a ready-to-merge handoff, not for ordinary stop or cancel requests.
---

# Full stop

- This is the protected handoff workflow adapted from Learn Ukrainian. An ordinary request to stop or cancel work is not an instruction to start or continue it.
- Carry the authorized work through implementation and verification under AGENTS.md worktree rules, and run [review-loop](../review-loop/SKILL.md), preserving owned work and evidence. An explicit full-stop brief suspends drive-epic's merge-this-turn rule for this change; the receiving owner merges. Never merge, enqueue, arm auto-merge, push to main, or delegate those actions.
- Before editing an existing PR, establish observable protection: open PR, auto-merge disabled and not queued. If necessary disable auto-merge and dequeue, then verify live state; for a new PR verify that state as soon as it exists. Recheck before pushes and at handoff. If protection cannot be established or verified, stop and report the blocker; do not invent a hold label.
- Report ready only when the open PR is protected and its live head has valid exact-head independent approval, passing applicable checks and completed proof. Future merge or deployment checks remain unproven; a changed head requires renewed review.
- Hand the receiving owner the PR, head, protection state, review and findings, verification, named residuals and next action. Otherwise report the specific blocked or waiting state; if already merged externally, report that fact and merge revision.
