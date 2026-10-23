# Brief: Chapter 73 — The Algorithmic Response

## Thesis and scope
This technical coda asks how changing an attention representation can change an inference-memory constraint, then follows the separate work of implementing and selecting compatible kernels. It complements Chapter 72's physical infrastructure story; it does not establish that algorithms eliminate infrastructure constraints.
Existing English prose is published. This first contract is a research draft, not retrospective acceptance or permission to expand it. Evidence IDs and claim dispositions are in [sources.md](sources.md).

## Boundary contract
1. Attribute C1–C2 to the paper; do not turn an evaluated comparison into a universal deployment guarantee.
2. Separate MLA from the additional inference optimizations in C2.
3. Use BIS as historical context, not evidence of DeepSeek's private design motive (C8).
4. Pin implementation descriptions; neither current HEAD nor a compatibility notice establishes a historical V2 integration.
5. Backend selection is conditional on supported configurations; publication is not adoption (C9).
6. Invent no private scenes, individual credit, quotations, hardware runs or review receipts.

## Prose Capacity Plan
Provisional anchored core: **2,000–3,000 words**, label **2k-4k natural**; no prose unlock or accepted cap follows. Budgets describe a possible later revision, not the existing prose's measured length.
- 300-400 words: the constraint and policy-context boundary; scene 1; S1 §1 and S2 opening announcement paragraphs.
- 800-1100 words: representation, cache accounting and positional treatment; scene 2; S1 §§2.1.1–2.1.4, equations 9–11 and Table 1.
- 350-500 words: what the reported comparison measures; scene 3; S1 abstract and §3.2.3, Inference Efficiency.
- 550-1000 words: implementation/version and backend-selection boundaries; scene 4; S3 README breaking-change notice, S4 MLA Backends, S5 introduction/MLA Backends.
Stretch **4,000–5,000 words** requires historical V2-compatible implementation evidence, an independently inspected reproduction and documented integration history (open questions 2–4); it is not an additional authorized budget. Review must assess whether those layers merit expansion.
If the verified evidence runs out, cap the chapter.
