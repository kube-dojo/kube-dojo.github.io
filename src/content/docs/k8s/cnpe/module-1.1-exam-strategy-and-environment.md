---
revision_pending: false
title: "CNPE Exam Strategy and Environment"
slug: k8s/cnpe/module-1.1-exam-strategy-and-environment
sidebar:
  order: 101
---

> **CNPE Track** | Complexity: `[MEDIUM]` | Time to Complete: 45-60 min
>
> **Prerequisites**: CNPE hub, Platform Engineering fundamentals, GitOps basics, Observability basics

## Learning Outcomes

After this module, you will be able to:

- diagnose CNPE prompts as GitOps, platform API, observability, security, or operations tasks before changing the system
- design a repeatable triage, execution, and verification workflow for a performance-based platform exam
- evaluate task risk and pace work across delivery, self-service, observability, security, and operations domains
- implement an exam environment checklist that reduces context mistakes, command drift, and verification gaps
- compare evidence sources so you can prove whether Git, the platform API, or the cluster reflects the desired state

## Why This Module Matters

Hypothetical scenario: you sit down for a CNPE-style practice session and the first task asks you to restore a platform service that is stuck after a delivery change. The repository shows a recent edit, the GitOps controller reports an unhealthy application, a Crossplane claim is not ready, and an admission policy event appears in the namespace. A learner who treats the task as a trivia question starts hunting for a remembered command, but a platform engineer reads the situation as a system-state problem: find the desired state, choose the smallest safe lever, and prove the platform converged.

That is why CNPE preparation has to feel different from passive certification study. The CNCF describes CNPE as a hands-on, performance-based exam for platform engineering work, and the published domains spread across platform architecture, GitOps and continuous delivery, platform APIs and self-service, observability and operations, and security and policy enforcement. In practical terms, you are not preparing to recite definitions; you are preparing to move across layers without losing the thread. The exam rewards candidates who can decide whether the source of truth is Git, a custom API, a policy engine, a controller status field, or a cluster observation.

This module builds the operating rhythm you will reuse throughout the CNPE track. You will learn to read prompts for intent, sort tasks by risk, keep your environment predictable, and verify results with evidence instead of hope. The goal is not to make you frantic or overly tactical. The goal is to make your practice sessions boring in the best way: every task gets classified, changed, checked, recorded, and either finished or deliberately deferred.

> **The Control Room Analogy**
>
> CNPE is less like a written test and more like a control room shift. You are not being asked to admire dashboards. You are being asked to notice the signal, choose the right lever, and confirm the system recovered.

## Read the Prompt as a Platform Contract

The first skill is prompt reading, because a performance exam hides most of its time savings before the first command. A CNPE task usually describes a gap between intended platform behavior and observed behavior. Your job is to identify the contract that is being violated: a GitOps application should match the repository, a self-service claim should produce ready infrastructure, an alert should fire only for the intended condition, a policy should block or audit the right objects, or a shared platform component should remain reliable while tenants change their workloads.

Read each prompt through three questions: what is the desired end state, what is the smallest safe change, and what proves the change worked? Those questions sound simple, but they prevent a common exam failure mode. Without them, candidates treat every prompt as a command search problem and drift into exploratory editing. With them, you can make a bounded plan even when the tool surface is unfamiliar, because every platform domain still has a source of truth, a reconciler or API boundary, and an observable result.

The CNPE domains encourage transitions between layers. A delivery task may begin with a repository edit, continue through an Argo CD sync, and end with a Kubernetes rollout check. A platform API task may begin with a namespaced claim, continue through a composite resource or controller status, and end with a managed resource condition. An operations task may begin with a metric or log pattern, continue through a deployment or config change, and end with a policy, event, or telemetry signal that proves the system behaved differently.

```text
+----------------------+----------------------+----------------------+
| Prompt clue          | Likely work surface  | Evidence to collect  |
+----------------------+----------------------+----------------------+
| "sync", "promote"    | GitOps repository    | app sync and health  |
| "claim", "self-serve"| platform API or CRD  | ready conditions     |
| "alert", "latency"   | observability stack  | metric, log, trace   |
| "deny", "audit"      | policy controller    | event or report      |
| "access", "role"     | Kubernetes RBAC      | can-i or binding     |
+----------------------+----------------------+----------------------+
```

Pause and predict: if a task mentions a desired version in Git but a different image is running in the cluster, which state do you trust first and what would prove reconciliation happened? The answer is not always "edit Git immediately." First determine whether the application is supposed to be GitOps-managed, whether the controller is paused or unhealthy, and whether the running workload belongs to the same desired object. That extra minute avoids editing the wrong repository path or fighting a controller that is already telling you why it cannot apply the change.

This prompt-reading habit also protects you from over-solving. If the desired end state is "the claim should be Ready" and the claim is failing because a composition parameter is invalid, replacing the whole composition is usually a poor exam move. The smallest safe change may be a single field, a corrected reference, or a namespace-scoped object the controller expected to find. CNPE-style work rewards accurate repair more than impressive motion.

