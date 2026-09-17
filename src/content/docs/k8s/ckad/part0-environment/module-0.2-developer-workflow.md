---
citations_verified: true
title: "Module 0.2: Developer Workflow"
slug: k8s/ckad/part0-environment/module-0.2-developer-workflow
sidebar:
  order: 2
lab:
  id: ckad-0.2-developer-workflow
  url: https://killercoda.com/kubedojo/scenario/ckad-0.2-developer-workflow
  duration: "30 min"
  difficulty: intermediate
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Long-form kubectl workflow module for CKAD speed and accuracy
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: Module 0.1 (CKAD Overview), basic shell comfort, and enough Kubernetes vocabulary to recognize Pods, Deployments, Services, Jobs, ConfigMaps, Secrets, and namespaces

---

## Learning Outcomes

After completing this module, you will be able to:

- **Design** a repeatable kubectl workflow that turns exam prompts into generated YAML, small edits, applied resources, and verified outcomes without wasting time.
- **Debug** common developer-resource failures using `kubectl describe`, `kubectl logs`, `kubectl exec`, events, JSONPath, and namespace checks.
- **Compare** imperative commands, generated manifests, and direct YAML authoring so you can choose the fastest reliable path for each CKAD task.
- **Evaluate** whether a resource was created in the right namespace, with the right container command, exposed through the right Service, and cleaned up after testing.
- **Implement** multi-container Pod, Job, CronJob, ConfigMap, Secret, and connectivity checks using patterns that are runnable on Kubernetes 1.35+ clusters.

---

## Why This Module Matters

A developer fails an on-call handoff because the Deployment was correct, the Service was correct, and the command history looked convincing, but every object landed in the previous namespace. The team spends the first minutes looking at application logs, then network policy, then image tags, while the real failure sits in plain sight: the workflow never forced the developer to prove where they were working before creating resources.

CKAD has the same shape. The exam rarely asks whether you can recite the definition of a Pod. It asks whether you can transform a scenario into a working Kubernetes object while the clock is moving. Knowledge matters, but workflow decides whether that knowledge reaches the cluster accurately. A strong workflow makes the right thing the easy thing: set context, generate a manifest, edit the smallest safe surface, apply it, verify it from inside the cluster, and leave no accidental resources behind.

This module treats `kubectl` as a developer workbench, not a command encyclopedia. You will learn when to create imperatively, when to generate YAML first, when to inspect live state, and when to abandon a command path because editing a manifest is safer. The goal is not to type the fewest characters once. The goal is to finish many tasks with low error rates, because speed without verification is just a faster way to lose points.

> **The Workshop Bench Analogy**
>
> A careful craftsperson does not throw every tool onto the bench and hope the right one appears. The measuring tape, square, pencil, saw, and clamps each have a fixed place because repeated work becomes reliable when the setup is deliberate. Your CKAD workflow should feel the same: alias, namespace, dry run, edit, apply, verify, and clean up in a sequence you can repeat under pressure.

---

## Core Workflow: From Prompt to Verified Resource

The developer workflow begins before you create anything. A CKAD prompt usually gives you a namespace, a resource type, a name, an image, ports, environment values, command behavior, and a verification requirement. If you start typing from the first noun you recognize, you risk solving only part of the task. Senior Kubernetes practitioners pause long enough to classify the task, because classification determines the safest path through `kubectl`.

Use `kubectl` once in full when documenting or teaching commands, then use the alias `k` for speed after you have defined it. In this module, `k` means `kubectl`. You should still understand every expanded command, because aliases help only when they shorten correct behavior. An alias that hides confusion simply lets you be wrong faster.

```bash
alias k='kubectl'
```

The first decision is whether the resource can be created correctly with one imperative command. Simple Pods, Deployments, Services, Jobs, CronJobs, ConfigMaps, and Secrets often can. Multi-container Pods, shared volumes, probes, security context, environment-from references, and nontrivial commands usually need generated YAML followed by editing. The high-skill move is not memorizing every flag; it is knowing when to stop forcing flags and switch to a manifest.

```text
+---------------------+      +----------------------+      +-------------------+
| Read exam prompt    | ---> | Classify resource    | ---> | Choose creation   |
| namespace, name,    |      | Pod, Deployment,     |      | imperative, dry   |
| image, ports, data  |      | Service, Job, etc.   |      | run, or YAML      |
+---------------------+      +----------------------+      +-------------------+
          |                              |                            |
          v                              v                            v
+---------------------+      +----------------------+      +-------------------+
| Set namespace       | ---> | Generate or edit     | ---> | Apply, inspect,   |
| or pass -n every    |      | the smallest safe    |      | test, and clean   |
| time deliberately   |      | manifest surface     |      | up test objects   |
+---------------------+      +----------------------+      +-------------------+
```

A useful mental model is "read, decide, build, prove." Read the prompt for constraints. Decide which workflow fits. Build only the object you need. Prove it from the cluster's point of view, not just from your terminal's exit code. This sequence prevents the common failure where the YAML is syntactically valid but behavior is still wrong.

> **Active learning prompt**: Read this scenario before looking ahead: "Create a Pod named `probe-demo` with image `nginx`, then verify the container image that actually reached the API server." Would you use `k run` directly, generate YAML first, or write YAML from scratch? Decide why, then compare your answer to the workflow below.

For a simple Pod with no extra fields, direct imperative creation is acceptable because the command maps cleanly to the requested object. Verification still matters. You are not finished when the command exits. You are finished when the live object has the expected shape and the Pod reaches a usable state.

```bash
k run probe-demo --image=nginx
k wait --for=condition=Ready pod/probe-demo --timeout=90s
k get pod probe-demo -o jsonpath='{.spec.containers[0].image}'
k delete pod probe-demo
```

If the prompt adds a second container, a shared volume, a specific restart policy, or a command with quoting requirements, generated YAML becomes safer. The point of dry-run generation is not avoiding YAML. The point is avoiding blank-page YAML while still keeping full control over the final manifest. You let `kubectl` create the boilerplate, then you edit the parts that matter.

```bash
k run probe-demo --image=nginx --dry-run=client -o yaml > probe-demo.yaml
```

The rest of this module builds the workflow in layers. First you make your shell fast enough for repeated work. Then you generate manifests reliably. Then you edit common developer objects. Then you verify from logs, exec, events, and JSONPath. Finally, you practice the whole loop with timed drills that match how CKAD tasks feel.

---

## Shell Setup and Alias Discipline

Aliases are not magic, and they are not required for Kubernetes. They are useful because CKAD is a performance exam where repeated commands create repeated opportunities for typos. The key is to alias complete, well-understood habits rather than inventing a private language that becomes unreadable under stress. Every alias should reduce friction for a command you already know how to expand.

Add these to `~/.bashrc` or `~/.zshrc` in your practice environment. In the real exam terminal, confirm what is already configured before editing startup files. Some environments include `k` and completion, but you should be able to recreate your workflow quickly if the shell starts plain.

```bash
alias k='kubectl'

alias kaf='kubectl apply -f'
alias kdel='kubectl delete'
alias kd='kubectl describe'
alias kg='kubectl get'
alias kl='kubectl logs'
alias kx='kubectl exec -it'

alias kgy='kubectl get -o yaml'
alias kgw='kubectl get -o wide'

export kdr='--dry-run=client -o yaml'

alias kr='kubectl run'
alias kgpw='kubectl get pods -w'
```

The `kdr` variable deserves special attention because it is a shell variable, not a Kubernetes feature. The unquoted variable expands into two command-line arguments: `--dry-run=client` and `-o yaml`. That makes it convenient for practice, but you should also be comfortable typing the full flags. If your shell session does not have the variable, the explicit form always works.

```bash
k run web --image=nginx $kdr > web.yaml
k run web --image=nginx --dry-run=client -o yaml > web.yaml
```

CKAD tasks often include Jobs and CronJobs, and these are easy to generate incorrectly if you forget where the command begins. For Jobs, the command follows `--`. For CronJobs, the schedule is part of the resource definition, and the command still follows `--`. Treat `--` as a boundary: flags before it configure `kubectl`, and [words after it become the container command and arguments](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands/).

