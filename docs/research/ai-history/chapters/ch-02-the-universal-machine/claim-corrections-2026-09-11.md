# Chapter 2 claim-level correction ledger — 2026-09-11

Research-only packet for #2329 (parents #2289 / #2272). Rechecks the Gödel/ω-consistency qualification, physical-machine scope, and modern-epilogue overclaims against freshly retrieved sources. Existing Green labels and the 2026-09-05 packets are pointers to verify, not independent acceptance. No published prose, generated artifact, or `status.yaml` lifecycle flag is changed here. This is not whole-chapter verification.

## Bindings

- Published file: `src/content/docs/ai-history/ch-02-the-universal-machine.md`
- Audit revision named in #2329: `3904f9b4a666a5090d191fa330aee1048c8e1e41`
- Current blob at this check: `eb92d6ca842a198c73e3be4c3e77b5951726b4c3` (file SHA-256 `2f2cf7525962b88cd38119b07d48daf5dd4387a7261f9b02953908ad1fcfc504`; last prose bind `#2352` / `673ac3686`)
- Line numbers below are source-file coordinates in the current blob, not rendered-page lines.
- Inherited dated records, not reopened as authority: `mathematical-corrections-2026-09-05.md`, `context-corrections-2026-09-05.md`

Each entry records: **claim; locator; source; class; printed locator; access; support; uncertainty; disposition**.

## Retrieval record (2026-09-11)

Hashes are SHA-256 of the retrieved bytes. HTTP 200 unless noted.

| Artifact | URL | Bytes | SHA-256 |
|---|---|---|---|
| Gödel 1931, Hirzel 2000 EN | https://hirzels.com/martin/papers/canon00-goedel.pdf | 335127 | `13e752f90f65678d36d135623dced442dac44bdf1755c50f8bb845c1abba5a3a` |
| Gödel 1931, Meltzer 1962 EN | https://homepages.uc.edu/~martinj/History_of_Logic/Godel/Godel%20%E2%80%93%20On%20Formally%20Undecidable%20Propositions%20of%20Principia%20Mathematica%201931.pdf | 181829 | `b40a947d1503bb00f14c7439cbd527825b0667321b01b97bbd77307020daa401` |
| Turing 1936 LMS scan | https://www.cs.virginia.edu/~robins/Turing_Paper_1936.pdf | 2198146 | `a126650c315e998ba96ea8248a60bde0afe60fec3e810acfc2b6c70d3b0e9f36` |
| Church 1936 AJM | https://ics.uci.edu/~lopes/teaching/inf212W12/readings/church.pdf | 493373 | `3e683416eaeb934d0a8daee9739f0211ba395e6e0973ac24c2b9588c330a7c25` |
| Rosser 1936 JSL extract | https://www.cambridge.org/core/journals/journal-of-symbolic-logic/article/abs/extensions-of-some-theorems-of-godel-and-church/0461E34DC1F219C459EE84CC2FA89068 | 758824 | `7bf9902d3a3326b96912aea33addc676f63bc658eb543032278a2a065f8ba251` |
| ZIB Z1 page | https://zuse.zib.de/z1 | 54365 | `cc9859bf930ecc27ddf36fbad33e0200240c557b40c0b2d7867dc9e03d887bda` |
| Rojas 2014 Z1 HTML | https://www.mi.fu-berlin.de/inf/groups/ag-ki/publications/Z1-Architecture/index.html | 37278 | `d4440953f96fe57461474928069db06b19f0b76dcd9603ee379c8a837286c564` |
| Rojas 2016 arXiv 1603.02396 | https://arxiv.org/pdf/1603.02396 | 590125 | `2acb63fbe567e7d3fc3b3e5e1a3417206f43a0a2bbdabcc022d41ffe2ceb833a` |
| Microchip tinyAVR §9.3 | https://onlinedocs.microchip.com/oxy/GUID-B990D80E-52D0-4869-8631-E8A045F89631-en-US-4/GUID-F9B6741C-7F50-477E-81A8-5423F10CD41A.html | 71564 | `cad96f5073660c1342a5038b250a13eb25a910da9621b395af79ce7cfbd36ecf` |
| SEP “Recursive Functions” | https://plato.stanford.edu/entries/recursive-functions/ | 299541 | `5fa44199c0133e1382ef9bd1dcc0ab8e447c0ebf9b33b39a75b129d1cd27a6d7` |
| NIST SP 800-83 PDF | https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-83.pdf | 2253648 | `558b9d76b99d55d757acb6619333c58d1ad4091c1bedcf1d04264e5532d806c3` |
| NIST SP 800-83 record | https://csrc.nist.gov/pubs/sp/800/83/final | 40399 | `122dc8d528c75d71470b76174989a2028e2966ac53d2a7f8bb66ede8d6c02edb` |

