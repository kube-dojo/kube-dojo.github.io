---
title: "Module 3.15: Azure Event Hub + Event Grid — Operator Path"
slug: cloud/azure-essentials/module-3.15-event-hub-event-grid
sidebar:
  order: 16
---
**Complexity**: `[COMPLEX]` | **Time to Complete**: 90-120 min | **Prerequisites**: [3.1-entra-id](../module-3.1-entra-id/), [3.2-vnet](../module-3.2-vnet/), [3.9-key-vault](../module-3.9-key-vault/), [3.10-monitor](../module-3.10-monitor/)

## What You'll Be Able to Do

After completing this module, you will be able to:

- **Compare** Event Hubs, Event Grid, Service Bus, Storage Queues, and Apache Kafka on AKS by matching each service to ordering, replay, fan-out, transaction, and ownership requirements.
- **Design** a secure Azure event pipeline with managed identity, RBAC, private endpoints, Capture, delivery retry, dead-lettering, and CloudEvents payloads.
- **Diagnose** Event Hubs throttling, consumer lag, Capture gaps, Event Grid delivery failures, and retry storms by using Azure Monitor metrics and Log Analytics queries.
- **Implement** an end-to-end Event Hubs Capture plus Event Grid notification flow with Azure CLI, a Python producer, and a webhook test endpoint.
- **Evaluate** the cost impact of throughput units, processing units, capture windows, retained blobs, Event Grid operations, namespace throughput, and cross-region replication.

The operator path is about choosing the right event service before an incident chooses it for you. Azure has several queues, brokers, and event routers because event-driven systems are not one shape. A telemetry firehose from thousands of devices, a storage-account blob-created notification, a command that must be processed once in order, and a developer-platform audit event all look like "messages" from far away. From close range they are different operational contracts, and the wrong contract creates expensive ambiguity.

## Why This Module Matters

Exercise scenario: a platform team receives three requests in the same planning meeting. The data team wants to ingest ten thousand telemetry records per second and replay a failed analytics job from yesterday. The application team wants a storage-account notification to call a webhook whenever a report blob lands. The finance team wants invoice commands processed exactly once, in order, with a dead-letter queue and manual replay. All three teams say they need "events", but only the first request naturally belongs on Event Hubs, only the second is a clean Event Grid fit, and the third is closer to Service Bus.

This distinction matters because managed event services fail in different ways. Event Hubs fails operationally when partitions are undersized, throughput units are capped too low, consumer groups are overloaded, checkpoints stall, or retention is shorter than the replay window. Event Grid fails operationally when a handler is down, filters match too broadly, validation is not handled, retries multiply delivery operations, or dead-letter storage is missing. Service Bus fails operationally when lock duration, sessions, duplicate detection, transactions, or dead-letter handling are misunderstood. The right service makes the incident obvious; the wrong service turns every event into a forensic puzzle.

