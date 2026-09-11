---
title: "Practical AI Tool Use"
slug: ai/ai-native-work/module-1.1-practical-ai-tool-use
sidebar:
  order: 1
revision_pending: false
---

> **Complexity**: `[QUICK]`
>
> **Time to Complete**: 35-45 min
>
> **Prerequisites**: Basic comfort with chat-based AI tools, source checking, and command-line examples

---

## What You'll Be Able to Do

- Evaluate AI tool fit by comparing task type, context depth, source needs, action rights, and risk before starting work.
- Design a smallest-safe-tool workflow that separates chat, search-grounded use, coding help, and agentic execution.
- Diagnose mismatches between reasoning-heavy, retrieval-heavy, coding, and workflow tasks before choosing a tool.
- Implement a verification plan with human review, source checks, sandbox tests, and stop conditions for high-risk work.

## Why This Module Matters

Hypothetical scenario: your team is preparing a Kubernetes 1.35 upgrade note, a support engineer asks for help explaining a failing deployment, and a manager wants the same AI assistant to rewrite the customer email, search for current release guidance, inspect a repository, and apply a fix. Each request sounds like "use AI," but each one has a different risk profile, context requirement, and verification path. If you push all of them into the same chat window, the tool may sound equally confident while being well suited for one task and poorly suited for another.

The operational problem is not that AI tools are weak; it is that teams often choose them by habit, brand, or novelty instead of by task shape. A conversational tool is excellent when you need explanation and quick iteration, but it becomes fragile when the job depends on recent sources, repository-wide context, or action inside a production environment. A coding assistant can read files and propose a patch, but it still needs tests, review, and a human decision about whether the change belongs in the system. An agentic workflow can coordinate multiple steps, but only when the goal is bounded, permissions are deliberate, and failure has a contained blast radius.

In this module, you will build a practical decision model for choosing the smallest safe tool that gives useful leverage without giving up control. The word "smallest" matters because every escalation adds cost, latency, permissions, and new ways to be wrong. The word "safe" matters because the right tool is not the one with the most impressive demo; it is the one whose output can be checked with the time, evidence, and access you actually have.

> **Go deeper:** This module stays at operator-level tool choice; for systematic prompt design see [Prompt Fundamentals](/ai/ai-engineering-foundations/module-1.1-prompt-fundamentals/) and for how applications package evidence and constraints see [Context Engineering Fundamentals](/ai/ai-engineering-foundations/module-2.1-context-fundamentals/).

## Start With The Task, Not The Tool

Many people begin with the question, "Which AI tool should I use?" That question feels practical, but it is already one step too late because it makes the tool the center of the decision. A better starting point is to name the kind of work you are doing: explanation, summarization, source discovery, drafting, rewriting, code inspection, code generation, or multi-step execution. Once the task type is visible, the tool choice becomes a consequence of the work instead of a guess based on whatever interface is open.

This task-first habit is especially important in technical work because similar prompts can require very different capabilities. "Explain why this pod is crashing" might be a teaching request if you paste a small error message, a coding request if the answer depends on application source, a search request if it depends on a recent CVE, or an operational workflow if the tool is allowed to run `kubectl` and inspect live state. The sentence looks similar, but the required context and verification path are different.

The first split to make is between reasoning-heavy work and retrieval-heavy work. Reasoning-heavy work asks the tool to combine constraints, compare tradeoffs, debug a causal chain, or propose a design. Retrieval-heavy work asks the tool to find current facts, source links, vendor guidance, or policy wording. If you use a strong reasoning model with no current sources for a retrieval-heavy task, you invite plausible but stale answers. If you use a search tool for a deep architecture tradeoff without giving it enough context, you may get citations without judgment.

The second split is context depth. Low-context tasks can fit in a normal conversation because the necessary material is short and easy to paste. Medium-context tasks may require a document, a few logs, or a short set of commands. High-context tasks, such as auditing a repository for a security pattern or understanding why a service mesh migration broke several tests, require a tool that can read the relevant files and preserve relationships between them. Copying fragments into chat creates context fragmentation, where the model loses how files, commands, and decisions connect.

Pause and predict: if you ask a general chat tool to audit a repository without giving it the repository, what kind of answer will it produce, and what evidence will be missing? The answer is usually a generic checklist with confident language but no file-level proof. That can still be useful as a planning aid, but it is not an audit. Calling it an audit would confuse a brainstorming output with verified work.

The third split is whether the tool only helps you think or is allowed to act. A tool that drafts a message has a small operational footprint because you can read the message before sending it. A tool that opens pull requests, edits configuration, runs shell commands, or calls APIs has a different accountability model. Once a tool can act, you need explicit boundaries, logging, review gates, and rollback paths because the failure mode is no longer just a bad sentence.

