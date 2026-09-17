---
title: "Module 3.4: Monitoring Applications"
slug: k8s/ckad/part3-observability/module-3.4-monitoring
revision_pending: false
sidebar:
  order: 4
lab:
  id: ckad-3.4-monitoring
  url: https://killercoda.com/kubedojo/scenario/ckad-3.4-monitoring
  duration: "30 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Long-form resource-monitoring module with conceptual foundations
>
> **Time to Complete**: 25-30 minutes
>
> **Prerequisites**: Module 3.1 (Probes), understanding of resource requests/limits

---

## Learning Outcomes

After completing this module, you will be able to:
- **Diagnose** pod and node resource pressure using `kubectl top pods`, `kubectl top nodes`, sorted output, and container-level metrics.
- **Compare** live CPU and memory usage against resource requests and limits to decide whether a workload has healthy headroom.
- **Verify** that Metrics Server is available and explain what data it can and cannot provide for Kubernetes 1.35 clusters.
- **Evaluate** whether a running application needs request tuning, limit tuning, replica changes, or deeper application investigation based on observed metrics.

---

## Why This Module Matters

Hypothetical scenario: you deploy a small API that looked fine in development, but during a practice exam the pod starts responding slowly after a burst of traffic. The logs do not show an exception, the readiness probe still passes, and `kubectl get pods` shows the workload as `Running`. At this point a beginner often keeps reading logs because logs feel concrete, but the real question is whether the container is running out of CPU time, climbing toward a memory kill, or merely waiting on an external dependency that resource metrics will not explain.

Monitoring gives you the quick dashboard view that fills the gap between "the pod exists" and "the application is healthy." Logs explain events after the application writes them, probes explain whether Kubernetes should route traffic or restart a container, and metrics explain how much CPU and memory the workload is consuming right now. On the CKAD exam you are not expected to design a full Prometheus estate, but you are expected to use `kubectl top`, interpret the numbers without confusing them with requests or limits, and decide what to inspect next.

The dashboard analogy is useful because it keeps the scope honest. A car dashboard can tell you that the fuel level is low or the engine temperature is high, but it does not tell you the chemical composition of the fuel or the complete service history. Kubernetes resource monitoring is similar: `kubectl top` is fast, focused, and intentionally shallow. It tells you whether node, pod, or container resource consumption deserves attention, then you combine that signal with pod descriptions, events, probes, resource settings, and application knowledge.

This module builds the operational habit behind that exam skill. You will check whether Metrics Server is available, read node and pod metrics, drill into containers inside a pod, compare live usage with declared resources, and choose a next action when the numbers look uncomfortable. The goal is not to memorize one command; the goal is to build a reliable first response when an application looks alive but feels unhealthy.

That first response is valuable because it stops two opposite mistakes. One mistake is ignoring resource pressure because the pod status is still green, which can leave a workload crawling toward throttling or an OOM kill. The other mistake is changing resources reflexively whenever an application misbehaves, which can hide a probe, routing, or dependency problem behind larger limits. A short monitoring pass gives you enough evidence to avoid both extremes.

---

## Metrics Server: The Data Source Behind `kubectl top`

Kubernetes does not store a convenient, queryable history of CPU and memory usage in the core API by itself. The kubelet on each node can expose current resource usage, but `kubectl top` needs the resource metrics API to aggregate and present that data. Metrics Server is the common lightweight add-on that scrapes kubelets, keeps recent samples in memory, and serves current CPU and memory metrics through `metrics.k8s.io`.

For a CKAD candidate, the important mental model is that Metrics Server is cluster infrastructure, not an application container you usually manage during an exam task. If the resource metrics API is missing, `kubectl top` cannot invent data, and HPA decisions based on CPU or memory also lose their usual metrics source. In a managed cluster or exam environment it is often preinstalled; in a local cluster, you may need to install or enable it before resource monitoring works.

```bash
# Check for metrics-server deployment
kubectl get deployment -n kube-system metrics-server

# Or check if `top` works
kubectl top nodes
```

When `kubectl top nodes` succeeds, you have confirmed more than command availability. You have confirmed that the API aggregation layer can serve metrics, that Metrics Server has fresh enough node data, and that your current user can read the resource metrics endpoint. When it fails with a message such as `Metrics API not available`, do not treat the workload as unmonitored because of an application fault; first verify the cluster add-on and your permissions.

Metrics Server provides current CPU and memory usage per node, current CPU and memory usage per pod, and the standard CPU or memory data used by the Horizontal Pod Autoscaler. It does not provide historical graphs, application-level counters, latency percentiles, request rates, PromQL queries, or custom business metrics. That boundary matters because `kubectl top` can show that memory rose, but it cannot tell you which endpoint, queue, tenant, or cache key caused the rise.

Pause and predict: if `kubectl top nodes` fails but `kubectl get pods` works, what does that say about the Kubernetes API server versus the metrics API? The API server can be reachable while an aggregated API such as `metrics.k8s.io` is unavailable, so the right response is to separate "cluster object access works" from "resource metrics are being served."

Metrics Server samples frequently enough for quick triage, but it is not a forensic database. Because it keeps recent readings in memory, a restart loses local historical context, and a short spike may disappear before you look at it. That is acceptable for the CKAD workflow because the exam skill is present-tense diagnosis: find the hot pod, compare its live usage to declared resources, and make a practical adjustment or investigation plan.

