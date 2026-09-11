---
revision_pending: false
title: "CNPE Observability, Security, and Operations Lab"
slug: k8s/cnpe/module-1.4-observability-security-and-operations-lab
sidebar:
  order: 104
---

> **CNPE Track** | Complexity: `[COMPLEX]` | Time to Complete: 75-90 min
>
> **Prerequisites**: CNPE Exam Strategy and Environment, Observability Theory, SRE, Security Principles, DevSecOps, Prometheus, OpenTelemetry, Grafana, Loki, OPA/Gatekeeper, Kyverno, Falco

## Learning Outcomes

After this module, you will be able to:

- diagnose platform incidents by connecting metrics, logs, traces, events, and recent changes into one defensible evidence chain
- evaluate whether an operational symptom is caused by workload health, resource pressure, admission policy, RBAC, secret access, runtime behavior, or network controls
- implement the smallest safe remediation while preserving platform security guardrails such as admission control, workload identity, and least-privilege access
- design a repeatable verification loop that proves the original symptom improved and that the platform remains explainable after the fix
- compare platform security signals across API server authorization, admission control, policy engines, runtime detection, and workload hardening

## Why This Module Matters

Hypothetical scenario: a team deploys a routine change to an internal service, and within minutes the service dashboard turns red, a deployment rollout stalls, and the on-call channel fills with guesses. One person sees elevated latency and wants to scale the deployment immediately. Another sees an admission denial in the namespace event stream and wants to disable the policy that blocked the rollout. A third person notices a new Falco alert and wants to isolate the workload before any application-level debugging continues. All three observations may be true, yet none of them is enough by itself to justify a platform change.

CNPE-style operations expects you to work like the person who can hold that messy scene together. You need to separate user impact from instrumentation noise, identify which control plane or data plane component is enforcing a constraint, and choose a correction that does not trade security for short-term availability without evidence. The skill is not memorizing where Grafana, Prometheus, Loki, OpenTelemetry, Gatekeeper, Kyverno, Falco, or Kubernetes events live. The skill is using them as an evidence system that turns a scattered incident into a sequence of testable claims.

This module is deliberately written as a lab chapter rather than a tool catalog because real platform incidents rarely respect chapter boundaries. A latency spike may be caused by CPU throttling, a missing secret, a NetworkPolicy, a rejected PodSecurity setting, a broken workload identity binding, or an upstream dependency that is invisible until you follow trace context. A safe response starts with a disciplined loop: observe the symptom, name the strongest hypothesis, inspect the narrowest useful signal, apply the smallest safe fix, and verify the original symptom rather than celebrating the command that changed the cluster.

> **The Flight Deck Analogy**
>
> Dashboards are not the aircraft. They are instruments. The pilot does not win by staring at gauges harder; the pilot wins by interpreting the instrument cluster, choosing the right response, and confirming the aircraft is stable again.

## Building an Evidence Chain Before Changing the Cluster

Observability begins with restraint. When a service is slow, the fastest command is often not the safest command, because an early fix can destroy the evidence you need to prove what happened. Restarting Pods may clear crash history, scaling replicas may hide saturation that should have changed resource requests, and disabling a policy may make the next deployment look successful while leaving the platform weaker. A platform engineer should first describe the incident as a claim: users see a symptom, one or more signals changed at a specific time, and a recent change or control plane decision may explain the relationship.

The practical evidence chain is intentionally simple: user-facing symptom, metric shift or alert, log pattern, trace or dependency failure, event stream, and recent change. This order does not mean every incident must start in a browser or end in Git history, but it keeps you from letting the easiest signal become the answer. Metrics are excellent for measuring shape and magnitude, logs are excellent for local detail, traces are excellent for dependency paths, and Kubernetes events are excellent for control plane decisions. Each signal has a bias, so the incident story gets stronger when two independent signals point in the same direction.

Think of the evidence chain like checking a building after the lights flicker. You might look at the room light, the breaker panel, the building feed, and the work order log before replacing equipment. Each check narrows the fault domain, and each check also protects you from replacing the wrong part. In Kubernetes, the equivalent fault domains include the workload process, container resources, scheduling, service discovery, network policy, API authorization, admission control, secret projection, runtime security, and dependency health. CNPE questions reward this fault-domain thinking because it scales from a single failed Pod to a platform-wide incident.

```
User impact
    |
    v
+---------------------+      +-------------------+
| Metrics and alerts  | ---> | Logs and events   |
+---------------------+      +-------------------+
          |                            |
          v                            v
+---------------------+      +-------------------+
| Traces/dependencies | ---> | Recent change set |
+---------------------+      +-------------------+
          |
          v
+---------------------+
| Smallest safe fix   |
+---------------------+
```

Before running this, what output do you expect if the problem is an admission denial rather than a container crash? Write down the signal you expect from `kubectl get events`, the signal you expect from `kubectl logs`, and the metric you expect to remain unchanged. This small prediction step matters because it stops you from searching until something looks suspicious and instead makes you test a hypothesis against the cluster.

A good first pass uses commands that reveal state without changing it. The following sequence intentionally mixes workload state, events, logs, and rollout history, because each command answers a different question about the same failure. It is not a universal runbook, and you should not paste it blindly into production namespaces, but it shows the rhythm of starting broad enough to see the fault domain and narrow enough to avoid an unbounded tool tour.

