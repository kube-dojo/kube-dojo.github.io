---
revision_pending: false
title: "Module 3.2: Container Logging"
slug: k8s/ckad/part3-observability/module-3.2-logging
sidebar:
  order: 2
lab:
  id: ckad-3.2-logging
  url: https://killercoda.com/kubedojo/scenario/ckad-3.2-logging
  duration: "30 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Long-form logging module covering an essential daily skill
>
> **Time to Complete**: 25-30 minutes
>
> **Prerequisites**: [Module 1.1 (Pods)](../part1-design-build/module-1.3-multi-container-pods/), basic understanding of stdout/stderr

---

## Learning Outcomes

After completing this module, you will be able to:
- **Debug** container failures by choosing the right `kubectl logs` flags for current, previous, selected-container, and label-selected log streams
- **Implement** stdout/stderr and structured logging patterns that Kubernetes and cluster-level collectors can capture without scraping private files
- **Diagnose** multi-container and init-container log access by identifying container names and selecting one stream or all available streams
- **Evaluate** when `kubectl logs`, label selectors, exported files, sidecars, and centralized logging are the right tool for an observability question

## Why This Module Matters

Hypothetical scenario: you deploy a small checkout service, the rollout looks green for a minute, and then one replica starts restarting while the other replica still answers requests. The Service endpoint list does not tell you why the process exited, and `kubectl describe pod` may only show a generic termination reason. The useful clue is usually the last thing the application wrote before it crashed, which means the fastest path from confusion to diagnosis is often a precise `kubectl logs` command.

Container logs are your first responder tool because they sit closest to the application behavior you are trying to explain. Metrics can tell you that error rate rose, traces can show where a request slowed down, and events can tell you that Kubernetes restarted a container, but logs often contain the application-level reason. In the CKAD exam and in daily operations, you need to retrieve those logs quickly without assuming the pod has one container, without drowning your terminal in thousands of old lines, and without losing the previous container output after a restart.

Kubernetes does not turn `kubectl logs` into a durable logging platform. It exposes the stdout and stderr streams that the kubelet can read from the container runtime on the node where the container ran. That design is intentionally narrow: it gives you immediate access during debugging, while production retention, search, indexing, alerting, and long-term analysis belong to cluster-level logging systems. This module teaches that boundary so you can use the built-in tool confidently while recognizing when you need something stronger.

> **The Flight Recorder Analogy**
>
> Container logs are like an airplane's black box. They record everything the application says through stdout and stderr. When something goes wrong, you retrieve the recording to understand what happened. Unlike a durable black box, however, Kubernetes only keeps recent local log data. If the container is replaced many times, the pod is evicted, or the node loses its local log files, older recordings may be gone unless a separate logging backend already collected them.

## The Kubernetes Log Path

The most important logging habit in Kubernetes is also the simplest one: applications should write operational messages to stdout and stderr. The container runtime captures those streams, the kubelet manages the log files on the node, and the Kubernetes API lets `kubectl logs` ask the kubelet for the relevant stream. The application does not need to know where the node stores the file, and you do not need shell access to the node for normal debugging.

That separation is why file-only logging inside a container is such a trap. A process can happily append to `/var/log/app.log` inside its filesystem while `kubectl logs` shows nothing useful, because Kubernetes is not reading arbitrary files from the container. A container image can include its own logging library, but for Kubernetes-native behavior the library should emit to stdout for normal messages and stderr for warnings or failures that should be distinguished by downstream tools.

The kubelet keeps enough local state to support immediate debugging, not enough to become your audit archive. Kubernetes documentation describes cluster-level logging as a separate architecture where node agents forward logs to a backend that stores, analyzes, and queries them independently of pods and nodes. That distinction matters during outages because deleting a pod, evicting it from a node, or cycling through several crash attempts can remove the evidence that was visible a few minutes earlier.

Pause and predict: if an application writes every message to `/var/log/app.log` inside the container and never writes to stdout or stderr, what do you expect `kubectl logs` to show? The correct prediction is "nothing relevant," even if the application is healthy and its private log file is growing. That one prediction catches many beginner debugging mistakes because it separates application logging behavior from Kubernetes log access.

The local path is easiest to remember as a short chain. Your process writes a line, the runtime records it in the runtime's Kubernetes log format, the kubelet manages the container log files under node directories such as `/var/log/containers/` and `/var/log/pods/`, and `kubectl logs` asks the API server for a stream from the kubelet. You normally interact only with the last step, but knowing the earlier steps explains both the power and the limits of the command.

This path also explains why `kubectl logs` can prove some things and cannot prove others. It can prove that a specific container wrote or did not write a line to its captured stream during the retained window. It cannot prove that an application performed no work, because the application may have handled requests without logging them, may have logged to a private file, or may have emitted structured events that were filtered before you looked.

When you interpret an empty log stream, separate absence of output from absence of behavior. A quiet nginx container in a toy lab may simply have no requests to report, while a quiet custom service after a known request may indicate a logging configuration problem. The next diagnostic step should come from that distinction: generate traffic, choose another container, inspect previous logs, or verify the application logging configuration.

The node-local storage detail matters during cluster maintenance as well. If a node is drained, a pod is evicted, or a workload controller replaces pods during a rollout, the convenient local stream may not be attached to the new object you are inspecting. That is why the safest live response is to read and preserve the relevant lines before performing disruptive actions that might replace the pod.

