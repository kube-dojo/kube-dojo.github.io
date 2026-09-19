---
citations_verified: true
title: "Part 0 Cumulative Quiz: Environment & Exam Technique"
sidebar:
  order: 6
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45-60 minutes
>
> **Prerequisites**: Part 0.1 Cluster Setup, Part 0.2 Shell Mastery, Part 0.3 Vim for YAML, Part 0.4 Documentation Navigation, Part 0.5 Exam Strategy
>
> **Kubernetes Version**: 1.35+

---

## Learning Outcomes

- **Evaluate** whether a Kubernetes exam environment is ready before attempting scored tasks, using context checks, namespace checks, shell helpers, and quick validation commands.
- **Debug** common setup failures in local clusters and exam terminals, including missing schedulers, broken kubeconfig context, malformed YAML, and command output that does not match the task requirement.
- **Design** a repeatable question workflow that starts with context safety, chooses the right generation or documentation strategy, edits manifests efficiently, and verifies results before moving on.
- **Compare** fast command-line approaches against documentation-driven approaches, choosing the one that reduces risk under exam time pressure instead of choosing commands from memory alone.
- **Apply** the three-pass exam method to mixed task sets, deciding which tasks to complete immediately, which to defer, and which evidence proves that a task is genuinely complete.

---

## Why This Module Matters

A candidate can understand Pods, Deployments, Services, and scheduling perfectly and still lose the exam in the first few minutes because the working context is wrong. Hypothetical scenario: one engineer in a practice cohort created every resource in the wrong cluster during a mock exam because the terminal prompt looked familiar and the first task felt easy. The commands were syntactically correct, the YAML was valid, and the troubleshooting was competent, but the work produced no score because it landed in the wrong place.

This module treats Part 0 as a professional operating routine rather than a collection of setup trivia. The CKA environment rewards people who can keep a narrow loop: read the task, check the target, create or inspect the right object, verify the result, then move on. The difficulty is not only Kubernetes knowledge; it is the ability to preserve accuracy while the clock is running and while the browser, terminal, editor, and documentation all compete for attention.

The cumulative quiz at the end is still important, but it is no longer the whole lesson. Before you answer scenario questions, you will rehearse the mental model that connects cluster setup, shell aliases, Vim editing, documentation navigation, and pass-based exam triage. Senior practitioners use the same pattern during incidents: establish the target, make the smallest safe change, observe the system, and avoid turning uncertainty into broad, unverified edits.

The exam does not require theatrical speed. It requires repeatable control. A slow first command that confirms the correct context is faster than ten confident commands executed against the wrong cluster, and a short documentation lookup is faster than debugging a manifest generated from a half-remembered API field. This module teaches you to make those trade-offs deliberately.

---

## Core Content: The Exam Loop Is a Control System

The safest way to think about an exam question is as a small control loop. You observe the target state, choose the narrowest action, apply it in the correct cluster and namespace, then compare the actual state with the task requirement. If the state matches, you stop; if it does not, you gather a more specific signal instead of repeating the same command louder.

A useful exam loop has five gates: target, plan, create or repair, verify, and record confidence. The target gate prevents wrong-cluster and wrong-namespace errors. The plan gate prevents you from turning a simple imperative command into a long YAML editing session. The create-or-repair gate keeps changes narrow. The verify gate proves the resource behaves as required. The confidence gate decides whether you move on or mark the task for a later pass.

```text
+-------------------+     +-------------------+     +-------------------+
|  1. Target Check  | --> |  2. Method Choice | --> |  3. Change State  |
|  context, ns, ask |     |  command, YAML,   |     |  create, patch,   |
|  scoring object   |     |  docs, explain    |     |  edit, delete     |
+-------------------+     +-------------------+     +-------------------+
          ^                         |                         |
          |                         v                         v
+-------------------+     +-------------------+     +-------------------+
|  5. Confidence    | <-- |  4. Verification  | <-- |  System Response  |
|  done, defer, or  |     |  get, describe,   |     |  events, status,  |
|  revisit later    |     |  logs, explain    |     |  errors, output   |
+-------------------+     +-------------------+     +-------------------+
```

The loop matters because exam questions rarely fail in dramatic ways. More often, a resource exists but has the wrong image, a Service selects no Pods, a Deployment rolls out in the wrong namespace, or a static Pod manifest has an indentation error. Each of those failures is easier to catch immediately than after several unrelated commands have changed the cluster.

During Part 0 you learned individual tools: `kubeadm`, kind, the `kubectl` alias, shell variables, Vim settings, `kubectl explain`, Kubernetes documentation, and the three-pass method. In this cumulative module, those tools become one workflow. A tool is exam-ready only when you know where it belongs in the loop and what kind of mistake it prevents.

The first professional habit is to separate action commands from evidence commands. Action commands change the cluster: `create`, `apply`, `patch`, `delete`, `scale`, `cordon`, or editing a static Pod manifest. Evidence commands reduce uncertainty: `get`, `describe`, `logs`, `events`, `auth can-i`, `explain`, and documentation searches. Candidates under pressure often run action commands when they should gather evidence, which creates new symptoms that hide the original issue.

The second professional habit is to keep the verification close to the task wording. If a question asks for three replicas, verification should include `READY` counts or JSONPath output that proves the number. If a question asks for a label selector, verification should prove that selected Pods match the Service or workload. If a question asks for a static Pod repair, verification should inspect the kubelet-managed mirror Pod, not merely the file you edited.

The third professional habit is to avoid treating memory as the primary source of truth. Memorized commands are useful for speed, but the exam allows official documentation because Kubernetes is broad and exact fields matter. A senior operator knows when a command skeleton is safe from memory and when an API field must be confirmed before writing YAML.

**Pause and predict:** Imagine the first exam task asks you to create a Deployment in namespace `app-prod`, but your current context points to a different cluster and your default namespace is `default`. What two checks would catch both hazards before you create anything?

