---
title: "Module 3.6: Security Basics (Theory)"
slug: k8s/kcna/part3-cloud-native-architecture/module-3.6-security-basics
sidebar:
  order: 7
revision_pending: false
---

- **Complexity**: `[MEDIUM]` - Long-form security foundations module with access-control and policy evaluation practice
- **Time to Complete**: 35-40 minutes
- **Prerequisites**: Modules 3.1-3.5 (Cloud Native Architecture)
- **Kubernetes target**: Kubernetes 1.35+

## Learning Outcomes

After completing this module, you will be able to apply the three-gate security model to realistic Kubernetes design reviews and incident triage:

1. **Diagnose** identity and access failures by tracing authentication, authorization, admission control, RBAC subjects, roles, and bindings.
2. **Design** a least-privilege ServiceAccount and RoleBinding model for a namespace-scoped workload.
3. **Evaluate** image trust risk by comparing mutable tags, immutable digests, scanning results, and provenance signals.
4. **Implement** runtime containment choices by selecting appropriate Pod Security Standards and NetworkPolicies.

## Why This Module Matters

The most common Kubernetes breaches are not cinematic zero-day stories with custom exploit chains. They are plain control-plane exposures: an admin dashboard reachable on the internet, a kubelet API without authentication, an etcd port left open during a hasty migration. The textbook 2018 case at a major automotive company is documented in [the CKS GUI security module](../../../cks/part1-cluster-setup/module-1.5-gui-security/) <!-- incident-xref: tesla-2018-cryptojacking --> — once attackers reached the dashboard, they did not need a sophisticated exploit; they used the cluster to run mining workloads and hid the activity by keeping resource usage low enough to avoid obvious alarms. Kubernetes can be powerful and well-engineered while still being defeated by a single missing access control.

The same pattern appears in many Kubernetes incidents because clusters are built from several security decisions that look harmless when viewed alone. A default ServiceAccount seems convenient until every pod inherits a token it does not need. A broad ClusterRoleBinding seems like a quick way to unblock a deployment until a compromised CI job can read Secrets across the whole cluster. A familiar image tag seems stable until the tag moves and the workload no longer matches the software that passed review. Security basics are not basic because they are easy; they are basic because every higher-level control depends on them.

This module builds the mental model behind Kubernetes security rather than turning you into a CKS candidate in one lesson. You will practice reading a cluster design the way an operator reads a building plan: who can enter, what they can bring in, and how much damage they can cause once something goes wrong. The goal is not to memorize every field in every policy. The goal is to diagnose where a failure belongs, compare the available controls, and make a defensible first improvement before the system grows more complex.

This curriculum uses the `k` alias for `kubectl`. If following along in a lab, define it in your shell:

```bash
alias k=kubectl
```

## The Three Gates: A Building Security Analogy

Kubernetes security is easier to reason about when you stop treating it as one giant feature named "security" and start treating it as a sequence of gates. A secure office building does not rely on a single guard who solves every problem. It checks identity at the door, inspects what people bring inside, and still limits what a visitor can reach if they get past the lobby. A Kubernetes cluster needs the same layered posture because no single control can answer every question.

```
THE THREE SECURITY GATES

  YOU ──► GATE 1 ──► GATE 2 ──► GATE 3 ──► INSIDE
          Badge       Bag Check   Seatbelt

  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
  │   GATE 1:      │  │   GATE 2:      │  │   GATE 3:      │
  │   BADGE         │  │   BAG CHECK    │  │   SEATBELT     │
  │                │  │                │  │                │
  │ "Who are you?" │  │ "What are you  │  │ "What can you  │
  │ "What can you  │  │  bringing in?" │  │  do once        │
  │  access?"      │  │                │  │  inside?"      │
  │                │  │                │  │                │
  │ K8s: API Auth  │  │ K8s: Image     │  │ K8s: Pod       │
  │ & RBAC         │  │ trust, scans,  │  │ Security,      │
  │                │  │ provenance     │  │ NetworkPolicy  │
  └────────────────┘  └────────────────┘  └────────────────┘
```

Gate 1 is identity and access. Kubernetes first needs to know who is making a request, then it needs to decide whether that identity may perform the requested action on the requested resource. This is where authentication, authorization, admission control, and RBAC connect. When this gate fails, the cluster often gives a person, tool, or workload more API access than it needs, which turns a small credential leak into a broad control-plane problem.

Gate 2 is image trust. A container image is the software package Kubernetes will run, but Kubernetes does not automatically know whether that package came from a trusted build, includes known vulnerable libraries, or still matches the image that passed testing last week. The bag-check analogy is useful because the risk enters before the workload starts. Once a compromised image is admitted to the cluster, Pod Security and NetworkPolicy can reduce damage, but they cannot make the software trustworthy after the fact.

Gate 3 is runtime containment. Even well-authenticated users can deploy vulnerable applications, and even well-scanned images can contain unknown flaws. Runtime controls assume that something eventually fails and ask how much blast radius remains. Pod Security Standards limit dangerous Linux and host integrations, while NetworkPolicies reduce the ability of one compromised pod to scan or call every internal service. Defense in depth means each gate is valuable on its own and stronger when the other two are also present.

