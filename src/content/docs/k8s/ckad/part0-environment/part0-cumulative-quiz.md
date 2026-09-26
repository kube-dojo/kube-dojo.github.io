---
revision_pending: false
title: "Part 0 Cumulative Quiz: Environment & Strategy"
slug: k8s/ckad/part0-environment/part0-cumulative-quiz
sidebar:
  order: 3
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45–60 minutes, including the practice exercise
>
> **Prerequisites**: [Module 0.1: CKAD Overview & Strategy](/k8s/ckad/part0-environment/module-0.1-ckad-overview/) and [Module 0.2: Developer Workflow](/k8s/ckad/part0-environment/module-0.2-developer-workflow/)

## Learning Outcomes

After completing this cumulative review, you can make and defend the following application decisions using the evidence taught in Part 0:

- **Compare CKAD and CKA responsibilities** when the same Kubernetes object appears in an application task and an administration task.
- **Prioritize weighted domains** and assign practice tasks to the three passes without confusing a study plan with an exam action.
- **Choose a namespace and context workflow** that puts each resource in the requested location and proves where it exists.
- **Generate and verify application resources** using client dry run, a Job command boundary, and checks against live objects.
- **Diagnose a Service selector mismatch** by comparing Pod labels with the Service selector and inspecting its backends.

## Why This Module Matters

Hypothetical scenario: a learner moves from a cluster administration drill to a developer task. The task asks for an application Deployment and Service in a named namespace. The learner spends time investigating cluster components because the Service is unreachable. The Service exists, but its selector matches no Pod labels. The useful response is to inspect the application path, fix the mismatch, and verify backends. This is a simulated practice situation, not an actual exam question or incident.

Part 0 gave you two complementary tools. [Module 0.1](/k8s/ckad/part0-environment/module-0.1-ckad-overview/) established the CKAD scope, domain weights, and three-pass strategy. [Module 0.2](/k8s/ckad/part0-environment/module-0.2-developer-workflow/) turned a task into a repeatable developer workflow. This review asks you to combine those tools before Part 1 introduces application design and build work. A correct resource created in the wrong namespace, or a Service without matching Pods, is still an incomplete application outcome.

Use the teaching sections to explain each decision before answering the eight questions. Then attempt the hands-on exercise in a disposable practice cluster. The questions ask for the most defensible next step within the situation given. They are practice questions, so an eight-question result is a diagnostic for your study, not the official CKAD passing score. Module 0.1 states a 66% passing score for CKAD and CKA; that figure does not turn this local quiz into a certification exam.

## Core Content

### Identify the responsibility behind a familiar object

CKAD and CKA share Kubernetes vocabulary. A Pod, Deployment, Service, ConfigMap, or Secret can appear in either track. Their shared names do not make the tasks interchangeable. CKAD approaches those objects through application delivery: start the process, connect configuration, expose traffic, observe health, and make a change safely. CKA includes cluster administration and control-plane repair. When a prompt contains a Service, first ask what outcome is requested. Routing traffic to an application is a developer task even though the Service itself is a cluster resource.

The distinction prevents an expensive false start. If an application request says traffic is missing, a learner might remember a broad networking investigation from CKA and begin with infrastructure. Part 0 teaches an application-first chain: check where the objects live, inspect the workload and its labels, inspect the Service selector, then inspect whether it has backends. Those observations can expose a developer-level mismatch before any wider investigation is justified. Nothing in this quiz asks you to repair the control plane, because that would change the task being assessed.

Think of the requested evidence as a boundary on your work. A prompt about a Job asks whether the command ran and the Job completed. A prompt about configuration asks whether the application receives the expected value. A prompt about a Service asks which Pods it selects and whether traffic can reach them. You may use the same client for all three, but each has a different proof. Treating object creation as proof of the whole outcome hides failures that appear after Kubernetes starts reconciling the object.

Module 0.1 places container image building in CKAD Application Design and Build. That placement matters when you decide what to study next. It does not mean every Part 0 drill should become an image-building exercise. Part 0 is about scope, strategy, and a command workflow used across later domains. This quiz checks whether you can classify the responsibility and select useful evidence; the later module teaches images in detail. Keep that sequence in mind when an option sends you toward unrelated cluster administration or a later topic.

Consider a Deployment that exists but does not serve the intended application. The object name alone cannot tell you whether to inspect Pods, Service backends, or the surrounding cluster. Start from the requirement: is the concern application rollout, configuration, or traffic? Then choose the narrowest observation that answers it. That approach applies to objects shared by both exams without assuming they ask the same kind of work. It also keeps the answer grounded in the evidence you can collect during a task.

