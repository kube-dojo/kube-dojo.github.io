---
title: "Chapter 73: The Algorithmic Response"
description: "How DeepSeek-V2 addresses KV-cache memory pressure, and what its paper and public implementation paths establish."
sidebar:
  order: 73
---

:::tip[In one paragraph]
DeepSeek-V2's Multi-head Latent Attention caches a shared latent plus a decoupled positional key. Its paper reports cache and throughput gains against DeepSeek 67B under specified conditions. Public kernels and serving-backend guides offer implementation paths, but compatibility and actual adoption need separate evidence. This coda connects those technical questions to earlier hardware constraints without claiming that export controls caused the design.
:::

## Learning outcomes

- Distinguish where KV bottlenecks appear in Transformer serving and why that memory bottleneck, not only compute count, constrains throughput in long-context inference.
- Explain MLA's low-rank key-value joint compression in prose, including what is shared, what is per-head, and what gets reconstructed during attention.
- Identify which DeepSeek-V2 claims are directly documented (and where) versus where this chapter should avoid overextending inference.
- Identify public implementation and backend-selection paths, and the compatibility evidence needed before claiming that a deployment can use them.
- Connect the chapter's argument to Chapter 71's uneven adaptation thesis without asserting a single-cause, policy-only causation line.

The chip-war story leaves a question for architecture: how do teams change designs when hardware access is constrained?
Chapter 71 showed that export controls were not only legal instruments; they were structural pressures on the whole AI stack.
It also showed that HBM and advanced packaging sit at the center of practical frontier performance, not as an engineering afterthought.
The model case below lets us inspect one memory design and ask what would connect it to those wider pressures.

The central claim we now test is narrow and explicit:
How can an architecture reduce an inference-memory constraint? DeepSeek-V2 documents one approach; it does not establish that export controls caused the design.

The claim is not that policy creates breakthroughs ex nihilo, or that every actor who compresses memory has the same strategic intent.
It is that constrained contexts can make architecture changes more salient than they would otherwise be, and that DeepSeek-V2's Multi-head Latent Attention (MLA) is one documented response to a very real bottleneck.
This coda moves from Chapter 71's questions about supply-chain permission to the design of attention memory.

### The KV bottleneck under hardware constraint

The memory side of long-context inference is where these constraints become visible.
Transformer attention needs query, key, and value streams per token.
Inference wants to reuse keys and values efficiently, and that reuse is what everyone calls KV cache.
For frontier contexts, this cache is not just a small implementation detail.
It sets hard ceilings on batch size, sequence length, and cost per useful token.
A cache that scales badly turns good hardware into a capped pipeline.

Chapter 71 already described why hardware bottlenecks are not distributed evenly.
Countries and firms at the top of the value chain do not share the same depth of access to HBM, packaging, memory interconnect, and local integration capacity.
That asymmetry matters for long-context systems because memory pressure compounds with every extra layer:
chip supply, memory supplier choice, package-level bandwidth, and operating discipline.

Chapter 71's account of uneven access raises a corresponding systems question: who can run and maintain a memory-efficient design?
Per-request latency and per-token memory footprint are measurable parts of that question. Connecting them to export policy requires a deployment history, not just a similar pattern of constraints.

In practical terms, long-context inference has a hidden fixed cost before one adds model depth.
The larger the token budget and the larger the concurrency, the more the model spends keeping past context in a representable state.
A frontier architecture team must choose whether to spend that budget in raw compute, in memory channels, or in algorithmic compression.
If memory dominates, then architecture becomes the place where strategy is won or lost first.

Advanced memory pressure also affects who can benefit from a design.
A design that reduces cache can reward actors with expensive HBM and dense interconnect even more, if the design is difficult to adopt.
A design that is cheap to adopt can spread further into constrained deployments.
The same design can therefore look strategic and also uneven.
The interesting question is whether the unevenness tracks policy pressure or merely technical taste.

## MLA as a case study: DeepSeek-V2 and low-rank KV joint compression

DeepSeek-V2 introduced MLA in the same broad family as attention engineering, but with a specific target: reduce inference-memory burden while preserving quality.
The paper frames MLA as an architectural response to inference-time KV overhead, and describes it as a low-rank decomposition over keys and values, with a shared latent vector carrying the compressed memory signal through each layer.
That is the key shape.
Rather than caching full key and value tensors at each token step in the traditional form, MLA compresses and reuses them into a lower-dimensional representation.