Access failures this session (do not invent locators from them): Rice 1953 AMS PDF and DOI landing, HTTP 403; Technikmuseum computers page, HTTP 404; Oxford *Collected Works I* chapter, HTTP 403.

## Findings

### G1 — Theorem VI hypothesis is ω-consistency (`Supported` / current prose in bound)

- **Audit claim** (`3904f9b4`, paragraph after Theorem VI): both unprovability directions closed by plain consistency; `r` treated as the closed sentence.
- **Current locator:** lines 68–70.
- **Sources:** Hirzel 2000 translation (later EN of 1931 primary; omits §§3–4 and all footnotes, PDF p.1). Theorem VI, original markers [187]–[189] / Hirzel PDF pp.14–16: κ must be ω-consistent; step 1, provability of `forall(17,r)` yields inconsistency; step 2 uses ω-consistency to exclude `not(forall(17,r))`. Meltzer 1962 (later EN; book pp.57–59 / PDF pp.60–62, same [188]–[189] markers) independently states Proposition VI under ω-consistency and the same two-step split. Both translations: every ω-consistent system is consistent; the converse fails.
- **Class:** primary paper in later translations. **Access:** both PDFs HTTP 200, 2026-09-11.
- **Support:** original theorem is not a consistency-only result; `r` is a class-sign / predicate with a free variable; the closed sentence is `forall(17,r)` (Hirzel) / `17 Gen r` (Meltzer).
- **Uncertainty:** Hirzel PDF p.15 “less general” sentence is translator commentary (magenta in that edition; absent after Meltzer’s Proposition VI). Do not attribute it to Gödel. Neither copy is an original *Monatshefte* scan.
- **Disposition:** keep the ω-consistency hypothesis and the two-branch split. Current lines 68–70 already sit inside this boundary. Do not silently substitute Rosser’s later hypothesis into the 1931 proof.

### G2 — Rosser 1936 is a later, weaker-hypothesis strengthening (`Supported` as extract only)

