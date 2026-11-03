# KubeDojo Scripts

## check_site_health.py

Validates site integrity — run before every push.

```bash
# Run the health check
python scripts/check_site_health.py
```

**What it checks:**
1. All `mkdocs.yml` nav entries point to existing files
2. No orphaned `.md` files missing from navigation
3. All internal markdown links resolve (`[text](path.md)`)
4. Changelog has links for every mentioned module
5. No duplicate nav entries
6. Module count in STATUS.md matches actual files
7. README files reference their child modules

**Exit codes:** 0 = pass, 1 = errors found

**When to run:**
- Before every `git push`
- After adding new modules
- After updating navigation or changelog

---

## ztt_status.py

Unified `Zero to Terminal` readiness report.

```bash
python scripts/ztt_status.py
python scripts/ztt_status.py --json
```

**What it reports:**
1. English ZTT theory modules present and fact-ledger audited
2. ZTT lab review state from `.pipeline/lab-state.yaml`
3. Ukrainian ZTT file presence and commit-sync state against English source files

---

## status.py

Unified repo-level operational status.

```bash
python scripts/status.py
python scripts/status.py --json
```

**What it reports:**
1. v2 pipeline queue/convergence state from `.pipeline/v2.db`
2. Translation ownership and repo-wide Ukrainian sync state
3. Lab review state from `.pipeline/lab-state.yaml`
4. Zero to Terminal readiness snapshot

---

## local_api.py

Read-only deterministic local API for repo and pipeline state.

```bash
python scripts/local_api.py
python scripts/local_api.py --host 0.0.0.0 --port 8768
```

**First endpoints:**
1. `/` and `/dashboard` — lightweight local monitor UI
2. `/healthz`
3. `/api/status/summary`
4. `/api/pipeline/v2/status`
5. `/api/translation/v2/status?section=prerequisites/zero-to-terminal`
6. `/api/labs/status`
7. `/api/ztt/status`
8. `/api/git/worktree`
9. `/api/issue-watch/248`
10. `/api/module/<module-key>/state`
11. `/api/module/<module-key>/orchestration/latest`

**Why it exists:**
1. Reduces repeated shell/file probes for stable state
2. Exposes deterministic JSON for pipeline, translation, labs, worktree, and module-level views
3. Adds a lightweight local dashboard so the API is easier to inspect without curl-only workflows

---

## issue_watch.py

Watch GitHub issue comments into local state and log files.

```bash
python scripts/issue_watch.py run 248
python scripts/issue_watch.py loop 248 --interval-seconds 1800
```

**What it does:**
1. Polls `gh issue view` for the target issue
2. Stores the latest snapshot under `.pipeline/issue-watch/<issue>.json`
3. Appends newly seen comments to `.pipeline/issue-watch/<issue>.log`
4. Gives long-running feedback review a durable local trail instead of relying on memory

---

## translation_v2.py

Queue-based Ukrainian sync control plane.

```bash
python scripts/translation_v2.py status --section prerequisites/zero-to-terminal
python scripts/translation_v2.py enqueue-section prerequisites/zero-to-terminal --limit 3
python scripts/translation_v2.py worker run --json
python scripts/translation_v2.py verify-worker run --json
python scripts/translation_v2.py watchdog sweep
```

**What it does:**
1. Detects per-module Ukrainian freshness (`synced / stale / missing / unknown`)
2. Enqueues translation jobs one module at a time on `.pipeline/translation_v2.db`
3. Runs a `write -> review` flow:
   - `worker`: translate or refresh the Ukrainian module
   - `verify-worker`: run deterministic freshness + Ukrainian quality verification
4. Retries failed modules without blocking whole-section progress

---

## dispatch.py

Direct CLI dispatch for Gemini and Claude — calls CLIs as subprocesses with no broker or database.

### Quick Usage

