---
citations_verified: true
title: "Module 5.1: Troubleshooting Methodology"
revision_pending: false
slug: k8s/cka/part5-troubleshooting/module-5.1-methodology
sidebar:
  order: 2
lab:
  id: cka-5.1-methodology
  url: https://killercoda.com/kubedojo/scenario/cka-5.1-methodology
  duration: "60 min"
  difficulty: intermediate
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Foundation for every CKA troubleshooting task and for real production response work
>
> **Time to Complete**: 50-65 minutes
>
> **Prerequisites**: Parts 1-4 completed, including cluster architecture, workloads, networking, storage, and basic kubectl fluency

---

## Learning Outcomes

After this module, you will be able to:

- **Apply** a systematic troubleshooting loop that moves from symptom capture to hypothesis testing, repair, and validation without random changes.
- **Diagnose** Kubernetes failures by identifying whether the first broken layer is application, container, pod, service, node, storage, network, or control plane.
- **Evaluate** diagnostic evidence from `describe`, Events, logs, resource status, object YAML, and node conditions to choose the next investigation step.
- **Compare** similar-looking failure states such as `Pending`, `ContainerCreating`, `CrashLoopBackOff`, `Running but not Ready`, and `Service has no endpoints`.
- **Design** a short exam-time troubleshooting plan that protects time, preserves evidence, and proves the fix before moving to the next task.

---

## Why This Module Matters

A platform engineer named Mira is on call when a rollout begins failing during a payment-service release. The dashboard says error rate is rising, the deployment controller says progress has stalled, and three teammates are already suggesting fixes in chat. One person wants to restart every pod, another wants to roll back immediately, and another says the problem must be DNS because that was the last incident they remember. If Mira follows the loudest guess, she may erase the evidence, make the outage wider, and still not know what actually failed.

Kubernetes troubleshooting rewards disciplined curiosity more than command memorization. The cluster is constantly reconciling desired state into actual state, so every failure leaves clues in different places: scheduler events, kubelet events, container logs, endpoint objects, node conditions, controller status, and sometimes the raw object spec. The operator's job is to read those clues in the right order, form a small hypothesis, test it, and change only the thing that evidence supports.

This matters on the CKA because [troubleshooting is a large exam domain and the time pressure is real](https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/). It matters even more in production because the first five minutes of an incident often determine whether the team learns quickly or scatters into disconnected guesses. A repeatable method gives you a calm path through noisy symptoms, and it lets another engineer follow your reasoning after the fix.

> **The Emergency Room Analogy**
>
> A strong emergency-room physician does not start with surgery because a patient says "it hurts." They stabilize, observe symptoms, check vital signs, order targeted tests, decide which system is failing, and only then treat. Kubernetes troubleshooting works the same way. You start with the visible symptom, gather low-risk evidence, isolate the failing layer, then apply the smallest fix that addresses the diagnosed cause.

Before the commands begin, confirm that your `kubectl` client is available and pointed at the intended cluster. This module writes every runnable example with the full `kubectl` command because copied shell blocks should work in non-interactive terminals, scripts, and exam environments without relying on local aliases.

```bash
kubectl version --client
```

---

## Part 1: Think Like an Investigator Before You Think Like an Operator

Troubleshooting begins before the first command because the most expensive mistakes are usually thinking mistakes. A learner who knows twenty kubectl commands but lacks a process will often bounce between logs, YAML, restarts, and edits without knowing which clue matters. A disciplined operator first decides what kind of evidence would separate one possible cause from another.

The process in this module uses five verbs: observe, isolate, inspect, repair, and validate. These are deliberately plain words because they map to actions you can perform under pressure. Observe the symptom without changing it, isolate the layer where the failure first appears, inspect the most relevant evidence at that layer, repair the smallest confirmed cause, and validate from the user's point of view rather than from the command that made the change.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         TROUBLESHOOTING FRAMEWORK                            │
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │ 1. OBSERVE   │──▶│ 2. ISOLATE   │──▶│ 3. INSPECT   │──▶│ 4. REPAIR    │  │
│  │ symptom and  │   │ failing      │   │ evidence and │   │ smallest     │  │
│  │ blast radius │   │ layer        │   │ test cause   │   │ confirmed fix│  │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘  │
│                                                                      │       │
│                                                                      ▼       │
│                                                            ┌──────────────┐  │
│                                                            │ 5. VALIDATE  │  │
│                                                            │ workload and │  │
│                                                            │ user path    │  │
│                                                            └──────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

The old four-step version of this process said identify, isolate, diagnose, and fix. That is still useful, but the added validation step prevents a common production failure: stopping when the pod turns green even though the service still has no endpoints or the application still returns errors. A Kubernetes object can look healthy in one view while the complete request path is still broken.

A good troubleshooting session also preserves a timeline. You do not need a formal incident document during a CKA task, but you should mentally track what changed, what you observed before the change, and what proved the fix. In production, that habit becomes the foundation for handoffs, post-incident review, and preventing repeat failures.

### 1.1 Observe the Symptom Without Mutating the Cluster

The first observation pass should be broad, fast, and read-only. You want to know whether the problem is isolated to one namespace, one workload, one node, or the entire cluster. This pass should not include `delete`, `edit`, `rollout restart`, or any command that changes state, because those commands can hide the original failure.

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get events -A --sort-by='.lastTimestamp' | tail -30
kubectl -n kube-system get pods -o wide
```

The output of these commands gives you a rough map. If every namespace shows pods stuck in `Pending`, the scheduler or cluster capacity may be involved. If only one deployment is crashing, the first broken layer is likely workload-specific. If many pods on one node are `Unknown` or `ContainerStatusUnknown`, the node-to-control-plane path deserves attention before you inspect application logs.

| Observation | What It Suggests | Safer Next Step |
|---|---|---|
| One new pod is `ImagePullBackOff` | Image name, tag, registry, or pull secret issue | `kubectl describe pod <pod> -n <ns>` |
| Many pods are `Pending` across namespaces | Capacity, taints, scheduler, or node availability issue | `kubectl describe pod <pod> -n <ns>` and `kubectl describe node <node>` |
| Pods on one node are `Unknown` | Kubelet, node network, runtime, or node health issue | `kubectl describe node <node>` before restarting workloads |
| Service returns connection refused | Endpoint, target port, readiness, or app listener issue | `kubectl get endpointslices -n <ns> -l kubernetes.io/service-name=<svc>` |
| `kubectl` is slow or times out | API server, etcd, control plane, or network path issue | [`kubectl get --raw='/readyz?verbose'`](https://kubernetes.io/docs/reference/using-api/health-checks/) if the API responds |

A precise symptom is more valuable than a dramatic symptom. "The app is down" is too broad to test. "Requests to `checkout.default.svc.cluster.local:8080` time out from the frontend pod, while direct requests to the checkout pod IP succeed" is specific enough to separate service routing from application health.

### 1.2 Active Learning Prompt: Choose the First Read-Only Command

A teammate says, "The new pod is broken, just delete it and let Kubernetes recreate it." Before you accept that advice, decide what evidence deletion would destroy. If the pod is stuck because of an image pull error, deleting it will create another pod with the same event. If it is crashing, deleting it may remove previous container logs and restart-count history that would explain the failure.

Write down the first read-only command you would run for each symptom before reading the answers. For `CrashLoopBackOff`, the strongest first command is usually `kubectl describe pod <pod> -n <namespace>` because Events and container state tell you whether the crash is actually an application exit, a probe failure, or a config problem. For `Service has no traffic`, the strongest first command is usually `kubectl get endpointslices` or `kubectl get endpoints` for the service, because a service without endpoints cannot route even if the service object exists.

### 1.3 Isolate by Layer, Not by Guess

Isolation means reducing the search space without yet claiming root cause. Kubernetes problems usually cross object boundaries, so the failing object is not always the faulty object. A service can be correct while its selector points at no ready pods. A pod can be healthy while a network policy blocks traffic. A deployment can be stalled because the underlying pod template references a missing secret.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ISOLATION LAYERS                                │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ CLUSTER: API server, scheduler, controller manager, etcd, admission     │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │ NODE: kubelet, container runtime, CNI, kube-proxy, local pressure │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │ POD: scheduling, volumes, image pulls, probes, conditions   │  │  │  │
│  │  │  │  ┌──────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │ CONTAINER: process, command, env, filesystem, limits  │  │  │  │  │
│  │  │  │  │  ┌────────────────────────────────────────────────┐  │  │  │  │  │
│  │  │  │  │  │ APPLICATION: config, dependency, protocol, bug  │  │  │  │  │  │
│  │  │  │  │  └────────────────────────────────────────────────┘  │  │  │  │  │
│  │  │  │  └──────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Start with the widest observed symptom, then drill down only where evidence  │
│  points. Do not inspect application logs for a pod that has never scheduled.  │
└──────────────────────────────────────────────────────────────────────────────┘
```

The layer model prevents wasted commands. If a pod is still `Pending`, inspect `describe` and Events first because the application container may not have started yet, so logs may be absent or not yet useful. If a service has no endpoints, testing DNS first may prove only that DNS resolves the service name, not that the service can send traffic anywhere. If the API server is intermittently unreachable, editing deployment YAML may be irrelevant because the control plane itself may be the first failure.

| Failure Layer | Typical Evidence | Commands That Usually Help |
|---|---|---|
| Application | Process exits, HTTP errors, dependency failures, bad config values | `kubectl logs`, `kubectl exec`, app health endpoint checks |
| Container | Bad command, missing binary, wrong environment, OOM kill | `kubectl describe pod`, `kubectl logs --previous`, JSONPath status |
| Pod | Image pull, volume mount, probe failure, missing ConfigMap or Secret | `kubectl describe pod`, `kubectl get pod -o yaml` |
| Service | No endpoints, wrong selector, wrong targetPort, not-ready pods excluded | `kubectl get svc`, `kubectl get endpointslices`, label comparison |
| Node | `NotReady`, pressure conditions, kubelet or runtime failure | `kubectl describe node`, `journalctl -u kubelet`, runtime status |
| Cluster | API timeout, scheduler failure, controller loops not reconciling | `kubectl get --raw='/readyz?verbose'`, kube-system pod logs |

