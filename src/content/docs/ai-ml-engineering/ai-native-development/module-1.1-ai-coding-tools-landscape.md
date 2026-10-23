---
title: "AI Coding Tools Landscape"
slug: ai-ml-engineering/ai-native-development/module-1.1-ai-coding-tools-landscape
sidebar:
  order: 202
---
> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 4-5 hours
>
> **Prerequisites**: Module 0 complete, basic Git workflow, and comfort running shell commands

---

## What You'll Be Able to Do

- Compare autocomplete, chat, IDE agent, terminal agent, local model, and protocol-connected AI coding tools by the engineering work they actually control.
- Evaluate a tool stack using context scope, edit authority, execution authority, data boundary, cost boundary, and review burden.
- Diagnose when an AI coding workflow is failing because the tool class is wrong, the context is incomplete, or the verification loop is too weak.
- Design a first-month adoption plan that starts with low-risk tasks and grows toward agentic work without bypassing source control or tests.
- Implement a repeatable tool evaluation worksheet that separates vendor claims from observed behavior on your own repository.

## Why This Module Matters

Hypothetical scenario: a platform team has three engineers, one service backlog, and four AI subscriptions spread across personal accounts. One engineer uses inline suggestions for boilerplate, another asks a browser chat to explain failing tests, and a third lets a terminal agent edit several files at once. All three say they are "using AI for coding," but they are not using the same kind of tool, accepting the same level of risk, or creating changes that can be reviewed with the same process.

That distinction matters because AI coding tools do not differ only by brand. They differ by where they run, how much of the repository they can see, whether they can edit files, whether they can execute commands, whether they can call external systems, and how billing is attached to the work. A fast inline assistant that completes a function signature is not a substitute for an agent that can run tests, and an agent that can run tests is not automatically safe to connect to production credentials.

This module gives you a practical landscape map. You will not memorize every plan name or model version, because those change too quickly. Instead, you will learn a durable evaluation model: decide what work needs to be done, identify the authority a tool needs to do that work, and put verification around the authority you grant. By the end, you should be able to choose a sane starter stack, explain why it fits your constraints, and reject tools that look impressive but solve the wrong problem.

> **Go deeper:** This phase maps tooling authority; the canonical prompt → context → harness → symphony spine lives in [AI Engineering Foundations](/ai/ai-engineering-foundations/).

## The Landscape Is About Authority, Not Hype

The easiest mistake in this space is comparing tools by model name alone. Model quality matters, but a coding workflow is shaped just as much by the tool wrapper around the model. A browser chat may use a strong model and still be awkward for a repository-wide refactor because it cannot inspect your tree, apply patches, or run tests. A smaller model inside a well-integrated agent may outperform it on a routine migration because the agent has the right files, can make edits, and can observe the test output.

Think of each tool as granting the model a specific set of permissions. Autocomplete grants permission to suggest text at the cursor. Chat grants permission to reason over pasted context. An IDE agent grants permission to inspect selected files and propose edits inside the editor. A terminal agent may receive permission to read the repository, write files, run commands, use Git, and sometimes call network tools. MCP and other connector systems extend that authority to databases, ticket trackers, documentation stores, browsers, and internal APIs.

```
Less authority                                                More authority

Autocomplete -> Chat -> IDE agent -> Terminal agent -> Connected agent
     |           |        |             |                |
     |           |        |             |                + external tools
     |           |        |             + shell and tests
     |           |        + multi-file edits
     |           + pasted or indexed context
     + current file and cursor
```

The more authority a tool has, the more valuable it can be on broad tasks and the more disciplined your verification loop must become. A wrong autocomplete suggestion is usually a local annoyance. A wrong terminal agent edit can change dependency files, loosen a test, or delete a migration unless permissions, Git hygiene, and human review catch it. This is why mature teams evaluate AI tools the way they evaluate deployment automation: what can it touch, what evidence does it produce, and how do we roll back when it is wrong?

Pause and predict: if a tool can read your repository but cannot run tests, which failure mode is more likely, a syntax error or a wrong business rule that still looks plausible? The syntax error is often easier to catch because static tools and test runners expose it quickly. The wrong business rule is more dangerous because the code can look idiomatic while silently implementing an assumption the model invented from incomplete context.

The landscape also has a billing boundary that is easy to misunderstand. A consumer chat subscription, a developer API key, an IDE subscription, and an enterprise seat are different products even when the vendor name is the same. Some tools include an agent under a subscription; others require separate API billing; some allow "bring your own key"; some route work through vendor-managed credits. Before adopting a tool, verify not only whether it can code, but which account pays for its calls and which data policy governs the code it sees.

| Tool class | Typical authority | Strong fit | Main risk |
|---|---|---|---|
| Autocomplete | Suggest text in editor | Repetitive code, tests, idioms | Confident local mistakes |
| Browser chat | Reason over pasted context | Explanations, design options, debugging snippets | Missing repository context |
| IDE agent | Read and edit selected project files | Refactors, feature slices, test repair | Over-broad edits inside the editor |
| Terminal agent | Read, edit, run commands, use Git | Multi-step tasks with verification | Unsafe command or dependency changes |
| Connected agent | Use files plus external tools | Internal docs, tickets, databases, deployment checks | Data exposure and workflow authority |

The authority diagram above is informal shorthand. The next section formalizes its **action-autonomy** dimension as a durable ladder (L0–L5) so you can compare tools by how far up they go, not by marketing labels. Note that the diagram's "connected agent" end is a *separate* authority dimension: **connectivity** (reaching external systems via MCP) widens what a tool can touch, not how autonomously it acts — which is why the Rosetta Stone tracks MCP as its own row rather than as a higher autonomy rung.

## Harness And Model Are Orthogonal Axes

A second durable axis sits beside authority: **harness** and **model** are independent choices. Confusing them leads to bad stack decisions — buying a subscription for a model you never use, or pairing a powerful harness with a model too weak for the task.

**Harness** is the agentic scaffold around the model: the loop that plans, calls tools, requests permissions, holds memory, and presents a UI or form factor (IDE panel, terminal CLI, desktop app, messaging gateway). The harness decides what the model can *do* in your environment — read files, run shell commands, open pull requests, reach MCP servers — regardless of which brain sits behind it.

