---
revision_pending: false
title: "Module 1.2: OTel Collector Advanced"
slug: k8s/otca/module-1.2-otel-collector-advanced
sidebar:
  order: 3
---
> **Complexity**: `[COMPLEX]` - Multiple interacting components, pipeline logic
>
> **Time to Complete**: 60-75 minutes
>
> **Prerequisites**: Module 1 (OpenTelemetry Fundamentals), basic Kubernetes knowledge
>
> **OTCA Domain**: Domain 3 - OTel Collector (26% of exam)

---

## Learning Outcomes

After completing this module, you will be able to:

1. **Design** multi-pipeline Collector configurations that route traces, metrics, and logs through distinct receiver, processor, connector, and exporter chains.
2. **Configure** advanced processors, including `memory_limiter`, `filter`, `transform`, `tail_sampling`, and `batch`, to reduce telemetry volume while preserving critical signals.
3. **Deploy** the Collector as a Kubernetes 1.35 DaemonSet agent and Deployment gateway with resource limits, health checks, and scaling behavior that match the workload.
4. **Diagnose** Collector pipeline issues using the debug exporter, zpages, and Collector internal metrics to identify bottlenecks, drops, and exporter failures.
5. **Evaluate** OTLP transports, connectors, and Collector distributions so you can choose between gRPC, HTTP, span-derived metrics, Core, Contrib, and custom builds.

## Why This Module Matters

Hypothetical scenario: your platform team has just replaced three vendor agents with OpenTelemetry Collectors across a Kubernetes 1.35 cluster. The pods are Ready, the health endpoint returns success, and application teams are already sending OTLP traces, Prometheus-format metrics, and container logs into the new path. On Monday morning, the incident review asks why slow checkout traces are missing while noisy readiness checks still appear in the backend. The Collector did not crash, and Kubernetes did not report a failed rollout; the failure lives in the pipeline logic between receiver, processor, connector, and exporter.

That is the operational reason this module spends so much time on configuration shape. The Collector is not merely a sidecar that forwards whatever it sees. It is a programmable telemetry data plane: it receives data through multiple protocols, applies ordered processors, bridges signals through connectors, sends data to one or more backends, and exposes its own health and debugging surfaces. A configuration can be syntactically valid while still dropping the exact spans you need, duplicating cluster metrics, or making tail-sampling decisions with incomplete traces.

For the OTCA exam, Domain 3 matters because it tests whether you can reason about that data plane under constraints, not whether you can memorize a single example file. For real operations, the same skill decides whether observability becomes a reliable troubleshooting tool or another distributed system that needs debugging during an outage. In this lesson, you will build from the Collector's config anatomy to multi-signal production patterns, then practice validating a working pipeline with debug output, zpages, and internal metrics.

## Collector Architecture and Configuration Anatomy

The Collector configuration is best read as a wiring diagram rather than as a long YAML file. Receivers describe how telemetry enters, processors describe what happens to it in memory, exporters describe where it leaves, connectors bridge one pipeline into another, extensions expose supporting services, and the `service` section decides which components are actually active. A component definition by itself is only inventory; the pipeline list is the assembly line that makes it run.

That distinction prevents a common exam and production mistake. You can declare a `filter` processor, a `debug` exporter, or a `zpages` extension in the right top-level section, but none of those components affects telemetry until the `service` stanza references them. Treat the top-level component blocks like parts on a workbench, then treat `service.pipelines` as the exact order in which those parts are bolted into the machine.

```yaml
# The five building blocks of every Collector config
receivers:    # How data gets IN to the Collector
processors:   # How data gets TRANSFORMED inside the Collector
exporters:    # How data gets OUT of the Collector
connectors:   # Bridge between pipelines (output of one, input of another)
extensions:   # Auxiliary services (health checks, auth, debugging)

service:      # Wires everything together into pipelines
  extensions: [health_check, zpages]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/backend]
    metrics:
      receivers: [otlp, prometheus]
      processors: [batch]
      exporters: [prometheusremotewrite]
    logs:
      receivers: [otlp, filelog]
      processors: [batch]
      exporters: [otlp/backend]
```

The most important design rule is that processors execute in the order listed in a pipeline. A `memory_limiter` near the end is less useful because data has already accumulated in earlier processors, while `batch` near the beginning can increase memory pressure before later filters remove unwanted telemetry. The exam often presents this as a simple ordering question, but the deeper lesson is that each processor changes the risk profile of the next component.

```
┌─────────────────────────────────────────────────────────────────┐
│                      OTel Collector                             │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │Receivers │──▶│Processors│──▶│Exporters │──▶│ Backends │   │
│  │          │   │          │   │          │   │          │   │
│  │ otlp     │   │ batch    │   │ otlp     │   │ Jaeger   │   │
│  │ prometheus│   │ filter   │   │ prometheus│   │ Prometheus│   │
│  │ filelog   │   │ transform│   │ debug    │   │ Loki     │   │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Extensions: health_check, zpages, pprof, bearertokenauth  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

Notice that the diagram shows extensions beside the pipeline rather than inside it. Extensions do not transform telemetry records, but they can be essential for operating the Collector safely. Health checks make Kubernetes probes meaningful, zpages help you inspect live pipeline state, pprof supports profiling, and authentication extensions let receivers or exporters enforce basic trust boundaries before telemetry crosses namespace or network edges.

Receivers define the front door of the Collector. The OTLP receiver is the universal input for OpenTelemetry-native traffic, and it commonly listens on gRPC port 4317 and HTTP port 4318. The Prometheus receiver scrapes metrics endpoints, the filelog receiver reads node log files, the hostmetrics receiver collects local system metrics, and the Kubernetes cluster receiver reads cluster-wide state from the API server. Those receivers solve different collection problems, so you should not run all of them everywhere just because the distribution includes them.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 4       # Default: 4 MiB
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins: ["*"]       # For browser-based apps
```

When you choose between OTLP/gRPC and OTLP/HTTP, think first about the network path rather than the application language. gRPC is efficient for service-to-Collector and Collector-to-Collector traffic when you control HTTP/2 routing, but HTTP is friendlier to browsers, older proxies, and debugging with ordinary tools. If a question says a browser is sending telemetry directly, or a proxy cannot handle HTTP/2 cleanly, OTLP/HTTP is usually the pragmatic answer.

| Aspect | gRPC (:4317) | HTTP (:4318) |
|--------|-------------|-------------|
| Performance | Higher throughput, streaming | Slightly lower |
| Compression | Built-in (gzip, zstd) | Requires config |
| Firewall-friendly | No (HTTP/2, specific ports) | Yes (standard HTTP) |
| Browser support | No (needs proxy) | Yes (for web apps) |
| Best for | Service-to-collector, collector-to-collector | Browser RUM, edge ingestion |

Prometheus, file, host, and Kubernetes receivers add useful non-OTLP entry points, but they also tie the Collector to a deployment location. A filelog receiver needs node filesystem access, so it belongs on an agent DaemonSet. A `k8s_cluster` receiver reads global Kubernetes state, so running it on every node duplicates metrics and increases API pressure. Before running this, what output do you expect from each receiver if it is moved from an agent to a gateway, and which receivers would simply stop seeing their data source?

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: 'k8s-pods'
          scrape_interval: 15s
          kubernetes_sd_configs:
            - role: pod
