---
citations_verified: true
title: "Module 1.9: Debugging Basics (Theory)"
slug: k8s/kcna/part1-kubernetes-fundamentals/module-1.9-debugging-basics
revision_pending: false
sidebar:
  order: 10
---

> **Complexity**: `[MEDIUM]` - Long-form debugging module with structured triage drills for Kubernetes 1.35+
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: Modules 1.1-1.8, basic `kubectl` access to a practice cluster, and the local habit of defining `alias k=kubectl` before using the short `k` commands in this module

## Learning Outcomes

Use the outcomes below as practical targets for your notes, lab work, and quiz answers throughout the module:

1. **Debug** an unhealthy workload by following a repeatable Kubernetes triage path from symptom to probable root cause.
2. **Analyze** pod phase, container state, conditions, events, and logs to decide which signal matters most in a failure scenario.
3. **Compare** image pull, scheduling, crash loop, out-of-memory, and probe failures using their observable evidence rather than guessing.
4. **Evaluate** whether a problem belongs to the application, the pod specification, the scheduler, the node, or a controller rollout.
5. **Design** a first-response checklist that preserves evidence, narrows scope, and avoids making an incident worse.

## Why This Module Matters

Late on a Thursday, a payments company pushed a small checkout release that changed how its API loaded database credentials. The old pods kept serving traffic, but the new ReplicaSet produced pods that restarted every few seconds, and the Deployment stalled while customer carts intermittently failed. The incident report later estimated more than $85,000 in abandoned transactions during the first hour, yet the most expensive mistake was not the bad configuration itself; it was the first responder deleting pods and restarting the rollout before anyone captured the previous container logs that named the missing environment variable.

That scene is common because Kubernetes failures arrive as compressed symptoms, not neat explanations. A single word such as `Pending`, `Running`, `CrashLoopBackOff`, or `ImagePullBackOff` can represent very different ownership boundaries, and a responder who guesses too early can chase the wrong component for half an hour. Debugging basics give you a disciplined way to ask, in order, whether Kubernetes could place the pod, whether the kubelet could prepare it, whether the container process started, whether the application stayed alive, and whether the workload became ready for traffic.

KCNA does not require you to solve every production incident from memory, but it does expect you to recognize where Kubernetes records evidence and how control-plane decisions differ from node-level and application-level facts. In this module, you will practice reading pod status as a timeline, using `describe`, logs, and events for their separate jobs, and designing a first-response checklist that narrows the problem before changing the cluster. Create the short alias with `alias k=kubectl`; from this point forward, commands use `k get`, `k describe`, and related forms because that is the operator habit you will see in real clusters.

## Part 1: Debugging Is Evidence Collection Before Action

Debugging Kubernetes begins with restraint because the first command can either preserve evidence or erase it. A pod deletion, rollout restart, or manual edit may temporarily change the visible symptom while hiding the original cause, especially when a crash loop contains useful previous logs or when short-lived events are aging out. Experienced responders slow down for a few minutes, not because they enjoy process, but because the cluster is already producing witnesses: the object spec says what was requested, the scheduler says whether placement succeeded, the kubelet says what happened on the node, and the application says why its process failed.

Think of the cluster as several witnesses describing the same incident from different angles. The Deployment, ReplicaSet, and Pod specs describe desired state, including image names, commands, resource requests, probes, environment references, and volumes. The scheduler explains why a pod did or did not receive a node, while the kubelet explains image pulls, container creation, probe failures, restarts, and local resource pressure. The application logs are another witness, but they only exist after the process actually ran, which is why logs are powerful for crash loops and almost useless for pods that never scheduled.

```ascii
KUBERNETES DEBUGGING WITNESSES

┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│ Desired State       │     │ Cluster Decisions   │     │ Runtime Evidence    │
│ Deployment, Pod     │────▶│ Scheduler, events   │────▶│ Kubelet, logs       │
│ spec, probes, env   │     │ placement, reasons  │     │ exits, restarts     │
└────────────────────┘     └────────────────────┘     └────────────────────┘
          │                            │                            │
          ▼                            ▼                            ▼
 "What did we ask for?"      "What did Kubernetes try?"      "What actually ran?"
```

The first classification question is not "Which fix should I try?" but "Which part of the system has already acted?" If the pod has no assigned node, the scheduler is still the main witness, so reading application logs is premature. If the pod has a node but the image cannot be pulled, the kubelet is telling you about registry, authentication, tag, or network evidence before the container exists. If the container started and exited, previous logs and last state become central, and if the process is alive but not ready, probe events and Service endpoints usually explain why traffic is withheld.

```ascii
THE FIRST RESPONSE LOOP

┌───────────────┐
│ 1. Scope      │  k get pods -A -o wide
│ problem size  │  One pod, one node, one namespace, or many?
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 2. Describe   │  k describe pod <pod> -n <namespace>
│ object story  │  Conditions, container states, events, mounts, probes
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 3. Read logs  │  k logs <pod> -n <namespace> [-p] [-c <container>]
│ app witness   │  Current or previous container output
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 4. Widen view │  k get events -n <namespace> --sort-by=.lastTimestamp
│ timeline      │  Related failures from scheduler, kubelet, and controllers
└───────────────┘
```

This loop is deliberately simple because incident pressure punishes clever but inconsistent behavior. Scope comes first so you know whether you are looking at one pod, one namespace, one node, one rollout, or a broader cluster failure. `describe` comes early because it joins desired state, current status, container state, conditions, and events in a single view. Logs come after you know a container has run, and events widen the timeline when you need scheduler, kubelet, or controller messages that are not part of the application output.

> **Pause and predict**: A teammate says, "The pod is broken, so I will delete it and let Kubernetes recreate it." Before reading on, decide when that action might be harmless and when it might destroy the best clue you have.

