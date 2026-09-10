---
citations_verified: true
title: "Module 1.12: OpenTelemetry Collector at Production Scale"
slug: platform/toolkits/observability-intelligence/observability/module-1.12-otel-collector-production
revision_pending: false
sidebar:
  order: 13
---

> **Toolkit Track** | Complexity: `[COMPLEX]` | Time: 60 min
>
> **Prerequisites**: [Module 1.2: OpenTelemetry](../module-1.2-opentelemetry/) and basic Kubernetes scheduling, Services, Deployments, DaemonSets, StatefulSets, resource limits, and namespaces.
>
> **Track**: Toolkits

## Learning Outcomes

After completing this module, you will be able to:

- **Choose** Collector deployment topologies for fleet-scale Kubernetes environments, including operator-managed `OpenTelemetryCollector` resources, auto-instrumentation `Instrumentation` resources, DaemonSets, Deployments, StatefulSets, and the agent plus gateway pattern.
- **Compose** Collector pipelines using receivers, processors, exporters, connectors, `memory_limiter`, `batch`, and processor ordering rules that protect reliability and cost.
- **Design** trace sampling at scale with head sampling, tail sampling policies, and the `load_balancing` exporter so horizontally scaled collector tiers preserve complete traces.
- **Control** telemetry cardinality and backend ingest cost with attribute allowlists, redaction, metric label reduction, transform processors, and per-tenant attribute scoping.
- **Route** multi-tenant telemetry through shared or isolated collector tiers using tenant attributes, routing connectors, per-tenant exporters, and clear isolation tradeoffs.

## Why This Module Matters

The OpenTelemetry basics module taught you the shape of a Collector pipeline: receive telemetry, process it, and export it to one or more backends. That model is accurate, but it is deliberately small. Production fleets add harder constraints. Hundreds of services emit traces, metrics, and logs from many clusters. Teams want different backends, different sampling policies, different retention tiers, and different budgets. Security teams want sensitive attributes removed before data leaves the cluster. Finance teams want the observability bill to stop growing faster than the platform itself. A single "send OTLP to a collector" diagram is not enough for that operating surface.

The production Collector is best understood as a traffic control layer for evidence. Applications create telemetry near the work. The Collector tier decides how much of that evidence is worth keeping, which attributes are allowed to travel, which tenant owns it, and which backend should receive it. Those decisions are operational policy, not application code. Moving them into a managed collector layer lets platform teams change sampling, routing, batching, and redaction without asking every service team to redeploy during an incident or a cost emergency.

The analogy is a regional airport network. A small private airstrip can land every plane directly, but a national network needs control towers, regional hubs, cargo rules, passenger screening, and route planning. The Collector plays the hub role. A DaemonSet collector near every node is like a local tower that accepts traffic close to the runway. A gateway tier is like a regional hub that applies shared policy. Tail sampling is like deciding which flights need detailed post-flight review after the journey is visible, not before the plane leaves the gate. Cardinality control is the baggage rule that prevents every passenger from inventing a unique tag and forcing the storage system to treat it as a new route.

The most expensive mistakes are subtle because telemetry often keeps flowing while the design is already broken. A collector without a `memory_limiter` may look healthy until a burst pushes it into OOMKill loops and upstream SDKs start dropping spans. A tail-sampling policy may keep errors in a test cluster, then silently lose important spans in production because a round-robin load balancer splits each trace across several collectors. A metrics pipeline may accept one new label such as `user.id`, `request.id`, or raw URL path, then create millions of time series before anyone sees the storage bill. This module teaches the production design habits that prevent those failures.

The module is intentionally not a runnable operator lab. You will see realistic configuration fragments because production collector work is configuration-heavy, but the goal is design literacy. You should finish with the ability to review a collector pull request and ask the right questions: where does tenant identity come from, which tier owns sampling, what protects memory, which attributes are allowed, and what happens when a backend slows down. Those questions catch more real failures than memorizing every component option.

This is also why the module keeps cost visible from the beginning. Observability platforms often fail socially before they fail technically: the platform team adds more detail because incidents are painful, finance pushes back because the bill grows, security asks for redaction after data has already spread, and application teams bypass shared policy because the default path feels too restrictive. A production Collector design gives those groups a common control surface. Sampling, routing, batching, and attribute policy become explicit platform decisions instead of scattered application defaults.

> **Landscape snapshot — as of 2026-09. This changes fast; verify against vendor docs before relying on specifics.**
>
> OpenTelemetry is a CNCF Graduated project. CNCF announced graduation on May 21, 2026 and described OTel as having the second-highest project velocity in CNCF after Kubernetes. That maturity applies to the project as a whole; the Collector still requires per-component review when you build a production distribution.
>
> The Collector is versioned separately from the specification and from many language SDKs. As of this snapshot, the core Collector release is v1.66.0/v0.160.0, published on September 2, 2026, and the contrib distribution is v0.160.0, published on September 2, 2026. The paired versioning is intentional: stable core modules can be in the v1.x line while the broader collector distribution and contrib components remain in the v0.1xx line.
>
> Component stability is mixed. The OpenTelemetry status page says core collector components have mixed stability levels, and each receiver, processor, exporter, connector, and extension documents its own alpha, beta, stable, deprecated, or unmaintained status in its README. Production reviews should therefore check the exact components you enable, not just the Collector binary version.

## Collector Deployment Topologies

