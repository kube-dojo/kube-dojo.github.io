---
title: "Modern Transformers: RoPE, ALiBi, and Attention-Head Geometry"
description: "Choose positional encoding and attention-head sharing patterns from first principles: RoPE, ALiBi, YaRN, MHA, MQA, GQA, and MLA, with decision criteria for long context, throughput, edge deployment, and quality-sensitive workloads."
slug: ai-ml-engineering/deep-learning/module-1.10-modern-transformers-rope-and-attention
sidebar:
  order: 1011
citations_verified: true
---

> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 8-10 hours
> Prerequisites: [Module 1.9: Graph Neural Networks](module-1.9-graph-neural-networks/), [Module 1.4.4: The Transformer Block from Scratch](module-1.4.4-transformer-block-from-scratch/), [Module 1.8: Self-Supervised Learning](module-1.8-self-supervised-learning/)

## Learning Outcomes

- **Diagnose** the limits of absolute positional embeddings and explain why they stop extrapolating cleanly beyond seen sequence lengths.
- **Implement** a mental model of RoPE and ALiBi that tracks both the algebra and the practical behavior, including why one is stronger for zero-shot long-context transfer and why the other is attractive in inference-constrained services.
- **Compare** MHA, MQA, GQA, and MLA at the level of kernel activity, KV-cache size, quality drift, and operational burden.
- **Build** a repeatable architecture decision tree for workload families: long-context inference, multi-GPU throughput, edge/Apple Silicon, and short-context quality-sensitive cases. Include one practical benchmark at 1K, 2K, and 4K context for MHA vs GQA.
- **Run and interpret** a practical head-to-head attention experiment at 1K/2K/4K context and map measured latency to tradeoffs.

## Why This Module Matters

A startup team ships a retrieval-augmented assistant behind an API endpoint.
The first quarter is successful because the model returns useful responses up to 4K tokens.
In month two the product team asks for 64K context to support long documents,
and suddenly quality collapses while GPU cost explodes.
The model architecture did not change.
Only two architectural knobs changed indirectly: positional treatment and KV-head topology.
This module gives you the engineering vocabulary to avoid guessing through that failure mode.

The deeper issue is not only that one transformer block changed its behavior.
The issue is that internal wiring changed from a tractable training-time geometry into a runtime bottleneck.
A model that is stable at moderate context can become unserviceable at high context because KV bytes, slope biases, and head sharing stop scaling linearly with request length.
This is exactly where modern transformer implementation details become first-class engineering decisions.

The module is designed as a technical bridge.
The historical context for MLA and attention compression appears in [The Algorithmic Response in AI History (ch-73)](/ai-history/ch-73-the-algorithmic-response/) in the AI History track, and this module is the implementation-side companion.
That means we focus on math, kernels, and service-level outcomes, then map each design to production cost and quality risk.

To stay practical, we do three things.
First, we restate positional embeddings and attention variants as memory and arithmetic contracts.
Second, we anchor each architecture to explicit failure modes and hardware bottlenecks.
Third, we end with a decision tree and a hands-on lab so the choice is not only conceptual but repeatable.

## Section 1: Absolute Positional Embeddings and Why They Break

The original transformer idea solved order dependence by adding positional information.
At inference, many implementations start from an equation of the form
$E_i = x_i + p_i$, where $x_i$ is the token embedding and $p_i$ is the positional vector.
The attention score between token $i$ and token $j$ depends on a dot product that includes $p_i$ and $p_j$.
When the position table is learned for $L_{\text{train}}$ positions and inference asks for $L > L_{\text{train}}$, then $p_{L}$ may not exist.
That failure is visible, deterministic, and often immediate: lookup failure or degraded behavior if embeddings are clamped, extrapolated, or padded poorly.

Even in cases where positional functions are fixed and sinusoidal, extrapolation is not a free lunch.
Sinusoid frequency ladders can represent positions beyond training length in theory,
but at large $i-j$ distances the model has rarely seen equivalent relative relationships during optimization.
The result is that attention similarity statistics drift.
A model can become overconfident around spurious local patterns or under-discriminate semantically distant evidence.
This matters most in long-context retrieval, code context memory, and multimodal follow-up loops.

The common failure pattern in production is this:
small-context behavior is stable first, then longer context requests shift attention mass toward local repetitions, memory pressure spikes, and latency/quality degrade before obvious errors appear.

- The model passes short-context tests with margin.
- A longer context prompt arrives, attention logits become numerically dominated by a few positions, and memory use grows.
- Latency and quality degrade before obvious functional bugs appear.

The key diagnosis is that absolute position methods are excellent for local interpolation but imperfect for relative extrapolation under constrained decode regimes.
They keep absolute coordinates, but many downstream systems care more about relative distance behavior.
That mismatch motivates RoPE and ALiBi.

## Section 2: RoPE from RoFormer (arXiv 2104.09864)

RoPE, short for rotary positional embedding, rotates vectors in a feature-intrinsic way instead of adding a separate positional vector.
The method starts from each query/key vector partitioned into 2-d planes.
A rotation by angle dependent on position index is applied before attention.
A canonical formulation is
\[\text{RoPE}(x, m) = R_m x\], where $R_m$ is a block rotation matrix for each feature pair and $m$ is the position.
The two-dimensional rotation block is $R_m=\begin{pmatrix}\cos(m\theta)&-\sin(m\theta)\\\sin(m\theta)&\cos(m\theta)\end{pmatrix}$, and $\theta$ depends on feature frequency.
Every pair of channels rotates in its own geometric plane.
The attention score then becomes
\[( R_{m} q )^\top (R_{n} k) = q^\top R_{n-m} k\], which makes the score depend on relative index difference.

The equation reveals the essential property: the score depends on the **relative index difference** $n-m$.
The score is not merely positional-aware, it is *relative-position aware* by construction.
That is exactly why RoPE became central in long-context dense-decoder systems.

A useful intuition is the difference between map-based and relative navigation.
Absolute encoding says “token one is at index 37, token two is index 58.”
RoPE says “token one and token two should compare under a relative angle determined by $(58-37)$,” even though absolute indices still seed the rotation.
If the model has only seen certain distance patterns during training,
it still receives a consistent geometric relation signal under larger offsets.
That consistency does not erase all distribution shift, but it preserves the right symmetry for many longer contexts.

There is another practical reason RoPE works in modern systems.
RoPE does not require a learned positional table sized by max sequence length.
Rotational angles derive from analytic frequencies, so the forward code has a cleaner extrapolation path.
That is not equivalent to guaranteed quality at million-token context.
It means the failure is less structural and more numerical.
In particular, KV and attention compute paths still need memory and cache control.
RoPE mostly reduces positional brittleness.

## Section 3: ALiBi (arXiv 2108.12409) and Distance-Only Bias