The mechanism can be explained at a high level without treating it like a tutorial.
For each time step, keys and values are projected through a down-projection into a compressed latent space.
Those latent vectors are what carry the needed context information forward.
The model then reconstructs projected forms for attention calculation through learned up-projections.
In other words, MLA does not throw context away; it changes where and how that context is stored.

### Low-rank intuition without mathematical overstatement

The historical value of MLA is not just that it reduced memory. It is that it changed what had to be *kept* at serving time.
In standard MHA, each layer stores per-head key and value tensors for each token.
That means the cache is repeated in a way that scales with the number of tokens, the number of heads, and each head dimension.
This shape is what drives practical bottlenecks for long-context inference:
as soon as context or batch scales, cache memory rises first, often before compute utilization becomes the first visible limiter.

For a reader-friendly picture, think of one token's context as a set of per-head “sheets,” one sheet per head.
Each sheet is separate and mostly similar in role, because each head performs its own key/value projection.
MLA interposes a shared latent table `C_t` first.
That table is smaller and shared across heads, then head-specific projectors recover what each head needs.
The paper frames this as low-rank key-value joint compression: move shared structure into one latent object, and keep head specialization in reconstruction steps.

What this changes is where the bottleneck sits.
Before, the bottleneck sat in many per-head cache planes.
After, it sits in two terms:
- a shared latent term per token,
- plus per-head reconstruction terms that are no longer as heavy as full K/V storage.

In a simplified form, this is often written as `(d_c + d_h^R) × l` per token, where `d_c` is shared latent size, `d_h^R` is the per-head reconstruction reserve, and `l` is context length.
That compares against the broad MHA pressure term in proportional form with full per-head K/V tables.
So the mechanism is not just a clever rewrite in algebra.
It is a materially different storage topology.

That topology can be read directly in serving arithmetic.
In standard MHA, per-layer cache writes scale with the number of head slices that must be preserved per token.
In MLA, the shared latent is charged once per token per layer, while head-specific reconstruction is applied only through lightweight reconstruction operators.
This trade is operational: fewer hot cache bytes can unlock concurrency, while the reconstruction path shifts some cost toward compute.
If memory is the first bottleneck, this generally favors longer windows and higher request density.
If compute becomes the bottleneck, gains become backend-sensitive and depend on kernel scheduling.

The chapter should therefore frame MLA as a conditional architecture, not a universal replacement.
The same mechanism that reduces memory pressure can produce different returns across hardware profiles and serving stack choices.
That is why the RoPE and backend details are narratively paired in the paper.

The paper's RoPE discussion is essential here.
The same attention model uses positional encodings, and those encodings are not free to be rearranged by arbitrary projection choices.
If compression were applied through the wrong order, positional structure can be distorted before reconstruction and the downstream attention result changes.
So MLA decouples position-sensitive channels and compresses the components that remain stable under that separation.
This is why the positional treatment appears in the same family as compression details in the DeepSeek-V2 write-up: it is not ornamental, it is required for correctness under long-range decoding.

So the key answer is straightforward and checkable.
MLA reduces memory by changing which representation must be cached for every token.
Standard MHA stores most of what the model might reuse in duplicated per-head buffers.
MLA stores less duplication, then pays a reconstruction tax where needed.
That is the architecture change, not a slogan.

The most useful way to read this in 2026 is as an operational claim about cache shape rather than a generic "compression" slogan.
Standard attention forces each layer to persist per-head key/value tensors that are mostly similar in purpose but not shared in memory form.
MLA introduces a shared latent stage first, then reuses lightweight head-specific operators.
That means every new token now contributes to a smaller set of stored objects and a compact set of head transforms, rather than full per-head K/V tables.
The practical effect is not that "memory is less."
The practical effect is that some memory structures become shared and therefore scale with the sequence length in a way that is less expensive for long-context workloads.

This helps separate two common misunderstandings.
One is to treat MLA as only a clever linear algebra maneuver.
The second is to assume it only helps model-level parameter efficiency.
In the chapter's terms, the mechanism is mostly about serving-state geometry, not raw parameter count.
The paper ties this explicitly to inference behavior in the MLA formulation and to where the context state must be retained during decoding.

