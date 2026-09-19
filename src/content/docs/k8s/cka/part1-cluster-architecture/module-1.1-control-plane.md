---
revision_pending: false
title: "Module 1.1: Control Plane Deep-Dive"
slug: k8s/cka/part1-cluster-architecture/module-1.1-control-plane
sidebar:
  order: 2
lab:
  id: cka-1.1-control-plane
  url: https://killercoda.com/kubedojo/scenario/cka-1.1-control-plane
  duration: "40 min"
  difficulty: intermediate
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Conceptual understanding required
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: Module 0.1 (working cluster)

---

## Learning Outcomes

After this module, you will be able to:

- **Diagnose** control plane failures by connecting symptoms to the API server, etcd, scheduler, controller manager, kubelet, kube-proxy, or container runtime.
- **Trace** a Kubernetes object request from `kubectl` through authentication, authorization, admission, storage, scheduling, reconciliation, and node execution.
- **Compare** control plane and worker node responsibilities so you can choose the right logs, health checks, and recovery path during an outage.
- **Recover** a failed static-pod control plane component by inspecting manifests, reading local node logs, and restoring the correct file.

---

## Why This Module Matters

Hypothetical scenario: you are on call for a practice cluster shortly before a CKA-style maintenance window, and developers report that new workloads no longer start. Existing applications still respond, `kubectl get nodes` sometimes works, a Deployment says it wants more replicas, and every new Pod sits in `Pending`. Those symptoms sound similar when you are under pressure, but they point to different parts of the system. If the API server is unhealthy, nearly every command becomes unreliable. If etcd is slow or unavailable, state changes stall. If the scheduler is missing, Pods can be created but never assigned. If the controller manager is stopped, higher-level objects can be accepted but never reconciled.

The control plane is the part of Kubernetes that decides what the cluster should be and records those decisions. Worker nodes make containers run, but they do not decide which Deployment should own a ReplicaSet, which node should receive a Pod, or whether a request is allowed. For the CKA exam and for real operational work, this distinction matters because it changes where you investigate first. You do not fix a missing scheduler by deleting a Pod from `kube-system`, and you do not debug an etcd certificate issue by staring at application container logs.

This module builds a mental map you can use when the cluster is partially broken. You will preserve the original component diagrams, command probes, troubleshooting drills, and static-pod recovery examples, but the prose now connects those assets into a single diagnostic story. By the end, you should be able to look at a symptom, predict which control loop is stuck, and choose the next command with intent rather than cycling through random checks.

Think of Kubernetes operations like a busy airport control room. The API server is the radio desk where every official request arrives, etcd is the durable operations ledger, the scheduler assigns aircraft to available gates, controllers compare planned schedules with reality, and kubelets coordinate the ground crew on each runway. The analogy is imperfect because Kubernetes is software, not aviation, but it helps you remember one crucial rule: the control plane coordinates and records decisions, while worker nodes perform the container work.

---

## Control Plane Map and Request Path

The first mistake learners make is picturing the control plane as one large process. Kubernetes is deliberately split into specialized components so each responsibility can fail, scale, and recover independently. The API server handles the front door and validation path, etcd holds persisted cluster state, the scheduler chooses nodes for unscheduled Pods, and the controller manager runs reconciliation loops that keep desired and observed state moving toward each other. Worker-side components then make those decisions real by starting containers, reporting status, and programming network rules.

The following architecture diagram is the starting map. It shows a kubeadm-style cluster where the major control plane components usually run as static Pods on a control plane node, while kubelet, kube-proxy, and the container runtime run on every node. In highly available production clusters, you may have several API servers, schedulers, and controller managers, with leader election deciding which scheduler and controller manager instance is active. The basic communication pattern remains the same: components talk through the API server, and only the API server persists Kubernetes API objects into etcd.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CONTROL PLANE                                │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────────┐ │
│  │ API Server  │  │   etcd      │  │    Controller Manager        │ │
│  │ (kube-api)  │◄─┤  (storage)  │  │  ┌────────────────────────┐  │ │
│  │             │  │             │  │  │ Deployment Controller  │  │ │
│  └──────┬──────┘  └─────────────┘  │  │ ReplicaSet Controller  │  │ │
│         │                          │  │ Node Controller        │  │ │
│         │ ┌─────────────────────┐  │  │ Job Controller         │  │ │
│         │ │     Scheduler       │  │  │ ... (40+ controllers)  │  │ │
│         │ │  (kube-scheduler)   │  │  └────────────────────────┘  │ │
│         │ └─────────────────────┘  └──────────────────────────────┘ │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          │ kubelet talks to API server
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           WORKER NODES                               │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Node 1                      Node 2                      Node 3  ││
│  │ ┌─────────┐ ┌──────────┐   ┌─────────┐ ┌──────────┐            ││
│  │ │ kubelet │ │kube-proxy│   │ kubelet │ │kube-proxy│   ...      ││
│  │ └─────────┘ └──────────┘   └─────────┘ └──────────┘            ││
│  │ ┌──────────────────────┐   ┌──────────────────────┐            ││
│  │ │ Container Runtime    │   │ Container Runtime    │            ││
│  │ │ (containerd)         │   │ (containerd)         │            ││
│  │ └──────────────────────┘   └──────────────────────┘            ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

The split between control plane and worker node components is not trivia. It tells you whether a failure prevents new decisions, existing containers, service networking, or all API access. A kubelet problem is local to the node that cannot launch or report Pods, while an API server problem can make the entire cluster look unavailable to clients. A stopped controller manager can leave existing Pods alone but prevent Deployments, Jobs, Nodes, and Endpoints from being reconciled. A scheduler problem usually shows up as Pods that exist in the API but never receive a `nodeName`.

| Component | Runs On | Purpose |
|-----------|---------|---------|
| kube-apiserver | Control plane | API gateway, all communication |
| etcd | Control plane | Cluster state storage |
| kube-scheduler | Control plane | Pod placement decisions |
| kube-controller-manager | Control plane | Reconciliation loops |
| kubelet | Every node | Container lifecycle |
| kube-proxy | Every node | Network rules |
| Container runtime | Every node | Actually runs containers |

When you run a command such as `kubectl create deployment nginx --image=nginx --replicas=3`, you are not talking to the scheduler or to a node directly. `kubectl` sends an HTTP request to the API server using credentials from your kubeconfig. The API server authenticates the user, authorizes the action, applies admission logic, validates the object, and stores the accepted desired state. Only after the object exists in the API can controllers and the scheduler react to it.

