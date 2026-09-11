---
citations_verified: true
title: "CNPA Core Platform Fundamentals Review"
revision_pending: false
slug: k8s/cnpa/module-1.2-core-platform-fundamentals-review
sidebar:
  order: 102
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 75-95 minutes
>
> **Prerequisites**: Basic DevOps, Kubernetes workload concepts, CI/CD fundamentals, and the CNPA orientation module
>
> **Track**: CNPA exam prep | Core platform fundamentals

## Learning Outcomes

After completing this module, you will be able to:

- Analyze how platform engineering reduces developer cognitive load without removing team ownership or accountability.
- Compare platform engineering, DevOps, and SRE by evaluating their goals, operating models, and failure modes in realistic scenarios.
- Design a simple golden path that combines self-service, policy, observability, and documentation into a usable developer workflow.
- Evaluate whether an internal developer platform is acting as a product, a portal, or a ticket queue with nicer branding.
- Diagnose common CNPA exam traps around guardrails, automation, adoption, platform maturity, and developer experience.

## Why This Module Matters

A company can spend months building a platform and still make delivery worse. Developers may open more tickets than before, security may add more review queues, and operations may inherit new tools without clearer ownership. The failure is rarely the lack of a portal or the absence of a fashionable tool. The failure is usually that the organization never treated the platform as a product with users, feedback, measured outcomes, and a clear promise about what complexity it removes.

The CNPA core domain focuses on this exact distinction. The exam is not asking whether you can name popular platform tools from memory. It is testing whether you can reason about why platform engineering exists, how it differs from adjacent practices, and what makes a platform capability mature enough for real teams to trust. If a question describes developers waiting on manual tickets, copying unsafe templates, or bypassing the official path, the best answer usually starts with the operating model rather than the user interface.

