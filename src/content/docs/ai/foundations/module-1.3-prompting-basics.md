---
title: "Prompting Basics"
slug: ai/foundations/module-1.3-prompting-basics
sidebar:
  order: 3
---

> **AI Foundations** | Complexity: `[QUICK]` | Time: 30-40 min

## Learning Outcomes

- Design a prompt contract that separates task, context, constraints, and output format for a technical request.
- Compare weak and improved prompts by identifying which missing instruction caused the output to drift.
- Diagnose prompt failures that come from missing evidence, unsafe assumptions, unclear format, or the wrong workflow.
- Implement an iterative prompting loop that records changes, verifies claims, and stops when the answer is reviewable.

## Why This Module Matters

Hypothetical scenario: a junior engineer asks an assistant, "Help me fix this broken deployment," then pastes a few log lines and waits. The assistant gives confident advice, but the advice assumes a Kubernetes cluster, administrator access, and a rolling deployment even though none of that was stated. The problem is not that prompting is mystical or that the model ignored a secret phrase. The problem is that the request never told the model what job it was doing, what evidence it was allowed to use, what assumptions were forbidden, or what shape a useful answer had to take.

Prompting is disciplined task framing. A prompt works like a ticket written for a very fast teammate who has no shared memory of your environment unless you provide it. If the ticket says "fix auth," the teammate must guess which service, which failure, which users, and which success condition matter. If the ticket says "diagnose why the login pod returns HTTP 503 after the 10:20 UTC deployment, using only the events and readiness probe output below, and return three likely causes with one verification command each," the work becomes bounded enough to inspect.

This module teaches the first practical layer: writing prompts that produce reviewable work instead of lucky prose. You will practice turning vague requests into prompt contracts, choosing when to use examples, asking for structured output, and deciding when a second prompt is better than one enormous prompt. The next module focuses on verification, so this one stops at the handoff point: the answer should be clear enough that a human or tool can check it.

> **Go deeper:** For the full prompt-engineering spine (contracts, reasoning prompts, libraries, and safety), see [Prompt Fundamentals](/ai/ai-engineering-foundations/module-1.1-prompt-fundamentals/) in [AI Engineering Foundations](/ai/ai-engineering-foundations/).

## A Prompt Is a Small Contract

A prompt is not a spell, and treating it like one creates bad habits quickly. The useful mental model is a small contract: it names the work, provides the evidence, states the boundaries, and describes the deliverable. The model still generates probable text rather than guaranteed truth, but a contract narrows the problem enough that the answer can be judged. Without that narrowing, the model fills empty space with default assumptions from common examples it has seen before.

The four fields below are enough for most beginner prompting tasks. The task says what operation you want performed, such as summarize, compare, diagnose, draft, refactor, or classify. The context supplies the material the model should use, including audience, system details, constraints from your environment, or source text. The constraints tell the model what not to do, which assumptions to avoid, and what level of detail belongs in scope. The output format makes the answer usable by a person or a script instead of leaving the model to choose a shape on its own.

```text
+------------------+--------------------------------------------------+
| Prompt Contract  | Question it answers                              |
+------------------+--------------------------------------------------+
| Task             | What work should be performed?                   |
| Context          | What facts, audience, and source material matter? |
| Constraints      | What limits, exclusions, or rules apply?          |
| Output format    | What should the finished answer look like?        |
+------------------+--------------------------------------------------+
```

Consider the weak request "Explain Kubernetes." It is not wrong in a moral sense; it is just under-specified. The model has to guess whether the answer should help a product manager, a Linux administrator, a developer using Docker, or an engineer preparing for a certification exam. Those guesses change the vocabulary, the examples, and the objects introduced first. A better contract removes the guesswork before the model starts writing.

```text
Task: Explain Kubernetes.
Context: Audience is a junior engineer who knows Linux processes and Docker containers but has never used a cluster.
Constraints: Use plain language. Avoid cloud-provider-specific services. Do not discuss service meshes yet.
Output format: Give a 250-word explanation, one analogy, and a table mapping Pod, Node, Deployment, and Service to familiar Docker or Linux ideas.
```

The improved prompt does not guarantee a perfect answer, but it gives you specific criteria for review. If the response mentions a service mesh, it violated a constraint. If it skips the table, it violated the output format. If it explains etcd consensus before Pods and Nodes, it missed the audience context. A useful prompt therefore creates a way to evaluate the answer, not just a way to ask the question.

> **Pause and predict:** If you remove only the audience line from the improved Kubernetes prompt, which part of the answer is most likely to change first: vocabulary, output format, or forbidden topics? Write your guess before reading on, because the answer reveals which part of the contract was doing the most steering.