```
┌─────────────────────────────────────────────────────────────────┐
│                    All Roads Lead to API Server                  │
│                                                                  │
│   kubectl ────────┐                                              │
│   Scheduler ──────┼────► kube-apiserver ◄───► etcd              │
│   Controllers ────┤                                              │
│   kubelet ────────┤                                              │
│   Dashboard ──────┘                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

The API server being the only Kubernetes component that directly stores API objects in etcd is a protective design choice. It centralizes authentication, authorization, validation, admission, version conversion, and audit behavior instead of allowing every component to write raw state. That design also creates a clear troubleshooting rule: if `kubectl` cannot reach the API server, normal cluster introspection is unavailable, so you must move to the control plane node and use local tools such as `journalctl`, `crictl`, or static manifest inspection.

```
1. kubectl → API Server: "Create this pod please"
2. API Server: Authentication check ✓
3. API Server: Authorization check ✓
4. API Server: Admission controllers run
5. API Server: Validation check ✓
6. API Server → etcd: "Store this pod spec"
7. API Server → kubectl: "Pod created (pending)"
```

At this point the Pod may exist only as desired state. Nothing in the sequence above guarantees that a container is already running. The scheduler still has to bind the Pod to a node, the kubelet on that node still has to observe the assignment, and the container runtime still has to pull the image and create the container. This gap between "accepted by the API" and "running on a node" is where many control plane troubleshooting scenarios live.

**Pause and predict:** If the API server is unavailable but a worker node already has healthy containers running, decide which activities can continue locally and which activities must wait for the control plane path to recover. Make your prediction before reading the answer, because this boundary is the fastest way to separate an application process failure from a cluster coordination failure.

<details>
<summary>Check your prediction</summary>

Failure layer: treating Kubernetes as a remote process supervisor that continuously permits every running container. Next action: verify the local kubelet and runtime for already assigned containers, then use local control plane node checks because new API requests, scheduling, status updates, and controller reconciliation are blocked or delayed until the API path returns.

</details>

This boundary matters during partial outages because a calm application response does not prove the control plane can still accept, schedule, or reconcile new work.

Kubernetes 1.35+ still follows this separation of concerns. Component flags, health endpoints, and exact manifest details evolve across releases, but the model remains stable enough for diagnostic reasoning. On a CKA-style kubeadm cluster, the control plane components are commonly defined as files under `/etc/kubernetes/manifests/`. The kubelet watches that directory and keeps the corresponding static Pods alive, which is why file recovery is often more important than `kubectl delete pod` during control plane repair.

---

## API Server and etcd: Front Door and Source of Truth

The API server is both a gateway and a policy enforcement point. It receives requests from humans, controllers, schedulers, kubelets, dashboards, operators, and automation. It does not run application containers, but it decides whether an object is accepted into the cluster record. If you are investigating a symptom that affects all clients, such as widespread `kubectl` timeouts, admission failures, or TLS errors, the API server is usually the first control plane component to check.

```bash
# Is the API server responding?
kubectl cluster-info

# Check API server component status (legacy)
kubectl get componentstatuses  # Deprecated, may not work on all clusters

# Modern health endpoints (preferred)
kubectl get --raw='/readyz?verbose'
kubectl get --raw='/livez?verbose'

# Direct health endpoint
kubectl get --raw='/healthz'

# Detailed health
kubectl get --raw='/healthz?verbose'
```

The `livez` and `readyz` endpoints are more useful than the old component status command because they expose API server health checks through a supported endpoint model. Liveness tells you whether the process should be restarted, while readiness tells you whether it is prepared to serve normal traffic. A readiness failure can be caused by dependencies such as etcd connectivity, post-start hooks, or other internal checks. The important habit is to read the verbose output instead of treating health as a single green or red light.

API server logs may be available through `kubectl logs` when the API path is healthy enough to read the mirror Pod. During a serious failure, that assumption may be false, so you need the local path too. In kubeadm clusters, the static Pod manifest records the image, command flags, certificates, etcd endpoints, admission configuration, and bind settings. A small edit in that manifest can break the front door for the entire cluster, so inspect before changing and keep a copy when practicing.

```bash
# If running as a static pod (kubeadm setup)
kubectl logs -n kube-system kube-apiserver-<control-plane-node>

# If running as systemd service
journalctl -u kube-apiserver

# Static pod manifest location
cat /etc/kubernetes/manifests/kube-apiserver.yaml
```

etcd is the durable memory behind that front door. Kubernetes stores API objects under keys that reflect resource type, namespace, and object name, though you normally interact through the Kubernetes API rather than through raw etcd reads. Losing etcd data is not like losing a cache; it means losing the cluster record. That is why backups, disk monitoring, quorum awareness, and certificate health are operational topics, not optional extras for large teams only.

```
Key format: /registry/<resource-type>/<namespace>/<name>

Examples:
/registry/pods/default/nginx
/registry/services/kube-system/kube-dns
/registry/secrets/default/my-secret
/registry/deployments/production/web-app
```

In a single-control-plane training cluster, etcd may be a single static Pod. In production, etcd is commonly deployed as a small odd-sized cluster because its Raft consensus model requires a majority of members to agree. A three-member etcd cluster can tolerate one member failure; a five-member cluster can tolerate two. Adding members does not simply make every operation faster because consensus still requires communication, disk writes, and quorum. The design goal is durable agreement, not raw key-value speed at any cost.

```
┌─────────────────────────────────────────────────────────────────┐
│                    etcd Cluster (Raft Consensus)                 │
│                                                                  │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐              │
│   │  etcd-1  │◄────►│  etcd-2  │◄────►│  etcd-3  │              │
│   │ (Leader) │      │(Follower)│      │(Follower)│              │
│   └──────────┘      └──────────┘      └──────────┘              │
│                                                                  │
│   Writes go to leader, replicated to followers                   │
│   Reads can go to any node                                       │
│   Survives loss of 1 node (quorum = 2/3)                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Checking etcd health often requires local certificates because the etcd API is protected. The following command uses the kubeadm-style certificate paths that are common in exam labs. If it fails, distinguish between transport problems, certificate problems, member health problems, and command configuration mistakes. A wrong certificate path can look like an etcd outage if you read only the last line of the error.

```bash
# etcd member list (if you have etcdctl configured)
ETCDCTL_API=3 etcdctl member list \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Check etcd pod
kubectl get pods -n kube-system | grep etcd
kubectl logs -n kube-system etcd-<control-plane-node>
```

Hypothetical scenario: `kubectl get pods -A` works slowly, `kubectl apply` often times out, and API server logs show repeated storage latency warnings.

**Pause and predict:** Which component should you suspect first, and why is this not primarily a scheduler investigation? Commit to one owner before opening logs, because broad read and write latency across many resources tests the shared API storage path before it tests later placement decisions.

<details>
<summary>Check your prediction</summary>

Failure layer: blaming the scheduler for symptoms that occur before scheduling decisions can become the bottleneck. Next action: suspect the API server waiting on etcd, then check etcd member health, disk pressure, certificate expiration, and whether compaction or defragmentation has been neglected in a long-running cluster.

</details>

The operational lesson is that every control loop depends on the shared state store being responsive, so storage latency can make unrelated Kubernetes behaviors degrade together.

> **Before running**: What output do you expect from `kubectl get --raw='/readyz?verbose'` on a healthy kubeadm control plane?

Before running this, what output do you expect from `kubectl get --raw='/readyz?verbose'` on a healthy kubeadm control plane? Predict the shape of the output before you execute it: you should expect named checks with `ok` results, not just a single success string. If a check fails, copy the exact failing check name into your notes, because it usually points more precisely than the final HTTP status.

---

## Scheduler, Controllers, and Node Agents

