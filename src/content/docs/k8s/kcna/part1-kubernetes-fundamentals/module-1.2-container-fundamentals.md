---
revision_pending: false
title: "Module 1.2: Container Fundamentals"
slug: k8s/kcna/part1-kubernetes-fundamentals/module-1.2-container-fundamentals
sidebar:
  order: 3
---

Complexity: `[MEDIUM]` long-form foundational module with hands-on isolation and packaging practice. Time to complete: 35-45 minutes. Prerequisites: Module 1.1 and basic Linux command-line comfort. The examples assume Kubernetes 1.35 or newer, and when Kubernetes commands appear later, set `alias k=kubectl` so the short `k` form is clear.

## Learning Outcomes

After completing this module, you will be able to:

1. **Compare** containers and virtual machines by evaluating kernel sharing, isolation boundaries, startup cost, and operational tradeoffs.
2. **Diagnose** namespace and cgroup behavior when a container can see the wrong process, network, filesystem, or resource limit.
3. **Evaluate** OCI images, registries, tags, layers, and digests to choose reproducible packaging practices for Kubernetes workloads.
4. **Describe** a container runtime inspection workflow that connects Docker, containerd, CRI-O, CRI, and Kubernetes pod behavior.

## Why This Module Matters

**Hypothetical scenario:** A payments platform ships a small reporting service as a container because the team wants fast deployment and consistent dependencies across development, staging, and production. The service looks harmless during testing, but a memory leak appears during a month-end traffic spike, and the container keeps allocating memory until the node begins evicting unrelated workloads. The post-incident costs include customer compensation, overtime, and delayed settlement work, yet the root cause is not an exotic Kubernetes failure; it is a basic misunderstanding of what container isolation does and does not provide.

That kind of outage feels unfair at first because containers are often described as isolated packages, and the word isolated sounds stronger than it really is. A container can have its own process list, hostname, mount view, and network interfaces while still sharing the host kernel and competing for the same finite CPU and memory. Kubernetes can schedule pods, restart containers, and pull images, but it cannot make poor assumptions disappear; if engineers do not know where the isolation boundary sits, they will debug the wrong layer when pressure arrives.

This module builds the mental model that KCNA expects and that day-to-day operators actually use. You will compare containers with virtual machines, trace the Linux features that make containers work, inspect the image and runtime standards that allow portability, and connect those ideas to Kubernetes 1.35 runtime behavior. The goal is not to become a Dockerfile specialist yet; the goal is to recognize what Kubernetes is orchestrating when it says it runs a container.

## What a Container Really Packages

A container is best understood as a process with a prepared filesystem, a controlled view of the operating system, and resource rules enforced by the host kernel. The image provides the application files, libraries, runtime, and minimal userspace that the process needs, while the kernel remains outside the package. That distinction is the first correction to make when someone says a container includes a whole operating system, because the package carries enough userspace to run the program, not a separate Linux kernel.

The original shorthand still helps if you read it carefully: a container is a lightweight, standalone, executable package that includes everything needed to run a piece of software except the host kernel. The package can contain a Python interpreter, a Node.js runtime, shared libraries, certificate files, shell tools, and application code. It does not contain the scheduler, memory manager, TCP/IP stack implementation, or kernel security machinery that actually runs on the node.