```bash
kubectl get deploy,pod,rs -n <namespace> -l app=<app-name>
kubectl get events -n <namespace> --sort-by=.lastTimestamp | tail -n 30
kubectl logs deploy/<app-name> -n <namespace> --tail=80
kubectl rollout history deploy/<app-name> -n <namespace>
kubectl describe deploy/<app-name> -n <namespace>
```

The sequence also shows why dashboards are not root cause by themselves. A latency graph can tell you when users were affected, how quickly the effect grew, and whether the incident is still active, but it rarely tells you whether the root cause is CPU throttling, a bad dependency, a rejected rollout, or a secret that stopped mounting. The dashboard is a flight instrument, not the aircraft, so you use it to establish direction and urgency before you inspect the systems that could plausibly produce the measurement.

Prometheus-style metrics are especially useful when you treat them as comparisons rather than isolated numbers. A high error rate matters more when it correlates with deployment time, restart count, saturation, queue depth, or upstream latency. A high CPU usage value may be normal for a batch worker and catastrophic for an API server if request latency and throttling rise at the same time. A CNPE answer often becomes clear when you compare what changed against what stayed stable, because stable signals rule out entire categories of guesses.

Logs should answer a different question than metrics. They should give you local facts such as authentication failures, policy rejection messages, missing environment variables, dependency timeout names, startup stack traces, or retry behavior that metrics aggregate away. Logs are not automatically more truthful than metrics, because sampling, verbosity, log rotation, and multiline formatting can all mislead you. Treat logs as witness statements: valuable, specific, and strongest when they align with independent evidence from events, traces, or controller status.

Traces provide the strongest dependency story when the application propagates context correctly through requests. A trace can show that the frontend is healthy, the API handler is waiting on an upstream authorization call, and the upstream call began failing after a deployment. That does not automatically prove the upstream service is at fault, because network policy, DNS, certificate rotation, or service mesh identity may still sit between the spans. The value of tracing is that it gives you a request path to inspect instead of forcing you to debug every component in the namespace.

Kubernetes events are often underused because they feel less polished than dashboards, yet they can be the clearest operational signal during control plane problems. Events can tell you that a Pod was denied by admission, a volume failed to mount, an image pull failed, a scheduler could not place a Pod, a readiness probe failed, or a ReplicaSet created no ready Pods. When a deployment is blocked, events usually narrow the question faster than more application logs, because the application may never have started.

Pause and predict: if a new policy blocks privileged containers in a namespace, which evidence should appear first, and which evidence should not appear at all? You should expect an admission or validation message before a running container log line, and you should not expect application error logs from a Pod that never got admitted. That distinction is operationally important because it tells you whether the fix belongs in the workload manifest, the policy exception mechanism, the namespace labels, or the policy definition itself.

Another useful habit is separating leading indicators from confirming indicators. A leading indicator tells you where to look next, while a confirming indicator proves that the suspected cause can explain the symptom. A sudden rise in request latency is a leading indicator because many causes can produce it. A trace showing all slow requests waiting on the same dependency, plus a NetworkPolicy event at the same time, starts to confirm the fault domain. This distinction keeps you from treating every red graph as equal evidence.

Controller status can also be misleading when you read it without time. A Deployment that now reports available replicas may still have failed for ten minutes during the user-impacting window, and a Pod that is currently Ready may have restarted repeatedly before stabilizing. That is why event ordering, rollout history, and metric timelines matter together. CNPE scenarios often include a recent change because the exam wants you to reason about sequence, not just state. The question is rarely "what is true now?" by itself; it is "what changed before the symptom appeared, and what proves the relationship?"

When logs are noisy, prefer structured filters over scrolling. Search for the request identifier, trace identifier, dependency name, status code, policy name, or service account that appears in another signal. If the log system supports labels, filter by namespace, workload, container, and time window before reading individual messages. This approach is faster than reading the newest lines from every Pod, and it also avoids confirmation bias. You are not hunting for any scary line; you are checking whether a specific claim has supporting evidence.

Instrumentation gaps deserve explicit treatment. If traces are missing for one service, say so in the incident note instead of pretending the path is fully observable. If logs omit request identifiers, use events, metrics, and rollout history more heavily, then record the logging gap as follow-up. If a policy engine reports only a terse denial, inspect the policy object and improve its message after the incident. Mature platform operations does not require perfect telemetry; it requires knowing which evidence is missing and how that absence changes confidence.

## Reading Kubernetes Health and Observability Signals Together

Kubernetes gives you several layers of health, and they do not all mean the same thing. A Deployment can be progressing while every request is failing, a Pod can be Running while the application is not Ready, and a Service can have endpoints while one dependency is quietly timing out. CNPE questions often hide the answer in this distinction. You need to read controller intent, Pod lifecycle, container state, and user-facing SLO signals as related but separate evidence, because each layer reports from a different point of view.

Start with the controller because it tells you whether Kubernetes can realize the desired state. If a Deployment reports unavailable replicas, the issue may be scheduling, image pulling, readiness, admission, or a crash. If the Deployment looks healthy but users see errors, the issue may live inside the application, a dependency, routing, authorization, or policy that only affects certain requests. Controller health is necessary for a stable platform, but it is not sufficient for a correct service.

Pod status adds detail, but it also compresses reality into short reason strings. `CrashLoopBackOff`, `ImagePullBackOff`, `CreateContainerConfigError`, and `Running` are useful labels, yet the investigation still depends on events, container state, and logs. A `Running` Pod with failing readiness probes may be less useful than a crashing Pod whose last logs clearly identify a bad configuration. The habit to build is asking what question the status answers and what question remains unanswered.

