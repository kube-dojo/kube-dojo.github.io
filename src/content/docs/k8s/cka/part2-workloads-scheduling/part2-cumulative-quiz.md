---
citations_verified: true
title: "Part 2 Cumulative Quiz: Workloads & Scheduling"
sidebar:
  order: 11
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45-60 minutes
>
> **Prerequisites**: Module 2.1 Pods Deep-Dive, Module 2.2 Deployments & ReplicaSets, Module 2.3 DaemonSets & StatefulSets, Module 2.4 Jobs & CronJobs, Module 2.5 Resource Management, Module 2.6 Scheduling, Module 2.7 ConfigMaps & Secrets
>
> **Kubernetes Version**: 1.35+

---

## Learning Outcomes

- **Evaluate** multi-container pod architectures, lifecycle hooks, and container probe configurations to ensure dependable application startup, health detection, and graceful process termination.
- **Manage** declarative application update strategies, revision histories, and rollback operations using Deployments and ReplicaSets to maintain service availability during rolling deployments.
- **Configure** specialized workload controllers including DaemonSets for cluster-wide node daemons and StatefulSets paired with headless Services for ordered deployment, unique network identities, and persistent storage bindings.
- **Implement** batch processing workloads and scheduled automation using Jobs and CronJobs with explicit parallelism limits, backoff retry policies, and concurrency control safeguards.
- **Optimize** workload scheduling decisions and configuration decoupling across worker nodes using resource requests, limits, QoS classes, node affinity, taints, tolerations, ConfigMaps, and Secrets.

---

## Why This Module Matters

Workloads and scheduling represent the core operational engine of Kubernetes, establishing how containerized software is instantiated, supervised, scaled, and placed across worker infrastructure. In the Certified Kubernetes Administrator examination, workloads and scheduling account for a major portion of practical scoring weight. Candidates often memorize basic manifest structures, yet struggle when multiple controllers interact under resource pressure or when rolling updates behave unexpectedly. Mastering Part 2 requires synthesizing pod lifecycle mechanics, declarative controller abstractions, distributed state guarantees, batch execution paradigms, resource enforcement boundaries, and scheduler scoring pipelines into an integrated mental model.

Hypothetical scenario: an operations engineer deployed an e-commerce catalog service into a staging cluster using a Deployment with default rolling update settings, but accidentally misconfigured the readiness probe endpoint to a non-existent path. When the engineer pushed an image update, the Deployment controller spawned a new replica that never achieved Ready status, yet the existing pods were prematurely terminated because maxUnavailable was miscalculated against a single-replica baseline. Traffic immediately failed across all frontend ingress routes because zero ready endpoints existed to satisfy customer requests. Had the engineer established automated rollback gates and validated readiness probe semantics beforehand, the control plane would have halted the rollout without dropping live traffic.

Operating production clusters requires diagnosing subtle behavioral boundaries rather than relying on superficial command syntax. A failing pod may indicate an application crash, an unfulfilled scheduling predicate, a missing ConfigMap key, or an immediate memory termination executed by the operating system kernel. When you understand how the kube-scheduler filters and scores nodes, and how the kube-controller-manager reconciles child ReplicaSets, troubleshooting shifts from anxious speculation into methodical root-cause isolation. This diagnostic discipline ensures that you select safe, targeted remediation steps during real incidents.

The Certified Kubernetes Administrator examination evaluates your ability to resolve multi-component failure scenarios under strict time constraints. You will encounter questions requiring rapid manifest generation using client-side dry runs, surgical patching of controller specifications, precision tuning of resource constraints, and node placement debugging. Developing automatic recall for declarative workload primitives allows you to focus mental energy on architectural constraints rather than basic tool navigation.

Senior infrastructure practitioners treat Kubernetes workloads as self-healing components in an asynchronous, eventual-consistency state machine. Controllers continuously compare observed infrastructure state with declared intent, driving convergence through idempotent control loops. Cultivating a deep appreciation for controller reconciliation, probe mechanics, and scheduling topologies empowers you to design resilient platforms capable of withstanding unexpected infrastructure failures without service degradation.

---

## Core Content: Pod Lifecycle and Resilient Multi-Container Patterns

The Pod represents the atomic unit of deployment and scheduling in Kubernetes, encapsulating one or more tightly coupled containers that share a network namespace and can share storage volumes. Process namespaces are shared only when configured. When a pod is submitted to the API server, it enters the Pending phase while the kube-scheduler identifies a suitable node. Once scheduled, the kubelet pulls images and starts regular init containers sequentially to completion before application containers. A sidecar defined in `initContainers` with `restartPolicy: Always` stays running; the kubelet starts subsequent containers once that sidecar has started. The pod transitions to Running once at least one application container starts successfully, remaining in this phase until all containers complete or terminate.

Multi-container pod architectures enable modular separation of concerns by co-locating supporting helper processes alongside the primary application engine. Common design patterns include sidecars that forward application logs or manage proxy communication, ambassador containers that abstract remote service endpoints, and adapter containers that normalize heterogeneous metrics into standardized formats. Co-located containers communicate over localhost using standard inter-process communication or TCP/UDP sockets, and share filesystem data through mounted emptyDir or persistent volumes. Enabling shared process namespaces allows auxiliary containers to inspect neighboring process tables, simplifying diagnostic sidecar implementations.

Container lifecycle health management relies on three distinct probe mechanisms configured within container specifications. Startup probes verify whether slow-starting applications have completed initialization, suppressing liveness and readiness checks until the startup probe succeeds to prevent premature container restarts. Liveness probes detect unrecoverable process deadlocks or internal application crashes; when a liveness probe fails repeatedly beyond its failureThreshold, kubelet terminates the container process and initiates a restart according to the pod restartPolicy. Readiness probes determine whether a container is prepared to serve incoming network requests; failing readiness probes cause the EndpointSlice controller to remove the container IP from active Service backends without restarting the container.

When application containers encounter repeated runtime failures, the kubelet enforces an exponential restart backoff delay to protect worker nodes from continuous process thrashing. The restart delay begins at ten seconds and doubles progressively through twenty, forty, eighty, and one hundred sixty seconds until reaching an upper ceiling of three hundred seconds. During this delayed period, the pod status reports CrashLoopBackOff within kubectl command output, signalling to operators that container exit codes, termination logs, and historical events must be analyzed to identify root causes.

Troubleshooting complex multi-container pods often requires inspecting active processes without restarting existing containers or mutating production manifest specifications. Administrators can add an ephemeral container with `kubectl debug` to join the pod network namespace. It sees other containers' processes only if the pod enables `shareProcessNamespace` or the debug command requests process sharing with a target container, subject to runtime support. This capability helps examine distroless or hardened images that omit shells and diagnostic utilities.

Graceful container termination protects in-flight transactions and preserves data integrity when workloads scale down or undergo scheduled maintenance. When the API server accepts a pod deletion, it sets `deletionTimestamp` and starts the termination grace period. The kubelet begins shutdown by running any `preStop` hook before sending SIGTERM to the container process. EndpointSlice updates happen concurrently with shutdown, so the application must handle traffic that can still arrive during the hook or after SIGTERM. If processes remain after the grace period, kubelet sends SIGKILL.