After the API server accepts a Pod object, the scheduler watches for Pods that do not yet have `.spec.nodeName`. Its job is not to run the Pod; its job is to choose a feasible node and bind the Pod by updating the API. The scheduler first filters out nodes that cannot run the Pod, then scores the remaining candidates. That two-stage model matters because a Pod stuck in `Pending` may have no feasible node at all, or it may have feasible nodes but be waiting behind other scheduling work.

```
┌────────────────────────────────────────────────────────────────┐
│                      Scheduling Process                         │
│                                                                 │
│  1. New pod created (no nodeName) ─────────────────────┐       │
│                                                         │       │
│  2. Scheduler watches API server                        ▼       │
│     "Any pods need scheduling?"  ◄────────────────── Pod Queue │
│                                                                 │
│  3. Filtering: Which nodes CAN run this pod?                   │
│     - Enough CPU/memory?                                        │
│     - Taints/tolerations match?                                 │
│     - Node selectors match?                                     │
│     - Affinity rules satisfied?                                 │
│                                                                 │
│  4. Scoring: Which node is BEST?                               │
│     - Resource balance                                          │
│     - Spreading across zones                                    │
│     - Custom priorities                                         │
│                                                                 │
│  5. Binding: Assign pod to winning node                        │
│     Scheduler → API Server: "pod X goes to node Y"             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Filtering is about hard constraints. If a Pod requests more CPU than any node can offer, requires a label no node has, lacks a toleration for a taint, or depends on a storage claim that is not bound, the scheduler cannot create a good answer by being clever. Scoring is different: it chooses among nodes that passed the hard tests, often preferring better resource balance, topology spread, or other configured priorities. In practice, the Events section of `kubectl describe pod` is your best first clue because it records why no node was accepted.

```bash
# Pod stuck in Pending
kubectl describe pod <pod-name>

# Look for Events section:
# "0/3 nodes are available: 1 node(s) had taint {node-role.kubernetes.io/control-plane: },
#  2 node(s) didn't match Pod's node affinity/selector"
```

**Pause and predict:** A Pod requests 4 CPU cores and 8Gi of memory, but no single node currently has that much allocatable capacity available. Predict the Pod phase, the kind of message you expect in `kubectl describe pod`, and whether restarting the scheduler would repair the situation.

<details>
<summary>Check your prediction</summary>

Failure layer: interpreting every `Pending` Pod as evidence that the scheduler process is broken. Next action: leave the scheduler running, inspect Pod Events for insufficient CPU or memory, and change the request or available capacity because the scheduler is correctly refusing an impossible placement.

</details>

This prediction is useful because it keeps you focused on schedulability evidence instead of spending exam time restarting a component that is already behaving correctly.

```bash
# Scheduler pod
kubectl get pods -n kube-system | grep scheduler
kubectl logs -n kube-system kube-scheduler-<control-plane-node>

# Scheduler leader election (in HA setups)
kubectl get endpoints kube-scheduler -n kube-system -o yaml
```

Controllers solve a different problem. A controller is a reconciliation loop: it watches desired state and observed state, compares them, and takes action when they differ. The kube-controller-manager is a single binary that runs many built-in controllers, including Deployment, ReplicaSet, Node, Job, Endpoint, ServiceAccount, and Namespace controllers. The design is powerful because each controller can focus on one kind of convergence rather than placing all cluster behavior inside the API server.

```
┌────────────────────────────────────────────────────────────────┐
│                    Controller Loop Pattern                      │
│                                                                 │
│                    ┌─────────────────┐                         │
│                    │  Desired State  │                         │
│                    │  (in etcd)      │                         │
│                    └────────┬────────┘                         │
│                             │                                   │
│                    Compare  │                                   │
│                             ▼                                   │
│            Is current state = desired state?                    │
│                             │                                   │
│              ┌──────────────┴──────────────┐                   │
│              │ YES                    NO   │                   │
│              ▼                             ▼                   │
│         Do nothing                  Take action                │
│         (wait & watch)              (create/delete/update)     │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

| Controller | Watches | Does |
|------------|---------|------|
| **Deployment** | Deployments | Creates/updates ReplicaSets |
| **ReplicaSet** | ReplicaSets | Ensures correct pod count |
| **Node** | Nodes | Monitors node health, evicts pods from dead nodes |
| **Job** | Jobs | Creates pods, tracks completion |
| **Endpoint** | Services, Pods | Updates Service endpoints |
| **ServiceAccount** | Namespaces | Creates default ServiceAccount |
| **Namespace** | Namespaces | Cleans up resources when namespace deleted |

The ReplicaSet example is the cleanest way to understand reconciliation. You create a desired replica count, and the ReplicaSet controller observes that zero matching Pods exist. It then creates Pods through the API server. If a Pod later disappears, the controller does not mourn the specific object; it sees that the count is below desired state and creates another matching Pod. This is why labels and selectors are central to Kubernetes behavior.

```yaml
# You create this:
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx
```

```
Controller loop:
1. Watch: "ReplicaSet 'web' wants 3 pods"
2. Check: "How many pods with label 'app=web' exist?"
3. Compare: "0 exist, 3 desired"
4. Act: "Create 3 pods"
5. Repeat forever...

Later:
- Pod dies → Controller sees 2 pods → Creates 1 more
- You scale to 5 → Controller sees 3 pods → Creates 2 more
- You scale to 2 → Controller sees 5 pods → Deletes 3
```

What would happen if the controller manager crashes while the API server, scheduler, and etcd are still running? You can still create a bare Pod because the API server can accept it and the scheduler can assign it, but Deployments, ReplicaSets, Jobs, Endpoints, and node lifecycle reactions stop converging. Existing containers can keep serving because kubelet owns their local lifecycle, yet higher-level Kubernetes intent becomes frozen until controllers return and catch up.

```bash
# Controller manager pod
kubectl get pods -n kube-system | grep controller-manager
kubectl logs -n kube-system kube-controller-manager-<control-plane-node>

# Check for specific controller issues in logs
kubectl logs -n kube-system kube-controller-manager-<node> | grep -i "error\|failed"
```

Node agents complete the path from desired state to running containers. The kubelet registers the node, watches for Pods assigned to it, asks the container runtime to create containers, reports status, and runs health probes. kube-proxy watches Services and EndpointSlices, then programs node-level network rules so Service virtual IPs can reach backing Pods. The container runtime, usually containerd in kubeadm-style clusters, performs the actual image and container operations through the Container Runtime Interface.

```bash
# Check kubelet status
systemctl status kubelet

# kubelet logs
journalctl -u kubelet -f

# kubelet configuration
cat /var/lib/kubelet/config.yaml
```

```bash
# Check kube-proxy
kubectl get pods -n kube-system | grep kube-proxy
kubectl logs -n kube-system kube-proxy-<id>

# See iptables rules kube-proxy created
iptables -t nat -L KUBE-SERVICES
```

```bash
# Check containerd
systemctl status containerd
crictl ps  # List running containers
crictl images  # List images
```

