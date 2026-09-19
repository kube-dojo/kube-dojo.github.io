---
citations_verified: true
title: "Module 1.4: Kustomize - Template-Free Configuration"
slug: k8s/cka/part1-cluster-architecture/module-1.4-kustomize
revision_pending: false
sidebar:
  order: 5
lab:
  id: cka-1.4-kustomize
  url: https://killercoda.com/kubedojo/scenario/cka-1.4-kustomize
  duration: "35 min"
  difficulty: intermediate
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Essential CKA skill for Kubernetes 1.35+
>
> **Time to Complete**: 40-55 minutes
>
> **Prerequisites**: Module 0.1 (working cluster), basic YAML knowledge, comfortable reading Deployments and Services

---

## Learning Outcomes

After this module, you will be able to:

- **Design** a base-and-overlay directory structure that keeps shared Kubernetes manifests reusable while allowing environment-specific changes.
- **Apply** Kustomize transformations for namespaces, names, labels, images, ConfigMaps, Secrets, and patches without editing the base resources.
- **Debug** rendered Kustomize output before applying it to a cluster, using `kubectl kustomize`, `kubectl diff -k`, and dry-run validation.
- **Evaluate** when Kustomize is the right tool compared with Helm, plain `kubectl apply`, or a GitOps controller.
- **Repair** common overlay failures such as bad relative paths, patch target mismatches, selector label damage, and generator hash surprises.

---

## Why This Module Matters

Hypothetical scenario: A platform team inherits a Kubernetes repository with three nearly identical folders named `dev`, `staging`, and `prod`. Each folder contains a Deployment, Service, ConfigMap, and Ingress for the same application. During an incident, the team patches a missing readiness probe in production, then forgets to apply the same fix to staging. Two weeks later, staging passes a release candidate that production would have rejected. The outage was not caused by Kubernetes being unpredictable; it was caused by configuration drift that the repository design made easy.

Kustomize solves that exact class of problem by separating what stays the same from what changes by environment. The shared application shape lives in a base. Each environment has an overlay that references the base and describes only the differences: namespace, image tag, replica count, labels, resource limits, or generated configuration. The learner still works with normal Kubernetes YAML, but the final manifest is assembled by a deterministic renderer before `kubectl` sends anything to the API server.

For the CKA, Kustomize matters because it is built into `kubectl` and appears in practical tasks where speed and correctness both matter. You may be asked to apply a provided overlay, fix a broken `kustomization.yaml`, preview rendered output, or patch a Deployment without modifying the base. Outside the exam, the same skills show up in GitOps repositories, promotion workflows, and multi-environment application delivery.

> **The Transparent Film Analogy**
>
> Think of Kustomize like transparent film overlays on a projector. The base slide contains the stable application: Deployment, Service, labels, probes, and container ports. The production film adds five replicas and stronger resource limits. The development film adds a different namespace and a cheaper image tag. Each film changes what the audience sees, but the original slide remains intact and reusable.

---

## Part 1: The Mental Model

Kustomize is not a package manager and it is not a template engine. [It is a manifest renderer that reads Kubernetes resources, applies transformations, applies patches, runs generators, and prints the final YAML.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) That distinction matters because Kustomize does not install release history, manage chart dependencies, or remember a previous deployment. It produces manifests; `kubectl apply -k` then applies those manifests.

The first habit to build is previewing the rendered output before you apply it. The command `kubectl kustomize <directory>` prints the YAML that Kustomize would generate. The command `kubectl apply -k <directory>` renders and applies that same output. In the exam and in real clusters, previewing first catches broken paths, incorrect names, unwanted selector changes, and surprising generated names before they become API objects.

The mental model becomes easier if you separate three moments in time. First, you have source files in Git, which may include a base, one or more overlays, patches, and generator inputs. Second, Kustomize renders those files into a single stream of ordinary Kubernetes YAML. Third, `kubectl apply` compares that rendered YAML with cluster state and submits create or update requests to the API server. Most confusing Kustomize bugs happen because a learner skips the middle moment and assumes the files on disk are the same thing as the objects Kubernetes will receive.

That middle moment is also where Kustomize earns its place in a CKA workflow. You do not need a cluster to answer many questions about a broken overlay, because the renderer can prove whether paths, names, patches, and generated references line up. When a task is under time pressure, this matters more than it first appears. A failed apply can leave you reading server errors, admission messages, and partial object state, while a failed render usually points back to a specific local directory or file that you can repair directly.

```text
┌────────────────────────────────────────────────────────────────┐
│                     Kustomize Rendering Flow                    │
│                                                                │
│   base/                              overlays/prod/             │
│   ┌──────────────────────┐          ┌────────────────────────┐  │
│   │ deployment.yaml       │          │ kustomization.yaml      │  │
│   │ service.yaml          │          │ patch-replicas.yaml     │  │
│   │ kustomization.yaml    │          │ patch-resources.yaml    │  │
│   └──────────┬───────────┘          └───────────┬────────────┘  │
│              │                                  │               │
│              └──────────────┬───────────────────┘               │
│                             ▼                                   │
│                    ┌─────────────────┐                          │
│                    │ Kustomize build │                          │
│                    │ render only     │                          │
│                    └────────┬────────┘                          │
│                             ▼                                   │
│                  final Kubernetes YAML                          │
│                             │                                   │
│                 kubectl apply sends this                        │
│                             ▼                                   │
│                    Kubernetes API server                        │
└────────────────────────────────────────────────────────────────┘
```

The base should be boring. It should define the objects that every environment needs, with safe defaults and names that make sense before environment-specific prefixes are added. The overlay should be small and opinionated. It says, "for this environment, use this namespace, this image tag, these resource limits, and these generated configuration values."

A useful review question is whether a future teammate could read the base without knowing which environment will use it. If the answer is yes, the base is probably doing its job. If the base mentions production-only replica counts, development-only debug flags, or a staging-only namespace, then the repository is starting to hide environment decisions in the shared layer. Kustomize does not stop you from making that design mistake, so the discipline has to come from how you divide the files.

| Term | What it means | Practical test |
|------|---------------|----------------|
| **Base** | A directory containing reusable Kubernetes resources and a `kustomization.yaml` that lists them. | Could another environment reuse this without copying files? |
| **Overlay** | A directory with its own `kustomization.yaml` that references a base and adds environment-specific changes. | Does this contain only what differs for one environment? |
| **Patch** | A partial YAML document or JSON patch that modifies a matching resource in the rendered set. | Does the target match the resource kind and original name? |
| **Transformer** | A Kustomize feature that changes many resources, such as names, namespaces, labels, annotations, or images. | Would it apply consistently across all included resources? |
| **Generator** | A feature that creates ConfigMaps or Secrets from literals, files, or environment files. | Does the generated object name change when content changes? |
| **Rendered output** | The final YAML produced by Kustomize before it is applied to Kubernetes. | Did you inspect this before changing the cluster? |

**Pause and predict:** Before reviewing the base manifests, consider what belongs in a shared base versus an environment overlay for a web application. Should a large scale setting like `replicas: 10` be defined in the base or in an overlay?

<details>
<summary>Check your prediction</summary>

