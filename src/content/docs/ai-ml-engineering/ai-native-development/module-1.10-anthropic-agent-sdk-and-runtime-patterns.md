---
citations_verified: true
title: "Anthropic Agent SDK and Runtime Patterns"
slug: ai-ml-engineering/ai-native-development/module-1.10-anthropic-agent-sdk-and-runtime-patterns
sidebar:
  order: 211
---

> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 2-3 hours

**Reading Time**: 2-3 hours

**Prerequisites**: Claude Code & CLI Deep Dive, CLI AI Coding Agents, Building with AI Coding Assistants, and Model Context Protocol for Agents

> **Go deeper:** For the vendor-neutral tool landscape introduced in this sub-track, revisit [AI Coding Tools Landscape](../module-1.1-ai-coding-tools-landscape/). For retrieval boundaries, dynamic context orchestration, and production harness operation around agent runtimes, see [Retrieval, Tools, and Memory Boundaries](/ai/ai-engineering-foundations/module-2.3-retrieval-tools-and-memory-boundaries/), [Dynamic Context Orchestration](/ai/ai-engineering-foundations/module-2.4-dynamic-context-orchestration/), and [Operating the Harness](/ai/ai-engineering-foundations/module-3.3-operating-the-harness/).

---

## Learning Outcomes

By the end of this module, you will be able to:

- **Design** an agent runtime that separates goal definition, tool execution, permissions, session state, and verification.
- **Compare** Claude Agent SDK, Claude Code CLI, MCP integrations, and hand-rolled client SDK loops for realistic team workflows.
- **Evaluate** runtime risks such as context drift, unsafe tool scope, missing approvals, and silent verification failures.
- **Implement** a small gather, act, verify prototype that logs agent behavior and enforces a concrete permission boundary.
- **Debug** weak agent designs by identifying which runtime layer is missing or misconfigured.

---

## What You'll Be Able to Do

You will be able to look at an "agent" proposal and separate the model capability from the runtime responsibility. That means you can ask whether the agent has enough context, whether it is allowed to mutate the right things, whether each tool crosses a local or external boundary, and whether the final answer is backed by evidence rather than confidence.

You will also be able to map Anthropic-specific implementation details onto neutral harness concepts. Claude Agent SDK is the worked example in this module, but the durable lesson is portable: every serious agent runtime needs a loop, a tool registry, permission policy, session state, observability, and verification. Other harnesses expose those ideas through different names, but the engineering questions remain the same.

---

## Why This Module Matters

Hypothetical scenario: a platform team ships an internal agent that looks impressive during a demo. It can inspect a repository, edit files, run commands, and explain its changes in confident language. A month later, the same agent becomes a source of operational risk because it edits outside the intended directory, repeats stale assumptions from old sessions, and closes work without running the checks the team normally expects from a human engineer.

The problem is not that the team used an AI model. The problem is that they built a chat loop and treated it like an agent runtime. A serious runtime has to decide which tools are available, which actions need approval, how sessions are resumed, how work is observed, and how each action is verified before the agent continues.

The Claude Agent SDK matters because Anthropic describes it as packaging many of the runtime patterns behind Claude Code into a programmable form. Instead of starting with a blank model client and rebuilding tool execution, permissions, hooks, sessions, MCP integration, and context management from scratch, a team can build on a harness designed for iterative agent work.

This module teaches the runtime design behind that harness. You will not only learn what the SDK exposes; you will learn how to reason about when it is appropriate, how to constrain it, and how to recognize the point where explicit workflow code is safer than agent autonomy.

