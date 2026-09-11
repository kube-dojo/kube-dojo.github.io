---
title: "AI Agents and Assistants"
slug: ai/ai-native-work/module-1.2-ai-agents-and-assistants
sidebar:
  order: 2
revision_pending: false
---

> **Complexity**: `[QUICK]`
>
> **Time to Complete**: 30-40 min
>
> **Prerequisites**: Practical AI tool use, basic command-line comfort, and basic Kubernetes vocabulary

---

## Learning Outcomes

- Compare chat, assistant, copilot, and agent workflows by autonomy, tool access, and accountability.
- Design an agent delegation ladder with review gates, rollback, and scoped Kubernetes permissions.
- Diagnose when an agent adds coordination cost versus when an assistant or script is safer.
- Implement a bounded hands-on evaluation for an agentic workflow using protected tool specifications and success criteria.

## Why This Module Matters

Hypothetical scenario: your platform team is reviewing a proposal for an AI incident helper. One version answers questions about logs, another drafts remediation commands for a human to review, and a third can inspect a Kubernetes 1.35 cluster, call tools, and prepare a change request. All three are described as "an agent" in the meeting, so the team begins debating model quality before agreeing on what the system is allowed to do.

That naming problem is not cosmetic. If a tool only summarizes a postmortem, a wrong answer is usually an information quality problem. If a tool can open tickets, query production metrics, apply manifests, or rotate a secret, the same wrong reasoning can become an operational change. The engineering question shifts from "did the model sound useful?" to "what loop did we create, what permissions did we grant, and who owns the decision when the loop reaches a risky step?"

This module gives you a practical vocabulary for that decision. You will separate chat, assistants, copilots, and agents by the shape of the loop they run, not by the brand name on the product. You will also build a safer delegation ladder for choosing the minimum useful level of autonomy, then test that ladder against concrete scenarios where an agent either helps or creates unnecessary coordination cost.

The important habit is to define the workflow before choosing the tool. A mature team does not ask whether it can use an agent everywhere. It asks where delegated action reduces toil, where bounded tool use improves feedback, and where human review remains the cheapest control. That discipline keeps AI-native work from turning into either fear of automation or blind trust in automation.

> **Go deeper:** For harness layers, system-of-record, and how agent loops sit inside controlled runtimes, see [Harness Fundamentals](/ai/ai-engineering-foundations/module-3.1-harness-fundamentals-layers-and-system-of-record/).

## The Autonomy Spectrum

People often use the words chatbot, assistant, copilot, and agent as if they were interchangeable. They are related, but they are not the same operational pattern. The difference is not whether a model is impressive or whether the interface looks conversational. The difference is who drives the loop, which context enters the system, which tools can be called, and what happens after the model produces an answer.

At the lowest level, chat helps you think. You bring a question, paste context, read the answer, and decide the next step yourself. That is useful for explaining a concept, drafting a note, or comparing two options. The model may be wrong, but it does not act unless you copy its output somewhere else. The human remains the loop runner, the tool caller, and the accountable operator.

An assistant helps inside a bounded workflow. It may have durable instructions, access to approved documents, or a narrow task context such as a repository, ticket, meeting transcript, or runbook. It can produce drafts and recommendations with less copy-paste because the workflow already supplies relevant context. Even then, the assistant usually stops at suggestion or preparation, leaving execution and approval with a person.

A copilot is an assistant embedded in a working environment. In an IDE, terminal, documentation editor, or support console, it can use ambient context such as the current file, selected text, open buffers, nearby code, or recent commands. That integration makes it feel smarter than a blank chat window, but it also creates a trap: local context is not global understanding. A copilot may understand the line you are editing while missing deployment policy, data migration risk, or the production runbook.

An agent helps carry out a bounded process. It can keep a goal active across steps, choose tools, observe results, and decide what to do next. That does not make it magic, and it does not remove the need for design. It means the workflow now contains a stateful execution loop, so the team must define allowed tools, stopping conditions, review gates, logging, and rollback paths.

The distinction lies primarily in the loop structure and degree of tool integration. A chatbot follows a request-response pattern where the human is the iterative engine. In contrast, an agent has a reasoning loop, often implemented with tool-calling frameworks, where the model determines which subtasks are necessary to reach a high-level goal, executes them using external APIs, observes the results, and then decides the next step. This shift from output generation to goal pursuit changes your role from direct operator to supervisor of a constrained process.

