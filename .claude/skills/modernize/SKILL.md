---
name: modernize
description: Assess an old KubeDojo PR or branch against current main, update it if appropriate and deliver its original goal. Use when explicitly asked to modernize or refresh old work.
---

# Modernize

- Inspect the original goal, PR, branch, reviews and findings; fetch current main and record the head and merge base. Check live ownership, worktrees and unpushed changes before touching the work.
- Compare the intent with current code and history: determine whether the problem is already solved, interfaces or assumptions changed, or the old approach would restore obsolete behavior. A clean rebase alone is not proof.
- Record an evidence-backed verdict: update if still appropriate, rework if the goal remains valid but the approach no longer fits, or superseded if the goal is already met or obsolete. Preserve original credit and scope; do not overwrite another active lane. For superseded, report evidence and stop without rebase, delivery, merge or enqueue.
- For update or rework, follow AGENTS.md worktree rules, preserve intent, verify the resulting changes and relevant behavior, and reassess if the source moves. Rebase or conflict resolution requires fresh exact-head review and checks.
- Hand only an update or rework verdict, revision, findings and evidence to [full-send](../full-send/SKILL.md) for delivery; use [full-stop](../full-stop/SKILL.md) only for an explicitly requested ready-to-merge handoff. Respect material blockers and higher-priority restrictions.
