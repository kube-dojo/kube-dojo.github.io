---
revision_pending: false
title: "Module 2.6: Scheduling"
slug: k8s/cka/part2-workloads-scheduling/module-2.6-scheduling
sidebar:
  order: 7
lab:
  id: cka-2.6-scheduling
  url: https://killercoda.com/kubedojo/scenario/cka-2.6-scheduling
  duration: "45 min"
  difficulty: advanced
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Critical exam topic
>
> **Time to Complete**: 45-55 minutes
>
> **Prerequisites**: Module 2.1 (Pods), Module 2.5 (Resource Management)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Design** node placement rules with nodeSelector, node affinity, pod affinity, and pod anti-affinity while explaining the scheduling tradeoffs.
- **Implement** taints and tolerations so dedicated, special-purpose, or temporarily protected nodes accept only the pods that should run there.
- **Evaluate** topology spread constraints for high availability across zones and nodes without creating avoidable Pending pods.
- **Diagnose** Pending pods by reading scheduler events and matching them to labels, taints, resources, affinity, and topology constraints.
- **Compare** hard and soft scheduling rules so exam answers and production manifests choose the least fragile control that still satisfies the requirement.

---

## Why This Module Matters

Hypothetical scenario: a platform team adds three new worker nodes to a Kubernetes 1.35 cluster, labels them for storage workloads, and expects a database rollout to land there. The pods stay Pending even though `kubectl top nodes` shows idle CPU and memory. The actual problem is not capacity in the broad sense; the pod requires one label, prefers another label, lacks a toleration for a node taint, and uses anti-affinity that cannot be satisfied in the current node layout. A person who only checks resource usage will chase the wrong problem, while a person who understands scheduling can read the event and move directly to the failing constraint.

Scheduling is where Kubernetes turns a declarative pod spec into a concrete node assignment. By default, the scheduler can place a pod on any feasible node with enough resources, but real clusters rarely stay that simple for long. Teams reserve GPU nodes for machine learning workloads, keep replicas apart so one node failure does not remove an entire service, prefer lower-cost instance types for batch jobs, and avoid zones that would create unnecessary network charges. These controls are powerful because they let one cluster host different reliability, cost, and hardware profiles without manually binding pods to nodes.

The risk is that every placement rule reduces the scheduler's freedom. A hard node affinity rule can make a rollout fail when a label is missing. A toleration can let a pod run on a dedicated node but does not force it to run there. A required anti-affinity rule can express perfect separation and accidentally make the last replica impossible to schedule. This module teaches scheduling as a decision process rather than a bag of YAML fragments, so you can choose the narrowest constraint that solves the real operational problem and debug the event trail when Kubernetes refuses to bind the pod.

The wedding seating analogy is still useful if you keep its limits in mind. `nodeSelector` is like assigning a guest to tables with an exact tag, such as "VIP." Node affinity is a richer seating preference: guests can require any table near the stage or merely prefer one side of the room. Taints are reserved-table signs, and tolerations are the badges that allow certain guests to sit there. Pod anti-affinity is the rule that keeps two people apart, while topology spread constraints are the seating chart rule that keeps each section of the room evenly filled.

## Node Labels, nodeSelector, and the Smallest Useful Constraint

The simplest scheduling rule is a node label match. Nodes are Kubernetes API objects, and labels on nodes work like labels on pods: they are key-value metadata that other components can select. A pod's `nodeSelector` is an exact AND match against those node labels. If the pod says `disk: ssd`, the scheduler removes every node that does not have `disk=ssd` from the feasible set before it scores the remaining nodes. That makes `nodeSelector` easy to read, easy to test, and easy to overuse.

Use `nodeSelector` when the requirement is binary and stable. Operating system, architecture, and a small number of hardware classes are good examples because the labels describe real node properties and the manifest usually has no reason to express alternatives. If a workload cannot run on Windows nodes, `kubernetes.io/os: linux` is clearer than a more elaborate affinity rule. If a test workload must land on one labeled training node during an exam lab, a selector is fast and defensible.

The tradeoff is that `nodeSelector` cannot express "one of these values," "prefer this but allow fallback," or "avoid this label if possible." It also combines every key with AND logic, so a pod requiring `disk=ssd` and `zone=us-west-1a` needs a node that has both labels at the same time. That exactness is helpful when you truly need it, but it can be brittle when cluster inventory changes. Before adding a selector, ask whether the pod must fail if the label is absent or whether a preference would be safer.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ssd-pod
spec:
  nodeSelector:
    disk: ssd              # Only schedule on nodes with this label
  containers:
  - name: nginx
    image: nginx
```

Node label management is often the fastest way to prove whether a scheduling rule is correct. On the CKA exam, you are likely to label a node, create a pod, and then verify placement with `kubectl get pod -o wide`. In production, label changes need more governance because they change the eligible node set for every pod that selects those labels. A misspelled key such as `disks=ssd` instead of `disk=ssd` is enough to make a perfectly healthy pod stay Pending.

```bash
# List node labels
kubectl get nodes --show-labels

# Label a node
kubectl label node worker-1 disk=ssd

# Remove a label
kubectl label node worker-1 disk-

# Overwrite a label
kubectl label node worker-1 disk=hdd --overwrite
```

Kubernetes and cloud providers attach several useful built-in labels to nodes. These labels are safer than ad hoc labels when they describe facts maintained by the platform, such as operating system or topology zone. You should still verify the actual keys in your cluster because older clusters, local labs, and managed services can differ in what they expose. The scheduler only sees the labels that exist on the Node object at scheduling time.

| Label | Description |
|-------|-------------|
| `kubernetes.io/hostname` | Node hostname |
| `kubernetes.io/os` | Operating system (linux, windows) |
| `kubernetes.io/arch` | Architecture (amd64, arm64) |
| `topology.kubernetes.io/zone` | Cloud availability zone |
| `topology.kubernetes.io/region` | Cloud region |
| `node.kubernetes.io/instance-type` | Instance type (cloud) |

```yaml
# Example: Schedule only on Linux nodes
spec:
  nodeSelector:
    kubernetes.io/os: linux
