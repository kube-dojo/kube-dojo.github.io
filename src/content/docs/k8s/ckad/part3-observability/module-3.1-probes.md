---
citations_verified: true
title: "Module 3.1: Application Probes"
slug: k8s/ckad/part3-observability/module-3.1-probes
sidebar:
  order: 1
lab:
  id: ckad-3.1-probes
  url: https://killercoda.com/kubedojo/scenario/ckad-3.1-probes
  duration: "30 min"
  difficulty: intermediate
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Critical exam topic with production consequences and multiple configuration trade-offs
>
> **Time to Complete**: 50-60 minutes
>
> **Prerequisites**: Module 1.1 (Pods), basic Service routing, and comfort reading Pod events with `kubectl describe`

---

## Learning Outcomes

After completing this module, you will be able to demonstrate probe design and evaluation with enough confidence to pass CKAD exam questions and defend production incident triage decisions using kubelet behavior signals:

- **Design** liveness, readiness, and startup probe configurations that match an application's startup behavior, dependency model, and failure modes.
- **Compare** HTTP, TCP, exec, and gRPC probe mechanisms, then select the least risky check for a given workload.
- **Debug** restart loops, missing Service endpoints, and slow rollouts by reading probe events, Pod status, and endpoint membership.
- **Evaluate** probe timing parameters so recovery is fast without causing false positives during normal startup, load, or garbage collection pauses.
- **Implement** runnable Kubernetes manifests that combine startup, liveness, and readiness probes for exam-style and production-style scenarios.

---

## Why This Module Matters

A team ships a new checkout service on Friday afternoon. The container starts, the Pod enters `Running`, and the rollout looks healthy, so the deployment continues across the cluster. A few minutes later, customer traffic starts failing because the process is alive but the application has not finished loading its pricing cache. Kubernetes did exactly what it was told: it ran containers and routed traffic to ready Pods. The problem was that nobody taught Kubernetes what "ready" meant for this application.

Probes are the contract between your application and the kubelet. They tell Kubernetes whether a container should be restarted, whether a Pod should receive traffic, and whether a slow-starting application deserves more time before normal health checks begin. Without probes, Kubernetes can only observe process-level facts such as "the container exists" and "the main process has not exited." Those facts are useful, but they are not the same as "the service can answer real requests."

[The CKAD exam tests probes](https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/) because they sit at the boundary between YAML fluency and operational judgment. You need to write valid manifests quickly, but you also need to know which probe failure restarts a container and which probe failure removes a Pod from Service endpoints. In real clusters, that distinction decides whether an outage heals itself, hides a broken Pod from users, or becomes worse because Kubernetes restarts healthy but slow containers.

> **The Hospital Monitoring Analogy**
>
> A liveness probe is like asking, "Does this patient need emergency intervention because the vital process has stopped?" A readiness probe is like asking, "Can this patient safely receive visitors right now?" A startup probe is like telling the monitoring system, "Do not apply normal alarm rules while the patient is still waking from surgery." Each question has a different consequence, and using one question for every situation causes noisy alarms or missed failures.

---

## The Mental Model: Three Questions, Three Actions

A probe is not just a health check endpoint. It is a health check endpoint plus a Kubernetes action. The fastest way to avoid probe mistakes is to ask what Kubernetes will do after a failure, because the same `/healthz` URL can be harmless in one probe and destructive in another.

```ascii
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Kubernetes Probe Decision Map                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  startupProbe                                                                │
│  Question: Has the application completed its startup sequence?                │
│  Failure:  Keep waiting until failureThreshold is exceeded.                   │
│  Success:  Enable livenessProbe and readinessProbe evaluation.                │
│                                                                              │
│  livenessProbe                                                               │
│  Question: Is the application alive enough that continuing is useful?         │
│  Failure:  Kill the container and let the restart policy recreate it.         │
│  Success:  Leave the running container alone.                                 │
│                                                                              │
│  readinessProbe                                                              │
│  Question: Should this Pod receive Service traffic right now?                 │
│  Failure:  Remove the Pod IP from matching Service endpoints.                 │
│  Success:  Add or keep the Pod IP in matching Service endpoints.              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

The most important operational distinction is that [liveness changes container lifetime, while readiness changes traffic routing](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/). A failing liveness probe increases restart counts and [can create `CrashLoopBackOff` behavior](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) if the application never satisfies the check. A failing readiness probe does not restart the container; it changes whether Services send traffic to that Pod. Startup probes gate the other two so that slow applications are not punished before they have had a fair chance to initialize.

> **Active Learning Prompt: Predict the Action**
>
> A Pod is `Running` with zero restarts, but the Service has no endpoints for it. Which probe family should you investigate first, and why would checking the restart count alone mislead you?

If your answer was "readiness," your mental model is on track. Readiness is the probe that controls endpoint membership, so the container can look stable while traffic is still blocked. Restart count is a liveness clue, not a readiness guarantee.

---

## Probe Types in Context

### Liveness Probe: Recover When Continuing Is Worse Than Restarting

A liveness probe should detect situations where the process is still present but the application is no longer making useful progress. Examples include a deadlocked worker pool, a server stuck in an unrecoverable internal state, or a process that accepts connections but can no longer serve core requests. The consequence is severe: Kubernetes kills the container. That makes liveness valuable for self-healing, but dangerous when the check is too broad or too sensitive.

A good liveness check is usually narrow. It should verify that the application runtime can make basic forward progress, not that every external dependency is perfect. If a downstream database is temporarily unavailable, restarting every application Pod may amplify the incident. In that case, readiness should usually fail so traffic drains, while liveness should continue to pass unless the process itself is stuck.

Before choosing a liveness endpoint, name the failure that a fresh container would actually clear. A local deadlock might qualify because restarting rebuilds the process state. A shared database outage does not qualify because the replacement container will encounter the same unavailable database. This question helps separate recovery from repeated disruption. It also suggests what to verify later: an intentional liveness failure should produce a restart, followed by a container that can answer the same check. If the replacement immediately fails again, inspect the underlying condition instead of simply shortening the probe period.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: liveness-web
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 10
      periodSeconds: 10
      timeoutSeconds: 2
      failureThreshold: 3
```

This Pod uses a simple HTTP liveness probe because `nginx` can answer `/` quickly after startup. The kubelet waits ten seconds before the first check, probes every ten seconds, and restarts the container after three consecutive failures. For a real application, the path might be `/healthz`, but the same principle applies: the endpoint should mean "restart me if this keeps failing."

