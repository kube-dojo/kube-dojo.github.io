# Chapter 12 representation: source-preparation content spine

Source-only author proposal, not narrative prose, a source grade, independent approval or chapter clearance. New preparation scope is P-868 printed pp. 7–16; the approved opening at `3c8b01309388310d64de3a3778a1c193307ab5db` keeps its original pp. 1, 3, 5–6 scope and remains unchanged/unpublished. Atomic anchors and uncertainties are in source-map.md.

## Reader question and documented constraint

**Question:** how does the program identify the element heading a formula's right-hand subexpression and bring that single element into working memory?
**Constraint:** in the paper's model, information to be processed is brought from storage into working memory and then returned (p. 11 / RP09). A identifies the whole expression's storage location; P records an element's tree path. Storage order is arbitrary and used only for searching, because each element's own information locates it in the tree (RP05, RP07, RP10). Retrieval transfers one element, not its entire associated subexpression.

## Forward content sequence

1. Give retrieval its documented reason: processing uses working memory, not just the storage list (RP09). LL/LT formal definitions may be shortened; if retained, keep their specification/IPP sense and initial/boundary-information condition (RP01).
2. Introduce X(1.7) as the paper's name for the whole expression beside the formula (p. 9); introduce A(1.7) as its storage location when A first appears (pp. 10, 12), before the lookup. Preserve declared glyph normalization and G as a count of negation signs (RP02–RP07).
3. Follow the tree into the explicitly possible storage list. Add one RP11-backed introduction: specially located lists hold main elements of axioms/proved theorems (T), active problems (P), and inactive problems (Q). Say that list name P differs from position field P; do not imply these lists store entire expressions inside one working element (pp. 11–13).
4. Demonstrate exactly one derived `FR x y` lookup. After transfer, state that y holds only the ∨ element, carrying P=R and A(1.7), not the entire q ∨ ¬p subexpression. Reaching its child elements would require further operations; none are demonstrated. Use one clear illustrative-not-reported-run boundary, not repeated proof disclaimers (D01 / RP09, RP14–RP15).
5. Put the operation in its language context without an inventory of new terms: processing/control distinction and routine definition (RP17–RP19). If new-IP conditions are retained, preserve the source's format-to-conditions reasoning and subsequent-reference scope (RP21); a routine is not automatically a new IP.
6. Keep the handoff honest: this retrieval does not explain heuristic proof-search choices. The old section's search explanation is not dispensable merely because this example is accurate; the adoption blocker in budget-and-open-questions.md must be resolved before replacement.

## Source-derived example data

Source transcription: `-p .→. q v -p`, expression 1.7, printed p. 9. Normalized reader notation: `¬p → (q ∨ ¬p)`; the change of negation/disjunction glyphs and replacement of punctuation dots by parentheses are declared normalization, not a facsimile or a new formula (p. 8 notation; p. 9 unnumbered tree and footnote 7).

| Tree position P | Element shown in source | Checked interpretation |
|---|---|---|
| none | → | Main element; no left/right path from itself. |
| L | -p | Left subelement; G=1. |
| R | v | Right subelement; root of the right subexpression. |
| RL | q | Left child of the right subelement. |
| RR | -p | Right child of the right subelement; G=1. |

The two occurrences named p occupy different positions. The source gives H=3 variable places, J=2 distinct variable names ignoring negation, K=3 levels (p. 11). Its possible storage order is `(q,RL), (-p,L), (v,R), (→,none), (-p,RR)` at A(1.7) (p. 12); retain might, not an actual-memory or required-order claim.

## D01: proposed reader walkthrough, explicitly derived

| Step | Assumption or operation | What the permitted pages support |
|---|---|---|
| Input | Suppose working memory x holds the main element of X(1.7), including A(1.7) and position none. | Author-chosen initial condition using the p. 9 tree and pp. 10–11 fields; not a reported execution. |
| Locate | Apply the source's `FR x y`; append R to the empty/no-direction root path, yielding R. | Generic FR rule printed on p. 13; do not concatenate the literal word none into a new path. |
| Search | Search A(1.7)'s possible list in order until the element with P=R is found. | pp. 13–14 algorithm plus p. 12's possible order; that list's third element is v/R. |
| Transfer | Put only the ∨ element into y, with P=R and whole-expression location A(1.7). | pp. 10–11, 14: one element, not the entire q ∨ ¬p subexpression. Its references support later child lookups; no further operation is demonstrated here. |

**Hard limit:** Figure 2 on p. 15 is a generic control network with numbered instructions; it does not label these instructions FR or apply them to X(1.7). Explain the routine concept separately. Do not present the walkthrough as an actual LT routine, a proof, machine output, or a historical hand session. How FR sets H/J/K or handles a missing right subelement is UNKNOWN within the selected passage; do not invent those behaviors.

## Narrow naming correction proposal, separate from prose adoption

The existing published opening's line 70 contrasts an early machine name with later theorist usage and suggests a historical shift. P-868 printed p. 3 already names the system logic theorist (LT). Propose removing the implied chronology and recording only contemporaneous labels. This is a source-backed correction proposal, not a site edit or a claim about why either name was chosen (RP22).

## Terra revision handoff after independent R1

Terra revised only terra-prose.md using steps 1–4's source-backed clarity/coverage changes, retaining one lookup and a natural length below900. No proof strategy was invented to fill the adoption gap. A full executed routine would require new scope. Root owns the adoption budget and independent R2; no source grade or chapter clearance is assigned here.

**Revision checkpoint:** the 557-word R1 draft is historical at `5158aac9d1f81ce46bbc15fd6dc6ab8299c5834a`; revised Terra prose has589 words. Genuine independent R1 returned NEEDS_CHANGES for adoption coverage (F1) and element/subexpression clarity (F2), while confirming source fidelity through text and actual scan Reads. The earlier same-family check missed these material issues and remains historical. H/J/K values and a new diagram remain omitted; independent exact-head R2 is required, and adoption remains blocked on the search-coverage decision.