The same discipline applies to alerts. A good alert points to a user-impacting condition or an exhaustion path that needs action, while a poor alert points to a raw implementation detail without context. CNPE will not ask you to design an entire alerting strategy here, but it may expect you to recognize when an alert is a symptom rather than a cause. Error budget thinking helps: if a symptom consumes budget or threatens a platform objective, it deserves incident response; if it is noisy but not user-impacting, it may deserve tuning, documentation, or a lower urgency.

| Signal | Best At Showing | Weakness | Operational Question |
|---|---|---|---|
| Metrics | Rate, magnitude, trend, saturation, error budget burn | Low detail and weak causality | Is the symptom real and how severe is it? |
| Logs | Local error detail, request context, startup failures | Volume, sampling, missing structure | What happened inside this process or controller? |
| Traces | Request path, dependency timing, propagation | Requires instrumentation and context propagation | Where did this request spend time or fail? |
| Events | Scheduling, admission, volume, image, probe, controller decisions | Short retention and uneven detail | What did Kubernetes decide or reject? |
| Audit and policy logs | Authorization and admission decisions | High volume and sensitive content | Who or what attempted the operation? |
| Runtime alerts | Suspicious process, file, network, or syscall behavior | Requires tuning and triage | Is the running container behaving outside policy? |

Exercise scenario: a service receives traffic through an Ingress, but the API percentile latency rises while Pod restarts stay flat. The first useful comparison is not whether one dashboard has a red panel; it is whether application latency, dependency latency, and resource saturation changed together. If traces show the delay begins at an upstream call and Kubernetes events show no rollout or admission failure, the safest next investigation is the dependency path. If events show a new NetworkPolicy applied at the same time, the same latency graph now points to a different fault domain.

This is why the phrase "connect metrics, logs, traces, and events into one incident story" is more than a curriculum slogan. A metric tells you the shape of pain, a trace names where a request waited, a log explains the local error, and an event tells you whether the control plane recently rejected or changed something. When these signals disagree, do not pick the signal you like best. Ask which system produced each signal, what it could not observe, and what narrow check would reconcile the disagreement.

The safest operational changes are those that correspond to a specific signal and have a verification plan before you apply them. If readiness probes fail because a dependency is unavailable, changing the probe may hide the outage rather than fix it. If CPU throttling coincides with latency and the workload has unrealistic limits, adjusting resources may be reasonable, but you should still verify latency, throttling, restarts, and node pressure afterward. If the deployment is blocked by a policy, the correction should be a policy-compliant manifest or a scoped exception, not a broad removal of admission controls.

Here is a worked example of reading a blocked rollout without changing anything. The commands deliberately ask the controller, the event stream, and the authorization system separate questions. In a real cluster, you would replace the placeholders with the namespace, deployment, service account, and resource names from the scenario.

```bash
kubectl rollout status deploy/<app-name> -n <namespace> --timeout=60s
kubectl get events -n <namespace> --sort-by=.lastTimestamp | tail -n 40
kubectl auth can-i get secrets --as=system:serviceaccount:<namespace>:<service-account> -n <namespace>
kubectl describe pod -n <namespace> -l app=<app-name>
```

If the rollout status times out, events mention a missing secret, and the service account cannot read the referenced secret, the story is much stronger than any one line by itself. The fix may be to correct the secret reference, bind a narrowly scoped Role, or move to a workload identity mechanism depending on the platform design. What matters is that the chosen fix follows from the evidence chain and can be verified by the same signals that identified the failure.

Which approach would you choose here and why: grant the application service account broad namespace secret access, create a Role for one named secret, or change the deployment to reference a secret managed by the platform? The best answer depends on the platform contract, but CNPE-style reasoning should prefer the narrowest permission that matches the workload's documented need. A broad RoleBinding may make the rollout pass, yet it also expands the blast radius of any future compromise.

## Treating Security Controls as Part of Operations

Security is not a separate phase that begins after the service is healthy. In a Kubernetes platform, security controls participate directly in ordinary operations because they decide which API calls succeed, which Pods are admitted, which identities can read secrets, which traffic paths are allowed, and which runtime behaviors generate alerts. If you remove those controls during an incident without understanding why they fired, you may restore one service while weakening the platform contract for every team that depends on it.

The security plane is easiest to reason about when you split it into decision points. Kubernetes RBAC answers whether an authenticated identity may perform an API action. Admission controllers and policy engines answer whether a requested object is acceptable before it is persisted or run. Runtime security tools answer whether an already running container behaves suspiciously. NetworkPolicy answers which Pod traffic is allowed by labels and namespaces. Secrets and workload identity answer how the workload proves who it is and obtains credentials without copying long-lived secrets into manifests.

```
Request or runtime behavior
          |
          v
+-------------------------+
| Authentication identity |
+-------------------------+
          |
          v
+-------------------------+
| RBAC authorization      |
+-------------------------+
          |
          v
+-------------------------+
| Admission and policy    |
+-------------------------+
          |
          v
+-------------------------+
| Runtime and network     |
+-------------------------+
          |
          v
+-------------------------+
| Verified workload state |
+-------------------------+
```

OPA/Gatekeeper and Kyverno are common ways to express admission policy as code, but they fit slightly different mental models. Gatekeeper uses the Open Policy Agent ecosystem and ConstraintTemplates, which can be powerful when teams need reusable policy logic. Kyverno works directly with Kubernetes-style YAML rules, which can be easier for platform teams that want validation, mutation, generation, and image verification policies close to ordinary manifests. The operational question is not which tool is fashionable; it is whether the policy explains itself, fails clearly, and supports scoped remediation.

