---
title: "LangChain Advanced"
slug: ai-ml-engineering/frameworks-agents/module-1.2-langchain-advanced
sidebar:
  order: 503
---


## What You'll Be Able To Do

- **Compose** multi-step LCEL pipelines from prompts, models, parsers, and routers using Runnable composition patterns you can test without live API keys.
- **Design** distinct tool schemas with Pydantic validation that guide models toward accurate tool selection, safe execution, and minimal token overhead.
- **Integrate** memory policies, retrieval tools, and `create_agent` loops into cohesive workflows that ground answers in verified external data instead of model weights.
- **Debug** agent execution loops using streaming events, callback handlers, verbose traces, and intermediate-step inspection when routing fails in production.
- **Apply** production patterns including least-privilege tools, structured error handling, caching layers, recursion limits, and cost-aware payload shaping.


## Why This Module Matters

Hypothetical scenario: A customer-support chatbot answers refund questions by generating policy text from model weights instead of calling a deterministic policy service. When the generated answer disagrees with the real policy, the business absorbs reputational damage and manual remediation cost. The failure mode is structural: the system treated the language model as a database rather than a reasoning engine that should orchestrate verified tools.

Hypothetical scenario: A financial analysis agent works in staging but generates excessive external API traffic in production because follow-up questions trigger fresh market-data calls without caching, recursion limits, or tight tool constraints. The model is not malicious; the architecture simply never encoded cost boundaries at the tool layer. Advanced LangChain work is therefore about composable primitives—runnables, tools, memory, retrievers, agents, callbacks, and streaming—wired together with explicit contracts that survive framework churn.

This module teaches the durable spine of LangChain orchestration: how to compose pipelines with LCEL, how to expose safe tools, how to ground agents with retrieval and memory, how to observe execution with callbacks and streaming, and how to harden deployments for security and cost. You already saw fundamentals in the sibling module [LangChain Fundamentals](/ai-ml-engineering/frameworks-agents/module-1.1-langchain-fundamentals/); here we go deeper into the patterns production teams reuse even when import paths change quarterly. When agent state and routing grow beyond a linear chain, the next step is [LangGraph for Agents](/ai-ml-engineering/frameworks-agents/module-1.3-langgraph-for-agents/).

> **LangChain landscape snapshot — as of 2026-09.** LangChain reorganizes APIs frequently; verify against current docs before relying on import paths or class names. Package layout at authoring time (`langchain` 1.4.x): `langchain-core` (Runnable/LCEL primitives—still the composition spine), provider packages (`langchain-openai`, etc.), `langchain-community` (integrations), higher-level `langchain` (agents via `create_agent`). Legacy `AgentExecutor` / `create_tool_calling_agent` live in maintenance `langchain-classic`. `create_agent` compiles a LangGraph; pass a `checkpointer` (or drop the graph into a larger StateGraph) when you need durable threads, human approval, or custom cyclic workflows.


## LCEL and Runnables

LangChain Expression Language (LCEL) is the composable spine of modern LangChain. Every serious component implements the Runnable interface: you can invoke it synchronously, await it asynchronously, batch inputs, and stream partial outputs with the same surface area. That uniformity matters because LLM applications are not one HTTP call—they are pipelines of prompts, models, parsers, routers, retrievers, and validators. When each step shares Runnable semantics, you can test, trace, and swap steps without rewriting the orchestration layer every time a provider changes its SDK.

The pipe operator is syntactic sugar for sequential composition. Conceptually, `prompt | model | parser` means: render the prompt from input variables, pass the rendered messages to the model, then parse the model text into application data. Under the hood each stage calls `invoke` on the previous stage's output. This is the same mental model as a Unix pipeline or a data-engineering DAG, except the transformations are probabilistic at the model boundary and deterministic everywhere else.

Parallel composition appears when multiple branches consume the same input without depending on each other. RunnableParallel lets you fan out work—summarize, classify, and extract metadata from the same document—then merge results into one dictionary for a downstream step. That pattern reduces latency compared with three serial model calls and keeps each branch's contract explicit. When one branch fails, you can catch the failure at the merge point instead of losing the entire request.

Branching and routing extend LCEL beyond straight lines. A router inspects input—intent label, keyword, or classifier output—and selects which sub-chain should run. This is how teams keep tool catalogs manageable: instead of presenting fifty tools to one agent, a lightweight router chooses a focused subset. Routing is a durable pattern whether you implement it with RunnableBranch, a custom function, or an outer orchestrator like LangGraph.

The following example uses `langchain_core` fakes so you can run it locally without API keys. It demonstrates sequential composition, parallel fan-out, and a simple passthrough merge—patterns you will reuse in retrieval and agent pipelines throughout this module.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

# Fake model returns deterministic text for tests.
# The iter() wrapper yields one queued message per invoke; after the queue
# exhausts, the next call raises StopIteration—rebuild the iterator for multi-turn tests.
fake_llm = GenericFakeChatModel(messages=iter([
    AIMessage(content="Intent: billing"),
    AIMessage(content="Summary: user asked about invoice timing."),
]))

classify_prompt = ChatPromptTemplate.from_messages([
    ("system", "Classify intent in one short phrase."),
    ("human", "{question}"),
])
summarize_prompt = ChatPromptTemplate.from_messages([
    ("system", "Summarize the user question in one sentence."),
    ("human", "{question}"),
])

classify_chain = classify_prompt | fake_llm | StrOutputParser()
summarize_chain = summarize_prompt | fake_llm | StrOutputParser()

router = RunnableParallel(
    intent=classify_chain,
    summary=summarize_chain,
)
enrich = router | RunnableLambda(lambda d: {**d, "route": "billing" if "billing" in d["intent"].lower() else "general"})

