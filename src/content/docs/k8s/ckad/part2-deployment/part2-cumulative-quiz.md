---
citations_verified: true
title: "Part 2 Cumulative Quiz: Application Deployment"
sidebar:
  order: 5
---

> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 70-90 minutes
>
> **Prerequisites**: Deployments and ReplicaSets, rollout history, Helm basics, Kustomize overlays, Services and selectors
>
> **Exam Context**: CKAD cumulative practice for application deployment workflows on Kubernetes 1.35+
>

---

## Learning Outcomes

- **Debug** a failed Deployment rollout by reading rollout status, ReplicaSet state, Pod events, and revision history instead of guessing from the top-level Deployment condition alone.
- **Design** rollout configuration for common application constraints, including zero-downtime web updates, single-version database workloads, blue/green cutovers, and replica-weighted canary releases.
- **Compare** Helm and Kustomize workflows for packaging, environment customization, rollback behavior, and exam-speed troubleshooting under time pressure.
- **Evaluate** whether a Service selector, Deployment label set, Helm value change, or Kustomize image override is the safest control point for a production deployment change.
- **Implement** a complete deployment recovery workflow that previews changes, applies them, verifies endpoint routing, rolls back safely, and cleans up without leaving misleading cluster state behind.

---

## Why This Module Matters

Hypothetical scenario: A platform team ships a routine web release late in the afternoon. The Deployment reports that a rollout is in progress, the new ReplicaSet exists, and the manifest looks reasonable at first glance. A few minutes later, customers report intermittent failures because the Service is still routing to old and new pods while the new image crashes only after receiving real traffic. The engineer who treats Deployment work as a list of commands loses time changing random fields. The engineer who understands rollout mechanics follows the evidence from Deployment to ReplicaSet to Pod to Service endpoints and fixes the real fault.

Application deployment is where CKAD knowledge becomes operational judgment. It is not enough to know that `k rollout undo` exists or that Helm has a `rollback` command. In a real cluster, the question is whether the rollback returns traffic to a known-good version, whether a Kustomize overlay changed the name of a referenced object, whether a Helm upgrade reused the intended values, and whether a Service selector accidentally included both stable and experimental pods. Those are applied and analytical skills, not recall skills.

This cumulative module turns Part 2 into a connected deployment practice. You will review the mechanisms that make Deployments, Helm, Kustomize, and release strategies fit together, then apply them in scenarios that look like exam tasks and production incidents. The goal is not to memorize one perfect YAML file. The goal is to build a reliable decision path you can use when a workload must be changed quickly without making the cluster harder to reason about.

---

## Deployment Control Plane: What Actually Changes

A Deployment is a declarative controller for ReplicaSets, and a ReplicaSet is the controller that keeps matching Pods at the requested count. When you change the Pod template inside a Deployment, Kubernetes creates a new ReplicaSet because the desired pod identity has changed. The Deployment then moves replicas between the old and new ReplicaSets according to its strategy. This means a rollout problem is rarely solved by staring only at the Deployment object; the evidence is spread across the Deployment, its ReplicaSets, the Pods they own, and the events attached to those Pods.

The simplest mental model is that a Deployment does not "run" your application directly. It writes intent, creates or scales ReplicaSets, and waits for enough Pods to become available. The Pod template is the boundary that matters for rollout history. [Changing `replicas` scales the current ReplicaSet, but changing the image, command, environment, probes, labels, or other fields inside `spec.template` creates a new revision.](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) CKAD questions often hide this distinction by mixing scale operations with image updates, so slow down enough to decide whether you are changing capacity or changing application identity.

```ascii
+--------------------------- Deployment: api ----------------------------+
| desired replicas: 4                                                    |
| strategy: RollingUpdate                                                |
| pod template hash changes when spec.template changes                   |
+------------------------------+-----------------------------------------+
                               |
                               v
+-----------------------+      scale down      +-------------------------+
| ReplicaSet api-old    | <------------------- | ReplicaSet api-new      |
| image: api:1.3        |                      | image: api:1.4          |
| replicas: 2           | -------------------> | replicas: 2             |
+-----------+-----------+      scale up        +------------+------------+
            |                                             |
            v                                             v
+-----------------------+                      +-------------------------+
| Pods serving traffic  |                      | Pods must become Ready  |
| selected by Service   |                      | before rollout succeeds |
+-----------------------+                      +-------------------------+
```

A rolling update is safe only when the application can tolerate two versions running at the same time. For stateless web workloads, that is usually the default assumption. For applications with strict schema coupling, leader election limits, or single-writer constraints, the default may be wrong. Kubernetes will happily run old and new Pods together if you ask for a rolling update; it does not know whether your application protocol supports that mix. Your job is to choose the strategy that matches the workload's compatibility boundary.

[`maxSurge` and `maxUnavailable` describe the temporary capacity envelope during a rolling update.](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) `maxSurge: 1` with four replicas allows five Pods briefly, which can preserve capacity while new Pods start. `maxUnavailable: 0` means Kubernetes should avoid dropping below the desired number of available replicas during the update. These fields are not abstract tuning knobs; they encode the business promise you are making while replacing a workload. If there is no spare cluster capacity, aggressive surge settings may still leave Pods pending, so rollout verification must include scheduling and readiness signals.

> **Active Learning Prompt**: Before reading the next paragraph, predict what happens when a four-replica Deployment uses `maxSurge: 1`, `maxUnavailable: 0`, and every new Pod fails its readiness probe. Which objects should show the failure first, and why would the old Pods remain important?

The answer is that the new ReplicaSet can grow only as far as the surge budget and readiness constraints allow. Failed or unready new Pods prevent the Deployment from considering them available, so the controller should avoid scaling down too many old available Pods. The Deployment status may say the rollout is not progressing, but the Pod events and [readiness probe failures](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) explain why. In practice, you verify the rollout with `k rollout status deploy/name`, inspect ReplicaSets with `k get rs`, and then move to `k describe pod` or `k logs` for the failing new Pods.

