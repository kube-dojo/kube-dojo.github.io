# Kubernetes minor-release playbook (agents)

Standing trigger for X06 (#2542). Humans may run the same steps.

**Read this before** writing cert modules, bumping a Kubernetes version, or authoring a Release Radar page. Dual-track mix-ups are how learners fail exams and how agents rewrite the wrong files.

- Learner policy: [`/k8s/releases/exam-version-policy/`](../../src/content/docs/k8s/releases/exam-version-policy.md)
- Machine pins: [`docs/pins/kubernetes.yaml`](../pins/kubernetes.yaml)
- Page template: [`kubernetes-release-bundle-template.md`](./kubernetes-release-bundle-template.md)
- Agent rule: [`.claude/rules/kubernetes-release-tracks.md`](../../.claude/rules/kubernetes-release-tracks.md)

## Dual-track (do not mix)

| Track | Source of truth | Update when | Typical paths |
|-------|-----------------|-------------|----------------|
| **A — Exam pin** | `exam_pin` in `docs/pins/kubernetes.yaml` | LF/CNCF exam environment version changes (web-verified the same day) | Cert modules stay pinned; bump PR is separate |
| **B — Latest-stable** | `latest_stable_track` in the same YAML | Upstream’s supported-minor window changes (~3 minors) | `src/content/docs/k8s/releases/` only |

Upstream GA of 1.36 or 1.37 does **not** authorize a CKA/CKAD/CKS rewrite. LF’s “aligns within approximately 4 to 8 weeks of the K8s release date” is a **forecast**, not evidence the exam moved.

## When to run (triggers)

Run this playbook when **any** of these are true:

1. [kubernetes.io/releases/](https://kubernetes.io/releases/) shows a GA minor missing under `src/content/docs/k8s/releases/`.
2. A minor left the upstream three-branch window and is still listed as “supported now”.
3. A task says “update certs to latest Kubernetes”, “bump CKA to 1.3X”, or similar.
4. A #2542 currency packet asks to re-verify the exam pin.

**Do not** treat these as this playbook’s job (parked or other issues):

- Teaching arcs / worked Stable features on existing minor pages (parked 2026-09-12 on #2542).
- Executed kind diff labs beyond the [kind practice matrix](../../src/content/docs/k8s/releases/practice-kind-matrix.md) (same).
- Killercoda polish; Ukrainian (#2291); generic freshness (#2294).

PRs that advance #2542 must say **`Refs #2542`** only. Never `Resolves` / `Closes` — the workstream stays open.

## Verify exam pin (required before any `exam_pin` edit)

All of the following must **agree on the same minor**, cited in the PR with a verification date:

1. [LF FAQ — exam environment version](https://docs.linuxfoundation.org/tc-docs/certification/faq-cka-ckad-cks) (“What application version is running in the Exam Environment?”)
2. [CKA product page](https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/) (“The exam is based on Kubernetes v…”)
3. [CKAD product page](https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/)
4. [CKS product page](https://training.linuxfoundation.org/certification/certified-kubernetes-security-specialist/)

Write a **verbatim** LF FAQ or CKA product-page sentence into `exam_pin.verified_note` (plus source and date). Required for any `exam_pin` field edit, including re-verify-without-bump — a paraphrase alone is not enough. If FAQ and product pages disagree, **do not bump** — report the contradiction on #2542.

Re-verified **2026-09-13**: CKA, CKAD, and CKS still state **Kubernetes v1.35**.

## Decision tree

| You observed | Do this | Do **not** |
|--------------|---------|------------|
| New upstream GA, no Radar page | Author a Track B bundle from the template; update `latest_stable_track` + kind image | Touch cert lesson bodies; bump `exam_pin` |
| Minor left upstream support | Archive note on the Release Radar index; drop it from `supported_minors`; keep the page | Delete history or rewrite certs |
| LF FAQ **and** product pages show a new exam minor | Track A bump PR (see below) | Combine with a new-Radar-page PR |
| Cert module says “GA in 1.36 / future” for something already Stable | Surgical one-line fix + link to the Radar page | Full cert rewrite |
| “Update CKA to latest” with no LF page change | Refuse. Point at the policy page and this playbook | Rewrite modules “to be current” |

## File allow / deny

**Track B (new or retired minor)** — allow:

- `src/content/docs/k8s/releases/**`
- `docs/pins/kubernetes.yaml` — `latest_stable_track` and `kind_node_images` only
- `src/content/docs/changelog.md` — one What’s New bullet
- `src/content/docs/k8s/index.md` — hub version list only if the supported set changed

**Process / playbook packet** (standing trigger and discovery hooks; may ship alone or with Track B) — allow:

- `docs/release-maintenance/kubernetes-minor-release-playbook.md`
- `docs/release-maintenance/kubernetes-release-bundle-template.md`
- `.claude/rules/kubernetes-release-tracks.md`
- `.claude/rules/new-content-checklist.md` — dual-track item only
- `AGENTS.md` / `CLAUDE.md` — dual-track pointers only (not the exam-pin minor number)
- `scripts/prompts/cold-start.md`
- `scripts/agent_onboarding.md`
- `scripts/prompts/module-writer.md` / `.claude/rules/module-quality.md` — playbook pointer only (not the exam-pin minor number)
- `docs/pins/kubernetes.yaml` — `exam_pin.verified_date` / `verified_note` on re-verify-without-bump (`kubernetes_minor` unchanged)

**Deny unless this is the rare Track A exam-pin bump PR:**

- `src/content/docs/k8s/cka/**`, `ckad/**`, `cks/**`, `kcna/**`, `kcsa/**`
- `src/content/docs/uk/**`
- exam fixtures (`scripts/cka_certificate_fixture.py` and siblings)
- exam-pin **version-number** lines in `AGENTS.md`, `.claude/rules/module-quality.md`, `scripts/prompts/module-writer.md`

**Never:**

- Confuse `busybox:1.36` (image tag) with cluster **1.36**
- Document every alpha as production guidance
- Silently edit `exam_pin` because kubernetes.io shipped a minor

## Detect

1. Open https://kubernetes.io/releases/ — record the three supported minors and the date.
2. Diff against `latest_stable_track.supported_minors` and files under `src/content/docs/k8s/releases/`.
3. Confirm kindest node tags on Docker Hub before writing `kind_node_images` (example: `v1.36.0` was unpublished; `v1.36.1` was the pin).

## Inventory

1. Official release blog: `https://kubernetes.io/blog/YYYY/MM/DD/kubernetes-v1-XX-release/`.
2. `CHANGELOG/CHANGELOG-1.XX.md` — removals and deprecations first.
3. Classify: Stable / Beta (esp. on-by-default) / Alpha / Deprecated / Removed.
4. Set **cert impact**: `none` | `watch` | `bump-needed`.
   - `bump-needed` **only** when the exam pin is moving in a separate Track A PR.
   - `watch` = exam still pinned, but cert prose may have stale “coming in 1.XX” callouts (fix surgically, later).

## Author (Track B)

Copy [`kubernetes-release-bundle-template.md`](./kubernetes-release-bundle-template.md) into `src/content/docs/k8s/releases/v1.XX.md` (keep existing `v1.35.md` / `v1.36.md` / `v1.37.md` as the pattern):

- Executive summary + theme name
- Learner-visible Stable table (who cares — not the full CHANGELOG)
- Deprecations / removals
- Cert impact box
- Practice pointers (kind image from `docs/pins/kubernetes.yaml`)
- Sources (official links + verification date)

Then:

1. Update `latest_stable_track.supported_minors` and `as_of`.
2. Sidebar order: newest first (current convention: 1.37 = 3, 1.36 = 4, 1.35 = 5).
3. Add a What’s New (`src/content/docs/changelog.md`) bullet.
4. English only. One minor (or one retire) per PR when possible.

## Review / merge

Cross-family review on exact head. Build from the **primary** checkout, not a worktree. Do not claim a main-checkout build validates unmerged worktree edits.

## Retire

When a minor leaves upstream support, add an “Archive” note on the Release Radar index; keep the page for history; remove it from “supported now” and from `supported_minors`.

## Exam-pin bump (Track A, rare)

Only when the LF sources in **Verify exam pin** all show a new environment version:

1. Update `exam_pin` in `docs/pins/kubernetes.yaml` (`kubernetes_minor`, `verified_date`, `verified_note` with a verbatim LF FAQ or CKA sentence plus source and date).
2. Update `AGENTS.md`, `.claude/rules/module-quality.md`, `scripts/prompts/module-writer.md` to the new pin.
3. Grep `1.3N` / `v1-3N.docs` / `kindest/node:v1.3N` / fixture scripts — **surgical** patches only, driven by Release Radar migration notes.
4. Separate PR from Track B authorship. Still `Refs #2542` (and #2280 if a cert-track upgrade issue is open). Never close #2542 from the bump PR alone.

## Packet hygiene

- One concern, fewer than 20 files.
- No generated artifacts (`.pipeline/`, `dist/`, `node_modules/`).
- After merge, the next #2542 packet is whatever AC remains — do not reopen closed children #2543–#2548 unless a real gap appears.