<details>
<summary>Check your prediction</summary>

A practical answer would start with context and namespace visibility rather than resource creation. `k config current-context` catches the cluster target, while `k config view --minify --output 'jsonpath={..namespace}{"\n"}'` or an explicit `-n app-prod` catches namespace drift. Checking only the context proves the cluster, but not the namespace; checking only the namespace can still place the object in the wrong cluster.

</details>

This module uses `k` as the standard alias for `kubectl` after this point. The alias is not magic and does not change Kubernetes behavior. Its value is reducing typing friction so that you spend less time fighting the terminal and more time verifying the requested state.

```bash
alias k=kubectl
complete -o default -F __start_kubectl k
```

A good loop also has a bias toward reversible operations. Generating YAML with `--dry-run=client -o yaml` is safer than manually typing an entire object from memory. Applying a focused manifest is easier to review than a large pasted block. Deleting a broken object may be correct in some tasks, but it should happen because the task or diagnosis justifies it, not because the terminal has become confusing.

The loop is simple enough to memorize, but the discipline is in using it when the question feels easy. Easy questions are where many candidates skip the target gate. Hard questions are where many candidates skip the confidence gate and spend too long chasing a single uncertain symptom.

---

## Core Content: Target Safety Before Speed

Every scored action must happen in the correct Kubernetes context. [A context combines a cluster, a user, and optionally a namespace](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/), and the exam can ask you to switch contexts between questions. Running a perfect command against the wrong context is worse than running no command at all because it consumes time, creates noise, and may make later verification misleading.

The minimum safe start for each question is to read the requested context from the task and switch deliberately. Do not rely on the previous question, the shell prompt, or muscle memory. The command is short, and the cost of skipping it is high.

```bash
k config use-context <context-from-question>
k config current-context
```

After the context, treat the namespace as part of the target. Some tasks state a namespace explicitly, some expect the default namespace, and some provide an existing object that tells you where the work belongs. A safe command uses `-n <namespace>` when the task names one, because explicit namespace flags reduce dependence on hidden terminal state.

```bash
k get ns
k get all -n <namespace-from-question>
```

When a task involves an existing object, inspect that object before changing it. For example, if the task says a Deployment is failing, do not begin by deleting Pods. Start with `get`, `describe`, and possibly `logs`, because they preserve evidence. The goal is to identify whether the failure is an image problem, scheduling problem, probe problem, selector problem, permissions problem, or configuration problem.

```bash
k get deploy -n <namespace>
k describe deploy <name> -n <namespace>
k get pods -n <namespace> -o wide
```

Target safety also applies to file paths on control plane nodes. [Static Pod manifests are read by the kubelet from `/etc/kubernetes/manifests/` on the node](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/), and kubelet turns those files into mirror Pods visible through the API server. Editing the wrong file or moving a manifest out of that directory changes the control plane behavior, so treat static Pod work as a high-risk operation that requires careful verification.

A static Pod problem is not solved when the YAML file looks plausible. It is solved when the kubelet has accepted the manifest and the corresponding mirror Pod returns to a healthy state. That means you should check the file, then check the Pod, then check events if the Pod does not recover.

```bash
sudo ls /etc/kubernetes/manifests/
k get pods -n kube-system
k describe pod <control-plane-pod-name> -n kube-system
```

For local practice, kind is useful because it gives you a disposable cluster that behaves enough like Kubernetes to practice workflows. kind uses a lightweight default networking setup suitable for local development, while kubeadm exposes the control plane bootstrap path more directly. You do not need to become a kind internals expert for CKA, but you should understand which environment you are using and which assumptions follow from it.

A common beginner mistake is to confuse cluster creation tools with cluster operation tools. `kubeadm init` creates a control plane on a node; `kubectl` talks to an API server described by kubeconfig; kind creates local clusters in containers; Vim edits files. During the exam, you usually operate an existing cluster rather than bootstrap one from scratch, so cluster setup knowledge is mostly valuable for diagnosing how control plane pieces fit together.

The following comparison is less about memorizing tools and more about choosing the right layer when diagnosing a problem. If the API server is unreachable, `kubectl` commands may not be enough. If a Deployment is misconfigured, restarting kubelet is almost certainly the wrong layer. Good operators choose the layer that matches the symptom.

| Situation | Best Starting Layer | Why This Layer Fits | First Evidence Command |
|---|---|---|---|
| New Pods stay Pending while existing Pods run | Scheduler and Pod constraints | The API works, but placement is not happening or cannot happen | `k describe pod <pod> -n <ns>` |
| API server is unreachable from kubectl | Kubeconfig, API server, or node service | Client commands cannot confirm workload state until connectivity returns | `k cluster-info` |
| Static control plane Pod disappears | Kubelet manifest directory | Static Pod lifecycle depends on local files watched by kubelet | `sudo ls /etc/kubernetes/manifests/` |
| Service has no endpoints | Labels and selectors | The Service exists, but it may not match the intended Pods | `k get endpoints -n <ns>` |
| YAML apply fails with schema error | Manifest structure and API fields | The cluster rejected the object before runtime behavior matters | `k explain <resource>.<field>` |

Notice that each row pairs a symptom with evidence rather than a memorized fix. This is the difference between an exam candidate who guesses and an operator who diagnoses. Under time pressure, diagnosis does not have to be long, but it must be specific enough to avoid damaging changes.

When you practice, deliberately say the target out loud or write it in a scratch note: context, namespace, resource, expected state. This habit can feel slow at first, but it compresses into a few seconds after repetition. The benefit is that every later command has a clear anchor.

A reliable target statement might sound like this: "In context `cluster-a`, namespace `web`, Deployment `frontend` must run three ready replicas with image `nginx:1.35` and expose port eighty through a ClusterIP Service." That sentence gives you enough information to choose commands, generate YAML, and verify readiness without rereading the full prompt repeatedly.