A useful Deployment workflow always separates intent, rollout, and serving traffic. The manifest expresses intent. The rollout machinery creates or scales ReplicaSets. [The Service chooses which Pods receive traffic based on labels.](https://kubernetes.io/docs/concepts/services-networking/service/index.html) When those layers are confused, teams patch the wrong thing. For example, scaling a Deployment will not fix a Service selector that matches zero Pods, and changing a Service selector will not repair a crashing container image. The fastest path is to ask which layer is broken before choosing the command.

The order of inspection also helps you distinguish a stalled replacement from a completed replacement with broken routing. Compare the desired and available replica counts, then identify which ReplicaSet owns each Pod. A Pod that cannot be scheduled points toward capacity or placement; a running Pod that never becomes ready points toward its probe or application startup. Only after those observations should you inspect whether the Service has ready endpoints. Each step narrows the failure boundary before you change a field.

```bash
kubectl get deploy api
kubectl rollout status deploy/api
kubectl get rs -l app=api
kubectl get pods -l app=api -o wide
kubectl describe pod -l app=api
kubectl get svc api -o yaml
kubectl get endpointslice -l kubernetes.io/service-name=api
```

The commands above form an evidence ladder. Start from the controller that owns intent, then walk down toward the concrete Pods and across toward the Service endpoints. In CKAD practice, this prevents a common failure mode: answering a rollback question with a rollback command before proving which revision is broken. In production, it prevents a worse failure mode: rolling back a Deployment when the real outage is a selector mismatch or missing readiness gate.

### Worked Example: Debugging a Stalled Rollout

Suppose a team updates `api` from `registry.example.com/api:1.3` to `registry.example.com/api:1.4`. The Deployment has four replicas, `maxSurge: 1`, and `maxUnavailable: 0`. The rollout does not finish. A beginner might immediately run `k rollout undo deploy/api`, which may be the right recovery action, but it skips diagnosis. A stronger operator spends a short, fixed amount of time proving what changed and where the rollout is stuck.

First, check the Deployment and rollout state. This establishes whether the controller is still progressing, timed out, or already complete from Kubernetes' perspective. A Deployment can be "available" enough to serve some traffic while still failing to complete a new rollout, so look at both availability and revision movement.

```bash
kubectl rollout status deploy/api --timeout=30s
kubectl rollout history deploy/api
kubectl get deploy api -o wide
```

Next, inspect the ReplicaSets. The new ReplicaSet should have the current image and some desired Pods. If the new ReplicaSet has Pods that exist but are not ready, the problem is likely inside the Pod lifecycle. If the new ReplicaSet has no Pods, look for quota, scheduling, or selector problems. If the old ReplicaSet was scaled down too far, examine strategy settings and readiness timing.

```bash
kubectl get rs -l app=api
kubectl describe rs -l app=api
```

Then, inspect the new Pods. The fastest signal often appears in `READY`, `STATUS`, `RESTARTS`, events, and container logs. A readiness probe failure is different from an image pull failure, and both are different from a crash after start. Each points to a different fix, so do not collapse every failed rollout into the same rollback reflex.

```bash
kubectl get pods -l app=api --sort-by=.metadata.creationTimestamp
kubectl describe pod -l app=api
kubectl logs -l app=api --tail=80
```

Finally, decide whether to fix forward or roll back. If the issue is a typo in an environment variable and you have the correct value, a fast patch or apply may be safer than a rollback. If the new image itself is bad, rolling back to the previous known-good revision is appropriate. If the Service selector is wrong, neither image change nor rollback will fix traffic until the selector matches the intended Pods.

```bash
kubectl rollout undo deploy/api
kubectl rollout status deploy/api
kubectl get endpointslice -l kubernetes.io/service-name=api
```

The worked example shows the core habit this module expects: choose commands because they answer a question. `rollout status` answers whether the controller completed the rollout. `get rs` answers how replicas are distributed across revisions. `describe pod` and `logs` answer why concrete containers are not becoming healthy. `get endpointslice` answers whether traffic has real backend Pods. When you can state the question, the command becomes easier to remember under exam pressure.

When a rollback is justified, verify both the restored Pod template and the serving path. The undo command can create another rollout, so wait for its status and compare the resulting Pods with the expected image. Then check the Service selector and EndpointSlices again. If a separate configuration object changed outside the Deployment, undoing its Pod template cannot restore that object. This is why the recovery boundary must match the boundary of the original change.

---

## Helm: Release State, Values, and Rollback Boundaries

Helm packages Kubernetes objects into charts and tracks each install or upgrade as a release revision. That release history is separate from Deployment revision history, though the two often interact. A Helm upgrade may create a new Deployment revision if it changes the Pod template, but Helm itself records the chart version, rendered manifest, and values used for the release. This matters because a Helm rollback returns the release to a previous rendered state, while a Deployment rollback changes only the Deployment's ReplicaSet history.

A Helm release is useful because many applications are more than one Deployment. A chart may include Deployments, Services, ConfigMaps, ServiceAccounts, Ingress objects, and policies that must change together. If you manually patch one object that Helm manages, the next Helm upgrade may overwrite that patch because Helm still believes the chart-rendered object is the source of truth. In exam tasks, that means you should use Helm commands when the question describes a Helm release. In production, it means you should avoid creating configuration drift that future upgrades will erase.

The most important Helm values skill is knowing the difference between default chart values, user-supplied values, and currently applied values. [`helm show values` displays chart defaults.](https://helm.sh/docs/helm/helm_show_values/) [`helm get values RELEASE` displays custom values supplied to the installed release, and `--all` includes computed values.](https://helm.sh/docs/helm/helm_get_values/) [`helm upgrade --reuse-values` starts from the release's existing custom values and applies the changes you add.](https://helm.sh/docs/helm/helm_upgrade/) Without that flag, an upgrade can accidentally drop previous customizations if you do not provide them again.

| Task | Strong Command Choice | Why It Fits the Situation |
|---|---|---|
| Inspect chart defaults before install | `helm show values repo/chart` | You need to know configurable keys before setting values. |
| Inspect values used by a release | `helm get values release --all` | You need evidence of the deployed configuration, not chart defaults. |
| Install into a new namespace | `helm install name repo/chart -n ns --create-namespace` | The release and namespace are created in one repeatable command. |
| Upgrade while preserving prior overrides | `helm upgrade name repo/chart --reuse-values --set key=value` | Existing custom values stay in place while one setting changes. |
| Recover a bad chart upgrade | `helm rollback name REVISION` | Helm restores the rendered release state for that revision. |
| Remove a release cleanly | `helm uninstall name -n ns` | Helm deletes the objects it owns for that namespaced release. |

Helm can be deceptively fast during CKAD practice because one command creates many objects. That speed is valuable only if you verify what was rendered and what was applied. [`helm template` previews manifests without installing.](https://helm.sh/docs/helm/helm_template/) `helm upgrade --dry-run` checks the rendered output for an upgrade. After applying, `helm status`, `k get all`, and workload-specific rollout checks confirm whether the chart's objects are healthy. Helm success means Kubernetes accepted the release; it does not guarantee the application is ready to serve traffic.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm show values bitnami/nginx | less
helm install my-nginx bitnami/nginx --set replicaCount=3 -n web --create-namespace
helm status my-nginx -n web
kubectl rollout status deploy -n web
```

> **Active Learning Prompt**: A release was installed with custom resource limits and later upgraded with `helm upgrade app chart --set service.type=LoadBalancer`. Predict what could happen to the resource limits if `--reuse-values` is omitted, then explain which command would prove the current values.

The risk is that the upgrade may render from chart defaults plus the newly supplied setting, not from every previous custom override. The exact behavior depends on how values were supplied and chart defaults, which is why evidence matters. Use `helm get values app --all` to inspect the current computed values and `helm history app` to see release revisions. If you need to preserve previous custom values while changing one field, use `--reuse-values` or provide a complete values file that represents the desired state.

Helm rollback deserves the same caution as Deployment rollback. Rolling back a release may change multiple Kubernetes objects, not only a Deployment image. That is often exactly what you want after a bad chart upgrade, because the Service, ConfigMap, and Deployment may need to return together. It can also surprise teams that manually patched one object outside Helm. The professional habit is to [inspect `helm history`, choose the target revision intentionally, roll back](https://helm.sh/docs/helm/helm_rollback/), and then verify the workloads and Services that matter to users.

Before any Helm upgrade, compare the proposed values with the release that is actually deployed. A single `--set` flag expresses only one requested difference; it is not a complete description of every earlier override. Render the proposed chart when time permits, inspect the Deployment and related ConfigMap, and record which release revision is currently healthy. If the upgrade fails, that revision gives you a concrete target for recovery, while post-upgrade checks tell you whether all affected objects returned together.

```bash
helm history my-app -n production
helm rollback my-app 2 -n production
helm status my-app -n production
kubectl get all -n production -l app.kubernetes.io/instance=my-app
```

---

## Kustomize: Overlays Without Losing Object Identity

Kustomize builds Kubernetes manifests by layering transformations over plain YAML. A base describes common resources, and overlays adjust those resources for a target environment such as development, staging, or production. This is different from Helm's templating model. Kustomize does not require a chart language or template expressions; [it modifies structured Kubernetes objects through fields such as `resources`, `namespace`, `namePrefix`, `labels`, `patches`, and `images`.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)

The professional value of Kustomize is that it makes environment differences explicit while preserving reviewable YAML. A base Deployment can define the container, ports, probes, and labels that every environment shares. A production overlay can set the namespace, replica count, image tag, resource limits, and name prefix. The danger is that transformations can affect object references. If you add a `namePrefix`, object names change. If a Service selector no longer matches the Deployment's Pod labels, traffic breaks even though both objects applied successfully.

```ascii
+----------------------------- kustomize build ------------------------------+
|                                                                            |
|  base/                                                                     |
|  +-- deployment.yaml        common app shape                                |
|  +-- service.yaml           common traffic entry                            |
|  +-- kustomization.yaml     resources list                                  |
|                                                                            |
|                   overlay transforms are applied                            |
|                                                                            |
|  overlays/prod/                                                            |
|  +-- kustomization.yaml     namespace: production                           |
|                             namePrefix: prod-                               |
|                             images: api -> api:1.4                          |
|                             patches: replicas/resources                     |
|                                                                            |
+-----------------------------------+----------------------------------------+
                                    |
                                    v
+--------------------------- rendered Kubernetes YAML ------------------------+
| prod-api Deployment, prod-api Service, production namespace references      |
+----------------------------------------------------------------------------+
```

A reliable Kustomize workflow has two separate steps: preview and apply. [`kubectl kustomize ./path` renders the final YAML so you can inspect names, namespaces, labels, selectors, image tags, and patches before the cluster sees them. `k apply -k ./path` applies the rendered result.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) On the exam, previewing may feel slower, but it is often the fastest way to catch a prefix, namespace, or image override mistake before it costs you several troubleshooting commands.

```bash
kubectl kustomize overlays/prod
kubectl apply -k overlays/prod
kubectl get deploy,svc -n production
```

[The `images` transformer is one of the most exam-relevant Kustomize features. It lets you replace an image tag or full image name without editing the base Deployment.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) This keeps the base stable while allowing each overlay to choose a release artifact. The image name must match the image name in the base, so `name: nginx` matches `nginx:1.21`, while a base that uses `registry.example.com/nginx` may need that full name as the match target. When an override appears to do nothing, inspect the rendered output before assuming Kubernetes ignored the change.

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
namespace: production
namePrefix: prod-
images:
  - name: nginx
    newTag: "1.25"
```

Kustomize patches are powerful, but they should be used for intentional environment differences rather than random edits. A production overlay that changes `replicas` from two to six is clear and defensible. A production overlay that rewrites labels without updating the Service selector is a traffic outage waiting to happen. Before applying an overlay, scan the rendered Deployment labels, Pod template labels, Service selector, namespace, and object names together. Those fields form the routing contract for the workload.

```bash
kubectl kustomize overlays/prod | less
kubectl kustomize overlays/prod | grep -E "name:|namespace:|image:|app:|selector:"
```

> **Active Learning Prompt**: An overlay adds `namePrefix: prod-` and `namespace: production`, but a teammate manually runs `k get svc app-svc -n production` and says the Service is missing. What should you check before recreating anything?

The first check is whether the rendered Service name changed to `prod-app-svc`. The second check is whether the Service exists in the intended namespace. The third check is whether the Service selector still matches the Pod template labels after transformations and patches. Recreating a missing object by hand may create drift and hide the fact that the overlay already produced a differently named object. Rendering the overlay answers the naming question cleanly.

Treat the rendered overlay as the object you are about to submit, not merely as a preview of source files. A reviewer can compare the final Deployment selector with its Pod template labels and the final Service selector in one pass. This also catches a common naming mistake: a command aimed at the unprefixed base object will report it missing even though the prefixed production object exists. Edit the overlay when the rendered contract is wrong, then render it again before applying.

Kustomize and Helm can be combined in real organizations, but CKAD tasks usually test them separately. When comparing them, focus on ownership and change model. Helm owns release history and chart-rendered resources. Kustomize owns a rendered manifest view built from bases and overlays. Helm rollback is release-aware. Kustomize rollback usually means applying a previous Git state or reverting overlay changes. Knowing that boundary helps you choose the right tool when a scenario gives you both packaging and environment customization clues.

| Decision Point | Prefer Helm When | Prefer Kustomize When |
|---|---|---|
| Starting from a vendor package | The application is distributed as a maintained chart. | You already have raw manifests and need small environment changes. |
| Managing release history | You need `helm history` and `helm rollback`. | You rely on Git history and `kubectl apply -k`. |
| Changing environment-specific fields | Values expose the fields cleanly in the chart. | Bases and overlays make the differences clearer. |
| Debugging rendered output | Use `helm template` or `helm get manifest`. | Use `kubectl kustomize` before applying. |
| Avoiding template language | Chart templates are already accepted by the team. | Plain Kubernetes YAML is preferred for review. |
| Exam-speed object edits | The task explicitly mentions a Helm release. | The task explicitly mentions `kustomization.yaml` or overlays. |

---

## Release Strategies: Matching Traffic Risk to Workload Constraints

A release strategy is a traffic and availability decision, not just a Kubernetes field. Rolling updates, recreate deployments, blue/green cutovers, and canary releases all answer the same question: how should users move from one version to another? Kubernetes provides primitives such as Deployments, Services, labels, and replica counts. You assemble those primitives into a release pattern that matches application compatibility, risk tolerance, and operational speed.

[Rolling update is the default Deployment strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) because it fits many stateless services. It gradually replaces old Pods with new Pods while trying to maintain availability according to `maxSurge` and `maxUnavailable`. It is a poor fit when old and new versions cannot run at the same time. It also does not provide a clean instant traffic switch; traffic follows whichever ready Pods match the Service selector. If both old and new Pods match the same selector during the rollout, both may receive traffic.

Recreate strategy terminates old Pods before creating new ones. This creates downtime, but it preserves the single-version guarantee. It is appropriate for workloads that cannot safely run two versions concurrently, such as simple database-like applications in exam scenarios or tightly coupled single-writer services. In production, many stateful systems should use StatefulSets or external migration strategies instead, but CKAD questions often use Recreate to test whether you understand the concurrency trade-off.

Blue/green deployment uses two complete environments or two complete sets of Pods, one active and one idle or warming. A Service selector points traffic to blue, then switches to green when green is verified. The advantage is a fast traffic cutover and a clear rollback by switching the selector back. The risk is selector accuracy. If the Service selector matches both versions or neither version, you either mix traffic unintentionally or send traffic nowhere.

```ascii
Before cutover:

+-----------------------+        selector: app=shop,version=blue        +----------------------+
| Service shop-svc      | --------------------------------------------> | Deployment shop-blue |
| stable DNS and port   |                                               | ready Pods: blue     |
+-----------------------+                                               +----------------------+
            |
            | does not select
            v
+----------------------+
| Deployment shop-green|
| ready Pods: green    |
+----------------------+

After cutover:

+-----------------------+        selector: app=shop,version=green       +----------------------+
| Service shop-svc      | --------------------------------------------> | Deployment shop-green|
| stable DNS and port   |                                               | ready Pods: green    |
+-----------------------+                                               +----------------------+
```

A blue/green switch is often just a Service patch. That simplicity is both the strength and the danger. A precise patch changes the selector to the new version label while preserving the common application label. A careless patch may remove other selector keys and accidentally include unrelated Pods. Always verify endpoints after the switch, because the Service object can look valid while endpoint discovery shows zero ready backends.

Prepare the reverse selector before cutting traffic, and check that the green Pods are ready while the blue Pods remain available. After the patch, inspect the whole selector rather than assuming only one key changed. EndpointSlices then show whether the intended green backends are eligible to receive Service traffic. Keeping both sets temporarily costs extra capacity, but it makes a selector switch back possible without waiting for another image rollout.

```bash
kubectl patch svc shop-svc -p '{"spec":{"selector":{"app":"shop","version":"green"}}}'
kubectl get svc shop-svc -o yaml
kubectl get endpointslice -l kubernetes.io/service-name=shop-svc
kubectl get pods -l app=shop,version=green
```

Canary deployment sends a small portion of traffic to a new version while most traffic continues to reach the stable version. With plain Kubernetes Services, replica weighting is approximate because the Service load-balances across ready endpoints rather than understanding percentages as policy. If stable has nine ready Pods and canary has one ready Pod under the same selector, the canary may receive roughly a small share of traffic, but actual distribution depends on client behavior, connection reuse, and kube-proxy or service mesh behavior. For CKAD, the key skill is setting labels and replica counts so one Service selects both sets of Pods.

```ascii
+------------------------ Service myapp-svc -------------------------+
| selector: app=myapp                                                |
+------------------------------+-------------------------------------+
                               |
                +--------------+--------------+
                |                             |
                v                             v
+------------------------------+   +------------------------------+
| Deployment stable-app         |   | Deployment canary-app        |
| labels: app=myapp,track=stable|   | labels: app=myapp,track=canary|
| replicas: 9                  |   | replicas: 1                  |
+------------------------------+   +------------------------------+
```

A canary should be observable before it is expanded. That means you need a way to identify canary Pods, check their logs, and compare readiness or error signals with stable Pods. If every Pod has only `app=myapp`, the Service can route to both, but you lose easy operational separation. [A better label set includes a shared selector label for traffic and a separate version or track label for diagnosis.](https://kubernetes.io/docs/concepts/workloads/management/) The Service selector uses the shared label, while your debugging commands filter by the track label.

Replica counts give a useful practice model for canary exposure, yet they are not a promise that every tenth request reaches the new version. A client may reuse connections, and ready endpoints may change while the test runs. Keep the traffic selector broad enough for both tracks, use `track: canary` to isolate logs and Pod checks, and state the observation window before increasing replicas. If exact request percentages are required, this simple Service pattern is insufficient.

```bash
kubectl scale deploy stable-app --replicas=9
kubectl scale deploy canary-app --replicas=1
kubectl get pods -l app=myapp -o wide
kubectl logs -l app=myapp,track=canary --tail=80
kubectl get endpointslice -l kubernetes.io/service-name=myapp-svc
```

The release strategy decision can be summarized as a compatibility question followed by a verification question. Can old and new versions run together? If no, prefer Recreate or a more specialized migration plan. If yes, do you need instant switchback? Blue/green may fit. If yes, do you need gradual exposure? Canary may fit. If neither special control is needed, rolling update is usually enough. After choosing, verify that traffic routing matches the strategy, because Kubernetes object success is not the same as user-facing success.

Downtime tolerance and simultaneous-version tolerance are separate constraints. Recreate addresses the latter by terminating old Pods before starting new ones, but it creates an availability gap. RollingUpdate usually protects availability better, provided the application tolerates both versions at once and the cluster can host any surge Pods. Blue/green needs capacity for two complete sets, while a simple canary adds only a smaller second set. Write down these costs before choosing a pattern from its name alone.

| Strategy | Best Fit | Main Control Point | Verification Focus |
|---|---|---|---|
| RollingUpdate | Stateless apps that tolerate mixed versions | Deployment strategy and readiness | Rollout status, ReplicaSets, Pod readiness |
| Recreate | Apps that require only one version at a time | Deployment strategy type | Old Pods terminated before new Pods run |
| Blue/Green | Fast cutover and fast switchback | Service selector | EndpointSlices point only to chosen color |
| Canary | Small exposure before broader rollout | Replica counts and shared selector | Service selects both tracks, logs identify canary |
| Helm rollback | Multi-object chart recovery | Helm release revision | Release history, rendered objects, workload health |
| Kustomize apply | Environment overlay promotion | Rendered manifest from overlay | Names, namespaces, selectors, images |

---

## Exam-Speed Workflow: Diagnose, Change, Verify, Recover

CKAD rewards speed, but reliable speed comes from reducing decisions, not skipping them. For deployment tasks, use a four-step loop: diagnose the current state, change the smallest correct control point, verify the effect, and know the recovery command before you need it. This loop works for Deployments, Helm releases, Kustomize overlays, blue/green switches, and canaries because each involves intent, application, and verification.

The first step is diagnosis. Identify the owner of the desired state. If the object is a raw Deployment, use `k get deploy`, `k rollout history`, and ReplicaSet inspection. If the scenario names a Helm release, inspect the release with Helm before patching Kubernetes objects by hand. If it names a Kustomization, render it before applying. If it describes traffic switching, inspect Service selectors and endpoints. The owner tells you where the durable fix belongs.

The second step is the smallest correct change. For a bad Deployment image, `k set image` or applying a corrected manifest may be enough. For a Helm value change, use `helm upgrade` with explicit values or `--reuse-values`. For a Kustomize image tag, modify the overlay's `images` field and apply with `-k`. For blue/green, patch the Service selector. Small does not mean casual; it means the change targets the layer that owns the problem.

The third step is verification. A command that exits successfully means Kubernetes accepted your request, not that the application works. Use rollout status for Deployments, Helm status for releases, rendered output for Kustomize, and endpoints for Services. When a Service should route to Pods, endpoint discovery is stronger evidence than the Service YAML alone. When a rollout should create a new revision, ReplicaSet state is stronger evidence than a single Deployment line.

The final step is recovery. Know whether recovery means `k rollout undo`, `helm rollback`, reapplying a previous Kustomize overlay, or switching a Service selector back. Each rollback mechanism has a different scope. [A Deployment rollback does not restore a ConfigMap changed by Helm.](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) A Service selector switch does not change the broken Pods; it only moves traffic away. Recovery should match the blast radius of the change you made.

```bash
# Raw Deployment recovery
kubectl rollout history deploy/api
kubectl rollout undo deploy/api --to-revision=2
kubectl rollout status deploy/api

# Helm release recovery
helm history api -n production
helm rollback api 2 -n production
helm status api -n production

# Kustomize recovery through a known overlay state
kubectl kustomize overlays/prod
kubectl apply -k overlays/prod
kubectl rollout status deploy/prod-api -n production

# Blue/green traffic recovery
kubectl patch svc shop-svc -p '{"spec":{"selector":{"app":"shop","version":"blue"}}}'
kubectl get endpointslice -l kubernetes.io/service-name=shop-svc
```

A senior deployment habit is to write down the verification target before running the change. If you patch a Service to green, [the verification target is EndpointSlices that contain green Pods and exclude blue Pods](https://kubernetes.io/docs/concepts/services-networking/service/index.html). If you upgrade a Helm release, the target is release status plus healthy workloads. If you apply a Kustomize overlay, the target is rendered names, namespaces, labels, and healthy rollout. This prevents the common exam mistake of stopping at the first command that returns no error.

Use the same four-step loop when recovery itself introduces another change. Diagnose the failed release, choose the rollback boundary, verify its new state, and retain enough evidence to explain what failed. A Deployment undo should be checked against its ReplicaSets and Pods; a Helm rollback should be checked against every affected resource; a blue/green switchback should be checked against endpoints. Finishing the command sequence without those checks leaves the central question unanswered: which version can users reach now?

---

## Did You Know?

- **Deployment revision history depends on the Pod template**: Scaling a Deployment changes replica count, but editing `spec.template` creates a new ReplicaSet revision that can appear in rollout history.

- **A Service selector is live traffic configuration**: Patching a selector can move production traffic immediately, so endpoint verification should follow every blue/green or canary selector change.

- **Helm and Kubernetes keep different histories**: Helm release history tracks chart-rendered releases, while Deployment rollout history tracks ReplicaSet revisions for one workload.

- **Kustomize previewing is a troubleshooting tool**: `kubectl kustomize` can reveal transformed names, namespaces, labels, and images before any object is sent to the API server.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Rolling back before inspecting ReplicaSets | You may hide a Service selector, probe, or scheduling problem and fail to learn the real cause. | Check rollout status, ReplicaSets, Pods, events, and endpoints before choosing recovery. |
| Using RollingUpdate for incompatible versions | Kubernetes may run old and new Pods together even when the application cannot tolerate mixed versions. | Use Recreate, blue/green, or a migration-specific plan when only one version may run. |
| Forgetting `--reuse-values` during Helm upgrade | Previous custom values can be lost if the upgrade renders from defaults plus one new setting. | Inspect values first and use `--reuse-values` or a complete values file. |
| Manually patching Helm-owned objects | Later Helm upgrades can overwrite manual changes and recreate the original problem. | Change the chart values or templates that own the rendered object. |
| Applying Kustomize without previewing | Name prefixes, namespaces, image overrides, or patches may render differently than expected. | Run `kubectl kustomize` and inspect names, selectors, labels, and images before applying. |
| Patching only part of a Service selector | A partial selector can include too many Pods or exclude every intended backend. | Patch the full intended selector and verify EndpointSlices immediately. |
| Treating canary percentages as exact with plain Services | Kubernetes Services balance across endpoints and do not enforce business-level traffic percentages. | Use replica ratios for exam practice and stronger traffic tools when exact percentages matter. |
| Verifying only object creation | Created objects may still have crashing Pods, empty endpoints, or unready containers. | Verify rollouts, Pod readiness, logs, and endpoint routing after every deployment change. |

---

## Quiz

### Question 1: Stalled Rolling Update Under Capacity Pressure

Your team runs a four-replica Deployment named `webapp` using `nginx:1.20`. They need a zero-downtime update pattern for a web tier and ask you to configure a rolling update with at most one extra Pod and no planned unavailable Pods. Later, the rollout stalls because the new Pods are not becoming ready. What manifest fields should encode the strategy, and what evidence should you inspect before rolling back?

A) Use `Recreate`; inspect only Deployment status, then undo if the new Pods are unready.
B) Use `RollingUpdate` with surge one and unavailable zero; inspect rollout, ReplicaSets, Pods, events, and logs.
C) Use `RollingUpdate` with surge zero and unavailable one; inspect the Service before any Pod evidence.
D) Set replicas to five and keep default strategy; inspect only the new image tag before undoing.

<details>
<summary>Answer</summary>

Use a `RollingUpdate` strategy with `maxSurge: 1` and `maxUnavailable: 0`, then inspect the rollout status, ReplicaSets, Pod readiness, events, and logs before deciding whether rollback is needed.

**B is correct** because it matches the requested capacity envelope and traces the stalled rollout to concrete Pods. A is wrong because Recreate permits downtime. C is wrong because it allows an unavailable Pod, and D is wrong because it changes steady-state capacity without encoding the requested strategy.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: webapp
  template:
    metadata:
      labels:
        app: webapp
    spec:
      containers:
        - name: nginx
          image: nginx:1.20
```

```bash
kubectl rollout status deploy/webapp
kubectl get rs -l app=webapp
kubectl get pods -l app=webapp
kubectl describe pod -l app=webapp
```

The strategy preserves desired availability when possible, but failed readiness can prevent progress. The ReplicaSet and Pod evidence tells you whether the issue is the image, probes, scheduling, or another Pod-level failure.

</details>

---

### Question 2: Choosing the Right Rollback Boundary

A Deployment named `api` was upgraded through a Helm release named `api-prod` in namespace `production`. The new release changed both the image and a ConfigMap value, and the application now fails startup. A teammate suggests `k rollout undo deploy/api -n production`. Evaluate that plan and choose the safer recovery command.

A) Run Deployment undo first, then patch the ConfigMap manually if startup still fails.
B) Delete the new ReplicaSet and wait for Helm to reconstruct the previous ConfigMap.
C) Inspect Helm history and roll back the release revision, then verify both changed objects.
D) Scale the Deployment to zero and back so it reloads the old ConfigMap value.

<details>
<summary>Answer</summary>

A Deployment rollback may only restore the Deployment's ReplicaSet state, while the Helm upgrade also changed a ConfigMap. Because the scenario says the change was made through a Helm release and affected multiple rendered objects, recover through Helm release history.

**C is correct** because Helm history identifies a prior release state covering the Deployment and ConfigMap. A is wrong because Deployment undo does not restore the ConfigMap. B is wrong because it bypasses release history, and D is wrong because it restarts Pods against the current configuration rather than recovering the release.

```bash
helm history api-prod -n production
helm rollback api-prod 2 -n production
helm status api-prod -n production
kubectl rollout status deploy/api -n production
```

The exact revision depends on `helm history`, so do not assume revision `2` without checking. Helm rollback is the safer boundary because it restores the release's rendered state rather than only one Deployment object.

</details>

---

### Question 3: Kustomize Overlay Breaks Traffic

You apply a production Kustomize overlay that sets `namespace: production`, adds `namePrefix: prod-`, and overrides the image tag. The Deployment is running, but `k get svc app-svc -n production` says the Service does not exist. Your team wants to recreate the Service manually. What should you do first, and what fields should you inspect?

A) Render the overlay, then inspect the transformed Service name, namespace, labels, and selector.
B) Recreate `app-svc` manually in production and compare it with the base manifest.
C) Remove `namePrefix` immediately, then retry the unprefixed Service lookup.
D) Roll back the Deployment image because an image override can hide a Service.

<details>
<summary>Answer</summary>

Render the overlay first and inspect the transformed object names, namespace, labels, and Service selector. The prefix may have changed `app-svc` to `prod-app-svc`, and manual recreation would create drift.

**A is correct** because the rendered overlay reveals whether `app-svc` became `prod-app-svc`. B is wrong because manual recreation bypasses the overlay. C is wrong because it changes the intended naming policy without diagnosis, and D is wrong because it targets the image instead of Service identity or routing.

```bash
kubectl kustomize overlays/prod
kubectl get svc -n production
kubectl get deploy -n production
kubectl get endpointslice -n production
```

If the rendered Service is named `prod-app-svc`, use that name. If the Service exists but has no endpoints, inspect whether the selector matches the Pod template labels. The correct fix belongs in the overlay, not in an untracked manual Service.

</details>

---

### Question 4: Blue/Green Cutover With Selector Safety

You have two Deployments, `shop-blue` and `shop-green`. Both use `app: shop`, while blue has `version: blue` and green has `version: green`. The Service `shop-svc` currently selects blue with `app: shop, version: blue`. Green has passed smoke tests. Patch the Service to cut traffic to green and state how you would verify that blue is no longer receiving traffic through that Service.

A) Replace the selector with only `version: green`, then verify the Service name exists.
B) Keep `version: blue` and scale blue down, then inspect Deployment status.
C) Add `version: green` to blue Pods, then verify that both colors stay ready.
D) Set `app: shop, version: green` together, then inspect ready Service endpoints.

<details>
<summary>Answer</summary>

Patch the full intended selector so the Service keeps the shared app label and changes only the version target.

**D is correct** because the full selector retains the shared app identity and targets green Pods. A is wrong because dropping `app` can select unrelated Pods. B is wrong because it removes capacity without moving the selector, and C is wrong because it changes blue Pod identity instead of performing a controlled cutover.

```bash
kubectl patch svc shop-svc -p '{"spec":{"selector":{"app":"shop","version":"green"}}}'
kubectl get svc shop-svc -o yaml
kubectl get endpointslice -l kubernetes.io/service-name=shop-svc
kubectl get pods -l app=shop,version=green
```

The important verification is endpoint membership, not only the Service YAML. EndpointSlices should point to ready green Pods and should not include blue Pods for this Service.

</details>

---

### Question 5: Canary With Operational Separation

A team wants a simple canary for `myapp` using plain Kubernetes Services. The stable Deployment should run nine replicas, the canary should run one replica, and one Service should route to both. They also want logs from the canary only during the test. Design the labels, scaling commands, and Service selector.

A) Give both tracks `app: myapp`, add distinct `track` labels, and select only `app` in the Service.
B) Give stable and canary different `app` labels, then select only `track: canary` in the Service.
C) Give every Pod only `app: myapp`, then use the shared label to isolate canary logs.
D) Give both tracks the same `track: stable`, then select `app` and `track` together.

<details>
<summary>Answer</summary>

Use a shared traffic label such as `app: myapp` for both Deployments and a separate diagnostic label such as `track: stable` or `track: canary`.

**A is correct** because the shared app label includes both tracks in traffic while distinct track labels isolate canary logs. B is wrong because its Service excludes stable Pods. C is wrong because it loses diagnostic separation, and D is wrong because it gives the canary the same track identity as stable.

```bash
kubectl scale deploy stable-app --replicas=9
kubectl scale deploy canary-app --replicas=1
kubectl expose deploy stable-app --name=myapp-svc --port=80 --selector=app=myapp
kubectl get endpointslice -l kubernetes.io/service-name=myapp-svc
kubectl logs -l app=myapp,track=canary --tail=80
```

The Service selector should be broad enough to include both stable and canary Pods, while the track label lets you inspect canary behavior separately. With plain Services, the traffic share is approximate, so the answer should not claim exact percentage enforcement.

</details>

---

### Question 6: Helm Values Drift During Upgrade

A release named `frontend` was installed with custom CPU limits and `replicaCount=3`. Your teammate runs `helm upgrade frontend repo/frontend --set service.type=LoadBalancer`, and after the upgrade the resource limits appear to have returned to chart defaults. Explain what likely happened and show a safer upgrade pattern.

A) Patch the Deployment limits directly; Helm will preserve the patch on later upgrades.
B) Reinstall the chart with defaults; a new release will recover the earlier limits.
C) Inspect deployed values, then upgrade with `--reuse-values` or a complete values file.
D) Run `helm show values` only, then repeat the same upgrade with a new revision.

<details>
<summary>Answer</summary>

The upgrade likely did not preserve previous custom values, or it rendered from a value set that omitted the resource limits. Inspect the deployed values and then upgrade using `--reuse-values` or a complete values file.

**C is correct** because it starts from evidence of deployed custom values and supplies a complete intended value set. A is wrong because direct patches can be overwritten by Helm. B is wrong because it discards the overrides, and D is wrong because it shows chart defaults rather than proving the release's deployed values.

```bash
helm get values frontend --all
helm history frontend
helm upgrade frontend repo/frontend --reuse-values --set service.type=LoadBalancer
helm status frontend
```

The safer pattern is to treat values as desired configuration, not as a one-off command memory. For production workflows, a checked-in values file is usually clearer than long `--set` chains.

</details>

---

### Question 7: Strategy Choice for Single-Version Workload

A small internal database-like application cannot safely run two versions at the same time because the new version writes data in a format the old version cannot read. The team currently uses the default Deployment strategy and sees both versions serving briefly during updates. Evaluate the strategy and provide the Deployment configuration change that matches the constraint.

A) Keep RollingUpdate and set `maxSurge: 1` to make overlap shorter.
B) Use a canary so only one new Pod overlaps with the old version.
C) Switch the Service selector after both versions are running and ready.
D) Use Recreate and accept downtime while old Pods stop before new Pods start.

<details>
<summary>Answer</summary>

The default rolling update is mismatched because it can run old and new Pods concurrently. Use `Recreate` if the requirement is that only one version runs at a time and downtime is acceptable for this workload.

**D is correct** because Recreate prevents concurrent old and new Pods when downtime is acceptable. A is wrong because a surge Pod still overlaps with old Pods. B is wrong because it deliberately mixes versions, and C is wrong because it requires both versions to run before cutover.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: internal-db-app
spec:
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: internal-db-app
  template:
    metadata:
      labels:
        app: internal-db-app
    spec:
      containers:
        - name: app
          image: internal-db-app:2.0
```

The answer should also mention the trade-off: Recreate avoids mixed versions but creates an availability gap while old Pods terminate and new Pods start.

</details>

---

### Question 8: Choosing Between Helm and Kustomize Under Exam Pressure

During a practice exam, one task says, "Install the `bitnami/nginx` chart as release `my-nginx` in namespace `web` with three replicas." Another task says, "Create a `kustomization.yaml` that includes `deployment.yaml`, sets namespace `production`, prefixes names with `prod-`, and overrides the nginx image tag." Compare the correct tool choices and provide the core commands for each.

A) Use Helm for both tasks because each involves an image and a namespace.
B) Use Helm for the chart release and Kustomize for local manifest transformations.
C) Use Kustomize for the chart release and Helm for the prefix transformation.
D) Use raw `kubectl apply` for both tasks and skip release or overlay metadata.