```bash
# Review a module (--review adds KubeDojo review context)
python scripts/dispatch.py gemini \
  "Review docs/k8s/cka/part3-services-networking/module-3.5-gateway-api.md for technical accuracy" \
  --review

# Review a GitHub issue and post result as comment
python scripts/dispatch.py gemini \
  "Review issue #66: $(gh issue view 66 --json body --jq .body)" \
  --review --github 66

# Review a diff
python scripts/dispatch.py gemini \
  "Review this diff for accuracy: $(git diff HEAD~3..HEAD -- docs/)" \
  --review

# Read prompt from stdin
cat prompt.txt | python scripts/dispatch.py gemini - --review

# Use Claude for expansion
python scripts/dispatch.py claude "Expand this draft to full depth..."
```

### Programmatic Usage

```python
from scripts.dispatch import GEMINI_WRITER_MODEL, dispatch_gemini_with_retry, post_to_github

ok, output = dispatch_gemini_with_retry("Review this module...", review=True)
if ok:
    post_to_github(66, output, GEMINI_WRITER_MODEL)
```

### Review Criteria

Gemini reviews KubeDojo content against these criteria (auto-injected with `--review`):
- **Technical accuracy**: K8s commands correct and runnable, version numbers accurate
- **Exam alignment**: Content matches current CNCF exam curriculum
- **Completeness**: Acceptance criteria thorough, edge cases covered
- **Junior-friendly**: Beginner-accessible, "why" explained not just "what"

### Architecture

- **No broker** — direct `subprocess.Popen` / `subprocess.run` calls to `gemini` and `claude` CLIs
- **Streaming** — Gemini output streams to stdout in real-time
- **Retry** — exponential backoff on rate limits (default 3 retries)
- **GitHub integration** — posts reviews as issue comments via `gh` CLI (with chunking for long reviews)

---

## #388 Module Quality Pipeline (`scripts/quality/`)