---

## Core Content: Command Generation, YAML Editing, and Documentation

Fast Kubernetes work depends on using the command line to produce correct starting points. [Generating YAML with `--dry-run=client -o yaml`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_deployment/) lets you avoid many indentation and API-shape mistakes, especially for common objects such as Pods, Deployments, Services, Jobs, ConfigMaps, and Secrets. The generated manifest is not always the final answer, but it is a safer skeleton than hand-writing every field.

Many learners define a shell helper named `do` for dry-run output during practice. If your shell supports it, a variable such as `do="--dry-run=client -o yaml"` can make generation faster, but you should understand the expanded command before relying on it. In the exam, a helper that you cannot explain becomes another source of risk.

```bash
do="--dry-run=client -o yaml"
k create deploy web --image=nginx:1.35 --replicas=3 $do > web-deploy.yaml
```

The generated YAML still needs review. For example, a Deployment generated from the command line may not include probes, resource requests, custom labels, or environment variables required by the task. The value of generation is that it gives you valid structure and common defaults, not that it reads the question for you.

Before editing YAML, configure Vim for Kubernetes-friendly indentation. YAML uses spaces, not tabs, and Kubernetes manifests are deeply sensitive to indentation because parent-child relationships carry meaning. A single misplaced field can turn a valid-looking file into an object that is rejected or accepted with the wrong behavior.

```bash
cat > ~/.vimrc <<'EOF'
set tabstop=2
set shiftwidth=2
set expandtab
set number
set ruler
EOF
```

The most important Vim skill is not an obscure shortcut. It is the ability to make small, controlled edits while preserving indentation. You need to insert fields at the correct level, duplicate nearby lines safely, delete wrong sections, and save quickly. Commands like `dd`, `yy`, `p`, `u`, `:w`, and `:q!` matter because they keep your attention on the manifest rather than the editor.

If pasted YAML becomes misindented, use paste mode before the next paste and turn it off afterward. Paste mode prevents Vim autoindent from trying to "help" in ways that damage copied manifests. This is a practical example of environment technique directly protecting Kubernetes correctness.

```bash
:set paste
:set nopaste
```

[The exam allows official documentation](https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed) because nobody should memorize every API field. Use `kubectl explain` when you need the shape of a resource from the cluster itself, and use Kubernetes documentation when you need examples, task flows, or conceptual reminders. The skill is choosing the smaller lookup that answers the question.

```bash
k explain deployment.spec.strategy
k explain pod.spec.containers.readinessProbe
```

For field-level uncertainty, `kubectl explain` is usually faster than opening a browser. It gives the resource path, field type, and description from the cluster's OpenAPI schema. For multi-step tasks such as configuring a probe, creating a NetworkPolicy, or checking Gateway API examples, the documentation site often provides better runnable examples.

Documentation navigation is not a detour from exam work. It is part of the work when the task involves exact syntax. The danger is unbounded browsing, where you search broadly, open several pages, and lose the thread of the question. A bounded lookup starts with a specific missing piece, finds it, applies it, and returns to verification. This is where you compare fast command-line approaches with documentation-driven approaches by asking which one reduces risk for the exact field or example you need.

**Pause and predict:** You need to add a readiness probe to a Deployment, but you remember only that the field belongs somewhere under `containers`. Choose `k explain`, official documentation, or both before reading the reasoning.

<details>
<summary>Check your prediction</summary>

A good choice is to start with `k explain pod.spec.containers.readinessProbe` or the equivalent Deployment template path if you need field structure quickly. If you also need a complete example with HTTP path and port values, the official documentation is useful after the field path is confirmed. This two-step approach prevents both vague browsing and blind YAML editing.

</details>

A worked example makes the pattern concrete. Suppose a task says: "In namespace `web`, create a Deployment named `portal` with three replicas using image `nginx:1.35`, then expose it on port eighty inside the cluster." A rushed candidate may type several commands from memory and assume success. A controlled candidate generates, applies, exposes, and verifies selectors and endpoints.

```bash
k config use-context <task-context>
k create ns web
k create deploy portal --image=nginx:1.35 --replicas=3 -n web
k expose deploy portal --port=80 --target-port=80 -n web
k rollout status deploy/portal -n web
k get deploy,svc,endpoints -n web
```

The verification is not decorative. `rollout status` proves the Deployment controller reached the desired state, while `get deploy,svc,endpoints` shows whether the Service has endpoints. If endpoints are empty, the Service may have the wrong selector, the Pods may not be Ready, or the Pods may not exist in the namespace you expected.

Now consider a similar task that requires a label `tier=frontend` on the Pod template and a Service selecting that label. In that case, exposing the Deployment immediately may not be enough, because the generated selector may follow the Deployment's default labels rather than the task's requested selector. You would generate or edit YAML, [confirm labels under both `spec.selector.matchLabels` and `spec.template.metadata.labels`](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), then apply and verify endpoints.

The senior-level habit is to connect every generated command to the resource model. A Deployment owns ReplicaSets, ReplicaSets create Pods, Services select Pods through labels, and readiness affects whether endpoints are populated. When verification fails, that model tells you where to look next.

```text
+---------------------+       owns        +---------------------+       creates      +---------------------+
| Deployment portal   | ----------------> | ReplicaSet revision | ----------------> | Pods with labels    |
| desired replicas=3  |                   | selector matches    |                   | app=portal          |
+---------------------+                   +---------------------+                   +---------------------+
                                                                                              |
                                                                                              | selected by labels
                                                                                              v
                                                                                  +---------------------+
                                                                                  | Service portal      |
                                                                                  | endpoints populated |
                                                                                  +---------------------+
```