<details>
<summary>Answer</summary>

The first task is Helm because it names a chart and release. The second task is Kustomize because it asks for a `kustomization.yaml` and manifest transformations.

**B is correct** because a chart and named release indicate Helm, while `kustomization.yaml` indicates Kustomize transformations. A is wrong because Helm is not requested for the raw-manifest task. C is wrong because it reverses the tools, and D is wrong because it omits the required release and overlay workflows.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm install my-nginx bitnami/nginx --set replicaCount=3 -n web --create-namespace
helm status my-nginx -n web
```

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
namespace: production
namePrefix: prod-
images:
  - name: nginx
    newTag: "1.25"
```

```bash
kubectl kustomize .
kubectl apply -k .
```

The key distinction is ownership. Helm manages a release revision from a chart, while Kustomize renders transformed Kubernetes YAML from local manifests.

</details>

---

## Hands-On Exercise

In this exercise, you will build and recover a small deployment workflow that combines the Part 2 skills. You will create a Deployment, observe rollout mechanics, introduce a controlled change, inspect traffic routing, practice Kustomize previewing, and choose the correct recovery boundary. Use a disposable namespace so cleanup is safe and obvious.

The exercise is intentionally multi-step because real deployment work is multi-step. Do not rush directly to the final command. At each stage, write down what you expect Kubernetes to create or change, then verify whether the cluster matched your expectation. That prediction habit is what converts command practice into operational skill.

