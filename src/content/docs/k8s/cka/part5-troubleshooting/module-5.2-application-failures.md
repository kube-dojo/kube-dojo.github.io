---
revision_pending: false
title: "Module 5.2: Application Failures"
slug: k8s/cka/part5-troubleshooting/module-5.2-application-failures
sidebar:
  order: 3
lab:
  id: cka-5.2-application-failures
  url: https://killercoda.com/kubedojo/scenario/cka-5.2-application-failures
  duration: "45 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Most common troubleshooting scenarios
>
> **Time to Complete**: 45-55 minutes
>
> **Prerequisites**: Module 5.1 (Troubleshooting Methodology), Module 2.1-2.7 (Workloads)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Diagnose** application failures by connecting Pod phase, container state, Events, logs, and exit codes to a specific root cause.
- **Fix** application failures caused by wrong images, missing ConfigMaps, missing Secrets, incorrect probes, and resource limits.
- **Debug** multi-container Pod failures by identifying the failing app container or init container before choosing a command.
- **Trace** Deployment rollout failures from a stalled rollout symptom through ReplicaSet, Pod, and container evidence.

---

## Why This Module Matters

Hypothetical scenario: you are the administrator on duty during a release window, and a team tells you that their new web Deployment is "down" even though the YAML applied without errors. The first Pod shows `ImagePullBackOff`, the second Pod is stuck in `ContainerCreating`, and a third Pod briefly reaches `Running` before returning to `CrashLoopBackOff`. None of those states tells you the full answer by itself, but each one tells you where Kubernetes was in the startup path when the failure became visible.

Application failure troubleshooting is where Kubernetes stops feeling like a collection of object definitions and starts behaving like an operating system for distributed processes. The scheduler, kubelet, container runtime, registry, volume plugins, probes, and controller loops all leave evidence in different places. If you jump straight to editing YAML, you may fix the symptom that happened to be visible first while missing the root cause that will return on the next rollout.

This module teaches a repeatable diagnostic path for the failures you will meet most often in the CKA exam and in day-to-day operations. You will learn how to move from Pod phase to Events, from Events to container state, from container state to previous logs, and from logs to the exact configuration, image, resource, or probe mistake that needs correction. The goal is not to memorize every status string; the goal is to build a habit of asking which Kubernetes component was trying to do work, what it reported, and what object you should inspect next.

The restaurant kitchen analogy is still useful, provided we use it carefully. A Pod is like an order moving through a kitchen: the order must be accepted, ingredients must be available, prep steps must complete, the dish must stay hot, and the waiter must know when it is ready to serve. A bad image is a bad recipe, a missing ConfigMap is a missing ingredient, an OOM kill is a cook running out of counter space, and a probe mistake is a waiter asking whether the dish is ready before it has finished cooking.

The same analogy also explains why ordering matters during troubleshooting. If the kitchen never received the order, checking whether the chef seasoned the dish is wasted effort. If the ingredients never arrived, tasting the sauce is impossible. Kubernetes gives you similar checkpoints, and disciplined operators honor those checkpoints before chasing application-level theories. That discipline matters under exam pressure because each minute spent in the wrong layer reduces the time available for the simple fix.

You should also notice the difference between repair and explanation. Repair gets the workload healthy again, but explanation proves why the chosen repair was correct. A strong administrator can say, "The Pod was scheduled, kubelet could not mount a ConfigMap volume, Events named `app-settings`, the ConfigMap was missing in this namespace, and creating it allowed the container to start." That sentence is more valuable than "I created a ConfigMap and it worked," because it can be reviewed, taught, and repeated.

## Reading the Pod Startup Path

Kubernetes surfaces application failures as status words, but those words are shorthand for checkpoints in a longer path. A Pod starts with scheduling, then kubelet preparation, then image pulls and volume setup, then init containers, then app containers, then readiness gates. Treating those checkpoints as a timeline prevents a common beginner mistake: looking at container logs when the container has never started, or editing a Deployment image when the scheduler never found a node.

The startup sequence below is the first protected diagnostic asset from the original lesson. Keep it in mind as a map rather than as a list of commands. When the Pod is `Pending`, the scheduler and cluster capacity are the likely focus. When the Pod is stuck during creation, kubelet preparation, image pulling, volume mounting, ConfigMaps, Secrets, or CNI setup become more likely. When the Pod has a restart count, the application process or a liveness probe has entered the story.

This timeline also helps you interpret missing evidence. Empty application logs are meaningful only if the container actually started. No restart count is meaningful only if the Pod reached the stage where a process could restart. A Deployment with unavailable replicas is meaningful only after you connect it to the Pods created by the newest ReplicaSet. Absence of evidence is not the same thing as evidence of absence; it often means you are asking the wrong layer for information.

```text
┌──────────────────────────────────────────────────────────────┐
│                    POD STARTUP SEQUENCE                       │
│                                                               │
│   1. Scheduling     2. Preparation      3. Startup           │
│   ┌──────────┐     ┌──────────────┐    ┌──────────────┐     │
│   │ Pending  │────▶│ Container    │───▶│ Init         │     │
│   │          │     │ Creating     │    │ Containers   │     │
│   └──────────┘     └──────────────┘    └──────────────┘     │
│        │                  │                   │              │
│        ▼                  ▼                   ▼              │
│   • Node selection   • Pull images      • Run in order      │
│   • Resource check   • Mount volumes    • Each must exit 0  │
│   • Taints/affinity  • Setup network    • Sequential only   │
│                                                               │
│   4. Running         5. Ready                                │
│   ┌──────────────┐  ┌──────────────┐                        │
│   │ Main         │─▶│ Readiness    │                        │
│   │ Containers   │  │ Probes Pass  │                        │
│   └──────────────┘  └──────────────┘                        │
│        │                   │                                 │
│        ▼                   ▼                                 │
│   • Start all         • Pod marked Ready                    │
│   • Run probes        • Added to Service                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

The fastest first command is usually `kubectl describe pod`, not because it is elegant, but because it joins several sources of truth in one place. It shows scheduling decisions, volume mount failures, image pull messages, probe failures, restart reasons, and recent Events. If the Pod is Pending, this command tells you whether the scheduler rejected every node because of requests, taints, selectors, affinity, or persistent volume constraints.

In Kubernetes 1.35 and current exam-style clusters, Events remain one of the highest-signal sources for startup failures because they are emitted by the components attempting the work. The scheduler explains why placement failed. Kubelet explains why preparation failed. The container runtime reports pull and start problems through kubelet. Controllers explain rollout progress at a higher level. Reading Events is not a beginner shortcut; it is how you ask the responsible component to describe what it just tried.

```bash
# Check why pod is pending
kubectl describe pod <pod> | grep -A 10 Events
```

Pending is a scheduling problem until evidence proves otherwise. The scheduler does not ask whether a node has free memory in the casual sense; it evaluates declared requests, taints, affinity, selectors, and volume rules. That is why a node may have unused physical memory while the scheduler still reports `Insufficient memory`: previously scheduled Pods have already reserved the allocatable budget through their requests.

The practical trap is to treat Pending as a reason to change container internals. An image tag, command, environment variable, or liveness probe does not matter until a node has accepted the Pod. If Events mention requests, the repair belongs to resource requests or cluster capacity. If Events mention taints, the repair belongs to tolerations or node selection. If Events mention PVC binding, the repair belongs to storage. This keeps the fix close to the layer that rejected the Pod.

| Message | Cause | Solution |
|---------|-------|----------|
| `0/3 nodes available` | No suitable nodes | Check node taints, affinity rules |
| `Insufficient cpu` | Not enough CPU | Reduce requests or add capacity |
| `Insufficient memory` | Not enough memory | Reduce requests or add capacity |
| `node(s) had taint that pod didn't tolerate` | Taints blocking | Add tolerations or remove taints |
| `node(s) didn't match node selector` | nodeSelector mismatch | Fix labels or selector |
| `persistentvolumeclaim not found` | PVC missing | Create PVC |
| `persistentvolumeclaim not bound` | No matching PV | Check StorageClass, create PV |

The supporting commands should match the hypothesis produced by Events. If Events mention insufficient resources, inspect node allocation and metrics. If Events mention taints or node selectors, inspect labels and taints. If Events mention PVC binding, inspect the claim and its StorageClass. Copying a generic command bundle into the terminal is slower than using the Event message as a searchlight.

```bash
# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"
kubectl top nodes

# Check node taints
kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints[*].key'

# Check node labels (for nodeSelector)
kubectl get nodes --show-labels
```

`ContainerCreating` means the scheduler has already placed the Pod on a node, so the investigation moves from the scheduler to kubelet preparation. At this stage kubelet may be pulling images, mounting volumes, reading ConfigMaps and Secrets, preparing the network namespace, and asking the container runtime to create containers. Logs are often empty here because the main process has not started yet.