**Pause and predict:** imagine a workload that uses a dedicated ServiceAccount, an image pinned by digest, and a pod spec that sets `privileged: true`. Which gate is strong, which gate is weak, and what kind of incident could still happen if the application is exploited? Write your answer before continuing, because this habit of assigning a finding to a gate is the simplest way to avoid vague security conversations.

## Gate 1: Identity, API Requests, and RBAC

Every meaningful Kubernetes security discussion eventually returns to the API server. Users create Deployments through it, controllers reconcile desired state through it, pods may call it through ServiceAccount tokens, and admission plugins inspect objects before they are persisted. That means a cluster's first security question is not "Which container is running?" but "Which identity is asking the API server to do what?" If you can answer that question precisely, many Kubernetes security controls become easier to compare.

The Kubernetes API request lifecycle has three major stages. Authentication asks who the caller is, usually through a client certificate, bearer token, webhook, or external identity provider such as OIDC. Authorization asks whether that authenticated caller may perform a verb, such as `get`, `create`, or `delete`, against a resource such as Pods, Secrets, or Deployments. Admission control runs after authorization and inspects the object being created or changed, which allows the cluster to reject a risky pod even when the user is otherwise allowed to create pods.

The distinction matters because each failure produces a different fix. If a developer receives an authentication error, granting a RoleBinding will not help because Kubernetes still does not trust the identity. If a developer is authenticated but receives a forbidden response, the likely problem is authorization, not admission. If the developer can create ordinary pods but the API rejects one that uses `hostNetwork: true`, RBAC may be working exactly as configured while admission blocks a dangerous payload. Good diagnosis starts by naming the layer that said no.

The following RBAC diagram from the original lesson is worth preserving because it captures the entire authorization relationship in one picture. A subject is the "who," a role is the "can do what," and a binding is the glue that connects the two. The part new Kubernetes users often miss is scope: a Role and RoleBinding live in a namespace, while a ClusterRole and ClusterRoleBinding can apply cluster-wide. Choosing the wider object because it is convenient is one of the fastest ways to make a future incident larger than it needed to be.

```
RBAC FLOW

  SUBJECT              BINDING              ROLE               RESOURCE
  (who)                (glue)               (permissions)      (what)

  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
  │ User     │    │              │    │ Role         │    │ Pods     │
  │ Group    │───►│ RoleBinding  │───►│ (namespace)  │───►│ Secrets  │
  │ Service  │    │ or Cluster   │    │ or Cluster   │    │ ConfigMaps│
  │ Account  │    │ RoleBinding  │    │ Role (global)│    │ Deploys  │
  └──────────┘    └──────────────┘    └──────────────┘    └──────────┘

  "Who"            "connects"           "can do what"       "to which
                    who to what                              things"
```

ServiceAccounts deserve special attention because they are workload identities. A human engineer normally authenticates through a kubeconfig, but a pod that needs to call the API server uses a ServiceAccount token. Kubernetes creates a `default` ServiceAccount in every namespace, and pods use it unless the pod spec names another ServiceAccount. That default behavior is convenient for a lab and risky in production because it makes identity implicit. A safer design names a dedicated ServiceAccount per workload and gives it only the verbs and resources the workload actually needs.

This minimal Role and RoleBinding example grants read-only access to ConfigMaps and Secrets in a single namespace, then attaches those permissions to a ServiceAccount named `app`. The YAML is intentionally small because the goal is to see the shape of the relationship rather than copy a production policy. Notice that the role lists verbs explicitly instead of using a wildcard, and notice that the RoleBinding references a Role rather than a ClusterRole. Those details are boring in the best possible way: they keep the authorization surface narrow.

```yaml
# Minimal Role + Binding example (namespace-scoped)
kind: Role
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: read-config
rules:
- apiGroups: [""]
  resources: ["configmaps","secrets"]
  verbs: ["get","list"]
---
kind: RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: bind-read-config
subjects:
- kind: ServiceAccount
  name: app
roleRef:
  kind: Role
  name: read-config
  apiGroup: rbac.authorization.k8s.io
```

You can test an RBAC decision without guessing by asking the API server the same authorization question it would answer during a request. In a real cluster, `k auth can-i` is one of the safest first commands because it does not mutate anything; it simply asks whether a subject can perform a verb on a resource. The example below is not a substitute for reviewing the YAML, but it gives an operator a quick way to confirm whether the policy behaves like the design says it should.

```bash
k auth can-i get secrets --as=system:serviceaccount:default:app
k auth can-i delete pods --as=system:serviceaccount:default:app
```

The principle of least privilege is easy to state and hard to practice because engineering teams naturally optimize for speed during delivery pressure. A pipeline that can do everything will unblock every release until the day its token leaks. A developer group with cluster-wide powers will avoid help-desk tickets until the day someone deletes resources outside their namespace. Least privilege forces a different question: what is the smallest set of actions that still lets this identity do its job, and how will we notice when that job changes?

**Before running this in a real cluster, what output do you expect?** If the ServiceAccount only has the Role shown above, it should be able to read Secrets in its namespace but should not be able to delete Pods. If your prediction and the command output disagree, do not immediately widen the policy. First check the namespace, the subject name, the binding scope, and whether another binding grants permissions you forgot existed.