### Turn domain weights into practice priorities

The five CKAD domains have unequal weights. Application Environment, Configuration and Security is the largest at 25%. Application Design and Build, Application Deployment, and Services and Networking each carry 20%. Observability and Maintenance carries 15%. These percentages help allocate preparation time, but they do not reveal the value of an individual task in this practice quiz. A domain is a study category; an exam task is a concrete request that must still be read on its own terms.

A weak study plan gives every domain the same number of sessions because the list has five rows. That makes a 15% domain and a 25% domain look identical. An equally weak plan studies only the largest domain and neglects Services, Jobs, or Deployments that can be practiced quickly. The useful decision combines weights with actual weak spots. If simple Pods are comfortable, spend less time repeating that exact command and more time on configuration, security, or developer variations that remain slow.

The domain names connect to different kinds of practice. Building an image or choosing a Job belongs to Design and Build. Updating an application and checking a rollout belongs to Deployment. Probes, logs, and diagnosis belong to Observability and Maintenance. ConfigMaps, Secrets, resource requirements, and application identity appear in Environment, Configuration and Security. Service selectors, endpoints, and application traffic belong to Services and Networking. These concerns can overlap in a practical task; the labels guide preparation rather than forcing every scenario into a single drawer.

Make a short practice plan after the quiz. Name one topic you execute confidently and one that still needs deliberate inspection. Put the larger weakness in a domain and compare that domain's weight with the time you assigned it. This exercise is more useful than memorizing 25%, 20%, and 15% without changing your practice. It also exposes whether you are spending time on familiar commands because they feel productive while unfamiliar work remains untested.

The 66% passing score for both CKAD and CKA is separate from the domain weights. It is not a target for each question here, and it does not mean a 66% practice score proves readiness. This page has eight questions covering only Part 0. Use incorrect answers to identify a workflow decision to repeat in a cluster. Your next practical check should involve the behavior you missed, such as namespace placement or Service backends, rather than memorizing an answer letter.

Suppose a learner knows the domain chart but cannot create a ConfigMap quickly. The chart identifies Environment, Configuration and Security as the largest domain, while the weakness identifies a specific practice target. A useful session might create a ConfigMap, connect it to a workload, and verify the intended value. That practice also exercises the developer workflow. Domain weight tells you where to allocate time; the object and verification plan tell you what to do with that time.

### Sequence tasks with the three-pass method

Module 0.1 presents a three-pass exam strategy. Pass 1 takes quick wins: imperative Pod, Deployment, and Service creation, labels, exposing an application, and simple ConfigMaps or Secrets. Pass 2 covers medium work that commonly requires more fields or inspection: probes, multi-container Pods, Jobs and CronJobs, and NetworkPolicies. Pass 3 reserves complex debugging, complex multi-container patterns, Helm values, and troubleshooting. These categories sequence work; they do not promise that every task of a kind always takes the same time.

The strategy protects attention. A simple Deployment can be created and verified quickly if the request is narrow, while a multi-container task may need careful YAML editing. Starting with a difficult Helm values problem can consume attention you would use to finish several familiar requests. Conversely, leaving all simple resources to the end risks running out of time with straightforward work unfinished. The three passes help you keep moving while still returning to harder tasks rather than abandoning them.

Classify the actual prompt before applying a category. A Service creation request with a clear port and matching Deployment is likely Pass 1. A Service that exists but has no backends is a diagnosis problem, even though Service also appears in the quick-win list. A Job with a specified container command belongs in the medium group because the command boundary and verification matter. If a workload has several interacting failures, the work can move toward complex troubleshooting. The category follows the required work, not the resource name alone.

The passes interact with verification. Quick does not mean unverified. A concise `kubectl get` can confirm the named object and namespace after creation. A Service check should include backends when traffic is requested. Medium tasks may require waiting for completion or inspecting a Pod template. Complex tasks may require logs, events, or comparison of desired and live state. In each case, stop after you have evidence for the requested outcome; adding unrelated investigation makes a short task long without improving its answer.

This quiz mixes the passes. Before selecting an option, decide whether the scenario calls for creation, editing, or diagnosis. Then ask whether the proposed command yields the evidence needed to finish. That two-step habit turns the three-pass method into a practical filter rather than a memorized list. It also keeps the method within its Part 0 purpose: time management and accurate application work, without new pass rules or an imagined scoring formula.

A pass label is useful only after you understand the prompt. Suppose two requests both say Service. One asks you to expose a healthy Deployment on a given port; another says its Service has no endpoints after a configuration change. The first may be a quick creation task. The second requires comparison of selectors and Pod labels. Giving both the same priority because they name the same object would erase the difference that matters for time and verification.

