---
title: "kind practice matrix"
description: "Local kind node images for Kubernetes 1.35, 1.36, and 1.37 Release Radar labs."
sidebar:
  order: 6
  label: "kind practice matrix"
---

Use **kind** for Release Radar practice. Keep Killercoda for polished exam-style scenarios; do not treat hosted labs as the version matrix source of truth.

## Node images

Pinned in `docs/pins/kubernetes.yaml` (adjust patch tags when you verify newer kindest publishes):

| Minor | kind node image | Notes |
|-------|-----------------|-------|
| 1.35 | `kindest/node:v1.35.0` | Matches current **exam pin** fixtures |
| 1.36 | `kindest/node:v1.36.1` | Middle supported minor |
| 1.37 | `kindest/node:v1.37.0` | Newest supported minor (Garhwal) |

Create separate clusters per minor (do not skew control plane vs workers beyond the [version skew policy](https://kubernetes.io/releases/version-skew-policy/)):

```bash
kind create cluster --name kd-135 --image kindest/node:v1.35.0
kind create cluster --name kd-136 --image kindest/node:v1.36.1
kind create cluster --name kd-137 --image kindest/node:v1.37.0
```

## Diff-only lab pattern

1. Apply a baseline manifest on **1.35**.
2. Re-apply or patch on **1.36** / **1.37**.
3. Record the behavioral delta (API accepted, field default changed, removal error, new status).
4. Do **not** re-teach “what is a Pod?”

Good first drills:

- **1.36:** confirm `gitRepo` volumes are rejected; migrate to initContainer + `git` or git-sync.
- **1.36:** MutatingAdmissionPolicy / OCI image volumes — exercise GA paths from the [1.36 radar page](/k8s/releases/v1.36/).
- **1.37:** explore KYAML output (`kubectl` KYAML) and pod-level resource fields on a throwaway Deployment.

## Cleanup

```bash
kind delete cluster --name kd-135
kind delete cluster --name kd-136
kind delete cluster --name kd-137
```
