---
citations_verified: true
title: "Module 6.4: FinOps with OpenCost"
slug: platform/toolkits/developer-experience/scaling-reliability/module-6.4-finops-opencost
sidebar:
  order: 5
---

> **Toolkit Track** | Complexity: `[MEDIUM]` | Time: 50-60 minutes

## Prerequisites

Before starting this module, you should be comfortable reading Kubernetes workload manifests, especially `resources.requests`, `resources.limits`, labels, namespaces, Services, and PersistentVolumeClaims. You should also understand why [schedulers use requests instead of live usage when placing Pods](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), because most Kubernetes cost allocation starts with that scheduling contract.

You should have completed or reviewed [Module 6.1: Karpenter](../module-6.1-karpenter/) if you want to connect cost visibility to node provisioning, spot capacity, and consolidation. Helm basics are assumed because the lab installs Prometheus and OpenCost with Helm charts. This module uses Kubernetes 1.35-compatible manifests and examples.

In the command examples, `kubectl` is shown first. After the setup section, you may create the common alias `alias k=kubectl` in your shell, and later inspection commands use `k` where it improves readability.

## Learning Outcomes

After completing this module, you will be able to:

- **Analyze** Kubernetes cluster spend by separating compute, storage, network, allocation, and idle cost signals.
- **Deploy and query** OpenCost with Prometheus so namespace, workload, and label-based allocation can support showback decisions.
- **Evaluate** right-sizing recommendations by comparing requests, observed usage, reliability headroom, throttling risk, and business criticality.
- **Design** cost guardrails with labels, ResourceQuotas, LimitRanges, and spot placement rules that reduce waste without surprising application teams.
- **Debug** common FinOps failure modes, including missing labels, misleading averages, idle resources, and workloads moved to unreliable capacity too aggressively.

## Why This Module Matters

A platform team at a growing SaaS company had a quiet reliability week and a very loud finance meeting. Their EKS clusters had no active incidents, the on-call rotation was calm, and customer-facing latency looked normal. The monthly cloud bill still climbed from \$38,000 to \$61,000, and nobody could explain which product, team, or workload caused the increase.

The first argument was about ownership. Finance saw a large compute line item tagged only as `eks-platform`, product engineering said the platform team owned the clusters, and the platform team said application teams owned their Pods. Everyone was partly right, but nobody had the allocation detail needed to act. A single worker node can run Pods from five teams, and a cloud bill usually charges for the node, not the individual Pod.

The second argument was about risk. One manager wanted to halve all CPU requests, another wanted to force every stateless workload onto spot instances, and a third wanted to delete every namespace older than a sprint. Each idea could save money, but each idea could also create an incident if applied without measurement. FinOps is not a cost-cutting contest. It is an operating model for making cost visible, accountable, and adjustable while reliability remains protected.

