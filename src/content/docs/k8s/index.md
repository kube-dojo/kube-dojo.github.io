---
title: "Kubernetes Certifications"
sidebar:
  order: 1
  label: "Certifications"
---
> **Release Radar:** Onboard Kubernetes **1.35 / 1.36 / 1.37** (and future minors) without mixing them into exam lessons — start at [Release Radar](/k8s/releases/) and the [exam version policy](/k8s/releases/exam-version-policy/).

**The Kubestronaut Path** — All 5 certifications required for [Kubestronaut](https://www.cncf.io/training/kubestronaut/) status, CNCF's recognition for passing KCNA, KCSA, CKAD, CKA, and CKS.

---

## Overview

```
                        KUBESTRONAUT PATH
    ════════════════════════════════════════════════════════

    ENTRY LEVEL (multiple choice, 90 min)
    ┌──────────────────────────────────────────────────────┐
    │  KCNA   Kubernetes & Cloud Native Associate          │
    │         └── Conceptual understanding of K8s & CNCF   │
    │                                                      │
    │  KCSA   Kubernetes & Cloud Native Security Associate │
    │         └── Security concepts and threat modeling    │
    └──────────────────────────────────────────────────────┘
                             │
                             ▼
    PRACTITIONER LEVEL (hands-on lab, 2 hours)
    ┌──────────────────────────────────────────────────────┐
    │  CKAD   Certified Kubernetes Application Developer   │
    │         └── Build and deploy applications            │
    │                                                      │
    │  CKA    Certified Kubernetes Administrator           │
    │         └── Install, configure, manage clusters      │
    │                                                      │
    │  CKS    Certified Kubernetes Security Specialist     │
    │         └── Secure clusters end-to-end (requires CKA)│
    └──────────────────────────────────────────────────────┘

    ════════════════════════════════════════════════════════
```

---

## Choose Your Path

Start with the job shape, not the alphabetical list. `KCNA` is useful for cloud-native context, but it is optional for learners who already need hands-on cluster work.

### The Operator

The operator wants production cluster administration: scheduling, networking, storage, upgrades, troubleshooting, and incident response. This is the strongest default route for SRE, infrastructure, and platform-adjacent learners who need to run clusters under pressure.

**Default route:** `KCNA (optional) → CKA → CKS`

**Concrete routes:**
- `Beginner -> operator`: `Prerequisites -> KCNA -> CKA -> CKS`
- `Linux / ops -> admin`: `Linux -> CKA -> CKS`

**When to come back:** after `CKA` or `CKS`, add specialist tracks such as `CGOA`, `CCA`, `ICA`, `KCA`, `CAPA`, `OTCA`, `PCA`, `CNPA`, `CNPE`, or `FinOps` when they match the platform you operate.

### The Developer

The developer wants to build, deploy, configure, observe, and debug applications on Kubernetes. This route focuses on workloads first, then cluster administration only if your work expands into platform ownership.

**Default route:** `KCNA (optional) → CKAD → CKA (optional)`

**Concrete routes:**
- `Beginner -> developer`: `Prerequisites -> KCNA -> CKAD`
- `Application developer -> platform-aware developer`: `CKAD -> CKA`

**When to come back:** after `CKAD`, add `CGOA`, `CAPA`, `CBA`, `OTCA`, `PCA`, `CNPA`, or `CNPE` when your work moves toward delivery platforms, observability, developer portals, or platform engineering.

### The Security Specialist

The security specialist wants to harden clusters, workloads, supply chains, runtime behavior, and policy controls. `CKS` is the centerpiece, but it requires `CKA` first — `CKS` is not security-flavored Kubernetes; it assumes you can already administer clusters under time pressure. `KCSA` is optional conceptual prep that fits *before* `CKA`, not after `CKS`.

**Default route:** `KCSA (optional) → CKA → CKS`

**Concrete routes:**
- `Hands-on first`: `CKA -> CKS`
- `Concepts first`: `KCSA -> CKA -> CKS`

**When to come back:** after `CKS`, add `CCA`, `KCA`, `CGOA`, `ICA`, `OTCA`, `PCA`, `CNPA`, `CNPE`, or `FinOps` when your security work touches networking, policy, GitOps, service mesh, observability, platforms, or cost governance.

### Platform And Specialist Routes

- `Kubernetes -> platform`: `KCNA or CKA -> CNPA -> CNPE`
- `GitOps / platform specialist`: `KCNA or CKA -> CGOA / CNPA / CNPE`
- `Observability specialist`: `CKAD or CKA -> PCA / OTCA`
- `Networking specialist`: `CKA -> CCA / ICA`

Specialist certifications are not a better first move than learning the core Kubernetes path. They make the most sense after you already understand how clusters, workloads, and operations fit together.

---

## Certifications

| Cert | Name | Type | Modules | Curriculum |
|------|------|------|---------|------------|
| [KCNA](/k8s/kcna/) | Kubernetes & Cloud Native Associate | Multiple choice | 28 | [Details](/k8s/kcna/) |
| [KCSA](/k8s/kcsa/) | Kubernetes & Cloud Native Security Associate | Multiple choice | 26 | [Details](/k8s/kcsa/) |
| [CKAD](/k8s/ckad/) | Certified Kubernetes Application Developer | Hands-on lab | 24 | [Details](/k8s/ckad/) |
| [CKA](/k8s/cka/) | Certified Kubernetes Administrator | Hands-on lab | 41 | [Details](/k8s/cka/) |
| [CKS](/k8s/cks/) | Certified Kubernetes Security Specialist | Hands-on lab | 30 | [Details](/k8s/cks/) |
| | **Total** | | **149** | |

---

## Start Here If

- you want external certification goals and exam-shaped structure
- you already finished [Prerequisites](/prerequisites/) or equivalent hands-on fundamentals
- you want the shortest route into employable Kubernetes administration or application delivery skills

## Do Not Start Here First If

- you are still uncomfortable with the terminal, SSH, files, and packages
- you have never deployed basic workloads to a cluster
- you are looking for theory-first platform engineering rather than certification prep

If that is your situation, start with [Prerequisites](/prerequisites/) first.

## Tool & Specialist Certifications

Beyond Kubestronaut, CNCF offers tool-specific certifications. KubeDojo maps existing modules as learning paths for each:

| Cert | Name | Learning Path |
|------|------|---------------|
| [PCA](/k8s/pca/) | Prometheus Certified Associate | Prometheus, PromQL, alerting |
| [ICA](/k8s/ica/) | Istio Certified Associate | Service mesh, traffic management |
| [CCA](/k8s/cca/) | Cilium Certified Associate | eBPF networking, policies |
| [CGOA](/k8s/cgoa/) | Certified GitOps Associate | ArgoCD, Flux, GitOps principles |
| [CBA](/k8s/cba/) | Certified Backstage Associate | IDPs, developer portals |
| [OTCA](/k8s/otca/) | OpenTelemetry Certified Associate | Observability, tracing |
| [KCA](/k8s/kca/) | Kyverno Certified Associate | Policy as code |
| [CAPA](/k8s/capa/) | Certified Argo Project Associate | Argo Workflows, Rollouts |
| [CNPE](/k8s/cnpe/) | Cloud Native Platform Engineer | Cross-track learning path |
| [CNPA](/k8s/cnpa/) | Cloud Native Platform Associate | Platform fundamentals |
| [FinOps](/k8s/finops/) | FinOps Practitioner | Cloud cost optimization |

These are best treated as specialization tracks, not replacements for a first Kubernetes foundation. For most learners:
- `KCNA`, `CKA`, or `CKAD` should come first
- specialist certs and platform certs make more sense once you know whether your work is admin, developer, security, GitOps, or platform focused

## Extending Kubernetes

| Section | Modules | Description |
|---------|---------|-------------|
| [Extending K8s](/k8s/extending/) | 8 | Controllers, operators, webhooks, API aggregation, CRDs |

---

## Exam Tips

All exams share these characteristics:
- **PSI Bridge proctoring** — Strict environment, webcam required
- **kubernetes.io allowed** — Official docs are your friend
- **Time pressure** — Speed matters as much as knowledge

Typical pacing:
- `KCNA` / `KCSA`: 4-8 weeks if you are already in the curriculum about `5-8 h/week`
- `CKAD` / `CKA`: 2-4 months at about `8-10 h/week`
- `CKS` after `CKA`: usually another `4-8 weeks`
- full Kubestronaut path: commonly `3-6 months` for already-technical learners at roughly `10 h/week`

For hands-on exams (CKAD, CKA, CKS):
- Practice with `kubectl` until it's muscle memory
- Master vim/nano for YAML editing
- Use `kubectl explain` and `--dry-run=client -o yaml`
- [killer.sh](https://killer.sh) included with exam purchase — use it

## After This Track

- go to [Cloud](/cloud/) if you want provider-specific production Kubernetes
- go to [Platform Engineering](/platform/) if you want systems thinking, SRE, GitOps, and platform design beyond the exams
- go to [On-Premises](/on-premises/) if your goal is private infrastructure and you already have Linux depth

## Choose Your Next Track After Core Kubernetes

| If Kubernetes leads you toward... | Next track | Why |
|---|---|---|
| managed production clusters on AWS, GCP, or Azure | [Cloud](/cloud/) | provider-specific networking, identity, and managed-control-plane patterns live there |
| SRE, GitOps, delivery automation, and internal platforms | [Platform Engineering](/platform/) | that is the systems-and-organization layer above the exams |
| private clusters, bare metal, and datacenter operations | [On-Premises](/on-premises/) | those assumptions diverge sharply from managed-cloud Kubernetes |
| ML workloads, serving, and AI infrastructure | [AI/ML Engineering](/ai-ml-engineering/) | the Kubernetes track is a prerequisite there, not the full workflow |

## Common Failure Modes After This Track

- assuming certification completion automatically means platform-engineering readiness
- jumping into on-prem operations without enough Linux depth
- treating specialist certifications as a substitute for choosing a real next operating context

---

## Curriculum Sources

We track official CNCF curricula:
- [CNCF Curriculum Repository](https://github.com/cncf/curriculum)
- [CKA Program Changes](https://training.linuxfoundation.org/certified-kubernetes-administrator-cka-program-changes/)
- [CKS Program Changes](https://training.linuxfoundation.org/cks-program-changes/)