### 1.4 Inspect Evidence in an Order That Matches the Lifecycle

A pod moves through a lifecycle, and the diagnostic order should follow that lifecycle. First ask whether Kubernetes accepted the desired state. Then ask whether the scheduler placed the pod. Then ask whether [the kubelet could prepare volumes and images. Then ask whether the container process started, stayed alive, and became ready.](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) Only after those checks should you decide that the application itself is misbehaving.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         POD LIFECYCLE DIAGNOSTIC ORDER                       │
│                                                                              │
│  YAML accepted ─▶ scheduled ─▶ volumes ready ─▶ image pulled ─▶ process starts │
│        │             │              │               │              │          │
│        ▼             ▼              ▼               ▼              ▼          │
│  API errors     FailedScheduling  FailedMount   ErrImagePull   CrashLoop      │
│  admission      taints/resources  missing PVC   auth or tag     app/probe     │
│                                                                              │
│  Ready for service traffic happens later, after readiness probes and endpoint │
│  publication succeed. A Running pod can still be excluded from a Service.     │
└──────────────────────────────────────────────────────────────────────────────┘
```

The lifecycle order is why `describe` is so powerful. It combines scheduling events, kubelet events, container state, volume information, conditions, and recent warnings in one place. Logs are still essential, but logs answer "what did the container process say?" They do not answer "why did the pod never mount its secret?" or "why did the scheduler reject every node?"

### 1.5 Repair the Smallest Confirmed Cause

The best repair is the smallest change that directly addresses the confirmed cause. If a deployment references `nginx:latestt`, set the image to a valid tag; do not rebuild the deployment from memory. If a service selector is `app: api` while pods are labeled `app: backend`, change one side intentionally; do not recreate the namespace. Small repairs reduce risk, make validation easier, and preserve the reasoning chain for review.

```bash
kubectl set image deployment/web -n prod app=nginx:1.27
kubectl patch service web -n prod --type='merge' -p '{"spec":{"selector":{"app":"web"}}}'
kubectl create configmap app-config -n prod --from-literal=MODE=production
```

In production, a repair should usually have a rollback path. On the CKA, the rollback path may simply be knowing the exact command you ran and verifying the result immediately. In a team environment, it means recording the change, using version-controlled manifests when possible, and resisting the temptation to make multiple speculative fixes at once.

### 1.6 Validate the Workload Path, Not Just the Object Status

Validation should match the original symptom. If the symptom was "frontend cannot call backend," then seeing the backend pod `Running` is not enough. You need to test from a similar source pod, through the same service name, port, and protocol that failed. If the symptom was "deployment rollout is stuck," then `kubectl rollout status` is a better validation command than a one-time `kubectl get pods`.

```bash
kubectl rollout status deployment/backend -n prod --timeout=90s
kubectl get pods -n prod -l app=backend -o wide
kubectl get endpointslices -n prod -l kubernetes.io/service-name=backend
kubectl exec -n prod deploy/frontend -- wget -qO- http://backend:8080/healthz
```

Validation also includes checking that the fix did not create a new failure. A pod that restarts successfully but loses its endpoints because readiness now fails is not fixed. A service that starts routing traffic after you loosen a selector may now route to unrelated pods. Validate the path that users or dependent workloads actually use whenever you can.

---

## Part 2: The Kubernetes Component Map

A component map turns symptoms into search directions. You do not need to memorize every internal detail of each component, but you should know which component owns each stage of the request or lifecycle. This knowledge is what lets you avoid checking CoreDNS for a pod that never scheduled or checking application logs for a service selector mismatch.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            COMPONENT FAILURE MAP                             │
│                                                                              │
│  SYMPTOM OR OBSERVATION                 CHECK THESE COMPONENTS FIRST          │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  Pods not scheduling                  → kube-scheduler, node resources        │
│  Pods stuck Pending                   → scheduler, taints, affinity, quotas   │
│  Pods stuck ContainerCreating         → kubelet, image pull, volumes, CSI     │
│  Pods CrashLoopBackOff                → container process, probes, app config │
│  Pods Running but not Ready           → readiness probe, app listener, deps   │
│  Pods cannot communicate              → CNI, NetworkPolicy, DNS, routes       │
│  Services have no endpoints           → selectors, readiness, pod labels      │
│  Services route to wrong pods         → selector too broad or stale labels    │
│  kubectl times out                    → API server, etcd, control plane path  │
│  Node NotReady                        → kubelet, runtime, network, pressure   │
│  Persistent volume issues             → PVC, PV, StorageClass, CSI driver     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

This map is not a replacement for evidence. It is a shortcut for choosing the next useful evidence source. For example, `CrashLoopBackOff` points toward container and application evidence, but the immediate cause could still be a failed liveness probe killing a healthy-but-slow application. That is why you inspect both Events and previous logs before declaring the cause.

### 2.1 Control Plane Components and Their Failure Shapes

[Control plane failures usually affect many workloads or make the cluster stop reconciling.](https://kubernetes.io/docs/concepts/overview/components/) [If the API server is down, nearly every kubectl command fails. If the scheduler is down, existing pods may keep running but new pods stay unscheduled. If the controller manager is down, deployments, replica sets, jobs, and endpoint updates may stop moving toward desired state.](https://kubernetes.io/docs/concepts/overview/components/)

| Component | What It Owns | Failure Shape | Useful First Evidence |
|---|---|---|---|
| kube-apiserver | Kubernetes API, admission, authentication, object writes | `kubectl` timeouts, errors, or failed object creation | `kubectl get --raw='/readyz?verbose'` |
| etcd | Durable cluster state for API objects | API errors, stale reads, failed writes, control plane instability | API server logs and readiness output |
| kube-scheduler | Assigning unscheduled pods to nodes | Pods remain `Pending` with scheduling events | `kubectl describe pod <pod>` |
| kube-controller-manager | Reconciliation for deployments, jobs, endpoints, nodes | Desired state stops converging after objects are accepted | kube-system pod logs and object status |
| cloud-controller-manager | Cloud load balancers, routes, cloud node integration | LoadBalancer pending, cloud routes missing | cloud-controller logs and service events |

A control plane component can fail silently from the perspective of one application. A single deployment stuck with `ProgressDeadlineExceeded` may look application-specific until you notice new pods in other namespaces are also not scheduling or controllers are not creating replacement pods. The broader your symptom, the more you should suspect shared components.

### 2.2 Node Components and Their Failure Shapes

Node-level failures often present as pods failing only on one node or as pods entering states that depend on kubelet work. [The kubelet turns scheduled pods into running containers, mounts volumes, reports status, and executes probes. The container runtime pulls images and starts containers. The CNI plugin wires pod networking. kube-proxy or an eBPF replacement implements service routing depending on cluster configuration.](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)

| Component | What It Owns | Failure Shape | Useful First Evidence |
|---|---|---|---|
| kubelet | Pod lifecycle on a node, status reporting, probes, volume setup | Node `NotReady`, pods stuck creating, probe events | `kubectl describe node <node>` and kubelet logs |
| container runtime | Image pulls, container starts, container exits | `ImagePullBackOff`, start failures, runtime errors | Pod events and runtime service status |
| CNI plugin | Pod network interface and routing setup | Pods cannot get network, cross-pod traffic fails | kubelet events and CNI pod logs |
| kube-proxy or service dataplane | Service virtual IP routing | Service reachable from some paths but not others | endpoints, node dataplane logs, service tests |
| CSI node plugin | Mounting and attaching storage on the node | `FailedMount`, PVC attach or mount events | pod events, PVC/PV status, CSI logs |

A useful node question is "does the same pod template fail on every node or only on this node?" If only one node shows the failure, inspect node conditions and local components. If the same failure follows the workload across nodes, inspect the workload spec, external dependencies, or shared cluster services.

### 2.3 Workload Controllers as Evidence, Not Just Containers

Deployments, ReplicaSets, StatefulSets, DaemonSets, and Jobs each add their own status and event trail. A pod crash is often visible at the pod, but a rollout failure is visible at the deployment. A Job failure may require looking at completed or failed pods that the controller created earlier. A StatefulSet storage issue may appear in PVCs as much as in pod events.

```bash
kubectl describe deployment <name> -n <namespace>
kubectl rollout status deployment/<name> -n <namespace> --timeout=90s
kubectl get rs -n <namespace> -l app=<label> -o wide
kubectl get jobs -n <namespace>
kubectl describe job <name> -n <namespace>
```

Controllers are especially useful for distinguishing a one-pod symptom from a desired-state problem. If one pod is unhealthy but the ReplicaSet has created replacements, Kubernetes may be recovering. If the deployment cannot create new ReplicaSets or the rollout deadline has been exceeded, the controller is telling you the workload as a whole is not converging.

### 2.4 Active Learning Prompt: Follow the Ownership Boundary

Imagine a service named `checkout` exists, DNS resolves `checkout.default.svc.cluster.local`, but requests hang until they time out. The backend pods are `Running`, yet `kubectl get endpoints checkout` returns no addresses. Before checking CoreDNS logs, explain why the empty endpoint object is stronger evidence than the successful DNS lookup.

The answer is that DNS only proves the service name resolves to the service virtual IP. It does not prove that Kubernetes has any ready backend pods selected for that service. Empty endpoints point toward selector mismatch, readiness probe failure, or pods not matching the service's namespace and labels, so the next checks should compare service selectors against pod labels and readiness conditions.

---

## Part 3: The Diagnostic Command Ladder

The command ladder is a deliberate order, not a command glossary. Each rung answers a different question and should influence the next rung. You climb only as far as needed, and you do not jump into high-risk or high-detail commands before simpler evidence narrows the path.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              COMMAND LADDER                                  │
│                                                                              │
│  1. OVERVIEW       kubectl get pods -A        What is affected and where?     │
│  2. EVENTS         describe / get events      What did Kubernetes report?     │
│  3. STATUS         get -o yaml/jsonpath       What state does the API store?  │
│  4. LOGS           kubectl logs --previous    What did the process say?       │
│  5. IN-POD TEST    kubectl exec               What happens from inside path?  │
│  6. NODE TEST      journalctl / systemctl     Is the local agent healthy?     │
│  7. CONTROL PLANE  readyz / kube-system logs  Are shared components healthy?  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

The ladder also protects exam time. You can answer many CKA troubleshooting tasks with the first four rungs: `get`, `describe`, `logs`, and a targeted fix. Node and control plane checks matter, but they should follow evidence rather than replace basic workload inspection.

### 3.1 Overview Commands

Overview commands answer "what is broken?" and "how wide is it?" They should be fast enough that you can run them without losing momentum. Use namespaces and labels whenever you know them, but begin wider when the symptom is unclear.

```bash
kubectl get pods -A -o wide
kubectl get nodes -o wide
kubectl get deploy,rs,pods -n <namespace>
kubectl get svc,endpoints,endpointslices -n <namespace>
kubectl get events -A --sort-by='.lastTimestamp' | tail -30
```

The `-o wide` flag is valuable because it adds placement information, pod IPs, and node names. If every failing pod is on the same node, the problem is probably not the application image. If failing pods span nodes but share the same deployment revision, the problem may be inside the pod template or application release.

### 3.2 Describe Before Logs

[`describe` is usually the best second command because it includes Kubernetes' own explanation of recent failures.](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) [It shows events, selected node, volumes, container state, last termination state, readiness, restart count, and probe messages.](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) Logs can explain a running process, but they cannot explain why the process never started.

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl describe deployment <deployment-name> -n <namespace>
kubectl describe node <node-name>
kubectl describe pvc <claim-name> -n <namespace>
```