There is a useful difference between "the task mentions a tool" and "the tool is the correct lever." A prompt may mention a Deployment only because the Deployment is the visible symptom, while the persistent fix lives in Git. It may mention an alert only because the alert is how the failure was noticed, while the safe change is a service selector or policy exception. Train yourself to ask which object has authority to keep the desired state true after your hands leave the keyboard.

Another practical prompt-reading habit is to separate nouns from verbs. The nouns tell you the objects and domains: application, claim, policy, alert, namespace, service, role, or pipeline. The verbs tell you the expected movement: promote, reconcile, deny, audit, restore, roll back, provision, or diagnose. When nouns and verbs point to different layers, the task is telling you to connect layers rather than camp inside one tool. That is where many CNPE points are won.

| Domain clue | First question | Fast evidence | Typical trap |
|-------------|----------------|---------------|--------------|
| GitOps delivery | Which repository path owns the desired state? | application diff, sync status, rollout status | editing live cluster objects that Git will overwrite |
| Platform API | Which custom object is the user-facing contract? | claim, XR, resource refs, conditions | debugging only the managed resource and ignoring the claim |
| Platform architecture / infrastructure | Which topology, tenancy, or sizing choice matches the prompt? | namespace layout, node pools, storage class, cost signals | patching one workload when the platform design is wrong |
| Observability | Which signal proves user-visible behavior changed? | metric query, trace span, log correlation, alert state | treating one log line as the whole incident |
| Security and policy | Is the rule supposed to audit or enforce? | admission event, policy report, denied request | changing policy before confirming match scope |
| Operations | Which component owns reconciliation? | controller logs, events, status conditions | restarting components without reading status |

## Build a Three-Pass Exam Workflow

The second skill is pacing. CNPE tasks are not equally difficult, and their difficulty is not always visible from the first sentence. A good strategy is to move through the exam in three passes: quick wins, medium tasks, and fragile or multi-step tasks. This is not a trick for avoiding hard work. It is a way to bank points, protect working memory, and make deliberate decisions about where your remaining time should go.

Pass one is for obvious, low-risk, easy-to-verify tasks. Examples include updating a GitOps value when the repository path is clear, inspecting a CRD or claim for a condition, fixing a simple RBAC binding, correcting a policy scope, or answering a diagnostic question from a metric or event. These tasks should have short feedback loops. You read, act, verify, and mark the result without trying to solve every adjacent problem you noticed.

Pass two is for tasks that need a few coordinated changes. Promotion between environments, a self-service provisioning request, an observability fix that touches both alerting and configuration, or a policy update with one verification step belongs here. The work is still bounded, but you need to keep two or three objects in your head at once. This is where a scratchpad matters, because the exam environment does not care that you almost finished a task if you cannot remember which check remains.

Pass three is for fragile or multi-step work. Multi-system troubleshooting, rollback after a bad delivery, a platform API failure with several dependent resources, or a security issue that requires careful exception handling can burn time quickly. Leaving these tasks for a deliberate pass gives you a cleaner mental state and more information from the rest of the exam. Sometimes an earlier quick task reveals the same repository layout, namespace convention, or controller behavior that makes the later task easier.

Before running this, what output do you expect from each command, and which one would tell you that you are in the wrong environment?

```bash
git status --short
kubectl config current-context
kubectl get events -A --sort-by=.lastTimestamp | tail -n 10
```

That command block is intentionally plain. This short environment check catches three high-value mistakes: uncommitted local edits, the wrong Kubernetes context, and recent cluster-level warnings. It does not solve the task, but it prevents you from solving a task in the wrong place. In an exam, that is often the difference between a recoverable typo and a long detour.

Timeboxing is the discipline that makes the three-pass strategy real. If a task does not reveal a credible next action after a bounded inspection, mark it and move on. A useful scratchpad entry can be short: `Q3: app out of sync, repo path unclear, return after GitOps tasks`. You are not abandoning the task; you are preserving the rest of the exam while keeping enough state to resume.

| Pass | Choose tasks that are | Typical examples | Stop condition |
|------|-----------------------|------------------|----------------|
| Pass 1 | obvious, low-risk, quick to verify | value edit, simple policy scope, RBAC check, claim inspection | no clear next action after initial inspection |
| Pass 2 | bounded but coordinated | promotion, self-service request, alert rule fix, rollout check | more than one uncertain dependency |
| Pass 3 | fragile, broad, or failure-prone | rollback, multi-controller issue, policy exception, deep incident | remaining time no longer supports safe change |

The three-pass workflow is also a way to compare task risk. A task with a short command and a vague goal is not necessarily quick, while a task with several steps can be safe if every step has a crisp verification point. The question is not "how many commands will I type?" The question is "how many assumptions can be wrong before I notice?" CNPE rewards candidates who notice wrong assumptions early.

Use practice sessions to calibrate your personal timeboxes. Some candidates are quick at GitOps edits but slow at reading policy events; others are comfortable with Kubernetes status but lose time tracing platform API relationships. Calibration is not about assigning shame to weak domains. It is about building a realistic pass strategy, because a domain that costs you ten minutes in practice will not magically become a three-minute task under proctoring pressure.