- **Current locator:** line 68 (“Rosser's 1936 result later used a modified argument…”).
- **Source:** J. B. Rosser, “Extensions of some theorems of Gödel and Church,” *JSL* 1(3), Sept. 1936, pp.87–91, DOI `10.2307/2269028`. Publisher extract only (Cambridge Core `#sec0`). Defines simple consistency vs Gödel’s ω-consistency; Satz VI as “ω-consistency implies … undecidable propositions”; then “by sacrificing some generality, it is proved that simple consistency implies the existence of undecidable propositions.” Site online date 12 March 2014 is not the article date.
- **Class:** primary article extract (not full text). **Access:** HTTP 200 extract, 2026-09-11.
- **Uncertainty:** detailed proof claims need the full article. Extract does not license a scene of Rosser “replacing” Gödel in 1931.
- **Disposition:** name Rosser separately as a 1936 consistency-only strengthening. Safe current wording is already inside this bound.

### T1 — Appendix equivalence ≠ Church–Turing thesis (`Supported`)

- **Current locator:** glossary line 58; appendix paragraph line 136.
- **Sources:** Turing 1936 appendix, printed pp.263–265 / PDF pp.34–36: “proved below in outline”; “existence of several formulae is assumed without proof.” Return address printed p.265. Church 1936 §7, printed p.356 / PDF p.13: identifies effective calculability with recursive / λ-definable functions; “so far as positive justification can ever be obtained for the selection of a formal definition to correspond to an intuitive notion.”
- **Class:** primary papers. **Access:** both PDFs HTTP 200.
- **Disposition:** appendix = outline formal equivalence. Thesis = identification with intuitive calculability. Current glossary already separates them.

### P1 — Scope physical-machine claims before asserting absence (`Overbroad` at audit / `Supported` scoped)

- **Audit claims** (`3904f9b4`): “No physical machine was built, no wires were soldered…”; “No vacuum-tube assembly, no relay bank, no electromechanical contraption … answered to the universal machine’s specification.”
- **Current locator:** lines 124–126.
- **Sources:** Turing §6, printed pp.241–242 / PDF pp.12–13: U is a single machine computing any computable sequence from an S.D on its tape — a mathematical specification, not a hardware inventory. ZIB Z1 page (institutional secondary): designed 1935–36, built 1936–38; mechanical; punched-tape instructions; “There were no relays”; “The only electrical unit was an electric motor”; reliability limited by synchronization. Rojas 2014 HTML (academic secondary): built 1936–38; punched tape; no conditional branching; description from reconstruction blueprints, letters, notebooks. Rojas 2016 arXiv 1603.02396 (academic secondary), p.1: built “1935/36 and 1937/38”; “the conditional jump was missing.”
- **Access:** ZIB, Rojas HTML, and arXiv HTTP 200. Technikmuseum URL used in the 2026-09-05 packet returned HTTP 404 here; do not reuse that locator from this check.
- **Support:** 1936–38 physical construction of a limited programmable mechanical machine is attested. None of these sources identify Z1 as an implementation of Turing’s U, a stored-program universal computer, or a reliable machine.
- **Uncertainty:** no source here proves the negative “no 1936 device satisfied U.” Stibitz Model K remains unchecked. Q8 in `open-questions.md` is narrowed, not closed.
- **Disposition:** define scope first: (a) physical implementation of Turing’s U, vs (b) any contemporaneous programmable calculator. Current lines 124–126 stay inside (a)/(b) separation. Do not restore an unqualified “no physical machine.”

### M1 — “Every production computer” shared-memory universal (`Unsupported` at audit / `Supported` as scoped model)

- **Audit claim:** “Every computer in production today is … a fixed processor reading instructions stored in the same memory as its data.”
- **Current locator:** line 151.
- **Source:** Microchip tinyAVR 1-series §9.3 “Architecture” (vendor primary): “Harvard architecture with separate buses for program and data”; program memory on Flash from `0x0000`; data space divided into I/O, SRAM, EEPROM, and Flash.
- **Access:** HTTP 200, 2026-09-11. One current MCU family, not a survey.
- **Disposition:** “many general-purpose stored-program systems can be usefully modeled…” Current line 151 already uses that bound. Do not restore the universal.

### M2 — Modern software as direct §6 consequence (`Overbroad` at audit / `Inference`)

- **Audit claim:** program-as-data of §6 “is what makes compilers, interpreters, virtual machines, and containers possible.”
- **Current locator:** line 151.
- **Source:** Turing §6 as in P1. The paper does not name those later systems.
- **Disposition:** later applications/analogies, not 1936 artifacts. Current line 151 already marks that inference.

### M3 — Antivirus / verification / Rice as if they were Turing §6 (`Overbroad` at audit / `Supported` narrowed)

- **Audit claim:** print-symbol/circle-free result is “the reason no static analyser can perfectly decide every program’s behaviour, the reason no antivirus can definitively classify every binary, and the reason formal verification stops at proof-decidable subsets.”
- **Current locator:** line 153.
- **Sources:** Turing §8, printed pp.247–248 / PDF pp.18–19: no machine D for circle-freeness; no machine E for whether an arbitrary machine prints a given symbol. SEP “Recursive Functions,” Theorem 3.4 (Rice 1953): every non-trivial index set is undecidable; surrounding prose applies this to semantic program properties (secondary scholarly exposition). NIST SP 800-83 §3.4.1.1, printed pp.3-6–3-7 / PDF pp.34–35: signatures, heuristics, false positives, false negatives; heuristics “cannot achieve highly accurate detection of new malware threats.” NIST publication record: Date Published November 2005 (`citation_publication_date` 2005/11/23); Withdrawn 22 July 2013; superseded by Rev. 1. Historical operational guidance, not a current-capability statement or a classification theorem.
- **Access:** Turing, SEP, and NIST HTTP 200. Rice 1953 AMS PDF HTTP 403 this session — bibliographic only; SEP carries the usable theorem text.
- **Disposition:** Turing supports a no-general-process analogy; Rice (via SEP) supports undecidability of non-trivial semantic properties; NIST supports heuristic limits. Combined safe wording: no sound-and-complete automatic procedure decides every non-trivial semantic property of arbitrary programs; antivirus is an engineering example. Current line 153 is inside that bound. Do not say §6 itself proves antivirus or verification limits.

## Unresolved in this packet (not settled)

- Princeton: appendix printed p.265 is a return address. Line 140’s autumn-1936 arrival / fellowship / 1938 thesis remains Yellow biographical chronology (`open-questions.md` Q2). Do not turn the address into a witnessed arrival scene.
- Still unchecked here: Church 1936b JSL note, Church 1937 review, Davis 1958 “halting” terminology, Hilbert–Ackermann edition, Kleene chronology, Stibitz Model K.
- `status.yaml` still mixes `capacity_plan_anchored`, `cross_family_review_pending`, published prose, and `cross_family_satisfied.overall: true`. Lifecycle reconciliation is a later packet.
- Follow-up packets named in #2329 remain open. A later prose PR, if any, must cite the then-current file hash; this ledger is not permission to expand scenes.

## Non-acceptance

No whole-chapter, Ukrainian, editorial-program, or learner-outcome acceptance follows. Independent-family source-fidelity review of this record remains pending.
