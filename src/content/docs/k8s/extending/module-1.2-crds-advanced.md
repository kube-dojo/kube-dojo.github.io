---
title: "Module 1.2: Custom Resource Definitions Deep Dive"
slug: k8s/extending/module-1.2-crds-advanced
revision_pending: false
sidebar:
  order: 3
---

> **Complexity**: `[MEDIUM]` - Defining your own Kubernetes APIs
>
> **Time to Complete**: 3 hours
>
> **Prerequisites**: Module 1.1 (API Deep Dive), familiarity with YAML and JSON Schema

---

## Learning Outcomes

After completing this module, you will be able to:

1. **Design** a CRD schema with structural validation, CEL rules, and default values that reject invalid input at admission time.
2. **Implement** CRD versioning with storage versions and conversion webhooks so `v1alpha1` and `v1` style objects coexist safely.
3. **Configure** subresources, additional printer columns, and scale paths so `kubectl` presents useful operational behavior for custom resources.
4. **Diagnose** CRD validation failures, pruning surprises, and version-skew issues using API discovery, dry-run requests, and explicit version reads.

---

## Why This Module Matters

Hypothetical scenario: your platform team publishes a `BackupPolicy` API so application teams can describe backup schedules without learning the backup controller internals. The first few manifests work, but then one team submits a schedule string that the controller can not parse, another team sets retention to a negative number, and an older automation job keeps creating `v1alpha1` resources after you have already taught newer clients about `v1beta1`. None of those mistakes should require a controller crash before anyone notices them.

CRDs are how Kubernetes lets you add a new noun to the API without patching the API server itself. When you install systems such as Istio, Argo CD, cert-manager, or the Prometheus Operator, they register resource types such as `VirtualService`, `Application`, `Certificate`, and `ServiceMonitor` so the cluster can store and serve domain-specific objects through the same discovery, authorization, admission, watch, and storage machinery used by built-in resources. That is powerful, but it also means your CRD becomes a public contract the moment other teams start writing YAML against it.

The database table analogy is useful as long as you do not take it too literally. A CRD is like a `CREATE TABLE` statement because it declares the name, group, fields, and validation rules for a new collection of records. Kubernetes then handles create, read, update, delete, watch, authorization, and etcd persistence for those records, while your controller focuses on reconciling desired state into real infrastructure. Unlike a simple table, however, a Kubernetes API also needs version negotiation, defaulting, pruning, subresources, server-side apply semantics, and user-facing discovery output that can survive years of clients.

This module teaches the shape of that contract. You will begin with the anatomy of a CRD, move into structural OpenAPI validation and CEL rules, then add versioning, conversion, status separation, scale support, and printer columns. The hands-on exercise brings those pieces together in a `BackupPolicy` API that rejects invalid input at admission time and gives operators enough information to diagnose behavior without reading raw JSON.

---

## Core Content

### CRD Anatomy and Naming Contracts

A CRD begins with naming, and naming is not cosmetic in Kubernetes. The group, kind, plural name, singular name, short names, categories, and scope decide how the resource appears in discovery, REST paths, RBAC rules, and day-to-day `kubectl` workflows. If two vendors both choose the same group and plural name, the cluster has no neutral way to serve both APIs under one path, so reverse-domain naming is a practical collision-avoidance mechanism rather than a style preference.

The `metadata.name` of a CRD must be the plural resource name followed by the API group. That gives Kubernetes the stable REST collection path for your objects, such as `/apis/data.kubedojo.io/v1alpha1/namespaces/default/backuppolicies`. The `kind` stays singular and PascalCase because it is the type name users see inside manifests, while `plural` and `singular` are lowercase names used by discovery and command-line clients. Scope is equally important: choose `Namespaced` for resources owned by a team, workload, tenant, or namespace boundary, and reserve `Cluster` for resources that truly represent cluster-wide policy.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backuppolicies.data.kubedojo.io    # plural.group
spec:
  group: data.kubedojo.io                   # API group
  names:
    kind: BackupPolicy                      # PascalCase
    listKind: BackupPolicyList
    plural: backuppolicies                  # URL path
    singular: backuppolicy                  # kubectl alias
    shortNames:
    - bp                                    # kubectl shorthand
    categories:
    - all                                   # appears in `kubectl get all`
  scope: Namespaced                         # or Cluster
  versions:
  - name: v1alpha1
    served: true                            # API Server serves this version
    storage: true                           # Stored in etcd as this version
    schema:
      openAPIV3Schema:                      # Validation schema
        type: object
        properties:
          spec:
            type: object
            properties:
              schedule:
                type: string
              retention:
                type: integer
```

The example above is intentionally small, but it already shows the highest-leverage decision: you are defining an API, not just a blob of YAML. A `BackupPolicy` belongs to the `data.kubedojo.io` group, so an administrator can write RBAC rules against that group, an admission policy can match that group, and a client can discover the served versions. Even when a controller has not been written yet, the API server can validate, persist, list, watch, and delete objects of this kind.

| Field | Convention | Example |
|-------|-----------|---------|
| `group` | Reverse domain, owned by you | `data.kubedojo.io` |
| `kind` | PascalCase, singular | `BackupPolicy` |
| `plural` | lowercase, plural | `backuppolicies` |
| `singular` | lowercase, singular | `backuppolicy` |
| `shortNames` | 1-4 letter abbreviations | `bp` |
| CRD `metadata.name` | `{plural}.{group}` | `backuppolicies.data.kubedojo.io` |

Never use `k8s.io`, `kubernetes.io`, or another group you do not own. Those names are reserved for Kubernetes core APIs or for other owners, and a collision forces users to choose between competing definitions. A reverse-domain group is not a security boundary by itself, but it gives humans and automation a clear ownership signal when they inspect discovery output or review a manifest.

Pause and predict: what do you think happens if two operators both try to create a CRD whose `metadata.name` is `backuppolicies.data.kubedojo.io` but whose schemas describe different fields? The API server will accept only one object at that name, and every client using that group and plural will be bound to whichever schema won. That is why naming is part of API design, not a paperwork step at the top of the file.

### Structural Schemas, Pruning, Defaults, and CEL

Kubernetes requires CRDs in `apiextensions.k8s.io/v1` to use structural OpenAPI v3 schemas. Structural means the API server can determine the type and shape of each field without running arbitrary code or resolving ambiguous schema branches. That property lets the API server prune unknown fields, apply defaults, publish OpenAPI for clients, calculate managed fields for server-side apply, and reject invalid data before the object reaches etcd or your controller.

The most common mistake is to treat validation as something the controller can clean up later. That makes every bad manifest a reconciliation problem, and it means invalid state may already be stored and watched by other components before your controller reacts. Strong CRD schemas move as much validation as possible into admission, where users get synchronous errors, automation can fail fast, and controllers can assume a narrower, safer input domain.

Every field should have an explicit `type`, and important fields should use `required`, `minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, `enum`, and bounded collection sizes. Defaults are applied before validation, so a rule that references a defaulted field sees the defaulted value. Unknown fields are pruned unless you intentionally preserve them in a specific subtree, which is useful for plugin configuration but dangerous if you use it to avoid modeling your API.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.apps.kubedojo.io
spec:
  group: apps.kubedojo.io
  names:
    kind: WebApp
    listKind: WebAppList
    plural: webapps
    singular: webapp
    shortNames:
    - wa
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        description: "WebApp defines a web application deployment."
        required:
        - spec
        properties:
          spec:
            type: object
            description: "WebAppSpec defines the desired state."
            required:
            - image
            - replicas
            properties:
              image:
                type: string
                description: "Container image in registry/repo:tag format."
                pattern: '^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)*:[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$'
                minLength: 3
                maxLength: 255
              replicas:
                type: integer
                description: "Number of desired pod replicas."
                minimum: 1
                maximum: 100
                default: 2
              port:
                type: integer
                description: "Container port to expose."
                minimum: 1
                maximum: 65535
                default: 8080
              env:
                type: array
                description: "Environment variables for the container."
                maxItems: 50
                items:
                  type: object
                  required:
                  - name
                  - value
                  properties:
                    name:
                      type: string
                      description: "Environment variable name."
                      pattern: '^[A-Z_][A-Z0-9_]*$'
                      minLength: 1
                      maxLength: 128
                    value:
                      type: string
                      description: "Environment variable value."
                      maxLength: 4096
              resources:
                type: object
                description: "Resource requirements."
                properties:
                  cpuLimit:
                    type: string
                    description: "CPU limit (e.g., 500m, 1)."
                    pattern: '^[0-9]+m?$'
                    default: "500m"
                  memoryLimit:
                    type: string
                    description: "Memory limit (e.g., 128Mi, 1Gi)."
                    pattern: '^[0-9]+(Ki|Mi|Gi|Ti)?$'
                    default: "256Mi"
              ingress:
                type: object
                description: "Ingress configuration."
                properties:
                  enabled:
                    type: boolean
                    default: false
                  host:
                    type: string
                    description: "Hostname for ingress."
                    pattern: '^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$'
                  path:
                    type: string
                    default: "/"
                  tlsEnabled:
                    type: boolean
                    default: false
              healthCheck:
                type: object
                description: "Health check configuration."
                properties:
                  path:
                    type: string
                    description: "HTTP path for health checks."
                    default: "/healthz"
                  intervalSeconds:
                    type: integer
                    minimum: 5
                    maximum: 300
                    default: 10
                  timeoutSeconds:
                    type: integer
                    minimum: 1
                    maximum: 60
                    default: 3
          status:
            type: object
            description: "WebAppStatus defines the observed state."
            properties:
              readyReplicas:
                type: integer
                description: "Number of pods that are ready."
              availableReplicas:
                type: integer
                description: "Number of pods available for service."
              conditions:
                type: array
                description: "Current conditions of the WebApp."
                items:
                  type: object
                  required:
                  - type
                  - status
                  properties:
                    type:
                      type: string
                      description: "Condition type."
                    status:
                      type: string
                      description: "Condition status."
                      enum:
                      - "True"
                      - "False"
                      - "Unknown"
                    reason:
                      type: string
                      description: "Machine-readable reason."
                    message:
                      type: string
                      description: "Human-readable message."
                    lastTransitionTime:
                      type: string
                      format: date-time
                      description: "When the condition last changed."
              observedGeneration:
                type: integer
                format: int64
                description: "Generation observed by the controller."
