---
title: "Module 6.6: Knative — Serverless Workloads on Kubernetes"
slug: platform/toolkits/developer-experience/scaling-reliability/module-6.6-knative
revision_pending: false
sidebar:
  order: 7
---
> **Toolkit Track** | Complexity: `[COMPLEX]` | Time: ~55 minutes

## Overview

You have 200 microservices running in your cluster. Most of them sit idle 80% of the time, burning CPU and memory doing nothing. Knative brings serverless to Kubernetes — your workloads scale to zero when nobody is using them and spin back up in seconds when traffic arrives. No proprietary FaaS lock-in, no cloud-specific APIs. Just Kubernetes, with an off switch.

In this module you will learn what serverless on Kubernetes actually means and how it differs from cloud FaaS, how Knative Serving manages serverless workloads through Services, Configurations, Revisions, Routes, and scale-to-zero autoscaling, how Knative Eventing handles event-driven architectures with CloudEvents, Brokers, Triggers, and Sources, how the activator proxy and cold starts work under the hood, how to configure traffic splitting for blue-green and canary deployments, how to install Knative with different networking layers, and when Knative is the right tool versus other approaches.

Before starting, ensure you are comfortable with Kubernetes Deployments, Services, and Ingress basics, understand scale-to-zero concepts from the KEDA module, have SLO awareness from the Reliability Engineering track, and are familiar with Helm and kubectl.

---

## What You'll Be Able to Do

After completing this module, you will be able to:

- **Deploy Knative Serving for serverless workloads with automatic scaling and revision management**
- **Configure Knative traffic splitting for canary deployments and A/B testing across service revisions**
- **Implement Knative Eventing with brokers, triggers, and event sources for event-driven architectures**
- **Compare Knative's serverless model against traditional Kubernetes Deployments for variable-traffic workloads**

---

## Why This Module Matters

Hypothetical scenario: a mid-size company ran 200 microservices on EKS. The team sized every deployment for peak load because nobody wanted to be the person whose service fell over during the monthly billing run. The result: roughly 80% of services sat idle most of the day, consuming reserved CPU and memory. The monthly cloud bill was approximately $45,000.

A platform engineer analyzed the traffic patterns and found that roughly 140 of those 200 services received fewer than 10 requests per hour outside of business hours — many received zero. The team migrated those 140 low-traffic services to Knative Serving with scale-to-zero enabled. Services that previously ran 24/7 now spun down after 60 seconds of inactivity and cold-started in under 2 seconds when traffic returned. The monthly bill dropped to approximately $12,000. The 60 always-on services kept their regular Deployments. The 140 bursty services got Knative. Nobody noticed the difference in latency because a 1.5-second cold start on an internal admin dashboard is invisible. The only thing that changed was the bill.

The lesson is not merely that serverless saves money — it is that the cost gap between always-on and on-demand compute reveals how much of our infrastructure spending goes toward idle capacity rather than actual work. In traditional Kubernetes, every Deployment replica consumes node resources whether it is handling requests or waiting for them. A three-replica service costs the same at 3 AM as it does at 3 PM, even if the 3 AM traffic is zero. Serverless on Kubernetes changes that equation: resources are allocated only when work exists to be done, and released the moment work stops. The hard part is knowing which workloads can sleep safely and which ones must stay warm. This module teaches you both the technical mechanics and the decision framework for making that call.

---

## What Is Serverless on Kubernetes?

Let us clear up the biggest misconception first. "Serverless" does not mean "no servers." It means servers that manage themselves — specifically, servers whose lifecycle is driven by demand rather than by human operators setting static replica counts. The marketing promise of "no servers to manage" is an exaggeration, but the underlying capability is real and valuable: workloads that scale to zero when idle, scale up automatically when requests arrive, and charge you only for the resources actually consumed rather than the resources you reserved just in case.

What distinguishes serverless on Kubernetes from cloud FaaS platforms like AWS Lambda or Azure Functions is that it runs inside your own cluster, using your own container images, subject to your own security policies and network topology. You are not handing your code to a proprietary runtime with opaque execution limits and vendor-specific APIs. You are deploying standard OCI containers that happen to have an autoscaler smart enough to turn them off when nobody is using them and turn them back on when someone shows up. This portability matters because it means the same service — same image, same configuration, same deployment artifacts — can run on any Kubernetes cluster, whether that cluster lives in AWS, GCP, on-premises, or in a developer's kind cluster on a laptop.

The cost model is the most immediate and tangible benefit. A traditional Kubernetes Deployment with three replicas running 24/7 consumes approximately 3 vCPU and 1.5 GB of memory continuously, costing perhaps \$50 per service per month at typical cloud instance pricing. That same workload under Knative, receiving traffic 2 hours per day on average, might consume resources for only 2 hours, costing approximately \$3-\$5 per month depending on the cold-start overhead and the specific resource profile. The ratio — roughly 10:1 for bursty workloads — is what makes serverless compelling for internal tools, admin dashboards, reporting APIs, and any service whose traffic pattern is spiky rather than steady.

```
"SERVERLESS" DOES NOT MEAN "NO SERVERS"
================================================================

What marketing says:
  "No servers to manage!"

What it actually means:
  "Servers that manage themselves."

Specifically:
  1. Scale to zero when idle (no pods running = no cost)
  2. Scale up automatically when requests arrive
  3. Developer provides container, platform handles the rest
  4. Pay for what you use, not what you reserve

================================================================

TRADITIONAL DEPLOYMENT vs KNATIVE
================================================================

Traditional:
  3 replicas ──────────────────────────── 3 replicas
  Running 24/7, even at 3 AM with zero traffic

Knative:
  0 pods ─── request ──▶ 1 pod ─── idle ──▶ 0 pods
  Only running when actively serving traffic

Cost comparison (per service, approximate):
  Traditional: ~$50/month (always on)
  Knative:     ~$3/month  (runs 2 hours/day average)
================================================================
```

Serverless on Kubernetes means your cluster still exists, your nodes still run, but individual workloads can sleep. Think of it like the difference between leaving every light in your house on 24/7 versus installing motion sensors — the house is still there, the wiring still works, but the lights only draw power when someone is in the room.

---

## Knative Serving

Knative Serving is the component that manages your serverless workloads. It introduces four Kubernetes Custom Resources that work together, but the central design decision — the one that shapes everything else — is that you as the developer create only one of them. The other three are derived automatically. This is not a convenience; it is a correctness guarantee. By deriving Configuration, Revision, and Route from a single Service specification, Knative prevents the class of configuration drift bugs where your desired state, your running state, and your traffic routing state disagree with each other. Every Knative Service is a single source of truth for what should be running and how traffic should reach it.

### The Four Resources

The Service resource (commonly abbreviated `ksvc` to distinguish it from the core Kubernetes Service) is the only object you write and apply. When you create or update a Knative Service, the Knative control plane does three things simultaneously. First, it writes your container specification into a Configuration object that describes the desired state of your workload — the image, environment variables, resource limits, and autoscaling annotations. Second, it snapshots that Configuration into an immutable Revision, which is a point-in-time record of exactly what was running. Third, it updates the Route to point network traffic at the appropriate Revision according to the traffic rules you specified.

```yaml
```

This four-way split exists because each resource answers a distinct operational question that would be difficult to answer from a single monolithic object. The Configuration answers "what should this workload look like right now?" The Revision answers "what did this workload look like at a specific point in time?" The Route answers "which version should receive what percentage of traffic?" And the Service is the glue that holds them together, presenting a single API surface to the developer while the control plane manages the derived state underneath.

