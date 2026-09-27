---
title: "From Cluster Admin to Platform Engineer"
sidebar:
  order: 2
---

> **Complexity**: `[MEDIUM]` - Bridge module that reframes cluster administration skills as platform engineering responsibilities
>
> **Time to Complete**: 90-120 minutes, including the hands-on drift exercise
>
> **Prerequisites**: CKA, CKAD, or CKS-level cluster administration, or equivalent experience operating Kubernetes workloads with kubectl

This bridge is for learners who have CKA, CKAD, CKS, or equivalent cluster administration experience and want to move into platform engineering. It closes the gap between operating Kubernetes resources and designing an internal platform as a product with reliability goals, golden paths, GitOps discipline, service ownership, observability, and adoption mechanics. The page works as both a readiness check and a short course: the diagnostic and the sequenced path tell you where to go next, and the teaching sections cover the three ideas that most often trip up experienced administrators.

## Learning Outcomes

- Distinguish an SLI, an SLO, an SLA, and an error budget by purpose and consequence, then calculate an error budget from an SLO target and a measurement window.
- Evaluate whether a proposed golden path is a supported product path or a wiki page by checking ownership, encoded defaults, escape hatches, and adoption evidence.
- Diagnose configuration drift caused by manual cluster edits by tracing how GitOps reconciliation compares live state with the desired state stored in Git.
- Build a sequenced study plan from the diagnostic checklist that maps your existing cluster administration skills to platform engineering gaps.
- Apply service ownership and toil criteria to decide whether a recurring operational task should be automated, documented, delegated, or deleted.

## Why This Matters

A certified cluster administrator already knows how to make Kubernetes do things: schedule Pods, repair nodes, rotate certificates, debug a failing Service, and read events until the cause appears. Platform engineering keeps all of that knowledge but changes who the work is for. The customer is no longer the cluster itself. It is the group of developers and service teams who need to ship software safely without learning every detail you learned for the exam, and success becomes whether those teams can deliver, recover, and stay inside guardrails without filing a ticket.

That shift sounds like a job title change, but it changes the questions you ask every day. An administrator asks whether a Deployment rolled out successfully. A platform engineer asks whether the rollout path that many teams share is measurably reliable, whether it is the easiest path to use, and whether anyone can explain what happens when it fails. The skills you already have are the raw material, and what is usually missing is vocabulary and discipline around reliability targets, product thinking, and declarative change control.

Hypothetical scenario: A platform team runs a shared ingress controller that a GitOps tool manages from a repository. During a busy afternoon an experienced administrator notices a misconfigured timeout, runs kubectl edit against the live object, and confirms that errors stop. Shortly afterward the GitOps controller, which has self-healing enabled, reapplies the version stored in Git and the errors return. The administrator did nothing wrong by Kubernetes standards, yet the fix vanished because the source of truth had moved from the cluster to a repository, and nobody had written that rule down for the team.

The scenario captures the three ideas this bridge teaches. First, reliability needs shared language: an SLI, an SLO, an SLA, and an error budget are different instruments, and mixing them up leads to impossible promises or meaningless dashboards. Second, a golden path is a supported product path with an owner and a support model, not a wiki page that describes how someone once did it. Third, GitOps reconciliation is the mechanism that makes manual cluster edits drift, because once a controller continuously applies desired state from Git, any change made outside Git is reverted, overwritten later, or left as untracked state.

## Diagnostic — Are You Ready?

Work through the checklist honestly before choosing a starting point. Each item describes something a platform engineer does routinely, and each unchecked item maps to a destination in the skills-gap table and a step in the sequenced path below. Checking an item means you could do it tomorrow without looking up the terms, not that you have read about it once.

- [ ] You can write an SLO that is neither impossibly tight nor too vague to guide decisions.
- [ ] You can explain the difference between an SLI, an SLO, an SLA, and an error budget.
- [ ] You have shipped a Terraform module, Helm chart, template, or automation path that other people actually used.
- [ ] You know what a golden path is and how it differs from a tutorial or wiki page.
- [ ] You have measured developer cycle time, deployment frequency, lead time, or change failure rate.
- [ ] You have participated in an incident postmortem that identified system and process causes.
- [ ] You can explain GitOps reconciliation and why manual cluster changes create hidden drift.
- [ ] You can describe a service ownership model that includes on-call, documentation, escalation, and lifecycle expectations.
- [ ] You can distinguish platform features from platform products.
- [ ] You can explain why self-service without guardrails becomes operational debt.
- [ ] You can identify when a cluster problem is really an organizational boundary problem.
- [ ] You can say no to a platform feature when it does not improve reliability, delivery speed, compliance, or operability.

Score yourself by counting unchecked items rather than checked ones, because the gaps decide your route. If most unchecked items concern SLOs, error budgets, incident reviews, and ownership, start with reliability and SRE material even if you are eager to install tools. If most gaps concern golden paths, cycle time, and saying no to features, start with the platform engineering discipline. If the GitOps items are unchecked, do not skip ahead to Argo CD, because reconciliation is the concept that transfers between tools and the tool is easier to learn afterward.

## Skills Gap Map

The table pairs a strength you already have with the adjacent skill a platform role expects, then points to the part of KubeDojo that teaches it. Read it left to right as a translation guide. The left column is not a weakness to apologize for; it is the foundation that makes the middle column learnable in weeks rather than months, because you already understand the system the new skills operate on.

| What you have | What you need | Where to study it |
|---|---|---|
| Kubernetes object fluency | Systems thinking across teams, services, and feedback loops | [What is Systems Thinking?](/platform/foundations/systems-thinking/module-1.1-what-is-systems-thinking/) |
| Cluster troubleshooting | Reliability goals and error-budget decisions | [Reliability Engineering](/platform/foundations/reliability-engineering/) |
| Metrics and logs usage | Observability as a design discipline | [Observability Theory](/platform/foundations/observability-theory/) |
| Security controls | Security principles embedded in platform defaults | [Security Principles](/platform/foundations/security-principles/) |
| Resource administration | Service ownership and operational models | [SRE](/platform/disciplines/core-platform/sre/) |
| YAML delivery | GitOps reconciliation and drift control | [GitOps](/platform/disciplines/delivery-automation/gitops/) |
| One-off automation | Reusable golden paths and developer experience | [Platform Engineering](/platform/disciplines/core-platform/platform-engineering/) |
| Tool familiarity | Tool selection based on user journeys and platform constraints | [Platform Toolkits](/platform/toolkits/) |
| Access management | Secret and policy workflows teams can adopt | [Vault](/platform/toolkits/security-quality/security-tools/module-4.1-vault-eso/) |
| Application deployment | Internal developer portal patterns | [Backstage](/platform/toolkits/infrastructure-networking/platforms/module-7.1-backstage/) |

