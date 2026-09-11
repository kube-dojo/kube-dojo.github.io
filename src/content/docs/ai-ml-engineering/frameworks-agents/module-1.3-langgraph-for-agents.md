---
title: "LangGraph for Agents"
slug: ai-ml-engineering/frameworks-agents/module-1.3-langgraph-for-agents
sidebar:
  order: 504
---
> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 80-100 minutes
>
> **Prerequisites**: [LangChain Fundamentals](../module-1.1-langchain-fundamentals/) and [LangChain Advanced](../module-1.2-langchain-advanced/), plus ReAct basics from [Reasoning and Logic Prompts](/ai/ai-engineering-foundations/module-1.2-reasoning-and-logic-prompts/).

---

## What You'll Be Able to Do
- **Design** stateful `StateGraph` workflows that separate state, node work, and conditional routing for agent tasks.
- **Implement** cyclic LangGraph control paths for retries, critique loops, and self-correcting agent behaviors.
- **Diagnose** reducer, routing, checkpoint, and recursion-limit failures in complex multi-agent architectures.
- **Evaluate** trade-offs between a plain Python loop, a linear LangChain-style sequence, and graph-based workflow orchestration.

## Why This Module Matters
Agents rarely fail because they cannot call a tool once. They fail because real workflows have state: a request must be classified, routed, retried, reviewed, and sometimes resumed after a human decision or service interruption. LangGraph gives that workflow an explicit graph instead of hiding control flow inside one enormous prompt, one long callback, or one loop whose exit conditions live only in a developer's head.

That difference matters because modern agent work is not just model invocation. A useful agent carries evidence forward, remembers which checks have passed, stores partial decisions, waits for approvals, exposes progress to a user interface, and recovers when a tool or model call fails. If those responsibilities are scattered across ad-hoc variables, background jobs, and prompt text, debugging becomes archaeological work. You inspect logs, reconstruct state by hand, and hope the next run takes the same route.

A document-analysis assistant makes the problem concrete. The first prototype might classify a document, extract fields, review the output, and ask for a correction. That looks easy as a script until a downstream service times out after classification but before review. Without durable graph state, operators may restart the whole session, repeat expensive model calls, and manually decide which intermediate result is still trustworthy. The real cost is not only latency or token spend; it is the loss of operator confidence when the agent cannot explain where it is in the process.

LangGraph should be read as a control-flow runtime for stateful agents, not as a magic intelligence layer. `StateGraph` defines the shared contract, nodes perform work, edges route execution, reducers decide how updates merge, checkpointers make progress durable, and interrupts allow external reviewers to participate without throwing away state. Those pieces are deliberately lower-level than a one-call agent framework because production reliability usually depends on making the control surface visible.

You do not need LangGraph for every LLM feature. If your program calls a model once, formats the answer, and exits, a plain function is clearer. If your workflow is a fixed sequence with no retries, no human approval, and no long-lived state, a linear chain or simple orchestration function may be enough. Reach for LangGraph when the work has durable state, branching decisions, cycles, multi-agent coordination, streaming progress, or a need to resume safely after interruption.

## Section 1: The Graph Mental Model and Linear Limitations
Once you understand Chain-of-Thought and ReAct patterns, the next production problem is orchestration. ReAct gives a model a loop of reasoning and action, but an application still needs to decide where that loop lives, what counts as state, when a retry is allowed, and who can stop a risky action. LangGraph answers by turning the workflow itself into a graph that can be inspected, tested, resumed, and evolved.

Think of standard linear chains like a highway with no exits. Once you start, you can only go forward. If you miss something, you have to drive to the end and start over from the beginning.

```mermaid
graph TD
    Input --> Chain1
    Chain1 --> Chain2
    Chain2 --> Chain3
    Chain3 --> Output
    Chain3 -.-> ConditionBranch
    ConditionBranch --> PathA[Path A]
    ConditionBranch --> PathB[Path B]
```

The first diagram shows why linear composition feels good during a demo and becomes brittle in production. Every step assumes the previous step succeeded well enough to keep going, so exception handling grows beside the actual workflow. You add flags, retry counters, manual checkpoints, and callback branches around the chain, until the "linear" program is no longer linear at all. At that point, the chain is only hiding a graph you have not named.

Real-world workflows, however, look more like a city street grid. You can loop back, take detours, or recover from wrong turns without restarting your journey. LangGraph allows you to construct these cyclic execution paths naturally, which matters for critique loops, tool retries, clarification flows, and multi-agent delegation where the next step depends on accumulated evidence.

```mermaid
graph TD
    Research --> Analyze
    Analyze --> Check
    Check -- not good enough --> Research
    Check --> Write
    Write --> Review
    Review -- revisions needed --> Write
    Review --> Publish
```

The second diagram is not only prettier; it changes the failure model. If review fails, the workflow returns to writing with the previous draft and review feedback still available. If research produced weak evidence, the graph can send the state back to research without discarding the analysis already performed. That is the practical meaning of stateful orchestration: the agent has a controlled path for correction instead of a vague instruction to "try again."

> **Pause and predict**: If a complex AI agent pipeline is purely linear, what architectural workarounds would you need to implement to allow an agent to correct a hallucinated answer after reviewing it?

### Why Graphs for AI Workflows?
At its core, a graph consists of nodes and edges connecting them. In LangGraph, that simple vocabulary becomes the control surface for agent design: nodes own work, edges own decisions, and the state object carries evidence between each step. This is a useful discipline because it keeps model reasoning, application policy, and orchestration rules from collapsing into a single prompt.

```mermaid
graph LR
    A[Node A] --edge--> B[Node B]
    B --edge--> C[Node C]
    B --edge--> D[Node D]
```

| Feature | Linear Chains | Graph Workflows |
|---------|---------------|-----------------|
| Conditional logic | Limited | Full branching |
| Cycles/loops | Not possible | Native support |
| State management | Pass through | Persistent state |
| Error recovery | Start over | Retry specific nodes |
| Human-in-the-loop | Awkward | Native support |
| Multi-agent | Sequential only | Fan-out parallelism for independent branches (supervisor routing is otherwise sequential) |

The table should not be read as "graphs are always better." A graph has its own overhead: you must name state fields, define merge behavior, test routes, and understand how checkpoints interact with deployed graph changes. That overhead is worthwhile when the workflow is long-running, auditable, or expensive to repeat. It is not worthwhile when a ten-line Python function expresses the whole policy more clearly.

Use a plain loop when the state is small, local, and disposable. Use a linear framework when each step is deterministic enough that failure means the whole request should fail. Use LangGraph when the path is part of the product: a user or operator needs to see why a decision happened, a workflow might wait for a person, or a later node must recover from an earlier partial success without pretending the run is brand new.

## Section 2: LangGraph Core Concepts
LangGraph revolves around a few central primitives: the `StateGraph`, nodes, edges, reducers, checkpointers, and interrupts. Learn these names before writing complex agents because most bugs come from confusing where data lives, who updates it, and how a route is selected. A graph is not just a different syntax for a chain; it is a set of contracts that define how work advances safely.

| Concept | Purpose |
|---------|---------|
| StateGraph | Container for workflow definition |
| Nodes | Processing functions that update state |
| Edges | Define flow between nodes |
| Reducers | How state updates are merged |
| Checkpointer | Enables pause/resume and persistence |
| Interrupts | Human-in-the-loop integration |

The most important habit is to separate three questions. What is the durable state of the workflow? Which function is allowed to change which part of that state? Which route should run next after the update? If those questions are mixed together, a graph can become as hard to debug as the tangled loop it was meant to replace. If they stay separate, each node and route becomes small enough to test with ordinary inputs.

State also has two different meanings that beginners often blur. The graph state is the structured application record passed between nodes, such as messages, extracted fields, approval flags, and retry counters. The model context is the prompt and message payload sent to an LLM inside a node. A node may derive model context from graph state, but the graph should not blindly store every token forever, because checkpoint size and context quality both degrade when state becomes a dumping ground.