There is also a useful timing detail to remember when you create a pod and immediately ask for metrics. A pod can become `Ready` before Metrics Server has scraped and published a sample for it, so a fresh pod may briefly be missing from `kubectl top` or may show no useful value. Waiting a short interval is not superstition; it reflects the scrape cycle and keeps you from diagnosing a brand-new pod as broken when the metrics pipeline simply has not caught up yet.

If the Metrics Server deployment exists but `kubectl top` still fails, the failure path belongs to the metrics pipeline rather than to your application. In a real cluster, an administrator might inspect the `metrics.k8s.io` APIService, Metrics Server logs, kubelet connectivity, and certificate settings. In a CKAD task, the more important move is to state the dependency accurately and avoid inventing resource conclusions from missing data.

---

## Reading Node, Pod, and Container Metrics

Start monitoring at the widest level that can answer your immediate question. Node metrics help you decide whether the cluster has broad capacity pressure, while pod metrics help you identify the workload consuming resources in a namespace. Container metrics are the next layer when a pod has more than one container, because resource requests and limits are set on containers even though `kubectl top pods` first presents an aggregate pod view. Kubernetes 1.35 also supports optional pod-level resources via `spec.resources` when the PodLevelResources feature gate is enabled, but container-level settings remain what `kubectl top pods --containers` inspects in the common CKAD case.

```bash
# All nodes
kubectl top nodes

# Output:
# NAME       CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# node-1     250m         12%    1024Mi          25%
# node-2     500m         25%    2048Mi          50%
```

Node output is useful when you suspect a scheduling or shared-capacity problem. A node at high memory usage may not have enough room for new pods, and a node with high CPU usage may be running latency-sensitive workloads that compete for time. The percentages in node output are based on node allocatable by default, so they answer a different question than pod usage: "How busy is this machine?" rather than "How close is this container to its configured limit?" Pass `--show-capacity` to compare against node capacity instead.

```bash
# All pods in current namespace
kubectl top pods

# All pods in all namespaces
kubectl top pods -A

# Pods in specific namespace
kubectl top pods -n kube-system

# Sort by CPU
kubectl top pods --sort-by=cpu

# Sort by memory
kubectl top pods --sort-by=memory

# Specific pod
kubectl top pod my-pod
```

Pod output is the exam workhorse because most CKAD tasks are namespace-scoped application tasks. Sorting by CPU quickly surfaces a busy replica, while sorting by memory surfaces workloads approaching their memory envelope. The `-A` flag is useful in real operations, but in exam tasks you should stay aware of namespace context because you may not need, or be allowed, to inspect every namespace.

Pause and predict: `kubectl top pods` shows a pod using 450m CPU with a limit of 500m, and another pod using 240Mi memory with a limit of 256Mi. Which one is in more immediate danger, and why? The CPU-heavy pod may be throttled and slow, but the memory-heavy pod is closer to a hard kill because memory overage is not smoothed the way CPU time can be.

```bash
# Show metrics per container
kubectl top pods --containers

# Output:
# POD          NAME      CPU(cores)   MEMORY(bytes)
# my-pod       app       100m         128Mi
# my-pod       sidecar   10m          32Mi
```

Container-level output prevents a common diagnostic mistake in multi-container pods. If an application container and a sidecar share a pod, the aggregate pod number can hide which container is actually consuming resources. That distinction matters because resource requests, limits, restart behavior, and image-level fixes are container-specific decisions, not generic pod-level guesses.

Use label selectors whenever a deployment has multiple pods and you need a clean view of one application. A sorted all-namespace output is useful for finding a cluster-wide resource hog, but a selector keeps the question focused on a workload you own. If three replicas of one deployment have very different CPU usage, the difference may point to uneven traffic, a long-running request, cache warm-up, or a pod stuck doing extra background work.

Selectors also make your notes and exam commands easier to defend. A command such as `kubectl top pods -l app=myapp` describes the workload boundary directly, while a visual scan through a long pod list depends on names, memory, and attention under time pressure. That difference matters during troubleshooting because the first command can be repeated by another engineer and should return the same target set as long as the labels are correct.

```bash
# Node status
kubectl top nodes

# Pod status sorted by resource usage
kubectl top pods --sort-by=cpu
kubectl top pods --sort-by=memory
```

This quick health check is intentionally short because monitoring should reduce uncertainty, not create a new investigation ritual every time. First ask whether nodes are broadly pressured, then ask which pods are consuming the most CPU or memory. If the answer points to one pod, drill down; if every pod is small but every node is full, you are looking at capacity distribution rather than one broken application.

```bash
# Top CPU consumers
kubectl top pods -A --sort-by=cpu --no-headers | head -10

# Top memory consumers
kubectl top pods -A --sort-by=memory --no-headers | head -10
```

The `head` filter is a practical way to turn noisy cluster output into a shortlist. In a real incident you would pair this with ownership and namespace checks before changing anything, because the largest consumer might be expected batch work rather than a faulty service. In a CKAD exercise, it helps you quickly locate the pod the task is trying to make you notice.

Sorted output is most useful when you already know what resource dimension matches the symptom. If the symptom is latency under load, CPU sorting is a natural first pass because throttling and CPU starvation can stretch request handling. If the symptom is restart loops, memory sorting and pod descriptions deserve priority because a container can die abruptly after crossing a memory limit.

