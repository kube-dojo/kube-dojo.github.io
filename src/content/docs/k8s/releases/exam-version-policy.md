---
title: "Exam version policy"
description: "Dual-track rules: exam-pinned certifications vs latest-stable Release Radar."
sidebar:
  order: 2
  label: "Exam version policy"
---

KubeDojo runs **two tracks** on purpose. Mixing them is how learners fail exams and how agents rewrite the wrong files.

## Track A — Exam pin (certifications)

| Field | Value |
|-------|-------|
| Current pin | **Kubernetes 1.35** |
| Applies to | CKA, CKAD, CKS, and associate tracks that declare the same target |
| Verified | 2026-09-12 (re-check LF/CNCF exam docs before any bump) |
| Source of truth | `docs/pins/kubernetes.yaml` → `exam_pin` |

**Rules**

- Cert modules teach the **exam environment** version, not “whatever is newest on kubernetes.io”.
- Upstream GA of 1.36 or 1.37 does **not** by itself authorize a cert-corpus rewrite.
- Bump the pin only after web-verified evidence that the Linux Foundation / CNCF exam (or published curriculum PDF) moved.

Look for the inline target callouts already used in cert part-0 modules (for example CKA exam strategy). Prefer linking here rather than inventing a second story per lesson.

## Track B — Latest-stable (Release Radar)

| Field | Value |
|-------|-------|
| Supported minors | **1.37, 1.36, 1.35** (upstream three-branch window) |
| Home | [Release Radar](/k8s/releases/) |
| Source of truth | `docs/pins/kubernetes.yaml` → `latest_stable_track` |

**Rules**

- Teach **deltas**: Stable graduations, removals, on-by-default betas that change operator behavior.
- Do **not** clone CKA/CKAD/CKS per minor.
- When a minor leaves upstream support, archive it on the Release Radar index; keep history, drop “supported now”.

## Shared fundamentals

Pods, Deployments, Services, RBAC, scheduling basics, and troubleshooting method stay in the cert and prerequisites tracks. Release Radar assumes that foundation and shows **what changed**.

## What agents must not do

- Rewrite every cert module on each Kubernetes minor.
- Treat `busybox:1.36` image tags as a cluster version pin.
- Document every alpha feature as production guidance.
- Silently bump `exam_pin` without LF/CNCF verification.

Standing playbook: `docs/release-maintenance/kubernetes-minor-release-playbook.md`.