```

Prometheus Kubernetes service discovery also needs Kubernetes API RBAC, typically `get`, `list`, and `watch` on the resource kinds it discovers, such as pods, endpoints, and services in the namespaces it scrapes.

```yaml
receivers:
  filelog:
    include: [/var/log/pods/*/*/*.log]
    operators:
      - type: json_parser
        timestamp:
          parse_from: attributes.time
          layout: '%Y-%m-%dT%H:%M:%S.%LZ'
```

```yaml
receivers:
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}
      filesystem: {}
      network: {}
      load: {}
```

```yaml
receivers:
  k8s_cluster:
    collection_interval: 30s
    node_conditions_to_report: [Ready, MemoryPressure]
    allocatable_types_to_report: [cpu, memory]
```

The `k8s_cluster` receiver is the clean example of "right component, wrong placement." It needs Kubernetes API permissions, and it observes objects that are already global from the perspective of a namespace. If you run it as a DaemonSet on every node, each agent reports similar cluster-level facts; if you run one gateway instance or one coordinated gateway Deployment, you get the same information with less duplicate work and less RBAC sprawl.

Processors are where the Collector becomes a data shaping system instead of a forwarding proxy. The `memory_limiter` protects the process before buffering grows, `batch` improves exporter efficiency, `filter` removes telemetry you intentionally do not want, `attributes` edits attributes, `transform` applies OTTL statements, and `tail_sampling` delays decisions until it can evaluate a trace. Those processors can all be valid, but the order decides whether they reduce risk or amplify it.

```yaml
processors:
  batch:
    send_batch_size: 8192         # Number of items per batch
    send_batch_max_size: 10000    # Hard upper limit
    timeout: 200ms                # Flush interval even if batch isn't full
```

The batch processor is almost always present because exporters are more efficient when they send groups of telemetry items rather than one record at a time. Batching reduces request overhead and improves compression, but it also means the Collector briefly holds more data in memory. That tradeoff is why `batch` normally appears late in a pipeline, after processors have limited memory, dropped unwanted data, and redacted fields that should not leave the cluster.

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 512                # Hard limit
    spike_limit_mib: 128          # Buffer for spikes
```

In this memory limiter example, the processor begins refusing data when memory approaches the configured limit minus the spike allowance, and it force-drops under harder pressure. That behavior is not a substitute for correct resource requests and limits, but it gives the Collector a controlled failure mode before the container is killed. It is usually better to lose some telemetry intentionally and visibly than to have Kubernetes restart the entire pipeline without preserving context.

```yaml
processors:
  filter:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.route"] == "/healthz"'     # Drop health checks
        - 'attributes["http.route"] == "/readyz"'
    metrics:
      metric:
        - 'name == "http.server.duration" and resource.attributes["service.name"] == "debug-svc"'
```

The filter processor should be treated like a firewall rule for observability data. It is powerful because it removes low-value signals close to the source, but a broad condition can silently discard evidence you will need later. Use `error_mode: ignore` so a malformed record does not stop the processor, and validate the filter with the debug exporter before sending traffic only to the long-term backend.

```yaml
processors:
  attributes:
    actions:
      - key: environment
        value: production
        action: upsert             # Insert or update
      - key: db.password
        action: delete             # Remove sensitive data
      - key: user.email
        action: hash               # Hash PII
```

Attribute processing gives you a predictable way to normalize resource and span metadata before downstream queries depend on it. Adding an `environment` attribute can make dashboards consistent, deleting a password-like attribute prevents accidental exposure, and hashing an email address preserves grouping without retaining the original value. The key operational habit is to make these transformations explicit and reviewed, because observability metadata often becomes part of alerting, retention, and cost controls.

```yaml
processors:
  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - set(attributes["deployment.env"], "prod") where resource.attributes["k8s.namespace.name"] == "production"
          - truncate_all(attributes, 256)           # Limit attribute value length
          - replace_pattern(attributes["http.url"], "token=([^&]*)", "token=***")
    metric_statements:
      - context: datapoint
        statements:
          - convert_sum_to_gauge() where metric.name == "system.cpu.time"
    log_statements:
      - context: log
        statements:
          - merge_maps(attributes, ParseJSON(body), "insert") where IsMatch(body, "^\\{")
```

OTTL, the OpenTelemetry Transformation Language, is a high-leverage exam topic because it appears wherever the Collector needs more expressive changes than simple attribute actions. Functions such as `set`, `delete`, `truncate_all`, `replace_pattern`, `merge_maps`, `ParseJSON`, and `IsMatch` let you alter telemetry based on context. The risk is that expressive rules deserve the same review discipline as application code, especially when they touch URLs, identifiers, or signal names that dashboards rely on.

```yaml
processors:
  tail_sampling:
    decision_wait: 10s              # Wait for trace to complete
    num_traces: 100000              # Traces held in memory
    policies:
      - name: errors-always
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow-traces
        type: latency
        latency: {threshold_ms: 1000}
      - name: low-volume-sample
        type: probabilistic
        probabilistic: {sampling_percentage: 10}
```

Tail sampling is different from head sampling because it waits until enough spans have arrived to judge the trace. That makes policies such as "keep all errors, keep all slow traces, sample the rest" possible, but it also means the Collector must hold traces in memory and route every span for a trace to the same decision point. Pause and predict: what do you think happens if a trace is split across two gateway replicas before tail sampling runs?

## Exporters, Connectors, and OTLP Transport Choices

Exporters are the back door of the Collector, and their behavior often determines whether a healthy-looking pipeline is actually delivering data. An OTLP exporter can send to another Collector or an observability backend, OTLP/HTTP can cross environments where gRPC is awkward, Prometheus can expose a scrape endpoint, debug can print records for validation, and file can write telemetry to disk. Each exporter has reliability and security settings that matter as much as the destination name.

```yaml
exporters:
  otlp:
    endpoint: tempo.observability.svc.cluster.local:4317
    tls:
      insecure: false
      cert_file: /certs/client.crt
      key_file: /certs/client.key
    compression: gzip              # or zstd
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s
```

The OTLP exporter is the default answer for Collector-to-Collector and Collector-to-backend communication because it preserves OpenTelemetry semantics cleanly. TLS and retry settings deserve explicit review: internal cluster traffic may use service mesh or private network controls, while traffic leaving the cluster should have transport security and clear retry limits. Unlimited retry pressure can make a backend outage worse, but no retry can turn a short network interruption into preventable data loss.

```yaml
exporters:
  otlphttp:
    endpoint: https://ingest.example.com
    compression: gzip
    headers:
      Authorization: "Bearer ${env:API_TOKEN}"
```

OTLP/HTTP is the practical choice when the network path favors ordinary HTTP handling, but the authentication example also shows why examples should use environment variables and placeholders rather than embedded secrets. A Collector ConfigMap is often visible to several platform roles, and pushing realistic credentials into examples or Git history is both unnecessary and dangerous. Keep sensitive values in Kubernetes Secrets or an external secret manager, then reference them intentionally.

```yaml
exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: otel
    resource_to_telemetry_conversion:
      enabled: true                 # Promote resource attributes to labels
```

The Prometheus exporter flips the usual push pattern into a scrape pattern. That can be useful when Prometheus is already the metrics backend, but promoting resource attributes to labels should be done carefully because label cardinality affects storage, query speed, and cost. A service name and namespace are usually helpful labels; user IDs, raw URLs, or request-specific values are almost always a problem.

