---
citations_verified: true
title: "Part 3 Cumulative Quiz: Application Observability and Maintenance"
sidebar:
  order: 6
---

> **Complexity**: [COMPLEX] CKAD intermediate-to-advanced observability review
>
> **Estimated Time**: 70-90 minutes for study, practice, quiz, and cleanup
>
> **Prerequisites**: Completed Part 3 modules on probes, logs, debugging, resource monitoring, and API versions
>
> **Cluster Assumption**: Kubernetes 1.35 or later, with the [Metrics Server installed](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/) for `kubectl top`
>
## Learning Outcomes

- **Debug** unhealthy application workloads by comparing Pod status, Events, probe configuration, current and previous container logs, and Service endpoints.
- **Design** probe strategies that separate slow startup, process health, and traffic readiness while avoiding unnecessary restarts or traffic to an unprepared container.
- **Evaluate** observability evidence from `kubectl describe`, `kubectl logs`, `kubectl top`, and API discovery to choose the next useful troubleshooting action under CKAD exam pressure.
- **Compare** CrashLoopBackOff, NotReady Pods, empty endpoints, missing metrics, and deprecated API manifests, then justify a command sequence that confirms or rejects each hypothesis.
- **Implement** a diagnostic workflow for an application failure and verify that the fix changed cluster state rather than only changing a YAML file.

## Why This Module Matters

A team deploys a payment API minutes before a busy sale begins, and the rollout looks green because the Deployment reports the desired number of replicas. A few minutes later, customer requests start timing out, the Service has fewer endpoints than expected, and one container is restarting so quickly that its current logs only show the latest boot banner. Nobody is helped by a memorized command if the operator cannot decide whether the next move is `describe`, `logs --previous`, `top`, endpoint inspection, or a probe change.

