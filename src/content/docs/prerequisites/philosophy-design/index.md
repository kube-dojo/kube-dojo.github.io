---
title: "Philosophy & Design"
sidebar:
  order: 0
---

After hands-on work in [Cloud Native 101](/prerequisites/cloud-native-101/) and [Kubernetes Basics](/prerequisites/kubernetes-basics/), this section examines the history of container orchestration, Kubernetes design choices, and the learning priorities of this curriculum.

Start with Module 1.1 for historical context. Module 1.2 compares imperative commands with declarative management: the API records desired state, and controllers work to bring current state toward it. Use that model to reason about changes and troubleshooting; application recovery and scaling also depend on the controllers, configuration, and resources available.

Module 1.3 helps you plan study scope by goal and points to related lessons. Module 1.4 explains technologies the curriculum skips and the criteria behind those choices. The value of a technology in your own environment requires its own assessment.

## Modules

| # | Module | Time | Description |
|---|--------|------|-------------|
| 1.1 | [Module 1.1: Why Kubernetes Won](module-1.1-why-kubernetes-won/) | 80–110 min | Historical context and adoption factors |
| 1.2 | [Module 1.2: Declarative vs Imperative - The Philosophy](module-1.2-declarative-vs-imperative/) | 80–110 min | Desired state, reconciliation, and imperative changes |
| 1.3 | [Module 1.3: Plan Study Scope by Goal](module-1.3-what-we-dont-cover/) | 80–110 min | Match study activities to the chosen goal and explore related lessons |
| 1.4 | [Module 1.4: Dead Ends - Technologies We Skip](module-1.4-dead-ends/) | 80–110 min | Technologies we skip and why |

These are planning estimates copied from the four module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **320–440 minutes (about 5 hours 20 minutes–7 hours 20 minutes)**; individual setup, reading, and practice time will vary.

The model and its limits follow the Kubernetes 1.35 documentation on [controllers](https://v1-35.docs.kubernetes.io/docs/concepts/architecture/controller/), [self-healing](https://v1-35.docs.kubernetes.io/docs/concepts/architecture/self-healing/), and [horizontal pod autoscaling](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/). Module 1.2 develops these ideas through examples and tradeoffs.
