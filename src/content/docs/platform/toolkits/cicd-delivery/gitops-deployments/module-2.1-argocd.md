---
citations_verified: true
title: "Module 2.1: ArgoCD"
slug: platform/toolkits/cicd-delivery/gitops-deployments/module-2.1-argocd
sidebar:
  order: 2
---

> **Toolkit Track** | Complexity: `[COMPLEX]` | Time: 60-75 min

---

## Prerequisites

Before starting this module, you should be comfortable reading Kubernetes manifests, creating namespaces, and reasoning about
Deployments, Services, ConfigMaps, Secrets, and RBAC. You do not need to be an ArgoCD expert yet, but you should already
understand the GitOps principle from [GitOps Discipline](/platform/disciplines/delivery-automation/gitops/): Git is treated
as the reviewed source of truth, and the cluster is continuously reconciled toward that truth.

You also need Git fundamentals because ArgoCD turns Git operations into deployment operations. A merge, revert, tag, or
branch promotion is not just repository housekeeping once ArgoCD watches that repository. It becomes a production control
plane action, so this module teaches both the mechanics and the operational judgment required to use the tool safely.

For the hands-on section, install a local Kubernetes environment such as kind, plus `kubectl`, `helm`, and the `argocd`
CLI. The commands define `alias k=kubectl` once, then use `k` for the rest of the module.

```bash
kubectl version --client
helm version
argocd version --client
kind version
alias k=kubectl
```

---

## Learning Outcomes

After completing this module, you will be able to:

- **Design** an ArgoCD Application model that separates source, destination, project boundaries, and sync behavior for
  production-grade Kubernetes delivery.
- **Debug** common OutOfSync, Degraded, and permission-denied states by comparing Git intent, rendered manifests, and live
  cluster resources.
- **Evaluate** when to enable automated sync, pruning, self-healing, sync waves, hooks, and ignore rules based on blast
  radius rather than convenience.
- **Implement** multi-application and multi-cluster GitOps patterns using App of Apps, ApplicationSets, and AppProjects
  without giving teams more access than they need.
- **Justify** rollback and recovery choices during incidents by choosing between Git revert, ArgoCD sync controls, and
  temporary operational freezes.

---

## Why This Module Matters

A platform engineer at a payments company watches a deployment dashboard turn red at the start of a busy business day.
No one ran `kubectl delete`, no one changed a Helm release manually, and the cluster itself is healthy. The actual cause
is quieter: a cleanup pull request removed a manifest directory that ArgoCD still treated as production intent, and the
controller faithfully reconciled the cluster by deleting resources that disappeared from Git.

That incident is painful because ArgoCD did not malfunction. It honored the contract the team gave it. Git said the
resources should not exist, pruning was enabled, and the controller executed the desired state. GitOps reduces drift and
improves auditability, but it also gives repository changes operational force. A weak review process, broad project
permissions, or careless prune policy can convert a normal merge into a fleet-wide outage.

ArgoCD is therefore not just another deployment UI. It is a reconciliation engine, an authorization boundary, a diff
calculator, and an operations workflow. Senior platform teams use it to make deployments boring, but they also build
guardrails around it because a system that can repair drift quickly can amplify mistakes just as quickly. This module
teaches the tool through that lens: not "which YAML fields exist," but "what does this controller do next, why, and who
is allowed to make it happen?"

---

## Core Concept: Reconciliation Is the Product

ArgoCD exists to answer one recurring question: does the live cluster match the desired state stored in Git? The answer
is not a one-time deployment result. It is continuously recalculated by controllers that fetch source material, render
manifests, compare them against Kubernetes, and optionally apply changes. This loop is why GitOps feels different from
traditional CI/CD. A CI job pushes a deployment and exits; ArgoCD keeps asking whether reality still matches intent.