The [OpenTelemetry Operator for Kubernetes](https://opentelemetry.io/docs/platforms/kubernetes/operator/) gives platform teams a Kubernetes-native control plane for collectors and auto-instrumentation. Its two important custom resources are `OpenTelemetryCollector`, which describes managed Collector instances, and `Instrumentation`, which configures SDK and auto-instrumentation injection for workloads. The distinction matters because collector topology and application instrumentation are separate decisions. You may standardize one gateway collector tier for a cluster while allowing different languages to use different injection settings, resource attributes, and exporter endpoints.

An operator-managed collector is still a Kubernetes workload. The operator reconciles the declared collector resource into the workload shape you choose, such as a Deployment, DaemonSet, StatefulSet, or sidecar. That mode is not an implementation detail. It defines the failure domain, scaling model, scheduling cost, and how much telemetry context the collector can see before it forwards data. At fleet scale, topology is a budget decision and a correctness decision at the same time.

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: cluster-gateway
  namespace: observability
spec:
  mode: deployment
  replicas: 3
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      memory: "2Gi"
  config:
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318
    processors:
      memory_limiter:
        check_interval: 1s
        limit_percentage: 75
        spike_limit_percentage: 15
      batch:
        send_batch_size: 8192
        timeout: 2s
    exporters:
      otlp/backend:
        endpoint: tempo-distributor.observability.svc.cluster.local:4317
        tls:
          insecure: true
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [otlp/backend]
```

The current landscape has four common collector shapes. A Deployment gateway provides a stable OTLP endpoint and central policy, so it is the usual first production target for application telemetry. A DaemonSet agent runs one collector per node, which is useful for node-local receivers, Kubernetes log collection, host metrics, and reducing cross-node network hops. A StatefulSet gives stable network identity and storage attachment, which can help with components that care about stable collector identities or headless service discovery. A sidecar collector sits next to one workload and can be useful for strict isolation, but it multiplies resource overhead and operational complexity because every application replica carries another process.

| Topology | Useful When | Main Tradeoff |
|---|---|---|
| Deployment gateway | Applications can send OTLP to a cluster, region, or data-center endpoint | Easy to scale, but it is an extra tier to secure and monitor |
| DaemonSet agent | You need node-local logs, host metrics, or low-latency local collection | Cost grows with node count even when telemetry volume is low |
| StatefulSet gateway | You need stable identities, headless service targets, or predictable resolver behavior | Scaling and upgrades need more care than a Deployment |
| Sidecar collector | A workload requires strong per-app isolation or local policy ownership | Every replica pays CPU and memory overhead for its own collector |

The agent plus gateway pattern combines two shapes. Node-local agents collect host-level signals, enrich telemetry with Kubernetes context, and forward to a smaller gateway tier. The gateway tier owns shared policy: tail sampling, backend credentials, tenant routing, filtering, and export retries. This split keeps node-specific work close to the node while avoiding a world where every DaemonSet instance has to know every backend credential and every sampling policy. It also lets you scale the gateway tier by ingest volume rather than by node count.

```text
Application Pods        Node Agents                 Regional Gateway
--------------          -----------                 ----------------
OTLP traces  ------->   DaemonSet collector   --->  Deployment/StatefulSet collectors
Container logs ----->   host/log receivers    --->  tail sampling, routing, export
Host metrics  ----->    k8s attributes        --->  backends and tenant policy
```

Cost shows up differently in each topology. A DaemonSet with 256 MiB requested memory on 300 nodes reserves about 75 GiB of cluster memory before it processes one span. A gateway Deployment with three replicas may reserve less baseline memory, but it concentrates burst risk and network traffic. A sidecar collector with 128 MiB next to 1,200 application pods reserves about 150 GiB of memory across the fleet. The right design is not the one with the fewest collectors; it is the one where baseline cost, burst absorption, failure isolation, and policy ownership match the telemetry volume.

The `Instrumentation` resource solves a different problem. It helps inject and configure auto-instrumentation libraries, SDK environment variables, and resource attributes for workloads. That is powerful, but it does not replace topology design. If auto-instrumented applications all send to a fragile gateway, the instrumentation works while the platform fails. If injected resource attributes use inconsistent service names or tenant labels, the collector can receive valid OTLP data that is still impossible to route, sample, or charge back correctly.

The practical topology rule is to separate locality from policy. Use local collectors when the signal needs local context, node access, or short network paths. Use gateway collectors when the signal needs shared policy, tenant decisions, backend credentials, or fleet-level cost control. Use sidecars only when isolation or application-owned policy is worth the repeated overhead. Use StatefulSets when stable identity is a requirement, not because stateful sounds more production-grade.

A useful design review starts by drawing the telemetry path separately for each signal. Traces from SDKs might go directly to a gateway because applications already know how to export OTLP. Container logs might need a DaemonSet because log files are node-local and require host volume access. Prometheus-style scraping might need a target allocator or shard-aware collector setup because a single gateway scraper can overload itself or create duplicate metric writers. Treating all signals as one pipeline usually produces a topology that is convenient to draw but painful to operate.

Failure domains should be visible in the topology. A DaemonSet agent failure affects the pods or node it serves, while a gateway failure can affect the entire cluster or region. A regional gateway can reduce backend credential sprawl, but it also becomes an incident object that deserves PodDisruptionBudgets, resource reservations, autoscaling policy, internal telemetry, and clear ownership. The more centralized the tier, the more disciplined its rollout process must be, because one bad collector configuration can drop evidence for many teams at once.

The operator improves consistency, but it does not remove the need for platform review. A malformed `OpenTelemetryCollector` resource can still express a poor topology, an unsafe processor order, or an exporter that sends too much data to the wrong place. Operator ownership should therefore include admission checks, configuration linting, canary rollouts, and dashboards for the reconciled workloads. The CRD makes collectors declarative; it does not make every declared design production-ready.

At fleet scale, topology also affects team autonomy. If every service team edits one shared gateway collector, the collector becomes a coordination bottleneck. If every team runs its own collector tier, the organization loses standardization and wastes resources. A practical platform often exposes a small set of blessed paths: a default shared gateway for ordinary services, a regulated path with stricter redaction, a high-volume path with aggressive sampling, and an exception process for teams that need dedicated collectors. Standard choices reduce both cost and negotiation.

## Pipeline Composition

A Collector pipeline is a directed path through receivers, processors, and exporters. Receivers accept telemetry from SDKs, agents, scrapers, files, or other collectors. Processors transform, drop, enrich, batch, redact, sample, or protect that telemetry. Exporters send the result to another collector, an observability backend, an object store, or a debugging sink. [The Collector configuration model](https://opentelemetry.io/docs/collector/configuration/) also includes connectors, which act as both exporter and receiver so one pipeline can feed another pipeline for routing, fan-out, or signal conversion.

The simple mental model is "receive, process, export," but production correctness depends on order. The [memory limiter processor](https://github.com/open-telemetry/opentelemetry-collector/blob/main/processor/memorylimiterprocessor/README.md) is designed to reject data when collector memory crosses configured thresholds, and its own best-practice guidance says to place it first in the pipeline. That early placement lets backpressure reach receivers before later processors allocate more memory. If you put expensive transforms, tail sampling, or batching before the limiter, the collector may burn memory on data that should have been refused earlier.

The [batch processor](https://github.com/open-telemetry/opentelemetry-collector/blob/main/processor/batchprocessor/README.md) belongs late in the pipeline because batching improves compression and reduces outbound connection overhead after dropping decisions are already made. If you batch before sampling or filtering, you spend CPU and memory packing telemetry that may be discarded a moment later. If you batch before tenant routing, you may also create awkward mixed-tenant batches that reduce isolation and make per-tenant export behavior harder to reason about.

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 15
  k8sattributes:
    passthrough: false
  transform/cardinality_guard:
    error_mode: ignore
    trace_statements:
      - limit(span.attributes, 80, ["http.route", "http.request.method", "http.response.status_code"])
      - truncate_all(span.attributes, 2048)
  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    policies:
      - name: keep-errors
        type: status_code
        status_code:
          status_codes: [ERROR]
  batch:
    send_batch_size: 8192
    timeout: 2s

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors:
        - memory_limiter
        - k8sattributes
        - transform/cardinality_guard
        - tail_sampling
        - batch
      exporters: [otlp/traces]
```

This example is conceptual, but the ordering is intentional. First, `memory_limiter` protects the process. Then Kubernetes enrichment can attach stable resource context while span context is still available. Then a transform step limits and truncates span attributes before the tail sampler stores trace data in memory. Then `tail_sampling` decides which complete traces to keep. Finally, `batch` prepares surviving telemetry for efficient export. You would tune the exact processors, but the reasoning is reusable.

Processor order also matters because some processors change context. The [tail sampling processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md) groups spans by trace ID and reassembles spans into new batches. Its documentation warns that processors relying on context, such as Kubernetes attribute enrichment, should run before tail sampling. If a later processor expects the same request metadata, client metadata, or batch structure that existed at ingest time, tail sampling may already have changed the shape of the data it sees.

Connectors deserve special attention because they make collector configuration look less linear. A connector is configured under `connectors`, appears as an exporter in one pipeline, and appears as a receiver in another pipeline. That indirection is useful for routing and generated signals, but it can hide mistakes. When you route by tenant, the pipeline that receives raw telemetry must export to the connector, and each tenant-specific pipeline must receive from that connector. If you forget one side, the collector configuration may validate differently than your mental diagram.

The strongest pipeline habit is to label every processor by intent. `attributes/redact_secrets` communicates more than `attributes`. `transform/drop_unbounded_labels` tells reviewers why it exists. `batch/tenant` says the batcher is tied to tenant metadata. Named components make review possible because production collector files often contain dozens of similar processors. They also help dashboard and internal telemetry labels point to the policy you actually meant to operate.

Pipeline composition should be reviewed as a contract between neighboring components. A receiver promises to accept data and pass it downstream. A processor may mutate, drop, delay, or regroup that data. An exporter may retry, queue, or fail. The contract breaks when one component assumes a shape that a previous component has already changed. For example, a route that depends on request metadata must run before a processor removes or regroups that metadata. A redaction rule that removes `tenant.id` must not run before tenant routing unless another trusted tenant field exists.

Ordering also changes cost in non-obvious ways. A transform that trims span attributes before tail sampling can reduce sampler memory because fewer bytes are held per pending trace. A filter that drops noisy health-check spans before tail sampling reduces the number of traces the sampler tracks. A batch processor before either of those steps can amplify memory because it waits with data that later processors may discard. The same components can be cheap or expensive depending on where they sit.

A production pipeline should have a failure story for each exporter. Backends slow down, credentials expire, DNS changes, network policies block traffic, and regional endpoints fail. Exporter queues and retries can protect short outages, but they also store data in memory or persistent queues and can hide a downstream failure until queues fill. When one exporter is optional and another is critical, split the paths or use routing and failure-specific policy instead of assuming one shared exporter list can express business priority.

Connectors are powerful because they make the collector graph-shaped rather than purely linear. That power deserves diagrams in code review. If a connector routes traces into three pipelines, reviewers should see which processors run before the connector, which run after it, and which pipelines receive unmatched data. The default route is especially important. A missing default can drop unexpected tenants. A permissive default can leak data to a shared backend. Neither is inherently wrong, but both must be deliberate.

## Sampling at Scale

Sampling is the first large cost lever most tracing platforms reach for, because traces can grow faster than logs or metrics during high-traffic periods. [OpenTelemetry sampling guidance](https://opentelemetry.io/docs/concepts/sampling/) distinguishes head sampling, where the decision happens early without seeing the full trace, from tail sampling, where the decision happens after observing all or most spans in the trace. Head sampling is cheap and simple. Tail sampling is more expensive, but it can keep errors, slow requests, and business-critical flows that random early sampling might drop.

Head sampling is usually configured in SDKs or near the first collector hop. It is efficient because most dropped traces never enter the expensive part of the pipeline. The downside is blindness. A request may look ordinary at the root span and fail deep inside a downstream dependency. A head sampler that dropped the trace at the edge cannot recover it later. That tradeoff is acceptable for very high-volume, low-value traffic, but it is dangerous when rare failures carry most of the incident value.

Tail sampling keeps the decision close to the evidence. The [tail sampling processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md) can sample by status code, latency, span count, attributes, OTTL conditions, probabilistic policy, rate limits, and combinations of policies. A useful production policy often keeps all error traces, keeps high-latency traces, keeps selected business flows at a higher rate, and keeps a small probabilistic sample of ordinary success traffic for baseline comparison.

```yaml
processors:
  tail_sampling/checkout:
    decision_wait: 15s
    num_traces: 100000
    expected_new_traces_per_sec: 3000
    decision_cache:
      sampled_cache_size: 200000
      non_sampled_cache_size: 400000
    policies:
      - name: keep-errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: keep-slow-checkout
        type: latency
        latency:
          threshold_ms: 1200
      - name: keep-critical-tenant
        type: string_attribute
        string_attribute:
          key: tenant.tier
          values: ["enterprise"]
      - name: baseline-success
        type: probabilistic
        probabilistic:
          sampling_percentage: 5
```

Tail sampling has a correctness condition that is easy to miss: all spans for a given trace must reach the same collector instance that makes the sampling decision. The processor documentation states this directly, and the [gateway deployment guidance](https://opentelemetry.io/docs/collector/deploy/gateway/) recommends a two-tier setup with the load-balancing exporter for cases where telemetry must be processed by a specific collector. If a normal round-robin Service sends span A to collector 1, span B to collector 2, and span C to collector 3, no collector sees the full trace. Each one makes a partial decision.

The fix is trace-aware routing before the tail-sampling tier. The [load-balancing exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/exporter/loadbalancingexporter/README.md) can consistently route spans based on `traceID`, so spans belonging to the same trace go to the same downstream collector. In Kubernetes, that often means a first-tier gateway receives OTLP from applications or agents, then exports to a second-tier tail-sampling collector pool through `load_balancing` with a DNS or Kubernetes resolver. The second tier performs tail sampling and exports kept traces to the backend.

```text
SDKs and node agents
        |
        v
First-tier gateway collectors
        |
        |  load_balancing exporter, routing_key: traceID
        v
Second-tier tail-sampling collectors
        |
        |  keep errors, slow traces, critical tenants, baseline sample
        v
Trace backend
```

This two-tier design costs more CPU, memory, and network hops than direct export, so you should use it where the value justifies the machinery. A moderate fleet can produce surprising volume. If 120 services average 10 running pods, each pod handles 2 requests per second, and each request creates 12 spans, the fleet produces about 28,800 spans per second. That is roughly 2.4 billion spans per day before retries, background jobs, and traffic spikes. Keeping every raw span may be useful during a migration, but it is rarely a sustainable default.

Sampling policy is also a fairness problem. A single high-volume service can dominate a global probabilistic sample and crowd out low-volume but business-critical services. Tail sampling lets you write policies that preserve low-volume critical flows while reducing ordinary high-volume success traces. Per-service or per-tenant policy should be explicit, reviewed, and monitored. Otherwise, "sample five percent" becomes a hidden product decision about whose incidents are easy to investigate.

The operational metrics of the sampler matter as much as the policy itself. Watch collector memory, refused data, dropped spans, tail-sampling decision latency, traces waiting for decisions, and exporter queue behavior. Increase `decision_wait` when late spans commonly arrive after the decision window, but remember that longer waits hold more trace data in memory. Increase `num_traces` when traffic bursts exceed the in-memory trace cache, but connect that change to pod memory limits and the `memory_limiter`. Sampling is not just a YAML policy; it is a stateful workload with a budget.

Good sampling policy starts with an incident question. "Keep five percent" is a volume target, not an investigation strategy. Better policies say which evidence must survive: all failed payment authorizations, all traces slower than an SLO threshold, all traces for a newly released service during a canary, all traces for a high-priority tenant during a migration, and a representative sample of ordinary success traffic. The collector can express those choices only if the relevant attributes are present, normalized, and preserved until the sampler evaluates them.

Tail sampling can also distort your view if the policy is too clever. A policy that keeps only errors and very slow requests makes the backend look like the system is always unhealthy because ordinary success traces are absent. A baseline probabilistic policy provides comparison data, which helps engineers understand whether a slow trace is unusual or just one example from a known latency distribution. Cost control should reduce volume without destroying the ability to compare failure paths with healthy paths.

Sampling decisions should be versioned and rolled out like application behavior. A change from ten percent baseline sampling to one percent baseline sampling may reduce cost, but it also reduces the chance that rare successful paths appear in traces. A new latency threshold may keep more traces during a traffic surge and overload the backend precisely when the incident is already stressful. Treat sampler policy as production code: review it, canary it, monitor the effect, and keep a rollback path.

The interaction between SDK head sampling and collector tail sampling deserves special care. If SDKs drop a trace at the head, the collector cannot reconstruct it later. That means aggressive head sampling can starve a tail sampler of the very evidence it needs. Head sampling is still useful for extremely high-volume or low-value traffic, but the fleet standard should make clear which services are allowed to head-sample, which must send unsampled traces to the collector tier, and which emergency procedure temporarily changes those settings.

## Cardinality and Cost Control

Cardinality is the number of distinct identities your telemetry system must store and query. In Prometheus-style metrics, the data model identifies a time series by metric name plus labels, so every new label value can create another series. In traces and logs, high-cardinality attributes may not create Prometheus series directly, but they still increase index size, storage, query fan-out, compression pressure, and backend ingest cost. The Collector is one of the few places where you can enforce attribute policy before the data reaches expensive storage.

The classic bad label is a unique request or user value. A metric named `http.server.duration` with labels for method, route, status, and service is manageable because those values come from small sets. Add `user.id`, raw `url.path`, `session.id`, `pod.uid`, or a full exception message as labels, and the same metric may produce millions of streams. The telemetry still looks structured, so teams often notice only after queries slow down or the backend rejects writes. Cardinality failures are not noisy at the edge; they are noisy in the bill and the backend.

Cost control starts with an allowlist mindset. Decide which resource attributes, span attributes, metric labels, and log attributes are allowed to cross each boundary. Service identity, namespace, environment, region, workload, route template, method, status code, tenant tier, and stable team ownership fields are usually useful. Raw identifiers, secrets, tokens, email addresses, full URLs with IDs, customer names, and unbounded error strings are usually dangerous. The collector should delete, hash, truncate, aggregate, or route these values before export.

The [attributes processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/attributesprocessor/README.md) is useful for direct actions such as delete, hash, insert, update, extract, and convert. The [transform processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/transformprocessor/README.md) uses OTTL statements and can apply richer signal-specific logic, such as keeping only selected keys, truncating long values, or replacing path patterns. The [metrics transform processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/metricstransformprocessor/README.md) can rename metrics, change label keys, delete data points, scale values, and aggregate across label sets or label values.

```yaml
processors:
  attributes/redact_sensitive_trace_attrs:
    actions:
      - key: enduser.id
        action: hash
      - key: http.request.header.authorization
        action: delete
      - key: db.statement
        action: delete
  transform/normalize_paths:
    error_mode: ignore
    trace_statements:
      - replace_all_matches(span.attributes, "/users/*/orders/*", "/users/{userId}/orders/{orderId}")
      - keep_keys(span.attributes, ["http.route", "http.request.method", "http.response.status_code", "tenant.id"])
      - truncate_all(span.attributes, 2048)
    metric_statements:
      - limit(datapoint.attributes, 20, ["service.name", "http.route", "http.response.status_code", "tenant.id"])
  metricstransform/reduce_pod_labels:
    transforms:
      - include: ^container\.
        match_type: regexp
        action: update
        operations:
          - action: aggregate_labels
            label_set: [namespace, workload, container]
            aggregation_type: sum
```

The safest place to drop sensitive data is before it leaves the trust boundary that created it. If a cluster hosts regulated workloads, delete or hash sensitive attributes in an agent or cluster-local gateway before forwarding to a regional collector or vendor endpoint. If you wait until a central multi-tenant backend, the sensitive value has already crossed a network and access boundary. Redaction is not only about storage cost; it is about reducing how many systems ever see the value.

Tenant attributes need a separate policy. A tenant label is essential for routing, chargeback, and debugging, but it can also explode cardinality if it is not normalized. `tenant.id` should come from an authenticated source or controlled metadata, not from arbitrary user input inside span attributes. If you support thousands of tenants, decide which signals need per-tenant labels and which should be aggregated by tenant tier, region, or product area. A high-cardinality tenant dimension may be justified for request traces and billing metrics, but it may be wasteful on every low-level runtime metric.

Batching by metadata is another hidden cost lever. The batch processor can create batcher instances per metadata key combination, which is useful for multi-tenant batching over authorization metadata. The same feature can consume significant memory because every distinct combination can allocate a background task and pending batch. If you batch by tenant, set `metadata_cardinality_limit`, validate tenant metadata early, and monitor the batch processor cardinality metric. Multi-tenancy should not turn the batch processor into an unbounded map.

Cost spikes usually come from multiplicative changes. A new service emitting 20 extra spans per request is noticeable. A new unbounded label on a high-volume metric is worse because it multiplies streams by every distinct value. A sampling change from 5 percent to 100 percent during an incident may be justified for one service, but dangerous if applied globally. A transform that preserves full command lines or request bodies may help one investigation and permanently expand storage. Production cost control means treating every added attribute as an ingest and retention decision.

Cardinality review should happen before a metric or attribute becomes part of a dashboard contract. Once teams depend on a label, removing it becomes a breaking change for alerts, dashboards, notebooks, and incident runbooks. The platform can reduce this friction by publishing allowed dimensions for common signal families: HTTP route, method, status, service, namespace, workload, region, and environment for request metrics; service, span name, status, route, and selected tenant tiers for traces; severity, service, namespace, and stable error category for logs. Clear defaults make the cheapest safe path easy.

The Collector is a good enforcement point, but it is not the only one. SDK instrumentation should avoid creating high-cardinality telemetry in the first place. Code review should challenge raw labels before they ship. Backend limits should reject runaway streams before they endanger shared storage. Dashboards should expose top label cardinality and ingest drivers. Collector transforms are the middle layer: they protect the backend from mistakes that escaped instrumentation review, and they provide a consistent policy boundary across languages and teams.

Cost control is also about retaining useful shape after reduction. Dropping every detailed attribute can make traces cheap but useless. The goal is to preserve dimensions that answer operational questions while removing dimensions that identify individual events too precisely for aggregation. For example, `http.route=/users/{userId}/orders/{orderId}` preserves the product path, while `url.path=/users/123/orders/987` creates unnecessary identity. A hashed `enduser.id` may support abuse investigation without exposing a raw identifier, but even hashed values can be high-cardinality and should rarely become metric labels.

Per-tenant scoping should distinguish cost allocation from debugging. Billing may need a stable tenant identifier on a small set of ingest accounting metrics. Debugging may need tenant identity on traces for a limited set of services or tiers. Broadly attaching `tenant.id` to every runtime metric, every process metric, and every log line can increase cardinality without improving most investigations. A mature policy says where tenant labels are mandatory, where they are optional, and where they are forbidden.

Do not confuse compression with cardinality control. Batching and compression reduce transport overhead, but they do not make a million distinct time series cheap to index and query. Similarly, dropping old data sooner reduces retention cost but does not prevent ingest spikes or query pain during the retention window. The cheapest telemetry is the telemetry you never generate or never export. The second cheapest is telemetry that is normalized before it reaches high-cost storage.

## Multi-Tenancy and Tenant Routing

Multi-tenancy in the Collector is the practice of moving telemetry from many teams, applications, namespaces, or customers through shared infrastructure without losing ownership, isolation, or cost accountability. The hard part is not adding a `tenant.id` attribute. The hard part is proving that the tenant value is trustworthy, preserved until routing happens, removed or scoped when it should not leak, and used consistently by exporters and backends. A tenant label that anyone can forge is not an isolation boundary.

The current Collector routing shape is the [routing connector](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/connector/routingconnector/README.md), which routes logs, metrics, or traces to specific pipelines using OTTL conditions. Older examples may refer to a routing processor, but connector-based routing is the model to learn for new designs because it routes between pipelines. That lets you apply different processors after the routing decision, such as per-tenant redaction, tenant-specific batching, exporter headers, or different retention destinations.

```yaml
connectors:
  routing/tenant:
    default_pipelines: [traces/default]
    error_mode: ignore
    table:
      - context: resource
        condition: attributes["tenant.id"] == "payments"
        pipelines: [traces/payments]
      - context: resource
        condition: attributes["tenant.id"] == "marketplace"
        pipelines: [traces/marketplace]

exporters:
  otlp/payments:
    endpoint: tempo-payments.observability.svc.cluster.local:4317
    headers:
      tenant: payments
    tls:
      insecure: true
  otlp/marketplace:
    endpoint: tempo-marketplace.observability.svc.cluster.local:4317
    headers:
      tenant: marketplace
    tls:
      insecure: true
  otlp/default:
    endpoint: tempo-shared.observability.svc.cluster.local:4317
    tls:
      insecure: true

service:
  pipelines:
    traces/in:
      receivers: [otlp]
      processors: [memory_limiter, attributes/tenant_from_auth]
      exporters: [routing/tenant]
    traces/payments:
      receivers: [routing/tenant]
      processors: [transform/payments_policy, batch]
      exporters: [otlp/payments]
    traces/marketplace:
      receivers: [routing/tenant]
      processors: [transform/marketplace_policy, batch]
      exporters: [otlp/marketplace]
    traces/default:
      receivers: [routing/tenant]
      processors: [transform/default_policy, batch]
      exporters: [otlp/default]
```

This example shows a shared ingress pipeline followed by tenant-specific pipelines. The first pipeline receives telemetry, applies early protection, and routes by tenant. The tenant pipelines apply local policy and export to different destinations. In a real design, the tenant value should come from authenticated request metadata, mTLS identity, namespace mapping, or a trusted enrichment step. If you simply trust whatever the application wrote into `tenant.id`, a compromised or misconfigured workload can route its telemetry into another tenant's backend.

There are three common isolation levels. Shared collector, shared backend, and tenant attributes is the cheapest model, but it relies on backend query isolation and disciplined labels. Shared collector with per-tenant exporters gives stronger routing and retention control while keeping one collector tier. Per-tenant collector tiers give the strongest operational separation, but they multiply upgrades, resource reservations, dashboards, and on-call surface. The platform should offer the weakest model that satisfies the data boundary, not the strongest model that sounds reassuring.

Tenant routing also interacts with sampling. If the tail sampler runs before routing, one policy must represent every tenant unless you encode tenant conditions inside the sampling policy. If routing runs before tail sampling, each tenant pipeline can own its own sampler, but now each tenant needs enough traffic and resources to make good decisions. For many organizations, the best compromise is an early trusted tenant stamp, trace-aware load balancing, and a second-tier sampler that includes tenant-aware policies for critical tenants and lower-cost probabilistic policies for routine traffic.

Chargeback and cost allocation need the same tenant discipline. If the collector emits internal metrics by pipeline, exporter, tenant, and error path, you can identify which tenant is driving ingest, queue growth, retries, or dropped data. If the collector tier is a black box, every cost conversation becomes political because the bill arrives without ownership evidence. Multi-tenant observability must be observable itself, with collector metrics, dashboards, alerts, and runbooks tied to tenant routes.

Tenant identity usually flows through more than one layer. A namespace may map to a team, an authentication proxy may attach an organization header, a service catalog may define ownership, and an SDK may add business context. These are not equivalent. Namespace ownership can route platform metrics to a team, while request-level tenant identity may route customer traces to a regulated backend. Mixing them under one generic `tenant` key creates confusion. Use names that describe the boundary, such as `platform.team`, `tenant.id`, `tenant.tier`, and `service.owner`.

Default routes are a security and cost decision. A default pipeline that exports unmatched telemetry to a shared backend is convenient during onboarding because new services do not disappear. It is also risky if regulated or high-cost telemetry arrives without a recognized tenant. A default pipeline that drops unmatched telemetry protects isolation but can hide onboarding mistakes. A balanced design may route unmatched telemetry to a short-retention quarantine backend, alert the platform team, and require the service owner to fix tenant metadata before production rollout.

Per-tenant exporters should not be treated as only endpoint differences. They may also carry different TLS settings, headers, compression behavior, retry budgets, queue sizes, sampling policies, and retention destinations. A premium tenant or regulated business unit may require stronger export guarantees and stricter redaction. A development tenant may tolerate lower retention and more aggressive sampling. The collector can express these differences, but only if the routing design keeps tenant-specific policy readable instead of burying it in one giant transform block.

Multi-tenancy also changes incident response. During a backend outage, do you drop low-priority tenants first, route them to cheaper storage, or let every tenant share the same queue until all exporters fail? During a suspected data leak, can you identify which tenant routes saw the sensitive attribute and which exporters sent it? During a cost spike, can you throttle one tenant without damaging others? These questions determine whether shared collector infrastructure is truly multi-tenant or merely multi-user.

## Patterns and Anti-Patterns

The best production pattern is a layered collector architecture with explicit responsibilities. Node agents collect local signals and add local context. Gateways enforce shared policy and hide backend credentials from applications. A trace-aware load-balancing tier feeds tail samplers when trace completeness matters. Tenant routing happens only after a trusted tenant identity is attached and before backend-specific export settings. Cardinality and redaction controls run before expensive storage boundaries, and every collector tier exports internal telemetry about memory, queue depth, refused data, and export failures.

The first anti-pattern is running without `memory_limiter`. Kubernetes resource limits can kill a collector, but they do not create graceful backpressure. A collector that dies under burst loses in-memory data, restarts cold, and may trigger retry storms from upstream agents or SDKs. The `memory_limiter` processor gives the pipeline a chance to refuse data before the process crosses its hard limit. It is not a substitute for sizing, but it is an essential guardrail for bursty ingest.

The second anti-pattern is tail sampling behind ordinary round-robin balancing. Round-robin can distribute load evenly while destroying trace completeness. The symptom is especially frustrating because the backend still receives traces, but they are partial, inconsistent, and biased by which collector saw which spans. If tail sampling correctness matters, use trace-aware routing such as the `load_balancing` exporter with `traceID`, and monitor the downstream sampler tier as a stateful workload.

The third anti-pattern is treating all attributes as harmless context. Every attribute has a storage, privacy, query, and ownership cost. Unbounded labels should be denied by default, not cleaned up after the backend melts. Build allowlists for metrics labels, delete or hash sensitive values before export, normalize paths to route templates, truncate long strings, and review any new tenant dimension as both a routing key and a cost key.

Best practices can be summarized as a review checklist: put memory protection first, batch late, sample intentionally, route by trusted tenant identity, normalize high-cardinality fields, monitor the collector tier, and write down which team owns each policy. That last item sounds administrative, but it prevents the most common production failure mode: everyone can edit the collector, nobody owns the cost, and no one can explain why a critical trace vanished during an incident.

The production-ready pattern is boring on purpose. Every collector tier has resource requests and limits, a memory limiter, health and readiness behavior, internal telemetry scraping, alerts for refused data and exporter failures, and a documented owner. Every backend exporter has a retry and queue strategy that matches the business value of the signal. Every sampling policy names the evidence it protects. Every route has a default behavior. Every transform that drops or hashes data has a reason that a reviewer can understand months later.

The review process should include a small set of adversarial questions. What happens if traffic doubles for one hour? What happens if the trace backend is slow but not down? What happens if a new service emits a million unique label values? What happens if a tenant attribute is missing or forged? What happens if the collector deployment rolls out a bad config to every replica at once? Designs that answer these questions are usually ready for production experimentation. Designs that wave them away are still demos.

Finally, remember that collector policy is part of the product experience for engineers. If the platform silently drops traces, developers stop trusting tracing. If cost controls remove the attributes needed to debug incidents, teams work around the platform and send data directly to vendors. If tenant routing is opaque, security teams push for isolated stacks everywhere. A good Collector design makes the safe path useful enough that teams choose it voluntarily.

The mature end state is not one perfect collector configuration. It is a repeatable operating loop. Teams propose new telemetry dimensions with expected value and expected cost. The platform tests those changes in a canary collector path, watches internal collector metrics and backend ingest, then promotes the policy through GitOps with a rollback. Incident reviews feed missing evidence back into instrumentation or collector policy. Cost reviews feed noisy dimensions back into allowlists and sampling rules. The Collector becomes the place where learning turns into fleet-wide defaults.

| Pattern or Anti-Pattern | Why It Matters | Better Habit |
|---|---|---|
| Agent plus gateway pattern | Separates local collection from shared policy | Keep node-local receivers near nodes and backend policy in gateways |
| `memory_limiter` first | Protects the process before expensive processors allocate more memory | Put `memory_limiter` first in every signal pipeline |
| Batch late | Avoids batching data that sampling or filtering will drop | Put `batch` after sampling, filtering, and tenant-specific transforms |
| Tail sampling without trace-aware routing | Splits traces across collectors and creates partial sampling decisions | Use `load_balancing` with `traceID` before the tail-sampling tier |
| Unbounded labels | Creates runaway series, storage, and query cost | Use allowlists, route templates, hashing, aggregation, and truncation |
| Tenant from untrusted span data | Lets workloads forge ownership and routing | Stamp tenant identity from authenticated metadata or platform mapping |
| Shared backend with no collector internal telemetry | Makes cost and failures impossible to attribute | Export collector metrics by pipeline, exporter, and route |

## Did You Know

- **The gateway pattern is not just a load balancer**: OpenTelemetry's gateway guidance explicitly calls out a two-tier setup when data must reach a specific collector, such as a tail-sampling tier that needs complete traces.
- **The batch processor can increase memory in multi-tenant mode**: batching by metadata creates separate batcher instances per metadata combination, so tenant-aware batching needs a cardinality limit and monitoring.
- **The load-balancing exporter is not ordinary balancing**: for traces, its default routing key is `traceID`, which is why it can keep spans for the same trace together for downstream processing.
- **Routing is now connector-shaped in current collector designs**: the routing connector acts as exporter and receiver between pipelines, which lets tenant-specific processors run after the route is chosen.

## Common Mistakes

| Mistake | Problem | Solution |
|---|---|---|
| Deploying one gateway Deployment with no node agents | Host logs, host metrics, and node-local context may be missing or expensive to collect remotely | Use DaemonSet agents for node-local signals and forward to gateways for shared policy |
| Putting `batch` before `tail_sampling` | The collector spends memory and CPU batching traces that may be dropped | Place sampling and filtering before `batch`, then batch surviving telemetry |
| Putting expensive transforms before `memory_limiter` | Bursts can allocate memory before the limiter can refuse data | Put `memory_limiter` first and size pods with realistic burst headroom |
| Using a normal Service in front of tail samplers | Spans from one trace can land on different collector instances | Route by `traceID` with the `load_balancing` exporter before the sampler tier |
| Adding raw IDs as metric labels | Every unique value can create another time series and spike backend cost | Keep route templates and stable dimensions, then hash or delete raw identifiers |
| Trusting application-provided tenant attributes | A buggy or compromised workload can route telemetry into the wrong tenant | Derive tenant identity from authenticated metadata, namespace mapping, or platform policy |
| Sharing one backend exporter for all tenants | Retention, routing, credentials, and cost attribution become hard to separate | Use per-tenant pipelines or exporters when isolation requirements justify the overhead |

## Quiz

1. A platform team runs three gateway collectors behind a Kubernetes Service and enables `tail_sampling` on each gateway. Error traces are often incomplete. What is the likely design bug?

   <details>
   <summary>Answer</summary>
   The likely bug is that the Service is spreading spans from the same trace across multiple collectors. Tail sampling requires one collector instance to see all spans for a trace before it can make a correct decision. Use a first-tier collector with the `load_balancing` exporter routed by `traceID`, then send complete traces to a second-tier tail-sampling collector pool.
   </details>

2. Why should `memory_limiter` normally appear before `batch`, transforms, and sampling processors?

   <details>
   <summary>Answer</summary>
   `memory_limiter` protects the collector process by refusing data when memory crosses configured thresholds. If it runs after expensive processors, those processors can allocate memory before the limiter has a chance to apply backpressure. Put it first, then do context enrichment, cardinality controls, sampling, and late batching.
   </details>

3. A service adds `user.id` and raw `url.path` as metric labels on a high-traffic histogram. Which learning outcome does this violate, and what should the collector do?

   <details>
   <summary>Answer</summary>
   This violates cardinality and cost control. Each unique user or raw path can create additional metric series, increasing ingest, storage, and query cost. The collector should keep route templates such as `http.route`, drop or hash raw identifiers, and use transform or metric transform processors to limit labels and aggregate where appropriate.
   </details>

4. When would a DaemonSet collector be a better fit than a Deployment gateway?

   <details>
   <summary>Answer</summary>
   A DaemonSet is a better fit when the collector needs node-local access or context, such as host metrics, container logs, Kubernetes node metadata, or local buffering before forwarding. A Deployment gateway is better for central policy, backend credentials, tenant routing, and shared export behavior. Many production fleets use both.
   </details>

5. What is the difference between routing by tenant before sampling and sampling before routing by tenant?

   <details>
   <summary>Answer</summary>
   Routing before sampling lets each tenant pipeline apply its own sampler, redaction, batching, and exporter policy, but it may create smaller stateful sampler pools per tenant. Sampling before routing centralizes the sampler but requires tenant-aware policies inside one sampler. The right choice depends on isolation requirements, traffic volume, and how much policy differs by tenant.
   </details>

6. Why is the routing connector often a better teaching target than older routing processor examples?

   <details>
   <summary>Answer</summary>
   The routing connector connects pipelines by acting as an exporter in the incoming pipeline and a receiver in routed pipelines. That model lets you run tenant-specific processors after the routing decision. Older processor-shaped examples route directly inside one pipeline and can make post-route processing harder to reason about.
   </details>

## Hands-On Exercise: Review a Production Collector Design

This is a conceptual review exercise, not a live cluster lab. Read the following collector fragment as if it came from a design review for a shared platform gateway. Your task is to identify the reliability, sampling, cardinality, and multi-tenancy bugs before anyone deploys it. You do not need Kubernetes access, a backend, or the OpenTelemetry Operator to complete the exercise.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 10s
  tail_sampling:
    decision_wait: 5s
    policies:
      - name: keep-errors
        type: status_code
        status_code:
          status_codes: [ERROR]
  attributes/tenant:
    actions:
      - key: tenant.id
        from_attribute: app.tenant
        action: upsert
  transform/cardinality:
    error_mode: ignore
    metric_statements:
      - limit(datapoint.attributes, 100, [])

exporters:
  otlp/shared:
    endpoint: tempo-shared.observability.svc.cluster.local:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, tail_sampling, attributes/tenant]
      exporters: [otlp/shared]
    metrics:
      receivers: [otlp]
      processors: [batch, transform/cardinality]
      exporters: [otlp/shared]
```

Review checklist:

- [ ] **Collector deployment topology**: Decide whether this fragment belongs in a DaemonSet agent, Deployment gateway, StatefulSet gateway, or agent plus gateway topology, and explain which production requirement drives your choice.
- [ ] **Pipeline composition and processor order**: Identify the ordering bug involving `memory_limiter`, `batch`, `tail_sampling`, and tenant enrichment, then rewrite the intended order in plain English.
- [ ] **Sampling at scale**: Explain why this collector fragment is incomplete for horizontally scaled tail sampling and name the missing trace-aware routing component.
- [ ] **Cardinality and cost control**: Find the metric cardinality weakness in the transform statement and propose a safer allowlist for stable labels such as service, namespace, route, method, status, and tenant.
- [ ] **Multi-tenant routing**: Explain why copying `app.tenant` into `tenant.id` is not enough for isolation, then describe a trusted tenant source and a per-tenant routing design.

A strong answer should say that `memory_limiter` is missing entirely, `batch` is too early, tenant enrichment happens after tail sampling, and the metrics transform limits attribute count without defining which labels are safe. It should also say that a horizontally scaled tail sampler needs trace-aware routing, usually with a first-tier `load_balancing` exporter using `traceID`, so all spans for the same trace reach the same sampler. Finally, it should challenge the tenant source, because application-provided tenant attributes are useful context but not an authorization boundary.

## Next Module

Continue to the [GitOps & Deployments toolkit](../../cicd-delivery/gitops-deployments/) to learn how production delivery patterns keep platform configuration, including collector policy, reviewable and repeatable.

## Sources

- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) - General Collector role and architecture.
- [CNCF OpenTelemetry graduation announcement](https://www.cncf.io/announcements/2026/05/21/cloud-native-computing-foundation-announces-opentelemetrys-graduation-solidifying-status-as-the-de-facto-observability-standard/) - CNCF maturity and project activity snapshot.
- [OpenTelemetry project status](https://opentelemetry.io/status/) - Collector mixed stability status and per-component stability guidance.
- [OpenTelemetry Collector v1.66.0/v0.160.0 release](https://github.com/open-telemetry/opentelemetry-collector/releases/tag/v0.160.0) - Current core Collector release at this snapshot.
- [OpenTelemetry Collector Contrib v0.160.0 release](https://github.com/open-telemetry/opentelemetry-collector-contrib/releases/tag/v0.160.0) - Current contrib distribution release at this snapshot.
- [OpenTelemetry Collector configuration](https://opentelemetry.io/docs/collector/configuration/) - Receivers, processors, exporters, connectors, and service pipelines.
- [OpenTelemetry Collector agent deployment pattern](https://opentelemetry.io/docs/collector/deploy/agent/) - Agent collectors alongside applications or hosts.
- [OpenTelemetry Collector gateway deployment pattern](https://opentelemetry.io/docs/collector/deploy/gateway/) - Gateway collectors, load balancing, and tail-sampling topology guidance.
- [OpenTelemetry Operator for Kubernetes](https://opentelemetry.io/docs/platforms/kubernetes/operator/) - Operator-managed collectors and auto-instrumentation entry point.
- [OpenTelemetry Operator README](https://github.com/open-telemetry/opentelemetry-operator/blob/main/README.md) - `OpenTelemetryCollector`, `Instrumentation`, deployment modes, and injection details.
- [OpenTelemetry Sampling](https://opentelemetry.io/docs/concepts/sampling/) - Head sampling, tail sampling, and cost tradeoffs.
- [OpenTelemetry Collector connectors](https://opentelemetry.io/docs/collector/components/connector/) - Connectors as exporter and receiver between pipelines.
- [Memory Limiter Processor README](https://github.com/open-telemetry/opentelemetry-collector/blob/main/processor/memorylimiterprocessor/README.md) - Memory limiter behavior and placement guidance.
- [Batch Processor README](https://github.com/open-telemetry/opentelemetry-collector/blob/main/processor/batchprocessor/README.md) - Batch behavior, late placement, and metadata batching.
- [Tail Sampling Processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md) - Tail-sampling policies and trace completeness requirement.
- [Load Balancing Exporter README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/exporter/loadbalancingexporter/README.md) - Trace-aware routing and resolver behavior.
- [Attributes Processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/attributesprocessor/README.md) - Attribute delete, hash, insert, update, extract, and convert actions.
- [Transform Processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/transformprocessor/README.md) - OTTL-based transform statements for traces, metrics, logs, and profiles.
- [Metrics Transform Processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/metricstransformprocessor/README.md) - Metric rename, label, delete, scale, and aggregate operations.
- [Routing Connector README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/connector/routingconnector/README.md) - Tenant and attribute-based routing to pipelines.
- [Prometheus data model](https://prometheus.io/docs/concepts/data_model/) - Metric identity as metric name plus labels.