If a Service has no endpoints, do not recreate the cluster or restart random Pods. Compare the Service selector with the Pod labels. This is a Level 4 diagnostic move because it analyzes the relationship between resources rather than recalling a command.

```bash
k get svc portal -n web -o yaml
k get pods -n web --show-labels
k get endpoints portal -n web -o wide
```

This is also where documentation can prevent overcorrection. A Service selector is not a free-form query language; it is a map of label keys and values that must match Pod labels. If the selector says `tier: frontend`, the Pod must carry `tier=frontend` at the Pod template level, not merely on the Deployment metadata.

The same principle applies to probes, resource requests, tolerations, node selectors, volumes, and environment variables. YAML location matters because Kubernetes controllers read specific fields. A value in the wrong section may be ignored, rejected, or applied to the wrong object.

---

## Core Content: Worked Troubleshooting Example

Troubleshooting tasks are often where exam performance separates recall from competence. A scenario may say that Pods are not starting, but that phrase can mean image pull failures, scheduling constraints, missing ConfigMaps, invalid commands, broken probes, insufficient permissions, or a disabled scheduler. The right response is not to try every fix; it is to collect enough evidence to classify the failure.

Start with the broadest cheap signal: resource status. The `get` command shows phase, readiness, restarts, age, node placement, and sometimes obvious error states. It does not explain everything, but it tells you which next evidence command is worth running.

```bash
k get pods -n <namespace> -o wide
```

If the Pod is Pending, the next command is usually `describe pod` because scheduling failures appear as events. If the Pod is Running but not Ready, inspect readiness probes, container states, and logs. If the Pod is CrashLoopBackOff, logs and previous logs matter. If the Pod does not exist, inspect the controller that should have created it.

```bash
k describe pod <pod-name> -n <namespace>
k logs <pod-name> -n <namespace>
k logs <pod-name> -n <namespace> --previous
```

Here is a worked example. The task says: "In namespace `orders`, fix the Deployment `api` so that it becomes available. Do not change the requested image unless the image is the cause." The candidate first confirms target, then inspects Deployment and Pods.

```bash
k config use-context <task-context>
k get deploy api -n orders
k get pods -n orders -o wide
k describe pod <api-pod-name> -n orders
```

The Pod event shows `Readiness probe failed: HTTP probe failed with statuscode: 404`. That means the container is running, scheduling succeeded, and the image is probably not the first suspect. The failure is in the readiness probe path, port, or application behavior. A reckless fix would delete the Deployment or change the image. A focused fix checks the probe fields.

```bash
k get deploy api -n orders -o yaml > api.yaml
```

