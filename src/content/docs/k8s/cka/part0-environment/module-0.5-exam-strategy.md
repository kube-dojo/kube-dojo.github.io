---
citations_verified: true
revision_pending: false
title: "Module 0.5: Exam Strategy - Three-Pass Method"
slug: k8s/cka/part0-environment/module-0.5-exam-strategy
sidebar:
  order: 5
lab:
  id: cka-0.5-exam-strategy
  url: https://killercoda.com/kubedojo/scenario/cka-0.5-exam-strategy
  duration: "15 min"
  difficulty: beginner
  environment: ubuntu
---

> **Complexity**: `[MEDIUM]` - Long-form strategy module with timed practice and planning drills
>
> **Time to Complete**: 20-30 minutes to learn, repeated timed practice to internalize
>
> **Prerequisites**: Modules 0.1-0.4, a working shell, and basic comfort running `kubectl` commands
>
> **Kubernetes Version Target**: 1.35+

---

## Learning Outcomes

After this module, you will be able to:

- **Apply** the Three-Pass Method to prioritize CKA tasks by score, complexity, and remaining time.
- **Triage** exam questions into quick, medium, and complex work before committing to a solution path.
- **Evaluate** point-per-minute tradeoffs when multiple unfinished questions compete for limited time.
- **Design** a repeatable question-start routine that protects against wrong-context and wrong-namespace mistakes.
- **Recover** from stuck troubleshooting tasks by preserving partial credit and moving to higher-confidence work.

---

## Why This Module Matters

Hypothetical scenario: you start the CKA with enough Kubernetes knowledge to create Deployments, repair a broken image, inspect RBAC, and read the official documentation without panic. The first question is a noisy node troubleshooting task, so you spend the opening stretch chasing kubelet symptoms while the timer keeps moving. When you finally look ahead, several smaller questions are waiting: a namespace, a ConfigMap, a Service exposure, and an output file. You did not fail because you lacked Kubernetes skill; you failed because the exam forced operational prioritization before you had a plan for it.

The CKA is a live performance exam, which means your answer is the cluster state you leave behind. A grader does not care that you almost solved a hard diagnostic task if three easy resources were never created in the correct context. That pressure is uncomfortable because real engineers are trained to finish the problem in front of them, yet timed exams reward the same discipline used in incident response: protect high-confidence fixes, time-box uncertainty, and keep visible progress ahead of private effort.

This module teaches the Three-Pass Method as a repeatable control system for that pressure. Pass 1 banks fast, familiar, verifiable work. Pass 2 handles standard multi-step tasks that need manifests, documentation, or relationship checks. Pass 3 spends the remaining time on troubleshooting and complex repair, where uncertainty is higher but partial credit can still be valuable. You will practice the strategy with the same assets this module has always used: context checks, namespace discipline, output-file tasks, RBAC, NetworkPolicy, PVCs, Deployment troubleshooting, and a small timed mock exam.

## Part 1: Apply The Three-Pass Method Before The Clock Starts Thinking For You

The clock is visible during the exam, but the deeper threat is decision fatigue. Every question asks you to decide which context to use, whether the namespace exists, whether the task is direct or diagnostic, when to consult documentation, and when to stop polishing. Those decisions are small individually, yet they accumulate while your hands are on the keyboard. The Three-Pass Method exists so most of the important timing decisions are made by a routine rather than by stress.

A linear exam path feels fair because it resembles schoolwork: read Question 1, solve Question 1, then move to Question 2. That habit breaks down when question order does not match point return, familiarity, or verification cost. A two-minute label task and a multi-branch node repair can sit next to each other, but they should not automatically receive the same opening attention. Strategy is the act of separating question order from work order.

```ascii
+----------------------+------------------------+-------------------------+
| Linear Exam Thinking | What Actually Happens  | Strategic Correction    |
+----------------------+------------------------+-------------------------+
| Start at Question 1  | Early hard task stalls | Scan all questions      |
| Finish before moving | One bug eats minutes   | Time-box aggressively   |
| Treat tasks equally  | Points are uneven      | Compare point return    |
| Perfect each answer  | Optional polish grows  | Meet requirements only  |
| Review at the end    | No time remains        | Verify during each task |
+----------------------+------------------------+-------------------------+
```

The first pass is not about rushing, and it is not about ignoring hard questions. It is about protecting the questions whose solution path is familiar and whose verification path is short. If one question asks for a namespace and a ConfigMap, that is likely a reliable early win. If another question says a workload cannot reach a Service, the first few minutes may only reveal the next diagnostic branch. Both questions matter, but only one should usually be solved before you know the rest of the exam.

**Pause and predict:** imagine the first question is a noisy node troubleshooting task worth slightly more than the second question, which asks you to create a Service for an existing Deployment. Which one would you attempt first after completing your initial exam scan, and why?

<details>
<summary>Check your prediction</summary>

Bank the Service first because its solution path and verification pattern carry low uncertainty, allowing you to secure reliable points in minutes before starting the investigation. Do not chase highest points first when an open-ended troubleshooting scenario risks consuming half your exam clock before routine work is banked.

</details>

Securing deterministic points early builds a cushion of verified score, ensuring that an unexpected diagnostic blocker on a broken worker node cannot jeopardize your entire exam attempt.

The passing score changes the mindset as well. You are not trying to produce a museum-quality cluster, and you are not trying to prove that you can solve every hard task in the order presented. You are trying to produce enough correct, verified state across enough questions. That means partial progress on a hard task can be useful, but only after you have not sacrificed predictable tasks that could have been completed and verified quickly.

The Three-Pass Method is also compatible with real professional judgment. During an incident, experienced operators first stabilize what is obviously wrong, then handle standard repair paths, and finally spend deeper time on uncertain root causes. The exam compresses that operating model into a timed lab. Treating it as triage instead of as a sequence of isolated puzzles makes the environment feel less mysterious and gives every minute a job.

The method also gives you a way to recover from nerves. When candidates panic, they often start inventing new workflows during the exam: a different note format, a different way to search documentation, a different command style, or a new habit of editing YAML by hand. That experimentation is expensive because it adds process uncertainty on top of Kubernetes uncertainty. A practiced pass order lets you return to a known routine whenever a question feels bigger than expected.

## Part 2: Triage Exam Questions Into Quick, Medium, And Complex Work

Triage begins by estimating three properties: expected time, predictability, and verification shape. A quick task is not merely short; it is short because the command pattern is familiar and the expected output is obvious. A medium task is not merely longer; it usually contains relationships that must line up across fields, resources, or namespaces. A complex task begins with symptoms, so the first action is evidence gathering rather than direct construction.