In standard MHA, each head owns a larger slice of cache.
In MLA, the shared latent (`d_c`) holds the common content structure and each head needs only a small reconstruction channel (`d_h^R`), which is why the memory budget expression is written in terms of `(d_c + d_h^R) × l`.
In concrete terms: each token still needs storage over context steps (`l`), but each step is represented by fewer bytes in the part that was duplicated across heads.
This is where the memory benefit is located.

The conceptual error to avoid is saying this is a complete removal of head-specific structure.
It is not.
MLA keeps the head-level specialization, but moves the expensive common part out of per-head repetition.
In the DeepSeek framing, the method is therefore conditional: where memory is the choke point, this redesign can materially improve serving headroom; where memory is not first in the bottleneck order, gains become mixed.

### Why this changes serving geometry

Inference math and systems economics can look independent, but this mechanism couples them directly.
In long-context serving, the sequence length and concurrency create two pressure channels at once:
KB-level KV state and token-level reuse.
MLA reduces one pressure channel by changing what must be kept hot.
That is not a free win, so DeepSeek's own paper still frames the method as a design tradeoff plus engineering integration task.

The paper's own wording in the abstract says MLA “guarantees efficient inference through significantly compressing the KV cache,” and Figure 1 plus Section 1 quantify this effect with explicit reported numbers.
In the documented DeepSeek-V2 setting, the authors report a **93.3% KV-cache reduction** and **5.76× maximum generation throughput** (arXiv:2405.04434, Abstract and §1 / Figure 1; MLA architecture details are in §2.1).
That numerical claim is the strongest place where we can say “documented effect” rather than “inferred adaptation.”

That reduction is most visible in production where context length and concurrent sequences are directly competing for memory capacity.
Holding hardware and serving policy fixed, a 93.3% KV reduction means the cache budget for one serving profile can be redistributed at scale.
In the simplest case, this enables longer contexts, larger concurrency, or lower reclaim pressure before paging-like fragmentation and throttling begin to dominate.
The chapter should preserve this conditional shape: this is a feasibility shift in the cache plane.

The production translation is therefore not just “less memory,” but more stable planning at model boundaries.
When one stack was previously forced to choose between context and throughput, MLA can change that trade-off frontier.
Even the paper's paired 5.76× throughput signal matters because it shows this is not only an accounting trick in a table; it is a deployment effect when the memory budget is the blocking variable.

This is also where the linear term `(d_c + d_h^R) × l` does real design work.
Every extra context token increases memory at a constant per-token cost in that reduced representation, rather than through duplicated per-head tables.
When memory pressure dominates, that linear reduction often shows up as fewer preemption events, fewer cache churn events, and more predictable scheduling under high concurrency.
Those are not headline benchmarks, but they are the things that matter to service reliability.

Read another way, the 93.3% figure is the gate opening statement.
The rest of the engineering is choosing what the platform gets after that gate opens:
longer effective context, higher concurrency, or tighter token-per-dollar envelopes.
DeepSeek's own 5.76× throughput signal gives one public anchor that this opened gate is meaningful in at least one operational profile.
The chapter should stay with conditional language here:
the mechanism improves one slice of the system envelope, and the exact win appears only if a deployment is actually memory-bound.

At the same time, this does not grant universal claims.
The same 93.3% number applies to the published DeepSeek-V2 architecture slice, not all checkpoints, not all hardware, and not all long-context workloads.
The next question is what public implementation paths make inspectable, separately from the paper's reported results.

The architecture in the paper is not an isolated software patch.
It sits in the same section family that compares attention variants and discusses cache size in operational terms.
The authors also describe companion choices around RoPE handling and the interaction between compression and inference pathways.
That matters historically, because the method became real not because one equation was elegant, but because it had to be integrated into a full transformer flow.
If a model family cannot keep one part of the pipeline coherent after compression, the claim of efficiency collapses into extra engineering debt.

A historical analogy is useful: we can think of the cache as a customs checkpoint inside the model.
Without compression, every token carries a bulky record.
With low-rank joint compression, the checkpoint still exists, but the record is standardized into a smaller passport.
The question is whether the passport keeps enough information to preserve behavior.
In the DeepSeek-V2 case, the design is presented as doing so.

The section that matters for the book's argument is not only that a memory claim exists.
It is that MLA is offered as an architectural response, with public implementation options whose model and version compatibility still need checking.
That is where constraints stop sounding like policy prose and start sounding like production reality.

