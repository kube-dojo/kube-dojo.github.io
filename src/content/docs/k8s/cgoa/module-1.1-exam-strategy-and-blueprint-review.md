---
citations_verified: true
title: "CGOA Exam Strategy and Blueprint Review"
slug: k8s/cgoa/module-1.1-exam-strategy-and-blueprint-review
revision_pending: false
sidebar:
  order: 101
---

> **CGOA Track** | **Complexity**: `[MEDIUM]` | **Time to Complete**: 90 minutes | **Prerequisites**: No Kubernetes operations experience required, but basic Git and CI/CD vocabulary will help

## Learning Outcomes

- **Evaluate CGOA scenario questions** by identifying the blueprint domain, the GitOps principle being tested, and the answer choice that preserves the operating model.
- **Compare GitOps with CI/CD, Infrastructure as Code, and configuration automation** without collapsing those practices into one vague "automation" bucket.
- **Design a blueprint-weighted study plan** that gives more practice time to higher-weight areas while still covering tooling, patterns, and related practices with the right depth.
- **Analyze multiple-choice distractors** by tracing whether each option keeps Git as the source of truth, uses automated pull-based reconciliation, and maintains a feedback loop.
- **Build and validate a personal exam strategy** using scenario classification, answer elimination, and a timed practice review process.

## Why This Module Matters

A platform engineer named Priya has used ArgoCD for a year, reviewed Helm charts, and watched production drift alerts. She opens a CGOA practice exam expecting tool trivia, then misses questions that ask whether a change belongs in CI, Git, the GitOps controller, or the runtime cluster. Her practical experience is real, but the exam rewards the ability to name the operating model behind the tool instead of simply remembering what a tool can do.