Which approach would you choose here and why: if Pods are `Running` but Services cannot reach them, would you start with the scheduler or with node networking state? Start with Service, EndpointSlice, kube-proxy, and node firewall or dataplane checks because scheduling has already completed. This kind of component-to-symptom mapping is the difference between fast diagnosis and noisy command collection.

---

## End-to-End Deployment Walkthrough and Recovery

The following command looks simple, but it causes several independent control loops to cooperate. Read the timeline slowly and notice how each step depends on the previous state becoming visible through the API. The Deployment controller cannot create a ReplicaSet until the Deployment exists. The ReplicaSet controller cannot create Pods until the ReplicaSet exists. The scheduler cannot bind Pods until Pods exist without `nodeName`. Kubelet cannot start containers until it sees Pods assigned to its node.

```bash
kubectl create deployment nginx --image=nginx --replicas=3
```

```
┌─────────────────────────────────────────────────────────────────┐
│ Timeline of Events                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ 0ms    kubectl → API Server: "Create Deployment nginx"          │
│ 5ms    API Server → etcd: Store Deployment                      │
│                                                                  │
│ 10ms   Deployment Controller sees new Deployment                │
│ 15ms   Deployment Controller → API: "Create ReplicaSet"         │
│ 20ms   API Server → etcd: Store ReplicaSet                      │
│                                                                  │
│ 25ms   ReplicaSet Controller sees new ReplicaSet                │
│ 30ms   ReplicaSet Controller → API: "Create Pod 1, 2, 3"        │
│ 35ms   API Server → etcd: Store 3 Pods (Pending)                │
│                                                                  │
│ 40ms   Scheduler sees 3 unscheduled Pods                        │
│ 50ms   Scheduler → API: "Pod 1→node1, Pod 2→node2, Pod 3→node1" │
│ 55ms   API Server → etcd: Update Pods with nodeName             │
│                                                                  │
│ 60ms   kubelet on node1 sees 2 Pods assigned to it              │
│ 65ms   kubelet on node2 sees 1 Pod assigned to it               │
│ 70ms   kubelets → containerd: "Start nginx containers"          │
│                                                                  │
│ 500ms  Containers running                                        │
│ 505ms  kubelets → API: "Pods are Running"                       │
│ 510ms  API Server → etcd: Update Pod status                     │
│                                                                  │
│ Done!  kubectl get pods shows 3/3 Running                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

This timeline is also a troubleshooting checklist. If no Deployment appears, focus on the client request, API server, admission, authorization, and etcd write path. If the Deployment exists but no ReplicaSet appears, suspect the Deployment controller inside the controller manager. If ReplicaSets exist but no Pods appear, suspect the ReplicaSet controller or selector issues. If Pods exist but remain unscheduled, inspect scheduler status and Pod events. If Pods are assigned but containers do not start, move to kubelet, image pull, runtime, and node conditions.

Static Pods add one important recovery rule. In kubeadm clusters, the API server, scheduler, controller manager, and etcd are often specified as files in `/etc/kubernetes/manifests/`, and kubelet creates mirror Pods so you can see them through the API. Deleting a mirror Pod through `kubectl` does not repair a missing manifest because kubelet is the real manager. If a manifest file disappears, the durable fix is to restore the file with correct content and permissions, then let kubelet recreate the static Pod.

Hypothetical scenario: a learner accidentally moves `/etc/kubernetes/manifests/kube-scheduler.yaml` during a lab, then tries to restart scheduling by deleting the scheduler Pod from `kube-system`. The visible Pod may vanish, but the root cause remains because the kubelet no longer has a manifest to run. The right repair is to restore `kube-scheduler.yaml`, watch kubelet recreate the static Pod, then verify that Pending Pods receive node assignments. This is a common exam-shaped pattern because it tests component ownership rather than command memorization.

The same reasoning applies to local logs. When the API server is working, `kubectl logs -n kube-system ...` is convenient. When the API server is down, it is unavailable by definition, so local node tools become mandatory. You may need to inspect `/etc/kubernetes/manifests/kube-apiserver.yaml`, read `journalctl -u kubelet`, or use `crictl ps` and `crictl logs` to inspect static Pod containers. The control plane is not magical; it is a set of processes that kubelet and the runtime still manage locally.

---

## Reading Control Plane Symptoms Like a Chain

A reliable diagnosis usually begins by locating the first broken link in the object lifecycle. Kubernetes exposes many views of the same event, and beginners often collect all of them without deciding which transition they are testing. A Deployment that exists proves the client request, authentication, authorization, admission, and first etcd write succeeded. A missing ReplicaSet after that points to Deployment reconciliation. A ReplicaSet with no Pods points to ReplicaSet reconciliation. Pods with no assigned node point to scheduling or impossible constraints. Assigned Pods that fail to start point to kubelet, image pull, runtime, storage mount, or node pressure.

This chain-based approach is faster than memorizing component names because it follows evidence. Imagine a learner says, "My Deployment failed." That statement is too broad to debug. Ask which object exists and which object should have appeared next. If the Deployment object is absent, investigate the API request. If the Deployment exists and has status conditions, read those conditions before moving lower. If the ReplicaSet exists but has zero desired Pods, check selectors and Deployment rollout state. Each answer narrows the component set without guessing.

The same method works in reverse when existing workloads keep running during control plane trouble. If containers are still serving traffic, kubelet and the runtime have already done enough local work to keep them alive. If the API server is down, those containers do not instantly die because Kubernetes is not a remote process supervisor that must constantly stream permission to every container. However, status reporting, new scheduling, scaling, rollout, and many self-healing actions will be impaired. That distinction explains why partial outages can look calm for a few minutes before hidden control loops matter.

There is also a difference between "not happening yet" and "cannot happen." Controllers and schedulers watch the API and work asynchronously, so a small delay after creating an object can be normal. A persistent delay with clear Events is different. If Events say no nodes match an affinity rule, waiting longer does not create a matching node. If controller logs show failed leader election, waiting might resolve after lease changes, but you still need to understand why leadership is unstable. Your job is to separate normal eventual consistency from a blocked precondition.

Worked example: suppose you run `kubectl create deployment api --image=nginx --replicas=3`, and the command returns success. One minute later, `kubectl get deployment api` shows the Deployment, but `kubectl get rs` shows no ReplicaSet. The scheduler has not had a chance to matter because there are no Pods to schedule. The kubelet has not had a chance to matter because there are no assigned Pods. The component responsible for creating the next object is the Deployment controller inside the controller manager, so that is where you look next.

If the ReplicaSet exists and three Pods exist, but all three Pods are `Pending`, the diagnostic owner changes. The Deployment and ReplicaSet controllers did their jobs well enough to create Pods. Now inspect Pod Events and scheduler logs. The answer might be a failed scheduler, but it might also be a correct scheduler refusing an impossible request. A Pod that asks for a label no node has should stay Pending until the label changes, the Pod spec changes, or a matching node joins. Treat the scheduler as a decision engine, not as a magic placement force.

If the Pods have `nodeName` set and remain in `ContainerCreating`, the scheduler is done. Look at kubelet Events, image pull status, volume attachment, CNI setup, and runtime logs on the assigned node. A missing image pull secret, a broken container runtime socket, or a CNI configuration error can all appear after scheduling succeeds. The control plane still records status, but the next useful evidence is often node-local. This is where CKA candidates lose time if they keep reading scheduler logs after the Pod is already bound.

API server symptoms require a different entry point because the API server is your normal window into the cluster. If `kubectl get --raw='/readyz?verbose'` works, use it because it gives structured readiness checks. If it fails with connection refused or TLS errors, move to the control plane node and inspect kubelet plus the API server manifest. If it works but reports etcd-related readiness failures, you have evidence that the API process is alive but its storage dependency is not healthy enough for normal service. That distinction changes whether you inspect API flags, certs, network reachability, or etcd itself.

etcd symptoms are often broad because every persisted state transition depends on storage. Slow etcd does not always mean etcd is fully down; it may mean disk latency, database growth, compaction issues, member communication trouble, or certificate errors between the API server and the etcd endpoint. Readiness output, API server logs, and `etcdctl endpoint health` or member commands can triangulate the cause. In production, you would also check metrics, disk capacity, and recent maintenance. In an exam lab, you focus on certificate paths, endpoints, static Pod health, and obvious disk or process failures.

Leader election adds another layer in highly available clusters. The scheduler and controller manager may run multiple Pods, but only the leader actively performs work. A standby instance is not broken just because it is not making scheduling or reconciliation decisions. If no leader can be elected, the cluster may accept objects without progressing. This is why checking leader election endpoints or leases can be useful when component Pods are Running but behavior is still frozen. Running means the process exists; leadership means the process owns the active work.

Static Pod recovery also deserves careful sequencing. First identify whether the manifest exists and whether kubelet is reading it. Then inspect whether the container was created and why it exited. If the manifest is missing, restore it before spending time on API-level deletes. If the manifest exists but contains a bad flag, compare it against a known-good backup or another control plane node. If the container runs but fails readiness, read the component logs and dependency checks. Each step tests a different layer of the local static Pod stack.

When you practice, write down the proof each command gives you. `kubectl get deployment` proves the API can read a Deployment object, not that the controller is healthy. `kubectl get pods -n kube-system | grep scheduler` proves a scheduler mirror Pod is visible, not that every Pod is schedulable. `journalctl -u kubelet` proves what the local kubelet is doing, not what etcd has stored. These distinctions seem fussy at first, but they are what make an incident timeline accurate.

The final habit is to avoid changing multiple layers at once. If you edit a static manifest, restart kubelet, drain a node, and delete workloads in one burst, you cannot tell which action fixed or worsened the symptom. Make one scoped change, watch the expected next transition, then continue. Kubernetes is built from reconciliation loops, so good troubleshooting uses the same patience: observe desired state, observe current state, change one input, and verify the next loop response.

One useful way to practice this discipline is to narrate a failure in terms of verbs rather than nouns. Instead of saying "the scheduler is broken," say "the Pod has not been bound to a node." Instead of saying "the controller manager is broken," say "the Deployment has not produced a ReplicaSet" or "the ReplicaSet has not produced Pods." Verb-based descriptions keep you close to evidence, and they make peer handoffs clearer. Another engineer can test the same transition without inheriting your unproven conclusion.

The API object status fields are also part of the evidence chain, not decorative output. Conditions, timestamps, observed generations, ready counts, and Events tell you whether a controller has seen the current desired state. For example, a Deployment may have a newer `metadata.generation` than `status.observedGeneration`, which means the controller has not yet processed the latest spec. A Pod may have a scheduled condition, a ready condition, and container state details that each belong to a different owner. Read these fields as breadcrumbs through the control loops.

Be careful with label selectors during control plane diagnosis. A ReplicaSet controller counts Pods by selector, not by the story you have in your head. If a Pod template label does not match the selector, Kubernetes may reject the object, or a controller may ignore Pods you expected it to own. If a Service selector does not match ready Pods, the Service can exist while having no useful endpoints. These mistakes are not control plane process outages, but they look like broken automation until you verify the selector relationship.

Node conditions provide another boundary marker. If a node is `NotReady`, the scheduler may stop placing normal Pods there, and the node controller may eventually react to missed heartbeats. If a node is Ready but under memory, disk, or PID pressure, kubelet may reject or evict work even though the control plane accepted the desired state. In a small lab, those details may feel secondary, yet they explain why "the Pod exists" is not enough. The node still has to prove it can execute the assignment safely.

Timeouts deserve similar care. A client-side timeout from `kubectl` can mean local network trouble, API server overload, admission webhook latency, etcd latency, or a request that needs to stream more data than expected. The message text, the affected verbs, and the affected resources matter. If only Pod creation is slow, compare admission, quota, image policy, and scheduler paths. If every list and watch operation is slow across the cluster, look harder at the API server and etcd. The breadth of the timeout is evidence.

For CKA practice, convert every broad incident into two artifacts: a suspected owner and a falsifiable next check. "Suspected owner: controller manager. Next check: does a new Deployment create a ReplicaSet, and do controller manager logs show reconciliation or leader election errors?" That format forces you to choose a test that could prove you wrong. If the ReplicaSet appears immediately, the controller manager is not the current blocker. You then move to the next transition instead of defending the first guess, and your notes remain useful to someone reviewing the path later under exam pressure or team review.

---

## Patterns & Anti-Patterns

Good control plane troubleshooting starts with symptom classification. Ask whether the failure blocks API access, state persistence, scheduling, reconciliation, node execution, or service networking. That question narrows the search before you touch anything. It also prevents harmful fixes, such as restarting every component when a single Pod has an impossible node selector. Restarting may hide timing clues and can turn a partial outage into a broader one if several components are already close to unhealthy.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Start at the failed transition | A resource is stuck between accepted, scheduled, running, or ready | Each transition maps to a small set of components | Build runbooks around transitions, not around random commands |
| Prefer health endpoints and events before restarts | The API is reachable but behavior is degraded | Readiness checks and events preserve evidence | Store important outputs in incident notes before making changes |
| Treat static manifests as source for static Pods | A control plane Pod keeps disappearing or cannot restart | kubelet reconciles files in `/etc/kubernetes/manifests/` | Back up manifests and compare against a healthy control plane node |
| Separate desired state from execution state | A Deployment, ReplicaSet, Pod, or container disagrees | Kubernetes progresses through controllers, scheduler, kubelet, and runtime | Use object owner references and status fields to follow the chain |

Anti-patterns usually come from treating Kubernetes as one box. A team sees Pods in `Pending` and restarts kubelet on every node, even though the Events section says the Pods request too much memory. Another team deletes a static Pod mirror and expects it to stay deleted, even though kubelet immediately recreates it from the manifest. These actions are understandable because the surface area is large, but they waste time because they ignore ownership boundaries.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Restarting all control plane components first | Evidence disappears and the outage can widen | Read health, events, and logs before choosing one component |
| Using `kubectl` only during API server failure | The main diagnostic tool depends on the failed component | SSH to the control plane and use manifest, kubelet, and runtime logs |
| Blaming the scheduler for every Pending Pod | Resource, taint, affinity, and storage constraints are missed | Inspect `kubectl describe pod` Events before touching scheduler |
| Editing static manifests without a backup | A typo can keep a core component crash-looping | Copy the manifest, make one change, and watch kubelet logs |

The safest habit is to name the owner of the next state transition. API server owns request acceptance, etcd owns persisted state, controllers own reconciliation, scheduler owns Pod binding, kubelet owns node-local Pod execution, kube-proxy owns many Service dataplane rules, and the runtime owns containers. If you cannot name the owner, pause before changing the system. That small discipline prevents most beginner control plane mistakes.

---

## Decision Framework

Use this framework when a cluster symptom looks broad but the exact component is unclear. Start with what still works, because negative evidence is often more useful than a long command list. If no `kubectl` command succeeds, move below the API and inspect the control plane node locally. If API reads work but writes are slow or failing, inspect API server readiness and etcd health. If objects are accepted but not acted on, follow the desired-state chain through controllers, scheduler, and kubelet.

```
Symptom observed
      |
      v