The following protected trace shows the shape of that loop. Treat it as an execution trace, not as a shell script to paste into a terminal. The model moves from observation to hypothesis to another tool call, and the safety question is whether each action is allowed, visible, and reversible.

```bash
# Example Agent Execution Trace (Internal Logic)
THOUGHT: Pod 'api-gateway' is in ImagePullBackOff. 
ACTION: kubectl describe pod api-gateway
OBSERVATION: "Failed to pull image 'registry/api-gw:v1.2': 401 Unauthorized"
THOUGHT: The registry secret is likely expired or missing in this namespace. 
ACTION: kubectl get secret regcred
OBSERVATION: "Error from server (NotFound): secrets 'regcred' not found"
ACTION: kubectl get secret regcred --namespace=shared-services
FINAL_RESPONSE: The image pull failed because 'regcred' is missing. I found it in 'shared-services'; shall I clone it here?
```

Notice the last sentence in the trace. The safer design stops before mutation and asks for approval because cloning a registry secret changes cluster state. A weaker design would let the agent copy credentials across namespaces without checking policy, ownership, or secret rotation practice. The model did not become dangerous because it used the word "agent"; it became operationally relevant because the loop reached an action boundary.

Pause and predict: what do you think happens if this same loop can run `kubectl apply` without a namespace allowlist, review gate, or change log? The likely failure is not just a bad answer. It is an untracked production change whose intent is hard to reconstruct after the fact. That is why the autonomy spectrum is also a responsibility spectrum.

The useful mental model is delegated responsibility. Chat helps you think, assistants help you work, copilots help inside a live environment, and agents help carry out a bounded process. Each step can be valuable, but each step also increases the need for constraints, observability, review, and recovery. A team that defines those controls early can adopt agents gradually instead of discovering trust boundaries during an incident.

This spectrum also helps with purchasing and platform decisions. A vendor may market a product as agentic because it can call tools, but your internal workflow may use only the assistant portion of that product. Another tool may look modest because it appears in a terminal, yet it may be able to execute commands, write files, and retry after errors. Classification by capability prevents the team from importing someone else's vocabulary without importing the safety model that vocabulary requires.

The same vocabulary improves communication between engineers, security reviewers, and product owners. When an engineer says "assistant," a reviewer should know that the system prepares or explains work but does not complete the operational step. When someone says "agent," the next questions should be about tool identity, approval boundaries, logs, and termination. Clear language makes reviews faster because the group can discuss the actual risk instead of debating a vague label.

## Tool Access Changes The Failure Mode

The most important difference between an assistant and an agent is not personality or fluency. It is the presence of tools that convert text into effects. A model without tools can still mislead a reader, but the reader must perform the next action. A model with tools can query a cluster, update a ticket, call an API, create a pull request, or trigger a workflow. That changes the blast radius of ordinary model mistakes.

Tool access is usually described as function calling, tool calling, actions, plugins, or connectors. The mechanism varies by platform, but the design problem is consistent. You present the model with named capabilities, structured arguments, and descriptions of when each capability should be used. The surrounding application receives the requested call, validates it, executes deterministic code, and returns an observation for the next model step.

The model should never be treated as the security boundary. It can choose from tools, but ordinary software must enforce what tools exist, what arguments are valid, what identity is used, and what rate limits apply. If the tool wrapper accepts arbitrary shell text, the model has been given an overly broad interface. If the wrapper exposes a narrow operation such as "list pods in approved namespaces," the agent can still help while remaining easier to reason about.

Technically, this shift relies on structured tool-calling architectures. The agent is provided with a registry of executable functions, often defined with JSON schemas, which it can invoke when its internal logic deems them necessary. Unlike a passive assistant, the agent proactively manages data transformations between these tools, handling some of the glue work that previously required a human engineer to copy results from one terminal window to another.

```json
{
  "thought": "The user wants to troubleshoot the 'auth-service' pod. I will first list all pods in the 'security' namespace to identify the exact name and status.",
  "tool": "kubectl_get_pods",
  "parameters": {
    "namespace": "security",
    "label_selector": "app=auth-service"
  },
  "expected_outcome": "List of pod names and their current phases."
}
```

The JSON-like trace is useful because it separates reasoning from the executable operation. The reasoning may be incomplete, but the tool request can still be checked. Does the namespace exist in the allowlist? Is the label selector restricted enough? Is this a read-only tool? Does the user have authority to request this data? Those checks belong in deterministic application code rather than in a hope that the model will always remember policy.

