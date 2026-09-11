---
citations_verified: true
title: "Module 4.7: Kyverno"
slug: platform/toolkits/security-quality/security-tools/module-4.7-kyverno
sidebar:
  order: 8
---
> **Toolkit Track** | Complexity: `[MEDIUM]` | Time: 45-55 minutes

**Prerequisites**: [Security Principles Foundations](/platform/foundations/security-principles/), [Module 4.2: OPA & Gatekeeper](../module-4.2-opa-gatekeeper/) recommended, and a working understanding of Kubernetes admission controllers.

---

## Learning Outcomes

After completing this module, you will be able to:

- **Design** Kyverno validation, mutation, generation, and image verification policies that match real platform security requirements without surprising application teams.
- **Debug** policy behavior by reading admission errors, PolicyReport resources, match and exclude blocks, and Kyverno CLI output.
- **Evaluate** when Kyverno is a better fit than OPA Gatekeeper, and when Gatekeeper or another policy engine remains the stronger choice.
- **Implement** a safe rollout path that starts in audit mode, measures existing violations, and moves selected rules to enforcement with clear exceptions.
- **Compare** policy choices against operational risks such as webhook availability, namespace blast radius, background scans, and multi-team ownership.

---

## Why This Module Matters

**Hypothetical scenario:** a platform team inherits a cluster where every team can deploy directly from its CI pipeline. The system looked healthy during ordinary releases, but the guardrails were mostly social agreements: "use non-root containers," "do not deploy `latest`," and "remember resource limits." Those rules lived in docs, pull request comments, and incident retrospectives, which meant they failed exactly when the delivery pressure increased.

One Friday afternoon, a service owner shipped a container running as root, with no CPU limit, and with a floating image tag from a public registry. The change passed CI because the YAML was syntactically valid, and it passed deployment because the API server had no policy saying the workload was unsafe. By Monday morning, the team was investigating noisy neighbors, unexplained cost growth, and an uncomfortable security review that asked why the cluster accepted a workload the organization already knew was forbidden.

