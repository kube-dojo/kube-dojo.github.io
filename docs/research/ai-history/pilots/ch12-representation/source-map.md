# Chapter 12 representation: ungraded atomic source proposals

All RP identifiers below are author proposals, not Green/Yellow/Red grades or independent approval. Only this packet's preparation scope is expanded. The [complete P-868 original](https://iiif.library.cmu.edu/file/Simon_box00006_fld00406_bdl0001_doc0001/Simon_box00006_fld00406_bdl0001_doc0001.pdf) remains read-only at primary `.agent/session229/book-opening-sol/P-868.pdf`, 64 pages, SHA-256 `33f718f6558c6ccc2e2882f4f35e4258eebc7a85ab1afe45c53463da2b8284cc`. No new retrieval was needed. This worktree's ignored `.agent/ch12-representation/` retains extraction/render code, complete selected-page text/renders and verification. Exact fragments below locate evidence; full-page context, diagrams and footnotes were read rather than inferred from fragments.

## Printed-to-PDF identity, visually checked page by page

| Printed | PDF one-based / zero-based index | Render and complete text under .agent/ch12-representation/pages/ |
|---|---|---|
| 7 | 8 / 7 | P-868-pdf-page-8.png / .txt |
| 8 | 9 / 8 | P-868-pdf-page-9.png / .txt |
| 9 | 10 / 9 | P-868-pdf-page-10.png / .txt |
| 10 | 11 / 10 | P-868-pdf-page-11.png / .txt |
| 11 | 12 / 11 | P-868-pdf-page-12.png / .txt |
| 12 | 13 / 12 | P-868-pdf-page-13.png / .txt |
| 13 | 14 / 13 | P-868-pdf-page-14.png / .txt |
| 14 | 15 / 14 | P-868-pdf-page-15.png / .txt |
| 15 | 16 / 15 | P-868-pdf-page-16.png / .txt |
| 16 | 17 / 16 | P-868-pdf-page-17.png / .txt |

The scans show printed headers, not merely a presumed one-page offset. OCR's p. 14 label and missing figure content were resolved from renders. P. 9's tree, p. 11's memory-unit drawing and p. 12's storage-list drawing are unnumbered; instruction format is Figure 1 on p. 12, control schematic Figure 2 on p. 15. Do not invent figure numbers for the unnumbered drawings. The raw render-manifest.json records the extraction stage; verification.json records completed author visual checks.

## Claims, actual anchors, exact fragments and scope

