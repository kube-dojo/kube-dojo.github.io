# Chapter 3 claim ledger — #2339 research packet

**Date:** 2026-09-11
**Scope:** `docs/research/ai-history/chapters/ch-03-the-physical-bridge/` only.
This packet does not edit published prose, invent scenes or motives, or accept
the chapter. Sidecar records from 2026-09-05 remain historical; this ledger
binds the five #2339 gaps to claim / locator / source class / access / support
/ uncertainty. Existing Green/status metadata is not fresh acceptance.

Narrative line numbers below are from `src/content/docs/ai-history/ch-03-the-physical-bridge.md`
in this checkout. They are research locators, not a prose-edit license.

| # | Claim | Locator | Source class | Access | Support | Uncertainty |
|---|---|---|---|---|---|---|
| 1 | Figure 5 → Figure 6 is a 13→6 *variable/contact-occurrence* reduction; absorption is theorem 15a (`X + XY = X`); theorem 17b is `X + f(X) = X + f(0)`. Do not infer a physical relay count. | Thesis printed pp. 14–16 (PDF pp. 17–19). Prose now at ch-03:112. Contract rows in `sources.md` / `scene-sketches.md` / `status.yaml` / `brief.md` / `open-questions.md` / `infrastructure-log.md` still said 13→5. | Primary (Shannon 1937 thesis facsimile). | 2026-09-11: MIT bitstream `.../34541425-MIT.pdf?sequence=1` returned HTTP 405. Class-notes mirror `https://fab.cba.mit.edu/classes/862.16/notes/computation/Shannon-1937.pdf` returned HTTP 200, 3,153,192 bytes, SHA-256 `4a7c64ce7a11c186568c36963dff77a958bd73ea56fe165a346e20fba9fc48d4` — same bytes as the 2026-09-05 cache. Handle page opened. This is not a fresh DSpace-bitstream success. | Printed p. 14 lists 15a `X = X + XY` and 17b `X + f(X) = X + f(0)`. Printed p. 15 displays `W + W'(X+Y) + (X+Z)(S+W'+Z)(Z'+Y+S'V)` (13 letters) and the 17b reductions on W, then X and Y. Printed p. 16 displays `W + X + Y + ZS'V` (6 letters) and Figure 6. Source says “large reduction in the number of elements”; it does not print 13→5 or a relay inventory. | OCR on this scan is noisy; letter counts are from the displayed algebra, not from OCR tokens. Six distinct variables appear in both forms; that does not establish hardware inventory, cost, performance, or minimality. |
| 2 | Separate Owens’s 1941–42 wartime finished-machine chronology from any inferred Shannon duty or motive. “Post-war scale” conflicts with Owens’s own dates. The 1931-machine / successor-design conjunction remains Yellow. | Owens 1986 printed pp. 63, 72, 79–81. Contract: `sources.md` claim table Scene 1 rows; `scene-sketches.md` Scene 1 beats. Prose now at ch-03:70. | Secondary historical article (Owens). Not a Shannon primary. | 2026-09-11: `https://worrydream.com/refs/Owens_1986_-_Vannevar_Bush_and_the_Differential_Analyzer.pdf` HTTP 200, SHA-256 `0e660e08ce7083073e98db445e3e319edd207e4d99c230fa653265f2e1803d48`. Printed p. 63 extracted. JSTOR publisher record not re-opened. | p. 63: dedicated “to winning the war” in 1942; ~100 tons, ~2000 tubes, several thousand relays; first demonstration 13 December 1941 (n.1). p. 72: 1931 six-integrator machine. p. 79: March 1936 $85,000 grant. Owens does not name Shannon. | Owens cannot prove Shannon’s day-to-day analyzer duties or that the setup problem *motivated* the thesis. Combine chronology with the 1938 byline only as Yellow personal context. |
| 3 | The worldwide-priority wording is a TICSP report of Yamada, not a checked direct Yamada-2004 English quotation. | TICSP-40 printed p. 17 and refs `[21]`/`[22]` (printed p. 20). Yamada 2004 J-STAGE article/abstract. Prose now at ch-03:80. | Secondary (TICSP historical report) citing secondary Japanese historiography. Yamada 2004 PDF is a later Japanese article. | This packet did not re-retrieve TICSP-40 or Yamada 2004. Bind to `context-corrections-2026-09-05.md`: TICSP S3 SHA-256 `6e1cc3acd974120529649e2a5b88369e158b4d6fb5710241225209d531ad6dd3`; Yamada PDF image-only; live ETHW PDF URL 404. | TICSP p. 17 attributes “the first paper on switching theory in the World” to Yamada and points `[21]` at a 2003 *C* article, `[22]` at the 2004 IEEJ article. Independent-discovery hedge stays; chronology alone does not prove influence. | Yamada 2003 `[21]` was not retrieved. Any English rendering of Yamada 2004 body text needs Japanese-language review. Do not present a direct checked quotation by assumption. |
| 4 | Piesch 1939 and Plechl–Duschek 1946: titles, dates, and opening-page context only. Do not expand to whole-publication priority or citation-pattern claims. | TICSP-40 printed pp. 183, 185–186. Springer record DOI `10.1007/BF01656419`. Prose now at ch-03:177. | Primary facsimile (reprinted first pages) + institutional publisher metadata. Full papers not held. | This packet did not re-open the facsimiles. Bind to the 2026-09-05 access note: first pages only; Springer full PDF access-controlled. | Accessible pages support titles/opening context. Publisher record: Piesch received 28 February 1939, published October 1939. Plechl–Duschek p. 204 facsimile labels a Piesch cite “1937” — keep that discrepancy; do not silently normalize. | “First sustained German-language formulation,” “too late to be a true parallel discovery,” and a complete-publication claim that the first Plechl–Duschek paper cited Nakashima but not Shannon exceed these pages. |
| 5 | Do not equate every modern chip with Shannon’s two-terminal series-parallel relay model, nor claim universal minimality. | Yosys 0.68-dev manual printed pp. 44, 50, 53, 71–72; Wolf & Glaser, Austrochip 2013. Prose now at ch-03:183–185. | Modern tool documentation (institutional/current) + 2013 conference paper (historical primary for that release). | This packet did not re-retrieve Yosys. Bind to `modern-logic-corrections-2026-09-05.md` hashes. Rolling manual URL is not a pinned edition. | Those pages support a tool-specific RTL-lowering / functional-preservation / target-mapping example. They do not cover every CPU, GPU, MCU, or FPGA, or identify silicon with 1937 series-parallel relays. | No timing, power, area, or fabrication result. Shannon’s hindrance algebra stays historically separate from this modern example. |
| 6 | Shannon p.1 names telephone exchanges and motor-control equipment as applications. Cost, floor-space, and failure-probability motives are not on the inspected thesis pages. | Thesis printed p.1. Prose ch-03:94. | Primary (thesis) for the named applications only. | Same 2026-09-11 Shannon-mirror access as row 1. | p.1 supports analysis vs. synthesis and the named applications. Printed pp. 14–16 support comparing series-parallel *expressions* (prose ch-03:118), not a priced hardware experiment. | Withdraw or hedge the cost/space/failure mechanism until a separate source is checked. Do not invent engineering motives. |

## Disposition for this research PR

- Correct the stale 13→5 Green rows in the chapter contract to 13→6 contact
  occurrences, theorem 15a vs 17b, printed pp. 14–16.
- Keep rows 2–4 Yellow where personal conjunction, Yamada 2003, or full
  European papers remain uninspected.
- Keep row 5 as a bounded modern-tool analogy, not a universal-chip law.
- Mark row 6 as still needing a source or narrower wording.
- No new word-count quota. No reader exercise in this packet.

## Access receipts (2026-09-11)

- Shannon class-notes mirror: HTTP 200, SHA-256
  `4a7c64ce7a11c186568c36963dff77a958bd73ea56fe165a346e20fba9fc48d4`.
- MIT DSpace bitstream: HTTP 405 (not a successful primary-endpoint retrieval).
- Owens worrydream mirror: HTTP 200, SHA-256
  `0e660e08ce7083073e98db445e3e319edd207e4d99c230fa653265f2e1803d48`.
- Yamada, TICSP-40, Yosys, and Springer full text: not re-fetched here.