The three-pass strategy also lowers the emotional cost of uncertainty. When you know in advance that some tasks are meant to be revisited, a skipped task becomes a planned state rather than a failure. That matters because platform work creates many plausible paths. A calm return note gives you permission to leave a branch of investigation before it turns into wandering.

## Prepare the Environment Like a Practice Lab

Your environment checklist should simulate the exam workflow, not just confirm that tools are installed. Many candidates practice with a comfortable terminal, a familiar cluster, and a forgiving amount of time, then discover that the exam setting makes basic navigation feel expensive. You want the opposite. Practice should make the environment boring, so your attention stays on the platform problem.

Start with context control. Know how you will confirm the active cluster, namespace, repository branch, and local working tree. If the task mentions multiple environments, use explicit flags or commands that print the target rather than relying on memory. Avoid runnable shell aliases in practice material and scripts, because aliases do not expand in non-interactive shells and they hide intent from anyone reviewing your commands later. Many engineers use personal shortcuts interactively, but CNPE preparation should train copy-paste-safe commands with the full `kubectl` binary.

Next, prepare a scratchpad format that is small enough to maintain under pressure. A useful entry records the task number, domain, intended lever, verification command, and status. Anything longer becomes a second documentation project. You are trying to externalize state, not write a postmortem. The scratchpad should help you resume a skipped task in one glance and avoid re-reading the whole prompt after a context switch.

```text
+------+------------+------------------+-----------------------+--------+
| Task | Domain     | Lever            | Verification          | State  |
+------+------------+------------------+-----------------------+--------+
| 1    | GitOps     | values file      | app health + rollout  | done   |
| 2    | Platform   | claim field      | claim Ready=True      | return |
| 3    | Security   | policy scope     | denied test workload  | open   |
+------+------------+------------------+-----------------------+--------+
```

Your local references should be predictable as well. The Kubernetes quick reference, `kubectl` reference pages, Argo CD user guide, Crossplane composition documentation, OpenTelemetry signal concepts, and policy-controller documentation are all valuable, but only if you can find the relevant page quickly. During practice, build the habit of looking up the concept you need, applying it, and closing the loop. Do not turn every lookup into a reading session.

Exercise scenario: you have thirty minutes to practice one GitOps task, one platform API task, and one observability or security task. Your setup goal is not to finish with a pretty notebook. Your setup goal is to prove that you can switch domains without losing command context, repository state, or verification discipline. If you cannot switch cleanly in practice, a performance exam will amplify the friction.

Environment preparation includes failure preparation. Decide what you will do when a command fails because the resource type is missing, the namespace is wrong, the context is stale, or a controller is not installed. The right response is usually to inspect scope and ownership before editing. For example, `kubectl api-resources` can tell you whether a CRD-backed API exists, while events and status conditions can show whether a controller saw your object and rejected it for a specific reason.

```bash
kubectl api-resources | grep -E 'claims|composite|applications|policies' || true
kubectl get namespaces
kubectl auth can-i get pods --all-namespaces
```

These commands are not universal answers, and the `grep` expression is intentionally broad. They model the environment-checking mindset: confirm that the APIs and permissions you plan to use are actually present before you build a solution around them. If the expected API is absent, the task may be asking you to use a different tool surface, inspect a different cluster, or recognize that a prerequisite controller is unhealthy.

Keep your documentation access just as deliberate as your cluster access. In a timed environment, docs are useful when they answer a specific operational question: which field controls automated sync, how a condition is represented, which command waits for an application, or how a validation policy reports audit results. Docs become harmful when they turn into a browsing session with no task hypothesis. Before opening a page, state the question you expect it to answer.

Practice without relying on personal shell state. That includes aliases, exported namespace variables, custom prompt decorations, and helper functions that do not exist in a neutral environment. There is nothing wrong with using those tools in daily work, but exam preparation should make hidden state visible. A command that includes the namespace, context check, resource name, and full binary is slower to type once and faster to debug when pressure rises.

## Execute Changes Through the Right Source of Truth

Once you understand the prompt and trust your environment, the next question is where to make the change. Platform engineering work is full of tempting wrong levers. A live `kubectl edit` may appear to fix a workload, but a GitOps controller can revert it. A direct managed-resource patch may appear to fix infrastructure, but a Crossplane composition can recreate the old state. A policy exception may quiet a denial, but the real bug may be a namespace label or match expression.

For GitOps tasks, treat Git as the desired-state contract unless the prompt clearly says otherwise. Inspect the application, repository path, target revision, sync status, and health before changing manifests. Argo CD distinguishes desired state from live state, and that distinction is exactly why GitOps helps platform teams operate at scale. If the desired state is wrong, fix Git; if the desired state is right but sync is blocked, inspect the controller, diff, hooks, waves, and permissions.