ALiBi takes a different route.
Instead of changing vector spaces, it injects a linear penalty directly into attention logits.
For token positions $i$ (query) and $j$ (key), each head has a fixed, head-specific slope $m_h$ set from a geometric schedule, and the logit becomes
 $\text{logit}^{(h)}_{i,j} = \frac{q^{(h)}_i k^{(h)\top}_j}{\sqrt{d_k}} - m_h (i-j)$, where $i \ge j$ for causal decoding.
The larger the distance, the stronger the subtraction.
Unlike RoPE, ALiBi does not add a positional vector.
It requires no position embeddings at runtime except implicit index arithmetic and has a small constant-time bias computation.

The practical interpretation is straightforward:
ALiBi prefers near-context tokens but never fully suppresses distant evidence.
The linear decay is soft, so long-range information remains available when needed, especially when semantic content justifies it.
Because bias is explicit and simple, ALiBi is surprisingly robust in decoder-only inference setups that must behave predictably under length growth.

In long-context workloads with weakly structured documents, ALiBi often reduces pathological drift.
The model cannot treat every position as equally likely, but it also does not discard everything beyond context windows.
This makes ALiBi attractive when architecture budget is tight and you need deterministic extrapolation behavior.
One implementation cost is that the slope set per head must be tuned or copied from known schedules.
When slopes are too steep, retrieval quality collapses for far references.
When slopes are too shallow, you recover less local focus and may get attention bleeding in unstructured prompts.

In practice, ALiBi’s geometric per-head slopes are a compact way to encode head specialization.
Some heads stay conservative and local, others remain global.
The module implementation style keeps these slopes fixed once configured because this is a serving concern as much as a training concern.
The ALiBi paper (§3) states head slopes are fixed (not learned) during training.

## Section 4: YaRN (arXiv 2309.00071) and NTK-Aware Scaling

YaRN sits in the same family as positional scaling strategies, but it is specifically about extending context length without retraining from scratch.
The core concept is NTK-aware scaling.
NTK intuition says that position encoding affects kernel behavior, so we can manipulate frequencies to preserve local geometry while enabling larger context ranges.

Conceptually, YaRN introduces a context-scale factor $\lambda > 1$ and applies a dual treatment:
short-distance positional frequencies stay near original values,
while long-distance behavior is stretched to allow larger positional offsets.
It is not simply “multiply positions by a constant.”
That naive scaling does not preserve near-context behavior,
so YaRN keeps a lower-frequency core stable and scales higher-frequency bands.
This mixed-band idea is why it remains useful for extending context beyond pretraining length in deployed systems.

The useful engineering takeaway is operational:
when you must run with longer user prompts than pretraining, YaRN-like scaling is a practical lever before architecture replacement.
It cannot invent factual knowledge beyond training corpus coverage.
It can, however, keep attention distance priors and positional structure less distorted than naive interpolation.

Use this interpretation when planning production upgrades:
- If quality drift is mostly positional and not representational, position scaling may buy enough runway.
- If quality drift is about factual memory saturation or architecture depth limits, you still need deeper structural changes.
- If latency is your blocker, evaluate whether NTK scaling changes prefill and decode enough to justify risk.

YaRN is not a silver bullet.
For contexts beyond very long thresholds, attention-kernel design and KV compression still dominate.
RoPE with KV-sharing changes, plus YaRN-like scaling where possible, are typically the strongest combination for long-context continuity.

## Section 5: Baseline Reference — Multi-Head Attention

Before comparing families, fix the baseline.
MHA computes per-head projections where each of the $H$ heads has independent $Q_h,K_h,V_h$ projections.
In compact form: $\text{MHA}(X)=\text{Concat}\big(\text{softmax}(\frac{Q_h K_h^\top}{\sqrt{d_k}}) V_h\big)W_O$.
At decode, MHA stores key-value history for every head independently.
If we denote:

- $L$ as sequence length,
- $N$ as number of transformer layers,
- $H$ as attention heads,
- $d_k$ as per-head key/value dimension,
- $b$ as bytes per stored value (2 for FP16/BF16, 1 for INT8 style quantized caches),

then approximate KV cache bytes are
$\text{KV}_{\text{MHA}} \approx 2 \times N \times H \times d_k \times L \times b$.

This is the first arithmetic reason MHA becomes expensive quickly.
KV scales linearly in all four pressure axes and linearly with context.
At 32K and many layers, memory is no longer a tuning detail; it is the primary constraint.

MHA tends to preserve quality when architecture and data are tuned together.
Each head has more explicit head-specific history, which often helps niche attention patterns.
But the service profile may be over-budget on memory traffic and on cache growth.

Quality-wise, MHA remains a strong default when sequence lengths are moderate, hardware is stable, and the team prioritizes behavior certainty over aggressive memory reduction.

## Section 6: MQA and the Single Shared KV Head

MQA (multi-query attention) keeps multiple query heads but only one shared key-value head.
That means attention scores are formed with many $Q_h$ but shared $K$ and $V$ projections.
The KV estimate drops dramatically to
$\text{KV}_{\text{MQA}} \approx 2 \times N \times d_k \times L \times b$.

This is near an H-fold reduction in KV storage relative to MHA.
That is a massive memory win for edge or single-user decoding.

The cost is a structural coupling.
Because keys and values are shared, each query head loses its own distinct key/value geometry.
In exchange for reduced bytes and cleaner cache behavior, some representational flexibility is sacrificed.
Many real workloads accept this tradeoff because decoding throughput and memory fit dominate.

MQA is a strong candidate for:
- local desktop deployment,
- Apple Silicon contexts where memory bandwidth and cache pressure dominate,
- single-GPU serving with modest batch and low latency requirements.

In those settings, quality loss is often small relative to the gain in capacity.
But if you need very sharp head specialization at extreme lengths, this trade can become visible as subtle factual drift and weaker cross-reference retrieval.

## Section 7: GQA as the Middle Ground (arXiv 2305.13245)

GQA groups query heads into groups that share one KV head each.
If group size is $g$, then $H_{kv}=H/g$.
The cache formula is
$\text{KV}_{\text{GQA}} \approx 2 \times N \times \frac{H}{g} \times d_k \times L \times b$.

When $g=2$ or $g=4$, this is a smooth trade between full MHA memory and MQA minimum memory.
GQA preserves partial head specialization while recovering much of MQA’s memory efficiency.

This is why GQA became the pragmatic default in many high-throughput serving families.
It is a design that admits scaling decisions:
- If quality regressions from MQA are too high, move toward GQA.
- If memory pressure remains too high, move toward larger groups or MQA.
- If quality is critical and context is not extreme, keep groups smaller and accept higher cache memory.

The operational profile of GQA is particularly important in production engines with mixed traffic.
Because KV and bandwidth are where service limits appear under concurrency,
GQA often yields the best throughput uplift before quality becomes fragile.
That makes it a strong bridge architecture for teams that cannot adopt MLA yet.

## Section 8: MLA — Multi-Head Latent Attention (DeepSeek-V2 arXiv 2405.04434)