Kyverno turns those platform agreements into Kubernetes-native policy. It reads and writes ordinary Kubernetes resources, uses YAML instead of a separate policy language, and [can validate, mutate, generate, and verify resources](https://raw.githubusercontent.com/kyverno/kyverno/main/README.md) at the point where they enter the cluster. The important lesson is not that Kyverno is "easy"; the important lesson is that a readable policy engine gives a platform team a practical path from documented intent to enforceable behavior.

This module teaches Kyverno as a production control system, not as a command reference. You will start with the admission path, then write policies that solve realistic problems, then learn how to roll them out without breaking existing workloads. By the end, you should be able to reason about both the YAML and the operational consequences of installing it.

> **Landscape snapshot — as of 2026-09. This changes fast; verify against the [Kyverno docs](https://kyverno.io/docs/) and the [CNCF project page](https://www.cncf.io/projects/kyverno/) before relying on specifics.** Kyverno is a **CNCF Graduated** project (accepted 2020-11; Incubating 2022-07; **Graduated 2026-03**), placing it in the same maturity tier as Kubernetes, Prometheus, and Helm. The current release line is **1.19** (latest **v1.19.1**, September 2026). Most importantly for the policies in this module: Kyverno **1.17 deprecated the `ClusterPolicy` and `Policy` (and `CleanupPolicy`) resources** in favour of dedicated **CEL-based policy types**, and their removal is scheduled for **v1.20 (October 2026)**.

The `ClusterPolicy`/`Policy` API used throughout this module is the one you will still meet on most running clusters, and it remains the clearest way to learn the four policy behaviours — validate, mutate, generate, and verifyImages — because each behaviour is visible in one readable document. Treat it as the durable mental model: the *concepts* (the admission contract, audit-before-enforce, pattern matching, generate-with-synchronize) carry over unchanged to the newer API. The §6 note on where the API is heading shows how those same concepts map onto the CEL-based types so your knowledge survives the migration.

---

## 1. Admission Control as a Platform Contract

Kyverno sits on the Kubernetes admission path, which means it evaluates resources [after authentication and authorization but before the object is stored in etcd](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/). That location matters because a policy engine can stop unsafe resources before controllers schedule them, mutate resources before other controllers observe them, and create companion resources when a trigger appears. When you use Kyverno well, the API server becomes a contract boundary between application teams and the platform.

The contract should be explicit and observable. A rule that denies every Pod without telling the developer what to fix creates friction, even if the security goal is valid. A rule that audits first, reports violations clearly, and then moves to enforcement after teams have remediated existing workloads is easier to defend during a production incident.

Kyverno is implemented through admission webhooks plus background controllers. The validating webhook can allow, deny, or audit a request. The mutating webhook can patch the resource before it is persisted. The generate controller can create dependent resources such as NetworkPolicies, RoleBindings, or ConfigMaps after a matching trigger resource is created.

```text
KYVERNO ADMISSION AND BACKGROUND FLOW
===============================================================

  Developer or CI
  kubectl apply / Helm / GitOps
          |
          v
  +------------------+       AuthN/AuthZ        +------------------+
  |   API Server     |------------------------->|  Kubernetes RBAC |
  +------------------+                          +------------------+
          |
          | AdmissionReview
          v
  +----------------------------------------------------------------+
  |                            Kyverno                             |
  |                                                                |
  |  +----------------+   +----------------+   +----------------+  |
  |  | Validate       |   | Mutate         |   | Generate       |  |
  |  | allow/deny     |   | patch object   |   | create related |  |
  |  | audit reports  |   | before store   |   | resources      |  |
  |  +----------------+   +----------------+   +----------------+  |
  |                                                                |
  |  ClusterPolicy / Policy resources drive each decision.          |
  +----------------------------------------------------------------+
          |
          | allow, deny, mutate, or reconcile later
          v
  +------------------+       Stored Object       +------------------+
  |       etcd       |<-------------------------| Controllers       |
  +------------------+                          +------------------+
```

The first design decision is not which YAML field to type. The first decision is whether the rule should block an admission request, modify it, create something related, or verify supply-chain evidence. Those actions look similar in a policy file, but they create different responsibilities for the platform team.

| Kyverno action | Production purpose | Typical example | Operational risk to manage |
|---|---|---|---|
| **Validate** | Reject or audit resources that violate a rule | Deny Pods without resource limits | A broad rule can block emergency releases if rolled out too quickly |
| **Mutate** | Patch resources before they are stored | Add default labels or security settings | Hidden mutation can surprise teams if it changes ownership-sensitive fields |
| **Generate** | Create related resources from a trigger | Create a default-deny NetworkPolicy for each new namespace | Generated resources need clear ownership and synchronization choices |
| **VerifyImages** | Check signatures and attestations for container images | Require signed images from a trusted issuer | Signature policies can block builds when the signing pipeline is unavailable |

A good platform policy has three layers of clarity. It states the intent in the policy name and message, scopes the rule narrowly enough that the blast radius is known, and exposes results through PolicyReport resources or CI output. If one of those layers is missing, the rule may still work technically while failing as a platform product.

**Pause and predict:** A team creates a Pod that violates a Kyverno validate rule configured with `validationFailureAction: Audit`. Will the API server store the Pod, and where should the platform team look afterward to see that it violated policy?

The answer is that the Pod is stored because audit mode does not block admission, and the violation appears in PolicyReport or ClusterPolicyReport resources depending on scope. This is why audit mode is useful during rollout: it lets you discover the current state before deciding what to enforce. It is also why audit mode is not a complete control for a high-risk rule; it observes violations, but it does not prevent them.

Kyverno has two policy resource scopes, and the scope should match the ownership model. A `ClusterPolicy` applies across the cluster and is normally owned by the platform or security team. A namespaced `Policy` applies only inside its namespace and can be useful for team-specific requirements that should not become global rules.

| Resource kind | Scope | Best use | Ownership signal |
|---|---|---|---|
| **ClusterPolicy** | Cluster-wide | Shared baselines such as non-root containers and disallowed registries | Platform team owns the default behavior |
| **Policy** | One namespace | Team-specific rules such as required labels for a single product area | Namespace owner can adapt rules inside their boundary |

The mistake to avoid is treating scope as a convenience setting. A ClusterPolicy with weak exceptions can accidentally govern system namespaces, observability workloads, and third-party controllers that were never part of the original requirement. A namespaced Policy can be safer during experimentation, but it will not protect the cluster if critical namespaces are forgotten.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-platform-labels
spec:
  validationFailureAction: Audit
  background: true
  rules:
  - name: require-app-and-team
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Pods must include app and team labels so ownership is visible during incidents."
      pattern:
        metadata:
          labels:
            app: "?*"
            team: "?*"
```

This first policy is intentionally gentle. It audits instead of enforcing, and its message explains the operational reason for the labels. The pattern checks that both labels exist and are not empty, which gives responders enough metadata to group workload issues by owning team.

Use `kubectl` first, then you may use the `k` alias if your shell defines it. The module examples spell out `kubectl` in setup commands because clarity matters when learners copy commands into a fresh environment.

```bash
kubectl apply -f require-platform-labels.yaml
kubectl run unlabeled-demo --image=nginx:1.27
kubectl get clusterpolicyreport -o wide
```

The expected behavior in audit mode is that the Pod is created and the report records a failure. If you change `validationFailureAction` to `Enforce`, the same Pod should be denied at admission with the message from the policy. That small field change is a large operational change, which is why rollout discipline matters.

---

## 2. Writing Validation Policies That Explain the Rule

Validation is the most familiar Kyverno capability because it maps directly to platform guardrails. A request comes in, Kyverno compares the object with the rule, and the request is allowed, denied, or recorded as a violation. The quality difference between a useful validation policy and an irritating one is usually the message, the scope, and the rollout path.

Start validation policies with one concrete risk. "All Pods must be secure" is too broad to express or debug cleanly. "Application Pods must not use floating image tags" is specific enough to test, explain, and tune. The tighter rule also helps you decide what exceptions are legitimate.

A strong validation policy includes an actionable failure message. Developers should know whether they need to add a field, change an image, use a different namespace, or ask for an exception. A message that only says "policy violation" transfers the diagnosis work to the person trying to ship.

The following worked example blocks floating `latest` image tags for ordinary application Pods while excluding system namespaces. It uses enforcement because the risk is easy to understand and the remediation is usually straightforward: [pin the image to an immutable version or digest](https://kubernetes.io/docs/concepts/containers/images/).

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-floating-image-tags
spec:
  validationFailureAction: Enforce
  background: true
  rules:
  - name: require-explicit-container-tags
    match:
      any:
      - resources:
          kinds:
          - Pod
    exclude:
      any:
      - resources:
          namespaces:
          - kube-system
          - kube-public
          - kyverno
    validate:
      message: "Floating image tags are not allowed. Use a version tag or digest so rollbacks and audits are deterministic."
      pattern:
        spec:
          containers:
          - image: "!*:latest"
```

The `pattern` block describes what must be true. The image expression `!*:latest` means each matched container image must not end with the forbidden tag. This is not a complete supply-chain strategy, but it removes a common source of nondeterministic deploys and makes later image verification policies easier to reason about.

```bash
kubectl apply -f disallow-floating-image-tags.yaml

kubectl run bad-tag --image=nginx:latest --labels="app=demo,team=platform"

kubectl run pinned-tag --image=nginx:1.27 --labels="app=demo,team=platform"
```

The first Pod should be denied and the second should be accepted. If both are accepted, check whether the policy was applied, whether Kyverno pods are ready, and whether the resource kind and namespace match the rule. If both are denied, inspect the failure message and confirm whether another ClusterPolicy is also evaluating the Pod.

A common validation problem appears when a policy checks only `containers` and forgets `initContainers` or `ephemeralContainers`. Attackers and ordinary mistakes do not care which array holds the risky image or security context. A production policy should cover the workload shapes your cluster actually allows.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
spec:
  validationFailureAction: Audit
  background: true
  rules:
  - name: require-container-limits
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Every application container must define CPU and memory limits so one workload cannot starve the node."
      pattern:
        spec:
          containers:
          - resources:
              limits:
                cpu: "?*"
                memory: "?*"
          =(initContainers):
          - resources:
              limits:
                cpu: "?*"
                memory: "?*"
```

The `=(initContainers)` anchor means the pattern applies if `initContainers` exists. Without that conditional anchor, the rule could require every Pod to have init containers, which is not the intent. This detail is a good example of why Kyverno is approachable but still deserves careful testing.

**Pause and predict:** A Pod has two regular containers. One has both CPU and memory limits, and the other has only a memory limit. Under the policy above, should the Pod pass or fail, and what should the failure message help the developer fix?

The Pod should fail because every matched container must satisfy the pattern. The message should point the developer toward adding the missing CPU limit, not toward learning Kyverno syntax. In a real rollout, you would also inspect PolicyReports to see whether a small number of shared Helm charts are responsible for many violations.

Some rules need richer comparisons than a simple pattern provides. Kyverno supports deny conditions with variables and operators, which are useful when the decision depends on request context or field comparisons. Use deny rules carefully because they can become harder to read than patterns when conditions pile up.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-loadbalancer-services
spec:
  validationFailureAction: Enforce
  background: false
  rules:
  - name: platform-team-approves-loadbalancers
    match:
      any:
      - resources:
          kinds:
          - Service
    validate:
      message: "Only platform-owned namespaces may create LoadBalancer Services; request an ingress or an approved exception."
      deny:
        conditions:
          all:
          - key: "{{ request.object.spec.type || '' }}"
            operator: Equals
            value: LoadBalancer
          - key: "{{ request.namespace || '' }}"
            operator: NotIn
            value:
            - platform-ingress
            - edge-services
```

This policy is intentionally set with `background: false` because it relies on admission request context. Background scans evaluate existing resources, but [not every request variable is meaningful outside an admission request](https://raw.githubusercontent.com/kyverno/kyverno/main/config/crds/kyverno/kyverno.io_clusterpolicies.yaml). When you design policies, decide whether you need to scan historical objects or only control future writes.

A senior platform engineer reads a Kyverno validation rule as an operational promise. The policy name tells what it protects, match and exclude blocks tell where it applies, the validation block tells how it decides, and the failure message tells how humans recover. If those four parts disagree, the policy will cause confusion even when the YAML is valid.

---

## 3. Mutating Policies Without Hiding Ownership

Mutation changes a resource before it is stored. This is powerful because it can make safe defaults automatic, but it is risky because application teams may not realize the stored object differs from the submitted manifest. Use mutation for defaults that are boring, documented, and safe to apply consistently.

A good mutation policy does not become a secret deployment system. Adding missing labels, setting default annotations, or inserting a known image pull secret may be reasonable. Injecting complex sidecars into arbitrary workloads can be appropriate in a service mesh or logging platform, but it requires versioning, observability, and an escape hatch.

Kyverno supports strategic merge patches, JSON patches, and foreach patterns for mutation. The most common beginner-friendly approach is `patchStrategicMerge`, which looks like the shape of the resource you want to modify. The `+()` notation means "add this field only if it is missing," which protects explicit choices made by the workload owner.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-platform-labels
spec:
  rules:
  - name: add-managed-labels
    match:
      any:
      - resources:
          kinds:
          - Pod
    exclude:
      any:
      - resources:
          namespaces:
          - kube-system
          - kyverno
    mutate:
      patchStrategicMerge:
        metadata:
          labels:
            +(managed-by): kyverno
            +(cost-center): "shared"
```

This policy is a safe first mutation because it adds metadata rather than changing runtime behavior. If a team already sets `cost-center`, Kyverno leaves it alone. That makes the policy a defaulting mechanism rather than an override mechanism, which is usually easier to justify.

```bash
kubectl apply -f add-default-platform-labels.yaml

kubectl run mutate-demo --image=nginx:1.27 --labels="app=web,team=platform"

kubectl get pod mutate-demo -o jsonpath='{.metadata.labels.managed-by}{"\n"}'
kubectl get pod mutate-demo -o jsonpath='{.metadata.labels.cost-center}{"\n"}'
```

The expected output is `kyverno` and `shared` unless the submitted manifest already supplied a different `cost-center`. If the labels are missing, inspect the mutating webhook configuration and confirm that the Pod was created after the policy existed. Mutation happens during admission; it does not retroactively patch objects that were already stored.

The next mutation example is more sensitive because it changes workload composition. The policy injects a logging sidecar only when the workload opts in with an annotation. Opt-in scoping gives application teams a clear signal and reduces the chance that the platform team changes the behavior of workloads that were never tested with the sidecar.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: inject-logging-sidecar
spec:
  rules:
  - name: add-fluent-bit-when-requested
    match:
      any:
      - resources:
          kinds:
          - Pod
          annotations:
            observability.kubedojo.io/inject-logger: "true"
    mutate:
      patchStrategicMerge:
        spec:
          containers:
          - name: platform-log-forwarder
            image: fluent/fluent-bit:3.0
            resources:
              requests:
                cpu: "25m"
                memory: "32Mi"
              limits:
                cpu: "50m"
                memory: "64Mi"
```

This policy should trigger a platform design conversation before it reaches production. Who owns sidecar upgrades? How will teams know the image version changed? What happens when the sidecar crashes? Can a workload opt out during an incident? Kyverno can perform the mutation, but the platform team still owns the product behavior created by that mutation.

**What would happen if:** A GitOps controller continuously applies a manifest without the `managed-by` label, while Kyverno mutates the live object to add that label. Would you expect drift noise, and how could you reduce it?

The answer depends on the GitOps tool and diff configuration, but drift noise is possible when the live object contains fields that are absent from Git. You can reduce the problem by committing the defaulted fields, configuring diff ignores for known mutation fields, or limiting mutation to fields that your deployment tooling already treats as server-side defaults. The key is to test policy behavior in the same delivery path teams actually use.

A mutation policy should be documented as part of the platform API. Developers need to know which fields are defaulted, which fields are respected when explicitly set, and which annotations opt into heavier behavior. Without that documentation, mutation can feel like the cluster is rewriting manifests behind their backs.

---

## 4. Generate Policies for Namespace Guardrails

Generate policies create related Kubernetes resources when another resource appears. This capability is one of Kyverno's major differences from Gatekeeper, and it is especially useful for namespace onboarding. A new namespace can automatically receive a default NetworkPolicy, a ResourceQuota, a LimitRange, or a RoleBinding that matches your platform baseline.

Generation is not validation. A generate rule does not deny a namespace because it lacks a NetworkPolicy; it creates the NetworkPolicy when the namespace is created. That difference matters because generated resources need ownership rules, synchronization behavior, and naming conventions that fit your operational model.

The following policy creates a [default-deny NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/) whenever a new ordinary namespace appears. It excludes system and Kyverno namespaces so the policy does not interfere with cluster infrastructure. It also sets `synchronize: true`, which tells Kyverno to keep the generated resource aligned with the policy over time.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: generate-default-deny-networkpolicy
spec:
  rules:
  - name: create-default-deny-for-new-namespaces
    match:
      any:
      - resources:
          kinds:
          - Namespace
    exclude:
      any:
      - resources:
          names:
          - kube-system
          - kube-public
          - kube-node-lease
          - kyverno
    generate:
      synchronize: true
      apiVersion: networking.k8s.io/v1
      kind: NetworkPolicy
      name: default-deny-all
      namespace: "{{ request.object.metadata.name }}"
      data:
        spec:
          podSelector: {}
          policyTypes:
          - Ingress
          - Egress
```

This policy is a strong platform default because network isolation is easy to forget during namespace creation. However, it should be paired with onboarding documentation that tells teams how to add allow rules for required traffic. A default-deny policy without a path to expected connectivity can turn security into a deployment blocker.

```bash
kubectl apply -f generate-default-deny-networkpolicy.yaml

kubectl create namespace payments-dev

kubectl get networkpolicy -n payments-dev default-deny-all -o yaml
```

The expected result is a `NetworkPolicy` named `default-deny-all` in the new namespace. If it does not appear immediately, wait briefly and check Kyverno controller logs because generation is reconciled by a controller after admission. If it appears and then is removed by another controller, you need to inspect ownership and synchronization behavior.

```text
GENERATE POLICY OWNERSHIP MODEL
===============================================================

  Namespace created: payments-dev
          |
          v
  +-----------------------------+
  | Kyverno generate rule       |
  | name: default-deny-all      |
  | synchronize: true           |
  +-----------------------------+
          |
          v
  +-----------------------------+
  | payments-dev namespace      |
  |                             |
  | NetworkPolicy               |
  | default-deny-all            |
  |                             |
  | Team-owned allow policies   |
  | allow-dns                   |
  | allow-ingress-controller    |
  +-----------------------------+
```

The generated default should be stable, small, and easy to recognize. Team-owned allow policies should be separate resources so teams can manage their own connectivity without editing the platform baseline. This separation makes audits clearer because the generated resource states the default posture while team resources state intentional exceptions.

Generate policies are also useful for [ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/) and [LimitRange defaults](https://kubernetes.io/docs/concepts/policy/limit-range/). Those resources are not security controls in the same way as NetworkPolicy, but they protect cluster reliability by preventing accidental resource exhaustion. The same ownership pattern applies: platform defaults should be generated predictably, while team-specific exceptions should be explicit.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: generate-namespace-resource-defaults
spec:
  rules:
  - name: create-default-quota
    match:
      any:
      - resources:
          kinds:
          - Namespace
    exclude:
      any:
      - resources:
          names:
          - kube-system
          - kube-public
          - kube-node-lease
          - kyverno
    generate:
      synchronize: true
      apiVersion: v1
      kind: ResourceQuota
      name: namespace-default-quota
      namespace: "{{ request.object.metadata.name }}"
      data:
        spec:
          hard:
            requests.cpu: "4"
            requests.memory: "8Gi"
            limits.cpu: "8"
            limits.memory: "16Gi"
            pods: "40"
```

Be careful with synchronized generation when teams need to customize generated objects. If `synchronize: true` is used, Kyverno may restore the generated object to the policy-defined state after someone changes it. That is exactly what you want for a security baseline, but it may frustrate teams if the generated object is supposed to be a starting template rather than a managed control.

**Pause and decide:** Your organization wants every new namespace to start with a ResourceQuota, but product teams need different quota sizes after onboarding. Should the generated quota use `synchronize: true`, or should the platform use another pattern?

A reasonable answer is to avoid synchronized generation for a quota that teams are expected to customize, or to generate a conservative default and require teams to request a managed override through a clear workflow. If the platform wants quotas to remain centrally managed, synchronization is appropriate, but then the exception process must be part of the design. The right answer depends on ownership, not only on Kyverno syntax.

Generation policies are most successful when they make the secure path the default path. A namespace should not be born empty and then wait for a human to remember ten setup steps. Kyverno lets the platform team encode those steps as reconciliation behavior, but the generated resources still need names, labels, and documentation that humans can understand during incidents.

---

## 5. Image Verification and Supply Chain Controls

Container image policy has two layers. Basic validation checks the image string, such as whether it uses a forbidden tag or registry. Image verification checks evidence about the image, such as whether it was signed by a trusted identity or has an attestation matching your build requirements.

Kyverno's `verifyImages` rules help enforce supply-chain policy at admission time. The goal is not to make Kubernetes a full artifact security platform. The goal is to ensure that the cluster only accepts images that came through the approved build and signing process.

A simple progression works best. First block obviously unsafe image references, such as `latest` or unknown registries. Then require images from approved registries. Then require signatures for sensitive namespaces. Finally, add attestation checks when the build pipeline reliably produces the required metadata.

The following policy sketches a registry restriction. It is not a signature policy yet, but it is a useful stepping stone because it reduces the number of places from which workloads can pull code.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-image-registries
spec:
  validationFailureAction: Enforce
  background: true
  rules:
  - name: require-approved-registries
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Images must come from approved registries so vulnerability scanning and provenance controls apply."
      pattern:
        spec:
          containers:
          - image: "registry.kubedojo.internal/* | ghcr.io/kube-dojo/*"
```

Registry restrictions are valuable, but they do not prove that the image was built by your pipeline. An attacker who can push to an approved registry could still publish an image with a valid-looking name. Signature verification closes part of that gap by requiring [cryptographic evidence from a trusted signer](https://www.nist.gov/publications/security-considerations-code-signing).

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-platform-images
spec:
  validationFailureAction: Enforce
  webhookTimeoutSeconds: 10
  rules:
  - name: require-signed-platform-images
    match:
      any:
      - resources:
          kinds:
          - Pod
          namespaces:
          - production
          - payments
    verifyImages:
    - imageReferences:
      - "registry.kubedojo.internal/platform/*"
      attestors:
      - entries:
        - keyless:
            subject: "https://github.com/kube-dojo/platform/.github/workflows/release.yaml@refs/heads/main"
            issuer: "https://token.actions.githubusercontent.com"
```

Treat this example as a teaching shape, not as a universal copy-paste policy. Real signature verification depends on your signing tool, identity provider, registry, and Kyverno version. The important design point is that image verification policies encode trust in the build identity, not just trust in the image name.

Verification policies can fail closed during registry, transparency log, identity provider, or network issues depending on configuration. That may be the correct security posture for production namespaces, but it should be a deliberate decision. For lower-risk environments, teams often start with audit mode or narrower matching until the signing pipeline is stable.

| Supply-chain control | What it proves | What it does not prove | Rollout advice |
|---|---|---|---|
| Disallow `latest` | Deploys refer to a stable tag shape | The tag cannot be moved in the registry | Enforce early because remediation is simple |
| Restrict registries | Images come from known locations | The image was built by an approved workflow | Audit current usage before enforcing |
| Require signatures | A trusted identity signed the image | The image is free of vulnerabilities | Enforce by namespace after signing is reliable |
| Require attestations | Build metadata or SBOM evidence exists | The application is logically secure | Start with critical services and clear exceptions |

**What would happen if:** You enforce signed images in the `production` namespace before every production build job signs images consistently. What failure pattern would application teams see, and what should the platform team measure before enforcement?

Teams would see admission denials for images that may otherwise be valid application releases. Before enforcement, the platform team should measure unsigned image frequency, identify which pipelines fail to sign, and verify that emergency patch workflows can produce signed artifacts. The policy is only as usable as the supply chain behind it.

Image verification is where Kyverno stops being only a YAML-friendly admission tool and becomes part of the delivery trust boundary. That boundary includes CI identities, registry permissions, artifact retention, signing keys or keyless identities, and incident response. Kyverno enforces the final admission decision, but the evidence must be produced earlier in the software delivery system.

---

## 6. Rollout, Reports, CLI Testing, and Tool Choice

The safest Kyverno rollout starts outside enforcement. Install Kyverno, deploy a small number of audit policies, inspect reports, fix the most common violations, then move selected rules to enforcement. This path gives the platform team evidence and gives application teams time to adapt.

PolicyReports are the feedback loop for audit mode and background scans. Namespaced PolicyReport resources show violations for namespaced resources, while ClusterPolicyReport resources cover cluster-scoped results. In production, many teams connect these reports to dashboards, alerts, or periodic review jobs rather than expecting humans to run `kubectl` manually.

```bash
kubectl get clusterpolicyreport

kubectl get policyreport -A

kubectl get policyreport -n default -o yaml
```

When a report shows many failures, do not immediately assume teams ignored guidance. Look for shared templates, stale Helm chart values, generated manifests, or defaults that your platform can improve centrally. Policy data is most useful when it helps you find leverage points instead of only assigning blame.

The Kyverno CLI lets you test policies against manifests before they reach the cluster. This is useful in CI because a pull request can fail with a policy explanation rather than waiting for a deployment failure. It is also useful for policy authors because it shortens the edit-test loop.

```bash
brew install kyverno

kyverno apply policies/ --resource k8s-manifests/ --detailed-results

kyverno test .
```

A minimal repository layout keeps policies, test resources, and expected results together. The exact shape can vary, but the principle is stable: every policy that blocks production should have at least one passing resource and one failing resource in version control. Without tests, policy changes become risky refactors.

```text
KYVERNO POLICY REPOSITORY SHAPE
===============================================================

  platform-policies/
  |
  +-- policies/
  |   +-- disallow-floating-image-tags.yaml
  |   +-- require-resource-limits.yaml
  |   +-- generate-default-deny-networkpolicy.yaml
  |
  +-- tests/
  |   +-- good-pod.yaml
  |   +-- bad-latest-tag-pod.yaml
  |   +-- namespace-trigger.yaml
  |
  +-- kyverno-test.yaml
  +-- README.md
```

A GitHub Actions workflow can run the CLI against manifests before merge. This does not replace admission control, because clusters still need to reject unsafe changes from every path. It does reduce feedback time and catches problems before they interrupt a deployment.

```yaml
name: Kyverno Policy Check

on:
  pull_request:
  push:
    branches:
    - main

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Install Kyverno CLI
      run: |
        curl -LO https://github.com/kyverno/kyverno/releases/latest/download/kyverno-cli_linux_amd64.tar.gz
        tar -xzf kyverno-cli_linux_amd64.tar.gz
        sudo mv kyverno /usr/local/bin/kyverno

    - name: Validate Kubernetes manifests
      run: kyverno apply policies/ --resource k8s-manifests/ --detailed-results
```

Kyverno and OPA Gatekeeper overlap, but they are not interchangeable in every situation. Kyverno is often easier for Kubernetes platform teams because policies look like Kubernetes resources and support validation, mutation, generation, and image verification in one model. [Gatekeeper is often stronger when teams need highly expressive logic, mature Rego expertise](https://raw.githubusercontent.com/open-policy-agent/gatekeeper/master/website/docs/howto.md), or policy reuse beyond Kubernetes.

| Decision point | Kyverno is usually stronger when... | Gatekeeper is usually stronger when... | Senior trade-off |
|---|---|---|---|
| Policy authoring | Kubernetes engineers will maintain policies in YAML | A policy team already writes Rego well | Choose the language your maintainers can review correctly |
| Mutation and generation | Defaults and companion resources are core requirements | Validation is the main requirement | Generation can simplify onboarding but creates ownership questions |
| Complex logic | Rules are mostly structural and admission-context based | Rules need advanced data structures or cross-domain logic | Readability matters, but expressiveness may be necessary |
| Tool reach | Kubernetes is the primary enforcement target | Policies must also cover Terraform, Envoy, or services outside Kubernetes | Avoid forcing one tool into a domain it was not built to own |
| Developer experience | Teams need clear YAML examples and fast adoption | Teams can absorb Rego training and centralized policy review | The best control is the one teams can understand under pressure |

Many organizations use both tools. For example, Kyverno can own Kubernetes-native defaults, image verification, and namespace generation, while [OPA handles broader policy-as-code across infrastructure repositories](https://raw.githubusercontent.com/open-policy-agent/opa/main/README.md). The important architectural choice is to avoid duplicate rules that produce conflicting messages or inconsistent decisions.

A production Kyverno installation also needs operational care. [Admission webhooks are part of the write path, so availability, timeouts, and failure policies matter](https://kubernetes.io/docs/concepts/cluster-administration/admission-webhooks-good-practices/). Policies should be reviewed like application code because a small match change can affect every namespace in the cluster.

```text
SAFE ROLLOUT LADDER
===============================================================

  1. Draft policy locally
          |
          v
  2. Test with Kyverno CLI against passing and failing manifests
          |
          v
  3. Deploy to a non-production cluster in Audit mode
          |
          v
  4. Review PolicyReports and fix shared templates
          |
          v
  5. Enforce in one low-risk namespace
          |
          v
  6. Expand enforcement with documented exceptions
          |
          v
  7. Monitor reports, admission denials, and webhook health
```

This ladder is slower than dropping a ClusterPolicy into production, but it is faster than recovering from a broken deployment path. It also creates artifacts that reviewers can inspect: test cases, audit reports, exception decisions, and measured impact. Senior engineers care about that evidence because policy engines fail socially as often as they fail technically.

### Where the Policy API Is Heading: CEL-Based Types

The single most important currency fact for anyone learning Kyverno today is that the policy API is mid-migration, and the `ClusterPolicy`/`Policy` resources used throughout this module are on a deprecation clock. Kyverno 1.17 promoted a set of **CEL-based policy types** to a stable `v1` API and deprecated the older resources; removal is scheduled for **v1.20 in October 2026**. Rather than one `ClusterPolicy` document that can bundle validation, mutation, generation, and image checks together, the new model gives each behaviour its own focused resource: `ValidatingPolicy`, `MutatingPolicy`, `GeneratingPolicy`, `ImageValidatingPolicy`, and `DeletingPolicy`. Each one does a single thing, which makes intent, RBAC, and review boundaries clearer than a multi-rule policy that mixes concerns.

The deeper reason for the shift is convergence with upstream Kubernetes. The project replaced its bespoke YAML pattern-matching syntax (the `?*`, `=()`, and `+()` anchors you learned earlier) with **CEL (Common Expression Language)**, the same expression language that powers Kubernetes' in-tree `ValidatingAdmissionPolicy` and `MutatingAdmissionPolicy`. Standardising on CEL means a platform engineer can reason about admission logic the same way whether it is enforced by a built-in admission policy or by Kyverno, and it lets the two coexist: lightweight, latency-sensitive checks can run as in-tree CEL policies with no webhook, while Kyverno continues to own the richer behaviours — cross-resource generation, image attestation, and policy reporting — that the built-in feature does not provide.

For learning, this changes very little, which is exactly why this module teaches the `ClusterPolicy` form first. Every durable concept transfers directly: the admission contract, the audit-then-enforce rollout discipline, matching resources to a rule, mutating without hiding ownership, generating namespace guardrails with `synchronize`, and verifying image provenance are all behaviours, not syntax. When you migrate, you are re-expressing the same rule — "require resource limits", "block floating tags", "generate a default-deny NetworkPolicy" — as a CEL expression in a single-purpose resource. The practical advice is to keep writing and testing in whichever form your current cluster runs, plan the migration before the October 2026 removal if you depend on `ClusterPolicy`, and use `kyverno migrate` tooling and the conversion guidance in the upstream docs rather than rewriting policies by hand.

The surrounding operational machinery survives the migration intact, which is what makes it manageable. PolicyReports and ClusterPolicyReports keep the same shared reporting model, so the dashboards and pass/fail/warn/error/skip workflows you build today keep working against the new policy types. The `kyverno apply` and `kyverno test` CLI workflow that gates policies in CI behaves the same way regardless of which resource kind the policy uses, so your test suite is portable. PolicyExceptions and the audit-then-enforce rollout ladder also carry over. In other words, the migration is a syntax-and-resource-shape change layered on top of an unchanged operating model — which is exactly why investing in the durable concepts now, rather than memorising one API's YAML, is the higher-leverage way to learn the tool.

---

## Did You Know?

- **Kyverno policies are Kubernetes resources**: You can manage them with GitOps tools such as Argo CD or Flux, review them with ordinary pull requests, and apply RBAC around who can change cluster-wide policy.
- **Generate rules make Kyverno more than a validator**: A platform team can create default NetworkPolicies, ResourceQuotas, and other namespace scaffolding automatically when teams onboard.
- **Audit mode is a rollout tool, not a security boundary**: It records violations so teams can measure impact, but it still allows violating resources to be admitted.
- **PolicyReports follow a shared Kubernetes policy reporting model**: This makes it easier to build dashboards and workflows around pass, fail, warn, error, and skip results.

---

## Common Mistakes

| Mistake | Problem | Better approach |
|---|---|---|
| Enforcing a new ClusterPolicy immediately across every namespace | Existing workloads can be blocked without warning, and emergency releases may fail for reasons teams have never seen | Start in `Audit`, review PolicyReports, fix shared templates, then enforce in scoped phases |
| Forgetting system namespace exclusions | Controllers in `kube-system`, Kyverno itself, or node-related components can be affected by application-focused rules | Add explicit excludes for system namespaces and test platform add-ons before broad enforcement |
| Treating mutation as invisible convenience | Developers may see GitOps drift or runtime behavior that differs from submitted manifests | Document defaults, prefer add-if-missing patches, and test mutation through the real delivery path |
| Using generate rules without deciding ownership | Teams may edit generated resources and then have Kyverno revert them, or they may assume the platform owns every related exception | Decide whether generated resources are managed controls or starting templates, then set `synchronize` accordingly |
| Checking only `containers` in security rules | Risky settings can remain in `initContainers` or other supported container arrays | Include conditional patterns for relevant container arrays and test manifests with multiple workload shapes |
| Writing vague denial messages | Developers cannot tell whether to change a field, request an exception, or contact the platform team | Write messages that explain the risk and the concrete remediation path |
| Skipping CLI tests for policies | A small match, exclude, or pattern mistake can affect many namespaces before anyone notices | Keep passing and failing manifests beside each policy and run `kyverno apply` or `kyverno test` in CI |
| Choosing Kyverno only because YAML feels easy | YAML policies can still encode subtle logic, broad blast radius, and operational coupling | Evaluate maintainability, expressiveness, ownership, rollout path, and integration needs before standardizing |

---

## Quiz

### Question 1

Your platform team wants to require `app` and `team` labels on Pods because incident responders struggle to find owners. The cluster already has hundreds of unlabeled Pods across many namespaces. How should you roll out the Kyverno policy, and what evidence should you collect before switching to enforcement?

<details>
<summary>Show Answer</summary>

Start with a ClusterPolicy using `validationFailureAction: Audit` and `background: true`, then review PolicyReport and ClusterPolicyReport results to identify existing violations. Group failures by namespace, team, and shared deployment template so you can fix common sources instead of treating every workload as a separate exception. After the violation count is low and teams know the remediation path, enforce in a limited set of namespaces before expanding cluster-wide.

</details>

### Question 2

A developer reports that their Pod was denied with the message "Floating image tags are not allowed," even though the image field is `registry.kubedojo.internal/api:v1.8.2`. What should you check before assuming Kyverno has a bug?

<details>
<summary>Show Answer</summary>

Check whether another container, init container, or generated sidecar uses `latest`, and inspect the full admission error to identify the rule that denied the request. Then review all matching ClusterPolicies because more than one policy may evaluate the same Pod. Also verify that the submitted manifest is the one that reached the API server, since Helm, Kustomize, or CI templating may have rendered a different image than the developer expected.

</details>

### Question 3

A namespace onboarding policy generates a default-deny NetworkPolicy with `synchronize: true`. A team deletes the generated NetworkPolicy during troubleshooting, and it reappears. Was Kyverno behaving correctly, and how should the platform team handle the team's need for connectivity?

<details>
<summary>Show Answer</summary>

Kyverno behaved correctly because `synchronize: true` tells it to reconcile the generated resource. The platform team should keep the generated default-deny policy as the baseline and help the team add separate allow policies for required traffic, such as DNS or ingress-controller access. If teams are expected to customize the generated object itself, then synchronization may be the wrong ownership model.

</details>

### Question 4

Your organization wants to inject a logging sidecar into selected workloads. A teammate proposes a Kyverno mutation policy that adds the sidecar to every Pod in every namespace. What risks should you identify, and what safer design would you recommend?

<details>
<summary>Show Answer</summary>

The broad mutation could change runtime behavior, resource consumption, startup time, and failure modes for workloads that were never tested with the sidecar. It could also create GitOps drift and unclear ownership for sidecar upgrades. A safer design is to scope the policy by namespace or annotation, require explicit opt-in at first, document the injected container, set resource requests and limits, and provide an emergency opt-out process.

</details>

### Question 5

A production signature verification policy blocks a release because the image is unsigned. The application team says the image came from the approved registry and passed vulnerability scanning. How should you explain the denial and what should you investigate?

<details>
<summary>Show Answer</summary>

Registry approval and vulnerability scanning do not prove that the image was signed by the trusted build identity required by the policy. The denial means the admission evidence did not match the verification rule, not necessarily that the image contains a known vulnerability. Investigate whether the build workflow signed the image, whether the subject and issuer in the policy match the CI identity, whether the image reference points to the signed artifact, and whether emergency release workflows also produce signatures.

</details>

### Question 6

A Kyverno policy works when tested against a new Pod creation, but existing violating Pods do not appear in reports. The policy has `validationFailureAction: Audit`, but the team forgot to set another field. What is likely missing, and why does it matter?

<details>
<summary>Show Answer</summary>

The policy likely lacks `background: true`, or the rule uses admission-only request context that cannot be evaluated during background scans. Background scanning matters because it evaluates existing resources and reports violations that were already present before the policy was deployed. Without it, audit mode may show only future admission activity, which gives an incomplete picture of production risk.

</details>

### Question 7

A platform team is choosing between Kyverno and Gatekeeper for a new policy program. Most rules are Kubernetes-specific defaults, namespace scaffolding, image checks, and simple structural validation. However, the security team already uses Rego for infrastructure policy outside Kubernetes. How would you recommend approaching the decision?

<details>
<summary>Show Answer</summary>

Kyverno is a strong fit for Kubernetes-native defaults, mutation, generation, and image verification because those requirements map directly to its resource model. Gatekeeper or OPA may remain valuable for cross-domain policy where Rego is already established. A pragmatic recommendation is to assign clear ownership boundaries, such as Kyverno for cluster admission defaults and generation, while OPA handles broader infrastructure policy, avoiding duplicate rules that produce conflicting decisions.

</details>

---

## Hands-On Exercise

### Objective

Install Kyverno in a local Kubernetes cluster, deploy validation and generation policies, test admission behavior, inspect policy reports, and practice a safe audit-to-enforce rollout. The exercise assumes Kubernetes 1.35+ behavior and uses ordinary `kubectl` commands so you can adapt the flow to Kind, Minikube, or a managed development cluster.

### Setup

Create a local cluster and install Kyverno with Helm. If you already have a disposable lab cluster, you may skip the cluster creation step, but do not run this exercise against a shared production cluster.

```bash
kind create cluster --name kyverno-lab

helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace

kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/instance=kyverno \
  -n kyverno \
  --timeout=180s

kubectl get pods -n kyverno
```

### Task 1: Create an audit-mode label policy

Create `require-platform-labels.yaml` and apply it. Keep the policy in audit mode so you can observe behavior before enforcement.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-platform-labels
spec:
  validationFailureAction: Audit
  background: true
  rules:
  - name: require-app-and-team
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Pods must include app and team labels so ownership is visible during incidents."
      pattern:
        metadata:
          labels:
            app: "?*"
            team: "?*"
```

```bash
kubectl apply -f require-platform-labels.yaml

kubectl run audit-unlabeled --image=nginx:1.27

kubectl get policyreport -A
kubectl get clusterpolicyreport
```

The unlabeled Pod should be admitted because the policy is in audit mode. The important result is the report entry, because that is what tells the platform team how much work enforcement would create. If no report appears immediately, wait briefly and check Kyverno pods before changing the policy.

### Task 2: Move the label policy to enforcement and compare behavior

Edit the policy so `validationFailureAction` is `Enforce`, then apply it again. Use one bad Pod and one good Pod so you see both sides of the admission decision.

```bash
kubectl apply -f require-platform-labels.yaml

kubectl run enforce-unlabeled --image=nginx:1.27

kubectl run enforce-labeled \
  --image=nginx:1.27 \
  --labels="app=web,team=platform"
```

The unlabeled Pod should be denied with the policy message, while the labeled Pod should be created. If both fail, inspect the exact error and check whether another policy is involved. If both pass, confirm that the policy is still present and that Kyverno admission webhooks are configured.

### Task 3: Add a policy that blocks floating image tags

Create `disallow-floating-image-tags.yaml` and apply it. This policy should be enforced because the remediation is simple and the error message is specific.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-floating-image-tags
spec:
  validationFailureAction: Enforce
  background: true
  rules:
  - name: require-explicit-container-tags
    match:
      any:
      - resources:
          kinds:
          - Pod
    exclude:
      any:
      - resources:
          namespaces:
          - kube-system
          - kube-public
          - kyverno
    validate:
      message: "Floating image tags are not allowed. Use a version tag or digest so rollbacks and audits are deterministic."
      pattern:
        spec:
          containers:
          - image: "!*:latest"
```

```bash
kubectl apply -f disallow-floating-image-tags.yaml

kubectl run bad-image \
  --image=nginx:latest \
  --labels="app=web,team=platform"

kubectl run good-image \
  --image=nginx:1.27 \
  --labels="app=web,team=platform"
```

The `bad-image` Pod should be denied, and the `good-image` Pod should be created. Notice that the label policy still applies, which is why the commands include labels. In production, multiple policies combine to define the admission contract.

### Task 4: Generate a default-deny NetworkPolicy for new namespaces

Create `generate-default-deny-networkpolicy.yaml` and apply it. Then create a namespace and confirm that Kyverno adds the NetworkPolicy.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: generate-default-deny-networkpolicy
spec:
  rules:
  - name: create-default-deny-for-new-namespaces
    match:
      any:
      - resources:
          kinds:
          - Namespace
    exclude:
      any:
      - resources:
          names:
          - kube-system
          - kube-public
          - kube-node-lease
          - kyverno
    generate:
      synchronize: true
      apiVersion: networking.k8s.io/v1
      kind: NetworkPolicy
      name: default-deny-all
      namespace: "{{ request.object.metadata.name }}"
      data:
        spec:
          podSelector: {}
          policyTypes:
          - Ingress
          - Egress
```

```bash
kubectl apply -f generate-default-deny-networkpolicy.yaml

kubectl create namespace generated-demo

kubectl get networkpolicy -n generated-demo
kubectl get networkpolicy -n generated-demo default-deny-all -o yaml
```

The namespace should contain a `default-deny-all` NetworkPolicy. If you delete it, Kyverno should recreate it because synchronization is enabled. That behavior is desirable for a managed security baseline, but you should be able to explain why it might be wrong for a team-customized template.

### Task 5: Test policies locally with the Kyverno CLI

Install the Kyverno CLI and test at least one policy against a manifest before applying it to the cluster. This step reinforces the shift-left workflow that production teams use in pull requests.

```bash
brew install kyverno

mkdir -p kyverno-lab/policies kyverno-lab/resources

cp require-platform-labels.yaml kyverno-lab/policies/

cat > kyverno-lab/resources/bad-pod.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: bad-pod
spec:
  containers:
  - name: nginx
    image: nginx:1.27
EOF

cat > kyverno-lab/resources/good-pod.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: good-pod
  labels:
    app: web
    team: platform
spec:
  containers:
  - name: nginx
    image: nginx:1.27
EOF

kyverno apply kyverno-lab/policies/ --resource kyverno-lab/resources/ --detailed-results
```

The CLI should show different results for the labeled and unlabeled resources. If it does not, inspect whether your policy is still in audit mode, whether the resource kind matches, and whether the manifest contains the fields the pattern expects. Use CLI testing to debug policy intent before you debug cluster behavior.

### Task 6: Clean up the lab

Delete the lab resources when you are finished. If you created a disposable Kind cluster, deleting the cluster is the simplest cleanup.

```bash
kind delete cluster --name kyverno-lab
```

### Success Criteria

- [ ] Kyverno pods are running in the `kyverno` namespace before policies are applied.
- [ ] An audit-mode label policy admits an unlabeled Pod and records a report result.
- [ ] The same label policy blocks an unlabeled Pod after switching to enforcement.
- [ ] A labeled Pod with a pinned image is admitted successfully.
- [ ] A Pod using `nginx:latest` is denied with a clear remediation message.
- [ ] A new namespace receives a generated `default-deny-all` NetworkPolicy.
- [ ] You can explain why `synchronize: true` recreates the generated NetworkPolicy after deletion.
- [ ] The Kyverno CLI evaluates at least one passing manifest and one failing manifest before cluster admission.

### Bonus Challenge

Write a namespaced `Policy` for a namespace called `development` that adds `environment: dev` to Pods only when the label is missing. Then create one Pod without the label and one Pod with `environment: test`, and verify that Kyverno defaults only the missing value instead of overwriting the explicit one.

---

## Next Module

Continue to the [Security Tools README](./) to review the rest of the security toolkit modules and choose the next control to practice.

## Sources

- [Kubernetes Admission Controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/) — Canonical reference for where admission policy runs in the API request path.
- [Kyverno README](https://raw.githubusercontent.com/kyverno/kyverno/main/README.md) — Primary upstream overview of Kyverno's core capabilities and positioning.
- [Kyverno ClusterPolicy CRD](https://raw.githubusercontent.com/kyverno/kyverno/main/config/crds/kyverno/kyverno.io_clusterpolicies.yaml) — Schema-level source for policy settings such as admission, background scanning, and rule types.
- [Kubernetes Images](https://kubernetes.io/docs/concepts/containers/images/) — Authoritative source for mutable tags, immutable digests, and production guidance around `:latest`.
- [kubernetes.io: network policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — The Kubernetes NetworkPolicy documentation includes the default deny all ingress and egress pattern.
- [kubernetes.io: resource quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/) — The Kubernetes ResourceQuota documentation directly defines namespace-level aggregate resource constraints.
- [kubernetes.io: limit range](https://kubernetes.io/docs/concepts/policy/limit-range/) — The Kubernetes LimitRange documentation directly describes these constraints and defaulting behavior.
- [nist.gov: security considerations code signing](https://www.nist.gov/publications/security-considerations-code-signing) — NIST's code-signing publication directly describes integrity and source-authentication guarantees, which supports the module's distinction between signing and vulnerability assessment.
- [raw.githubusercontent.com: howto.md](https://raw.githubusercontent.com/open-policy-agent/gatekeeper/master/website/docs/howto.md) — The Gatekeeper how-to documentation directly explains ConstraintTemplates, constraints, and Rego use.
- [raw.githubusercontent.com: README.md](https://raw.githubusercontent.com/open-policy-agent/opa/main/README.md) — The OPA README directly describes OPA as a general-purpose policy engine with integrations across the stack.
- [kubernetes.io: admission webhooks good practices](https://kubernetes.io/docs/concepts/cluster-administration/admission-webhooks-good-practices/) — The Kubernetes admission webhook good-practices page directly covers latency, timeouts, availability, and failure-policy concerns.