print(enrich.invoke({"question": "Where is my invoice for March?"}))
```

Testing LCEL chains without live models is a production habit, not a classroom trick. Fake chat models, stub retrievers, and RunnableLambda stand-ins let you assert on output shape, routing decisions, and parser behavior in ordinary unit tests. When a provider bumps a SDK version, those tests tell you whether your composition still honors contracts even before you spend tokens on integration runs.

Assign runnables (`RunnablePassthrough.assign`) are the idiomatic way to enrich inputs mid-pipeline. You might attach a session identifier, redact sensitive fields, or compute a cache key before the prompt renders. Because assign returns a new runnable, you keep side effects localized and observable rather than hiding mutations inside prompt templates.

Fallback runnables wrap primary and secondary models or parsers. If the primary model times out, the fallback can be a smaller local model or a deterministic template response. Document fallback behavior in runbooks so on-call engineers know which quality bar applies during partial outages.

**LCEL version gotchas.** Between langchain-core 0.1 and 0.3 releases, `RunnableBranch` condition signatures and streaming event shapes changed subtly—code that relied on `stream_log` event keys may need updates when upgrading. The pipe operator itself is stable, but helper imports (`RunnablePassthrough`, `RunnableParallel`) occasionally move from `langchain` to `langchain_core.runnables`. Pin `langchain-core` in `requirements.txt` and diff golden outputs per Runnable stage after every bump; a green import does not guarantee identical stream chunk boundaries. Async `ainvoke` on chains that mix sync tools and async models requires explicit `asyncio` bridges—calling sync tools inside async runnables without `asyncio.to_thread` blocks the event loop under load.

## Tools and Tool-Calling

Large language models generate text; they do not natively check live weather, query your database, or send email. Tool calling (also called function calling) closes that gap: the model emits a structured request, your application executes the function, and the model incorporates the result into its next turn. LangChain's tool abstractions generate JSON schemas from Python functions so you do not hand-maintain provider-specific wire formats for OpenAI, Anthropic, and Google.

The tool description is the routing signal. Models rarely read your implementation; they read the name, description, and parameter docs you expose. Vague descriptions cause wrong-tool selection; overlapping descriptions cause random guessing. Production teams invest more time in docstrings and schema examples than in clever prompt hacks because schema quality is the cheapest lever for reliability.

LangChain offers three common authoring paths: the `@tool` decorator for simple functions, StructuredTool with Pydantic args_schema for validation, and BaseTool subclasses when you need dependency injection or custom async behavior. All three compile down to the same tool contract the model sees. Pick the path that matches how strictly you must validate inputs before side effects occur.

Before a language model can effectively use a software tool, it must comprehend the tool's mechanics through metadata: name, description, parameters, and return shape. This critical information is transmitted via a tool schema, traditionally structured in JSON. The schema acts as the interface contract between the LLM's generative text capabilities and your deterministic backend system.

Writing pure JSON schemas by hand is tedious and prone to syntactic errors. Maintaining synchronization between a manual JSON schema and the underlying Python function signature is a recipe for drift. LangChain's decorator and StructuredTool paths auto-generate schemas at runtime from type hints and docstrings.

```python
# A tool schema tells the LLM everything it needs to know
weather_tool_schema = {
    "name": "get_weather",
    "description": "Get the current weather for a location. Use this when the user asks about weather, temperature, or conditions for a specific place.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and country, e.g., 'Tokyo, Japan' or 'New York, USA'"
            },
            "units": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature units. Default is celsius."
            }
        },
        "required": ["location"]
    }
}
```

```python
from langchain_core.tools import tool

@tool
def get_weather(location: str, units: str = "celsius") -> str:
    """Get the current weather for a location.

    Use this when the user asks about weather, temperature, or
    conditions for a specific place.

    Args:
        location: The city and country, e.g., 'Tokyo, Japan'
        units: Temperature units - 'celsius' or 'fahrenheit'

    Returns:
        A string describing the current weather conditions.
    """
    return f"Weather in {location}: 22 {units[0].upper()}, sunny"
```

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    """Input schema for weather tool."""
    location: str = Field(description="City and country, e.g., 'Tokyo, Japan'")
    units: str = Field(default="celsius", description="celsius or fahrenheit")

def get_weather_impl(location: str, units: str = "celsius") -> str:
    """Implementation of weather lookup."""
    return f"Weather in {location}: 22 {units[0].upper()}, sunny"

weather_tool = StructuredTool.from_function(
    func=get_weather_impl,
    name="get_weather",
    description="Get current weather for a location",
    args_schema=WeatherInput,
    return_direct=False,
)
```

```python
from langchain_core.tools import tool
from typing import Optional
import subprocess
import os

@tool
def run_shell_command(command: str) -> str:
    """Execute a shell command and return the output.

    Use this for:
    - Running tests: "pytest tests/"
    - Checking git status: "git status"
    - Installing packages: "pip install package_name"
    - Any other shell operation

    Args:
        command: The shell command to execute

    Returns:
        Command output (stdout + stderr) or error message
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return output if output else "Command completed with no output"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

@tool
def read_file(file_path: str, max_lines: Optional[int] = 100) -> str:
    """Read the contents of a file.

    Use this to examine source code, configuration files, log files, or documentation.

    Args:
        file_path: Path to the file (relative or absolute)
        max_lines: Maximum lines to read (default 100)

    Returns:
        File contents or error message
    """
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()[:max_lines]
            content = "".join(lines)
            if len(lines) == max_lines:
                content += f"\n... (truncated, showing first {max_lines} lines)"
            return content
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def search_code(pattern: str, directory: str = ".") -> str:
    """Search for a pattern in code files using grep.

    Use this to find function definitions, locate imports, or find usage of variables.

    Args:
        pattern: Regex pattern to search for
        directory: Directory to search in (default: current)

    Returns:
        Matching lines with file paths and line numbers
    """
    try:
        result = subprocess.run(
            f'grep -rn "{pattern}" {directory} --include="*.py" --include="*.js" --include="*.ts" | head -50',
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if not output:
            return f"No matches found for pattern: {pattern}"
        return output
    except Exception as e:
        return f"Error searching: {str(e)}"
```

**Warning:** The `run_shell_command` example above passes LLM-chosen strings to `subprocess.run(..., shell=True)` with no validation—it exists to show tool wiring, not production safety. Real deployments must whitelist commands, reject shell metacharacters, and sandbox execution; see the `SafeCommandInput` pattern later in this module for a hardened approach.

Tool categories help you reason about blast radius. Data retrieval tools should be read-only by default. Communication tools need rate limits. System operation tools require authentication context passed from your app layer, not inferred from chat text alone.

Hierarchical tool organization consolidates related actions under a meta-tool with an action parameter. Instead of twenty flat functions, present one developer_tools meta-tool whose docstring enumerates allowed actions. This reduces schema tokens in the prompt and gives the model a clearer decision tree.

Provider wire formats differ—OpenAI nests parameters under function objects, Anthropic uses input_schema, Google uses its own variant. LangChain normalizes these differences when you use first-class tool abstractions. Manual JSON dictionaries reintroduce the protocol mismatch bugs you thought you eliminated.

