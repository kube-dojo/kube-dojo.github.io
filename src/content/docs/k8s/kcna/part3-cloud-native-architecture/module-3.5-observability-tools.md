---
revision_pending: false
title: "Module 3.5: Observability Tools"
slug: k8s/kcna/part3-cloud-native-architecture/module-3.5-observability-tools
sidebar:
  order: 6
---

- **Complexity**: `[MEDIUM]` - Long-form observability module with tool selection and hands-on practice
- **Time to Complete**: 40-55 minutes
- **Prerequisites**: Module 3.4 (Observability Fundamentals), basic Kubernetes workloads, and a local Kubernetes 1.35+ cluster for the optional lab
- **Command style**: This module uses `alias k=kubectl` in shell examples so commands stay readable while still running the standard Kubernetes CLI

## What You'll Be Able to Do

After completing this module, you will be able to:

1. **Diagnose** observability gaps by choosing Prometheus, Grafana, Fluent Bit, Fluentd, Jaeger, Loki, Tempo, or OpenTelemetry for a cluster symptom.
2. **Compare** pull-based and push-based metrics collection approaches, including when the Prometheus Pushgateway is appropriate.
3. **Design** an OpenTelemetry collection path that routes metrics, logs, and traces without locking application code to one backend.
4. **Evaluate** Kubernetes-specific signals from Metrics Server, kube-state-metrics, and application metrics when debugging cluster behavior.

## Why This Module Matters

**Hypothetical scenario:** during a holiday traffic surge, an online retailer watches successful checkouts collapse while every Kubernetes Deployment still reports the expected replica count. The public status page stayed green for several minutes because the cluster was alive, the Pods were running, and the nodes had spare CPU. The real failure sat between the payment service and a database connection pool that had quietly saturated after a configuration rollout. Revenue leaked away while engineers bounced between shell sessions, raw logs, and a dashboard that only showed node utilization. The expensive part of the incident was not the bug itself; it was the time spent proving where the bug was not.

That pattern is common in cloud native systems because Kubernetes separates components so effectively that no single component tells the whole story. A Pod can be running while its request latency is terrible, a Service can have endpoints while every request returns a server error, and a cluster can have enough CPU while a downstream dependency is stalled. Observability tools exist to shorten the path from symptom to evidence. They do not replace engineering judgment, but they give that judgment reliable instruments: metrics for trends, logs for events, traces for request paths, and dashboards that bring those signals into one workflow.

KCNA does not expect you to operate every observability product as a specialist. It does expect you to recognize which tool solves which problem, why Prometheus usually pulls metrics instead of waiting for applications to push them, how Grafana differs from the data stores it visualizes, why Fluent Bit is often deployed on every node, and how OpenTelemetry reduces instrumentation churn across languages and vendors. This module turns the tool list into an operational map so you can answer exam scenarios and make defensible choices in a real Kubernetes 1.35+ environment.

## Observability Stack Overview

Observability begins with the question a tired engineer asks during an incident: "What changed, where did it hurt, and which evidence proves it?" Metrics answer the shape of the problem over time, logs preserve discrete events, and traces reconstruct the route a request took through services. The tools in this module specialize around those signals, but the important idea is not the brand name. The important idea is that each signal has a different cost model, query model, and failure mode, so a healthy stack deliberately combines them instead of pretending one signal can do every job.

The original stack diagram below is worth reading from bottom to top. Applications and Kubernetes components emit telemetry, collectors normalize or forward that telemetry, storage systems keep each signal in a form that can be queried, and Grafana or a similar visualization layer lets humans correlate the evidence. Notice that "observability stack" does not mean one giant product. It usually means several small contracts: scrape metrics, ship logs, export traces, query stores, route alerts, and preserve enough context that a responder can move from a symptom to a cause.

