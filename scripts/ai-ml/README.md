# AI/ML Engineering Migration Scripts (#199)

Phase scripts for the neural-dojo → KubeDojo AI/ML Engineering track migration.
Run **in order**, one at a time. All scripts are idempotent and resumable.

| Script | Phase | What it does |
|---|---|---|
| `phase4b-new-modules.sh` | 4b | Creates 8 stub modules and runs the v1 pipeline on each (REWRITE mode → Gemini Pro writes from scratch) |
| `phase5-dedupe.sh` | 5 | Full dedupe audit of all 60 AI/ML modules vs existing tracks → `docs/migration-decisions.md` |
| `phase8-uk-translate.sh` | 8 | Translates the entire AI/ML track to Ukrainian via `uk_sync.py translate-section`, one phase at a time |

Phase 6 (pipeline polish) is intentionally skipped per `#199`. Phase 7
(cross-linking) was a one-off; its script called the removed in-tree
dispatcher and is retired.

## Prerequisites

- `.venv` with kubedojo deps installed
- Gemini CLI authenticated (`gemini -y` works)
- Working tree clean before starting each phase

## Running

```bash
# Suggested order
bash scripts/ai-ml/phase5-dedupe.sh             # cheap, informs cross-linking
bash scripts/ai-ml/phase4b-new-modules.sh       # 8 new modules, slow
bash scripts/ai-ml/phase8-uk-translate.sh       # heaviest — run last
```

Run a subset of phase 4b (e.g. only modules 1, 2, 3):

```bash
bash scripts/ai-ml/phase4b-new-modules.sh 1 2 3
```

Run only one section in phase 8:

```bash
bash scripts/ai-ml/phase8-uk-translate.sh mlops
```

## Logs

All long-running commands tee to `.pipeline/ai-ml-logs/` (gitignored). Check there
when something fails — the last log file has the full Gemini exchange.

## Verification after each phase

```bash
npm run build                            # 0 errors required
.venv/bin/python scripts/check_site_health.py
git status                                # confirm only expected files changed
```

## After everything

```bash
.venv/bin/python scripts/uk_sync.py status   # confirm UK parity
gh issue close 199 -c "All phases complete except #6 (pipeline polish, deferred)"
```
