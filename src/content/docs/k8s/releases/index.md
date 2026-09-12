---
title: "Kubernetes Release Radar"
sidebar:
  order: 1
  label: "Release Radar"
---

**Track upstream Kubernetes minors without confusing them with your exam pin.**

Upstream currently supports three minors at a time — today that is **1.37, 1.36, and 1.35** ([Kubernetes Releases](https://kubernetes.io/releases/), verified 2026-09-12). KubeDojo teaches those deltas here. Certification lessons (CKA/CKAD/CKS) stay on the **exam pin** until the Linux Foundation / CNCF exam environment moves — see [Exam version policy](/k8s/releases/exam-version-policy/).

## Start here

| Page | Use it when |
|------|-------------|
| [Exam version policy](/k8s/releases/exam-version-policy/) | You need the dual-track rules (exam vs latest-stable) |
| [Kubernetes 1.37 — Garhwal](/k8s/releases/v1.37/) | Newest supported minor (GA 2026-08-26) |
| [Kubernetes 1.36 — Haru](/k8s/releases/v1.36/) | Middle supported minor |
| [Kubernetes 1.35 — Timbernetes](/k8s/releases/v1.35/) | Oldest supported minor **and** current exam-pin context |
| [kind practice matrix](/k8s/releases/practice-kind-matrix/) | Local labs across the three minors |

## How to read a release page

1. **Cert impact** — usually `none` while the exam stays on 1.35.
2. **Stable table** — learner/operator-visible GA items (not the full CHANGELOG).
3. **Removals** — break your clusters if ignored (example: `gitRepo` volumes disabled in 1.36).
4. **Practice** — prefer kind node images from the matrix; diff-only labs over full cert clones.
5. **Sources** — official release blog + releases page; treat third-party roundups as secondary.

## Agents

Machine pins live in [`docs/pins/kubernetes.yaml`](https://github.com/kube-dojo/kube-dojo.github.io/blob/main/docs/pins/kubernetes.yaml). Standing workflow: [`docs/release-maintenance/kubernetes-minor-release-playbook.md`](https://github.com/kube-dojo/kube-dojo.github.io/blob/main/docs/release-maintenance/kubernetes-minor-release-playbook.md). Workstream: GitHub **#2542** (X06 under epic #2272).
