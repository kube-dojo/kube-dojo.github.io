---
name: drive-epic
description: >-
  Model-agnostic playbook for driving one KubeDojo GitHub epic end-to-end over
  dispatch_smart and the local briefing API. Coordinates the curriculum site
  (kube-dojo/kube-dojo.github.io) with the Killercoda labs sister repo
  (kube-dojo/kubedojo-labs). Use when launched as an epic driver, told to
  "drive this epic", or when the user names an epic such as #2272.
---

# Drive a KubeDojo epic

You are driving **one epic** (for example `#2272`). You are **not** a clerk
waiting on a single PR, and you are **not** a solo implementer of the whole
program. Dispatch exists so the fleet does the volume; you own judgment:
what is next, which family×harness should do it, whether the artifact
actually worked, and what residual remains.

**Golden rule: this skill teaches method, never the live roster.** Caps,
models, and who is healthy change. Read them fresh — never from memory:

- `GET http://127.0.0.1:8768/api/orient` and `/api/briefing/session?compact=1`
- [[dispatch-router]] — activity × lane matrix and `dispatch_smart` commands
- `codexbar usage --provider both --no-color` (plus `cursor` / `antigravity`)
  before a wave of 3+ dispatches or any burst to one lane

If a claim (count, SHA, gate, cap, lab pass/fail) is not in fresh tool output,
**stop and run the tool**.

Sister-repo details (Killercoda layout, G04, hosted vs local evidence):
[dual-repo.md](dual-repo.md).

---

## The loop (every cycle)

### 0. Orient

```bash
KUBEDOJO_ISSUE=<N> bash scripts/cold-start.sh   # or omit env for standalone
curl -sS --max-time 3 "http://127.0.0.1:8768/api/orient"
curl -sS --max-time 3 "http://127.0.0.1:8768/api/pipeline/leases"
curl -sS --max-time 3 "http://127.0.0.1:8768/api/git/cleanup"
```

Know the epic number, both remotes, and the latest `.agent/session-state/`
handoff (read the file only if briefing leaves a narrative gap). Drain the
bridge inbox for this seat:

```bash
.venv/bin/python -m scripts.ai_agent_bridge inbox --for "$SESSION_HANDOFF_AGENT"
```

(`gemini` is the CLI default; pass the seat that is actually driving.)

### 1. Inventory the epic (binding)

Quote open-child counts from GitHub, not from memory:

```bash
gh issue view <EPIC> --repo kube-dojo/kube-dojo.github.io
# children:
gh api graphql -f query='query($n:Int!){repository(owner:"kube-dojo",name:"kube-dojo.github.io"){issue(number:$n){subIssues(first:50){nodes{number title state}}}}}' -F n=<EPIC>
gh issue list --repo kube-dojo/kubedojo-labs --state open --limit 30
gh pr list --repo kube-dojo/kube-dojo.github.io --state open
gh pr list --repo kube-dojo/kubedojo-labs --state open
```

**Step 0 of any dispatch:** `gh pr list --state all --search "<issue-nr>"`.
An open issue ≠ unfixed.

### 2. Dispose every open child

For each open issue, exactly one of:

- **in_flight** — named PR/task id + head SHA
- **dispatch now** — ROUTING_CARD + capacity evidence
- **named hold** with one code:
  `dependency_blocked | authoring_wip_cap | review_wip_cap | ci_capacity |
  worktree_wip_cap | disk_capacity | human_decision | no_ready_work |
  needs_operator_go`

Silence is a driver failure. Ending a turn with only "waiting on review/CI"
and no fill/disposition is forbidden.

**No fabricated done.** Never invent acceptance thresholds. Quote the tool
residual count before "done"; `residual > 0` requires a next dispatch in the
same session. Do not close a bilingual issue on EN-only work.

### 2c. No idle paid lanes

Precedence: correctness → safety/resource bounds → critical path →
utilization. After any dispatch or review ask, **before** holding, fill every
free *compatible* lane. Idle free lane + ready item = utilization failure.
Never manufacture busywork. Disk wins: `df -h` + `git worktree list` before
fan-out; reap first.

Honor the **active epic's** stated worktree/disk cap (quote it from the
issue body — do not remember a number). Labs worktrees live in
`kubedojo-labs/.worktrees/` and count separately — still reap merged ones.
Remove local `dist/` after validation.

### 3. Route by activity × live capacity

Load [[dispatch-router]]. Then quote CodexBar before picking a seat:

```bash
codexbar usage --provider both --no-color
codexbar usage --provider cursor --no-color
codexbar usage --provider antigravity --no-color
```

**CAPACITY_CARD** (required in the brief or issue comment):
`pick=… avoid=… free=… session_window=…`

Rules:

1. Prefer cool + idle + fit. Do **not** habit-route to Codex while
   `Pace: … deficit` / `will not last to reset` and a cooler seat exists.
