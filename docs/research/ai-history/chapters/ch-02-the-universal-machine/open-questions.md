# Open Questions: Chapter 2 — The Universal Machine

Surfaced from `brief.md` *Conflict Notes* and the Yellow/Red entries in `sources.md`. Each question identifies the specific evidence needed to resolve it. Drafting cannot rely on any open-question item until its evidence is in hand.

## Resolution Required Before Drafting

### Q1. Hilbert-Ackermann edition for the Entscheidungsproblem citation
- **Question:** Which edition of *Grundzüge der theoretischen Logik* is the chapter citing? The 1st edition (1928), the 1931 second printing of the 1st edition (which Turing 1936 cites), or the 2nd revised edition (1938)?
- **Why it matters:** The chapter says "the Entscheidungsproblem was formulated in *Grundzüge der theoretischen Logik* (1928), chapter 3." Strictly, the 1928 1st edition is the first appearance. But Turing 1936 §11 p.259 cites "(Berlin, 1931)" — the second printing. The 2nd revised edition (1938) post-dates the chapter's window and changed the chapter numbering.
- **Evidence needed:** Direct retrieval of all three editions, or a Hodges 1983 / Davis 2000 page anchor that resolves the citation question authoritatively.
- **Status:** Yellow. Non-blocking for prose drafting (the chapter can cite the 1928 1st edition with a footnote about Turing's 1931-printing reference); but cleaner if resolved.

### Q2. Turing's exact arrival date at Princeton
- **Question:** When did Turing physically arrive at Princeton? The appendix dated 28 August 1936 carries the Princeton return address; standard secondary literature (Hodges 1983 et al.) typically gives a late-September 1936 sailing date. Are these reconcilable, or is there a genuine date discrepancy?
- **Why it matters:** The chapter's Scene 5 narrative move depends on whether Turing "wrote the appendix from Princeton" (literal) or "wrote the appendix and signed it as if from Princeton because that was his upcoming address" (administrative). Both readings are possible from the primary anchors alone.
- **Evidence needed:** Hodges 1983 page anchor for Turing's transatlantic crossing date; ideally Turing's correspondence from 1936 (King's College Cambridge archives, Princeton archives, Turing Papers digitized at turingarchive.kings.cam.ac.uk).
- **Status:** Yellow. Non-blocking; the chapter can phrase Scene 5 to allow either reading.

### Q3. The route by which Turing learned of Church's parallel work
- **Question:** Did Turing learn of Church 1936 via the *Am. J. Math.* April 1936 issue arriving in Cambridge, the *JSL* March 1936 note, a personal letter from Newman, or some other route?
- **Why it matters:** Scene 5's narrative move benefits from concrete detail about how the news crossed the Atlantic. Without an anchor, the scene must hedge ("by some combination of journal and correspondence").
- **Evidence needed:** Hodges 1983 page anchors; Turing's correspondence with Newman (King's College archive); Newman's correspondence with Church (Princeton archive).
- **Status:** Yellow. Non-blocking; the *fact* of mid-process learning is anchored via Stanford Encyclopedia (Copeland) and Turing's own footnote.

### Q4. Should Post 1936 be in scope?
- **Question:** Emil Post's "Finite Combinatory Processes — Formulation 1," *Journal of Symbolic Logic* 1, no. 3 (October 1936), pp. 103-105, independently arrived at a tape-and-state model essentially identical to Turing's machine. The current `brief.md` Scope explicitly excludes Post. Should this be reconsidered?
- **Why it matters:** A "two parallel discoveries" framing is honest but slightly incomplete. The fuller story is "three parallel discoveries" — Church, Turing, Post. The chapter's narrative arc is cleaner with two; the historical record supports three.
- **Evidence needed:** Direct retrieval of Post 1936 (JSL 1(3), pp.103-105); a decision from the human editor / cross-family review on whether to expand scope.
- **Status:** Yellow. **Flag for cross-family review before prose drafting begins.** If the editorial decision is "include Post," Scene 2 would need restructuring as "the parallel discoveries (plural)."

### Q5. The Hodges 1983 edition question
- **Question:** Which edition of Hodges' *Alan Turing: The Enigma* should the chapter cite — the 1983 first edition (Burnett Books / Hutchinson) or the 2014 Princeton University Press centenary edition?
- **Why it matters:** Page anchors differ between editions. The 2014 centenary edition has a new introduction by Hodges and slightly different pagination. Citation discipline requires one consistent edition.
- **Evidence needed:** Editorial decision; access to the chosen edition for page-anchoring.
- **Status:** Yellow. Recommendation: cite the 2014 Princeton centenary edition as default (more accessible to current readers), with footnote noting equivalents in the 1983 first edition where significant.

## Lower-Priority Questions (Do Not Block Drafting)

### Q6. The 1937 *Proc. LMS* correction paper
- **Question:** Turing 1937, "On Computable Numbers... A Correction," *Proc. London Math. Soc.* (2) 43, pp. 544-546, contains substantive corrections to the 1936 paper. Are any of those corrections load-bearing for this chapter's claims?
- **Why it matters:** If the correction modifies the §6 universal-machine construction or the §11 Entscheidungsproblem proof, the chapter's anchors might need adjusting.
- **Evidence needed:** Direct retrieval of the correction paper.
- **Status:** Yellow. Non-blocking — the corrections in the literature are typically discussed as technical fixes that do not modify the load-bearing claims. Verify before final prose review.

### Q7. Newman's role at Cambridge
- **Question:** What was Max Newman's specific role in introducing Turing to the *Entscheidungsproblem*? The standard secondary narrative says Newman's foundations-of-mathematics course was the introduction. Specific Newman lecture dates, course content, and Newman's reaction to Turing's manuscript would tighten Scene 3.
- **Why it matters:** A scene-level Newman beat would help anchor the Cambridge-1935 setting that currently sits at Yellow.
- **Evidence needed:** Hodges 1983 page anchors; King's College Cambridge archives; Newman Papers (St John's College, Oxford archives, possibly).
- **Status:** Yellow. Non-blocking — Newman can be cited via Hodges 1983 once that page anchor lands; or the Newman beat can be omitted if anchors do not land.