**Model** is the brain: a frontier API (Claude, GPT, Gemini, and peers), a local open-weights stack (Gemma, Llama, Qwen via Ollama or similar), or specialized reasoning models (DeepSeek and others). Same harness, different model — different cost, latency, privacy boundary, and capability ceiling.

**Coupling** is how tightly harness and model are bound:

| Coupling style | What it means | Illustrative examples (current per-tool specifics live in the dated Rosetta below) |
|---|---|---|
| Model-locked | Harness ships with one vendor model family | Claude Code → Claude; Codex → OpenAI; Antigravity → Gemini |
| Model-agnostic / BYO | You supply API keys or run local weights | aider, Cline, opencode, Hermes, OpenClaw |

A model-agnostic harness on a **local** open-weights model flips the economics: marginal token cost drops toward zero, privacy improves because prompts stay on your hardware, and capability often trades down versus a frontier API. That tradeoff is intentional — not a defect — when the work is repetitive, sensitive, or cost-bound. The Rosetta Stone table later maps which tools sit in which coupling bucket.

**Durable trend (as of 2026-06; verify before relying):** model coupling is loosening. Cursor accepts bring-your-own API keys and multiple frontier providers (including xAI Grok). GitHub Copilot added a model picker (December 2025 and February 2026 releases). First-party vendor CLIs remain the most locked category, though even those are opening slightly. The pattern: **harness vendors compete on autonomy ceiling and form factor; model vendors compete on reasoning quality; open standards (MCP, AGENTS.md) decouple both from any single product.**

When you evaluate a stack, ask two questions on separate lines: (1) how much authority does this *harness* grant? (2) which *model* (and billing path) powers it? A strong model in a chat-only harness still cannot run your tests. A capable harness on a weak local model may fail on hard refactors but excel at scoped edits under a privacy policy.

## The Autonomy Ladder (L0–L5)

The authority diagram in the previous section maps to a named autonomy ladder — the AI-coding analog of SAE driving levels. Levels describe **how much driving the tool does**, not which vendor built it. Do not use product names (such as a well-known "copilot" brand) as level labels; those names collide with products and vague marketing.

```
Less autonomy                                                          More autonomy

L0          L1           L2              L3                 L4                    L5
Autocomplete  Chat assist  Inline edits    Supervised agent   Autonomous/background  Persistent autonomous
     |            |             |                 |                    |                      |
  you drive   you apply    you approve      you checkpoint      minimal per-step       long-lived,
  suggestions  answers      each multi-file   plans + acts in     approval; cloud/       messaging-driven,
               manually     diff              permission          background;            self-directed
                                                boundary            opens a PR            across sessions
```

| Level | Name | You do | Tool does | Typical form factor |
|---|---|---|---|---|
| **L0** | Autocomplete | Drive every keystroke | Suggest inline completions at the cursor | IDE extension |
| **L1** | Chat assist | Ask; copy or apply answers manually | Reason over pasted or indexed context; no write loop | Browser, app, or IDE chat panel |
| **L2** | Inline edits | Approve each proposed patch | Propose multi-file diffs inside the editor | IDE agent |
| **L3** | Supervised agent | Checkpoint plans and risky actions | Plan and act over many steps inside a permission boundary | Terminal CLI, IDE agent mode |
| **L4** | Autonomous / background | Set task; review outcome | Run a whole task toward completion with minimal per-step approval; often cloud or background; may open a PR | Coding agent, cloud worker |
| **L5** | Persistent autonomous agent | Define goals and guardrails | Long-lived, self-directed, messaging-driven; persists and may self-improve across sessions | Desktop gateway, messaging bridge |

**Key teaching point (durable):** **L1 chat is near-universal — table stakes, not a differentiator.** Most products ship chat. The informative signals are (1) the **autonomy ceiling** — how far up the ladder the tool can go on real work — and (2) whether it offers **L0 autocomplete**, which tracks the IDE form factor and daily flow-state coding. Compare tools on those axes plus harness–model coupling, not on whether they have a chat panel.

When the Rosetta Stone lists an autonomy ceiling, it means the highest level the product class supports today, not the level you must use on every task. Mature workflows mix levels: L0 for typing, L1 for design critique, L3 for test repair, L4 only with strong contracts and review.

## AI Coding Harness Rosetta Stone

**Snapshot as of 2026-06.** The AI-coding-tool landscape reorders fast — verify against each tool's docs before relying on specifics. Tools are peers; this maps capabilities, not a ranking.

| Capability | Claude Code | Codex | Antigravity | Cursor | GitHub Copilot | aider | Hermes | OpenClaw |
|---|---|---|---|---|---|---|---|---|
| Vendor | Anthropic | OpenAI | Google | Cursor | GitHub/Microsoft | open-source | Nous Research | OpenClaw Foundation |
| Form factors | CLI + IDE + desktop | CLI + cloud + app | IDE + desktop + CLI + SDK | IDE + CLI | IDE + CLI + coding agent | CLI | desktop + CLI + chat gateway | messaging gateway |
| Autonomy ceiling | L4 | L4 (cloud) | L4 (multi-agent) | L4 (background agents) | L4 (coding agent) | L3 | L5 (persistent) | L5 (persistent) |
| L0 autocomplete | no | no | yes (editor) | yes | yes | no | no | no |
| Model coupling | locked (Claude) | locked (OpenAI) | locked (Gemini) | BYO + frontier | frontier-pick (no local) | BYO + local | BYO + local | BYO + local |
| Rules file | CLAUDE.md (AGENTS.md NOT native) | AGENTS.md | AGENTS.md | .cursorrules + AGENTS.md | copilot-instructions + AGENTS.md | AGENTS.md | — | — |
| MCP client | yes | yes | yes | yes | yes | varies | varies | varies |
| Open-source | no | CLI yes | no | no | no | yes | yes (MIT) | yes |

**How to read this table:** pick the row that matches your work — form factor (IDE vs CLI vs gateway), autonomy ceiling (L3 vs L4 vs L5), and model coupling (locked frontier vs BYO vs local) — not the vendor logo. A tool with L4 background agents and no L0 autocomplete fits a different daily rhythm than an IDE with autocomplete and L3 supervised mode only. Two columns recur across many rows: **MCP** for tool connectivity and **AGENTS.md** (or product-specific equivalents) for hierarchical agent instructions. Those open standards are the durable cross-tool layer; the snapshot cells above will drift — the axes will not.

