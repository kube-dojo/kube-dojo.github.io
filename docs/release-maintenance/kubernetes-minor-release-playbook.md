# Kubernetes minor-release playbook (agents)

Standing workflow for X06 (#2542). Humans may run the same steps.

## Rules

1. **Do not rewrite CKA/CKAD/CKS modules** when upstream ships a minor.
2. **Exam pin** (`docs/pins/kubernetes.yaml` → `exam_pin`) moves only after web-verified LF/CNCF exam / curriculum PDF change.
3. **Latest-stable track** always mirrors upstream’s supported minors (~3).
4. Prefer **official** release blogs + CHANGELOG + docs version paths as sources. Third-party roundups are secondary.
5. Ignore most **alpha** unless paradigm-shifting; teach beta (esp. on-by-default) and GA deeply.
6. Never confuse **busybox:1.36** (image tag) with cluster version **1.36**.

## Detect

1. Open https://kubernetes.io/releases/ — note the three supported minors.
2. If a new GA minor appears that is missing under `src/content/docs/k8s/releases/`, open/update the X06 child issue and proceed.

## Inventory

1. Read the official release blog (`kubernetes.io/blog/.../kubernetes-v1-XX-release/`).
2. Skim `CHANGELOG/CHANGELOG-1.XX.md` for removals/deprecations.
3. Classify: Stable / Beta / Alpha / Deprecated / Removed.
4. Set **cert impact**: `none` | `watch` | `bump-needed` (bump-needed only when exam pin moves).

## Author

Copy the structure of an existing `v1.XX.md` Release Radar page:

- Executive summary + theme name
- Learner-visible Stable table (who cares)
- Deprecations / removals
- Cert impact box
- Practice pointers (kind image from `docs/pins/kubernetes.yaml`)
- Sources (official links + verification date)

Update `latest_stable_track.supported_minors` and sidebar order (newest first). Add a What’s New (`changelog.md`) bullet.

## Review / merge

Cross-family review on exact head. Build from **primary** checkout, not a worktree.

## Retire

When a minor leaves upstream support, move its page to an “Archive” note on the Release Radar index; keep the page for history but remove it from “supported now”.

## Exam-pin bump (rare)

Only when LF/CNCF exam environment version changes:

1. Update `exam_pin` in `docs/pins/kubernetes.yaml` with new `verified_date`.
2. Update `AGENTS.md`, `.claude/rules/module-quality.md`, `scripts/prompts/module-writer.md`.
3. Grep `1.3N` / `v1-3N.docs` / `kindest/node:v1.3N` / fixture scripts — surgical patches only, driven by Release Radar migration notes.
4. Separate PR from Release Radar delta authorship.
