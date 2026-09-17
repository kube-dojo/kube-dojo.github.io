---
revision_pending: false
title: "Module 0.1: CKS Exam Overview"
slug: k8s/cks/part0-environment/module-0.1-cks-overview
sidebar:
  order: 1
lab:
  id: cks-0.1-cks-overview
  url: https://killercoda.com/kubedojo/scenario/cks-0.1-cks-overview
  duration: "25 min"
  difficulty: advanced
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Long-form orientation module with exam-format analysis and study-plan design
>
> **Time to Complete**: 20-25 minutes
>
> **Prerequisites**: CKA certification (must have passed CKA at any point before attempting CKS)

---

## What You'll Be Able to Do

After completing this module, you will be able to:

1. **Compare** CKA and CKS exam scope, domain weights, and operational expectations.
2. **Evaluate** CKS readiness by mapping official prerequisites, exam format, allowed resources, and domain weights to your current skills.
3. **Design** a CKS study plan that prioritizes high-weight security domains without ignoring Linux hardening.
4. **Diagnose** security posture gaps in a Kubernetes 1.35+ practice cluster using CKS-style inspection commands.
5. **Implement** a repeatable exam strategy for triaging quick wins, tool-heavy tasks, and complex security scenarios.

---

## Why This Module Matters

Exercise scenario: you have just passed CKA, and your cluster administration habits are strong enough that you can repair a broken deployment, rotate a certificate, and recover a failed control plane. A product team now asks whether that same cluster would survive a compromised container image, a workload running with excessive host access, or a namespace with no network boundary. The CKS exam exists in that gap between "the platform runs" and "the platform resists abuse."

The Certified Kubernetes Security Specialist is not a second pass through CKA with different labels. It assumes you already know how kubeadm clusters, Pods, Services, RBAC, and troubleshooting fit together, then asks whether you can reduce attack surface across build, deployment, and runtime. That distinction matters because a workload can be perfectly available while still running as root, accepting traffic from every namespace, mounting secrets too broadly, or shipping from an image that should never have entered the cluster.

This module gives you the map before you start the climb. You will compare CKA and CKS expectations, read the exam format as an engineering constraint, translate domain weights into study priorities, and practice a first security posture inspection. Treat the module as calibration: if a topic feels familiar from CKA, ask what the attacker would do with that same mechanism.

The examples in this track are written for Kubernetes 1.35+ behavior where Kubernetes API semantics are stable, but exam candidates should always check the Linux Foundation CKS pages before scheduling because the published exam environment version can change independently of this curriculum. The safer habit is to separate two ideas: learn current Kubernetes security practice deeply, and verify the exact exam version and allowed resources close to your booking date.

---

## CKS vs CKA: From Operations to Security Judgment

CKA trains you to keep Kubernetes usable under pressure. You learn to create resources, repair cluster components, configure networking, and debug workloads that do not start. CKS keeps those skills in play, but it changes the question you ask after every successful command. The new question is not merely whether the object exists or the Pod reaches `Running`; it is whether the object narrows privilege, limits blast radius, and creates enough evidence for later investigation.