Admission failures should be treated like compiler errors for platform contracts. A compiler error does not mean "turn off the compiler"; it means the submitted program violated a rule that protects correctness. A policy denial should tell the workload owner which field, label, image, security context, or namespace condition failed. If the denial is correct, fix the manifest. If the denial is too broad, fix the policy. If the denial is correct but an exception is justified, create a scoped and auditable exception rather than weakening the rule globally.

RBAC failures require the same care because a permission error often tempts people into granting cluster-wide access. The right question is not "what permission makes the error disappear?" but "what resource, verb, namespace, and subject match the workload's actual responsibility?" Kubernetes RBAC is additive, so once you grant a permission you cannot remove it with another Role. That design makes least privilege an operational habit, not a paperwork exercise.

Secrets and workload identity failures often look like application bugs until you inspect the event stream and environment. A Pod can fail because a Secret does not exist, because a projected volume cannot be mounted, because a controller did not create the Secret yet, or because an external identity binding is missing. The secure remediation depends on the platform pattern. You might correct a SecretStore reference, repair an ExternalSecret, bind a Kubernetes service account to a cloud identity, or fix a Vault role, but you should avoid putting sensitive values directly into manifests as an emergency shortcut.

Runtime security changes the investigation because the workload already exists. Falco-style detections may report suspicious process execution, sensitive file access, unexpected network behavior, or container escape indicators. A runtime alert is not automatically proof of compromise, but it is also not just dashboard noise. You need to correlate it with the Pod identity, image, deployment time, logs, and expected application behavior before choosing isolation, rollback, policy tuning, or escalation.

The safe-response principle is simple: preserve guardrails unless the task explicitly requires a controlled exception, and document why the exception exists. This is especially important for CNPE because platform engineering is judged by repeatability. A one-off manual patch that nobody can explain may resolve today's incident and create tomorrow's audit failure. A small manifest change, policy fix, Role update, or documented exception leaves the platform in a state another engineer can inspect.

Policy ownership is part of this safety model. If a platform team publishes a Restricted baseline, service teams need to know where to find the policy, what exception path exists, and how denial messages map to allowed remediation. Without that ownership, every incident becomes a negotiation in the middle of an outage. Good platform policy behaves like a guardrail on a road: it is visible before the dangerous edge, it bends traffic toward the safe path, and it leaves enough markings for a driver to understand the correction.

A practical security investigation should also distinguish identity from permission. Identity answers "who is making this request?" Permission answers "what is that identity allowed to do?" In Kubernetes, the subject may be a human user, a controller, or a service account mounted into a workload. If the identity is wrong, adding permissions to it may simply bless a misconfiguration. If the identity is right but the permission is missing, the Role or binding can be fixed narrowly. Mixing these questions is how teams accidentally grant power to the wrong subject.

Image and supply-chain signals can appear in operations work even when the incident looks like runtime or admission trouble. A policy may reject an unsigned image, an image verification rule may require an attestation, or a runtime alert may fire because a new image contains an unexpected binary. The safe response is to inspect the image reference, digest, policy message, and release pipeline rather than replacing the image tag with something convenient. A platform that relies on provenance must keep that evidence intact during incident response.

Secrets require similar discipline because they often sit at the boundary between application teams and platform systems. If a secret controller fails to reconcile, the symptom may appear as application authentication errors, Pod mount failures, or empty environment variables. The fix should repair the controller, store reference, identity binding, or namespace configuration that owns the secret lifecycle. Copying the value by hand into a different Secret object may restore traffic, but it creates an unmanaged credential that rotation, auditing, and revocation workflows may miss.

Use the following quick map when a deployment is blocked. It keeps the security plane from becoming a blur of tools and makes each failure type point to a specific inspection path.

| Symptom | Likely Control Point | Evidence to Inspect | Safer Remediation |
|---|---|---|---|
| `forbidden` from API server | RBAC authorization | `kubectl auth can-i`, Role, RoleBinding, ServiceAccount | Grant the narrow verb/resource/namespace needed |
| `denied the request` in events | Admission policy | Events, policy engine logs, policy object | Fix manifest or scoped policy rule |
| Secret volume will not mount | Secret access or object existence | Pod events, Secret, ExternalSecret, service account | Repair secret reference or identity binding |
| Pod rejected for security context | Pod security or admission policy | Pod spec, namespace labels, policy message | Set compliant fields or scoped exception |
| Runtime process alert | Runtime detection | Falco event, Pod logs, image, command, recent change | Confirm behavior, isolate or tune with evidence |
| Traffic blocked after deploy | NetworkPolicy or mesh identity | Endpoint, policy labels, mesh events, trace path | Correct labels or policy for intended path |

Before changing a policy, ask whether the policy is wrong, the workload is wrong, or the exception process is missing. Those are different fixes. A correct policy with poor error messages needs better feedback; an overly broad policy needs narrower matching; a workload that violates a valid baseline needs a manifest change. Treating all denials as policy bugs leads to a platform where controls exist only until the first inconvenient rollout.

## Operational Remediation and Verification Loops

An operations task is not complete when a command succeeds. It is complete when the original symptom is gone, the evidence chain now supports the new healthy state, and the platform still satisfies its security contract. This distinction matters because Kubernetes commands often report that they accepted a request, not that the system reached the desired outcome. `kubectl apply` can succeed while the rollout fails, a RoleBinding can be created while the workload still lacks the right identity, and a policy edit can be admitted while it silently stops enforcing the intended baseline.