**Hypothetical scenario:** a platform team discovers that an internal deployment tool has `cluster-admin` because an early prototype needed to create namespaces and nobody revisited the binding. Months later the tool only updated Deployments in two namespaces, but the old binding remained. When the team simulated a compromised pipeline token, the token could read Secrets, patch admission webhooks, and delete workloads across the cluster. The fix was not exotic: split namespace creation into a controlled admin workflow, give the pipeline a namespaced Role for deployment updates, and audit the remaining ClusterRoleBindings on a schedule.

## Gate 2: Image Trust, Tags, Scanning, and Provenance

Kubernetes schedules containers, but it does not magically prove that the container image is the one your team intended to run. An image reference looks like a small string in a manifest, yet that string connects your cluster to a registry, a build pipeline, a base operating system, application dependencies, and a history of patches. If you treat that string casually, you outsource part of your security decision to whichever person or process can change the registry reference.

Tags are the first trap because they look stable while behaving like pointers. A tag such as `nginx:1.25` or `myapp:production` can be moved to a different image after your review. That mutability is useful during development because humans can remember names more easily than hashes, but it weakens production reproducibility. Two pods created from the same manifest at different times may pull different image contents if the tag changes and the local node cache does not already have the old image.

```
TAG (mutable -- can change)
  nginx:1.25

DIGEST (immutable -- content-addressed)
  nginx@sha256:6a5db2a1c89e0deaf...

If a single byte changes, the digest changes.
Tags can be re-pointed. Digests cannot be faked.
```

An image digest is a content-addressed identifier, which means the reference changes when the image content changes. Pinning production workloads by digest gives incident responders and release engineers a precise answer to "what is running?" It also creates a real maintenance tradeoff. Digest pinning will not automatically pull a patched image just because a tag moved, so the organization needs automation that updates digests, runs tests, and opens reviewable changes. Security improves when immutability and update automation travel together.

Image scanning answers a different question: what known vulnerabilities or risky packages exist inside this image? Scanners usually inspect image layers, identify packages and language dependencies, and compare versions against vulnerability data. The result is not a magical secure or insecure label. It is evidence for a decision. A critical vulnerability in an unused package may still require cleanup, while a remotely exploitable flaw in the running application path may block a release until the base image or dependency is patched.

Provenance asks where the image came from and whether the build process is trustworthy. Signing tools such as Sigstore cosign can attach cryptographic signatures and attestations to images, allowing a cluster policy or release process to require that images come from a known pipeline. At the KCNA level, you do not need to memorize every signature command. You do need the concept: scanning tells you what is inside, while provenance tells you who built it and whether the build path matches your trust policy.

The bag-check gate is especially important because Kubernetes manifests often move faster than security review. A team may copy a public image into a prototype, then promote the same manifest into staging and production because it "worked." Another team may rely on a mutable internal tag because their deployment system was built before digest pinning became common. Neither team is careless in a moral sense; they are experiencing normal delivery pressure. The security design must make the safer path convenient enough that speed does not always defeat it.

**Which approach would you choose here and why?** For a production payment API, compare three options: a public image by tag, an internal image by tag after scanning, or an internal image by digest with signature verification. The last option has more operational machinery, but it gives you a clearer chain from source to runtime. For a throwaway local demo, that extra machinery may be unnecessary; for a sensitive service, it is the difference between hoping and verifying.

Here is the worked way to evaluate an image reference during review. First, ask whether the image comes from a registry your organization trusts. Second, ask whether the reference is immutable for production. Third, ask whether vulnerability scanning happened close enough to deployment that the data is useful. Fourth, ask whether the image can be traced back to a controlled build pipeline. If the answer to any of those questions is "we assume so," you have found the gap to close.

A realistic incident response angle shows why this matters. Suppose a team reports that a pod restarted and now behaves differently, but the Deployment still says `myapp:production`. Without a digest, you must inspect node caches, registry history, CI logs, and rollout timing to reconstruct which bytes ran. With a digest, the manifest itself records the exact content. That does not solve the incident, but it removes a whole class of uncertainty while everyone is already under pressure.

## Gate 3: Pod Security and Network Segmentation

Runtime containment starts with an uncomfortable assumption: one of your workloads will eventually be vulnerable, misconfigured, or tricked into doing something it should not do. A secure cluster therefore tries to reduce the permissions and reach of each workload before compromise occurs. Pod Security Standards focus on what a pod can do to the node and kernel boundary. NetworkPolicies focus on what a pod can reach over the network. Together they turn a single exploited application from a cluster-wide problem into a smaller investigation.

Many container images run as root inside the container unless the image author or pod spec says otherwise. Root inside a container is not automatically root on the node, but it becomes far more dangerous when combined with hostPath mounts, extra Linux capabilities, privileged mode, host networking, host PID access, or writable host filesystems. Kubernetes gives you the vocabulary to deny these combinations before they reach a node. The important lesson is that runtime safety is not a single checkbox; it is a set of choices that reduce the usefulness of an exploit.

Host networking is dangerous for similar reasons. A pod using `hostNetwork: true` shares the node's network namespace, which lets it bind ports on the node and interact with traffic in ways ordinary pod networking would not allow. Some infrastructure components genuinely need host-level access, especially networking agents and node-level system software. Most application workloads do not. When an ordinary web app asks for host networking, the correct first response is not "sure"; it is "what exact node-level capability are you trying to use?"