Here is a task model that compactly describes a multi-step root-cause analysis. Notice that the task is not assigned to one magic interface. Each step is matched to the tool that can see the needed evidence and support the next verification step.

```bash
# Example: A multi-step 'Root Cause Analysis' task definition
# 1. Observation: Pull logs from the failing pod (Tool: kubectl/Terminal)
# 2. Synthesis: Correlate logs with recent Git commits (Tool: IDE Agent with git access)
# 3. Verification: Check if the suspected library has known CVEs (Tool: Web-enabled AI)
# 4. Execution: Apply the patch and verify the build (Tool: IDE Agent + Local Compiler)
```

That example also shows why tool-hopping can be both helpful and dangerous. Moving from terminal evidence to repository analysis to current vulnerability guidance is reasonable because each step changes the evidence source. Jumping between tools because one answer feels uncertain is less useful unless you can explain what capability the next tool adds. A disciplined operator changes tools when the task boundary changes, not when the conversation becomes uncomfortable.

Think of tool choice like choosing a vehicle inside a city. Walking is often fastest for a short distance, a bicycle helps when the trip is longer, and a truck matters when you need to move heavy equipment. Using the truck for every trip creates parking problems, fuel cost, and blind spots. In AI work, agents and broad automation are the truck: powerful when the load justifies them, clumsy when the job is simply to think, search, or rewrite.

Before you choose an interface, write a one-sentence task contract. A useful contract says what evidence the tool needs, what output you expect, what the tool is not allowed to do, and how you will check the result. "Explain this error using only the pasted log and give me three likely causes" is a better contract than "fix this." "Search current vendor docs and return links with dates" is a better contract than "what changed recently?" The contract forces the task to become observable.

The contract should also name the consumer of the output. A note for your own learning can tolerate uncertainty if it clearly marks assumptions, while a runbook update for a team needs sharper wording, source links, and version constraints. A pull request suggestion needs an even stronger contract because it changes shared code. When the consumer changes, the same tool may need a different prompt, a different evidence standard, or a different review gate.

One practical way to build the contract is to write three short clauses before the prompt: "Use only," "Produce," and "Stop if." "Use only" limits the evidence source, such as a pasted log, a specific vendor page, or files in the repository. "Produce" names the artifact, such as a summary, decision table, test patch, or ranked hypothesis list. "Stop if" defines uncertainty, such as missing sources, failing commands, or a request for permissions outside the task.

This habit keeps you from confusing confidence with scope. A model can sound confident because it has completed the sentence, not because it has seen the evidence. If the contract says the tool can use only the pasted log, then an answer that speculates about hidden database state should be challenged. If the contract says the output must include official sources, then a polished answer with no URLs is incomplete rather than almost done.

## A Practical Tool Model

A practical model has four layers: chat tools, search-grounded tools, coding tools, and agentic or workflow tools. These layers are not a maturity ladder where higher always means better. They are different ways to trade context, grounding, action rights, cost, and control. Most day-to-day work should stay in the lowest layer that can answer the task with evidence you can verify.

Chat tools are best for explanation, brainstorming, outlining, and conversational refinement. They are strong when the problem is bounded by what you provide and when the output is judged by coherence, usefulness, and your own review. They are weak when the task requires strict reproducibility, current sources, hidden context, or direct action. A chat tool can help you reason about Kubernetes scheduling concepts, but it cannot inspect your cluster unless you give it the relevant evidence.

Search-grounded tools are best when freshness and source discipline matter. They should be the default for recent vendor changes, policy references, security advisories, pricing, model availability, and anything where training data may be outdated. Their weakness is that retrieval is not the same as judgment. A search-grounded answer with links can still miss the operational implication, overfit to the first result, or combine sources that apply to different product versions.

Coding tools are best when the work lives in files. They can read code, explain unfamiliar modules, propose patches, generate tests, and connect an error message to a function or configuration path. Their advantage is local context; their danger is local overconfidence. A coding assistant may produce a syntactically clean patch that ignores product intent, weakens a test, or changes a public contract unless you require targeted verification and review.

Agentic or workflow tools are best for repeated, bounded, multi-step work where the tool can observe, decide, act, and check results within a defined sandbox. They are not better chat; they are delegated process execution. A workflow that collects logs, correlates them with recent commits, searches external advisories, and proposes a patch may deserve an agentic loop because each step can be observed and checked. A one-off rewrite of a short paragraph probably does not.

The move from chat to workflow changes the safety problem. In chat, the main question is whether the answer is useful and true enough for the next human step. In workflow execution, the question becomes whether the tool should have permission to take the next step at all. That is why action-taking tools need explicit fail-safes, such as read-before-write, dry-run before apply, approval before destructive operations, and a clear condition for stopping.