A strong operator reads `describe` from both top and bottom. The top tells you the current state and object relationships. The Events section at the bottom tells you what the scheduler, kubelet, and controllers tried to do and why they failed. In many failures, the Events section is the shortest route to root cause.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DESCRIBE OUTPUT SECTIONS                             │
│                                                                              │
│  SECTION              WHAT TO LOOK FOR                                        │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  Name / Namespace      Confirm you are inspecting the intended object         │
│  Node                  See whether the pod was scheduled and where it landed  │
│  Status                Current phase, but not the full health story           │
│  IP / Controlled By    Pod address and owning controller                      │
│  Containers            State, Ready, Restart Count, Last State, image         │
│  Conditions            PodScheduled, Initialized, Ready, ContainersReady      │
│  Volumes               ConfigMaps, Secrets, PVCs, projected service account   │
│  QoS Class             Resource request and limit class affecting eviction    │
│  Events                Scheduler, kubelet, mount, image, probe, and warnings  │
│                                                                              │
│  The Events section is often the highest-value evidence, but it is not the    │
│  only section. Container state and conditions tell you whether the event is   │
│  current, historical, or already resolved.                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Logs and Previous Logs

[Logs answer what the container process wrote to stdout and stderr](https://kubernetes.io/docs/concepts/cluster-administration/logging/) — the default application logging path Kubernetes expects. For a pod that has restarted, [current logs may show only the new container instance, which can hide the actual crash. Use `--previous` when the restart count is greater than zero or when the Events section says the container terminated.](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)

```bash
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
kubectl logs <pod-name> -n <namespace> -c <container-name>
kubectl logs deployment/<deployment-name> -n <namespace> --tail=100
```

Multi-container pods require explicit container selection. A sidecar may look healthy while the application container is failing, so always identify container names before concluding that logs are clean. The pod spec and JSONPath can list containers quickly.

```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].name}{"\n"}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].name}{"\n"}'
```

### 3.4 YAML and JSONPath for Precise Evidence

When `describe` summarizes too much, read the stored API object directly. YAML is useful for comparing selectors, labels, probes, resources, mounts, tolerations, and environment references. JSONPath is useful when you need one exact field during an exam or when you want to avoid visually scanning a large object.

```bash
kubectl get pod <pod-name> -n <namespace> -o yaml
kubectl get svc <service-name> -n <namespace> -o yaml
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.phase}{"\n"}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].restartCount}{"\n"}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

YAML is also where you catch subtle mismatch problems. A service selector of `app: web` will not select pods labeled `app.kubernetes.io/name: web`. A volume referencing `configMap.name: app-config` will fail if the ConfigMap exists in a different namespace, because namespaced references do not cross namespace boundaries.

### 3.5 Events as Time-Ordered Evidence

[Kubernetes Events are short-lived signals emitted by controllers and node agents. They are not a full logging system](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/), but [they are often the best immediate evidence for scheduling, image pull, mount, and probe failures](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/). Sort them by timestamp when the namespace has many objects.

```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
kubectl get events -A --field-selector type=Warning --sort-by='.lastTimestamp'
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```

Events can be noisy and may expire, so do not treat a missing event as proof that nothing happened. If an issue occurred hours ago, use workload status, logs, metrics, and external observability where available. On the CKA, events are most useful for active failures happening while you investigate.

### 3.6 In-Pod Network and DNS Tests

Network tests are meaningful only when run from the right place. Testing a service from your laptop is not the same as testing it from a pod in the same namespace and policy context. For cluster-internal failures, run a temporary pod or exec into a related pod and test the same DNS name, port, and protocol the application uses.

```bash
kubectl run netcheck -n <namespace> --image=busybox:1.36 --restart=Never -- sleep 3600
kubectl exec -n <namespace> netcheck -- nslookup kubernetes.default.svc.cluster.local
kubectl exec -n <namespace> netcheck -- wget -qO- http://<service-name>:<port>/healthz
kubectl delete pod netcheck -n <namespace>
```

If your cluster image lacks `wget` or `nslookup`, choose a debug image available in the environment. In a restricted environment, a minimal debug image is often enough for DNS and simple HTTP checks. The important habit is matching the source and destination path instead of testing from a place that bypasses the failure.

### 3.7 Node and Control Plane Checks

Node checks become appropriate when evidence points below the pod spec. A pod stuck in `ContainerCreating` with repeated runtime errors, many pods failing on one node, or a node marked `NotReady` all justify moving to node-level evidence. [On kubeadm-style exam clusters](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/), [control plane components often run as static pods in `kube-system`](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/), while kubelet runs as a system service on the node.

```bash
kubectl describe node <node-name>
kubectl -n kube-system get pods -o wide
kubectl -n kube-system logs <control-plane-pod-name> --tail=100
ssh <node-name> "systemctl status kubelet --no-pager"
ssh <node-name> "journalctl -u kubelet --no-pager -n 100"
ssh <node-name> "systemctl status containerd --no-pager"
```

Do not begin with SSH simply because it feels powerful. SSH is appropriate when Kubernetes evidence says the node agent, runtime, local storage, or local network is the likely broken layer. If the failure is a bad image tag in a deployment, logging into the node wastes time and adds risk.

---

## Part 4: Reading Pod Status Without Being Fooled

[Pod status is a useful signal, but it is not a complete health verdict. `Running` means at least one container is running or has run, not that the application is ready to serve traffic. `Pending` may mean the scheduler has not placed the pod, but it can also include time before images and volumes are prepared.](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) You must connect phase, conditions, container state, restart count, and events.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  POD PHASES                                  │
│                                                                              │
│                 ┌────────────┐                                               │
│                 │  Pending   │                                               │
│                 │ scheduling │                                               │
│                 │ or setup   │                                               │
│                 └─────┬──────┘                                               │
│                       │                                                      │
│                       ▼                                                      │
│                 ┌────────────┐        all app containers exit 0              │
│                 │  Running   │───────────────────────────────┐               │
│                 │ process or │                               ▼               │
│                 │ containers │                         ┌────────────┐        │
│                 └─────┬──────┘                         │ Succeeded  │        │
│                       │ one container exits non-zero    │ completed  │        │
│                       ▼                                 └────────────┘        │
│                 ┌────────────┐                                               │
│                 │   Failed   │                                               │
│                 │ terminal   │                                               │
│                 └────────────┘                                               │
│                                                                              │
│                 ┌────────────┐                                               │
│                 │  Unknown   │  node communication lost or status unavailable│
│                 └────────────┘                                               │
│                                                                              │
│  Phase is broad. Conditions and container states explain readiness, restarts, │
│  scheduling, image pulls, probe failures, and last termination reason.         │
└──────────────────────────────────────────────────────────────────────────────┘
```

A pod can have phase `Running` while condition `Ready=False`. This happens when the container process is alive but readiness probes fail, a sidecar is not ready, or the application is not listening on the expected port. [Services normally route only to ready endpoints, so `Running` pods can still receive no traffic](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/).

### 4.1 Common Pod States and Their First Useful Check

The table below connects visible status to the first check that usually gives the highest-value evidence. It is not a script to follow blindly, but it prevents the most common mismatch between symptom and command. Notice that logs are not always first because many states happen before the process writes logs.

| Visible Status | What It Usually Means | First Useful Check | What You Are Trying to Prove |
|---|---|---|---|
| `Pending` | Pod not scheduled or waiting for setup | `kubectl describe pod` | Resources, taints, affinity, quota, or scheduling rejection |
| `ContainerCreating` | Assigned to node, kubelet preparing container | `kubectl describe pod` | Image pull, volume mount, CNI, or Secret/ConfigMap reference |
| `ImagePullBackOff` | Image pull failed and kubelet is backing off | `kubectl describe pod` | Bad image, bad tag, registry auth, or unreachable registry |
| `CreateContainerConfigError` | Container config cannot be constructed | `kubectl describe pod` | Missing ConfigMap, Secret, key, or invalid env reference |
| [`CrashLoopBackOff`](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) | Container repeatedly exits after starting | `kubectl describe pod`, then `kubectl logs --previous` | Probe failure, app error, bad command, OOM, or dependency failure |
| `Running` but `Ready=False` | Process started but not eligible for service | `kubectl describe pod` and readiness details | Failing readiness probe, wrong port, dependency, or slow startup |
| `Evicted` | Kubelet removed pod because node pressure or policy | `kubectl describe pod` and `kubectl describe node` | Memory, disk, PID pressure, priority, or resource requests |
| `Unknown` | Control plane cannot get current status from node | `kubectl describe node` | Kubelet, node network, runtime, or node availability |

### 4.2 CrashLoopBackOff Worked Example

This worked example demonstrates the full loop before you solve similar failures in the exercise. The scenario is simple: a pod starts, exits immediately, and Kubernetes restarts it with exponential backoff. The goal is not just to fix the pod, but to practice evidence order.

Create a namespace and a deliberately crashing pod. This pod uses BusyBox and exits with status `1`, so the failure is deterministic and safe to reproduce in a practice cluster.

```bash
kubectl create ns method-demo
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-demo
  namespace: method-demo
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - echo "starting demo"; sleep 2; echo "failing now"; exit 1
EOF
```

Observe without changing the pod. The first command tells you the visible status and restart count. It does not yet prove why the container is failing.

```bash
kubectl get pod crash-demo -n method-demo
```

Now inspect Kubernetes evidence. The Events section will show the container starting and backoff behavior, while the container state will show termination details. This explains that Kubernetes can start the container, so the failure is after the process begins.

```bash
kubectl describe pod crash-demo -n method-demo
```

Move to previous logs because the current container may already have restarted. [The `--previous` flag asks for logs from the last terminated instance](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), which is exactly where the crash message lives. On fast clusters, wait a few seconds after the first restart before running `--previous`; the kubelet may not have flushed the prior instance's log buffer yet.

```bash
kubectl logs crash-demo -n method-demo --previous
```

Use JSONPath to confirm the exit code. This is not always necessary, but it is useful when deciding between application exit, signal termination, and OOM behavior. Exit code `1` here confirms a normal application-level failure, not a scheduler, image, or volume failure.

```bash
kubectl get pod crash-demo -n method-demo -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

Repair the pod by replacing the failing command with a long-running command. In normal production work you would edit version-controlled manifests or update the deployment template, but a standalone practice pod can be replaced directly.

```bash
kubectl delete pod crash-demo -n method-demo
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-demo
  namespace: method-demo
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - echo "starting demo"; sleep 3600
EOF
```

Validate the original symptom. The pod should stop restarting, and the logs should show startup without the failure message. You are not validating a theoretical fix; you are checking that the observed failure state has changed.

```bash
kubectl get pod crash-demo -n method-demo
kubectl logs crash-demo -n method-demo
```

The lesson from this example is the sequence. `describe` proved that the container started and restarted. `logs --previous` revealed what the terminated process wrote. JSONPath confirmed the exit code. The repair changed only the confirmed failing command. Validation checked the same object and symptom that were originally broken.

### 4.3 Exit Codes and Termination Reasons

Exit codes are compact but easy to overinterpret. Kubernetes records termination reason, exit code, signal, and sometimes a message. You should combine exit code with pod Events, resource limits, and application logs before deciding the cause.

| Exit or Reason | Likely Meaning | Confirm With | Typical Repair Direction |
|---|---|---|---|
| Exit code `1` | Application returned a generic error | `kubectl logs --previous` | Fix command, config, dependency, or application bug |
| Exit code `126` | Command found but not executable | Container image and command field | Fix file permissions or command path |
| Exit code `127` | Command not found | Pod spec command and image contents | Use correct binary or image |
| Exit code `137` | SIGKILL, often OOMKilled | `Last State`, pod limits, node pressure | Adjust memory, fix leak, tune requests and limits |
| Exit code `143` | SIGTERM, often graceful stop | Events, rollout, eviction, termination timing | Check controller action or shutdown behavior |
| Reason `OOMKilled` | Container exceeded memory limit or node pressure killed it | `kubectl describe pod` and metrics | Increase limit only after understanding usage |
| Reason `Error` | Process exited non-zero | logs and application config | Fix application-level cause |
| Reason `Completed` in a long-running pod | Process exited zero unexpectedly for workload type | command, args, controller type | Use correct controller or long-running command |

A common mistake is treating OOMKilled as simply "increase memory." Sometimes that is correct, but not always. If the application suddenly uses ten times normal memory after a release, raising limits may hide a regression. If the pod has no memory request and lands on a crowded node, setting appropriate requests may be as important as changing the limit.

### 4.4 Running Does Not Mean Ready

Readiness is the bridge between a running process and service traffic. Kubernetes can run a container process while excluding it from service endpoints because the readiness probe fails. This is a healthy behavior: it prevents traffic from reaching a pod that is not prepared to serve.

```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
kubectl describe pod <pod-name> -n <namespace> | sed -n '/Readiness/,/Environment/p'
kubectl get endpointslices -n <namespace> -l kubernetes.io/service-name=<service-name>
```

The `sed` range above assumes a fixed section order in `describe` output; section order can vary by Kubernetes version, so fall back to reading the full description when the range returns nothing useful.

When a service has no endpoints and pods are `Running`, compare readiness and labels before debugging DNS. DNS resolution can succeed even when the endpoint set is empty. The service virtual IP may exist, but kube-proxy or the service dataplane has no ready backend addresses to send traffic to.

---

## Part 5: Service, Network, and Storage Triage

Workload troubleshooting often expands into service, network, or storage because Kubernetes composes many objects into one application path. A deployment may be correct while its service selector is wrong. A pod may be ready while a NetworkPolicy blocks the calling namespace. A database pod may be stuck because the PVC cannot bind. The method stays the same: observe, isolate, inspect, repair, validate.

### Service Path Debugging

Service debugging starts by separating name resolution from endpoint selection and port routing. [DNS can resolve a service name even when the service has no endpoints. Endpoints can exist while the service targets the wrong port. The application can listen on one port while the service `targetPort` points to another.](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            SERVICE REQUEST PATH                              │
│                                                                              │
│  Client Pod                                                                  │
│     │                                                                        │
│     │ 1. DNS lookup: backend.default.svc.cluster.local                        │
│     ▼                                                                        │
│  Service Virtual IP                                                          │
│     │                                                                        │
│     │ 2. Service selector chooses ready pods through EndpointSlices           │
│     ▼                                                                        │
│  EndpointSlice addresses                                                     │
│     │                                                                        │
│     │ 3. targetPort maps service port to container listening port             │
│     ▼                                                                        │
│  Backend Pod container                                                       │
│                                                                              │
│  A failure at any step can look like "the service is down." Test each step    │
│  separately so you do not repair the wrong object.                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

A service with no endpoints is usually not a networking problem. It is usually a label or readiness problem. Compare the service selector against pod labels exactly, including key names, values, and namespace.

```bash
kubectl get svc <service-name> -n <namespace> -o yaml
kubectl get pods -n <namespace> --show-labels
kubectl get endpoints <service-name> -n <namespace>
kubectl get endpointslices -n <namespace> -l kubernetes.io/service-name=<service-name> -o wide
```

If endpoints exist, test the port mapping. The service `port` is what clients use. [The service `targetPort` is what backend pods must actually listen on.](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/) A named `targetPort` must match a named container port, which makes YAML readability better but can fail if the name is wrong.

```bash
kubectl get svc <service-name> -n <namespace> -o jsonpath='{.spec.ports[*].port}{" -> "}{.spec.ports[*].targetPort}{"\n"}'
kubectl exec -n <namespace> <client-pod> -- wget -qO- http://<service-name>:<port>/healthz
```

### DNS Triage

DNS problems should be tested from inside the cluster. The first question is whether the client pod can resolve the name. The second is whether it can connect to the resolved service. The third is whether CoreDNS itself is healthy if multiple pods and namespaces have lookup failures.

```bash
kubectl exec -n <namespace> <client-pod> -- nslookup kubernetes.default.svc.cluster.local
kubectl exec -n <namespace> <client-pod> -- nslookup <service-name>.<namespace>.svc.cluster.local
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=100
```

Do not confuse DNS failure with HTTP failure. `nslookup` only proves name resolution. If DNS succeeds but HTTP fails, move to service endpoints, target ports, readiness, application listener configuration, and NetworkPolicy. If DNS fails for every service name from multiple pods, CoreDNS or cluster DNS configuration becomes more plausible.

### NetworkPolicy Triage

NetworkPolicy failures are policy and label problems first, packet problems second. [A policy selects pods, then defines allowed ingress or egress.](https://kubernetes.io/docs/concepts/services-networking/network-policies/) [If a pod is selected by a restrictive policy and no rule allows the traffic, traffic is denied](https://kubernetes.io/docs/concepts/services-networking/network-policies/) even when services, endpoints, and DNS are otherwise correct.

```bash
kubectl get networkpolicy -n <namespace>
kubectl describe networkpolicy <policy-name> -n <namespace>
kubectl get pods -n <namespace> --show-labels
kubectl exec -n <namespace> <client-pod> -- wget -qO- http://<service-name>:<port>/
```

When troubleshooting policy, compare four label sets: the policy's pod selector, the source pod labels, the source namespace labels, and the destination pod labels. Many failures come from a policy selecting more pods than intended or from a namespace selector that no longer matches after namespace labels changed.

### Storage Triage

Storage failures often appear as pods stuck in `Pending` or `ContainerCreating`, but the underlying evidence may live on PVCs, PVs, StorageClasses, or CSI driver pods. [A pod cannot start if its required volume cannot bind, attach, or mount.](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) The pod event usually points to the storage object that needs deeper inspection.

```bash
kubectl get pvc -n <namespace>
kubectl describe pvc <claim-name> -n <namespace>
kubectl get pv
kubectl get storageclass
kubectl describe pod <pod-name> -n <namespace>
kubectl -n kube-system get pods | grep -i csi
```

The key distinction is bind versus mount. [A PVC stuck `Pending` usually means it cannot bind to a PV or dynamic provisioning failed. A pod stuck with `FailedMount` may mean the PVC is bound but the node cannot attach or mount the volume. Those are different layers and require different evidence.](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)

| Storage Symptom | Likely Layer | Evidence to Inspect | Common Repair Direction |
|---|---|---|---|
| PVC stuck `Pending` | Provisioning or binding | `kubectl describe pvc` and StorageClass | Fix StorageClass, capacity, access mode, or provisioner |
| Pod event says `FailedMount` | Node mount or secret/config volume | `kubectl describe pod` and kubelet events | Fix volume reference, permissions, or CSI node plugin |
| Pod event says attach timeout | CSI attach or cloud volume path | PVC, PV, CSI controller logs | Check driver health and volume attachment constraints |
| StatefulSet pod waits for volume | Controller and PVC template | StatefulSet status and PVCs | Inspect per-pod claim and storage class behavior |
| ConfigMap volume missing | Workload reference | pod Events and namespace object list | Create correct ConfigMap in same namespace or fix name |

---

## Part 6: Exam & Production Patterns

### Patterns & Anti-Patterns

The CKA rewards correct fixes under time pressure, while production rewards correct fixes with evidence and low blast radius. The methods overlap. Both require you to avoid random changes, read the highest-value evidence first, and validate the outcome. The difference is how much documentation and collaboration surround the work.

The most reliable troubleshooting patterns all have the same shape: gather low-risk evidence, narrow the layer, make one deliberate change, and validate the original path. The matching anti-patterns usually feel faster in the moment because they skip one of those steps, but they create uncertainty that costs more time later. Use the table below as a practical guardrail when pressure makes random action tempting.

| Pattern | Use It When | Why It Scales | Anti-Pattern to Avoid |
|---|---|---|---|
| Read-only first pass | The symptom is unclear or noisy | It preserves Events, previous logs, restart history, and placement clues for later reasoning | Restarting pods before collecting evidence |
| Layered isolation | The same symptom could come from workload, node, service, storage, or control plane causes | It prevents you from debugging components that cannot yet be involved | Calling every unexplained failure "networking" |
| One confirmed fix at a time | You have more than one plausible repair | It keeps cause and effect visible, which matters for exams, handoffs, and post-incident learning | Patching images, probes, selectors, and resources together |
| Path-based validation | The requested outcome is reachability, rollout health, or dependency access | It proves the fix from the caller's point of view rather than from one object status | Stopping when a pod turns `Running` |

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                      THREE-PASS TROUBLESHOOTING STRATEGY                     │
│                                                                              │
│  PASS 1: Fast evidence and obvious fixes, usually one to three minutes        │
│    - Wrong namespace, wrong context, typo in image, missing object name       │
│    - Selector mismatch, obvious missing ConfigMap or Secret, bad targetPort   │
│                                                                              │
│  PASS 2: Standard layered debugging, usually four to seven minutes            │
│    - Pod lifecycle, rollout status, readiness, endpoints, DNS, simple policy  │
│    - Resource requests, taints, affinity, PVC binding, probe failures         │
│                                                                              │
│  PASS 3: Deeper cluster and node investigation, only when evidence points     │
│    - Node NotReady, kubelet or runtime failure, control plane readiness       │
│    - CSI, CNI, scheduler, or controller-manager failures                      │
│                                                                              │
│  If the first three minutes produce no narrowing evidence, mark the task and  │
│  return after collecting points from faster questions.                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

This strategy is not an excuse to skip hard questions. It is a way to keep one difficult symptom from consuming the entire exam. Your goal in the first pass is to harvest easy evidence and easy fixes. Your goal in the second pass is to follow the lifecycle method. Your goal in the third pass is to decide whether the issue truly requires node or control plane debugging.

### 6.1 A Time-Boxed CKA Troubleshooting Loop

For a typical exam troubleshooting question, begin by confirming context and namespace. Many wrong fixes happen because the candidate inspects the default namespace while the broken workload lives elsewhere. Then run a focused overview, inspect the most relevant object, apply the smallest fix, and validate the exact requested outcome.

```bash
kubectl config current-context
kubectl get ns
kubectl get pods -n <namespace> -o wide
kubectl describe pod <pod-name> -n <namespace>
kubectl get deploy,svc,endpoints -n <namespace>
```

If the task statement gives a service or application path, validate through that path instead of stopping at pod status. If the task says "make the web service reachable," the service endpoint and an HTTP check matter. If the task says "fix the deployment rollout," `kubectl rollout status` matters.

### 6.2 Production Incident Discipline

In production, you usually have observability systems, change history, deployment tools, and teammates. The Kubernetes method still applies, but you add communication and evidence preservation. Before changing state, capture enough evidence that someone can understand why the fix was chosen. After changing state, write down what changed and what validation proved.

| Incident Habit | Why It Matters | Kubernetes Example |
|---|---|---|
| State the symptom precisely | Prevents the team from solving different problems | "checkout pods ready, service has empty endpoints" |
| Preserve key evidence | Avoids losing short-lived Events and previous logs | Save `describe` output and `logs --previous` when useful |
| Make one fix at a time | Keeps cause and effect visible | Fix image tag before changing probes or resources |
| Validate user path | Prevents false recovery | Test from frontend pod through service DNS |
| Record follow-up risk | Separates immediate repair from durable prevention | Add image tag policy or readiness test later |

The best troubleshooters are not people who never guess. They are people who make guesses explicit as hypotheses and then test them cheaply. "I think this is a selector mismatch because the service has no endpoints while pods are ready" is a testable statement. "Networking is broken" is too broad to guide action.

### 6.3 Decision Matrix for the Next Command

When you feel stuck, choose the next command based on the question you need answered. This matrix is intentionally practical: each row connects a question to evidence and a decision. It is useful during exam practice because it turns anxiety into a small diagnostic choice.

| Question You Need Answered | Command | If Yes | If No |
|---|---|---|---|
| Is the failure isolated to one namespace? | `kubectl get pods -A -o wide` | Inspect namespace workloads | Inspect nodes or shared services |
| Did the pod schedule? | `kubectl describe pod <pod> -n <ns>` | Inspect kubelet, image, volume, container state | Inspect scheduler events and node constraints |
| Did the container start and exit? | `kubectl describe pod` and `kubectl logs --previous` | Inspect app command, config, probes, resources | Inspect image, mount, and config construction |
| Is the pod ready for service traffic? | `kubectl get pod <pod> -o jsonpath=...` | Inspect service endpoints and ports | Inspect readiness probe and app listener |
| Does the service select ready pods? | `kubectl get endpointslices` | Test target port and app response | Compare selector, labels, and readiness |
| Is one node special? | `kubectl get pods -A -o wide` | Inspect node conditions and kubelet | Inspect workload or shared cluster layer |
| Are recent Events pointing to a cause? | `kubectl get events --sort-by='.lastTimestamp'` | Follow the involved object | Use YAML, logs, metrics, or controller status |
| Is the API itself healthy enough? | `kubectl get --raw='/readyz?verbose'` | Continue object-level debugging | Inspect control plane component health |

---

## Decision Framework

Practice drills build speed, but speed should come after method. Run these drills in a disposable cluster until you can match each command to the evidence it provides. Do not memorize them as isolated commands; say out loud what question each command answers. The decision framework here is simple: choose the drill that matches the layer your evidence has isolated, then stop as soon as the next useful question changes.

### Drill 1: Cluster Overview in Under One Minute

This drill answers whether the problem is isolated or broad. It is useful at the beginning of unknown incidents and CKA tasks where the namespace is not obvious. Look for non-running pods, node placement patterns, and recent warnings.

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get events -A --field-selector type=Warning --sort-by='.lastTimestamp' | tail -20
```

A good result is not just "I ran three commands." A good result is a short statement such as "Only `payments` has failing pods, and both failing pods are on different nodes, so I will inspect the deployment and pod template next." That statement shows that the overview narrowed your search.

### Drill 2: Pod Lifecycle Triage

This drill answers where a pod is stuck in its lifecycle. Use it for `Pending`, `ContainerCreating`, `CrashLoopBackOff`, readiness failures, and unexpected restarts. The sequence moves from summary to Kubernetes events to container evidence.

```bash
kubectl get pod <pod-name> -n <namespace> -o wide
kubectl describe pod <pod-name> -n <namespace>
kubectl get pod <pod-name> -n <namespace> -o yaml
```

After running the drill, classify the first failing stage. If the pod never scheduled, do not inspect logs. If the image never pulled, do not debug app config yet. If the process started and exited, then logs and exit codes become appropriate.

### Drill 3: Crash Investigation

This drill answers why a container restarted. It combines previous logs with termination status and avoids the common mistake of reading only the current container logs. Use it whenever restart count is nonzero.

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.exitCode}{"\n"}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].restartCount}{"\n"}'
```

Your conclusion should connect evidence to cause. "The pod is CrashLooping because the previous container log says it cannot read `/etc/app/config.yaml`, and the pod Events show the ConfigMap volume mounted successfully, so I will inspect the file path and application args" is better than "the app crashed."

### Drill 4: Service Endpoint Check

This drill answers whether service routing has usable backend pods. It is useful when the service object exists but traffic fails. Compare selectors and labels before assuming DNS or CNI is broken.

```bash
kubectl get svc <service-name> -n <namespace> -o yaml
kubectl get endpoints <service-name> -n <namespace>
kubectl get endpointslices -n <namespace> -l kubernetes.io/service-name=<service-name> -o wide
kubectl get pods -n <namespace> --show-labels
```

If endpoints are empty, explain whether the selector is wrong or pods are not ready. If endpoints exist, explain whether the service port maps to the application listener. This distinction prevents broad "networking" fixes that do not touch the real cause.

### Drill 5: DNS and In-Cluster Connectivity

This drill answers whether the client can resolve and reach the destination from inside the cluster. Use a source pod in the same namespace and policy context when possible. Avoid testing only from your laptop because that bypasses cluster-internal routing and policy.

```bash
kubectl exec -n <namespace> <client-pod> -- nslookup <service-name>.<namespace>.svc.cluster.local
kubectl exec -n <namespace> <client-pod> -- wget -qO- http://<service-name>:<port>/healthz
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
```

Interpret the result in layers. DNS failure points toward CoreDNS, search path, or network to DNS. DNS success with HTTP failure points toward service endpoints, target port, NetworkPolicy, or application listener. HTTP success from one pod but not another points toward source-specific policy or namespace differences.

### Drill 6: Node Health Check

This drill answers whether a specific node is the first broken layer. Use it when many failures cluster on one node or when the node is `NotReady`. Kubernetes evidence comes first, then node service evidence if you have node access.

```bash
kubectl describe node <node-name>
kubectl get pods -A -o wide --field-selector spec.nodeName=<node-name>
ssh <node-name> "systemctl status kubelet --no-pager"
ssh <node-name> "journalctl -u kubelet --no-pager -n 100"
ssh <node-name> "systemctl status containerd --no-pager"
```

Look for pressure conditions, kubelet heartbeat problems, runtime failures, disk pressure, and CNI errors. If only one workload fails on an otherwise healthy node, return to workload evidence. If many unrelated workloads fail on the same node, the node deserves deeper attention.

### Drill 7: Storage Binding and Mounting

This drill answers whether a storage failure is happening at binding time or mount time. PVC status and pod Events together tell you whether the scheduler and kubelet are waiting for storage. This distinction matters because binding and mounting involve different components.

```bash
kubectl get pvc -n <namespace>
kubectl describe pvc <claim-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
kubectl get storageclass
```

If the PVC is `Pending`, inspect the StorageClass, requested access mode, capacity, and provisioner. If the PVC is `Bound` but the pod reports `FailedMount`, inspect node mount events, CSI node plugin health, and the exact volume reference in the pod.

### Drill 8: Rollout Failure Triage

This drill answers why a deployment is not converging. Deployment status tells you whether the rollout is progressing, ReplicaSets show which revision owns which pods, and pod inspection explains the actual failure. This is one of the most common exam and production patterns.

```bash
kubectl rollout status deployment/<deployment-name> -n <namespace> --timeout=60s
kubectl describe deployment <deployment-name> -n <namespace>
kubectl get rs,pods -n <namespace> -l <selector-key>=<selector-value> -o wide
kubectl describe pod <new-pod-name> -n <namespace>
```

A stalled rollout is rarely fixed by restarting the deployment blindly. If new pods fail readiness, fix readiness or app startup. If new pods cannot pull an image, fix the image reference or pull credentials. If the deployment selector does not match the template labels, fix the immutable or template fields carefully according to what Kubernetes permits.

---

## Did You Know?

- **Events are evidence with an expiration date**: Kubernetes Events are intended for recent operational signals, not long-term incident history, so production clusters should ship logs and events into durable observability systems.
- **`Running` is a phase, not a promise**: A pod can be `Running` while readiness is false, endpoints are empty, or the application is returning errors to real clients.
- **`describe` is a multi-layer command**: One pod description can show scheduler decisions, kubelet failures, container termination state, volume references, probe messages, and recent Events.
- **Service DNS can succeed while traffic still fails**: DNS resolves the service name to a virtual IP, but endpoint selection, readiness, target ports, policy, and application listeners still decide whether requests work.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Jumping straight to logs for every pod problem | Logs feel familiar, but they do not exist for unscheduled pods and often miss image, volume, and config construction failures | Run `kubectl describe pod` first, then use logs when the container actually started |
| Restarting or deleting pods before collecting evidence | The restart looks harmless, but it can erase previous logs, reset timing clues, and hide the original symptom | Capture status, Events, restart count, and previous logs before mutating state |
| Treating `Running` as healthy | Pod phase is visible and easy to trust, while readiness and endpoint publication are less obvious | Check readiness conditions, endpoints, and the real request path |
| Debugging DNS before checking service endpoints | A successful service lookup sounds like network proof, but DNS can resolve a service with no ready backends | Inspect selectors, labels, readiness, endpoints, and target ports first |
| Making several speculative fixes at once | Pressure rewards visible action, but multiple changes hide which repair worked and can create new failures | Change one confirmed cause, then validate the original symptom |
| Ignoring namespace and context | Commands may inspect healthy objects while the broken workload lives elsewhere | Confirm context, namespace, and object name before interpreting output |
| Assuming node access is always the next step | SSH debugging feels deeper, but it wastes time when evidence points to workload YAML or service selection | Move to node checks only after pod or node evidence supports that layer |
| Stopping validation at green pod status | A green pod is satisfying, but the workload path may still fail through services, policy, readiness, or dependencies | Validate with rollout status, endpoints, and an in-cluster request that matches the original failure |

---

## Quiz

### Q1: The Rollout That Looks Like an App Crash

Your team deploys a new `api` version, and the deployment stalls. The newest pods show `CrashLoopBackOff`, but a teammate says to immediately run `kubectl logs deployment/api -n prod`. You have two minutes to start correctly. What command do you run first, and what decision will its output help you make?

<details>
<summary>Answer</summary>

Start with `kubectl describe pod <new-api-pod> -n prod`, choosing one of the new failing pods. The description tells you whether Kubernetes successfully scheduled the pod, pulled the image, mounted volumes, built container config, and then started a process that crashed. If Events show an image, ConfigMap, Secret, mount, or probe failure, logs may not be the first useful evidence. If the container did start and terminate, then move to `kubectl logs <pod> -n prod --previous` to inspect the last failed process instance.

</details>

### Q2: The Empty Service

A frontend pod can resolve `checkout.prod.svc.cluster.local`, but HTTP requests to `http://checkout:8080/healthz` time out. `kubectl get svc checkout -n prod` shows the service exists. What evidence do you collect next, and how would two different results change your next step?

