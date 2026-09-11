---
name: k8s-cert-expert
description: Align KubeDojo Kubernetes certification lessons and study guidance with official CNCF exam objectives. Use when writing or checking exam-specific coverage, not for ordinary Kubernetes implementation work.
---

# Kubernetes Certification Expert

Use this skill for certification alignment alongside the module authoring or review contract. Determine the target certification and relevant exam objectives before judging coverage.

## Sources and version scope

Use the [official CNCF curricula](https://github.com/cncf/curriculum) for domain weights and objectives, and the certification provider's current exam documentation for duration, format, prerequisites, allowed resources, and passing requirements. Verify these when needed; do not treat dated exam snapshots or remembered task counts as current.

Use [Kubernetes documentation](https://kubernetes.io/docs/) and [Helm documentation](https://helm.sh/docs/) for technical behavior. Match examples to the repository's declared Kubernetes target and identify any difference from the current exam environment.

## Track placement

Certification modules live under `src/content/docs/k8s/`. Inspect the relevant index for current module coverage rather than relying on static counts.

| Track | Curriculum emphasis | Path |
|-------|---------------------|------|
| CKA | Cluster administration and troubleshooting | `src/content/docs/k8s/cka/` |
| CKAD | Application design, deployment, and observability | `src/content/docs/k8s/ckad/` |
| CKS | Cluster, system, workload, supply-chain, and runtime security | `src/content/docs/k8s/cks/` |
| KCNA | Cloud-native and Kubernetes fundamentals | `src/content/docs/k8s/kcna/` |
| KCSA | Cloud-native security fundamentals and threat models | `src/content/docs/k8s/kcsa/` |
| Extending Kubernetes | Extension mechanisms and controllers | `src/content/docs/k8s/extending/` |

## Exam-oriented teaching

For hands-on preparation, teach context selection, imperative commands, manifest generation with `--dry-run=client -o yaml`, and `kubectl explain` alongside verification of results. A three-pass practice strategy can separate quick tasks, medium tasks, and complex troubleshooting; adapt timing to the learner and current exam format.

Keep exam-speed advice tied to correct, verifiable outcomes. For knowledge-based exams, assess understanding of the official objectives through scenarios. Distinguish verified exam rules from suggested study strategies and third-party simulations such as killer.sh.