### 1. StateGraph
The foundation is the `StateGraph`, which manages the state schema, nodes, and transition logic. Treat it as the workflow contract rather than a convenience wrapper, because every node and edge must agree on the same state shape. The graph builder is where you state, in code, what the workflow is allowed to remember and how every named step fits into the topology.

The following small state definition is intentionally minimal. It shows the three kinds of fields you will see repeatedly: accumulated history, current phase, and final result. The `messages` field accumulates because later nodes need the whole trace, while `current_step` and `result` are ordinary replacement fields because there should be only one current step and one latest result.

```python
from langgraph.graph import StateGraph, END

# Define the state type
from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]  # Accumulates
    current_step: str
    result: str

# Create the graph
graph = StateGraph(AgentState)
```

### 2. State Annotations
State updates require precise instructions on how new data should merge with existing data. A list of messages should usually accumulate, while a current phase should replace its previous value, and LangGraph needs that distinction spelled out. Reducers are therefore not decoration; they are the rules that keep parallel or repeated updates from silently erasing information.

This snippet is a compact version of a production design decision. `current_value` should be replaced because it represents the latest view. `history` should accumulate because every node contributes evidence. `counter` uses a custom reducer because increments from different nodes must combine into one total. When a workflow behaves strangely, checking these reducers is often faster than staring at prompts.

```python
from typing import Annotated
import operator

class MyState(TypedDict):
    # This field gets REPLACED on each update
    current_value: str

    # This field ACCUMULATES (list concatenation)
    history: Annotated[List[str], operator.add]

    # This field uses custom reducer
    counter: Annotated[int, lambda a, b: a + b]
```

> **Stop and think**: Why is `operator.add` crucial for tracking an LLM's conversation history? What happens to the AI's context window if a field lacks this annotation, and how would that failure appear when an agent tries to recover from a bad intermediate answer?

Reducers are also where graph design intersects with cognitive load. If every field accumulates forever, the state grows and every checkpoint becomes heavier. If every field replaces, the agent loses memory of previous attempts. Good state design usually separates durable audit history from compact working summaries, then lets nodes rebuild prompt context from the right subset instead of handing the whole state to the model.

### 3. Nodes and Edges
Nodes receive the current state, perform logic, and return a partial state update. Edges define the conditional or unconditional routes between these nodes, so the graph can express decisions without burying them inside a long prompt or a tangled callback. A good node is boring in the best way: it reads the state, does one job, returns a patch, and lets the graph decide the next hop.

The `analyze_node` example below returns only the fields it wants to update. It does not mutate the incoming dictionary in place, and it does not decide which node runs next. That keeps the function easy to unit test. You can pass a small `AgentState` fixture into the node, assert the returned patch, and test routing separately.

```python
def analyze_node(state: AgentState) -> dict:
    """Analyze the input and return findings."""
    messages = state["messages"]
    # Do analysis...
    return {
        "current_step": "analyze",
        "messages": ["Analysis complete: found 3 issues"]
    }

# Add node to graph
graph.add_node("analyze", analyze_node)
```

Edges are where the graph becomes a workflow instead of a bag of functions. An unconditional edge is a statement that one step always follows another. A conditional edge is a routing rule, usually implemented as a small pure function that reads state and returns a route key. The important part is that route keys are explicit, finite, and testable.

```python
# Unconditional edge: always go from A to B
graph.add_edge("node_a", "node_b")

# Conditional edge: choose based on state
def should_continue(state: AgentState) -> str:
    if state["result"] == "success":
        return "finish"
    else:
        return "retry"

graph.add_conditional_edges(
    "check",
    should_continue,
    {
        "finish": "output",
        "retry": "process"  # Creates a cycle!
    }
)
```

The conditional example creates a cycle by routing `"retry"` back to `"process"`. That cycle is the feature LangGraph was built to express, but it also creates responsibility. The state must include enough information to decide when retry is still useful, and the route map must account for unexpected states. Without that discipline, a graph can burn tokens in a loop just as easily as a hand-written while loop.

### 4. Compilation
Every graph requires explicit entry and exit points before it can be compiled into an executable application. Compilation is the moment LangGraph validates the topology and turns your declarative workflow into something you can invoke, stream, checkpoint, or interrupt. It is also where runtime capabilities such as checkpointers and interrupt boundaries are attached.

The `START` and `END` sentinels make the lifecycle visible. They help you reason about whether every branch can terminate and whether any node is orphaned. In a review, you should be able to trace the graph from `START` to `END` and explain every cycle that can delay termination.

```python
from langgraph.graph import START, END

# Set entry point
graph.add_edge(START, "first_node")

# Set exit point (END is a special node)
graph.add_edge("final_node", END)
```

Once compiled, the graph behaves like an application object. That object can be invoked once, streamed step by step, or configured with a `thread_id` for persistence. Notice that the input must satisfy the state schema well enough for the first node to run, which is why default values and clear state initialization matter.

```python
# Compile the graph
app = graph.compile()

# Run it
result = app.invoke({"messages": ["Hello"], "current_step": "start"})
```

## Section 3: Building Your First LangGraph Workflow
Let's build a practical document processing pipeline. The graph structure will dynamically route documents based on classification, which makes the example small enough to read while still showing the production pattern: parse once, classify once, and then send work to the correct specialist node. This pattern appears in invoice processing, policy review, support triage, legal intake, and any agent that must choose a specialized path after inspecting an input.

```mermaid
graph LR
    Parse --> Classify --> Route
    Route --> ProcessA[Process A] --> Output1[Output]
    Route --> ProcessB[Process B] --> Output2[Output]
```

The diagram has one decision point and three possible processors. That is deliberate. A first LangGraph workflow should not begin with ten agents and nested subgraphs. It should begin with a clear state object, a few named nodes, and one route that proves the graph can choose different execution paths while preserving a shared record of what happened.

### Step 1: Define State
The state definition is the contract for the whole workflow. `document` is the raw input, `doc_type` records the classification, `extracted_data` accumulates structured observations, `messages` accumulates audit notes, and `output` stores the final user-facing result. This is already more disciplined than passing arbitrary dictionaries through a chain because each field has a purpose.

```python
from typing import TypedDict, List, Annotated, Literal
import operator

class DocumentState(TypedDict):
    # The input document
    document: str

    # Classification result
    doc_type: Literal["invoice", "contract", "letter", "unknown"]

    # Extracted data (accumulates across nodes)
    extracted_data: Annotated[List[dict], operator.add]

    # Processing messages
    messages: Annotated[List[str], operator.add]

    # Final output
    output: str
```

### Step 2: Define Nodes
Each node below is intentionally small. `parse_node` records a basic parse event, `classify_node` decides the document type, the processor nodes extract type-specific data, and `output_node` creates the final response. In a production system, the parsing node might call OCR, the classifier might call an LLM with structured output, and the processors might call different extraction tools, but the graph shape would remain the same.

Notice that no node appends directly to a shared global log. Each node returns a partial state update, and the reducer on `messages` decides how to merge those updates. This is the difference between a workflow log that is part of the graph state and a side-effect log that can only be reconstructed from whatever your observability system happened to capture.

