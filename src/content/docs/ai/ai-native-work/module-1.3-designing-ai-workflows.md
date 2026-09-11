---
title: "Designing AI Workflows"
slug: ai/ai-native-work/module-1.3-designing-ai-workflows
sidebar:
  order: 3
revision_pending: false
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45-60 min
>
> **Prerequisites**: AI-native work fundamentals, basic command-line comfort, and familiarity with code review or operational review habits

---

## What You'll Be Able to Do

- Design bounded AI workflow candidates by mapping goals, inputs, outputs, ownership, verification, and revision paths.
- Implement verification gates for AI-generated drafts using tests, policy checks, source review, and human approval.
- Compare human-in-the-loop and human-on-the-loop checkpoints for risk, accountability, latency, and scale.
- Diagnose workflow failure modes such as hidden context, missing source visibility, weak rollback, and novelty-driven automation.
- Evaluate when not to automate high-risk decisions without deterministic checks, clear escalation, and accountable ownership.

## Why This Module Matters

Hypothetical scenario: your team wants to "use AI for release work" because everyone is spending too much time turning issue notes, pull request summaries, test output, and deployment risks into a release brief. The first week feels promising because the model drafts fluent text quickly, but each engineer builds a different prompt, copies different context, and checks different facts before publishing. By Friday, the team has not built a workflow; it has created several private habits that only work while the original prompt writer is watching closely.

That difference matters because the real value of AI usually comes from workflow design, not isolated prompts. A prompt can produce a useful draft once, but a workflow makes the useful behavior repeatable, observable, reviewable, and improvable. If the workflow is vague, AI creates noise faster, and the team spends its time correcting plausible output. If the workflow is clear, AI can reduce friction while preserving the human and technical checks that make the final result trustworthy.

In this module, you will design workflows the way an engineer designs a production path: define the input, shape the context, constrain the output, verify the result, revise when the result fails, and assign responsibility before anything important changes state. You will not learn a magic prompt that fixes every task. You will learn a repeatable design method for deciding where AI belongs, where it should stop, and what evidence must exist before a person or system trusts its output.

> **Go deeper:** When workflows graduate to multi-agent orchestration and fleet-scale coordination, see [Symphony](/ai/ai-engineering-foundations/module-4.1-symphony-work-orchestration-as-applied-harness/) in the engineering-foundations spine.

## From Prompting to Workflow Design

A workflow is not "a lot of prompts." A workflow is a repeatable structure for moving from an input, through a sequence of steps, toward an output, with clear ownership and verification. That definition sounds simple, but it is the line between casual AI usage and operational AI usage. A casual prompt can be helpful when you are exploring ideas alone. A workflow is what you need when another person must repeat the process, review the result, or depend on the output later.

The easiest way to spot a non-workflow is to ask someone to explain the path from request to final artifact. If the answer is mostly "I paste some stuff into the model and clean it up," the process still depends on hidden judgment. Hidden judgment is not automatically bad, but it cannot be measured, delegated, or improved until the team names it. Workflow design turns that hidden judgment into visible steps, much like a deployment pipeline turns a developer's local build ritual into a shared system.

Good AI workflow design starts with the output, not the model. The question is not "Which model can do this task?" but "What result do we need, what evidence makes it acceptable, and what happens when it is not acceptable?" Once the output and acceptance criteria are clear, the model becomes one component in a larger path. That path may include retrieval, schema validation, tests, source checks, peer review, human approval, or rollback instructions, depending on the risk of the task.

In an AI-native context, workflows can be linear, branching, or looped. A simple writing workflow may move from goal to context to draft to review. A more advanced operational workflow may classify the request, route it to a specialized prompt, call a tool, validate the tool output, and retry with focused feedback when a gate fails. The important point is not that every workflow must be complicated. The important point is that the team can see the steps and reason about where trust is earned.

```yaml
# Example: A self-correcting workflow for infrastructure-as-code generation
workflow:
  nodes:
    - id: generate-manifest
      action: llm_call
      params: { model: "gpt-4o-mini", template: "k8s-deployment" }
    - id: semantic-audit
      action: llm_judge
      params: { model: "o1-preview", rubric: "sec-policies.md" }
      on_fail: { target: generate-manifest, feedback: true, retry: 3 }
  edges:
    - from: generate-manifest
      to: semantic-audit
      condition: success
```

This example shows deterministic scaffolding around probabilistic generation. The generation step can vary because the model is producing a draft, but the workflow around it is explicit: generate a Kubernetes manifest, audit the result against a security policy rubric, and retry with feedback only when the audit fails. The point is not to pretend that the model is deterministic. The point is to make the surrounding control plane deterministic enough that failures are visible and bounded.

Think of the model as a talented but distractible collaborator sitting inside a process you own. You would not ask that collaborator to approve production access, publish a compliance statement, and change a cluster without checks. You would ask for a draft, compare the draft with evidence, run tools that catch mechanical mistakes, and decide who can approve the final action. Workflow design is the act of putting those boundaries in writing before the first impressive demo convinces people to skip them.

Pause and predict: what do you think happens if a team standardizes the prompt but never standardizes the verification step? The answer is that the team may get a more consistent style of draft, but it still cannot consistently trust the result. Prompt consistency improves the first pass. Workflow consistency improves the path from first pass to accepted work.