### Treat context and namespace as part of the answer

Module 0.2 starts a developer task by checking context and namespace. The same resource name can exist in several namespaces, and the current context can carry a namespace left by an earlier task. A command that succeeds in the wrong place creates misleading confidence. Before recreating a supposedly missing object, inspect where you are and search the requested namespace. If the object exists there, recreating it will not solve the problem. If it exists elsewhere, you have located a placement error.

Two deliberate styles are available. Set the current context's namespace once for a run of commands, then verify it before creation. Or pass `-n` explicitly on each namespaced command. The first style saves repetition within a task, while the second makes each command's target visible. Neither style protects you if you forget which task you are solving. Pick one, use it consistently for creation and inspection, and recheck the context when the prompt changes.

Suppose a task requests a Deployment named `web` in `inventory`, but your previous drill used `payments`. Running `kubectl get deployment web` without a namespace tells you only about the current namespace. It cannot prove the object is missing from `inventory`. A targeted `kubectl get deployment web -n inventory` checks the requested location directly. If you then create or update anything, make the namespace equally explicit or set it deliberately. Creation and verification must point to the same place.

Context deserves the same care. `kubectl config current-context` identifies the context the client will use. `kubectl config view --minify` shows the active context configuration, including a namespace when one is set. If namespace is absent, Module 0.2 explains that namespaced commands default to `default` unless a namespace flag overrides it. A blank displayed namespace is not a reason to create extra resources; it is a cue to set or pass the requested namespace.

After a practice drill, restore context state you intentionally changed, and delete only the practice objects you own. During an assessment, leave resources the task asks you to create so they can be checked. These instructions have different goals: local cleanup prevents a later drill from accidentally passing because an old object remains, while assessment verification needs the final object available. In both settings, a precise namespace check comes before a broad delete or blind retry.

If a command reports that an object is absent, ask what set was searched. A lookup scoped to the current namespace cannot settle a claim about another namespace. A lookup in the correct namespace still depends on the current cluster context. Write the target context and namespace beside your practice prompt, then use them for both action and proof. This turns environment setup into part of the solution instead of an invisible assumption behind it.

### Choose creation, generation, and direct editing deliberately

A simple resource often fits one imperative command. A Pod with one image or a plain Deployment can be created directly and then inspected. When a prompt adds a second container, probe, shared volume, or nested configuration, generated YAML can be safer than forcing the entire requirement into flags. Module 0.2 teaches a cycle: read the prompt, classify the object, choose the smallest reliable creation path, apply or create it, and verify the live result. The goal is a correct outcome with manageable edits.

Client dry run is useful when you need a starter manifest. `--dry-run=client -o yaml` prints YAML without creating the resource. Redirecting that output to a file lets you edit the generated structure before applying it. The absence of creation is the feature, so do not interpret a successful dry-run command as proof that the resource exists. Inspect the file for required fields, then apply it and inspect the resulting live object in the requested namespace.

This command generates a simple Pod manifest. It does not create the Pod, and it does not invent probes, volumes, labels, or a second container that you did not specify. Inspect the generated file before deciding which fields still need to be added.

```bash
kubectl run web --image=nginx --dry-run=client -o yaml > web.yaml
```

Module 0.2 also separates client dry run from server-side validation. Client dry run builds the object locally and prints it; a server dry run asks the API server to process an apply request without persisting it. This quiz focuses on the client form because it gives a starting manifest. Do not blur either form with a successful live apply. The final proof still comes from inspecting what exists after the intended creation step.

Use the full `kubectl` command in every fenced example here. Module 0.2 discusses shell shortcuts, but a shortcut depends on the shell where it was defined. Full commands keep the page copyable and let you reason about the command itself. Under time pressure, a shortcut helps only if you know its expansion and have confirmed it exists. The exam shell may define short names; this page still prints `kubectl` so examples remain explicit.

A generated manifest is also a prompt to compare desired and present fields. If the task needs a probe, a dry-run Pod file will not supply it just because a Pod definition is valid. If the task needs a label used by a Service, the same check applies. Generation saves boilerplate; it does not interpret every sentence of a task. Make the required edits, validate the structure, and inspect the live object after applying rather than trusting that file creation completed the application.

### Keep the Job command on the container side of the boundary

Jobs test whether you read both the Kubernetes object and the application request. A Job runs finite work rather than serving ongoing traffic. If a prompt specifies a container command, the `kubectl create job` invocation needs a boundary between client options and the words sent to the container. Module 0.2 shows that the command follows `--`. Omitting that boundary can turn intended program arguments into misplaced client arguments or produce a command that does not express the requested work.