```text
┌─────────────────────────────────────────────────────────────┐
│              CKA → CKS PROGRESSION                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CKA (Kubernetes Administrator)                            │
│  ├── Build and maintain clusters                           │
│  ├── Deploy and manage workloads                           │
│  ├── Troubleshoot failures                                 │
│  └── "Make it work"                                        │
│                                                             │
│            ↓ Foundation for ↓                              │
│                                                             │
│  CKS (Kubernetes Security Specialist)                      │
│  ├── Harden clusters against attack                        │
│  ├── Secure supply chain                                   │
│  ├── Detect and respond to threats                         │
│  └── "Make it secure"                                      │
│                                                             │
│  Key difference:                                           │
│  CKA asks "Does it run?"                                   │
│  CKS asks "Can it be compromised?"                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

That progression is why the CKA prerequisite is meaningful rather than ceremonial. Security work is mostly about narrowing choices in systems you already understand. If you cannot tell whether a ServiceAccount token is used by a Pod, whether a NetworkPolicy selector actually matches traffic, or whether a kubelet setting came from a config file or a systemd drop-in, then the security layer becomes guesswork instead of analysis.

The hardest mindset change is that CKS often treats success output as incomplete evidence. A green deployment tells you the scheduler accepted the Pod and the kubelet launched containers; it does not tell you whether the image was scanned, whether the Pod can escape into host namespaces, whether the workload has unnecessary capabilities, or whether suspicious behavior would be logged. You cannot secure what you do not understand, but once you do understand it, you must learn to distrust "it works" as the final answer.

CKS also introduces tools and operating-system concepts that Kubernetes administrators often postpone. AppArmor and seccomp shape what a process may do after it starts. Runtime detection tools inspect behavior that Kubernetes itself does not describe in a manifest. Supply chain checks ask whether an image, SBOM, signature, or static analysis result should be trusted before the workload ever reaches the API server.

Pause and predict: when a Pod fails only after you enable stricter security controls, what evidence would separate an application bug from an admission, policy, profile, or runtime enforcement problem? A strong CKA answer starts with events and logs, while a strong CKS answer also asks which security layer could have rejected the workload before or after container startup.

That difference changes how you study. You still need speed with `kubectl`, YAML, and troubleshooting, but your mental checklist expands from resource state to attack path. For every cluster object, ask what privilege it grants, what network path it opens, what host surface it touches, what credential it exposes, and what signal it leaves behind if abused.

The useful comparison is not "CKA is easy and CKS is hard." The useful comparison is that CKA mostly validates operational control, while CKS validates defensive judgment under the same time pressure. A candidate who can build clusters but cannot reason about least privilege, kernel restrictions, supply chain trust, or runtime evidence will feel the exam pulling them into unfamiliar territory.

---

## Exam Format, Rules, and Allowed Resources

The CKS exam is performance-based, delivered online, and solved on the command line. That format rewards practical fluency more than memorization because the tasks require you to change real files, inspect real cluster state, and decide which evidence matters. You should expect the same physical pressure as CKA: a remote desktop, a browser inside the exam environment, a terminal, a timer, and little room for exploratory wandering.

| Aspect | Details |
|--------|---------|
| **Duration** | 2 hours (120 minutes) |
| **Format** | Performance-based (CLI tasks) |
| **Questions** | ~17 tasks (per current LF/Killer.sh simulator; verify LF Important Instructions before booking) |
| **Passing Score** | 67% |
| **Prerequisite** | CKA certification (passed before attempting CKS) |
| **Environment** | Linux command line, Kubernetes clusters, current LF-published version |
| **Validity** | 2 years |

The table is more than trivia because every row implies a behavior. A two-hour window for roughly seventeen performance tasks means you must budget time, record skipped work, and avoid turning one hard problem into the reason you lose several easier ones. Task counts can shift when the Linux Foundation updates the simulator, so treat the Important Instructions page as the source of truth close to your exam date. A 67% passing score means partial progress matters; if you can fix the RBAC part of a question but not the audit policy part, you should still do the fix you can prove.

The prerequisite row should also shape your readiness test. The Linux Foundation states that CKS candidates must have taken and passed CKA before attempting CKS, and the CKS certification is designed for accomplished Kubernetes practitioners. That wording does not mean you must be a full-time security engineer, but it does mean the exam assumes CKA-level command speed while it evaluates security-specific tasks.

Allowed resources are a common source of wasted exam time. The CKS allowed-resource list is not identical to the CKA list, and it changes as exam tooling changes. As of the current Linux Foundation resources page, CKS candidates may use the in-VM browser for Kubernetes documentation, the Kubernetes blog, Falco documentation, Bom CLI documentation, etcd documentation, ingress-nginx configuration documentation, Cilium documentation, Istio documentation, and task-specific Quick Reference links supplied by the exam.

During the exam, you may access:

- Kubernetes Documentation: `https://kubernetes.io/docs/`
- Kubernetes Blog: `https://kubernetes.io/blog/`
- Falco documentation: `https://falco.org/docs/`
- Bom CLI reference: `https://kubernetes-sigs.github.io/bom/cli-reference/`
- etcd documentation: `https://etcd.io/docs/`
- NGINX Ingress Controller documentation: `https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/`
- Cilium documentation: `https://docs.cilium.io/en/stable/`
- Istio documentation: `https://istio.io/latest/docs/`
- Task-specific Quick Reference links provided by the exam environment

The operational lesson is simple: practice with the allowed documents, not just with search engines and personal notes. If you learn Falco rule syntax by searching the open web, then you may be fast in your normal workstation and slow in the exam browser. If you bookmark the relevant navigation paths inside allowed documentation during practice, then the exam feels less like a memory test and more like a documentation lookup under pressure.

There is also a security lesson in the allowed-resource policy. The exam is testing independent work inside a controlled environment, so outside devices, unauthorized notes, and external research are not part of the workflow. You should design your preparation around reproducible commands and official documentation paths instead of private cheat sheets that cannot come with you.

Before running your first practice lab, decide which facts you will memorize and which facts you will look up. Memorize short command shapes, common field names, and where major topics live in the docs. Look up long policy examples, tool-specific syntax, and edge-case flags because copying a correct vendor example and adapting it carefully is usually safer than reconstructing it from memory.

Make a documentation map during preparation, but keep it conceptual rather than a private cheat sheet. For each allowed site, write the topic you expect to find there and practice reaching that topic from the site's own navigation. For example, Kubernetes documentation is the natural home for Pod Security Standards, NetworkPolicies, RBAC, audit policy concepts, and workload security fields, while Falco documentation is the natural home for rule conditions, macros, lists, and event fields. This drill builds the exact navigation muscle the exam allows.

The map also protects you from stale study material. If a blog post says one tool or domain split is current, but the Linux Foundation exam page and allowed-resource page say something different, trust the official pages for exam planning. If a lab uses a tool that is not in the general allowed list, treat that as practice for the underlying security workflow unless the exam task itself provides a Quick Reference link. That discipline keeps your study plan tied to primary sources instead of rumor.

---

## Domain Weights and Study Economics

The public CKS domains are the scoring map for your study plan. They tell you where the exam spends attention and where your existing CKA habits need security-specific depth. The current Linux Foundation domain list gives three large security-heavy domains 20% each, while Cluster Setup, Cluster Hardening, and System Hardening divide the remaining score.

