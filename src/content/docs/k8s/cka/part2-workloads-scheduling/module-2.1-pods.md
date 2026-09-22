---
revision_pending: false
title: "Module 2.1: Pods Deep-Dive"
slug: k8s/cka/part2-workloads-scheduling/module-2.1-pods
sidebar:
  order: 2
lab:
  id: cka-2.1-pods
  url: https://killercoda.com/kubedojo/scenario/cka-2.1-pods
  duration: "40 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Foundation for all workloads
>
> **Time to Complete**: 40-50 minutes
>
> **Prerequisites**: Module 1.1 (Control Plane), Module 0.2 (Shell Mastery)

---

## What You'll Be Able to Do

After this module, you will be able to:
- **Implement** pods imperatively and declaratively with resource requests, probes, and security contexts
- **Diagnose** pod failures systematically across `Pending`, `ImagePullBackOff`, `CrashLoopBackOff`, readiness failures, and `OOMKilled`
- **Configure** liveness, readiness, and startup probes for applications with different startup and dependency behavior
- **Design** multi-container pods that use init containers, sidecars, shared volumes, and shared networking appropriately
- **Evaluate** restart policies, lifecycle phases, and termination behavior when choosing how a workload should recover

---

## Why This Module Matters

Hypothetical scenario: your team deploys a small API behind a Service, the Deployment reports that the rollout completed, but users still receive intermittent connection failures. `kubectl get pods` shows some pods as `Running`, some as `CrashLoopBackOff`, and one as `Running` with `0/1` readiness. The fix is not to memorize one command; the fix is to read the pod as a bundle of scheduling decisions, container states, probes, events, logs, networking, and termination rules until the evidence points at the actual fault.

Pods are the atomic unit of deployment in Kubernetes. Every container you run lives inside a pod, and every Deployment, StatefulSet, DaemonSet, and Job creates pods as the execution objects that land on nodes. If pods feel vague, higher-level workloads become misleading because the controller may look healthy while the pod underneath is unscheduled, pulling the wrong image, failing a probe, running without traffic, or restarting faster than the application can write useful logs.

This module treats pods as an operational object rather than a YAML shape to copy. You will create pods quickly, convert imperative commands into manifests, add security and resource boundaries, reason about the lifecycle from init containers through graceful termination, and debug the common failure modes you will see in the CKA exam and in ordinary cluster work. By the end, `kubectl get pod`, `kubectl describe pod`, `kubectl logs`, and `kubectl exec` should feel like a connected workflow instead of four unrelated commands.

Think of a pod like an apartment. Containers are roommates sharing the apartment: they share the same address, the same network namespace, and optionally the same storage, but each still has its own process and filesystem view. When the apartment is removed, the roommates leave together; when one roommate listens on a port, another roommate cannot claim the same port inside that same apartment because the network address is shared.

---

## Pod Fundamentals: What Kubernetes Actually Schedules

A pod is the smallest deployable unit in Kubernetes, but that definition becomes useful only when you connect it to scheduling and failure behavior. The scheduler does not place an individual Linux process on a node; it places a pod spec, and the kubelet on that node asks the container runtime to create the containers described in that spec. That means node capacity, image pull permissions, init-container success, probes, restart rules, and termination policy all meet at the pod boundary.

The practical result is that a pod is both a wrapper around containers and a contract with the cluster. The spec says what should exist, the status says what happened when Kubernetes tried to make it exist, and the Events section explains the recent control-plane and kubelet decisions. A strong pod debugging habit starts by reading those three layers separately instead of treating the visible `STATUS` column as the whole story.

```
┌────────────────────────────────────────────────────────────────┐
│                           Pod                                   │
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                   │
│   │   Container 1   │    │   Container 2   │                   │
│   │   (main app)    │    │   (sidecar)     │                   │
│   │                 │    │                 │                   │
│   │   Port 8080     │    │   Port 9090     │                   │
│   └─────────────────┘    └─────────────────┘                   │
│            │                      │                             │
│            └──────────┬───────────┘                             │
│                       │                                         │
│              Shared Network Namespace                           │
│              • Same IP address                                  │
│              • localhost communication                          │
│              • Shared ports (can't conflict)                    │
│                                                                 │
│              Shared Volumes (optional)                          │
│              • Mount same volume                                │
│              • Share data between containers                    │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The shared network namespace is the feature that most often surprises new operators. Two containers in the same pod communicate through `localhost`.

**Pause and predict:** two containers in the same pod both try to listen on port `8080`. What do you expect the second container to log, and how would the result differ if those containers were in separate pods? Make the prediction before reading on, because this is the exact mental model that prevents many confusing sidecar failures.

<details>
<summary>Check your prediction</summary>

All containers in a single pod share one network namespace and one pod IP. If a main application listens on port `8080`, the second container in that same pod fails to bind port `8080` (logging `address already in use`), so a helper in that same pod must use another port. Conversely, two separate pods receive different pod IP addresses, which means another pod can safely bind port `8080` without any port conflict.

</details>

The next section is comparing container and pod boundaries to clarify how shared runtime resources shape day-to-day operational responsibilities across nodes.

| Aspect | Container | Pod |
|--------|-----------|-----|
| Unit | Single process | Group of containers |
| Network | Own network namespace | Shared network namespace |
| IP Address | None (uses pod's) | One per pod |
| Storage | Own filesystem | Can share volumes |
| Lifecycle | Managed by pod | Managed by Kubernetes |

Pods exist because some containers are too tightly coupled to run as separate workloads. A log shipper that tails files from the main application, a service-mesh proxy that must sit beside the application, and an init container that prepares configuration before startup are all examples where scheduling and lifecycle coupling are useful. The tradeoff is that coupling also removes independent scaling, so a helper that needs its own rollout cadence or replica count should usually become a separate workload.

The pod is ephemeral by design, so you should not treat its name, IP, or local filesystem as stable infrastructure. A replacement pod may run on a different node with a different IP, and an `emptyDir` volume disappears when the pod is removed. Controllers and Services provide stable behavior above pods, but when a pod is failing, you still diagnose the pod itself because it is the object that exposes the direct evidence.

There is another subtle reason pods are the right level of abstraction: they let Kubernetes make placement decisions using the combined shape of the containers that must run together. If a main container needs `200m` CPU and a sidecar needs `50m`, the pod's scheduling footprint is the sum of those requests. That prevents Kubernetes from placing a helper somewhere the main application cannot run, and it also means an oversized sidecar can block the whole pod from scheduling even when the application itself looks small.

The pod boundary also determines how Kubernetes reports readiness. A pod with two regular containers is not fully ready until all containers that participate in readiness are ready, so a quiet helper can keep the whole pod out of Service endpoints. That is usually desirable when the helper is essential, such as a proxy sidecar, but it is surprising when the helper is optional. If readiness should not depend on a helper, review whether that helper belongs in the same pod or whether its probe should be configured differently.

You should also separate pod identity from application identity. A pod name is a useful debugging handle, but it is not a durable address for clients, and a pod IP is not a stable endpoint to embed in configuration. Labels, selectors, and Services form the stable application-facing layer above pods. This module stays at pod level because you need that foundation before the next module shows how Deployments and ReplicaSets keep replacement pods aligned with a desired replica count.

---

## Creating Pods Quickly Without Losing Control

The fastest reliable workflow is to generate a correct starting point and then edit the fields that matter. During the CKA exam, `kubectl run` with `--dry-run=client -o yaml` gives you valid Kubernetes structure without forcing you to remember every field from scratch. In production-style work, the same habit helps you avoid typo-driven debugging because you start with an object shape produced by Kubernetes tooling and then review the resulting manifest before applying it.

```bash
# Create a simple pod
kubectl run nginx --image=nginx

# Create pod and expose port
kubectl run nginx --image=nginx --port=80

# Create pod with labels
kubectl run nginx --image=nginx --labels="app=web,env=prod"

# Create pod with environment variables
kubectl run nginx --image=nginx --env="ENV=production"

# Resource requests/limits cannot be patched onto a running bare pod — its
# resources are immutable. Set them in the pod spec at creation time (see the
# YAML workflow below).