For a practice Job named `report` that uses BusyBox to print a marker, the following command gives the image to `kubectl` and the `echo` command to the container. The example is a practice instruction, not observed output from a cluster. A successful command submission would still need a completion check and logs before you could say the marker was produced.

```bash
kubectl create job report --image=busybox -- echo complete
kubectl wait --for=condition=complete job/report --timeout=90s
kubectl logs job/report
```

Read those three lines as separate claims. The first requests a Job. The second waits for its completion condition. The third inspects what the workload printed. If the first succeeds but the wait times out, inspect Job Pods and events instead of declaring success. If the Job completes but the expected text is absent, inspect the live command and logs. Object creation, lifecycle, and output are related, but none substitutes for the others.

CronJobs appear in Module 0.1's medium pass and in Module 0.2's command practice because they add a schedule to Job creation. This quiz does not ask you to calculate cron expressions from memory. It asks you to preserve the general habit: identify the requested workload, put the container command after the boundary, and choose verification that fits the workload. Scheduling syntax becomes relevant when a request includes a schedule; it does not belong in an unrelated Service diagnosis.

When you generate YAML for a Job instead of creating it immediately, the same principle applies. Check what `kubectl` generated and compare the container command with requested behavior before applying. A generated manifest may be syntactically complete while missing an application requirement. A human-readable `kubectl get job` can show status; the Job's Pods and logs explain how the command behaved. This is the create, inspect, prove loop from Module 0.2 applied to finite work.

There is a time-management consequence as well. Jobs are placed in Pass 2, but that classification does not permit a rushed command that changes meaning around `--`. The boundary is a small syntax detail with a large effect on the workload. Check it while composing the command, then reserve a short verification step for completion and output. Correcting one character before submitting is faster than diagnosing a Job that never ran the intended program.

### Verify Services by following selectors to backends

A Service can exist while its endpoints are empty. Module 0.2 gives a concrete reason: the Service selector does not match the labels on Pods meant to receive traffic. Creating the Service is only the first part of the requested outcome. A Service with a name, port, and valid YAML can still have nobody to serve. When traffic is missing, compare the selector with the workload's Pod labels before changing unrelated application settings.

The distinction between Deployment labels and Pod template labels matters here. A Service selects Pods, so you need labels on the resulting Pods or their template. A Deployment name alone does not make a Service select it. If the Service expects `app: api` but the Pods carry `app: web`, both objects can exist while remaining disconnected. A direct comparison makes that mismatch visible. An EndpointSlice check then shows whether the Service has selected usable backends after correction.

Use the commands below after choosing the requested namespace. They inspect a Service, candidate Pod labels, and the Service's EndpointSlices. The label selector in the final command filters EndpointSlices belonging to the named Service. Empty or missing backends are a reason to inspect selector and Pod state, not a reason to claim traffic has been proven.

```bash
kubectl get service api -n inventory -o yaml
kubectl get pods -n inventory --show-labels
kubectl get endpointslices -n inventory -l kubernetes.io/service-name=api
```

After fixing the selector, repeat the backend check. A useful verification loop asks what changed between the empty result and the new result. If Pod labels did not change but the Service selector did, that supports the mismatch diagnosis. If endpoints remain empty, look again at selected Pods and their readiness. Module 0.1 connects readiness to the traffic path, so matching labels alone do not guarantee a ready backend. Keep the explanation tied to what commands show, and do not assert an HTTP response until you test one.

This is also a study-planning example. Services and Networking is a 20% domain, but the task may require Observability and Maintenance habits such as reading status or events. The domain chart tells you to practice both; the live symptom tells you what to inspect first. The three-pass method helps decide when to continue debugging and when to move to another task. These tools reinforce one another when their separate purposes remain clear.

A selector repair is narrow because it addresses an observed difference between desired and actual values. Recreating a Deployment or changing an image before inspecting labels would add new variables without evidence. If the Service selector and Pod labels already match, say so and change your hypothesis. Then inspect Pod readiness and EndpointSlices again. A diagnosis is strong when it predicts a result that a second command can confirm or contradict.

### Choose evidence that matches the requested outcome

Verification is more than rerunning the creation command. For a named resource, use a targeted `kubectl get` in the requested namespace. For a Deployment, check rollout and the Pods it created. For a Job, check completion and logs. For a Service, check selectors and backends, then perform an in-cluster request if the task calls for traffic proof. For configuration, inspect the source object and the workload's reference or environment. The right check depends on what the prompt says must be true.

