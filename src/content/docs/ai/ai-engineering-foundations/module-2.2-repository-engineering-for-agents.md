---
title: "Repository Engineering for Agents"
slug: ai/ai-engineering-foundations/module-2.2-repository-engineering-for-agents
sidebar:
  order: 22
revision_pending: false
---

> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 90-120 min
>
> **Prerequisites**: Module 2.1 Context Engineering Fundamentals or equivalent; familiarity with repository layout, Git workflows, and Markdown documentation.

## Learning Outcomes

By the end of this module, you will be able to map a durable, machine-checkable instruction stack, identify where durable policy ends and ephemeral run context begins, and apply these decisions so agents can start reliably instead of recovering from avoidable context drift.

- **Design** a repository-level agent legibility stack and justify where each layer lives.
- **Differentiate** system-of-record files from ephemeral task memory and ephemeral execution logs.
- **Engineer** progressive-disclosure instruction files that prevent context drift and stale rules.
- **Compose** structured `docs/` surfaces that transform policy, architecture, and operations into machine-readable guidance.
- **Map** how a repository can “talk back” to an agent through API endpoints, checks, and status surfaces.

## Why This Module Matters

Mira has seen one more task bounce back and forth.
She asked an agent to fix a bug, then ran a different check, then got a patch that violated an obvious repo rule.
The repo had good docs somewhere, but the agent never found the right page at the right moment.

This module treats repository design as the difference between “reasonable instructions” and “usable instructions.”
A poorly engineered repository can still have great people and great models, and still fail repeatedly.
A well-engineered repository gives agents a stable map, a clear load order, and explicit feedback loops.

Repository engineering for agents is not documentation theater.
You are not writing yet another long instruction file.
You are designing a load-bearing contract surface.

The contract has three constraints.
First, an agent must discover the right context quickly.
Second, context must stay trustworthy over time.
Third, the repository must continuously signal what changed since the last run.

In this module, you will learn how to satisfy all three while avoiding the classic failure modes of brittle, overgrown AGENTS-like files and one-size-fits-all instructions.

## The Problem We Keep Solving in Long AI-Work

Team-level AI workflows usually break in one of four recurring ways: monolithic instruction surfaces, missing entry paths, stale guidance that outlives the process it governs, and repositories that provide no machine-checkable failure signal.

### 1) The one-file monolith

A single AGENTS-like file grows until it becomes a museum.
It includes policy, style, branch rules, secrets hygiene, PR etiquette, test order, deployment notes, and platform quirks all in one place.
The file eventually becomes noise.
Agents still load it, but the signal-to-noise ratio drops.

### 2) The missing map

Some repos have many files but no discoverable entry path.
The agent reads random rule files and misses the system-of-truth folder.
By the time it lands on the right page, the task context has shifted.

### 3) The stale loop

A stale rule says branch `main`, but the repo moved to `main` plus `release` and `stage`.
An obsolete review cadence says run one check, while the CI now requires three.
An old checklist tells the agent to skip an expensive but now required step.
This mismatch is not hypothetical.

### 4) The blindfolded repo

The repo returns no structured signals beyond a final success line.
It might compile but still violate governance.
An agent cannot “learn” repo expectations if the repo does not expose what was expected or what failed.

If you can prevent these four modes, you improve correctness, review quality, and merge predictability while reducing repeated context-loss runs and avoiding the hidden costs of stale or contradictory guidance.

## What AGENTS.md and CLAUDE.md actually become in agent engineering

AGENTS.md and CLAUDE.md are paired contract layers, not duplicate instruction books.
In KubeDojo, AGENTS.md is the cross-tool bootstrap: it defines what every session must do before coding, including issue-driven onboarding, non-negotiable checks, and anti-pattern boundaries.
CLAUDE.md is the runtime-memory surface for Anthropic tooling, where orchestration behavior and operational intent can be specific without overburdening the shared bootstrap.

The split is intentional. If a rule should survive across model families and toolchains, it belongs in the root contract; if it is specific to one runtime model, it belongs to the model memory file.
AGENTS remains compact and stable because that file is the first shared contract the engine sees.
CLAUDE carries the richer session-specific details and then points to the same scoped rule surface for current run behavior.

OpenAI’s AGENTS.md guide describes **per-directory precedence with root-to-leaf concatenation** (at most one file per directory).
Within each directory, discovery order is:
`AGENTS.override.md` → `AGENTS.md` → fallback filenames configured in `project_doc_fallback_filenames`.
If a directory contains `AGENTS.override.md`, that file wins at that level and replaces `AGENTS.md` and any configured fallback there.
If none of those files exists at that level, discovery continues upward; the selected file from each ancestor directory is concatenated root-to-leaf into the combined instruction set.

The guide also makes one important hard-limit point explicit: `project_doc_max_bytes` truncates combined instructions.
The default is **32 KiB (32768 bytes)**; the sample config in the guide shows raising the limit to `65536`, and the behavior is to keep only the most recent in-scope bytes when combined guidance exceeds that boundary.
That means KubeDojo’s design principle of keeping AGENTS/CLAUDE concise is not stylistic; it is a reliability requirement so critical lines are not evicted by byte cap.
Fallback filenames only work when listed in config.
If a project uses `TEAM_GUIDE.md` but forgets it in `project_doc_fallback_filenames`, Codex silently ignores that file.

This mechanism matters because it turns instruction size into a hard runtime contract.
Suppose an AGENTS-like file grows to 20k words and then later a hotfix prepends 100 lines at the top.
The byte cap can silently drop lower-priority content in that same file, which is why teams usually reserve AGENTS and CLAUDE for invariants, not for all historical context.
That is also why the bootstrap should stay deterministic: every non-deterministic or long-lived detail must be delegated to scoped files or checkable endpoints, then explicitly referenced from the root contract.

The OpenAI model side has another implication that is easy to miss.
AGENTS.md uses per-directory precedence with root-to-leaf concatenation (`AGENTS.override.md` -> `AGENTS.md` -> fallback files, at most one file per directory), while CLAUDE.md is not bound to that same precedence model.
In practice, that means `AGENTS.md` has clearer portability and fallback semantics in cross-tool dispatch, while CLAUDE.md can encode Anthropic-specific continuity and memory posture for workflows that need it.
Treating the two as the same layer creates coupling risk, but treating them as complementary layers gives you predictability: one stable cross-runtime boot contract plus one higher-cardinality operational memory contract.