Later modules in this sub-track build on this Rosetta when comparing local models, harness configuration, and agent economics.

## Landscape Snapshot As Of 2026-06

**As of 2026-06; the landscape moves fast — verify before relying.** Product names, tiers, and prices change quarterly. The sections above teach durable evaluation axes; **this section holds volatile product and market facts only.**

### Open standards under neutral governance

The field is converging on **neutral, foundation-governed open standards** that decouple harness ⟂ model ⟂ vendor:

- **MCP (Model Context Protocol)** — Anthropic introduced it on November 25, 2024; the protocol was **donated to the Linux Foundation's Agentic AI Foundation on December 9, 2025** (co-founded by Anthropic, Block, and OpenAI, with Google, Microsoft, and AWS backing). By early 2026 the MCP SDK saw on the order of ~97M monthly downloads. MCP is the cross-vendor way tools reach files, databases, and APIs instead of bespoke integrations per product.
- **AGENTS.md** — a plain-Markdown, hierarchical (nearest-file-wins) agent-instructions convention, **also stewarded by the Agentic AI Foundation**. Codex, Cursor, Aider, Devin, Copilot, Gemini CLI, Windsurf, opencode, Zed, and others read it natively across 60,000+ projects. **Claude Code uses `CLAUDE.md` and does not currently natively read AGENTS.md** (community requests exist). Plan instructions per harness until that gap closes.

Together, MCP and AGENTS.md let teams port *policy* and *connectivity* across harness changes without rewriting everything when the model or IDE shifts.

### Form-factor convergence

Every major vendor now ships multiple form factors rather than a single surface: Anthropic (Claude Code CLI, IDE, and desktop), OpenAI (Codex CLI, cloud, and app), Google (**Gemini CLI**; **Code Assist sunsets the individual tier on June 18, 2026**, folded into Antigravity — enterprise Code Assist remains), Cursor (IDE and CLI). Convergence means your choice is often *which harness loop* you live in daily, not whether a vendor offers only chat or only an IDE.

### The autonomy frontier (L4→L5) and its economics

Persistent and background autonomy (L4–L5) is where **agentic scaling economics** bite — independent of any single vendor narrative.

Open-source persistent agents gained visibility in this window: **Hermes** (Nous Research; desktop preview around June 2026; messaging-gateway form factor; BYO/local model) and **OpenClaw** (Peter Steinberger; runs on your own hardware; reaching **~302k GitHub stars by April 2026** (unusually rapid star growth); creator joined OpenAI in February 2026; project moved toward an independent foundation).

**Cost reality (verified, neutral):** running on the order of ~100 autonomous Codex agents for 30 days cost OpenClaw's creator **\$1.3M in OpenAI API tokens** (603B tokens / 7.6M requests; that figure reflected Codex "Fast Mode" — standard mode was approximately **\$300k**; the bill was covered by OpenAI). The durable lesson: **L4/L5 autonomy on a frontier API can cost thousands per agent per month**; the **same harness class on a local open-weights model** carries **~zero marginal token cost**, trading capability for cost and privacy. Neither side is universally "better" — the fit depends on task difficulty, data boundary, and budget.

**Billing decoupling (verified; both directions):** in 2026, vendors moved programmatic and agent usage onto **separate metered credits** rather than folding unlimited agent turns into flat subscriptions. Anthropic introduced separate Agent SDK credits (effective June 15, 2026) for `claude -p`, Agent SDK, and Actions, following an April 2026 restriction and May reversal. OpenAI meters Codex Cloud and API usage similarly. Read this as the industry adjusting prices to agentic-scale economics — not as proof that any one vendor is uniquely expensive or anti-open-source.

When you reach for L4 or L5, pair the autonomy ceiling in the Rosetta with a **cost boundary** in your adoption worksheet: expected tokens per task, credit pools, and whether a local model on a BYO harness is enough for the same scope.

## Tool Families And Their Engineering Fit

The Rosetta Stone and autonomy ladder give you a cross-vendor map; this section translates those axes into **engineering fit** — which tool *class* matches which kind of repository work. When a row below mentions "IDE agent" or "terminal agent," map it to an L-level and harness form factor from the sections above rather than to a single product name.

Autocomplete-first tools are the lowest-friction entry point. GitHub Copilot, Tabnine, Codeium-style completion, VS Code Copilot features, and similar products watch the local editing context and propose the next line, block, or small function. They work well when you already know the shape of the solution and want to reduce typing. They are less useful when the correct answer depends on files the assistant cannot see or on decisions it cannot validate.

Chat-first tools are strongest when the task is conceptual rather than mechanical. A browser or app chat can explain an unfamiliar framework, compare implementation options, review a pasted function, or help you draft a specification before you give it to a more integrated coding agent. Chat is also useful as a second opinion because it is naturally separated from the write path. That separation is a feature when you want reasoning without accidental file changes.

AI-first IDEs and editor agents combine context, editing, and interaction speed. Cursor, Windsurf, Cline, Continue, Copilot Chat in an editor, and similar products let you ask questions about a project and apply changes without leaving the development surface. Their practical advantage is not only the model. It is the shortened loop from "find the relevant files" to "change them" to "review the diff." Their practical weakness is that broad edits can feel smooth enough that developers stop reading the patch carefully.

Terminal agents such as Codex-style tools, Claude Code, Gemini CLI, Aider, Goose, Open Interpreter, and related command-line workflows are closer to automation than autocomplete. They are natural when the task involves commands: inspect a test failure, edit several files, run the targeted test, read the new error, and iterate. They also fit remote and server-side environments where an editor integration is less convenient. The cost is that the terminal is a powerful place to make mistakes, so command approval, sandboxing, and Git boundaries are not optional details.

Local-model and self-hosted coding assistants solve a different problem: control. A local stack may be slower, less capable, or more operationally demanding than a hosted frontier model, but it can be attractive when source code cannot leave a machine or when a team wants predictable cost for routine suggestions. Local tools are often best for autocomplete, search, summarization, and repetitive transformations rather than for the hardest reasoning tasks. The engineering decision is whether privacy and cost control outweigh the additional setup and quality tradeoff.

