---
revision_pending: false
title: "Module 2.5: Resource Management"
slug: k8s/cka/part2-workloads-scheduling/module-2.5-resource-management
sidebar:
  order: 6
lab:
  id: cka-2.5-resource-management
  url: https://killercoda.com/kubedojo/scenario/cka-2.5-resource-management
  duration: "40 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Critical for production workloads
>
> **Time to Complete**: 40-50 minutes
>
> **Prerequisites**: Module 2.1 (Pods), Module 2.2 (Deployments)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Configure** CPU and memory resource requests and limits, then explain how those values affect scheduling and runtime enforcement.
- **Diagnose** OOMKilled containers, CPU throttling, resource-pressure evictions, and Pending pods caused by insufficient allocatable resources.
- **Implement** namespace resource governance with LimitRange defaults, ResourceQuota caps, and checks that prove the controls are working.
- **Design** a resource strategy that balances application reliability, cluster utilization, burst tolerance, and Kubernetes 1.35+ resize options.

---

## Why This Module Matters

Hypothetical scenario: a team launches a new API into a shared Kubernetes cluster with no resource requests and no namespace quota. The pods start quickly in a quiet test namespace, so the manifests look harmless, but during the first busy morning the containers grow until the node enters memory pressure. Other workloads that did reserve memory are now competing with BestEffort pods, the kubelet starts evicting lower-priority candidates, and the incident feels random because the failing application is not the only application that made the original mistake.

Resource management turns that kind of surprise into a set of explicit promises. A request tells the scheduler what capacity a pod needs before it is placed. A limit tells the container runtime where to enforce a boundary after the pod is running. A LimitRange gives a namespace reasonable defaults and guardrails, while a ResourceQuota limits the total amount a team can consume. The point is not to memorize YAML fields; the point is to design resource contracts that make scheduling, failures, and ownership predictable.

The CKA exam tests this because the same mechanics show up in production triage. A Pending pod may not be broken at all; it may simply ask for more CPU or memory than any node can provide after existing requests are counted. A restarting pod may not have an application exception; it may be crossing a cgroup memory limit and receiving a SIGKILL from the kernel. A slow pod may not be unhealthy; it may be hitting CPU throttling because a low limit prevents short bursts. In this module you will connect those symptoms to the Kubernetes objects that created them, then practice the commands that prove the diagnosis.

The hotel-room analogy is still useful if you keep its limits in mind. A node is like a hotel, requests are reservations, and limits are occupancy rules. The scheduler assigns rooms based on reservations, not on guesses about who might show up later. Once the guests arrive, memory limits are strict fire-code boundaries, while CPU limits behave more like a time-share rule that slows a noisy guest instead of evicting them immediately.

## Resource Contracts: Requests, Limits, and Units

Kubernetes resource management begins with a split between scheduling intent and runtime enforcement. A request is the amount of CPU or memory Kubernetes uses when deciding whether a node has enough allocatable capacity for a pod. A limit is the maximum amount a container may consume after it starts. Those fields sit next to each other in a manifest, but they answer different questions, and confusing them is the source of many exam mistakes and production outages.

The simplest manifest shows the shape of the contract. This pod asks the scheduler to reserve `100m` of CPU and `128Mi` of memory, but it allows the container to burst up to `500m` CPU and `256Mi` memory while it is running. The scheduler uses only the request for placement, so a small request can make placement easier, but an unrealistically small request also makes the pod more vulnerable during node pressure because the pod is borrowing capacity it did not reserve.

Think of the request as the amount of capacity you are willing to make unavailable to other pods even when your container is quiet. That may sound wasteful, but it is the foundation for predictable placement. If ten pods each request `100m`, the scheduler can reason about one CPU core of committed work before any process starts. If those same pods omit requests, the scheduler has no declared baseline and may pack them onto a node that looks acceptable only because the busiest moment has not arrived yet.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: resource-demo
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:          # Minimum guaranteed resources
        memory: "128Mi"
        cpu: "100m"
      limits:            # Maximum allowed resources
        memory: "256Mi"
        cpu: "500m"
```

| Aspect | Requests | Limits |
|--------|----------|--------|
| Purpose | Scheduling guarantee | Hard cap |
| When used | Scheduler deciding placement | Container runtime enforcement |
| Underutilized | Other pods can use slack | N/A |
| Exceeded | N/A | Container killed for memory or throttled for CPU |

**Pause and predict:** Suppose a pod requests `100m` CPU and `128Mi` memory alongside a `256Mi` memory limit without setting any CPU limit. Which value governs node scheduling, which threshold triggers process termination, and which compute resource can burst above its initial reservation?

<details>
<summary>Check your prediction</summary>

Requests are what the scheduler uses for placement decisions, calculating whether the candidate node has sufficient allocatable capacity. The memory limit is what can OOMKill the container when resident memory usage crosses that specified ceiling. CPU with no limit can still burst above its request whenever excess host cycles exist, while the memory limit cannot be crossed safely without triggering process termination.

The diagram below captures the most important operational distinction. Memory and CPU both have requests and limits, but they do not fail in the same way when a container crosses the limit. Memory is not compressible in the same way CPU time is, so a container that crosses its memory limit can be killed with an OOMKilled reason. CPU can be sliced over time, so a container that crosses its CPU limit is throttled and continues running more slowly.

```text
┌────────────────────────────────────────────────────────────────┐
│                    Requests vs Limits                           │
│                                                                 │
│   Memory: 128Mi request, 256Mi limit                           │
│                                                                 │
│   0        128Mi      256Mi                  Node Memory       │
│   ├─────────┼──────────┼───────────────────────────────────►   │
│   │         │          │                                       │
│   │ Reserved│ Can grow │ OOMKilled if exceeded                │
│   │(guara-  │ into this│                                       │
│   │ nteed)  │ space    │                                       │
│                                                                 │
│   CPU: 100m request, 500m limit                                │
│                                                                 │
│   0       100m       500m                    Node CPU          │
│   ├─────────┼──────────┼───────────────────────────────────►   │
│   │         │          │                                       │
│   │ Reserved│ Can burst│ Throttled (not killed)               │
│   │         │ up to    │                                       │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

</details>

The next section is parsing core syntax units and millicores across manifests, where subtle notation choices create unexpected production surprises.