## Open implementation half: what became materially shared

DeepSeek's open publication path matters because it changes how a mechanism exits the paper.
The [pinned FlashMLA README](https://github.com/deepseek-ai/FlashMLA/blob/0f11e178da1f67becb087a324b400854931ec3e3/README.md) describes the repository's attention kernels, available for inspection and possible integration. Public availability does not establish the authors' reuse intent or actual adoption by other teams.

At runtime, the value is where memory geometry and kernel layout meet.
The inspected README distinguishes prefill and decode kernels and documents hardware/software requirements. Its 2026.09.30 notice reports removal of Hopper and earlier-model support and changes to KV-cache formats. It names V3/V3.2/V4.0, not V2; neither that list nor its historical-commit link establishes V2 compatibility here.

Claims about tiling, shared memory or warp-level reductions need inspection of the relevant pinned implementation or technical report. The README alone does not establish those details or a measured throughput outcome for this chapter's model.

The concrete next layer is framework integration.
The [pinned vLLM guide](https://github.com/vllm-project/vllm/blob/f3871c3cbf8a608f7ee833ec4c2c5277f77bee41/docs/design/attention_backends.md), MLA Backends, documents separate prefill and decode selection. The [pinned SGLang guide](https://github.com/sgl-project/sglang/blob/74c08f3dc5d98dddf052ba03122fc084a31a0269/docs/docs/advanced_features/attention_backend.mdx) explicitly makes support dependent on model, platform and backend, including page-size constraints. These are configuration paths where supported, not unrestricted portability guarantees.

An operator would still need to validate model support, precision, hardware, traffic conditions and recovery behavior. The inspected backend menus do not demonstrate an equivalent fallback, an observability setup or successful production switching.

In this sense, vLLM and SGLang illustrate the same pattern with different mechanics:
backend abstractions offer one route to evaluate compatible kernels. They are neither the only integration route nor evidence that a particular stack has standardized the method.

A useful framing for this chapter is:
the paper, public kernel code and backend configuration describe different layers of a possible implementation path. Their presence does not verify the historical sequence of integration or routine operational use.

### What this does and does not prove about open-source adoption

Open-source visibility is not the same as adoption depth.
Public code lets maintainers investigate integration. Whether the same model and workload can use a particular backend requires a version-matched compatibility check; the three documentation snapshots are not a tested stack.

The practical consequence is an expanded candidate set, not universal equivalence.
The model family that published the optimization is not the only site that can benefit.
But each adopter still inherits migration cost: compiler flags, backend versioning, and observability policy.
So the chapter should explicitly state that “open” is a lower entry barrier, not a guaranteed outcome.

For this chapter, the strongest claim is narrower and more defensible:
Public kernel and framework documentation identify implementation options. Establishing V2 reuse or adoption requires a compatible historical version and evidence of actual integration.

The case therefore has two layers of implementation documentation, not adoption measurements:
1) public kernels and documentation;
2) documented backend-selection paths in serving frameworks.

What we should not overstate is that this automatically implies broad parity.
Diffusion in infrastructure is still uneven because each stack pays migration cost in compilers, scheduling assumptions, and deployment observability.
In that sense, open-source diffusion appears as a widening of the candidate set, not a collapse of friction.

## Honest framing: causation versus correlation

The DeepSeek paper does not claim, and cannot be used to claim here, that MLA was an explicit legal-adaptation strategy to U.S. export controls.
That causation claim is not established in the paper itself.
The book should not insert that story from convenience.
We can say the opposite:
constrained-hardware environments can select for architecture that reduces bottleneck dependence.
MLA documents an inference-efficiency design; it does not establish that policy selected that design or prove a particular intent.

This distinction matters for credibility.
The chapter should be explicit that multiple forces can converge:
scale pressure, cost pressure, model quality pressure, and supply pressure.
Export controls are one visible macroforce.
They are not the only causal engine.
That is a cleaner historical sentence than claiming intention.

We also avoid inflated side claims about other techniques named in social commentary.
The inspected record contains the MLA paper and public kernel/backend documentation; historical V2 compatibility and deployment use remain separate questions.
Everything else belongs to a different research note unless supported directly.
That is the discipline this chapter is trying to restore.

For governance, that means two layers at once.
One layer says policy can influence what architectures are financially and operationally plausible.
The second says architecture can then diffuse through open kernels and widen who can benefit from those same constraints.
The direction is not a single line.
It is a loop.

