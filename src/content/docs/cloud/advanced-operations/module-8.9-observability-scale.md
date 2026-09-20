---
title: "Module 8.9: Large-Scale Observability & Telemetry"
slug: cloud/advanced-operations/module-8.9-observability-scale
sidebar:
  order: 10
---

> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 2.5 hours
>
> **Prerequisites**: Basic understanding of Prometheus, Grafana, and logging concepts
>
> **Track**: Advanced Cloud Operations

## What You'll Be Able to Do

After completing this module, you will be able to:

- **Diagnose** performance bottlenecks and out-of-memory crashes in Prometheus due to high-cardinality metrics, implementing robust recording rules to mitigate them.
- **Design** highly available, scalable, multi-cluster observability architectures utilizing Thanos, Loki, and OpenTelemetry to unify metrics, logs, and distributed traces.
- **Implement** advanced log filtering, transformation, and sampling strategies via OpenTelemetry Collector pipelines to drastically reduce logging costs and storage overhead.
- **Evaluate** the architectural trade-offs between centralized push-based metric systems (like Grafana Mimir) and decentralized pull-based sidecar models (like Thanos).
- **Debug** cross-cluster distributed trace contexts using OpenTelemetry and tail-based sampling, ensuring complete transaction visibility across complex microservice boundaries.

---

## Why This Module Matters

**Hypothetical scenario:** A platform team operating fourteen Kubernetes clusters across three regions discovers that their single central Prometheus instance now holds more than twelve million active time series after a routine microservices rollout. Memory climbs from sixteen gigabytes to sixty-four gigabytes within hours, PromQL queries time out above thirty seconds, and the Prometheus pod begins crash-looping with out-of-memory errors every few days. The team responds by vertically scaling the pod to one hundred twenty-eight gigabytes of RAM, which briefly stabilizes ingestion until a restart forces a twenty-five-minute Write-Ahead Log replay. During that blind window, a payment gateway degrades while on-call engineers grep unstructured logs across hundreds of nodes because metrics, traces, and centralized dashboards are simultaneously unreliable.

This pattern underscores a fundamental truth about cloud-native infrastructure at enterprise scale: observability data volume naturally grows faster than the applications it monitors. The durable fix is rarely more RAM on a monolith. Teams need per-cluster Prometheus (or equivalent scrape agents), a vendor-neutral collection plane with OpenTelemetry, long-term metric storage with downsampling, log pipelines that sample before egress, and trace policies that keep errors without storing every span. On AWS that often means Amazon Managed Service for Prometheus (AMP) plus CloudWatch; on Google Cloud, Managed Service for Prometheus or Cloud Monitoring with Cloud Logging; on Azure, Azure Monitor managed Prometheus and Application Insights. This module teaches how to design that multi-cluster, multi-signal platform so telemetry remains trustworthy when clusters, tenants, and regions multiply.

---

## The Observability Scale Problem

Observability at scale is fundamentally a distributed data management problem. As you add more clusters, nodes, pods, and microservices to your Kubernetes v1.35 environment, the volume of metrics, logs, and traces multiplies exponentially. The computational cost and operational complexity of transmitting, processing, and querying this telemetry data inevitably grows faster than the physical infrastructure it is designed to monitor.

When a platform scales up, a standard out-of-the-box monitoring stack rapidly hits physical limitations. A single node's disk input/output operations per second (IOPS) cannot keep up with thousands of log lines written every second. A single process's memory cannot hold millions of active time series chunks. 

| Telemetry Volume at Scale | Small | Medium | Large |
| :--- | :--- | :--- | :--- |
| **Nodes** | 10 | 50 | 200 |
| **Pods** | 200 | 2,000 | 15,000 |
| **Services** | 20 | 100 | 500 |
| **Metrics: Time series** | 50K | 500K | 5M+ |
| **Metrics: Samples/second** | 5K | 50K | 500K |
| **Metrics: Storage (30 days)** | 10GB | 100GB | 1TB+ |
| **Logs: Lines/second** | 500 | 5,000 | 50,000 |
| **Logs: Storage (30 days)** | 50GB | 500GB | 5TB+ |
| **Traces: Spans/second** | 100 | 1,000 | 10,000 |
| **Traces: Storage (30 days)**| 5GB | 50GB | 500GB+ |

As demonstrated in the table above, enterprise-scale telemetry demands tiered storage architectures, aggressive downsampling, and decentralized processing to remain economically viable.

---

## The Three Pillars at Multi-Cluster Scale

Metrics, logs, and traces answer different questions, and each pillar fails in a predictable way when you treat a fleet of Kubernetes 1.35 clusters like a single laptop deployment. Metrics tell you *how much* and *how fast* through time-series aggregation; logs tell you *what happened in one place* with rich context; traces tell you *how a request moved* across services and regions. At small scale you can colocate all three in one namespace with default Helm charts. At large scale you must separate ingestion paths, retention tiers, and query planes so a logging storm cannot starve metric scrapes, and a cardinality explosion cannot take down trace backends.

Naive single-cluster observability collapses for four structural reasons. First, **network and identity boundaries**: scraping every pod in every cluster from one Prometheus requires cross-VPC connectivity, long scrape intervals, or insecure metric endpoints exposed beyond the cluster perimeter. Second, **cardinality multiplication**: the same HTTP metric with a `pod` label across fifteen thousand pods creates orders of magnitude more series than the same metric aggregated at deployment scope. Third, **egress economics**: shipping raw logs and full-resolution metrics from eu-west-1 to a central us-east-1 store can dominate the observability bill because cloud providers price inter-region and NAT traversal differently on AWS, GCP, and Azure. Fourth, **blast radius**: one oversized ingester or compactor outage should not blank every region’s dashboards simultaneously.

OpenTelemetry (OTel) is the vendor-neutral collection standard that keeps these pillars coherent. Applications and platform agents emit OTLP (OpenTelemetry Protocol) over gRPC or HTTP to an OTel Collector, which applies processors for batching, filtering, attribute enrichment, and sampling before exporting to backends. The Collector can scrape Prometheus endpoints, tail container logs via `filelog`, and receive traces from instrumented services using the same pipeline vocabulary. That uniformity matters when AWS teams standardize on AMP remote write, GCP teams on Google Cloud Managed Service for Prometheus, and Azure teams on Azure Monitor workspace ingestion, while still wanting identical pod labels and trace context in every cluster.

```mermaid
flowchart TB
    subgraph Fleet["Many clusters / regions / tenants"]
        C1[Cluster A metrics logs traces]
        C2[Cluster B metrics logs traces]
        C3[Cluster C metrics logs traces]
    end

    subgraph OTel["OTel Collector tier\nDaemonSet + optional central Deployment"]
        Proc[Processors:\nfilter batch sample k8sattributes]
    end

    subgraph Backends["Purpose-built stores"]
        M[Metrics:\nPrometheus Thanos Mimir AMP]
        L[Logs:\nLoki Cloud Logging Azure Monitor]
        T[Traces:\nTempo X-Ray Cloud Trace App Insights]
    end

    subgraph Consume["Consumption layer"]
        G[Grafana / Cloud consoles]
        SLO[SLO + alerting\nerror budgets]
    end

    C1 --> OTel
    C2 --> OTel
    C3 --> OTel
    OTel --> M
    OTel --> L
    OTel --> T
    M --> G
    L --> G
    T --> G
    M --> SLO
```

The diagram is intentional: collectors are a **data plane**, backends are **storage/query engines**, and SLO tooling sits on metrics (often with exemplars linking into traces). Platform teams that skip the middle layer usually end up with fifteen different Fluent Bit configs and incompatible label names, which makes multi-cloud incident response painfully slow.

| Pillar | Primary question | Typical failure at scale | Vendor-neutral anchor | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Metrics** | Is the system fast/healthy/right-sized? | OOM from label cardinality; slow PromQL | Prometheus + remote write / Thanos | AMP, CloudWatch metrics | Cloud Monitoring, GMP | Azure Monitor managed Prometheus |
| **Logs** | What did this pod say when it failed? | Ingest quota blowout; expensive full-text index | Structured logs + label selectors | CloudWatch Logs | Cloud Logging | Log Analytics / Monitor logs |
| **Traces** | Where did latency accumulate? | Storing 100% spans; broken context | W3C `traceparent` + tail sampling | X-Ray | Cloud Trace | Application Insights |

> **Stop and think**: If your organization mandates Azure Monitor for corporate compliance but cluster teams prefer in-cluster Loki for developer self-service, which pillar needs the strictest write-path governance so you do not pay twice for the same log bytes?

---

## Multi-Cluster Prometheus with Thanos

Prometheus was originally designed for localized, single-cluster deployments. It utilizes a highly optimized local Time Series Database (TSDB) but lacks native capabilities for distributed querying, horizontal scaling, or seamless long-term object storage. When operating multiple clusters, you need a mechanism to query data across all of them globally, store historical data economically (beyond the brief retention period of local SSDs), and deduplicate incoming metrics from highly available (HA) Prometheus pairs.

On Amazon EKS, the Prometheus Operator pattern remains the default starting point, with optional remote write to AMP when finance wants a managed control plane. On GKE, Google documents using Managed Service for Prometheus collectors or bringing your own Prometheus with consistent workload identity for scrape auth. On AKS, the Azure Monitor metrics addon can replace self-managed scrape infrastructure for teams that accept workspace-based governance. The Kubernetes version (1.35 in this curriculum) does not change these economics; it only shifts which kubelet/cAdvisor metrics appear and how autoscaling endpoints are labeled.

Operational limits you should plan around—verify current numbers in vendor docs rather than memorizing quotas—include TSDB head block size, maximum recommended active series per Prometheus instance, ingester memory for Loki when stream counts spike, and tail-sampling buffer RAM in centralized Collectors. Exceeding any of these limits produces the same user-visible symptom: dashboards go blank during the exact moment leadership asks for a timeline.

### Thanos Architecture

Thanos solves the multi-cluster observability problem by injecting a sidecar container alongside your existing Prometheus instances. This sidecar bridges the gap between local, ephemeral storage and global, persistent storage.

```mermaid
flowchart TD
    subgraph Cluster A
        A_Prom[Prometheus] -->|scrape| A_Sidecar[Thanos Sidecar]
    end
    subgraph Cluster B
        B_Prom[Prometheus] -->|scrape| B_Sidecar[Thanos Sidecar]
    end
    
    A_Sidecar -->|Upload TSDB blocks| ObjStore[(Object Storage\nS3/GCS/Azure)]
    B_Sidecar -->|Upload TSDB blocks| ObjStore
    
    subgraph Thanos Components
        StoreGW[Store Gateway\nreads old data]
        Compactor[Compactor\ndownsample blocks]
        Querier[Querier\nfan-out to all sources]
    end
    
    ObjStore --> StoreGW
    ObjStore --> Compactor
    
    A_Sidecar -.-> Querier
    B_Sidecar -.-> Querier
    StoreGW -.-> Querier
    
    Grafana[Grafana] -->|queries| Querier
```