Kubernetes defines three Pod Security Standards as named policy levels. These levels are enforced by the built-in Pod Security Admission controller when namespaces are labeled for enforcement, audit, or warning behavior. The `pod-security.kubernetes.io/enforce`, `warn`, and `audit` labels can be set independently — for example, `warn: restricted` surfaces violations without blocking workloads while the team fixes images, then `enforce: restricted` applies once compatibility is proven.

| Level | What It Allows | Use Case |
|---|---|---|
| **Privileged** | Everything. No restrictions. | System-level infrastructure (CNI, storage drivers) |
| **Baseline** | Blocks the most dangerous settings (hostNetwork, privileged containers, hostPath) while remaining broadly compatible | General-purpose workloads with minimal changes |
| **Restricted** | Requires running as non-root, drops all capabilities (only `NET_BIND_SERVICE` add-back allowed), seccomp `RuntimeDefault`, restricted volume types, no privilege escalation | Security-sensitive and hardened workloads |

Baseline is often the practical first step for a mixed application environment because it blocks the clearest foot-guns without forcing every existing image to be rebuilt immediately. Restricted is the better target for sensitive workloads, new services, and teams that control their Dockerfiles. The tradeoff is developer friction. An application that writes temporary files into its root filesystem or assumes it can bind privileged ports may fail under Restricted until the team adjusts the image and runtime configuration. That friction is not a reason to avoid Restricted; it is a reason to plan the migration deliberately.

NetworkPolicies address a different default. In Kubernetes, pods can generally communicate with other pods unless a policy selects them and restricts traffic. That open network is friendly for early development and hazardous for production. A compromised frontend pod should not automatically reach a database, a metrics backend, and an internal admin tool just because they share a cluster. NetworkPolicies let you describe allowed traffic by pod labels, namespace labels, ports, and direction.

```
WITHOUT NetworkPolicy          WITH NetworkPolicy

  ┌─────┐     ┌─────┐          ┌─────┐     ┌─────┐
  │ Web │────►│ DB  │          │ Web │────►│ DB  │
  └─────┘     └─────┘          └─────┘     └─────┘
      │                                        X
      │                                        │ (blocked)
  ┌─────┐     ┌─────┐          ┌─────┐     ┌─────┐
  │ Log │────►│ DB  │          │ Log │     │ DB  │
  └─────┘     └─────┘          └─────┘     └─────┘

  Everyone can reach              Only Web can
  reach everything                reach DB
```

A default-deny posture is the common secure pattern. You first create a policy that selects pods and denies ingress or egress by default, then you add narrow allow policies for traffic the application truly needs. This model feels slower the first time because teams must name dependencies that used to be implicit. That is also the benefit. The dependency list becomes reviewable, testable, and much easier to reason about during an incident.

**Stop and think:** by default, every pod in many Kubernetes clusters can communicate with every other pod. If an attacker compromises a single pod in the `frontend` namespace, what resources could they access without NetworkPolicies in place? A good answer includes databases, admin dashboards, internal APIs, and possibly the Kubernetes API server if the pod also has a useful ServiceAccount token.

The following example shows a simple default-deny ingress policy. It is intentionally small so you can focus on the idea: select pods in the current namespace and allow no ingress rules. In a real application, you would add a second policy that permits traffic from frontend pods using `namespaceSelector` and `podSelector` labels, on the specific ports the service requires. NetworkPolicy behavior depends on a CNI plugin that implements it — verify support in your chosen networking layer before relying on policies in production. Calico, Cilium, and other CNIs implement NetworkPolicy, but default kubenet or some managed-cluster configurations may not enforce rules until you enable a compatible CNI.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: backend
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

A practical containment story often begins with a small application bug. Imagine a frontend service has a server-side request forgery flaw that lets an attacker make outbound HTTP calls from inside the pod. With no NetworkPolicies, the attacker can scan cluster DNS names, call internal services, and look for metadata endpoints or admin tools. With egress restrictions and namespace ingress policies, the same bug may still be serious, but the attacker's map is smaller. Security basics rarely make incidents impossible; they make incidents less explosive.

## Patterns & Anti-Patterns

Security patterns are useful only when they are tied to the reason they work. "Use least privilege" is a slogan until the team can describe the identity, the resource, the verb, and the namespace where the permission is needed. "Scan images" is vague until the release process says which vulnerabilities block deployment and who owns remediation. The patterns below are deliberately operational because Kubernetes security fails most often in the gap between a good principle and a repeatable workflow.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---|---|---|---|
| Dedicated workload ServiceAccounts | Any workload that calls the Kubernetes API or runs in a sensitive namespace | It gives each workload a distinct identity and prevents accidental inheritance from `default` | Automate ServiceAccount and Role creation in templates so teams do not copy broad bindings |
| Namespace-scoped RBAC first | Team-owned application namespaces and CI jobs that deploy to known namespaces | It limits compromised credentials to the area where the work actually happens | Use separate admin workflows for cluster-scoped resources instead of letting every pipeline manage them |
| Digest-pinned images with automated updates | Production workloads and regulated environments | It makes the running image reproducible while still allowing reviewed patch updates | Use dependency automation to refresh digests, run tests, and open reviewable changes |
| Baseline everywhere, Restricted where ready | Mixed clusters with both legacy and new applications | It blocks the most dangerous pod settings immediately while creating a path toward stronger hardening | Use Pod Security Admission in warn or audit mode before enforcing Restricted broadly |
| Default-deny plus narrow allow policies | Namespaces that contain databases, queues, control planes, or admin tools | It turns implicit network reachability into explicit application dependencies | Maintain labels carefully, because NetworkPolicy quality depends on accurate selectors |