# Generate YAML without creating (essential for exam!)
kubectl run nginx --image=nginx --dry-run=client -o yaml > pod.yaml
```

Imperative commands are excellent for speed, but they are not a substitute for understanding the manifest. A generated pod with no resource requests may schedule in a lightly used test cluster and fail to fit in a constrained cluster, while a pod using `nginx` without a tag can pull a different image later than the one you practiced with. Treat imperative creation as a template generator and verification tool, not as permission to stop thinking about the spec.

```yaml
# pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx
  labels:
    app: nginx
    env: production
spec:
  containers:
  - name: nginx
    image: nginx:1.25
    ports:
    - containerPort: 80
    resources:
      requests:
        memory: "64Mi"
        cpu: "100m"
      limits:
        memory: "128Mi"
        cpu: "200m"
```

The declarative manifest shows the operational contract more clearly than the command. Labels make the pod selectable by Services and other tools, the image tag makes runtime behavior more repeatable, and the resource requests tell the scheduler what capacity must be available before the pod can land. Limits add a guardrail after the pod starts, but they do not replace requests because scheduling decisions are made before the container consumes memory or CPU.

```bash
# Apply the pod
kubectl apply -f pod.yaml
```

When you operate a pod, use commands that reveal different layers of state. `kubectl get` answers whether Kubernetes has a current object and what high-level status it reports, `kubectl describe` combines selected spec fields with status and events, and `kubectl get -o yaml` shows the full API object. Deletion is also part of the lifecycle; a normal delete gives the workload time to shut down, while a forced delete is a troubleshooting tool that can hide application shutdown bugs if used casually.

```bash
# List pods
kubectl get pods
kubectl get pods -o wide        # Show IP and node
kubectl get pods --show-labels  # Show labels

# Describe pod (detailed info)
kubectl describe pod nginx

# Get pod YAML
kubectl get pod nginx -o yaml

# Delete pod
kubectl delete pod nginx

# Delete pod immediately (skip graceful shutdown)
kubectl delete pod nginx --grace-period=0 --force

# Watch pods
kubectl get pods -w
```

Security context is another field that belongs in the first pod lesson because it changes what the container is allowed to do once it starts. A pod can define defaults such as `runAsUser` and `fsGroup`, while an individual container can tighten settings such as privilege escalation and writable root filesystems. These settings do not make a vulnerable image safe by themselves, but they reduce the damage a process can do when the image or application misbehaves.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sec-ctx-demo
spec:
  securityContext:
    runAsUser: 1000
    fsGroup: 2000
  containers:
  - name: myapp
    image: busybox
    command: [ "sh", "-c", "sleep 1h" ]
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
```

Before running this, what output do you expect from `kubectl describe pod sec-ctx-demo` if the image starts successfully but the application tries to write under `/`? The important reasoning step is to separate container startup from application behavior: Kubernetes may start the container correctly, yet the process can still fail because the security context intentionally denies an unsafe filesystem write.

Resource settings deserve the same careful reading as security settings. A request is a scheduling promise: Kubernetes tries to place the pod only on a node that can satisfy the requested CPU and memory. A limit is a runtime boundary: the container may be throttled for CPU or killed for memory if it exceeds the configured ceiling. Many confusing pod failures start when teams set limits without understanding normal peak memory, then interpret `CrashLoopBackOff` as an application bug even though the prior state says `OOMKilled`.

For exam work, get comfortable generating YAML, editing only the required fields, and then validating the object shape before applying it. `kubectl apply --dry-run=server` is useful when available because it asks the API server to validate the object without persisting it, while `kubectl diff` can show what would change for an existing object. Those commands are not magic, but they slow down the exact class of mistakes that come from hurried indentation and wrong field placement.

The right amount of pod YAML depends on the task. A one-off debug pod can be intentionally small because it is disposable and created to answer a narrow question. A workload pod that represents a real service should include labels, a pinned image, resources, probes, and a security posture that matches the environment. The difference is not ceremony; it is whether a future operator can infer intent from the manifest instead of reverse-engineering it from cluster behavior.

---

## Lifecycle, Status, and Termination

Pod lifecycle language is precise, but `kubectl get pods` compresses several layers into one table. A pod phase such as `Pending` or `Running` describes the broad lifecycle state, while container states such as `Waiting`, `Running`, and `Terminated` describe the individual containers inside the pod. The visible `STATUS` column may show a waiting reason like `ImagePullBackOff` or `CrashLoopBackOff`, so always confirm details with `describe` when the status is part of a diagnosis.

| Phase | Description |
|-------|-------------|
| **Pending** | Pod accepted, waiting to be scheduled or pull images |
| **Running** | Pod bound to node, at least one container running |
| **Succeeded** | All containers terminated successfully (exit 0) |
| **Failed** | All containers terminated, at least one failed |
| **Unknown** | Pod state cannot be determined (node communication issue) |

| State | Description |
|-------|-------------|
| **Waiting** | Not running yet (pulling image, applying secrets) |
| **Running** | Executing without issues |
| **Terminated** | Finished execution (successfully or failed) |

The phase table is useful, but the transition path matters more during troubleshooting. `Pending` before scheduling usually points to resources, node selectors, affinity, taints, or missing scheduling capacity. `Pending` after scheduling can still involve image pulls or container setup, and `Running` does not prove readiness because a container can be alive while a readiness probe keeps it out of Service endpoints.

```
┌────────────────────────────────────────────────────────────────┐
│                      Pod Lifecycle                              │
│                                                                 │
│   Pod Created                                                   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────┐     No node available                            │
│   │ Pending │◄────────────────────────────────┐                │
│   └────┬────┘                                 │                │
│        │ Scheduled to node                    │                │
│        ▼                                      │                │
│   ┌─────────┐     Container crashes           │                │
│   │ Running │────────────────────────────────►│                │
│   └────┬────┘                                 │                │
│        │                                      │                │
│        ├─────────────────────┐                │                │
│        │                     │                │                │
│        ▼                     ▼                │                │
│   ┌───────────┐        ┌────────┐            │                │
│   │ Succeeded │        │ Failed │            │                │
│   │ (exit 0)  │        │(exit≠0)│            │                │
│   └───────────┘        └────────┘            │                │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The quickest status checks should become muscle memory because they answer different questions. A normal `get` tells you the aggregate readiness and restart count, `describe` shows events and selected lifecycle details, and JSONPath lets you extract exactly the field you need when the output table is too compressed. During an exam, those commands also save time because you can decide whether to inspect scheduling, image pulls, probes, or application logs next.

```bash
# Quick status
kubectl get pod nginx
# NAME    READY   STATUS    RESTARTS   AGE
# nginx   1/1     Running   0          5m

# Detailed status
kubectl describe pod nginx | grep -A10 "Status:"

# Container states
kubectl get pod nginx -o jsonpath='{.status.containerStatuses[0].state}'

# Check why a pod is pending
kubectl describe pod nginx | grep -A5 "Events:"
```

Termination is part of lifecycle, not an afterthought. When you delete a pod, Kubernetes marks it for deletion, removes ready endpoints from normal Service traffic, sends `SIGTERM` to the containers, waits for the termination grace period, and eventually sends `SIGKILL` if the process does not exit. The default grace period is 30 seconds, which is generous enough for many small services but still short enough that applications should handle `SIGTERM` intentionally.

You can override the grace period during deletion with `kubectl delete pod nginx --grace-period=5`, but that should be a deliberate choice. Short grace periods are useful for stuck test pods and urgent cleanup, while normal application pods need enough time to stop accepting work, finish in-flight requests, flush logs, and close connections. If users see errors during rollouts, a too-short or ignored termination path is just as plausible as a bad image or a broken readiness probe.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: restart-demo
spec:
  restartPolicy: OnFailure   # Only restart if container fails
  containers:
  - name: worker
    image: busybox
    command: ["sh", "-c", "exit 1"]  # Will be restarted
```

**Pause and predict:** a pod with `restartPolicy: Always` has a container that exits with code `0`, while another pod with `restartPolicy: OnFailure` exits with the same code. Which one restarts, and what would you expect to see in `RESTARTS` after a few minutes? Answering this correctly shows that you are reading policy, exit code, and workload intent together.