```

**Pause and predict:** a pod selects both `kubernetes.io/os: linux` and `disk: ssd`. The cluster has Linux nodes and SSD nodes, but no node carries both labels. What happens when the scheduler tries to place this pod, and what evidence would you check?

<details>
<summary>Check your prediction</summary>

The scheduler requires every `nodeSelector` key to match on the same node; it cannot combine a Linux match from one node with an SSD match from another. It finds no eligible node, so the pod stays Pending. A `FailedScheduling` event points to the node selector mismatch.

</details>

The next section is node affinity, which gives you more ways to describe placement requirements and preferences when a simple selector is too restrictive.

That behavior is why selectors should describe required facts, not vague preferences. If SSD placement improves performance but ordinary disks are acceptable during a capacity crunch, a hard selector is too strict. If Linux is required because the container image or workload cannot run on Windows, a selector is appropriate. The CKA mindset is to convert the sentence in the task into a scheduling contract: "must run on" means hard filtering, while "should prefer" means scoring.

## Node Affinity: Required Rules, Preferred Rules, and Operators

Node affinity is the next step up from `nodeSelector`. It still places pods based on node labels, but it gives you richer expressions, multiple values per key, and soft preferences. The most important naming pattern is `requiredDuringSchedulingIgnoredDuringExecution` versus `preferredDuringSchedulingIgnoredDuringExecution`. The first phrase says whether the rule is mandatory or a preference during scheduling; the second phrase says label changes after placement do not automatically evict or reschedule the pod.

That "ignored during execution" suffix prevents a common misconception. If a pod lands on a node because the node has `disk=ssd`, and someone later removes that label, the pod keeps running. Kubernetes does not continuously re-run every node affinity decision for already-bound pods. If you need runtime eviction based on node conditions or administrative action, you are in taint, toleration, drain, or controller territory rather than node affinity territory.

| Type | Behavior |
|------|----------|
| `requiredDuringSchedulingIgnoredDuringExecution` | Hard requirement (like nodeSelector) |
| `preferredDuringSchedulingIgnoredDuringExecution` | Soft preference |

Required node affinity is useful when you need more expression than `nodeSelector` but still want a hard filter. The classic example is "disk must be SSD or NVMe." `nodeSelector` cannot express two acceptable values for the same key, but affinity can use the `In` operator with multiple values. The scheduler treats terms as alternatives and expressions within a term as combined requirements, so read the indentation carefully before you trust the rule.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: affinity-required
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: disk
            operator: In
            values:
            - ssd
            - nvme
  containers:
  - name: nginx
    image: nginx
```

Preferred node affinity changes the scheduler's scoring phase instead of the filtering phase. A preferred rule says, "If eligible nodes match this preference, score them higher, but do not fail the pod when they do not." The weight can be from 1 to 100, and multiple preferences add to the final score used by the scheduler profile. This is the right tool when a hardware class, zone, or instance family is beneficial but not absolutely required for correctness.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: affinity-preferred
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80               # Higher weight = stronger preference
        preference:
          matchExpressions:
          - key: disk
            operator: In
            values:
            - ssd
      - weight: 20
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values:
            - us-west-1a
  containers:
  - name: nginx
    image: nginx
```

In this example, `zone` is a custom node label you apply in the lab (for example `kubectl label node ... zone=us-west-1a`). On cloud clusters, prefer the well-known `topology.kubernetes.io/zone` key instead — nodes must expose zone labels for either key to contribute to preferred-affinity scoring.

Think of required affinity as a locked door and preferred affinity as a recommendation from the seating host. A locked door keeps a pod out even when the room has empty chairs. A recommendation can influence where the pod lands, but other scoring factors may still win. This distinction matters when you debug, because a pod that violates a preference can still be Running, while a pod that violates a requirement cannot be bound at all.

Node affinity operators make the rule expressive enough for real scheduling contracts. `In` and `NotIn` compare label values against a set. `Exists` and `DoesNotExist` care only about whether the key is present. `Gt` and `Lt` perform integer comparisons, which can be helpful for numeric labels but are less common in exam tasks. The scheduler evaluates the labels on the node, not data inside the container image or application.

| Operator | Meaning |
|----------|---------|
| `In` | Label value is in set |
| `NotIn` | Label value not in set |
| `Exists` | Label exists (any value) |
| `DoesNotExist` | Label doesn't exist |
| `Gt` | Greater than (integer comparison) |
| `Lt` | Less than (integer comparison) |

```yaml
# Example: Node must have "gpu" label with any value
matchExpressions:
  - key: gpu
    operator: Exists

# Example: Node must NOT be in zone us-east-1c
matchExpressions:
  - key: topology.kubernetes.io/zone
    operator: NotIn
    values:
    - us-east-1c
```

Before running this, what output do you expect if every node lacks the `gpu` label and the pod uses required node affinity with `operator: Exists`? The pod should remain Pending because the scheduler has no feasible node after the node affinity filter. If the same rule is written as a preferred affinity term, the pod can still run somewhere, but the preference contributes no useful score because no node matches it.

Affinity becomes confusing when you combine it with selectors. A pod can have both `nodeSelector` and `nodeAffinity`, and both must be satisfied. That can be exactly what you want, such as requiring Linux and then preferring one instance family, but it can also create hidden contradictions. When a Pending pod has both fields, do not debug them separately as if one overrides the other. Read the whole pod spec and reduce the rules until you find the first filter that removes every node.

## Pod Affinity and Anti-Affinity: Placing Workloads Relative to Other Pods

Node affinity asks, "What labels does the node have?" Pod affinity asks, "What other pods are already running in this topology domain?" That shift is subtle but important. You use pod affinity when proximity to another workload matters, such as putting a web pod near a cache pod in the same node or zone. You use pod anti-affinity when separation matters, such as keeping replicas away from one another so one node failure does not remove all copies.

Inter-pod affinity rules use a `labelSelector` to identify the peer pods and a `topologyKey` to define what "near" or "apart" means. With `topologyKey: kubernetes.io/hostname`, the domain is a node. With `topology.kubernetes.io/zone`, the domain is a zone. The scheduler looks at the existing pods that match the selector, finds their nodes, reads those nodes' topology labels, and then decides whether the candidate node is allowed.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-pod
spec:
  affinity:
    podAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: cache
        topologyKey: kubernetes.io/hostname    # Same node
  containers:
  - name: web
    image: nginx
```

Required pod affinity is less common than required pod anti-affinity because it can create startup ordering problems. If the cache pod does not exist yet, a web pod that requires proximity to `app=cache` has no matching peer to anchor the rule. For tightly coupled side-by-side components, a single pod with multiple containers may be a better design. For workloads that only benefit from proximity, preferred pod affinity is usually more resilient.

Pod anti-affinity is a common high-availability pattern, especially with Deployments and StatefulSets. The following rule says a pod should not schedule onto a node that already has a pod labeled `app=web`. When used with required semantics, it enforces one matching pod per topology domain. That can be exactly right for three replicas on three nodes, and exactly wrong for four replicas on three nodes.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-pod
  labels:
    app: web
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: web
        topologyKey: kubernetes.io/hostname
  containers:
  - name: web
    image: nginx