### Q8. The "no machines existed" infrastructure point
- **Question:** Is the chapter's claim that "no general-purpose programmable digital computer existed in 1936" defensible without footnoting Konrad Zuse's Z1 (under construction in Berlin from 1936) or the Bell Labs Model K (Stibitz, 1937)?
- **Why it matters:** The chapter's "infrastructure was zero" framing is dramatic but requires care. Zuse's Z1 was programmable (via punched tape) and in development through 1936; the Z3 (1941) is widely credited as the first programmable digital computer. Stibitz's Model K (1937) is later than Turing 1936 but close.
- **Evidence needed:** A short footnote citing Zuse and Stibitz, with dates that put them squarely *after* Turing's May 1936 manuscript receipt. Standard secondary sources have these.
- **Status:** Yellow, narrowed 2026-09-11. [claim-corrections-2026-09-11.md](claim-corrections-2026-09-11.md) P1 scopes “no physical U” separately from Z1 (built 1936–38; punched-tape mechanical; no attested U implementation). Stibitz Model K and any 1936 device meeting U remain unchecked. Do not restore an unqualified “no physical machine.”

### Q9. The "stored program" architecture lineage
- **Question:** How explicit should the chapter be about the distance between Turing's §6 universal computing machine and the post-1945 stored-program machines (EDVAC, Manchester Baby, EDSAC)?
- **Why it matters:** The chapter's "Birth of Software" framing in Scene 4 risks anachronism if the §6 universal machine is read backward as "the EDVAC architecture." The boundary contract is explicit that this conflation is forbidden, but prose-level vigilance is required.
- **Evidence needed:** Editorial discipline during prose drafting; cross-link to Ch8 throughout Scene 4.
- **Status:** Yellow. Self-managed during drafting via boundary contract.

### Q10. Should the chapter mention Gödel-Herbrand recursiveness explicitly?
- **Question:** Church 1936 §7 mentions both λ-definability and *recursiveness* (in the sense of Gödel and Herbrand) as alternative formalisms. Kleene's later (1936) paper proves these are equivalent. Should Scene 5's "triangle of equivalences" mention all three frameworks (λ-definability, Gödel-Herbrand recursiveness, Turing-computability) or just two (Church's, Turing's)?
- **Why it matters:** The "three independent frameworks converge on one mathematical object" is a more accurate framing than "two frameworks converge." But it adds a layer of technical detail that may or may not earn its narrative cost.
- **Evidence needed:** Editorial decision. Anchors are already in `sources.md` (Church 1936 §7 p.356 references both; Kleene's equivalence proof attestation pending Davis 1965 anthology page anchor).
- **Status:** Yellow. Non-blocking; resolve during prose-draft outline.

## Notes on resolution sequence

The order of attempted resolution:
1. ✅ **Done (Claude 2026-04-28):** Turing 1936, Church 1936, Gödel 1931 — all three primary papers anchored at page level via `pdftotext` extraction. **17 Scene-Level Claim Table rows promoted to Green.**
2. ✅ **Done (Claude 2026-04-28):** Stanford Encyclopedia "Church-Turing Thesis" (Copeland) and "Turing" (Hodges) — anchored via verbatim WebFetch quotes; framing claims and priority chronology Green.
3. **Tractable but not yet done:** Hodges 1983 *Alan Turing: The Enigma* page anchors for biographical claims (resolves Q2, Q3, Q5, Q7).
4. **Tractable but not yet done:** Davis 2000 *The Universal Computer* page anchors for the Leibniz-to-Turing lineage framing in Scene 4.
5. **Tractable but not yet done:** Davis 1965 *The Undecidable* page anchors for cross-checking Gödel/Turing/Church translations against Hirzel/Meltzer.
6. **Tractable but not yet done:** Church 1936b "A Note on the Entscheidungsproblem" JSL 1(1) page anchors (resolves a small Yellow on Scene 2; non-blocking for prose drafting).
7. **Tractable but not yet done:** Church 1937 *JSL* review of Turing 1936, p.43 page anchor for the "Turing machine" coining (resolves a Yellow on Scene 5).
8. **Out of scope for this contract:** Hilbert correspondence (Göttingen archives), Turing correspondence (King's College Cambridge archives at turingarchive.kings.cam.ac.uk), Newman correspondence — archive-blocked or requiring physical access. None are blocking for `capacity_plan_anchored` status.

The chapter has now reached **`capacity_plan_anchored`** status: every Prose Capacity Plan layer in `brief.md` cites at least one specific page anchor in `sources.md`, and 17 of 21 Scene-Level Claim Table rows are Green via direct primary-source `pdftotext` extraction (Turing 1936, Church 1936, Gödel 1931 Hirzel/Meltzer translations, Stanford Encyclopedia entries with verbatim WebFetch confirmation).

Promotion of additional scenes from Yellow to Green is a stretch upgrade pursued via items 3-7 above. None are blocking for cross-family review of this contract.