Module 0.2 separates symptoms by layer. A Pending Pod cannot provide useful application logs because its container has not started. A Running Pod that is not Ready points you toward readiness checks and events. A completed Job has a different lifecycle from a Deployment that should remain available. A Service with empty endpoints points first toward selection and Pod readiness. None of these observations requires control-plane diagnosis. Each locates the part of the application path that owns missing behavior.

JSONPath can extract an exact field when a task requests a value, such as the image in a Pod specification. That extraction proves only the field; it does not prove the image pulled or the container became ready. `kubectl describe` and events can explain why an object did not reach its desired state. `kubectl logs` reveals container output after it starts. These commands complement one another. Choosing one because it is familiar, rather than because it answers the question, can leave part of the task unchecked.

For this quiz, describe expected evidence before revealing each answer. If an option proposes creating an object, ask what the next check would show. If an option proposes deleting or recreating something, ask what observation justifies it. This habit turns a multiple-choice answer into a practical command plan. You can then rehearse the plan in the hands-on exercise and see whether live state supports your reasoning.

The eight scenarios stay within Part 0. They revisit exam scope, weights, pass sequencing, namespace handling, manifest generation, Job commands, and Service selection. They do not test later modules by surprise. If you miss an item, use the named source module to rebuild your reasoning, then repeat the corresponding cluster check. A memorized answer letter has little value; an explanation that survives a different resource name or namespace is useful.

Verification also has a stopping rule. When the request is to produce a local manifest, no live resource is required unless the prompt adds that step. When the request is to run a Job, a generated manifest alone falls short. When the request is to expose an application, the existence of a Service alone falls short. Define the stopping evidence from the requested outcome before you begin, so a successful intermediate command does not look like an endpoint.

### Rehearse the full decision loop before the quiz

Start a scenario by restating the requested end state in one sentence. Include object, namespace, application behavior, and proof requirement if the prompt gives them. This prevents the first visible command from becoming your entire plan. A Deployment and Service request may sound simple, but the end state includes ready Pods and selected backends. A Job request includes completion and the requested command's effect. A generated manifest request may end with a file rather than a live object.

Next, classify what you know and what remains uncertain. If the namespace is supplied, target it explicitly. If an object is said to be missing, verify that claim in the requested context before recreating it. If the prompt asks for a manifest without creation, client dry run fits. If it asks for running behavior, the manifest alone is insufficient. This classification is a short reasoning step that avoids longer corrections after a wrong assumption reaches the cluster.

Then choose the smallest reliable action and pair it with an observation. Imperative creation is efficient for simple objects. Generated YAML is useful when nested fields need editing. Logs answer output questions after a container starts; EndpointSlices answer backend questions; Pod labels and Service selectors answer selection questions. Your command path can change when evidence contradicts your expectation. That is the point of verification: it turns an assumption into a result you can inspect and correct.

Finally, decide whether the scenario belongs in a quick, medium, or complex pass. The category should follow required work after you understand the task. It should not override prompt, namespace, or proof requirement. The three-pass method helps sequence finite time across tasks, while the developer workflow helps finish each task accurately. Both are needed: a careful solution never reached and a fast solution in the wrong namespace each fail for different reasons.

**Pause and predict:** A Service named `api` exists in the requested namespace, but its EndpointSlice shows no selected backend. Which two fields would you compare before changing the Deployment image, and what observation would support a selector mismatch?

<details>
<summary>Reveal the reasoning</summary>

Compare the Service selector with candidate Pods' labels. A selector value absent from those Pod labels supports the mismatch diagnosis; inspect EndpointSlices again after a correction.

</details>

The comparison narrows your next action to the application traffic path, saving time when several unrelated resources are visible in the namespace.

One final practice habit makes the review transferable. Write down the evidence that would make you change your mind. If selector and labels match, do not keep repeating the same repair; inspect Pod readiness and backends again. If a Job does not complete, the command boundary may be correct while the workload still fails. If an object appears absent, context or namespace may explain the observation. Each command should confirm your plan or tell you which assumption to revise.

**Pause and predict:** A generated Pod YAML file appears after `kubectl run web --image=nginx --dry-run=client -o yaml > web.yaml`. What can you claim now, and which separate step would prove that a Pod exists in the requested namespace?

<details>
<summary>Reveal the reasoning</summary>

You can claim the client produced a starter manifest file. Client dry run did not create a Pod. Apply the reviewed file in the requested namespace, then inspect that live Pod there.

</details>

Separating file generation from live verification keeps a successful local command from becoming an unsupported claim about the cluster's current state.

## Did You Know?