```

Hypothetical scenario: a team scales a Deployment from two replicas to four after a traffic increase, but the cluster has only three worker nodes and the template uses required pod anti-affinity by hostname. The first three replicas can occupy different nodes. The fourth has no legal destination because every node already has a matching pod. The cluster still has unused resources, but the placement rule is stricter than the capacity model.

The topology key determines the size of the separation domain. Hostname anti-affinity spreads across nodes. Zone anti-affinity spreads across zones. Region anti-affinity is rarely useful inside a single cluster because most clusters are scoped to one region, but the label exists in many cloud environments. The key must exist on candidate nodes, because a missing topology label can make a rule impossible to evaluate the way you intended.

| topologyKey | Meaning |
|-------------|---------|
| `kubernetes.io/hostname` | Same node |
| `topology.kubernetes.io/zone` | Same availability zone |
| `topology.kubernetes.io/region` | Same region |

```
┌────────────────────────────────────────────────────────────────┐
│            Anti-Affinity with Different topologyKeys           │
│                                                                │
│   topologyKey: kubernetes.io/hostname                          │
│   -> Pods spread across nodes (one per node)                   │
│                                                                │
│   Node1: [web-1]    Node2: [web-2]    Node3: [web-3]           │
│                                                                │
│   topologyKey: topology.kubernetes.io/zone                     │
│   -> Pods spread across zones (one per zone)                   │
│                                                                │
│   Zone-A            Zone-B            Zone-C                   │
│   [web-1]           [web-2]           [web-3]                  │
│   Node1,Node2       Node3,Node4       Node5,Node6              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

For CKA tasks, the fastest diagnostic is to translate the topology key into plain language. `kubernetes.io/hostname` means "same or different node." `topology.kubernetes.io/zone` means "same or different zone." If the question asks for replicas across nodes, hostname is the likely key. If it asks for availability zones, use the zone label and make sure the cluster actually has that label on the nodes in the lab.

Pod anti-affinity is not the same thing as topology spread constraints. Anti-affinity answers whether a candidate domain already has a matching pod and can enforce strict absence. Topology spread counts how many matching pods exist in each domain and limits the skew between domains. If you want six replicas across three zones, anti-affinity by zone may block the fourth pod, while topology spread can allow two per zone with a skew of one or zero depending on the current distribution.

## Taints and Tolerations: Repulsion, Permission, and Eviction

Taints live on nodes, and tolerations live on pods. The mental model is repulsion: a tainted node repels pods that do not tolerate that taint. This is different from node affinity, which attracts or filters pods based on labels. A toleration does not attract a pod to the tainted node by itself; it only allows the pod to pass a filter that would otherwise reject it. To dedicate nodes, you commonly combine a taint with node affinity or a selector.

```
┌────────────────────────────────────────────────────────────────┐
│                   Taints and Tolerations                       │
│                                                                │
│   Node with taint: gpu=true:NoSchedule                         │
│   ┌─────────────────────────────────────────────┐              │
│   │                                             │              │
│   │  Regular Pod:        blocked from node      │              │
│   │                                             │              │
│   │  Pod with matching   allowed on node        │              │
│   │  toleration:                                │              │
│   │                                             │              │
│   └─────────────────────────────────────────────┘              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

The taint effect controls how strong the repulsion is. `NoSchedule` prevents new pods from being scheduled unless they tolerate the taint, while existing pods remain. `PreferNoSchedule` asks the scheduler to avoid the node but permits placement when necessary. `NoExecute` is stronger because it also affects existing pods; pods without a matching toleration can be evicted from the node. That makes `NoExecute` useful for some node-condition behavior and dangerous as a casual maintenance tool.

| Effect | Behavior |
|--------|----------|
| `NoSchedule` | Pods won't be scheduled (existing pods stay) |
| `PreferNoSchedule` | Soft version - avoid but allow if necessary |
| `NoExecute` | Evict existing pods, prevent new scheduling |

Stop and think: an SRE wants to prepare a node for maintenance by preventing new placements, but they want existing pods to keep running until a controlled drain later in the window. `NoSchedule` is the right taint effect because it blocks new scheduling without evicting existing pods. If the goal is to remove existing pods, use a deliberate drain procedure or a `NoExecute` taint only when you understand the eviction behavior and controller impact.

```bash
# Add taint to node
kubectl taint nodes worker-1 gpu=true:NoSchedule

# View taints
kubectl describe node worker-1 | grep Taints

# Remove taint (note the minus sign)
kubectl taint nodes worker-1 gpu=true:NoSchedule-

# Multiple taints
kubectl taint nodes worker-1 dedicated=ml:NoSchedule
kubectl taint nodes worker-1 gpu=nvidia:NoSchedule
```

The syntax of a toleration mirrors the taint, but the semantics are still permission rather than attraction. A pod with a toleration for `gpu=true:NoSchedule` may run on a GPU-tainted node, but it may also run on an untainted node unless another rule restricts it. This is a frequent source of surprise. If the requirement says "only GPU pods should run on GPU nodes," taint the GPU nodes and add tolerations to GPU pods. If it says "GPU pods must run on GPU nodes," also add node affinity for a GPU label.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  tolerations:
  - key: "gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  containers:
  - name: cuda-app
    image: nvidia/cuda
```

Toleration operators are simpler than affinity operators. `Equal` requires the key, value, and effect to match the taint. `Exists` can match any value for a given key, and a toleration with only `operator: Exists` can tolerate all taints. That wildcard form is powerful and should be rare for application pods because it bypasses the isolation intent of taints across the cluster.

| Operator | Meaning |
|----------|---------|
| `Equal` | Key and value must match |
| `Exists` | Key exists (any value matches) |

```yaml
# Match specific value
tolerations:
- key: "gpu"
  operator: "Equal"
  value: "nvidia"
  effect: "NoSchedule"

# Match any value for key
tolerations:
- key: "gpu"
  operator: "Exists"
  effect: "NoSchedule"

# Tolerate all taints (wildcard)
tolerations:
- operator: "Exists"
```

Several common cluster patterns use taints deliberately. Control plane nodes are often tainted so ordinary application pods do not compete with control plane components. GPU nodes are tainted so non-GPU pods do not waste specialized hardware. Batch or spot nodes may be tainted so only workloads designed for interruption run there. The exact keys are a local policy decision, but the scheduling mechanics are the same.