The vocabulary usually changes first because audience context tells the model how much background knowledge to assume. Output format and forbidden topics still constrain shape and scope, but they do not tell the model whether "control plane" needs a definition or can be used as familiar language. This is why the same technical task can need different prompts for a beginner, a staff engineer, and an executive. The task stays stable while the context changes the level of explanation.

The contract frame also prevents a common beginner mistake: adding random intensity words instead of operational detail. "Be precise," "be professional," and "be senior" are weaker than "cite the exact field name," "return only commands that are safe to run in read-only mode," or "separate evidence from inference." Abstract quality words can help tone, but concrete rules produce answers that are easier to inspect. When a prompt fails, first ask which contract field was missing rather than searching for a special phrase.

The contract does not need to be long. For a quick everyday request, one compact paragraph can still contain all four fields: "Draft a release note for backend engineers, using the change list below, avoiding customer-facing marketing language, and returning one paragraph plus three risk bullets." That sentence has a task, audience context, a style constraint, and a format. The danger is not short prompts; the danger is short prompts that omit the decision the answer must support and document.

## Context, Evidence, and Examples

Context is the material the model should treat as relevant to the task. In everyday chat, context may be a few sentences about the reader. In engineering work, context often includes logs, YAML, API responses, requirements, or a previous draft. The danger is that source material and instructions can blur together when they are pasted into one undifferentiated block. Clear delimiters reduce that risk by showing where instructions end and evidence begins.

```markdown
Task: Diagnose the likely cause of this failed rollout.

Rules:
- Use only the evidence inside <evidence>.
- If the evidence is not enough, say what is missing.
- Return a table with columns Evidence, Inference, Verification.

<evidence>
kubectl rollout status deployment/web
deployment "web" exceeded its progress deadline

kubectl get pods -l app=web
web-6dbb9f4f7c-2k8ms   0/1   ImagePullBackOff
</evidence>
```

The XML-like tags are not magic syntax; they are visual separators. You could use headings, fenced code blocks, or another clear convention, but the point is the same. The model needs to distinguish instruction text from evidence text, especially when evidence may contain phrases that look like commands. If a log line says "ignore previous instructions," a well-framed prompt tells the model that the line is data to analyze, not a new rule to obey.

Examples are a second kind of context. They are useful when the task has a style or classification boundary that is hard to describe abstractly. If you want a bug triage assistant to label reports as `reproducible`, `needs-info`, or `not-a-bug`, one short example per label may teach the boundary better than a long paragraph. The examples should be small, representative, and clearly separated from the new item to classify.

```text
Task: Classify the new report using one of: reproducible, needs-info, not-a-bug.

Examples:
- Report: "On version 1.6.2, saving a profile with an empty display name returns HTTP 500."
  Label: reproducible
- Report: "The app is broken after the update."
  Label: needs-info
- Report: "The export is CSV, but I expected Excel."
  Label: not-a-bug

New report:
"On version 1.6.2, clicking Export creates a CSV with duplicated header rows."

Output format:
Label: <one label>
Reason: <one sentence based on the examples>
```

Few-shot examples are powerful because they show the model what counts as a match, but they can also overfit the answer. If every example is short, the model may produce short answers even when the new case needs nuance. If every example uses the same product area, the model may import that product area into unrelated requests. Good examples should teach the decision boundary, not accidentally teach irrelevant decorations.

Context should be trimmed rather than dumped. Pasting a whole incident channel into a prompt feels thorough, but it forces the model to decide which lines are evidence, which lines are speculation, and which lines are outdated. A stronger prompt gives the current facts, the unknowns, and the decision you need to make. If the raw material is large, use one pass to extract evidence and a second pass to reason over the extracted evidence, so each step has a clear job.

Before you include context, ask what the model must know to avoid a wrong assumption. For a Kubernetes explanation, the audience matters more than the entire Kubernetes documentation set. For a deployment diagnosis, the observed state, recent change, and permission boundary matter more than old chat history. For a policy draft, the source policy and target audience matter more than your general frustration with the process. Context is not "everything nearby"; it is the minimum evidence needed for the task to be fair.

There is also a security reason to label evidence. Prompt injection is the pattern where untrusted text tries to become an instruction, such as a web page that tells a summarizer to reveal hidden rules or ignore the user's request. Beginners often think prompt injection is only a problem for public chatbots, but the same risk appears when an assistant reads tickets, logs, documents, or repository text. Delimiters do not solve the problem alone, but they make the intended boundary explicit enough for later guardrails and review.

When examples conflict with written rules, fix the prompt before trusting the answer. A common mistake is to say "return one sentence" and then provide examples that are full paragraphs. Another is to ask for neutral incident language while every example blames a team by name. Models learn from both the explicit instruction and the pattern of examples, so examples should obey the same rules you want applied to the new input. If they do not, the examples are not helpful context; they are competing instructions.