```yaml
exporters:
  debug:
    verbosity: detailed            # basic | normal | detailed
    sampling_initial: 5            # First N items logged
    sampling_thereafter: 200       # Then every Nth item
```

The debug exporter is not a production backend, but it is one of the safest ways to prove a pipeline is working before you depend on it. Add it beside the real exporter during rollout, send a known trace or metric, and confirm that the transformed record looks the way you expect. Remove or reduce verbose debug output after validation because detailed telemetry logs can grow quickly and may include sensitive attributes if redaction is not complete.

```yaml
exporters:
  file:
    path: /data/otel-output.json
    rotation:
      max_megabytes: 100
      max_days: 7
      max_backups: 5
```

Connectors are special because they behave as an exporter in one pipeline and a receiver in another. The spanmetrics connector is the classic example: traces enter the traces pipeline, the connector derives RED-style metrics, and those generated metrics enter the metrics pipeline. This lets you create request rate, error, and duration metrics from trace data, but it also means dimension choices can create high-cardinality metrics if you include fields that vary per request.

```yaml
connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [5ms, 10ms, 25ms, 50ms, 100ms, 500ms, 1s, 5s]
    dimensions:
      - name: http.method
      - name: http.status_code
    namespace: traces.spanmetrics

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo, spanmetrics]     # spanmetrics is an exporter here
    metrics:
      receivers: [otlp, spanmetrics]            # spanmetrics is a receiver here
      processors: [batch]
      exporters: [prometheus]
```

Read that configuration slowly because it teaches the connector mental model better than a definition does. The traces pipeline exports to both Tempo and `spanmetrics`, while the metrics pipeline receives from both ordinary OTLP and `spanmetrics`. If you see a connector in only one side of that relationship, the derived signal will not appear where you expect it.

```yaml
connectors:
  count:
    spans:
      span.count:
        description: "Count of spans"
    logs:
      log.record.count:
        description: "Count of log records"
```

OTLP itself has two common transports, and the right answer depends on constraints rather than preference. gRPC uses HTTP/2 and Protocol Buffers, supports streaming patterns, and is a strong internal default. HTTP can use Protobuf or JSON over request-response paths such as `/v1/traces`, `/v1/metrics`, and `/v1/logs`, which makes it easier to work through proxies and easier to inspect with ordinary HTTP tooling.

| Feature | OTLP/gRPC | OTLP/HTTP |
|---------|-----------|-----------|
| Transport | HTTP/2 with Protocol Buffers | HTTP/1.1 with Protobuf or JSON |
| Port | 4317 | 4318 |
| Compression | gzip, zstd (built-in) | gzip (via Content-Encoding) |
| Streaming | Yes (bidirectional) | No (request/response) |
| Path (traces) | N/A (gRPC service) | `/v1/traces` |
| Path (metrics) | N/A | `/v1/metrics` |
| Path (logs) | N/A | `/v1/logs` |
| Proxy support | Needs HTTP/2-aware proxy | Works with any HTTP proxy |

Compression should be a deliberate exporter setting in production. Telemetry data contains repeated attribute names, service names, and resource metadata, so compression often provides meaningful bandwidth reduction. zstd can be attractive for internal traffic when supported end to end, while gzip is the more broadly compatible choice for external endpoints and mixed infrastructure.

```yaml
exporters:
  otlp:
    endpoint: gateway:4317
    compression: zstd        # Best ratio for telemetry data
  otlphttp:
    endpoint: https://ingest.example.com
    compression: gzip        # More widely supported
```

Which approach would you choose here and why: an internal agent-to-gateway path in a cluster you control, or browser-originated telemetry that must cross a corporate proxy? The first case usually favors OTLP/gRPC with efficient compression and service discovery. The second usually favors OTLP/HTTP, CORS-aware ingestion, and stricter attention to authentication and rate limits at the edge.

## Kubernetes Deployment Patterns and the Operator

Kubernetes changes the Collector design conversation because placement controls what data the Collector can see. A DaemonSet agent runs one Collector per node, which makes it good for local logs, host metrics, and near-source buffering. A Deployment gateway runs a shared pool, which makes it good for aggregation, tail sampling, routing, and backend-specific export policy. The most common production pattern uses both because neither placement solves every problem alone.

```
Agent Mode (DaemonSet)                Gateway Mode (Deployment)
──────────────────────                ─────────────────────────

┌─────────────────────┐              ┌─────────────────────┐
│      Node 1         │              │      Node 1         │
│ ┌─────┐ ┌────────┐ │              │ ┌─────┐             │
│ │App A│─▶│Collector│─┤              │ │App A│──┐          │
│ └─────┘ │(Agent) │ │              │ └─────┘  │          │
│ ┌─────┐ │        │ │              │ ┌─────┐  │          │
│ │App B│─▶│        │ │              │ │App B│──┤          │
│ └─────┘ └───┬────┘ │              │ └─────┘  │          │
└─────────────┼──────┘              └──────────┼──────────┘
              │                                │
              ▼                                │
┌─────────────────────┐                        │
│      Node 2         │              ┌─────────▼──────────┐
│ ┌─────┐ ┌────────┐ │              │  Gateway Collector  │
│ │App C│─▶│Collector│─┤───▶Backend  │  (Deployment, 2+   │
│ └─────┘ │(Agent) │ │              │   replicas)         │──▶Backend
│         └───┬────┘ │              │                     │
└─────────────┼──────┘              └─────────▲──────────┘
              │                                │
              ▼                     ┌──────────┼──────────┐
         Backend                    │      Node 2         │
                                    │ ┌─────┐  │          │
                                    │ │App C│──┘          │
                                    │ └─────┘             │
                                    └─────────────────────┘
```

The agent and gateway split is also a scaling boundary. Agents scale with nodes and provide backpressure close to workloads, while gateways scale with telemetry volume and export complexity. Tail sampling belongs at the gateway because it needs enough spans from the same trace to make a decision, and host-level collection belongs at the agent because the gateway cannot read every node's local files or system counters.

| Aspect | Agent (DaemonSet) | Gateway (Deployment) |
|--------|-------------------|---------------------|
| Deployment | One per node | Shared pool (2+ replicas) |
| Resource use | Light per node | Heavier but centralized |
| Tail sampling | Not possible (incomplete traces) | Yes (full traces arrive) |
| Host metrics | Yes (local access) | No |
| Filelog | Yes (local files) | No |
| Scaling | Scales with nodes | HPA on CPU/memory |
| Best for | Collection, basic processing | Aggregation, sampling, routing |

The simple production chain is applications to node agents, agents to gateways, and gateways to one or more backends. That shape lets you keep node-local collection simple while centralizing expensive or policy-heavy processing. It also creates a clear failure model: if a backend is unavailable, gateways can absorb retry behavior without every application or node agent needing full backend-specific logic.

```
Apps ──▶ Agent (DaemonSet) ──▶ Gateway (Deployment) ──▶ Backends
         - hostmetrics            - tail_sampling
         - filelog                - spanmetrics
         - memory_limiter         - routing
         - batch                  - export to N backends
```

Horizontal gateway scaling creates one subtle trace problem: all spans of a trace must reach the same gateway if tail sampling is enabled. Ordinary round-robin load balancing can split a trace across replicas, so each gateway sees an incomplete story and makes a poor decision. The load balancing exporter solves that by routing based on trace ID and discovering gateway instances through a resolver such as DNS.