```text
┌─────────────────────────────────────────────────────────────┐
│              CKS DOMAIN WEIGHTS                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Cluster Setup                    ██████░░░░░░░░░░░░ 15%   │
│  Network policies, CIS benchmarks, ingress security         │
│                                                             │
│  Cluster Hardening                ██████░░░░░░░░░░░░ 15%   │
│  RBAC, ServiceAccounts, API security, upgrades              │
│                                                             │
│  System Hardening                 ████░░░░░░░░░░░░░░ 10%   │
│  AppArmor, seccomp, host OS, kernel hardening               │
│                                                             │
│  Microservice Vulnerabilities     ████████░░░░░░░░░░ 20%   │
│  Security contexts, Pod Security, secrets, sandboxing       │
│                                                             │
│  Supply Chain Security            ████████░░░░░░░░░░ 20%   │
│  Image scanning, signing, SBOM, static analysis             │
│                                                             │
│  Monitoring & Runtime Security    ████████░░░░░░░░░░ 20%   │
│  Falco, audit logs, immutable containers, incident response │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The 20% domains deserve disproportionate practice because they combine new concepts with exam pressure. Microservice Vulnerabilities asks whether you can harden Pod and workload configuration, manage secrets, apply Pod Security Standards, and reason about isolation. Supply Chain Security moves earlier in the lifecycle, where you judge image footprint, SBOMs, artifact policy, and static analysis results before the workload enters the cluster.

Monitoring, Logging, and Runtime Security completes the lifecycle by asking what happens after deployment. This domain is where audit logs, runtime detection, immutable containers, and incident investigation connect. It is also where candidates often discover that normal Kubernetes status output does not show enough; you need evidence about behavior, syscall patterns, API activity, and response workflow.

The smaller domains are still essential because they support the larger ones. Cluster Setup includes network policies, ingress TLS, CIS benchmark review, node metadata protection, endpoint protection, and platform binary verification. Cluster Hardening includes RBAC, ServiceAccounts, API access, and upgrades. System Hardening includes host surface reduction, least-privilege identity, external access minimization, and kernel hardening with AppArmor and seccomp.

The scoring economy creates a trap: candidates over-practice what feels familiar. If CKA made you comfortable with RBAC and cluster repair, you may spend too much time polishing those skills while neglecting SBOM generation, Falco rule structure, workload static analysis, or kernel profiles. Familiar domains are useful, but the CKS pass usually depends on converting unfamiliar security mechanisms into repeatable routines.

Pause and predict: if you had ten study sessions left, would you spend three of them on kubeadm cluster setup because it feels concrete, or would you reserve more time for supply chain and runtime tasks that have higher weight and less CKA overlap? The right answer depends on your gaps, but the decision must be based on domain weight and task novelty rather than comfort.

A practical study plan should therefore start with a diagnostic inventory. Mark each domain as "can solve under time," "can solve with docs," or "cannot solve yet." Then allocate the most time to high-weight domains in the last category, keep short daily reps for command speed, and use spaced review for Linux security features because AppArmor and seccomp are easy to recognize in prose and harder to debug in a live cluster.

Domain weights should not make you ignore low-percentage work. A single 10% domain can contain a task that blocks other work if you cannot interpret host-level security behavior. The point is to match effort to risk: review every domain, but invest the deepest practice where the score weight, novelty, and failure cost intersect.

---

## Tooling Map and Security Mindset

CKS tooling covers different phases of the software and cluster lifecycle. Some tools inspect artifacts before deployment, some check cluster configuration, and some detect behavior while workloads run. Treat the tool list as a map of where evidence comes from rather than a shopping list to memorize.

| Tool | Purpose | Exam Use |
|------|---------|----------|
| **Trivy** | Image vulnerability scanning | Practice finding CVEs and remediation paths when image scanning is required |
| **Falco** | Runtime threat detection | Write, modify, and reason about rules for suspicious workload behavior |
| **kube-bench** | CIS benchmark checking | Audit cluster security against benchmark controls |
| **kubesec** | Manifest static analysis | Score YAML security and identify risky workload fields |
| **AppArmor** | Application access control | Create, load, and apply profiles that constrain process behavior |
| **seccomp** | System call filtering | Restrict container syscalls through pod or runtime profiles |
| **Bom** | Software bill of materials generation | Inspect image contents and supply chain metadata when SBOM work appears |
| **Cilium / Istio** | Network and service-mesh security | Reason about encryption, identity, and policy when the task references those systems |

The exact tools available in a task can vary by exam environment and Quick Reference instructions, so avoid building your study plan on one binary alone. The deeper pattern is portable: identify the security question, choose the evidence source, run the narrowest command that answers it, then change configuration only after you know which control is missing. That pattern works whether the task names Trivy, Bom, Kubesec, KubeLinter, Falco, Cilium, Istio, or a plain Kubernetes API object.

Image and manifest analysis live before runtime. They help you decide whether a workload should be admitted to the cluster, whether the base image is unnecessarily large, whether sensitive fields are exposed, and whether an artifact has enough metadata to trust. These checks are easier to automate outside the exam, but the exam version usually asks you to interpret output and make a concrete fix.

Runtime tools answer a different class of question. A manifest can say a container should run with a read-only root filesystem, but runtime observation tells you whether a process spawned a shell, touched a sensitive path, or made a suspicious network connection. Falco is important because it turns kernel and Kubernetes events into rule matches that security teams can use during investigation.

Linux security controls are where many Kubernetes administrators feel the steepest curve. AppArmor and seccomp operate below the Kubernetes object model, yet Kubernetes exposes ways to request profiles for Pods. If a workload suddenly fails when a profile is applied, you must reason about process behavior, kernel mediation, container runtime support, and Pod events together.

```text
┌─────────────────────────────────────────────────────────────┐
│              ADMINISTRATOR vs SECURITY THINKING             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Administrator sees:          Security specialist sees:     │
│  ─────────────────────────────────────────────────────────  │
│  "Pod is running"             "Pod runs as root"            │
│  "Service is accessible"      "Service has no NetworkPolicy"│
│  "App deploys successfully"   "Image has many CVEs"         │
│  "Cluster is operational"     "API server allows anonymous" │
│  "Secrets are mounted"        "Secrets are data in etcd"    │
│                                                             │
│  Key insight:                                              │
│  Working ≠ Secure                                          │
│  Everything you built in CKA, CKS teaches you to harden    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The diagram is intentionally blunt because CKS rewards a different kind of attention. A Pod in `Running` state may still violate least privilege. A Service that routes traffic may still lack an ingress or egress boundary. A secret mounted correctly may still be too widely readable, too long-lived, or stored without the protections your organization expects.