Kubelet preparation failures are often caused by dependencies that look small in YAML but are mandatory at runtime. A single misspelled Secret name can prevent an otherwise perfect image from starting. A PVC that is not bound can block the volume mount. A private image without a usable pull Secret can stop the process before your application code exists. The YAML may be syntactically valid while still describing a workload that cannot be materialized on the node.

Pause and predict: if a Pod is stuck in `ContainerCreating` for several minutes and the application logs are empty, which external dependency is most likely blocking the transition from Pod specification to runnable container? Your answer should point to something kubelet must prepare before the process can exist, such as an image pull, a volume mount, a missing Secret, a missing ConfigMap, or a network setup failure.

```bash
# Always check Events first
kubectl describe pod <pod> | grep -A 15 Events
```

The table below preserves the original preparation-failure map, but the important habit is to read the message as a component clue. `ImagePullBackOff` points toward the registry and image reference, while `MountVolume.SetUp failed` points toward storage or projected configuration. A missing ConfigMap or Secret is not an application bug yet; it is Kubernetes refusing to start the container because the declared dependency does not exist.

| Message | Cause | Solution |
|---------|-------|----------|
| `pulling image` (stuck) | Slow/large image | Wait, or use smaller image |
| `ImagePullBackOff` | Wrong image name | Fix image reference |
| `ErrImagePull` | Registry auth failed | Check imagePullSecrets |
| `MountVolume.SetUp failed` | Volume mount issue | Check PVC, ConfigMap, Secret exists |
| `configmap not found` | Missing ConfigMap | Create ConfigMap |
| `secret not found` | Missing Secret | Create Secret |
| `network not ready` | CNI issues | Check CNI pods |

The next commands verify the dependency named by the Event instead of guessing. Namespaces matter here: a ConfigMap or Secret with the same name in another namespace is invisible to the Pod. In the exam, this detail often separates a quick fix from a long detour, because `kubectl get configmap <name>` without `-n` may query the wrong namespace and create a false negative.

```bash
# Check image pull issues
kubectl get events --field-selector involvedObject.name=<pod>

# Check if ConfigMap/Secret exists
kubectl get configmap <name>
kubectl get secret <name>

# Check PVC status
kubectl get pvc
kubectl describe pvc <name>
```

## Diagnosing CrashLoopBackOff and Exit Evidence

`CrashLoopBackOff` is not the root cause; it is Kubernetes protecting the node and registry from a container that repeatedly exits. The kubelet starts the container, observes the process terminate, waits with exponential backoff, and tries again while the Pod remains under the owning controller. Your job is to find the last terminated state and the previous logs before the next restart erases the most useful context from the current process view.

A useful mental model is to separate "Kubernetes could not start the process" from "Kubernetes started the process and the process did not stay alive." `ImagePullBackOff`, missing volumes, and missing required Secrets usually sit in the first category. `CrashLoopBackOff` usually sits in the second category, though probes can blur the line by killing a process Kubernetes already started. That distinction tells you whether to inspect dependency Events or process evidence first.

The protected cycle diagram is worth reading slowly. The backoff starts small, grows after repeated crashes, and caps at five minutes between restart attempts. After a container runs successfully for about ten minutes, Kubernetes resets the restart backoff, which is why a newly fixed configuration may still appear delayed if the Pod has been failing for a long time.

```text
┌──────────────────────────────────────────────────────────────┐
│                   CRASHLOOPBACKOFF CYCLE                      │
│                                                               │
│   Container Start ──▶ Container Crash ──▶ Wait ──┐           │
│         ▲                                         │           │
│         └─────────────────────────────────────────┘           │
│                                                               │
│   Backoff Times:                                              │
│   1st crash: wait 10s                                         │
│   2nd crash: wait 20s                                         │
│   3rd crash: wait 40s                                         │
│   4th crash: wait 80s                                         │
│   5th crash: wait 160s                                        │
│   6th+ crash: wait 300s (5 min max)                          │
│                                                               │
│   After 10 minutes of running successfully, timer resets     │
└──────────────────────────────────────────────────────────────┘
```

The practical sequence is status, Events, current state, previous logs, and exit code. Status tells you whether a restart loop exists. Events often show probe kills, OOM kills, and image or mount messages. Current state tells you whether the container is waiting, running, or terminated now. Previous logs and `lastState` tell you what happened to the last process instance, which is usually the one that contains the real failure.

The order matters because each command answers a narrower question than the one before it. `kubectl get pod` tells you that a restart loop exists, but it does not prove why. `kubectl describe pod` tells you whether Kubernetes observed OOM, probe, or scheduling evidence. Previous logs tell you whether the application reported its own reason before exiting. Exit code then helps classify that reason without replacing the logs. Skipping directly to the last command produces brittle conclusions.

Pause and predict: if a Pod has restarted many times but currently shows `Running`, where would you look for the failure that caused the earlier restart? The current logs may only show the newest process instance, so the stronger answer is previous logs plus the container's `lastState.terminated` details, with `-c` used when the Pod has multiple containers.

```bash
# Step 1: Check pod status and restart count
kubectl get pod <pod>
# Look at RESTARTS column

# Step 2: Check events
kubectl describe pod <pod> | grep -A 10 Events

# Step 3: Check current container state
kubectl describe pod <pod> | grep -A 10 "State:"

# Step 4: Check PREVIOUS container logs (crucial!)
# For multi-container pods, identify the failing container and specify it with -c
# kubectl get pod <pod> -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\t"}{.restartCount}{"\n"}{end}'
kubectl logs <pod> --previous # add -c <container-name> if multiple containers

# Step 5: Check exit code
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
```

Exit codes are compact evidence, not magic answers. Code `1` usually means the application chose to exit with a generic error, so logs and configuration become important. Code `127` points toward a command or entrypoint that does not exist in the image. Code `137` means SIGKILL, which may be an OOM kill or another forced termination, so you must check the termination reason rather than assuming every `137` is a memory leak.

| Exit Code | Signal | Meaning | Common Cause |
|-----------|--------|---------|--------------|
| 0 | - | Success | Normal exit (shouldn't cause CrashLoop) |
| 1 | - | Application error | App logic error, missing config |
| 2 | - | Misuse of shell builtin | Script error |
| 126 | - | Command not executable | Permission issue |
| 127 | - | Command not found | Wrong entrypoint/command |
| 128+N | Signal N | Killed by signal | Fatal error raised by OS |
| 137 | SIGKILL (9) | Force killed | OOMKilled, or `kill -9` |
| 139 | SIGSEGV (11) | Segmentation fault | Application bug |
| 143 | SIGTERM (15) | Graceful termination | Normal shutdown |
| 255 | - | Unknown/Custom error | Application specific fatal error |

OOMKilled is especially easy to misread because the visible symptom may look like an application crash. Kubernetes enforces the container memory limit through the node's container runtime and kernel memory controls; when the process exceeds that limit, it can be killed even if the node still has memory available. The fix might be increasing the limit, lowering the application baseline, changing startup behavior, or splitting a heavy workload from the request-serving container.

The CKA exam usually rewards the direct correction, but production work requires one more question: why was this limit wrong for this workload? A startup spike may call for a higher limit or smaller preload. A true leak may require rollback or code repair. A batch task placed in a request-serving Deployment may need a Job or separate worker. The Kubernetes symptom tells you the enforcement event; it does not automatically choose the long-term capacity design.

```bash
# Check for OOMKilled status
kubectl describe pod <pod> | grep -i oom

# Check memory limits
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].resources.limits.memory}'

# Check actual memory usage (if pod is running)
kubectl top pod <pod>

# Fix: Increase memory limit
kubectl patch deployment <name> -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"memory":"512Mi"}}}]}}}}'
```

The most useful CrashLoop diagnosis combines three views: what the process logged, why Kubernetes says it terminated, and what the Pod spec asked Kubernetes to run. If the logs say a file is missing and the spec mounts that file from a ConfigMap key, you have a configuration dependency failure. If the exit code says command not found and the spec overrides `command`, you probably replaced the image entrypoint incorrectly.

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Exit code 1 | App error | Check logs, fix application |
| Exit code 127 | Command not found | Fix `command` or `args` in spec |
| Exit code 137 + OOMKilled | Memory exceeded | Increase memory limit |
| Exit code 137 no OOM | Killed externally | Check liveness probe |
| Container exits immediately | No foreground process | Add `sleep infinity` or fix command |
| Logs show "file not found" | Missing ConfigMap/Secret | Verify mounts exist |
| Logs show "permission denied" | Security context | Fix runAsUser or fsGroup |

Multi-container Pods add one more layer: the failing container may not be the first container in the spec. Sidecars, init containers, and helper containers all have separate logs and restart counts. Before you run `kubectl logs`, list the container statuses and choose the container whose restart count or waiting reason matches the symptom. This avoids the misleading experience of reading healthy sidecar logs while the app container is failing beside it.

## Fixing Image and Registry Failures

Image pull failures happen before the application process exists, so they leave evidence in Events rather than in application logs. Kubernetes first reports an immediate pull failure, commonly `ErrImagePull`, and then moves to `ImagePullBackOff` after repeated failures. The same status can come from a typoed tag, a private registry without credentials, a registry outage, or a rate limit, so the Event message is more important than the short Pod status.

This is also why deleting the Pod is rarely the first useful action. If the owning template still contains the same bad image reference or missing pull Secret, a new Pod repeats the same failure and may even reset the evidence you were about to read. Fix the reference, credentials, or registry path on the controller template, then let the controller create a new Pod from corrected desired state. The controller is the source of recurrence, so it is usually the source of repair.

```text
┌──────────────────────────────────────────────────────────────┐
│                  IMAGE PULL ERROR FLOW                        │
│                                                               │
│   Attempt Pull ──▶ ErrImagePull ──▶ ImagePullBackOff         │
│        │              │                    │                  │
│        │              │                    │                  │
│   (Success)      (First failure)    (Repeated failures)      │
│                                                               │
│   ErrImagePull causes:                                        │
│   • Image doesn't exist                                       │
│   • Registry unreachable                                      │
│   • Authentication failed                                     │
│   • Rate limited (Docker Hub)                                │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Start with the exact error text from the pull attempt. `manifest unknown` means the repository or tag cannot be found. `unauthorized` means credentials are missing or invalid. Network timeouts point toward registry reachability, DNS, proxy, or node egress. `toomanyrequests` usually means the registry is rate limiting unauthenticated or high-volume pulls.

```bash
# Check events for specific error
kubectl describe pod <pod> | grep -A 5 "Failed to pull"

# Common error messages:
# "manifest unknown" - Image tag doesn't exist
# "unauthorized" - Registry auth failed
# "timeout" - Registry unreachable
# "toomanyrequests" - Rate limited
```

For a wrong image name or tag, prefer updating the owning controller instead of editing the failed Pod. Standalone Pods are disposable in labs, but real workloads usually come from Deployments, StatefulSets, Jobs, or CronJobs. If you change only the created Pod, the controller may recreate the same failure from the original template.

Image names carry several pieces of meaning at once: registry host, repository path, image name, tag, and sometimes digest. A typo in any part can produce a pull failure that looks similar at the Pod-status level. Before changing a tag, read the full reference from the Pod or controller and compare it with the intended release artifact. In clusters using admission policies or image mirrors, also remember that the reference you wrote may be transformed or validated before kubelet pulls it.

```bash
# Check current image
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].image}'