```

This schema does more than describe documentation for humans. It rejects images that do not match the expected registry and tag pattern, bounds replica counts, sets defaults for common fields, limits collection sizes, and constrains condition status to known values. The API server can return a validation error before the controller sees a malformed object, which reduces controller branches and improves feedback for users writing manifests.

Pause and predict: if a user submits a `WebApp` with an environment variable name `1_INVALID`, which specific schema rule rejects it, and when does the rejection happen? The `pattern` under `spec.env.items.properties.name` rejects the value during API server admission, before the object is persisted. The controller never needs a special case for this malformed environment variable because the invalid object never becomes stored cluster state.

| Keyword | Applies To | Example |
|---------|-----------|---------|
| `minimum` / `maximum` | integer, number | `minimum: 1` |
| `exclusiveMinimum` / `exclusiveMaximum` | integer, number | `exclusiveMinimum: true` |
| `minLength` / `maxLength` | string | `maxLength: 253` |
| `pattern` | string | `pattern: '^[a-z]+$'` |
| `enum` | any | `enum: ["debug", "info", "warn"]` |
| `minItems` / `maxItems` | array | `maxItems: 10` |
| `uniqueItems` | array | `uniqueItems: true` |
| `required` | object | `required: ["name"]` |
| `default` | any | `default: 3` |
| `format` | string | `format: date-time` |
| `nullable` | any | `nullable: true` |

Kubernetes also adds extension fields to OpenAPI so custom APIs can behave more like built-in APIs. List and map extensions tell server-side apply whether a collection is atomic, set-like, or map-like, which changes how multiple field managers merge changes. Validation extensions let you attach CEL expressions where simple per-field constraints are not enough, including immutability checks and relationships between sibling fields.

```yaml
properties:
  metadata:
    type: object
    properties:
      name:
        type: string
        # Validate like a Kubernetes name
        x-kubernetes-validations:
        - rule: "self.matches('^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')"
          message: "must be a valid Kubernetes name"

  ports:
    type: array
    x-kubernetes-list-type: map
    x-kubernetes-list-map-keys:
    - containerPort
    items:
      type: object
      properties:
        containerPort:
          type: integer
        protocol:
          type: string

  labels:
    type: object
    additionalProperties:
      type: string
    x-kubernetes-map-type: granular   # SSA tracks individual keys

  immutableField:
    type: string
    x-kubernetes-validations:
    - rule: "self == oldSelf"
      message: "field is immutable once set"
```

The `ports` example is a practical server-side apply decision. Without map semantics, a manager that owns one list item can conflict with or overwrite another manager that owns a different item because the whole list may be treated as one field. With `x-kubernetes-list-type: map` and a stable key, Kubernetes can reason about individual entries, which is closer to how operators expect lists of ports, conditions, and named rules to behave.

CEL rules are best used for relationships that OpenAPI does not express cleanly, such as `minReplicas` being less than or equal to `maxReplicas` or requiring an ingress host when TLS is enabled. CEL validation rules via `x-kubernetes-validations` graduated to GA in Kubernetes 1.29, so they are a dependable, server-enforced layer on every supported cluster rather than an alpha convenience. Keep CEL rules small, deterministic, and directly tied to the field being validated. If the rule requires network calls, large lookups, or business policy that changes frequently, use an admission webhook or controller logic instead.

```yaml
spec:
  type: object
  x-kubernetes-validations:
  - rule: "self.minReplicas <= self.maxReplicas"
    message: "minReplicas must not exceed maxReplicas"
    fieldPath: ".minReplicas"
  - rule: "self.replicas >= self.minReplicas && self.replicas <= self.maxReplicas"
    message: "replicas must be between minReplicas and maxReplicas"
  - rule: "!has(self.ingress) || !self.ingress.tlsEnabled || self.ingress.host != ''"
    message: "host is required when TLS is enabled"
  properties:
    minReplicas:
      type: integer
    maxReplicas:
      type: integer
    replicas:
      type: integer
    ingress:
      type: object
      properties:
        tlsEnabled:
          type: boolean
        host:
          type: string