```python
def parse_node(state: DocumentState) -> dict:
    """Parse the raw document."""
    doc = state["document"]
    # Simulate parsing
    return {
        "messages": [f"Parsed document: {len(doc)} characters"]
    }

def classify_node(state: DocumentState) -> dict:
    """Classify the document type."""
    doc = state["document"].lower()

    if "invoice" in doc or "amount due" in doc:
        doc_type = "invoice"
    elif "agreement" in doc or "contract" in doc:
        doc_type = "contract"
    elif "dear" in doc or "sincerely" in doc:
        doc_type = "letter"
    else:
        doc_type = "unknown"

    return {
        "doc_type": doc_type,
        "messages": [f"Classified as: {doc_type}"]
    }

def process_invoice(state: DocumentState) -> dict:
    """Extract invoice-specific data."""
    return {
        "extracted_data": [{"type": "invoice", "amount": "$1,234.56"}],
        "messages": ["Extracted invoice data"]
    }

def process_contract(state: DocumentState) -> dict:
    """Extract contract-specific data."""
    return {
        "extracted_data": [{"type": "contract", "parties": ["A", "B"]}],
        "messages": ["Extracted contract data"]
    }

def process_generic(state: DocumentState) -> dict:
    """Generic processing for other documents."""
    return {
        "extracted_data": [{"type": "generic", "summary": "Document processed"}],
        "messages": ["Generic processing complete"]
    }

def output_node(state: DocumentState) -> dict:
    """Generate final output."""
    data = state["extracted_data"]
    return {
        "output": f"Processed {len(data)} items: {data}",
        "messages": ["Output generated"]
    }
```

### Step 3: Define Routing Logic
The routing function is the policy boundary. It reads `doc_type` and returns the name of the next node. Keeping that mapping in one small function makes edge cases visible: invoices route to invoice processing, contracts route to contract processing, and letters or unknown documents fall back to generic processing. The fallback is important because production classifiers eventually see inputs outside the happy path.

```python
def route_by_type(state: DocumentState) -> str:
    """Route to appropriate processor based on document type."""
    doc_type = state["doc_type"]

    routing = {
        "invoice": "process_invoice",
        "contract": "process_contract",
        "letter": "process_generic",
        "unknown": "process_generic"
    }

    return routing.get(doc_type, "process_generic")
```

### Step 4 & 5: Build and Run the Graph
Graph construction wires the contract, node functions, and routing policy together. The workflow starts at parse, moves to classify, chooses exactly one processor, and then converges on the output node. That fan-in is valuable because downstream code does not need to know which specialized processor ran; it only needs the normalized `extracted_data` and `messages` fields.

This is also where you should read the graph like a reviewer. Every node has a path from `START`; every processor has a path to `output`; and `output` has a path to `END`. The route map includes every route key the routing function can return. If any of those checks fail, the bug is in the graph definition rather than in the model.

```python
from langgraph.graph import StateGraph, START, END

# Create graph
workflow = StateGraph(DocumentState)

# Add nodes
workflow.add_node("parse", parse_node)
workflow.add_node("classify", classify_node)
workflow.add_node("process_invoice", process_invoice)
workflow.add_node("process_contract", process_contract)
workflow.add_node("process_generic", process_generic)
workflow.add_node("output", output_node)

# Add edges
workflow.add_edge(START, "parse")
workflow.add_edge("parse", "classify")

# Conditional routing after classification
workflow.add_conditional_edges(
    "classify",
    route_by_type,
    {
        "process_invoice": "process_invoice",
        "process_contract": "process_contract",
        "process_generic": "process_generic"
    }
)

# All processors lead to output
workflow.add_edge("process_invoice", "output")
workflow.add_edge("process_contract", "output")
workflow.add_edge("process_generic", "output")

# Output leads to END
workflow.add_edge("output", END)

# Compile
app = workflow.compile()
```

The invocation demonstrates the payoff. You pass one initial state to the compiled app and receive a final state containing the classification, accumulated messages, extracted data, and output. For a classroom example the classifier is a string check, but the architecture is the same when classification is an LLM call or a deterministic rules engine.

```python
# Test with an invoice
result = app.invoke({
    "document": "INVOICE #123\nAmount Due: $1,234.56\nDue Date: 2024-01-15",
    "extracted_data": [],
    "messages": []
})

print("Document type:", result["doc_type"])
print("Messages:", result["messages"])
print("Output:", result["output"])
```

When should you reach for this pattern? Use it when one input should take one of several specialized routes and all routes must return to a common shape. Do not use it for a pure batch job where every input always goes through every step; a simple pipeline is clearer there. The graph becomes useful when classification, fallback, and auditability are real product requirements rather than tutorial decoration.

## Section 4: Cycles and Error Handling
Cycles are the beating heart of robust AI workflows. A self-correcting writer agent should not restart from the beginning whenever a review fails; it should carry the draft, feedback, revision count, and approval status back through a controlled loop. Cycles turn "try again" from an instruction hidden in a prompt into a route that is visible in code.

```mermaid
graph LR
    Draft --> Review
    Review --> Good{Good?}
    Good -- Yes --> Publish
    Good -- No --> Draft
```

The review loop above is the smallest useful example of agent correction. The draft node creates or revises a response, the review node decides whether the current output is acceptable, and the conditional edge either publishes or returns to drafting. That design is easy to explain to a stakeholder because the loop has a purpose, a state variable, and an exit condition.

The code below does not call a real model because the orchestration lesson is more important than provider setup. In a real writer agent, the draft node would call a model with the topic and feedback, while the review node might call another model, a rubric evaluator, or a deterministic policy check. The graph does not care which implementation you choose as long as each node returns a valid patch.

```python
from typing import TypedDict, List, Annotated
import operator

class WriterState(TypedDict):
    topic: str
    draft: str
    feedback: str
    revision_count: int
    is_approved: bool
    messages: Annotated[List[str], operator.add]

def draft_node(state: WriterState) -> dict:
    """Create or revise the draft."""
    topic = state["topic"]
    feedback = state.get("feedback", "")
    count = state.get("revision_count", 0)

    if count == 0:
        # Initial draft
        draft = f"# {topic}\n\nThis is the initial draft about {topic}."
        msg = "Created initial draft"
    else:
        # Revision based on feedback
        draft = f"# {topic}\n\nRevised draft (v{count+1}): Addressed feedback: {feedback}"
        msg = f"Revised draft (attempt {count + 1})"

    return {
        "draft": draft,
        "revision_count": count + 1,
        "messages": [msg]
    }

def review_node(state: WriterState) -> dict:
    """Review the draft and provide feedback."""
    draft = state["draft"]
    count = state["revision_count"]

    # Simulate review (in real app, this would use an LLM)
    if count >= 3:  # Accept after 3 attempts
        return {
            "is_approved": True,
            "feedback": "Looks good!",
            "messages": ["Review passed!"]
        }
    else:
        return {
            "is_approved": False,
            "feedback": f"Need more detail in section {count}",
            "messages": [f"Review failed: needs revision"]
        }

def publish_node(state: WriterState) -> dict:
    """Publish the approved draft."""
    return {
        "messages": [f"Published after {state['revision_count']} revisions!"]
    }

def should_continue(state: WriterState) -> str:
    """Decide whether to revise or publish."""
    if state["is_approved"]:
        return "publish"
    else:
        return "revise"

# Build the graph
writer = StateGraph(WriterState)

writer.add_node("draft", draft_node)
writer.add_node("review", review_node)
writer.add_node("publish", publish_node)

writer.add_edge(START, "draft")
writer.add_edge("draft", "review")

writer.add_conditional_edges(
    "review",
    should_continue,
    {
        "revise": "draft",   # CYCLE: go back to draft
        "publish": "publish"
    }
)

writer.add_edge("publish", END)

app = writer.compile()

# Run it
result = app.invoke({
    "topic": "LangGraph Cycles",
    "revision_count": 0,
    "is_approved": False,
    "messages": []
})

print("Final messages:", result["messages"])
# Output shows the progression through multiple revisions
```

The state fields explain the design. `topic` is stable input, `draft` is the current artifact, `feedback` carries reviewer guidance, `revision_count` is the safety counter, `is_approved` is the route signal, and `messages` records the trace. If the loop behaves badly, you can inspect those fields and ask whether the reviewer is too strict, whether feedback is being applied, or whether the route is ignoring approval.

### Safety First: Preventing Infinite Loops
When implementing cycles, missing safety checks will stall your application entirely. Defensively wrap conditions with retry limits so the graph can fail closed, produce a partial result, or route to human review instead of consuming tokens forever. A recursion limit protects the runtime, but a domain-specific counter protects the product because it lets you choose the right fallback.