The first mental model is simple: Git describes desired state, Kubernetes exposes live state, and ArgoCD sits between
them as a reconciler. The details become more subtle when Helm templates are rendered, Kustomize overlays mutate names,
admission controllers default fields, or humans make manual changes during an incident. ArgoCD must compare rendered
intent with live resources, not just compare files with files.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                         ARGOCD RECONCILIATION LOOP                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Git repository                  ArgoCD control plane       Kubernetes API  │
│  ┌─────────────────────┐        ┌──────────────────────┐   ┌────────────┐ │
│  │ apps/payments/      │        │ repo-server          │   │ live state │ │
│  │ ├── base/           │ fetch  │ - clones Git         │   │ resources  │ │
│  │ └── overlays/prod/  ├───────▶│ - renders manifests  │   │ health     │ │
│  └─────────────────────┘        └──────────┬───────────┘   └─────┬──────┘ │
│                                            │                     │        │
│                                            ▼                     │        │
│                                  ┌──────────────────────┐        │        │
│                                  │ application          │ query  │        │
│                                  │ controller           ├────────┘        │
│                                  │ - compares desired   │                 │
│                                  │ - detects drift      │                 │
│                                  │ - applies sync plan  │ apply           │
│                                  └──────────┬───────────┘                 │
│                                             └────────────────────────────▶ │
│                                                                            │
│  Result: Synced when desired and live match; OutOfSync when they differ.    │
└────────────────────────────────────────────────────────────────────────────┘
```

This model explains why "ArgoCD deployed my app" is an incomplete statement. The controller may have rendered the desired
manifests successfully, applied them successfully, and still marked the application Degraded because Kubernetes health
checks failed. It may also mark an app OutOfSync because a mutating webhook added fields that are harmless but not present
in Git. Useful ArgoCD operation starts with separating render problems, apply problems, health problems, and drift problems.

| State | What ArgoCD Is Saying | Typical Practitioner Question |
|-------|------------------------|-------------------------------|
| `Synced` | Rendered desired state matches tracked live resources | Are the resources also healthy and serving traffic? |
| `OutOfSync` | Desired and live resources differ | Is this expected drift, a manual hotfix, or a Git change waiting to apply? |
| `Progressing` | Kubernetes accepted changes but health is not final | Which controller condition is still moving toward readiness? |
| `Degraded` | A resource reports unhealthy or failed status | Is the manifest wrong, or is the workload failing after deployment? |
| `Missing` | A resource expected from Git is absent in the cluster | Was it deleted manually, pruned by another app, or blocked by permissions? |
| `Unknown` | ArgoCD cannot determine state confidently | Is the API server unreachable, the CRD missing, or health logic incomplete? |

Stop and think: if a production Deployment is `OutOfSync` because the live cluster has five replicas while Git says three,
what extra fact do you need before deciding whether to sync? The important question is not "how do I force it back?" The
important question is "who changed it and why?" If an HPA owns replica count, you probably need an ignore rule. If an
operator manually scaled during an incident, syncing immediately may remove emergency capacity before the incident is over.

[ArgoCD's main components divide this work so failures are easier to isolate.](https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/) The API server serves the UI, CLI, API, SSO,
and RBAC checks. The repo server clones repositories and renders manifests through Helm, Kustomize, Jsonnet, or plain YAML.
The application controller watches Application resources, compares desired and live state, and performs sync operations.
Redis caches expensive state so the system does not repeatedly render and fetch the same material under load.

| Component | Primary Job | Failure Symptoms | First Debug Step |
|-----------|-------------|------------------|------------------|
| API server | UI, CLI, webhooks, sessions, RBAC enforcement | Login failures, UI errors, CLI timeouts | Check `argocd-server` logs and Service reachability |
| Repo server | Clone repositories and render manifests | Manifest generation errors, missing chart values | Run `argocd app manifests` and inspect repo-server logs |
| Application controller | Compare, sync, prune, and assess health | Apps stuck OutOfSync, sync waves blocked | Check app events and controller logs |
| Dex | Optional OIDC identity brokering | SSO redirects fail or groups are missing | Inspect OIDC claims and Dex connector config |
| Redis | Cache manifests and application state | Slow UI, repeated rendering, cache errors | Check Redis health and repo-server latency |

A useful senior habit is to name which component owns the symptom before touching configuration. If the UI denies a sync
button, that is probably RBAC. If the manifest preview fails before Kubernetes sees anything, that is probably repo-server
or source configuration. If Kubernetes accepts the manifest but health never turns green, that is probably workload or
health-assessment behavior. This component-first diagnosis prevents random changes to sync policy when the problem is
actually authentication, rendering, or application readiness.

---

## Installing ArgoCD Without Confusing Bootstrap and Delivery

Installing ArgoCD is a bootstrap problem, not yet an application-delivery problem. At the start, something outside ArgoCD
must create the `argocd` namespace and install the ArgoCD controllers. Many teams use a one-time `kubectl apply`, Helm,
Terraform, or a cluster lifecycle tool for this bootstrap. After ArgoCD is running, it can manage many other resources,
and mature teams often make ArgoCD manage its own configuration as well.

For a lab, [the upstream install manifest is acceptable](https://argo-cd.readthedocs.io/en/stable/getting_started/) because it creates a complete working control plane quickly. For
production, teams usually prefer Helm or Kustomize so they can pin versions, configure replicas, set resource requests,
enable SSO, define ingress, and manage values through review. The important distinction is that the bootstrap path should
be repeatable and versioned even if ArgoCD is not yet available to reconcile it.

```bash
kind create cluster --name argocd-lab

alias k=kubectl

k create namespace argocd

k apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

k -n argocd wait \
  --for=condition=ready pod \
  -l app.kubernetes.io/name=argocd-server \
  --timeout=180s

k -n argocd get pods
```

[The initial admin password is stored in a Kubernetes Secret.](https://argo-cd.readthedocs.io/en/stable/getting_started/) In production, you should rotate or disable this default admin
path after SSO and RBAC are configured. In a lab, retrieving the password lets you access the UI and CLI quickly.

```bash
ARGOCD_PASSWORD="$(
  k -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath="{.data.password}" | base64 -d
)"

printf '%s\n' "$ARGOCD_PASSWORD"
```

Port-forwarding is enough for a local exercise. The service listens on HTTPS, so the browser and CLI must connect with
TLS expectations. The `--insecure` flag below means the local CLI will not reject the self-signed certificate used in the
lab. That is not a recommendation for production ingress; production should use trusted certificates and a deliberate
network exposure model.

```bash
k -n argocd port-forward svc/argocd-server 8080:443 > /tmp/argocd-port-forward.log 2>&1 &

argocd login 127.0.0.1:8080 \
  --username admin \
  --password "$ARGOCD_PASSWORD" \
  --insecure

argocd app list
```

A production Helm install expresses the same control-plane intent with configurable values. The exact chart version and
ArgoCD version should be pinned by your platform team because controller upgrades can change behavior around health checks,
ApplicationSet features, or Kubernetes API compatibility. The following command is runnable, but it is still only a
starting point; production values should live in a reviewed repository rather than being typed at a terminal.

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --set server.replicas=2 \
  --set repoServer.replicas=2 \
  --set redis.enabled=true \
  --set controller.replicas=1
```

The application controller can shard clusters across replicas. To enable sharding, set the StatefulSet replica count and
`ARGOCD_CONTROLLER_REPLICAS` to the same number. Scaling Argo CD is not just "increase every Deployment."
Repo-server replicas help when rendering is expensive, API-server replicas help with UI and CLI concurrency, and controller
tuning helps when many applications reconcile at once. Treat those as different bottlenecks, not one generic capacity knob.

---

## Modeling an Application: Source, Destination, Project, Sync

An ArgoCD `Application` is a contract that binds four ideas together. The source tells ArgoCD where desired state lives
and how to render it. The destination tells ArgoCD which cluster and namespace should receive those resources. The project
defines what the application is allowed to do. The sync policy defines how aggressively ArgoCD should reconcile differences.

That separation matters because most production mistakes are boundary mistakes. A valid Git path can still target the
wrong namespace. A harmless staging application can become dangerous if it belongs to a project that allows cluster-wide
resources. A correct production manifest can become risky if pruning is enabled without deletion review. Reading an
Application as a boundary document is more useful than reading it as a deployment recipe.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook-staging
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: guestbook-staging
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

This example uses the in-cluster Kubernetes API server as its destination. That is the simplest mode because ArgoCD is
installed in the same cluster it manages. Multi-cluster operation adds registered cluster credentials, but the Application
shape remains the same: source, destination, project, and sync behavior still define the boundary.

```bash
cat > /tmp/guestbook-staging.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook-staging
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: guestbook-staging
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

k apply -f /tmp/guestbook-staging.yaml

argocd app get guestbook-staging
argocd app sync guestbook-staging
argocd app wait guestbook-staging --health --timeout 180
```