```
┌─────────────────────────────────────────────────────────────┐
│                    Container Logging                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Application                                                │
│       │                                                     │
│       ▼                                                     │
│  stdout/stderr ─────────────▶ Container Runtime             │
│                                      │                      │
│                                      ▼                      │
│                              /var/log/containers/           │
│                              /var/log/pods/                 │
│                                      │                      │
│                                      ▼                      │
│                              kubectl logs                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Pod: my-pod                                         │   │
│  │ ┌──────────────┐  ┌──────────────┐                 │   │
│  │ │ Container A  │  │ Container B  │                 │   │
│  │ │  (stdout)    │  │  (stdout)    │                 │   │
│  │ │  (stderr)    │  │  (stderr)    │                 │   │
│  │ └──────────────┘  └──────────────┘                 │   │
│  │        │                 │                          │   │
│  │        ▼                 ▼                          │   │
│  │ kubectl logs -c a  kubectl logs -c b                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

There are two consequences you should carry into every debugging session. First, `kubectl logs` is scoped to containers, even when the command lets you name a pod or a controller. Second, the logs have the same lifecycle risks as local node files unless a separate collector forwards them elsewhere. A good operator uses `kubectl logs` immediately, captures the important output when needed, and treats centralized logging as a production requirement rather than a nice extra.

## Reading One Pod Without Drowning

The basic `kubectl logs` command retrieves a snapshot of a container's current log stream. If the pod has exactly one regular container, Kubernetes can infer the container name, so `kubectl logs pod-name` is enough. The moment a pod has more than one regular container, that shortcut becomes ambiguous and Kubernetes asks you to specify a container with `-c`, because each container owns its own stdout and stderr streams.

The default snapshot can be too much or too little depending on the incident. A freshly started pod may have only a few lines, while a long-running pod can produce so much output that the clue scrolls away before you can read it. Filtering by recent lines, recent time, and timestamps keeps the terminal useful, and those flags are often more important than memorizing more exotic commands.

```bash
# Basic logs
kubectl logs pod-name

# Follow logs (stream)
kubectl logs -f pod-name

# Last N lines
kubectl logs --tail=100 pod-name

# Logs since timestamp
kubectl logs --since=1h pod-name
kubectl logs --since=30m pod-name
kubectl logs --since=10s pod-name

# Logs since specific time
kubectl logs --since-time=2024-01-15T10:00:00Z pod-name  # replace with a recent RFC3339 time

# Show timestamps
kubectl logs --timestamps pod-name
```

The `--tail` flag is your safest first move when you do not know the volume. It preserves your terminal, it avoids wasting time on old startup chatter, and it lets you widen the search if the last lines do not contain the clue. The `--since` and `--since-time` flags are more useful when you have a known incident window, such as "errors started after the 10:00 UTC rollout" or "the alert fired during the last half hour."

Relative windows and absolute timestamps answer different operational questions. `--since=30m` is convenient when you are debugging immediately after an alert, because it follows your current clock. `--since-time=2024-01-15T10:00:00Z` is better when you are matching a fixed event such as a rollout start, a config change, or a ticket timestamp that another engineer already recorded.

Timestamps are not only for humans reading log lines. They are also a cheap correlation tool when the cluster has no trace data available or when you are working inside an exam environment. If a readiness probe failed at a known time and the application printed a dependency error seconds earlier, the timestamped log stream can connect the Kubernetes symptom to the application cause without requiring extra tooling.

The order of flags rarely matters to `kubectl`, but the order of your reasoning does. Start with the smallest useful time or line window, inspect whether the expected stream is present, and then widen only when the evidence is missing. That habit keeps you from confusing "the clue is not in the last hundred lines" with "the clue does not exist."

Streaming with `-f` is a different mode of thinking. Instead of asking "what already happened," you ask "what happens next when I reproduce the request or wait for the next retry." That is useful during active debugging, but it can hide older lines that explain the original failure, so pair it with `--tail` or run a snapshot first. If you are watching several pods at once, be deliberate about prefixes and selectors so you know which line came from which source.

Multi-container pods add only one rule: name the stream you want. The container names live in the pod spec, so you can query them with JSONPath before choosing a log stream. `--all-containers=true` is useful when you need a quick scan, but it can mix unrelated lines, which makes timestamp and prefix discipline more important in larger pods.

```bash
# Specify container (required for multi-container)
kubectl logs pod-name -c container-name

# All containers
kubectl logs pod-name --all-containers=true

# List containers in pod
kubectl get pod pod-name -o jsonpath='{.spec.containers[*].name}'
```

Pause and predict: you run `kubectl logs my-pod` and get no output, but the application is definitely running and processing requests. The likely causes are not all Kubernetes problems. The application may be logging only to a private file, the useful lines may be in a sidecar container, or the current container may have restarted after the interesting output was written.

The previous-container flag is the fastest way to inspect a single recent crash. When a container restarts, `kubectl logs --previous` asks for the logs from the last terminated instance rather than the current fresh instance. That is exactly what you need for `CrashLoopBackOff`, but it is not a time machine for every past restart, so use it early and capture the evidence if the failure is still under investigation.

```bash
# Logs from previous crashed/restarted container
kubectl logs pod-name --previous
kubectl logs pod-name -p