The labels `[QUICK]`, `[MEDIUM]`, and `[COMPLEX]` are not judgments about whether you are good at Kubernetes. They are planning categories for this exam attempt. A candidate with strong RBAC fluency may treat a RoleBinding as medium and finish it quickly, while another candidate may need documentation every time. The strategy remains the same: do not let uncertain work block predictable work unless the point value and your confidence justify the tradeoff.

| Category | Typical Time | Common Signals | Verification Shape |
|----------|--------------|----------------|--------------------|
| `[QUICK]` | 1-3 minutes | Create, scale, label, annotate, expose a familiar object | One `kubectl get` or `kubectl describe` confirms the result |
| `[MEDIUM]` | 4-6 minutes | RBAC, PVC, NetworkPolicy, ConfigMap usage, simple scheduling rule | Manifest plus object inspection confirms the result |
| `[COMPLEX]` | 8-15 minutes | Troubleshoot, repair, debug, investigate, node or control-plane issue | Several diagnostic commands narrow the failure before a fix works |

A quick task usually has a direct imperative path. Creating a Pod, scaling a Deployment, labeling an object, exposing a Deployment, or writing selected object names to a file should have a short feedback loop. That loop is valuable because it closes the question while the requirement is still fresh in your working memory. The moment you need multiple documentation pages or several diagnostic branches, the question has stopped behaving like Pass 1 work.

A medium task usually has more than one moving part. RBAC requires the subject, Role, RoleBinding, verbs, resources, and namespace to agree. NetworkPolicy requires you to distinguish the protected Pods from the allowed sources. A PVC requires access modes and storage requests in the correct object. None of those tasks are inherently mysterious, but each contains enough structure that typing from memory can create subtle mistakes.

A complex task usually starts with a symptom rather than a desired object. Pods are pending, DNS resolution fails, a node is not ready, a rollout is stuck, or an application cannot reach a Service. You must observe, form a hypothesis, change one thing, and verify. That uncertainty is why complex tasks usually belong in Pass 3, after the predictable work has stopped competing for the same time.

```ascii
+-------------------+       +----------------------+       +--------------------+
| Read Question     | ----> | Estimate Work Type   | ----> | Choose Pass        |
+-------------------+       +----------------------+       +--------------------+
        |                              |                              |
        v                              v                              v
+-------------------+       +----------------------+       +--------------------+
| Context Required  |       | Predictable Command  |       | Pass 1: Quick      |
| Namespace Needed  |       | Documented Manifest  |       | Pass 2: Medium     |
| Output File Path  |       | Diagnostic Unknown   |       | Pass 3: Complex    |
+-------------------+       +----------------------+       +--------------------+
```

Before running this, what output do you expect from your own categorization? Take three example tasks: create a Secret and mount it into a Pod, fix a kubelet that will not start, and write all Pod names with label `tier=frontend` into a file. The Secret task is usually medium because it combines object creation with Pod configuration. The kubelet task is complex because the cause is unknown. The output-file task is quick because the command and verification are direct.

A useful exam habit is to update the category when new evidence appears. A task that looked quick can become medium if the namespace is unexpected, the target object has different labels than the prompt implies, or the requested output format is precise. That update is not a failure; it is exactly what triage is supposed to do. You noticed reality early enough to move the task to a later pass instead of letting it silently consume the opening minutes.

The reverse can happen too. A task that looked complex from its title may become medium once events reveal a single obvious cause, such as an invalid image tag or a missing selector. Do not keep a task in Pass 3 just because you initially labeled it complex. Triage is a living estimate. The discipline is to revise the estimate based on evidence, then compare the newly estimated work against the rest of the unfinished exam.

## Part 3: Protect Predictable Points With Pass 1

Pass 1 starts with a scan, not with a solution command. You read enough of each question to identify the context, namespace, resource type, output path, point value if shown, and likely category. You are building a map of the work, not solving it yet. The scan feels expensive only if you measure it as idle time; in practice it prevents the more expensive mistake of discovering easy questions after difficult ones have already spent the clock.

A good Pass 1 task has a short command path and a short verification path. The task might ask for a namespace, Pod, Deployment scale change, label, annotation, ConfigMap, Secret, or Service exposure. These tasks are attractive early because they can be completed with complete commands, verified immediately, and then mentally closed. You should not carry them as unfinished background noise while debugging a harder problem.

```bash
# Quick example: create a namespace, then verify it exists.
kubectl create namespace production
kubectl get namespace production
```

The example is intentionally plain because exam commands should be copy-paste runnable in ordinary shells. Many engineers use a short alias for `kubectl` interactively, but aliases do not expand in non-interactive shell scripts and are easy to forget under pressure. In this curriculum, runnable shell blocks use the full `kubectl` binary name. That makes the command longer, but it makes the example unambiguous and safer for learners who paste blocks into practice scripts.

```bash
# Quick example: create a Pod in a specified namespace, then verify readiness.
kubectl run web --image=nginx:1.25 -n production
kubectl get pod web -n production
```

```bash
# Quick example: scale a Deployment and confirm the desired replica count.
kubectl scale deployment api --replicas=3 -n production
kubectl get deployment api -n production
```

```bash
# Quick example: expose a Deployment and inspect the Service object.
kubectl expose deployment api --port=8080 --target-port=8080 -n production
kubectl get service api -n production
```

Verification is part of the answer, not a separate review phase. If the grader expects a Pod in `production` and you created it in `default`, a fast `kubectl get` catches the mistake while the question is still loaded in your head. Immediate verification also reduces final-review pressure because you can trust completed work instead of reopening every question at the end.

| Pass 1 Habit | Why It Matters | Example Verification |
|--------------|----------------|----------------------|
| Switch context before every question | A correct solution in the wrong cluster earns no credit for the intended task | `kubectl config current-context` |
| Confirm namespace before creating resources | Many exam tasks are namespace-scoped and silently differ by location | `kubectl get ns target-ns` |
| Prefer imperative commands for simple objects | Imperative commands reduce YAML typing and syntax risk | `kubectl get pod web -n production` |
| Verify immediately after each change | Immediate checks catch mistakes while they are still cheap | `kubectl describe deployment api -n production` |

Pass 1 should feel almost mechanical. Read the task, switch context, confirm namespace, run the direct command, verify the required state, and move. Mechanical does not mean careless; it means you are using a routine to prevent pressure from turning simple work into improvisation. If a supposedly quick task asks for exact formatting, a hidden namespace, or unfamiliar flags, stop treating it as quick and return after better opportunities are banked.