This is the point where CKAD observability stops being a list of commands and becomes a diagnostic craft. Kubernetes gives you many signals, but those signals are uneven: [Events are short-lived](https://kubernetes.io/docs/reference/glossary/?all=true&term-control-plane=), logs can belong to the wrong container instance, [readiness affects traffic without restarting a container](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/), and liveness can hide a slow startup problem by repeatedly killing the process. A capable application operator does not run every command randomly; they build a hypothesis, gather the cheapest evidence, and then change only the field that matches the failure.

Part 3 is cumulative because real incidents are cumulative. A failing application might involve a bad readiness path, a Service selector typo, a memory limit that forces restarts, and a manifest copied from an older API version. Each isolated topic from earlier modules is useful, but the exam and the workplace both reward learners who can combine them quickly. This module teaches that combination: read the symptom, narrow the system boundary, inspect the right evidence, make the smallest safe fix, and verify through Kubernetes state.

The stakes are practical rather than theoretical. A readiness probe that points to the wrong port can remove every Pod from a Service while the containers continue running. A liveness probe that fires before startup completes can turn a slow application into an endless CrashLoopBackOff. A missing previous log command can erase the only useful stack trace from the container instance that actually failed. These are small configuration errors, but in production they become outages because traffic, restarts, and evidence all move independently.

## Core Content

### 1. Observability Starts With Boundaries, Not Commands

The first mistake in Kubernetes troubleshooting is treating every symptom as a Pod problem. A user-facing outage crosses several boundaries: client request, Service, Endpoints or EndpointSlices, Pod readiness, container process, filesystem, resource pressure, and sometimes the API version used to create the object. The fastest diagnostic path is not the longest command list; it is the shortest path that identifies which boundary is broken.

Use this mental model before touching YAML. If a Service has no endpoints, the immediate question is not whether nginx is installed correctly. The immediate question is whether the Service selector matches Ready Pods, because only Ready matching Pods should receive traffic. If a Pod is Running but not Ready, the immediate question is whether readiness is failing because the application is not accepting traffic or because the probe is aimed at the wrong place. If a Pod is restarting, current logs may be misleading because they show the new container instance, while `--previous` shows the one that died.

```ascii
+-------------------+      +-------------------+      +-------------------+
| External symptom  | ---> | Kubernetes route  | ---> | Container reality |
| timeout or 503    |      | Service endpoints |      | process and logs  |
+-------------------+      +-------------------+      +-------------------+
          |                          |                          |
          v                          v                          v
+-------------------+      +-------------------+      +-------------------+
| Check Service     |      | Check readiness   |      | Check previous    |
| selector and port |      | probe and Events  |      | logs and restarts |
+-------------------+      +-------------------+      +-------------------+
```

The diagram is deliberately simple because the first pass through an incident should be simple. You are trying to locate the broken boundary before you dive into details. When the boundary is Service-to-Pod, inspect selectors and endpoints. When the boundary is kubelet-to-container, inspect probes, restart counts, Events, and logs. When the boundary is scheduler-to-node resources, inspect requests, limits, node pressure, and metrics.

A useful CKAD habit is to ask, “What would have to be true for this symptom to appear?” [A Service with no endpoints requires either no matching Pods, matching Pods that are not Ready, or a selector that points at the wrong labels.](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) A CrashLoopBackOff requires a container that exits, is killed by a probe, or cannot start successfully. A missing `kubectl top` result requires either missing Metrics Server, a scrape delay, or an object that is not currently emitting metrics. Each symptom has a small set of likely causes, and that set determines the next command.

**Active learning prompt**: Before reading further, imagine a Pod that says `Running` but receives no traffic from its Service. Write down two different reasons this can happen. One reason should involve the Pod itself, and one reason should involve the Service object that routes to it.

### 2. Probe Strategy: Startup, Liveness, and Readiness Have Different Jobs

Probes are often taught as three similar YAML blocks, but their meanings are different enough that mixing them up creates outages. A startup probe protects slow initialization by [delaying liveness and readiness checks until the application has had enough time to boot](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/). A liveness probe answers, “Should kubelet restart this container because it is broken?” A readiness probe answers, “Should this Pod receive traffic right now?” Those questions point to different risks, so the probe configuration should reflect different failure behavior.

Readiness should usually be more conservative than liveness. If an application temporarily loses a database connection, it might be correct to remove the Pod from Service endpoints while keeping the process alive so it can reconnect. If liveness checks the same dependency too aggressively, kubelet may restart a process that would have recovered on its own. That creates extra load during an outage and can make the incident worse.

Startup probes are especially important for applications that perform migrations, warm caches, load models, or initialize large dependency graphs. Without a startup probe, liveness begins after `initialDelaySeconds`, and a delay that works on a developer laptop may fail on a loaded node. A startup probe gives the application a longer boot window while still allowing liveness to protect it after startup succeeds. This is not just a convenience; it changes the failure semantics from “restart during slow boot” to “restart after startup has failed beyond an acceptable threshold.”

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: observed-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: observed-api
  template:
    metadata:
      labels:
        app: observed-api
    spec:
      containers:
      - name: api
        image: nginx:1.27
        ports:
        - containerPort: 80
        startupProbe:
          httpGet:
            path: /
            port: 80
          failureThreshold: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 10
          timeoutSeconds: 2
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5
          timeoutSeconds: 2
```

This Deployment is intentionally modest because the structure matters more than the image. The startup probe allows up to five minutes of startup attempts before kubelet treats startup as failed. After startup succeeds, liveness checks every ten seconds and can restart the container if the HTTP endpoint stops responding. Readiness checks more frequently because Service routing benefits from faster traffic removal and restoration.

The probe you choose should match the failure you want Kubernetes to handle. HTTP probes are natural when the application exposes a health endpoint. TCP probes are useful when an open socket is a good readiness signal, although they cannot verify application-level correctness. Exec probes are useful when health depends on local files or commands inside the container, but they can be expensive and brittle if they run complex shell logic. A probe is part of your control plane contract with kubelet, so keep it narrow, fast, and meaningful.

| Probe Type | Main Question | Typical Action When Failing | Common CKAD Risk |
|---|---|---|---|
| startupProbe | Has the application completed initialization yet? | Delays other probes, then restarts if startup never succeeds | Missing it for slow apps causes liveness restarts during boot |
| livenessProbe | Is the container broken enough to restart? | Restarts the container after failure threshold is reached | Checking external dependencies can trigger restart storms |
| readinessProbe | Should this Pod receive Service traffic? | Removes or adds Pod endpoints without restart | Wrong path or port makes healthy Pods unreachable |
| exec probe | Does a command inside the container succeed? | Depends on probe field using it | Shell assumptions fail in minimal images |
| httpGet probe | Does an HTTP endpoint return success? | Depends on probe field using it | Path, named port, or scheme mismatch causes false failure |

A strong probe strategy treats restarts as expensive. Restarting is useful when the process is wedged, deadlocked, or unable to recover. Restarting is harmful when the application is simply waiting for a dependency, handling backpressure, or warming up slowly. Readiness is the safer signal for temporary inability to serve traffic because it changes routing without destroying process state.

Probe thresholds express an operational tolerance, not a promise that an application is healthy for an exact wall-clock duration. For periodic probes, `periodSeconds` controls how often kubelet checks, while `failureThreshold` controls how many consecutive failures trigger the action. A long period with a small threshold can delay detection; a short period with an aggressive threshold can react to brief pauses. Estimate the tolerated interval from both settings, then check the application’s normal startup and response-time variation before tightening it.

Probe design also depends on what a successful response proves. An HTTP 200 from `/healthz` might show that the process can answer a request, while a readiness endpoint might additionally verify that initialization and required local state are complete. Making every probe query every downstream service couples local recovery to remote availability. Keep liveness focused on conditions the process itself can recover from only by restarting, and let readiness represent whether this instance should receive new work.

When a probe fails, correlate the timing with rollout and container state before changing thresholds. Repeated failures beginning only during startup point toward startup budget or initialization behavior; failures after a stable period may instead indicate a bad path, port, scheme, or dependency. Events establish when kubelet acted, while application logs explain what the process was doing. A measured adjustment should change one of these causes and preserve the distinction among startup, liveness, and readiness.

**Active learning prompt**: Suppose an API returns errors while its database is unavailable, but it automatically reconnects when the database returns. Would you put the database check in liveness, readiness, both, or neither? Justify the operational consequence of your choice before you compare it with the quiz scenarios later.

### 3. Worked Example: Debug a Pod That Runs but Never Receives Traffic

This worked example shows the diagnostic sequence before you are asked to solve a similar problem independently. The scenario is common: a Deployment appears to have Pods, the containers are not crashing, but requests through the Service fail. The goal is to avoid jumping straight into the container when the routing layer may already explain the problem.

First, create a small broken workload that has a label mismatch between the Pod template and the Service selector. This is runnable in a practice namespace, and it uses only standard Kubernetes resources. The Deployment creates Pods labeled `app: checkout-api`, while the Service selects `app: checkout`, so the Service has no matching endpoints even though Pods exist.

```bash
kubectl create namespace observability-lab
kubectl -n observability-lab create deployment checkout-api --image=nginx:1.27 --replicas=2
kubectl -n observability-lab label deployment checkout-api tier=frontend
kubectl -n observability-lab expose deployment checkout-api --name=checkout-svc --port=80 --target-port=80
kubectl -n observability-lab patch svc checkout-svc -p '{"spec":{"selector":{"app":"checkout"}}}'
```

Now inspect the symptom from the Service boundary. The first command confirms the Service selector, and the second command checks whether Kubernetes found any Ready Pods that match it. Depending on your cluster version and display settings, `kubectl get endpoints` may show `<none>` for the Service, while [EndpointSlices provide the newer representation of the same routing data](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/).

```bash
kubectl -n observability-lab describe svc checkout-svc
kubectl -n observability-lab get endpoints checkout-svc
kubectl -n observability-lab get endpointslice -l kubernetes.io/service-name=checkout-svc
```

The expected evidence points away from container logs. The containers are probably fine because the Service selector currently matches no Pods. The next command compares Pod labels with the Service selector. This is a higher-value move than running `kubectl logs` because the failure boundary is already between Service and Pod selection.

```bash
kubectl -n observability-lab get pods --show-labels
kubectl -n observability-lab get svc checkout-svc -o jsonpath='{.spec.selector}{"\n"}'
```

A focused fix changes either the Service selector or the Pod labels. In most real environments, you should understand ownership before patching labels because Deployments recreate Pods from their templates. For this lab, patch the Service selector to match the Deployment label that already exists. Then verify that endpoints appear instead of assuming the patch worked.

```bash
kubectl -n observability-lab patch svc checkout-svc -p '{"spec":{"selector":{"app":"checkout-api"}}}'
kubectl -n observability-lab get endpoints checkout-svc
kubectl -n observability-lab get endpointslice -l kubernetes.io/service-name=checkout-svc
```

The lesson is that observability is not only about looking inside containers. Kubernetes routing is itself observable, and its state often explains an outage earlier than application logs do. A Service does not send traffic to all Pods in a namespace; it sends traffic to Ready Pods whose labels match the selector and whose ports match the target. If the selector is wrong, the application can be perfectly healthy and still unreachable through the Service.

A similar pattern appears with readiness probes. If labels match but Pods are not Ready, the Service may still have no usable endpoints. In that case the next evidence is `kubectl describe pod`, especially the readiness probe section and the Events near the bottom. The correct fix might be changing a probe path, exposing the right container port, or repairing the application health endpoint. The boundary-first method still holds: prove whether routing, readiness, or process health is responsible before editing YAML.

```bash
kubectl -n observability-lab get pods
kubectl -n observability-lab describe pod -l app=checkout-api
kubectl -n observability-lab logs -l app=checkout-api --tail=40
```

This worked example also shows why verification must observe cluster state, not only command success. A successful `patch` command means the API accepted the change. It does not mean traffic now has endpoints, probes now pass, or the application now responds correctly. Always follow a fix with the state that the fix was supposed to change.

### 4. CrashLoopBackOff: Preserve Evidence Before It Disappears

[CrashLoopBackOff is not a root cause; it is Kubernetes telling you that a container repeatedly started and then stopped.](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) The cause may be an application exception, a missing file, bad command arguments, a failed probe, an image issue that appears before the loop begins, or resource pressure. Your job is to separate “the process exited” from “kubelet killed the process” and then inspect the evidence from the container instance that failed.

The most important habit is checking previous logs early. Current logs belong to the currently running or recently started container instance. If the container starts, prints a boot message, crashes, and restarts, current logs might not include the stack trace from the previous instance. The `--previous` flag asks Kubernetes for [the logs from the last terminated container instance](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), which is often the only place the root cause appears.

```bash
kubectl get pod crashing-pod
kubectl describe pod crashing-pod
kubectl logs crashing-pod --previous --tail=80
kubectl logs crashing-pod --tail=80
```

Use `describe` to connect logs with lifecycle details. The `Last State` section can show exit codes, reasons, and timestamps. Events can show probe failures, image pull problems, OOM kills, failed mounts, and scheduling problems. If Events mention liveness probe failures before restarts, the application may not be exiting by itself; kubelet may be killing it because the configured health check fails.

```bash
kubectl describe pod crashing-pod | sed -n '/Containers:/,/Conditions:/p'
kubectl describe pod crashing-pod | sed -n '/Events:/,$p'
```

When a Pod has more than one container, always specify the container name. Sidecars and init containers produce different evidence, and `kubectl logs pod-name` may choose a default that is not the failing container. In a CKAD setting, this is a frequent source of wasted time because the command succeeds while answering the wrong question.

Treat a Pod’s containers as separate diagnostic subjects even though Kubernetes schedules and reports them together. A healthy frontend can keep serving its own logs while a backend repeatedly exits, and a log agent can report its own failures without explaining application behavior. First compare each container’s restart count, readiness, and last termination reason; then select the container that matches the symptom. This prevents a valid command from producing evidence about the wrong process.

The `--previous` flag has a narrow time window because it refers to the prior instance of a container in the current Pod. It does not provide an unlimited archive, and a later lifecycle change can replace the instance that the command would return. Capture relevant output promptly when restarts are frequent, then preserve the facts needed to reason: timestamps, exit code, termination reason, and nearby Events. A Pod replacement can require looking at centralized logging if retention beyond the current object matters.

Log volume is another reason to scope requests deliberately. Start with a bounded tail or time interval, add a container selector, and use a label selector only when comparing replicas is the question. Deployment-level logs may combine output from several Pods, which can interleave events and make causal ordering unclear. Once one Pod is suspicious, query it directly and use timestamps or request identifiers to connect an application message with the lifecycle evidence from `describe`.

```bash
kubectl get pod multi-app -o jsonpath='{.spec.containers[*].name}{"\n"}'
kubectl logs multi-app -c backend --previous --tail=60
kubectl logs multi-app -c frontend --tail=60
```

Resource pressure adds another layer. If the container was OOMKilled, logs may be incomplete because the kernel terminated the process. `kubectl top` helps identify current CPU and memory usage, but it does not replace lifecycle state because top shows live metrics rather than the exact reason for a previous termination. Use both signals together: lifecycle tells you what happened, metrics tells you whether the condition is still present.

```bash
kubectl top pod crashing-pod
kubectl top pod crashing-pod --containers
kubectl describe pod crashing-pod | grep -A8 "Last State"
```

The following decision flow is a practical way to avoid command wandering during CrashLoopBackOff. It starts with evidence that is most likely to disappear or be misunderstood, then moves toward configuration. You do not need to memorize the diagram; practice the habit of asking whether the container died by itself, kubelet killed it, or the environment prevented it from running correctly.

```ascii
+----------------------+
| Pod is CrashLooping  |
+----------+-----------+
           |
           v
+----------------------+
| Read previous logs   |
| kubectl logs --previous    |
+----------+-----------+
           |
           v
+----------------------+
| Describe lifecycle   |
| exit code + Events   |
+----------+-----------+
           |
           v
+----------------------+        +----------------------+
| Probe failure shown? | -----> | Inspect probe path, |
+----------+-----------+  yes   | port, delay, timing |
           | no                 +----------------------+
           v
+----------------------+        +----------------------+
| OOMKilled or limits? | -----> | Compare top metrics |
+----------+-----------+  yes   | with requests/limits|
           | no                 +----------------------+
           v
+----------------------+
| Inspect command, env,|
| mounts, image, args  |
+----------------------+
```

A senior troubleshooting stance is to change one thing at a time and verify the specific expected result. If liveness is too aggressive, increasing `initialDelaySeconds` should reduce probe-related restarts, not necessarily fix an application exception. If memory limits are too low, changing a probe path will not fix OOMKilled. If a command path is wrong, resource metrics may look normal because the process exits before doing real work. Evidence narrows the fix.

### 5. Logs, Metrics, and API Discovery Under Exam Pressure

CKAD tasks often reward speed, but speed should come from practiced command selection rather than from guessing. Logs answer “what did the process emit?” [Metrics answer “what resources are objects consuming now?”](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/) API discovery answers “what schema does this cluster accept?” These tools are complementary, and confusing them leads to shallow troubleshooting.

Logs are strongest for application behavior and container output. Use `--tail` to keep output focused, `-f` to follow active logs, `--previous` for restarted containers, and `-c` for a specific container. Use label selectors when the question is about all replicas of a Deployment, but remember that combined logs from multiple Pods can interleave lines and hide sequence. For exact diagnosis, narrow the evidence when needed.

```bash
kubectl logs deploy/checkout-api --tail=100
kubectl logs deploy/checkout-api --all-containers --tail=100
kubectl logs pod/checkout-api-abc123 -c api --previous --tail=80
kubectl logs -l app=checkout-api --since=10m --tail=200
```

Metrics are strongest for current resource usage and relative comparison. They depend on Metrics Server, so an error from `kubectl top` might be an observability-system problem rather than an application problem. Sorting helps under exam pressure when you need the highest CPU or memory consumer. Use `--containers` when a multi-container Pod hides which container is responsible.

Resource metrics answer a deliberately limited question: what resource use is reported for the sampled objects now? They do not show the peak from several minutes ago, explain which allocation caused an out-of-memory termination, or replace requests and limits from the Pod specification. Compare multiple replicas to find an outlier, inspect containers to locate the consumer, and then use `describe` for limits and last termination state. If the workload has already recovered, an empty or ordinary current reading does not disprove an earlier spike.

When `kubectl top` reports that metrics are unavailable, separate the observability pipeline failure from the workload diagnosis. Confirm whether the API exposes the metrics resource and whether Metrics Server is installed and ready before repeatedly querying the same Pod. A missing metrics response means the operator lacks that measurement at the moment; it does not prove the application uses no CPU or memory. Continue with restart counts, Events, and termination state while resolving the missing measurement through the cluster’s supported monitoring path.

Sorting all Pods by memory is useful for finding relative outliers, but it can obscure context when namespaces contain unrelated workloads or different request profiles. Narrow the query to the incident namespace when the symptom is scoped there, compare replicas of the same application, and inspect requests and limits alongside observed usage. A container near its limit may deserve attention, while a larger absolute value can be normal for a different workload. Use the metric to choose what to inspect next, not as an automatic verdict.

```bash
kubectl top pods -A --sort-by=memory
kubectl top pods -n observability-lab --sort-by=cpu
kubectl top pod checkout-api-abc123 --containers
kubectl top nodes
```

API discovery prevents stale-manifest mistakes. [Kubernetes 1.35 accepts current stable APIs for common CKAD resources such as `networking.k8s.io/v1` Ingress, `batch/v1` CronJob, and `networking.k8s.io/v1` NetworkPolicy.](https://v1-35.docs.kubernetes.io/docs/reference/generated/kubernetes-api/v1.35/) Instead of relying on memory during an exam, use `kubectl explain` or `kubectl api-resources` to confirm the group and version that the cluster serves.

Discovery should target the cluster where the manifest will be applied because API availability is a property of that API server and its enabled resources. `kubectl api-resources` helps identify the served resource name, short names, group, and scope; `kubectl explain` follows with fields from the published schema. These commands reduce guessing, but they do not validate every semantic requirement or guarantee that referenced Services, classes, or policies exist. Treat them as a schema checkpoint before server-side validation and runtime checks.

For a version migration, update the object shape as well as `apiVersion`. The Ingress stable API uses explicit path types and a service backend structure with a named service and a port reference. A manifest can pass YAML parsing while still being rejected by schema validation, or it can be accepted but route differently because its fields describe another behavior. Compare the old and current schemas, then validate the candidate against the target cluster before expecting a controller to act on it.

There are three useful validation boundaries after discovery. Local generation and `kubectl explain` help check command syntax and field expectations; server-side dry run asks the API server to validate an object without persisting it; an applied object then needs controller and runtime verification. Each boundary catches a different class of failure. Passing schema checks does not prove that a controller has reconciled the object, and seeing an accepted object does not prove that its Pods or traffic path are healthy.

```bash
kubectl explain ingress | grep VERSION
kubectl explain cronjob | grep VERSION
kubectl explain networkpolicy | grep VERSION
kubectl api-resources | grep -E 'ingresses|cronjobs|networkpolicies'
```

The subtle point is that discovery commands teach you what the API server knows, not whether your particular manifest is semantically correct. A CronJob might use `batch/v1` and still fail because field names are wrong. [An Ingress might use the right API version and still route incorrectly because `pathType` or backend service names are wrong.](https://v1-35.docs.kubernetes.io/docs/reference/using-api/deprecation-guide/) Discovery is the first gate, not the full validation story.

A useful pressure-tested sequence is symptom, scope, evidence, fix, verification. Symptom is what the user or task reports. Scope identifies whether the object boundary is Service, Pod, container, metrics, or manifest API. Evidence uses the smallest command that tests that boundary. Fix changes one relevant thing. Verification observes the state that should change as a result. This sequence is slower than guessing once, but faster than guessing three times.

The sequence also helps control blast radius. A Service selector patch changes which Pods may receive traffic, while a probe-template change triggers a rollout and replaces Pods over time. These actions have different effects, so choose the narrowest object that owns the faulty setting. Before writing, record the expected observable result, such as nonempty endpoints or a Ready condition. Afterward, compare the observed result with that expectation and keep investigating if the two do not match.

Verification should follow the causal path from the modified object toward the original user symptom. For a probe change, inspect rollout completion and Pod conditions before checking endpoints; for a selector change, compare selector labels and endpoint addresses; for a resource issue, compare live metrics with container limits and termination state. This ordered check catches a partial repair early. It also avoids treating command exit status as proof that a distributed system has converged.

Under exam time pressure, use a small evidence note rather than relying on memory while switching between objects. Record the reported symptom, the boundary you are testing, one or two observations, the changed field, and the expected verification. This keeps the next command tied to a hypothesis and makes it easier to reverse a mistaken change. It is especially useful when several signals disagree, such as Running Pods with failed readiness or normal current metrics after an earlier restart.

```ascii
+----------+     +-------+     +----------+     +------+     +-------------+
| Symptom  | --> | Scope | --> | Evidence | --> | Fix  | --> | Verification|
+----------+     +-------+     +----------+     +------+     +-------------+
| 503      |     | svc   |     | endpoints|     | label|     | endpoints   |
| restart  |     | pod   |     | previous |     | probe|     | restarts    |
| high mem |     | node  |     | top      |     | limit|     | top + state |
| bad YAML |     | api   |     | explain  |     | field|     | apply dryrun|
+----------+     +-------+     +----------+     +------+     +-------------+
```

**Active learning prompt**: Your team says, “The Deployment is broken because the Service returns 503.” Decide which command you would run first and why. Then decide what command you would run second if the first command showed empty endpoints.

### 6. From Quiz Review to Operational Practice

This module still includes a cumulative quiz, but the quiz is no longer the first teaching event. You have now reviewed the diagnostic model, probe semantics, a worked Service example, CrashLoopBackOff evidence, and the distinction among logs, metrics, and API discovery. The quiz scenarios below ask you to apply that model rather than recall isolated commands.

Before taking the quiz, set a realistic constraint. Give yourself enough time to reason, but do not let yourself browse randomly through every previous module. The CKAD exam expects you to use documentation, but it also expects a strong command-line workflow. In practice, your fastest answers will come from recognizing the failure boundary, not from memorizing every flag.

If you miss a question, classify the miss. Was the problem that you chose the wrong boundary, forgot a command flag, changed the wrong object, or failed to verify? That classification matters because the remediation is different. A wrong boundary requires more scenario practice. A forgotten flag requires command repetition. A missing verification step requires a stricter habit after every fix.

## Did You Know?

1. [Readiness failures do not restart a container; they remove the Pod from Service endpoints until the readiness condition becomes true again.](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/)

2. [`kubectl logs --previous` only works when Kubernetes still has a terminated container instance to read](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), so repeated restarts and cleanup can make this evidence disappear.

3. [EndpointSlices are the scalable successor to the older Endpoints object, but `kubectl get endpoints` remains useful for quick CKAD-style checks on small Services.](https://kubernetes.io/docs/concepts/services-networking/service/index.html)

4. [`kubectl top` reports metrics collected through the resource metrics pipeline, so it is a live usage view rather than a historical incident recorder.](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/)

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Checking application logs before checking whether a Service has endpoints | The container might be healthy while routing is broken, so logs can waste time and distract from selector or readiness evidence | Start at the boundary implied by the symptom, then move inward only when routing state is plausible |
| Using the same dependency-heavy endpoint for liveness and readiness | A temporary dependency outage can trigger restarts instead of only removing traffic from the Pod | Keep liveness focused on process health and use readiness for traffic-serving ability |
| Forgetting `--previous` during CrashLoopBackOff | Current logs may show only the latest restart and miss the failing container instance | Capture previous logs early, then connect them to exit codes and Events |
| Omitting `-c` in multi-container Pods | Kubernetes may show logs for the wrong container or ask for a container choice during time pressure | List container names and inspect the container that matches the symptom |
| Treating `kubectl top` as a root-cause tool | Metrics show current usage, not the complete history or reason for termination | Combine metrics with `describe`, Events, restart counts, and termination reasons |
| Patching a Service selector without verifying endpoints | The API can accept a patch that still selects no Ready Pods | Verify with Endpoints or EndpointSlices after every routing change |
| Copying old manifests without API discovery | Deprecated or removed API versions fail before workload behavior can even be tested | Confirm current versions with `kubectl explain` or `kubectl api-resources` in the target cluster |
| Increasing probe delays without understanding the failure | Timing changes can hide an application bug or prolong an outage | Read Events and logs first, then adjust probe type, path, port, threshold, or delay intentionally |

## Quiz

### Question 1: Service Routes to No Pods

Your team exposes a Deployment named `orders-api` through a Service named `orders-svc`. The Deployment has two Running Pods, but requests through the Service fail with connection errors. `kubectl get endpoints orders-svc` shows no addresses. What should you inspect first, and what is a focused fix if the Service selector does not match the Pod labels?
A) Restart both Pods, because Running status suggests stale network state.
B) Compare the Service selector with Pod labels, then patch the selector or labels so they match.
C) Increase the liveness failure threshold so the Service waits longer.
D) Replace the Service with an Ingress using the same selector.

<details>
<summary>Answer</summary>

Start with the routing boundary because the Service has no endpoints. Inspect the Service selector and the Pod labels, then patch either the Service selector or the workload labels so they match the intended ownership model.

Option B is correct because an empty endpoint set directly fits a selector mismatch. Options A, C, and D are wrong because restarts, probe timing, and Ingress configuration do not make a Service selector match the existing Pod labels.

```bash
kubectl describe svc orders-svc
kubectl get pods --show-labels
kubectl get svc orders-svc -o jsonpath='{.spec.selector}{"\n"}'

# Example focused fix when Pods are labeled app=orders-api:
kubectl patch svc orders-svc -p '{"spec":{"selector":{"app":"orders-api"}}}'

# Verify the state that should change:
kubectl get endpoints orders-svc
kubectl get endpointslice -l kubernetes.io/service-name=orders-svc
```

The key reasoning is that logs are not the first evidence when the Service already proves it has no endpoints. The application can be healthy and still unreachable when labels or readiness prevent endpoint registration.

</details>

### Question 2: Running Pod Is Not Ready

A Pod named `catalog-0` is Running but never becomes Ready. The readiness probe is configured as an HTTP GET on `/ready` port `8080`, but the application listens on port `8000`. What commands would you use to confirm the probe failure, and how would you correct the configuration?
A) Patch the live Pod's container port and leave its owning controller unchanged.
B) Delete the Pod so its readiness probe is evaluated again from a clean start.
C) Change the Service target port to 8000 while keeping the Pod probe on 8080.
D) Inspect readiness details and Events, then fix the readiness probe in the owning controller's Pod template.

<details>
<summary>Answer</summary>

Confirm the readiness failure through `describe`, then inspect the container port or application behavior to verify the mismatch. Correct the Pod template in the controller that owns the Pod, because editing a live Pod directly is usually not durable.

Option D is correct because the controller template is the durable source for replacement Pods, and the evidence confirms the probe mismatch. Options A, B, and C are wrong because they either change an ephemeral Pod, repeat the same failing configuration, or alter Service routing without fixing the readiness probe.

```bash
kubectl describe pod catalog-0 | sed -n '/Readiness:/,/Environment:/p'
kubectl describe pod catalog-0 | sed -n '/Events:/,$p'
kubectl get pod catalog-0 -o jsonpath='{.spec.containers[*].ports}{"\n"}'

# If this Pod is owned by a Deployment named catalog:
kubectl patch deployment catalog --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/port","value":8000}]'

kubectl rollout status deployment catalog
kubectl get pods -l app=catalog
kubectl get endpoints catalog
```

The correction should be verified through readiness and endpoints, not only through patch success. A Ready Pod should appear in the relevant Service endpoints if labels and ports also match.

</details>

### Question 3: Slow Startup Causes Restart Loop

A Java application takes three minutes to initialize on a busy node. The Deployment has a liveness probe with `initialDelaySeconds: 20`, `periodSeconds: 10`, and `failureThreshold: 3`. The Pods enter CrashLoopBackOff even though the application works locally. How would you redesign the probes so Kubernetes does not kill the application during normal startup?
A) Add a startup probe with a sufficient startup budget, then retain liveness and readiness for their separate jobs.
B) Remove readiness so every starting Pod immediately receives Service traffic.
C) Set liveness to check the database and restart whenever the dependency is unavailable.
D) Increase the replica count without changing the probe behavior.

<details>
<summary>Answer</summary>

Add a startup probe that allows enough time for initialization, then keep liveness for post-startup process health and readiness for traffic serving. The startup probe disables liveness and readiness until startup succeeds, which prevents normal slow boot from becoming a restart loop.

Option A is correct because a startup probe delays the other probes until initialization succeeds. Options B, C, and D are wrong because removing readiness risks premature traffic, dependency-heavy liveness can cause restart storms, and extra replicas repeat the same bad probe design.

```bash
kubectl patch deployment java-api --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/startupProbe",
    "value": {
      "httpGet": {
        "path": "/healthz",
        "port": 8080
      },
      "periodSeconds": 10,
      "failureThreshold": 30
    }
  },
  {
    "op": "replace",
    "path": "/spec/template/spec/containers/0/livenessProbe/httpGet/path",
    "value": "/healthz"
  },
  {
    "op": "replace",
    "path": "/spec/template/spec/containers/0/readinessProbe/httpGet/path",
    "value": "/ready"
  }
]'