# Previous instance of specific container
kubectl logs pod-name -c container-name --previous
```

Before running this in a real cluster, predict which container instance you are reading: current or previous. That mental check prevents a common mistake where someone inspects a clean startup log, sees no error, and concludes the application did not explain the crash. In reality, the error may still be available one flag away, but only until another restart or lifecycle event changes what the node keeps locally.

## Selectors, Deployments, and Replica Noise

Single-pod logging is manageable because there is only one name to type and one stream to reason about. Real applications are often managed by Deployments, ReplicaSets, Jobs, or other workload controllers that create pods with generated names. Once a Deployment has several replicas, debugging by copying one pod name at a time becomes slow and biased because you might inspect the healthy replica while the unhealthy replica is producing the useful line.

Label selectors solve that grouping problem. If the pods share a stable label such as `app=myapp`, `kubectl logs -l app=myapp` can collect logs from matching pods without forcing you to list every generated pod name. This is especially useful during CKAD tasks because labels are already central to Services, Deployments, and selection, so the same grouping concept carries into logging.

The selector is a contract with the labels on the pods, not with your intention. If a rollout introduced a new label value, if canary pods use a different label, or if an old debug pod still carries the same label, the command may include the wrong population. A quick `kubectl get pods -l app=myapp --show-labels` before a broad log command can prevent you from treating mixed workloads as one signal.

Generated pod names are another reason selectors are safer than manual copying. A Deployment can replace pods while you are investigating, and the newest pod name may not be the one that crashed. Selecting by label lets you ask a workload-level question, while reading a specific pod with `--previous` lets you ask a lifecycle-level question about one container instance. Those are complementary scopes, not interchangeable shortcuts.

```bash
# Logs from all pods with a label
kubectl logs -l app=myapp

# Follow logs from all matching pods
kubectl logs -l app=myapp -f

# Limit to specific number of pods
kubectl logs -l app=myapp --max-log-requests=5

# With tail
kubectl logs -l app=myapp --tail=50
```

Selectors also introduce two operational cautions. First, the selector must match the pods you intend, not merely the Deployment name you remember. Second, following logs from many pods uses concurrent log requests, and `kubectl logs` has limits that you may need to raise with `--max-log-requests` for larger replica sets. A command that quietly watches only part of the fleet can mislead you during a scaled incident.

Timestamps become more valuable as soon as several pods are involved. Without timestamps, you may see an error line and a recovery line but not know which came first, especially when streams from multiple pods are interleaved. With timestamps, you can compare the order of events across replicas and line it up with rollout events, readiness failures, external requests, or metrics alerts.

Stop and think: a pod has two containers, `app` and `sidecar`. You run `kubectl logs my-pod` and get an error that a container name must be specified. The fix is not to recreate the pod or change the application; the fix is to choose `-c app`, choose `-c sidecar`, or use `--all-containers=true` when you intentionally want both streams.

```bash
# Label + container + tail
kubectl logs -l app=myapp -c nginx --tail=100

# Label + since
kubectl logs -l app=myapp --since=30m
```

Selectors should narrow the question before they widen the output. If the incident is a single failing replica, start by identifying that pod and reading its previous logs. If the incident affects every replica after a rollout, a label selector with `--since` and `--timestamps` gives you a faster cross-section. The command is most useful when the label, time window, and container name all match the failure model you are testing.

## Filtering, Exporting, and Structured Output

`kubectl logs` is intentionally small, so you will often combine it with ordinary shell tools. `grep` can isolate errors, redirection can save evidence to a file, and timestamps can make a saved excerpt useful after your terminal session ends. These are not replacements for a central logging backend, but they are practical tools when you are solving an exam task or preserving the last few lines of a failing pod.

```bash
# Stream with timestamps
kubectl logs -f --timestamps pod-name

# Stream only errors (grep)
kubectl logs -f pod-name | grep -i error

# Stream from multiple pods
kubectl logs -f -l app=myapp --all-containers=true
```

The pipe to `grep` is useful for quick triage, but it can also hide context. An error line often needs the few lines before it, especially when a retry loop prints the target host, request ID, or configuration path earlier in the sequence. For serious debugging, start with a bounded snapshot, then filter once you know what pattern is worth searching.

Filtering also creates a privacy and evidence problem that beginners often miss. A command such as `grep -i token` might reveal that a secret was printed, but redirecting the full output into a file can duplicate sensitive data onto your workstation. In production, handle exported logs according to the same data rules as any other operational artifact, because the file may contain request bodies, user identifiers, or accidental credentials.

Request identifiers make shell filtering much more useful. If the application includes a stable request ID in every structured log event, you can search one identifier and reconstruct a single flow without collecting unrelated user activity. Without that field, engineers often fall back to timestamp guessing, which works for tiny labs but becomes unreliable when many replicas process concurrent requests.

```bash
# Save to file
kubectl logs pod-name > pod-logs.txt

# Save with timestamps
kubectl logs --timestamps pod-name > pod-logs-$(date +%s).txt