CPU units are easy to misread under exam pressure. Kubernetes lets you write CPU in whole cores or millicores, where `1000m` means one core and `100m` means one tenth of a core. A request of `100m` does not mean the process can only ever use one tenth of a core unless you also set a low CPU limit; it means the scheduler reserves that much capacity for placement and the runtime can enforce the limit if one exists.

| Value | Meaning |
|-------|---------|
| `1` | 1 CPU core |
| `1000m` | 1 CPU core, written in millicores |
| `100m` | 0.1 CPU core, or 100 millicores |
| `500m` | 0.5 CPU core |

Memory units have a separate trap because Kubernetes accepts both decimal and binary suffixes. `Mi` means mebibytes, based on powers of two, while `M` means megabytes, based on powers of ten. The difference is small enough to miss in a casual review and large enough to matter when you are setting tight limits across many pods. In manifests, use `Mi` and `Gi` consistently unless you have a deliberate reason to use decimal units.

Requests and limits also interact with multi-container pods. Kubernetes schedules the pod as a unit, so it adds the requests for the main container, sidecars, and init-related accounting when deciding whether the pod fits. A sidecar with missing or mismatched resources can change both scheduling pressure and QoS classification. In real reviews, do not stop after checking the first container named `app`; inspect every container in the pod template because the scheduler and kubelet evaluate the combined pod, not your mental model of the primary process.

| Value | Meaning |
|-------|---------|
| `128Mi` | 128 mebibytes, or 128 times 1024 squared bytes |
| `1Gi` | 1 gibibyte |
| `256M` | 256 megabytes, or 256 times 1000 squared bytes |

## Scheduling, Pending Pods, and Node Pressure

The scheduler does not place pods by watching live CPU and memory usage. It sums the requests of pods already assigned to a node, compares that total against the node's allocatable resources, and checks whether the new pod's requests fit. Allocatable is not the same as raw capacity because the node reserves some resources for the operating system, kubelet, and other node-level work. This is why a node with four CPU cores may expose less than four cores as allocatable to pods.

```bash
# Check node allocatable resources
kubectl describe node <node-name> | grep -A6 "Allocatable"

# Allocatable:
#   cpu:                2
#   memory:             4Gi
#   pods:               110
```

The placement decision is conservative by design. Kubernetes would rather leave a pod Pending than place it on a node where the requested resources cannot be promised. That does not mean the cluster has no idle CPU at that instant; it means the requested reservations no longer fit according to the scheduler's accounting. On a busy cluster, this distinction is useful because it separates capacity planning problems from application startup problems.

This is why a Pending pod is often a capacity signal instead of an application bug. The container has not pulled an image, started a process, or emitted application logs because the scheduler has not bound it to a node. When you see `Pending`, read the events before changing the image or restarting controllers. A FailedScheduling message that names insufficient memory tells you to inspect requests, node allocatable capacity, quotas, and placement constraints; it does not tell you to debug the application binary.

```text
┌────────────────────────────────────────────────────────────────┐
│                   Scheduling Decision                           │
│                                                                 │
│   Node Capacity: 4Gi memory                                    │
│   Already Requested: 3Gi                                       │
│   Available: 1Gi                                               │
│                                                                 │
│   Pod A requests 2Gi memory                                    │
│   → Cannot schedule (2Gi > 1Gi available)                      │
│   → Pod stays Pending                                          │
│                                                                 │
│   Pod B requests 500Mi memory                                  │
│   → Can schedule (500Mi < 1Gi available)                       │
│   → Pod placed on node                                         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

You can create the failure mode directly by asking for a large amount of memory. The pod is valid YAML, and the container image is ordinary, but the scheduler cannot bind it if no node has enough remaining allocatable memory after requests are considered. In an exam, the fastest path is usually `kubectl describe pod` and the Events section, because the FailedScheduling message tells you whether the issue is insufficient CPU, insufficient memory, taints, affinity, or another placement constraint.

```bash
# Create pod with huge request
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: big-pod
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        memory: "100Gi"
EOF

# Check status
kubectl get pod big-pod
# NAME      READY   STATUS    RESTARTS   AGE
# big-pod   0/1     Pending   0          10s

# Check why
kubectl describe pod big-pod | grep -A5 "Events"
# Warning  FailedScheduling  Insufficient memory
```

Node pressure is different from scheduling failure because it happens after pods are already running. A node can enter MemoryPressure, DiskPressure, or PIDPressure when kubelet sees local resources falling below configured thresholds. At that point kubelet may evict pods, and QoS class plus actual usage relative to requests becomes important. Scheduling protected the initial placement; eviction protects the node when runtime conditions have changed.

The difference matters because the fix happens at a different layer. If a pod cannot be scheduled, you either lower its request, add capacity, change placement constraints, or free requested capacity by moving other workloads. If a node is under pressure, you inspect which running pods are consuming unreserved resources, whether requests reflect reality, and whether eviction thresholds are being crossed. Treating both symptoms as "the cluster is out of memory" hides the useful evidence that Kubernetes already gives you.

```bash
# Check node resource pressure
kubectl describe node <node-name> | grep -A10 "Conditions"
# MemoryPressure    False    KubeletHasSufficientMemory
# DiskPressure      False    KubeletHasNoDiskPressure
# PIDPressure       False    KubeletHasSufficientPID
```

Before running this in a real cluster, what output do you expect from a Pending pod that requested too much memory: a container status reason, a scheduler event, or an application log line? The correct answer shapes your command order. If the pod never reached a node, container logs are not the first place to look; the scheduler event is the evidence that tells you the pod was never admitted to runtime.

## Runtime Enforcement: CPU Throttling and OOMKilled

Once a pod is running, limits are enforced by the container runtime and the Linux kernel mechanisms underneath it. CPU and memory are both written under `resources.limits`, but they do not behave symmetrically. CPU is compressible because the runtime can delay execution and hand out fewer CPU time slices. Memory is not safely compressible from Kubernetes' point of view, so exceeding a memory limit can kill the container even when the process has no chance to log a graceful error.

```bash
# Container trying to use 2 CPUs with 500m limit
# Gets throttled to 500m worth of CPU time
```

CPU throttling is subtle because averages can hide it. `kubectl top pod` might show modest average CPU usage while an application still experiences latency spikes, especially if the process is bursty and gets throttled during short request-handling windows. This is why some production teams set CPU requests carefully but avoid CPU limits for latency-sensitive services, while others keep limits for stronger multi-tenant isolation. The right answer depends on workload behavior and cluster policy, not on a universal ratio.

The exam does not require you to tune kernel counters, but it does expect you to know the symptom pattern. A throttled service may look healthy from a restart-count perspective because the container stays alive. Readiness probes might pass between bursts, yet users see slow responses during peak traffic. If the resource contract has a low CPU limit, raising only the request will not remove the runtime cap, while raising only the limit will not change scheduling reservations. The useful fix depends on whether placement honesty or runtime headroom is the real problem.

Memory limits produce a more visible symptom. When a process inside the container uses more memory than its cgroup limit allows, the kernel can kill it, and Kubernetes reports the previous container state as terminated with reason `OOMKilled`. Exit code 137 is common because it represents a SIGKILL. The application may have no stack trace because the kill happened outside the application's normal error path.

```bash
# Check for OOMKilled
kubectl describe pod <pod-name> | grep -A5 "Last State"
# Last State:  Terminated
#   Reason:    OOMKilled
#   Exit Code: 137