---

## Core Content: Declarative Rollouts and ReplicaSet Supervision

The Deployment controller provides declarative lifecycle management for stateless applications, orchestrating automated rolling updates, canary releases, dynamic scaling, and instantaneous rollbacks across worker nodes. A Deployment does not create or supervise individual Pod objects directly; instead, it creates and manages intermediate ReplicaSet resources distinguished by unique pod-template-hash identifiers. When an administrator updates a Deployment specification, such as altering a container image or modifying environment variables, the Deployment controller automatically constructs a new ReplicaSet reflecting the desired configuration and orchestrates an incremental transition of active replicas.

Rolling update behavior is governed by two critical parameters declared within the strategy.rollingUpdate block: maxSurge and maxUnavailable. The maxSurge parameter defines the maximum number of additional Pods that can be provisioned above the declared replica count during a rollout, expressed as an absolute integer or a percentage. The maxUnavailable parameter specifies the maximum number of Pods that can be unavailable during the update process relative to the desired replica target. Tuning these values balances infrastructure resource consumption against application availability; setting maxUnavailable to zero guarantees that full baseline capacity remains operational throughout the entire update window.

**Pause and predict:** A Deployment configured with 3 replicas specifies a rolling update strategy with maxUnavailable set to 0 and maxSurge set to 1. When an administrator updates the container image, what workload capacity remains available throughout the rollout surge, and which command shows the new ReplicaSet?

<details>
<summary>Check your prediction</summary>

During the surge, 100% of the original desired capacity (all 3 original Pods) remains fully available because maxUnavailable is 0, while the Deployment controller creates 1 additional Pod under a new ReplicaSet, bringing total running Pods temporarily to 4. To identify the newly generated ReplicaSet, run `kubectl get rs` or `kubectl describe deployment <deployment-name>` to view the active ReplicaSets and their revision annotations.

</details>

Observing rollout transitions directly through controller event streams prevents premature service degradation during zero-downtime updates in production clusters. Infrastructure engineers monitor replica stabilization before terminating legacy revision assets to guarantee seamless customer traffic migration across application version boundaries.

Managing application update histories requires disciplined inspection of revision metadata and rapid rollback execution when defects emerge in production environments. Running kubectl rollout status allows operators to track container creation and readiness transitions synchronously from the command line. The controller preserves historical ReplicaSet manifests up to the limit defined by revisionHistoryLimit, enabling operators to inspect prior configurations with kubectl rollout history. If a new release exhibits runtime faults, executing kubectl rollout undo reverts the Deployment to the preceding healthy revision instantly by scaling down the defective ReplicaSet and scaling up the historical replica specification.

Deployment controllers enforce a rollout timeout boundary through the progressDeadlineSeconds field, which defaults to six hundred seconds in standard configurations. If a rolling update fails to make measurable progress toward completion within this duration, such as when container images cannot be pulled or readiness probes fail perpetually, the controller marks the Progressing condition as False with a ProgressDeadlineExceeded reason. While the controller does not automatically revert the failed rollout, setting this condition enables external automation and alerting systems to trigger automated remediation workflows.

Pausing and resuming rollouts provides granular administrative control during complex multi-step deployments or canary verifications. Executing kubectl rollout pause suspends the active rollout loop, allowing engineers to apply multiple configuration adjustments, such as updating resource limits and environment variables simultaneously, without triggering unnecessary intermediate ReplicaSet transitions. Once all modifications are declared, running kubectl rollout resume instructs the controller to evaluate the accumulated differences and initiate a single, consolidated rolling update sequence.

Declarative canary releases can also use two Deployments behind one Service. Give the stable and canary pod templates a shared label that the Service selects, plus distinct version labels that make each Deployment's own selector narrower. Identical Deployment selectors can cause their ReplicaSets to compete over the same pods. Changing the two replica counts adjusts the approximate share of ready endpoints, although it does not guarantee an exact traffic percentage.

---

## Core Content: Specialized Workload Management with StatefulSets and DaemonSets

Stateful applications require operational guarantees that stateless Deployments cannot provide, including stable network hostnames, ordered lifecycle sequences, and dedicated persistent storage bindings. The StatefulSet controller addresses these requirements by assigning each pod an immutable, zero-based ordinal index ranging from zero up to the replica count minus one. In default OrderedReady mode, the controller launches pods sequentially, waiting for pod zero to achieve Ready status before initializing pod one, and reverses this sequence during scaling down operations. This predictable ordering prevents data corruption in distributed quorum systems such as ZooKeeper, Cassandra, and replicated database clusters.

Network identity for StatefulSet pods is established through a mandatory governing headless Service configured with clusterIP set to None. CoreDNS utilizes this headless Service declaration to generate individual, discoverable DNS A-records and SRV records for every ordinal pod within the cluster domain. Each replica receives a fully qualified domain name structured as pod-name dot service-name dot namespace dot svc dot cluster dot local, ensuring that peer replicas can reliably locate one another regardless of pod restarts or IP address reassignments. Without a governing headless Service, StatefulSet instances lose direct DNS discoverability.

Persistent storage in StatefulSets is automated through `volumeClaimTemplates`, which create a dedicated PersistentVolumeClaim for each ordinal pod. A claim's name follows `{volumeClaimTemplate.metadata.name}-{pod-name}`: a template named `data` produces `data-web-0` for pod `web-0`. A bound claim provides stable storage across pod rescheduling. By default, claims are retained when the StatefulSet scales down or is deleted; an explicit PVC retention policy can change that behavior.

```text
+-------------------------------------------------------------------------+
|                  StatefulSet Identity and Storage Topology              |
|                                                                         |
|  StatefulSet: "database" (replicas: 2, claim template: "data")           |
|  Governing Service: "db-headless"                                        |
|                                                                         |
|  +--------------------------------+   +-------------------------------+ |
|  | Pod: database-0                |   | Pod: database-1               | |
|  | Hostname: database-0           |   | Hostname: database-1          | |
|  | DNS: database-0.db-headless... |   | DNS: database-1.db-headless.. | |
|  +---------------+----------------+   +---------------+---------------+ |
|                  |                                    |                 |
|                  v                                    v                 |
|  +--------------------------------+   +-------------------------------+ |
|  | PVC: data-database-0           |   | PVC: data-database-1          | |
|  | (Retained on scale-down)       |   | (Retained on scale-down)      | |
|  +--------------------------------+   +-------------------------------+ |
+-------------------------------------------------------------------------+
```

Advanced StatefulSet management supports partition-based rolling updates declared under updateStrategy.rollingUpdate.partition within the specification. When a partition ordinal is configured, the StatefulSet controller updates only those replicas whose ordinal index is greater than or equal to the partition value, leaving all lower ordinals running the legacy version. This capability enables staged database schema upgrades and fine-grained canary testing where a single replica verifies application stability before updates proceed across the entire cluster.

In operational scenarios where strict startup ordering is unnecessary, operators configure podManagementPolicy as Parallel rather than the default OrderedReady setting. In Parallel mode, the StatefulSet controller creates or deletes all replica pods concurrently, eliminating sequential initialization delays. This pattern is particularly advantageous for distributed caching clusters, such as Redis or Cassandra rings, where individual nodes discover peers through headless DNS but do not require strict ordinal initialization.

