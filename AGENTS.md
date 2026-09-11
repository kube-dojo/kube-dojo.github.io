# AGENTS.md — KubeDojo agent instructions

KubeDojo is an Astro/Starlight curriculum site. These instructions apply across
agent families. Use `CLAUDE.md` for Claude-specific behavior and
`.claude/rules/agy-workflow.md` when dispatching to the Google lane.

## Scope and completion

Complete the requested outcome, including implementation, relevant verification,
and fixes for failures caused by the change. Continue through these authorized
local steps without asking for approval after the first draft. If running or
visually inspecting the result is part of the task, include that in completion.
Report remaining blockers precisely; do not claim a partial result is complete.

Use the task's acceptance criteria and output contract. A local edit does not
itself authorize publishing, deployment, merging, or unrelated cleanup. Carry
out external actions when the user's request authorizes them, subject to the
review gates below. Preserve the requested scope and any explicit LOC budget.

## Workspace and evidence

- Start at the repository root with `git status --short --branch`.
- Work in `.worktrees/<short-name>` on a new `codex/<short-name>` branch from
  `main`. Keep the primary checkout on `main`; preserve pre-existing changes.
- Use `apply_patch` for manual edits. Do not revert others' work or delete files
  or worktrees without explicit instructions.
- Stage explicit files. Exclude runtime output: `.pipeline/state.yaml`,
  `.pipeline/reviews/**`, `.pipeline/logs/**`, `.bridge/messages.db`, `.cache/**`,
  `.pids/**`, `dist/**`, `node_modules/**`, `*.staging.md`, and `*.bak`.
- Ground claims in inspected code, live state, or verified sources. Never invent
  sources, historical dialogue, incidents, or data to meet a length target.
  Report an evidence shortfall in the required output format.

## Read context when it applies

For issue-driven or pipeline work, read the issue verbatim, then run
`KUBEDOJO_ISSUE=N bash scripts/cold-start.sh` (omit the variable without an issue).
This starts services and reports workspace, decisions, briefing, and handoff
pointers. For a self-contained documentation or code edit, inspect the relevant
files directly; service startup and a full handoff are unnecessary.

Before claiming pipeline work, read `GET /api/pipeline/leases`. Before fixing a
module, read `GET /api/module/{key}/state`; before re-reviewing it, read
`GET /api/reviews?module={key}`. The API base is `http://127.0.0.1:8768`.
Use `/api/tracks/readiness` and `/api/activity` for curriculum-wide coordination.
Read a full handoff only when the briefing leaves a relevant gap. If the API is
down, cold-start exits 0 with a `STATUS.md` excerpt and handoff path; this is a
fallback, not proof of healthy services.

| Task | Relevant context |
|---|---|
| Session or pipeline coordination | `scripts/prompts/cold-start.md`, `scripts/agent_onboarding.md` |
| Author curriculum | `agents_extensions/shared/skills/curriculum-writer/SKILL.md`, `scripts/prompts/module-writer.md` |
| Review curriculum | `agents_extensions/shared/skills/module-quality-reviewer/SKILL.md`, `docs/quality-rubric.md`, applicable `docs/rubric-profiles/` |
| Content structure and frontmatter | `.claude/rules/new-content-checklist.md` |
| Current quality scores | `/api/quality/scores`; the static `docs/quality-audit-results.md` is historical |
| Agent dispatch | `scripts/dispatch_smart.py`, applicable adapter and provider workflow |

Load a skill for its actual workflow, not merely because a keyword appears.
Shared skill sources live in `agents_extensions/shared/skills`; maintain their
tracked `.claude/skills` mirrors with `agents_extensions/deploy.sh`. Check which
copy the current agent actually loads; local `.agents/skills` copies can drift.
Retain exact schemas and curriculum requirements; choose implementation steps
according to the task rather than expanding every task into the full pipeline.

## Tools and validation

Use `.venv/bin/python` explicitly for Python commands and subprocesses. Do not
use `sys.executable`, `python3`, or an unqualified `python`. This project runs
locally: derive paths from the repository or `Path(__file__)`, use `127.0.0.1`
for local services, and do not introduce container paths such as `/app/src`.

Run checks relevant to the changed behavior and the pre-submit requirements
below. After they pass, repeat or broaden them only for new changes, failures,
or unresolved risks. Do not weaken assertions, disable lint rules, add empty
skips, or hide missing imports to obtain a pass.

Builds run from the primary checkout, not `.worktrees/*`, because the existing
Astro dependency layout has a worktree resolution limitation. Keep primary on
`main` and preserve its changes. Fetching a branch alone does not put its content
into a main-checkout build: report the revision actually tested and use branch
CI to verify a proposed change before merge. Do not claim a main build validates
unmerged worktree edits.