In Kubernetes work, tool boundaries should map to real operational boundaries. A read-only diagnostic helper might list pods, fetch events, inspect workload status, and retrieve logs with redaction. A change-preparation assistant might generate a patch and run dry-run validation, but stop before applying it. A higher-autonomy agent might open a pull request, run tests, and request approval from a code owner. Production mutation should remain the last rung, not the default starting point.

Before running this thought experiment, decide what output you expect from each tool call: should the system return raw cluster data, a summarized observation, or a redacted result with policy annotations? Raw output gives the model more context, but it may expose secrets or noisy details. Summaries reduce risk, but they can hide the signal needed for diagnosis. The right answer depends on the workflow and the data classification.

The safest teams treat every tool as a small API product. It has a purpose, an input schema, an authorization rule, an audit log, and a clear failure mode. If the model asks for a forbidden action, the tool should refuse with a useful explanation. If the tool times out, the agent should not keep retrying forever. If a tool returns unexpected data, the agent should surface uncertainty instead of pretending the observation confirms its plan.

This is also where cost and latency enter the design. A chat answer may take one model call, while an agent loop can take many calls plus external tool requests. That overhead is worthwhile when the task has repeatable structure and real information gathering. It is wasteful when the human already has the needed context or when a simple script would produce the same result deterministically. Tool access is valuable only when the loop earns its complexity.

Tool design should also account for data minimization. A log reader does not always need entire pod logs, and a ticket summarizer does not always need every comment ever written on a project. Smaller tool responses reduce token cost, lower the chance of leaking sensitive data into prompts, and make the agent's reasoning easier to inspect. When the tool can return a focused observation with links to fuller evidence, reviewers get both safety and traceability.

Versioning matters because tools become contracts. If you change a tool from read-only diagnosis to mutation, or broaden a namespace filter, existing prompts and approval assumptions may no longer be valid. Treat those changes like API changes: document them, review them, and test them with representative runs. A surprising tool upgrade can silently turn a safe assistant workflow into a higher-risk agent workflow.

The strongest tool wrappers make invalid requests boring. If the agent asks to inspect a namespace outside its scope, the wrapper should return a clear policy denial rather than a vague failure. If the agent asks for a destructive operation through a read-only tool, the wrapper should state that the operation is unavailable. Clear denials teach the loop where the boundaries are and give human reviewers evidence that policy enforcement is working.

## Assistants, Copilots, And Agents In Kubernetes Work

Kubernetes makes the distinction concrete because the same natural-language request can map to very different workflows. "Help me debug this deployment" could mean explain a YAML error, summarize a set of events, prepare a safe diagnostic command, or independently inspect a cluster. The right pattern depends on risk, ambiguity, available context, and whether the task requires action across multiple steps.

Use chat when the work is exploratory thinking. If you are learning why a Deployment creates ReplicaSets, comparing rolling update settings, or asking for a plain-language explanation of an error, chat is enough. You provide the context and decide whether the answer fits. The model is a tutor or drafting partner, not an operator with access to the system you are discussing.

Use an assistant when the workflow is bounded and the human remains the integrator. Examples include summarizing incident notes, reorganizing a runbook, explaining a manifest, checking whether a policy description is clear, or drafting a pull request description from a known diff. These tasks benefit from guidance and context, but they do not require autonomous action. The assistant reduces cognitive load without taking control of the environment.

Use a copilot when local context is the main advantage. An IDE copilot can infer naming conventions from nearby code, suggest tests beside the function under edit, or help complete a manifest while you keep your hands in the editor. Its weakness is the same as its strength: it optimizes around nearby context. You still need review for cross-service contracts, security policy, deployment order, and other concerns outside the current window.

Use an agent when the work has multiple steps, a stable goal, repeatable structure, clear tool boundaries, and meaningful feedback after each step. Inspecting a codebase, proposing a patch, running tests, and summarizing the result can fit that pattern. Gathering artifacts for a recurring compliance report can fit it too. Applying a fixed review rubric across many modules with checkpoints is another reasonable agentic workflow because the task repeats and the stop conditions can be defined.