This validator pattern expresses one useful boundary. It teaches a habit that transfers beyond any single vendor or interface: every proposed action should come with a validation command, and inability to validate should halt the workflow rather than encourage guessing.

```markdown
# Role: Senior Site Reliability Engineer
# Constraint: Every proposed configuration change MUST be accompanied by a 
# validation command (e.g., `kubectl diff -f ...` or `terraform plan`).
# Fail-Safe: If the tool cannot verify the environment state through a 
# non-destructive read command, it must halt and request human review.
```

Before running this, what output do you expect from a tool that follows the validator pattern during a Kubernetes manifest change? A good answer should include the proposed change, the non-destructive check, the expected signal from that check, and the point where the tool stops for human review. If the tool jumps straight from suggestion to apply, it is not following the pattern even if the proposed YAML looks reasonable.

The four layers can also be understood through the idea of context gravity. Some tasks have low gravity because the important context fits in a question. Some tasks have medium gravity because they need a few documents or logs. Some tasks have high gravity because the answer depends on a repository, an environment, or a long chain of decisions. High-gravity work should not be squeezed into a low-context tool simply because the interface is convenient.

Cost and latency matter too. A slower, more expensive reasoning model may be appropriate for a subtle design review, but it is wasteful for formatting a checklist. A fast model may be ideal for repetitive rewrite suggestions, but risky for a high-stakes incident diagnosis if it cannot inspect logs, commits, and current advisories. Good operators choose by the bottleneck: reasoning, retrieval, local context, execution, or review.

This is also where confidentiality enters the decision. If the task contains secrets, customer data, private source code, unreleased strategy, or regulated information, tool choice must include data handling and access policy. The smallest safe tool may be no external tool at all, or it may be a local tool with approved access controls. "Can this model answer?" is less important than "may this system receive the evidence it would need to answer?"

The layers become clearer when you separate capability from authority. Capability asks whether the tool can understand the task, retrieve the evidence, read the files, or execute the analysis. Authority asks whether the tool is allowed to use that capability in your environment. A model may be capable of editing Kubernetes manifests, but that does not mean it should have cluster credentials, permission to push, or permission to approve its own changes.

That distinction prevents two opposite mistakes. The first mistake is underusing a tool because you are afraid of action, even though read-only analysis would be safe and useful. The second mistake is overgranting permission because the tool produced a smart plan. A good workflow often gives high capability with low authority: read repository files, parse logs, generate a patch, and run tests, but require a human to decide whether the change should be merged or deployed.

For cloud-native work, the boundary between analysis and action should be visible in the command path. Reading manifests, describing resources, and running local validation are observational steps. Applying manifests, deleting resources, rotating secrets, and changing traffic are action steps. AI assistance can be valuable on both sides, but the checkpoint between them should be explicit. The tool should know when it is preparing evidence and when it is asking for approval to change state.

## Tool Selection Questions

After you know the task layer, ask a short set of selection questions. Is this idea generation, explanation, search, coding, or execution? Do I need sources? Do I need reproducible outputs? Is the task high-risk? Do I need the system to act, or only to help me think? These questions sound simple, but they prevent the common failure where a tool is chosen because it is impressive rather than because it fits the job.

The first question is about evidence. If the answer can be judged from general reasoning and your own expertise, chat may be enough. If the answer depends on current product behavior, vendor documentation, or a public advisory, search-grounded work is safer. If the answer depends on private files, local tests, or repository structure, a coding tool has the right shape. If the answer depends on repeated observation and action, a workflow may be justified.

The second question is about reproducibility. Some AI output is useful even when it is not exactly reproducible, such as brainstorming names for sections or generating alternative phrasings. Operational work needs a different bar because another engineer must be able to follow the evidence. For technical decisions, ask the tool to preserve commands, versions, files, URLs, assumptions, and checks. A useful answer should leave a trail that someone else can replay or challenge.

The third question is about risk. Risk is not only production access. A wrong summary sent to executives, an unsupported compliance interpretation, an invented citation, or a patch that silently weakens authorization can all cause damage. The right response to risk is not always "never use AI"; often it is "reduce permission, require sources, add review, run tests, and stop before the irreversible step." The tool should match the consequence of being wrong.

The fourth question is about action rights. A system that can read files is different from a system that can edit files, and a system that can edit files is different from one that can push code or change infrastructure. Permissions should be granted in small steps. Give read access before write access, dry-run ability before live execution, and narrow task ownership before broad autonomy. The more the tool can do, the clearer the boundary must be.

Which approach would you choose here and why: a teammate asks for help choosing between two Kubernetes autoscaling settings, but the answer depends on current cluster metrics that the AI tool cannot see? A disciplined answer might use chat to frame the tradeoffs, terminal commands to collect metrics, and a human review to decide. The AI tool can support the reasoning, but it should not pretend to know the missing measurements.