OpenCost gives platform teams the missing translation layer. It combines Kubernetes state, usage metrics, and cloud pricing so teams can [see which namespaces, controllers, labels, and idle capacity consume money](https://github.com/opencost/opencost). Once cost is visible at the level where engineers make decisions, the conversation changes from blame to design: which requests are oversized, which environments should sleep at night, which workloads tolerate interruption, and which shared platform costs should be allocated fairly.

## Core Content

### 1. Build the Cost Mental Model Before Installing Tools

Kubernetes itself does not send a cloud invoice, but Kubernetes decisions create the shape of the invoice. A Deployment requests CPU and memory, the scheduler packs Pods onto nodes, an autoscaler adds nodes when capacity is insufficient, and the cloud provider charges for the nodes and managed infrastructure. If the cluster asks the cloud for more capacity than workloads actually use, the difference becomes idle cost.

The first mental split is between **provisioned cost**, **allocated cost**, and **used cost**. Provisioned cost is what the cloud charges for running resources such as nodes, volumes, load balancers, and network services. Allocated cost is the share attributed to a namespace, workload, or team based on Kubernetes objects and resource requests. Used cost is the observed resource consumption over time. Waste often appears when allocated cost is much lower than provisioned cost, or when used cost is much lower than allocated cost.

```text
KUBERNETES COST BREAKDOWN
====================================================================

┌──────────────────────────────────────────────────────────────────┐
│                         TOTAL CLUSTER COST                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  COMPUTE                                                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Node cost = instance price x hours running                │  │
│  │  Allocated = sum of pod resource requests                  │  │
│  │  Used = observed CPU and memory over time                  │  │
│  │  Idle = node capacity - allocated capacity                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  STORAGE                                                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  PersistentVolumes, snapshots, backup retention, IOPS      │  │
│  │  Cost often follows provisioned size, not actual bytes     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  NETWORK                                                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Load balancers, NAT gateways, egress, cross-zone traffic  │  │
│  │  Cost often hides outside the application namespace        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

KEY INSIGHT:
The cloud charges for resources that exist. Kubernetes schedules against
resources that Pods request. Applications succeed or fail based on resources
they actually use under load.
```

A useful FinOps review begins by asking which gap matters most. If nodes are mostly empty, the platform may need better bin packing, Karpenter consolidation, or smaller instance families. If Pods request far more than they use, the application teams need right-sizing guidance. If network or storage costs dominate, workload CPU tuning will not solve the real problem.

**Stop and think:** A namespace owns Pods that request `12` CPU, but those Pods use only `2` CPU at P95. The cluster node pool has `32` CPU provisioned and only `18` CPU allocated. Which gap should the platform team investigate first: request waste, node idle capacity, or both? Write down what each number tells you before reading the next paragraph.

The answer is both, but in sequence. The namespace has request waste because `12` CPU requested for `2` CPU used is likely excessive unless the service has rare spikes or latency-critical behavior. The cluster also has node idle capacity because `32` CPU provisioned for `18` CPU allocated means the scheduler cannot fill the nodes with current requests. Reducing Pod requests may make node idle worse for a moment, then autoscaler consolidation can remove nodes and convert the request savings into cloud savings.

FinOps gets practical when the team distinguishes **showback** from **chargeback**. Showback means reporting costs to teams without directly billing them, usually to create awareness and better engineering decisions. Chargeback means assigning actual internal costs to teams or business units. Most organizations should start with showback because it reveals labeling gaps, shared-cost debates, and reporting mistakes before money moves between budgets.

| Cost Concept | Kubernetes Signal | Cloud Signal | Decision It Supports |
|---|---|---|---|
| Provisioned compute | Node capacity and node lifetime | VM or node hourly price | Can autoscaling or consolidation remove nodes? |
| Allocated compute | Pod CPU and memory requests | Shared node price | Which team or workload consumes scheduled capacity? |
| Used compute | Metrics from Prometheus or metrics-server | Not usually visible in the invoice | Are requests too high, too low, or unstable? |
| Storage | PVCs, PVs, storage classes | Volume, snapshot, and IOPS charges | Are volumes oversized or retained too long? |
| Network | Services, Ingress, traffic metrics | Load balancer, NAT, and egress charges | Are topology or exposure choices expensive? |

The table matters because each row has a different owner. Platform teams usually own node provisioning and shared infrastructure defaults. Application teams usually own requests, labels, and workload behavior. Finance usually owns budget reporting and allocation rules. OpenCost helps those groups use the same evidence instead of debating from separate dashboards.

### 2. Deploy OpenCost Where It Can See Metrics and Pricing

[OpenCost needs Kubernetes object data, usage metrics, and pricing inputs](https://github.com/opencost/opencost). Kubernetes tells it which Pods, controllers, namespaces, labels, nodes, and volumes exist. Prometheus provides time-series usage data so OpenCost can compare requested capacity with observed usage. Pricing can come from cloud integrations or configured defaults, depending on the environment and maturity of the deployment.

```text
OPENCOST ARCHITECTURE
====================================================================

┌────────────────┐      ┌────────────────┐      ┌──────────────────┐
│ Cloud Pricing  │      │ Kubernetes API │      │ Prometheus       │
│ API or Config  │      │ Server         │      │ Metrics Store    │
│                │      │                │      │                  │
│ instance price │      │ nodes          │      │ cpu usage        │
│ storage price  │      │ pods           │      │ memory usage     │
│ network price  │      │ namespaces     │      │ container stats  │
└───────┬────────┘      └───────┬────────┘      └────────┬─────────┘
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                │
                       ┌────────▼────────┐
                       │    OpenCost     │
                       │                 │
                       │ Allocation      │
                       │ idle tracking   │
                       │ efficiency      │
                       │ label grouping  │
                       └────────┬────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
        Dashboard UI        REST API        Prometheus metrics
        for humans          for reports      for alerting
```

For a production deployment, install OpenCost in a dedicated namespace and connect it to the same Prometheus that already scrapes kube-state-metrics, node metrics, and container metrics. For a learning environment, the exact dollar values may be synthetic or approximate, but the allocation relationships are still useful. A Pod that requests ten times more CPU than another Pod should show a larger allocated compute share even in a local cluster.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update

helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --create-namespace \
  --set server.persistentVolume.enabled=false \
  --set alertmanager.enabled=false

helm upgrade --install opencost opencost/opencost \
  --namespace opencost \
  --create-namespace \
  --set opencost.prometheus.internal.enabled=false \
  --set opencost.prometheus.external.url="http://prometheus-server.monitoring.svc:80" \
  --set opencost.ui.enabled=true
```

After installation, verify the Pods and Services before opening the dashboard. A dashboard that loads but shows missing or flat data usually means Prometheus connectivity is broken, metrics labels are incomplete, or the cluster has not had enough time to generate useful samples. Cost tooling is only as trustworthy as its inputs.

```bash
kubectl get pods -n monitoring
kubectl get pods -n opencost
kubectl get svc -n opencost

kubectl port-forward -n opencost svc/opencost 9090:9090
```

Open the dashboard at `http://127.0.0.1:9090` while the port-forward is running. In a real cluster, avoid exposing cost data publicly because namespace names, team labels, and workload names can reveal internal architecture. Treat cost visibility as operational data: useful to engineers and finance, but still [governed by access control](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).

You can also query the API directly when building reports or validating allocation behavior. The API is useful for automation because dashboards are good for exploration, while scheduled reports need repeatable queries. Keep the port-forward in one terminal and run the following commands in another.

```bash
kubectl port-forward -n opencost svc/opencost 9003:9003

curl -s "http://127.0.0.1:9003/allocation/compute?window=24h&aggregate=namespace"

curl -s "http://127.0.0.1:9003/allocation/compute?window=7d&aggregate=label:team"

curl -s "http://127.0.0.1:9003/allocation/compute?window=24h&aggregate=controller"
```

**Active check:** Suppose the namespace report works, but the `aggregate=label:team` report has a large unallocated or empty-label bucket. What operational problem does that reveal? The cost tool is not failing; it is showing that the cluster lacks a reliable ownership contract. The next platform task is not tuning CPU. It is enforcing labels at admission time and backfilling ownership metadata.

The deployment should eventually be connected to dashboards and alerts, but early adoption should start with a weekly report reviewed by both platform and application teams. If the first conversation is about a perfectly polished dashboard, teams may debate colors and chart types. If the first conversation is about three expensive namespaces, two missing labels, and one idle environment, teams can act.

### 3. Allocate Shared Cost Without Creating Bad Incentives

Allocation is not just arithmetic. It is a social contract that decides who is accountable for which costs. If allocation rules punish teams for using shared platform services, teams may bypass the platform. If allocation rules hide shared costs entirely, nobody has pressure to improve expensive defaults. Good FinOps design makes cost visible without encouraging unsafe local optimizations.

The simplest allocation model groups costs by namespace. This works when namespaces map cleanly to teams or environments, but many real clusters are messier. Shared namespaces may run platform controllers, observability agents, ingress controllers, and data services used by multiple teams. Application namespaces may contain workloads owned by multiple products. Labels give you more flexible allocation when namespace boundaries are not enough.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-api
  namespace: prod-user
  labels:
    app.kubernetes.io/name: user-api
    app.kubernetes.io/part-of: user-platform
    team: identity
    environment: production
    cost-center: engineering-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: user-api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: user-api
        app.kubernetes.io/part-of: user-platform
        team: identity
        environment: production
        cost-center: engineering-platform
    spec:
      containers:
      - name: user-api
        image: nginx:1.27
        resources:
          requests:
            cpu: "250m"
            memory: "384Mi"
          limits:
            memory: "768Mi"
```

Notice that the [labels are present both on the Deployment and on the Pod template](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/). Many reporting tools allocate running Pod cost from Pod labels, not only controller labels. If labels exist only on the parent object, a report may look complete in `kubectl get deployment` but incomplete in cost allocation.

A mature allocation model separates direct workload cost, shared platform cost, and idle cost. Direct workload cost belongs to the team or application that requested capacity. Shared platform cost may be divided by usage, by namespace count, by traffic, or by an agreed platform budget. Idle cost should usually remain visible to the platform team and cluster owners, because idle capacity is often caused by node sizing, autoscaler settings, or conservative request defaults across many teams.

```text
COST ALLOCATION MODEL
====================================================================

┌──────────────────────────────────────────────────────────────────┐
│                       Monthly Cluster Spend                      │
└───────────────────────────────┬──────────────────────────────────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
        ▼                       ▼                        ▼
┌─────────────────┐     ┌─────────────────┐      ┌─────────────────┐
│ Direct Workload │     │ Shared Platform │      │ Idle Capacity   │
│ Cost            │     │ Cost            │      │ Cost            │
│                 │     │                 │      │                 │
│ namespaces      │     │ ingress         │      │ unallocated CPU │
│ controllers     │     │ observability   │      │ unused memory   │
│ team labels     │     │ security agents │      │ empty nodes     │
└────────┬────────┘     └────────┬────────┘      └────────┬────────┘
         │                       │                        │
         ▼                       ▼                        ▼
 team showback report      allocation policy       platform backlog
 right-sizing targets      shared-service review   autoscaler tuning
```

The danger is over-precision. A report that claims a team owes `$12,834.19` may look authoritative while resting on assumptions about idle allocation, shared daemon overhead, or cloud discounts. Early reports should use ranges, trends, and rankings more than exact cents. The goal is to find the first few decisions that change spend meaningfully.

**Stop and think:** Your organization has one shared ingress controller that serves all teams. Should its load balancer and controller Pod cost be charged equally to every namespace, charged by request volume, or held in a platform budget? There is no universal answer. Equal split is simple but unfair to small teams, traffic-based allocation is more accurate but requires trustworthy metrics, and platform budget ownership encourages central optimization but can hide product-level demand.

When labels are missing, do not manually fix reports forever. Enforce the ownership fields where workloads enter the cluster. Kyverno, Gatekeeper, or another [admission controller can require `team`, `environment`, and `cost-center` labels](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/). That policy turns cost reporting from a cleanup task into a deployment contract.

### 4. Right-Size Requests Without Breaking Reliability

Right-sizing is the most visible FinOps practice because many clusters contain workloads with requests far above observed usage. The common story is not negligence. A service was launched under deadline pressure, a developer copied a manifest from a larger service, or an outage led someone to increase CPU and memory during an incident. Months later, the larger request remains even though the workload no longer needs it.

The worked example below shows the reasoning process. The `checkout-api` Deployment currently runs three replicas. Each replica requests `2` CPU and `2Gi` memory, so the scheduler reserves `6` CPU and `6Gi` memory for the service. Prometheus data from the last two weeks shows P95 CPU at `210m`, P99 CPU at `380m`, P95 memory at `420Mi`, and the maximum memory observed during a batch reconciliation at `610Mi`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
  namespace: payments
spec:
  replicas: 3
  selector:
    matchLabels:
      app: checkout-api
  template:
    metadata:
      labels:
        app: checkout-api
        team: payments
        environment: production
    spec:
      containers:
      - name: checkout-api
        image: nginx:1.27
        resources:
          requests:
            cpu: "2"
            memory: "2Gi"
          limits:
            cpu: "4"
            memory: "4Gi"
```

A careless recommendation would set requests exactly to current average usage. That saves money on paper but ignores peaks, deployment overlap, garbage collection, cold starts, and organic growth. A more responsible recommendation uses percentile data and service criticality. For this service, a CPU request around `300m` gives headroom above P95, and a memory request around `640Mi` covers P95 with enough room for normal variance. A memory limit around `1Gi` is reasonable if the team monitors OOMKills after rollout.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
  namespace: payments
spec:
  replicas: 3
  selector:
    matchLabels:
      app: checkout-api
  template:
    metadata:
      labels:
        app: checkout-api
        team: payments
        environment: production
    spec:
      containers:
      - name: checkout-api
        image: nginx:1.27
        resources:
          requests:
            cpu: "300m"
            memory: "640Mi"
          limits:
            memory: "1Gi"
```

The change reduces scheduled CPU from `6` CPU to `900m`, which can allow the autoscaler to pack nodes more efficiently. It does not automatically reduce the cloud bill until nodes consolidate or future scale-ups are avoided. This distinction prevents a common reporting mistake: [request savings are potential savings until the infrastructure layer actually removes or avoids provisioned capacity](https://kubernetes.io/docs/concepts/cluster-administration/node-autoscaling/).

```text
RESOURCE RIGHT-SIZING WORKFLOW
====================================================================

Step 1: MEASURE
────────────────────────────────────────────────────────────────────
  Collect at least one full business cycle of metrics.
  Compare weekdays, weekends, batch windows, release windows, and peaks.

Step 2: ANALYZE
────────────────────────────────────────────────────────────────────
  Compare requests with P95, P99, and maximum usage.
  Flag containers with requests far above P95 or no requests at all.
  Check OOMKills, CPU throttling, latency, and restart history.

Step 3: RECOMMEND
────────────────────────────────────────────────────────────────────
  Set requests from observed usage plus reliability headroom.
  Treat memory more conservatively because exceeding memory can kill Pods.
  Avoid tight CPU limits for latency-sensitive services unless required.

Step 4: APPLY
────────────────────────────────────────────────────────────────────
  Roll out one service or namespace at a time.
  Watch saturation, latency, throttling, restarts, and user-facing errors.
  Keep a rollback manifest or Git revert ready.

Step 5: CONSOLIDATE
────────────────────────────────────────────────────────────────────
  Confirm that autoscaling or node consolidation turns freed requests
  into fewer nodes, smaller nodes, or avoided future scale-outs.
```

**Active check:** Before changing a request, ask what failure mode the original request may have been hiding. Was the service bursty during month-end processing? Did memory grow during large exports? Did CPU spike only during deploy warm-up? A right-sizing change that ignores the workload story can turn a cost win into a reliability incident.

The safest rollout pattern starts with non-production, then one production replica set, then the rest of the workload. [Watch `container_cpu_cfs_throttled_periods_total`, memory working set, restart count, latency percentiles, and HPA behavior](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) if autoscaling is enabled. Cost changes should be reviewed with the same seriousness as performance changes because both alter resource contracts.

```bash
kubectl top pods -n payments
kubectl describe deployment checkout-api -n payments
kubectl get events -n payments --sort-by=.lastTimestamp

k get pods -n payments -l app=checkout-api
k describe pod -n payments -l app=checkout-api
```

Resource right-sizing should not become a one-time cleanup sprint. New releases change behavior, traffic grows, background jobs appear, and libraries change memory profiles. Add a monthly review or automated report that flags workloads where requests exceed recent P95 usage by a chosen threshold. The threshold should create a manageable queue, not shame every team with noisy recommendations.

### 5. Use Spot, Shutdown, and Guardrails as Design Tools

[Spot and preemptible capacity can reduce compute cost dramatically, but they trade price for interruption risk](https://aws.amazon.com/ec2/spot/). The right question is not “Can this run on spot?” The right question is “What happens when this Pod disappears with short notice, and can the system absorb that event without user harm?” Stateless replicas, idempotent workers, CI runners, and retryable batch jobs are usually good candidates. Single-replica databases, cluster control components, and fragile stateful workloads are usually poor candidates.

```text
SPOT INSTANCE DECISION TREE
====================================================================

Is the workload stateless or externally durable?
├── YES ──► Can it handle interruption and retry safely?
│          ├── YES ──► Strong spot candidate
│          │          web replicas, workers, CI jobs, batch processors
│          │
│          └── NO  ──► Fix the workload first
│                     add graceful shutdown, retries, disruption budgets
│
└── NO  ──► Is state replicated and tested under node loss?
           ├── YES ──► Possible spot candidate with strict safeguards
           │          replicated queues, tested search clusters
           │
           └── NO  ──► Keep on on-demand capacity
                      single databases, controllers, critical stores
```

Placement rules should prefer cheaper capacity without making scheduling impossible. A common pattern is to tolerate spot node taints, prefer spot nodes through node affinity, spread replicas across zones, and allow fallback to on-demand when spot capacity is unavailable. This keeps the application available while still biasing normal placement toward lower cost.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: report-worker
  namespace: analytics
  labels:
    app: report-worker
    team: analytics
    spot-eligible: "true"
spec:
  replicas: 6
  selector:
    matchLabels:
      app: report-worker
  template:
    metadata:
      labels:
        app: report-worker
        team: analytics
        spot-eligible: "true"
    spec:
      tolerations:
      - key: "karpenter.sh/capacity-type"
        operator: "Equal"
        value: "spot"
        effect: "NoSchedule"
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 90
            preference:
              matchExpressions:
              - key: karpenter.sh/capacity-type
                operator: In
                values:
                - spot
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: ScheduleAnyway
        labelSelector:
          matchLabels:
            app: report-worker
      containers:
      - name: worker
        image: nginx:1.27
        lifecycle:
          preStop:
            exec:
              command:
              - /bin/sh
              - -c
              - sleep 15
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            memory: "1Gi"
      terminationGracePeriodSeconds: 30
```

Non-production shutdown is another high-leverage design choice. A staging environment that runs only during working hours may not need full compute overnight or on weekends. The platform should still preserve databases, test data, and required shared services, but many Deployments can scale to zero on a schedule. That is usually safer than asking every team to remember manual cleanup.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-down-staging
  namespace: staging
spec:
  schedule: "0 19 * * 1-5"
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: scaler
          containers:
          - name: scaler
            image: bitnami/kubectl:1.35
            command:
            - /bin/sh
            - -c
            - |
              kubectl get deployments -n staging -o name | \
              xargs -r -I{} kubectl scale {} --replicas=0 -n staging
          restartPolicy: OnFailure
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-up-staging
  namespace: staging
spec:
  schedule: "0 8 * * 1-5"
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: scaler
          containers:
          - name: scaler
            image: bitnami/kubectl:1.35
            command:
            - /bin/sh
            - -c
            - |
              kubectl get deployments -n staging -o name | \
              xargs -r -I{} kubectl scale {} --replicas=1 -n staging
          restartPolicy: OnFailure
```

The service account behind a scaler needs [permission only for the target namespace and only for the resources it changes](https://kubernetes.io/docs/reference/access-authn-authz/rbac/). Cost automation should follow the same least-privilege principles as reliability automation. A scheduler that can scale every namespace in the cluster is a cost-control tool and also a production outage risk.

Guardrails make the desired behavior the easy behavior. [ResourceQuotas cap the total requested capacity in a namespace](https://kubernetes.io/docs/concepts/policy/resource-quotas/), [LimitRanges provide defaults for Pods that omit requests](https://kubernetes.io/docs/concepts/policy/limit-range/), and admission policies enforce cost labels. These controls are not substitutes for communication, but they prevent accidental spending patterns from reaching the cluster unnoticed.

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-alpha-budget
  namespace: team-alpha
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    limits.cpu: "40"
    limits.memory: "80Gi"
    persistentvolumeclaims: "10"
    services.loadbalancers: "2"
    pods: "100"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: workload-defaults
  namespace: team-alpha
spec:
  limits:
  - type: Container
    default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
    max:
      cpu: "4"
      memory: "8Gi"
    min:
      cpu: "50m"
      memory: "64Mi"
```

Do not use quotas as a surprise punishment. If a team suddenly cannot deploy during an incident because a quota was set without discussion, the platform has created a reliability problem in the name of cost control. Publish the policy, show the current usage, give teams a path to request exceptions, and review exceptions with both cost and reliability context.

### 6. Investigate Idle Resources and Choose the Next Action

Idle resources often persist because they have no owner, no expiry date, or no monitoring signal. A forgotten load-test namespace can run for months. A bound PersistentVolumeClaim can keep charging after the Pod that used it is gone. A LoadBalancer Service can create a cloud resource that outlives the experiment that needed it. OpenCost helps identify the expensive areas, but Kubernetes inspection still helps verify what action is safe.

```bash
kubectl get namespaces --show-labels
kubectl get svc -A --field-selector spec.type=LoadBalancer
kubectl get pvc -A
kubectl get deployments -A
kubectl get statefulsets -A
```

A good cleanup workflow avoids deleting first and asking later. Start by tagging suspected idle resources, notifying the owner, and setting an expiry window. For non-production resources, an owner may approve deletion quickly. For production resources, the investigation should include recent events, traffic, backups, and dependency checks.

```bash
kubectl annotate namespace loadtest-2026-04 \
  finops.kubedojo.io/review="candidate-idle" \
  finops.kubedojo.io/reviewed-by="platform" \
  --overwrite

kubectl label namespace loadtest-2026-04 \
  environment=temporary \
  --overwrite

kubectl get all -n loadtest-2026-04
kubectl get pvc -n loadtest-2026-04
kubectl get events -n loadtest-2026-04 --sort-by=.lastTimestamp
```

Storage cleanup deserves special caution because [deleting a PVC can delete data, depending on the StorageClass reclaim policy](https://kubernetes.io/docs/concepts/storage/persistent-volumes/). A cost report that shows an expensive volume is a starting point, not proof that the volume is safe to remove. Confirm the owner, application dependency, backup status, and reclaim behavior before deleting anything.

Network cost also deserves deeper investigation. Many teams notice compute waste first because CPU and memory are familiar, but NAT gateways, cross-zone traffic, and load balancers can become major costs. [A namespace with many `LoadBalancer` Services may be better served by a shared Ingress controller or Gateway API implementation](https://kubernetes.io/docs/concepts/services-networking/service/). A workload that transfers large data between zones may need topology-aware placement rather than smaller CPU requests.

```text
FINOPS ACTION SELECTION
====================================================================

Observed signal
│
├── Requests much higher than usage
│   └── Right-size workload, then confirm node consolidation
│
├── High node idle cost
│   └── Review autoscaler, node pools, instance sizes, and bin packing
│
├── Missing owner labels
│   └── Backfill labels, then enforce ownership at admission
│
├── Many LoadBalancer Services
│   └── Consolidate exposure through Ingress or Gateway where appropriate
│
├── Expensive bound volumes
│   └── Verify owner, backup, reclaim policy, and deletion safety
│
└── Non-production runs all night
    └── Schedule scale-down or environment sleep with opt-out rules
```

The senior-level skill is choosing the next action with the best risk-adjusted return. A `70%` CPU request reduction on a critical checkout service may be riskier than deleting a confirmed idle load-test namespace. Moving a worker to spot may be safer than changing memory limits on a latency-sensitive API. FinOps decisions should be ranked by savings, confidence, owner clarity, operational risk, and time to verify.

## Did You Know?

- OpenCost is a CNCF Sandbox project that originated from Kubecost and focuses on Kubernetes-native cost allocation rather than invoice-only cloud reporting.
- A workload can show large request savings before the cloud bill drops, because actual savings usually require node consolidation, smaller nodes, or avoided future scale-out.
- CPU and memory behave differently for reliability: CPU pressure often causes latency or throttling, while memory pressure can terminate a container with an OOMKill.
- Label quality is a FinOps dependency; without consistent ownership labels, reports drift toward shared buckets that are difficult to assign or improve.

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Treating OpenCost as a finance-only dashboard | Engineers cannot improve costs they never see, and finance cannot infer workload intent from invoices alone. | Review cost reports with platform, application, and finance stakeholders together. |
| Right-sizing from averages | Averages hide peaks, batch windows, deploy warm-up, and memory growth patterns. | Use P95, P99, maximum usage, and reliability history before changing requests. |
| Claiming request reduction as immediate savings | The cloud bill does not fall until provisioned capacity is removed or future capacity is avoided. | Pair right-sizing with autoscaler consolidation and node pool review. |
| Missing labels on Pod templates | Cost reports by team or cost center collapse into unknown buckets even if Deployments look labeled. | Enforce required labels at admission and apply them to Pod templates. |
| Moving fragile workloads to spot | Interruptions can cause outages, data loss, or slow recovery if workloads are not designed for eviction. | Start with stateless, retryable, horizontally replicated workloads. |
| Using quotas without communication | Teams may discover limits during urgent deployments, turning cost control into a delivery blocker. | Publish quotas, show current usage, and define an exception process. |
| Deleting idle-looking storage too quickly | Bound volumes may contain data needed for recovery, audits, or paused environments. | Verify owner, backups, reclaim policy, and dependencies before deletion. |
| Ignoring network and load balancer cost | Compute tuning cannot fix expensive exposure patterns or cross-zone traffic. | Include Services, Ingress, NAT, and topology in cost reviews. |

## Quiz

### Question 1

Your team sees a namespace requesting `16` CPU while OpenCost and Prometheus show P95 usage around `3` CPU for the last two weeks. The application owner wants to cut requests to `3` CPU immediately across all replicas. What should you recommend, and what evidence would you check before approving the change?

<details>
<summary>Show Answer</summary>

Do not cut directly to the observed P95 without context. Recommend a staged right-sizing change that adds reliability headroom above P95, then roll it out gradually while monitoring latency, CPU throttling, restarts, and HPA behavior. Check whether the two-week window includes normal peak traffic, batch jobs, release events, and business-cycle spikes.

The key reasoning is that requests influence scheduling and capacity planning, but the application still needs room for bursts and growth. A safer plan might reduce requests significantly, observe production behavior, and then continue tuning. The change should also be paired with node consolidation, otherwise the cloud bill may not drop immediately.

</details>

### Question 2

OpenCost reports a large `team=""` or unknown-label bucket when aggregating by `label:team`, but namespace-level allocation looks reasonable. A manager says the dashboard is broken. How do you debug the issue, and what platform control would prevent recurrence?

<details>
<summary>Show Answer</summary>

First inspect whether the running Pods have the expected `team` label on their Pod templates, not only on parent Deployments or namespaces. Cost allocation often uses Pod labels because Pods are the running units consuming resources. If labels are missing, the dashboard is likely revealing an ownership metadata gap rather than failing.

To prevent recurrence, enforce required labels with an admission policy using Kyverno, Gatekeeper, or a similar controller. Backfill existing workloads, then make `team`, `environment`, and `cost-center` part of the deployment contract.

</details>

### Question 3

A platform engineer reduces CPU requests for several services and reports a large monthly savings estimate. At the end of the month, the cloud bill barely changes. What likely happened, and what should the team inspect next?

<details>
<summary>Show Answer</summary>

The request reduction created potential savings but did not necessarily remove provisioned cloud resources. If the same nodes kept running, the cloud provider continued charging for them. Kubernetes may have more schedulable space, but the bill changes only when nodes are consolidated, smaller instances are used, or future scale-outs are avoided.

The team should inspect autoscaler behavior, node utilization, node pool instance sizes, Karpenter consolidation settings, PodDisruptionBudgets, and scheduling constraints that prevent packing. They should connect workload right-sizing to infrastructure consolidation.

</details>

### Question 4

A batch processing Deployment is stateless, retries jobs safely, and has six replicas. The team wants to save money with spot capacity, but they also require reports to complete by morning. What Kubernetes placement and reliability controls would you design?

<details>
<summary>Show Answer</summary>

Prefer spot capacity rather than requiring it absolutely, so the workload can fall back to on-demand capacity when spot is unavailable. Add tolerations and preferred node affinity for spot nodes, use topology spread constraints across zones, and ensure the application handles graceful termination. Consider a PodDisruptionBudget if too many simultaneous interruptions would break the completion target.

The design should also include observability for job retry rate, completion latency, and interruption frequency. Spot is appropriate because the workload is stateless and retryable, but the morning completion requirement means the system needs fallback and monitoring.

</details>

### Question 5

A namespace has ten `LoadBalancer` Services for small internal tools. Compute usage is low, but the monthly cost report for the namespace is still high. What would you investigate, and what architectural change might reduce cost?

<details>
<summary>Show Answer</summary>

Investigate whether each Service provisions a separate cloud load balancer and whether those tools could share an Ingress controller or Gateway. Load balancers can create recurring base charges even when backend Pods are small. Also check whether the tools are internal-only and could use private exposure patterns.

A likely improvement is to consolidate routing through one shared Ingress or Gateway where security and ownership requirements allow it. Add a ResourceQuota limit for `services.loadbalancers` so accidental proliferation is caught early.

</details>

### Question 6

A storage report shows several expensive bound PVCs in a namespace where no Pods are currently running. A teammate suggests deleting them to save money before the next billing cycle. What should you do first?

<details>
<summary>Show Answer</summary>

Do not delete the PVCs immediately. Verify the owner, application dependency, backup status, StorageClass reclaim policy, and whether the namespace is paused rather than abandoned. Bound volumes may contain state needed for recovery, audits, or future restart.

A safer workflow is to annotate the resources as cleanup candidates, notify the owning team, set an expiry window, and delete only after approval or policy-based timeout. Storage cleanup can save money, but it has higher data-loss risk than scaling down stateless Deployments.

</details>

### Question 7

A new ResourceQuota blocks a production team from deploying an emergency hotfix because their namespace already exceeds the CPU request cap. The quota was added during a cost-control initiative. How would you correct the rollout process while preserving cost guardrails?

<details>
<summary>Show Answer</summary>

The issue is not that quotas are bad; it is that the quota was introduced without an operational exception path and enough visibility. Correct the process by publishing quota values, showing each team current usage, giving advance notice, and defining a temporary override or escalation path for incidents. Review whether the quota should differ by environment or service criticality.

Preserve the guardrail by keeping quotas in place after adjustment, but make them part of a transparent platform contract. Cost controls should prevent accidental waste without blocking urgent reliability work.

</details>

## Hands-On Exercise

### Objective

Install OpenCost in a local Kubernetes cluster, create two teams with different resource profiles, identify waste, and apply guardrails that make cost ownership visible. The exercise is designed as a small simulation: the local cluster will not produce a realistic cloud invoice, but it will demonstrate allocation mechanics and right-sizing reasoning.

### Environment Setup

Use a local cluster such as kind. The commands below create the cluster, install metrics-server, install Prometheus, and install OpenCost. Keep the setup close to the module because FinOps tools are easier to understand when you can inspect the objects they read.

```bash
kind create cluster --name finops-lab

kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update

helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --create-namespace \
  --set server.persistentVolume.enabled=false \
  --set alertmanager.enabled=false

helm upgrade --install opencost opencost/opencost \
  --namespace opencost \
  --create-namespace \
  --set opencost.prometheus.internal.enabled=false \
  --set opencost.prometheus.external.url="http://prometheus-server.monitoring.svc:80" \
  --set opencost.ui.enabled=true
```

Verify the installation before adding workloads. If Pods are still starting, wait and check again rather than debugging cost reports with incomplete dependencies.

```bash
kubectl get pods -n kube-system
kubectl get pods -n monitoring
kubectl get pods -n opencost
kubectl get svc -n opencost
```

You can define the short alias after the base setup if you want the later inspection commands to match common platform-engineering practice.

```bash
alias k=kubectl
```

### Task 1: Create Team Namespaces and Guardrails

Create two namespaces that represent two application teams. Team Alpha receives a quota and default requests so you can observe guardrail behavior. Team Beta starts with fewer controls so you can compare how workloads appear in reports.

```bash
kubectl create namespace team-alpha
kubectl create namespace team-beta

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-budget
  namespace: team-alpha
spec:
  hard:
    requests.cpu: "4"
    requests.memory: "4Gi"
    limits.cpu: "8"
    limits.memory: "8Gi"
    pods: "20"
    services.loadbalancers: "1"
EOF

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: LimitRange
metadata:
  name: workload-defaults
  namespace: team-alpha
spec:
  limits:
  - type: Container
    default:
      cpu: "200m"
      memory: "256Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
EOF
```

Inspect the objects and make sure they exist before moving on.

```bash
k describe resourcequota compute-budget -n team-alpha
k describe limitrange workload-defaults -n team-alpha
```

### Task 2: Deploy a Wasteful Workload and an Efficient Workload

Deploy two NGINX workloads. Both are intentionally simple so that resource differences are easy to see. The wasteful workload requests far more CPU and memory than an idle NGINX container normally uses, while the efficient workload uses smaller requests.

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wasteful-api
  namespace: team-alpha
  labels:
    app: wasteful-api
    team: alpha
    environment: lab
    cost-center: engineering
spec:
  replicas: 3
  selector:
    matchLabels:
      app: wasteful-api
  template:
    metadata:
      labels:
        app: wasteful-api
        team: alpha
        environment: lab
        cost-center: engineering
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            memory: "1Gi"
EOF

kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: efficient-api
  namespace: team-beta
  labels:
    app: efficient-api
    team: beta
    environment: lab
    cost-center: engineering
spec:
  replicas: 3
  selector:
    matchLabels:
      app: efficient-api
  template:
    metadata:
      labels:
        app: efficient-api
        team: beta
        environment: lab
        cost-center: engineering
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
          limits:
            memory: "128Mi"
EOF
```

Wait for Pods to run, then compare requested resources with live usage. The exact usage numbers will vary by environment, but the relationship should be clear: both applications do similar work, while one reserves far more capacity.

```bash
k rollout status deployment/wasteful-api -n team-alpha
k rollout status deployment/efficient-api -n team-beta

k top pods -n team-alpha
k top pods -n team-beta

k get pods -n team-alpha -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory
k get pods -n team-beta -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory
```

### Task 3: Query OpenCost by Namespace and Team Label

Open the OpenCost UI and query the API. In a local kind cluster, pricing may be approximate, but namespace and label grouping still demonstrate how allocation works. The important learning goal is to connect labels, requests, and reports.

```bash
kubectl port-forward -n opencost svc/opencost 9090:9090
```

Open `http://127.0.0.1:9090` while the port-forward is active. In another terminal, run the API port-forward and query the allocation endpoints.

```bash
kubectl port-forward -n opencost svc/opencost 9003:9003
```

```bash
curl -s "http://127.0.0.1:9003/allocation/compute?window=1h&aggregate=namespace"

curl -s "http://127.0.0.1:9003/allocation/compute?window=1h&aggregate=label:team"
```

Write down which namespace appears more expensive and why. The answer should involve requested capacity and allocation, not just current CPU usage. If the label report has missing buckets, inspect the Pod template labels and compare them with the Deployment metadata labels.

```bash
k get pods -A --show-labels
k get deployment wasteful-api -n team-alpha -o yaml
k get deployment efficient-api -n team-beta -o yaml
```

### Task 4: Test Quota Enforcement

Try to deploy a workload that exceeds Team Alpha's quota. The Deployment object may be created, but [the namespace should not be able to admit all requested Pods because the quota limits total requests](https://kubernetes.io/docs/concepts/policy/resource-quotas/).

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quota-buster
  namespace: team-alpha
  labels:
    app: quota-buster
    team: alpha
    environment: lab
spec:
  replicas: 10
  selector:
    matchLabels:
      app: quota-buster
  template:
    metadata:
      labels:
        app: quota-buster
        team: alpha
        environment: lab
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            memory: "1Gi"
EOF
```

Inspect the quota and events. This is the moment where cost guardrails become operationally visible. The API server enforces the quota before the scheduler can place every Pod.

```bash
k get pods -n team-alpha
k describe resourcequota compute-budget -n team-alpha
k get events -n team-alpha --sort-by=.lastTimestamp
```

### Task 5: Apply a Right-Sizing Change

Patch the wasteful workload to use smaller requests, then compare the requested capacity again. This lab does not guarantee immediate cloud savings because kind is local, but it demonstrates the Kubernetes-side change that would allow a real autoscaler to pack workloads more efficiently.

```bash
kubectl patch deployment wasteful-api -n team-alpha --type='json' \
  -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}
  ]'

k rollout status deployment/wasteful-api -n team-alpha

k get pods -n team-alpha -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory
k top pods -n team-alpha
```

After the rollout, explain what changed and what did not. The Pod requests changed. The Deployment rolled out a new ReplicaSet. The local cluster cost may not change because there is no real cloud node bill to reduce. In a production cluster, the next question would be whether autoscaling or consolidation removes provisioned capacity.

### Task 6: Identify Idle and Expensive Resource Patterns

Create a temporary LoadBalancer Service and a bound-looking PVC so you can practice inspection. In a local cluster, the Service may remain pending because there is no cloud load balancer integration, but the object still demonstrates the Kubernetes signal that would create cost in a cloud environment.

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: expensive-entrypoint
  namespace: team-beta
  labels:
    team: beta
    environment: lab
spec:
  type: LoadBalancer
  selector:
    app: efficient-api
  ports:
  - name: http
    port: 80
    targetPort: 80
EOF

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: old-test-data
  namespace: team-beta
  labels:
    team: beta
    environment: lab
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
EOF
```

Inspect the resources and decide what evidence you would need before deleting them in a real cluster.

```bash
k get svc -A --field-selector spec.type=LoadBalancer
k get pvc -A
k describe pvc old-test-data -n team-beta
```

### Success Criteria

- [ ] OpenCost Pods are running in the `opencost` namespace and the UI is reachable through `http://127.0.0.1:9090`.
- [ ] Prometheus is running in the `monitoring` namespace and OpenCost is configured to use it as an external Prometheus source.
- [ ] Team Alpha and Team Beta namespaces exist with visible ownership labels on workload Pod templates.
- [ ] The wasteful workload initially requests much more CPU and memory than the efficient workload.
- [ ] The quota in Team Alpha prevents all `quota-buster` replicas from being admitted.
- [ ] The right-sizing patch reduces the wasteful workload's requested CPU and memory.
- [ ] You can explain why request reduction is not the same as immediate cloud-bill reduction.
- [ ] You can identify why a LoadBalancer Service or orphaned PVC may require separate cost review.

### Cleanup

Delete the lab cluster when finished.

```bash
kind delete cluster --name finops-lab
```

## Next Module

You have completed the Scaling and Reliability Toolkit. Continue to the [Platforms Toolkit](/platform/toolkits/infrastructure-networking/platforms/) to learn how internal developer platforms connect reliability, self-service, governance, and cost-aware operations.

Related modules worth revisiting are [Module 6.1: Karpenter](../module-6.1-karpenter/) for node provisioning and consolidation, and [Module 6.3: Velero](../module-6.3-velero/) for backup decisions that affect storage cost and recovery risk.

## Sources

- [kubernetes.io: manage resources containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) — The Kubernetes resource management documentation states that the scheduler checks summed container requests against node capacity and can reject placement even when actual usage is low.
- [github.com: opencost](https://github.com/opencost/opencost) — The OpenCost README describes Kubernetes workload and cloud cost monitoring, resource allocation, and allocation queries.
- [kubernetes.io: rbac](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) — Kubernetes RBAC documentation provides the authoritative access-control model for controlling who can read cluster resources and operational data.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment documentation describes the Pod template and selector/label relationship used for Pods managed by a Deployment.
- [kubernetes.io: validating admission policy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/) — The ValidatingAdmissionPolicy documentation includes label-requirement examples and explains admission-time validation.
- [kubernetes.io: node autoscaling](https://kubernetes.io/docs/concepts/cluster-administration/node-autoscaling/) — Kubernetes node autoscaling documentation explains provisioning and consolidation around scheduling capacity rather than billing changes from workload requests alone.
- [aws.amazon.com: spot](https://aws.amazon.com/ec2/spot/) — The AWS EC2 Spot page directly describes discounted spare capacity and interruption characteristics.
- [kubernetes.io: resource quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/) — The Kubernetes ResourceQuota documentation lists compute quotas and object-count quotas including services.loadbalancers and persistentvolumeclaims.
- [kubernetes.io: limit range](https://kubernetes.io/docs/concepts/policy/limit-range/) — The LimitRange documentation directly describes default, minimum, and maximum resource constraints for namespace objects.
- [kubernetes.io: persistent volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) — The PersistentVolume documentation explains Delete and Retain reclaim policies and how Delete can remove the associated external storage asset.
- [kubernetes.io: service](https://kubernetes.io/docs/concepts/services-networking/service/) — The Kubernetes Service documentation describes type LoadBalancer and cloud-provider load balancer provisioning.
- [OpenCost Advances to CNCF Incubating Status](https://www.cncf.io/blog/2024/10/31/opencost-advances-to-the-cncf-incubator/) — Provides current CNCF project status and historical context for OpenCost's origins.
