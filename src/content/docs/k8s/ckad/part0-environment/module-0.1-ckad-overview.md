---
revision_pending: false
title: "Module 0.1: CKAD Overview & Strategy"
slug: k8s/ckad/part0-environment/module-0.1-ckad-overview
sidebar:
  order: 1
lab:
  id: ckad-0.1-ckad-overview
  url: https://killercoda.com/kubedojo/scenario/ckad-0.1-ckad-overview
  duration: "30 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Long-form orientation and strategy module
>
> **Time to Complete**: 20-30 minutes
>
> **Prerequisites**: CKA curriculum completed (recommended) or Kubernetes fundamentals

---

## Learning Outcomes

After completing this module, you will be able to:

- **Compare** CKAD and CKA responsibilities using exam domains, weights, and developer-facing resource patterns.
- **Design** a weighted study plan that prioritizes environment, configuration, security, deployment, networking, observability, and design-build practice.
- **Implement** a Kubernetes 1.35+ practice environment with kind, kubectl dry-run manifests, Jobs, CronJobs, probes, and context checks.
- **Debug** exam workflow pitfalls involving context switching, task triage, probes, multi-container pods, logs, and cleanup.

## Why This Module Matters

Hypothetical scenario: you join a team that already runs Kubernetes clusters, but every release still depends on a platform engineer to turn application intent into manifests. The developer asks for a background worker, a readiness check, a small Secret, and a rollback plan, then waits while someone else translates those needs into Pods, Deployments, Services, Jobs, and configuration objects. The CKAD exam exists because that handoff is too slow for teams that expect application engineers to ship safely inside Kubernetes without becoming full cluster administrators.

CKAD is not a smaller CKA. It uses the same Kubernetes control plane, the same `kubectl` client, and many of the same resource types, but it changes the point of view. CKA asks whether you can keep the restaurant open: nodes join, networking works, storage attaches, and RBAC protects the kitchen. CKAD asks whether you can cook the meal: package the application, attach configuration, expose the right port, choose the right workload object, observe health, and recover when the app misbehaves. Both perspectives need Kubernetes fluency, but the pressure lands in different places.

This first module gives you the map before the work begins. You will compare CKAD with CKA, translate the official domain weights into a study plan, build a local practice loop, and learn a three-pass exam strategy that protects your score when a task is harder than expected. The goal is not to memorize a motivational checklist. The goal is to leave with a practical operating model for deciding what to practice, how to practice it, and how to behave when the clock is moving.

## CKAD and CKA Responsibilities Share a Cluster but Not a Job

The fastest way to misunderstand CKAD is to treat it as another cluster-operations exam. If you already studied CKA, that assumption feels tempting because Pods, Deployments, Services, ConfigMaps, Secrets, volumes, Helm, Kustomize, and NetworkPolicies appear in both tracks. The difference is that CKAD evaluates how an application developer uses those primitives, while CKA evaluates whether an administrator can keep the platform available and correctly configured for many teams. A shared resource name does not imply a shared mental model.

The original comparison is still the right starting point because it separates scope before it separates commands. CKA and CKAD both run for two hours, both use performance-based tasks, and both expect fluency with multiple Kubernetes contexts. The CKAD task usually begins closer to application intent, such as "make this web app expose port 8080 and fail readiness until `/ready` works," while the CKA task usually begins closer to cluster intent, such as "repair this node, storage class, or control-plane component." That distinction changes how you allocate study time.

| Aspect | CKA | CKAD |
|--------|-----|------|
| **Focus** | Cluster administration | Application development |
| **Perspective** | Ops/Platform team | Dev/Application team |
| **Exam Duration** | 2 hours | 2 hours |
| **Passing Score** | 66% | 66% |
| **Questions** | ~15-20 tasks | ~15-20 tasks |
| **Clusters** | Multiple contexts | Multiple contexts |

If you completed CKA recently, you can carry over a meaningful base. You should not spend your first CKAD week relearning what a Pod is, how labels connect a Service to endpoints, or how a Deployment creates ReplicaSets. You should instead convert that knowledge into developer-speed workflows: generate a manifest quickly, edit the fields that matter, apply it, inspect status, read logs, and clean up. CKA gives you vocabulary; CKAD rewards how quickly you can turn that vocabulary into running application resources.

The shared portion includes Pods, Deployments, ReplicaSets, Services, ConfigMaps, Secrets, PersistentVolumes, PersistentVolumeClaims, basic networking, NetworkPolicies, Helm basics, Kustomize basics, and RBAC fundamentals. Treat those as prerequisite muscles rather than the whole training plan. When an exam task says "configure a pod to consume a ConfigMap," it is not asking for a lecture on the API server. It is asking whether you can create the object, mount or project the data correctly, restart or observe the workload when needed, and prove the application sees what you intended.

> **Pause and predict**: You already know about sixty percent of CKAD content from CKA if your fundamentals are fresh. Before looking at the table below, write down three topics you expect CKAD to emphasize more heavily than CKA, then compare your guesses with the developer-focused list.

The CKAD emphasis moves toward resource shape, application lifecycle, and feedback loops. Multi-container pods matter because application behavior often depends on an init container, a helper sidecar, or a local proxy. Probes matter because the cluster can only route traffic safely when the application exposes a useful health contract. Jobs and CronJobs matter because developers routinely run migrations, cleanup tasks, and one-off workers that do not belong inside a long-running web process.