DaemonSets guarantee that a designated pod replica executes continuously across every eligible worker node within the Kubernetes cluster. Platform engineers deploy DaemonSets for node-level infrastructure services, including container network interface agents like Calico or Cilium, host metric exporters like Prometheus node-exporter, and log forwarding agents like Fluentbit. Unlike legacy implementations that relied on custom controller scheduling, modern DaemonSet controllers leverage the default kube-scheduler, respecting node selectors, node affinity rules, taints, and tolerations configured on the pod template.

Updating DaemonSet workloads follows two distinct operational strategies declared in the updateStrategy field. The default RollingUpdate strategy automatically deletes and replaces old pods one node at a time, ensuring continuous background daemon coverage without overwhelming cluster compute capacity. Alternatively, the OnDelete strategy suspends automated updates, replacing pods on a node only when the administrator explicitly terminates the legacy container manually. This manual control proves valuable when rolling out kernel-sensitive network agents across heterogeneous physical infrastructure.

---

## Core Content: Batch Execution and Scheduled Workflows with Jobs and CronJobs

Batch processing workloads differ fundamentally from continuous background services because batch containers are designed to execute finite tasks to completion before terminating cleanly. The Job controller supervises run-to-completion tasks, instantiating one or more pods and guaranteeing that a specified number of successful completions occur before the workload is marked finished. Jobs enforce a strict restartPolicy rule: pod templates must configure restartPolicy as OnFailure or Never, because the default Always policy is incompatible with finite batch execution.

Parallel execution and workload completion targets are controlled through the completions and parallelism fields in the Job specification. Non-parallel jobs execute a single pod until it succeeds, whereas parallel jobs with fixed completion counts run multiple pods concurrently until the total completions threshold is reached. If a batch task encounters runtime errors, the Job controller retries execution according to backoffLimit, applying exponential backoff delays between attempts. If the total number of pod failures exceeds the backoffLimit, or if execution time surpasses activeDeadlineSeconds, the controller terminates active pods and marks the Job permanently failed.

The CronJob controller extends batch capabilities by scheduling Job executions based on standard cron expressions formatted across five fields: minute, hour, day of month, month, and day of week. The controller watches active CronJob declarations, evaluating the cron schedule against cluster time to construct child Job objects automatically at designated intervals. Administrators configure successfulJobsHistoryLimit and failedJobsHistoryLimit to govern how many completed and terminated job records remain visible in the API datastore, preventing etcd metadata bloat from recurring executions.

**Pause and predict:** A CronJob is configured with a schedule of * * * * * and concurrencyPolicy set to Forbid. If a scheduled execution takes ninety seconds to finish and the next scheduled one-minute trigger occurs while the previous Job is still running, does the CronJob controller launch a second Job instance?

<details>
<summary>Check your prediction</summary>

No, a second Job will not start. Under concurrencyPolicy: Forbid, the CronJob controller inspects existing active jobs created by the CronJob specification; if any previous job is still running when the schedule triggers, the controller skips the current execution and logs a missed schedule event rather than launching concurrent workloads.

</details>

Selecting the appropriate concurrency safeguard protects backend databases and downstream compute nodes from cascading resource starvation caused by overlapping batch executions. Administrators examine schedule execution intervals against realistic job completion durations to establish predictable pipeline throughput without triggering premature execution suppressions.

Concurrency policies dictate how the CronJob controller handles schedule triggers when preceding batch instances remain active. The default Allow policy permits concurrent job executions, which can saturate node resources if successive runs pile up behind slow external services. The Forbid policy suppresses new job creation while an earlier instance runs, protecting downstream databases from duplicate batch processing. The Replace policy terminates the currently executing job immediately and spawns a fresh instance, which is ideal for time-sensitive cache refreshes where obsolete calculations should be discarded in favor of current data.

Modern Kubernetes releases provide Indexed completion mode, configured by setting completionMode to Indexed within the Job specification. In this mode, each pod receives an immutable completion index ranging from zero up to completions minus one, exposed inside the container environment through the JOB_COMPLETION_INDEX variable. This feature enables distributed computing frameworks to partition static data sets or compute tasks across parallel workers without requiring external coordination services.

Administrators also manage job execution queues by leveraging the suspend field within the Job specification. Setting suspend to true allows platform operators or custom admission controllers to queue batch workloads in the API server without dispatching pods to the scheduler. Once compute capacity becomes available, updating suspend to false instructs the Job controller to begin scheduling worker pods immediately.

Handling missed execution windows requires configuring startingDeadlineSeconds within the CronJob specification. If a cluster control plane outage or network partition prevents the CronJob controller from executing during its scheduled window, startingDeadlineSeconds establishes the maximum allowable delay for initiating late jobs. If the controller discovers more than one hundred missed schedule intervals and startingDeadlineSeconds is unconfigured, the CronJob controller ceases scheduling future jobs entirely, logging an error that requires administrative intervention to reset.

---

## Core Content: Resource Allocation, Throttling, and Quality of Service

Resource management in Kubernetes allows cluster operators to control how compute capacity is divided, allocated, and enforced across competing containerized workloads. Container specifications declare compute constraints using requests and limits for CPU and memory resources. Resource requests represent the minimum compute capacity guaranteed to a container, functioning as the primary metric used by the kube-scheduler during node filtering. Resource limits define the absolute ceiling of compute consumption permitted to a container during runtime execution, enforced directly by the host operating system kernel.

CPU and memory resources exhibit fundamentally different behavioral characteristics under contention due to the distinction between compressible and non-compressible resources. CPU is compressible: if a container attempts to consume more CPU cycles than its declared limit, the Linux Completely Fair Scheduler throttles the container process using CFS quotas, slowing execution speed without terminating the container. Conversely, memory is non-compressible: if a container process exceeds its memory limit, the Linux kernel Out-Of-Memory killer intervenes immediately, terminating the misbehaving process with an exit status of 137 and forcing a container restart.

Kubernetes automatically categorizes every pod into one of three Quality of Service classes based upon the relationship between container requests and limits:

- **Guaranteed**: Every container in the pod has CPU and memory requests and limits that match for each resource after admission defaulting. A missing request can be defaulted from its corresponding limit, so the request need not be written explicitly. Guaranteed pods are generally evicted after lower QoS classes under node resource pressure, but they are not immune to eviction.
- **Burstable**: At least one container in the pod specifies a CPU or memory request or limit, but requests and limits do not match across all resources. Burstable workloads can consume surplus host capacity when available, but face eviction if the host encounters severe memory pressure.
- **BestEffort**: No container in the pod defines any CPU or memory requests or limits. BestEffort workloads operate on scavenged node capacity, and the kubelet evicts them first whenever host resources become constrained.