The immutability of Revisions is the most important property in this model. Once a Revision is created, it cannot be changed — its container image, its environment variables, its resource specification are fixed forever. This means you can always route traffic back to any previous Revision with complete confidence that it will behave exactly as it did before. Rollback is not a redeploy; it is a traffic shift. If your v3 deployment introduces a bug that only manifests under load, you can shift 100% of traffic back to v2 in a single API call — no image rebuild, no pod restart, no waiting for a new deployment to roll out. The old Revision's pods were already running or can be reactivated from the immutable snapshot.

```
KNATIVE SERVING RESOURCE MODEL
================================================================

┌─────────────────────────────────────────────────────────────┐
│  SERVICE (ksvc)                                             │
│  Top-level resource. You create this.                       │
│  Manages everything below automatically.                    │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  CONFIGURATION                                        │  │
│  │  Desired state of your workload.                      │  │
│  │  Each change creates a new Revision.                  │  │
│  │                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ Revision v1 │  │ Revision v2 │  │ Revision v3 │  │  │
│  │  │ (image:1.0) │  │ (image:1.1) │  │ (image:1.2) │  │  │
│  │  │             │  │             │  │  (latest)   │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ROUTE                                                │  │
│  │  Maps traffic to Revisions.                           │  │
│  │  Enables traffic splitting.                           │  │
│  │                                                       │  │
│  │  100% ──▶ Revision v3 (latest)                       │  │
│  │   OR                                                  │  │
│  │   90% ──▶ Revision v2, 10% ──▶ Revision v3 (canary) │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

Key insight: You only create the SERVICE.
Knative creates Configuration, Revisions, and Route for you.
================================================================
```

- **Service (ksvc)**: The only resource you need to create. It manages the entire lifecycle.
- **Configuration**: Describes the desired state (container image, env vars, resource limits). Every update creates a new Revision.
- **Revision**: An immutable snapshot of your Configuration at a point in time. Think of it like a Git commit for your deployment.
- **Route**: Maps network traffic to one or more Revisions. This is how traffic splitting works.

### Your First Knative Service

The following Service definition deploys a simple HTTP application that responds with a greeting. The specification looks similar to a Kubernetes Deployment embedded inside a PodTemplateSpec, and that is intentional — Knative reuses the Kubernetes Pod specification so that anything you know about configuring containers, volumes, probes, and resource limits applies here without translation. The Knative-specific behavior is expressed through annotations in the template metadata, which is a deliberate design choice: annotations are optional, additive, and do not require changes to the core API schema when new autoscaling features are introduced.

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hello
  namespace: default
spec:
  template:
    metadata:
      annotations:
        # Scale to zero after 60 seconds of no traffic
        autoscaling.knative.dev/scale-to-zero-pod-retention-period: "60s"
    spec:
      containers:
      - image: gcr.io/knative-samples/helloworld-go
        ports:
        - containerPort: 8080
        env:
        - name: TARGET
          value: "World"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
```

```bash
# Apply the service
kubectl apply -f hello-service.yaml

# Check the Knative service
kubectl get ksvc hello

# Output:
# NAME    URL                                 LATESTCREATED   LATESTREADY     READY
# hello   http://hello.default.example.com    hello-00001     hello-00001     True

# Check the automatically created resources
kubectl get configuration hello
kubectl get revision -l serving.knative.dev/service=hello
kubectl get route hello
```

The output shows that Knative assigned a URL to the service automatically, created a Revision named `hello-00001`, and confirmed that the Revision is Ready — meaning the pod passed its readiness check and is serving traffic. The URL contains the service name and namespace as subdomains, which is the standard Knative naming convention and enables multi-tenancy by preventing name collisions across namespaces.

### Autoscaling: From 0 to N

Knative uses the Knative Pod Autoscaler (KPA) by default, which is more responsive than the standard Horizontal Pod Autoscaler (HPA) for serverless workloads. The HPA in core Kubernetes scales based on CPU or memory utilization averaged over a window — typically 60 to 90 seconds — which makes sense for long-running services with gradual traffic changes but is too slow for serverless workloads that need to react to traffic arriving after a period of zero activity. The KPA, by contrast, measures concurrency directly: how many requests are in flight at this exact moment. When a request arrives for a scaled-to-zero service, the KPA can decide to scale up within roughly 50 milliseconds, bypassing the metrics pipeline that feeds the HPA.

The KPA also supports a panic mode for sudden traffic spikes. Under normal operation, the autoscaler uses a 60-second stable window to smooth out transient fluctuations and avoid oscillation. But if the observed concurrency exceeds twice the target for a shorter panic window (typically 6 seconds), the KPA enters panic mode and scales more aggressively, then gradually scales back down once the spike subsides. This two-window design — stable for normal operation, panic for surges — is what allows Knative to handle both idle services waking up to a trickle of traffic and services suddenly hit by a flood.

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: autoscale-demo
spec:
  template:
    metadata:
      annotations:
        # Autoscaler class: kpa (default) or hpa
        autoscaling.knative.dev/class: "kpa.autoscaling.knative.dev"

        # Target concurrent requests per pod
        autoscaling.knative.dev/target: "10"

        # Minimum replicas (0 enables scale-to-zero)
        autoscaling.knative.dev/min-scale: "0"

        # Maximum replicas
        autoscaling.knative.dev/max-scale: "50"

        # Scale down delay (seconds of idle before scaling to zero)
        autoscaling.knative.dev/scale-to-zero-pod-retention-period: "30s"

        # Initial scale when waking from zero
        autoscaling.knative.dev/initial-scale: "1"
    spec:
      containers:
      - image: gcr.io/knative-samples/autoscale-go
        ports:
        - containerPort: 8080
```

The key metric is **concurrency** — how many simultaneous requests each pod should handle. If `target` is 10 and 50 requests arrive simultaneously, Knative scales to 5 pods. You can also configure the autoscaler to use Requests Per Second (RPS) as the scaling metric by setting `autoscaling.knative.dev/metric: "rps"` and `autoscaling.knative.dev/target: "100"` to target 100 requests per second per pod. The concurrency model is generally preferred for request-response workloads because it directly measures the resource that matters — inflight work — rather than an indirect proxy like CPU utilization.

---

## Scale to Zero: How It Actually Works

This is the defining feature of Knative, and understanding the mechanics helps you tune it properly. Scale-to-zero is not simply "delete the pods when idle." It is a coordinated dance between four components — the autoscaler, the activator, the ingress layer, and the Kubernetes scheduler — that must preserve a critical guarantee: no request is ever dropped, even if it arrives when zero pods exist to serve it.

The lifecycle moves through five distinct phases. During the active phase, pods are running and serving traffic directly through the ingress layer. When traffic stops, the autoscaler starts a countdown based on the `scale-to-zero-pod-retention-period` — a grace period that prevents premature scale-down during brief traffic lulls. If no requests arrive before the timer expires, Knative terminates all application pods and reconfigures the ingress to point at the activator instead. The activator is now the only component in the data path, and it is holding zero requests. Zero pods, zero resource consumption, but a live endpoint that can accept the next request whenever it arrives.