- **Shared passing score:** Module 0.1 states that CKAD and CKA both use a 66% passing score, despite their different responsibilities.
- **Largest domain:** Application Environment, Configuration and Security carries 25% in Module 0.1's CKAD domain breakdown.
- **Client dry run:** Module 0.2 shows that `--dry-run=client -o yaml` prints a starter manifest without creating the resource.
- **Empty backends:** Module 0.2 demonstrates that a Service can exist while a selector mismatch leaves its endpoints empty.

## Common Mistakes

| Mistake | Why it fails | Better decision |
|---|---|---|
| Treating a shared Service name as a CKA repair task | The object name does not determine whether the request concerns application delivery or cluster administration. | Read the requested outcome and inspect the application traffic path first. |
| Studying every domain for equal time | CKAD domains have different weights, so equal blocks can neglect the largest domain. | Combine stated weights with your weak areas when planning practice. |
| Using a pass label to skip verification | A quick command can still place an object in the wrong namespace or leave it without backends. | Pair even Pass 1 work with a targeted live check. |
| Recreating a supposedly missing resource immediately | The object may already exist in a different namespace or context from the one inspected. | Check the requested location and current context before changing state. |
| Treating client dry run as live creation | Client dry run prints YAML, so success says nothing about a persisted Pod. | Review the file, apply it when requested, and inspect the live object. |
| Omitting the Job command boundary | Container words may be misread as client arguments instead of the workload command. | Put the container command after `--`, then check completion and logs. |
| Assuming a Service object proves traffic | A selector can match no Pod labels even when the Service exists and looks valid. | Compare selector and labels, inspect EndpointSlices, and test traffic when requested. |
| Using logs for every failure | A container that has not started cannot provide useful application logs. | Inspect Pod status, description, and events before choosing logs. |

## Quiz

Choose one answer for each scenario before opening its explanation. The eight items cover only decisions taught in Modules 0.1 and 0.2. For each answer, say what you would verify next; a correct letter without a proof plan is an incomplete practice result.

### Question 1: Same object, different responsibility

A task asks you to expose an existing application Deployment with a Service and prove its Pods receive traffic. Another task asks an administrator to repair a cluster component. Both mention Kubernetes networking. Which approach fits the first task and the Part 0 CKAD scope?

A) Inspect the application's Service selector, Pod labels, and backends before claiming traffic works.
B) Repair control-plane components first because every networking word indicates CKA work.
C) Treat the Service object's successful creation as complete traffic proof.
D) Build a new container image before checking the existing application path.

<details>
<summary>Answer 1: Compare CKAD and CKA responsibilities</summary>

**A is correct because** the requested result is application traffic, so the selector-to-Pod path and backends are relevant evidence. **B is wrong** because control-plane repair belongs to administrator scope in Module 0.1 and is not requested here. **C is wrong** because a Service can exist without selected backends. **D is wrong** because image building is a CKAD topic, but this scenario provides no image problem. Inspect EndpointSlices and test the in-cluster route if traffic proof is required.

</details>

### Question 2: Weight and weak spot

You have practiced plain Deployment creation repeatedly, but still need help with ConfigMaps, Secrets, and application security settings. Your remaining study time is limited. Which plan uses the domain breakdown without pretending the weights are task scores?

A) Divide every remaining session equally because there are five domain names.
B) Give more practice to Environment, Configuration and Security, while retaining mixed drills for other domains.
C) Practice only Deployment commands because a familiar command is faster to repeat.
D) Treat the 66% passing score as a required score for each individual domain.

<details>
<summary>Answer 2: Prioritize weighted domains</summary>

**B is correct because** the weak areas sit in the 25% Environment, Configuration and Security domain, the largest domain, while mixed work protects coverage elsewhere. **A is wrong** because equal time ignores both weighting and weakness. **C is wrong** because repeating a strength leaves weak areas untested. **D is wrong** because 66% is an exam passing score, not a per-domain practice threshold. Your next study check should use a configuration task that you create and verify in a cluster.

</details>

### Question 3: Classify work before assigning a pass

Four prompts remain: create a simple Pod, add a probe to an existing workload, create a Job with a command, and debug a complex failing application. You want to follow Module 0.1's three-pass method. Which order best matches the taught categories?

A) Complex debugging first, then the Pod, then the probe and Job together.
B) Pod first, probe and Job in the medium pass, complex debugging in the final pass.
C) Job and probe first, then complex debugging, and the Pod only if time remains.
D) Put all four in Pass 1 because each prompt names a Kubernetes resource.

<details>
<summary>Answer 3: Prioritize tasks across three passes</summary>

**B is correct because** simple imperative Pod creation is a quick win, probes and Jobs are medium work, and complex debugging belongs in the final pass. **A is wrong** because it leads with open-ended work. **C is wrong** because it postpones a quick win. **D is wrong** because a resource name alone does not indicate effort. Verify each task at the level it requires; pass order does not make verification optional.