The next design question is observability. A workflow that cannot explain what happened during a run is difficult to improve, even when the final answer is acceptable. At minimum, a useful AI workflow should record the input, context source versions, model or tool configuration, verification results, final decision, and owner. This does not require exposing private data broadly, but it does require enough traceability that a reviewer can diagnose why two runs produced different outcomes.

Versioning is part of the same discipline. If a team changes the prompt, swaps the model, updates a retrieval source, or tightens a validation rule, the workflow should treat that as a change to a maintained system. Otherwise, quality drift becomes mysterious. A release pipeline would not silently change a compiler and leave engineers guessing why builds behave differently. AI workflows deserve the same respect because prompt and context changes can alter behavior just as meaningfully as code changes.

Another useful habit is to separate workflow state from conversation state. A chat transcript can be convenient during exploration, but it is a weak system of record for repeatable work. The workflow should name the durable artifacts it produces: a brief, a patch, a review report, a checklist, a ticket comment, or a structured JSON object. When the durable artifact is clear, the team can attach validation, ownership, and history to that artifact instead of relying on memory inside a private chat.

Finally, design the workflow so a failure teaches the next run something specific. A failed gate should produce a useful reason, not just a red mark. "Missing source for the rollout-risk claim" is actionable. "Bad answer" is not. The more precise the failure signal, the easier it is for a model, tool, or human to revise the output without creating new mistakes elsewhere. Good workflow design turns failure into structured feedback.

## The Core Pattern: Draft, Verify, Revise

The smallest useful AI workflow pattern is easy to remember because it mirrors how careful people already work. You define the goal, collect context, ask AI for a draft, verify the draft, revise based on the verification result, and only then produce the final output. The draft can be prose, code, a checklist, a data extraction, or a proposed action. The verification step is what turns that draft from interesting output into work that can be trusted by someone besides the person who generated it.

```text
goal -> context -> AI draft -> verification -> revision -> final output
```

The mistake is usually removing the verification step because the draft looks polished. Polished output is dangerous when the workflow lacks evidence, because fluency can hide missing constraints, old assumptions, unsupported claims, and tool-incompatible syntax. A model can make a wrong answer feel finished. A workflow forces the answer to pass through checks that are harder to fake, such as source review, schema validation, automated tests, policy checks, dry runs, or named human approval.

The goal step should be narrow enough that the workflow can decide whether it succeeded. "Help with onboarding" is not a workflow goal because almost any output could be defended as helpful. "Convert a support handoff into a first-draft onboarding checklist with product links, open questions, and an owner for each step" is much better because it names the shape of the output. The clearer the goal, the easier it is to collect relevant context and reject output that wanders away from the task.

The context step should provide enough information for the model to act, but not so much that the model has to guess what matters. In production workflows, context should move beyond static prompt text toward dynamic context injection. Rather than providing a generic description of the system, the workflow should retrieve the relevant logs, API schemas, source documents, issue links, review comments, or cluster state for the specific goal. The model should see the evidence it needs, and reviewers should be able to inspect that evidence later.

For a Kubernetes troubleshooting workflow, the context should not merely say "the cluster is broken." A stronger context bundle might include the failing Pod's events, recent deployment changes, resource quotas, relevant logs, and the exact error strings from stderr. That bundle constrains the model and gives the verifier something concrete to check. Without this discipline, the model may produce generic advice that sounds reasonable while ignoring the one detail that explains the failure.

The verification step should be designed before the generation step is trusted. For engineering workflows, verification often means piping the AI draft into a syntax checker, test runner, policy engine, dry-run environment, or source citation review. For writing and research workflows, verification may mean checking every claim against the supplied source material and marking unsupported statements for removal. The mechanism changes by domain, but the design principle stays the same: the draft must meet evidence-based criteria before it can move forward.

```bash
# Example of an automated verification gate in a CLI workflow
# 1. AI generates a manifest (draft.yaml)
# 2. Verification step uses a dry-run and a policy check
kubectl apply -f draft.yaml --dry-run=server && \
kube-linter lint draft.yaml && \
echo "Verification Passed" || \
echo "Verification Failed: Feeding errors back to revision loop"
```

This command block is intentionally simple, but it captures an important operational habit. The model can draft a manifest, yet the workflow refuses to treat the manifest as acceptable until Kubernetes server-side dry-run and lint checks have had a chance to reject it. In a real system, you would also capture the failing output and feed a concise error summary into the revision step. That is stronger than asking the model to "try again" because the correction is anchored in a concrete failure.

The revision step should not be a vague loop where the model keeps regenerating until the human gets tired. A useful revision loop carries forward the failed check, the reason for failure, and the constraint that must be preserved. For example, "the policy check rejected missing resource limits; revise only the resource section and keep labels unchanged" is better than "fix this YAML." Specific feedback narrows the model's search space and reduces the risk that one fix breaks another part of the output.

Before running this, what output do you expect if `draft.yaml` has a valid schema but violates a lint rule about missing CPU limits? The dry-run may pass because the API server accepts the object, but the lint step should fail and send the workflow into revision. That distinction is the reason mature workflows often use multiple verification gates. Different tools catch different classes of error, and a single green check rarely proves that the output is ready.