Anti-patterns usually start as shortcuts. The dangerous part is not that a team makes one exception during an emergency; the dangerous part is that the exception becomes invisible infrastructure. A one-week `cluster-admin` binding survives for a year. A temporary `:latest` tag becomes the production release mechanism. A privileged pod added for troubleshooting becomes part of the permanent deployment. The fix is not only technical cleanup, but also an ownership habit: every exception needs a reason, an owner, and a review date.

| Anti-Pattern | Why Teams Fall Into It | Better Alternative |
|---|---|---|
| Binding developers or pipelines to `cluster-admin` | It immediately unblocks every permission error and avoids learning RBAC scope | Create namespace Roles for routine work and keep cluster-admin for controlled break-glass use |
| Using `default` ServiceAccounts everywhere | Pod specs are shorter and early demos work without extra YAML | Name workload-specific ServiceAccounts and disable token mounting for pods that do not call the API |
| Trusting image tags as release evidence | Tags are readable and fit human release names | Record release names separately and deploy immutable digests in manifests |
| Enforcing Restricted before testing applications | The security target is correct, but legacy images were not built for it | Run warn or audit mode first, fix images, then enforce Restricted by namespace |
| Creating NetworkPolicies without label discipline | Policies appear to exist, but selectors match too much or too little | Treat labels as part of the security contract and review them with the policy |

The most effective teams pair patterns together. A namespace that uses dedicated ServiceAccounts but has no NetworkPolicies still leaves a compromised application free to explore the network. A workload pinned by digest but running as privileged still turns an application flaw into a node-level problem. A default-deny network policy with a broad ServiceAccount token still leaves the API server as a valuable target. The three-gate model prevents false comfort because it asks you to check identity, supply chain, and runtime containment separately.

## Decision Framework

When you review a Kubernetes workload, start with the question that creates the most immediate blast radius: what identity does this workload use, and what can that identity do? If the pod does not need the Kubernetes API, disable automatic token mounting or ensure the ServiceAccount has no meaningful permissions. If it does need the API, write the Role as if you had to explain every verb to an incident reviewer. That framing changes `verbs: ["*"]` from a convenience into an unexplained liability.

Next, review the image reference and build evidence. For a development namespace, a readable tag from an internal registry may be acceptable if the namespace has limited access and the workload is disposable. For production, prefer a digest-pinned image from a trusted build pipeline with scan results and provenance. The decision is not "tags are always evil"; the decision is whether the environment can tolerate the ambiguity that tags introduce. Sensitive environments usually cannot.

Then review runtime containment. If the workload asks for privileged mode, host networking, hostPath, host PID, or extra capabilities, require a specific technical reason. Infrastructure components sometimes need these powers, but ordinary application services rarely do. Choose Baseline when you need broad compatibility quickly, and choose Restricted when the application can run as non-root with a tighter filesystem and capability model. Use warning or audit modes to learn what would break before you enforce a stricter level across a namespace.

Finally, review network reachability as an application dependency map. Ask which pods should initiate traffic, which pods should receive it, and which ports are required. If the team cannot answer, that is not a reason to leave the network open forever; it is a discovery task. Start with sensitive namespaces such as databases, queues, observability backends, and internal admin tools. A default-deny policy there produces immediate value because those targets are attractive during lateral movement.

| Review Question | Safer Default | Use a Broader Option Only When | Evidence to Ask For |
|---|---|---|---|
| Which ServiceAccount should the pod use? | Dedicated ServiceAccount with narrow Role | The workload truly needs shared identity across a controlled set of pods | Role rules, binding scope, and `k auth can-i` checks |
| How should the image be referenced? | Internal image pinned by digest | The workload is a disposable development demo | Registry ownership, scan result, and update automation |
| Which Pod Security level fits? | Baseline for compatibility, Restricted for sensitive services | The pod is node-level infrastructure with documented need | Namespace labels, warning output, and exception owner |
| What network traffic is allowed? | Default-deny plus explicit allow rules | The namespace is temporary and isolated from sensitive targets | Dependency map, labels, ports, and CNI NetworkPolicy support |

This framework is intentionally small enough to use during a design review. If a proposed workload passes all four rows, it is not automatically secure, but it has cleared the common KCNA-level failure modes. If it fails one row, the three-gate model tells you where to focus. If it fails several rows at once, do not accept a single broad fix such as "we will monitor it." Monitoring helps detect trouble, but it does not replace identity boundaries, image trust, or runtime containment.

## Putting the Gates Together in Reviews

