---
revision_pending: false
title: "Module 5.7: Logging & Monitoring"
slug: k8s/cka/part5-troubleshooting/module-5.7-logging-monitoring
sidebar:
  order: 8
lab:
  id: cka-5.7-logging-monitoring
  url: https://killercoda.com/kubedojo/scenario/cka-5.7-logging-monitoring
  duration: "35 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Essential observability skills
>
> **Time to Complete**: 40-50 minutes
>
> **Prerequisites**: Module 5.1 (Methodology), Modules 5.2-5.6 (troubleshooting specifics)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Debug** container log investigations using `kubectl logs` with container selection, previous logs, follow mode, timestamps, and label selectors.
- **Evaluate** Kubernetes events to diagnose scheduling, mount, probe, restart, and eviction failures before event retention expires.
- **Implement** sidecar-based logging for applications that write files instead of `stdout` and `stderr`.
- **Monitor** resource usage with `kubectl top` by explaining how Metrics Server moves kubelet metrics into the `metrics.k8s.io` API.
- **Correlate** node-level logs, container logs, events, and metrics to choose the next diagnostic action during a Kubernetes 1.35 troubleshooting session.

## Why This Module Matters

Hypothetical scenario: a Deployment rolls out during a release window, the new pods alternate between `Running` and `CrashLoopBackOff`, the application team says their health endpoint passed in staging, and the platform team sees no obvious node failure. In that moment, the useful question is not "where are the logs?" but "which evidence source can still answer the current question?" Container logs may show an exception, previous container logs may show the line just before a restart, events may show an image pull or probe failure, and resource metrics may show that the pod is being throttled or killed under pressure.

Logging and monitoring in Kubernetes are deliberately split across layers because no single API can tell the whole story. The kubelet captures container `stdout` and `stderr`, the API server stores short-lived Events, Metrics Server exposes recent CPU and memory measurements, and node services such as kubelet and containerd keep their own journals. A strong troubleshooter moves across those layers with a sequence of hypotheses, rather than staring at one noisy log stream and hoping the important line appears.

This module turns the quick commands from earlier troubleshooting lessons into an operational workflow. You will practice reading current and previous container logs, interpreting events, checking resource metrics, using a sidecar for file-based logs, and falling back to node logs when the Kubernetes API is unavailable or incomplete. The point is not to memorize every flag; the point is to know which observable can still contain evidence, what each tool cannot show, and how to narrow a failure without inventing a story.

## Container Logs: Current, Previous, and Multi-Container Evidence

Kubernetes logging starts with a simple contract: applications should write useful diagnostic output to `stdout` and `stderr`, and the node will make that output available through the kubelet. The container runtime writes the stream into log files on the node, kubelet exposes those files through its API, and `kubectl logs` retrieves the content through the Kubernetes API path. That design keeps application containers simple, but it also means a log line is scoped to a container instance, not to a Deployment, a Service, or a long-lived business process.

```
┌──────────────────────────────────────────────────────────────┐
│                 CONTAINER LOGGING FLOW                        │
│                                                               │
│   Container                                                   │
│   ┌────────────────────────────────────────────────────┐     │
│   │  Application                                        │     │
│   │       │                                             │     │
│   │       ├── stdout ──────┐                           │     │
│   │       │                │                           │     │
│   │       └── stderr ──────┼────▶ Container runtime    │     │
│   │                        │      captures output      │     │
│   └────────────────────────────────────────────────────┘     │
│                            │                                  │
│                            ▼                                  │
│   Node filesystem                                             │
│   /var/log/containers/<pod>_<ns>_<container>-<id>.log        │
│                            │                                  │
│                            ▼                                  │
│   kubectl logs (reads these files via kubelet API)           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

The practical consequence is that the first log command you run should match the failure mode you are testing. A stable single-container pod can usually be inspected directly, while a restarted container often needs `--previous`, and a multi-container pod needs explicit container selection. If you skip that choice, you may inspect the wrong stream and build the wrong diagnosis, especially when a sidecar, init container, or log forwarder is the component actually failing.

```bash
# View logs from a pod (single container)
kubectl logs <pod>

# View logs from specific container (multi-container pod)
kubectl logs <pod> -c <container>

# Follow logs in real-time
kubectl logs <pod> -f

# Show last N lines
kubectl logs <pod> --tail=50

# Show logs since time
kubectl logs <pod> --since=1h
kubectl logs <pod> --since=30m

# Show logs with timestamps
kubectl logs <pod> --timestamps

# Combine options
kubectl logs <pod> --tail=100 --timestamps -f
```

**Pause and predict:** A pod has two containers. If you run `kubectl logs <pod>` without `-c`, what evidence would you expect, and what might you miss while investigating?

<details>
<summary>Reveal the container boundary</summary>

Logs belong to containers, not the pod as a merged unit. With two containers, a command that does not name one is ambiguous; identify the container you need or explicitly request all containers.

</details>

Before choosing a command, inspect the pod specification and decide which component could explain the symptom you are investigating.

Multi-container pods are common in production even when the application itself seems simple. A service mesh proxy, file tailer, authentication helper, or metrics exporter can all live beside the main application and fail independently. When the symptom involves traffic, logging, startup ordering, or shared volumes, inspect the container list before assuming the app container is the only useful source of evidence.

```bash
# List containers in a pod
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].name}'

# Get logs from specific container
kubectl logs <pod> -c <container>

# Get logs from all containers
kubectl logs <pod> --all-containers=true

# Get logs from init containers
kubectl logs <pod> -c <init-container>
```

Previous container logs are essential for `CrashLoopBackOff` because the current container instance may not have reached the failing code path yet. `kubectl logs <pod>` reads the active instance by default, so it can show only a startup banner while the useful stack trace is attached to the instance that died moments earlier. The `--previous` flag changes the target from the current container to the last terminated instance, which is often the difference between seeing "starting application" and seeing the exception that caused the restart.

```bash
# Get logs from previous container instance (after crash)
kubectl logs <pod> --previous
kubectl logs <pod> -c <container> --previous

# This shows what was logged before the container died
# Essential for understanding why it crashed
```

File-based logging is the awkward case because Kubernetes does not automatically collect arbitrary files inside a container filesystem. A legacy process that writes only to `/var/log/app.log` can be perfectly chatty from the application's point of view and completely silent from `kubectl logs`. The usual bridge is a sidecar container that shares a volume with the application, tails the file, and writes the same content to its own `stdout`, where the kubelet can capture it normally.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: legacy-app
spec:
  containers:
  - name: main-app
    image: legacy-app:1.0
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log
  - name: log-tailer
    image: busybox:1.36
    command: ["/bin/sh", "-c", "touch /var/log/app.log 2>/dev/null; tail -n+1 -F /var/log/app.log"]
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log
  volumes:
  - name: shared-logs
    emptyDir: {}
```

You can then view the logs by querying the sidecar with `kubectl logs legacy-app -c log-tailer`. This pattern is useful when you cannot change the application quickly, but it has tradeoffs: the sidecar consumes resources, the shared `emptyDir` is node-local and ephemeral, and a naive `tail -f` can miss rotation behavior unless the application and tailer agree on file handling. Treat it as a compatibility pattern, not as an excuse to ignore modern `stdout` and structured logging practices.