| Use Case | Taint Example |
|----------|---------------|
| GPU nodes | `gpu=true:NoSchedule` |
| Dedicated nodes | `dedicated=team-a:NoSchedule` |
| Control plane nodes | `node-role.kubernetes.io/control-plane:NoSchedule` |
| Draining nodes | `node.kubernetes.io/unschedulable:NoSchedule` |

When you troubleshoot taints, read the scheduler event literally. A message such as `node(s) had untolerated taint` means adding CPU will not help, changing the image will not help, and restarting the pod will not help. Either the pod needs a matching toleration, the taint needs to be removed, or the workload should not be trying to use that node. The right fix depends on policy, not merely syntax.

## Topology Spread Constraints: Even Distribution Without One-Per-Domain Rigidity

Topology spread constraints were designed for the common case where you want balanced distribution across failure domains, not strict one-per-domain uniqueness. The scheduler counts matching pods in each topology domain and evaluates whether placing the new pod would exceed `maxSkew`. With `maxSkew: 1` across zones, Kubernetes tries to keep the difference between the most populated and least populated eligible zones no greater than one. That is often a better high-availability expression than required zone anti-affinity.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: spread-pod
  labels:
    app: web
spec:
  topologySpreadConstraints:
  - maxSkew: 1                              # Max difference between zones
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule        # Hard requirement
    labelSelector:
      matchLabels:
        app: web
  containers:
  - name: nginx
    image: nginx
```

The four core fields are worth memorizing because they map directly to scheduler behavior. `labelSelector` tells Kubernetes which pods to count. `topologyKey` defines the domains, such as nodes or zones. `maxSkew` defines the maximum allowed imbalance. `whenUnsatisfiable` decides whether the rule is a hard filter with `DoNotSchedule` or a soft scoring preference with `ScheduleAnyway`. A mistake in any of these fields changes the meaning of the whole constraint.

| Parameter | Description |
|-----------|-------------|
| `maxSkew` | Maximum allowed difference in pod count across domains |
| `topologyKey` | Label key defining domains (zone, node, etc.) |
| `whenUnsatisfiable` | `DoNotSchedule` (hard) or `ScheduleAnyway` (soft) |
| `labelSelector` | Which pods to count for distribution |

The `labelSelector` usually matches the pod template labels of the same Deployment, which makes the scheduler count sibling replicas. If the selector is too broad, unrelated pods can influence placement and make the distribution look worse than it is. If the selector is too narrow, the scheduler may not count the replicas you meant to spread. In exam conditions, compare the selector against the pod template labels before you spend time looking at node resources.

```
┌────────────────────────────────────────────────────────────────┐
│              Topology Spread (maxSkew: 1)                      │
│                                                                │
│   Zone A          Zone B          Zone C                       │
│   [pod][pod]      [pod]           [pod]                        │
│   Count: 2        Count: 1        Count: 1                     │
│                                                                │
│   Max difference = 2-1 = 1 <= maxSkew                          │
│                                                                │
│   New pod arrives - where can it go?                           │
│   Zone A: 3 pods -> difference 3-1=2 > maxSkew                 │
│   Zone B: 2 pods -> difference 2-1=1 <= maxSkew                │
│   Zone C: 2 pods -> difference 2-1=1 <= maxSkew                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

Topology spread still has failure modes. If one zone has no eligible nodes because of labels, taints, or resource pressure, a hard spread constraint may block scheduling in the other zones once the skew would become too large. `ScheduleAnyway` can be a better fit for user-facing services where running slightly imbalanced is better than not running. `DoNotSchedule` is appropriate when the availability requirement is stronger than the desire to complete the rollout immediately.

**Pause and predict:** a three-replica Deployment uses required pod anti-affinity on `kubernetes.io/hostname` in a cluster with two nodes. What happens to its third replica, and which constraint better expresses a goal to "spread as evenly as possible"?

<details>
<summary>Check your prediction</summary>

The third replica cannot schedule: required hostname anti-affinity excludes both nodes because each already runs a matching pod. For a goal of spreading as evenly as possible, a topology spread constraint with `ScheduleAnyway` or a carefully chosen `DoNotSchedule` rule expresses the distribution goal more accurately than required anti-affinity.

</details>

The next section is the cost and traffic tradeoff of distributing workloads across failure domains, which belongs in the same placement decision.

There is also a cost dimension. Spreading across zones improves fault tolerance, but some cloud environments charge for cross-zone data transfer or make cross-zone traffic slower than same-zone traffic. That does not mean you should avoid zone spreading; it means you should choose it for stateless front ends, replicated services, and workloads designed for zone failure, while being more deliberate with chatty storage systems. Scheduling is always reliability, cost, and performance negotiated in YAML.

## Scheduling Decision Flow and Troubleshooting Pending Pods

The scheduler is easier to debug when you separate filtering from scoring. Filtering removes nodes that cannot run the pod because they fail a hard requirement: insufficient resources, node selector mismatch, required affinity mismatch, untolerated taints, required anti-affinity, or hard topology spread. Scoring ranks the nodes that remain using preferences and plugin scores. If there are no remaining nodes, the pod stays Pending and the event tells you which filters rejected nodes.

```
┌────────────────────────────────────────────────────────────────┐
│                   Scheduling Decision Flow                     │
│                                                                │
│   Pod Created                                                  │
│       │                                                        │
│       ▼                                                        │
│   Filter Nodes                                                 │
│   ├── nodeSelector matches?                                    │
│   ├── Node affinity required matches?                          │
│   ├── Taints tolerated?                                        │
│   ├── Resources available?                                     │
│   ├── Pod anti-affinity satisfied?                             │
│   └── Topology spread constraints ok?                          │
│       │                                                        │
│       ▼                                                        │
│   Score Remaining Nodes                                        │
│   ├── Node affinity preferred                                  │
│   ├── Pod affinity preferred                                   │
│   └── Resource optimization                                    │
│       │                                                        │
│       ▼                                                        │
│   Select Highest Scoring Node                                  │
│       │                                                        │
│       ▼                                                        │
│   Bind Pod to Node                                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

The best first command is usually `kubectl describe pod <name>`, because the Events section includes FailedScheduling messages produced by the scheduler. Those messages often compress several independent reasons into one line, such as insufficient CPU on some nodes and an untolerated taint on another. Treat each reason as a separate filter result. Do not assume there is one root cause until you know whether any node satisfies all requirements at once.

| Symptom | Likely Cause | Debug Command |
|---------|--------------|---------------|
| Pending (no events) | No nodes match constraints | `kubectl describe pod` |
| Pending (Insufficient) | Resource shortage | Check node resources |
| Pending (Taints) | No toleration for taint | Check node taints, pod tolerations |
| Pending (Affinity) | No nodes match affinity rules | Simplify/remove affinity |

```bash
# Check pod events
kubectl describe pod <pod-name> | grep -A10 Events