# Fix with set image
kubectl set image deployment/<name> <container>=<correct-image>

# Or edit directly
kubectl edit deployment <name>
```

Private registry failures require matching the Secret, namespace, ServiceAccount, and Pod template. A Docker registry Secret in the wrong namespace is invisible to the Pod. A Secret that exists but is not referenced through `imagePullSecrets` is also invisible during the pull. Patching the default ServiceAccount can be a good namespace-level fix in a lab, while production teams often make that choice explicitly through workload-specific ServiceAccounts.

```bash
# Create registry secret
kubectl create secret docker-registry regcred \
  --docker-server=registry.example.com \
  --docker-username=user \
  --docker-password=your-registry-password-here \
  --docker-email=user@example.com

# Add to pod spec
kubectl patch serviceaccount default -p '{"imagePullSecrets":[{"name":"regcred"}]}'

# Or add to specific deployment
kubectl patch deployment <name> -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"regcred"}]}}}}'
```

Rate limiting is different from a bad image reference because the same image may work for one node and fail for another depending on pull history and credentials. Authentication, internal registries, pre-pulled images, and alternative public registries are all valid mitigations, but the right choice depends on cluster policy. In an exam environment, the most likely fix is a corrected image reference or an existing pull secret, not a registry architecture redesign.

```bash
# Option 1: Use authenticated pulls
kubectl create secret docker-registry dockerhub \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=<username> \
  --docker-password=<TOKEN>

# Option 2: Use alternative registry (e.g., quay.io, public.ecr.aws)
# nginx:latest -> public.ecr.aws/nginx/nginx:latest
```

## Debugging Configuration, Secrets, and Runtime Inputs

Configuration failures sit on the boundary between Kubernetes and the application. Kubernetes can detect missing ConfigMaps, missing Secrets, missing volume sources, and invalid references before the container starts. It cannot always detect a wrong key name, an unexpected value, or an application-specific environment variable requirement; those may appear only after the process begins and exits with an application error.

That boundary is the reason configuration problems can produce different visible states. A missing mounted ConfigMap can leave the Pod stuck during container creation, while a present ConfigMap with a missing application key can let the container start and crash. An optional key reference might allow startup with an empty or absent value, shifting the failure into application behavior. Good debugging asks whether Kubernetes rejected the dependency or the application rejected the data.

Pause and predict: what Pod status would you expect if a Pod references a Secret that does not exist in the namespace? The answer depends on how the Secret is consumed, but the usual sign is a container-creation failure with Events saying the Secret could not be found, because kubelet cannot materialize the environment or mounted volume promised by the Pod spec.

The diagnosis begins by reading the Pod spec for declared inputs and then checking whether those objects exist in the same namespace. For mounted ConfigMaps and Secrets, the failure may appear as a volume setup error. For environment variables sourced through `valueFrom`, Kubernetes may block startup if a required key reference cannot be resolved unless the reference is optional.

```bash
# Check what ConfigMaps/Secrets the pod needs
kubectl get pod <pod> -o yaml | grep -A 5 "configMap\|secret"

# Verify they exist
kubectl get configmap
kubectl get secret

# Check specific one
kubectl describe configmap <name>
```

Creating the missing object can be a valid emergency fix when the desired data is known and safe to create. In a controlled exam lab, a literal key is often enough to prove you identified the dependency. In production, you should confirm ownership and data source before inventing values, because an application that starts with the wrong configuration may fail more quietly than one that refuses to start.

Secrets deserve special caution because their presence can satisfy Kubernetes while their contents remain wrong. A Secret named correctly but containing an old password, wrong key name, or value encoded from the wrong source may let the Pod start and fail against the external dependency. Kubernetes does not authenticate your database password while creating the Pod. It only projects bytes into the container, so application logs and dependency telemetry may still be needed after Kubernetes accepts the object.

```bash
# Create missing ConfigMap
kubectl create configmap <name> --from-literal=key=value

# Create missing Secret
kubectl create secret generic <name> --from-literal=password=your-password-here

# If you have the data file
kubectl create configmap <name> --from-file=config.yaml
kubectl create secret generic <name> --from-file=credentials.json
```

Wrong keys are subtler than missing objects. A ConfigMap named `app-settings` may exist and still lack the `REDIS_HOST` key that the container expects. If the application reads a mounted file path, logs might show `file not found`. If it reads an environment variable, logs might show a missing variable error and exit code `1`, which means Kubernetes successfully started the process but the application rejected its inputs.

```bash
# Check what keys exist in ConfigMap
kubectl get configmap <name> -o yaml

# Check pod's expected keys
kubectl get pod <pod> -o yaml | grep -A 10 configMapKeyRef

# Compare expected vs actual
```

Patching a ConfigMap changes the object, but it does not always update a running application immediately. Environment variables are captured when the container starts, so a Pod must be recreated to see changed values. Projected volumes can update on the node, but many applications read configuration only at startup. A good troubleshooting fix includes both correcting the data and ensuring the workload consumes the corrected data.

```bash
# Add missing key to ConfigMap
kubectl patch configmap <name> -p '{"data":{"missing-key":"value"}}'

# Or recreate
kubectl create configmap <name> --from-literal=key1=val1 --from-literal=key2=val2 --dry-run=client -o yaml | kubectl apply -f -
```

Environment variable debugging is most useful after the container is running or briefly running. Compare the values inside the process environment with the values declared in the Pod template. If the Pod crashes too quickly for `exec`, use previous logs and the Pod spec instead. In multi-container Pods, remember that each container has its own environment and mounts.

```bash
# Check environment variables in running container
kubectl exec <pod> -- env

# Check what's defined in spec
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].env[*]}'