Assume the manifest contains this relevant section. The path is `/healthz`, but the application exposes `/ready` according to the task note or logs. The correct edit is narrow: update the readiness probe path and reapply.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: orders
spec:
  template:
    spec:
      containers:
        - name: api
          image: registry.k8s.io/e2e-test-images/agnhost:2.55
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
```

After editing, verification must prove the Deployment becomes available, not just that `kubectl apply` succeeded. Applying a manifest only proves that the API server accepted the object. The controller still has to roll out Pods, probes still have to pass, and status still has to converge.

```bash
k apply -f api.yaml
k rollout status deploy/api -n orders
k get deploy api -n orders
k get pods -n orders
```

This example demonstrates an important senior-level pattern: identify the subsystem that is already working so you do not disturb it. Scheduling worked, so node selection was not the issue. The container ran, so the image and command were not the first issue. Readiness failed, so the fix targeted readiness. Good troubleshooting narrows the blast radius.

Now compare that with a static Pod scenario. If the task says the scheduler is not running on a control plane node and new Pods remain Pending, the evidence path changes. You inspect system namespace Pods and the manifest directory rather than editing a workload Deployment.

```bash
k get pods -n kube-system
sudo ls /etc/kubernetes/manifests/
sudo sed -n '1,160p' /etc/kubernetes/manifests/kube-scheduler.yaml
```

If the scheduler manifest is missing, the kubelet cannot create the static scheduler Pod from that file. In a practice cluster, restoring the manifest from a backup or correcting its filename may recover scheduling. In an exam task, follow the provided environment and task constraints carefully, because control plane repair questions can have narrow expected changes.

The practical diagnostic question is: "Which controller or agent is responsible for the missing behavior?" If Pods are not being placed on nodes, the scheduler is involved. If a Deployment is not creating Pods, the Deployment controller and ReplicaSet chain are involved. If a static Pod does not appear, kubelet and the manifest directory are involved. If Service traffic fails, selectors, endpoints, readiness, and networking are involved.

**Pause and predict:** A Pod is `Running` but the Service has no endpoints. Before reading the answer, choose the first two resource relationships you would inspect to explain the symptom.

<details>
<summary>Check your prediction</summary>

The first relationship is Service selector to Pod labels, because endpoints depend on matching Ready Pods. The second relationship is Pod readiness to endpoint publication, because a matching Pod may still be excluded if it is not Ready. Commands follow from those relationships: inspect `svc -o yaml`, `pods --show-labels`, `endpoints`, and Pod readiness details.

</details>

```bash
k get svc <service> -n <namespace> -o yaml
k get pods -n <namespace> --show-labels
k get endpoints <service> -n <namespace> -o wide
k describe pod <pod> -n <namespace>
```

This style of troubleshooting is slower only while you are learning it. With practice, it becomes faster than trial and error because each command either confirms or eliminates a specific hypothesis. That is the difference between navigating a system and poking at it.

---

## Core Content: Exam Strategy Under Time Pressure

The three-pass method exists because not all questions have the same uncertainty. Quick tasks should be completed early because they provide score with low investigation cost. Medium tasks deserve focused work once quick wins are secured. Complex troubleshooting or multi-resource tasks may require deferral so they do not consume the time needed for easier points.

Pass one is for tasks that you can complete and verify in a few minutes with high confidence. Examples include creating a simple namespace, scaling a Deployment, exposing a Deployment when labels are straightforward, or generating a basic resource from a command. The key is not that the task looks familiar; the key is that the verification path is short.

Pass two is for tasks that need editing, documentation lookup, or two or three connected resources. Examples include adding probes, creating a Job with a specific command, configuring a ConfigMap volume, or adjusting labels and selectors. These tasks are still manageable, but they require more careful reading and verification.

Pass three is for tasks with open-ended diagnosis, control plane symptoms, node-level work, or uncertain failure modes. A question that says "troubleshoot why Pods are not starting" may become simple after evidence, but it begins with unknown scope. Marking it for pass three is not avoidance; it is time management.

A useful rule is to spend the first minute classifying the task rather than solving it blindly. If you can name the target resource, generation method, and verification command immediately, it is probably pass one. If you need a manifest edit or a documentation lookup, it is probably pass two. If you cannot yet name the failing layer, it belongs in pass three until evidence makes it smaller.

Scoring pressure can tempt candidates into partial work. Partial work sometimes earns no credit if the expected resource state is missing, so verification is a scoring activity, not a polish activity. A completed task has evidence that matches the instruction. A merely attempted task has commands in shell history.

Keep scratch notes minimal and structured. You do not need paragraphs during the exam; you need a queue of deferred tasks and the reason they were deferred. A useful note might be: "Q6 pass3: pods Pending in `payments`; check scheduler/events after quick wins." That note preserves context without stealing time.

The exam browser and terminal create another strategic hazard: context switching. Opening documentation for every command breaks flow, while refusing documentation causes field errors. The balanced strategy is to use documentation for exactness, not for reassurance. Search with the missing field or task name, copy only the relevant pattern, then return to the terminal.

A senior operator also knows when to stop improving a solution. If the task asks for a ClusterIP Service and endpoints are populated, do not spend extra time making the YAML prettier. If the task asks for a Deployment image update and rollout status succeeds, do not inspect every unrelated Pod in the namespace. Completion means matching the requirement, not exhausting curiosity.

The following decision matrix can guide pass assignment during practice. Use it after reading a task, then compare your final outcome with your initial classification. Over time, your classifications will become more accurate.

| Signal in the Task | Likely Pass | Reasoning Pattern | Verification Anchor |
|---|---|---|---|
| "Create a namespace" or "scale this Deployment" | Pass 1 | Direct command, low ambiguity, short feedback loop | `k get` for exact object state |
| "Create from YAML with these fields" | Pass 2 | Generation plus edit, field placement matters | `k apply`, `k get -o yaml`, status |
| "Add a probe, volume, or environment variable" | Pass 2 | Requires correct API path under Pod template | `k explain`, rollout status, describe |
| "Troubleshoot why Pods are not starting" | Pass 3 | Unknown failure layer until events and states are inspected | `describe`, logs, events |
| "Control plane component is missing" | Pass 3 | Node-level or static Pod repair can affect cluster health | kube-system Pods, manifests, events |
| "Use documentation to configure a feature" | Pass 2 | Bounded lookup likely needed for exact syntax | Official example plus cluster status |

Practice the strategy with a timer, but do not confuse timer pressure with rushing. Rushing skips gates. A disciplined pace moves quickly because each step has a purpose and each verification command closes a loop.

---

## Core Content: Cumulative Readiness Review

Part 0 readiness is not measured by whether you can repeat twenty facts. It is measured by whether you can operate in a Kubernetes terminal without losing target, structure, or evidence. The following review connects the earlier modules into a single readiness model.

From cluster setup, you need the control plane mental model. The API server stores and serves cluster state, controllers reconcile desired state, the scheduler assigns Pods to nodes, kubelet runs Pods on nodes, and static Pods come from files watched by kubelet. When a symptom appears, this model helps you choose the responsible component.

From shell mastery, you need low-friction command execution. The `k` alias, completion, dry-run generation, and output formatting save time only when they remain transparent. If a helper hides too much, slow down and expand it. The exam rewards fluency, not mystery.

From Vim, you need reliable manifest editing. YAML correctness is not visual neatness; it is structural meaning. Two-space indentation, spaces instead of tabs, paste mode when needed, and small edits prevent errors that are hard to see under pressure.

From documentation navigation, you need bounded lookup habits. Use `kubectl explain` for API field paths and official docs for examples or task patterns. Do not browse to feel confident. Browse to answer a named question, then return to the terminal and verify.

From exam strategy, you need pass-based prioritization. The three-pass method is a scoring strategy, but it is also a cognitive-load strategy. It prevents one uncertain problem from consuming the attention needed for several straightforward tasks.

A strong Part 0 learner can explain why each habit exists. Context checks prevent wrong-target work. Dry-run YAML prevents structural mistakes. Vim settings protect indentation. Documentation prevents field hallucination. Verification converts attempted work into scored work. Pass strategy protects time.

A senior-level learner can also adapt those habits when conditions change. If autocomplete is unavailable, they can still use explicit commands. If documentation search is slow, they can use `kubectl explain`. If a generated manifest lacks a required field, they can edit it safely. If a task becomes larger than expected, they can defer it and preserve score elsewhere.

Before taking the cumulative quiz, pause and rehearse this compact workflow: context, namespace, resource, method, edit, apply, verify, decide. That sentence is not a slogan; it is an execution order. If you can apply it to unfamiliar questions, Part 0 has done its job.

---

## Did You Know?

- **Fact 1**: [`kubectl explain` reads schema information exposed by the Kubernetes API server](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_explain/), which means it can reflect the resource fields available in the cluster you are actually using rather than a random example from memory.

- **Fact 2**: [Static Pods are managed by kubelet from files on the node](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/), so a broken manifest can affect a control plane component even when the Kubernetes API is otherwise healthy enough to show mirror Pods.

- **Fact 3**: [A Service with a valid ClusterIP can still send traffic nowhere if its selector does not match any Ready Pods](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/), which is why endpoints are often better verification evidence than the Service object alone.

- **Fact 4**: The exam's time pressure makes verification more important, not less important, because a fast unverified task can silently earn no credit while also giving you false confidence.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Starting a task without switching context | Correct resources created in the wrong cluster usually do not score and can mislead later troubleshooting | Run `k config use-context <context>` and confirm with `k config current-context` before scored changes |
| Assuming the namespace from the previous question still applies | Namespaced resources can look missing or broken when they were created in a different namespace | Use explicit `-n <namespace>` flags whenever the task names a namespace |
| Hand-writing large YAML from memory | Small indentation or field-path errors can waste more time than generation would have taken | Generate a skeleton with dry-run output, then edit only the fields the task requires |
| Treating `kubectl apply` as verification | Apply only proves the API accepted the object, not that controllers converged or traffic works | Verify with rollout status, resource status, events, labels, endpoints, or logs as appropriate |
| Using documentation without a specific question | Browsing broadly burns time and increases the chance of copying irrelevant examples | Decide the missing field or pattern first, look it up, apply it, then return to verification |
| Deleting Pods before gathering evidence | Deletion can erase useful state and may simply recreate the same failure under a controller | Inspect status, events, logs, and owning controllers before disruptive actions |
| Editing static Pod manifests casually | A malformed control plane manifest can remove a critical component until kubelet accepts a corrected file | Inspect the file carefully, preserve indentation, and verify the mirror Pod in `kube-system` |
| Spending too long on an unknown failure | One open-ended task can consume the time needed for several direct tasks | Classify uncertain troubleshooting as pass three, record a note, and return after quick wins |

---

## Quiz

Answer these scenario-based questions without referring to earlier modules. After each answer, compare your reasoning with the explanation, not just the final command. The goal is to prove that you can choose safe actions under realistic exam constraints.

### 1. Wrong-Target Prevention

You open a new exam question that says: "Use context `cluster-b` and namespace `payments`." Your prompt still shows a familiar cluster name from the previous task, and you are confident you know the resource command. What should you do before creating anything, and what risk remains if you only check the context?

1. Switch to `cluster-b`, confirm it, and use `-n payments` or verify the namespace before changing resources.
2. Check only `k config current-context`, then create the resource because the namespace can be fixed later.
3. Create the resource first, then move it to `payments` if verification shows it landed in `default`.
4. Skip the target check because the prompt already displays a familiar cluster name from the previous task.

<details>
<summary>Answer</summary>

Option 1 is correct because it checks both target dimensions before any scored change: `k config use-context cluster-b`, `k config current-context`, and explicit `-n payments` commands or a verified namespace setting. Option 2 is wrong because context alone still leaves namespace drift. Option 3 is incorrect because moving namespaced resources after creation is not a safe exam workflow. Option 4 is not correct because a familiar prompt is weaker evidence than the kubeconfig state.

</details>

### 2. Choosing Generation Over Memory

A task asks you to create a Deployment named `worker` with two replicas, image `busybox:1.36`, and command `sleep 3600`, then save the manifest before applying it. You remember most of the Deployment structure but are not sure where command arguments belong. What approach best balances speed and correctness?

1. Generate a dry-run Deployment manifest, inspect or edit command fields, confirm uncertain paths with `k explain`, then apply.
2. Hand-write the whole Deployment from memory because saving time matters more than checking field placement.
3. Create a Pod instead of a Deployment because Pod command fields are easier to remember.
4. Apply the generated manifest without saving it, then edit the live object only if the Pods fail.

<details>
<summary>Answer</summary>

Option 1 is correct because dry-run output creates a valid Deployment skeleton while `k explain pod.spec.containers.command` and `k explain pod.spec.containers.args` resolve exact field shape before applying. Option 2 is wrong because memory-based YAML increases indentation and API-path risk. Option 3 is incorrect because the task requires a Deployment. Option 4 is not correct because the task explicitly asks to save the manifest before applying it.

</details>

### 3. Diagnosing Pending Pods

Your team created a Deployment successfully, but all new Pods remain `Pending`. Existing Pods in other namespaces are still running, and the API server responds normally. Which evidence should you gather first, and why is changing the image a weak first move?

1. Run `k get pods -o wide` and `k describe pod` in the namespace to read scheduling state and events.
2. Change the image immediately because Pending usually means the container image cannot start.
3. Delete the Deployment and recreate it before collecting events so the controller gets a clean attempt.
4. Restart the API server because existing Pods in other namespaces prove scheduling is irrelevant.

<details>
<summary>Answer</summary>

Option 1 is correct because Pending is primarily a scheduling signal until events prove otherwise. Option 2 is wrong because image changes target container startup after scheduling, not assignment to a node. Option 3 is incorrect because deletion discards useful evidence and may recreate the same failure. Option 4 is not correct because a responsive API server and existing running Pods point toward scheduling constraints or scheduler behavior, not an immediate API restart.

</details>

### 4. Repairing a Service With No Endpoints

A Service exists and has a ClusterIP, but traffic fails and `k get endpoints` shows no addresses. The Pods for the application are Running. What relationships should you inspect, and what result would confirm the fix?

1. Compare Service selectors, Pod labels, and Pod readiness, then confirm endpoints contain the expected Pod IPs and ports.
2. Recreate the Service with a new ClusterIP because an existing Service without endpoints must be corrupt.
3. Restart all Running Pods because any Running Pod should automatically receive Service traffic.
4. Change the Deployment image because empty endpoints usually mean the container image is outdated.

<details>
<summary>Answer</summary>

Option 1 is correct because Services publish endpoints from matching Ready Pods, so selectors, labels, and readiness are the first relationships to inspect. Option 2 is wrong because the ClusterIP can exist while selectors match nothing. Option 3 is incorrect because Running is not the same as selected and Ready. Option 4 is not correct because an image change does not address selector or readiness evidence unless the diagnosis specifically points there.

</details>

### 5. Handling a Broken Static Pod

A control plane node is missing the scheduler Pod, and newly created Pods are not being assigned to nodes. You have node access. What file location and Kubernetes namespace are most relevant, and how should you verify recovery?

1. Check `/etc/kubernetes/manifests/` on the control plane node and verify the scheduler mirror Pod in `kube-system`.
2. Edit the Deployment manifests for the Pending workloads because the scheduler is controlled by application YAML.
3. Look only in the default namespace because new Pods were created there and namespace scope controls scheduling.
4. Delete every Pending Pod repeatedly until kubelet recreates the scheduler from the workload controller.

<details>
<summary>Answer</summary>

Option 1 is correct because kubelet manages static control plane Pods from `/etc/kubernetes/manifests/`, and the scheduler mirror Pod should appear in `kube-system` when the manifest is present and valid. Option 2 is wrong because application Deployments do not control the scheduler component. Option 3 is incorrect because control plane static Pods are not found by inspecting only the default namespace. Option 4 is not correct because deleting Pending workload Pods does not restore a missing scheduler manifest.

</details>

### 6. Deciding When to Use Documentation

A question asks you to add an HTTP readiness probe to an existing Deployment. You know the concept, but you are uncertain about the exact YAML path under the Pod template. What is the fastest safe lookup strategy when you compare fast command-line approaches with documentation-driven approaches?

1. Use `k explain` for the specific probe path, then use official documentation only if you need a complete example.
2. Search broadly across the web until you find any readiness probe YAML that looks familiar.
3. Guess the indentation from memory because readiness probes always go directly under the Deployment spec.
4. Skip the probe because a Deployment can roll out without readiness configuration.

<details>
<summary>Answer</summary>

Option 1 is correct because `k explain deployment.spec.template.spec.containers.readinessProbe` and related subfields answer the exact API-path question quickly, while official docs help if a fuller HTTP example is needed. Option 2 is wrong because broad search is unbounded and may use irrelevant examples. Option 3 is incorrect because probe placement under the Pod template matters. Option 4 is not correct because the task requires the readiness probe, and the fast command-line versus documentation-driven approaches decision is about bounded lookup rather than avoiding the task.

</details>

### 7. Applying the Three-Pass Method

You scan a mock exam with a mixed task set: create a namespace, add a ConfigMap volume to a Deployment, and troubleshoot why several Pods are not starting. How should you apply the three-pass exam method to order them, and what evidence tells you that the first task is complete?

1. Create and verify the namespace first, handle the ConfigMap volume second, and defer broad troubleshooting until pass three.
2. Start with the broad troubleshooting task because it might reveal information useful for every other question.
3. Add the ConfigMap volume first, then create the namespace afterward if the apply command fails.
4. Work strictly in page order even when the first task has uncertain scope and weak verification.

<details>
<summary>Answer</summary>

Option 1 is correct because the namespace is a pass-one quick win, the ConfigMap volume is a pass-two manifest-edit task, and broad Pod troubleshooting belongs in pass three unless evidence makes it smaller. Option 2 is wrong because open-ended diagnosis can consume time before easy score is secured. Option 3 is incorrect because namespace existence is a prerequisite target, not an afterthought. Option 4 is not correct because page order is less important than uncertainty, verification cost, and score protection. This is how you apply the three-pass exam method to a mixed task set.

</details>

### 8. Verifying a Rollout Instead of Assuming It

You update a Deployment image and `kubectl apply` reports that the object was configured. The question asks for the Deployment to run the new image successfully. What additional checks should you perform before marking the task done?

1. Run rollout status and inspect the Deployment and Pods to confirm readiness and the requested image state.
2. Stop after `configured` appears because API acceptance proves the new Pods are healthy.
3. Delete old Pods immediately because rollout status is unnecessary after an image update.
4. Check only the YAML file on disk because the saved manifest proves cluster convergence.

<details>
<summary>Answer</summary>

Option 1 is correct because `k rollout status deploy/<name> -n <ns>`, Deployment status, and Pod inspection prove controller convergence and requested image state. Option 2 is wrong because `configured` only means the API accepted the object. Option 3 is incorrect because deleting Pods can mask rollout evidence and is not the normal verification step. Option 4 is not correct because a local file does not prove the cluster reached the desired state.

</details>

---

## Hands-On Exercise

**Task**: Build and validate an exam-ready workflow in a disposable practice cluster. You will create resources, intentionally inspect relationships, use documentation-style field discovery, and verify the final state instead of trusting command success.

Use an existing local Kubernetes practice cluster such as kind, minikube, or another disposable environment. Do not run these steps against a shared production cluster. If your practice environment does not use the exact same context name as the examples, substitute your own context deliberately and verify it before continuing.

### Step 1: Establish Target Safety

Start by recording your current context and creating a dedicated namespace for this exercise. The point is not that namespace creation is difficult; the point is to begin every task by proving the target before changing state.

```bash
k config current-context
k create ns part0-review
k get ns part0-review
```

### Step 2: Create a Deployment From a Generated Skeleton

Generate or directly create a Deployment named `portal` with three replicas and image `nginx:1.35` in the exercise namespace. If you generate YAML first, inspect it before applying so you can connect the command to the manifest structure.

```bash
k create deploy portal --image=nginx:1.35 --replicas=3 -n part0-review
k rollout status deploy/portal -n part0-review
```

### Step 3: Expose the Deployment and Verify Endpoints

Expose the Deployment with a ClusterIP Service on port eighty. Then verify not only that the Service exists, but that endpoints are populated. This step confirms that labels, selectors, Pod readiness, and Service wiring agree.

```bash
k expose deploy portal --port=80 --target-port=80 -n part0-review
k get svc,endpoints -n part0-review
k get pods -n part0-review --show-labels
```

### Step 4: Use Field Discovery Before Editing

Use `kubectl explain` to inspect the readiness probe field path. You do not need to memorize the whole schema; you need to practice asking the cluster for the exact field shape before editing YAML.

```bash
k explain deployment.spec.template.spec.containers.readinessProbe
k explain pod.spec.containers.readinessProbe.httpGet
```

### Step 5: Export, Edit, and Apply a Focused Manifest Change

Export the Deployment, add a readiness probe to the container, and reapply the manifest. Use Vim with spaces and careful indentation, or use another editor only if it preserves YAML structure reliably.

```bash
k get deploy portal -n part0-review -o yaml > portal.yaml
```

Add this probe under the container that runs `nginx:1.35`, preserving two-space YAML indentation relative to nearby fields.

```yaml
readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 3
  periodSeconds: 5