```
SCALE-TO-ZERO LIFECYCLE
================================================================

Phase 1: ACTIVE (pods running, serving traffic)
─────────────────────────────────────────────────
  Client ──▶ Ingress ──▶ Pod (serving requests)
                         Pod
                         Pod

Phase 2: GRACE PERIOD (no traffic, counting down)
─────────────────────────────────────────────────
  No requests for 30s...
  Knative Autoscaler: "Scale-to-zero timer started."
  Pods still running, ready to serve.

Phase 3: SCALED TO ZERO (no pods, activator watching)
─────────────────────────────────────────────────
  Knative terminates all pods.
  Ingress now points to the ACTIVATOR (a Knative system component).
  No application pods exist. Zero resource consumption.

Phase 4: COLD START (request arrives, waking up)
─────────────────────────────────────────────────
  Client ──▶ Ingress ──▶ Activator (holds the request)
                              │
                              ├── Signals autoscaler: "Wake up!"
                              ├── Autoscaler creates pod(s)
                              ├── Waits for pod to be Ready
                              └── Forwards buffered request to pod
                                        │
  Client ◀── Response ◀── Pod ◀─────────┘

Phase 5: ACTIVE AGAIN
─────────────────────────────────────────────────
  Ingress switches from Activator back to pod directly.
  Subsequent requests go straight to pods (no activator overhead).
================================================================
```

### The Activator

The activator is Knative's secret weapon. It is a reverse proxy that sits in the data path only when a service is scaled to zero, and only for the first request that wakes the service up. In the scaled-to-zero state, the ingress layer rewrites its routing table to send traffic to the activator instead of to application pods. When the first request arrives, the activator does not immediately forward it — there are no pods to forward to — so instead it buffers the request in memory while simultaneously signaling the autoscaler. The autoscaler creates at least one pod (governed by `initial-scale`), waits for the readiness probe to pass, and then notifies the activator. The activator forwards the buffered request to the now-ready pod and the response flows back to the client. Once the pod is running, the ingress layer switches its routing to point directly at the pod, and the activator steps out of the data path entirely.

This buffering guarantee is essential for correctness. Without it, the first request would receive a 503 or a connection refused — the Kubernetes Service would have no endpoints to route to. With the activator in place, the client experiences a delay (cold start latency) but never a dropped request or an error. The tradeoff is that the activator introduces a single point of buffering during cold start. If hundreds of requests arrive simultaneously while the service is scaled to zero, the activator buffers them all and feeds them to the new pods as they become ready. The activator has finite memory, so an extreme flood of requests during cold start could overwhelm it, but in practice this is manageable because the autoscaler creates multiple pods rapidly (governed by the panic window) and the buffering window is typically under 2 seconds.

### Cold Start Latency

Cold start is the time between "request arrives" and "pod is ready to serve." It is the price of scale-to-zero, and understanding its components lets you decide whether the cost is acceptable for a given workload. The latency has several contributors: the activator receives the request in roughly 5 milliseconds, the autoscaler decides to scale up in about 50 milliseconds, the API server creates the pod object in roughly 100 milliseconds, and the scheduler places the pod on a node in another 50 milliseconds. These control-plane operations are fast and predictable. The dominant variables are container startup time — which depends on image size, application initialization logic, and whether the image is cached on the node — and the readiness probe delay, which depends on how quickly your application signals that it is ready to accept traffic.

```
COLD START BREAKDOWN
================================================================

Component                         Typical Time
─────────────────────────────────────────────────
Activator receives request        ~5ms
Autoscaler decision               ~50ms
API server creates pod            ~100ms
Scheduler places pod              ~50ms
Container image pull              0ms (cached) to 30s+ (not cached)
Container startup                 ~200ms to 5s (app dependent)
Readiness probe passes            ~100ms to 10s (app dependent)
─────────────────────────────────────────────────
TOTAL (image cached, fast app)    ~500ms to 2s
TOTAL (image not cached, slow)    5s to 45s

HOW TO MINIMIZE COLD START:
1. Use small container images (distroless, alpine)
2. Pre-pull images on nodes (DaemonSet trick)
3. Keep application startup fast (lazy initialization)
4. Set min-scale: 1 for latency-sensitive services
5. Use initial-scale to start multiple pods on wake
================================================================
```

The most effective mitigations are straightforward engineering choices. Use small base images — distroless or Alpine — to keep image pull times under a second when the image is cached, and under 5 seconds when it is not. Consider running a DaemonSet that pre-pulls your most common images onto every node, eliminating the pull time entirely. Design your application startup to be fast: defer expensive initialization that is not needed for the first request, load large data structures lazily, and avoid framework startups that scan entire classpaths. For services where even a 2-second cold start is unacceptable — user-facing APIs, payment endpoints, anything on the critical path — set `min-scale: 1` to keep at least one pod warm at all times. You lose the cost savings of scale-to-zero for that service, but you gain predictable sub-millisecond response times. The decision is always a tradeoff between cost and latency, and the right answer depends on the service's role in your system.

---

## Knative Eventing

Knative Serving handles request-response workloads — a client sends an HTTP request and expects a response. Knative Eventing handles a different pattern: event-driven architectures where producers emit events and consumers react to them, often without a direct request-response relationship between the two. The value proposition is decoupling. In a traditional microservice architecture, if Service A needs to notify Service B of an order creation, A must know B's address, B's API contract, and B's availability. If B is down, A must retry or queue. If you add Service C that also needs to know about order creation, A must be updated to notify C as well. Each new consumer tightens the coupling.

Knative Eventing replaces this web of direct connections with an event mesh. Producers send events to a Broker — a central event bus that accepts CloudEvents — and consumers subscribe to the events they care about via Triggers that specify filter criteria. The producer does not know who consumes its events; the consumer does not know who produces them. Adding a new consumer means creating a new Trigger, not modifying any existing service. This inversion of responsibility — from "producer pushes to known consumers" to "consumers pull what they need from a shared bus" — is the same architectural pattern that made message brokers indispensable in enterprise integration, now running natively on Kubernetes with a CloudEvents-standardized event format.

### Core Concepts

The CloudEvents specification, itself a CNCF project, is what makes this decoupling work across heterogeneous systems. Every event in Knative Eventing is a CloudEvent: a JSON object with mandatory fields like `type`, `source`, `id`, and `specversion`, plus optional fields for `subject`, `time`, and `datacontenttype`. The `type` field is the primary routing key — it describes what happened in a reverse-DNS format like `com.example.order.created` or `dev.knative.sources.ping`. Because CloudEvents is a CNCF standard, events produced by Knative can be consumed by any CloudEvents-compatible system — AWS EventBridge, Azure Event Grid, or a custom Go service using the CloudEvents SDK — and events from those systems can flow into Knative's Broker the same way.

```
KNATIVE EVENTING ARCHITECTURE
================================================================

┌──────────────────────────────────────────────────────────┐
│                      SOURCES                              │
│  (Where events come from)                                 │
│                                                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Kafka   │  │ GitHub   │  │ Cron     │  │ API      │ │
│  │ Source  │  │ Source   │  │ Source   │  │ Source   │ │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
└───────┼────────────┼────────────┼────────────┼──────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌──────────────────────────────────────────────────────────┐
│                      BROKER                               │
│  (Central event bus, receives all events)                 │
│  Events are CloudEvents (standard format)                 │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Event: {type: "dev.knative.kafka.event",           │ │
│  │          source: "kafka-cluster",                    │ │
│  │          data: {...}}                                │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────┬────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Trigger    │ │  Trigger    │ │  Trigger    │
│  filter:    │ │  filter:    │ │  filter:    │
│  type=order │ │  type=payment│ │  type=*    │
│      │      │ │      │      │ │      │      │
│      ▼      │ │      ▼      │ │      ▼      │
│  Order Svc  │ │  Payment   │ │  Audit Log  │
│  (ksvc)     │ │  Svc (ksvc)│ │  (ksvc)     │
└─────────────┘ └─────────────┘ └─────────────┘
================================================================
```