## Constraints Shape the Search Space

Constraints tell the model where not to go. A task and context may still leave too many acceptable answers, especially when the model has seen many common patterns for the topic. If you ask for deployment advice without constraints, it may suggest restarting Pods, changing resource requests, using a cloud-specific service, or installing a new tool. Some of those suggestions might be reasonable in another environment and wrong in yours.

Useful constraints are specific enough to be checked. "Be concise" is weaker than "use at most five bullets." "Be safe" is weaker than "do not suggest commands that change cluster state." "Use good sources" is weaker than "cite only vendor docs or project documentation, and mark any uncited claim as an inference." A reviewer can test the second version of each pair. The first version mostly relies on the model's private interpretation of quality.

```yaml
task: Review a Kubernetes Pod manifest for beginner-level security risks.
context:
  audience: "new platform engineer"
  kubernetes_version: "1.35"
constraints:
  - "Do not recommend third-party scanners."
  - "Do not assume cluster-admin access."
  - "Only discuss fields visible in the manifest."
  - "Mark any missing evidence as 'not provided'."
output_format:
  type: "markdown_table"
  columns:
    - Field
    - Risk
    - Why it matters
    - Safer setting
```

Negative constraints deserve special attention because they prevent plausible but unusable answers. If your organization does not allow external SaaS tools, say so. If the user only has read permissions, say so. If the answer must avoid a topic because it belongs in a later module, say so. Without negative constraints, the model may choose the most common internet answer, and the most common internet answer is often written for a different environment.

Output constraints are where prompting starts to become engineering rather than conversation. A Markdown table is easier to scan than a paragraph when you need to compare choices. JSON is useful when a program will parse the result, but only if the task really needs machine consumption and the model or API mode can enforce it. A short explanation plus a checklist is useful when the reader must act. The format should serve the next step, not merely make the answer look tidy.

Uncertainty is another constraint, and it is one of the most valuable for technical work. Models are usually optimized to be helpful, so they may complete a missing story unless told to stop at the evidence. A prompt can require the answer to separate observed facts, inferences, and missing information. That does not make the answer true, but it makes uncertainty visible enough for a human to decide what to check next.

```text
Return three sections:

Observed facts:
- Only statements directly supported by the provided evidence.

Likely inferences:
- Reasonable explanations, each tied to one observed fact.

Missing information:
- Specific data needed before recommending a fix.
```

> **Pause and predict:** In the rollout prompt above, what happens if you ask for "the fix" before asking for observed facts and missing information? The likely failure is not bad grammar; it is premature certainty, where the answer jumps from `ImagePullBackOff` to a single remediation without checking registry credentials, image name, tag existence, or node network access.

The right constraint depends on the failure mode you are trying to prevent. If answers are too generic, add audience, environment, and non-goals. If answers are hard to parse, add a format. If answers invent missing facts, add evidence rules and an uncertainty section. If answers are too long, add a length limit and priority order. Prompting improves when each new constraint is attached to a specific observed failure, not when constraints are piled on because they sound professional.

Constraints can also conflict, and conflict is easier to see when rules are concrete. "Explain all risks in detail" and "keep the answer under one hundred words" may both sound reasonable until a manifest has six risky fields. The model may satisfy the length limit by hiding important risk, or satisfy the detail request by violating the length limit. When constraints compete, give a priority rule such as "prioritize correctness over brevity" or "if more than three risks exist, list the three highest-impact risks and say how many were omitted."

## Make Assumptions Visible

Assumptions are the quiet part of most prompt failures. A model may assume the cluster is managed by a cloud provider, the user has administrator access, the codebase uses a common framework, or the incident is urgent enough to justify disruptive action. Those assumptions are not always unreasonable, but they become dangerous when they are invisible. A prompt that asks the model to name assumptions turns hidden defaults into reviewable text.

An assumption register is useful when the task has missing details but you still want progress. Instead of pretending the missing details do not matter, ask the model to separate required assumptions from optional assumptions. Required assumptions are the facts that must be true for the answer to be valid. Optional assumptions are convenience choices that can be changed later. This distinction helps a reviewer see whether the answer is stable or fragile.

```text
Task: Propose a first-pass troubleshooting plan for the failed API Deployment.

Context:
- The new Pod is in CrashLoopBackOff.
- Logs have not been collected.
- The engineer has namespace-level read access only.

Constraints:
- Do not assume root cause.
- Do not include commands that mutate cluster state.
- Make assumptions explicit.

Output format:
1. Required assumptions
2. Optional assumptions
3. Read-only checks in safe order
```

