---
revision_pending: false
title: "Module 1.5: CRDs & Operators - Extending Kubernetes"
slug: k8s/cka/part1-cluster-architecture/module-1.5-crds-operators
sidebar:
  order: 6
lab:
  id: cka-1.5-crds-operators
  url: https://killercoda.com/kubedojo/scenario/cka-1.5-crds-operators
  duration: "40 min"
  difficulty: advanced
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - New to CKA 2025
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: Module 1.1 (Control Plane understanding)

---

## Learning Outcomes

After this module, you will be able to:

- **Design** a Custom Resource Definition with schema validation, scope, printer columns, and subresources that fit a real operational purpose.
- **Debug** CRD discovery, API group, version, validation, and deletion problems using `kubectl` and Kubernetes API metadata.
- **Implement** an operator-style reconciliation loop that turns a custom resource into ordinary Kubernetes objects.
- **Evaluate** when a CRD and operator are better than built-in resources, Helm values, or plain configuration files.
- **Diagnose** operator reconciliation failures by inspecting custom resource status, events, controller pods, and RBAC boundaries.

## Why This Module Matters

Exercise scenario: your platform team wants application teams to request TLS certificates, monitoring targets, and small databases without opening tickets for every supporting object. The teams do not want to learn every Secret, Service, StatefulSet, and certificate challenge detail, but the cluster still needs validation, auditability, RBAC, and repeatable operations. A Custom Resource Definition gives the API server a new resource type, and an operator gives that resource type behavior.

This is the same extension model behind widely used Kubernetes tools such as cert-manager, the Prometheus Operator, Argo CD, Istio, and many storage and database operators. Those tools do not ask the Kubernetes project to add a built-in `Certificate`, `ServiceMonitor`, or `PostgreSQL` kind. They register those kinds through CRDs, then run controllers that watch the new resources and reconcile ordinary Kubernetes objects until the cluster matches the desired state.

For the CKA, the point is not to become an operator author in one lesson. The point is to recognize what happens when the API grows beyond Pods and Deployments, know how to inspect the new types, and separate storage from behavior. A CRD by itself stores and validates data; an operator watches that data and acts on it. Confusing those two ideas is the fastest path to mystery failures during installation, upgrades, and incident response.

Think of Kubernetes like a public building with a front desk. Built-in resources are standard request forms the staff already knows how to process: Pod, Service, Deployment, ConfigMap. A CRD adds a new form to the desk, such as Certificate or Database. An operator is the trained staff member who reads that form, orders the right materials, checks progress, and updates the requester when the work is complete.

This module also matters because CRDs are often the first place where platform engineering becomes visible to application teams. A platform team can expose a small, stable API that says "I need a certificate for this DNS name" or "I need this workload monitored" while hiding the operational workflow behind the scenes. That is not merely convenience. It reduces the number of manual steps a team must remember, narrows who needs permission to touch sensitive resources, and gives the organization a consistent audit trail.

There is a cost to that power. Once a CRD is installed and teams begin committing custom resources to Git, the CRD becomes an API that people depend on. Renaming fields, changing defaults, altering scope, or removing versions can break deployments just as surely as changing a public REST API. Treat CRD design as contract design: start with the user problem, expose the smallest useful intent, and plan how the API can evolve without surprising every cluster that already stores those objects.

## Custom Resources Extend the API, Not the Scheduler

A CRD extends the Kubernetes API with a new resource type. After the CRD is accepted by the API server, the new kind participates in normal API machinery: discovery, validation, storage in etcd, watch streams, RBAC checks, `kubectl get`, `kubectl describe`, and deletion. That is powerful because clients do not need a separate database or side API to track platform intent; the cluster API becomes the shared contract.

The extension is deliberately narrow. Installing a CRD does not teach the scheduler how to place a database, does not create pods, and does not run backups. The API server stores custom resources and enforces the schema you provide. Behavior comes from a controller, often called an operator, that observes the custom resources and creates or updates other resources. **Pause and predict:** if you define a `Database` CRD and then create a `Database` object with `replicas: 3` before any operator is installed, which Kubernetes component accepts the object, and which component would have to create the database Pods or StatefulSets?

<details>
<summary>Check your prediction</summary>

The `Database` object is stored and schema-validated by the API server if it matches the CRD. No database Pods or StatefulSets appear until a controller watches that object and reconciles the requested state into ordinary workload resources.

</details>

This split is the first diagnostic branch learners should practice, because the API server can accept intent long before any domain-specific controller turns that intent into running infrastructure. If `kubectl apply` says it has no match for a kind, discovery or CRD installation is broken. If an accepted object sits idle, continue the investigation on the controller side instead of assuming the scheduler misunderstood a new kind. If the object is rejected with a field error, the CRD schema is doing its job and the manifest does not match the declared API contract.

A useful way to reason about CRDs is to compare them with ConfigMaps. Both can store structured information, and both can be read by controllers or applications. The difference is that a CRD gets its own resource identity, discovery metadata, schema, RBAC verbs, watch stream, status model, and lifecycle behavior. If the data is just configuration consumed by one application, a ConfigMap may be enough. If the data is a platform object that many users create, inspect, secure, and automate, a CRD becomes more appropriate.

Custom resources also fit Kubernetes' declarative style better than ad hoc scripts. A script can create several resources once, but it usually does not keep checking whether they still match the desired state. A custom resource can remain in the API as the long-lived statement of intent, while a controller repairs drift over time. That is the same mental model you already use with Deployments: you declare replicas, and a controller keeps working until the observed Pods match that declaration.

```
Built-in Resources:          Custom Resources (via CRDs):
├── Pod                      ├── Certificate (cert-manager)
├── Deployment               ├── Prometheus (prometheus-operator)
├── Service                  ├── PostgreSQL (postgres-operator)
├── ConfigMap                ├── VirtualService (istio)
└── ...                      └── YourOwnResource
```

Once a CRD exists, `kubectl` treats the new resource family like any other API resource. The plural name becomes the everyday command target, while short names can make interactive exploration faster. The commands below are intentionally ordinary because that is the design goal: custom resources should feel native to operators, scripts, admission policies, and humans who already know Kubernetes.

```bash
# Built-in resource
kubectl get pods

# Custom resource (after CRD is installed)
kubectl get certificates
kubectl get prometheuses
kubectl get postgresqls
```

A CRD definition has several pieces that appear again in real clusters. The API group keeps your type separate from built-in groups and from other extension projects. The version list controls which versions are served and which version is stored. The OpenAPI v3 schema tells the API server what shape valid custom resources must have. Scope determines whether instances live inside namespaces or at cluster level.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: crontabs.stable.example.com    # <plural>.<group>
spec:
  group: stable.example.com            # API group
  versions:
    - name: v1                         # API version
      served: true                     # Enable this version
      storage: true                    # Store in etcd
      schema:
        openAPIV3Schema:               # Validation schema
          type: object
          properties:
            spec:
              type: object
              properties:
                cronSpec:
                  type: string
                image:
                  type: string
                replicas:
                  type: integer
  scope: Namespaced                    # or Cluster
  names:
    plural: crontabs                   # kubectl get crontabs
    singular: crontab                  # kubectl get crontab
    kind: CronTab                      # Kind in YAML
    shortNames:
      - ct                             # kubectl get ct