Label and controller log selection help when the failing behavior exists across replicas. Bare `kubectl logs deployment/<name>` follows the controller relationship but streams logs from only one representative pod in that Deployment; add `--all-pods=true` when you need every replica. `kubectl logs -l app=nginx` selects pods by labels, which is useful when a Deployment, StatefulSet, or Job created several pods that share the same symptom. These commands are convenient, but they can also produce interleaved output, so combine them with timestamps, container names, and a small `--tail` when you are trying to reconstruct timing.

```bash
# Logs from all pods with a label
kubectl logs -l app=nginx

# Logs from all pods in a deployment (--all-pods=true required)
kubectl logs deployment/my-deployment --all-pods=true

# Follow logs from all matching pods
kubectl logs -l app=nginx -f

# With container name for multi-container pods
kubectl logs -l app=nginx -c <container>
```

Before running this, what output do you expect if one selected pod is still pending and another is already running? The command can only return logs for containers that have produced logs, so missing output is not always evidence that an application is quiet. It may mean the container never started, the wrong namespace was selected, the label matched fewer pods than expected, or the useful evidence lives in Events rather than logs.

## Kubernetes Events: Short-Lived Clues from the Control Plane

Events are Kubernetes objects that record notable state changes and operational warnings. They are not application logs, and they are not a permanent audit trail; they are short-lived clues produced by components such as the scheduler, kubelet, controllers, and API server. In troubleshooting, Events are usually the first place to look when a pod is pending, cannot mount a volume, fails a probe, pulls an image slowly, gets evicted, or restarts before the application can write useful logs.

```
┌──────────────────────────────────────────────────────────────┐
│                   KUBERNETES EVENTS                           │
│                                                               │
│   Events are generated by:                                    │
│   • Scheduler (scheduling decisions)                         │
│   • kubelet (container lifecycle)                            │
│   • Controllers (resource management)                        │
│   • API server (API operations)                              │
│                                                               │
│   Event Types:                                                │
│   • Normal:  Informational, things working as expected       │
│   • Warning: Something unexpected, might need attention      │
│                                                               │
│   Important: Events expire after ~1 hour by default!         │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

The most important limitation is retention. The default API server event TTL is one hour (`--event-ttl` on kube-apiserver), which means events are designed for near-real-time diagnosis rather than weekend forensics. If a batch job failed two days ago and no event export pipeline exists, `kubectl get events` may truthfully return nothing even though Kubernetes emitted useful warnings at the time. That is why production observability stacks often ship events into a log platform or event-specific collector before the API server garbage-collects them.

```bash
# All events in current namespace
kubectl get events

# All events cluster-wide
kubectl get events -A

# Sort by time (most recent last)
kubectl get events --sort-by='.lastTimestamp'

# Sort by time (most recent first)
kubectl get events --sort-by='.lastTimestamp' | tac

# Filter by type
kubectl get events --field-selector type=Warning

# Events for specific object
kubectl get events --field-selector involvedObject.name=<pod-name>

# Watch events in real-time
kubectl get events -w
```

**Pause and predict:** A pod was created three days ago and has been restarting since then. Which observations might still be visible, and which early observations might be gone?

<details>
<summary>Reveal the time boundary</summary>

Recent restart, backoff, probe, or image events may remain if they are still emitted, while the original scheduling and creation events may have aged out. Use the age column to distinguish the latest repetition from the beginning of the incident.

</details>

Compare the remaining timeline with current pod state before deciding whether it explains the initial failure or only its continuing symptoms.

| Reason | Type | What It Means |
|--------|------|---------------|
| Scheduled | Normal | Pod assigned to node |
| Pulled | Normal | Image successfully pulled |
| Created | Normal | Container created |
| Started | Normal | Container started |
| Killing | Normal | Container being terminated |
| FailedScheduling | Warning | Couldn't find suitable node |
| FailedMount | Warning | Volume mount failed |
| Unhealthy | Warning | Probe failed |
| BackOff | Warning | Container crashing, backing off |
| FailedCreate | Warning | Controller couldn't create pod |
| Evicted | Warning | Pod evicted from node |
| OOMKilling | Warning | Container killed for OOM |

`kubectl describe` remains valuable because it places object state, configuration, and related events in one view. For a pending pod, the Events section often tells you whether the scheduler lacked CPU, memory, matching node labels, tolerations, or a bound volume. For a running-but-unhealthy pod, describe output can connect probe settings to `Unhealthy` events, showing whether a restart loop is caused by application crashes or by kubelet killing a container that fails liveness checks.

```bash
# Events appear in describe output
kubectl describe pod <pod>
# Look for the Events section at the bottom

kubectl describe node <node>
# Shows node-level events

kubectl describe pvc <pvc>
# Shows volume binding events
```

Events and logs answer different questions. Logs tell you what a process wrote from inside a container, while Events tell you what Kubernetes components observed from outside that process. A pending pod has no useful application logs because the container has not started, but it can have rich scheduling Events. A crashing pod may have both: Events can show the restart and backoff behavior, while previous logs explain what the process did before termination.

## Resource Metrics: `kubectl top`, Metrics Server, and Pressure Signals

Resource metrics are recent measurements of CPU and memory usage, not historical graphs and not capacity planning by themselves. In a Kubernetes 1.35 cluster, `kubectl top` talks to the `metrics.k8s.io` API, which is normally served by Metrics Server. Metrics Server scrapes the kubelet resource endpoint on each node, aggregates current usage, and exposes a lightweight API that supports quick operational checks and autoscaling inputs, but it is not a full monitoring database.

```
┌──────────────────────────────────────────────────────────────┐
│                   METRICS SERVER                              │
│                                                               │
│   Nodes                    Metrics Server                     │
│   ┌───────────────────┐   ┌──────────────┐                   │
│   │ kubelet           │───│ Collects     │                   │
│   │ /metrics/resource │   │ aggregates   │                   │
│   └───────────────────┘   │ exposes      │                   │
│                           └──────┬───────┘                   │
│                                  │                           │
│                           metrics.k8s.io API                  │
│                                  │                           │
│                                  ▼                           │
│                           kubectl top                        │
│                                                               │
│   Without Metrics Server → kubectl top fails                 │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Because `kubectl top` depends on an aggregated API, a failure does not automatically mean the node stopped measuring resources. It may mean Metrics Server is not installed, the APIService registration is unavailable, TLS or kubelet authentication is failing, or RBAC blocks the request. The fastest check is to inspect the Metrics Server pod and the APIService registration before chasing application resource limits.

```bash
# Check if Metrics Server is installed
kubectl -n kube-system get pods | grep metrics-server

# Check metrics API
kubectl get apiservices | grep metrics

# If not installed, top commands will fail
kubectl top nodes  # Error: Metrics API not available
```