```text
┌─────────────────────────────────────────────────────────────┐
│              WHAT'S INSIDE A CONTAINER                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    CONTAINER                         │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Application Code                            │    │   │
│  │  │  (your app, scripts, binaries)              │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Dependencies                                │    │   │
│  │  │  (libraries, packages, frameworks)          │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Runtime                                     │    │   │
│  │  │  (Python, Node.js, Java JVM, etc.)          │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  System Tools & Libraries                    │    │   │
│  │  │  (minimal OS userspace)                     │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  NOT included: Kernel (shared with host)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Think of an image as a carefully packed lunchbox rather than a whole kitchen. The lunchbox can include the meal, utensils, napkins, and seasoning, but it still depends on the building for tables, power, water, and safety rules. In the same way, a container image can include your application and its dependencies, but the node supplies the kernel, device drivers, and enforcement mechanisms that make the process run.

This matters when debugging because many container problems are not inside the application at all. A process may fail because the image lacks a shared library, because the runtime starts the wrong entry point, because a Kubernetes security context blocks a filesystem write, or because the node's cgroup settings terminate the process for memory use. Treating the container as a tiny machine hides those layers, while treating it as a packaged process makes each failure path easier to test.

A worked example makes the boundary concrete. If a Node.js application image contains `/usr/local/bin/node`, `/app/server.js`, and the libraries under `/app/node_modules`, that image can run on many Linux hosts because it brings the userspace files it needs. It still cannot run on a Linux node with a completely incompatible CPU architecture, and it still cannot call kernel features that the host kernel does not provide, because the image is portable only across compatible runtime environments.

The phrase "works on my machine" is the cultural reason containers became so popular. Before container workflows were common, teams often discovered that a library version, package mirror, certificate bundle, or environment variable differed between a laptop and a server. A container image does not eliminate every environmental difference, but it makes the application filesystem and startup command explicit enough that those differences become visible artifacts rather than folklore passed between teammates.

The image also gives operations teams a cleaner handoff than a runbook full of manual installation steps. Instead of asking a server to become the right shape over time, the team builds a versioned artifact and asks the runtime to start it. That changes failure analysis because a bad deployment can be traced to a specific image reference, build process, or runtime setting instead of an unknown sequence of shell commands executed months ago.

Pause and predict: if a container image says it is based on Ubuntu, does that mean the running process has an Ubuntu kernel, or only an Ubuntu-style userspace? The practical answer affects incident response. If the application triggers a kernel bug, upgrading packages inside the image may not fix the node; if the application is missing `ca-certificates`, rebuilding the image may be exactly the right fix.

Containers also encourage immutability, which means the running instance should be treated as disposable. You can write temporary files inside a container, but those writes belong to a writable layer attached to that one running container unless a volume is mounted. Kubernetes leans into this model by replacing containers instead of nursing individual instances back to health, so configuration, logs, and persistent data need deliberate destinations outside the disposable process.

That disposable model is easy to say and harder to practice. Engineers who are used to logging into servers may want to install a debugging package, edit a configuration file, and leave the changed server in service. In a container workflow, those actions should usually become a new image, a changed manifest, or an attached diagnostic session that disappears afterward. The reward is that the next replica, node, or cluster can be created from the same declared inputs instead of a hidden manual history.

## Containers vs Virtual Machines

Virtual machines and containers both let teams run multiple workloads on shared hardware, but they draw the isolation boundary in different places. A VM virtualizes hardware and boots a guest operating system with its own kernel, so each workload can be separated by a hypervisor boundary. A container isolates processes inside one host operating system, so the runtime is lighter and faster, but the shared kernel becomes a security and compatibility dependency.

The difference is easiest to see as a stack. In a VM design, every guest carries its own kernel and operating system services, which gives strong separation but consumes more memory and disk. In a container design, each application carries its own userspace dependencies, while the host kernel remains common to all containers on that node.

```text
┌─────────────────────────────────────────────────────────────┐
│         VIRTUAL MACHINES vs CONTAINERS                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  VIRTUAL MACHINES                    CONTAINERS             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  ┌─────┐ ┌─────┐ ┌─────┐          ┌─────┐ ┌─────┐ ┌─────┐ │
│  │App A│ │App B│ │App C│          │App A│ │App B│ │App C│ │
│  ├─────┤ ├─────┤ ├─────┤          ├─────┤ ├─────┤ ├─────┤ │
│  │Bins │ │Bins │ │Bins │          │Bins │ │Bins │ │Bins │ │
│  │Libs │ │Libs │ │Libs │          │Libs │ │Libs │ │Libs │ │
│  ├─────┤ ├─────┤ ├─────┤          └──┬──┘ └──┬──┘ └──┬──┘ │
│  │Guest│ │Guest│ │Guest│             │       │       │     │
│  │ OS  │ │ OS  │ │ OS  │             │       │       │     │
│  └──┬──┘ └──┬──┘ └──┬──┘             └───────┼───────┘     │
│     └───────┼───────┘                        │             │
│             │                        ┌───────┴───────┐     │
│     ┌───────┴───────┐                │Container      │     │
│     │  Hypervisor   │                │Runtime        │     │
│     └───────┬───────┘                └───────┬───────┘     │
│             │                                │             │
│     ┌───────┴───────┐                ┌───────┴───────┐     │
│     │   Host OS     │                │   Host OS     │     │
│     └───────┬───────┘                └───────┬───────┘     │
│             │                                │             │
│     ┌───────┴───────┐                ┌───────┴───────┐     │
│     │   Hardware    │                │   Hardware    │     │
│     └───────────────┘                └───────────────┘     │
│                                                             │
│  Each VM has full OS                 Containers share      │
│  (heavy, slow to start)             host kernel (light)    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The table below preserves the common KCNA comparison, but each row should be read as a tradeoff rather than a universal ranking. Containers usually start in seconds and consume megabytes because they avoid booting a guest OS, but that efficiency comes from relying on the host kernel. VMs often start slower and use more storage, but they remain useful when the team needs different kernels, stronger tenant boundaries, or operating systems that cannot share a Linux kernel.

| Aspect | Virtual Machine | Container |
|--------|-----------------|-----------|
| **Size** | GBs | MBs |
| **Startup** | Minutes | Seconds |
| **Isolation** | Strong (separate kernel) | Process-level (shared kernel) |
| **Overhead** | High | Low |
| **Density** | ~10s per host | ~100s per host |
| **Portability** | Medium | High |

The security implication is the part beginners tend to underestimate. A VM escape usually has to cross a hypervisor boundary, while a container escape often means the attacker has found a way to abuse the shared kernel, a mounted host path, a privileged capability, or a misconfigured runtime. That does not make containers unsafe by default, but it does mean production clusters need defense in depth: non-root users, minimal capabilities, read-only filesystems where possible, trusted images, and workload isolation policies.

**Hypothetical scenario:** A platform team moves internal batch jobs from VMs to containers and celebrates the first capacity report because the same hosts can run many more jobs. Two weeks later, the team discovers that one job expected to write to `/var/log/app` forever, and every restarted container loses the local file unless a volume is mounted. The VM-era assumption had been that a server was a durable home; the container-era assumption needed to be that the process could be replaced at any moment.

Before running anything in Kubernetes, ask which boundary you actually need. If two teams own trusted services for the same product, containers on shared nodes may be a good fit. If unrelated customers run arbitrary code, the design may require separate nodes, sandboxed runtimes, or containers inside lightweight VMs. The KCNA-level answer is not "containers are better" or "VMs are better"; the answer is that each technology optimizes a different boundary.

Cost and speed often push teams toward containers, but risk should still have a vote. A development platform that runs internal build jobs may accept ordinary container isolation because the users, source repositories, and cluster administrators belong to the same organization. A public code execution platform has a different threat model because customers can submit unknown programs, so the same density advantage may need to be balanced with stronger isolation, per-tenant nodes, or sandboxed runtimes.