**Tool performance and cost.** Every tool bound to a chat model inflates the system prompt with full JSON schemas—fifteen tools can add thousands of definition tokens per request even when the model picks one. Measure definition-token overhead separately from conversation history when debating flat catalogs versus meta-tools. Parallel tool calls (supported by OpenAI and Anthropic on recent models) cut wall-clock latency for independent reads but burst downstream API quotas; coordinate per-vendor concurrency limits. Cache idempotent tool results with TTL keys derived from normalized arguments, not raw model strings that vary cosmetically.

## Memory

Models are stateless unless you resend prior context. Memory in LangChain is not magic persistence—it is a policy for what conversation history, summaries, or entity facts get injected into the next prompt. The design question is always the same: what should the model see next, and what should never be copied forward for privacy, cost, or correctness reasons?

ConversationBufferMemory keeps recent turns verbatim, which maximizes fidelity but grows tokens linearly. ConversationSummaryMemory compresses older turns through a summarization call, trading exact wording for headroom. ConversationSummaryBufferMemory combines both: keep the last k turns exact, summarize everything older. For agents, memory must coexist with tool results—if you store huge tool payloads in history, you will blow context limits even when the user's question was small.

Entity memory tracks facts about named entities across turns—customer identifiers, project codenames, regions. Token-buffer memory enforces a hard cap by dropping oldest messages. Regardless of flavor, treat memory as untrusted input on the next turn: users can steer what gets remembered, and tool outputs can contain injection payloads. Sanitize, cap, and audit what memory writes just as you would audit retrieval chunks.

When you integrate memory with LCEL, wrap the memory load and save steps as RunnableLambdas or use built-in history-aware runnables. The durable pattern is explicit: load variables from a session store, render the prompt with history placeholders, invoke the model, then persist only the new turn plus any structured facts you truly need. Avoid storing raw tool JSON in long-term memory unless your compliance review explicitly allows it.

The example below simulates a sliding window buffer without external databases. It shows how to trim history before each invoke—a technique you will combine with agents in the next sections.

```python
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

MAX_TURNS = 6
session_store: dict[str, list] = {}

def load_history(inputs: dict) -> dict:
    sid = inputs["session_id"]
    history = session_store.get(sid, [])
    return {**inputs, "history": history[-MAX_TURNS:]}

def save_turn(inputs: dict) -> dict:
    sid = inputs["session_id"]
    session_store.setdefault(sid, []).extend([
        HumanMessage(content=inputs["question"]),
        AIMessage(content=inputs["answer"]),
    ])
    return inputs

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise assistant."),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

# Fake answer step for offline demo
answer = RunnableLambda(lambda d: {**d, "answer": f"Echo: {d['question']}"})

chain = (
    RunnablePassthrough.assign(**{"history": RunnableLambda(load_history) | (lambda d: d["history"])})
    | prompt
    | answer
    | RunnableLambda(save_turn)
)

chain.invoke({"session_id": "demo", "question": "Hello"})
print(session_store["demo"])
```

Session identifiers should come from your authentication layer, never from model-generated text. If the model can choose its own session key, attackers can read another user's history by guessing identifiers. Treat memory stores like databases with access control lists and encryption at rest.

Summarization memory introduces an extra model call. Monitor summarization drift: if summaries omit negation or numeric constraints, downstream answers inherit the mistake. Periodic full-history refresh for high-stakes workflows reduces silent summary corruption.

**Memory migration notes.** LangChain 0.2+ moved many memory classes from `langchain.memory` to `langchain_community` and deprecated several chain-centric memory wrappers in favor of explicit message-history stores plus LCEL. `ConversationBufferMemory` still works but LangGraph checkpointing is now the recommended path for durable multi-turn agent state. If you upgrade mid-project, audit every `MessagesPlaceholder` binding—history key names (`chat_history` vs. `history`) differ across templates and cause empty-context bugs that look like model amnesia.

## Retrieval Integration

Retrieval-augmented generation belongs inside agent systems as a first-class tool, not only as a static prefix prompt. When the model can decide whether to search documentation, it fetches context on demand instead of stuffing every prompt with irrelevant chunks. LangChain retrievers implement Runnable: you pass a query string and receive documents with metadata.

A typical retrieval tool wraps embed-query, vector search, and formatting steps. Keep returned text concise—titles, snippets, and source URLs—not entire PDFs. Agents chain retrieval with synthesis: search, read top matches, maybe call a detail tool, then answer. This mirrors how human analysts work and keeps token usage closer to the minimum needed for grounding.

Hybrid patterns combine retrieval with structured database tools. Use retrieval for unstructured knowledge such as policies and runbooks, and SQL or API tools for authoritative transactional data such as order status or account balance. The durable lesson is separation of concerns: never let the model invent numbers that a tool could fetch, and never let a retrieval chunk override a tool result without explicit reasoning in the trace.

The retrieval-augmented tool pattern below mirrors production architectures where the agent explicitly queries a vector store when it detects a knowledge gap. Replace the in-memory list with your vector database in real deployments.

```python
from langchain_core.tools import tool

MOCK_DOCS = [
    {"source": "runbook.md", "text": "Restart the indexer pod if lag exceeds five minutes."},
    {"source": "policy.md", "text": "Refunds require manager approval above five hundred dollars."},
]

@tool
def answer_from_docs(question: str) -> str:
    """Answer questions using our documentation.

    This tool searches our vector database of documentation
    and returns relevant information to answer the question.
    """
    hits = [d for d in MOCK_DOCS if any(w in d["text"].lower() for w in question.lower().split())]
    if not hits:
        hits = MOCK_DOCS[:2]
    context = "\n\n".join(f"From {r['source']}:\n{r['text']}" for r in hits)
    return f"Relevant documentation:\n\n{context}"
```

Chunk metadata powers citation in agent answers. Return source filenames, section headings, and last-updated timestamps alongside snippets so the model can quote responsibly. Users trust answers more when the agent cites retriever metadata instead of speaking ex cathedra.

Re-ranking retrieved chunks before they enter the tool result often improves answer quality more than enlarging k. Keep re-rankers behind the same Runnable interface so you can A/B them in staging without rewriting agent prompts.

**Retrieval edge cases.** Empty vector-store results should return an explicit "no documents found" string, not an empty tool payload—the model may hallucinate when given blank context. Stale embeddings after document updates cause confident wrong answers; version your index and include `last_updated` in chunk metadata so agents can warn users about outdated policies. Hybrid search (dense + BM25) reduces misses on exact SKU or error-code queries that pure embedding search mishandles.

## Agents and the Agent Loop