Deleting a pod managed by a Deployment can be a reasonable recovery step after evidence has been collected, because [the controller will create a replacement from the same template](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/). It is a poor first move when the previous instance had the only useful stack trace, when event ordering matters, or when you still need to know whether the scheduler, kubelet, or application failed first. The safer habit is to capture the status, previous logs, and events, state a hypothesis, and then decide whether a restart, rollback, Secret fix, resource change, or probe adjustment matches the evidence.

A useful way to practice restraint is to narrate the failure in terms of ownership before touching anything. "The scheduler has not assigned a node" points you toward resources, taints, affinity, topology, or storage binding. "The kubelet cannot pull the image" points you toward tags, registry credentials, and network reachability. "The application started and exited with a missing setting" points you toward configuration and release ownership. This ownership language prevents the classic beginner error of treating every red pod as an application bug or every application bug as a Kubernetes bug.

## Part 2: Read Pod State Like a Timeline

A pod status line is a compressed timeline, not a final diagnosis. `STATUS` in `k get pods` often displays a container reason chosen for human readability, while the pod phase is a broader lifecycle category such as `Pending`, `Running`, `Succeeded`, `Failed`, or `Unknown`. That distinction matters because a pod can be in the `Running` phase while one container is not ready, and [a pod can appear `Pending` because it has not been scheduled or because it is already assigned to a node while the kubelet prepares images and volumes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/).

```bash
k get pods -n default -o wide
```

```text
NAME                         READY   STATUS             RESTARTS   AGE   IP           NODE
api-6d8b7c9f5c-f2mzp          0/1     CrashLoopBackOff   9          18m   10.244.1.8   worker-a
web-76bc6c9d7b-9nq5p          1/1     Running            0          42m   10.244.2.4   worker-b
report-5d9c997d8d-xr2hg       0/1     Pending            0          11m   <none>       <none>
```

The `READY` column tells you how many regular containers are ready compared with how many the pod defines. The `STATUS` column gives a concise reason that often comes from the most important current or recent container state, while `RESTARTS` tells you whether the kubelet has repeatedly started the container after termination. The `NODE` column is just as important as the more dramatic status text, because a missing node means the scheduler has not placed the pod, and a named node means the investigation has moved to kubelet, image, volume, probe, resource, or application evidence.

```ascii
POD LIFECYCLE STATE DIAGRAM

                ┌──────────┐
    Pod created │          │
   ────────────▶│ Pending  │──── Scheduler cannot place pod
                │          │     because resources, taints,
                └────┬─────┘     affinity, or volumes block it
                     │
                     │ Scheduled to a node
                     ▼
                ┌──────────┐
                │ Waiting  │──── Kubelet is preparing containers,
                │          │     pulling images, or mounting volumes
                └────┬─────┘
                     │
                     │ Containers started
                     ▼
                ┌──────────┐     ┌────────────┐
                │ Running  │────▶│ Terminated │
                │          │     │            │
                └────┬─────┘     └─────┬──────┘
                     │                 │
                     │                 ▼
                     │          ┌──────────────┐
                     │          │ Restarted or │
                     │          │ stays failed │
                     │          └──────────────┘
                     ▼
                ┌───────────┐
                │ Succeeded │──── Normal for Jobs when all containers exit 0
                └───────────┘

   Special: Unknown means the control plane cannot determine pod state from the node.
```

Translate every visible status into a focused question. `Pending` asks whether the scheduler assigned a node and, if not, which scheduling rule blocked placement. `ImagePullBackOff` asks whether the kubelet can reach and authenticate to the registry and whether the referenced image exists. `CrashLoopBackOff` asks what the previous container instance printed or exited with, while `Running` with `0/1` readiness asks which condition or probe is preventing Service traffic. This translation keeps you from running familiar commands that do not match the failure stage.

| Signal | Most Useful First Question | Best First Evidence |
|---|---|---|
| `Pending` with no node | Why could the scheduler not place this pod? | `k describe pod` Events section |
| `ImagePullBackOff` | What exact image pull error did the kubelet report? | Pod events from `k describe pod` |
| `CrashLoopBackOff` | Why did the previous container exit? | `k logs <pod> -p` and Last State |
| `Running` but not `Ready` | Which readiness condition or probe is failing? | Pod conditions, endpoints, and probe events |
| `OOMKilled` | Did the container exceed its memory limit? | Last State reason, exit code, resource limits |
| `Unknown` | Is the node unreachable or unhealthy? | Node conditions and node events |

Pod conditions provide a more structured view than the one-line status because they expose which lifecycle milestones are true or false. [`PodScheduled` means the scheduler assigned a node, `Initialized` means init containers completed, `ContainersReady` means all app containers report ready, and `Ready` means the pod should receive traffic through Services that select it](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/). A pod can be alive but not useful if `Ready` is false, which is exactly why Kubernetes separates process existence from traffic eligibility.

| Condition | What It Means | Debugging Interpretation |
|---|---|---|
| `PodScheduled` | The pod has been assigned to a node. | If false, focus on scheduler events, resources, taints, affinity, and volumes. |
| `Initialized` | Init containers have completed successfully. | If false, inspect init container logs and volume or permission setup. |
| `ContainersReady` | All app containers report ready. | If false, inspect container states, readiness probes, and dependency errors. |
| `Ready` | The pod should receive Service traffic. | If false, traffic should not be routed to this pod even if it is running. |

Container states are more specific than pod conditions because each regular, init, or sidecar-style container can be waiting, running, or terminated independently. In a multi-container pod, a logging sidecar can be healthy while the main API fails, or an init container can block the entire pod before the application image starts. Always name the container with `-c <container>` when logs or state are ambiguous, and use current state plus last state to understand both what is happening now and what happened during the previous attempt.

| Container State | Meaning | What to Check |
|---|---|---|
| `Waiting` | The container has not started or is backing off before the next start attempt. | Reason field such as `ImagePullBackOff`, `ContainerCreating`, or `CrashLoopBackOff`. |
| `Running` | The process is currently executing inside the container. | Start time, readiness, probes, and whether restarts have happened recently. |
| `Terminated` | The process exited or was killed. | Exit code, reason, finished time, and previous logs with `k logs -p`. |