<details>
<summary>Check your prediction</summary>

Restart policy controls what kubelet does after a container terminates, and it should match the workload shape. A pod configured with `restartPolicy: Always` restarts on exit `0` because it treats any container termination as an interruption. Conversely, `restartPolicy: OnFailure` does not restart on exit `0` because exit code `0` signals successful completion. Over time, `RESTARTS` climbs only for the `Always` pod, while the `OnFailure` pod remains stopped in `Completed` status with zero restarts.

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `Always` (default) | Restart on any termination | Long-running services |
| `OnFailure` | Restart only on non-zero exit | Jobs that should retry on failure |
| `Never` | Never restart | One-time scripts, debugging |

For managed workloads, remember that controllers may create replacement pods even when an individual pod has a policy that does not restart a completed container.

</details>

The next section is inspecting container restart counts and termination states through kubectl commands to observe how kubelet records process exit history.

```bash
# Check restart count
kubectl get pods
# NAME    READY   STATUS    RESTARTS   AGE
# nginx   1/1     Running   3          10m

# Describe shows restart details
kubectl describe pod nginx | grep -A5 "Last State"
```

Lifecycle diagnosis becomes easier when you distinguish "the pod object exists" from "the workload is serving." A pod can exist in the API before it has a node, be assigned to a node before its image is available, start a container before the app has loaded configuration, and report `Running` before readiness allows traffic. Each stage has a different owner: scheduler, kubelet, container runtime, image registry, application process, and probe configuration all leave evidence in different places.

The `RESTARTS` column is a counter, not a root cause. A restart count of `0` can still hide a pod that never scheduled, and a high restart count does not tell you whether the cause is a bad command, a missing file, a failed liveness probe, or memory pressure. Pair the counter with `Last State`, exit code, Events, and previous logs. When those sources agree, you can fix the cause instead of treating the restart itself as the problem.

Graceful termination is also part of availability design. During deletion or rollout, an application that stops accepting new work quickly and finishes in-flight work cleanly can disappear from endpoints with little user impact. An application that ignores `SIGTERM` or keeps advertising readiness while shutting down can create errors even though the pod eventually exits successfully. For that reason, readiness behavior and termination handling should be tested together, not only during emergency cleanup.

---

## Debugging Pods from Symptom to Evidence

Pod debugging is a narrowing process. Start with the visible symptom, choose the command that exposes the next layer, and avoid changing the object until you understand why it failed. If you patch an image, delete a pod, or widen a resource limit too early, you may erase the evidence that would have distinguished a registry problem from a scheduling problem or an application crash from a probe-induced restart.

```
Pod Problem
    │
    ├── kubectl get pods (check STATUS)
    │       │
    │       ├── Pending → kubectl describe (check Events)
    │       │               └── ImagePullBackOff, Insufficient resources, etc.
    │       │
    │       ├── CrashLoopBackOff → kubectl logs (check app errors)
    │       │                        └── Application crash, missing config, etc.
    │       │
    │       └── Running but not working → kubectl exec (check inside)
    │                                       └── Network issues, wrong config, etc.
    │
    └── kubectl describe pod (always useful)
```

The Events section is where Kubernetes tells you what it tried to do recently. A scheduling failure may mention insufficient CPU, untolerated taints, node affinity mismatch, or volume attachment trouble. An image failure may show pull attempts, authentication errors, or a missing tag. Events are not permanent logs, so they are best used early, then paired with pod status and application logs.

```bash
# The trinity of debugging
kubectl get pod nginx              # What's the status?
kubectl describe pod nginx         # What's happening? (events)
kubectl logs nginx                 # What does the app say?

# Deeper investigation
kubectl exec -it nginx -- /bin/sh  # Get inside
kubectl get events --sort-by='.lastTimestamp'  # Recent events
kubectl top pod nginx              # Resource usage (if metrics-server)
```

Logs answer a different question from events: what did the application or container entrypoint say? For a restarting pod, the most important flag is often `--previous`, because the current container instance may be too new to contain the crash output. In multi-container pods, always specify `-c` when ambiguity matters; otherwise you may inspect the quiet sidecar while the main application is failing.

```bash
# Current logs
kubectl logs nginx

# Follow logs (like tail -f)
kubectl logs nginx -f

# Last 100 lines
kubectl logs nginx --tail=100

# Logs from last hour
kubectl logs nginx --since=1h

# Logs from specific container (multi-container pod)
kubectl logs nginx -c sidecar

# Previous container logs (after crash)
kubectl logs nginx --previous
```

`kubectl exec` is for inspecting a running container, not for proving the pod is healthy. It helps when the pod is running but behavior is wrong: the config file is not mounted, DNS resolution fails, a process environment variable is missing, or a sidecar cannot reach the main app over `localhost`. If the container is crashing too quickly to exec into it, use logs, previous logs, events, or an ephemeral debug approach in later troubleshooting modules rather than racing the restart loop.

```bash
# Run a command
kubectl exec nginx -- ls /

# Interactive shell (/bin/sh works on minimal images; many images lack bash)
kubectl exec -it nginx -- /bin/sh

# Specific container in multi-container pod
kubectl exec -it nginx -c sidecar -- /bin/sh

# Run commands without shell
kubectl exec nginx -- cat /etc/nginx/nginx.conf
kubectl exec nginx -- env
kubectl exec nginx -- ps aux
```

| Symptom | Cause | Solution |
|---------|-------|----------|
| `ImagePullBackOff` | Wrong image name or no access | Fix image name, check registry auth |
| `CrashLoopBackOff` | Container keeps crashing | Check logs for app errors |
| `Pending` (no events) | No node has enough resources | Free up resources or add nodes |
| `Pending` (scheduling) | Taints, affinity rules | Check node taints and pod tolerations |
| `Running` but not ready | Readiness probe failing | Check probe configuration and app |
| `OOMKilled` | Out of memory | Increase memory limits |

Hypothetical scenario: a pod shows `Running` but the Service sends no traffic to it, and the application log looks normal. The tempting move is to exec into the container and test the application manually, but the first useful clue is usually the `READY` column and the readiness-probe events in `kubectl describe pod`. A container can be alive and still excluded from endpoints because readiness is a routing signal, not a process-aliveness signal.

Which approach would you choose here and why: increasing the liveness probe timeout, removing the readiness probe, or checking the readiness endpoint dependency path first? The best answer depends on evidence, but you should be suspicious of probes that call external dependencies from liveness. A database outage should usually stop new traffic through readiness, not force the application into repeated restarts.

A useful debugging sequence is to ask, "Could this command possibly answer my current question?" If the pod is unscheduled, `kubectl exec` cannot help because there is no container to enter. If the image cannot be pulled, application logs cannot help because the process never started. If the pod is running but not ready, logs may help, but the probe events and endpoint state are usually more direct. This small discipline saves time under exam pressure and prevents destructive guesswork in real clusters.

When events mention insufficient resources, do not immediately delete random pods to make room. First inspect the requested resources on the failing pod and the allocatable capacity on candidate nodes, because the scheduler uses requests rather than current usage for placement. A node can look quiet in a momentary metrics view and still be unavailable for scheduling if its requested capacity is already committed. That distinction becomes important when teams over-request memory or copy limits into requests without measuring.

When logs are empty, widen your thinking rather than assuming the logging system failed. The container may be exiting before the application initializes logging, the entrypoint may be wrong, the image may lack the expected shell, or a security context may block a filesystem write needed during startup. `describe` can show command, image, state, and events, while `get pod -o yaml` exposes the resolved spec. Together they often reveal a mismatch between the manifest you intended and the container that actually ran.

For multi-container pods, always name the container you are inspecting when the symptom involves a specific process. A sidecar can be healthy while the main app crashes, and the main app can be healthy while a proxy sidecar blocks traffic. The `READY` count tells you how many containers are ready, but the per-container status in `describe` tells you which one is waiting, terminated, or restarting. That per-container view is the difference between a fast fix and a misleading aggregate status.

---

## Multi-Container Pods, Init Containers, and Shared Volumes