An agent is a loop, not a single completion. The model receives tools, chooses an action, observes the tool result, and repeats until it produces a final answer or hits a guardrail. The ReAct pattern—reasoning interleaved with acting—formalizes this loop and remains the mental model even when frameworks rename their harness classes.

`create_agent` is the LangChain 1.x entry point: it binds the model, tools, and system prompt and returns a compiled graph that loops until the model emits no more tool calls. Cap runaway loops with `recursion_limit` on invoke (or `.with_config({"recursion_limit": N})`). Inspect `result["messages"]` for tool calls and `ToolMessage` observations. Temperature near zero is common for tool routing because creativity in JSON tool selection is usually a liability.

Tool-calling agents differ from text-only ReAct agents: modern chat models emit native tool_call objects instead of parsing Thought/Action/Observation strings from free text. LangChain 1.x agents assume structured `tool_calls`; mismatch manifests as ignored tools or infinite retries. Recover from tool failures with `handle_tool_error` on the tool or middleware that implements `wrap_tool_call`—do not expect a `handle_parsing_errors=` knob on the harness.

When durable threads, human approval, or custom cyclic graphs enter the picture, add a `checkpointer` to `create_agent` or compose LangChain tools and retrievers into an explicit LangGraph. The ReAct loop taught here is still the conceptual foundation.

**Legacy note.** `AgentExecutor` and `create_tool_calling_agent` are not on the `langchain.agents` mainline in 1.x (`ImportError` if you copy old tutorials). They live in maintenance `langchain-classic` (`from langchain_classic.agents import AgentExecutor, create_tool_calling_agent`). Keep the ReAct mental model; do not start new work on the classic executor.

```python
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

tools = [run_shell_command, read_file, search_code]

# create_agent calls model.bind_tools(); GenericFakeChatModel leaves that abstract.
class BindableFakeChatModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

# In production swap for your provider LLM (or a model string such as "openai:gpt-5.5").
llm = BindableFakeChatModel(messages=iter([
    AIMessage(content="", tool_calls=[{
        "name": "search_code",
        "args": {"pattern": "import requests", "directory": "."},
        "id": "call_1",
    }]),
    AIMessage(content="Found files importing requests in the src directory."),
]))

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="""You are a helpful developer assistant with access to tools.

When using tools:
- Think step by step about what information you need
- Use the most appropriate tool for each task
- If a tool returns an error, try to understand and fix the issue
- Summarize your findings clearly for the user""",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Find all Python files that import requests"}]},
    config={"recursion_limit": 10},
)
print(result["messages"][-1].content)
```

Scratchpad pollution happens when tools return verbose payloads that accumulate in agent history. Truncate or summarize tool outputs at the boundary before the next model turn. Your future self debugging a routing failure will thank you for concise intermediate observations.

Human-in-the-loop approvals belong outside the model's direct tool access. Expose a pending_action field in application state and require an authenticated API call to confirm destructive operations. Prompts asking the model to be careful are not a substitute for authorization checks.

**Agent loop retries and limits.** `recursion_limit` on `create_agent` invoke stops infinite loops but does not retry failed tools—add retry logic inside idempotent tools or wrap tool calls with `wrap_tool_call` middleware. Log raw model messages before the next turn so you can distinguish prompt issues from provider schema drift. `create_agent` already compiles a graph; add a `checkpointer` or an explicit LangGraph when you need durable state, human approval, or custom cycles.

## Streaming and Callbacks

Streaming improves perceived latency by emitting partial tokens or events before the full completion finishes. In LCEL, any Runnable that implements `stream` can participate in a streaming chain; events bubble from inner components outward. For chat UIs, stream model tokens; for agent dashboards, stream tool-start and tool-end events so operators see progress while long-running tools execute.

Callbacks are the observability hook surface. BaseCallbackHandler implementations receive events—chain start, LLM start, tool end, errors—and forward them to logs, metrics, or tracing products. Even without a commercial tracer, a lightweight callback that prints tool names and latencies pays for itself the first time you debug a mis-selected tool in production.

Combine streaming with callbacks carefully: streaming handlers may fire hundreds of times per request, so aggregate before writing to expensive sinks. For agents, log the structured tool call and summarized result, not every token of the scratchpad, unless you are actively diagnosing a single failure.

The handler below demonstrates debug-friendly logging using only langchain_core. Pair it with `chain.stream()` or `agent.stream({"messages": [...]})` to watch events arrive incrementally during development.

```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
import time

class DebugCallback(BaseCallbackHandler):
    def on_chain_start(self, serialized, inputs, **kwargs):
        print(f"[chain start] keys={list(inputs.keys())}")

    def on_tool_end(self, output, **kwargs):
        preview = str(output)[:120]
        print(f"[tool end] {preview}")

    def on_llm_end(self, response, **kwargs):
        print("[llm end] completion received")

fake = GenericFakeChatModel(messages=iter([AIMessage(content="streamed chunk")]))

def slow_tool(x: str) -> str:
    time.sleep(0.1)
    return x.upper()

chain = RunnableLambda(slow_tool) | fake

for chunk in chain.stream("hello", config={"callbacks": [DebugCallback()]}):
    print("chunk:", chunk)
```

Structured logging beats println debugging at scale. Serialize callback events as JSON lines with trace identifiers, latency, and token estimates. Correlate those logs with user session identifiers to reconstruct failure timelines without replaying full prompts in production.

Back-pressure matters when consumers process streams slower than models emit tokens. Use async iterators and bounded queues in your API layer so slow clients do not force the model side to buffer unbounded text.

**Streaming and observability pitfalls.** `stream()` on `create_agent` graphs emits heterogeneous event types—distinguish `on_chat_model_stream` token chunks from `on_tool_start` status in your UI so users know the agent is waiting on external systems. Callback handlers attached via config propagate to child runnables; forgetting to pass `config={"callbacks": [...]}` on nested `.invoke()` calls creates blind spots in traces. High-cardinality tags (per-user IDs in callback metadata) can explode tracing backend costs—aggregate at session level in production.

## Production Patterns

Production patterns start with failure as the default case. Tools time out, APIs rate-limit, and models emit invalid JSON. Use handle_tool_error, try/except inside tools, and graceful degradation paths that return actionable error strings the model can read on the next turn. Crashes should be reserved for programmer errors, not for expected external dependency failures.

Security for tool-calling systems applies the principle of least privilege at the tool boundary, not in the prompt. Parameterize SQL, whitelist shell prefixes, require confirmation flags for destructive operations, and validate inputs with Pydantic before any side effect. Diagnose vulnerabilities by threat-modeling each tool as if the model were adversarial—because prompt injection can make it behave that way.