For platform API tasks, identify the user-facing object first. In Crossplane terms, a claim can be namespaced while a composite resource is cluster-scoped, and the composition owns managed resources behind the abstraction. That separation is the point of a platform API: application teams request an outcome without managing every infrastructure detail. In Crossplane v1 (and v2 LegacyCluster mode), a namespaced **Claim** maps to a cluster-scoped composite resource (XR); in Crossplane v2 the XR is namespaced by default and there is no separate Claim API. Exam tasks may use either model — diagnosis still flows claim → XR → composition → managed-resource refs in v1, or namespaced-XR conditions in v2. In an exam task, debugging only the cloud resource or only the Kubernetes object can waste time if you skip the relationship between claim, composite resource, composition, and managed resource conditions.

For observability tasks, resist the urge to treat the first signal as the truth. Metrics, logs, traces, events, and policy reports answer different questions. A metric can show rate or saturation, a trace can show request path, a log can show a local event, and a Kubernetes event can show controller behavior. CNPE-style operations work often asks you to combine signals just enough to choose a safe lever, not to conduct an open-ended investigation.

For security and policy tasks, confirm the intended mode before changing the rule. Kyverno validation rules can audit or enforce, and Gatekeeper-style admission control also depends on match scope, constraints, and templates. A policy that should audit a migration behaves very differently from a policy that should block production workloads. If the prompt asks for a denied workload to become allowed, the right change may be a label, namespace selection, exception, image reference, or policy parameter rather than weakening the whole control.

```bash
kubectl get applications.argoproj.io -A
kubectl get claims -A 2>/dev/null || true  # claim plural is per-XRD — substitute your claim CRD plural
kubectl get events -A --sort-by=.lastTimestamp | tail -n 20
kubectl auth can-i create deployments --namespace default
```

Notice the pattern in those commands. They do not assume one platform implementation, but they ask useful questions: is there a GitOps application API, are there claim-like resources, what recently happened in the cluster, and do I have the permission needed for the next step? In a real task you would narrow each command, but broad inspection is acceptable when it prevents an immediate wrong edit.

The smallest safe change is the one that moves the contract toward the desired state while preserving ownership. In GitOps, that may be one values field and a sync verification. In platform APIs, it may be a claim parameter that lets the composition reconcile. In observability, it may be an alert threshold or label selector that matches the intended service. In security, it may be a policy match expression that targets the correct namespace without opening the whole cluster.

A useful rule is to prefer reversible, scoped, and owned changes. Reversible means you can explain how to undo the change without reconstructing the whole task. Scoped means the change affects the named workload, namespace, claim, application, or policy target rather than the entire platform. Owned means the change is made at the layer that will continue reconciling the state. If your planned edit fails any of those tests, slow down and inspect ownership again.

This is especially important for rollback tasks. A rollback in GitOps may mean returning a repository value or revision, not deleting pods until an old version happens to appear. A rollback in a platform API may mean restoring a claim parameter or composition reference, not editing each managed resource one by one. A rollback in policy may mean restoring an enforce mode after a migration window, not removing the policy object entirely. The word "rollback" describes the desired outcome; the platform owner determines the lever.

## Verify Like the Task Is Not Done Yet

Verification is the real skill because platform systems are asynchronous. A file can be correct before a controller has applied it. A Kubernetes object can exist before it is ready. A policy can be installed before it matches the intended resource. A telemetry query can return data before it proves the user-visible path recovered. Treat every task as incomplete until you have evidence from the layer that owns the final state.

Good verification is layered. First, confirm the change exists at the source of truth. Second, confirm the controller or API accepted it. Third, confirm the user-facing or operator-facing result changed. That sequence prevents two opposite mistakes: declaring victory after a local file edit, and staring at the live cluster without realizing the desired state never changed. CNPE tasks often become easier when you write the verification path before editing.

```text
+-------------------+-----------------------+------------------------+
| Source evidence   | Reconcile evidence    | Outcome evidence       |
+-------------------+-----------------------+------------------------+
| Git diff clean    | app Synced/Healthy    | rollout available      |
| claim spec fixed  | XR Ready=True         | managed ref ready      |
| alert rule edited | rule loaded by stack  | alert state expected   |
| policy adjusted   | admission event clear | test object allowed    |
+-------------------+-----------------------+------------------------+
```

Which approach would you choose here and why: if the repository diff is correct but the workload is still old, would you inspect the workload first, the GitOps application first, or the controller logs first? A strong answer starts with the GitOps application because it connects the desired state to the live state. If the application is out of sync, you know reconciliation is the immediate issue. If it is synced and healthy, then the workload selector, namespace, image tag, or prompt interpretation may be wrong.

Verification also has a cost, so choose evidence that is specific enough without becoming a research project. `kubectl get events -A` is useful for broad orientation, but a completed task usually needs a narrower check: the named application health, the named claim condition, the named deployment rollout, the named policy report, or the named alert. Broad checks find direction; narrow checks prove completion.

```bash
kubectl get deployment -A
kubectl get pods -A --field-selector=status.phase!=Running
kubectl get events -A --sort-by=.lastTimestamp | tail -n 20
kubectl auth can-i list pods --all-namespaces
```

Do not confuse "no error appeared" with verification. Some controllers reconcile slowly, some policies audit without blocking, and some telemetry systems lag behind the change. If a task asks for readiness, look for readiness. If it asks for enforcement, test admission or inspect policy results. If it asks for delivery, prove both sync and workload health. This is why a scratchpad entry should include the planned proof, not just the planned command.