- **Source**: Produces events. Connects external systems (Kafka, GitHub webhooks, cron schedules, APIs) to the Knative eventing mesh by translating their native protocols into CloudEvents.
- **Broker**: A central event bus. Receives events and distributes them to Triggers based on filter criteria. The Broker is the decoupling point — producers send here, consumers subscribe from here.
- **Trigger**: A filter that routes events from a Broker to a subscriber (typically a Knative Service). You define which event types each subscriber cares about using CloudEvents attribute filters.
- **CloudEvents**: A CNCF specification for describing events in a standard way. Every event in Knative Eventing is a CloudEvent with `type`, `source`, `id`, `data`, and other metadata.

Under the hood, the Broker uses a Channel — an event storage and delivery mechanism — that can be backed by different implementations depending on your durability and throughput requirements. The default in-memory Channel is suitable for development but loses events on restart. For production, you would configure a Kafka Channel or a NATS Channel that persists events to disk and provides at-least-once delivery guarantees across Broker restarts. This pluggable Channel layer is a deliberate design choice: the Broker and Trigger API remains the same regardless of the underlying transport, so you can start with the simple in-memory Channel and switch to Kafka later without changing any of your Source, Broker, or Trigger definitions.

### Eventing Example

The following YAML creates the complete event flow: a cron-style PingSource that fires every minute, a Broker that receives the events, a Trigger that filters for ping events and routes them to a subscriber, and a Knative Service that displays the events it receives. Notice that the PingSource declares its `sink` — the destination for produced events — as the Broker, not as the subscriber. The subscriber is only referenced in the Trigger. This indirection is what enables the decoupling: if you later add a second subscriber that also wants to receive ping events, you create another Trigger pointing to a different service, and you do not touch the PingSource at all.

```yaml
# 1. Create a Broker (event bus)
apiVersion: eventing.knative.dev/v1
kind: Broker
metadata:
  name: default
  namespace: default
---
# 2. Create an event Source (cron job that fires every minute)
apiVersion: sources.knative.dev/v1
kind: PingSource
metadata:
  name: heartbeat
  namespace: default
spec:
  schedule: "*/1 * * * *"
  contentType: "application/json"
  data: '{"message": "heartbeat"}'
  sink:
    ref:
      apiVersion: eventing.knative.dev/v1
      kind: Broker
      name: default
---
# 3. Create a Trigger (route heartbeat events to our service)
apiVersion: eventing.knative.dev/v1
kind: Trigger
metadata:
  name: heartbeat-trigger
  namespace: default
spec:
  broker: default
  filter:
    attributes:
      type: dev.knative.sources.ping
  subscriber:
    ref:
      apiVersion: serving.knative.dev/v1
      kind: Service
      name: event-display
---
# 4. Create the subscriber service
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: event-display
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: gcr.io/knative-releases/knative.dev/eventing/cmd/event_display
```

Events flow: PingSource fires every minute, sends a CloudEvent to the Broker, the Trigger matches the event type and forwards it to the `event-display` service. If the service is scaled to zero, it wakes up to process the event — combining Eventing's event-driven wake-up with Serving's scale-to-zero. This is the pattern that makes Knative more than the sum of its parts: events trigger scaling, scaling saves resources, and the entire cycle operates without any application-level polling or cron logic.

---

## Traffic Splitting

One of Knative's most powerful features is built-in traffic splitting across Revisions. No service mesh required. The ability to route a percentage of traffic to different versions of the same service is not unique to Knative — you can achieve it with Istio VirtualServices, with Linkerd traffic splits, or with an ingress controller that supports weighted backends — but Knative integrates it directly into the Service resource, using the same Revision objects that track your deployment history. This means traffic splitting is not a separate configuration you bolt on after deployment; it is a first-class field in the same API you use to deploy.

The implication for deployment safety is significant. With a traditional Kubernetes Deployment, a rolling update replaces pods gradually, but every pod runs the same version of your code — there is no mechanism to send 5% of traffic to a new version while the rest stays on the old one without external tooling. Knative's Revision model and traffic splitting change this: you can deploy a new Revision that receives 0% of production traffic, test it thoroughly through a tagged URL that hits it directly, then gradually increase its traffic share while monitoring error rates and latency. If the new Revision misbehaves, you set its traffic percentage back to zero — no rollback, no redeploy, no waiting for pods to terminate and restart. The old Revision is still there, still warm, still capable of handling 100% of traffic immediately.

### Blue-Green Deployment

A blue-green deployment with Knative means deploying the new version as a Revision, testing it in isolation via a tagged route, and then shifting all traffic to it in one operation once you are confident. The key advantage over traditional blue-green — where you maintain two separate Deployments and swap the Service selector — is that Knative Revisions share the same Service, same URL scheme, and same autoscaling configuration. You are not duplicating infrastructure; you are creating a new point in the deployment history.

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-app
spec:
  template:
    metadata:
      name: my-app-v2  # Name this revision explicitly
    spec:
      containers:
      - image: my-registry/my-app:2.0
  traffic:
  # All traffic goes to the new revision
  - revisionName: my-app-v2
    percent: 100
  # Tag the old revision so you can access it directly
  - revisionName: my-app-v1
    percent: 0
    tag: previous
```

With the `previous` tag, you can access the old version at `previous-my-app.default.example.com` for testing — even though it gets 0% of production traffic. If the new version has a problem, reversing the blue-green swap means changing `percent: 100` back to v1 and `percent: 0` to v2, which takes effect in seconds.

### Canary Deployment

Canary deployment extends the same mechanism to a gradual, percentage-based rollout. You deploy the new Revision, start it at a small traffic percentage while monitoring key metrics, and incrementally increase the percentage as confidence builds. Knative's Route controller implements this by programming the underlying networking layer — Kourier, Istio, or Contour — with the weighted traffic distribution, so the split happens at the ingress level before any request reaches an application pod. Each Revision scales independently based on the traffic it receives: if v2 is receiving 10% of 1,000 requests per second, it scales to handle approximately 100 requests per second, while v1 handles the remaining 900 with its own independently scaled set of pods.

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-app
spec:
  template:
    metadata:
      name: my-app-v3
    spec:
      containers:
      - image: my-registry/my-app:3.0
  traffic:
  # 90% to current stable version
  - revisionName: my-app-v2
    percent: 90
    tag: stable
  # 10% to new canary version
  - revisionName: my-app-v3
    percent: 10
    tag: canary
```

```bash
# Gradually shift traffic
# 10% -> 25% -> 50% -> 100%

# Check current traffic split
kubectl get ksvc my-app -o jsonpath='{.status.traffic[*]}'

# Each tagged revision gets its own URL:
# stable-my-app.default.example.com  (always hits v2)
# canary-my-app.default.example.com  (always hits v3)
# my-app.default.example.com         (split 90/10)
```

---

## Installation

Knative requires a networking layer. You have three main choices, and the decision has lasting operational implications because the networking layer sits in the critical path for every request your serverless workloads will ever receive.

### Option 1: Knative with Kourier (Lightweight)

Kourier is the simplest option — an Envoy-based ingress built specifically for Knative. It implements exactly the networking features that Knative Serving needs (HTTP routing, header-based routing, traffic splitting, activator integration) without any additional service mesh functionality. For most Knative installations, Kourier is the right default: it installs in roughly two minutes, consumes about 100 MB of memory, and adds no sidecar proxies to application pods. The tradeoff is that Kourier provides no mTLS, no distributed tracing, and no advanced traffic policies beyond what Knative itself exposes through the Route API. If you need those capabilities, you would already be running Istio for reasons unrelated to Knative.