```bash
# See which container in pod uses most resources
kubectl top pods --containers -l app=myapp
```

Before running this, what output do you expect if the main container is healthy but a logging sidecar is looping? You should expect the pod-level number to look high and the container-level output to concentrate most of that usage in the sidecar. That prediction gives you a testable hypothesis before you start changing deployment resources.

---

## Interpreting CPU, Memory, and Units

The numbers in `kubectl top` are compact, so the first skill is translating units without overthinking them. Kubernetes CPU values are measured in cores and millicores, where `1000m` means one full CPU core and `100m` means one tenth of a core. Memory values are usually displayed in binary units such as `Mi` and `Gi`, although manifests may also contain decimal units such as `M`.

| Value | Meaning |
|-------|---------|
| `1` | 1 full CPU core |
| `1000m` | 1000 millicores = 1 core |
| `500m` | 0.5 cores (half a core) |
| `100m` | 0.1 cores (10% of a core) |

CPU usage should be read as demand for CPU time, not as a pile of memory that fills up. A container using 450m CPU is trying to consume almost half a core at that moment, and if its limit is 500m it may be close to throttling. CPU throttling usually causes latency, slower work, or missed deadlines, but the container is not killed simply because it wanted more CPU than the limit allowed.

| Value | Meaning |
|-------|---------|
| `128Mi` | 128 mebibytes |
| `1Gi` | 1 gibibyte (1024 Mi) |
| `256M` | 256 megabytes |

Memory usage behaves differently because it is capacity that a process holds. If a container exceeds its memory limit, the kernel can terminate it with an out-of-memory kill, and Kubernetes will report the previous state when you describe the pod. That is why a pod at 94 percent of its memory limit feels more dangerous than a pod at 94 percent of its CPU limit, even though both numbers deserve attention.

```text
NAME        CPU(cores)   CPU%     MEMORY(bytes)   MEMORY%
my-pod      100m         10%      256Mi           12%
```

In this output, `100m` means the pod is using 100 millicores, or roughly 10 percent of one CPU core. `256Mi` means it is currently using 256 mebibytes of memory. Percentages on node output relate to node allocatable by default (`--show-capacity` uses capacity), while pod output is most useful when you compare the absolute values against the workload's requests and limits.

The key habit is to avoid treating every high number as the same kind of emergency. High CPU can explain slowness, queue buildup, or throttling, but it may also be expected during a short batch job. High memory near a limit can explain restarts, OOMKilled events, and sudden process death, and it often needs either more headroom or application-level memory controls.

CPU percentages can be especially misleading if you forget what the percentage is relative to. Node percentages are relative to node allocatable by default (or capacity with `--show-capacity`), while pod CPU values are more useful as millicores that you compare to the container's request and limit. When in doubt, trust the absolute unit first, then use percentages only as a quick capacity signal for the node view.

```yaml
resources:
  requests:
    cpu: "100m"      # Guaranteed minimum
    memory: "128Mi"
  limits:
    cpu: "500m"      # Maximum allowed
    memory: "256Mi"
```

Requests and limits answer different questions from live usage. A request tells the scheduler how much capacity to reserve for placement and quality of service decisions. A limit tells the runtime the maximum a container is allowed to consume, with CPU and memory enforcing that maximum in different ways.

This distinction also affects how Kubernetes classifies pods for quality of service. A pod with no requests and no limits is treated differently from a pod whose containers have matching requests and limits, and those classifications influence eviction choices under node pressure. You do not need to recite every class for this module, but you should recognize why honest requests matter even when a workload is not near a limit.

```bash
# Actual usage from metrics
kubectl top pod my-pod
# CPU: 50m, Memory: 100Mi

# Interpretation:
# - Using 50m CPU (within 100m request, well under 500m limit)
# - Using 100Mi RAM (within 128Mi request, under 256Mi limit)
```

This pod is currently using less CPU than requested and less memory than requested, so it has comfortable headroom. That does not prove it will always be healthy, because `kubectl top` is current-state data rather than historical evidence. It does, however, tell you that an immediate resource limit is probably not the reason for a live symptom at the instant you measured it.

Stop and think: a pod has resource requests of `cpu: 100m, memory: 128Mi` but `kubectl top` shows actual usage of `cpu: 50m, memory: 300Mi`, and the pod has not been OOMKilled. How is this possible? The request is not a ceiling, so memory can rise above the request; only a memory limit creates a hard maximum, and the pod may have no memory limit or a limit above 300Mi.

```bash
# Check if pods are near their limits
kubectl top pods

# Compare with defined limits
kubectl get pod my-pod -o jsonpath='{.spec.containers[*].resources}'
```

That comparison is the smallest useful resource investigation loop. First observe current usage, then inspect the declared resource policy, then decide whether the problem is too little requested capacity, a limit that is too tight, an application consuming unexpected resources, or a workload that needs more replicas. The numbers are not the decision by themselves; they are the evidence you use to choose the next command.

---

## Comparing Usage with Requests and Limits

The most common monitoring error is comparing the wrong things. A pod using more than its request is not automatically unhealthy, because requests are scheduling promises rather than runtime ceilings. A pod near its memory limit, however, may be one allocation away from termination, and a pod near its CPU limit may be getting throttled hard enough to miss response-time expectations.