The operational habits differ as well. VM teams often manage long-lived hosts with patch windows, configuration management, and host-level monitoring. Container teams still patch nodes, but they also rebuild images, promote artifacts through registries, and treat container restarts as normal lifecycle events. When an organization migrates from VMs to containers, the hardest part is often not the command syntax; it is replacing server ownership habits with artifact and orchestration habits.

## Linux Isolation: Namespaces, Cgroups, and Layers

Containers feel like small systems because the Linux kernel can give a process a private view of selected operating system resources. Namespaces answer the question "what can this process see?" and cgroups answer the question "how much can this process use?" Union filesystems answer a third question that matters for packaging: "how can many containers share the same read-only files while each container gets its own writable changes?"

Namespaces are the visibility mechanism. A process in a PID namespace can see its own process tree, a process in a network namespace can see its own interfaces and routes, and a process in a mount namespace can see a filesystem layout that differs from the host. These are not pretend views created by a shell wrapper; they are kernel features that change what system calls return to the isolated process.

```text
┌─────────────────────────────────────────────────────────────┐
│              LINUX NAMESPACES                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Namespace     What It Isolates                            │
│  ─────────────────────────────────────────────────────────  │
│  PID           Process IDs (container sees own PIDs)       │
│  Network       Network interfaces, IPs, ports              │
│  Mount         Filesystem mounts                           │
│  UTS           Hostname and domain name                    │
│  IPC           Inter-process communication                 │
│  User          User and group IDs                          │
│                                                             │
│  Each container gets its own namespaces                    │
│  → Appears to have its own isolated system                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

When a container shell reports that it is PID 1, it is telling the truth within its PID namespace. The same process still has another PID from the host's perspective, and the host can manage it like any other process. This dual identity explains why a process can look like the first process inside the container while still being controlled by the runtime, kubelet, and node operating system outside the namespace.

Pause and predict: if containers share the host kernel, what happens if a containerized process exploits a kernel vulnerability? The isolation boundary can collapse because the kernel is common infrastructure, which is why patching nodes, reducing Linux capabilities, and avoiding privileged containers are not optional hardening details. Namespaces reduce what a process can see, but they do not turn one kernel into many kernels.

Cgroups provide the accounting and enforcement side of the model. Without cgroups, a process in a namespace could still consume the host's memory or CPU until other workloads suffer. With cgroups, the kernel can track resource use and apply limits, which is why Kubernetes resource requests and limits ultimately matter to the node rather than only to the scheduler.

```text
┌─────────────────────────────────────────────────────────────┐
│              CONTROL GROUPS (cgroups)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Cgroups limit and track resources:                        │
│                                                             │
│  CPU:      "Container A gets max 2 cores"                  │
│  Memory:   "Container B gets max 512MB"                    │
│  Disk I/O: "Container C gets max 100MB/s"                  │
│  Network:  "Container D gets max 100Mbps"                  │
│                                                             │
│  Without cgroups:                                          │
│  One container could consume ALL resources                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The financial-services outage from the opening scenario is a classic cgroup lesson. Namespace isolation made the reporting container look separate, but missing resource limits allowed the memory leak to compete directly with the host and neighboring containers. In Kubernetes, a memory limit gives the kernel a concrete boundary; when the process exceeds it, the container can be terminated instead of letting the node become unstable.

Union filesystems make images efficient enough to distribute and reuse. An image is built from read-only layers, and a running container receives a writable layer on top for runtime changes. If many containers use the same base image, the node can store those base layers once and attach separate writable layers to each running container.

```text
┌─────────────────────────────────────────────────────────────┐
│              CONTAINER IMAGE LAYERS                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Container Image (read-only layers):                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 4: Application code       (your app)         │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Layer 3: Dependencies           (npm packages)     │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Layer 2: Runtime                (Node.js)          │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Layer 1: Base OS                (Ubuntu slim)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Running Container adds:                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Writable layer  (runtime changes, logs, temp files)│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Benefits:                                                 │
│  • Layers are cached and reused                           │
│  • Multiple containers share base layers                  │
│  • Efficient storage and transfer                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Layer ordering has practical consequences. If the dependency layer changes every build, the runtime may need to rebuild or pull everything above it, even when application code is the only real change. If dependencies are stable and application code sits in the final layer, builds and pulls become faster because the base OS, runtime, and dependencies can remain cached.

Before running this, what output do you expect from `k get pods` after a container exceeds its memory limit in Kubernetes? The pod may restart, and its previous container state can show an OOMKilled reason, because the kernel enforced the cgroup limit and kubelet observed the termination. That observation connects a Linux primitive to a Kubernetes troubleshooting clue, which is exactly the bridge KCNA wants you to build.

The simplest diagnostic habit is to separate visibility failures from resource failures. If a process cannot see a file, hostname, network interface, or sibling process, think namespaces and mounts first. If a process slows down, restarts under load, or gets terminated with memory pressure, think cgroups, requests, limits, and node capacity first. The symptoms overlap sometimes, but this split keeps your first investigation grounded.

User namespaces add one more important nuance because they can map user and group IDs differently inside and outside the container. A process may appear to run as root inside its namespace while mapping to a less privileged identity on the host, depending on runtime support and configuration. That mapping can reduce risk, but it is not a substitute for careful security context design, because mounted files, Linux capabilities, and runtime privileges still influence what the process can actually do.

Try a quick prediction before moving on: if a pod shows `OOMKilled` after a traffic spike, which isolation primitive gives you the first clue, namespaces or cgroups? The answer should be cgroups, because the symptom is resource enforcement rather than visibility.

Network namespaces are another place where the Kubernetes abstraction builds on the container primitive. A standalone Docker container may receive its own network namespace and virtual interface, while a Kubernetes pod normally gives all containers in the pod a shared network namespace. That is why two containers in one pod can talk over `localhost`, and it is also why pod design should group tightly coupled processes rather than unrelated services that merely happen to share a deployment schedule.

Mount namespaces explain many "file not found" and "permission denied" surprises. The container may have a path that looks familiar, such as `/etc`, `/tmp`, or `/var`, but those paths belong to the container's filesystem view unless a volume or host path changes the mount layout. When a process writes logs to a path that is not backed by a volume or log collector, the data may disappear with the container, even though the path looked durable from inside the shell.

Cgroups also influence scheduling expectations before a process starts. Kubernetes uses resource requests to decide where a pod can fit, and the node runtime uses limits to enforce boundaries after the container is running. If a team copies tiny requests from an example manifest, the scheduler may pack too many pods onto a node; if a team sets limits without observing memory spikes, the kernel may terminate a process that looked healthy during ordinary traffic.

## Images, Registries, Tags, and OCI Portability

An image is a read-only template used to create containers, while a container is a running instance created from that template. The recipe analogy is still useful because a recipe can produce many cakes, and an image can produce many containers. The analogy breaks if you imagine the recipe changing after the cake is baked; a running container can add writable changes, but those changes do not mutate the original image layers.

| Concept | Analogy |
|---------|---------|
| Image | Recipe / Blueprint |
| Container | Cake / Building |

Image references look small, but they carry important operational meaning. A reference can include the registry location, repository name, and tag, and a production-grade reference can also include a digest that identifies the exact image content. Tags are convenient labels, but digests are stronger evidence when you need to prove that every node is running identical bytes.

```text
registry/repository:tag