Can kubectl reach the API server?
      |
      +-- No --> Check kube-apiserver static Pod, kubelet logs, certificates,
      |          bind address, and local runtime status on the control plane.
      |
      +-- Yes --> Are API reads or writes slow across many resources?
                  |
                  +-- Yes --> Check API server readyz/livez and etcd health.
                  |
                  +-- No --> Does the object exist but no child object appears?
                              |
                              +-- Yes --> Check kube-controller-manager logs.
                              |
                              +-- No --> Are Pods created but Pending?
                                          |
                                          +-- Yes --> Check scheduler and Pod Events.
                                          |
                                          +-- No --> Are Pods assigned but not Running?
                                                      |
                                                      +-- Yes --> Check kubelet and runtime.
                                                      |
                                                      +-- No --> Check Service, EndpointSlice,
                                                                  kube-proxy, and application readiness.
```

| Symptom | Most Likely Owner | First Useful Check | Why This Check Comes First |
|---------|-------------------|--------------------|----------------------------|
| `kubectl` cannot connect | API server or node-local static Pod stack | `journalctl -u kubelet` and API server manifest | `kubectl` depends on the component you are testing |
| All writes are slow or time out | API server to etcd path | `kubectl get --raw='/readyz?verbose'` and etcd member health | Every write must be persisted before other loops react |
| Deployment exists but no ReplicaSet appears | Controller manager | Controller manager logs and leader election status | Deployment reconciliation creates the next object |
| Pods exist but have no `nodeName` | Scheduler or scheduling constraints | `kubectl describe pod <pod-name>` Events | Events reveal resource, taint, affinity, and volume blockers |
| Pod assigned but containers absent | kubelet or runtime | `journalctl -u kubelet` and `crictl ps` | Node-local execution starts after scheduling |
| Pod Running but Service traffic fails | kube-proxy or Service endpoints | Service, EndpointSlice, kube-proxy logs, node rules | Scheduling is complete, so networking owns the next hop |

This decision framework is not a replacement for documentation or deeper debugging. It is a guardrail for the first ten minutes of an incident or exam task. In those minutes, the goal is to avoid confusing the component that records desired state with the component that executes it. Once you identify the stuck transition, detailed component documentation and logs become far easier to interpret.

---

## Did You Know?

1. **Static Pods are managed by kubelet, not by the API server.** In kubeadm clusters, core control plane components commonly live as manifests under `/etc/kubernetes/manifests/`, and the Pods shown in `kube-system` are mirror objects. This is why restoring a deleted manifest repairs the component while deleting the mirror Pod does not.

2. **The API server is designed to be stateless.** Durable Kubernetes state lives in etcd, so restarting an API server should not erase objects. That statelessness is what lets highly available clusters run multiple API server instances behind a load balancer.

3. **etcd uses Raft consensus and needs quorum.** A three-member etcd cluster tolerates one failed member, while a five-member cluster tolerates two. Even-sized clusters are usually avoided because they add cost without improving failure tolerance in the way many people expect.

4. **Schedulers and controller managers use leader election in highly available clusters.** Multiple instances can run, but only the active leader performs the main work at a given time. Standby instances are still valuable because they can take over when the leader fails.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Thinking kubelet runs in a Pod | Most other Kubernetes components are visible as Pods, so learners assume kubelet is too | Check kubelet with `systemctl status kubelet` and `journalctl -u kubelet` on the node |
| Ignoring etcd health when the API is slow | The symptom appears in `kubectl`, so the storage path is easy to overlook | Check API server readiness and etcd member health, disk space, certificates, and latency |
| Not checking component logs | The resource state shows the effect, not always the cause | Read the relevant `kube-system` logs when the API works, and local node logs when it does not |
| Confusing control plane with worker responsibilities | Kubernetes presents one API even though many components own different transitions | Map the stuck transition to API server, etcd, controller manager, scheduler, kubelet, kube-proxy, or runtime |
| Forgetting static Pods are file-backed | Mirror Pods look normal in `kubectl get pods` output | Restore or edit the manifest in `/etc/kubernetes/manifests/` and watch kubelet recreate the Pod |
| Restarting scheduler for impossible Pod constraints | Pending Pods look like scheduler failures even when the scheduler is correct | Inspect Pod Events for insufficient resources, taints, affinity, selectors, and unbound PVCs |
| Using deprecated component status as the only health signal | Old habits and older tutorials still mention `kubectl get componentstatuses` | Prefer `readyz`, `livez`, component logs, and direct etcd checks on Kubernetes 1.35+ clusters |

---

## Quiz

<details>
<summary>Question 1: Your monitoring alert says etcd latency is high, and developers report that `kubectl` commands are slow or timing out. Why does etcd latency affect `kubectl`, and which other cluster behaviors would degrade?</summary>

The API server is the only Kubernetes component that persists API objects into etcd, and every normal `kubectl` request goes through the API server. When etcd is slow, the API server can block on reads or writes, so clients experience timeouts even if the API server process is still alive. Scheduler binding decisions, controller status updates, kubelet status reports, and admission paths that require persisted state can all degrade. The key diagnostic clue is that many unrelated resource operations become slow together, which points to the shared API-to-etcd path rather than one workload controller.

</details>

<details>
<summary>Question 2: A developer reports that a new Deployment shows `0/3` replicas ready. You run `kubectl get pods` and see three Pods stuck in `Pending`, while the scheduler Pod is Running. What are the most likely causes, and how would you investigate?</summary>

A Running scheduler does not guarantee that any node is eligible for the Pods. Start with `kubectl describe pod <pod-name>` and read the Events section because it will usually mention insufficient CPU or memory, untolerated taints, node selector mismatches, affinity failures, or unbound PersistentVolumeClaims. Then compare those messages against node labels, taints, allocatable resources, and storage state. Restarting the scheduler would be premature unless Events or scheduler logs show the scheduler itself is unhealthy.

</details>

<details>
<summary>Question 3: During an incident, the kube-controller-manager has been down for 10 minutes. Existing Pods are still serving traffic, but a Deployment scaled from 3 to 5 replicas never creates the extra Pods. Explain the difference.</summary>

Existing containers keep running because kubelet and the container runtime manage local execution after Pods have already been assigned. Scaling a Deployment requires controller reconciliation: the Deployment controller updates ReplicaSets, and the ReplicaSet controller creates or deletes Pods to match desired replica count. With the controller manager down, the new desired state can sit in etcd without the controller that acts on it. Once the controller manager returns, it should observe the mismatch and create the missing Pods.

</details>

<details>
<summary>Question 4: A colleague accidentally deleted `/etc/kubernetes/manifests/kube-scheduler.yaml`. They try `kubectl delete pod kube-scheduler -n kube-system` to restart it, but scheduling stays broken. What went wrong, and what is the correct fix?</summary>

The scheduler in a kubeadm control plane is commonly a static Pod managed by kubelet from the manifest file. The Pod visible through `kubectl` is a mirror Pod, so deleting it does not recreate the missing source manifest. The correct fix is to restore `/etc/kubernetes/manifests/kube-scheduler.yaml` from backup or from a healthy control plane node, then watch kubelet recreate the static Pod. After the scheduler is Running, verify that Pending Pods receive node assignments.

</details>

<details>
<summary>Question 5: `kubectl create pod` succeeds, the Pod gets a `nodeName`, but the container never starts and kubelet reports image pull failures. Which component owns the next diagnostic step, and why?</summary>

The API server and scheduler have already done their parts because the Pod exists and has been assigned to a node. The next owner is the kubelet on the selected node, working with the container runtime to pull the image and create the container. You should inspect `kubectl describe pod` for image events, then move to `journalctl -u kubelet` and runtime commands such as `crictl ps` or `crictl images` on that node. The scheduler is not the first suspect because binding already happened.

</details>

<details>
<summary>Question 6: A Service has a ClusterIP, the backing Pods are Running and Ready, but traffic to the Service fails from one node only. Which part of the architecture should you investigate first?</summary>

Because the Pods are Running and Ready, the control plane has already accepted, scheduled, and reconciled the workload. A one-node Service failure points toward node-local dataplane behavior, especially kube-proxy rules, firewall rules, CNI state, or EndpointSlice propagation on that node. Start by checking the Service and EndpointSlice objects, then inspect kube-proxy logs and node rules such as the `KUBE-SERVICES` chain if that cluster uses iptables mode. Restarting the controller manager would not be the first move because the failure is localized to traffic handling.

</details>

<details>
<summary>Question 7: The API server is down, and `kubectl logs -n kube-system kube-apiserver-<node>` cannot connect. What should you do next, and why?</summary>

When the API server is down, `kubectl logs` depends on the failed path, so it is the wrong tool for the next step. SSH to the control plane node and inspect local state: `journalctl -u kubelet`, the static manifest at `/etc/kubernetes/manifests/kube-apiserver.yaml`, and runtime logs through `crictl` if needed. This works because kubelet and the runtime are local processes that can still expose evidence even when the Kubernetes API is unavailable. The goal is to find whether the static Pod is missing, crash-looping, misconfigured, or unable to reach etcd.

</details>

---

## Hands-On Exercise

This exercise places the control plane command drills in a safer diagnostic sequence. Run destructive steps only in a disposable practice cluster, such as the linked lab environment, because moving static manifests intentionally breaks control plane components. If you are on a shared cluster, perform only the read-only inspection steps and discuss the recovery tasks instead of executing them.

**Task**: Explore your cluster's control plane components and practice mapping symptoms to owners.

### Guided Exploration

1. **List all control plane pods**:

```bash
kubectl get pods -n kube-system
```

2. **Check component health**:

```bash
kubectl get componentstatuses
kubectl get --raw='/healthz?verbose'
```

3. **View API server configuration**:

```bash
# On control plane node
sudo cat /etc/kubernetes/manifests/kube-apiserver.yaml | grep -A5 "command:"
```

4. **Check scheduler logs for recent activity**:

```bash
kubectl logs -n kube-system -l component=kube-scheduler --tail=20
```

5. **Watch controller manager in action**:

```bash
# Terminal 1: Watch controller logs
kubectl logs -n kube-system -l component=kube-controller-manager -f