This pattern also makes cost and latency easier to manage. Teams often worry that verification will slow every workflow down, but a predictable gate can reduce total time by catching defects before they reach a human reviewer. The reviewer sees fewer obvious mistakes, the revision loop receives clearer feedback, and failed drafts do not leak into downstream channels. A fast unchecked draft followed by a long cleanup meeting is usually slower than a slightly slower workflow that catches problems early.

The verification step should match the output type. For prose, verification may inspect source coverage, audience fit, required sections, and unsupported claims. For code, it may run tests, linters, type checks, dependency scans, and build commands. For operational recommendations, it may check current state, safety constraints, rollback options, and approval requirements. When verification is generic, the workflow produces generic confidence. When verification is domain-specific, the workflow produces evidence a practitioner can use.

Revision should also preserve intent. A common failure mode is a model that fixes the reported problem but changes unrelated parts of the output. You can reduce this by feeding the model a narrow critique and explicitly naming what must remain unchanged. For example, a code workflow can ask the model to revise only the failing test area and preserve public interfaces. A writing workflow can ask it to remove unsupported claims without changing approved terminology. The workflow becomes safer when revisions are scoped.

There is also a useful distinction between blocking gates and advisory gates. A syntax error or missing required source should usually block the workflow because the artifact cannot be accepted in that state. A style suggestion, minor clarity concern, or optional improvement may be advisory, especially in low-risk workflows. Naming that distinction prevents every check from becoming a crisis. It also lets the team tune the workflow over time as it learns which failures truly predict downstream risk.

## Choosing Good and Bad Workflow Targets

Good workflow targets share a few traits. They have recurring inputs, a stable output shape, clear review criteria, and a human or tool that can tell whether the output is acceptable. Structured drafting is a strong target because the model can produce a first pass while the workflow checks format, tone, required sections, and evidence. Summarization with source review can work well when the source material is visible and the summary is not allowed to invent claims outside that material.

Routine document transformation is another strong candidate because the model can act as a semantic bridge between messy language and a structured downstream format. Meeting notes can become status updates, support tickets can become response drafts, and long issue threads can become migration checklists. The value is not that the model writes words quickly. The value is that the workflow absorbs natural-language variation while still producing a predictable artifact that another person or system can review.

Coding support can also be a strong workflow target when the model is tethered to tests, linting, build output, and code review. The weak version is "AI writes code and we merge it because it looks right." The stronger version is "AI proposes a patch, the test runner and linter produce objective feedback, the model revises within constraints, and a human reviews the final diff." That structure turns AI from a shortcut around engineering discipline into a participant inside engineering discipline.

```yaml
workflow:
  target: security_remediation
  schema_validation: true
  steps:
    - name: extract_vulnerability_impact
      prompt: |
        Analyze the following CVE data. 
        Identify affected container images and required patch versions.
        Output ONLY a JSON object matching the 'VulnerabilitySchema'.
    - name: generate_k8s_patch
      dependency: extract_vulnerability_impact
      action: "kubectl patch deployment {{deployment_name}} --patch-file {{generated_patch}}"
```

This security remediation fragment shows both promise and risk. Extracting vulnerability impact into a strict schema is a good target because it converts unstructured advisory text into a reviewable object. Generating a Kubernetes patch can be useful, but only if the workflow adds validation, impact analysis, and approval before applying anything. The target becomes safer when the model prepares evidence and candidate changes, while deterministic tools and accountable humans decide whether the change should proceed.

Bad workflow targets usually fail because the task has high risk, unclear ownership, unstable inputs, or no reliable way to verify the output. High-risk decisions with no validation are especially poor candidates. A workflow that automatically approves security exceptions, changes production limits, or publishes legal commitments based only on model confidence is not AI-native maturity. It is automation without accountability. The fact that a model can produce a plausible recommendation does not mean the organization has earned the right to act on it automatically.

Tasks with unclear ownership are also weak targets because no one knows who must inspect drift, update prompts, approve changes, or stop the workflow when behavior degrades. AI workflows are not "set and forget" systems. Models change, APIs evolve, context sources move, rubrics get stale, and cost patterns shift. If no person owns those changes, the workflow becomes an orphan process that looks automated until it quietly fails in a way nobody budgeted time to catch.

Novelty-driven automation is a third common trap. A new model capability can make a demo exciting without making the workflow valuable. The right question is not "Can the model do this?" but "Is this a recurring task where AI can improve speed or quality while verification remains practical?" If the answer is no, a manual checklist may be cheaper, safer, and easier to explain. Mature AI adoption includes saying no to workflows that would create more operational surface area than they remove.

Hypothetical scenario: a platform team wants an AI workflow to respond to raw production log streams by restarting Pods when it sees repeated error messages. The idea sounds helpful because it promises fast remediation, but the input is noisy, the action changes production state, and the difference between a transient network issue and a bad rollout may not be visible in a single log line. A safer design would first classify symptoms, gather corroborating signals, prepare a recommendation, and require deterministic checks or human approval before any restart.

The best early workflow candidates are often boring. They do not make keynote demos dramatic, but they remove repeated friction from real work. Turning a long issue thread into a review checklist, turning a transcript into decisions and open questions, or turning a failed test log into a structured debugging brief can save time while keeping humans in control. These workflows are valuable because they compress preparation work, not because they pretend the model owns the final decision.