# All containers
kubectl logs pod-name --all-containers=true > all-logs.txt
```

Exported files are helpful when you need to compare output, attach a short excerpt to a ticket, or inspect logs without repeatedly calling the API. They are also easy to misuse. Do not treat ad hoc exported files as the system of record for production incidents, and do not capture secrets or personal data into local files unless your organization allows that workflow and you know how the file will be protected.

Structured logging makes both manual and centralized analysis more reliable. A human-readable line can be clear to the person who wrote it, but it forces downstream tools to parse text with fragile regular expressions. A JSON log line can expose fields such as timestamp, level, service, request ID, user ID surrogate, or dependency name in a consistent way, which helps collectors such as Fluent Bit, Fluentd, or Loki index the data.

**Unstructured Log (Hard to parse):**
```text
2024-03-10 14:22:01 ERROR Connection failed to db-svc:5432 user=admin
```

**Structured Log (Easy for Fluentd/Loki to index):**
```json
{"timestamp":"2024-03-10T14:22:01Z","level":"error","message":"Connection failed","service":"db-svc","port":5432,"user":"admin"}
```

The structured example is not automatically better just because it is JSON. It becomes better when the field names are stable, the values are safe to collect, and the application consistently writes one event per line to stdout or stderr. If every team invents different keys for the same concept, the logging backend still has to normalize the data, so the application contract matters as much as the output format.

Structured logs should preserve human meaning as well as machine fields. A `message` field that says "failed" is less useful than one that says which dependency failed and what operation was attempted, even if both lines are valid JSON. Good logging gives humans enough context to choose the next action and gives machines enough stable fields to group, filter, and alert without brittle text parsing.

Severity levels deserve the same care. If every routine retry is logged as `error`, central dashboards become noisy and `grep -i error` becomes less meaningful during a live incident. If real failures are logged as `info`, alerts and quick searches miss them. The stdout/stderr transport gets the data into Kubernetes, but the application still owns the quality of the signal it emits.

For CKAD, the practical takeaway is direct. Configure applications and examples so logs reach stdout and stderr, use `kubectl logs` to inspect them, and understand why a sidecar may be needed for legacy software that cannot be changed. For production engineering, the next step is designing the collection pipeline, retention policy, query model, and privacy controls that live beyond `kubectl logs`.

## Multi-Container, Init Container, and Sidecar Streams

Modern pods often contain more than the main application. A sidecar may proxy traffic, publish metrics, synchronize files, or adapt a legacy log file into stdout. An init container may perform setup work before the app starts. Each of those containers can have its own log stream, which means the first debugging decision is not only "which pod" but also "which container in that pod."

The sidecar pattern makes the stream boundary visible. In the following pod, `app` and `sidecar` are separate containers with separate names and separate logs. The main `nginx` container may have little output until it receives requests, while the BusyBox sidecar prints a message every few seconds. If you read only one stream, you might miss the behavior that explains the pod.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sidecar-demo
spec:
  containers:
  - name: app
    image: nginx
  - name: sidecar
    image: busybox
    command: ['sh', '-c', 'while true; do echo sidecar running; sleep 10; done']
```

```bash
# View main app logs
kubectl logs sidecar-demo -c app

# View sidecar logs
kubectl logs sidecar-demo -c sidecar

# All containers
kubectl logs sidecar-demo --all-containers=true
```

Use `--all-containers=true` when you are surveying the pod, then switch to `-c` when you need a clean stream. Survey mode answers "which component is talking," while selected-container mode answers "what exactly did this component say." That difference matters when a sidecar prints health messages that make the pod look active while the main container has already failed.

Init containers deserve separate attention because they run before regular app containers. If an init container fails, the application may never start, so reading the app container logs can be a dead end. You need the init container name, and you need to ask for that stream directly with `-c`, just as you would for a sidecar or any other named container in the pod.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
spec:
  initContainers:
  - name: init-setup
    image: busybox
    command: ['sh', '-c', 'echo Init complete']
  containers:
  - name: app
    image: nginx