The fastest candidates verify quickly because they have practiced evidence patterns in advance. They know that status conditions usually explain controller progress, that Kubernetes events often reveal admission and scheduling failures, that GitOps health and sync are separate, and that observability signals answer different questions. They are not faster because they type every command from memory. They are faster because they know what kind of proof each domain requires.

Verification should also be phrased in terms of the prompt, not the command you happened to run. If the prompt asks for a staging promotion, the proof is not merely "the command succeeded"; it is "the staging application is synced to the requested version and the workload is available." If the prompt asks for self-service provisioning, the proof is "the claim and its composite resource report readiness and reference the expected resources." This phrasing keeps you from accepting weak evidence because it is convenient.

Be careful with green dashboards and empty outputs. A green view may be stale, filtered, or unrelated to the task, and an empty output may mean no events matched your query rather than no problem exists. Good verification names the object, namespace, signal, and expected condition when possible. When you cannot get a perfect proof, record the best available evidence and the limitation, then decide whether the task is safe to mark complete.

## Recover When a Task Starts Going Sideways

Even a disciplined workflow will hit uncertainty. The exam-relevant skill is not never getting stuck; it is recognizing the shape of being stuck early enough to recover. A task is sideways when you have made a change but cannot name the expected evidence, when each command opens a new branch of investigation, or when you are editing objects owned by a controller you have not identified.

The first recovery move is to stop changing state and rebuild the contract. Re-read the prompt, identify the desired end state, and inspect ownership. If GitOps owns the workload, live edits are temporary. If a platform API owns managed resources, direct patches may be overwritten. If a policy controller owns admission, a deployment failure may be a policy signal rather than a workload bug. Ownership tells you which changes will persist.

The second recovery move is to reduce scope. Instead of debugging the whole platform, choose one relationship to prove. Does the application point at the expected repository path? Does the claim reference the expected composition? Does the policy match the namespace? Does the alert query include the intended label? Does the service selector match the pods? Small proofs turn a vague problem back into a bounded task.

The third recovery move is to timebox honestly. Mark the task, capture the clue that matters, and move on if the next action is not clear. This is difficult because leaving a partially solved problem feels bad, but spending the next long block on it can cost more than the task is worth. Your scratchpad should make returning cheap: write the current object, the suspected owner, and the check you would run next.

```text
Task 4 return note:
Desired: claim Ready=True for team-a cache service.
Seen: claim exists, XR not Ready, composition ref cache-small.
Next check: describe XR and inspect resource refs before editing managed objects.
```

That note is enough. It preserves the mental stack without pretending you solved the issue. When you return, you can continue at the relationship that matters instead of repeating the same broad inspection. This discipline is especially important in CNPE because platform work naturally crosses many tools. Without a return note, a skipped task becomes expensive twice.

Recovery also includes knowing when not to change a platform control. Weakening a policy, disabling automation, or deleting a controller-owned object can create more cleanup than the original issue. In a practice lab, these actions may seem harmless. In an exam, they can damage later tasks that depend on the same platform behavior. Prefer changes that satisfy the prompt while preserving the platform contract.

One recovery technique is to ask whether you are debugging cause, ownership, or evidence. Cause asks why the system is wrong. Ownership asks which component has authority to make it right. Evidence asks how you will know it is right. When a task feels tangled, you are often mixing those questions together. Split them apart and answer the missing one before typing another mutation command.

Another recovery technique is to switch from mutation commands to read-only commands until the shape is clear. Describe the object, inspect its conditions, list related events, check authorization, and confirm whether the expected API resource exists. Read-only commands are not a guarantee of safety, but they are much less likely to create cleanup debt. In a timed exam, avoiding cleanup debt is a real performance advantage.

Finally, treat skipped tasks as inventory. At the halfway point of a practice session, scan your return notes and group them by domain. If three skipped tasks are all GitOps path issues, solve the clearest one first because the answer may teach you the repository layout for the others. If skipped tasks span unrelated domains, choose the one with the most specific next check. This turns return work into prioritization instead of panic.

## Patterns & Anti-Patterns

Patterns and anti-patterns turn the workflow into habits you can recognize under pressure. The most useful CNPE patterns are not exotic; they are reliable ways to preserve system ownership while moving quickly. The anti-patterns are attractive because they produce visible motion, but they hide whether the platform will keep the state you created.

| Pattern | When to Use | Why It Works | Scaling Consideration |
|---------|-------------|--------------|-----------------------|
| Read-act-verify loop | Every task, especially mixed-domain prompts | It ties each edit to a desired state and a proof | Keep each loop small so failures identify one assumption |
| Source-of-truth first | GitOps, platform API, and policy tasks | It prevents live fixes from fighting controllers | Confirm ownership before editing shared or generated objects |
| Evidence ladder | Asynchronous reconciliation and operations tasks | It separates source, controller, and outcome evidence | Record the proof in your scratchpad so you can resume quickly |
| Three-pass pacing | Timed practice and full exam simulation | It banks easy points before fragile work consumes attention | Revisit skipped tasks with a short return note, not a full restart |