```bash
alias kcj='kubectl create job'
alias kccj='kubectl create cronjob'

k create job once --image=busybox -- echo complete
k create cronjob hourly --image=busybox --schedule="0 * * * *" -- date
```

Debug aliases should be short but not mysterious. A one-off debug Pod should use `--rm` so it disappears, `-it` when you need interactive output, and `--restart=Never` when the container command is meant to run once and exit. Without `--restart=Never`, a quick command can become a confusing lifecycle problem instead of a clean test.

```bash
alias kdebug='kubectl run debug --image=busybox --rm -it --restart=Never --'
alias klc='kubectl logs -c'
alias kctx='kubectl config use-context'
alias kns='kubectl config set-context --current --namespace'
```

Completion is also part of workflow quality. It reduces spelling mistakes for resource names and namespaces. Completion is not a substitute for understanding, but it is a valuable guardrail when a name is long or similar to another object. Configure it during practice so you can decide whether to configure it quickly in your exam environment.

```bash
source <(kubectl completion bash)
complete -o default -F __start_kubectl k
```

If you use Z shell, the setup is different but the goal is the same: make `k get po<Tab>` and resource-name completion work. Do not spend exam time debugging a fancy shell configuration. Your fallback should always be plain commands plus `k get` output copied accurately.

```bash
source <(kubectl completion zsh)
compdef __start_kubectl k
```

A senior workflow keeps aliases small enough to verify. After configuring them, test the commands against harmless resources. If an alias expands unexpectedly, fix it before you rely on it. The exam is not the place to discover that your local shell alias used a flag unsupported by the cluster's installed client.

```bash
type k
type kgy
echo "$kdr"
k version --client
```

> **Active learning prompt**: Suppose `echo "$kdr"` prints nothing during an exam task. What breaks, what still works, and how would you continue without spending time repairing shell startup files?

The correct answer is that nothing about Kubernetes breaks. Only your shortcut is missing. Continue with the explicit flags: `--dry-run=client -o yaml`. This is why every shortcut in this module is taught as a shorter form of a visible command, not as something you must memorize blindly.

---

## Namespace First: Prevent Correct Work in the Wrong Place

Namespace mistakes are especially painful because the commands can all succeed. You create the Deployment, expose it, inspect Pods, and run tests, but the grader looks in another namespace. That is worse than an immediate error because success output builds false confidence. The fix is a workflow rule: every task starts with namespace handling before resource creation.

