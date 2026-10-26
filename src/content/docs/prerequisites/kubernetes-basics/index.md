---
title: "Kubernetes Basics"
sidebar:
  order: 0
---
Welcome to Kubernetes Basics. In this section, you will dive into the foundational concepts and practical skills required to navigate and manage Kubernetes environments. Whether you are transitioning from traditional infrastructure or standalone containerized setups, understanding these core primitives is essential for modern cloud-native deployment.

We will start from the ground up by setting up your first local cluster and learning how to interact with it using the standard command-line tool, kubectl. From there, we will explore the atomic units of Kubernetes, known as Pods, and discover how Deployments maintain replicas and Services provide stable access, subject to readiness signals, healthy nodes, and available capacity.

Finally, you will separate application configuration from container images using ConfigMaps and Secrets, organize resources using Namespaces and Labels, and describe desired state using YAML manifests. Secrets require additional access controls and storage protections; creating a Secret alone does not secure sensitive data. By the end of this section, you will have practiced deploying, inspecting, updating, and cleaning up example workloads in a disposable cluster.

## Modules

| # | Module | Time | Description |
|---|--------|------|-------------|
| 1.1 | [Your First Cluster](module-1.1-first-cluster/) | 80–110 min | Setting up and exploring a local Kubernetes cluster |
| 1.2 | [kubectl Basics](module-1.2-kubectl-basics/) | 100–140 min | Essential commands for interacting with and querying clusters |
| 1.3 | [Pods - The Atomic Unit](module-1.3-pods/) | 80–110 min | Understanding and managing the smallest deployable objects |
| 1.4 | [Deployments - Managing Applications](module-1.4-deployments/) | 90–130 min | Maintaining replicas and managing rollouts within readiness and capacity limits |
| 1.5 | [Services - Stable Networking](module-1.5-services/) | 80–110 min | Providing stable networking and load balancing for dynamic pods |
| 1.6 | [ConfigMaps and Secrets](module-1.6-configmaps-secrets/) | 60–90 min | Externalizing runtime configuration and protecting sensitive data |
| 1.7 | [Namespaces and Labels](module-1.7-namespaces-labels/) | 50–80 min | Organizing, grouping, and selecting resources within a cluster |
| 1.8 | [YAML for Kubernetes](module-1.8-yaml-kubernetes/) | 60–90 min | Writing, structuring, and understanding declarative cluster manifests |

These are planning estimates copied from the eight module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **600–860 minutes (about 10 hours–14 hours 20 minutes)**; individual setup, reading, and practice time will vary.