```

The naming convention on `metadata.name` is not decorative. Kubernetes expects the CRD name to be the plural resource name followed by the API group, such as `crontabs.stable.example.com`. If that does not match `spec.names.plural` and `spec.group`, installation fails. This makes discovery unambiguous when many extension projects add resources with similar kinds.

The API group deserves careful naming because it becomes part of every custom resource manifest. Public projects usually use a domain they control, while internal platforms often use an internal domain or organization-specific group. Avoid generic groups such as `apps.example.com` in real production APIs unless they are only for training, because collisions and unclear ownership make later operations harder. The group should tell a future engineer where the type came from and which team owns its lifecycle.

```bash
# Apply the CRD
kubectl apply -f crontab-crd.yaml

# Verify it was created
kubectl get crd crontabs.stable.example.com

# Now you can create instances
kubectl get crontabs
# No resources found (expected - we haven't created any yet)
```

CRDs are stored in etcd like built-in resources, but the API server is still stricter than a plain key-value store. It validates objects against the schema, exposes the type through discovery, enforces RBAC on verbs such as `get` and `update`, and lets clients watch for changes. That shared machinery is why custom resources work cleanly with GitOps tools, admission controllers, audit logs, and standard operational workflows.

That shared machinery is also why CRDs should be installed through the same controlled process as other cluster APIs. A broken CRD can block application installs, and a removed CRD can delete the custom resources that depended on it. In mature clusters, CRD changes are reviewed like code, applied before the custom resources that use them, and tested during upgrades. If a chart or manifest bundle mixes CRDs and custom resources, check the installation order before assuming a later error is a controller problem.

The first custom resource instance looks like any other manifest because the CRD has made `stable.example.com/v1` and `CronTab` recognizable to the API server. The object below records desired state, not an actual running cron implementation. Without a controller, it will sit in etcd as valid declarative data, visible and editable, but not acted upon by the cluster.

```yaml
apiVersion: stable.example.com/v1
kind: CronTab
metadata:
  name: my-cron-job
  namespace: default
spec:
  cronSpec: "* * * * */5"
  image: my-awesome-cron-image
  replicas: 3
```

```bash
kubectl apply -f my-crontab.yaml
kubectl get crontabs
kubectl get ct    # Using shortName
kubectl describe crontab my-cron-job
```

Standard operations work because the custom resource is now an API resource. You can list it across namespaces, edit it, delete it, watch it, and retrieve its stored YAML. The exact verbs available still depend on RBAC, so a developer might be able to create a `Certificate` in one namespace while only platform administrators can manage a cluster-scoped issuer.

The important habit is to read the resource through both the user view and the API view. The user view asks whether the object expresses the desired outcome clearly. The API view asks which group, version, scope, schema, status, and permissions control that object. When a cluster contains many operators, the second view keeps you from treating every unfamiliar kind as mysterious. It is still Kubernetes API machinery, just extended by a project-specific contract.

```bash
# Create
kubectl apply -f crontab.yaml

# List
kubectl get crontabs -A

# Describe
kubectl describe crontab my-cron-job

# Edit
kubectl edit crontab my-cron-job

# Delete
kubectl delete crontab my-cron-job

# Watch
kubectl get crontabs -w

# Get as YAML
kubectl get crontab my-cron-job -o yaml
```

Before running the next command sequence in a practice cluster, decide which layer you expect to answer each question. **Pause and predict:** when `kubectl api-resources` lists a custom type and `kubectl describe` succeeds against one instance, have you proved that the operator is healthy, or have you only proved discovery and object inspection are working?

<details>
<summary>Check your prediction</summary>

`kubectl api-resources` proves that the API server knows the type through discovery; it does not prove the controller is healthy. `kubectl describe` on a custom resource can show the desired spec and any observed status the operator has written, so missing or stale status becomes evidence for the next troubleshooting branch.

</details>

That mental split makes CRD debugging feel much less random because every command is assigned to a specific layer before the cluster returns output.

Another practical detail is that discovery can lag briefly during installation because clients cache API resource information. If you install a CRD and immediately apply a custom resource from a script, an older client cache or an ordering issue can produce a confusing "no matches" message. Re-running discovery, applying CRDs before dependent resources, and keeping installation steps explicit are simple ways to avoid that noise. In exams, slow down and prove the type exists before chasing unrelated symptoms.

## Operators Turn Custom Resources Into Work

An operator is a controller that understands a specific domain and reconciles custom resources into real cluster changes. It watches the API, reads desired state from custom resources, compares that desired state with the actual objects in the cluster or an external system, and makes changes until the two match. The controller repeats this loop because Kubernetes is eventually consistent: pods restart, users edit objects, nodes fail, and external APIs return temporary errors.

The word operator is sometimes used loosely, but the CKA-relevant pattern is precise: CRDs define the API surface, and controllers implement the behavior. Many operators also ship RBAC, ServiceAccounts, Deployments, leader election configuration, admission webhooks, conversion webhooks, and status update logic. Those supporting pieces matter because a controller with the wrong permissions can watch resources successfully while failing to create the Deployment, Secret, or StatefulSet it is supposed to manage.

Operators are especially useful when the managed system has operational knowledge that does not fit into a static template. Databases need backups, failover, upgrades, and storage checks. Certificate systems need challenge handling, renewal timing, and external issuer communication. Monitoring systems need target discovery and generated configuration. A template can produce initial YAML, but an operator can keep interpreting intent as the world changes around it.

That does not mean every abstraction needs an operator. A controller is another running component with logs, metrics, RBAC, upgrades, and failure modes. If the desired behavior is one-time rendering, a chart or Kustomize overlay may be simpler. If the behavior must react to changes, repair drift, talk to external systems, and publish status, the operator pattern earns its complexity. The best operators reduce the operational surface exposed to users while taking responsibility for the harder moving parts.

```
┌────────────────────────────────────────────────────────────────┐
│                     Operator Pattern                            │
│                                                                 │
│   You create:                                                   │
│   ┌─────────────────────────────────────────┐                  │
│   │ apiVersion: databases.example.com/v1    │                  │
│   │ kind: PostgreSQL                        │                  │
│   │ spec:                                   │                  │
│   │   version: "15"                         │                  │
│   │   replicas: 3                           │                  │
│   │   storage: 100Gi                        │                  │
│   └─────────────────────────────────────────┘                  │
│                          │                                      │
│                          ▼                                      │
│   ┌─────────────────────────────────────────┐                  │
│   │           Operator (Controller)          │                  │
│   │                                          │                  │
│   │   Watches PostgreSQL resources           │                  │
│   │   Creates:                               │                  │
│   │   • StatefulSet with 3 replicas          │                  │
│   │   • PVCs for 100Gi storage               │                  │
│   │   • Services for connections             │                  │
│   │   • Secrets for credentials              │                  │
│   │   • ConfigMaps for configuration         │                  │
│   │                                          │                  │
│   │   Manages:                               │                  │
│   │   • Automatic failover                   │                  │
│   │   • Backups                              │                  │
│   │   • Version upgrades                     │                  │
│   └─────────────────────────────────────────┘                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

In this diagram, the custom resource is the order form and the generated Kubernetes objects are the work product. The operator is not a one-time installer like a Helm chart; it keeps watching after the first apply. If a managed Deployment is deleted, the operator may recreate it. If a desired replica count changes, the operator may update the child object. If an external certificate authority rejects a request, the operator may write that failure into status conditions.

Owner references often connect managed child objects back to the custom resource, but they are not the whole story. Operators may manage objects that cannot safely be garbage-collected, objects in other namespaces, or resources in external systems such as DNS providers and cloud APIs. That is why status, events, finalizers, and logs remain important. You need to know whether the operator intended to own the child object, whether cleanup is blocked, and whether external work completed.