Cost control is part of architecture: cache idempotent reads, cap tool result size, limit parallel tool fan-out, and measure tokens per successful task—not per attempt. Multi-step agents trade extra model round-trips for targeted context; single-pass RAG trades one large prompt for simplicity. Choose based on workload shape, not framework defaults.

Hypothetical scenario: A market-data agent without caching answers every follow-up with fresh API calls, inflating bills during a single curious user session. Hypothetical scenario: A legal-research agent follows related-case links recursively until it hits provider limits. Fixes—TTL caches, call budgets, truncated tool payloads—are boring engineering that keeps agent demos from becoming production incidents.

When debugging agents, stream events and inspect `result["messages"]` to see tool inputs and `ToolMessage` outputs in order. Dump compiled tool schemas to verify docstrings became descriptions. Compare synchronous versus parallel tool execution when latency matters: independent reads should run concurrently when your runtime and provider support parallel tool calls.

```python
from langchain_core.tools import tool, ToolException

@tool(handle_tool_error=True)
def risky_operation(param: str) -> str:
    """A tool that might fail.

    The handle_tool_error=True means failures are caught
    and returned as messages instead of crashing.
    """
    if not param:
        raise ToolException("Parameter cannot be empty!")
    return f"Success with {param}"

def handle_tool_error(error: ToolException) -> str:
    """Convert tool errors into helpful messages."""
    return f"""Tool Error: {str(error)}

Suggestions:
- Check if all required parameters are provided
- Verify the input format is correct
- Try a simpler query first"""

@tool(handle_tool_error=handle_tool_error)
def another_risky_tool(x: int) -> str:
    """Tool with custom error handling."""
    if x < 0:
        raise ToolException("Negative numbers not allowed")
    return str(x * 2)
```

```python
from pydantic import BaseModel, Field, field_validator
import subprocess

class SafeCommandInput(BaseModel):
    """Validated input for shell commands."""
    command: str = Field(description="Command to run")

    @field_validator("command")
    @classmethod
    def validate_command(cls, v):
        allowed_prefixes = ["git ", "npm ", "pytest ", "python -m"]
        if not any(v.startswith(p) for p in allowed_prefixes):
            raise ValueError(f"Command not allowed: {v}")
        dangerous = ["rm -rf", "sudo", "> /dev", "curl | sh"]
        if any(d in v for d in dangerous):
            raise ValueError(f"Dangerous command blocked: {v}")
        return v

@tool(args_schema=SafeCommandInput)
def safe_shell_command(command: str) -> str:
    """Run a safe, whitelisted shell command."""
    return subprocess.run(command, shell=True, capture_output=True, text=True).stdout
```

```python
from langchain_core.tools import tool
import asyncio

@tool
async def get_weather_async(location: str) -> str:
    """Get weather (async version)."""
    await asyncio.sleep(1)
    return f"Weather in {location}: Sunny, 72F"

@tool
async def get_time_async(timezone: str) -> str:
    """Get current time in timezone (async version)."""
    await asyncio.sleep(1)
    from datetime import datetime
    return f"Time in {timezone}: {datetime.now().strftime('%H:%M')}"

@tool
async def get_news_async(topic: str) -> str:
    """Get latest news on topic (async version)."""
    await asyncio.sleep(1)
    return f"Latest news on {topic}: [Headlines would go here]"
```

```python
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

# Reuse the fake model + tools from the agent-loop example above.
agent = create_agent(model=llm, tools=tools, system_prompt="You are a concise developer assistant.")

result = agent.invoke(
    {"messages": [{"role": "user", "content": "test query"}]},
    config={"recursion_limit": 10},
)

for msg in result["messages"]:
    if isinstance(msg, AIMessage) and msg.tool_calls:
        for call in msg.tool_calls:
            print(f"Tool: {call['name']}")
            print(f"Input: {call['args']}")
    if isinstance(msg, ToolMessage):
        print(f"Output: {msg.content}")
        print("---")

for tool in tools:
    print(f"Name: {tool.name}")
    print(f"Description: {tool.description}")
    print(f"Schema: {tool.args_schema.model_json_schema()}")
    print("---")
```

Rate limiting at the tool layer protects downstream SaaS APIs from agent bursts. Combine token buckets per user with global circuit breakers when a provider returns repeated 429 responses. Agents should surface degraded-mode answers instead of retry-storming a failing dependency.

Prompt injection via tool results is an integration security topic. Wrap untrusted tool output in clear delimiters and instruct the model to treat delimited content as data, not instructions. See OWASP guidance on prompt injection when designing retrieval and browser tools.

## Advanced Gotchas and Cross-Cutting Concerns

Production LangChain systems fail at integration boundaries more often than at model quality. The patterns below span multiple sections and deserve explicit treatment because they do not fit neatly into a single Runnable or tool.

**Error propagation in composed graphs.** When a RunnableParallel branch raises an exception, the entire parallel invoke fails unless you wrap optional branches in RunnableLambda try/except blocks or use newer `exceptions="return"` merge semantics where your langchain-core version supports them. Mark branches as critical vs. best-effort in design docs so on-call engineers know whether partial dictionaries are acceptable. Chain-level `with_fallbacks` on the outer runnable catches model timeouts but not arbitrary Python exceptions inside custom tools—those need `handle_tool_error` or explicit catches at the tool boundary.

**Retry policy belongs per tool category.** Chat models retry rate-limited API calls automatically when configured; Python tools do not. Use libraries like `tenacity` inside idempotent read tools, never inside payment or email-sending tools without idempotency keys. Document retry safety in each tool description so orchestrators and future maintainers inherit the contract. `create_agent` `recursion_limit` is not a retry mechanism—it caps graph steps, not transient HTTP failures.

**Observability without cardinality explosions.** Pass consistent `config={"tags": ["billing-agent"], "metadata": {"route": "v2"}}` on every invoke, batch, and stream call so distributed traces remain readable. Deep graphs with many RunnableLambda steps can emit hundreds of callback events per request; aggregate token counts at chain boundaries and sample full verbose traces behind feature flags. LangSmith and OpenTelemetry exporters hook the same BaseCallbackHandler interface—choose one primary sink to avoid duplicate billing on high-volume streams.

**Testing fakes across multi-turn flows.** GenericFakeChatModel queues one AIMessage per `invoke`; agent tests that expect three tool rounds need three queued messages or a factory that rebuilds `iter([...])` before each test case. `create_agent` also calls `bind_tools`—subclass the fake and return `self` (as in the agent-loop example) or the model node raises `NotImplementedError`. Tool-calling fakes must include well-formed `tool_calls` dicts with `name`, `args`, and `id` keys—malformed shapes produce parsing errors indistinguishable from production provider drift in verbose logs.