```python
def should_continue_safe(state: WriterState) -> str:
    """Continue with a maximum retry limit."""
    MAX_RETRIES = 5

    if state["is_approved"]:
        return "publish"
    elif state["revision_count"] >= MAX_RETRIES:
        return "publish"  # Publish anyway after max retries
    else:
        return "revise"
```

The example returns `"publish"` after the maximum retry count because the tutorial keeps the route map small. In a production system, a better route might be `"human_review"`, `"partial_publish"`, or `"failed_with_context"`. The key is that the graph should leave the loop for a named reason, not because an exception broke the process after the model already consumed more context than expected.

You should also isolate error-prone operations at the node level to ensure localized recovery. If an external API fails inside one node, the graph should route from that node's error state rather than losing every previous observation. A node-level error field is often more useful than raising immediately, because the graph can decide whether to retry, ask a person, or continue with degraded output.

```python
def safe_node(state: MyState) -> dict:
    """Node with built-in error handling."""
    try:
        # Risky operation
        result = call_external_api(state["input"])
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": None, "error": str(e)}

def route_on_error(state: MyState) -> str:
    """Route based on success/failure."""
    if state.get("error"):
        return "handle_error"
    return "continue"
```

That localized error state works in tandem with the explicit retry pattern. The retry counter belongs in graph state because routing decisions must remain visible, replayable, and testable after a failure. If the counter lives in a closure or global variable, concurrent runs can corrupt each other and a resumed workflow may forget how many attempts have already happened.

```python
class RetryState(TypedDict):
    input: str
    output: str
    attempts: int
    max_attempts: int
    success: bool

def process_with_retry(state: RetryState) -> dict:
    """Process with retry tracking."""
    attempts = state.get("attempts", 0) + 1

    try:
        # Your processing logic
        result = risky_operation(state["input"])
        return {
            "output": result,
            "attempts": attempts,
            "success": True
        }
    except Exception as e:
        return {
            "output": str(e),
            "attempts": attempts,
            "success": False
        }

def should_retry(state: RetryState) -> str:
    """Decide whether to retry."""
    if state["success"]:
        return "done"
    elif state["attempts"] < state["max_attempts"]:
        return "retry"
    else:
        return "failed"
```

This pattern is especially important for agents that call external tools. A search API may return a timeout, a database may reject a query, or a web automation step may land on an unexpected page. If every failure becomes a hard crash, the user sees only "agent failed." If the failure becomes state, the graph can explain what failed, how many times it retried, and which fallback route it selected.

### Integrating LLMs
The true power emerges when node operations are powered by LLMs. Each node can use a different system prompt, tool set, model, or evaluation rule while still returning a predictable state update to the rest of the graph. This lets you use model specialization without letting model behavior own the orchestration policy.

The factory function below creates specialized LLM nodes from a system prompt. The researcher, writer, and editor can each have different instructions, but all of them return the same kind of state patch. That uniformity matters because the surrounding graph should not need to know the details of each prompt in order to route the workflow.

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

class LLMAgentState(TypedDict):
    messages: Annotated[List[dict], operator.add]
    task: str
    result: str

def create_llm_node(system_prompt: str):
    """Factory function to create LLM nodes with different personas."""
    llm = init_chat_model("your-provider:your-model")  # substitute your chat model

    def node(state: LLMAgentState) -> dict:
        # Build message history
        messages = [SystemMessage(content=system_prompt)]
        messages.append(HumanMessage(content=state["task"]))

        # Call LLM
        response = llm.invoke(messages)

        return {
            "result": response.content,
            "messages": [{"role": "assistant", "content": response.content}]
        }

    return node

# Create specialized nodes
researcher = create_llm_node(
    "You are a research assistant. Gather relevant information about the topic."
)

writer = create_llm_node(
    "You are a skilled writer. Create engaging content based on the research."
)

editor = create_llm_node(
    "You are a strict editor. Review and improve the writing. Be concise."
)
```

There is a trade-off here. Putting each persona in its own node improves observability and gives you separate prompts, model choices, and test fixtures. It also increases graph complexity. If the task is a single model call with a stable prompt, do not split it into three nodes just to look agentic. Split when the intermediate state has value, when each step needs different tools, or when failures should be handled differently.

## Section 5: Multi-Agent Orchestration & Parallelism
When coordinating numerous specialized agents, the "Supervisor Pattern" is indispensable. A central node dictates routing while worker nodes handle isolated execution, which keeps specialization useful without letting every agent negotiate directly with every other agent. The goal is not to create an organization chart for its own sake; it is to control who decides, who acts, and where shared state is summarized.

```mermaid
graph TD
    Supervisor[Supervisor]
    Supervisor --> Researcher
    Supervisor --> Analyst
    Supervisor --> Writer
    Researcher --> Supervisor
    Analyst --> Supervisor
    Writer --> Supervisor
    Supervisor --> FinalOutput[Final Output]
```

The supervisor pattern works well when the work has a stable coordinator and several specialized capabilities. A researcher gathers context, an analyst interprets it, and a writer turns it into an artifact. The supervisor sees the shared state and assigns the next worker based on missing fields. That is simpler than letting every worker call every other worker, which quickly turns routing into a conversational free-for-all.

The code below models that idea with deterministic functions. In a real application, each worker might be a model-backed agent with its own tools, but the supervisor should still route from explicit state rather than vibes. If `research` is empty, route to the researcher. If `analysis` is empty, route to the analyst. If `draft` is empty, route to the writer. If all required fields exist, finish.

```python
from typing import Literal

class TeamState(TypedDict):
    task: str
    research: str
    analysis: str
    draft: str
    current_agent: str
    next_agent: Literal["researcher", "analyst", "writer", "done"]
    messages: Annotated[List[str], operator.add]

def supervisor_node(state: TeamState) -> dict:
    """Decide which agent should work next."""
    if not state.get("research"):
        return {"next_agent": "researcher", "messages": ["Assigning to researcher"]}
    elif not state.get("analysis"):
        return {"next_agent": "analyst", "messages": ["Assigning to analyst"]}
    elif not state.get("draft"):
        return {"next_agent": "writer", "messages": ["Assigning to writer"]}
    else:
        return {"next_agent": "done", "messages": ["All work complete!"]}

def researcher_node(state: TeamState) -> dict:
    """Research agent gathers information."""
    task = state["task"]
    # In real app, use LLM + tools
    return {
        "research": f"Research findings for: {task}",
        "current_agent": "researcher",
        "messages": ["Research complete"]
    }

def analyst_node(state: TeamState) -> dict:
    """Analyst processes research."""
    research = state["research"]
    return {
        "analysis": f"Analysis of: {research}",
        "current_agent": "analyst",
        "messages": ["Analysis complete"]
    }

def writer_node(state: TeamState) -> dict:
    """Writer creates final content."""
    analysis = state["analysis"]
    return {
        "draft": f"Final draft based on: {analysis}",
        "current_agent": "writer",
        "messages": ["Draft complete"]
    }

def route_to_agent(state: TeamState) -> str:
    """Route to the next agent."""
    return state["next_agent"]

# Build the multi-agent graph
team = StateGraph(TeamState)

team.add_node("supervisor", supervisor_node)
team.add_node("researcher", researcher_node)
team.add_node("analyst", analyst_node)
team.add_node("writer", writer_node)

team.add_edge(START, "supervisor")

team.add_conditional_edges(
    "supervisor",
    route_to_agent,
    {
        "researcher": "researcher",
        "analyst": "analyst",
        "writer": "writer",
        "done": END
    }
)

# Each agent reports back to supervisor
team.add_edge("researcher", "supervisor")
team.add_edge("analyst", "supervisor")
team.add_edge("writer", "supervisor")