Avoid agents when the task is mostly one-shot reasoning, the requirements are still vague, the cost of wrong action is high, or human ownership is unclear. Those conditions do not prove an agent is impossible, but they mean the process design is not ready. If nobody can say what the agent may do, what it must not do, and who approves the next step, the missing piece is governance rather than model capability.

The protected assistant example below shows a bounded helper workflow. It asks for help generating filtering logic, but the engineer remains responsible for deciding whether the result is correct and where to run it. That is a very different risk profile from an agent that can execute the query, infer a remediation, and modify cluster state.

```bash
# Using an assistant to generate complex filtering logic
# Task: List all images used in the 'production' namespace, sorted by node
kubectl get pods -n production -o json | assistant-tool "Generate a
jsonpath that returns a list of unique container images
mapped to the nodeName they are running on."
```

This matters during incidents because pressure encourages over-delegation. A team sees a slow manual process and assumes an agent should take over. Sometimes that is correct, especially for repetitive evidence gathering. Sometimes the better answer is a read-only assistant that prepares context faster while leaving remediation decisions with the incident commander. The difference is not philosophical; it is a choice about failure containment.

Kubernetes 1.35 also reminds us that the platform itself is a changing API surface. A helpful agent must know which cluster version, admission controls, resource policies, and controller conventions it is operating against. If the model relies on stale assumptions or generic Kubernetes advice, tool validation becomes more important, not less. The cluster should reject invalid resources, but a mature workflow catches many mistakes before reaching the API server.

Which approach would you choose here and why: an assistant that drafts a NetworkPolicy explanation, a copilot that edits the YAML beside you, or an agent that validates the policy against a staging cluster and opens a review request? The best answer depends on whether the goal is learning, editing, or executing a repeatable validation loop. Naming that goal first prevents the team from treating autonomy as a status symbol.

A practical Kubernetes rollout often uses several patterns at once. Chat may help a new engineer learn why readiness probes matter, a copilot may help write the probe configuration, an assistant may draft the pull request explanation, and an agent may run validation across a set of services. That combination is normal. The mistake is assuming one pattern should replace all the others. Mature AI-native work composes different levels of autonomy around the risk of each step.

The same task can also move along the spectrum over time. During early exploration, a human may paste logs into chat to learn the failure shape. After the team sees the same failure repeatedly, it may create an assistant that gathers the right fields and drafts a diagnosis. If the diagnosis becomes reliable and the tool boundaries are narrow, the team may later build a read-only agent. The workflow earns autonomy by proving itself in safer forms first.

This is why "human in the loop" needs precision. A human who receives a final answer with no evidence is not meaningfully in the loop. A human who sees the observation, proposed action, risk, rollback note, and policy check can make a real decision. The quality of the checkpoint matters more than the slogan. Review gates should be designed for fast comprehension, not ceremonial approval.

## Designing Bounded Agent Loops

An agent loop should be designed like a small control plane. It has inputs, allowed actions, observations, state, and termination rules. The model supplies flexible reasoning, but the surrounding system supplies the rails. Without those rails, the agent can chase irrelevant evidence, repeat expensive calls, or treat a weak hypothesis as permission to act.

The common reasoning pattern is sometimes called reason and act. The agent observes a goal, reasons about the next useful step, calls a tool, receives an observation, and updates its plan. This is powerful because the model can adapt when reality disagrees with the first guess. It is also risky because every iteration creates another opportunity for drift, cost, data exposure, or unauthorized action.

The protected YAML block below sketches a narrow tool specification. The tool validates a manifest against a target cluster schema. It does not apply the manifest, create a namespace, or open a firewall. That narrowness is a feature. A validation tool can safely appear earlier on the delegation ladder because its failure mode is bounded and its output can be reviewed.

```yaml
# Example of a Tool Specification for an AI Agent
name: k8s_resource_validator
description: "Validates a Kubernetes manifest against a target cluster's API schema."
parameters:
  type: object
  properties:
    manifest_yaml:
      type: string
      description: "The full YAML content of the resource to validate."
    namespace:
      type: string
      description: "The namespace context for validation."
  required: ["manifest_yaml"]
```

A well-designed tool specification does three jobs. First, it tells the model what capability exists, so the agent can choose it when appropriate. Second, it tells the application how to validate arguments before running deterministic code. Third, it tells reviewers what the agent could have done when they inspect logs after a run. If a tool description is vague, all three jobs become harder.