In this decentralized architecture, Prometheus continues to scrape targets and evaluate local alerting rules. Every two hours, Prometheus cuts a new immutable TSDB block to disk. The Thanos Sidecar detects this new block and uploads it to an inexpensive object store (like AWS S3 or Google Cloud Storage). 

### Deploying Thanos with Prometheus Operator

To deploy this architecture, you configure the Prometheus Operator to inject the Thanos Sidecar and mount the necessary credentials for the external object storage.

```yaml
# Prometheus with Thanos sidecar (per cluster)
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 2  # HA pair
  retention: 6h  # Short local retention (Thanos handles long-term)
  externalLabels:
    cluster: "prod-us-east-1"
    region: "us-east-1"
  thanos:
    image: quay.io/thanos/thanos:v0.41.0
    objectStorageConfig:
      key: objstore.yml
      name: thanos-objstore-config
  storage:
    volumeClaimTemplate:
      spec:
        storageClassName: gp3
        resources:
          requests:
            storage: 50Gi
  serviceMonitorSelector:
    matchLabels:
      release: prometheus
```

```yaml
# Object storage configuration
apiVersion: v1
kind: Secret
metadata:
  name: thanos-objstore-config
  namespace: monitoring
stringData:
  objstore.yml: |
    type: S3
    config:
      bucket: thanos-metrics-longterm
      endpoint: s3.us-east-1.amazonaws.com
      region: us-east-1
```

### Thanos Querier (Central Query Endpoint)

To view the data, you deploy a Thanos Querier in a central management cluster. The Querier exposes a standard PromQL API. When it receives a query from Grafana, it intelligently fans out the request. It asks the local Sidecars for recent, un-uploaded data, and asks the Store Gateway for older historical data fetched from S3.

```yaml
# Deploy in a central management cluster
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thanos-querier
  namespace: monitoring
spec:
  replicas: 2
  selector:
    matchLabels:
      app: thanos-querier
  template:
    metadata:
      labels:
        app: thanos-querier
    spec:
      containers:
        - name: querier
          image: quay.io/thanos/thanos:v0.41.0
          args:
            - query
            - --http-address=0.0.0.0:9090
            - --grpc-address=0.0.0.0:10901
            # Connect to Thanos sidecars in each cluster
            - --store=thanos-sidecar.cluster-a.monitoring.svc:10901
            - --store=thanos-sidecar.cluster-b.monitoring.svc:10901
            # Connect to Thanos Store Gateway (for historical data)
            - --store=thanos-store-gateway:10901
            # Deduplicate HA Prometheus pairs
            - --query.replica-label=prometheus_replica
          ports:
            - name: http
              containerPort: 9090
            - name: grpc
              containerPort: 10901
```

```yaml
# Thanos Store Gateway (serves data from object storage)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: thanos-store-gateway
  namespace: monitoring
spec:
  replicas: 2
  selector:
    matchLabels:
      app: thanos-store
  template:
    metadata:
      labels:
        app: thanos-store
    spec:
      containers:
        - name: store
          image: quay.io/thanos/thanos:v0.41.0
          args:
            - store
            - --data-dir=/data
            - --objstore.config-file=/etc/thanos/objstore.yml
            - --grpc-address=0.0.0.0:10901
          volumeMounts:
            - name: data
              mountPath: /data
            - name: objstore-config
              mountPath: /etc/thanos
      volumes:
        - name: objstore-config
          secret:
            secretName: thanos-objstore-config
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        storageClassName: gp3
        resources:
          requests:
            storage: 20Gi  # Cache for frequently accessed blocks
```

**Thanos Receive** (alternative to sidecar upload) accepts Prometheus remote write directly and writes to object storage without waiting for two-hour TSDB blocks. Receive fits burstier workloads and centralized agent models, but it shifts failure modes to the receive hash ring; operations teams must monitor replication factor and backlog queues. Many EKS/GKE/AKS fleets combine sidecar for clusters that already run Prometheus Operator, plus Receive for edge clusters that only run lightweight agents.

Grafana Mimir (Cortex lineage) prefers remote write from the start. A minimal `remote_write` stanza in Prometheus or the OTel exporter points to Mimir distributors:

```yaml
# prometheus.yml fragment — remote_write to Mimir or AMP-compatible endpoint
remote_write:
  - url: https://mimir-distributor.monitoring.svc:8080/api/v1/push
    headers:
      X-Scope-OrgID: team-payments
    queue_config:
      capacity: 10000
      max_shards: 50
      min_shards: 1
      max_samples_per_send: 5000
```

Tune `queue_config` when clusters flap during node drains; undersized queues cause sample drops that look like application outages in Grafana. Managed endpoints (AMP, Google Cloud Managed Service for Prometheus, Azure Monitor workspace) publish authentication and endpoint formats in their official docs—swap the URL and signing mechanism, keep the queue discipline.

### Thanos vs. Cortex vs. Mimir

When architecting for scale, engineers typically weigh Thanos against push-based alternatives like Grafana Mimir. Both solve the long-term storage and global query problem, but they do so using fundamentally different topological designs. 

| Feature | Thanos | Cortex | Grafana Mimir |
|---|---|---|---|
| Architecture | Sidecar-based (near Prometheus) | Push-based (remote_write) | Push-based (remote_write) |
| Query | Fan-out to sidecars + store | Centralized query frontend | Centralized query frontend |
| Storage | Object storage (S3/GCS) | Object storage + index store | Object storage |
| Multi-tenancy | Labels only | Native (per-tenant storage) | Native (per-tenant limits) |
| Operational complexity | Medium (many components) | High (many microservices) | Medium (simplified Cortex) |
| Best for | Multi-cluster with existing Prometheus | Large multi-tenant platforms | Large multi-tenant platforms |
| License | Apache 2.0 | Apache 2.0 | AGPL 3.0 |

### Metrics at Scale: Remote Write, Federation, and Downsampling

Prometheus remains the de facto metrics format on Kubernetes because `ServiceMonitor` objects, kube-state-metrics, and application `/metrics` endpoints already speak it. The core Prometheus project intentionally optimizes for **reliable local scraping** rather than horizontal sharding; when you outgrow one TSDB head, you choose an ecosystem pattern instead of a bigger single pod.

**Remote write** pushes samples from Prometheus (or the OTel `prometheusremotewrite` exporter) to a centralized receiver. Grafana Mimir, Cortex, and Amazon Managed Service for Prometheus all ingest via Prometheus remote write APIs. This model centralizes query and compaction but shifts operational focus to ingestion quotas, per-tenant limits, and deduplication of HA pairs. AWS documents AMP pricing primarily around **samples ingested**, with additional charges for stored samples and query samples processed, which makes remote-write cardinality discipline an FinOps task, not only a reliability task.

**Federation** (`/federate`) lets a global Prometheus pull aggregated series from regional Prometheus servers. Federation is simpler than Thanos for small multi-cluster footprints, but it still concentrates query load on the global instance and encourages up-sum-only workflows that break when labels differ across clusters. Most enterprises beyond roughly ten clusters adopt Thanos, Mimir, or a managed Prometheus-compatible service instead of a federation tree.

**Recording rules** pre-compute expensive PromQL (rates, histogram quantiles, aggregations by deployment) into new lower-cardinality metrics. They are the cheapest performance win because dashboards query `$recording_rule` instead of `sum(rate(...[5m])) by (pod)` across thousands of pods.

**Downsampling** (Thanos Compactor, Mimir/Cortex compaction, or managed retention policies) stores five-second resolution briefly, then one-minute or five-minute resolution for months. Compactor downsampling is how teams keep multi-year SLO history without paying full-resolution storage for every scrape interval.

| Pattern | When it fits | AWS angle | GCP angle | Azure angle |
| :--- | :--- | :--- | :--- | :--- |
| Thanos sidecar + object store | Existing per-cluster Prometheus + S3/GCS/Azure Blob | Sidecar uploads to S3; querier in tooling cluster | GCS backend; multi-cluster GKE | Azure Blob + managed identities |
| Mimir/Cortex remote write | Greenfield central TSDB + strong tenancy | AMP as managed remote-write target | Google Cloud Managed Service for Prometheus | Azure Monitor workspace for Prometheus metrics |
| Federation only | Few clusters, coarse aggregates | Rare at EKS fleet scale | Rare beyond early GKE pilots | Possible for hub-spoke AKS |

> **Stop and think**: If the Thanos Compactor goes down for 48 hours, what happens to your Grafana dashboards? Would you lose data, or just experience slower queries when looking at historical data from a week ago?

---

## OpenTelemetry Collector at Scale

The OpenTelemetry (OTel) Collector acts as a vendor-agnostic ingestion pipeline, standardizing the receipt, processing, and exportation of all telemetry signals: metrics, logs, and distributed traces. At enterprise scale, the Collector becomes the single most critical data router in your architecture.

Deploying OTel as a DaemonSet ensures that every Kubernetes node has a localized agent capable of collecting node-level metrics (from kubelet), intercepting standard out logs, and receiving application traces with minimal network latency.

For fleets larger than a handful of clusters, introduce a **gateway tier**: DaemonSet collectors forward to a regional Deployment that runs tail sampling, sensitive attribute redaction, and rate limiting before remote write leaves the region. This mirrors how cloud providers structure their own pipelines—edge collection, regional aggregation, central query—and prevents every node from holding incomplete traces during `decision_wait`. On AWS, ADOT distributions package collectors with X-Ray exporters; on GCP and Azure, OpenTelemetry distributions target Cloud Trace and Application Insights respectively while still allowing OTLP export to Tempo for multi-cloud neutrality.

When wiring exporters, treat TLS and identity as part of the data plane. Prometheus remote write to AMP or Azure Monitor workspaces should use workload identity (EKS Pod Identity or IRSA, GKE Workload Identity, Entra Workload ID on AKS) instead of long-lived keys embedded in ConfigMaps. The same identity pattern applies to Loki object storage and Thanos S3/GCS/Azure Blob uploads.

```mermaid
flowchart LR
    subgraph Applications
        Pod1[Pod OTLP]
        Pod2[Pod OTLP]
        Pod3[Pod Prom]
    end
    
    Kubelet[kubelet metrics]
    cAdvisor[cadvisor metrics]
    NodeExp[node-exporter]
    
    subgraph OTel Collector per node
        direction TB
        subgraph Receivers
            R_OTLP[OTLP gRPC/HTTP]
            R_Prom[Prometheus scrape]
            R_Filelog[Filelog container logs]
        end
        subgraph Processors
            P_Batch[batch]
            P_Filter[filter]
            P_Trans[transform]
            P_Samp[tail_sampling]
            P_Mem[memory_limiter]
        end
        subgraph Exporters
            E_Prom[prometheusremotewrite]
            E_OTLPHTTP[otlphttp → Loki /otlp]
            E_OTLP[otlp to Tempo]
        end
        Receivers --> Processors --> Exporters
    end
    
    Pod1 --> R_OTLP
    Pod2 --> R_OTLP
    Pod3 -.-> R_Prom
    
    Kubelet --> R_Prom
    cAdvisor --> R_Prom
    NodeExp --> R_Prom
    
    E_Prom --> Thanos[Thanos/Mimir\nmetrics]
    E_OTLPHTTP --> Loki[Loki/Elasticsearch\nlogs]
    E_OTLP --> Tempo[Tempo/Jaeger\ntraces]
```