The smallest safe fix is usually the one that changes the fewest assumptions. If a Deployment references a wrong Secret name, fix the reference or create the intended Secret through the approved controller. If a Role lacks `get` for one ConfigMap, grant that one verb to the specific service account in the specific namespace. If CPU throttling explains latency and requests are undersized, adjust resource requests and limits in the manifest rather than manually deleting Pods and hoping rescheduling helps. Small fixes are not always enough, but they preserve causality so you can prove what worked.

Verification should reuse the original symptom because otherwise you can accidentally prove the wrong thing. If the incident began as user-visible latency, verify latency and error rate, not only Pod readiness. If the incident began as a blocked rollout, verify rollout completion, events, and policy logs, not only that a YAML file applied. If the incident began as a runtime alert, verify the workload behavior and detection outcome, not only that the Pod restarted. The original symptom is the contract you owe to users and operators.

Here is a simple verification loop that keeps the before-and-after relationship visible. It can be adapted for almost any platform incident because it does not assume a specific tool stack. The goal is to write the incident story in a way that another engineer can replay from evidence rather than trusting your memory.

```bash
kubectl get events -A --sort-by=.lastTimestamp | tail -n 20
kubectl logs deploy/<name> -n <namespace> --tail=50
kubectl describe deploy/<name> -n <namespace>
```

This minimal command block matters as a last-mile check. It is not enough for every incident, and it deliberately omits metrics, traces, and policy engine logs that would be available in a fuller platform, but it remains useful for quick orientation. Events show whether the control plane is still rejecting or warning, logs show whether the workload is still failing locally, and the Deployment description shows whether the controller reached the desired state.

For a CNPE lab, you should also practice writing a remediation note in the same structure every time. State the symptom, the evidence, the cause, the change, the verification, and the guardrail status. This is not bureaucratic ceremony. It forces you to identify whether your fix preserved RBAC, admission, runtime controls, network policy, and secret handling, which is the difference between fixing a service and quietly creating a platform exception nobody can audit later.

Exercise scenario: a deployment starts failing after a new image is released, and the event stream says the Pod was rejected because the container requests privileged mode. A risky fix is to loosen the policy globally so the rollout can continue. A safer fix is to determine whether the privilege request is actually required, remove it if it is accidental, or create a scoped exception if the platform has an approved exception process. Verification then includes rollout status, absence of new admission denials, and confirmation that the policy still blocks unrelated privileged Pods.

Rollbacks deserve the same evidence standard. A rollback can be the right smallest safe fix when a recent release clearly introduced user impact, but it is not a substitute for diagnosis. If the rollback restores service, you still need to identify whether the release broke application logic, resource shape, identity, policy compliance, or a dependency contract. Otherwise the same failure returns with the next deployment, and the platform has learned nothing except how to move backward quickly.

Network and identity issues often require verification from both sides of a boundary. If a NetworkPolicy blocked traffic, verify that the intended client can connect and that unintended clients remain blocked. If a workload identity binding was missing, verify the application can obtain the intended credentials and that no static secret was introduced as a workaround. If a service mesh certificate or authorization policy was involved, verify both the trace path and the identity decision. The after-state must show that availability and security recovered together.

Operational verification also means checking for side effects. Scaling a deployment may reduce latency but increase node pressure. Relaxing a policy may unblock one rollout but admit unsafe workloads in other namespaces. Changing a service account may fix a secret read and accidentally grant access to unrelated objects. The platform engineer's job is to inspect the next ring of consequences before closing the incident, especially when the fix touched shared controls.

The after-action note should be boring, specific, and easy to audit. Include the namespace, workload, time window, symptom, primary evidence, rejected hypotheses, chosen remediation, and verification result. Rejected hypotheses are worth recording because they explain why you did not take tempting actions such as scaling, restarting, or disabling policy. They also help the next responder avoid repeating the same checks if the issue returns. In a platform environment, the note is part of the product because it teaches future operators how the system behaves under stress.

When the fix is a policy or permission change, include a negative verification. Positive verification proves the intended workload now works; negative verification proves the guardrail still blocks something it should block. For example, after adding a scoped exception for one workload, test or reason through why unrelated workloads cannot use the same exception. After adding a Role, verify the service account still cannot access neighboring secrets or cluster-wide resources. This extra step is what turns security from an obstacle into an operational invariant.

Some incidents should end with follow-up rather than more live changes. If the service is stable but the evidence shows weak logging, missing traces, confusing policy messages, or a runbook gap, capture those items outside the emergency path. Trying to solve every quality problem while users are waiting can increase risk. The operational loop restores safety first, then turns weak signals into backlog items with owners. This distinction lets you improve the platform without stretching an incident beyond the point where live changes are justified.

Finally, practice communicating uncertainty. A strong platform engineer does not say "the dashboard was red, so I fixed it." They say "latency rose after the rollout, traces showed dependency delay, events showed no admission failure, and rollback restored the original SLO, so the release likely changed dependency behavior; policy and RBAC were not implicated by the collected evidence." That statement is careful, testable, and honest about confidence. It gives the next engineer a place to continue instead of a vague claim of root cause.

## Patterns & Anti-Patterns

Patterns and anti-patterns turn individual incident tactics into platform habits. The patterns below are useful because they preserve causality, keep security controls visible, and make verification repeatable across teams. The anti-patterns are common because they feel fast in the moment, especially when a dashboard is red and people want visible action. CNPE expects you to recognize the difference between action that reduces uncertainty and action that only reduces discomfort.