</details>

### Question 4: A resource appears missing

A request targets namespace `inventory`, but your current context still uses `payments` from a previous task. A plain `kubectl get deployment web` reports no object. What is the best next step before creating another Deployment?

A) Recreate `web` immediately in the current namespace to avoid delay.
B) Delete every Deployment named `web` and start the task over.
C) Check the current context and query `web` explicitly in `inventory`.
D) Switch to control-plane troubleshooting because `kubectl get` found nothing.

<details>
<summary>Answer 4: Choose a namespace and context workflow</summary>

**C is correct because** the plain lookup covered the current namespace, not necessarily the requested one. Check context, then use `kubectl get deployment web -n inventory` to test the claim. **A is wrong** because it may create an extra object in `payments`. **B is wrong** because no evidence justifies deletion. **D is wrong** because namespace mismatch is a more direct explanation. Once located, create or update only what the task still needs.

</details>

### Question 5: Manifest versus live Pod

You need a Pod manifest as a starting point, with no object created yet. After reviewing the file, you may add fields and apply it. Which choice matches that request and gives you an honest verification boundary?

A) Run `kubectl run web --image=nginx`, then claim the Pod is merely a local file.
B) Run `kubectl run web --image=nginx --dry-run=client -o yaml > web.yaml`, then inspect the file before any apply.
C) Run `kubectl get pod web` and treat an absent result as proof the file is correct.
D) Create a Service named `web` and use its existence as proof of the Pod manifest.

<details>
<summary>Answer 5: Generate and verify application resources</summary>

**B is correct because** client dry run prints a starter manifest without creating a Pod. Inspect `web.yaml` for required fields, then apply and query the Pod only if creation is requested. **A is wrong** because direct `kubectl run` creates a resource. **C is wrong** because an absent live Pod says nothing about file quality. **D is wrong** because a Service cannot validate the Pod manifest. The next verification depends on whether the task ends at a file or a running resource.

</details>

### Question 6: Container command in a Job

A practice task asks for a Job named `report` using BusyBox, with `echo complete` as the container command. Which command expresses that request, and what would you check after submitting it?

A) `kubectl create job report --image=busybox -- echo complete`; then check completion and logs.
B) `kubectl create job report --image=busybox echo complete`; then trust the creation response.
C) `kubectl run report --image=busybox`; then assume a Job exists.
D) `kubectl create service clusterip report --tcp=80:80`; then inspect its backends.

<details>
<summary>Answer 6: Generate and verify a Job</summary>

**A is correct because** `--` separates Job creation options from the command passed to the container. Completion and logs test whether finite work ran as intended. **B is wrong** because it omits the documented boundary. **C is wrong** because a Pod created through `run` is not the requested Job. **D is wrong** because a Service does not perform the task. If completion fails, inspect the Job and Pods before assuming command submission proved success.

</details>

### Question 7: Service without backends

An `api` Service exists in `inventory`, but EndpointSlice inspection shows no usable backend. The Service selector requests `app: api`, while candidate Pods show `app: web`. What is the best diagnosis and verification plan?

A) The selector mismatch matters; align selector and labels, then inspect EndpointSlices again.
B) The Service name guarantees selection, so change the image tag instead.
C) The Service exists, so report that application traffic is proven.
D) Delete the namespace because no backend means the context must be corrupt.

<details>
<summary>Answer 7: Diagnose a Service selector mismatch</summary>

**A is correct because** a Service selects Pods through matching labels, and these values differ. Correct the intended selector or labels, then check backends again. **B is wrong** because a Service name does not replace a matching selector. **C is wrong** because existence does not prove traffic. **D is wrong** because the mismatch is visible without deleting unrelated state. If backends remain empty after labels match, inspect selected Pod readiness before asserting another cause.

</details>

### Question 8: Match evidence to a symptom

A Pod has not started, so an application log command yields no helpful output. You need to decide whether the problem is at Pod setup rather than inside a running process. Which inspection best follows the Part 0 workflow?

A) Repeat `kubectl logs` indefinitely because logs cover every Kubernetes failure.
B) Inspect Pod status, description, and events in the requested namespace before choosing the next action.
C) Create a second Service because that will force the container to start.
D) Rewrite CKAD study weights because the Pod did not produce logs.

<details>
<summary>Answer 8: Generate and verify application evidence</summary>

**B is correct because** status, description, and events can expose why a Pod has not reached a running container. **A is wrong** because an unstarted container may have no application logs to inspect. **C is wrong** because another Service does not resolve Pod setup. **D is wrong** because study weights organize preparation, not live diagnosis. If the container later starts and fails, logs become useful; choose evidence according to the stage observed.