```

```bash
# View init container logs
kubectl logs init-demo -c init-setup
```

There is a subtle difference between "previous container instance" and "init container." `--previous` selects the previous terminated instance of a named container after a restart, while `-c init-setup` selects a specific container stream by name. You can combine container selection and previous logs when a named container has restarted, but you should not use `--previous` as a substitute for identifying the correct container.

Container names are part of the pod's operational interface. Names such as `app`, `proxy`, `collector`, and `init-db` communicate intent during debugging, while names such as `container-1` make every incident slower. You may not control names during an exam question, but in real manifests clear names reduce the chance that someone reads the wrong stream under pressure.

The same rule applies to ownership. A proxy sidecar may be owned by the platform team, the application container by the service team, and a logging collector sidecar by an observability team. When you preserve logs with the container name attached, the next handoff is much clearer because the evidence already points to the component that produced it.

Sidecars can also bridge file-only legacy logging into the Kubernetes model. The better long-term fix is to make the application write to stdout and stderr directly, but sometimes you inherit software that cannot be changed quickly. In that case, a sidecar can read a shared volume file and write each line to its own stdout, making the data visible to kubelet and collection agents while you plan the application change.

## Worked Log Investigation

Exercise scenario: a Deployment has two replicas, and users report intermittent failures after a configuration change. One pod is still serving traffic, one pod is restarting, and the Service remains reachable because at least one endpoint is healthy. The goal is not to run every logging flag you know; the goal is to choose the smallest sequence that explains the failure without destroying the evidence.

Start by identifying the pods that belong to the application and checking restart counts. The restart count tells you which pod deserves attention, while the labels tell you whether a selector-based log command will include the right set. If you already know the label, use it consistently so the pod list, snapshot logs, and follow-up commands refer to the same workload population.

Next, read the current logs with a short tail and timestamps. If the container restarted recently, the current logs may show only the new startup attempt, which is still useful because it confirms the process has begun again. Do not stop there if the restart count is nonzero. Move to `--previous` for the same pod and container so you can read the output that was written before the last termination.

If the pod has multiple containers, list the container names before asking for logs. In a pod with `app`, `proxy`, and `metrics`, the proxy may report upstream failures while the app reports configuration parse errors. Reading the wrong stream is not just incomplete; it can send you toward the wrong owner and the wrong fix.

If the failure appears across all replicas, switch from one pod to a label selector. Add `--since` to match the incident window, `--tail` to bound the output, and `--timestamps` when you need to compare timing. Raise `--max-log-requests` when the selector matches more pods than the default concurrent follow limit, especially when you are streaming a live issue.

When you have a meaningful excerpt, export it with timestamps before deleting or recreating the pod. In an exam, that file may simply help you inspect the line without scrolling. In real operations, it may help you hand off evidence to another engineer while the central logging system catches up or while access to the production backend is restricted.

The handoff should include the command shape, not just the pasted lines. A teammate needs to know whether the excerpt came from the current instance, the previous instance, one container, all containers, or a selector across replicas. Two identical error messages can imply different fixes depending on whether one pod printed the message before crashing or every pod printed it after a shared dependency failed.

If you later discover that the first command answered the wrong scope, say that explicitly in the investigation notes. "These lines came from the sidecar, not the app container" is a useful correction because it prevents the next engineer from building on a false premise. Logging discipline is partly technical and partly conversational: the stream you read, the window you chose, and the evidence you preserved all become part of the debugging record.

```bash
# Essential commands
kubectl logs POD                      # Basic logs
kubectl logs POD -f                   # Follow/stream
kubectl logs POD --tail=100           # Last 100 lines
kubectl logs POD --since=1h           # Last hour
kubectl logs POD -c CONTAINER         # Specific container
kubectl logs POD --previous           # Previous instance
kubectl logs POD --all-containers=true # All containers
kubectl logs -l app=myapp             # By label
kubectl logs POD --timestamps         # With timestamps
```

That sequence gives you a reusable debugging shape: identify the workload, choose the container stream, bound the time or size, inspect the previous instance when restarts are involved, and only then broaden to labels or exports. It avoids the two extremes that waste time, which are staring at one healthy pod while another pod fails, and dumping every log line from every replica without a clear question.

## Patterns & Anti-Patterns

Container logging patterns are small decisions repeated across many services. The right pattern preserves the application signal, keeps `kubectl logs` useful during immediate debugging, and leaves room for a central logging backend to do the durable work. The wrong pattern usually starts as convenience, such as "write a local file because the framework already does that," and later becomes an outage problem when nobody can retrieve the evidence quickly.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Application writes one event per line to stdout/stderr | New or changeable services | Kubelet, `kubectl logs`, and node collectors all see the same stream | Standardize field names before many teams depend on queries |
| `--tail`, `--since`, and `--timestamps` for first response | Any noisy pod or replica set | The command answers a bounded question instead of flooding the terminal | Pair timestamps with labels when comparing replicas |
| `-c` for named containers and `--all-containers=true` for survey mode | Sidecar, proxy, metrics, and init-container pods | You choose between a clean stream and a quick pod-wide scan | Prefix or timestamps become important when streams are mixed |
| Sidecar streams a legacy file to stdout | Software cannot be changed immediately | Kubernetes can collect the sidecar stream without node shell access | Treat this as a migration bridge, not a default design |

The main anti-pattern is using `kubectl logs` as if it were durable storage. It is excellent for immediate inspection, but it is bounded by local node log lifecycle and container restarts. A cluster-level backend exists because operational questions often arrive after the pod moved, the node rotated files, or the short previous-container window disappeared.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Application writes only to `/var/log/app.log` inside the container | `kubectl logs` and node collectors miss the application signal | Write to stdout/stderr or add a temporary streaming sidecar |
| Starting every investigation with unbounded logs | Large output hides the relevant line and slows the operator | Start with `--tail`, `--since`, or both |
| Reading a multi-container pod without naming the container | Kubernetes rejects the command or you inspect the wrong stream | List container names and use `-c`, then use `--all-containers=true` only when intentional |
| Deleting a crashing pod before reading previous logs | The local evidence may disappear with the old container lifecycle | Capture `kubectl logs --previous` before recreation or rollout changes |

## Decision Framework

Choose the logging approach by matching the question to the scope of evidence. A single current pod needs a direct snapshot, a recent crash needs the previous instance, a scaled Deployment needs a selector, and an audit or trend question needs centralized logging. The command is only "right" when it matches the lifecycle and scope of the evidence you need.

| Question | First Tool | Add This When Needed | Stop and Escalate When |
|----------|------------|----------------------|------------------------|
| What is this one container doing now? | `kubectl logs pod-name` | `-c`, `--tail`, `--timestamps` | The pod has multiple containers or the output is empty |
| What did the container print before it crashed? | `kubectl logs pod-name --previous` | `-c container-name` | The pod restarted many times and older evidence is gone |
| Are all replicas showing the same error? | `kubectl logs -l app=name --since=30m` | `--tail`, `--timestamps`, `--max-log-requests` | The selector matches too much noise or misses known pods |
| Do I need a durable incident record? | Central logging backend | Query by service, level, request ID, and time range | The backend lacks the fields needed for reliable search |
| Can Kubernetes see a legacy application's file logs? | Application change or streaming sidecar | Shared volume plus sidecar stdout stream | The sidecar becomes permanent operational debt |

For CKAD, prefer the simplest command that proves the point. The exam rewards correct resource selection and fast troubleshooting, not elaborate pipelines. If a pod has one container, read it directly. If it has two containers, name the container. If it crashed, use `--previous`. If the workload has replicas, use the label selector only after you understand what label selects the intended pods.

For production, the framework has a second layer: decide whether the information should still exist tomorrow. `kubectl logs` is a live troubleshooting interface, while a logging backend is an observability system with retention, search, access control, and correlation. When the answer may be needed by another team, by an incident review, or by a compliance process, capture it through the durable path instead of relying on the node's local lifecycle.

## Did You Know?

- Kubernetes logging architecture documentation states that cluster-level logging requires a separate backend because Kubernetes does not provide a native storage solution for log data.
- The kubelet log rotation settings include `containerLogMaxSize`, which defaults to `10Mi`, and `containerLogMaxFiles`, which defaults to `5` in the documented kubelet configuration behavior.
- The generated `kubectl logs` reference lists `--max-log-requests` with a default of `5` concurrent requests when following logs selected by a label.
- Native sidecar containers became active by default in Kubernetes v1.29, and Kubernetes v1.35 clusters can still use ordinary multi-container sidecar patterns for logging workflows.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Forgetting `-c` for multi-container pods | The pod name feels specific enough, but Kubernetes stores one log stream per container | Run `kubectl get pod POD -o jsonpath='{.spec.containers[*].name}'`, then use `kubectl logs POD -c CONTAINER` |
| Looking for logs from deleted pods | Local pod and container log lifecycle is shorter than production investigation timelines | Check `--previous` before deletion, and rely on cluster-level logging for durable retention |
| App logging to files, not stdout | Many frameworks default to file appenders inherited from VM-style deployments | Configure stdout/stderr logging, or use a temporary sidecar that tails the file to stdout |
| Not using `--tail` for large logs | The first command is copied from a simple example and returns too much history | Start with `--tail=100`, then widen the window only if the clue is missing |
| Ignoring init container logs | The application container never starts, so app logs are empty or irrelevant | Inspect init container names and run `kubectl logs POD -c INIT_CONTAINER` |
| Following selector logs without raising request limits | A scaled Deployment can exceed the default concurrent follow behavior | Use `--max-log-requests` deliberately and confirm the selector matches every intended pod |
| Grepping too early | Filtering hides context that explains why an error line appeared | Read a bounded timestamped snapshot first, then grep for a known pattern |
| Treating `kubectl logs` as long-term storage | It is convenient during an incident and feels like the logging system | Use a central backend for retention, search, alerting, and post-incident analysis |

## Quiz

<details><summary>Question 1: Your `checkout` pod has restarted twice. `kubectl logs checkout` shows only a clean startup message from the current instance, but you need the error that caused the last exit. What command do you run, and why?</summary>

Run `kubectl logs checkout --previous`, adding `-c CONTAINER` if the pod has more than one container. The normal command reads the current container instance, which may have started after the failure. `--previous` asks for the immediately prior terminated instance, so it is the right first response for a recent crash. It will not recover an unlimited restart history, which is why production systems need central log retention.

</details>

<details><summary>Question 2: A developer says `kubectl logs my-pod` returns an error that a container name must be specified. The pod is Running and has no restarts. What is the likely pod shape, and how should the developer proceed?</summary>

The pod almost certainly has multiple regular containers, such as an app container plus a sidecar. Kubernetes cannot infer which stdout or stderr stream the developer wants, so the developer should list container names with JSONPath and rerun the command with `-c container-name`. If the goal is only a quick survey, `--all-containers=true` is acceptable, but it mixes streams and should not replace precise selection during diagnosis.

</details>

<details><summary>Question 3: Your team deployed eight `checkout` replicas with label `app=checkout`, and errors began during the last half hour. You need a bounded view across replicas without flooding your terminal. What command shape should you choose?</summary>

Use a label selector with a time bound and a line bound, for example `kubectl logs -l app=checkout --since=30m --tail=100 --timestamps`. If you follow the logs live, consider `--max-log-requests` because selector-based following has a default concurrency limit. The selector answers the replica-scope question, while the time and tail filters keep the output small enough to reason about. Timestamps help correlate lines across different pods.

</details>

<details><summary>Question 4: An application writes to `/var/log/app.log` inside the container, and `kubectl logs` is empty even though the file is growing. What is wrong with the logging pattern, and what are two practical fixes?</summary>

`kubectl logs` reads stdout and stderr streams exposed through the kubelet path; it does not inspect arbitrary private files inside the container filesystem. The preferred fix is to configure the application to write structured events to stdout and stderr. If the application cannot be changed immediately, a sidecar can read the shared log file and write the lines to its own stdout. The sidecar bridge should be treated as a migration aid because it adds another moving part.

</details>

<details><summary>Question 5: A pod uses an init container named `init-setup` to prepare configuration, but the application container never starts. Reading `kubectl logs init-demo -c app` gives no clue. What should you check next?</summary>

Check the init container stream with `kubectl logs init-demo -c init-setup`. Init containers run before regular containers, so a setup failure can block the app from ever producing logs. This is not a previous-instance problem unless a specific container restarted; it is a container-selection problem. If the init container repeatedly fails, its output is the first place to look for missing configuration, DNS failures, or permission errors.

</details>

<details><summary>Question 6: During an incident, someone proposes deleting the crashing pod and waiting for the Deployment to create a clean replacement before looking at logs. How do you evaluate that proposal?</summary>

That proposal risks destroying the most useful local evidence. A Deployment replacement may restore service, but the previous container logs should be captured first with `kubectl logs POD --previous`, including `-c` when the pod has multiple containers. If service restoration is urgent, another engineer can capture logs while the rollout action proceeds. Long-term, the team should verify that a central backend already collected the relevant time window.

</details>

<details><summary>Question 7: You need to decide between `kubectl logs`, exporting a local file, and querying a logging backend for a customer-impacting issue reported yesterday. Which tool should lead, and why?</summary>

The logging backend should lead because the question is historical and may outlive the node or pod that originally produced the log lines. `kubectl logs` is still useful if the pod is running and you need a quick current comparison, but it is not a durable archive. Exporting a local file can preserve a small excerpt during live work, yet it should not become the authoritative incident record. The backend is the right system for retention, access control, and cross-replica queries.

</details>

## Hands-On Exercise

Exercise scenario: you will create several small pods that generate useful, boring, and failing logs, then practice choosing the right command for each situation. The goal is not to memorize a wall of flags. The goal is to build the habit of asking three questions before every command: which pod or selector, which container stream, and which time or size boundary.

Use a disposable namespace if your lab environment allows it, or run these resources in a temporary practice cluster. The manifests use BusyBox and nginx because they start quickly and keep the focus on log behavior rather than application code. Read each task before running the commands, predict the output you expect, and then compare the actual output with that prediction.

**Setup:**
```bash
# Create a pod that generates logs
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: log-demo
  labels:
    app: log-demo