# Common issue: ConfigMap key name doesn't match env var name
# Check with:
kubectl get pod <pod> -o yaml | grep -A 5 valueFrom
```

## Tracing Deployment Rollout Failures

A Deployment rollout failure is a controller-level symptom built from Pod-level causes. The Deployment controller creates a new ReplicaSet from the updated Pod template, scales it up, and waits for the new Pods to become available while preserving availability according to the rollout strategy. If the new Pods never become Ready, the rollout stalls even though the old ReplicaSet may keep serving traffic.

The Deployment controller is intentionally conservative because availability is part of the API contract. During a rolling update, it can keep old Pods running while trying to create new Pods, and this gives you room to diagnose without immediately taking the service completely offline. That same behavior can make failures look confusing: the Service still works for some users, the Deployment says progress is incomplete, and only the newest Pods show the actual broken template.

Stop and think: if `kubectl rollout status deployment/<name>` hangs, what object should you describe next to find the actual creation errors? The Deployment conditions are useful, but the newest ReplicaSet and its Pods usually contain the concrete image, mount, probe, scheduling, or crash evidence that explains why availability is not progressing.

The first pass is to read the Deployment, then its ReplicaSets, then the Pods owned by the newest ReplicaSet. Do not assume the Deployment itself has the root cause. It often reports a high-level condition such as `ProgressDeadlineExceeded`, while the Pod Events show the exact missing Secret, bad image tag, or failing readiness probe.

```bash
# Check deployment status
kubectl get deployment <name>
kubectl describe deployment <name>

# Check ReplicaSets
kubectl get rs -l app=<name>

# Check pods from new ReplicaSet
kubectl get pods -l app=<name>
```

The rollout-state diagram from the original module captures the operational risk. A rollout can be partially successful, with old Pods still carrying traffic while new Pods fail. That is a safer failure mode than replacing everything at once, but it can still leave you under capacity. Your decision is whether to fix forward quickly, rollback, or pause and investigate while the previous version remains available.

```text
┌──────────────────────────────────────────────────────────────┐
│                  DEPLOYMENT ROLLOUT STATES                    │
│                                                               │
│   Progressing                 Stuck                           │
│   ┌──────────────┐           ┌──────────────┐                │
│   │ New RS       │           │ New RS       │                │
│   │ scaling up   │           │ pods failing │                │
│   └──────────────┘           └──────────────┘                │
│         │                          │                          │
│         ▼                          ▼                          │
│   ┌──────────────┐           ┌──────────────┐                │
│   │ Old RS       │           │ Old RS       │                │
│   │ scaling down │           │ still running│                │
│   └──────────────┘           └──────────────┘                │
│                                                               │
│   Rollout waits for new pods to become Ready                 │
│   If pods never Ready, rollout stalls                        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Finding the newest ReplicaSet is a practical shortcut when labels are consistent. The command below sorts ReplicaSets by creation timestamp, describes the newest one, and then inspects failing Pods. In real clusters, label hygiene matters: if a selector is broad or inconsistent, the command may include more than the Deployment you intended, so always confirm names before making changes.

ReplicaSets are valuable because they preserve rollout history in object form. The old ReplicaSet represents the previous Pod template, and the new ReplicaSet represents the attempted template. Comparing their images, environment references, probes, and resource settings can reveal the exact change that introduced the failure. You do not need to diff every line during a timed task, but noticing that the new ReplicaSet alone contains a bad tag or new probe often shortens the investigation dramatically.

```bash
# Check deployment conditions
kubectl describe deployment <name> | grep -A 10 Conditions

# Check new ReplicaSet's pods
NEW_RS=$(kubectl get rs -l app=<name> --sort-by='.metadata.creationTimestamp' -o name | tail -1)
kubectl describe "$NEW_RS"

# Check why pods aren't ready
kubectl get pods -l app=<name> | grep -v Running
kubectl describe pod <failing-pod>
```

Rollback is a service-restoration tool, not an admission of defeat. If the new revision is breaking capacity and the old revision is known good, `kubectl rollout undo` moves the Deployment back to the previous Pod template while preserving the controller's normal behavior. After service is stable, you can investigate the failed revision with less pressure and build a corrected forward fix.

```bash
# Check rollout history
kubectl rollout history deployment/<name>

# Rollback to previous version
kubectl rollout undo deployment/<name>

# Rollback to specific revision
kubectl rollout undo deployment/<name> --to-revision=2

# Verify rollback
kubectl rollout status deployment/<name>
```

Fix-forward is appropriate when the root cause is obvious and safe to correct, such as a typoed image tag or a missing ConfigMap key. Rollback is better when the failure is ambiguous, customer-facing capacity is low, or the fix requires application code. Forced restarts and scale-down operations are powerful, but they can hide evidence and interrupt healthy Pods, so keep them as deliberate choices rather than reflexes.

```bash
# Option 1: Fix the issue and let rollout continue
kubectl set image deployment/<name> <container>=<fixed-image>

# Option 2: Rollback
kubectl rollout undo deployment/<name>

# Option 3: Force restart (deletes and recreates pods)
kubectl rollout restart deployment/<name>

# Option 4: Scale down then up (nuclear option)
kubectl scale deployment/<name> --replicas=0
kubectl scale deployment/<name> --replicas=3
```

## Readiness, Liveness, and Probe-Caused Failures

Probes are health contracts between Kubernetes and your container, and a wrong contract can create a failure that looks like an application bug. Liveness answers, "Should kubelet restart this container?" Readiness answers, "Should Services send traffic to this Pod?" Startup probes answer, "Should liveness wait while this slow-starting process becomes alive enough to evaluate?" Mixing these meanings is one of the fastest ways to create self-inflicted outages.

Health endpoints should be designed with their Kubernetes action in mind. A liveness endpoint should fail only when restarting the container is likely to improve the situation. A readiness endpoint can be stricter because its failure merely removes the Pod from traffic. A startup probe can be patient because its purpose is to give slow initialization a fair chance. When all three endpoints point to the same expensive dependency check, a dependency outage can trigger restarts instead of graceful traffic removal.

The preserved probe diagram shows the two most common probe consequences. A failed liveness probe restarts the container, which can cause CrashLoopBackOff when the probe is too aggressive. A failed readiness probe removes the Pod from Service endpoints, which can make the application appear down even though the process is running and logs look healthy.

```text
┌──────────────────────────────────────────────────────────────┐
│                     PROBE TYPES                               │
│                                                               │
│   LIVENESS                      READINESS                     │
│   Is container alive?           Is container ready?           │
│                                                               │
│   Failure action:               Failure action:               │
│   RESTART container             REMOVE from service           │
│                                                               │
│   Use for:                      Use for:                      │
│   • Deadlock detection          • Startup dependencies        │
│   • Hung processes              • Warming caches              │
│                                                               │
│   Bad liveness config          Bad readiness config           │
│      = crash loops                 = no traffic               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Probe diagnosis starts with the configured path, port, command, timing, and Events. If Events show repeated liveness failures followed by restarts, the probe may be killing the container before the application is actually broken. If readiness fails without restarts, traffic may be blocked because the readiness endpoint returns an error, the port is wrong, or the app depends on a backend that is not ready yet.

Manual probe testing should happen from the same network perspective as the probe whenever possible. Executing a command inside the container and calling `127.0.0.1` checks the local listener and path, which is close to what an HTTP probe against the Pod IP is trying to validate. If the manual check works but Events still show failures, compare port names, container ports, scheme, timeout, and whether the endpoint sometimes exceeds the configured timeout under load.

```bash
# Check probe configuration
kubectl get pod <pod> -o yaml | grep -A 10 "livenessProbe\|readinessProbe"

# Check for probe failures in events
kubectl describe pod <pod> | grep -i "unhealthy\|probe"

# Test probe manually (nginx images ship curl, not wget)
kubectl exec <pod> -- curl -sf http://127.0.0.1:8080/health
kubectl exec <pod> -- cat /tmp/healthy
```

Probe timing is where many otherwise correct configurations fail. A Java service, database migration, cache warmup, or model-loading application may need time before it can answer `/health`. If liveness begins too early, Kubernetes restarts the container during normal startup and guarantees it never reaches readiness. A startup probe or a longer initial delay allows slow startup without weakening the long-term liveness contract.

| Issue | Symptom | Fix |
|-------|---------|-----|
| Wrong port | Probe fails, container works | Fix port in probe spec |
| Wrong path | 404 errors in events | Fix httpGet path |
| Too aggressive | Containers keep restarting | Increase timeoutSeconds, periodSeconds |
| Missing initialDelaySeconds | Fails during startup | Add initialDelaySeconds |
| App slow to start | CrashLoop at startup | Use startupProbe |

The YAML below keeps the original liveness timing example, and the numbers are intentionally readable rather than universal. The right timing depends on startup distribution, endpoint cost, and failure tolerance. Use `startupProbe` when startup is slow, use readiness for dependency and warmup gates, and reserve liveness for conditions where restart is genuinely the safest recovery action.

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30   # Wait 30s before first probe
  periodSeconds: 10         # Probe every 10s
  timeoutSeconds: 5         # Timeout after 5s
  failureThreshold: 3       # Restart after 3 failures
```

