# Agent Onboarding — Local API Recipes

Single source of concrete `curl` recipes for any agent (Claude, Codex, Gemini) spinning up against this repo. The local API runs on `http://127.0.0.1:8768` and is read-only — there is no POST surface.

## 1. Cold-start orientation

**Single entry point** (preferred — replaces manual curl crawl):

```bash
# Issue-driven session:
KUBEDOJO_ISSUE=1234 bash scripts/cold-start.sh

# Standalone session:
bash scripts/cold-start.sh

# Optional route discovery:
bash scripts/cold-start.sh --manifest
```

Emits labeled sections: `workspace`, `pending-decisions`, `briefing`, `orient`, `session`.
On API failure: `STATUS.md` excerpt + handoff path, exit 0. Copy-paste ritual:
[`scripts/prompts/cold-start.md`](prompts/cold-start.md).
If the issue is a Kubernetes minor or exam-pin question, read
[`docs/release-maintenance/kubernetes-minor-release-playbook.md`](../docs/release-maintenance/kubernetes-minor-release-playbook.md)
before editing (exam pin ≠ latest-stable Release Radar).

Individual endpoints (when you need one call without the full ritual):

```bash
# Compact briefing — ~0.7K tokens, 76% reduction vs. the crawl.
curl -s --max-time 2 http://127.0.0.1:8768/api/briefing/session?compact=1

# Punch-line orientation — primary action + up to 3 alternatives (~1.3 KB).
curl -s --max-time 2 http://127.0.0.1:8768/api/orient

# Latest handoff pointer (path + title/tldr, not the full handoff body).
curl -s --max-time 2 http://127.0.0.1:8768/api/session/current

# Full briefing (~1.5K) when you also want next_reads + the worktree list.
curl -s http://127.0.0.1:8768/api/briefing/session

# Machine-readable endpoint index — use this instead of reading local_api.py.
curl -s http://127.0.0.1:8768/api/schema
```

The briefing body carries these agent-critical fields:

| field | what it answers |
|-------|-----------------|
| `actions.active` | what's in flight right now (read-only from a deciding agent's view) |
| `actions.blocked` | what the pipeline can't make progress on without human input |
| `actions.next` | what's ready to pick up |
| `top_modules[]` | every row above that names a module, with a drill-down `endpoint` |
| `alerts[]` | one-line warnings (stale pids, critical rubric, zombie workers) |
| `blockers[]` / `focus[]` | pulled from `STATUS.md` |
| `freshness.stale_seconds` | 0 when background-refreshed; if >75 s the data is growing stale |

Every briefing response carries a weak ETag. Send `If-None-Match` with the previous ETag on repeat polls to get a cheap `304 Not Modified`.

## 2. Before claiming work

Avoid cross-agent collisions — check leases before picking a module:

```bash
# All active leases, ordered by expiry.
curl -s http://127.0.0.1:8768/api/pipeline/leases

# Just one module.
curl -s http://127.0.0.1:8768/api/module/k8s/cka/module-2.8-scheduler/lease
```

## 3. Before fixing a module

`diagnostics[]` carries the stable `code` + human `summary` + optional drill-down `next_action`. Switch on `code`, not `summary`.

```bash
curl -s http://127.0.0.1:8768/api/module/k8s/cka/module-2.8-scheduler/state
```

Known diagnostic codes:

- `english_missing`, `frontmatter_missing`, `frontmatter_no_title`
- `no_lab`, `no_fact_ledger`
- `uk_translation_missing`, `uk_state_<status>`
- `rubric_critical`, `rubric_poor`
- `pipeline_rejected`, `pipeline_dead_letter`
- `lease_held`

## 4. Before re-reviewing

```bash
# Index of all review artifacts.
curl -s http://127.0.0.1:8768/api/reviews

# Existing audit log for one module (capped at 200 KB, flags `truncated`).
curl -s "http://127.0.0.1:8768/api/reviews?module=k8s/cka/module-2.8-scheduler"
```

## 5. Situational awareness

```bash
# Per-track, per-section production-readiness grid.
curl -s http://127.0.0.1:8768/api/tracks/readiness

# Merged 24-h feed: commits + pipeline v2 events + bridge messages.
curl -s "http://127.0.0.1:8768/api/activity?limit=30"

# Zombie workers + stuck jobs + unresolved dead-letters in one call.
curl -s http://127.0.0.1:8768/api/pipeline/v2/stuck

# Per-module event timeline (timestamps are Unix-epoch SECONDS, not ms).
curl -s "http://127.0.0.1:8768/api/pipeline/v2/events?module=k8s/cka/module-2.8-scheduler&limit=50"
```