This means Codex-specific files and CLAUDE.md ecosystems should compose, not duplicate.
Root `AGENTS.md` and `CLAUDE.md` define what never changes across sessions.
`.claude/rules/*` carries mutable, scoped behavior that still stays close to the code path.
When both evolve together, agents get stable entry conditions from AGENTS/CLAUDE and current operational details from rules without context drift.

The model-specific fit is straightforward:
CLAUDE.md supplies the deeper memory surface for Anthropic-style continuation memory,
while AGENTS.md remains the cross-tool bootstrap that other engines can consume.
That is why KubeDojo keeps shared anti-pattern policy in AGENTS.md and operational session rhythm in CLAUDE.md, with no contradiction because each layer has explicit precedence.

In this model, CLAUDE and AGENTS are not competitors; they are adjacent boundaries.
Where they overlap, they should point to the same scoped descendants, then let one model-specific and one cross-model layer keep behavior consistent without contradiction.

## Progressive Disclosure as a design principle

Progressive disclosure is the discipline of ordering context by stability, reuse, and expected drift.
It is not a UI concept copied into docs.
It is a memory-safety principle for AI work.

Imagine context as a memory hierarchy.
The first layer must always be safe to keep.
The second layer must support repeatable operations.
The third layer should stay narrow and time-bound.

```text
+--------------------------------------------------------------+
| Layer  | Stability            | Change cadence | Agent read-time policy |
+--------+---------------------+----------------+-----------------------+
| L0     | High                 | Slow           | Always load            |
| L1     | Medium               | Moderate       | Load when in subtree    |
| L2     | Low                  | Frequent       | Load on demand only     |
| L3     | Ephemeral            | Real-time      | Load from current task   |
+--------+---------------------+----------------+-----------------------+
```

### L0: Always-loaded map files

L0 includes your highest-level bootstrap files.
If every agent starts with your repository, this layer should include a compact map of policy, checks, and run-time entry points, because L0 must remain small enough to load instantly and stable enough to trust between runs.

- one path to the main workflow contract,
- one path to safety and branch policy,
- one path to docs index,
- and one path to execution checks.

AGENTS.md and root CLAUDE.md are common L0 occupants.
But they should remain compact.
A compact L0 means 100-250 high-leverage lines, not a 3,000-line instruction book.

### L1: Repository-locally discoverable slices

L1 should include scoped rules and recurring playbooks.
In this layer, instructions remain stable across many tasks, but they are narrow enough to allow one tab, domain, or workflow to evolve without forcing global contract edits.

- rules apply to common workflows,
- changes are infrequent,
- text should be stable across many tasks,
- examples should be durable and explicit.

This is where `.claude/rules`, architecture notes, and recurring task-runbooks usually live, and where teams preserve durable guidance close to the work so instructions can be reused without flattening everything into root files.

### L2: Role-specific and workflow-specific documents

L2 holds targeted instructions tied to roles, features, or recurring domains.
A few examples:
Use L2 when behavior differs by function, timeline, or permission set, and always encode who can run each step and what output proves compliance.

- docs for onboarding,
- docs for PR review,
- docs for module publishing,
- docs for issue triage,
- docs for release hygiene.

These are not ignored.
They are loaded when needed and often become the differentiator between a decent agent workflow and a high-precision one.

### L3: Dynamic run surfaces

L3 is what the repo tells the agent about the *current* run.
Think of it as per-task telemetry.
Examples include:

- current pipeline state,
- open issue constraints,
- required checks for the task,
- open warnings from local APIs,
- and review history for this module.

For L3, the repository becomes operational, not only descriptive, because every active task should be able to read current lease state, warnings, and review evidence before deciding what to change next.

## The bootstrap stack for this repository

KubeDojo organizes startup around three layers. Repository-wide rules give agents a starting point, scoped guidance sets requirements for specific tasks, and commands and APIs report current state.

Start with `AGENTS.md` for the repository-wide rules and `CLAUDE.md` for Claude-specific guidance.
Run `git status --short --branch` from the repository root to see the current branch and any local changes. For issue-driven work, read the issue to establish the scope before exploring unrelated files.
For a self-contained edit, open the affected files and follow the checks named in `AGENTS.md`.

For fleet coordination, follow the instructions for the installed `lu-machinery` release. For live curriculum state, follow the local API recipes in `scripts/agent_onboarding.md`.
They show which queries answer whether someone already holds a module lease, what condition the module is in, and whether a review exists.
If the local API is unreachable or the lease data is unavailable, the current lease state is unknown. Use `STATUS.md` as an index, and defer any claim that requires a live lease check until you can verify it.

The scoped curriculum rules live under `agents_extensions/claude/rules/` and are deployed to `.claude/rules/`.
Read `module-quality.md` and `new-content-checklist.md` when the task calls for them. Keeping the detailed checks in scoped files gives agents a short starting point and a direct route to the rules they need.

The live checks and the lab exercise serve different purposes.
`scripts/print-run-contract.sh` is a lab-created parser script you build in the practical exercise, used to check contract paths deterministically.
Together these examples show how to keep durable rules in files and check current conditions when the task calls for them.

## The docs-as-system-of-record model

A well-engineered repository treats `docs/` as the durable interface between humans and agents.
Humans maintain structure.
Agents consume structure.
When both sides align, the repo becomes easier to operate.

For this model to work, documentation has to meet three criteria: stable authority, machine readability, and continuous review pressure through executable assertions.

1. **Stable authority**: statements should be true for the module until intentionally revised.
2. **Machine readability**: enough section headings, anchors, and predictable names for tooling and retrieval.
3. **Review pressure**: every change to docs should be reflected in checklists, PR templates, or state surfaces.

A practical pattern is to separate docs by intent so long-term architecture records, workflow instructions, and run-time notes do not collide in one place.

```text
+----------------------+----------------------------------------------+
| Folder intent        | Primary consumer                               |
+----------------------+----------------------------------------------+
| src/content/docs     | Long-term learning, policy, and design records  |
| .claude/rules        | Scoped agent operating constraints            |
| scripts/*            | Operational contracts and automation surfaces  |
| docs/research        | Strategic research and brief summaries         |
+----------------------+----------------------------------------------+
```