A production replica count such as `replicas: 10` belongs in an environment overlay rather than the shared base. The base should define only generic workload structures that all targets share safely, leaving environment-specific scale, resource boundaries, and capacity tuning to individual overlays.

</details>

Evaluating which fields belong in shared foundations versus environment customizations is a fundamental architectural discipline when constructing reproducible multi-cluster delivery pipelines.

---

## Part 2: Build a Clean Base

A base directory starts with normal Kubernetes manifests. There is no special syntax inside the Deployment or Service just because Kustomize will render them. This is one reason Kustomize works well for teams that already know Kubernetes YAML: the base remains readable by standard Kubernetes tooling, code review, and documentation.

The base also needs a `kustomization.yaml` file. This file is the local build recipe. It tells Kustomize which resources belong in this unit and which transformations or generators should run. [If a directory has YAML files but no `kustomization.yaml`, `kubectl apply -k` does not know how to treat it as a Kustomize package.](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/)

A common convention in interactive shells is to shorten `kubectl`, but that habit is risky in training material and copied scripts because aliases often do not expand in non-interactive execution. The CKA environment may also start from a clean shell, so this module uses the full `kubectl` command everywhere. Before you begin a timed task, a safer readiness check is to confirm that the real binary is available and that its client version prints as expected.

```bash
kubectl version --client
```

The following base defines a small web application. It deliberately keeps the namespace out of the base because namespaces usually differ by environment. It also uses stable labels for selectors and pod matching. Later sections will explain why changing selector labels casually is one of the easiest ways to break an otherwise valid overlay.

```bash
mkdir -p webapp/base
```

```yaml
# webapp/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
  labels:
    app.kubernetes.io/name: webapp
    app.kubernetes.io/component: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: webapp
      app.kubernetes.io/component: frontend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: webapp
        app.kubernetes.io/component: frontend
    spec:
      containers:
        - name: webapp
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              memory: "64Mi"
              cpu: "100m"
```

```yaml
# webapp/base/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: webapp
  labels:
    app.kubernetes.io/name: webapp
spec:
  selector:
    app.kubernetes.io/name: webapp
    app.kubernetes.io/component: frontend
  ports:
    - name: http
      port: 80
      targetPort: 80
```

```yaml
# webapp/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
```

Preview the base before creating overlays. This step teaches you to treat Kustomize as a renderer first and an apply mechanism second. If the rendered base is invalid, every overlay that references it inherits the problem.

```bash
kubectl kustomize webapp/base/
```

You should see a Deployment and a Service. Nothing has been applied to the cluster yet. The command is safe because it only prints YAML. If you want Kubernetes client-side validation without changing the cluster, pipe the rendered output to a dry-run apply.

```bash
kubectl kustomize webapp/base/ | kubectl apply --dry-run=client -f -
```

The base is intentionally minimal, but it is not a stub. It contains the API resources that define the workload shape. The overlay will decide the environment, image version, replica count, and operational policy. That separation is what prevents environment drift from becoming a maintenance habit.

Notice that the base Deployment and Service use the same stable label pair for the selector relationship. This is deliberate because selector labels are part of the contract between objects, not merely decorative metadata. A Service that selects pods by `app.kubernetes.io/name` and `app.kubernetes.io/component` must continue to find pods after the overlay renders. When you later add environment labels, prefixes, and image changes, you should verify that those changes do not accidentally change the meaning of the selector contract.

There is also a practical exam reason to keep the base small and conventional. If the base is valid Kubernetes YAML, you can reason about it with the same habits you already use for Deployments and Services. You can inspect `spec.selector.matchLabels`, compare it with the pod template labels, and check the container image without learning a second syntax. Kustomize adds composition around those objects; it does not replace the need to understand the objects themselves.

---

## Part 3: Add Overlays Without Copying the Base

An overlay references the base by relative path. If the overlay is in `webapp/overlays/dev/`, then `../../base` means "go up from `dev` to `overlays`, go up from `overlays` to `webapp`, then enter `base`." Most beginner Kustomize failures are not YAML syntax failures; they are path failures caused by counting directory levels incorrectly.

The development overlay below adds a namespace, a name prefix, and an environment label. The prefix prevents name collisions when multiple rendered variants share a cluster. The namespace keeps objects in the correct administrative boundary. The label makes it easy to query, filter, and operate on all resources for the development environment.

```bash
mkdir -p webapp/overlays/dev webapp/overlays/prod
```

```yaml
# webapp/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: dev-
namespace: development

labels:
  - pairs:
      environment: dev
      app.kubernetes.io/managed-by: kustomize
    includeSelectors: false
```

The `labels` transformer is safer here than a blind selector-changing label strategy. Environment labels are useful on object metadata and pod templates, but adding them to selectors can make Services and Deployments select a narrower set of pods than you intended. For a new workload, selector changes may work. For an existing workload, selector mutations can fail because Deployment selectors are immutable.

The important phrase in that paragraph is "for an existing workload." Kubernetes allows many fields to change over time, but [it treats a Deployment selector as identity, not decoration](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/). If a label transformer changes selectors after the Deployment already exists, the API server may reject the update because the controller would no longer own the same pod set. Even if an object is new and the apply succeeds, selector changes can still surprise operators because the Service and Deployment may stop agreeing about which pods are part of the application.

**Pause and predict:** When Kustomize renders an overlay configured with `namePrefix: dev-` targeting a base with a Service named `webapp`, will the resulting Service be named `webapp`, `dev-webapp`, or `webapp-dev`?

<details>
<summary>Check your prediction</summary>

The rendered Service will be named `dev-webapp`. The transformer prepends prefix strings directly to `metadata.name` across all managed resources in the compilation unit.

</details>

Examining rendered resource identifiers prior to applying an overlay ensures that internal network routing, service discovery endpoints, and ingress definitions align predictably across deployment environments.

```bash
kubectl kustomize webapp/overlays/dev/
```

A production overlay usually needs stronger differences. It may change replicas, image tags, resource limits, generated configuration, or annotations used by policy and observability tools. The key is that the overlay still avoids copying the entire Deployment. It expresses only the production-specific decisions.

Production is the environment where overlay discipline pays off most clearly. You want production to be different where operations require it, but you do not want production to become a fork of the application definition. Five replicas, stronger resource limits, a production namespace, and a hardened image tag are legitimate production decisions. Copying the whole Deployment just to express those decisions creates a second source of truth, and that second source will eventually miss a shared fix unless review culture is unusually strict.

```yaml
# webapp/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: prod-
namespace: production

labels:
  - pairs:
      environment: production
      app.kubernetes.io/managed-by: kustomize
    includeSelectors: false

images:
  - name: nginx
    newTag: "1.25-alpine"

patches:
  - path: patch-replicas.yaml
  - path: patch-resources.yaml
```

```yaml
# webapp/overlays/prod/patch-replicas.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  replicas: 5
```