A key point in DeepSeek-V2 §2.1 is that MLA splits the caching path into low-rank latent projections and per-head reconstruction.
Instead of storing full per-head key and value tensors for every token in cache, MLA stores compact latents.
A simplified view is:
- map hidden state to a latent K-latent and V-latent
- share these latents across heads,
- expand per-head values at compute time for attention scoring.

In practice this is implemented with low-rank projection matrices.
The latent dimension is much smaller than $H \times d_k$, and that is where the KV reduction comes from.
The paper reports a headline 93.3% KV reduction versus naive dense baselines for comparable settings.
The effect is most noticeable when context grows into tens of thousands of tokens.

DeepSeek-V2 uses a decoupled RoPE path because standard RoPE on compressed keys/values does not commute with the low-rank decomposition used by MLA.
If RoPE were applied before decomposition, it would break that decomposition and force recomputation of full keys during decoding.
So MLA keeps two cache components:
- the latent KV cache $c_t^{KV}$ with dimension $d_c$
- a separate decoupled RoPE component $k_t^R$ with dimension $d_h^R$.

For sequence-wise cache accounting, DeepSeek-V2 describes the per-layer per-token cache as
$\text{KV}_{\text{MLA}} \propto d_c + d_h^R$.
Across $l$ layers, this is
$$\text{KV}_{\text{MLA}} = (d_c + d_h^R)\cdot l$$
(up to dtype and projection constants), as introduced in §2.1.3.

Think of MLA as turning KV into a compressed “source manifold” plus lightweight view-dependent decoders.
You pay extra projection work during attention but move the dominant memory burden out of cache growth.
This shifts the bottleneck toward compute and projection overhead, which can be preferable when memory bandwidth is your first-order constraint.

A practical way to remember MLA:
- MHA: full history for every head.
- MQA: one shared history for all heads.
- GQA: several shared histories for groups.
- MLA: low-rank shared latent history with per-head reconstruction at query time.

That third step matters for hardware.
KV reduction reduces memory pressure per request,
which in turn reduces paging risk, increases concurrent requests per GPU, and improves service stability at long context.
But MLA implementation complexity is higher.
Integration risk comes from model-specific kernels, projection shapes, quantization paths, and compatibility with your serving stack.

DeepSeek’s FlashMLA implementation explores this design as part of optimized kernel paths.
If you are adopting MLA, the practical question is not “does it work on paper,” but “does your stack support its latent cache and projection schedule without forcing fallback kernels.”

## Section 9: FlashAttention and Why It Is Usually Not the First Choice of this Module

FlashAttention is an important kernel-level optimization for exact attention with memory-tiling and IO-aware computation.
It is especially relevant in long-context training and high-throughput serving where softmax computation can become memory-bound.
In this module it is intentionally brief because several infra modules already handle the full engine-level analysis.

The distinction we keep here is: FlashAttention answers “how do we compute attention faster,”
while RoPE/ALiBi/MQA/GQA/MLA answer “what is the representation geometry and cache contract of the architecture.”
Both are required in real deployments, but the design choice you are asked to make for this issue is mostly about wiring and cache topology.

## Section 10: Workload-to-Architecture Decision Tree

Use this as a practical decision filter, not a slogan.
The tree below is tuned for the four regimes you requested.

### 10.1 Workload: long-context inference, >=1M tokens

If your service must reliably run around one million context tokens, start from these two constraints:
- context budget is no longer a preference but a memory and cache contract,
- relative position behavior is as important as raw local fluency.

For that workload, start with a RoPE family plus a scalable positional strategy such as YaRN (or compatible scaling in your stack).
This gives you a stronger distance prior than simple additive absolute positions and better extrapolation behavior than naïve sinusoids.
Then evaluate MLA as a cache strategy.
MLA usually gives the best long-context KV control because reducing KV growth is the dominant operational pressure.

A simple branch for this path:

1. If context target exceeds pretraining range by more than 8x, prefer RoPE + YaRN.
2. If memory headroom under one-M tokens is still insufficient, move to MLA if kernels and serving support exist.
3. If MLA is unavailable, select highest stable GQA ratio that preserves quality metrics.
4. If both quality and memory are unstable, reduce context windows and add hierarchical retrieval before architecture changes.

### 10.2 Workload: multi-GPU serving with high throughput

In multi-GPU serving, throughput usually collapses first from per-token memory traffic and queue scheduling.
When concurrency is high, every extra KV byte multiplies into queue depth.
This is a strong environment for GQA.

Why GQA first?
Because it usually preserves more quality than MQA while reducing cache by a controllable factor.
That reduction lowers inter-request variance and gives scheduler more stable working sets.
The practical branch is:

1. If quality target is strict but not extreme at long distances, use GQA with moderate group size.
2. If memory pressure remains dominant after GQA, test MQA only after observing recall and citation tasks.
3. If quality must not move at all for high-value paths, keep MHA only for that path and route high-throughput traffic through GQA paths.

### 10.3 Workload: edge / Apple Silicon / single-GPU

Here the architecture budget is set by memory cap and power, not by full-scale datacenter throughput.
MQA is often the default choice because cache size directly determines max context and stability.
With MQA, single-GPU serving often becomes feasible without immediate model distillation.

The branch:

1. If local GPU memory is the primary cap and quality tolerances are standard, start with MQA.
2. If quality drift appears on reference retrieval at moderate context, test RoPE implementation details before changing model family.
3. If one class of documents is repeatedly failing, reduce context via retrieval or summarization and keep MQA for steady serving.

### 10.4 Workload: short-context quality-sensitive

Short-context inference has a different profile.
KV scale is smaller and local attention quality becomes the main objective.
MHA is usually best here because it keeps full per-head K/V capacity.

Branch:

1. For chat-like short prompts where quality, formatting, and correctness matter, start with MHA.
2. Add minimal caching optimizations first (backend-level kernels, request batching), not architectural compression.
3. Only switch to GQA/MQA if there is a hard throughput or deployment constraint that cannot be solved elsewhere.

## Section 11: Quality-Throughput Curves and Trade-Off Geometry

Treat every architecture as a curve in the same coordinate system.
The x-axis can be latency per output token, memory per context, or cost per user-visible request.
The y-axis can be factual fidelity or benchmark score.
The wrong mental model is choosing one point without reading the curve.
The right model is choosing a point that dominates your deployment constraints.

### 11.1. MHA curve

- Quality: highest or near-highest on many tasks,
- Memory: steep with context,
- Throughput: lower at high concurrency when context grows,
- Engineering: simplest mental model and broad framework compatibility.

As context increases, KV terms dominate.
The curve usually drops sharply in throughput once queueing and paging interact.

### 11.2. GQA curve

- Quality: high in middle regimes,
- Memory: reduced by $g$ ratio,
- Throughput: improved under long prompts and batch,
- Engineering: moderate complexity, broad integration support.

The curve is often the best practical frontier for production inference.
GQA often beats MQA on quality while providing substantial memory savings.

### 11.3. MQA curve

- Quality: slightly lower in position-sensitive retrieval and long-context aliasing cases,
- Memory: lowest among classical variants,
- Throughput: often excellent in low-concurrency local settings,
- Engineering: often easiest to fit into constrained hardware.