# Check events
kubectl get events --field-selector reason=OOMKilling
```

The following pod intentionally asks a stress process to allocate more memory than its limit. It is useful in a disposable lab namespace because it proves the failure mode without requiring a broken application. Do not use this kind of workload in a shared production namespace; it is a teaching probe that is supposed to cross the boundary and get killed.

Memory troubleshooting is also where requests and limits are most often confused. A memory request does not protect a container from being killed when it crosses its own memory limit. A memory limit does not guarantee that the pod will be scheduled onto a node with enough reserved capacity for normal operation. You need both sides of the contract: the request should represent what the workload needs to run reliably, and the limit should represent the maximum you are willing to allow before containment is safer than continued growth.

```yaml
# Pod that will be OOMKilled
apiVersion: v1
kind: Pod
metadata:
  name: memory-hog
spec:
  containers:
  - name: memory-hog
    image: polinux/stress
    command: ["stress"]
    args: ["--vm", "1", "--vm-bytes", "200M", "--vm-hang", "1"]
    resources:
      limits:
        memory: "100Mi"     # Limit is less than 200M stress allocates
```

Hypothetical scenario: a web container restarts every few minutes, the application logs end abruptly, and the deployment controller keeps creating replacement containers. If `kubectl describe pod` shows `Last State: Terminated` with `Reason: OOMKilled`, the first fix is not to restart the deployment again. You need to decide whether the limit is too low for legitimate traffic, the request is too low and causing poor eviction priority, or the application has a leak that will eventually exceed any reasonable limit.

## Quality of Service Classes and Eviction Behavior

Kubernetes assigns every pod a QoS class from its resource configuration. The class does not replace priority classes, preemption, or eviction thresholds, but it is an important signal during resource pressure. Guaranteed pods made the strongest promise because every container has CPU and memory requests equal to limits. BestEffort pods made no resource promise at all. Burstable pods sit between those cases because they have at least one request or limit, but they do not meet the strict Guaranteed rule.

| QoS Class | Condition | Eviction Priority |
|-----------|-----------|-------------------|
| **Guaranteed** | requests = limits for all containers | Last, lowest priority for eviction |
| **Burstable** | At least one request or limit set | Middle |
| **BestEffort** | No requests or limits | First, highest priority for eviction |

Guaranteed is more restrictive than many learners expect. Every container in the pod must have both CPU and memory requests and limits, and the request must equal the limit for each resource. If one side is missing or one value differs, the pod is not Guaranteed. This strictness matters because a sidecar without matching resources can change the QoS class of the whole pod.

Guaranteed should therefore be a deliberate choice rather than a formatting habit. It gives the pod the strongest resource promise, but it can reduce cluster utilization because every replica reserves its full limit. That tradeoff may be appropriate for a component that must survive pressure, but it is wasteful for a workload that normally uses a small baseline and only occasionally bursts. The design question is whether the cost of eviction or throttled burst behavior is higher than the cost of reserving more capacity.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: guaranteed-pod
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "128Mi"    # Same as request
        cpu: "100m"        # Same as request
```

```bash
# Check QoS class
kubectl get pod guaranteed-pod -o jsonpath='{.status.qosClass}'
# Guaranteed
```

Burstable is the normal class for many services because teams often want a realistic request and some headroom above it. That tradeoff improves utilization, but it also means the pod is borrowing capacity when it runs above its request. During node memory pressure, a Burstable pod that is far above its request is a stronger eviction candidate than a Burstable pod that is still below its request, because the first pod is consuming more than it reserved.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: burstable-pod
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "128Mi"
      limits:
        memory: "256Mi"    # Different from request
```

BestEffort pods are easy to create accidentally because a pod with no resources section gets that class. They are useful for quick experiments in a disposable namespace, but they are poor citizens in shared production clusters. The scheduler can place them without reserving CPU or memory, and during pressure they are among the first pods kubelet considers for eviction.

Burstable is where most nuanced decisions live. A Burstable pod can be well designed when the request is honest and the limit gives safe headroom. It can also be badly designed when the request is tiny, the limit is huge, and the workload normally consumes far more than it reserved. The label alone is not enough to judge quality. Compare actual usage with the request, then decide whether the pod is borrowing a little capacity responsibly or depending on unreserved capacity as its normal operating model.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: besteffort-pod
spec:
  containers:
  - name: app
    image: nginx
    # No resources section
```

```text
Eviction Order (first to last):
1. BestEffort pods (no requests set - evicted first)
2. Burstable pods using more than their requests
3. Burstable pods using less than their requests
4. Guaranteed pods (last resort)
```

**Pause and predict:** Consider a pod configured with requests of `100m` CPU and `128Mi` memory, alongside a memory limit of `256Mi` and no CPU limit. Which Quality of Service tier does Kubernetes assign to this pod, and what happens if the container attempts to allocate `300Mi` of memory during operation?

<details>
<summary>Check your prediction</summary>

The pod is Burstable because CPU has no limit and the memory request does not equal the memory limit, failing the strict requirements for Guaranteed status. If the process attempts to consume `300Mi` of memory, the `256Mi` memory limit can still kill it because the Linux kernel cgroup controller enforces hard memory limits regardless of whether the pod belongs to the Guaranteed class.

</details>

The next section is managing cluster consumption through administrative admission controls, establishing structural guardrails across shared organizational platform namespaces.

## Namespace Governance with LimitRanges and ResourceQuotas