The [Event Hubs overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-about) describes Event Hubs as a scalable event ingestion service, while the [Event Grid overview](https://learn.microsoft.com/en-us/azure/event-grid/overview) describes Event Grid as a highly scalable event routing service. Those words are easy to skim past, but they are the first split in the operator mental model. Event Hubs is where a stream lives long enough to be read, replayed, partitioned, and analyzed. Event Grid is where an event is routed to interested handlers and retried if delivery fails.

Use this picture as the simplest map:

```text
continuous stream                                      discrete event
high volume                                            low to moderate volume
ordered per partition                                  fan-out to handlers
reader controls pace                                   publisher pushes to router
consumer checkpoints                                   delivery attempts and dead-letter
replay from retention                                  no stream replay contract

        +------------------+                       +------------------+
        |   Event Hubs     |                       |    Event Grid    |
        | stream ingestion |                       | event routing    |
        +--------+---------+                       +--------+---------+
                 |                                          |
                 v                                          v
       analytics, Kafka clients,                 Functions, webhooks, queues,
       Capture, Stream Analytics                 Event Hubs, Service Bus
```

**Pause and predict:** A producer emits one million sensor readings each minute, and a downstream job must replay the last six hours after a bug fix. Would Event Grid or Event Hubs make the operator's recovery easier, and what property drives the answer?

<details>
<summary>Check your prediction</summary>

**Event Hubs** is the first candidate because it provides a durable partitioned stream where records are retained across the configured retention window, enabling consumer-controlled replay from past checkpoints. Event Grid is an event router that pushes transient notifications to registered handlers without maintaining a durable commit log or replayable stream offset history.
</details>

The rest of the module treats Event Hubs and Event Grid side by side. That is deliberate. Operators do not receive tickets that say "please create the correct service". They receive workload requirements, cost constraints, security rules, and incident symptoms. Your job is to translate those signals into the right managed event contract.

## Why Event-Driven Azure Has More Than One Service

Event-driven architecture is not only about decoupling. It is about choosing where time, order, pressure, and responsibility live. If the producer writes faster than the consumer reads, someone must absorb that pressure. If a handler is offline, someone must decide how long to retry. If a record is malformed, someone must keep enough evidence to debug it. If a consumer deploys a bad version, someone must decide whether replay is available.

Platform architects must analyze ingest scalability, processing latency expectations, and blast radiuses before provisioning cloud infrastructure. Telemetry flows demand dedicated buffering mechanisms to protect backend data stores during traffic spikes, whereas control-plane workflows require flexible routing policies to broadcast state changes across decoupled services. Evaluating how components handle sustained bursts and intermittent downstream downtime guarantees that system boundaries remain resilient under peak production loads.

The [Azure messaging comparison](https://learn.microsoft.com/en-us/azure/service-bus-messaging/compare-messaging-services) is worth reading because it prevents a common mistake: treating every message-shaped problem as Event Grid. Service Bus exists because enterprise commands need ordering, sessions, transactions, duplicate detection, lock renewal, scheduled delivery, and a first-class dead-letter queue. Storage Queues exist because some workloads need a simple, low-cost queue with huge storage capacity and fewer broker semantics. Event Grid exists because many systems only need a small event to say "something happened over there". Event Hubs exists because streams need ingestion, retention, partitioned reads, replay, and analytics integration.

### Streaming Versus Eventing

Streaming is a time-ordered flow of records. The data often has analytic value as a sequence, not just as individual messages. You care about partition keys because order is only guaranteed inside a partition. You care about retention because the stream is a recovery tool. You care about consumer lag because a reader can be healthy but behind. You care about throughput because one weak namespace can throttle every producer.

Eventing is a notification pattern. The event usually says that a resource changed, a workflow step completed, or an integration point should react. You care about filters because a handler should receive only relevant events. You care about delivery retries because the router pushes to subscribers. You care about validation because webhook endpoints must prove they own the address. You care about dead-lettering because a handler outage should not erase evidence.

```text
+---------------------+------------------------------+------------------------------+
| Operator question   | Streaming answer             | Eventing answer              |
+---------------------+------------------------------+------------------------------+
| Who controls pace?  | Consumer reads at its pace    | Router delivers to handler   |
| What is ordered?    | Records inside a partition    | No broad ordering contract   |
| How do I recover?   | Re-read retained records      | Retry or dead-letter events  |
| Where is pressure?  | Namespace throughput and lag  | Handler health and retries   |
| Common Azure fit    | Event Hubs                    | Event Grid                   |
+---------------------+------------------------------+------------------------------+
```

### Where Service Bus and Storage Queues Fit

**Pause and predict:** An engineering team considers placing invoice processing commands on Event Hubs, where each message requires session-state affinity for customer-level serialization, lock renewal during long-running approvals, and a first-class dead-letter queue for corrupted payloads. Should the team place these commands on Event Hubs?

<details>
<summary>Check your prediction</summary>

**Service Bus** is the first candidate for this workload. Event Hubs is a high-throughput partitioned data stream optimized for continuous ingestion and append-only reader checkpoints, not a competing-consumer message broker. It lacks message-level lock renewal, session state coordination across worker nodes, and native broker-managed dead-letter queues. Service Bus provides transaction boundaries, peek-lock settlement, duplicate detection, and explicit dead-lettering for poison messages.
</details>

Teams that run both billing workflows and telemetry pipelines usually keep change tickets separate so a spike in sensor volume cannot steal the same on-call rotation as a stuck invoice. Reviewers ask who owns retry, who owns poison-message handling, and which dashboard proves a command finished, before they argue about SKU names.

Storage Queues are useful when the message contract is simple and cost or storage capacity matters more than broker features. They are common in low-complexity worker patterns, simple retry loops, or systems that already depend heavily on Azure Storage. They do not replace Event Hubs for replayable streams or Event Grid for native Azure event routing.

### Worked Example: Four Requirements, Four Choices

A fleet of point-of-sale devices emits one-kilobyte telemetry records continuously. The analytics team wants to replay yesterday's records after fixing a parsing bug. Choose Event Hubs because retention, partitions, consumer groups, and replay are core to the service.

A storage account receives a nightly export file and must notify a compliance workflow. Choose Event Grid because the storage service already emits a blob-created event, and the workflow only needs a discrete notification.

An order command must preserve customer-level order and must move to a dead-letter queue after repeated processing failures. Choose Service Bus because sessions, lock renewal, and DLQ handling are the operational contract.

A research platform already runs Strimzi on AKS, requires custom Kafka broker configuration, and has a team that owns broker upgrades. Kafka on AKS may be justified because control and ecosystem compatibility matter more than managed-service convenience.

Now you solve it: your platform receives a request for "events" from a team that needs webhook fan-out to three SaaS endpoints, no replay, low message volume, and detailed failure evidence when an endpoint is down. Which service would you start with, and which feature must be configured before production?

## Event Hubs Deep Dive

Event Hubs is easiest to operate when you stop thinking of it as a queue. It is a partitioned commit log with managed ingestion, retention, and consumer coordination. Producers append events. Consumers read from partitions. Each consumer group has its own view of progress. Checkpoint storage records where a reader stopped so it can continue after a restart.

The [Event Hubs scalability guidance](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-scalability) ties the model to throughput units, processing units, and capacity units. Those units matter because Event Hubs is often placed at the front door of a data system. If the front door throttles, downstream services may look idle while producers fail.

### Partitions and Partition Keys

A partition is an ordered sequence inside an event hub. Event Hubs guarantees ordering within a partition, not across the entire event hub. That means a partition key is an operational decision, not a cosmetic field. If all records for `device-123` use the same partition key, those records stay ordered relative to each other. If every record uses the same key, one partition becomes hot while other partitions sit idle. If no key is used, Event Hubs distributes records across partitions, which is often good for throughput but removes affinity.

```text
event hub: telemetry

partition 0: device-a, device-a, device-a
partition 1: device-b, device-c, device-b
partition 2: device-d, device-e, device-d
partition 3: device-f, device-g, device-f

consumer group: analytics-prod
  checkpoint store says partition 0 offset N
  checkpoint store says partition 1 offset M
  checkpoint store says partition 2 offset P
  checkpoint store says partition 3 offset Q
```

Choose partition count before production with care. More partitions can improve parallelism, but they also increase reader coordination and may complicate per-key ordering assumptions. You cannot fix a poor partition-key strategy only by buying more throughput. If all writes land on one hot partition, the namespace can have spare capacity while one partition creates latency and throttling symptoms.

### Consumer Groups and Checkpoint Store

A consumer group is an independent view over the same stream. The analytics team, fraud team, and archive verifier can each have their own consumer group. One team falling behind does not move another team's checkpoint. That independence is valuable, but it also means every new consumer group can multiply outbound read load.

The checkpoint store is where the client records progress. Most Azure SDK examples use Blob Storage for checkpoints because it is durable, cheap, and easy to coordinate across multiple reader instances. The checkpoint is not the event data. It is the bookmark. If the checkpoint store is unavailable or permissions are wrong, readers may repeatedly reprocess events or fail to coordinate partition ownership.

### Tiers: Basic, Standard, Premium, Dedicated

The [Event Hubs quotas and tiers page](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-quotas) is the source you check before committing a design. The short version is that Basic is a low-cost ingestion tier with fewer features, Standard is the common shared-capacity production tier, Premium gives isolated resources and larger limits through processing units, and Dedicated gives single-tenant capacity through capacity units. Do not choose the tier from a feature name alone. Choose it from throughput, isolation, event size, Capture needs, private networking, schema registry, and operational blast radius.

| Tier | Capacity unit | Operator fit | Main tradeoff |
|---|---|---|---|
| Basic | Throughput unit | Low-cost ingestion where advanced production features are not needed | Fewer features and tighter limits |
| Standard | Throughput unit | Common production start for shared-capacity event ingestion | Multi-tenant capacity and explicit TU sizing |
| Premium | Processing unit | Stronger isolation, larger limits, private networking, schema registry, and included features | Higher hourly baseline |
| Dedicated | Capacity unit | Very high scale, strict isolation, and predictable broker capacity | Capacity-unit commitment and platform planning |

### Throughput Units, Processing Units, and Capacity Units

In Standard, a throughput unit is the planning unit. The commonly used mental model is one TU for up to one megabyte per second or one thousand events per second ingress, and up to two megabytes per second egress. The exact current limits and tier details belong in the Microsoft quota page, not in a runbook copied once and forgotten. The operator point is that both event count and bytes matter.

Worked sizing example: a telemetry workload sends ten thousand events per second, with one kilobyte average payloads, and the team wants eighty percent headroom. The event-rate requirement is ten thousand divided by one thousand divided by 0.8, which rounds up to thirteen TUs. The byte-rate requirement is about ten megabytes per second divided by one megabyte per second divided by 0.8, which also rounds up to thirteen TUs. The namespace should start at thirteen TUs or use auto-inflate with a ceiling above that value.

Using the public East US retail meters observed while writing this module, Standard Throughput Unit pricing was `$0.03` per hour and Standard ingress events were `$0.028` per million events. Thirteen TUs for a thirty-day month at seven hundred thirty hours is about `$284.70`. Ten thousand events per second for that month is about twenty-five billion nine hundred twenty million events, so the ingress-events meter is about `$725.76`. If Standard Capture is enabled on the namespace and billed at `$0.10` per hour, thirteen TUs add about `$949.00` before storage, reads, and regional data transfer. The rough monthly service subtotal is about `$1,959.46`, and the bill still needs blob storage, analytics readers, and Log Analytics ingestion.

That example is intentionally plain. It shows why a stream that sounds "small" because each record is one kilobyte can still have a meaningful monthly bill when the rate is continuous. Cost is not a finance-only concern here. If you undersize TUs, you buy incidents. If you oversize without telemetry, you buy idle capacity. If you enable Capture and retain blobs forever, you buy storage growth that never pages anyone until the budget alert fires.

### Auto-Inflate and Explicit Ceilings

Auto-inflate lets a Standard namespace increase throughput units when ingress pressure rises. It is useful because traffic rarely respects the spreadsheet. It is also not a license to ignore capacity planning. Auto-inflate needs a maximum ceiling, and that ceiling is a cost and reliability decision. Set it too low and producers still throttle during spikes. Set it too high and one buggy producer can create an expensive month.

Use auto-inflate when traffic is bursty, producers are important, and the team has alerts on both throttling and capacity. Use fixed TUs when traffic is stable, cost ceilings are strict, and the producer behavior is controlled. For critical workloads, alert before the ceiling is reached so the operator has time to decide whether to raise the ceiling, shed load, tune partitions, or move to Premium.

### Premium and Dedicated Capacity

Premium changes the conversation from shared throughput units to processing units. The [Event Hubs Premium overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-premium-overview) is the entry point for features such as stronger resource isolation, larger event sizes, private links, customer-managed keys, and included capabilities that are add-ons or constrained elsewhere. Premium often pays off when the workload is important enough that noisy-neighbor risk, larger events, private networking, schema registry, or predictable performance matter more than the lower Standard entry price.

Dedicated changes the conversation again. The [Event Hubs Dedicated overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-dedicated-overview) describes a single-tenant cluster model with capacity units. Dedicated is not the first stop for a normal application team. It is for organizations that have very high throughput, strict isolation requirements, or a platform team prepared to own capacity planning at a larger scale.

### Geo-Disaster Recovery Pairing

The [Event Hubs geo-disaster recovery documentation](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-geo-dr) describes alias-based namespace pairing. The alias is the stable name clients use, while the primary and secondary namespaces sit behind it. Failover moves the alias, which means clients can reconnect without a full application reconfiguration.

Geo-DR is not magic replication of every operational concern. Operators still need to understand what metadata is replicated, what event data is not available after a failover, how producers reconnect, how consumers recover checkpoints, and how downstream systems handle duplicates. If the business requirement is cross-region data durability for the event stream itself, Capture to geo-redundant storage or a separate replication design may be needed. An alias helps with namespace failover; it does not replace a recovery architecture.

### Capture to Blob or ADLS Gen2

The [Event Hubs Capture overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-capture-overview) explains how Event Hubs can write stream data to Azure Blob Storage or ADLS Gen2 in Avro format. Capture is a powerful operator feature because it decouples stream ingestion from batch analytics. The event hub can keep receiving data while downstream systems read files later. It is also a cost and data-lifecycle feature because those Avro blobs live in storage until lifecycle policy removes or tiers them.

Capture windows are configured by time and size. A short window creates smaller files and faster downstream visibility, but it can produce more objects and more listing overhead. A larger window produces fewer files, but it delays batch consumers. For many operational pipelines, a five-minute window is a practical starting point because it keeps the exercise observable without creating a file per event.

Exactly-once language needs precision. Event Hubs can preserve order within a partition and Capture can write Avro files reliably, but end-to-end exactly-once processing depends on producers, consumers, checkpointing, idempotent sinks, and failure recovery. If a consumer writes to a database and checkpoints before the write is durable, data can be lost. If it writes to a database and crashes before checkpointing, data can be processed twice. Design idempotent consumers and use deterministic event IDs when the business cannot tolerate duplicate side effects.

### Schema Registry

The [Event Hubs Schema Registry overview](https://learn.microsoft.com/en-us/azure/event-hubs/schema-registry-overview) gives teams a managed place to store schemas for Avro, JSON, and Protobuf payloads. That matters because streams usually outlive one producer version. If every producer invents its own payload shape, consumers become archaeology projects. Compatibility modes give operators a way to control evolution, such as allowing additive fields while blocking changes that break old consumers.

Schema Registry also helps when Kafka clients use Event Hubs through the Kafka surface. The schema contract should be independent of the client library. Whether a producer uses an Azure SDK or a Kafka client, the platform still needs a clear rule for payload evolution, ownership, and breaking changes.

### Kafka Surface

The [Event Hubs Kafka overview](https://learn.microsoft.com/en-us/azure/event-hubs/azure-event-hubs-apache-kafka-overview) explains how Event Hubs exposes an Apache Kafka-compatible endpoint for many Kafka clients. This is useful during migration or when an application already speaks the Kafka protocol. The operational benefit is that teams can use managed Event Hubs without running brokers, ZooKeeper-era components, or broker storage.

Many development organizations standardize on Apache Kafka client libraries to maintain consistency across distributed on-premises and multi-cloud architectures. Running self-hosted Kafka clusters requires continuous administrative maintenance, including broker node patching, storage rebalancing, and complex operational tuning. Managed endpoints eliminate broker infrastructure management tasks while enabling existing application runtimes to stream records directly into cloud environments without rewriting publisher or consumer codebases.

**Pause and predict:** A Kafka application depends on broker-level topic configuration and an admin API that Event Hubs does not support. What should the migration plan test before the cutover date?

<details>
<summary>Check your prediction</summary>

The Event Hubs Kafka surface is protocol-compatible, not identical to a dedicated Apache Kafka cluster. The migration plan must account for unsupported broker-level admin APIs by shifting topic provisioning to Azure Resource Manager templates, Bicep, or the Azure CLI. Operators must explicitly test Kafka client library versions, SASL and OAuth authentication mechanisms, partition and offset tracking semantics, transaction support, and monitoring telemetry before cutover.
</details>

Bridging stream ingestion into downstream notification workflows marks the boundary where continuous logging yields to event-driven orchestration. While partitioned commit logs excel at buffering millions of high-velocity metrics, distributed systems equally require lightweight notification channels to alert external microservices when critical operational milestones occur. Understanding how streaming platforms hand off state changes to reactive messaging meshes establishes the architectural foundation for building resilient Azure solutions.

## Event Grid Deep Dive

Event Grid is an event router. It receives an event from a source, evaluates subscriptions and filters, and delivers matching events to handlers. The [Event Grid overview](https://learn.microsoft.com/en-us/azure/event-grid/overview) is the map for topics, event subscriptions, schemas, and handlers. The important operator idea is that Event Grid owns routing and delivery attempts, not a durable stream that consumers replay at will.

```text
source service or app
      |
      v
+--------------------+
| Event Grid topic   |
| system/custom/etc. |
+---------+----------+
          |
          +--> subscription: Functions handler
          |
          +--> subscription: webhook handler
          |
          +--> subscription: Event Hubs sink
          |
          +--> subscription: Service Bus queue
```

### Topics, System Topics, Custom Topics, Partner Topics, and Domains

A topic is the endpoint where Event Grid receives events. System topics represent Azure resources that emit events, such as Storage Accounts. Custom topics are application-owned event entry points. Partner topics are used when a partner service publishes events into Azure. Domains group many topics under one management boundary, which is useful for SaaS-style multi-tenant publishing.

Use a system topic when the source is already an Azure resource that emits events. Use a custom topic when your application is the publisher. Use a domain when one publishing surface must serve many tenants or applications with topic-level isolation. Use a partner topic when the source is an integrated partner service. The question is not "which object can I create fastest"; it is "who owns the source, who owns the subscribers, and how many routing boundaries are needed?"

### Subscribers and Event Handlers

Event handlers include Azure Functions, Logic Apps, webhooks, Event Hubs, Service Bus, Storage Queues, Hybrid Connections, and other Azure endpoints. That list is the reason Event Grid is so useful as glue. An Event Grid subscription can call a serverless function, send to a queue, or bridge into Event Hubs for analytics. The handler choice should reflect the reliability contract.

Choose Functions for code that reacts immediately and scales with events. Choose Logic Apps for workflow integration where connectors and human-readable steps matter. Choose a webhook for external systems, but treat validation, authentication, idempotency, and retry behavior as production requirements. Choose Event Hubs as a destination when discrete Azure events need to join an analytics stream. Choose Service Bus when the event should become a durable command for enterprise processing. Choose Storage Queues when the consumer is simple and the queue semantics are enough.

### Event Grid Native Schema and CloudEvents

Event Grid supports its native event schema and the CloudEvents 1.0 schema. The [Event Grid event schema documentation](https://learn.microsoft.com/en-us/azure/event-grid/event-schema) describes the native shape and CloudEvents support. The [CloudEvents 1.0 specification](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md) exists because event producers and consumers need a common envelope for source, type, ID, time, subject, and data content.

Use CloudEvents when events cross team, platform, or vendor boundaries. It gives integration partners a standard envelope and reduces custom adapter code. Use the native Event Grid schema when you are staying inside Azure examples, legacy handlers expect it, or the source and handler already use that shape. Do not mix schemas casually. Schema is an API contract, and changing it can break subscribers even if the event data itself is unchanged.

Example CloudEvents-shaped storage notification, trimmed for readability:

```json
{
  "specversion": "1.0",
  "type": "Microsoft.Storage.BlobCreated",
  "source": "/subscriptions/.../storageAccounts/stdojocapture",
  "id": "event-id-from-event-grid",
  "time": "2026-05-19T12:00:00Z",
  "subject": "/blobServices/default/containers/capture/blobs/ns/hub/0/file.avro",
  "data": {
    "api": "PutBlob",
    "contentLength": 12345,
    "url": "https://stdojocapture.blob.core.windows.net/capture/ns/hub/0/file.avro"
  }
}
```

### Filtering

Filtering is where Event Grid becomes an operational tool instead of a noisy broadcast channel. The [Event Grid filtering documentation](https://learn.microsoft.com/en-us/azure/event-grid/event-filtering) covers event type filters, subject prefix and suffix filters, and advanced filters over event data. A good subscription is narrow enough that the handler can trust the incoming event stream. A broad subscription pushes filtering into code, increases delivery attempts, and makes incident triage harder.

Use event type filters to subscribe only to events such as `Microsoft.Storage.BlobCreated`. Use subject prefix filters to narrow to a container or virtual path. Use subject suffix filters for file extensions such as `.avro` when the subject convention is stable. Use advanced filters when the decision depends on data fields, but keep them understandable enough that an operator can audit the match rule at 2 AM.

### Delivery Retry and Dead-Lettering

The [Event Grid delivery and retry documentation](https://learn.microsoft.com/en-us/azure/event-grid/delivery-and-retry) provides essential operational specifications for managing failed deliveries to subscriber endpoints. Production architectures must account for endpoint degradation, downstream timeouts, and permanent subscriber outages without compromising event publishing pipelines.

**Pause and predict:** A subscriber webhook goes offline for several hours during an unexpected outage. Does Event Grid maintain a replayable ordered stream of undelivered notifications, and will it automatically protect against data loss by dead-lettering dropped events by default?

<details>
<summary>Check your prediction</summary>

Event Grid retries delivery using exponential backoff for up to **24 hours** by default, but it provides **no order guarantee** across retries and concurrent deliveries. Crucially, **dead-lettering is off by default**; unrouted events are permanently dropped once retry duration expires unless an explicit Azure Storage container is configured. Furthermore, non-retriable HTTP errors like 400 (Bad Request), 403 (Forbidden), and 413 (Payload Too Large) cause delivery to fail immediately without retry.
</details>

Production readiness reviews must verify event routing resilience before promoting subscriptions into live environments. Operations teams establish proactive alert rules on delivery metric spikes and track subscription latency in Azure Monitor. Maintaining rigorous observability across integration endpoints keeps subscriber outages from becoming silent publisher incidents.

### Event Grid Namespaces, MQTT, and Pull Delivery

Event Grid Namespaces matter when Event Grid becomes more than a push-webhook router. The [Event Grid namespace concepts](https://learn.microsoft.com/en-us/azure/event-grid/concepts-event-grid-namespaces) describe namespace topics, clients, topic spaces, permission bindings, and pull delivery. Namespaces also support an MQTT v5 broker surface, which is important for IoT-style clients that speak MQTT and need brokered pub-sub behavior.

Use the namespace model when clients need MQTT v5, pull delivery, or a more explicit client/topic permission model. Do not choose namespaces just because they are newer. For a simple Azure Storage blob-created notification to an Azure Function, a system topic and event subscription are still the clearer shape. For many device clients publishing through MQTT topic spaces, namespaces may be the feature that makes Event Grid the right entry point.

## Decision Framework: Event Hubs, Event Grid, Service Bus, or Kafka on AKS

Operators need a decision framework because service names are poor requirements. Start with the failure you need to survive. If a consumer is down, do you need replay from a stream, delivery retry from a router, a dead-letter queue with lock semantics, or broker control inside Kubernetes? The answer usually selects the service before any feature checklist does.

```text
start
  |
  v
Need ordered replayable high-throughput stream?
  | yes -> Event Hubs
  | no
  v
Need discrete notification fan-out to handlers?
  | yes -> Event Grid
  | no
  v
Need commands, sessions, transactions, FIFO, DLQ?
  | yes -> Service Bus
  | no
  v
Need Kafka broker control, plugins, or self-managed compliance?
  | yes -> Kafka on AKS with Strimzi
  | no -> Storage Queue, Function trigger, or simpler integration
```

| Requirement | First candidate | Why |
|---|---|---|
| High-throughput telemetry ingestion | Event Hubs | Partitioned stream, retention, consumer groups, replay, analytics |
| Blob-created event to webhook | Event Grid | Native system topic, filters, push delivery, retry, dead-letter |
| Invoice command with sessions | Service Bus | FIFO-like sessions, locks, transactions, DLQ, duplicate detection |
| Simple background work item | Storage Queue | Low ceremony, storage-backed queue, fewer broker features |
| Existing Kafka app without broker ownership | Event Hubs Kafka surface | Kafka protocol bridge to managed ingestion |
| Kafka with custom broker configuration | Kafka on AKS | Control over brokers, plugins, storage, network, and upgrade timing |
| Azure control-plane event fan-out | Event Grid | System topics and event subscriptions match the pattern |

### Event Hubs Wins When

Use Event Hubs when the workload is high-throughput ingestion, observability telemetry, clickstream data, device readings, security events, or analytics data. The key signals are continuous arrival, partition affinity, replay requirements, multiple independent readers, Kafka client compatibility, or downstream systems such as Stream Analytics, Azure Data Explorer, Databricks, or custom consumers. Event Hubs is also useful as the Event Grid destination when discrete Azure events need to become a stream for audit or analytics.

### Event Grid Wins When

Use Event Grid when the workload is a discrete event notification. The key signals are fan-out, webhook integration, Azure resource events, SaaS-style integration, serverless handlers, low to moderate event rate, and push or pull delivery. Event Grid is the right mental model for "notify subscribers that something happened" rather than "store this stream so consumers can replay it later".

### Service Bus Wins When

Use Service Bus when messages are business commands and the handler must coordinate processing state. Sessions, duplicate detection, scheduled messages, transactions, lock renewal, and dead-letter queues are not optional details for many enterprise workflows. This module does not teach Service Bus in depth, but it must protect you from choosing Event Grid when the real requirement is command processing.

### Apache Kafka on AKS Wins When

Use Kafka on AKS with an operator such as Strimzi only when the organization needs broker-level control and accepts broker-level responsibility. Valid reasons include regulatory constraints that block a managed service, custom broker plugins, strict network topology, specialized retention and compaction policies, ecosystem tools that require Kafka broker behavior, or a platform team already operating Kafka well. Invalid reasons include "we know Kafka" when no one wants to patch brokers, size disks, tune JVMs, test rolling upgrades, or own weekend incidents.

## Identity, Networking, and Security

Security for event systems is mostly about removing shared secrets, shrinking network paths, and making data-plane permissions explicit. The same lesson from Entra ID, VNet, Key Vault, and Monitor appears again here: production failures often come from identity and network assumptions that were invisible during a portal demo.

### Managed Identity and RBAC

For Event Hubs data access, prefer managed identity with Azure RBAC when the producer or consumer runs in Azure. Use roles such as `Azure Event Hubs Data Sender`, `Azure Event Hubs Data Receiver`, and `Azure Event Hubs Data Owner`. Grant the narrowest useful scope, often the event hub or namespace rather than the subscription. For local development, `DefaultAzureCredential` can use a developer login, but production should run under a managed identity or workload identity.

Example role assignment for the signed-in user during the lab:

```bash
EVENTHUB_ID="$(az eventhubs eventhub show \
  --resource-group "$RG" \
  --namespace-name "$EH_NAMESPACE" \
  --name "$EVENTHUB_NAME" \
  --query id \
  --output tsv)"

USER_OBJECT_ID="$(az ad signed-in-user show --query id --output tsv)"

az role assignment create \
  --assignee "$USER_OBJECT_ID" \
  --role "Azure Event Hubs Data Sender" \
  --scope "$EVENTHUB_ID"
```

SAS tokens still exist because not every producer can use Entra ID. They are useful for external clients, constrained devices, legacy libraries, and integration points that understand connection strings but not managed identity. They also increase secret-management burden. If you use SAS, create separate policies for send and listen, rotate keys, store secrets in Key Vault, avoid namespace-wide root policies for applications, and prefer short-lived generated SAS tokens when possible.

### Private Endpoints, Firewalls, and Service Endpoints

Network controls answer a different question than RBAC. RBAC says who can call the data plane. Private endpoints, firewalls, and service endpoints decide which network paths can reach the service endpoint. For Event Hubs Standard and Premium, private networking patterns are common when producers and consumers run in VNets. Private endpoints move access through Private Link. IP firewall rules restrict public ingress. VNet service endpoints can be useful in supported patterns, but private endpoints are usually the cleaner zero-public-path design for new production workloads.

Event Grid has its own network realities. A webhook endpoint must be reachable by Event Grid unless you route through supported private or Azure-native handlers. External webhooks need validation, authentication, idempotency, and rate limits. When a private application needs to receive events, consider Azure-native handlers, private endpoints where supported, or queue-based indirection rather than exposing a fragile internal webhook.

### TLS and Customer-Managed Keys

TLS should be table stakes for every path. The more interesting production decision is key ownership. Customer-managed keys for Event Hubs are available in higher tiers such as Premium and Dedicated, and they pull Key Vault operations into the availability path. That is not bad, but it must be designed deliberately. If a key is disabled, deleted, or blocked by networking, the event service can be affected. Treat CMK as a compliance and operational commitment, not a checkbox.

### Security Review Checklist

- Producers use managed identity or tightly scoped SAS policies.
- Consumers have receiver permissions only where they read.
- Capture storage has lifecycle policy, RBAC, and network controls.
- Event Grid webhook subscriptions have validation and authentication.
- Dead-letter storage is not public and has a retention owner.
- Diagnostic settings send logs and metrics to the right workspace.
- Private endpoints and DNS are tested from the actual producer subnet.
- Break-glass procedures cover key rotation and namespace failover.

## Cost Lens: Capacity, Operations, and Hidden Spikes

Cost belongs in the design review because event systems scale quietly. A stream can run every second of the month. A broken Event Grid handler can retry for hours. Capture can create storage that outlives the application. Geo-DR and replication can add cross-region data transfer. Log Analytics can ingest large diagnostic volumes if every event is logged by application code.

### Event Hubs Standard Cost Model

Standard Event Hubs has several cost surfaces. Throughput units are hourly capacity. Ingress events can be metered per million events. Capture can add an hourly meter and storage charges. Kafka endpoint usage can add a meter in some pricing models. Networking, cross-region transfer, storage transactions, and monitoring are outside the simple namespace price.

Worked example recap:

| Input | Value |
|---|---:|
| Event rate | 10,000 events/sec |
| Average payload | 1 KB |
| Ingress data | about 10 MB/sec |
| Headroom target | 80 percent utilization |
| Required TUs by event count | 13 |
| Required TUs by bytes | 13 |
| Planning TUs | 13 |
| Approx TU monthly cost | `$284.70` |
| Approx ingress event cost | `$725.76` |
| Approx Standard Capture cost | `$949.00` |

The important part is not the exact dollar total. Prices vary by region, currency, tier, reservation, and date, so the [Event Hubs pricing page](https://azure.microsoft.com/en-us/pricing/details/event-hubs/) is the source of truth before purchase. The important part is the method: calculate both event rate and byte rate, apply headroom, add retention and Capture costs, then model the downstream readers.

### Event Hubs Premium Cost Model

Premium uses processing units instead of Standard throughput units. The hourly baseline is higher, but Premium can pay off when it avoids throttling incidents, multi-tenant contention, larger-event workarounds, separate add-on costs, or private-network and schema requirements that would otherwise create complexity. Premium is usually a production decision for important streams, not a default for every small integration.

The inflection point is not only math. If a Standard namespace needs many TUs, constant auto-inflate, separate isolation per team, private networking, schema registry, and larger event sizes, Premium may be cheaper operationally even if the service line item is higher. That is the difference between cloud cost and engineering cost.

### Event Grid Cost Model

Event Grid charges around operations. Publishing, matching, delivery attempts, namespace throughput, and MQTT operations can all matter depending on the tier and feature set. The [Event Grid pricing page](https://azure.microsoft.com/en-us/pricing/details/event-grid/) should be checked during design because operation counting can surprise teams that think a single event is always a single billable unit.

Example: one million storage blob-created events per month delivered to three subscribers is not only one million events in the system. There is a publish side, matching work, and delivery to each subscriber. If one webhook is unavailable and Event Grid retries repeatedly, delivery attempts increase. If dead-lettering is enabled, Storage costs also appear. Retry storms are therefore both reliability and cost incidents.

### Where Costs Spike

Undersized Event Hubs TUs spike cost and risk in two ways. If auto-inflate is enabled with a high ceiling, a sudden producer bug can increase hourly capacity. If auto-inflate is disabled or capped too low, producers throttle, retry, and push costs elsewhere. Set a ceiling, alert near the ceiling, and tie the alert to a runbook that distinguishes expected launch traffic from malformed producer loops.

Capture costs spike when files are retained without lifecycle rules. Set storage lifecycle policies for raw Avro blobs. Move old data to cool or archive tiers only when downstream readers can tolerate access latency and retrieval charges. If compliance requires retention, record the owner and retention period in the module or Terraform variable, not in tribal memory.

Geo-DR and replication costs spike when data crosses regions or when duplicate pipelines run hot. Namespace alias failover is not the same as free replicated analytics data. Plan cross-region data transfer, Capture storage replication, and duplicate consumer behavior before the disaster recovery exercise.

Event Grid costs spike when handlers are unavailable. Every failing delivery path creates retries until policy is exhausted. The operator response is not simply "increase retry duration". Fix authentication, scale the handler, reduce filter breadth, use a queue as a buffer, or dead-letter events so the retry loop does not punish a dependency that is already unhealthy.

## Observability and Operator Queries

Observability for event systems has two sides. The broker or router tells you about capacity, delivery, and throttling. The application tells you whether it processed the event safely. Do not accept a dashboard that only shows producer success. A stream can ingest successfully while every consumer is a day behind. An Event Grid subscription can publish successfully while the webhook is failing validation.

### Event Hubs Metrics

The [Event Hubs monitoring reference](https://learn.microsoft.com/en-us/azure/event-hubs/monitor-event-hubs-reference) is the metric source to use when building dashboards. Operators commonly watch incoming bytes, incoming messages or requests, outgoing bytes, outgoing messages, throttled requests, server errors, user errors, connections, and captured bytes. For Capture, watch whether captured bytes move when events are flowing. For consumers, Azure Monitor does not magically know every checkpoint store, so lag often requires comparing last enqueued sequence numbers with stored checkpoints.

Practical Event Hubs dashboard panels should answer the questions an on-call operator asks before opening the portal blades one by one. Each panel needs an owner, an expected range, and a runbook link so the dashboard becomes an operating surface rather than a wall of charts.

| Panel | Signal | Operator question |
|---|---|---|
| Incoming bytes and messages | Producer volume | Is traffic normal or spiking? |
| Throttled requests | Capacity pressure | Are TUs or partitions limiting writes? |
| Outgoing bytes and messages | Consumer reads | Are consumers active? |
| Captured bytes | Capture health | Are Avro files being written? |
| Server errors and user errors | Service and client failures | Is the problem Azure-side or caller-side? |
| Active connections | Client behavior | Did a deploy drop or multiply connections? |

Example KQL for Event Hubs metrics in Azure Monitor can start with the namespace-level pressure signals, then drill into a specific event hub or consumer application once you know whether the broker is throttling:

```kusto
AzureMetrics
| where ResourceProvider == "MICROSOFT.EVENTHUB"
| where Resource has "ehns-dojo"
| where MetricName in ("IncomingBytes", "OutgoingBytes", "ThrottledRequests")
| summarize Total = sum(Total) by MetricName, bin(TimeGenerated, 5m)
| order by TimeGenerated asc
```

Example KQL for a throttling view should be used as an alert investigation query because any nonzero throttling means producers are already experiencing backpressure or retries:

```kusto
AzureMetrics
| where ResourceProvider == "MICROSOFT.EVENTHUB"
| where MetricName == "ThrottledRequests"
| summarize Throttled = sum(Total) by Resource, bin(TimeGenerated, 5m)
| where Throttled > 0
| order by TimeGenerated desc
```

Consumer lag is harder because the checkpoint store is application-owned. One practical approach is to emit application metrics that record the last processed sequence number per partition and compare it with the last enqueued sequence number from Event Hubs runtime properties. If the difference grows, the consumer is behind. If the difference shrinks, it is catching up. If it is flat while incoming volume continues, the consumer is stuck.

### Event Grid Metrics

The [Event Grid metrics reference for topics](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-eventgrid-topics-metrics) includes delivery and failure signals such as successful delivery, failed delivery attempts, dropped events, and publish success or failure. For production subscriptions, alert on failed attempts before dropped events. Dropped events mean the system has already exhausted delivery or could not deliver. Failed attempts mean the operator still has time to fix the handler, authentication, filter, or network path.

Example KQL for Event Grid delivery failures should compare successful delivery, failed attempts, and dropped events so the operator can separate a transient endpoint issue from actual event loss:

```kusto
AzureMetrics
| where ResourceProvider == "MICROSOFT.EVENTGRID"
| where MetricName in ("DeliveryAttemptFailCount", "DeliverySuccessCount", "DroppedEventCount")
| summarize Total = sum(Total) by Resource, MetricName, bin(TimeGenerated, 5m)
| order by TimeGenerated desc
```

Example KQL for a handler outage pattern should focus on the failure rate over time because raw failure counts can look alarming during a traffic spike and quiet during a low-volume outage:

```kusto
AzureMetrics
| where ResourceProvider == "MICROSOFT.EVENTGRID"
| where MetricName in ("DeliveryAttemptFailCount", "DeliverySuccessCount")
| summarize Failed = sumif(Total, MetricName == "DeliveryAttemptFailCount"),
            Succeeded = sumif(Total, MetricName == "DeliverySuccessCount")
            by Resource, bin(TimeGenerated, 10m)
| extend FailureRate = todouble(Failed) / todouble(Failed + Succeeded)
| where Failed > 0
| order by TimeGenerated desc
```

### Operational Runbook: Event Hubs Throttling

When producers report throttling, first verify whether the namespace is at its capacity ceiling. Check incoming bytes, incoming requests, throttled requests, and TU or PU settings. Then check partition distribution. If one partition is hot because of a bad partition key, adding TUs may not fix the real problem. Next check producer retry behavior. Aggressive retries can multiply pressure. Finally decide whether to raise the TU ceiling, enable auto-inflate, tune partition keys, add partitions for new hubs, or move to Premium.

### Operational Runbook: Event Grid Delivery Failure

When Event Grid delivery fails, start with the subscription. Verify endpoint validation, authentication, filter rules, endpoint DNS, TLS certificate, and handler response codes. Then check retry policy and dead-letter configuration. If the handler is a webhook, confirm it returns success only after durable acceptance. If the handler does real work synchronously and times out, put a queue or Function in front of the slow work. Event Grid should not be forced to wait while a downstream batch job runs.

## Patterns & Anti-Patterns

Patterns and anti-patterns are where service knowledge becomes operational judgment. Most production mistakes are not because a team never heard of Event Hubs or Event Grid. They happen because the team used the right feature in the wrong place, or ignored the cost and failure mode attached to it.

| Pattern | When to use it | Why it works | Scaling consideration |
|---|---|---|---|
| Event Hubs for telemetry streams | Continuous high-volume records with replay needs | Consumers control pace and checkpoints | Plan partitions, TUs, retention, and consumer groups |
| Event Grid to Service Bus | Discrete events that trigger reliable command processing | Event Grid routes, Service Bus owns command semantics | Monitor delivery and queue depth separately |
| Event Grid to Event Hubs | Azure resource events need analytics or audit replay | Event Grid captures discrete source events into a stream | Avoid broad filters that flood the stream |
| Capture to ADLS Gen2 | Stream data needs batch analytics or compliance archive | Avro files decouple ingestion from readers | Add lifecycle policy and schema ownership |
| CloudEvents at boundaries | Events cross teams, vendors, or platforms | Standard envelope reduces adapter code | Version payload schemas separately |
| Private endpoint for critical producers | Producers live in controlled VNets | Reduces public exposure and simplifies network policy | Test DNS and failover path before launch |

| Anti-pattern | What goes wrong | Better alternative |
|---|---|---|
| Event Grid as a command queue | Retries and delivery do not replace sessions, locks, and transactions | Use Service Bus for commands |
| One partition key for all events | One hot partition limits throughput and order assumptions become fragile | Choose a key with useful affinity and distribution |
| One consumer group per pod | Outbound load and checkpoint coordination become chaotic | Share a consumer group per logical application |
| Capture without lifecycle policy | Storage grows forever and no one owns retention | Add lifecycle rules and retention owners |
| Webhook does slow processing inline | Event Grid retries when the handler times out | Acknowledge quickly, enqueue work, process asynchronously |
| SAS root policy in application config | Key rotation and blast radius become painful | Use managed identity or narrow SAS policies |

## Did You Know?

- Event Hubs Standard capacity planning must consider both event count and byte rate; a workload can be under the event limit and over the byte limit at the same time.
- Event Hubs Capture writes Avro files, so downstream readers should treat the archive as a typed data product rather than a pile of opaque blobs.
- CloudEvents 1.0 standardizes the event envelope, but it does not standardize your business payload; you still need schema ownership and compatibility rules.
- Event Grid retry behavior can turn one unhealthy webhook into many delivery attempts, so dead-letter storage and handler health alerts are cost controls as well as reliability controls.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Choosing Event Grid for ordered business commands | The word event hides the need for sessions, locks, and DLQ handling | Use Service Bus when command semantics drive the requirement |
| Sizing Event Hubs only by event count | Payload size is ignored during planning | Calculate required units from both events per second and megabytes per second |
| Treating partition count as a late tuning knob | Early demos use defaults and production needs arrive later | Choose partition count and key strategy during design review |
| Creating many consumer groups casually | Every group is an independent reader view and can add load | Create groups only for real independent applications |
| Leaving Capture blobs forever | Archive data feels harmless because it is cheap per GB | Add lifecycle rules, retention owners, and storage cost alerts |
| Filtering Event Grid in handler code only | It is faster to write code than to design subscriptions | Use event type, subject, and advanced filters at the subscription |
| Skipping Event Grid dead-letter storage | The happy path works during development | Configure dead-lettering before production and test handler failure |

## Quiz

<details><summary>Your telemetry producer sends steady one-kilobyte records at a rate that sometimes doubles during business events. Consumers must replay the stream after a failed deployment. Which Azure service is the first candidate, and what two capacity signals do you check?</summary>
Event Hubs is the first candidate because the workload is continuous, high-throughput, and replayable. Check event rate and byte rate because Standard throughput planning can be constrained by either messages per second or megabytes per second. You should also watch throttled requests and consumer lag during the business event. Event Grid would be a poor fit because the requirement is a retained stream, not only push notification fan-out.
</details>

<details><summary>A storage account writes Avro Capture files, and three teams want notification when new blobs land. One team wants a webhook, one wants a Function, and one wants messages in Service Bus. What design keeps the source simple?</summary>
Use an Event Grid system topic on the Storage Account with separate event subscriptions for each handler. Filter the subscriptions to the capture container and blob path so unrelated storage events do not reach the handlers. The Service Bus subscriber can turn the notification into durable command processing if that team needs queue semantics. Keep dead-letter storage configured because webhook and Function failures should leave evidence.
</details>

<details><summary>A payment workflow requires per-customer ordering, duplicate detection, transactions, and a dead-letter queue for manual repair. A developer proposes Event Grid because the messages are called events. How do you respond?</summary>
The requirements point to Service Bus, not Event Grid. Event Grid is an event router with delivery attempts; it is not the right primitive for transactional command handling with sessions and broker-managed dead-letter queues. You can still use Event Grid upstream to notify that a resource changed, but the payment command itself belongs on a messaging service built for that contract. The design review should name the failure mode: a duplicate or out-of-order payment command is a business incident.
</details>

<details><summary>Consumers are behind by several hours even though Event Hubs incoming metrics look normal and producers are not throttled. What do you inspect next?</summary>
Inspect outgoing bytes or messages, consumer application health, checkpoint ownership, and the checkpoint store permissions. Event Hubs can ingest successfully while a consumer is stuck or repeatedly reprocessing the same partition. Compare last processed sequence numbers with last enqueued sequence numbers per partition if the application emits that telemetry. Adding throughput units may not help if the reader has a code, identity, or checkpoint problem.
</details>

<details><summary>An Event Grid webhook subscription shows rising failed delivery attempts after a certificate rotation. What operator actions come before increasing the retry duration?</summary>
First validate the endpoint TLS chain, DNS, authentication, and webhook response status. Then check the Event Grid subscription validation and dead-letter configuration so failed events are not lost. Increasing retry duration can multiply pressure against a broken endpoint, so it is not the first fix. If the handler does slow work, put a queue or Function in front of it and acknowledge receipt quickly.
</details>

<details><summary>A Kafka application team wants to move to Event Hubs through the Kafka endpoint. They use admin APIs and broker-specific topic settings in their deployment scripts. What should the migration plan prove?</summary>
The plan must prove that the specific Kafka client version, authentication mode, offset behavior, producer settings, and admin operations work against Event Hubs. Kafka protocol compatibility does not mean every broker feature or configuration knob exists. Scripts that assume self-managed broker control may need to change or remain on Kafka. If those broker controls are mandatory, Kafka on AKS with Strimzi may be the more honest platform choice.
</details>

<details><summary>A team enables Capture for a busy event hub and celebrates that analytics now has raw files. Two months later storage cost grows faster than expected. What design gap caused the surprise?</summary>
Capture created durable Avro blobs, but the team did not define lifecycle policy, retention ownership, or downstream access patterns. Capture is not only an ingestion feature; it is a storage lifecycle commitment. The fix is to set tiering and deletion rules that match compliance and analytics needs, and to alert on captured bytes and storage growth. The cost review should include both Event Hubs meters and storage meters.
</details>

## Hands-On Exercise: Event Hubs Capture to Event Grid Webhook

Exercise scenario: you will build a small event pipeline without AKS. The flow is Event Hubs ingestion, Capture to Storage as Avro files, Event Grid notification from the Storage Account, and a webhook test endpoint that receives CloudEvents-shaped blob-created events. Use a non-production subscription or a short-lived resource group. Delete the resource group when you finish.

Before executing deployment commands in a cloud environment, engineers must evaluate architectural boundaries, operational contracts, and failure layers across ingestion, routing, and enterprise messaging services. Reviewing common design fallacies ensures operational readiness when diagnosing event pipeline incidents under real production conditions.

**Card A: Event Grid is the first candidate for one million sensor readings per minute that must replay the last six hours.** A solutions architect selects Event Grid to ingest continuous high-volume telemetry from a distributed IoT sensor fleet and plans to replay records after downstream pipeline failures. The architect assumes reactive event routing naturally includes durable stream storage, partition checkpointing, and time-based message replay.

<details>
<summary>Check your prediction</summary>

Failure layer: streaming versus event routing architectural boundaries. Next action: designate Event Hubs as the ingestion service because it provides partitioned commit log durability, configurable data retention windows, and consumer-controlled checkpoint replay for high-throughput continuous streams.
</details>

**Card B: The Event Hubs Kafka endpoint is a drop-in replacement for every Kafka broker admin API and topic configuration.** An infrastructure engineer migrates an on-premises Kafka cluster to Azure Event Hubs without code changes and assumes automated deployment scripts can manage topic configurations, log compaction, and partition settings via standard Kafka admin APIs. The engineer treats managed protocol compatibility as equivalent to self-hosted broker semantics.

<details>
<summary>Check your prediction</summary>

Failure layer: protocol compatibility versus managed broker administrative capabilities. Next action: validate Kafka client libraries, partition assignments, and authentication against Event Hubs while migrating topic lifecycle management to Azure Resource Manager, Bicep, or the Azure CLI rather than relying on unsupported Kafka admin APIs.
</details>

**Card C: Event Grid dead-letters undelivered events by default and delivers them in order.** A systems operator deploys an Event Grid subscription to deliver state changes to an external webhook and expects undelivered events to be saved automatically in storage during endpoint downtime without reordering during retry cycles. The operator assumes default subscription provisioning protects against message loss and preserves chronological sequence.

<details>
<summary>Check your prediction</summary>

Failure layer: event delivery retry mechanics and dead-letter configuration defaults. Next action: configure an explicit dead-letter storage container on the event subscription with managed identity permissions, and design downstream consumers to be idempotent to handle out-of-order deliveries and duplicate delivery attempts.
</details>

**Card D: Event Hubs is the first candidate for invoice commands that need sessions and a first-class dead-letter queue.** A billing developer selects Event Hubs to process customer payment and invoice commands, assuming partitioned streams provide message locking, transaction boundaries, and automated routing of malformed commands to a dead-letter queue. The developer treats a high-throughput stream ingestion service as an enterprise command broker.

<details>
<summary>Check your prediction</summary>

Failure layer: enterprise message broker semantics versus data streaming pipelines. Next action: designate Azure Service Bus as the primary messaging service because it natively provides message sessions for FIFO ordering, peek-lock settlement, message lock renewal, transaction support, and built-in dead-letter queues.
</details>

**Success Criteria**:

- [ ] Resource group, Storage Account, Event Hubs namespace, and event hub exist in one region.
- [ ] Event hub has four partitions and Capture enabled with a five-minute window.
- [ ] Your identity can send events to the event hub through Azure RBAC.
- [ ] The Python producer sends at least one hundred events without a connection string.
- [ ] Storage contains at least one Avro Capture blob under the expected container path.
- [ ] Event Grid system topic exists for the Storage Account.
- [ ] Webhook test endpoint receives a CloudEvents-formatted `Microsoft.Storage.BlobCreated` event for the Capture container.
- [ ] Backpressure test produces or explains throttling signals and records the operator response.

### Step One: Set Variables and Create the Resource Group

Pick a short unique suffix because Storage Account and Event Hubs namespace names are globally constrained. The commands use `eastus` for consistency with the cost examples, but you can choose a closer supported region.

```bash
export LOCATION="eastus"
export SUFFIX="$(date +%s | tail -c 6)"
export RG="rg-dojo-eventing-${SUFFIX}"
export STORAGE="stdojoeh${SUFFIX}"
export CAPTURE_CONTAINER="capture"
export EH_NAMESPACE="ehns-dojo-${SUFFIX}"
export EVENTHUB_NAME="telemetry"
export SYSTEM_TOPIC="egst-dojo-storage-${SUFFIX}"
export EG_SUB="egsub-capture-webhook"

az group create \
  --name "$RG" \
  --location "$LOCATION"
```

Expected result: the resource group exists, and every later resource lands in the same region unless the command says otherwise.

### Step Two: Create Storage for Capture and Dead-Letter Evidence

The lab uses one Storage Account for Capture output and Event Grid dead-letter examples. In production, you may separate archive and dead-letter storage so retention, access, and incident review permissions are clearer.

```bash
az storage account create \
  --resource-group "$RG" \
  --name "$STORAGE" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

STORAGE_ID="$(az storage account show \
  --resource-group "$RG" \
  --name "$STORAGE" \
  --query id \
  --output tsv)"

USER_OBJECT_ID="$(az ad signed-in-user show --query id --output tsv)"

az role assignment create \
  --assignee "$USER_OBJECT_ID" \
  --role "Storage Blob Data Contributor" \
  --scope "$STORAGE_ID"

az storage container create \
  --account-name "$STORAGE" \
  --name "$CAPTURE_CONTAINER" \
  --auth-mode login
```

If the container creation fails immediately after role assignment, wait a minute and retry. Azure RBAC propagation is not instant, and the failure is usually an authorization delay rather than a storage problem.

### Step Three: Create Event Hubs Namespace and Event Hub with Capture

Create a Standard namespace with two throughput units. Then create one event hub with four partitions and Capture enabled to the container. The archive naming format keeps namespace, hub, partition, and time in the path so operators can inspect Capture output without opening every file.

```bash
az eventhubs namespace create \
  --resource-group "$RG" \
  --name "$EH_NAMESPACE" \
  --location "$LOCATION" \
  --sku Standard \
  --capacity 2

az eventhubs eventhub create \
  --resource-group "$RG" \
  --namespace-name "$EH_NAMESPACE" \
  --name "$EVENTHUB_NAME" \
  --partition-count 4 \
  --message-retention 1 \
  --enable-capture true \
  --capture-interval 300 \
  --capture-size-limit 10485760 \
  --destination-name EventHubArchive.AzureBlockBlob \
  --storage-account "$STORAGE_ID" \
  --blob-container "$CAPTURE_CONTAINER" \
  --archive-name-format "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}"
```

Expected result: the event hub exists with four partitions, and the Capture settings point to your storage container. If your installed Azure CLI uses slightly different parameter names for Capture, run `az eventhubs eventhub create --help` and keep the same values.

### Step Four: Grant Send Permission and Install Producer Dependencies

The producer uses `DefaultAzureCredential`, so it can use your Azure CLI login locally and managed identity in Azure. This avoids putting an Event Hubs connection string in a script.

```bash
EVENTHUB_ID="$(az eventhubs eventhub show \
  --resource-group "$RG" \
  --namespace-name "$EH_NAMESPACE" \
  --name "$EVENTHUB_NAME" \
  --query id \
  --output tsv)"

az role assignment create \
  --assignee "$USER_OBJECT_ID" \
  --role "Azure Event Hubs Data Sender" \
  --scope "$EVENTHUB_ID"

.venv/bin/python -m pip install azure-eventhub azure-identity
```

Create `send_events.py` in a temporary lab directory outside the repo or paste it into your shell with an editor. The snippet is intentionally complete and runnable as-is after the environment variables are set.

```python
import json
import os
import time
import uuid
from datetime import datetime, timezone

from azure.eventhub import EventData, EventHubProducerClient
from azure.identity import DefaultAzureCredential


fully_qualified_namespace = f"{os.environ['EH_NAMESPACE']}.servicebus.windows.net"
eventhub_name = os.environ["EVENTHUB_NAME"]
event_count = int(os.environ.get("EVENT_COUNT", "100"))
batch_size = int(os.environ.get("EVENT_BATCH_SIZE", "20"))
payload_bytes = int(os.environ.get("EVENT_PAYLOAD_BYTES", "1024"))
sleep_ms = int(os.environ.get("EVENT_SLEEP_MS", "50"))

credential = DefaultAzureCredential()
producer = EventHubProducerClient(
    fully_qualified_namespace=fully_qualified_namespace,
    eventhub_name=eventhub_name,
    credential=credential,
)


def build_event(index: int) -> EventData:
    device_id = f"device-{index % 8:02d}"
    body = {
        "event_id": str(uuid.uuid4()),
        "device_id": device_id,
        "sequence": index,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "payload": "x" * payload_bytes,
    }
    event = EventData(json.dumps(body))
    event.properties = {
        "content-type": "application/json",
        "schema": "dojo.telemetry.v1",
    }
    return event


sent = 0
started = time.perf_counter()

with producer:
    while sent < event_count:
        batch = producer.create_batch(partition_key=f"device-{sent % 8:02d}")
        for _ in range(min(batch_size, event_count - sent)):
            batch.add(build_event(sent))
            sent += 1
        producer.send_batch(batch)
        if sleep_ms:
            time.sleep(sleep_ms / 1000)

elapsed = time.perf_counter() - started
print(f"sent={sent} elapsed_seconds={elapsed:.2f} rate={sent / elapsed:.1f}_events_per_second")
```

Run the producer:

```bash
export EH_NAMESPACE
export EVENTHUB_NAME
.venv/bin/python send_events.py
```

Expected result: the script prints `sent=100` and exits without a connection string. If authentication fails, run `az login`, verify the RBAC assignment scope, and wait for propagation.

### Step Five: Verify Capture Wrote Avro Blobs

Capture writes on a time or size window, so wait at least five minutes unless your event volume reaches the size limit first. Then list blobs in the capture container.

```bash
az storage blob list \
  --account-name "$STORAGE" \
  --container-name "$CAPTURE_CONTAINER" \
  --auth-mode login \
  --query "[].name" \
  --output table
```

Expected result: at least one path appears with the namespace, event hub name, partition ID, and time components. If no blobs appear, check `CapturedBytes`, the Capture configuration, Storage permissions, and whether enough time has passed for the Capture window.

### Step Six: Create the Event Grid System Topic

Create a system topic for the Storage Account. This makes the Storage Account the Event Grid source for blob-created notifications.

```bash
az eventgrid system-topic create \
  --resource-group "$RG" \
  --name "$SYSTEM_TOPIC" \
  --location "$LOCATION" \
  --topic-type Microsoft.Storage.StorageAccounts \
  --source "$STORAGE_ID"
```

Expected result: the system topic exists and points to the Storage Account resource ID.

### Step Seven: Subscribe a Webhook to Capture BlobCreated Events

Create a temporary endpoint at a service such as `https://webhook.site`. Copy the unique URL into `WEBHOOK_URL`. Do not use a production webhook for this lab.

```bash
export WEBHOOK_URL="https://webhook.site/your-temporary-id"

az eventgrid system-topic event-subscription create \
  --resource-group "$RG" \
  --system-topic-name "$SYSTEM_TOPIC" \
  --name "$EG_SUB" \
  --endpoint-type webhook \
  --endpoint "$WEBHOOK_URL" \
  --event-delivery-schema cloudeventschemav1_0 \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/${CAPTURE_CONTAINER}/blobs/${EH_NAMESPACE}/${EVENTHUB_NAME}/"
```

Event Grid sends a validation event when you create a webhook subscription. Webhook test sites usually record the validation request but may not automatically echo the validation code. If the portal or CLI shows validation pending, open the captured validation event and use the `validationUrl` if present. That step proves why production webhooks need explicit validation handling.

Run the producer again and wait for another Capture window:

```bash
EVENT_COUNT=200 EVENT_BATCH_SIZE=25 EVENT_SLEEP_MS=25 .venv/bin/python send_events.py
```

Expected result: the webhook site receives a CloudEvents payload with `type` equal to `Microsoft.Storage.BlobCreated`, and the `subject` points into your Capture container.

### Step Eight: Trigger and Interpret Backpressure

Lower the namespace from two throughput units to one. Then run a larger producer burst with bigger payloads. The goal is to observe throttling or understand why your local producer cannot generate enough pressure.

```bash
az eventhubs namespace update \
  --resource-group "$RG" \
  --name "$EH_NAMESPACE" \
  --capacity 1

EVENT_COUNT=5000 \
EVENT_BATCH_SIZE=100 \
EVENT_PAYLOAD_BYTES=2048 \
EVENT_SLEEP_MS=0 \
  .venv/bin/python send_events.py
```

Check the metrics:

```bash
az monitor metrics list \
  --resource "$EVENTHUB_ID" \
  --metric IncomingRequests,ThrottledRequests,IncomingBytes \
  --interval PT1M \
  --aggregation Total \
  --output table
```

Expected result: if your producer exceeds the namespace capacity, `ThrottledRequests` rises. If it does not rise, record the measured producer rate and explain that the workstation did not exceed the one-TU envelope. The operator response is still the same decision tree: enable auto-inflate with a ceiling, raise explicit TUs, reduce producer retry pressure, tune partition keys, increase partitions for new hubs, or move to Premium when isolation and features justify it.

### Cleanup

Delete the resource group when you are done. This removes the namespace, storage, system topic, event subscription, and captured blobs.

```bash
az group delete \
  --name "$RG" \
  --yes \
  --no-wait
```

## Sources

- [Azure Event Hubs overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-about) - Defines Event Hubs as the managed ingestion and streaming service used for the stream mental model.
- [Event Hubs quotas and limits](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-quotas) - Grounds tier comparisons, capacity limits, and planning boundaries.
- [Event Hubs scalability](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-scalability) - Explains throughput units, processing units, capacity units, and auto-inflate.
- [Event Hubs Capture overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-capture-overview) - Documents Capture to Blob Storage or ADLS Gen2 and Avro archive behavior.
- [Event Hubs geo-disaster recovery](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-geo-dr) - Explains alias-based namespace pairing and failover behavior.
- [Event Hubs Premium overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-premium-overview) - Supports the Premium tier isolation and feature discussion.
- [Event Hubs Dedicated overview](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-dedicated-overview) - Supports capacity-unit and single-tenant cluster guidance.
- [Event Hubs Schema Registry](https://learn.microsoft.com/en-us/azure/event-hubs/schema-registry-overview) - Documents schema groups and Avro, JSON, and Protobuf schema management.
- [Event Hubs for Apache Kafka](https://learn.microsoft.com/en-us/azure/event-hubs/azure-event-hubs-apache-kafka-overview) - Documents the Kafka-compatible endpoint and migration considerations.
- [Event Hubs monitoring reference](https://learn.microsoft.com/en-us/azure/event-hubs/monitor-event-hubs-reference) - Provides Event Hubs metrics and diagnostic categories for dashboards.
- [Azure Event Grid overview](https://learn.microsoft.com/en-us/azure/event-grid/overview) - Defines Event Grid as Azure's event routing service.
- [Azure messaging services comparison](https://learn.microsoft.com/en-us/azure/service-bus-messaging/compare-messaging-services) - Compares Event Grid, Event Hubs, Service Bus, and Storage Queues.
- [Event Grid event schema](https://learn.microsoft.com/en-us/azure/event-grid/event-schema) - Documents native Event Grid schema and CloudEvents support.
- [Event Grid delivery and retry](https://learn.microsoft.com/en-us/azure/event-grid/delivery-and-retry) - Explains retry behavior, dead-lettering, and delivery failure handling.
- [Event Grid filtering](https://learn.microsoft.com/en-us/azure/event-grid/event-filtering) - Documents subject filters, event type filters, and advanced filters.
- [Event Grid namespace concepts](https://learn.microsoft.com/en-us/azure/event-grid/concepts-event-grid-namespaces) - Explains namespaces, clients, topic spaces, permissions, and pull delivery.
- [Event Grid topics metrics reference](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-eventgrid-topics-metrics) - Provides Event Grid delivery and failure metrics.
- [Azure Event Hubs pricing](https://azure.microsoft.com/en-us/pricing/details/event-hubs/) - Pricing source for throughput, ingress, Capture, Premium, and Dedicated cost checks.
- [Azure Event Grid pricing](https://azure.microsoft.com/en-us/pricing/details/event-grid/) - Pricing source for Event Grid operations, namespace throughput, and MQTT cost checks.
- [CloudEvents 1.0 specification](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md) - Defines the standard event envelope used for cross-platform event contracts.

## Next Module

Continue to [Azure SQL Database](../module-3.16-azure-sql/) to add a managed relational data tier to the Azure services you have been assembling.