Examples:
docker.io/library/nginx:1.25
gcr.io/google-containers/pause:3.9
mycompany.com/myapp:v2.1.0

Parts:
• registry:    Where image is stored (docker.io, gcr.io)
• repository:  Name of the image (nginx, myapp)
• tag:         Version identifier (1.25, latest, v2.1.0)
```

The `latest` tag deserves special suspicion because it sounds like a promise but behaves like a mutable pointer. A node that pulled `myapp:latest` yesterday and another node that pulls it today may receive different content if the tag was overwritten. That behavior is convenient during local experiments, but in production it breaks repeatability, incident rollback, and forensic analysis.

Registries are distribution systems for images, and they can be public, private, cloud-hosted, or self-managed. Kubernetes does not care whether an image came from Docker Hub, a cloud registry, or a private enterprise registry as long as the node can authenticate, pull the layers, and hand the image to a compatible runtime. The registry decision usually depends on supply-chain controls, network locality, audit requirements, and integration with the organization's identity system.

| Registry | Description |
|----------|-------------|
| Docker Hub | Default public registry |
| gcr.io | Google Container Registry |
| ECR | Amazon Elastic Container Registry |
| ACR | Azure Container Registry |
| Quay.io | Red Hat registry |

The Open Container Initiative, usually shortened to OCI, is what keeps the ecosystem from fragmenting into one image format per tool. OCI image and runtime specifications describe how images are structured and how containers should be created at a low level. Because of those standards, an image built by Docker can be stored in a registry and run by containerd or CRI-O on a Kubernetes node.

This portability is the answer to a common Docker deprecation fear. Kubernetes removed dockershim in version 1.24, but it did not reject images built with Docker. Docker images that follow the OCI image format remain usable because Kubernetes talks to a runtime through CRI, and the runtime understands the image format; the removed piece was a compatibility shim around Docker Engine as a runtime path.

Which approach would you choose here and why: a mutable tag such as `latest`, a semantic version tag such as `v1.2.4`, or a digest pin for a regulated production deployment? A semantic version tag is better than `latest`, but a digest gives the strongest content identity because tags can be moved. Many teams use both a readable tag and a digest in release evidence so humans can discuss versions while automation verifies exact content.

Registries also become policy enforcement points as organizations mature. A small team may pull directly from a public registry during experiments, but a production platform often mirrors approved images into a private registry after scanning and signing. That extra step is not bureaucracy for its own sake; it gives the organization a place to record provenance, block known vulnerable artifacts, and keep deployments working even if an external registry has an outage or rate limit.

Tags and digests answer different human questions. A tag such as `v1.2.4` answers "which release did we intend to deploy?" while a digest answers "which exact content did the runtime pull?" During a rollback, you usually want both pieces of information because people discuss incidents in release names, but machines prove consistency with content identifiers. Confusing those jobs leads to arguments where everyone uses the same image name but not the same bytes.

Image layer design also influences security updates. If a base image receives an important package fix, every application image built on that base must be rebuilt and promoted, even when application code has not changed. Teams sometimes assume that using a tag like `ubuntu:22.04` automatically updates running containers, but existing images and containers do not magically change; the build and deployment pipeline has to create and roll out new artifacts.

Here is a minimal Kubernetes pod manifest that uses an explicit image tag and a non-root security posture. You do not need to run it for this module, but reading it connects packaging decisions to the API objects you will use later. The command examples use `k`, and the alias was introduced at the top of the module.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: container-fundamentals-demo
spec:
  containers:
    - name: web
      image: docker.io/library/nginx:1.25
      securityContext:
        runAsNonRoot: true
        allowPrivilegeEscalation: false
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 500m
          memory: 256Mi
```

```bash
alias k=kubectl
k apply -f pod.yaml
k get pods container-fundamentals-demo
k describe pod container-fundamentals-demo
```

The manifest is intentionally modest because the point is not yet advanced workload design. The tag is explicit, the resource boundaries map to cgroups, and the security context reduces the consequences if the application is compromised. In later Kubernetes modules you will learn how Deployments, Services, and admission policies build on these same image and runtime assumptions.

## Container Runtimes and Kubernetes CRI