```

Before running this, what output do you expect from a server-side dry run when `minReplicas` is larger than `maxReplicas`? You should expect an admission error with the message from the CEL rule, not a stored object that the controller later marks failed. That distinction matters because admission errors are cheap, immediate, and visible to the tool that submitted the manifest.

| Expression | Description |
|-----------|------------|
| `self` | Current value of the field |
| `oldSelf` | Previous value (for update validation) |
| `self.field` | Access a sub-field |
| `self.list.exists(x, x.name == 'foo')` | Check if any item matches |
| `self.list.all(x, x.port > 0)` | Check all items match |
| `self.matches('^[a-z]+$')` | Regex match |
| `size(self) <= 10` | Collection/string size check |
| `has(self.optionalField)` | Check if optional field is set |

### Versioning, Conversion, and Storage Migration

The first version of a CRD is rarely the final version. Fields get renamed, status grows richer, nested objects replace flat strings, and clients continue to exist after the platform team has moved on. Kubernetes handles this by letting a CRD serve multiple versions while choosing exactly one storage version for etcd. Served versions are the API shapes clients can request, while the storage version is the internal persisted representation.

Versioning is not a license to make arbitrary breaking changes and hope clients adapt. A good CRD version plan starts by deciding which changes are additive and which changes require conversion. Adding an optional field is usually easy because older clients can ignore it, but renaming `port` to `ports` or replacing `target: "deployment/web"` with a structured selector changes meaning. When versions are structurally different, the API server needs a conversion webhook that can translate between versions during read and write paths.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.apps.kubedojo.io
spec:
  group: apps.kubedojo.io
  names:
    kind: WebApp
    listKind: WebAppList
    plural: webapps
    singular: webapp
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true       # Clients can read/write this version
    storage: false      # NOT the storage version
    deprecated: true    # Show deprecation warning
    deprecationWarning: "apps.kubedojo.io/v1alpha1 WebApp is deprecated; use v1beta1"
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
              port:
                type: integer
          status:
            type: object
            properties:
              readyReplicas:
                type: integer

  - name: v1beta1
    served: true       # Clients can read/write this version
    storage: true       # THIS version is stored in etcd
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required:
            - image
            properties:
              image:
                type: string
              replicas:
                type: integer
                minimum: 1
                maximum: 100
                default: 2
              ports:                  # Renamed from 'port' to 'ports' (array)
                type: array
                items:
                  type: object
                  properties:
                    name:
                      type: string
                    containerPort:
                      type: integer
                    protocol:
                      type: string
                      enum: ["TCP", "UDP"]
                      default: "TCP"
              resources:              # New field in v1beta1
                type: object
                properties:
                  cpuLimit:
                    type: string
                  memoryLimit:
                    type: string
          status:
            type: object
            properties:
              readyReplicas:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  properties:
                    type:
                      type: string
                    status:
                      type: string
```

In this example, both versions remain served, but only `v1beta1` is stored. Because these two versions are structurally different, automatic conversion between them requires a conversion webhook (`strategy: Webhook`, shown next). With the default `None` strategy the API server only rewrites the `apiVersion` label and copies fields as-is, which is safe ONLY when the schemas are compatible. A client may create a `v1alpha1` object and the API server persists it in the storage version; on read, it returns the stored fields under the requested version label without translating `port` into `ports` unless a webhook performs that mapping.

There are two conversion strategies. The `None` strategy is effectively a no-op and is only safe when the schemas are compatible enough that the same object can be represented across versions without semantic translation. The `Webhook` strategy sends conversion reviews to a service you operate, and that service must handle every supported version pair correctly enough that old and new clients see stable meaning.

```yaml
spec:
  conversion:
    strategy: Webhook
    webhook:
      conversionReviewVersions: ["v1"]
      clientConfig:
        service:
          namespace: webapp-system
          name: webapp-webhook
          path: /convert
          port: 443
        caBundle: <base64-encoded-CA-cert>
```

Conversion webhooks sit on a sensitive request path. If the webhook is down, slow, or returns inconsistent objects, reads and writes for affected versions can fail or surprise clients. Treat conversion code like API compatibility code: cover it with tests, keep it deterministic, preserve unknown meaning when possible, and deploy it before flipping storage versions or deprecating older served versions.

Changing the storage version does not rewrite every existing object in etcd immediately. Existing objects remain stored in the older representation until they are rewritten, while reads may convert them on the fly. That lazy behavior avoids an instant cluster-wide rewrite, but it also means you need a deliberate storage migration plan when you want the persisted representation to converge.

```bash
# List all objects (triggers conversion on read)
kubectl get webapps --all-namespaces -o yaml > /dev/null

# Or use the storage version migrator (kube-storage-version-migrator)
# This systematically reads and rewrites all objects in the new storage version
# (optional component — not installed on default kind/minikube clusters)
```

Pause and predict: if you have 10,000 `WebApp` resources stored as `v1alpha1` and you mark `v1beta1` as storage, do those objects instantly rewrite in etcd? They do not. The API server can serve converted views on demand, but you still need a rewrite or a storage-version migration process if you want the backing data to move to the new storage representation.

Diagnosing version skew starts with discovery. `kubectl api-resources` shows which resources are served and which version appears preferred, while an explicit fully qualified resource request can show what an older client receives. Server-side dry run is equally important because it executes defaulting, validation, and admission without saving bad state, making it the fastest way to test a CRD schema change before you merge it into a platform repository.

### Subresources and Operational Interfaces

Subresources let your custom API behave like built-in Kubernetes resources. The most important one is `status`, which separates desired state from observed state. Users and GitOps tools write `spec` to describe what they want, while controllers write `status` to describe what the cluster currently has. Without that separation, a normal update to the main resource can overwrite controller-owned status fields, which makes status less trustworthy and can create noisy reconciliation loops.

```yaml
versions:
- name: v1beta1
  served: true
  storage: true
  subresources:
    status: {}      # Enable /status subresource
  schema:
    openAPIV3Schema:
      # ... schema here
```

With the status subresource enabled, the main resource endpoint ignores `status` updates, and the `/status` endpoint ignores `spec` updates. That sounds simple, but it is a major ownership boundary. RBAC can grant controllers permission to update `webapps/status` without letting them rewrite user intent, while users can update the resource without accidentally claiming the controller has observed something it has not.

```bash
# Users update spec
kubectl patch webapp my-app --type=merge -p '{"spec":{"replicas":5}}'

# Controllers update status (using client-go)
# webapp.Status.ReadyReplicas = 5
# client.Status().Update(ctx, webapp)
```

The scale subresource is another operational contract. It lets tools such as `kubectl scale` and the Horizontal Pod Autoscaler interact with your custom resource through the standard `scale` interface rather than learning your entire schema. To enable it, you point Kubernetes at the desired replicas field, the observed replicas field, and optionally the label selector field that identifies controlled pods.

```yaml
versions:
- name: v1beta1
  served: true
  storage: true
  subresources:
    status: {}
    scale:
      specReplicasPath: .spec.replicas
      statusReplicasPath: .status.readyReplicas
      labelSelectorPath: .status.labelSelector
```

Now standard scaling commands can target the custom resource:

```bash
# Scale the custom resource
kubectl scale webapp my-app --replicas=5

# Use HPA (also requires Metrics Server and a controller that keeps
# status.replicas, status.selector, and readyReplicas current)
kubectl autoscale webapp my-app --min=2 --max=10 --cpu-percent=80
```

CPU-based autoscaling on arbitrary CRDs is not automatic just because the scale subresource exists. HPA reads metrics through Metrics Server and writes desired replicas through the scale endpoint, but your controller must maintain the status fields HPA consults and reconcile child workloads accordingly.

Pause and predict: if you configure HPA for your custom resource but omit the `scale` subresource, what breaks first? The HPA has no standard scale endpoint to read or write for that resource, so it can not reliably determine current replicas or update desired replicas. The fix is not an HPA flag; it is a CRD contract that exposes scale paths with fields your controller actually maintains.

Printer columns complete the basic operator experience. By default, `kubectl get` for a custom resource shows little more than name and age, which forces users to inspect YAML for every question. Additional printer columns let the API server publish useful JSONPath snippets so clients can show image, desired replicas, ready replicas, phase, schedule, last backup time, or other fields that matter during normal triage.