**StructuredTool and Pydantic v2.** LangChain 0.2+ expects Pydantic v2 models for `args_schema`; use `field_validator` with `@classmethod`, not v1 `@validator`, and introspect schemas with `model_json_schema()` instead of `.schema()`. Validation runs before any side effect—keep validators fast and free of network I/O. Optional fields need explicit `Field(default=...)` or `Optional` typing; models sometimes omit keys entirely, and missing vs. null behaves differently across providers.

**Cost guards that survive prompt changes.** Track tokens per successful task (answer delivered, ticket resolved), not per attempt—agents that retry failed tools inflate per-attempt metrics without reflecting user value. Session-level tool-call budgets complement per-invoke `recursion_limit` when users open multiple tabs or replay conversations. Alert on category spikes (market-data tools, browser automation) separately from aggregate LLM spend so finance and engineering see the same regression at different granularities.

### Operational notes

Runnable configuration travels through `.invoke()`, `.batch()`, and `.stream()` via the config dict. Pass tags, metadata, callbacks, and run names there instead of hard-coding observability inside each step. Consistent run naming makes distributed traces readable when multiple chains serve the same HTTP route.

LangChain fundamentals covered installation and first chains; this module assumes you can read a Runnable graph. When imports move between packages, the graph shape—prompt, model, parser, tool—should remain stable. Pin integration tests to behavior, not to deprecated class names noted in the snapshot callout.

Agents that call retrieval tools should log which sources were used for compliance review. Store citation metadata alongside user messages in your application database, not only in ephemeral scratchpads. Auditors care about provenance more than eloquence when answers influence billing or safety decisions.

Parallel tool calls reduce wall-clock time but increase burst load on downstream APIs. Coordinate concurrency limits across tools sharing the same vendor quota. Otherwise parallel execution becomes a faster way to exhaust rate limits.

Structured output parsers pair naturally with LCEL when tools are unavailable. Use them when you need JSON fields for UI rendering but not external side effects. Mixing parsers and tools in one chain is valid: parse plan steps, then execute approved tools sequentially.

Callback handlers can redact secrets before logs persist. Implement on_llm_start and on_tool_end hooks that strip API keys or PII patterns from serialized inputs. Redaction belongs in observability plumbing, not in hopeful system prompts.

Memory summarization should preserve open questions explicitly. If the user asked for a follow-up on invoice March, the summary must retain that identifier. Generic summaries that drop entities cause agents to re-ask already answered clarifications.

Tool routing classifiers can be small models or embedding similarity over description vectors. Either approach beats dumping every schema into one prompt when catalogs exceed a dozen entries. Measure routing precision in staging before enabling automatic subset selection in production.

Streaming partial JSON from models is fragile compared with native tool-call messages. Prefer provider tool-call APIs when available; fall back to text parsers only for legacy models. LangChain's `create_agent` harness assumes structured `tool_call` objects.

Production deployments should version tool schemas alongside API deployments. Breaking parameter renames without versioning confuse models mid-conversation. Expose schema version identifiers in tool descriptions during migration windows.

Graceful degradation returns partial answers when non-critical tools fail. If news retrieval fails but weather succeeds, answer with weather and disclose the news outage. Users prefer honest partial results over hallucinated completeness.

Integrate retrieval confidence scores into tool results when your vector store provides them. Low-confidence hits should trigger clarification questions instead of authoritative statements. Confidence metadata is cheap to append and saves reputation on edge-case queries.

Debug sessions should capture full `result["messages"]` transcripts only for opted-in users or internal staff. Full tool payloads may contain sensitive output. Gate verbose traces behind feature flags and retention policies aligned with privacy review.

Apply circuit breakers on tools that call legacy mainframes or batch systems. One slow tool should not block the entire agent thread pool. Return timeout messages the model can quote while your status page explains the outage.

Compose test fixtures that snapshot expected Runnable outputs per stage. When upgrading langchain-core, diff stage outputs before running end-to-end agent evaluations. Stage-level regressions are easier to fix than mysterious end-user answer drift.

Design tool descriptions for multilingual users when your product serves global markets. Include English canonical names but describe intents using phrases non-English prompts might use. Routing quality improves when descriptions mention common synonyms and abbreviations.

Memory encryption and retrieval ACLs belong in platform engineering checklists. Agents amplify any data leak because they combine memory, retrieval, and tools in one transcript. Treat agent sessions as sensitive composite records, not ephemeral chat logs.

Streaming UX should distinguish model tokens from tool status messages. Show tool-start indicators separately so users know the agent is waiting on external systems. Perceived reliability improves when the interface explains pauses instead of freezing silently.

Apply budget alerts on token usage per tool category. Finance teams notice category spikes faster than aggregate LLM bills alone. Tag callbacks with tool names to feed those dashboards automatically.

Integrate explicit LangGraph (or pass a `checkpointer` to `create_agent`) when the default agent loop needs checkpointing after human approval. LangChain tools and retrievers still plug into LangGraph nodes. This module's ReAct loop maps directly to graph nodes and conditional edges.

Compose retriever and formatter steps as separate runnables so you can unit test formatting without vector infrastructure. Mock retriever outputs as lists of Document objects with metadata. When formatting changes, tests fail fast instead of silently altering agent answers in production.

Design idempotent tools whenever possible so retries after timeouts do not double-charge or duplicate records. Document which tools are safe to retry in the tool description itself. Agents and orchestrators use that hint when deciding whether to re-invoke after transient failures.

Debug malformed tool JSON by logging the raw model message before parsing. Often the fix is a clearer parameter description or a smaller tool set rather than a new prompt essay. Keep a corpus of failed parses from staging to regression-test parser upgrades.

Apply request-level budgets that cap total tool calls across an entire user session. Per-invoke `recursion_limit` is necessary but not sufficient when users open multiple tabs. Session stores should track cumulative tool usage and refuse new calls when budgets exhaust.

Integrate feature flags to disable risky tools instantly without redeploying model weights. Operations teams need a kill switch when a vendor API behaves unexpectedly during an incident. Tool registries loaded at startup make flag-gated subsets straightforward to implement.

Streaming token events to mobile clients may require coalescing chunks to reduce UI flicker. Batch tokens every fifty milliseconds unless the product demands character-by-character rendering. Measure battery and data impact on mobile when enabling full token streaming.