Notice that the tool rows come last. Vault and Backstage appear in the map because platform teams use tools like them, but each row pairs the tool with a workflow or pattern rather than with installation steps. A platform engineer is judged by whether teams adopt secret workflows, developer portals, and delivery paths, and the tool is only one part of that outcome. When you evaluate any similar tool later, ask which skill it depends on and which user problem it solves before you ask how to install it.

## Sequenced Path

The order below front-loads the concepts that make later tools meaningful. Each step states why it sits where it does, so you can adapt the sequence when your diagnostic shows you already own a step. Skipping a step is reasonable when you can answer the matching quiz questions on this page; skipping because a tool looks more exciting is the most common way to end up with an elaborate platform that nobody uses.

1. Start with [What is Systems Thinking?](/platform/foundations/systems-thinking/module-1.1-what-is-systems-thinking/).
   Why this step: platform work is about feedback loops, incentives, constraints, and service boundaries, not only cluster state.

2. Continue through [Reliability Engineering](/platform/foundations/reliability-engineering/).
   Why this step: SLOs, error budgets, and reliability tradeoffs are the language used to decide what the platform should optimize.

3. Study [Observability Theory](/platform/foundations/observability-theory/).
   Why this step: platform teams need to make failure modes visible to service teams without turning every user into an observability expert.

4. Move into [SRE](/platform/disciplines/core-platform/sre/).
   Why this step: SRE connects reliability targets, incident response, toil reduction, and operational ownership.

5. Read [Platform Engineering](/platform/disciplines/core-platform/platform-engineering/).
   Why this step: the platform becomes an internal product when it has users, adoption paths, feedback loops, and a support model.

6. Study [GitOps](/platform/disciplines/delivery-automation/gitops/).
   Why this step: reconciliation discipline turns Kubernetes operations into reviewable, repeatable, auditable system change.

7. Add [Argo CD](/platform/toolkits/cicd-delivery/gitops-deployments/module-2.1-argocd/) when you need implementation detail.
   Why this step: tools are easier to evaluate once you understand reconciliation, ownership, promotion, and rollback requirements.

8. Add [Backstage](/platform/toolkits/infrastructure-networking/platforms/module-7.1-backstage/) when you are ready to design developer entry points.
   Why this step: an internal developer portal is useful only when it reflects real service ownership and golden-path workflows.

9. Add [Vault](/platform/toolkits/security-quality/security-tools/module-4.1-vault-eso/) when secrets and identity become platform primitives.
   Why this step: platform teams must make secure defaults easier than unsafe workarounds.

Plan on revisiting early steps after later ones. Systems thinking reads differently once you have watched an error budget change a roadmap, and reliability engineering reads differently once you have seen a reconciler overwrite a manual fix. Treat the path as a spiral rather than a list you complete once, and use the hands-on exercise at the end of this page to build one small working artifact for each of the three core ideas before you start the first step.

## From Operating Objects to Operating a Product

Cluster administration is organized around objects and their states. You learn which controller owns which resource, how the scheduler places Pods, why a PersistentVolumeClaim stays Pending, and which kubectl command reveals the evidence. That object model is precise and testable, which is why certification exams can measure it in a timed lab. Platform engineering keeps the object model but adds a second layer above it: the people who consume the platform, the interfaces they use, and the feedback loops that tell you whether the platform is actually helping them.

The CNCF platforms white paper defines a platform for cloud native computing as an integrated collection of capabilities defined and presented according to the needs of the platform's users. Its first listed attribute is treating the platform as a product, followed by attributes such as user experience, self-service, reduced cognitive load, and secure defaults. That framing matters because products have users with choices. A project is finished when its tickets close, while a product succeeds only when people keep using it because it saves them effort they would otherwise spend.

```text
Cluster administration loop            Platform product loop
+-----------------------------+        +----------------------------------+
| 1. alert or ticket arrives  |        | 1. observe a developer journey   |
| 2. inspect live objects     |        | 2. measure where time is lost    |
| 3. fix the live state       |        | 3. design a capability or path   |
| 4. confirm the cluster is OK|        | 4. ship it as the default        |
+-----------------------------+        | 5. track adoption and SLOs       |
                                       +----------------------------------+
   unit of work: one object               unit of work: a class of problems
```

The practical consequence is that your unit of work grows. Instead of fixing one namespace quota, you design a namespace request flow that sets quotas, network policies, and ownership labels by default for every team that asks. Instead of debugging one failed rollout, you look at why rollouts fail across services and change the shared template, pipeline, or documentation so the whole class of failure becomes rarer. Your kubectl skills remain the way you verify that the platform works, but they stop being the main way you deliver value to anyone.

Systems thinking is the right first step for exactly this reason. A platform sits between many teams, and its behavior emerges from feedback loops, delays, and incentives as much as from YAML. When a developer bypasses the paved road, the useful question is not who broke the rule but what in the system made the bypass cheaper than the supported path. You already use that habit when a crash loop turns out to be a missing ConfigMap, and platform work asks you to apply it to people and processes as well as objects.

The CNCF platform engineering maturity model makes the same point from another direction. It assesses organizations across five aspects, namely investment, adoption, interfaces, operations, and measurement, and it describes four levels called provisional, operational, scalable, and optimizing. Adoption and measurement sit beside the technical aspects rather than after them, which is a useful reminder that a technically excellent platform with no adoption is still an immature platform by that model's standards.

## Reliability Language: SLI, SLO, SLA, and Error Budget

These four terms are often used interchangeably in meetings, which is exactly why they cause trouble. They answer different questions: what you measure, what you aim for internally, what you promise externally with consequences, and how much failure you can afford to spend. The Google SRE book defines the first three precisely, and the SRE workbook turns the fourth into an operating policy. Treat them as four separate instruments that work together rather than as four synonyms for uptime.

| Term | Question it answers | Typical owner | Example |
|---|---|---|---|
| SLI | What do we measure? | Service team, with platform-provided tooling | Successful deploy API requests divided by valid requests |
| SLO | What target do we aim for internally? | Service team and its stakeholders | 99.9% of valid requests succeed over a rolling 30 days |
| SLA | What do we promise externally, with consequences? | Business, legal, and service owner together | Service credits if monthly availability falls below a contractual threshold |
| Error budget | How much unreliability can we spend? | Service team, enforced by an agreed policy | 0.1% of valid requests in the window may fail |