spec:
  containers:
  - name: logger
    image: busybox
    command: ['sh', '-c', 'i=0; while true; do echo "$(date) - Log entry $i"; i=$((i+1)); sleep 2; done']
EOF

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/log-demo --timeout=30s
```

Task 1 is the baseline. Read a snapshot, follow the stream briefly, stop the follow with Ctrl+C, and then ask for only the last few lines with timestamps. You should notice that the application timestamp printed by BusyBox and the Kubernetes timestamp added by `--timestamps` are related but not identical pieces of information.

**Part 1: Basic Logs**
```bash
# View logs
kubectl logs log-demo

# Follow logs (Ctrl+C to stop)
kubectl logs log-demo -f

# Last 5 lines
kubectl logs log-demo --tail=5

# With timestamps
kubectl logs log-demo --timestamps --tail=5
```

<details><summary>Solution notes for Task 1</summary>

The first command should show the accumulated output from the single `logger` container. The follow command should continue printing new lines until you interrupt it. The `--tail=5` command should reduce the output to five recent lines, and the timestamped command should add Kubernetes timestamps before each line. If any command is empty, check whether the pod is ready and whether the BusyBox command is still running.

</details>

Task 2 adds a second stream. The nginx container may not print much during this simple lab, while the sidecar prints regular messages. That difference is useful because it forces you to separate "the pod is quiet" from "the container I selected is quiet." Use the JSONPath command to list names before reading each stream.

**Part 2: Multi-Container**
```bash
# Create multi-container pod
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: multi-log
spec:
  containers:
  - name: app
    image: nginx
  - name: sidecar
    image: busybox
    command: ['sh', '-c', 'while true; do echo Sidecar log; sleep 5; done']