kubectl rollout status deployment java-api
kubectl describe pod -l app=java-api | sed -n '/Startup:/,/Environment:/p'
```

The important design choice is not simply increasing liveness delay. A startup probe models the separate startup phase, while readiness can still keep the Pod out of traffic until it is truly able to serve.

</details>

### Question 4: CrashLoopBackOff With Missing Stack Trace

A Pod named `billing-worker` is in CrashLoopBackOff. Running `kubectl logs billing-worker` only shows the newest startup message, and the useful exception is not visible. What evidence should you collect next, and how do you decide whether the process exited or kubelet killed it?
A) Stream only current logs until the next restart and infer the previous failure from the startup banner.
B) Delete the Pod immediately so its replacement starts without the old failure state.
C) Read previous logs and inspect terminated state, exit code, reason, and Events before another restart replaces the evidence.
D) Increase the memory limit before collecting logs because CrashLoopBackOff always indicates OOM.

<details>
<summary>Answer</summary>

Collect previous logs and lifecycle details before the evidence is replaced by another restart. Use `describe` to inspect the terminated state, exit code, reason, and Events, then compare that with logs.

Option C is correct because previous logs and termination evidence distinguish an application exit from a kubelet action. Options A, B, and D are wrong because current logs omit the useful instance, deletion discards context, and CrashLoopBackOff alone does not establish an OOM cause.

```bash
kubectl logs billing-worker --previous --tail=100
kubectl describe pod billing-worker | sed -n '/Last State:/,/Ready:/p'
kubectl describe pod billing-worker | sed -n '/Events:/,$p'
```

If previous logs show an application exception and `Last State` shows a nonzero exit code, the process likely exited by itself. If Events show repeated liveness probe failures followed by restarts, kubelet likely killed the container because the probe failed. If the reason is `OOMKilled`, resource pressure is central and current logs may be incomplete.

</details>

### Question 5: Multi-Container Pod Hides the Failing Container

A Pod named `web-stack` has containers named `frontend`, `backend`, and `log-agent`. The Pod restarts repeatedly, but the frontend logs look normal. How do you identify which container is failing and retrieve the relevant logs?
A) Run `kubectl logs web-stack` repeatedly and treat the default container output as the combined Pod stream.
B) Inspect container statuses and request logs with `-c backend`, including `--previous` when the failing instance terminated.
C) Restart the frontend container so its logs include messages from the backend.
D) Read only the log-agent output because sidecars contain every application message.

<details>
<summary>Answer</summary>

List container names and inspect container statuses from `describe` or JSON output, then request logs for the container with restarts or a terminated previous state. Do not rely on the default container selection.

Option B is correct because container status identifies the failing process and `-c` selects its logs. Options A, C, and D are wrong because `kubectl logs` without `-c` chooses a default rather than merging streams, restarting the frontend does not expose backend history, and a log agent is not guaranteed to capture every message.

```bash
kubectl get pod web-stack -o jsonpath='{.spec.containers[*].name}{"\n"}'
kubectl describe pod web-stack | sed -n '/Containers:/,/Conditions:/p'