app = team.compile()
```

The supervisor route has a hidden design assumption: there is one correct next worker at each point. That assumption is often valid for staged work, but not for independent work. If research, risk analysis, and policy review can happen at the same time, a serial supervisor will add latency without improving quality. That is when fan-out and fan-in become more useful than delegation loops.

### Fan-Out / Fan-In Parallelism
Tasks devoid of interdependencies should run simultaneously. Fan-out sends the same state to independent processors, and fan-in combines their results after each branch finishes, reducing latency without sacrificing a single final decision point. This is a natural fit for multi-perspective review, independent retrieval shards, document batch analysis, and evaluator ensembles.

The following example fans out from `START` to three processors and then fans in to a single combine node. The processors write different state keys, so their updates do not collide. If they all wrote the same list field, you would need a reducer that defines how to merge the parallel updates. Parallelism therefore makes reducer design more important, not less.

```python
from langgraph.graph import StateGraph

class ParallelState(TypedDict):
    input: str
    result_a: str
    result_b: str
    result_c: str
    final: str

# Three independent processors
def process_a(state): return {"result_a": f"A: {state['input']}"}
def process_b(state): return {"result_b": f"B: {state['input']}"}
def process_c(state): return {"result_c": f"C: {state['input']}"}

def combine(state):
    return {"final": f"{state['result_a']} + {state['result_b']} + {state['result_c']}"}

graph = StateGraph(ParallelState)

graph.add_node("a", process_a)
graph.add_node("b", process_b)
graph.add_node("c", process_c)
graph.add_node("combine", combine)

# Fan out from START to parallel nodes
graph.add_edge(START, "a")
graph.add_edge(START, "b")
graph.add_edge(START, "c")

# Fan in to combine
graph.add_edge("a", "combine")
graph.add_edge("b", "combine")
graph.add_edge("c", "combine")

graph.add_edge("combine", END)

app = graph.compile()
# LangGraph will execute a, b, c in parallel!
```

Fan-out is powerful, but it is not free. Parallel LLM calls can increase peak token spend, saturate rate limits, and create conflicting outputs that the reducer or combine node must reconcile. Use it when latency matters and the branches are genuinely independent. Avoid it when one branch needs another branch's output or when the final synthesis would spend more effort resolving contradictions than the parallelism saved.

## Section 6: Persistence, Subgraphs, and the Human-in-the-Loop
For high-stakes tasks, integrating human oversight is paramount. Interrupt mechanisms temporarily suspend workflows at a named boundary, preserve the current state, and allow a reviewer to approve, reject, or amend the next step before execution continues. This is different from sending a Slack message from inside a node; the workflow itself stops at a known point and can resume from durable state.

Human review belongs at boundaries where the next action changes risk. Sending a draft email, executing a trade, deleting a resource, publishing a generated report, or calling a privileged tool should not depend on a model's private confidence. In LangGraph, you can place the interrupt before the risky node so the proposal is created automatically but execution waits for a human or external policy system.

```python
from langgraph.checkpoint.memory import MemorySaver

class ApprovalState(TypedDict):
    proposal: str
    approved: bool
    feedback: str
    messages: Annotated[List[str], operator.add]

def create_proposal(state: ApprovalState) -> dict:
    return {
        "proposal": "I propose we invest $100K in AI infrastructure",
        "messages": ["Proposal created"]
    }

def await_approval(state: ApprovalState) -> dict:
    """This node will be interrupted for human input."""
    # The interrupt happens here - human provides approved/feedback
    return {
        "messages": ["Awaiting approval..."]
    }

def execute_proposal(state: ApprovalState) -> dict:
    if state["approved"]:
        return {"messages": ["Proposal executed!"]}
    else:
        return {"messages": [f"Proposal rejected: {state['feedback']}"]}

# Build with checkpointing
workflow = StateGraph(ApprovalState)

workflow.add_node("propose", create_proposal)
workflow.add_node("await", await_approval)
workflow.add_node("execute", execute_proposal)

workflow.add_edge(START, "propose")
workflow.add_edge("propose", "await")
workflow.add_edge("await", "execute")
workflow.add_edge("execute", END)

# Compile with checkpointer for interrupts
checkpointer = MemorySaver()
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["execute"]  # Interrupt before execution
)
```

The checkpointer is not optional decoration in this pattern. An interrupt without persistence would be only a pause in memory, which is not enough when a person may take minutes or hours to respond. The `thread_id` identifies the workflow instance, and the checkpoint records the state needed to continue from the boundary rather than replaying the proposal step.

Resuming the workflow simply requires feeding the human-amended state back in. The graph does not need to rerun earlier nodes because the checkpoint already records where the workflow stopped and which state fields were available. That is the core operator experience: review current state, update the decision fields, continue execution, and preserve the audit trail.

```python
# Start the workflow
config = {"configurable": {"thread_id": "proposal-1"}}

# Run until interrupt
result = app.invoke({"approved": False, "messages": []}, config)
print("Paused at:", result)

# Human reviews and provides approval
# Update state with human input
app.update_state(
    config,
    {"approved": True, "feedback": "Looks good!"}
)

# Continue execution
final = app.invoke(None, config)  # None continues from checkpoint
print("Final:", final)
```

### Persistence and State Checkpoints
Checkpointers are essential for crash-proofing applications. Memory is fine for local testing, but production systems usually need durable backends so a restart, deployment, or worker crash does not erase expensive agent progress. LangGraph persistence records checkpoints organized by thread, which supports resume, history inspection, time travel debugging, and human review.

The in-memory example is useful for local development because it makes the mechanics visible without adding infrastructure. It also teaches an important constraint: each persisted run needs a stable `thread_id`. Without a thread identifier, the checkpointer cannot know which prior state belongs to the current workflow, and resume semantics become impossible.

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# Each run is identified by thread_id
config = {"configurable": {"thread_id": "my-session-1"}}
result = app.invoke(input_state, config)

# Get history
history = list(app.get_state_history(config))
for state in history:
    print(f"Step: {state.metadata}")
```

SQLite is a practical next step for local durable testing or single-process workflows. The context-manager form matters because the saver owns a database connection whose lifetime should be explicit. Compile and invoke the graph inside the `with` block so the application does not hold a closed connection after the context exits.

```python
# pip install langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite import SqliteSaver

# from_conn_string is a context manager: the underlying connection is only
# valid inside the `with` block, so compile and run the graph in that scope.
with SqliteSaver.from_conn_string("workflows.db") as checkpointer:
    app = graph.compile(checkpointer=checkpointer)
    # ... invoke the app here; checkpoints survive process restarts.
```

Postgres is the better fit when multiple workers, deployments, or long-lived production threads need the same checkpoint store. The code shape is similar, but operational responsibilities change: migrations, connection management, backups, retention, and access control become part of the agent platform. The framework gives you persistence hooks; your platform still owns the database discipline.

```python
# pip install langgraph-checkpoint-postgres
from langgraph.checkpoint.postgres import PostgresSaver

# Also a context manager; call setup() once to create the checkpoint tables.
with PostgresSaver.from_conn_string("postgresql://user:pass@host:5432/db") as checkpointer:
    checkpointer.setup()  # first run only
    app = graph.compile(checkpointer=checkpointer)
```

### Streaming Operations
LangGraph supports granular streaming. You can emit entire state updates or individual tokens generated directly by the LLM inside nodes, which gives user interfaces and operators visibility before a long workflow reaches its final state. Streaming is not just cosmetic; it changes how users trust long-running agents because they can see which node is active and what intermediate state is changing.

Choose the stream mode based on the observer. A developer debugging a workflow may want full values or updates. A product interface may want token-level messages from model calls. An operations view may want task or checkpoint events. The same graph can support several of these views, which is much cleaner than sprinkling custom callbacks throughout every node.

```python
# Stream all events
for event in app.stream(input_state, config, stream_mode="values"):
    print(f"State update: {event}")

# Stream specific node outputs
for event in app.stream(input_state, config, stream_mode="updates"):
    print(f"Node output: {event}")
```