Another signal of a good target is that failure is easy to see before the output causes harm. If a transcript summary misses an action item, a reviewer can catch it against the transcript. If a generated JSON object fails schema validation, the workflow can reject it immediately. If a model recommends an unsafe infrastructure action, the harm may not be visible until after the action. The easier it is to detect a bad output early, the better the task fits a first workflow.

You should also consider whether the workflow will create reusable knowledge. A one-off prompt may solve today's problem, but a workflow can teach the team what context matters, which checks catch defects, and which outputs need human judgment. That learning compounds only when the workflow is repeated and measured. If the task is rare, ambiguous, and high impact, a careful manual review may produce better organizational learning than a fragile automation path.

The boundary between good and bad targets can move as the team matures. A task that is too risky for automation today may become a good AI-assisted recommendation workflow after the team builds better telemetry, source retrieval, tests, and approval habits. That does not mean every task should eventually become fully automated. It means workflow maturity expands the range of tasks where AI can safely prepare evidence, draft artifacts, and reduce human toil without hiding accountability.

## Placing Humans, Tools, and Checkpoints

The phrase "human in the loop" is useful, but it is too vague to design with by itself. Humans can define goals, approve context, review drafts, check evidence, approve actions, investigate failures, and update rubrics. Those are different jobs with different costs. A workflow that asks a human to review every comma will not scale. A workflow that removes humans from irreversible decisions may scale in the wrong direction. The design work is deciding where human judgment is actually needed.

Human-in-the-loop usually means the workflow cannot proceed until a person approves a step. That pattern is appropriate when the action is high impact, the evidence is ambiguous, or accountability must be explicit. Human-on-the-loop means the system can proceed through low-risk steps while a person monitors metrics, reviews samples, and handles escalations. That pattern works when deterministic gates cover common failures and the remaining risk is low enough for sampling and alerting rather than per-item approval.

Tools belong where the correctness criteria can be expressed mechanically. A Kubernetes server-side dry-run can check whether a manifest is accepted by the API server. A linter can enforce style and policy rules. A schema validator can reject malformed JSON. A citation checker can confirm that links exist and that required source fields are present. Tools do not replace human judgment, but they remove classes of review work that humans are slow and inconsistent at performing repeatedly.

The most effective workflows combine tools and humans in a sequence that matches risk. A model can draft a change, a tool can reject syntax and policy errors, the model can revise based on those errors, and a human can review the final diff and rationale. That order reduces human fatigue because people spend less time catching obvious mechanical mistakes. It also improves accountability because the human sees the artifact after the workflow has collected evidence instead of before the workflow has done its basic hygiene.

```yaml
# Example: Workflow Verification Gate
workflow:
  name: production-resource-patching
  steps:
    - id: generate-patch
      type: llm-inference
      prompt: "Generate a K8s deployment patch to optimize memory limits"
    - id: validation-gate
      type: verification
      strategy: dry-run
      required_checks:
        - schema_validation: "kubernetes-1.35"
        - impact_analysis: "non-destructive"
    - id: manual-approval
      type: human-in-the-loop
      condition: "impact_score > 0.7"
```

This gate adds two important constraints to the earlier idea of AI-generated operational patches. First, the patch must pass verification before approval matters. Second, manual approval is tied to impact, which lets the workflow treat low-risk and high-risk changes differently. The design still needs real implementation details, but the shape is healthier than a direct path from model output to cluster action. A model may suggest a patch; the workflow decides whether the patch is allowed to become an action.

Ownership should appear in the workflow design as a named role, not an assumption. Someone owns the prompt, someone owns the context sources, someone owns the verification rubric, someone owns the final decision, and someone owns rollback or incident response when the workflow behaves badly. In a small team, one person may hold several of those responsibilities. The important point is that the workflow document makes responsibility explicit before a failure exposes the gap.

Which approach would you choose here and why: a human must approve every AI-generated status summary, or a human reviews only summaries that fail source coverage checks or mention high-risk commitments? The right answer depends on the risk of the output, the quality of automated checks, and the cost of delay. Workflow design is not about maximizing automation. It is about matching oversight to the consequences of being wrong.

A practical way to place humans is to ask which decisions require context outside the artifact. A linter can notice a missing field, but it cannot know whether a release note will alarm a customer, whether a policy exception is politically sensitive, or whether a proposed workaround conflicts with an incident commander's plan. Those judgments belong to people because they depend on organizational context, priorities, and consequences that are not fully represented in the input bundle.

At the same time, people should not be used as expensive parsers. If the workflow always asks a human to check whether a JSON object has required fields, the workflow is wasting human attention. Machines are excellent at repeatable structural checks. Humans are better at ambiguity, accountability, prioritization, and final acceptance. Good checkpoint placement protects the human reviewer's attention for the decisions where judgment actually changes the outcome.

Escalation paths deserve the same care as happy paths. A workflow should state what happens when verification fails repeatedly, when context is missing, when the model refuses or produces unusable output, and when a human approver is unavailable. Without an escalation path, teams improvise under pressure and often weaken the workflow exactly when the risk is highest. A simple stop-and-escalate rule can be more valuable than a clever retry loop.