Before running this inspection, what output do you expect from a small practice cluster that has never been intentionally hardened? Most learners predict one or two issues, but the first scan often shows several classes of gaps at once: no NetworkPolicies, namespaces without Pod Security Admission labels, Pods missing `runAsNonRoot`, and containers with unset privilege fields. That surprise is useful because it teaches you not to confuse default cluster behavior with a hardened posture.

The security mindset is not paranoia; it is structured skepticism. You ask which boundary is supposed to protect the workload, whether that boundary is actually configured, how an attacker would move if it failed, and what log would prove the movement happened. Those questions let you read ordinary Kubernetes output as security evidence.

When you practice, write down the control and the evidence separately. For example, "Pod Security Admission restricts unsafe workload fields" is the control, while "namespace label `pod-security.kubernetes.io/enforce=restricted`" is one piece of evidence. Keeping those ideas separate prevents a common mistake: seeing a label, command, or tool output and assuming the intended protection is complete.

---

## Curriculum Structure and Study Strategy

The KubeDojo CKS track follows the exam domains so your study path mirrors the scoring map. Part 0 establishes the environment and exam habits, then later parts build from cluster controls to workload hardening, supply chain security, and runtime response. This order matters because each later domain uses assumptions from earlier domains.

| Part | Domain | Weight | Modules |
|------|--------|--------|---------|
| 0 | Environment Setup | - | Exam prep, lab setup, tools |
| 1 | Cluster Setup | 15% | Network policies, CIS, ingress |
| 2 | Cluster Hardening | 15% | RBAC, ServiceAccounts, API |
| 3 | System Hardening | 10% | AppArmor, seccomp, OS |
| 4 | Microservice Vulnerabilities | 20% | Security contexts, PSA, secrets |
| 5 | Supply Chain Security | 20% | Image analysis, signing, SBOM |
| 6 | Runtime Security | 20% | Falco, audit, incidents |

Part 1 is where CKA networking knowledge becomes security enforcement. A NetworkPolicy is not just a YAML object; it is the difference between a compromised frontend reaching every database and a compromised frontend being limited to known dependencies. Ingress hardening works the same way because TLS, controller configuration, and endpoint exposure determine what the outside world can touch.

Part 2 tightens identity and API access. RBAC tasks often look familiar from CKA, but CKS asks for least privilege rather than mere functionality. The safer habit is to start from the verb, resource, namespace, and subject actually required, then add only the permission needed for the scenario.

Part 3 moves below Kubernetes objects into host and kernel controls. AppArmor and seccomp can feel unrelated to Kubernetes until you see a Pod request a profile and then fail because the process attempted a blocked action. This part teaches you to connect workload behavior, runtime configuration, and operating-system policy.

Part 4 focuses on microservice vulnerabilities inside the workload boundary. Security contexts, Pod Security Standards, secrets, sandboxing, and isolation techniques all shape what a compromised process can do next. The exam value here is not naming the field; it is choosing the field that reduces a realistic path of abuse without breaking the application unnecessarily.

Part 5 shifts left into supply chain security. You evaluate base images, artifact provenance, SBOMs, allowed registries, signatures, and static analysis findings. This domain is high weight because many production compromises begin before Kubernetes ever schedules a Pod, and the cluster can only enforce what the delivery pipeline made visible.

Part 6 closes the loop with monitoring, logging, and runtime security. Audit policies, Falco rules, container immutability, and incident response turn security from a pre-deployment checklist into an operating practice. In this part, a correct answer often combines detection, evidence collection, and a mitigation step.

The three-pass strategy below is a time-management model, not a rigid exam script. It helps you avoid spending too long on one complex task while easier scoring opportunities remain open. Use it during practice so the habit is automatic before the real timer starts.