```text
+-------------------------------------------------------------------------+
|                  Quality of Service (QoS) Eviction Hierarchy            |
|                                                                         |
|  [ BestEffort ]  --> Evicted FIRST under node memory pressure           |
|                      (No requests or limits configured)                 |
|                                                                         |
|  [ Burstable ]   --> Evicted SECOND under node memory pressure          |
|                      (Requests < Limits or partial definitions)         |
|                                                                         |
|  [ Guaranteed ]  --> Evicted LAST under node memory pressure            |
|                      (Requests == Limits for CPU & Memory everywhere)   |
+-------------------------------------------------------------------------+
```

Linux Completely Fair Scheduler quota enforcement translates container CPU limits into cgroup parameters named cpu.cfs_quota_us and cpu.cfs_period_us on worker nodes. By default, the kernel enforces quotas across one hundred millisecond evaluation periods, meaning a container with a limit of five hundred millicores receives fifty milliseconds of execution time per period. Multi-threaded applications that spawn numerous concurrent worker threads can exhaust their period quota prematurely, experiencing severe CPU throttling even when overall average CPU utilization appears well below configured thresholds.

When worker nodes experience critical memory exhaustion, the kubelet evaluates container working set memory rather than resident memory to make eviction determinations. The working set metric incorporates active memory pages and cached filesystem blocks that cannot be reclaimed easily by the kernel. If a node crosses hard eviction thresholds, such as memory.available dropping below one hundred mebibytes, the kubelet ranks pods by QoS class and relative memory consumption, evicting lower-tier workloads to protect the stability of the underlying host operating system.

Cluster administrators implement policy boundaries using ResourceQuota and LimitRange objects to prevent rogue workloads from monopolizing shared cluster infrastructure. A ResourceQuota establishes cumulative consumption ceilings within a namespace, restricting total CPU, memory, persistent storage, and object counts. A LimitRange operates at the individual pod and container level within a namespace, enforcing default requests and limits for unconfigured containers, establishing minimum and maximum sizing boundaries, and preventing developers from deploying unconstrained workloads that disrupt multi-tenant harmony.

---

## Core Content: Advanced Pod Placement, Node Affinity, and Taints

The kube-scheduler assigns unscheduled pods to eligible worker nodes through a two-phase evaluation pipeline consisting of filtering and scoring. During the filtering phase, the scheduler applies predicate plugins to eliminate candidate nodes that cannot satisfy workload constraints, filtering out hosts with insufficient CPU or memory capacity, mismatched host ports, unsatisfied node selectors, or un-tolerated node taints. In the subsequent scoring phase, the scheduler evaluates remaining candidate nodes against weighted priority plugins, ranking hosts based on balanced resource allocation, image locality, and topological spread preferences to select the optimal host.

Workload placement constraints begin with basic nodeSelector declarations and extend to sophisticated expression-based node affinity rules. A nodeSelector matches exact key-value labels on nodes, functioning strictly as a binary filter. Node affinity provides advanced matching capabilities using logical operators including In, NotIn, Exists, DoesNotExist, Gt, and Lt. Hard node affinity, declared as requiredDuringSchedulingIgnoredDuringExecution, blocks pod placement entirely if no worker node satisfies the expression. Soft node affinity, declared as preferredDuringSchedulingIgnoredDuringExecution, assigns positive integer weights to candidate nodes, guiding the scheduler toward preferred infrastructure while permitting placement elsewhere if capacity is unavailable.

Pod affinity and anti-affinity rules coordinate workload placement based on labels present on neighboring pods rather than node attributes. Pod affinity encourages co-locating dependent microservices within the same availability zone or network switch to minimize communication latency. Pod anti-affinity prevents redundant application replicas from scheduling onto the same physical node or failure domain, eliminating single points of failure across infrastructure outages. Both affinity types evaluate topologyKey fields, such as kubernetes.io/hostname or topology.kubernetes.io/zone, to define the geographical or physical boundary of the placement constraint.

Topology spread constraints provide fine-grained control over workload distribution across arbitrary failure domains, preventing replica clustering on single availability zones. Configured with maxSkew, topologyKey, whenUnsatisfiable, and labelSelector fields, topology spread constraints instruct the scheduler to calculate the difference in pod counts between zones. The maxSkew parameter defines the maximum permitted degree of imbalance; setting whenUnsatisfiable to DoNotSchedule enforces a rigid placement ceiling, whereas ScheduleAnyway treats the constraint as a soft optimization preference.

Modern scheduling architectures support combining topology spread constraints with matchLabelKeys to maintain balanced distributions during rolling updates. When a new Deployment revision rolls out, matchLabelKeys instructs the scheduler to evaluate skew calculations using the pod-template-hash label, ensuring that incoming pods spread evenly without being blocked by legacy replicas awaiting termination. This refinement prevents rollout deadlocks in tightly constrained multi-zone environments.

Taints and tolerations establish node repulsion boundaries, allowing specific nodes to reject workloads. Administrators apply taints with `kubectl taint nodes`, specifying a key, value, and effect: `NoSchedule`, `PreferNoSchedule`, or `NoExecute`. `NoSchedule` prevents untolerated pods from scheduling while leaving existing pods undisturbed. `PreferNoSchedule` is a soft scheduling preference. `NoExecute` also evicts running pods without a matching toleration. A matching toleration without `tolerationSeconds` keeps the pod bound indefinitely; setting `tolerationSeconds` limits how long that matching toleration delays eviction.

Node maintenance procedures frequently leverage the built-in unschedulable node condition alongside administrative taints. Executing kubectl cordon applies the node.kubernetes.io/unschedulable taint with effect NoSchedule, preventing the scheduler from placing newly created pods on the machine while leaving running workloads completely unaffected. When preparing a node for hardware replacement or kernel upgrades, administrators follow cordoning with kubectl drain, which invokes the Eviction API to evict existing pods gracefully while respecting PodDisruptionBudgets.

---

## Core Content: Configuration Decoupling with ConfigMaps and Secrets

The twelve-factor application methodology mandates the strict separation of executable application binaries from runtime configuration and credentials. Kubernetes implements this separation through ConfigMap and Secret resources, allowing developers to inject non-confidential variables, configuration files, and sensitive authentication credentials dynamically without rebuilding container images. ConfigMaps store plaintext data formatted as individual key-value pairs or multi-line configuration blocks, constructed from literal command-line arguments, local property files, or entire configuration directories.

Secret objects store confidential data, such as database credentials, TLS certificates, and API tokens, encoding payload values in base64 format within the API datastore. Kubernetes provides several built-in Secret types, including Opaque for general-purpose user credentials, kubernetes.io/tls for public and private cryptographic keys, and kubernetes.io/dockerconfigjson for private container registry authentication. Base64 encoding is an obfuscation mechanism rather than cryptographic encryption; securing Secrets requires enabling encryption-at-rest within the kube-apiserver configuration and enforcing strict Role-Based Access Control policies to restrict read permissions.

Workload pods consume ConfigMaps and Secrets through two primary injection mechanisms: environment variables and mounted filesystem volumes. Environment variables inject individual configuration keys using valueFrom references, or ingest all key-value pairs simultaneously using the envFrom directive. Filesystem volume mounts present configuration data as directories, where each key represents an individual filename and its corresponding value represents the file content. Mounting configurations as volumes enables atomic live updates managed by kubelet synchronization loops, allowing application processes that watch configuration files to reload updated settings dynamically.