```python
# Stream tokens from LLM calls within nodes
async for event in app.astream_events(input_state, config, version="v2"):
    if event["event"] == "on_llm_stream":
        print(event["data"]["chunk"].content, end="", flush=True)
```

### Composing Workflows (Subgraphs)
Encapsulating complexity makes architectures reusable. Any compiled graph can become a node in a broader parent graph, letting you test a workflow independently before composing it into a larger agent system. Subgraphs are especially helpful when teams own different parts of an agent platform or when a repeated capability, such as research or validation, appears in many workflows.

The subgraph example below is intentionally simple: a research graph searches and summarizes, then a parent graph uses the compiled research workflow as one node before writing. The parent does not need to know every internal research step. It only needs the subgraph's interface to match the parent state or to be wrapped by a mapping function.

```python
# Create a reusable subgraph
research_graph = StateGraph(ResearchState)
research_graph.add_node("search", search_node)
research_graph.add_node("summarize", summarize_node)
research_graph.add_edge(START, "search")
research_graph.add_edge("search", "summarize")
research_graph.add_edge("summarize", END)
research_subgraph = research_graph.compile()

# Use in parent graph
main_graph = StateGraph(MainState)
main_graph.add_node("research", research_subgraph)  # Subgraph as node!
main_graph.add_node("write", write_node)
main_graph.add_edge(START, "research")
main_graph.add_edge("research", "write")
main_graph.add_edge("write", END)
```

Subgraphs are a design boundary, so treat them like APIs. Decide which state keys are shared, which keys are private, how checkpoints should be scoped, and whether the subgraph is per-invocation or per-thread. If those choices are left implicit, nested workflows become hard to inspect, and a parent graph may accidentally depend on a child graph's internal state shape.

### Architecture Design Patterns
Here are battle-tested topologies to memorize for high-performance agentic systems. The diagrams are simple, but each one encodes a design decision about feedback, validation, hierarchy, or parallelism that should be explicit before you write nodes. Treat these patterns as starting points, not as a menu where every agent must use the most elaborate option.

**Pattern 1: Research-Write-Review Cycle** fits content and analysis workflows where a draft should improve after critique. The important edge is the review loop, because it makes revision a controlled route instead of an ad-hoc second prompt.
```mermaid
graph LR
    Research --> Write --> Review --> Approved{Approved?}
    Approved -- No --> Write
```

**Pattern 2: Multi-Stage Validation** fits workflows with several independent gates. Each validation node can reject early, which keeps policy, format, and content checks separate enough to test and debug.
```mermaid
graph TD
    Input --> ValFormat[Validate Format]
    ValFormat --> ValContent[Validate Content]
    ValContent --> ValPolicy[Validate Policy]
    ValPolicy --> Process

    ValFormat --> Reject1[Reject]
    ValContent --> Reject2[Reject]
    ValPolicy --> Reject3[Reject]
```

**Pattern 3: Hierarchical Agents** fits large tasks where one supervisor delegates to team leads and workers. The hierarchy reduces coordination noise because each layer summarizes state before passing it upward.
```mermaid
graph TD
    Manager --> LeadA[Team Lead A]
    Manager --> LeadB[Team Lead B]
    Manager --> LeadC[Team Lead C]

    LeadA --> Worker1[Worker 1]
    LeadB --> Worker2[Worker 2]
    LeadC --> Worker3[Worker 3]
```

**Pattern 4: MapReduce for Parallel Processing** fits document batches, independent retrieval shards, and multi-perspective analysis. The splitter creates independent work, while the reducer owns the final synthesis and conflict handling.
```mermaid
graph TD
    Splitter --> Proc1[Process 1]
    Splitter --> Proc2[Process 2]
    Splitter --> Proc3[Process 3]

    Proc1 --> Reducer
    Proc2 --> Reducer
    Proc3 --> Reducer
```

The pattern choice should follow the failure mode. Use a research-write-review cycle when critique can improve one artifact. Use multi-stage validation when different gates enforce different policies. Use hierarchical agents when large work needs summarized delegation. Use MapReduce when many independent inputs or perspectives must be processed before one synthesis step. A graph is most maintainable when the topology explains the work rather than impressing the reader.

### Cost and Benefit Categories
Why invest in the steeper learning curve of LangGraph over rudimentary orchestration scripts? The economic value comes from removing custom state-management code, reducing restart waste, and giving operators a replayable record of how an agent reached its state. You will not find dollar figures here — every team's mix of workflow volume, model cost, and on-call burden differs. Instead, compare the cost categories below using your own measurements before making an architecture decision.

**Engineering time** is usually the first category to move. Ad-hoc orchestration scripts tend to accumulate bespoke persistence, retry, and routing logic that a graph framework already provides. LangGraph does not eliminate design work, but it shifts effort from reinventing state machines toward defining nodes, edges, and checkpoints.

**Operational overhead** covers the human time spent babysitting runs: restarting failed workflows, stitching together logs, and building one-off review tooling. Built-in interrupts, checkpointing, and state replay reduce the custom glue code operators maintain when agents run in production.

**Failure and restart cost** captures wasted model tokens, duplicated tool calls, and downstream rework when a crash forces a full rerun from scratch. Durable checkpoints and automatic resume narrow that blast radius — fewer runs restart from zero, and fewer incidents require manual triage.

The direction of the tradeoff is consistent: you pay upfront in framework learning and graph design, and you recover value as workflow count, failure rate, and review requirements grow. Map each category to your team's actual numbers — development hours, on-call minutes, and API spend from restarts — before treating LangGraph as a net win.

| Component | Without LangGraph | With LangGraph |
|-----------|-------------------|----------------|
| State Management | Often requires substantial custom code | Built-in |
| Crash Recovery | Manual replay (lost time + tokens) | Automatic resume |
| Human Review | Custom tooling | Native interrupts |
| Debugging | Log analysis | State replay |

| Feature | Airflow/Prefect | LangGraph |
|---------|-----------------|-----------|
| Primary use | Data pipelines | AI workflows |
| Node types | Python functions | LLM-aware functions |
| State management | External | Built-in with reducers |
| Streaming | Support varies by platform and pattern | First-class support |
| Human-in-loop | Often requires extra orchestration | Native interrupt/resume |
| LLM integration | DIY | Native with LangChain |

The comparison is not an argument that LangGraph replaces data orchestrators. Airflow and Prefect remain strong choices for scheduled data pipelines, dependency management, and operational batch work. LangGraph is better matched to interactive or long-running agent workflows where state, model calls, tool use, human decisions, and streaming progress are part of one runtime. Many production systems use both: a data orchestrator prepares data, and a LangGraph application handles the stateful agent interaction.

## Did You Know?

- LangGraph v1.x is positioned by the official docs as a low-level orchestration framework for long-running, stateful agents, and it can be used with LangChain components without requiring every application to be a LangChain chain.
- The Graph API documentation describes state, nodes, and edges as the three core components of a graph, with reducers controlling how node updates apply to the shared state.
- LangGraph persistence saves checkpoints by thread, which is what enables human review, conversational memory, time travel debugging, and fault-tolerant recovery after node failures.
- The original LangGraph launch blog emphasized cyclic graphs because cycles are a critical part of many agent runtimes, including ReAct-style loops and multi-agent workflows.

## Common Mistakes
Most LangGraph bugs are not mysterious model failures. They are ordinary workflow bugs made more visible by the graph: state fields overwrite when they should accumulate, route functions return keys that are not mapped, loops lack a stopping rule, or checkpointing is added after the human review path has already shipped. The fix is usually to make the workflow contract stricter and the route decisions easier to test.

