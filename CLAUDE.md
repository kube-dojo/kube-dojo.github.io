# CLAUDE.md

KubeDojo — free, open-source cloud native curriculum.

## Agent Orientation (first call on a cold start)

**FIRST ACTION, every session — no exceptions:** invoke the
`curriculum-orchestrator` skill via the Skill tool. This loads the
orchestrator role into context (queue ownership, dispatch routing, PR
hygiene, handoff discipline) before any other work. Apply this even on
issue-driven sessions — the issue is *what* to work on; the skill is
*how* to drive it.

**Issue-driven sessions:** read the GitHub issue verbatim, then run one script:

```bash
KUBEDOJO_ISSUE=N bash scripts/cold-start.sh
```

Standalone session: `bash scripts/cold-start.sh` (add `--manifest` for route discovery).

The script is API-first: services-up, `git status`, pending Decision Cards, then compact
briefing + orient punch-line + session handoff pointer. It exits 0 with a `STATUS.md`
fallback when the API is down. Full ritual: [`scripts/prompts/cold-start.md`](scripts/prompts/cold-start.md).
Individual curl recipes: [`scripts/agent_onboarding.md`](scripts/agent_onboarding.md).

Only read the underlying handoff file (`.agent/session-state/<date>-*.md`; pre-s196 history in `docs/session-state/`) when briefing/orient
leave a real narrative-why gap. Respect `.claude/rules/decision-card.md` for pending decisions.

**Before you claim/fix/re-review work**:
- `GET /api/pipeline/leases`
- `GET /api/module/{key}/state`
- `GET /api/reviews?module={key}`

Optional situational check: `GET /api/activity?limit=30`.

Standalone session = main orchestrator. Drive the queue; ask only on irreversible or ambiguous actions.

Full agent recipe: [`scripts/agent_onboarding.md`](scripts/agent_onboarding.md).

## Agent Usage

- Don't spawn agents for work a single Grep/Read/Glob can do — it's slower and wasteful.
- Agents ARE worth it for genuinely parallel work and context isolation (large refactors, independent research).
- Batch direct tool calls in one message when possible (3 Greps > 3 agents).
- Keep sessions long (`/continue`) — cache hits are ~95% within a session.

## Multi-agent deliberation (`ab discuss`)

For high-leverage decisions only (architecture, threshold freezes, contested NEEDS CHANGES, bets affecting 100+ modules). Use `scripts/ab discuss <channel> --with claude,codex,agy --max-rounds 3` (agy is the Google lane; gemini-cli is retired, #2125/#2230). See `.claude/rules/decision-card.md` for the full protocol (deliberation not quorum; emit a Decision Card on disagreement only). Scan `docs/decisions/pending/` at cold start.

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

1. **Orient via `/api/briefing/session`** (see *Agent Orientation* above). `STATUS.md` is the fallback when the API is down.
2. Use `scripts/prompts/module-writer.md` for new modules
3. Send completed work to the designated cross-family reviewer (see `docs/review-protocol.md`) before closing issues
4. **At session end**: write a lean handoff BRIEF (~2-5KB, YAML frontmatter + bullets) to `.agent/session-state/YYYY-MM-DD-session-NN-<topic>.md` — **Markdown, in the agent dir, never through git/PRs** (AI→AI local agent state; user directives s190b + s196, lu parity #3768/#4704). `docs/session-state/` = tracked pre-s196 history. Then update the LIVE index **`.agent/STATUS.md`** (machine-local, gitignored; preferred by the briefing API — seed from the tracked `STATUS.md` if missing) — promote the new file to "Latest handoff", shift the previous Latest into "Predecessor chain", refresh "Cross-thread notes" / `## TODO` / `## Blockers`. The tracked `STATUS.md` holds durable sections and changes via PR only. **Do NOT inline the full handoff into STATUS.md** — it is an index, not a log. The briefing API (`scripts/local_api.py:_parse_status_md`) parses `## TODO` (unchecked `- [ ]`) and `## Blockers` (`- `) from STATUS.md, so keep those headings populated.

## Build & Serve

```bash
npm run build              # builds to dist/, ~38s for 1,999 pages
npx astro dev              # dev server with hot reload
npx astro preview          # preview built site
```

## Key Files

| File | Purpose |
|------|---------|
| `STATUS.md` | Current work, progress, blockers |
| `.claude/rules/` | Scoped rules (quality, translation, decision-card, etc.) |
| `.claude/settings.json` | Shared permissions (committed) |
| `.claude/settings.local.json` | Personal overrides (gitignored) |
| `docs/pedagogical-framework.md` | Educational research & guidelines |
| `docs/quality-rubric.md` | 1-5 rubric for module/lab quality |
| `scripts/prompts/module-writer.md` | Standard prompt for module creation |
| `docs/pins/kubernetes.yaml` | Exam pin vs latest-stable minors + kind node images |
| `docs/release-maintenance/kubernetes-minor-release-playbook.md` | Standing trigger for each new Kubernetes minor |
| `scripts/dispatch.py` / `scripts/dispatch_smart.py` | CLI dispatchers |
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
- Build before push (0 warnings)
- Never push without verifying

## Links

- **Repo**: https://github.com/kube-dojo/kube-dojo.github.io