| Pattern | When to Use | Why It Works | Scaling Consideration |
|---|---|---|---|
| Evidence chain first | Any incident with unclear cause | It ties user impact to independent signals before a fix | Standardize the incident note format across teams |
| Control point mapping | Any security or deployment denial | It separates RBAC, admission, runtime, network, and identity decisions | Maintain ownership for each policy and identity system |
| Smallest safe fix | Any remediation under uncertainty | It preserves causality and limits blast radius | Prefer Git-tracked changes and scoped exceptions |
| Original-symptom verification | After every remediation | It proves the user or platform contract recovered | Keep SLO dashboards and event queries close to runbooks |

| Anti-Pattern | What Goes Wrong | Why Teams Fall Into It | Better Alternative |
|---|---|---|---|
| Dashboard tunnel vision | The team treats a symptom as root cause | Graphs are visible and emotionally persuasive | Correlate metrics with logs, traces, events, and changes |
| Security bypass as incident fix | Availability returns while platform trust weakens | Policy feels like the obstacle during pressure | Fix the manifest, policy, or scoped exception path |
| Multi-change debugging | Nobody knows which change helped or harmed | Parallel action feels productive | Change one defensible thing and verify the original symptom |
| Broad RBAC grants | The workload gains unnecessary permissions | `cluster-admin` makes errors disappear quickly | Grant narrow verbs on named resources where possible |
| Manual secret injection | Sensitive values escape the platform workflow | It looks faster than repairing identity or controllers | Repair External Secrets, Vault, or workload identity flow |
| Runtime alert dismissal | Suspicious behavior continues uninvestigated | Teams assume noisy detections are false positives | Correlate alert, image, command, logs, and recent changes |

The important scaling lesson is that good platform operations moves fixes into repeatable paths. A one-time `kubectl edit` during a lab can teach you the mechanics, but production-grade operations should usually converge on declarative manifests, policy repositories, controller-owned secrets, auditable exceptions, and runbooks that include verification. The more shared the platform becomes, the more important it is that the fix teaches the system a stable rule rather than relying on the memory of the person who was online.

## Decision Framework

Use this decision framework when an incident combines observability, security, and operations signals. It is intentionally written as a structured guide rather than a rigid flowchart because real evidence often arrives out of order. The goal is to keep each decision attached to a signal and each signal attached to a safe next action.

```
1. Is there confirmed user or platform impact?
   |
   +-- No  -> tune alert, document noise, or monitor with lower urgency
   |
   +-- Yes -> identify the strongest changed signal
              |
              +-- Metrics only changed
              |      -> compare saturation, error rate, deployment time, dependency latency
              |
              +-- Events show control plane rejection
              |      -> inspect admission, RBAC, secret, scheduling, or volume cause
              |
              +-- Logs show local failure
              |      -> compare config, secret, dependency, and rollout history
              |
              +-- Traces show dependency delay
              |      -> inspect upstream health, network policy, identity, and routing
              |
              +-- Runtime alert fired
                     -> correlate process behavior, image, Pod identity, and recent changes
```

After choosing a branch, decide whether the response is observe, repair, rollback, isolate, or escalate. Observe when impact is unclear and the signal is noisy. Repair when the cause is narrow and the change is safe. Roll back when a recent release clearly introduced impact and restoring the previous known-good state is faster than forward repair. Isolate when runtime behavior suggests meaningful security risk. Escalate when the evidence points outside your authority, such as a shared identity provider, cluster admission configuration, or infrastructure dependency.

| Situation | Prefer | Avoid | Verification |
|---|---|---|---|
| Admission denial with clear message | Manifest fix or scoped policy update | Disabling the policy globally | Rollout succeeds and policy still denies invalid test case |
| RBAC forbidden for one resource | Narrow Role and RoleBinding | Cluster-wide admin binding | `kubectl auth can-i` passes only for intended action |
| Latency with resource saturation | Resource request or limit adjustment | Restart-only remediation | Latency, throttling, restarts, and node pressure improve |
| Latency isolated to dependency | Dependency or network path diagnosis | Scaling unrelated frontend Pods | Trace path and dependency metrics recover |
| Missing secret mount | Secret reference or controller repair | Hard-coded sensitive value in manifest | Pod mounts secret and secret workflow remains managed |
| Runtime suspicious behavior | Correlate and isolate if risk is credible | Ignoring all runtime detections as noise | Alert stops for fixed cause or escalation record exists |

This framework also helps you answer CNPE scenarios under time pressure. If the prompt mentions admission, RBAC, events, policy, or security context, do not jump straight to application logs unless the workload actually started. If the prompt mentions user latency, error rate, traces, or SLO burn, do not focus only on Pod status unless that status changed at the same time. If the prompt mentions runtime detection, do not treat a healthy Deployment as proof that nothing is wrong. Match the signal to the plane that produced it, then choose the narrowest next check.

The tradeoff is that structured reasoning can feel slower than immediate action. In practice, it is faster because it prevents reversals. Five minutes spent proving that a rollout is blocked by admission can save thirty minutes of chasing application logs that do not exist. A narrow RBAC check can prevent a broad permission grant that later becomes a security review issue. The decision framework is a way to keep speed and safety aligned.

## Did You Know?