| Topic | CKA Coverage | CKAD Coverage |
|-------|-------------|---------------|
| **Multi-container pods** | Mentioned | Deep focus |
| **Init containers** | Mentioned | Essential skill |
| **Probes** (liveness/readiness/startup) | Basic | Detailed |
| **Jobs & CronJobs** | Covered | Developer focus |
| **Container image building** | Not covered | Important |
| **API deprecations** | Not covered | Exam topic |
| **Debugging applications** | From admin view | From dev view |
| **Deployment strategies** | Rolling updates | Blue/green, canary |

The chef and restaurant-manager analogy from the original module is useful because it keeps the boundary memorable. CKA is the restaurant manager checking that the kitchen opens, staff are scheduled, suppliers deliver ingredients, and customers can enter the building. CKAD is the chef deciding which dish is prepared, when each component starts, how to detect that the dish is ready, and how to handle a failed preparation step. The chef still depends on the building, but the exam is about execution inside that environment.

There is one practical consequence for your notes. Do not create a CKAD notebook organized only by object kind, such as "Pods," "Services," and "ConfigMaps." Organize it by developer task: "run a web process," "inject configuration," "gate traffic on readiness," "run a one-time job," "ship logs from a sidecar," and "expose an app." Kubernetes objects are the vocabulary; application outcomes are the sentences you need to write under time pressure.

## Exam Domains and Weighted Study Planning

The official CKAD curriculum is divided into five weighted domains. The weights are not trivia; they are a scheduling input. A learner who spends most of a week on comfortable Deployment commands while neglecting environment, configuration, and security is quietly choosing to underprepare for the largest domain. A learner who practices only the newest or most interesting topics can make the opposite mistake by leaving easy Services, Jobs, or ConfigMap points on the table.

```
┌──────────────────────────────────────────────────────────────────┐
│                    CKAD Exam Breakdown                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Application Environment, Configuration & Security   25%  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────┐ ┌───────────────────────────┐   │
│  │ Application Design & Build │ │ Application Deployment    │   │
│  │            20%             │ │           20%             │   │
│  └────────────────────────────┘ └───────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────┐ ┌───────────────────────────┐   │
│  │ Services & Networking      │ │ Observability/Maintenance │   │
│  │            20%             │ │           15%             │   │
│  └────────────────────────────┘ └───────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Application Design and Build carries twenty percent of the exam. In practice, this domain asks whether you can define, build, and modify container images at the level needed by an application developer; create Jobs and CronJobs; design multi-container pod patterns; and use persistent or ephemeral volumes where the workload needs them. You should practice this domain by starting from application intent rather than from an object template. For example, "run a backup once and keep its logs" naturally becomes a Job, while "prepare configuration before the app starts" naturally becomes an init container.

Application Deployment also carries twenty percent. This domain focuses on Deployments, rolling updates, rollbacks, Helm, Kustomize, and release strategies such as blue-green or canary. The important CKAD skill is not merely creating a Deployment from memory. The useful skill is knowing when a change belongs in an image tag, a `kubectl set image` command, a Kustomize overlay, a Helm value, or a rollback. That decision requires both command speed and release judgment.

Application Observability and Maintenance carries fifteen percent, but it is easy to underestimate because it shows up inside many tasks. Probes, logs, events, `kubectl describe`, and application-level debugging appear whenever the manifest is syntactically valid but the workload still does not behave. API deprecation awareness also belongs here because a manifest that uses an old API version can fail before the application ever starts. This domain is smaller by weight, yet it protects points in every other domain.

Application Environment, Configuration and Security is the largest domain at twenty-five percent. It covers ConfigMaps, Secrets, ServiceAccounts, resource requests and limits, SecurityContexts, and working with custom resources. This is the closest CKAD gets to platform policy, but the developer point of view remains clear: make the application configurable, give it only the identity and privileges it needs, constrain its resource behavior, and discover extension APIs without assuming cluster-admin access. If your study plan has only one oversized block, put it here.

Services and Networking carries twenty percent. CKAD expects you to expose applications through Services, use Ingress rules where available, and reason about NetworkPolicies from an application perspective. The common developer mistake is to treat networking as a final wrapper around a completed Pod. In Kubernetes, a Service selector, a Pod label, a container port, and a readiness probe form one traffic path. You need to debug that path as a system, not as four separate YAML fragments.

| Domain | Weight | Practice Bias | Evidence You Are Ready |
|--------|--------|---------------|-------------------------|
| Application Design and Build | 20% | Jobs, CronJobs, init containers, sidecars, volumes | You can choose the right workload shape from a scenario and generate a clean starter manifest quickly. |
| Application Deployment | 20% | Deployments, rollout commands, Helm, Kustomize, release strategies | You can update, observe, and roll back an app without losing track of labels or selectors. |
| Observability and Maintenance | 15% | Probes, logs, events, debug commands, deprecated APIs | You can explain whether a failure is scheduling, container startup, readiness, liveness, or service routing. |
| Environment, Configuration and Security | 25% | ConfigMaps, Secrets, ServiceAccounts, resources, SecurityContexts, CRDs | You can inject configuration and constrain runtime behavior without rebuilding an image. |
| Services and Networking | 20% | Services, Ingress, NetworkPolicies, endpoint checks | You can prove which Pods receive traffic and why another Pod is blocked or allowed. |

Design your study plan from both weight and weakness. If you already passed CKA, allocate less time to plain Pod creation and more time to the developer-specific variations that CKA did not force into muscle memory. If you have written Deployments at work but never created CronJobs or init containers by hand, do not let workplace familiarity fool you into skipping those topics. Exam readiness is not the same as production exposure because the exam removes your IDE, your teammate, and your slow review loop.

A useful four-block plan over two weeks uses the weights as guardrails rather than a rigid calendar. Spend the first block confirming that your CKA basics are fast enough: Pods, Deployments, Services, ConfigMaps, Secrets, and namespace context. Spend the second block on the largest domain, especially resource requirements, SecurityContexts, ServiceAccounts, and configuration injection. Use the third block for Jobs, CronJobs, probes, multi-container patterns, and debugging. Use the final block for timed mixed drills where you decide what to skip, what to finish, and what to return to later.

## Practice Environment and Command Workflow

You need a practice environment that is disposable, repeatable, and close enough to the exam to build useful habits. For this curriculum, use Kubernetes 1.35 or later and a current `kubectl` client. A local kind cluster is a good fit because you can create resources, break them, delete them, and rebuild the cluster without waiting on a shared environment. The point is not to reproduce every exam detail. The point is to make repetition cheap enough that you actually repeat.

The original module used kind for the practice cluster, and that remains the recommended baseline. A multi-node cluster is helpful even when most CKAD work happens at the application layer because it keeps your mental model honest. Pods schedule onto workers, Services select endpoints, and events report the same kinds of scheduling and image-pull problems you will see elsewhere. You do not need to tune control-plane internals for CKAD, but you do need an environment where Kubernetes behaves like Kubernetes.

```bash
# Create a multi-node CKAD practice cluster
cat <<EOF > ckad-cluster.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
EOF
kind create cluster --config ckad-cluster.yaml --name ckad-prep
```

After the cluster exists, treat `kubectl` context as part of every exercise. The CKAD exam uses multiple contexts, and many wrong answers start with correct YAML applied to the wrong cluster or namespace. Your local drill should always include three checks before serious work: current context, target namespace, and the resource names already present. This sounds slow until you lose more time debugging a resource that was never created where you thought it was.

The most valuable command pattern is `--dry-run=client -o yaml`. It gives you a syntactically valid starter object quickly, then lets you edit the fields that imperative commands cannot express cleanly. You should use imperative creation for simple resources, generated YAML for moderate resources, and hand-written YAML only when generation would take longer than writing the manifest. That is a pragmatic exam habit, not a philosophical preference.

```bash
kubectl run nginx --image=nginx --dry-run=client -o yaml > pod.yaml
```

Before running this, what output do you expect to see in `pod.yaml`? You should expect a complete Pod manifest with `apiVersion`, `kind`, `metadata`, and a single container using the `nginx` image, but you should not expect probes, volumes, SecurityContexts, or custom labels unless you add them. That prediction matters because the next step is editing the generated shape. If you cannot predict what generation gives you, you will not notice when a required field is still missing.

CKAD speed comes from knowing which commands produce useful scaffolds. The original quick-reference command group is preserved below with full `kubectl` names so each block can be copied into a non-interactive shell. Many engineers use a short alias interactively, but exam and training material should teach commands that work when pasted into scripts, terminals, and automated checkers.

```bash
# Jobs and CronJobs
kubectl create job myjob --image=busybox -- echo "hello"
kubectl create cronjob mycron --schedule="* * * * *" --image=busybox -- date