The triage example below captures a realistic distinction. A Kubernetes RBAC audit is not merely a search task, even though documentation may help. It requires reasoning over permissions, parsing structured output, and checking whether a ServiceAccount can reach privileged actions. The recommended strategy is therefore a reasoning model with an execution sandbox for analysis, not a plain conversation based on memory.

```text
# Triage Example: Selecting a tool for a Kubernetes RBAC Audit
task: "Audit ClusterRoleBindings for potential privilege escalation"
requirements:
  reasoning_density: "High" (Tracing ServiceAccount permissions to Pod execution)
  knowledge_freshness: "Medium" (RBAC primitives are stable)
  execution_layer: "High" (Requires parsing JSON/YAML output to verify logic)
recommended_strategy: "Use a reasoning model with an execution sandbox for analysis"
```

Notice the phrase "execution sandbox" rather than "production access." For analysis, a sandbox can parse JSON, compare YAML, calculate statistics, or run tests against a safe fixture. That is different from letting the tool modify the cluster. In many workflows, the best design is to give the AI enough execution ability to verify its reasoning while withholding the authority to perform irreversible operations.

Another useful question is whether the work is one-time or repeatable. A one-time explanation rarely needs automation because the overhead of designing a workflow is greater than the task. A weekly review that collects the same signals, checks the same sources, and produces the same decision log may deserve a reusable workflow. Repetition alone is not enough, though. The steps must be stable enough to encode, and ownership must be clear enough to review.

Finally, ask what a good failure looks like. A good chat failure is easy to spot because you can ask follow-up questions or check a source. A good coding-tool failure is caught by tests, linting, code review, or a small diff. A good workflow failure stops early, reports what it tried, preserves logs, and asks for human input. If you cannot describe the safe failure mode, the tool probably has too much autonomy for the current task.

You should also ask what evidence would change your mind. If no possible output would change the decision, then the AI step may be performative rather than useful. If a source-grounded tool finds a vendor deprecation notice, that might change a guidance document. If a coding tool finds that a failing test is unrelated to the suspected file, that should change the debugging path. A useful AI interaction narrows uncertainty; it should not merely decorate a decision already made.

When evidence conflicts, do not force the tool to hide the conflict in a single confident recommendation. Ask it to preserve the disagreement, name the strongest source on each side, and explain what local check would resolve the question. This is especially important for platform work, where documentation, provider behavior, and cluster configuration may not line up perfectly. The best answer may be a small experiment, not a louder paragraph.

Version scope is another selection question that beginners often skip. A Kubernetes answer for 1.35, a cloud provider answer for a newly released feature, and a language-library answer for a specific major version all require different grounding. If the tool cannot state the version it is using, make that uncertainty visible in the output. Version awareness is not pedantry; it is the difference between reusable guidance and a subtle future bug.

## Risk, Verification, And When To Stop

The default pattern is to start with the smallest tool that can safely solve the task: use chat before agents, search before unsupported claims, a coding assistant before broad automation, and a workflow system only when steps repeat and ownership is clear. This reduces cost and complexity, but it also protects your attention. Every additional capability creates another thing you must supervise, so escalation should buy a specific form of leverage.

Verification is the practical difference between useful AI assistance and hopeful outsourcing. For explanation, verification may mean checking whether the concept matches your mental model and whether examples behave as described. For source-grounded work, it means opening the cited documents, checking dates, and confirming that the quoted guidance applies to your version. For code, it means tests, static checks, review, and diff discipline. For workflows, it means checkpoints between observation, planning, action, and rollback.

The most dangerous AI failure is not obvious nonsense; it is a plausible answer that lands just outside your expertise. That is why source needs must be explicit. If a tool says a feature exists in Kubernetes 1.35, ask for the official documentation or a command that proves the API is available. If a tool proposes a library version, ask for release notes or package metadata. If a tool suggests a security interpretation, ask what authority supports it and what remains uncertain.

There are also situations where AI should not be used first. Avoid AI-first behavior when the task involves confidential material you cannot expose, when the stakes are high and you have no reliable verification path, when the work depends on exact legal, medical, or compliance wording, or when doing the task directly is faster and less error-prone. Refusing to use AI in those moments is not anti-technology. It is good tool selection.

For high-risk tasks, design stop conditions before prompting. A stop condition is a rule that tells the tool when it must halt instead of continuing. Examples include missing source evidence, failing tests, ambiguous ownership, commands that would delete resources, or a diff larger than the agreed scope. Stop conditions turn caution into an executable workflow rule, which is much stronger than hoping the tool will be careful.

Human review should be placed where judgment changes the outcome, not only at the very end. If a workflow drafts three possible fixes, review should happen before the tool edits files. If a coding assistant proposes a broad refactor, review the plan before the diff grows. If a search-grounded tool finds conflicting documentation, review the source applicability before the answer becomes internal guidance. Review is most valuable before momentum hides uncertainty.