Kubernetes does not run containers by itself. The kubelet on each node asks a container runtime to pull images, create containers, start them, stop them, and report status. That runtime work is exposed through the Container Runtime Interface, or CRI, so kubelet can use a standard API instead of embedding every runtime's private implementation details.

The runtime landscape can be confusing because Docker is both a developer tool and a historical runtime path. Docker Engine includes high-level image build and developer workflow features, while containerd is a lower-level runtime component focused on pulling images, managing snapshots, and supervising containers. CRI-O is another Kubernetes-focused runtime that implements CRI directly and is common in OpenShift-oriented environments.

```text
┌─────────────────────────────────────────────────────────────┐
│              CONTAINER RUNTIME INTERFACE (CRI)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    Kubernetes                               │
│                         │                                   │
│                         │ CRI (standard interface)          │
│                         │                                   │
│         ┌───────────────┼───────────────┐                  │
│         │               │               │                   │
│         ▼               ▼               ▼                   │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐              │
│   │containerd│   │  CRI-O   │   │  Docker  │              │
│   │          │   │          │   │(via shim)│              │
│   └──────────┘   └──────────┘   └──────────┘              │
│                                                             │
│  containerd: Default in most K8s distributions            │
│  CRI-O:      Lightweight, Kubernetes-focused              │
│  Docker:     Deprecated in K8s 1.24+                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

For KCNA, the key point is that Kubernetes uses CRI to talk to container runtimes, and containerd is the most common runtime in many Kubernetes distributions. The older Docker path required dockershim because Docker Engine did not expose CRI in the shape kubelet needed. Removing dockershim reduced an extra integration layer, but it did not remove Docker as a build tool from developer laptops.

A container lifecycle starts before the process exists. The runtime pulls the image, prepares the root filesystem from image layers, configures namespaces and cgroups, creates the container, starts the entry point, watches the running process, and eventually stops and removes it. Kubernetes adds pod-level orchestration around that lifecycle, but the process creation remains runtime work on the node.

```text
┌─────────────────────────────────────────────────────────────┐
│              CONTAINER LIFECYCLE                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Pull Image                                             │
│     Download image from registry                           │
│                    │                                        │
│                    ▼                                        │
│  2. Create Container                                       │
│     Prepare filesystem, namespaces, cgroups               │
│                    │                                        │
│                    ▼                                        │
│  3. Start Container                                        │
│     Execute the container's entry point                   │
│                    │                                        │
│                    ▼                                        │
│  4. Running                                                │
│     Container is executing                                 │
│                    │                                        │
│         ┌─────────┴─────────┐                              │
│         │                   │                               │
│         ▼                   ▼                               │
│  5a. Stop              5b. Crash                          │
│      Graceful              Unexpected                      │
│      shutdown              termination                     │
│         │                   │                               │
│         └─────────┬─────────┘                              │
│                   │                                         │
│                   ▼                                         │
│  6. Remove Container                                       │
│     Clean up resources                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Lifecycle thinking prevents a common debugging mistake. If an image pull fails, the application code never started, so reading application logs is the wrong first move. If the container starts and exits immediately, the entry point or process behavior is more likely than the registry. If the process runs and then restarts under load, resources, probes, or runtime enforcement become better suspects.

The same reasoning applies when inspecting pods in Kubernetes. A pod stuck in `ImagePullBackOff` points toward registry access, image name, tag, credentials, or network path. A pod in `CrashLoopBackOff` means the image was pulled and the container process started, but the main process exited repeatedly. A pod with `OOMKilled` in the previous state points straight back to cgroup-enforced memory limits.

Here is a compact runtime inspection sequence you can use on a test cluster when the pod from the previous section is present. The goal is not to memorize commands; it is to connect the Kubernetes status you see through `k` to the runtime activity underneath kubelet.

```bash
alias k=kubectl
k get pod container-fundamentals-demo -o wide
k describe pod container-fundamentals-demo
k get pod container-fundamentals-demo -o jsonpath='{.status.containerStatuses[0].imageID}{"\n"}'
```

If the output shows an image ID with a digest, Kubernetes is reporting the concrete image that the runtime used, not merely the friendly tag from the manifest. That matters during rollbacks because a tag can be reused while a digest identifies content. When production teams investigate whether every replica is running the same build, image IDs and digests are often more trustworthy than names alone.

The runtime boundary also explains why Kubernetes node troubleshooting sometimes uses tools that application developers never touch. A developer may build with Docker and push to a registry, while an operator on a node may inspect containerd state with `crictl` or runtime-specific tooling. Both people are working with the same container lifecycle, but from different control points: one creates artifacts, and the other verifies how kubelet and the runtime turned those artifacts into processes.

Kubelet is the translator between Kubernetes intent and node reality. The API server stores the desired pod, the scheduler chooses a node, and kubelet asks the runtime to make the container state match the pod spec. If the runtime cannot pull the image, create the container, or start the process, kubelet reports that failure back through pod status and events. Reading those events is therefore not optional bookkeeping; it is the node telling you which part of the lifecycle failed.

In production, runtime choice is usually made by the Kubernetes distribution rather than by each application team. A managed cluster might standardize on containerd, while an OpenShift environment may use CRI-O, and application teams normally should not care as long as their images are portable and their manifests avoid runtime-specific assumptions. The design win is that platform teams can choose the runtime implementation while workload teams rely on the CRI and OCI contracts.

## Patterns & Anti-Patterns

Even an introductory container module benefits from a small pattern catalog because production failures often come from repeating the same simple mistake under pressure. Patterns are not rules for every situation; they are defaults that make the normal path safer. Anti-patterns are attractive shortcuts that seem harmless during development but create ambiguity, weak isolation, or unreproducible behavior in clusters.