# Generate multi-container pod YAML
kubectl run multi --image=nginx --dry-run=client -o yaml > multi.yaml
# Then edit to add sidecar

# Debugging
kubectl logs pod-name -c container-name
kubectl exec -it pod-name -c container-name -- sh
kubectl debug pod-name --image=busybox --target=container-name

# Quick testing
kubectl run test --image=busybox --rm -it --restart=Never -- wget -qO- http://service  # replace 'service' with your Service name
```

Probe syntax deserves a separate memory slot because it is common, precise, and easy to mistype. A liveness probe answers whether Kubernetes should restart the container. A readiness probe answers whether the Pod should receive Service traffic. A startup probe gives slow-starting applications time before liveness checks begin. Mixing those purposes is one of the fastest ways to create a workload that looks managed but behaves badly.

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

The key is to connect probe type to failure mode. If a container is healthy after boot but needs time to load caches, use startup protection rather than a generous liveness delay everywhere. If an application can run background tasks before it can serve requests, readiness is the gate that protects users. If a process wedges permanently, liveness is the restart signal. Exam tasks often provide just enough text to choose one of those meanings, so slow down long enough to read the symptom.

Context switching is another workflow skill that should become automatic. The command sequence is simple, but the habit is what matters. List contexts when a task names a target cluster, switch to the requested context, confirm it, and set the namespace if the task gives one. Do this before creating resources, not after the first surprising result.

```bash
# List available contexts
kubectl config get-contexts

# Switch context (to the practice cluster created earlier)
kubectl config use-context kind-ckad-prep

# Verify current context
kubectl config current-context