### Step 1: Create a Disposable Namespace

Create a namespace for the exercise and keep every object inside it. This keeps the lab isolated and makes cleanup predictable.

```bash
kubectl create ns ckad-part2-lab
kubectl config set-context --current --namespace=ckad-part2-lab
```

Success criteria:

- [ ] The namespace `ckad-part2-lab` exists.
- [ ] Your current context uses `ckad-part2-lab` as the default namespace.
- [ ] `k get all` in the namespace returns no unexpected application objects before you start.

### Step 2: Deploy the Stable Version

Create a stable Deployment with four replicas and a rolling update configuration that allows one surge Pod and no planned unavailability. Expose it with a Service that selects `app: webapp`.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: webapp
      track: stable
  template:
    metadata:
      labels:
        app: webapp
        track: stable
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: webapp-svc
spec:
  selector:
    app: webapp
    track: stable
  ports:
    - port: 80
      targetPort: 80
EOF
```

```bash
kubectl rollout status deploy/webapp
kubectl get deploy,rs,pods,svc
kubectl get endpointslice -l kubernetes.io/service-name=webapp-svc
```

Success criteria:

- [ ] The Deployment `webapp` reaches four ready replicas.
- [ ] The Service `webapp-svc` has endpoints that point to stable Pods.
- [ ] `k get rs -l app=webapp` shows the ReplicaSet created by the initial Pod template.
- [ ] You can explain why the Service selector includes both `app` and `track`.

### Step 3: Perform and Inspect an Image Update

Update the image to a newer nginx tag and verify that Kubernetes creates a new ReplicaSet. This step practices the difference between changing the Pod template and changing only the replica count.

```bash
kubectl set image deploy/webapp nginx=nginx:1.26
kubectl rollout status deploy/webapp
kubectl rollout history deploy/webapp
kubectl get rs -l app=webapp
kubectl get pods -l app=webapp -o wide
```

Success criteria:

- [ ] The rollout completes successfully.
- [ ] Rollout history shows more than the initial revision.
- [ ] ReplicaSets show that the new Pod template created a new ReplicaSet.
- [ ] You can identify which command proved that the rollout completed.

### Step 4: Practice a Deployment Rollback

Roll back the Deployment to the previous revision and verify that the ReplicaSet distribution changes. This is a raw Deployment rollback, not a Helm rollback, because the workload was created directly with Kubernetes manifests.

```bash
kubectl rollout undo deploy/webapp
kubectl rollout status deploy/webapp
kubectl rollout history deploy/webapp
kubectl get rs -l app=webapp
```

Success criteria:

- [ ] The Deployment returns to the previous image revision.
- [ ] The rollout completes after the undo operation.
- [ ] You can state why `k rollout undo` is appropriate here.
- [ ] You can state why `helm rollback` would not be appropriate for this object as created.

### Step 5: Create a Green Deployment for Blue/Green Practice

Create a second Deployment representing the green version. Keep the same `app: webapp` label but use `track: green` so the Service can switch traffic precisely.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp-green
spec:
  replicas: 4
  selector:
    matchLabels:
      app: webapp
      track: green
  template:
    metadata:
      labels:
        app: webapp
        track: green
    spec:
      containers:
        - name: nginx
          image: nginx:1.26
          ports:
            - containerPort: 80
EOF
```