| Anti-pattern | What Goes Wrong | Why Teams Fall Into It | Better Alternative |
|--------------|-----------------|------------------------|--------------------|
| Live-editing GitOps-managed resources | The controller reverts the change or creates a diff you do not expect | The live object is visible and feels closer than the repository | Identify the application source path, edit Git, then verify sync and health |
| Debugging managed resources before the platform API | You fix a symptom while the claim or composition remains invalid | Cloud or workload resources show concrete errors first | Start at the user-facing claim, follow references, then inspect managed resources |
| Treating the first signal as the root cause | One log or event sends you into the wrong subsystem | Urgent signals feel more trustworthy than quiet status fields | Combine one source signal with one reconciliation or ownership check |
| Weakening policy to make a workload pass | You create broad risk and may break later security tasks | A denied request looks like an obstacle instead of feedback | Confirm match scope, mode, and intended exception before changing enforcement |

These patterns scale beyond the exam because they are ordinary platform engineering practices. Internal developer platforms succeed when contracts are explicit, controllers own reconciliation, and teams can prove outcomes without tribal knowledge. CNPE simply compresses those habits into a timed setting. If your practice workflow would be dangerous in a real platform, it is probably a poor exam workflow too.

The strongest pattern is consistency across domains. A delivery task, a self-service task, and a policy task look different on the surface, but all three can be handled with the same mental loop: classify the contract, change the owning layer, and prove the result. When you practice that loop, the exam becomes less about remembering a pile of unrelated tools and more about applying one operating model to several platform surfaces.

## Decision Framework

Use this framework whenever a CNPE task is ambiguous. The goal is not to force every prompt into a rigid category; the goal is to choose a first lever that respects ownership and gives you quick evidence. Start with the noun the prompt cares about, then follow the source of truth to the controller or API that should make the noun true.

```text
+-----------------------------+
| What changed or failed?      |
+-------------+---------------+
              |
              v
+-----------------------------+
| Is Git the desired state?    |
+------+----------------------+
       | yes
       v
  GitOps path -> sync/health -> rollout proof
       |
       no
       v
+-----------------------------+
| Is there a platform API?     |
+------+----------------------+
       | yes
       v
  claim/XR -> composition refs -> ready proof
       |
       no
       v
+-----------------------------+
| Is the issue operational?    |
+------+----------------------+
       | yes
       v
  signal -> owner -> bounded fix -> signal proof
       |
       no
       v
  policy/RBAC/object scope -> admission or access proof
```

The framework deliberately asks about Git before live cluster editing because GitOps is a major CNPE domain and a common platform source of truth. It asks about platform APIs before managed resources because self-service abstractions are supposed to hide implementation details until you need them for diagnosis. It asks about operations and policy last because those tasks often look like generic Kubernetes debugging until you identify the owning control.

| If the prompt says | Prefer this first lever | Verify with | Avoid |
|--------------------|-------------------------|-------------|-------|
| "promote", "sync", "rollback" | repository state and GitOps application | diff, sync, health, rollout | direct live patch without checking ownership |
| "self-service", "claim", "template" | claim, XR, XRD, composition | conditions and resource refs | editing generated resources first |
| "alert", "latency", "error budget" | telemetry query and owning workload | signal changes and workload state | relying on one log line as proof |
| "deny", "audit", "policy" | policy scope, mode, and test object | admission result or policy report | disabling enforcement globally |
| "permission", "access" | RBAC subject, verb, resource, namespace | `kubectl auth can-i` | adding broad cluster-admin style access |

Use the decision framework with humility. If evidence contradicts your first classification, reclassify the task instead of forcing the original plan. A prompt that begins with a rollout failure may become a policy task when admission events show denied pods. A prompt that begins with a claim may become a GitOps task when the claim manifest is generated from a repository path. Good strategy is not stubborn; it is structured enough to change direction quickly.

You can also use the framework after a task, not only before it. After you mark a task complete, ask whether your evidence touched the right branch of the decision tree. If you classified a problem as GitOps but never checked sync or health, your proof is weak. If you classified a problem as policy but never tested admission or inspected a report, your proof is weak. This quick review catches incomplete work while the task context is still warm.

The framework is intentionally small enough to memorize, but your implementation should be written down during practice. Build a one-page checklist with the branches, common evidence commands, and a few warning signs for each domain. Then use it until you can classify tasks without staring at it. The point is not to carry a perfect checklist into the exam. The point is to train a repeatable decision path before the timer makes improvisation expensive.

## Did You Know?

- CNPE is a 120-minute, online, proctored, performance-based exam; cost is $445 with one free retake, so time management is part of the tested skill rather than an afterthought.
- The official CNPE exam blueprint weights five domains as follows:

| Domain | Weight |
|---|---|
| Platform Architecture and Infrastructure | 15% |
| GitOps and Continuous Delivery | 25% |
| Platform APIs and Self-Service Capabilities | 25% |
| Observability and Operations | 20% |
| Security and Policy Enforcement | 15% |

  GitOps and platform APIs together account for half the blueprint, which means source-of-truth and abstraction work are central to the exam.