`kubectl top` is deliberately small and immediate. It helps you identify hot pods, compare nodes, and decide whether a failure could be caused by memory pressure, CPU throttling, or extreme imbalance. It does not tell you what happened last night, and it does not replace Prometheus, OpenTelemetry, or a vendor monitoring platform for long-term trend analysis. Use it as a fast current-state instrument during diagnosis, especially on the CKA exam where built-in tools matter.

```bash
# Node resource usage
kubectl top nodes

# Pod resource usage (current namespace)
kubectl top pods

# Pod resource usage (all namespaces)
kubectl top pods -A

# Sort by CPU
kubectl top pods --sort-by=cpu

# Sort by memory
kubectl top pods --sort-by=memory

# Per-container usage
kubectl top pods --containers

# Specific pod
kubectl top pod <pod-name>
```

The units in `kubectl top` are compact but precise. CPU is usually shown in millicores, where `100m` is one tenth of a core and `1000m` is one full core. Memory is often shown in binary units such as `Mi` and `Gi`. The measurement becomes meaningful only when you compare it with requests, limits, node allocatable capacity, and the symptom you are investigating.

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                   METRIC INTERPRETATION                                                    │
│                                                                                            │
│   NAME         CPU(cores)   MEMORY(bytes)                                                  │
│   my-pod       100m         256Mi                                                          │
│                                                                                            │
│   CPU: 100m = 100 millicores = 0.1 CPU core                                                │
│        1000m = 1 core                                                                      │
│                                                                                            │
│   Memory: Mi = mebibytes (1024 * 1024 bytes)                                               │
│           Gi = gibibytes                                                                   │
│                                                                                            │
│   Compare against requests/limits:                                                         │
│   usage above requests: under-requested; scheduling/QoS + eviction risk under node pressure│
│   memory near/above limit: OOMKilled                                                       │
│   CPU at limit: throttled (not killed)                                                     │
│                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

Before running this, what output do you expect when a pod uses more CPU than its request but less than its limit? CPU requests influence scheduling, while CPU limits influence throttling, so a pod can legitimately use more than its request after it starts if spare CPU is available. Memory behaves differently because exceeding the memory limit can terminate the container, which is why memory spikes often need correlation with restart counts, `OOMKilled` status, and previous logs.

```bash
# Compare actual usage vs requests
# Step 1: Get requests
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].resources.requests}'

# Step 2: Get actual usage
kubectl top pod <pod>

# If actual >> requests, pod is under-requested
# If actual << requests, pod is over-requested
```

Metrics become especially useful when you pair them with Events. A pod that is pending with `FailedScheduling` may not need logs at all; it may need request tuning or additional node capacity. A running pod with high memory and a restart reason of `OOMKilled` needs previous logs and limit review. A pod with high CPU and slow responses might be throttled even though the process is not crashing, which changes the next action from "read stack trace" to "compare CPU limits, latency, and throttling metrics."

## Node-Level and Control Plane Logs

Most day-to-day troubleshooting should start with Kubernetes APIs, because they preserve object context and avoid unnecessary node access. Node-level logs matter when the API server is unavailable, kubelet behavior is the suspected failure, container runtime operations are broken, or the evidence you need is below the pod abstraction. On Linux nodes, container logs are typically reachable through `/var/log/containers`, while kubelet and container runtime logs are usually available through `journalctl` when systemd manages those services.

```
┌──────────────────────────────────────────────────────────────┐
│                NODE LOG LOCATIONS                             │
│                                                               │
│   Container logs (symlinks):                                  │
│   /var/log/containers/<pod>_<ns>_<container>-<id>.log        │
│                                                               │
│   Pod logs (actual files):                                    │
│   /var/log/pods/<ns>_<pod>_<uid>/                            │
│                                                               │
│   kubelet logs:                                               │
│   journalctl -u kubelet                                       │
│                                                               │
│   Container runtime logs:                                     │
│   journalctl -u containerd                                    │
│   journalctl -u docker (if using docker)                     │
│                                                               │
│   System logs:                                                │
│   /var/log/syslog or /var/log/messages                       │
│   journalctl                                                  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Direct node inspection has higher operational risk than `kubectl` because you are leaving the normal API workflow. You need node access, you need to know the operating system layout, and you must avoid mutating files while investigating. Still, it is a legitimate fallback when `kubectl logs` cannot reach kubelet, when the API server is down, or when a node-specific issue such as disk pressure, kubelet certificate failure, or container runtime errors prevents normal object-level diagnosis.

```bash
# SSH to node first
ssh <node>

# Container logs directly
ls /var/log/containers/
tail -f /var/log/containers/<pod>*.log

# kubelet logs
journalctl -u kubelet -f
journalctl -u kubelet --since "10 minutes ago"
journalctl -u kubelet | grep -i error

# Container runtime logs
journalctl -u containerd -f

# System messages
dmesg | tail -50
journalctl -xe
```

Control plane component logs depend on how the cluster was installed. In kubeadm-style clusters, core control plane components often run as static pods in `kube-system`, which makes their logs visible through `kubectl logs` when the API server is healthy enough to answer. In other distributions, components may be systemd services, managed containers, or hosted control plane processes that require provider-specific access. The diagnostic principle stays the same: find the component boundary first, then use the logging mechanism for that boundary.

```bash
# If using static pods (kubeadm)
# Logs available via kubectl
kubectl -n kube-system logs kube-apiserver-<node>
kubectl -n kube-system logs kube-scheduler-<node>
kubectl -n kube-system logs kube-controller-manager-<node>
kubectl -n kube-system logs etcd-<node>

# Or directly on node via journalctl (if systemd services)
journalctl -u kube-apiserver
journalctl -u kube-scheduler
journalctl -u kube-controller-manager
journalctl -u etcd
```

Node logs also explain why log rotation matters. The kubelet manages container log files according to its configuration, which protects nodes from unbounded disk growth but also means old log content can disappear locally. If a noisy application fills logs quickly, your `kubectl logs --previous` window may be shorter than you expect. For production systems, node-local log retention should be treated as a buffer until logs are shipped to durable storage, not as the system of record.

## Correlating Logs, Events, and Metrics into a Workflow

Troubleshooting becomes faster when you ask one evidence question at a time. Start with the object state and recent Events because they tell you whether Kubernetes could schedule, pull, mount, start, and keep the container alive. Then inspect current or previous container logs depending on restart behavior. Use metrics when the symptom could be pressure, throttling, or imbalance. Finally, move to node-level logs only when the API view is missing, contradictory, or below the layer where the problem lives.

```
┌──────────────────────────────────────────────────────────────┐
│              LOG ANALYSIS WORKFLOW                            │
│                                                               │
│   1. Start with events                                        │
│      kubectl describe <resource> | grep -A 20 Events         │
│                                                               │
│   2. Check recent events cluster-wide                        │
│      kubectl get events --sort-by='.lastTimestamp' | tail    │
│                                                               │
│   3. Get container logs                                       │
│      kubectl logs <pod>                                       │
│      kubectl logs <pod> --previous  (if crashed)             │
│                                                               │
│   4. Filter for errors                                        │
│      kubectl logs <pod> | grep -i error                      │
│      kubectl logs <pod> | grep -i exception                  │
│                                                               │
│   5. Check timing                                             │
│      kubectl logs <pod> --timestamps --since=10m             │
│                                                               │
│   6. Check related components                                 │
│      If pod issues: check node                               │
│      If network issues: check CNI, kube-proxy                │
│      If DNS issues: check CoreDNS                            │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Filtering is useful only after you understand the stream you are filtering. A `grep -i error` command can surface important lines, but it can also hide the context line before the error or miss applications that log failures as `fatal`, `exception`, `panic`, or structured JSON fields. Use filtering to reduce noise, not to outsource judgment. When timing matters, add `--timestamps` and narrow with `--since` or `--since-time` before searching.