| Proposal | Atomic content / exact page and locator | Exact fragment | Qualification / context |
|---|---|---|---|
| RP01 | p. 7, Information Processing Systems: IPS has memories/processes; LL is IPS and LT a particular IPP. | “memories” | Determinate program behavior requires initial and supplied boundary information; no machine execution claim. |
| RP02 | p. 8, Symbolic Logic and 1.01: variables usually interpreted as sentences; not/or primitives; implication defined from them. | “usually” | Not a claim of natural-language understanding; normalized glyphs must be declared. |
| RP03 | p. 8, Coding: elements correspond to variables/connectives excluding punctuation dots and negation signs; symbols encode properties. | “excluding” | Element and symbol are not interchangeable; negation is a field, not another tree node here. |
| RP04 | p. 9, displayed expression 1.7 and explanatory parenthesis: -p implies q or -p. | “1.7” | Use the rendered expression; extraction damages arrow/dots. Footnote 7 permits understanding dots as punctuation replacing parentheses. |
| RP05 | p. 9, unnumbered tree: positions none/L/R/RL/RR and associated subexpressions. | “Right” | Root none means no path; the two p occurrences are separate places, not different variable names. |
| RP06 | p. 10, Symbol G: two p elements have G=1, the rest G=0; whole-expression negation belongs to its associated element. | “G” | No separate negation element; do not generalize to another formalism. |
| RP07 | p. 10, Symbols P/A/N: P is tree path, A location of the whole expression, N variable/expression name. | “whole” | A is not the individual element's address. F applies only to variable elements, C only to nonvariables; unit U is deferred. |
| RP08 | p. 11, H/J/K definitions: X(1.7) has H=3, J=2 ignoring negation, K=3. | “H” | These are the source's expression descriptors, not measured performance or counts of proved theorems. |
| RP09 | p. 11, Memory Structure / W drawing: a working memory holds one E plus H/J/K spaces. | “single” | Model distinguishes bringing information from storage to working memories and returning it; FR field-update details are not supplied here. |
| RP10 | pp. 11–12, storage paragraph / unnumbered list: list order arbitrary; X(1.7) might use q/RL,-p/L,v/R,→/none,-p/RR. | “might” | Possible order, not mandatory or observed layout. Order is used for searching; P retains tree position. |
| RP11 | p. 12, three special lists: T theorem/axioms, P active problems, Q inactive problems, containing main elements. | “main” | List name P is distinct from position field P; do not conflate namespaces. |
| RP12 | p. 12, Information Processes, Figure 1: operation, three reference places L/C/R and branch location B. | “three” | Format is a specification; no physical instruction encoding asserted. |
| RP13 | p. 13, reference/storage paragraphs: reference places refer to working memories; no direct storage reference except T/P/Q. | “except” | Ordinary storage lists are found through A in elements; preserve the exception. |
| RP14 | p. 13, displayed FR x y and following explanation: right subelement's P comes from appending R to P(x). | “appending” | Generic rule; initial x must identify an element with a right subelement for the proposed illustration. |
| RP15 | p. 14, first paragraph, continuing FR: search the storage list for correct P, transfer the element to working memory y. | “transfer” | No proof inference, formula mutation or H/J/K update is specified by this account. |
| RP16 | p. 14, Programs and Routines: discrete-time model assumes one process occurs at a time. | “assume” | An assumption of the description, not hardware timing or concurrency evidence. |
| RP17 | p. 14, operation components: processing changes memory; control transfers control; some control-significant IPs do not alter memory. | “some” | Do not claim every instruction changes memory contents. |
| RP18 | pp. 14–15, Control / Figure 2: binary branch; normally sequential; #2 can branch to A/#4 and #4 to B/#1. | “Normally” | Figure 2 is generic; it is not an X(1.7) or FR routine. |
| RP19 | p. 15, Routines: instruction list with a control network is called a routine. | “routine” | Conceptual handoff only; do not invent a named LT proof routine. |
| RP20 | p. 16, opening continuation: routine determines later memory contents if initial contents are specified. | “if” | Preserve the condition and duration scope, not unconditional determinism. |
| RP21 | p. 16, numbered conditions: only qualifying routines define new IPs; at most two external branch destinations and three changed working memories referenced subsequently. | “only” | Not three changed memories in total: other memories may change but cannot subsequently be referenced. Instruction format separately permits at most three working-memory references and one branch. |
| RP22 | prior permitted p. 3, paragraph naming LT: the same 1956 paper already calls the system logic theorist. | “logic theorist” | Narrow correction to published line 70's implied naming chronology only; no motive, date-of-renaming or source-grade change. |

**D01 derived proposal, not a direct source claim:** join RP04–RP10 with RP14–RP15 to assume x holds X(1.7)'s main element, locate R and transfer v/R into y; optionally repeat to RR in z. Actual formula/list/generic operation are source-derived; the chosen initial condition and concrete replay are this author's pedagogical instantiation. The paper does not print that execution or tie it to Figure 2. This is the main boundary for Root to resolve before Terra.

**Remaining UNKNOWN:** FR's H/J/K updates, missing-right-child behavior and an actual LT proof routine for X(1.7) are not established within pp. 7–16. P. 16 ends by introducing consequences continued outside this packet; do not supply them from inference. Exact expression glyphs, list order and numbered figure labels are now visually resolved, not UNKNOWN. Full-chapter source/acceptance gates remain outside scope.