### SLI: the measurement

An SLI is a carefully defined quantitative measure of some aspect of the level of service you provide. The SRE workbook recommends expressing it as the number of good events divided by the total number of events, which yields a value between zero and one hundred percent. Good events might be HTTP requests that return a non-error status within a latency threshold, deploy jobs that finish successfully, or namespace requests fulfilled without manual intervention. The definition must state where you measure, which events count, and what makes an event good.

Cluster administrators tend to start with resource signals such as CPU, memory, or node readiness, because those are what cluster dashboards show first. Those signals are useful for diagnosis, but they are poor SLIs because users do not experience CPU; they experience failed requests and slow pages. A strong SLI is measured as close to the user as practical, such as at the load balancer or in the client, and it moves when users would notice a change. Resource metrics then become the diagnostic layer you consult after an SLI tells you something is wrong.

### SLO: the internal target

An SLO is a target value or range of values for a service level that is measured by an SLI, always paired with a time window. A statement such as "99.9% of valid checkout requests succeed over a rolling 30-day window" is an SLO, while "the checkout service should be reliable" is only a wish. The window matters as much as the number, because a rolling window treats short spikes differently from a calendar month, and a very short window can turn every brief incident into an emergency.

Choosing the target is a product decision, not a purely technical one. The SRE book chapter on embracing risk argues that one hundred percent is the wrong reliability target for almost everything, partly because each extra nine costs more engineering effort and partly because users on imperfect phones and networks can't perceive the difference beyond a certain point. A useful SLO is tight enough that missing it means users are genuinely unhappy and loose enough that the team can still ship changes. If nobody would act differently when the SLO is missed, the target is decoration.

### SLA: the external promise

An SLA is an explicit or implicit contract with users that includes consequences of meeting or missing the SLOs it contains. Consequences are the defining feature, whether they take the form of service credits, refunds, penalties, or other contractual remedies. The SRE book offers a quick test, which is to ask what happens if the objective is missed. If there is no explicit consequence, you are almost certainly looking at an SLO, however formally someone wrote it down or however official the document looks.

For platform teams this distinction protects both sides of the relationship. Internal platforms rarely have contracts, so most platform promises are SLOs with an agreed response rather than SLAs. When an external SLA does exist, the internal SLO should normally be stricter than the contractual threshold, so the team receives a warning and has room to react before a breach triggers consequences. Copying the SLA number into the SLO removes that margin and guarantees that the first signal of trouble arrives as a contractual problem rather than an engineering one.

### Error budget: the permitted unreliability

The error budget is one minus the SLO, applied over the SLO's window. A 99.9% availability SLO over thirty days leaves 0.1% of that window as budget, and because thirty days contain 43,200 minutes, the budget is 43.2 minutes of full unavailability. Request-based SLOs use events instead of minutes: if the window contains two million valid requests and the SLO is 99.5%, the budget is ten thousand failed requests. Either way, the budget turns an abstract target into a quantity that teams can spend, save, and track.

The budget only changes behavior when it is paired with an error budget policy. The SRE workbook describes that policy as a documented agreement on the specific actions that must be taken when a service has consumed its entire budget for a period, and on who will take them. Typical actions include prioritizing reliability fixes over features, freezing risky changes until the service is back within its objective, and reviewing the incidents that consumed the most budget. Product, development, and SRE stakeholders agree to the policy in advance, which is what makes it enforceable when pressure arrives.

The budget also works in the other direction. If a service consistently ends each window with most of its budget unspent, the team may be moving too cautiously, or the SLO may be looser than users need. Either finding is useful, because the team can ship faster with more confidence or tighten the objective to match what users actually experience. That two-way property is what makes error budgets a shared decision tool between product and engineering rather than a punishment applied after outages.

> **Pause and predict:** A platform's deployment pipeline has an SLO of 99% successful runs over a 28-day window, and it has handled 4,000 valid runs so far this window. Sixty runs failed because of platform faults. Before reading on, predict how much budget remains and whether the error budget policy should slow down changes to the platform itself.

The budget so far is 1% of 4,000 runs, which is forty failed runs, so sixty platform-caused failures have already overspent it by twenty. More runs later in the window will enlarge the budget slightly, but not enough to erase the overspend unless the failure rate drops sharply. A sensible policy response is to pause risky pipeline changes and spend the next few days on the causes of those failures. Notice that you reached this conclusion with arithmetic and an agreed rule, not with an argument about whose fault the failures were.

### Platform SLOs versus service SLOs

A platform has its own users, so it needs its own SLOs, separate from the SLOs of the services that run on it. Useful platform SLIs measure the paths developers depend on: the success rate of the shared deployment pipeline, the time from a namespace request to a usable namespace, the availability of the internal developer portal, or the proportion of secret synchronizations that complete without error. Each one describes an experience a service team would notice, which keeps the platform team focused on outcomes rather than cluster tidiness.

The split also clarifies ownership during incidents. When a service misses its SLO because its own code regressed, the service team spends its budget and follows its own policy. When a service misses its SLO because the shared ingress path failed, the platform's budget for that capability is spent as well, and the platform's error budget policy decides what happens next. Without that separation, every incident turns into a debate about whose fault it was, and the budgets stop driving any decisions at all.

## Golden Paths Are Products, Not Wiki Pages

Spotify's engineering blog describes the Golden Path as the "opinionated and supported" path to build something, and it explains that engineers had previously discovered how to do things mostly by asking colleagues. Both adjectives in that definition carry weight. Opinionated means the path makes choices for the user, such as the language runtime, the pipeline, the logging format, and the security baseline. Supported means someone owns the path, keeps it working as the platform changes, and helps the people who follow it.

A wiki page can describe the same choices, but it doesn't make them for anyone. A page that says to add a list of annotations, create a ServiceMonitor, and remember the NetworkPolicy hands the cognitive load back to every reader, ages silently as the platform changes, and gives no signal when people stop following it. A golden path encodes those choices in something executable: a template that generates a working service, a pipeline that already runs the security scans, and defaults that emit metrics and ownership labels without extra effort from the developer.

| Property | Wiki page | Golden path |
|---|---|---|
| Form | Prose instructions to copy by hand | Template, pipeline, and defaults that run |
| Owner | Last editor, often unknown | Named platform team with a support channel |
| Freshness | Ages silently | Versioned, tested, and released like software |
| Defaults | Described, then copied inconsistently | Encoded, so the safe choice is the easy choice |
| Feedback | Page views, if anything | Adoption, time to first deploy, support requests |
| Leaving the path | Undefined | Documented escape hatch with reduced support |
| End of life | Forgotten | Deprecation notice and migration path |