```yaml
# On the Agent
exporters:
  loadbalancing:
    protocol:
      otlp:
        tls:
          insecure: true
    resolver:
      dns:
        hostname: otel-gateway-headless.observability.svc.cluster.local
        port: 4317
```

The OpenTelemetry Operator adds Kubernetes-native management on top of those deployment modes. Instead of hand-writing every Deployment, DaemonSet, Service, and ConfigMap, you can describe an `OpenTelemetryCollector` custom resource and let the Operator reconcile the underlying objects. It also supports auto-instrumentation through the `Instrumentation` custom resource, which is useful when application teams need a low-friction starting point.

```bash
# Install cert-manager first (required dependency)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.5/cert-manager.yaml

# Install the OTel Operator
kubectl apply -f https://github.com/open-telemetry/opentelemetry-operator/releases/latest/download/opentelemetry-operator.yaml
```

Operator-managed Collectors are still Collectors, so the same pipeline reasoning applies. The `mode` field chooses daemonset, deployment, statefulset, or sidecar, while `spec.config` contains the receiver, processor, exporter, connector, extension, and service configuration. Do not let the custom resource abstraction hide the data-flow questions you already learned to ask.

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: otel-agent
  namespace: observability
spec:
  mode: daemonset                    # daemonset | deployment | statefulset | sidecar
  image: otel/opentelemetry-collector-contrib:0.160.0
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
        limit_mib: 512
      batch: {}
    exporters:
      otlp:
        endpoint: otel-gateway.observability.svc.cluster.local:4317
        tls:
          insecure: true
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [otlp]
```

Auto-instrumentation is powerful because the Operator can inject language agents into pods through annotations, but it should be introduced with clear ownership. The application still needs compatible runtimes, predictable resource overhead, and an endpoint that can accept the resulting telemetry. Start with a small namespace or a single workload, then expand after you have verified trace quality, attribute names, and sampling behavior.

Before copying an `Instrumentation` manifest, confirm the CRD versions served by the installed Operator. The **`Instrumentation` kind is served at `opentelemetry.io/v1alpha1`**. **`OpenTelemetryCollector`** is the kind that introduced **`v1beta1`** alongside older served versions—do not confuse the two CRDs when reading exam prompts or upstream samples.

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: auto-instrumentation
  namespace: observability
spec:
  exporter:
    endpoint: http://otel-agent-collector.observability.svc.cluster.local:4318
  propagators:
    - tracecontext
    - baggage
  sampler:
    type: parentbased_traceidratio
    argument: "0.25"
  java:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:latest
  python:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:latest
  nodejs:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-nodejs:latest
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-java-app
spec:
  template:
    metadata:
      annotations:
        instrumentation.opentelemetry.io/inject-java: "true"     # Java auto-instrument
        # Other options:
        # instrumentation.opentelemetry.io/inject-python: "true"
        # instrumentation.opentelemetry.io/inject-nodejs: "true"
        # instrumentation.opentelemetry.io/inject-dotnet: "true"
    spec:
      containers:
        - name: app
          image: my-java-app:latest
```

Collector distributions matter more as you move from lab to production. The Core distribution gives you a smaller, project-maintained base; Contrib gives you broad integration coverage; a custom distribution built with the OpenTelemetry Collector Builder includes only the components you select. The exam expects you to know the tradeoff, and production security reviews usually care about it because every unused component is dependency surface.

| Distribution | Components | Use Case |
|-------------|-----------|----------|
| **Core** (`otel/opentelemetry-collector`) | ~20 components (otlp, batch, debug, etc.) | Minimal footprint, security-sensitive environments |
| **Contrib** (`otel/opentelemetry-collector-contrib`) | 200+ components (all community receivers, processors, exporters) | Development, when you need specific integrations |
| **Custom** (built with `ocb`) | Exactly what you choose | Production — include only what you use |

The Collector Builder configuration is explicit dependency management for your telemetry data plane. You declare the distribution metadata and the exact receiver, processor, and exporter modules you want compiled in. That can reduce binary size, startup time, and audit scope, but it also means you own the build process and must update the selected components as OpenTelemetry releases move forward.

```yaml
# builder-config.yaml
dist:
  name: my-collector
  description: "Production collector"
  output_path: ./dist
  otelcol_version: "0.160.0"

receivers:
  - gomod: go.opentelemetry.io/collector/receiver/otlpreceiver v0.160.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/filelogreceiver v0.160.0

processors:
  - gomod: go.opentelemetry.io/collector/processor/batchprocessor v0.160.0
  - gomod: go.opentelemetry.io/collector/processor/memorylimiterprocessor v0.160.0

exporters:
  - gomod: go.opentelemetry.io/collector/exporter/otlpexporter v0.160.0
  - gomod: go.opentelemetry.io/collector/exporter/debugexporter v0.160.0
```

```bash
# Build it
ocb --config builder-config.yaml
```

A custom Collector is not automatically better; it is better when you have a stable component set, a release process, and a reason to reduce footprint or dependency surface. During early experimentation, Contrib is often the faster path because it includes the receiver or exporter you are testing. Once the pipeline stabilizes, a custom distribution lets you remove components that were useful during discovery but unnecessary for long-term operation.

## Debugging and Operating a Multi-Signal Pipeline

Debugging a Collector starts with a basic question: did telemetry enter, change, and leave the pipeline the way you intended? Kubernetes pod health only answers whether the process is alive. The Collector's own telemetry, debug exporter, and zpages answer whether receivers accepted data, processors dropped or transformed it, exporters sent it, and extensions are running. Those signals should be present in every serious rollout plan.

```yaml
extensions:
  health_check:
    endpoint: 0.0.0.0:13133       # Liveness/readiness probe target

  zpages:
    endpoint: 0.0.0.0:55679       # Internal debug UI at /debug/tracez, /debug/pipelinez

  pprof:
    endpoint: 0.0.0.0:1777        # Go pprof profiling

  bearertokenauth:
    token: "${env:OTEL_AUTH_TOKEN}"

service:
  extensions: [health_check, zpages, pprof, bearertokenauth]
```

| Extension | Purpose | Default Port |
|-----------|---------|-------------|
| `health_check` | K8s liveness/readiness probes | 13133 |
| `zpages` | Debug UI: pipeline status, trace samples | 55679 |
| `pprof` | Performance profiling | 1777 |
| `bearertokenauth` | Authenticate incoming/outgoing requests | N/A |

The debug exporter should be used as a temporary observability mirror. When a filter, transform, or connector is introduced, add `debug` beside the real exporter and send a known test record. If the record appears before a processor but not after it, you have narrowed the failure without guessing about the backend, network policy, or dashboard query.

```yaml
exporters:
  debug:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/backend, debug]    # Add debug alongside real exporter
```

Internal telemetry is the Collector's dashboard of itself. Receiver accepted counters show whether input is arriving, processor dropped counters show whether filtering or pressure is removing data, exporter sent counters show successful output, and exporter failed counters reveal backend or network problems. These metrics let you distinguish "the app emitted nothing" from "the Collector dropped it" from "the backend rejected it."

```yaml
service:
  telemetry:
    logs:
      level: debug                  # debug | info | warn | error
      encoding: json                # For structured log parsing
    metrics:
      level: detailed               # none | basic | normal | detailed
      address: 0.0.0.0:8888        # Collector's own /metrics endpoint
```