```text
┌─────────────────────────────────────────────────────────────┐
│              CKS THREE-PASS STRATEGY                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PASS 1: Quick Security Wins (1-3 min each)                │
│  ├── Create NetworkPolicy                                  │
│  ├── Apply existing AppArmor profile                       │
│  ├── Fix obvious RBAC issue                                │
│  └── Set runAsNonRoot: true                                │
│                                                             │
│  PASS 2: Tool-Based Tasks (4-6 min each)                   │
│  ├── Scan image with Trivy, fix vulnerabilities            │
│  ├── Create seccomp profile                                │
│  ├── Configure Pod Security Admission                       │
│  ├── Run kube-bench, fix findings                          │
│  └── Configure audit policy (when task supplies manifest)  │
│                                                             │
│  PASS 3: Complex Scenarios (7+ min each)                   │
│  ├── Write custom Falco rule                               │
│  ├── Investigate runtime incident                          │
│  ├── Multi-step hardening task                             │
│  └── Complex NetworkPolicy scenarios                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The first pass should capture tasks whose success criteria are visible and narrow. A simple NetworkPolicy, a missing security context field, an obvious RoleBinding correction, or a namespace label can often be solved quickly if you have practiced the YAML shapes. These tasks are valuable because they build score and confidence without consuming the middle of the exam.

The second pass is for tasks where a tool or documentation lookup is expected. You may need to run a scanner, read output, adjust a manifest, or adapt a vendor example. The danger here is over-reading: once the output identifies the finding the task cares about, make the targeted change and move on instead of chasing every warning.

The third pass is for multi-step work that requires synthesis. A runtime investigation might ask you to interpret a rule, identify a process, preserve evidence, and apply a mitigation. A complex NetworkPolicy might require understanding labels, namespace selectors, DNS egress, and application dependencies. These are high-value tasks, but they can absorb too much time if attempted before easier work.

Which approach would you choose here and why: a strict first-to-last exam flow, or a pass-based flow that intentionally skips unresolved tasks and returns later? The pass-based flow is usually safer for CKS because the exam mixes short control fixes with deeper investigations, and your score should not depend on the first hard scenario appearing early.

Build your personal plan around feedback loops. After each practice session, record which domain the task belonged to, whether you solved it without docs, which command or document path slowed you down, and what kind of mistake occurred. Over a few sessions, that record becomes more useful than a generic study checklist because it shows your actual failure pattern.

---

## Worked Example: Turning One Running Pod into a Security Finding

Exercise scenario: a namespace contains a web workload that is healthy from an operations perspective. The Deployment has the desired replicas, the Pods are in `Running`, the Service has endpoints, and an HTTP check returns success. A CKA-style review would probably move on after confirming logs, events, readiness, and routing. A CKS-style review keeps going because the security question is not whether the workload serves traffic, but what the workload could do after compromise.

Start with identity because identity defines what the workload can ask the API server to do. If the Pod uses the default ServiceAccount, the finding is not automatically severe, but it is a prompt to inspect whether the namespace has default token behavior, whether any RoleBinding grants broad verbs to that account, and whether the workload actually needs API access. The study action is to practice reading ServiceAccount, Role, RoleBinding, ClusterRole, and ClusterRoleBinding objects as one privilege story instead of isolated YAML fragments.

Next inspect process privilege. A Pod that omits `runAsNonRoot`, allows privilege escalation, uses default capabilities, or mounts a writable root filesystem may still run without errors. The finding is that the manifest leaves too much behavior to image defaults and container runtime defaults. Your study action is to build a small matrix of security context fields, then deploy intentionally violating Pods so you can recognize the difference between admission rejection, container startup failure, and application-level failure.

Now inspect network reachability. If the namespace has no NetworkPolicy, the Pod may initiate or receive traffic more broadly than the application requires, depending on the CNI and any external controls. The correct CKS question is not "does a policy object exist somewhere in the cluster" but "does a selected policy constrain this Pod's required ingress and egress paths." Your study action is to practice label matching and DNS egress because policies that block name resolution often look like application failures until you connect the symptom to the control.

Then inspect data exposure. A workload can mount a secret correctly and still expose too much if the secret contains broad credentials, is mounted into unnecessary containers, or is readable by a ServiceAccount that too many subjects can use. CKS does not turn you into a secrets-management product specialist, but it does expect you to notice whether Kubernetes secret usage expands blast radius. Your study action is to trace which Pod consumes the secret, which account can read it, and whether the manifest could reduce the exposure.

Supply chain evidence comes before you trust the image. If the image uses a large base, lacks useful metadata, carries known vulnerabilities, or arrives without an SBOM when the task asks for one, the running state proves very little. Your study action is to practice extracting the image reference, running the specified scanner or SBOM tool from the lab instructions, and separating task-relevant findings from noise. In a timed exam, you rarely need to fix every possible issue; you need to fix the issue the scenario asks you to evaluate.

Runtime evidence completes the picture because some risks appear only after the process starts. A shell spawned inside a container, writes to an unexpected path, or calls a sensitive syscall may not change the Kubernetes status at all. Your study action is to practice reading Falco-style rule conditions and mapping an alert back to a namespace, Pod, container, process, and command. That mapping turns a detection event into an investigation path rather than a scary line of output.

The worked example produces a compact decision record. Identity asks what the workload can request, process privilege asks what it can do locally, network policy asks where it can move, data exposure asks what it can read, supply chain checks ask whether the artifact should run, and runtime evidence asks what it actually did. Those six lenses give you a practical way to convert one healthy Pod into a set of CKS study tasks without inventing a production incident.

If you repeat this example across several workloads, you will notice which lens you skip under time pressure. Some candidates forget identity because RBAC feels familiar; others forget runtime evidence because the workload looks quiet; others over-focus on scanners because tool output feels concrete. The value of the exercise is that it reveals your blind spot before the exam does.

---

## Patterns & Anti-Patterns

For an orientation module like this one, the most useful pattern is to connect every study activity to a concrete security decision. Reading about Pod Security Standards is helpful, but applying a namespace label, deploying a violating Pod, reading the rejection, and then fixing the manifest creates exam-ready memory. The same pattern works for Falco, SBOMs, RBAC, NetworkPolicies, and kernel profiles.

Another reliable pattern is to keep a narrow evidence ladder for each domain. Start with the Kubernetes object, then check the controller or tool output, then inspect host or runtime evidence only when the task points there. This prevents random command wandering while still reminding you that not all security state is visible from one API response.

Use failure as a practice tool. Intentionally deploy a Pod that violates a restricted Pod Security profile, apply a NetworkPolicy that blocks DNS, write a Falco rule with a bad condition, or configure a seccomp profile that denies a needed syscall. Breaking the control in a lab teaches you what the error looks like, which is exactly the recognition skill the exam rewards.

The first anti-pattern is treating CKS as vocabulary acquisition. Memorizing that seccomp filters syscalls or that Falco detects runtime behavior does not help much unless you can apply, inspect, and repair those controls. CKS tasks are practical, so your study artifacts should be commands, manifests, rule edits, and observed outcomes.

The second anti-pattern is assuming a secure setting is harmless because the application still starts. A container that runs as non-root is better than one that runs as root, but it may still have unnecessary capabilities, writable filesystems, broad egress, and a powerful ServiceAccount. Security is layered, and CKS often tests whether you can identify the missing layer rather than celebrate the layer already present.

The third anti-pattern is over-trusting tool output. A scanner finding, benchmark result, or rule match is evidence, not judgment. You still need to decide whether the finding is in scope for the task, whether the recommended fix is safe for the workload, and whether the change actually satisfies the question. In practice, run the tool, isolate the relevant finding, make the smallest defensible fix, and verify the specific outcome.

When this module does not apply is also worth naming. If you are preparing for KCSA, you need broader conceptual security coverage and less hands-on command speed. If you are preparing for CKA, you need deeper cluster operations practice before security specialization. If you are building a production security program, CKS is a useful baseline, but it is not a substitute for threat modeling, organizational policy, incident response drills, and continuous controls.

---

## When You'd Use This vs Alternatives

Use CKS preparation when your goal is to prove hands-on Kubernetes security competence under vendor-neutral exam constraints. It is especially relevant when you already administer clusters and want a structured path through workload hardening, supply chain controls, runtime detection, and incident investigation. The credential is narrow enough to be practical and broad enough to force you beyond one vendor's managed-service defaults.

Use KCSA preparation when you need security literacy without assuming CKA-level administration. KCSA is a better fit for architects, managers, early-career engineers, and platform-adjacent contributors who need to understand cloud native security concepts but are not yet expected to solve cluster tasks under a terminal timer. It can also be a stepping stone before CKA and CKS.

Use CKA reinforcement when your Kubernetes operations are not yet automatic. If YAML editing, context switching, RBAC inspection, service troubleshooting, or node-level debugging still feel slow, then CKS will amplify that friction. Security tasks stack on top of operational tasks, so weak administration fundamentals become expensive during the exam.

Use vendor-specific security certifications when your daily work depends on a particular cloud provider or commercial platform. Those certifications may cover IAM integration, managed control planes, proprietary scanning, logging pipelines, or policy engines in more depth than CKS. They do not replace CKS because CKS tests portable Kubernetes security mechanisms, but they can complement it for production roles.

Use internal production drills when your objective is organizational readiness rather than exam performance. A real security program needs ownership, alert routing, change review, exception handling, and incident communications. CKS can teach the technical controls, but production readiness requires the social and operational machinery around those controls.

The decision rule is therefore straightforward: choose the path that matches the job you need to perform next. If you need to secure Kubernetes resources at the command line, CKS is the right target. If you need foundational vocabulary, choose KCSA. If you need cluster repair speed, choose CKA practice. If you need cloud-specific implementation detail, add the relevant vendor track after the portable Kubernetes model is strong.

---

## Did You Know?

- **CKS was announced as generally available on November 17, 2020.** The [CNCF GA announcement](https://www.cncf.io/announcements/2020/11/17/kubernetes-security-specialist-certification-now-available/) describes the launch as a performance-based exam for securing container workloads and Kubernetes platforms across build, deployment, and runtime.

- **The CKS passing score is 67%, and the certification is valid for 2 years.** That combination means the exam expects practical competence, but it also expects candidates to refresh because Kubernetes security tooling and exam environments change over time.

- **Three CKS domains account for 60% of the score.** Minimize Microservice Vulnerabilities, Supply Chain Security, and Monitoring, Logging, and Runtime Security each carry 20%, which is why study time should not be spread evenly across every topic.

- **Supply chain security became critical** as a heavily tested CKS domain. The track covers two canonical incidents in depth: a [build-system compromise that pushed signed-but-malicious updates to thousands of downstream customers](/prerequisites/modern-devops/module-1.3-cicd-pipelines/) <!-- incident-xref: solarwinds-2020 --> and a [transitive Java logging library vulnerability that exposed any application accepting attacker-controlled input strings](/platform/disciplines/reliability-security/devsecops/module-4.4-supply-chain-security/) <!-- incident-xref: log4shell -->.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Studying only Kubernetes API objects | CKA habits make RBAC, NetworkPolicy, and Pods feel like the whole exam | Add deliberate reps for AppArmor, seccomp, SBOMs, runtime rules, and audit evidence |
| Treating domain weights as trivia | Candidates read the percentages once but still study whatever feels easiest | Allocate practice time by weight, novelty, and recent failure history |
| Ignoring the official allowed-resource list | Search-engine practice hides how constrained the exam browser is | Practice navigation inside the exact allowed documentation domains |
| Memorizing tool names without workflows | Tool recognition feels like progress until a task requires interpretation | Run each tool against a broken example, explain the relevant finding, and verify the fix |
| Assuming `Running` means safe | Operational success is visible, while privilege and network exposure are quieter | Inspect security contexts, ServiceAccounts, policies, secrets, and runtime evidence separately |
| Leaving Linux hardening until the end | AppArmor and seccomp feel smaller because System Hardening is lower weight | Schedule spaced practice because kernel-profile errors take time to recognize |
| Spending too long on one complex scenario | Security investigations can expand into many possible paths | Use a three-pass strategy and return to complex work after collecting quick points |

---

## Quiz

<details>
<summary>1. Your colleague passed CKA several years ago and wants to register for CKS now. They plan to study only RBAC and NetworkPolicies because those were their strongest CKA topics. How would you evaluate their readiness?</summary>

They satisfy the CKS prerequisite if they have taken and passed CKA before attempting CKS, but their study plan is not ready for the exam. RBAC and NetworkPolicies matter, yet they cover only part of Cluster Hardening and Cluster Setup. They also need hands-on work with workload hardening, supply chain analysis, runtime detection, audit evidence, and Linux security controls. A better readiness judgment compares their skills against every CKS domain and gives extra time to high-weight areas with less CKA overlap.

</details>

<details>
<summary>2. During practice, you solve every cluster setup task quickly but repeatedly fail SBOM and runtime detection tasks. The exam domain map gives several areas different weights. How should you redesign the study plan?</summary>

You should shift more time toward Supply Chain Security and Monitoring, Logging, and Runtime Security because each is a high-weight domain and your practice evidence shows weakness there. Cluster setup still needs maintenance reps, but extra time there has lower return if you already solve those tasks under pressure. The redesigned plan should include tool-output interpretation, vendor documentation navigation, and broken-lab scenarios for SBOM and runtime evidence. Keep a short review loop for familiar domains so speed does not decay.

</details>

<details>
<summary>3. A Pod reaches `Running`, its Service routes traffic, and application logs are clean. A CKS-style review still rejects the deployment. What security evidence would you inspect before disagreeing?</summary>

You should inspect the Pod security context, container security context, ServiceAccount, mounted secrets, namespace Pod Security Admission labels, and NetworkPolicies before treating the deployment as acceptable. A running Pod can still run as root, hold excessive capabilities, use a powerful token, accept broad network traffic, or mount sensitive data. You should also consider image and runtime evidence if the task points to supply chain or detection concerns. The CKS mindset is that availability is only one property, not proof of secure configuration.

</details>

<details>
<summary>4. In the exam browser, you search Kubernetes documentation for Falco rule syntax and cannot find the macro example you need. What rule about allowed resources did you misunderstand?</summary>

You misunderstood that CKS has a specific allowed-resource list beyond the core Kubernetes documentation. Falco documentation is a separate allowed domain for CKS, so the correct recovery is to navigate directly to the official Falco docs from inside the exam environment. The broader lesson is to practice with the allowed documentation set before the exam. If you rely on open web search during preparation, you may not know where official vendor examples live when the exam browser is constrained.

</details>

<details>
<summary>5. Your first practice scan shows no NetworkPolicies, unset `runAsNonRoot` fields, and namespaces without Pod Security Admission labels. Why is this a useful diagnostic rather than just a list of failures?</summary>

It shows which security controls are absent from the current cluster posture and gives you a study map tied to real evidence. No NetworkPolicies suggest unrestricted pod-to-pod communication unless the CNI enforces other controls. Unset `runAsNonRoot` and missing Pod Security labels point to workload-hardening gaps that the CKS microservice domain tests heavily. Treating the scan as a diagnostic helps you convert observations into prioritized practice tasks.

</details>

<details>
<summary>6. You are halfway through a timed mock exam and a runtime investigation has consumed too much time. Several short hardening tasks remain unanswered. What should your exam strategy be?</summary>

You should mark the complex runtime investigation, capture any partial evidence or easy mitigation you already know, and move to the shorter tasks. The three-pass strategy exists because CKS mixes quick configuration fixes with deeper investigations. Finishing several narrow tasks can produce more reliable score than over-investing in one uncertain scenario. Return to the complex task after collecting the easier points.

</details>

<details>
<summary>7. A candidate says they will memorize every command instead of practicing documentation navigation because documentation lookup is slow. Why is that risky for CKS?</summary>

It is risky because CKS includes tool-specific and security-specific tasks where exact syntax, examples, and supported fields matter. Memorization helps with common command shapes, but vendor docs are safer for detailed Falco rules, SBOM commands, policy examples, and edge-case configuration. The exam allows specific official resources because practical engineers are expected to use documentation well. A balanced strategy memorizes high-frequency patterns and practices fast lookup for details.

</details>

---

## Hands-On Exercise

Exercise scenario: use a Kubernetes 1.35+ practice cluster or lab environment to perform a first-pass security posture inspection. The goal is not to fully harden the cluster in this module; it is to learn how ordinary `kubectl` output becomes CKS evidence. If you do not have a cluster ready yet, read the commands now and run them after the lab setup module.

Complete these tasks in order and write down the evidence you find. Each task builds from simple discovery toward a security judgment, so avoid fixing anything until you can explain what the current state means. That habit matters in CKS because premature changes can hide the exact evidence a task wanted you to inspect.

- [ ] Identify whether the control plane exposes admission or audit configuration evidence.
- [ ] Count NetworkPolicies across all namespaces and decide whether the cluster has a default network boundary.
- [ ] Inspect workload-level `runAsNonRoot` settings and note namespaces where the field is unset.
- [ ] Find privileged containers, if any, and record the namespace, Pod, and container context you would inspect next.
- [ ] Review Pod Security Admission labels and decide which namespaces would reject restricted-policy violations.

```bash
# Step 1: Check if your cluster has basic security features
echo "=== Checking API Server Security ==="
kubectl get pods -n kube-system | grep apiserver
kubectl get pods -n kube-system -l component=kube-apiserver -o yaml 2>/dev/null | grep -E "enable-admission|audit" | head -5 || echo "Check on control plane node"