Think of requests as the table reservation and limits as the restaurant closing time. A reservation means the restaurant planned space for you, but it does not mean you cannot order more food if the kitchen has capacity. Closing time is different: once it arrives, service stops regardless of whether you wanted one more course.

For CPU, low requests can cause scheduling pressure and noisy-neighbor behavior because the scheduler placed too many hungry workloads on the same node. Tight CPU limits can cause throttling when the application needs short bursts. For memory, low requests can make placement optimistic, while tight limits create abrupt failures when the process crosses the boundary.

Resource usage below request usually means the container has enough reserved capacity for its current behavior. Usage above request but below limit means the container is borrowing available node capacity and may still be acceptable if the workload is bursty. Usage near a limit means you should inspect symptoms, events, and application behavior before deciding whether to raise the limit, tune the application, or change traffic distribution.

The phrase "borrowing available capacity" is important because it explains both flexibility and risk. Kubernetes allows a container to use more than its request when the node has room, which makes bursts efficient. The risk is that many containers can be scheduled based on requests that are lower than their real sustained usage, leaving the node crowded when several workloads become busy at the same time.

Use `kubectl describe pod` when metrics suggest a memory problem because the description can show restart counts, last termination reason, and events. A current memory value of 220Mi against a 256Mi limit is uncomfortable, but a previous `OOMKilled` state changes the diagnosis from "risk" to "already happened." Monitoring finds the pressure; pod state confirms whether Kubernetes has already acted.

Exercise scenario: a three-replica deployment has one pod using 400m CPU while the other two use 50m. If there is no CPU limit, the hot pod may burst as much as the node allows, and the immediate risk is resource competition with other workloads. If there is a 500m limit, the hot pod is close to throttling, and you should inspect traffic balance, session affinity, long-running requests, or uneven cache warm-up.

When evaluating whether to change requests or limits, avoid using a single sample as the only evidence unless the exam task is intentionally simple. One `kubectl top` reading tells you a point in time, while a workload's safe resource policy should reflect expected sustained behavior and bursts. In CKAD tasks, you can still make a targeted change when the exercise gives a clear symptom, but the professional habit is to distinguish present triage from long-term capacity planning.

For request tuning, ask whether the scheduler had an honest picture of the workload. If a pod usually runs at 300Mi but requests 64Mi, the cluster may overpack nodes even though the pod survives in quiet periods. Raising the request does not make the application consume less memory, but it makes placement more truthful and can reduce surprises when several pods become active together.

For limit tuning, ask whether the boundary is protecting the cluster or punishing normal behavior. A memory limit below a routine working set creates restart risk, while a CPU limit below a normal burst creates latency risk. Removing limits entirely is not automatically better, because one runaway container can then compete aggressively with other workloads on the same node.

The same principle applies to memory. If a Java service with a cache is using 240Mi of a 256Mi limit, raising the limit may stop immediate restarts, but it may not fix an unbounded cache. The right recommendation often has two layers: create enough headroom for stability, then investigate or configure the application so memory growth is intentional rather than accidental.

---

## Worked Monitoring Workflow

A reliable monitoring workflow starts with a narrow question instead of a command habit. If users report slowness, ask whether the workload is CPU-constrained, memory-constrained, unevenly loaded, or blocked on something metrics cannot see. That framing helps you decide whether to inspect nodes, pods, containers, resource specs, events, or logs next.

Begin by checking node pressure because a saturated node can make healthy pods look bad. If one node has much higher CPU or memory use than its peers, the issue may be placement, a local hot workload, or a lack of spare cluster capacity. If nodes look fine, shift to pod-level output and sort by the resource that matches the symptom.

Then compare replicas rather than reading a single pod in isolation. A deployment is a set of interchangeable pods, so uneven metrics are often more revealing than a single high number. If one replica is hot and the others are idle, resource tuning may be less urgent than understanding why load, state, or background work is not distributed evenly.

Next, compare the hot pod against its declared resources. A pod using 80m CPU with a 500m limit is unlikely to be CPU-throttled, even if it is the top CPU user in a quiet namespace. A pod using 480m CPU with a 500m limit is a different story, especially if latency is rising or readiness failures appear during load.

For multi-container pods, move from pod totals to container breakdown before changing the deployment. Sidecars, proxies, log shippers, and service mesh containers can consume more than expected, and their tuning path is different from the main application. If the sidecar is hot, raising the main container's limit will not solve the cause.

Finally, decide whether metrics are enough for the task. Resource metrics can justify changing requests, limits, or replicas, but they cannot explain every application symptom. If CPU and memory look healthy, switch to logs, events, probes, endpoints, network policy, service routing, or application-level metrics rather than trying to force `kubectl top` to answer a question outside its scope.

This is where senior judgment stays practical rather than philosophical. A strong monitoring response does not mean running every command you know; it means stopping once the evidence points away from resource pressure and choosing the next tool deliberately. On the exam, that discipline saves time because you avoid editing manifests that have nothing to do with the observed failure.

The following visualization keeps the request-limit relationship visible while you make those decisions. It is intentionally simple: below request is comfortable, above request is borrowed capacity, near limit is warning, and beyond a memory limit becomes a kill path. CPU differs in enforcement, but the same visual habit helps you compare present usage to declared boundaries.