> **What would happen if** you only looked at `k get pods` and saw `Running`, then told your team the service was healthy? Explain why that could be wrong when the `READY` column says `0/1`.

The mature reading of pod state avoids two traps that appear on both exams and real rotations. The first trap is treating the `STATUS` column as a human diagnosis, when it is only a clue generated from lifecycle state at one moment. The second trap is assuming all failures are application failures; Kubernetes may be unable to schedule the pod, mount a volume, pull an image, satisfy a probe, or keep a node connected even when the application code is correct.

## Part 3: Use `describe`, Logs, and Events Without Mixing Their Jobs

`k describe pod` is the best bridge between desired state and cluster behavior. It shows identity, labels, owner references, node assignment, IPs, conditions, mounted volumes, environment references, container states, resource requests and limits, probes, and recent events in one command. That breadth is useful because real incidents often contain contradictions, such as a container that starts successfully but fails readiness, a pod that is scheduled but blocked by a volume mount, or a Deployment whose new pods all fail while the old ReplicaSet remains healthy.

```bash
k describe pod api-6d8b7c9f5c-f2mzp -n default
```

When reading `describe`, use a consistent order so your eyes do not bounce randomly through the output. First confirm namespace, name, labels, and owner because wrong-object debugging is more common than people admit. Then check node, phase, conditions, and container state, paying close attention to last state, restart count, resources, command, args, and probes. Finally, read the Events section from oldest relevant line to newest relevant line, because the bottom often tells you what the kubelet or scheduler is currently retrying.

```ascii
HOW TO READ kubectl describe pod

┌──────────────────────────────┐
│ Identity                     │  Name, namespace, labels, owner, node
├──────────────────────────────┤
│ Status and Conditions        │  Phase, Ready, ContainersReady, Scheduled
├──────────────────────────────┤
│ Container Details            │  Image, ports, command, state, last state
├──────────────────────────────┤
│ Configuration References     │  Env, ConfigMaps, Secrets, volumes, probes
├──────────────────────────────┤
│ Events                       │  Scheduler and kubelet timeline of actions
└──────────────────────────────┘
```

Logs answer a narrower question: what did the container process write to standard output and standard error. They are central when the process has started and exited, but they do not explain an unscheduled pod, an image tag that cannot be fetched, or a PersistentVolumeClaim that cannot bind. For crash loops, the `-p` flag is usually the difference between seeing the real startup failure and seeing nothing useful from the current waiting attempt.

```bash
k logs api-6d8b7c9f5c-f2mzp -n default
k logs api-6d8b7c9f5c-f2mzp -n default -p
k logs api-6d8b7c9f5c-f2mzp -n default -c api
```

Events answer what Kubernetes components attempted and why those attempts succeeded or failed. Scheduler events explain placement failures, kubelet events explain image pulls, container lifecycle, probe results, and mount failures, and controller events can explain rollout progress. [Events are time-limited in most clusters, so they are not a replacement for centralized logs and metrics](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/), but they are often the freshest and clearest evidence while a beginner is learning how cluster components report work.

```bash
k get events -n default --sort-by=.lastTimestamp
```

A practical rule is to avoid crossing evidence streams too early. If the event says `0/3 nodes are available: 3 Insufficient memory`, application code is not your first investigation because the container never had a place to run. If previous logs say `FATAL: missing DB_PASSWORD`, describing every node in the cluster is a distraction because the application has already named a startup dependency. The fastest operators are not the ones who know the longest command list; they are the ones who let each signal choose the next command.

The tradeoff is that no single evidence source is complete. `describe` may show a terse event that needs context from the manifest, logs may show an application error without proving how the environment variable was mounted, and events may summarize a repeated failure without retaining every historical attempt. You solve that by linking sources into a timeline: desired state asked for X, Kubernetes attempted Y, the node reported Z, and the application either ran or did not run. That timeline gives you a defensible next action instead of a guess.

Another helpful habit is to write down what each evidence source cannot tell you. Pod status cannot prove why the application crashed. Logs cannot prove that a Service is routing traffic. Events cannot prove that a fixed configuration has reached every new pod. This negative space matters because it keeps you from overstating one clue, and it naturally points toward the next command that should confirm or reject your hypothesis.

In team incidents, this clarity also improves communication. Saying "the pod is Pending because the scheduler reports insufficient memory" is much more useful than saying "the pod is broken." Saying "the container started and exited after reporting a missing Secret key" gives the application or platform owner a precise handoff. Good debugging language describes the observed stage, the evidence source, and the next safe action, so another engineer can audit your reasoning without replaying every command.

## Part 4: Worked Example - Diagnose Before You Fix

Suppose a team deploys version `1.8.2` of an API and the rollout stalls. The old pods continue serving traffic, but the new ReplicaSet creates pods that never become ready, and the release manager asks whether this is a bad image, a scheduling problem, or an application issue. A disciplined responder scopes the failure first because the pattern of old pods healthy and new pods unhealthy points toward the new template, new image, or configuration used only by the new version.

```bash
k get pods -n shop -o wide
```

```text
NAME                       READY   STATUS             RESTARTS   AGE   NODE
api-58c7d5f9b6-m2q8x        1/1     Running            0          2d    worker-a
api-58c7d5f9b6-r6ndk        1/1     Running            0          2d    worker-b
api-7b9c6d4f78-jk2tp        0/1     CrashLoopBackOff   6          9m    worker-a
```

This output already rules out several possibilities. The new pod has a node, so the scheduler placed it. It is not an image pull failure because the status is a crash loop rather than an image pull reason, and the restart count proves the container process has run more than once. The strongest first evidence is therefore previous logs from the new pod, because the process likely printed its startup failure before exiting.

```bash
k logs api-7b9c6d4f78-jk2tp -n shop -p
```