EOF

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/multi-log --timeout=30s

# List containers
kubectl get pod multi-log -o jsonpath='{.spec.containers[*].name}'

# View each container
kubectl logs multi-log -c app
kubectl logs multi-log -c sidecar

# All containers
kubectl logs multi-log --all-containers=true
```

<details><summary>Solution notes for Task 2</summary>

The JSONPath output should include `app` and `sidecar`. Reading the `sidecar` container should show repeated "Sidecar log" lines, while the nginx app container may have little or no output until it handles requests. `--all-containers=true` is useful for a quick survey, but a focused investigation should return to `-c` so one stream does not obscure another.

</details>

Task 3 demonstrates why current logs and previous logs answer different questions. The pod exits with a failure and is restarted by Kubernetes according to its pod restart policy. You will wait for at least one restart, confirm the pod state, and then inspect the previous instance for the lines printed before the exit.

**Part 3: Previous Instance**
```bash
# Create pod that crashes
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crasher
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'echo "Starting..."; echo "About to crash!"; exit 1']
EOF

# Wait until the container has restarted at least once, then check previous logs
until [ "$(kubectl get pod crasher -o jsonpath='{.status.containerStatuses[0].restartCount}')" -ge 1 ]; do sleep 2; done
kubectl get pod crasher
kubectl logs crasher --previous
```

<details><summary>Solution notes for Task 3</summary>

After the restart, the pod should show evidence of failure or repeated starts, depending on timing. The previous logs should include "Starting..." and "About to crash!" from the terminated instance. If you run `--previous` before `restartCount` reaches 1, Kubernetes 1.35 returns an empty or error response; poll restart count instead of relying on a fixed sleep. This is the same habit you need for CrashLoopBackOff triage.

</details>

Task 4 is cleanup for the setup resources. Deleting the pods at the end keeps later drills predictable and prevents old labels from matching selector commands. In a real investigation you would capture needed evidence before deletion; in this lab the evidence is intentionally disposable.

**Cleanup:**
```bash
kubectl delete pod log-demo multi-log crasher
```

<details><summary>Solution notes for cleanup</summary>

The delete command should remove the three pods created by the setup tasks. If one pod was already removed or still terminating, Kubernetes may report that state, which is acceptable in a practice environment. Confirm with `kubectl get pods` if you want a clean workspace before starting the drills.

</details>

The following drills preserve the same scenarios in shorter form so you can build speed. Treat the target times as practice pacing, not as a pass-fail measure. The real exam skill is choosing the command without hesitation, then verifying that the output answers the question you meant to ask.

### Drill 1: Basic Logs (Target: 1 minute)

This drill checks the simplest path: create a single-container pod, wait for readiness, read logs, and clean up. The important observation is that a quiet container is not automatically a broken command. nginx may not emit many lines until it serves traffic, so your job is to verify the pod and understand the application's logging behavior.

```bash
# Create pod
kubectl run drill1 --image=nginx

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/drill1 --timeout=30s

# View logs
kubectl logs drill1