The reconciliation loop is the controller's heartbeat. It starts with a watch event, reads desired and current state, calculates the difference, acts, and then waits for the next event or retry. Good controllers are idempotent, which means repeating the same reconciliation should be safe. That property is essential because watches can reconnect, retries can happen after partial work, and several resource changes can arrive while earlier work is still settling.

Reconciliation is easier to understand if you stop thinking in terms of commands and start thinking in terms of convergence. A user changes desired state. The controller notices eventually. The controller makes one or more changes. The cluster or an external system reports new observed state. The controller records that observation and decides whether more work remains. This loop may finish in seconds, or it may stay pending while waiting for storage, DNS, certificates, or human approval.

```
┌─────────────────────────────────────────────────────────────┐
│                  Reconciliation Loop                         │
│                                                              │
│   ┌─────────┐                                               │
│   │  Watch  │◄─────────────────────────────────────────┐    │
│   └────┬────┘                                          │    │
│        │ Event: PostgreSQL resource changed            │    │
│        ▼                                               │    │
│   ┌─────────┐                                          │    │
│   │  Read   │ Get current state from cluster           │    │
│   └────┬────┘                                          │    │
│        │                                               │    │
│        ▼                                               │    │
│   ┌─────────┐                                          │    │
│   │ Compare │ Current state vs. Desired state          │    │
│   └────┬────┘                                          │    │
│        │                                               │    │
│        ▼                                               │    │
│   ┌─────────┐                                          │    │
│   │  Act    │ Create/Update/Delete resources           │    │
│   └────┬────┘                                          │    │
│        │                                               │    │
│        └─────────────────────────────────────────────►─┘    │
│                  Repeat forever                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Hypothetical scenario: a `Certificate` custom resource exists, but the Secret named in `spec.secretName` never appears. The first question is not "is Kubernetes broken?" It is "which controller should reconcile this type, and can that controller see the object and write the target Secret?" You would check the CRD, the custom resource status and events, the operator Deployment, the operator logs, and the RBAC binding that gives the controller permission to manage Secrets.

What would happen if the cert-manager controller pod crashed while its CRDs remained installed? You could still create `Certificate` custom resources because the API server knows the type, validates the schema, and stores accepted objects. Existing TLS Secrets would continue to serve traffic because they are ordinary Secrets already consumed by Ingresses or workloads. New issuance and renewal would stall until the controller recovered, because no active reconciliation loop would be processing those custom resources.

This failure mode is common enough that it should become an instinct. When the API accepts an object but nothing follows, inspect the controller path. When the API rejects an object, inspect the CRD and schema path. When the child objects exist but drift back after manual edits, inspect which custom resource owns the desired state. Those three questions cover a large share of operator incidents without requiring deep knowledge of the specific product.

```bash
# Install cert-manager (includes CRDs)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Check CRDs created
kubectl get crd | grep cert-manager
# certificates.cert-manager.io
# clusterissuers.cert-manager.io
# issuers.cert-manager.io
# ...
```

The `Certificate` object below is a useful example because the custom resource is short while the actual workflow is not. A controller may need to create CertificateRequests, solve ACME challenges, update status conditions, handle retries, and write a Secret only after successful issuance. The learner-facing API stays compact because the operator hides the procedural work behind a declarative type.

```yaml
# Create a Certificate resource
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: myapp-tls
  namespace: default
spec:
  secretName: myapp-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - myapp.example.com
```

The cert-manager operator watches this Certificate and requests a certificate, completes the ACME challenge, stores the certificate in the named Secret, and renews before expiration. That list is not magic hidden inside the API server. It is controller behavior, so failures appear in the custom resource status, events, related resources, and controller logs rather than in scheduler output.

The user-facing resource is intentionally declarative. It names the Secret that should contain the certificate, references an issuer, and lists DNS names. It does not tell cert-manager how many retries to perform or which temporary resources to create for a challenge. That separation is the value of the operator pattern: the custom resource captures stable intent, while the controller can improve its implementation across releases without changing every application manifest.

The Prometheus Operator follows the same pattern with monitoring resources. A `Prometheus` custom resource declares a Prometheus instance, while `ServiceMonitor` and related resources describe scrape targets and rules. The operator watches those custom resources and produces StatefulSets, ConfigMaps, Services, and generated configuration. The result is a Kubernetes-native monitoring API rather than a pile of manually edited configuration files.

Monitoring resources also show why selectors and labels matter in operator APIs. Creating a `ServiceMonitor` does not guarantee that every Prometheus instance will select it. The Prometheus custom resource may define selectors that include only certain labels or namespaces. When scraping fails, the answer may be in the relationship between custom resources, not in the target application's Pods. Always read both sides of the declarative contract.

```bash
# Check Prometheus CRDs
kubectl get crd | grep monitoring.coreos.com
# prometheuses.monitoring.coreos.com
# servicemonitors.monitoring.coreos.com
# alertmanagers.monitoring.coreos.com
```

```yaml
# Create a Prometheus instance
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: main
  namespace: monitoring
spec:
  replicas: 2
  serviceAccountName: prometheus
  serviceMonitorSelector:
    matchLabels:
      team: frontend
```

Discovery is the skill that keeps you oriented in an unfamiliar cluster. Start from CRDs to learn which custom types exist, then move to custom resources to find instances, then locate the controller that owns those types. Namespaces are often clues: cert-manager commonly runs in `cert-manager`, monitoring stacks often run in `monitoring`, and platform teams may install operators in dedicated system namespaces.

In a real cluster, there may be dozens or hundreds of CRDs, so pattern recognition helps. Group names often identify products, such as `cert-manager.io` or `monitoring.coreos.com`. Resource names often identify the user-facing concept, such as certificates, issuers, servicemonitors, or prometheusrules. Controller pods often include the product or operator name. These clues are not proof by themselves, but together they form a fast map of which API extension belongs to which controller.

```bash
# List all CRDs in cluster
kubectl get crd

# See all custom resources of a type
kubectl get certificates -A

# Check if operator is running
kubectl get pods -A | grep operator
kubectl get pods -A | grep -E "cert-manager|prometheus"
```

## Schema, Scope, Status, and Lifecycle

Schema validation turns a CRD from loose storage into a real API contract. Without a useful schema, the API server accepts misspelled fields and nonsensical values, leaving the operator to discover bad input later. With a schema, invalid objects are rejected early, field types are documented through discovery, and clients can produce better errors. In Kubernetes 1.35 and later, structural schemas remain the expected baseline for production CRDs.

The example below adds required fields, a cron-like pattern, numeric bounds, and a default. It is still intentionally small, but it shows the mindset: put stable validation at the API boundary, then let the controller focus on behavior. Do not put every business rule into a static schema; rules that depend on external systems, current cluster state, or asynchronous work belong in admission webhooks or reconciliation status.

Good schemas reduce ambiguity for both people and machines. If a field is required, say so. If a number has safe bounds, enforce them. If a string has a small valid set, use an enum. If a field is optional but the controller assumes a default, declare that default in the CRD when appropriate. These choices make errors appear when the manifest is applied rather than minutes later in a controller log that the application team may not be allowed to read.

There is still a balance to keep. A schema that is too loose pushes every mistake into reconciliation, which makes failures slower and less predictable. A schema that is too rigid can block legitimate use cases or make version upgrades painful. For an exam scenario, focus on identifying where the rejection happens. For a real platform, review the schema with both API users and operator maintainers so the contract is useful without becoming brittle.

```yaml
schema:
  openAPIV3Schema:
    type: object
    required:
      - spec
    properties:
      spec:
        type: object
        required:
          - cronSpec
          - image
        properties:
          cronSpec:
            type: string
            pattern: '^(\d+|\*)(/\d+)?(\s+(\d+|\*)(/\d+)?){4}$'
          image:
            type: string
          replicas:
            type: integer
            minimum: 1
            maximum: 10
            default: 1