Treat the escape hatch as part of the design rather than as a failure. Spotify's post says an adventurous engineer can leave the Golden Path and do their own thing, but will not get the same support. That trade is the heart of a healthy golden path: teams with unusual needs are not blocked, the platform team is not obliged to support every variation, and the reasons people leave become product feedback. If many teams leave for the same reason, the path is missing a capability, and the fix belongs in the template rather than in a sternly worded policy.

Adoption is the measurement that separates a product from a mandate. A golden path that people choose voluntarily is solving a real problem, while one that teams avoid, work around, or use only because an audit forces them is telling you something about its cost. Track how many new services start from the path, how long a new team takes to reach its first production deployment, and which support requests keep recurring. Those measurements connect directly to delivery metrics such as deployment frequency and lead time, and they give you evidence for declining features that would not move them.

Tools such as Backstage software templates are one way to deliver a golden path, and they serve here as a worked example rather than a requirement. A Backstage template can scaffold a repository, register the new component in a software catalog with an owner, and open the initial pull request. The same outcome can come from a repository template plus a shared pipeline library, or from a command-line generator. The durable skill is deciding what the path should encode and how you will know it works; the tool is chosen afterward, based on which interfaces your users already live in.

> **Pause and predict:** Your team maintains a thorough wiki page titled "How to deploy a new service" that has not changed in a year. Using the comparison table above, list the three properties you would need to add before you could honestly call it a golden path, and predict which one would cost your team the most effort to sustain.

Most teams find that ownership and freshness are the expensive properties, not the template itself. Generating a skeleton repository can take an afternoon, while committing a team to keep that skeleton current through runtime upgrades, security patches, and pipeline changes is a standing investment. That cost is why the maturity model treats investment as its own aspect. A golden path without funded ownership decays into another stale wiki page, only with more automation attached, and the automation makes the decay harder to notice.

## GitOps Reconciliation and Why Manual Edits Drift

You already understand reconciliation, even if you have never used a GitOps tool. The Kubernetes documentation describes controllers as control loops that watch the state of the cluster and then make or request changes where needed, and it uses a room thermostat as the analogy. When you scale a Deployment, the Deployment and ReplicaSet controllers keep working until the running Pods match the number you declared. The desired state lives in the API server, and the controllers treat it as the truth they converge toward.

GitOps moves the desired state one level further out. The OpenGitOps principles state that desired state is expressed declaratively, stored in a versioned and immutable form, pulled automatically by software agents, and continuously reconciled by agents that observe actual state and attempt to apply the desired state. In practice the source is a Git repository, and a controller such as Argo CD or Flux compares what Git declares with what the cluster contains. Kubernetes controllers still watch the API server, but the API server is no longer where humans are supposed to make changes.

```text
   engineer
      |  pull request, review, merge
      v
+--------------+   pull    +--------------------+   apply   +------------------+
| Git history  | --------> | GitOps reconciler  | --------> | Kubernetes API   |
| desired state|           | compare, then sync | <-------- | live state       |
+--------------+           +--------------------+  observe  +------------------+
                                                                  ^
                  kubectl edit / scale / patch (outside Git) -----+
                  result: reverted, overwritten later, or untracked
```

Now consider what a manual edit means in that system. When you run kubectl edit, kubectl scale, or kubectl patch against an object that a GitOps controller manages, you change live state without changing desired state. The reconciler sees a difference between Git and the cluster, and what happens next depends on how it is configured. That dependence is why "I fixed it in the cluster" is not a complete sentence on a GitOps platform: you also need to say what the reconciler will do with your fix, and when.

Argo CD illustrates the common outcomes clearly. Its automated sync documentation says that, by default, changes made to the live cluster will not trigger automated sync, so the application is reported as out of sync while your edit stays in place until a later sync from Git overwrites it. With self-healing enabled, Argo CD syncs when live state deviates from Git, so your edit is reverted shortly after you make it. A third outcome applies to objects no reconciler manages at all: the edit persists, nobody reviews it, and it disappears when the environment is rebuilt from Git.

The following Application manifest is illustrative and uses a placeholder repository URL. It shows the two settings that most change how drift behaves, alongside the source and destination fields that tie a Git path to a cluster namespace. Flux and other reconcilers express the same ideas with different fields and names, so read this as an example of the concept rather than as the only way to configure it.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/platform-gitops.git
    targetRevision: main
    path: apps/web
  destination:
    server: https://kubernetes.default.svc
    namespace: web
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

With prune enabled, resources removed from Git are deleted from the cluster, and the Argo CD documentation notes that automated sync does not prune by default, as a safety mechanism. With selfHeal enabled, live changes are reverted to match Git. Together those settings make Git the only durable way to change the application, which is the goal. They also mean that a well-intentioned manual fix during an incident will be undone unless someone changes Git or deliberately pauses automation first.

### Revert, codify, or declare the difference

Every detected drift calls for one of three responses. Revert means the live change was a mistake or an experiment, so you let the reconciler restore Git's version. Codify means the live change was correct, so you open a pull request that puts it into Git, where it is reviewed and becomes the new desired state. Declare the difference means another controller legitimately owns that field, so you stop treating it as drift. Choosing the response deliberately is the skill; leaving drift in place because nobody decided is how platforms lose track of their own configuration.

The HorizontalPodAutoscaler is the classic case for the third response. The Kubernetes autoscaling documentation recommends removing spec.replicas from the Deployment manifest once an HPA manages the workload, because applying a manifest that still contains a replica count scales the workload back to that number. If Git keeps the field, the reconciler and the autoscaler fight over one value. Argo CD offers ignoreDifferences for fields other controllers own, but its sync options documentation explains that ignored differences affect only the diff by default, and the RespectIgnoreDifferences option is needed for sync to leave them alone.

There is also a subtler kind of drift that no diff will show you. Re-applying a manifest with kubectl apply removes a field only if that field appeared in the previously applied configuration and is now missing from the file. A field someone added manually, which the file never declared, is left in place. The hands-on exercise demonstrates this directly, and the durable lesson carries over to GitOps tools, whose diff strategies vary: declare in Git every field you care about, and treat anything you never declared as untracked state.

### Break-glass without losing the fix

Incidents sometimes justify a manual change, because a pull request, review, and sync cycle can be slower than a mitigation users need immediately. The platform answer is a break-glass procedure, not a ban. The procedure should say who may pause automated sync for an application, how the pause is announced, where the manual change is recorded, and how quickly a pull request must codify or reverse it. Pausing self-heal on purpose is safe, while forgetting that it is paused is how a cluster quietly drifts for months.