The biggest Pass 1 risk is invisible drift. You begin with quick tasks, then one task has a small wrinkle, then that wrinkle turns into a search, then the search becomes a debugging session. Nothing dramatic happens, but the first pass has quietly disappeared. Protect Pass 1 by naming the checkpoint before you start: if a task stops being direct, leave it in a good partial state, make a note if the interface supports it, and continue.

## Part 4: Use Pass 2 For Standard Multi-Step Kubernetes Work

Pass 2 is where documented Kubernetes mechanics matter most. These tasks are not usually mysterious, but they contain enough fields that pure memory can be risky. You may create a Role and RoleBinding, mount a Secret, write a PVC, apply a NetworkPolicy, configure a probe, or wire a ConfigMap into a Pod. The exam skill is choosing the lowest-risk construction path and then verifying the relationship the grader cares about.

A strong Pass 2 workflow starts from a reliable pattern rather than a blank file. For RBAC, imperative commands often reduce typing and make the subject relationship explicit. For PVCs and NetworkPolicies, compact manifests can be safer because the nested fields matter. The best choice is not always the shortest command; it is the path that minimizes mistakes for the object in front of you.

```bash
# Worked example setup: create a namespace and a service account for an RBAC task.
kubectl create namespace secure
kubectl create serviceaccount app-sa -n secure
```

```bash
# Worked example: create a Role and bind it to the ServiceAccount.
kubectl create role pod-reader --verb=get,list,watch --resource=pods -n secure
kubectl create rolebinding app-sa-pod-reader --role=pod-reader --serviceaccount=secure:app-sa -n secure
```

```bash
# Worked example verification: prove the binding grants the intended access.
kubectl auth can-i list pods --as=system:serviceaccount:secure:app-sa -n secure
kubectl get role,rolebinding,serviceaccount -n secure
```

This RBAC example demonstrates the full cycle: create the objects, connect the subject to the permission, and verify the authorization result. The API server accepting an object is not the same as the task being correct. A RoleBinding can exist while pointing to the wrong ServiceAccount namespace, using the wrong Role name, or living in the wrong namespace. Pass 2 discipline means verifying the relationship, not only the object count.

NetworkPolicy is a classic Pass 2 topic because valid YAML can still express the opposite of what you intended. The policy below protects Pods selected by `spec.podSelector`, then allows ingress from Pods selected under `ingress.from`. If you reverse those selectors, the manifest still applies but the behavior fails the requirement. Read the traffic relationship in plain language before you apply the file.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: web
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

```bash
# Apply and inspect the NetworkPolicy after saving it as netpol.yaml.
kubectl create namespace web
kubectl apply -f netpol.yaml
kubectl describe networkpolicy allow-frontend-to-backend -n web
```

**Pause and predict:** before applying a NetworkPolicy manifest to your cluster, which Pods are protected by the rule and which Pods may initiate incoming traffic?

<details>
<summary>Check your prediction</summary>

Both `podSelector` (protected workloads) and `ingress.from` (authorized client Pods) must be verified. Checking only one side leaves the policy incomplete and risks either locking out intended traffic or leaving sensitive endpoints completely exposed.

</details>

Verifying label selector alignment before issuing the apply command prevents subtle network isolation bugs that otherwise demand painful diagnostic drills across multiple namespaces.

**Pause and predict:** you are six minutes into a medium task, and your next diagnostic step is still a guess. How should you reclassify the task now, and what action should you take?

<details>
<summary>Check your prediction</summary>

The task has become complex; move it to Pass 3 if untouched medium work remains on your exam dashboard. Banking accessible points across the rest of the cluster ensures that challenging edge cases never monopolize the minutes required to reach a passing score.

</details>

Establishing explicit time boundaries around medium-tier questions guarantees that unexpected configuration puzzles do not consume the valuable minutes required for routine cluster administrative tasks.

Documentation lookup belongs in Pass 2, but it needs a purpose. [Opening the Kubernetes documentation](https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed) to confirm the field name for a PVC or NetworkPolicy is a good use of time because you know what object you are building. Wandering through pages because you are unsure what the failure means is different; that is diagnosis, not construction. In timed practice, separate those two behaviors so you learn when documentation is accelerating work and when it is masking uncertainty.

## Part 5: Recover From Stuck Troubleshooting With Pass 3

Pass 3 is where the exam gives you permission to troubleshoot deeply because the predictable work is already protected. This changes the psychology of debugging. You are no longer spending every minute on a broken node while easy tasks remain untouched. You are spending remaining time on higher-uncertainty work because the risk-adjusted return now makes sense.

Good troubleshooting follows a loop: observe, hypothesize, change one thing, verify, and decide the next step. The loop matters because random fixes create new symptoms and burn time. A candidate who deletes Pods repeatedly may never notice an invalid image, missing Secret, failed scheduling constraint, or wrong Service selector. Evidence is faster than guessing when the problem space is broad.

```ascii
+-------------------+      +-------------------+      +-------------------+
| Observe Symptoms  | ---> | Form Hypothesis   | ---> | Make Small Change |
+-------------------+      +-------------------+      +-------------------+
         ^                                                   |
         |                                                   v
+-------------------+      +-------------------+      +-------------------+
| Decide Next Step  | <--- | Verify Result     | <--- | Inspect New State |
+-------------------+      +-------------------+      +-------------------+
```

Consider a Deployment whose Pods are in `ImagePullBackOff`. A weak approach is to delete Pods and hope the next replica behaves differently. A stronger approach is to inspect the Deployment, list the selected Pods, read events, identify the failing image, update the Deployment, and verify the rollout. The difference is not memorizing every failure mode; it is following a diagnostic loop that turns uncertainty into visible progress.

```bash
# Worked troubleshooting example: inspect the Deployment, Pod state, and recent events.
kubectl get deployment critical-app -n production
kubectl get pods -l app=critical-app -n production
kubectl describe pod -l app=critical-app -n production
kubectl get events -n production --sort-by='.lastTimestamp'
```

```bash
# If events show a bad image reference, update the image and watch the rollout.
kubectl set image deployment/critical-app critical-app=nginx:1.25 -n production
kubectl rollout status deployment/critical-app -n production
kubectl get pods -l app=critical-app -n production
```

Partial credit is not an excuse for sloppy work. It is a reason to make the most important correct state visible before time expires. If a question asks you to fix a broken workload and add resource limits, a running workload without the limits may be more valuable than carefully formatted limits on a Deployment that still cannot start. The exam rewards inspectable cluster state, so make the highest-value state true first.

Which approach would you choose here and why: with four minutes left, events clearly show a bad image, but the question also asks for resource requests and limits. The stronger first move is to fix the image and verify the rollout, because that resolves the main broken state and creates visible progress. If the rollout succeeds quickly, then add the resource fields. If it does not, you still have evidence and a focused next step rather than a half-edited manifest.