This prompt is different from simply asking for uncertainty. Uncertainty says what is not known; an assumption register says what the answer is temporarily relying on. For example, "assuming `kubectl logs` is allowed in this namespace" is a required assumption for a logs-first plan. If that assumption is false, the plan must change. By naming it, the model gives the operator a specific permission check rather than burying the dependency inside a command list.

Assumption handling also helps when prompts cross team boundaries. A platform engineer may assume that every service has readiness probes, while an application engineer may know that a legacy service does not. A security reviewer may assume production data is in scope, while the prompt writer only meant a development cluster. Stating assumptions in the output lets those readers correct the premise before debating the recommendation. This saves time because the disagreement moves from "the answer feels wrong" to "assumption two is false."

You can also forbid certain assumptions before they appear. If the model often suggests tools your organization does not use, say "do not assume third-party scanners are available." If it often jumps to administrator actions, say "assume namespace-level read access only." If it often invents missing logs, say "if logs are absent, list the exact log command rather than describing log contents." These are not style preferences; they are environment boundaries that keep the answer grounded.

Assumptions should be removed once evidence arrives. If a follow-up provides the actual log output, the next prompt should tell the model to replace the earlier assumption with observed evidence. Otherwise, the conversation can carry stale assumptions forward even after better information appears. A good refinement might say, "Use the logs below as evidence and remove any assumption that the container exits before binding its port unless the logs support it." That instruction keeps the prompt history from overpowering new facts.

## Iteration Beats Giant Prompts

Many learners try to write one perfect prompt that anticipates every possible edge case. That approach usually creates a long, brittle instruction block that is hard to debug. When the answer fails, you cannot tell whether the task was unclear, the context was noisy, the constraints conflicted, or the format was unrealistic. Iteration is better because each follow-up changes one thing and gives you evidence about what mattered.

An iterative loop has four steps: ask for a bounded draft, inspect the result against a standard, refine the narrowest missing piece, and verify before using the output. This is similar to writing code in small commits. A giant unreviewed patch may contain the same final logic, but small changes make defects easier to isolate. Prompting works the same way because the visible conversation becomes a change log for the model's instructions.

```text
Step 1: Draft
"Summarize this incident timeline for a junior SRE. Use only the facts below."

Step 2: Inspect
"The summary mixed confirmed facts with hypotheses. Revise it into two sections:
Confirmed facts and Open questions."

Step 3: Refine
"Add one verification command for each open question. Do not propose fixes yet."

Step 4: Verify
"Check the final version for any statement not supported by the original facts."
```

The important move is that each follow-up names the defect in the previous answer. "Try again" is usually weak because it does not say what changed. "Separate confirmed facts from hypotheses" is stronger because it adds a review rule. "Do not propose fixes yet" is stronger because it prevents the model from racing ahead. You are not negotiating with the model; you are editing the contract after inspecting a draft.

Iteration also helps control cost and attention. A single enormous prompt may include instructions that compete with each other, especially if you ask for analysis, generation, critique, and formatting all at once. Smaller prompts let you decide whether the first step is good enough before paying attention to the next step. In a coding workflow, this might mean asking for a test failure summary first, then a patch plan, then a focused code change, then a review checklist.

Keep a short prompt log when the work matters. The log does not need to be formal; three lines are enough: original task, defect found, refinement added. This habit turns prompting from improvisation into a reviewable process. If a teammate asks why the final answer says "insufficient evidence," you can point to the refinement that required missing information to be explicit. If a later model version behaves differently, the log gives you the smallest reproducer.

Iteration has a stopping rule. Stop when the answer is clear enough to verify or use for the next human decision. Do not keep polishing tone after the facts, assumptions, and format are right. Extra rounds can make an answer smoother while adding accidental changes. In technical work, a plain answer with visible uncertainty is often better than an elegant answer that has been rewritten so many times that its evidence trail is hard to see.

One useful iteration habit is to change only one prompt dimension at a time. If you add new evidence, change the output format, and alter the audience in the same follow-up, you will not know which change improved or damaged the answer. A focused refinement such as "keep the facts unchanged, but convert the next steps into a table with Owner and Evidence columns" is easier to audit. It also teaches the model that parts of the draft are accepted while one part needs repair.

## Match the Prompt to the Work Product

Different work products need different prompt contracts. A diagnostic prompt should slow the model down and make evidence visible. A transformation prompt should preserve meaning while changing shape. A generation prompt should define acceptance criteria because the output did not exist before. A critique prompt should name the standard used for review. If you use the same generic prompt for all four jobs, you will get answers that sound similar even though the risks are different.

The table below is a starting point for choosing the prompt shape. It is not a closing checklist; it is a routing table. Before writing a prompt, decide which work product you actually need, then choose the contract fields that reduce the most likely failure for that work. The same source material can produce a summary, a diagnosis, a decision record, or a set of next checks, and each of those outputs needs different boundaries.