Which approach would you choose here and why: a service takes thirty seconds to load data before it can answer health checks, but after startup it can deadlock under a rare bug. A strong answer uses a startup probe to protect the normal startup window, a readiness probe to keep traffic away until the service is actually ready, and a liveness probe that detects the deadlock only after startup has completed.

## Patterns & Anti-Patterns

Good application troubleshooting patterns reduce the number of moving parts you inspect at once. You start with the lifecycle checkpoint, then pick the evidence source that matches that checkpoint, then make the smallest correction at the owning object. This is slower than guessing for the first few minutes, but it is much faster across a real incident because each observation either confirms or eliminates a class of causes.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Phase-first triage | A Pod is not healthy and the cause is unclear | Pod phase narrows the responsible component before you inspect logs or YAML | Teach the whole team the same phase-to-evidence map so handoffs are consistent |
| Previous-log capture | Restart count is greater than zero | The previous process instance usually contains the crash message | Centralized logging is helpful, but `kubectl logs --previous` remains a fast local check |
| Controller-first repair | A failed Pod belongs to a Deployment or other controller | Editing the controller template prevents the same bad Pod from being recreated | Use rollout history and GitOps records to keep emergency fixes auditable |
| Probe separation | A service has distinct alive, ready, and startup states | Each probe type has a different Kubernetes action and should test a different promise | Standardize endpoint semantics across teams without forcing identical timing |

Anti-patterns usually come from treating a status as an answer rather than as a pointer. `CrashLoopBackOff` does not say whether the process crashed because of missing configuration, bad code, OOM, or an aggressive probe. `ImagePullBackOff` does not say whether the repository is private, typoed, unreachable, or rate limited. Reliable troubleshooting keeps asking what evidence would distinguish the likely causes.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Reading only current logs in a CrashLoop | The current process may be too new or empty, while the previous instance held the error | Use `kubectl logs --previous` and inspect `lastState.terminated` |
| Editing a failed Pod from a Deployment | The Deployment recreates the same bad template on the next reconciliation | Patch or edit the Deployment, then watch the rollout |
| Treating every `137` as a memory leak | SIGKILL can come from OOM or an external kill path | Check the termination reason and Events before changing limits |
| Using liveness as a readiness test | Kubernetes restarts containers that merely need more time or dependencies | Put traffic gating in readiness and slow-start protection in startup probes |

## Decision Framework

The decision framework below is a compact way to choose the next inspection point without memorizing every possible message. First ask whether the Pod was scheduled. Then ask whether kubelet prepared the container. Then ask whether the process started and terminated. Then ask whether the process is running but not receiving traffic. Each step changes the evidence source and the likely fix.

Use the framework as a loop rather than a one-time flowchart. After you make a fix, watch the workload move to the next checkpoint and be ready for the next failure to appear. A Pod can move from `ImagePullBackOff` to `CrashLoopBackOff` after you fix the tag, because pulling the image only reveals the next problem in the application process. That is not a failed fix; it is normal layered debugging in a system with several startup gates.

| Visible Symptom | First Evidence Source | Likely Root Cause Family | Safer First Action |
|-----------------|-----------------------|--------------------------|--------------------|
| `Pending` | `kubectl describe pod` Events | Requests, taints, selectors, affinity, PVC binding | Inspect scheduler message before changing the workload |
| `ContainerCreating` | Pod Events and referenced objects | Image pull, volume mount, ConfigMap, Secret, CNI | Verify the named dependency in the same namespace |
| `ImagePullBackOff` | Failed pull Event text | Bad tag, auth, reachability, rate limit | Correct image or pull secret on the owning controller |
| `CrashLoopBackOff` | Previous logs and `lastState` | App error, command error, OOM, probe kill | Capture previous logs before deleting the Pod |
| Running but not Ready | Probe Events and endpoint state | Readiness path, port, dependency, warmup | Test the readiness endpoint from inside the container |
| Deployment rollout stalled | Deployment, newest ReplicaSet, failing Pods | New template creates unhealthy Pods | Fix forward if obvious, rollback if capacity is at risk |

Use this framework during an exam by speaking the path to yourself: "phase, Events, state, logs, owning controller." That small script keeps you from skipping to an attractive command too early. In production, the same path helps you write a clear incident note because you can show what the system reported, what object owned the failing template, and why the chosen fix addressed the root cause.

## Did You Know?

- **CrashLoopBackOff has exponential backoff**: Kubernetes commonly starts retries around 10 seconds, then 20 seconds, then 40 seconds, and eventually caps repeated container restart delays at about 5 minutes.
- **Init containers run before app containers**: if an init container fails, the main container never starts, so ordinary `kubectl logs <pod>` output can be empty until you select the init container explicitly.
- **Image pull failure statuses change over time**: a Pod can show `ErrImagePull` after an immediate pull failure and later show `ImagePullBackOff` as kubelet spaces out repeated attempts.
- **OOMKilled does not always mean a memory leak**: a container can exceed a limit during normal startup if its baseline memory requirement is higher than the configured limit.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Not checking `--previous` | The current container instance hides the crash message from the prior instance | Always inspect previous logs and `lastState.terminated` for CrashLoopBackOff |
| Ignoring init containers | The main container never starts, so its logs look empty and misleading | List init container statuses and read logs with `-c <init-container-name>` |
| Fixing symptoms instead of root cause | A visible status string feels like the answer, especially under time pressure | Use phase, Events, state, logs, and owning controller before editing |
| Using wrong resource units | CPU and memory units are easy to mistype, causing unexpected scheduling or OOM behavior | Use `m` for millicores and `Mi` or `Gi` for memory, then verify requests and limits |
| Making liveness probes too aggressive | Teams reuse readiness checks and accidentally restart slow-starting healthy containers | Add startup protection and tune delay, timeout, period, and failure threshold |
| Forgetting imagePullSecrets | Private images fail even though the Secret exists somewhere in the cluster | Put the Secret in the workload namespace and reference it from the Pod or ServiceAccount |
| Using `restartPolicy: Never` for Deployments | Run-once semantics are confused with long-running workload semantics | Use Deployments with `Always`; use Jobs for run-to-completion tasks |
| Overlooking namespace context | Commands query the default namespace and report objects missing incorrectly | Add `-n <namespace>` or set a deliberate namespace context before debugging |

## Quiz

<details>
<summary>Question 1: A new Deployment enters CrashLoopBackOff, the previous logs end with `Error: REDIS_HOST not set`, and the last exit code is `1`. What exactly failed, and where should you fix it?</summary>

The container process started successfully enough to run application code, then the application exited because a required runtime input was missing. Exit code `1` is generic, so the decisive evidence is the log message naming `REDIS_HOST`. Fix the Deployment template or the referenced ConfigMap or Secret so the environment variable exists, then restart or roll out the workload so the new container receives the corrected environment. This is not an image pull issue or a scheduler issue because the process reached application startup.
</details>

<details>
<summary>Question 2: A developer updates a Deployment image to `nginx:1.255`, and the Pod first shows `ErrImagePull` and later `ImagePullBackOff`. What should you inspect before changing anything?</summary>

Inspect the Pod Events for the exact failed pull message, because the short status does not distinguish a nonexistent tag from registry authentication, reachability, or rate limiting. If the Event says the manifest is unknown, fix the image tag on the Deployment with a valid nginx tag. If it says unauthorized, verify the image pull Secret and its namespace. The key is that no application logs exist yet, because the container image was never pulled and the process never started.
</details>

<details>
<summary>Question 3: A Pod remains Pending and Events say `0/3 nodes are available: 3 Insufficient memory`, but the nodes appear to have physical memory free. What is blocking scheduling?</summary>

The scheduler is evaluating allocatable capacity against declared memory requests, not casual free memory observed from the operating system. Existing Pods may have reserved enough memory through requests that no node has sufficient unallocated requested capacity for the new Pod. Reduce the pending Pod's request if it is too high, move or remove other workloads, or add capacity. Do not treat this as an OOMKilled problem because the container has not run yet.
</details>

<details>
<summary>Question 4: A Pod has been crashing for hours, you correct the ConfigMap it depends on, and nothing restarts immediately. How long might Kubernetes wait, and what can you do if you need a faster retry?</summary>

The restart backoff may already be at the five-minute cap, so kubelet might not start the container again until the next scheduled retry. That delay protects the node from tight restart loops, but it can make a successful fix look ineffective for a short time. If an immediate retry is safe, delete the Pod and let the owning controller recreate it from the corrected template or dependency. Preserve logs first if you still need evidence from the failed instance.
</details>

<details>
<summary>Question 5: A Deployment creates a Pod, but the main container never starts and `kubectl logs <pod>` is empty. What hidden component should you investigate?</summary>

Investigate init containers first, because Kubernetes runs them sequentially before app containers. If an init container fails or hangs, the app container process is never launched, so ordinary app logs are empty by design. Describe the Pod to see init container state, then run `kubectl logs <pod> -c <init-container-name>` for the failing init container. Fixing the main container image or command would miss the actual gate.
</details>

