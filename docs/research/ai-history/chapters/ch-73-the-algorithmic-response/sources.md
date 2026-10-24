# Sources: Chapter 73

Initial inspection 2026-10-23; cache-accounting checkpoint 2026-10-24. Green means independently corroborated and reviewed; Yellow means source-visible but pending those checks; Red means unsupported for drafting. Retrieval and file presence grant no clearance. This packet has **0 Green, 8 Yellow, 2 Red** claims.

## Source register
| ID / class | Inspected source and locator | Access and limits |
|---|---|---|
| S1 / primary author paper | [DeepSeek-V2, v5](https://arxiv.org/html/2405.04434v5): abstract, §§1, 2.1.1–2.1.4, 3.1.2, 3.2.3, Appendix A Contributions and Acknowledgments; [Figure 1(b) SVG](https://arxiv.org/html/2405.04434v5/efficiency.svg); [submission history/byline](https://arxiv.org/abs/2405.04434v5). | Public HTML read; original Figure 1(b) rendered and visually inspected 2026-10-24. Equations/section identifiers, not inferred PDF pages. Results and individual credits are author-reported, not independently reconstructed. |
| S2 / primary government announcement | [BIS, 2022-10-07](https://www.bis.gov/press-release/commerce-implements-new-export-controls-advanced-computing-semiconductor-manufacturing-items-peoples): dated heading and opening three paragraphs. | Public HTML read; historical announcement and stated rationale, not current legal guidance or evidence of MLA intent. |
| S3 / primary project documentation | [FlashMLA README at 0f11e178da1f67becb087a324b400854931ec3e3](https://github.com/deepseek-ai/FlashMLA/blob/0f11e178da1f67becb087a324b400854931ec3e3/README.md): line 3 breaking-change notice, Introduction, Requirements. | Pinned raw file HTTP200. The 2026.09.30 notice removes Hopper/earlier-model support and changes cache formats; it names V3/V3.2/V4.0, not V2. Its historical compatibility link is an unverified V2 research lead. |
| S4 / primary project documentation | [vLLM attention backends at f3871c3cbf8a608f7ee833ec4c2c5277f77bee41](https://github.com/vllm-project/vllm/blob/f3871c3cbf8a608f7ee833ec4c2c5277f77bee41/docs/design/attention_backends.md): MLA Backends, Prefill/Decode Backends, lines 208–230. | Pinned raw file HTTP200; configuration interfaces inspected. Generated table includes were not expanded; no exhaustive support claim. |
| S5 / primary project documentation | [SGLang backend guide at 74c08f3dc5d98dddf052ba03122fc084a31a0269](https://github.com/sgl-project/sglang/blob/74c08f3dc5d98dddf052ba03122fc084a31a0269/docs/docs/advanced_features/attention_backend.mdx): introduction line 10, MLA Backends, page-size constraints lines 318–323. | Pinned raw file HTTP200; model/platform restrictions documented, no runtime test or cross-project version alignment. |
| S6 / independent secondary evidence | Not obtained in this packet. | Independent benchmark reproduction, institutional history and adoption evidence remain missing; no invented bibliography. |
| S7 / primary author paper, baseline architecture only | [DeepSeek LLM, v1, 2024-01-05](https://arxiv.org/html/2401.02954v1#S2.T2), Xiao Bi et al.: Table 2, §2.2 Architecture and §2.4 Infrastructures. | Public HTML inspected 2026-10-24. The 67B model has 95 layers, model width 8192, 64 attention heads (`n_heads`) and 8 KV heads; §2.2 identifies GQA. Architecture and training-precision anchors do not establish the inference-cache precision used in S1's comparison. This is not independent reproduction evidence. |

## Claim matrix
| Claim / scene | Bounded claim | Anchor | Status |
|---|---|---|---|
| C1 / 2 | MLA jointly compresses keys/values into a latent; the positional key adds cache requirements. Table 1 counts elements per token across `l` layers, independently of storage precision. | S1 §§2.1.2–2.1.4, equations 9–11 and 14–19, Table 1/caption | Yellow |
| C2 / 3 | Paper reports 93.3% KV-cache reduction and 5.76× maximum generation throughput versus dense DeepSeek 67B; V2 is an MoE with 236B total parameters and 21B active per token. Throughput uses one eight-H800 node and the 67B service's prompt/generation-length distribution; deployment also uses FP8 parameters and average six-bit KV quantization. | S1 abstract for ratios/parameter counts, Figure 1(b) for the cache chart's KB/Token label; §3.2.3 Training Costs for the dense baseline and Inference Efficiency for throughput/setup; S7 Table 2/§2.2 for baseline GQA architecture. Exact 93.3% accounting remains unverified; see checkpoint below. | Yellow |
| C3 / 1 | BIS announced advanced-computing/semiconductor controls on 2022-10-07 with stated national-security and foreign-policy interests. | S2 heading/opening | Yellow |
| C4 / 4 | FlashMLA exposes kernels with explicit version and hardware constraints. | S3 Introduction/breaking-change notice/Requirements | Yellow |
| C5 / 4 | vLLM documents separate MLA prefill/decode backend selection. | S4 MLA Backends | Yellow |
| C6 / 4 | SGLang documents configuration-dependent support and page-size constraints. | S5 introduction/MLA Backends/page-size list | Yellow |
| C7 / 1 | DeepSeek-AI is the paper's collective author; v1 submitted 2024-05-07, v5 revised 2024-06-19. Individual acknowledgments are recorded separately in C10. | S1 byline/submission history | Yellow |
| C8 / 1 | Export controls caused MLA's design or establish its authors' motives. | No causal author/archival evidence obtained | Red |
| C9 / 4 | Public kernels prove widespread adoption, universal speedups or hardware independence. | No deployment/reproduction evidence obtained | Red |
| C10 / 2 | The paper credits Huazuo Gao and Wangding Zeng with key MLA research innovations and thanks Jianlin Su for position-embedding discussion. This is author-reported acknowledgment, not an independent invention history. | S1 Appendix A, final acknowledgment paragraph | Yellow |

## Cache-accounting checkpoint (2026-10-24)

This is conditional arithmetic, not a benchmark reproduction or C1/C2 clearance. Dense parameter activation does not imply MHA: S7 identifies the 67B baseline's attention as GQA.

| Evidence class | Input or calculation | Locator and limit |
|---|---|---|
| Source-visible | S1 counts MLA as `(d_c + d_h^R) l` and GQA as `2 n_g d_h l`, in elements per token across layers, independent of storage precision. V2 uses `l=60`, `d_c=512`, `d_h^R=64`. | S1 Table 1/caption and §3.1.2 Model Hyper-Parameters. |
| Source-visible | Figure 1(b)'s cache-for-generation panel title gives units `KB/Token` and the plot annotates a 93.3% reduction. | Original S1 SVG visually inspected. It does not print exact per-bar values, cache dtype or a KB-versus-KiB definition; bar positions are not used as exact numerical data here. |
| Source-visible | The 67B baseline has 95 layers, width 8192, 64 attention heads and 8 KV heads. | S7 Table 2 and §2.2; the inference-comparison cache dtype is not given by these architecture anchors. |
| Derived working input | Use head dimension `8192 / 64 = 128` under the conventional model-width/query-head split, and eight GQA KV groups. | Architecture-based calculation, not a measured cache layout or separately stated benchmark setting. |
| Derived element accounting | V2: `(512 + 64) × 60 = 34,560`; baseline GQA: `2 × 8 × 128 × 95 = 194,560` elements/token. Equal-bit-width reduction: `1 − 34,560 / 194,560 ≈ 82.2368%`. | Applying S1's formulas to the stated/derived inputs; not the paper's reported deployment-memory calculation. |
| Assumed precision/accounting | A 16-bit 67B cache, with S1's reported average six-bit V2 cache treated as a bit cost for the counted elements. | The baseline precision is an assumption, not established by the inspected anchors. This idealized payload estimate excludes allocator, packing and quantization-metadata accounting. |
| Derived ideal payload | Under that assumption: baseline `389,120` bytes/token and V2 `25,920` bytes/token. Decimal units give `389.12 kB` and `25.92 kB`; binary units give `380 KiB` and `25.3125 KiB`. | Unit conversions of the conditional calculation, not measured allocations or printed figure values. The chart's `KB` convention is not defined in the inspected figure. |
| Conditional result | `1 − (34,560 × 6) / (194,560 × 16) ≈ 93.3388%`. | Numerically compatible with a rounded 93.3%, but not evidence that the authors used these assumptions or this accounting definition. |

S1 §3.2.3 distinguishes FP8 model parameters from average six-bit KV-cache quantization. S7 §2.4 reports bf16 training precision; that is not an inference-cache dtype statement. Do not infer the baseline cache dtype from weights, training precision or the reported percentage. Obtain the compared 67B cache precision and accounting definition before treating this calculation as the reported result. This packet retains C1/C2 as Yellow; any later per-claim clearance requires its applicable corroboration and reviews.
