---
title: "Cloud Native 101"
sidebar:
  order: 0
---

Cloud native practices help teams automate deployment, recovery, and scaling when those needs justify the complexity. Single-server applications, monoliths, and simpler managed services remain valid choices; the goal is to match operational tools to the workload rather than adopt every available platform.

This section is for systems administrators and developers learning the platform their code runs on. You will learn to explain containers, Docker images, what Kubernetes adds, and when microservices are worth their cost.

Our journey begins at the lowest level of abstraction by exploring containers and how they isolate processes. We then examine Docker, the tool that popularized containerization, before moving up a layer to understand when orchestration systems like Kubernetes justify their operational cost. Finally, we will map out the broader Cloud Native Computing Foundation (CNCF) ecosystem and explore the trade-offs between monoliths and microservices when choosing application architecture.

## Modules

| Module | Title | Time | Description |
|--------|-------|------|-------------|
| 1.1 | [What Are Containers?](module-1.1-what-are-containers/) | 80–110 min | Containers explained from first principles and how they differ from virtual machines. |
| 1.2 | [Docker Fundamentals](module-1.2-docker-fundamentals/) | 90–120 min | Building, running, and managing containers effectively with Docker. |
| 1.3 | [What Is Kubernetes?](module-1.3-what-is-kubernetes/) | 90–120 min | The need for container orchestration and why Kubernetes became a common answer to it. |
| 1.4 | [The Cloud Native Ecosystem](module-1.4-cloud-native-ecosystem/) | 100–130 min | Navigating the CNCF landscape, open-source standards, and key ecosystem projects. |
| 1.5 | [From Monolith to Microservices](module-1.5-monolith-to-microservices/) | 90–120 min | Understanding the architectural evolution, benefits, and inherent trade-offs of microservices. |

Start with a working terminal and a machine where you can install Docker for module 1.2. For module 1.3's hands-on exercise, complete [Your First Cluster](../kubernetes-basics/module-1.1-first-cluster/) if needed and confirm the selected cluster is dedicated and disposable; then continue to [Kubernetes Basics](../kubernetes-basics/) after Cloud Native 101.

These are planning estimates copied from the five module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **450–600 minutes (about 7 hours 30 minutes–10 hours)**; individual setup, reading, and practice time will vary.