Individual pod settings are necessary, but they are not enough in a cluster where several teams create workloads independently. Namespace policy gives platform operators a place to set defaults and ceilings without editing every application manifest. LimitRange applies constraints to individual objects at admission time, while ResourceQuota caps aggregate consumption across the namespace. Used together, they prevent both accidental BestEffort pods and namespace-level resource hoarding.

A LimitRange can set default requests and limits when a container omits them. It can also define minimum and maximum values so a pod cannot request absurdly tiny or huge amounts. This is especially useful when a ResourceQuota requires requests or limits, because the LimitRange can supply those missing fields automatically before quota accounting is checked. The object is namespace-scoped, so each team can have a policy that matches its workload profile.

Defaults should be conservative enough to protect the namespace without pretending to know every workload. A default request that is too high wastes quota and makes small pods appear expensive. A default request that is too low recreates the overcommit problem under a more official-looking policy. Many teams start with small defaults for ordinary web services, require explicit resources for heavier workloads, and review exceptions through normal platform processes. The key is that the namespace now has a predictable baseline instead of relying on every manifest author to remember the same fields.

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: cpu-memory-limits
  namespace: development
spec:
  limits:
  - type: Container
    default:           # Default limits if not specified
      cpu: "500m"
      memory: "256Mi"
    defaultRequest:    # Default requests if not specified
      cpu: "100m"
      memory: "128Mi"
    min:               # Minimum allowed
      cpu: "50m"
      memory: "64Mi"
    max:               # Maximum allowed
      cpu: "1"
      memory: "1Gi"
```

```bash
# Apply LimitRange to namespace
kubectl apply -f limitrange.yaml

# Now create pod without resources
kubectl run test --image=nginx -n development

# Check - default resources were applied!
kubectl get pod test -n development -o yaml | grep -A10 resources
```

LimitRange can apply to more than individual containers. A container policy is the most common for CPU and memory defaults, but pod-level constraints can cap the sum across containers, and PVC constraints can govern storage requests. The important exam detail is that a LimitRange is admission-time policy. It changes or rejects new objects; it does not continuously resize already-running pods after they have been admitted.

| Type | Applies To |
|------|------------|
| `Container` | Individual containers |
| `Pod` | Sum of all containers in pod |
| `PersistentVolumeClaim` | PVC storage requests |

ResourceQuota is the aggregate side of the same governance story. Instead of saying one container may not exceed a maximum, a quota says the namespace as a whole may not exceed a total. It can cap requested CPU, requested memory, limits, pod count, PVC count, and other object counts. This gives each team a budget and keeps a noisy namespace from consuming the entire cluster by accident.

Quota design should mirror how you want teams to make tradeoffs. A `requests.cpu` quota controls reserved CPU and therefore scheduling footprint. A `limits.memory` quota controls the maximum memory blast radius if every container grows to its limit. A pod-count quota prevents a namespace from creating thousands of tiny objects even when each object has small resources. These dimensions answer different questions, so a useful namespace policy often combines compute quotas with object-count quotas instead of relying on only one hard value.

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: development
spec:
  hard:
    requests.cpu: "4"           # Total CPU requests
    requests.memory: "8Gi"      # Total memory requests
    limits.cpu: "8"             # Total CPU limits
    limits.memory: "16Gi"       # Total memory limits
    pods: "10"                  # Total number of pods
    persistentvolumeclaims: "5" # Total PVCs
```

```bash
# View quota
kubectl get resourcequota -n development

# Detailed view
kubectl describe resourcequota compute-quota -n development
# Name:            compute-quota
# Resource         Used    Hard
# --------         ----    ----
# limits.cpu       2       8
# limits.memory    4Gi     16Gi
# pods             5       10
```

Quota failures are admission failures, not runtime failures. If a namespace has already used all allowed pod slots, the next pod creation is rejected before the container ever starts. This behavior is helpful because it gives a clear error at the point of change, but it also means developers need enough feedback to understand whether they exceeded object count, requested CPU, requested memory, or another quota dimension.

```bash
# If quota exceeded
kubectl run new-pod --image=nginx -n development
# Error: exceeded quota: compute-quota, requested: pods=1, used: pods=10, limited: pods=10
```

Stop and think: you create a ResourceQuota in a namespace with `pods: 10` and `requests.cpu: 4`. A developer tries to create a pod without specifying any CPU request. The pod may be rejected because compute quotas require the relevant resource requests or limits to be present, unless a LimitRange supplies defaults during admission. The better design is to pair the quota with a LimitRange so ordinary workloads get sane defaults and unusual workloads must declare their needs explicitly.

## Right-Sizing, Monitoring, and Kubernetes 1.35 Resize

Choosing resource values is a measurement problem before it is a YAML problem. If you set requests below normal usage, the scheduler overcommits the node and the pod may be a poor eviction candidate during pressure. If you set requests far above normal usage, the scheduler packs fewer pods per node and the cluster looks full while real usage is low. The practical goal is to reserve enough for steady operation, allow appropriate bursts, and keep limits from hiding design problems.

A good first pass is to observe the workload under a representative test, then separate baseline from burst. Baseline is the level you would be uncomfortable losing during normal operation, so it belongs near the request. Burst is temporary headroom that may be useful but should not define scheduling capacity unless it is constant. Memory deserves extra caution because it is often sticky: a process that allocates memory may not return it quickly, and a too-low limit can create restart loops that look like application instability.

```bash
# 1. Profile your application
# Run locally or in test environment to measure actual usage

# 2. Set requests slightly above average usage
# Ensures pod gets scheduled

# 3. Set limits to handle bursts
# Allow headroom for spikes but protect the node
```

The ratios below are not universal rules; they are starting points for conversation. A web server with short spikes might use a small CPU request and a higher CPU limit. A database usually needs more conservative memory because eviction or OOMKilled behavior is expensive and stateful recovery can be slow. A cache may care more about memory sizing than CPU burst. Always combine these patterns with measurements from a test or staging environment.

| Application Type | Request | Limit | Ratio |
|-----------------|---------|-------|-------|
| Web server | 100m CPU, 128Mi | 500m CPU, 512Mi | 1:5, 1:4 |
| Background worker | 200m CPU, 256Mi | 1 CPU, 1Gi | 1:5, 1:4 |
| Database | 500m CPU, 1Gi | 2 CPU, 4Gi | 1:4, 1:4 |
| Cache | 100m CPU, 512Mi | 200m CPU, 1Gi | 1:2, 1:2 |