This repository already uses that structure by design.
`docs/` is not the only source of truth.
But it is the highest-value source for persistent repository knowledge.

## Designing the AGENTS chain

You do not need one giant AGENTS strategy document.
You need a predictable chain.
Here is a reliable sequence:

### Step 1: root bootstrap card

Create or verify a short root file that answers where the contract starts, what blocks execution, what command order to use, and where nested files override general policy.

- where checks live,
- what command order governs each run,
- what forbidden outputs are banned,
- and where deeper instructions are linked.

### Step 2: scope folders

If repository sections have unique logic, add scoped files.
The scope can be by tab, domain, or operational area.
A file in a subfolder should override root instructions when conflicts are explicit.

### Step 3: stable-to-dynamic linking

Use short links and explicit anchors.
Every scoped file should point to deeper documents rather than duplicate them.

### Step 4: periodic audits

Every quarter, read and prune stale references, retired tooling notes, and ownership drift so discovery still points to actual, runnable files instead of archive artifacts.

- stale process calls,
- outdated tools,
- moved folders,
- changed ownership names.

If an instruction file has not changed in a year but still describes current work, test it.
If it no longer matches real behavior, remove or move it down the stack.

### Step 5: feedback hooks

The chain must include where violations surface.
If a rule exists and is not checked, it is not an instruction, only lore.

## CLAUDE.md as layered memory in this model

In Anthropic tooling, CLAUDE.md gives project-context memory that is hierarchy-aware.
Agents use the file system to inherit higher-level and lower-level instructions automatically.
That makes CLAUDE.md a strong candidate for one part of L0 or L1.

It must not absorb every policy.
For robust stacks, root instruction files should encode stable intent, while role or workflow-specific behavior belongs in scoped documents that are easier to update safely.

- root CLAUDE.md: startup posture and cross-project conventions,
- nested CLAUDE.md: domain-specific context,
- references to `docs/` pages for durable design and policy,
- links to local endpoints for current state.

The important distinction:
A stable bootstrap contract should not be a catch-all for fast-changing behavior; it should own only the principles that remain valid across many runs and teams.

- CLAUDE.md is memory bootstrap.
- AGENTS.md is often ecosystem-level bootstrap and agent-facing index.
- docs pages are durable records and behavior contracts.

You can use both without contradiction.
When they overlap, choose the closest applicable layer as source of truth for that concern.

## How a repository should “talk back”

A repository talks back when it provides machine-readable failure signals at the same pace the agent makes decisions.
In KubeDojo, this means three endpoints are tied into one operational loop: concurrency (`/api/pipeline/leases`), state (`/api/module/{key}/state`), and historical review (`/api/reviews?module={key}`).
This is not just observability; it is control flow.

In the first scenario, an agent is about to claim a module that someone else is working on.
`GET /api/pipeline/leases` lists active leases. The response from `/api/module/{key}/state` includes the lease information for the target module.
If another agent holds the lease, wait for its release or choose a different module. If the lease index returns `exists: false`, the data is unavailable even if the active list is empty.
Treat these reads as evidence for deciding what to do next. The claim itself goes through the curriculum workflow.

Failure scenario 2: invalid module state before edit.
The same `/api/module/{key}/state` call can return `diagnostics[]` entries with stable `code` values such as `frontmatter_no_title`, `rubric_poor`, `uk_translation_missing`, or `lease_held`.
Each diagnostic record includes `severity`, `summary`, and optionally `next_action`.
That is the key design signal: failures are not just booleans.
When `next_action` says `GET /api/labs/status`, the agent can switch to lab health checks.
When it says `GET /api/quality/scores`, the agent can inspect the reported rubric scores.
This is how `diagnostics[]` turns unknown failures into deterministic remediation steps.
The same payload also contains `english_path`, `ukrainian_path`, and `fact_ledger` presence flags.
If the frontmatter lacks a title, open the source file. If the translation is stale, check `GET /api/translation/v2/status`. The diagnostic directs the agent to the relevant file or query.

Failure scenario 3: stale review path or unresolved evidence.
An agent asks `/api/reviews?module={key}` before making final edits.
If the module has no recorded review, the API returns `{"error":"review_not_found"}` with HTTP 404. Check which review the task requires before proceeding.
If a review exists but lacks evidence, `fact_check_unverified` in state and a warning diagnostic indicates additional fix pass needed before rework can proceed.
This scenario preserves review integrity while keeping the failure local and machine-readable.

Failure scenario 4: invalid module key.
Endpoints enforce key validation through `_validate_module_key`.
If an agent sends `/api/reviews?module=bad value`, the API returns `{"error":"invalid_module_key"}` with `400`.
That error is not cosmetic; it is a hard signal to normalize or correct the module key before re-running claims or state checks.
If `/api/module/{key}/state` receives the same malformed key, it also returns `400`.
That avoids the expensive “worked on the wrong file” class of failures.

Failure scenario 5: stale output in pipeline state.
If `/api/module/{key}/state` shows `frontmatter_*` or `english_missing` plus `pipeline_rejected` in diagnostics, the same endpoint already points to `/api/pipeline/v2/events?module=...` so a second API call explains whether the issue is queue ordering, dependency conflict, or dead-letter.
This is the anti-noise pattern: each failure path has a narrow and explicit next call, instead of a broad rerun cycle and manual log hunting.

In a healthy flow, all three failures converge to explicit states:
`leases` prevents conflict, `state` explains why the module is blocked, and `reviews` confirms whether the latest rationale is trustworthy.
Only when all three agree can an agent move from diagnostic mode to patch mode with confidence that duplicates and stale state are both addressed.

## From instruction to executable contracts

The goal is not only readable text.
An instruction surface must become executable checks.
The most common failure is static prose with no mechanical hook, because models can read claims but still fail when no command confirms what “done” looks like.

A minimal contract pattern is: a claim, a command, a gate, and a remediation step, all in the same file family so every claim can be audited without cross-file triangulation.

1. Statement in instruction file.
2. Corresponding command in `scripts/*`.
3. Automated check with stable command name.
4. CI or local check gate.
5. Review path when check fails.
6. Remediation instruction when status turns red.

## Repository interface for agents: a design framework

Use this architecture lens when auditing a repository, because each row must tie a visible question to a repeatable measurement and a recovery path.