```yaml
# webapp/overlays/prod/patch-resources.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  template:
    spec:
      containers:
        - name: webapp
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

Notice the patch target name: `webapp`, not `prod-webapp`. [Kustomize matches patches against the original resource identity before the name prefix is applied.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) This surprises learners because the final object name includes the prefix, but the patch file still describes the base resource it wants to modify.

Preview production and inspect the output carefully. The final Deployment name should include the prefix, the namespace should be production, the image tag should be changed, and the replica count should be five. If any of those are missing, fix the render before applying to a cluster.

```bash
kubectl kustomize webapp/overlays/prod/
```

---

## Part 4: Transformers as Controlled Bulk Edits

Transformers are powerful because they apply a consistent change across many resources. They are also risky because a broad transformation can affect more fields than a beginner expects. The right way to use them is to understand which fields they touch, preview output, and keep environment overlays narrow enough that review stays meaningful.

Think of a transformer as a controlled bulk edit with Kubernetes awareness. A text editor search-and-replace can change names in places where they are comments, examples, or unrelated strings. Kustomize transformers operate on structured resource fields and, for known reference relationships, update related fields together. That structure is useful, but it does not remove judgment. You still need to decide whether a bulk edit is the clearest expression of intent or whether a targeted patch would be safer for a single object.

The name transformers are straightforward. `namePrefix` prepends text to resource names, while `nameSuffix` appends text. Kustomize also updates internal references when it understands the relationship, such as a Deployment referring to a generated ConfigMap. This is one reason Kustomize is better than simple search-and-replace.

```yaml
# Example name transformation
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: prod-
nameSuffix: -blue
```

```text
┌──────────────────────────┐
│ Base name                │
│ webapp                   │
└─────────────┬────────────┘
              │ namePrefix: prod-
              │ nameSuffix: -blue
              ▼
┌──────────────────────────┐
│ Rendered name            │
│ prod-webapp-blue         │
└──────────────────────────┘
```

The namespace transformer sets `metadata.namespace` on namespaced resources. [It does not make cluster-scoped resources namespaced.](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) A Namespace object, ClusterRole, ClusterRoleBinding, CustomResourceDefinition, and StorageClass are cluster-scoped, so the namespace transformer cannot turn them into namespaced objects. This is important when an overlay includes both application resources and cluster-level resources.

```yaml
# Example namespace transformation
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: production
```

The image transformer is the preferred way to change image tags when the image name already exists in the base. It avoids writing a patch against the nested container list, and it is easier to scan during review. It can change the tag, the registry, or both.

```yaml
# Example image transformation
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: nginx
    newName: registry.example.com/platform/nginx
    newTag: "1.25-alpine"
```

Labels deserve special care. Older examples often use `commonLabels`, which can add labels to selectors as well as object metadata. That can be acceptable when creating a brand-new workload, but it is dangerous when updating a live Deployment because selector fields are immutable. [Prefer the newer `labels` transformer when you need control over whether selector fields are included.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)

```yaml
# Safer label transformation for environment metadata
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

labels:
  - pairs:
      environment: production
      team: platform
    includeSelectors: false
```

| Transformer | What it changes | Main risk | Safer habit |
|-------------|-----------------|-----------|-------------|
| `namePrefix` | Resource names and known references. | Patches written against prefixed names do not match. | Patch the base name and preview final names. |
| `nameSuffix` | Resource names and known references. | Long names may exceed Kubernetes name length limits. | Keep suffixes short and environment-oriented. |
| `namespace` | Namespaced resource metadata. | Cluster-scoped resources remain cluster-scoped. | Preview mixed resource sets before applying. |
| `images` | Container image references matching the original image name. | A name mismatch leaves the image unchanged. | Preview and search rendered output for `image:`. |
| `labels` | Metadata, selectors, and templates depending on options. | Selector changes can break or be rejected. | Use `includeSelectors: false` for operational labels. |
| `commonAnnotations` | Object annotations. | Sensitive values may be exposed in metadata. | Keep secrets in Secret data, not annotations. |

A senior-level Kustomize review asks whether the transformer expresses intent better than a patch. If you are changing every resource in the overlay, a transformer is clearer. If you are changing one field on one object, a patch is often clearer. If you are changing behavior that Kubernetes treats as immutable, you need to plan a migration instead of assuming the renderer can force it through.

The review should also ask whether the rendered output will be understandable to someone debugging the cluster later. A namespace transformer is easy to explain because every namespaced object lands in the environment namespace. An image transformer is easy to explain because the base image name maps to a specific tag or registry in that overlay. A broad label rule with selector inclusion is harder to explain because it can affect metadata, pod templates, and controller selectors at once. When the effect is broad, the preview step becomes part of the design, not just a final check.

---

## Part 5: Patches and Why Names Matter

Patches are how overlays make targeted changes to resources from the base. The two practical patch styles you will see most often are strategic merge patches and JSON 6902 patches. Strategic merge patches look like partial Kubernetes objects. [JSON patches look like a list of operations against JSON paths.](https://www.rfc-editor.org/rfc/rfc6902) Both are useful, but they solve different problems.

The strongest reason to use a patch is that the change belongs to one object, not to the whole overlay. A replica count, readiness probe, resource limit, or pod security setting may be production-specific, but it does not necessarily need a transformer that touches every resource. Patches let you keep the base readable while expressing the operational difference near the environment that owns it. The trade-off is that patch identity must be exact: the kind, name, API version, and list merge keys have to match what Kustomize is rendering.

Strategic merge is usually easier for Kubernetes-native objects such as Deployments. It understands merge keys for many Kubernetes lists. For example, containers merge by `name`, so a patch that mentions the `webapp` container modifies that container instead of replacing the entire container list. This is exactly why container names must be accurate.

```yaml
# webapp/overlays/prod/patch-probes.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  template:
    spec:
      containers:
        - name: webapp
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
```

[If the base container is named `webapp` and the patch uses `app`, the strategic merge patch can add a second container instead of modifying the existing one.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/update-api-object-kubectl-patch/) That rendered YAML may even be valid Kubernetes YAML while still being operationally wrong. This is why previewing the full output and reading the container list matters.

> **What would happen if:** Your production patch references a container named `app`, but the base Deployment's container is named `webapp`. Before running the command, decide whether you expect a validation error, a new container, or a modified existing container. Then render the overlay and inspect `spec.template.spec.containers`.

JSON 6902 patches are better when you need exact operations, especially against scalar fields or lists where strategic merge behavior is not what you want. They are also useful when you want the patch to fail if a path is missing, because a `replace` operation expects the target path to exist.

```yaml
# webapp/overlays/prod/kustomization.yaml fragment
patches:
  - target:
      kind: Deployment
      name: webapp
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 5
      - op: add
        path: /metadata/annotations/reviewed-by
        value: platform-team
```

Patch targeting can also use kind, name, namespace, group, version, and label selectors. For exam work, target by kind and name unless the task clearly asks for label selection. For repository work, target enough identity to make accidental matches unlikely.

```yaml
# Target one Deployment by kind and base name
patches:
  - path: patch-resources.yaml
    target:
      kind: Deployment
      name: webapp
```

```yaml
# Target all frontend Deployments by label
patches:
  - path: patch-frontend-memory.yaml
    target:
      kind: Deployment
      labelSelector: "app.kubernetes.io/component=frontend"