- Kubernetes custom resources extend the Kubernetes API, so a platform API built on CRDs can be inspected with ordinary API habits even when the underlying resources are complex.
- OpenTelemetry groups telemetry into signals such as traces, metrics, and logs (with baggage for cross-service context), which is a useful mental model when choosing evidence for operations tasks.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Starting with the hardest task | The first confusing prompt feels urgent, and candidates want relief before moving on | Sweep obvious low-risk tasks first, mark hard tasks with a return note, and protect time for later passes |
| Editing blindly | The live object is visible, but the controller, repository path, or platform API owner has not been identified | Name the desired end state, source of truth, and verification command before changing anything |
| Treating docs as enough | Reading creates recognition, but CNPE rewards recall, sequencing, and proof under time pressure | Rehearse full terminal workflows and require every practice task to end with evidence |
| Not timeboxing a stuck task | A partially solved problem creates sunk-cost pressure and keeps expanding | Stop after a bounded inspection, write the next useful check, and move to a task with clearer evidence |
| Skipping post-change checks | YAML can look correct while reconciliation, admission, or rollout still fails | Verify source, controller acceptance, and final outcome before marking the task done |
| Using a comfortable but unrealistic practice setup | Familiar aliases, namespaces, and open-ended time hide environment friction | Practice with explicit contexts, full commands, a scratchpad, and timed domain switches |
| Weakening policy or access too broadly | A narrow denial looks like a blocker, so candidates remove the guardrail instead of fixing scope | Confirm audit versus enforce mode, match conditions, and intended exception before changing controls |

## Quiz

1. Your first CNPE task says a service must be promoted to staging, and you see both a Git repository and a running Deployment with the old image. What should you inspect first?

A. Patch the Deployment image directly because the live object is the fastest lever.
B. Inspect the GitOps application and repository path that owns the desired state.
C. Restart the pods so the controller pulls the newest image automatically.
D. Change the policy engine because image promotion is usually blocked by admission.

<details>
<summary>Answer and reasoning</summary>

B is the best first move because the prompt language points to promotion, which usually belongs to the GitOps source of truth. If the application owns the Deployment, a direct patch in A may be reverted or create a drift that does not satisfy the task. C guesses at a runtime symptom without proving the desired image changed. D is possible only if evidence shows admission is blocking the promotion, so it should not be the first lever.

</details>

2. A platform API claim is present in the application namespace, but the managed resource behind it is not ready. Which investigation path best preserves the platform contract?

A. Delete and recreate the managed resource so it gets a clean start.
B. Patch the provider-owned resource until it reports ready.
C. Inspect the claim, composite resource, composition reference, and resource refs in order.
D. Ignore the claim and search all controller logs for generic errors.

<details>
<summary>Answer and reasoning</summary>

C is correct because platform APIs intentionally separate the user-facing request from the managed implementation. The claim and composite resource conditions usually explain whether the platform accepted the request and where reconciliation failed. A and B may fight the controller and leave the invalid contract unchanged. D can be useful later, but broad log searching before following references wastes time and weakens diagnosis.

</details>

3. During pass one, a task looks simple but you cannot identify the namespace or source of truth after an initial inspection. What should you do?

A. Keep exploring until the task is solved because switching tasks wastes context.
B. Make a broad cluster change that is likely to cover multiple namespaces.
C. Mark a concise return note and move to clearer quick-win tasks.
D. Skip all verification so you can recover time on the next task.

<details>
<summary>Answer and reasoning</summary>

C is the disciplined choice because pass one exists to bank low-risk points, not to solve every ambiguous task immediately. A creates sunk-cost pressure and can consume the exam before easier work is done. B is unsafe because broad changes can break unrelated tasks. D saves a few seconds while increasing the chance that incomplete work is counted as done.

</details>

4. You changed a values file for a GitOps-managed workload, and the workload still shows the old replica count. Which evidence chain is strongest?

A. Local file changed, GitOps app synced and healthy, rollout status shows desired replicas.
B. Local file changed, terminal prompt returned successfully, no one complained.
C. Deployment patched live, pods restarted, Git repository still differs from the cluster.
D. Events are quiet, so the change is automatically complete.

<details>
<summary>Answer and reasoning</summary>

A is strongest because it covers source evidence, reconciliation evidence, and outcome evidence. B proves only that a local edit occurred and says nothing about the platform accepting it. C may produce a temporary live state while violating GitOps ownership. D treats absence of noise as proof, but quiet events do not prove desired state or rollout health.

</details>

5. A policy task says new workloads in a namespace should be audited but not blocked. A test pod is denied. What is the best first diagnosis?

A. Confirm policy mode, match scope, namespace labels, and the event or policy report.
B. Delete the policy so the pod can start and the task is unblocked.
C. Grant yourself broader permissions because admission failures are usually RBAC issues.
D. Patch the pod repeatedly until one version slips through admission.

<details>
<summary>Answer and reasoning</summary>

