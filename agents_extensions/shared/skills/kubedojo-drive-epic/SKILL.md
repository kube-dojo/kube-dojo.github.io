---
name: kubedojo-drive-epic
description: >-
  KubeDojo overlay for the installed drive-epic skill. Adds the curriculum
  site (kube-dojo/kube-dojo.github.io) and Killercoda labs
  (kube-dojo/kubedojo-labs) rules that the fleet skill does not carry. Use
  together with drive-epic when driving a KubeDojo epic such as #2272.
---

# Drive a KubeDojo epic (overlay)

This file is a **KubeDojo-only overlay**. The method comes from the installed
lu-machinery release; this overlay only adds what is specific to KubeDojo.
When the two disagree, the installed release and the rules core win.

| Concern | Source of truth (installed release) |
| --- | --- |
| Driver loop, orientation, queue, routing, handoff | `drive-epic` skill and its references |
| Cold start and plane state | `.venv/bin/python -I -m lu_machinery.fleet_comms cold-start-board` and `plane-status` |
| Launching the KubeDojo lane driver | `lu_machinery/start-kube-dojo-driver.sh` (lane `kube-dojo`) |
| Dispatch | `"$LEARN_UKRAINIAN_PYTHON" -m lu_machinery.dispatch dispatch --repo kube-dojo --worktree ...`, with `LEARN_UKRAINIAN_PRIMARY_REPO_ROOT` set to the machinery shared-state checkout (`agents_extensions/README.md`, "Apply and verify"); without it the dispatcher refuses |
| Review of record | `review-loop` and `local-code-review`; reviewer from `lu_machinery.review.closeout_cli resolve-reviewer` |
| Landing and closeout | `full-send` / `full-stop` (publisher `pr-merge`, `merge_closeout`) |
| Rollover and handoff | `thread-rollover` and the lane `handoff_note` |

Live roster, caps and routes are read fresh from the catalog and the
resolver, never from this file.

**Curriculum edits by Claude workers.** The KubeDojo content hook
`block-orchestrator-content-edits.sh` refuses Claude `Edit`/`Write` on
`src/content/docs/**` unless `KUBEDOJO_DISPATCHED=1`, and today only the legacy
`scripts/dispatch_smart.py` sets it; a Claude worker started by
`lu_machinery.dispatch` is refused. Until that exemption is migrated, route
curriculum edits one of these two ways (both take the brief as a file):

```bash
# Fleet route, non-Claude implementer; needs LEARN_UKRAINIAN_PRIMARY_REPO_ROOT.
"$LEARN_UKRAINIAN_PYTHON" -m lu_machinery.dispatch dispatch --repo kube-dojo \
  --agent codex --mode workspace-write --worktree --task-id <task-id> \
  --prompt-file <brief.md> --owned-path <path>
# Legacy route, temporary until census PR 7 retires it; the brief goes on stdin.
.venv/bin/python scripts/dispatch_smart.py edit --agent codex \
  --worktree .worktrees/<task> --new-branch <branch> - < <brief.md>
```

KubeDojo delivery and review notes: [delivery.md](delivery.md). Sister-repo details: [dual-repo.md](dual-repo.md).

## KubeDojo inventory

Quote open-child counts from GitHub, not from memory:

```bash
gh issue view <EPIC> --repo kube-dojo/kube-dojo.github.io
gh api graphql -f query='query($n:Int!){repository(owner:"kube-dojo",name:"kube-dojo.github.io"){issue(number:$n){subIssues(first:50){nodes{number title state}}}}}' -F n=<EPIC>
gh issue list --repo kube-dojo/kubedojo-labs --state open --limit 30
gh pr list --repo kube-dojo/kube-dojo.github.io --state open
gh pr list --repo kube-dojo/kubedojo-labs --state open
```

Before any dispatch, search both repositories for an existing PR on the issue
(`gh pr list --state all --search "<issue-nr>"`). An open issue is not proof
that the work is unfixed.

## KubeDojo completion criteria

A packet or child issue is complete only when all of these hold, on top of
the release Definition of Done:

1. Every acceptance criterion is met with evidence (commands, `verify_module`,
   rubric disposition, source locators), not "looks good" or "CI green".
2. Dual-repo: if the packet spans the site and `kubedojo-labs`, both sides
   meet their criteria or a named residual issue exists for the other repo.
3. English-only work does not close a bilingual or Ukrainian obligation, and
   it introduces no Ukrainian regression in shared routes.
4. Unrun labs stay `unknown`, never `pass`.
5. Epic or parent issues close only on their own completion criteria, never
   on one slice.

## Build gate

- Markdown-only content PRs: the required CI job "Astro build (render +
  schema)" is the build gate; do not run a local full-site build.
- Code, config, schema or Astro changes: one `npm run build` at a time, not
  on a loaded machine, from the primary checkout against the intended
  revision (a worktree's shallow `node_modules` layout does not build).
  Remove local `dist/` after validation.

## Dual-repo split (always)

| Concern | Repo | Typical paths |
| --- | --- | --- |
| Curriculum prose, routes, site gates | `kube-dojo/kube-dojo.github.io` | `src/content/docs/`, `scripts/quality/`, Astro |
| Killercoda scenarios | `kube-dojo/kubedojo-labs` | flat `<id>/index.json` + `stepN/` at **repo root** |
| Lab *buttons* / `lab.url` | main repo | must match `https://killercoda.com/kubedojo/scenario/<id>` |
| Scenario CI harness | labs `#1` | Ubuntu vs Kubernetes lanes are separate acceptance |

One PR, one repo. Labs worktrees live in `kubedojo-labs/.worktrees/` and count
against the epic's stated worktree and disk cap separately. Cross-link issue
numbers (`#2276` ↔ labs `#2`). File presence is not execution acceptance;
hosted Killercoda HTTP 200 is not a learner scenario. See
[dual-repo.md](dual-repo.md).

## Local vs hosted proof

| Kind | Driver owns? |
| --- | --- |
| Local proof (API smoke, `npm run build` for code/config/schema/Astro changes, scenario `test-scenario.sh`) | **Yes** |
| Billable cloud / AWS / GCP / Azure provisioning | **Only on present-tense operator GO** |
| Killercoda **hosted interactive** smoke | Record as residual unless platform access exists |
| Production Pages cutover | CI deploy after merge; do not claim prod HA |

Issue text sets **scope**, not authorization to spend money. A lab page that
mentions a cloud provider is not a licence to provision one.

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
- Fast-moving topics follow `.claude/rules/durable-vendor-content.md`.

English-first scheduling (when the epic says so) does **not** waive
Ukrainian obligations; Ukrainian work follows `.claude/rules/translation.md`.

## This overlay is NOT

- A replacement for the installed `drive-epic`, `full-send` or `review-loop`
- A single-module writer (use [[curriculum-writer]])
- Authority to weaken quality gates, skip independent review, or push `main`