```yaml
versions:
- name: v1beta1
  served: true
  storage: true
  additionalPrinterColumns:
  - name: Image
    type: string
    description: "Container image"
    jsonPath: .spec.image
    priority: 0          # 0 = always shown, 1+ = shown with -o wide
  - name: Replicas
    type: integer
    description: "Desired replicas"
    jsonPath: .spec.replicas
  - name: Ready
    type: integer
    description: "Ready replicas"
    jsonPath: .status.readyReplicas
  - name: Status
    type: string
    description: "Current status"
    jsonPath: .status.conditions[?(@.type=="Ready")].status
    priority: 0
  - name: Age
    type: date
    jsonPath: .metadata.creationTimestamp
```

Result:

```
$ kubectl get webapps
NAME       IMAGE             REPLICAS   READY   STATUS   AGE
my-app     nginx:1.27        3          3       True     5m
frontend   react-app:2.1     2          1       False    2m
```

Good printer columns answer the first operational question, not every possible question. Use priority zero for the columns most users need on a narrow terminal, and assign higher priorities to fields that help debugging but make default output too wide. If a column requires a complex JSONPath over an array, test it against empty, missing, and multi-item data so the output stays predictable.

| JSONPath Expression | Selects |
|-------------------|---------|
| `.spec.replicas` | Simple field |
| `.status.conditions[0].status` | First array element |
| `.status.conditions[?(@.type=="Ready")].status` | Filter by field value |
| `.metadata.creationTimestamp` | Standard field (use with `type: date`) |
| `.metadata.labels.app` | Label value |

### A Production-Grade WebApp CRD

The following CRD brings the pieces together into one definition. It uses a stable API group, a namespaced resource, a single served storage version, the status and scale subresources, printer columns, bounded fields, list map semantics, default values, and CEL cross-field validation. In a generated operator project this YAML would usually come from Go markers and controller-gen, but reading the expanded CRD helps you see exactly what the API server receives.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.apps.kubedojo.io
  annotations:
    controller-gen.kubebuilder.io/version: v0.17.0
spec:
  group: apps.kubedojo.io
  names:
    kind: WebApp
    listKind: WebAppList
    plural: webapps
    singular: webapp
    shortNames:
    - wa
    categories:
    - all
    - kubedojo
  scope: Namespaced
  versions:
  - name: v1beta1
    served: true
    storage: true
    subresources:
      status: {}
      scale:
        specReplicasPath: .spec.replicas
        statusReplicasPath: .status.readyReplicas
    additionalPrinterColumns:
    - name: Image
      type: string
      jsonPath: .spec.image
    - name: Desired
      type: integer
      jsonPath: .spec.replicas
    - name: Ready
      type: integer
      jsonPath: .status.readyReplicas
    - name: Phase
      type: string
      jsonPath: .status.phase
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
    schema:
      openAPIV3Schema:
        type: object
        description: "WebApp manages a web application deployment with optional ingress."
        required:
        - spec
        properties:
          apiVersion:
            type: string
          kind:
            type: string
          metadata:
            type: object
          spec:
            type: object
            description: "Desired state of the WebApp."
            required:
            - image
            x-kubernetes-validations:
            - rule: "self.minReplicas <= self.maxReplicas"
              message: "minReplicas must not exceed maxReplicas"
            - rule: "self.replicas >= self.minReplicas && self.replicas <= self.maxReplicas"
              message: "replicas must be within [minReplicas, maxReplicas]"
            properties:
              image:
                type: string
                description: "Container image."
                minLength: 1
                maxLength: 255
              replicas:
                type: integer
                description: "Desired number of replicas."
                minimum: 0
                maximum: 500
                default: 2
              minReplicas:
                type: integer
                description: "Minimum replicas for autoscaling."
                minimum: 0
                default: 1
              maxReplicas:
                type: integer
                description: "Maximum replicas for autoscaling."
                minimum: 1
                maximum: 500
                default: 10
              ports:
                type: array
                description: "Ports to expose."
                maxItems: 20
                x-kubernetes-list-type: map
                x-kubernetes-list-map-keys:
                - containerPort
                items:
                  type: object
                  required:
                  - containerPort
                  properties:
                    name:
                      type: string
                      maxLength: 15
                    containerPort:
                      type: integer
                      minimum: 1
                      maximum: 65535
                    protocol:
                      type: string
                      enum: ["TCP", "UDP", "SCTP"]
                      default: "TCP"
              env:
                type: array
                description: "Environment variables."
                maxItems: 100
                items:
                  type: object
                  required:
                  - name
                  properties:
                    name:
                      type: string
                    value:
                      type: string
                    valueFrom:
                      type: object
                      description: "Simplified placeholder — in Kubernetes, valueFrom is an object with secretKeyRef or configMapKeyRef, not a string."
              resources:
                type: object
                properties:
                  requests:
                    type: object
                    properties:
                      cpu:
                        type: string
                        default: "100m"
                      memory:
                        type: string
                        default: "128Mi"
                  limits:
                    type: object
                    properties:
                      cpu:
                        type: string
                        default: "500m"
                      memory:
                        type: string
                        default: "512Mi"
              ingress:
                type: object
                x-kubernetes-validations:
                - rule: "!self.tlsEnabled || self.host != ''"
                  message: "host is required when TLS is enabled"
                properties:
                  enabled:
                    type: boolean
                    default: false
                  host:
                    type: string
                  path:
                    type: string
                    default: "/"
                  tlsEnabled:
                    type: boolean
                    default: false
                  tlsSecretName:
                    type: string
          status:
            type: object
            description: "Observed state of the WebApp."
            properties:
              phase:
                type: string
                enum: ["Pending", "Deploying", "Running", "Degraded", "Failed"]
              readyReplicas:
                type: integer
              availableReplicas:
                type: integer
              observedGeneration:
                type: integer
                format: int64
              conditions:
                type: array
                x-kubernetes-list-type: map
                x-kubernetes-list-map-keys:
                - type
                items:
                  type: object
                  required:
                  - type
                  - status
                  properties:
                    type:
                      type: string
                    status:
                      type: string
                      enum: ["True", "False", "Unknown"]
                    reason:
                      type: string
                    message:
                      type: string
                    lastTransitionTime:
                      type: string
                      format: date-time
```

When you test a production CRD, test both the happy path and the rejection paths. A CRD that only accepts valid examples may still be too permissive, and a CRD that rejects one invalid example may still miss a dangerous edge case. Server-side dry run is the right default because it exercises the API server validation stack without leaving a resource behind.

```bash
# Apply the CRD
kubectl apply -f webapp-crd.yaml

# Verify it registered and wait for the API server to serve it
kubectl wait --for=condition=established crd/webapps.apps.kubedojo.io
kubectl api-resources | grep webapp

# Create a valid WebApp
cat << 'EOF' | kubectl apply -f -
apiVersion: apps.kubedojo.io/v1beta1
kind: WebApp
metadata:
  name: my-frontend
  namespace: default
spec:
  image: nginx:1.27
  replicas: 3
  minReplicas: 1
  maxReplicas: 10
  ports:
  - name: http
    containerPort: 80
  - name: metrics
    containerPort: 9090
  env:
  - name: NODE_ENV
    value: production
  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "1"
      memory: "1Gi"
  ingress:
    enabled: true
    host: frontend.example.com
    path: /
    tlsEnabled: true
    tlsSecretName: frontend-tls
EOF

# Check printer columns
kubectl get webapps
kubectl get wa            # shortName works

# Try an invalid resource to diagnose validation failures using server dry-run
cat << 'EOF' | kubectl apply --dry-run=server -f -
apiVersion: apps.kubedojo.io/v1beta1
kind: WebApp
metadata:
  name: invalid-app
spec:
  image: nginx:1.27
  replicas: 3
  minReplicas: 10     # ERROR: minReplicas > maxReplicas (default 10)
  maxReplicas: 5      # ERROR: less than minReplicas