Multi-container pods are powerful because they make tight coupling explicit. Containers in the same pod are scheduled together, share the pod IP, can communicate over `localhost`, and can mount the same volumes. That is ideal for helpers that are meaningless without the main application, but it is a poor fit for independently scalable services because the pod is the scaling unit.

```
┌────────────────────────────────────────────────────────────────┐
│                Multi-Container Patterns                         │
│                                                                 │
│   Sidecar                    Ambassador             Adapter     │
│   ┌──────────────────┐       ┌──────────────────┐  ┌─────────┐ │
│   │ ┌────┐  ┌────┐   │       │ ┌────┐  ┌────┐   │  │┌────┐   │ │
│   │ │Main│  │Log │   │       │ │Main│  │Proxy│  │  ││Main│   │ │
│   │ │App │──│Ship│   │       │ │App │──│     │──┼──││App │   │ │
│   │ └────┘  └────┘   │       │ └────┘  └────┘   │  │└──┬─┘   │ │
│   │   Main + Helper  │       │   Proxy outbound │  │   │     │ │
│   └──────────────────┘       └──────────────────┘  │┌──▼──┐  │ │
│                                                    ││Adapt│  │ │
│   Examples:                  Examples:             ││Log  │  │ │
│   - Log collectors           - Service mesh proxy  │└─────┘  │ │
│   - Config reloaders         - Database proxy      │Transform│ │
│   - Git sync                 - Auth proxy          └─────────┘ │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The sidecar pattern keeps a helper beside the main application for the lifetime of the pod. A log shipper that tails application logs from a shared volume is the classic example, but the same pattern appears in proxies, certificate refreshers, and config reloaders. The design works when the helper and main app should be created, moved, restarted, and deleted as one unit.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-with-sidecar
spec:
  containers:
  # Main application container
  - name: web
    image: nginx
    ports:
    - containerPort: 80
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx

  # Sidecar container - ships logs
  - name: log-shipper
    image: busybox
    command: ["sh", "-c", "tail -F /var/log/nginx/access.log"]
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx

  volumes:
  - name: logs
    emptyDir: {}
```

The shared `emptyDir` volume in this pod is created when the pod is assigned to a node and removed when the pod is gone. That makes it useful for transient coordination between containers, such as generated files, rendered configuration, or logs being consumed by a sidecar. It is not durable storage, so if you need data to survive pod replacement, you should move to a PersistentVolume-backed pattern in a later storage module.

Init containers solve a different problem: ordered startup. They run before app containers, they run sequentially, and each one must complete successfully before the next init container or any regular container starts. This is the right tool for preparing files, waiting for a dependency, or performing a one-time setup step that should not remain running beside the application.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
spec:
  # Init containers run first, in order
  initContainers:
  - name: wait-for-db
    image: busybox
    command: ['sh', '-c', 'until nc -z db-service 5432; do echo waiting for db; sleep 2; done']

  - name: init-config
    image: busybox
    command: ['sh', '-c', 'echo "config initialized" > /config/ready']
    volumeMounts:
    - name: config
      mountPath: /config

  # App containers start after all init containers succeed
  containers:
  - name: app
    image: myapp
    volumeMounts:
    - name: config
      mountPath: /config

  volumes:
  - name: config
    emptyDir: {}
```

| Use Case | Example |
|----------|---------|
| Wait for dependency | Wait for database to be ready |
| Setup configuration | Clone git repo, generate config |
| Database migrations | Run migrations before app starts |
| Register with service | Register instance with external system |
| Download assets | Fetch static files from S3 |

Stop and think: your web application needs a configuration file generated from a template before the app starts, and it also needs a log-shipping helper for the whole runtime. Which container pattern handles each requirement, and can both patterns appear in the same pod? The answer is yes: use an init container for the completed setup work and a sidecar for the long-running helper.

When an init container fails, app containers do not start. With the default restart behavior for pods managed like services, kubelet retries the init sequence, and you will see the pod stuck in an init-related waiting state until the init step succeeds or you change the spec. That makes init containers a useful guardrail for preconditions, but it also means a fragile dependency check can prevent otherwise healthy application code from even starting.

Init containers should do work that is safe to repeat. Because Kubernetes may retry them after failure, an init container that runs a migration, writes external state, or registers with a remote system should be idempotent or guarded by the external system. A simple file-rendering init container is naturally repeatable; a database migration may need application-level migration tooling that records applied versions. If the setup step cannot tolerate retries, it probably needs a more explicit Job or release process.

Sidecars have the opposite lifetime problem. They continue running beside the main application, so they must be cheap enough to exist per pod replica and reliable enough not to hold the pod hostage. A log shipper that consumes too much memory can cause the pod to be killed even if the main application is efficient, and a proxy sidecar with a failing readiness check can remove the application from traffic. The helper is part of the workload footprint, not a free accessory.

Shared volumes are a coordination tool, not a synchronization protocol. If one container writes a file and another reads it, you still need to reason about timing, partial writes, permissions, and cleanup. Init containers avoid many timing issues because they complete before app containers start, while sidecars require the main application to handle files changing during runtime. That distinction is why the same `emptyDir` volume can be safe in an init pattern and fragile in a long-running producer-consumer pattern.

When you choose between one pod with two containers and two pods with a Service, ask who owns failure. If the helper failing means the application instance is useless, keep them together and let the pod represent that shared fate. If the helper can fail independently, scale independently, or serve multiple application instances, split it out. Kubernetes gives you both tools, and the better design is the one whose failure boundary matches the real system.

---

## Probes, Readiness, and Runtime Health

Kubernetes cannot automatically know whether your process is useful just because it is running. A web server process may be alive but deadlocked, an API may be serving only errors while a cache warms, and a slow legacy application may need a long startup window before normal health checks make sense. Probes let you describe those distinctions so kubelet can restart truly unhealthy containers and Services can route traffic only to ready pods.

| Probe | Purpose | Action on Failure | When to Use |
|-------|---------|-------------------|-------------|
| **Startup** | Checks if the application has started successfully | Restarts the container | For slow-starting legacy applications that need extra time to initialize without failing liveness checks. |
| **Liveness** | Checks if the application is healthy and running | Restarts the container | To recover from deadlocks or application crashes where the process is running but unresponsive. |
| **Readiness** | Checks if the application is ready to accept traffic | Removes pod from Service endpoints | When the app is running but temporarily unable to serve traffic (e.g., loading large caches, database connection dropped). |

The most important probe distinction is the consequence of failure. Liveness failure restarts the container, so it should detect conditions that a restart can plausibly fix, such as a stuck process. Readiness failure removes the pod from normal Service endpoints, so it should detect whether the application can accept traffic right now. Startup failure protects slow starters by disabling liveness and readiness checks until startup succeeds or the startup budget is exhausted.

Probes can use HTTP, TCP, or command execution, and the mechanism should match the signal you actually need. An HTTP readiness endpoint can check whether the application has loaded config and opened required pools, while a TCP socket probe only proves that something accepts connections on a port. An exec probe is flexible, but it runs inside the container and can become expensive or brittle if it shells out to slow commands every few seconds.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: probe-demo
spec:
  containers:
  - name: myapp
    image: nginx
    ports:
    - containerPort: 80
    
    # 1. Startup Probe: Wait up to 300 seconds (30 * 10) for slow start
    startupProbe:
      httpGet:
        path: /
        port: 80
      failureThreshold: 30
      periodSeconds: 10

    # 2. Liveness Probe: Restart if deadlocked
    livenessProbe:
      exec:
        command:
        - cat
        - /usr/share/nginx/html/index.html
      initialDelaySeconds: 5
      periodSeconds: 5
      
    # 3. Readiness Probe: Stop sending traffic if backend disconnected
    readinessProbe:
      tcpSocket:
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 10
```

**Pause and predict:** if a pod's liveness probe passes but its readiness probe fails, what will `kubectl get pods` show in the `READY` and `STATUS` columns, and will the pod be restarted? Make your prediction before checking the result below.

<details>
<summary>Check your prediction</summary>

STATUS stays `Running`, READY is not full (for example `0/1`), and a readiness failure does not restart the container. When readiness fails, kubelet leaves the container running while the endpoint controller removes the pod IP address from matching Service endpoints until health probes succeed again.