<details>
<summary>Answer</summary>

Check service endpoints with `kubectl get endpoints checkout -n prod` or `kubectl get endpointslices -n prod -l kubernetes.io/service-name=checkout -o wide`, then compare the service selector with pod labels using `kubectl get svc checkout -n prod -o yaml` and `kubectl get pods -n prod --show-labels`. If endpoints are empty, focus on selector mismatch or pod readiness because DNS has already succeeded. If endpoints exist, focus on service port to targetPort mapping, NetworkPolicy, and whether the application is actually listening on the target port.

</details>

### Q3: The Pod That Never Had Logs

A pod named `report-worker` is `Pending` for several minutes. A junior engineer says the application logs will explain it, but `kubectl logs report-worker -n analytics` returns an error. Explain why logs are the wrong first evidence and identify the next command.

<details>
<summary>Answer</summary>

Logs are wrong because a `Pending` pod may not have a running container yet. If the scheduler has not assigned the pod or the kubelet has not started the container, there is no application process to produce logs. Run `kubectl describe pod report-worker -n analytics` and read the Events section for `FailedScheduling`, quota, taints, node affinity, PVC binding, or other lifecycle evidence. If the pod has been scheduled but is waiting for setup, the same description will point toward image or volume problems.

</details>

### Q4: The Node-Specific Failure