```text
┌─────────────────────────────────────────────────────────────┐
│                  Resource Usage Levels                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Memory Usage Example:                                      │
│                                                             │
│  |                                                          │
│  |  ▓▓▓▓▓▓▓▓▓▓ Limit: 256Mi (max before OOMKill)           │
│  |                                                          │
│  |  ████████ Request: 128Mi (guaranteed)                   │
│  |                                                          │
│  |  ████ Current: 64Mi (from kubectl top)                  │
│  |                                                          │
│  └──────────────────────────────────────────────           │
│                                                             │
│  Status: Healthy (usage < request)                         │
│                                                             │
│  ─────────────────────────────────────────────             │
│                                                             │
│  |                                                          │
│  |  ▓▓▓▓▓▓▓▓▓▓ Limit: 256Mi                                │
│  |                                                          │
│  |  ████████████████ Current: 200Mi (from kubectl top)     │
│  |                                                          │
│  |  ████████ Request: 128Mi                                │
│  |                                                          │
│  └──────────────────────────────────────────────           │
│                                                             │
│  Status: Warning (usage > request, approaching limit)       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The worked outcome is deliberately modest because most monitoring wins are modest. You do not need to build a dashboard to know that a pod using 200Mi of a 256Mi memory limit deserves attention. You need to notice the relationship, confirm whether restarts or events already happened, and choose whether to adjust resources or investigate application behavior.

---

## CKAD Scope and Operational Boundaries

The CKAD monitoring scope is practical and command-line focused. You should know how to use `kubectl top`, identify whether Metrics Server is available, read CPU and memory units, sort pods by resource usage, and drill into containers. You should also understand that monitoring is one observability signal among logs, probes, events, and descriptions, not a replacement for them.

What you do not need for this module is a full Prometheus setup, Grafana dashboard design, PromQL query writing, custom metrics adapter configuration, or long-term storage architecture. Those topics matter in production, but they are outside the quick resource-monitoring workflow CKAD emphasizes. Keeping that boundary clear helps you spend exam time on commands that actually solve the task.

In Kubernetes 1.35 and nearby current versions, the resource metrics workflow remains centered on the Metrics API and `kubectl top`. The command output may vary slightly by cluster, and local environments sometimes need extra Metrics Server flags for kubelet TLS or address preferences. The interpretation habit remains stable: current usage first, declared resource policy second, symptom-specific follow-up third.

You should also know when `kubectl top` is not enough. If a pod is slow with low CPU and low memory, the bottleneck may be I/O, DNS, an external service, application locking, garbage collection, or a bad readiness design. Resource metrics tell you whether CPU or memory pressure is plausible; they do not prove the absence of every other problem.

Another boundary is the difference between infrastructure metrics and application metrics. CPU and memory can tell you that a process is working hard, but they cannot tell you how many checkout requests failed, how long a queue waited, or whether a cache hit rate collapsed. For CKAD, you only need the infrastructure layer here, but recognizing the boundary prevents you from overclaiming what the data proves.

When a task asks you to "monitor" or "check resource usage," do not jump straight to editing manifests. Gather the metric, compare it to requests and limits, and only then decide whether a resource change is justified. That sequence protects you from treating every symptom as a capacity problem and from making a workload less efficient by raising limits without evidence.

---

## Patterns & Anti-Patterns

A useful pattern is the two-level check: inspect nodes first when the symptom might be cluster-wide, then inspect pods when the symptom is workload-specific. This pattern works because node pressure and pod pressure require different next actions. Scaling one deployment may help a hot application, but it will not create capacity on a full cluster if every node is already constrained.

Another strong pattern is selector-based monitoring for deployments. Instead of scanning all pods and visually filtering names, use labels to ask for the pods that belong to one workload. This keeps your command output small, makes sorted results meaningful, and avoids confusing a similarly named system pod with the application you are responsible for.

A third pattern is container breakdown before resource edits in multi-container pods. When a pod has sidecars, the aggregate pod number is only a starting point. Container-level metrics help you change the correct container's request or limit and help you avoid blaming the main application for resource use caused by a proxy, logger, or helper process.

The first anti-pattern is treating requests as health thresholds. Teams fall into this because requests and limits live beside each other in the manifest, but requests are scheduling inputs, not runtime alarms. The better approach is to read usage relative to both values: usage above request affects capacity planning, while usage near limit affects immediate runtime risk.

The second anti-pattern is expecting `kubectl top` to explain history. The command shows current resource usage, not yesterday's spike or a trend line across a release. If you need historical analysis, use a monitoring stack that stores time series; if you are solving a CKAD task, use `kubectl top` for fast present-tense evidence and move on.

The third anti-pattern is changing limits without checking events. A pod near a memory limit is concerning, but an actual `OOMKilled` event gives you stronger evidence and may change the urgency. Pair the metric with pod description output when the symptom involves restarts, because Kubernetes state tells you whether the risk has already turned into failure.

---

## Decision Framework

Use `kubectl top nodes` when the question is about cluster capacity, uneven node pressure, or whether one node is carrying an unusual load. Use `kubectl top pods` when the question is about which workload is hot in a namespace. Use `kubectl top pods --containers` when a pod has more than one container or when the aggregate pod number does not identify the actual consumer.

If CPU is high and memory is comfortable, look for throttling risk, uneven traffic, expensive requests, or too few replicas. Raising a CPU limit may reduce throttling, but it can also let one workload take more node CPU, so compare the change with node capacity and the workload's expected behavior. In a quick exam task, the manifest may make the intended adjustment obvious; in production, you would validate it with longer measurements.

If memory is high and close to a limit, inspect restarts and previous state before assuming the application is merely busy. Memory limits are hard boundaries, and a small allocation can convert a warning into an OOM kill. The next action might be increasing headroom, reducing cache size, fixing a leak, or lowering per-pod load by scaling replicas.

If one replica is hot and its siblings are quiet, resist the urge to tune every replica equally before you understand the asymmetry. A deployment can be healthy in aggregate while one pod handles sticky sessions, a long request, a warmed cache, or a background task that other replicas do not share. The decision framework therefore treats unevenness as a clue: first explain why the pod differs, then decide whether resource policy, traffic distribution, or application behavior should change.

If both CPU and memory look low, stop trying to solve the symptom with resource knobs. Check logs, events, readiness and liveness probes, service endpoints, DNS, network policy, dependencies, or application metrics. A calm `kubectl top` output is useful because it narrows the search, but it does not declare the application healthy by itself.

If Metrics Server is unavailable, separate the exam response from the cluster-admin response. In an exam, note that `kubectl top` depends on Metrics Server and use other available evidence if installation is outside the task. In a real cluster, verify the deployment, APIService, kubelet access, and Metrics Server logs before drawing conclusions from missing metrics.

If metrics are available but surprising, prefer reversible observation before mutation. Re-run a focused command with a selector, check container-level output, and inspect the manifest resources before applying changes. That small pause catches many wrong fixes, especially when a sidecar, namespace mismatch, or stale mental model made the first reading look more dramatic than it was.

---

## Did You Know?

- **Metrics Server scrapes kubelets every 15 seconds by default.** The data is recent enough for quick triage, but it is not a real-time stream or a durable history.
- **`kubectl top` shows current usage, not historical trends.** For release comparisons, incident timelines, and capacity forecasts, you need a time-series monitoring system.
- **Horizontal Pod Autoscaler uses resource metrics for standard CPU and memory scaling decisions.** If resource metrics are unavailable, HPA cannot make normal CPU or memory decisions.
- **Metrics Server keeps its working data in memory.** A restart removes local historical context, which is one reason it should not be treated as a monitoring database.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Running `kubectl top` before verifying Metrics Server | The core API works, so the missing metrics API looks like an application problem | Check `kubectl top nodes` and the `metrics-server` deployment before interpreting absent metrics |
| Confusing requests with actual usage | Requests and limits sit together in YAML, so they feel like the same kind of threshold | Treat requests as scheduling reservations and compare live usage separately against limits |
| Ignoring high memory pods | CPU throttling is visible as slowness, while memory risk may stay quiet until a kill | Sort by memory, compare to limits, and inspect pod previous state for `OOMKilled` |
| Not checking container-level metrics | Pod totals are easier to read than per-container output | Use `kubectl top pods --containers` before changing resources in multi-container pods |
| Expecting historical data from `kubectl top` | The command feels like a monitoring tool, so learners expect charts and trends | Use `kubectl top` for current triage and a time-series stack for history |
| Changing limits without checking events | A high number creates urgency, so the manifest gets edited first | Pair metrics with `kubectl describe pod` to confirm restarts, throttling clues, or OOM history |
| Sorting all namespaces without narrowing ownership | Cluster-wide output looks authoritative but can mix unrelated workloads | Use namespaces and label selectors when the task concerns one application |

---

## Quiz

<details>
<summary>Your deployment has three replicas. One pod uses 400m CPU while the other two use 50m each, and users report uneven latency. What should you check before raising CPU limits?</summary>

First compare the hot pod's usage to its CPU request and limit to see whether it is actually near throttling. Then check whether traffic is uneven, whether one pod is handling long-running work, and whether the deployment uses sticky sessions or a cache pattern that creates a hot replica. Raising a CPU limit may reduce throttling, but it will not fix an imbalanced workload. Container-level metrics are also useful if the pod has a sidecar that could be consuming the CPU.
</details>

<details>
<summary>A Java pod with `limits.memory: 256Mi` shows 240Mi in `kubectl top pods`, but it has not restarted yet. How should you evaluate the risk?</summary>

The pod is close to a hard memory boundary, so the risk is high even without a current restart. Memory above the limit can result in an OOM kill, unlike CPU pressure that usually appears as throttling. You should inspect `kubectl describe pod` for previous OOM kills and review whether the cache or heap has a configured maximum. A reasonable fix may include more headroom plus application-level memory tuning.
</details>

<details>
<summary>You run `kubectl top nodes` and receive `Metrics API not available`, while `kubectl get pods` still works. What does that tell you?</summary>

The core Kubernetes API is reachable, but the resource metrics API is not serving data to your request. The missing component is usually Metrics Server, an unhealthy Metrics Server deployment, an APIService problem, or a permission issue. This does not prove that application pods are unhealthy. It tells you that `kubectl top` currently lacks its data source, so you must verify the metrics pipeline before using resource metrics.
</details>

<details>
<summary>A multi-container pod has an application container and a logging sidecar. Pod-level metrics show 200m CPU total. How do you identify the real consumer and why does it matter?</summary>

Run `kubectl top pods POD_NAME --containers` or use the same command with a selector to see per-container CPU and memory. The distinction matters because resources are commonly configured per container, not as one shared pod knob in the manifest—though Kubernetes 1.35 also supports optional pod-level resources via `spec.resources` when the PodLevelResources feature gate is enabled. If the sidecar uses 180m, raising the application container's request would miss the cause. The correct fix might be sidecar configuration, image behavior, or a sidecar-specific limit.
</details>

<details>
<summary>A pod uses 300Mi memory, its request is 128Mi, and there is no memory limit. It is not OOMKilled. Is this inconsistent?</summary>

No, this is consistent because a memory request is not a maximum. The request helped the scheduler place the pod and influences quality of service, but it does not stop the process at 128Mi. Without a memory limit, the container can consume more memory as long as the node can provide it. The operational question becomes whether the request is too low for honest scheduling and whether a limit should be set deliberately.
</details>

<details>
<summary>After checking `kubectl top pods`, CPU and memory both look low, but readiness failures continue. What should you do next?</summary>

Low CPU and memory make resource pressure less likely as the primary cause, so you should widen the investigation. Check pod events, readiness probe configuration, application logs, service endpoints, DNS, network policy, and dependency health. Monitoring has still helped because it removed one class of explanation. The mistake would be raising resources simply because the application is unhealthy.
</details>

<details>
<summary>You sort pods by memory and find a system namespace pod at the top, but your task concerns one application deployment. How should you keep the investigation focused?</summary>

Use the target namespace and label selectors to inspect the deployment's pods directly. Cluster-wide sorting is useful for capacity awareness, but it can distract you with workloads unrelated to the task. For an application investigation, `kubectl top pods -l app=...` gives a cleaner comparison across replicas. If node pressure remains suspicious, then return to node metrics and broader namespace output.
</details>

---

## Hands-On Exercise

Exercise scenario: you will create a small deployment with requests and limits, wait for Metrics Server to publish readings, compare live usage with declared resources, and then repeat the same monitoring pattern through focused drills. If your local cluster does not have Metrics Server installed, the setup commands may still create pods successfully, but `kubectl top` will fail until the metrics API is available. Treat that failure as a valid diagnostic finding rather than as a reason to skip the interpretation steps.

The task is to monitor resource usage of running applications, compare the numbers with resource policy, and explain the next action you would take from the evidence.

### Setup
```bash
# Create a deployment with known resource usage
cat << 'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: monitor-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: monitor-demo
  template:
    metadata:
      labels:
        app: monitor-demo
    spec:
      containers:
      - name: nginx
        image: nginx
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
EOF