Monitoring should include both quality and operations. Quality metrics might include pass rates, revision counts, source coverage, reviewer overrides, and post-publication corrections. Operational metrics might include latency, cost, timeout rate, tool failures, and escalation volume. These metrics help the owner decide whether the workflow is improving work or merely moving effort into hidden maintenance. A workflow that saves ten minutes per run but creates frequent confusing escalations may not be a win.

## Patterns and Anti-Patterns

Patterns are reusable shapes that help teams avoid inventing a workflow from scratch every time. They are not rigid templates. A good pattern explains when to use it, why it works, and what must change as the workflow scales. For AI workflows, the strongest patterns usually preserve human accountability while moving repetitive transformation, drafting, and mechanical checking into a predictable path.

| Pattern | Use When | Why It Works | Scaling Consideration |
|---|---|---|---|
| Draft then verify | The model creates a first pass that a person or tool can check. | It separates creativity from acceptance and makes trust conditional. | Add automated checks before human review so reviewers focus on judgment. |
| Retrieve then answer | The model must summarize or reason over source material. | It limits unsupported claims by making evidence visible. | Track source freshness, retrieval coverage, and unanswered questions. |
| Route then specialize | Requests vary enough that one prompt becomes overloaded. | A router sends work to smaller prompts with narrower context. | Monitor routing errors because a good answer in the wrong path is still a failure. |
| Fail closed with escalation | The workflow may produce uncertain or risky output. | Ambiguous cases stop or escalate instead of silently proceeding. | Define escalation ownership and alert thresholds before launch. |

The draft-then-verify pattern is the default for writing, coding, and analysis because it matches how professionals already manage risk. Let the model produce a draft quickly, then require the draft to pass checks that reflect the domain. The retrieved-answer pattern matters when claims must trace back to evidence. It is not enough for a summary to sound credible; the workflow should expose what sources were used and what claims were not supported.

The route-then-specialize pattern becomes useful when a single prompt starts carrying too much responsibility. For example, one support workflow might route requests into billing clarification, troubleshooting, onboarding, and escalation paths. Each specialized step can receive narrower context and a more precise rubric. The tradeoff is that routing itself becomes a failure point, so the workflow must measure misroutes and provide a way to recover when the first classification is wrong.

Anti-patterns are tempting because they often make a demo look faster than a production workflow. They remove friction by removing the very checks that create trust. When teams fall into these traps, the fix is rarely "use a bigger model." The fix is to restore boundaries, evidence, ownership, and rollback. A stronger model can still produce an unsupported claim, apply stale context, or take an action the organization never agreed to automate.

| Anti-Pattern | What Goes Wrong | Why Teams Fall Into It | Better Alternative |
|---|---|---|---|
| Prompt pile | The process becomes a private collection of prompts with no shared path. | Early experiments reward individual speed. | Convert the best prompt into a documented workflow with inputs, checks, and owners. |
| Trust by fluency | Output is accepted because it reads confidently. | Fluent text feels finished and lowers reviewer suspicion. | Require evidence, tests, or source checks before acceptance. |
| Hidden context | The model depends on unstated knowledge from one operator. | Experts forget how much they are carrying in their heads. | Make context sources explicit and attach them to each run. |
| Action before evidence | The workflow changes state before quality is known. | Teams want automation to remove waiting. | Generate recommendations first, then gate actions through checks and approval. |

The action-before-evidence anti-pattern is the one that deserves the most caution in infrastructure and security work. It is reasonable to ask AI for a proposed patch, a risk summary, or a troubleshooting plan. It is not reasonable to let the workflow change production state before the team knows whether the proposal is valid. AI-native work should make evidence easier to collect, not make evidence optional.

Patterns should be documented in a way that new team members can test. If a workflow says it uses draft-then-verify, the document should identify what counts as a draft, what checks must pass, who can override a failure, and where the final artifact is stored. If a workflow says it retrieves sources, it should identify which repositories, indexes, tickets, or documents are eligible sources. This level of detail keeps patterns from becoming slogans that mean different things to different operators.

Anti-patterns often survive because they are socially convenient. It is easier to praise a fast draft than to ask who verified it. It is easier to trust the person who built the prompt than to require the process to be repeatable without them. It is easier to add another retry than to admit the target is poorly chosen. A mature team treats those moments as design signals. Friction is not always waste; sometimes it is the workflow revealing that trust has not been earned yet.

When you review an AI workflow, look for the point where responsibility becomes explicit. If every step says "the system does this," but no step names who approved the goal, who owns the context, who accepts the final artifact, or who handles failure, the workflow is incomplete. Responsibility is not a decorative governance layer added after the technical design. It is part of the technical design because it determines what happens when the workflow is wrong.

One useful review exercise is to ask how the workflow would fail quietly. Could it use stale source material while still producing confident summaries? Could it route an urgent request into a low-risk path? Could it keep retrying until cost spikes without improving quality? Could it pass schema validation while violating policy intent? These questions help you find missing gates before the workflow becomes trusted enough to cause larger problems.

## Decision Framework