For practical work, pair each AI layer with a verification artifact. Chat should leave a concise summary of assumptions. Search should leave source URLs and notes about freshness or version. Coding tools should leave a diff, commands run, and test results. Agentic workflows should leave an execution log that distinguishes observation, reasoning, proposed action, approval, and result. These artifacts make the work inspectable after the conversation has moved on.

Verification artifacts also help teams learn which tool choices are paying off. If a chat explanation repeatedly needs source correction, the task may belong in a search-grounded workflow. If coding suggestions repeatedly fail because the assistant lacks project context, the team may need a repository-aware tool or smaller tasks. If an agentic workflow produces long logs with little useful action, the process may be better as a checklist. The evidence should shape the next workflow design.

There is a social side to verification as well. When a human reviews AI-assisted work, the reviewer needs to know which parts were generated, which sources were checked, and which commands were run. Hiding AI involvement makes review harder because the reviewer cannot focus on likely failure modes. Clear disclosure does not need drama; a short note such as "AI helped draft this, sources checked below, tests run here" gives the reviewer the right frame.

The good habit is simple: start by choosing the smallest safe tool that solves the task, then escalate only when a named limitation blocks progress. If chat cannot provide current sources, escalate to search-grounded work. If search cannot inspect your repository, escalate to a coding tool. If the same bounded process repeats and every step has a check, consider a workflow. If none of those paths has a reliable verification method, stop and redesign the task.

## Patterns & Anti-Patterns

Patterns and anti-patterns help you evaluate tool fit quickly, but they should not become slogans. A pattern is a repeatable decision that preserves control while improving leverage. An anti-pattern is a decision that feels efficient at the start and becomes expensive when evidence, ownership, or verification is missing. The table below is a compact reference, but the real skill is recognizing the reason behind each row.

| Pattern | When To Use It | Why It Works |
|---|---|---|
| Task contract before prompt | Use when the request is more complex than a quick explanation. | It names evidence, output, boundaries, and checks before the tool starts optimizing for fluency. |
| Ground before summarize | Use when the answer depends on recent facts, vendor guidance, or policy. | It prevents unsupported claims from becoming polished internal guidance. |
| Read-only before write access | Use when a tool can inspect systems, files, or APIs. | It gives the tool enough context to reason while keeping action under human control until the plan is reviewed. |
| Dry run before live execution | Use when infrastructure, data, or customer-facing behavior could change. | It turns model confidence into observable evidence before an irreversible step. |

The strongest pattern is the task contract because it improves every layer of tool use. In chat, it keeps the answer focused. In search, it tells the tool what source quality matters. In coding, it constrains the diff. In workflows, it becomes the boundary between delegated execution and uncontrolled autonomy. A task contract is not bureaucracy; it is the lightweight design document for an AI-assisted step.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|---|---|---|
| Tool-first prompting | The user bends the task to the open interface and misses evidence requirements. | Name the task type, context depth, risk, and verification path first. |
| Agent for a checklist | The workflow adds permissions and latency without reducing real work. | Keep the checklist human-run until repetition and stable checks justify automation. |
| Search as judgment | The answer has links but weak reasoning about applicability. | Use search for grounding, then apply domain review to compare scope, version, and risk. |
| Coding assistant as owner | The diff may pass syntax while violating intent or weakening tests. | Treat the assistant as a patch proposer and keep ownership with the engineer. |

One anti-pattern deserves special attention: using "more automation" as a proxy for being more advanced. Mature AI use often looks less flashy because it uses small tools with sharp boundaries. A team that uses chat for explanation, search for source checks, a coding assistant for focused patches, and a human approval gate for risky changes is usually operating at a higher level than a team that gives an agent vague goals and broad credentials.

Another pattern worth practicing is separating exploration from commitment. Exploration asks the tool to generate possibilities, compare approaches, or surface unknowns. Commitment turns one possibility into a change, a decision, or a published artifact. Mixing those modes creates pressure to accept the first fluent answer. Keeping them separate lets you use creative breadth early and strict verification later, which is a better match for how technical decisions actually mature.

In team settings, patterns should be written as small operating agreements rather than personal preferences. For example, a team might agree that AI-generated documentation updates need primary sources, code patches need targeted tests, and infrastructure changes need dry-run output before review. These agreements reduce argument during urgent work because the checkpoint is known in advance. They also make AI use teachable for new team members instead of dependent on individual intuition.

Anti-patterns often appear when a team is tired or under time pressure. During an incident, a fluent tool can feel like relief, and during a deadline, an agent can feel like free throughput. That is exactly when boundaries matter most. A practical rule is to lower autonomy as risk rises unless verification improves at the same time. Speed without verification is not acceleration; it is deferred debugging.