</details>

The next section is balancing probe timeouts and thresholds so health checks protect application traffic without triggering unnecessary container restart loops.

Probe configuration is a balancing act, not a checkbox. Timeouts that are too short can restart healthy but temporarily slow applications, while thresholds that are too lenient can leave dead pods receiving traffic or stuck containers running too long. When debugging a probe issue, read the endpoint behavior, the timeout, the failure threshold, and the period together because those four values define the real failure budget.

Hypothetical scenario: during a load test, the database slows down and the application health endpoint waits on a database query. If that endpoint is used for liveness with a one-second timeout, Kubernetes may restart the application repeatedly, adding more cold starts and making the database pressure worse. A better design usually keeps liveness focused on internal process health and uses readiness to stop new traffic when dependencies are temporarily unavailable.

Startup probes are especially useful for applications that have a long but legitimate initialization path. Without a startup probe, liveness may begin judging the container before the application has loaded indexes, warmed caches, or completed startup migrations. With a startup probe, kubelet gives the application a separate startup budget before liveness becomes active. That does not mean the app can start forever; it means the startup failure budget is explicit and separate from normal runtime health.

Readiness should be conservative enough to protect users but not so broad that every dependency blip drains all capacity. A readiness endpoint that checks database connectivity may be appropriate for a request path that always needs the database, while a service with degraded-but-useful behavior might expose a readiness check based on local queue capacity or critical configuration. The pod lesson is that Kubernetes will follow the signal you provide, so the endpoint has to represent the traffic decision you actually want.

Liveness should be cheap, local, and meaningful. If the probe command forks a heavy process every few seconds, the health check itself can become load. If the probe tests only that a TCP port is open, it may miss application deadlock. The best liveness signal is one that answers, "Is this process stuck in a way a restart is likely to repair?" rather than "Can every downstream dependency answer right now?"

When a probe fails, inspect both the Kubernetes event and the endpoint manually from the same perspective if possible. An HTTP endpoint that works from your laptop may fail from kubelet because it binds only to localhost inside the container, requires a Host header, uses the wrong path, or responds slower than the configured timeout. The event tells you that kubelet judged the probe failed; manual testing helps explain why the application behaved that way under the probe configuration.

---

## Pod Networking and Direct Inspection

Kubernetes gives every pod its own IP address, and containers inside the pod share that IP. This model is simpler than host-port thinking because pods can communicate with other pods directly, while containers in the same pod use `localhost` for intra-pod traffic. The tradeoff is that pod IPs are ephemeral, so direct pod-to-pod access is useful for debugging but Services are the stable abstraction for normal traffic.

```
┌────────────────────────────────────────────────────────────────┐
│                     Pod Networking                              │
│                                                                 │
│   Every pod gets a unique IP address                           │
│   Containers in pod share that IP                              │
│   Pods can communicate with all other pods (no NAT)            │
│                                                                 │
│   ┌───────────────────────┐    ┌───────────────────────┐       │
│   │ Pod A (10.244.1.5)    │    │ Pod B (10.244.2.8)    │       │
│   │ ┌─────┐    ┌─────┐    │    │ ┌─────┐              │       │
│   │ │ C1  │    │ C2  │    │    │ │ C1  │              │       │
│   │ │:80  │    │:9090│    │    │ │:8080│              │       │
│   │ └──┬──┘    └──┬──┘    │    │ └──┬──┘              │       │
│   │    │          │       │    │    │                 │       │
│   │    └────┬─────┘       │    │    │                 │       │
│   │         │ localhost   │    │    │                 │       │
│   └─────────┼─────────────┘    └────┼─────────────────┘       │
│             │                       │                          │
│             └───────────────────────┘                          │
│                Can reach each other directly                   │
│                10.244.1.5:80 ←→ 10.244.2.8:8080               │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

When you test networking, be clear about which path you are testing. A sidecar curling `localhost:80` tests intra-pod communication, a separate debug pod curling a pod IP tests pod-network reachability, and a client using a Service name tests selector, endpoint, and kube-proxy or data-plane behavior. Those are different questions, so do not let one successful curl convince you that the whole path is healthy.

```bash
# Containers in same pod communicate via localhost
# Container 1 (nginx on port 80)
# Container 2 can reach it at localhost:80

# Example: curl from sidecar to main app
kubectl exec -it pod-name -c sidecar -- curl localhost:80
```

```bash
# Get pod IP
kubectl get pod nginx -o wide
# NAME    READY   STATUS    IP           NODE
# nginx   1/1     Running   10.244.1.5   worker-1

# Get IP with jsonpath
kubectl get pod nginx -o jsonpath='{.status.podIP}'

# Get all pod IPs
kubectl get pods -o custom-columns='NAME:.metadata.name,IP:.status.podIP'
```

Direct inspection is especially useful when readiness is failing. If the application responds from inside the pod but not through the Service, inspect labels, selectors, endpoints, and readiness. If it fails from inside the pod, inspect the process, port, local config, and sidecar interaction before blaming cluster networking. The clean diagnostic habit is to move one hop at a time instead of testing the longest path first.

The pod network model also explains why host networking assumptions can be misleading. A container port in the pod spec documents what the container intends to expose, but it does not by itself publish that port outside the pod or create a Service. A Service selects pods by labels and sends traffic to matching ready endpoints, while a direct pod IP bypasses that selector logic. If direct pod access works but Service access fails, your next question should be about labels, selectors, readiness, and endpoint generation rather than the application listener.

DNS troubleshooting follows the same path-by-path method. A pod can fail to resolve a Service name because CoreDNS is unavailable, because the query uses the wrong namespace, or because the Service does not exist. A direct pod IP test skips DNS entirely, so it is useful for isolating name resolution from raw connectivity. In early pod debugging, you are not expected to master every network plugin detail, but you are expected to avoid mixing DNS, Service selection, readiness, and pod-local process checks into one vague "network issue."

Security context and networking can intersect in small ways. A non-root container may be unable to bind a privileged port, and a read-only root filesystem may block an application from writing a generated config file needed before it listens. Those failures can look like network failures from outside because the port never opens. When a pod does not accept traffic, inspect the process logs and container state before assuming the cluster network dropped packets.

---

## Patterns & Anti-Patterns

Good pod design starts with honest coupling. If containers must share a lifecycle, share files through a transient volume, or communicate over `localhost` as one logical unit, a pod-level pattern is appropriate. If they need independent scaling, independent deployment, or separate ownership, forcing them into one pod creates operational friction that will show up later during rollouts and incidents.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Generate YAML with `--dry-run=client -o yaml` | You need a fast, valid starting manifest | Kubernetes tooling creates the object skeleton and reduces syntax mistakes | Review and commit the final YAML when the object matters beyond a quick task |
| Sidecar for tightly coupled helpers | A helper must live beside one app instance | Shared network and volumes make coordination simple | The sidecar scales only when the main app scales |
| Init container for ordered setup | Setup must complete before the app starts | Init containers run sequentially and gate app startup | Slow or fragile init work delays pod readiness |
| Readiness for traffic control | The app is alive but not ready for requests | Service endpoints exclude unready pods without restarting them | Bad readiness checks can remove too much capacity |
| Resource requests and limits | You need predictable scheduling and containment | Requests guide scheduling; limits cap consumption | Limits that are too tight can cause `OOMKilled` or throttling |

Anti-patterns usually come from treating a pod as a small virtual machine. A pod can contain multiple containers, but it is still meant to represent one deployable unit, not a collection of unrelated services. The better alternative is almost always to split independent concerns into separate workloads and connect them through Services, queues, or storage interfaces that match their real lifecycle.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Putting unrelated services in one pod | They cannot scale, roll out, or fail independently | Use separate Deployments and connect through a Service |
| Using `latest` tags | A recreated pod may run a different image than the one tested | Pin a versioned tag or immutable digest |
| Checking databases in liveness probes | Dependency slowness causes restarts that amplify outages | Use readiness for dependency availability and liveness for process health |
| Omitting resource requests | Scheduler cannot reserve realistic capacity | Set CPU and memory requests based on measured behavior |
| Debugging only with `kubectl exec` | Crash loops and scheduling failures may have no running shell to inspect | Start with `get`, `describe`, events, and logs, then exec when the container is stable |

The pattern tables are not rules to apply blindly; they are prompts for operational fit. A small learning pod can be created imperatively and deleted minutes later, while a production workload should be expressed in version-controlled manifests or higher-level workload objects. Similarly, a sidecar is elegant when the helper is bound to exactly one application instance, and awkward when the helper becomes a shared service in disguise.

---

## Decision Framework

Use this framework when you are deciding what to do with a pod problem or pod design. The first question is whether you are creating, debugging, or modeling coupling, because those paths use different evidence. Creation work starts from spec quality, debugging starts from status and events, and coupling decisions start from lifecycle and scaling.

```
Need a pod?
    │
    ├── Quick exam or throwaway test?
    │       └── Use kubectl run, then generate YAML if fields need editing.
    │
    ├── Repeatable workload definition?
    │       └── Write or generate YAML, pin images, add labels, resources, and probes.
    │
    ├── Pod is not starting?
    │       └── Read STATUS, describe Events, then inspect image, scheduling, and init state.
    │
    ├── Pod starts but receives no traffic?
    │       └── Check READY, readiness probe events, labels, selectors, and endpoints.
    │
    └── Helper container needed?
            ├── Runs before app and exits? Use an init container.
            └── Runs beside app for its lifetime? Use a sidecar.
