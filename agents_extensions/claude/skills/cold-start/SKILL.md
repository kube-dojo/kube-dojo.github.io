---
name: cold-start
description: Orient issue-driven or pipeline work using KubeDojo's live briefing and handoff pointers.
---

# Cold start

Use this workflow when taking a GitHub issue or coordinating pipeline work.
Self-contained code or documentation edits can start with repository status
and the relevant files, without starting services.

Read the issue verbatim, then run `KUBEDOJO_ISSUE=N bash scripts/cold-start.sh`
from the repository root (omit the variable if there is no issue). See
`scripts/prompts/cold-start.md` for the command sequence and output sections.
Paths here are relative to the repository root.

Use the briefing to resolve the assigned task; an unrelated queue suggestion
is not a new assignment. Read the full handoff only for a relevant context gap.
Before claiming pipeline work, check `GET /api/pipeline/leases`. Post a claim
only when authorized. Make changes in a worktree, preserving primary `main`.

If the API is unavailable, the script exits 0 with a STATUS excerpt and handoff
path. Continue with sufficient local evidence, or report the specific missing
state; exit 0 is not a service health check.

Honor a dispatch's tool and output constraints. A supplied content packet that
prohibits shell commands does not need a separate orchestration session.