```bash
kubectl rollout status deploy/webapp-green
kubectl get pods -l app=webapp --show-labels
kubectl get endpointslice -l kubernetes.io/service-name=webapp-svc
```

Success criteria:

- [ ] The green Deployment reaches four ready replicas.
- [ ] The Service still points only to stable Pods before the cutover.
- [ ] You can explain why the green Pods exist but do not receive Service traffic yet.
- [ ] The labels make it possible to distinguish stable and green Pods in commands.

### Step 6: Cut Traffic to Green and Verify Endpoint Routing

Patch the Service selector to green while preserving the shared app label. Then inspect both the complete selector and its EndpointSlices, because the patch command can succeed even when no ready green Pod matches the resulting traffic rule.

```bash
kubectl patch svc webapp-svc -p '{"spec":{"selector":{"app":"webapp","track":"green"}}}'
kubectl get svc webapp-svc -o yaml
kubectl get endpointslice -l kubernetes.io/service-name=webapp-svc
kubectl get pods -l app=webapp,track=green
```

Success criteria:

- [ ] The Service selector includes `app: webapp` and `track: green`.
- [ ] EndpointSlices for `webapp-svc` point to green Pods.
- [ ] Stable Pods still exist but are no longer selected by the Service.
- [ ] You can describe the rollback action for this blue/green cutover.