```

| Decision | Choose This | When the Evidence Shows | Watch Out For |
|----------|-------------|-------------------------|---------------|
| Imperative command | `kubectl run` | You need speed or a generated starting point | Missing fields must still be reviewed |
| Declarative pod YAML | `kubectl apply -f` | You need repeatability and exact spec control | Standalone pods are rarely the final production controller |
| Init container | `initContainers` | Setup must complete before app startup | Dependency waits can block the whole pod |
| Sidecar | Multiple app containers | Helper must share lifecycle, network, or files | No independent scaling for the helper |
| Readiness probe | `readinessProbe` | Traffic should pause without a restart | Probe must reflect request-serving ability |
| Liveness probe | `livenessProbe` | Restart is likely to repair the process | External dependency checks can cause restart storms |

For exam tasks, this framework turns into a time-saving order of operations. Generate the smallest valid object, apply it, observe the status, and then use the most specific command that answers the next question. For real operations, the same order prevents guesswork because every change is tied to evidence: events for scheduling and image pulls, logs for application crashes, probes for readiness and restart behavior, and exec for live in-container inspection.

---

## Did You Know?

- Kubernetes gives a pod a single IP address shared by all containers in that pod, which is why two containers in the same pod cannot both bind the same port on that IP.
- The default pod termination grace period is 30 seconds, so an application that ignores `SIGTERM` may look fine during normal operation and still cause errors during rollout or deletion.
- Init containers run to completion before app containers start, and they do not use readiness probes because their job is to finish rather than stay ready for traffic.
- Startup probes were added so slow-starting applications can receive a separate startup budget before liveness checks begin, which helps avoid restarts during legitimate initialization.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Using `latest` tag | It feels convenient during testing, but a later pod recreation may pull a different image. | Pin a version tag such as `nginx:1.25` or use an immutable image digest for critical workloads. |
| No resource requests | The pod may run in a quiet lab, so the missing scheduling signal is easy to miss. | Set CPU and memory requests that reflect measured minimum needs, then add limits deliberately. |
| Ignoring `kubectl describe` events | Operators jump straight to logs even when the container never started. | Read Events for scheduling, image pull, mount, and probe failures before changing the spec. |
| Forgetting `--previous` on crash loops | The current restarted container may not contain the crash message yet. | Use `kubectl logs POD --previous` and inspect `Last State` in `describe`. |
| Checking dependencies in liveness | Teams reuse a broad `/health` endpoint for every probe. | Keep liveness focused on internal process health and put dependency readiness in readiness checks. |
| Forgetting `-c` in multi-container pods | `kubectl logs` or `exec` may default to the wrong container or ask you to choose. | Specify `-c container-name` whenever the pod has more than one container. |
| Treating pod IPs as stable | Direct pod IP tests work once, which can hide the replacement behavior. | Use pod IPs for debugging and Services for stable application traffic. |
| Using forced deletion as a normal habit | It clears stuck pods quickly but skips the shutdown path you need to validate. | Prefer normal deletion, and reserve `--grace-period=0 --force` for deliberate cleanup cases. |

---

## Quiz

<details>
<summary>1. Your pod is `Pending` for several minutes, and `kubectl logs` returns an error because no container has started. What do you check first, and why?</summary>

Start with `kubectl describe pod <name>` and read the Events section because a `Pending` pod may not have a running container to produce logs. Events can show insufficient CPU or memory, node affinity mismatch, untolerated taints, volume problems, or image pull setup messages. If scheduling failed, application logs are irrelevant because kubelet never started the container. If the pod was scheduled and is waiting on image pull or init work, the same describe output points you to that layer next.

</details>

<details>
<summary>2. A pod shows `CrashLoopBackOff` with many restarts after a new image rollout. Which commands give the fastest useful evidence, and what are you looking for?</summary>

Run `kubectl logs <pod> --previous` first because the previous container instance often contains the crash message that disappeared when the container restarted. Then run `kubectl describe pod <pod>` and inspect `Last State`, exit code, restart count, and Events. Exit code `137` often points toward memory pressure, while ordinary non-zero exits usually point back to the application command, configuration, or dependencies. You should avoid deleting the pod before collecting that evidence because replacement can reset the most useful context.

</details>

<details>
<summary>3. Your application needs a generated config file before startup and a log shipper during runtime. How should you structure the pod, and what failure behavior should you expect?</summary>

Use an init container to generate the configuration file into a shared volume, then start the main application and log shipper as regular containers that mount the relevant volumes. The init container runs first and must complete successfully before either runtime container starts. If the init container fails, Kubernetes retries according to the pod restart behavior and the application containers remain blocked. This structure prevents the application from starting with missing configuration while still allowing the sidecar to run for the full application lifetime.

</details>

<details>
<summary>4. A pod is `Running` but shows `0/1` in the `READY` column, and users cannot reach it through the Service. What is the most likely pod-level area to inspect?</summary>

Inspect the readiness probe and the Service endpoint path before assuming the process is dead. A `Running` pod with `0/1` readiness means the container can be alive while Kubernetes considers it not ready for traffic. `kubectl describe pod` should show readiness probe failures, and endpoint inspection can confirm whether the pod is excluded from the Service. Liveness is different: if liveness were failing repeatedly, you would expect restarts rather than only a readiness count problem.

</details>

<details>
<summary>5. During a database slowdown, pods repeatedly restart because `/health` checks the database and is configured as a liveness probe. Why does this make the outage worse, and how would you redesign the probes?</summary>

The liveness probe tells kubelet to restart the container when the endpoint times out, so database slowness turns into application restarts. Those restarts drop in-flight work, create cold starts, and can add more load to the dependency when each pod reconnects. Move dependency-sensitive checks into readiness so the pod stops receiving new traffic without being killed. Keep liveness focused on conditions a restart can repair, such as an internal deadlock or a process that cannot answer a cheap local check.

</details>

<details>
<summary>6. A sidecar cannot connect to the main container on `localhost:8080`, and both containers are in the same pod. What pod facts guide your diagnosis?</summary>

Containers in the same pod share a network namespace, so `localhost:8080` should reach the main container if the main process is actually listening on that port. Check whether the main application bound to a different port, bound only after startup work, or crashed after the sidecar began trying to connect. Also confirm there is no port conflict because two containers in the same pod cannot both bind the same port on the shared pod IP. `kubectl logs -c`, `kubectl exec -c`, and `kubectl describe pod` together separate app behavior from pod-level networking assumptions.

</details>

<details>
<summary>7. You generated a pod manifest with `kubectl run --dry-run=client -o yaml`, edited it, and now it fails with `ImagePullBackOff`. What should you inspect before changing unrelated fields?</summary>

Inspect the image name, tag, registry path, and image pull events in `kubectl describe pod`. `ImagePullBackOff` usually means Kubernetes tried to pull the image and failed because the tag does not exist, the registry is unavailable, or authentication is missing. Resource requests, probes, and security context may still matter later, but they do not explain a failed image pull before the container starts. Fix the image reference or registry access first, then wait for the pod to move into the next lifecycle stage.

</details>

---

## Hands-On Exercise

Exercise scenario: you will create a multi-container pod with an init container, a main web container, and a log-reading sidecar, then inspect the lifecycle and clean it up. The goal is not only to make the pod run, but to practice reading the evidence at each step. Keep the manifest visible while you work so you can connect each command output to a specific field in the pod spec.

### Task 1: Create a pod with an init container and sidecar

```bash
cat > multi-container-pod.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: webapp
spec:
  initContainers:
  - name: init-setup
    image: busybox
    command: ['sh', '-c', 'echo "Init complete" > /shared/init-status.txt']
    volumeMounts:
    - name: shared
      mountPath: /shared

  containers:
  - name: web
    image: nginx
    ports:
    - containerPort: 80
    volumeMounts:
    - name: shared
      mountPath: /usr/share/nginx/html
    - name: logs
      mountPath: /var/log/nginx

  - name: log-reader
    image: busybox
    command: ['sh', '-c', 'tail -F /logs/access.log 2>/dev/null || sleep infinity']
    volumeMounts:
    - name: logs
      mountPath: /logs

  volumes:
  - name: shared
    emptyDir: {}
  - name: logs
    emptyDir: {}