- Kubernetes events are stored through the API server as event objects, but event retention is intentionally limited by cluster configuration, so serious incident workflows should export important events to durable logging or observability storage.
- Prometheus alerting rules separate detection from notification: Prometheus evaluates alert expressions, while Alertmanager handles grouping, inhibition, silencing, and routing to receivers.
- OpenTelemetry defines traces, metrics, and logs as separate signal types, which is why a platform can standardize collection without forcing every team to use the same backend storage product.
- Kubernetes v1.35 keeps Pod Security Standards oriented around Privileged, Baseline, and Restricted profiles, so a compliant remediation often means fixing fields such as privilege escalation, capabilities, host namespaces, and seccomp rather than inventing a custom security model.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Looking only at Grafana | Dashboards are visible first and show symptoms in a persuasive way, but they do not usually prove why the symptom happened. | Correlate metrics with logs, traces, Kubernetes events, rollout history, and policy decisions before changing the platform. |
| Breaking security to fix availability | Under pressure, the control that blocks a deployment can look like the problem rather than the system protecting the platform. | Fix the blocker while preserving controls through a compliant manifest, narrow RBAC, scoped exception, or corrected policy. |
| Changing multiple things at once | Parallel fixes feel efficient during an incident, but they erase the causal link between evidence and remediation. | Change the smallest defensible item first, then verify the original symptom and supporting signals before another change. |
| Ignoring admission or RBAC errors | Teams sometimes assume application logs hold the answer even when the workload was never admitted or authorized. | Check events, policy messages, `kubectl auth can-i`, Roles, RoleBindings, service accounts, and namespace labels early. |
| Forgetting to verify after the fix | A successful command can be mistaken for a recovered service, especially when the CLI exits cleanly. | Re-check the original symptom, controller state, event stream, logs, and relevant policy or identity signal. |
| Granting broad permissions for a narrow failure | It is faster to add a powerful binding than to inspect the exact verb, resource, and namespace that failed. | Use least privilege, name the subject clearly, and verify only the intended action succeeds. |
| Treating runtime detections as ordinary alert noise | Repeated false positives can make teams ignore the one signal that deserves security triage. | Correlate the runtime alert with image, command, Pod identity, deployment time, and expected process behavior. |
| Hard-coding secret values during an outage | Repairing the proper identity or secret controller can feel slower than putting a value directly in a manifest. | Restore the approved secret workflow through External Secrets, Vault, workload identity, or the platform-managed controller. |

## Quiz

<details>
<summary>Question 1: Your team sees API latency spike immediately after a deployment, but Pod restarts are flat and the event stream has no warnings. Traces show most request time is spent waiting on an upstream authorization service. What should you check next?</summary>

The strongest next check is the dependency path: upstream authorization health, network policy, service mesh identity, DNS, and any rollout or configuration change for that dependency. Pod restarts staying flat makes a local crash less likely, and the absence of Kubernetes events makes admission, scheduling, and volume failures less likely. Scaling the API deployment might hide queueing for a short time, but it does not address the span that shows where requests wait. This diagnosis tests whether you can connect metrics, traces, events, and recent changes into one evidence chain.
</details>

<details>
<summary>Question 2: A deployment fails to progress, and events say the Pod was denied because a container requested privileged mode. A teammate proposes disabling the policy for the namespace. What is the safer response?</summary>

First determine whether privileged mode is actually required. If it is accidental, remove the field and redeploy; if it is justified, use the platform's scoped exception process rather than disabling the policy broadly. The event points to admission control, not application logic, so reading application logs will not help if no Pod was admitted. Verification should include rollout success and proof that the policy still blocks unrelated privileged workloads.
</details>

<details>
<summary>Question 3: A workload receives `forbidden` when trying to read one ConfigMap in its own namespace. Which remediation best preserves the platform security posture?</summary>

Create or update a namespace-scoped Role that grants the specific verb on the specific resource, then bind it to the workload's service account. A cluster-wide binding or broad resource access would make the immediate error disappear while expanding blast radius beyond the evidence. You should verify with `kubectl auth can-i` using the service account identity and then confirm the application recovers. This answer maps the symptom to RBAC authorization rather than admission or runtime policy.
</details>

<details>
<summary>Question 4: A Falco-style runtime alert reports unexpected shell execution in a container, but the Deployment is healthy and user traffic looks normal. What should your incident response do?</summary>

Do not dismiss the alert just because readiness and traffic look healthy, because runtime detections observe behavior inside an already running container. Correlate the alert with the image, command, Pod identity, logs, recent rollout, and expected operational tasks. If the behavior is not expected, isolate or roll back according to your platform process while preserving evidence. If the behavior is expected, tune the rule with a documented reason rather than ignoring future detections.
</details>

<details>
<summary>Question 5: A service cannot mount a Secret after a platform controller upgrade. Metrics show failed requests, logs only show missing credentials, and events mention a projected volume failure. What is the most useful first fix path?</summary>

The evidence points to secret projection or the controller-owned secret workflow, so inspect the Secret object, ExternalSecret or Vault binding, service account, and controller events. Hard-coding the credential into the Deployment would bypass the approved security path and create a new risk. The fix should repair the managed secret or identity binding, then verify the Pod mounts it and requests recover. This answer uses events and logs together instead of treating the application error as the whole cause.
</details>

<details>
<summary>Question 6: A NetworkPolicy was changed at the same time an internal service began timing out only when called from one namespace. How should you verify the fix?</summary>