# Wait for pods to be ready and metrics to populate
kubectl rollout status deployment/monitor-demo
sleep 30
```

Use this setup to practice a realistic order of operations. You are not trying to make nginx consume a large amount of CPU; you are practicing how to locate metrics, read the units, compare the live values to the manifest, and notice when metrics are unavailable. The `sleep 30` gives Metrics Server time to publish a sample in typical local clusters.

### Part 1: Basic Monitoring
```bash
# Check if metrics server is running
kubectl top nodes

# View pod metrics
kubectl top pods -l app=monitor-demo

# Sort by CPU
kubectl top pods --sort-by=cpu
```

<details>
<summary>Solution guidance for Part 1</summary>

If `kubectl top nodes` returns node metrics, continue to pod metrics and compare the three replicas. If it returns a Metrics API error, verify Metrics Server before blaming the deployment. For a quiet nginx deployment, CPU and memory should usually be small, so the main success criterion is reading and interpreting the output rather than finding a dramatic spike.
</details>

### Part 2: Compare with Requests
```bash
# Get resource requests
kubectl get pods -l app=monitor-demo -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources}{"\n"}{end}'

# Compare with actual usage
kubectl top pods -l app=monitor-demo
```

<details>
<summary>Solution guidance for Part 2</summary>

The JSONPath command shows the requests and limits declared on the container, while `kubectl top` shows current usage. Healthy idle nginx pods should normally sit below their memory limit and use little CPU. If a live value is above a request but below a limit, call that borrowed capacity rather than an automatic failure.
</details>

### Cleanup
```bash
kubectl delete deploy monitor-demo
```

### Practice Drills

These drills preserve the same monitoring moves in smaller exam-style repetitions. Run them only in a disposable practice namespace or local cluster, and delete the resources when finished. The targets are intentionally short because CKAD monitoring tasks reward quick recognition and accurate interpretation.

### Drill 1: Node Metrics (Target: 1 minute)

```bash
# Check node resource usage
kubectl top nodes