A senior operator also knows when to stop diagnosing. If a node issue could be kubelet configuration, container runtime state, disk pressure, or network reachability, you cannot explore every branch equally with only a few minutes left. Pick the branch best supported by the evidence, make one reversible or clearly required fix, verify, and then decide whether another task can still produce more certain points. Pass 3 is focused investigation, not unlimited curiosity.

Pass 3 is also where notes can help, as long as they stay brief. If you leave a troubleshooting task, record the last verified symptom and the next evidence-driven check, not a long essay. For example, "events show bad image, rollout not fixed yet" is useful because it tells your future self where to resume. A paragraph of speculation is less useful because it takes time to write and may anchor you to an early hypothesis after the evidence changes.

## Part 6: Design A Question-Start Routine For Context, Namespace, And Output Files

Wrong-context work is painful because it can look perfect in your terminal. You switch nothing, create the right object shape, verify it successfully, and move on. The grader then checks a different cluster context, and the answer earns nothing for the intended question. That failure is avoidable only if context switching is part of the first action for every question rather than a cleanup step at the end.

The safest question-start routine is short enough to repeat while nervous. Read the required context. Switch context. [Confirm the current context](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/). Identify the namespace. Confirm or create the namespace only when the task tells you to create it. Then solve the actual requirement and verify it in the same context and namespace. The routine costs seconds, but a wrong context can cost an entire question.

```bash
# Question-start routine: replace the context and namespace with the values from the task.
kubectl config use-context exam-cluster-a
kubectl config current-context
kubectl get namespace production
```

```ascii
+------------------------+
| Every Question Starts  |
+------------------------+
| 1. Read context        |
| 2. Switch context      |
| 3. Confirm context     |
| 4. Check namespace     |
| 5. Solve requirement   |
| 6. Verify result       |
+------------------------+
```

Namespaces deserve the same discipline. [Many Kubernetes objects are namespace-scoped](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/), and `default` is rarely a safe exam assumption. A Pod named `web` in `default` does not satisfy a task that asked for `web` in `production`. If you create an object in the wrong namespace, recreate it correctly first. Delete the accidental object only when cleanup is safe and does not steal time from required work.

Output-file questions look easy, yet they are easy to lose through small formatting mistakes. If the task asks for a file path, create exactly that path. If it asks for names only, suppress headers. If it asks for sorted output, sort the output before writing it. These questions are often excellent Pass 1 wins because verification is simple: print the file and compare the content shape to the prompt.

```bash
# Example: output Pod names with a label selector to an exact file path.
kubectl get pods -l tier=frontend -o custom-columns=NAME:.metadata.name --no-headers > /tmp/frontend-pods.txt
cat /tmp/frontend-pods.txt
```

The best question-start routine is boring because it removes improvisation. You do not need a new plan for every cluster context or namespace. You need the same small ritual repeated until it is automatic: context, namespace, solve, verify. That habit is not only for exams; it is also how production engineers avoid changing the wrong cluster during real maintenance.

Treat output files as part of the same routine. Many candidates think of file tasks as shell trivia, but they are really precision tasks: the path, headers, sorting, and object scope all matter. A command that prints the right data to the terminal but forgets the requested file is not requirement-complete. A file with an extra header line can fail a strict check even though the Kubernetes query was correct. Read the output shape as carefully as you read the resource name.

## Part 7: Evaluate Point-Per-Minute Tradeoffs

Point value matters, but raw point value is not enough. A high-value task that might take the rest of the exam can be worse than two smaller tasks with short verification paths. The useful question is not simply which task is worth the most. The useful question is which task is likely to produce the most verified credit per minute from your current position.

This calculation is partly emotional control. Hard tasks are sticky because they feel personal, especially when you are close to solving them. The exam does not reward interesting struggle; it rewards enough required state across the cluster. If another task can produce certain points faster, your strategy should beat your curiosity. A deliberate skip is not giving up; it is moving work to the right pass.

```ascii
+------------------+----------------------+-----------------------------+
| Time Remaining   | Best Use             | Usually Avoid               |
+------------------+----------------------+-----------------------------+
| 90+ minutes      | Finish quick tasks   | Deep troubleshooting first   |
| 45-90 minutes    | Medium tasks         | Optional polish             |
| 15-45 minutes    | Complex or leftovers | Starting vague rabbit holes  |
| 0-15 minutes     | Verify and quick fix | New multi-branch diagnosis   |
+------------------+----------------------+-----------------------------+
```

Set decision checkpoints before starting medium or complex work. For a medium task, ask after several minutes whether the remaining work is obvious and verifiable. For a complex task, ask after each diagnostic loop whether the next step is evidence-driven or guess-driven. If the next step is mostly guessing and other questions remain, move on while the time still has somewhere better to go.

Stop and decide: you have 18 minutes left, one 9-point troubleshooting task untouched, one 5-point PVC task untouched, and one 4-point output-file task untouched. Write your order before reading further. A strong order is output file, PVC, then troubleshooting, because the first two tasks are highly verifiable and together match the value of the uncertain task. If the troubleshooting task turns out to be simple, you still reach it with banked points behind you.

Point-per-minute thinking does not remove judgment. You can still choose a high-value complex task earlier when you are unusually confident and the remaining work is low value or already verified. The important part is that the choice is explicit. Question order should not accidentally decide how you spend the only minutes that can produce score.

The calculation becomes easier if you think in expected value instead of pride. A task worth many points but only half likely to finish quickly may be a worse choice than a smaller task you can complete with high confidence. You do not need a formal formula during the exam. You only need to ask whether the next few minutes are likely to create verified state. If the honest answer is no, the task should wait unless everything easier is done.

## Part 8: Requirement-Complete Is Good Enough

Good enough does not mean careless. It means the solution satisfies the stated requirements and has been verified. In production systems, you may add labels, probes, resource defaults, dashboards, comments, and policy checks because long-term maintenance matters. In the exam, unstated improvements can consume time and sometimes introduce errors. Requirement-complete is the target because the grader evaluates requested state.

A common perfectionist trap is overbuilding manifests. If the task asks for a Deployment with three replicas and a specific image, you do not need probes, resource limits, affinity, annotations, and comments unless the prompt asks for them. Optional best practices are valuable in real systems, but they do not compensate for missing required fields. A clean minimal answer that meets the prompt is stronger than an elegant answer that forgets the namespace.

```bash
# Requirement-complete answer: create a Deployment with three replicas using the requested image.
kubectl create deployment web --image=nginx:1.25
kubectl scale deployment web --replicas=3
kubectl rollout status deployment/web
```