### OTel Collector Configuration

A production-grade Collector configuration heavily utilizes Processors. The `memory_limiter` processor is particularly vital; it forcefully drops telemetry data when the pod's memory usage approaches critical thresholds, ensuring the Collector does not trigger a cascading node-level OOM kill.

```yaml
# OTel Collector deployed as DaemonSet (one per node)
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: otel-node-collector
  namespace: monitoring
spec:
  mode: daemonset
  config:
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

      # Scrape Prometheus endpoints from pods with annotations
      prometheus:
        config:
          scrape_configs:
            - job_name: 'kubernetes-pods'
              kubernetes_sd_configs:
                - role: pod
              relabel_configs:
                - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
                  action: keep
                  regex: true

      # Collect container logs from the node
      filelog:
        include:
          - /var/log/pods/*/*/*.log
        operators:
          - type: router
            routes:
              - output: parse_json
                expr: 'body matches "^\\{"'
              - output: parse_plain
                expr: 'true'
          - id: parse_json
            type: json_parser
          - id: parse_plain
            type: regex_parser
            regex: '^(?P<message>.*)$'

    processors:
      # Prevent OOM by limiting memory usage
      memory_limiter:
        check_interval: 5s
        limit_percentage: 80
        spike_limit_percentage: 25

      # Batch telemetry for efficient export
      batch:
        send_batch_size: 1024
        timeout: 5s

      # Add Kubernetes metadata to all telemetry
      k8sattributes:
        auth_type: serviceAccount
        extract:
          metadata:
            - k8s.pod.name
            - k8s.namespace.name
            - k8s.deployment.name
            - k8s.node.name
          labels:
            - tag_name: team
              key: team
            - tag_name: app
              key: app

      # Filter out noisy metrics to reduce cardinality
      filter:
        metrics:
          exclude:
            match_type: regexp
            metric_names:
              - go_.*           # Go runtime metrics (usually not needed)
              - process_.*      # Process metrics (usually not needed)
              - promhttp_.*     # Prometheus client metrics

    exporters:
      prometheusremotewrite:
        endpoint: "http://thanos-receive:19291/api/v1/receive"
        tls:
          insecure: true

      otlphttp/loki:
        endpoint: "http://loki-gateway:3100/otlp"
        tls:
          insecure: true

      otlp/tempo:
        endpoint: "tempo-distributor:4317"
        tls:
          insecure: true

    service:
      pipelines:
        metrics:
          receivers: [otlp, prometheus]
          processors: [memory_limiter, k8sattributes, filter, batch]
          exporters: [prometheusremotewrite]
        logs:
          receivers: [filelog]
          processors: [memory_limiter, k8sattributes, batch]
          exporters: [otlphttp/loki]
        traces:
          receivers: [otlp]
          processors: [memory_limiter, k8sattributes, batch]
          exporters: [otlp/tempo]
```

Loki 3.x ingests logs natively over OTLP (`/otlp`). The contrib `loki` exporter (`lokiexporter`, push to `/loki/api/v1/push`) was deprecated in 2024-07 and removed from current Collector builds—configs that still reference `exporters: loki` fail decode with `unknown type: loki`. Route log pipelines through `otlphttp` (or `otlp`) to the Loki OTLP endpoint instead.

**Pause and predict:** If you configure the `memory_limiter` processor in an OpenTelemetry Collector pipeline to reject telemetry when memory consumption reaches ninety percent, and an application triggers a sudden spike in log volume, which signal (metrics, logs, or traces) gets dropped first? Or does the processor drop all signals equally?

<details>
<summary>Check your prediction</summary>

The `memory_limiter` processor refuses **all** telemetry signals equally rather than prioritizing metrics or dropping logs first. The processor enforces a process-wide soft limit based on Go runtime heap checks. When memory usage breaches the soft limit or reaches the hard limit, the processor refuses data across all active pipelines by rejecting calls to `ConsumeLogs`, `ConsumeTraces`, and `ConsumeMetrics` until garbage collection runs and heap usage falls back below the threshold. Because the limiter evaluates overall process memory rather than individual pipeline buffers, an unexpected surge in verbose application logs causes the Collector to reject incoming metrics and traces simultaneously. Production architectures mitigate this shared blast radius by deploying dedicated Collector instances for high-volume log streams.
</details>

Preventing sudden log volume spikes from starving essential metric and trace pipelines requires decoupling textual log ingestion from core operational telemetry. The next section explores how Loki transforms log aggregation economics by indexing metadata labels instead of building heavy inverted indices on raw text payloads.


---

## Centralized Logging at Scale with Loki

Traditional log aggregation systems, such as Elasticsearch, ingest textual logs and build extensive, full-text inverted indices. While this permits ultra-fast keyword searches, the index itself frequently grows larger than the raw log data, resulting in exorbitant storage costs and massive memory overhead.

### Loki: The Log Aggregation System Built for Kubernetes

Grafana Loki addresses this by adopting a design philosophy heavily inspired by Prometheus. Loki does not index the actual text content of a log line. Instead, it groups log lines into compressed chunks and exclusively indexes the metadata labels attached to them (e.g., `namespace="production"`, `app="payment-gateway"`).

```mermaid
flowchart TD
    subgraph Clusters
        C_A[Cluster A OTel]
        C_B[Cluster B OTel]
        C_C[Cluster C OTel]
    end
    
    subgraph Loki Distributed
        Distributor[Distributor\nreceives streams]
        Ingester[Ingester\nWAL + in-memory index]
        ObjStore[(Object Storage\nchunks + index)]
        Querier[Querier\nreads ingesters + storage]
        QueryFE[Query Frontend\ncaching, splitting]
    end
    
    C_A --> Distributor
    C_B --> Distributor
    C_C --> Distributor
    
    Distributor --> Ingester
    Ingester --> ObjStore
    
    QueryFE --> Querier
    Querier --> Ingester
    Querier --> ObjStore
```

This deliberate trade-off makes ingestion and long-term storage exponentially cheaper. When executing a search query, Loki quickly identifies the relevant compressed chunks using the label index and then brute-force scans (greps) through the chunk content in memory.

### Structured Logging and Shipping Pipelines

Unstructured printf-style logs force expensive parsing at query time and encourage operators to promote volatile fields (request IDs, user IDs) into labels, which repeats the cardinality mistake from metrics. **Structured logging** (JSON or logfmt with stable keys like `level`, `service`, `trace_id`, `http.route`) lets collectors enrich and filter without guessing. OpenTelemetry Logs Bridge maps existing log streams into OTLP so the same Collector pipeline can route to Loki, Google Cloud Logging, or Azure Monitor.

At node scale, **Fluent Bit** and **Vector** remain the dominant shippers because they are lightweight, support Kubernetes metadata filters, and integrate with cloud-native sinks. A common enterprise pattern is DaemonSet shipper → regional OTel Collector (sampling + PII redaction) → central Loki or cloud logging API. On AWS, FireLens for EKS often fronts CloudWatch Logs; on GCP, logging agents target Cloud Logging with workload identity; on Azure, Container Insights and diagnostic settings feed Log Analytics. The architectural invariant is identical: **filter and sample before cross-region egress**, because log ingestion pricing is volume-based and surprises show up on the invoice before anyone tunes retention.

| Tier | Retention | Query expectation | Cost driver |
| :--- | :--- | :--- | :--- |
| Hot | 1–7 days | Fast troubleshooting | In-memory ingesters / indexing |
| Warm | 30 days | Namespace-scoped investigations | Object storage + compactor |
| Cold / compliance | 1–7 years | Rare legal or audit pulls | Archive storage + export jobs |

### Loki Deployment for Multi-Cluster

Loki can be deployed in a distributed mode, breaking apart the read and write paths into discrete microservices (Distributor, Ingester, Querier). This allows you to independently scale ingestion bandwidth separately from query processing power.

```yaml
# Loki values for Helm (distributed mode)
# helm install loki grafana/loki -n monitoring -f loki-values.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: loki-config
  namespace: monitoring
data:
  loki.yaml: |
    auth_enabled: true  # Multi-tenant mode

    server:
      http_listen_port: 3100

    common:
      storage:
        s3:
          bucketnames: loki-chunks-prod
          region: us-east-1

    limits_config:
      retention_period: 30d
      max_query_lookback: 30d
      ingestion_rate_mb: 20       # Per-tenant rate limit
      ingestion_burst_size_mb: 30
      max_streams_per_user: 50000
      max_label_name_length: 1024
      max_label_value_length: 2048

    schema_config:
      configs:
        - from: 2026-01-01
          store: tsdb
          object_store: s3
          schema: v13
          index:
            prefix: loki_index_
            period: 24h

    compactor:
      working_directory: /data/compactor
      retention_enabled: true
```

### Log Volume Control

At a massive scale, an unoptimized service blindly logging at the `DEBUG` level can single-handedly saturate a cluster's network interfaces and exhaust centralized storage budgets. OpenTelemetry allows you to assert authoritative control over log volumes before they ever leave the node.

LogQL queries should mirror how operators actually troubleshoot: start with low-cardinality selectors (`{namespace="payments", app="ledger"}`), narrow time windows, then pipeline filters (`| json | level="error"`). Teaching engineers to search raw text globally without labels recreates Elasticsearch costs inside Loki. For security investigations that truly need full-text search, route a **copy** of specific audit streams to a purpose-built index rather than promoting all application logs to full-text infrastructure.

When bridging clouds, normalize field names (`severity` vs `level`, `trace_id` vs `traceId`) in OTel `transform` processors so Grafana derived fields work across AKS, EKS, and GKE. Consistency beats having the perfect parser per language.

```yaml
# OTel Collector: Filter noisy logs before they reach Loki
processors:
  filter/logs:
    logs:
      exclude:
        match_type: regexp
        bodies:
          - "health check"
          - "GET /healthz"
          - "GET /readyz"
          - "GET /metrics"
        resource_attributes:
          - key: k8s.namespace.name
            value: "kube-system"  # Drop kube-system logs

  # Sample a fixed percentage of log records (not severity-filtered by itself)
  probabilistic_sampler:
    sampling_percentage: 10
  # To keep only DEBUG at 10%, add a filter processor on severity before the sampler

  # Transform: drop specific log fields to reduce size
  transform/logs:
    log_statements:
      - context: log
        statements:
          - delete_key(attributes, "request_headers")
          - delete_key(attributes, "response_body")
          - truncate_all(attributes, 4096)
```