Three unrelated workloads fail after landing on `worker-2`, while the same workloads run correctly on other nodes. The failing pods show `ContainerCreating` with repeated runtime errors. How do you isolate whether this is a workload problem or a node problem?

<details>
<summary>Answer</summary>

First confirm the placement pattern with `kubectl get pods -A -o wide --field-selector spec.nodeName=worker-2` and compare it with healthy pods on other nodes. Then inspect the node with `kubectl describe node worker-2`, looking for readiness, pressure, runtime, and kubelet-related Events. Because unrelated workloads fail only on one node and the state is `ContainerCreating`, node-level evidence is justified. If you have node access, check `systemctl status kubelet`, `journalctl -u kubelet`, and `systemctl status containerd` on `worker-2`.

</details>

### Q5: The Successful DNS Lookup That Still Fails

A developer proves DNS works by running `nslookup payments` from a client pod. The application still cannot connect to `payments:9000`. Design the next two checks and explain what each one proves.

<details>
<summary>Answer</summary>

First check endpoints with `kubectl get endpoints payments -n <namespace>` or EndpointSlices with the service-name label. This proves whether the service has ready backend pod addresses. Second check the service port and targetPort with `kubectl get svc payments -n <namespace> -o yaml`, then compare it with the container's listening port or named port in the pod spec. DNS success only proves name resolution to the service virtual IP; endpoints and targetPort prove whether traffic has a backend and whether it is sent to the right container port.