```text
┌─────────────────────────────────────────────────────────────┐
│              TYPICAL OBSERVABILITY STACK                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              VISUALIZATION                           │   │
│  │  ┌────────────────────────────────────────────────┐ │   │
│  │  │                 GRAFANA                         │ │   │
│  │  │  Dashboards for metrics, logs, traces          │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│         ┌───────────────┼───────────────┐                  │
│         ▼               ▼               ▼                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  METRICS    │ │   LOGS      │ │   TRACES    │          │
│  │             │ │             │ │             │          │
│  │ Prometheus  │ │ Loki        │ │ Jaeger      │          │
│  │ or          │ │ or          │ │ or          │          │
│  │ Mimir       │ │ Elasticsearch│ │ Tempo      │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│         ▲               ▲               ▲                  │
│         │               │               │                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              COLLECTION                              │   │
│  │                                                      │   │
│  │  Metrics: Prometheus scrapes / OpenTelemetry       │   │
│  │  Logs: Fluentd / Fluent Bit / OpenTelemetry       │   │
│  │  Traces: OpenTelemetry / Jaeger agent             │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ▲                                   │
│                         │                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              APPLICATIONS                            │   │
│  │  [Pod] [Pod] [Pod] [Pod] [Pod] [Pod]              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Think of a Kubernetes cluster like a hospital with many specialized instruments. Prometheus is the heart-rate monitor that measures numeric signals repeatedly, while logs are the medical chart that records specific events and decisions. Jaeger or Tempo is closer to an imaging scan because it follows one request through the body of the system. Grafana is the central screen at the nurses' station: it does not create every measurement, but it lets a responder compare measurements without walking room to room.

The tradeoff is that every instrument can be misused. Metrics are compact and cheap enough to retain for weeks, but they hide individual examples behind aggregation. Logs contain concrete messages, but large clusters produce enough log volume to make careless indexing expensive. Traces show causality across service boundaries, but they require consistent context propagation and sampling decisions. Pause and predict: if a checkout service starts timing out only for one downstream dependency, which signal would show the trend first, and which signal would prove the exact request path that failed?

A practical observability workflow works like a ladder. Start with the broadest signal that can confirm user impact, then climb toward the narrower signal that explains cause. Metrics are usually first because a responder can see whether request rate, error rate, latency, saturation, or replica availability changed at the same time as the incident. Logs often come next because they show specific error messages, configuration values, and dependency responses. Traces become decisive when several services participate in one user action and the team needs to locate the slow or failing hop.

This ladder is also a cost-control technique. If every investigation begins by searching all logs across all namespaces, the logging backend becomes the most expensive part of the stack and responders still drown in irrelevant lines. If every investigation begins with one dashboard that points to a service, namespace, pod, route, and time window, later log and trace queries can be narrow. Good observability design therefore reduces both incident time and infrastructure spend by using cheap aggregate signals to guide expensive detailed queries.

The ladder should be practiced before an outage, not invented during one. Teams can rehearse by taking a recent deployment, selecting one user-facing operation, and asking which dashboard proves that operation is healthy. Then they can follow the link from the metric panel to logs and from logs to traces, checking whether labels and correlation fields survive each step. If the path breaks during rehearsal, the fix is usually straightforward: add a label, adjust a dashboard variable, propagate a trace header, or document the correct namespace.

## Prometheus, Metrics, and Alerting

Prometheus is the dominant cloud native metrics system because it made a few opinionated choices that fit dynamic infrastructure. Instead of asking every application to know where the monitoring server lives, Prometheus discovers targets and scrapes their `/metrics` endpoints on a schedule. That pull model gives Prometheus an independent view of liveness: if a target disappears, the scrape fails, and the monitoring system can alert on the absence of data. A push-only system can accidentally hide a dead target because the dead process is no longer around to report that it died.

The pull model also matches Kubernetes service discovery. Pods come and go, Services point at changing endpoint sets, and labels describe roles better than fixed hostnames do. Prometheus can watch Kubernetes metadata, find scrape targets that match configured labels or annotations, and attach useful labels such as namespace, pod, container, and service. The result is a time-series database where each sample has a metric name, a timestamp, a value, and labels that explain which workload produced it.

That discovery behavior is why Prometheus feels native in Kubernetes even when the application itself knows very little about the cluster. A Deployment scales from two Pods to ten, the endpoints change, and Prometheus can discover the new targets through Kubernetes metadata rather than through hand-maintained host lists. The operational contract moves from "configure every host" to "label workloads consistently and expose a scrapeable endpoint." This is easier to automate, but it also means label hygiene becomes part of observability hygiene.

```text
┌─────────────────────────────────────────────────────────────┐
│              PROMETHEUS                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CNCF Graduated project for metrics                       │
│                                                             │
│  Key characteristics:                                      │
│  ─────────────────────────────────────────────────────────  │
│  • Pull-based model (scrapes targets)                     │
│  • Time-series database                                    │
│  • PromQL query language                                  │
│  • AlertManager for alerting                              │
│                                                             │
│  How it works:                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                      │   │
│  │  ┌──────────┐                                       │   │
│  │  │Prometheus│ ──── scrape ────→ /metrics endpoint  │   │
│  │  │  Server  │                                       │   │
│  │  │          │ ←─── metrics ────  Target (Pod)      │   │
│  │  └──────────┘                                       │   │
│  │       │                                              │   │
│  │       ├──→ Store time series data                   │   │
│  │       ├──→ Evaluate alert rules                     │   │
│  │       └──→ Respond to PromQL queries               │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  PromQL example:                                          │
│  ─────────────────────────────────────────────────────────  │
│  rate(http_requests_total[5m])                           │
│  "Requests per second over last 5 minutes"               │
│                                                             │
│  histogram_quantile(0.99, sum by (le) (rate(              │
│    request_duration_seconds_bucket[5m])))                │
│  "99th percentile latency"                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Prometheus stores data as time series, which is powerful when labels are bounded and dangerous when labels are unbounded. A metric such as `http_requests_total{status="500",method="POST",service="checkout"}` stays manageable because each label has a small set of values. A metric that includes a user ID, session ID, order ID, or raw URL path can create a new series for every customer interaction. That is called high cardinality, and it can exhaust memory long before the application itself looks busy.

Metric type matters as much as metric name. Counters are for values that only increase, such as total requests or total errors, and PromQL functions such as `rate()` turn that ever-growing number into a per-second trend. Gauges are for values that can rise or fall, such as queue depth, current connections, or memory usage. Histograms group observations into buckets so teams can estimate latency percentiles without storing every request. Choosing the wrong type creates misleading graphs even when collection is technically working.

| Component | Purpose |
|-----------|---------|
| **Prometheus Server** | Scrapes and stores metrics |
| **AlertManager** | Handles alerts, routing, silencing |
| **Pushgateway** | For short-lived jobs (push metrics) |
| **Exporters** | Expose metrics from systems |
| **Client libraries** | Instrument your code |

The Pushgateway is the exception that proves the pull-model rule. It exists for service-level batch jobs that run briefly, finish successfully, and disappear before Prometheus can reliably scrape them. A backup verification Job might push its final success metric to the Pushgateway before exiting, and Prometheus later scrapes the Pushgateway like any other target. It is not a general way to make long-running services push metrics, because then Prometheus loses the simple "scrape failed" signal that tells you a target is down.

The key phrase is service-level batch job, not "anything short-lived." If a Kubernetes Job represents a specific business activity such as nightly reconciliation, publishing a final success or duration metric can be useful. If the metric represents a machine instance, a one-off Pod, or a workflow whose lifecycle is already visible in Kubernetes events, pushing can create stale series that appear healthy after the producer is gone. Treat Pushgateway usage as a design decision that needs cleanup semantics, ownership, and clear labels.

Before running any PromQL, ask what decision the query should support. `rate(http_requests_total[5m])` is useful when you need traffic velocity, while `histogram_quantile(0.99, sum by (le) (rate(request_duration_seconds_bucket[5m])))` is useful when the slowest user experiences matter more than the average. If an alert fires from a single instant sample, it may flap during normal spikes. If it waits too long, responders learn about customer pain after the business does. The art is choosing a window that matches the symptom and the operational action.

**Hypothetical scenario:** a team tracks HTTP requests by adding the user's unique ID as a Prometheus label, producing samples like `http_requests_total{user_id="12345"}`. When the application grew quickly, Prometheus created millions of unique label combinations, which meant millions of time series. Memory usage climbed until Prometheus crashed, and the monitoring outage hid the application outage. The fix was not a bigger dashboard; it was a better metric design that used bounded labels such as status code, route template, method, and service.