| Type | Practice | When to Use It | Why It Works | Scaling Consideration |
|------|----------|----------------|--------------|-----------------------|
| Pattern | Pin images with explicit versions or digests | Any shared or production environment | Makes rollouts and rollbacks reproducible | Automate updates so pinning does not block patching |
| Pattern | Set CPU and memory requests and limits deliberately | Workloads with predictable resource needs | Maps scheduling intent and cgroup enforcement to workload behavior | Revisit limits using real metrics instead of copying defaults |
| Pattern | Run as non-root with minimal capabilities | Internet-facing and internal services alike | Reduces the impact of application compromise | Combine with admission control so exceptions are visible |
| Anti-pattern | Treating containers as lightweight VMs | Teams migrating server habits directly into Kubernetes | Leads to mutable state, hidden dependencies, and poor lifecycle handling | Move state to volumes or services and rebuild images for changes |
| Anti-pattern | Using `latest` in production manifests | Teams trying to get automatic updates without a release process | Makes node pulls non-deterministic and breaks audit evidence | Use release tags, digests, and automated vulnerability scanning |
| Anti-pattern | Ignoring runtime status fields | Teams jumping straight from pod failure to application code | Misses image pull, cgroup, and lifecycle clues surfaced by kubelet | Standardize first-response commands for pod status and events |

The pattern behind all three good practices is explicitness. An explicit image version tells the runtime what content to fetch, explicit resources tell the kernel what to enforce, and an explicit security context tells the runtime which privileges the process should not receive. Kubernetes is powerful because it turns these decisions into declarative state, but it cannot infer a release policy, a resource budget, or a security boundary from good intentions.

The anti-patterns share the opposite failure mode: they preserve ambiguity. Treating a container like a VM makes people patch running instances instead of rebuilding images. Using `latest` makes two nodes disagree about what "the app" means. Ignoring runtime status makes every symptom look like an application bug, even when kubelet is already telling you that the image never pulled or the kernel killed the process.

Scaling these patterns requires automation rather than heroics. If version pinning depends on every developer remembering the right tag format, it will drift under release pressure. If resource tuning depends on a one-time guess, it will rot as traffic and code change. Good platforms make the safe path ordinary by providing base images, release templates, vulnerability scans, policy checks, and dashboards that show when a workload is outside its expected resource envelope.

There is still room for judgment because not every environment has the same risk profile. A throwaway learning cluster can tolerate `latest`, root containers, and tiny resource guesses while a student is exploring concepts. A shared production cluster should make those same choices difficult or impossible. The point of learning the fundamentals is to know when a shortcut is a learning convenience and when it has become an operational liability.

## Decision Framework

When you choose how to package or run a workload, start by naming the boundary you need. If the workload is trusted, Linux-based, and benefits from quick scaling, a normal container runtime is usually appropriate. If the workload needs a different kernel, strict tenant isolation, or arbitrary untrusted code execution, the design should consider VMs, sandboxed runtimes, or node separation before a shared-kernel container becomes the default.