You can set resources directly in a manifest or use `kubectl set resources` against an existing workload. For long-lived systems, prefer declarative manifests in version control because the resource contract is part of the workload design. For an exam or a quick repair, `kubectl set resources` is useful because it patches a controller and lets the controller recreate pods with the new template.

```bash
# Create with resources using a manifest
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: nginx
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
      limits:
        cpu: "500m"
        memory: "256Mi"
EOF
```

```bash
# Update existing deployment
kubectl set resources deployment/nginx \
  -c nginx \
  --requests="cpu=100m,memory=128Mi" \
  --limits="cpu=500m,memory=256Mi"

# Check resource usage (requires metrics-server)
kubectl top pods
kubectl top nodes
```

Monitoring commands help you compare declared intent with observed behavior. `kubectl describe node` shows capacity, allocatable resources, and allocated requests and limits. `kubectl top` shows current usage when metrics-server is installed and healthy. Neither command is enough alone. The declared values tell you what the scheduler and quota system believe, while usage metrics tell you whether the workload is actually using the resource contract you gave it.

When numbers disagree, trust each tool for the thing it is designed to report. `kubectl top` can tell you that a pod currently uses much less memory than its request, which may indicate over-reservation. `kubectl describe node` can tell you that requested memory is already high enough to block new placements, even if live usage is lower right now. ResourceQuota output can tell you the namespace budget is exhausted before any node-level issue appears. Good diagnosis is the habit of lining up these views instead of treating one command as authoritative.

```bash
# Check node resource usage
kubectl top nodes
# NAME    CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# node1   250m         12%    1200Mi          60%

# Check pod resource usage
kubectl top pods
kubectl top pods -n kube-system
kubectl top pod nginx --containers
```

```bash
# Node capacity and allocatable
kubectl describe node <node-name> | grep -A10 "Capacity"
kubectl describe node <node-name> | grep -A10 "Allocatable"

# Node resource usage summary
kubectl describe node <node-name> | grep -A10 "Allocated resources"
```

Kubernetes 1.35 makes in-place pod resource resize generally available for CPU and memory through the `/resize` subresource. This does not mean every resize is invisible to the application. The pod spec, container `resizePolicy`, the resource being changed, and runtime support decide whether a container can be updated in place or must be restarted. Use it as a tool for right-sizing and operational repair, but keep controller-managed workloads and GitOps ownership in mind.

In-place resize is especially useful for closing the gap between observation and correction. Before this capability, vertical changes commonly meant replacing pods, which mixed the resource fix with rollout behavior. With resize, an operator can sometimes adjust a running pod, observe whether pressure clears, and then promote the new values into the owning workload template. That workflow is still disciplined: the direct change is evidence and mitigation, while the template or manifest update is the durable configuration.

```bash
# Check current resources
kubectl get pod nginx -o jsonpath='{.spec.containers[0].resources}'

# Resize CPU and memory without replacing the Pod object
kubectl patch pod nginx --subresource resize --patch '
{
  "spec": {
    "containers": [{
      "name": "nginx",
      "resources": {
        "requests": {"cpu": "200m", "memory": "256Mi"},
        "limits": {"cpu": "500m", "memory": "512Mi"}
      }
    }]
  }
}'

# Verify whether the resize is pending or in progress
kubectl get pod nginx -o jsonpath='{.status.conditions[?(@.type=="PodResizePending")].status}'
kubectl get pod nginx -o jsonpath='{.status.conditions[?(@.type=="PodResizeInProgress")].status}'
# Empty output means the condition is not currently set.
# If either condition is True, the resize is still pending or in progress.
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: resize-demo
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 200m
        memory: 256Mi
    resizePolicy:
    - resourceName: cpu
      restartPolicy: NotRequired    # CPU changes apply live
    - resourceName: memory
      restartPolicy: RestartContainer # Memory changes restart container
```

Which approach would you choose here and why: patch one running pod with the `/resize` subresource, patch the owning Deployment with `kubectl set resources`, or update the manifest in version control and let your delivery system roll it out? For an unmanaged debug pod, direct resize can be appropriate. For a Deployment, the durable fix usually belongs on the pod template, because the next rollout or replacement pod will otherwise drift back to the old contract.

## Patterns & Anti-Patterns

Use the request-first pattern for most stateless services. Start by measuring steady-state CPU and memory, set requests close to normal usage plus modest headroom, and then decide whether limits are needed for isolation. This works because the scheduler only has requests to reason about. If those values are realistic, the cluster can pack workloads efficiently without pretending every burst is permanent.

The request-first pattern also makes incident communication clearer. When a service cannot schedule, you can point to a declared reservation and compare it with available allocatable resources. When a namespace hits quota, you can show which workloads are consuming the budget through their requests. Without requests, every conversation becomes a live-usage argument, and live usage changes from minute to minute. Stable resource contracts give teams a shared language for capacity, ownership, and fairness.

Use namespace guardrails for shared clusters. A LimitRange should provide defaults and reasonable min or max values, while a ResourceQuota should cap the namespace budget. This pattern scales better than relying on every developer to remember resource fields by hand, and it produces clearer admission errors when a namespace exceeds its budget. The scaling consideration is policy ownership: platform teams should publish defaults and teach application teams how to request exceptions.

Use QoS intentionally for critical workloads. Some components deserve Guaranteed QoS because eviction would be more expensive than lower utilization. Other workloads are better as Burstable because a little extra headroom improves cost efficiency. The pattern is to choose the class as a reliability decision, not as an accidental result of whatever fields happened to be omitted from the manifest.

Avoid limits-only configuration. It looks protective because the container has a maximum, but it gives the scheduler too little information unless admission defaults add a request. A workload can then land on a node without reserving the capacity it normally needs, and under pressure it may be treated worse than the team expects. The better alternative is to set explicit requests and then choose limits only where the failure behavior is acceptable.

Avoid copying ratios across workload types without measurement. A CPU-heavy batch worker, a latency-sensitive API, a JVM service, and an in-memory cache do not have the same burst pattern or memory risk. Teams fall into this because a single example manifest is easy to standardize. The better alternative is to publish starting profiles, then require teams to confirm them with metrics from their workload.

