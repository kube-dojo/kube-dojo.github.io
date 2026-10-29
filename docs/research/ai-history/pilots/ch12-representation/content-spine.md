# Chapter 12 representation: source-preparation content spine

Source-only author proposal, not narrative prose, a source grade, independent approval or chapter clearance. New preparation scope is P-868 printed pp. 7–16; the approved opening at `3c8b01309388310d64de3a3778a1c193307ab5db` keeps its original pp. 1, 3, 5–6 scope and remains unchanged/unpublished. Atomic anchors and uncertainties are in source-map.md.

## Reader question and documented constraint

**Question:** when a program needs the right-hand part of a formula, how does it identify that part and bring it into working memory?
**Constraint:** the structural tree and the storage list are different organizations. A identifies the whole expression's storage location; P records an element's path in the tree. Storage order is arbitrary in this specification and supports searching, rather than supplying the expression's tree structure (RP05, RP07, RP10). Do not imply the program reads mathematical prose or that a computer run is being reconstructed.

## Forward content sequence

1. Bridge from LL to representation: LL is an IPS of memories/processes; LT is a particular IPP with rules for when processes occur. Determinate behavior is conditioned on initial/boundary information (RP01).
2. Introduce the paper's actual X(1.7), not an invented theorem. Contrast an element with symbols recording its properties; negation is represented by G rather than an extra element (RP02–RP06).
3. Follow the same expression from its tree into the paper's explicitly possible storage list. Explain A versus P before giving a memory operation (RP07–RP10).
4. Use the source's FR operation for a transparent reader walkthrough, with explicit assumed input memory. Separate this derived instantiation from what the paper itself directly prints (D01).
5. Put the operation in its language context: working-memory reference places, special T/P/Q lists, processing/control components, routine sequencing and limits on defining new IPs (RP11–RP21). A routine is not automatically a new IP.
6. Handoff: locating and transferring part of an expression makes a representation inspectable; choosing a successful proof-search method is a further question. These pages alone do not supply an executed proof of X(1.7).

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
| Transfer | Put that element into working memory y. | p. 14's transfer completes this one source-derived operation; it does not change or prove the formula. |
| Optional second lookup | If the writer needs it, apply the same rule from y's P=R to a fresh working memory z, obtaining RR and the -p element. | Derived repetition of the same rule, not a source-printed trace or proof routine; omit if it costs words without new explanation. |

**Hard limit:** Figure 2 on p. 15 is a generic control network with numbered instructions; it does not label these instructions FR or apply them to X(1.7). Explain the routine concept separately. Do not present the walkthrough as an actual LT routine, a proof, machine output, or a historical hand session. How FR sets H/J/K or handles a missing right subelement is UNKNOWN within the selected passage; do not invent those behaviors.

## Narrow naming correction proposal, separate from prose adoption

The existing published opening's line 70 contrasts an early machine name with later theorist usage and suggests a historical shift. P-868 printed p. 3 already names the system logic theorist (LT). Propose removing the implied chronology and recording only contemporaneous labels. This is a source-backed correction proposal, not a site edit or a claim about why either name was chosen (RP22).

## Before any Terra prose pass

Root should resolve the permitted scope of D01, adopt a replacement budget, and review the atomic proposals/qualifier lock. Terra may reorder and explain verified material, not invent a proof trace, runtime, memory-update rule or motive. Any full executed routine would require a new source scope. Full-chapter GPS/implementation/secondary-source gates remain open; no new source or chapter grade is assigned here.

**Prose-stage lead decision:** authorize exactly one explicitly derived root-to-R lookup, omit the optional second lookup, and use ≤900 words as a ceiling rather than a target. Terra's resulting557-word draft is in terra-prose.md. Sol's same-family semantic author check found no material errors; independent source/prose review and actual reviewer scan inspection remain pending. H/J/K and a new diagram are omitted from the prose; no full-chapter contract or source clearance follows.