Metrics become operational only when they are connected to alerting. Grafana can alert, and many teams use it, but the Prometheus ecosystem includes Alertmanager for grouping, deduplicating, silencing, and routing alerts. The difference matters during an incident because ten alerts about one failing dependency should become one actionable page, not ten independent interruptions. A good alert states customer impact, likely ownership, and a first query to run; a bad alert merely says a graph crossed a line.

Alert rules should be written from symptoms, not from every metric that looks interesting. A node running hot for one minute may deserve a dashboard annotation, while sustained API error rate for paying customers deserves a page. Alertmanager helps only after teams define those human expectations: severity, route, silence policy, grouping key, and escalation path. If those decisions are missing, adding more alert rules simply teaches responders to ignore the monitoring system, which is worse than having fewer alerts with higher trust.

One useful review question is whether the alert names the action it expects. "CheckoutErrorBudgetBurning" points responders toward customer impact and service ownership, while "PodRestartsHigh" may or may not require immediate action depending on workload behavior. Infrastructure alerts are still necessary, but they should be tied to a consequence such as lost capacity, degraded redundancy, or imminent data loss. Prometheus and Alertmanager provide the machinery; humans still need to encode which symptoms deserve interruption.

## Grafana, Logs, and Traces in the Debugging Workflow

Grafana is often described as a dashboard tool, but in practice it is a correlation workspace. Prometheus has its own expression browser, Loki has log queries, and Jaeger has a trace UI, yet responders lose time when every signal lives in a separate tab with different filters. Grafana connects to many data sources so a dashboard can show request rate from Prometheus, error logs from Loki, and request traces from Jaeger or Tempo in one place. That does not make Grafana the source of truth for the data; it makes Grafana the place where humans compare evidence.

The dashboard diagram below preserves the original module's key distinction. Grafana visualizes and explores signals; it does not replace Prometheus, Loki, Elasticsearch, Jaeger, or Tempo as storage systems. This is a common KCNA trap. If the question asks which tool stores and queries time-series metrics, Prometheus is the answer. If the question asks which tool provides dashboards across metrics, logs, and traces, Grafana is the answer. If the question asks why an engineer can move from a metric spike to related logs without leaving the browser, the answer is cross-source correlation.

```text
┌─────────────────────────────────────────────────────────────┐
│              GRAFANA                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Visualization and dashboarding (not CNCF, but essential) │
│                                                             │
│  What Grafana does:                                        │
│  ─────────────────────────────────────────────────────────  │
│  • Create dashboards                                       │
│  • Query multiple data sources                            │
│  • Alerting (also has its own alerting)                   │
│  • Explore mode for ad-hoc queries                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Dashboard: Application Overview                    │   │
│  │  ┌────────────────────────────────────────────────┐ │   │
│  │  │  Request Rate          Error Rate              │ │   │
│  │  │  ┌────────────┐        ┌────────────┐         │ │   │
│  │  │  │ ▂▃▅▇█▇▅▃▂ │        │ ▂▁▁▃▁▁▁▁▂ │         │ │   │
│  │  │  │  1.2k/s   │        │   0.5%    │         │ │   │
│  │  │  └────────────┘        └────────────┘         │ │   │
│  │  ├────────────────────────────────────────────────┤ │   │
│  │  │  Latency p99: 245ms   Active Pods: 5          │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Data sources supported:                                  │
│  • Prometheus                                              │
│  • Loki (logs)                                            │
│  • Jaeger/Tempo (traces)                                  │
│  • Elasticsearch                                          │
│  • And many more...                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Logs answer questions that metrics intentionally compress away. A metric can tell you that the checkout service returned more 500 responses, but a log line can show that the database driver reported "connection timeout" after the pool limit changed. Kubernetes encourages logging to stdout and stderr because the container runtime can write those streams to node files, and node-level agents can collect them without modifying every application. Fluent Bit and Fluentd are common collectors in that layer, with Fluent Bit favored when each node needs a lightweight agent.

Useful logs are structured enough to filter and plain enough for humans to read under pressure. A line that says "payment failed" is less useful than a structured event with service, route, status, dependency, latency, and a safe correlation ID. At the same time, logs should not contain passwords, raw tokens, payment details, or personal data that creates a security incident inside the observability system. The collector can enrich and route events, but application teams still own whether the message explains the operational fact that matters.

```text
┌─────────────────────────────────────────────────────────────┐
│              LOGGING TOOLS                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FLUENTD (CNCF Graduated)                                 │
│  ─────────────────────────────────────────────────────────  │
│  • Unified logging layer                                  │
│  • Collects from many sources                             │
│  • Routes to many destinations                            │
│  • Plugin ecosystem                                        │
│                                                             │
│  FLUENT BIT (CNCF Graduated, part of Fluentd)            │
│  ─────────────────────────────────────────────────────────  │
│  • Lightweight version of Fluentd                        │
│  • Lower resource usage                                   │
│  • Better for edge/resource-constrained                  │
│                                                             │
│  Typical flow:                                            │
│  ─────────────────────────────────────────────────────────  │
│  Container stdout → Fluent Bit → Elasticsearch/Loki     │
│                                                             │
│  LOKI (Grafana Labs)                                      │
│  ─────────────────────────────────────────────────────────  │
│  • Log aggregation system                                 │
│  • Designed to be cost-effective                         │
│  • Only indexes metadata (labels)                        │
│  • Pairs with Grafana                                     │
│                                                             │
│  ELK/EFK Stack:                                           │
│  ─────────────────────────────────────────────────────────  │
│  • Elasticsearch (storage)                               │
│  • Logstash/Fluentd (collection)                        │
│  • Kibana (visualization)                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The logging storage choice changes both cost and search behavior. Elasticsearch indexes log content deeply, which makes full-text search powerful but can require significant CPU, memory, and storage planning. Loki takes a different approach by indexing labels and storing log content more cheaply, which works well when labels such as namespace, pod, app, and cluster narrow the search before you inspect text. Neither design is universally better. A compliance-heavy team with arbitrary audit searches may pay for full-text indexing, while a platform team debugging Kubernetes services may prefer Loki's lower operating cost.