### Step 7: Switch Back to Stable

Recover traffic by switching the Service selector back to stable. This shows that a blue/green rollback is a traffic routing change rather than a Deployment image rollback.

```bash
kubectl patch svc webapp-svc -p '{"spec":{"selector":{"app":"webapp","track":"stable"}}}'
kubectl get endpointslice -l kubernetes.io/service-name=webapp-svc
```

Success criteria:

- [ ] EndpointSlices point back to stable Pods.
- [ ] Green Pods still exist after traffic is moved away.
- [ ] You can explain why this rollback did not modify either Deployment.
- [ ] You can identify when you would delete or scale down the green Deployment later.

### Step 8: Preview a Kustomize Overlay

Create a small Kustomize working directory outside the cluster state and preview it before applying. This step reinforces that Kustomize rendering should be inspected before cluster changes.

```bash
mkdir -p /tmp/ckad-part2-kustomize
cd /tmp/ckad-part2-kustomize
cat <<'EOF' > deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
EOF
cat <<'EOF' > kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
namespace: ckad-part2-lab
namePrefix: prod-
images:
  - name: nginx
    newTag: "1.26"
EOF
kubectl kustomize .
```

Success criteria:

- [ ] The rendered Deployment name is prefixed with `prod-`.
- [ ] The rendered namespace is `ckad-part2-lab`.
- [ ] The rendered image tag is `1.26`.
- [ ] You inspected the output before applying it to the cluster.