# Check node labels
kubectl get nodes --show-labels

# Check node taints
kubectl describe node <node> | grep Taints

# Check node resources
kubectl describe node <node> | grep -A10 "Allocated resources"

# Verify where pods landed
kubectl get pods -o wide
```

A disciplined troubleshooting loop starts with the pod event, then checks the pod spec, then checks node reality. If the event mentions node affinity, inspect the affinity block and the node labels. If it mentions taints, inspect node taints and pod tolerations. If it mentions insufficient resources, compare requests against allocatable capacity and existing allocations. If it mentions topology spread or anti-affinity, count matching pods by topology domain instead of staring only at CPU and memory.

Exercise scenario: a pod says it requires `tier=frontend`, prefers `zone=us-east-1a`, and tolerates `frontend=true:NoSchedule`, yet it lands outside `us-east-1a`. That is not automatically a bug. The zone rule is preferred, so it can be ignored if another node scores higher or if no eligible node in that zone passes the hard filters. To force the zone, make it a required node affinity rule, but accept that the pod may then remain Pending when the zone lacks capacity.

The exam trick is to change as little as possible. If a task asks you to make one pod schedule, do not remove every constraint unless the question explicitly says the constraints are wrong. Add the missing label, add the missing toleration, lower an unrealistic request, or change a required rule to preferred only when that matches the stated goal. A broad cleanup may make the pod Running, but it can fail the intent of the task.

## Patterns & Anti-Patterns

Pattern: use labels for stable node capabilities and taints for node access policy. A label such as `disk=ssd` tells the scheduler what the node is. A taint such as `dedicated=ml:NoSchedule` tells the scheduler who is allowed to use it. Combining both gives you a complete contract for special nodes: ordinary pods are repelled, and approved pods both tolerate the taint and require the matching capability label.

Pattern: prefer soft rules when the business requirement is preference rather than correctness. Preferred node affinity, preferred pod anti-affinity, and `ScheduleAnyway` topology spread keep rollouts moving during partial capacity shortages. They are not weaker engineering; they are honest representations of requirements that can bend. The operational advantage is that the service remains available while still nudging placement toward the desired shape.

Pattern: use topology spread constraints for replica distribution across zones or nodes when you need balance rather than uniqueness. Required anti-affinity is excellent for "never two replicas in the same domain," but it becomes fragile when replica count exceeds domain count. Topology spread lets the scheduler reason about skew, which matches the way most multi-replica services are operated. For six replicas across three zones, balanced two-per-zone placement is usually the desired outcome.

Pattern: debug Pending pods as a set intersection problem. The feasible node set is the intersection of resources, selectors, required affinity, taints, anti-affinity, and topology spread. If any one constraint leaves an empty set, the pod cannot bind. This framing prevents random command use and helps you explain your fix during a review or exam debrief.

Anti-pattern: tainting dedicated nodes without adding a positive placement rule to the dedicated pods. The toleration lets the pod use the node, but it does not stop the pod from using untainted nodes. The better alternative is a taint plus a toleration plus node affinity or nodeSelector. That combination repels everyone else and attracts the intended workload.

Anti-pattern: writing required anti-affinity for every high-availability workload. Teams fall into this because "required" sounds safer than "preferred," but strict uniqueness can block scale-outs and rollouts. If the real goal is even distribution, use topology spread constraints. If the real goal is best-effort separation, use preferred anti-affinity and monitor placement.

Anti-pattern: treating labels as casual notes. A node label used by scheduling is part of the production control plane contract. Renaming, deleting, or applying it inconsistently can break workloads without changing a single Deployment manifest. Manage scheduling labels deliberately, document their meaning, and prefer provider-maintained labels when they accurately represent the property you need.

Anti-pattern: fixing scheduler failures by deleting constraints until the pod runs. That can hide the operational requirement the manifest was supposed to enforce. If a database replica required SSD nodes, making it run on any node may pass a shallow readiness check and still create a durability or performance problem. The better approach is to identify the failed constraint and decide whether to satisfy it, soften it, or correct it.

## Decision Framework

Choose the scheduling control by starting with the sentence you need to make true. If the sentence is about a node property, use node labels with `nodeSelector` or node affinity. If the sentence is about reserving or protecting nodes, use taints and tolerations. If the sentence is about relationship to other pods, use pod affinity or anti-affinity. If the sentence is about evenness across a topology, use topology spread constraints.

For a required node property, decide whether the condition is simple or expressive. A simple exact match, such as "Linux only" or "disk must be SSD," can use `nodeSelector` when there is only one acceptable value for each key. If the rule needs alternatives, operators, or preference, node affinity is clearer and safer. This keeps basic manifests readable while preserving affinity for cases where its extra structure carries real meaning.

For node reservation, start with the repulsion side of the policy. A taint on the node protects the node from ordinary pods, but that only answers who may enter. The allowed workload still needs a toleration to pass the taint filter, and it may need affinity to guarantee that it lands on the reserved nodes. This three-part design is common for GPU, platform, ingress, and batch pools because it separates "what the node is" from "who may use it."

For pod relationships, ask whether proximity is a correctness requirement or a best-effort optimization. Required pod affinity can block startup if the peer pod is missing, while required anti-affinity can block scale-out if there are not enough topology domains. Preferred pod affinity and preferred anti-affinity preserve intent without turning every temporary shortage into a failed rollout. Use required relationship rules only when a violation is worse than a Pending pod.

For balanced replicas, prefer topology spread constraints over clever anti-affinity unless the requirement is strict uniqueness. A spread rule makes the scheduler count matching pods per domain and reason about skew, which maps naturally to "keep these replicas balanced across zones." This is especially useful when replica count changes over time. A future scale-up that should create three pods per zone should not be blocked by a rule that was written as if one pod per zone were the permanent goal.

The final decision is whether the rule should fail closed or degrade gracefully. Fail closed when the wrong placement would break the workload, expose a protected node, or invalidate a reliability guarantee. Degrade gracefully when the rule is about cost, preference, latency, or best-effort separation. This wording is useful in reviews because it forces the team to say what harm the rule prevents rather than merely choosing the most restrictive field available.

Hard rules are for correctness boundaries. A pod that cannot run without a GPU should use a hard rule. A system component that must tolerate a control plane taint should declare that toleration. A replica that must never share a node with another matching replica can use required anti-affinity if the cluster has enough nodes. The cost of hard rules is rollout fragility, so every hard rule should be tied to a clear failure mode it prevents.

Soft rules are for preferences that improve reliability, performance, or cost without defining correctness. A web tier can prefer newer instance types while accepting older nodes. A service can prefer spreading across zones while still running during a temporary zone capacity issue. A cache client can prefer co-location with cache pods without blocking startup if the cache moves. The value of soft rules is graceful degradation.

When rules combine, order your thinking from broad to narrow. First, can any node run the pod based on resources and basic selectors? Second, do taints require permissions that the pod lacks? Third, do relationship rules with other pods remove the remaining nodes? Fourth, do topology constraints require a domain that is unavailable or imbalanced? This framework maps closely to scheduler events and keeps troubleshooting grounded.

For production design, write down the owner of each scheduling label and taint. If the platform team owns `dedicated=ml`, application teams should not invent competing meanings. If cloud automation applies topology labels, do not overwrite them with manual values. If a team needs a new placement class, create a small policy contract rather than letting every application create a one-off key. Scheduling remains maintainable only when the labels and taints are treated as shared infrastructure.

## Did You Know?

- **`IgnoredDuringExecution` is literal.** A pod that already passed node affinity keeps running if the matching node label changes after binding, so label drift affects future scheduling rather than immediately moving existing pods.

- **A toleration is not a destination.** It allows a pod onto a tainted node, but it does not require that node. Dedicated-node designs usually need a taint, a matching toleration, and a positive node selection rule.

- **Topology spread constraints became stable in Kubernetes 1.19 and remain a core Kubernetes 1.35 scheduling tool.** They are often a better fit than required anti-affinity for multi-replica services that need balanced placement rather than strict uniqueness.

- **DaemonSets receive several built-in tolerations automatically.** That helps node-level agents continue running on nodes with common condition taints, which is why DaemonSet scheduling often behaves differently from ordinary Deployment pods.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| `nodeSelector` typo | The manifest looks correct at a glance, but no node has the exact key and value. | Verify with `kubectl get nodes --show-labels`, then correct the key or label the intended node. |
| Missing toleration | The node has a `NoSchedule` taint, and the pod has no matching permission to pass that filter. | Add a toleration that matches key, value, and effect, or remove the taint if the node should be general purpose. |
| Treating toleration as attraction | A pod tolerates a dedicated node taint but still lands on an untainted node. | Combine the toleration with node affinity or nodeSelector for the dedicated node label. |
| Wrong topologyKey | The rule spreads by hostname when the intent was zone, or spreads by zone when the cluster lacks zone labels. | Match the key to the failure domain and confirm that every candidate node has the label. |
| `NoExecute` instead of `NoSchedule` | The operator wanted to block new placements but accidentally triggered eviction behavior. | Use `NoSchedule` for placement control, and use drain or `NoExecute` only when eviction is intended. |
| Anti-affinity too strict | Required separation demands more topology domains than the cluster actually has. | Use preferred anti-affinity or topology spread constraints with an appropriate `maxSkew`. |
| Ignoring resource requests | The team focuses on labels and taints while the event also reports insufficient CPU or memory. | Read the full FailedScheduling event and compare pod requests with node allocatable capacity. |

## Quiz

<details>
<summary>Question 1: Your team needs pods to run on SSD nodes but also accept NVMe nodes. A junior engineer used `nodeSelector: {disk: ssd}`, which excludes NVMe nodes. What rule should you write, and why?</summary>

Use `requiredDuringSchedulingIgnoredDuringExecution` node affinity with `operator: In` and values `ssd` and `nvme`. This is a hard requirement because the workload must use one of those disk classes, but it needs OR logic that `nodeSelector` cannot express for a single key. A preferred rule would allow non-SSD and non-NVMe nodes, which violates the requirement. A toleration would not help because taints control permission onto nodes rather than selecting disk labels.

</details>

<details>
<summary>Question 2: A pod tolerates `gpu=nvidia:NoSchedule`. The cluster has one node with that taint, one node with `dedicated=ml-team:NoSchedule`, and one untainted node. Where can the pod schedule, and what extra rule would make it use only GPU nodes?</summary>

The pod can schedule on the GPU-tainted node because it has a matching toleration, and it can also schedule on the untainted node because no toleration is needed there. It cannot schedule on the `dedicated=ml-team` node because that taint is different and remains untolerated. To make the pod use only GPU nodes, add node affinity or a nodeSelector for a GPU label such as `gpu=nvidia`. The toleration grants permission, while the label rule creates attraction or a hard requirement.

</details>

<details>
<summary>Question 3: You deploy six web replicas across three zones with required pod anti-affinity using `topology.kubernetes.io/zone`, and later replicas stay Pending. What went wrong, and what should you use instead?</summary>

Required zone anti-affinity says that no two matching pods may share a zone, so it can schedule at most three replicas across three zones. The fourth and later replicas have no legal zone even if every zone has spare CPU and memory. Topology spread constraints are the better fit because they balance counts across zones instead of enforcing one-per-zone uniqueness. With `maxSkew: 1`, six replicas can settle into an even two-per-zone shape when capacity exists.

</details>

<details>
<summary>Question 4: During a CKA task, `kubectl describe pod` shows `0/3 nodes are available: 2 Insufficient cpu, 1 node(s) had untolerated taint`. What are the two separate problems, and how do you decide which fix is appropriate?</summary>

Two nodes failed the resource filter because the pod's CPU request cannot fit there, so you can reduce the request, free capacity, or add capacity if that matches the task. The remaining node failed the taint filter because the pod lacks a matching toleration. Adding a toleration is appropriate only if that workload is supposed to run on the tainted node, such as an infrastructure pod on a reserved node. The key is that both reasons are independent filters, and a complete fix must leave at least one node satisfying all constraints.

</details>

<details>
<summary>Question 5: A Deployment has preferred node affinity for `zone=us-east-1a`, but a pod lands in another zone. A teammate says Kubernetes ignored the manifest. How do you explain the behavior?</summary>

Preferred node affinity affects scoring, not feasibility, so the scheduler is allowed to bind the pod to another eligible node. That can happen when no node in `us-east-1a` passes hard filters, or when other scoring factors outweigh the preference. If the zone is required for correctness, change the rule to required node affinity and accept that the pod may remain Pending when that zone lacks capacity. If the zone is only a cost or latency preference, the current behavior is expected.

</details>

<details>
<summary>Question 6: A cache client uses required pod affinity to run on the same node as `app=cache`, but the cache Deployment is temporarily scaled to zero. What happens, and what design would be less fragile?</summary>

The client pod can remain Pending because there is no matching cache pod that satisfies the required affinity term. Required pod affinity depends on existing matching pods in the specified topology domain, so startup ordering and scale-to-zero events matter. A less fragile design is preferred pod affinity if proximity is beneficial but not mandatory. If the containers truly must run together, place them in the same pod as separate containers instead of relying on scheduler co-location.

</details>

<details>
<summary>Question 7: You need to protect GPU nodes from ordinary workloads and also guarantee GPU workloads land there. Which combination of scheduling controls should you choose?</summary>

Taint the GPU nodes, add matching tolerations to approved GPU pods, and add node affinity or nodeSelector for a GPU node label. The taint repels ordinary pods that lack permission. The toleration lets approved pods pass the taint filter. The node affinity or selector makes those approved pods require the GPU nodes instead of merely being allowed to use them. Using only a toleration is incomplete because the pods could still run on untainted general-purpose nodes.

</details>

## Hands-On Exercise

In this exercise, you will practice the scheduling controls as a sequence rather than isolated commands. Use a disposable lab cluster, because you will add labels and taints to nodes and then remove them. Read each expected result before running the command, then compare it with the scheduler's actual behavior. The goal is not only to create Running pods; it is to explain why each pod was eligible or ineligible for each node.

### Part A: nodeSelector

Start with the smallest useful constraint: label one node and require that label from a pod. This proves that you can create a node label, use it from `nodeSelector`, verify placement, and clean up without leaving cluster state behind. If the pod does not land where expected, check whether the label key and value on the node exactly match the pod spec.

1. **Label a node and use nodeSelector**:

```bash
# Get a node name
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