Collectors are also part of reliability, not just plumbing. A Fluent Bit DaemonSet that cannot buffer during a backend outage may drop the exact logs needed to investigate that outage. A collector with unlimited buffering may fill node storage and create a second incident. Production designs should decide what happens when the destination is slow: whether to retry, sample, spill to disk, drop low-priority logs, or backpressure the source. Those decisions are uncomfortable, but making them explicitly is better than discovering defaults during a major failure.

Log retention should follow investigation needs rather than habit. Short retention may be fine for noisy debug logs if metrics and traces identify recent incidents quickly, while security or audit events may need a longer lifecycle with tighter access controls. Retaining everything forever is rarely the responsible choice because it increases cost and data exposure. A sensible policy separates high-value operational logs, compliance logs, and low-value noise, then gives each class a retention and indexing strategy that matches its purpose.

Tracing fills a different gap: it follows one request across service boundaries. In a monolith, a stack trace often tells the whole story. In microservices, one checkout request may pass through an ingress controller, API gateway, cart service, payment service, fraud service, and database proxy before the user sees a result. A trace keeps a shared trace ID and span context across those hops so the trace backend can draw a waterfall that shows where latency accumulated or where an error originated.

Sampling is the main tracing tradeoff for busy systems. Capturing every trace may be excellent for debugging but unaffordable at high traffic, while sampling too aggressively may miss rare failures. Many teams keep a baseline sample of successful requests and retain a higher percentage of errors, slow requests, or high-value transactions. The important KCNA-level idea is that tracing is not magic packet capture. It depends on applications and middleware propagating context, creating spans, and exporting those spans to a collector or backend.

```text
┌─────────────────────────────────────────────────────────────┐
│              TRACING TOOLS                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  JAEGER (CNCF Graduated)                                  │
│  ─────────────────────────────────────────────────────────  │
│  • End-to-end distributed tracing                         │
│  • Originally from Uber                                   │
│  • OpenTracing-compatible (historical); Jaeger v2 on OTel Collector │
│  • Service dependency analysis                            │
│                                                             │
│  Components (v1 legacy; v2 uses OTel Collector):           │
│  • Jaeger Client / OTel SDK (in your app)                │
│  • Jaeger Agent (per node — removed in Jaeger v2)        │
│  • Jaeger Collector                                       │
│  • Jaeger Query/UI                                        │
│                                                             │
│  TEMPO (Grafana Labs)                                     │
│  ─────────────────────────────────────────────────────────  │
│  • Cost-effective trace storage                          │
│  • Only stores trace IDs and spans                       │
│  • Integrates with Grafana                               │
│                                                             │
│  ZIPKIN                                                   │
│  ─────────────────────────────────────────────────────────  │
│  • One of the first distributed tracers                  │
│  • Originally from Twitter                               │
│  • Simple to set up                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Worked example: at 3:00 AM, an alert reports `HighErrorRate` for the payment service. In Grafana, the responder confirms that error rate rose sharply after a rollout and then filters the Prometheus panels by namespace and pod. The related Loki logs show connection timeouts from one payment Pod, and a trace ID in the log opens a Jaeger view where the payment span spends most of its time waiting on the database. The fix may still require application knowledge, but the observability workflow turned a vague page into a concrete dependency path.

That example also shows why a "single pane of glass" should not mean a single undifferentiated screen. The useful part is shared context: the same time range, namespace, release, service, pod, and trace ID can travel between panels and tools. A dashboard that mixes unrelated platform graphs, business graphs, and infrastructure graphs can slow responders down. A dashboard that starts with service health and links outward to focused logs and traces gives responders a path instead of a wall of charts.

Pause and predict: if you deploy Fluent Bit as three replicas in a Deployment on a 20-node cluster, which nodes will have their container logs collected? The answer is only the nodes where those three Pods happen to land, because the log files live on each node's filesystem. That is why log agents commonly run as DaemonSets. The scheduling pattern follows the data location, not the desired replica count.

## OpenTelemetry as the Instrumentation Contract

OpenTelemetry matters because tool choice changes faster than application code should. Before OpenTelemetry, a service might use one library for Prometheus metrics, another for Jaeger traces, and a separate logging convention that varied by language. Replacing a backend could require touching every service, every runtime, and every build pipeline. OpenTelemetry offers vendor-neutral APIs, SDKs, semantic conventions, and the Collector so teams can instrument code once and route telemetry to the backend that fits the current platform.

The Collector is the practical centerpiece of that design. Applications can export OpenTelemetry Protocol data to a nearby Collector, and the Collector can receive, process, batch, filter, enrich, and export telemetry to systems such as Prometheus, Jaeger, Tempo, Loki, or a vendor service. This gives platform teams a control point outside the application binary. If trace sampling needs adjustment during an incident, or if a team migrates from Jaeger storage to Tempo, the preferred change is a Collector pipeline change rather than a code release across every service.

Collector configuration is usually described as receivers, processors, exporters, and pipelines. Receivers accept telemetry from applications, agents, or scrape targets. Processors can batch, filter, redact, add resource attributes, or sample telemetry before it leaves the cluster. Exporters send the processed data to one or more destinations. Pipelines wire those pieces together per signal type, so a metrics pipeline can behave differently from a traces pipeline even when both enter the same Collector.

```text
┌─────────────────────────────────────────────────────────────┐
│              OPENTELEMETRY                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CNCF Graduated project - THE unified standard          │
│                                                             │
│  What it provides:                                         │
│  ─────────────────────────────────────────────────────────  │
│  • APIs for instrumenting code                            │
│  • SDKs for multiple languages                            │
│  • Collector for receiving/processing telemetry          │
│  • Unified protocol (OTLP)                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                      │   │
│  │  [App with OTel SDK] ──→ [OTel Collector] ──→      │   │
│  │                              │                      │   │
│  │                    ┌─────────┼─────────┐            │   │
│  │                    ▼         ▼         ▼            │   │
│  │              Prometheus   Jaeger    Loki            │   │
│  │              (metrics)   (traces)  (logs)          │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Why OpenTelemetry matters:                               │
│  ─────────────────────────────────────────────────────────  │
│  • Vendor neutral (switch backends easily)               │
│  • Single instrumentation for metrics+traces+logs        │
│  • Replaces OpenTracing and OpenCensus                  │
│  • Becoming the industry standard                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