**Pause and predict:** An active Deployment running 3 replicas consumes environment variables from a ConfigMap using the envFrom directive. An operator patches the ConfigMap with new configuration keys and values, and immediately scales the Deployment from 3 to 5 replicas without modifying the pod template. Which Pods in the Deployment observe the updated ConfigMap values?

<details>
<summary>Check your prediction</summary>

Only the 2 newly created Pods (replicas 4 and 5) observe the updated ConfigMap values. The 3 existing running Pods continue executing with the old environment variables injected at container startup because Linux process environments cannot be dynamically altered after process initialization. To propagate updated environment variables across all replicas, the operator must trigger a rollout restart using `kubectl rollout restart deployment <name>`.

</details>

Understanding the operational divergence between environment variable injection and live filesystem projections dictates how teams design configuration refresh workflows. Decoupling configuration state from container process lifecycles prevents subtle version drift across horizontally scaled microservice tiers during operational adjustments.

When mounting configuration files into existing directories that already contain other application assets, using standard volume mounts overwrites the entire target directory. To mount a single configuration file without clobbering existing directory contents, operators specify a subPath within the volumeMount declaration. However, administrators must note that files mounted via subPath do not receive automated live updates when the underlying ConfigMap or Secret changes, because the Linux kernel binds the specific file inode at container initialization, bypassing subsequent directory re-linking.

Enterprise architectures frequently streamline configuration volume declarations by utilizing projected volumes. A projected volume maps multiple heterogeneous sources, including ConfigMaps, Secrets, downward API metadata, and projected service account tokens, into a unified directory structure inside the container filesystem. This unified projection simplifies container configuration logic while enforcing least-privilege credential injection through time-bound, audience-scoped service account tokens.

Immutable ConfigMaps and Secrets protect configuration data from accidental changes. Set `immutable: true` as a top-level field beside `metadata` and `data`, not inside `metadata`. Immutable objects cannot have their data changed in place; Kubernetes can also close watches for them, reducing API server load in clusters with many mounted configuration objects.

---

## Did You Know?