```

| Patch style | Best use | Example decision | Failure mode to check |
|-------------|----------|------------------|-----------------------|
| Strategic merge | Kubernetes-native objects where partial YAML is readable. | Add resources, probes, replicas, or pod security context. | Wrong list merge key creates a new list item. |
| JSON 6902 | Precise operations against exact paths. | Replace `/spec/replicas` or add a single annotation. | Wrong path fails or modifies an unintended path. |
| Targeted patch | One resource needs a known change. | Patch only `Deployment/webapp`. | Target name uses rendered name instead of base name. |
| Label-selected patch | A class of resources needs the same change. | Patch all frontend Deployments. | Selector matches more resources than intended. |

The senior habit is to make patch intent obvious during review. A patch file named `patch.yaml` forces reviewers to open it before they know what risk it carries. A patch named `patch-resources.yaml` or `patch-readiness-probe.yaml` tells the reviewer what behavior should change and makes accidental scope creep easier to spot.

Patch files should be small enough that a reviewer can answer two questions quickly. What resource is this patch supposed to match, and what behavior is it supposed to change? If a patch changes replicas, resources, probes, labels, and annotations at the same time, it is harder to detect an accidental selector mutation or a container-name mismatch. Splitting patches by intent is not ceremony; it is a way to make rendered-output review faster and more reliable when a repository grows beyond one application.

---

## Part 6: ConfigMap and Secret Generators

Generators create ConfigMaps and Secrets from files, literals, or environment files. They are useful because configuration content often belongs near the overlay that owns it. A development overlay may set a verbose log level. A production overlay may set a stricter timeout. The generator keeps that environment-owned configuration close to the environment-owned kustomization.

Generators also make configuration changes visible in the same review as workload changes. If a production overlay changes a timeout file and a resource limit patch together, reviewers can reason about both effects before the manifest is applied. Without a generator, teams often hand-create ConfigMaps in a separate folder or apply them manually, which weakens the link between the application version and the configuration it expects. Kustomize does not solve every configuration-management problem, but it gives you a clean way to keep ordinary ConfigMap and Secret inputs inside the overlay boundary.

The most important generator behavior is the hash suffix. By default, Kustomize appends a content hash to generated ConfigMap and Secret names. When the content changes, the generated name changes. If a Deployment references that generated object through Kustomize-managed name references, the Pod template changes too, which triggers a rollout.

```bash
mkdir -p webapp/overlays/prod/config
```

```bash
cat > webapp/overlays/prod/config/app.properties << 'EOF'
LOG_LEVEL=info
FEATURE_FLAGS=checkout-v2
REQUEST_TIMEOUT_SECONDS=10
EOF
```

```yaml
# webapp/overlays/prod/kustomization.yaml fragment
configMapGenerator:
  - name: webapp-config
    files:
      - config/app.properties
```

A Deployment can consume that generated ConfigMap by the logical name from the generator. [Kustomize rewrites the reference to the hashed rendered name.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) This is the useful part: you write the stable logical name, and Kustomize keeps the applied name content-addressed.

```yaml
# Example base Deployment fragment
envFrom:
  - configMapRef:
      name: webapp-config
```

```text
┌──────────────────────────┐
│ Generator logical name   │
│ webapp-config            │
└─────────────┬────────────┘
              │ content changes
              ▼
┌──────────────────────────┐
│ Rendered ConfigMap name  │
│ webapp-config-abc123     │
└─────────────┬────────────┘
              │ Deployment reference rewritten
              ▼
┌──────────────────────────┐
│ Pod template changes     │
│ rollout is triggered     │
└──────────────────────────┘
```

Secrets can be generated the same way, but generating a Secret does not make secret handling secure by itself. If you commit plaintext password files to Git, Kustomize will faithfully create Secrets from leaked material. For real environments, use sealed secrets, external secret operators, SOPS, or another secret management workflow. For the CKA, you only need to understand the Kustomize mechanics.

```yaml
# webapp/overlays/prod/kustomization.yaml fragment
secretGenerator:
  - name: webapp-db
    literals:
      - username=webapp
      - password=change-me-in-real-life
    type: Opaque
```

**Pause and predict:** If a team configures `disableNameSuffixHash: true` on a ConfigMap generator and subsequently alters the data payload, will existing Pods automatically restart when the updated manifest is applied?

<details>
<summary>Check your prediction</summary>

Existing Pods will not roll automatically when applied. Because the generated ConfigMap name remains static, the Deployment pod template specification is unchanged, leaving the controller with no trigger to initiate a rolling update.

</details>

Understanding how workload controllers evaluate template mutations prevents silent divergence between runtime process state and updated configuration stored in the cluster.

Legacy software stacks occasionally mandate predictable configuration object names rather than generated hashed identifiers. Disabling hash generation accommodates those naming constraints but requires deliberate operational intervention whenever configuration values must take effect immediately.

```yaml
# Disabling the generator hash suffix
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

configMapGenerator:
  - name: webapp-config
    literals:
      - LOG_LEVEL=info

generatorOptions:
  disableNameSuffixHash: true
```

[The field name is `disableNameSuffixHash`, not `disableNameSuffix`.](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) This detail matters in troubleshooting because examples from memory or outdated notes can lead to a kustomization that does not behave as expected. When in doubt, render output and inspect the generated names instead of assuming the option worked.

Hash suffixes are worth keeping unless you can name the system that truly requires stable generated object names. With the suffix enabled, a ConfigMap content change becomes a name change, and a rewritten pod template reference gives the Deployment controller a reason to create new Pods. With the suffix disabled, the object data can change while the pod template stays identical, so existing Pods may continue running with older environment-derived configuration until something else restarts them. That difference is easy to miss if you only inspect the ConfigMap and forget to inspect the Deployment template.

---

## Part 7: Debugging Kustomize Like an Operator

Debugging Kustomize starts before you talk to the API server. If rendering fails, Kubernetes never sees the resources. If rendering succeeds but the output is wrong, Kubernetes may accept an object that behaves differently than you intended. The safest workflow is render, inspect, validate, diff, then apply.

This order is intentionally conservative because it separates local mistakes from cluster mistakes. A bad relative path, missing kustomization file, or unmatched patch target is a local composition problem. A rejected immutable selector, missing namespace, or failed admission policy is a cluster interaction problem. If you apply before rendering, these categories blur together and you spend time asking the API server questions that the local renderer could have answered faster.

```bash
kubectl kustomize webapp/overlays/prod/
```

Use `grep` or `yq` if available to inspect a specific field quickly, but do not depend on them in the exam unless you know they exist. Plain `kubectl kustomize` output is enough for most tasks. Search the rendered YAML for `name:`, `namespace:`, `image:`, `replicas:`, and any field the task specifically asked you to change.

```bash
kubectl kustomize webapp/overlays/prod/ | grep -E "name:|namespace:|image:|replicas:"
```

Dry-run validation catches API-level mistakes without creating resources. It is not a full server-side admission test when using client dry-run, but it catches many structural errors. Server dry-run can be stronger when the API server is reachable and supports the resource types involved.

```bash
kubectl kustomize webapp/overlays/prod/ | kubectl apply --dry-run=client -f -
```

```bash
kubectl apply --dry-run=server -k webapp/overlays/prod/
```

[Diff shows what would change compared with the current cluster.](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/) This is useful when a rendered overlay is valid but may update existing objects in surprising ways. In a GitOps workflow, the controller may perform the apply, but the human still benefits from rendering and diffing locally during review.

```bash
kubectl diff -k webapp/overlays/prod/
```

Apply only after the render matches the task. In the CKA, create namespaces first if the overlay expects them and the task does not provide them. Kustomize setting `namespace: production` does not automatically create the Namespace object unless you include a Namespace resource.

```bash
kubectl create namespace production
kubectl apply -k webapp/overlays/prod/
kubectl get deploy,svc -n production
```

A good troubleshooting sequence is intentionally repetitive. First, prove the path exists. Second, prove the base renders. Third, prove the overlay renders. Fourth, prove the rendered output contains the intended change. Fifth, apply or diff. This sequence prevents you from debugging the cluster when the problem is really a relative path in a local directory.

```text
┌──────────────────────────────┐
│ Kustomize troubleshooting    │
└───────────────┬──────────────┘
                ▼