### Readiness Probe: Control Traffic Without Killing the Container

A readiness probe answers a different question: can this Pod safely receive requests right now? It may fail during startup, cache warmup, overloaded periods, maintenance windows, or temporary loss of a required dependency. When readiness fails, the Pod stays alive, but Services stop routing traffic to it until the probe succeeds again.

Readiness is where application-specific truth belongs. If the app requires a database connection before it can serve user requests, readiness may check that connection. If the app needs a local cache loaded before request latency is acceptable, readiness may stay false until the cache is warm. The goal is not to prove the process is alive; the goal is to avoid sending user traffic to a Pod that cannot handle it.

Think about readiness across the entire request path. A process might answer a simple HTTP request while still loading the data needed for its normal operations. The readiness endpoint should represent the capability that matters to the Service's callers, with a check cheap enough to run repeatedly. When it fails, the container remains available for investigation and may become ready again without any restart. This makes readiness useful for temporary loss of a required dependency, but a check that follows every optional dependency can unnecessarily remove a Pod that could still serve useful requests.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: readiness-web
  labels:
    app: readiness-web
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    readinessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 3
      periodSeconds: 5
      timeoutSeconds: 2
      failureThreshold: 2
```

If this readiness probe fails, `kubectl get pod` may still show the Pod as `Running`, but the `READY` column will not show the container as ready. If a Service selects the Pod, endpoint membership changes as readiness changes. That is why readiness probes are central to zero-downtime rollouts: Kubernetes can wait for new Pods to become ready before sending them traffic.

### Startup Probe: Protect Slow Boot Without Weakening Liveness Forever

A startup probe is for applications whose startup time is long, variable, or difficult to predict. Before startup probes existed, teams often used very large `initialDelaySeconds` values on liveness probes. That workaround prevented early restarts, but it also delayed detection of real failures after startup. Startup probes solve this by giving the app a separate startup budget, then handing control to normal liveness and readiness checks once startup succeeds.

The key behavior is gating. When a startup probe is configured, liveness and readiness probes do not run until the startup probe succeeds. If the startup probe never succeeds and its failure threshold is exceeded, Kubernetes restarts the container. After startup succeeds once, the startup probe is done for that container instance, and normal probe behavior begins.

Estimate the startup budget from the slowest startup that the workload is expected to complete successfully, rather than its fastest local run. Image initialization, cache loading, and cold node conditions can make a short default window misleading. Then check whether the same application needs prompt recovery after boot. A startup probe lets the initial window be generous while leaving the steady-state liveness window shorter. The budget is still finite: an application that never completes startup must eventually fail the startup check, so investigate repeated restarts instead of treating a larger threshold as a cure.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: startup-web
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    startupProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
      failureThreshold: 24
    livenessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
      failureThreshold: 2
```

This startup probe gives the container up to about two minutes to pass its first health check. Once it passes, the liveness probe can remain reasonably aggressive, which means post-startup failures are detected quickly. This is usually better than setting `initialDelaySeconds: 120` on the liveness probe, because the startup path and the steady-state recovery path are separate.

> **Active Learning Prompt: Choose the Consequence**
>
> Your application takes ninety seconds to compile templates on boot, then usually serves traffic reliably. During a traffic spike, the database sometimes rejects connections for ten seconds. Which probe should tolerate startup, which probe should stop traffic during database rejection, and which probe should avoid checking the database directly?

A strong answer uses startup for the template compilation window, readiness for database-dependent traffic routing, and liveness for process health rather than downstream availability. That division keeps Kubernetes from restarting containers just because a dependency had a temporary problem.

---

## Probe Mechanisms: How Kubernetes Checks Health

Kubernetes 1.35 supports several probe mechanisms. The mechanism should match what the application can prove cheaply and reliably. A probe that is expensive, flaky, or dependent on the wrong layer will eventually become an outage trigger.

| Mechanism | Best Fit | Success Condition | Common Risk |
|-----------|----------|-------------------|-------------|
| HTTP GET | Web services and APIs with health endpoints | HTTP status code from 200 through 399 | Endpoint performs too much work or redirects to a generic login page |
| TCP socket | Protocols where opening a port proves basic availability | TCP connection can be established | Port is open even though the application protocol is unhealthy |
| Exec | Containers with a local health command or file-based signal | Command exits with status 0 | Command is slow, missing, or consumes too many resources |
| gRPC | gRPC services implementing the standard health checking protocol | gRPC health response is serving | Service does not implement the expected health service |

### HTTP GET Probes