2. **This driver session is a seat.** If you are Cursor, do **not**
   `dispatch_smart --agent cursor` (deadlock / quota contention). Same for
   any seat you occupy.
3. `--agent gemini` is retired — Google lane is **`--agent agy`**.
4. China-hosted providers (direct DeepSeek, GLM/z.ai) are **local only**;
   never from GH Actions.
5. Hard cap **3 parallel rewrites**. Mix families for 3+ parallel reviews.
6. Warn the operator before 3+ parallel **or** 5+ sequential to one agent
   in 10 minutes.

### 3-routing. ROUTING_CARD (no card = no dispatch)

Before every implement `dispatch_smart`:

```
ROUTING_CARD
issue: #<n>  repo: kube-dojo/<site|labs>
owned_paths: …
acceptance_cmd: …
model_x_harness: <agent> / <task_class> / <model>
why: …
alternatives_considered: (≥2)
capacity: (quoted CodexBar + avoid list)
parallel_free_seats: …
```

Default pattern: **advisor/driver briefs → heap/practical worker**. Do not
spend frontier models on lockfiles, pointer publishes, or smoke jobs.

After ≥3 implement dispatches this session, require ≥2 agents **and** ≥2
task-classes/tiers, or a written `NOTE: fleet_breadth` with tool-backed
blockers.

### 4. Dispatch

Workers use **worktrees**, never primary `main`.

Curriculum:

```bash
git worktree add .worktrees/<name> -b <branch> main
.venv/bin/python scripts/dispatch_smart.py <search|edit|draft|review|architect> \
  --agent <lane> --worktree .worktrees/<name> --task-id <id> \
  --prompt-file - <<'BRIEF'
… numbered brief …
BRIEF
```

Labs (sister repo — different git root):

```bash
git -C /path/to/kubedojo-labs worktree add .worktrees/<name> -b <branch> main
# dispatch with cwd = that worktree; do not mix trees in one PR
```

Brief must be literal-complete: owned paths, acceptance command, budget
(`<20 files`, default **≤200 aggregate lines** unless the issue sets another
reviewed budget), "find and fix ALL occurrences of this pattern, not just
the listed lines", **no auto-merge**, conventional commit + PR.

Codex danger-mode always needs `--worktree`. Content drafts that must not
SIGKILL: `draft` + `--timeout 3600`. Agy implement/write is danger-mode
(headless permissions).

Run dispatches in the background; read
`logs/dispatch_responses/<task-id>.txt` when the wrapper finishes.
**Do not** `until grep; sleep` watchers. Headless Claude liveness = the
session JSONL mtime/`tail -1`, not `ps`.

Stagger same-lane spawns ~10s. Drain inbox again immediately before each
dispatch.

### 5. Settle

Terminal success for `dispatch_smart` is a zero exit **and** a PR URL or
stated residual. Before declaring a dispatch dead: `gh pr list --state open`,
then the worktree for finished-but-unpushed work.

This wait is a fill window, not an idle period.

### 6. Cross-family review (discussion ≠ review)

Load [[cross-family-reviewer]]. Review of record is **independent and
cross-family**, **exact-head**: attested model, `VERDICT: APPROVE` (or
`NEEDS_CHANGES`), SHA equals current PR head. Post as a **PR comment**
(do not `gh pr review --approve` — same GitHub identity owns both sides).

```bash
.venv/bin/python scripts/dispatch_smart.py review --agent <other-family> \
  --worktree .worktrees/<name> --task-id review-<N> --prompt-file - <<'BRIEF'
Cross-family review of PR #<N> at head <SHA>. VERDICT + findings.
BRIEF
```

Read the review **content**, apply deltas, re-probe gates yourself. If the
head moves, CF is stale — re-run before merge. Ground-check every finding
(web-verify volatile facts; `verify_review.py` for quote/line accuracy).

Do **not** use a Gemini Flash-class model as a code/lab reviewer.

### 7. Merge

PRs only. Never commit or merge on primary `main`.

Order:

1. Independent exact-head CF on the current SHA
2. Required CI green on **that same head**
3. Then merge (`gh pr merge --rebase` unless the issue/PR says squash)

Never treat `gh pr merge --auto` as a substitute for CF. Blocking CI red →
never `--admin`. A driver merges **its own lane's** PR after CF+CI; flag
another lane's PR rather than merging it.

`npm run build` for content/Astro changes runs from the **primary checkout**
against the intended revision — not inside `.worktrees/` (symlink
`node_modules` is one level too shallow).

### 7a. Post-merge cleanup (mandatory)

A merge is not done until residue is gone:

1. Confirm merge SHA; close the issue or prove residual on the parent.
2. Remove the dispatch worktree (`git worktree remove` after processes leave).
3. Delete the local branch if it remains; `git fetch --prune`;
   `git worktree prune`.
4. Prove with `git worktree list` and `df -h`.