<details>
<summary>Question 6: A rollout is stuck midway, old Pods still serve traffic, and the newest ReplicaSet has one Pod in CrashLoopBackOff. What is the fastest safe capacity restoration?</summary>

If the service is at risk and the old revision is known good, `kubectl rollout undo deployment/<name>` is the fastest safe restoration path. It returns the Deployment template to the previous revision and lets the Deployment controller scale healthy Pods normally. After capacity is stable, inspect the failed new ReplicaSet and Pod evidence to decide whether the next fix should be image, configuration, resource, or probe related. Fix-forward is reasonable only when the cause is obvious and the remaining capacity is acceptable.
</details>

<details>
<summary>Question 7: A Java service needs thirty seconds to warm caches, but liveness checks `/health` immediately and restarts the container repeatedly. Which probe design should replace that setup?</summary>

Use a startup probe to protect the warmup period, readiness to keep traffic away until the service can answer real requests, and liveness only after startup has completed. The current liveness probe is acting too early, so Kubernetes interrupts normal initialization and creates a CrashLoopBackOff. An `initialDelaySeconds` can help, but startup probes express the intent more clearly for slow-starting containers. Readiness alone would not restart the container, and liveness alone cannot distinguish warmup from a dead process.
</details>

<details>
<summary>Question 8: A Pod named `checkout` runs two containers — `app` and `log-shipper`. The Pod shows CrashLoopBackOff, `kubectl logs checkout` prints healthy sidecar startup lines, and `kubectl get pod checkout -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\t"}{.restartCount}{"\n"}{end}'` shows `app` with restart count 4 and `log-shipper` with 0. What command finds the application crash message?</summary>

Identify the failing container first, then read its logs with `-c`. Run `kubectl describe pod checkout | grep -A5 "Last State"` to confirm which container owns the restarts, then `kubectl logs checkout -c app --previous` for the crash output. Without `-c app`, you may read the sidecar's healthy logs while the application container beside it keeps failing. If `--previous` returns no logs because the container exits instantly, rely on `describe` and the jsonpath exit code before retrying `--previous`.
</details>

## Hands-On Exercise: Application Failure Scenarios

Exercise scenario: diagnose three failing Pods in a fresh owned namespace and a failed Deployment rollout in a separate fresh namespace. For each, inspect Events and relevant state before choosing a repair. Run these deliberately broken workloads in a disposable lab environment.

### Setup

Use one Bash session for Scenarios 1, 2 and 4. Set `APP_LAB_KUBECONFIG` to the absolute path of a dedicated disposable Kubernetes 1.35 kubeconfig, `APP_LAB_CONTEXT` to its context, and `APP_LAB_CLUSTER_UID` to the `kube-system` UID recorded by trusted fixture provisioning. Do not fetch a current UID and treat it as the expected identity. Keep the dedicated kubeconfig unchanged; identity alone does not prove disposability.

The helpers use [explicit kubectl targeting](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl/) to bind the supplied fences to that fixture and a newly created namespace; they are not a sandbox for arbitrary commands or manifests. Keep the private creation receipt. Failed or interrupted creation preserves the candidate for fixture-owner reconciliation, never adoption by later lookup. Continue only after setup succeeds.

Scenario 3 retains its separate `KUBEDOJO_LAB_*` inputs, namespace and cleanup. Its reference to `app-debug-lab` describes the other scenarios' former fixed name; Scenarios 1/2/4 now use the unique `app-debug-…` namespace below. Use Scenario 3's own instructions in a separate Bash session; neither cleanup handles the other's namespace.

```bash
_app_lab_base() {
  command kubectl --kubeconfig="$_APP_LAB_CONFIG" --context="$_APP_LAB_CONTEXT" \
    --namespace="${_APP_LAB_NS:-default}" --request-timeout=30s "$@"
}
_app_lab_identity() {
  local actual
  actual=$(_app_lab_base get namespace kube-system -o jsonpath='{.metadata.uid}' </dev/null) || return
  [[ -n "$_APP_LAB_CLUSTER_UID" && "$actual" == "$_APP_LAB_CLUSTER_UID" ]] || {
    echo 'Fixture identity mismatch; stop.' >&2; return 1;
  }
}
_app_lab_receipt() {
  (umask 077; declare -p _APP_LAB_CONFIG _APP_LAB_CONTEXT _APP_LAB_CLUSTER_UID _APP_LAB_NS _APP_LAB_UID _APP_LAB_DELETE_SENT) >> "$_APP_LAB_RECEIPT"
}
app_lab_setup() {
  [[ -z ${_APP_LAB_NS+x} && -z ${_APP_LAB_RECEIPT+x} ]] || {
    echo 'Existing candidate/receipt: reconcile it before another setup.' >&2; return 1;
  }
  [[ -n ${APP_LAB_KUBECONFIG:-} && -n ${APP_LAB_CONTEXT:-} && -n ${APP_LAB_CLUSTER_UID:-} ]] || {
    echo 'Supply all three independently verified fixture inputs.' >&2; return 1;
  }
  _APP_LAB_CONFIG=$APP_LAB_KUBECONFIG; _APP_LAB_CONTEXT=$APP_LAB_CONTEXT; _APP_LAB_CLUSTER_UID=$APP_LAB_CLUSTER_UID
  _app_lab_identity || return
  _APP_LAB_NS="app-debug-$(date +%s)-$RANDOM-$RANDOM"; _APP_LAB_UID=; _APP_LAB_DELETE_SENT=false
  _APP_LAB_RECEIPT="$PWD/$_APP_LAB_NS.receipt"
  (umask 077; set -o noclobber; : > "$_APP_LAB_RECEIPT") || return
  _app_lab_receipt || return
  printf 'Retain receipt: %s\n' "$_APP_LAB_RECEIPT"
  if ! _APP_LAB_UID=$(_app_lab_base create namespace "$_APP_LAB_NS" -o jsonpath='{.metadata.uid}'); then
    _APP_LAB_UID=; echo 'Creation uncertain: retain candidate; ask fixture owner to reconcile.' >&2; return 1
  fi
  [[ $_APP_LAB_UID =~ ^[0-9a-fA-F-]{36}$ ]] || {
    _APP_LAB_UID=; echo 'Missing creation UID: preserve candidate; do not adopt or delete it.' >&2; return 1;
  }
  _app_lab_receipt || return
  _APP_LAB_RECEIPT_OK=true
}
app_lab() {
  local arg actual
  [[ ${1:-} != delete ]] || { echo 'Use app_lab_cleanup for teardown.' >&2; return 1; }
  for arg in "$@"; do
    [[ $arg == -- ]] && break
    case "$arg" in
      -n*|-s*|-A*|--namespace*|--context*|--kubeconfig*|--cluster*|--user*|--server*|--all-namespaces*|--raw*|--as*|--token*|--client-*|--certificate-authority*|--insecure-skip-tls-verify*|--tls-server-name*|--request-timeout*)
        echo 'Target override refused.' >&2; return 1;;
    esac
  done
  [[ ${_APP_LAB_RECEIPT_OK:-} == true && -s ${_APP_LAB_RECEIPT:-} && -n ${_APP_LAB_NS:-} && ${_APP_LAB_UID:-} =~ ^[0-9a-fA-F-]{36}$ ]] || {
    echo 'No valid creation receipt; stop.' >&2; return 1;
  }
  _app_lab_identity || return
  actual=$(_app_lab_base get namespace "$_APP_LAB_NS" -o jsonpath='{.metadata.uid}' </dev/null) || return
  [[ "$actual" == "$_APP_LAB_UID" ]] || { echo 'Namespace identity mismatch; stop.' >&2; return 1; }
  _app_lab_base "$@"
}
app_lab_setup
```

### Scenario 1: CrashLoopBackOff

This Pod starts a BusyBox container, prints one line, and exits with code `1`. That makes it a clean example of a process-level failure rather than an image, scheduling, or volume problem. Your goal is to prove the exit code and then create a separate corrected Pod with a long-running command, retaining the failing Pod for comparison.

```bash
cat <<'EOF' | app_lab apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-app
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sh', '-c', 'echo "Starting..."; exit 1']
EOF
```

**Task**: Find why it is crashing and what exit code it has.

<details>
<summary>Solution</summary>

```bash
app_lab describe pod crash-app | grep -A5 "Last State"
app_lab get pod crash-app -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
# Exit code 1 - the command explicitly exits with error

# If kubelet retained logs from the prior instance, follow up with:
app_lab logs crash-app --previous

# Create a corrected Pod; retain crash-app and its evidence.
cat <<'EOF' | app_lab create -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-app-fixed
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sh', '-c', 'echo "Starting..."; sleep 3600']
EOF
app_lab wait --for=condition=Ready pod/crash-app-fixed --timeout=90s
app_lab get pod crash-app crash-app-fixed
```