There are two safe namespace styles. You can [set the current namespace for the session, or you can pass `-n` on every command](https://kubernetes.io/docs/tasks/administer-cluster/namespaces/). Setting the namespace is faster for a multi-command task, but it creates risk when you move to the next task. Passing `-n` is explicit and slightly longer. Use one style deliberately, and do not drift between them without checking.

```bash
k create ns dev
k config set-context --current --namespace=dev
k get pods
```

```bash
k get pods -n dev
k run web --image=nginx -n dev
k expose pod web --port=80 -n dev
```

The fastest namespace check is not the prettiest command; it is the one you will actually run. `k config view --minify` shows the current context and namespace. If no namespace appears, commands default to `default`. That absence is meaningful, so do not read it as "unknown." It means Kubernetes will use the `default` namespace unless you pass `-n`.

```bash
k config view --minify | grep namespace || true
```

A better exam habit is to set or pass the namespace at the start of every task, then verify the created object with the same namespace. This creates a closed loop: the command that creates the object and the command that proves it exists both point to the same place. If they disagree, you catch the issue immediately.

```bash
k create ns inventory
k config set-context --current --namespace=inventory
k create deploy api --image=nginx
k get deploy api
k get pods -l app=api
```

When switching tasks, reset deliberately. Do not rely on memory. If task one used `payments` and task two uses `inventory`, the first command for task two should mention `inventory` either by setting the context or by passing `-n inventory`. The tiny cost of that command is much lower than debugging invisible resources.

```bash
k config set-context --current --namespace=inventory
k config view --minify | grep namespace
```

> **Stop and think**: You finish a task in `payments`, then create a Service for the next task without switching to `inventory`. The Service exists, but the grader reports it missing. Which command would reveal the problem fastest, and how would you repair the state without deleting unrelated resources?

The fastest reveal is usually `k get svc -A | grep <service-name>` because it shows where the object actually landed. The repair depends on the resource. For exam tasks, the cleanest path is usually to recreate the object in the correct namespace, verify it there, and delete only the misplaced object if you are sure it is yours.

```bash
k get svc -A | grep api || true
k get svc api -n payments -o yaml > api-svc.yaml
```

If you export YAML from the wrong namespace, remove fields that should not be replayed and change the namespace carefully. For CKAD, it is often faster to regenerate the Service in the correct namespace than to sanitize exported YAML. Exporting live YAML includes server-managed fields that can distract you from the task.

```bash
k expose deploy api --port=80 -n inventory
k get svc api -n inventory
k delete svc api -n payments
```

---

## Dry-Run Generation: Fast YAML Without Blank-Page Risk

The dry-run pattern is the center of CKAD developer workflow. It gives you valid Kubernetes structure without creating the resource. That matters because many tasks require one or two custom fields beyond what an imperative command can express cleanly. Generating a manifest lets you start from valid `apiVersion`, `kind`, `metadata`, and common labels, then edit only the necessary fields.

```bash
k run nginx --image=nginx --dry-run=client -o yaml > pod.yaml
k create deploy web --image=nginx --replicas=3 --dry-run=client -o yaml > deploy.yaml
k create job backup --image=busybox --dry-run=client -o yaml -- echo done > job.yaml
k expose deploy web --port=80 --dry-run=client -o yaml > svc.yaml
```

When using the `kdr` shortcut, remember that redirection happens in your shell. The file is written by the shell, not by Kubernetes. If the command before `>` is wrong, you may still create an empty or partial file depending on the failure. Always inspect generated YAML before applying it when you have edited or redirected anything important.

```bash
export kdr='--dry-run=client -o yaml'

k run nginx --image=nginx $kdr > pod.yaml
sed -n '1,80p' pod.yaml
```

Dry-run generation is especially useful for resources whose syntax is easy to mistype. A Deployment generated by `k create deploy` includes the correct selector and template label pairing. Writing those fields from scratch is possible, but it is also a place where [small mismatches cause a Deployment that never owns its Pods](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/). Let the tool generate the relationship, then edit the image, replicas, ports, or environment values as needed.

```bash
k create deploy web --image=nginx --replicas=2 $kdr > web-deploy.yaml
k apply -f web-deploy.yaml
k rollout status deploy/web --timeout=90s
```

Service generation has two reliable paths. You can expose an existing resource, or you can create a Service directly. Exposing a Deployment is convenient because [Kubernetes uses the Deployment's labels to build the selector](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_expose/). Creating a Service directly is useful when the backing Pods already have known labels or when the prompt specifically asks for a Service manifest.

```bash
k expose deploy web --port=80 --target-port=80 $kdr > web-svc.yaml
k create svc clusterip web --tcp=80:80 $kdr > web-svc-direct.yaml
```

For Jobs and CronJobs, dry-run generation prevents a common timing problem. If you run the object directly, the Job may start and finish before you notice that the command was wrong. Generating YAML first lets you inspect the container command and restart policy before the controller acts on it.

```bash
k create job backup --image=busybox $kdr -- sh -c 'echo backup complete' > backup-job.yaml
k create cronjob hourly --image=busybox --schedule="0 * * * *" $kdr -- sh -c 'date' > hourly-cronjob.yaml
```

A strong workflow uses `kubectl explain` as a targeted reference, not as a reading project. [If you forget where a field belongs, ask the API schema](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_explain/). This is faster and safer than guessing indentation. For example, container `env` belongs under a container, while `volumes` belongs under `spec`.

```bash
k explain pod.spec.containers.env
k explain pod.spec.volumes
k explain deployment.spec.template.spec.containers.readinessProbe
```

> **Active learning prompt**: You need a Deployment with a readiness probe. Would you keep trying to express the probe through `k create deploy` flags, or generate the Deployment and edit YAML? Explain the trade-off before moving on.

Generate and edit YAML. The readiness probe is nested inside the Pod template's container spec, and forcing it through imperative shortcuts would be slower and less reliable. The dry-run pattern gives you the Deployment skeleton, including selectors and template labels, so you can add the probe in the correct location.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 10
```

Apply only after the manifest tells a coherent story. Labels in the selector and Pod template must match. Container names must match the names you will use with `logs -c` or `exec -c`. Ports referenced by probes and Services must match actual container ports or application listeners. YAML validity is only the first gate; Kubernetes behavior is the real test.

```bash
k apply -f web-deploy.yaml
k rollout status deploy/web --timeout=90s
k get deploy web -o wide
k describe deploy web
```

---

## Imperative Commands, Manifests, and the Decision Matrix

Not every task deserves a manifest file. If the prompt says "create a Pod named `web` using image `nginx`," direct imperative creation is fast and accurate. If the prompt says "create a Pod named `web` with two containers sharing a volume," direct imperative creation is the wrong tool. The practitioner skill is choosing the workflow that minimizes total time, including verification and repair.

| Task Pattern | Best Starting Point | Why This Works | Verification Command |
|--------------|--------------------|----------------|----------------------|
| Simple one-container Pod | `k run` directly or dry-run YAML | The command maps cleanly to the requested object | `k get pod NAME -o wide` |
| Deployment with replicas | `k create deploy` | The generated selector and template labels align automatically | `k rollout status deploy/NAME` |
| Service for an existing Deployment | `k expose deploy` | The selector is derived from existing labels | `k get endpointslices -l kubernetes.io/service-name=NAME` |
| Multi-container Pod | `k run ... $kdr`, then edit | Imperative flags cannot express multiple containers cleanly | `k get pod NAME -o jsonpath='{.spec.containers[*].name}'` |
| Job or CronJob with command | `k create job` or `k create cronjob` | The command boundary after `--` is explicit | `k get jobs` or `k get cronjobs` |
| ConfigMap or Secret from literals | `k create cm` or `k create secret` | Imperative creation avoids indentation mistakes | `k get cm NAME -o yaml` |
| Probe, volume, envFrom, securityContext | Generate YAML, then edit | Nested fields are easier to place correctly in a manifest | `k describe pod` and events |

A direct imperative command is best when the prompt and the command have the same shape. A generated manifest is best when the prompt adds structure below `spec`. Hand-written YAML is best only when generation would take longer than writing a small known object, or when you are adapting a pattern you have practiced many times. In the exam, pride has no value; choose the path that gets a correct object verified fastest.

Worked example: the prompt says, "In namespace `demo`, create a Deployment named `api` using image `nginx`, two replicas, and expose it internally on port 80. Verify it is reachable from inside the cluster." This is a clean imperative workflow because each required object has a direct command.

```bash
k create ns demo
k config set-context --current --namespace=demo
k create deploy api --image=nginx --replicas=2
k rollout status deploy/api --timeout=90s
k expose deploy api --port=80 --target-port=80
k get svc api
k run test --image=busybox --rm -it --restart=Never -- wget -qO- http://api
k config set-context --current --namespace=default
k delete ns demo
```

Now compare a similar prompt: "Create a Pod named `api` with an `nginx` container and a `busybox` sidecar that sleeps for one hour." The resource name sounds simple, but the structure is not a one-command Pod anymore. Generate the base Pod, edit the second container, apply, and verify both containers exist.

```bash
k run api --image=nginx $kdr > api-pod.yaml
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api
  labels:
    run: api
spec:
  containers:
  - name: api
    image: nginx
  - name: sidecar
    image: busybox
    command: ["sleep", "3600"]
```

```bash
k apply -f api-pod.yaml
k wait --for=condition=Ready pod/api --timeout=90s
k get pod api -o jsonpath='{.spec.containers[*].name}'
k logs api -c sidecar --tail=5
```

The verification step reveals another senior habit: verify the behavior that matters, not just the existence of the object. A multi-container Pod can exist while one container is crashing. A Service can exist without endpoints. A Job can exist without completing. A ConfigMap can exist with the wrong key. Your command sequence should prove the specific claim the prompt asks you to satisfy.

---

## YAML Editing Without Breaking Structure

YAML editing is where many otherwise strong candidates lose time. Kubernetes manifests are indentation-sensitive, and the most common failure is not a Kubernetes concept failure; it is a field placed at the wrong level. Use generation to get the outer structure, then make small edits with clear before-and-after intent. You are not writing a novel in YAML. You are placing fields exactly where the API expects them.

Vim configuration can remove friction if you use Vim. If you use another editor in practice, know the exam environment may still favor terminal editing. These settings make two-space YAML indentation predictable.

```vim
set tabstop=2
set shiftwidth=2
set expandtab
set autoindent
```

The fastest Vim commands for CKAD are the ones that support duplication, indentation, search, and saving. You do not need to become a Vim expert to pass CKAD, but you need enough fluency to duplicate a container block and move fields without damaging indentation.

```vim
yy
p
dd
>>
<<
/image
:50
:wq
```

When adding a sidecar, copy a complete container block rather than typing every line from scratch. Then edit the copied name, image, and command. This reduces syntax risk because list markers and indentation already match the manifest. The critical detail is that the second `- name:` line must align with the first container's `- name:` line.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi
spec:
  containers:
  - name: main
    image: nginx
  - name: sidecar
    image: busybox
    command: ["sleep", "3600"]
```

The placement of `volumes` and `volumeMounts` is a classic source of mistakes. [`volumes` belongs under `spec` because it describes storage available to the Pod. `volumeMounts` belongs under each container because it describes where that container sees the storage](https://kubernetes.io/docs/concepts/configuration/configmap/). If you reverse those levels, the manifest may be rejected or the container may start without the expected files.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: shared-logs
spec:
  volumes:
  - name: logs
    emptyDir: {}
  containers:
  - name: web
    image: nginx
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx
  - name: reader
    image: busybox
    command: ["sh", "-c", "tail -f /var/log/nginx/access.log"]
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx
```

Environment variables have a similar level rule. `env` belongs under a container, because environment variables are injected into a specific container process. A ConfigMap object can be generated separately, then referenced from the Pod or Deployment. This separation is important because a prompt may ask you to create both the data source and the workload that consumes it.

```bash
k create cm app-config --from-literal=MODE=prod --from-literal=LOG_LEVEL=info
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: env-demo
spec:
  containers:
  - name: app
    image: busybox
    command: ["sh", "-c", "env && sleep 3600"]
    envFrom:
    - configMapRef:
        name: app-config
```

After editing YAML, use server-side feedback quickly. [`k apply --dry-run=server -f file.yaml` asks the API server to validate the manifest without persisting it](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/). Client dry-run generates or validates locally, but server dry-run catches schema and admission behavior closer to the cluster you are using. If server dry-run passes, applying the file is less risky.

```bash
k apply --dry-run=server -f env-demo.yaml
k apply -f env-demo.yaml
```

> **Active learning prompt**: In the shared-volume Pod above, what would happen if `volumeMounts` were placed under `spec` beside `volumes` instead of under each container? Predict whether the API accepts it, then use `k explain pod.spec.containers.volumeMounts` to confirm where the field belongs.

The broader lesson is that `kubectl explain` is part of the editing workflow. You do not need to memorize every field path. You need to know how to discover the path quickly and apply it correctly. The API schema is the source of truth during the exam.

```bash
k explain pod.spec.containers.volumeMounts
k explain pod.spec.volumes.emptyDir
k explain pod.spec.containers.envFrom.configMapRef
```

---

## Quick Testing Patterns From Inside the Cluster

A Service that responds from your laptop is not the same as a Service that resolves from inside the cluster. CKAD tasks often care about in-cluster behavior, so your verification should use a temporary Pod in the same namespace. The pattern is short, but each flag has a job: `--rm` cleans up, `-it` connects your terminal, `--restart=Never` creates a one-shot Pod, and the command after `--` performs the test.

```bash
k run test --image=busybox --rm -it --restart=Never -- wget -qO- http://service-name
```

BusyBox is useful because it is small and commonly available, but it may not include every tool you want in every image tag. For HTTP behavior, `curlimages/curl` is often clearer. For DNS checks, BusyBox `nslookup` is usually enough. Pick the image that matches the question, and do not waste time installing tools into a temporary Pod.

```bash
k run dns-test --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default.svc
k run curl-test --image=curlimages/curl --rm -it --restart=Never -- curl -sS http://service-name
```

The `--restart=Never` flag matters because it sets the Pod's restart policy for one-off command execution. If a test command exits successfully and the Pod is configured to restart, the cluster may keep restarting it or make the lifecycle harder to interpret. A clean test Pod should run, show output, exit, and disappear.

```bash
k run once --image=busybox --restart=Never -- echo done
k get pod once
k delete pod once
```

When a Service test fails, do not jump straight to application debugging. Work from the network object backward. First confirm the Service exists in the namespace. Then confirm it has a selector. Then confirm endpoint slices exist for matching Pods. Then confirm the Pods are Ready. This sequence prevents you from reading logs for an application that the Service does not even select.

```bash
k get svc backend
k describe svc backend
k get endpointslices -l kubernetes.io/service-name=backend
k get pods --show-labels
```

EndpointSlices are the modern way Kubernetes tracks Service backends. You may still see examples using `k get endpoints`, and that can be useful, but EndpointSlices give more current detail on newer clusters. In CKAD practice, either can reveal the most important fact: whether the Service currently has backends.

```bash
k get endpoints backend
k get endpointslices -l kubernetes.io/service-name=backend -o wide
```

> **Stop and think**: A Service exists, and DNS resolves, but `wget http://backend` times out. What should you inspect before changing the application image?

Inspect the Service selector and the backend Pods' labels before changing the image. A selector mismatch creates a perfectly valid Service with no useful backends. [If EndpointSlices are empty, the request has nowhere to go. If endpoints exist but the request still fails, then check container ports, readiness, logs, and application behavior](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/).

```bash
k describe svc backend
k get pods --show-labels
k get pod -l app=backend -o wide
k logs -l app=backend --tail=20
```

Temporary debug Pods should not become clutter. If an interactive test is interrupted, `--rm` may not always remove the object immediately. Check and clean up by label or name. Leaving extra Pods usually does not fail a task by itself, but clutter makes later debugging slower and can confuse your own verification.

```bash
k get pods
k delete pod test dns-test curl-test --ignore-not-found
```

---

## Logs, Exec, Describe, Events, and JSONPath

Debugging is a narrowing process. `k get` tells you what exists and broad status. `k describe` tells you scheduling, events, container state, probes, mounts, and image pull behavior. `k logs` tells you what the application wrote. `k exec` lets you inspect from inside a running container. JSONPath extracts exactly the field a prompt asks for without manual copying.

Start with `k get` when you need orientation. Use `-o wide` when placement, IP, or node information matters. Use labels when you need to connect a Deployment, ReplicaSet, Pod, and Service. The goal is to reduce the problem space before you inspect details.

```bash
k get pods
k get pods -o wide
k get deploy,rs,pod
k get pods --show-labels
```

Use `k describe` when Kubernetes is making a decision you do not understand. Scheduling failures, image pull errors, crash loops, failed mounts, and readiness probe failures usually show useful events. Events are time-ordered clues from controllers and kubelet. They often explain the failure faster than logs.

```bash
k describe pod web
k describe deploy web
k get events --sort-by=.metadata.creationTimestamp
```

Use logs when the container starts far enough to write output. [For a single-container Pod, `k logs pod-name` is enough. For a multi-container Pod, specify `-c` to avoid ambiguity. If a container restarted, `--previous` often contains the crash output you need](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), while current logs may be empty or misleading.

```bash
k logs web --tail=20
k logs web -f
k logs multi -c sidecar --tail=20
k logs web --previous
```

Use exec when you need to inspect files, environment, DNS, or local process behavior inside a running container. Keep exec commands focused. If you need only one file, run `cat`. If you need a shell, use `sh` because many minimal images do not include `bash`.

```bash
k exec web -- printenv
k exec web -- cat /etc/resolv.conf
k exec -it web -- sh
k exec multi -c sidecar -- ps
```

JSONPath is best when the task asks for a precise value. Copying from `describe` is slow and error-prone. Grepping YAML can work, but it can also match the wrong field. JSONPath makes your intent explicit: this object, this path, this output.

```bash
k get pod nginx -o jsonpath='{.status.podIP}'
k get pods -o jsonpath='{.items[*].status.podIP}'
k get pod nginx -o jsonpath='{.spec.containers[0].image}'
k get pod nginx -o jsonpath='{.spec.nodeName}'
```

For multi-container Pods, JSONPath lets you verify names and images quickly. This is useful after editing YAML because a Pod can be Ready while still using a different image than the prompt requested. It also helps when you need to target the correct container for logs or exec.

```bash
k get pod multi -o jsonpath='{.spec.containers[*].name}'
k get pod multi -o jsonpath='{.spec.containers[*].image}'
```

ConfigMaps and Secrets need careful extraction because their data shape differs. ConfigMap values are plain strings in `.data`. [Secret values are base64-encoded in `.data`](https://kubernetes.io/docs/concepts/configuration/secret/), so you usually decode them when checking the actual value. Do not decode values if the prompt specifically asks for the encoded value.

```bash
k get cm app-config -o jsonpath='{.data.MODE}'
k get secret app-secret -o jsonpath='{.data.password}' | base64 -d
```

Worked example: a prompt says, "Write the node name where Pod `web` is scheduled to `/tmp/web-node.txt`." This is not a logging task and not a describe-copy task. It is a precise extraction task, so JSONPath is the fastest reliable tool.

```bash
k get pod web -o jsonpath='{.spec.nodeName}' > /tmp/web-node.txt
cat /tmp/web-node.txt
```

Now apply the same thinking to a harder prompt: "Find the image used by the container named `sidecar` in Pod `multi` and write it to `/tmp/sidecar-image.txt`." The first-container shortcut is not enough because the target is selected by name. Use a JSONPath filter.

```bash
k get pod multi -o jsonpath="{.spec.containers[?(@.name=='sidecar')].image}" > /tmp/sidecar-image.txt
cat /tmp/sidecar-image.txt
```

> **Active learning prompt**: Your Pod has two containers, `app` and `logger`. The prompt asks for the `logger` image. Why is `{.spec.containers[0].image}` dangerous, and what evidence would you collect before writing the answer file?

The index path is dangerous because it assumes container order. YAML edits, generated manifests, and copied examples can place containers in different order than you expect. Verify container names with `{.spec.containers[*].name}`, then extract by filter or inspect the manifest carefully before writing the answer file.

```bash
k get pod multi -o jsonpath='{.spec.containers[*].name}'
k get pod multi -o jsonpath="{.spec.containers[?(@.name=='logger')].image}"
```

---

## Developer Resources You Should Generate Quickly

CKAD developer tasks repeatedly use a small set of resource patterns. You do not need to memorize every Kubernetes object in the API. You need fluent generation and verification for the resources that appear in application delivery: Pods, Deployments, Services, Jobs, CronJobs, ConfigMaps, Secrets, and simple volume-backed multi-container Pods.

A simple Pod is useful for testing, debugging, and one-off workloads. Use direct creation when the Pod is itself the requested object. Use dry-run when the Pod needs edits. Always think about restart policy when the command is meant to finish rather than run as a service.

```bash
k run web --image=nginx
k run sleeper --image=busybox --restart=Never -- sleep 3600
k run web --image=nginx $kdr > web-pod.yaml
```

A Deployment is the normal starting point for replicated application workloads. It owns ReplicaSets, which own Pods, and it supports rollout commands. For a CKAD prompt, a Deployment is often easier than individual Pods because `k rollout status` gives a clean verification point.

```bash
k create deploy api --image=nginx --replicas=3
k rollout status deploy/api --timeout=90s
k scale deploy api --replicas=2
k set image deploy/api nginx=httpd
k rollout status deploy/api --timeout=90s
```

A Service gives stable access to selected Pods. The most common CKAD Service is `ClusterIP`, which exposes the workload inside the cluster. The Service is only as good as its selector, so verify endpoints after creation. A Service without endpoints is not a successful application path.

```bash
k expose deploy api --port=80 --target-port=80
k get svc api
k get endpointslices -l kubernetes.io/service-name=api
```

A Job runs a task to completion. Use it when the prompt asks for a batch task, one-time command, or completion status. Do not confuse a Job with a Pod that happens to exit. [A Job controller tracks completions and retries according to the Job spec](https://kubernetes.io/docs/concepts/workloads/controllers/job/), which is what the prompt usually intends.

```bash
k create job backup --image=busybox -- sh -c 'echo backup complete'
k wait --for=condition=complete job/backup --timeout=90s
k logs job/backup
```

A CronJob schedules Jobs. CKAD prompts may ask for a specific schedule string, such as every hour. Put the schedule in quotes so the shell does not interpret the asterisks. Verify both the CronJob definition and, if needed, create a manual Job from it for behavior testing.

```bash
k create cronjob hourly --image=busybox --schedule="0 * * * *" -- sh -c 'date'
k get cronjob hourly
k create job hourly-manual --from=cronjob/hourly
k wait --for=condition=complete job/hourly-manual --timeout=90s
```

ConfigMaps and Secrets often appear as supporting resources. Generate them imperatively from literals or files when possible, because the command avoids YAML quoting mistakes. Then reference them from a Pod or Deployment. Remember that Secrets are only base64-encoded by default, not magically secure in every operational sense.

```bash
k create cm app-config --from-literal=MODE=prod --from-literal=LOG_LEVEL=debug
k create secret generic app-secret --from-literal=password=s3cr3t
```

A ConfigMap volume is useful when the prompt wants a file mounted into a container. The ConfigMap stores key-value pairs, and the volume exposes keys as files. This is different from `envFrom`, which exposes keys as environment variables. Choose based on the prompt's required behavior.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-file-demo
spec:
  containers:
  - name: app
    image: busybox
    command: ["sh", "-c", "cat /etc/app/MODE && sleep 3600"]
    volumeMounts:
    - name: app-config
      mountPath: /etc/app
  volumes:
  - name: app-config
    configMap:
      name: app-config
```

When you need to verify mounted ConfigMap data, exec into the container and inspect the mounted path. Do not assume the mount worked because the Pod is Running. A container can run while your application reads the wrong file path. Verification should match the prompt.

```bash
k exec config-file-demo -- cat /etc/app/MODE
```

---

## Worked Example: Build, Expose, Test, and Inspect

This worked example demonstrates the full workflow before you attempt a similar task yourself. The scenario is intentionally ordinary because ordinary tasks are where discipline pays off. You will create a namespace, deploy an app, expose it, test it from inside the cluster, inspect the live image, and clean up.

Scenario: "In namespace `workflow-demo`, create a Deployment named `web` with image `nginx`, two replicas, expose it as a ClusterIP Service on port 80, verify in-cluster HTTP access, then write the first container image to `/tmp/web-image.txt`."

Start by handling namespace state. This makes the rest of the commands shorter and reduces the chance that objects land in `default`.

```bash
k create ns workflow-demo
k config set-context --current --namespace=workflow-demo
k config view --minify | grep namespace
```

Create the Deployment and wait for rollout. The wait command proves the controller reached the desired state, while `get pods` shows the backing Pods and their status.

```bash
k create deploy web --image=nginx --replicas=2
k rollout status deploy/web --timeout=90s
k get pods -l app=web -o wide
```

Expose the Deployment and verify Service backends. This is the point where many learners stop too early. A Service object by itself does not prove traffic will reach Pods. EndpointSlices show whether the Service has selected ready backends.

```bash
k expose deploy web --port=80 --target-port=80
k get svc web
k get endpointslices -l kubernetes.io/service-name=web
```

Test from inside the cluster using a temporary Pod. This proves DNS, Service routing, and HTTP response from the perspective that matters for most Kubernetes workloads.

```bash
k run test --image=busybox --rm -it --restart=Never -- wget -qO- http://web
```

Extract the requested image using JSONPath. The prompt asks for a value in a file, so do not copy from `describe`. Let the API output the exact field.

```bash
k get deploy web -o jsonpath='{.spec.template.spec.containers[0].image}' > /tmp/web-image.txt
cat /tmp/web-image.txt
```

Clean up namespace state after the example. In an exam, you would not delete resources that the task asks you to leave for grading, but in practice labs you should clean up so later exercises start from a known state.

```bash
k config set-context --current --namespace=default
k delete ns workflow-demo
```

The important part is not the specific `nginx` Deployment. The important part is the sequence. Namespace first, create with the simplest reliable command, wait for controller convergence, verify Service endpoints, test from inside the cluster, extract exact fields, and clean up only when the task or lab permits it.

---

## Senior-Level Troubleshooting Patterns

Senior troubleshooting is less about knowing more commands and more about asking sharper questions in the right order. When a workload fails, separate object existence from controller progress, controller progress from Pod health, Pod health from application behavior, and application behavior from network exposure. Each layer has a different command.

If a Deployment does not produce ready Pods, inspect the rollout and Pods before editing YAML. A Deployment may be waiting on image pulls, failing probes, insufficient resources, or selector issues. `rollout status` gives the symptom, but `describe` and events usually give the mechanism.

```bash
k rollout status deploy/api --timeout=30s
k get rs,pod -l app=api
k describe deploy api
k describe pod -l app=api
```

If a Pod is Pending, logs will not help because the container has not started. Use `describe pod` and events to inspect scheduling, volume, or image-pull setup. If a Pod is Running but not Ready, probes or application readiness are likely. If a Pod is CrashLoopBackOff, logs and previous logs become useful.

```bash
k get pod failing -o wide
k describe pod failing
k logs failing --previous
```

If a Service does not route traffic, inspect selectors and endpoints before application internals. A common failure is a Deployment labeled `app: api` while the Service selector expects `run: api`. Both objects are valid. They simply do not connect. Kubernetes will not guess your intent.

```bash
k get svc api -o yaml
k get pods --show-labels
k get endpointslices -l kubernetes.io/service-name=api
```

If an environment variable is missing, verify the source object and the Pod spec. A ConfigMap can exist with the wrong key. A Pod can reference the wrong ConfigMap name. A Deployment can be updated while old Pods are still running. The live Pod template and the actual Pod environment both matter.

```bash
k get cm app-config -o yaml
k get deploy api -o yaml
k exec deploy/api -- printenv | grep MODE || true
```

If a mounted file is missing, check both sides of the mount. The Pod spec must define a volume, the container must mount that volume, and the source ConfigMap or Secret must contain the expected key. A mistake at any layer produces a different symptom, so inspect each layer deliberately.

```bash
k describe pod config-file-demo
k get cm app-config -o yaml
k exec config-file-demo -- ls -la /etc/app
```

If a Job does not complete, check Pods owned by the Job. The Job object tells you completion counts and retry state, but the Pod logs tell you why the command failed. Remember that Job Pods often finish quickly, so use labels and logs from the Job rather than assuming a long-running process.

```bash
k get job backup
k get pods -l job-name=backup
k logs job/backup
k describe job backup
```

If a CronJob is not creating Jobs, check schedule, suspend state, and recent events. For behavior testing, create a manual Job from the CronJob. This avoids waiting for the next scheduled time and proves whether the template command itself works.

```bash
k get cronjob hourly -o yaml
k create job hourly-test --from=cronjob/hourly
k wait --for=condition=complete job/hourly-test --timeout=90s
k logs job/hourly-test
```

The debugging principle is consistent: locate the layer that owns the behavior, then use the command that exposes that layer. Do not use logs for scheduling. Do not use Service YAML for container crashes. Do not use JSONPath when a human-readable event stream would explain the failure faster.

---

## Did You Know?

- **[`--dry-run=client -o yaml` generates a manifest without creating the object](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_run/)**: This lets you combine fast imperative skeletons with careful YAML edits, which is usually faster and safer than writing nested Kubernetes manifests from a blank file.

- **`--restart=Never` changes the Pod restart policy for one-off tests**: That matters for temporary command Pods because a successful command should exit cleanly instead of being restarted in a way that confuses your verification.

- **A Service can exist while routing to no Pods**: The Service selector must match labels on ready Pods, so EndpointSlices or endpoints are the evidence that traffic has somewhere to go.

- **JSONPath is a precision tool, not just a formatting option**: It is strongest when the task asks for one exact field, especially when writing answer files or selecting a named container from a multi-container Pod.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Workflow |
|---------|--------------|-----------------|
| Forgetting to set or pass the namespace at the start of a task | Objects are created correctly but in the wrong namespace, which often looks like a mysterious grader failure | Start each task with `k config set-context --current --namespace=NAME` or use `-n NAME` consistently |
| Using direct imperative commands for nested Pod requirements | Multi-container Pods, volumes, probes, and env references become awkward or impossible to express accurately | Generate a base manifest with dry-run, edit the nested fields, validate, then apply |
| Forgetting `--restart=Never` on one-off test Pods | A command that should run once can restart or leave confusing Pod state behind | Use `k run test --image=... --rm -it --restart=Never -- COMMAND` for temporary checks |
| Verifying only that a Service object exists | A Service without matching endpoints does not prove traffic reaches any backend Pods | Check selectors, Pod labels, and EndpointSlices after creating or debugging a Service |
| Copying values manually from `describe` when an exact file answer is required | Manual copying is slow and can capture the wrong line or extra formatting | Use JSONPath redirection such as `k get pod web -o jsonpath='{.spec.nodeName}' > /tmp/answer.txt` |
| Looking at logs for Pods that have not started | Pending Pods have no useful container logs, so the real issue is scheduling, volumes, or image pulling | Use `k describe pod` and sorted events before logs when the Pod is not Running |
| Editing YAML at the wrong indentation level | Kubernetes rejects the manifest or accepts an object that behaves differently than intended | Use `k explain FIELD.PATH`, copy existing blocks carefully, and run `k apply --dry-run=server -f file.yaml` |
| Leaving temporary debug resources scattered across the namespace | Later `get pods` output becomes noisy, and you may confuse test Pods with workload Pods | Prefer `--rm` for interactive tests and delete named debug Pods with `--ignore-not-found` after interrupted sessions |

---

## Quiz

1. **Your exam task says to create a Deployment named `checkout` in namespace `shop`, expose it internally on port 80, and verify that a Pod in the same namespace can reach it. You create the Deployment and Service, but your test Pod reports it cannot resolve `checkout`. What do you check first, and what commands would you run?**

   <details>
   <summary>Answer</summary>

   Check namespace placement first because DNS names are namespace-scoped by default. Run `k get deploy,svc,pod -n shop` to confirm the objects exist where the prompt expects them, then run the temporary test Pod in the same namespace with `k run test --image=busybox --rm -it --restart=Never -n shop -- nslookup checkout`. If the Service is missing from `shop`, search across namespaces with `k get svc -A | grep checkout || true`, recreate it in `shop`, and delete only the misplaced object if you are sure it came from your mistake. This tests the module outcome of evaluating namespace correctness before deeper debugging.

   </details>

2. **You generated a Pod manifest for `api` from `k run api --image=nginx $kdr`, then edited it to add a `busybox` sidecar. The Pod is Running, but `k logs api` returns an error asking you to choose a container. How do you inspect the sidecar logs and prove both containers are present?**

   <details>
   <summary>Answer</summary>

   Multi-container Pods require container selection for logs when Kubernetes cannot infer which container you mean. First prove the container names with `k get pod api -o jsonpath='{.spec.containers[*].name}'`, then inspect the sidecar with `k logs api -c sidecar --tail=20`. If the sidecar is crashing, use `k logs api -c sidecar --previous` after checking `k describe pod api`. The key decision is to target the named container rather than treating a multi-container Pod like a single-container Pod.

   </details>

3. **A task asks you to create a Job named `report` that prints `daily report complete` and then write evidence that it completed. You accidentally run a plain Pod instead because you remember the image and command but not the controller type. What is wrong with that solution, and how do you repair it?**

   <details>
   <summary>Answer</summary>

   A Pod that exits is not the same as a Job. The prompt asks for a Job controller, which tracks completion and retries. Repair by creating the actual Job: `k create job report --image=busybox -- sh -c 'echo daily report complete'`, then verify with `k wait --for=condition=complete job/report --timeout=90s` and `k logs job/report`. If the mistaken Pod is unrelated to grading, remove it with `k delete pod report --ignore-not-found` or delete the specific mistaken Pod name. This applies the workflow decision between one-off Pods and controller-managed batch work.

   </details>

4. **Your Service `backend` exists and DNS resolves from a temporary Pod, but HTTP requests hang. The Deployment Pods are Running. What evidence would you collect before editing the container image or restarting Pods?**

   <details>
   <summary>Answer</summary>

   Collect Service selector and endpoint evidence first. Run `k describe svc backend`, `k get pods --show-labels`, and `k get endpointslices -l kubernetes.io/service-name=backend -o wide`. If EndpointSlices are empty, the Service selector does not match ready Pods, so editing the image would not address the routing problem. If endpoints exist, then inspect target ports, readiness, and application logs with `k describe pod -l app=backend` and `k logs -l app=backend --tail=20`. The important reasoning step is separating Service routing from application behavior.

   </details>

5. **A prompt asks you to write the image used by the container named `logger` in Pod `webapp` to `/tmp/logger-image.txt`. The Pod has two containers, and `logger` is not guaranteed to be first. What command should you use, and why is an indexed JSONPath risky here?**

   <details>
   <summary>Answer</summary>

   Use a name-based JSONPath filter: `k get pod webapp -o jsonpath="{.spec.containers[?(@.name=='logger')].image}" > /tmp/logger-image.txt`. An indexed expression such as `{.spec.containers[0].image}` is risky because it assumes the container order matches your expectation. Multi-container manifests are often edited by copying blocks, and order is not the same as identity. Verify names first with `k get pod webapp -o jsonpath='{.spec.containers[*].name}'` if you are unsure.

   </details>

6. **You create a ConfigMap `app-config` with `MODE=prod`, then create a Pod that should print the variable and sleep. The Pod starts, but `k exec env-demo -- printenv | grep MODE` shows nothing. What should you inspect, and what YAML placement error is most likely?**

   <details>
   <summary>Answer</summary>

   Inspect both the ConfigMap and the Pod spec: `k get cm app-config -o yaml` and `k get pod env-demo -o yaml`. The likely YAML error is placing `envFrom` at the wrong level, such as under `spec` instead of under the specific container. `envFrom` belongs under `spec.containers[]` because environment variables are injected into a container process. Use `k explain pod.spec.containers.envFrom` to confirm the path, fix the manifest, apply it, and recreate the Pod if needed because Pod environment variables are set when containers start.

   </details>

7. **You need to add a readiness probe to a Deployment. You know the image and replica count, so you start with `k create deploy`. Should you keep searching for an imperative flag for the probe, or switch workflows? Describe the fastest reliable path.**

   <details>
   <summary>Answer</summary>

   Switch to generated YAML and edit the manifest. Run `k create deploy web --image=nginx --replicas=2 --dry-run=client -o yaml > web.yaml`, add `readinessProbe` under the container in `spec.template.spec.containers`, validate with `k apply --dry-run=server -f web.yaml`, then apply and verify with `k rollout status deploy/web --timeout=90s` and `k describe pod -l app=web`. This is faster and safer than hunting for a flag because probes are nested container fields and YAML placement is the natural workflow.

   </details>

8. **During a timed practice, a Pod is stuck in Pending and a teammate suggests checking `k logs` immediately. What should you do instead, and why?**

   <details>
   <summary>Answer</summary>

   Use `k describe pod POD_NAME` and `k get events --sort-by=.metadata.creationTimestamp` before logs. Pending means the container has not started, so there may be no container logs to read. The likely causes are scheduling constraints, volume issues, image pull setup, or admission problems, and those appear in Pod conditions and events. Logs become useful after the container starts or after it crashes; before that, the kubelet and scheduler events are the right layer to inspect.

   </details>

---

## Hands-On Exercise

**Task**: Practice a complete CKAD developer workflow by creating, exposing, testing, inspecting, and debugging resources in a temporary namespace. The exercise is designed as guided practice first and independent practice second. Do not skip verification commands; they are the part that turns command typing into operational skill.

**Part 1: Prepare the namespace and confirm your workflow**

Before creating workloads, isolate the exercise in its own namespace. This makes cleanup safe and makes namespace mistakes obvious. Use the alias `k` only after confirming it exists, and fall back to `kubectl` if your shell does not have the alias configured.

```bash
alias k='kubectl'
export kdr='--dry-run=client -o yaml'

k create ns ckad-workflow
k config set-context --current --namespace=ckad-workflow
k config view --minify | grep namespace
```

Success criteria for Part 1:

- [ ] `k` expands to `kubectl` or you consciously use `kubectl` instead.
- [ ] `echo "$kdr"` prints `--dry-run=client -o yaml`.
- [ ] The current namespace is `ckad-workflow`.
- [ ] `k get pods` runs without a namespace error.

**Part 2: Generate and apply a Deployment manifest**

Generate a Deployment manifest instead of writing it from scratch. This reinforces the pattern that lets Kubernetes create selector and template label structure for you. After generation, inspect the file before applying it.

```bash
k create deploy api --image=nginx --replicas=2 $kdr > api-deploy.yaml
sed -n '1,120p' api-deploy.yaml
k apply --dry-run=server -f api-deploy.yaml
k apply -f api-deploy.yaml
k rollout status deploy/api --timeout=90s
k get pods -l app=api -o wide
```

Success criteria for Part 2:

- [ ] `api-deploy.yaml` contains `kind: Deployment`.
- [ ] The Deployment has two desired replicas.
- [ ] `k rollout status deploy/api` completes successfully.
- [ ] `k get pods -l app=api` shows two Pods or shows rollout progress that you can explain.

**Part 3: Expose the Deployment and test from inside the cluster**

Create a ClusterIP Service from the Deployment, then verify routing from a temporary Pod. Do not treat Service creation as enough. Check EndpointSlices so you know the Service has backends.

```bash
k expose deploy api --port=80 --target-port=80
k get svc api
k get endpointslices -l kubernetes.io/service-name=api
k run test --image=busybox --rm -it --restart=Never -- wget -qO- http://api
```

Success criteria for Part 3:

- [ ] Service `api` exists in namespace `ckad-workflow`.
- [ ] EndpointSlices show backend addresses for the Service.
- [ ] The temporary BusyBox test can retrieve an HTTP response from `http://api`.
- [ ] No completed `test` Pod remains after the command exits, unless the command was interrupted.

**Part 4: Create a multi-container Pod from generated YAML**

Generate a base Pod, then edit it into a multi-container Pod. The goal is to practice the moment where imperative creation stops being enough and manifest editing becomes the right workflow.

```bash
k run webapp --image=nginx $kdr > webapp-pod.yaml
```

Replace the generated file with this final shape if you are practicing non-interactively, or edit your generated file manually to match it.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: webapp
  labels:
    run: webapp
spec:
  volumes:
  - name: logs
    emptyDir: {}
  containers:
  - name: webapp
    image: nginx
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx
  - name: logger
    image: busybox
    command: ["sh", "-c", "tail -f /var/log/nginx/access.log"]
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx
```

Validate, apply, and verify both containers. If readiness takes longer than expected, inspect the Pod instead of repeatedly applying the same file.

```bash
k apply --dry-run=server -f webapp-pod.yaml
k apply -f webapp-pod.yaml
k wait --for=condition=Ready pod/webapp --timeout=90s
k get pod webapp -o jsonpath='{.spec.containers[*].name}'
k logs webapp -c logger --tail=5
```

Success criteria for Part 4:

- [ ] `webapp` has exactly the containers `webapp` and `logger`.
- [ ] Both containers mount the `logs` volume at `/var/log/nginx`.
- [ ] `k wait --for=condition=Ready pod/webapp` succeeds or you can explain the failure from `k describe pod webapp`.
- [ ] You can retrieve logs from the `logger` container using `-c logger`.

**Part 5: Extract exact fields with JSONPath**

Use JSONPath for answer-file style tasks. This part trains precision. Do not copy values manually from `describe`.

```bash
k get pod webapp -o jsonpath="{.spec.containers[?(@.name=='logger')].image}" > /tmp/logger-image.txt
k get pod webapp -o jsonpath='{.spec.nodeName}' > /tmp/webapp-node.txt
cat /tmp/logger-image.txt
cat /tmp/webapp-node.txt
```

Success criteria for Part 5:

- [ ] `/tmp/logger-image.txt` contains `busybox`.
- [ ] `/tmp/webapp-node.txt` contains the node name where `webapp` is scheduled.
- [ ] You used a name-based JSONPath filter for the `logger` image rather than assuming container order.
- [ ] You can explain why JSONPath is safer than manual copying for exact answer files.

**Part 6: Add ConfigMap data and verify it inside a Pod**

Create a ConfigMap and a Pod that consumes it as environment variables. This part reinforces field placement under the container spec.

```bash
k create cm app-config --from-literal=MODE=prod --from-literal=LOG_LEVEL=debug
```

Create `env-demo.yaml` with the following content.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: env-demo
spec:
  containers:
  - name: app
    image: busybox
    command: ["sh", "-c", "env && sleep 3600"]
    envFrom:
    - configMapRef:
        name: app-config
```

Apply and verify from inside the running container.

```bash
k apply --dry-run=server -f env-demo.yaml
k apply -f env-demo.yaml
k wait --for=condition=Ready pod/env-demo --timeout=90s
k exec env-demo -- printenv | grep MODE
k exec env-demo -- printenv | grep LOG_LEVEL
```

Success criteria for Part 6:

- [ ] ConfigMap `app-config` contains keys `MODE` and `LOG_LEVEL`.
- [ ] Pod `env-demo` reaches Ready.
- [ ] `MODE=prod` appears in the container environment.
- [ ] `LOG_LEVEL=debug` appears in the container environment.

**Part 7: Create and verify a Job**

Create a Job with a command after the `--` boundary. Wait for completion and inspect logs from the Job. This is the clean batch workflow CKAD expects when a prompt asks for a Job.

```bash
k create job report --image=busybox -- sh -c 'echo daily report complete'
k wait --for=condition=complete job/report --timeout=90s
k logs job/report
k get job report
```

Success criteria for Part 7:

- [ ] Job `report` exists and reaches `Complete`.
- [ ] `k logs job/report` prints `daily report complete`.
- [ ] You can explain why a Job is different from a plain Pod running the same command.
- [ ] You know which command to use if the Job fails and you need to inspect the created Pod.

**Part 8: Clean up deliberately**

In the exam, do not delete resources that must remain for grading. In this practice exercise, cleanup is part of restoring a known state. Reset the namespace context before deleting the namespace so later commands do not point at a disappearing namespace.

```bash
k config set-context --current --namespace=default
k delete ns ckad-workflow
k get ns ckad-workflow
```

Success criteria for Part 8:

- [ ] Your current namespace is reset to `default`.
- [ ] Namespace `ckad-workflow` is deleted or in terminating state.
- [ ] You did not delete unrelated namespaces or resources.
- [ ] You can repeat the exercise from a clean state.

---

## Practice Drills

### Drill 1: Alias Verification (Target: 2 minutes)

This drill is about confidence in your shell setup. Run each command and explain what it proves. If any alias is missing, use the full `kubectl` command and keep moving.

```bash
type k
echo "$kdr"
k version --client
k get ns
```

Success criteria:

- [ ] You know whether `k` is configured.
- [ ] You know whether `kdr` is configured.
- [ ] You can continue with full flags if either shortcut is missing.

### Drill 2: YAML Generation Speed (Target: 6 minutes)

Generate YAML for common developer resources without applying them. Inspect each file briefly so you connect command flags to manifest structure.

```bash
k run nginx --image=nginx $kdr > /tmp/pod.yaml
k create deploy web --image=nginx --replicas=2 $kdr > /tmp/deploy.yaml
k create svc clusterip web --tcp=80:80 $kdr > /tmp/svc.yaml
k create job backup --image=busybox $kdr -- echo done > /tmp/job.yaml
k create cronjob hourly --image=busybox --schedule="0 * * * *" $kdr -- date > /tmp/cronjob.yaml
k create cm app-config --from-literal=key=value $kdr > /tmp/cm.yaml
k create secret generic app-secret --from-literal=password=secret $kdr > /tmp/secret.yaml
```

Success criteria:

- [ ] Every generated file contains the expected `kind`.
- [ ] The Job and CronJob include the intended command.
- [ ] You can identify which generated manifests are safe to apply immediately and which would need edits for a richer prompt.

### Drill 3: Namespace Switching (Target: 3 minutes)

Practice moving between namespaces without losing track of context. This is not glamorous, but it prevents some of the most expensive mistakes.

```bash
k create ns alpha
k create ns beta
k config set-context --current --namespace=alpha
k run marker --image=nginx
k get pods
k get pods -n beta
k config set-context --current --namespace=beta
k get pods
k get pods -n alpha
k config set-context --current --namespace=default
k delete ns alpha beta
```

Success criteria:

- [ ] You can predict where `marker` appears before running each `get` command.
- [ ] You understand the difference between current namespace and explicit `-n`.
- [ ] You reset context before cleanup finishes.

### Drill 4: Multi-Container Speed (Target: 5 minutes)

Create a multi-container Pod using generation plus editing. The point is not to memorize the final YAML. The point is to practice creating a valid starting point, adding a sidecar at the right indentation, and verifying container-specific behavior.

```bash
k create ns multi-drill
k config set-context --current --namespace=multi-drill
k run multi --image=nginx $kdr > /tmp/multi.yaml
```

Edit `/tmp/multi.yaml` so it contains a second container.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi
  labels:
    run: multi
spec:
  containers:
  - name: main
    image: nginx
  - name: sidecar
    image: busybox
    command: ["sleep", "3600"]
```

Apply and verify.

```bash
k apply --dry-run=server -f /tmp/multi.yaml
k apply -f /tmp/multi.yaml
k wait --for=condition=Ready pod/multi --timeout=90s
k get pod multi -o jsonpath='{.spec.containers[*].name}'
k exec multi -c sidecar -- ps
k config set-context --current --namespace=default
k delete ns multi-drill
```

Success criteria:

- [ ] Both containers are listed by JSONPath.
- [ ] `k exec` targets the sidecar container explicitly.
- [ ] You can explain why the sidecar command must keep running for the container to stay Ready.

### Drill 5: Service Debugging (Target: 7 minutes)

Create a selector mismatch on purpose, then debug it. This drill teaches why Service existence is not enough.

```bash
k create ns svc-debug
k config set-context --current --namespace=svc-debug
k create deploy api --image=nginx
k rollout status deploy/api --timeout=90s
k create svc clusterip api --tcp=80:80
k patch svc api -p '{"spec":{"selector":{"app":"wrong"}}}'
k get svc api
k get endpointslices -l kubernetes.io/service-name=api
```

Now repair the selector and verify traffic.

```bash
k patch svc api -p '{"spec":{"selector":{"app":"api"}}}'
k get endpointslices -l kubernetes.io/service-name=api
k run test --image=busybox --rm -it --restart=Never -- wget -qO- http://api
k config set-context --current --namespace=default
k delete ns svc-debug
```

Success criteria:

- [ ] You observe empty or incorrect endpoints while the selector is wrong.
- [ ] You repair the Service without recreating the Deployment.
- [ ] You verify HTTP access from inside the namespace.

### Drill 6: JSONPath Extraction (Target: 4 minutes)

Create a Pod and extract multiple fields. This drill should feel mechanical by the end, because exact field extraction appears in many practical tasks.

```bash
k create ns jsonpath-drill
k config set-context --current --namespace=jsonpath-drill
k run nginx --image=nginx
k wait --for=condition=Ready pod/nginx --timeout=90s

k get pod nginx -o jsonpath='{.status.podIP}'
echo
k get pod nginx -o jsonpath='{.spec.containers[0].image}'
echo
k get pod nginx -o jsonpath='{.spec.nodeName}'
echo
k get pod nginx -o jsonpath='{.status.phase}'
echo

k config set-context --current --namespace=default
k delete ns jsonpath-drill
```

Success criteria:

- [ ] You can extract Pod IP, image, node name, and phase without `describe`.
- [ ] You add `echo` or formatting when needed so outputs do not run together.
- [ ] You understand when an index-based path is acceptable and when a name-based filter is safer.

### Drill 7: Complete Developer Workflow (Target: 10 minutes)

Simulate a compact CKAD task from start to finish. Create a namespace, build a Deployment, expose it, mount ConfigMap data into a separate Pod, extract an answer file, and clean up only after verification.

```bash
k create ns full-drill
k config set-context --current --namespace=full-drill

k create deploy site --image=nginx --replicas=2
k rollout status deploy/site --timeout=90s
k expose deploy site --port=80 --target-port=80
k get endpointslices -l kubernetes.io/service-name=site

k create cm site-config --from-literal=SITE_MODE=practice
```

Create `site-env.yaml`.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: site-env
spec:
  containers:
  - name: checker
    image: busybox
    command: ["sh", "-c", "env && sleep 3600"]
    envFrom:
    - configMapRef:
        name: site-config
```

Apply, verify, and extract.

```bash
k apply --dry-run=server -f site-env.yaml
k apply -f site-env.yaml
k wait --for=condition=Ready pod/site-env --timeout=90s
k exec site-env -- printenv | grep SITE_MODE
k run test --image=busybox --rm -it --restart=Never -- wget -qO- http://site
k get deploy site -o jsonpath='{.spec.template.spec.containers[0].image}' > /tmp/site-image.txt
cat /tmp/site-image.txt

k config set-context --current --namespace=default
k delete ns full-drill
```

Success criteria:

- [ ] The Deployment reaches a successful rollout.
- [ ] The Service has endpoints and responds to in-cluster HTTP.
- [ ] The ConfigMap value is visible inside `site-env`.
- [ ] `/tmp/site-image.txt` contains the expected image string.
- [ ] You can explain every verification command in the sequence.

---

## Next Module

[Module 1.1: Container Images](/k8s/ckad/part1-design-build/module-1.1-container-images/) - Build, tag, inspect, and choose container images for CKAD application tasks.

## Sources

- [kubernetes.io: kubectl commands](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands/) — The official generated kubectl command reference shows the exact usage syntax for both `create job` and `create cronjob`, including the `--` boundary and CronJob schedule flag.
- [kubernetes.io: namespaces](https://kubernetes.io/docs/tasks/administer-cluster/namespaces/) — The namespaces task page directly covers namespace scoping, `--namespace`, `kubectl config set-context --current --namespace=...`, and the `default` namespace behavior.
- [kubernetes.io: kubectl run](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_run/) — The `kubectl run` reference explicitly documents client dry-run as printing the corresponding object without creating it.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment documentation explicitly states that `.spec.selector` must match `.spec.template.metadata.labels`.
- [kubernetes.io: kubectl expose](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_expose/) — The autogenerated `kubectl expose` reference says it uses the exposed resource's selector as the selector for the new Service.
- [kubernetes.io: kubectl explain](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_explain/) — The official `kubectl explain` reference states that field information is retrieved from the server in OpenAPI format.
- [kubernetes.io: configmap](https://kubernetes.io/docs/concepts/configuration/configmap/) — The ConfigMap documentation shows Pod-level volumes, per-container `volumeMounts`, and `envFrom.configMapRef` nested under the container spec.
- [kubernetes.io: kubectl apply](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/) — The `kubectl apply` reference explicitly defines `--dry-run=server` as sending a server-side request without persisting the resource and documents server-side validation behavior.
- [kubernetes.io: debug service](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/) — The official service-debugging guide walks through checking EndpointSlices, selector-to-label matching, and targetPort alignment when a Service is not routing traffic.
- [kubernetes.io: kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/) — The autogenerated `kubectl logs` reference defines the single-container default, the `-c` container selector, and `--previous` behavior exactly.
- [kubernetes.io: job](https://kubernetes.io/docs/concepts/workloads/controllers/job/) — The Jobs concept page directly explains that a Job creates Pods, retries execution until the required successful terminations occur, and contrasts Jobs with bare Pods.
- [kubernetes.io: secret](https://kubernetes.io/docs/concepts/configuration/secret/) — The Secrets concept page states that `data` values are base64-encoded strings and explicitly cautions that this only obscures the values rather than securing them.