Protocol-connected tools change the question from "can the assistant edit code?" to "what systems can the assistant reach?" MCP is the most visible example of this shift: it gives tools a common way to connect to filesystems, issue trackers, databases, documentation, and custom services. That is powerful for internal platform work because an agent can answer questions from live context instead of stale memory. It is also risky because tool access turns a coding assistant into a workflow participant. The 2026-06 landscape snapshot notes MCP's move to foundation governance — the protocol is the durable layer; individual product MCP menus change faster.

Before running this comparison on your own setup, choose one recent task from your Git history. Would it have benefited more from faster typing, better explanation, multi-file editing, command execution, or access to an external system such as tickets or docs? The answer tells you which tool family to evaluate first. If you choose by popularity instead, you may buy an agent when you only needed autocomplete, or install autocomplete when your bottleneck is repository-wide diagnosis.

| If the work is... | Start with... | Require before trusting output |
|---|---|---|
| Writing predictable boilerplate | Autocomplete | Local review and style consistency |
| Understanding a new codebase | Chat or IDE agent | File references and explanation checks |
| Changing many related files | IDE or terminal agent | Diff review and targeted tests |
| Fixing a failing test | Terminal agent | Re-run of the exact failing command |
| Designing security-sensitive code | Chat for critique, human-owned implementation | Threat model and security review |
| Connecting to internal systems | MCP or connector-enabled agent | Least-privilege access and audit logs |

## Context, Permissions, And Verification Loops

Every effective AI coding workflow has three loops: context in, action out, and evidence back. Context is the information the tool can use: open buffers, indexed repositories, terminal output, docs, schemas, issue text, and human instructions. Action is what the tool can change: a suggestion, a patch, a command, a generated test, or an external API call. Evidence is what proves the action worked: tests, linters, type checks, logs, screenshots, review comments, and the final Git diff.

Weak workflows usually break one of those loops. If the context is weak, the assistant fills gaps with assumptions. If the action authority is too broad, the assistant may solve the visible problem by making unrelated changes. If the evidence loop is weak, the assistant can produce polished code that nobody has actually executed. A senior engineer using AI well does not merely write better prompts; they design the loop so the model is forced to collide with reality quickly.

Here is a small adoption worksheet you can use when comparing tools. It is intentionally operational rather than emotional. If you cannot answer a row, the tool is not ready for serious use on shared code, even if the demo looked strong.

| Question | Acceptable answer for shared repos |
|---|---|
| What files can it read? | Explicit workspace scope, not home directory by default |
| What files can it write? | Repository files only, reviewed through Git diff |
| Can it run commands? | Yes only with clear approval mode and visible output |
| Can it reach network services? | Disabled or restricted unless the task needs it |
| Where do credentials live? | Outside prompts, outside committed files, and never pasted into chat |
| How is cost charged? | Known seat, subscription, credit pool, or API account |
| What evidence is required? | Targeted tests, linters, type checks, or manual acceptance notes |

The minimum verification loop for agentic tools is simple: inspect the plan, apply a narrow change, run the smallest meaningful check, read the diff, then decide whether to continue. The loop should be small enough that you can understand each increment. If an agent changes twenty files before producing evidence, you have moved from assisted development into unreviewed automation. That may be acceptable for a throwaway prototype, but it is a poor default for a repository that other people depend on.

```bash
git status --short
git diff --stat
git diff -- src/
npm test -- --runInBand
```

The command block above is not a universal test recipe; it is a habit template. Start by checking what changed, then inspect the shape of the patch, then run the most relevant test command for the stack. Python projects might use `.venv/bin/pytest`, Go projects might use `go test ./...`, and frontend projects might use `npm run test` plus a build. The important part is that the assistant's claim is not the evidence. The repository's own tools are the evidence.

Exercise scenario: an IDE agent edits a data validation function and a terminal agent edits the same function plus its tests. The IDE agent feels safer because it stayed inside the editor, but the terminal agent may be safer if it ran the exact failing tests and produced a smaller diff. Tool safety is not determined by interface alone. It is determined by the authority granted and the evidence returned.

When you evaluate a tool, record failures as carefully as successes. Did it invent a library API? Did it change formatting across unrelated files? Did it weaken a test instead of fixing the implementation? Did it ignore a project instruction file? These observations are more useful than a vague feeling that a tool is "smart" or "bad." They tell you where to use the tool and where to add guardrails.

## Building A Starter Stack Without Tool Sprawl

Beginners often try five assistants in the first week and learn none of them well. That creates noise because each tool has different shortcuts, context rules, billing behavior, and failure modes. A better starter stack has one tool for fast local help, one tool for deeper repository work, and one deliberate fallback for explanation or second opinions. The goal is not to own every category; it is to cover the main kinds of work without losing control.

For many learners, a practical stack is a familiar editor with autocomplete plus one agentic tool that can work inside a Git repository. Autocomplete handles the flow state of daily coding: names, loops, tests, adapters, and repeated patterns. The agent handles tasks that require several steps: inspect files, make a narrow change, run a check, and iterate. Browser chat remains useful for asking "teach me this concept" or "review this design" without granting write access.

Teams should add tools more slowly than individuals. A team adoption plan needs shared conventions: which repositories may be indexed, whether external model calls are allowed, how secrets are protected, which agent modes are approved, and what checks are required before review. Without those conventions, AI use becomes invisible local automation. Invisible automation is hard to audit, hard to debug, and hard for teammates to trust.

The first-month plan below is intentionally conservative. It introduces value early but reserves broad authority until developers have seen real failure modes in their own codebase.

| Week | Scope | Allowed tasks | Required evidence |
|---|---|---|---|
| 1 | Autocomplete and chat | Boilerplate, explanations, small tests | Human review of every accepted suggestion |
| 2 | IDE agent on narrow files | Refactor one function, add unit tests | Diff plus targeted test run |
| 3 | Terminal agent in sandbox | Fix a known failing test or lint issue | Command transcript and clean Git diff |
| 4 | Connected context pilot | Read docs or issue data, no write actions outside repo | Access review and audit notes |