# Quick shortcut: set namespace for context
kubectl config set-context --current --namespace=default
```

When you practice, keep cleanup explicit. Exam tasks rarely reward cleanup unless asked, but local learning collapses if old resources pollute new drills. A lingering Service selector can make a new Pod appear reachable for the wrong reason, and an old ConfigMap can hide a typo in the manifest you meant to test. Deleting named resources at the end of drills preserves the signal in your next run.

## Three-Pass Exam Strategy and Speed Drills

The CKAD exam is a time-allocation exercise as much as a Kubernetes exercise. Every task has a point value, but every task also has a risk profile. Simple imperative commands can produce points quickly. A complex multi-container Pod can consume ten minutes if one indentation level is wrong. A debugging task can be easy when the event message is obvious and expensive when the symptom points in several directions. The three-pass strategy protects you from spending your best time in the wrong place.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CKAD Three-Pass Method                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pass 1: Quick Wins (40-50 min)                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Create pod/deployment/service (imperative commands)   │   │
│  │ • Add labels, annotations                               │   │
│  │ • Expose a deployment                                   │   │
│  │ • Simple ConfigMap/Secret creation                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Pass 2: Medium Tasks (40-50 min)                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Add probes to pods                                    │   │
│  │ • Create multi-container pods                           │   │
│  │ • Jobs and CronJobs                                     │   │
│  │ • Network policies                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Pass 3: Complex Tasks (20-30 min)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Debugging failing applications                        │   │
│  │ • Complex multi-container patterns                      │   │
│  │ • Helm charts with values                               │   │
│  │ • Troubleshooting scenarios                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

Pass one is about harvesting low-risk points. Creating a Deployment, exposing it as a Service, adding a label, creating a literal ConfigMap, or generating a simple Pod manifest should not become a long design session. If you recognize the task and can finish it in a few minutes, do it and move on. This pass also gives you a feel for the exam environment, because you confirm contexts, editor behavior, copy-paste behavior, and documentation access while the tasks are still simple.

Pass two is for tasks that require editing but have a familiar shape. Adding probes, writing a small Job, creating a CronJob, adding a sidecar, or applying a basic NetworkPolicy often belongs here. These tasks are not hard because the concept is mysterious. They are hard because they need several exact fields, and exact fields invite small mistakes. In pass two, you have enough time to check the result, but you are still avoiding the deepest debugging holes.

Pass three is for tasks that are complex, ambiguous, or likely to require multiple inspections. A failing application with a bad probe, wrong selector, missing Secret key, and incorrect container command may be solvable, but it is not the task you want to meet first. The same is true for Helm value overrides if you are slow with chart inspection, or a multi-container pod that combines init, sidecar, shared volume, and log verification. The strategy is not avoidance; it is sequencing.

> **Stop and think**: Classify these tasks before reading further: creating a NetworkPolicy, running a Pod with a specific image, adding a sidecar container, exposing a Deployment, and debugging a failing readiness probe. Which are pass one, which are pass two, and which might become pass three if the symptoms are unclear?

The speed tips from the original module remain correct once the commands use full `kubectl`. Practice them until the first draft is automatic, then spend your attention on the fields that the task adds. A command you can type quickly is useful only if you still verify the resource it created. Speed without inspection produces confident wrong answers.

```bash
# These should be muscle memory
kubectl run nginx --image=nginx
kubectl create deployment web --image=nginx --replicas=3
kubectl expose deployment web --port=80 --target-port=80
kubectl create job backup --image=busybox -- /bin/sh -c "echo done"
kubectl create cronjob cleanup --image=busybox --schedule="*/5 * * * *" -- /bin/sh -c "echo cleanup"
```

Your inspection loop should be as practiced as your creation loop. After creating a workload, run a targeted `kubectl get`, then a `kubectl describe` if status is not obvious, then logs only when the container actually started. After creating a Service, inspect selectors and endpoints instead of assuming that a successful Service object means traffic will flow. After adding a probe, describe the Pod and read probe events because a probe can fail while the container keeps running.

The following drills are deliberately small. They are not a substitute for full mock exams, but they develop the timed reflexes that make mock exams useful. Run them with a clean namespace, set a timer, and stop when the target expires. If you miss the target, do not merely repeat the same command faster. Identify whether the delay came from command recall, YAML editing, context confusion, or verification.

```bash
# 1. Pod named 'web' with nginx image
kubectl run web --image=nginx

# 2. Deployment named 'api' with 2 replicas of httpd
kubectl create deployment api --image=httpd --replicas=2

# 3. Service exposing the api deployment on port 8080
kubectl expose deployment api --port=8080 --target-port=80

# 4. Job named 'backup' that runs busybox and echoes "done"
kubectl create job backup --image=busybox -- echo "done"

# 5. CronJob named 'hourly' running every hour
kubectl create cronjob hourly --image=busybox --schedule="0 * * * *" -- date

# Verify
kubectl get pod,deploy,svc,job,cronjob

# Cleanup
kubectl delete pod web
kubectl delete deployment api
kubectl delete service api
kubectl delete job backup
kubectl delete cronjob hourly
```

Drill two practices manifest generation. The useful skill is not the redirection itself; it is recognizing which generated manifest is the fastest safe starting point. A generated Service manifest can save you from remembering the exact field names, but it cannot know whether your selector matches the labels in your Deployment. A generated Deployment manifest gives you the scaffold, but it does not decide your probes, resources, or environment variables.

```bash
# Generate pod YAML
kubectl run nginx --image=nginx --dry-run=client -o yaml > /tmp/pod.yaml

# Generate deployment YAML
kubectl create deployment web --image=nginx --dry-run=client -o yaml > /tmp/deploy.yaml

# Generate service YAML
kubectl create service clusterip mysvc --tcp=80:80 --dry-run=client -o yaml > /tmp/svc.yaml

# Verify files exist and are valid
head -10 /tmp/pod.yaml
head -10 /tmp/deploy.yaml
```

Drill three practices context switching. This should feel almost boring by exam day because the cost of boring is lower than the cost of repairing resources created in the wrong place. When a question names a context, switch first. When it names a namespace, set or pass the namespace before applying resources. When in doubt, verify current context before changing the cluster.

```bash
# List available contexts
kubectl config get-contexts

# Switch context (to the practice cluster created earlier)
kubectl config use-context kind-ckad-prep

# Verify current context
kubectl config current-context