## When You'd Use This vs Alternatives

Use a simple chat tool when the task is explanation, brainstorming, or rewriting and the important context fits in the conversation. Use a search-grounded tool when the task depends on recent or source-sensitive information. Use a coding tool when the answer depends on repository files, tests, or local commands. Use an agentic workflow when the task is repeated, bounded, observable, and safe to pause at checkpoints.

| Task Signal | Start With | Escalate When | Stop When |
|---|---|---|---|
| You need an explanation or draft | Chat tool | The answer needs current sources, files, or execution. | You can review the output directly and no external evidence is required. |
| You need recent guidance | Search-grounded tool | You need deeper reasoning over the retrieved material. | Sources are missing, stale, or do not apply to your version. |
| You need code help | Coding tool | The task spans repeated steps with stable checks. | Tests fail, the diff grows beyond scope, or ownership is unclear. |
| You need repeated execution | Agentic workflow | The process has clear observations, actions, and checkpoints. | The tool cannot verify state or asks for permissions beyond the task. |

This decision framework is intentionally conservative. It does not say "never use agents" or "always use search." It says each escalation must pay rent. If a stronger tool does not add evidence, context, execution, or verification that the task actually needs, then it adds supervision overhead without improving the result. The goal is not to minimize AI use; the goal is to maximize useful leverage per unit of risk.

The framework also gives you a way to explain tool choice to someone else. Instead of saying "I used this model because it is better," you can say "I used search because the answer depended on current vendor documentation," or "I used a coding assistant because the failing behavior depended on repository context." That explanation is easier to review and easier to improve. It turns tool choice into an engineering decision rather than a preference.

When a task feels ambiguous, run a two-minute classification pass before doing the real work. Write the task type, required evidence, risk level, allowed actions, and verification artifact. If those fields are easy to fill in, proceed with the smallest matching tool. If they are hard to fill in, the problem is not ready for automation. Clarifying the task will usually save more time than asking a stronger model to guess what you meant.

This framework is also useful after the work is done because it gives you a review checklist. Ask whether the tool had the evidence it needed, whether the output matched the requested artifact, whether the chosen layer added real leverage, and whether the verification artifact would convince a skeptical teammate. If any answer is weak, the next iteration should change the workflow rather than merely ask for a nicer response.

Over time, teams can turn repeated classifications into local guidance. You might discover that release-note drafting almost always starts with search, that test-failure triage works best in a coding assistant, and that production remediation stays human-run until dry-run and rollback evidence are attached. Those patterns should remain revisable, but writing them down prevents every person from rediscovering the same boundaries under deadline pressure.

The final judgment is whether the tool helped you move from uncertainty to justified action. Explanation reduces conceptual uncertainty, search reduces source uncertainty, coding help reduces implementation uncertainty, and workflows reduce coordination cost across repeated steps. When a tool does not reduce one of those uncertainties, it may still be interesting, but it is not doing useful engineering work. Practical AI tool use is the discipline of noticing that difference before the task becomes expensive.

That discipline improves with repetition, so treat each completed AI-assisted task as feedback for the next selection decision.

## Did You Know?

- The NIST AI Risk Management Framework 1.0 was released in January 2023, and its core functions use the sequence Govern, Map, Measure, and Manage to structure AI risk work.
- OpenAI's function-calling guidance recommends making tool definitions clear and constrained, because the model can only choose well when the available functions are obvious and bounded.
- Kubernetes has supported server-side dry-run for API requests for years, which is why commands such as `kubectl diff` fit naturally into AI-assisted change review.
- The phrase "human in the loop" is not a single control; it can mean review before action, approval after a plan, monitoring during execution, or audit after completion.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Using chat when the task needs current sources | The answer sounds fluent, so the missing retrieval step is easy to overlook. | Use a search-grounded tool first, then ask for dates, source links, and applicability notes. |
| Giving an agent a vague goal | The user wants speed but has not defined evidence, boundaries, or stop conditions. | Write a task contract with inputs, allowed actions, forbidden actions, and review checkpoints. |
| Treating code suggestions as ownership transfer | The assistant produces a patch, so the engineer relaxes review discipline. | Run tests, inspect the diff, and keep responsibility with the human maintainer. |
| Escalating every task to automation | Agentic tools feel more advanced than simple prompts. | Start with the smallest safe tool and escalate only when a named limitation blocks the task. |
| Asking for source-sensitive guidance without source quality criteria | The tool may collect links that are stale, secondary, or not version-matched. | Require primary/vendor sources and ask the tool to state version assumptions. |
| Letting action tools skip dry runs | The proposed change looks reasonable, and the user wants to save time. | Require non-destructive validation such as test runs, previews, diffs, or read-only checks before action. |
| Ignoring confidentiality during tool choice | The team focuses on usefulness and forgets whether the evidence may be shared. | Decide data boundaries before prompting, and use approved local or enterprise tools when private context is required. |