EOF
# Expected: admission error from CEL validation

# Test scale subresource
kubectl scale webapp my-frontend --replicas=5
kubectl get webapp my-frontend -o jsonpath='{.spec.replicas}'
```

Which approach would you choose here and why: a broad schema that accepts nearly any field so the controller can decide later, or a stricter schema that rejects unknown and malformed data up front? For platform APIs, the stricter schema usually gives a better operational outcome because every client gets the same contract, and invalid data does not drift through watches, caches, backups, and debugging tools. Use controller logic for reconciliation and external state, not for basic shape validation that admission can enforce.

### Operating and Evolving CRDs Safely

Publishing the first version of a CRD is usually the easy part; operating it after other teams depend on it is the real test. Treat the CRD manifest as an API artifact with the same review standard you would apply to an HTTP endpoint or a shared library. A reviewer should ask whether every required field is truly required, whether optional fields have sensible defaults, whether list merge semantics match user expectations, and whether the status shape gives a controller enough room to explain partial progress instead of only success or failure.

Start every CRD review with stored data in mind. Once an object is accepted, it may be stored in etcd, copied into backups, watched by controllers, indexed by clients, exported by audit tooling, and committed into GitOps repositories. A loose field that slips through admission can therefore become part of the operational record even if the controller later ignores it. Strong schemas are not busywork; they reduce the amount of invalid state that every other component has to tolerate.

The safest schema review pattern is to work backward from bad examples. Write one valid manifest, then write manifests that omit required fields, typo important fields, exceed every maximum, use unsupported enum values, invert cross-field relationships, and create empty arrays or maps where the controller expects content. Run those manifests with server-side dry run and confirm the API server returns useful messages. If a bad manifest is accepted, improve the schema before adding controller code that compensates for it.

Defaulting deserves the same discipline as validation. A default value is not just a convenience for users; it becomes persisted API behavior that clients may learn to rely on. Prefer defaults that are conservative, inexpensive, and safe when a user is new to the API. Avoid defaults that allocate expensive infrastructure, enable public exposure, or hide a policy decision that should be explicit in a manifest reviewed by the owning team.

CRD status design should answer three questions for an operator: what generation did the controller observe, what condition currently blocks progress, and what field or external dependency should be checked next. Conditions are usually more durable than a single phase string because they let you represent multiple truths at once, such as `Ready=False`, `Progressing=True`, and `Degraded=True`. A phase can still be helpful in printer columns, but conditions give automation and humans richer diagnostic structure.

When you add conditions, keep them map-like by condition type so server-side apply and patch behavior stay predictable. A controller that replaces the whole conditions array on every reconcile can fight with other writers and make historical transitions hard to read. A controller that updates one condition type at a time, includes `observedGeneration`, and writes clear reason strings produces status that feels native to Kubernetes. The CRD schema should support that behavior by constraining condition status values and bounding message lengths.

Version planning should begin before the first public release, even if you only serve one version on day one. Decide what counts as compatible for your API: adding optional fields, adding new enum values, changing defaults, tightening validation, and renaming fields have different risk profiles. Tightening validation can break existing manifests that were previously accepted, so it needs the same care as a field removal. If you discover invalid stored objects, migrate them before making a rule stricter.

Deprecation warnings are useful because they meet users where they already are: inside the API request. A warning on a served version tells an old script that it still works today but needs attention before removal. That warning is most valuable when paired with a migration guide, conversion behavior, and a clear date or release target in project documentation. A warning without a migration path only creates noise, while a removal without warning creates avoidable outages.

Conversion webhooks should be boring by design. They should not call cloud APIs, read unrelated cluster state, or make policy decisions that vary by time of day. Their job is to preserve API meaning between versions, and every extra dependency expands the blast radius of reads and writes. If conversion fails, clients may be unable to read objects in a requested version, so test webhook availability, TLS configuration, and version coverage before making older and newer versions depend on it.

A useful conversion test suite includes round-trip checks. Convert an old object to the new version, then convert it back and verify the fields old clients care about are still present with the same meaning. Convert a new object to the old version and decide how unsupported new fields degrade. Sometimes you can preserve data in annotations or status during migration, but sometimes the honest answer is that old versions can only serve a lossy view and should be deprecated quickly.

Storage migration is an operational event, not just a YAML edit. After the storage version changes, reads can convert objects on demand, but the persisted representation may remain mixed until objects are rewritten. That matters for backups, disaster recovery, direct etcd inspection, and performance during large list operations. Plan migrations during a maintenance window appropriate for the number of objects, and measure API server and webhook behavior under list and watch traffic before assuming the change is cheap.

Server-side apply adds another reason to model list and map semantics carefully. If a field represents named entries, such as ports, conditions, notification destinations, or retention policies, atomic list behavior often creates unnecessary conflicts because the whole list acts like one managed field. Map semantics let different field managers own distinct entries when the key is stable. The cost is that you must choose the key carefully and validate enough of the item shape to prevent ambiguous ownership.

Printer columns should be reviewed with real terminal output, not just by reading YAML. A column that looks reasonable in a CRD may wrap badly when names are long or status messages include detailed reasons. The default view should answer the first triage question: is the resource active, what target does it affect, what schedule or image is configured, and is the controller reporting progress? Wider diagnostic fields belong behind `priority: 1` so users can opt into them.

RBAC is part of the CRD contract as soon as teams operate the resource. A user who can update the main resource should not automatically be able to update status, and a controller that updates status should not automatically be able to rewrite spec. Similarly, a team that can create namespaced custom resources should not necessarily be able to modify the CRD definition itself. Separate the cluster-admin responsibility of publishing APIs from the tenant responsibility of using those APIs.

Admission webhooks and CEL rules complement each other, but they solve different problems. CEL is best for local, deterministic checks over the object being admitted. A validating webhook is better when the rule depends on external inventory, organization policy, or complex parsing that would make a CEL expression unreadable. A mutating webhook can fill values that CRD defaulting does not express, but every mutation should be predictable enough that users are not surprised when they read the object back.

Observability for CRDs starts with the API server and continues into the controller. During development, watch API server validation errors, audit events, controller reconcile errors, and status transitions together. If users report that an object was accepted but nothing happened, first ask whether the object matches the schema, whether the controller observed the latest generation, whether status conditions explain the blockage, and whether printer columns surface enough state for a quick answer. That investigation path is much faster when the CRD was designed for diagnosis from the start.

Testing should include upgrade and downgrade paths, not only fresh installs. Apply the old CRD, create old resources, upgrade the CRD, read those resources through each served version, create new resources, and verify older clients get either a compatible view or a clear deprecation path. Then test cleanup and deletion, because finalizers and custom resources can keep a CRD deletion from completing. These tests catch compatibility mistakes that unit tests around controller reconcile loops usually miss.

Documentation should live beside the CRD definition, not only beside the controller. Users need to know which fields are required, which defaults are applied, which versions are deprecated, which status conditions are meaningful, and which printer columns are intended for routine triage. The CRD schema can include descriptions, but descriptions alone rarely explain migration choices or operational expectations. Pair schema comments with examples that show valid resources, rejected resources, and the expected `kubectl get` output.

GitOps workflows make CRD compatibility especially important because manifests may be applied repeatedly by automation that has no memory of a deprecation meeting. A controller upgrade may happen quickly, but repository changes across many teams often take longer. Serving an old version with a warning gives those repositories time to move, while conversion keeps central storage consistent during the transition. If you remove a version before repositories are updated, the failure appears as an apply error in every pipeline still using the old API.

Large clusters also change the cost model for CRD design. A resource that seems harmless with three objects may be expensive with thousands of objects, especially if status is noisy or unbounded fields make each object large. Every status update can trigger watches, cache updates, and downstream reconciles. Bound message sizes, avoid writing status when nothing changed, and keep high-cardinality event-like data out of the custom resource unless it is truly part of the desired or observed state.

Be careful with fields that look like escape hatches. A generic `config` map, a preserved unknown subtree, or an untyped `template` field can be useful when embedding another API, but it also weakens validation and server-side apply ownership. If you need an extension point, name it clearly, bound its size, and document who owns its contents. Do not use an escape hatch to avoid deciding the shape of fields that your controller already depends on.

Deletion semantics belong in the API conversation too. Many custom resources use finalizers so a controller can clean up external resources before the object disappears. That means users need status conditions and events that explain deletion progress, and the schema should include enough identity fields for the controller to clean up reliably. If an API allows users to change those identity fields after creation, deletion may become ambiguous, so consider immutability rules for fields that name external resources.

Field immutability is one of the most useful CEL patterns for CRDs that manage durable infrastructure. A backup target, cloud database identifier, or storage class may be safe to choose at creation time but risky to mutate later. You can compare `self` and `oldSelf` to reject updates that would change such a field, then ask users to create a new resource when they need a different target. That makes disruptive changes explicit instead of hiding them in a normal patch.

Finally, review CRDs from the perspective of the person on call. During an incident, they will not read your controller code first; they will run discovery commands, list resources, inspect status, and look for recent events. If the CRD has clear printer columns, bounded and meaningful status, explicit conditions, and validation messages that point to the bad field, the API itself helps them move quickly. If the CRD is a loose data bag, the on-call engineer has to reverse-engineer intent while the system is already failing.

The practical rule is simple: make invalid states unrepresentable when the API server has enough information to reject them. Let the controller focus on the changing world outside the object, such as pods becoming ready, backups completing, certificates renewing, or cloud resources appearing. A CRD that accepts nearly anything forces the controller to be both API server and reconciler. A CRD with a clear schema, version strategy, subresources, and diagnostic columns lets Kubernetes carry more of the API contract for you.

---

## Patterns & Anti-Patterns

CRD design patterns are really API maintenance patterns. The YAML may look static, but the resource becomes part of user workflows, Git repositories, automation scripts, dashboards, alerts, and RBAC rules. Design choices that feel minor during the first implementation become expensive once clients depend on them, so use the table below as a design review checklist before publishing a new version.

| Pattern | When to Use | Why It Works | Scaling Consideration |
|---------|-------------|--------------|-----------------------|
| Structural schema first | Every `apiextensions.k8s.io/v1` CRD | Gives the API server enough information for pruning, validation, defaulting, and server-side apply | Add bounds to strings, arrays, and maps so objects stay within practical limits |
| Version before breaking shape | Any API that external clients use | Lets old and new clients coexist while you migrate manifests and controllers | Conversion code must be tested as compatibility code, not treated as glue |
| Status and scale as contracts | Resources reconciled by controllers or autoscalers | Separates user intent from observed state and lets standard tools interact with the resource | Controller RBAC should target `/status`, and HPA needs maintained scale fields |
| Printer columns for first triage | Resources users inspect during incidents | Makes `kubectl get` useful without forcing every user into raw YAML | Keep default columns narrow and move secondary fields behind `-o wide` |

Anti-patterns usually appear when a team treats a CRD as an internal serialization format instead of a public API. That temptation is understandable because CRDs are easy to apply and change, but the ease is misleading. Once a field exists in live manifests, changing or deleting it has the same compatibility cost as changing any other API field.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Controller-only validation | Invalid state reaches etcd and every watcher before the controller reacts | Reject shape, range, enum, and cross-field errors in the CRD schema |
| Root-level arbitrary objects | Unknown fields bypass the contract and surprise server-side apply | Model known fields explicitly, preserving unknown fields only in named extension subtrees |
| Silent version removal | Older clients fail suddenly when a served version disappears | Deprecate first, publish warnings, keep conversion working, and migrate clients deliberately |
| Status in user manifests | Users or GitOps tools overwrite observed state | Enable the status subresource and grant status updates only to controllers |

---

## Decision Framework

Use CRD features according to the kind of compatibility problem you are solving. The safest path is not always the most complicated path; a simple additive schema change may not need a webhook, while a renamed field with changed meaning almost certainly does. The following matrix is a practical way to choose the smallest mechanism that still preserves a clear API contract.

| Situation | Use This | Avoid This | Reasoning |
|-----------|----------|------------|-----------|
| A field is required for every useful object | `required` plus a specific type | Controller errors after creation | Admission feedback is faster and prevents bad stored state |
| A field has a safe common value | `default` in the schema | Mutating controller patches after creation | Defaults become visible and consistent before validation and storage |
| Two fields must agree | CEL validation | A long controller reconcile branch | Cross-field admission keeps invalid combinations out of etcd |
| A new optional field is added | Same version or new served version, depending on stability | Immediate storage-version flip | Additive changes do not automatically require conversion |
| A field is renamed or restructured | New version plus conversion webhook | `None` conversion with incompatible shapes | Clients need stable meaning across requested versions |
| Operators need quick status | Printer columns and status subresource | Requiring raw YAML inspection | Discovery metadata should support routine triage |
| Autoscaling should target the CRD | Scale subresource | Custom HPA workarounds | Standard tools expect the Kubernetes scale interface |

An implementation flow helps keep the order straight. Start with the resource contract and schema, then add validation for invalid inputs, then add operational interfaces, and only then make versioning decisions for compatibility. If you start with conversion or controller code before the schema is stable, you risk building complicated machinery around a contract that has not yet been reviewed.

---

## Did You Know?

1. CRDs became available in beta form long before `apiextensions.k8s.io/v1`, but structural schemas became mandatory for v1 CRDs in Kubernetes 1.16, which changed CRDs from mostly flexible JSON storage into much stronger API contracts.
2. Kubernetes stores custom resources in etcd through the same API server machinery as built-in objects, so a poorly bounded CRD can create real storage and watch pressure even though no custom storage backend was written.
3. CEL validation for CRDs lets many cross-field checks run directly in API server admission, which avoids deploying a validating admission webhook for simple relationships such as `minReplicas <= maxReplicas`.
4. A CRD can serve multiple versions while storing only one version, so the version in a user's manifest is not necessarily the representation persisted in etcd.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Non-structural schema | Teams copy old examples or leave nested objects untyped | Give every field an explicit type and keep validation keywords inside typed fields |
| Missing `required` on `spec` | Early examples focus on successful manifests and skip empty-object tests | Mark essential fields as required and test empty or partial resources with server-side dry run |
| Regex too permissive | The pattern validates one happy-path string but not edge cases | Test valid and invalid examples, then pair patterns with min and max length bounds |
| No status subresource | The first controller writes status directly and nobody notices the ownership problem | Enable `status: {}` and update status through the `/status` subresource |
| Changing storage version without migration | Teams expect the storage flag to rewrite old objects immediately | Plan conversion and storage migration, then verify storedVersions and object rewrites |
| Using arbitrary maps at the root | A flexible data bag feels faster than modeling the API | Keep the root structural and preserve unknown fields only in deliberate extension fields |
| Forgetting printer columns | Developers test with `kubectl get -o yaml` instead of operator workflows | Add narrow default columns and move secondary diagnostics behind priority fields |
| CEL rules too complex | Business policy gets pushed into admission because it is convenient | Keep CEL deterministic and local, and use webhooks or controllers for external policy |

---

## Quiz

<details>
<summary>1. You review a CRD pull request that uses `additionalProperties: true` at the root and omits explicit types from several nested objects. The CRD fails on a modern Kubernetes cluster. What should you change first, and why?</summary>

The first fix is to make the schema structural by declaring explicit types for the root object and every modeled nested field. Root-level arbitrary properties prevent the API server from safely pruning, defaulting, and calculating managed fields, so the CRD is rejected before any custom resources can use it. Move flexible maps into specific typed fields if the API truly needs extensibility, and keep validation keywords attached to typed schema nodes. This directly tests the ability to design a CRD schema that admission can enforce.

</details>

<details>
<summary>2. Your team has a `Database` CRD with a `status` field but no status subresource. A developer applies a manifest that overwrites `status.activeConnections`, and the controller reacts to false data. How does the status subresource change the failure mode?</summary>

With the status subresource enabled, updates to the main resource endpoint ignore `status`, so a user manifest can not accidentally claim observed state. The controller writes status through the separate `/status` endpoint, and RBAC can grant that permission without granting full spec updates. This keeps desired state and observed state under different ownership, which makes controller behavior easier to reason about. It also aligns the CRD with built-in Kubernetes resource conventions.

</details>

<details>
<summary>3. A `Certificate` CRD serves `v1alpha1` and `v1beta1`, but `v1alpha1` is still the storage version. A developer creates a `v1beta1` object. What representation is stored, and what must happen during reads?</summary>

The API server stores the object in the configured storage version, so the persisted representation is `v1alpha1`. On write, the incoming `v1beta1` object is converted to the storage form before it is saved. On read, the API server converts the stored object to whichever served version the client requested. If the versions are structurally different, a conversion webhook must perform that translation correctly or clients will see failures or incorrect data.

</details>

<details>
<summary>4. Users keep entering schedule strings such as `every day` in a `BackupJob` CRD, and the controller rejects them later. How would you reject obviously malformed schedules before storage?</summary>

Add schema validation to the `schedule` field so the API server rejects malformed values during admission. A CEL rule can check that the string has five space-separated fields, while a `minLength` and `maxLength` can keep the field bounded. This will not prove the cron expression is semantically perfect, but it blocks common malformed input before it reaches etcd. More advanced calendar semantics belong in a webhook or controller because they require deeper parsing.

```yaml
x-kubernetes-validations:
- rule: "self.matches('^(\\S+\\s+){4}\\S+$')"
  message: "schedule must be a valid cron expression with 5 fields"