### Step 9: Apply the Overlay and Verify the Rendered Object

Apply the overlay only after previewing its rendered name, namespace, labels, and image. Then verify the actual object name and rollout status in the cluster so the result matches the manifest you inspected before the apply operation.

```bash
kubectl apply -k .
kubectl rollout status deploy/prod-api
kubectl get deploy prod-api -o wide
```

Success criteria:

- [ ] The Deployment is named `prod-api`, not `api`.
- [ ] The Deployment runs in the lab namespace.
- [ ] The Deployment uses the overridden image tag.
- [ ] You can explain why a teammate looking for `deploy/api` would be using the wrong rendered name.

### Step 10: Cleanup

Return to a safe namespace, remove the lab namespace, and delete the temporary Kustomize directory. Cleanup is part of deployment skill because stale objects make later verification misleading.

```bash
cd -
kubectl config set-context --current --namespace=default
kubectl delete ns ckad-part2-lab
rm -rf /tmp/ckad-part2-kustomize
```

Success criteria:

- [ ] The namespace `ckad-part2-lab` is deleted or terminating.
- [ ] Your current context no longer defaults to the deleted namespace.
- [ ] The temporary Kustomize directory is removed.
- [ ] You can rerun `k get ns ckad-part2-lab` and explain the result.

---