kubectl logs web-stack -c backend --previous --tail=100
kubectl logs web-stack -c backend --tail=100
```

If `backend` shows restarts and previous logs contain the exception, that is the evidence to use for the fix. The `frontend` logs can be correct and still irrelevant because a Pod-level symptom can be caused by any container in the Pod.

</details>

### Question 6: High Memory During an Incident

An API Deployment is responding slowly. One Pod is suspected of using much more memory than the others, but it has not restarted yet. What commands help you compare usage across the namespace and then inspect container-level usage for the suspicious Pod?
A) Read previous logs from every Pod and use line count as a proxy for memory use.
B) Sort nodes by CPU, then raise memory requests for every Deployment in the cluster.
C) Inspect only the Pod's YAML because configured limits show its current memory consumption.
D) Run `kubectl top pods` sorted by memory, then inspect the suspicious Pod with `--containers` if it has multiple containers.

<details>
<summary>Answer</summary>

Use `kubectl top` for current resource comparison, sorted by memory, then inspect the suspicious Pod by container if it has more than one container.

Option D is correct because current metrics identify the relative outlier and container view narrows usage within a multi-container Pod. Options A, B, and C are wrong because logs do not measure memory, CPU sorting answers a different question, and a configured limit is not a current usage reading.

```bash
kubectl top pods -n production --sort-by=memory
kubectl top pod suspicious-pod -n production --containers
kubectl describe pod suspicious-pod -n production | sed -n '/Limits:/,/Requests:/p'
```

Metrics help identify the live resource pattern, but they do not prove the historical cause of a previous restart. If the Pod later restarts, pair this with `describe` and previous logs to check for `OOMKilled` or application-level failure.

</details>

### Question 7: Manifest Uses a Deprecated API

A teammate gives you an Ingress manifest that starts with `apiVersion: extensions/v1beta1`, and `kubectl apply` fails on a Kubernetes 1.35 cluster. How do you confirm the supported API version and avoid guessing the replacement shape?
A) Discover the API on the target cluster, inspect the current schema, and use `networking.k8s.io/v1` with its current fields.
B) Change only `apiVersion` and assume every old field remains valid.
C) Apply the object to a different cluster and copy whatever version that cluster accepts.
D) Convert the Ingress to a Service without checking the intended routing behavior.

<details>
<summary>Answer</summary>

Use API discovery against the target cluster, then inspect the resource schema. For Ingress in modern Kubernetes, the stable API is `networking.k8s.io/v1`, and the manifest must use the current field structure.

Option A is correct because discovery reflects the target API server and the schema reveals field-shape changes. Options B, C, and D are wrong because a version-string edit can leave removed fields, another cluster may serve different APIs, and replacing the resource can change routing behavior.

```bash
kubectl explain ingress | grep VERSION
kubectl explain ingress.spec
kubectl api-resources | grep ingress
```

A correct fix changes more than the version string if the old manifest used obsolete fields. For example, `pathType` is required in modern Ingress paths, and backend service references use the current `service.name` and `service.port` structure.

</details>

### Question 8: Probe Fix Without Verification

You patch a Deployment to change its readiness path from `/health` to `/ready`. The command succeeds, so a teammate says the incident is fixed. What verification sequence would you run before agreeing?
A) Stop after the patch because API acceptance guarantees that Pods are healthy.
B) Check only the Deployment's desired replica count, which proves endpoint readiness.
C) Verify rollout, Pod readiness, Events, and Service endpoints because the accepted patch alone does not prove runtime behavior.
D) Delete the namespace and recreate the same objects to clear stale state.

<details>
<summary>Answer</summary>

Verify rollout, Pod readiness, Events, and Service endpoints because those are the states the readiness fix should affect. Patch success only proves that the API accepted the change.

Option C is correct because each check follows the changed probe through reconciliation to traffic routing. Options A, B, and D are wrong because object acceptance and desired replica count do not prove readiness, while deleting the namespace is destructive and does not diagnose whether the probe change worked.

```bash
kubectl rollout status deployment checkout-api
kubectl get pods -l app=checkout-api
kubectl describe pod -l app=checkout-api | sed -n '/Readiness:/,/Environment:/p'
kubectl describe pod -l app=checkout-api | sed -n '/Events:/,$p'
kubectl get endpoints checkout-svc
```

The incident is fixed only if the new Pods become Ready and the Service has the expected endpoints. If readiness still fails, the path change did not address the actual boundary or another issue remains.

</details>

## Hands-On Exercise

In this exercise you will build and repair a small observability incident in a practice namespace. The goal is not to memorize the exact YAML; the goal is to practice moving from symptom to boundary, from boundary to evidence, and from evidence to the smallest useful fix. Run this in a disposable cluster or namespace because the exercise intentionally creates broken routing and probe behavior.

### Exercise Setup

Create a namespace and deploy a small application with two intentional problems. The Service selector will not match the Pod labels, and the readiness probe will point at the wrong port. These two failures let you practice separating Service routing from Pod readiness.

```bash
kubectl create namespace part3-observability
```

```bash
cat << 'EOF' | kubectl apply -n part3-observability -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inventory-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: inventory-api
  template:
    metadata:
      labels:
        app: inventory-api
        tier: backend
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          periodSeconds: 5
          timeoutSeconds: 2
        livenessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 10
          timeoutSeconds: 2