| Work product | Main risk | Prompt move that helps |
|---|---|---|
| Diagnosis | Unsupported root cause | Require observed facts, inferences, missing evidence, and verification steps |
| Transformation | Meaning changes during reformatting | State invariants that must not change and ask for a change log |
| Generation | Plausible but unsuitable new content | Provide acceptance criteria, audience, non-goals, and examples |
| Critique | Vague preference masquerades as review | Provide a rubric, severity levels, and evidence requirements |
| Plan | Steps appear in the wrong order | Require dependencies, prerequisites, and stop conditions |

Diagnostic prompts are evidence-first because their biggest failure is premature certainty. If you paste a stack trace and ask "what is wrong," the model may jump to the most familiar cause. A stronger diagnostic prompt asks for facts visible in the trace, possible causes ranked by evidence, and the next command or file to inspect. That structure does not make the diagnosis correct, but it prevents the answer from hiding the gap between symptom and cause.

Transformation prompts are different because the input already contains the meaning. The model's job is to preserve that meaning while changing form, such as turning meeting notes into an action list or turning a paragraph into a release note. The prompt should name invariants: do not add owners, do not change dates, do not invent deadlines, and keep uncertainty markers such as "maybe" or "unconfirmed." Without invariants, a clean transformation can silently become an edited story.

Generation prompts need acceptance criteria because there is no original answer to preserve. If you ask for a runbook section, define who will use it, what incident state it covers, which commands are allowed, and what success looks like. Generation also benefits from non-goals because models often include adjacent material. A runbook prompt that says "do not include long-term prevention work" is less likely to mix immediate response steps with a post-incident improvement plan.

Critique prompts need a rubric because "review this" invites personal preference. A useful critique prompt might say: "Review this prompt for missing context, unverifiable claims, unsafe assumptions, and output ambiguity. Classify each issue as blocking or advisory, and quote the phrase that caused it." That instruction turns a vague review into a structured inspection. It also keeps the model from rewriting the prompt before it has explained what is wrong.

Planning prompts need dependencies and stop conditions. If you ask for "a migration plan," the model may produce a sequence that looks orderly while skipping prerequisites such as backups, access checks, or rollback ownership. A stronger prompt asks for phases, prerequisites for each phase, validation after each phase, and a condition that stops the plan before the next step. Planning is not only a list of actions; it is an ordering problem with risk gates.

```text
Task: Review the prompt below as a critique task, not a rewrite task.
Context: The prompt will be used by a junior engineer during incident communication.
Constraints:
- Find missing context, unsafe assumptions, unclear output format, and unverifiable claims.
- Quote the exact phrase that creates each issue.
- Do not rewrite the whole prompt unless asked.
Output format:
Table with columns: Issue, Severity, Evidence, Suggested narrow fix.
```

Notice that this prompt says "critique task, not a rewrite task" because critique and generation are easy to confuse. If the model rewrites immediately, the learner may get a better-looking prompt without understanding why it improved. When the work product is review, the explanation of the defect is part of the deliverable. When the work product is generation, the finished artifact is the deliverable. Choosing the work product first keeps those outputs separate.

> **Pause and predict:** If a transformation prompt changes an incident note from "registry access has not been checked" to "registry access failed," which contract field would you tighten? The best answer is not output format; it is the invariant that uncertainty markers and unverified statements must be preserved during transformation.

Prompt templates are useful only when they leave room for the work product to change. A template that always includes role, task, context, constraints, and format is fine, but a template that always asks for root cause, remediation, and prevention will distort tasks that are not root-cause analyses. Keep templates small enough that you can remove irrelevant fields. The goal is to remember the contract parts, not to force every request through the same ceremony.

## Use Prompt Reviews Before Reuse

Prompts that will be reused deserve a short review before they become team habits. A one-off prompt can be messy if the human is watching closely, but a saved prompt in a runbook, support macro, or automation script will be copied under pressure. Small ambiguities then repeat across many requests. Reviewing the prompt itself is cheaper than reviewing every bad answer it produces later.

A prompt review asks different questions from an answer review. The reviewer is not judging whether a particular output is correct; they are checking whether the prompt gives enough information for a future output to be judged. Does the task name the action? Is the source material clearly separated from instructions? Are forbidden assumptions stated? Is the expected output shaped for the next user or system? Can a reviewer tell when the model disobeyed the prompt?

```text
Prompt review checklist:
- Task verb is specific.
- Evidence boundary is visible.
- Audience or consumer is named.
- Constraints are checkable.
- Output format matches the next step.
- Missing information has an allowed response.
```