```bash
# Search for errors
kubectl logs <pod> | grep -i error
kubectl logs <pod> | grep -i exception
kubectl logs <pod> | grep -i fatal

# Exclude noise
kubectl logs <pod> | grep -v "INFO"
kubectl logs <pod> | grep -v "health check"

# Complex filters
kubectl logs <pod> | grep -E "error|warning|failed"

# With timestamps and filtering
kubectl logs <pod> --timestamps | grep "2024-01-15T10:3"

# Count error occurrences
kubectl logs <pod> | grep -c error
```

Multi-pod analysis is a correlation problem, not just a larger text stream. When several replicas fail, you want to know whether all pods fail the same way, whether only one node is affected, whether one version or label set is involved, and whether sidecars report a different sequence than application containers. Use controller and label selection for breadth, then narrow to a representative pod for precise timestamps and previous logs.

```bash
# Logs from all pods in deployment (--all-pods=true required)
kubectl logs deployment/<name> --all-pods=true --all-containers=true

# Aggregate logs from multiple pods with labels
kubectl logs -l app=frontend --all-containers

# Using stern (not built-in, but useful)
# stern <pod-name-pattern>

# Workaround: loop through pods
for pod in $(kubectl get pods -l app=nginx -o name); do
  echo "=== $pod ==="
  kubectl logs $pod --tail=5
done
```

Correlating Events and logs is where many investigations become decisive. If an Event says a liveness probe failed at a particular time, logs around that timestamp can show whether the application was still booting, waiting on a database, rejecting traffic, or deadlocked. If an Event says a container was killed, previous logs can show what happened before termination, while metrics can show whether memory pressure made the kill predictable.

```bash
# Get event time
kubectl get events --field-selector involvedObject.name=my-pod

# Note the timestamp, then check logs around that time
kubectl logs my-pod --since-time="2024-01-15T10:30:00Z"

# Or use relative time
kubectl logs my-pod --since=5m
```

Which approach would you choose here and why: start by following live logs, or first sort recent Warning Events across the namespace? If the symptom is "new pod never becomes Ready," Events usually have higher signal because they reveal pull, mount, scheduling, and probe failures that happen outside the app process. If the symptom is "Ready pod returns errors under traffic," live logs plus timestamps may be the better first move.

## Monitoring Patterns for Exam and Operations

A quick cluster health pass should be small enough to run under pressure and broad enough to catch obvious failures. Start with nodes, non-running pods, current metrics, and warning Events. This does not replace deeper observability, but it gives you a consistent baseline before you chase a single component. On the CKA exam, this habit also prevents wasting time inside application logs when the real failure is a node condition or a scheduling constraint.

```bash
# Quick cluster health check
kubectl get nodes
kubectl get pods -A | grep -v Running
kubectl top nodes
kubectl get events -A --field-selector type=Warning

# Create a simple monitoring script
watch -n 5 'kubectl get pods -A | grep -v Running | grep -v Completed'
```

Resource pressure detection needs both object status and current measurements. Node conditions such as `MemoryPressure`, `DiskPressure`, and `PIDPressure` explain why kubelet may evict pods or reject work. Top commands show current consumers, while pending pods can reveal requests that no node can satisfy. The goal is to separate an application fault from a cluster capacity or node health fault before you change the wrong manifest.

```bash
# Check for node pressure
kubectl describe nodes | grep -E "MemoryPressure|DiskPressure|PIDPressure"

# Check for pods using excessive resources
kubectl top pods -A --sort-by=memory | head -10
kubectl top pods -A --sort-by=cpu | head -10

# Check for pending pods (might indicate resource shortage)
kubectl get pods -A --field-selector=status.phase=Pending
```

Temporary debug pods are useful when you need tools inside the cluster network, but they should be created deliberately. Use `--rm` so the pod is deleted when the shell exits, and use `--restart=Never` so you create a bare Pod rather than a controller-managed workload. Choose the namespace and service account carefully, because a debug pod running with the wrong identity can prove only that the wrong identity has access.

```bash
# Create debug pod with networking tools
kubectl run debug --image=nicolaka/netshoot --rm -it --restart=Never -- bash

# Simple debug pod
kubectl run debug --image=busybox:1.36 --rm -it --restart=Never -- sh

# Debug with specific service account
kubectl run debug --image=busybox:1.36 --rm -it --restart=Never --overrides='{"spec":{"serviceAccountName":"<sa>"}}' -- sh

# Debug in specific namespace
kubectl run debug -n <namespace> --image=busybox:1.36 --rm -it --restart=Never -- sh
```

The best monitoring pattern is a decision loop: observe, form a hypothesis, run the smallest command that can disprove it, then update your path. If the hypothesis is "the app crashed," previous logs are high value. If it is "the pod never scheduled," Events and describe output matter more. If it is "the node is unhealthy," node conditions and kubelet logs are more relevant than application output.

## Worked Example: Building an Evidence Timeline

Exercise scenario: a namespace named `payments` contains a Deployment whose new pods are not becoming healthy after a configuration change. The service is still partially available because older replicas remain ready, but the rollout is stalled and the on-call engineer needs to decide whether to roll back, fix configuration, or change resource settings. You are not told the root cause in advance, because the skill being practiced is evidence sequencing rather than command memorization.

The first observation is the controller state, not the application log. A stalled Deployment tells you that some desired replicas are unavailable, but it does not explain whether the pods failed scheduling, image pull, startup, readiness, or steady-state execution. Starting with `kubectl describe deployment` and `kubectl get pods -n payments -o wide` gives you object names, node placement, restart counts, and status phases. That prevents a common mistake: reading one pod log and assuming it represents the whole rollout.

Suppose the pod table shows two new pods in `Running` with restart counts increasing and one older pod still `Running` with zero restarts. That immediately narrows the problem toward the new ReplicaSet or configuration, not a universal node outage. The next useful move is to inspect one failing pod with `kubectl describe pod`, because the Events section can reveal whether kubelet is killing the container due to probes, whether the container exits on its own, or whether resource enforcement is involved.

The describe output shows repeated `BackOff` Events and a container state of `Waiting` with reason `CrashLoopBackOff`. At this point, current logs are less useful than previous logs, because the container has already died at least once. You run `kubectl logs -n payments <pod> --previous` and see a configuration validation error near startup. That single line is useful, but it is not yet the full timeline, because you still need to connect it to the rollout and confirm that the same error appears on all new replicas.

