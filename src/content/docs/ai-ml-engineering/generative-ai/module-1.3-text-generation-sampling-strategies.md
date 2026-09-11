---
citations_verified: true
title: "Text Generation & Sampling Strategies"
slug: ai-ml-engineering/generative-ai/module-1.3-text-generation-sampling-strategies
sidebar:
  order: 304
---

> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 5-6 hours
>
> **Prerequisites**: Module 1.1 (Introduction to LLMs), Module 1.2 (Tokenization & Text Processing), and basic Python.
>
> **Track**: AI/ML Engineering — Generative AI Foundations

---

## Learning Outcomes

By the end of this module, you will be able to:

- **Compare** greedy decoding, beam search, temperature sampling, nucleus sampling, top-k filtering, min-p filtering, repetition penalties, constrained decoding, and stopping controls across realistic production scenarios.
- **Design** sampling profiles for structured extraction, code generation, customer support chat, summarization, creative ideation, and long-form drafting.
- **Diagnose** repeated phrases, malformed structured output, dull responses, runaway generation, and incoherent high-variance text by tracing the decoding configuration.
- **Evaluate** the trade-offs between determinism, diversity, cost, latency, safety, and user experience when selecting generation parameters.
- **Implement** a runnable local sampling playground that demonstrates how decoding settings change token selection without requiring access to a hosted model API.

## Why This Module Matters

Hypothetical scenario: A product manager at a travel company asks the AI team why the support assistant confidently invented a refund exception that did not exist in the policy manual. The prompt included the correct policy, the retrieval system returned the right document, and the model was capable of summarizing it accurately in offline tests. The failure appeared only in production, where the assistant had been configured with a chat-friendly decoding profile designed to sound warm, varied, and conversational. That profile was useful for brainstorming marketing copy, but it was dangerous for a workflow where the correct answer was narrow, contractual, and auditable.

Sampling strategy is the part of text generation that decides which token gets written next after the model has scored the possible options. A model can assign probabilities well and still produce a bad answer if the decoding layer rewards novelty in a task that requires consistency. Conversely, the same model can sound lifeless, repetitive, or evasive if every application is forced through a deterministic profile. Production AI engineering is not only prompt design; it is also control over the statistical process that turns probability distributions into text.

This module teaches sampling as an engineering control surface rather than as a set of magic knobs. You will start with the token-by-token mechanics, then progressively add temperature, top-p, top-k, repetition penalties, stop sequences, and length limits. The goal is not to memorize default numbers. The goal is to reason from the workload: what must be stable, what may vary, what must never appear, how long the answer should be, and what failure mode would hurt users most.

## The Generation Loop

