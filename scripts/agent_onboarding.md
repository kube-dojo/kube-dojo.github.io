# Agent Onboarding — KubeDojo Local API Recipes

Concrete `curl` recipes for inspecting KubeDojo curriculum and pipeline state on the local API (`http://127.0.0.1:8768`). Start it from the primary checkout with `.venv/bin/python scripts/local_api.py` (binds 127.0.0.1:8768 by default).

## 1. Fleet orientation, dispatch and review

Fleet orientation, dispatch, cross-family review, landing and handoff live in the installed `lu-machinery` release:

- **Orient:** `"$LEARN_UKRAINIAN_PYTHON" -I -m lu_machinery.fleet_comms cold-start-board` and `"$LEARN_UKRAINIAN_PYTHON" -I -m lu_machinery.fleet_comms plane-status` (with `LEARN_UKRAINIAN_PRIMARY_REPO_ROOT` set as [`agents_extensions/README.md`](../agents_extensions/README.md) describes).
- **Dispatch:** `"$LEARN_UKRAINIAN_PYTHON" -m lu_machinery.dispatch dispatch --repo kube-dojo --worktree ...`
- **Review & landing:** follow the installed `review-loop` and `full-send` skills (`lu_machinery.review.closeout_cli resolve-reviewer`, `lu_machinery.review.record_cf_verdict`, `lu_machinery.publish`).
- **Kubernetes minor / exam-pin work:** read [`docs/release-maintenance/kubernetes-minor-release-playbook.md`](../docs/release-maintenance/kubernetes-minor-release-playbook.md) before editing (exam pin ≠ latest-stable Release Radar).

Machine-readable local API endpoint index:

```bash
curl -s http://127.0.0.1:8768/api/schema
```

## 2. Before claiming curriculum work

Avoid cross-agent collisions — check active pipeline leases before picking a module:

```bash
# All active leases, ordered by expiry.
curl -s http://127.0.0.1:8768/api/pipeline/leases

# Just one module.
curl -s http://127.0.0.1:8768/api/module/k8s/cka/module-2.8-scheduler/lease
```

## 3. Before fixing a module

`diagnostics[]` carries a stable `code`, human `summary`, and optional drill-down `next_action`. Switch on `code`, not `summary`.

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

## 4. Before re-reviewing a module

```bash
# Index of all review artifacts.
curl -s http://127.0.0.1:8768/api/reviews

# Existing audit log for one module (capped at 200 KB, flags `truncated`).
curl -s "http://127.0.0.1:8768/api/reviews?module=k8s/cka/module-2.8-scheduler"
```

## 5. Curriculum and pipeline status

```bash
# Whole-page review records and acceptance assertions; all page types/locales.
curl -s http://127.0.0.1:8768/api/content/coverage

# Legacy module frontmatter flags plus bound source counts, not full acceptance.
curl -s http://127.0.0.1:8768/api/tracks/readiness

# Live heuristic rubric scores and quality board.
curl -s http://127.0.0.1:8768/api/quality/scores
curl -s http://127.0.0.1:8768/api/quality/board

# Zombie workers + stuck jobs + unresolved dead-letters in one call.
curl -s http://127.0.0.1:8768/api/pipeline/v2/stuck

# Per-module event timeline (timestamps are Unix-epoch SECONDS, not ms).
curl -s "http://127.0.0.1:8768/api/pipeline/v2/events?module=k8s/cka/module-2.8-scheduler&limit=50"
```

## 6. Human dashboard

The same endpoints feed the local HTML dashboard at `http://127.0.0.1:8768/` (`/quality`, `/operations`, `/uk`, `/telemetry`, `/artifacts`).

## 7. Conventions

- **Errors are JSON envelopes**: `{"error": "<code>", ...optional context}` with an HTTP status matching the code.
- **Cache**: cacheable endpoints return a weak ETag; `If-None-Match` yields `304`.
- **Timestamps**: Unix-epoch seconds for `.pipeline/v2.db` payloads.