The next step is to query logs from the Deployment or label selector with a small tail and timestamps. If all new pods show the same validation error shortly after startup, you can treat the failure as a release configuration issue rather than a node-specific runtime issue. If only one pod shows the error and the others fail differently, the investigation branches. This is why broad selection and narrow inspection should alternate: breadth tells you pattern, while detail tells you mechanism.

Now imagine that previous logs show no application error, but `describe pod` shows `Unhealthy` Events from a liveness probe. That changes the diagnosis. The application might be slow to start, the probe path might be wrong, or the dependency checked by the probe might be unavailable. In that branch, you inspect readiness and liveness settings, compare timestamps with application startup logs, and decide whether the probe is detecting a real failure or killing a process that would have become healthy with a longer startup window.

Resource metrics create a third branch. If the pod restarts and Events show `OOMKilling`, `kubectl top pod` may or may not catch the spike because the container dies quickly and metrics are sampled. You still compare requests and limits, but you do not rely on `kubectl top` alone. Previous logs, termination reason, and Events carry the strongest evidence for a memory kill, while Metrics Server provides current context for surviving pods and node-level pressure.

Node placement can also change the path. If every failing pod lands on the same node, check the node's conditions, kubelet Events, and container runtime logs before blaming the application. A bad image cache, disk pressure, broken CNI state, or kubelet problem can produce symptoms that look like application instability from the Deployment view. The pod table's `NODE` column is therefore not decoration; it is a correlation field that helps separate workload problems from infrastructure problems.

Timing is the thread that ties these observations together. A useful timeline might say: the new ReplicaSet created pods at 10:12, kubelet started containers at 10:13, the application logged a configuration error at 10:13, kubelet recorded `BackOff` at 10:14, and the Deployment stayed unavailable afterward. That sequence supports a configuration rollback. A different timeline, where scheduling failed before any container started, would support a placement or capacity fix instead.

**Pause and predict:** The application team asks for "the logs from the failed rollout." What would you collect, and how would you label it so they can reconstruct the timeline?

<details>
<summary>Reveal the evidence set</summary>

Collect previous logs for each failing container, current logs for surviving replicas, relevant Events sorted by time, and the Deployment or ReplicaSet revision. Label each item with its pod, container, and timestamp so the handoff identifies what failed and when.

</details>

Group the captured material by workload and time, then explain which observations support the diagnosis and which gaps still need investigation.

This example also explains why log aggregation does not eliminate `kubectl` skills. A central log system may preserve history and improve search, but Kubernetes object state is still the fastest way to map a symptom to pods, containers, nodes, restart reasons, and Events. Conversely, `kubectl` may show only recent or node-local evidence, so durable logging remains essential for delayed investigations. Effective operators understand both views and move between them deliberately.

When the evidence points to configuration, you still verify the fix with observability rather than assuming the rollout is healed. After applying a corrected ConfigMap, Secret, or Deployment environment variable, watch Events for new failures, read the first startup logs from the replacement pods, and confirm readiness. If metrics were part of the symptom, compare resource usage again after the fix. The closeout is not "command returned zero"; the closeout is "the previous failure mode no longer appears, and the workload reaches the expected state."

When the evidence points to resources, the safest next step depends on whether the issue is scheduling, runtime memory, or CPU saturation. A `Pending` pod with `FailedScheduling` due to insufficient memory needs request changes or capacity, while a running pod killed with `OOMKilled` needs limit and memory behavior review. A CPU-heavy pod with no restarts may need limit adjustment, horizontal scaling, or application profiling. These cases all involve "resources," but each has a different first command and a different responsible layer.

When the evidence points to node health, preserve the Kubernetes view before going deeper. Capture pod placement, node conditions, Warning Events, and affected workload names, then inspect kubelet or container runtime logs if needed. Node logs can be noisy, and without the object context you may not know which errors matter. The sequence matters because it lets you return from node-level evidence to a specific pod, namespace, and workload instead of collecting unrelated system messages.

The same timeline habit applies on the CKA exam, even though the environment is smaller. You are often rewarded for choosing the shortest valid evidence path: Events for scheduling and mounts, previous logs for crashes, `kubectl top` for current pressure, and node journals for kubelet or runtime issues. The exam does not require a production observability platform, but it does require you to know why a command is relevant before running it. That keeps you fast without being random.

The final lesson from the scenario is that observability data has freshness and scope. Events are fresh but short-lived, container logs are scoped to a container instance, metrics are recent and sampled, and node logs are local to a machine. A diagnosis is stronger when it names those limits directly. Instead of saying "the logs prove the deployment is broken," say "the previous logs for all new app containers show the same startup validation error after the new ReplicaSet was created." That statement is specific enough to act on.

You should also think about audience when collecting evidence. An application developer often needs the exact exception, environment variable, or timestamped request failure. A platform engineer may need pod placement, node conditions, kubelet Events, and whether the same symptom appears across namespaces. A release manager may need a clear yes-or-no recommendation about rollback. The same raw observability data can support all three conversations, but only if you preserve enough context to connect evidence to action.

Good evidence notes are compact and reproducible. Record the namespace, pod name, container name, command used, and the time window you inspected. If you used `--previous`, say so explicitly, because that distinguishes a terminated instance from the current one. If you filtered logs, keep the unfiltered command available as well, because another reviewer may need surrounding lines. This discipline matters during handoff, when a teammate must trust your conclusion without rerunning every command from memory.

There is a subtle difference between "monitoring" and "debugging" in this module. Monitoring asks whether the system is healthy now and whether resource usage looks abnormal. Debugging asks why a specific symptom occurred. `kubectl top nodes` can support monitoring by showing current pressure, while previous logs support debugging by explaining a terminated container. Strong troubleshooters combine them, but they do not confuse a current measurement with a historical cause.

The workflow also protects against overfitting to familiar failures. If you recently fixed an image pull problem, you may be tempted to assume the next rollout failure has the same cause. The evidence loop forces you to check state, Events, logs, metrics, and placement before committing to a fix. That is slower than guessing for the first minute, but faster than rolling back a healthy image when the real issue is a missing Secret, a failed mount, or a too-strict probe.

Finally, treat cleanup as part of observability practice. Temporary debug pods, lab namespaces, and ad hoc scripts can create noise that confuses later investigations if they remain in the cluster. Deleting the lab namespace after this exercise is not just tidiness; it keeps future `kubectl get pods -A`, Events, and metrics output focused on real workloads. Clean environments make signal easier to find, which is exactly what logging and monitoring are supposed to provide.

## Patterns & Anti-Patterns

The patterns below are designed for operational use, where speed matters but premature certainty is dangerous. Each pattern works because it makes the evidence boundary explicit. Logs, Events, metrics, and node journals all describe different layers, so the right pattern is usually the one that narrows the layer before it narrows the command.