You should verify both the intended allowed path and the intended denied paths. A policy fix is not complete if it merely restores traffic by opening the namespace too broadly. Check labels, selected Pods, namespace selectors, endpoints, traces, and connection tests from the expected client namespace. The after-state should prove availability recovered while the network guardrail still blocks traffic outside the contract.
</details>

<details>
<summary>Question 7: After a rollback, the error rate drops to normal and users stop reporting failures. Why is the incident not necessarily finished?</summary>

The rollback proves the previous version was safer than the release, but it does not explain which platform contract the release violated. You still need to identify whether the change affected application logic, resources, identity, admission policy, network behavior, or a dependency. Without that cause, the same release can fail again when it is retried. A complete operational loop records the symptom, evidence, rollback decision, verification, and remaining follow-up.
</details>

## Hands-On Exercise

Exercise scenario: rehearse an incident response loop for one Kubernetes service or deployment in a lab cluster. You may use a real sandbox workload from the platform track, or you may choose a harmless sample deployment and reason through the failure mode without breaking a shared environment. Pick one suspected cause from resource pressure, RBAC, admission policy, secret access, network policy, or runtime behavior, then use the evidence chain to prove or disprove it.

### Setup

Choose a namespace, deployment, and service account you are allowed to inspect. If you are working in a shared cluster, do not weaken namespace policies, delete shared Secrets, or change cluster-wide policy objects. The goal is to practice diagnosis and verification, not to create a production-style outage for other learners.

```bash
kubectl get namespaces
kubectl get deploy -A
kubectl get serviceaccount -A
```

### Tasks

- [ ] Record the original symptom in one sentence, including whether it is user-visible latency, a failed rollout, an authorization error, a secret mount failure, a policy denial, or a runtime alert.
- [ ] Collect at least two independent signals from metrics, logs, traces, events, rollout state, policy output, RBAC checks, or runtime detection records.
- [ ] Map the likely cause to one platform plane: workload health, resource pressure, RBAC, admission policy, secret access, runtime behavior, network policy, or dependency health.
- [ ] Propose the smallest safe remediation and explicitly name which guardrail remains in place after the fix.
- [ ] Verify the original symptom again and record what changed in the evidence chain.
- [ ] Write a short incident note with symptom, evidence, cause, fix, verification, and remaining follow-up.

<details>
<summary>Solution guide for Task 1</summary>

Write the symptom as a testable claim rather than a vague complaint. For example, "the deployment has no available replicas because new Pods are rejected by admission" is stronger than "the app is broken." If the symptom is user-facing, include the SLO or request path affected. If the symptom is platform-facing, include the controller or policy decision that makes it visible.
</details>

<details>
<summary>Solution guide for Task 2</summary>

Use two signals that come from different systems. Pair a metric with an event, a log with an RBAC check, a trace with a NetworkPolicy inspection, or a runtime alert with rollout history. The point is not to collect every possible signal; the point is to reduce uncertainty. If the two signals disagree, write down what each signal can and cannot observe before choosing another check.
</details>

<details>
<summary>Solution guide for Task 3</summary>

Name the plane that made the decision or produced the failure. RBAC failures usually include `forbidden`; admission failures usually appear before the object runs; secret mount failures appear in Pod events; runtime detections appear after the container starts; dependency failures appear in traces and application logs. This mapping protects you from changing the wrong layer.
</details>

<details>
<summary>Solution guide for Task 4</summary>

Prefer a remediation that changes one thing and leaves a narrow audit trail. Examples include fixing a manifest field, creating a namespace-scoped Role, correcting a Secret reference, restoring a workload identity binding, or adding a documented scoped policy exception. Avoid broad policy removal, cluster-wide permissions, or manual secret injection unless the lab explicitly asks you to demonstrate why those are unsafe.
</details>

<details>
<summary>Solution guide for Tasks 5 and 6</summary>

Verify the original symptom first, then inspect the supporting signals that should have changed. A rollout problem should show successful rollout state and no new denial events. A latency problem should show improved latency and reduced pressure or dependency delay. A security problem should show the guardrail still enforcing the intended baseline. The incident note should be short enough to read during handoff and specific enough to reproduce the reasoning.
</details>

### Success Criteria

- [ ] You can explain the cause using at least two signals
- [ ] Your fix does not remove the platform guardrails entirely
- [ ] You can verify the service or policy recovered
- [ ] Your incident note names the original symptom, the fix, and the verification evidence
- [ ] You can explain why one tempting shortcut would have been less safe

### Verification Commands

```bash
kubectl get events -A --sort-by=.lastTimestamp | tail -n 20
kubectl logs deploy/<name> -n <namespace> --tail=50
kubectl describe deploy/<name> -n <namespace>
```

## Sources

- [Kubernetes documentation: Debug Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)
- [Kubernetes documentation: Events](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/)
- [Kubernetes documentation: RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Kubernetes documentation: Admission controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Kubernetes documentation: Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes documentation: Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes documentation: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Prometheus documentation: Alerting overview](https://prometheus.io/docs/alerting/latest/overview/)
- [OpenTelemetry documentation: Signals](https://opentelemetry.io/docs/concepts/signals/)
- [Grafana Loki documentation](https://grafana.com/docs/loki/latest/)
- [OPA Gatekeeper documentation](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [Kyverno documentation: Policies](https://kyverno.io/docs/policy-types/cluster-policy/)
- [Falco documentation: Rules](https://falco.org/docs/concepts/rules/)

## Next Module

Continue with [CNPE Full Mock Exam](../module-1.5-full-mock-exam/), where GitOps, platform APIs, observability, and security are combined into a timed run.