The trade curve is favorable when context and cost are constrained and slight quality drift is acceptable.

### 11.4. MLA curve

- Quality: strong at long-range tasks for large contexts, especially in tuned deployments,
- Memory: strongest long-context reduction due latent cache representation,
- Throughput: dependent on projection/kernel quality,
- Engineering: highest implementation complexity.

The MLA curve has the best long-context memory efficiency but only if your stack supports the kernels and cache plumbing.
If the implementation falls back to non-optimized paths, the curve can invert and look worse than GQA.

## Section 12: Cross-Track Connections

Two deep connections matter.

First, every KV optimization changes the bandwidth problem described in [Memory Bandwidth Math](../ai-infrastructure/module-1.6-memory-bandwidth-math/).
A wrong estimate there leads to wrong architecture decisions here.
If your model appears to have a bandwidth floor, changing from MHA to GQA or MLA changes the floor shape.

Second, every architecture decision is multiplied by serving behavior covered in
[Production Inference Engines](../ai-infrastructure/module-1.7-production-inference-engines/).
A fast attention variant with weak observability is still a production risk.
For example, if your scheduler cannot expose cache residency, TTFT variance, and queue depth, quality regressions can arrive as silent user-facing incidents.

Cross-check those modules before you finalize the choice.

## Decision-Making Checklist

Use this sequence in design reviews.

1. Define workload envelope first: context, concurrency, SLA class, and quality floor.
2. Identify bottleneck class: KV cache, prefill compute, attention kernel, or application-level latency target.
3. Choose positional strategy for context generalization: RoPE baseline, RoPE + YaRN, or ALiBi where distance linearity is preferable.
4. Choose KV family: MHA, MQA, GQA, or MLA.
5. Assign fallback alternatives and measurable stop conditions.

Do not stop at architecture label.
If your design has no “if this degrades, we switch back” path, the deployment team has no safe exit.

This checklist is why engineering teams avoid one-model lock in.
A model that looks perfect in an internal notebook can fail on concurrency with real queueing behavior.
The design should therefore include an explicit rollback axis and a benchmark gate.

## Practical Lab (Bloom L3+): Compare MHA vs GQA in vLLM/Transformers

This lab is intentionally operational.
You will load one MHA-family model and one GQA-family model,
measure KV cache footprint and decode latency at 1K, 2K, and 4K,
and then reason through the results.

### 12.1 Model set and expectation

Use any available GPU-capable host.
If you already have a vLLM environment, use it.
The default pair is:

- Llama-2-style MHA baseline: `NousResearch/Llama-2-7b-hf` (MHA, `num_attention_heads = 32`, `num_key_value_heads = 32`)
- Mistral-style model with GQA: `mistralai/Mistral-7B-Instruct-v0.3` (`num_attention_heads = 32`, `num_key_value_heads = 8`)

Expected shape is: GQA should show lower KV growth and better long-context decode stability under equal serving configuration,
with a small or moderate quality tradeoff depending on your benchmark corpus.

### 12.2 Install and minimal setup

```bash
.venv/bin/pip install --upgrade 'torch>=2.3' 'transformers' 'vllm' 'accelerate'
```

### 12.3 Estimate-only calculator (before runtime benchmark)

```python
import math

def estimate_kv_gb(seq_len, layers, kv_heads, head_dim=128, dtype_bytes=2):
    """
    Estimate KV cache size in GiB for a causal decoder with prefill+decode serving context.
    """
    bytes_total = 2 * layers * kv_heads * head_dim * seq_len * dtype_bytes
    return bytes_total / 1024**3

variants = {
    "mha": 32,
    "gqa": 8,
}

for model_label, kv_heads in variants.items():
    for seq_len in [1024, 2048, 4096]:
        gb = estimate_kv_gb(seq_len=seq_len, layers=32, kv_heads=kv_heads)
        print(model_label, seq_len, round(gb, 2), "GiB")
```

This rough calculator is not optional.
It gives you a first-order estimate of whether your hardware can even attempt the full benchmark.
Many failures come from skipping this and launching a benchmark that never reaches steady state.

### 12.4 Benchmark script with vLLM

For this lab, use prompt sizes that fit under a 4096-token model limit while generating 128 output tokens: 896, 1920, and 3968 token prompts.
This leaves a consistent 128-token generation headroom under `max_model_len=4096`.

```python
import argparse
import time
from dataclasses import dataclass

import torch
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer


@dataclass
class ModelSpec:
    name: str
    model: str
    architecture_note: str
    kv_heads: int


def build_model(spec: ModelSpec, dtype: str = "float16"):
    return LLM(
        model=spec.model,
        tensor_parallel_size=1,
        dtype=dtype,
        trust_remote_code=True,
        enable_prefix_caching=True,
        max_model_len=4096,
        gpu_memory_utilization=0.85,
    )


def benchmark(model: LLM, prompt: str, new_tokens: int = 128):
    params = SamplingParams(
        temperature=0.7,
        top_p=0.95,
        max_tokens=new_tokens,
    )
    start = time.time()
    outputs = model.generate([prompt], params)
    elapsed = time.time() - start
    out = outputs[0]
    total_tokens = len(out.outputs[0].token_ids)
    # tokens per second is an approximate total throughput proxy.
    tps = total_tokens / max(elapsed, 1e-9)
    return elapsed, total_tokens, tps


def synthetic_prompt(tokenizer: AutoTokenizer, seq_len: int) -> tuple[str, int]:
    base_prompt = "A long story about software architecture, memory systems, and software engineering patterns. "
    tokens = []
    while len(tokens) < seq_len:
        tokens.extend(tokenizer.encode(base_prompt, add_special_tokens=False))
    tokens = tokens[:seq_len]
    assert len(tokens) == seq_len, f"Token count mismatch: {len(tokens)} vs {seq_len}"
    prompt = tokenizer.decode(tokens)
    return prompt, seq_len


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["mha", "gqa"], default="mha")
    args = parser.parse_args()

    specs = {
        "mha": ModelSpec(
            name="Llama_MHA",
            model="NousResearch/Llama-2-7b-hf",
            architecture_note="MHA",
            kv_heads=32,
        ),
        "gqa": ModelSpec(
            name="Mistral_GQA",
            model="mistralai/Mistral-7B-Instruct-v0.3",
            architecture_note="GQA",
            kv_heads=8,
        ),
    }

    model = build_model(specs[args.model])
    tokenizer = AutoTokenizer.from_pretrained(specs[args.model].model)
    benchmark_contexts = [
        (896, "1K-128"),
        (1920, "2K-128"),
        (3968, "4K-128"),
    ]
    for seq_len, context_label in benchmark_contexts:
        prompt, actual_tokens = synthetic_prompt(tokenizer, seq_len)
        torch.cuda.synchronize()
        elapsed, tokens, tps = benchmark(model, prompt, new_tokens=128)
        torch.cuda.synchronize()
        print(f"{specs[args.model].name},{specs[args.model].architecture_note},{context_label},{actual_tokens},{elapsed:.2f},{tokens},{tps:.2f},{actual_tokens}")
```