# Identify which node has highest CPU
kubectl top nodes --sort-by=cpu
```

<details>
<summary>Drill 1 solution</summary>

The highest CPU node appears at the top of the sorted output. If the command fails, record that Metrics Server is unavailable and do not infer anything about node load from the absence of data. If it succeeds, compare CPU and memory percentages because the busiest CPU node is not always the busiest memory node.
</details>

### Drill 2: Pod Metrics (Target: 2 minutes)

```bash
# Create test pods
kubectl run drill2a --image=nginx
kubectl run drill2b --image=nginx

# Wait for metrics to populate
kubectl wait --for=condition=ready pod/drill2a pod/drill2b
sleep 30

# Check their metrics
kubectl top pods

# Cleanup
kubectl delete pod drill2a drill2b
```

<details>
<summary>Drill 2 solution</summary>

Both pods should appear in `kubectl top pods` after Metrics Server has a sample. If one pod is missing immediately after readiness, wait briefly because metrics collection is not instantaneous. The expected interpretation is that simple nginx pods use little CPU until they receive meaningful traffic.
</details>

### Drill 3: Container Metrics (Target: 2 minutes)

```bash
# Create multi-container pod
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: drill3
spec:
  containers:
  - name: nginx
    image: nginx
  - name: sidecar
    image: busybox
    command: ['sleep', '3600']