This review is especially important when a prompt moves from chat into automation. In chat, a human can notice that the answer ignored a constraint and ask a follow-up. In automation, the answer may flow into a ticket, report, or script input before anyone reads it closely. A reusable prompt should therefore be more explicit about format, uncertainty, and forbidden actions than a casual exploratory prompt. The less human attention sits between output and use, the stronger the contract must be.

Prompt reviews also help teams avoid superstition. If a saved prompt contains a phrase like "be world class" and nobody can explain which failure it prevents, remove it or replace it with a checkable rule. If a phrase is useful, the review should reveal why: perhaps it sets audience level, limits scope, or requires evidence. A prompt library should read like operational guidance, not like a collection of charms.

## When Prompting Is the Wrong Fix

Some failures cannot be solved by better wording. If the source material is absent, the model cannot recover the missing facts by being prompted harder. If the workflow has no verification step, a polished prompt can still produce a polished mistake. If the task requires current system state, private data, or a real command result, the model needs tools or fresh evidence rather than a more elaborate instruction. Prompting is a control surface, not a substitute for the rest of the system.

A useful diagnostic question is: "Would a careful human be able to answer this from the same information?" If the answer is no, the prompt is not the main bottleneck. A human cannot diagnose a production outage from "the app is slow" without metrics, logs, recent changes, and scope. A model cannot do it either. The right next step is to gather evidence or narrow the question, not to add words like "deeply analyze" or "think carefully."

There are also cases where the task should be split across tools. A model can explain a Terraform plan, but the plan should still come from `terraform plan`. A model can help interpret test failures, but the tests should still run. A model can draft a Kubernetes manifest, but schema validation and cluster policy checks should still happen outside the prompt. Good prompting asks the model to do the language and reasoning work that fits it, while deterministic tools handle the facts they are built to check.

Use the table below when a prompt keeps failing. It is not a general "best practices" summary; it is a fault isolation guide. Each row identifies a different root cause and a different fix. If two rows apply, address the evidence or workflow issue before polishing phrasing, because unclear facts will keep contaminating otherwise well-structured prompts.

| Symptom | Likely root cause | Better next move |
|---|---|---|
| The answer invents environment details | Missing context or evidence | Provide the relevant facts and forbid unsupported assumptions |
| The answer is correct but unusable | Output format does not match the next step | Specify a table, checklist, JSON shape, or decision record |
| The answer gives a fix too early | No uncertainty or evidence rule | Require observed facts, inferences, and missing information first |
| The answer changes style every run | Audience and examples are unstable | Add a target reader and one or two representative examples |
| The answer cannot be trusted | No external verification workflow | Run commands, check docs, or require citations before use |

This boundary matters because prompt superstition wastes time. Teams sometimes collect phrases that appear to work once, then paste them into every request. The phrases may hide the real issue for a while, but they do not create evidence, access, tests, or ownership. A strong operator treats a prompt failure as a diagnostic signal: either the contract is incomplete, the evidence is missing, the task belongs to a tool, or the workflow needs a human decision.

## Worked Example: From Vague Request to Reviewable Prompt

Exercise scenario: you want help writing a short internal note about a failed image rollout. The first draft request is "Write a message explaining the deployment failure." That request leaves the audience, evidence, tone, and next action unstated. The model might apologize, blame the wrong component, recommend restarting everything, or write a dramatic incident update when you only needed a calm status note.

Start by naming the task and audience. The task is not "write something"; it is "draft a status update." The audience is not everyone; it is engineers waiting in a team channel. The evidence is limited to the rollout status and Pod state you actually have. The constraints should prevent speculation and premature fixes. The format should match the channel where the note will be pasted.

```text
Task: Draft a short internal status update about a failed deployment.

Context:
- Audience: engineers watching the #platform channel.
- Service: web.
- Evidence:
  - `kubectl rollout status deployment/web` returned "deployment exceeded its progress deadline".
  - `kubectl get pods -l app=web` showed one new Pod in ImagePullBackOff.
  - No registry logs have been checked yet.

Constraints:
- Do not blame a person or team.
- Do not claim the root cause is known.
- Do not suggest a fix yet.
- Separate confirmed facts from next checks.

Output format:
- 2 sentence status update.
- 3 bullet next checks.
```

That prompt is now reviewable. If the output says "the registry credentials are broken," it violated the evidence boundary because registry logs have not been checked. If it suggests deleting Pods, it violated the "do not suggest a fix yet" constraint. If it writes six paragraphs, it violated the output format. The contract gives you handles for correction instead of leaving you with a vague feeling that the answer is not quite right.

A reasonable answer to the prompt might be: "The `web` deployment has not completed because the new Pod is currently in `ImagePullBackOff`; the root cause is not confirmed yet. We are checking the image name, tag availability, and registry access before recommending a remediation." The next checks would be to verify the image reference in the Deployment, confirm the tag exists in the registry, and inspect pull-related events on the affected Pod.