### 12.5 Expected measured shape and interpretation

Below is an illustrative table shape from the same hardware class and prompt family.
Use it as a sanity envelope rather than a target score.

| Model | Attention Variant | Context | KV estimate (GiB) | Decode TPS (1-user, batch=1) | TTFT (ms) | Practical comment |
|---|---|---:|---:|---:|---|
| `NousResearch/Llama-2-7b-hf` | MHA | 896 (1K-128) | 0.50 | 62 | 260 | Quality baseline is clear; KV pressure starts to become visible past 2K |
| `NousResearch/Llama-2-7b-hf` | MHA | 1920 (2K-128) | 1.00 | 54 | 340 | KV and softmax costs rise together; quality and latency trade-off becomes visible |
| `NousResearch/Llama-2-7b-hf` | MHA | 3968 (4K-128) | 2.00 | 46 | 420 | Still operational, but expect occupancy stress and less stable tails by 4K |
| `mistralai/Mistral-7B-Instruct-v0.3` | GQA | 896 (1K-128) | 0.13 | 78 | 230 | Better cache profile with earlier headroom at short-to-mid context |
| `mistralai/Mistral-7B-Instruct-v0.3` | GQA | 1920 (2K-128) | 0.25 | 70 | 320 | Longer-context stability gains start to appear while quality usually remains close |
| `mistralai/Mistral-7B-Instruct-v0.3` | GQA | 3968 (4K-128) | 0.50 | 62 | 400 | Often better than MHA for sustained 4K and above at equal SLO targets |

You should read those numbers as a comparison curve.
If MQA or MLA are in scope in your infrastructure, you can add them to the same table with the same prompt family and observe where each line bends.
The absolute values matter less than shape.

### 12.6 How to explain the results in reviews

A useful review pattern is:

- Compare whether measured KPIs follow the predicted KV scaling curve.
- If they diverge, inspect prompt batching, prefill strategy, and sampling settings first.
- If MHA quality is materially higher at 8K but collapses at 32K, prefer GQA or MLA for user-visible long-context SLOs.
- If short-context quality is the primary contract and long-context is rare, keep MHA and use context policies to cap pathological prompts.

This prevents architecture churn from becoming a blind optimization run.

## Did You Know?

- RoPE turns relative positions into rotations, so the transformed query-key dot product depends on distance as much as absolute index.
- ALiBi adds a per-head linear bias and requires no learned positional vectors, which can be a useful operational simplification for certain serving stacks.
- GQA sits between MQA and MHA as a head-sharing spectrum where cache reduction and quality retention can be tuned by group size.
- MLA reduces KV cache pressure aggressively through low-rank latents, but only if serving kernels actually execute the design efficiently.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Treating sequence length extrapolation as a fine-tuning problem only | Teams expect weights to fix a positional geometry mismatch | Decide whether positional encoding and positional scaling need architecture changes before retraining |
| Selecting attention variant only on single-benchmark TPS | Aggregate throughput hides TTFT and long-context variance | Report TTFT, queue depth, and long-context fidelity probes together |
| Comparing models using only one context length | Position and KV behavior are context dependent | Benchmark at realistic range points such as 8K, 16K, and 32K |
| Using absolute positional assumptions beyond training length | Teams conflate padding tricks with genuine extrapolation | Use RoPE/ALiBi choices tied to context policy and verify failure mode with far-reference prompts |
| Choosing MQA for everything in multi-tenant service | Single-GPU mindset does not transfer to shared concurrency | In shared workloads, verify quality degradation for retrieval accuracy and cross-reference tasks |
| Ignoring head-sharing impact on long retrieval tasks | Engineers optimize only for memory numbers | Add factual long-range probes and compare citations, table references, and contradiction handling |
| Assuming MLA is always superior if it is smaller | Latent projection adds its own integration and kernel assumptions | Gate MLA adoption behind stack compatibility, kernel maturity, and warm startup behavior |

## Quiz

<details>
<summary>Question 1: A team uses 1M-token retrieval context and has severe KV-cache OOM at 256 users. Which first move is most defensible?</summary>

A. Keep MHA and add more GPUs without changing attention family.

B. Switch to MQA to minimize cache size and accept some mild quality drift.

C. Switch to MLA immediately and ignore serving compatibility because cache is the only bottleneck.

D. Switch to a deeper MLP-only architecture.

**Answer: B.** The immediate bottleneck is cache size, and MQA gives the strongest classical KV reduction.
At first pass, option B is the right direction because it directly addresses cache pressure with predictable memory gains.
Option A solves only capacity with infrastructure and often delays the failure.
Option C can be even better when supported, but skipping compatibility and kernel readiness is high risk.
Option D is orthogonal and cannot target KV cache memory directly.
</details>

<details>
<summary>Question 2: A model with RoPE works well up to 8K but quality drifts at 32K; MHA KV estimate also rises above 12 GiB. Which architectural pair is most coherent as a first change?</summary>

A. Change to ALiBi with default slopes and keep everything else unchanged.

B. Keep RoPE and switch to MQA only.

C. Add RoPE/YaRN-style scaling and plan GQA or MLA depending on kernel support.

D. Remove positional encoding and rely on absolute embeddings.

**Answer: C.** This path addresses both positional extrapolation and memory scaling with a coherent long-context strategy.
Option A may help local-distance behavior but does not reduce KV growth on its own.
Option B helps memory but does not directly stabilize positional extrapolation.
Option D removes structure needed for sequential reasoning and is generally not a first repair.
</details>

<details>
<summary>Question 3: Your service uses multi-GPU tensor parallel inference and has decent quality requirements. Which attention family is usually the best first candidate?</summary>

A. MHA because it preserves full per-head flexibility.

B. GQA with a moderate group size.

C. MQA for maximum compression.

D. ALiBi without changing model class.

**Answer: B.** GQA is usually the best starting point because it reduces KV bytes while retaining partial per-head specialization.
That usually gives a better quality-efficiency balance than MQA at multi-user throughput scales.
Option A often runs into cache pressure too early.
Option C can overreduce geometry too quickly for quality-sensitive multi-tenant tasks.
Option D is an orthogonal positional choice and does not control KV-head sharing by itself.
</details>

<details>
<summary>Question 4: Which statement correctly characterizes MLA in this context?</summary>

A. MLA stores full per-head K and V tensors exactly like MHA.

B. MLA is a low-rank latent cache approach and is useful when long-context memory pressure is dominant.

C. MLA always outperforms GQA regardless of hardware support.

D. MLA removes the need for serving stack validation.

**Answer: B.** MLA is designed to reduce KV caching pressure by storing compact latents and reconstructing per-head attention context at compute time.
Option C is wrong because implementation maturity and kernel support determine realized performance.
Option D is wrong because serving-stack validation is still required for production safety.
Option A is incorrect because the central point of MLA is reduced KV storage.
</details>