```

```bash
# This would fail validation
kubectl apply -f bad-crontab.yaml
# Error: spec.replicas: Invalid value: 15: must be <= 10
```

Additional printer columns improve the day-two experience. A custom resource might have dozens of fields, but the most useful fields should appear in `kubectl get` without forcing every operator to read YAML. This is especially helpful during exams and incidents, where you need to scan status quickly. Choose columns that help answer operational questions, not every field that exists.

Printer columns are a small feature with a large usability effect. A certificate list that shows readiness and expiration is easier to operate than one that only shows names. A backup list that shows schedule, last run, and phase is easier to triage than a YAML-only interface. If users constantly need the same `jsonpath` command, that is a signal that the CRD should expose a better column.

```yaml
versions:
  - name: v1
    additionalPrinterColumns:
      - name: Schedule
        type: string
        jsonPath: .spec.cronSpec
      - name: Replicas
        type: integer
        jsonPath: .spec.replicas
      - name: Age
        type: date
        jsonPath: .metadata.creationTimestamp
```

```bash
kubectl get crontabs
# NAME          SCHEDULE       REPLICAS   AGE
# my-cron-job   * * * * */5    3          5m
```

Subresources split responsibilities inside the same custom resource. The `status` subresource lets controllers update observed state without racing with users who edit desired state under `spec`. The `scale` subresource lets generic tooling scale a custom resource when the CRD maps the desired and observed replica paths. Before running this in a cluster, predict which user or controller should update `spec.replicas` and which one should update `status.replicas`.

The spec-status split is one of the most important Kubernetes habits to preserve in custom APIs. Users write desired state under `spec`, and controllers write observed state under `status`. When those responsibilities blur, field ownership becomes confusing and automation starts overwriting user intent. A clean status model lets users ask practical questions: has the controller seen my latest generation, what phase is it in, and what condition explains the current block?

```yaml
versions:
  - name: v1
    subresources:
      status: {}           # Enable /status subresource
      scale:               # Enable kubectl scale
        specReplicasPath: .spec.replicas
        statusReplicasPath: .status.replicas
```

```bash
# Now this works
kubectl scale crontab my-cron-job --replicas=5
```

Scope is a design decision about ownership. Namespaced custom resources fit application or team-owned intent, such as a certificate for one namespace, a database for one service, or an application deployment policy. Cluster-scoped resources fit shared infrastructure, such as a cluster issuer, storage profile, global policy, or node-level integration. The wrong scope creates either unnecessary duplication or excessive centralization.

Scope also changes the security model. Namespaced resources can usually be delegated with Roles and RoleBindings, which lets teams manage their own instances without touching other namespaces. Cluster-scoped resources need ClusterRoles and cluster-wide names, so they should represent concepts that truly cross namespace boundaries. If you are unsure, ask where ownership and blast radius belong. The answer often tells you the correct scope before any YAML is written.

```yaml
# Namespaced (default)
scope: Namespaced
# Resources exist within a namespace
# kubectl get crontabs -n myapp

# Cluster-scoped
scope: Cluster
# Resources are cluster-wide (like Nodes, PVs)
# kubectl get clusterissuers (cert-manager example)
```

| Scope | Use When | Examples |
|-------|----------|----------|
| **Namespaced** | Resource belongs to a team/app | Certificate, Database, Application |
| **Cluster** | Resource is shared/global | ClusterIssuer, StorageProfile |

Deleting a CRD is a lifecycle event, not a harmless cleanup command. Kubernetes removes the custom resource instances for that CRD because their type no longer exists. Objects created by an operator, such as Secrets or Deployments, may or may not be deleted depending on owner references, finalizers, and controller behavior. **Pause and predict:** if a CRD is deleted before the operator has removed its finalizers, what evidence would you look for to confirm which resources survived, and which evidence would be gone with the custom resource type?

<details>
<summary>Check your prediction</summary>

The custom resource instances of that type are gone because their API definition is gone. Child objects may remain, so look for terminating objects, leftover owner references, surviving Secrets, surviving Deployments, and any operator logs or events that explain how far cleanup progressed.

</details>

This is why uninstall procedures deserve the same caution as installation procedures, especially when a custom API represents stateful infrastructure rather than a disposable training object. Finalizers are another reason custom resources are more than simple YAML files. A finalizer can block deletion until a controller finishes cleanup, such as removing external cloud resources or taking a final backup. That makes deletion safer, but it also creates failure modes: if the controller is gone and the finalizer remains, the resource can stay stuck in a terminating state. The fix should be deliberate because removing a finalizer tells Kubernetes to stop waiting for cleanup.

Versioning adds one more lifecycle concern. A CRD can serve multiple versions, but one version is marked for storage. Mature APIs use this to move users gradually from one shape to another, sometimes with conversion webhooks. For CKA work, you mostly need to recognize served versions and storage versions when a manifest fails. In production, you need a migration plan before removing a served version because old manifests and automation may still depend on it.

Treat CRD backups as part of cluster recovery. Backing up etcd may preserve custom resources, but GitOps manifests are often the faster human recovery path because they show which objects should exist and why. Exporting a CRD alone is not enough; you also need the custom resource instances and the operator configuration that gives them behavior. This is especially important before uninstalling an operator, because uninstall steps may remove CRDs and therefore the custom resources they define.

## Exam-Relevant Inspection and Troubleshooting

The most reliable CRD troubleshooting sequence starts with discovery. Ask whether the type exists, which group and version it belongs to, whether it is namespaced, and which short names are available. `kubectl api-resources` answers many of these questions without forcing you to read the full CRD. When a manifest fails with "no matches for kind", compare its `apiVersion` and `kind` to discovery output before chasing controller logs.

After discovery, separate object existence from object readiness. A custom resource can exist, be syntactically valid, and still represent work that has not completed. Read `metadata.generation` and any status field that records the observed generation if the operator provides one. If the observed generation lags behind, the controller may not have processed the latest spec. If generations match but a condition is false, the operator has processed the request and is telling you why it cannot finish.

```bash
# List all CRDs
kubectl get crd

# Get details about a CRD
kubectl describe crd certificates.cert-manager.io

# See the full CRD definition
kubectl get crd certificates.cert-manager.io -o yaml
```

Custom resource inspection comes next. A successful `kubectl get` proves the object exists, but `kubectl describe` and `kubectl get -o yaml` show the fields that matter during diagnosis. Look for `status.conditions`, events, observed generation, finalizers, owner references, and whether the object is in the namespace you expect. Many mature operators use status conditions as their primary support interface.

Events are useful, but they are not a durable database of everything that happened. They can expire, and high-volume clusters can make them noisy. Status conditions tend to be more stable because they live on the object and are updated by the controller. Logs then give the controller's detailed view, especially when an external system rejects a request. Use all three sources together: events for recent hints, status for current state, and logs for controller reasoning.

```bash
# List custom resources
kubectl get <resource-name> -A

# Get specific resource
kubectl get certificate my-cert -o yaml

# Edit custom resource
kubectl edit certificate my-cert