Now make one narrow refinement. Suppose the answer is technically clear, but the channel prefers messages that include who owns the next check. Do not rewrite the entire prompt from scratch. Add one instruction: "Include an Owner column in the next-checks bullets, using Platform for manifest checks and Release Engineering for registry checks." The result should change only the next-checks section, while the confirmed facts and uncertainty remain intact.

```text
Refinement:
Revise only the next-checks list. Add an Owner field to each bullet.
Use Platform for manifest and Pod event checks.
Use Release Engineering for registry tag and registry access checks.
Keep the two-sentence status update unchanged.
```

Constraint-flip variation: if you only have two minutes before the on-call handoff, keep the same facts but optimize for investigation speed. The prompt should force triage priorities instead of exhaustive coverage, with the output still required to label uncertainty.

```text
Task: Draft a 2-minute handoff note for a failed `web` deployment.

Context:
- `kubectl rollout status deployment/web` shows a progress deadline exceeded.
- A new `web` Pod is in ImagePullBackOff.
- No logs have been collected yet.

Constraints:
- Provide exactly three next checks.
- Order checks by expected signal-to-effort from namespace read-only access.
- Do not claim the root cause or propose a fix.

Output format:
2 short bullet findings and 3 numbered next checks in this shape: [Owner] | [Command] | [Why this is highest priority].
```

This variant is not about adding more detail; it is about preserving reviewability when decision time is short and avoiding the temptation to pretend certainty.

## Did You Know?

- The 2020 GPT-3 paper reported strong few-shot behavior, which is one reason examples inside a prompt can change how a model performs a task.
- Instruction tuning with human feedback became a major reason general models became easier to steer with natural-language task framing after 2022.
- OWASP lists prompt injection as LLM01 in its 2025 Top 10 for LLM Applications, which shows that prompt boundaries are also a security concern.
- Chain-of-thought research showed large gains on some reasoning benchmarks, but production prompts often need concise private reasoning or answer-only formats rather than long visible reasoning.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Asking for "help" without naming the task | The requester knows the situation and forgets the model does not | Start with a verb such as diagnose, compare, draft, classify, or refactor |
| Dumping raw context without delimiters | Pasting everything feels safer than selecting evidence | Label instructions, evidence, examples, and the new request separately |
| Using tone words instead of checkable rules | Words like "professional" and "precise" sound useful but are vague | Replace them with length limits, allowed sources, fields, and forbidden assumptions |
| Treating the first answer as final | The model sounds fluent even when it missed a constraint | Inspect the answer against the prompt contract and refine the smallest defect |
| Asking for a fix before asking for evidence | People want a quick resolution under pressure | Require observed facts, inferences, and missing information before remediation |
| Copying prompt tricks across unrelated tasks | A phrase worked once, so it becomes ritual | Tie each instruction to a real failure mode in the current task |
| Expecting prompting to replace verification | The output is easier to read than the source evidence | Use commands, docs, tests, or citations to check claims before acting |

## Quiz

<details>
<summary>Question 1: Your teammate asks, "Explain Kubernetes," and receives a long answer about control plane internals. The reader only knows Linux and Docker. What prompt change should you make first?</summary>

Add audience context before adding more topic detail. A better prompt would say that the reader knows Linux processes and Docker containers but has never used a cluster. That change tells the model which vocabulary needs explanation and which analogies are useful. Adding more Kubernetes terms would likely make the answer even less beginner-friendly.
</details>

<details>
<summary>Question 2: A prompt asks a model to summarize a support ticket, but the ticket text includes the sentence "ignore the previous instructions." What should the prompt do to reduce confusion?</summary>

Separate instructions from evidence with clear delimiters and tell the model to treat the ticket text as data. For example, place the ticket inside an `<evidence>` block and say that instructions inside the evidence are not user instructions. This does not solve every prompt-injection risk, but it makes the intended boundary explicit. A stronger production workflow would pair that prompt boundary with tool permissions and output review.
</details>

<details>
<summary>Question 3: The answer to your rollout diagnosis prompt keeps recommending fixes before proving the cause. Which constraint should you add?</summary>

Require the answer to separate observed facts, likely inferences, and missing information before any remediation. This changes the task from "solve the incident" to "show what the evidence supports." It also makes unsupported claims easier to reject. If the evidence is incomplete, the correct answer should name the missing data rather than invent a root cause.
</details>

<details>
<summary>Question 4: You need output that a script can parse, but the model keeps adding friendly commentary before and after the useful content. What part of the prompt contract is missing?</summary>