> **Stop and think**: You just deployed a new microservice that logs a unique `request_id` as a label for every single log line. What will happen to your Loki cluster's performance and storage costs over the next few hours?

---

## Cardinality and Cost Management

In time-series databases, cardinality refers to the total number of unique time series actively being tracked. The cardinality of a single metric is determined by multiplying the number of unique values for each associated label. High-cardinality labels—such as explicit IP addresses, unique session tokens, or unsanitized HTTP request paths—are the primary culprits behind Prometheus OOM crashes.

Cardinality is also how managed vendors meter your bill. Amazon Managed Service for Prometheus charges by metric samples ingested; Google Cloud and Azure publish analogous ingestion models for Prometheus metrics and log analytics. That means a label explosion is simultaneously a reliability incident and a procurement incident. FinOps dashboards should plot `prometheus_tsdb_head_series` (or cloud equivalents) alongside daily ingestion cost so product teams see feedback within days, not at quarter close.

Platform engineering teams typically publish a **label contract**: allowed keys (`service`, `http_route_group`, `status_code`, `deployment`), forbidden keys (`user_id`, `email`, raw `url`), and guidance to put high-cardinality identifiers in exemplars, logs, or trace attributes. Enforcement layers include: (1) admission-time linting in CI for custom ServiceMonitors, (2) OTel `transform`/`filter` processors dropping labels at collection, (3) Prometheus `metric_relabel_configs` on scrape, and (4) hard per-tenant limits in Mimir or AMP workspaces. AWS documents cost optimization for AMP emphasizing ingestion control; the same discipline applies whether storage is S3 behind Thanos or a managed workspace.

**Hypothetical scenario:** A team adds `customer_id` as a Prometheus label on an API with two million monthly active users. Even at one sample per minute, series multiplication overwhelms local TSDB RAM and can push remote-write pipelines into throttle. The remediation is not “buy bigger nodes forever”; it is migrate `customer_id` to trace attributes, aggregate counters by `customer_tier`, and add a recording rule for SLA-relevant aggregates only.

```mermaid
flowchart TD
    Metric["Metric: http_requests_total"]
    
    subgraph Labels ["Labels Contributing to Cardinality"]
        direction TB
        Method["methods: 4 (GET, POST, etc.)"]
        Path["paths: 500 (one per endpoint)"]
        Status["status_codes: 20 (200, 404, etc.)"]
        Pod["pods: 100 (across deployments)"]
        Instance["instances: 50 (nodes)"]
    end
    
    Metric --> Labels
    Labels --> Total["Total time series: 4 * 500 * 20 * 100 * 50 = 200,000,000"]
    
    Total --> Impact["Impact at 200M series:\n- ~400GB memory\n- ~2TB disk (30 days)\n- Minute-long query latency"]
    
    subgraph Fix ["THE FIX: Reduce label cardinality"]
        direction TB
        DropPod["Remove pod label (aggregate at deployment)"]
        BucketPath["Bucket path into categories (/api/users/*)"]
        DropInstance["Remove instance label (aggregate at cluster)"]
    end
    
    Impact --> Fix
    Fix --> NewTotal["After Fix: 4 * 50 * 20 = 4,000 time series\n(50,000x reduction)"]
```

### Controlling Cardinality

By utilizing Prometheus recording rules, platform operators can execute heavy, computationally expensive aggregations directly on the backend, generating new, streamlined metrics. This means when a developer loads a dashboard, Grafana queries the pre-aggregated data rather than forcing Prometheus to calculate massive sums on the fly.

```yaml
# Prometheus recording rules: pre-aggregate to reduce cardinality
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: cardinality-reduction
  namespace: monitoring
spec:
  groups:
    - name: aggregated-http-metrics
      interval: 30s
      rules:
        # Aggregate per-pod metrics to per-deployment
        - record: http_requests:rate5m:by_deployment
          expr: |
            sum by (namespace, deployment, method, status_code) (
              rate(http_requests_total[5m])
            )

        # Bucket paths into categories
        - record: http_requests:rate5m:by_path_group
          expr: |
            sum by (namespace, deployment, path_group, method) (
              label_replace(
                rate(http_requests_total[5m]),
                "path_group",
                "$1",
                "path",
                "(/api/[^/]+)/.*"
              )
            )
```

To actively hunt down cardinality offenders within an environment, operators can leverage specific PromQL queries directly against the TSDB metadata.

```bash
# Find the highest cardinality metrics in Prometheus
# (Run this PromQL query in Grafana)

# Top 10 metrics by cardinality
topk(10, count by (__name__)({__name__=~".+"}))

# Find labels causing cardinality explosion for a specific metric
count by (pod) (http_requests_total)
# If this returns 500+ series, "pod" label is too granular
```

**Pause and predict:** If you implement a Prometheus recording rule to aggregate granular per-pod metrics into a deployment-level summary, what happens to the historical data stored under the original pod-level metric name? Does the new recording rule rewrite or recalculate existing historical time series in the TSDB?

<details>
<summary>Check your prediction</summary>

A recording rule evaluates strictly **at current time** moving forward and records samples into an entirely **new** series without altering historical data. Prometheus recording rules do not backfill past intervals or rewrite existing TSDB blocks on disk. The original pod-level series remain stored in historical blocks exactly as recorded until they reach their retention limit and are purged by the compactor. Dashboards querying the original pod-level metric across historical windows will still see old pod series, but queries spanning both past and present must account for the series name transition. Historical data remains untouched, meaning recording rules reduce storage ingestion rates and query latency only from the moment they are applied.
</details>

Pre-computing aggregated metrics relieves TSDB query pressure and controls cardinality, but aggregated counters cannot reconstruct the end-to-end journey of an individual transaction across distributed services. The next section examines how distributed tracing preserves transaction context across cluster and cloud boundaries without generating unmanageable storage overhead.

---

## Cross-Cloud Distributed Tracing

**Pause and predict:** If the Frontend Service and Payment Service belong to different teams using different tracing instrumentation (such as Jaeger versus Zipkin clients), what happens to the trace context when an HTTP request crosses the cluster boundary? Does the downstream service seamlessly continue the incoming trace, or does the trace break into disconnected fragments?

<details>
<summary>Check your prediction</summary>

Without a shared propagator, the trace fractures into disconnected spans because Jaeger and Zipkin default to incompatible HTTP header formats. Zipkin historically relies on B3 propagation (`X-B3-TraceId`, `X-B3-SpanId`), whereas modern OpenTelemetry and Jaeger implementations default to the W3C Trace Context standard (`traceparent`). Even though HTTP carries the request across the cluster boundary, the downstream service cannot locate its expected trace header, treats the request as a brand-new transaction root, and generates a new trace ID. Platform teams resolve cross-boundary trace fracture by standardizing on W3C `traceparent` or configuring dual propagators (`b3multi`, `tracecontext`) across all service runtimes and ingress gateways.
</details>

Maintaining trace continuity requires strict header contract alignment across service boundaries before telemetry ever leaves an application container. The following operational architecture explores how distributed tracing tracks transactions across independent clusters and why context propagation standards are critical.

As architectures fracture into dozens of microservices deployed across disparate Kubernetes clusters, traditional single-service logging becomes insufficient for diagnosing systemic latency. Distributed tracing tracks the complete lifecycle of a single request as it traverses network boundaries, database calls, and inter-service HTTP requests. 

This relies heavily on trace context propagation, where standard HTTP headers (such as the W3C `traceparent` header defined in the W3C Trace Context recommendation) are injected at ingress and extracted by each downstream hop. If any service strips headers at a gateway or rewrites outbound calls without propagating context, traces fracture into orphan spans and on-call engineers see “mystery” latency inside the mesh. Service meshes (Istio, Linkerd, Cilium with Hubble) can automate propagation for HTTP/gRPC, but application-owned outbound clients still need explicit instrumentation or eBPF-based capture.

**Head-based sampling** decides keep/drop at trace start (for example “keep 10% of all traces”). It is cheap and easy but statistically discards rare failures. **Tail-based sampling** buffers spans until the trace completes, then applies policies such as “keep all ERROR status” or “keep latency > 2s.” Tail sampling requires a centralized Collector Deployment with enough memory to hold incomplete traces during `decision_wait`, which is why DaemonSet collectors forward spans to a regional aggregator tier.

**Exemplars** link histogram metrics to trace IDs so Grafana can jump from a latency spike in PromQL to the exact trace in Tempo or Jaeger. That bridge is how SLO dashboards become actionable during incidents instead of merely pretty.

| Signal linkage | Mechanism | Operational payoff |
| :--- | :--- | :--- |
| Metrics → Traces | Exemplars on histograms | Click from SLO burn to slow trace |
| Logs → Traces | `trace_id` field in JSON logs | Pivot from error line to waterfall |
| Traces → Metrics | Span metrics derived in Collector | RED metrics from trace stream |

```mermaid
flowchart TD
    subgraph Cluster A us-east-1
        FES[Frontend Service\ntrace_id: abc123\nspan_id: span-1]
        API[API Gateway\ntrace_id: abc123\nspan_id: span-2\nparent: span-1]
    end
    
    subgraph Cluster B eu-west-1
        Pay[Payment Service\ntrace_id: abc123\nspan_id: span-3\nparent: span-2]
        Fraud[Fraud Check Service\ntrace_id: abc123\nspan_id: span-4\nparent: span-3]
    end
    
    FES -->|HTTP header: traceparent| Pay
    FES --> API
    Pay --> Fraud
    
    OTelA[OTel Collector]
    OTelB[OTel Collector]
    
    API --> OTelA
    Fraud --> OTelB
    
    Tempo[(Tempo / Jaeger\nStores all spans for abc123)]
    
    OTelA --> Tempo
    OTelB --> Tempo
```

### Tail-Based Sampling for Traces

Ingesting and storing 100% of generated distributed traces is often financially unviable. Most systems implement sampling strategies. Standard "head-based" sampling makes a random drop-or-keep decision the moment a request starts. However, this means you will frequently drop traces for transactions that eventually fail later in the pipeline.

For multi-region checkout flows, also verify **baggage and context propagation** across asynchronous boundaries (Kafka, SQS, Pub/Sub, Azure Service Bus). A trace that breaks when a message is enqueued will show a perfect frontend span and a disconnected consumer span, misleading latency analysis. OpenTelemetry propagators must be configured on producers and consumers with the same W3C headers; mesh ingress gateways should forward `traceparent` untouched. When vendors provide managed trace pipelines (X-Ray, Cloud Trace, Application Insights), confirm whether tail sampling happens in your Collector or in the cloud backend, because double-sampling can erase rare errors entirely.

Tail-based sampling resolves this by holding all constituent spans of a trace in a temporary memory buffer until the entire request completes. Only then does it execute policy decisions, guaranteeing that any trace containing an error or exceeding latency thresholds is preserved.