</details>

### Q6: The OOMKilled Data Processor

A data-processing pod restarts repeatedly after a new release. `kubectl describe pod` shows the last state reason is `OOMKilled` and exit code `137`. A teammate proposes doubling the memory limit immediately. How do you evaluate whether that is the right repair?

<details>
<summary>Answer</summary>

First confirm the termination evidence in `kubectl describe pod`, then inspect the container's requests and limits with `kubectl get pod <pod> -o yaml` and recent usage if metrics are available through `kubectl top pod <pod> -n <namespace> --containers`. Doubling the limit may be appropriate if legitimate workload demand increased and the node has capacity, but it may hide a memory leak or poor request sizing. Also inspect whether the pod has an unrealistically low limit, whether multiple restarts began after a specific image version, and whether node memory pressure contributed. The repair should address the diagnosed cause, not just remove the visible limit.

</details>

### Q7: The Multi-Container Trap

A pod has an `app` container and a `log-agent` sidecar. The service returns 500 responses, but `kubectl logs web-abc -n prod` shows only healthy sidecar messages. What do you do next, and how do you avoid checking the wrong container again?

<details>
<summary>Answer</summary>

List container names with `kubectl get pod web-abc -n prod -o jsonpath='{.spec.containers[*].name}{"\n"}'`, then read the application container logs with `kubectl logs web-abc -n prod -c app`. If the container has restarted, use `kubectl logs web-abc -n prod -c app --previous`. Multi-container pods require explicit container selection because default log behavior can return a different container than the one serving traffic. The lasting habit is to identify containers before interpreting logs as evidence for the whole pod.