This staged rollout avoids two common extremes. It does not pretend AI tools are harmless text expanders, and it does not treat them as autonomous engineers. It gives the tools real work while keeping the blast radius small enough for a learner or team lead to understand. After a month, you should have concrete evidence about which tasks became faster, which review checks caught mistakes, and which permissions were unnecessary.

Cost evaluation belongs in the same worksheet as technical evaluation. A tool that looks cheap per month can become expensive if every agentic turn consumes metered credits, and a tool that looks expensive can be reasonable if it replaces several separate subscriptions. Track cost by workflow, not by brand. "One test-fix session," "one multi-file refactor," and "one day of autocomplete" are more meaningful units than a plan name that may change next quarter. For L4–L5 work, add expected token or credit burn using the economics notes in the landscape snapshot — frontier API autonomy and local open-weights autonomy are different cost classes even when the harness looks similar.

## Worked Example: Choosing Tools For A Repository Migration

Exercise scenario: you maintain a small TypeScript API that uses an older validation library. The task is to migrate three request handlers to a new schema library, update tests, and keep behavior unchanged. This is not a pure autocomplete task because the work spans multiple files. It is not a broad architecture redesign because the desired behavior is already known. It is a good evaluation task because success can be checked by tests and diff review.

Start by writing the task contract before choosing the tool. The contract should name the files, the behavior that must stay stable, the commands that prove success, and the boundaries the assistant must not cross. This prevents the tool from turning a migration into an unsolicited redesign. A good contract sounds less like a wish and more like a small engineering ticket.

```markdown
Task: migrate validation in the user routes only.

Scope:
- src/routes/users.ts
- src/validation/users.ts
- tests/users.test.ts

Do:
- Replace the old schema library with the new one in these files.
- Preserve HTTP status codes and response shapes.
- Add tests for missing email, invalid email, and duplicate username.

Do not:
- Change authentication middleware.
- Reformat unrelated files.
- Add a new framework.

Evidence:
- npm test -- users.test.ts
- npm run typecheck
```

Now compare the tool options against the contract. Autocomplete can help inside each file, but it will not manage the migration loop. Browser chat can critique the plan, but it cannot reliably inspect the current tests unless you paste enough context. An IDE agent is a strong fit if it can edit the three files and show a diff. A terminal agent is also a strong fit if it can run the two evidence commands and iterate on failures. A connected agent is unnecessary unless the migration depends on tickets, internal docs, or a database schema outside the repository.

The first pass should be narrow. Ask the agent to inspect the three files and propose a plan before editing. If the plan mentions files outside scope, dependencies you did not request, or behavior changes, stop and correct it. If the plan matches the contract, allow one edit pass. After the edit, run the evidence commands yourself or let the terminal agent run them while you watch the output. The result is acceptable only when the diff is scoped and the checks pass.

Suppose the tests fail because duplicate username validation now returns a different error message. That is the exact moment where agentic tools are useful: paste or expose the failure, ask for the smallest fix that preserves the existing response shape, and re-run only the failing test. End the example when the scoped diff is clean, `users.test.ts` passes, and type checking passes. The outcome is a verified migration of three files with behavior preserved.

## Reading Vendor Claims Like An Engineer

AI coding vendors describe their products with phrases such as codebase-aware, autonomous, secure, enterprise-ready, and agentic. Those phrases are not useless, but they are not engineering requirements. A tool can be codebase-aware because it indexes your repository, because it reads only selected files, because it retrieves embeddings from a cloud service, or because it watches your open editor tabs. Each design creates a different failure mode, so the useful question is not whether the phrase appears on a product page. The useful question is how the capability behaves under test.

Treat vendor claims as hypotheses. If a tool says it understands the whole repository, ask it to locate the function that enforces a specific invariant and explain which tests protect that invariant. If a tool says it is autonomous, give it a task with a known failing test and watch whether it narrows the failure, edits only relevant files, and stops after evidence. If a tool says it is secure, inspect where prompts, code snippets, indexes, logs, and telemetry go. A claim becomes actionable only when you can map it to observable behavior.

The most important claims to test are context, persistence, execution, and isolation. Context tells you what the model can see during a turn. Persistence tells you what the system remembers after the turn ends, including project rules, previous plans, and cached indexes. Execution tells you whether the assistant can run commands or call tools. Isolation tells you whether the assistant is constrained to a workspace, a sandbox, a container, or a permission profile that prevents accidental access to unrelated files.

Before running a vendor demo on your own code, create a small claim test. Choose a repository fact that is easy for a human to verify but not obvious from one file. For example, ask where authorization is enforced for one route, which test fixture creates a disabled account, or which configuration path controls a retry limit. A tool that answers with exact file references and admits uncertainty is more trustworthy than a tool that gives a smooth explanation without evidence. The test is not measuring eloquence; it is measuring grounded retrieval.

Capability labels also hide different human interaction models. Some tools ask before every command, some ask only for risky commands, some operate in a planning mode until you approve edits, and some make changes immediately. Those modes matter because a cautious approval flow can be productive on shared code, while an aggressive flow may be better for disposable prototypes. The same model behind those modes can feel careful or reckless depending on the permission defaults.

Use a three-pass evaluation for any serious candidate. First, run a read-only task that asks the tool to explain a part of the codebase with file references. Second, run a narrow edit task with an exact success command. Third, run a recovery task where the first generated patch fails a test and the tool must interpret the failure without broadening scope. This sequence exposes whether the tool can find context, make changes, and learn from evidence.

Record the result in concrete language. "Found the correct auth middleware but missed a test fixture" is useful. "Good at codebase understanding" is too vague. "Changed three files, ran the targeted test, and stopped when the diff matched scope" is useful. "Agentic workflow felt smooth" is not enough to guide team policy. Engineering notes should let another developer reproduce the evaluation and decide whether the result matters for their work.

One subtle signal is how the tool handles uncertainty. Good coding assistants ask for missing constraints, inspect files before editing, or state that a claim is not visible from current context. Weak assistants often fill gaps with plausible defaults. In normal chat, that may sound helpful. In code, it creates unowned design decisions. If a tool repeatedly invents project rules, helper functions, or configuration names, reduce its authority until it proves it can ground answers in the repository.