Bounded loops need explicit stop conditions. A diagnostic agent might stop after collecting events, logs, rollout status, and one hypothesis. A code agent might stop after creating a patch, running the repository's tests, and summarizing failures. A reporting agent might stop after preparing a draft and listing missing data. Without a stop rule, "try another thing" becomes the default, and the system can consume time or mutate state without improving confidence.

Human-in-the-loop gates should appear where the type of risk changes. Reading logs and proposing an explanation may need lightweight review. Writing to a repository, opening an external ticket, changing a cluster object, or notifying customers needs stronger approval. The gate should be part of the workflow, not an afterthought added when somebody feels nervous. Good gates are specific: approve this patch, in this namespace, for this reason, with this rollback path.

Rollback design is part of agent design. If an agent prepares a patch, it should also explain what previous state it observed and how to revert the change. If it opens a pull request, it should include test results and any commands it did not run. If it cannot determine a safe rollback, that uncertainty is a reason to stop. The goal is not to make the agent timid; the goal is to make delegated action inspectable.

Observability matters because agent failures are often process failures. You need logs that show the user request, selected tools, arguments after validation, tool results, policy denials, approvals, and final output. Those logs should avoid exposing secrets, but they must be detailed enough to reconstruct the path. If a reviewer sees only the final answer, the workflow has no audit trail.

Idempotency is another practical requirement. If a tool creates or updates resources, retries must not duplicate work or leave half-finished objects behind. Kubernetes controllers already teach this lesson: desired state loops work because repeated reconciliation should converge rather than multiply side effects. Agent tools should borrow that discipline. A retry should be safe, or the tool should clearly say that it is not retryable.

When you design an agent, start with the smallest useful loop. Give it read-only tools first, then add preparation tools, then add review actions, and only later consider limited execution in low-risk contexts. This ladder keeps trust calibrated. It also creates evidence for the next decision: if the read-only loop cannot produce reliable diagnoses, granting write access will not fix the underlying design.

State management is part of that smallest useful loop. The agent should know what goal it is pursuing, which observations belong to the current run, and which assumptions are still unproven. It should not carry stale conclusions from a previous incident into a new one unless the workflow explicitly provides that context. Run-scoped memory keeps an agent from sounding confident because it remembers an old pattern that no longer fits.

Error handling should be designed before success demos. If a tool returns a permission error, the agent should report the denied action and stop or choose an allowed diagnostic path. If a validation tool returns a schema error, the agent should explain the failing field rather than hallucinating a cluster problem. If a network call fails, the loop should avoid repeated blind retries. These behaviors are ordinary software reliability concerns, applied to model-driven control flow.

Evaluation should measure process quality, not just final answers. A good test set includes easy cases, ambiguous cases, policy-denied cases, stale-context cases, and cases where the correct behavior is to stop. For each run, reviewers can score whether the agent chose relevant tools, respected boundaries, preserved evidence, and surfaced uncertainty. That form of evaluation is more useful than asking whether the final prose sounded confident.

## Patterns & Anti-Patterns

For a quick module, the most useful pattern is the bounded delegation pattern. Choose a stable workflow, define the goal in operational terms, expose only the tools needed for that goal, and require a human checkpoint before state changes. This pattern works because it narrows the agent's world. The model can still adapt inside the loop, but the system around it prevents the loop from becoming an all-purpose operator.

A second pattern is read-only first. Before an agent can apply a patch, let it gather evidence, explain its reasoning, and produce a proposed change. Review the quality of those runs as you would review a junior operator's notes. If the evidence is consistently relevant and the proposed actions are conservative, you have a basis for adding more capability. If the evidence is noisy, the next step is better tools or prompts, not broader permissions.

A third pattern is tool-specific accountability. Every tool should have an owner, an audit trail, input validation, and a documented failure mode. This sounds heavy for a small prototype, but it prevents prototypes from quietly becoming production pathways. When a tool has an owner, somebody can update it when Kubernetes behavior changes, credentials rotate, or policy rules become stricter.

The main anti-pattern is autonomy theater. A team wraps a simple checklist in an agent loop because "agent" sounds advanced, even though a deterministic script would be faster, cheaper, and easier to test. The result is a workflow with more moving parts and less predictability. If the task has fixed inputs, fixed steps, and no need for language understanding, write the script and use AI to document or review it.