The internal metric names are intentionally operational: `otelcol_receiver_accepted_spans` says spans arrived, `otelcol_processor_dropped_spans` says a processor removed spans, `otelcol_exporter_sent_spans` says spans left successfully, and `otelcol_exporter_send_failed_spans` says an exporter could not deliver. When you diagnose Collector pipeline issues, compare those counters by signal and pipeline before changing application instrumentation.

| Endpoint | What It Shows |
|----------|---------------|
| `/debug/pipelinez` | Active pipelines and their components |
| `/debug/tracez` | Sample traces flowing through the Collector |
| `/debug/rpcz` | gRPC call statistics |
| `/debug/extensionz` | Running extensions |

```bash
# Port-forward to access zpages
kubectl port-forward svc/otel-collector 55679:55679
# Then open http://localhost:55679/debug/pipelinez
```

The following complete configuration ties the ideas together. It receives traces, metrics, and logs, scrapes Prometheus and host metrics, filters health checks, redacts sensitive values, generates span metrics, exports to separate backends, enables health and zpages, and exposes internal metrics. It is intentionally richer than a minimal exam answer because production failures usually happen where signals and policy meet.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      scrape_configs:
        - job_name: 'k8s-pods'
          scrape_interval: 15s
          kubernetes_sd_configs:
            - role: pod
  filelog:
    include: [/var/log/pods/*/*/*.log]
    operators:
      - type: json_parser
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 1024
    spike_limit_mib: 256
  batch:
    send_batch_size: 8192
    timeout: 200ms
  filter/healthz:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.route"] == "/healthz"'
        - 'attributes["http.route"] == "/readyz"'
  transform/redact:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - replace_pattern(attributes["http.url"], "token=([^&]*)", "token=REDACTED")
    log_statements:
      - context: log
        statements:
          - replace_pattern(body, "password=\\S+", "password=***")

exporters:
  otlp/tempo:
    endpoint: tempo.observability.svc.cluster.local:4317
    tls:
      insecure: true
  otlphttp/loki:
    endpoint: http://loki.observability.svc.cluster.local:3100/otlp
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
  debug:
    verbosity: basic

connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [5ms, 10ms, 25ms, 50ms, 100ms, 500ms, 1s, 5s]
    dimensions:
      - name: http.method
      - name: http.status_code

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  zpages:
    endpoint: 0.0.0.0:55679

service:
  extensions: [health_check, zpages]
  telemetry:
    logs:
      level: info
    metrics:
      address: 0.0.0.0:8888
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, filter/healthz, transform/redact, batch]
      exporters: [otlp/tempo, spanmetrics, debug]
    metrics:
      receivers: [otlp, prometheus, hostmetrics, spanmetrics]
      processors: [memory_limiter, batch]
      exporters: [prometheus, debug]
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, transform/redact, batch]
      exporters: [otlphttp/loki, debug]
```

When reviewing a configuration like this, walk one signal at a time. For traces, OTLP input passes through memory protection, health-check filtering, redaction, batching, Tempo export, spanmetric generation, and debug output. For metrics, OTLP, Prometheus, host, and derived span metrics share a pipeline before Prometheus and debug export. For logs, OTLP and file input share redaction and batching before **OTLP/HTTP export to Loki** (`otlphttp/loki` at `http://…:3100/otlp`—Loki accepts OTLP over HTTP, not OTLP/gRPC on port 3100) and debug mirror.

That walk-through is the fastest way to find hidden mistakes. If a processor exists but is not in the relevant signal pipeline, it cannot affect that signal. If a connector appears as an exporter but not as a receiver in another pipeline, its output has nowhere useful to go. If debug output is present but backend data is missing, the exporter, backend, authentication, or network path becomes the next investigation target.

### Worked Review: Safely Changing a Collector Pipeline

Imagine that the next change request is to reduce telemetry cost while keeping enough detail for incident response. A weak review would look only for valid YAML and perhaps confirm that the Collector pod restarts cleanly. A strong review follows the trace of data through the pipeline and asks what each component can drop, transform, buffer, or duplicate. That review style is slower on the first few attempts, but it prevents expensive surprises after the Collector becomes the shared path for every team.

Start with receiver intent. If applications send OTLP directly to a gateway, the gateway can receive application spans, but it cannot read each node's container log files unless those files are mounted from the node. If agents scrape pod metrics, they need discovery permissions and a clear label strategy. If a browser sends OTLP/HTTP, CORS and authentication are not optional edge details; they are part of the receiver contract because the receiver is exposed to a different trust boundary.

Next, review processor order as a safety sequence. Memory protection should happen before expensive buffering, broad filtering should happen before backend export, redaction should happen before records cross a boundary, and batching should happen after most per-record work is complete. This order is not just about performance. It also decides which metrics you can use to explain a drop, because a processor can only report work that reaches it.

Then review every filter as if it were a production access rule. Health-check spans are usually safe to drop, but a condition that matches service names, URL prefixes, or status codes can remove evidence from real incidents. Use positive examples and negative examples when testing a filter: one record that should be dropped, one similar record that must survive, and one malformed record that proves `error_mode` behavior. Without those cases, a filter can pass a happy-path demo and still damage observability.

Transform rules deserve the same review because they can rename attributes that dashboards, alerts, and service maps already depend on. A `replace_pattern` that redacts a token is helpful; a broad `set` that overwrites a resource attribute can break grouping across an entire backend. When a transform changes names, write down the downstream query or dashboard that will consume the result, then validate that query against debug output before the change reaches a shared environment.

Sampling policy needs an even stricter placement review. Head sampling can happen near the source because the decision is made before a full trace exists, but tail sampling is a gateway concern because it uses facts discovered later in the trace. A policy that keeps errors and slow requests is only meaningful if all spans for a trace arrive at the same sampling processor. If traffic is balanced randomly across gateways, the policy is still configured but the data it evaluates is incomplete.

Connector review is about both directions of signal flow. When `spanmetrics` appears in a traces pipeline exporter list, it receives spans and creates metrics. When the same connector appears in a metrics pipeline receiver list, those created metrics enter the metrics path and can be exported. If either side is missing, the connector may look present while the derived signal never reaches the intended backend. That is why connector bugs often feel like silent failures.

Cardinality review belongs beside connector review because generated metrics can grow faster than hand-written metrics. The most tempting dimensions are often the most dangerous: raw URLs, user identifiers, pod names in short-lived workloads, or request IDs that change every call. Stable dimensions such as method, status code, route template, service name, and namespace usually preserve useful grouping without creating a new time series for every request.

Exporter review should separate delivery concerns from data-shaping concerns. If debug output shows a record after processing, the Collector produced the right payload. If the backend is missing it, investigate exporter endpoint, TLS, authentication, compression support, retries, network policy, and backend limits. Changing a filter or transform at that point can mask the real problem because the data path has already reached the exporter boundary.

Retry settings are especially easy to overlook because they sound like a reliability improvement by default. Retries help with transient network or backend failures, but they also consume memory and can increase pressure when a backend is already unhealthy. A production gateway should have retry behavior that matches backend expectations, queueing decisions that match memory limits, and alerts that distinguish temporary send failures from sustained exporter failure.