When you use Helm, [the Application source points at a chart repository or Git repository](https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/) and provides values. This is
powerful because teams can expose a small set of environment differences without duplicating whole manifest trees. It is
also a source of confusion because the rendered manifest, not the values file alone, is what ArgoCD compares against the
cluster. Debugging Helm-based apps often starts by asking ArgoCD to show the rendered manifests it is actually applying.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: nginx-demo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://charts.bitnami.com/bitnami
    chart: nginx
    targetRevision: 15.4.0
    helm:
      releaseName: nginx-demo
      values: |
        replicaCount: 2
        service:
          type: ClusterIP
  destination:
    server: https://kubernetes.default.svc
    namespace: nginx-demo
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Kustomize expresses variation differently. A base contains shared resources, and overlays patch or compose those resources
for each environment. In GitOps repositories this is often easier to review than large copied manifests because reviewers
can see exactly what production changes relative to staging. The trade-off is that name prefixes, namespace fields, and
patch targets must be understood carefully or resources will appear with unexpected names.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                         KUSTOMIZE REPOSITORY SHAPE                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  app-config/                                                               │
│  ├── base/                                                                 │
│  │   ├── deployment.yaml          shared container, ports, labels           │
│  │   ├── service.yaml             shared service selector and port          │
│  │   └── kustomization.yaml       base resource list                        │
│  └── overlays/                                                             │
│      ├── staging/                                                          │
│      │   └── kustomization.yaml   one replica, staging namespace            │
│      └── production/                                                       │
│          └── kustomization.yaml   more replicas, production namespace       │
│                                                                            │
│  ArgoCD Application source.path points at one overlay, not the whole repo.   │
└────────────────────────────────────────────────────────────────────────────┘
```

Stop and think: if staging and production point at the same Git repository but different overlay paths, where should you
change the container image tag? If every environment should receive the image after promotion, the base may be right. If
production should promote only after staging bakes, the production overlay or a promotion commit may be safer. The right
answer depends on your release process, but the question must be asked before the repository structure is frozen.

A senior review of an Application looks for a handful of risks before approving it. Is `targetRevision` pinned to a branch,
tag, or commit, and does that match the promotion model? Does the destination namespace belong to the team? Does the project
allow only the needed repositories and resource kinds? Is pruning safe for this app? Are namespace creation and resource
ownership clear? Those review questions catch more production issues than memorizing every CRD field.

| Application Field | Design Question | Safer Default for New Teams | When to Relax It |
|-------------------|-----------------|-----------------------------|------------------|
| `source.repoURL` | Which repository is trusted as deployment intent? | Team-owned repo allowlisted by AppProject | Shared platform repos with CODEOWNERS |
| `source.targetRevision` | Which Git ref is deployed? | Environment branch or immutable tag | `HEAD` for fast-moving nonproduction apps |
| `source.path` | Which subtree is the app boundary? | One app or one environment overlay | Monorepo generators with strict review rules |
| `destination.namespace` | Where can resources be created? | Team namespace created by sync option | Cluster bootstrap apps with platform approval |
| `project` | Which policy boundary applies? | One AppProject per team or domain | Shared project only for low-risk labs |
| `syncPolicy.automated.prune` | Can Git deletions delete live resources? | `false` until deletion process is mature | `true` for disposable or tightly governed resources |
| `syncPolicy.automated.selfHeal` | Can ArgoCD revert live drift automatically? | `true` for stateless app config | Temporarily disabled during emergency operations |

---

## Sync Policy: Automation With a Blast Radius

Syncing is the act of applying desired state to the destination cluster. Manual sync means a human or automation command
must approve the action after ArgoCD detects drift. Automated sync means ArgoCD can apply changes when it notices the
desired state differs from live state. Neither is universally correct. The operational question is how much confidence
you have in the source, the review process, and the reversibility of the resources being changed.

The two flags that deserve the most scrutiny are `selfHeal` and `prune`. `selfHeal` tells ArgoCD to undo live changes that
were not made in Git. That is excellent for preventing configuration drift, but it can also undo a carefully documented
emergency scale-up. [`prune` tells ArgoCD to delete live resources that are no longer in the desired state.](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/) That is useful
for cleanup, but it turns file deletions into Kubernetes deletions.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payments-api
  namespace: argocd
spec:
  project: payments
  source:
    repoURL: https://github.com/example/payments-deploy.git
    targetRevision: production
    path: overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: payments-production
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PruneLast=true
```

[`PruneLast=true`](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/) is a small but important example of sequencing judgment. If a change replaces one resource with another,
you often want new resources created and healthy before old resources are removed. This does not make pruning harmless,
but it reduces avoidable downtime during replacement operations. The larger safety decision remains whether the application
should prune automatically at all.

Sync waves give you ordering inside a sync. ArgoCD already applies some Kubernetes resource kinds in a sensible order,
but explicit waves become useful when an application contains namespaces, CRDs, controllers, migrations, workloads, and
ingress resources that have real dependencies. [Lower wave numbers run first](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/), and ArgoCD waits for health before advancing
when health checks are available.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payments-production
  annotations:
    argocd.argoproj.io/sync-wave: "-2"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: payments-config
  namespace: payments-production
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
data:
  FEATURE_FLAGS: "stable"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  namespace: payments-production
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payments-api
  template:
    metadata:
      labels:
        app: payments-api
    spec:
      containers:
        - name: api
          image: nginx:1.25
          ports:
            - containerPort: 80
```

Hooks run jobs at specific points in the sync lifecycle. They are tempting because they let you bolt imperative work onto
a declarative delivery system, but that temptation should be handled carefully. A database migration hook can be useful
when it is idempotent, observable, and safe to retry. A hook that mutates external state without rollback semantics can
make Git history look clean while the real system becomes harder to recover.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: payments-schema-check
  namespace: payments-production
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: check
          image: busybox:1.36
          command:
            - sh
            - -c
            - "echo checking schema compatibility && exit 0"
---
apiVersion: batch/v1
kind: Job
metadata:
  name: payments-post-sync-smoke
  namespace: payments-production
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: smoke
          image: curlimages/curl:8.7.1
          command:
            - sh
            - -c
            - "curl -fsS http://payments-api.payments-production.svc.cluster.local"
```