```

</details>

<details>
<summary>5. Two automation scripts update different entries in a CRD `ports` array, and the last writer overwrites the other writer's entry. Which schema extension helps, and what key must you choose?</summary>

Use `x-kubernetes-list-type: map` with `x-kubernetes-list-map-keys` so server-side apply can manage individual list entries instead of treating the whole array as one atomic field. The key must be stable and unique for the list, such as `containerPort` or a port `name`, depending on your API semantics. This lets separate field managers own different entries without replacing the entire list. The design still needs validation to prevent duplicate or ambiguous keys.

</details>

<details>
<summary>6. A user omits `replicas`, but the schema has `default: 2` and a CEL rule requiring `replicas >= minReplicas`. The manifest includes `minReplicas: 1`. Does validation pass, and why?</summary>

Validation passes because CRD defaulting runs before validation. The API server inserts `replicas: 2` into the object, and the CEL rule evaluates against the defaulted object rather than the user's original sparse manifest. The stored resource then contains the explicit default value, which makes later reads and controller behavior consistent. If the default would violate another rule, the request would fail after defaulting.

</details>

<details>
<summary>7. Operators say `kubectl get backuppolicies` wraps on small terminals, but they still need detailed diagnostic fields sometimes. How should you configure printer columns?</summary>

Keep only the essential fields at priority zero, because those columns are shown in normal `kubectl get` output. Move secondary fields such as detailed reason strings, backup counts, or timestamps to priority one or higher so they appear with `-o wide`. This gives routine triage a compact default view while preserving detail for power users. Test the JSONPath for missing status fields so new objects do not produce confusing output.

</details>

<details>
<summary>8. A developer writes `imgae` instead of `image` in a strict custom resource manifest that omits the required `image` field. What happens?</summary>

The apply fails validation because `spec.image` is required. If the schema did not mark `image` as required and the manifest contained only the misspelled `imgae` field, the API server would prune that unknown field during admission because the CRD has a structural schema that does not include `imgae`. Pruning removes fields outside the declared schema before persistence, which keeps stored objects aligned with the API contract. The fix is to require important fields and use server-side dry run tests that include common typos and omissions.

</details>

---

## Hands-On Exercise

Exercise scenario: you are publishing a `BackupPolicy` API for application teams that need scheduled backups for workloads and persistent data. The API starts with a simple `v1alpha1` shape and evolves into a richer `v1beta1` shape with structured retention, target selectors, notifications, status, and printer columns. Your goal is not to build the backup controller yet; your goal is to make the Kubernetes API contract strong enough that a future controller receives valid, bounded, and discoverable objects.

### Task 1: Create the CRD

Apply a CRD that serves both versions, marks `v1beta1` as storage, deprecates `v1alpha1`, enables status, and publishes useful printer columns. Because `v1alpha1` and `v1beta1` use different schemas and this CRD has no `spec.conversion` block, the default `None` strategy only relabels `apiVersion` — cross-version reads return stored fields untranslated. In production you would add `spec.conversion.strategy: Webhook` or keep version schemas compatible. Read the manifest before running it and identify which validation rule prevents `retention.maxCount` from being lower than `retention.minCount`.

```bash
cat << 'CRDEOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backuppolicies.data.kubedojo.io
spec:
  group: data.kubedojo.io
  names:
    kind: BackupPolicy
    listKind: BackupPolicyList
    plural: backuppolicies
    singular: backuppolicy
    shortNames:
    - bp
    categories:
    - kubedojo
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: false
    deprecated: true
    deprecationWarning: "data.kubedojo.io/v1alpha1 BackupPolicy is deprecated; use v1beta1"
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required:
            - schedule
            - target
            properties:
              schedule:
                type: string
              retentionDays:
                type: integer
                minimum: 1
                maximum: 365
                default: 30
              target:
                type: string
          status:
            type: object
            properties:
              lastBackup:
                type: string
                format: date-time
              backupCount:
                type: integer
    additionalPrinterColumns:
    - name: Schedule
      type: string
      jsonPath: .spec.schedule
    - name: Retention
      type: integer
      jsonPath: .spec.retentionDays
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp

  - name: v1beta1
    served: true
    storage: true
    subresources:
      status: {}
    additionalPrinterColumns:
    - name: Schedule
      type: string
      jsonPath: .spec.schedule
    - name: Retention
      type: string
      jsonPath: .spec.retention.maxAge
    - name: Last Backup
      type: string
      jsonPath: .status.lastBackupTime
    - name: Status
      type: string
      jsonPath: .status.phase
    - name: Backups
      type: integer
      jsonPath: .status.successfulBackups
      priority: 1
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
    schema:
      openAPIV3Schema:
        type: object
        required:
        - spec
        properties:
          spec:
            type: object
            required:
            - schedule
            - target
            x-kubernetes-validations:
            - rule: "self.retention.maxCount >= self.retention.minCount"
              message: "maxCount must be >= minCount"
            properties:
              schedule:
                type: string
                description: "Cron schedule expression."
                minLength: 9
                maxLength: 100
              paused:
                type: boolean
                default: false
              retention:
                type: object
                properties:
                  maxAge:
                    type: string
                    description: "Maximum age (e.g., 30d, 12h)."
                    pattern: '^[0-9]+(d|h|m)$'
                    default: "30d"
                  maxCount:
                    type: integer
                    minimum: 1
                    maximum: 1000
                    default: 100
                  minCount:
                    type: integer
                    minimum: 1
                    maximum: 100
                    default: 3
              target:
                type: object
                required:
                - kind
                properties:
                  kind:
                    type: string
                    enum: ["Deployment", "StatefulSet", "PersistentVolumeClaim", "Namespace"]
                  name:
                    type: string
                  labelSelector:
                    type: object
                    properties:
                      matchLabels:
                        type: object
                        additionalProperties:
                          type: string
              notifications:
                type: array
                maxItems: 5
                items:
                  type: object
                  required:
                  - type
                  - endpoint
                  properties:
                    type:
                      type: string
                      enum: ["slack", "email", "webhook"]
                    endpoint:
                      type: string
                    onlyOnFailure:
                      type: boolean
                      default: true
          status:
            type: object
            properties:
              phase:
                type: string
                enum: ["Active", "Paused", "Failing", "Unknown"]
              lastBackupTime:
                type: string
                format: date-time
              nextBackupTime:
                type: string
                format: date-time
              successfulBackups:
                type: integer
              failedBackups:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  required:
                  - type
                  - status
                  properties:
                    type:
                      type: string
                    status:
                      type: string
                      enum: ["True", "False", "Unknown"]
                    reason:
                      type: string
                    message:
                      type: string
                    lastTransitionTime:
                      type: string
                      format: date-time