A good Kubernetes security review sounds less like a courtroom argument and more like a disciplined walk through the system. Start by reading the workload manifest and naming the identity. If the pod uses `default`, ask whether that identity has any RoleBindings, whether token mounting is necessary, and whether another workload shares the same namespace. Then read the image reference and ask whether the exact bytes are reproducible. Only after that should you inspect privileged settings, host integration, and network reachability. The order is useful because it follows the path from API permission to software supply to runtime blast radius.

One practical review technique is to write one sentence per gate before proposing any fix. For example: "Badge risk: the analytics pod uses the namespace default ServiceAccount, and that identity can list Secrets." "Bag Check risk: the image uses a mutable release tag with no digest in the manifest." "Seatbelt risk: the pod requests privileged mode and the namespace has no Pod Security Admission enforcement." Those sentences force the reviewer to be specific. They also prevent a common mistake where a team responds to every finding with the same general control, such as scanning, monitoring, or documentation.

The three gates also help you set remediation priority. A privileged pod with a cluster-admin token is urgent because Gate 1 and Gate 3 fail together, making both API abuse and node-level abuse plausible after compromise. A digest-pinned image that has one medium vulnerability in an unused package may still need a patch, but it is a different level of emergency if RBAC and runtime containment are strong. Priority is not only severity labels from a scanner. Priority is the combination of exploitability, privilege, reachability, and the ability to move from one boundary to another.

During incident response, the same model becomes a questioning tool. For identity, ask which ServiceAccount token was mounted, which API calls were made, and whether audit logs show forbidden attempts or successful reads of sensitive resources. For image trust, ask which digest ran, when it was built, whether the registry reference changed, and whether the build pipeline was part of the suspected compromise. For runtime containment, ask whether the pod had host access, whether it ran as root, which namespaces it could reach, and which egress paths were open. These questions are concrete enough for different teams to investigate in parallel.

The model is also useful when teaching application teams because it avoids turning platform security into a list of unexplained prohibitions. Instead of saying "you cannot use hostPath," explain that hostPath crosses the seatbelt boundary by giving the container access to node files that ordinary application code should not touch. Instead of saying "we require digests," explain that tags are pointers and digests are evidence of exact content. Instead of saying "you need another ServiceAccount," explain that shared identity makes it impossible to grant one workload a permission without granting it to every pod that shares the account.

There is one final tradeoff to keep in view: controls that are invisible to developers are easier to adopt, but controls that are never understood are easier to bypass. Namespace templates, admission policies, and deployment automation should provide safe defaults, because nobody wants every team to handcraft security YAML from scratch. At the same time, engineers should understand the reason behind the defaults well enough to recognize exceptions. KCNA-level security knowledge is the vocabulary for those conversations. It lets a beginner ask the right question before the cluster has accumulated years of hidden risk.

When you are unsure where to begin, choose one workload and trace it end to end. Name the ServiceAccount, list the RoleBindings, inspect the image reference, check whether the namespace enforces a Pod Security level, and identify which NetworkPolicies select the pod. That small review is more useful than a broad security promise because it produces concrete evidence. It may reveal that the workload is already reasonably contained, or it may reveal that three unrelated teams each assumed another team owned the same boundary. Either result is actionable.

Security basics also become easier when you separate prevention from recovery. RBAC, image provenance, Pod Security, and NetworkPolicy are preventive controls because they reduce what can happen before an incident starts. Audit logs, registry history, scan records, and deployment records support recovery because they help you reconstruct what happened after suspicion appears. A mature cluster needs both, but they answer different questions. If a design relies only on recovery evidence, the attacker may already have too much room to move. If a design relies only on prevention, the team may struggle to prove what actually happened during a real event.

The KCNA exam will not ask you to build a complete enterprise security platform, but it expects you to recognize these relationships. A Secret exposed through overbroad RBAC is an identity and authorization problem, even if the image is perfectly scanned. A mutable tag in production is an image trust problem, even if the pod runs as non-root. A database reachable from every namespace is a runtime containment problem, even if the application team uses a dedicated ServiceAccount. The skill is to classify the risk accurately, then choose the control that changes the condition instead of merely sounding security-minded.

That classification habit is valuable beyond exams because it improves how teams communicate under pressure. A vague report such as "the cluster is insecure" gives an operator nowhere to start. A precise report such as "this namespace has no NetworkPolicy and the database accepts traffic from unrelated pods" points directly to a testable change. Clear language shortens the path from concern to remediation.

## Did You Know?