## Limits and counter-examples: where adaptation is not automatic

The previous sections stay close to what the public record supports, but they also need a reverse edge.
Algorithmic substitution does not erase constraints; it reorders them.
Chapter 71’s uneven adaptation frame predicts this shape:
actors with more mature tooling and integration depth can often convert policy pressure into architectural advantage,
while others face a longer lag even if the idea is visible.

The direct counter-example in the same direction is simple: reducing KV cache does not solve compute-bound or bandwidth-bound deployment.
If a stack is already dominated by scheduler contention, quantization overhead, network latency, or I/O bottlenecks, a cache reduction alone does not produce proportional gains.
A second counter-example is quality sensitivity.
MLA is an optimization design with explicit quality-preservation assumptions.
It is not a free option for every precision target, training stage, or evaluation regime.

There are also policy-level limits.
Policy making an architectural response more likely or valuable remains a historical hypothesis here.
It cannot prove a one-to-one causal line from every legal control to every design detail.
The stronger claim would be stronger than the sources can bear, and it would become deterministic where history should remain structural.

This uncertainty is not weakness.
It is the honest edge of causal method.

What the case does not tell us is just as important as what it does:
- it documents an architecture and an author-reported model comparison, not global optimality or successful substitution under export controls,
- it does not measure training-time impact across all domains,
- it does not prove that open publication alone guarantees broad parity,
- and it does not claim that open-source diffusion by itself overcomes unequal hardware and maintenance environments.

The practical implication of that boundary is simple:
distinguish the reported memory result from the additional evidence needed for hardware-specific integration and use.

Those are not caveats added for balance language only.
They are the actual epistemic boundary of what this chapter can infer from the public record.
A robust historical claim needs to tell the reader what can be generalized and what cannot.
Here we can generalize that memory-aware design can be an adaptation path; we cannot generalize that every constraint produces the same design priority.

That distinction is why this chapter's strongest claim remains procedural:
identify bottleneck geometry, test architecture-level substitution, and then test whether the substitution is deployable in an ecosystem with its own compatibility limits.
The evidence supports that sequence and does not support a more sweeping deterministic narrative.

A useful way to keep this chapter honest is to treat this as a structured claim set with explicit boundaries.
The chapter's first claim is empirical and narrow: MLA compresses KV state through a low-rank decomposition and the paper reports strong cache gains.
The second claim concerns implementation: public kernels and backend documentation offer paths whose compatibility must be checked. The proposed historical link to constrained teams' adoption remains a research question, not a measured outcome.
The temptation is to collapse the documented mechanism and the historical hypothesis into a single political causation sentence.
The stronger argument avoids that collapse.

So the case does not license a simple timeline where policy pressure directly writes a kernel architecture, and architecture then instantly levels global capability.
At best, policy alters the optimization surface.
Then design teams test alternatives.
Then infrastructure choices determine whether alternatives are absorbable.
Only after these steps does observed adoption occur.
That sequence is why this chapter is intentionally modest, and why it aligns with the uneven adaptation argument instead of replacing it.

So the chapter's thesis remains modest and strong.
The mechanism and implementation options are documented; successful integration must be established for the chosen model and stack.
Chapter 71's uneven-adaptation frame suggests asking which teams can use an architectural option, and how long integration takes.
Answering that requires evidence about particular stacks and deployments, beyond the availability of a paper or repository.

The historical question is where a constraint changes design choices, and how we could establish that change.
Here the paper makes an attention-layer design inspectable; whether policy moved capability formation into that layer remains unproved.
If this pattern generalizes, then future constraint episodes will also show design moves at the infrastructure margin.
That is not a deterministic prediction.
It is a pattern-level prediction conditioned on where bottlenecks sit and which actors can afford compatibility work.

What the chapter should therefore not do is imply that every architecture tweak produces broad strategic balance.
It is possible for two designs to be equally clever and still unequally consequential because one design fits available compiler and runtime ecosystems better.
It is also possible for one design to open memory for one workload profile and close it for another.
These are the kinds of boundary conditions that keep infrastructure history from becoming a single story of winners and losers.

For readers mapping this to the prior chapter, the strongest takeaway is to treat adaptation as a layered process.
Chapter 71 described where policy pressure fell hardest and where institutions diverged.
This technical epilogue documents a memory strategy and asks how hardware constraints and stack compatibility could affect its use. It does not establish policy-driven design or a change in who actually adopted it.