| Pattern | When to Use | Why It Works | Scaling Consideration |
|---------|-------------|--------------|-----------------------|
| Events-first triage | Pods are `Pending`, `ContainerCreating`, failing probes, or recently restarted | Kubernetes components explain lifecycle failures before the app can log them | Export Events for retention because API-server event TTL is short |
| Previous-log crash analysis | Containers restart quickly or show `CrashLoopBackOff` | The last terminated instance contains the failure that the current instance may not have reached | Include `-c <container>` in multi-container pods to avoid reading the wrong restart |
| Timestamp correlation | Events, logs, and metrics all show symptoms near the same period | Matching time windows separates cause from follow-on noise | Use consistent time zones and ship logs centrally for long investigations |
| Sidecar file tailing | Legacy apps write to files and cannot be changed immediately | A shared volume plus tailer converts file writes into kubelet-captured `stdout` | Plan migration to direct structured `stdout` to reduce sidecar overhead |

Anti-patterns usually come from treating one observable as the whole truth. A log stream can be empty because the container never started, not because nothing failed. A `kubectl top` error can mean Metrics Server is down, not that the cluster has no resource usage. A lack of Events can mean retention expired, not that Kubernetes saw nothing. The safer alternative is to name what the tool can and cannot prove before acting on it.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Following live logs before checking object state | You miss scheduling, image pull, mount, or probe failures outside the process | Run `kubectl describe` and recent Warning Events first for lifecycle issues |
| Reading only the first container in a pod | Sidecar, init, or proxy failures stay invisible | List containers and use `-c` or `--all-containers=true` intentionally |
| Treating Events as permanent history | Weekend or delayed incident analysis loses the original clues | Export Events to a durable log system and capture timelines during incidents |
| Using node SSH as the first diagnostic step | You lose object context and increase operational risk | Start with Kubernetes APIs, then fall back to node logs when the API layer is insufficient |

## Decision Framework

Use this framework when the symptom is clear but the next command is not. The first decision is whether the container has started. If it has not, logs are secondary because there is no meaningful process output. The second decision is whether the container restarted. If it did, previous logs are more useful than current logs. The third decision is whether the symptom could be caused by resource pressure. If it could, metrics and node conditions should be checked before changing application code.

| Symptom | First Evidence Source | Next Evidence Source | Common Fix Direction |
|---------|----------------------|----------------------|----------------------|
| Pod is `Pending` | `kubectl describe pod` Events | Node allocatable resources, PVC status, taints, affinity | Adjust requests, storage binding, tolerations, or placement rules |
| Pod is `CrashLoopBackOff` | `kubectl logs --previous` | Events, restart reason, probes, resource limits | Fix app startup, configuration, dependency access, or limits |
| Pod is `Running` but not `Ready` | Events and probe output | Current logs with timestamps | Fix readiness endpoint, startup timing, dependency checks, or probe configuration |
| `kubectl top` fails | APIService and Metrics Server pod | Metrics Server logs and kubelet access | Install, repair, or reconfigure Metrics Server |
| Node shows pressure | Node describe conditions | Top pods sorted by CPU or memory, kubelet logs | Tune requests and limits, evict noisy workloads, or add capacity |

```
┌───────────────────────────┐
│ What is the visible state? │
└──────────────┬────────────┘
               │
     ┌─────────▼─────────┐
     │ Container started? │
     └───────┬─────┬─────┘
             │yes  │no
             │     ▼
             │  Check Events, scheduling, image pull, mounts
             ▼
   ┌─────────────────────┐
   │ Restarted recently? │
   └───────┬─────┬───────┘
           │yes  │no
           │     ▼
           │  Check current logs with timestamps
           ▼
   Check previous logs, restart reason, Events
           │
           ▼
   If pressure is plausible, compare top metrics with requests and limits
```

The framework is intentionally conservative. It avoids "read logs" as a universal first step because Kubernetes failures often happen before the application owns control. It also avoids treating metrics as a final answer, because a hot pod might be a symptom of retries caused by a dependency failure. The best next command is the one that can eliminate a branch of the decision tree with the least noise.

## Did You Know?

- **Kubernetes captures `stdout` and `stderr` by convention**: the kubelet exposes container streams from node log files, which is why applications that only write private files need a bridge such as a sidecar.
- **Events have short default retention**: the API server's event TTL defaults to one hour, so cluster Events should be exported if your team needs incident timelines after the immediate troubleshooting window.
- **`kubectl top` depends on an aggregated API**: the command needs Metrics Server and the `metrics.k8s.io` API, so a failure can be an observability pipeline problem rather than an application problem.
- **Log rotation is node-local**: kubelet settings such as maximum log size and file count protect disk space, but they also mean node-local logs are not durable incident archives.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Forgetting `--previous` during `CrashLoopBackOff` | The current container instance starts cleanly and hides the line that killed the previous instance | Use `kubectl logs <pod> --previous`, and add `-c <container>` for multi-container pods |
| Treating an empty log as proof that nothing happened | Pending pods, image pull failures, and mount failures can occur before application code runs | Check `kubectl describe pod` and Warning Events before relying on logs |
| Reading the wrong container in a pod | Sidecars, init containers, and proxies create multiple log streams under one pod name | List container names and choose `-c <container>` or `--all-containers=true` deliberately |
| Ignoring event retention | Events are short-lived and may disappear before delayed incident analysis begins | Export Events to durable logging and capture event output during the incident |
| Assuming `kubectl top` is built in everywhere | Metrics Server is a separate component and can be absent or unhealthy | Check the Metrics Server pod and the `metrics.k8s.io` APIService before diagnosing app usage |
| Comparing metrics only to limits | Requests affect scheduling, limits affect enforcement, and each answers a different question | Compare current usage against requests, limits, node capacity, and restart reasons |
| Starting with node SSH for normal pod failures | Direct node access loses Kubernetes object context and can distract from simple lifecycle clues | Start with Events, describe output, and logs; use node logs when the API view is insufficient |
| Filtering logs too early | `grep` can remove timing context or miss differently named failure messages | Narrow by time first, then search for error families such as exception, fatal, failed, and panic |

## Quiz

<details>
<summary>Question 1: Your team deploys a new image and the pod enters `CrashLoopBackOff`. `kubectl logs my-app` shows only a startup banner. What do you check next, and why?</summary>

Use `kubectl logs my-app --previous`, adding `-c <container>` if the pod has more than one container. The normal logs command reads the current container instance, which may have only started and not yet reached the failing line. `--previous` asks kubelet for the last terminated instance, where the stack trace, missing configuration message, or fatal startup error is usually present. After reading it, correlate the timestamp with Events so you can separate application failure from probe or resource enforcement.

</details>

<details>
<summary>Question 2: A pod is stuck in `Pending`, and a junior administrator wants to run `kubectl logs` to find the application complaint. What should you do instead?</summary>

Start with `kubectl describe pod <pod>` and recent Warning Events for the namespace. A pending pod usually has not started a container, so there may be no application output to retrieve. Events can show `FailedScheduling`, unbound PVCs, taints, affinity mismatches, or insufficient CPU and memory. Once the pod reaches a container state, logs become useful, but before that the control plane is the evidence source.

</details>

<details>
<summary>Question 3: `kubectl top pods -n production` returns an error that metrics are unavailable. Your kubeconfig and RBAC are correct. What component is the likely focus?</summary>