# Label the node
kubectl label node $NODE disk=ssd

# Create pod with nodeSelector
cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: ssd-pod
spec:
  nodeSelector:
    disk: ssd
  containers:
  - name: nginx
    image: nginx
EOF

# Verify placement
kubectl get pod ssd-pod -o wide

# Cleanup
kubectl delete pod ssd-pod
kubectl label node $NODE disk-
```

### Part B: Taints and Tolerations

Now add a node taint and compare a pod without a toleration to a pod with a matching toleration. In a single-node lab, the pod without a toleration usually stays Pending. In a multi-node lab, it may land on another untainted node, which is still correct because taints repel only from the tainted node. The with-toleration pod should be allowed onto the tainted node, but remember that permission is not the same as attraction.

2. **Add taint and create pod with toleration**:

```bash
# Taint the node
kubectl taint nodes $NODE dedicated=special:NoSchedule

# Try to create pod without toleration
kubectl run no-toleration --image=nginx

# Check - should be Pending or on different node
kubectl get pod no-toleration -o wide

# Create pod with toleration
cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: with-toleration
spec:
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "special"
    effect: "NoSchedule"
  containers:
  - name: nginx
    image: nginx
EOF

# Verify placement
kubectl get pod with-toleration -o wide

# Cleanup
kubectl delete pod no-toleration with-toleration
kubectl taint nodes $NODE dedicated-
```

### Part C: Pod Anti-Affinity

Next, deploy three replicas with preferred pod anti-affinity by hostname. This rule asks the scheduler to spread matching pods across nodes when it can, but it does not block the Deployment if the lab has fewer nodes than replicas. That makes it a good exam-safe demonstration of the difference between preference and requirement. Check the `NODE` column and explain whether the result was fully spread or only best effort.

3. **Spread pods across nodes**:

```bash
cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spread-deploy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: spread
  template:
    metadata:
      labels:
        app: spread
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: spread
              topologyKey: kubernetes.io/hostname
      containers:
      - name: nginx
        image: nginx
