# Cold start — issue-driven and pipeline sessions

Copy-paste sequence for a fresh KubeDojo coding session. Single shell entry point:
`scripts/cold-start.sh` (also documented in `AGENTS.md`, `CLAUDE.md`, and
`.claude/skills/cold-start/SKILL.md`).

Use this workflow for issue-driven work or tasks that need pipeline state.
For self-contained code or documentation edits, start with repository status
and the relevant files; no service startup or full handoff is needed.

## Session prompt

```
1. Read GitHub issue #N verbatim (parent task).
   gh issue view N --repo kube-dojo/kube-dojo.github.io
   If the issue is a Kubernetes minor, exam-version bump, or “update certs to latest K8s”:
   read docs/release-maintenance/kubernetes-minor-release-playbook.md before editing.
   Dual-track: exam_pin ≠ latest_stable_track. Refs #2542 only (never Resolves).

2. Orient (services-up + workspace + API):
   KUBEDOJO_ISSUE=N bash scripts/cold-start.sh
   # Optional route discovery:
   bash scripts/cold-start.sh --manifest

3. Check GET /api/pipeline/leases before claiming pipeline work.
   If issue claiming is authorized:
   gh issue comment N --body "Claiming — worktree .worktrees/<short-name>"

4. Create worktree on main (never work on primary main):
   git worktree add .worktrees/<short-name> -b codex/<short-name> main

5. Work in the worktree only. Do not merge — cross-family review via
   scripts/dispatch.py or scripts/ab; organizer merges.

6. Read the full handoff file ONLY if briefing/orient leaves a narrative gap.
   Path comes from --- kubedojo:session --- (API) or --- kubedojo:handoff-path --- (fallback).
```

Complete the assigned acceptance criteria in the worktree, run the applicable
checks from AGENTS.md, and fix failures introduced by the change. Continue
through authorized validation and delivery rather than stopping at the first
implementation. For bridge assignments, return the verified PR and its design
choice; for local edits, return changed paths and verification. Report a precise
blocker when completion is impossible. Preserve the organizer's merge boundary.

## What the script emits

| Section | Source |
|---------|--------|
| `kubedojo:issue` | `KUBEDOJO_ISSUE=N` reminder (optional) |
| `kubedojo:workspace` | `git status --short` |
| `kubedojo:pending-decisions` | `docs/decisions/pending/` (first 5) |
| `kubedojo:briefing` | `GET /api/briefing/session?compact=1` |
| `kubedojo:orient` | `GET /api/orient` — primary action + alternatives |
| `kubedojo:session` | `GET /api/session/current` — handoff pointer only |
| `kubedojo:manifest` | `GET /api/state/manifest` (with `--manifest`) |

API base: `http://127.0.0.1:8768` (`KUBEDOJO_API` override). Timeout: 2s per request.

## API-down fallback

When the briefing API does not respond after retries, the script **exits 0** and prints:

- First 40 lines of `STATUS.md`
- Latest handoff path parsed from the `## Latest handoff` table

Then read `CLAUDE.md` / `MEMORY.md` only if the fallback block is insufficient.

## Before claiming / fixing / re-reviewing

After cold-start, use the local API (see `scripts/agent_onboarding.md`):

- Claim work: `GET /api/pipeline/leases`
- Fix module: `GET /api/module/{key}/state`
- Re-review: `GET /api/reviews?module={key}`

## Bounded dispatches

Honor the supplied tool and output contract. A content-only dispatch can supply
its module state and source packet directly and prohibit shell/service startup.
Do not expand such a packet into a separate orchestration session.