HTTP probes are common because most web applications can expose cheap health endpoints. Kubernetes treats status codes from 200 through 399 as success. Any other status code, timeout, DNS problem, or connection failure counts as a failed probe. Headers can be supplied when the endpoint requires a specific host or custom marker, but health checks should not require user authentication.

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
    httpHeaders:
    - name: X-Probe
      value: kubelet
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 2
```

A production HTTP health endpoint should be intentionally boring. It should not allocate large objects, call half the platform, or perform an expensive database migration check. For liveness, it should answer whether the process can still serve basic work. For readiness, it may include dependencies that are required for serving user traffic, but those dependency checks should have tight timeouts and clear failure behavior.

Match the HTTP path and port to what the container actually serves. A probe aimed at a plausible but nonexistent path can fail consistently even while the main application is healthy. An endpoint that redirects every request to a login page may produce a successful HTTP probe without proving the application is ready for real traffic. Compare the probe response with the meaning you intended, then inspect the Pod events when that meaning and the observed status disagree. The status code alone is only useful when the endpoint's contract is clear.

### TCP Socket Probes

A TCP socket probe only checks whether the kubelet can open a TCP connection to the container port. This is useful for services that do not speak HTTP, such as Redis, MySQL, or custom binary protocols. It is also weaker than an application-level check because a process may accept TCP connections while failing every real command after connection.

```yaml
livenessProbe:
  tcpSocket:
    port: 6379
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 2
```

Use TCP probes when connection acceptance is the best cheap signal available. For example, an exam question may ask for a Redis liveness check, and a TCP probe on port `6379` is fast to write and usually acceptable. In a production Redis deployment, you might prefer an exec probe that runs `redis-cli ping` if the image includes the tool and the command is reliable.

### Exec Probes

An exec probe runs a command inside the container. It succeeds when the command exits with status `0` and fails when the command exits with a nonzero status or times out. Exec probes are powerful because they can inspect local files, run application-specific commands, or query a local process without exposing another network endpoint.

```yaml
livenessProbe:
  exec:
    command:
    - sh
    - -c
    - test -f /tmp/healthy
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 2
```

The power of exec probes comes with overhead and image coupling. The command must exist in the container image, run quickly, and behave consistently under load. If a minimal image does not contain `sh`, `cat`, `curl`, or a database client, the probe will fail even if the application is healthy. That failure mode is common in exam practice because learners copy an exec command into an image that does not include the binary.

Review an exec probe as part of the image contract, not as an isolated YAML field. The command, its arguments, and any files it reads must be present inside the exact container that receives the probe. A local file can prove that startup code ran once, but it might remain present after the application stops making progress. Conversely, a useful protocol command might consume too much CPU if it runs every few seconds on every replica. Choose the check whose failure has the same meaning as the restart or traffic decision it controls.

### gRPC Probes

A gRPC probe checks a service using the [gRPC health checking protocol](https://kubernetes.io/blog/2022/05/13/grpc-probes-now-in-beta/). It is a good fit when the application already implements the standard health service and exposes it on a known port. It avoids bundling a separate probing binary into the image, which used to be a common workaround for gRPC workloads.

```yaml
livenessProbe:
  grpc:
    port: 50051
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 2
```

Use gRPC probes when the app actually implements gRPC health checking. Do not choose gRPC just because the application uses gRPC for business traffic. The probe and the service need to agree on the health protocol, otherwise the kubelet cannot interpret the response correctly.

---

## Timing Parameters: Fast Recovery Without False Positives

Probe timing is where many correct-looking manifests become operationally dangerous. The YAML may validate, but the thresholds may restart healthy applications during garbage collection pauses, slow cold starts, or temporary CPU pressure. Probe timing should be chosen from observed application behavior, not copied from a generic snippet.

| Parameter | Meaning | Default | Practical Guidance |
|-----------|---------|---------|--------------------|
| `initialDelaySeconds` | Delay before the first probe after container start | 0 | Useful without startup probes, but avoid using it as a long-term startup workaround |
| `periodSeconds` | Time between probe attempts | 10 | Shorter periods detect failures faster but increase probe load |
| `timeoutSeconds` | Time allowed for one probe attempt | 1 | Increase when the health endpoint is valid but predictably slower than one second |
| `successThreshold` | Consecutive successes required after failure | 1 | For readiness, values above one can prevent rapid endpoint flapping |
| `failureThreshold` | Consecutive failures required before action | 3 | Higher values reduce false positives but delay restart or endpoint removal |

The approximate failure action time is `initialDelaySeconds + (failureThreshold * periodSeconds)`, ignoring timeout details and scheduling jitter. For example, a liveness probe with `initialDelaySeconds: 10`, `periodSeconds: 10`, and `failureThreshold: 3` will usually restart the container after roughly forty seconds if every probe fails. That is long enough to avoid killing during a brief hiccup, but short enough to recover from a real stuck process.

The calculation changes in meaning depending on probe type. For liveness, the action is restart. For readiness, the action is endpoint removal. For startup, the action is restart after the startup budget is exhausted. The arithmetic is similar, but the consequence is different, so the same numbers may be reasonable for one probe and too aggressive for another.

Treat the formula as a planning estimate, not an exact stopwatch. Probe attempts have execution time, kubelet scheduling is not perfectly aligned with wall-clock time, and a successful attempt breaks a consecutive failure streak. Record the longest normal response time before selecting `timeoutSeconds`, then consider whether brief load spikes should be tolerated through `failureThreshold`. For readiness, faster removal may protect callers, but an overly sensitive check can make endpoints appear and disappear repeatedly. For liveness, the cost of a false positive includes a restart and another startup period, so the acceptable timing can differ.

```ascii
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Probe Timing Timeline                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  container starts                                                            │
│       │                                                                      │
│       ├── initialDelaySeconds                                                │
│       │                                                                      │
│       ├── probe attempt 1 fails                                              │
│       │      wait periodSeconds                                              │
│       ├── probe attempt 2 fails                                              │
│       │      wait periodSeconds                                              │
│       ├── probe attempt 3 fails                                              │
│       │                                                                      │
│       └── failureThreshold reached, so Kubernetes performs probe action       │
│                                                                              │
│  For liveness: restart container. For readiness: remove endpoint.             │
│  For startup: restart container because startup never completed.              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

> **Worked Example: Debug the Math Before Editing YAML**
>
> A Java API starts in thirty-five seconds on a warm node and up to ninety seconds on a cold node. The team configured a liveness probe with no startup probe, `initialDelaySeconds: 15`, `periodSeconds: 10`, and `failureThreshold: 3`. The first failure window ends at about forty-five seconds, which means cold starts can be killed before they finish. A better design is a startup probe with `periodSeconds: 5` and `failureThreshold: 24`, giving roughly two minutes for startup, then a liveness probe with normal steady-state timing.

The worked example shows the decision sequence you should use on the CKAD exam and in production reviews. First, estimate realistic startup time. Second, decide whether startup timing and steady-state failure detection need separate budgets. Third, configure startup and liveness independently so one concern does not distort the other.

---

## Designing Probe Endpoints

A health endpoint is part of the application interface. It deserves the same design care as any other API because Kubernetes will make scheduling and restart decisions from it. A weak endpoint hides broken workloads, while an overambitious endpoint creates false outages.

For liveness, design the endpoint to answer whether restarting this container is likely to improve the situation. It can check internal event loops, local worker status, or a lightweight self-test. It should usually avoid external dependencies because restarting the process rarely fixes a database outage, a DNS incident, or a third-party API failure.

For readiness, design the endpoint to answer whether the Pod should receive user traffic right now. This may include required dependencies, migrations, warmed caches, or feature flag readiness. If the Pod cannot serve useful requests without a database, failing readiness during database unavailability is often correct. The Pod stays alive, and Kubernetes stops sending it traffic until it can serve again.

For startup, design the endpoint to become successful only when the app has finished the phase that makes normal probes meaningful. It might reuse the liveness endpoint if liveness is not valid until startup completes, or it might use a dedicated endpoint that reports boot sequence completion. The startup check should not become a second readiness check; its job is to unlock normal probing.