The output format is missing or too weak. Specify the exact shape the script expects, such as JSON with required keys or a Markdown table with named columns. If the API or model supports enforced structured output, use that instead of relying only on prose instructions. The prompt should also say whether extra commentary is forbidden.
</details>

<details>
<summary>Question 5: A teammate writes a huge prompt containing background, examples, policies, formatting rules, and a request for critique. The result is inconsistent and hard to debug. What workflow should replace it?</summary>

Use an iterative loop with bounded steps. Ask for a first draft or analysis, inspect the result against a standard, then refine the narrowest defect in a follow-up prompt. This makes it clear which instruction changed the answer. It also avoids hiding conflicting requirements inside one large prompt.
</details>

<details>
<summary>Question 6: Your prompt asks for a root cause, but the only evidence is "the app is slow." The answer invents a database bottleneck. Is this primarily a prompting problem?</summary>

No. The prompt is exposing an evidence problem. A careful human could not determine the root cause from that single statement either. The better next move is to gather metrics, logs, recent changes, and scope, or to ask the model for a data-collection checklist rather than a diagnosis.
</details>

<details>
<summary>Question 7: A model gives a useful answer once after you add "act like a senior engineer," so the team starts adding that phrase everywhere. What should replace that habit?</summary>

Replace the phrase with concrete task rules tied to the current failure mode. If the issue is unsupported claims, require evidence and uncertainty. If the issue is unusable output, specify format. If the issue is wrong level, name the audience. The goal is not to find a universal phrase; it is to make each prompt reviewable.
</details>

## Hands-On Exercise

In this exercise, you will turn a vague prompt into a small prompt contract, test it against likely failure modes, and revise it once. Use any AI assistant available to you, or write the expected answers manually if you are reading offline. The point is not to get a perfect model response; the point is to practice making the prompt specific enough that you can tell whether the response followed it.

Exercise scenario: you are helping a new engineer understand a failed Kubernetes Deployment. The only evidence you have is that `kubectl rollout status deployment/api` reported a progress deadline and `kubectl get pods -l app=api` showed a new Pod in `CrashLoopBackOff`. You do not have logs yet, and you do not know the root cause.

- [ ] Write a weak one-sentence prompt that a busy engineer might actually send.
- [ ] Rewrite it using Task, Context, Constraints, and Output format.
- [ ] Add one negative constraint that prevents unsupported root-cause claims.
- [ ] Add one uncertainty requirement that forces missing information to be visible.
- [ ] Run or mentally simulate the prompt, then write one narrow refinement based on the first answer.
- [ ] Check whether the final answer separates facts, inferences, and next checks.

<details>
<summary>Solution example</summary>

A weak prompt might be: "Explain why the API deployment failed." A stronger version would say: "Task: Draft a beginner-friendly diagnosis note for a Kubernetes Deployment that failed to progress. Context: `kubectl rollout status deployment/api` reported a progress deadline, and `kubectl get pods -l app=api` showed a new Pod in `CrashLoopBackOff`; logs have not been collected. Constraints: do not claim a root cause, do not recommend a fix, and use only the evidence provided. Output format: three sections named Observed facts, Possible inferences, and Next checks, with no more than three bullets per section."

A useful refinement after the first answer might be: "Revise the Next checks section so each check names the command or evidence needed, but keep the Observed facts section unchanged." That refinement is narrow because it changes only the part that was incomplete. The final answer should state that the Deployment failed to progress and a new Pod is crashing, infer that logs and events are needed before cause can be known, and list checks such as inspecting Pod logs, describing the Pod events, and confirming recent image or configuration changes.
</details>

## Sources

- [Anthropic prompt engineering overview](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview)
- [Anthropic guidance on clear and direct prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/clear-direct)
- [Anthropic prompt structure guidance with XML tags](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#structure-prompts-with-xml-tags)
- [Anthropic jailbreak mitigation guidance](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks)
- [Google Gemini prompting strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies)
- [Google Vertex AI introduction to prompt design](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/introduction-prompt-design)
- [Microsoft Azure OpenAI prompt engineering concepts](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/prompt-engineering)
- [AWS Bedrock prompt engineering guidelines](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-engineering-guidelines.html)
- [AWS Bedrock guardrails documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165)
- [Training Language Models to Follow Instructions with Human Feedback](https://arxiv.org/abs/2203.02155)
- [Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection](https://arxiv.org/abs/2302.12173)
- [Defending Against Indirect Prompt Injection Attacks With Spotlighting](https://arxiv.org/abs/2403.14720)
- [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models](https://arxiv.org/abs/2201.11903)
- [OWASP Top 10 for LLM Applications 2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf)

## Next Module

Continue to [How to Verify AI Output](../module-1.4-how-to-verify-ai-output/).