Vendor comparison should finish with a fit statement, not a winner. A tool can be approved for onboarding explanations and rejected for write access. Another can be approved for terminal-based test repair and rejected for secrets-adjacent work. This keeps the decision aligned with tasks instead of identity. You are not choosing a favorite brand; you are assigning controlled authority to a tool class.

Use thresholds when the decision affects a team. For a shared repository, require at least three successful scoped tasks before approving write access, zero incidents of secret exposure, and a documented rollback path for every command-capable mode. For personal experimentation, the threshold can be lighter: one successful task, one reviewed diff, and one written note about where the tool struggled. The numbers are less important than the habit of making approval conditional on observed behavior.

The same threshold idea applies to upgrades. A new model, new extension version, or new connector can change behavior even when the product name stays the same. Re-run one read-only task and one narrow edit task after major upgrades. If the tool starts ignoring instructions, widening diffs, or changing tests carelessly, pause broad use until the team understands the regression.

Keep one deliberately boring benchmark task in the repository for this purpose. It should be small enough to run in a few minutes, stable enough that expected behavior is known, and realistic enough to touch production-style patterns. A boring benchmark catches practical regressions better than a flashy demo because it exercises the same review habits the team uses on normal work. Store the expected commands beside the benchmark so every evaluator uses the same evidence standard. Rotate the benchmark only when the underlying code path stops representing normal development and shared review expectations across routine team collaboration patterns.

## Data Boundaries And Team Governance

AI coding tools interact with source code, prompts, logs, terminal output, dependency metadata, and sometimes production-like data. That makes governance a practical engineering concern, not a legal afterthought. Even when a vendor offers strong data controls, a developer can still paste secrets into a prompt, expose an internal schema through a connector, or let an agent read files outside the intended workspace. The first governance rule is simple: classify the data path before you classify the tool as safe.

Start with four data categories. Public code and public documentation are the least sensitive. Private source code is more sensitive because it contains architecture, business logic, unreleased features, and sometimes comments that reveal internal process. Operational data is more sensitive again because logs, tickets, traces, and database snapshots can include customer or employee information. Secrets are in a separate category because they should not enter prompts, transcripts, screenshots, generated files, or tool logs at all.

The tool's interface changes the data path. Autocomplete may send local context to a hosted service, or it may use a local model, depending on configuration. Browser chat receives whatever a developer pastes. IDE agents may index repository files, store conversation history, and attach selected snippets to requests. Terminal agents may include command output in context, which means test logs and error traces can become model input. Connected agents may retrieve from systems that were never part of the repository review process.

Team policy should define allowed tool classes by repository sensitivity. An open-source sample project can tolerate broader hosted assistance than a private payments service. A documentation repository may allow browser chat with copied excerpts, while a regulated codebase may require enterprise settings, disabled training on submitted data, restricted connectors, and local-only tools for certain tasks. The point is not to block every assistant. The point is to prevent accidental escalation from "help me write a test" to "send internal customer logs to an unapproved service."

Permissions should follow least privilege. A coding agent that only needs to update Markdown does not need access to cloud credentials. An assistant that only needs a failing unit test does not need a connector to the ticket tracker. A tool that can read `~/.ssh`, `.env`, browser profiles, or unrelated workspaces is over-scoped for normal repository work. Deny rules, workspace roots, sandbox modes, and reviewable configuration files make these boundaries visible to the team.

Governance also includes prompt and transcript handling. Some teams treat prompts as disposable conversation, but prompts often contain requirements, design notes, stack traces, and code excerpts. If transcripts are stored in a vendor dashboard, local file, or team knowledge base, they need the same classification discipline as other engineering artifacts. A useful policy names what may be pasted, where transcripts may be stored, and when a transcript should be deleted or redacted.

Connected tools need extra care because they combine authority domains. A repository agent with read access to issues can use product context well. The same agent with write access to issues, deployment systems, and database tools can accidentally perform workflow actions that were never reviewed as code. For early adoption, prefer read-only connectors, explicit approval gates, and narrow scopes such as one documentation collection or one project board. Write-capable connectors should arrive only after the team has audit logs and rollback procedures.

Secrets require mechanical defenses, not reminders alone. Use `.gitignore`, secret scanning, denylisted file patterns, shell environment hygiene, and placeholder values in examples. Do not ask an assistant to "use my real token from the environment" unless the tool is explicitly designed for secure secret handling and the action is necessary. Most coding tasks can be completed with `your-api-token-here`, a mock credential, or a local test fixture that never leaves the machine.

Compliance reviews become easier when the team can show a decision record. The record should name approved tools, allowed repositories, disabled features, connector scopes, billing ownership, and required verification checks. It should also name prohibited behaviors, such as pasting production logs into consumer chat or granting a coding agent write access to deployment systems. This is lightweight compared with incident response after sensitive context leaks through an untracked workflow.

Governance is not separate from developer experience. If the approved path is slow, confusing, or underpowered, developers will route around it with personal accounts. A good policy gives people a productive default: one approved autocomplete option, one approved agentic option, clear setup instructions, and examples of tasks each tool may handle. The safer path should also be the easy path.

## Measuring Whether The Tool Actually Helps

AI coding tools can make developers feel faster before they make the team faster. A single engineer may generate code quickly while reviewers spend more time untangling broad patches, or a team may merge more lines while defect rates rise. Measurement does not need to be heavy, but it must look beyond "the assistant produced code." The relevant question is whether the workflow improves lead time, quality, learning, or maintenance without moving hidden costs to someone else.

Start with task-level measures. For each evaluation task, record time to first patch, time to verified patch, number of files changed, number of review comments, number of assistant iterations, commands run, and whether the final diff stayed in scope. These measures are more useful than total generated lines. Generated lines can increase because the tool added unnecessary abstraction. Verified task completion shows whether the tool helped produce a maintainable result.

Quality measures should include negative signals. Track hallucinated APIs, missing edge cases, weakened assertions, security concerns, dependency churn, formatting-only changes, and failures to follow repository instructions. A tool that saves ten minutes but frequently weakens tests is not saving time; it is borrowing risk from the future. Conversely, a tool that is slower but consistently produces narrow patches with strong tests may be valuable for onboarding or unfamiliar code.