```ascii
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Endpoint Design Boundary                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  /livez                                                                      │
│  - checks local process progress                                             │
│  - avoids broad downstream dependency checks                                 │
│  - failure means restart could help                                          │
│                                                                              │
│  /readyz                                                                     │
│  - checks whether requests can be served now                                  │
│  - may include critical dependencies with strict timeouts                     │
│  - failure means remove from Service traffic                                  │
│                                                                              │
│  /startupz                                                                   │
│  - checks whether boot has completed enough for normal probes                 │
│  - protects slow initialization without weakening steady-state liveness       │
│  - failure means keep waiting until startup budget is exhausted               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

A common senior-level design choice is to separate `/livez` and `/readyz` even when they initially return the same result. The separation gives the application room to evolve without changing Kubernetes semantics later. If the team later adds a database readiness check, it can update `/readyz` without accidentally causing liveness-driven restarts during a database incident.

Write down what each endpoint promises before implementing it. If `/livez` answers only local process progress, a failing shared dependency should not turn it red. If `/readyz` answers whether this replica can serve the Service's requests, its dependencies should match those requests rather than every background feature. Keep the startup signal tied to completion of initialization so normal probing starts at the intended boundary. This contract makes a future change reviewable: a new check can be judged by the Kubernetes action it would trigger, not just by whether its HTTP response looks healthy.

---

## Worked Example: Fix a Restart Loop Caused by Liveness

In this scenario, a learner inherits a Pod that keeps restarting. The container image is fine, but the liveness probe points at a missing path. The Pod reaches `Running`, the kubelet checks `/not-here`, receives a failing HTTP status, and restarts the container after the threshold is reached.

First, create the broken Pod so the failure is observable. Use `kubectl` throughout the module so each example runs without shell-specific aliases.

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: broken-liveness
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    livenessProbe:
      httpGet:
        path: /not-here
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 2
EOF
```

Wait long enough for the kubelet to run the probe more than once, then inspect the Pod and its events. The restart count is the first clue because liveness failures restart containers. The event stream is the stronger clue because it includes the failed probe message and often the failing status code.

```bash
sleep 20
kubectl get pod broken-liveness
kubectl describe pod broken-liveness
```

You should see events indicating that the liveness probe failed. The exact wording can vary by Kubernetes version and image behavior, but the important details are the probe type, the failing path, and the restart action. In an exam, this event section is often the fastest way to confirm whether the problem is a wrong path, wrong port, timeout, or command failure.