┌──────────────────────────────┐
│ Does the overlay path exist? │
└───────────────┬──────────────┘
                ▼
┌──────────────────────────────┐
│ Does the base render alone?  │
└───────────────┬──────────────┘
                ▼
┌──────────────────────────────┐
│ Does the overlay render?     │
└───────────────┬──────────────┘
                ▼
┌──────────────────────────────┐
│ Is the intended field right? │
└───────────────┬──────────────┘
                ▼
┌──────────────────────────────┐
│ dry-run, diff, then apply    │
└──────────────────────────────┘
```

When an overlay fails with a resource accumulation error, read the path in the error message literally. It usually tells you which file or directory Kustomize tried to load. When a patch appears to do nothing, check the target kind, target name, API version, and container names. When a generated ConfigMap does not roll pods, inspect whether the Deployment reference was rewritten and whether hash suffixing was disabled.

For CKA practice, build a habit of writing down the intended field before you run the command. If the task says production should have five replicas, ask where that number should appear in the rendered Deployment and then verify exactly that field. If the task says the production image should use a specific tag, search for `image:` in the rendered output and confirm that the tag changed in the container you intended. This small pause turns Kustomize debugging from "look at a wall of YAML" into "prove or disprove one expectation at a time."

---

## Part 8: Kustomize vs Helm vs Plain Manifests

Kustomize, Helm, and plain manifests can all deploy Kubernetes objects, but they optimize for different situations. Plain manifests are easiest when there is only one environment and little variation. Kustomize is strongest when you own the manifests and need environment overlays without templates. [Helm is strongest when you want packaging, values files, dependencies, and release history.](https://helm.sh/docs/topics/charts/)

The comparison is not about which tool is more professional. It is about where the variation lives and who owns the source material. If you own a Deployment and need three environment variants, Kustomize lets you keep ordinary Kubernetes YAML while expressing differences without copying the whole object. If you consume a third-party application that already ships as a chart, Helm may give you a better supported interface than editing rendered YAML directly. If you need one temporary debug Pod, plain manifests are simpler than building a directory hierarchy around it.

Another useful way to decide is to ask who should be able to review the change. Kustomize overlays are friendly to Kubernetes reviewers because the final intent remains close to standard manifests: a Deployment patch still looks like part of a Deployment, and an image transformer still names an image. Helm values can be cleaner for packaged software, but the relationship between a value and the rendered object may require chart knowledge. Plain manifests are the easiest to read for one-off work, but they provide no built-in answer when the same object needs controlled differences across environments.

The wrong decision often shows up as friction during change. If every environment folder contains copied YAML, plain manifests have exceeded their useful size. If a Kustomize repository starts simulating conditionals, loops, and reusable functions, the team may be trying to use Kustomize as a template language. If a Helm chart has only one Deployment and three values, Helm may be more machinery than the task needs.

| Aspect | Plain manifests | Kustomize | Helm |
|--------|-----------------|-----------|------|
| Primary model | Apply YAML files directly. | Render bases plus overlays. | Render charts with templates and values. |
| Best fit | Single environment or simple demos. | Owned manifests with controlled environment differences. | Packaged applications, dependencies, release lifecycle. |
| Template language | None. | None. | Go templates. |
| Built into `kubectl` | Yes, through normal apply. | Yes, through `kubectl apply -k` and `kubectl kustomize`. | No, separate Helm CLI. |
| Release history | No. | No. | Yes, Helm releases track revisions. |
| Drift control | Manual unless paired with GitOps. | Strong repository structure, stronger with GitOps. | Stronger release model, stronger with GitOps. |
| Exam speed | Fast for simple resources. | Fast for overlays and patch tasks. | Useful when chart tasks are explicit. |

For the CKA, choose the tool the task asks for. If the task says apply a Kustomize configuration, use `kubectl apply -k`. If it asks you to preview a Kustomize directory, use `kubectl kustomize`. If it asks for a Helm release, use Helm. Do not convert a Kustomize task into a Helm task because you prefer Helm; the grader expects a specific cluster outcome and sometimes a specific workflow.

In real teams, Kustomize often pairs with GitOps controllers such as Argo CD or Flux. The repository contains bases and overlays. [The controller watches an overlay path and applies the rendered output.](https://fluxcd.io/flux/components/kustomize/kustomizations/) Rollback then comes from Git history or controller sync behavior, not from Kustomize itself. That division is healthy: Kustomize renders configuration, while GitOps manages continuous reconciliation.

---

## Part 9: Worked Example - Fix a Broken Production Overlay

Exercise scenario: A team reports that `kubectl apply -k webapp/overlays/prod/` fails after a directory cleanup. The base still exists, but the overlay cannot find it. Instead of editing randomly, debug the render path first.

Broken overlay:

```yaml
# webapp/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../base

namePrefix: prod-
namespace: production
```

The overlay lives at `webapp/overlays/prod/`. From there, `../base` means `webapp/overlays/base`, which does not exist. The correct path is `../../base`, because the overlay must go up to `overlays`, then up to `webapp`, then down into `base`.

Corrected overlay:

```yaml
# webapp/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: prod-
namespace: production
```

Now render before applying:

```bash
kubectl kustomize webapp/overlays/prod/
```

Suppose the render succeeds, but the production task also requires five replicas and the rendered Deployment still has one. Add a patch with the base resource name, not the prefixed final name.

```yaml
# webapp/overlays/prod/patch-replicas.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  replicas: 5
```

```yaml
# webapp/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: prod-
namespace: production

patches:
  - path: patch-replicas.yaml