# Terminal 2: Create and delete a deployment
kubectl create deployment test --image=nginx --replicas=2

# Verify the deployment was created successfully before deleting
kubectl rollout status deployment test

kubectl delete deployment test
```

6. **Explore etcd if available**:

```bash
# On control plane node with etcdctl
sudo ETCDCTL_API=3 etcdctl get /registry/namespaces/default \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key
```

### Practice Drills

#### Drill 1: Component Identification Race

Without looking at notes, identify which component handles each scenario. The target is two minutes, but accuracy matters more than speed because each row maps to an exam troubleshooting path.

| Scenario | Component |
|----------|-----------|
| Stores all cluster state | ___ |
| Decides which node runs a new pod | ___ |
| Authenticates kubectl requests | ___ |
| Creates pods when ReplicaSet changes | ___ |
| Reports node status to control plane | ___ |
| Maintains iptables rules for Services | ___ |

<details>
<summary>Solution</summary>

1. etcd
2. kube-scheduler
3. kube-apiserver
4. kube-controller-manager (ReplicaSet controller)
5. kubelet
6. kube-proxy

</details>

#### Drill 2: Troubleshooting Missing Scheduler

Exercise scenario: Pods are stuck in Pending forever because the scheduler manifest has been moved out of the watched manifest directory. Do this only on a disposable cluster where breaking scheduling is acceptable.

```bash
# Setup: Break the scheduler
sudo mv /etc/kubernetes/manifests/kube-scheduler.yaml /tmp/