Health checks need similar humility. A successful liveness probe means the Collector process can answer the health extension; it does not mean every receiver is accepting data or every exporter is delivering it. Readiness probes are still important because Kubernetes needs a signal for rollout and restart decisions, but pipeline validation must come from the Collector's own telemetry and from known test records flowing through the configured paths.

Resource sizing should be reviewed with signal volume in mind rather than copied from a sample. A node agent that reads logs can experience spikes during crash loops, while a gateway that performs tail sampling holds trace state until `decision_wait` expires. Memory limits, spike limits, batch sizes, and sampling buffers interact, so a configuration that works for a small namespace may not survive a busy cluster without tuning.

RBAC is another placement clue. A filelog receiver needs hostPath-style access and node scheduling; a Kubernetes cluster receiver needs API permissions; an Operator-managed Collector needs permissions appropriate to the objects it reconciles. If a design grants every Collector instance broad permissions because one receiver needs them, reconsider the placement. Splitting agent and gateway responsibilities often reduces both runtime load and permission scope.

Version review matters because Collector examples age quickly. The structure in this module is stable, but component names, maturity levels, and image versions should be checked against the OpenTelemetry documentation before a production rollout. Kubernetes version 1.35 does not change the core DaemonSet and Deployment reasoning, yet clusters can differ in admission policy, Pod Security settings, and network policy that affect how the Collector is allowed to run.

Finally, write the rollback plan in terms of data flow. If a transform breaks dashboards, you should know whether to remove only that processor, remove it from one signal pipeline, or switch exporter output back to debug for validation. If gateway sampling loses traces, you should know whether the fix is routing affinity, sampling parameters, or temporarily bypassing tail sampling. A Collector rollback that simply redeploys the previous YAML may be enough, but the review should identify the smallest safe reversal.

This review pattern is also how you answer scenario questions under exam pressure. Identify the signal, locate the Collector placement, trace the pipeline order, verify connector direction, then inspect exporter and diagnostic surfaces. The details vary from question to question, but that sequence keeps you from treating a healthy pod as a healthy telemetry path or treating a backend symptom as an application instrumentation bug.

There is one more habit worth practicing before you leave the review: name the evidence that would change your mind. If you believe a filter is dropping spans, the evidence is a processor dropped counter or a debug comparison before and after that processor. If you believe the backend is rejecting data, the evidence is exporter failure metrics or backend-side rejection logs while debug output still shows processed records. Clear evidence targets keep troubleshooting from becoming a sequence of speculative YAML edits.

The same evidence mindset improves change communication. Instead of saying "we added tail sampling," say "we added gateway tail sampling, routed traces by trace ID, kept errors and slow traces, and verified accepted, dropped, sent, and failed counters during rollout." That sentence tells reviewers what changed, where it runs, why it is safe, and how the team checked it. Good Collector operations are often less about clever configuration and more about making every data-flow assumption observable.

## Patterns & Anti-Patterns

Strong Collector designs are usually boring in the best sense: node agents collect what only nodes can see, gateways perform centralized policy, processors are ordered by risk reduction, and debug surfaces stay available during rollout. The patterns below are not decorative architecture rules; they are operational shortcuts that reduce ambiguity when telemetry disappears, duplicates, or overwhelms a backend.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Agent plus gateway | Clusters with logs, host metrics, and distributed traces | Agents collect local data while gateways centralize sampling and routing | Scale agents with nodes and gateways with telemetry volume |
| Memory limiter first, batch last | Almost every traces, metrics, or logs pipeline | The Collector rejects pressure before buffering and exports efficiently after processing | Tune limits against pod memory requests and backend throughput |
| Debug mirror during rollout | New filters, transforms, connectors, or exporters | You can inspect records before blaming applications or backends | Reduce verbosity after validation to control log volume |
| Trace-ID-aware gateway routing | Tail sampling with more than one gateway replica | All spans for one trace reach the same sampling decision point | Use a headless Service or resolver strategy that exposes replicas |

Anti-patterns often begin as convenience. A team runs Contrib everywhere because it is easy, places tail sampling on agents because agents are already deployed, or leaves a broad filter untested because the Collector stayed Ready. Those choices are understandable during experiments, but they create confusion when the system becomes part of incident response.

| Anti-pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Running global receivers on every agent | Duplicate metrics and unnecessary API server load | Run cluster-wide receivers in a gateway or single coordinated instance |
| Treating health checks as pipeline validation | The process is alive even when telemetry is dropped | Use debug exporter, zpages, and internal metrics for data-flow validation |
| Using request-specific dimensions in spanmetrics | Metrics cardinality grows too quickly | Use stable dimensions such as method, status code, service, and route templates |
| Keeping broad Contrib builds forever | Larger dependency surface and unused components | Build a custom Collector once the production component set stabilizes |

## Decision Framework

Collector decisions become manageable when you separate data source, processing policy, and export constraints. First ask where the telemetry originates and which Collector placement can see it. Then decide whether records need local protection, central aggregation, sampling, redaction, derived metrics, or backend-specific routing. Finally, choose the transport and distribution that fit your network and operational maturity.

| Decision | Choose This | When the Constraints Look Like This |
|----------|-------------|-------------------------------------|
| Placement | DaemonSet agent | Node logs, host metrics, node-local buffering, or low-latency collection near workloads |
| Placement | Deployment gateway | Tail sampling, centralized routing, shared authentication, spanmetrics, or backend fan-out |
| Transport | OTLP/gRPC | Internal traffic, HTTP/2 support, high throughput, Collector-to-Collector paths |
| Transport | OTLP/HTTP | Browser telemetry, HTTP-only proxies, JSON debugging, simple edge ingestion |
| Distribution | Core | Minimal component set and security-sensitive baseline |
| Distribution | Contrib | Discovery, labs, or integrations not present in Core |
| Distribution | Custom | Stable production pipeline with explicit dependency control |

Use this mental flow when a scenario question gives you more information than you need. If the problem mentions missing complete traces after scaling gateways, look at trace routing before changing sampling policy. If it mentions duplicated cluster metrics, look at receiver placement before touching Prometheus queries. If it mentions exporter failures while debug output still shows records, focus on transport, credentials, TLS, backend availability, and retry behavior.

```
Telemetry source?
  ├─ Node-local files or host metrics ──▶ Agent DaemonSet
  │                                      └─ Forward to gateway for shared policy
  ├─ Application OTLP signals ─────────▶ Agent or gateway, based on latency and ownership
  │                                      └─ Use OTLP/gRPC internally when possible
  └─ Cluster-wide API metrics ─────────▶ Gateway or single collector instance
                                         └─ Avoid per-node duplication

Need tail sampling or spanmetrics?
  ├─ Yes ──▶ Gateway with trace-aware routing and enough memory
  └─ No ───▶ Keep processing close to source unless backend policy needs centralization
```

The framework is deliberately compact because real incidents do not wait while you admire a perfect architecture diagram. Start with visibility, then placement, then order, then export. That sequence keeps you from fixing the wrong layer, which is the most common failure mode when a Collector configuration is valid YAML but invalid operations.

## Did You Know?