# Step 2: Check for NetworkPolicies (most clusters have none by default)
echo "=== NetworkPolicy Count ==="
kubectl get networkpolicies -A
NETPOL_COUNT=$(kubectl get networkpolicies -A --no-headers 2>/dev/null | wc -l)
echo "Total NetworkPolicies: $NETPOL_COUNT"
if [ "$NETPOL_COUNT" -eq 0 ]; then
  echo "No NetworkPolicies found. Pods may communicate freely unless another control enforces policy."
fi

# Step 3: Check Pod-level runAsNonRoot (container-level fields are covered in later modules)
echo "=== Pods Running as Root ==="
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}: runAsNonRoot={.spec.securityContext.runAsNonRoot}{"\n"}{end}' | head -10

# Step 4: List privileged containers with namespace/Pod/container context (positives only)
echo "=== Privileged Containers ==="
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}/{range .spec.containers[*]}{.name}: privileged={.securityContext.privileged}{"\n"}{end}{end}' | grep 'privileged=true'

# Step 5: Check Pod Security Admission labels
echo "=== Pod Security Standards ==="
kubectl get namespaces -o jsonpath='{range .items[*]}{.metadata.name}: {.metadata.labels.pod-security\.kubernetes\.io/enforce}{"\n"}{end}' | grep -v ": $"