The deeper point connects back to your certification skills. In a GitOps world you mostly use kubectl to observe, through commands such as get, describe, logs, events, and diff, while changes flow through Git. Running kubectl diff against the files in the repository is one of the fastest ways to check whether the cluster matches what Git declares, and its exit status makes it easy to use in scripts. The skill you practiced for the exam becomes the verification layer for a system where the repository, not the terminal, is the control surface.

## Service Ownership, SRE, and Toil

A common misreading of SRE is that it simply means joining an on-call rotation. On-call is part of the practice, but the SRE book frames the discipline around engineering: reliability targets, error budgets, incident response, postmortems, capacity planning, and the deliberate reduction of toil. A team that carries a pager and never changes the systems that page it is doing operations under a new title. For a platform team, SRE practices are how you decide which reliability work to do next and how you show that it mattered.

Toil has a specific definition in the SRE book: work that is manual, repetitive, automatable, tactical, without enduring value, and that grows linearly as the service grows. Cluster administrators usually recognize a lot of toil in their current jobs, such as creating namespaces by hand, rotating credentials manually, or approving routine access requests one ticket at a time. Each of those is a candidate for a platform capability, and naming it as toil is the first step toward getting time allocated to remove it rather than simply absorbing it forever.

Not every recurring task should be automated, though. For each piece of toil, a platform engineer chooses among four responses: automate it into a self-service capability, document it so another team can run it safely, delegate it to the team that has the context, or delete it because the process no longer serves anyone. Automation that nobody owns becomes operational debt of its own, which is why self-service without guardrails appears in the diagnostic. A self-service namespace API still needs quotas, labels, policies, and a support path, or it moves toil from the ticket queue into the incident queue.

Service ownership ties these ideas together. An ownership model states which team is paged for a service, where its runbooks and documentation live, how escalation works, and what happens when the service is retired. Platform tooling can make ownership visible, for example through a software catalog that records the owning team for every component, but it can't create ownership where none exists. When a catalog lists an owner who no longer works on the service, the portal is accurate about its metadata and wrong about reality, and that gap is exactly where incidents stall.

Postmortems are the feedback loop that keeps ownership honest. The SRE book's chapter on postmortem culture emphasizes blameless reviews that look for the system and process causes of an incident rather than for an individual to blame. For a cluster administrator the shift is from asking which command fixed the problem to asking which conditions made the failure possible and which platform change would make the whole class of failure less likely. That second question is where many platform roadmap items come from, and it is why incident reviews belong in platform planning.

## Measuring Delivery, Not Just Clusters

Cluster dashboards answer whether the infrastructure is healthy, but they rarely answer whether the platform is helping anyone. Delivery metrics fill that gap. DORA's research tracks software delivery performance with measures of throughput, such as how often teams deploy and how long changes take to reach production, and measures of instability, such as how often deployments fail and how long recovery takes. The exact names and number of metrics have changed across DORA reports, so check the current guide before building a dashboard, but the durable idea is stable.

For a platform team these measures work best as learning signals rather than as rankings. Comparing two service teams by deployment frequency invites gaming and ignores that their services carry different risk. Comparing the same team before and after it moved onto a golden path tells you whether the path helped. Pair delivery measures with a few developer experience signals, such as the time a new engineer needs to ship a first change or the volume of recurring support requests, and you have a feedback loop that can justify or cancel the next platform investment.

## Secure Defaults and Tool Selection

Security in a platform role follows the same product logic as golden paths: the secure option should also be the easiest one. A cluster administrator applies security controls such as RBAC bindings, Pod Security admission levels, and NetworkPolicies object by object. A platform engineer builds those controls into templates and workflows, so each new service starts secure and a team would need to take deliberate extra steps to become insecure. When the safe path takes more effort than the unsafe one, people choose the unsafe path under deadline pressure, and no policy document changes that.

Secrets management is a good example of a workflow that has to be designed rather than merely installed. The External Secrets Operator synchronizes values from an external secret store, such as HashiCorp Vault, into Kubernetes Secrets, and Vault's Kubernetes auth method lets workloads authenticate using their service account tokens. Those pieces help only when the platform decides naming conventions, the path structure in the store, the review process for new secrets, and rotation expectations. The Vault module in the sequenced path teaches the mechanics, while this bridge asks you to see the result as a workflow that teams must adopt.

The same caution applies to developer portals and delivery controllers. Backstage, Argo CD, and Vault appear in this bridge as worked examples of capabilities: a portal with a software catalog and templates, a GitOps reconciler, and a secret store. Other tools deliver the same capabilities, and the landscape changes quickly, so compare candidates by user journeys, operability, and reliability impact rather than by feature lists. The anti-pattern to avoid is installing a portal before you have ownership data worth showing, or installing a reconciler before the team agrees how changes reach Git.

## Anti-patterns

- Treating platform engineering as just YAML at scale.
- Building golden paths nobody uses because no developer workflow was measured first.
- Ignoring developer cycle-time data and optimizing only cluster cleanliness.
- Conflating SRE with an on-call rotation.
- Installing Backstage, Argo CD, or Vault before defining the operating model they serve.
- Creating self-service APIs without ownership, support, deprecation, and incident paths.

Each anti-pattern is a symptom of treating the platform as infrastructure rather than as a product with users. Watch for them in your own plans and proposals: when a document names a tool before it names a user problem, or measures cluster state instead of delivery outcomes, it is usually drifting toward one of these patterns, and the cheapest time to correct course is before anything is installed.

## What success looks like

- You can describe platform users, their constraints, and the work they are trying to finish.
- You can define a golden path with defaults, escape hatches, documentation, and support boundaries.
- You can use SLOs and error budgets to prioritize platform work.
- You can identify toil and decide whether to automate, document, delegate, or delete it.
- You can explain how GitOps reduces drift and improves reviewability.
- You can evaluate tools by adoption, operability, and reliability impact instead of feature lists.

## Did You Know?

- The SRE book gives a one-question test for telling an SLO from an SLA: ask what happens if the objective is missed. If there is no explicit consequence, you are almost certainly looking at an SLO, however formal the document looks.
- Spotify's 2020 post on golden paths recalls that, before those paths existed, engineers often learned tooling practices by asking colleagues, a habit the company affectionately called "rumour-driven development".
- The OpenGitOps principles, version 1.0.0, list four properties: declarative, versioned and immutable, pulled automatically, and continuously reconciled. The last one is the same control-loop idea Kubernetes controllers use, applied to a Git repository.
- Google's SRE organization advertises a goal of keeping toil below 50% of each SRE's time, so that at least half goes to engineering work that reduces future toil or adds service features.