Inspect Metrics Server and the `metrics.k8s.io` APIService before changing application manifests. `kubectl top` does not read pod cgroups directly; it queries the aggregated metrics API served by Metrics Server. Metrics Server must be running, able to scrape kubelet resource endpoints, and registered as an available APIService. If that pipeline is broken, `kubectl top` fails even though workloads are consuming CPU and memory.

</details>

<details>
<summary>Question 4: A pod has a main application container and a log-forwarder sidecar. You suspect both are involved in a failure. How do you avoid reading only half the evidence?</summary>

First list the containers with `kubectl get pod <pod> -o jsonpath='{.spec.containers[*].name}'`, then read the relevant streams with `kubectl logs <pod> -c <container>` or use `--all-containers=true` when correlation matters. The pod name alone does not guarantee that the stream you see belongs to the failing component. Sidecars can fail authentication, proxies can reject traffic, and init containers can leave setup clues that the main container never repeats. Container selection keeps the investigation tied to the component boundary.

</details>

<details>
<summary>Question 5: A batch job failed two days ago, but `kubectl get events` returns no useful entries. Does that prove Kubernetes emitted no Events?</summary>

No. Events are short-lived Kubernetes objects, and the default event TTL is one hour unless the API server is configured differently. By the time you investigate a two-day-old failure, the original scheduling, pull, mount, or probe Events may have been garbage-collected. For long incident timelines, ship Events to durable logging or observability storage while they are fresh. For the current investigation, rely on persisted application logs, job status, pod termination state, and external monitoring.

</details>

<details>
<summary>Question 6: A pod is running but slow, `kubectl top pod` shows high CPU, and there are no restarts. What is the next diagnostic direction?</summary>

Compare current CPU usage with the pod's requests and limits, then check whether throttling or saturation explains the symptom. High CPU without restarts points less toward a crash and more toward performance, limits, dependency retries, or load imbalance. Events may still matter if probes are failing, but previous logs are unlikely to help unless the container restarted. The useful path is to connect metrics, latency, limits, and application logs for the same time window.

</details>

<details>
<summary>Question 7: The API server is temporarily unreachable, but you have SSH access to the node running a critical pod. Where can you look for container logs, and what caution applies?</summary>

On the node, inspect `/var/log/containers/` for symlinks named with the pod, namespace, container, and container ID, then follow the matching file carefully. Those files are managed by the kubelet and container runtime, so they are useful when the normal API path is unavailable. Avoid editing or deleting node log files during diagnosis, because you can destroy evidence or interfere with rotation. When API access returns, reconcile the node evidence with Kubernetes object state.

</details>

## Hands-On Exercise: Log and Metric Analysis

Exercise scenario: you will create a namespace with one pod that continuously emits mixed info and error messages, one pod that repeatedly crashes, and an optional legacy-style file logger. The exercise forces you to use current logs, previous logs, filtering, Events, and metrics in a controlled environment before you need them during an exam or production incident. Run these commands in a disposable Kubernetes 1.35+ cluster where creating a namespace and temporary pods is allowed.

### Setup

```bash
# Create test namespace
kubectl create ns logging-lab

# Create a pod that generates logs
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: log-generator
  namespace: logging-lab
spec:
  containers:
  - name: logger
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      i=0
      while true; do
        echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Log message $i"
        if [ $((i % 5)) -eq 0 ]; then
          echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Something went wrong at iteration $i" >&2
        fi
        i=$((i+1))
        sleep 2
      done
EOF

# Create a crashy pod for --previous demo
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crashy-pod
  namespace: logging-lab
spec:
  containers:
  - name: crasher
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      echo "Starting up..."
      sleep 5
      echo "About to crash!"
      exit 1
EOF

# Wait for log-generator to be ready before proceeding
kubectl wait --for=condition=Ready pod/log-generator -n logging-lab --timeout=60s
```

### Task 1: Basic Log Operations

Use this task to prove that you can read the current stream, follow it briefly, limit the output, and add timestamps. Stop following with `Ctrl+C` after you have seen several lines; the goal is to confirm the stream and then move to targeted evidence gathering, not to watch logs indefinitely.

```bash
# View logs
kubectl logs -n logging-lab log-generator

# Follow logs
kubectl logs -n logging-lab log-generator -f
# (Ctrl+C to stop)

# Last 10 lines
kubectl logs -n logging-lab log-generator --tail=10

# With timestamps
kubectl logs -n logging-lab log-generator --tail=10 --timestamps
```

<details>
<summary>Solution notes for Task 1</summary>

You should see a repeating mix of `INFO` messages and occasional `ERROR` messages from the same container. The `--tail` flag should reduce the output to a small recent window, and `--timestamps` should add Kubernetes log timestamps before each line. If the pod is not ready yet, wait a few seconds and check `kubectl describe pod -n logging-lab log-generator` before assuming the log command is broken.

</details>

### Task 2: Filtering Logs

Filtering teaches you to reduce noise after you have confirmed the stream. Run the error searches, count the matching lines, and then exclude the info lines. Notice that each pipeline answers a different question: one finds examples, one measures rough frequency, and one shows everything that is not routine info output.

```bash
# Find errors only
kubectl logs -n logging-lab log-generator | grep ERROR

# Count errors
kubectl logs -n logging-lab log-generator | grep -c ERROR

# Exclude INFO messages
kubectl logs -n logging-lab log-generator | grep -v INFO
```

<details>
<summary>Solution notes for Task 2</summary>

The error count should grow over time because the pod emits an error every few iterations. If the count is zero, the pod may have just started or your command may be reading the wrong namespace. In a real incident, you would usually combine filtering with `--since` or `--since-time` so the count reflects the incident window instead of the pod's whole lifetime.

</details>

### Task 3: Previous Container Logs

The crashing pod is designed to show why the current stream and the previous stream are different. Watch the pod until you see restarts or `CrashLoopBackOff`, then retrieve the previous instance. This is the same move you use when an application starts, prints a banner, exits, and restarts too quickly for the current log stream to reveal the fatal line.

```bash
# Wait for crashy-pod to crash and restart
kubectl get pod -n logging-lab crashy-pod -w
# (Press Ctrl+C to stop once you see CrashLoopBackOff)

# When it shows CrashLoopBackOff or restarts, check previous logs
kubectl logs -n logging-lab crashy-pod --previous
```

<details>
<summary>Solution notes for Task 3</summary>

The previous logs should include `Starting up...` followed by `About to crash!`. If `--previous` returns that no previous terminated container exists, wait for the first restart and try again. The key habit is to use pod status and restart count to decide whether current or previous logs match the failure instance.

</details>

### Task 4: Events Analysis

Events should show the lifecycle around the crashy pod, including creation, start, termination, and backoff behavior. Sort by timestamp so you can read the sequence rather than a random-looking table. Then use `describe` to see the Events section in context with pod status and container state.

```bash
# All events in namespace
kubectl get events -n logging-lab --sort-by='.lastTimestamp'

# Describe pod for events
kubectl describe pod -n logging-lab crashy-pod | grep -A 10 Events

# Watch for new events
kubectl get events -n logging-lab -w
```

<details>
<summary>Solution notes for Task 4</summary>