EOF

# Check pod distribution
kubectl get pods -l app=spread -o wide

# Cleanup
kubectl delete deployment spread-deploy
```

**Card A: A nodeSelector with `kubernetes.io/os: linux` and `disk: ssd` is satisfied when some nodes are Linux and other nodes have SSDs.** An operator applies both keys to a pod while the cluster inventory splits those labels across separate machines.

<details>
<summary>Check your prediction</summary>

Failure layer: node selector conjunction versus cluster-wide label inventory. Next action: inspect labels on individual nodes and find one node carrying both values, or change the placement requirement; the scheduler cannot assemble a match from separate nodes.

</details>

**Card B: Removing the `disk=ssd` label from a node evicts pods that scheduled there because of required node affinity.** An operator removes the label after a pod has already been bound to that node.

<details>
<summary>Check your prediction</summary>

Failure layer: scheduling-time affinity versus runtime eviction. Next action: recognize that `requiredDuringSchedulingIgnoredDuringExecution` does not evict the already-bound pod when the label disappears; inspect the pod's node assignment, then use an appropriate drain or eviction workflow if relocation is required.

</details>

**Card C: Required pod anti-affinity on `kubernetes.io/hostname` still places all three replicas when the cluster has only two nodes.** A team expects every replica of its Deployment to start while also forbidding matching pods from sharing a hostname.

<details>
<summary>Check your prediction</summary>

Failure layer: strict one-per-host separation versus available topology domains. Next action: expect the third replica to remain unschedulable because both nodes already host a matching pod; add an eligible node or use a suitable topology spread constraint when balanced placement permits sharing.

</details>

**Card D: A toleration for a GPU taint forces the pod to run on GPU nodes.** An operator adds a matching toleration and assumes it also selects the GPU pool.

<details>
<summary>Check your prediction</summary>

Failure layer: taint permission versus node attraction. Next action: use node affinity or a node selector alongside the toleration when the pod must run on GPU nodes; the toleration only permits scheduling onto nodes with that taint.

</details>

**Success Criteria**:

- [ ] Design a nodeSelector-based placement rule and verify the selected node.
- [ ] Implement a taint and a matching toleration, then remove both cleanly.
- [ ] Compare allowed placement with required placement by explaining why toleration alone is not attraction.
- [ ] Evaluate pod anti-affinity behavior by checking whether replicas spread across nodes.
- [ ] Evaluate topology spread constraints by verifying replica placement across labeled zones.
- [ ] Diagnose at least one Pending pod from scheduler events rather than guessing from the manifest alone.

### Practice Drills

These drills reinforce the same ideas under time pressure. Run them only in a lab cluster, and clean up each drill before starting the next one. If a drill behaves differently from the comment, first check how many nodes your lab has and whether previous labels or taints are still present. Many scheduling surprises are simply leftover cluster state.

### Drill 1: nodeSelector (Target: 3 minutes)

```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

# Label node
kubectl label node $NODE env=production

# Create pod with nodeSelector (YAML matches exam-style manifests)
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: selector-test
spec:
  nodeSelector:
    env: production
  containers:
  - name: nginx
    image: nginx