```text
+----------------------+---------------------------+-------------------------------+
| Surface              | Question asked            | Quality test                   |
+----------------------+---------------------------+-------------------------------+
| Bootstrap files      | Can agent start safely?    | Loads without contradiction    |
| Rules & norms        | Are restrictions explicit? | Covered by checks/review        |
| Structured docs      | Where does truth live?     | Searchability + freshness       |
| Scripted feedback     | Can it report current state?| API + command stability         |
| Observability surfaces | Can it explain failures?  | Logs + summary output           |
+----------------------+---------------------------+-------------------------------+
```

Your design objective is to maximize positive findings in all five columns, then prune any section that cannot be measured or repeatedly justified in run logs.

## Four mandatory design questions

Before writing any instruction file, ask and answer whether each claim is stable, who is accountable, and which command must be re-run after every update.

1. What is always true for this repository?
2. What is usually true but subject to change?
3. What is temporary for this specific work?
4. What does the repo report after each run?

If you cannot answer these quickly, your instructions are too broad and likely forcing one file to absorb both durable rules and task-local behavior.

## The repository as a contract with multiple readers

Different readers extract different meaning from the same files, so AGENTS layers, docs, and scripts should preserve aligned grammar for humans, agents, and CI while making intent portable across roles.

- **Humans** want rationale and narrative.
- **Agents** want stable extraction points.
- **CI** wants commandable invariants.
- **Reviewers** want auditability and deterministic checklists.

A single section can serve all if authored with this principle: policy first, rationale second, verification command third, and review artifact fourth.
That structure scales because every reader can verify intent in the same order, even when they consume the section for different reasons.

## Layered instruction pattern for real modules

A practical scaffold for module authoring is:
It should be explicit enough that maintainers can verify the module entry, module checks, and completion path without opening unrelated folders.

```text
ModuleRoot/
  module-name/
    module.md          # compact module-level learning contract
    tasks/
      hands-on.md      # optional, if task flow is large
    checklists/
      preflight.md     # optional runtime checklist
```

Do not require every module to include all folders.
Do require each module to state at least one stable path to:

- how to start,
- how to verify,
- how to report completion.

## What should not go into AGENTS.md

A strong anti-pattern is loading AGENTS.md with one-time or rapidly changing instructions.
Use targeted docs instead, because root layers should preserve stable semantics and role/task documents can evolve without breaking every session’s startup contract.

- PR-specific reviewer names,
- one-off issue details,
- temporary local branch naming experiments,
- unresolved design drafts.

If this content becomes frequent, move it into task-local artifacts instead of the startup contract. Keep root files stable by routing recurring prompts, issue-specific agreements, per-module notes, and temporary run logs to scoped locations, where they can be pruned and replaced without touching bootstrap behavior.

- task prompt,
- issue comments,
- per-module notes,
- temporary run logs.

## When CLAUDE.md should be split

A single CLAUDE.md becomes fragile when multiple teams touch overlapping runtime expectations, when domain-specific behavior drifts independently, or when one file is forced to encode both stable policy and transient execution nuance.

- it contains unrelated instructions for distinct domains,
- multiple teams modify it without ownership boundaries,
- nested directories conflict silently,
- and readers can no longer identify active scope.

In that case, split by subtree where edits are independent.
That split may mirror source structure, team boundaries, or subsystem ownership.

## Repository anti-fragility: stale-aware design

Every repository instruction system ages.
A strong pattern is a simple stale policy, where stale guidance has a deprecation path and a clear owner before it misguides future tasks.

### Staleness policy sample

For every instruction file: define owner, review cadence, migration target, and deprecation note in one explicit metadata block so stale behavior cannot hide.

- define an owner,
- define expected review cadence,
- define a deprecation note,
- define migration target.

Those fields should be reviewed whenever the command surface changes.

If a file fails cadence twice in a row, move it into task-local scope or delete it.

A stale-file score can be calculated manually.
Use this as a quarterly health check for AGENTS-like surfaces before drift appears as runtime failures.

```text
+-------------------+----------------+------------------+--------------------------+
| File              | Last modified  | Last effective   | Action                     |
+-------------------+----------------+------------------+--------------------------+
| AGENTS.md         | older than 60d  | unchanged 30d     | review required            |
| CLAUDE.md         | older than 45d  | changed twice/mth  | refresh mapping sections    |
| docs/ modules     | older than 120d | unchanged 60d     | verify against scripts      |
| .claude/rules     | older than 30d  | changed 10d         | force owners review         |
+-------------------+----------------+------------------+--------------------------+
```

## Repository surfaces in practice: a blueprint

A repository that can be used by agents should expose four primary documents:

1. Orientation document.
2. Standards and review document.
3. State and health document.
4. Escalation and override document.

### Orientation document

This is the first file an agent should always be able to resolve.
In KubeDojo, the root `AGENTS.md` serves this role and points to instructions for specific tasks.

### Standards and review document

This is where long-lived behavior rules live and where durable constraints are captured, then tied to checks that prevent accidental drift.
For example:

- issue-first workflow,
- branch expectations,
- PR conventions.

### State and health document

This is where current conditions are exposed, including active blockers, quality gates, and which commands define whether execution may proceed.
For example:

- module-level pipeline state,
- quality state,
- active blockers,
- local API warnings.

### Escalation and override document

This is where conflict resolution is described, including precedence rules between overlapping layers and how to settle contradictions before any write action.

- which guidance wins at conflict,
- what manual checks are mandatory,
- where to report and close contradictions.

## Example architecture: how to teach an agent what to ignore

Agents do poorly when asked to reason over generated files, vendor directories, and throwaway outputs without explicit exclusions.
Include explicit exclusions in bootstrap and in task checklists.

Examples of exclusions should be explicit and versioned, because hidden build artifacts are a common source of false positives during instruction discovery.

- build directories,
- dist artifacts,
- cache directories,
- database and message store files,
- generated lockfiles that are environment-specific,
- ephemeral PID files.

In this repository, generated run artifacts are already called out in AGENTS-like constraints.
The same idea should appear in your own project.

## Designing repo legibility with file-level contracts

File-level contracts are specific statements attached to known files so automation can quickly verify what each file means at runtime.
A few patterns:

```text
# Contract pattern A — Immutable baseline
File: src/content/docs/<path>/index.md
Contract: this page defines module navigation and purpose.
Owner: module lead.
Refresh: when curriculum spine changes.

# Contract pattern B — Execution invariant
File: scripts/*
Contract: command output and failure mode should remain machine predictable.
Owner: script author.
Refresh: before every release.

# Contract pattern C — Cognitive map
File: CLAUDE.md
Contract: bootstrap contract and first-order instructions.
Owner: maintainers.
Refresh: weekly for active repos.
```

For each file, state both “what it does” and “why it does it,” then link to a check command.

## Hands-on checklist design for repository authors

Your module should teach action, not only theory.
A practical module should demonstrate what to do before and after a task, and what to verify when expectations are not met.
A practical authoring cycle:

1. Start from the issue.
2. Draft the contract surfaces.
3. Add links and exclusions.
4. Add verification commands.
5. Add feedback surfaces.
6. Run checks.
7. Update index.

Each step should include owner and next state, with a minimum recovery check before moving to the next step.

## The minimal contract set for a healthy repo

An effective minimum set in this model has seven files/components, and removing any one usually creates an untestable gap in either onboarding, enforcement, or closure.

- `AGENTS.md` or equivalent.
- `CLAUDE.md` or equivalent.
- one documented startup sequence that checks the worktree and identifies the task.
- one `local` API or script to query current run context.
- one module checklist for review.
- one quality entrypoint check.
- one health check.

If a repository lacks at least one component, the repo is not currently “agent-friendly.”

## Worked example: repository design walkthrough

KubeDojo is a concrete example of the same layered model that this module is trying to teach.
Suppose an issue asks you to fix a lesson. The root instructions tell you which worktree to use and which checks to run. Git reports the branch and local changes, and the issue identifies the lesson and the expected fix.
If you need to claim the module through the curriculum workflow, use `/api/pipeline/leases` before taking ownership. An active lease tells you to leave the module with its current owner. An unavailable API leaves that decision pending.
`scripts/agent_onboarding.md` points to the lease check, the module state endpoint (`/api/module/{key}/state`), and the review endpoint (`/api/reviews`). Each query answers a specific question at the point where you need the answer.

The module design pattern deepens when you compare the `scripts/local_api.py` state model.
`/api/module/{key}/state` merges filesystem checks, translation status, review status, and active lease data into one payload.
That means agents do not stitch state across random files just to determine whether a module is safe to claim.
Instead, they read one response and branch deterministically.
This is exactly the "talk-back" contract this module is teaching.

In that state payload, three details are especially practical:
`lease` shows whether the module is held, `diagnostics[]` identifies specific problems, and `next_action`, when present, points to a follow-up check.
That means the repository does not merely tell an agent what is wrong; it prescribes which verification step should happen next.
The difference matters because one `state` call can substitute for dozens of tribal-knowledge rules.

KubeDojo's `agents_extensions/` holds the project's curriculum rules and skills. The pinned `lu-machinery` release supplies shared fleet operations such as orientation, dispatch, and review. The deployment procedure in `agents_extensions/README.md` explains how the two fit together.
The root instructions can stay short when they point to the maintained procedure for each task. An agent editing a lesson can find the curriculum rules without loading fleet coordination instructions.

## Layer-by-layer design rubric

You can evaluate your repository design with this matrix and a live check list, because every row should point to a source file and a command that proves the claim before work starts.

```text
+--------------------+-------------------------+--------------------------+-------------------+
| Layer              | Design indicator         | Evidence check            | Failure signal     |
+--------------------+-------------------------+--------------------------+-------------------+
| Orientation         | One file gets you started| bootstrap check passes    | repeated clarifications |
| Memory              | Instructions are layered  | nested memory load         | conflicting rules |
| Content             | docs map stays current   | versioned docs links       | stale copy/paste |
| Feedback            | run-time state is exposed | API/state endpoint query   | silent failures |
| Governance          | exceptions are explicit   | review notes + logs        | silent rule drift |
+--------------------+-------------------------+--------------------------+-------------------+
```

## Designing for scale across many issue types

Small repos can get away with one file.
Large repos need more shape and often explicit ownership boundaries so that growth does not blur what each layer guarantees.

### Multi-team pattern

Each team gets scoped docs.
Global rules stay small.
Scoped rules override global where local scope is explicit.

### Multi-model pattern

Different AI models and tools parse instructions differently.
Keep stable commands and names consistent.
This reduces model-specific variance.

### Multi-runtime pattern

One run happens locally.
One run happens in CI.
One run happens in reviews.
The repository should emit the same expected state to each runtime.

## Practical contract artifacts you should build

A mature repository has at least these artifacts:

1. **Navigation card**: where to start.
2. **Execution card**: what to run and when.
3. **Risk card**: what not to do.
4. **Recovery card**: where to check failures and how to restart.
5. **Closure card**: what constitutes a successful run.

Each card can live in docs or in command output, but links should exist from bootstrap files.

## Avoiding instruction debt

Instruction debt accumulates in three ways and each accumulation pattern can hide a recurring source of run-time failure until it compounds over multiple issues.

- one-time task assumptions copied into baseline rules,
- outdated historical incident notes left in bootstrap,
- duplicate instruction copies in multiple files.

When debt is high, agents do not get confused because they cannot parse ambiguity.
They act on ambiguity, and the same uncertainty leaks into execution order, branch decisions, and check sequencing.

To prevent debt, require ownership tags and a migration path. Every scoped instruction file should define who owns it, how often it is reviewed, and what explicit migration route replaces it when stale evidence appears.
For example:

- Owner: module maintainer,
- Reviewer: quality reviewer,
- Expiry review date,
- Migration note.

## Repository engineering as a social contract

This is technical and social.
Agents are not replaced by this process.
Humans still decide architecture, ownership, and quality.
The engineering work is to let humans make those decisions once and let agents execute repeatedly.

A repo that talks back to an agent creates better collaboration because:

- humans spend less time repeating context,
- agents spend less time rediscovering policy,
- and failures are easier to diagnose.

## The design exercise: map this repo to four layers

Try this for your own repository.
For each layer, fill one sentence that names who owns the layer, where it is checked, and what happens if validation fails.