You should see Events that match the pod lifecycle and backoff behavior. The Event messages are not a replacement for application logs, but they explain what kubelet is doing from the outside. If no Events appear, confirm you are in the right namespace and remember that old Events expire, so recent activity is easier to observe than historical activity.

</details>

### Task 5: Metrics (if Metrics Server installed)

Run the metrics commands only if your lab cluster has Metrics Server installed and healthy. If they fail, treat the failure as a valid diagnostic branch: check whether Metrics Server exists, whether the metrics API is registered, and whether the cluster environment supports it. Do not rewrite application requests based on missing metrics until you know the metrics pipeline is working.

```bash
# Node metrics
kubectl top nodes

# Pod metrics
kubectl top pods -n logging-lab

# All pods by memory
kubectl top pods -A --sort-by=memory | head
```

<details>
<summary>Solution notes for Task 5</summary>

If Metrics Server is present, you should see current CPU and memory usage for nodes and pods. The numbers may be small because the lab pods are lightweight. If the command fails with a metrics API error, inspect `kubectl -n kube-system get pods | grep metrics-server` and `kubectl get apiservices | grep metrics` rather than assuming the workload has no resource usage.

</details>

### Task 6: Sidecar File Logging Challenge

This optional challenge implements the file-to-stdout bridge from the core lesson. The main container writes to a file on a shared `emptyDir`, and the sidecar tails that file to its own standard output. Query the sidecar logs, then explain why the main container's logs are less useful for file-only applications.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: file-logger
  namespace: logging-lab
spec:
  containers:
  - name: main-app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      i=0
      while true; do
        echo "$(date '+%Y-%m-%d %H:%M:%S') file log $i" >> /var/log/app.log
        i=$((i+1))
        sleep 2
      done
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log
  - name: log-tailer
    image: busybox:1.36
    command: ["sh", "-c", "touch /var/log/app.log 2>/dev/null; tail -n+1 -F /var/log/app.log"]
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log
  volumes:
  - name: shared-logs
    emptyDir: {}
EOF

kubectl wait --for=condition=Ready pod/file-logger -n logging-lab --timeout=60s
kubectl logs -n logging-lab file-logger -c log-tailer --tail=10
```

<details>
<summary>Solution notes for Task 6</summary>

The useful file log lines should appear from the `log-tailer` container, not from the main application container. This demonstrates why Kubernetes-native logging prefers direct `stdout` and `stderr`, and why a sidecar is only a bridge for legacy behavior. In production, you would also think about rotation, resource requests for the sidecar, and durable log shipping beyond the node.

</details>

### Practice Drills

The drills below preserve the fast command patterns from the original module. Run them after the main tasks until you can choose the right command from the symptom without pausing. They are intentionally short, but the reasoning behind them should now be clear from the workflow sections above.

### Drill 1: View Last N Logs (30 sec)
```bash
# Task: Show last 20 log lines
kubectl logs <pod> --tail=20
```

### Drill 2: Logs with Timestamps (30 sec)
```bash
# Task: Show logs with timestamps
kubectl logs <pod> --timestamps
```

### Drill 3: Previous Container Logs (30 sec)
```bash
# Task: Get logs from crashed container
kubectl logs <pod> --previous
```

### Drill 4: Multi-Container Logs (1 min)
```bash
# Task: Get logs from specific container
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].name}'
kubectl logs <pod> -c <container-name>
```

### Drill 5: Recent Events (30 sec)
```bash
# Task: Show events sorted by time
kubectl get events --sort-by='.lastTimestamp'
```

### Drill 6: Warning Events (30 sec)
```bash
# Task: Show only warning events
kubectl get events --field-selector type=Warning
```

### Drill 7: Node Metrics (30 sec)
```bash
# Task: Show node resource usage
kubectl top nodes
```

### Drill 8: Pod Metrics Sorted (30 sec)
```bash
# Task: Show top memory-consuming pods
kubectl top pods -A --sort-by=memory | head
```

### Card A: Two-container logs

`kubectl logs` without `-c` on a two-container pod returns one merged stream of both containers. Decide whether that claim is true before revealing the answer.

<details>
<summary>Reveal Card A</summary>

**False.** Logs are container-specific; without `-c`, the command does not automatically merge both containers. Name a container or request all containers explicitly so the evidence has a clear origin.

</details>

### Card B: Three-day-old pod

Events from pod creation three days ago are still the best record of the original schedule. Decide whether that claim is true before revealing the answer.

<details>
<summary>Reveal Card B</summary>

**False.** Early scheduling and creation Events may have expired, even when newer Events from recurring failures remain. Check timestamps and seek another retained record before treating recent Events as the original timeline.

</details>

### Card C: Failed rollout logs

The logs from a failed rollout are the current logs of the newest pod. Decide whether that claim is true before revealing the answer.

<details>
<summary>Reveal Card C</summary>

**False.** A useful handoff also includes previous logs from failing containers, current logs from surviving replicas, time-sorted Events, and the Deployment or ReplicaSet revision. The newest pod alone cannot establish the full failure sequence.

</details>

### Card D: Missing Metrics Server

`kubectl top` works even when Metrics Server is not installed. Decide whether that claim is true before revealing the answer.

<details>
<summary>Reveal Card D</summary>

**False.** `kubectl top` depends on the resource metrics pipeline, commonly supplied by Metrics Server. If it is absent, the metrics API may be unavailable, so diagnose that dependency before interpreting the command failure.

</details>

**Success Criteria**: Confirm live logs, previous container logs, event age, and why a metrics command can fail when the metrics server is absent.

- [ ] Viewed live logs with follow and stopped the stream intentionally.
- [ ] Filtered logs for errors and explained what the filter hides.
- [ ] Retrieved previous container logs from a restarting pod.
- [ ] Analyzed Events for crash, lifecycle, or backoff information.
- [ ] Used `kubectl top` when Metrics Server was available, or diagnosed why it was unavailable.
- [ ] Implemented sidecar-based logging for a file-writing application.
- [ ] Correlated logs, Events, and metrics to choose the next diagnostic action.

### Cleanup

```bash
kubectl delete ns logging-lab
```

## Learner check

> Bare `kubectl logs deployment/<name>` follows the controller relationship but streams logs from only one representative pod in that Deployment; add `--all-pods=true` when you need every replica. `kubectl logs deployment/my-deployment --all-pods=true` — `usage above requests: under-requested; scheduling/QoS + eviction risk under node pressure` — `memory near/above limit: OOMKilled` — `CPU at limit: throttled (not killed)`.

## Sources

- [Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)
- [Resource Metrics Pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [kubectl top](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/)
- [kubectl top pod](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/kubectl_top_pod/)
- [kubectl top node](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/kubectl_top_node/)
- [Debug Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [Sidecar Containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [Event API](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/)
- [kube-apiserver](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/) (`--event-ttl`)
- [Kubelet Configuration](https://kubernetes.io/docs/tasks/administer-cluster/kubelet-config-file/)
- [Metrics Server](https://github.com/kubernetes-sigs/metrics-server)

## Next Module

Continue to [Part 6: Mock Exams](/k8s/cka/part6-mock-exams/) to test these troubleshooting moves under exam-style time pressure.