# Quick shortcut: set namespace for context
kubectl config set-context --current --namespace=default
```

Drill four forces probe syntax into memory. You do not need to worship memorization, but you do need enough recall to avoid searching documentation for every common field. The important part of this drill is the verification command at the end. If `kubectl describe` does not show the probes you intended, your manifest did not express the health contract correctly.

```bash
# Create a pod YAML with all three probe types
cat << 'EOF' > /tmp/probed-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: probed-app
spec:
  containers:
  - name: app
    image: nginx
    ports:
    - containerPort: 80
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 3
      periodSeconds: 5
    startupProbe:
      httpGet:
        path: /
        port: 80
      failureThreshold: 30
      periodSeconds: 10
EOF

# Apply and verify
kubectl apply -f /tmp/probed-pod.yaml
kubectl describe pod probed-app | grep -A5 "Liveness\\|Readiness\\|Startup"

# Cleanup
kubectl delete pod probed-app
```

Drill five keeps multi-container patterns tied to scenarios. Pattern recognition is faster than field memorization when the question describes intent clearly. If something must finish before the main app starts, think init container. If something runs beside the app for its lifetime, think sidecar. If the app talks to localhost while another container translates the remote dependency, think ambassador.

```
Scenario 1: Download config before app starts
Answer: Init container

Scenario 2: Ship logs to Elasticsearch alongside main app
Answer: Sidecar

Scenario 3: Wait for database to be ready
Answer: Init container

Scenario 4: Proxy database connections through localhost
Answer: Ambassador