```bash
# Install Knative Serving CRDs and core
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.22.1/serving-crds.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.22.1/serving-core.yaml

# Install Kourier networking layer
kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-v1.22.1/kourier.yaml

# Configure Knative to use Kourier
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

# Install Knative Eventing (optional)
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.22.1/eventing-crds.yaml
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.22.1/eventing-core.yaml

# Install the in-memory channel (for development)
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.22.1/in-memory-channel.yaml

# Install the MT-Channel-based broker
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.22.1/mt-channel-broker.yaml

# Verify
kubectl get pods -n knative-serving
kubectl get pods -n knative-eventing
```

### Option 2: Knative Operator (Production)

The Knative Operator manages the Serving and Eventing installations as Kubernetes custom resources, enabling declarative configuration, version upgrades through manifest changes rather than manual `kubectl apply` sequences, and reconciliation of configuration drift — if someone accidentally deletes a Knative system component, the operator recreates it. For production clusters where multiple teams rely on Knative, the operator provides an operational safety net that manual installation does not.

```bash
# Install the Knative Operator
kubectl apply -f https://github.com/knative/operator/releases/download/knative-v1.22.1/operator.yaml

# Create a KnativeServing instance
cat <<EOF | kubectl apply -f -
apiVersion: operator.knative.dev/v1beta1
kind: KnativeServing
metadata:
  name: knative-serving
  namespace: knative-serving
spec:
  ingress:
    kourier:
      enabled: true
  config:
    network:
      ingress-class: "kourier.ingress.networking.knative.dev"
EOF

# Create a KnativeEventing instance
cat <<EOF | kubectl apply -f -
apiVersion: operator.knative.dev/v1beta1
kind: KnativeEventing
metadata:
  name: knative-eventing
  namespace: knative-eventing
EOF
```

### Networking Layer Comparison

The choice of networking layer is primarily a question of what else is running in your cluster, not a question of Knative capability — all three options implement the full Knative networking API.

| Feature | Kourier | Istio | Contour |
|---------|---------|-------|---------|
| **Complexity** | Low | High | Medium |
| **Resource usage** | ~100MB | ~500MB+ | ~200MB |
| **mTLS** | No | Yes | No |
| **Service mesh features** | No | Yes | No |
| **Best for** | Dev, simple production | Already using Istio | Already using Contour |
| **Setup time** | 2 minutes | 15+ minutes | 5 minutes |

Use Kourier unless you already have Istio or Contour in your cluster. Adding a full service mesh solely to satisfy Knative's networking requirement adds significant operational complexity — sidecar injection, mTLS certificate rotation, and an additional control plane — for features your workloads may not need.

---

## Landscape Snapshot — as of 2026-06

This section captures the current state of serverless-on-Kubernetes tooling at the time of writing. This changes fast; verify against vendor docs before relying on specifics.

Knative is a **CNCF Graduated** project. It was accepted to CNCF at the Incubating maturity level on March 2, 2022, and promoted to Graduated on September 11, 2025, reflecting its production adoption, governance maturity, and contributor diversity. The project has been running at Google Cloud Run's scale for years — Cloud Run is a managed Knative service — and powers serverless platforms at IBM Code Engine and VMware Tanzu.

The Knative project maintains several components. Knative Serving (v1.22.1 as of this writing) manages request-driven workloads with scale-to-zero and traffic splitting. Knative Eventing (v1.22.1) provides the event mesh with Brokers, Triggers, Sources, and Channels. The client (`kn` CLI) and the Operator are maintained in separate repositories but release in lockstep with Serving and Eventing. The networking layer projects (net-kourier, net-istio, net-contour) also track the same version.

The broader serverless-on-Kubernetes landscape includes KEDA (CNCF Graduated), which provides event-driven autoscaling for standard Kubernetes workloads including scale-to-zero, but does not provide the Revision model, traffic splitting, or event mesh that Knative offers. OpenFaaS and Fission are alternative serverless frameworks that predate Knative and offer simpler operational models with fewer moving parts, at the cost of a smaller ecosystem and less integration with the CloudEvents standard. Cloud provider FaaS offerings (AWS Lambda, Azure Functions) provide the lowest operational overhead and fastest cold starts but introduce vendor lock-in and are not portable across clouds or on-premises.

---

## Rosetta: Durable Capabilities Across Tools

The durable capabilities of serverless workloads — scale-to-zero, request-driven autoscaling, revision management, traffic splitting, event mesh, and CloudEvents conformance — exist across multiple tools in this space. This table maps the capability to the tool, not to declare a winner, but to help you choose based on which capabilities your workload actually needs.

| Capability | Knative | plain HPA+Deployment | KEDA | OpenFaaS / Fission | Cloud FaaS (Lambda, etc.) |
|---|---|---|---|---|---|
| Scale-to-zero | Yes | No | Yes | Yes | Yes |
| Request-driven autoscale | Yes (KPA, concurrency/RPS) | HPA (CPU/memory) | Event-driven (many scalers) | Yes | Yes |
| Immutable revisions + traffic split | Yes | No | No | No | Version aliases (provider-specific) |
| Event mesh (pub/sub) | Yes (Broker/Trigger) | No | Scaling only (no mesh) | No | Provider-specific (EventBridge, etc.) |
| CloudEvents-native | Yes | No | No | No | Partial (EventBridge) |
| Portable across K8s clusters | Yes | Yes | Yes | Yes | No (locked to cloud) |
| Operational complexity | Medium-high | Low | Low-medium | Medium | Low (managed) |
| Cold start latency | 0.5–5s | N/A (always warm) | 0.5–5s | 0.5–3s | 0.1–10s (varies by runtime) |

---

## Decision Framework

Choosing between these tools is not a matter of which one is "better" but of which capabilities your workload needs and which operational costs your team is willing to bear. Use this framework to evaluate your services against the durable axes.

Start by profiling your service's traffic pattern. If the service receives steady, predictable traffic 24/7 — a payment API, a user-facing frontend, a service that serves hundreds of requests per second continuously — serverless adds complexity without providing its primary benefit (cost savings from idle scale-down). In this case, a traditional Deployment with HPA or KEDA is the simpler, more appropriate choice. The HPA gives you CPU-based or memory-based scaling; KEDA adds event-driven scaling if your traffic is driven by queue depth or external metrics. Both are simpler to operate than Knative because they do not introduce the activator, the Revision lifecycle, or the networking layer requirement.

If the service is bursty — receiving traffic in spikes with long idle periods — serverless is the right model, and the next question is whether you need the full Knative feature set or whether scaling alone is sufficient. KEDA with a scaled object that targets zero replicas when idle gives you scale-to-zero on standard Deployments without adopting Knative's serving model. This is a good fit when you already have Deployments and just want to add intelligent scale-down — an internal reporting API that wakes up when a user requests a report and sleeps afterward, for example. You do not need the Revision model or traffic splitting for this use case, so KEDA keeps the operational surface smaller.

Choose Knative when you need more than scaling. If your deployment safety practice requires canary rollouts with fine-grained traffic percentage control, Knative's built-in traffic splitting eliminates the need for a service mesh. If you need an event mesh where multiple services subscribe to events from multiple sources through a decoupled Broker, Knative Eventing provides this natively with CloudEvents conformance. If you want immutable deployment records that enable instant rollback without redeployment, the Revision model gives you that audit trail. If you operate a multi-tenant platform where each tenant's service should scale to zero when inactive, Knative's per-Service autoscaling and URL naming convention handle multi-tenancy cleanly. These capabilities are the reasons to adopt Knative beyond what KEDA plus a Deployment can provide.

Choose a cloud FaaS platform when portability is not a requirement and operational simplicity is the highest priority — a small team building prototypes or event handlers that will never leave AWS Lambda, for instance. The tradeoff is vendor lock-in and execution constraints (15-minute timeout, limited runtime support), but the operational burden approaches zero.

