# Infrastructure evidence: Chapter 73

- C1: compare S1 equations 14–19 and Table 1; counting only the compressed latent omits the decoupled positional key. `l` is layer count, not context length; `d_h^R` is the per-head dimension of decoupled queries/key.
- C2: retain the paper's deployment optimizations, device count and workload basis whenever interpreting throughput. No local GPU benchmark was run.
- C4: S3 is a pinned documentation snapshot, not a V2-compatible environment specification. Its historical commit link remains uninspected here.
- C5–C6: model configuration, backend, hardware and page size constrain selection. The three project snapshots are not a tested compatible stack.
- Do not infer tiling, warp reductions, shared-memory use or bandwidth measurements from a repository title; inspect pinned code/technical reports before drafting those details.
- Access on 2026-10-23: S1/S2 public HTML and S3–S5 pinned raw files. No VPS tunnel, installed backend, cloud resource or accelerator was used. Source IDs: [sources.md](sources.md).