Use a decision framework when you are deciding whether a task deserves an AI workflow, a manual checklist, or ordinary automation. AI is useful when the input contains natural language or messy variation, the output can be constrained, and verification is practical. Traditional automation is often better when the input and output are already structured and the rules are deterministic. Manual work remains appropriate when the consequences are high and the judgment cannot yet be reduced to a reliable rubric.

```text
Start
  |
  v
Is the task recurring and valuable?
  |-- no --> Keep it manual or exploratory
  |
 yes
  v
Can the output be specified and checked?
  |-- no --> Improve the process before adding AI
  |
 yes
  v
Is the action high risk or state changing?
  |-- yes --> Require deterministic gates and named approval
  |
 no
  v
Can failures be detected and revised cheaply?
  |-- no --> Use sampling, escalation, or a manual workflow
  |
 yes
  v
Build a bounded AI workflow with logging and review
```

This flowchart deliberately slows the decision down before implementation begins. Recurrence matters because workflow design has a maintenance cost. Checkability matters because AI output without verification becomes a trust problem. Risk matters because state-changing workflows need stronger gates than drafting workflows. Cheap failure detection matters because a workflow that can only be evaluated after damage occurs is not ready for automation.

| Decision Question | AI Workflow Is Promising When | Prefer Another Approach When |
|---|---|---|
| Input shape | Inputs are varied but belong to a known task family. | Inputs are fully structured and deterministic rules are enough. |
| Output shape | The output can be defined, reviewed, and revised. | No one can agree what a good output looks like. |
| Verification | Tests, source checks, schemas, or reviewers can catch failures. | The only check is "the model seemed confident." |
| Risk | The workflow drafts, recommends, or handles low-risk changes. | The workflow would make high-impact decisions without approval. |
| Ownership | A named owner can maintain prompts, context, and gates. | The workflow would be launched and forgotten. |

When in doubt, reduce the workflow's authority before increasing its autonomy. Ask the model to prepare a recommendation instead of taking action. Ask it to extract structured data instead of deciding policy. Ask it to draft a change instead of applying the change. These reductions are not signs of weak AI adoption. They are signs that the team understands the difference between accelerating work and surrendering responsibility.

For the module's core example patterns, the research-support path looks like this, with source gathering and human source review acting as the trust-building checkpoints around the model's summary draft:

```text
question -> gather source material -> AI summary -> human source check -> revision -> publish
```

The coding-support path has the same shape, but it uses engineering checks instead of source review, so tests, linting, build results, and human code review become the evidence gates before merge:

```text
task -> code/context -> AI proposal -> tests/lint/build -> human review -> merge
```

The shape changes, but the principle does not: no high-trust output without a matching verification step. In research work, the verification step asks whether claims are supported by visible sources. In coding work, it asks whether the patch satisfies tests, linting, build constraints, and review expectations. In operational work, it may ask whether a dry-run passes, a policy engine accepts the change, and a named owner approves the action.

This framework also helps you diagnose failures after a workflow launches. If output quality drops, inspect the context bundle, generation prompt, verification gates, revision loop, and ownership model separately. Do not blame the model first just because the model produced the visible artifact. Many AI failures are workflow failures: stale sources, hidden requirements, missing tests, unclear approval rules, or a revision loop that feeds the model vague criticism instead of actionable evidence.

The framework should be revisited after real runs, not treated as a one-time approval form. Early runs teach you which inputs are messier than expected, which checks reject useful output, which failures require escalation, and which pieces of context the model actually needs. That feedback should change the workflow document. If the document never changes after repeated use, either the team is not learning from runs or the workflow is not being inspected seriously.

A good workflow review asks for examples, not just intent. Show a passing run, a failing run, a revised run, and an escalated run. The passing run proves the happy path is understandable. The failing run proves the gates catch meaningful defects. The revised run proves feedback is actionable. The escalated run proves humans know when and how to intervene. These examples are more useful than abstract claims because they expose the workflow's behavior under ordinary pressure.

This is also where AI workflow design connects to team culture. If the organization rewards speed while ignoring evidence, people will route around checks. If it treats every failure as blame, people will hide workflow problems instead of improving them. If it values visible reasoning, teams will write better rubrics, preserve better traces, and make clearer approval decisions. The technical design and the human incentives must support each other, or the workflow will drift toward whatever behavior gets rewarded.

The final test is whether another competent person can run the workflow without guessing. They should know what input to collect, what context to attach, what the model is allowed to produce, what checks must pass, what happens after failure, and who accepts the final output. If they need private knowledge from the original prompt author, the workflow is not finished. It may still be a useful experiment, but it is not ready to become a shared operating habit.

## Did You Know?