| Mistake | Why it happens | Fix / Remedy |
|---------|---------------|--------------|
| **Forgetting State Annotations** | Defining `messages: List[str]` replaces the list on every node execution. | Use `Annotated[List[str], operator.add]` for accumulation. |
| **Infinite Loops** | Conditional edges lack fallback limits, trapping agents in endless validation. | Track a `retry_count` in state and exit forcefully when it exceeds a threshold. |
| **Missing Routing Edge Cases** | Conditional edge fails to account for a string variant, raising a KeyError. | Usually return a fallback/default route in routing functions for unexpected cases. |
| **Stateful Nodes** | Relying on global Python variables (`global count`) inside nodes corrupts concurrent runs. | Enforce pure functions. Move all tracking to the `TypedDict` graph state. |
| **Bloated State Objects** | Pushing massive 10MB payloads directly into state kills memory during checkpoints. | Persist references to external storage (`document_url: str`) instead of raw data. |
| **Missing Graph Compilation** | You must compile the graph before invoking it. | Always instantiate via `app = graph.compile()` before invoking. |
| **Unpersisted Threads** | Pausing for human-in-the-loop without attaching a checkpointer wipes the session. | Define `checkpointer=MemorySaver()` (or Postgres) during `.compile()`. |

### Avoiding Pitfalls through Proper Design
The examples below show the same design lesson from several angles: make state explicit, keep node behavior local, and avoid hidden mutable process state. LangGraph gives you a runtime that can preserve and route state, but it cannot infer whether your state schema describes the real workflow. That judgment belongs to the developer.

```python
# BAD: Lists get replaced, not accumulated
class BadState(TypedDict):
    messages: List[str]  # Each node replaces the list!

# GOOD: Use annotation for accumulation
class GoodState(TypedDict):
    messages: Annotated[List[str], operator.add]
```

The first mistake is the easiest to miss because the graph still runs. It simply forgets earlier messages. You may only notice the bug after a recovery path fails because the reviewer cannot see the original draft or a later model call lacks the context needed to explain an earlier decision.

```python
# BAD: No exit condition
graph.add_conditional_edges("check", should_continue, {
    "retry": "process",
    "done": "output"
})
# If should_continue always returns "retry", infinite loop!

# GOOD: Add max retries
def should_continue_safe(state):
    if state["attempts"] >= MAX_RETRIES:
        return "done"  # Force exit
    return "retry" if not state["success"] else "done"
```

The second mistake is more expensive because it burns runtime. A loop without a domain-level exit condition will eventually hit a recursion limit or operational timeout, but that is a last-resort guardrail. A better design stores attempts, remaining budget, or reviewer escalation state and routes intentionally before the runtime has to stop the graph.

```python
# BAD: Missing route
def route(state):
    if condition_a:
        return "a"
    elif condition_b:
        return "b"
    # What if neither? KeyError!

# GOOD: Always have a default
def route(state):
    if condition_a:
        return "a"
    elif condition_b:
        return "b"
    else:
        return "default"
```

Routing failures often show up as rare incidents because the missing branch requires an unusual input. The defensive habit is to write route functions as if the classifier is imperfect, because it is. A default route can send work to generic processing, human review, or a safe failure state with enough context for debugging.

```python
# BAD: Node maintains internal state
counter = 0
def bad_node(state):
    global counter
    counter += 1  # This persists across invocations!
    return {"count": counter}

# GOOD: All state in the graph state
def good_node(state):
    count = state.get("count", 0) + 1
    return {"count": count}
```

Global counters and cached mutable objects are especially dangerous in agent systems because workflows are often concurrent and long-lived. One user's run can leak into another user's run, and a resumed thread may disagree with process memory after a deployment. Put workflow progress into state and put shared infrastructure into runtime context or dependency injection.

```python
# BAD: Storing large data in state
class BadState(TypedDict):
    full_document: str  # 10MB document in every state snapshot!

# GOOD: Store references, load when needed
class GoodState(TypedDict):
    document_id: str  # Reference to external storage
```

Large state makes every checkpoint heavier and every inspection harder. Prefer storing durable references to documents, embeddings, artifacts, or logs, then let nodes load the needed data when they run. Store summaries and decisions in graph state; store bulky artifacts in systems designed for bulky artifacts.

### Golden Best Practices
The following best practices are a compact design checklist. Before writing the graph, decide which state is durable, which state is transient model context, and which state should be recomputed from external systems. That decision prevents many later debates about why a checkpoint is large, incomplete, or hard to migrate.

```python
# Think about:
# - What needs to persist across nodes?
# - What should accumulate vs replace?
# - What's the minimal state needed?

class WellDesignedState(TypedDict):
    # Core data
    input: str
    output: str

    # Progress tracking (accumulates)
    steps_completed: Annotated[List[str], operator.add]

    # Metadata (replaces)
    current_phase: str
    last_error: Optional[str]
```

Pure nodes are easier to test, retry, and reason about after a crash. That does not mean a node can never call an external service, but it does mean the node should return a clear state patch and make side effects deliberate. If a node sends an email, writes a ticket, or executes a trade, put that side effect behind a review boundary or idempotency key.

```python
# Node should be deterministic given same state
def pure_node(state: MyState) -> dict:
    # Only use state input
    # No external side effects
    # Return consistent output
    return {"result": process(state["input"])}
```

Reusable subgraphs help once a workflow is proven, not before. Start with the simplest graph that exposes the control flow, then extract validation, retrieval, or approval patterns when multiple workflows need the same behavior. Premature subgraphs can hide state boundaries before you understand them.

```python
# Create reusable components
validation_subgraph = create_validation_graph()
processing_subgraph = create_processing_graph()

# Compose in main graph
main_graph.add_node("validate", validation_subgraph)
main_graph.add_node("process", processing_subgraph)
```

Runaway cycles need both framework and business safeguards. A `recursion_limit` is a framework-level maximum; a retry count in state is a business-level decision about when the work is no longer improving. Use both, and make the fallback route visible enough that operators know whether the graph stopped because it succeeded, degraded, or escalated.

```python
# Prevent runaway cycles
config = {
    "configurable": {"thread_id": "x"},
    "recursion_limit": 50  # Max steps
}
result = app.invoke(state, config)
```

Visualization is not only for presentations. Rendering the graph catches accidental branches, missing convergence points, and route maps that do not match the workflow people think they built. When a graph review finds a mismatch between the diagram and the intended process, fix the graph before tuning the prompts.

```python
# Visualize your graph to catch issues
from IPython.display import Image, display

display(Image(app.get_graph().draw_mermaid_png()))
```

## Quiz

Use these questions to check whether you can reason about LangGraph as an orchestration tool rather than memorize API names. The answers connect directly back to the outcomes: state design, cyclic control flow, failure diagnosis, multi-agent coordination, persistence, and the trade-off between graph-based orchestration and simpler approaches.

<details>
<summary>1. A developer notices their LangGraph workflow is replacing the message history instead of appending new messages. What is the architectural flaw?</summary>
The developer likely assigned `messages: List[str]` in their `TypedDict` instead of applying LangGraph's accumulation annotation. Without `Annotated[List[str], operator.add]`, LangGraph falls back to its default reducer behavior. This default behavior overwrites the existing state key entirely with the newly returned dictionary value. To resolve this, the state definition must explicitly instruct the framework to merge list contents.
</details>

<details>
<summary>2. You need to implement a fallback mechanism where a failed API call is retried up to three times before halting. How does a graph accomplish this?</summary>
You must model the error and the retry logic explicitly as state data properties rather than relying on standard try-catch blocks alone. By incorporating an `attempts: int` counter and `success: bool` flag into your State, you gain granular control over execution flow. You can then write a routing function that inspects the outcome and iterates the cycle until `attempts >= 3`. At that point, the function must forcefully return a fallback edge to break the cycle.
</details>

<details>
<summary>3. A team is designing a system where an AI agent proposes a trade, but a human must approve it before execution. How should this be implemented natively in LangGraph?</summary>
The framework handles this effortlessly using the specialized checkpointer interrupt feature. The team should initialize their orchestrator by calling `app.compile(checkpointer=MemorySaver(), interrupt_before=["execute"])`. This halts execution immediately before the trade execution node runs, preserving the current state safely in memory. Once human feedback is secured, it is injected back via `.update_state()`, allowing the system to proceed seamlessly.
</details>