Review load is a key metric for teams. AI-generated patches often look polished, which can make reviewers skim. That is dangerous because the mistakes are not always syntactic; they are often assumption errors. Track whether reviewers need more time to understand AI-authored patches, whether generated tests clarify or obscure intent, and whether the assistant's transcript helps explain the design. If the review burden rises, reduce task size or require better contracts before edits.

Learning value matters in a curriculum setting. A tool that only writes code for the learner can slow skill development if the learner stops reading. A tool that explains choices, shows alternatives, and helps connect failures to concepts can accelerate learning. Measure this with small checks: can the learner explain the final diff, name the evidence that proves it works, and identify one edge case the assistant missed? If not, the workflow produced output without understanding.

Use paired tasks when possible. Run one small task manually, one with autocomplete, and one with an agent. Keep the tasks similar in risk and size. You are not trying to conduct a formal academic study; you are calibrating your own workflow. The comparison often reveals that autocomplete wins for small local edits, agents win for test-driven multi-file tasks, and manual work still wins when the problem is ambiguous or business-specific.

The most honest productivity metric is verified cycle time. Start the clock when the task is clear enough to begin, and stop when the patch is reviewed locally with evidence. Do not stop when the assistant prints code. Do not ignore time spent rewriting prompts, reverting unrelated edits, or debugging generated tests. AI changes where the time goes. Good measurement follows the whole loop, not just the impressive middle.

There is also a maintenance horizon. Revisit accepted AI-assisted changes after a week or two of normal development. Did the code remain easy to modify? Did generated abstractions survive contact with real requirements? Did tests catch later regressions? Some assistant output is locally correct but stylistically alien to the codebase, which creates friction later. Maintenance review catches that cost.

For team reporting, avoid vanity metrics such as "percentage of code written by AI." That number is easy to inflate and hard to interpret. A healthier report says which task classes are approved, which checks are required, what failure modes were observed, and where the tool saved verified cycle time. This gives engineering leaders decisions they can act on: expand, restrict, train, or replace the workflow.

The final measurement artifact can be a one-page scorecard. Give each tool a rating for context grounding, scoped edits, command execution, test repair, security behavior, cost clarity, and developer learning. Add a short note with one task it handled well and one task it should not handle yet. That scorecard becomes the bridge between individual experimentation and team standards.

## Did You Know?

- GitHub Copilot became generally available in 2022, which makes modern AI-assisted coding a very young practice compared with Git, continuous integration, or cloud deployment.
- Anthropic introduced the Model Context Protocol in November 2024 to standardize how assistants connect to tools and data sources instead of relying on one-off integrations.
- Terminal coding agents changed the workflow boundary because they can observe command output, not just produce text. That moves them closer to build automation than to traditional autocomplete.
- Long context does not remove the need for selection. A tool can fit more files in context and still fail if the important requirement lives in an issue, a test fixture, or an undocumented production rule.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Choosing by model name only | The wrapper, permissions, and evidence loop matter as much as raw model quality | Compare tool authority and verification behavior on your own repository |
| Treating chat subscriptions as API access | Vendors often separate consumer chat, developer APIs, and coding agents | Confirm the billing product before building a workflow around it |
| Giving an agent the whole repo for a small task | Broad context feels helpful but invites unrelated edits | Name the exact files and success checks before edits begin |
| Accepting generated tests without inspecting them | Tests can encode the assistant's mistaken assumptions | Review test intent and make sure assertions protect real behavior |
| Letting tools see secrets | Prompts and tool logs can persist outside the local shell | Use placeholders, secret managers, and deny rules for sensitive files |
| Skipping Git review because the agent ran tests | Passing tests do not prove the patch is scoped or maintainable | Read `git diff` and reject unrelated changes |
| Piloting too many tools at once | Switching costs hide whether the workflow is actually improving | Run one evaluation task per tool family and record results |

## Quiz

<details>
<summary>Question 1: Your team needs to add docstrings and simple tests to a group of similar utility functions. The code is low risk, repetitive, and already has clear examples nearby. Which tool family should you try first?</summary>

Start with autocomplete or an editor-integrated assistant, because the task is repetitive and local. A terminal agent could do it, but the extra authority is not necessary for a low-risk pattern completion task. The key evidence is still review of the generated tests and a targeted test run, because generated tests can copy incorrect assumptions from the implementation.
</details>

<details>
<summary>Question 2: An agent proposes changing a validation library, rewriting unrelated middleware, and reformatting half the repository in one patch. What diagnosis fits this failure?</summary>

The tool was given too much action authority for an underspecified task. The right response is to stop, restate scope with exact files and forbidden changes, and ask for a smaller plan before allowing edits. Running tests is not enough here because the main problem is uncontrolled blast radius, not only correctness.
</details>

<details>
<summary>Question 3: A developer says their paid web chat account should automatically work with every terminal coding tool from the same vendor. What should you check before agreeing?</summary>

Check whether the coding tool uses the consumer subscription, a separate API key, an IDE seat, or a vendor-managed credit plan. These products are often separate even when they share a brand and model family. The practical fix is to read the current vendor documentation and confirm the billing path before installing the tool into a team workflow.
</details>

<details>
<summary>Question 4: A browser chat gives a convincing answer about a failing integration test, but it has only seen the error message and one helper function. What is the likely weakness in this workflow?</summary>

The context loop is weak. The assistant may reason well from the pasted snippet, but it cannot see fixtures, configuration, recent diffs, or the code path that triggers the failure. A better workflow is to provide the relevant files or use an IDE or terminal agent that can inspect the repository, then require the exact failing test to pass.
</details>

<details>
<summary>Question 5: A team wants an assistant to read internal deployment docs and query a ticket system while coding. Which landscape concept becomes important, and what guardrail should come first?</summary>

Connected agents and MCP-style tool access become important because the assistant needs external context beyond repository files. The first guardrail should be least-privilege access: read-only where possible, scoped connectors, no production secrets in prompts, and auditability for tool calls. Without that, the assistant becomes an untracked workflow actor.
</details>

<details>
<summary>Question 6: A terminal agent fixes a failing test and shows that the command now passes, but the diff also weakens a security assertion. Should the patch be accepted?</summary>