That gap matters because [CGOA is a theory exam about GitOps as a discipline](https://www.cncf.io/training/certification/cgoa/). The exam is not trying to prove that you know every ArgoCD screen, Flux command, or Helm template function. It is testing whether you can recognize a healthy GitOps design, reject designs that quietly reintroduce manual deployment, and explain why declarative desired state plus reconciliation changes how teams operate.

This module turns the blueprint into a decision system. You will learn how the domains fit together, how to read questions for intent, how to separate close answer choices, and how to practice in a way that improves judgment instead of only increasing flashcard volume. The senior-level goal is not "memorize the five domains"; the senior-level goal is "diagnose what the question is really measuring, then choose the answer that keeps the system governable."

## Core Content

### 1. Read The Blueprint As A Map Of Judgment

The CGOA blueprint is a signal about where the exam expects judgment. [Higher-weight domains deserve more time](https://www.cncf.io/training/certification/cgoa/), but they also deserve deeper practice because they anchor many questions in the smaller domains. If a tooling question asks about Flux or ArgoCD, the best answer often depends on a principle such as versioned desired state, pull-based reconciliation, or the difference between build automation and deployment reconciliation.

| Domain | Weight | What it is really testing | How to study it |
|---|---:|---|---|
| GitOps Terminology | 20% | Whether you can interpret desired state, drift, reconciliation, state store, and feedback loop in scenario wording | Build a working vocabulary by explaining each term through a small incident |
| GitOps Principles | 30% | Whether you can evaluate a workflow against OpenGitOps ideas instead of tool preference | Practice eliminating answers that break declarative, versioned, pulled, or reconciled behavior |
| Related Practices | 16% | Whether you can compare GitOps with IaC, CaC, DevOps, DevSecOps, CI, CD, and progressive delivery | Use contrast tables and ask which system owns which decision |
| GitOps Patterns | 20% | Whether you can reason about promotion, rollback, environments, multi-cluster layout, and drift handling | Work through sequence-based scenarios and identify the source of truth |
| Tooling | 14% | Whether you can place ArgoCD, Flux, Helm, Kustomize, and policy tools into the model | Learn tool roles and trade-offs, but keep principles ahead of product names |

The most common mistake is to treat the percentages as separate study boxes. In practice, the domains nest inside one another. Terminology gives you the nouns, principles give you the control loop, related practices define boundaries, patterns show the operating choices, and tooling gives examples of implementations. When a question feels ambiguous, ask which layer the question is really testing before you compare answer choices.

```ascii
+--------------------------- CGOA QUESTION ---------------------------+
|                                                                      |
|  Scenario wording                                                     |
|        |                                                             |
|        v                                                             |
|  +------------------+       +------------------+                     |
|  | Domain signal    | ----> | Principle signal |                     |
|  | terminology?     |       | source of truth? |                     |
|  | patterns?        |       | reconciliation?  |                     |
|  | tooling?         |       | feedback loop?   |                     |
|  +------------------+       +------------------+                     |
|        |                                                             |
|        v                                                             |
|  +------------------+       +------------------+                     |
|  | Distractor check | ----> | Final answer     |                     |
|  | push deploy?     |       | best preserves   |                     |
|  | manual drift?    |       | GitOps model     |                     |
|  | tool trivia?     |       | in the scenario  |                     |
|  +------------------+       +------------------+                     |
|                                                                      |
+----------------------------------------------------------------------+
```

A useful mental model is to think of each CGOA question as a small architecture review. The question describes a team, a workflow, a failure, or a proposed improvement. Your job is to recommend the choice that keeps desired state declared, stored, reviewed, versioned, automatically applied, and continuously compared with runtime state. That is why pure memorization feels brittle: the answer often depends on how the pieces interact.

**Stop and think:** A question says, "A team wants the CI server to apply manifests directly to production after tests pass." Which blueprint domain is being tested first, and which GitOps principle is most likely at risk? Do not answer from tool preference. Answer by naming the domain, then the principle, then the operational consequence.

The answer is not merely "CI/CD is bad" because CI/CD is not bad. The issue is ownership of deployment reconciliation. CI can build, test, scan, package, and propose a desired-state change, but the GitOps model expects the cluster-side reconciliation mechanism to pull the approved desired state from the state store. When CI pushes directly into production, Git stops being the operational source of truth and drift becomes harder to reason about.

### 2. Learn GitOps Terms As Operational Signals

GitOps terminology matters because exam wording compresses a lot of meaning into a few repeated phrases. Desired state is not simply "configuration files in a repo"; it is the declared target that a controller can compare against observed runtime state. Drift is not every runtime difference; it is a meaningful difference between managed desired state and actual state. Reconciliation is not a one-time deployment; it is repeated comparison and correction.

| Term | Exam-safe meaning | What a distractor may imply | Better reasoning habit |
|---|---|---|---|
| Desired state | The declared target state stored in a versioned source of truth | Any local script, ticket, or human memory can define the target | Ask where the target state lives and whether it can be reviewed |
| Actual state | The currently observed runtime condition of the system | Runtime state always matches Git immediately | Ask what the controller sees and whether it is converged |
| Drift | A difference between intended managed state and observed state | Every dynamic runtime change is drift | Ask whether the field should be controlled declaratively |
| Reconciliation | Automated repeated movement from actual state toward desired state | A manual deploy command is equivalent to reconciliation | Ask what component performs comparison and correction |
| State store | The authoritative versioned place for desired state, commonly Git | Any dashboard or cluster object can become the source of truth | Ask where rollback, audit, and review would happen |
| Feedback loop | Status information that reports convergence, health, and mismatch | Applying manifests is enough without observing results | Ask how the team knows whether desired state took effect |
| Rollback | Returning desired state to a previous reviewed version and reconciling | Manually editing production is the cleanest rollback | Ask whether rollback preserves auditability and repeatability |

The exam often tests terms by placing them inside a story instead of asking for definitions. For example, a team may hotfix a Deployment with a direct `kubectl edit` and then notice the value returns to the Git version. The surface detail is a command, but the tested concept is reconciliation correcting drift. If you only memorize a definition, you may miss the mechanism; if you understand the mechanism, the command detail becomes less distracting.

Terminology also protects you from overgeneralizing. "State" appears in many systems, but GitOps cares about desired state as a declarative target and actual state as observed runtime condition. A database table with changing user data is state, but it is not normally the same kind of declarative platform state that GitOps reconciles. Good exam answers keep that boundary clear instead of claiming Git should store every byte that changes in a system.

A senior practitioner reads vocabulary through consequences. If Git is the state store, then review, audit, rollback, and promotion are Git-centered. If a controller reconciles, then manual changes are temporary unless they are committed back to desired state. If feedback is required, then a pipeline that "fires and forgets" is incomplete. The vocabulary is not academic; it predicts how the system behaves under failure.

**Stop and think:** Your team sees a running Pod with a different image tag than the Deployment manifest in Git. Before deciding that this is drift, what should you verify? Consider whether the manifest is the managed desired state, whether another controller owns the field, and whether the GitOps controller has reported sync or health status.

A careful answer verifies ownership and timing. If the Deployment is managed by the GitOps controller and the image tag differs after reconciliation should have completed, the mismatch is drift or a failed reconciliation symptom. If the field is intentionally mutated by another controller, or if a new commit has not yet reconciled, the diagnosis changes. CGOA questions reward that kind of conditional thinking.

### 3. Treat The Four Principles As One Control Loop

[The four OpenGitOps principles](https://github.com/open-gitops/documents/blob/main/PRINCIPLES.md) are easiest to remember as a loop rather than a slogan. The system starts with a declarative description of desired state. That description is versioned and immutable, so change history is reviewable and recoverable. Software agents automatically pull the desired state into the runtime environment. The agents continuously reconcile actual state to desired state and report feedback.

```ascii
+----------------------+       +----------------------+       +----------------------+
| Declarative desired  | ----> | Versioned immutable | ----> | Pulled automatically |
| state describes what |       | history makes change|       | by a software agent  |
| should exist         |       | reviewable          |       | from the state store |
+----------------------+       +----------------------+       +----------------------+
          ^                                                                  |
          |                                                                  v
          |                                                        +----------------------+
          |                                                        | Continuously         |
          +--------------------------------------------------------| reconciled with      |
                                                                   | feedback and drift   |
                                                                   +----------------------+
```

The loop matters because many wrong answers preserve one principle while breaking another. An answer may use declarative YAML but apply it manually from a laptop. Another answer may use Git history but allow the cluster dashboard to become the authoritative source after deployment. A third answer may run automation but only as a push from CI without continuous observation. On the exam, the best answer usually keeps the whole loop intact.

Worked example: A team stores Kubernetes manifests in Git and has a CI job run `kubectl apply` after each merge. The manifests are declarative and versioned, so two principles are partly present. However, the deployment path is push-based and may not continuously reconcile cluster state after the job exits. A stronger GitOps answer would have CI build and test artifacts, commit or update desired state, and let an in-cluster or cluster-connected controller pull and reconcile from Git.

This worked example shows why CGOA questions are rarely won by spotting one keyword. If the answer says "Git" but removes pull-based reconciliation, it is not the best GitOps answer. If the answer says "automation" but provides no feedback loop, it is incomplete. If the answer says "manual approval" but makes the manual step update the reviewed desired state before reconciliation, it may still fit GitOps depending on the scenario.

The control loop also explains why GitOps improves recovery. A team can recover from accidental cluster changes because the reconciler compares actual state with desired state and moves the system back toward the declared target. A team can recover from a bad desired-state change by reverting or correcting the versioned state and letting reconciliation apply the new target. Both forms of recovery depend on keeping the source of truth clean.

When you evaluate answer choices, trace the loop in order. Ask whether the target is declarative, whether the target is versioned and reviewable, whether an agent pulls the target, and whether actual state is continuously compared with the target. If an answer breaks the loop, it needs a strong reason to remain plausible. Most exam distractors break the loop quietly.

### 4. Separate GitOps From Neighboring Practices

CGOA expects you to understand GitOps in context, not in isolation. Infrastructure as Code, Configuration as Code, DevOps, CI, CD, progressive delivery, and policy automation often appear in the same operating environment. They are related because they help teams manage change safely, but they do not all own the same step in the delivery system.

| Practice | Primary question it answers | How it relates to GitOps | Common exam trap |
|---|---|---|---|
| Infrastructure as Code | How do we declare infrastructure resources repeatably? | IaC can provide desired-state files that GitOps reconciles or provisions around | Assuming all IaC is automatically GitOps |
| Configuration as Code | How do we store configuration in reviewed, versioned files? | CaC supports GitOps by making configuration declarative and auditable | Treating stored config as sufficient without reconciliation |
| CI | How do we build, test, scan, and package changes? | CI can validate artifacts and update desired state through reviewed changes | Letting CI become the production deploy authority |
| CD | How do changes reach environments reliably? | GitOps can be a CD operating model for deployment reconciliation | Equating every deployment pipeline with GitOps |
| DevOps | How do teams improve flow, feedback, and shared ownership? | GitOps supports DevOps goals with auditable automated operations | Treating DevOps as a specific tool or command sequence |
| DevSecOps | How do security controls run on the delivery path? | DevSecOps embeds shift-left scanning and policy in the pipeline; GitOps governs how versioned desired state is pulled and reconciled by agents | Treating security scanning alone as GitOps reconciliation |
| Progressive delivery | How do we reduce risk during rollout? | GitOps can manage desired rollout configuration for canary or blue-green patterns | Assuming rollout strategy replaces source-of-truth discipline |
| Policy as Code | How do we define and enforce rules automatically? | Policy can validate desired state before or during reconciliation | Assuming policy checks alone provide deployment reconciliation |

DevSecOps is orthogonal to GitOps in the same way CI is: it governs what security gates run on the way to production (shift-left scanning, policy checks, supply-chain controls), while GitOps governs how reviewed desired state reaches the cluster through pull-based reconciliation. A pipeline can be strong on DevSecOps and still weak on GitOps if CI pushes manifests directly after scans pass.

The boundary between CI and GitOps is especially important. CI is excellent at producing evidence that a change is safe enough to propose: tests passed, images were built, vulnerabilities were scanned, and manifests were rendered. GitOps is concerned with the reviewed desired state and the reconciliation of that desired state into runtime environments. The practices cooperate, but the exam will punish answers that collapse them into one push pipeline.

Infrastructure as Code has a similar boundary. Terraform, Crossplane, Pulumi, and Kubernetes manifests can all describe resources, but GitOps is not defined by the file format alone. The defining behavior is a versioned desired state automatically pulled and continuously reconciled. An IaC workflow that requires an engineer to run an apply command from a workstation may be good automation, but it is not automatically GitOps.

Configuration as Code can be even more subtle. A team may store application configuration in Git and still copy it manually into production. That gives review history but not automated reconciliation. Another team may store controller configuration in Git and have an agent reconcile it continuously. Both use Git, but only the second example completes the GitOps operating model.

**What would happen if:** A security team adds policy checks that reject unapproved container registries, but deployments still happen through a human running scripts from a laptop. Does the policy system make the workflow GitOps? The better answer is no. Policy improves governance, and it may support GitOps, but it does not replace the source-of-truth and reconciliation requirements.

A senior answer also avoids tool tribalism. ArgoCD and Flux are common GitOps controllers, but their presence does not automatically make every surrounding process healthy. Helm and Kustomize can render or customize manifests, but they do not define the whole operating model by themselves. The exam often asks for the most GitOps-aligned practice, not the most famous tool name.

### 5. Use Patterns To Reason About Environments And Promotion

Patterns are where the exam moves from vocabulary into design trade-offs. A single environment can reconcile one branch or path from one repository. Multiple environments can use separate branches, directories, repositories, or promotion pull requests. Multiple clusters can share base configuration while applying cluster-specific overlays. None of those layouts is universally best, so you must reason from risk, governance, blast radius, and team workflow.

```ascii
+-------------------+        pull request         +-------------------+
| app source repo   | --------------------------> | env config repo   |
| code and tests    |                             | desired state     |
+-------------------+                             +-------------------+
          |                                                |
          | image build and scan                           | controller pulls
          v                                                v
+-------------------+                             +-------------------+
| container registry|                             | cluster runtime   |
| immutable image   |                             | actual state      |
+-------------------+                             +-------------------+
```

Promotion patterns test whether you understand what should move between environments. A common GitOps promotion model does not push live cluster state from dev to staging. Instead, it promotes a reviewed change to the desired state for the next environment, often by updating an image tag, chart version, Kustomize overlay, or environment path. The reconciler for that environment then pulls the updated desired state.

Rollback follows the same logic. A GitOps-friendly rollback changes desired state back to a known good version, then lets reconciliation converge runtime state. A less aligned rollback manually edits the cluster until it appears fixed, leaving Git stale and future reconciliations unpredictable. The exam may present both answers as "fast"; the better answer preserves auditability and future consistency.

Environment separation is another frequent design signal. Separate repositories can increase isolation and access control, but they add coordination overhead. Separate directories in one repository can simplify shared review and reduce duplication, but they require careful permissions and review rules. Branch-based promotion can feel familiar to developers, but it can also create merge complexity if environment state diverges heavily. The best answer depends on the scenario constraints.

| Pattern choice | Useful when | Risk to watch | Exam reasoning cue |
|---|---|---|---|
| One repo with environment directories | Teams want simple shared visibility and consistent review | Weak permissions can allow accidental production edits | Look for small teams or low separation requirements |
| Separate repos per environment | Production needs stronger access control or ownership boundaries | Duplication and promotion coordination can increase | Look for compliance, isolation, or separate approver needs |
| Branch-based promotion | Team already manages promotion through branch workflows | Long-lived branch drift can become confusing | Look for questions about merge discipline and history |
| Image tag promotion | Build once and deploy the same immutable artifact across environments | Mutable tags undermine repeatability | Look for artifact immutability and traceability |
| Overlay-based customization | Environments share a base but need specific differences | Overlay sprawl can hide important changes | Look for Kustomize, Helm values, or environment-specific settings |
| Multi-cluster reconciliation | Many clusters need consistent baselines and local overrides | Broad mistakes can affect many clusters if review is weak | Look for fleet management, tenants, or regional clusters |

Worked example: A company has dev, staging, and production clusters. Developers can merge to dev after normal review, but production requires operations approval. The team wants to promote the same image digest through each environment. A strong GitOps design stores environment desired state in reviewed Git paths or repos, updates the image digest through pull requests, restricts production approvals, and lets each environment controller reconcile its own target. A weaker answer has CI deploy directly to each cluster after a manual checkbox.

This example demonstrates the difference between "manual approval" and "manual deployment." Manual approval can be part of GitOps when it gates a desired-state change in Git. Manual deployment breaks the model when a person applies changes directly to the cluster and Git becomes historical paperwork. CGOA questions often hide this distinction in wording, so slow down when you see approval, emergency, rollback, or production.

### 6. Study Tooling Through Roles, Not Product Memorization

Tooling is the smallest domain by weight, but it appears throughout scenario questions. The safest study approach is to learn what role each tool commonly plays in a GitOps system. A controller reconciles desired state. A packaging tool produces or renders manifests. A customization tool overlays environment differences. A policy tool validates or constrains changes. A secrets tool protects sensitive material while still supporting declarative workflows.

| Tool or category | Common role in GitOps study | What to know for CGOA-level reasoning | What not to overfocus on |
|---|---|---|---|
| ArgoCD | GitOps controller with application-oriented reconciliation and UI visibility | It pulls desired state, [compares sync status, reports health](https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/), and supports app patterns | Memorizing every CLI flag or screen label |
| Flux | GitOps toolkit with [controllers for sources, Kustomizations, Helm releases, and image automation](https://fluxcd.io/flux/concepts/) | It reconciles sources and workloads through Kubernetes-native controllers | Treating it as only a simple sync script |
| Helm | [Packaging and templating system for Kubernetes manifests](https://helm.sh/docs/topics/charts/) | It can produce desired manifests that a GitOps controller reconciles | Assuming Helm alone provides continuous GitOps reconciliation |
| Kustomize | [Overlay and patch system for customizing Kubernetes YAML](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) | It supports environment-specific desired state without templating | Assuming overlays remove the need for review discipline |
| Jsonnet | Data templating language for generating configuration | It can model complex reusable configuration | Expecting deep syntax questions at associate level |
| SOPS or sealed secrets | Secret handling approaches often used with GitOps | They help keep encrypted or sealed secret material in Git safely | Claiming plaintext secrets in Git are acceptable |
| Policy engines | Validation and governance for desired or admitted state | They complement GitOps by enforcing rules before or during reconciliation | Treating policy as a replacement for reconciliation |

The product names matter less than the control responsibility. If a question asks whether Helm or Kustomize is more appropriate, focus on what problem is being solved. Helm is often used for packaged applications with values and releases. Kustomize is often used for composing bases and overlays without templates. Both can fit inside GitOps, and neither alone guarantees GitOps.

ArgoCD and Flux questions often test reconciliation, drift detection, and source tracking. You do not need to memorize every configuration field to answer associate-level questions. You do need to know that these tools watch sources of desired state, compare them with actual cluster state, and apply changes through controllers. If an answer makes them passive documentation systems, it is likely wrong.

Secrets questions require careful trade-off reasoning. GitOps prefers Git as the source of truth, but [plaintext secrets in Git are unsafe](https://kubernetes.io/docs/concepts/security/secrets-good-practices/). The exam may expect recognition of [encrypted secrets, sealed secrets, external secret managers, or secret references as safer patterns](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/). The key is to preserve declarative management and auditability without exposing sensitive values.

A senior-level study habit is to write tool-neutral answers first. Before naming ArgoCD or Flux, describe the capability: "a controller pulls versioned desired state and reports sync health." Before naming Helm or Kustomize, describe the need: "the team needs repeatable environment-specific manifests." This prevents tool names from distracting you from the principle being tested.

### 7. Turn Multiple-Choice Questions Into A Repeatable Procedure

The best exam strategy is a repeatable procedure that reduces anxiety and catches distractors. Start by identifying the scenario's operating problem. Then classify the blueprint domain. Next, trace the GitOps loop. After that, eliminate answer choices that break source of truth, reviewability, pull-based automation, or reconciliation. Only then compare the remaining choices for the best fit.

```ascii
+---------------------+
| Read scenario once  |
+----------+----------+
           |
           v
+---------------------+
| Name the problem    |
| drift? promotion?   |
| CI boundary? tool?  |
+----------+----------+
           |
           v
+---------------------+
| Map to blueprint    |
| domain and principle|
+----------+----------+
           |
           v
+---------------------+
| Eliminate choices   |
| breaking the loop   |
+----------+----------+
           |
           v
+---------------------+
| Choose best answer  |
| for this scenario   |
+---------------------+
```

Worked example: A question says a team has production manifests in Git, but engineers frequently edit live resources during incidents. After each incident, production sometimes changes again when the GitOps controller syncs. The team asks how to reduce confusion. The strongest answer is to require incident fixes to be captured as reviewed desired-state changes, then let the controller reconcile, while using emergency processes that update Git as soon as possible. The weakest answer is to pause the controller indefinitely and rely on manual edits.

The reasoning is mechanical. The scenario is about drift and source-of-truth confusion. The relevant principles are versioned desired state and continuous reconciliation. A tempting answer may emphasize speed by letting operators edit the cluster directly, but that treats the symptom while making the model less reliable. Another tempting answer may mention a tool upgrade, but tooling alone does not fix ownership of desired state.

Worked example: A question says a team builds container images in CI and wants the fastest GitOps-aligned way to deploy a tested image to staging. The best answer is usually to update staging desired state, such as an image digest or chart version, through a controlled Git change and allow the staging reconciler to apply it. An answer that has CI run `kubectl set image` directly against staging may be fast, but it bypasses the desired-state review and reconciliation model.

This procedure also helps with "best answer" questions. Sometimes two answers are partly correct, but one is more complete. Prefer the answer that preserves the operating model across the full lifecycle: proposed change, review, versioned state, automated pull, reconciliation, feedback, and rollback. If an answer works only for the happy path but fails audit or recovery, it is usually weaker.

### 8. Build A Study Plan That Matches The Blueprint

A good study plan starts with high-weight principles and terminology, then layers in patterns, related practices, and tooling. Do not spend the first week memorizing product feature lists. Learn the control loop first, because it explains why the product features exist and how to interpret scenario wording. Once the model is stable, tool comparisons become easier.

| Study phase | Main goal | Practice activity | Evidence you are ready to move on |
|---|---|---|---|
| Phase 1: Terms | Explain core vocabulary through incidents | Write one production-style scenario for each term | You can distinguish drift, reconciliation, desired state, and feedback without notes |
| Phase 2: Principles | Trace the GitOps loop through workflows | Classify workflows as aligned, partial, or misaligned | You can explain which principle a bad workflow breaks |
| Phase 3: Boundaries | Compare GitOps with neighboring practices | Sort responsibilities across CI, Git, controller, and runtime | You can say what CI should do and what the reconciler should do |
| Phase 4: Patterns | Evaluate promotion, rollback, and environment designs | Sketch repository and environment flow diagrams | You can justify a pattern using risk, access, and audit needs |
| Phase 5: Tools | Map tools to capabilities | Build tool-role flashcards with scenarios, not definitions | You can answer tool questions without relying on brand loyalty |
| Phase 6: Timed review | Practice exam procedure under time pressure | Review every missed question by domain and broken principle | Your misses cluster into fixable reasoning habits instead of random guesses |

The review process matters more than the raw number of practice questions. After each practice set, tag every missed question with one cause: vocabulary confusion, principle break, boundary confusion, pattern trade-off, tool role, or careless reading. Then study the highest-frequency cause first. This converts mistakes into a targeted improvement plan instead of a vague feeling that you need to "study more."

Avoid studying only from flashcards. Flashcards help with vocabulary, but CGOA questions are scenario based enough that you need application practice. For each term, write a small operational story. For each principle, write one aligned and one misaligned workflow. For each tool, write what role it plays in the loop. This forces retrieval and analysis together.

Time management on exam day should protect reasoning. If a question is long, read the last sentence first to find what it asks, then read the scenario. If two answers look close, compare them against the GitOps loop instead of comparing word elegance. If you are stuck, eliminate answer choices that turn Git into documentation after the fact, replace reconciliation with manual action, or confuse CI with cluster convergence.

### 9. Recommended KubeDojo Review Path

Use the following modules as a guided review path, but do not read them as isolated references. For each module, write down one CGOA-style scenario it helps answer. That transforms passive review into practice and gives you a personal bank of examples before you attempt full practice sets.

- [What is GitOps?](../../../platform/disciplines/delivery-automation/gitops/module-3.1-what-is-gitops/)
- [Repository Strategies](../../../platform/disciplines/delivery-automation/gitops/module-3.2-repository-strategies/)
- [Environment Promotion](../../../platform/disciplines/delivery-automation/gitops/module-3.3-environment-promotion/)
- [Drift Detection](../../../platform/disciplines/delivery-automation/gitops/module-3.4-drift-detection/)
- [Secrets in GitOps](../../../platform/disciplines/delivery-automation/gitops/module-3.5-secrets/)
- [Multi-cluster GitOps](../../../platform/disciplines/delivery-automation/gitops/module-3.6-multi-cluster/)
- [IaC Fundamentals](../../../platform/disciplines/delivery-automation/iac/module-6.1-iac-fundamentals/)
- [ArgoCD](../../../platform/toolkits/cicd-delivery/gitops-deployments/module-2.1-argocd/)
- [Flux](../../../platform/toolkits/cicd-delivery/gitops-deployments/module-2.3-flux/)
- [Helm & Kustomize](../../../platform/toolkits/cicd-delivery/gitops-deployments/module-2.4-helm-kustomize/)

When reading the GitOps discipline modules, focus on operating consequences. Ask what breaks when Git is not the source of truth, what breaks when reconciliation is not continuous, and what breaks when promotion is not represented as reviewed desired state. These questions align directly with exam reasoning and with real platform engineering decisions.

When reading the tooling modules, focus on capability boundaries. ArgoCD and Flux reconcile desired state, but they do not remove the need for clean repository strategy. Helm and Kustomize help shape manifests, but they do not replace review, audit, and feedback. Secrets tools reduce exposure risk, but they still need a design that avoids plaintext sensitive values in Git.

The path above is intentionally broader than a cram sheet. CGOA is an associate exam, but the strongest preparation is to understand why GitOps exists as an operating model. If you can explain the trade-off behind each pattern, you can handle unfamiliar wording because you are reasoning from first principles.

## Patterns & Anti-Patterns

The exam strategy that works best is the same strategy that works in a production design review: name the ownership boundary before you name the tool. In a healthy GitOps answer, the proposed change is represented as declarative desired state, the desired state is stored in a reviewed and versioned location, a software agent pulls that state, and the runtime system is checked continuously for convergence. This pattern prevents a question from turning into a guessing contest about whether the examiner prefers ArgoCD, Flux, Helm, Kustomize, or another implementation detail.

The first strong pattern is **controller-owned convergence**. Use it when a question describes a cluster, an environment, or a fleet that should stay aligned with Git over time. The reason this pattern works is that the deployment authority remains with the reconciler rather than with a laptop, a one-shot CI job, or a dashboard button. It scales because every environment can have its own reconciliation scope, permissions, and health feedback while still using the same mental model for rollback and drift investigation.

The second strong pattern is **reviewed promotion of immutable artifacts**. Use it when a question describes movement from development to staging or production, especially when the same tested image should move through multiple environments. The best answer usually changes an image digest, chart version, or overlay value in the next environment's desired state, then lets that environment's controller reconcile. This pattern keeps promotion auditable and prevents teams from copying live runtime objects forward with all their accidental mutations.

The third strong pattern is **tool-neutral capability mapping**. Use it whenever an answer choice names a product, because product names are often distractors unless the role is clear. ArgoCD and Flux commonly reconcile desired state; Helm packages and renders applications; Kustomize composes bases and overlays; policy engines validate rules; secret tooling protects sensitive material while preserving declarative workflows. A candidate who maps capability before tool can answer unfamiliar product wording without abandoning the GitOps principles.

The fourth strong pattern is **miss review by failure mode**. Use it during study after every timed practice set, because raw score alone does not tell you what to repair. Tag each miss as terminology confusion, principle break, related-practice boundary, pattern trade-off, tool-role confusion, or careless reading. After a few sets, the pattern of misses tells you whether to reread a domain, rebuild a diagram, or practice answer elimination, and that is more efficient than rereading every module with equal weight.

The most dangerous anti-pattern is **Git as deployment paperwork**. Teams fall into it because they genuinely store manifests or values in Git, but the runtime change still happens somewhere else through a direct command, dashboard action, or pipeline push. It feels close to GitOps because Git is present, yet it breaks audit, rollback, and reconciliation because Git records intent after the fact rather than owning the desired state. On the exam, reject answers where Git is merely a record of what someone already did.

Another common anti-pattern is **manual incident drift with delayed cleanup**. It happens because production incidents reward immediate action, and a direct edit may look like the fastest way to restore service. The trap is that the controller may later revert the edit, or future deployments may behave unpredictably because the desired state and actual state tell different stories. A better answer allows emergency action only inside a process that captures the fix in Git quickly, documents the reason, and returns convergence authority to the reconciler.

A subtler anti-pattern is **blueprint silo studying**. Candidates see the domain weights and create separate piles of flashcards, then become surprised when a tooling question depends on a principle or a pattern question depends on terminology. The blueprint is layered, not isolated: terminology gives names, principles define the loop, related practices define boundaries, patterns show design choices, and tooling provides implementations. Study activities should cross those layers so each practice question builds judgment rather than isolated recall.

| Pattern or anti-pattern | Use or avoid when | Why it matters for CGOA reasoning | Scaling concern |
|---|---|---|---|
| Controller-owned convergence | Use when runtime state must stay aligned with reviewed desired state | Preserves pull-based reconciliation and feedback | Scope controllers and permissions per environment or cluster |
| Reviewed promotion of immutable artifacts | Use when moving tested releases through environments | Keeps promotion auditable and repeatable | Avoid mutable tags and unclear ownership of production state |
| Tool-neutral capability mapping | Use when product names appear in choices | Prevents tool trivia from hiding principle violations | Keep a short role map for common tools instead of memorizing screens |
| Miss review by failure mode | Use after every timed practice set | Converts wrong answers into a targeted study plan | Tag misses consistently or the data becomes noisy |
| Git as deployment paperwork | Avoid when Git records changes after runtime action | Breaks source-of-truth reasoning | Audit trails become weak and rollback becomes guesswork |
| Manual incident drift with delayed cleanup | Avoid when direct edits are not captured in Git | Creates conflict between actual state and desired state | Emergency paths need ownership, time limits, and review |
| Blueprint silo studying | Avoid when preparing across domains | Produces brittle answers to mixed scenario questions | Review paths should connect terms, principles, patterns, and tools |

## Decision Framework

Use this framework whenever a CGOA question feels ambiguous, because ambiguity usually means the exam is asking you to compare operating consequences rather than recall a definition. First, find the scenario's decision point: a deployment path, a rollback, a drift response, an environment promotion, a tool choice, or a study-priority choice. Second, ask which blueprint domain is most visible and which lower-level principle supports it. Third, trace the GitOps loop and eliminate answer choices that make Git stale, make humans the steady-state deploy mechanism, remove continuous reconciliation, or hide feedback.

The framework starts with desired state because desired state is the anchor for every other exam decision. If an answer does not say where the target state lives, who can review it, and how it changes, the answer is probably incomplete even if it mentions automation. Desired state also separates Kubernetes platform configuration from unrelated runtime data: a Deployment replica count, an ArgoCD Application, or a Kustomize overlay can be managed declaratively, while user transactions in a database are not normally promoted through GitOps as YAML. That boundary prevents overbroad answers that claim Git should contain every changing value in a system.

After desired state, evaluate the execution path. In GitOps, a controller or software agent should pull approved state and reconcile the runtime environment; CI should usually build, test, scan, package, render, and propose changes rather than become the long-term cluster convergence mechanism. This distinction does not make CI less important. It makes the handoff cleaner: CI produces confidence and artifacts, Git records the desired operational target, and the reconciler applies and observes the target inside the environment where drift can occur.

Next, evaluate feedback and recovery. A deployment that cannot report sync, health, drift, or reconciliation failure is not a complete operating model, because the team cannot tell whether intent became reality. A rollback that edits production by hand may be fast in the moment, but it leaves the next reconciliation cycle and the next audit review in doubt. Prefer answers where rollback is a desired-state change to a known good version, followed by convergence and observation, because that preserves both speed and governability.

Finally, compare the remaining choices against the wording of the scenario rather than against personal preference. If the scenario emphasizes regulation, the best pattern may isolate production permissions even if a single repository is simpler. If the scenario emphasizes a small team learning GitOps, one repository with clear environment paths may be easier to reason about than a many-repository layout. If the scenario emphasizes Kubernetes 1.35 or newer platform behavior, assume current Kubernetes primitives and controller-based reconciliation rather than older manual cluster operation habits.

Pause and predict: if a question says a team uses encrypted secrets in Git but disables the controller during every production change, which part of the GitOps loop is protected and which part is broken? The confidentiality problem is handled better than plaintext secrets, but the reconciliation model is still broken if the controller is not trusted to apply and observe desired state. This is why "best answer" questions often require choosing the option that preserves the most important operating properties together, not the option that fixes only one symptom.

The same sequence works when the question mentions Kubernetes directly. For Kubernetes 1.35 and newer, assume that declarative API objects, controllers, server-side validation, and status reporting are normal parts of the platform, so a GitOps answer should use those strengths instead of bypassing them. If a prompt mentions `kubectl`, remember that the exam is usually testing whether the command belongs in an emergency investigation, a one-time bootstrap, or the steady-state deployment path; the `k` alias is convenient for practice, but it does not change the operating boundary.

This distinction is useful because many realistic teams keep a small number of imperative commands for diagnosis, bootstrap, or recovery while still expecting normal delivery to flow through reviewed desired state. The exam is not asking you to pretend those commands never exist; it is asking you to decide whether they are temporary support actions or the regular mechanism that changes production. That difference often separates a merely plausible answer from the strongest GitOps answer.

Before running a timed practice set, write the following decision sequence on scratch paper or in your notes. The sequence is short enough to use under exam pressure, but it still protects the reasoning path. If a question takes too long, stop rereading the same sentence and move through the sequence deliberately: problem, domain, principle, broken answer choices, best operational consequence.

```ascii
+-------------------------+
| 1. Name the problem     |
| drift, promotion, tool, |
| boundary, or study plan |
+-----------+-------------+
            |
            v
+-------------------------+
| 2. Map the domain       |
| terminology, principle, |
| practice, pattern, tool |
+-----------+-------------+
            |
            v
+-------------------------+
| 3. Trace the loop       |
| desired, versioned,     |
| pulled, reconciled      |
+-----------+-------------+
            |
            v
+-------------------------+
| 4. Eliminate breaks     |
| stale Git, manual push, |
| missing feedback        |
+-----------+-------------+
            |
            v
+-------------------------+
| 5. Pick consequence     |
| safest for audit,       |
| recovery, and scale     |
+-------------------------+
```

## Did You Know?

1. **GitOps is defined by an operating model, not by Git alone.** A repository gives version history, but the model also requires declarative desired state, automated pull-based application, continuous reconciliation, and feedback about convergence.

2. **A manual approval can still fit GitOps when it gates a desired-state change.** The approval becomes a problem only when it turns into a person manually changing production while Git becomes stale documentation.

3. **Drift detection is useful because it protects both reliability and auditability.** It tells teams when runtime state no longer matches the reviewed target, which helps them separate intentional change from accidental or unauthorized change.

4. **The CGOA blueprint is weighted toward principles.** GitOps Principles is the single heaviest domain at **30%**, followed by GitOps Terminology and GitOps Patterns at **20%** each, Related Practices at **16%**, and Tooling at **14%** — so principle-level reasoning earns more than tool trivia.

## Common Mistakes

| Mistake | Why it hurts | Better answer |
|---|---|---|
| Treating GitOps as "using Git for config" | That definition misses pull-based automation, reconciliation, and feedback, so it cannot distinguish good workflows from shallow Git storage | Explain the full loop: declarative desired state, versioned source, automated pull, continuous reconciliation, and observed feedback |
| Mixing GitOps with CI/CD | CI and GitOps cooperate, but CI usually builds and validates while GitOps reconciles approved desired state into environments | Separate build and test responsibilities from desired-state management and cluster convergence |
| Memorizing tools without the model | Tool names can distract from the principle being tested, especially when multiple tools could support the same pattern | Start by identifying the capability required, then map tools to that capability |
| Confusing drift with normal dynamic state | Not every runtime change is a violation of desired state, because some fields are generated, observed, or owned by other controllers | Ask whether the difference is part of the declarative state that GitOps is expected to manage |
| Choosing speed over source of truth during incident scenarios | Manual hotfixes may appear fast, but they create hidden state that reconciliation or future deployments can overwrite | Use emergency workflows that capture the fix in Git and restore reconciler ownership as quickly as possible |
| Assuming IaC automatically equals GitOps | IaC describes resources, but a person running an apply command is not the same as continuous pull-based reconciliation | Evaluate whether the workflow has a versioned desired state and an automated reconciler |
| Reading blueprint percentages as isolated silos | Tooling, patterns, and related practices often depend on terminology and principles, so studying them separately causes brittle answers | Use the blueprint as a layered map where principles explain the other domains |
| Trusting a correct-sounding phrase without checking consequences | Distractors often include words like Git, automation, or declarative while quietly breaking review, pull, or feedback | Trace the proposed workflow end to end before choosing the answer |

## Quiz

<details>
<summary>Your team stores Kubernetes manifests in Git, and a CI job applies them directly to production after tests pass. A CGOA scenario question asks whether this is the strongest GitOps design. How should you evaluate the workflow?</summary>

The workflow has declarative and versioned pieces, but it is not the strongest GitOps design because deployment is push-based from CI and may not include continuous reconciliation. A better answer separates CI from reconciliation: CI builds, tests, scans, and proposes or updates desired state, while a GitOps controller pulls the approved state and keeps the cluster converged. The tested reasoning is the boundary between CI/CD and GitOps, not whether CI is useful. This evaluates the scenario by locating the blueprint domain first, then checking which GitOps principle is at risk.

</details>

<details>
<summary>A production incident is fixed by editing a live Deployment in the cluster. The next morning the value changes back to the Git version, and the team is confused. Which concept should you apply first, and what process change would you recommend?</summary>

Apply the concepts of drift, desired state, and reconciliation. The live edit created a runtime difference from the desired state stored in Git, and the reconciler moved the cluster back toward the declared target. The better process is to capture the incident fix as a reviewed desired-state change in Git, then let the controller reconcile it, with an emergency path that still restores Git as the source of truth. That answer preserves auditability while explaining why the original runtime-only change did not last.

</details>

<details>
<summary>A question describes a team choosing between separate production and staging repositories or one repository with environment directories. Which answer is most likely correct if production has stricter approval and audit requirements?</summary>

The stronger answer is likely a design that enforces production-specific approval and access boundaries, which may mean a separate production repository or a strongly protected production path. The reasoning should mention governance, blast radius, and review requirements rather than claiming one repository pattern is always best. CGOA pattern questions usually reward matching the repository strategy to risk and ownership constraints. This is a design decision, so the best answer must explain the trade-off rather than simply choosing the most isolated layout.

</details>

<details>
<summary>A team uses Helm charts to package an application and stores values files in Git. Deployments happen when an engineer runs Helm from a laptop. A question asks whether Helm makes the workflow GitOps. What should you answer?</summary>

Helm supports the workflow by rendering and packaging manifests, but Helm alone does not make it GitOps. The laptop-driven command is a manual push action, and the scenario does not describe continuous pull-based reconciliation or feedback. A more GitOps-aligned design would store the desired chart version and values in Git and have a controller reconcile that desired state into the cluster. This answer compares tool capability with the operating model instead of treating a familiar Kubernetes tool as proof of GitOps.

</details>

<details>
<summary>A security team wants to store secrets in Git so that every environment can be fully recreated. One answer suggests committing plaintext Kubernetes Secret manifests because Git is the source of truth. Why is that answer weak, and what would be stronger?</summary>

The answer is weak because it applies the source-of-truth idea while ignoring confidentiality. GitOps does not require exposing sensitive values in plaintext. A stronger answer uses a safer declarative secret pattern, such as encrypted secrets, sealed secrets, or external secret references, while preserving reviewable desired state and automated reconciliation. The reasoning matters because a secure GitOps answer must satisfy both governance and secrecy, not one at the expense of the other.

</details>

<details>
<summary>During a practice exam, two multiple-choice distractors both mention ArgoCD. One says ArgoCD should show sync and health status while reconciling from Git. The other says ArgoCD should be used as a dashboard after CI has already pushed changes into the cluster. How do you choose?</summary>

Choose the answer where ArgoCD reconciles from Git and reports sync and health status. That answer preserves the controller's role in the GitOps loop. The dashboard-only answer uses a tool name but assigns the deployment authority to CI, which weakens the pull-based reconciliation model and may turn Git into documentation after the fact. This is the distractor-analysis move: ignore the shared product name and trace which option keeps source of truth, reconciliation, and feedback intact.

</details>

<details>
<summary>A team wants faster promotion from staging to production. One proposal copies the live staging cluster objects into production. Another proposal promotes the same tested image digest by updating production desired state through a reviewed pull request. Which proposal is more GitOps-aligned, and why?</summary>

Promoting the tested image digest through reviewed production desired state is more GitOps-aligned. It keeps production controlled by a versioned source of truth, preserves auditability, and lets the production reconciler apply the approved target. Copying live cluster objects can transfer accidental runtime state and bypass the reviewable desired-state model. The scenario is about promotion design, so the best answer should preserve artifact immutability and environment-specific approval rather than moving observed state by hand.

</details>

<details>
<summary>A learner keeps missing questions that compare GitOps with Infrastructure as Code, CI/CD, and configuration automation. Their instinct is to answer that any declarative file in Git is GitOps. How would you correct their reasoning and adjust the study plan?</summary>

Declarative files in Git are necessary ingredients in many GitOps systems, but they are not the whole model. The learner should check whether the desired state is versioned and immutable, whether a software agent pulls it automatically, and whether actual state is continuously reconciled with feedback. IaC, CI/CD, and configuration automation can support GitOps, but they do not automatically supply the full control loop. The study plan should add boundary-comparison drills and missed-question tagging so the learner can validate progress instead of rereading the same definitions.

</details>

## Hands-On Exercise

**Task:** Build a personal CGOA exam decision sheet that classifies scenarios by blueprint domain, identifies the GitOps principle at stake, and records an answer-elimination rule. This exercise is hands-on because you will create a concrete study artifact, test it against scenarios, and verify that your reasoning aligns with the learning outcomes.

**Scenario set:** Use the scenarios below as your starting data. They are intentionally similar to exam prompts, but they are not asking for recall. For each scenario, decide which domain is most relevant, which principle or boundary is being tested, which answer type would be weak, and which answer type would be strong.

1. A CI system builds an image, runs tests, and then applies production manifests directly to the cluster.
2. An operator manually changes a live Deployment during an incident, and the GitOps controller later restores the Git value.
3. A team stores Helm values in Git but runs Helm manually from a laptop for each deployment.
4. A regulated production environment requires different approval rules from staging.
5. A team wants to keep secrets declarative without exposing plaintext values in the repository.
6. A multi-cluster platform team wants shared baseline configuration with cluster-specific differences.
7. A practice question asks whether GitOps, IaC, and DevOps are interchangeable names for the same practice.
8. A dashboard reports that an application is out of sync with the desired state in Git.

**Step 1: Create a working directory and study sheet.** The commands below create a simple Markdown worksheet that you can edit in any text editor. The command is runnable on a local machine with a POSIX shell, and it does not require a Kubernetes cluster.

```bash
mkdir -p cgoa-study
cat > cgoa-study/exam-decision-sheet.md <<'EOF'
# CGOA Exam Decision Sheet

## Decision Procedure

1. Name the scenario's operating problem.
2. Map the problem to a blueprint domain.
3. Identify the GitOps principle, boundary, or pattern being tested.
4. Eliminate answers that break source of truth, reviewability, pull-based automation, reconciliation, or feedback.
5. Choose the answer that best preserves the operating model in the scenario.

## Scenario Classifications

| Scenario | Domain | Principle or boundary | Weak answer pattern | Strong answer pattern |
|---|---|---|---|---|
| CI applies production manifests directly | Related Practices | CI versus GitOps reconciliation | CI becomes deploy authority | CI updates desired state; controller reconciles |
| Manual incident edit is reverted | Terminology | Drift and reconciliation | Disable reconciliation indefinitely | Capture fix in Git and reconcile |
| Helm values in Git, laptop deploy | Tooling | Tool role versus operating model | Helm alone equals GitOps | Controller reconciles chart desired state |
| Production requires stricter approval | Patterns | Environment governance | Same access for every environment | Protected production desired state |
| Declarative secrets without plaintext | Patterns | Source of truth plus confidentiality | Plaintext secrets in Git | Encrypted or external secret pattern |
| Shared multi-cluster baseline | Patterns | Fleet consistency with local variation | Duplicate unmanaged config | Shared base plus cluster overlays |
| GitOps, IaC, DevOps comparison | Related Practices | Practice boundaries | Treat all automation as identical | Separate goals and ownership |
| Application out of sync | Terminology | Desired versus actual state | Ignore feedback | Investigate drift and reconciliation |
EOF
```

**Step 2: Add your own reasoning notes.** Open `cgoa-study/exam-decision-sheet.md` and add one sentence under each row explaining why the weak answer breaks the GitOps model. Keep the sentence concrete. For example, do not write "because it is not GitOps"; write "because CI applies runtime state directly and the controller no longer owns convergence."

**Step 3: Create three new scenarios of your own.** One scenario must involve a rollback, one must involve a tool comparison, and one must involve a boundary between GitOps and another practice. For each scenario, write the strong answer pattern before you write the weak one. This order forces you to reason from the model instead of inventing distractors first.

**Step 4: Time-box a review pass.** Give yourself 12 minutes to classify the original eight scenarios and your three new scenarios without looking back at the module. Mark any scenario where you needed notes. Those marks identify the domain you should review next.

**Step 5: Validate your sheet with the decision procedure.** For each row, trace the GitOps loop: declarative desired state, versioned and immutable source, automated pull, continuous reconciliation, and feedback. If your strong answer does not preserve at least the relevant part of that loop, revise it.

**Success Criteria:**

- [ ] Your decision sheet contains all eight provided scenarios plus three original scenarios you wrote yourself.
- [ ] Every scenario has a blueprint domain, a principle or boundary, a weak answer pattern, and a strong answer pattern.
- [ ] At least one scenario covers terminology, one covers principles, one covers related practices, one covers patterns, and one covers tooling.
- [ ] Your rollback scenario explains why changing desired state is stronger than manually editing the live cluster.
- [ ] Your tool comparison scenario describes tool roles before naming the preferred tool.
- [ ] Your CI or IaC boundary scenario separates build, validation, desired-state storage, and reconciliation responsibilities.
- [ ] You can classify all scenarios in a 12-minute pass and explain each answer without using the phrase "because GitOps says so."
- [ ] You have identified one weakest domain for follow-up review and linked it to a module in the recommended KubeDojo path.

**Reflection prompt:** After completing the worksheet, choose the scenario that felt most ambiguous and write a short explanation of what made it hard. Ambiguity is useful feedback. If the difficulty came from vocabulary, review terminology. If it came from two answers sounding correct, practice tracing the full control loop. If it came from tool names, rewrite the scenario in tool-neutral language and solve it again.

## Learner check

> DevSecOps is orthogonal to GitOps in the same way CI is: it governs what security gates run on the way to production (shift-left scanning, policy checks, supply-chain controls), while GitOps governs how reviewed desired state reaches the cluster through pull-based reconciliation.

## Sources

- https://training.linuxfoundation.org/certification/certified-gitops-associate-cgoa/
- https://www.cncf.io/training/certification/cgoa/
- https://github.com/cncf/curriculum/blob/master/CGOA_Curriculum.pdf
- https://opengitops.dev/
- https://github.com/open-gitops/documents/blob/main/PRINCIPLES.md
- https://argo-cd.readthedocs.io/en/stable/
- https://fluxcd.io/flux/concepts/
- https://helm.sh/docs/
- https://kubectl.docs.kubernetes.io/references/kustomize/
- https://kubernetes.io/docs/concepts/configuration/secret/
- https://external-secrets.io/latest/
- https://getsops.io/docs/
- [cncf.io: cgoa](https://www.cncf.io/training/certification/cgoa/) — The CNCF certification page explicitly describes CGOA as an online, proctored, multiple-choice exam and states its scope.
- [github.com: PRINCIPLES.md](https://github.com/open-gitops/documents/blob/main/PRINCIPLES.md) — The OpenGitOps principles document is the canonical upstream definition of these four principles.
- [Argo CD Architectural Overview](https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/) — Backs Argo CD component architecture and responsibilities such as API server, repository server, application controller, Git polling/reconciliation, sync, rollback, auth delegation, and RBAC enforcement.
- [fluxcd.io: concepts](https://fluxcd.io/flux/concepts/) — Flux Core Concepts explicitly defines Sources and Reconciliation and gives GitRepository, Kustomization, and HelmRelease as concrete controller-backed examples.
- [Helm Charts](https://helm.sh/docs/topics/charts/) — Backs Helm chart structure, Chart.yaml, values.yaml, templates, dependencies, chart packaging, chart types, and general claims about how Helm models reusable Kubernetes application packages.
- [kubernetes.io: kustomization](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) — The Kubernetes Kustomize task page explicitly documents customization via kustomization files and explains bases and overlays.
- [kubernetes.io: secrets good practices](https://kubernetes.io/docs/concepts/security/secrets-good-practices/) — Kubernetes secret good-practices documentation explicitly warns that sharing or checking in base64-encoded Secret manifests exposes the secret and that base64 is not encryption.
- [argo-cd.readthedocs.io: secret management](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/) — Argo CD's secret-management guidance explicitly recommends destination-cluster secret management and names Sealed Secrets and External Secrets Operator as examples.

## Next Module

Continue with [CGOA GitOps Principles Review](../module-1.2-gitops-principles-review/).