CRDEOF
```

<details>
<summary>Solution notes</summary>

The cross-field rule is attached to `spec` in the `v1beta1` schema and compares `self.retention.maxCount` with `self.retention.minCount`. If the CRD applies successfully, Kubernetes has accepted the structural schema and registered the resource path. If the apply fails, inspect the validation error first rather than changing the controller, because the controller is not involved in CRD registration.

</details>

```bash
# Wait for the CRD to become established before using it
kubectl wait --for=condition=established crd/backuppolicies.data.kubedojo.io
```

### Task 2: Create a Valid BackupPolicy

Create a `v1beta1` resource that exercises schedule, retention, target, and notification fields. The Slack endpoint uses a training value that is clearly not a real credential, because examples should teach structure without teaching learners to paste secrets into repositories.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: data.kubedojo.io/v1beta1
kind: BackupPolicy
metadata:
  name: daily-db-backup
  namespace: default
spec:
  schedule: "0 2 * * *"
  retention:
    maxAge: "30d"
    maxCount: 90
    minCount: 7
  target:
    kind: StatefulSet
    name: postgres
  notifications:
  - type: slack
    endpoint: "https://hooks.slack.com/services/YOUR/WEBHOOK/HERE"
    onlyOnFailure: true
EOF
```

<details>
<summary>Solution notes</summary>