```

Finally, render and check the exact field:

```bash
kubectl kustomize webapp/overlays/prod/ | grep -A 8 "kind: Deployment"
```

This example is small, but it models the senior workflow. You corrected the path, verified the render, added the smallest patch that expressed the production difference, and verified the rendered field before applying. The important skill is not memorizing this exact file layout; it is following a repeatable reasoning path when Kustomize output surprises you.

That reasoning path scales beyond the example because it keeps the question narrow at each step. A broken path is repaired in the overlay recipe, not in the Deployment. A missing replica change is repaired in the patch target, not by copying the full base into production. A confusing final name is explained by the order of Kustomize transformations, not by guessing that Kubernetes renamed the object after apply. When you can name the layer that owns the symptom, Kustomize stops feeling like magic and starts behaving like a deterministic build step.

---

## Did You Know?

- **[Kustomize has been built into `kubectl` since Kubernetes v1.14](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)**: That makes it practical in exam environments because you can use `kubectl kustomize` and `kubectl apply -k` without installing a separate binary.
- **GitOps tools commonly understand Kustomize paths directly**: [Argo CD](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/) and Flux can watch an overlay directory, render it, and continuously reconcile the resulting resources to a cluster.
- **Generated ConfigMap and Secret names are content-sensitive by default**: The hash suffix changes when generator input changes, which helps trigger Deployment rollouts when Pod template references are rewritten.
- **[Kustomize can be combined with Helm in advanced workflows](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/)**: Teams sometimes render or inflate Helm chart output and then apply Kustomize overlays, but this adds complexity and should be justified by a real need.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|--------------|---------------|
| Referencing the base with the wrong relative path | Kustomize fails before Kubernetes sees any resource, often with an accumulation or "must resolve to a file" error. | Count from the overlay directory and verify with `kubectl kustomize <overlay>`. |
| Forgetting a `kustomization.yaml` file in the base or overlay | A directory full of YAML is not automatically a Kustomize unit. | Add `apiVersion`, `kind: Kustomization`, and a `resources` list to each Kustomize directory. |
| Writing patches against rendered prefixed names | Patches do not match because Kustomize targets the original base resource name. | Use `metadata.name` from the base, then verify the final prefixed name in rendered output. |
| Using broad label transformations that mutate selectors | Deployment selectors are immutable after creation, and Services may stop selecting the intended pods. | Prefer the `labels` transformer with `includeSelectors: false` for environment metadata. |
| Disabling generator hash suffixes without understanding the rollout impact | Pods may keep running with old configuration because the referenced object name does not change. | Keep hash suffixes enabled unless a legacy integration requires stable names, then plan restarts separately. |
| Applying before rendering | Valid YAML can still be the wrong YAML, and apply makes mistakes live. | Run `kubectl kustomize`, then dry-run or diff before `kubectl apply -k`. |
| Treating Kustomize like Helm | Kustomize has no release history, rollback command, chart dependencies, or templating language. | Use Git history or GitOps for rollback, and choose Helm when package management is the requirement. |
| Copying base manifests into every overlay | Shared changes drift across environments, recreating the problem Kustomize is meant to solve. | Keep the base as the source of shared resources and put only differences in overlays. |

---

## Quiz

Use these questions as reasoning drills rather than recall checks. In each one, identify the layer that owns the problem before choosing a command: source files, Kustomize rendering, Kubernetes validation, or live cluster state. That habit matches how real troubleshooting works because a single failed deployment can involve more than one layer. The best answer is rarely "rerun apply"; it is usually "prove which layer is wrong, repair the smallest thing, and preview again."

1. **Your team deploys the same API to development, staging, and production. A developer copied the Deployment into all three environment folders and changed the replica count in each copy. A security context fix was later applied only to production. How would you redesign the repository with Kustomize, and why does that reduce risk?**

   <details>
   <summary>Answer</summary>

   Create a shared `base/` directory containing the Deployment, Service, and any common configuration. Then create `overlays/dev/`, `overlays/staging/`, and `overlays/prod/`, each with its own `kustomization.yaml` referencing `../../base`. Put environment-specific changes such as namespace, name prefix, image tag, replica count, and resource limits in overlays. This reduces risk because the security context fix is made once in the base and inherited by every environment. The overlays still express real differences, but they no longer duplicate the whole workload definition.

   </details>

2. **During a CKA task, `kubectl apply -k webapp/overlays/staging/` fails with a message that Kustomize cannot accumulate resources from `../base`. The base directory is `webapp/base`, and the overlay is `webapp/overlays/staging`. What should you check and change before trying to apply again?**

   <details>
   <summary>Answer</summary>

   Check the relative path from the overlay directory, not from your current shell directory. From `webapp/overlays/staging`, the path `../base` points to `webapp/overlays/base`, which is wrong. The correct path is usually `../../base`. Change the overlay's `resources` entry to `../../base`, then run `kubectl kustomize webapp/overlays/staging/` to verify rendering before applying.

   </details>

3. **A production overlay uses `namePrefix: prod-`. A patch file targets `metadata.name: prod-webapp`, but the rendered Deployment still has the old replica count. The final object is named `prod-webapp`. Why did the patch not work, and what is the correct patch target name?**

   <details>
   <summary>Answer</summary>

   Kustomize matches patches against the base resource identity before applying the name prefix. Even though the final rendered object is named `prod-webapp`, the patch should target the base resource name, usually `webapp`. Change the patch file to `metadata.name: webapp`, render with `kubectl kustomize`, and confirm that `spec.replicas` changed in the final output.

   </details>

4. **A team adds `commonLabels: { environment: prod }` to an overlay for an existing Deployment. The apply fails because the Deployment selector is immutable. What happened, and how should the team add environment labels more safely?**

   <details>
   <summary>Answer</summary>

   The label transformation likely tried to add the environment label to selector fields as well as metadata. Deployment selectors are immutable after the Deployment exists, so Kubernetes rejected the update. Use the `labels` transformer with `includeSelectors: false` when adding operational metadata that should not change selectors. Then render the output and verify that metadata and pod template labels are appropriate while immutable selectors remain unchanged.

   </details>

5. **Your application reads settings from a ConfigMap generated by Kustomize. After changing the config file and reapplying the overlay, you expect a rollout, but the Deployment does not restart. What two Kustomize-related details would you inspect first?**

   <details>
   <summary>Answer</summary>

   First, inspect whether generator hash suffixing is enabled. If `generatorOptions.disableNameSuffixHash: true` is set, the ConfigMap name stays stable and may not trigger a Pod template change. Second, inspect whether the Deployment reference is managed in a way Kustomize can rewrite to the generated name. Render the overlay and compare the generated ConfigMap name with the name referenced by the Deployment. If the reference does not change, Kubernetes has no reason to roll the Pods.

   </details>

6. **A teammate wants to use Kustomize for a third-party monitoring stack that already has a maintained Helm chart with dependencies and release notes. They also want rollback history. How would you evaluate that choice?**

   <details>
   <summary>Answer</summary>

   Kustomize is strongest when the team owns the manifests and needs environment overlays. A third-party monitoring stack with chart dependencies and expected rollback history is often a better fit for Helm. Helm provides chart packaging, values, dependencies, and release revisions. Kustomize could still be used to customize rendered output in an advanced workflow, but that adds complexity. The recommendation should be based on the operational requirement: if package management and release history are central, Helm is likely the better primary tool.

   </details>

7. **You render a production overlay and notice two containers in the Deployment: `webapp` and `app`. The base originally had only `webapp`, and your patch was meant to add resource limits. What likely caused the second container, and how do you repair it?**

   <details>
   <summary>Answer</summary>

   The strategic merge patch probably used the wrong container name. Kubernetes strategic merge uses `name` as the merge key for the container list, so a patch entry named `app` does not modify the existing `webapp` container; it can create a new container entry. Repair the patch by changing the container name to `webapp`, render the overlay again, and verify that there is one container with the expected resource requests and limits.

   </details>

---

## Hands-On Exercise

**Task**: Build, inspect, apply, and troubleshoot a Kustomize structure for a web application with development and production overlays.

This exercise follows the same progression you should use in the exam: create the base, add a simple overlay, add a production overlay, render before applying, validate with dry-run, apply only after the output is correct, and then clean up. The commands are written to run in a shell with `kubectl` available and a working Kubernetes cluster.

The exercise intentionally repeats render commands more often than a rushed operator might. That repetition is the point. You are training yourself to treat rendered YAML as the contract between the repository and the cluster, not as an optional diagnostic artifact. When the output looks wrong, stop in the repository and repair the Kustomize input. When the output looks right but the API server rejects it, move your attention to cluster constraints such as namespaces, immutable fields, admission policy, and permissions.

### Step 1: Create the directory structure

```bash
mkdir -p webapp/base
mkdir -p webapp/overlays/dev
mkdir -p webapp/overlays/prod
mkdir -p webapp/overlays/prod/config
```

### Step 2: Create the base Deployment

```bash
cat > webapp/base/deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
  labels:
    app.kubernetes.io/name: webapp
    app.kubernetes.io/component: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: webapp
      app.kubernetes.io/component: frontend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: webapp
        app.kubernetes.io/component: frontend
    spec:
      containers:
        - name: webapp
          image: nginx:1.25
          ports:
            - containerPort: 80
          envFrom:
            - configMapRef:
                name: webapp-config
          resources:
            requests:
              memory: "64Mi"
              cpu: "100m"