For Codex-from-bridge invocations use `scripts/ab`. The wrapper currently pins
`CODEX_BRIDGE_MODE=danger`; do not duplicate contradictory sandbox defaults in
prompts. Its guard is `scripts/ops/smoketest_ab_codex_danger.sh`.

## MANDATORY PRE-SUBMIT CHECKLIST

**Before opening a PR, verify EVERY item. If ANY check fails, fix it BEFORE submitting.**

- [ ] `.venv/bin/ruff check` clean on every Python file you changed
- [ ] `.venv/bin/python scripts/test_pipeline.py` — 0 new failures (2 pre-existing `check_failures` tests + 1 `TestStatusFourStage` order flake are acceptable until their dedicated cleanup lands)
- [ ] `npm run build` passes if you touched content under `src/content/docs/` or Astro config (skip for pure-Python-script changes)
- [ ] No `sys.executable` anywhere — always `.venv/bin/python` explicitly
- [ ] No `@pytest.mark.skip` with empty `pass` bodies, no double-skip decorators
- [ ] Assertions not weakened (no `is True` → `isinstance(..., bool)`)
- [ ] Every changed file is directly related to the task
- [ ] Total files changed < 20 (if more, you likely included artifacts)
- [ ] Diff budget respected (tasks specify a LOC ceiling; if you can't fit, split)
- [ ] Primary repo is NOT on detached HEAD after your work

**If you cannot check every box, your PR will be rejected.**

### Book-only AI History PR exception

For PRs that only touch AI History book/research material and do not affect executable code, generated state, or the published Astro site, do **not** run the expensive curriculum pipeline gate. These PRs include changes strictly limited to:

- `docs/research/ai-history/**` (including all narrative drafts, workflow, and coordination docs within this path)

Required checks for these book-only PRs are:

- [ ] `git diff --check` clean on the changed files
- [ ] cross-family review posted as a PR comment
- [ ] no generated artifacts included
- [ ] primary repo remains on `main`

Skip `.venv/bin/python scripts/test_pipeline.py` for this category. That test suite validates the curriculum pipeline and has low signal for unpublished book research while consuming substantial local and model resources. If a book PR also changes Python, scripts, pipeline behavior, `src/content/docs/`, Astro config, or shared tooling, this exception does not apply and the full checklist above is required.

## Delegation and routing

One accountable lead owns scope, integration, validation, and final disposition.
Use deterministic tools first. Delegate disjoint bounded work only when it adds
useful speed or independent evidence; do small sequential tasks locally.
Workers must preserve others' edits and return changed paths, validation, risks,
and blockers. Do not give routine workers secrets, `.envrc`, GitHub actions,
review routing, merge decisions, or a second orchestration role.

Use the live installed catalog and provider health/quota signals. The preferred
Codex roles are Astra medium for the lead, Astra low for bounded implementation,
Luna medium/high for read-only exploration, and Astra high for advice or
adversarial review. Prefer installed named profiles. If a route is unavailable,
report it rather than silently substituting. Do not copy dated model tables
into this file. Headless dispatch defaults live in `scripts/dispatch_smart.py`;
verify that route separately from desktop profiles before using it.

Probe CodexBar before substantive fan-out; report only aggregate usage and
timestamps. Unknown telemetry stays unknown. Keep packets bounded as usage
rises and honor the user's quota policy. Gemini calls remain sequential because
the user also runs workloads elsewhere.

## PRs and independent review

Keep one concern per PR, fewer than 20 changed files, and any task-specific LOC
ceiling. If an issue's budget cannot fit, prepare a split plan instead of a
mega-PR. Include its issue reference in the commit title and PR body; report
summary, verification, and diff size. Do not include generated artifacts.

Before merging or closing an issue, obtain an adversarial review from a
*different model family* and post it as a PR/issue comment when posting is
authorized. Codex reviewing Codex is not that review, and passing tests do not
replace it. Route the required cross-family review before merge; keep the lead
accountable. Resolve material findings before proceeding. Use a comment rather
than `gh pr review --approve` when author and reviewer share a GitHub identity.

For bridge-delegated issues, deliver the implementation and verified PR, then
return the PR URL and design choice through the authorized bridge. The organizer
owns merge after independent review. Report the specific blocker if dispatch,
validation, or PR creation fails.

Final reports include changed files, verification and its limits, remaining work,
and final `git status --short --branch` for worktree and primary checkout.

## Curriculum invariants

Published content lives in `src/content/docs/`; Ukrainian content mirrors it in
`src/content/docs/uk/`. Navigation uses Starlight configuration and frontmatter,
including `title:` and `sidebar.order:`. Kubernetes content targets 1.35 unless
the task establishes a newer target. Pipeline v2 is the default; v1 remains for
compatibility.

Teach the reasons behind concepts and use worked examples. For mathematics,
explain the purpose and use concrete demonstrations before formalism. Preserve
substantive learning outcomes, legitimate variation, source requirements, and
the relevant rubric; never pad unsupported content to satisfy a metric.