Avoid treating `kubectl top` as a capacity planner by itself. It shows recent usage, not scheduler reservations, quota usage, or throttling counters. A pod with low average CPU can still be throttled during short bursts, and a node with low current memory can still be unable to schedule a pod because requests already fill allocatable capacity. The better alternative is to compare `kubectl top`, `kubectl describe node`, pod events, and quota output before deciding what to change.

Another anti-pattern is using resource policy as punishment instead of as a contract. If platform teams set tiny defaults to force developers to ask for more, workloads fail in confusing ways and developers learn to bypass the policy. If application teams set inflated requests to avoid future conversations, the cluster becomes artificially full. Better resource management is a negotiation with evidence: defaults handle the ordinary case, metrics justify exceptions, and quotas make the shared boundary explicit.

## Decision Framework

Start with the symptom, then choose the resource-management lever that matches the failure point. If the pod is Pending and never starts, inspect scheduling events and node allocatable resources first. If the pod starts and restarts with exit code 137, inspect memory limits, observed memory usage, and whether the application has a leak. If the pod runs but latency spikes under load, inspect CPU limits and throttling risk before assuming the application is unhealthy.

For namespace design, decide whether the problem is missing defaults, excessive individual pod size, or excessive aggregate consumption. Missing defaults point to a LimitRange with `defaultRequest` and `default`. Oversized individual pods point to LimitRange `max` values or review policy. Aggregate overuse points to ResourceQuota. When both defaults and aggregate caps are required, create the LimitRange first so ordinary pods receive resource fields before quota admission evaluates them.

For troubleshooting, read failures in the order Kubernetes encounters them. Admission errors happen before scheduling, so ResourceQuota and LimitRange messages appear when the API server rejects the object. Scheduling errors happen after admission, so they show up as pod events while the pod remains Pending. Runtime enforcement happens after the pod is bound and containers start, so OOMKilled, restarts, and throttling symptoms appear in status, events, and metrics. This timeline keeps you from debugging the wrong layer.

For right-sizing, separate emergency repair from durable configuration. In Kubernetes 1.35+, the `/resize` subresource can be useful when one running pod needs immediate CPU or memory adjustment and the policy allows it. A Deployment-level change is better when every replica should share the new contract. A version-controlled manifest update is the durable answer when the change must survive rollouts, reviews, and future reconciliations.

For reliability, compare the cost of eviction against the cost of lower utilization. Guaranteed QoS may be appropriate for critical control-plane-adjacent services or stateful workloads where eviction has high impact. Burstable is often appropriate for stateless services that benefit from efficient packing and can tolerate occasional pressure behavior. BestEffort should usually be limited to experiments, throwaway jobs, or namespaces where eviction is acceptable.

For exam execution, convert that framework into a quick command sequence. If creation fails, read the error and check namespace policy. If the pod exists but is Pending, describe the pod and inspect scheduling events. If the pod runs and restarts, describe it and inspect last state, exit code, and limits. If the pod runs but is slow, compare CPU limits, requests, and observed usage. This sequence is faster than guessing because each step follows the Kubernetes lifecycle.

## Did You Know?

- **In-Place Pod Resize is now GA**: In Kubernetes 1.35, CPU and memory requests and limits can be updated for running Pods through the `/resize` subresource, and `resizePolicy` influences whether a container restart is required.
- **CPU and memory limits fail differently**: CPU overuse is throttled, while memory overuse can terminate the container with `OOMKilled` and commonly appears with exit code 137.
- **Guaranteed QoS is all-or-nothing**: Every container in the pod needs matching CPU and memory requests and limits; one incomplete sidecar can make the whole pod Burstable.
- **Metrics-server feeds `kubectl top`**: The common cluster metrics pipeline collects recent resource usage for commands such as `kubectl top`, but scheduling still uses declared requests rather than live usage.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| No requests set | The manifest works in a quiet test namespace, so the team forgets the scheduler has no reservation to use | Set realistic CPU and memory requests, or use a LimitRange to apply defaults |
| Limits too low | A copied example value becomes a production boundary without workload profiling | Measure real usage, raise the memory limit when legitimate, and fix leaks when usage grows without bound |
| Requests equal limits everywhere | Teams chase Guaranteed QoS without considering burst tolerance or utilization | Reserve Guaranteed QoS for workloads that need it, and use Burstable contracts for services that can safely burst |
| Using `M` instead of `Mi` | Decimal and binary suffixes look similar in a fast review | Standardize on `Mi` and `Gi` for memory manifests unless decimal units are intentional |
| Quota without LimitRange defaults | ResourceQuota requires fields that ordinary pod manifests omit | Create LimitRange defaults before or with compute quotas so admission can populate missing requests |
| Looking only at `kubectl top` | Recent usage is easier to read than scheduler reservations and events | Compare usage with `describe node`, pod events, ResourceQuota output, and resource specs |
| Patching one pod owned by a Deployment | Direct pod edits feel fast during an incident, but the controller template still has old resources | Patch the controller or version-controlled manifest for durable changes, and use pod resize only when direct repair is intended |

## Quiz

<details>
<summary>Question 1: A pod is Pending after a deploy. The image exists, the namespace is correct, and `kubectl describe pod` shows FailedScheduling with insufficient memory. What should you check and change first?</summary>

Check the pod's memory request and compare it with node allocatable resources and already requested memory. The scheduler uses requests, not current live usage, so the pod can remain Pending even when a node looks quiet in `kubectl top`. If the request is accidentally too large, reduce it to a measured value; if the request is legitimate, add capacity or move lower-priority workloads. Changing the memory limit alone will not solve placement if the request still cannot fit.

</details>

<details>
<summary>Question 2: A container restarts with exit code 137, no application error, and `Last State: Terminated, Reason: OOMKilled`. How do you diagnose whether to raise the limit or fix the application?</summary>

Start by confirming the memory limit and checking observed memory growth with available metrics. If usage rises steadily without returning to a stable level, suspect a leak and treat a higher limit as temporary containment rather than the final fix. If usage spikes only during valid traffic and then stabilizes, the limit may be too low for normal operation. Also check the request, because a low request can make the pod more vulnerable during node pressure even if the limit prevents node-wide damage.

</details>

<details>
<summary>Question 3: Your API has a CPU request of `100m`, a CPU limit of `200m`, and latency spikes under peak traffic even though average CPU in `kubectl top` looks low. What resource issue could explain the symptom?</summary>

