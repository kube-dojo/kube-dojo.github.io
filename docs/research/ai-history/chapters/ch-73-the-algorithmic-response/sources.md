# Sources: Chapter 73

Inspected 2026-10-23. Green means independently corroborated and reviewed; Yellow means source-visible but pending those checks; Red means unsupported for drafting. Retrieval and file presence grant no clearance. This packet has **0 Green, 7 Yellow, 2 Red** claims.

## Source register
| ID / class | Inspected source and locator | Access and limits |
|---|---|---|
| S1 / primary author paper | [DeepSeek-V2, v5](https://arxiv.org/html/2405.04434v5): abstract, §§1, 2.1.1–2.1.4, 3.2.3; [submission history/byline](https://arxiv.org/abs/2405.04434v5). | Public HTML read; equations/section identifiers, not inferred PDF pages. Author-reported results, no independent reproduction. |
| S2 / primary government announcement | [BIS, 2022-10-07](https://www.bis.gov/press-release/commerce-implements-new-export-controls-advanced-computing-semiconductor-manufacturing-items-peoples): dated heading and opening three paragraphs. | Public HTML read; historical announcement and stated rationale, not current legal guidance or evidence of MLA intent. |
| S3 / primary project documentation | [FlashMLA README at 0f11e178da1f67becb087a324b400854931ec3e3](https://github.com/deepseek-ai/FlashMLA/blob/0f11e178da1f67becb087a324b400854931ec3e3/README.md): line 3 breaking-change notice, Introduction, Requirements. | Pinned raw file HTTP200. Notice reports 2026.09.30 removal of Hopper/earlier-model support and cache-format changes; historical compatibility link is a research lead, not verified V2 support. |
| S4 / primary project documentation | [vLLM attention backends at f3871c3cbf8a608f7ee833ec4c2c5277f77bee41](https://github.com/vllm-project/vllm/blob/f3871c3cbf8a608f7ee833ec4c2c5277f77bee41/docs/design/attention_backends.md): MLA Backends, Prefill/Decode Backends, lines 208–230. | Pinned raw file HTTP200; configuration interfaces inspected. Generated table includes were not expanded; no exhaustive support claim. |
| S5 / primary project documentation | [SGLang backend guide at 74c08f3dc5d98dddf052ba03122fc084a31a0269](https://github.com/sgl-project/sglang/blob/74c08f3dc5d98dddf052ba03122fc084a31a0269/docs/docs/advanced_features/attention_backend.mdx): introduction line 10, MLA Backends, page-size constraints lines 318–323. | Pinned raw file HTTP200; model/platform restrictions documented, no runtime test or cross-project version alignment. |
| S6 / independent secondary evidence | Not obtained in this packet. | Independent benchmark reproduction, institutional history and adoption evidence remain missing; no invented bibliography. |

## Claim matrix
| Claim / scene | Bounded claim | Anchor | Status |
|---|---|---|---|
| C1 / 2 | MLA jointly compresses keys/values into a latent; the positional component adds cache requirements. | S1 §§2.1.2–2.1.4, equations 9–11, Table 1 | Yellow |
| C2 / 3 | Paper reports 93.3% KV-cache reduction and 5.76× maximum generation throughput versus DeepSeek 67B. Throughput uses one eight-H800 node and the 67B service's prompt/generation-length distribution; deployment also uses FP8 parameters and average six-bit KV quantization. | S1 abstract; §3.2.3 Inference Efficiency | Yellow |
| C3 / 1 | BIS announced advanced-computing/semiconductor controls on 2022-10-07 with a stated national-security rationale. | S2 heading/opening | Yellow |
| C4 / 4 | FlashMLA exposes kernels with explicit version and hardware constraints. | S3 Introduction/breaking-change notice/Requirements | Yellow |
| C5 / 4 | vLLM documents separate MLA prefill/decode backend selection. | S4 MLA Backends | Yellow |
| C6 / 4 | SGLang documents configuration-dependent support and page-size constraints. | S5 introduction/MLA Backends/page-size list | Yellow |
| C7 / 1 | DeepSeek-AI is the paper's collective author; v1 submitted 2024-05-07, v5 revised 2024-06-19. | S1 byline/submission history | Yellow |
| C8 / 1 | Export controls caused MLA's design or establish its authors' motives. | No causal author/archival evidence obtained | Red |
| C9 / 4 | Public kernels prove widespread adoption, universal speedups or hardware independence. | No deployment/reproduction evidence obtained | Red |