# Delete custom resource
kubectl delete certificate my-cert
```

API discovery also helps you avoid guessing plural names. The kind may be `Certificate`, but the resource may be `certificates`; the kind may be `PrometheusRule`, but the resource name may be `prometheusrules`. The API group identifies the owning extension project, which helps you find the right documentation, controller Deployment, and RBAC rules when behavior is missing.

Plural names and short names can be deceptively important under time pressure. If a command fails because you guessed the wrong resource name, the error may look like a missing CRD even though the API is healthy. `kubectl api-resources` is faster and safer than guessing. It shows the resource name, short names, API group, namespaced status, and kind in one place, which is exactly the information you need to form the next command correctly.

```bash
# List all resource types (including custom)
kubectl api-resources

# Filter by group
kubectl api-resources --api-group=cert-manager.io

# Show if namespaced
kubectl api-resources --namespaced=true
```

A common exam trap is stopping after the CRD exists. The CRD only proves the API server can store the object. If behavior is missing, inspect the controller Deployment, its logs, its leader election status if applicable, and the permissions on its ServiceAccount. A controller can fail quietly from the learner's perspective because the custom resource still appears healthy until you inspect its status or events.

Hypothetical scenario: a team applies a `ServiceMonitor`, but Prometheus never starts scraping the service. A good diagnostic path is to verify the `servicemonitors.monitoring.coreos.com` CRD, list the `ServiceMonitor` in the right namespace, check labels against the Prometheus resource selector, inspect Prometheus Operator logs, and confirm RBAC allows the operator to read the namespace. Jumping straight to pod restarts skips the declarative contract that the operator is actually watching.

The same process works for validation failures. If the API server rejects the object, read the field path in the error and compare it with the CRD schema. If the object is accepted but the operator reports `Ready=False`, read status conditions and events. If status never changes, check whether the controller has the `update` permission on the resource's status subresource. Each symptom points to a different boundary.

RBAC failures deserve special attention because they can look like operator bugs. A controller may have permission to list custom resources but not to create a child Secret, update a status subresource, or watch resources in another namespace. The resulting error usually appears in controller logs, and sometimes in status conditions. When a custom resource stays pending with no obvious schema problem, check the ServiceAccount, Roles, ClusterRoles, and bindings that belong to the operator.

Admission webhooks can add another layer. Some operators install validating or mutating webhooks for their custom resources, so an apply can fail even when the static CRD schema looks permissive. The error message usually names the webhook, which tells you the request reached admission but was rejected by extension logic. That is different from a missing CRD and different from a reconciliation failure after storage. Place the symptom on the request path before choosing a fix.

## Patterns & Anti-Patterns

Good CRD design starts with a stable user-facing contract and hides unstable implementation details behind the controller. A learner should be able to read the custom resource and understand intent without knowing every generated child object. When the CRD mirrors every field in a Deployment or StatefulSet, it stops simplifying operations and becomes a second, less familiar API for the same problem.

Use these patterns when they make the cluster easier to operate, not merely because custom resources are available. CRDs are best when they encode reusable operational intent: certificate issuance, backup policy, database lifecycle, monitoring target discovery, or a platform-specific application abstraction. The operator then owns the procedural work that humans would otherwise repeat and forget during stressful moments.

A strong pattern is to design from the runbook backward. If an on-call engineer needs to answer whether a backup is scheduled, last completed, currently failing, or blocked by credentials, those answers should appear in fields, status conditions, printer columns, or related events. The CRD is not just a developer input format; it is also an operations surface. That perspective produces APIs that are easier to debug after the original author has moved on.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Intent-focused CRD | Teams need a simple resource such as `Certificate`, `Database`, or `BackupPolicy` | The CRD describes the desired outcome while the operator handles details | Keep the spec small and version it carefully as usage grows |
| Status conditions | Users need to diagnose asynchronous work | Conditions expose observed state without changing desired state | Standardize condition names so dashboards and runbooks stay consistent |
| Namespaced ownership | Application teams own instances independently | RBAC and quotas can follow namespace boundaries | Provide cluster-scoped templates or issuers for shared defaults |
| Printer columns | Operators need fast `kubectl get` triage | Important fields appear in lists without reading full YAML | Avoid exposing volatile internals that change every reconcile loop |

Anti-patterns usually come from treating CRDs as either too magical or too trivial. They are not magic because a controller must still reconcile behavior. They are not trivial because once a CRD is widely used, changing schema, versions, and deletion behavior becomes API maintenance. A careless CRD can create long-lived operational debt because every GitOps repo, script, and user's muscle memory depends on it.

Another anti-pattern is hiding all errors in controller logs. Logs are necessary for maintainers, but API users should not need cluster-admin access to learn why their object is not ready. Status conditions, events, and clear validation messages move the failure closer to the person who can fix the manifest. This is why mature operators invest heavily in status design: it converts asynchronous work into a supportable API conversation.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| CRD without controller for behavior | Users create valid objects that never affect workloads | Either install the operator or document the CRD as data-only |
| Overloaded spec fields | The CRD becomes a copy of every underlying Kubernetes object | Expose intent and let the controller choose implementation details |
| No status subresource | Controllers and users race over the same object fields | Enable `status` and put observed state under `.status` |
| Unsafe CRD deletion | All custom resources of that type disappear unexpectedly | Back up manifests, delete instances intentionally, and understand finalizers |

## Decision Framework

Choosing a CRD is an API design decision. Use one when the resource represents a durable concept in your platform, users need Kubernetes-native workflows, and a controller can reliably turn desired state into observed state. Avoid one when a simpler built-in resource, Helm chart value, ConfigMap, or documentation convention solves the problem without introducing a new API surface and lifecycle.

The question "could we build this as a CRD?" is less useful than "who benefits from this becoming an API?" If one team applies one manifest twice a year, a CRD may be ceremony. If many teams repeat a risky sequence every week, a CRD plus operator can remove toil and reduce mistakes. The stronger the operational knowledge behind the workflow, the stronger the case for an operator rather than a static template.

```
Need a new Kubernetes-facing abstraction?
        |
        v
Is the desired state durable and reusable across teams?
        |-- no --> Prefer built-in resources, Helm values, or a ConfigMap.
        |
       yes
        v
Does something need to reconcile or validate asynchronous work?
        |-- no --> A CRD may be data-only, but document that clearly.
        |
       yes
        v
Can you operate the controller, RBAC, upgrades, and status model?
        |-- no --> Use an existing operator or narrow the problem first.
        |
       yes
        v