The pod may be CPU throttled during short bursts even though the average over the metrics window is low. CPU limits are enforced over small scheduling periods, so a request-handling burst can hit the `200m` cap and slow down while the longer average still appears modest. You can test this by raising or removing the CPU limit in a controlled environment and comparing latency. The request should still be sized realistically so scheduling remains honest.

</details>

<details>
<summary>Question 4: A namespace has a ResourceQuota for `requests.cpu` and `pods`, but developers frequently create pods without resource fields and get admission errors. What object should you add and why?</summary>

Add a LimitRange that supplies `defaultRequest` values for CPU and memory, and usually default limits as well. Compute quotas need the relevant request or limit fields so Kubernetes can account for namespace usage at admission time. The LimitRange fills in missing values before quota evaluation, which lets ordinary pods be admitted while still counting against the namespace budget. You should also set reasonable min and max values if individual pod size needs guardrails.

</details>

<details>
<summary>Question 5: During node memory pressure, you see a Guaranteed pod, a Burstable pod using much more than its request, and a BestEffort pod. Which pod is most likely to be evicted first, and what resource design lesson follows?</summary>

The BestEffort pod is the first likely eviction candidate because it made no CPU or memory reservation. If pressure continues, Burstable pods that are using more than their requests become stronger candidates before Guaranteed pods. The design lesson is that requests are not paperwork; they influence both scheduling and how kubelet judges fairness under pressure. Critical workloads should not accidentally run as BestEffort because a resources section was omitted.

</details>

<details>
<summary>Question 6: You resize a running pod in Kubernetes 1.35 with the `/resize` subresource, and the change works. Why might that still be the wrong long-term fix for a Deployment?</summary>

A direct pod resize changes the running Pod object, but a Deployment creates pods from its template. If the template still contains the old resources, future replacement pods can return to the old request and limit values. For durable controller-managed workloads, patch the Deployment or update the version-controlled manifest that owns it. In-place resize is useful for immediate repair and right-sizing, but ownership and reconciliation still matter.

</details>

## Hands-On Exercise

This exercise uses ordinary pods and namespace policy to connect scheduling, QoS, and admission behavior. Run it in a disposable cluster or lab environment. The goal is not to memorize every command, but to predict the result before each check and then compare that prediction with Kubernetes status, events, and object YAML.

### Task 1: Create a Burstable pod with explicit requests and limits

Create a pod where requests and limits differ, then verify the QoS class. Notice that the pod is not Guaranteed even though it has both CPU and memory values, because the request and limit values are not equal.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: resource-test
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
      limits:
        cpu: "200m"
        memory: "256Mi"
EOF

kubectl get pod resource-test -o jsonpath='{.status.qosClass}'
# Burstable (because requests are not equal to limits)
```

### Task 2: Create a Guaranteed pod

Now create a pod where CPU and memory requests equal limits. This is the strict pattern Kubernetes requires for Guaranteed QoS.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: guaranteed
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "128Mi"
        cpu: "100m"
EOF

kubectl get pod guaranteed -o jsonpath='{.status.qosClass}'
# Guaranteed
```

### Task 3: Create a BestEffort pod

Create a pod with no resource settings and confirm that Kubernetes classifies it as BestEffort. In a shared cluster, this is usually a signal that namespace defaults are missing.

```bash
kubectl run besteffort --image=nginx
kubectl get pod besteffort -o jsonpath='{.status.qosClass}'
# BestEffort
```

### Task 4: Apply a LimitRange and observe defaults

Create a namespace, add a LimitRange, and then create a pod without explicit resources. The pod manifest you submitted did not include resources, but the admitted pod should show the defaults supplied by the namespace policy.

```bash
kubectl create namespace limits-test

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: limits-test
spec:
  limits:
  - type: Container
    default:
      cpu: "200m"
      memory: "128Mi"
    defaultRequest:
      cpu: "100m"
      memory: "64Mi"
EOF

# Create pod without resources
kubectl run test-defaults --image=nginx -n limits-test

# Check - defaults applied!
kubectl get pod test-defaults -n limits-test -o yaml | grep -A8 resources
```

### Task 5: Test ResourceQuota admission

Add a pod-count quota and create pods until the namespace budget is exhausted. `test-defaults` from Task 4 already consumes one of the two allowed pod slots, so `pod1` brings the namespace to `2/2` and the second new pod is rejected.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: pod-quota
  namespace: limits-test
spec:
  hard:
    pods: "2"
EOF

# Create pods until quota exceeded
kubectl run pod1 --image=nginx -n limits-test
kubectl run pod2 --image=nginx -n limits-test  # Should fail: test-defaults + pod1 already reach 2/2

kubectl describe resourcequota pod-quota -n limits-test
```

### Task 6: Clean up

Remove the standalone pods and test namespace so the lab leaves the cluster clean for the next module.

```bash
kubectl delete pod resource-test guaranteed besteffort
kubectl delete namespace limits-test
```

**Card A: The scheduler places a pod by watching live CPU and memory usage, so a quiet node in `kubectl top` can always take another pod.** An administrator observes low instantaneous utilization on a worker node and expects the scheduler to bind incoming workloads there regardless of existing pod resource reservations.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing instantaneous node utilization with declarative resource allocation accounting. Next action: understand that scheduling uses requests against allocatable, not live usage; run `kubectl describe node` to inspect committed resource requests, because a node with low live usage in `kubectl top` will still reject additional pods once total requested reservations reach allocatable capacity.

</details>

**Card B: A memory request prevents OOMKilled. Only a missing memory limit can kill the container.** A developer configures memory requests for an application and assumes the container cannot be terminated as long as the cluster has free memory available on the host.

<details>
<summary>Check your prediction</summary>

Failure layer: mistaking scheduling reservations for runtime container memory boundary protection. Next action: understand that a memory request does not stop a memory limit from killing the container; the Linux cgroup controller terminates the process immediately with an OOMKilled status whenever consumption breaches the configured memory limit regardless of request sizing.

</details>

**Card C: With no CPU limit, the container is killed when it uses more CPU than its request.** A platform engineer worries that an unconstrained process consuming surplus processor cycles beyond its configured CPU request during traffic spikes will be terminated by the runtime.

<details>
<summary>Check your prediction</summary>

Failure layer: conflating compressible compute scheduling mechanisms with terminal memory enforcement actions. Next action: understand that CPU without a limit is throttled only if a limit exists, and no limit means it can burst into unused node compute capacity without termination; exceeding a CPU request never triggers container termination.

</details>

**Card D: A pod with a memory limit and no CPU limit is Guaranteed because a limit is set.** An operator defines a memory limit on a container and assumes Kubernetes grants top eviction protection because an explicit upper constraint exists.

<details>
<summary>Check your prediction</summary>

Failure layer: misjudging Quality of Service classification rules and resource boundary completeness. Next action: understand that Guaranteed requires CPU and memory requests equal to limits on every container in the pod; omitting a CPU limit or leaving requests unequal to limits classifies the pod as Burstable, leaving it vulnerable to eviction during node memory pressure.

</details>

**Success Criteria**:

- [ ] Configure CPU and memory requests and limits on a pod, then verify the admitted resource spec.
- [ ] Diagnose why a pod is Burstable, Guaranteed, or BestEffort from its resource fields.
- [ ] Implement a LimitRange that supplies namespace defaults for pods without explicit resources.
- [ ] Implement a ResourceQuota and verify admission failure when the namespace exceeds its budget.
- [ ] Design a resource troubleshooting flow that checks events, QoS, quota, usage metrics, and controller ownership.

### Additional Practice Drills

The drills below preserve the command patterns from the original practice set. Treat them as timed repetitions after you understand the concepts, not as a substitute for the explanations above.

```bash
# Drill 1: Resource Creation
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: web
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
      limits:
        cpu: "500m"
        memory: "512Mi"