```text
2026-04-26T09:15:12Z starting api service
2026-04-26T09:15:12Z loading configuration from environment
2026-04-26T09:15:12Z FATAL missing required environment variable: DB_PASSWORD
```

The log message is strong, but a senior responder still verifies how Kubernetes was asked to provide that setting. The application says it needs `DB_PASSWORD`; `describe` can show whether that value is referenced from a Secret, whether the container has a last state and exit code that match the crash, and whether kubelet events show repeated backoff. This check prevents a too-fast conclusion such as "the database is down" when the actual failure is missing configuration.

```bash
k describe pod api-7b9c6d4f78-jk2tp -n shop
```

```text
State:          Waiting
  Reason:       CrashLoopBackOff
Last State:     Terminated
  Reason:       Error
  Exit Code:    1
Environment:
  DB_HOST:      postgres.shop.svc.cluster.local
  DB_PASSWORD:  <set to the key 'password' in secret 'api-db'>
Events:
  Warning  BackOff  kubelet  Back-off restarting failed container api
```

The probable root cause is now specific enough to test safely: the new pod expects a Secret key that is missing, renamed, empty, or not present in the `shop` namespace. The next checks should inspect the Secret object and then the Deployment rollout, rather than deleting random pods or editing the live pod. If the Secret is corrected or the Deployment template is fixed, the responder should verify that the rollout progresses, the new pod becomes Ready, and old pods are replaced according to the Deployment strategy.

```bash
k get secret api-db -n shop
k describe secret api-db -n shop
k rollout status deployment/api -n shop
```

This worked example shows the difference between evidence collection and command collection. `CrashLoopBackOff` selected previous logs, previous logs selected configuration, `describe` connected that configuration to a Secret reference, and rollout status verified whether the controller recovered after the underlying issue was corrected. The same pattern works when the symptom changes: start with the stage of failure, choose the witness for that stage, and only then choose an action.

Notice that the example never required privileged access to the node or deep knowledge of the application code. That is exactly why these basics belong early in a Kubernetes curriculum. You can often reduce an incident from "the deployment is failing" to "the new template references configuration the application cannot read" with ordinary read commands. That reduction does not solve every problem, but it turns panic into a focused request for the owner who can make the real change.

## Part 5: Failure Patterns You Must Recognize

The most common Kubernetes failures are recognizable because each has a different first useful signal. You do not need to memorize every possible event message, but you should know which evidence source owns the problem and which fixes belong to that source. A scheduler problem appears in scheduling events, an image problem appears in kubelet pull events, a startup problem appears in previous logs and last state, a memory kill appears in termination reason and resource limits, and a traffic problem often appears in readiness conditions and Service endpoints.

These patterns also help you avoid false similarities. `CrashLoopBackOff` and `ImagePullBackOff` both look alarming in the status column, but one means the process ran and the other means the process could not even be created. `Pending` and `Running` with `0/1` readiness can both block a rollout, but one belongs to placement and the other belongs to startup or health. When two symptoms look similar from a distance, compare the lifecycle stage first, then compare the evidence.

### 5.1 CrashLoopBackOff

`CrashLoopBackOff` means a container started, exited, and is now being restarted with a delay. Kubernetes is not saying why the application failed; it is saying the kubelet is backing off before trying again. The cause may be a bad command, missing environment variable, application exception, failed dependency, incorrect file permission, impossible startup migration, or a liveness probe that kills the process after it starts. Because the process has already run, previous logs and last state are your most efficient first evidence.

```bash
k logs <pod-name> -n <namespace> -p
k describe pod <pod-name> -n <namespace>
```