# Create a test pod
kubectl run drill-pod --image=nginx

# Observe the problem
kubectl get pods  # Pending forever
kubectl describe pod drill-pod | grep -A5 Events

# YOUR TASK: Diagnose and fix
# 1. What's missing?
# 2. How do you restore it?
```

<details>
<summary>Solution</summary>

```bash
# Check control plane pods
kubectl get pods -n kube-system | grep scheduler  # Nothing!

# Restore scheduler
sudo mv /tmp/kube-scheduler.yaml /etc/kubernetes/manifests/

# Wait for scheduler and verify
kubectl get pods -n kube-system | grep scheduler  # Running!
kubectl get pod drill-pod  # Now Running

# Cleanup
kubectl delete pod drill-pod
```

</details>

#### Drill 3: Troubleshooting Controller Manager Down

Exercise scenario: Deployments are accepted by the API server, but ReplicaSets and Pods are never created because the controller manager manifest has been moved away.

```bash
# Setup
sudo mv /etc/kubernetes/manifests/kube-controller-manager.yaml /tmp/

# Create deployment
kubectl create deployment drill-deploy --image=nginx --replicas=3

# Observe
kubectl get deploy  # Shows 0/3 ready
kubectl get rs      # No ReplicaSet created!
kubectl get pods    # No pods!

# YOUR TASK: Diagnose and fix
```

<details>
<summary>Solution</summary>

```bash
# Check controller manager
kubectl get pods -n kube-system | grep controller  # Nothing!

# Restore controller manager
sudo mv /tmp/kube-controller-manager.yaml /etc/kubernetes/manifests/