## Common Mistakes

| Mistake | Why it hurts | Better approach |
|---|---|---|
| Copying the SLA threshold directly into the SLO | The first warning of trouble arrives as a contractual breach | Keep the internal SLO stricter than the SLA so there is time to react |
| Choosing CPU or node readiness as the SLI | Users experience failed and slow requests, not resource usage | Measure good events over valid events as close to the user as practical |
| Publishing an SLO without an error budget policy | Missing the target changes nothing, so the number becomes decoration | Agree in advance which actions happen when the budget is spent, and who takes them |
| Calling a wiki page a golden path | Nobody owns it, it ages silently, and choices are copied by hand | Encode defaults in templates and pipelines with a named owner and support channel |
| Fixing a GitOps-managed object with kubectl edit and moving on | Self-heal reverts it, a later sync overwrites it, or it becomes untracked state | Codify the fix in Git, or follow a recorded break-glass procedure that pauses sync |
| Keeping spec.replicas in Git for an HPA-managed Deployment | The reconciler and the autoscaler fight over the replica count | Remove the field from the manifest, or configure the reconciler to respect the ignored field |
| Installing a portal or controller before defining the operating model | The tool has nothing real to show and adoption stalls | Map user journeys, ownership, and change flow first, then choose tools |

## Quiz

Each question describes a situation you are likely to meet during your first months in a platform role. Choose one answer before opening the explanation, and pay attention to why the other options fail, because the distractors are the misunderstandings that experienced cluster administrators most often bring with them.

**Question 1.** A product manager wants the internal platform objective of 99.95% successful deployment API requests copied word for word into a new external contract, which would pay service credits whenever availability drops below that same number. What is the most accurate response to the proposal?

A) Agree, because an SLA and an SLO are the same promise written for different audiences.
B) Keep the SLO internal and set any contractual SLA threshold looser, because only the SLA carries consequences.
C) Replace the SLO with CPU utilization targets, because contracts should rest on easily read resource metrics.
D) Remove the error budget, because an external contract makes internal budgets unnecessary once credits exist.

<details>
<summary>Answer to Question 1</summary>

**Correct answer: B.** B is correct because the SLA is the external contract with consequences, while the SLO is the internal target; keeping the SLO stricter than the SLA gives the team warning and room to react before credits are owed. A is wrong because an SLA is defined by its consequences, and the SRE book's test is exactly whether missing the objective triggers an explicit consequence. C is wrong because users experience failed and slow requests rather than CPU usage, so resource metrics make poor SLIs and worse contracts. D is wrong because the error budget is what tells the team how much unreliability remains before the SLO, and therefore the SLA, is at risk.

</details>

**Question 2.** A service has an availability SLO of 99.9% over a rolling thirty-day window, and the team tracks its error budget as minutes of full unavailability. One outage this window lasted thirty minutes, and there were no other failures. How much of the error budget remains for the rest of the window?

A) None, because 0.1% of a single day is only 1.44 minutes and the outage exceeded it.
B) All of it, because error budgets only count incidents that users formally reported.
C) About 13.2 minutes, because the thirty-day budget is 43.2 minutes and thirty were spent.
D) About 73.2 minutes, because the outage minutes are added to the 43.2-minute budget.

<details>
<summary>Answer to Question 2</summary>

**Correct answer: C.** C is correct because thirty days contain 43,200 minutes, 0.1% of that is 43.2 minutes, and a thirty-minute outage leaves about 13.2 minutes; with more than two thirds spent, the error budget policy should make the team cautious about risky changes. A is wrong because it applies the budget to one day instead of the SLO's thirty-day window. B is wrong because the SLI measures events or time directly, not user complaints, so unreported failures still consume budget. D is wrong because spending budget reduces what remains; failures never add to the budget.

</details>

**Question 3.** Two platform teams each claim to offer a golden path for new services. The first maintains a detailed wiki page with copy-and-paste YAML. The second maintains a versioned template, a pipeline with built-in security scans, a named support channel, and a monthly adoption report. Which statement best evaluates the two claims?

A) Both are golden paths, because each one documents the recommended way to build a new service.
B) Neither is a golden path, because a golden path must be mandatory for every team in the organization.
C) The wiki page is stronger, because prose documentation is always easier to update than a template.
D) The second is a golden path, because it is an opinionated, supported product path with an owner and adoption evidence.

<details>
<summary>Answer to Question 3</summary>

**Correct answer: D.** D is correct because a golden path is a supported product path: it encodes defaults in something executable, has an owner and a support channel, and measures adoption. A is wrong because describing choices is not the same as making them, and a wiki page with no owner ages silently. B is wrong because Spotify's definition treats the path as optional; engineers may leave it, but they lose the same level of support. C is wrong because being easy to edit does not make a page maintained, tested, or adopted, which are the properties that matter.

</details>

**Question 4.** During an incident you run kubectl edit on a Deployment to raise a memory limit, and the Pods stabilize. Shortly afterward the old limit returns and the Pods restart again. The Deployment is managed by Argo CD with automated sync, prune, and selfHeal enabled. What explains the manual cluster edit disappearing?

A) The kubelet rejected the edit, because memory limits change only when the Deployment is deleted and recreated.
B) The reconciler detected drift between live state and Git and reapplied Git, so the fix belongs in Git.
C) The API server lost the edit, because kubectl edit writes to a local cache until the next backup runs.
D) Prune deleted the Deployment, because any manual edit marks a resource as no longer defined in Git.

<details>
<summary>Answer to Question 4</summary>

**Correct answer: B.** B is correct because GitOps reconciliation with selfHeal compares live state to Git and syncs when they differ, so a manual cluster edit drifts and is reverted; the fix must be codified in Git, or sync must be paused under a recorded break-glass procedure. A is wrong because changing resources in the Pod template is a normal update that triggers a rollout. C is wrong because kubectl edit submits the change to the API server, which is why the Pods stabilized at first. D is wrong because prune deletes resources removed from Git, and the Deployment still exists in Git.

</details>

**Question 5.** A team adds a HorizontalPodAutoscaler to a Deployment that Argo CD syncs from Git. The manifest in Git still sets spec.replicas to three. Under load the autoscaler scales to eight replicas, but the count keeps snapping back toward three whenever a sync runs. Which change resolves the conflict most cleanly?