## Quiz

<details>
<summary>Question 1: Your team needs a quick explanation of a confusing Kubernetes concept before a meeting. No one needs sources, code changes, or any action taken. How should you evaluate AI tool fit by comparing task type, context depth, source needs, action rights, and risk?</summary>

A chat tool is the best starting point because this is an explanation task with low context depth and no action rights. The risk is also low because humans can review the explanation before using it. A search-grounded or agentic tool would add overhead without adding evidence that the task actually requires. The important review step is to check whether the explanation matches the team's current understanding and the Kubernetes version being discussed.
</details>

<details>
<summary>Question 2: You are updating internal guidance based on a cloud provider feature that changed recently. A teammate suggests using a strong reasoning model with no web access because it sounds smarter. What tool choice is safer?</summary>

A search-grounded tool is safer because the task is retrieval-heavy and source-sensitive. A reasoning model without current access may produce a coherent answer from stale memory, which is exactly the failure you are trying to avoid. After retrieval, you may still use reasoning to compare implications, but the first step should gather primary or vendor sources. The final guidance should include source links, dates when available, and the version scope.
</details>

<details>
<summary>Question 3: Your team wants help understanding an unfamiliar repository and generating a first patch for a failing test, but a human engineer will still review the result before merging. Which layer helps you design a smallest-safe-tool workflow?</summary>

A coding tool fits this job because the answer depends on files, tests, and local repository context. The smallest-safe workflow is to let the tool inspect the relevant code, propose a focused patch, and run targeted verification while the human keeps ownership of the merge decision. Plain chat would suffer from missing context unless you pasted enough files to recreate the repository relationships. A broad agent is unnecessary unless the patch process becomes a repeated, bounded workflow with stable checks.
</details>

<details>
<summary>Question 4: A manager asks for an autonomous AI agent to rewrite one short email that you could rewrite manually in two minutes. What should you diagnose before choosing the tool?</summary>

You should diagnose the mismatch between the small rewriting task and the proposed agentic execution layer. The work has low context depth, low need for action rights, and little repetition, so a simple chat or writing assistant is enough if AI is useful at all. An agent adds permissions, setup, and supervision without reducing meaningful risk or effort. The better decision is to keep the task simple and reserve workflow automation for repeated processes.
</details>

<details>
<summary>Question 5: Your security team asks an AI system to make production configuration changes directly, but there is no review gate and no reliable way to verify the result before rollout. How should you implement a verification plan?</summary>

You should stop the action-taking part of the task in its current form. A verification plan would need read-only inspection, a proposed change, a non-destructive preview, human review, and a rollback path before live execution. Without those controls, the system has too much authority for the available evidence. AI may still help draft the plan or analyze read-only data, but it should not directly change production.
</details>

<details>
<summary>Question 6: You need to check whether a suspected open-source library issue has known vulnerabilities, gather links, and confirm the latest guidance before deciding on a fix. Which tool should you use first?</summary>

Use a search-grounded tool first because the task depends on current external information and source quality. Chat alone can help you frame what to look for, but it should not be trusted as the source of truth for vulnerability status. After collecting sources, a reasoning or coding tool may help interpret whether the issue affects your dependency graph. The final decision still needs human review because applicability depends on versions and runtime exposure.
</details>

<details>
<summary>Question 7: Your team runs the same multi-step process every week: collect logs, compare them with recent changes, verify external advisories, and then apply a patch with checkpoints. When does an agentic workflow make sense?</summary>

An agentic workflow makes sense when the steps are stable, bounded, observable, and separated by checkpoints. The tool can collect evidence, summarize correlations, prepare a proposed patch, and run checks, but it should stop before risky actions that require approval. This is different from asking an agent to solve a vague incident end to end. The workflow is justified because repetition and clear verification reduce the cost of supervision.
</details>

## Hands-On Exercise

Exercise scenario: you are going to build a small decision log that maps real tasks to the smallest safe AI tool, then verify each choice with short evidence. The goal is not to produce a perfect policy document. The goal is to practice naming task type, context depth, source need, action rights, and verification before you open a tool. Use a topic from your actual work if it is safe to share, or use a harmless personal technical task if your work context is confidential.

- [ ] Create a file named `tool-selection-notes.md` in your working directory.
  Verification command:
```bash
touch tool-selection-notes.md
test -f tool-selection-notes.md && echo "notes file exists"
```

<details>
<summary>Solution guidance</summary>

This first step is intentionally simple because the exercise is about decision quality, not file mechanics. The verification command creates the file if needed and confirms that the path exists. If you are working in a repository, keep this as a scratch file unless your team explicitly wants to commit it.
</details>