---

## Operational Concerns

Running Knative in production introduces concerns beyond the application-level scaling behavior. Understanding these concerns upfront prevents the class of incidents where Knative itself becomes the thing that needs debugging at 2 AM.

The networking layer is the most critical operational dependency. Knative cannot route traffic without a functioning ingress, which means a misconfigured Kourier or Istio deployment breaks every Knative Service in the cluster. Monitor the networking layer's pods, its configuration, and its metrics with the same rigor you apply to your own applications. A common failure mode is the `config-network` ConfigMap in the `knative-serving` namespace drifting from the expected values — if someone changes `ingress-class` to an invalid value, all routing stops. Treat this ConfigMap as production infrastructure and manage it through GitOps, not manual `kubectl patch` operations.

Cold-start latency mitigation is a tuning exercise, not a one-time configuration. Set `min-scale` thoughtfully: a value of 1 eliminates cold starts for that service but also eliminates the primary cost benefit of scale-to-zero. Use it only for services on the user-facing critical path. Set `scale-to-zero-pod-retention-period` long enough to avoid oscillation — a service that scales to zero, receives a request 30 seconds later, scales up, goes idle, and scales to zero again is consuming more resources in repeated cold starts than it would by staying warm. Set the retention period to at least 2-3 minutes for services with intermittent traffic. Use `initial-scale` to warm up multiple pods on wake for services that receive bursts of traffic after idle periods — starting 3 pods instead of 1 when the first request arrives distributes the burst across multiple instances immediately.

The Knative control plane itself has a resource footprint. The core Serving components (activator, autoscaler, controller, webhook) consume roughly 500 MB of memory and 1 vCPU in aggregate under light load, plus the networking layer's resources. The Eventing components add another 300-500 MB. For a production cluster, budget at least 2 vCPU and 2 GB of memory for the Knative system components before accounting for your application workloads. This overhead is the price of the serverless abstraction, and it is reasonable for clusters running dozens of serverless workloads, but it may be disproportionate for a cluster running only one or two services — in that case, KEDA plus a Deployment is the leaner choice.

---

## Patterns and Anti-Patterns

### Patterns

**Pattern 1: Profile Before You Migrate.** Before moving any service to Knative, collect at least two weeks of traffic data — requests per second, idle periods, resource consumption — and compute the service's duty cycle. Services that are idle more than 50% of the time benefit from scale-to-zero. Services that are active more than 90% of the time save little and incur the cold-start penalty. Make the migration decision based on data, not enthusiasm for the technology. A simple Prometheus query over the Deployment's request rate is sufficient: if the 95th percentile of request rate is zero, the service is a strong candidate for Knative.

**Pattern 2: Tag Revisions for Safe Experimentation.** Always tag the Revision that is receiving 0% of traffic with a descriptive name so engineers can test it in isolation before shifting production traffic. A tagged Revision at 0% traffic gets its own URL, its own set of pods (if `min-scale` is set to 1), and its own monitoring — it is a full staging environment that happens to share a Service with production. Use this for pre-flight checks: deploy the canary at 0%, run integration tests against the tagged URL, verify metrics, and only then increase the traffic percentage.

**Pattern 3: Use the Broker as Your Integration Boundary.** When building event-driven systems, route all external events through a Broker even if there is initially only one consumer. The Broker is the decoupling point that makes future consumers free to add. If you wire a KafkaSource directly to a subscriber, adding a second subscriber requires modifying the Source. If you wire the KafkaSource to a Broker and use Triggers for subscriptions, adding a second subscriber requires only a new Trigger. The Broker also gives you a single place to configure Channel durability — switching from in-memory to Kafka for persistence is a Broker configuration change, not a change to every Source and Trigger.

### Anti-Patterns

**Anti-Pattern 1: Knative for Everything.** Adopting Knative as the default deployment mechanism for all services, including always-on, high-traffic workloads that never scale to zero, adds the Knative control plane overhead, the activator cold-start path, and the Revision lifecycle management complexity to services that derive no benefit from them. Always-on services under Knative still experience the Revision creation and Route reconciliation on every update, adding operational noise without delivering scale-to-zero savings. Keep always-on services on standard Deployments with HPA.

**Anti-Pattern 2: Zero-Minimum Autoscaling for Latency-Sensitive Services.** Setting `min-scale: 0` on a service that is on the critical path for user requests guarantees that some percentage of users will experience a cold start. Even a 1-second delay is noticeable in a web UI; a 3-second delay causes users to reload the page or abandon the interaction. Profile your user-facing services carefully: if p95 latency matters, keep at least one pod warm.

**Anti-Pattern 3: Giant Container Images with Slow Startup.** Deploying a 500 MB container image that takes 30 seconds to start on Knative with scale-to-zero means every cold start inflicts a 30-second delay on the first user. If the service scales to zero frequently — a reporting API that gets hit twice a day, for example — the cold start cost dominates the user experience. Invest in small images (distroless, Alpine, or a carefully pruned multi-stage build) and fast application startup, or accept that this service needs `min-scale: 1` and will not benefit from scale-to-zero economics.

**Anti-Pattern 4: Installing Istio Just for Knative.** Adding a full service mesh with sidecar injection, mTLS, and an Istiod control plane solely because Knative needs a networking layer creates significant operational complexity — sidecar resource overhead, certificate rotation, upgrade coordination — without any corresponding benefit from service mesh features. Use Kourier, which is purpose-built for Knative and far simpler to operate. Reserve Istio for clusters where you need mesh features (mTLS between services, fine-grained traffic policies, distributed tracing) independent of Knative.

---

## Did You Know?

1. **Knative was originally created by Google, Pivotal, IBM, Red Hat, and SAP in 2018, and is now a CNCF Graduated project.** Google Cloud Run is literally Knative running as a managed service — when you deploy to Cloud Run, you are deploying a Knative Service. Cloud Run's scale and reliability are a direct testament to Knative's production readiness, processing billions of requests daily. Knative was accepted to CNCF at Incubating maturity in March 2022 and promoted to Graduated in September 2025, joining projects like Kubernetes, Prometheus, and Envoy at the highest maturity level.

2. **Knative can scale a service from 0 to 1,000 pods in under 30 seconds.** The activator proxy buffers incoming requests during cold start so that no requests are dropped — they just wait. The two-window autoscaler design (stable window for normal scaling, panic window for rapid surges) enables this: when a flood of requests arrives after a scale-to-zero period, the panic window detects the spike within 6 seconds and scales aggressively, while the activator holds the early requests.

3. **The Knative project removed its Build component in 2019 and handed that responsibility to Tekton.** This is a rare example of a project intentionally shrinking its scope to do fewer things better. Instead of maintaining a built-in container build system, Knative delegated to Tekton, which has since become the standard for Kubernetes-native CI/CD pipelines. The lesson for platform teams: do not build what your ecosystem already provides better.

4. **The CloudEvents specification that Knative Eventing uses is itself a CNCF project.** By standardizing the event envelope — `type`, `source`, `id`, `specversion`, and `data` — CloudEvents enables Knative events to flow into AWS EventBridge, Azure Event Grid, Google Eventarc, or any custom CloudEvents-compatible consumer without translation layers. This standardization is what makes the event mesh pattern work across organizational and cloud boundaries, not just within a single cluster.