EOF

# Wait for pod and metrics to populate
kubectl wait --for=condition=ready pod/drill3
sleep 30

# View per-container metrics
kubectl top pods drill3 --containers

# Cleanup
kubectl delete pod drill3
```

<details>
<summary>Drill 3 solution</summary>

The output should show separate rows for the `nginx` and `sidecar` containers. The busybox sidecar is only sleeping, so its CPU should normally be very low. The important skill is verifying that you can separate container usage instead of relying on the aggregate pod number.
</details>

### Drill 4: Sorted Output (Target: 2 minutes)

```bash
# Get pods sorted by memory usage
kubectl top pods -A --sort-by=memory

# Get pods sorted by CPU usage
kubectl top pods -A --sort-by=cpu
```

<details>
<summary>Drill 4 solution</summary>

The first command puts memory-heavy pods near the top, while the second does the same for CPU-heavy pods. If a system pod leads the list, do not assume it is part of your application problem. Use the sorted output as a shortlist, then narrow by namespace or label.
</details>

### Drill 5: System Pods (Target: 2 minutes)

```bash
# Check kube-system pod resource usage
kubectl top pods -n kube-system

# Sort by CPU to find most active
kubectl top pods -n kube-system --sort-by=cpu
```

<details>
<summary>Drill 5 solution</summary>

System namespace metrics help you distinguish application pressure from control-plane or cluster add-on activity. In many local clusters, system pods should be modest, but exact values depend on the environment. The skill is reading namespace-scoped metrics without mixing them with your application deployment.
</details>

### Drill 6: Full Monitoring Workflow (Target: 4 minutes)

The scenario for this final drill is an investigation of suspected high resource usage in a deployment with multiple replicas.

```bash
# Create deployment with multiple replicas
kubectl create deploy drill6 --image=nginx --replicas=5

# Wait for pods and metrics to populate
kubectl rollout status deployment/drill6
sleep 30

# Check overall deployment resource usage
kubectl top pods -l app=drill6

# Find highest consumer
kubectl top pods -l app=drill6 --sort-by=cpu

# Check container level
kubectl top pods -l app=drill6 --containers

# Compare to node capacity
kubectl top nodes

# Cleanup
kubectl delete deploy drill6
```

<details>
<summary>Drill 6 solution</summary>

The expected workflow is selector first, sorted selector second, container breakdown third, and node comparison last. For a quiet nginx deployment, you may not find meaningful high usage, but the command sequence is still the point. If one replica is much higher than the others, inspect whether it is receiving traffic or doing work the other replicas are not doing.
</details>

### Success Criteria

- [ ] You verified whether Metrics Server is serving resource metrics by running a `kubectl top` command.
- [ ] You compared pod CPU and memory usage with the deployment's declared requests and limits.
- [ ] You used sorted pod output to identify the highest CPU or memory consumer.
- [ ] You used `--containers` to separate container-level metrics in a multi-container pod.
- [ ] You explained whether a high memory value near a limit is more urgent than a high CPU value near a limit.
- [ ] You cleaned up all practice pods and deployments created during the exercise.

---

## Learner check

> The percentages in node output are based on node allocatable by default, so they answer a different question than pod usage: "How busy is this machine?" rather than "How close is this container to its configured limit?" Pass `--show-capacity` to compare against node capacity instead.

Before you move on, explain why node CPU% and memory% can differ from what you would calculate against total node capacity, and when you would pass `--show-capacity`.

---

## Sources

- [Kubernetes documentation: Resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [Kubernetes documentation: Metrics for Kubernetes system components](https://kubernetes.io/docs/concepts/cluster-administration/system-metrics/)
- [Kubernetes documentation: Managing resources for containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes documentation: Assign CPU resources to containers and pods](https://kubernetes.io/docs/tasks/configure-pod-container/assign-cpu-resource/)
- [Kubernetes documentation: Assign memory resources to containers and pods](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/)
- [Kubernetes documentation: `kubectl top`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/)
- [Kubernetes documentation: Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Kubernetes documentation: Metrics API](https://kubernetes.io/docs/reference/external-api/metrics.v1beta1/)
- [Metrics Server GitHub repository](https://github.com/kubernetes-sigs/metrics-server)
- [Metrics Server FAQ — high availability and scaling](https://github.com/kubernetes-sigs/metrics-server/blob/master/FAQ.md)
- [KubeDojo lab scenario: CKAD 3.4 Monitoring](https://killercoda.com/kubedojo/scenario/ckad-3.4-monitoring)

## Next Module

[Module 3.5: API Deprecations](../module-3.5-api-deprecations/) - Next you will handle API version changes and deprecations so manifests stay compatible with current Kubernetes releases.