- **Layer 0**: what file always loads and why.
- **Layer 1**: what file scopes by folder and who owns it.
- **Layer 2**: where role-specific behavior and tool choices live.
- **Layer 3**: where current-run state and telemetry are published.

Then add at least one check command per layer.
Keep those commands in bootstrap or scripts so they can be run without opening unrelated folders.

## Did You Know

- Repositories that survive long AI-first programs keep boot instructions short and keep deep context in linked `docs/`.
- The most stable failure signals come from scripts and APIs, not from prose that is not tied to checks.
- Progressive disclosure is usually more reliable than comprehensiveness because it reduces context collisions between tools and teams.
- A reusable agent repository surface uses nested files, explicit links, and explicit state endpoints at every scale.

## Common repository mistakes and anti-patterns are most useful when ranked by how quickly they break agent reliability.

The following table is diagnostic. Use it as a practical pre-merge audit before onboarding a new task, because it catches the same anti-patterns that produce repeated stale failures.

## Common Mistakes and the failure paths they create when instruction layers become inaccurate

| Mistake | Why it harms agents | Typical symptom |
|---|---|---|
| One giant AGENTS file without sections | Overload and ambiguous priority | Agents skip critical constraints |
| No nested instruction overrides | Global rules override local needs silently | Team-specific tasks fail for local conventions |
| Instructions duplicated in many places | Conflicting stale copies | Different runs contradict each other |
| `docs/` used as dumping ground | No stable index of truth | Agents open wrong file repeatedly |
| No machine-readable state surface | Hidden failures remain silent | Repetition of same fix loop |
| Generated artifacts mixed with source docs | Noise in search results | Agents ingest garbage context |
| No periodic review for instruction files | Context drift becomes systemic | Outdated policy appears “current” |

## What a repo surface should contain in this module’s scope

This module focuses on a practical design bundle:
Use these four points as a minimal proof of readiness before claiming a repository instruction stack is deployable.

- a compact repository-level map,
- a scoped memory hierarchy,
- structured `docs/` records,
- and operational feedback endpoints.

For learning, this means the minimum implementation is:

- one root bootstrap file,
- one hierarchical memory file,
- one set of structured docs,
- one quality check,
- one health check,
- and one escalation route.

A useful rule is that each of those six items should point to at least one concrete file, and each target should have a failure mode that is testable in the next shell command.
If the route to escalation disappears, the design is not ready for distributed agents because there is no deterministic handoff path.

## Design patterns for AGENTS-like files

Use the following layout pattern, and preserve it as a reusable audit template for future modules.

The pattern above should remain explicit and actionable: a root map, a stable invariant block, and a runtime route block.
That gives maintainers a consistent audit trail that can be checked by both people and agents without reverse-engineering each module.

```text
# Root map
- What this repo is,
- how agents should start,
- where deeper docs live,
- where checks are run.

# Stable invariants
- branch policies,
- required checks,
- code organization constraints.

# Runtime route
- relevant APIs,
- health endpoints,
- review path.
```

Use this boundary so transient or speculative material does not become permanent contract surface by default, especially while experiments and temporary constraints are being evaluated.
Do not include:

- ephemeral one-off issue details,
- deep technical history,
- and long unowned troubleshooting transcripts.

## Checklist design for maintainers

A concise maintainability checklist for repository engineering:
This list should be reviewed every sprint because one outdated assumption can disable entire automation flows.

1. Is the entrypoint short enough to read quickly?
2. Are command paths explicit and deterministic?
3. Are temporary notes scoped to tasks?
4. Are generated directories explicitly excluded?
5. Is there a “next step after failure” route?
6. Is the docs index discoverable from bootstrap files?
7. Are layered files mutually consistent?

If any answer is no, file triage is required and you must update the section owner before continuing task execution.

## How to design this for a real team in one week

Week 1:
Run this as an operational micro-plan where each day either narrows ambiguity or eliminates stale contract risk.

- Day 1: inventory existing rules and duplicates.
- Day 2: define map-only root AGENTS/CLAUDE.
- Day 3: move stable facts into docs structure.
- Day 4: split nested scoped instructions.
- Day 5: expose state and health commands.
- Day 6: add missing review surfaces.
- Day 7: run checks and collect first failure pattern.

Week 2 and beyond:
Use these cycles to make stale checks, ownership updates, and stale command cleanup part of normal team rhythm.

- add stale checks,
- add ownership metadata,
- add automated reminder to remove stale sections.

## Knowledge as reusable modules

A repository designed for agents should support both quick start and deep dives.
A quick start path gives short-term speed.
A deep-dive path gives long-term correctness.

Quick-start path:
Use this path when the repo is first loaded and you need a deterministic confidence baseline before any content edits.

- check the branch and local changes with `git status --short --branch`,
- read the task and check live state when the workflow requires it,
- open module index,
- run module checks.

Deep-dive path:
Use this path when behavior changes, review disputes, or stale files suggest that the baseline contract no longer matches observed execution.

- inspect review history,
- inspect instruction deltas,
- inspect pipeline status,
- and trace failure sequences across runs.

## The “if not represented, enforce” rule

If an expectation affects behavior, and the repo cannot represent it in a file or command, the expectation is probably not enforceable.
Enforceability is what turns human preferences into machine trust.

A non-enforced expectation is still useful context but not operational truth, because models need explicit commands to move from documentation to reliable action.

## Designing for portability across model families

Different models and frameworks load context differently.
You can reduce variance by using:

- concise L0 instructions,
- stable file names,
- low churn for bootstrap,
- deterministic check commands,
- and explicit state surfaces.

This matters in mixed-model workflows and in multi-tool review loops where one model may prioritize narrative and another may only act on check outcomes.

## How to express model-agnostic contracts

Do not write instructions as one tool’s command syntax.
Write them as behavior expectations and expected states.
For tool specifics, provide per-tool examples as examples, not as only definitions.

For example:
Use this section to avoid syntax-driven instruction lock-in and keep behavior expectations stable across tooling.

- “Do not run commands that mutate hidden state without a rollback plan.”
- then optionally:
  - “For Git, use standard commands in review mode.”
  - “For local APIs, use explicit endpoints.”

The behavioral contract stays model-agnostic and remains valid even as tool commands or execution clients evolve.

## Operationally safe defaults