Design a CRD with schema, scope, status, printer columns, and versioning.
```

The decision should also include who will be on call. A custom API can make application teams faster, but the platform team now owns API compatibility, controller health, upgrade paths, and documentation. If the abstraction saves ten teams from repeating risky manual procedures, that tradeoff is often worth it. If it hides two YAML fields behind a new controller, the operational cost usually outweighs the benefit.

Use the following final test before introducing a new custom API: can you explain the desired state in one or two sentences, can you validate the safest parts at admission time, can you expose progress through status, and can you recover if the controller is unavailable? If the answer is yes, you likely have a real Kubernetes extension. If the answer is no, narrow the API or choose a simpler mechanism until ownership is clearer.

| Choice | Use It When | Avoid It When |
|--------|-------------|---------------|
| Built-in resource | Kubernetes already models the thing directly | Users need a domain concept that spans several resources |
| Helm values | Installation-time templating is enough | The desired state must be watched and reconciled after install |
| ConfigMap | Consumers only need static configuration | You need validation, status, RBAC by resource type, or watches |
| CRD plus operator | The platform needs a durable API and active reconciliation | No team can own controller operations and version compatibility |

## Did You Know?

- Kubernetes added CRDs as the stable replacement for the older ThirdPartyResource extension mechanism, and `apiextensions.k8s.io/v1` has been the normal production API for years.
- A CRD can serve several versions while storing one version, which lets API authors migrate clients gradually instead of breaking every manifest at once.
- Operator SDK, Kubebuilder, and controller-runtime all build on the same Kubernetes watch and reconcile ideas, even though they package scaffolding differently.
- Finalizers are ordinary strings in metadata, but they can block deletion until a controller removes them after cleanup.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Creating a custom resource before the CRD | The API server has no registered kind or discovery entry yet | Install the CRD first, then reapply the custom resource after discovery updates |
| Using the wrong API group or version | Manifests are copied from another operator release or old documentation | Check `kubectl api-resources` and `kubectl get crd <name> -o yaml` for the served versions |
| Expecting a CRD to create workloads by itself | The CRD stores desired state, but no reconciliation logic is running | Install and verify the operator controller, then inspect custom resource status |
| Deleting a CRD before deleting instances | The type and its custom resources are removed together | Export or back up instances, delete them intentionally, and understand finalizers before CRD removal |
| Assuming every custom resource is namespaced | Some platform resources are cluster-scoped and ignore `-n` | Check `kubectl api-resources --namespaced=false` or read `spec.scope` on the CRD |
| Ignoring status conditions | Operators often report useful failures on the custom resource, not only in logs | Use `kubectl describe` and inspect `.status.conditions`, events, and observed generation |
| Granting the operator broad cluster-admin permissions | It is faster during installation but risky during incidents and audits | Use the documented RBAC, then narrow permissions to the resources and subresources it reconciles |
| Changing CRD schemas casually | Existing manifests, GitOps pipelines, and stored objects depend on the API contract | Version the API, provide conversion or migration guidance, and test upgrades before rollout |

## Quiz

<details>
<summary>1. Your team applies a `Database` custom resource and it is accepted, but no StatefulSet appears. What do you check first, and why?</summary>

Start by proving which layer is working. The accepted custom resource means the CRD exists and the API server can store the object, so the next checks are the operator Deployment, its logs, its ServiceAccount permissions, and the custom resource status or events. A CRD alone does not create a StatefulSet, so repeatedly editing the custom resource is unlikely to help until a controller is watching and reconciling it. If status is empty, also check whether the controller has permission to update the status subresource.

</details>

<details>
<summary>2. A manifest fails with `no matches for kind "Certificate" in version "cert-manager.io/v1"`. How would you debug the API side before investigating cert-manager logs?</summary>

First run `kubectl get crd | grep cert-manager` and `kubectl api-resources --api-group=cert-manager.io` to confirm the CRD is installed and serving the expected version. If the CRD is missing, install or repair cert-manager before applying the resource. If the group exists but the version differs, update the manifest to a served version or upgrade the CRD according to the vendor documentation. Controller logs are secondary here because the API server rejected the object before any controller could reconcile it.

</details>

<details>
<summary>3. A platform engineer proposes a cluster-wide `BackupPolicy` CRD but sets `scope: Namespaced`. What operational problems should you raise?</summary>

Namespaced scope would force every namespace to duplicate what is meant to be a shared policy, increasing drift and making audit results harder to interpret. It also changes RBAC and command behavior because users would need namespace-specific permissions and `kubectl` commands. If the policy truly governs the whole cluster, `scope: Cluster` is the clearer API, with ClusterRoles and globally unique names. If teams need local overrides, use a separate namespaced resource or fields that reference a cluster-scoped policy.

</details>

<details>
<summary>4. You delete `certificates.cert-manager.io` while many `Certificate` resources exist. What survives, what is lost, and what recovery path is realistic?</summary>

Deleting the CRD removes the custom resources of that type because the API type is gone. Secrets already written by cert-manager may continue to exist and keep serving existing TLS traffic, but the desired certificate objects and renewal intent are gone. Recovery usually means reinstalling the CRD and recreating the `Certificate` manifests from Git or backup. This is why CRD deletion should be treated as API removal, not ordinary cleanup.

</details>

<details>
<summary>5. A `CronTab` custom resource is rejected because `spec.replicas` is `15`, but the team insists the operator could handle that value. Where should the fix be made?</summary>

The rejection happened at the API validation boundary, so the manifest or CRD schema must change before the operator is involved. If replicas above `10` are truly valid, update the CRD schema through a planned API change and test stored objects and clients. If the limit is intentional, the team should correct the custom resource to fit the contract. Operators should not be expected to reconcile objects the API server refuses to store.

</details>

<details>
<summary>6. Prometheus is not scraping a service after a `ServiceMonitor` is created. Which CRD and operator-specific clues help you diagnose the problem?</summary>

Confirm that the `servicemonitors.monitoring.coreos.com` CRD exists and the `ServiceMonitor` is in the namespace expected by the Prometheus resource. Then compare labels and selectors between the `ServiceMonitor` and the `Prometheus` custom resource because the operator may only select monitors with matching labels. Inspect the Prometheus Operator logs and the status of related resources for reconciliation errors. This path checks the declarative link before assuming the workload pods are the problem.

</details>

<details>
<summary>7. An operator-managed Deployment is manually scaled from two replicas to five, but later returns to two. What does this tell you about reconciliation?</summary>

It shows that the operator treats the custom resource as the source of truth and repairs drift in child resources. Manual changes to generated objects may appear to work briefly, but the next reconciliation loop compares actual state with desired state and updates the child object back to the declared value. The durable fix is to edit the custom resource field that controls replicas, if the CRD exposes one. This is expected behavior, not the Deployment controller fighting the user by itself.

</details>

## Hands-On Exercise

In this exercise you will create a small CRD, create custom resources, inspect discovery, add validation concepts, and run a simple educational operator loop. The shell examples are designed for a disposable Kubernetes cluster. They create local files in your current directory and remove them during cleanup, so run them from a scratch workspace rather than inside an application repository.

Read each task as a miniature troubleshooting lab, not just a typing exercise. After each apply, ask which component accepted the request and which component, if any, is expected to act on it. When an object does not appear, use discovery. When an object is rejected, use schema errors. When an object exists but nothing else changes, use the controller path. That repetition is the point of the lab.

### Task 1: Create a Website CRD

Create a `Website` resource that records a URL and a replica count. This first CRD does not run a website by itself; it gives the API server a new type and lets you practice discovery and validation. Notice that the schema requires `spec.url`, while `spec.replicas` has a default.

```bash
cat > website-crd.yaml << 'EOF'
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: websites.stable.example.com
spec:
  group: stable.example.com
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              required:
                - url
              properties:
                url:
                  type: string
                replicas:
                  type: integer
                  default: 1
      additionalPrinterColumns:
        - name: URL
          type: string
          jsonPath: .spec.url
        - name: Replicas
          type: integer
          jsonPath: .spec.replicas
        - name: Age
          type: date
          jsonPath: .metadata.creationTimestamp
  scope: Namespaced
  names:
    plural: websites
    singular: website
    kind: Website
    shortNames:
      - ws
EOF

kubectl apply -f website-crd.yaml
```

```bash
kubectl get crd websites.stable.example.com
kubectl api-resources | grep website
```

<details>
<summary>Solution notes</summary>

The CRD should appear as `websites.stable.example.com`, and `kubectl api-resources` should show the `websites` resource with the short name `ws`. If discovery does not show it, inspect the CRD installation error before creating instances. The API server must know the type before it can accept a `Website` object.

</details>

### Task 2: Create and Inspect Custom Resources

Create one `Website` instance, then use the plural, singular, and short-name forms to inspect it. This task is intentionally about API behavior, not website hosting. The object records desired state and becomes visible to standard Kubernetes tooling.

```bash
cat > my-website.yaml << 'EOF'
apiVersion: stable.example.com/v1
kind: Website
metadata:
  name: company-site
  namespace: default