---

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Using Knative for all services | Always-on services gain nothing; Knative adds overhead and complexity | Profile traffic patterns first; only migrate services that are idle 50%+ of the time |
| Ignoring cold start latency | Users see 2-5 second delays on first request after idle period | Set `min-scale: 1` for user-facing services, or use scale-to-zero only for internal/async workloads |
| Large container images | 500MB+ images cause 10-30 second cold starts when not cached on the node | Use distroless or alpine base images; keep images under 100MB; pre-pull with a DaemonSet |
| Not setting resource requests | Knative autoscaler cannot make good decisions without knowing pod resource consumption | Always set CPU and memory requests; the autoscaler uses these for scheduling decisions |
| Installing Istio just for Knative | Adds 500MB+ of memory overhead and significant operational complexity | Use Kourier unless you already have Istio for other reasons |
| Forgetting to configure DNS | Knative generates URLs like `hello.default.example.com` that do not resolve | Configure a real domain with a wildcard DNS record, or use Magic DNS for development |
| Not testing cold start path | The warm path works fine, but the cold start path has different failure modes | Test by scaling to zero manually and then sending a request |
| Setting scale-to-zero window too short | Service oscillates between 0 and 1 pods, wasting resources on repeated cold starts | Set `scale-to-zero-pod-retention-period` to at least 60s; longer for bursty traffic patterns |

---

## Quiz

### Question 1
What are the four Knative Serving resources, and which one do you actually create?

<details>
<summary>Show Answer</summary>

The four resources are **Service** (ksvc), **Configuration**, **Revision**, and **Route**. You only create the **Service**. Knative automatically creates and manages the Configuration, Revisions, and Route. The Configuration describes the desired state, each change produces an immutable Revision (like a Git commit), and the Route determines how traffic is split across Revisions. This four-way split exists because each resource answers a distinct operational question — desired state, point-in-time snapshot, and traffic routing — that would be difficult to answer from a single monolithic object.

</details>

### Question 2
Explain how the activator enables scale-to-zero without dropping requests, walking through each step from when the first request arrives to when the pod is serving traffic.

<details>
<summary>Show Answer</summary>

When a Knative service scales to zero, the ingress layer routes traffic to the **activator** instead of directly to application pods (which no longer exist). When a request arrives: (1) the activator buffers the request (the client waits), (2) it signals the autoscaler to create pods, (3) the autoscaler schedules pod(s) and waits for the readiness probe to pass, (4) the activator forwards the buffered request to the now-ready pod, and (5) the ingress switches to routing directly to pods, removing the activator from the data path. The client experiences a delay (cold start latency) but never a dropped request or an error. The activator is only in the data path when the service is scaled to zero; once pods are running, traffic goes directly to them.

</details>

### Question 3
What is a Knative Revision and why is its immutability critical for deployment safety?

<details>
<summary>Show Answer</summary>

A Revision is an immutable snapshot of a Knative Configuration at a point in time. Every time you update a Knative Service (change the image, environment variables, resource limits, etc.), a new Revision is created. Immutability enables three critical capabilities. First, traffic splitting — you can route percentages of traffic to different Revisions for canary deployments because each Revision is a stable, unchanging target. Second, instant rollback — you can shift 100% of traffic back to a previous Revision in a single API call without redeploying, because the old Revision's specification is preserved exactly. Third, auditability — you can see precisely what was running at any point in time. Revisions function like Git commits: each one is a permanent, immutable record of a specific configuration state.

</details>

### Question 4
You have a Knative Service with `autoscaling.knative.dev/target: "10"` and 75 concurrent requests arrive. How many pods will Knative create?

<details>
<summary>Show Answer</summary>

Knative will target **8 pods** (75 / 10 = 7.5, rounded up to 8). The KPA (Knative Pod Autoscaler) uses the concurrency target to determine the desired replica count. With a target of 10 concurrent requests per pod and 75 total concurrent requests, it needs at least 8 pods to keep each pod at or below the target concurrency. In practice, the autoscaler also considers a panic window for rapid scaling and a stable window for gradual adjustment, so the actual pod count may briefly be higher or lower depending on how quickly the traffic ramp occurred. If 75 requests arrived suddenly after a period of zero traffic, the panic window would detect the surge and may scale to more than 8 pods initially, then stabilize at 8.

</details>

### Question 5
What is the difference between Knative Eventing's Broker and a Trigger?

<details>
<summary>Show Answer</summary>

A **Broker** is a central event bus that receives CloudEvents from Sources and makes them available for filtered delivery. A **Trigger** is a subscription with a filter that watches a Broker and routes matching events to a specific subscriber (typically a Knative Service). The Broker is the decoupling point — producers send events here without knowing who will consume them — and Triggers are the subscription mechanism — consumers declare what they want without knowing who produces it. You define filter criteria on the Trigger using CloudEvents attribute matching (for example, `type: order.created`), and the Broker delivers only matching events to that Trigger's subscriber. Adding a new consumer means creating a new Trigger; no existing Source or service needs modification.

</details>

### Question 6
Why is Kourier recommended over Istio for most Knative installations?

<details>
<summary>Show Answer</summary>

Kourier is recommended for most installations for several reasons. First, resource usage: Kourier uses roughly 100 MB of memory as a standalone ingress, while Istio adds roughly 500 MB for its control plane plus sidecar proxies consuming memory in every application pod. Second, complexity: Kourier is a single component purpose-built for Knative's networking needs, while Istio is a full service mesh with many components (istiod, gateways, sidecars, CRDs) that require ongoing configuration and upgrade coordination. Third, scope: unless you need mTLS between services, distributed tracing, or advanced traffic policies for your entire cluster, Istio's features are unused overhead. The only situation where Istio makes sense is when you already have it installed and configured for other reasons (mTLS, mesh-level observability) and want Knative to leverage the existing infrastructure rather than introduce a second networking layer.

</details>

### Question 7
A team deploys all 50 of their microservices on Knative with scale-to-zero. Users complain about intermittent slowness. What went wrong?

<details>
<summary>Show Answer</summary>

The team used Knative for services that should not scale to zero. The intermittent slowness is caused by cold starts — when a user hits a service that has scaled to zero, they wait 1-5 seconds (or more) while the pod starts up. The fix is to profile traffic patterns and categorize services. High-traffic, user-facing services should set `min-scale: 1` (or remain on regular Deployments with HPA) to avoid cold starts entirely. Internal and asynchronous services with bursty traffic are appropriate for scale-to-zero. Latency-sensitive services should never scale to zero. Not every service benefits from scale-to-zero; the savings only matter for services that are idle a significant portion of the time, and the cold start penalty must be acceptable for the service's role in the system. Running always-on services under Knative also adds Revision lifecycle management overhead with no corresponding benefit.

</details>

### Question 8
How would you implement a canary deployment with Knative that sends 5% of traffic to a new version and enables direct testing of the canary?

<details>
<summary>Show Answer</summary>

Update the Knative Service with a traffic split in the `traffic` section, giving the new Revision 5% of traffic and the stable Revision 95%, while tagging both for direct access:

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-app
spec:
  template:
    metadata:
      name: my-app-v2
    spec:
      containers:
      - image: my-registry/my-app:2.0
  traffic:
  - revisionName: my-app-v1
    percent: 95
    tag: stable
  - revisionName: my-app-v2
    percent: 5
    tag: canary
```

Each tagged revision gets its own URL (`canary-my-app.default.example.com` for direct testing of the new version, `stable-my-app.default.example.com` for the current version). To promote the canary, gradually increase the percentage (5 to 25 to 50 to 100) while monitoring error rates, latency, and other service-level indicators. To roll back, set the canary to 0% and stable to 100% — no redeployment needed, no service mesh required. The rollback takes effect in seconds because the Route controller simply updates the ingress routing table.

</details>

---

## Hands-On Exercise

### Objective

Deploy a Knative service, watch it scale to zero, send a request to trigger cold start, observe it scale back up, and then perform a traffic split between two revisions.

### Environment Setup

```bash
# Create a kind cluster with port mapping for Kourier
cat <<EOF | kind create cluster --name knative-lab --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 31080
    hostPort: 8080
    protocol: TCP
