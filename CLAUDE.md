# CLAUDE.md

KubeDojo — free, open-source cloud native curriculum.

## Agent Orientation (first call on a cold start)

Fleet machinery (session start, context and compaction hooks, guards,
dispatch, review, landing, handoff) comes from the installed lu-machinery
release, deployed by `npm run agents:deploy` (see
[`agents_extensions/README.md`](agents_extensions/README.md)). This repository
keeps only the KubeDojo overlay: curriculum skills, content rules and content
hooks.

**Drivers:** load the installed `drive-epic` skill and the KubeDojo overlay
`kubedojo-drive-epic`. Orient with
`"$LEARN_UKRAINIAN_PYTHON" -I -m lu_machinery.fleet_comms cold-start-board` and
`"$LEARN_UKRAINIAN_PYTHON" -I -m lu_machinery.fleet_comms plane-status` (both
need `LEARN_UKRAINIAN_PRIMARY_REPO_ROOT`, below); the lane driver is launched by the release's
`start-kube-dojo-driver.sh`. Dispatch with
`"$LEARN_UKRAINIAN_PYTHON" -m lu_machinery.dispatch dispatch --repo kube-dojo --worktree ...`
with `LEARN_UKRAINIAN_PRIMARY_REPO_ROOT` set to the machinery shared-state checkout
(see [`agents_extensions/README.md`](agents_extensions/README.md#apply-and-verify)); without it the
dispatcher refuses.

**Issue-driven sessions:** read the GitHub issue verbatim first.

**Before you claim/fix/re-review curriculum work** (KubeDojo local API, `http://127.0.0.1:8768`):
- `GET /api/pipeline/leases`
- `GET /api/module/{key}/state`
- `GET /api/reviews?module={key}`

Optional situational check: `GET /api/content/coverage` or `GET /api/tracks/readiness`.
Start the local API with `./services.sh start api` (primary checkout) or
`.venv/bin/python scripts/local_api.py` when it is down; an unreachable API is unknown state.

## Agent Usage

- Don't spawn agents for work a single Grep/Read/Glob can do — it's slower and wasteful.
- Agents ARE worth it for genuinely parallel work and context isolation (large refactors, independent research).
- Batch direct tool calls in one message when possible (3 Greps > 3 agents).
- Keep sessions long (`/continue`) — cache hits are ~95% within a session.

## Decisions

High-leverage decisions (architecture, threshold freezes, contested reviews,
bets affecting 100+ modules) follow the installed rules core: consultation,
designated approval and independent review stay distinct, and discussion is
never a review of record. Pending decisions are recorded in
`docs/decisions/pending/`; scan it at cold start.

## Project Overview

**Website**: https://kube-dojo.github.io/ (Starlight/Astro)

**Site tabs**: Home | What's New | Fundamentals | Cloud | Certifications | Platform Engineering

**Tracks**:
- **Fundamentals** — Zero to Terminal, Everyday Linux, Cloud Native 101, K8s Basics, Philosophy & Design, Modern DevOps
- **Cloud** — Rosetta Stone, AWS/GCP/Azure Essentials (12 each), Architecture Patterns, EKS/GKE/AKS Deep Dives, Advanced Ops, Managed Services, Enterprise & Hybrid
- **Certifications** — CKA, CKAD, CKS, KCNA, KCSA, Extending K8s, 10+ tool certs
- **Platform Engineering** — Foundations (7 sections), Disciplines (12 sections), Toolkits (17 categories)

**Ukrainian translation**: ~40% (Prerequisites, CKA, CKAD). Files in `src/content/docs/uk/`.

> **HTML-first artifact policy:** see [`docs/migrations/html-first/plan.html`](docs/migrations/html-first/plan.html) — HUMAN-FACING orchestrator artifacts (audit reports, bug autopsies, batch summaries, PR review explainers) default to HTML. AI-consumed artifacts stay Markdown: dispatch briefs, **session handoffs** (re-reclassified AI→AI 2026-07-07 s196 — local agent state since PR #2247), STATUS.md / CLAUDE.md / `.claude/rules/` / memory.

## Session Workflow

1. **Orient via the installed release** (see *Agent Orientation* above). `STATUS.md` is the fallback when the API is down.
2. Use `scripts/prompts/module-writer.md` for new modules
3. Send completed work through the installed `review-loop` skill (independent, cross-family, exact-head; see also `docs/review-protocol.md`) before closing issues
4. **At session end**: follow the installed `thread-rollover` skill and lane `handoff_note` (rules core P7). Keep the tracked `STATUS.md` for durable sections updated via PR only.

## Build & Serve

```bash
npm run build              # builds to dist/, ~38s for 1,999 pages
npx astro dev              # dev server with hot reload
npx astro preview          # preview built site
```

Build gate: for markdown-only content PRs the required CI job "Astro build (render + schema)" is the gate — do not run a local full-site build; build locally only for code, config, schema or Astro-layer changes, one at a time, never on a loaded machine.

## Key Files

| File | Purpose |
|------|---------|
| `STATUS.md` | Current work, progress, blockers |
| `.claude/rules/` | Deployed rules: the release core plus KubeDojo content rules (quality, translation, etc.) |
| `agents_extensions/shared/settings.json` | Source for shared permissions and hooks |
| `.claude/settings.local.json` | Personal overrides (gitignored) |
| `docs/pedagogical-framework.md` | Educational research & guidelines |
| `docs/quality-rubric.md` | 1-5 rubric for module/lab quality |
| `scripts/prompts/module-writer.md` | Standard prompt for module creation |
| `docs/pins/kubernetes.yaml` | Exam pin vs latest-stable minors + kind node images |
| `docs/release-maintenance/kubernetes-minor-release-playbook.md` | Standing trigger for each new Kubernetes minor |
| `lu_machinery.dispatch` (installed release) | Fleet dispatcher (`--repo kube-dojo`) |
| `astro.config.mjs` | Starlight config (sidebar, i18n, theme) |

## Curriculum Structure

```
src/content/docs/          # English content (648 files)
├── prerequisites/         # Fundamentals tab
├── linux/                 # Linux Deep Dive + Everyday Use
├── cloud/                 # Cloud tab (85 modules)
├── k8s/                   # Certifications tab (169 modules)
├── platform/              # Platform Engineering tab (199 modules)
└── uk/                    # Ukrainian translations (115 files)
    ├── prerequisites/
    ├── k8s/cka/
    └── k8s/ckad/
```

## Practice Environment Approach

- **Lightweight**: kind/minikube for most exercises
- **Multi-node**: kubeadm only when topic requires
- **Mock exams**: Questions + self-assessment, not simulation
- **Recommend killer.sh** for realistic exam simulation

## Git Workflow

- Branch: `main`
- Commits: `feat:`, `docs:`, `fix:` prefixes with `#N` issue refs
- Build gate: CI "Astro build (render + schema)" for markdown-only PRs; local build (0 warnings) only for code/config/schema/Astro changes
- Never push without verifying

## Links

- **Repo**: https://github.com/kube-dojo/kube-dojo.github.io