- [ ] Add five task labels to the file: `explanation`, `recent information`, `code help`, `repeatable workflow`, and `high-risk/no-verification`.
  Verification command:
```bash
grep -nE 'explanation|recent information|code help|repeatable workflow|high-risk/no-verification' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

Use these labels as headings or bullet prefixes. The labels match the tool-selection categories from the module, so they make later review easier. If the command prints all five lines, you have enough structure to continue.
</details>

- [ ] For the `explanation` task, use a chat tool to answer a question you already partly understand, then write two lines: why chat was enough and what still needed human judgment.
  Verification command:
```bash
grep -nE 'chat was enough|human judgment' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

Choose something low-risk, such as explaining a command flag or summarizing a concept you can check from memory. The point is to see that chat can be useful without pretending to be authoritative for every task. Your note should make the review boundary explicit.
</details>

- [ ] For the `recent information` task, use a search-grounded tool to look up a current topic, then record two source links and one sentence explaining why plain chat would have been risky.
  Verification command:
```bash
grep -Eo 'https?://[^ )]+' tool-selection-notes.md | wc -l
grep -n 'plain chat would have been risky' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

Pick a topic where freshness genuinely matters, such as a vendor release note, a product deprecation, or a current security advisory. Do not use random blog links if primary documentation exists. Your sentence should connect the risk to staleness, source quality, or version mismatch.
</details>

- [ ] For the `code help` task, give a coding assistant one small bounded request, then record one useful output and one reason a human should still review the result.
  Verification command:
```bash
grep -nE 'useful output|human should still review' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

Keep the request narrow, such as explaining a function, suggesting a test case, or finding where a config value is used. A useful output is not automatically a correct change. Record the review reason in concrete terms, such as test coverage, API compatibility, security impact, or codebase style.
</details>

- [ ] For the `repeatable workflow` task, write a 3-5 step process you do more than once, then decide whether it should stay a checklist or become a workflow/agent. Add one sentence explaining the boundary.
  Verification command:
```bash
grep -nE 'checklist|workflow|agent|boundary' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

Good candidates include weekly report preparation, release note triage, or a repeated diagnostic routine. The decision should mention whether the steps are stable, whether outputs are easy to verify, and whether the tool needs action rights. If those conditions are missing, keeping the process as a checklist is usually the safer answer.
</details>

- [ ] Add one example where AI should not be used at all because the risk, confidentiality, or verification gap is too high.
  Verification command:
```bash
grep -nE 'should not be used|confidential|risk|verification gap' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

This example should be specific enough to teach a boundary, but it should not expose private details. You might describe a class of work, such as unreleased customer data, legal wording, or production access without dry-run capability. The important part is naming why the verification or data boundary fails.
</details>

- [ ] End the file with one reusable rule: start with the smallest safe tool that solves the task.
  Verification command:
```bash
grep -n 'smallest safe tool that solves the task' tool-selection-notes.md
```

<details>
<summary>Solution guidance</summary>

This final rule is the memory hook for the module. It is short enough to reuse before opening a tool, and it forces the next decision to begin with task fit. If your team wants a longer version, add source needs, action rights, and verification as subpoints.
</details>

The exercise is complete when the checklist below shows a balanced decision log, not just a set of copied commands. Each item should connect the task to a tool choice and a verification reason.

- [ ] `tool-selection-notes.md` exists and includes all five task categories.
- [ ] At least one task is matched to chat, one to search-grounded use, one to coding assistance, and one to a checklist or workflow decision.
- [ ] The recent-information example includes at least two sources.
- [ ] One example explicitly says AI should not be used and explains why.
- [ ] The final rule reflects a task-first approach instead of a tool-first approach.

## Sources

- [Artificial Intelligence Risk Management Framework (AI RMF 1.0)](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10) — Background on evaluating AI risk and deciding when stronger controls and human review are needed.
- [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) — Practical guidance on generative-AI risks, verification needs, and safe operational boundaries.
- [NIST AI Risk Management Framework overview](https://www.nist.gov/itl/ai-risk-management-framework)
- [OpenAI function calling guide](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI tools guide](https://platform.openai.com/docs/guides/tools)
- [OpenAI prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic tool use overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
- [Anthropic evaluation tool guide](https://docs.anthropic.com/en/docs/test-and-evaluate/eval-tool)
- [Google Gemini function calling documentation](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google Vertex AI grounding overview](https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/overview)
- [Microsoft responsible AI overview](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/overview)
- [Kubernetes debugging tasks](https://kubernetes.io/docs/tasks/debug/)
- [kubectl diff reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/)

## Next Module

Continue to [AI Agents and Assistants](../module-1.2-ai-agents-and-assistants/) to separate chat, assistants, copilots, and agents by autonomy and review boundaries.