EOF

kubectl get pod web -o jsonpath='{.spec.containers[0].resources}'
kubectl get pod web -o jsonpath='{.status.qosClass}'
kubectl delete pod web
```

```bash
# Drill 2: QoS Class Identification
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: qos-guaranteed
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        cpu: "100m"
        memory: "100Mi"
      limits:
        cpu: "100m"
        memory: "100Mi"
EOF

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: qos-burstable
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        cpu: "100m"
EOF

kubectl run qos-besteffort --image=nginx

for pod in qos-guaranteed qos-burstable qos-besteffort; do
  echo "$pod: $(kubectl get pod $pod -o jsonpath='{.status.qosClass}')"
done

kubectl delete pod qos-guaranteed qos-burstable qos-besteffort
```

```bash
# Drill 3: LimitRange
kubectl create namespace lr-test

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: LimitRange
metadata:
  name: mem-limit
  namespace: lr-test
spec:
  limits:
  - type: Container
    default:
      memory: "256Mi"
    defaultRequest:
      memory: "128Mi"
    min:
      memory: "64Mi"
    max:
      memory: "1Gi"
EOF

kubectl run default-test --image=nginx -n lr-test
kubectl get pod default-test -n lr-test -o jsonpath='{.spec.containers[0].resources}'

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: too-big
  namespace: lr-test
spec:
  containers:
  - name: app
    image: nginx
    resources:
      limits:
        memory: "2Gi"
EOF

kubectl delete namespace lr-test
```

```bash
# Drill 4: ResourceQuota
kubectl create namespace quota-test

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: quota-test
spec:
  hard:
    requests.cpu: "1"
    requests.memory: "1Gi"
    limits.cpu: "2"
    limits.memory: "2Gi"
    pods: "3"
EOF

kubectl describe resourcequota compute-quota -n quota-test

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod1
  namespace: quota-test
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "200m"
        memory: "256Mi"
      limits:
        cpu: "400m"
        memory: "512Mi"
---
apiVersion: v1
kind: Pod
metadata:
  name: pod2
  namespace: quota-test
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "200m"
        memory: "256Mi"
      limits:
        cpu: "400m"
        memory: "512Mi"
---
apiVersion: v1
kind: Pod
metadata:
  name: pod3
  namespace: quota-test
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "200m"
        memory: "256Mi"
      limits:
        cpu: "400m"
        memory: "512Mi"
EOF

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod4
  namespace: quota-test
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "200m"
        memory: "256Mi"
      limits:
        cpu: "400m"
        memory: "512Mi"
EOF

kubectl describe resourcequota compute-quota -n quota-test
kubectl delete namespace quota-test
```

```bash
# Drill 5: Resource Troubleshooting
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pending-pod
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "100"
        memory: "100Gi"
EOF

kubectl get pod pending-pod
kubectl describe pod pending-pod | grep -A5 "Events"

kubectl delete pod pending-pod
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pending-pod
spec:
  containers:
  - name: nginx
    image: nginx
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
EOF

kubectl get pod pending-pod
kubectl delete pod pending-pod
```

```bash
# Drill 6: Update Resources
kubectl create deployment resource-update --image=nginx --replicas=2

kubectl set resources deployment/resource-update \
  --requests="cpu=100m,memory=128Mi" \
  --limits="cpu=200m,memory=256Mi"

kubectl get pods -l app=resource-update -w &
sleep 10
kill %1 2>/dev/null

kubectl describe deployment resource-update | grep -A10 "Resources"
kubectl delete deployment resource-update
```

<details>
<summary>Drill 7 solution: complete namespace resource setup</summary>

```bash
kubectl create namespace challenge

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: LimitRange
metadata:
  name: limits
  namespace: challenge
spec:
  limits:
  - type: Container
    default:
      cpu: "200m"
      memory: "256Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
    max:
      cpu: "1"
      memory: "1Gi"
EOF

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: quota
  namespace: challenge
spec:
  hard:
    pods: "4"
    requests.cpu: "2"
    requests.memory: "4Gi"
EOF

kubectl create deployment app --image=nginx --replicas=2 -n challenge
kubectl get all -n challenge
kubectl describe resourcequota quota -n challenge
kubectl delete namespace challenge
```

</details>

## Sources

- [Resource Management for Pods and Containers](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Pod Quality of Service Classes](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-qos/)
- [Limit Ranges](https://v1-35.docs.kubernetes.io/docs/concepts/policy/limit-range/)
- [Resource Quotas](https://v1-35.docs.kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes Metrics Server](https://github.com/kubernetes-sigs/metrics-server)
- [Resize CPU and Memory Resources assigned to Containers](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/)
- [Vertical Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/)
- [Node-pressure Eviction](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
- [kubectl set resources reference](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl_set/kubectl_set_resources/)
- [kubectl top reference](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl_top/)

## Next Module

[Module 2.6: Scheduling](../module-2.6-scheduling/) - Node selection, affinity, taints, and tolerations.