- Kubernetes server-side dry-run has been generally available since Kubernetes 1.18, which means workflows can often ask the API server whether an object would be accepted before changing live cluster state.
- The NIST AI Risk Management Framework 1.0 was released in January 2023 and organizes risk work around Govern, Map, Measure, and Manage functions that map cleanly to workflow ownership and verification.
- OpenAI structured output features can constrain model responses to a supplied schema, which is useful when an AI workflow must hand data to downstream automation instead of a human reader.
- Kube-linter checks Kubernetes YAML for common configuration and security issues before deployment, making it a practical example of a deterministic gate after AI-generated manifest drafting.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Starting with a model choice instead of an output contract | New tools make model selection feel like the main design decision. | Define the final artifact, acceptance criteria, owner, and failure path before choosing model settings. |
| Treating a prompt library as a workflow | A prompt can hide context, judgment, and review steps inside one person's habit. | Document the input, context sources, draft step, verification gate, revision rule, and final approver. |
| Skipping verification because the output is fluent | Fluent prose or clean-looking code creates false confidence. | Add source review, schema validation, tests, linting, dry-run checks, or named approval before acceptance. |
| Giving the model too much unfiltered context | Teams fear missing information, so they paste everything. | Retrieve the smallest relevant context bundle and keep evidence visible for reviewers. |
| Letting AI change state before quality is known | Automation demos reward speed and hide operational consequences. | Generate recommendations or patches first, then require deterministic gates and approval for state changes. |
| Failing to assign workflow ownership | Everyone assumes someone else will update prompts, sources, rubrics, and alerts. | Name owners for context, verification, final decisions, monitoring, and rollback. |
| Building novelty workflows for one-off tasks | A new capability makes a demo feel strategically important. | Prioritize recurring, valuable tasks where output shape and verification are stable. |

## Quiz

<details>
<summary>Your team wants to use AI for release summaries. Each engineer has a different prompt, different context, and a different review habit. What is the main workflow problem, and what should the team define first?</summary>

The main problem is that the team has private prompting habits rather than a shared workflow. A workflow needs a defined input, context bundle, expected output, verification step, revision path, and owner. The team should first define the output contract and acceptance criteria, because those choices determine what context is needed and what checks must exist. After that, prompt design becomes one implementation detail inside the workflow instead of the workflow itself.
</details>

<details>
<summary>An AI-generated incident summary sounds polished, but reviewers later discover that two claims were not supported by the source notes. Which missing gate caused the failure?</summary>

The missing gate is source-visible verification. The workflow allowed a fluent draft to move forward without checking each important claim against the supplied evidence. A stronger design would require the summary to cite or reference source material, mark uncertain claims, and route unsupported statements into revision. The lesson is that polished language is not evidence; verification must make the evidence inspectable.
</details>

<details>
<summary>Your team proposes `task -> AI writes code -> merge` for small bug fixes because the patches usually look correct. How should you redesign the path?</summary>

Redesign it as `task -> code/context -> AI proposal -> tests/lint/build -> human review -> merge`. The model can produce a useful first patch, but tests and linters should catch mechanical and behavioral issues before a reviewer spends time on judgment. Human review remains important because tests rarely express every architectural or maintainability concern. The workflow earns trust by combining automated evidence with accountable approval.
</details>

<details>
<summary>A platform team wants AI to restart Pods automatically whenever logs contain repeated errors. What makes this a weak workflow target, and what safer version could you design?</summary>

The target is weak because raw logs are noisy, the action changes production state, and the workflow may not distinguish transient symptoms from root causes. A safer version would classify the symptom, collect corroborating signals, prepare a recommendation, and run deterministic checks before any action. High-impact remediation should require escalation or approval unless the team has strong evidence that the automated action is safe. The safer workflow uses AI to prepare analysis, not to bypass operational judgment.
</details>

<details>
<summary>You have a transcript-to-status-update workflow with a stable output template and manager review. What makes this a strong AI workflow candidate?</summary>

It is strong because the input is recurring, the output shape is stable, and a human reviewer can decide whether the draft is acceptable. The model handles natural-language transformation while the workflow preserves accountability through review. The risk is usually lower than state-changing automation, so the team can gain speed without removing essential oversight. The workflow should still check format, required sections, and unsupported commitments before publication.
</details>

<details>
<summary>A workflow fails intermittently after an API schema changes, but nobody knows who owns the prompt, context retrieval, or validation rule. Which design failure does this reveal?</summary>

This reveals unclear ownership. AI workflows are maintained systems, not one-time prompts, so someone must own context sources, prompt updates, validation logic, monitoring, and rollback. When ownership is implicit, drift becomes hard to diagnose because every component looks like someone else's responsibility. The fix is to assign named roles and include maintenance expectations in the workflow design.
</details>

<details>
<summary>You are choosing between full automation, AI-assisted drafting, and a manual checklist for a production security exception process. What decision rule should guide the choice?</summary>

The decision should follow risk, checkability, and accountability. A production security exception is high impact, so full automation is inappropriate unless deterministic checks and named approval are strong enough to control the risk. AI-assisted drafting may be useful for summarizing evidence and preparing a recommendation, while a human remains responsible for approval. If the team cannot define reliable checks, a manual checklist is safer until the process is clearer.
</details>

## Hands-On Exercise

In this exercise, you will design a repeatable AI workflow for a real task, with clear inputs, ownership, verification, and a revision path when output is weak. Choose a task that matters enough to repeat but is small enough to test in one sitting, such as summarizing meeting notes, drafting a weekly status update, turning a support request into a response draft, or generating a first-pass troubleshooting checklist.