```yaml
# OTel Collector with tail-based sampling
# Deploy as a Deployment (NOT DaemonSet) for trace aggregation
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: otel-trace-sampler
  namespace: monitoring
spec:
  mode: deployment
  replicas: 3
  config:
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317

    processors:
      # Tail-based sampling: decide AFTER seeing the full trace
      tail_sampling:
        decision_wait: 10s  # Wait for all spans to arrive
        num_traces: 100000  # Buffer size
        policies:
          # Always keep error traces
          - name: errors
            type: status_code
            status_code:
              status_codes:
                - ERROR
          # Always keep slow traces (>2s)
          - name: slow-traces
            type: latency
            latency:
              threshold_ms: 2000
          # Sample 5% of normal traces
          - name: normal-sampling
            type: probabilistic
            probabilistic:
              sampling_percentage: 5

    exporters:
      otlp/tempo:
        endpoint: "tempo-distributor:4317"
        tls:
          insecure: true

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [tail_sampling]
          exporters: [otlp/tempo]
```

### Managed Trace Backends

Vendor-managed trace stores trade operational toil for ingestion pricing and retention limits. **AWS X-Ray** integrates with the CloudWatch agent and ADOT (AWS Distro for OpenTelemetry) collectors on EKS; sampling rules can be configured centrally while still exporting OTLP to self-hosted Tempo when needed. **Google Cloud Trace** accepts OTLP via OpenTelemetry and ties into Cloud Monitoring trace explorer views for GKE workloads. **Azure Application Insights** (workspace-based) ingests OpenTelemetry traces from AKS and links them to smart detection alerts, though teams should treat high-cardinality custom dimensions carefully because they affect both cost and query performance.

---

## Managed Observability: AWS, GCP, and Azure

Build-versus-buy is not a one-time choice; it is a per-signal decision tied to compliance, staffing, and existing cloud commitments. Many enterprises run **open-source backends in-cluster** (kube-prometheus-stack, Loki, Tempo) for engineering velocity while using **managed ingestion and long-term stores** for production SLAs and IAM integration.

| Capability | AWS (EKS-centric) | GCP (GKE-centric) | Azure (AKS-centric) | Kubernetes-neutral |
| :--- | :--- | :--- | :--- | :--- |
| Metrics | Amazon Managed Service for Prometheus, CloudWatch | Google Cloud Managed Service for Prometheus, Cloud Monitoring | Azure Monitor managed Prometheus metrics | Prometheus + Thanos/Mimir |
| Logs | CloudWatch Logs, FireLens | Cloud Logging | Azure Monitor / Log Analytics | Loki, OTel → object store |
| Traces | X-Ray, ADOT | Cloud Trace | Application Insights | Tempo, Jaeger |
| Dashboards / SLO UI | Amazon Managed Grafana, CloudWatch | Cloud Monitoring dashboards | Azure Managed Grafana, Monitor workbooks | Grafana |
| Cost visibility | Cost Explorer + CUR tags | Cloud Billing + labels | Cost Management + tags | Kubecost, OpenCost |

**Amazon Managed Service for Prometheus** offers a Prometheus-compatible remote write endpoint with AWS IAM authentication and automatic scaling; AWS documents ingestion as the dominant cost driver, with tiered per-sample pricing and separate storage and query-sample charges. Teams on EKS often keep a local Prometheus for scraping and alerting while remote-writing to AMP for global query and retention.

**Google Cloud Managed Service for Prometheus** and Cloud Monitoring collect Prometheus metrics from GKE with managed collectors and support PromQL-style querying in the Cloud Monitoring metrics explorer. Google documents metric ingestion and API read costs separately from logging, which matters when autoscaling clusters add kubelet/cAdvisor cardinality automatically.

**Azure Monitor workspace for Prometheus metrics** (managed Prometheus on AKS) ingests Prometheus remote write data into a workspace integrated with Azure Monitor alerts and Grafana. Application Insights provides APM-style trace and dependency views; pairing it with OpenTelemetry SDKs is the supported path as legacy instrumentation agents retire.

The managed path wins when you need **federated identity**, **private endpoints**, and **org-wide SLO reporting** without operating Compactor rings yourself. The self-hosted path wins when you need **multi-cloud identical configs**, **air-gapped regions**, or **aggressive custom sampling** that managed quotas resist.

Hybrid designs are common and valid: scrape and alert locally with Prometheus on every cluster, remote-write long retention to AMP or Azure Monitor, mirror critical logs to Loki for LogQL, and export traces to Tempo plus Cloud Trace for teams that live in GCP consoles. The non-negotiable requirement is a written **telemetry routing policy** so you do not triple-pay for the same DEBUG log stream.

---

## SLOs, Error Budgets, and Symptom-Based Alerting

**Pause and predict:** If you configure an infrastructure alert rule that pages on-call engineers whenever CPU utilization exceeds 80% on any pod, but your customer contract is governed by latency Service Level Objectives, which alert will wake the team during a thread-pool exhaustion incident where checkout requests stall without elevating CPU?

<details>
<summary>Check your prediction</summary>

The CPU threshold alert will remain completely silent because thread-pool exhaustion starves application workers while consuming virtually zero CPU cycles. When worker threads block waiting on an unresponsive database query, downstream deadlock, or saturated connection pool, CPU utilization drops or stays flat even as incoming HTTP requests queue and timeout. Only a symptom-based alert monitoring latency percentiles (such as p99 request duration) or SLO error budget burn rates will fire and wake the on-call engineer during customer-impacting degradation. Alerting on infrastructure causes like CPU usage creates noise during benign spikes and blinds teams during silent application starvation incidents.
</details>

Reliable alerting structures prioritize customer impact over internal resource metrics to ensure on-call engineers respond to real service degradation. The following operational framework outlines how service level objectives and error budgets establish principled thresholds that distinguish critical customer symptoms from benign infrastructure events.

Telemetry exists to support decisions, not to fill disks. **Service Level Indicators (SLIs)** are precise measurements (availability, latency, freshness) drawn primarily from metrics, with logs and traces as debugging lenses. **Service Level Objectives (SLOs)** set targets over rolling windows (for example 99.9% of checkout requests faster than 500 ms over thirty days). The **error budget** is the allowed unreliability before the SLO fails; when the budget burns quickly, feature work yields to reliability work.

Symptom-based alerting pages humans on user-visible pain (SLO burn rate, failed synthetic probes, elevated 5xx rates) instead of every infrastructure twitch (single pod restart, node NotReady during drain). Multi-window, multi-burn-rate alerts (popularized in Google SRE practice) reduce false positives while still catching fast burns. Implementations typically use recording rules or Mimir/AMP ruler components to evaluate PromQL, then route through Alertmanager, PagerDuty, or cloud notification channels.

**Alert fatigue** arrives when hundreds of threshold rules fire during partial outages, training on-call engineers to ignore pages. The fix is consolidation: one page per customer-facing service with clear severity, runbooks linked from annotations, and automatic silences for known maintenance windows. Multi-cluster environments should include `cluster` and `region` labels in alert templates so responders know which kubeconfig to use without reading a wiki. Managed clouds add native channels—Amazon SNS for CloudWatch alarms, Google Cloud alerting policies, Azure Monitor action groups—but the routing discipline remains the same: symptom first, infrastructure cause second.

Recording rules for SLIs should be owned by the service team that owns the SLO, not only by central platform Prometheus. Central teams provide libraries (`slo:http_availability:ratio_rate5m`, `slo:http_latency:p99_rate5m`) and linting; product teams supply the `service` label selectors. That division prevents platform engineers from becoming bottlenecks every time a new deployment adds an HTTP route.

| Alert type | Example signal | Why it scales |
| :--- | :--- | :--- |
| Symptom | `slo:burn_rate5m > 14` for checkout | Correlates to customer pain |
| Cause | `KubeNodeNotReady` on one node | Useful after symptom fires |
| Cardinality guard | `prometheus_tsdb_head_series` growth | Prevents observability outage |

---

## Cost Lens: Observability as a Top-3 Cloud Line Item

Observability frequently lands in the top three non-compute cloud spends because pricing is **ingestion-linear**: every extra label value, log line, and span multiplies monthly cost more predictably than CPU throttling. FinOps teams that only right-size nodes while ignoring telemetry volume routinely save compute and still miss six-figure observability invoices.

**Metrics costs** scale with samples ingested per month. High scrape frequency (10s vs 60s), HA duplication without deduplication, and unbounded labels (`user_id`, raw URL paths) explode sample counts. Managed Prometheus services on AWS, GCP, and Azure all document ingestion-tier pricing; verify current rates in official pricing pages because tiers change. Mitigations: increase scrape interval for infra metrics, drop expensive labels in OTel `transform` processors, use recording rules, enable downsampling, and enforce per-team quotas in Mimir or AMP workspace limits.

**Logs costs** scale with gigabytes ingested and indexed. CloudWatch Logs charges ingestion and storage; Google Cloud Logging bills log volume; Azure Monitor log ingestion uses a pay-per-GB model in workspace analytics. Full-text search systems cost more than label-indexed Loki-style stores. Mitigations: structured logging at INFO in production, dynamic DEBUG only on targeted pods, tail sampling for verbose components, exclude health-check bodies, and tier retention (seven-day hot, thirty-day warm, archive for compliance).

**Traces costs** scale with span count. Storing one hundred percent of traces for a high-QPS API is rarely economical; tail sampling that retains errors and slow traces while sampling routine success paths is the standard compromise. Cross-region export of spans mirrors NAT/egress surprises seen in metrics and logs.

**Network costs** are the hidden multiplier. On AWS, NAT Gateway charges per gigabyte processed plus cross-AZ traffic; on GCP, Cloud NAT and inter-zone egress apply; on Azure, NAT Gateway and bandwidth meters add up. Centralizing all telemetry in one region from globally distributed clusters can cost more than the storage itself. Regional aggregation with summarized metrics and sampled logs/traces before cross-region transfer usually pays for itself.

| Knob | Affects | Risk if misapplied |
| :--- | :--- | :--- |
| Scrape interval | Metric samples | Miss short incidents |
| Label allow-lists | Cardinality | Blind spots in drill-down |
| Log sampling | Log GB/month | Lose rare failure evidence |
| Trace tail policies | Span storage | Over-retain routine traffic |
| Retention downsampling | Long-term $ | Lose fine-grain historical queries |

Kubecost and OpenCost attribute spend to namespaces and labels, but they do not replace cloud logging invoices. Use both: in-cluster attribution for engineering accountability, cloud billing exports for finance truth.

### Provider-Specific Cost Gotchas

**AWS:** NAT Gateway processing charges per gigabyte can exceed log storage when all DaemonSet shippers hairpin through a single NAT in a private subnet. Prefer VPC endpoints for S3 (Thanos/Loki blocks), AMP remote write endpoints, and CloudWatch Logs where available. Cross-AZ traffic between Prometheus replicas and ingesters also accrues silently during zone-balanced HA.