Memory backends range from in-process dicts to Redis, Postgres, and dedicated session services. Pick storage based on retention policy, encryption requirements, and horizontal scale. Agents replicated across pods need shared memory stores; in-process dicts break with load balancing.

Retrieval tools should tag results with ACL scopes derived from the authenticated user. Never return documents the user could not fetch through normal application APIs. Vector stores must index permission metadata alongside embeddings for filter enforcement.

Compose validation runnables after the model and before tools execute when business rules are deterministic. Let the model propose structured intent, then validate with code before any side effect. This pattern reduces catastrophic tool calls compared with trusting free-form JSON alone.

Design observability dashboards around tool success rate, p95 latency, and tokens per successful task. Leaders ask for ROI narratives; engineers need the same metrics to spot regressions after prompt changes. Export callback events to your metrics stack with consistent label cardinality limits.

Apply red-team exercises that attempt prompt injection through retrieved snippets and tool outputs. Schedule exercises after major tool additions or retrieval index refreshes. Document mitigations in runbooks linked from on-call playbooks.

Debug parallel tool failures by recording which branch failed in RunnableParallel merges. Partial success dictionaries should mark failed keys explicitly instead of omitting them silently. Downstream prompts can acknowledge partial data when one branch times out.

Integrate circuit breaker state into tool descriptions during incidents. When a dependency is degraded, update dynamic descriptions to steer the model away from broken tools. Static schemas cannot express outage mode; application-layer registries can.

Streaming agent UIs should show cancellation controls that abort in-flight tool calls. Users who cancel must not leave orphaned writes in external systems. Use idempotency keys on mutating tools to make cancellation safe.

LCEL batch APIs help offline evaluation: pass hundreds of inputs through the same chain with shared callbacks. Collect latency distributions per stage to find bottlenecks before launch. Batch mode reveals parser edge cases that single manual invokes miss.

Tool schema examples in docstrings should mirror real user phrasing collected from support tickets. Product managers can supply anonymized phrases during tool design reviews. Grounding descriptions in actual language beats inventing synthetic scenarios alone.

Memory eviction policies should consider regulatory retention separately from model context limits. Legal hold may require keeping transcripts models no longer see. Separate compliance archives from active prompt history to satisfy both constraints.

Production agents benefit from golden-path integration tests that mock only external HTTP, not LangChain internals. Use recorded fixtures for vendor APIs and real Runnable graphs for everything else. Tests then catch composition regressions and vendor schema changes independently.

Apply structured audit logs whenever tools mutate customer records. Include actor, tool name, arguments hash, and outcome status. Forensics teams need deterministic traces more than conversational politeness after incidents.

RunnableLambda steps are the escape hatch when you need plain Python between model calls. Keep lambdas small and pure; push heavy IO into tools with explicit schemas instead of hidden side effects. Named functions improve stack traces when callbacks report errors mid-chain.

Cross-linking fundamentals and LangGraph modules helps teams choose the right orchestration layer. Stay on LCEL and `create_agent` until you need custom cycles, durable checkpoints, or human-approval nodes; graduate to an explicit LangGraph when those dominate. Mixing both in one product is normal—shared tools and retrievers reduce duplication.

Token accounting should attribute tool definition overhead separately from conversation history. Large tool catalogs inflate every request even when the model picks one tool. Measure definition tokens when debating meta-tool consolidation versus flat schemas.

Warm-start agent sessions with retrieved policy snippets only when the user's intent classifies as policy-related. Eager retrieval on every message wastes tokens and increases injection surface. Intent classifiers implemented as lightweight LCEL branches keep costs predictable.

Vendor SDK upgrades should run through staging chains that record parity diffs on golden inputs. Behavioral drift often appears in tool-call formatting before user-visible answer quality shifts. Automate those diffs in CI tied to langchain-core version bumps.

Closing the loop: compose runnables, design tool contracts, integrate memory and retrieval, debug with callbacks, and apply production guardrails. These skills transfer even when class names change—verify against the snapshot callout and official docs each release. The framework is volatile; the orchestration discipline is durable.

## Did You Know?