spec:
  url: https://example.com
  replicas: 3
EOF

kubectl apply -f my-website.yaml
```

```bash
# List websites
kubectl get websites
kubectl get ws    # Short name

# Describe
kubectl describe website company-site

# Get as YAML
kubectl get website company-site -o yaml

# Edit
kubectl edit website company-site
```

```bash
cat > blog.yaml << 'EOF'
apiVersion: stable.example.com/v1
kind: Website
metadata:
  name: blog
spec:
  url: https://blog.example.com
  replicas: 2
EOF

kubectl apply -f blog.yaml
kubectl get ws
```

<details>
<summary>Solution notes</summary>

Both `company-site` and `blog` should appear with the custom printer columns if your cluster has accepted the CRD exactly as written. If the output does not show the columns, check that `additionalPrinterColumns` is nested under the served version. If `kubectl get ws` fails, verify that `shortNames` was accepted in the CRD.

</details>

### Task 3: Explore Installed Operators and CRDs

Use discovery commands to identify any operator-managed APIs already present in your cluster. A small practice cluster may not have cert-manager or Prometheus installed, so a missing result is not automatically a failure. The point is to practice moving from CRD names to resource instances and then to likely controller pods.

```bash
# Check for cert-manager
kubectl get crd | grep cert-manager

# Check for prometheus operator
kubectl get crd | grep monitoring.coreos.com

# List all CRDs
kubectl get crd
```

```bash
# List all CRDs
kubectl get crd

# Get details on a specific CRD
kubectl get crd <crd-name> -o yaml | head -50

# List instances of a CRD
kubectl get <resource-name> -A

# Describe a CRD
kubectl describe crd <crd-name>
```

<details>
<summary>Solution notes</summary>

For an installed operator, you should be able to connect at least three clues: the CRD group, one or more custom resources, and a controller pod or Deployment. For example, cert-manager resources use the `cert-manager.io` group, while Prometheus Operator resources use `monitoring.coreos.com`. If no common operators are installed, use your `Website` CRD for the same discovery process.

</details>

### Task 4: Build Validation and Status Examples

Create a second simple CRD that validates database fields. Then create an invalid resource and a valid one so you can see the difference between API validation failure and successful storage. After that, create a tiny `Task` CRD with a status subresource so you can inspect how status is modeled even when no controller updates it.

```bash
# Create CRD
cat << 'EOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: apps.example.com
spec:
  group: example.com
  names:
    kind: App
    listKind: AppList
    plural: apps
    singular: app
    shortNames:
      - ap
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                image:
                  type: string
                replicas:
                  type: integer
EOF

# Verify CRD exists
kubectl get crd apps.example.com

# Create an instance
cat << 'EOF' | kubectl apply -f -
apiVersion: example.com/v1
kind: App
metadata:
  name: my-app
spec:
  image: nginx:1.25
  replicas: 3
EOF

# Query using short name
kubectl get ap

# Cleanup
kubectl delete app my-app
kubectl delete crd apps.example.com
```

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databases.stable.example.com
spec:
  group: stable.example.com
  names:
    kind: Database
    plural: databases
    singular: database
    shortNames:
      - db
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          required:
            - spec
          properties:
            spec:
              type: object
              required:
                - engine
                - version
              properties:
                engine:
                  type: string
                  enum:
                    - postgres
                    - mysql
                    - mongodb
                version:
                  type: string
                storage:
                  type: string
                  default: "10Gi"
EOF

# Try to create invalid resource (should fail)
cat << 'EOF' | kubectl apply -f -
apiVersion: stable.example.com/v1
kind: Database
metadata:
  name: invalid-db
spec:
  engine: oracle  # Not in enum!
  version: "14"
EOF

# Create valid resource
cat << 'EOF' | kubectl apply -f -
apiVersion: stable.example.com/v1
kind: Database
metadata:
  name: prod-db
spec:
  engine: postgres
  version: "14"
EOF

# Cleanup
kubectl delete database prod-db
kubectl delete crd databases.stable.example.com
```

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: tasks.work.example.com
spec:
  group: work.example.com
  names:
    kind: Task
    plural: tasks
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      subresources:
        status: {}
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                command:
                  type: string
            status:
              type: object
              properties:
                phase:
                  type: string
                completedAt:
                  type: string
EOF

# Create task
cat << 'EOF' | kubectl apply -f -
apiVersion: work.example.com/v1
kind: Task
metadata:
  name: build-job
spec:
  command: "make build"
EOF

# View the task
kubectl get task build-job -o yaml

# Cleanup
kubectl delete task build-job
kubectl delete crd tasks.work.example.com
```

<details>
<summary>Solution notes</summary>

The invalid `Database` should be rejected before storage because `oracle` is not in the enum. The valid object should be stored and listed. The `Task` object should show a `status` field only if something writes it, but the CRD now exposes a status subresource that a controller could update separately from user-managed `spec`.

</details>

### Task 5: Diagnose a Missing CRD and Design a Backup CRD

Apply a resource for a type that does not exist, observe the failure, and then design a `Backup` CRD with required fields. This mirrors the most common first failure when installing operator-managed applications from incomplete manifests: the custom resource is applied before the CRD.

```bash
# Try to create a resource for non-existent CRD
cat << 'EOF' | kubectl apply -f -
apiVersion: nonexistent.example.com/v1
kind: Widget
metadata:
  name: test
spec:
  size: large
EOF

# Error: no matches for kind "Widget"

# Diagnose
kubectl get crd | grep widget  # Nothing
kubectl api-resources | grep -i widget  # Nothing

# Solution: CRD must be created before resources
# Create the CRD first, then the resource
```

Design and implement a CRD for a `Backup` resource with group `backup.example.com`, required fields `source`, `destination`, and `schedule`, an optional integer `retention` defaulting to seven days, and schedule validation as a string field. Then create a sample `Backup` resource and query it through its short name.

```bash
# YOUR TASK: Create the CRD and a sample Backup resource
```

<details>
<summary>Solution</summary>

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backups.backup.example.com
spec:
  group: backup.example.com
  names:
    kind: Backup
    plural: backups
    shortNames:
      - bk
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          required:
            - spec
          properties:
            spec:
              type: object
              required:
                - source
                - destination
                - schedule
              properties:
                source:
                  type: string
                destination:
                  type: string
                schedule:
                  type: string
                retention:
                  type: integer
                  default: 7
EOF

cat << 'EOF' | kubectl apply -f -
apiVersion: backup.example.com/v1
kind: Backup
metadata:
  name: daily-db-backup
spec:
  source: /data/postgres
  destination: s3://backups/postgres
  schedule: "0 2 * * *"
  retention: 14
EOF

kubectl get bk
kubectl delete backup daily-db-backup
kubectl delete crd backups.backup.example.com
```

</details>

### Task 6: Run a Basic Educational Operator

This final task uses a Bash loop as an educational controller for the `Website` CRD. It is not a production operator, but it makes reconciliation visible: the loop lists custom resources, reads their desired state, and applies a Deployment named after each website. After you delete the managed Deployment, the loop recreates it from the custom resource.