## 6. Human dashboard

The same endpoints feed an HTML dashboard at `http://127.0.0.1:8768/`. The Operator panel at the top renders `actions.*` as Now / Blocked / Next columns, the readiness grid, and the activity feed. Agents don't need it; operators often do.

## 7. Fallback

`bash scripts/cold-start.sh` handles API-down automatically: prints the first 40 lines of
`STATUS.md` plus the Latest handoff path, then exits 0.

If that block is insufficient:

1. Read the handoff file from the `kubedojo:handoff-path` section.
2. `cat CLAUDE.md` for project overview.
3. `git status` for worktree state (also emitted by the script when API is up).

The briefing API exists so deep file crawls are normally unnecessary.

## 8. Conventions

- **All endpoints are `GET`.** There is no write surface by design.
- **Timestamps are Unix-epoch seconds** for anything sourced from `.pipeline/v2.db` and for the merged activity feed's `items[].at` (bridge-sourced rows are normalized from ISO to epoch inside `/api/activity`). Only the dedicated `/api/bridge/messages` endpoint preserves the bridge's original ISO-8601 strings in its `timestamp` field.
- **Errors are JSON envelopes**: `{"error": "<code>", ...optional context}` with an HTTP status that matches the code.
- **Cache**: cacheable endpoints return a weak ETag; `If-None-Match` yields `304`.
- **Compact**: `/api/briefing/session?compact=1` drops navigation aids (`next_reads`, `links`, worktree list) while keeping the actionable surface.

## 9. Cross-family PR review (before merge)

Cross-family review is mandatory (`docs/review-protocol.md`, AGENTS.md rule 10). Implementation agents open PRs; the **orchestrator merges** after review.

**Reviewer routing (Decision Card C)** — full rationale and updates live in [`docs/decisions/2026-05-24-reviewer-routing-composer-2-5.md`](../docs/decisions/2026-05-24-reviewer-routing-composer-2-5.md):

| Task class | Primary | Secondary | Notes |
|---|---|---|---|
| T0 content review (R1 + R2) | composer-2.5 (`cursor`) | codex | deepseek tertiary; bash-runnability brief required |
| Content authoring | codex / composer-2.5 / deepseek (rotation) | — | — |
| Code / dispatcher / CI review | codex | composer-2.5 (`cursor`) | unchanged |
| Lab-runnability + ground-truth | composer-2.5 (`cursor`) | codex | bash-runnability specialty |
| Translation review (UK) | gemini-cli (when quota back) | codex | unchanged |

**Symmetric rule:** pick a reviewer from a **different model family** than the author (composer-2.5 / Cursor-authored content → **codex** reviews; codex-authored code → **composer-2.5** or Gemini reviews).

| When | Tool | Command |
|------|------|---------|
| Headless Gemini (Ultra OAuth) | `dispatch.py` | `KUBEDOJO_GEMINI_SUBSCRIPTION=1 .venv/bin/python scripts/dispatch.py gemini - --review` |
| T0 content / lab-runnability review | `dispatch_smart.py` | `.venv/bin/python scripts/dispatch_smart.py review --agent cursor --model composer-2.5 --task-id review-pr-N -` (stdin brief; see workflow) |
| Code / dispatcher / CI review | `dispatch_smart.py` | `.venv/bin/python scripts/dispatch_smart.py review --agent codex --worktree .worktrees/<branch> --task-id review-pr-N -` (stdin brief) |
| Quote verification (always) | `verify_review.py` | `.venv/bin/python scripts/verify_review.py --pr N --from-pr --branch origin/<branch>` |

Workflow:

1. Dispatch the reviewer with a brief that includes `gh pr diff N` and `docs/review-protocol.md` (heredoc on `-` is fine).
2. Post the review as `gh pr comment` — not `gh pr review --approve` when the same GitHub identity owns author and reviewer.
3. Run `verify_review.py --from-pr` (or pipe the saved review on stdin) before treating `NEEDS CHANGES` as blocking; ignore `quote_missing` findings unless the verifier confirms them. **Do not** run `--pr` without `--from-pr` and without stdin — that reads empty stdin and falsely reports `0 verified`.
4. Orchestrator merges after an independent-family review is posted; coding agents do not merge their own PRs.

Smoketest: `bash scripts/ops/smoketest_review_verifier.sh` (CLI fixture with one verified + one quote_missing finding).