</details>

### Q8: The Fix That Was Not Validated

You fix an image typo in a deployment, and the new pods become `Running`. The task says "make the web application reachable through the `web` service." You are tempted to move on. What validation do you perform before considering the task complete?

<details>
<summary>Answer</summary>

Validate the requested service path, not just pod phase. Run `kubectl rollout status deployment/<name> -n <namespace>` to confirm the rollout converged, then check `kubectl get endpointslices -n <namespace> -l kubernetes.io/service-name=web -o wide` to confirm the service has ready backends. Finally, make an in-cluster request from a suitable client pod, such as `kubectl exec -n <namespace> <client-pod> -- wget -qO- http://web:<port>/healthz`. The original requirement was reachability through the service, so `Running` pods alone are insufficient validation.

</details>

---

## Hands-On Exercise: Systematic Troubleshooting Practice

### Scenario

You will create broken resources, diagnose them with the five-step method, repair only confirmed causes, and validate through the workload path. The exercise intentionally combines image, ConfigMap, readiness, service selector, and resource failures because real incidents rarely arrive as single neat errors.

### Setup

Use one Bash session and an independently provisioned disposable Kubernetes 1.35 fixture. Before running setup, set `LAB_KUBECONFIG` to the absolute path of its dedicated kubeconfig, `LAB_CONTEXT` to its context, and `LAB_CLUSTER_UID` to the `kube-system` namespace UID recorded by trusted fixture provisioning. Do not fetch the current cluster's UID and treat it as the expected identity. A matching UID checks identity, not disposability; keep the dedicated kubeconfig unchanged during the exercise.

The helpers use [explicit kubectl targeting](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl/). They guard the supplied fences, including piped manifests and nested lookups, not arbitrary manifests or commands. Keep the printed private receipt for reconciliation if the session is lost. Setup refuses to run again while candidate state exists, including after a failed or interrupted creation; a later lookup cannot replace a successful creation receipt.

```bash
_lab_base() {
  command kubectl --kubeconfig="$_LAB_CONFIG" --context="$_LAB_CONTEXT" \
    --namespace="${_LAB_NS:-default}" --request-timeout=30s "$@"
}
_lab_identity() {
  local actual
  actual=$(_lab_base get namespace kube-system -o jsonpath='{.metadata.uid}' </dev/null) || return
  [[ -n "$_LAB_CLUSTER_UID" && "$actual" == "$_LAB_CLUSTER_UID" ]] || {
    echo 'Fixture identity mismatch; stop.' >&2; return 1;
  }
}
_lab_receipt() {
  (umask 077; declare -p _LAB_CONFIG _LAB_CONTEXT _LAB_CLUSTER_UID _LAB_NS _LAB_UID _LAB_DELETE_SENT) >> "$_LAB_RECEIPT"
}
lab_setup() {
  [[ -z ${_LAB_NS+x} && -z ${_LAB_RECEIPT+x} ]] || {
    echo 'Existing candidate/receipt: reconcile it before another setup.' >&2; return 1;
  }
  [[ -n ${LAB_KUBECONFIG:-} && -n ${LAB_CONTEXT:-} && -n ${LAB_CLUSTER_UID:-} ]] || {
    echo 'Supply all three independently verified fixture inputs.' >&2; return 1;
  }
  _LAB_CONFIG=$LAB_KUBECONFIG; _LAB_CONTEXT=$LAB_CONTEXT; _LAB_CLUSTER_UID=$LAB_CLUSTER_UID
  _lab_identity || return
  _LAB_NS="troubleshoot-$(date +%s)-$RANDOM-$RANDOM"; _LAB_UID=; _LAB_DELETE_SENT=false
  _LAB_RECEIPT="$PWD/$_LAB_NS.receipt"
  (umask 077; set -o noclobber; : > "$_LAB_RECEIPT") || return
  _lab_receipt || return
  printf 'Retain receipt: %s\n' "$_LAB_RECEIPT"
  if ! _LAB_UID=$(_lab_base create namespace "$_LAB_NS" -o jsonpath='{.metadata.uid}'); then
    _LAB_UID=; echo 'Creation uncertain: retain candidate; ask fixture owner to reconcile.' >&2; return 1
  fi
  [[ $_LAB_UID =~ ^[0-9a-fA-F-]{36}$ ]] || {
    _LAB_UID=; echo 'Missing creation UID: preserve candidate; do not adopt or delete it.' >&2; return 1;
  }
  _lab_receipt || return
  _LAB_RECEIPT_OK=true
}
lab() {
  local arg actual
  [[ ${1:-} != delete ]] || { echo 'Use lab_cleanup for teardown.' >&2; return 1; }
  for arg in "$@"; do
    [[ $arg == -- ]] && break
    case "$arg" in
      -n*|-s*|-A*|--namespace*|--context*|--kubeconfig*|--cluster*|--user*|--server*|--all-namespaces*|--raw*|--as*|--token*|--client-*|--certificate-authority*|--insecure-skip-tls-verify*|--tls-server-name*|--request-timeout*)
        echo 'Target override refused.' >&2; return 1;;
    esac
  done
  [[ ${_LAB_RECEIPT_OK:-} == true && -s ${_LAB_RECEIPT:-} && -n ${_LAB_NS:-} && ${_LAB_UID:-} =~ ^[0-9a-fA-F-]{36}$ ]] || {
    echo 'No valid creation receipt; stop.' >&2; return 1;
  }
  _lab_identity || return
  actual=$(_lab_base get namespace "$_LAB_NS" -o jsonpath='{.metadata.uid}' </dev/null) || return
  [[ "$actual" == "$_LAB_UID" ]] || { echo 'Namespace identity mismatch; stop.' >&2; return 1; }
  _lab_base "$@"
}
lab_setup
```

Continue only after setup succeeds. The fault manifest below contains intentional mistakes to discover using evidence; its namespace comes from `lab`.

```bash
cat <<'EOF' | lab apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: broken-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: broken-app
  template:
    metadata:
      labels:
        app: broken-app
        tier: backend
    spec:
      containers:
      - name: app
        image: nginx:latestt
        ports:
        - name: http
          containerPort: 80
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 3
          periodSeconds: 5
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "500m"
        volumeMounts:
        - name: config
          mountPath: /etc/nginx/conf.d
      volumes:
      - name: config
        configMap:
          name: nginx-config
---
apiVersion: v1
kind: Service
metadata:
  name: broken-app
spec:
  selector:
    app: broken-api
  ports:
  - name: http
    port: 8080
    targetPort: http
EOF
```

### Task 1: Observe the Current State

Start broad and do not fix anything yet. Capture which objects exist, which pods are failing, and which Events appear most recent. Write one sentence describing the first visible symptom before moving deeper.

```bash
lab get deploy,rs,pods,svc,endpointslices -o wide
lab get events --sort-by='.lastTimestamp'
```

Success criteria for this task are evidence-based. You should be able to say whether the deployment created pods, whether the pods reached `Running`, and whether the service has endpoints. If you cannot state those three things, you have not observed enough.

- [ ] Confirmed whether pods were created by the deployment.
- [ ] Confirmed whether the pods reached `Running` and `Ready`.
- [ ] Confirmed whether the service has endpoints.
- [ ] Identified the most recent warning Events without changing any object.

### Task 2: Isolate the First Failing Layer

Inspect one broken pod with `describe`. Do not jump to logs until you know whether the container started. Use the Events section to decide whether the first failing layer is scheduler, image pull, volume mount, container process, readiness, or service selection.

```bash
POD_NAME="$(lab get pods -l app=broken-app -o jsonpath='{.items[0].metadata.name}')"
lab describe pod "$POD_NAME"
```

You should discover at least two pod-startup blockers over the course of the repair. The exact order depends on what Kubernetes reports first, but the image typo and missing ConfigMap are both real issues. Fix one confirmed issue at a time and re-observe after each fix.

- [ ] Identified the image typo from Events or container state.
- [ ] Identified the missing `nginx-config` ConfigMap from Events after or alongside the image problem.
- [ ] Avoided using logs before the container had actually started.
- [ ] Wrote a short hypothesis for each blocker before applying its repair.

### Task 3: Repair the Confirmed Startup Blockers

Apply the smallest repairs for the image typo and missing ConfigMap. Use commands that directly address the confirmed causes. Then watch the rollout long enough to see the next layer of failure, because fixing startup blockers may reveal readiness or service problems.

```bash
lab set image deployment/broken-app app=nginx:1.27
lab create configmap nginx-config --from-literal=default.conf='server { listen 80; location / { return 200 "ok\n"; } location /ready { return 200 "ready\n"; } }'
lab rollout status deployment/broken-app --timeout=90s
lab get pods -l app=broken-app
```

If the rollout still does not complete, inspect the newest pod again. Do not assume the first repair fixed everything. Kubernetes troubleshooting often reveals one blocker at a time because later lifecycle stages cannot fail until earlier stages succeed.

- [ ] Fixed the image reference to a valid nginx image tag.
- [ ] Created the missing ConfigMap in the same namespace as the pod.
- [ ] Re-ran `describe` or rollout status after each repair.
- [ ] Confirmed the deployment pods are `Running` and ready before moving to service validation.

### Task 4: Validate the Service Path