## What this coda changes in the series narrative

MLA marks a new frontier in the chapter's larger arc.
The chip war made the stack visible by showing where export and hardware controls bind.
MLA shows that, once memory bottlenecks are severe, binding can move upward into model-level memory strategy.
The “where” of competition becomes less about only which die can be bought and more about which memory strategy can be run under constrained batch and context conditions.

The asymmetry from Chapter 71 appears again here.
Actors with access to advanced packaging and high-performance memory supply still enjoy a lower-friction path.
Actors constrained in those layers can still compete if a memory strategy is open, portable, and integrated into tooling they can operate.
But in practice, adoption is mediated by stack maturity and local ecosystem support.
This is not a universal equalizer.
It is an unequal redistribution of design surface.

The policy implication is therefore subtle.
We are no longer watching only “restrictions” and “substitutes” as macroeconomic abstractions.
We are watching the micro-structure of where substitution is expensive and where it is cheap.
An architecture that stores memory differently can be one form of structural adaptation, and that adaptation can spread through open repos with less institutional friction than an entire toolchain replacement.

The chapter connects to the book's export-control arc by posing a testable question about adaptation. DeepSeek-V2 documents a response to KV-cache pressure; the inspected sources do not establish that legal controls produced it. Tracing that historical link would require evidence beyond the architecture and benchmark.

The next historical question now follows naturally.
If HBM scarcity can make inference kernels more valuable than raw parameter count, then infrastructure policy will remain a research variable, not only a commercial one.
The AI system will continue to evolve in the space between laws, materials, and memory equations.
And in this space, Chapter 73 leaves us with one durable lesson.
An architectural option can be inspected before its historical consequences are known.
The next task is to trace how that option becomes usable capability, and for whom.

At the same time, this chapter's own limits should be read forward.
We do not claim exhaustive impact.
The documented pieces are an inference-memory problem, a proposed representation and public implementation paths. Their connection to operational reuse remains testable rather than verified here.

This technical epilogue leaves a cleaner problem statement for future histories:
how do design substitutions in one layer propagate backward into procurement, compiler stack maturity, and eventually competitive positioning?
If future histories keep this thread explicit, they will avoid the common failure mode of turning each policy shock into a myth of deterministic causation.

## Common mistakes / misconceptions

- Thinking MLA only helps with latency and ignoring its role in per-request memory sustainability.
- Treating the 93.3% figure as a global guarantee across all architectures, prompts, and hardware profiles.
- Concluding that open publication means instant equal adoption regardless of serving stack maturity.
- Misreading this chapter as “policy-created innovation” rather than “constraint-aligned response with documented effects.”
- Using the chapter to imply that every memory optimization can be mapped to a single geopolitical intent.

### Why this is the right kind of example for the series

Some historical claims fail because they confuse an innovation with an outcome.
MLA is a useful anchor because the paper links the mechanism to the memory bottleneck directly, and the mechanism is then carried into a public repository.
That gives us two kinds of documentation: a paper's result and public implementation options whose compatibility needs checking.
The book can use both without overstretching.

A second strength is that this is not framed as a miracle optimization.
The text itself says MLA sits among familiar pressure points: sequence length, attention overhead, and inference efficiency.
That matters because it keeps MLA in the same continuity as prior engineering stories.
The reader is not asked to believe a completely new paradigm.
They are asked to notice a specific bottleneck turned into a specific structural design.

If we ignore such examples, the export-control argument risks ending as a purely legal chronology.
If we overstate them, we get mythology.
So this chapter's restraint is the historical method itself.

The middle of the 2020s generated many narrative overreaches about who replaced what where they replaced it.
The safe method is: describe the pressure, map the mechanism, then test diffusion.
MLA supplies a documented mechanism and implementation leads; measuring diffusion remains further work.
It is not a universal answer to every AI infrastructure constraint.
It is a documented point where constraints and architecture met.

This also aligns with Chapter 71's broader point about uneven adaptation.
One node in the ecosystem can absorb control pressure by changing design.
Another node can absorb it by changing suppliers.
Another can absorb it by changing service geography.
MLA supplies a design to investigate within that framework; the policy-to-design link still needs its own evidence.