```bash
# 1. First, create the Website CRD
cat << 'EOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: websites.stable.example.com
spec:
  group: stable.example.com
  scope: Namespaced
  names:
    plural: websites
    singular: website
    kind: Website
    shortNames: [ws]
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                image: {type: string, default: "nginx:alpine"}
                replicas: {type: integer, default: 1}
EOF

# 2. Create the Operator Script
# This represents the controller's reconciliation loop
cat << 'EOF' > website-operator.sh
#!/bin/bash
echo "Starting Website Operator..."
while true; do
  # Find all Website custom resources
  for ws in $(kubectl get websites -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
    image=$(kubectl get website $ws -o jsonpath='{.spec.image}')
    replicas=$(kubectl get website $ws -o jsonpath='{.spec.replicas}')

    # Reconcile: Ensure a Deployment exists with the desired state
    kubectl create deployment $ws-site --image=$image --replicas=$replicas --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1
    echo "Reconciled Website: $ws -> Image: $image, Replicas: $replicas"
  done
  sleep 5
done
EOF
chmod +x website-operator.sh

# 3. Run the operator in the background
./website-operator.sh &
OPERATOR_PID=$!

# 4. Create a Custom Resource
cat << 'EOF' | kubectl apply -f -
apiVersion: stable.example.com/v1
kind: Website
metadata:
  name: my-portfolio
spec:
  image: "nginx:alpine"
  replicas: 2
EOF

# 5. Observe the reconciliation (Wait a few seconds for the loop)
sleep 6
kubectl get deployments
kubectl get pods

# 6. Test the Reconciliation Loop
# The operator should fight back if we delete the managed deployment
echo "Deleting the managed deployment to simulate a failure..."
kubectl delete deployment my-portfolio-site

# 7. Check again in 5-10 seconds
sleep 6
kubectl get deployments
# The operator recreated it! This is the reconciliation loop in action.

# 8. Clean up
kill $OPERATOR_PID
kubectl delete website my-portfolio
kubectl delete deployment my-portfolio-site
kubectl delete crd websites.stable.example.com
rm website-operator.sh
```

<details>
<summary>Solution notes</summary>

When the script is running, the Deployment should appear after the `Website` custom resource exists. If you delete the Deployment while the script continues running, the next loop should recreate it. If it does not, inspect whether `kubectl get websites` returns the custom resource, whether the script has permission to create Deployments, and whether the Deployment name matches the script's naming convention.

</details>

**Card A: Installing a CRD creates the database Pods.** A learner sees the API server accept a `Database` custom resource and assumes the cluster must now schedule three database replicas. The wrong belief is tempting because the manifest looks declarative in the same way a Deployment manifest looks declarative. Predict which layer stores the intent, which layer creates Pods, and what evidence would separate a missing operator from a bad scheduler.

<details>
<summary>Check your prediction</summary>

**Failure layer:** The failure is in reconciliation, not scheduling. A CRD installs an API type and validates matching custom resources, but an operator or controller must translate that custom resource into Pods, StatefulSets, Services, or Secrets.

**Next action:** Confirm the custom resource exists, then look for the responsible controller Deployment, its logs, its RBAC permissions, and any status conditions on the custom resource.

</details>

**Card B: `kubectl api-resources` listing the type means the operator is healthy.** A learner runs discovery, sees the plural resource name, and treats that as proof that the installed extension is ready. The command is useful, but it answers an API-server question rather than a controller-health question. Predict which additional evidence would show that the operator has actually processed a specific custom resource.

<details>
<summary>Check your prediction</summary>

**Failure layer:** Discovery only proves that the API server serves the type. It does not prove the controller is running, authorized, watching the namespace, or able to write child resources.

**Next action:** Describe the custom resource, inspect status conditions and observed generation, check events, and then inspect the operator Deployment, logs, and RBAC bindings.

</details>

**Card C: Deleting a CRD only removes the definition; instances and children always stay.** A learner treats CRD deletion like deleting a class name from documentation while assuming every existing object survives unchanged. Kubernetes behaves more sharply because custom resources depend on their API definition for storage, discovery, and lifecycle handling. Predict what disappears immediately and what might remain for manual investigation after the operator is gone.

<details>
<summary>Check your prediction</summary>

**Failure layer:** The custom resource instances disappear with the CRD because the type no longer exists. Child resources may remain or disappear depending on owner references, finalizers, and whether the controller completed cleanup before the API disappeared.

**Next action:** Before uninstalling, list and back up the custom resources, understand the operator's cleanup behavior, then after deletion inspect surviving Secrets, Deployments, owner references, and terminating objects.

</details>

**Card D: A Certificate object exists, so a missing Secret means Kubernetes is broken.** A learner sees a valid `Certificate` custom resource and expects the Secret named in `spec.secretName` to appear automatically. The API server can store the request even when cert-manager cannot reconcile it because an issuer is wrong, RBAC is missing, or the controller is unhealthy. Predict which resource fields and controller signals would distinguish a Kubernetes API problem from a certificate-operator problem.

<details>
<summary>Check your prediction</summary>

**Failure layer:** The failure is usually in the cert-manager reconciliation path, not in the core Kubernetes Secret API. A stored `Certificate` proves API acceptance, while the missing Secret means the controller has not completed issuance.

**Next action:** Describe the `Certificate`, read its conditions and events, confirm the referenced Issuer or ClusterIssuer, inspect cert-manager controller logs, and verify the controller can create Secrets in the target namespace.

</details>

**Success Criteria**:

- [ ] Design a CRD with a valid group, names, scope, version, schema, and printer columns.
- [ ] Create custom resources and query them with plural, singular, and short-name forms.
- [ ] Debug CRD discovery and validation failures using `kubectl get crd`, `kubectl api-resources`, and apply errors.
- [ ] Implement an operator-style reconciliation loop that recreates a Deployment from a custom resource.
- [ ] Evaluate whether a custom resource should be namespaced or cluster-scoped.
- [ ] Diagnose operator reconciliation failures by checking custom resource status, events, controller pods, logs, and RBAC.

### Cleanup

Run this cleanup if you completed the earlier tasks and want to remove the practice resources. Some objects may already be gone if you followed every embedded cleanup command, so `--ignore-not-found` keeps the final sweep harmless.

```bash
kubectl delete website company-site blog my-portfolio --ignore-not-found
kubectl delete deployment my-portfolio-site --ignore-not-found
kubectl delete crd websites.stable.example.com --ignore-not-found
kubectl delete crd apps.example.com --ignore-not-found
kubectl delete crd databases.stable.example.com --ignore-not-found
kubectl delete crd tasks.work.example.com --ignore-not-found
kubectl delete crd backups.backup.example.com --ignore-not-found
rm -f website-crd.yaml my-website.yaml blog.yaml website-operator.sh
```

## Sources

- [Kubernetes documentation: Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
- [Kubernetes documentation: Extend the Kubernetes API with CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)
- [Kubernetes documentation: API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/)
- [Kubernetes documentation: Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [Kubernetes documentation: Finalizers](https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/)
- [Kubernetes documentation: API access control](https://kubernetes.io/docs/reference/access-authn-authz/)
- [Kubebuilder book: CronJob tutorial](https://book.kubebuilder.io/cronjob-tutorial/cronjob-tutorial)
- [Kubebuilder book: Status subresource](https://book.kubebuilder.io/reference/generating-crd.html)
- [Operator SDK documentation](https://sdk.operatorframework.io/docs/)
- [controller-runtime documentation](https://pkg.go.dev/sigs.k8s.io/controller-runtime)
- [cert-manager documentation](https://cert-manager.io/docs/)
- [Prometheus Operator documentation](https://prometheus-operator.dev/docs/getting-started/introduction/)

## Next Module

[Module 1.6: RBAC](../module-1.6-rbac/) - Role-Based Access Control for securing your cluster.