<details>
<summary>Question 5: During a design review, which metric set is most correct for validating long-context architecture choice?</summary>

A. TTFT, TPS at multiple context points, queue depth, and retrieval correctness probes.

B. Total tokens per hour only.

C. One synthetic benchmark with the shortest available context.

D. Hardware utilization alone.

**Answer: A.** Long-context architecture decisions need both latency metrics and quality fidelity checks.
Using only throughput misses practical user impact at tail latency.
Context-point probing is required because behavior is highly non-linear with length.
Option B hides latency regime issues.
Option C fails because it ignores the critical range.
Option D is insufficient because utilization without quality and tail behavior can still look healthy.
</details>

<details>
<summary>Question 6: A team says “we will use ALiBi because it is simple and no learned positional table.” Which caveat is most important?</summary>

A. Simplicity guarantees quality parity with RoPE in every task.

B. ALiBi changes global distance priors and may alter retrieval behavior for specific tasks.

C. ALiBi removes any need for KV compression choices.

D. ALiBi is identical to MQA.

**Answer: B.** ALiBi’s head-wise linear biases are powerful but they change how far context is weighted.
That can shift behavior on distant-reference tasks.
Option A is false because quality is task-dependent.
Option C is false because ALiBi does not change K/V cache structure.
Option D confuses positional strategy with attention-head topology.
</details>

<details>
<summary>Question 7: What is the best reason for adding an explicit fallback architecture path in production?</summary>

A. Fallbacks reduce code size.

B. Fallbacks are unnecessary if one architecture wins a benchmark.

C. A fallback avoids single-point architectural failure when real workloads hit different regions.

D. Fallbacks increase cost and should be avoided.

**Answer: C.** Real workloads are heterogeneous, so the first architecture often fails in a narrow region and degrades gracefully in others.
A staged path (for example, MHA for high-sensitivity paths and GQA/MLA for scale paths) reduces incident risk.
Option A is not the purpose and can be false.
Option B is a common benchmark fallacy.
Option D ignores reliability requirements in production.
</details>

## Hands-On Exercise

Goal: quantify the architecture choice for your own hardware and connect measured numbers to the decision tree.
Use the same random prompt family across model family pairs and keep batch small.
The objective is not to reach a perfect absolute benchmark.
The objective is to produce an interpretable difference curve.

- [ ] Confirm model availability and record exact hardware/software versions, especially PyTorch, CUDA, and vLLM build.

<details>
<summary>Solution guidance</summary>

Record these fields: CPU, GPU, GPU memory, PCIe/NVLink topology, model ids, precision, max model len, and serving commit.
Without this metadata, future readers cannot compare benchmarks across runs.
</details>

- [ ] Run the KV estimator from section 12.3 for MHA and GQA values and compute expected cache growth at 1K/2K/4K.

<details>
<summary>Solution guidance</summary>

Use the same `layers`, `head_dim`, and `dtype` for both variants, changing only `kv_heads`.
Check that long-context model behavior aligns with cache growth before you run full inference.
</details>

- [ ] Run the vLLM benchmark script for both models at each context point and export timestamped CSV rows.

<details>
<summary>Solution guidance</summary>

Use fixed seeds and fixed output lengths for comparability.
Collect TTFT, elapsed time, output token count, and approximate TPS.
Store raw terminal output and parsed rows.
</details>

- [ ] Compare measured decode TPS and TTFT against the estimated KV curve.

<details>
<summary>Solution guidance</summary>

A model with worse-than-expected latency relative to cache estimate may be suffering from kernel fallback or prefill overhead.
Do not conclude architecture failure before checking sampling, paging, and warm-up effects.
</details>

- [ ] Evaluate two quality probes (fact recall and reference span localization) at all three context points.

<details>
<summary>Solution guidance</summary>

Build two prompt families: one that stresses factual consistency and one that stresses long-range reference.
Use the same scoring rubric for both models and both lengths.
</details>

- [ ] Decide one recommendation and one fallback.

<details>
<summary>Solution guidance</summary>

Your recommendation should specify: primary architecture, reason tied to measured numbers, and explicit fallback architecture with a clear trigger.
For example, “GQA at short-to-mid context and MLA for sustained 32K+, with quality gate below threshold then revert to high-capacity MHA path.”
</details>

- [ ] Add a brief postmortem note on why the result would differ on CPU-only, A100, and Apple Silicon.

<details>
<summary>Solution guidance</summary>

CPU-only will not represent the same memory pressure regime.
Apple Silicon introduces unified memory and different scheduler behavior.
A100/H100 shifts both prefill and decode shapes due higher concurrency and memory bandwidth.
</details>

- [ ] Optional: add one MLA candidate if your stack supports FlashMLA and provide a short comparison row.

<details>
<summary>Solution guidance</summary>

If you attempt MLA, preserve the same prompt family and output constraints.
Only compare within the same hardware and sampling strategy.
</details>

Success criteria:

- [ ] KV estimate increases with context while TPS and TTFT follow the expected trend (TPS decreases as KV cache and prefill pressure rise).
- [ ] 1K/2K/4K measurements are present for both attention families.
- [ ] The chosen architecture is justified by measured bottleneck shape, not by benchmark one-line output.
- [ ] A fallback architecture is explicitly documented.
- [ ] Quality probes are run at each context point, even if approximate.
- [ ] The postmortem explains at least one CPU/GPU/Apple Silicon divergence.

## Next Module

Continue to [Machine Learning](../machine-learning/) to apply these foundations to tabular ML — the sklearn API, regression, trees, and evaluation.

## Sources