- [OpenAI introduced function calling in June 2023](https://openai.com/index/function-calling-and-other-api-updates/), shifting many applications from pure text generation toward agentic workflows that call external APIs.
- [Anthropic's tool-use announcement](https://www.anthropic.com/news/tool-use-ga) describes how external tools improve accuracy on tasks models cannot complete from weights alone.
- Tool selection accuracy often degrades as overlapping tools accumulate; large catalogs typically need routing layers or hierarchical meta-tools rather than flat schema dumps.
- [ReAct (Reason + Act)](https://arxiv.org/abs/2210.03629) formalized interleaved reasoning and tool use—the same loop LangChain `create_agent` implements with modern native tool-call messages.


## Common Mistakes

| Mistake | Why it hurts | Fix |
|---|---|---|
| Overpowered tools | Models may invoke destructive commands when scopes are too broad. | Apply least privilege; parameterize queries and restrict filesystem or SQL access. |
| Missing error context | Generic failures force the model to guess the next step. | Return actionable error strings; use `handle_tool_error` and try/except inside tools. |
| Tool overload | Dozens of overlapping tools confuse routing. | Consolidate related actions into meta-tools or route to focused subsets first. |
| Ignoring memory growth | Storing full tool payloads in history blows context limits. | Trim or summarize tool results before persisting memory; cap turn count. |
| Synchronous fan-out | Sequential independent reads inflate latency. | Use async tools and parallel tool calls when the provider supports them. |
| Bloated tool responses | Huge JSON objects consume tokens and obscure answers. | Return only fields the model needs; paginate large result sets. |
| Weak descriptions | The model routes primarily on docstrings, not code. | Write specific descriptions with examples, edge cases, and when-not-to-use notes. |
| Skipping observability | Failures look like model bugs when tools misbehave silently. | Add callbacks, verbose traces, and structured logs at Runnable boundaries. |


## Knowledge Check

1. **How do you compose an LCEL pipeline that classifies intent and summarizes a question in parallel before routing?**
   <details>
   <summary>Compose parallel LCEL branches with RunnableParallel before a routing merge step</summary>
   Build two chains (classify and summarize) that share the same input dict, merge with RunnableParallel, then apply a RunnableLambda or RunnableBranch to pick the next chain. Test with GenericFakeChatModel so compose logic is verified without API keys.
   </details>

2. **Your agent selects the wrong tool among fifteen similar database utilities. What design change improves schema clarity?**
   <details>
   <summary>Design distinct tool descriptions and hierarchical meta-tools instead of flat duplicates</summary>
   Rewrite descriptions so each tool states when to use it and when not to. Consolidate related SQL helpers into one meta-tool with an action parameter, or route to a focused subset before invoking the main `create_agent` loop.
   </details>

3. **How should you integrate memory with agents so tool results do not exhaust the context window?**
   <details>
   <summary>Integrate memory policies that trim tool payloads and cap stored turns</summary>
   Load only recent turns into MessagesPlaceholder, summarize older history, and never persist raw megabyte JSON from tools. Save structured facts separately when long-term recall is required.
   </details>

4. **Operators cannot see why an agent stalled during a long tool call. Which debug hooks help?**
   <details>
   <summary>Debug with streaming events, callbacks, and result["messages"] on the agent</summary>
   Attach a BaseCallbackHandler that logs tool start/end timestamps, stream the graph, and inspect `result["messages"]` for tool calls and ToolMessage outputs after the run. Stream partial events to the UI so latency is visible while tools execute.
   </details>

5. **A retrieval tool returns entire PDFs and answers become slow and expensive. What production pattern fixes this?**
   <details>
   <summary>Apply production payload shaping—snippets, citations, and hard size caps on retrieval tool output</summary>
   Return titles, short excerpts, and source metadata instead of full documents. Combine with re-ranking and a synthesis step so the model sees only the minimum grounded context.
   </details>

6. **Users trigger repeated market-data fetches with follow-up questions. Which apply-layer control limits cost?**
   <details>
   <summary>Apply TTL caching, recursion limits, and call budgets at the tool boundary</summary>
   Cache idempotent reads with time-bucket keys, enforce `recursion_limit` on the agent invoke, and track per-session tool call counts. Surface degraded answers when limits are reached instead of silent retry storms.
   </details>


## Hands-On Exercise

Build a small offline agent lab using `langchain_core` fakes—no API keys required. Complete every checkbox before moving to LangGraph in the next module.

- [ ] **Compose** an LCEL chain with RunnableParallel that extracts keywords and counts words from the same input string, then merges both results.
- [ ] **Design** a `@tool` with a Pydantic schema that rejects empty location strings and returns simulated weather JSON.
- [ ] **Integrate** Conversation-style memory by loading the last two turns into a ChatPromptTemplate MessagesPlaceholder before invoking a fake chat model.
- [ ] **Debug** the run with a custom BaseCallbackHandler that prints chain start and LLM end events.
- [ ] **Apply** `handle_tool_error=True` on a tool that raises ToolException when input is invalid.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool, ToolException
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableParallel, RunnableLambda, RunnablePassthrough
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

class Loc(BaseModel):
    location: str = Field(min_length=1, description="City name")

@tool(args_schema=Loc)
def get_weather(location: str) -> str:
    '''Return simulated weather for a city.'''
    return f'{{"city": "{location}", "temp_c": 21, "conditions": "clear"}}'

@tool(handle_tool_error=True)
def strict_echo(text: str) -> str:
    '''Echo text or fail clearly.'''
    if not text.strip():
        raise ToolException("text must be non-empty")
    return text

class Trace(BaseCallbackHandler):
    def on_chain_start(self, serialized, inputs, **kwargs):
        print("[debug] chain start", list(inputs.keys()))

fake = GenericFakeChatModel(messages=iter([
    AIMessage(content="Memory-aware answer."),
]))

history = [HumanMessage(content="Hi"), AIMessage(content="Hello!")]

prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer briefly."),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

analysis = RunnableParallel(
    keywords=RunnableLambda(lambda d: " ".join(w for w in d["text"].split() if len(w) > 4)),
    words=RunnableLambda(lambda d: str(len(d["text"].split()))),
)

composed = (
    RunnablePassthrough.assign(analysis=analysis)
    | prompt
    | fake
)

print(composed.invoke({"text": "compose integrate debug apply", "history": history, "question": "Summarize our chat"}))
print(get_weather.invoke({"location": "Oslo"}))
print(strict_echo.invoke({"text": ""}))
```


## Next Module

Continue to [Module 1.3: LangGraph for Agents](/ai-ml-engineering/frameworks-agents/module-1.3-langgraph-for-agents/) to model durable agent state, cyclic workflows, and human-in-the-loop checkpoints beyond the default `create_agent` loop.


## Sources

- [LangChain LCEL concepts](https://python.langchain.com/docs/concepts/lcel/) — Official overview of Runnable composition, piping, and streaming semantics in LangChain Expression Language.
- [LangChain tools concepts](https://python.langchain.com/docs/concepts/tools/) — How tools expose schemas to models and integrate with agents and chains.
- [LangChain agents (1.x)](https://docs.langchain.com/oss/python/langchain/agents) — Official `create_agent` harness: model, tools, `system_prompt`, middleware, and `{"messages": [...]}` invoke.
- [Migrate to LangChain v1](https://docs.langchain.com/oss/python/migrate/langchain-v1) — `create_agent` vs older factories; legacy runtime and chains in `langchain-classic`.
- [LangChain memory concepts](https://python.langchain.com/docs/concepts/memory/) — Memory types, buffer policies, and how history feeds prompts across turns.
- [LangChain streaming concepts](https://python.langchain.com/docs/concepts/streaming/) — Streaming modes for tokens and events through Runnable pipelines.
- [LangChain callbacks concepts](https://python.langchain.com/docs/concepts/callbacks/) — Callback handler lifecycle hooks for tracing and custom logging.
- [Tool calling how-to](https://python.langchain.com/docs/how_to/tool_calling/) — Practical guide to binding tools to chat models and executing tool calls.
- [Streaming how-to](https://python.langchain.com/docs/how_to/streaming/) — Step-by-step patterns for streaming LCEL chains and chat models.
- [ReAct paper](https://arxiv.org/abs/2210.03629) — Yao et al.; foundational interleaved reasoning and acting pattern underlying modern agents.
- [OpenAI function calling guide](https://platform.openai.com/docs/guides/function-calling) — Provider reference for tool schemas, parallel calls, and structured outputs.
- [Anthropic tool use GA](https://www.anthropic.com/news/tool-use-ga) — Announcement and design notes for Claude tool-use integrations.
- [Google Vertex function calling](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/function-calling) — Google Cloud reference for function-calling request and response shapes.
- [OWASP Prompt Injection](https://owasp.org/www-community/attacks/PromptInjection) — Security reference for direct and indirect prompt injection, including via tool and retrieval content.

