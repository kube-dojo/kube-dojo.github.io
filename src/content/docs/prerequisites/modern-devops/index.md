---
title: "Modern DevOps"
sidebar:
  order: 0
---

This section connects infrastructure, delivery, observation, platform, and security practices. It is for learners who have begun working with Git and Kubernetes and want to explore how those practices fit together.

## Before You Start

Start with command-line and Git basics and enough YAML to read indentation. If these are new, use [Zero to Terminal](/prerequisites/zero-to-terminal/), especially [Git Basics](/prerequisites/zero-to-terminal/module-0.6-git-basics/), and [YAML for Kubernetes](/prerequisites/kubernetes-basics/module-1.8-yaml-kubernetes/). The [prerequisites route](/prerequisites/) recommends [Git Deep Dive](/prerequisites/git-deep-dive/) before this section. Review [Kubernetes Basics](/prerequisites/kubernetes-basics/) for deployments, Services, and manifests; GitOps also lists Kubernetes fundamentals as preparation. Observability additionally expects basic distributed-systems and API knowledge; [From Monolith to Microservices](/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices/) is a related foundation.

## Choose Your Route

For the section's foundation, start with **1.1–1.4** in order: IaC, GitOps, CI/CD, then observability. GitOps and CI/CD list earlier modules as prerequisites; check each module's own prerequisites and exercise setup before starting. For further depth, continue to **1.5 Platform Engineering** after 1.1–1.4, then **1.6 DevSecOps** after 1.1–1.5, as their headers recommend. You can return to a later topic for reference, but review its listed prerequisites first.

## Modules

| # | Module | Time | Description |
|---|--------|------|-------------|
| 1.1 | [Infrastructure as Code](module-1.1-infrastructure-as-code/) | 100–130 min | Explore declarative and imperative workflows and configuration drift. |
| 1.2 | [GitOps](module-1.2-gitops/) | 80–110 min | Explore Git-based desired state and reconciliation. |
| 1.3 | [CI/CD Pipelines](module-1.3-cicd-pipelines/) | 100–130 min | Compare integration, delivery, and deployment workflows. |
| 1.4 | [Observability Fundamentals](module-1.4-observability/) | 70–100 min | Explore metrics, logs, traces, and service objectives. |
| 1.5 | [Platform Engineering Concepts](module-1.5-platform-engineering/) | 80–110 min | Explore internal developer platforms and their operating models. |
| 1.6 | [Security Practices (DevSecOps)](module-1.6-devsecops/) | 80–110 min | Explore security checks across delivery and runtime. |

These are planning estimates copied from the six module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **510–690 minutes (about 8 hours 30 minutes–11 hours 30 minutes)**; individual setup, reading, and practice time will vary.

## Next Step

Ready to begin? Open [Module 1.1: Infrastructure as Code](module-1.1-infrastructure-as-code/). If you need more preparation, return to the [prerequisites hub](/prerequisites/) and choose the foundation you need first.