A) Delete the HPA, because autoscalers are fundamentally incompatible with GitOps reconciliation.
B) Disable selfHeal for every application in the cluster, because production should never correct drift.
C) Remove spec.replicas from the manifest in Git, because the autoscaler should own the replica count.
D) Raise spec.replicas in Git to eight, because a larger fixed number satisfies both the HPA and the reconciler.

<details>
<summary>Answer to Question 5</summary>

**Correct answer: C.** C is correct because the Kubernetes autoscaling documentation recommends removing spec.replicas once an HPA manages the workload; the field then has one owner and the reconciler stops fighting the autoscaler. A is wrong because autoscalers and GitOps coexist well once field ownership is clear. B is wrong because it disables drift correction everywhere to hide a single field conflict. D is wrong because any fixed number still fights the HPA whenever load changes; a declared difference with RespectIgnoreDifferences is a valid alternative, but a bigger constant is not.

</details>

**Question 6.** You manage a Deployment with kubectl apply from a file in Git. A colleague runs kubectl scale to set five replicas and kubectl set env to add FEATURE_FLAG=on. You then re-run kubectl apply with the unchanged file, which declares two replicas and no environment variables. What state should you expect afterward?

A) Replicas return to two and the variable remains, because apply removes only previously applied fields.
B) Replicas stay at five and the variable is removed, because apply never changes fields other commands touched.
C) Both changes are reverted, because kubectl apply always makes the live object identical to the file.
D) Neither change is reverted, because kubectl apply only creates new objects and skips existing ones.

<details>
<summary>Answer to Question 6</summary>

**Correct answer: A.** A is correct because client-side kubectl apply compares the file, the live object, and the last-applied-configuration annotation: replicas is declared in the file, so it returns to two, while the variable never appeared in the previous applied configuration, so apply leaves it in place as untracked drift. B is wrong because apply does reset declared fields that other commands changed. C is wrong because apply is not a full replacement, which is exactly why undeclared manual changes can survive. D is wrong because apply updates existing objects as well as creating new ones.

</details>

**Question 7.** Leadership asks your new platform team to install an internal developer portal this quarter, so that every service appears in a catalog. Most services have no recorded owner, and nobody has measured where developers lose time today. What should the platform team do first?

A) Install the portal immediately and let teams fill in ownership later, because visibility creates demand.
B) Map developer journeys and establish service ownership data, because a catalog needs real owners.
C) Replace the portal plan with a larger cluster, because developer friction is usually a capacity problem.
D) Publish a wiki page listing every service, because a list is equivalent to a catalog with templates.

<details>
<summary>Answer to Question 7</summary>

**Correct answer: B.** B is correct because a portal is useful only when it reflects real service ownership and golden-path workflows, and measuring developer journeys shows which capabilities the portal should expose first. A is wrong because a catalog full of missing or stale owners teaches developers not to trust the portal. C is wrong because nothing in the scenario points to capacity, and guessing at causes skips the measurement step. D is wrong because a static list has no owner, no templates, and no feedback loop, which are the properties that make a catalog valuable.

</details>

**Question 8.** A CKA holder completes the diagnostic checklist and leaves every item about SLOs, error budgets, postmortems, and service ownership unchecked, while confidently checking the GitOps and tooling items. Which sequenced study plan best fits the result of that diagnostic?

A) Start with the Argo CD and Backstage toolkit modules, because tools are the quickest way to show progress.
B) Skip the foundations entirely, because cluster administration certification already covers reliability work.
C) Study only observability dashboards, because more metrics will close SLO and ownership gaps on their own.
D) Start with systems thinking and reliability engineering, then SRE, because those steps match the gaps.

<details>
<summary>Answer to Question 8</summary>

**Correct answer: D.** D is correct because the unchecked diagnostic checklist items map to systems thinking, reliability engineering, and SRE in the sequenced path, so a sequenced study plan should begin there and defer tools the learner already understands. A is wrong because tools are easier to evaluate after the reliability concepts, and this learner already checked the tooling items. B is wrong because cluster administration certifications focus on operating Kubernetes, not on SLOs, error budgets, or ownership models. C is wrong because dashboards display signals but do not define targets, policies, or owners.

</details>

## Hands-On Exercise: Drift, Error Budgets, and a Golden-Path Charter

This exercise builds one small artifact for each core idea. You will create drift on purpose in a local kind cluster and observe what kubectl diff and kubectl apply do with it, calculate error budgets for two SLOs, and write a one-page charter that turns a deployment wiki page into a golden-path proposal. Plan for about forty-five minutes, and have Docker or another kind-supported container runtime, the kind CLI, kubectl, git, and python3 available before you begin.

### Step 1: Create a cluster and a Git-tracked manifest

Start with a disposable cluster and a small Git repository that plays the role of the platform's source of truth. The repository holds one Deployment manifest, and applying it by hand stands in for the sync step a GitOps controller would perform. That keeps the exercise focused on the reconciliation concept rather than on installing and configuring a controller, and it lets you see each comparison step explicitly. Run every later command from the same repository directory.

```bash
kind create cluster --name platform-bridge
kubectl create namespace bridge-lab

mkdir -p ~/platform-bridge/apps/web
cd ~/platform-bridge
git init --quiet

cat > apps/web/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: bridge-lab
  labels:
    app.kubernetes.io/name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: web
  template:
    metadata:
      labels:
        app.kubernetes.io/name: web
    spec:
      containers:
        - name: web
          image: nginx:1.27
          ports:
            - containerPort: 80
EOF

git add apps/web/deployment.yaml
git -c user.name="Bridge Lab" -c user.email="lab@example.com" commit --quiet -m "Add web deployment"

kubectl apply -f apps/web/deployment.yaml
kubectl -n bridge-lab rollout status deployment/web --timeout=180s
```

The rollout status command should report that the Deployment was successfully rolled out. At this point Git, the last applied configuration stored on the object, and the live object all agree. That agreement is the state a reconciler works to maintain, and the next step deliberately breaks it the way a busy operator might during an incident.

### Step 2: Create drift the way an operator would

Make two manual changes of the kind that happen under pressure: scale the Deployment and add an environment variable directly against the live object. Neither change touches the file in Git, so both are drift, even though the cluster accepts them and the Pods keep running normally. Before running the next step, write down which of the two changes you expect kubectl apply to undo.

```bash
kubectl -n bridge-lab scale deployment/web --replicas=5
kubectl -n bridge-lab set env deployment/web FEATURE_FLAG=on
kubectl -n bridge-lab rollout status deployment/web --timeout=180s
kubectl -n bridge-lab get deployment web -o jsonpath='{.spec.replicas}{"\n"}'
```

### Step 3: Detect the drift and re-apply from Git