# Watch pods appear
kubectl get pods -w  # 3 pods created

# Cleanup
kubectl delete deployment drill-deploy
```

</details>

#### Drill 4: API Server Health Deep Dive

Check API server health using multiple methods and compare what each method proves. The direct curl method is useful from the control plane node, while the `kubectl get --raw` methods verify the authenticated API path.

```bash
# Method 1: Basic connectivity
kubectl cluster-info

# Method 2: Health endpoints
kubectl get --raw='/healthz'
kubectl get --raw='/readyz'
kubectl get --raw='/livez'

# Method 3: Detailed health
kubectl get --raw='/readyz?verbose' | grep -E "^\[|ok|failed"

# Method 4: Direct curl (from control plane)
curl -k https://localhost:6443/healthz

# Method 5: Check API server logs for errors
kubectl logs -n kube-system -l component=kube-apiserver --tail=20 | grep -i error
```

#### Drill 5: Watch the Reconciliation Loop

Use two terminals to observe that changing desired state does not directly run containers. The controller manager reacts first, then lower-level objects and node components continue the chain.

```bash
# Terminal 1: Watch controller manager logs
kubectl logs -n kube-system -l component=kube-controller-manager -f | grep -i "replicaset\|deployment"

# Terminal 2: Create, scale, delete deployment
kubectl create deployment watch-me --image=nginx --replicas=2
kubectl rollout status deployment watch-me

kubectl scale deployment watch-me --replicas=5
kubectl rollout status deployment watch-me

kubectl delete deployment watch-me

# Observe logs in Terminal 1 - see the controller react to each change
```

#### Drill 6: etcd Exploration

Explore what etcd stores if you have `etcdctl` and the local certificates on the control plane node. Avoid listing all keys in production clusters because the output can be large and may expose sensitive object names.

```bash
# Set up etcdctl alias
export ETCDCTL_API=3
alias etcdctl='etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key'

# List all keys (be careful in production!)
etcdctl get / --prefix --keys-only | head -50

# Find all pods
etcdctl get /registry/pods --prefix --keys-only

# Get a specific pod's data
etcdctl get /registry/pods/default/<pod-name>
```

#### Drill 7: Challenge Full Control Plane Restart

Exercise scenario: restart control plane static Pods by restarting kubelet, then verify that the cluster recovers. This is an advanced practice task for disposable clusters only.

```bash
# WARNING: Only do this on practice clusters!

# 1. Note current state
kubectl get nodes
kubectl get pods -A | wc -l

# 2. Restart all control plane components
sudo systemctl restart kubelet
# Static pods will restart automatically

# 3. Wait and verify recovery
sleep 30
kubectl get nodes  # All Ready?
kubectl get pods -n kube-system  # All Running?

# 4. Test workload scheduling
kubectl run recovery-test --image=nginx
kubectl wait --for=condition=Ready pod/recovery-test --timeout=60s
kubectl get pods
kubectl delete pod recovery-test
```

**Card A: API server down means running containers die.** A candidate sees `kubectl` fail to connect during a practice outage and immediately assumes every application container on every worker must have exited. They begin deleting workload objects and planning redeployments even though the affected Pods were already assigned to nodes before the API server failure. The wrong belief is tempting because the API server feels like the cluster's control center, but running containers are local runtime processes once kubelet has started them.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing loss of central coordination with instant loss of local execution. Next action: check node-local kubelet and runtime evidence for already assigned Pods, then separately repair API access so new scheduling, status updates, and reconciliation can resume.

</details>

**Card B: Pending always means the scheduler is broken.** An operator sees a Pod remain `Pending` after a Deployment is created and jumps straight to scheduler logs, assuming the scheduling process must be hung. They overlook that the Pod requests more CPU and memory than any node can currently provide, so the scheduler has no feasible node to choose. The wrong belief turns a clear capacity or constraint message into unnecessary control plane surgery.

<details>
<summary>Check your prediction</summary>

Failure layer: treating `Pending` as a process-health verdict instead of a placement outcome. Next action: read `kubectl describe pod` Events first, then compare resource requests, taints, node selectors, affinity, and volume binding before touching scheduler components.

</details>

**Card C: Deleting the scheduler Pod in kube-system restarts scheduling when the static manifest is gone.** A learner accidentally removes `/etc/kubernetes/manifests/kube-scheduler.yaml`, notices the mirror Pod still appears for a moment, and runs `kubectl delete pod` in `kube-system` to force a clean restart. They expect the kubelet to recreate the scheduler from the deleted Pod object, but the durable source for that static Pod has disappeared. The wrong belief confuses the API mirror with the file that kubelet actually watches.

<details>
<summary>Check your prediction</summary>

Failure layer: mistaking a static Pod mirror object for the authoritative static Pod definition. Next action: restore `/etc/kubernetes/manifests/kube-scheduler.yaml` with correct content and permissions, watch kubelet recreate the static Pod, and verify Pending Pods receive `nodeName` assignments.

</details>

**Card D: Slow kubectl get is a scheduler problem.** A team notices `kubectl get pods -A` is slow, `kubectl apply` often times out, and API server logs mention storage latency, then they focus on scheduler restarts because new Pods also appear delayed. They miss that broad API read and write slowness affects many resources before any single scheduling decision can matter. The wrong belief follows one visible workload symptom while ignoring the shared etcd-backed state path underneath it.

<details>
<summary>Check your prediction</summary>

Failure layer: diagnosing a broad API storage symptom as a narrow placement symptom. Next action: check API server readiness, etcd endpoint or member health, disk pressure, certificates, and storage latency before investigating scheduler behavior.

</details>

**Success Criteria**:

- [ ] Can identify all control plane components and their Pods.
- [ ] Can check API server liveness and readiness using supported health endpoints.
- [ ] Can find and read control plane component logs through `kubectl` when the API is healthy.
- [ ] Can switch to local kubelet, manifest, and runtime inspection when the API server is unavailable.
- [ ] Can explain what each component does during Deployment creation.
- [ ] Can restore a moved scheduler or controller manager static Pod manifest in a practice cluster.

### Cleanup

```bash
# Remove test deployment if created
kubectl delete deployment test --ignore-not-found
```

---

## Sources

- https://kubernetes.io/docs/concepts/overview/components/
- https://kubernetes.io/docs/concepts/architecture/control-plane-node-communication/
- https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/
- https://kubernetes.io/docs/reference/command-line-tools-reference/kube-scheduler/
- https://kubernetes.io/docs/reference/command-line-tools-reference/kube-controller-manager/
- https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/
- https://kubernetes.io/docs/reference/command-line-tools-reference/kube-proxy/
- https://kubernetes.io/docs/reference/using-api/health-checks/
- https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/
- https://kubernetes.io/docs/tasks/debug/debug-cluster/
- https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/
- https://etcd.io/docs/v3.6/op-guide/runtime-configuration/

## Next Module

[Module 1.2: Extension Interfaces (CNI, CSI, CRI)](../module-1.2-extension-interfaces/) - How Kubernetes plugs in networking, storage, and container runtimes.