EOF
```

### Step 3: Create the base Service

```bash
cat > webapp/base/service.yaml << 'EOF'
apiVersion: v1
kind: Service
metadata:
  name: webapp
  labels:
    app.kubernetes.io/name: webapp
spec:
  selector:
    app.kubernetes.io/name: webapp
    app.kubernetes.io/component: frontend
  ports:
    - name: http
      port: 80
      targetPort: 80
EOF
```

### Step 4: Create the base kustomization

```bash
cat > webapp/base/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml

configMapGenerator:
  - name: webapp-config
    literals:
      - LOG_LEVEL=debug
      - FEATURE_FLAGS=local
EOF
```

### Step 5: Render the base and inspect generated names

```bash
kubectl kustomize webapp/base/
```

Look for the generated ConfigMap name and the Deployment reference to that name. They should match after Kustomize rewrites the reference. If the Deployment still references plain `webapp-config` while the generated ConfigMap has a suffix, stop and inspect the YAML before moving on.

### Step 6: Create the development overlay

```bash
cat > webapp/overlays/dev/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: dev-
namespace: development

labels:
  - pairs:
      environment: dev
      app.kubernetes.io/managed-by: kustomize
    includeSelectors: false

images:
  - name: nginx
    newTag: "1.25"
EOF
```

### Step 7: Render development and verify the transformation

```bash
kubectl kustomize webapp/overlays/dev/
```

Confirm that names begin with `dev-`, namespaced resources use `development`, the image is `nginx:1.25`, and the selector labels still match the pod template labels needed by the Service and Deployment.

### Step 8: Create production configuration input

```bash
cat > webapp/overlays/prod/config/app.properties << 'EOF'
LOG_LEVEL=info
FEATURE_FLAGS=checkout-v2
REQUEST_TIMEOUT_SECONDS=10
EOF
```

### Step 9: Create production patches

```bash
cat > webapp/overlays/prod/patch-replicas.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  replicas: 5
EOF
```

```bash
cat > webapp/overlays/prod/patch-resources.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  template:
    spec:
      containers:
        - name: webapp
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
EOF
```

### Step 10: Create the production overlay

```bash
cat > webapp/overlays/prod/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: prod-
namespace: production

labels:
  - pairs:
      environment: production
      app.kubernetes.io/managed-by: kustomize
    includeSelectors: false

images:
  - name: nginx
    newTag: "1.25-alpine"

configMapGenerator:
  - name: webapp-config
    behavior: replace
    files:
      - config/app.properties

patches:
  - path: patch-replicas.yaml
  - path: patch-resources.yaml
EOF
```

### Step 11: Render production and verify specific fields

```bash
kubectl kustomize webapp/overlays/prod/
```

```bash
kubectl kustomize webapp/overlays/prod/ | grep -E "name:|namespace:|replicas:|image:|memory:|cpu:"
```

The production Deployment should be named with a `prod-` prefix, run in the `production` namespace, use five replicas, use `nginx:1.25-alpine`, and include the stronger resource requests and limits.

### Step 12: Validate without changing the cluster

```bash
kubectl apply --dry-run=client -k webapp/overlays/prod/
```

If your cluster supports the relevant server-side validation, also run:

```bash
kubectl apply --dry-run=server -k webapp/overlays/prod/
```

### Step 13: Apply development and production

```bash
kubectl create namespace development
kubectl create namespace production
kubectl apply -k webapp/overlays/dev/
kubectl apply -k webapp/overlays/prod/
```

If either namespace already exists, the create command may report that it already exists. In a practice environment, you can continue if the namespace is present and you have permission to use it.

### Step 14: Verify cluster state

```bash
kubectl get deploy,svc,configmap -n development
kubectl get deploy,svc,configmap -n production
```

```bash
kubectl get deploy prod-webapp -n production -o jsonpath='{.spec.replicas}{"\n"}'
kubectl get deploy prod-webapp -n production -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

### Step 15: Break and repair one overlay on purpose

Edit `webapp/overlays/prod/kustomization.yaml` and temporarily change `../../base` to `../base`. Then run:

```bash
kubectl kustomize webapp/overlays/prod/
```

Read the error message, repair the path, and render again. This deliberate failure builds the diagnostic habit you need under exam pressure.

**Card A: Copying three environment folders is safer than overlays.** An engineer decides that cloning full directory trees for development, staging, and production avoids the complexity of inheritance and patch composition. They believe that having independent, completely detached manifest files in each environment eliminates the risk of unintentional shared changes reaching production unexpectedly. Over time, critical security patches, health probe adjustments, and standard label updates applied to development are never backported to production manifests because there is no shared source of truth.

<details>
<summary>Check your prediction</summary>

Failure layer: mistaking duplicate file silos for configuration safety and auditability. Next action: maintain common application topology in a shared base directory, restricting environment directories to minimal overlays containing only necessary patches and transformers.

</details>

**Card B: `kubectl apply -k` applies the files on disk without rendering.** A junior operator assumes that pointing `kubectl apply -k` at an overlay directory sends the individual raw YAML documents directly to the Kubernetes API server in sequential order. They believe that Kustomize functions as a simple batch wrapper around standard manifest directories rather than an in-memory compilation engine. Because of this misconception, they bypass local rendering checks and fail to anticipate how transformer directives merge and mutate resource definitions before submission.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing client-side overlay composition with raw file application. Next action: run `kubectl kustomize <directory>` or `kubectl diff -k <directory>` to preview the fully rendered and transformed YAML stream before applying changes to the cluster.