OpenTelemetry does not eliminate the need to understand each signal. Metrics still need careful naming and bounded attributes, logs still need useful structure without secret leakage, and traces still need context propagation across process boundaries. What it changes is the ownership boundary. Application developers can use language-specific OTel SDKs and semantic conventions, while platform engineers manage Collector pipelines, exporters, resource detection, and backend routing. That division is healthier than forcing every product team to become an expert in every backend.

This ownership split works best when the platform publishes a small contract. For example, every service must set a service name, environment, version, and namespace; HTTP spans must use standard semantic attributes; and logs must include a correlation field that can connect them to traces when available. The platform can then build dashboards, retention policies, and alert routes around consistent metadata. Without that contract, OpenTelemetry may still collect data, but the data will be difficult to compare across teams.

The unified standard is especially valuable in mixed-language organizations. A Go service, a Java service, and a Python service can all emit spans with consistent attributes such as service name, HTTP method, status code, and Kubernetes namespace. When those services participate in one request, the trace backend can stitch the spans together because the context travels in standardized headers. Before running this in a real cluster, ask what output you would expect if one service forgets to propagate trace context; the trace will split, and the dependency path will look broken even when the network is fine.

For KCNA, remember that OpenTelemetry is about instrumentation and telemetry pipelines, not just another dashboard. It complements Prometheus, Grafana, Jaeger, Loki, Tempo, Fluent Bit, and Fluentd. In some deployments it can collect all three signal types; in others it handles traces and metrics while Fluent Bit still handles node-level log files. A strong answer explains the interface: application or agent emits telemetry, Collector processes it, backend stores it, and visualization or alerting tools help humans act on it.

Migration stories are where OpenTelemetry's value becomes visible. A company may begin with Jaeger because it is familiar and later choose Tempo because it integrates cleanly with its Grafana-based stack. If applications exported directly to Jaeger-specific clients, that migration could require service-by-service code changes and coordinated releases. If applications use OpenTelemetry and export to a Collector, the migration can be staged by adding a second exporter, validating data, switching dashboards, and then retiring the old destination.

## Kubernetes-Specific Observability Signals

Kubernetes adds its own layer of signals, and the distinction between resource metrics, object state, and application behavior is exam-important. Metrics Server supplies the lightweight CPU and memory metrics used by `k top` and the Horizontal Pod Autoscaler. It is not a historical time-series database, and it is not a replacement for Prometheus. It answers immediate resource questions such as "how much CPU is this Pod using now?" rather than questions such as "what was p99 checkout latency during yesterday's release?"

kube-state-metrics exports Kubernetes object state as Prometheus metrics. Instead of measuring container CPU directly, it reports facts from the Kubernetes API such as desired replicas, available replicas, Pod phases, node conditions, and resource requests. That is valuable because many outages are control-plane or rollout-state problems rather than raw resource problems. A Deployment with desired replicas set to eight and available replicas stuck at three tells a different story from a Deployment with eight healthy Pods that all return application errors.

This distinction prevents a common debugging mistake: treating "Kubernetes is healthy" as the same as "the service is healthy." Kubernetes can schedule Pods, attach Services, and report readiness while the application returns the wrong answer to users. Conversely, an application can be healthy but under-provisioned because scheduling, quota, or autoscaling is stuck. Metrics Server, kube-state-metrics, and application metrics are not competing truth sources. They are different layers of the same operational picture.