This object should be accepted because it includes both required `spec` fields, satisfies the retention relationship, and uses a notification object with the required `type` and `endpoint`. After creation, read the object back and notice that defaults such as `paused` may appear even though you did not provide them. That confirms defaulting happened before storage.

</details>

### Task 3: Verify Discovery and Printer Columns

Use discovery and normal `kubectl get` output to confirm the API is usable by humans and automation. The short name is convenient interactively, but the full command remains readable in scripts and module examples.

```bash
kubectl get backuppolicies
kubectl get bp              # shortName
kubectl get bp -o wide      # includes priority 1 columns
```

<details>
<summary>Solution notes</summary>

The default output should include schedule, retention, last backup, status, and age columns. Because no controller is updating status in this exercise, some status columns may be empty, and that is expected. The `-o wide` output should include the priority-one backup count column, which demonstrates how printer column priority controls default width.

</details>

### Task 4: Test Validation Failures

Submit invalid resources with server feedback visible. These examples deliberately use `|| true` so a shell session can continue after the expected failure, but do not interpret a continued shell as a successful Kubernetes request.

```bash
# Missing required field
cat << 'EOF' | kubectl apply -f - 2>&1 || true
apiVersion: data.kubedojo.io/v1beta1
kind: BackupPolicy
metadata:
  name: bad-policy-1
spec:
  schedule: "0 2 * * *"
EOF

# Invalid retention (minCount > maxCount)
cat << 'EOF' | kubectl apply -f - 2>&1 || true
apiVersion: data.kubedojo.io/v1beta1
kind: BackupPolicy
metadata:
  name: bad-policy-2
spec:
  schedule: "0 2 * * *"
  retention:
    maxCount: 2
    minCount: 10
  target:
    kind: Deployment
    name: my-app
EOF
```

<details>
<summary>Solution notes</summary>

The first request should fail because `target` is required, and the second should fail because the CEL rule rejects the retention relationship. Both failures happen during admission, before the objects are stored. If an invalid object appears in `kubectl get backuppolicies`, review the schema location of the rule and confirm you applied the latest CRD definition.

</details>

### Task 5: Test the Deprecated Version

Create an object through the deprecated version to observe the deprecation warning and reinforce the difference between served versions and the storage version. This is the kind of compatibility bridge you use while migrating old manifests.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: data.kubedojo.io/v1alpha1
kind: BackupPolicy
metadata:
  name: old-style-backup
spec:
  schedule: "0 3 * * 0"
  retentionDays: 14
  target: "deployment/web"
EOF
# You should see a deprecation warning
```

<details>
<summary>Solution notes</summary>

The request should still succeed because `v1alpha1` is served, but the warning tells users which version to adopt. Because `v1beta1` is storage and the two versions have different shapes with default `None` conversion, reading the object as `v1beta1` returns the stored `v1alpha1` fields without translating `target: "deployment/web"` into the structured `v1beta1` target object. This exercise focuses on the CRD surface, so treat the warning as a prompt to plan a conversion webhook before a real migration.

</details>

### Task 6: Cleanup

Delete the resources and the CRD when you are finished. Removing the CRD removes the custom resource endpoint and the stored custom resources, so only run cleanup in a disposable learning cluster.

```bash
kubectl delete backuppolicies --all
kubectl delete crd backuppolicies.data.kubedojo.io
```

<details>
<summary>Solution notes</summary>

After cleanup, `kubectl api-resources | grep backuppolicies` should no longer show the resource. If resources remain, check namespaces and finalizers before assuming the CRD delete failed. A real operator may add finalizers to custom resources, which can delay deletion until cleanup logic completes.

</details>

**Success Criteria**:

- [ ] CRD registers successfully with both versions.
- [ ] Valid resources create without errors.
- [ ] Invalid resources are rejected with clear error messages.
- [ ] CEL cross-field validation works for `minCount <= maxCount`.
- [ ] Printer columns display correctly in default and wide output.
- [ ] Short name `bp` works for interactive discovery.
- [ ] `v1alpha1` shows a deprecation warning.
- [ ] Status subresource is enabled when you inspect the CRD.

---

## Sources

- https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/
- https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/
- https://kubernetes.io/docs/reference/kubernetes-api/extend-resources/custom-resource-definition-v1/
- https://kubernetes.io/docs/reference/using-api/api-concepts/
- https://kubernetes.io/docs/reference/using-api/deprecation-policy/
- https://kubernetes.io/docs/reference/using-api/cel/
- https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
- https://kubernetes.io/docs/reference/using-api/server-side-apply/
- https://kubernetes.io/docs/tasks/manage-kubernetes-objects/update-api-object-kubectl-patch/
- https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- https://kubernetes.io/docs/reference/kubectl/jsonpath/

## Next Module

[Module 1.3: Building Controllers with client-go](../module-1.3-controllers-client-go/) - Write a complete Kubernetes controller from scratch using the API design patterns you practiced in Modules 1.1 and 1.2.