</details>

**Card C: `commonLabels` is always safe on a live Deployment.** A cluster administrator adds `commonLabels` to a production kustomization file to enforce consistent environment tracking tags across all existing workloads. They expect the transformer to annotate all resources smoothly without disrupting active controller operations or workload reconciliation cycles. When the update is applied, the API server rejects the modified Deployment specification because the transformer mutated the immutable selector field on an existing workload.

<details>
<summary>Check your prediction</summary>

Failure layer: violating Kubernetes Deployment selector immutability rules through broad label transformation. Next action: use the modern `labels` field with `includeSelectors: false` to apply organizational metadata safely to metadata and pod templates without altering immutable selector fields.

</details>

**Card D: Overlay patches must target the already-prefixed name (`prod-webapp`).** A platform developer prepares a patch to increase replica counts for a production overlay that declares `namePrefix: prod-`. Seeing that the final workload will be named `prod-webapp` in the cluster, they write the patch's `metadata.name` as `prod-webapp` to match the anticipated object identifier. When Kustomize compiles the overlay, it reports an error because patches are evaluated against the original base resource name before prefix transformers take effect.

<details>
<summary>Check your prediction</summary>

Failure layer: misunderstanding Kustomize transformation execution ordering and patch target matching. Next action: set `metadata.name` in overlay patches to match the original resource name from the base, allowing `namePrefix` transformers to apply prefixing downstream during compilation.

</details>

**Success Criteria**:

- [ ] You can explain why the base contains shared resources but not environment-specific production settings.
- [ ] You can render a base and an overlay before applying either one.
- [ ] You can use `namePrefix`, `namespace`, `labels`, `images`, patches, and generators in a working overlay.
- [ ] You can explain why production patches target `metadata.name: webapp` instead of `prod-webapp`.
- [ ] You can verify that generated ConfigMap names and Deployment references match in rendered output.
- [ ] You can diagnose and repair a broken relative path in an overlay.
- [ ] You can validate with dry-run before applying resources to the cluster.
- [ ] You can clean up everything created by the exercise.

### Cleanup

```bash
kubectl delete -k webapp/overlays/dev/
kubectl delete -k webapp/overlays/prod/
kubectl delete namespace development production
rm -rf webapp/
```

---

## Practice Drills

### Drill 1: Preview Before Apply

Create a tiny Kustomize base and prove to yourself that previewing does not change the cluster. This drill trains the safest first move for any exam task involving `-k`.

```bash
mkdir -p drill-preview
cat > drill-preview/deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: preview-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: preview-demo
  template:
    metadata:
      labels:
        app: preview-demo
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
EOF

cat > drill-preview/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
EOF

kubectl kustomize drill-preview/
kubectl get deploy preview-demo
kubectl apply -k drill-preview/
kubectl get deploy preview-demo
kubectl delete -k drill-preview/
rm -rf drill-preview
```

### Drill 2: Repair a Patch Name

This drill creates a patch that targets the wrong name. Your job is to render, observe that the change is missing, repair the patch target, and render again.

```bash
mkdir -p drill-patch/base drill-patch/overlay
cat > drill-patch/base/deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: nginx:1.25
EOF

cat > drill-patch/base/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
EOF

cat > drill-patch/overlay/patch-replicas.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prod-api
spec:
  replicas: 3
EOF

cat > drill-patch/overlay/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../base

namePrefix: prod-

patches:
  - path: patch-replicas.yaml
EOF

kubectl kustomize drill-patch/overlay/
```

Repair `patch-replicas.yaml` so the target name is `api`, then render again and confirm that the final `prod-api` Deployment has three replicas.

```bash
rm -rf drill-patch
```

### Drill 3: Generator Hash Observation

This drill shows why generated ConfigMap names change when content changes. Render once, change a literal, and render again.

```bash
mkdir -p drill-generator
cat > drill-generator/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
EOF

kubectl kustomize drill-generator/

cat > drill-generator/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=debug
EOF

kubectl kustomize drill-generator/
rm -rf drill-generator
```

### Drill 4: Choose the Right Tool

Read each scenario and decide whether plain manifests, Kustomize, or Helm is the best primary tool. Then compare your answer with the explanation.

1. You have one Namespace and one debug Pod for a quick troubleshooting task.
2. You own a web application and need dev, staging, and production variants.
3. You need to install a third-party ingress controller with dependencies and release rollback.

<details>
<summary>Suggested reasoning</summary>

Plain manifests are enough for the quick debug Pod because there is no reusable environment structure. Kustomize fits the owned web application because the base can hold the shared workload while overlays hold environment differences. Helm fits the third-party ingress controller because chart packaging, dependencies, values, and release history are part of the requirement.

</details>

---

## Sources

- https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/
- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://kubernetes.io/docs/concepts/services-networking/service/
- https://kubernetes.io/docs/concepts/configuration/configmap/
- https://kubernetes.io/docs/concepts/configuration/secret/
- https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
- https://kubernetes.io/docs/concepts/overview/working-with-objects/names/
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/
- https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/
- https://fluxcd.io/flux/components/kustomize/kustomizations/

---
- [kubernetes.io: kustomization](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) — The Kubernetes Kustomize task page directly states that kubectl has supported kustomization files since 1.14 and shows the exact commands.
- [kubernetes.io: kubectl kustomize](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/) — The kubectl kustomize reference explicitly says the directory argument must contain `kustomization.yaml`.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment docs directly state both the selector/template-label matching requirement and selector immutability.
- [kubernetes.io: namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) — The namespaces documentation explicitly distinguishes namespaced objects from cluster-wide objects.
- [kubernetes.io: update api object kubectl patch](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/update-api-object-kubectl-patch/) — The kubectl patch task shows that container lists use strategic merge with `name` as the merge key and demonstrates list-merging behavior.
- [rfc-editor.org: rfc6902](https://www.rfc-editor.org/rfc/rfc6902) — RFC 6902 is the primary standard defining JSON Patch documents as ordered sequences of operations over JSON locations.
- [kubernetes.io: kubectl diff](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/) — The kubectl diff reference defines diff exactly in those terms and documents `-k/--kustomize`.
- [argo-cd.readthedocs.io: kustomize](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/) — The Argo CD Kustomize guide directly says Argo renders with Kustomize when the path contains `kustomization.yaml` and says to point path to the overlay.
- [fluxcd.io: kustomizations](https://fluxcd.io/flux/components/kustomize/kustomizations/) — The Flux Kustomization documentation directly describes build-from-path, namespace handling, validation, and apply behavior.
- [helm.sh: charts](https://helm.sh/docs/topics/charts/) — The Helm charts documentation directly covers Go-template rendering, values files, and chart dependencies.

## Next Module

[Module 1.5: CRDs & Operators](../module-1.5-crds-operators/) - Extending Kubernetes with Custom Resource Definitions.