[Text generation is usually autoregressive, which means the model writes one token, appends that token to the context, and then uses the expanded context to score the next token.](https://huggingface.co/docs/transformers/v4.45.1/llm_tutorial) The model is not drafting a complete paragraph in a hidden buffer and then revealing it. It is repeatedly answering a narrower question: given everything so far, which token should come next? This is why early decoding choices matter so much. A slightly unusual token at step five changes the context at step six, which changes the probabilities at step seven, and the whole answer can drift into a different path.

```mermaid
flowchart TD
    A[Prompt and prior context] --> B[Model scores next-token candidates]
    B --> C[Raw logits for vocabulary]
    C --> D[Decoding controls reshape or filter choices]
    D --> E[Sampler selects one token]
    E --> F[Append token to context]
    F --> G{Stop condition met?}
    G -- No --> B
    G -- Yes --> H[Return final text]
```

At each step, the model produces raw scores called logits. Those scores are converted into probabilities, and the decoding strategy decides whether to choose the highest-probability token or sample from a filtered set. If the prompt is `The deployment failed because the`, the model might assign high probability to `image`, `probe`, `node`, and `secret`, while assigning tiny probabilities to thousands of irrelevant tokens. Decoding determines whether the answer follows the safest path, explores a plausible alternative, or accidentally reaches into the low-probability tail.

```mermaid
flowchart LR
    subgraph StepOne["Step 1"]
        P1["Prompt: The deployment failed because the"] --> M1["Model scores vocabulary"]
        M1 --> D1["image 0.32<br/>probe 0.24<br/>node 0.18<br/>secret 0.09<br/>weather 0.001"]
        D1 --> S1["Sampler chooses: image"]
    end
    S1 --> P2
    subgraph StepTwo["Step 2"]
        P2["Context: The deployment failed because the image"] --> M2["Model scores vocabulary"]
        M2 --> D2["tag 0.36<br/>pull 0.25<br/>registry 0.16<br/>digest 0.08"]
        D2 --> S2["Sampler chooses: tag"]
    end
    S2 --> OUT["Output path: image tag ..."]
```

The key engineering insight is that decoding does not create knowledge that the model lacks. It changes how strongly the model follows its most likely continuation, how much alternative wording is allowed, and how aggressively risky low-probability options are removed. A retrieval-augmented answer still needs low-variance decoding if every word must align with source material. A story-writing assistant still needs some filtering because creativity is not the same as random token selection.

**Active learning prompt:** Before reading further, decide which workload should be more deterministic: extracting `namespace`, `deployment`, and `imageTag` fields from an incident report, or suggesting five names for a new internal platform team. Write one sentence explaining the failure mode you are trying to prevent in each case.

## Greedy Decoding and Determinism

Greedy decoding always picks the highest-probability next token. When the model gives `image` a probability of `0.32` and `probe` a probability of `0.24`, greedy decoding selects `image` every time. This makes the output stable for the same prompt and model snapshot, which is valuable for tests, structured extraction, reproducible reports, and workflows where downstream systems parse the response. It also makes the model less able to explore alternative phrasing, which can make responses feel repetitive or overly conservative.

```ascii
+-----------------------------+-----------------------------+
| Candidate next token        | Probability after scoring   |
+-----------------------------+-----------------------------+
| image                       | 0.32                        |
| probe                       | 0.24                        |
| node                        | 0.18                        |
| secret                      | 0.09                        |
| timeout                     | 0.06                        |
+-----------------------------+-----------------------------+
| Greedy choice               | image                       |
+-----------------------------+-----------------------------+
```

Greedy decoding is often exposed as `temperature: 0.0`, although different providers may implement exact determinism differently. Some APIs also have model-side nondeterminism, backend changes, safety layers, or tool-use routing that can affect repeatability even when temperature is zero. From an application design perspective, however, a zero-temperature profile is still the right starting point whenever correctness means "the same valid format every time" rather than "a pleasantly varied answer."

A deterministic profile does not guarantee truth. If the prompt asks for a policy that is not present in the context, greedy decoding may consistently produce the same wrong answer. Determinism controls variance, not factuality. In production, you pair deterministic decoding with schema validation, retrieval grounding, refusal rules, and tests that compare output against expected structures. Treat greedy decoding as one guardrail in a larger reliability system.

```python
EXTRACTION_PROFILE = {
    "temperature": 0.0,
    "top_p": 1.0,
    "max_tokens": 300,
    "stop_sequences": ["\n\nEND"],
}
```

Use this kind of profile when a downstream parser, ticketing system, CI pipeline, or audit log depends on predictable output shape. The `top_p` value is effectively neutral here because a zero-temperature setting already selects the top token. The `max_tokens` limit protects cost and prevents runaway generation, while the stop sequence gives the model a clear place to end after the target payload. The important design habit is to write the profile from the consumer backward: if a parser consumes it, do not optimize for charm.

## Beam Search: Exploring Multiple High-Probability Paths

Greedy decoding commits to one path at every step, which is fast but myopic. [Beam search keeps several partial sequences alive at once, expands each candidate by one token, and retains only the highest-scoring beams until generation finishes.](https://huggingface.co/docs/transformers/en/generation_strategies) Instead of asking "what is the best next token?" once, beam search asks "what are the best continuations if I allow myself to reconsider later?" That extra search budget can help when the locally best token leads to a dead end, which is why beam search historically mattered for machine translation, captioning, and other tasks where a slightly unusual early word can still produce a strong final sentence.

```ascii
Beam width = 2 after one decoding step

Step context: "The rollout failed because the"

Beam 1: "The rollout failed because the image"     score 0.41
Beam 2: "The rollout failed because the probe"     score 0.33
Discarded: "... node", "... secret", "... timeout"

Next step expands BOTH beams, then keeps the top 2 combined scores again.
```

Beam search increases compute and memory because each step evaluates multiple active hypotheses. Wider beams explore more alternatives, but they also make generation slower and can produce text that is safe yet bland. In open-ended chat, beam search often feels repetitive because all surviving paths chase the same high-probability phrasing. In structured tasks with a scoring function, such as translation with a reference metric or constrained summarization with length penalties, beam search can still be the right tool because you are optimizing a measurable objective rather than conversational surprise.

| Beam setting | Behavior | Best fit | Main risk |
|---|---|---|---|
| `num_beams: 1` | Equivalent to greedy for many APIs | Fast extraction and code | No recovery from early mistakes |
| `num_beams: 4-8` | Moderate search with better global coherence | Translation-like rewriting, short summaries | Higher latency and cost |
| `num_beams: >8` | Expensive search with diminishing returns | Research or offline batch jobs | Often dull, overly literal text |

A practical engineering rule is to reserve beam search for workloads with an external score or a narrow output space. If your success metric is "valid JSON every time," deterministic greedy decoding plus schema validation is usually simpler than beam search. If your success metric is "best BLEU score against a reference translation," beam search may still earn its cost. For customer-facing assistants, beam search is rarely the first knob you touch; temperature, top-p, grounding, and validation layers usually matter more.

> **Active learning prompt:** A team uses beam width `8` for marketing copy generation and complains that every draft sounds identical. Before changing models, explain whether the complaint fits beam search behavior or indicates a different failure mode such as weak prompts or missing diversity controls.

## Temperature: Reshaping Confidence

Temperature changes the sharpness of the probability distribution before sampling. Low temperature makes high-probability tokens even more dominant, while high temperature flattens the distribution and gives lower-probability tokens more opportunity to appear. This is why temperature is often described as a creativity knob, but that nickname is incomplete. It is more precise to say that temperature controls how willing the sampler is to depart from the model's strongest local preference.

```mermaid
flowchart TD
    A[Raw logits] --> B{Temperature}
    B -- "0.0" --> C[Greedy: highest token only]
    B -- "0.2" --> D[Very sharp distribution]
    B -- "0.7" --> E[Moderate variation]
    B -- "1.0" --> F[Original distribution]
    B -- "1.3" --> G[Flattened distribution]
    C --> H[Stable structured output]
    D --> I[Focused code or extraction]
    E --> J[Natural chat or summaries]
    F --> K[Creative drafting]
    G --> L[Risk of drift without filtering]
```

A temperature near zero is appropriate when the output space is narrow. Code generation, YAML generation, SQL drafting, and JSON extraction all punish unnecessary variation because a single unexpected token can break execution or parsing. A temperature around `0.2` can still allow limited flexibility while keeping the answer close to the most likely continuation. A temperature around `0.7` is common for conversational assistants because users usually prefer language that adapts to their wording and does not repeat the same sentence template forever.

High temperature becomes useful when the user explicitly wants novelty, such as brainstorming product names or exploring story directions. It is still an engineering risk because the sampler is more likely to select tokens that are merely possible rather than strongly supported by the prompt. High temperature should usually be paired with top-p filtering, stronger review, or an application design that can tolerate weak ideas. Never use high temperature to compensate for missing context or unclear instructions; it will make the model more adventurous, not more informed.

| Temperature range | Behavior | Best fit | Main risk |
|---|---|---|---|
| `0.0` | Greedy and highly repeatable | JSON, tests, strict templates | Consistently repeats a wrong assumption if the prompt is flawed |
| `0.1-0.3` | Focused with minimal variation | Code, YAML, factual summaries | Can sound rigid and may miss useful alternate wording |
| `0.4-0.8` | Balanced and conversational | Support chat, explanations, reports | May add phrasing variety that complicates parsing |
| `0.9-1.2` | Creative and diverse | Ideation, storytelling, drafts | Can drift from constraints without filters |
| `>1.2` | Highly exploratory | Experimental writing only | Incoherence, invented details, wasted tokens |

**Active learning prompt:** Your team generates Kubernetes NetworkPolicy YAML from natural-language requests. The model often adds a friendly preface before the manifest, and CI fails because the output is no longer valid YAML. Would you first lower temperature, raise temperature, add a repetition penalty, or increase `max_tokens`? Explain the mechanism behind your choice, not just the setting.

## Top-p: Dynamic Filtering With a Nucleus

Top-p, also called nucleus sampling, filters the candidate tokens by cumulative probability. The sampler sorts tokens from most likely to least likely, [keeps the smallest set whose total probability reaches the `top_p` threshold](https://huggingface.co/docs/transformers/v4.22.2/main_classes/text_generation), and discards everything else. Unlike top-k, the size of the candidate set changes at every generation step. When the model is very confident, top-p may keep only a few tokens. When the model is uncertain among many plausible options, top-p can keep a broader set.

```ascii
Sorted candidates for one decoding step
+-------------+-------------+------------------------+
| Token       | Probability | Cumulative probability |
+-------------+-------------+------------------------+
| image       | 0.32        | 0.32                   |
| probe       | 0.24        | 0.56                   |
| node        | 0.18        | 0.74                   |
| secret      | 0.09        | 0.83                   |
| timeout     | 0.06        | 0.89                   |
| quota       | 0.04        | 0.93  <- top_p 0.90    |
| pineapple   | 0.001       | discarded              |
+-------------+-------------+------------------------+
```

Top-p is useful because many language-model distributions have a long tail of low-probability tokens. Those tail tokens are not always impossible, but they are often where gibberish, weird topic jumps, and unsupported claims begin. A `top_p` value such as `0.9` allows the model to vary among plausible choices while removing the most unlikely tail. A tighter value such as `0.5` or `0.7` forces the answer to stay close to the strongest candidates, which can be helpful for factual summaries or code-like output.

The interaction between temperature and top-p matters more than either setting alone. Temperature changes the shape of the distribution, while top-p decides how much of that shaped distribution remains eligible. A high temperature with `top_p: 1.0` can wander into strange options because the tail remains available. A moderate temperature with `top_p: 0.9` often gives natural language without letting extremely unlikely tokens through. A low temperature with tight top-p can become so constrained that responses feel repetitive or fail to adapt to legitimate user variation.

| Workload | Recommended top-p | Why this range works | What to watch |
|---|---|---|---|
| Strict extraction | `1.0` with temperature `0.0` | Greedy decoding makes nucleus filtering irrelevant | Validate schema anyway |
| Code generation | `0.4-0.7` | Keeps token choices focused on common syntax patterns | May overfit to common boilerplate |
| Support chat | `0.8-0.95` | Allows natural wording while removing extreme tail tokens | Still needs grounding and policy checks |
| Creative drafting | `0.9-0.98` | Preserves a broad set of plausible continuations | Can drift if the prompt is weak |
| Brainstorming | `0.9-1.0` | Maximizes variety for low-stakes idea generation | Needs ranking or human selection afterward |

A common misunderstanding is that `top_p: 0.9` means "choose the top ninety percent of tokens." It does not. It means "choose the smallest set of tokens whose probability mass reaches ninety percent." If the top token alone has probability `0.95`, the nucleus may contain only that token. If many tokens each have similar probability, the nucleus may contain many candidates. That dynamic behavior is why top-p is usually a better default than a fixed top-k value.

## Min-p: Confidence-Scaled Dynamic Truncation

Top-p removes the long tail using cumulative probability, but its cutoff does not always track how confident the model is on a given step. [Min-p sampling scales the truncation threshold from the probability of the top token, keeping more candidates when the model is uncertain and tightening the pool when the top token is already very likely.](https://arxiv.org/abs/2407.01082) The idea is durable even when benchmark results are debated: dynamic filters should react to confidence, not only to rank or fixed mass cutoffs.

```ascii
Same step, two different confidence levels

Confident step (top token probability = 0.82)
  min-p keeps tokens with p >= 0.82 * min_p_value
  Result: small candidate set, conservative continuation

Uncertain step (top token probability = 0.21)
  min-p keeps tokens with p >= 0.21 * min_p_value
  Result: broader candidate set, more room to explore
```

Min-p is especially relevant when teams raise temperature for creative workloads but still want guardrails against absurd tail tokens. A high temperature flattens the distribution; min-p can still discard tokens whose absolute probability is tiny relative to the current leader. That combination is not a license to skip prompt design, and follow-up work has argued that min-p does not universally beat well-tuned top-p on every benchmark. Treat min-p as another engineering control to test on your workload rather than as a universal upgrade.

| Setting | Behavior | Best fit | What to watch |
|---|---|---|---|
| min-p disabled | Only temperature/top-p/top-k apply | Baseline comparisons | May miss an easy win on creative tasks |
| min-p `0.05-0.10` | Mild confidence scaling | Chat and drafting at moderate temperature | Validate against your own eval set |
| min-p `0.10-0.20` | Stronger tail removal on confident steps | Creative generation with safety filters | Can feel constrained if prompts are already narrow |

When you evaluate min-p against top-p, change one variable at a time and measure the failure modes you care about: repetition, hallucinated detail, malformed structure, latency, and user satisfaction. Sampling research moves quickly; the durable lesson is to compare decoders with task-specific metrics instead of assuming a newly published method replaces every existing profile.

## Top-k: Static Filtering and Its Trade-Offs

[Top-k sampling keeps exactly the `k` most probable tokens and removes the rest.](https://huggingface.co/docs/transformers/v4.22.2/main_classes/text_generation) If `top_k` is `5`, the sampler can choose only among the five highest-ranked candidates, regardless of their absolute probabilities. This is easy to reason about, and it can be useful in local model stacks or research settings where a fixed candidate budget is desirable. The weakness is that the same `k` can be too broad when the model is confident and too narrow when the model is uncertain.

```ascii
Clear-step distribution with top_k = 5
+-------------+-------------+-------------------------------+
| Token       | Probability | Decision                      |
+-------------+-------------+-------------------------------+
| pass        | 0.82        | kept                          |
| fail        | 0.08        | kept                          |
| skip        | 0.03        | kept                          |
| retry       | 0.02        | kept                          |
| timeout     | 0.01        | kept                          |
| unrelated   | 0.004       | discarded                     |
+-------------+-------------+-------------------------------+
```

In the clear distribution above, keeping five tokens may already be too generous because the model strongly prefers one answer. A top-p filter might keep only `pass` and perhaps `fail`, while top-k keeps weaker alternatives merely because they happen to be ranked near the top. In a different step where twelve candidates are genuinely close, `top_k: 5` might discard useful options too early. Static filtering cannot adapt to confidence.

You should avoid combining top-p and top-k unless the provider documentation explicitly defines the order and you have a reason to need both. Some systems apply top-k first, then top-p. Others apply nucleus filtering first, then cap the result. That implementation detail changes the candidate pool, which means the same numbers can behave differently across backends. For most application work, choose top-p as the primary filter and leave top-k unset or neutral.

| Filter | Candidate set size | Strength | Weakness |
|---|---|---|---|
| Greedy | One token | Maximum repeatability | No diversity |
| Top-p | Dynamic by probability mass | Adapts to model confidence | Less intuitive to inspect manually |
| Top-k | Fixed by rank | Simple and predictable candidate count | Can include weak tokens or exclude plausible ones |
| Temperature only | Entire vocabulary remains possible | Simple diversity control | Low-probability tail remains available |
| Beam search | Multiple high-probability paths | Useful for translation-like tasks | Often dull for open-ended generation |

## Repetition Penalties and Degeneration

Autoregressive generation can fall into repeated phrases because the model keeps conditioning on its own previous text. If a phrase has just appeared several times, the context makes it locally probable to appear again. This failure mode is sometimes called degeneration: the output remains grammatical but becomes unhelpfully repetitive. Long-form responses, brainstorming lists, and generic explanations are especially vulnerable because the model can loop on high-level phrases that sound plausible.

```ascii
Without a repetition penalty
+------------------------------------------------------------+
| The platform should be scalable. The platform should be    |
| scalable because the platform should be scalable. The       |
| platform should be scalable for future growth.             |
+------------------------------------------------------------+

With a moderate repetition penalty
+------------------------------------------------------------+
| The platform should scale horizontally, recover from node   |
| loss, and expose capacity signals before traffic spikes.   |
+------------------------------------------------------------+
```

A repetition penalty reduces the probability of tokens that have already appeared. The exact implementation varies, but the engineering intent is consistent: make repeated tokens less attractive so the sampler explores nearby alternatives. A mild value such as `1.05` or `1.1` can help a chatbot avoid stale wording. A stronger value such as `1.2` or `1.3` can help longer creative responses, but excessive penalties make text sound forced because the model avoids natural repeated function words and domain terms.

Repetition penalties are not a substitute for a good prompt structure. If you ask for "ten unique ideas" but do not require categories, constraints, or evaluation criteria, the model may still repeat themes using different words. Penalties operate at the token level, while conceptual diversity often requires task design. For serious ideation workflows, combine a moderate repetition penalty with explicit diversity requirements such as "one operational idea, one security idea, one cost idea, and one developer-experience idea."

| Repetition setting | Likely behavior | Suitable workload | Risk |
|---|---|---|---|
| `1.0` | No penalty | Short structured output, code, exact terminology | Long text may loop |
| `1.05-1.1` | Gentle discouragement | Chat, summaries, support responses | May not fix severe loops |
| `1.15-1.3` | Stronger vocabulary pressure | Long drafting, brainstorming, story generation | Can sound unnatural |
| `>1.3` | Aggressive avoidance | Rare rescue setting for loop-heavy local models | May damage coherence and terminology |

A senior-level debugging habit is to distinguish repetition caused by decoding from repetition caused by content design. If the model repeats the same phrase after several hundred tokens, a repetition penalty and shorter sections may help. If it repeats the same idea across list items, the prompt likely lacks distinct axes for comparison. If it repeats boilerplate at the start of every answer, the system prompt or examples may be teaching the model that preamble is required.

## Constrained and Structured Decoding

Prompt-only JSON instructions fail often because language models can still emit prefaces, markdown fences, or partially valid objects. Constrained decoding pushes the reliability boundary closer to the model by restricting which tokens remain legal at each step. [Grammar-based and schema-guided approaches compile a machine-readable constraint, then mask illegal tokens before sampling occurs.](https://dottxt-ai.github.io/outlines/latest/) The durable concept is separate from any one library: you are no longer hoping the model chooses the right format; you are enforcing it during generation.

```text
Prompt-only structured output
  Model may emit: "Here is the JSON:" + object + trailing commentary
  Downstream parser: fragile

Constrained structured output
  Step 1 legal tokens: '{'
  Step 2 legal tokens: '"service"' or other schema keys
  Step 3 legal tokens: ':' then string/value tokens allowed by schema
  Downstream parser: still validate, but fewer surprise prefixes
```

Structured output appears under several names across providers and runtimes: JSON schema mode, grammar-constrained generation, guided decoding, or response-format objects. The names change faster than the idea. The idea is that machine-consumed outputs deserve a hard boundary, while human-consumed prose usually deserves softer sampling controls plus grounding and review.

| Approach | Mechanism | Strength | Weakness |
|---|---|---|---|
| Prompt-only formatting | Instructions and examples | Easy to ship | Frequent invalid or wrapped output |
| Stop sequences and regex cleanup | Post-hoc trimming | Cheap incremental guardrail | Cannot guarantee full validity |
| Schema or grammar constraints | Token masking during decoding | Strong format compliance | Requires runtime support and testing |
| External validator plus repair loop | Parse, reject, retry | Works on any provider | Adds latency and cost |

Use constrained decoding when a parser, workflow engine, or database import consumes the answer. Keep sampling conservative even with constraints, because constraints limit format, not factuality. A schema can force valid JSON while still allowing `"refundApproved": true` when the source document never authorized a refund. Pair structured decoding with retrieval grounding, field-level validation, and audit logging.

> **Landscape snapshot — as of 2026-06. This changes fast; verify against vendor docs before relying on specifics.**
>
> | Capability | Where it commonly appears | Engineering note |
> |---|---|---|
> | JSON schema response format | Hosted chat/completions APIs | Good for extraction endpoints; verify exact schema support in current API docs |
> | Guided/grammar decoding | Local inference runtimes and specialized libraries | Useful when you control the serving stack |
> | Regex or CFG constraints | Research-oriented decoding toolkits | Powerful for narrow formats; test edge cases carefully |
>
> Treat this table as a lookup aid, not a product recommendation. Capability names and availability change frequently across providers.

Hypothetical scenario: An incident automation service asks for `{ "severity": "high", "service": "checkout" }` but receives markdown with a code fence. Moving from prompt-only instructions to schema-constrained decoding removes the fence problem, yet the team still needs source validation because the severity value can remain wrong even when the JSON is syntactically perfect.

## Length Limits, Stop Sequences, and Cost Control

Length control is a reliability feature, not only a billing feature. Every production generation should have an explicit `max_tokens` limit based on the expected output, the downstream consumer, and the acceptable latency budget. Without a limit, a model can continue until it reaches a provider cap, burns unnecessary tokens, or produces text that the user never needed. A strict limit also forces the application designer to decide what "done" looks like.

Stop sequences give the model a semantic boundary. A few-shot prompt might show several examples separated by `###`, and the model may continue writing additional examples unless a stop sequence tells it where the target answer ends. Structured output often benefits from a sentinel such as `END_JSON` or an instruction to stop after a closing delimiter. Stop sequences are especially useful when the output will be embedded into another file, sent to a parser, or shown in a UI with limited space.

```python
SUMMARY_PROFILE = {
    "temperature": 0.3,
    "top_p": 0.7,
    "max_tokens": 220,
    "stop_sequences": ["\n\n###", "\n\nSource:"],
}
```

The example above is designed for a factual summary rather than a creative answer. Low temperature keeps the response close to the source, top-p removes low-probability wording, and `max_tokens` bounds cost and latency. The stop sequences prevent the model from drifting into another prompt section or inventing a source list. Notice that none of these settings proves the summary is accurate. They reduce decoding risk, while citation checks, source comparison, and application tests address factual risk.

A common production pattern is to set a conservative model output limit and then validate the result. If the output is incomplete, malformed, or fails schema validation, the application can retry with a repair prompt or a larger limit. Blindly raising `max_tokens` for every request is a poor fix because it increases cost for successful cases and may hide prompt design problems. Treat length as part of the contract between the model and the application.

## Worked Example: Diagnosing a Broken Extraction Flow

A team uses an LLM to extract incident metadata from support messages. The downstream system expects a JSON object with `service`, `environment`, `severity`, and `summary`. During testing, the model sometimes returns valid JSON, but other times it writes a sentence before the object or appends an explanation afterward. The current profile is `temperature: 0.7`, `top_p: 0.9`, `max_tokens: 1000`, and no stop sequence. The prompt asks the model to "extract the details and explain any uncertainty."

The first diagnosis is that the decoding profile and task contract disagree. A JSON extraction flow does not need conversational variation, and the phrase "explain any uncertainty" invites text outside the object. The profile should be deterministic, the prompt should require only JSON, and the output should be validated. A stop sequence can help, but schema validation is the stronger boundary because a stop sequence alone cannot guarantee that all required keys exist.

```python
BROKEN_EXTRACTION_PROFILE = {
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 1000,
}

FIXED_EXTRACTION_PROFILE = {
    "temperature": 0.0,
    "top_p": 1.0,
    "max_tokens": 240,
    "stop_sequences": ["\n\nEND_JSON"],
}
```

The repaired design also changes the prompt structure. Instead of asking for explanation, it provides a schema and requires the model to put uncertainty into fields such as `"severity": "unknown"` or `"summary": "insufficient information"`. That preserves useful uncertainty while keeping the output parseable. A retry path can ask the model to repair invalid JSON, but the primary path should be strict enough that repair is rare.

```json
{
  "service": "checkout-api",
  "environment": "prod",
  "severity": "high",
  "summary": "Checkout requests are timing out after a new image rollout."
}
```

The senior-level lesson is that sampling parameters are only one layer in a control system. The profile reduces output variance, the prompt defines the contract, the stop sequence bounds the response, and the validator rejects malformed results. If any one layer is missing, the others have to carry too much responsibility. Reliable AI systems usually come from several modest controls working together, not from a single perfect setting.

## Production Profiles by Use Case

The safest way to choose sampling settings is to classify the workload before touching any numbers. Ask whether the output is consumed by a human or a machine, whether diversity is valuable or harmful, whether the answer must cite source material, and how expensive a bad answer would be. These questions turn sampling from guesswork into design. The following profiles are starting points, not universal defaults, and they should be tested against representative prompts.

### Use Case 1: Customer Support Chat

Support chat needs natural language, but it must stay within policy and source material. A moderate temperature can make answers feel less robotic, while top-p filtering removes unlikely tail tokens. The application should still ground answers in retrieved policy text, include refusal behavior for missing information, and log enough metadata for audit. A decoding profile cannot make an unsupported policy true.

```python
SUPPORT_CHAT_PROFILE = {
    "temperature": 0.6,
    "top_p": 0.9,
    "repetition_penalty": 1.05,
    "max_tokens": 500,
    "stop_sequences": ["\nUser:", "\nHuman:"],
}
```

### Use Case 2: Code Generation

Code generation rewards consistency, syntax discipline, and common patterns. A low temperature helps the model choose conventional tokens, while a tight top-p prevents unnecessary exploration. Repetition penalties should usually remain neutral or mild because code legitimately repeats identifiers, indentation, keywords, and structural markers. The stronger reliability boundary is compilation, unit tests, static analysis, and review.

```python
CODE_GENERATION_PROFILE = {
    "temperature": 0.2,
    "top_p": 0.5,
    "repetition_penalty": 1.0,
    "max_tokens": 1200,
    "stop_sequences": ["\n```", "\n# End"],
}
```

### Use Case 3: Creative Story Writing

Creative writing benefits from a wider candidate pool because the user often wants surprise, texture, and varied phrasing. A temperature near `1.0` with a broad nucleus allows richer continuations while still filtering the most unlikely tail. A moderate repetition penalty helps avoid repeated sentence openings and recycled imagery. The application should give the user editing tools rather than pretending every generated draft is final.

```python
CREATIVE_WRITING_PROFILE = {
    "temperature": 1.0,
    "top_p": 0.95,
    "repetition_penalty": 1.2,
    "max_tokens": 1800,
    "stop_sequences": ["\n\n###"],
}
```

### Use Case 4: JSON Data Extraction

JSON extraction is a machine-consumed workflow, so the decoding profile should prioritize validity and repeatability. Use zero temperature, a neutral top-p, a tight token budget, and a clear stop boundary. The application should parse the output with a real JSON parser and reject or repair invalid results. If the provider supports native structured output or schema-constrained decoding, use that before relying on prompt-only formatting.

```python
JSON_EXTRACTION_PROFILE = {
    "temperature": 0.0,
    "top_p": 1.0,
    "repetition_penalty": 1.0,
    "max_tokens": 300,
    "stop_sequences": ["\n\nEND_JSON"],
}
```

### Use Case 5: Brainstorming Ideas

Brainstorming is one of the few places where higher variance is often desirable. The goal is not to produce a single correct answer; it is to generate a candidate set that a human or ranking step can evaluate. A higher temperature and broad top-p can surface less obvious ideas, while a repetition penalty reduces near-duplicates. You should still ask for categories, constraints, or scoring criteria so the diversity is useful rather than chaotic.

```python
BRAINSTORMING_PROFILE = {
    "temperature": 1.15,
    "top_p": 0.95,
    "repetition_penalty": 1.25,
    "max_tokens": 900,
    "stop_sequences": ["\n\nEND_IDEAS"],
}
```

### Use Case 6: Financial or Incident Summarization

Summaries of high-stakes material should be conservative but readable. Very low temperature can make text rigid, while moderate low temperature gives the model enough flexibility to produce clear sentences. Top-p should be tighter than for chat because unsupported wording can change the meaning of a report. The application should cite sources, preserve uncertainty, and avoid allowing the model to fill gaps with plausible but unverified details.

```python
FACTUAL_SUMMARY_PROFILE = {
    "temperature": 0.3,
    "top_p": 0.7,
    "repetition_penalty": 1.0,
    "max_tokens": 450,
    "stop_sequences": ["\n\nSources:", "\n\nEND_SUMMARY"],
}
```

| Use Case | Temperature | Top-p | Top-k | Repetition | Max Tokens | Primary validation |
|---|---:|---:|---:|---:|---:|---|
| Code generation | `0.2` | `0.5` | unset | `1.0` | `1200` | tests and linters |
| JSON extraction | `0.0` | `1.0` | unset | `1.0` | `300` | JSON schema |
| Support chatbot | `0.6` | `0.9` | unset | `1.05` | `500` | policy grounding |
| Creative writing | `1.0` | `0.95` | unset | `1.2` | `1800` | human editing |
| Brainstorming | `1.15` | `0.95` | unset | `1.25` | `900` | ranking criteria |
| Factual summary | `0.3` | `0.7` | unset | `1.0` | `450` | source comparison |
| Translation-like rewriting | `0.3` | `0.8` | unset | `1.0` | `800` | bilingual review |
| Test fixtures | `0.0` | `1.0` | unset | `1.0` | varies | exact expected output |

## Decision Process for New Workloads

When you face a new workload, do not start by copying a temperature from an example. Start by identifying the consumer of the output. If software consumes the output, favor deterministic decoding and validation. If a human consumes the output and values tone, use moderate sampling with safety filters. If a human consumes the output and values surprise, allow wider sampling but add ranking, editing, or review. The profile should express the cost of variance.

```mermaid
flowchart TD
    A[New generation workload] --> B{Machine-consumed output?}
    B -- Yes --> C[Use low or zero temperature]
    C --> D[Add schema or parser validation]
    D --> E[Set tight max_tokens and stop boundary]
    B -- No --> F{Is novelty a product requirement?}
    F -- No --> G[Use low-moderate temperature and top_p filter]
    G --> H[Ground in source material and test factuality]
    F -- Yes --> I[Use higher temperature with broad top_p]
    I --> J[Add repetition control and human/ranking review]
```

This decision tree deliberately separates generation quality from output validation. A creative brainstorming tool can tolerate weak ideas because the user chooses among them. A compliance assistant cannot tolerate creative policy interpretation because users may act on the response. A code assistant sits between the two: some variation is helpful, but executable validation is mandatory. Sampling strategy should match the consequences of a bad token, not the personality you wish the model had.

There is also a latency and cost dimension. Larger `max_tokens` increases the worst-case response time and price. Wider sampling can sometimes produce longer, more meandering answers because the model explores less direct paths. Strong stop sequences and concise prompt contracts keep the output bounded. In high-throughput systems, sampling profiles should be part of capacity planning, not hidden constants buried in application code.

## Diagnosing Decoding Failures in Production

When generated text looks wrong, resist the urge to change random parameters until something "looks better." Diagnose by tracing the decoding configuration against the symptom. Repeated phrases usually point to missing repetition control, overly long generation, or weak section structure in the prompt. Malformed structured output usually means the task is machine-consumed but the profile still allows conversational variation. Dull brainstorming output often means temperature, top-p, or min-p are too conservative for a novelty-seeking workload. Runaway generation usually means missing `max_tokens`, weak stop boundaries, or a repair loop that keeps extending incomplete answers. Incoherent high-variance text often means high temperature with insufficient tail filtering.

```text
Symptom -> first decoding checks

Repeated phrase loop     -> repetition_penalty, max_tokens, prompt section design
JSON wrapped in prose    -> temperature 0.0, constrained decoding, parser validation
Over-creative support    -> lower temperature, tighten top_p/min_p, add grounding
Identical beam outputs   -> reduce beam width or switch to sampling for open text
Runaway cost             -> max_tokens, stop sequences, retry only on failure
```

Logging the full decoding profile alongside prompts and outputs makes these diagnoses possible weeks later during an incident review. At minimum, record temperature, top-p, top-k, min-p, repetition penalty, max tokens, stop sequences, beam width, seed or deterministic mode, and whether structured decoding was enabled. Without that metadata, teams re-tune by folklore and rediscover the same failure twice.

## Evaluating Trade-offs Between Determinism and Experience

Selecting generation parameters is an evaluation problem, not a defaults problem. Determinism improves testability, parser reliability, and auditability, but it can make customer-facing language feel stiff. Diversity improves brainstorming, phrasing adaptation, and exploration, but it increases the risk of unsupported detail and parser breakage. Cost and latency rise with larger token budgets, wider beams, and repair loops that retry generation. Safety and user experience depend on how harmful a wrong token would be in the specific workflow.

| Workload consequence | Favor | De-emphasize | Validation layer |
|---|---|---|---|
| Parser breakage | Zero temperature, constraints | High temperature, wide top-p | Schema or parser tests |
| User trust in policy answers | Grounding, conservative sampling | Creative sampling | Source comparison, refusal rules |
| Ideation sessions | Moderate-high temperature, repetition control | Greedy decoding | Human ranking |
| Offline batch translation | Beam search or low temperature | Unbounded sampling | Reference metrics or bilingual review |
| High QPS API | Tight max_tokens, minimal repair | Wide beams, huge limits | Load tests and cost alarms |

The evaluation habit that separates senior engineers from prompt tweakers is to define the failure mode first, pick the smallest decoding change that addresses it, and measure again on representative prompts. A support bot and a CI YAML generator should not share a "default creative profile" just because both use the same model name.

| Decision question | If yes | If no |
|---|---|---|
| Will a parser consume the output? | Use `temperature: 0.0` and schema validation | Allow moderate natural-language variation |
| Is novelty valuable to the user? | Increase temperature and review/rank outputs | Keep temperature low or moderate |
| Could a wrong detail cause harm? | Tighten top-p, ground in sources, preserve uncertainty | Focus more on user experience |
| Is the output long-form? | Add repetition control and section limits | Keep repetition penalty neutral |
| Does the prompt contain few-shot examples? | Add stop sequences to prevent extra examples | Use normal task-specific boundaries |
| Is cost sensitive? | Lower `max_tokens` and add retry only when needed | Allow room for richer answers |

## Did You Know?

1. Nucleus sampling was popularized by [the 2019 paper "The Curious Case of Neural Text Degeneration,"](https://arxiv.org/abs/1904.09751) which showed that simply maximizing likelihood can produce dull or repetitive text even when the model is strong.

2. A zero-temperature setting is best understood as a decoding choice, not as a universal reproducibility guarantee, because provider infrastructure, model versions, safety layers, and tool routing can still change behavior.

3. Repetition problems often become visible only after several hundred generated tokens, which is why short demos can look healthy while long-form production responses still degrade.

4. Native structured-output features, when available, are usually stronger than prompt-only JSON instructions because they constrain the generation or validate the result closer to the model boundary.

## Common Mistakes

| Mistake | Why it fails | Practical fix |
|---|---|---|
| Using chat defaults for structured extraction | General chat defaults usually allow wording variation, prefaces, and explanations that break parsers. | Use `temperature: 0.0`, a strict prompt contract, a stop boundary, and schema validation. |
| Treating temperature as a truthfulness control | Lower temperature reduces variance, but it does not add missing evidence or correct bad context. | Pair conservative decoding with retrieval grounding, refusal behavior, and factual checks. |
| Combining top-p and top-k without a documented reason | Different backends may apply the filters in different orders, changing the candidate pool. | Prefer top-p alone unless the provider documents the combined behavior and you test it. |
| Setting high temperature for code or YAML | Extra variation can introduce invalid syntax, unexpected comments, or conversational filler. | Use low temperature, tight top-p, and validate with compilers, parsers, linters, or tests. |
| Omitting `max_tokens` in production | Runaway generation increases cost, latency, and the chance of irrelevant trailing text. | Set a limit based on the expected output and add a repair path for incomplete results. |
| Overusing repetition penalties | Strong penalties can make normal terminology, identifiers, and function words look artificially avoided. | Start mild for prose, keep code mostly neutral, and inspect output quality before raising it. |
| Solving conceptual duplication with token penalties | Repetition penalties reduce token reuse but do not guarantee diverse ideas or distinct categories. | Add prompt constraints that require different angles, audiences, risks, or evaluation criteria. |
| Forgetting stop sequences in few-shot prompts | The model may continue the pattern and generate extra examples instead of stopping at the answer. | Add a delimiter or sentinel that marks the end of the target response. |

## Quiz

**1. Your team deploys an LLM that extracts Kubernetes incident fields into JSON for an automated ticket router. The router fails because the model sometimes writes `Here is the JSON:` before the object, although the fields themselves are usually correct. Which change should you make first?**

- A) Increase temperature so the model can find a better phrasing.
- B) Set temperature to `0.0`, require JSON only, add a stop boundary, and validate with a JSON parser.
- C) Increase `max_tokens` so the model has enough room to finish the explanation.
- D) Add a high repetition penalty so the preface appears less often.

<details>
<summary>Answer</summary>

**Correct answer: B.** The failure is not that the model lacks enough space or needs more variety; the failure is that a machine-consumed workflow is using a profile that allows conversational text. A deterministic profile, strict output contract, stop boundary, and parser validation align the decoding behavior with the downstream consumer.
</details>

**2. A product team wants an assistant to propose unusual internal hackathon themes. The current profile uses `temperature: 0.2`, `top_p: 0.5`, and no repetition penalty. Users say every idea sounds like a generic productivity workshop. What adjustment best matches the workload?**

- A) Raise temperature near `1.1`, use broad top-p such as `0.95`, and add a moderate repetition penalty.
- B) Lower temperature to `0.0` so the model consistently selects the best theme.
- C) Set top-k to `1` so the output becomes more focused.
- D) Reduce `max_tokens` so the model cannot repeat itself.

<details>
<summary>Answer</summary>

**Correct answer: A.** Brainstorming is a novelty-seeking workload, so the profile should allow more varied candidates while still filtering the extreme tail. A moderate repetition penalty helps reduce near-duplicate ideas, while lowering temperature or top-k would make the output even more predictable.
</details>

**3. A support chatbot must sound natural, but it keeps inventing unusual phrases and occasionally drifts away from the retrieved policy. The current profile is `temperature: 1.2`, `top_p: 1.0`, and `max_tokens: 900`. Which diagnosis is most accurate?**

- A) The model needs a larger token budget to explain the policy fully.
- B) The sampler is too deterministic and cannot adapt to customer wording.
- C) High temperature plus no nucleus filtering leaves too much low-probability tail available.
- D) A repetition penalty is impossible to use in customer support.

<details>
<summary>Answer</summary>

**Correct answer: C.** The profile encourages exploratory token choices and does not filter the long tail, which increases the risk of strange wording and drift. A support chatbot usually needs moderate temperature, top-p filtering, grounding, and policy validation rather than maximum variation.
</details>

**4. A developer uses `top_p: 0.95` and `top_k: 10` in a local inference stack. After a framework upgrade, output diversity changes even though the numbers are identical. What is the most likely cause and fix?**

- A) The model forgot previous conversations, so increase context length.
- B) The framework may apply top-p and top-k in a different order, so simplify to one filtering strategy unless both are explicitly required.
- C) The temperature must be exactly `1.0` whenever top-p is enabled.
- D) The stop sequence is too short, so remove it.

<details>
<summary>Answer</summary>

**Correct answer: B.** Combining filtering strategies can make behavior depend on implementation order. If one version applies top-k before top-p and another applies top-p before top-k, the eligible candidate pool changes, so the standard fix is to choose the primary filter and test it directly.
</details>

**5. To diagnose repeated phrases in long-form output, you inspect logs and see moderate temperature, top-p filtering, and no repetition penalty in the decoding configuration. What should you try first, and what else should you inspect?**

- A) Add a mild repetition penalty and inspect whether the prompt asks for distinct sections with different purposes.
- B) Set temperature to `0.0` and remove all section headings.
- C) Increase `max_tokens` because the model is running out of space.
- D) Disable top-p so the model can use every token in the vocabulary.

<details>
<summary>Answer</summary>

**Correct answer: A.** The symptom fits degeneration in long-form generation, so a mild repetition penalty can help. You should also inspect the prompt because conceptual repetition often means the task lacks distinct axes, not merely that the sampler reused tokens.
</details>

**6. A CI assistant generates YAML manifests. The YAML is usually correct, but one out of several runs includes a comment explaining the manifest, which breaks a strict downstream comparison test. Which profile best fits this use case?**

- A) `temperature: 0.8`, `top_p: 0.9`, `max_tokens: 1000`
- B) `temperature: 1.0`, `top_p: 1.0`, `repetition_penalty: 1.2`
- C) `temperature: 0.0`, neutral top-p, clear stop sequence, and YAML parser validation
- D) `temperature: 1.2`, top-k set to `50`, and no stop sequence

<details>
<summary>Answer</summary>

**Correct answer: C.** YAML for CI is machine-consumed and exactness matters. The profile should reduce variance, define a stopping boundary, and rely on parser validation rather than hoping the model chooses not to add explanatory text.
</details>

**7. When you evaluate the trade-offs between determinism and readability for a financial analyst summary tool, the current profile uses `temperature: 0.0` and produces accurate but awkward sentence fragments. Stakeholders want readable summaries without creative interpretation of the source. Which adjustment is most reasonable?**

- A) Move to `temperature: 1.5` so the model can write more naturally.
- B) Use a low nonzero temperature such as `0.3`, pair it with tighter top-p, and keep source validation.
- C) Remove `max_tokens` so the model can decide how much explanation is needed.
- D) Add a very high repetition penalty so every sentence is unique.

<details>
<summary>Answer</summary>

**Correct answer: B.** The workload needs readability but remains high-stakes and source-bound. A low nonzero temperature with constrained top-p can improve fluency while preserving conservative behavior, but factual validation and source comparison still carry the accuracy requirement.
</details>

## Hands-On Exercise

Build a local Python sampling playground that shows how temperature, top-p, top-k, repetition penalties, and token limits change generated text. This lab does not call a hosted model API, so you can focus on decoding mechanics without credentials or network access. You will implement a tiny token-transition model, run several profiles, and reason from observed behavior back to production settings.

### Task 1: Bootstrap the Lab Environment

Create an isolated directory and virtual environment before writing any code. Using an explicit interpreter path keeps later commands reproducible across shells and CI snippets.

```bash
mkdir -p sampling-strategies-lab
cd sampling-strategies-lab
python3 -m venv .venv
.venv/bin/python --version
```

### Task 2: Create the Sampling Playground Script

Save the script below as `sampling_lab.py`. It implements greedy decoding, temperature scaling, top-k, top-p, repetition penalties, and preset profiles you will compare in later tasks.

```bash
cat > sampling_lab.py <<'PY'
import argparse
import math
import random
from collections import Counter

TRANSITIONS = {
    "<START>": {
        "JSON": 0.28,
        "Chat": 0.24,
        "Code": 0.22,
        "Creative": 0.16,
        "Unusual": 0.10,
    },
    "JSON": {"extraction": 0.68, "format": 0.20, "story": 0.04, "bananas": 0.01},
    "Chat": {"answers": 0.42, "support": 0.32, "rambles": 0.08, "sparkles": 0.02},
    "Code": {"generation": 0.52, "syntax": 0.30, "poetry": 0.05, "mist": 0.01},
    "Creative": {"drafts": 0.38, "ideas": 0.34, "twists": 0.20, "static": 0.03},
    "Unusual": {"ideas": 0.44, "phrases": 0.30, "detours": 0.18, "noise": 0.04},
    "extraction": {"needs": 0.70, "prefers": 0.20, "wanders": 0.02},
    "format": {"needs": 0.62, "prefers": 0.28, "wanders": 0.02},
    "answers": {"need": 0.46, "balance": 0.34, "repeat": 0.10},
    "support": {"needs": 0.44, "balance": 0.36, "repeat": 0.10},
    "generation": {"needs": 0.58, "prefers": 0.24, "repeat": 0.08},
    "syntax": {"needs": 0.60, "prefers": 0.22, "repeat": 0.08},
    "drafts": {"benefit": 0.44, "need": 0.26, "repeat": 0.18},
    "ideas": {"benefit": 0.40, "need": 0.28, "repeat": 0.20},
    "twists": {"benefit": 0.44, "need": 0.24, "repeat": 0.20},
    "phrases": {"benefit": 0.34, "repeat": 0.30, "drift": 0.18},
    "detours": {"drift": 0.40, "repeat": 0.24, "benefit": 0.18},
    "needs": {"strict": 0.44, "clear": 0.32, "repeat": 0.18},
    "need": {"moderate": 0.40, "clear": 0.30, "repeat": 0.20},
    "prefers": {"low": 0.48, "focused": 0.34, "repeat": 0.12},
    "balance": {"controlled": 0.44, "natural": 0.34, "repeat": 0.14},
    "benefit": {"from": 0.55, "with": 0.25, "repeat": 0.14},
    "from": {"variety": 0.44, "novelty": 0.32, "repeat": 0.16},
    "with": {"filters": 0.50, "limits": 0.28, "repeat": 0.14},
    "strict": {"decoding": 0.70, "schemas": 0.20, "repeat": 0.05},
    "clear": {"limits": 0.42, "validation": 0.36, "repeat": 0.14},
    "moderate": {"temperature": 0.54, "filtering": 0.28, "repeat": 0.12},
    "low": {"temperature": 0.62, "variance": 0.20, "repeat": 0.10},
    "focused": {"sampling": 0.56, "tokens": 0.24, "repeat": 0.12},
    "controlled": {"randomness": 0.56, "language": 0.24, "repeat": 0.12},
    "natural": {"language": 0.54, "answers": 0.24, "repeat": 0.14},
    "variety": {"helps": 0.52, "matters": 0.28, "repeat": 0.12},
    "novelty": {"helps": 0.52, "matters": 0.28, "repeat": 0.12},
    "filters": {"remove": 0.52, "limit": 0.28, "repeat": 0.12},
    "limits": {"control": 0.52, "protect": 0.28, "repeat": 0.12},
    "decoding": {".": 1.0},
    "schemas": {".": 1.0},
    "validation": {".": 1.0},
    "temperature": {".": 1.0},
    "filtering": {".": 1.0},
    "variance": {".": 1.0},
    "sampling": {".": 1.0},
    "tokens": {".": 1.0},
    "randomness": {".": 1.0},
    "language": {".": 1.0},
    "helps": {".": 1.0},
    "matters": {".": 1.0},
    "remove": {"tail": 0.70, "noise": 0.20, "repeat": 0.05},
    "limit": {"tail": 0.60, "noise": 0.25, "repeat": 0.08},
    "control": {"cost": 0.60, "length": 0.25, "repeat": 0.08},
    "protect": {"cost": 0.55, "parsers": 0.30, "repeat": 0.08},
    "tail": {".": 1.0},
    "noise": {".": 1.0},
    "cost": {".": 1.0},
    "length": {".": 1.0},
    "parsers": {".": 1.0},
    "repeat": {"repeat": 0.70, "repeat.": 0.30},
    "repeat.": {".": 1.0},
    "wanders": {"noise": 0.50, "drift": 0.30, "repeat": 0.10},
    "rambles": {"noise": 0.50, "drift": 0.30, "repeat": 0.10},
    "sparkles": {"noise": 0.50, "drift": 0.30, "repeat": 0.10},
    "poetry": {"noise": 0.50, "drift": 0.30, "repeat": 0.10},
    "mist": {"noise": 0.50, "drift": 0.30, "repeat": 0.10},
    "static": {"noise": 0.50, "drift": 0.30, "repeat": 0.10},
    "drift": {".": 1.0},
    "bananas": {"noise": 1.0},
}

PRESETS = {
    "deterministic_json": {
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 0,
        "repetition_penalty": 1.0,
        "max_tokens": 9,
        "seed": 11,
    },
    "balanced_chat": {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 0,
        "repetition_penalty": 1.05,
        "max_tokens": 11,
        "seed": 11,
    },
    "creative_brainstorm": {
        "temperature": 1.1,
        "top_p": 0.95,
        "top_k": 0,
        "repetition_penalty": 1.2,
        "max_tokens": 13,
        "seed": 11,
    },
    "loop_prone": {
        "temperature": 0.8,
        "top_p": 1.0,
        "top_k": 0,
        "repetition_penalty": 1.0,
        "max_tokens": 12,
        "seed": 5,
    },
    "loop_resistant": {
        "temperature": 0.8,
        "top_p": 1.0,
        "top_k": 0,
        "repetition_penalty": 1.3,
        "max_tokens": 12,
        "seed": 5,
    },
    "code_generation": {
        "temperature": 0.2,
        "top_p": 0.5,
        "top_k": 0,
        "repetition_penalty": 1.0,
        "max_tokens": 9,
        "seed": 17,
    },
}

def normalize(probs):
    total = sum(probs.values())
    if total <= 0:
        raise ValueError("probabilities must sum to a positive value")
    return {token: value / total for token, value in probs.items()}

def apply_repetition_penalty(probs, counts, penalty):
    if penalty <= 1.0:
        return probs
    adjusted = {}
    for token, value in probs.items():
        adjusted[token] = value / (penalty ** counts[token])
    return normalize(adjusted)

def apply_temperature(probs, temperature):
    if temperature == 0.0:
        best = max(probs, key=probs.get)
        return {best: 1.0}
    adjusted = {}
    for token, value in probs.items():
        adjusted[token] = math.pow(value, 1.0 / temperature)
    return normalize(adjusted)

def apply_top_k(probs, top_k):
    if top_k <= 0:
        return probs
    kept = dict(sorted(probs.items(), key=lambda item: item[1], reverse=True)[:top_k])
    return normalize(kept)

def apply_top_p(probs, top_p):
    if top_p >= 1.0:
        return probs
    ranked = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    kept = {}
    cumulative = 0.0
    for token, value in ranked:
        kept[token] = value
        cumulative += value
        if cumulative >= top_p:
            break
    return normalize(kept)

def sample_token(probs, rng):
    tokens = list(probs)
    weights = [probs[token] for token in tokens]
    return rng.choices(tokens, weights=weights, k=1)[0]

def generate(preset_name):
    cfg = PRESETS[preset_name]
    rng = random.Random(cfg["seed"])
    counts = Counter()
    current = "<START>"
    output = []

    for _ in range(cfg["max_tokens"]):
        base = TRANSITIONS.get(current, {".": 1.0})
        probs = apply_repetition_penalty(base, counts, cfg["repetition_penalty"])
        probs = apply_temperature(probs, cfg["temperature"])
        probs = apply_top_k(probs, cfg["top_k"])
        probs = apply_top_p(probs, cfg["top_p"])
        token = sample_token(probs, rng)
        if token == ".":
            output.append(token)
            break
        output.append(token)
        counts[token] += 1
        current = token

    text = " ".join(output).replace(" .", ".")
    return cfg, text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", required=True, choices=sorted(PRESETS))
    args = parser.parse_args()
    cfg, text = generate(args.preset)
    print(f"Preset: {args.preset}")
    print("Config:")
    for key, value in cfg.items():
        print(f"  {key}: {value}")
    print("Output:")
    print(text)

if __name__ == "__main__":
    main()
PY
```

### Task 3: Compare Deterministic and Conversational Profiles

Run the deterministic preset twice, then run the balanced chat preset once. Record how temperature and top-p change the path through the toy vocabulary.

```bash
.venv/bin/python sampling_lab.py --preset deterministic_json
.venv/bin/python sampling_lab.py --preset deterministic_json
.venv/bin/python sampling_lab.py --preset balanced_chat
```

### Task 4: Observe Repetition Penalties

Compare the loop-prone and loop-resistant presets using the same seed so the difference comes from decoding controls rather than randomness alone.

```bash
.venv/bin/python sampling_lab.py --preset loop_prone
.venv/bin/python sampling_lab.py --preset loop_resistant
```

Write one paragraph explaining whether the repetition penalty changed token-level loops and whether it could guarantee conceptual diversity across brainstorming bullets.

### Task 5: Compare Code and Creative Profiles

Run the code-generation preset alongside the creative brainstorming preset and note how tighter top-p changes the selected path.

```bash
.venv/bin/python sampling_lab.py --preset code_generation
.venv/bin/python sampling_lab.py --preset creative_brainstorm
```

### Task 6: Experiment with Top-k Versus Top-p

Temporarily set `top_k: 3` in the `balanced_chat` preset inside `sampling_lab.py`, rerun the preset, and explain how fixed-rank filtering differs from nucleus filtering in your notes.

```bash
grep -n "balanced_chat" -A8 sampling_lab.py
.venv/bin/python sampling_lab.py --preset balanced_chat
```

### Task 7: Map Profiles to Production Workloads

Capture four short recommendations in a notes file or commit message so you can reuse them when designing real services.

```bash
printf '%s\n' \
'JSON extraction: temperature 0.0, neutral top_p, schema validation, tight max_tokens.' \
'Support chat: moderate temperature, top_p filtering, grounding, policy checks.' \
'Code generation: low temperature, tight top_p, tests and linters.' \
'Brainstorming: higher temperature, broad top_p, repetition control, human ranking.' \
> sampling-profile-notes.txt
cat sampling-profile-notes.txt
```

### Success Criteria

- [ ] The lab directory contains `.venv/bin/python` and a runnable `sampling_lab.py` script.
- [ ] You can compare greedy decoding, temperature sampling, nucleus (top-p) sampling, top-k filtering, repetition penalties, and stopping controls across the presets you executed (beam search, min-p, and constrained decoding are covered in the module theory rather than in the lab presets).
- [ ] Running `deterministic_json` twice with the same seed produces identical output text.
- [ ] The balanced chat preset shows moderate temperature and top-p filtering in its printed configuration.
- [ ] You can explain why top-p dynamically adapts while top-k uses a fixed rank cutoff.
- [ ] You can diagnose repeated phrases and runaway generation by tracing the decoding configuration for each preset you run.
- [ ] You can evaluate the trade-offs between determinism, diversity, cost, latency, and user experience when choosing a profile.
- [ ] You can design distinct sampling profiles for structured extraction, support chat, code generation, and brainstorming.
- [ ] You can name the validation layer that must accompany each production profile rather than treating decoding settings as sufficient on their own.

## Learner check

> Sampling strategy is the engineering control surface that turns next-token probabilities into text. Choose deterministic or constrained decoding when software consumes the output, moderate filtered sampling when humans need natural language, and wider sampling plus review when novelty is the product requirement.

## Next Module

Next module: [Embeddings & Semantic Search](../module-1.4-embeddings-semantic-search/)

Sampling parameters control how a model turns probabilities into generated text, but embeddings solve a different problem: how systems represent meaning so similar content can be found, compared, clustered, and retrieved. In the next module, you will learn how text becomes vectors, why semantic similarity powers retrieval-augmented generation, and how embedding quality affects the context that a generator receives before sampling ever begins.

## Sources

- [The Curious Case of Neural Text Degeneration](https://arxiv.org/abs/1904.09751) — Primary paper for nucleus sampling, degeneration under maximization, and the motivation for sampling-based decoding.
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — Foundational sequence-generation reference that established beam search as a standard decoding strategy in neural text generation.
- [Turning Up the Heat: Min-p Sampling for Creative and Coherent LLM Outputs](https://arxiv.org/abs/2407.01082) — Introduces min-p sampling, which scales truncation thresholds from top-token confidence at each decoding step.
- [Min-p, Max Exaggeration: A Critical Analysis of Min-p Sampling in Language Models](https://arxiv.org/abs/2506.13681) — Independent re-analysis useful for evaluating min-p claims against tuned top-p baselines.
- [Hugging Face Transformers: Generation Strategies](https://huggingface.co/docs/transformers/en/generation_strategies) — Practical overview of greedy decoding, beam search, sampling, and current generation terminology.
- [Hugging Face Transformers: LLM Tutorial](https://huggingface.co/docs/transformers/v4.45.1/llm_tutorial) — Explains autoregressive generation as repeated next-token selection until a stop condition is reached.
- [Hugging Face Transformers: Text Generation](https://huggingface.co/docs/transformers/v4.22.2/main_classes/text_generation) — Defines `top_p` and related generation parameters in cumulative-probability terms.
- [Outlines Structured Generation](https://dottxt-ai.github.io/outlines/latest/) — Documents grammar- and schema-guided decoding as a constraint layer during token generation.
- [OpenAI Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs) — Provider documentation for schema-constrained response formats in hosted APIs.
- [vLLM Sampling Parameters](https://docs.vllm.ai/en/stable/api/vllm/sampling_params.html) — Runtime reference for temperature, top-p, top-k, repetition penalties, and related local inference controls.