```text
┌─────────────────────────────────────────────────────────────┐
│              KUBERNETES OBSERVABILITY                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Built-in Kubernetes metrics:                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  METRICS SERVER                                           │
│  • Resource metrics (CPU, memory)                        │
│  • Used by kubectl top                                   │
│  • Used by HPA for autoscaling                          │
│                                                             │
│  KUBE-STATE-METRICS                                       │
│  • Kubernetes object state                               │
│  • Deployment replicas, Pod status, etc.                │
│  • Complements metrics server                            │
│                                                             │
│  Example queries:                                         │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  # Pod resource usage                                     │
│  container_memory_usage_bytes{pod="my-app-xyz"}         │
│                                                             │
│  # Deployment availability                                │
│  kube_deployment_status_replicas_available               │
│  {deployment="frontend"}                                  │
│                                                             │
│  # Node conditions                                        │
│  kube_node_status_condition{condition="Ready"}           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Application metrics complete the picture by measuring behavior Kubernetes cannot infer. The API server can tell you that a Pod is Ready, but it cannot know whether the checkout endpoint is meeting a 300 ms latency target unless the application exposes that metric. The kubelet can report memory usage, but it cannot know that successful payment attempts fell after a feature flag changed. This is why mature dashboards usually combine cluster health, workload state, and service-level indicators instead of treating Kubernetes readiness as a business-health signal.

Service-level indicators make that combination concrete. Request success rate, request latency, throughput, and saturation are common starting points because they connect infrastructure behavior to user experience. Kubernetes readiness can protect traffic routing, but it is often a coarse local check. A service-level dashboard should ask whether users can complete the important operation, whether the operation is fast enough, and whether the system has enough headroom to keep doing it. That is a different question from whether containers exist.

Here is a compact way to evaluate the layers during debugging. If autoscaling fails, check Metrics Server and HPA events first because the autoscaler depends on that pipeline. If a rollout stalls, inspect kube-state-metrics or Kubernetes status fields because the issue may be scheduling, readiness, image pull, or replica availability. If customers see errors while Kubernetes looks healthy, pivot to Prometheus application metrics, logs, and traces because the failure likely lives above the orchestration layer.

The same symptom can cross layers, so avoid stopping at the first plausible explanation. High latency might come from CPU throttling, a bad rollout, a slow dependency, noisy neighbors, a broken cache, or a network policy that sends traffic through an unexpected path. A disciplined responder moves through evidence: resource metrics, object state, application metrics, logs, and traces. Each step either narrows the hypothesis or rules out a layer, which is far more reliable than guessing from the loudest dashboard.

This layered view also helps during design reviews. When a new service launches, ask how Kubernetes will show scheduling and readiness, how Prometheus will show request behavior, how logs will expose dependency errors, and how traces will cross service boundaries. If any layer lacks an answer, the team has found an observability gap before users find it. That habit turns observability from a post-incident cleanup task into part of the definition of production readiness.

```bash
alias k=kubectl
k top pods -n monitoring
k get deploy -n monitoring
k describe hpa -n default
```

The alias setup above is just a shell shortcut, not a different tool. It matters here because KCNA scenarios often use the full command name in prose, while KubeDojo labs use `k` to keep repeated commands readable. When you see `k get` or `k top`, read it as the standard Kubernetes CLI against a Kubernetes 1.35+ cluster. If a lab command fails, the troubleshooting question is still about Kubernetes state, RBAC, namespaces, and installed components, not about a custom wrapper.

## Patterns & Anti-Patterns

Reliable observability stacks grow from boring patterns. Put node-local log collectors near node-local files, scrape metrics from stable endpoints, keep label cardinality bounded, and keep dashboards tied to operational decisions. The pattern is not "install every tool." The pattern is "make each tool answer a specific question faster than a human could answer it with raw shell commands." A cluster with fewer tools and clear ownership often outperforms a cluster with many products and no disciplined signal design.

Ownership is the hidden pattern behind the visible tools. Platform teams usually own the shared collectors, storage backends, dashboards, and alert-routing infrastructure. Application teams own whether their services expose useful metrics, write meaningful logs, and propagate trace context. Security teams care about retention, access, and data leakage. When those ownership lines are explicit, observability changes can be reviewed like any other production change rather than treated as an afterthought attached to incidents.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Prometheus scrapes application and Kubernetes metrics | Services expose `/metrics`, exporters exist, or kube-state-metrics is installed | Pull-based collection gives an independent failure signal and fits Kubernetes discovery | Keep labels bounded and plan retention or remote storage before cardinality grows |
| Fluent Bit runs as a DaemonSet | Container stdout and stderr logs live on each node | One agent per node can read local log files and follow Pods as scheduling changes | Set CPU and memory limits so logging does not compete with workloads during bursts |
| OpenTelemetry Collector sits between apps and backends | Teams need vendor-neutral instrumentation or multi-language consistency | The Collector centralizes batching, processing, sampling, and exporter choices | Treat Collector configuration as production code and test changes before rollout |
| Grafana correlates multiple data sources | Responders need metrics, logs, and traces in one investigation path | Shared filters and linked panels reduce context switching during incidents | Keep dashboards focused on decisions, not every metric the stack can emit |

The matching anti-patterns usually come from confusing installation with observability. A team may have Prometheus but no alert routing, Grafana but no service-level panels, logs but no useful labels, or traces that break at the first service boundary. These failures feel subtle because the tools are technically present. During a real outage, however, the missing contract appears as slow diagnosis, noisy pages, expensive storage, or dashboards nobody trusts.

Another useful test is whether a new engineer can follow an incident path without tribal knowledge. If the only person who knows which dashboard matters is on vacation, the stack is fragile even if all components are running. Namespaces, dashboard folders, alert labels, runbook links, and trace fields should make ownership discoverable. Observability should reduce dependence on memory during stressful moments, not require responders to remember a private map of every service.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Treating Metrics Server as a Prometheus replacement | HPA and `k top` work, but there is no historical application telemetry | Use Metrics Server for resource metrics and Prometheus for time-series monitoring |
| Labeling metrics with user IDs or request IDs | Time-series cardinality explodes and Prometheus memory pressure rises | Use bounded labels such as route template, status code, method, and service |
| Shipping every log field into full-text indexing by default | Storage and indexing costs rise faster than debugging value | Index useful labels, retain structured fields carefully, and choose Loki or Elasticsearch based on query needs |
| Deploying collectors without resource limits | A telemetry burst can starve application Pods or evict the collector | Set requests, limits, buffering policies, and backpressure expectations |

## Decision Framework

Start tool selection from the symptom, not from the product catalog. If the symptom is "traffic dropped after a rollout," begin with metrics because you need rate, error, and latency trends. If the symptom is "one request path is slow only when it touches payment," traces are likely decisive. If the symptom is "the process logged a database timeout after a config change," logs carry the concrete event. If the symptom is "the Deployment wants more replicas than it has," Kubernetes object state may be more useful than application instrumentation.

Time horizon is another decision input. Immediate autoscaling needs recent resource metrics, short incident response needs high-resolution service metrics and fresh logs, and capacity planning needs retained trends over days or weeks. Traces are often most valuable near an incident window because they show request examples, while metrics provide the longer trend that shows whether a problem is new or recurring. Retention, sampling, and storage choices should match those time horizons instead of using one default for every signal.

| Scenario | First Tool to Reach For | Follow-Up Tool | Why |
|----------|-------------------------|----------------|-----|
| HPA does not scale a busy workload | Metrics Server and HPA events | Prometheus application metrics | HPA needs resource or custom metrics, while app metrics explain demand |
| Error rate rises after a release | Prometheus in Grafana | Loki logs and Jaeger or Tempo traces | Metrics prove the trend, logs and traces localize the failure |
| Batch Job finishes before scraping | Pushgateway | Prometheus alert rules | Short-lived jobs are a valid push exception when they publish final service-level metrics |
| Multi-language teams need consistent traces | OpenTelemetry SDK and Collector | Jaeger or Tempo | Instrumentation stays stable while backends can change |
| Node-level logs are missing from some nodes | Fluent Bit DaemonSet | Kubernetes scheduling and permissions | Collectors must run where the log files exist |
| Dashboard is green but customers complain | Service-level Prometheus metrics | Traces and logs | Kubernetes health does not equal business success |

For a small startup with a five-node cluster, the PLG-style stack of Prometheus, Loki, and Grafana can be a pragmatic starting point because it keeps storage and operations relatively modest. Elasticsearch remains powerful when broad full-text search is a hard requirement, but it often demands more memory, shard planning, and operational tuning. Mimir and Tempo become interesting as scale grows and teams need horizontally scalable Prometheus-compatible metrics or cost-conscious trace storage. The right choice is the smallest stack that answers current questions while leaving a migration path for future scale.

The migration path is why standards and interfaces matter. Prometheus exposition format, OpenTelemetry Protocol, Kubernetes labels, and consistent dashboard variables all reduce the cost of changing storage or visualization later. A team can begin with a single Prometheus instance, add remote storage when retention grows, introduce OpenTelemetry for traces, and later route some telemetry to managed services if operations become too heavy. The goal is not to predict every future tool. The goal is to avoid early choices that trap application code or operational habits.

When you compare tools on the exam, look for the contract each tool owns. Prometheus owns metric scraping, storage, PromQL, and alert-rule evaluation. Grafana owns visualization and cross-source exploration. Fluent Bit and Fluentd own log collection and routing. Jaeger and Tempo own distributed trace storage and query workflows. OpenTelemetry owns instrumentation standards and Collector pipelines. Metrics Server and kube-state-metrics own Kubernetes resource and object-state visibility. Once those contracts are clear, most scenario questions become matching exercises with operational tradeoffs attached.

Which approach would you choose here and why: a team has ten services, no traces, and a plan to switch from Jaeger to Tempo next quarter? The defensible answer is to instrument with OpenTelemetry and send telemetry through the Collector, because that avoids tying application code to the current trace backend. The backend choice can then change in configuration, while semantic conventions and context propagation stay consistent across services.

## Did You Know?

- **Prometheus graduated at CNCF in 2018** after Kubernetes, which signals how central metrics became to cloud native operations.
- **OpenTelemetry was created by merging OpenTracing and OpenCensus** so teams would not need competing instrumentation standards for similar telemetry goals.
- **Loki indexes labels rather than full log text** by design, which can lower storage and indexing cost when labels are chosen carefully.
- **Metrics Server intentionally keeps a narrow role**: it serves recent resource metrics for autoscaling and `k top`, not long-term observability analysis.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Pushing all service metrics directly to Prometheus | Engineers assume every monitoring system receives data from applications | Let Prometheus scrape long-running targets and reserve Pushgateway for appropriate short-lived service-level jobs |
| Using Metrics Server as the only observability backend | `k top` works, so the cluster appears to have metrics covered | Add Prometheus or a compatible time-series system for history, application metrics, and alert rules |
| Deploying Fluent Bit as a small Deployment | Teams think of collectors like ordinary stateless services | Run node log collectors as a DaemonSet so each node's container logs are reachable |
| Creating dashboards without alert ownership | Dashboard creation feels like completion even when no one watches it | Define alert routes, severity, runbooks, and silences for the signals that require action |
| Adding request IDs or user IDs as metric labels | Developers want easy drill-down from metrics to individual customers | Put high-cardinality identifiers in logs or traces, and keep Prometheus labels bounded |
| Treating Grafana as the metrics database | Users see the chart in Grafana and assume Grafana owns the data | Teach the separation between visualization, data source, storage, and collection |
| Installing OpenTelemetry without a pipeline design | Teams adopt the standard but skip receiver, processor, exporter, and sampling decisions | Design Collector pipelines explicitly and test routing for metrics, logs, and traces before production rollout |

## Quiz

<details><summary>Your checkout service shows a sharp rise in 500 responses, but all Pods are Ready and node CPU is normal. Which tools would you use first, and what evidence are you looking for?</summary>

Start with Prometheus metrics in Grafana because the first task is to confirm the error-rate trend and isolate it by service, route, status, namespace, and pod. Then pivot to logs through Loki, Elasticsearch, Fluent Bit, or Fluentd output to find concrete error messages around the same time window. If the service is part of a request chain, use Jaeger or Tempo traces to see where the failing request slowed down or returned an error. Kubernetes readiness and CPU are useful signals, but they do not prove that business-level requests are succeeding.

</details>

<details><summary>A short-lived backup verification Job finishes in 30 seconds, and Prometheus often misses its final success metric. How should the team compare pull-based and push-based collection here?</summary>

Prometheus should still scrape normal long-running services because pull-based collection gives a clean failure signal when targets disappear. This Job is one of the valid exceptions because it may complete before the next scrape interval. The Job can push its final service-level metric to the Prometheus Pushgateway, and Prometheus can scrape the Pushgateway on schedule. The team should avoid using Pushgateway as a general replacement for scraping because that weakens target-liveness detection.

</details>

<details><summary>Your organization has Go, Java, and Python services, and the platform team plans to move traces from Jaeger storage to Tempo later. What OpenTelemetry design reduces rewrite risk?</summary>

Instrument each service with OpenTelemetry APIs and SDKs, then send telemetry to an OpenTelemetry Collector rather than directly coupling code to one backend. The Collector can route traces to Jaeger today and Tempo later by changing exporter configuration. It can also batch, enrich, sample, and process telemetry consistently for all languages. This design keeps application instrumentation stable while the platform evolves storage and visualization choices.

</details>

<details><summary>An HPA fails to scale a Deployment, while Grafana still shows application request traffic increasing. Which Kubernetes-specific signals should you evaluate?</summary>

Check Metrics Server and HPA status first because the HPA depends on resource metrics or configured custom metrics to make scaling decisions. Use `k describe hpa` to inspect missing metrics, target values, and recent scaling events, then check `k top pods` if resource metrics should be available. kube-state-metrics can also show desired and available replica state when a rollout or scheduling issue blocks capacity. Prometheus application metrics explain demand, but the autoscaler pipeline explains why Kubernetes did or did not add replicas.

</details>

<details><summary>A team deploys Fluent Bit with three replicas on a 20-node cluster and later discovers missing logs. What is the likely design error?</summary>

The likely error is running the node log collector as a Deployment instead of a DaemonSet. Container log files are written on the node where each Pod runs, so a collector must be present on every node that should be observed. Three replicas only cover three scheduled locations, and Kubernetes may move those replicas during maintenance. A DaemonSet makes the scheduling intent match the data location by running one collector Pod per node.

</details>

<details><summary>A dashboard contains dozens of graphs, but responders still need ten minutes to decide whether a release caused customer impact. What should change?</summary>

The team should redesign the dashboard around operational questions rather than tool inventory. Start with service-level indicators such as request rate, error rate, and latency, then link to logs and traces filtered by the same service, namespace, and release. Too many low-level charts can hide the signal that responders need during the first minutes of an incident. A useful Grafana dashboard helps compare evidence quickly; it is not a museum for every metric.

</details>

<details><summary>A developer wants to add `order_id` and `trace_id` labels to a Prometheus counter so they can find individual failures. How should you respond?</summary>

Do not put unbounded identifiers such as order IDs or trace IDs into Prometheus metric labels because each unique value creates additional time series. That can cause cardinality growth, memory pressure, slow queries, and even monitoring outages. Keep metrics labels bounded with values such as route template, method, status code, and service. Put individual identifiers in logs or traces, where they are designed to help drill into single events or request paths.

</details>

## Hands-On Exercise: Exploring the Stack

In this exercise, you will deploy the Prometheus and Grafana stack into a local Kubernetes 1.35+ cluster, inspect the installed components, and connect the lab back to the tool-selection decisions from the lesson. The commands use `k` after defining `alias k=kubectl`, and the flow preserves the original module's goal: see Prometheus, Grafana, Alertmanager, and kube-state-metrics arrive as one practical monitoring stack. You can use minikube or kind, but the examples below assume minikube for the start and cleanup commands.

- [ ] **Step 1: Start a local cluster, set the alias, and add the Prometheus Helm repo.**

  ```bash
  minikube start
  alias k=kubectl
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
  helm repo update
  ```

  <details><summary>Solution notes</summary>

  The Helm repository contains the kube-prometheus-stack chart used in this lab. The alias does not change Kubernetes behavior; it only shortens later commands. If `minikube start` fails, fix the local cluster first because Helm cannot install into a cluster that is not reachable.

  </details>

- [ ] **Step 2: Install the Kube-Prometheus Stack into a dedicated namespace.**

  ```bash
  helm install monitoring prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace
  ```

  <details><summary>Solution notes</summary>

  This chart installs Prometheus, Grafana, Alertmanager, kube-state-metrics, and supporting components. That breadth is useful for learning because you can inspect several observability roles at once. In production, you would still review chart values, retention, storage, alert routes, credentials, and resource requests before treating the installation as complete.

  </details>

- [ ] **Step 3: Wait for the monitoring Pods to become ready and identify their roles.**

  ```bash
  k get pods -n monitoring -w
  ```

  <details><summary>Solution notes</summary>

  Look for Pods whose names include Prometheus, Grafana, Alertmanager, operator, and kube-state-metrics. If a Pod stays Pending, describe it to check scheduling constraints or storage requirements. If a Pod repeatedly restarts, inspect logs and events before moving to the dashboard because the visualization layer depends on the underlying services.

  </details>

- [ ] **Step 4: Port-forward Grafana and open the dashboard locally.**

  ```bash
  k port-forward svc/monitoring-grafana 8080:80 -n monitoring
  ```

  <details><summary>Solution notes</summary>

  Open `http://127.0.0.1:8080` in your browser. The default username is `admin`, and the default password for this chart is commonly `prom-operator`, though chart defaults can change across releases. Navigate to a Kubernetes compute-resource dashboard and connect what you see to the lesson: Grafana is the visualization layer, while Prometheus and kube-state-metrics provide the data.

  </details>