The pattern matters because beginners often inspect only current logs and miss the useful failure from the terminated instance. In a tight restart loop, the current container may be waiting, starting, or not yet at the failure point, while [`-p` asks for the last terminated container's output](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/). If every replica of the same Deployment crashes the same way, suspect a shared image, command, configuration, Secret, ConfigMap, probe, or dependency before blaming one node.

### 5.2 ImagePullBackOff and ErrImagePull

`ErrImagePull` and `ImagePullBackOff` mean the kubelet cannot fetch the container image. The application code has not run yet, so logs are usually empty or unavailable, and `exec` is impossible because there is no created container to enter. The event message is the primary clue because it can distinguish a tag that was never pushed from registry authentication failure, pull access denial, an incorrect repository path, DNS failure, network timeout, or a registry outage.

```bash
k describe pod <pod-name> -n <namespace>
```

Look for event phrases such as `manifest unknown`, `not found`, `pull access denied`, `unauthorized`, or timeout errors, then match the fix to that exact wording. A correct-looking image name can still fail if the CI pipeline pushed a different tag, the namespace lacks an `imagePullSecrets` reference, the registry path changed, or the node cannot reach the registry. Changing probes or application configuration cannot help until the kubelet can pull and create the container.

### 5.3 Pending and FailedScheduling

A pod in `Pending` with no assigned node is a scheduler problem until proven otherwise. The scheduler compares the pod's requests, node selectors, affinity rules, taints, tolerations, topology spread constraints, and volume requirements against available nodes. If no node satisfies the full set, the pod remains unscheduled, and `FailedScheduling` events explain which constraints rejected the available nodes.

```bash
k describe pod <pod-name> -n <namespace>
k get nodes -o wide
```

Common messages include insufficient CPU, insufficient memory, untolerated taints, unmatched node affinity, incompatible topology rules, or unbound PersistentVolumeClaims. The correct response is not to restart the pod because it has not started. You either change the pod's scheduling requirements, reduce resource requests when that is honest, provision capacity, fix storage binding, or add a toleration intentionally after confirming that the target nodes are appropriate.

### 5.4 OOMKilled

`OOMKilled` means the process exceeded its memory limit and the kernel killed it. Kubernetes records this in container last state, and [the exit code is often `137`](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/) because the process received a forced kill signal. The pod may then enter `CrashLoopBackOff` if the restart policy or owning controller keeps starting the same memory-hungry process under the same limit.

```bash
k describe pod <pod-name> -n <namespace>
```

The immediate comparison is between the container's memory limit and the application's actual memory behavior. Increasing a limit can be a valid mitigation when the original limit was unrealistic, but it is not always the complete fix. A memory leak, unbounded cache, accidental large batch load, or runtime heap setting can consume any larger limit eventually, so good debugging distinguishes a capacity mismatch from growth that should be fixed in the application.

### 5.5 Probe Failures and Running-But-Not-Ready Pods

A pod can run but receive no Service traffic because readiness failed. Liveness failures restart the container, readiness failures remove the pod from endpoints, and startup probes give slow-starting applications time before liveness begins. Probe failures are common after a port, path, scheme, startup duration, authentication behavior, or dependency changes, and they are especially easy to misread because `STATUS` may still say `Running`.

```bash
k describe pod <pod-name> -n <namespace>
k get endpoints <service-name> -n <namespace>
```

The dangerous beginner mistake is to see `Running` and assume users can reach the workload. Always compare `STATUS` with `READY`, then inspect events for messages such as `Readiness probe failed` or `Liveness probe failed`. If the application is healthy but the probe points to the wrong path or port, fix the probe. If the probe is correct and the application cannot satisfy it, fix the application or dependency that readiness is accurately exposing.

There is one more failure class worth keeping in the back of your mind: controller mismatch. Sometimes the pod-level symptom is real, but the reason it keeps returning is that the owning controller keeps creating new pods from an unchanged template. A direct pod edit may appear to work for a moment, then vanish when the Deployment replaces the pod. When the failure is tied to a rollout, always connect pod evidence back to the Deployment, ReplicaSet, Job, StatefulSet, or DaemonSet that owns it.

| Pattern | Main Signal | First Command | Likely Fix Area |
|---|---|---|---|
| Crash loop | `CrashLoopBackOff`, increasing restarts | `k logs <pod> -p` | App startup, command, config, dependency, probe |
| Image pull | `ImagePullBackOff`, `ErrImagePull` | `k describe pod <pod>` | Image reference, registry auth, registry/network reachability |
| Scheduling | `Pending`, no node assigned | `k describe pod <pod>` | Requests, taints, affinity, PVCs, node capacity |
| Memory kill | `OOMKilled`, exit code `137` | `k describe pod <pod>` | Memory limit, leak, heap sizing, workload shape |
| Readiness failure | `Running` with `0/1` ready | `k describe pod <pod>` | Probe path, port, startup time, dependency health |
| Node issue | Many pods fail on one node | `k describe node <node>` | Node pressure, kubelet, networking, disk, taints |

> **Before running the next command**, decide which row in the table matches your symptom and name the evidence you expect to see. If the evidence does not appear, revise the classification instead of forcing the original theory.

## Part 6: Build a First-Response Checklist

A debugging checklist is valuable because incidents make people skip steps. The goal is not to turn you into a robot; the goal is to protect your attention when several people are waiting for an answer and every chat message suggests a different fix. Use the checklist as a loop: confirm context, scope impact, classify the failure stage, inspect the right evidence, form a hypothesis, act on the most likely owner, and verify recovery at the controller and traffic levels.

```ascii
FIRST-RESPONSE CHECKLIST

┌───────────────────────┐
│ 1. Confirm Context     │  Correct cluster, namespace, workload, time window
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ 2. Scope Impact        │  One pod, many pods, one node, all namespaces
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ 3. Classify Failure    │  Scheduling, image, runtime, readiness, node
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ 4. Inspect Evidence    │  Describe, logs, previous logs, events, nodes
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ 5. Choose Action       │  Roll back, fix config, scale, adjust resources
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ 6. Verify Recovery     │  Rollout status, readiness, events, endpoints
└───────────────────────┘
```

Start every session by confirming context because debugging the wrong namespace wastes time and can cause accidental changes. `k config current-context` and `k get pods -A` are simple guardrails, especially in learning clusters where several namespaces may contain similarly named workloads. In production, teams often add shell prompts, kubeconfig conventions, and read-only defaults for the same reason: the first step of debugging is proving that you are looking at the intended cluster and workload.

```bash
k config current-context
k get pods -A -o wide
```

After context and scope, choose the narrowest evidence command that matches the failure stage. Use `describe` for scheduling, image pull, probe, volume, and kubelet lifecycle messages. Use `logs -p` for previous crashed containers, and add `-c` when a pod contains multiple containers. Use node commands when many unrelated pods fail on the same node or when pod status is `Unknown`. Use rollout commands when old and new ReplicaSets behave differently, because the controller view tells you whether the failure is isolated to a new template.

```bash
k rollout status deployment/<deployment-name> -n <namespace>
k get rs -n <namespace>
k describe node <node-name>
```

Verification matters because a "fix" that changes one pod's status may not restore the workload. For Deployments, verify rollout status, pod readiness, restart counts, and endpoints for Services that select the pods. For scheduling fixes, verify that the pod receives a node and then proceeds through image pull and container start. For probe fixes, verify that the pod becomes Ready and that the Service endpoint list includes it, because users care about traffic eligibility rather than process existence alone.

The checklist should leave a small audit trail even in a practice environment. Capture the visible symptom, the first useful evidence, the likely owner, the action taken, and the recovery check. This can be a chat message, an incident note, or a personal scratchpad. The format matters less than the discipline of writing a claim another engineer could challenge, because debugging improves fastest when your reasoning is visible.

As you gain experience, you will add environment-specific steps to the same skeleton. A managed cluster might require checking cloud load balancer health, a service mesh might require inspecting sidecar readiness, and a regulated environment might require preserving extra logs before cleanup. Those additions do not replace the fundamentals. They extend the same sequence of scope, classify, inspect, act, and verify.

## Patterns & Anti-Patterns

Good Kubernetes debugging patterns are small habits that scale from a lab cluster to a production incident. The common thread is that each pattern protects evidence, narrows ownership, and leaves a clear explanation for the next responder. Anti-patterns do the opposite: they change state before classification, mix evidence sources, or turn a specific symptom into a vague belief that "Kubernetes is broken."

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---|---|---|---|
| Scope before fixing | Any unhealthy workload, especially during rollouts | Separates one-pod failures from node, namespace, or cluster patterns | Use labels and owners to compare replicas quickly across namespaces |
| Read previous logs for crash loops | Containers with restarts or `CrashLoopBackOff` | Captures the failed process output before the next attempt hides it | Centralized logging is still needed when pods churn quickly |
| Follow owner references | Pods created by Deployments, Jobs, StatefulSets, or DaemonSets | Prevents direct pod edits that controllers overwrite | Fix the template or controller source so replacements inherit the change |
| Verify traffic eligibility | Pods that are `Running` but not serving users | Readiness and endpoints decide Service routing | Check endpoint slices or Service backends in larger clusters |

| Anti-Pattern | What Goes Wrong | Better Alternative |
|---|---|---|
| Restart-first debugging | Restarts erase timing, previous logs, and sometimes the only failing instance | Capture status, previous logs, and events before changing state |
| Treating every pod issue as app code | Scheduler, image, volume, probe, and node failures get misassigned | Classify the failure stage before choosing the owner |
| Editing a live pod | Controllers recreate pods from the original template, so the fix disappears | Change the Deployment, StatefulSet, Job, or source manifest |
| Declaring victory on one green pod | The rollout, readiness, or endpoints may still be unhealthy | Verify controller progress and traffic path, not just one object |

These patterns are intentionally modest because debugging basics should be reliable under stress. A responder who always scopes impact, reads the right witness, and verifies the controller-level outcome will outperform someone who knows many advanced commands but applies them randomly. As you practice, focus less on memorizing exact output and more on recognizing which component could have produced each clue.

Patterns are also a way to protect the team from local folklore. Many teams have a favorite fix, such as restarting pods, increasing memory, or rolling back immediately, because that action solved a memorable incident once. A pattern is stronger than folklore because it says when the action applies, why it works, and what evidence should exist first. That makes it easier to repeat the good part of experience without copying the accidental part.

## When You'd Use This vs Alternatives

Use this basic triage loop when you are facing a fresh workload failure and need to decide where the problem belongs. It is especially useful for KCNA-level incidents such as pods stuck in `Pending`, images that cannot be pulled, containers that crash during startup, pods that run but fail readiness, and rollouts that stall. It gives you a fast path from symptom to likely owner without requiring deep cluster internals, custom observability, or privileged node access.

| Situation | Use the Basic Triage Loop | Use Deeper Tooling |
|---|---|---|
| One new pod fails after a deployment | Yes, compare old and new pods, logs, events, and rollout status | Later, if app traces or metrics are needed |
| Many unrelated pods fail on one node | Yes, scope by node and inspect node conditions | Use node logs and infrastructure tools if node health is unclear |
| A request is slow but all pods are Ready | Partially, verify rollout and restarts first | Use application metrics, tracing, and Service/network debugging |
| A cluster-wide outage affects API access | Limited, because `k` commands may fail | Use control-plane, cloud, and infrastructure diagnostics |

The main tradeoff is that basic triage is excellent at locating the first obvious failure boundary but not always sufficient to explain deep performance or networking behavior. A pod can be Ready while application latency is unacceptable, and a Service can have endpoints while a NetworkPolicy or DNS issue breaks a specific request path. The habit still helps because it eliminates common workload lifecycle failures before you move to logs aggregation, metrics dashboards, distributed traces, packet captures, or cloud-provider diagnostics.

When you do move to deeper tooling, carry the same evidence discipline with you. A metrics dashboard should answer a specific question raised by the pod timeline, such as whether memory climbed before an OOM kill or whether request latency changed after a rollout. A trace should answer a request-path question, not replace basic readiness checks. Advanced tools are most useful when the simple lifecycle evidence has already narrowed the search.

The boundary between basic and advanced debugging is therefore a handoff, not a wall. Basic triage should produce a sentence like, "The pod is Ready, endpoints include it, and restarts are stable, so the next question is request latency through the Service path." That sentence tells the next tool what to prove. It also prevents the team from reopening solved lifecycle questions while a deeper networking, tracing, or application-performance investigation begins.

## Did You Know?

1. **Events are temporary evidence**: many clusters retain events for a limited time, so fresh incident data can disappear before a later review. Production teams usually pair events with centralized logs and metrics because the built-in event stream is a short-term debugging tool.

2. **`Running` is not the same as `Ready`**: a container process can be alive while readiness is false, and Services should avoid routing traffic to that pod. This distinction explains many "the pod is running but users still fail" scenarios.

3. **Previous logs are often more useful than current logs**: in a crash loop, the current container may be waiting, starting, or not yet at the failure point. `k logs -p` asks for the logs from the last terminated instance, which often contains the actual error.

4. **Exit code `137` usually points to a forced kill**: it commonly appears when a container is OOMKilled, although you should verify the `reason` field rather than relying on the number alone. The combination of exit code, reason, and memory limit tells a stronger story than any single field.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Deleting a failing pod before inspection | The replacement may hide previous logs, timing, and events while reproducing the same failure. | Read `describe`, previous logs, and events first, then restart only if the evidence supports it. |
| Treating `Running` as healthy | The process exists, but readiness may be false and Service traffic may still be blocked. | Compare `READY`, conditions, probe events, and Service endpoints before declaring recovery. |
| Reading application logs for an unscheduled pod | The familiar logs command feels like debugging, but no container has run yet. | Read pod events and scheduling constraints with `k describe pod`. |
| Ignoring namespace and context | Similar workload names in different namespaces lead to wrong conclusions or unsafe changes. | Confirm `k config current-context` and use `-n <namespace>` deliberately. |
| Fixing the live pod instead of the controller template | A controller recreates pods from the old template, so direct pod edits do not persist. | Change the Deployment, StatefulSet, Job, or source manifest that owns the pod. |
| Increasing memory limits without checking behavior | A larger limit may postpone a memory leak rather than solve it. | Compare limits with expected usage, inspect app memory behavior, and tune runtime settings when needed. |
| Assuming all replica failures are node failures | Identical failure across replicas often points to shared configuration, image, or dependency issues. | Compare node placement, then inspect shared pod template and previous logs. |
| Skipping verification after a change | One pod may recover while rollout, readiness, or endpoints remain unhealthy. | Verify rollout status, pod readiness, restart counts, events, and Service endpoints. |

## Quiz

<details>
<summary>Your team deploys a new API version, and all new pods show `CrashLoopBackOff` while the old pods remain Ready. What evidence should you collect first, and what kind of root cause are you testing?</summary>

Start with `k logs <new-pod> -n <namespace> -p` because the container has already run and crashed, and the previous instance usually contains the real startup error. Then use `k describe pod <new-pod> -n <namespace>` to confirm last state, exit code, environment references, probes, and events. Because every new replica fails while old replicas work, you are testing a shared new-template problem such as image behavior, command or args, configuration, Secret or ConfigMap references, or a dependency required during startup. This is a debug path for an unhealthy workload because it follows observable evidence rather than guessing.

</details>

<details>
<summary>A pod has been `Pending` for several minutes, has no node assigned, and `k logs` returns an error because the container is not available. What should you check next, and why?</summary>

Run `k describe pod <pod> -n <namespace>` and read the Events section. A pod with no node assigned has not reached the point where application logs can exist, so the scheduler's event messages are the primary evidence. The likely causes include insufficient CPU or memory, untolerated taints, unmatched affinity or node selectors, topology constraints, or an unbound PersistentVolumeClaim. This analyzes pod phase and scheduler evidence before looking at container state.

</details>

<details>
<summary>A Service receives no traffic for a new pod even though `k get pods` shows the pod as `Running` with zero restarts. The `READY` column says `0/1`. How do you debug without being misled by the `Running` phase?</summary>

Treat this as a readiness problem until evidence says otherwise. Use `k describe pod <pod> -n <namespace>` to inspect conditions and probe events, then check whether readiness is failing because of the wrong path, port, scheme, startup delay, timeout, or dependency. You can also inspect `k get endpoints <service> -n <namespace>` to verify whether the pod is excluded from Service routing. The key is to separate pod phase from traffic readiness because `Running` does not mean the workload is usable.

</details>

<details>
<summary>A container repeatedly terminates with reason `OOMKilled`, and the team proposes a rollout restart. Why is that unlikely to be a complete fix, and what should you evaluate instead?</summary>

A rollout restart starts the same process under the same memory limit, so it usually reproduces the same kill after memory usage grows again. You should inspect the pod's memory limit in `k describe pod`, compare it with expected application memory needs, and evaluate whether the limit is too low, the application leaks memory, the runtime heap is misconfigured, or the workload is loading too much data. A limit increase can be a mitigation, but it should match evidence rather than guesswork. This compares OOM evidence with crash and rollout evidence so the action targets the right owner.

</details>

<details>
<summary>An image reference looks correct in the manifest, but the pod shows `ImagePullBackOff`. Your teammate wants to exec into the pod to test registry access. What is wrong with that plan, and what should you do instead?</summary>

You cannot exec into a container that has not been created, and an image pull failure means the application process never started. Use `k describe pod <pod> -n <namespace>` and read the kubelet event messages for the exact pull failure. The message should point toward a missing tag, registry authentication failure, permission problem, DNS or network timeout, or incorrect registry path. This compares image pull failures with runtime failures by asking which evidence exists at that lifecycle stage.

</details>

<details>
<summary>Three unrelated workloads become unhealthy at about the same time, and all affected pods are on `worker-b`. Pods for the same Deployments on other nodes remain healthy. How should you widen the investigation?</summary>

This pattern suggests a node-scoped problem rather than three independent application bugs. Use `k get pods -A -o wide` to confirm placement, then inspect `k describe node worker-b` for conditions such as memory pressure, disk pressure, PID pressure, network unavailable, taints, and recent node events. You should still preserve pod-level evidence, but the shared node is the strongest clue. This evaluates whether the problem belongs to the node instead of the application, pod spec, scheduler, or controller rollout.

</details>

<details>
<summary>A rollout is stuck with two old pods Ready and one new pod Pending. The product owner asks whether users are down. What do you check, and how do you explain the risk?</summary>

Check `k rollout status deployment/<name> -n <namespace>`, `k get pods -n <namespace> -o wide`, and `k describe pod <pending-new-pod> -n <namespace>`. If the old pods remain Ready and selected by the Service, users may still be served, but the rollout is blocked and capacity or redundancy may be reduced. The Pending pod's events will explain whether resources, taints, affinity, or volumes prevent the new version from scheduling. This evaluates the controller rollout separately from the pod scheduling failure and the live traffic path.

</details>

## Hands-On Exercise

In this exercise you will create three small failure scenarios in a practice namespace, classify each failure, and collect the correct evidence before cleanup. Use a disposable local or lab cluster, not a production cluster, because the resources are intentionally broken and will generate events or restarts. The commands assume you have already run `alias k=kubectl`; if your shell does not retain aliases between sessions, define it again before starting.

### Step 1: Create an isolated namespace

Create a namespace so the exercise resources are easy to find and remove. This keeps the practice failures away from other workloads and gives you a clean event timeline. Namespaces are also a useful safety habit because they force you to pass `-n kcna-debug` and stay conscious of the scope you are inspecting.

```bash
k create namespace kcna-debug
k get namespace kcna-debug
```

- [ ] The namespace `kcna-debug` exists and is visible in `k get namespace`.
- [ ] You can run commands with `-n kcna-debug` without changing your default namespace.

### Step 2: Create an image pull failure

Apply a pod that references an image tag that should not exist. The goal is to prove that image pull failures are diagnosed from events, not application logs, because the application process cannot write logs until the kubelet has pulled the image and created the container.

```bash
k apply -n kcna-debug -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: bad-image
spec:
  restartPolicy: Never
  containers:
    - name: app
      image: nginx:no-such-kcna-debug-tag
      ports:
        - containerPort: 80
EOF
```

Wait briefly, then inspect status and events. Notice the order of commands: status tells you the visible symptom, `describe` tells you the kubelet's pull failure, and logs demonstrate why the normal application-debugging path is not useful for this specific stage.

```bash
k get pod bad-image -n kcna-debug
k describe pod bad-image -n kcna-debug
k logs bad-image -n kcna-debug
```

- [ ] The pod shows `ErrImagePull` or `ImagePullBackOff` after the kubelet attempts the pull.
- [ ] The `describe` output contains an event explaining the image pull failure.
- [ ] You can explain why `k logs` is not the right evidence source for this scenario.

### Step 3: Create a crash loop failure

Apply a pod whose container starts, prints a message, and exits with a non-zero code. This scenario is intentionally different from the image pull failure because the container does run, which means previous logs and last state become useful evidence. The goal is to train your eye to move from status to previous logs instead of treating every failure the same way.

```bash
k apply -n kcna-debug -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: crash-demo
spec:
  containers:
    - name: app
      image: busybox:1.36
      command:
        - /bin/sh
        - -c
        - echo "starting demo"; echo "missing required setting"; exit 1
EOF
```

Watch it restart, then read both pod state and previous logs. If your first attempt at `k logs -p` runs before the container has restarted, wait a few moments and try again; the important lesson is that the previous terminated instance is often the clearest witness in a crash loop.

```bash
k get pod crash-demo -n kcna-debug
k logs crash-demo -n kcna-debug -p
k describe pod crash-demo -n kcna-debug
```

- [ ] The pod reaches `CrashLoopBackOff` or shows repeated restarts after several moments.
- [ ] `k logs -p` shows the message from the previous failed container instance.
- [ ] `k describe pod` shows a terminated last state or restart evidence that matches the log output.

### Step 4: Create a scheduling failure

Apply a pod with an intentionally unrealistic memory request. This scenario should remain unscheduled on normal practice clusters, which means the scheduler events are the correct evidence and application logs should not exist. If your cluster is unusually large and the pod schedules, increase the request in your scratch copy rather than changing the lesson's conclusion.

```bash
k apply -n kcna-debug -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: too-large
spec:
  containers:
    - name: app
      image: busybox:1.36
      command:
        - /bin/sh
        - -c
        - sleep 3600
      resources:
        requests:
          memory: "1000Gi"
          cpu: "1"
EOF
```

Inspect placement and scheduler messages. The important detail is the missing node in the wide output and the `FailedScheduling` event in `describe`, because together they show that the pod never reached kubelet container startup.

```bash
k get pod too-large -n kcna-debug -o wide
k describe pod too-large -n kcna-debug
```

- [ ] The pod remains `Pending` and has no assigned node in `k get pod -o wide`.
- [ ] The Events section explains why the scheduler could not place the pod.
- [ ] You can state why restarting this pod would not solve the scheduling failure.

### Step 5: Build a one-page triage note

Write a short note for each failed pod using the same structure: visible symptom, first useful evidence, likely owner, and next safe action. The note can be in your editor, a terminal scratch file, or a team incident template; the important part is the reasoning, not the format. This turns command output into a first-response checklist that preserves evidence and narrows scope before action.

```text
Pod:
Visible symptom:
First useful evidence:
Likely owner:
Next safe action:
```

- [ ] `bad-image` is classified as an image pull failure with kubelet events as the first useful evidence.
- [ ] `crash-demo` is classified as a runtime crash with previous logs as the first useful evidence.
- [ ] `too-large` is classified as a scheduling failure with scheduler events as the first useful evidence.
- [ ] Each next action preserves evidence and targets the likely root cause instead of randomly restarting resources.
- [ ] Your first-response checklist explicitly covers debug, analyze, compare, evaluate, and design decisions from the learning outcomes.

### Step 6: Clean up the practice namespace

Remove the namespace after you finish so the intentionally broken resources do not keep generating events or restarts. Cleanup is part of debugging discipline because a lab failure left behind can confuse future practice, and in shared clusters it can waste resources or distract another learner.

```bash
k delete namespace kcna-debug
```

- [ ] `k get namespace kcna-debug` no longer shows the namespace after deletion completes.
- [ ] You can explain the three different failure classes without looking up the commands.

## Sources

- [Kubernetes: Debug Applications](https://kubernetes.io/docs/tasks/debug/debug-application/)
- [Kubernetes: Debug Clusters](https://kubernetes.io/docs/tasks/debug/debug-cluster/)
- [Kubernetes: Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Kubernetes: Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes: Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)
- [Kubernetes: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Kubernetes: kube-scheduler](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
- [Kubernetes: Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Kubernetes: Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [kubectl logs reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)
- [kubectl describe reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_describe/)
- [kubectl get reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_get/)
- [kubernetes.io: pod condition](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/) — The Pod Conditions documentation defines these built-in conditions and states that non-Ready Pods are removed from matching Service load-balancing pools.
- [kubernetes.io: kube apiserver](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/) — The kube-apiserver reference documents the `--event-ttl` retention setting and its default, which supports the operational point that events are not kept indefinitely.
- [kubernetes.io: assign memory resource](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/) — The official memory-resource task includes a concrete OOMKilled example showing `reason: OOMKilled` alongside `exitCode: 137`.
- [Kubernetes Docs: Images](https://kubernetes.io/docs/concepts/containers/images/) — Covers image-pull behavior, `ImagePullBackOff`, registry authentication context, and why image failures happen before application logs exist.

## Next Module

Continue to [Part 2: Container Orchestration - Module 2.1: Scheduling](/k8s/kcna/part2-container-orchestration/module-2.1-scheduling/) to learn how Kubernetes decides where to place your pods.