<details>
<summary>4. An architect wants three distinct specialized agents to analyze a document simultaneously and then combine their insights. Which graph configuration achieves this?</summary>
The architect should fan-out the execution by connecting the START node directly to all three worker nodes simultaneously via unconditional edges. Next, all three worker nodes must direct their downstream edges into a single downstream combination node. Because LangGraph automatically runs independent nodes in parallel, it naturally processes the three tasks concurrently. This approach eliminates latency bottlenecks before finally synchronizing the distinct outputs.
</details>

<details>
<summary>5. A graph enters an infinite loop between a "review" node and a "draft" node. How can this architectural flaw be mitigated safely?</summary>
A runaway cycle typically happens when a conditional edge lacks an explicit architectural cap or fallback route. To mitigate this safely, introduce a `recursion_limit` directly in the execution configuration object. Additionally, you should track the total revision count inside the node state. This allows your routing logic to force an exit or transition to a generic "publish" edge once that count hits a sensible upper limit.
</details>

<details>
<summary>6. During a high-traffic period, your container crashes halfway through a multi-agent debate. Without starting over, how can LangGraph resume from the exact point of failure?</summary>
LangGraph achieves system resiliency using persistent Checkpointers backed by external databases. If the graph was compiled with a `SqliteSaver` or `PostgresSaver`, the orchestrator simply reinvokes the workflow targeting the exact `thread_id` contained within the configuration object. The application then reconstructs the last fully processed state segment automatically. From there, it picks up execution at the subsequent unexecuted node without dropping any prior context.
</details>

<details>
<summary>7. When should you choose a plain Python loop or linear sequence instead of LangGraph, and when does graph-based workflow orchestration become worth the overhead?</summary>
Choose a plain loop when the state is local, disposable, and easy to understand in one function. Choose a linear sequence when every step always runs in the same order and failure should fail the whole request. LangGraph becomes worth the overhead when the workflow needs durable state, conditional routes, retries, human review, streaming visibility, multi-agent coordination, or recovery from partial progress. The trade-off is explicitness: you write more structure, but the workflow becomes inspectable and resumable.
</details>

## Hands-On Exercise: Building a Multi-Agent Analyst

**Objective**: Implement a supervisor-managed research system that handles topic searches, evaluates depth, and loops if criteria aren't met. Keep the exercise small: the goal is to understand LangGraph control flow, not to build a production research product.

**Step 1: Environment Setup**
Create a new directory and virtual environment from the repository root or another shell where the project Python is available:
```bash
REPO_ROOT="$(pwd)"
mkdir langgraph-lab && cd langgraph-lab
"$REPO_ROOT/.venv/bin/python" -m venv venv
source venv/bin/activate
pip install langgraph langchain-google-genai typing-extensions
```

**Step 2: Define Your TypedDict State**
Create a python script `agent.py`. Add a state dictionary that tracks the requested `topic`, a `research_log` (using `operator.add` to accumulate discoveries), and a `loop_count` integer to cap search attempts.

**Step 3: Construct Worker Nodes**
Implement two Python functions that keep side effects obvious and return only partial state updates. This mirrors production LangGraph style, where every node should be easy to unit test with one input state and one returned patch:
1. `researcher_node`: Appends a mocked observation to `research_log`.
2. `reviewer_node`: Evaluates if the `research_log` has 2 or more entries. If so, updates a boolean `is_comprehensive` flag to True.

**Step 4: Implement Routing**
Write a routing function taking the current state. If `loop_count` > 3, return `"max_reached"`. If `is_comprehensive` is True, return `"done"`. Otherwise, return `"research"` so the graph cycles deliberately rather than through hidden recursion.

**Step 5: Graph Compilation & Execution**
Instantiate a `StateGraph`, link the nodes, setup the conditional edge pointing out of the reviewer node, and execute `.invoke()`. The output should show accumulated research entries and a final route that proves the loop exited for a reason.

<details>
<summary>View the Full Solution Code</summary>

```python
import operator
from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, START, END

# Step 2: State Definition
class ResearchState(TypedDict):
    topic: str
    research_log: Annotated[List[str], operator.add]
    loop_count: int
    is_comprehensive: bool

# Step 3: Node Implementation
def researcher_node(state: ResearchState) -> dict:
    current_count = state.get("loop_count", 0)
    return {
        "research_log": [f"Found insight part {current_count + 1}."],
        "loop_count": current_count + 1
    }

def reviewer_node(state: ResearchState) -> dict:
    logs = state.get("research_log", [])
    return {
        "is_comprehensive": len(logs) >= 2
    }

# Step 4: Routing Logic
def routing_logic(state: ResearchState) -> str:
    if state.get("loop_count", 0) > 3:
        return "max_reached"
    if state.get("is_comprehensive"):
        return "done"
    return "research"

# Step 5: Compilation
workflow = StateGraph(ResearchState)
workflow.add_node("researcher", researcher_node)
workflow.add_node("reviewer", reviewer_node)

workflow.add_edge(START, "researcher")
workflow.add_edge("researcher", "reviewer")
workflow.add_conditional_edges(
    "reviewer",
    routing_logic,
    {
        "done": END,
        "max_reached": END,
        "research": "researcher"
    }
)

app = workflow.compile()
output = app.invoke({"topic": "Quantum Computing", "research_log": [], "loop_count": 0})
print("Final State:", output)
```
</details>

### Success Checklist
- [ ] Nodes accurately append to the `research_log`.
- [ ] Execution completes gracefully after hitting the minimum log requirement.
- [ ] Changing the `reviewer_node` logic to require 5 items effectively triggers the max loop cutoff.

## Sources

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph) - Official v1.x positioning for LangGraph as a low-level runtime for long-running, stateful agents.
- [Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api) - Defines the state, node, edge, reducer, compilation, and recursion-limit concepts used throughout this module.
- [Use the graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api) - Practical guide for sequences, branches, loops, `Send`, and `Command` control-flow patterns.
- [Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) - Official examples for deciding when a workflow or agent pattern fits a LangGraph application.
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) - Source for checkpoints, threads, time travel, fault tolerance, memory, and checkpointer backends.
- [Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/human-in-the-loop) - Official interrupt and resume mechanics for workflows that require external approval or input.
- [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming) - Documents state, update, message, checkpoint, task, and debug stream modes.
- [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) - Explains using one graph as a node inside another graph and how subgraph state communicates with parent state.
- [LangChain multi-agent docs](https://docs.langchain.com/oss/python/langchain/multi-agent) - Pattern guidance for supervisor, handoff, and tool-calling multi-agent designs built on LangGraph concepts.
- [LangGraph launch blog](https://www.langchain.com/blog/langgraph) - Original LangChain blog introducing LangGraph for cyclic agent runtimes.
- [LangGraph multi-agent workflows blog](https://www.langchain.com/blog/langgraph-multi-agent-workflows) - Early examples of collaboration, supervision, and critique loops using LangGraph.
- [Building LangGraph from first principles](https://www.langchain.com/blog/building-langgraph) - Design rationale for LangGraph's low-level runtime, state, durability, and control philosophy.
- [Interrupt blog](https://www.langchain.com/blog/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt) - LangChain discussion of first-class human-in-the-loop support in LangGraph.
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) - Paper grounding the reasoning/action loop that many graph-based agent runtimes need to control.
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) - Paper motivating self-reflection and feedback loops that map naturally to cyclic graph control flow.
- [Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761) - Background on model tool-use behavior, which LangGraph workflows often orchestrate explicitly.
- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) - Multi-agent conversation paper useful for contrasting graph-supervised coordination with agent-to-agent chat.

## Next Module

[Module 1.4 - LlamaIndex](../module-1.4-llamaindex/) - Add a purpose-built data framework for RAG and knowledge-intensive agents: ingestion, indexing, and query engines on top of the LangChain/LangGraph foundations you just built.