1. **Kubernetes RBAC became stable in Kubernetes 1.8**, replacing older authorization patterns for most clusters and making policy changes possible through normal API objects instead of static files.
2. **The default ServiceAccount exists in every namespace**, and pods use it unless another ServiceAccount is named, which is why implicit workload identity is a real security concern.
3. **Pod Security Policy was removed in Kubernetes 1.25**, and the built-in Pod Security Admission controller is now the standard native way to enforce Pod Security Standards.
4. **A single `privileged: true` pod with host access can undermine node isolation**, which is why Restricted policies reject dangerous host namespace and capability settings.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Using the `default` ServiceAccount for all workloads | Teams omit identity design because pods run without extra YAML, then every workload inherits whatever permissions the default identity has | Create a dedicated ServiceAccount per workload and bind only the namespace Role it needs |
| Granting `cluster-admin` to CI/CD pipelines | Broad permissions unblock releases quickly, especially when the pipeline manages more than one resource type | Split cluster-scoped setup from routine deployment and give the pipeline explicit verbs on explicit resources |
| Referencing images by tag (`:latest` or `:v2`) | Tags are readable and convenient, so teams mistake them for immutable release evidence | Use digests (`@sha256:...`) for production deployments and automate reviewed digest updates |
| Running containers as root | Base images often default to root, and application teams may not notice until hardening begins | Build images that run as a non-root user and set `runAsNonRoot: true` where appropriate |
| No NetworkPolicies in any namespace | Early clusters prioritize connectivity, and the open default survives after production data arrives | Apply a default-deny ingress policy per sensitive namespace, then allow specific traffic |
| Using wildcard RBAC rules (`verbs: ["*"]`) | Wildcards are easier than discovering the exact API verbs a tool needs | List each verb explicitly, such as `get`, `list`, `watch`, `create`, and `update` |
| Enforcing Restricted without a migration pass | The team chooses the right target but skips compatibility discovery for existing workloads | Run Pod Security Admission in warn or audit mode first, fix images, then enforce by namespace |

## Knowledge Check

<details>
<summary>Question 1: Your company uses `myapp:production` as the image tag for all deployments. A developer pushes a new build to the same tag. What security risk does this create, and how would you address it?</summary>

Mutable tags mean the image content can change without the reference changing. A deployment using `myapp:production` might pull a different image on each node or after a restart, potentially running untested or compromised code. This also breaks reproducibility because responders cannot tell which exact image is running from the manifest alone. The fix is to reference production images by their content-addressable digest and use automation to update that digest through review when a new build is approved.

</details>

<details>
<summary>Question 2: An intern deployed a pod with `privileged: true`. What risks does this create, and which runtime control should catch it?</summary>

A privileged container receives broad access to Linux capabilities and host-level operations that ordinary application pods should not need. If an attacker compromises the application, privileged mode can turn that application flaw into node compromise or container escape. Pod Security Admission enforcing Baseline or Restricted should reject this for normal workloads, while a review process should require a specific infrastructure reason for any exception. The remediation is to remove privileged mode and adjust the application to run within a safer Pod Security Standard.

</details>

<details>
<summary>Question 3: A team creates a single ClusterRole with `resources: ["*"]` and `verbs: ["*"]`, then binds it to all developers through a ClusterRoleBinding. Why is this a problem?</summary>

This grants every developer full administrative reach across resources and namespaces, including the ability to read Secrets, delete workloads, change RBAC, and possibly escalate further. The problem is not only that the permissions are broad; it is that the blast radius of one compromised credential becomes cluster-wide. A better design starts with namespace-scoped Roles for routine work and reserves cluster-scoped permissions for a smaller operational workflow. The team should verify the new policy with `k auth can-i` checks before removing the old binding.

</details>

<details>
<summary>Question 4: Your cluster has no NetworkPolicies configured. A pod in the `frontend` namespace is compromised. What can the attacker reach?</summary>

Without NetworkPolicies, Kubernetes networking is commonly open enough that the attacker can attempt connections to pods in other namespaces, including backend databases, internal APIs, and monitoring tools. If the pod also has a useful ServiceAccount token, the Kubernetes API server may become another target. The mitigation is to create default-deny policies in sensitive namespaces and then add narrow allow rules for required application flows. This does not fix the original compromise, but it reduces lateral movement.

</details>

<details>
<summary>Question 5: A security audit finds that many pods in the `analytics` namespace use the `default` ServiceAccount, and that ServiceAccount is bound to a ClusterRole that grants `get` and `list` on Secrets cluster-wide through a ClusterRoleBinding named `default-secret-reader`. What is the blast radius, and how would you remediate it?</summary>

The blast radius is severe because compromising any pod in `analytics` that mounts that token could expose Secrets across the entire cluster, not just within the namespace. Each namespace has its own `default` ServiceAccount, but a ClusterRoleBinding applies cluster-wide regardless of which namespace the subject lives in. The immediate fix is to remove or narrow the ClusterRoleBinding so the default ServiceAccount no longer inherits cluster-wide Secret access. The durable fix is to create dedicated ServiceAccounts for workloads that need the API and set no meaningful permissions for workloads that do not. For pods that never call the API, disabling automatic token mounting further reduces the value of a compromise.

</details>

<details>
<summary>Question 6: A developer authenticates successfully and has an RBAC Role allowing them to create Pods, but the API server rejects a Pod using `hostNetwork: true`. Compare authentication, authorization, and admission control in this scenario. Which layer blocked the request?</summary>

Authentication succeeded because the API server recognized the developer's identity. Authorization also succeeded because RBAC allowed that identity to create Pod objects. Admission control blocked the request after inspecting the content of the pod spec and finding a setting that violated policy. This is why RBAC and admission are complementary: RBAC decides whether you may access the endpoint, while admission decides whether this particular object is acceptable.

</details>

<details>
<summary>Question 7: A team pins images by digest but deploys every workload with the same highly privileged ServiceAccount. Which gate is strong, which gate is weak, and what should they fix first?</summary>