- OTLP/gRPC and OTLP/HTTP use different default ports: 4317 for gRPC and 4318 for HTTP, and many exam scenarios hinge on recognizing which transport is being described.
- The `spanmetrics` connector turns trace data into RED-style metrics, so one trace pipeline can also feed request rate, error, and duration metrics into a metrics pipeline.
- The Collector has Core, Contrib, and custom distribution models; Contrib includes 200+ components, while `ocb` lets production teams compile only the components they use.
- zpages exposes live debugging paths such as `/debug/pipelinez` and `/debug/tracez` on port 55679 when the extension is enabled.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Declaring a component but not adding it to a pipeline | The top-level config reads like the component is active, but `service.pipelines` is the real wiring | Always trace the relevant signal through receivers, processors, connectors, and exporters under `service` |
| Placing `batch` before `memory_limiter` | Batching feels like a universal optimization, so it gets added first | Put `memory_limiter` early and `batch` late so pressure is controlled before buffering grows |
| Running tail sampling on agents | Agents are already deployed on every node, so sampling seems close to the source | Run tail sampling on gateways and use trace-ID-aware routing across gateway replicas |
| Running `k8s_cluster` on every node | Teams copy the same receiver set into every Collector mode | Run cluster-wide receivers in one gateway-style placement with the right RBAC |
| Forgetting `error_mode: ignore` on filter or transform processors | The rule examples work on clean data during testing | Set error handling deliberately and validate malformed or unexpected records with debug output |
| Promoting unstable attributes to Prometheus labels | Resource-to-telemetry conversion looks convenient for every attribute | Promote only bounded, stable dimensions such as service, namespace, method, and route templates |
| Treating pod readiness as proof of telemetry delivery | Kubernetes can only tell that the Collector process is responding | Check debug exporter output, zpages, and `otelcol_*` internal metrics for actual data flow |
| Keeping a broad Contrib image after the pipeline stabilizes | It speeds up early experimentation and never gets revisited | Move to a custom Collector build when component choices and release ownership are mature |

## Quiz

<details>
<summary>Question 1: Your team designs a multi-pipeline Collector configuration for traces, metrics, and logs, but the new `filter/healthz` processor is not changing trace output. What do you check first?</summary>

Check whether `filter/healthz` is listed under `service.pipelines.traces.processors`, not merely declared under the top-level `processors` block. A Collector component exists only as inventory until a pipeline references it. If the processor is present in the wrong signal pipeline, it still will not affect traces, even though the configuration can load successfully. After confirming pipeline wiring, use the debug exporter to compare records before and after the processor.
</details>

<details>
<summary>Question 2: A gateway Deployment was scaled to several replicas, and tail sampling started missing slow traces. The policy still says to keep slow traces. What design problem is most likely?</summary>

The likely problem is that spans from the same trace are being split across gateway replicas before the `tail_sampling` processor sees them. Tail sampling needs enough of the completed trace to make a correct decision, so the agent-to-gateway path should use trace-ID-aware routing such as the load balancing exporter. Changing the latency threshold would not fix incomplete trace visibility. Adding more replicas can make the issue worse unless routing preserves trace affinity.
</details>

<details>
<summary>Question 3: You configure advanced processors to reduce volume, but an exporter reports fewer spans than expected after a transform rollout. Which signals help you diagnose whether data was dropped inside the Collector or rejected by the backend?</summary>

Compare Collector internal metrics across the receiver, processor, and exporter stages. `otelcol_receiver_accepted_spans` shows whether spans entered, `otelcol_processor_dropped_spans` shows whether a processor removed them, `otelcol_exporter_sent_spans` shows successful export, and `otelcol_exporter_send_failed_spans` points toward backend or network failure. The debug exporter can also mirror representative records so you can inspect transformed attributes. This approach narrows the failure layer before you change application instrumentation.
</details>

<details>
<summary>Question 4: A Kubernetes 1.35 cluster needs container logs, host metrics, spanmetrics, and tail sampling. How would you deploy the Collector, and why?</summary>

Use a DaemonSet agent for container logs and host metrics because those data sources are node-local, then forward to a gateway Deployment for spanmetrics and tail sampling. The gateway can centralize derived metrics, sampling decisions, routing, and backend authentication. Tail sampling should not run on agents because each agent may see only part of a distributed trace. This split also lets you scale gateways independently from node count.
</details>

<details>
<summary>Question 5: A browser-based application cannot send OTLP/gRPC through the enterprise proxy, but the team still wants OpenTelemetry-native ingestion. Which OTLP transport do you evaluate, and what tradeoff do you accept?</summary>

Evaluate OTLP/HTTP on port 4318 because it works through ordinary HTTP infrastructure and supports paths such as `/v1/traces`. The tradeoff is that it may not provide the same internal throughput characteristics as gRPC, and you need to configure edge concerns such as CORS, authentication, compression, and rate limits carefully. For internal Collector-to-Collector traffic, OTLP/gRPC remains a strong default when HTTP/2 is supported. The transport choice follows the network constraint rather than a universal preference.
</details>

<details>
<summary>Question 6: Your spanmetrics connector produces far more metrics series than expected after adding request URL as a dimension. What is wrong with the design?</summary>

The connector is using an unstable, high-cardinality dimension. Raw request URLs can contain IDs, query strings, and other per-request values, so deriving metrics from them can create a large number of time series. Use stable dimensions such as `http.method`, `http.status_code`, service name, and route templates instead. The connector is useful, but it inherits the same cardinality discipline required for any metrics pipeline.
</details>

<details>
<summary>Question 7: A security review asks why production Collectors still use the Contrib distribution even though the pipeline only needs OTLP, filelog, memory limiter, batch, transform, debug, and one OTLP exporter. What should you propose?</summary>

Propose building a custom Collector with `ocb` once the component set and release process are stable. Contrib is useful during discovery because it includes many integrations, but it also ships many components the production pipeline may never use. A custom build reduces binary size and dependency surface while keeping the required receivers, processors, and exporters explicit. The proposal should include upgrade ownership, because a custom distribution must still track OpenTelemetry releases.
</details>

## Hands-On Exercise: Build a Multi-Signal Pipeline

Exercise scenario: you are preparing a small observability namespace for a team that wants one Collector receiving traces, metrics, and logs through OTLP, generating span-derived metrics, and exposing enough diagnostics to prove the pipeline works before a backend is added. The lab uses debug output instead of a vendor backend so you can focus on Collector behavior. The same validation pattern applies when you later replace `debug` with production exporters.

### Setup

You need a working Kubernetes cluster, `kubectl`, and the ability to create a namespace. The commands below use kind for a disposable local cluster, but you can skip that first command if you already have a lab cluster. Keep the Collector in an `observability` namespace so later cleanup is straightforward and the Service names match the examples.

```bash
# Create a kind cluster (skip if you already have one)
kind create cluster --name otel-lab

# Create namespace
kubectl create namespace observability
```

### Task 1: Deploy the Collector

Apply the ConfigMap, Deployment, and Service in one command. The configuration includes OTLP receivers for all signals, `memory_limiter` and `batch` processors, a `spanmetrics` connector, debug exporters, health checks, zpages, and internal metrics. Read the `service.pipelines` section before applying it so you can predict which components are active for each signal.