The safest defaults for repository engineering are conservative.
If uncertain, prefer explicitness over coverage, because explicit checks and explicit recovery paths reduce silent failure than heuristic assumptions do.

- explicit exclusions,
- explicit scopes,
- explicit update paths,
- and explicit failure messages.

## Practical lab: design a two-layer bootstrap for this module

Design this lab with the existing scaffold, then swap the checker from string-matching to parsing.
Keep `repo-contract.md` human-readable, but force the paths in the script to be machine-verifiable.

To keep this useful outside a teaching environment, this parser script must be deterministic:
it reads `repo-contract.md`, extracts only layer markers `L0`–`L3`, checks each referenced file/path against the repository root, and exits with a clear, machine-checkable code.
The check is intentionally narrow so it catches stale references early and does not pretend to validate every arbitrary line in the contract file.
When a path passes, it prints `OK EXISTS <path>`.
When a path is missing, it prints `MISSING <path>`.
When the contract manifest itself is absent, it emits `MISSING_FILE repo-contract.md`.
The exit code is the contract you can wire directly into CI gates or pre-commit guards.

1. Create `repo-contract.md` with explicit layer references using a parseable format that can be parsed reliably by `awk` and validated as a contract before any content mutation begins.

```md
# Repository Run Contract

- L0: AGENTS.md
- L1: CLAUDE.md
- L2: agents_extensions/claude/rules/
- L3: src/content/docs/ai/ai-engineering-foundations/module-2.2-repository-engineering-for-agents.md
```

2. Create `scripts/print-run-contract.sh` with this parser-oriented version, keeping strict outputs and deterministic exit codes so each failure is visible before patch execution starts.

```bash
#!/usr/bin/env bash
set -euo pipefail # strict shell execution keeps contract checks deterministic for pre-write guards in this lab

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_CONTRACT="${ROOT_DIR}/repo-contract.md" # stable manifest path shared across all checks

if [[ ! -f "${REPO_CONTRACT}" ]]; then
  echo "MISSING_FILE repo-contract.md" >&2
  exit 2
fi

declare -a refs
mapfile -t refs < <(
  awk '/^- [Ll][0-3]:[[:space:]]*/ {gsub(/^- [Ll][0-3]:[[:space:]]*/, "", $0); print $0}' "${REPO_CONTRACT}"
)

missing=0
for ref in "${refs[@]}"; do
  if [[ -e "${ROOT_DIR}/${ref}" ]]; then
    echo "OK EXISTS ${ref}"
  else
    echo "MISSING ${ref}"
    ((missing += 1))
  fi
done

if (( missing > 0 )); then
  echo "contract_check: FAILED with ${missing} missing references" >&2
  exit 1
fi

echo "contract_check: PASSED"
```

3. Set one explicit stale-rule policy:

Before editing, run `bash scripts/print-run-contract.sh`.
Success is defined as exit `0`, exactly one `contract_check: PASSED`, and every contract entry rendering as `OK EXISTS`.
Failure must stop execution immediately:

- If `repo-contract.md` is missing, the script exits `2` with `MISSING_FILE repo-contract.md`.
- If at least one contract reference is stale, the script exits `1`, prints one or more `MISSING <path>` lines, and prints `contract_check: FAILED with N missing references`.
In both cases, the task must not continue until references are repaired and the script is clean.
This failure semantics is deliberate: the contract itself becomes a precondition check, not a postmortem note.
You can still run patch edits after the script passes, but not before.

Why this is a stronger pattern than string matching:
string checks are easy to pass with formatting drift.
parsing enforces that the contract format itself is understood by the verifier, so every line under `L0`–`L3` is validated consistently.
Apply the same principle to startup checks. Decide which conditions each task requires and verify those conditions before making changes.

Suggested extension for lab rigor (optional) is to make stale checks enforceable over time.
You can add a duplicate L-level key detector, require that every referenced file exists and is non-empty, and emit a deterministic warning for trailing slash normalization.
These checks are cheap, mechanical, and give you one concrete hook for future "proof of maintenance" tasks in the same module.

Expected failure transcript when `CLAUDE.md` disappears:
A short failure run should look like:

This pre-write transcript is expected and should stop the task before mutation because stale references are a hard gating condition, not a warning.


```text
$ bash scripts/print-run-contract.sh
MISSING CLAUDE.md
contract_check: FAILED with 1 missing references
```

If the contract file itself is removed, the transcript should look like:

If this happens, execution is blocked and must be treated as a hard pre-condition failure until the manifest is restored.

```text
$ bash scripts/print-run-contract.sh
MISSING_FILE repo-contract.md
```

Both transcripts are expected failure paths during the pre-write gate, and both should block automated patch execution until corrected.

This means you can keep `repo-contract.md` readable for humans and still keep enforcement strict for agents because both readability and gate correctness are part of the same contract, just represented at different layers.

## Design challenge: avoiding false safety in instructions

A false-safe instruction is one that looks strict but does not stop bad outcomes, especially when it defines behavior without defining deterministic recovery, validation gates, and clear failure handling.
That happens when:

- constraints reference files that no longer exist,
- examples show only happy path,
- and checks are not wired.

Use this audit phrase while reviewing any instruction layer:

“Can this rule be violated without failing a check?”

If yes, it is informative but not enforceable, so it needs a check, gate, or explicit exception rule before it is treated as instruction.

## Knowledge Check

### 1) Which statement best describes progressive disclosure for repository legibility?
<details>
<summary>Which statement best describes progressive disclosure for repository legibility?</summary>

A) Place all instructions in one file so agents never need to jump around.
B) Separate short-lived details from stable contracts so that agents can load the right layer first.
C) Keep everything in generated logs because those are always up-to-date.
D) Store everything in PR comments so it is always visible.

**Correct answer: B** because stable contracts should be short and frequently reused, while temporary rules remain scoped and on-demand. **A is wrong** because it increases ambiguity and reduces signal strength. **C is wrong** because logs are often noisy and not stable. **D is wrong** because PR comments are not a contract surface for every run.
</details>

### 2) Which layer should host high-frequency operational policies?
<details>
<summary>Which layer should host high-frequency operational policies?</summary>

A) A single root AGENTS file with every possible constraint, regardless of longevity.
B) Layered scope files plus a stable root map that links to them.
C) Only ephemeral task prompts that reset every session.
D) A generated changelog only.