```text
┌─────────────────────────────────────────────────────────────┐
│              CONTAINER DECISION FRAMEWORK                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Need a different kernel or OS? ── yes ──► Use a VM path    │
│              │                                              │
│              no                                             │
│              ▼                                              │
│  Running untrusted tenant code? ── yes ──► Add sandboxing   │
│              │                         or node isolation    │
│              no                                             │
│              ▼                                              │
│  Need fast rollout and density? ── yes ──► Use containers   │
│              │                                              │
│              no                                             │
│              ▼                                              │
│  Prefer the simpler operating model that matches the risk   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Use containers when the main problem is packaging dependencies, scaling many similar Linux processes, and replacing instances quickly. Use VMs when the main problem is kernel isolation, operating-system diversity, or a strong administrative boundary between tenants. Use sandboxed container approaches when the team wants container workflows but needs a thicker boundary than ordinary namespaces and cgroups provide.

The same decision frame applies to image references. Use a floating tag only for local experiments where surprise is acceptable. Use an explicit version tag for normal development and staging workflows where humans need readable release names. Use digests, or tags plus digest evidence, when production reproducibility and auditability matter more than convenience.

For troubleshooting, choose the layer that matches the symptom. Image reference and registry problems belong before container creation. Namespace, filesystem, and entry-point problems appear during creation or start. Cgroup and health problems usually appear while the container is running. This sequencing saves time because it prevents you from inspecting application logs for a container that never existed.

The framework is also useful during design reviews. When someone proposes putting three unrelated services into one pod because they are all "small containers," ask whether they should truly share lifecycle, network namespace, and scheduling fate. When someone proposes a privileged container for convenience, ask which kernel or host access is actually required. When someone proposes a floating image tag, ask how the team will prove what ran during an incident.

For KCNA exam questions, translate wording into layers. If the question mentions host kernel sharing, compare containers with VMs. If it mentions visibility of processes or networks, think namespaces. If it mentions resource starvation, think cgroups. If it mentions Docker images still running after dockershim removal, think OCI image portability and CRI runtime integration. That translation habit turns memorized facts into a troubleshooting model.

## Did You Know?

- **Containers are older than Docker.** Unix `chroot` appeared in 1979, FreeBSD jails arrived in 2000, and Docker popularized the developer-friendly container workflow in 2013.
- **Docker images did not disappear from Kubernetes.** Kubernetes removed dockershim in version 1.24, but OCI-compatible images built with Docker still run through containerd and CRI-O.
- **OCI has two core specifications for this module.** The image specification standardizes packaged content, and the runtime specification standardizes how a filesystem bundle becomes a running container.
- **Kernel sharing explains OS limits.** A Linux container expects a Linux kernel interface, so running Windows containers on Linux requires a virtualization layer rather than ordinary shared-kernel isolation.

## Common Mistakes

Common mistakes usually begin as reasonable shortcuts in a small environment. The fix is not to shame the shortcut; it is to recognize where the shortcut stops scaling. Use this table as a review checklist when you read a manifest, debug a failed pod, or explain container fundamentals to a teammate.

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| "Containers are lightweight VMs" | The UI feels like a tiny machine, so teams miss the shared-kernel architecture. | Explain that containers are isolated processes sharing the host kernel, then choose VM or sandbox isolation when the boundary requires it. |
| "Each container has its own OS" | Images contain userspace files that look like an operating system distribution. | Say that images carry userspace, libraries, and tools, while the kernel comes from the host node. |
| "Docker equals containers" | Docker is the most familiar developer tool, so people confuse the tool with the runtime model. | Separate Docker as a build and workflow tool from runtimes such as containerd and CRI-O. |
| "Images and containers are the same" | Both words appear together in commands and dashboards. | Treat the image as the read-only template and the container as the running instance with its own writable layer. |
| Running containers as root by default | Local examples often work without setting a user or security context. | Configure a non-root user in the image or Kubernetes security context, and remove unnecessary privileges. |
| Using the `latest` tag in production | Teams want automatic updates without designing a release process. | Pin versions or digests, then use automation to rebuild and promote patched images intentionally. |
| Ignoring image layer ordering | Builds still succeed, so cache behavior is easy to overlook. | Put stable base, runtime, and dependency steps before frequently changing application files. |
| Not setting cgroup resource limits | Small test workloads rarely exhaust the node. | Define CPU and memory requests and limits, then tune them from observed workload metrics. |

## Quiz

Each question below is scenario-based because container fundamentals matter most when you can apply them under pressure. Read the symptom first, decide which layer is most likely involved, and then open the answer to compare your reasoning with the explanation.

<details>
<summary>Your team says containers are just lightweight VMs because both package applications. How do you compare containers and virtual machines, and why does the distinction matter during incident response?</summary>

Containers and VMs package workloads behind different boundaries. A VM includes a guest operating system and kernel on top of a hypervisor, while a container is an isolated process that shares the host kernel and carries only the userspace it needs. During incident response, that distinction tells you whether to investigate guest OS boot behavior and hypervisor isolation or namespace, cgroup, image, and runtime behavior on the node. It also shapes risk decisions because shared-kernel containers need hardening and patching at the node level.
</details>

<details>
<summary>A pod can see files it should not see after a host path was mounted for troubleshooting. Which namespace or filesystem idea helps you diagnose the problem?</summary>

Start with the mount namespace and the container filesystem view. Containers normally see a prepared root filesystem assembled from image layers and mounts, but a host path mount deliberately exposes part of the node filesystem into that view. The fix is to remove the unnecessary host path, narrow the mount to the least required directory, or replace it with a safer volume pattern. This is not primarily a cgroup issue because the symptom is about visibility, not resource consumption.
</details>

<details>
<summary>A service restarts only during traffic spikes, and `k describe pod` shows the previous container state as OOMKilled. Which Linux feature is involved, and what should the team change?</summary>

The relevant feature is cgroups, because the kernel is enforcing the container's memory boundary. The restart means the process exceeded its configured memory limit or ran on a node where memory pressure exposed an unrealistic setting. The team should inspect real memory use, tune requests and limits, and fix leaks or excessive buffering in the application. Raising limits without understanding usage may hide the symptom while leaving the workload inefficient.
</details>

<details>
<summary>A developer builds an image with Docker, but production Kubernetes 1.35 nodes use containerd. Can that image run, and what standard makes the answer reliable?</summary>

Yes, the image can run if it is OCI-compatible, which ordinary Docker-built images are expected to be. Kubernetes talks to containerd through CRI, and containerd can pull and run OCI images from registries. Docker as a developer build tool is not the same thing as Docker Engine as the Kubernetes runtime path. The important distinction is that the image format remains portable even though dockershim was removed in Kubernetes 1.24.
</details>

<details>
<summary>A production Deployment uses `myapp:latest`, and after a node replacement only one replica starts failing. How do you evaluate the image reference problem?</summary>

The mutable tag is the likely source of inconsistency because the replacement node may have pulled different content than the older nodes. Tags are human-friendly labels, but they can be moved, so `latest` does not guarantee identical bytes across time. The fix is to deploy explicit version tags or digests and record the image ID that actually ran. That gives rollback, audit, and debugging workflows a stable target.
</details>

<details>
<summary>An application image has base OS, runtime, dependencies, and application code layers. The team changes only application code but rebuilds are slow because dependency installation runs every time. What should you inspect?</summary>

Inspect the Dockerfile or build recipe for layer ordering and cache invalidation. If dependency metadata or installation steps are placed after frequently changing application files, every code edit can invalidate the dependency layer and force expensive rebuilds. Stable layers should come first, while frequently changing application code should sit near the end. This layout also helps nodes reuse existing layers when multiple containers share the same base and runtime.
</details>

<details>
<summary>A security audit finds the main process runs as root inside the container, and the developer argues namespaces are enough. How should you respond?</summary>

Namespaces reduce what the process can see, but they do not make root harmless. A root process inside a container may still have more privilege than the workload needs, and a runtime, kernel, capability, or mount misconfiguration can increase the blast radius of a compromise. The better design is to run as a non-root user, drop unnecessary capabilities, avoid privileged mode, and set Kubernetes security context fields explicitly. That approach accepts that containers are useful isolation, not a perfect security boundary.
</details>

<details>
<summary>You need to implement a first inspection workflow for a failing pod before reading application code. Which runtime lifecycle clues should you check first?</summary>

Start by checking whether the image pulled, whether the container was created, whether the entry point started, and how the previous container terminated. `k describe pod` surfaces events such as image pull failures, crash loops, and OOMKilled states, while container status fields can show the image ID and restart history. This sequence follows the lifecycle from registry to runtime to running process. It prevents you from debugging application logic when the runtime never successfully started the application.
</details>

## Hands-On Exercise

This exercise preserves the original local container inspection path and adds a Kubernetes-oriented interpretation layer. You can use Docker if it is installed locally, or `nerdctl` with containerd if that is your runtime tool. The goal is to observe namespace isolation, image layers, and lifecycle state, then connect those observations to what Kubernetes reports through kubelet and CRI.

### Setup

Use one terminal for local runtime commands and, if you have a test cluster, another terminal for optional Kubernetes commands. The Docker commands below are intentionally simple because the learning target is the model, not a complex application. If Docker is unavailable, translate the same steps to your local containerd workflow with `nerdctl`.

### Task 1: Run a Simple Container

Start an interactive Alpine Linux container and notice that the shell becomes the main process inside the container namespace.

```bash
docker run -it alpine sh
```

<details>
<summary>Solution notes</summary>

The command pulls the Alpine image if needed, creates a container, starts `sh`, and attaches your terminal to it. You are now inside the container's namespace view, not inside a new VM. Keep the shell open for the next task so you can inspect the process tree from the container's perspective.
</details>

### Task 2: Diagnose Process Isolation with Namespaces

Inside the container, list the running processes and compare that small process list with what you know is running on the host.

```bash
ps aux
```

<details>
<summary>Solution notes</summary>

The shell usually appears as PID 1 inside the container because the PID namespace gives the process a private view. The host still has its own PID for the same process, and the runtime can manage it from outside. This is the easiest hands-on proof that namespace isolation changes visibility rather than creating a separate kernel.
</details>

### Task 3: Exit and Observe Container Lifecycle State

Exit the shell, then inspect all containers so you can see what happened when the main process ended.

```bash
docker ps -a
```

<details>
<summary>Solution notes</summary>

The container is in an `Exited` state because its main process terminated when you left the shell. Kubernetes uses the same underlying idea when a container process exits inside a pod, although kubelet adds restart policy behavior and pod status reporting around it. A stopped container is not a reusable server; it is evidence of a process lifecycle.
</details>

### Task 4: Explore Image Layers

Pull an image and inspect the layer list so you can see the read-only filesystem pieces that form the image.

```bash
docker pull nginx:latest
docker image inspect nginx:latest | grep -A 10 "Layers"
```

<details>
<summary>Solution notes</summary>

The SHA256 entries represent content-addressed layers that the runtime can cache and reuse. In production you would avoid `latest`, but it remains acceptable for this local inspection because the exercise is about observing layers. The important lesson is that a running container adds a writable layer on top of these read-only pieces.
</details>

### Task 5: Connect the Runtime Model to Kubernetes

If you have a disposable Kubernetes 1.35 test cluster, create a pod manifest from the earlier YAML example, apply it, and inspect the pod status with the short alias.

```bash
alias k=kubectl
k apply -f pod.yaml
k get pods
k describe pod container-fundamentals-demo
```

<details>
<summary>Solution notes</summary>

The Kubernetes output should show whether the image pulled, whether the container started, and which events kubelet recorded. If the pod fails, classify the failure by lifecycle stage before changing the manifest. Image reference problems, start command problems, and resource problems produce different clues even though all of them may appear as a pod that is not healthy.
</details>

### Success Criteria

- [ ] You successfully started an interactive container and implemented a basic runtime inspection workflow.
- [ ] You diagnosed namespace behavior by verifying that the container has its own isolated process tree with PID 1.
- [ ] You inspected an image to see its composed layers and evaluated why layer reuse matters.
- [ ] You compared containers and virtual machines using the shared-kernel boundary rather than the "lightweight VM" shortcut.
- [ ] You connected Docker, containerd or CRI-O, CRI, and Kubernetes pod status into one runtime lifecycle model.
- [ ] You identified at least one production hardening step: non-root execution, explicit tags or digests, or cgroup-backed resource limits.

## Sources

The sources below are primary project, standards, or vendor references for the container model described in this module. Source reachability is intentionally separated from the local verifier run for this rewrite, but the links are chosen so you can validate the claims against authoritative documentation.

- [Kubernetes: Container Runtimes](https://kubernetes.io/docs/setup/production-environment/container-runtimes/)
- [Kubernetes: Images](https://kubernetes.io/docs/concepts/containers/images/)
- [Kubernetes: Pods](https://kubernetes.io/docs/concepts/workloads/pods/)
- [Kubernetes: Configure a Security Context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Kubernetes: Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes: Kubernetes v1.24 Release Notes](https://kubernetes.io/blog/2022/05/03/kubernetes-1-24-release-announcement/)
- [OCI Image Specification](https://github.com/opencontainers/image-spec)
- [OCI Runtime Specification](https://github.com/opencontainers/runtime-spec)
- [containerd Documentation](https://containerd.io/docs/)
- [CRI-O Project](https://cri-o.io/)
- [Docker: Use Containers to Build, Share and Run Applications](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/)
- [Linux man-pages: namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [Linux man-pages: cgroups](https://man7.org/linux/man-pages/man7/cgroups.7.html)

## Next Module

[Module 1.3: Kubernetes Architecture - Control Plane](../module-1.3-control-plane/) introduces the control-plane components that decide where containers run, how desired state is stored, and how node agents turn API intent into running workloads.