EOF
```

```bash
cat << 'EOF' | kubectl apply -n part3-observability -f -
apiVersion: v1
kind: Service
metadata:
  name: inventory-svc
spec:
  selector:
    app: inventory
  ports:
  - port: 80
    targetPort: 80
EOF
```

### Step 1: Observe the Routing Boundary

Start with the Service because the user-facing symptom is that traffic through the Service does not work. Inspect the Service selector, Pod labels, Endpoints, and EndpointSlices. Do not change anything until you can explain whether the Service has matching Pods.

```bash
kubectl -n part3-observability describe svc inventory-svc
kubectl -n part3-observability get pods --show-labels
kubectl -n part3-observability get endpoints inventory-svc
kubectl -n part3-observability get endpointslice -l kubernetes.io/service-name=inventory-svc
```

Expected reasoning: the Service selector uses `app: inventory`, while the Pods use `app: inventory-api`. Even if the Pods were Ready, this Service would not select them. This means the first fix should address labels or selector logic before you spend time on logs.

### Step 2: Fix the Service Selector and Verify the New Symptom

Patch the Service selector to match the Pods. Then verify endpoints again. You may still see no ready addresses if readiness is failing, which is useful because it reveals the next boundary.

```bash
kubectl -n part3-observability patch svc inventory-svc -p '{"spec":{"selector":{"app":"inventory-api"}}}'
kubectl -n part3-observability get endpoints inventory-svc
kubectl -n part3-observability get pods
```

If the endpoints are still empty or not usable, do not undo the selector fix. The selector problem was real, but it was not the only problem. Multi-cause incidents are common, and the discipline is to keep confirmed fixes while continuing to inspect the next failing boundary.

### Step 3: Inspect Readiness Evidence

Now inspect one of the Pods and read the readiness probe section plus Events. The readiness probe points to port `8080`, but nginx listens on port `80` in this manifest. This is exactly the kind of error that leaves containers running while keeping them out of Service traffic.

```bash
POD_NAME="$(kubectl -n part3-observability get pod -l app=inventory-api -o jsonpath='{.items[0].metadata.name}')"
kubectl -n part3-observability describe pod "$POD_NAME" | sed -n '/Readiness:/,/Environment:/p'
kubectl -n part3-observability describe pod "$POD_NAME" | sed -n '/Events:/,$p'
```

Expected reasoning: readiness is the traffic gate, so a wrong readiness port explains why Pods do not become Ready. Liveness uses port `80`, so the containers may avoid restarts while still failing readiness. That difference is the teaching point: liveness and readiness do not have the same operational meaning.

### Step 4: Fix the Readiness Probe in the Deployment Template

Patch the Deployment template so new Pods use the correct readiness port. Because Pods managed by Deployments are recreated from the template, changing only a live Pod would not be durable. After the patch, wait for rollout and verify Pod readiness.

```bash
kubectl -n part3-observability patch deployment inventory-api --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/port","value":80}]'