</details>

## Hands-On Exercise

Simulation: use a disposable Kubernetes practice cluster to build and inspect a small application path. The exercise gives you an intended namespace, a Deployment, and a Service with an intentional selector mismatch. You will create the objects, observe empty backends, correct the Service selector, and verify selected backends. The simulated failure is part of the drill; no real outage or exam task is being described.

Start by confirming your active context. Create a namespace named `quiz-practice` if it does not already exist, and keep every command targeted to it. Create a Deployment named `api` using `nginx`, wait for rollout, and inspect labels on its Pods. Expose the Deployment as a ClusterIP Service on port 80. Record the initial Service selector and EndpointSlices before deliberately changing the selector to `app: wrong`. This gives you a known mismatch to diagnose rather than an ambiguous pre-existing failure.

The commands below show one reproducible route. Read each line before using it, because deleting a practice namespace is appropriate only when you own it and no other work is stored there. Expected observation after the wrong selector: the Service exists, but its EndpointSlices have no selected ready backend. Expected observation after repair: selected backends appear once Pods are ready. These are expectations for your run, not observations from a run of this page.

```bash
kubectl config current-context
kubectl create namespace quiz-practice
kubectl create deployment api --image=nginx -n quiz-practice
kubectl rollout status deployment/api -n quiz-practice --timeout=90s
kubectl get pods -n quiz-practice --show-labels
kubectl expose deployment api --port=80 --target-port=80 -n quiz-practice
kubectl get service api -n quiz-practice -o yaml
kubectl get endpointslices -n quiz-practice -l kubernetes.io/service-name=api
kubectl patch service api -n quiz-practice -p '{"spec":{"selector":{"app":"wrong"}}}'
kubectl get pods -n quiz-practice --show-labels
kubectl get service api -n quiz-practice -o yaml
kubectl get endpointslices -n quiz-practice -l kubernetes.io/service-name=api
kubectl patch service api -n quiz-practice -p '{"spec":{"selector":{"app":"api"}}}'
kubectl get endpointslices -n quiz-practice -l kubernetes.io/service-name=api
```

Before repair, write down the two selector values you compared. Explain why a Service can be present while its backends are empty. After repair, check that the Deployment Pods have the label expected by the Service and that EndpointSlices show selected backends. If they do not, inspect selected Pod status and readiness rather than inventing a new cause. This is also practice in separating evidence you observed from the result you expected.

**Success Criteria**: You can show the requested namespace, reproduce the empty backend condition, identify the selector mismatch, and verify selected backends after a targeted repair.

- [ ] Current context is known, and every create or inspect command targets the practice namespace.
- [ ] Deployment Pods carry `app: api`, while the deliberately broken Service selector requests `app: wrong`.
- [ ] The Service remains present during the mismatch, while EndpointSlices show no selected ready backend.
- [ ] After selector repair, EndpointSlices show selected backends for ready application Pods.
- [ ] You can explain why object existence did not prove traffic and name the next check if backends stay empty.

When the exercise is complete, remove only the namespace you created for this isolated drill, provided it contains no work you intend to keep. You can use `kubectl delete namespace quiz-practice` for cleanup. In an assessed task, keep requested objects available for inspection instead of deleting them after verification. The difference comes from task purpose, not from a different Kubernetes command rule.

## Sources

- [CNCF CKAD certification](https://www.cncf.io/training/certification/ckad/)
- [CNCF CKAD curriculum for Kubernetes 1.35](https://github.com/cncf/curriculum/blob/master/CKAD_Curriculum_v1.35.pdf)
- [Linux Foundation certification handbook](https://docs.linuxfoundation.org/tc-docs/certification/lf-handbook2)
- [Linux Foundation CKA and CKAD tips](https://docs.linuxfoundation.org/tc-docs/certification/tips-cka-and-ckad)
- [Kubernetes Pods](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/)
- [Kubernetes Deployments](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kubernetes Jobs](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes CronJobs](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Kubernetes probes](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Kubernetes ConfigMaps in Pods](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)
- [Kubernetes Services](https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes kubectl reference](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/)
- [Kubernetes namespace administration](https://kubernetes.io/docs/tasks/administer-cluster/namespaces/)
- [Kubernetes Service debugging](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)

## Next Module

[Module 1.1: Container Images](/k8s/ckad/part1-design-build/module-1.1-container-images/) continues with application image work after this Part 0 strategy and workflow review, giving you a concrete new design topic for the command and verification habits you practiced here.