Another anti-pattern is permission-first design. The team grants broad access so the agent can "figure it out," then tries to add safety with prompt instructions. That reverses the proper order. Permissions should come from the workflow's needs, not from the model's curiosity. A prompt can request caution, but authorization must be enforced by the tool layer, identity system, and environment policy.

A subtler anti-pattern is passive copilot acceptance. The user receives a plausible suggestion inside the editor and merges it as if the tool had evaluated the whole system. Copilots are excellent at local acceleration, but they are not automatically reviewers, architects, or release managers. The better alternative is to treat copilot output like a draft: inspect it, test it, and run the same review process you would use for human-written changes.

The final anti-pattern is invisible work. An agent that gathers data, makes decisions, and reports only a polished final answer may feel efficient, but it leaves reviewers unable to distinguish evidence from inference. A safer agent reports the important observations, rejected options, policy constraints, and remaining uncertainty. Transparency is not extra paperwork; it is how the team decides whether the delegation is earning trust.

One more useful pattern is reversible preparation. Let the agent do work that creates reviewable artifacts: a patch, a report draft, a test result summary, or a proposed runbook update. Those artifacts can be inspected, discussed, changed, and rejected without touching production. Reversible preparation converts language-model flexibility into ordinary engineering review material, which is exactly where teams already have strong habits.

Another anti-pattern is treating approval as a single broad permission. "You may fix the cluster" is too vague to be a safe gate. A better approval is narrow and contextual: "you may open a pull request that changes this manifest, for this service, based on this validation result." Narrow approvals reduce ambiguity for the agent and reduce review burden for the human because the allowed action is easy to verify.

## Decision Framework

Start with the task shape. If the request is a one-time explanation, use chat or a simple assistant. If the task needs local context but the human is editing and reviewing, use a copilot. If the task repeats across many items, needs tool calls, and benefits from observing intermediate results, consider an agent. If the task changes production state, require stronger gates no matter which interface you use.

Then classify the risk. Low-risk work includes drafting, summarizing, formatting, and read-only inspection of non-sensitive data. Medium-risk work includes preparing pull requests, running tests, creating tickets, or validating manifests in staging. High-risk work includes production writes, credential handling, customer notifications, billing changes, and destructive operations. The higher the risk, the more the system needs scoped identity, review, audit logs, and rollback.

Next, ask whether language reasoning is actually needed. Agents are useful when the workflow requires judgment over messy inputs, such as logs, code, tickets, documentation, or partial observations. They are less useful when the work is already deterministic. If a cron job, controller, policy engine, or script can do the job more reliably, use that deterministic tool and reserve AI for explanation, triage, or exception handling.

Finally, choose the minimum effective delegation level. The ladder is chat only, assistant with suggestions, assistant with bounded tool use, agent with explicit review gates, and agent with limited autonomous execution in low-risk contexts. Skipping rungs creates trust problems because the team has no evidence about how the system behaves under smaller responsibilities. Climbing gradually lets you learn from safe failures.

Use this sentence as a design check: "The system may do X with Y tools until Z condition, then it must ask A person for B approval." If you cannot fill in that sentence, the workflow is not ready for an agent. If you can fill it in clearly, you have the outline of a reviewable design.

The framework also applies after deployment. Review agent runs the way you review incidents and pull requests. Look for unnecessary tool calls, weak evidence, missing citations, repeated retries, vague final summaries, and approvals that were too broad. A delegation system should improve over time because the team can see where the loop helped and where it wasted attention.

When the decision is close, prefer the less autonomous option and collect evidence. A good assistant workflow can later become an agent workflow if the need for repeated tool use becomes obvious. A premature agent workflow is harder to simplify because users may begin depending on behavior that was never properly governed. Conservatism here is not fear of automation. It is the same staged rollout thinking engineers already use for infrastructure changes.

You can also compare the workflow to existing Kubernetes control patterns. Controllers are trusted because their desired state, permissions, reconciliation rules, and events are inspectable. An agent should not receive more trust than a controller while offering fewer guarantees. If the agent's desired state is vague, its permissions are broad, and its events are missing, the system needs more engineering before it deserves operational authority.

## Did You Know?