Now replace the Pod with a valid probe path. [Pods are mostly immutable for container probe changes](https://kubernetes.io/docs/concepts/workloads/pods/) in practical exam workflows, so deleting and recreating the Pod is usually faster than trying to patch nested fields under pressure.

```bash
kubectl delete pod broken-liveness --ignore-not-found=true

kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: broken-liveness
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 10
      failureThreshold: 3
EOF
```

Verify that the restart count remains stable after the initial start. A single successful `kubectl get pod` is useful, but not sufficient for this failure mode because liveness failures happen over time. Wait through more than one probe period before deciding the fix worked.

```bash
kubectl wait --for=condition=Ready pod/broken-liveness --timeout=60s
sleep 25
kubectl get pod broken-liveness
kubectl describe pod broken-liveness | grep -A 12 Events
```

This worked example demonstrates the full loop: observe the symptom, connect restart behavior to liveness, read kubelet events, correct the probe path, and verify over time. The same loop applies to wrong ports, missing exec commands, and probe timeouts.

---

## Debugging Readiness and Service Endpoints

Readiness problems often look like networking problems because the application process is alive but the Service has no eligible endpoints. Users report connection failures, while `kubectl get pods` shows `Running`. That mismatch is a strong signal to inspect readiness, labels, and endpoints together.

Create a small Deployment and Service to see the relationship. This example intentionally uses a readiness probe that succeeds, so you can observe the healthy baseline before thinking about failures.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ready-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ready-demo
  template:
    metadata:
      labels:
        app: ready-demo
    spec:
      containers:
      - name: app
        image: nginx:1.27
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 2
          periodSeconds: 5
          failureThreshold: 2
---
apiVersion: v1
kind: Service
metadata:
  name: ready-demo
spec:
  selector:
    app: ready-demo
  ports:
  - port: 80
    targetPort: 80
```

Apply it and verify all layers. The Deployment rollout tells you whether Kubernetes sees the desired replicas as available. The Pod list tells you readiness at the Pod level. The endpoint list tells you whether the Service has routable backend IPs.

```bash
kubectl apply -f ready-demo.yaml
kubectl rollout status deployment/ready-demo --timeout=90s
kubectl get pods -l app=ready-demo
kubectl get endpoints ready-demo
```

When readiness is broken, use the same three-layer approach. If Pods are `Running` but not `Ready`, inspect `kubectl describe pod`. [If Pods are `Ready` but endpoints are missing, inspect Service selectors and Pod labels.](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/) If endpoints exist but traffic still fails, move on to Service ports, NetworkPolicy, application behavior, or node-level networking.

```bash
kubectl describe pod -l app=ready-demo
kubectl get svc ready-demo -o yaml
kubectl get pods -l app=ready-demo --show-labels
```

This distinction matters under exam pressure because not every "Service has no endpoints" problem is a probe problem. A bad readiness probe removes endpoints. A bad selector also removes endpoints. A good debugger checks both before changing manifests.

Start with the resource nearest the visible symptom and work backward. If the Service has no backend address, compare its selector with the Pod labels before editing any health check. If labels match, compare Pod readiness and the probe events. A Pod can be running while its readiness condition is false, so phase alone does not explain routing. Once the Pod is ready and the Service selects it, endpoint membership gives a separate confirmation of the traffic path. This sequence prevents an unrelated probe edit from hiding a selector error or leaving the original failure untouched.

---

## Choosing the Right Probe Mechanism

The best probe is the cheapest one that answers the operational question accurately. Do not make a liveness probe perform a full user journey just because a full user journey is important. A full user journey belongs in synthetic monitoring outside the container restart path, while a probe should be fast, local enough to be reliable, and tied to a specific Kubernetes action.

For a web API, HTTP probes usually provide the clearest signal. Use `/livez` for local process health and `/readyz` for traffic readiness. For Redis or another TCP service, a TCP probe may be acceptable for liveness, but an exec probe with a protocol command can be stronger if the image includes the tool. For gRPC services, prefer gRPC probes when the application implements the health protocol. For minimal images, avoid exec probes that assume shell utilities exist.

| Scenario | Recommended Probe | Why This Choice Fits | Watch Out For |
|----------|-------------------|----------------------|---------------|
| HTTP API with dedicated health routes | HTTP liveness and readiness | Clear application-level signal with low overhead | Do not make liveness depend on every downstream service |
| Redis container in an exam task | TCP liveness on port 6379 | Fast to write and validates listener availability | TCP success does not prove Redis commands work |
| PostgreSQL image with `pg_isready` available | Exec readiness or liveness depending on goal | Protocol-aware check from inside the container | Missing binary or slow command causes false failures |
| gRPC service with health protocol implemented | gRPC probe | Avoids extra binaries and checks native health status | The app must expose the standard health service |
| Slow legacy Java service | Startup plus HTTP liveness and readiness | Separates boot budget from steady-state recovery | Do not replace startup probe with a huge liveness delay |

A senior probe design also considers blast radius. If one shared dependency fails and every Pod's liveness probe checks that dependency, the cluster may restart hundreds of containers at once. That does not repair the dependency; it adds load, destroys caches, and complicates recovery. In most designs, dependency availability affects readiness first, while liveness remains focused on whether this container should continue running.

Mechanism choice and probe purpose are separate decisions. An HTTP check can be either liveness or readiness, and an exec command can carry either consequence as well. First decide whether the failure should restart this container or withhold traffic; only then choose the cheapest mechanism that can observe the condition. A TCP connection may establish that a listener exists, yet it cannot establish that a request will succeed. A protocol-aware check can answer a stronger question, provided it remains reliable under load and exists in the container image used by the workload.

---

## Common Patterns

### Pattern 1: Web Application with Separate Lifecycle Endpoints

This pattern is the safest default for production web applications. The startup probe protects initialization, the liveness probe checks basic process health, and the readiness probe decides whether traffic should flow. The endpoints are separate because their meanings are separate.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: webapp-probes
  labels:
    app: webapp-probes
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    startupProbe:
      httpGet:
        path: /
        port: 80
      failureThreshold: 24
      periodSeconds: 5
      timeoutSeconds: 2
    livenessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 10
      timeoutSeconds: 2
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
      timeoutSeconds: 2
      failureThreshold: 2
```

In a real application, `/` would usually become `/startupz`, `/livez`, and `/readyz`. The `nginx` image is used here because it gives you a runnable manifest in any standard Kubernetes practice cluster. The lesson is the lifecycle structure, not that every production service should use `/`.

### Pattern 2: Readiness Gate for Traffic During Warmup

Some applications can start their process quickly but need extra time before they are useful. For example, an API might need to load routing tables, build an in-memory search index, or connect to a required database. In those cases, readiness should stay false until traffic can be handled correctly.

```yaml
readinessProbe:
  httpGet:
    path: /readyz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 2
  successThreshold: 2
  failureThreshold: 2
```

The `successThreshold: 2` setting is only valid above one for readiness probes, and it can reduce endpoint flapping after a failure. That does not mean every readiness probe needs it. Use it when a single successful check is not enough evidence that the Pod should rejoin traffic.

### Pattern 3: Exec Probe for a Local Health File

A local file check is useful for teaching exec probes because it is easy to observe and break. The application creates `/tmp/healthy` at startup, and the liveness probe restarts the container if that file disappears. This is not a universal production pattern, but it demonstrates the exec success rule clearly.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: exec-health-file
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - touch /tmp/healthy && sleep 3600
    livenessProbe:
      exec:
        command:
        - cat
        - /tmp/healthy
      initialDelaySeconds: 5
      periodSeconds: 5
      timeoutSeconds: 2
      failureThreshold: 2
```

If you delete the file with `kubectl exec exec-health-file -- rm /tmp/healthy`, the next failing probe sequence restarts the container. After restart, the startup command recreates the file, so the Pod becomes healthy again. That is a compact way to see the relationship between probe failure, container restart, and application initialization.

### Pattern 4: TCP Probe for a Non-HTTP Listener

A TCP probe works when the service's useful health signal is "is the port accepting connections?" This is common in exam tasks for Redis or simple TCP daemons. It is less expressive than a protocol-specific command, but it is valid Kubernetes configuration and often the intended answer.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: redis-tcp-probe
spec:
  containers:
  - name: redis
    image: redis:7
    ports:
    - containerPort: 6379
    livenessProbe:
      tcpSocket:
        port: 6379
      initialDelaySeconds: 10
      periodSeconds: 10
      timeoutSeconds: 2
      failureThreshold: 3
```

If the exam asks for TCP, write TCP. If a production review asks whether TCP is enough, evaluate what the team needs to know. A TCP accept proves less than a Redis `PING`, but it also avoids depending on client tools inside the image.

---

## Exam Workflow: Fast, Correct, Verifiable

Probe tasks on the CKAD exam are usually YAML editing tasks. Speed matters, but verification matters more because a one-character path or port mistake can leave a Pod restarting. The safest workflow is generate, edit, apply, describe, and verify the exact probe fields.

Start by generating a manifest when possible. Imperative commands do not expose every probe option cleanly, so use dry-run output as a starting point and edit the YAML.

```bash
kubectl run webapp --image=nginx:1.27 --port=80 --dry-run=client -o yaml > pod.yaml
```

Open `pod.yaml`, add the probe block under the container, and apply it. Be careful with indentation: probes are fields of the container, not fields of the Pod spec and not fields under `ports`.

```bash
kubectl apply -f pod.yaml
kubectl describe pod webapp | grep -E "Liveness|Readiness|Startup"
kubectl get pod webapp
```

For readiness tasks, always verify endpoint membership if a Service is involved. [A Pod can be `Running` without being a Service backend](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/), and the exam often rewards checking the exact resource affected by the configuration.

```bash
kubectl get endpoints
kubectl get endpoints webapp
kubectl describe pod webapp | grep -A 20 Events
```

For liveness tasks, wait long enough to observe stability or failure. If a liveness probe has `periodSeconds: 10` and `failureThreshold: 3`, checking one second after creation tells you almost nothing. Time-based behavior requires time-based verification.

Finish verification by matching an observation to each probe's consequence. For liveness, read the restart count together with events after enough attempts have elapsed. For readiness, compare the Pod's ready status with the Service backend view, then confirm that labels and selectors agree. For startup, check whether normal probes begin after initialization and whether the configured budget covers the intended delay. This is also a useful review discipline outside an exam: a valid manifest proves syntax, while the resource status and event history show whether the configured checks produce the behavior you wanted.

```bash
sleep 35
kubectl get pod webapp
kubectl describe pod webapp | grep -A 20 Events
```

---

## Did You Know?

- **Startup probes prevent a specific anti-pattern**: before startup probes, teams often hid slow startup by setting a huge liveness delay, which also delayed real failure detection after the app was already running.

- **Readiness failures do not restart containers**: they change Service endpoint membership, which is why a Pod can have zero restarts while still receiving no traffic.

- **Exec probes run inside the container image**: if the image does not include the command you configured, the probe fails even when the application process is healthy.

- **HTTP probe redirects can count as success**: Kubernetes treats HTTP status codes from 200 through 399 as successful, so a health endpoint that redirects may hide a badly designed check.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---------|--------------|-----------------|
| Using the same deep dependency check for liveness and readiness | A database or third-party outage can trigger restarts that do not fix the dependency and may worsen recovery | Keep liveness focused on local process health, and put traffic-critical dependencies in readiness with tight timeouts |
| Making liveness too aggressive during startup | Slow but healthy containers are killed before they finish booting, creating restart loops | Use a startup probe for slow startup, then keep liveness tuned for steady-state recovery |
| Forgetting that readiness controls Service endpoints | Debugging focuses on restart count while traffic fails because the Pod is not considered ready | Check `READY`, Pod events, Service selectors, and `kubectl get endpoints` together |
| Assuming TCP success means application success | A port can accept connections while the protocol handler or business logic is broken | Use HTTP, exec, or gRPC probes when you need an application-level signal |
| Configuring an exec probe with missing tools | Minimal images often lack `sh`, `cat`, `curl`, database clients, or custom binaries | Verify the command exists in the image, or choose a network probe that matches the app |
| Leaving `timeoutSeconds` at one second for slow checks | Legitimate health checks fail under load, causing endpoint flapping or restarts | Make health checks cheap, then set timeout values based on observed response behavior |
| Putting probe fields at the wrong YAML level | The manifest may be rejected, or the probe may not attach to the intended container | Place `startupProbe`, `livenessProbe`, and `readinessProbe` under the specific container entry |
| Treating startup probes as permanent health checks | Teams misunderstand why liveness and readiness do not run during startup, then miss post-startup behavior | Remember that startup gates normal probes only until it succeeds for that container instance |

---

## Quiz

1. **Your team deploys a Java API that starts in about twenty seconds on warm nodes but sometimes takes two minutes after a node image pull. The current liveness probe starts after thirty seconds and kills the container after three failed checks. During a rollout, new Pods repeatedly restart before becoming ready. What probe design would you apply, and how would you justify it?**

   <details>
   <summary>Answer</summary>

   Add a startup probe that gives the application enough time for the slow startup case, then keep liveness tuned for steady-state failures. For example, a startup probe with `periodSeconds: 5` and `failureThreshold: 30` gives about two and a half minutes for startup before Kubernetes restarts the container. Liveness and readiness should begin only after startup succeeds. This is better than increasing the liveness `initialDelaySeconds` to a very large value because it separates boot-time tolerance from normal failure detection after the app is running.
   </details>

2. **A Service intermittently has no endpoints, but all selected Pods show `Running` and restart counts remain at zero. Users see connection failures during these windows. Which Kubernetes objects and probe behavior should you inspect first, and what failure would you expect to find?**

   <details>
   <summary>Answer</summary>

   Inspect Pod readiness status, Pod events, Service selectors, Pod labels, and `kubectl get endpoints <service-name>`. Zero restarts make liveness failure less likely, while disappearing endpoints point toward readiness failure or a selector mismatch. If the labels and selector match, expect readiness probe failures in `kubectl describe pod`, possibly caused by a flaky readiness endpoint, an external dependency check, or thresholds that are too aggressive under normal load.
   </details>

3. **A team uses `/healthz` for both liveness and readiness. The endpoint checks the database, message queue, and a third-party billing API. When the billing API slows down, Kubernetes restarts every application Pod. How would you redesign the probes to reduce blast radius?**

   <details>
   <summary>Answer</summary>

   Split the health semantics into separate endpoints. The liveness endpoint should check local process progress and avoid broad downstream checks, because restarting the container will not repair a third-party billing outage. The readiness endpoint can check dependencies required to serve traffic, using strict timeouts and clear failure behavior so Pods are removed from endpoints when they cannot serve. This keeps traffic away from unready Pods without causing cluster-wide restarts during a dependency incident.
   </details>

4. **You are asked to add a liveness probe to a Redis Pod during an exam. The requirement says the probe must verify that port `6379` accepts connections, and no HTTP endpoint exists. Which probe mechanism should you use, and what limitation should you keep in mind?**

   <details>
   <summary>Answer</summary>

   Use a TCP socket liveness probe on port `6379`. It matches the stated requirement and is valid for a non-HTTP service. The limitation is that TCP success only proves the port accepts connections; it does not prove Redis can successfully process commands. In a production setting, an exec probe using a Redis client might provide a stronger signal if the image includes the tool and the command is reliable.
   </details>

5. **A Pod uses an exec liveness probe with `command: ["cat", "/tmp/healthy"]`. It runs well in a `busybox` test image but fails immediately after the team switches to a distroless application image. The application logs show no startup error. How would you diagnose and fix the issue?**

   <details>
   <summary>Answer</summary>

   The probe command likely fails because the distroless image does not include `cat` or the expected shell utilities. Check the Pod events with `kubectl describe pod` to confirm exec probe failures, and inspect the image design if needed. Fix the probe by using a command that actually exists in the image, adding a small purpose-built health binary, or switching to an HTTP or gRPC probe exposed by the application. Do not assume tools from a teaching image exist in a minimal production image.
   </details>

6. **During a rollout, new Pods become ready for a few seconds, then drop out of endpoints, then return again. The readiness endpoint performs a slow cache verification that sometimes takes longer than the configured one-second timeout. What changes would you evaluate before increasing replica count?**

   <details>
   <summary>Answer</summary>

   First, make the readiness check cheaper if possible, because health endpoints should be fast and predictable. Then evaluate `timeoutSeconds`, `failureThreshold`, `periodSeconds`, and possibly `successThreshold` for readiness so endpoint membership does not flap on a single slow response. Increasing replicas may hide symptoms temporarily, but it does not fix the readiness signal. The correct fix is to align readiness timing with realistic endpoint behavior while keeping the check narrow enough to avoid unnecessary load.
   </details>

7. **You inherit a Pod manifest where `livenessProbe` is indented under `spec` beside `containers` instead of under the container item. The Pod fails to apply with a schema-related error. How would you correct the manifest, and why does the nesting matter operationally?**

   <details>
   <summary>Answer</summary>

   Move `livenessProbe` under the specific container entry, at the same indentation level as fields such as `image`, `ports`, and `readinessProbe`. Probes are container-level configuration because each container in a Pod may have different health behavior, ports, commands, and lifecycle needs. The nesting matters because Kubernetes must know exactly which container the kubelet should probe and restart when liveness fails.
   </details>

---

## Hands-On Exercise

**Task**: Configure, verify, break, and repair probes for a web application so you can connect manifest fields to kubelet behavior.

**Goal**: By the end of this exercise, you should be able to prove that startup gates normal probes, liveness restarts a broken container, and readiness controls Service endpoint membership.

### Step 1: Create a Pod with Startup, Liveness, and Readiness Probes

Apply a runnable Pod manifest that uses `nginx` and HTTP probes. The paths use `/` because this image serves that path by default, which lets you focus on Kubernetes probe behavior rather than application code.

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: probe-demo
  labels:
    app: probe-demo
spec:
  containers:
  - name: app
    image: nginx:1.27
    ports:
    - containerPort: 80
    startupProbe:
      httpGet:
        path: /
        port: 80
      failureThreshold: 12
      periodSeconds: 5
      timeoutSeconds: 2
    livenessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 10
      failureThreshold: 3
      timeoutSeconds: 2
    readinessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
      failureThreshold: 2
      timeoutSeconds: 2
EOF
```

### Step 2: Verify the Pod and Probe Configuration

Use `wait`, `get`, and `describe` so you verify both high-level status and the actual probe fields attached to the container.

```bash
kubectl wait --for=condition=Ready pod/probe-demo --timeout=90s
kubectl get pod probe-demo
kubectl describe pod probe-demo | grep -E "Startup|Liveness|Readiness"
```

Success criteria: `kubectl wait --for=condition=Ready pod/probe-demo --timeout=90s` should succeed, `kubectl get pod probe-demo` should show the Pod running and ready, and `kubectl describe pod probe-demo` should confirm startup, liveness, and readiness probe configuration on the `app` container.

- [ ] `kubectl wait` reports that `pod/probe-demo` met the `Ready` condition within the timeout.
- [ ] `kubectl get pod probe-demo` shows the Pod in `Running` status with the container ready.
- [ ] `kubectl describe pod probe-demo` shows startup, liveness, and readiness probe configuration for the `app` container.

### Step 3: Expose the Pod and Confirm Readiness Controls Endpoints

Create a Service and confirm that the ready Pod appears as a backend endpoint. This connects the readiness probe to traffic routing rather than just Pod status.

```bash
kubectl expose pod probe-demo --port=80 --target-port=80
kubectl get svc probe-demo
kubectl get endpoints probe-demo
```

Success criteria: after Service creation, confirm at least one endpoint appears for `probe-demo`, and explain how a readiness change can remove that endpoint without triggering a restart.

- [ ] `kubectl get svc probe-demo` shows a Service named `probe-demo`.
- [ ] `kubectl get endpoints probe-demo` shows at least one endpoint address and port for the Pod.
- [ ] You can explain why a failing readiness probe would remove this endpoint without increasing the restart count.

### Step 4: Break the Liveness Probe Signal and Observe Restart Behavior

Delete the default `nginx` index file so the `/` path no longer returns the same successful response. Then wait long enough for the liveness probe to fail according to the configured period and threshold.

```bash
kubectl exec probe-demo -- rm /usr/share/nginx/html/index.html
sleep 40
kubectl get pod probe-demo
kubectl describe pod probe-demo | grep -A 20 Events
```

Success criteria: after deleting the default index and waiting for probe execution, the event stream should show liveness failures and container restarts, not just endpoint-only behavior.

- [ ] The Pod event stream shows failed liveness probe messages or a container restart related to probe failure.
- [ ] `kubectl get pod probe-demo` shows that restart count changed after the liveness failures.
- [ ] You can state why Kubernetes restarted the container instead of merely removing the Pod from Service endpoints.

### Step 5: Repair the Application Signal and Verify Stability

Because the container restart recreates the default file for this image, wait for the Pod to become ready again and confirm that endpoint membership returns.

```bash
kubectl wait --for=condition=Ready pod/probe-demo --timeout=90s
sleep 15
kubectl get pod probe-demo
kubectl get endpoints probe-demo
```

Success criteria: after the restart clears, the Pod should return to `Ready` and endpoints should reappear, with restart counts matching the observed recovery path.

- [ ] The Pod returns to `Ready` after the restart.
- [ ] The Service endpoint exists again after readiness succeeds.
- [ ] The restart count remains stable during the final observation window.

### Step 6: Clean Up

Remove the Service and Pod so the practice namespace is ready for the next exercise, and verify cleanup leaves no stale probes, pods, or Services that could confuse the next drill.

```bash
kubectl delete svc probe-demo --ignore-not-found=true
kubectl delete pod probe-demo --ignore-not-found=true
```

Success criteria: remove the Service and Pod and verify the namespace is clean for the next drill, while confirming no unrelated resources were removed.

- [ ] `kubectl get pod probe-demo` no longer returns the practice Pod.
- [ ] `kubectl get svc probe-demo` no longer returns the practice Service.
- [ ] No unrelated resources were deleted during cleanup.

---

## Practice Drills

### Drill 1: HTTP Liveness Probe

Create a Pod named `drill-http-live` running `nginx:1.27` with an HTTP liveness probe against `/` on port `80`. The probe should wait five seconds before the first check and run every ten seconds.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: drill-http-live
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 10
EOF

kubectl describe pod drill-http-live | grep Liveness
kubectl delete pod drill-http-live --ignore-not-found=true
```

</details>

### Drill 2: Exec Liveness Probe

Create a Pod named `drill-exec-live` using `busybox:1.36`. The container should create `/tmp/healthy` and then sleep. Configure an exec liveness probe that checks the file.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: drill-exec-live
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - touch /tmp/healthy && sleep 3600
    livenessProbe:
      exec:
        command:
        - cat
        - /tmp/healthy
      initialDelaySeconds: 5
      periodSeconds: 5
EOF

kubectl describe pod drill-exec-live | grep Liveness
kubectl delete pod drill-exec-live --ignore-not-found=true
```

</details>

### Drill 3: TCP Liveness Probe

Create a Pod named `drill-tcp-live` running `redis:7` with a TCP liveness probe on port `6379`. The probe should wait ten seconds before the first check and run every five seconds.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: drill-tcp-live
spec:
  containers:
  - name: redis
    image: redis:7
    ports:
    - containerPort: 6379
    livenessProbe:
      tcpSocket:
        port: 6379
      initialDelaySeconds: 10
      periodSeconds: 5
EOF

kubectl describe pod drill-tcp-live | grep Liveness
kubectl delete pod drill-tcp-live --ignore-not-found=true
```

</details>

### Drill 4: Readiness Probe with Service Verification

Create a Deployment named `drill-ready` with two `nginx:1.27` replicas and an HTTP readiness probe on `/`. Expose it with a Service and verify that both replicas appear as endpoints.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drill-ready
spec:
  replicas: 2
  selector:
    matchLabels:
      app: drill-ready
  template:
    metadata:
      labels:
        app: drill-ready
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 2
          periodSeconds: 3
EOF

kubectl expose deployment drill-ready --port=80 --target-port=80
kubectl rollout status deployment/drill-ready --timeout=90s
kubectl get endpoints drill-ready
kubectl delete service drill-ready --ignore-not-found=true
kubectl delete deployment drill-ready --ignore-not-found=true
```

</details>

### Drill 5: Startup Probe for Slow Initialization

Create a Pod named `drill-startup` that sleeps for twenty seconds before starting `nginx`. Configure a startup probe that gives enough time for the delayed start, then add liveness and readiness probes for the steady state.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: drill-startup
spec:
  containers:
  - name: app
    image: nginx:1.27
    command:
    - sh
    - -c
    - sleep 20 && nginx -g 'daemon off;'
    ports:
    - containerPort: 80
    startupProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
      failureThreshold: 8
    livenessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
      failureThreshold: 2
EOF

kubectl wait --for=condition=Ready pod/drill-startup --timeout=90s
kubectl describe pod drill-startup | grep -E "Startup|Liveness|Readiness"
kubectl delete pod drill-startup --ignore-not-found=true
```

</details>

### Drill 6: Diagnose a Broken Probe Path

Create a Pod with an intentionally broken liveness path, observe the restart behavior, then recreate it with the correct path. This drill mirrors a common exam troubleshooting task.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: drill-broken-path
spec:
  containers:
  - name: app
    image: nginx:1.27
    livenessProbe:
      httpGet:
        path: /missing
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 3
      failureThreshold: 2
EOF

sleep 20
kubectl get pod drill-broken-path
kubectl describe pod drill-broken-path | grep -A 20 Events

kubectl delete pod drill-broken-path --ignore-not-found=true

kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: drill-broken-path
spec:
  containers:
  - name: app
    image: nginx:1.27
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 10
EOF

kubectl wait --for=condition=Ready pod/drill-broken-path --timeout=60s
kubectl get pod drill-broken-path
kubectl delete pod drill-broken-path --ignore-not-found=true
```

</details>

### Drill 7: Distinguish Selector Problems from Readiness Problems

Create a Deployment with a valid readiness probe, then create a Service with the wrong selector. Use endpoints and labels to prove the problem is not the probe.

<details>
<summary>Solution</summary>

```bash
kubectl apply -f - << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drill-selector
spec:
  replicas: 1
  selector:
    matchLabels:
      app: drill-selector
  template:
    metadata:
      labels:
        app: drill-selector
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: drill-selector
spec:
  selector:
    app: wrong-label
  ports:
  - port: 80
    targetPort: 80
EOF

kubectl rollout status deployment/drill-selector --timeout=90s
kubectl get pods -l app=drill-selector --show-labels
kubectl get endpoints drill-selector
kubectl get service drill-selector -o yaml

kubectl delete service drill-selector --ignore-not-found=true
kubectl delete deployment drill-selector --ignore-not-found=true
```

</details>

---

## Senior Review Checklist

Before approving a probe configuration in a real cluster, review what the probe causes Kubernetes to do. A liveness probe is not a dashboard metric; it is a restart trigger. A readiness probe is not just a health URL; it is a traffic-routing gate. A startup probe is not a permanent monitor; it is a temporary shield for initialization.

Ask whether each probe checks something the container can answer reliably under normal load. If the probe depends on a broad dependency graph, consider whether that dependency belongs in readiness instead of liveness. If a probe endpoint is slow, fix the endpoint before simply raising thresholds. If an exec command depends on tools in the image, verify those tools exist in the exact image tag being deployed.

Finally, verify behavior with the Kubernetes resources that actually change. Use restart counts and events for liveness. Use Pod readiness, endpoint membership, and rollout status for readiness. Use startup timing and gated probe behavior for startup. Probe design is finished only when the manifest is valid and the observed cluster behavior matches the intended consequence.

---

## Sources

- [Kubernetes v1.35: Liveness, Readiness, and Startup Probes](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — This is the canonical v1.35 reference for probe semantics, mechanisms, defaults, and failure behavior.
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) — This task page provides runnable examples and concrete event output for probe troubleshooting.
- [Pod Conditions](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/) — It clarifies the difference between Running and Ready and explains why readiness affects Service endpoint membership.
- [Certified Kubernetes Application Developer (CKAD)](https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/) — It shows the official CKAD v1.35 domain coverage, including probes and health checks.
- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — It documents why repeated liveness or startup failures can appear as container restarts and `CrashLoopBackOff` during debugging.
- [Kubernetes v1.35: Pod Lifecycle](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — It documents the restart-policy behavior behind the module's v1.35 startup and liveness examples.
- [Pods](https://kubernetes.io/docs/concepts/workloads/pods/) — It explains the Pod update limits behind deleting and recreating the example Pod to change its probe.
- [Service](https://kubernetes.io/docs/concepts/services-networking/service/) — It explains how a Service selects backing Pods and why the module compares selectors with labels.
- [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) — It explains the ready condition of Service backends behind the module's endpoint-membership checks.
- [kubectl describe](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_describe/) — It documents the resource details and related events used to diagnose the module's failed probes.

## Next Module

Move next to [Module 3.2: Container Logging](../module-3.2-logging/) to continue with practical log collection patterns once probe behavior and endpoint routing are stable.