kubectl -n part3-observability rollout status deployment inventory-api
kubectl -n part3-observability get pods -l app=inventory-api
kubectl -n part3-observability get endpoints inventory-svc
```

Expected reasoning: the fix should produce Ready Pods and Service endpoints. If rollout completes but endpoints remain empty, return to selector, labels, readiness Events, and port configuration. The verification state must match the intended effect of the fix.

### Step 5: Add a CrashLoopBackOff Evidence Drill

Create a Pod that exits immediately so you can practice previous logs and lifecycle inspection. This is a controlled failure, not an application you are trying to keep running. The important behavior is that the current state changes while the previous container logs preserve the failure message.

```bash
cat << 'EOF' | kubectl apply -n part3-observability -f -
apiVersion: v1
kind: Pod
metadata:
  name: failing-worker
spec:
  restartPolicy: Always
  containers:
  - name: worker
    image: busybox:1.36
    command:
    - sh
    - -c
    - echo "starting worker"; echo "fatal: missing required queue name"; exit 2
EOF
```

Wait briefly, then inspect the Pod status, previous logs, and lifecycle state. If the first `--previous` attempt is too early, wait a few seconds and run it again. The aim is to catch the terminated instance rather than only the newest start.

```bash
kubectl -n part3-observability get pod failing-worker
kubectl -n part3-observability logs failing-worker --previous --tail=20
kubectl -n part3-observability describe pod failing-worker | sed -n '/Last State:/,/Ready:/p'
kubectl -n part3-observability describe pod failing-worker | sed -n '/Events:/,$p'
```

Expected reasoning: the previous logs show the application-level failure, and the lifecycle section shows a nonzero exit code. This is different from a liveness-probe kill or an OOM kill, so the next fix would target command arguments, environment, or application configuration rather than probe timing.

### Step 6: Check Metrics and API Discovery

If your cluster has Metrics Server, compare resource usage in the namespace. If it does not, note the failure as an observability-system limitation rather than an application diagnosis. Then confirm API versions for common resources using discovery commands.

```bash
kubectl top pods -n part3-observability --sort-by=memory
POD_NAME="$(kubectl -n part3-observability get pod -l app=inventory-api -o jsonpath='{.items[0].metadata.name}')"
kubectl top pod "$POD_NAME" -n part3-observability --containers
kubectl explain ingress | grep VERSION
kubectl explain cronjob | grep VERSION
kubectl explain networkpolicy | grep VERSION
```

Expected reasoning: metrics are useful only when the metrics pipeline is available and current. API discovery is useful for confirming what the target cluster accepts. Neither replaces `describe`, Events, logs, endpoints, or rollout verification; they answer different questions.

### Success Criteria

- [ ] You can explain why the initial Service had no endpoints before inspecting application logs.
- [ ] You patched the Service selector and verified the endpoint state after the patch.
- [ ] You identified the readiness probe port mismatch from `describe` output and Events.
- [ ] You patched the Deployment template rather than treating a managed Pod as the durable source of truth.
- [ ] You verified that Pods became Ready and that the Service gained endpoints after the readiness fix.
- [ ] You captured previous logs from the intentionally failing Pod and connected them to the exit code.
- [ ] You used `kubectl top` appropriately or recognized that Metrics Server was unavailable.
- [ ] You confirmed at least one current API version with `kubectl explain` or `kubectl api-resources`.
- [ ] You can describe the difference between fixing routing, fixing readiness, and fixing a crashing process.

### Cleanup

Remove the practice namespace after you complete the exercise. Deleting the namespace removes the Deployment, Service, Pods, and intentionally failing worker created by this lab.

```bash
kubectl delete namespace part3-observability
```

## Next Module

[Part 4: Application Environment, Configuration and Security](/k8s/ckad/part4-environment/module-4.1-configmaps/) — move from observing running applications to configuring environment data, Secrets, and security settings that shape how applications behave in the cluster.

## Sources

- [training.linuxfoundation.org: certified kubernetes application developer ckad](https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/) — The official CKAD page names Kubernetes v1.35 and lists these observability-and-maintenance competencies.
- [kubernetes.io: kubectl top](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/) — The kubectl reference directly states that Metrics Server must be installed and running for `kubectl top` to work.
- [kubernetes.io: glossary](https://kubernetes.io/docs/reference/glossary/?all=true&term-control-plane=) — The Kubernetes glossary entry for Event explicitly describes limited retention and best-effort, supplemental semantics.
- [kubernetes.io: liveness readiness startup probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — The probes documentation states that failed readiness does not restart the container and sets the Pod Ready condition to false.
- [kubernetes.io: endpoint slices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) — EndpointSlice docs explain that Services with selectors track matching Pods and that endpoint readiness maps to Pod readiness.
- [kubernetes.io: pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — The Pod lifecycle docs define CrashLoopBackOff as the backoff state for a container that keeps failing and restarting.
- [kubernetes.io: kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/) — The kubectl logs reference explicitly defines `--previous` as printing logs from the previous container instance if it exists.
- [v1-35.docs.kubernetes.io: v1.35](https://v1-35.docs.kubernetes.io/docs/reference/generated/kubernetes-api/v1.35/) — The Kubernetes v1.35 API reference lists these resources under those served API group/version pairs.
- [v1-35.docs.kubernetes.io: deprecation guide](https://v1-35.docs.kubernetes.io/docs/reference/using-api/deprecation-guide/) — The v1.35 deprecation guide documents removal of old Ingress APIs and the required field-shape changes for `networking.k8s.io/v1`.
- [kubernetes.io: pod condition](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/) — The Pod conditions docs state that Pods not Ready are removed from Service endpoints, and the probes docs define readiness failure behavior.
- [kubernetes.io: index.html](https://kubernetes.io/docs/concepts/services-networking/service/index.html) — The Service docs directly support EndpointSlice primacy and legacy Endpoints limitations; the quick-check guidance is practical advice rather than an exact documentation statement.
- [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/) — It walks through selector, port, and EndpointSlice debugging in the same boundary-first style this module teaches.