**Correct answer: B** because stable, repeatable policies need predictable location and links from root, while prompts handle task-specific details. **A is wrong** because it becomes stale and verbose. **C is wrong** because ephemeral prompts cannot represent durable governance. **D is wrong** because changelogs are historical and not operational bootstrap.
</details>

### 3) Why is a `docs/` structure considered a system of record in this module?
<details>
<summary>Why is a structured `docs/` considered a system of record?</summary>

A) Because it can store all agent instructions in raw binary format.
B) Because it is the first place every agent reads automatically.
C) Because it can hold durable, reviewable, and versioned instructions that can be linked and revised intentionally.
D) Because it is required by every model family and automatically replaces all rules.

**Correct answer: C** because `docs/` provides durable structure, traceable updates, and reviewability. **A is wrong** because the content model remains human-readable text, not binary instructions. **B is wrong** because bootstrap can include other files, and first load does not guarantee completeness. **D is wrong** because replacement is context-specific and unsafe.
</details>

### 4) What is the most accurate interpretation of “repo talks back” in this context?
<details>
<summary>What is the most accurate interpretation of "repo talks back"?</summary>

A) The repo should always print friendly messages.
B) The repo should expose status, checks, and constraints that can be observed by agents before and after action.
C) The repo should block all automated edits.
D) The repo should avoid runtime signals to reduce noise.

**Correct answer: B** because reproducible feedback channels are what allow agents to adapt actions in a safe loop. **A is wrong** because decorative output without operational signals is insufficient. **C is wrong** because blocking all automation is the opposite of efficient workflow. **D is wrong** because observability is needed for reliable operations.
</details>

### 5) Which item best fits a stale-rule anti-pattern?
<details>
<summary>Which item best fits a stale-rule anti-pattern?</summary>

A) A rule reviewed weekly with ownership and migration notes.
B) A command copied into one file years ago and never updated despite changed tooling.
C) A root file that links to scoped documents for deeper detail.
D) A task prompt that references a current issue branch.

**Correct answer: B** because stale copied rules mislead agents and undermine trust. **A is wrong** because it implies active maintenance. **C is wrong** because it supports discoverability and freshness. **D is wrong** because task prompts are temporary, not stale base policy.
</details>

### 6) In this module’s design model, what should avoid being in a permanently loaded file?
<details>
<summary>In this module’s design model, what should avoid being in a permanently loaded file?</summary>

A) Stable governance and branch constraints.
B) One-off issue notes.
C) Scope links to module-specific docs.
D) Core execution checks.

**Correct answer: B** because one-off issue notes become stale and should be task-local. **A is wrong** because stable constraints belong in always-loaded references. **C is wrong** because scope links are high-value discoverability paths. **D is wrong** because core checks are central to safe operation and should be discoverable.
</details>

### 7) Which statement reflects the best ownership pattern for instruction files?
<details>
<summary>Which statement reflects the best ownership pattern for instruction files?</summary>

A) Only one person owns every instruction file globally.
B) No ownership is needed as long as files are descriptive.
C) Each file has a scope, owner, and refresh path, with nested files overriding conflicts.
D) Root ownership is enough for all scoped folders.

**Correct answer: C** because scope plus ownership plus refresh policy reduces drift and clarifies update responsibility. **A is wrong** because that model becomes a bottleneck and misses domain ownership. **B is wrong** because ownership enables consistency and maintenance cadence. **D is wrong** because scope-level conflicts require delegated and explicit ownership.
</details>

## Hands-on Practical Exercises

- [ ] Audit your repo root bootstrap by listing the first five files loaded before any task work, then mark which are stable L0 and which are scoped L1.
- [ ] Build a `Repository Legibility Sheet` in one markdown file with four layers, links, and one health-check command for each layer.
- [ ] Add one `docs/` entry as a durable contract for agent execution and one explicit exclusion list for generated artifacts.
- [ ] Define a short failure feedback loop: identify one endpoint or command that should run after every task and explain how it changes next actions.
- [ ] Draft a stale-rotation rule that assigns an owner and cadence to each bootstrap and scoped instruction file.

## Next Module

*Next module coming soon.*

## Sources

- [Harness engineering (OpenAI)](https://openai.com/index/harness-engineering/)
- [Give Claude context with CLAUDE.md (Anthropic Support)](https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts)
- [Claude Code memory model (Anthropic docs)](https://docs.anthropic.com/en/docs/claude-code/memory)
- [Custom instructions with AGENTS.md — Codex (OpenAI Developers)](https://developers.openai.com/codex/guides/agents-md)
- [AGENTS.md project format](https://agents.md/)
- [AGENTS.md repository (GitHub)](https://github.com/agentsmd/agents.md)
- [AGENTS.md example source file](https://raw.githubusercontent.com/agentsmd/agents.md/main/AGENTS.md)
- [KubeDojo CLAUDE.md](https://raw.githubusercontent.com/kube-dojo/kube-dojo.github.io/main/CLAUDE.md)
- [KubeDojo agent instructions](https://github.com/kube-dojo/kube-dojo.github.io/blob/main/AGENTS.md)
- [KubeDojo local API recipes](https://github.com/kube-dojo/kube-dojo.github.io/blob/main/scripts/agent_onboarding.md)
- [KubeDojo agent extension deployment](https://github.com/kube-dojo/kube-dojo.github.io/blob/main/agents_extensions/README.md)
- [KubeDojo module-quality rules](https://raw.githubusercontent.com/kube-dojo/kube-dojo.github.io/main/agents_extensions/claude/rules/module-quality.md)
- [KubeDojo new-content checklist](https://raw.githubusercontent.com/kube-dojo/kube-dojo.github.io/main/agents_extensions/claude/rules/new-content-checklist.md)
- [Starlight sidebar architecture](https://starlight.astro.build/guides/sidebar/)
- [Starlight frontmatter reference](https://starlight.astro.build/reference/frontmatter/)
- [Astro routing guide](https://docs.astro.build/en/guides/routing/)
- [KubeDojo configuration file](https://raw.githubusercontent.com/kube-dojo/kube-dojo.github.io/main/astro.config.mjs)
- `scripts/print-run-contract.sh` in this module is intentionally contract-driven: `repo-contract.md` is the root contract file, and its references are the canonical list the script checks before running.