EOF

kubectl apply -f multi-container-pod.yaml
```

<details>
<summary>Solution notes</summary>

The manifest uses an init container to write a file before `nginx` starts, then mounts the same `shared` volume into the web container. It also mounts a `logs` volume into both `nginx` and the `log-reader` sidecar so the helper has access to files produced by the main container. If the pod does not start, use `kubectl describe pod webapp` before editing the manifest because the Events section will usually identify the first failed layer.

</details>

### Task 2: Wait for startup and inspect init state

```bash
# Wait for the pod to be fully ready
kubectl wait --for=condition=ready pod/webapp --timeout=90s

# Check init container completed
kubectl describe pod webapp | grep -A10 "Init Containers"
```

<details>
<summary>Solution notes</summary>

The wait command should complete only after the regular containers are ready. The describe output should show the init container as terminated successfully, which confirms the setup step completed before the app containers became active. If the pod remains in an init state, inspect the init container logs with `kubectl logs webapp -c init-setup` and then check the command, image, and volume mount.

</details>

### Task 3: Verify the shared volume and sidecar view

```bash
# Init container created this file
kubectl exec webapp -c web -- cat /usr/share/nginx/html/init-status.txt

# Execute command non-interactively
kubectl exec webapp -c log-reader -- ls /logs
```

<details>
<summary>Solution notes</summary>

The first command proves that the file written by the init container is visible to the web container through the shared volume. The second command proves that the sidecar has its own filesystem but can see the mounted log directory. If either command fails, compare the `volumeMounts` and `volumes` names carefully because a spelling mismatch changes the runtime shape of the pod.

</details>

### Task 4: Generate traffic and read logs

```bash
# Get pod IP
POD_IP=$(kubectl get pod webapp -o jsonpath='{.status.podIP}')

# Generate traffic from another pod
kubectl run curl --image=curlimages/curl --rm -i --restart=Never -- curl -s $POD_IP

# Check sidecar saw the log
kubectl logs webapp -c log-reader
```

<details>
<summary>Solution notes</summary>

This task uses the pod IP for direct debugging rather than stable application traffic. The temporary curl pod should reach `nginx`, and the sidecar log command should show whether the helper can read log output from the shared mount. In a real service path, you would add a Service and test through DNS or the Service IP, but direct pod access keeps this exercise focused on pod networking and sidecar behavior.

</details>

### Task 5: Practice targeted debugging and cleanup

```bash
# Logs from specific container
kubectl logs webapp -c web
kubectl logs webapp -c log-reader

# View recent logs
kubectl logs webapp -c web --tail=10

# Cleanup
kubectl delete pod webapp
rm multi-container-pod.yaml
```

<details>
<summary>Solution notes</summary>

Specifying `-c` keeps the debugging target explicit in a multi-container pod. The cleanup uses normal pod deletion so you can observe graceful termination if you run `kubectl get pods -w` in another terminal. Forced deletion is unnecessary for this exercise unless the pod becomes stuck for reasons you have already inspected.

</details>

### Practice Drills

The following drills preserve the same command patterns in smaller repetitions. Use them after the main exercise if you want CKA-speed practice, but keep the same diagnostic discipline: generate, apply, observe, inspect, and clean up. Do not move faster than your ability to explain which pod field or status line each command is proving.

```bash
# 1. Basic nginx pod
kubectl run nginx --image=nginx

# 2. Pod with labels
kubectl run labeled --image=nginx --labels="app=web,tier=frontend"

# 3. Pod with port
kubectl run webserver --image=nginx --port=80

# 4. Pod with environment variables
kubectl run envpod --image=nginx --env="ENV=production" --env="DEBUG=false"

# 5. Pod with resource requests (set at creation via --overrides; a running
#    bare pod's resources are immutable, so they cannot be patched in afterward)
kubectl run limited --image=nginx --overrides='{"spec":{"containers":[{"name":"limited","image":"nginx","resources":{"requests":{"cpu":"100m","memory":"128Mi"},"limits":{"cpu":"200m","memory":"256Mi"}}}]}}'

# Verify all pods
kubectl get pods

# Cleanup
kubectl delete pod nginx labeled webserver envpod limited
```

```bash
# Generate base YAML
kubectl run webapp --image=nginx:1.25 --port=80 --dry-run=client -o yaml > webapp.yaml

# View and verify
cat webapp.yaml

# Apply it
kubectl apply -f webapp.yaml

# Modify: add a label
kubectl label pod webapp tier=frontend

# Verify label
kubectl get pod webapp --show-labels

# Cleanup
kubectl delete -f webapp.yaml
rm webapp.yaml
```

```bash
# Create a pod that will fail
kubectl run failing --image=nginx --command -- /bin/sh -c "exit 1"

# Check status
kubectl get pod failing
# STATUS: CrashLoopBackOff

# Debug step 1: describe
kubectl describe pod failing | tail -20

# Debug step 2: logs
kubectl logs failing --previous

# Debug step 3: check events
kubectl get events --field-selector involvedObject.name=failing

# Cleanup
kubectl delete pod failing
```

```bash
# Create pod with sidecar
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: sidecar-demo
spec:
  containers:
  - name: main
    image: nginx
    volumeMounts:
    - name: shared
      mountPath: /usr/share/nginx/html
  - name: sidecar
    image: busybox
    command: ['sh', '-c', 'while true; do date > /html/index.html; sleep 5; done']
    volumeMounts:
    - name: shared
      mountPath: /html
  volumes:
  - name: shared
    emptyDir: {}
EOF

# Wait for ready
kubectl wait --for=condition=ready pod/sidecar-demo --timeout=60s

# Test - sidecar writes timestamp that nginx serves
kubectl exec sidecar-demo -c main -- cat /usr/share/nginx/html/index.html

# Wait 5 seconds and check again - timestamp should change
sleep 5
kubectl exec sidecar-demo -c main -- cat /usr/share/nginx/html/index.html

# Cleanup
kubectl delete pod sidecar-demo
```

```bash
# Create pod with init container
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
spec:
  initContainers:
  - name: init-download
    image: busybox
    command: ['sh', '-c', 'echo "Hello from init" > /work/message.txt']
    volumeMounts:
    - name: workdir
      mountPath: /work
  containers:
  - name: main
    image: busybox
    command: ['sh', '-c', 'cat /work/message.txt && sleep 3600']
    volumeMounts:
    - name: workdir
      mountPath: /work
  volumes:
  - name: workdir
    emptyDir: {}
EOF

# Wait for init container and main container to be ready
kubectl wait --for=condition=ready pod/init-demo --timeout=60s

# Verify init worked
kubectl logs init-demo