- [RoFormer: Enhanced Transformer with Rotary Position Embedding](https://arxiv.org/abs/2104.09864)
- [ALiBi: Attention with Linear Biases](https://arxiv.org/abs/2108.12409)
- [GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints](https://arxiv.org/abs/2305.13245)
- [YaRN: Effective Context Length Extrapolation](https://arxiv.org/abs/2309.00071)
- [DeepSeek-V2: A Next-Generation Mixture-of-Experts Language Model](https://arxiv.org/abs/2405.04434)
- [FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](https://arxiv.org/abs/2205.14135)
- [FlashMLA repository](https://github.com/deepseek-ai/FlashMLA)
- [vLLM project](https://github.com/vllm-project/vllm)
- [vLLM RoPE implementation (Llama3 rope)](https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/layers/rotary_embedding/llama3_rope.py)
- [vLLM YARN/NTK rope support](https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/layers/rotary_embedding/yarn_scaling_rope.py)
- [vLLM attention implementations notes](https://docs.vllm.ai/en/stable/design/v1/attention.html)
- [llama.cpp repository](https://github.com/ggml-org/llama.cpp)
- [llama.cpp RoPE kernel (CUDA)](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-cuda/rope.cu)
- [llama.cpp RoPE test coverage](https://github.com/ggml-org/llama.cpp/blob/master/tests/test-rope.cpp)
- [Transformers modeling of positional embeddings](https://github.com/huggingface/transformers/tree/main/src/transformers/models)
- [Hugging Face Transformers generation API](https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)
- [PyTorch documentation on scaled dot-product attention](https://pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html)
- [PyTorch distributed and inference considerations](https://pytorch.org/docs/stable/torch.compiler.html)
- [CITATION: Transformer paper for baseline context](https://arxiv.org/abs/1706.03762)

## Extended Applied Appendix: Trade-Off Surfaces, Diagnostics, and Concrete Failure Signatures

When teams discuss long-context and high-throughput attention, they often jump directly to one metric and over-index on it.
A robust workflow uses three layers of evidence.
First layer evidence is analytic: equation-level complexity and memory scaling.
Second layer evidence is benchmarked behavior: latency, throughput, and queueing traces at realistic sequences.
Third layer evidence is user-impact: retrieval quality, citation support, and failure drift across context windows.
Only when all three layers agree should architecture selection be considered stable.

The analytic layer is where this module contributes most.
Suppose a model has six dimensions of stress: context, concurrency, quality tolerance, latency budget, deployment budget, and engineering stack maturity.
Each of those dimensions selects a different sub-optimal point.
A design that looks best in isolation can become the worst candidate once the full vector is considered.
The appendix helps you test whether a design remains coherent when the vector rotates.

For baseline cache math, start from the full key/value state requirement.
A fixed architecture with sequence length $L$ stores a structured tensor containing all attention keys and values required for decode.
Each request has hidden coupling between layers, heads, and bytes per element.
The cache growth curve is not random.
It is deterministic and often linear in sequence length under fixed configuration, which means your first prediction should be deterministic too.
When that prediction is wrong, it indicates an implementation mismatch rather than a purely architectural mismatch.

In practical terms, this means you can reason about memory at the level of per-layer factors before touching the benchmark loop.
If the predicted curve already violates your memory budget, benchmarking is unnecessary until model choice changes.
The most common productivity waste in LLM serving reviews is running a benchmark for an architecture that has already failed arithmetic feasibility.
A 4 GB budget that predicts 6 GB at 16K context is not a benchmark problem.
It is a model-family problem.

One concrete way to apply this: compute separate upper bounds for prefill and decode.
Prefill grows with input length and may be optimized by caching and model-specific kernel fusion.
Decode grows with generated length and is constrained by both arithmetic and memory bandwidth.
If decode KV residency is the bottleneck, architecture changes usually give better ROI than larger kernels.
If prefill dominates and decode appears healthy, architecture and sampling constraints should be revisited before changing the KV family.
This split helps avoid false optimization conclusions.

A subtle but practical point is that KV bytes are not the only memory axis.
Activation memory, optimizer state (for online adaptation), runtime buffers, and request-level overhead can all move the observed envelope by gigabytes.
What matters to architecture review is the marginal slope of each axis.
If an architecture reduces KV by 2x but increases temporary activation by 1.5x and adds unstable scratch allocation, the net gain can be negligible.
That is why model-family reviews should track the full per-step memory profile, even when using an approximate KV formula.

Long-context behavior should be observed under three prompt taxonomies.
Use coherent short prompts, adversarial retrieval prompts, and periodic-structure prompts with repeated patterns.
If quality degrades only in one taxonomy, your solution may still be deployable with guards.
If it degrades in all taxonomies, your architecture and scoring assumptions should be rebalanced.
Prompt taxonomy is a practical dimension of Bloom L3+ validation.

Positional encoding choice should be validated by stress prompts that exaggerate relative distance.
For RoPE-focused experiments, include prompts where the key evidence sits near the end and appears as paraphrase earlier.
For ALiBi-focused experiments, include prompts where the best next token depends on long-distance evidence competing with local repetition.
For YaRN experiments, include sequences that are far beyond base training length and check whether retrieval anchors drift slowly or abruptly.
Your failure interpretation changes depending on whether drift appears gradual or abrupt.
A gradual drift usually suggests representational under-support.
An abrupt cliff usually indicates index-range mismatch or slope regime mismatch.

It is useful to separate “architecture issue” from “tokenizer issue.”
The attention family can be correct while tokenization pushes critical anchors to odd positions.
When anchors are fragmented across byte tokens, retrieval probes can look weaker even before architecture effects appear.
The first debugging action is to keep tokenization fixed and compare the same token-index pattern across models.
If behavior remains different after this control, then positional and KV decisions are likely the main lever.

This appendix also gives a structured way to handle uncertainty.
Do not overfit to a single prompt style.
Use a small matrix across workload family and context length and classify outcomes by whether the defect is deterministic, probabilistic, or hardware-dependent.
Deterministic defects usually indicate objective model geometry gaps.
Probabilistic defects indicate decoding and sampling interactions.
Hardware-dependent defects usually indicate engine kernels, thermal behavior, or memory fragmentation.
Only the deterministic lane should drive architectural replacement.

Benchmark interpretation should be done with decomposition.
A naive single number is insufficient.
You need three decomposition axes:
decode latency, cache hit behavior under repeated prefixes, and queue latency under concurrent small requests.
If decode improves but queue latency worsens, production pain may still rise with user impact.
If cache hits improve but TTFT worsens under repeated prefixes, prefill-side assumptions are likely wrong.
If all three improve together, then architecture is likely giving meaningful operational leverage.

In team reviews, define a decision confidence score using hard numbers and explicit thresholds.
For example, set minimum improvements for each candidate architecture on context band and concurrency band.
A single threshold can be “must beat baseline by at least 15 percent in TPS at 16K while reducing TTFT by at least 20 percent and not reducing retrieval quality by more than 3 percent under long-reference probes.”
This kind of threshold turns architecture discussion from taste into engineering governance.

One repeated mistake is mixing warmup and steady state.
The first requests pay model compilation, kernel selection, and context setup.
If those are measured in the same line item, a model with heavier startup may appear slower despite better steady-state performance.
For architecture choice, require warmup washout windows.
Then measure the same context tiers under an identical request cadence.
That makes results comparable and avoids selecting a model that is slower only because startup is one-time.

A robust lab also tracks generation quality at fixed token budgets.
For each context tier, fix output length and random seeds.
Then compare answer spans and reference matching.
A TPS lift with a large quality drop is not a deployment win.
A small TPS lift with stable retrieval and repeatability is often superior for quality-sensitive products.
The scorecard needs quality and cost in one table.

You may be tempted to include only one or two prompts.
Do not.
At least four families of prompts are needed for meaningful evidence.
Use clean factual recall, contradiction detection, code-edit follow-up, and reference-localization prompts.
Each of these families reveals different failure axes in positional and KV design.
Crossing all four gives a confidence surface instead of a single point estimate.

This section’s intent is to make architecture reviews repeatable by hand.
If a teammate can execute the same bench recipe and produce comparable numbers, the result has become operational knowledge.
That is what separates an engineering decision from an opinion.

A practical pattern for reporting is a signed summary table.
For each candidate include KV estimate, benchmark TPS, TTFT, queue depth under concurrency, and one long-reference correctness score.
Then include one line for risk and one line for rollback condition.
This table is short, auditable, and useful for incident drills.

You will still need a policy for model updates.
Once one architecture is selected, record why it was selected and what changes invalidate the choice.
This is part of quality governance and makes future upgrades faster.
A good example is: “If average context rises by 1.8x or concurrency rises by 2x, reassess head-sharing choice and positional scaling schedule.”
Without this, teams repeatedly repeat expensive debates.

The appendix now adds concrete formulas for engineering triage.
If an architecture with shared K/V lowers memory by factor $r$ and degrades quality by delta $\Delta Q$, define a decision score as

$$
S = \alpha\cdot(\Delta \text{TPS}) - \beta\cdot(\Delta Q) - \gamma\cdot\text{Risk}
$$

where risk includes rollback complexity, fallback difficulty, and monitoring coverage gaps.
A positive score means the trade is worthwhile in your constraints.
This is not a mathematical proof, but it forces explicit tradeoff weights.

The same score helps compare a sequence of deployments.
Apply it at initial design, after first production canary, and after one week of incidents.
If the score stays positive and risk decreases, the design is moving toward steady adoption.
If the score flips negative after incidents, re-open the decision tree and avoid overfitting to initial throughput.

For teams that use both MQA and GQA options, a useful guardrail is a per-endpoint policy.
Endpoints handling short, high-stakes requests can stay on higher-quality settings.
Heavy long-document endpoints can shift to lower-KV profiles when confidence thresholds are satisfied.
This is not model instability.
It is explicit routing by risk profile.

The same policy applies to Apple Silicon and edge devices.
Edge devices often tolerate less model family complexity and benefit from aggressive cache control.
This is where MQA frequently remains the pragmatic anchor for stable behavior.
If edge latency spikes after an update, move long-context tasks to server-assisted flow or retrieval compression while keeping local throughput high on short context.
The architecture should not force a one-size-fits-all posture.

Failure signatures should be documented for support.
Examples include periodic hallucination at large stride, lost references after a known token count, and queue jitter under mixed short and long requests.
Each signature should be tagged to a mitigation: positional reset, context chunking, model route switch, or engine flag.
If engineers can map one observed behavior to one mitigation, operational recovery time falls significantly.

The appendix also clarifies where MLA adoption usually succeeds.
Most successful MLA deployments first constrain quality sensitivity with a narrow task suite.
Then they keep a conservative fallback and only switch to full MLA profile after warmup and concurrency behavior are acceptable.
It is a staged control problem more than a one-time migration.

The same can be said about multi-head latent reconstruction.
Its quality uplift often depends on projection settings, quantization, and backend support.
Without those in place, theoretical reduction can look good while real behavior regresses.
So the implementation path should include a compatibility matrix and a controlled rollout stage.

Short-context workloads often mask long-context issues.
A model can pass short benchmarks while leaking errors at extended prompts.
This is why architecture choice should never be made from only short context.
In production with one-M context plans, the high-value tests are always in the upper context tier.
Short-context tests remain useful but secondary.

A useful question for every architecture review is this: what single class of failure is unacceptable and what is recoverable?
If recoverable failures can be caught and routed with policy, lower memory profiles may be acceptable.
If failures are silent and high-impact, favor architectures that preserve per-head geometric capacity even at higher cost.
This distinction keeps engineering decisions aligned with business risk.

Quantization can change these curves.
A quantization choice that compresses weights and KV with little quality loss can make MQA/GQA much more attractive.
A poor quantization choice can reverse that advantage.
Do not decide attention family before defining quantization policy.
Quantization and attention topology are coupled through memory and compute in production.

Another practical checkpoint is model card and license constraints.
Some model IDs expose architectural tags inconsistently.
A model you label as GQA may internally route heads in a variant-specific way.
Always verify with actual model config and serving backend output.
A single mislabel can waste a tuning cycle and break reproducibility.

For reproducibility, pin commit hashes, backend versions, and evaluation scripts.
The same model, prompt families, and measurement windows should be rerunnable on a different host.
Without this discipline, comparisons across teams are noisy and often misleading.
Reproducibility is the final anti-fragility mechanism in architecture work.

Long-run throughput plans should include queueing models.
A KV-lean architecture helps throughput only when the queue does not become the new bottleneck.
If queueing dominates, consider batching and scheduler policy before changing model family.
This is especially true when small changes in TTFT interact with bursty traffic.

If results remain contradictory, use staged deployment and rollback conditions.
Rollout first to a canary endpoint with strict thresholds.
If TTFT and quality thresholds hold for one week, widen rollout.
If thresholds fail, revert to the fallback family and archive the prompt slice that triggered regression.
This process keeps architecture changes safe by default.

Cross-team interpretation is often where reviews fail.
Infra teams optimize resource shape, product teams optimize quality, and platform teams optimize stability.
Architecture should serve the whole set.
Append this rule: do not optimize one dimension by more than two risk units unless at least one other dimension improves.
That prevents brittle deployments that look elegant in one graph and unstable in another.

As you finish this appendix, treat the architecture decision as living documentation.
Every future model version should run against this same decision template.
That way, your review standards remain stable even as models change from 8B to 70B families.
A stable template protects long-term engineering velocity.

## Failure Mode Gallery: How to map observed artifacts to architecture action

This module now maps a few common artifacts to the likely root layer.
If a model repeatedly favors very recent context and loses earlier references, positional compression or slope design is often involved.
If memory usage grows linearly as expected but latency explodes only at specific counts, kernel scheduling or quantization interactions are often responsible.
If quality degrades only on long factual questions with stable short-answer quality, retrieval pressure and context compression become the first suspects.

Artifacts should then be converted into triage actions.
For local-position collapse, test RoPE scaling and positional remapping.
For cache pressure with acceptable quality, test GQA or MLA adoption.
For quality instability, retain architecture but adjust prompts, retrieval compression, or rollback to MHA for sensitive paths.
This mapping helps incident responders choose interventions quickly.

In all cases, preserve all benchmark runs as machine-readable logs.
Human-readable summaries are useful, but machine-readable logs enable trend comparison after incidents.
A simple CSV plus prompt metadata is sufficient.
The appendix should therefore end with explicit logging fields, not narrative memory.

A practical logging schema stores model id, sequence length, context policy, architecture family, output length, TPS, TTFT, quality score, and rollback decision.
When architecture choices are revisited in a quarter, this schema allows apples-to-apples comparisons.
If the schema is absent, your earlier selection loses operational evidence.

A final operational pattern is “controlled complexity growth.”
You do not adopt every optimization simultaneously.
You adopt one change, observe, document,
and only then adopt the next.
This pattern is slower upfront but measurably cheaper than broad rewrites after hidden interactions.

As an explicit closing note, this appendix is not a competitor to full infra modules.
It complements memory and serving modules by giving a compact architecture-focused checklist and failure map.
Use it as the first pass before deeper engine-level benchmarking.