</details>

### Scenario 2: Missing ConfigMap

This Pod references a ConfigMap volume named `app-settings`, but the ConfigMap does not exist yet. The container image is valid, so image pull is not the likely cause. The evidence should appear in Events as a volume setup or missing ConfigMap problem, and the fix is to create the named object in the same namespace.

```bash
cat <<'EOF' | app_lab apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: config-app
spec:
  containers:
  - name: app
    image: nginx:1.25
    volumeMounts:
    - name: config
      mountPath: /etc/app
  volumes:
  - name: config
    configMap:
      name: app-settings
EOF
```

**Task**: Find why it is stuck in ContainerCreating and fix it.

<details>
<summary>Solution</summary>

```bash
# Diagnose
app_lab describe pod config-app | grep -A 5 Events
# "configmap "app-settings" not found"

# Fix
app_lab create configmap app-settings --from-literal=key=value

# Verify
app_lab wait --for=condition=Ready pod/config-app --timeout=90s
app_lab get pod config-app
```

</details>

### Scenario 3: Failed Deployment Rollout

Hypothetical scenario: a new image tag breaks a release. This controlled
exercise uses its own fresh namespace, separate from `app-debug-lab`, so you
can inspect a failed revision while the healthy revision remains available.

Prerequisites: Bash, `jq`, namespace permissions, and a dedicated disposable
Kubernetes 1.35 context with a supported `kubectl` client. Set
`KUBEDOJO_LAB_CONTEXT` and a fresh `KUBEDOJO_LAB_NAMESPACE`; calls use the
dedicated context explicitly. The namespace is constrained to a DNS-1123 label
before any mutation. Context strings remain quoted command arguments and are
serialized with `jq --arg`, so arbitrary context text is never interpolated
into YAML.

```bash
(
  set -euo pipefail
  : "${KUBEDOJO_LAB_CONTEXT:?Set a dedicated disposable context}"
  : "${KUBEDOJO_LAB_NAMESPACE:?Set a fresh namespace name}"
  if (( ${#KUBEDOJO_LAB_NAMESPACE} > 63 )) || [[ ! "$KUBEDOJO_LAB_NAMESPACE" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "Namespace must be a fresh DNS-1123 label (lowercase letters, digits, hyphens; max 63 characters)" >&2
    exit 1
  fi
  KUBEDOJO_LAB_OWNER=cka52-2337
  if existing_namespace=$(kubectl --context "$KUBEDOJO_LAB_CONTEXT" get namespace "$KUBEDOJO_LAB_NAMESPACE" -o json --ignore-not-found); then
    if [ -n "$existing_namespace" ]; then
      echo "Refusing an existing namespace; choose a fresh lab namespace" >&2
      exit 1
    fi
  else
    status=$?
    echo "Namespace preflight failed; refusing to continue (kubectl status $status)" >&2
    exit "$status"
  fi
  jq -n \
    --arg name "$KUBEDOJO_LAB_NAMESPACE" \
    --arg owner "$KUBEDOJO_LAB_OWNER" \
    --arg context "$KUBEDOJO_LAB_CONTEXT" \
    '{apiVersion:"v1",kind:"Namespace",metadata:{name:$name,labels:{"kubedojo.io/lab-owner":$owner},annotations:{"kubedojo.io/lab-context":$context}}}' |
    kubectl --context "$KUBEDOJO_LAB_CONTEXT" create -f -
  cat <<EOF | kubectl --context "$KUBEDOJO_LAB_CONTEXT" apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: image-rollout
  namespace: $KUBEDOJO_LAB_NAMESPACE
spec:
  replicas: 2
  progressDeadlineSeconds: 30
  selector:
    matchLabels:
      app: image-rollout
  template:
    metadata:
      labels:
        app: image-rollout
    spec:
      containers:
      - name: app
        image: nginx:1.25
EOF
  kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" rollout status deployment/image-rollout --timeout=90s
)
```

Record the successful baseline:

```bash
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get deployment image-rollout
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get pods -l app=image-rollout
```

Before the change, predict what will happen to the two ready Pods if the new
image cannot be pulled. Induce failure without deleting the healthy revision:

```bash
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" set image deployment/image-rollout app=nginx:tag-does-not-exist
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" rollout status deployment/image-rollout --timeout=45s
```

A progress-deadline error or command timeout prompts inspection; a non-zero
status alone is not proof. Inspect
Deployment conditions, ReplicaSets/Pods, and namespaced Events before repair:

```bash
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get deployment image-rollout
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" describe deployment image-rollout
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get pods -l app=image-rollout -o wide
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get events --sort-by=.lastTimestamp
```

Accept only actual output tying the new ReplicaSet/Pod to the bad image and an
image-pull failure such as `ErrImagePull`/`ImagePullBackOff`. Stop on API,
authentication, context, or registry-access errors.

Choose the object you would repair and explain why deleting a failing Pod
would not correct its controller's image template.

<details>
<summary>Check your repair: roll back the Deployment</summary>

Repair the owning Deployment and verify readiness:

```bash
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" rollout undo deployment/image-rollout
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" rollout status deployment/image-rollout --timeout=90s
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get deployment image-rollout
kubectl --context "$KUBEDOJO_LAB_CONTEXT" -n "$KUBEDOJO_LAB_NAMESPACE" get pods -l app=image-rollout
```

Success requires 2 ready baseline replicas, observed failed-image evidence,
then 2 ready replicas after rollback. Record actual output; do not prescribe
Event wording. In the validation run below, the two old Pods stayed ready while the new
ReplicaSet could not pull its image; rollback restored the old template.

</details>

Cleanup must be independently runnable after interruption, use the same
explicit dedicated context, and avoid resetting the user's global context:

```bash
(
  set -euo pipefail
  : "${KUBEDOJO_LAB_CONTEXT:?Set the dedicated disposable context}"
  : "${KUBEDOJO_LAB_NAMESPACE:?Set the lab namespace}"
  if (( ${#KUBEDOJO_LAB_NAMESPACE} > 63 )) || [[ ! "$KUBEDOJO_LAB_NAMESPACE" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "Namespace must be the DNS-1123 label used by this lab" >&2
    exit 1
  fi
  KUBEDOJO_LAB_OWNER=cka52-2337
  if namespace_name=$(kubectl --context "$KUBEDOJO_LAB_CONTEXT" get namespace "$KUBEDOJO_LAB_NAMESPACE" -o jsonpath='{.metadata.name}' --ignore-not-found); then :; else
    status=$?
    echo "Namespace lookup failed; refusing cleanup (kubectl status $status)" >&2
    exit "$status"
  fi
  [ -z "$namespace_name" ] && { echo "Lab namespace is already absent"; exit 0; }
  if namespace_owner=$(kubectl --context "$KUBEDOJO_LAB_CONTEXT" get namespace "$KUBEDOJO_LAB_NAMESPACE" -o jsonpath="{.metadata.labels['kubedojo\.io/lab-owner']}" --ignore-not-found); then :; else
    status=$?
    echo "Owner lookup failed; refusing cleanup (kubectl status $status)" >&2
    exit "$status"
  fi
  if namespace_context=$(kubectl --context "$KUBEDOJO_LAB_CONTEXT" get namespace "$KUBEDOJO_LAB_NAMESPACE" -o jsonpath="{.metadata.annotations['kubedojo\.io/lab-context']}" --ignore-not-found); then :; else
    status=$?
    echo "Context lookup failed; refusing cleanup (kubectl status $status)" >&2
    exit "$status"
  fi
  if [ "$namespace_owner" != "$KUBEDOJO_LAB_OWNER" ] || [ "$namespace_context" != "$KUBEDOJO_LAB_CONTEXT" ]; then
    echo "Refusing cleanup: namespace ownership or context marker does not match" >&2
    exit 1
  fi
  kubectl --context "$KUBEDOJO_LAB_CONTEXT" delete namespace "$KUBEDOJO_LAB_NAMESPACE" --wait=true
)
```

[Deployment progress and rollback](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/):
a stalled Deployment reports its condition and keeps retrying; it does not
automatically roll back. [JSONPath keys containing periods](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/jsonpath/)
need the escaping shown in cleanup.

Validation: 2026-09-05, kind Kubernetes 1.35.0 on Linux/arm64 with kubectl
1.35.0. The six command blocks produced two ready baseline replicas, a new
ReplicaSet/Pod with the unavailable tag and `ImagePullBackOff`, then two ready
replicas after rollback. Namespace and disposable cluster cleanup passed.
Registry availability and error wording can differ in your environment.

### Scenario 4: Resource Constraint (OOM)