**GCP:** Inter-zone egress within a region still carries cost at scale; placing Loki ingesters and GKE nodes in the same zone during labs is fine, but production should document zone spread versus telemetry egress explicitly. Cloud Logging charges log volume; exporting everything at DEBUG from GKE workloads is the most common surprise.

**Azure:** NAT Gateway and bandwidth meters apply similarly to AWS patterns. Log Analytics ingestion bills per gigabyte ingested into a workspace; retaining verbose container stdout without transformation doubles both ingestion and retention cost.

None of these replace fundamental telemetry discipline: fewer labels, shorter retention for noisy signals, and sampling before export.

---

## Patterns & Anti-Patterns

| Pattern | When to Use | Why It Works | Scaling Note |
| :--- | :--- | :--- | :--- |
| Per-cluster Prometheus + global query | 3+ EKS/GKE/AKS clusters | Local scrape stays low-latency; global tier federates history | Add `cluster` external label on every write path |
| OTel Collector DaemonSet + central sampler | Node logs + app OTLP | Distributes CPU; tail sampling needs aggregation tier | Separate memory limits per pipeline signal |
| Recording rules + downsampling | Dashboards query heavy PromQL | Shrinks query cost and cardinality | Document rule ownership per team |
| Symptom SLO alerts with multi-burn windows | On-call sustainability | Pages correlate to user pain | Pair with runbooks linking metrics → traces |
| Regional telemetry aggregation | Multi-region active-active | Cuts NAT/egress before central store | Keep compliance data residency in region |

| Anti-Pattern | What Goes Wrong | Better Alternative |
| :--- | :--- | :--- |
| Central Prometheus scraping all clusters | OOM, cross-network scrape failures, security exposure | In-cluster Prometheus/Agent + Thanos/Mimir/AMP remote write |
| High-cardinality labels on metrics | TSDB explosion, AMP/Mimir bill spike | Bound labels; put IDs in traces/logs |
| `request_id` as Loki label | Ingester OOM, index blowout | Keep `request_id` in log line JSON field |
| 100% trace retention | Span storage dominates budget | Tail sampling for errors/slow paths |
| DEBUG logging fleet-wide | Log quota exhaustion | Dynamic log level + OTel filters |
| Duplicate export to cloud + Loki ungoverned | Pay twice for same bytes | Policy: one primary log sink per environment |
| CPU-threshold-only alerts | Miss latency SLO failures | Alert on SLI burn rates and synthetic checks |

---

## Decision Framework

Use this flow when choosing observability architecture for a new fleet or region expansion. It assumes Kubernetes 1.35, multi-account or multi-project governance, and finance scrutiny on ingestion bills.

```mermaid
flowchart TD
    Start[Fleet observability design] --> Clusters{How many clusters/regions?}
    Clusters -->|1-2| Simple[In-cluster kube-prometheus + Loki single binary]
    Clusters -->|3+| Global{Need single-pane global PromQL?}
    Global -->|Yes| Store{Prefer self-hosted object store or managed Prometheus?}
    Store -->|Self-hosted| Thanos[Thanos sidecar + querier + compactor]
    Store -->|Managed| CloudMP[AMP / GMP / Azure Monitor workspace RW]
    Global -->|No per-region only| Regional[Regional stacks + federated dashboards]
    Clusters -->|Compliance multi-cloud| OTel[OTel Collector standard + dual export policy]
    OTel --> Signals{Dominant pain today?}
    Signals -->|Metrics cardinality| Card[Label governance + recording rules + downsampling]
    Signals -->|Log cost| Log[Structured logs + sampling + retention tiers]
    Signals -->|Trace volume| Trace[Tail sampling Deployment tier]
    Card --> SLO[Define SLI/SLO + symptom alerts]
    Log --> SLO
    Trace --> SLO
```

| Decision input | Lean Thanos sidecar | Lean Mimir/AMP remote write | Lean managed logs (CloudWatch / Cloud Logging / Monitor) |
| :--- | :--- | :--- | :--- |
| Existing per-cluster Prometheus investment | High | Medium (agent mode) | N/A for metrics |
| Multi-tenant hard limits required | Medium (label hacks) | High | High (cloud IAM boundaries) |
| Team lacks TSDB operators | Low | Medium | High |
| Strict data residency per region | High (region-scoped buckets) | Medium (regional workspaces) | High |
| FinOps needs sample-level billing visibility | Medium | High on managed Prometheus | High on cloud logging |

### Build vs Buy Summary

| Requirement | Favor self-hosted (Thanos/Loki/Tempo) | Favor managed (AMP/GMP/Azure Monitor) |
| :--- | :--- | :--- |
| Identical config across AWS+GCP+Azure | Primary | Secondary (per-cloud workspaces) |
| Small platform SRE team | Risky unless automated | Strong |
| Enterprise IAM + PrivateLink | DIY with care | Strong |
| Custom tail-sampling laws | Full control | Constrained by service limits |
| Long-term cost at >1B samples/month | Tunable (object store tuning) | Tiered pricing—model before commit |

---

## Did You Know?

1. **Prometheus was created at SoundCloud in 2012** and was the second project (after Kubernetes) to join the CNCF in 2016. Despite this ubiquity, Prometheus was never designed for multi-cluster or long-term storage -- those capabilities come from ecosystem projects like Thanos, Cortex, and Mimir. The Prometheus project maintainers have explicitly stated that horizontal scalability is not a goal of the core project.

2. **A single Kubernetes node generates approximately 500-800 metric time series** just from kubelet and cAdvisor metrics, before any application metrics. A 100-node cluster starts with 50,000-80,000 baseline time series. Application metrics typically add 3-10x on top of this. This means a 100-node cluster with microservices easily reaches 500K-1M time series -- the point where a single Prometheus instance starts struggling.

3. **Grafana Loki's index is 10-100x smaller than Elasticsearch's** for the same log volume. Loki achieves this by indexing only labels (key-value metadata like namespace, pod name, and level), not the full text content. This means Loki is dramatically cheaper for storage but slower for full-text search queries. The design bet is that most log queries in Kubernetes filter by namespace and pod first, then grep through a small subset -- a bet that has proven correct for the majority of operational use cases.

4. **OpenTelemetry became the second most active CNCF project** (after Kubernetes itself) in 2023 by contributor count. The project unified two competing projects, OpenTracing and OpenCensus, and standardized on W3C Trace Context for propagation. The OTel Collector alone processes billions of telemetry signals per day across production deployments worldwide, making it arguably the most widely deployed data pipeline in cloud-native infrastructure.

Platform reviews should treat observability changes like capacity changes: every new label, log field, or span attribute needs an owner, a retention class, and a removal plan. That discipline keeps multi-cloud fleets understandable when AWS, GCP, and Azure invoices arrive in the same week. During incident retrospectives, ask whether missing telemetry caused slower mitigation; if yes, fund pipeline fixes before buying larger Prometheus pods. A one-page telemetry routing diagram prevents most observability gaps in production fleets across clouds.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Running a single Prometheus for all clusters | "Prometheus can handle it" | Shard Prometheus per cluster. Use Thanos or Mimir for cross-cluster querying. No single Prometheus should scrape more than 1M time series. |
| Storing metrics at full resolution forever | "We might need it" | Use Thanos Compactor to downsample: 5-second resolution for 2 weeks, 1-minute for 3 months, 5-minute for 1 year. Saves 90%+ storage. |
| No cardinality limits on application metrics | "Developers know best" | Set ingestion limits (per-tenant in Mimir, series limits in Prometheus). Add pre-aggregation rules. High-cardinality labels (user_id, request_id) should be trace attributes, not metric labels. |
| Logging everything at DEBUG level in production | "We might need the details" | Default to INFO in production. Use dynamic log level changes for debugging specific services. A single DEBUG-level service can generate more log volume than the rest of the cluster. |
| Not using tail-based sampling for traces | "We keep all traces" | At 10,000 spans/second, storing all traces costs thousands per month. Tail-based sampling keeps errors and slow traces (the ones you investigate) while sampling 5-10% of normal traces. |
| Running OTel Collector as a Deployment instead of DaemonSet for logs | "One collector is simpler" | A single Collector becomes a bottleneck and SPOF. DaemonSet (one per node) distributes the load and ensures logs are collected even if a collector crashes. Use Deployment only for aggregation/sampling tiers. |
| No resource limits on monitoring components | "Monitoring should always run" | A memory-unlimited Prometheus that OOM-kills takes down monitoring AND the node. Set memory limits and use memory_limiter processor in OTel Collector. |
| Separate dashboards per cluster | "Each team manages their own Grafana" | Use a central Grafana with Thanos as the data source. Cluster-specific dashboards with a cluster selector variable. Single pane of glass for on-call. |

---

## Quiz

<details>
<summary>1. Your organization has just acquired a startup, adding 5 new Kubernetes clusters to your existing 3. You decide to point your central Prometheus instance to scrape all 8 clusters. Within hours, Prometheus starts crash-looping. Why did this architectural decision fail, and what specific limitations were hit?</summary>

Prometheus was designed with a single-node, pull-based architecture that fundamentally assumes all targets are within the same cluster boundaries. When you point a single Prometheus at 8 clusters, it attempts to hold all active time series from every cluster in memory simultaneously, which quickly leads to catastrophic out-of-memory (OOM) crashes. Additionally, pulling metrics across cluster networks introduces significant latency and requires exposing secure metric endpoints to the public internet or managing complex VPNs. By adopting a distributed approach like Thanos or Mimir, you can keep a lightweight Prometheus scraper inside each cluster to handle local ingestion. These tools then push or serve the data to a centralized query tier, preventing any single instance from bearing the memory burden of the entire fleet.
</details>

<details>
<summary>2. You are tasked with designing a multi-cluster metrics platform. Your manager asks you to choose between Thanos and Grafana Mimir. You currently have Prometheus deployed in all clusters and rely heavily on it for local alerting. Which architectural differences should drive your decision?</summary>

The core architectural difference lies in how data is transported and queried across the platform. Thanos uses a decentralized, sidecar-based approach where your existing Prometheus instances continue to store short-term data, while the Thanos Querier reaches into each cluster to fan-out queries. This is ideal when you want to heavily leverage existing Prometheus deployments for local alerting, as local data remains accessible even if the central control plane is disconnected. Grafana Mimir, conversely, uses a push-based model where Prometheus simply acts as an agent forwarding data via `remote_write` to a centralized Mimir backend. Mimir is generally preferred if you need robust multi-tenancy and want to centralize all storage and querying, but it requires completely offloading storage responsibilities from your local Prometheus instances.
</details>

<details>
<summary>3. During a major marketing event, your Prometheus memory usage spikes from 32GB to 128GB in 10 minutes, and queries for `http_requests_total` time out. You discover this metric now has 200 million unique time series. What specific anti-pattern likely caused this sudden cardinality explosion, and how do you resolve it?</summary>