- In 2023, the ReAct paper popularized combining reasoning traces with external actions, which helped many engineers describe agent loops as observe, reason, act, and observe again.
- Kubernetes 1.35 continues the pattern that cluster behavior depends on API version, admission control, and controller reconciliation, so agent tools should validate against the actual target environment.
- Many production-grade agent systems use narrow tools rather than open-ended shell access because structured inputs are easier to authorize, log, test, and rate-limit.
- Anthropic's agent guidance and OpenAI's practical guide at https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/ both emphasize workflow fit: added autonomy is valuable when the task benefits from tool use, state, and reviewable intermediate steps.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Calling every conversational AI system an agent | The interface is chat-shaped, so people classify by appearance rather than loop structure. | Classify by autonomy, tool access, state, and accountability before choosing controls. |
| Giving an agent broad production access during a pilot | Teams want to demonstrate value quickly and assume prompt instructions are enough. | Start read-only, add narrow tools, and require approval before any production mutation. |
| Treating copilot suggestions as architecture review | The suggestion appears inside the workflow and feels context-aware. | Review copilot output against system-level constraints, tests, and deployment policy. |
| Using an agent for a deterministic checklist | Agent branding feels more modern than a script. | Use scripts, controllers, or policy engines for fixed workflows, and use AI for messy interpretation. |
| Hiding intermediate observations from reviewers | Teams optimize for a clean final answer and forget auditability. | Log tool calls, validated arguments, observations, denials, approvals, and uncertainty. |
| Adding write tools before stop conditions | The team focuses on capability and postpones workflow boundaries. | Define stop rules, retry limits, escalation paths, and rollback notes before enabling writes. |
| Letting the model enforce security policy | It is tempting to encode policy in the prompt because it is fast to change. | Enforce policy in deterministic tool wrappers, identity systems, admission controls, and review gates. |

## Quiz

<details>
<summary>Your team wants an AI system to summarize an incident transcript, reorganize the timeline, and draft clearer follow-up notes, but it must not update tickets or call external tools. Which pattern should you choose?</summary>

Choose an assistant rather than an agent. The workflow is bounded, language-heavy, and valuable without autonomous action. Chat could also help, but an assistant with access to the transcript and note template fits better because it can work inside the reporting workflow. An agent would add coordination cost without a tool-use benefit.
</details>

<details>
<summary>A platform engineer proposes a system that detects a failed deployment, inspects rollout status, fetches logs, compares the error with recent configuration changes, proposes a patch, runs tests, and then asks for approval. Is this chat, assistant, copilot, or agent work?</summary>

This is agent work because it has a stable goal, multiple steps, tool calls, observations, and a review gate before action. The approval step is important because it marks the boundary between diagnosis and mutation. A copilot might help edit the patch, and an assistant might explain the logs, but the described loop carries a process across several tool-backed steps.
</details>

<details>
<summary>Your manager asks for an agent to explain a single YAML validation error in a manifest that is already pasted into the chat. What should you diagnose about the request?</summary>

Diagnose this as a mismatch between task shape and autonomy. A one-time explanation does not need stateful tool use, repeated observations, or delegated action. A chat prompt or bounded assistant is cheaper and easier to review. Using an agent here adds ceremony and may distract from the real goal, which is understanding and fixing the manifest.
</details>

<details>
<summary>An IDE copilot suggests a change to a Kubernetes deployment file, and a developer assumes the suggestion accounts for production policy, rollback order, and cross-service behavior. What is the failure mode?</summary>

The failure mode is passive copilot acceptance. The copilot may have useful local context, but local context is not the same as full architectural review. The developer should treat the suggestion as a draft, then check policy, tests, deployment sequencing, and review requirements. The problem is not using a copilot; the problem is assigning it accountability it does not have.
</details>

<details>
<summary>An agent asks to copy a registry secret into a namespace after observing an ImagePullBackOff. What review gate should exist before the action proceeds?</summary>

The gate should require a human to approve the exact namespace, secret source, reason for copying, and rollback or rotation plan. Copying a secret changes cluster state and may violate credential ownership rules. A read-only diagnosis can be automated earlier, but credential movement deserves explicit approval and audit logging. The safer agent design stops at a proposed action unless policy allows that exact operation.
</details>

<details>
<summary>Your team has a recurring compliance report that requires gathering approved metrics, checking them against a rubric, drafting a summary, and asking a reviewer to approve the final text. Why might an agent be reasonable here?</summary>

An agent may be reasonable because the task is repeatable, tool-backed, and structured around intermediate evidence. The goal is stable, and the workflow can stop at a human review gate before publication. The team can expose narrow read tools for approved metrics and require the agent to list missing data. That makes delegated work useful without giving it uncontrolled authority.
</details>