This Pod intentionally asks the stress process to allocate more memory than the container limit allows. The intended result is `OOMKilled`, which must be observed rather than inferred from the limit. The checked Kubernetes 1.35 arm64 fixture observed that termination with `polinux/stress`; this does not establish portability or verify the higher-limit Pod. Keep the failing Pod and create a distinct Pod with a higher limit for comparison, then record its actual behavior before claiming a successful repair.

```bash
cat <<'EOF' | app_lab apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: oom-app
spec:
  containers:
  - name: app
    image: polinux/stress
    command: ["stress"]
    args: ['--vm', '1', '--vm-bytes', '500M']
    resources:
      limits:
        memory: "100Mi"
EOF
```

**Task**: Determine whether the observed termination reason is `OOMKilled`. If the image cannot run on the fixture, record that limitation and stop this scenario; an image or architecture failure is not OOM evidence.

<details>
<summary>Solution</summary>

```bash
# Diagnose
app_lab describe pod oom-app | grep -i oom
app_lab get pod oom-app -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
# Require an observed OOMKilled reason; a generic exit is not proof.

# Create a separate comparison Pod; retain oom-app.
cat <<'EOF' | app_lab create -f -
apiVersion: v1
kind: Pod
metadata:
  name: oom-app-fixed
spec:
  containers:
  - name: app
    image: polinux/stress
    command: ["stress"]
    args: ['--vm', '1', '--vm-bytes', '500M']
    resources:
      limits:
        memory: "600Mi"
EOF
app_lab get pod oom-app oom-app-fixed
```

A sampled Running/Ready state does not prove the memory problem is fixed. Record actual termination reasons, restart history and corrected-workload behavior before claiming success. Keeping both Pods also requires capacity for both; do not delete the failing Pod to manufacture a passing comparison.

</details>

### Success Criteria

- [ ] Diagnose application failures by identifying `crash-app` exit code as `1` using previous logs and container state.
- [ ] Create `crash-app-fixed`, verify it becomes Ready, and retain the original failed Pod for comparison.
- [ ] Fix application failures caused by missing ConfigMaps by creating `app-settings` in the correct namespace.
- [ ] Diagnose the new ReplicaSet's image-pull failure, roll back `image-rollout`, and verify two ready replicas in its dedicated namespace.
- [ ] Record `OOMKilled` for `oom-app` before creating the higher-limit `oom-app-fixed`; report an unreproduced failure instead of claiming OOM from an image or architecture error.

### Cleanup

Explicit cleanup below deletes only the recorded Scenarios 1/2/4 namespace, including failed and corrected Pods. It uses a [UID-preconditioned DELETE](https://github.com/kubernetes/apimachinery/blob/v0.35.0/pkg/apis/meta/v1/types.go), bounded wait and final absence check. Failures retain the receipt for deliberate retry; never fall back to name-only deletion or remove finalizers.

```bash
app_lab_cleanup() {
  local actual
  [[ ${_APP_LAB_RECEIPT_OK:-} == true && -s ${_APP_LAB_RECEIPT:-} && -n ${_APP_LAB_NS:-} && ${_APP_LAB_UID:-} =~ ^[0-9a-fA-F-]{36}$ ]] || {
    echo 'No valid creation receipt; cleanup refused.' >&2; return 1;
  }
  _app_lab_identity || return
  actual=$(_app_lab_base get namespace "$_APP_LAB_NS" --ignore-not-found -o jsonpath='{.metadata.uid}' </dev/null) || return
  if [[ -n "$actual" ]]; then
    [[ "$actual" == "$_APP_LAB_UID" ]] || { echo 'Replacement namespace: stop.' >&2; return 1; }
    printf '{"apiVersion":"v1","kind":"DeleteOptions","preconditions":{"uid":"%s"}}' "$_APP_LAB_UID" |
      _app_lab_base delete --raw "/api/v1/namespaces/$_APP_LAB_NS" -f - || return
    _APP_LAB_DELETE_SENT=true; _app_lab_receipt || return
    _app_lab_base wait --for=delete "namespace/$_APP_LAB_NS" --timeout=120s || return
  elif [[ $_APP_LAB_DELETE_SENT != true ]]; then
    echo 'Namespace missing without confirmed deletion; reconcile receipt.' >&2; return 1
  fi
  actual=$(_app_lab_base get namespace "$_APP_LAB_NS" --ignore-not-found -o jsonpath='{.metadata.uid}' </dev/null) || return
  [[ -z "$actual" ]] || { echo 'Namespace still present; retain receipt.' >&2; return 1; }
  printf 'Confirmed namespace absent: %s. Retain receipt: %s\n' "$_APP_LAB_NS" "$_APP_LAB_RECEIPT"
}
app_lab_cleanup
```

There is no automatic EXIT cleanup when an interactive command is interrupted. If the creation response, session or receipt is lost, stop for fixture-owner reconciliation; never recover ownership by looking up the candidate's current UID. Retain the private receipt on failure and retry cleanup in the same session. It stores identifiers and a kubeconfig path, not credential contents; do not blindly source a receipt.

### Practice Drills

These drills preserve the original quick-command practice while using full runnable `kubectl` commands. Treat them as timed recall only after you understand the evidence path, because speed without diagnosis can make you confidently wrong. The goal is to make the correct next command feel automatic once the Pod phase and Events have pointed you in the right direction.

### Drill 1: Quick Pod Status (30 sec)

```bash
# Task: Show all pods with restart count > 0
kubectl get pods -A -o custom-columns='NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount' | awk '$2 > 0'
```

### Drill 2: Previous Logs (30 sec)

```bash
# Task: Get last 50 lines from previous container instance
kubectl logs <pod> --previous --tail=50
```

### Drill 3: Exit Code Check (1 min)

```bash
# Task: Get exit code from crashed container
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
# Or from describe:
kubectl describe pod <pod> | grep "Exit Code"
```

### Drill 4: Image Fix (1 min)

```bash
# Task: Update image in deployment
kubectl set image deployment/<name> <container>=<new-image>
```

### Drill 5: Create Missing ConfigMap (1 min)

```bash
# Task: Create ConfigMap from literal
kubectl create configmap <name> --from-literal=key=value
# From file
kubectl create configmap <name> --from-file=<filename>
```

### Drill 6: Environment Variable Debug (1 min)

```bash
# Task: Check all env vars in running container
kubectl exec <pod> -- env | sort
```

### Drill 7: Rollback Deployment (1 min)

```bash
# Task: Rollback to previous version
kubectl rollout undo deployment/<name>
kubectl rollout status deployment/<name>
```

### Drill 8: Check Probe Config (1 min)

```bash
# Task: View probe configuration
kubectl get pod <pod> -o yaml | grep -A 15 livenessProbe
kubectl get pod <pod> -o yaml | grep -A 15 readinessProbe
```

## Learner check

> `image: polinux/stress` with `command: ["stress"]` and `args: ['--vm', '1', '--vm-bytes', '500M']` replaces the schema-v1 `progrium/stress` image so the OOM lab runs on Kubernetes 1.35.

You applied Scenario 4 with a 100Mi memory limit and the stress container requesting 500M. What termination reason should `kubectl get pod oom-app -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'` return before you raise the limit?

---

## Sources

- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — Backs pod phases, container states, restart behavior, CrashLoopBackOff semantics, init-container sequencing, readiness-related lifecycle concepts, and general pod-state troubleshooting vocabulary.
- [kubernetes.io: init containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/) — The official Init Containers concept page states that init containers run before app containers, sequentially, and gate app-container startup.
- [kubernetes.io: assign memory resource](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/) — The official memory-resource task shows a container being OOMKilled because its memory use exceeds the configured limit, which supports the operational point.
- [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/) — Backs exact kubectl logs behavior and flags such as container selection, follow mode, timestamps, tail, since, previous logs, and all-containers retrieval.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment concept documentation explicitly states that only `restartPolicy: Always` is allowed in a Deployment pod template.
- [kubernetes.io: job](https://kubernetes.io/docs/concepts/workloads/controllers/job/) — The Job concept documentation explicitly defines Jobs as one-off tasks that run to completion.
- [kubernetes.io: update deployment rolling](https://kubernetes.io/docs/tasks/run-application/update-deployment-rolling/) — The rolling-update task says stalled rollouts usually indicate new Pods are failing to start and recommends checking Deployment conditions and events.
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) — Covers the core troubleshooting workflow for describe, logs, events, exec, and pod inspection.
- [Images](https://kubernetes.io/docs/concepts/containers/images/) — Documents image pull policy, private-registry authentication context, and ImagePullBackOff behavior.
- [Liveness, Readiness, and Startup Probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — Provides the authoritative semantics behind probe-triggered restarts, readiness gating, and startup protection.

## Next Module

Continue to [Module 5.3: Control Plane Failures](../module-5.3-control-plane/) to learn how to troubleshoot API server, scheduler, controller manager, and etcd issues.