Do not merge obsolete drafts merely to clear disk.

### 7-rollout. Local vs hosted proof

| Kind | Driver owns? |
| --- | --- |
| Local proof (API smoke, `npm run build`, scenario `test-scenario.sh`) | **Yes** |
| Billable cloud / AWS / GCP / Azure provisioning | **Only on present-tense operator GO** |
| Killercoda **hosted interactive** smoke | Record as residual unless platform access exists |
| Production Pages cutover | CI deploy after merge; do not claim prod HA |

Missing local proof on a user-visible change is incomplete closeout. Issue
text sets **scope**, not authorization to spend money.

### 8. Handoff

Load [[session-handoff-writer]]. Write a lean Markdown brief to
`.agent/session-state/YYYY-MM-DD-session-NN-<topic>.md` and update the live
index `.agent/STATUS.md` (`## TODO` + `## Blockers`). Never commit handoffs.

Drain inbox once more before signalling done.

---

## Dual-repo split (always)

| Concern | Repo | Typical paths |
| --- | --- | --- |
| Curriculum prose, routes, site gates | `kube-dojo/kube-dojo.github.io` | `src/content/docs/`, `scripts/quality/`, Astro |
| Killercoda scenarios | `kube-dojo/kubedojo-labs` | flat `<id>/index.json` + `stepN/` at **repo root** |
| Lab *buttons* / `lab.url` | main repo | must match `https://killercoda.com/kubedojo/scenario/<id>` |
| Scenario CI harness | labs `#1` | Ubuntu vs Kubernetes lanes are separate acceptance |

One PR, one repo. Cross-link issue numbers (`#2276` ↔ labs `#2`). File
presence is not execution acceptance. Hosted Killercoda HTTP 200 ≠ learner
scenario. See [dual-repo.md](dual-repo.md).

---

## Evidence standard (content-upgrade epics)

Copied from the live epic body when driving #2272 — do not weaken it:

- Load-bearing facts need a locator, verification date, applicability, and
  uncertainty. A URL is not proof the claim is supported.
- Never fabricate dialogue, incidents, benchmarks, execution results, or
  learner feedback.
- Label synthetic teaching examples. No forced mystery or gamification.
- Unavailable verification stays incomplete. Preserve good content;
  retain/revise/expand — no rewrite quota.
- PR counts are not completion percentages. Distinguish accepted / partial /
  untouched / evidence-unavailable.
- Default diff budget: **<20 files, ≤200 aggregate lines**. Coherent lab
  scenarios need an **explicit per-issue budget** plus reviewer endorsement
  (a full Killercoda tree will not fit 200 lines).

English-first scheduling (when the epic says so) does **not** waive
Ukrainian obligations. Do not introduce UK regressions in shared
code/routes. Translation volume uses the UK roster in [[dispatch-router]]
(author + RAG calque gates + required reviewer families — live data).

---

## Per-seat delta

Same playbook. Live **model ids and task-class defaults** are
[[dispatch-router]] + CodexBar — do not freeze them here. §2c binds every seat.

| Seat | Constraint that is not a roster pin |
| --- | --- |
| **Cursor** | If **you** are the Cursor driver, do not `dispatch_smart --agent cursor`. Attest `resolved_model` when CF identity matters. A CLEAN PR with CF APPROVE is merged the same turn. |
| **Claude** | Cheapest Claude *review* is inline. Headless for author lanes or an independent context on the hardest 1–2 reviews. Session (5h) window beats weekly. |
| **Codex / GPT** | Skip the lane when CodexBar shows deficit and a cooler eligible seat exists. Review always danger + worktree. |
| **AGY (Google)** | `--agent agy` (gemini-cli retired). Check **both** Gemini pools. Never Flash-class for code/lab CF. Re-prove write on the live write-tier before load-bearing. |
| **DeepSeek** | Local only (China-host). Ground-check numbers/schemas. |
| **Grok** | Native grok CLI = code, complete diffs, no file tools. Content-class Grok is a different harness — resolve in dispatch-router. Driver-only if seated: no multi-file heroics. |
| **GLM / OpenCode** | Local only. Never CI. |

---

## Escalate — do not decide solo

1. Architecture / process / gate-threshold changes
2. Contested CF (author vs reviewer, or two reviewers split)
3. Fragile-fix whose right layer is unclear
4. Billable infrastructure or production cutover without present-tense GO
5. Repo-wide safety interruption of another lane (linter/Python-version
   bumps, generated-state commits, silent gate weakening)

Gates passing is necessary, not sufficient — verify the real artifact
renders or the scenario `verify.sh` actually runs.

## This skill is NOT

- A replacement for [[dispatch-router]] or [[curriculum-orchestrator]]
- A single-module writer (use [[curriculum-writer]])
- Authority to weaken quality gates, skip CF, or push `main`
- A license to provision AWS/GCP/Azure because a lab page mentions them