# Check init container status
kubectl describe pod init-demo | grep -A5 "Init Containers"

# Cleanup
kubectl delete pod init-demo
```

```bash
# Create two pods
kubectl run pod-a --image=nginx --port=80
kubectl run pod-b --image=busybox --command -- sleep 3600

# Wait for ready
kubectl wait --for=condition=ready pod/pod-a pod/pod-b --timeout=60s

# Get pod-a IP
POD_A_IP=$(kubectl get pod pod-a -o jsonpath='{.status.podIP}')
echo "Pod A IP: $POD_A_IP"

# From pod-b, reach pod-a
kubectl exec pod-b -- wget -qO- $POD_A_IP

# Cleanup
kubectl delete pod pod-a pod-b
```

```bash
# Create pod with wrong image
kubectl run broken --image=nginx:nonexistent-tag

# Check status
kubectl get pod broken
# STATUS: ImagePullBackOff or ErrImagePull

# Diagnose
kubectl describe pod broken | grep -A10 "Events"

# Fix: update the image
kubectl set image pod/broken broken=nginx:1.25

# Verify fixed
kubectl get pod broken
kubectl wait --for=condition=ready pod/broken --timeout=60s

# Cleanup
kubectl delete pod broken
```

```bash
# Challenge prompt: complete this workflow without looking at the solution
kubectl run challenge --image=nginx:1.25 --labels="app=web,env=test"
kubectl wait --for=condition=ready pod/challenge --timeout=60s
kubectl exec challenge -- sh -c 'echo "Hello" > /tmp/test.txt'
kubectl get pod challenge -o wide
kubectl logs challenge --tail=10
kubectl delete pod challenge
```

```bash
# Challenge solution check: prove each requested result explicitly
kubectl run challenge --image=nginx:1.25 --labels="app=web,env=test"
kubectl wait --for=condition=ready pod/challenge --timeout=60s
kubectl exec challenge -- sh -c 'echo "Hello" > /tmp/test.txt'
kubectl exec challenge -- cat /tmp/test.txt
kubectl get pod challenge -o jsonpath='{.status.podIP}'
kubectl logs challenge
kubectl delete pod challenge
```

```bash
# Probe inspection drill: collect readiness and liveness evidence
kubectl describe pod webapp | grep -A20 "Conditions:"
kubectl describe pod webapp | grep -A20 "Events:"
kubectl get pod webapp -o jsonpath='{.status.containerStatuses[*].ready}'
```

```bash
# Lifecycle inspection drill: compare phase, container state, and restart count
kubectl get pod webapp
kubectl get pod webapp -o jsonpath='{.status.phase}'
kubectl get pod webapp -o jsonpath='{.status.containerStatuses[*].restartCount}'
kubectl describe pod webapp | grep -A8 "Last State"
```

**Card A: Two containers in one pod can both bind port 8080, because each container has its own IP.** An engineer places two web services inside the same pod manifest and configures both processes to listen on port 8080. The team assumes each container receives an independent network namespace and unique IP address, allowing identical ports to coexist without socket collisions.

<details>
<summary>Check your prediction</summary>

Failure layer: Pod network namespace boundary versus independent container networking conflation. Next action: understand that containers in the same pod share a single network namespace and one pod IP, so they communicate over localhost and cannot bind the same port; the second container fails with a bind error such as `address already in use`; two different pods can both listen on port 8080 because each pod receives its own distinct IP address; configure co-located containers in the same pod to use distinct port numbers, or separate the workloads into distinct pods if they must each bind port 8080.

</details>

**Card B: `restartPolicy: OnFailure` restarts a container that exits 0, because the pod is supposed to keep running.** An operator writes a batch processing pod with `restartPolicy: OnFailure` and notices that the worker process exits cleanly after completing its calculation. The engineer expects kubelet to restart the container immediately to keep the pod running continuously alongside long-lived services.

<details>
<summary>Check your prediction</summary>

Failure layer: Pod restart policy semantics versus process exit code evaluation conflation. Next action: understand that exit code 0 indicates clean, successful completion, so `restartPolicy: OnFailure` leaves the container stopped and transitions the pod to `Completed` without incrementing `RESTARTS`; kubelet restarts containers on exit code 0 only when `restartPolicy: Always` is configured; `OnFailure` restarts containers only on non-zero exit codes; choose `restartPolicy: Always` for long-running daemons that must continuously run, and use `OnFailure` or `Never` for run-to-completion batch tasks.

</details>

**Card C: A failing readiness probe restarts the container, because the pod is not ready.** A developer observes that an application pod fails its readiness check when an external database connection temporarily drops. The developer assumes that kubelet will kill and recreate the unhealthy container to restore normal serving capacity across the cluster.

<details>
<summary>Check your prediction</summary>

Failure layer: Readiness probe traffic filtering versus liveness probe process remediation conflation. Next action: understand that a failing readiness probe never causes kubelet to restart the container; the pod remains in `Running` status with its `READY` column decremented (such as `0/1`), and the endpoint controller removes the pod IP from matching Service endpoints so it stops receiving client requests; kubelet restarts a container only when a liveness probe or startup probe fails; use readiness probes to isolate temporarily overwhelmed or disconnected workloads, and reserve liveness probes for unrecoverable deadlocks.

</details>

**Card D: A pod IP is a stable address, so other applications should call it directly.** A platform team discovers that backend microservices can reach each other directly using internal pod IP addresses. They hardcode these specific IP values into upstream client configuration files to bypass service discovery abstractions and avoid extra routing hops.

<details>
<summary>Check your prediction</summary>

Failure layer: treating a pod IP as a durable client address. Next action: use the pod IP only as a short-lived debugging handle. A container restart inside the same pod keeps that IP. Deleting the pod and creating a replacement assigns a new IP. Point clients at a Service.

</details>

**Success Criteria**:

- [ ] Can create pods with imperative commands
- [ ] Can generate YAML with `--dry-run=client -o yaml`
- [ ] Can explain pod lifecycle phases and restart-policy behavior from observed output
- [ ] Can debug with `kubectl get`, `describe`, `logs`, and `exec` in the right order
- [ ] Can create multi-container pods with init containers, sidecars, and shared volumes
- [ ] Can choose readiness, liveness, and startup probes based on failure consequences

---

## Sources

- [Pods](https://kubernetes.io/docs/concepts/workloads/pods/) — Backs pod fundamentals: pods as the smallest deployable unit, one-or-more container model, shared network namespace, shared storage, co-location, and the pod abstraction used by higher-level workload controllers.
- [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — Backs Deployment behavior, Deployment-to-ReplicaSet-to-Pod ownership, rollout strategy, rolling updates, maxSurge/maxUnavailable behavior, rollout history, pause/resume, and rollback concepts.
- [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/) — Backs one-pod-per-node semantics, automatic coverage of added nodes, common node-level use cases, selective node placement via nodeSelector/affinity, and DaemonSet toleration behavior.
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) — Backs stable pod identity, ordinal naming, stable storage via volumeClaimTemplates, ordered deployment and rolling updates, headless Service requirements, and DNS/network identity behavior.
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/) — Backs run-to-completion semantics, backoffLimit, restartPolicy constraints, completions, parallelism, pod replacement on failure, and batch workload behavior distinct from Deployments.
- [Security Context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/) — The Kubernetes security-context task page directly defines the field and documents the exact example settings used here.
- [Pod Lifecycle](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle) — Supports claims about Pod phases, scheduling/binding terminology, graceful termination, terminationGracePeriodSeconds, preStop hook execution during shutdown, and Pod resize status conditions in v1.35.
- [Init Containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/) — Backs init-container ordering, run-to-completion behavior, differences from app containers, and pod startup sequencing before main containers begin.
- [Liveness, Readiness, and Startup Probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — Backs probe semantics, differences between liveness/readiness/startup probes, and how kubelet reacts to failing probes or holds readiness during startup.
- [kubectl run](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_run/) — Backs the imperative pod creation and `--dry-run=client -o yaml` workflow used for fast manifest generation.

## Next Module

[Module 2.2: Deployments & ReplicaSets](../module-2.2-deployments/) - Rolling updates, rollbacks, and scaling.