# Step 6: Identify security improvements needed
echo ""
echo "=== Security Gaps Identified ==="
echo "Review the output above. Common gaps include:"
echo "- No NetworkPolicies (pods can talk to anything)"
echo "- Pods running as root"
echo "- No Pod Security Standards enforced"
echo "- Missing audit logging"
```

The API server check is intentionally conservative because managed clusters and local labs expose control-plane details differently. If the command cannot read static Pod manifests through the API, that does not prove admission or audit logging is absent. It means the next evidence source may be the control-plane node, the managed-service configuration interface, or the lab instructions.

The NetworkPolicy count is a starting point, not a complete policy audit. A cluster with zero policies usually has no Kubernetes-native pod traffic boundary, but a cluster with several policies can still allow too much traffic if selectors are broad or egress is missing. In later modules, you will move from counting policies to proving which flows are allowed.

The `runAsNonRoot` query checks the Pod-level security context, which is only one place the setting can appear. Container-level security context may override or complement Pod-level settings, and Pod Security Admission may enforce restrictions even when a manifest omits explicit fields. The point of this first pass is to notice unset posture, then learn the deeper rules in workload-hardening modules.

The privileged-container query prints `namespace/pod/container: privileged=true` lines only, so you can record the exact context a CKS task would ask you to inspect next. If output appears, inspect the full Pod manifest and determine whether host namespaces, host paths, capabilities, or ServiceAccount permissions make the risk worse. If output is empty, you still need other controls, because "not privileged" is not the same as "least privilege."

The Pod Security Admission label check tells you whether namespaces advertise an enforcement level such as `baseline` or `restricted`. Missing labels are common in practice clusters, and they give you a concrete improvement path for later modules. The labels are also a reminder that CKS often tests namespace-level policy and workload-level fields together.

<details>
<summary>Solution guidance for tasks 1-2</summary>

For the API server task, record whether you saw admission or audit-related flags and where the evidence came from. For the NetworkPolicy task, record the count and at least one namespace that has no visible policy. A defensible answer distinguishes "I did not have access to that evidence through the API" from "the control is definitely absent."

</details>

<details>
<summary>Solution guidance for tasks 3-5</summary>

For `runAsNonRoot`, privileged containers, and Pod Security Admission labels, write down the exact field that was unset or configured. If the output is empty, note what the command actually checked and what it did not check. This prevents false confidence and prepares you for later modules where you will inspect container-level fields, namespace labels, and admission behavior together.

</details>

Success criteria:

- [ ] You can compare CKA-style operational evidence with CKS-style security evidence from the same cluster.
- [ ] You can evaluate whether your practice cluster has visible gaps in network policy, workload identity, and Pod Security Admission.
- [ ] You can design the next three study actions based on the highest-risk gaps you observed.
- [ ] You can diagnose at least one place where a successful workload state does not prove secure workload posture.
- [ ] You can implement the three-pass exam strategy by labeling each finding as a quick win, tool-based task, or complex scenario.

---

## Learner check

> A two-hour window for roughly seventeen performance tasks means you must budget time, record skipped work, and avoid turning one hard problem into the reason you lose several easier ones. Task counts can shift when the Linux Foundation updates the simulator, so treat the Important Instructions page as the source of truth close to your exam date.

## Sources

- https://www.cncf.io/announcements/2020/11/17/kubernetes-security-specialist-certification-now-available/
- https://training.linuxfoundation.org/certification/certified-kubernetes-security-specialist/
- https://docs.linuxfoundation.org/tc-docs/certification/faq-cka-ckad-cks
- https://docs.linuxfoundation.org/tc-docs/certification/important-instructions-cks
- https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed
- https://kubernetes.io/docs/
- https://kubernetes.io/blog/
- https://kubernetes.io/docs/concepts/security/pod-security-standards/
- https://kubernetes.io/docs/concepts/services-networking/network-policies/
- https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- https://falco.org/docs/
- https://kubernetes-sigs.github.io/bom/cli-reference/
- https://etcd.io/docs/
- https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/
- https://docs.cilium.io/en/stable/
- https://istio.io/latest/docs/
- https://trivy.dev/latest/docs/
- https://github.com/kubernetes/kubernetes

## Next Module

[Module 0.2: Security Lab Setup](../module-0.2-security-lab/) - Build your CKS practice environment with the security tools and cluster access patterns this overview references.