The image trust gate is stronger because digest pinning improves reproducibility and reduces ambiguity about the running software. The identity gate is weak because a shared highly privileged ServiceAccount gives every workload the same broad API reach. The first fix should be to split workload identities and bind namespace-scoped Roles with explicit verbs and resources. Digest pinning should remain in place, but it cannot compensate for a dangerous API identity.

</details>

## Hands-On Exercise

This exercise is a security design audit rather than a cluster mutation lab. That is intentional for a KCNA theory module: you are practicing how to classify findings, choose controls, and explain the reason for each fix. If you do have a disposable Kubernetes 1.35+ cluster, you can run the read-only `k auth can-i` checks from the RBAC section, but the main work here can be completed from the scenarios alone.

### Worked Example: Applying the Three Gates

Before you try the exercise below, evaluate one configuration using the Three Gates framework. A developer provides a snippet for a new internal analytics tool: it uses `image: internal-registry/analytics:v2`, names `serviceAccountName: default`, and sets `securityContext: { privileged: true }`. That single snippet crosses all three gates because the image reference is mutable, the workload identity is implicit, and the runtime setting is dangerous for an ordinary application.

The remediation should also be split by gate. For Gate 1, create a dedicated `analytics-sa` ServiceAccount with least-privilege RBAC instead of relying on `default`. For Gate 2, resolve the image to an immutable digest and ensure the image is scanned in the build or release pipeline. For Gate 3, remove privileged mode and label the namespace for Baseline or Restricted Pod Security Admission after testing compatibility. This is the habit you are building: classify the finding, then choose the control that actually addresses that class of risk.

### Your Turn

Review the following scenarios. For each one, identify which of the Three Gates it primarily violates and propose a specific configuration fix to secure it. Some scenarios have a secondary risk, but choose the primary gate first so your remediation stays focused.

| # | Scenario | Gate Violated | Proposed Fix |
|---|---|---|---|
| 1 | A web app deployment mounts the node's root filesystem using `hostPath: /`. | ? | ? |
| 2 | A CI/CD pipeline uses a ServiceAccount bound to a ClusterRole with `verbs: ["*"]`. | ? | ? |
| 3 | A deployment pulls `nginx:latest` directly from Docker Hub for a production app. | ? | ? |
| 4 | All pods in the `backend` namespace can freely receive traffic from the `frontend` and `testing` namespaces. | ? | ? |

- [ ] Classify each scenario as Badge, Bag Check, or Seatbelt.
- [ ] Write one specific Kubernetes control or manifest change that would reduce the risk.
- [ ] Explain why your proposed fix addresses the gate you selected rather than a different gate.
- [ ] Identify which finding you would remediate first in a production incident review.
- [ ] Compare your answers with the solution and revise any answer that relies on vague advice.

<details>
<summary>Suggested solution</summary>

| # | Gate Violated | Proposed Fix |
|---|---|---|
| 1 | Seatbelt (Gate 3) | Remove the `hostPath` mount. Enforce the Baseline or Restricted Pod Security Standard on the namespace to block host filesystem access, reducing host-level blast radius. |
| 2 | Badge (Gate 1) | Remove the wildcard verbs. Create a namespace-scoped Role that explicitly lists only the exact verbs (e.g., `create`, `update`, `get`) and resources (e.g., `deployments`, `services`) the pipeline actually needs. |
| 3 | Bag Check (Gate 2) | Change `nginx:latest` to a specific image digest (`nginx@sha256:...`). Ensure the image is pulled from a trusted, scanned internal registry rather than directly from Docker Hub. |
| 4 | Seatbelt (Gate 3) | Implement a default-deny NetworkPolicy in the `backend` namespace. Then, create a specific NetworkPolicy with `namespaceSelector` and `podSelector` that allows ingress from the `frontend` namespace on port 443 only. |

</details>

### Success Criteria

- [ ] You can explain why authentication, authorization, and admission control are separate API security stages.
- [ ] You can read a RoleBinding and identify the subject, role reference, and namespace scope.
- [ ] You can justify digest pinning without pretending it removes the need for patch automation.
- [ ] You can choose between Baseline and Restricted Pod Security Standards for a realistic workload.
- [ ] You can describe how a default-deny NetworkPolicy reduces lateral movement.

## Sources

- [Kubernetes documentation: Authentication](https://kubernetes.io/docs/reference/access-authn-authz/authentication/)
- [Kubernetes documentation: Authorization](https://kubernetes.io/docs/reference/access-authn-authz/authorization/)
- [Kubernetes documentation: Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Kubernetes documentation: Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/)
- [Kubernetes documentation: Admission Controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Kubernetes documentation: Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes documentation: Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [Kubernetes documentation: Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes documentation: Images](https://kubernetes.io/docs/concepts/containers/images/)
- [Kubernetes documentation: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes documentation: Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [Sigstore cosign documentation](https://docs.sigstore.dev/cosign/)

## Next Module

Continue to [Module 3.7: Community and Collaboration](/k8s/kcna/part3-cloud-native-architecture/module-3.7-community-collaboration/) to learn how open-source governance, SIGs, and the CNCF ecosystem shape Kubernetes development, because technical security decisions are also shaped by the people and project structures that maintain cloud native software.