This module teaches the core mental model from beginner to senior level. At the beginner level, platform engineering is the practice of building shared capabilities that help teams ship safely. At the practitioner level, it is a product discipline that must balance autonomy, governance, reliability, cost, and adoption. At the senior level, it is an organizational design choice: the platform team accepts responsibility for [reducing repeated complexity](https://tag-app-delivery.cncf.io/whitepapers/platforms/) so product teams can spend more of their attention on business problems.

## Core Content

### 1. The Platform Exists To Reduce Repeated Complexity

Platform engineering begins with a practical observation: many product teams solve the same delivery problems repeatedly. They need service templates, CI/CD pipelines, environments, secrets, deployment workflows, observability, identity, and incident response patterns. If every team invents these from scratch, the organization pays the cost many times and still gets inconsistent outcomes. The platform team exists to make the common path easier, safer, and more reliable than every team building its own path.

That does not mean platform engineering centralizes every decision. A mature platform removes unnecessary decisions while preserving meaningful ownership. A service team should not need to become an expert in every cloud networking primitive before deploying a small API, but it should still understand its service's reliability goals, resource needs, and operational behavior. The platform provides paved roads, guardrails, and useful defaults so teams can move quickly without guessing where the dangerous edges are.

A good exam answer usually recognizes this balance. If a choice says "platform teams own all operations so developers can ignore production," it is too extreme. If a choice says "developers should configure every infrastructure detail themselves because that is true DevOps," it is also too extreme. Platform engineering succeeds when it reduces cognitive load while keeping teams close enough to their systems to make responsible decisions.

```ascii
+----------------------+        +------------------------+        +----------------------+
| Repeated team needs  |        | Platform capabilities  |        | Developer outcomes   |
|----------------------|        |------------------------|        |----------------------|
| Service scaffolding  | -----> | Golden path templates  | -----> | Faster first deploy  |
| CI/CD configuration  | -----> | Standard pipelines     | -----> | Fewer broken releases|
| Runtime environments | -----> | Self-service requests  | -----> | Less ticket waiting  |
| Secrets and identity | -----> | Guardrailed workflows  | -----> | Safer defaults       |
| Logs, metrics, traces| -----> | Observability baseline | -----> | Faster diagnosis     |
+----------------------+        +------------------------+        +----------------------+
```

The important word in the diagram is "outcomes." A platform capability is not valuable because it exists. It is valuable when it changes the experience of delivery in a measurable way. A template that nobody uses is not a golden path. A portal that forwards requests into a manual queue is not real self-service. A policy that blocks deployment without explaining remediation is not a helpful guardrail. CNPA questions often hide these differences in plausible wording, so look for the outcome, not the label.

> **Stop and think:** A team says, "We have a developer portal, so we have an internal developer platform." What evidence would you ask for before agreeing? Focus on what developers can actually do without waiting for a manual handoff.

A useful beginner rule is that platform engineering turns repeated expert work into supported product workflows. A senior platform engineer adds two more questions: which work should be standardized, and which work should remain flexible? Standardization is helpful when teams repeatedly need the same safe path. Flexibility is necessary when workloads have genuine differences in latency, compliance, scale, or operational risk.

| Platform question | Weak answer | Stronger CNPA-style answer |
|---|---|---|
| What problem does the platform solve? | It gives developers a portal. | It reduces repeated delivery complexity through supported self-service capabilities. |
| Who are the users? | Anyone who files infrastructure tickets. | Internal developers and operators who consume platform products to ship and run services. |
| How is success measured? | Number of tools installed. | Adoption, lead time, reliability, support load, developer satisfaction, and safe delivery outcomes. |
| What should be standardized? | Everything possible. | Repeated workflows where common defaults reduce risk without blocking legitimate variation. |
| What should remain flexible? | Nothing, because flexibility creates drift. | Workload-specific choices that teams can justify and operate within guardrails. |

A platform team should therefore avoid becoming a new bottleneck. If the official path requires waiting several days for a manual approval, teams will route around it. If the path is easy but unsafe, security and operations will resist it. The platform product must make the right thing the easy thing by combining usability with governance. That combination is the heart of many CNPA questions.

### 2. Platform Engineering, DevOps, And SRE Are Related But Not The Same

DevOps, SRE, and platform engineering overlap because all three try to improve software delivery and operations. The exam expects you to separate them without creating false competition between them. [DevOps is a culture and operating model that reduces silos between development and operations](https://tag-app-delivery.cncf.io/wgs/platforms/glossary/). SRE is a reliability discipline that applies engineering practices to operations, often using service level objectives, error budgets, automation, and incident learning. Platform engineering builds internal products that make delivery and operations easier for teams.

The distinction matters because the same organization may use all three. DevOps shapes how teams collaborate. SRE shapes how reliability is measured and improved. Platform engineering shapes the shared capabilities that teams consume. A platform team may embed SRE practices into its golden paths, and a DevOps culture may make platform adoption easier, but those relationships do not make the terms interchangeable.

```ascii
+-------------------------+--------------------------+------------------------------+
| Practice                | Primary question         | Typical evidence             |
+-------------------------+--------------------------+------------------------------+
| DevOps                  | How do teams collaborate | Shared ownership, fast flow, |
|                         | across build and run?    | reduced handoffs             |
+-------------------------+--------------------------+------------------------------+
| SRE                     | How reliable should the  | SLOs, error budgets, toil    |
|                         | service be in practice?  | reduction, incident learning |
+-------------------------+--------------------------+------------------------------+
| Platform engineering    | How do teams consume     | Golden paths, self-service,  |
|                         | shared capabilities?     | adoption, product feedback   |
+-------------------------+--------------------------+------------------------------+
```

A common exam trap is to describe platform engineering as "the team that does DevOps for everyone else." That answer weakens the DevOps principle of shared ownership. Another trap is to describe SRE as "the platform team that keeps systems online." That answer misses SRE's reliability-specific practices. A better answer identifies the center of gravity: DevOps is cultural collaboration, SRE is reliability engineering, and platform engineering is productized internal capability.

The boundaries can still be messy in real organizations. A small company may have one team handling CI/CD templates, incident processes, observability, Kubernetes operations, and developer support. The label matters less than the operating model. If that team behaves as a ticket queue and manually performs every deployment-related task, it is not practicing mature platform engineering even if its name says "platform." If it creates reliable self-service workflows, measures adoption, and improves the developer journey, it is moving toward platform maturity.

> **Active check:** Read the following scenario and decide which discipline is most central. A team introduces error budgets and uses them to decide whether to pause feature releases after repeated outages. This is mainly SRE, even if the data appears inside a developer portal.

| Scenario signal | Most likely concept | Why that answer fits |
|---|---|---|
| Teams are encouraged to own build and run responsibilities together. | DevOps | The focus is collaboration and reducing organizational silos. |
| A service has an SLO and release decisions change when the error budget is exhausted. | SRE | The focus is reliability targets and engineering trade-offs. |
| Developers create new services from approved templates with default pipelines and observability. | Platform engineering | The focus is reusable internal capability consumed through self-service. |
| A central team manually approves every namespace request through a queue. | Operations bottleneck | The process may be necessary temporarily, but it is not mature self-service. |
| A portal displays links but cannot provision, configure, or operate anything. | Developer portal only | The interface exists, but the platform capability may still be missing. |

Senior practitioners pay attention to incentives. DevOps fails when ownership becomes vague. SRE fails when reliability targets are ignored or used as paperwork. Platform engineering fails when adoption is treated as obedience rather than user choice. A mature platform team earns adoption by making the supported path better than the unsupported path, then uses metrics and feedback to improve that path over time.

### 3. Internal Developer Platforms Are Product Surfaces, Not Just Portals

An internal developer platform, often shortened to IDP, is the developer-facing product surface for platform capabilities. It may include [a portal, templates, APIs, command-line tools, documentation, service catalogs, workflow engines, policy checks, and integrations with infrastructure systems](https://tag-app-delivery.cncf.io/wgs/platforms/glossary/). The key idea is the abstraction boundary. Developers interact with a supported workflow, while the platform hides or automates lower-level complexity that most teams should not repeat manually.

The portal is only one possible surface. A team might consume the platform through Git pull requests, a CLI, a Backstage plugin, a service catalog, an API, or a Kubernetes custom resource. The exam may present a shiny portal as though it proves platform maturity. Be skeptical. The mature platform question is not "is there a UI?" but "can developers complete common work safely, quickly, and consistently?"

A good IDP makes the common workflow visible and operable. A developer should be able to discover how to create a service, understand what defaults will be applied, request the needed runtime resources, see deployment status, find logs and metrics, and know how to get support when something fails. The platform team should be able to see where the workflow breaks, where users abandon it, and which teams need exceptions.

```ascii
+--------------------------------------------------------------------------------+
|                         Internal Developer Platform                             |
+--------------------------------------------------------------------------------+
|                                                                                |
|  +----------------+    +----------------+    +----------------+                 |
|  | Service catalog|    | Golden paths   |    | Documentation  |                 |
|  | ownership data |    | templates      |    | support model  |                 |
|  +-------+--------+    +-------+--------+    +-------+--------+                 |
|          |                     |                     |                          |
|          v                     v                     v                          |
|  +----------------+    +----------------+    +----------------+                 |
|  | CI/CD systems  |    | Runtime layer  |    | Observability  |                 |
|  | build/release  |    | Kubernetes/IaaS|    | logs/metrics   |                 |
|  +-------+--------+    +-------+--------+    +-------+--------+                 |
|          |                     |                     |                          |
|          v                     v                     v                          |
|  +--------------------------------------------------------------------------+  |
|  |                 Policy, identity, audit, quotas, cost controls            |  |
|  +--------------------------------------------------------------------------+  |
|                                                                                |
+--------------------------------------------------------------------------------+
```

This diagram also shows why "IDP equals portal" is too narrow. The portal may be the front door, but the platform includes the workflows and integrations behind it. If a developer clicks "create database" and a human platform engineer still performs every step manually, the portal is a request form. If the workflow validates policy, provisions the database, attaches identity, records ownership, applies cost tags, and exposes connection guidance, the platform is providing real self-service.

> **Stop and think:** Your organization has a service catalog, but ownership fields are stale and nobody knows who responds to incidents. Is the catalog improving developer experience, or is it creating false confidence? What platform feedback loop would you add first?

The strongest IDP design starts from user journeys. A beginner may think in features: catalog, template, pipeline, dashboard. A senior practitioner thinks in workflows: create a service, deploy a change, request a dependency, diagnose an incident, rotate a secret, decommission a workload. Each workflow should have an owner, a service level expectation, clear documentation, and feedback from real users. Without that product thinking, an IDP becomes a collection of disconnected tools.

| IDP surface | What it can provide | What makes it mature |
|---|---|---|
| Developer portal | Discovery, catalog, docs, workflow entry points | Accurate ownership data and links to working self-service actions |
| CLI | Fast repeatable operations for engineers who prefer terminals | Consistent authentication, safe defaults, and useful error messages |
| Git workflow | Reviewable changes for infrastructure and app configuration | Policy checks, audit trail, and clear rollback paths |
| Templates | Standard service or infrastructure starting points | Maintained defaults, versioning, and migration guidance |
| APIs | Automation hooks for teams and other tools | Stable contracts, authentication, rate limits, and documentation |
| Observability views | Logs, metrics, traces, SLO status, incident context | Actionable signals mapped to ownership and remediation steps |

A senior platform team also distinguishes between discoverability and capability. Discoverability means the developer can find the right path. Capability means the path actually performs useful work. Both matter. If capability exists but nobody can find it, adoption suffers. If discovery exists without capability, frustration grows because the interface promises more than the platform can deliver.

### 4. Golden Paths Are Opinionated Workflows With Escape Hatches

A golden path is the recommended route for a common workflow. It is opinionated because the platform team has selected defaults that work for most cases. It is not supposed to be a prison. The path should reduce accidental complexity while still allowing justified exceptions for teams with special requirements. This balance is why many platform engineers prefer the phrase "paved road" to "one true way."

A weak golden path is only a document. It says, "Use these tools and follow these steps," but the developer still assembles everything manually. A stronger golden path is executable. It scaffolds a service, applies standards, creates deployment configuration, connects observability, and shows the developer how to operate what was created. The exam may describe either version, so inspect whether the path merely recommends behavior or actually supports it.

A golden path should usually include four layers. First, it gives a developer a starting point, such as a service template. Second, it embeds guardrails, such as security checks and required metadata. Third, it provides operational defaults, such as logging, metrics, health checks, and rollback guidance. Fourth, it offers support and feedback, because teams will find gaps that the platform team did not predict.

```ascii
+----------------------+      +----------------------+      +----------------------+
| Start with template  | ---> | Deploy through path  | ---> | Operate with defaults|
|----------------------|      |----------------------|      |----------------------|
| service scaffold     |      | CI/CD pipeline       |      | logs and metrics     |
| ownership metadata   |      | policy checks        |      | health checks        |
| dependency choices   |      | environment config   |      | incident runbook     |
+----------------------+      +----------------------+      +----------------------+
           |                             |                              |
           v                             v                              v
+--------------------------------------------------------------------------------+
|                      Feedback loop: adoption, friction, incidents, exceptions    |
+--------------------------------------------------------------------------------+
```

A good golden path should make the common case faster than the custom path. If developers must fight the template, wait for approvals, or rewrite generated configuration before anything works, they will avoid the platform. If security requirements appear only after the team is ready to release, developers will see the platform as a blocker. The best guardrails appear early, explain the reason for failures, and give a remediation route.

> **Active check:** A team asks to bypass the golden path because its service needs a nonstandard database topology. A mature platform response is not automatically "yes" or "no." Evaluate whether the requirement is real, whether the platform should support a new variant, and whether the exception can remain auditable.

| Golden path element | Beginner interpretation | Senior interpretation |
|---|---|---|
| Template | A starter repository | A maintained product artifact with versioning and migration expectations |
| CI/CD pipeline | A build script | A controlled release path with evidence, rollback, policy, and feedback |
| Policy check | A gate that blocks bad changes | A guardrail that teaches remediation and prevents known unsafe states |
| Documentation | Instructions for humans | A support surface that reduces repeated questions and captures intent |
| Escape hatch | A way to ignore the platform | A governed exception process that preserves autonomy without hiding risk |
| Adoption metric | Number of teams told to use it | Evidence that teams choose it because it solves their workflow better |

The escape hatch is especially important in exam scenarios. A platform that forbids every exception may look safe, but it can push teams into shadow systems. A platform that allows every exception without review may look flexible, but it loses standardization and auditability. A mature platform supports exceptions deliberately, learns from them, and turns repeated exceptions into new supported paths when the pattern is common enough.

### 5. Self-Service Must Include Guardrails, Not Just Automation

Self-service means [developers can request or change platform capabilities without waiting for a manual platform ticket for every routine action](https://tag-app-delivery.cncf.io/whitepapers/platforms/). It does not mean developers bypass governance. Mature self-service combines automation, policy, identity, quotas, auditability, and recovery. The goal is to make safe actions fast and unsafe actions clear, explainable, and remediable.

This is one of the most common CNPA traps. A question may describe self-service as "developers can provision anything they want without review." That is not mature platform engineering. Another question may describe governance as "all requests must be manually approved by operations." That is not mature self-service. The stronger answer is usually automated self-service with guardrails that encode policy close to the workflow.

A useful way to evaluate self-service is to ask what happens before, during, and after the request. Before the request, the developer should know which options are supported and what each option costs or implies. During the request, automation should validate policy and apply defaults. After the request, the platform should record ownership, expose observability, support rollback or cleanup, and make the action auditable.

```ascii
+------------------+      +------------------+      +------------------+
| Before request   | ---> | During request   | ---> | After request    |
+------------------+      +------------------+      +------------------+
| supported options|      | identity check   |      | ownership record |
| clear defaults   |      | policy validation|      | audit trail      |
| cost visibility  |      | quota enforcement|      | observability    |
| docs and examples|      | automated action |      | cleanup path     |
+------------------+      +------------------+      +------------------+
```

Guardrails should be designed as product features, not as surprise barriers. A policy error that says "denied" teaches little. A better policy error says which requirement failed, why the rule exists, and what the developer can change. The platform team should treat repeated policy failures as feedback. Maybe the documentation is unclear, the template is out of date, or the policy is enforcing a rule that no longer matches reality.

Here is a small runnable example that demonstrates the difference between a vague rule and a useful guardrail. It does not require a Kubernetes cluster because it validates local YAML text. The point is not to build a complete policy engine; the point is to see what helpful feedback looks like.

```bash
mkdir -p cnpa-core-review
cat > cnpa-core-review/deployment.yaml <<'YAML'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
    owner: payments-team
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payments-api
  template:
    metadata:
      labels:
        app: payments-api
        owner: payments-team
    spec:
      containers:
        - name: payments-api
          image: nginx:1.27
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
YAML

grep -q 'owner: payments-team' cnpa-core-review/deployment.yaml && \
grep -q 'requests:' cnpa-core-review/deployment.yaml && \
grep -q 'limits:' cnpa-core-review/deployment.yaml && \
echo "guardrail check passed: ownership and resource limits are present"
```

A real platform would use Kubernetes admission control, Open Policy Agent, Kyverno, CI checks, or another policy system rather than `grep`. The teaching point still holds. A useful guardrail checks for known risk before deployment, gives feedback early, and helps the developer fix the issue. It is not merely a wall at the end of the release process.

> **Stop and think:** If developers keep failing the same policy check, what should the platform team investigate first: developer discipline, unclear docs, a broken template, or a rule that does not match real workloads? A senior answer considers all four before blaming users.

Self-service also has limits. Highly regulated actions, production data access, emergency break-glass changes, and expensive infrastructure may require extra review. The platform maturity question is whether those reviews are deliberate, auditable, and proportional to risk. Manual review is not automatically bad. Manual review becomes a platform failure when it is the default path for routine work that could be safely automated.

| Self-service pattern | Mature signal | Risk if missing |
|---|---|---|
| Service creation | Template creates runnable service with ownership and pipeline defaults | Teams copy stale examples and miss required metadata |
| Environment request | Policy validates quota, naming, cost tags, and access | Manual queue grows and teams create unofficial environments |
| Secret access | Identity and approval are tied to role and audit trail | Credentials spread through chat, tickets, or local files |
| Deployment | Pipeline applies checks, rollback guidance, and evidence | Releases depend on tribal knowledge and manual commands |
| Observability | Logs, metrics, traces, and alerts are attached by default | Teams discover missing signals during incidents |
| Cleanup | Decommission path removes unused resources safely | Costs and risk accumulate after services are abandoned |

The senior-level nuance is that self-service is not only about speed. It also improves consistency, auditability, and learning. When the platform encodes a safe workflow, every successful request produces evidence about how the organization operates. When the workflow fails, the failure produces feedback about where the platform needs improvement. Ticket queues hide that learning inside individual conversations.

### 6. Platform As A Product Means Adoption Is Earned

"Platform as a product" is not a slogan. It changes how the platform team chooses work, measures success, and handles feedback. A product team does not simply ship features because they are technically interesting. It [understands users, prioritizes problems, validates assumptions, measures adoption, and iterates](https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/). Platform teams need the same discipline because their users are internal developers with real delivery pressure.

A platform product has a value proposition. For example, "Create a production-ready HTTP service in one hour with built-in deployment, ownership metadata, and observability." That promise is specific enough to test. If developers still need several days of platform support, the promise is not yet true. If the generated service lacks alerts, the promise is incomplete. If only one team uses the workflow because everyone else finds it too rigid, adoption data is telling the platform team something important.

The platform product also has a support model. Internal users need to know where to ask questions, how incidents are handled, which capabilities are stable, and how breaking changes are communicated. A platform without support may look efficient in architecture diagrams but expensive in practice. Developers will interrupt individual platform engineers, create workarounds, and lose trust when changes surprise them.

```ascii
+----------------------+      +----------------------+      +----------------------+
| Product discovery    | ---> | Product delivery     | ---> | Product learning     |
+----------------------+      +----------------------+      +----------------------+
| user interviews      |      | templates and APIs   |      | adoption metrics     |
| journey mapping      |      | docs and workflows   |      | support tickets      |
| pain-point analysis  |      | policies and defaults|      | incident patterns    |
| priority decisions   |      | release management   |      | roadmap adjustments  |
+----------------------+      +----------------------+      +----------------------+
```

Adoption is a core platform metric, but it must be interpreted carefully. Forced adoption may make a dashboard look good while increasing frustration. Voluntary adoption is stronger evidence that the path is useful, but some safety requirements may still be mandatory. The senior view is to separate adoption of product value from compliance with minimum standards. Teams should want the golden path because it helps them, while the organization may still require certain guardrails for risk control.

Good platform metrics combine delivery, reliability, usability, and operational load. Lead time for a new service, time to first deployment, percentage of workloads with ownership metadata, number of support tickets per capability, policy failure reasons, incident frequency, and developer satisfaction can all be useful. No single metric proves maturity. A platform team needs a small set of measures that reveal whether users are becoming more effective.

| Metric | What it can reveal | Bad interpretation to avoid |
|---|---|---|
| Time to first deploy | Whether service creation and deployment are actually fast | Assuming speed matters even if the result is unsafe or unsupported |
| Golden path adoption | Whether teams find the supported path useful | Treating forced usage as proof of good developer experience |
| Support ticket volume | Where workflows create confusion or missing capability | Blaming developers instead of improving the platform product |
| Policy failure reasons | Which guardrails need clearer remediation or better defaults | Hiding failures because they make the platform look strict |
| Incident patterns | Which defaults or docs fail under real operations | Treating every incident as only an application-team problem |
| Developer satisfaction | Whether users trust and understand the platform | Optimizing happiness while ignoring reliability and governance |

The platform product mindset also changes prioritization. A platform team should not build every requested feature immediately. It should look for repeated problems, high-risk workflows, and improvements that unlock many teams. One-off requests may become escape hatches or consulting work, but repeated one-off requests are a signal that a new product capability may be needed. Senior platform work is often deciding what not to standardize yet.

> **Active check:** A platform team receives many requests for custom CI steps. Some requests are genuinely different, but many are small variations of the same security scan. What would you standardize, what would you leave configurable, and what metric would tell you whether the change helped?

### 7. GitOps And Infrastructure As Code Are Enablers, Not The Whole Platform

GitOps and Infrastructure as Code often appear in platform engineering discussions because they support repeatability, reviewability, and automation. [Infrastructure as Code describes managing infrastructure definitions as versioned code rather than manual console changes](https://www.hashicorp.com/en/resources/what-is-infrastructure-as-code). [GitOps uses Git as the desired-state source and relies on automated reconciliation to apply changes to environments](https://raw.githubusercontent.com/open-gitops/documents/main/PRINCIPLES.md). Both can be powerful platform building blocks, but neither is the same thing as platform engineering.

The exam may try to make a tool or practice sound like the whole discipline. "The company uses Terraform, so it has a platform" is not enough. "The company uses GitOps, so developers have self-service" is also not enough. IaC and GitOps can enable self-service if they are wrapped in usable workflows, policy, ownership, and support. Without those pieces, they may simply move manual complexity into pull requests.

A mature platform may use IaC to define cloud resources, GitOps to apply Kubernetes manifests, policy engines to validate changes, and a portal or CLI to guide users through requests. The developer experience should hide unnecessary internal wiring while preserving enough transparency for troubleshooting. Senior practitioners are comfortable with that layering: the platform product is the user-facing workflow, while IaC and GitOps are implementation mechanisms.

```ascii
+----------------------+      +----------------------+      +----------------------+
| Developer action     | ---> | Platform workflow    | ---> | Automation mechanism |
+----------------------+      +----------------------+      +----------------------+
| Request environment  |      | validate and approve |      | IaC plan and apply   |
| Deploy application   |      | pipeline and policy  |      | GitOps reconciliation|
| Change configuration |      | review and audit     |      | versioned manifests  |
| Diagnose issue       |      | surface signals      |      | logs, metrics, traces|
+----------------------+      +----------------------+      +----------------------+
```

The implementation details matter, but the CNPA core domain usually rewards reasoning about outcomes. If GitOps gives teams a clear review path, rollback history, drift correction, and visible deployment state, it supports platform goals. If it forces every developer to learn a complex repository layout with unclear ownership and cryptic failure messages, it may increase cognitive load. A platform team should wrap the mechanism in a workflow that fits its users.

Here is a small example of how a platform might represent a supported service deployment. The YAML is ordinary Kubernetes configuration, but the platform value comes from the defaults: ownership labels, resource requests, probes, and a predictable shape that automation can validate.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  labels:
    app.kubernetes.io/name: orders-api
    app.kubernetes.io/part-of: commerce
    platform.kubedojo.io/owner: orders-team
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: orders-api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: orders-api
        platform.kubedojo.io/owner: orders-team
    spec:
      containers:
        - name: orders-api
          image: nginx:1.27
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /
              port: 8080
          livenessProbe:
            httpGet:
              path: /
              port: 8080
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```

If you use `kubectl` often, many Kubernetes learners create a short interactive alias after they understand that it is only a local shell shortcut. Training material and platform documentation should still use the full command because learners copy examples into scripts, CI jobs, and runbooks where aliases may not expand. In a real cluster, a developer could validate the manifest locally before sending it through the platform workflow. The following command [performs a client-side dry run and does not change cluster state](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/).

```bash
kubectl apply --dry-run=client -f orders-api.yaml
```

The YAML alone is not a golden path. It becomes part of a golden path when the platform maintains it, documents the intended use, validates important fields, connects it to delivery automation, and helps teams troubleshoot failures. The same is true for Terraform modules, Helm charts, Crossplane compositions, Backstage templates, or any other platform artifact. The artifact is a means to an outcome.

### 8. Worked Example: Evaluating A Platform Decision

Consider this scenario. A growing company has twenty product teams. Each team provisions Kubernetes namespaces by opening a ticket with the operations team. The ticket asks for namespace name, owner, environment, quota, network access, and cost center. Tickets wait several days because operations manually checks naming rules, creates the namespace, applies ResourceQuota, grants RBAC, and sends a message when finished. Developers complain that the queue slows experiments, while operations complains that many tickets are incomplete.

A weak response is to build a portal form that sends the same ticket with a nicer interface. That may improve discoverability slightly, but it does not remove the bottleneck. Another weak response is to let every developer create namespaces directly with cluster-admin permissions. That improves speed but removes governance. A platform-engineering response turns the repeated namespace request into a [self-service workflow with policy, defaults, audit, and support](https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/).

Step one is to identify the repeated decision points. Namespace name, owner, environment, quota, network access, and cost center are not random. They are governance inputs. Step two is to encode the easy checks: required fields, allowed environments, naming convention, default quota sizes, and ownership metadata. Step three is to automate the standard path while routing unusual requests through a visible exception process. Step four is to measure whether lead time falls, ticket quality improves, and support questions decrease.

```ascii
+---------------------------+       +---------------------------+
| Current ticket process    |       | Platform self-service path |
+---------------------------+       +---------------------------+
| Developer fills ticket    |       | Developer selects template |
| Operations checks fields  |       | Workflow validates fields  |
| Operations creates object |       | Automation creates object  |
| Operations applies quota  |       | Defaults apply quota       |
| Operations sends message  |       | Status is visible          |
| Audit is scattered        |       | Audit is recorded          |
+---------------------------+       +---------------------------+
```

The senior-level trade-off is exception handling. Some namespaces may need unusual quota, special network access, or production data controls. The platform should not pretend those needs do not exist. Instead, it should make the standard path fast and the exception path explicit. If many teams request the same exception, the platform team should consider making that exception a supported variant.

| Decision | Recommended platform response | Reasoning |
|---|---|---|
| Standard development namespace | Fully automated self-service | Low risk and repeated often, so manual review adds little value |
| Production namespace with normal controls | Automated workflow with stronger policy and required ownership | The workflow is still repeated, but the risk requires tighter validation |
| Namespace requiring unusual network access | Exception workflow with review and audit | The request may be valid, but it changes the risk profile |
| Missing owner metadata | Block with clear remediation | Ownership is necessary for incidents, cost, and lifecycle management |
| Repeated custom quota requests | Investigate as a possible new supported tier | Repetition suggests the platform defaults may not fit real demand |

Now connect the example to the CNPA exam. The best answer would not say "buy a portal" or "remove operations from the process." It would say to provide self-service namespace provisioning through an internal developer platform, encode guardrails for policy and ownership, keep an auditable exception path, and measure adoption plus lead time. That answer applies platform-as-product thinking, self-service with governance, and developer experience improvement in one coherent response.

### 9. Senior Review Model For CNPA Questions

CNPA multiple-choice questions often include answers that sound partly correct. The strongest strategy is to evaluate the scenario through a small review model. Ask what problem is being solved, who the platform user is, whether the proposed solution reduces cognitive load, whether governance is encoded as guardrails, and how success would be measured. This turns memorized definitions into applied reasoning.

The review model also helps when terms overlap. If the scenario is mostly about SLOs, incident learning, and error budgets, the answer likely leans toward SRE. If it is about developers creating services through templates and self-service workflows, the answer likely leans toward platform engineering. If it is about culture, shared ownership, and reducing handoffs between development and operations, the answer likely leans toward DevOps. When the scenario mixes them, choose the answer that addresses the main failure described.

```ascii
+--------------------------------------------------------------------------------+
|                         CNPA Core Decision Checklist                            |
+--------------------------------------------------------------------------------+
| 1. What repeated developer workflow is painful or risky?                         |
| 2. Does the solution reduce cognitive load or just rename the handoff?           |
| 3. Are guardrails automated, explainable, and close to the workflow?             |
| 4. Can developers complete routine work without waiting for manual tickets?      |
| 5. Is there an exception path for real edge cases without hiding risk?           |
| 6. Are adoption, reliability, lead time, and support load measured?              |
+--------------------------------------------------------------------------------+
```

Use this checklist to eliminate shallow answers. If an answer focuses only on tools, ask what workflow the tool improves. If an answer focuses only on speed, ask what controls prevent unsafe outcomes. If an answer focuses only on governance, ask whether developers can still move without unnecessary delay. If an answer focuses only on ownership, ask whether the platform provides enough support for teams to succeed.

A senior platform thinker also watches for local optimization. A security team may optimize for blocking risk, an operations team may optimize for stability, and a product team may optimize for speed. Platform engineering tries to create workflows where these goals reinforce each other. A golden path with built-in policy, deployment evidence, and observability can make secure delivery faster rather than slower. That is why platform engineering is an organizational capability, not just a toolchain.

| Exam phrase | What to test before choosing it | Better reasoning habit |
|---|---|---|
| "Single pane of glass" | Does it perform work or only display links? | Prefer capabilities over dashboards. |
| "Developer autonomy" | Are guardrails and accountability still present? | Autonomy is not the absence of governance. |
| "Standardization" | Does it reduce repeated complexity or block valid differences? | Standardize the common path, govern exceptions. |
| "Self-service" | Can routine work complete without manual handoff? | Automation must include policy, audit, and support. |
| "Platform adoption" | Is adoption earned by value or forced by mandate? | Use adoption data together with satisfaction and outcomes. |
| "Shift left" | Does earlier feedback actually help developers remediate? | Earlier blocking without guidance is just earlier frustration. |

By the end of this review, you should be able to read a platform scenario and identify the missing product mechanism. Maybe the missing piece is feedback from developers. Maybe it is a guardrail that explains remediation. Maybe it is an escape hatch for unusual workloads. Maybe it is a metric that proves the platform improves delivery. The CNPA exam rewards that applied judgment more than memorized slogans.

## Recommended KubeDojo Review Map

Use this review map when you need to strengthen a weak area before the exam. The CNPA core domain connects directly to the broader platform engineering track, so these modules are not just background reading. They provide the deeper theory behind the decision-making patterns used in scenario questions.

- [What is Platform Engineering?](../../../platform/disciplines/core-platform/platform-engineering/module-2.1-what-is-platform-engineering/)
- [Developer Experience](../../../platform/disciplines/core-platform/platform-engineering/module-2.2-developer-experience/)
- [Internal Developer Platforms](../../../platform/disciplines/core-platform/platform-engineering/module-2.3-internal-developer-platforms/)
- [Golden Paths](../../../platform/disciplines/core-platform/platform-engineering/module-2.4-golden-paths/)
- [Self-Service Infrastructure](../../../platform/disciplines/core-platform/platform-engineering/module-2.5-self-service-infrastructure/)
- [Platform Maturity](../../../platform/disciplines/core-platform/platform-engineering/module-2.6-platform-maturity/)
- [What is GitOps?](../../../platform/disciplines/delivery-automation/gitops/module-3.1-what-is-gitops/)
- [IaC Fundamentals](../../../platform/disciplines/delivery-automation/iac/module-6.1-iac-fundamentals/)
- [What is Observability?](../../../platform/foundations/observability-theory/module-3.1-what-is-observability/)
- [Incident Management](../../../platform/disciplines/core-platform/sre/module-1.5-incident-management/)

## Patterns & Anti-Patterns

The most useful CNPA review habit is to translate every platform claim into a pattern or an anti-pattern. A pattern is not just something that sounds modern; it is a repeatable way of arranging ownership, workflow, automation, and feedback so teams can deliver safely with less unnecessary effort. An anti-pattern is often the same vocabulary used without the operating discipline behind it. A portal can be either a discovery pattern or a ticket-queue anti-pattern depending on what happens after the developer clicks a button.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---|---|---|---|
| Productized golden path | Many teams create similar services, environments, or delivery pipelines. | It turns repeated expert work into supported defaults that developers can trust. | Version templates, publish migration guidance, and measure adoption by workflow outcome rather than mandate. |
| Policy-backed self-service | Routine requests need governance but not human review every time. | It makes safe actions fast while preserving ownership, audit, quotas, and remediation. | Keep policies close to the workflow and treat repeated failures as product feedback. |
| Service catalog with ownership | Teams need to find services, owners, runbooks, and operational signals quickly. | It connects discovery to accountability, incident response, and lifecycle management. | Automate ownership updates where possible because stale catalog data creates false confidence. |
| Observability by default | New workloads repeatedly launch without useful logs, metrics, traces, or health checks. | It prevents teams from discovering missing signals during incidents. | Standardize baseline signals while allowing workload-specific SLOs and dashboards. |

The productized golden path pattern is strongest when the platform team maintains the path as a living product artifact. That means the template has a release process, ownership, documentation, known compatibility expectations, and a way to tell consuming teams what changed. A template that was copied once and never updated becomes a source of drift. A maintained path can absorb lessons from incidents, security findings, support tickets, and user interviews, which is how the platform improves without asking every application team to rediscover the same lesson.

Policy-backed self-service works because it moves governance from a late human checkpoint into the normal development workflow. The key word is backed, not replaced. A mature workflow still has identity, auditability, limits, approval rules for risky actions, and a clear exception path. The platform team is not surrendering control; it is encoding the routine parts of control so reviewers spend their attention on genuinely unusual risk. That is a better use of expertise than repeatedly checking whether an owner field was filled in.

The service catalog pattern is easy to underestimate because catalog pages can look like simple directories. In platform engineering, the catalog becomes more valuable when it ties ownership data to deployments, SLOs, documentation, cost metadata, and incident context. During a service problem, an accurate catalog can answer who owns the workload, where its dashboards are, which dependencies matter, and how to escalate. During normal delivery, it helps developers discover examples and supported capabilities without wandering through chat history or stale wiki pages.

| Anti-Pattern | What Goes Wrong | Why Teams Fall Into It | Better Alternative |
|---|---|---|---|
| Portal as a painted ticket queue | Developers still wait for manual handoffs, so lead time barely changes. | A UI is easier to launch than workflow automation and policy integration. | Start with one high-volume workflow and automate the standard path end to end. |
| Guardrails as unexplained blockers | Teams see policy as arbitrary and route around the official path. | Rules are implemented from a control perspective without developer feedback. | Return actionable errors, include compliant defaults, and publish remediation examples. |
| Mandatory adoption before product fit | Dashboards show usage while developer trust declines. | Leaders want visible standardization before the platform has earned confidence. | Improve the workflow, measure friction, and mandate only minimum risk controls. |
| Platform team as the new operations queue | The team becomes responsible for every routine request and every exception. | Central expertise feels safer than exposing self-service early. | Automate low-risk repeatable work and reserve human review for high-risk exceptions. |

These anti-patterns are attractive because they initially look controlled. A painted ticket queue can be demonstrated in a meeting, unexplained blockers can reduce certain classes of risk, mandatory adoption can produce tidy reporting, and centralized operations can feel orderly. The cost appears later as shadow workflows, support overload, long lead times, and brittle ownership. The CNPA exam often asks you to spot that delayed cost, so do not stop at whether the organization has the right nouns.

Hypothetical scenario: a platform team launches a portal page for Kubernetes namespace requests, but the portal only writes a ticket into the old operations queue. The team announces that self-service exists because developers no longer email operations directly. A stronger analysis says discovery improved, but self-service did not. The better next move is to automate the normal namespace path with required metadata, ResourceQuota defaults, RBAC binding through approved roles, audit logging, and an exception route for unusual network access.

Patterns and anti-patterns can coexist in the same system. An organization may have an excellent service template but weak policy feedback, or a useful catalog with stale ownership data. That is why platform maturity should be evaluated workflow by workflow rather than declared for the whole organization at once. For CNPA questions, identify the specific workflow under stress, name the missing mechanism, and choose the answer that improves developer outcomes while preserving accountability.

## Decision Framework

Use this framework when a CNPA scenario asks what a platform team should do next. Start with the workflow, not the tool. Then decide whether the work is repeated enough to standardize, risky enough to guard, varied enough to need an escape hatch, and important enough to measure. This sequence prevents two common mistakes: building automation for a workflow nobody needs, and blocking a routine workflow with human review because policy was never encoded.

```ascii
+-------------------------------+
| Start with one painful workflow|
+---------------+---------------+
                |
                v
+-------------------------------+
| Is it repeated across teams?   |
+---------------+---------------+
        | yes                    | no
        v                        v
+----------------------+   +---------------------------+
| Standardize defaults |   | Document or consult first |
+----------+-----------+   +---------------------------+
           |
           v
+-------------------------------+
| Can routine risk be encoded?   |
+---------------+---------------+
        | yes                    | no
        v                        v
+----------------------+   +---------------------------+
| Add policy guardrails|   | Keep reviewed exception   |
+----------+-----------+   +---------------------------+
           |
           v
+-------------------------------+
| Measure adoption, lead time,   |
| support load, and reliability  |
+-------------------------------+
```

The first decision is repetition. If only one team has a specialized workload, the platform team may help that team directly or document a supported exception, but it should be cautious about turning that case into a universal standard. Standardizing too early can create a path that fits nobody well. If five or more teams ask for similar namespace provisioning, service scaffolding, deployment evidence, or observability defaults, the repeated pattern is a good candidate for platform product work because the same improvement can remove duplicated effort across many teams.

The second decision is risk. Low-risk, high-volume requests are usually the best candidates for automated self-service because manual review adds delay without much judgment. High-risk requests may still use a platform workflow, but the workflow should include stronger checks, required evidence, or human approval. The senior move is not to treat "manual" as always bad or "automated" as always mature. The mature move is to match the control to the risk and make the routine part predictable.

The third decision is whether the platform should expose implementation detail. Kubernetes 1.35 workloads still need concrete runtime objects, resources, probes, labels, and policies, but most developers should not have to rediscover every low-level decision for every service. A good platform surface lets developers choose meaningful options such as environment, ownership, service type, dependency class, and reliability target. It hides boilerplate while leaving enough transparency that teams can debug failures and understand operational consequences.

| Scenario Clue | Decision Question | Strong Platform Response |
|---|---|---|
| Developers wait days for a routine resource request. | Can the standard path be automated with policy and audit? | Build self-service for the common case and route unusual requests through an explicit exception path. |
| Teams bypass the template after repeated failures. | Is the golden path actually usable and supported? | Fix defaults, validation, docs, and observability before treating bypass behavior as only a compliance issue. |
| Security blocks deployments late in the pipeline. | Could feedback move earlier with remediation guidance? | Shift policy checks close to authoring and return clear messages that explain what to change. |
| A portal links to docs but cannot provision anything. | Is this discovery, capability, or both? | Keep the portal as a front door, but prioritize workflow automation behind the highest-volume entry points. |
| Leadership tracks only features shipped. | Which user outcomes changed? | Measure time to first deploy, adoption quality, support reasons, reliability signals, and developer satisfaction. |
| A team needs a real exception. | Is the need unique, repeated, or risky? | Review and audit the exception, then promote repeated exceptions into supported variants when justified. |

Pause and predict: if the platform team automates namespace creation but does not attach ownership metadata, what breaks first during cost review or incident response? The answer is usually not the namespace creation itself. The breakage appears when nobody can identify the responsible team, clean up abandoned resources, or route an alert to the right owner. This is why self-service has to include lifecycle data, not just provisioning speed.

The final decision is measurement. A platform team needs enough metrics to learn whether the workflow improved, but not so many that reporting becomes the product. Time to first deploy can reveal whether a golden path really accelerates service creation. Policy failure reasons can reveal whether guardrails teach or confuse. Support ticket themes can reveal where documentation, templates, or automation are incomplete. Reliability and incident patterns can reveal whether defaults work in production rather than only in demos.

Before running a platform improvement, write the expected behavior in one sentence. For example: "A developer can create a development namespace with ownership metadata, quota, default network policy, audit trail, and visible status in less than one working hour without opening a manual operations ticket." That sentence is testable. It also keeps the team honest because a portal form, a wiki page, or a Terraform module alone cannot satisfy the whole promise unless the surrounding workflow works.

When you answer CNPA questions, use the framework as a filtering tool. Reject answers that substitute tool adoption for workflow improvement. Reject answers that maximize autonomy while ignoring governance. Reject answers that maximize control while preserving unnecessary handoffs. Prefer answers that reduce repeated cognitive load, encode proportional guardrails, preserve team accountability, expose operational signals, and measure whether developers actually become more effective.

## Did You Know?

- **Fact 1**: Many successful platforms begin by improving one painful workflow, such as service creation or environment requests, before expanding into a full developer platform.
- **Fact 2**: A developer portal can improve discovery, but it becomes strategically valuable only when connected to maintained workflows, ownership data, and operational signals.
- **Fact 3**: Guardrails are most effective when they run close to the developer's normal workflow, because late feedback creates rework and encourages bypass behavior.
- **Fact 4**: Platform teams often measure both product metrics and operational metrics because adoption without reliability, or reliability without usability, gives an incomplete picture.

## Common Mistakes

| Mistake | Why it is wrong | Better answer |
|---|---|---|
| Treating platform engineering as a tool choice | The exam tests the operating model and product discipline, not just whether a tool exists. | Start with the developer workflow, the platform capability, and the outcome being improved. |
| Confusing a developer portal with the whole platform | A portal may be the front door, but the platform includes workflows, automation, policies, docs, and support. | Describe the abstraction boundary and the capabilities behind the interface. |
| Thinking self-service removes governance | Mature self-service includes policy, identity, quotas, auditability, and recovery paths. | Pair self-service with automated guardrails and clear remediation. |
| Assuming adoption is optional or automatic | A platform no one trusts or uses does not reduce organizational complexity. | Treat adoption, satisfaction, and workflow outcomes as core success signals. |
| Describing golden paths as rigid mandates | Overly rigid paths can create shadow systems and local workarounds. | Present golden paths as recommended, supported workflows with governed escape hatches. |
| Collapsing DevOps, SRE, and platform engineering into one label | The practices overlap but have different centers of gravity and exam implications. | Compare the scenario's main focus: collaboration, reliability, or internal product capability. |
| Measuring success by features shipped only | A platform can ship many features while developer lead time and support burden get worse. | Use outcome metrics such as time to first deploy, ticket reduction, reliability, and adoption quality. |
| Moving manual tickets into Git without improving the workflow | Version control improves review and audit, but it may not reduce cognitive load by itself. | Wrap GitOps or IaC in usable workflows, policy feedback, documentation, and support. |

## Quiz

1. **Your organization launches a developer portal that lists service templates, runbooks, dashboards, and request forms. Developers still wait several days for environment provisioning because each request is manually handled by operations. Which platform maturity gap should you identify first?**

   <details>
   <summary>Answer</summary>

   The main gap is that the portal improves discovery but does not yet provide real self-service capability. A stronger platform approach would automate routine environment provisioning with policy validation, ownership metadata, quotas, auditability, and visible status. The best CNPA answer should avoid saying the portal is useless; it has value as a front door. The issue is that the workflow behind the front door still behaves like a manual ticket queue.

   </details>

2. **A team argues that platform engineering means developers should never touch infrastructure because the platform team should operate everything. Another team argues that DevOps means every application team should manage all infrastructure details itself. How should you evaluate both claims?**

   <details>
   <summary>Answer</summary>

   Both claims are too extreme. Platform engineering reduces repeated complexity by providing supported internal products, but it should not remove all ownership from application teams. DevOps encourages shared ownership and reduced silos, but it does not require every team to master every low-level infrastructure detail. A mature answer balances autonomy and support: the platform provides paved roads and guardrails, while service teams remain accountable for how their workloads behave.

   </details>

3. **Developers frequently bypass the official service template because it lacks required observability defaults and produces deployment failures that are hard to diagnose. The platform team wants to mandate the template anyway to increase adoption. What should you recommend?**

   <details>
   <summary>Answer</summary>

   The platform team should improve the golden path before treating low adoption as a compliance problem. The bypass behavior is feedback that the template does not yet solve the developer workflow well enough. The team should add observability defaults, improve validation and error messages, test the generated service path, and measure whether adoption improves because the path becomes useful. Mandating a broken path may increase apparent usage while reducing trust.

   </details>

4. **A security policy blocks deployments missing owner labels, but the error message only says "denied." Teams repeatedly ask platform engineers what went wrong. What platform product improvement best addresses the situation?**

   <details>
   <summary>Answer</summary>

   The guardrail should provide actionable remediation close to the workflow. A better policy failure would state that the owner label is missing, explain why ownership is required for incidents and lifecycle management, and show the expected label format. The platform team should also update templates so compliant metadata is included by default. This reduces support load while keeping the governance requirement intact.

   </details>

5. **A company uses GitOps for all Kubernetes deployments. Developers submit pull requests to change manifests, but the repository structure is difficult to understand and failed reconciliations produce unclear messages. Which CNPA conclusion is strongest?**

   <details>
   <summary>Answer</summary>

   GitOps is a useful enabling mechanism, but it does not automatically create a mature platform experience. The workflow may be reviewable and auditable, but it may still impose high cognitive load on developers. The platform team should improve the user-facing workflow through clearer templates, documentation, policy feedback, ownership mapping, and observability of reconciliation status. The best answer evaluates the developer outcome rather than assuming GitOps equals platform maturity.

   </details>

6. **A product team needs a nonstandard database configuration that the golden path does not support. The platform team can either reject the request, allow a completely unmanaged exception, or create a reviewed exception with audit and follow-up. Which option best fits mature platform engineering?**

   <details>
   <summary>Answer</summary>

   A reviewed and auditable exception is usually the strongest option. Mature golden paths should support legitimate variation without allowing unmanaged risk. The platform team should evaluate whether the requirement is real, record the exception, define ownership and support expectations, and monitor whether similar requests repeat. If the pattern becomes common, it may deserve a new supported platform capability.

   </details>

7. **You need to diagnose common CNPA exam traps around guardrails, automation, platform maturity, and developer experience. Platform leadership reports success because twelve platform features shipped this quarter, but developer surveys still show confusion, time to first deployment has not improved, and support tickets increased. How should you evaluate the success claim?**

   <details>
   <summary>Answer</summary>

   The success claim is weak because feature output is not the same as platform outcome. This is a common CNPA exam trap: guardrails, automation, and platform maturity should be diagnosed through developer experience and workflow evidence, not through the count of features shipped. Platform-as-product thinking measures whether users become more effective, not only whether the platform team shipped work. The team should examine time to first deploy, adoption quality, support ticket reasons, developer satisfaction, reliability impact, and whether workflows reduce cognitive load. The likely conclusion is that the roadmap needs product discovery and workflow improvement, not just more features.

   </details>

## Hands-On Exercise

**Task**: Evaluate and improve a simple platform workflow design for service creation. You will create a local review artifact, identify weak platform signals, propose a better golden path, and verify that your recommendation includes self-service, guardrails, observability, and adoption metrics.

**Scenario**: A company has a "new service" process that starts with a wiki page. Developers copy a repository manually, paste a CI file from another team, ask operations for a namespace, ask security for a secret pattern, and open a monitoring ticket after the first production incident. Leadership calls this a platform because a portal page links to all the instructions.

**Steps**:

1. Create a local workspace for the exercise.

   ```bash
   mkdir -p cnpa-core-review/exercise
   cd cnpa-core-review/exercise
   ```

2. Create a short description of the current workflow.

   ```bash
   cat > current-workflow.md <<'EOF'
   # Current new-service workflow

   Developers start from a wiki page.
   They manually copy an existing repository.
   They paste a CI file from another team.
   They open an operations ticket for a namespace.
   They ask security how secrets should be handled.
   They request monitoring only after the first production incident.
   EOF
   ```

3. Classify the weaknesses using the core platform concepts from this module.

   ```bash
   cat > platform-review.md <<'EOF'
   # Platform Review

   ## Workflow weaknesses

   - The portal is mainly a link collection, not a working self-service platform.
   - The service template is informal because developers copy another repository manually.
   - Guardrails arrive late because security guidance is requested after scaffolding.
   - Namespace provisioning is still a manual ticket instead of a policy-backed workflow.
   - Observability is reactive because monitoring is requested after an incident.
   - Adoption cannot be evaluated because there is no defined golden path metric.

   ## Improved golden path

   The platform should provide a maintained service template that includes ownership metadata,
   CI/CD defaults, resource guidance, secret integration instructions, and observability defaults.
   Namespace provisioning should be self-service with policy validation for owner, environment,
   quota, and cost center. The workflow should expose deployment status, policy feedback, logs,
   metrics, and support guidance from the first deployment.

   ## Success metrics

   - Time from service request to first successful deployment
   - Percentage of new services created from the maintained template
   - Number of manual tickets required per new service
   - Policy failure reasons and remediation completion rate
   - Percentage of services with owner metadata and observability defaults
   - Developer satisfaction with the new-service workflow
   EOF
   ```

4. Add a minimal Kubernetes manifest that represents a better platform default for a new service.

   ```bash
   cat > service-default.yaml <<'YAML'
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: catalog-api
     labels:
       app.kubernetes.io/name: catalog-api
       app.kubernetes.io/part-of: retail
       platform.kubedojo.io/owner: catalog-team
   spec:
     replicas: 2
     selector:
       matchLabels:
         app.kubernetes.io/name: catalog-api
     template:
       metadata:
         labels:
           app.kubernetes.io/name: catalog-api
           platform.kubedojo.io/owner: catalog-team
       spec:
         containers:
           - name: catalog-api
             image: nginx:1.27
             ports:
               - containerPort: 8080
             readinessProbe:
               httpGet:
                 path: /
                 port: 8080
             resources:
               requests:
                 cpu: "100m"
                 memory: "128Mi"
               limits:
                 cpu: "500m"
                 memory: "256Mi"
   YAML
   ```

5. Run simple local checks that model guardrail thinking.

   ```bash
   grep -q 'platform.kubedojo.io/owner: catalog-team' service-default.yaml
   grep -q 'readinessProbe:' service-default.yaml
   grep -q 'resources:' service-default.yaml
   grep -q 'Time from service request to first successful deployment' platform-review.md
   echo "exercise checks passed"
   ```

6. If you have `kubectl` available, validate the manifest client-side. The command uses the full binary name so it remains copy-paste safe in scripts, CI jobs, and shared runbooks.

   ```bash
   kubectl apply --dry-run=client -f service-default.yaml
   ```

**Success Criteria**:

- [ ] Your review distinguishes a portal from an internal developer platform capability.
- [ ] Your improved workflow includes self-service provisioning rather than a manual namespace ticket.
- [ ] Your recommendation includes guardrails for ownership, policy, quota, or cost visibility.
- [ ] Your recommendation includes observability defaults before the first production incident.
- [ ] Your success metrics measure outcomes, not only platform features shipped.
- [ ] Your manifest includes ownership metadata, a readiness probe, and resource requests or limits.
- [ ] Your final explanation connects the changes to reduced cognitive load and safer developer autonomy.

**Reflection Prompt**: If a reviewer challenged your design by saying "this is just more automation," explain why the product workflow matters. Your answer should mention the developer journey, supported defaults, policy feedback, operational visibility, and adoption metrics. A strong response shows that platform engineering is not automation for its own sake; it is the productization of repeated delivery capabilities.

## Sources

- https://kubernetes.io/docs/concepts/overview/
- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
- https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/
- https://opentelemetry.io/docs/concepts/
- https://opentelemetry.io/docs/concepts/signals/
- https://sre.google/sre-book/service-level-objectives/
- https://sre.google/workbook/error-budget-policy/
- https://tag-app-delivery.cncf.io/whitepapers/platforms/
- https://tag-app-delivery.cncf.io/wgs/platforms/maturity-model/readme/
- [tag-app-delivery.cncf.io: platforms](https://tag-app-delivery.cncf.io/whitepapers/platforms/) — The CNCF Platforms White Paper explicitly describes platforms as user-defined capability collections that reduce common work and cognitive load for internal users.
- [tag-app-delivery.cncf.io: glossary](https://tag-app-delivery.cncf.io/wgs/platforms/glossary/) — The CNCF Platforms glossary directly defines DevOps and explains platform engineering as a way to scale DevOps principles through a unified platform.
- [tag-app-delivery.cncf.io: platform eng maturity model](https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/) — The CNCF Platform Engineering Maturity Model explicitly contrasts manual custom processes with self-service solutions and names self-serve portals and golden-path templates as maturity signals.
- [raw.githubusercontent.com: PRINCIPLES.md](https://raw.githubusercontent.com/open-gitops/documents/main/PRINCIPLES.md) — The upstream OpenGitOps principles file states the four defining properties: declarative, versioned and immutable, pulled automatically, and continuously reconciled.
- [hashicorp.com: what is infrastructure as code](https://www.hashicorp.com/en/resources/what-is-infrastructure-as-code) — HashiCorp's IaC primer directly defines infrastructure as code in terms of configuration files replacing manual GUI or command-line processes and emphasizes versioning and repeatability.
- [kubernetes.io: kubectl apply](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/) — The official `kubectl apply` reference explicitly says client dry-run prints the object that would be sent without sending or persisting it.
- [CNCF CNPA Certification Page](https://www.cncf.io/training/certification/cnpa/) — This is the canonical public overview of the CNPA exam context that this review module is preparing learners for.

## Next Module

Continue with [CNPA Delivery, APIs, and Observability Review](../module-1.3-delivery-apis-and-observability-review/).