- [ ] Choose one recurring task that produces a structured output. Pick something small and repeatable, then write one sentence describing why the task is worth improving and what final artifact the workflow should produce.

  <details>
  <summary>Solution guidance</summary>

  A good task might be "turn a weekly engineering meeting transcript into a project update with decisions, risks, owners, and open questions." This is better than "summarize meetings" because the output shape is specific and reviewable. Avoid tasks where the model would approve policy, change production state, or make high-risk decisions without evidence.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  mkdir -p ai-workflow-lab
  cd ai-workflow-lab
  pwd
  ```

- [ ] Write a workflow brief that defines the exact goal, inputs, output, owner, and failure handling. Create a file named `workflow-brief.md` with these fields: `Goal:`, `Inputs:`, `Output:`, `Verification:`, `Owner:`, and `If output is weak or wrong:`.

  <details>
  <summary>Solution guidance</summary>

  Keep each field concrete enough that another person could repeat the workflow. The `Inputs:` field should name visible source material rather than "whatever the requester provides." The `Verification:` field should describe how the output will be checked, and the failure-handling field should say whether the workflow revises, escalates, or stops.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  grep -E '^(Goal|Inputs|Output|Verification|Owner|If output is weak or wrong):' workflow-brief.md
  ```

- [ ] Map the workflow as a sequence of explicit steps. Use a structure like `goal -> context -> AI draft -> verification -> revision -> final output`, then adapt it to your chosen task so each step is concrete.

  <details>
  <summary>Solution guidance</summary>

  For a status-update workflow, the sequence might be `meeting transcript -> extract decisions and risks -> AI draft update -> source check against transcript -> owner revision -> manager approval -> publish`. Notice that the AI draft is only one step. The verification and approval steps make the workflow repeatable and accountable.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  cat workflow-brief.md
  ```

- [ ] Add human and tool checkpoints to the workflow. Mark where a human defines the goal, where AI produces a draft, where a tool or checklist verifies the result, and where a human approves or rejects the output.

  <details>
  <summary>Solution guidance</summary>

  You might mark the requester as responsible for the goal, the model as responsible only for a draft, a checklist as responsible for source and format checks, and the project owner as responsible for final approval. If the task has low risk, approval may be quick. If the task can create commitments or operational changes, approval should be explicit.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  grep -n 'Verification:' workflow-brief.md
  grep -n 'Owner:' workflow-brief.md
  ```

- [ ] Create a simple verification rubric with pass/fail checks. Add at least three checks such as `matches requested format`, `uses visible source material or provided context`, `contains no unsupported claims`, and `is approved by the named owner`.

  <details>
  <summary>Solution guidance</summary>

  A rubric should be specific enough to reject a plausible but wrong draft. For example, "good quality" is too vague, while "every decision in the update appears in the transcript or is marked as an open question" is checkable. Write the checks so a teammate can apply them without asking what you meant.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  grep -nE 'pass|fail|format|source|owner' workflow-brief.md
  ```

- [ ] Run one dry run of the workflow with a sample input. Use a short example input, produce a draft with AI, evaluate it against your rubric, and record whether it passed, failed, and what should change before the next run.

  <details>
  <summary>Solution guidance</summary>

  The dry run should reveal at least one improvement. Maybe the input was missing the audience, the output template was too vague, or the verification rubric did not mention source visibility. Record the failure honestly, because the point of the dry run is to improve the workflow before it becomes someone else's default process.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  printf '%s\n' 'Sample run completed' >> workflow-brief.md
  tail -n 10 workflow-brief.md
  ```

- [ ] Revise the workflow to remove one weakness. Improve one of these areas: unclear input, missing verification, unclear ownership, no revision path, too much hidden context, or action before evidence.

  <details>
  <summary>Solution guidance</summary>

  The revision should change the workflow, not just the wording of the prompt. For example, add a required source list, name the approver, include a failed-check revision rule, or downgrade an automated action into a recommendation. A good revision makes the next run easier to evaluate than the first run.
  </details>

  Use these verification commands to confirm the lab artifact exists and still matches the workflow requirement before moving to the next task.
  ```bash
  grep -nE 'revision|verify|owner|input' workflow-brief.md
  wc -l workflow-brief.md
  ```

Use the following success criteria to decide whether your workflow is ready for another person to try. These are deliberately written as checkboxes because a workflow that cannot pass simple visible criteria is not ready for automation or delegation.

- [ ] The workflow has a clearly stated goal, inputs, output, owner, verification step, and fallback path.
- [ ] The workflow includes both an AI draft step and a separate verification step.
- [ ] At least one human responsibility is explicit.
- [ ] A dry run was completed and used to improve the workflow.
- [ ] The final workflow is specific enough that another person could repeat it without guessing.

## Sources

- [A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)
- [NIST AI RMF Playbook](https://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbook)
- [Advancing accountability in AI](https://oecd.ai/en/accountability/)
- [OpenAI function calling guide](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI structured outputs guide](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI evals guide](https://platform.openai.com/docs/guides/evals)
- [OpenAI prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Kubernetes server-side dry-run](https://kubernetes.io/docs/reference/using-api/api-concepts/#dry-run)
- [Kubernetes validating admission policies](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/)
- [KubeLinter documentation](https://docs.kubelinter.io/)
- [OWASP Top 10 for Large Language Model Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)

## Next Module

Continue to [Human-in-the-Loop Habits](../module-1.4-human-in-the-loop-habits/) to practice the review habits that keep AI-assisted work accountable after a workflow is designed.