<details>
<summary>A prototype agent repeatedly calls diagnostic tools after receiving noisy results and never reaches a clear stopping point. What design change should you make?</summary>

Add explicit stop conditions, retry limits, and escalation rules. The agent should know how many observations are enough for a first hypothesis and when uncertainty must be reported to a human. More tool calls do not automatically create better diagnosis; they can increase cost and noise. A bounded loop should stop, summarize evidence, and ask for direction when confidence remains low.
</details>

## Hands-On Exercise

Exercise scenario: you are advising a team that wants to introduce AI help into a Kubernetes 1.35 operations workflow. They have three candidate tasks: explaining manifests to new engineers, preparing pull requests for recurring policy updates, and diagnosing failed rollouts in a staging cluster. Your job is to classify each task, set the minimum useful delegation level, and define controls before any production access is considered.

Start by creating a small evaluation note in your own editor. You do not need cluster access for this exercise because the goal is workflow design, not command execution. For each candidate task, write the task goal, the data the system needs, the tools it may use, the point where it must stop, and the person who approves the next action. This is the same design discipline you would apply before wiring real tools into an agent loop.

For the rollout diagnosis task, be especially concrete about boundaries. A safe first version might read Deployment status, ReplicaSet status, pod events, and recent logs from a staging namespace, then produce a hypothesis and suggested next command. It should not restart workloads, edit manifests, copy secrets, or change image tags. If your design includes those actions, move them behind a separate approval gate and explain the rollback path.

For the policy update task, distinguish preparation from execution. An agent can search for affected manifests, draft a patch, run validation, and open a review request without merging anything. That still saves time because the repetitive evidence gathering is delegated. The human reviewer remains accountable for accepting the change, and the repository's normal tests and branch protections remain part of the control system.

For the manifest explanation task, resist the urge to overbuild. A good assistant with a small amount of context may be the best tool because the learner needs explanation, not autonomous action. If the team later notices repeated questions, it can add retrieval over approved documentation or examples. That is still assistant territory unless the system begins choosing tools and carrying a goal across steps.

- [ ] Compare chat, assistant, copilot, and agent workflows in a delegation matrix for the three candidate tasks.
- [ ] Design an agent delegation ladder with review gates, rollback notes, and scoped Kubernetes permissions for the rollout diagnosis task.
- [ ] Diagnose where an agent adds coordination cost and where an assistant or deterministic script is safer.
- [ ] Implement a bounded evaluation plan for an agentic workflow using protected tool specifications and measurable success criteria.
- [ ] Record success criteria for audit logs, stop conditions, human approvals, and evidence quality before any production mutation.

<details>
<summary>Suggested solution</summary>

For manifest explanation, choose chat or a bounded assistant because the goal is learning and review, not action. For recurring policy updates, choose an assistant with bounded tool use or an agent that prepares pull requests and runs tests, then stops for review. For staging rollout diagnosis, choose a read-only agent that can inspect rollout status, events, and logs, then propose next steps without applying changes. Production mutation should remain out of scope until the team has evidence from safe runs.
</details>

<details>
<summary>Success criteria checklist review</summary>

A strong answer names the loop driver, tool boundary, approval owner, and stop condition for each task. It avoids broad production access during the pilot and does not rely on prompt instructions as the security boundary. It also distinguishes between deterministic steps, such as running a fixed validation command, and language-heavy steps, such as summarizing noisy logs. The best answers include rollback notes even when the first version is read-only because rollback thinking improves later design.
</details>

## Sources

- [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK: Agents](https://openai.github.io/openai-agents-python/agents/)
- [OpenAI Agents SDK: Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Developers: Apps SDK](https://developers.openai.com/apps-sdk)
- [LangChain agents overview](https://docs.langchain.com/oss/python/langchain/agents)
- [Microsoft Semantic Kernel agents](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/)
- [Kubernetes documentation: API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/)
- [Kubernetes documentation: Authorization overview](https://kubernetes.io/docs/reference/access-authn-authz/authorization/)
- [Kubernetes documentation: Using RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Kubernetes documentation: Auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)
- [Kubernetes documentation: Server-side dry run](https://kubernetes.io/docs/reference/using-api/api-concepts/#dry-run)

## Next Module

Continue to [Designing AI Workflows](../module-1.3-designing-ai-workflows/) to turn the delegation ladder into complete AI-native workflow designs.