EOF

# Install Knative Serving
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.22.1/serving-crds.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.22.1/serving-core.yaml

# Install Kourier
kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-v1.22.1/kourier.yaml

# Configure Knative to use Kourier
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

# Configure Magic DNS for local development
kubectl patch configmap/config-domain \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"127.0.0.1.sslip.io":""}}'

# Patch Kourier to use NodePort for kind
kubectl patch service kourier -n kourier-system \
  --type merge \
  --patch '{"spec":{"type":"NodePort","ports":[{"port":80,"targetPort":8080,"nodePort":31080}]}}'

# Wait for Knative to be ready
kubectl wait --for=condition=Ready pods --all -n knative-serving --timeout=120s
kubectl wait --for=condition=Ready pods --all -n kourier-system --timeout=120s

# Verify installation
kubectl get pods -n knative-serving
kubectl get pods -n kourier-system
```

### Tasks

**Step 1: Deploy a Knative Service.** Create a basic Knative Service that responds with a greeting. Save the following YAML as `hello-knative.yaml`:

```yaml
# Save as hello-knative.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hello
  namespace: default
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/scale-to-zero-pod-retention-period: "30s"
    spec:
      containers:
      - image: gcr.io/knative-samples/helloworld-go
        ports:
        - containerPort: 8080
        env:
        - name: TARGET
          value: "KubeDojo Student"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
```

```bash
kubectl apply -f hello-knative.yaml

# Check the service
kubectl get ksvc hello

# Watch all created resources
kubectl get configuration hello
kubectl get revision -l serving.knative.dev/service=hello
kubectl get route hello
```

**Step 2: Send a request and observe pods.** Send a request to the Knative Service and watch how Knative creates pods in response. Open a second terminal to watch pods being created and destroyed as traffic arrives and subsides:

```bash
# Terminal 2: watch pods
kubectl get pods -l serving.knative.dev/service=hello -w
```

In the first terminal, send a request to the service and verify the response:

```bash
# Send a request
curl -H "Host: hello.default.127.0.0.1.sslip.io" http://localhost:8080

# Expected output: "Hello KubeDojo Student!"
```

**Step 3: Watch scale-to-zero.** After you stop sending requests, observe how Knative scales the service back to zero after the configured idle period of 30 seconds:

```bash
# Wait 30+ seconds with no traffic
# In Terminal 2, you should see the pod terminate

# Verify: no pods running
kubectl get pods -l serving.knative.dev/service=hello
# Expected: No resources found
```

**Step 4: Trigger cold start.** Send a request after the service has scaled to zero and measure the cold start latency. The `time` command will show you exactly how long the full cold-start path takes:

```bash
# Time the cold start
time curl -H "Host: hello.default.127.0.0.1.sslip.io" http://localhost:8080

# Note the total time -- this includes cold start latency
# Expected: 1-5 seconds depending on your system

# Check pods again -- one should be running now
kubectl get pods -l serving.knative.dev/service=hello
```

**Step 5: Deploy a second revision and split traffic.** Update the Knative Service with a new container environment variable and configure traffic splitting so that 80% of requests go to the original revision and 20% to the new one. Save this as `hello-v2.yaml`:

```yaml
# Save as hello-v2.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hello
  namespace: default
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/scale-to-zero-pod-retention-period: "30s"
    spec:
      containers:
      - image: gcr.io/knative-samples/helloworld-go
        ports:
        - containerPort: 8080
        env:
        - name: TARGET
          value: "KubeDojo Graduate"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
  traffic:
  - latestRevision: false
    revisionName: hello-00001
    percent: 80
    tag: stable
  - latestRevision: true
    percent: 20
    tag: canary
```

```bash
kubectl apply -f hello-v2.yaml

# Verify two revisions exist
kubectl get revision -l serving.knative.dev/service=hello

# Send multiple requests and observe the split
for i in $(seq 1 20); do
  curl -s -H "Host: hello.default.127.0.0.1.sslip.io" http://localhost:8080
done

# You should see ~80% "Hello KubeDojo Student!" and ~20% "Hello KubeDojo Graduate!"

# Test tagged routes directly
curl -H "Host: stable-hello.default.127.0.0.1.sslip.io" http://localhost:8080
# Always returns: "Hello KubeDojo Student!"

curl -H "Host: canary-hello.default.127.0.0.1.sslip.io" http://localhost:8080
# Always returns: "Hello KubeDojo Graduate!"
```

**Step 6: Promote the canary.** After verifying that the new revision behaves correctly under the 20% traffic split, promote it to receive 100% of production traffic with a single command:

```bash
# Shift all traffic to the new revision
kubectl patch ksvc hello --type merge --patch '{
  "spec": {
    "traffic": [
      {"revisionName": "hello-00001", "percent": 0, "tag": "previous"},
      {"latestRevision": true, "percent": 100}
    ]
  }
}'

# Verify
curl -H "Host: hello.default.127.0.0.1.sslip.io" http://localhost:8080
# Should always return: "Hello KubeDojo Graduate!"
```

### Success Criteria

- [ ] Knative Serving is installed and all pods are running in knative-serving namespace
- [ ] A Knative Service is deployed and accessible via curl
- [ ] You observed the service scale to zero (0 pods) after the idle period
- [ ] You triggered a cold start and measured the latency
- [ ] You deployed a second revision and verified traffic splitting (80/20)
- [ ] You accessed individual revisions via tagged routes
- [ ] You promoted the canary to 100% traffic

### Bonus Challenge

Install Knative Eventing and create a PingSource that fires every 30 seconds, a Broker, a Trigger, and an event-display service. Verify that the event-display service scales to zero between events and wakes up each time a CloudEvent arrives.

---

## Sources

- [Knative Documentation](https://knative.dev/docs/)
- [Knative Serving Documentation](https://knative.dev/docs/serving/)
- [Knative Serving — Services](https://knative.dev/docs/serving/services/)
- [Knative Serving Autoscaling](https://knative.dev/docs/serving/autoscaling/)
- [Knative Serving Traffic Management](https://knative.dev/docs/serving/traffic-management/)
- [Knative Eventing Documentation](https://knative.dev/docs/eventing/)
- [Knative Eventing — Brokers and Triggers](https://knative.dev/docs/eventing/brokers/)
- [Knative Eventing — PingSource](https://knative.dev/docs/eventing/sources/pingsource/)
- [Knative Serving GitHub Repository](https://github.com/knative/serving)
- [Knative Eventing GitHub Repository](https://github.com/knative/eventing)
- [CNCF Knative Project Page](https://www.cncf.io/projects/knative/)
- [CloudEvents Specification](https://cloudevents.io/)
- [Knative Eventing Triggers](https://knative.dev/docs/eventing/triggers/) — Reference for filtered event subscription via Brokers and Triggers.
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [KEDA Documentation](https://keda.sh/)
- [OpenFaaS Documentation](https://docs.openfaas.com/)

---

## Next Module

Return to [Module 6.2: KEDA](/platform/toolkits/developer-experience/scaling-reliability/module-6.2-keda/) to compare event-driven autoscaling approaches, or explore [Module 6.4: FinOps with OpenCost](/platform/toolkits/developer-experience/scaling-reliability/module-6.4-finops-opencost/) to measure the cost savings from scale-to-zero.

---

*"The cheapest pod is the one that is not running."*