A design node has a special historical texture.
Compared to procurement disputes, design moves leave code, tables, reproducibility signals, and maintenance footprints.
Even if adoption is partial, the mechanism can be copied, modified, and redeployed.
That is why design responses are easier to trace than policy rhetoric.

## What this technical epilogue changes for the book's closure

The chapter's title says “algorithmic response” on purpose.
The closing chapters pose three connected questions: which hardware can be obtained, what infrastructure can support it, and what a model must retain while it runs.
Chapter 71 examines supply-chain permission; Chapter 72 examines physical capacity.
This coda adds a specific memory design to investigate alongside those constraints.

That clarifies the infrastructure close in Chapter 72.
The AI system no longer looks like an either/or sequence of “policy then compute.”
It is a closed loop where policy shifts what is worth computing,
hardware shifts what is affordable to compute,
and architecture shifts which forms of that computation remain usable.

The practical result is still uneven.
A compatible stack may be able to adopt an MLA implementation, but these sources do not establish adoption speed or success for either advanced or constrained teams.
This is not a tidy leveling story.
The distribution and timing of any benefit remain questions for deployment evidence.

The final lesson is to keep technical results and historical causation distinct. DeepSeek-V2 provides a memory-aware architecture and a bounded author-reported comparison. The role of export controls in producing that outcome remains unestablished.

As we leave the chapter, the historical burden is to keep the chain tight:
policy regime, hardware constraint, memory pressure, architectural choice, open implementation, and adoption each need their own evidence. A documented middle step does not prove the entire chain.

## Self-assessment

1. Why does this chapter treat MLA as a "case of constrained architectural response" instead of "proof of policy intent"?
2. In one paragraph, describe MLA's storage change and why this affects long-context generation more directly than raw parameter count alone.
3. State the two exact DeepSeek-V2 numbers used in this chapter and trace each to a precise paper location.
4. Distinguish FlashMLA's public availability from evidence of V2 compatibility or adoption. Which version and deployment facts would you check next?
5. Relate the technical case to Chapter 71's uneven-adaptation argument. What further evidence would establish a causal connection to export controls?

## Sources

### Primary

- [DeepSeek-AI. "DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model." arXiv:2405.04434v5, 2024.](https://arxiv.org/html/2405.04434v5) — §§2.1.2–2.1.4 and Table 1 for cache accounting; abstract for the ratios; §3.2.3 Training Costs/Inference Efficiency for baseline and setup.
- [DeepSeek-AI. "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning." arXiv:2501.12948, 2025.](https://arxiv.org/abs/2501.12948)
- [DeepSeek-AI. FlashMLA README, commit 0f11e178da1f67becb087a324b400854931ec3e3.](https://github.com/deepseek-ai/FlashMLA/blob/0f11e178da1f67becb087a324b400854931ec3e3/README.md) — Introduction, breaking-change notice and Requirements; inspected October 23, 2026. This snapshot does not establish historical V2 compatibility.
- [DeepSeek-AI. TileKernels repository (GPU kernel project using TileLang).](https://github.com/deepseek-ai/TileKernels)
- [TileLang. TileLang DSL repository.](https://github.com/tile-ai/tilelang)
- [SGLang. Attention backend guide, commit 74c08f3dc5d98dddf052ba03122fc084a31a0269.](https://github.com/sgl-project/sglang/blob/74c08f3dc5d98dddf052ba03122fc084a31a0269/docs/docs/advanced_features/attention_backend.mdx) — introduction, MLA Backends and page-size constraints; inspected October 23, 2026, without runtime validation.
- [vLLM. Attention backends, commit f3871c3cbf8a608f7ee833ec4c2c5277f77bee41.](https://github.com/vllm-project/vllm/blob/f3871c3cbf8a608f7ee833ec4c2c5277f77bee41/docs/design/attention_backends.md) — MLA prefill/decode selection; inspected October 23, 2026. Generated table includes were not expanded.
- [BIS. Export Controls for Certain Electronic Devices, Computers, and Advanced Computing Items.](https://www.federalregister.gov/citation/87-FR-62186)
- [Chris Miller, *Chip War: The Fight for the World's Most Critical Technology* (Scribner, 2022).](https://books.google.com/books/about/Chip_War.html?id=fUVdEAAAQBAJ)
- [A Survey on Transformer Compression (arXiv:2402.05964).](https://arxiv.org/abs/2402.05964v2)