This sudden explosion in time series is almost certainly caused by developers injecting high-cardinality data—such as unique user IDs, transaction IDs, or raw request paths—into metric labels. Because every unique combination of label values creates an entirely new time series in the TSDB, a surge in unique users directly translates to a surge in memory consumption. To resolve this, you should quickly drop the offending labels using Prometheus relabeling rules or OTel Collector processors to stabilize the system. Moving forward, high-cardinality identifiers should be migrated to distributed trace attributes or structured logs, while metrics should only use bounded categories like HTTP status codes or normalized route templates.
</details>

<details>
<summary>4. Your security team is complaining that searching for a specific IP address across a month of Loki logs takes several minutes, whereas it took seconds in their old Elasticsearch cluster. However, your infrastructure bill is now 90% lower. What fundamental design choice in Loki explains both the cost savings and the slow query performance for this specific task?</summary>

Loki deliberately avoids building full-text inverted indexes of the actual log content, which is the primary driver of both storage costs and compute overhead in systems like Elasticsearch. Instead, Loki only indexes the metadata labels (such as namespace, application name, and log level) attached to the log streams. When the security team searches for an IP address, Loki must first use the label index to find the relevant chunks of compressed log text, and then literally scan through those text chunks to find the IP matches. This architectural trade-off sacrifices raw full-text search speed in exchange for massive storage efficiency, making it perfect for targeted operational debugging but less optimal for needle-in-a-haystack security forensics.
</details>

<details>
<summary>5. You are implementing distributed tracing for a high-traffic e-commerce site. You configure your OTel Collectors to sample 10% of all traces. The next day, developers complain that whenever a checkout fails, the corresponding trace is almost always missing from Tempo. Why did this sampling strategy fail your team, and what approach would guarantee error traces are kept?</summary>

You implemented head-based sampling, which makes a randomized keep-or-drop decision at the very beginning of the request lifecycle before the system knows whether the transaction will succeed or fail. Because failures are statistically rare, a 10% random sample means there is a 90% chance that the trace for a failed checkout is immediately discarded. To guarantee that valuable traces are retained, you must implement tail-based sampling in your OTel Collector architecture. Tail-based sampling buffers the entire trace in memory until it completes, allowing you to evaluate the full transaction and apply intelligent policies that typically keep traces containing errors or high latency while randomly sampling the successful, routine requests.
</details>

<details>
<summary>6. A poorly configured Java application goes into a crash loop, spamming multiline stack traces at DEBUG level. Within an hour, it consumes your entire daily logging quota in Loki, causing logs from other critical services to be dropped. How can you design a multi-layered filtering strategy to prevent this single service from monopolizing your log pipeline?</summary>

To prevent a single runaway application from taking down your logging infrastructure, you must implement controls at multiple stages of the telemetry pipeline. First, establish strict log level configurations at the application level to ensure production services default to INFO or WARN, preventing DEBUG spam from ever being emitted. Second, deploy OpenTelemetry Collectors configured with filtering processors to drop known noisy patterns or truncate excessively large log bodies before they consume network bandwidth. Finally, configure tenant-based rate limiting and quota enforcement within Loki itself. This ensures that even if an application bypasses local filters, it will only exhaust its own isolated namespace quota without impacting the observability of other critical infrastructure.
</details>

<details>
<summary>7. Your CFO asks why observability spend on AWS doubled after you connected six EKS clusters in eu-west-1 to a central AMP workspace in us-east-1. Prometheus samples look flat, but the bill spiked. Which cost dimensions should you investigate first, and what architectural change usually helps?</summary>

Start with cross-region remote write and NAT egress, because shipping every sample and metadata field across regions can dominate the invoice even when series counts look stable. Next inspect AMP samples ingested (tiered per-sample pricing), duplicate HA pairs without deduplication, and shorter scrape intervals on infrastructure jobs. Query samples processed also accrue when global dashboards run heavy range queries during incidents. The usual architectural fix is regional AMP workspaces (or regional Thanos/Mimir cells) with aggregated recording rules exported globally, plus OTel filters that drop high-cardinality labels before remote write leaves the cluster region.
</details>

<details>
<summary>8. Platform leadership wants one SLO dashboard for checkout across AKS, EKS, and GKE, but each cloud team exports metrics differently. What minimum contract should you standardize before picking Thanos versus managed Prometheus?</summary>

Standardize external labels (`cluster`, `region`, `environment`, `team`), metric names for SLIs (availability and latency histograms), and alert labels before debating storage engines. Require OpenTelemetry or Prometheus exporters to expose the same histogram buckets and route through collectors that enforce label allow-lists. With that contract, Thanos or Mimir can federate self-hosted data, while AMP, Google Cloud Managed Service for Prometheus, and Azure Monitor workspaces can remote-write into Grafana with identical PromQL recording rules. Without the contract, any global backend becomes a label zoo and SLO math diverges per cloud.
</details>

---

## Hands-On Exercise: Build a Multi-Cluster Monitoring Stack

In this advanced exercise, you will manually provision and configure a robust monitoring stack featuring Prometheus, a simulated Thanos Sidecar arrangement, an OpenTelemetry Collector, Loki for log aggregation, and Grafana for visualization. The lab intentionally runs on a single kind cluster with Kubernetes 1.35 to keep resource usage manageable, but the configuration patterns mirror production multi-cluster designs: external labels for future federation, DaemonSet collectors for per-node logs, memory limiters to avoid OOM during bursts, and cardinality reports you should run weekly in real fleets.

Before starting, internalize the production mapping: Task 1’s Prometheus external labels correspond to Thanos `cluster` labels; Task 2’s OTel→Loki path corresponds to regional aggregation before cloud logging export; Task 6’s cardinality report is the same PromQL you would paste into an incident channel when AMP ingestion spikes. If any step fails, check pod memory first—observability components are among the first to be starved when nodes are undersized. 

### Prerequisites

- kind cluster configured locally
- Helm package manager installed
- kubectl installed and configured

### Task 1: Deploy Prometheus with Thanos Sidecar

Initiate the deployment of the kube-prometheus-stack, injecting the Thanos sidecar to simulate local metric persistence destined for object storage.

<details>
<summary>Solution</summary>

```bash
# Create cluster
kind create cluster --name obs-lab --image kindest/node:v1.35.0

# Add Helm repos
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack with Thanos sidecar
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.replicas=1 \
  --set prometheus.prometheusSpec.retention=6h \
  --set 'prometheus.prometheusSpec.externalLabels.cluster=obs-lab' \
  --set 'prometheus.prometheusSpec.externalLabels.region=local' \
  --set alertmanager.enabled=false

# Wait for Prometheus to be ready
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=prometheus -n monitoring --timeout=300s

echo "Prometheus deployed with cluster labels"
```
</details>

### Task 2: Deploy Loki and OpenTelemetry Collector

Establish the log ingestion pathway. You will deploy Loki to store the logs and immediately overlay an OpenTelemetry Collector configured to dynamically process local container standard outputs.

<details>
<summary>Solution</summary>

```bash
# Add Loki helm repo
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Loki in monolithic mode for the lab (chart v12+ renamed SingleBinary → Monolithic)
helm install loki grafana/loki \
  --namespace monitoring \
  --set deploymentMode=Monolithic \
  --set loki.useTestSchema=true \
  --set loki.auth_enabled=false \
  --set loki.commonConfig.replication_factor=1 \
  --set loki.storage.type=filesystem \
  --set monolithic.replicas=1

# Install OpenTelemetry Operator/Collector
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Create OTel Collector values
cat <<'EOF' > otel-values.yaml
mode: daemonset
presets:
  logsCollection:
    enabled: true
config:
  receivers:
    filelog:
      include: [ /var/log/pods/*/*/*.log ]
  processors:
    memory_limiter:
      check_interval: 1s
      limit_percentage: 75
      spike_limit_percentage: 15
    batch:
      send_batch_size: 10000
      timeout: 10s
  exporters:
    otlphttp:
      endpoint: http://loki:3100/otlp
  service:
    pipelines:
      logs:
        receivers: [filelog]
        processors: [memory_limiter, batch]
        exporters: [otlphttp]
EOF

helm install otel-collector open-telemetry/opentelemetry-collector \
  --namespace monitoring \
  -f otel-values.yaml

# Wait for components
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=loki -n monitoring --timeout=300s
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=opentelemetry-collector -n monitoring --timeout=300s

echo "Loki and OTel Collector deployed successfully"
```
</details>

### Task 3: Deploy Sample Workloads for Log Collection

Deploy a sample nginx workload so the OTel `filelog` receiver has container logs to ship. Plain `nginx:stable` serves HTTP on port 80 only (no `/metrics`); kube-prometheus-stack discovers targets via ServiceMonitor/PodMonitor, not `prometheus.io/*` pod annotations—this task validates **log** ingestion, not app metric scraping.

<details>
<summary>Solution</summary>

```bash
# Deploy a sample app (stdout/stderr logs for filelog → Loki)
kubectl create namespace sample-app

kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-server
  namespace: sample-app
  labels:
    team: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-server
  template:
    metadata:
      labels:
        app: web-server
        team: backend
    spec:
      containers:
        - name: nginx
          image: nginx:stable
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: web-server
  namespace: sample-app
spec:
  selector:
    app: web-server
  ports:
    - port: 80
EOF

kubectl wait --for=condition=Ready pod -l app=web-server -n sample-app --timeout=60s
```
</details>

### Task 4: Query Cross-Cluster Metrics

Execute direct PromQL requests using `curl` against the exposed Prometheus API. Confirm `external_labels` via the status config API—they are attached on federation, remote-write, and Alertmanager paths, not on every local instant-query series.

<details>
<summary>Solution</summary>

```bash
# Port-forward to Prometheus
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &

sleep 3

# Query metrics using curl (PromQL API)
echo "=== Node Count ==="
curl -s 'http://localhost:9090/api/v1/query?query=count(up{job="kubelet"})' | jq '.data.result[0].value[1]'

echo "=== Pod Count by Namespace ==="
curl -s 'http://localhost:9090/api/v1/query?query=count(kube_pod_info)%20by%20(namespace)' | jq '.data.result[]'

echo "=== Top CPU Consumers ==="
curl -s 'http://localhost:9090/api/v1/query?query=topk(5,%20sum%20by%20(namespace,%20pod)%20(rate(container_cpu_usage_seconds_total{container!=""}[5m])))' | jq '.data.result[]'

echo "=== External labels (configured on Prometheus) ==="
curl -s 'http://localhost:9090/api/v1/status/config' | jq -r '.data.yaml' | grep -E 'external_labels|cluster:|region:'

# Stop port-forward
kill %1 2>/dev/null
```
</details>

### Task 5: Query Loki Logs via CLI

Validate that the OpenTelemetry log pipeline is successfully intercepting file logs and flushing them to Loki by leveraging the LogQL API.

<details>
<summary>Solution</summary>

```bash
# Port-forward to Loki
kubectl port-forward -n monitoring svc/loki 3100:3100 &

sleep 3

echo "=== Recent Log Lines from Sample App ==="
# We use LogQL to fetch logs from the sample app namespace
curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="sample-app"}' \
  --data-urlencode 'limit=5' | jq '.data.result[0].stream'

kill %1 2>/dev/null
```
</details>