Scenario 5: Monitor and reload config on change
Answer: Sidecar
```

Drill six checks whether the domain weights are available when you make scheduling decisions. You are not memorizing them to answer a recall question. You are memorizing them so that a weak area with a large weight gets enough practice time before a familiar area with a smaller operational payoff consumes the schedule.

```
1. Application Design and Build - 20%
2. Application Deployment - 20%
3. Application Observability and Maintenance - 15%
4. Application Environment, Configuration and Security - 25%
5. Services and Networking - 20%
```

The final exam strategy is to combine these drills into mixed sets. A ten-minute set might create a Deployment, expose it, add a ConfigMap, and verify traffic. A fifteen-minute set might add a Job, a CronJob, a readiness probe, and a cleanup step. A longer set should include a deliberate context switch and one broken resource. You are training decision-making under time pressure, so each drill should end with evidence, not just a command prompt.

## Worked Example: Turn a CKAD Prompt into Evidence

Exercise scenario: a mock task tells you to switch to the `kind-ckad-prep` context, work in the `apps` namespace, create a three-replica `orders` Deployment from `nginx`, expose it on port 80, add a ConfigMap value named `MODE=practice`, and prove the application is reachable from a temporary BusyBox Pod. The task looks simple, but it crosses four common failure boundaries: context, namespace, workload creation, and service selection. A learner who jumps straight to typing might finish quickly, or might create perfect resources in the wrong namespace and spend several minutes debugging a problem that is not really Kubernetes at all.

The first move is to translate the prompt into evidence requirements. The final answer is not "I ran commands." The final answer is "the required resources exist in the required namespace, the Deployment has the requested replica count, the Service selects the expected Pods, the ConfigMap exists with the requested key, and an in-cluster client can reach the Service." That evidence framing changes the work. You are no longer typing a linear recipe; you are building a small proof for each claim the prompt makes.

Start with target verification because it is the cheapest error to prevent. You would check the current context, switch if needed, create or select the `apps` namespace if the task permits it, and decide whether to pass `--namespace apps` on each command or set the namespace on the current context. Passing the namespace explicitly is slightly noisier, but it makes each command self-contained. Setting the context namespace is faster for repeated commands, but it requires a verification step so you do not accidentally carry that namespace into the next task.

Next, choose the creation path. A plain Deployment with an image and replica count is a pass-one task because `kubectl create deployment` can express it directly. Exposing the Deployment is also a pass-one task because `kubectl expose deployment` creates a Service with a selector derived from the Deployment labels. The ConfigMap literal is simple enough for an imperative command. The temporary BusyBox test Pod is also an imperative command, but it should run after the Service exists so its failure tells you something about networking rather than missing resources.

After creation, inspect the Deployment before testing the Service. The useful evidence is not merely that the Deployment object exists. You want desired, updated, and available replicas to converge, or you want events that explain why they do not. If the Pods are pending, a Service test will fail for the wrong reason. If the Pods are running but not ready, a Service may have no ready endpoints. This is where CKAD starts to reward sequencing rather than raw command memory.

Now inspect labels and selectors. A Deployment creates Pods with labels, and a Service routes to Pods whose labels match its selector. If you created the Service through `kubectl expose deployment`, the selector is usually correct, but "usually" is not evidence. A quick look at Pod labels, Service selector, and endpoints confirms the traffic path. If endpoints are empty, changing the Service port without checking labels is guesswork. If endpoints exist, the next failure is more likely to be container port, application response, DNS, or network policy.

The ConfigMap value needs its own proof. A task might only require creating the ConfigMap, in which case `kubectl get configmap orders-config -o yaml` is enough. If the task requires the Deployment to consume the ConfigMap, existence is not enough; you must inspect the Pod spec or execute inside a container to verify the environment variable or mounted file. CKAD prompts often use precise wording. "Create a ConfigMap" and "configure the application to use a ConfigMap" are different jobs, and treating them as the same job creates silent partial credit risk.

The reachability test should come from inside the cluster because a ClusterIP Service is not designed for direct access from your laptop. A temporary BusyBox Pod using `wget` or a similar client tests the same DNS and Service routing path another Pod would use. If that test fails, split the problem. First confirm the Service DNS name and namespace. Then confirm endpoints. Then confirm the target port and container response. This layered approach prevents the common habit of editing whichever manifest you touched most recently.

Suppose the test fails with a DNS error. That points toward name, namespace, or cluster DNS, not toward the Deployment image. If the temporary Pod runs in `default` while the Service lives in `apps`, the short name `orders` may not resolve as expected. Use the fully qualified service name or run the test Pod in the same namespace. This is a developer-facing networking issue, and it appears simple only after you have trained yourself to separate DNS, selection, readiness, and application response.

Suppose the test reaches the Service but returns a connection error. That shifts attention to endpoints and ports. The Service might expose port 80 but target a container port that does not listen, or it might have no endpoints because readiness is failing. A correct CKAD response is to inspect the Service and endpoints before rebuilding the Deployment. Kubernetes gives you enough state to narrow the failure, and the exam rewards candidates who read that state instead of thrashing.

Suppose the Deployment has the wrong replica count because you typed quickly and missed the requested value. This is exactly why verification belongs in the workflow, not at the end of the exam. Scaling the Deployment is cheap if you notice immediately. Discovering the mismatch ten tasks later is expensive because you have to reconstruct what happened under time pressure. The habit is to compare the prompt against live state before you mark the task complete.

This worked example also shows why a study plan should include mixed drills. If you practice only Deployment creation, the Service selector feels like a separate topic. If you practice only Services, namespace mistakes feel like background noise. If you practice only ConfigMaps, you may forget to prove consumption. A mixed prompt forces you to preserve the relationships among objects, which is the real CKAD skill behind many simple-looking tasks.

There is a useful scoring lesson here. A partially complete task can still earn value if the correct resources exist and the main relationship is clear, but a resource in the wrong namespace may be invisible to the grader for that task. A Service with no matching endpoints is often worse than no Service because it looks complete until someone tests traffic. A ConfigMap that exists but is not consumed may satisfy only part of the request. Verification tells you which kind of partial answer you have.

When you review your attempt, classify every delay. If you forgot the command shape, add an imperative drill. If you wrote the object in the wrong namespace, add a context drill. If your Service had no endpoints, add a label-selector drill. If the ConfigMap existed but the Pod did not consume it, add an environment-injection drill. This classification turns failure into a study plan instead of a vague feeling that you need more practice.

The same analysis works for harder prompts. Replace the Deployment with a Job and the lifecycle decision changes. Add a readiness probe and the endpoint check becomes more important. Add a sidecar and container-specific logs become part of the proof. Add a NetworkPolicy and the reachability test must include both an allowed and a blocked source. The mechanics scale because the workflow is evidence-driven: identify the claim, create the smallest correct object, inspect the state, and prove the behavior.

## Patterns & Anti-Patterns

CKAD preparation works best when you treat commands as part of a feedback loop. The pattern is not "type faster." The pattern is "create a valid starting point, edit the meaningful fields, apply the object, inspect the result, and use the evidence to decide the next command." That loop is small enough to repeat many times and broad enough to handle most developer-facing Kubernetes tasks.

| Pattern | When to Use It | Why It Works |
|---------|----------------|--------------|
| Generate first, then edit | The resource has a common starter shape but needs custom fields | `kubectl --dry-run=client -o yaml` prevents blank-page YAML mistakes while leaving room for probes, env, volumes, and security fields. |
| Verify the traffic path | A Service, Ingress, NetworkPolicy, or readiness probe is involved | Checking labels, selectors, endpoints, and readiness status finds the real break instead of assuming the newest object is wrong. |
| Practice by scenario | You are deciding among Pod, Deployment, Job, CronJob, init, sidecar, and Service | Scenario framing trains the same resource-selection skill the exam uses, while object-only notes encourage recall without judgment. |

The strongest anti-pattern is studying CKAD as a list of isolated object manifests. Isolated manifests look productive because they create many pages of notes, but they hide the relationships that make Kubernetes useful. A Deployment needs labels that a Service can select. A Secret must be referenced by the correct key. A readiness probe changes endpoint routing. A NetworkPolicy depends on selectors from both sides of the connection. If your study method does not force those relationships into view, it will not prepare you for debugging.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Relearning cluster administration first | Time goes into nodes and control-plane mechanics instead of developer tasks | Review CKA basics briefly, then shift to application resources and workflows. |
| Copying aliases into runnable examples | Commands fail in scripts or pasted shells where aliases are not expanded | Type full `kubectl` commands in practice material and automate only after the habit is clear. |
| Treating pass rate folklore as planning data | Study effort follows anecdotes rather than official domain weight and personal weakness | Use domain weights, timed drills, and failed-task logs to decide what to practice next. |

Use the patterns when you can describe the resource relationship in plain language. If you cannot explain why a Service should select a Pod, why a readiness probe blocks traffic, or why an init container is different from a sidecar, do not reach for a larger manifest yet. Slow down and build the smallest scenario that exposes that relationship. The exam rewards completion, but preparation rewards deliberate isolation.

## When You'd Use This vs Alternatives

This overview module is useful when you are choosing how to prepare, not when you need deep syntax for a single resource. If you are deciding whether CKAD is the right next credential after CKA, use the comparison and domain weights. If you are deciding how to split limited study hours, use the planning table. If you are about to sit a mock exam, use the three-pass method and timed drills. If you need detailed probe, Job, Helm, Kustomize, or NetworkPolicy instruction, move to the dedicated modules after this orientation.

| Situation | Use This Overview | Use a Dedicated Module |
|-----------|-------------------|------------------------|
| You need to choose study priorities | Yes, because domain weights and overlap guide scheduling | Not first, because deep syntax can distract from planning. |
| You missed a mock task involving probes | Yes, to classify the failure as workflow, syntax, or concept | Yes, then drill the observability module until probe decisions are automatic. |
| You can create resources but run out of time | Yes, because three-pass sequencing is the likely gap | Maybe, if one resource family repeatedly causes the delay. |
| You cannot explain Services or ConfigMaps yet | Briefly, to see why they matter for CKAD | Yes, return to fundamentals before increasing exam speed. |

The decision rule is simple: use this module to decide what to practice and how to pace the exam, then use the later modules to build depth. A learner who stays in overview mode too long becomes good at naming topics without solving tasks. A learner who skips overview mode entirely can become good at individual commands while misallocating study time. Good preparation alternates between the map and the terrain.

## Did You Know?

- **CKA launched in 2017, and CKAD followed in May 2018.** CKAD was created for developers who design, build, configure, and expose applications on Kubernetes without necessarily managing the cluster itself.
- **The current CNCF CKAD page lists five domains with weights of 20%, 20%, 15%, 25%, and 20%.** Those numbers are a planning tool because the largest domain is environment, configuration, and security.
- **The CKAD exam is performance-based and runs for approximately two hours.** That format rewards command-line execution and verification, not just knowing resource definitions in theory.
- **CNCF states that quarterly exam updates are planned to match Kubernetes releases.** For this curriculum, practice with Kubernetes 1.35 or newer so your commands and API versions stay current.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Focusing too much on cluster admin | CKA habits make nodes, control-plane repair, and storage internals feel more important than CKAD application tasks | Review the shared basics briefly, then spend most practice time on developer workflows, probes, configuration, Jobs, Services, and debugging. |
| Ignoring init containers | They look like a small Pod feature until a task requires setup ordering before the main container starts | Practice scenarios where an init container downloads config, waits for a dependency, or prepares a shared volume. |
| Not knowing probe syntax | Probe fields are precise, and learners often confuse liveness, readiness, and startup responsibilities | Memorize one minimal probe shape, then drill which probe type matches each failure mode. |
| Skipping Jobs and CronJobs | Long-running web apps feel more familiar, so finite and scheduled workloads receive less repetition | Create one Job and one CronJob in every mixed drill until command generation and verification are automatic. |
| Only using `kubectl apply` | Declarative habits are good in production but can be slow when the exam asks for a simple object | Use imperative creation and dry-run generation for starter manifests, then edit only the fields the task requires. |
| Forgetting context and namespace checks | Multiple contexts make it possible to apply correct YAML to the wrong target | Start each task by confirming context and namespace, then verify resources in that same target before moving on. |
| Studying object kinds without resource relationships | Separate notes hide how labels, selectors, probes, endpoints, and policies interact | Build small scenarios that force one relationship at a time, then inspect the evidence with `kubectl get`, `describe`, and logs. |

## Quiz

<details>
<summary>Question 1: You passed CKA last month and have ten study evenings before CKAD. You can already create Pods, Deployments, and Services, but you are slow with ConfigMaps, Secrets, probes, Jobs, and CronJobs. How should you design the study plan?</summary>

Prioritize the weak developer-facing areas instead of spending most evenings replaying CKA fundamentals. The official weights make environment, configuration, and security the largest domain, so ConfigMaps, Secrets, resource settings, ServiceAccounts, and SecurityContexts deserve a large block. Jobs, CronJobs, probes, and multi-container patterns should come next because they are common CKAD differentiators. Keep one or two mixed sessions for Pods, Deployments, and Services so the basics remain fast, but do not let familiar work consume the schedule.
</details>

<details>
<summary>Question 2: During a timed mock, you start with a complex multi-container Pod that needs an init container, a sidecar, a shared volume, and log verification. After ten minutes, it still fails. What should you do next?</summary>

Mark the task and move to faster work unless the fix is immediately obvious. That kind of task belongs in the later pass because it has several fields and several possible failure points. Continuing to fight it early risks losing simple points from Deployments, Services, ConfigMaps, or Jobs. Return after harvesting quick wins, then debug with events, container status, and logs rather than rewriting the whole manifest blindly.
</details>

<details>
<summary>Question 3: A Service object exists, but your test Pod cannot reach the web app through the Service name. The Deployment Pods are running. What do you inspect before changing the application image?</summary>

Inspect the Service selector, the Pod labels, the endpoints, and the readiness state. A Service can exist without selecting any ready Pods, so the object alone does not prove traffic can flow. If labels do not match, update the selector or labels according to the task. If endpoints are empty because readiness fails, fix the readiness probe or application path before blaming the image.
</details>

<details>
<summary>Question 4: A task asks for a cleanup process to run every hour and print the current date. You create a Deployment because it is the workload kind you know best. Why is that the wrong resource choice?</summary>

A Deployment manages long-running replicated Pods, while the scenario describes scheduled finite work. The better fit is a CronJob because it creates Jobs on a schedule and each Job runs to completion. Using a Deployment would leave a container running continuously or require custom scheduling logic inside the application. CKAD expects you to choose the Kubernetes primitive that matches the workload lifecycle.
</details>

<details>
<summary>Question 5: You apply a manifest successfully, but `kubectl get pods` shows the Pod in the wrong namespace. The task named a namespace in the first sentence. What exam workflow mistake caused this, and how do you prevent it?</summary>

The mistake was treating context and namespace as background setup instead of part of the task. A successful API response only proves the object was accepted somewhere, not that it was accepted in the required target. Prevent it by checking the current context, setting or passing the namespace before applying resources, and verifying with the same namespace immediately afterward. This is a workflow bug, not a Kubernetes concept gap.
</details>

<details>
<summary>Question 6: Your Pod restarts repeatedly after a liveness probe is added, but the application normally takes a long time to boot. Which probe strategy should you consider?</summary>

Consider a startup probe so Kubernetes gives the slow-starting application time before liveness restarts are enforced. Liveness should detect a process that is no longer healthy after startup, not punish a process that is still initializing. Readiness may also be needed to keep traffic away until the app can serve requests. The key is to map probe type to lifecycle phase rather than increasing every delay without understanding the symptom.
</details>

<details>
<summary>Question 7: A teammate says CKAD should be easy because it shares Pods, Services, ConfigMaps, Secrets, and NetworkPolicies with CKA. What is missing from that comparison?</summary>

The comparison lists shared objects but ignores the different job being tested. CKAD asks whether an application developer can use those objects to package, configure, expose, observe, and debug workloads. CKA asks whether an administrator can operate the cluster that runs those workloads. The overlap is real, but CKAD adds developer-specific depth around probes, Jobs, CronJobs, multi-container patterns, deployment workflows, and application debugging.
</details>

## Hands-On Exercise

Exercise scenario: you are preparing a clean CKAD practice namespace and want to prove that your basic developer workflow is ready before moving into deeper modules. You will create a Deployment, expose it, add configuration, add a Secret with a training value, generate YAML for later edits, check context, and clean up. The exercise is intentionally small, but it touches the workflow habits that prevent many exam mistakes.

Complete the first success criteria in under five minutes once the cluster is ready. If you struggle, do not continue by reading faster. Return to the relevant fundamentals and repeat the drill until the verification step feels routine. The exercise is not measuring whether you can type a command once; it is measuring whether you can create, expose, configure, verify, and clean up without losing your place.

```bash
# 1. Create a deployment with 3 replicas
kubectl create deployment ckad-test --image=nginx --replicas=3