## Sources

- [training.linuxfoundation.org: certified kubernetes application developer ckad](https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/) — The Linux Foundation CKAD page names Kubernetes v1.35 and lists deployment-strategy, Helm, and Kustomize competencies.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment concept page directly documents declarative updates, new ReplicaSets on Pod template changes, and the fact that scaling does not create a new revision.
- [kubernetes.io: index.html](https://kubernetes.io/docs/concepts/services-networking/service/index.html) — The Service docs directly describe selector-based targeting and continuous EndpointSlice updates for matching Pods.
- [kubernetes.io: liveness readiness startup probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — The probes documentation states this behavior explicitly for failed readiness probes.
- [helm.sh: helm rollback](https://helm.sh/docs/helm/helm_rollback/) — The Helm rollback command reference directly defines rollback-by-revision and points readers to `helm history` for revision numbers.
- [helm.sh: helm show values](https://helm.sh/docs/helm/helm_show_values/) — The Helm command reference says `helm show values` inspects a chart and displays the contents of `values.yaml`.
- [helm.sh: helm get values](https://helm.sh/docs/helm/helm_get_values/) — The Helm get-values reference documents `--all` as dumping all computed values for the named release.
- [helm.sh: helm upgrade](https://helm.sh/docs/helm/helm_upgrade/) — The Helm upgrade reference directly defines the `--reuse-values` merge behavior.
- [helm.sh: helm template](https://helm.sh/docs/helm/helm_template/) — The Helm template reference describes it as locally rendering templates and displaying the output.
- [kubernetes.io: kustomization](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) — The Kustomize task page enumerates these customization fields and explains the kustomization-based workflow.
- [kubernetes.io: management](https://kubernetes.io/docs/concepts/workloads/management/) — The Kubernetes workload-management docs explicitly present the `track`-label canary pattern, shared Service selector, and 3:1 replica example.
- [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) — Best reference for how Services track ready backends and how endpoint conditions change during updates and termination.
- [Helm Commands](https://helm.sh/docs/helm/) — Central CLI reference for `helm show values`, `get values`, `upgrade`, `history`, `rollback`, and `template`.

## Next Module

[Part 3: Application Observability and Maintenance](/k8s/ckad/part3-observability/module-3.1-probes/) - Probes, logging, debugging, and API deprecations.