```

Apply the edited manifest and verify that the rollout converges again.

```bash
k apply -f portal.yaml
k rollout status deploy/portal -n part0-review
k get deploy,pods,endpoints -n part0-review
```

### Step 6: Practice a Selector Diagnosis

Inspect the Service selector and Pod labels, then explain to yourself why the endpoints exist. If you want a challenge, temporarily change the Service selector to a label that does not match, observe endpoints disappear, then restore the correct selector. Only do this in the disposable exercise namespace.

```bash
k get svc portal -n part0-review -o yaml
k get pods -n part0-review --show-labels
k get endpoints portal -n part0-review -o wide
```

### Step 7: Clean Up Deliberately

Delete the namespace only after you have verified the final state and practiced the diagnosis. Cleanup is part of professional cluster operation because it proves you can distinguish practice resources from durable resources.

```bash
k delete ns part0-review
```

**Card A: Checking only the context is enough.** Wrong belief: if `k config current-context` matches the task, the target is safe. That belief misses namespace state, and most CKA workload objects are namespaced. Failure layer: target safety. Next action: pair context confirmation with explicit `-n <namespace>` or a verified current namespace before creating resources.

**Card B: `kubectl apply` configured means the rollout succeeded.** Wrong belief: API acceptance is the same as workload convergence. `configured` only says the object was accepted; controllers, Pods, probes, and images still need to reach the requested state. Failure layer: verification. Next action: run rollout status and inspect Deployment, Pod, and event evidence before marking the task done.

**Card C: A Running Pod guarantees Service endpoints.** Wrong belief: any Running Pod behind a Service will automatically receive traffic. Endpoints require matching selectors and Ready Pods, so labels and readiness can still block publication. Failure layer: resource relationship diagnosis. Next action: compare Service selectors with Pod labels, then check endpoints and readiness details.

**Card D: Highest-point troubleshooting first.** Wrong belief: the largest or scariest task deserves the first minutes because it might be worth more. Open-ended diagnosis can absorb time before quick verified points are secured. Failure layer: exam strategy. Next action: classify tasks into passes, finish low-uncertainty work first, and return to broad failures with preserved notes.

**Success Criteria**:

- [ ] You confirmed the Kubernetes context before creating exercise resources.

- [ ] You created the `part0-review` namespace and verified that it existed before continuing.

- [ ] You created a three-replica `portal` Deployment using image `nginx:1.35` in the correct namespace.

- [ ] You exposed the Deployment with a Service and verified that endpoints were populated.

- [ ] You used `kubectl explain` to inspect readiness probe fields before editing the manifest.

- [ ] You edited YAML with valid indentation and applied the readiness probe without breaking the rollout.

- [ ] You verified the final state with rollout status, Pod status, Service status, and endpoints rather than relying only on `apply`.

- [ ] You can explain why a Service selector mismatch would produce an empty endpoints object even when Pods are Running.

---

## Sources

- [docs.linuxfoundation.org: certification resources allowed](https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed) — The Linux Foundation resources-allowed page explicitly permits Kubernetes documentation access and explicitly allows the on-site search while forbidding external search results.
- [kubernetes.io: organize cluster access kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/) — The kubeconfig documentation directly states that each context has cluster, namespace, and user parameters and that kubectl uses the current context by default.
- [kubernetes.io: implementation details](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/) — The kubeadm implementation details page explicitly documents the manifest path, kubelet watch behavior, and `kube-system` namespace placement for kubeadm-managed control plane static Pods.
- [kubernetes.io: static pod](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/) — The static Pods task page explicitly says static Pods are managed by kubelet and that kubelet automatically tries to create a mirror Pod for each one.
- [kubernetes.io: kubectl create deployment](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_deployment/) — The `kubectl create deployment` reference explicitly documents `--dry-run=client` as printing the object that would be sent without sending it.
- [kubernetes.io: kubectl explain](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_explain/) — The official `kubectl explain` reference says information about each field is retrieved from the server in OpenAPI format.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment documentation explicitly states that `.spec.selector` must match `.spec.template.metadata.labels`.
- [kubernetes.io: endpoint slices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) — The EndpointSlice documentation says Services with selectors get EndpointSlices containing matching Pods and that Pod-backed endpoint readiness maps to the Pod `Ready` condition.
- [kubernetes.io: namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) — The namespaces concept page explains namespace scoping for namespaced resources, which supports the module's namespace-target checks.
- [kubernetes.io: service](https://kubernetes.io/docs/concepts/services-networking/service/) — The Service concept page documents Services as a way to expose applications running as Pods and explains selector-based targeting.
- [kubernetes.io: kubectl rollout](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_rollout/) — The `kubectl rollout` reference documents rollout management commands used to verify controller progress after Deployment changes.

## Next Module

Continue to [Part 1: Cluster Architecture](/k8s/cka/part1-cluster-architecture/)