```bash
kubectl apply -n observability -f - <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
data:
  config.yaml: |
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
        limit_mib: 256
        spike_limit_mib: 64
      batch:
        send_batch_size: 1024
        timeout: 1s

    connectors:
      spanmetrics:
        dimensions:
          - name: http.method

    exporters:
      debug:
        verbosity: detailed

    extensions:
      health_check:
        endpoint: 0.0.0.0:13133
      zpages:
        endpoint: 0.0.0.0:55679

    service:
      extensions: [health_check, zpages]
      telemetry:
        metrics:
          address: 0.0.0.0:8888
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [debug, spanmetrics]
        metrics:
          receivers: [otlp, spanmetrics]
          processors: [memory_limiter, batch]
          exporters: [debug]
        logs:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [debug]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
spec:
  replicas: 1
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
        - name: collector
          image: otel/opentelemetry-collector-contrib:0.160.0
          args: ["--config=/etc/otel/config.yaml"]
          ports:
            - containerPort: 4317
            - containerPort: 4318
            - containerPort: 13133
            - containerPort: 55679
          volumeMounts:
            - name: config
              mountPath: /etc/otel
          livenessProbe:
            httpGet:
              path: /
              port: 13133
          readinessProbe:
            httpGet:
              path: /
              port: 13133
      volumes:
        - name: config
          configMap:
            name: otel-collector-config
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
spec:
  selector:
    app: otel-collector
  ports:
    - name: otlp-grpc
      port: 4317
    - name: otlp-http
      port: 4318
    - name: health
      port: 13133
    - name: zpages
      port: 55679
EOF
```

<details>
<summary>Solution notes for Task 1</summary>

The Deployment should create one Collector pod, and the readiness probe should pass through the health check extension. If the pod does not become Ready, inspect the logs for configuration parsing errors first because the Collector validates component names and pipeline references during startup. A successful rollout does not yet prove telemetry is flowing; it only proves the process loaded and the health extension responded.
</details>

### Task 2: Send Test Telemetry

Wait for readiness, port-forward the OTLP/HTTP Service port, and send a minimal trace payload. The payload uses a fixed service name and an HTTP method attribute so the debug exporter and spanmetrics connector have visible data to work with. Before running the curl command, predict where you expect to see the trace and which derived metric pipeline should also receive a signal.

```bash
# Wait for the collector to be ready
kubectl wait --for=condition=ready pod -l app=otel-collector -n observability --timeout=60s

# Port-forward to send data
kubectl port-forward -n observability svc/otel-collector 4318:4318 &

# Send a test trace via OTLP/HTTP
curl -X POST http://localhost:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "test-service"}}]},
      "scopeSpans": [{
        "spans": [{
          "traceId": "5b8aa5a2d2c872e8321cf37308d69df2",
          "spanId": "051581bf3cb55c13",
          "name": "GET /api/users",
          "kind": 2,
          "startTimeUnixNano": "1000000000",
          "endTimeUnixNano": "2000000000",
          "attributes": [
            {"key": "http.method", "value": {"stringValue": "GET"}},
            {"key": "http.status_code", "value": {"intValue": "200"}}
          ]
        }]
      }]
    }]
  }'
```

<details>
<summary>Solution notes for Task 2</summary>

The HTTP request should return a successful response from the Collector receiver. If it fails, check that the port-forward is still running and that the Service exposes port 4318. If the request succeeds but nothing appears in logs, verify that the traces pipeline exports to `debug` and that the Collector pod you are reading is the current Ready pod.
</details>

### Task 3: Verify Pipeline Behavior

Use three independent checks: debug logs for the trace record, zpages for active pipelines, and internal metrics for accepted spans. This triangulation is more reliable than a single check because each surface answers a different question. Logs show representative payload content, zpages show pipeline structure, and metrics show counters that can be used in alerts.

```bash
# Check collector logs — you should see the trace in debug output
kubectl logs -n observability -l app=otel-collector --tail=50

# Check zpages
kubectl port-forward -n observability svc/otel-collector 55679:55679 &
# Open http://localhost:55679/debug/pipelinez in your browser

# Check Collector's own metrics
kubectl port-forward -n observability svc/otel-collector 8888:8888 &
curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted
```

<details>
<summary>Solution notes for Task 3</summary>

You should see the test span in the Collector logs, all three pipelines listed in zpages, and receiver accepted counters in the internal metrics endpoint. If debug logs show the trace but internal metrics do not, make sure the metrics telemetry address is exposed by the pod and port-forwarded correctly. If zpages is unreachable, check that the extension is enabled under `service.extensions`, not just declared under `extensions`.
</details>

### Task 4: Explain the Production Changes

Write down the changes you would make before moving this lab pattern into production. Consider where you would split agent and gateway responsibilities, whether you would keep Contrib or build a custom Collector, which exporter would replace `debug`, how you would protect credentials, and what metrics would become alerts. This task forces you to connect the working lab to the design framework instead of treating it as a copy-paste manifest.

<details>
<summary>Solution notes for Task 4</summary>

A production design would usually run node agents for file logs and host metrics, then forward to gateways for sampling, spanmetrics, routing, and backend exports. Debug output would become temporary or sampled, credentials would move into Secrets or external secret management, and internal Collector metrics would feed alerts for accepted, dropped, sent, and failed telemetry. A stable pipeline should also consider a custom Collector distribution rather than keeping a broad Contrib image forever.
</details>

### Success Criteria

- [ ] Design multi-pipeline Collector configurations by tracing the lab's traces, metrics, and logs through the active `service.pipelines` entries.
- [ ] Configure advanced processors by explaining why `memory_limiter` appears before `batch` and where `filter`, `transform`, or `tail_sampling` would fit.
- [ ] Deploy Collector workloads in Kubernetes 1.35 and explain when this Deployment should become an agent DaemonSet, a gateway Deployment, or both.
- [ ] Diagnose Collector pipeline issues by using debug logs, zpages, and `otelcol_*` internal metrics instead of relying only on pod readiness.
- [ ] Evaluate OTLP transports, connectors, and distributions by choosing a production exporter, a spanmetrics dimension set, and Core, Contrib, or custom Collector packaging.

## Sources

- [OpenTelemetry Collector configuration](https://opentelemetry.io/docs/collector/configuration/)
- [OpenTelemetry Collector deployment](https://opentelemetry.io/docs/collector/deployment/)
- [OpenTelemetry Protocol specification](https://opentelemetry.io/docs/specs/otlp/)
- [OpenTelemetry Collector transformation documentation](https://opentelemetry.io/docs/collector/transforming-telemetry/)
- [OpenTelemetry Collector batch processor](https://github.com/open-telemetry/opentelemetry-collector/tree/main/processor/batchprocessor)
- [OpenTelemetry Collector memory limiter processor](https://github.com/open-telemetry/opentelemetry-collector/tree/main/processor/memorylimiterprocessor)
- [OpenTelemetry Collector tail sampling processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor)
- [OpenTelemetry Collector spanmetrics connector](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/connector/spanmetricsconnector)
- [OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator)
- [OpenTelemetry Collector Builder](https://opentelemetry.io/docs/collector/custom-collector/)
- [Kubernetes DaemonSet documentation](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [Kubernetes Deployment documentation](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

## Learner check

> Under `connectors.count`, metric names are map keys (`span.count`, `log.record.count`) directly under `spans` and `logs`—there is no `traces:` wrapper and no list items with `name:`.

> Instrumentation is served at opentelemetry.io/v1alpha1; OpenTelemetryCollector (not Instrumentation) added the v1beta1 API version.

> Logs export to Loki via otlphttp/loki at http://loki…:3100/otlp because Loki accepts OTLP over HTTP only, not OTLP/gRPC on :3100.

## Next Module

[OTCA Track Overview](/k8s/otca/) — Review all four OTCA domains and continue with the observability toolkit modules.