No. The evidence loop is incomplete because the targeted test passing does not prove the change preserves the intended protection. The correct response is to reject the weakened assertion, restore the security expectation, and ask for an implementation fix that satisfies the original test intent.
</details>

<details>
<summary>Question 7: You are designing a first-month rollout for a team that has never used coding agents. Why is a staged rollout better than immediately enabling repository writes and external connectors?</summary>

A staged rollout lets the team learn failure modes while the blast radius is small. Autocomplete and chat reveal suggestion quality, narrow IDE tasks reveal diff discipline, terminal tasks reveal command and test behavior, and connectors introduce data-access questions last. This creates evidence for policy decisions instead of relying on vendor demos.
</details>

## Hands-On Exercise: Evaluate One AI Coding Tool

Use a non-production repository or a disposable branch for this exercise. Pick one tool you already have access to, then evaluate it against a small task that can be verified by tests, type checks, or a build. The task should touch enough code to be meaningful but not enough to create a messy review. Good candidates include adding validation tests, converting one module to stricter types, improving error handling in one function, or documenting a small public API.

### Task 1: Write The Evaluation Contract

- [ ] Name the tool, tool family, billing boundary, and model if the interface exposes it.
- [ ] Define the exact files or directories the tool may read and edit.
- [ ] Write the success command, such as a targeted test, type check, or lint command.
- [ ] Write two forbidden changes, such as dependency upgrades or unrelated formatting.

<details>
<summary>Solution guidance</summary>

A usable contract might say: "Use an IDE agent to update `src/validation/user.ts` and `tests/user-validation.test.ts`; do not change authentication, package files, or formatting-only lines; success is `npm test -- user-validation.test.ts`." The contract is good when another developer can tell whether the assistant stayed inside it.
</details>

### Task 2: Run One Narrow Assistant Pass

- [ ] Ask the tool to inspect context and summarize a plan before editing.
- [ ] Reject the plan if it touches files outside the contract.
- [ ] Allow one edit pass only after the plan matches the scope.
- [ ] Save the raw prompt or transcript location if your team process allows it.

<details>
<summary>Solution guidance</summary>

Do not start by asking for the entire finished feature. A useful first prompt is: "Inspect only these files and propose the smallest change plan. Do not edit yet." That lets you evaluate whether the tool respects boundaries before it has write authority.
</details>

### Task 3: Verify The Patch

- [ ] Run the success command from the contract.
- [ ] Inspect `git diff --stat` and the full diff for unrelated edits.
- [ ] Record any hallucinated APIs, weakened tests, formatting churn, or scope drift.
- [ ] Decide whether the tool is approved for similar tasks, approved with restrictions, or rejected for now.

<details>
<summary>Solution guidance</summary>

Your result should be a short evaluation note, not a feeling. For example: "Approved for single-module test additions; failed once by inventing a helper name; requires human test review; no external connectors needed." That note is more useful for future work than a generic statement that the tool was good or bad.
</details>

### Success Criteria

- [ ] The tool family is identified by authority, not only by vendor name.
- [ ] The evaluation contract includes scope, forbidden changes, and evidence commands.
- [ ] The final diff is reviewed manually.
- [ ] The final decision names at least one approved use and one restricted use.

## Learner check

Before moving on, confirm you can explain the two orthogonal axes and use the Rosetta without treating it as a ranking. In your own words, answer: which autonomy level is table stakes, and which levels actually differentiate tools?

> **Key teaching point (durable):** **L1 chat is near-universal — table stakes, not a differentiator.** Most products ship chat. The informative signals are (1) the **autonomy ceiling** — how far up the ladder the tool can go on real work — and (2) whether it offers **L0 autocomplete**, which tracks the IDE form factor and daily flow-state coding. Compare tools on those axes plus harness–model coupling, not on whether they have a chat panel.

## Sources

- [OpenAI Codex documentation](https://developers.openai.com/codex)
- [OpenAI code generation guide: Use Codex](https://developers.openai.com/api/docs/guides/code-generation#use-codex)
- [Claude Code overview](https://code.claude.com/docs/en/overview)
- [GitHub Copilot documentation](https://docs.github.com/en/copilot)
- [Visual Studio Code Copilot overview](https://code.visualstudio.com/docs/copilot/overview)
- [Cursor documentation](https://cursor.com/docs)
- [Windsurf getting started documentation](https://docs.windsurf.com/windsurf/getting-started)
- [Gemini CLI official repository](https://github.com/google-gemini/gemini-cli)
- [Aider documentation](https://aider.chat/docs/)
- [Cline documentation](https://docs.cline.bot/home)
- [Continue documentation](https://docs.continue.dev/)
- [Model Context Protocol introduction](https://modelcontextprotocol.io/docs/getting-started/intro)
- [Tabnine getting started documentation](https://docs.tabnine.com/main/getting-started/install)
- [Open Interpreter introduction](https://docs.openinterpreter.com/getting-started/introduction)
- [Goose official repository](https://github.com/aaif-goose/goose)
- [Anthropic: MCP donated to Agentic AI Foundation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation)
- [Linux Foundation: Agentic AI Foundation formation](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [AGENTS.md specification](https://agents.md/)
- [Google Developers Blog: Transitioning Gemini CLI to Antigravity CLI](https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- [OpenClaw (Wikipedia)](https://en.wikipedia.org/wiki/OpenClaw)
- [Nous Research](https://nousresearch.com/)
- [Tom's Hardware: OpenClaw Codex token cost report](https://www.tomshardware.com/tech-industry/artificial-intelligence/openclaw-creator-burns-through-1-3-million-in-openai-api-tokens-in-a-single-month)
- [The Next Web: autonomous agent API economics at scale](https://thenextweb.com/news/openclaw-peter-steinberger-1-3-million-openai-token-bill)
- [Anthropic Support: Claude Agent SDK and subscription credits](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
- [The New Stack: Anthropic Agent SDK credit pools](https://thenewstack.io/anthropic-agent-sdk-credits/)

## Next Module

Next: [Local Models for AI Coding](/ai-ml-engineering/ai-native-development/module-1.2-local-models-for-ai-coding/) — the **model axis**: local vs cloud inference, and pairing models with harnesses from the Rosetta Stone.