- **Fact 1**: [Regular init containers run sequentially to completion](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/) before application containers start. An init container with `restartPolicy: Always` is a sidecar that remains running while subsequent containers start.
- **Fact 2**: [StatefulSets require a headless Service](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) with clusterIP None to establish direct DNS A-records for individual ordinal pods, enabling predictable peer-to-peer discovery for distributed databases without clusterIP load balancing.
- **Fact 3**: [Linux kernel Control Groups enforce memory limits strictly](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) through the Out-Of-Memory killer which immediately terminates containers exceeding their memory ceiling with exit code 137, while CPU limits merely trigger process throttling without container termination.
- **Fact 4**: [Marking ConfigMaps and Secrets as immutable](https://kubernetes.io/docs/concepts/configuration/configmap/) by setting immutable to true protects critical application configurations from accidental drift while substantially reducing API server memory and CPU overhead by terminating watch connections.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Updating a Deployment image without checking readiness probe configuration | The new ReplicaSet may spin up pods that fail readiness, but legacy pods might be killed if maxUnavailable is misconfigured, causing total outage | Configure explicit readiness probes and safe maxUnavailable/maxSurge parameters before initiating rollouts |
| Deploying a StatefulSet without a governing headless Service | Individual ordinal pods never receive individual DNS records, breaking stateful peer discovery and clustering | Always declare and bind a headless Service (`clusterIP: None`) matching the StatefulSet `serviceName` |
| Omitting memory requests when defining memory limits | Kubernetes automatically assigns requests equal to limits, potentially escalating the pod into an unintended QoS class or causing node scheduling failures | Explicitly specify both resource requests and limits based on observed profiling data |
| Expecting ConfigMap changes in `envFrom` to update running containers | Container process environment variables are immutable at runtime and never reload without process recreation | Trigger a rolling rollout restart (`kubectl rollout restart deployment <name>`) or use volume mounts for reloadable configs |
| Using `restartPolicy: Always` in batch Job specifications | The Job controller rejects the manifest because batch workloads require run-to-completion semantics | Specify `restartPolicy: OnFailure` or `restartPolicy: Never` for all Job and CronJob manifests |
| Tainting a node with `NoExecute` when critical pods lack a matching toleration | Untolerated running pods are evicted; `tolerationSeconds` cannot delay eviction without a matching toleration | Add a matching `NoExecute` toleration without `tolerationSeconds` to remain bound, or set a duration when delayed eviction is intended |
| Mounting ConfigMaps via `subPath` and expecting automated live updates | The kubelet atomic volume update mechanism does not propagate modifications to individual files mounted using `subPath` | Mount the entire ConfigMap directory or design an external reload container to watch and signal updates |
| Encoding Secrets with `echo "secret" \| base64` instead of `echo -n` | A trailing newline character (`\n`) is encoded into the payload, causing subtle authentication failures in application containers | Always use `echo -n "secret" \| base64` to avoid injecting unwanted newline bytes into credential values |

---

## Quiz

Answer these scenario-based questions without referring to earlier modules. After each answer, compare your reasoning with the explanation, not just the final command. The goal is to prove that you can choose safe actions under realistic exam constraints.

### 1. Multi-Container Pod Lifecycle and Probes

An application container in a multi-container pod takes sixty seconds to warm up its internal caching layer before it can answer requests or respond to health checks. When deployed with a standard liveness probe configured with initialDelaySeconds set to 5 and failureThreshold set to 3, the container continuously restarts every twenty seconds and never enters a healthy state. How should an engineer resolve this cyclic container termination?

1. Add a startup probe pointing to the health endpoint with a failureThreshold high enough to accommodate the sixty-second initialization window.
2. Remove the readiness probe and rely exclusively on container runtime exit codes to detect process health.
3. Change the pod restartPolicy from Always to Never so that kubelet stops restarting the initialization failure.
4. Increase the container memory limit to 2Gi to force the kernel to bypass liveness probe evaluation.

<details>
<summary>Answer</summary>

Option 1 is correct because configuring a startup probe disables liveness and readiness probe execution until the container successfully completes initialization, preventing premature termination loops. Option 2 is wrong because removing readiness probes leaves unready pods receiving user traffic through active Services. Option 3 is incorrect because setting restartPolicy to Never merely leaves the pod dead upon the first failure rather than resolving slow startup. Option 4 is not correct because memory limits have no influence on probe execution schedules or liveness timeouts.

</details>

### 2. Deployment Rolling Update Surge Tuning

A production Deployment runs 4 replicas. The engineering team requires that during an image upgrade, the workload must never drop below 4 operational pods, while the total number of pods across the cluster during the rollout must not exceed 5. Which rollingUpdate strategy configuration satisfies these constraints?

1. Set `maxUnavailable: 0` and `maxSurge: 1` under `strategy.rollingUpdate`.
2. Set `maxUnavailable: 1` and `maxSurge: 0` under `strategy.rollingUpdate`.
3. Set `maxUnavailable: 25%` and `maxSurge: 25%` under `strategy.rollingUpdate`.
4. Change the Deployment strategy type to `Recreate` to ensure clean transitions.

<details>
<summary>Answer</summary>

Option 1 is correct because `maxUnavailable: 0` guarantees all 4 initial replicas remain active throughout the rollout, while `maxSurge: 1` restricts additional transient pods to exactly 1 above desired count (total 5). Option 2 is wrong because `maxUnavailable: 1` permits the controller to drop capacity to 3 pods during updates. Option 3 is incorrect because `maxUnavailable: 25%` of 4 replicas allows 1 pod to be unavailable (leaving only 3 available). Option 4 is not correct because the Recreate strategy terminates all 4 running pods before creating new ones, causing immediate application downtime.

</details>

### 3. StatefulSet Identity and Headless Service Configuration

An operator deploys a 3-replica StatefulSet named `datastore` managing a distributed key-value database, but client applications report that domain name queries to `datastore-0.datastore-headless.production.svc.cluster.local` fail with NXDOMAIN. Inspecting the cluster reveals the StatefulSet pods are running, and a Service named `datastore-headless` exists with `clusterIP: 10.96.120.45`. What is the root cause of this name resolution failure?

1. The governing Service was created as a standard ClusterIP Service instead of a headless Service with `clusterIP: None`, preventing CoreDNS from generating individual ordinal A-records.
2. The StatefulSet specification is missing an explicit `volumeClaimTemplate` mapping the DNS names to host volumes.
3. The pods were deployed in `OrderedReady` mode instead of `Parallel` mode, which disables cluster DNS registration.
4. The CoreDNS deployment must be scaled to 5 replicas to support StatefulSet record serialization.

<details>
<summary>Answer</summary>

Option 1 is correct because CoreDNS only constructs direct DNS A-records for individual StatefulSet pods when the governing Service has `clusterIP: None` (a headless Service). Option 2 is wrong because volumeClaimTemplates manage persistent storage claims, not network name resolution. Option 3 is incorrect because podManagementPolicy controls startup sequencing, not DNS registration. Option 4 is not correct because CoreDNS replica count affects resolution capacity, not whether headless SRV and A-records are generated.

</details>

### 4. DaemonSet Node Scheduling and Tolerations

A platform engineer deploys a monitoring DaemonSet that must run on all worker nodes across the cluster, including two dedicated nodes tainted with `node-role.kubernetes.io/infra:NoSchedule`. After applying the DaemonSet manifest, pods appear on general worker nodes, but the two dedicated infrastructure nodes remain empty. How should the engineer ensure the DaemonSet schedules onto the tainted hosts?

1. Add a toleration to the DaemonSet pod template matching key `node-role.kubernetes.io/infra` with effect `NoSchedule` and operator `Exists`.
2. Delete the taint from the infrastructure nodes using `kubectl taint nodes` and run the DaemonSet in hostNetwork mode.
3. Modify the DaemonSet to run with `restartPolicy: OnFailure` so that the kubelet overrides node taints automatically.
4. Change the DaemonSet `updateStrategy` from `RollingUpdate` to `OnDelete`.

<details>
<summary>Answer</summary>

Option 1 is correct because adding a matching toleration to the pod template permits the kube-scheduler to place DaemonSet pods onto nodes possessing the `NoSchedule` taint. Option 2 is wrong because removing taints compromises node isolation policies designed to protect infrastructure hosts from unapproved workloads. Option 3 is incorrect because DaemonSets only support `restartPolicy: Always` and restart policies do not bypass scheduling taints. Option 4 is not correct because the updateStrategy dictates rollout behavior when templates change, not initial node scheduling eligibility.

</details>

### 5. Job Parallelism, Completions, and Retries

A data engineering batch task requires processing 10 independent data chunks to completion. The processing container can run safely with up to 3 concurrent instances without overloading the source database. If an individual pod crashes due to a transient network timeout, the Job controller should retry up to 4 times before failing the entire batch. Which Job manifest fields correctly configure this requirement?

1. Configure `completions: 10`, `parallelism: 3`, `backoffLimit: 4`, and `restartPolicy: OnFailure`.
2. Configure `completions: 3`, `parallelism: 10`, `activeDeadlineSeconds: 4`, and `restartPolicy: Always`.
3. Configure `completions: 10`, `parallelism: 3`, `backoffLimit: 4`, and `restartPolicy: Always`.
4. Configure `completions: 10`, `parallelism: 1`, `backoffLimit: 10`, and `restartPolicy: Never`.

<details>
<summary>Answer</summary>

Option 1 is correct because completions: 10 establishes the required successful run count for the batch workload, parallelism: 3 limits concurrent pods to 3, backoffLimit: 4 restricts retries to 4 attempts, and restartPolicy: OnFailure is valid for Jobs. Option 2 is wrong because swapping completions and parallelism runs 10 pods concurrently for only 3 completions, while restartPolicy: Always is rejected by the API server. Option 3 is incorrect because Jobs strictly prohibit restartPolicy: Always. Option 4 is not correct because parallelism: 1 runs tasks sequentially rather than utilizing the permitted 3 concurrent workers.

</details>

### 6. Resource Management and Quality of Service Classification

A pod manifest declares a single container with a memory request of 256Mi and a memory limit of 512Mi. The CPU request is configured as 200m, while the CPU limit is unconfigured. What Quality of Service class does Kubernetes assign to this pod, and what happens if the container process consumes 600Mi of memory during peak operation?

1. The pod is classified as `Burstable`, and the container is immediately terminated with an OOMKilled exit code 137 when memory exceeds 512Mi.
2. The pod is classified as `Guaranteed`, and the container CPU is throttled while memory is dynamically expanded.
3. The pod is classified as `BestEffort`, and the kubelet evicts the entire worker node when memory exceeds 512Mi.
4. The pod is classified as `Burstable`, and memory usage is throttled by the Linux Completely Fair Scheduler without container restart.

<details>
<summary>Answer</summary>

Option 1 is correct because having requests and limits that are not identical across all resources categorizes the workload as `Burstable`, and exceeding a strict memory limit triggers immediate Linux kernel OOM termination (exit code 137). Option 2 is wrong because Guaranteed QoS requires requests to equal limits for both CPU and memory across all containers. Option 3 is incorrect because BestEffort QoS only applies when zero requests or limits are declared. Option 4 is not correct because memory is a non-compressible resource that cannot be throttled; only CPU can be throttled via CFS quotas.

</details>

### 7. Advanced Scheduling with Node Affinity and Anti-Affinity

An architect must ensure that web frontend pods are scheduled exclusively onto worker nodes in availability zones `zone-a` or `zone-b`. Additionally, no two web frontend pods should ever run on the exact same physical node to protect against local hardware failure. Which combination of scheduling primitives satisfies both requirements?

1. Use `nodeAffinity` with `requiredDuringSchedulingIgnoredDuringExecution` matching key `topology.kubernetes.io/zone` in values `[zone-a, zone-b]`, paired with `podAntiAffinity` using `topologyKey: kubernetes.io/hostname`.
2. Use `nodeSelector` matching `zone: zone-a, zone-b`, paired with `podAffinity` using `topologyKey: kubernetes.io/hostname`.
3. Configure `nodeAffinity` with `preferredDuringSchedulingIgnoredDuringExecution` matching `zone-a`, paired with a node taint `NoSchedule` on `zone-b`.
4. Configure `topologySpreadConstraints` with `maxSkew: 0` and omit all affinity and selector rules.

<details>
<summary>Answer</summary>

Option 1 is correct because hard `nodeAffinity` restricts node placement to the specified zones using the In operator, while `podAntiAffinity` across `topologyKey: kubernetes.io/hostname` prevents co-locating matching frontend pods on the same node. Option 2 is wrong because `nodeSelector` does not support set-based matching across multiple values (it requires exact equality), and podAffinity co-locates pods rather than separating them. Option 3 is incorrect because soft affinity does not guarantee zone enforcement and taints prevent scheduling on zone-b. Option 4 is not correct because maxSkew cannot be zero and topology spread constraints alone do not enforce strict mutual pod exclusion on identical hostnames.

</details>

### 8. Configuration Decoupling and Live Updates

A microservice consumes application parameters from a ConfigMap mounted as a directory at `/etc/config`. The ConfigMap is modified in the cluster using `kubectl edit configmap`. How do the updated keys propagate to the running container, and what limitation applies if an individual file was mounted using `subPath`?

1. Mounted directories are updated automatically by the kubelet sync loop, but files mounted using `subPath` do not receive live updates and require a pod recreation.
2. Mounted directories and `subPath` files both update instantaneously within five seconds through Linux inotify kernel events.
3. The ConfigMap update triggers an automatic rolling restart of the parent Deployment controller immediately upon API acceptance.
4. Neither directory mounts nor `subPath` mounts ever update; ConfigMaps are permanently immutable once mounted inside container sandboxes.

<details>
<summary>Answer</summary>

Option 1 is correct because the kubelet periodically updates directory volume projections via symbolic link swaps, but individual files mounted using `subPath` bypass directory linking and never receive automatic updates. Option 2 is wrong because `subPath` volume mounts are bound to file inodes at creation time and cannot be updated in place by kubelet. Option 3 is incorrect because editing a ConfigMap does not modify the Deployment pod template, so the Deployment controller triggers no automated rollout. Option 4 is not correct because standard volume mounts do receive live updates unless the ConfigMap is explicitly configured with `immutable: true`.

</details>

---

## Hands-On Exercise

**Task**: Execute a comprehensive workload and scheduling verification drill across your local practice cluster. You will configure multi-container pods with probes, orchestrate safe Deployment rollouts and rollbacks, deploy StatefulSets with headless Services, execute parallel batch Jobs, configure Quality of Service boundaries, and manage node taints with ConfigMap environment injections.

Use an existing disposable local Kubernetes cluster such as kind, minikube, or a multi-node kubeadm sandbox. Do not run these destructive operations against a shared production environment. All commands use standard kubectl syntax without shell aliases.

### Step 1: Multi-Container Pod with Probes and Shared Volume

Deploy a multi-container pod featuring an application container and a sidecar container sharing an emptyDir volume. Configure an HTTP readiness probe on the application container:

```bash
cat <<'EOF' > /tmp/multi-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-app
  labels:
    app: multi-app
spec:
  volumes:
  - name: shared-data
    emptyDir: {}
  containers:
  - name: web-server
    image: nginx:1.35
    ports:
    - containerPort: 80
    volumeMounts:
    - name: shared-data
      mountPath: /usr/share/nginx/html
    readinessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 2
      periodSeconds: 5
  - name: content-producer
    image: busybox:1.36
    command: ["/bin/sh", "-c"]
    args:
    - while true; do echo "Health verification at $(date)" > /data/index.html; sleep 5; done
    volumeMounts:
    - name: shared-data
      mountPath: /data
EOF

kubectl apply -f /tmp/multi-pod.yaml
kubectl wait --for=condition=Ready pod/multi-app --timeout=30s
kubectl describe pod multi-app | grep -E '(Ready:|ContainersReady:)'
kubectl delete pod multi-app
rm -f /tmp/multi-pod.yaml
```

### Step 2: Deployment Rollout and Rollback Verification

Create a Deployment running 3 replicas, update the container image with explicit surge parameters, inspect the rollout history, and execute an immediate rollback:

```bash
kubectl create deployment rolling-drill --image=nginx:1.35 --replicas=3
kubectl patch deployment rolling-drill -p '{"spec":{"strategy":{"rollingUpdate":{"maxSurge":1,"maxUnavailable":0}}}}'
kubectl set image deployment/rolling-drill nginx=nginx:1.35-alpine
kubectl rollout status deployment/rolling-drill
kubectl rollout history deployment/rolling-drill
kubectl rollout undo deployment/rolling-drill
kubectl rollout status deployment/rolling-drill
kubectl get rs -l app=rolling-drill
kubectl delete deployment rolling-drill
```

### Step 3: StatefulSet and Headless Service Resolution

Deploy a 2-replica StatefulSet with a governing headless Service. Verify that individual ordinal pod identities receive unique, stable DNS records:

```bash
cat <<'EOF' > /tmp/stateful-drill.yaml
apiVersion: v1
kind: Service
metadata:
  name: stateful-svc
spec:
  clusterIP: None
  selector:
    app: stateful-drill
  ports:
  - port: 80
    name: web
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: stateful-drill
spec:
  serviceName: stateful-svc
  replicas: 2
  selector:
    matchLabels:
      app: stateful-drill
  template:
    metadata:
      labels:
        app: stateful-drill
    spec:
      containers:
      - name: nginx
        image: nginx:1.35
        ports:
        - containerPort: 80
EOF

kubectl apply -f /tmp/stateful-drill.yaml
kubectl rollout status statefulset/stateful-drill
test "$(kubectl get service stateful-svc -o jsonpath='{.spec.clusterIP}')" = None
kubectl get pods -l app=stateful-drill -o custom-columns=NAME:.metadata.name,HOSTNAME:.spec.hostname,SUBDOMAIN:.spec.subdomain
kubectl run dns-check --image=busybox:1.36 --restart=Never --command -- sh -c 'nslookup stateful-drill-0.stateful-svc && nslookup stateful-drill-1.stateful-svc'
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/dns-check --timeout=60s
kubectl logs dns-check
kubectl delete pod dns-check
kubectl delete -f /tmp/stateful-drill.yaml
rm -f /tmp/stateful-drill.yaml
```

### Step 4: Batch Job Parallelism and Resource Quotas

Create a batch Job that runs 6 tasks to completion with a concurrency parallelism of 2, configuring explicit resource requests and limits:

```bash
cat <<'EOF' > /tmp/batch-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-drill
spec:
  completions: 6
  parallelism: 2
  backoffLimit: 3
  template:
    spec:
      restartPolicy: OnFailure
      containers:
      - name: worker
        image: busybox:1.36
        command: ["/bin/sh", "-c", "echo 'Processing task'; sleep 2"]
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
EOF

kubectl apply -f /tmp/batch-job.yaml
kubectl wait --for=condition=Complete job/batch-drill --timeout=60s
kubectl get job batch-drill
kubectl get job batch-drill -o jsonpath='{.spec.template.spec.containers[0].resources}{"\n"}'
kubectl delete -f /tmp/batch-job.yaml
rm -f /tmp/batch-job.yaml
```

### Step 5: Node Taints, Tolerations, and ConfigMap Injection

Create a ConfigMap and taint a Ready node, including a control-plane node in a single-node sandbox. Constrain two pods to that node through scheduler-evaluated node affinity: one lacks the new taint's toleration and must remain Pending, while the other tolerates it and reads the ConfigMap through `envFrom`. The control-plane tolerations handle common sandbox taints on both pods, so the maintenance taint is the difference under test:

```bash
kubectl create configmap app-cfg --from-literal=ENVIRONMENT=staging --from-literal=LOG_LEVEL=info
TARGET_NODE=$(kubectl get nodes --no-headers | awk '$2 == "Ready" {print $1; exit}')
test -n "$TARGET_NODE"
kubectl taint node "$TARGET_NODE" maintenance=true:NoSchedule --overwrite

cat <<EOF > /tmp/taint-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: untolerated-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchFields:
          - key: metadata.name
            operator: In
            values: ["$TARGET_NODE"]
  tolerations:
  - key: node-role.kubernetes.io/control-plane
    operator: Exists
    effect: NoSchedule
  - key: node-role.kubernetes.io/master
    operator: Exists
    effect: NoSchedule
  containers:
  - name: test-app
    image: busybox:1.36
    command: ["/bin/sh", "-c", "sleep 3600"]
---
apiVersion: v1
kind: Pod
metadata:
  name: config-taint-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchFields:
          - key: metadata.name
            operator: In
            values: ["$TARGET_NODE"]
  tolerations:
  - key: node-role.kubernetes.io/control-plane
    operator: Exists
    effect: NoSchedule
  - key: node-role.kubernetes.io/master
    operator: Exists
    effect: NoSchedule
  - key: "maintenance"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  containers:
  - name: test-app
    image: busybox:1.36
    command: ["/bin/sh", "-c", "env && sleep 3600"]
    envFrom:
    - configMapRef:
        name: app-cfg
EOF

kubectl apply -f /tmp/taint-pod.yaml
kubectl wait --for=condition=PodScheduled=False pod/untolerated-pod --timeout=30s
test "$(kubectl get pod untolerated-pod -o jsonpath='{.status.phase}')" = Pending
test "$(kubectl get pod untolerated-pod -o jsonpath='{.status.conditions[?(@.type=="PodScheduled")].reason}')" = Unschedulable
kubectl wait --for=condition=Ready pod/config-taint-pod --timeout=30s
test "$(kubectl get pod config-taint-pod -o jsonpath='{.spec.nodeName}')" = "$TARGET_NODE"
test "$(kubectl exec config-taint-pod -- printenv ENVIRONMENT)" = staging
test "$(kubectl exec config-taint-pod -- printenv LOG_LEVEL)" = info
kubectl delete -f /tmp/taint-pod.yaml
kubectl taint node "$TARGET_NODE" maintenance=true:NoSchedule-
kubectl delete configmap app-cfg
rm -f /tmp/taint-pod.yaml
```

**Card A: A Deployment rollout with maxUnavailable 0 never runs more Pods than the desired count.** An operations engineer configures a Deployment of 4 replicas with maxUnavailable set to 0 and maxSurge set to 2. They assume that because maxUnavailable guarantees zero missing replicas, the cluster will never execute more than 4 concurrent Pods during an image rollout. When they trigger an update, they are alarmed to discover 6 Pods running simultaneously across worker nodes and attempt to kill the extra containers manually.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing availability floor guarantees with surge headroom limits. Next action: recognize that maxSurge allows the Deployment controller to create additional Pods above the desired replica count to maintain full capacity while new containers initialize, and allow the rollout to converge automatically without manual container deletion.

</details>

**Card B: A headless Service is optional for a StatefulSet that needs stable network names.** A platform developer deploys a 3-replica MongoDB StatefulSet without creating a governing Service, assuming that Kubernetes StatefulSets automatically assign discoverable, individual DNS A-records to each ordinal pod out of the box. When dependent applications fail to resolve mongo-0 through cluster DNS queries, the developer assumes CoreDNS has crashed and restarts the cluster DNS deployment repeatedly.

<details>
<summary>Check your prediction</summary>

Failure layer: assuming StatefulSet controllers generate network DNS records without a governing headless Service. Next action: create and bind a headless Service with clusterIP set to None and matching serviceName metadata so that CoreDNS creates stateful pod identity A-records for each individual ordinal instance.

</details>

**Card C: Setting a memory limit without a request keeps the Pod in Burstable and the limit is only a hint.** A junior sysadmin writes a Pod manifest specifying a memory limit of 512Mi without defining a memory request, believing that omitting the request places the workload into the flexible Burstable QoS tier where the limit acts merely as an advisory guideline. When the container suddenly terminates with an OOMKilled exit code 137 upon reaching 512Mi, the sysadmin files a kernel bug report blaming host memory management.

<details>
<summary>Check your prediction</summary>

Failure layer: misunderstanding default request inheritance and container runtime cgroup memory enforcement. Next action: understand that Kubernetes defaults an omitted memory request from its limit. The Pod is Guaranteed only if every container also has equal CPU requests and limits after defaulting; otherwise it is Burstable. A memory limit remains enforceable, so exceeding it can lead to an OOM kill.

</details>

**Card D: Patching a ConfigMap used through envFrom rewrites the environment of Pods that are already running.** An engineer updates database connection parameters in a ConfigMap referenced by a Deployment through the envFrom configuration block. They expect that patching the ConfigMap will instantly update the running containers' environment variables in place without restarting Pods. When the application continues connecting to the legacy database host, the engineer assumes the ConfigMap patch failed to apply to the API server datastore.

<details>
<summary>Check your prediction</summary>

Failure layer: conflating dynamic filesystem mounts with static container process environment initialization. Next action: execute `kubectl rollout restart deployment <name>` to trigger a rolling recreation of Pods so that newly spawned containers read the updated ConfigMap keys into their process environments.

</details>

**Success Criteria**:

- [ ] You evaluated multi-container pod architectures and verified probe status using `kubectl describe pod`.
- [ ] You inspected a Deployment rollout, ran `kubectl rollout undo`, and waited for the rollback to complete.
- [ ] You configured a StatefulSet with a headless Service and resolved both ordinal pod DNS names.
- [ ] You created a batch workload using a Job with explicit completion and parallelism constraints and monitored task lifecycle.
- [ ] You confirmed an untolerated pod remains unschedulable and a matching toleration allows the second pod onto the tainted node.
- [ ] You checked the Job's declared resource requests and limits in its manifest.
- [ ] You confirmed the tolerated pod received both ConfigMap values through environment variables.

---

## Sources

- https://kubernetes.io/docs/concepts/workloads/pods/
- https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
- https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/
- https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
- https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/
- https://kubernetes.io/docs/concepts/workloads/controllers/job/
- https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
- https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/
- https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/
- https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/
- https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/
- https://kubernetes.io/docs/concepts/configuration/configmap/
- https://kubernetes.io/docs/concepts/configuration/secret/

## Next Module

Continue to [Part 3: Services & Networking](/k8s/cka/part3-services-networking/)