- [ ] **Step 5: Compare resource metrics, object state, and application-oriented metrics.**

  ```bash
  k top pods -n monitoring
  k get deploy -n monitoring
  k get svc -n monitoring
  ```

  <details><summary>Solution notes</summary>

  `k top` depends on the resource metrics pipeline, while `k get deploy` shows Kubernetes object state. The Grafana dashboards add historical Prometheus views and kube-state-metrics-derived panels. The exercise is not just to prove the stack installed; it is to practice separating "resource usage," "desired versus current state," and "service behavior" when reading observability data.

  </details>

- [ ] **Step 6: Clean up the local cluster when you are finished.**

  ```bash
  minikube delete
  ```

  <details><summary>Solution notes</summary>

  Deleting the minikube cluster removes the lab resources and returns your workstation to a clean state. In a shared cluster, you would delete the Helm release and namespace instead of deleting the whole cluster. The important operational habit is to know which resources a lab creates before leaving them behind.

  </details>

Success criteria:

- [ ] You can explain why Prometheus is installed as the metrics backend and Grafana as the visualization layer.
- [ ] You can identify which installed component exposes Kubernetes object state for Prometheus.
- [ ] You can distinguish `k top` resource metrics from Prometheus historical metrics.
- [ ] You can describe why Fluent Bit would normally run as a DaemonSet, even though this chart focuses on metrics.
- [ ] You can choose whether a future tracing backend should be Jaeger or Tempo without changing application instrumentation when OpenTelemetry is used.

## Sources

- [Prometheus overview](https://prometheus.io/docs/introduction/overview/)
- [Prometheus Pushgateway guidance](https://prometheus.io/docs/instrumenting/pushing/)
- [Prometheus query basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana documentation](https://grafana.com/docs/grafana/latest/)
- [Grafana Loki documentation](https://grafana.com/docs/loki/latest/)
- [Fluentd documentation](https://docs.fluentd.org/)
- [Fluent Bit documentation](https://docs.fluentbit.io/manual)
- [Jaeger documentation](https://www.jaegertracing.io/docs/2.0/)
- [Grafana Tempo documentation](https://grafana.com/docs/tempo/latest/)
- [OpenTelemetry documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry Collector documentation](https://opentelemetry.io/docs/collector/)
- [Kubernetes resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [kube-state-metrics project](https://github.com/kubernetes/kube-state-metrics)
- [Prometheus Community Helm charts](https://prometheus-community.github.io/helm-charts)

## Next Module

Continue to [Module 3.6: Security Basics](/k8s/kcna/part3-cloud-native-architecture/module-3.6-security-basics/) to connect observability signals with the security foundations that keep cloud native systems trustworthy.