EOF

# Verify
kubectl get pod selector-test -o wide

# Cleanup
kubectl delete pod selector-test
kubectl label node $NODE env-
```

### Drill 2: Taints (Target: 5 minutes)

```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

# Add taint
kubectl taint nodes $NODE app=critical:NoSchedule

# View taint
kubectl describe node $NODE | grep Taints

# Pod without toleration - will be Pending or elsewhere
kubectl run no-tol --image=nginx
kubectl get pod no-tol -o wide

# Pod with toleration
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: with-tol
spec:
  tolerations:
  - key: "app"
    operator: "Equal"
    value: "critical"
    effect: "NoSchedule"
  containers:
  - name: nginx
    image: nginx
EOF

kubectl get pod with-tol -o wide

# Cleanup
kubectl delete pod no-tol with-tol
kubectl taint nodes $NODE app-
```

### Drill 3: Node Affinity (Target: 5 minutes)

```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl label node $NODE size=large

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: affinity-test
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: size
            operator: In
            values:
            - large
            - xlarge
  containers:
  - name: nginx
    image: nginx
EOF

kubectl get pod affinity-test -o wide

# Cleanup
kubectl delete pod affinity-test
kubectl label node $NODE size-
```

### Drill 4: Pod Anti-Affinity (Target: 5 minutes)

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anti-affinity
spec:
  replicas: 3
  selector:
    matchLabels:
      app: anti-test
  template:
    metadata:
      labels:
        app: anti-test
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                app: anti-test
            topologyKey: kubernetes.io/hostname
      containers:
      - name: nginx
        image: nginx
EOF

# Check distribution (each pod on different node)
kubectl get pods -l app=anti-test -o wide

# Cleanup
kubectl delete deployment anti-affinity
```

### Drill 5: Troubleshooting - Pending Pod (Target: 5 minutes)

```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

# Create impossible scenario
kubectl taint nodes $NODE impossible=true:NoSchedule

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pending-pod
spec:
  nodeSelector:
    nonexistent: label
  containers:
  - name: nginx
    image: nginx
EOF

# Diagnose
kubectl get pod pending-pod
kubectl describe pod pending-pod | grep -A10 Events

# YOUR TASK: Why is it Pending? Fix it.

# Cleanup
kubectl delete pod pending-pod
kubectl taint nodes $NODE impossible-
```

<details>
<summary>Solution</summary>

The pod is Pending for two reasons. The `nodeSelector` requires `nonexistent=label`, which no node has unless you add it. The node also has a taint that the pod does not tolerate. Fix the scenario by adding the missing label to the intended node and adding a matching toleration, or by removing the artificial taint and selector if the workload should be general purpose.

</details>

### Drill 6: Challenge - Complex Scheduling

Create a pod that must run on nodes with label `tier=frontend`, prefers nodes with label `zone=us-east-1a`, and tolerates taint `frontend=true:NoSchedule`. This challenge combines a hard node requirement, a soft placement preference, and a taint permission. After it schedules, explain which part of the manifest would be responsible if the pod were Pending.

```bash
# YOUR TASK: Create this pod
```

<details>
<summary>Solution</summary>

```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl label node $NODE tier=frontend zone=us-east-1a
kubectl taint nodes $NODE frontend=true:NoSchedule

cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: complex-schedule
spec:
  tolerations:
  - key: "frontend"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: tier
            operator: In
            values:
            - frontend
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values:
            - us-east-1a
  containers:
  - name: nginx
    image: nginx
EOF

kubectl get pod complex-schedule -o wide

# Cleanup
kubectl delete pod complex-schedule
kubectl label node $NODE tier- zone-
kubectl taint nodes $NODE frontend-
```

</details>

### Drill 7: Topology Spread (Target: 5 minutes)

Apply the topology spread constraint from the theory section and verify that `app: web` replicas distribute across labeled zones. This drill works best on a multi-node lab (minikube with `--nodes 3`, kind, or a cloud cluster); on a single-node cluster, pods still schedule but zone skew is not meaningful.

```bash
# Label nodes with zone topology (adjust node count to your lab)
NODE1=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
NODE2=$(kubectl get nodes -o jsonpath='{.items[1].metadata.name}')
kubectl label node $NODE1 topology.kubernetes.io/zone=zone-a --overwrite
kubectl label node $NODE2 topology.kubernetes.io/zone=zone-b --overwrite

# Deploy replicas with topology spread (same labels/key as the theory example)
cat << 'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-spread
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: ScheduleAnyway
        labelSelector:
          matchLabels:
            app: web
      containers:
      - name: nginx
        image: nginx
EOF

# Verify spread — check NODE column and zone labels on those nodes
kubectl get pods -l app=web -o wide
kubectl get nodes -L topology.kubernetes.io/zone

# Expected: when two zones have eligible nodes, no zone should hold more
# than one extra replica compared to the least-populated zone (maxSkew: 1)

# Cleanup
kubectl delete deployment web-spread
kubectl label node $NODE1 topology.kubernetes.io/zone-
kubectl label node $NODE2 topology.kubernetes.io/zone-
```

## Learner check

Before moving on, confirm you can explain why a pod with preferred node affinity can land outside its preferred zone, and why topology spread with `maxSkew: 1` differs from required pod anti-affinity.

> In this example, `zone` is a custom node label you apply in the lab (for example `kubectl label node ... zone=us-west-1a`). On cloud clusters, prefer the well-known `topology.kubernetes.io/zone` key instead — nodes must expose zone labels for either key to contribute to preferred-affinity scoring.

## Sources

- [Assign Pods to Nodes](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- [Taints and Tolerations](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Pod Topology Spread Constraints](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
- [Kubernetes Scheduler](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
- [Well-Known Labels, Annotations, and Taints](https://v1-35.docs.kubernetes.io/docs/reference/labels-annotations-taints/)
- [Nodes](https://v1-35.docs.kubernetes.io/docs/concepts/architecture/nodes/)
- [Assign Pods to Nodes Using Node Labels](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/assign-pods-nodes/)
- [Assign Pods to Nodes Using Node Affinity](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/assign-pods-nodes-using-node-affinity/)
- [Safely Drain a Node](https://v1-35.docs.kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [Node-Pressure Eviction](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
- [DaemonSet](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [AWS Cost and Usage Report data transfer details](https://docs.aws.amazon.com/cur/latest/userguide/cur-data-transfers-charges.html)

## Next Module

[Module 2.7: ConfigMaps & Secrets](../module-2.7-configmaps-secrets/) - Application configuration management.