| Hook | When It Runs | Good Use | Risk to Watch |
|------|--------------|----------|---------------|
| `PreSync` | Before normal resources sync | Compatibility checks, guarded migrations | Blocking all deploys with fragile external calls |
| `Sync` | During the main sync phase | Resources that must participate in the apply plan | Confusing hook-owned and app-owned resources |
| `PostSync` | After synced resources become healthy | Smoke tests, notifications, cache warmups | Declaring success when tests are too shallow |
| `SyncFail` | After a sync operation fails | Cleanup, incident notification | Hiding the original failure behind cleanup noise |
| `PostDelete` | After application deletion operations | Controlled cleanup for managed dependencies | Deleting data that should outlive the application |
| `Skip` | Resource is not applied by ArgoCD | Externally managed resource included for context | Assuming ArgoCD protects a resource it skips |

A healthy sync policy is usually conservative at first and becomes more automated as evidence accumulates. A team may
start with manual sync and no prune in production, then enable self-heal for stateless workloads, then enable automated
sync for low-risk services, then enable prune only where deletion review and ownership are mature. The goal is not maximum
automation. The goal is automation that matches the team's ability to predict and recover from the controller's actions.

---

## ApplicationSets and App of Apps: Scaling Without Copying Risk

Managing one Application manually is straightforward. Managing many Applications across teams, clusters, and environments
requires a generation pattern. ArgoCD has two common answers: App of Apps and ApplicationSets. App of Apps lets one root
Application manage other Application manifests stored in Git. ApplicationSets generate Applications from templates and
generators such as [Git directories, cluster registrations, lists, pull requests, or matrix combinations](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/).

[The App of Apps pattern](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/) is easy to understand because it uses the same Application resource recursively. A root app points
at a directory of child Application manifests. The root app syncs those child Application CRs into the `argocd` namespace,
and each child Application manages its own workload. This is useful for platform bootstrap because installing ingress,
cert-manager, observability, and team apps can be represented as reviewed child Application files.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                              APP OF APPS PATTERN                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Git repository                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ argocd/                                                              │  │
│  │ ├── root-app.yaml             one Application watched by operators    │  │
│  │ └── apps/                                                              │  │
│  │     ├── cert-manager.yaml     child Application for certificates       │  │
│  │     ├── ingress-nginx.yaml    child Application for ingress            │  │
│  │     ├── observability.yaml    child Application for monitoring         │  │
│  │     └── payments-api.yaml     child Application for a service          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                         │                                                  │
│                         ▼                                                  │
│  ArgoCD root Application creates child Application resources in argocd.      │
│                         │                                                  │
│                         ▼                                                  │
│  Each child Application reconciles its own source path and destination.      │
└────────────────────────────────────────────────────────────────────────────┘
```

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform-root
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://github.com/example/platform-gitops.git
    targetRevision: main
    path: argocd/apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
```