Now test the requirement a user would care about: traffic through the service. The service object exists, but the selector is intentionally wrong. Use endpoints and labels to prove the cause before patching it.

```bash
lab get svc broken-app -o yaml
lab get endpointslices -l kubernetes.io/service-name=broken-app -o wide
lab get pods --show-labels
```

Patch the service selector only after you can explain the mismatch. Then create a temporary client pod and test the service through its cluster DNS name and port.

```bash
lab patch svc broken-app --type='merge' -p '{"spec":{"selector":{"app":"broken-app"}}}'
lab get endpointslices -l kubernetes.io/service-name=broken-app -o wide
lab run client --image=busybox:1.36 --restart=Never -- sleep 3600
lab wait --for=condition=Ready pod/client --timeout=90s
lab exec client -- wget -qO- http://broken-app:8080/
```

The validation should return the response from nginx through the service. If it fails, inspect endpoints, targetPort, pod readiness, and the temporary client pod status before changing anything else. Remember that service reachability is a path, not a single object.

- [ ] Proved the original service selector did not match the backend pod labels.
- [ ] Patched the service selector to `app: broken-app`.
- [ ] Confirmed the service has endpoints after the patch.
- [ ] Tested traffic through `http://broken-app:8080/` from inside the namespace.

### Task 5: Diagnose a CrashLoopBackOff Pod

Create a separate crashing pod and apply the worked-example sequence without looking back at the solution. This pod starts, prints output, and exits with a nonzero code. Your goal is to capture previous logs and termination details before making a repair.

```bash
cat <<'EOF' | lab apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-pod
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - echo "booting"; sleep 2; echo "configured failure"; exit 1
EOF
```

Use the method in order. Observe status, inspect `describe`, read previous logs, and confirm exit code. Then decide what change would make the pod stop crashing.

```bash
lab get pod crash-pod
lab describe pod crash-pod
lab logs crash-pod --previous
lab get pod crash-pod -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

You do not need to repair this standalone pod unless you want extra practice. The important outcome is explaining why `--previous` matters and why the failure is application process behavior rather than scheduling, image pull, or volume setup.

- [ ] Confirmed the pod reached `CrashLoopBackOff`.
- [ ] Used `kubectl logs --previous` to inspect the terminated container instance.
- [ ] Retrieved the last exit code with JSONPath.
- [ ] Explained why the failure is inside the container process after startup.

### Task 6: Diagnose a Pending Pod

Create a pod that requests unrealistic resources. It should remain `Pending` because the scheduler cannot find a suitable node. Your job is to prove that no application logs can exist yet and that the scheduler event is the relevant evidence.

```bash
cat <<'EOF' | lab apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pending-pod
spec:
  containers:
  - name: app
    image: nginx:1.27
    resources:
      requests:
        memory: "100Gi"
        cpu: "100"
EOF
```

Inspect scheduler evidence and node capacity. Do not attempt to exec or read logs from a pod that has not started. The failure is a scheduling decision, not an application error.

```bash
lab get pod pending-pod
lab describe pod pending-pod
lab get nodes
lab describe node "$(lab get nodes -o jsonpath='{.items[0].metadata.name}')" | sed -n '/Allocatable/,/System Info/p'
```

A good answer identifies the scheduler as the component refusing placement because no node can satisfy the resource request. The repair would be to lower requests to realistic values, add suitable capacity, or change scheduling constraints depending on the real workload requirement.

- [ ] Confirmed the pod stayed `Pending`.
- [ ] Found the `FailedScheduling` event.
- [ ] Explained why logs are not useful for an unscheduled pod.
- [ ] Proposed a repair that addresses requests or capacity rather than restarting the pod.

### Cleanup

Explicitly remove only the namespace recorded by successful setup. [UID preconditions](https://github.com/kubernetes/apimachinery/blob/v0.35.0/pkg/apis/meta/v1/types.go) protect the [raw DELETE request](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl_delete/) from deleting a replacement namespace. A failed request or bounded wait preserves the receipt for retry; do not fall back to name-only deletion, remove finalizers, or delete `method-demo`.

```bash
lab_cleanup() {
  local actual
  [[ ${_LAB_RECEIPT_OK:-} == true && -s ${_LAB_RECEIPT:-} && -n ${_LAB_NS:-} && ${_LAB_UID:-} =~ ^[0-9a-fA-F-]{36}$ ]] || {
    echo 'No valid creation receipt; cleanup refused.' >&2; return 1;
  }
  _lab_identity || return
  actual=$(_lab_base get namespace "$_LAB_NS" --ignore-not-found -o jsonpath='{.metadata.uid}' </dev/null) || return
  if [[ -n "$actual" ]]; then
    [[ "$actual" == "$_LAB_UID" ]] || { echo 'Replacement namespace: stop.' >&2; return 1; }
    printf '{"apiVersion":"v1","kind":"DeleteOptions","preconditions":{"uid":"%s"}}' "$_LAB_UID" |
      _lab_base delete --raw "/api/v1/namespaces/$_LAB_NS" -f - || return
    _LAB_DELETE_SENT=true; _lab_receipt || return
    _lab_base wait --for=delete "namespace/$_LAB_NS" --timeout=120s || return
  elif [[ $_LAB_DELETE_SENT != true ]]; then
    echo 'Namespace missing without confirmed deletion; reconcile receipt.' >&2; return 1
  fi
  actual=$(_lab_base get namespace "$_LAB_NS" --ignore-not-found -o jsonpath='{.metadata.uid}' </dev/null) || return
  [[ -z "$actual" ]] || { echo 'Namespace still present; retain receipt.' >&2; return 1; }
  printf 'Confirmed namespace absent: %s. Retain receipt: %s\n' "$_LAB_NS" "$_LAB_RECEIPT"
}
lab_cleanup
```

There is no automatic EXIT cleanup: interrupting diagnosis must not silently delete the exercise. If creation loses its response, ownership is uncertain even if the candidate later exists. If the Bash session or receipt is lost, stop and ask the fixture owner to reconcile the candidate and provisioning records; do not reconstruct ownership by looking up its current UID. Retain failed-cleanup receipts and retry deliberately in the same session. The receipt contains identifiers and a kubeconfig path, not credential contents; keep it private and do not blindly source an untrusted receipt.

### Exercise Reflection

After cleanup, write a brief troubleshooting note for yourself. It should include the initial symptom, the first failing layer, the evidence command that proved it, the repair, and the validation command. This reflection is not busywork; it builds the same concise reasoning you will need during the CKA and during real incident handoffs.

- [ ] Recorded the first symptom without exaggerating it.
- [ ] Named the first failing layer for each broken object.
- [ ] Matched each fix to evidence rather than to a guess.
- [ ] Designed a short exam-time troubleshooting plan that preserves evidence, protects time, and proves the fix before moving to the next task.
- [ ] Validated the service path, not only pod status.
- [ ] Cleaned up all exercise resources.

---

## Learner check

> The hands-on exercise defines `lab` to keep its supplied commands on the selected fixture and owned namespace. Run those blocks in the same Bash session after successful setup. Other examples use full `kubectl` commands; the exercise helper is not an exam prerequisite or a general-purpose command sandbox.

You are evaluating an OOMKilled pod before raising its memory limit. Which command shows per-container CPU and memory usage from the metrics API, and why should you run it after reading `kubectl describe pod` rather than before?

---

## Sources

- [training.linuxfoundation.org: certified kubernetes administrator cka](https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/) — The Linux Foundation CKA page explicitly lists Troubleshooting at 30% and states the exam is a 2-hour performance-based test.
- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — Backs pod phases, container states, restart behavior, CrashLoopBackOff semantics, init-container sequencing, readiness-related lifecycle concepts, and general pod-state troubleshooting vocabulary.
- [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/) — Backs service-level checks such as verifying Service existence, selector matching, EndpointSlice population, and the classic 'service has no endpoints' troubleshooting flow.
- [Service](https://kubernetes.io/docs/concepts/services-networking/service/) — Backs Service types and behavior: ClusterIP, NodePort default range, LoadBalancer semantics, ExternalName, headless Services, selectors, DNS-based discovery, and readiness/endpoints relationships.
- [kubernetes.io: components](https://kubernetes.io/docs/concepts/overview/components/) — The Kubernetes components overview defines the API server, scheduler, and controller manager responsibilities directly.
- [Services, Load Balancing, and Networking](https://kubernetes.io/docs/concepts/services-networking/) — Backs the Kubernetes network model: pod IPs, pod-to-pod reachability expectations, Service abstractions, EndpointSlice involvement, and high-level networking architecture used in troubleshooting workflows.
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) — Backs use of describe, logs, events, exec, and YAML inspection to diagnose pod startup, scheduling, and runtime failures.
- [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/) — Backs exact kubectl logs behavior and flags such as container selection, follow mode, timestamps, tail, since, previous logs, and all-containers retrieval.
- [Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/) — Backs stdout/stderr logging expectations, node log-file locations, kubelet-managed log handling/rotation context, and sidecar-based logging patterns for file-writing applications.
- [kubeadm Implementation Details](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/) — Backs kubeadm-managed control-plane layout, especially static pod manifest paths under /etc/kubernetes/manifests, host networking defaults, and local etcd static-pod behavior.
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) — Backs cluster DNS behavior, service and pod DNS records, namespace-qualified lookups, headless-service DNS results, and the role of cluster DNS in service discovery troubleshooting.
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — Backs NetworkPolicy semantics, ingress/egress controls, additive policy behavior, pod/namespace/IPBlock selectors, and the requirement for a network plugin that enforces NetworkPolicy.
- [Kubernetes API Health Endpoints](https://kubernetes.io/docs/reference/using-api/health-checks/) — Useful for the module’s control-plane triage guidance, especially /readyz and verbose health checks.

## Next Module

Continue to [Module 5.2: Application Failures](../module-5.2-application-failures/) to learn how to troubleshoot pods, deployments, probes, configuration errors, and application-level failures in more depth.
