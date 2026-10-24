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
- Explain MLA's shared latent and positional-key cache, distinguishing conceptual up-projections from their absorption during inference.
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

Chapter 71's account of uneven access raises a corresponding systems question: who can run and maintain a memory-efficient design? Per-request latency and per-token memory footprint are measurable parts of that question. Connecting them to export policy requires a deployment history, not just a similar pattern of constraints.

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
For each token, the attention input is down-projected into a latent vector from which the content keys and values are defined through learned up-projections.
Those latent vectors are what carry the needed context information forward.
Those equations describe the representation; they do not require materializing full keys and values during inference. Section 2.1.2 explains how the up-projections can be absorbed into the query and output projections. Quality still needs evaluation; compression is not a claim of lossless recovery of an arbitrary model's cache.

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
The paper frames this as low-rank key-value joint compression: use a shared latent representation while retaining head-specific learned projections.

What this changes is where the bottleneck sits.
Before, the bottleneck sat in many per-head cache planes.
After, it sits in two terms:
- a shared latent term per token,
- plus a shared positional key for decoupled rotary position embedding (RoPE).

Table 1 of the [DeepSeek-V2 paper, v5](https://arxiv.org/html/2405.04434v5) gives `(d_c + d_h^R) × l` cached elements per token across `l` layers. Here `d_c` is the KV compression dimension and `d_h^R` is the per-head dimension of the decoupled queries and key; it is not a reconstruction reserve.
The MHA comparison is `2 × n_h × d_h × l` elements per token. A sequence of `N` cached tokens multiplies either count by `N`; storage bytes additionally depend on precision and representation. Neither expression uses `l` for context length.
So the mechanism is not just a clever rewrite in algebra.
It is a materially different storage topology.

That topology can be read directly in serving arithmetic.
In standard MHA, per-layer cache writes scale with the number of head slices that must be preserved per token.
In MLA, each layer caches the shared latent and the decoupled positional key. Projection absorption means that a mandatory full-key/value reconstruction cost cannot be read off the conceptual equations alone (§2.1.2).
If memory is the first bottleneck, this generally favors longer windows and higher request density.
If compute becomes the bottleneck, gains become backend-sensitive and depend on kernel scheduling.

The chapter should therefore frame MLA as a conditional architecture, not a universal replacement.
The same mechanism that reduces memory pressure can produce different returns across hardware profiles and serving stack choices.
RoPE compatibility and backend implementation therefore need separate attention.

The paper's RoPE discussion is essential here.
The same attention model uses positional encodings, and those encodings are not free to be rearranged by arbitrary projection choices.
Section 2.1.3 explains that applying RoPE to the content keys would place a position-dependent matrix between projections and prevent the absorption described above. Equations 14–19 instead introduce decoupled positional queries and a shared positional key. The key must also be cached; the queries are not part of that cache term.

So the key answer is straightforward and checkable.
MLA reduces memory by changing which representation must be cached for every token.
Standard MHA caches each head's keys and values; separate heads need not contain identical data.
MLA stores a compressed latent plus positional information, while its inference algebra permits avoiding explicit reconstruction of the full content keys and values.
That is the architecture change, not a slogan.

The most useful way to read this in 2026 is as an operational claim about cache shape rather than a generic "compression" slogan.
Standard attention forces each layer to persist per-head key/value tensors that are mostly similar in purpose but not shared in memory form.
MLA introduces a shared latent stage and a decoupled positional key. New tokens add cache entries; learned projection weights are not new per-token cache objects.
The practical effect is not that "memory is less."
The practical effect is that some memory structures become shared and therefore scale with the sequence length in a way that is less expensive for long-context workloads.

This helps separate two common misunderstandings.
One is to treat MLA as only a clever linear algebra maneuver.
The second is to assume it only helps model-level parameter efficiency.
In the chapter's terms, the mechanism is mostly about serving-state geometry, not raw parameter count.
The paper ties this explicitly to inference behavior in the MLA formulation and to where the context state must be retained during decoding.

In standard MHA, each head owns a larger slice of cache.
In MLA, `d_c` counts the latent dimensions and `d_h^R` the dimensions of the shared decoupled key cached at each layer. Multiplying their sum by the layer count `l` gives the per-token element count, not the whole sequence's bytes.
Context length enters through the number of cached tokens `N`; Table 1 explicitly excludes storage precision from its element counts.
This is where the memory benefit is located.

The conceptual error to avoid is saying this is a complete removal of head-specific structure.
It is not.
MLA keeps the head-level specialization, but moves the expensive common part out of per-head repetition.
The operational inference is conditional: reduced cache may improve serving headroom where memory is the choke point; other bottlenecks require their own measurements. This is a deployment consideration, not the paper's stated framing.

### Why this changes serving geometry

Inference math and systems economics can look independent, but this mechanism couples them directly.
In long-context serving, the sequence length and concurrency create two pressure channels at once:
KB-level KV state and token-level reuse.
MLA reduces one pressure channel by changing what must be kept hot.
A smaller cache does not establish every deployment's performance; the need to test integration and remaining bottlenecks is this chapter's engineering inference.

The paper's abstract reports **93.3% KV-cache reduction** and **5.76× maximum generation throughput** compared with DeepSeek 67B. The abstract also gives V2's mixture-of-experts model sizes: 236B total parameters and 21B active per token. The dense 67B baseline is identified in §3.2.3, Training Costs; that subsection does not establish the cache-reduction accounting.
The throughput setup matters: §3.2.3, Inference Efficiency, specifies one node with eight H800 GPUs for V2's measurement and the prompt/generation-length distribution from the DeepSeek 67B service. It does not specify the 67B comparison hardware there. V2 deployment also uses FP8 parameters and KV-cache quantization averaging six bits per element. The result therefore cannot be attributed to MLA alone.

As an engineering inference, reducing per-token cache can leave room for longer sequences or more concurrent requests when memory is the limiting resource. The reported percentage is a model comparison, not a controlled measurement holding every architecture and serving choice fixed. Its full accounting needs attention dimensions, layer counts and precision; §3.2.3 does not state whether quantization contributes to the 93.3% figure.

The 5.76× result is reported for the authors' evaluated configuration, rather than a guaranteed memory-bound deployment effect. A different stack needs its own comparison before claiming the same trade-off improvement.

This is also where the linear term `(d_c + d_h^R) × l` does real design work.
For a fixed model, every additional cached token adds the Table 1 element count. Fragmentation, preemption, cache churn and scheduling reliability require separate measurements; the reported cache and throughput figures do not establish those outcomes.

The practical question is what a tested deployment can do with a different cache shape. Longer context, higher concurrency and lower cost are possible objectives, not interchangeable conclusions from one benchmark.

At the same time, this does not grant universal claims.
The 93.3% number remains the paper's V2-versus-67B claim, not a property of every checkpoint, hardware platform or long-context workload. Public implementation paths are a separate kind of evidence.

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
The next step is to inspect compatibility requirements and test an implementation in a specified environment.

## Open implementation half: what became materially shared

DeepSeek's open publication path matters because it changes how a mechanism exits the paper.
The [pinned FlashMLA README](https://github.com/deepseek-ai/FlashMLA/blob/0f11e178da1f67becb087a324b400854931ec3e3/README.md) describes the repository's attention kernels, available for inspection and possible integration. Public availability does not establish actual adoption by other teams.

At runtime, the value is where memory geometry and kernel layout meet.
The inspected README distinguishes prefill and decode kernels and documents hardware/software requirements. Its 2026.09.30 notice reports removal of Hopper and earlier-model support and changes to KV-cache formats. It names V3/V3.2/V4.0, not V2; neither that list nor its historical-commit link establishes V2 compatibility here.

Claims about tiling, shared memory or warp-level reductions need inspection of the relevant pinned implementation or technical report. The README alone does not establish those details or a measured throughput outcome for this chapter's model.

The concrete next layer is framework integration.
The [pinned vLLM guide](https://github.com/vllm-project/vllm/blob/f3871c3cbf8a608f7ee833ec4c2c5277f77bee41/docs/design/attention_backends.md), MLA Backends, documents separate prefill and decode selection. The [pinned SGLang guide](https://github.com/sgl-project/sglang/blob/74c08f3dc5d98dddf052ba03122fc084a31a0269/docs/docs/advanced_features/attention_backend.mdx) explicitly makes support dependent on model, platform and backend, including page-size constraints. These are configuration paths where supported, not unrestricted portability guarantees.

An operator would still need to validate model support, precision, hardware, traffic conditions and recovery behavior. The inspected guides describe selection-time priority and fallback order, not failure recovery during serving, an observability setup or successful production switching.

In this sense, vLLM and SGLang illustrate the same pattern with different mechanics:
backend abstractions offer one route to evaluate compatible kernels. They are neither the only integration route nor evidence that a particular stack has standardized the method.

A useful framing for this chapter is:
the paper, public kernel code and backend configuration describe different layers of a possible implementation path. Their presence does not verify the historical sequence of integration or routine operational use.

### What this does and does not prove about open-source adoption

Open-source visibility is not the same as adoption depth.
Public code lets maintainers investigate integration. Whether the same model and workload can use a particular backend requires a version-matched compatibility check; the three documentation snapshots are not a tested stack.

The practical consequence is an expanded candidate set, not universal equivalence.
The model family that published the optimization is not the only site that can benefit.
A prospective integration needs checks of compiler flags, backend versions and observability requirements before its cost can be assessed.
Whether public availability lowers the entry barrier is one of the questions those checks must answer.

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

For governance, what evidence would connect a policy change to an architectural choice and then to a documented deployment?

## Limits and counter-examples: where adaptation is not automatic

The previous sections stay close to what the public record supports, but they also need a reverse edge.
Algorithmic substitution does not erase constraints; it reorders them.
Chapter 71's uneven-adaptation frame suggests asking how tooling and integration capacity affect the options available to particular teams.

Reducing KV cache does not by itself guarantee a speedup when another resource dominates. It may also affect memory traffic; a bandwidth-bound workload is not automatically excluded from benefiting.
If a stack is already dominated by scheduler contention, quantization overhead, network latency, or I/O bottlenecks, a cache reduction alone does not produce proportional gains.
A second counter-example is quality sensitivity.
MLA is an optimization design with explicit quality-preservation assumptions.
It is not a free option for every precision target, training stage, or evaluation regime.

There are also policy-level limits.
This chapter treats a causal link between policy and architectural choice as a hypothesis.
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
The second claim concerns implementation: public kernels and backend documentation offer paths whose compatibility must be checked. The proposed historical link to constrained teams' adoption remains a research question, not a measured outcome. The temptation is to collapse the documented mechanism and the historical hypothesis into a single political causation sentence.
The stronger argument avoids that collapse.

So the case does not license a simple timeline where policy pressure directly writes a kernel architecture, and architecture then instantly levels global capability.
At best, policy alters the optimization surface.
Then design teams test alternatives.
Then infrastructure choices determine whether alternatives are absorbable.
Only after these steps does observed adoption occur.
That sequence is why this chapter is intentionally modest, and why it aligns with the uneven adaptation argument instead of replacing it.

So the chapter's thesis remains modest and strong.
The mechanism and implementation options are documented; successful integration must be established for the chosen model and stack.
Chapter 71's uneven-adaptation frame suggests asking which teams can use an architectural option, and how long integration takes. Answering that requires evidence about particular stacks and deployments, beyond the availability of a paper or repository.

The historical question is where a constraint changes design choices, and how we could establish that change.
Here the paper makes an attention-layer design inspectable; whether policy moved capability formation into that layer remains unproved.
If later evidence establishes such a pattern and it generalizes, future constraint episodes may also show design moves at the infrastructure margin.
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

MLA brings the infrastructure story down to a concrete design question: what must a model keep in memory while it runs, and what alternatives can be tested? To understand who can use such a design, a history would need compatibility records, integration effort and documented deployments. Those records could then be compared across teams with different hardware access. Whether public code lowers costs or widens access is part of that investigation. A useful comparison would examine the work required to make a particular model, backend and hardware configuration operate together.

The chapter connects to the book's export-control arc by posing a testable question about adaptation. DeepSeek-V2 documents a response to KV-cache pressure; the inspected sources do not establish that legal controls produced it. Tracing that historical link would require evidence beyond the architecture and benchmark.

The next historical question now follows naturally.
If HBM scarcity can make inference kernels more valuable than raw parameter count, then infrastructure policy will remain a research variable, not only a commercial one.
The AI system will continue to evolve in the space between laws, materials, and memory equations.
And in this space, Chapter 73 leaves us with one durable lesson.
An architectural option can be inspected before its historical consequences are known. The next task is to trace whether and how that option becomes usable capability, and for whom.

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
The paper links MLA to an inference-memory problem; public kernel documentation describes implementation options. Those are two kinds of evidence to inspect, rather than a documented sequence of integration and use.
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
The closing chapters pose three connected questions: which hardware can be obtained, what infrastructure can support it, and what a model must retain while it runs. Chapter 71 examines supply-chain permission; Chapter 72 examines physical capacity. This coda adds a specific memory design to investigate alongside those constraints.

One analytical frame for the closing chapters is a feedback loop: policy may change which computations are feasible, hardware may change their cost, and architecture may change their resource needs. Testing that frame requires tracing each link in a particular case.

A compatible stack may be able to adopt an MLA implementation, but these sources do not establish adoption speed or success for either advanced or constrained teams.
This is not a tidy leveling story.
The distribution and timing of any benefit remain questions for deployment evidence.

The final lesson is to keep technical results and historical causation distinct. DeepSeek-V2 provides a memory-aware architecture and a bounded author-reported comparison. The role of export controls in producing that outcome remains unestablished.

As we leave the chapter, the historical burden is to keep the chain tight:
policy regime, hardware constraint, memory pressure, architectural choice, open implementation, and adoption each need their own evidence. A documented middle step does not prove the entire chain.

## Self-assessment

1. Why does this chapter treat MLA as a "case of constrained architectural response" instead of "proof of policy intent"?
2. In one paragraph, describe MLA's storage change and why this affects long-context generation more directly than raw parameter count alone.
3. State the two reported DeepSeek-V2 numbers, their baseline and source locations, and the throughput setup that limits their interpretation.
4. Distinguish FlashMLA's public availability from evidence of V2 compatibility or adoption. Which version and deployment facts would you check next?
5. Relate the technical case to Chapter 71's uneven-adaptation argument. What further evidence would establish a causal connection to export controls?

## Sources

### Primary

- [DeepSeek-AI. "DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model." arXiv:2405.04434v5, 2024.](https://arxiv.org/html/2405.04434v5) — §§2.1.2–2.1.4 and Table 1 for cache accounting; abstract for both ratios and model sizes; §3.2.3 Training Costs for the dense baseline and Inference Efficiency for the throughput setup.
- [DeepSeek-AI. FlashMLA README, commit 0f11e178da1f67becb087a324b400854931ec3e3.](https://github.com/deepseek-ai/FlashMLA/blob/0f11e178da1f67becb087a324b400854931ec3e3/README.md) — Introduction, breaking-change notice and Requirements; inspected October 23, 2026. This snapshot does not establish historical V2 compatibility.
- [SGLang. Attention backend guide, commit 74c08f3dc5d98dddf052ba03122fc084a31a0269.](https://github.com/sgl-project/sglang/blob/74c08f3dc5d98dddf052ba03122fc084a31a0269/docs/docs/advanced_features/attention_backend.mdx) — introduction, MLA Backends and page-size constraints; inspected October 23, 2026, without runtime validation.
- [vLLM. Attention backends, commit f3871c3cbf8a608f7ee833ec4c2c5277f77bee41.](https://github.com/vllm-project/vllm/blob/f3871c3cbf8a608f7ee833ec4c2c5277f77bee41/docs/design/attention_backends.md) — MLA prefill/decode selection; inspected October 23, 2026. Generated table includes were not expanded.
- [BIS. Advanced-computing and semiconductor-manufacturing export-control announcement, October 7, 2022.](https://www.bis.gov/press-release/commerce-implements-new-export-controls-advanced-computing-semiconductor-manufacturing-items-peoples) — dated heading and opening paragraphs for the historical policy context; not evidence of MLA's design motives.