### Task 6: Create a Cardinality Report

Diagnose potential TSDB bloat by generating an automated cardinality report, showcasing the metrics responsible for creating the most time series inside the database block.

<details>
<summary>Solution</summary>

```bash
# Port-forward to Prometheus
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &

sleep 3

echo "=== Total Active Time Series ==="
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' | \
  jq '.data.result[0].value[1]'

echo ""
echo "=== Top 10 Metrics by Series Count ==="
curl -s 'http://localhost:9090/api/v1/query?query=topk(10,%20count%20by%20(__name__)({__name__=~".%2B"}))' | \
  jq -r '.data.result[] | "\(.metric.__name__): \(.value[1]) series"'

echo ""
echo "=== Series Count by Job ==="
curl -s 'http://localhost:9090/api/v1/query?query=count%20by%20(job)%20({__name__=~".%2B"})' | \
  jq -r '.data.result[] | "\(.metric.job): \(.value[1]) series"'

echo ""
echo "=== Cardinality Recommendations ==="
echo "- If any single metric exceeds 10,000 series: investigate labels"
echo "- If total series > 500K: consider pre-aggregation with recording rules"
echo "- If 'pod' label creates >100 unique values: aggregate to deployment level"

kill %1 2>/dev/null
```
</details>

### Task 7: Set Up Grafana Dashboard

Conclude the setup by provisioning an interactive visualization layer, proving that all the previously verified metrics flow successfully into graphical panels.

<details>
<summary>Solution</summary>

```bash
# Port-forward to Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &

sleep 3

# Default credentials: admin / prom-operator
echo "Grafana available at http://localhost:3000"
echo "Username: admin"
echo "Password: prom-operator"

echo ""
echo "=== Dashboard Setup Steps ==="
echo "1. Log in to Grafana at http://localhost:3000"
echo "2. Navigate to Dashboards > New > Import"
echo "3. Import dashboard ID 315 (Kubernetes Cluster Monitoring)"
echo "4. Select the 'Prometheus' data source"
echo "5. Verify metrics appear with cluster=obs-lab label"

# Alternative: create dashboard via API
curl -s -X POST http://admin:prom-operator@localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d '{
    "dashboard": {
      "id": null,
      "title": "Cost Audit - Cluster Overview",
      "panels": [
        {
          "title": "Active Time Series",
          "type": "stat",
          "targets": [{"expr": "prometheus_tsdb_head_series"}],
          "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0}
        },
        {
          "title": "Pods by Namespace",
          "type": "piechart",
          "targets": [{"expr": "count(kube_pod_info) by (namespace)"}],
          "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4}
        }
      ]
    },
    "overwrite": true
  }' 2>/dev/null && echo "Dashboard created" || echo "Dashboard creation via API (optional)"

kill %1 2>/dev/null
```
</details>

### Clean Up

Always tear down infrastructure locally to free up resources immediately after laboratory exercises.

```bash
kind delete cluster --name obs-lab
```

Before you close the lab, audit the four claims below. Each open card states a hypothesis that sounds operationally plausible during large-scale observability and telemetry operations. Treat the claim as a prediction, then open the details only after you have an answer.

**Card A: When log volume spikes, memory_limiter drops logs first and keeps metrics and traces flowing.** A platform team configures a shared OpenTelemetry Collector DaemonSet to ingest metrics, structured container logs, and distributed traces from application nodes. To prevent the Collector process from running out of memory during traffic surges, the team enables the memory_limiter processor across all data pipelines. The team assumes that when an application enters debug logging mode, the processor will selectively throttle or drop the high-volume log pipeline first while allowing low-bandwidth metric scrapes and vital distributed traces to pass through unharmed.

<details>
<summary>Check your prediction</summary>

Failure layer: OpenTelemetry Collector process-level memory management versus pipeline-level prioritization. Next action: understand that `memory_limiter` acts as a blunt, process-wide circuit breaker that rejects **all** telemetry signals once memory limits are breached; the processor tracks total Go runtime heap allocation and refuses `ConsumeLogs`, `ConsumeTraces`, and `ConsumeMetrics` indiscriminately across every pipeline until memory usage drops below the configured soft limit; to prevent runaway logging from starving vital metrics and traces, isolate log collection into dedicated Collector instances or separate deployment tiers with distinct resource allocations.
</details>

**Card B: A recording rule that aggregates by deployment rewrites historical pod-level series so old dashboards automatically show the new aggregation.** An operations engineer discovers that storing raw per-pod HTTP request rates creates severe time-series cardinality bloat in Prometheus. To fix slow dashboard loading, the engineer deploys a recording rule that calculates the five-minute request rate aggregated strictly by deployment and namespace. The engineer expects that applying this rule will retroactively consolidate historical pod-level series stored in existing TSDB blocks so that historical trend charts seamlessly display the aggregated deployment metric across past months.

<details>
<summary>Check your prediction</summary>

Failure layer: Time-series database immutability and append-only evaluation semantics. Next action: recognize that Prometheus recording rules evaluate strictly **at current time** and append into an entirely **new** time series without rewriting or backfilling historical data; existing TSDB blocks remain unchanged until they reach their configured retention boundary and are removed; historical dashboards querying the original pod-level series must continue querying the old metric for past intervals or use PromQL queries that bridge the transition period, while the new recording rule optimizes query performance and storage going forward.
</details>

**Card C: A Jaeger client talking to a Zipkin client still produces one connected trace because HTTP already carries the request across the cluster boundary.** A payment platform integrates an upstream checkout service instrumented with the Jaeger OpenTelemetry client and a downstream fraud engine instrumented with legacy Zipkin libraries across different Kubernetes clusters. Because all microservice communication takes place over standard HTTP calls that carry headers across network boundaries, the integration lead assumes the two tracing engines will automatically stitch the request hops into a single unified trace waterfall in Grafana Tempo.

<details>
<summary>Check your prediction</summary>

Failure layer: Distributed context propagation protocol mismatch across heterogenous tracing implementations. Next action: configure explicit cross-system context propagators because HTTP transport alone does not resolve conflicting header specifications; legacy Zipkin clients inject and extract B3 propagation headers (`X-B3-TraceId`, `X-B3-SpanId`), whereas modern OpenTelemetry and Jaeger implementations default to the W3C Trace Context standard (`traceparent`); without aligning propagators or enabling B3 compatibility on the receiver, downstream services fail to recognize the incoming context and start a brand-new trace root, fracturing the transaction into disconnected fragments.
</details>

**Card D: CPU > 80% on every pod is the alert that pages during a thread-pool exhaustion incident that throttles checkout without high CPU.** An infrastructure engineering team relies on node and pod CPU saturation alarms to guard application health, configuring high-priority pages whenever container CPU usage sustains above eighty percent. When an upstream database connection stall triggers thread-pool exhaustion that prevents checkout requests from processing, the team expects the pod CPU alert to wake on-call engineers immediately before customers abandon their transactions.

<details>
<summary>Check your prediction</summary>

Failure layer: Cause-based infrastructure utilization alerting versus symptom-based user-impact detection. Next action: replace cause-oriented CPU thresholds with symptom-based alerts targeting Service Level Objectives such as latency percentiles and error budget burn rates; during thread-pool exhaustion or downstream connection blocking, worker threads sit idle waiting on blocked I/O, resulting in flat or plummeting CPU consumption while user-facing latency and error rates spike; page strictly on customer symptoms like elevated p99 latency or burn rates, retaining CPU utilization metrics as secondary debugging signals rather than primary escalation triggers.
</details>

**Success Criteria**:

- [ ] Prometheus correctly deployed with external labels injected (`cluster`, `region`).
- [ ] Loki and OpenTelemetry Collector daemonsets deployed and streaming unstructured pod logs without crashing.
- [ ] Sample nginx pods emit logs collected by OTel and queryable in Loki (no app `/metrics` scrape in this lab).
- [ ] Manual PromQL validation queries return JSON; external labels verified via `/api/v1/status/config` (not on local `up` series).
- [ ] Native LogQL queries cleanly return application logs from Loki's backend.
- [ ] The automated cardinality report accurately identifies the specific top metrics driving series count bloat.
- [ ] The main Grafana service is highly accessible over a secure port forward, with the correct Prometheus data source globally configured.

---

## Next Module

[Module 8.10: Scaling IaC & State Management](../module-8.10-iac-scale/) -- Your clusters are now highly observable, your ingestion costs are firmly optimized, and your architecture cleanly spans multiple regions. It is time to learn how to actively manage the infrastructure as code (IaC) that holds it all together. Delve into advanced Terraform state partitioning, robust module design, enterprise GitOps integration, and aggressive drift detection at massive operational scale.

## Sources

- [Amazon Managed Service for Prometheus](https://docs.aws.amazon.com/prometheus/latest/userguide/what-is-AMP.html) — Managed Prometheus-compatible metrics for container workloads on AWS.
- [Understand and optimize costs in AMP](https://docs.aws.amazon.com/prometheus/latest/userguide/AMP-costs.html) — AWS guidance on ingestion-driven cost drivers and Cost Explorer usage.
- [Amazon Managed Service for Prometheus pricing](https://aws.amazon.com/prometheus/pricing/) — Official sample-ingestion, storage, and query pricing tiers.
- [CloudWatch Logs pricing](https://aws.amazon.com/cloudwatch/pricing/) — Ingestion and storage model for AWS log pipelines.
- [AWS X-Ray developer guide](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html) — Trace collection and service map concepts on AWS.
- [Google Cloud Managed Service for Prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus) — GKE-oriented managed Prometheus metrics collection and querying.
- [Cloud Logging pricing](https://cloud.google.com/stackdriver/pricing) — Log volume and retention cost factors on GCP.
- [Cloud Trace documentation](https://cloud.google.com/trace/docs) — Distributed tracing on Google Cloud.
- [Azure Monitor managed Prometheus metrics](https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/prometheus-metrics-overview) — Managed Prometheus metrics workspaces for AKS and hybrid monitoring.
- [Application Insights overview](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview) — APM, traces, and telemetry for Azure workloads.
- [Azure Monitor log ingestion and billing](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/cost-logs) — Log Analytics ingestion cost guidance.
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) — Vendor-neutral telemetry ingestion, processing, and export pipelines.
- [Prometheus remote write](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_write) — Remote storage integration contract used by AMP, Mimir, and Cortex.
- [Thanos documentation](https://thanos.io/tip/thanos/getting-started.md/) — Multi-cluster long-term metric storage and global query architecture.
- [Grafana Loki overview](https://grafana.com/docs/loki/latest/get-started/overview/) — Label-based indexing model and scalable logging deployment modes.
- [Metrics for Kubernetes system components](https://kubernetes.io/docs/concepts/cluster-administration/system-metrics/) — Cluster-level metrics foundations for platform observability.