```bash
# Verification focuses on the stated requirement, not on cosmetic YAML quality.
kubectl get deployment web -o jsonpath='{.spec.replicas}{"\n"}'
kubectl get deployment web -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Requirement-complete also applies to partial credit. If a multi-part task asks for a ServiceAccount, Role, RoleBinding, and Pod using that ServiceAccount, create and verify as many correct pieces as possible in the correct namespace. Leaving a partially correct object graph is usually better than deleting everything because the final Pod did not start. The grader can only score what exists.

This mindset mirrors incident response. Stabilizing traffic may matter more than discovering the deepest root cause during the opening minutes of an outage. Once users are no longer affected, the team can investigate the underlying defect. The exam compresses that habit into a timed environment: secure what works, reduce uncertainty, and spend remaining time where it can still change the outcome.

Requirement-complete answers are easier to trust when you verify the exact field the prompt named. If the prompt asks for three replicas, read `.spec.replicas`; if it asks for an image, read the container image; if it asks for a Service port, inspect the Service port and targetPort. Broad commands such as `kubectl get all` can be useful for orientation, but they are rarely the strongest proof. Precise verification keeps your confidence tied to the requirement rather than to a general feeling that the object looks fine.

## Part 9: Worked Mini-Triage Across A Small Exam

Now combine the strategy into a miniature exam plan. Suppose you have four questions and 20 minutes. The tasks are to create a Pod, create a PVC, create a NetworkPolicy, and fix a Deployment whose Pods will not start. A linear candidate may still succeed if the order is friendly. A strategic candidate scans all four, categorizes them, and deliberately chooses the fastest path to verified state.

```ascii
+------------+----------------------------------------------+------------+----------------+
| Question   | Requirement                                  | Category   | Planned Pass   |
+------------+----------------------------------------------+------------+----------------+
| Q1         | Create Pod q1-pod running nginx               | QUICK      | Pass 1         |
| Q2         | Create NetworkPolicy for backend traffic      | MEDIUM     | Pass 2         |
| Q3         | Create PVC requesting 5Gi ReadWriteOnce       | MEDIUM     | Pass 2         |
| Q4         | Debug broken Deployment q4-broken             | COMPLEX    | Pass 3         |
+------------+----------------------------------------------+------------+----------------+
```

Pass 1 handles Q1 because it is direct and verifiable. The point value might not be the highest, but the confidence and speed are excellent. Completing Q1 also warms up the terminal and gives you an early success without stealing time from more complex work. That emotional benefit is secondary, but it matters when pressure is high.

```bash
kubectl run q1-pod --image=nginx:1.25
kubectl get pod q1-pod
```

Pass 2 handles Q3 and Q2. The PVC is shorter than the NetworkPolicy, so many candidates should do the PVC first. The NetworkPolicy follows once the namespace and selectors are clear. This order protects the easier medium task before the selector-heavy task, which has more ways to be valid YAML but wrong behavior.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: q3-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

```bash
kubectl apply -f q3-pvc.yaml
kubectl get pvc q3-pvc
```

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: q2-netpol
  namespace: web
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

```bash
kubectl create namespace web
kubectl apply -f q2-netpol.yaml
kubectl describe networkpolicy q2-netpol -n web
```

Pass 3 handles Q4 because the diagnostic path depends on evidence. The first commands inspect object state, selected Pods, detailed Pod events, and recent namespace events. If those observations point to a bad image, the fix is direct. If they point somewhere else, the same loop still gives you the next evidence-driven step instead of a random edit.

```bash
kubectl get deployment q4-broken
kubectl get pods -l app=q4-broken
kubectl describe pod -l app=q4-broken
kubectl get events --sort-by='.lastTimestamp'
```

```bash
kubectl set image deployment/q4-broken nginx=nginx:1.25
kubectl rollout status deployment/q4-broken
kubectl get pods -l app=q4-broken
```

This worked mini-triage demonstrates constructive alignment across the module. The learning outcome asks you to apply triage, the teaching activity shows categorization and ordering, and the quiz and lab ask you to make the same decision under different constraints. That is how you should practice: strategy first, commands second, verification always.

## Patterns & Anti-Patterns

Exam strategy improves when you can name the patterns you want to repeat and the anti-patterns you want to catch early. The table below is not a separate checklist to memorize during the exam. It is a way to recognize behavior while practicing so that your timing habits become visible. When a drill goes badly, usually one of these anti-patterns appeared before the command error did.

| Pattern Or Anti-Pattern | When It Appears | Better Exam Move |
|-------------------------|-----------------|------------------|
| Pattern: scan before solving | At the opening of the exam or any new section of tasks | Build a rough pass order before committing to deep work |
| Pattern: verify immediately | After every create, apply, scale, or repair command | Prove the exact requirement while the prompt is still fresh |
| Pattern: reclassify stuck work | When a quick or medium task starts requiring diagnosis | Move it to a later pass and protect higher-confidence work |
| Anti-pattern: first-question tunnel vision | A hard opening task feels like it must be finished before anything else | Skip after the scan if uncertainty is high and easier tasks exist |
| Anti-pattern: optional polish | A working answer tempts you to add unstated best practices | Stop at requirement-complete and verified state |
| Anti-pattern: end-only review | Verification is delayed until the final minutes | Review during each task so the final pass is for small checks |

Use these patterns during practice reviews rather than only on exam day. After a timed drill, mark where you scanned, where you verified, where you skipped, and where you should have skipped sooner. That feedback turns vague advice into calibration. The point is not to become rigid; the point is to make your judgment faster and more reliable while the timer is running.

Patterns also help you avoid overcorrecting after one bad drill. If you ran out of time because you skipped too late, the lesson is not to abandon every hard task immediately. The lesson is to set clearer checkpoints and compare unfinished work sooner. If you lost points because you skipped too aggressively, the lesson may be to improve verification and confidence estimates. A pattern language lets you improve the decision, not just blame the last command.

## Decision Framework

For a strategy module like this, the decision framework can stay simple: choose the next task by combining confidence, verification cost, and remaining time. If the task is familiar, direct, and easy to verify, it belongs early. If it needs several objects but the path is documented, it belongs in the middle. If it starts from symptoms or has many possible causes, it belongs late unless the point value and your confidence are unusually favorable.

| Decision Question | Choose Earlier When | Choose Later When |
|-------------------|---------------------|-------------------|
| Can I state the command or manifest shape before typing? | The command path is familiar and namespace/context are clear | You need several diagnostic steps before knowing the fix |
| Can I verify the result with one or two checks? | `kubectl get`, `describe`, `auth can-i`, or file output proves the answer | Verification requires traffic tests, logs, events, and several hypotheses |
| Does the work compete with easier unfinished tasks? | Similar-value tasks are already complete or lower confidence | Several predictable tasks remain untouched |
| Is partial credit likely to be visible? | Applying correct pieces improves cluster state even if incomplete | Most progress is private reasoning with little inspectable state |

The framework deliberately avoids a universal rule such as always solve highest points first. Highest-value-first can be correct when the task is familiar and the remaining list is small. It can also be disastrous when the high-value task is a multi-branch troubleshooting problem and several routine tasks are untouched. The right decision is risk-adjusted, not ego-adjusted.

During the final minutes, the framework becomes more conservative. Prefer verifying completed tasks, fixing small obvious errors, writing required files, and making visible partial progress. Avoid starting a new broad diagnosis unless all smaller opportunities are closed. The closer the timer gets to zero, the more valuable certainty becomes.

Use the same framework when reviewing practice logs. For each task, write the category you assigned, the category it became, the time you spent, and the verification that proved or failed the answer. After several drills, you will see patterns: maybe RBAC is consistently slower than expected, or output files are easy but frequently misformatted, or troubleshooting becomes efficient once you read events first. Those observations are the real payoff of timed practice because they turn a generic strategy into your personal exam plan.

## Did You Know?

- **The CKA is performance-based**: [Linux Foundation describes the certification as a hands-on exam](https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/), so the important artifact is the live cluster state you create rather than an explanation of what you intended.
- **[The current public passing score is 66%](https://docs.linuxfoundation.org/tc-docs/certification/faq-cka-ckad-cks)**: That threshold changes the strategy because complete perfection is less important than enough verified work across enough tasks.
- **The exam uses multiple tasks against real Kubernetes environments**: Context and namespace mistakes are costly because correct commands can still land in the wrong target.
- **Kubernetes documentation is large enough to become a time sink**: Knowing where to look is useful, but the Three-Pass Method keeps documentation lookup from replacing execution.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Starting immediately on the first question | The first question feels authoritative because it appears first, even if it is slow or ambiguous | Scan all questions first and build a pass order from confidence, value, and verification cost |
| Treating every task as equal | A two-minute object creation and a long diagnostic task both look like single questions in the interface | Compare predictability, point value, and expected verification time before choosing the next task |
| Forgetting to switch context | Correct work in the wrong cluster still looks correct in the terminal that created it | Make `kubectl config use-context` and `kubectl config current-context` part of every question-start routine |
| Ignoring namespaces | Namespace-scoped objects can be correct in one namespace and invisible to the grader in another | Read the namespace from the prompt and verify with `kubectl get` before creating resources |
| Overbuilding manifests | Real-world best practices tempt candidates to add fields the prompt did not request | Implement the requested state, verify it, and move optional improvements out of exam thinking |
| Staying stuck without a checkpoint | A task that was supposed to be medium gradually becomes troubleshooting without a decision | Reclassify stuck work, preserve useful state, and return after higher-confidence tasks are complete |
| Skipping immediate verification | The final review feels like the right time to check everything, but time often disappears | Verify after each change with the smallest command that proves the requirement |

## Quiz

<details>
<summary>1. You begin the exam and the first question asks you to troubleshoot a node that is NotReady, while the second asks you to create a namespace and ConfigMap worth slightly fewer points. How do you apply the Three-Pass Method to prioritize these CKA tasks by score, complexity, and remaining time?</summary>

Scan the remaining questions first, then handle the namespace and ConfigMap during Pass 1 if they are as straightforward as they appear. The node problem may require several diagnostic branches, while the namespace and ConfigMap are predictable and easy to verify. The slightly higher score does not justify allowing uncertainty to block a fast completed answer. After quick work is banked, return to the node task with less opportunity cost.

</details>

<details>
<summary>2. You are six minutes into a NetworkPolicy task and the YAML applies, but traffic still does not behave as expected. How should you triage this exam question into quick, medium, or complex work before committing more time?</summary>

Treat the task as having moved from medium to complex unless your next step is clearly evidence-driven. If labels or selectors can be inspected immediately and the mismatch is obvious, fix it and verify. If you are guessing at policy behavior without clear evidence, mark the task for Pass 3 and move to other medium tasks. Reclassification is a strategy decision, not an admission that the original estimate was bad.

</details>

<details>
<summary>3. You completed an RBAC task, but `kubectl auth can-i` shows the ServiceAccount cannot list Pods. What should you inspect before rewriting everything?</summary>

Inspect the RoleBinding subject, namespace, and role reference before deleting or recreating the whole answer. Common failures include binding the wrong ServiceAccount namespace, using the wrong Role name, or creating the binding in a different namespace from the Role. Targeted inspection follows the diagnostic loop and preserves work that is already correct. Rewriting everything wastes time and may introduce a new mistake.

</details>

<details>
<summary>4. You have 14 minutes left. One untouched question asks for a high-value recovery procedure, and another asks for command output to a specified file plus a simple Deployment scale change. How do you evaluate the point-per-minute tradeoff?</summary>

Complete the output-file and scale-change tasks first, then spend remaining time on the recovery task. The smaller tasks have short verification paths and high certainty, so their expected return per minute is strong. The recovery task may be valuable, but it is multi-step and carries higher risk. The strategic order banks predictable state before starting the final complex attempt.

</details>

<details>
<summary>5. You realize that you solved a Service question in the wrong context. The command history is available and five minutes remain. How do you design the recovery around the question-start routine?</summary>

Switch to the required context immediately, confirm it, and recreate or reapply the required Service in the correct namespace. Verify the Service in the correct context before doing anything else. If time remains and cleanup is safe, remove the accidental object from the wrong context, but that is secondary. The priority is creating verified state where the grader expects it.

</details>

<details>
<summary>6. A task asks for a Deployment with three replicas and a specific image, and you are tempted to add probes and resource limits because they are best practice. What should exam strategy tell you?</summary>

Create the requested Deployment with the specified image and replica count, verify those requirements, and move on unless probes or resource limits were explicitly requested. Optional polish can consume time and introduce errors without improving the score. Requirement-complete means the stated state is present and verified. It is not careless minimalism; it is disciplined scope control under a timer.

</details>

<details>
<summary>7. During Pass 3, a broken workload question asks you to fix both an image error and missing resource limits. You have three minutes left, and events clearly show the image is invalid. How do you recover from the stuck troubleshooting task while preserving partial credit?</summary>

Fix the invalid image first, verify that Pods start or the rollout progresses, and then add resource limits only if time remains. A running workload is a major visible improvement, while resource limits on a still-broken Deployment may not satisfy the core troubleshooting requirement. The best partial-credit move creates the most important correct state quickly. That answer follows evidence and avoids spending the final minutes on lower-impact polish.

</details>

## Hands-On Exercise

**Task**: Practice the Three-Pass Method against a small timed exam, then review your triage decisions. This exercise trains prioritization as much as command syntax, so keep a timer visible and write down when you choose to skip. The goal is not to finish perfectly on the first try. The goal is to make your decision process inspectable so the next timed drill is better calibrated.

### Setup

Create a practice namespace and a deliberately broken Deployment. These commands are safe in a disposable local cluster. If you are using a shared cluster, choose a unique namespace name and clean it up when finished. The broken Deployment is intentional because the lab needs one complex task that should not be solved during Pass 1.

```bash
kubectl create namespace exam-strategy-practice
kubectl create deployment q4-broken --image=nginx:doesnotexist -n exam-strategy-practice
```

### Mock Exam Questions

1. Create a Pod named `q1-pod` running `nginx:1.25` in namespace `exam-strategy-practice`.
2. Create a ConfigMap named `q2-config` with key `LOG_LEVEL=debug` in namespace `exam-strategy-practice`.
3. Create a PVC named `q3-pvc` requesting `5Gi` with `ReadWriteOnce` access mode in namespace `exam-strategy-practice`.
4. Troubleshoot the Deployment `q4-broken` in namespace `exam-strategy-practice` so its Pods can start.
5. Write the names of all Pods in namespace `exam-strategy-practice` to `/tmp/exam-strategy-pods.txt` with no header line.
6. Create a Role named `pod-reader` that can `get`, `list`, and `watch` Pods, then bind it to a ServiceAccount named `app-sa` in namespace `exam-strategy-practice`.

### Step 1: Scan And Categorize

Before running any solution command, scan all six tasks and write each one as `[QUICK]`, `[MEDIUM]`, or `[COMPLEX]`. Your categorization should reflect your current skill, not someone else's. If RBAC is automatic for you, it may still be medium because it has several related objects. If the output-file task feels unfamiliar, mark it as quick only after you know the exact formatting command you plan to use.

- [ ] I scanned all questions before solving.
- [ ] I identified the namespace for every task.
- [ ] I triaged exam questions into quick, medium, and complex work before typing solution commands.
- [ ] I chose a Pass 1, Pass 2, and Pass 3 order before typing solution commands.
- [ ] I wrote down at least one task I would skip if it exceeded its time box.

<details>
<summary>Suggested categorization</summary>

Q1, Q2, and Q5 are usually quick because their command paths and verification paths are short. Q3 and Q6 are usually medium because PVC and RBAC objects require careful field and relationship checks. Q4 is complex because it starts from a broken workload and requires evidence before a fix. If your personal skill changes these estimates, document why and keep the same pass logic.

</details>

### Step 2: Pass 1 Quick Wins

Complete only the quick tasks first. For many learners, Q1, Q2, and Q5 are quick. Do not start the broken Deployment yet, even if it looks tempting, because the purpose is to protect predictable points. Verify each result immediately so you do not create a final-review backlog.

```bash
kubectl run q1-pod --image=nginx:1.25 -n exam-strategy-practice
kubectl create configmap q2-config --from-literal=LOG_LEVEL=debug -n exam-strategy-practice
kubectl get pods -n exam-strategy-practice -o custom-columns=NAME:.metadata.name --no-headers > /tmp/exam-strategy-pods.txt
```

```bash
kubectl get pod q1-pod -n exam-strategy-practice
kubectl get configmap q2-config -n exam-strategy-practice
cat /tmp/exam-strategy-pods.txt
```

- [ ] I completed the quick tasks before starting troubleshooting.
- [ ] I verified each quick task immediately after creating the required state.
- [ ] I did not add optional fields or spend time polishing completed answers.

<details>
<summary>Pass 1 solution notes</summary>

The Pod and ConfigMap commands create directly requested objects, so they are good Pass 1 candidates. The output-file command uses `--no-headers` because the prompt asks for names only. Printing the file with `cat` is not extra polish; it is the verification that the task asks for exact file content rather than just cluster state.

</details>

### Step 3: Pass 2 Medium Tasks

Complete the PVC and RBAC tasks next. Use YAML for the PVC because the object shape is compact and precise. Use imperative commands for RBAC because they reduce typing and make the subject relationship explicit. Keep a checkpoint: if either task turns into diagnosis, preserve what works and move it to Pass 3.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: q3-pvc
  namespace: exam-strategy-practice
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

```bash
kubectl apply -f q3-pvc.yaml
kubectl create serviceaccount app-sa -n exam-strategy-practice
kubectl create role pod-reader --verb=get,list,watch --resource=pods -n exam-strategy-practice
kubectl create rolebinding app-sa-pod-reader --role=pod-reader --serviceaccount=exam-strategy-practice:app-sa -n exam-strategy-practice
```

```bash
kubectl get pvc q3-pvc -n exam-strategy-practice
kubectl auth can-i list pods --as=system:serviceaccount:exam-strategy-practice:app-sa -n exam-strategy-practice
```

- [ ] I used a manifest or command pattern that matched the task instead of relying on memory alone.
- [ ] I verified the PVC object and the RBAC permission separately.
- [ ] I evaluated point-per-minute tradeoffs before spending extra time on any YAML error.
- [ ] I stopped adding fields once the stated requirements were satisfied.

<details>
<summary>Pass 2 solution notes</summary>

The PVC verification proves the object exists in the correct namespace, though binding behavior can depend on storage classes in your practice cluster. The RBAC verification proves the ServiceAccount can list Pods, which is the relationship the task cares about. If `kubectl auth can-i` returns `no`, inspect the RoleBinding subject and namespace before recreating everything.

</details>

### Step 4: Pass 3 Complex Troubleshooting

Now troubleshoot the broken Deployment. Start by observing the state, then use events to identify the likely cause. Make one focused change and verify the rollout. This is the recovery habit from the lesson: when a task is stuck or symptom-based, gather evidence first and make the smallest useful fix.

```bash
kubectl get deployment q4-broken -n exam-strategy-practice
kubectl get pods -l app=q4-broken -n exam-strategy-practice
kubectl describe pod -l app=q4-broken -n exam-strategy-practice
kubectl get events -n exam-strategy-practice --sort-by='.lastTimestamp'
```

```bash
kubectl set image deployment/q4-broken nginx=nginx:1.25 -n exam-strategy-practice
kubectl rollout status deployment/q4-broken -n exam-strategy-practice
kubectl get pods -l app=q4-broken -n exam-strategy-practice
```

- [ ] I gathered evidence before changing the Deployment.
- [ ] I made one targeted fix based on the observed failure.
- [ ] I verified that the rollout completed or made visible progress.
- [ ] I recovered from stuck troubleshooting by preserving visible partial credit instead of deleting useful work.

<details>
<summary>Pass 3 solution notes</summary>

The setup used an intentionally invalid image, so events should point toward image pull failure. Updating the image is the focused fix because it directly addresses the observed evidence. If your cluster shows a different symptom, keep the same loop: inspect, hypothesize, change one thing, and verify. Do not edit unrelated fields just because the Deployment is already open.

</details>

### Step 5: Review Your Strategy

After the timer stops, review the decisions rather than only the commands. Strategy improves when you identify where your estimates were wrong. If a quick task took too long, ask whether the command was unfamiliar or the requirement was more complex than it looked. If a medium task became troubleshooting, ask what evidence would have told you to skip earlier.

- [ ] I recorded which task took longer than expected and why.
- [ ] I identified one command or manifest pattern to practice before the next mock exam.
- [ ] I identified one moment where I should have skipped earlier or stayed longer.
- [ ] I cleaned up the practice namespace after finishing the review.

```bash
kubectl delete namespace exam-strategy-practice
rm -f /tmp/exam-strategy-pods.txt
```

<details>
<summary>Review guidance</summary>

Write a short review note after each timed drill. Include the task you misclassified, the verification step that caught a mistake, and the next practice focus. Over several drills, this gives you a personal timing profile. That profile is more useful than a generic list of commands because it tells you which tasks should be Pass 1, Pass 2, or Pass 3 for you.

</details>

**Card A: Always start with the highest-point question.** A candidate opens the exam and immediately jumps to an eight-point node troubleshooting question because it carries the largest score weight on the dashboard. They spend thirty-five minutes chasing obscure kubelet configuration flags without identifying the root cause, leaving multiple straightforward two-point and four-point tasks completely untouched as time runs out. The candidate assumed that maximizing potential points per question was more important than protecting predictable, low-uncertainty points across the whole cluster.

<details>
<summary>Check your prediction</summary>

Failure layer: optimizing for raw point weight instead of point-per-minute certainty and risk-adjusted return. Next action: scan all questions first, bank low-uncertainty Pass 1 quick wins immediately, and defer high-variance troubleshooting tasks to Pass 3.

</details>

**Card B: If NetworkPolicy YAML parses, selector direction does not matter.** An operator constructs an ingress NetworkPolicy and validates that `kubectl apply --dry-run=client` succeeds without syntax or schema warnings. Believing that valid YAML structure guarantees correct network filtering, they invert the labels so that `podSelector` matches the client pods while `ingress.from` matches the target database. The policy successfully applies to the cluster, but it silently blocks production database traffic while failing to isolate the backend workload.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing valid declarative syntax with correct traffic-direction semantics in Kubernetes network specifications. Next action: inspect both selector boundaries explicitly, verifying that `podSelector` targets the protected workloads and `ingress.from` isolates authorized client sources before applying.

</details>

**Card C: Six minutes of guessing is still Pass 2 when the points are high.** A student spends six minutes configuring a persistent volume claim and an associated pod mount, but the pod remains stuck in `ContainerCreating` due to an unidentified storage class mismatch. Because the question is worth five points, the student insists on staying in Pass 2 and attempts random volume field edits for another ten minutes without an evidence-based hypothesis. They believe that abandoning the question after investing time represents wasted effort, rather than recognizing that escalating uncertainty has turned the task into complex debugging.

<details>
<summary>Check your prediction</summary>

Failure layer: falling victim to sunk-cost fallacy when a medium construction task exceeds its time box and turns into speculative troubleshooting. Next action: time-box medium tasks strictly at six minutes, preserve any valid partial resources created, and reclassify the question to Pass 3 while other untouched medium tasks remain.

</details>

**Card D: Wandering documentation is a good Pass 2 use of time.** When confronted with an unfamiliar RBAC binding syntax during Pass 2, an engineer opens the official documentation and starts reading full conceptual articles about authorization modules, API groups, and webhook authenticators. Twenty minutes elapse as the candidate browses multiple tabs without copying or adapting a concrete RoleBinding manifest skeleton. The engineer treated documentation during timed implementation as general exploratory study rather than as a rapid, targeted lookup for a known resource definition.

<details>
<summary>Check your prediction</summary>

Failure layer: substituting open-ended conceptual browsing for targeted procedural lookup during a timed implementation pass. Next action: restrict in-exam documentation use to copying verified YAML examples from Tasks or checking field names with `kubectl explain`, moving on immediately if the required pattern is not located within ninety seconds.

</details>

**Success Criteria**:

- [ ] Can triage exam questions into quick, medium, and complex tiers in under three minutes.
- [ ] Can bank Pass 1 quick wins without stalling on early high-point troubleshooting questions.
- [ ] Can time-box Pass 2 medium tasks and demote stalled items to Pass 3 when guessing begins.
- [ ] Can execute a question-start routine confirming context and namespace before every mutating command.
- [ ] Can preserve partial credit during Pass 3 troubleshooting by making focused, evidence-backed fixes.

## Sources

- https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/
- https://docs.linuxfoundation.org/tc-docs/certification/lf-handbook2/exam-preparation-checklist
- https://docs.linuxfoundation.org/tc-docs/certification/lf-handbook2/exam-rules-and-policies
- https://kubernetes.io/docs/tasks/tools/
- https://kubernetes.io/docs/reference/kubectl/
- https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands
- https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/
- https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- https://kubernetes.io/docs/concepts/services-networking/network-policies/
- https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
- https://kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/
- [training.linuxfoundation.org: certified kubernetes administrator cka](https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/) — The official CKA certification page directly describes the exam as online, proctored, performance-based, command-line based, and 2 hours long.
- [docs.linuxfoundation.org: faq cka ckad cks](https://docs.linuxfoundation.org/tc-docs/certification/faq-cka-ckad-cks) — The Linux Foundation certification FAQ explicitly states that a score of 66% or above is required to pass the CKA.
- [docs.linuxfoundation.org: certification resources allowed](https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed) — The official resources-allowed page states that CKA candidates may use kubernetes.io/docs and may use its on-site search as long as they do not open external search results.
- [kubernetes.io: organize cluster access kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/) — The kubeconfig documentation explains that a context contains cluster, namespace, and user information and that kubectl uses the current context by default.
- [kubernetes.io: namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) — The Kubernetes namespaces documentation defines namespaces as scopes for names and shows that namespaced resources are separated by namespace.

## Next Module

Next: [Part 1: Cluster Architecture, Installation & Configuration](/k8s/cka/part1-cluster-architecture/) begins the first full CKA domain by turning this exam routine toward the architecture, installation, and configuration tasks you will triage in real practice.