# 2. Expose it as a ClusterIP service
kubectl expose deployment ckad-test --port=80

# 3. Create a ConfigMap
kubectl create configmap ckad-config --from-literal=env=production

# 4. Create a Secret with a training placeholder value
kubectl create secret generic ckad-secret --from-literal=password=your-password-here

# 5. Verify everything
kubectl get deploy,svc,cm,secret | grep ckad
```

<details>
<summary>Solution notes for the baseline drill</summary>

The Deployment should show three desired replicas, the Service should exist as a ClusterIP Service, and the ConfigMap and Secret should both appear in the resource list. If the command output is empty, check the namespace and context before recreating resources. If the Deployment exists but Pods are not ready, inspect the Pod events and image pull status. The Secret value is a training placeholder; do not use realistic credentials in practice manifests.
</details>

```bash
# Cleanup
kubectl delete deployment ckad-test
kubectl delete service ckad-test
kubectl delete configmap ckad-config
kubectl delete secret ckad-secret
```

Now expand the same workflow with progressive tasks. Each task should produce observable evidence, and each cleanup should remove only the resources you created. If a task fails, write down the failure category: command recall, YAML shape, context, namespace, selector, probe behavior, or workload choice. That failure log becomes your next study plan.

- [ ] **Implement a Kubernetes 1.35+ practice environment with kind and confirm the active `kubectl` context.**
- [ ] **Create and expose the `ckad-test` Deployment, then verify the Service and selected Pods.**
- [ ] **Generate dry-run YAML for a Pod, Deployment, and ClusterIP Service, then inspect the generated files before applying anything.**
- [ ] **Create one Job and one CronJob, verify their resources, and explain why neither should be a Deployment.**
- [ ] **Apply the probed Pod manifest from the speed drill, then use `kubectl describe` to prove liveness, readiness, and startup probes are present.**
- [ ] **Clean up all resources from the exercise and verify the namespace no longer contains the named practice objects.**

<details>
<summary>Expanded solution guide</summary>

Start by creating the kind cluster if it does not already exist, then run `kubectl config current-context` and confirm it points to `kind-ckad-prep`. Create the Deployment and Service with the baseline commands, then inspect `kubectl get pods --show-labels`, `kubectl get service ckad-test`, and `kubectl get endpoints ckad-test` so you see the label-selector relationship. Generate YAML files with `--dry-run=client -o yaml` and read the first lines before applying any generated object. For the Job and CronJob, use the preserved speed-drill commands and verify with `kubectl get job,cronjob`. For the probed Pod, apply the manifest from the drill and use `kubectl describe pod probed-app` to inspect probe sections. Clean up by deleting each named resource and confirm with a final `kubectl get pod,deploy,svc,job,cronjob,cm,secret`.
</details>

## Learner check

Before moving on, make sure you can explain why this drill command now works as written — specifically why `--target-port` must match the container's listening port (nginx serves on 80), or the Service ends up with zero ready endpoints:

> kubectl expose deployment web --port=80 --target-port=80

## Sources

- https://www.cncf.io/training/certification/ckad/
- https://github.com/cncf/curriculum/blob/master/CKAD_Curriculum_v1.35.pdf
- https://docs.linuxfoundation.org/tc-docs/certification/lf-handbook2
- https://docs.linuxfoundation.org/tc-docs/certification/tips-cka-and-ckad
- https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/
- https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/job/
- https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
- https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/
- https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/service/
- https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/
- https://kind.sigs.k8s.io/docs/user/quick-start/

## Next Module

[Module 0.2: Developer Workflow](../module-0.2-developer-workflow/) - Optimize your kubectl patterns for CKAD speed.