# Cleanup
kubectl delete pod drill1
```

### Drill 2: Follow Logs (Target: 2 minutes)

This drill creates a container that prints a steady heartbeat. Use follow mode long enough to prove that the stream is live, then interrupt it and delete the pod. If you forget to interrupt the stream, the terminal is not stuck; it is doing exactly what `-f` requested.

```bash
# Create logging pod
kubectl run drill2 --image=busybox -- sh -c 'while true; do echo tick; sleep 1; done'

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/drill2 --timeout=30s

# Follow (Ctrl+C after a few ticks)
kubectl logs drill2 -f

# Cleanup
kubectl delete pod drill2
```

### Drill 3: Multi-Container (Target: 3 minutes)

This drill repeats the sidecar selection pattern without the longer explanation. Predict which stream will be noisy before you read it. Then use the app and monitor names explicitly so the command remains clear even if another container is added later.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: drill3
spec:
  containers:
  - name: web
    image: nginx
  - name: monitor
    image: busybox
    command: ['sh', '-c', 'while true; do echo monitoring; sleep 5; done']
EOF

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/drill3 --timeout=30s

# Get logs from each
kubectl logs drill3 -c web
kubectl logs drill3 -c monitor

# Cleanup
kubectl delete pod drill3
```

### Drill 4: Label Selection (Target: 2 minutes)

This drill uses labels to select more than one pod. The nginx pods may not produce interesting application logs, but the selector still teaches the grouping behavior. In a real workload, the same pattern lets you move from a generated pod name to a workload-wide question.

```bash
# Create multiple pods
kubectl run drill4a --image=nginx -l app=drill4
kubectl run drill4b --image=nginx -l app=drill4

# Wait for pods to be ready
kubectl wait --for=condition=Ready pod -l app=drill4 --timeout=30s

# Logs from all with label
kubectl logs -l app=drill4

# Cleanup
kubectl delete pod -l app=drill4
```

### Drill 5: Previous Instance (Target: 3 minutes)

This drill reinforces the previous-instance muscle memory. The container prints a line, sleeps briefly, and exits with failure. Poll until `restartCount` is at least 1, inspect the pod, and then read the previous logs rather than the current fresh attempt. If `--previous` is unavailable on a very fast crash, fall back to `kubectl logs drill5` (current) before the next restart erases the evidence.

```bash
# Create crashing pod
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: drill5
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'echo "Run at $(date)"; sleep 5; exit 1']
EOF

# Wait until the container has restarted at least once
until [ "$(kubectl get pod drill5 -o jsonpath='{.status.containerStatuses[0].restartCount}')" -ge 1 ]; do sleep 2; done
kubectl get pod drill5

# After restart, get previous logs
kubectl logs drill5 --previous

# Cleanup
kubectl delete pod drill5
```

### Drill 6: Complete Logging Scenario (Target: 4 minutes)

This drill combines Deployment pods, label selection, and previous logs. The Deployment creates two failing replicas, so a selector can show the recent error pattern across the workload, while a specific pod name lets you read a previous instance. Use both because they answer different questions.

```bash
# Create "broken" deployment
cat << 'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drill6
spec:
  replicas: 2
  selector:
    matchLabels:
      app: drill6
  template:
    metadata:
      labels:
        app: drill6
    spec:
      containers:
      - name: app
        image: busybox
        command: ['sh', '-c', 'echo "Starting app"; echo "ERROR: Database connection failed"; exit 1']
EOF

# Wait for pods to be created
sleep 5

# Find pods
kubectl get pods -l app=drill6

# Check logs from one pod
kubectl logs -l app=drill6 --tail=10

# Get previous instance logs
POD=$(kubectl get pods -l app=drill6 -o jsonpath='{.items[0].metadata.name}')
until [ "$(kubectl get pod "$POD" -o jsonpath='{.status.containerStatuses[0].restartCount}')" -ge 1 ]; do sleep 2; done
kubectl logs "$POD" --previous

# Cleanup
kubectl delete deploy drill6
```

Your success criteria are practical. You should be able to run each command, explain why it targets the right stream, and describe what evidence would disappear if you deleted the pod too early.

- [ ] I can read current logs from a single-container pod with `kubectl logs`.
- [ ] I can limit log output by line count, time window, and timestamps.
- [ ] I can list container names and read one selected stream from a multi-container pod.
- [ ] I can retrieve previous logs from a restarted container before deleting the pod.
- [ ] I can use a label selector to inspect logs across related pods.
- [ ] I can explain when a central logging backend is required instead of relying on local `kubectl logs`.

## Learner check

> If you run `--previous` before `restartCount` reaches 1, Kubernetes 1.35 returns an empty or error response; poll restart count instead of relying on a fixed sleep.

Before you move on, explain why the restart-count poll is more reliable than `sleep 15` when a pod is in `CrashLoopBackOff`, and when you would read current-instance logs instead of waiting for `--previous`.

## Sources

- [Kubernetes Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [kubectl logs reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)
- [kubectl command reference](https://kubernetes.io/docs/reference/kubectl/generated/)
- [Kubernetes Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod)
- [Kubernetes Troubleshooting Applications](https://kubernetes.io/docs/tasks/debug/debug-application/)
- [Kubernetes Pods](https://kubernetes.io/docs/concepts/workloads/pods/)
- [Kubernetes Init Containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [Kubernetes Sidecar Containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [Kubernetes Labels and Selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/)
- [Kubernetes Workloads](https://kubernetes.io/docs/concepts/workloads/)
- [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

## Next Module

[Module 3.3: Debugging in Kubernetes](../module-3.3-debugging/) - Troubleshoot pods, containers, and cluster issues.