> **Landscape snapshot — Claude Agent SDK, as of 2026-06.** Vendor SDK surfaces churn; verify against Anthropic's current docs before relying on specifics.
>
> - **Name:** Claude Agent SDK (formerly the Claude Code SDK) — broadened beyond coding to general agents.
> - **Languages:** Python and TypeScript.
> - **Built-in capabilities:** file read / run / search / edit, MCP support, hooks, permissions (allow & deny rules, permission modes, approval callbacks), sessions (IDs, resume, result messages, compact-boundary events), and subagents.
> - **Durable spine (this module's focus):** the agent-loop lifecycle, the permission/guardrail model, session/state boundaries, and runtime tradeoffs — these outlast any single SDK version.

---

## 1. From Chat Integration to Agent Runtime

A plain chat integration asks a model to respond to a user message. A plain client SDK lets your application call a model, receive output, and optionally implement a tool-calling loop yourself. An agent runtime goes further because it gives the model an environment where it can gather context, use tools, act, observe results, and continue until the task reaches a defensible stopping point.

That distinction matters because most production failures are not caused by the first prompt being poorly worded. They happen when the system gives the model a powerful tool without a permission boundary, loses track of state across a long task, fails to inspect tool output, or treats a generated answer as done before checking the external reality it claims to change.

The Claude Agent SDK is Anthropic's library form of the agent harness behind Claude Code. The official Agent SDK overview describes agents that can read files, run commands, search the web, edit code, connect to MCP servers, use hooks, track sessions, and manage context. The SDK does not remove the need for engineering judgment; it moves many runtime concerns into a structured place where you can design and inspect them.

That packaging is valuable precisely because it makes the runtime visible. A hand-rolled loop can absolutely be correct, but it often spreads policy across prompt text, helper functions, API wrappers, and ad hoc logs. Once the loop becomes hard to inspect, it becomes hard to answer the operational questions that matter: which tool was called, why was it allowed, what evidence came back, which state was preserved, and what stopped the run from continuing forever.

The neutral comparison from [Module 1.1](../module-1.1-ai-coding-tools-landscape/) still applies here. Claude Agent SDK is the concrete worked example, not the universal answer. A Cursor rule, a Codex harness, a LangGraph node, a CrewAI worker, or a custom service can all express similar runtime concepts. The implementation details differ, but the boundary questions do not.

A useful mental model is that the SDK is not the intelligence layer alone. It is a runtime layer around the intelligence. The model still reasons, but the runtime decides what kind of world the model is allowed to touch, how that world is represented, and what evidence is required before work can be called complete.

```text
+----------------------+      +----------------------+      +----------------------+
|      User Goal       | ---> |   Agent Runtime      | ---> |   External World     |
| outcome and context  |      | tools, policy, state |      | files, shell, APIs   |
+----------------------+      +----------+-----------+      +----------+-----------+
                                           |                             |
                                           v                             |
                                +----------------------+                |
                                | Verification Signals | <--------------+
                                | tests, logs, diffs   |
                                +----------------------+
```

The diagram is deliberately simple because the first design question is simple: can the agent prove that its action changed the world in the intended way? If the answer is no, the runtime is incomplete even if the prompt looks sophisticated.

A beginner often asks, "What prompt should I use?" A senior engineer asks, "What loop will keep this system honest when the prompt is not enough?" The Claude Agent SDK is useful when the honest loop needs tools, sessions, approvals, hooks, and observability rather than a one-shot answer.

**Stop and think:** If an agent edits a file and then explains why the edit should work, what evidence would convince you that the edit actually worked? Write down two verification signals before reading further, then compare them with the verification patterns in the next section.

The most common answer is "run the test," and that is a good start. A stronger answer includes the specific test, the expected failure before the fix, the expected passing output after the fix, and the file-level diff that proves the change stayed within scope. Verification is not a vibe; it is a runtime behavior.

The first failure mode in this layer is under-gathering. The agent sees one file, assumes it has the whole system, and edits a local symptom while missing configuration, generated code, feature flags, or tests nearby. A good runtime does not solve under-gathering by dumping the entire repository into context. It gives the agent targeted discovery tools, keeps tool output observable, and lets the developer constrain the search surface to the files and systems that matter.

The second failure mode is over-acting. The agent gathers enough context, proposes a reasonable next step, and then uses a tool with broader authority than the task requires. That is how a documentation cleanup turns into dependency installation, generated artifact churn, or external system mutation. The runtime boundary should make the smallest useful action easy and the broader action explicit.

The third failure mode is false verification. The agent runs a command that is convenient but irrelevant, interprets partial output as success, or reports that a check "should pass" because the explanation is coherent. The SDK can expose the message stream, result status, tool calls, and hooks around execution, but your application still has to define which verification signals count. In production, the final answer should be a compact audit record, not just a persuasive narrative.

> ## Learner check
>
> Before allowing an agent to act, name the evidence it must gather, the smallest tool set it may use, and the verifier that can prove the result.

---

## 2. The Gather, Act, Verify Loop

Anthropic's public guidance frames agent work as an iterative loop: gather context, take action, verify work, and repeat when necessary. That loop is valuable because it matches how careful engineers solve ambiguous tasks. They inspect the situation, make a bounded change, check whether the world now matches the goal, and only then decide whether to continue.

The gather stage exists because an agent that acts without context is guessing. In a codebase, gathering might mean reading a failing test, searching for the relevant function, inspecting configuration, and checking recent logs. In a support workflow, it might mean loading the customer record, previous conversations, entitlement state, and current incident status.

The act stage exists because agents are useful only when they can do more than summarize. Acting can mean editing a file, running a script, creating a report, calling an MCP tool, updating a ticket, or asking the user for a decision. The action should be narrow enough that the verification stage can evaluate it.

The verify stage exists because agent reasoning is not self-validating. A model can produce a plausible explanation for a wrong change, and a long-running agent can build later decisions on that wrong change if the runtime does not force a check. Verification converts the agent's claim into evidence.

```text
+-------------------+        +-------------------+        +-------------------+
|  Gather Context   | -----> |    Take Action    | -----> |   Verify Result   |
| read, search, ask |        | edit, call, run   |        | test, diff, audit |
+---------+---------+        +---------+---------+        +---------+---------+
          ^                            |                            |
          |                            v                            |
          |                  +-------------------+                  |
          +------------------| Continue or Stop  |<-----------------+
                             | based on evidence |
                             +-------------------+
```

This loop is a runtime pattern, not just a planning slogan. A real implementation has to give the agent tools for gathering, tools for acting, and a policy that treats verification as mandatory for meaningful actions. Otherwise the loop exists only in documentation.

Anthropic's Agent SDK loop documentation describes a message lifecycle where the SDK initializes session metadata, the model evaluates the prompt, requested tools execute, results are fed back, and the cycle repeats until the agent returns a final result. That is the mechanical form of gather, act, verify. It is not merely "the model thinks again"; it is a stream of messages, tool results, limits, hooks, and session identifiers that your application can inspect.

The practical implication is that you should design the loop before you design the prompt. If the loop allows unlimited turns, unrestricted Bash, no stop condition, and no audit of tool results, then even a strong prompt is operating inside a weak runtime. If the loop has a turn budget, a cost budget, scoped tools, and a stop policy, then the prompt has a healthier environment to work inside.

Consider a bug-fixing agent. If it can read files and edit files but cannot run tests, it may produce a patch that looks reasonable but cannot establish correctness. If it can run tests but the runtime does not require test execution before returning, the tool exists but the behavior is still weak. If it can run tests and must report the exact command and result, the runtime starts to resemble an engineering workflow.

A senior-level design also asks whether verification can fail safely. The agent should not hide a failing test behind a confident summary. It should stop, report the failure, preserve logs, and either revise the change or ask for help when the failure exceeds its tool scope.

**Pause and predict:** Your agent gathers context from an old session, edits a file, and then fails verification. Should it automatically continue with a second edit, rewind the file, ask the user, or open a subagent investigation? The best answer depends on risk, but it should never ignore the failed verification and continue as if nothing happened.

For low-risk local changes, an automatic second attempt can be reasonable if the diff remains small and the verifier is deterministic. For production operations, external mutations, or credential-adjacent workflows, a failed verification should usually stop and escalate. The runtime policy should encode that difference before the incident happens.

This is where the SDK boundary differs from a simple workflow script. In a script, you normally decide every step in advance: read this file, transform this field, run this command, exit. In an agent runtime, the model may decide which file to read next or which verifier to run, but the runtime still decides which categories of decisions are allowed. The SDK gives you a place to express those limits; it does not absolve you from choosing them.

---

## 3. What the Claude Agent SDK Adds

The Claude Agent SDK adds value when your application needs the same kind of autonomous loop that Claude Code uses, but inside your own product, service, platform workflow, or internal automation. It gives you [programmable access to built-in tools, permissions, sessions, hooks, MCP servers, subagents, and context-management behavior](https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously).

With a client SDK, your application usually owns the whole tool loop. You send a message, inspect whether the model requested a tool, execute the tool yourself, pass the result back, continue the loop, and decide when to stop. That gives maximum control, but it also means your team must build every runtime guardrail.

With the Agent SDK, you configure the runtime and stream messages from an agent loop. The model can use allowed tools through the harness, while your application observes, configures, and constrains the run. That is a different abstraction boundary, and choosing it should be an architectural decision rather than a default.

| Need | Plain Client SDK | Claude Agent SDK |
|------|------------------|------------------|
| One-shot classification | Usually simpler | Usually more runtime than needed |
| Deterministic workflow with fixed steps | Application controls each step directly | Possible, but may add unnecessary autonomy |
| Local code or file work | You implement file tools and loop behavior | Built-in tools can handle reads, edits, search, and commands |
| Long-running iterative tasks | You design session and context strategy | Sessions and context management are first-class concerns |
| External integrations | You implement APIs or tool execution | MCP servers can expose structured external capabilities |
| Runtime control | You design approvals, hooks, and logs | Hooks and permissions provide configurable control points |

The right comparison is not "Which option is more powerful?" The right comparison is "Which option places responsibility in the clearest location?" If your workflow must execute exactly six deterministic steps, explicit application code may be clearer. If your workflow requires the agent to inspect a messy environment and choose reasonable next actions, the Agent SDK may be the better runtime.

The SDK also changes how you think about development velocity. A team can prototype an agent quickly by allowing read, search, edit, and shell tools in a constrained workspace. That does not mean the prototype is production-ready. Production readiness comes from narrowing permissions, adding hooks, preserving evidence, adding session discipline, and testing failure cases.

Here is a minimal SDK-shaped example that illustrates the configuration idea. It is intentionally small, because the important learning point is that tool access is explicit and should be scoped to the job rather than granted broadly by habit.

```python
import asyncio
from claude_agent_sdk import ClaudeAgentOptions, query

async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
    )

    async for message in query(
        prompt="Review this repository and summarize the risky test gaps without editing files.",
        options=options,
    ):
        print(message)

asyncio.run(main())
```

This example is runnable when the `claude-agent-sdk` package is installed and an Anthropic API key is configured in the environment. More importantly, it demonstrates a read-only runtime choice. The agent can inspect, but it cannot edit, run arbitrary shell commands, or mutate external systems.

A common beginner mistake is to start with every tool enabled because the agent seems more capable. A senior engineer starts with the smallest tool set that can complete the job, then adds tools only when a concrete failure shows the agent lacks a necessary capability. Each tool is both a power and a liability.

The SDK also gives you a useful review surface when you are comparing agent proposals. Ask where each proposal keeps session state, how it exposes tool calls to logs, how it caps runaway loops, and what it returns when the task stops because of a limit rather than success. A proposal that cannot answer those questions is probably still a demo loop, even if it uses a polished model and impressive tool names.

---

## 4. Tool Boundaries: Built-In Tools, MCP, and Custom Code

The Claude Agent SDK gives agents built-in tools for common local work, such as reading files, writing or editing files, running shell commands, discovering files, searching contents, fetching web pages, and monitoring command output. These tools are appropriate when the agent's work happens in a local workspace or a controlled execution environment.

MCP is different. MCP is the right boundary when the agent needs structured access to external systems, standardized authentication behavior, or reusable integrations across clients. A GitHub issue tracker, Slack workspace, internal database, browser automation service, or cloud control plane should not be faked as a vague shell instruction when a structured tool boundary is available.

Custom code is the third option. Sometimes the most reliable tool is a small script or service your team owns, especially when the workflow has strict business rules. A custom tool can validate inputs, enforce invariants, return typed results, and keep complex policy out of the prompt.

```text
+----------------------+       +----------------------+       +----------------------+
| Built-In Tools       |       | MCP Servers          |       | Custom Tools         |
| local execution      |       | external systems     |       | business logic       |
+----------------------+       +----------------------+       +----------------------+
| Read/Edit files      |       | GitHub, Slack        |       | approve_invoice      |
| Bash verification    |       | ticketing systems    |       | calculate_risk_score |
| Grep/Glob search     |       | cloud APIs           |       | normalize_customer   |
| Web fetch/search     |       | databases            |       | validate_policy      |
+----------------------+       +----------------------+       +----------------------+
```

The design rule is straightforward: built-in tools are the local execution surface, MCP is the external integration surface, and custom tools are the domain-specific business surface. Mixing those roles creates confusion. For example, forcing local file reads through an MCP server adds ceremony without much safety, while using Bash scripts to mutate SaaS systems can bury authentication and audit behavior in fragile command text.

MCP deserves special attention because it is often misunderstood as "tools, but more official." The protocol is a client-server boundary for sharing context and actions between AI applications and external systems. Its core primitives include tools, resources, and prompts, and the architecture separates the host application, the MCP client connection, and the MCP server that provides capabilities. That separation is what gives MCP its value: the external system can expose a typed capability without becoming an unbounded shell command.

Security differs across the three surfaces. Built-in local tools need path boundaries, command allowlists, and workspace isolation. MCP tools need authentication, server trust, transport security, schema clarity, and audit records for external calls. Custom tools need input validation and business-policy enforcement because they often encode rules that should not be left to natural language. Treating all tools as equal is a design smell.

A good agent design also keeps tool names aligned with the action you want the agent to consider. If the common action is "search customer tickets," expose that as a clear capability rather than forcing the agent to compose several low-level API calls every time. Clear tools reduce prompt burden and make logs easier to review.

**Stop and think:** Your incident agent needs to inspect local deployment manifests, query a cloud provider, and open a follow-up ticket. Which capabilities should be built-in, which should be MCP, and which might deserve custom code? Do not answer by naming technologies first; answer by describing the boundary each action crosses.

A defensible design would use built-in file and shell tools for local manifests, MCP or a typed integration for the cloud provider and ticket system, and custom code for any organization-specific policy such as incident severity calculation. The runtime should make those boundaries visible because hidden boundaries are hard to audit.

This is also where the L0-L5 autonomy ladder becomes practical. At L0, the model answers with no tool authority. At L1, it receives curated context. At L2, it can use read-only tools. At L3, it can propose writes behind review. At L4, it can perform bounded low-risk actions directly. At L5, it operates with broad autonomy in a carefully isolated environment. The Agent SDK is most useful around L2-L4 because tool use, approvals, hooks, sessions, and verification all need to be explicit.

The following SDK-shaped configuration shows an MCP server beside built-in read tools. The exact MCP server command depends on the integration, but the pattern is that external services are attached as structured servers rather than improvised through unconstrained shell access.

```python
import asyncio
from claude_agent_sdk import ClaudeAgentOptions, query

async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        mcp_servers={
            "tickets": {
                "command": "node",
                "args": ["./mcp-ticket-server.js"],
            }
        },
    )

    async for message in query(
        prompt="Inspect the local runbook and check whether an external incident ticket already exists.",
        options=options,
    ):
        print(message)

asyncio.run(main())
```

The example is small, but the architectural point is large. Reading the local runbook and checking an external ticket are not the same class of action. One belongs in the workspace; the other crosses an organizational boundary and needs authentication, auditability, and clearer semantics.

When the tool boundary is unclear, prefer the boring answer. If a plain client SDK call plus one explicit API request can solve the job, use that. If the agent needs to discover which integration to call, handle several possible external states, and continue after tool results, then MCP inside an agent runtime becomes more defensible. The goal is not to maximize tool count; it is to minimize ambiguous authority.

---

## 5. Permissions, Hooks, and Approval Boundaries

Permissions are not a final polish step. They define the agent's blast radius. A runtime without permissions is equivalent to handing a junior automation script the keys to every system and hoping the prompt remains wise under pressure.

The basic permission question is, "What is the agent allowed to do without asking?" The answer should vary by risk. Read-only analysis can allow broad inspection. Local documentation edits can allow writes inside a known directory. Production actions should require narrow tools, human approval, audit logs, rollback paths, and clear stopping conditions.

| Risk Level | Example Workflow | Default Tool Scope | Approval Pattern | Verification Signal |
|------------|------------------|--------------------|------------------|---------------------|
| Low | summarize repository risks | read, glob, grep | no approval for reads | cited files and summary diff |
| Medium | fix a local test failure | read, edit, bash verifier | approval or policy for writes | exact test command and result |
| High | change cloud resources | narrow MCP tools only | approval before mutation | external state check and audit record |
| Critical | credential or payment workflow | specialized tools only | human decision required | independent system confirmation |

Hooks provide runtime interception points. They let your application log, validate, block, or transform behavior around tool use and session events. In a serious system, hooks are how you move policy from "the prompt said not to" into executable control.

The SDK documentation describes permissions through allow rules, deny rules, permission modes, approval callbacks, and hook decisions. That means the runtime can do more than ask the model to behave. It can pre-approve read-only tools, block specific commands, ask a human before sensitive actions, and return a denial message to the model when a requested tool call crosses the boundary.

A pre-tool hook can block edits outside an allowed path before the write happens. A post-tool hook can log changed files after an edit. A stop hook can reject completion if verification evidence is missing. A session-start hook can attach run metadata, while a session-end hook can emit cost and audit events.

```text
+-------------------+        +-------------------+        +-------------------+
| Agent requests    | -----> | Pre-tool hook     | -----> | Tool executes     |
| Edit config.yaml  |        | allow or block    |        | only if allowed   |
+-------------------+        +---------+---------+        +---------+---------+
                                      |                            |
                                      v                            v
                             +-------------------+        +-------------------+
                             | Audit decision    |        | Post-tool hook    |
                             | reason recorded   |        | verify and log    |
                             +-------------------+        +-------------------+
```

The important principle is that hooks should enforce small, concrete rules. "Be safe" is not a hook policy. "Block writes outside `workspace/`," "require approval before Bash commands containing `kubectl apply`," and "refuse to stop unless `logs/verification.txt` exists" are hook policies.

Approval boundaries should be designed around reversibility, not around whether the model sounds confident. A local text edit that can be reverted with a diff is a different class of action from rotating a credential, changing a payment record, or deleting cloud resources. When an action is irreversible, expensive, externally visible, or security-sensitive, the runtime should ask for approval through a structured path and preserve the exact input that was approved.

A hook can also create friction intentionally. Friction is not always bad in agent systems. It is often the difference between useful autonomy and unreviewed mutation. The more irreversible the action, the more the runtime should slow down and ask for explicit confirmation.

Here is a compact hook-shaped example based on the SDK documentation style. The hook records file modifications so the run leaves an audit trail that can be inspected after the agent finishes.

```python
import asyncio
from datetime import datetime
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, query

async def log_file_change(input_data, tool_use_id, context):
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "unknown")

    with open("./audit.log", "a", encoding="utf-8") as audit:
        audit.write(f"{datetime.now().isoformat()} changed={file_path} tool_use_id={tool_use_id}\n")

    return {}

async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Glob", "Grep"],
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Edit|Write", hooks=[log_file_change]),
            ],
        },
    )

    async for message in query(
        prompt="Improve README clarity without editing files outside this repository.",
        options=options,
    ):
        print(message)

asyncio.run(main())
```

This example still needs surrounding policy before production use. It logs modifications, but it does not by itself prevent a bad modification. In practice, you combine logging hooks with permission configuration, pre-tool validation, and verification requirements.

The safest permission posture usually grows in stages. Start with L2 read-only exploration until you trust the agent's context-gathering behavior. Move to L3 reviewed writes when the diffs are understandable and the verifier is reliable. Move to L4 bounded autonomy only for low-risk actions where rollback, logging, and failure handling have already been exercised. Do not jump from a useful demo to L5 authority because the SDK can technically run a broad loop.

**Pause and predict:** If a hook logs every edit but never blocks any edit, what kind of risk has it reduced and what kind has it left untouched? The audit risk is reduced because the team can inspect what happened later, but the prevention risk remains because the hook does not stop the action before it occurs.

A mature runtime usually needs both prevention and detection. Prevention limits what can happen; detection preserves evidence about what did happen. Verification then decides whether the result is acceptable.

---

## 6. Sessions, Context Compaction, and Drift

Sessions are one of the reasons the Agent SDK is more than a tool wrapper. Real work often spans multiple exchanges, and a useful agent may need to remember what it read, which files it changed, which hypothesis failed, and what goal the user approved. Session continuity can reduce repeated context gathering and preserve momentum.

Anthropic's SDK documentation describes session IDs, resume behavior, result messages, and compact-boundary events in the agent stream. Those details matter because session state is not an invisible convenience. It is part of the runtime contract. If your application cannot explain which session was resumed, what facts were carried forward, and where compaction happened, then it cannot reliably debug long-running behavior.

Continuity also creates risk. If the agent carries forward a weak assumption from early in the run, later decisions may inherit that mistake. If the session grows cluttered with obsolete observations, the model may spend attention on stale context. If the user changes the goal and the runtime does not record that change clearly, the agent may optimize for yesterday's task.

Context compaction helps long-running agents avoid running out of room, but compaction is not magic. A compressed summary can preserve the wrong thing, omit a crucial failed experiment, or flatten uncertainty into false certainty. Teams should treat compacted context as an artifact that needs discipline, not as a perfect memory.

A good session design keeps durable facts separate from working hypotheses. "The service reads `config/runtime.yaml`" is a fact if it was verified from source. "The failure is probably caused by timeout settings" is a hypothesis until a test confirms it. The runtime should make that distinction visible in logs, notes, or structured state.

```text
+----------------------+       +----------------------+       +----------------------+
| Durable Facts        |       | Working Hypotheses   |       | Verification Records |
| confirmed by source  |       | possible explanations|       | commands and results |
+----------------------+       +----------------------+       +----------------------+
| file paths inspected |       | suspected root cause |       | test output          |
| user-approved goal   |       | proposed next action |       | diff summary         |
| policy boundaries    |       | uncertain dependency |       | external check       |
+----------------------+       +----------------------+       +----------------------+
```

Session state should answer three questions after any pause. What is the current goal? What evidence has already been gathered? What remains unverified? If the state cannot answer those questions, resuming the session may create more confusion than starting fresh.

A senior-level agent design also includes a session reset strategy. Sometimes the correct response to drift is not more compaction; it is a clean run with only verified facts carried forward. That is especially true after major goal changes, repeated failed attempts, or tool results that contradict the current plan.

Drift is not only a memory-size problem. It is also a goal-alignment problem. An agent can drift because the user changed the objective, because a subtask produced a misleading summary, because a verifier failed and the failure was softened in the next prompt, or because a compacted summary dropped the reason a risky action was forbidden. Your mitigation should match the cause: restate the goal, preserve failed verifier output, archive the full transcript before compaction, or restart with a verified-facts brief.

The cleanest mitigation pattern is to keep three artifacts outside the model's mutable conversation: a task brief, a verification ledger, and a change log. The task brief states the current objective and non-negotiable boundaries. The verification ledger records commands, external checks, and outcomes. The change log records what the agent actually touched. These artifacts make resumption safer because they outlive compaction and can be inspected by a human or another runtime.

Subagents interact with session design because they can isolate context. A search subagent can inspect a large body of material and return only relevant findings to the main agent. That can reduce clutter, but it also requires accountability: the main agent should know which subagent produced which finding and what evidence supports it.

Use subagents when the work decomposes naturally, the subtasks can proceed independently, and the output boundary is clear. Avoid subagents when the task is small, sequential, or accountability would become harder to trace. Multi-agent architecture is not automatically more advanced; sometimes it is just a more expensive way to lose the thread.

Session discipline is also where SDK runtime and hand-rolled workflow differ sharply. In a hand-rolled workflow, state is usually explicit because the application stores each transition. In an agent runtime, conversation history can tempt teams to treat "the model remembers" as state management. That is not enough. The application should still decide which facts are durable, which summaries are disposable, and which evidence must be rechecked after a resume.

---

## 7. Worked Example: Designing a Repo Maintenance Agent

This worked example demonstrates how to move from a vague agent idea to a concrete runtime design. The scenario is a platform team that wants an agent to maintain internal developer documentation. The agent should inspect a repository, improve outdated docs, and verify that links and formatting still pass local checks.

The first version of the request is too broad: "Build an agent that updates docs." A runtime cannot safely implement that goal because the action surface is unclear. Does the agent edit all files? Can it run shell commands? Can it open pull requests? Can it contact external systems? Does it stop after one file or continue across the repository?

Step 1 is to rewrite the goal as an outcome with boundaries. A better goal is: "Improve documentation files under `docs/` that reference a deprecated setup command, keep edits scoped to those files, and run the local documentation verifier before finishing." This statement tells the agent what success means and what scope is allowed.

Step 2 is to choose the tool surface. The agent needs `Read`, `Glob`, and `Grep` to find references. It needs `Edit` to update files. It needs `Bash` only for the verifier command, not for arbitrary system changes. It does not need MCP unless it must update external tickets, send Slack messages, or call a repository hosting API.

Step 3 is to define the permission boundary. The agent may read the repository, but it may edit only files below `docs/`. The agent may run a known verifier command, but it may not run destructive shell commands or install dependencies. This turns a broad automation idea into a controlled local workflow.

Step 4 is to define hooks. A pre-tool hook should block edits outside `docs/`. A post-tool hook should record every changed file. A stop hook should check that the verifier ran after the last edit. The hooks turn policy into runtime behavior rather than leaving it as a polite instruction.

Step 5 is to define session state. The session should record the original goal, the search query used to find deprecated references, the files changed, the verifier command, and the final result. If the agent resumes later, it should know which findings were already handled and which remain open.

Step 6 is to define verification. The agent must run a specific command, such as `.venv/bin/python scripts/check_links.py docs`, or another local documentation check that the project provides. The final answer should include the command, exit status, and a short explanation of any remaining failures.

```text
+--------------------------+------------------------------------------------------+
| Design Choice            | Worked Example Decision                              |
+--------------------------+------------------------------------------------------+
| Goal                     | Replace deprecated setup command references in docs  |
| Built-in tools           | Read, Glob, Grep, Edit, constrained Bash verifier    |
| MCP                      | Not needed unless external issues or messages update |
| Permission boundary      | Edit only files under docs/                          |
| Pre-tool hook            | Block writes outside docs/                           |
| Post-tool hook           | Append changed file path to audit log                |
| Stop condition           | Verifier ran after final edit                        |
| Session artifact         | Goal, files changed, verifier result, open questions |
+--------------------------+------------------------------------------------------+
```

The learner should notice that the worked example did not begin with a model choice. Model quality matters, but the runtime design decides whether a capable model is operating inside a reliable system. The same model can be safe in one runtime and risky in another.

Here is a runnable local prototype that models the policy without requiring live SDK access. It is not a replacement for the Claude Agent SDK; it is a teaching scaffold that makes the runtime mechanics visible. It gathers context from a workspace file, acts by cleaning repeated lines, verifies the result, and logs each stage.

```python
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path("agent-runtime-lab")
WORKSPACE = ROOT / "workspace"
LOGS = ROOT / "logs"
NOTES = WORKSPACE / "notes.txt"
RUN_LOG = LOGS / "run.log"


def log(stage: str, message: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} stage={stage} {message}\n")


def ensure_lab_files() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    if not NOTES.exists():
        NOTES.write_text(
            "\n".join(
                [
                    "Runtime design notes",
                    "- tools matter",
                    "- tools matter",
                    "- permissions unclear",
                    "- no verify step yet",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def enforce_workspace_write(path: Path) -> None:
    resolved_workspace = WORKSPACE.resolve()
    resolved_target = path.resolve()

    if not resolved_target.is_relative_to(resolved_workspace):
        raise PermissionError(f"blocked write outside workspace: {path}")


def gather() -> list[str]:
    log("gather", f"reading={NOTES}")
    return NOTES.read_text(encoding="utf-8").splitlines()


def act(lines: list[str]) -> list[str]:
    log("act", "removing duplicate bullets and adding verification note")
    seen = set()
    cleaned = []

    for line in lines:
        if line.startswith("- ") and line in seen:
            continue
        cleaned.append(line)
        if line.startswith("- "):
            seen.add(line)

    if "- verification required before completion" not in cleaned:
        cleaned.append("- verification required before completion")

    enforce_workspace_write(NOTES)
    NOTES.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
    return cleaned


def verify(lines_before: list[str], lines_after: list[str]) -> bool:
    changed = lines_before != lines_after
    duplicate_removed = lines_after.count("- tools matter") == 1
    verification_added = "- verification required before completion" in lines_after
    result = changed and duplicate_removed and verification_added
    log(
        "verify",
        f"changed={changed} duplicate_removed={duplicate_removed} verification_added={verification_added} result={result}",
    )
    return result


def simulate_blocked_write() -> None:
    target = ROOT / "outside.txt"
    log("permission", f"attempted_write={target}")
    enforce_workspace_write(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate-blocked-write", action="store_true")
    args = parser.parse_args()

    ensure_lab_files()
    log("goal", "clean local runtime notes with a gather-act-verify loop")

    if args.simulate_blocked_write:
        try:
            simulate_blocked_write()
        except PermissionError as error:
            log("permission", f"blocked=true reason={error}")
            print(error)
            return 0

    before = gather()
    after = act(before)

    if not verify(before, after):
        print("verification failed")
        return 1

    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Save the prototype as `runner.py` in a temporary exercise directory and run it with the repository virtual environment. The commands below use `.venv/bin/python` explicitly because this project expects commands to run through the checked-in virtual environment rather than an arbitrary system interpreter.

```bash
mkdir -p agent-runtime-lab
.venv/bin/python runner.py
cat agent-runtime-lab/workspace/notes.txt
cat agent-runtime-lab/logs/run.log
.venv/bin/python runner.py --simulate-blocked-write
```

The solution demonstrates the runtime pattern before asking you to build your own version later. It has a goal, a workspace boundary, a gather step, an action step, a verification step, and a durable log. The code is intentionally plain so you can see the control decisions that an SDK-based runtime would formalize with tools, permissions, hooks, and sessions.

The worked example also shows why "agent" is not a synonym for "model call." The useful behavior comes from the loop and its constraints. The model may choose how to solve the task, but the runtime defines what it may touch, what it must prove, and what evidence survives after the run.

---

## 8. Choosing Between SDK Runtime and Hand-Rolled Workflow

The Claude Agent SDK is usually a strong fit when the job is open-ended, tool-rich, and iterative. Examples include internal coding agents, documentation maintenance, research assistants, on-call triage helpers, and support agents that need to gather context from several places before deciding what to do next.

A hand-rolled workflow is usually a better fit when the job is deterministic, narrow, or highly regulated. Examples include one-shot classification, fixed extraction pipelines, financial transactions, compliance workflows with prescribed steps, and systems where every transition must be explicitly represented in application code.

The distinction is not about ambition. A hand-rolled workflow can be more professional than an autonomous agent if the business process is fixed. The SDK becomes attractive when the environment is too messy for a rigid flow but still needs operational controls that a plain chat loop cannot provide.

A practical evaluation starts with five questions. Can the task be completed by a fixed sequence of steps? Does the agent need to inspect unknown context? Are the tools mostly local or external? What is the cost of a wrong action? What evidence should be required before the run is done?

| Question | If the Answer Is Yes | Likely Direction |
|----------|----------------------|------------------|
| Is every step known in advance? | Workflow code can express the process clearly | Hand-rolled loop |
| Does the agent need to explore files or messy context? | The runtime needs flexible search and inspection | Agent SDK |
| Does the agent mutate external systems? | Tool boundaries and approvals matter heavily | MCP plus strict policy |
| Is verification deterministic? | The runtime can enforce a reliable stop condition | Agent SDK or workflow code |
| Is failure expensive or irreversible? | Autonomy should be narrow and approval-heavy | Workflow code or constrained SDK |

A senior engineer also considers organizational fit. If operators already understand Claude Code workflows, the Agent SDK can make custom agents feel familiar. If the organization has mature workflow orchestration and strict state machines, explicit orchestration may integrate more cleanly.

The safest adoption path is usually incremental. Start with read-only analysis, then allow scoped local edits, then add verification, then add external integrations through MCP, then introduce higher-risk mutations only after hooks, approvals, logs, and rollback paths are proven. Do not begin with broad autonomy simply because the SDK makes it technically possible.

There is one more tradeoff that shows up in real teams: debug visibility. A hand-rolled workflow can be easier to debug because every transition is your code. An SDK runtime can be easier to operate because tool calls, permissions, sessions, and hooks are already first-class concepts. The right answer depends on which visibility your team needs more. If auditors need a fixed state machine, explicit workflow code may win. If operators need to see a messy investigation unfold across tools, an agent runtime may be clearer.

Treat the SDK as a harness, not a guarantee. It can provide a disciplined loop, but you still decide whether the loop is appropriate for the job. A good design review should end with a sentence like: "This workflow earns L3 authority because writes are reviewed, all tools are scoped, and completion is blocked without verifier evidence." If you cannot say that sentence honestly, the runtime is not ready for that level of autonomy.

---

## Key Takeaways

- An agent runtime is the loop around the model: gather context, act through tools, verify results, and decide whether to continue or stop.
- Claude Agent SDK is the worked example in this module, but the durable concepts transfer to other harnesses: tool registry, policy, hooks, session state, observability, and verification.
- Built-in tools, MCP servers, and custom code solve different boundary problems; choose the smallest surface that makes the action clear and auditable.
- Permissions and hooks are executable runtime controls, while prompts are instructions. Serious systems need both, but only controls can prevent or record boundary violations.
- Long-running sessions need drift mitigation through verified facts, change logs, verification ledgers, and deliberate compaction or reset policies.
- The SDK is strongest when the job is open-ended and tool-rich; explicit workflow code is stronger when the process is deterministic, regulated, or audit-heavy.

---

## Did You Know?

- The Claude Agent SDK is the renamed and broader form of the Claude Code SDK, reflecting that the underlying harness can support non-coding agents as well as software-development workflows.
- The SDK supports both Python and TypeScript, which lets teams embed agent loops into backend services, automation scripts, developer tools, and web-facing applications.
- MCP is not a replacement for local tools; it is a protocol boundary for structured external integrations such as SaaS systems, databases, browsers, and internal APIs.
- Context compaction can help long-running sessions continue, but it can also preserve stale assumptions unless the runtime separates verified facts from temporary hypotheses.

---

## Common Mistakes

| Mistake | What Goes Wrong | Better Runtime Pattern |
|---------|-----------------|------------------------|
| Treating the SDK like a fancy chat wrapper | The team ignores tools, sessions, hooks, and verification, so the system behaves like an unsafe prompt loop. | Design the runtime around gather, act, verify, permissions, durable state, and observable tool use. |
| Enabling too many tools at the start | The agent's reach expands faster than the team's ability to review or contain side effects. | Start with the smallest tool set that can complete the job, then add capabilities only after a concrete need appears. |
| Using MCP for everything | Local file and shell work becomes over-abstracted, while the team loses the simplicity of built-in workspace tools. | Use built-in tools for local execution, MCP for external systems, and custom tools for domain-specific policy. |
| Relying on prompts for safety | The model may still request dangerous actions because instructions are not the same as enforceable controls. | Encode safety in permissions, hooks, approval gates, path checks, and verifier requirements. |
| Skipping verification after edits | The agent can build later actions on a broken change and return a confident but false success report. | Require deterministic verification after meaningful actions and include the exact command or external check in the final result. |
| Letting sessions accumulate stale context | Old hypotheses become treated as facts, and later decisions inherit early mistakes. | Checkpoint verified facts, compact deliberately, reset when goals change, and preserve uncertainty in session notes. |
| Adding subagents for small sequential work | Coordination overhead grows while accountability and context ownership become harder to inspect. | Use subagents only when tasks decompose naturally, can run independently, and return evidence-bounded findings. |

---

## Quiz

**Q1.** Your team built a repository assistant with a plain model client. It can call custom tools, but the application code must inspect each tool request, execute it, pass the result back, track history, and decide when to stop. The assistant now needs long-running sessions, hooks, and built-in file tools. What architectural change would you recommend, and what responsibility would still remain with your team?

<details>
<summary>Answer</summary>
The team should evaluate moving this workflow to the Claude Agent SDK because the job now needs an agent runtime rather than only a model client. The SDK can provide the agent loop, built-in tools, sessions, hooks, permissions, MCP integration, and context-management support. The team still owns the runtime design decisions: allowed tools, permission boundaries, approval rules, verification requirements, observability, and when the agent should stop or escalate.
</details>

**Q2.** A documentation agent can edit files under `docs/`, but it also has unrestricted Bash access. During a run, it tries to install packages and modify generated output because it thinks that will fix a formatting issue. Which runtime layer is weak, and how should you redesign it?

<details>
<summary>Answer</summary>
The control layer is weak because the agent has broader execution power than the task requires. The redesign should restrict edits to `docs/`, allow only the verifier command needed for the documentation workflow, block destructive or unrelated shell commands, and log every changed file. A pre-tool hook can block writes outside the allowed path, while a stop condition can require verification after the final edit.
</details>

**Q3.** An incident assistant needs to read local Kubernetes manifests, check whether a cloud load balancer exists, and create a ticket in the company's incident system. One engineer suggests doing all three through Bash commands. How would you divide the tool boundary, and why?

<details>
<summary>Answer</summary>
Local manifest inspection belongs in built-in file and shell tools because it is workspace-local execution. Cloud load balancer checks and ticket creation should go through MCP or typed external integrations because they cross system boundaries, require authentication, and need clearer audit behavior. Any organization-specific incident severity calculation could be a custom tool so business policy is enforced outside the prompt.
</details>

**Q4.** A support agent resumes a week-old session and keeps treating an early guess as confirmed truth. It sends customers answers based on that stale assumption even though newer tickets contradict it. What session design failure caused this, and what should the runtime preserve differently?

<details>
<summary>Answer</summary>
The session design failed to separate durable facts from working hypotheses. The runtime should preserve verified facts with evidence, keep hypotheses labeled as uncertain, record contradictory signals, and reset or compact context deliberately when the goal or evidence changes. Long-lived sessions are useful only when the state remains trustworthy enough to resume.
</details>

**Q5.** A manager asks for subagents because a multi-agent diagram looks more impressive. The workflow is a short sequential code review where one agent would read three files and produce a recommendation. Should you add subagents, and what criteria would change your answer?

<details>
<summary>Answer</summary>
Subagents are not justified for a short sequential workflow because they add coordination cost and make accountability harder to inspect. The answer would change if the work decomposed naturally into independent searches, required sifting through large unrelated context, or benefited from isolated specialist contexts that return evidence-bounded findings to an orchestrator.
</details>

**Q6.** A bug-fixing agent edits a file, says the patch should solve the problem, and then stops without running the failing test. The final answer is polished and includes a plausible explanation. How should the runtime have prevented this weak completion?

<details>
<summary>Answer</summary>
The runtime should require verification before completion. A stop hook or equivalent policy could refuse to finish unless the relevant test command ran after the final edit and the result was captured. The final answer should include the exact command, result, and any remaining failure rather than treating an explanation as evidence.
</details>

**Q7.** A regulated workflow must always validate an input record, call a pricing service, ask a human for approval, and then write a transaction record. The steps never vary, and discretionary tool use would create audit risk. Would you choose the Agent SDK as the main runtime or a hand-rolled workflow, and why?

<details>
<summary>Answer</summary>
A hand-rolled workflow is likely the better main runtime because the process is deterministic, regulated, and approval-heavy. Explicit application code can represent each required state transition and audit event directly. The Agent SDK might still help with surrounding analysis or drafting, but the transaction path itself should remain tightly scripted and constrained.
</details>

---

## Hands-On Exercise

**Goal:** Build a small local runtime prototype that demonstrates the same design discipline you would apply before embedding the Claude Agent SDK in a real application.

You will create a gather, act, verify loop, enforce a workspace permission boundary, record hook-like logs, and write a short design note explaining when this toy runtime should become an SDK-based agent. The exercise intentionally starts without a live API call so you can focus on runtime mechanics rather than authentication.

- [ ] Create a local exercise directory from the repository root and add a workspace plus log directory for the prototype.

```bash
mkdir -p anthropic-agent-runtime-lab/workspace anthropic-agent-runtime-lab/logs
```

- [ ] Create a sample workspace file that contains duplicated content and a missing verification note, giving the runtime a concrete problem to solve.

```bash
cat > anthropic-agent-runtime-lab/workspace/notes.txt <<'EOF'
Runtime design notes
- tools matter
- tools matter
- permissions unclear
- no verify step yet
EOF
```

- [ ] Create `anthropic-agent-runtime-lab/runner.py` with a runnable implementation of gather, act, verify, permission enforcement, and hook-like logging.

```python
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
LOGS = ROOT / "logs"
NOTES = WORKSPACE / "notes.txt"
RUN_LOG = LOGS / "run.log"


def log(stage: str, message: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} stage={stage} {message}\n")


def enforce_workspace_write(path: Path) -> None:
    workspace = WORKSPACE.resolve()
    target = path.resolve()

    if not target.is_relative_to(workspace):
        raise PermissionError(f"blocked write outside workspace: {path}")


def gather() -> list[str]:
    log("gather", f"tool=Read target={NOTES.relative_to(ROOT)}")
    return NOTES.read_text(encoding="utf-8").splitlines()


def act(lines: list[str]) -> list[str]:
    log("act", "tool=Edit target=workspace/notes.txt")
    seen = set()
    cleaned = []

    for line in lines:
        if line.startswith("- ") and line in seen:
            continue
        cleaned.append(line)
        if line.startswith("- "):
            seen.add(line)

    if "- verification required before completion" not in cleaned:
        cleaned.append("- verification required before completion")

    enforce_workspace_write(NOTES)
    NOTES.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
    return cleaned


def verify(before: list[str], after: list[str]) -> bool:
    changed = before != after
    duplicate_removed = after.count("- tools matter") == 1
    verification_added = "- verification required before completion" in after
    passed = changed and duplicate_removed and verification_added

    log(
        "verify",
        f"changed={changed} duplicate_removed={duplicate_removed} verification_added={verification_added} passed={passed}",
    )
    return passed


def simulate_blocked_write() -> None:
    target = ROOT / "outside.txt"
    log("permission", f"attempted_write={target.name}")
    enforce_workspace_write(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate-blocked-write", action="store_true")
    args = parser.parse_args()

    log("goal", "clean workspace notes and prove the result before stopping")

    if args.simulate_blocked_write:
        try:
            simulate_blocked_write()
        except PermissionError as error:
            log("permission", f"blocked=true reason={error}")
            print(error)
            return 0

    before = gather()
    after = act(before)

    if not verify(before, after):
        print("verification failed")
        return 1

    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] Run the prototype and inspect both the changed workspace file and the runtime log.

```bash
.venv/bin/python anthropic-agent-runtime-lab/runner.py
cat anthropic-agent-runtime-lab/workspace/notes.txt
cat anthropic-agent-runtime-lab/logs/run.log
```

- [ ] Trigger the blocked-write path and confirm that the permission boundary prevents a write outside `workspace/`.

```bash
.venv/bin/python anthropic-agent-runtime-lab/runner.py --simulate-blocked-write
cat anthropic-agent-runtime-lab/logs/run.log
```

- [ ] Add a `README.md` in `anthropic-agent-runtime-lab/` that maps the prototype to the Claude Agent SDK concepts from this module.

```bash
cat > anthropic-agent-runtime-lab/README.md <<'EOF'
# Agent Runtime Lab

This lab models a gather, act, verify runtime loop before introducing a live Agent SDK call.

Built-in-style local tools:
- Read the workspace file.
- Edit the workspace file.
- Run local verification through the runner.

MCP-style external tools if this became a real agent:
- GitHub issue lookup.
- Slack notification.
- Ticket creation.
- Cloud API inspection.

Runtime controls:
- Writes are allowed only inside workspace/.
- Every stage writes to logs/run.log.
- The run cannot succeed unless verification passes.

When a hand-rolled loop is enough:
- The workflow is deterministic.
- The action surface is tiny.
- Every step is known before execution.

When the Claude Agent SDK is a better fit:
- The agent must inspect unknown context.
- Tool use is iterative.
- Sessions, hooks, MCP, and permissions need to be configured instead of rebuilt.
EOF
```

- [ ] Verify that your lab demonstrates runtime behavior rather than only text generation.

```bash
grep -R "stage=verify" -n anthropic-agent-runtime-lab/logs/run.log
grep -R "blocked=true" -n anthropic-agent-runtime-lab/logs/run.log
grep -R "MCP-style external tools" -n anthropic-agent-runtime-lab/README.md
```

**Success Criteria**

- [ ] The prototype has a visible gather, act, verify loop with concrete file input and output.
- [ ] The permission rule blocks at least one attempted write outside the allowed workspace.
- [ ] The log captures goal, gather, act, verify, and blocked-permission events.
- [ ] The README correctly separates built-in local tool work from MCP-style external integrations.
- [ ] The README explains when a hand-rolled loop is enough and when the Claude Agent SDK runtime becomes the better choice.

---

## Next Module

This is the last module in the AI-Native Development sub-track. Next, return to the [AI-Native Development index](./) for review, or continue onward to [Generative AI](../generative-ai/) and [Frameworks & Agents](../frameworks-agents/) when you want deeper model and agent-system architecture.

## Sources

- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) - Official Agent SDK overview for built-in tools, hooks, subagents, MCP, permissions, and sessions.
- [How the agent loop works](https://code.claude.com/docs/en/agent-sdk/agent-loop) - Official runtime-loop reference for message flow, tool execution, permissions, budgets, compaction, and result handling.
- [Work with sessions](https://code.claude.com/docs/en/agent-sdk/sessions) - Official guidance for SDK session IDs, resume behavior, forks, and continuity patterns.
- [Handle approvals and user input](https://code.claude.com/docs/en/agent-sdk/user-input) - Official approval and user-input reference for agent runs that need human decisions.
- [Configure permissions](https://code.claude.com/docs/en/agent-sdk/permissions) - Official permission rules and modes used to constrain tool execution.
- [Intercept and control agent behavior with hooks](https://code.claude.com/docs/en/agent-sdk/hooks) - Official hook reference for pre-tool, post-tool, compaction, stop, and observability control points.
- [Give Claude custom tools](https://code.claude.com/docs/en/agent-sdk/custom-tools) - Official custom-tool reference for domain-specific capabilities inside an SDK runtime.
- [Connect to external tools with MCP](https://code.claude.com/docs/en/agent-sdk/mcp) - Official SDK MCP integration page for external tool boundaries.
- [Observability with OpenTelemetry](https://code.claude.com/docs/en/agent-sdk/observability) - Official observability page for tracing and runtime monitoring concepts.
- [Securely deploying AI agents](https://code.claude.com/docs/en/agent-sdk/secure-deployment) - Official deployment security guidance for SDK-based agents.
- [Architecture overview](https://modelcontextprotocol.io/docs/learn/architecture) - MCP's official architecture explanation of hosts, clients, servers, transports, and primitives.
- [Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices) - MCP's security guidance for trusted servers, user consent, tool descriptions, and authorization boundaries.
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) - Anthropic engineering guidance on workflows versus agents, tool design, ground truth, and stopping conditions.
- [Enabling Claude Code to Work More Autonomously](https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously) - Anthropic announcement covering Agent SDK, hooks, subagents, and autonomy improvements.
- [New Capabilities for Building Agents on the Anthropic API](https://www.anthropic.com/news/agent-capabilities-api) - Anthropic announcement for adjacent agent-building primitives, including MCP connector and code execution context.