A is correct because the prompt distinguishes audit from enforce behavior, and the denial means the policy or scope may not match the intended mode. B removes the control instead of fixing it and can affect other tasks. C confuses admission with authorization without evidence. D is trial-and-error editing that may hide the actual policy mistake.

</details>

6. An observability task shows an alert firing after a deployment change. Which verification approach is most exam-ready?

A. Read one application log line and assume it explains the alert.
B. Combine the alert query or state with the owning workload status and one relevant signal.
C. Disable the alert so the dashboard becomes green.
D. Restart the monitoring stack before checking labels or queries.

<details>
<summary>Answer and reasoning</summary>

B is best because observability work needs evidence that connects the signal to the owning system. A may be useful but is too narrow to prove the alert condition changed. C changes the symptom rather than the platform behavior. D adds risk and delays diagnosis before checking the simpler causes, such as labels, selectors, or rollout health.

</details>

7. You need to design a repeatable triage, execution, and verification workflow for CNPE practice. Which checklist gives the best preparation signal?

A. Confirm cluster context, repository status, scratchpad format, docs access, and one verification habit per domain.
B. Install many tools and assume the exam environment will match your workstation exactly.
C. Practice only by reading documentation until every command feels familiar.
D. Use personal command shortcuts in every script so practice feels faster.

<details>
<summary>Answer and reasoning</summary>

A is correct because it trains the environment controls that matter under time pressure. Together, those controls form a repeatable triage workflow for a performance-based platform exam. B overfits to a workstation and may fail when the exam environment differs. C builds recognition but not recall, sequencing, or verification. D can be convenient interactively, but scripts and shared examples should use complete commands so they remain runnable and clear.

</details>

## Hands-On Exercise

Exercise scenario: build a personal CNPE exam workflow using three small tasks from this track or from your own platform lab. Choose one GitOps or delivery task, one platform API or self-service task, and one observability, security, or operations task. The objective is not to create a perfect lab environment; the objective is to practice classification, pacing, and evidence collection until the rhythm feels repeatable.

### Setup

Use a cluster or sandbox where you can safely inspect resources, and use a repository that contains at least one Kubernetes or platform manifest. If you do not have Argo CD, Crossplane, Kyverno, or Gatekeeper installed, you can still complete the exercise by writing the classification and verification plan for those domains. The practice value comes from choosing the source of truth and proof, not from pretending every tool is present.

```bash
git status --short
kubectl config current-context
kubectl get namespaces
kubectl get events -A --sort-by=.lastTimestamp | tail -n 10
```

### Tasks

- [ ] Pick three tasks and classify each one as GitOps, platform API, observability, security, or operations before running any change command.
- [ ] For each task, write the desired end state, smallest safe change, and verification command in a scratchpad.
- [ ] Solve the easiest task first, then the medium task, then the most fragile task, using a timer for each pass.
- [ ] After each change, collect source evidence, reconciliation or controller evidence, and final outcome evidence where applicable.
- [ ] Write one return note for any task that becomes unclear instead of continuing open-ended investigation.
- [ ] Review the session and identify one environment habit that slowed you down.

<details>
<summary>Solution guidance</summary>

A strong solution has three short scratchpad entries rather than a long narrative. For a GitOps task, the entry should name the repository path, application or controller, and rollout or health proof. For a platform API task, it should name the claim or custom resource, the controller-owned relationship you inspected, and the readiness evidence. For an observability, security, or operations task, it should name the signal, the owning component, and the evidence that changed after your action.

</details>

### Success Criteria

- [ ] You can finish all three tasks without getting stuck on the first one.
- [ ] Each task has a clear verification command or evidence source.
- [ ] You can explain why you chose the order you used.
- [ ] You can identify which task belonged in Git, the platform API, or the cluster.
- [ ] You can show at least one source, reconciliation, and outcome proof from the session.

<details>
<summary>Example scratchpad</summary>

```text
Task A: GitOps delivery
Desired: staging service uses image tag from prompt.
Lever: edit values file in repo path shown by application source.
Proof: app synced and healthy, deployment rollout complete.

Task B: Platform API
Desired: cache claim Ready=True.
Lever: fix claim parameter after checking XR condition.
Proof: claim and XR ready, resource refs present.

Task C: Security
Desired: namespace audited, not blocked.
Lever: adjust policy mode or namespace selector after confirming event.
Proof: test pod admitted and policy report records audit result.
```

</details>

## Sources

- https://www.cncf.io/training/certification/cnpe/
- https://www.cncf.io/training/certification/
- https://kubernetes.io/docs/reference/kubectl/quick-reference/
- https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
- https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
- https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_wait/
- https://docs.crossplane.io/latest/composition/composite-resource-definitions/
- https://docs.crossplane.io/latest/composition/composite-resources/
- https://opentelemetry.io/docs/concepts/signals/
- https://kyverno.io/docs/policy-types/cluster-policy/validate/
- https://open-policy-agent.github.io/gatekeeper/website/docs/
- https://dora.dev/capabilities/trunk-based-development/

## Next Module

Continue with [CNPE GitOps and Delivery Lab](../module-1.2-gitops-and-delivery-lab/), where the abstract workflow becomes a timed, hands-on delivery scenario.