ApplicationSets are better when the repetition has a clear template. If each cluster needs the same addon, or each directory
under `apps/*` should become one Application, writing individual child Application files creates review noise. A generator
can discover the intended set, while the template defines the consistent Application shape. The benefit is reduced copying;
the risk is that a broad generator can create or delete many Applications after a small repository change.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: addon-directory-apps
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/example/platform-addons.git
        revision: main
        directories:
          - path: addons/*
  template:
    metadata:
      name: '{{path.basename}}'
    spec:
      project: platform
      source:
        repoURL: https://github.com/example/platform-addons.git
        targetRevision: main
        path: '{{path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{path.basename}}'
      syncPolicy:
        automated:
          prune: false
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

For multi-cluster deployments, a list generator is the most explicit place to start because each cluster entry can carry
different values. Once cluster onboarding is mature, the clusters generator can select registered clusters by label. The
progression is deliberate: static lists are less elegant, but they are easier to review while a team is learning the blast
radius of generated Applications.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: payments-api-environments
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - env: staging
            clusterUrl: https://kubernetes.default.svc
            namespace: payments-staging
            path: overlays/staging
          - env: production
            clusterUrl: https://kubernetes.default.svc
            namespace: payments-production
            path: overlays/production
  template:
    metadata:
      name: 'payments-api-{{env}}'
    spec:
      project: payments
      source:
        repoURL: https://github.com/example/payments-deploy.git
        targetRevision: main
        path: '{{path}}'
      destination:
        server: '{{clusterUrl}}'
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          prune: false
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

| Generator | Use Case | Review Concern |
|-----------|----------|----------------|
| `list` | Explicit environments, clusters, or apps with small counts | Manual entries can drift from reality |
| `git` directories | One Application per repository directory | Directory renames can create and remove apps |
| `git` files | Application values loaded from structured files | Template behavior may hide a risky value change |
| `clusters` | Deploy to registered clusters selected by labels | Cluster labels become deployment policy |
| `matrix` | Combine apps and clusters into a generated grid | Small template mistakes multiply quickly |
| `merge` | Combine data from multiple generators by key | Missing keys can produce surprising omissions |
| `pullRequest` | Temporary preview environments for changes | Cleanup and secret exposure need careful design |

ApplicationSet power should be matched with repository protections. A matrix generator that deploys every app to every
labeled production cluster is efficient, but it means a label change or directory addition can trigger many deployments.
For senior teams, the generator is not just YAML. It is a policy surface that deserves CODEOWNERS, tests that render the
generated Applications, and review from people who understand the target clusters.

---

## Projects and RBAC: The Real Multi-Tenancy Boundary

ArgoCD AppProjects are where platform teams turn "please use the shared ArgoCD instance" into enforceable boundaries.
[A project can restrict source repositories, destination clusters and namespaces](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/), allowed resource kinds, denied resource
kinds, and project-scoped roles. Without projects, a shared ArgoCD instance becomes a shared deployment credential, which
is the opposite of platform self-service.

The most important design rule is that a team should not be able to deploy a resource merely because they can write YAML.
They should need both Git approval and ArgoCD project permission. If Team A can point an Application at Team B's namespace,
the platform has delegated too much. If Team A can create cluster-wide RBAC from an app repository, the project boundary
is too loose for ordinary application delivery.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: payments
  namespace: argocd
spec:
  description: Payments team application boundary
  sourceRepos:
    - https://github.com/example/payments-*
  destinations:
    - namespace: payments-*
      server: https://kubernetes.default.svc
  clusterResourceWhitelist: []
  namespaceResourceWhitelist:
    - group: ""
      kind: ConfigMap
    - group: ""
      kind: Service
    - group: apps
      kind: Deployment
    - group: networking.k8s.io
      kind: Ingress
  namespaceResourceBlacklist:
    - group: ""
      kind: Secret
  orphanedResources:
    warn: true
  roles:
    - name: developer
      description: Payments developers can view and sync payments applications
      policies:
        - p, proj:payments:developer, applications, get, payments/*, allow
        - p, proj:payments:developer, applications, sync, payments/*, allow
        - p, proj:payments:developer, logs, get, payments/*, allow
      groups:
        - payments-developers
```

This project intentionally denies direct Secret creation. That does not mean payments applications cannot use secrets.
It means secrets should arrive through an approved mechanism such as External Secrets, Sealed Secrets, or a platform-owned
secret delivery process. The policy separates application deployment from credential management, which is a common and
valuable platform boundary.

[Instance-level RBAC maps users and groups to ArgoCD capabilities.](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/) Project roles then narrow what those users can do inside
a project. Both layers matter. Instance RBAC can decide whether a group can create Applications at all; project roles can
decide which project applications they may get, sync, or inspect. When SSO is configured, group claims from the identity
provider become part of this enforcement chain.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.default: role:readonly
  policy.csv: |
    p, role:platform-admin, applications, *, */*, allow
    p, role:platform-admin, projects, *, *, allow
    p, role:platform-admin, clusters, *, *, allow
    g, platform-admins, role:platform-admin

    p, role:application-developer, applications, get, */*, allow
    p, role:application-developer, applications, sync, */*, allow
    p, role:application-developer, logs, get, */*, allow
    g, application-developers, role:application-developer
  scopes: '[groups]'
```

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                         SOFT MULTI-TENANT ARGOCD                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Identity Provider                                                         │
│  ┌────────────────────────┐                                                │
│  │ groups claim            │                                                │
│  │ - payments-developers   │                                                │
│  │ - search-developers     │                                                │
│  └────────────┬───────────┘                                                │
│               │                                                            │
│               ▼                                                            │
│  ArgoCD RBAC maps groups to roles, then AppProjects limit destinations.     │
│                                                                            │
│  ┌────────────────────────┐             ┌────────────────────────┐         │
│  │ Project: payments       │             │ Project: search         │         │
│  │ Repos: payments-*       │             │ Repos: search-*         │         │
│  │ Namespaces: payments-*  │             │ Namespaces: search-*    │         │
│  │ Cluster resources: none │             │ Cluster resources: none │         │
│  └────────────┬───────────┘             └────────────┬───────────┘         │
│               │                                      │                     │
│               ▼                                      ▼                     │
│  payments-staging, payments-prod        search-staging, search-prod         │
│                                                                            │
│  Shared ArgoCD instance, separated by source, destination, kind, and role.   │
└────────────────────────────────────────────────────────────────────────────┘
```

Soft multi-tenancy is not hard isolation. All tenants still depend on the availability and correctness of the shared
ArgoCD control plane. A platform team should monitor it as shared infrastructure, restrict who can modify global settings,
and avoid letting ordinary app teams install arbitrary config-management plugins. For stronger tenant separation, some
organizations run separate ArgoCD instances per environment, business unit, or security boundary.

The practical question is not "one ArgoCD or many?" The practical question is which failure domains must be separated.
A single instance for many dev teams may be fine if projects are strict and workloads are low risk. Regulated production
systems may justify a dedicated instance with a smaller administrator group, separate SSO policy, stricter repository
allowlists, and slower upgrade cadence.

---

## Troubleshooting: From Symptom to Owner

ArgoCD troubleshooting is easiest when you start from the status and then identify the owner of the failing layer. A sync
failure is not the same as a health failure. A manifest generation error is not the same as an RBAC denial. An OutOfSync
diff is not always a bug. The fastest operators avoid "click sync again" as a reflex and instead collect enough evidence
to decide whether the source, renderer, Kubernetes API, workload, or ArgoCD policy is responsible.

The CLI gives you a compact path through that evidence. `argocd app get` shows status, conditions, sync policy, source,
destination, and recent history. `argocd app diff` shows what ArgoCD thinks differs. `argocd app manifests` shows rendered
desired manifests. Kubernetes commands then show live resource events, conditions, and controller-level failures.

```bash
argocd app get guestbook-staging

argocd app diff guestbook-staging

argocd app manifests guestbook-staging > /tmp/guestbook-rendered.yaml

k -n guestbook-staging get all

k -n guestbook-staging describe deployment guestbook-ui

k -n argocd logs deploy/argocd-application-controller --tail=100
```

A common OutOfSync pattern appears when another controller owns a field that Git also declares. Replica counts managed by
an HPA are the classic example. If Git says three replicas and the HPA scales to six, ArgoCD can report drift forever or
fight the autoscaler if self-heal is enabled. The fix is not to disable GitOps for the whole app. The fix is to stop
declaring ownership of that field in the wrong place or [configure an ignore rule for the controller-owned field](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/).

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web-with-hpa
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/web-deploy.git
    targetRevision: main
    path: overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: web-production
  ignoreDifferences:
    - group: apps
      kind: Deployment
      name: web
      namespace: web-production
      jsonPointers:
        - /spec/replicas
```

Another common pattern is a rendered manifest that Kubernetes rejects. This often happens when a CRD is missing, an API
version is no longer served, or a policy controller denies a resource. ArgoCD cannot make an invalid desired state valid;
it can only report the failure. In that case, look at app conditions and Kubernetes admission messages before changing
sync options. A sync option cannot fix a resource kind that the cluster does not understand.

```bash
argocd app get guestbook-staging --show-operation

argocd app history guestbook-staging

k -n argocd get events --sort-by=.lastTimestamp | tail -n 20
```

Rollbacks should usually start in Git. Reverting the commit that introduced the bad desired state preserves the audit trail
and lets ArgoCD reconcile normally. The ArgoCD rollback command can be useful when you need to return quickly to a previous
application revision, but [automated sync may move the app back to the current Git head unless you pause or change policy](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).
That is why incident runbooks should say exactly when to suspend auto-sync and who may do it.

```bash
git revert HEAD
git push

argocd app sync guestbook-staging
argocd app wait guestbook-staging --health --timeout 180
```

If you must pause automation during an incident, make it explicit and temporary. Record why it was done, make the Git fix,
sync deliberately, and then restore the policy. Long-lived manual drift is exactly what GitOps was adopted to prevent.
A controlled exception is operations; an undocumented exception becomes technical debt that ArgoCD will eventually surface.

```bash
argocd app set guestbook-staging --sync-policy none

argocd app diff guestbook-staging

argocd app sync guestbook-staging

argocd app set guestbook-staging --sync-policy automated --self-heal
```

| Symptom | Likely Layer | What to Inspect | Common Fix |
|---------|--------------|-----------------|------------|
| Manifest generation error | Source or renderer | Repo-server logs and rendered manifests | Fix Helm values, Kustomize path, or repo credentials |
| Permission denied during sync | ArgoCD project or Kubernetes RBAC | AppProject, destination, service account permissions | Narrowly grant the missing action or change destination |
| OutOfSync after every sync | Ownership conflict or mutation | `argocd app diff` and live resource YAML | Remove field from Git or add targeted ignore rule |
| Degraded Deployment | Workload runtime | Pods, ReplicaSet events, readiness probes | Fix image, config, resources, or probes |
| App stuck deleting | Finalizer or prune issue | Application finalizers and child resources | Remove blockers only after confirming ownership |
| UI login works but sync denied | ArgoCD RBAC | `argocd-rbac-cm`, SSO group claims, project roles | Map group to the correct role with least privilege |

---

## Worked Example: A Safe Fix for Drift and Risky Pruning

Challenge: the `payments-api` Application is OutOfSync in production. The diff shows the live Deployment has five replicas,
while Git says three. The same Application also has automated pruning enabled. The on-call engineer wants to press Sync
because the UI is red, but the service is currently handling elevated traffic from a partner launch. Walk through the
decision and produce a safer fix.

First, separate the two issues. Replica drift is the visible symptom, but automated pruning is a latent risk. Syncing now
would likely reduce replicas from five to three if ArgoCD owns `/spec/replicas`. That might be correct after the launch,
but during elevated traffic it could reduce capacity. Pruning is not involved in this replica diff, but it means any
concurrent Git deletion in the same app could remove resources automatically. The safest response starts with evidence,
not with a sync button.

```bash
argocd app get payments-api

argocd app diff payments-api

k -n payments-production get deploy payments-api -o yaml > /tmp/payments-live.yaml

argocd app manifests payments-api > /tmp/payments-desired.yaml
```

Assume the investigation shows an HPA exists and scaled the Deployment during real traffic. That means the live replica
count is not a rogue manual change; it is controller-owned operational state. The desired manifest should not fight it.
A senior fix is to let the HPA own replicas and make ArgoCD ignore only that field for this Deployment. Do not ignore the
whole Deployment, and do not disable self-heal for unrelated fields such as image, environment, or probes.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payments-api
  namespace: argocd
spec:
  project: payments
  source:
    repoURL: https://github.com/example/payments-deploy.git
    targetRevision: production
    path: overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: payments-production
  ignoreDifferences:
    - group: apps
      kind: Deployment
      name: payments-api
      namespace: payments-production
      jsonPointers:
        - /spec/replicas
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PruneLast=true
```

The same change disables automated pruning because this production app has not yet passed a deletion-safety review. That
does not mean resources can never be removed. It means deletion becomes a deliberate sync decision until the team adds
CODEOWNERS, deletion review, orphan warnings, and confidence through staging. This is the difference between slowing down
dangerous operations and abandoning GitOps.

Next, test the rendered result before relying on the controller. A reviewer should be able to see the Application policy
change, understand why replica drift is expected, and confirm no unrelated resources are being ignored. The desired result
is not merely "green UI." The desired result is a reconciler that still enforces application intent while respecting the
autoscaler's ownership of one field.

```bash
argocd app diff payments-api

argocd app sync payments-api

argocd app wait payments-api --health --timeout 180
```

Finally, write the operational note that would belong in the pull request. The note should say that `/spec/replicas` is
ignored because HPA owns that field, pruning is disabled until production deletion review is implemented, and self-heal
remains enabled for all other declared fields. That explanation aligns code, review, and incident response. It also gives
the next on-call engineer a reason not to "fix" the ignore rule by removing it during a future red dashboard moment.

This worked example models the process you should use in the hands-on exercise: identify the source of drift, decide
whether ArgoCD should own the differing field, change the smallest relevant policy, and verify with both ArgoCD and
Kubernetes commands. The point is not to memorize one ignore rule. The point is to practice ownership-aware reconciliation.

---

## Did You Know?

- **ArgoCD can render several source styles before applying anything**: plain YAML, Helm charts, Kustomize overlays,
  Jsonnet, and configured plugins all become Kubernetes manifests before comparison.
- **[Application health is not the same as sync status](https://argo-cd.readthedocs.io/en/stable/user-guide/status-badge/)**: an app can be Synced because manifests match and still be Degraded
  because a Deployment, Job, or custom resource reports unhealthy state.
- **ApplicationSets create Application resources, not workload resources directly**: the generated Applications then
  perform their own reconciliation against clusters and namespaces.
- **Project restrictions protect both clusters and teams**: source allowlists, destination allowlists, and resource kind
  limits prevent one team's repository from becoming another team's deployment control plane.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Approach |
|---------|--------------|-----------------|
| Enabling `prune: true` on production before deletion review exists | A Git deletion can become a live Kubernetes deletion without enough human scrutiny | Start with prune disabled, use orphan warnings, then enable prune only after review and rollback paths are proven |
| Treating OutOfSync as automatically bad | Expected controller-owned fields can look like drift and cause unnecessary syncs | Inspect the diff, identify the field owner, and use narrow ignore rules when another controller owns the field |
| Putting many teams in the `default` project | Repositories, namespaces, and cluster resources become too broadly accessible | Create AppProjects per team, product, or trust boundary with explicit source and destination limits |
| Using hooks for non-idempotent external changes | A retry or partial failure can leave systems outside Kubernetes in an unknown state | Keep hooks idempotent, observable, and small; move complex workflows into dedicated release automation |
| Copying Application YAML for every environment | Small differences become hard to review and easy to miss | Use Kustomize overlays, Helm values, App of Apps, or ApplicationSets where repetition has a clear template |
| Ignoring repo-server errors and changing sync policy | Render failures happen before Kubernetes apply, so sync options cannot fix them | Render manifests with ArgoCD, inspect repo-server logs, and fix source paths, chart values, or credentials |
| Giving app teams cluster-wide resource permissions by default | A normal application repository can create RBAC, CRDs, or namespaces beyond its scope | Deny cluster resources unless the app is a reviewed platform component |
| Rolling back only through the UI during GitOps incidents | Auto-sync may reapply the bad Git head and the audit trail becomes confusing | Prefer Git revert, pause automation only when needed, then sync and restore policy deliberately |

---

## Quiz

### Question 1

Your team uses ArgoCD for a production API. The UI shows `OutOfSync` because live replicas are eight while Git declares
three. You also find an HPA for the same Deployment. What should you check and change before pressing Sync?

<details>
<summary>Show Answer</summary>

Check whether the HPA is intentionally managing `/spec/replicas` and whether current traffic requires the higher replica
count. If the HPA owns that field, syncing back to the Git value can reduce capacity and fight autoscaling. The better
fix is to remove replica ownership from Git or add a narrow `ignoreDifferences` rule for `/spec/replicas` on that specific
Deployment. Keep self-heal enabled for other fields so ArgoCD still enforces image, config, labels, and probes.
</details>

### Question 2

A developer proposes enabling automated sync with `prune: true` for a production Application that manages Deployments,
Services, ConfigMaps, and PVC-backed StatefulSets. The team has no deletion review process yet. How do you evaluate the
proposal?

<details>
<summary>Show Answer</summary>

Reject or defer automatic pruning for that production app until deletion controls exist. Automated sync with self-heal may
be reasonable for stateless configuration, but pruning can delete resources that disappeared from Git. For PVC-backed or
stateful workloads, the blast radius is higher. A safer path is `prune: false`, `selfHeal: true`, orphan warnings, CODEOWNERS
on production paths, staging validation, and a documented manual prune process before any production opt-in.
</details>

### Question 3

Your ArgoCD Application fails before any Kubernetes resource is created. The error mentions Kustomize cannot find a patch
target. Another engineer suggests adding `CreateNamespace=true`. What should you do instead?

<details>
<summary>Show Answer</summary>

Treat it as a render problem, not a namespace problem. `CreateNamespace=true` helps only when manifests render successfully
and the destination namespace does not exist. A Kustomize patch target error means repo-server cannot produce valid desired
manifests. Run `argocd app manifests <app>`, inspect repo-server logs, verify the Application `source.path`, and fix the
Kustomize base, overlay, patch target name, or namePrefix behavior.
</details>

### Question 4

A platform team wants every registered staging cluster to receive the same logging addon, but production clusters must
opt in one at a time. Which ApplicationSet generator strategy would you recommend?

<details>
<summary>Show Answer</summary>

Use the `clusters` generator with labels for staging clusters, because staging deployment is intentionally tied to cluster
registration metadata. For production, use an explicit `list` generator or a more restrictive label that is applied only
after review. This keeps staging automated while making production opt-in visible. The key is recognizing that cluster
labels become deployment policy when the clusters generator is used.
</details>

### Question 5

A shared ArgoCD instance lets Team A create an Application that points to Team B's namespace, even though Git review is
working correctly. Which ArgoCD boundary is missing or too broad?

<details>
<summary>Show Answer</summary>

The AppProject boundary is missing or too broad. Git review controls repository changes, but AppProjects control which
sources, destinations, and resource kinds an Application may use. Create separate projects for Team A and Team B, restrict
Team A to Team A repositories and namespaces, and map SSO groups to project-scoped roles. Instance RBAC alone is not enough
if the project allows broad destinations.
</details>

### Question 6

During an incident, someone disables auto-sync and manually patches a Deployment to restore service. The incident ends,
but the Application remains manually changed for several days. What recovery sequence should the team follow?

<details>
<summary>Show Answer</summary>

First capture the live fix and decide whether it belongs in Git. If it does, commit the equivalent manifest change or
revert the bad Git change. Then run `argocd app diff` to confirm the intended reconciliation, sync the app, wait for health,
and re-enable the appropriate automated policy. Leaving auto-sync disabled and drift undocumented defeats the GitOps model
and makes the next reconciliation surprising.
</details>

### Question 7

A matrix ApplicationSet combines all app directories with all clusters. A pull request renames a directory under `apps/`
and the preview shows generated Application names changing. What risk should reviewers focus on?

<details>
<summary>Show Answer</summary>

Reviewers should focus on whether the rename deletes old generated Applications and creates new ones, especially if pruning
or finalizers are involved. With matrix generators, a small Git structure change can multiply across clusters. The review
should render or preview generated Applications, verify whether resource ownership changes, and require an explicit migration
plan if old app names must be preserved or retired safely.
</details>

### Question 8

An Application is Synced but Degraded after a rollout. The Git diff is clean, and ArgoCD successfully applied all manifests.
Where should you investigate next, and why?

<details>
<summary>Show Answer</summary>

Investigate Kubernetes workload health rather than Git drift. Synced means desired and live manifests match; Degraded means
a resource reports unhealthy state. Check Deployment conditions, Pod events, logs, readiness probes, image pull status, and
dependent services. The fix is likely in workload behavior or configuration, not in ArgoCD sync policy.
</details>

---

## Hands-On Exercise

### Scenario: Build and Diagnose a Safe ArgoCD Delivery Flow

You are onboarding a small application into ArgoCD. The team wants automated self-healing for manual drift, but production
deletions are not mature enough for automatic pruning. Your job is to install ArgoCD in a local cluster, create a staging
Application from a public Git repository, inspect sync and health state, simulate safe drift, and document the policy
decision you would use before production.

### Step 1: Create the Lab Cluster and Install ArgoCD

Create a fresh kind cluster, install ArgoCD, and log in through a local port-forward. These commands assume the CLI tools
listed in the prerequisites are installed.

```bash
kind create cluster --name argocd-module-21

alias k=kubectl

k create namespace argocd

k apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

k -n argocd wait \
  --for=condition=ready pod \
  -l app.kubernetes.io/name=argocd-server \
  --timeout=180s

ARGOCD_PASSWORD="$(
  k -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath="{.data.password}" | base64 -d
)"

k -n argocd port-forward svc/argocd-server 8080:443 > /tmp/argocd-module-21-port-forward.log 2>&1 &

argocd login 127.0.0.1:8080 \
  --username admin \
  --password "$ARGOCD_PASSWORD" \
  --insecure
```

Success criteria:

- [ ] `kind get clusters` includes `argocd-module-21`.
- [ ] `k -n argocd get pods` shows ArgoCD pods running or completed.
- [ ] `argocd app list` connects successfully without authentication errors.

### Step 2: Create an Application With Conservative Automation

Create an Application from the public ArgoCD example repository. Keep `selfHeal: true` so manual drift is corrected, but
keep `prune: false` because this exercise models a team that has not yet completed deletion-safety review.

```bash
cat > /tmp/guestbook-staging.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook-staging
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: guestbook-staging
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

k apply -f /tmp/guestbook-staging.yaml

argocd app get guestbook-staging

argocd app sync guestbook-staging

argocd app wait guestbook-staging --health --timeout 180
```

Success criteria:

- [ ] `argocd app get guestbook-staging` shows the expected repository and path.
- [ ] The Application reaches `Synced` after sync.
- [ ] The Application reaches `Healthy` or provides a clear Kubernetes reason if your local environment is still pulling images.
- [ ] `k -n guestbook-staging get all` shows resources created in the destination namespace.

### Step 3: Inspect Rendered Desired State and Live State

Before simulating drift, collect what ArgoCD thinks it should apply and what Kubernetes is actually running. The goal is
to practice evidence gathering rather than relying only on the UI status badge.

```bash
argocd app manifests guestbook-staging > /tmp/guestbook-desired.yaml

k -n guestbook-staging get all

k -n guestbook-staging get deployment -o yaml > /tmp/guestbook-live-deployments.yaml

argocd app diff guestbook-staging || true
```

Success criteria:

- [ ] `/tmp/guestbook-desired.yaml` contains rendered Kubernetes manifests.
- [ ] You can identify at least one Deployment or Service that came from the Git source.
- [ ] You can explain whether any diff shown is expected or actionable.

### Step 4: Simulate Manual Drift and Watch Self-Heal

Patch a live resource manually, then observe how ArgoCD responds. This demonstrates the value and risk of self-healing:
the cluster returns to Git intent, but any emergency manual change would also be reverted unless automation is paused.

```bash
DEPLOYMENT_NAME="$(
  k -n guestbook-staging get deployment \
    -o jsonpath='{.items[0].metadata.name}'
)"

k -n guestbook-staging scale deployment "$DEPLOYMENT_NAME" --replicas=2

argocd app diff guestbook-staging || true

sleep 45

k -n guestbook-staging get deployment "$DEPLOYMENT_NAME"

argocd app get guestbook-staging
```

Success criteria:

- [ ] You can see the manual replica change before reconciliation or explain why reconciliation happened quickly.
- [ ] ArgoCD returns the live state toward Git because `selfHeal` is enabled.
- [ ] You can state when this behavior is desirable and when it should be paused during an incident.

### Step 5: Evaluate Prune Policy Before Production

Now inspect the Application policy and write the production decision you would put in a pull request. You do not need to
enable pruning in this lab. The point is to practice a senior review habit: deletion automation should be justified, not
enabled by default.

```bash
k -n argocd get application guestbook-staging -o yaml > /tmp/guestbook-application.yaml

grep -n "prune" /tmp/guestbook-application.yaml

cat > /tmp/guestbook-production-review-note.txt <<'EOF'
Production policy decision:
- Keep selfHeal enabled for stateless drift correction.
- Keep prune disabled until deletion review, CODEOWNERS, and staging validation exist.
- Use orphaned resource warnings to detect cleanup needs before allowing automatic deletion.
- Revisit prune after the team demonstrates safe recovery from a deleted manifest in staging.
EOF

cat /tmp/guestbook-production-review-note.txt
```

Success criteria:

- [ ] The Application manifest shows `prune: false`.
- [ ] Your review note explains the difference between self-heal and prune.
- [ ] Your review note includes at least one guardrail required before production pruning.
- [ ] Your decision is based on blast radius, not on whether automation feels convenient.

### Step 6: Clean Up

Remove the lab cluster when you are finished.

```bash
kind delete cluster --name argocd-module-21
```

Success criteria:

- [ ] `kind get clusters` no longer lists `argocd-module-21`.
- [ ] You preserved any notes you need outside the deleted cluster.
- [ ] You can describe the complete flow from Git source to rendered manifests to live cluster state.

---

## Next Module

Continue to [Module 2.2: Argo Rollouts](../module-2.2-argo-rollouts/) where you will extend GitOps delivery with canary,
blue-green, analysis, and progressive promotion strategies.

## Sources

- [Argo CD Architectural Overview](https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/) — Backs Argo CD component architecture and responsibilities such as API server, repository server, application controller, Git polling/reconciliation, sync, rollback, auth delegation, and RBAC enforcement.
- [argo-cd.readthedocs.io: release 3.1](https://argo-cd.readthedocs.io/en/release-3.1/) — General lesson point for an illustrative rewrite.
- [Introduction to ApplicationSet Controller](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/) — Covers ApplicationSet concepts, generators, monorepo patterns, and multi-cluster app generation.
- [Argo CD RBAC Configuration](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/) — Explains Argo CD RBAC, built-in roles, SSO group mapping, and project-scoped access control.
- [argo-cd.readthedocs.io: getting started](https://argo-cd.readthedocs.io/en/stable/getting_started/) — The getting-started guide shows the stable-manifest install and explicitly recommends a pinned version for production.
- [argo-cd.readthedocs.io: application specification](https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/) — The Application specification reference directly defines these fields and notes that `repoURL` may target Git or Helm sources.
- [argo-cd.readthedocs.io: auto sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/) — The automated-sync documentation directly defines auto-sync, self-heal, and automatic pruning behavior.
- [argo-cd.readthedocs.io: sync options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/) — The sync-options documentation explicitly defines `PruneLast=true` as a final implicit sync wave after resources become healthy.
- [argo-cd.readthedocs.io: sync waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/) — The sync-phases-and-waves reference directly defines the hook lifecycle and the lowest-to-highest sync-wave ordering model.
- [argo-cd.readthedocs.io: cluster bootstrapping](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/) — The cluster-bootstrapping guide documents the App of Apps pattern and warns that it is an admin-only capability.
- [argo-cd.readthedocs.io: projects](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/) — The projects guide directly lists these restriction types and explains that the default project initially allows any repo, cluster, and kind.
- [argo-cd.readthedocs.io: status badge](https://argo-cd.readthedocs.io/en/stable/user-guide/status-badge/) — The status-badge documentation explicitly describes health status and sync status as separate application status dimensions.