End-to-end automation for the site-wide module rewrite (#388). Per item: codex (gpt-5.5, danger) writes → gemini cross-family review → auto-merge on APPROVE → cleanup. Held PRs (APPROVE_WITH_NITS / NEEDS CHANGES) surface for orchestrator triage.

### Primary entry point: `run_388_batch.py`

Single E2E command. Builds the bucket from the local API, dispatches, cleans up, prints summary.

```bash
# See available tracks + critical-mod counts
python scripts/quality/run_388_batch.py --list-tracks

# Run one fine-grained track (KCNA, KCSA, CKA, CKAD, CKS, "Platform Toolkits", ...)
python scripts/quality/run_388_batch.py --track KCSA

# Run a top-level alias (mirrors site-nav tab)
python scripts/quality/run_388_batch.py --track certifications   # = k8s/
python scripts/quality/run_388_batch.py --track platform-engineering  # = platform/

# Use a curated module list (skip auto-build)
python scripts/quality/run_388_batch.py --input scripts/quality/my-list.txt

# Preview without dispatching anything
python scripts/quality/run_388_batch.py --track CKAD --dry
```

**Top-level aliases** (map to filesystem prefixes):
| Alias | Prefix |
|------|------|
| `certifications` | `k8s/` |
| `platform-engineering` | `platform/` |
| `fundamentals` | `prerequisites/` + `linux/` |
| `cloud` | `cloud/` |
| `on-premises` | `on-premises/` |
| `ai` | `ai/` |
| `ai-ml-engineering` | `ai-ml-engineering/` |

**API integration** (replaces ad-hoc filters):
- `/api/quality/upgrade-plan?target=5.0` — pre-bucketed candidates
- `/api/quality/board` — filters out already-shipped modules
- `/api/pipeline/leases` — skips modules currently leased by another worker (per CLAUDE.md "Before you claim work")

### Building blocks (run_388_batch chains these; also runnable standalone)

#### `verify_module.py` — the canonical contract

Deterministic verifier. All gates must clear for tier T0.

```bash
# One module, no source check
python scripts/quality/verify_module.py \
  --glob src/content/docs/k8s/cka/part1-control-plane/module-1.1-control-plane.md \
  --skip-source-check --summary --quiet

# All revision_pending modules → JSONL audit
python scripts/quality/verify_module.py --all-revision-pending --out logs/audit.jsonl
```

Blocking gate keys (`gate_results`; its output decides each gate, and several are narrow heuristics, so a pass does not prove the content rule): `gate_no_source_h1`, `structure_sections_present`, `structure_order_correct`, `structure_quiz_answers_have_details`, `sources_all_reachable`, `anti_leak`, `runnable_no_kubectl_alias`, `lab_image_binary_match`, `anti_fabrication_no_unsourced_anecdote`, `practice_mcq_four_options_with_distractors`, `outcomes_aligned`. Word counts, density (wpp, short-paragraph rate), sentence length and template counts (Did You Know, Common Mistakes, quiz items, sources) are reported in the record as diagnostics, and `length_attention` flags unusually short or long pages for their outcomes; none of them rejects, tiers or rewards a page (#3744). Tiers (`classify_tier`): T0 no blocking failure; T1 one or two `structure_*` failures only; T2 `lab_image_binary_match` only; T3 any other failure.

#### `dispatch_388_pilot.py` — per-module orchestrator

Sequential codex → gemini → merge loop.

```bash
python scripts/quality/dispatch_388_pilot.py \
  --input scripts/quality/day3-bucket1-kcna.txt \
  --log logs/388_kcna.jsonl \
  --max 5    # optional canary cap
```

Verdict routing:
- `APPROVE` → squash-merge with `--delete-branch`
- `APPROVE_WITH_NITS` → log `merge_held_nits` + post review; **held** for orchestrator triage (C3 fix-up lane)
- `NEEDS CHANGES` / `UNCLEAR` → log `merge_held`; orchestrator decides re-dispatch vs inline

#### `cleanup_388_pilot.py` — post-batch housekeeping

```bash
python scripts/quality/cleanup_388_pilot.py --input scripts/quality/day3-bucket1-kcna.txt
python scripts/quality/cleanup_388_pilot.py --input <file> --dry   # preview only
python scripts/quality/cleanup_388_pilot.py --input <file> --no-fetch
```

1. `git fetch` + `git pull --ff-only origin main`
2. Re-verify each input module on main
3. Clear stale `revision_pending: true` on modules that pass the verifier
4. Remove `*388-pilot*` worktrees + their branches
5. Remove `/private/tmp/kubedojo-build-388-pilot` (codex's build workaround)
6. Print per-module table

### Held-PR triage (manual, per C3 deliberation)

Held PRs require orchestrator judgment — the C3 fix-up lane was deliberated in `ab discuss day3-388` (2026-05-02). The summary at the end of `run_388_batch.py` lists each held PR with its gemini review URL:

- **APPROVE_WITH_NITS** (URL fix, redundant alias, typo, single-line removal) → fix inline on the branch + `gh pr merge --squash --delete-branch <num>`
- **NEEDS CHANGES** (structural failure, missing section, or a reviewer-confirmed loss of needed explanation or added padding) → close PR, or re-dispatch codex on the existing branch with the gemini review as the brief:
  ```bash
  codex exec -C .worktrees/codex-388-pilot-<slug> \
    -m gpt-5.5 --dangerously-bypass-approvals-and-sandbox - <<< "<gemini's review as the brief>"
  ```

### Operational risks (when running solo)

1. **Codex auth expiry** — batch silently dies. Run `codex login` before launching.
2. **Gemini 429** — under load `gemini-3.1-pro-preview` returns "no capacity." Fall back: `KUBEDOJO_GEMINI_REVIEW_MODEL=gemini-3-flash-preview python scripts/quality/run_388_batch.py ...`.
3. **Process death mid-batch** — no resume support today; manually edit the input file to skip already-merged modules and relaunch.
