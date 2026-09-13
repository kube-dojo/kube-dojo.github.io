---
description: Dual-track Kubernetes versions — exam pin vs latest-stable Release Radar
paths:
  - "src/content/docs/k8s/**"
  - "docs/pins/**"
  - "docs/release-maintenance/**"
  - "AGENTS.md"
  - "scripts/prompts/module-writer.md"
  - ".claude/rules/module-quality.md"
---

# Kubernetes release tracks

KubeDojo runs **two** Kubernetes version tracks. Mixing them is a defect.

| Track | SSOT | Content |
|-------|------|---------|
| **Exam pin** | `docs/pins/kubernetes.yaml` → `exam_pin` | CKA / CKAD / CKS / KCNA / KCSA |
| **Latest-stable** | same file → `latest_stable_track` | `src/content/docs/k8s/releases/` only |

- Standing workflow: `docs/release-maintenance/kubernetes-minor-release-playbook.md`
- Learner policy: `/k8s/releases/exam-version-policy/`
- Workstream: **#2542** (`Refs` only, never Resolves)

## Must

- Read the playbook before authoring a new minor or changing `exam_pin`.
- Bump `exam_pin` only after the LF FAQ **and** CKA/CKAD/CKS product pages agree on a new exam environment version (cite URL + date).
- Put new upstream minors on Release Radar. Update `latest_stable_track` and kind images there.
- Prefer official release blogs + CHANGELOG over third-party roundups.

## Must not

- Rewrite cert modules because kubernetes.io shipped a minor.
- Treat LF’s “4–8 weeks after GA” alignment note as proof the exam moved.
- Treat `busybox:1.36` (image tag) as cluster version 1.36.
- Teach every alpha as production guidance.
- Close #2542 from a single currency packet.

Parked on #2542 (do not sneak into a pin/playbook PR): teaching arcs on minor pages, executed kind diff labs, Killercoda polish.