Run kubectl diff against the file in Git. The command exits with status 0 when there are no differences, 1 when differences are found, and a higher status when kubectl or the diff program itself fails, which makes it practical in scripts and CI checks. Then re-apply the unchanged file, as a reconciler would, and inspect both fields you changed by hand.

```bash
kubectl diff -f apps/web/deployment.yaml
echo "kubectl diff exit status: $?"

kubectl apply -f apps/web/deployment.yaml
kubectl -n bridge-lab get deployment web -o jsonpath='{.spec.replicas}{"\n"}'
kubectl -n bridge-lab get deployment web -o jsonpath='{.spec.template.spec.containers[0].env}{"\n"}'
```

Observed output from a recorded run on a kind cluster: the diff showed the replica count changing from 5 back to 2, plus a bump in metadata.generation, and exited with status 1, but it showed no change to the FEATURE_FLAG variable. After the apply, replicas read 2 while the environment still contained FEATURE_FLAG. Client-side apply removes a field only when it appeared in the last applied configuration and is now missing from the file, and the variable was never in either, so it survived as untracked state.

### Step 4: Codify the change instead of reverting it

Suppose the incident review decides the feature flag is correct and should stay. The platform response is to codify it: change the file, commit it, and apply from Git, so that the desired state, the history, and the live object agree again. Afterward kubectl diff should report no differences and exit with status 0, and the Git log should show the change as a reviewed commit rather than as an unexplained edit.

```bash
python3 - <<'EOF'
from pathlib import Path
path = Path("apps/web/deployment.yaml")
text = path.read_text()
text = text.replace(
    "          ports:\n",
    "          env:\n            - name: FEATURE_FLAG\n              value: \"on\"\n          ports:\n",
)
path.write_text(text)
EOF

git -c user.name="Bridge Lab" -c user.email="lab@example.com" commit --quiet -am "Codify FEATURE_FLAG for web"
kubectl apply -f apps/web/deployment.yaml
kubectl diff -f apps/web/deployment.yaml
echo "kubectl diff exit status: $?"
git log --oneline
```

### Step 5: Calculate two error budgets

Now turn two SLOs into budgets. The first is time-based and uses the thirty-day window from the reliability section. The second is request-based and asks how much of the budget a batch of failures has consumed. Run the calculation rather than relying on mental arithmetic, because a slip in the number of nines changes the answer by a factor of ten and quietly invalidates every decision built on it.

```bash
python3 - <<'EOF'
window_minutes = 30 * 24 * 60
slo = 0.999
print(f"time budget: {window_minutes * (1 - slo):.1f} minutes")

valid_requests = 2_000_000
request_slo = 0.995
failed_requests = 6_500
request_budget = valid_requests * (1 - request_slo)
print(f"request budget: {request_budget:.0f} failed requests")
print(f"budget consumed: {failed_requests / request_budget:.0%}")
EOF
```

```text
time budget: 43.2 minutes
request budget: 10000 failed requests
budget consumed: 65%
```

Decide what your error budget policy would say at 65% consumed with part of the window still ahead. A reasonable answer names a threshold, an action, and an owner, such as requiring extra review for risky changes once most of the budget is gone and pausing feature releases when it is exhausted. The exact thresholds are yours to choose; what matters is that the decision is written down and agreed before an incident forces it.

### Step 6: Write a golden-path charter and a toil review

Pick a deployment wiki page you know, real or imagined, and write a one-page charter that would turn it into a golden path. Use the properties from the comparison table: what the path encodes, who owns it, how it is versioned, what the escape hatch is, how adoption and a platform SLO are measured, and how the path will eventually be deprecated. Then classify two recurring tasks from your own work against the toil criteria and record an ownership decision for each.

```bash
cat > charter.md <<'EOF'
# Golden path charter: new web service

Owner (team and support channel):
Encoded defaults (template, pipeline, security, observability):
Versioning and release process:
Escape hatch and reduced-support terms:
Adoption measure:
Platform SLI and SLO for this path:
Deprecation and migration policy:

Toil review (task, toil criteria met, decision: automate, document, delegate, or delete):
1.
2.
EOF

git add charter.md
git -c user.name="Bridge Lab" -c user.email="lab@example.com" commit --quiet -m "Draft golden path charter"
kind delete cluster --name platform-bridge
```

### Success Criteria

- [ ] You created drift with kubectl scale and kubectl set env, then used kubectl diff to detect the replica change before re-applying from Git.
- [ ] You explained in one sentence why kubectl apply restored the replica count but left the undeclared environment variable in place as manual cluster drift.
- [ ] You codified the manual cluster edit in Git and confirmed that kubectl diff exited with status 0 afterward.
- [ ] You calculated the 43.2-minute time budget and the 10,000-request error budget, and wrote an SLO policy action for 65% consumption.
- [ ] Your golden path charter names an owner, encoded defaults, an escape hatch, an adoption measure, and a platform SLO.
- [ ] You classified two recurring tasks against the toil criteria and recorded a service ownership decision for each.

## Sources

- [Google SRE Book: Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Google SRE Book: Embracing Risk](https://sre.google/sre-book/embracing-risk/)
- [Google SRE Workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Google SRE Book: Eliminating Toil](https://sre.google/sre-book/eliminating-toil/)
- [Google SRE Book: Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- [OpenGitOps principles](https://opengitops.dev/)
- [Argo CD: Automated Sync Policy](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/)
- [Argo CD: Sync Options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/)
- [Kubernetes: Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [Kubernetes: Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- [Spotify Engineering: How We Use Golden Paths to Solve Fragmentation in Our Software Ecosystem](https://engineering.atspotify.com/2020/08/how-we-use-golden-paths-to-solve-fragmentation-in-our-software-ecosystem/)
- [CNCF TAG App Delivery: Platforms White Paper](https://tag-app-delivery.cncf.io/whitepapers/platforms/)
- [CNCF TAG App Delivery: Platform Engineering Maturity Model](https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/)
- [Backstage: Software Templates](https://backstage.io/docs/features/software-templates/)
- [External Secrets Operator: Overview](https://external-secrets.io/latest/introduction/overview/)
- [HashiCorp Vault: Kubernetes Auth Method](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
- [DORA: Software Delivery Performance Metrics](https://dora.dev/guides/dora-metrics/)

## Next Module

Continue with [What is Systems Thinking?](/platform/foundations/systems-thinking/module-1.1-what-is-systems-thinking/), the first step in the sequenced path. It introduces the feedback loops, delays, and leverage points that the rest of the platform track uses to explain why some internal platforms earn adoption while others stall despite excellent engineering.
