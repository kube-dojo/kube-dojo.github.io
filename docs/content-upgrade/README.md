# KubeDojo complete content upgrade

## Mandate

Upgrade the complete KubeDojo curriculum, Ukrainian edition, and AI/ML history book. This is a delivery program, not a sample-only review. Every current content page is in scope, including hubs, glossary, navigation, exercises, assessments, reference pages, and the 73-chapter book. New material is justified by demonstrated learning or factual-coverage gaps, not a target page count.

The user's governing instruction is that content must be backed by facts. Do not invent incidents, historical dialogue, internal thoughts, quotes, citations, metrics, benchmark results, expected outputs, or learner evidence. Clearly marked controlled exercises can use synthetic inputs, but must teach a verified concept, expose their assumptions, and never pretend to be historical events or production measurements. Do not impose mystery, discovery, role-play, or gamification as a house style. Make reading worthwhile through clarity, thoughtful examples, accurate explanation, and useful practice.

Accountable lead: the current Codex task. GitHub is the work-status authority. Local plans explain scope and evidence; worker reports and heuristic dashboards do not independently prove completion.

Current [review results and recommendation reconciliation](review-status.md) record examined revisions, findings, repairs and remaining coverage. Previously fixed pages remain in the full-page review scope; a closed repair ticket does not exempt its surrounding content.

## Baseline and scope

Initial inventory at commit `8dd9bbd4cccffdef62b426cf987a0e4c5a8c92cb`: 1,639 Markdown/MDX files; 1,083 English pages and 556 Ukrainian pages. English curriculum contains 828 module files, plus 73 book chapters. Counts must be regenerated when the checkout changes. The earlier [audit](../content-review-and-expansion-plan-2026-09-04.md) contains sample findings and methodological limits.

| Portfolio | EN pages | EN modules/chapters | Scope of upgrade |
|---|---:|---:|---|
| Prerequisites | 51 | 44 | Entry route, terminal, Git, networking, containers, Kubernetes basics, realistic workload |
| Linux | 49 | 37 | Foundations, container primitives, operations, troubleshooting, security, portable lab setup |
| Kubernetes | 261 | 195 | All certification/specialty routes, current official objective mapping, labs and assessments |
| Cloud | 104 | 92 | All three providers, managed Kubernetes, architecture, hybrid and advanced operations |
| Platform | 286 | 242 | Every foundation, discipline, and toolkit; conceptual progression and operational validation |
| On-premises | 67 | 57 | Planning, provisioning, networking, storage, security, resilience, operations, multi-cluster, AI infrastructure |
| AI | 44 | 37 | Literacy, everyday use, building, engineering foundations, infrastructure applications, local models |
| AI/ML Engineering | 142 | 124 | Prerequisites through mathematical foundations, classical ML, deep learning, generation, serving and operations |
| AI history | 74 | 73 | All nine parts, all chapters, research contracts, sources, historical accuracy, readability and technical explanation |
| Shared English pages | 5 | — | Landing/support pages, glossary, progress, status, error routes and their integration |
| Ukrainian edition | 556 present | 394 module counterparts | All corresponding routes: factual and pedagogical fidelity, missing pages, freshness, terminology and UI |

No topic is declared absent based on a filename or heading scan. Match outcomes to actual paragraphs, examples, and assessments. Verify current external authorities before changing exam, version, service, price, law, benchmark, or product claims. Source access failures are unknowns, not license to fill from model memory.

## Work packages

The companion [track program](track-program.md), [book program](book-program.md), and [acceptance contract](evidence-and-acceptance.md) define the detailed work. GitHub workstreams cover the full portfolios; execution issues and PRs remain bounded by explicit page paths and outcomes.

1. **Inventory and evidence ledger.** Enumerate every EN and UK page, route, section, type, source revision, and counterpart. Record review disposition and evidence separately from structural metrics. Audit new pages added during delivery too. Existing page count must not become a frozen denominator that hides later additions.
2. **Standards alignment.** Resolve conflicting writer/reviewer templates, source-check timing, complexity markers, fixed word floors, and completion terminology in separately reviewed changes. Keep existing enforcement until its reviewed replacement is ready. Prefer enough depth for the outcome over arbitrary expansion. No blanket template rewrite.

   The existing v2 workflow can draft before downstream citation backfill. Such work remains provisional: the upgrade must not declare factual/source acceptance or publish an upgraded page until claim support and source-fidelity review are complete with sources available. G02 owns the reviewed policy/tooling reconciliation; no inherited rubric text is silently removed as part of this plan.
3. **Factual/source verification.** Audit load-bearing factual claims and quotations throughout the site. Record exact source, locator, date checked, version/date scope, supported claim, uncertainties, and reviewer. Links alone do not prove support. Use authoritative primary sources and appropriate independent historical corroboration.
4. **All eight curriculum portfolios.** Review every section's outcomes and every page's contribution. Preserve sound material; repair accuracy, scaffolding, duplication, workload, and weak exercises; author new content only after proving the gap. Every workstream includes its hubs and next-step routes.
5. **Labs and assessments.** Map each applied outcome to a task that demonstrates it. Record setup, versions, prerequisites, resource/cost boundaries, expected vs observed output, troubleshooting, verification, and cleanup. A fixture test does not prove a cloud lab or production behavior. Offer an explicit non-executed status when required infrastructure is unavailable.
6. **Cross-track application.** Develop a small set of coherent applied routes connecting existing lessons. Use technically accurate, labeled sample applications and transparent datasets, not invented production success stories. Each route has a verifiable final artifact and a task requiring the learner to apply the concept to a different input.
7. **Complete book revision.** Reconcile all 73 chapter contracts and statuses; verify historical claims and public source references; revise pacing, transitions and explanations with an independent source-fidelity review. Preserve documented uncertainty. Reader-aid additions and prose revisions follow their distinct workflows.
8. **Complete Ukrainian edition.** Continue existing epic #1911. First repair semantic drift and explicit English fallbacks; stabilize EN sections, translate missing pages and assets, review fidelity and natural Ukrainian, then verify routes and source-revision freshness. Honor #2086's stronger translation-review requirements and #2110 terminology work.
9. **Reader experience and accessibility.** Validate navigation, prerequisites, search, math/diagram readability, mobile layout, keyboard access, accessible alternatives, and reading/progress controls in the rendered site. Extend existing components where needed; do not build a game layer by default.
10. **Maintenance and release.** Establish review triggers for versioned claims, source changes, superseded standards, broken references, and EN-to-UK divergence. Close the program only after the page ledger and deployment evidence reconcile; retain explicit unresolved items rather than silently waiving them.

## Sequencing and dependencies

**Wave A — foundations of the program:** inventory, standards/evidence contract, source and lab audit formats, and the known route defects. Start concrete verified fixes while inventory proceeds; do not turn governance into an indefinite prerequisite for useful work.

**Wave B — entry and continuity:** prerequisites and Linux, introductory AI, certification objective mapping, Ukrainian audience drift, book contract reconciliation. Independently verify chapter sources and cloud setup requirements in parallel. First batches calibrate the workflow; all remaining pages stay in the required queue.

**Wave C — breadth:** complete Kubernetes, cloud, on-premises, platform, and AI/ML section batches; all book parts move through fact-checking and editorial work. Sequence prerequisite concepts before their dependent lessons, but independent sections can progress concurrently.

**Wave D — full integration:** cross-track projects, stabilized-section translations, route/accessibility validation, whole-site regression and maintenance. Translation can follow completed sections throughout earlier waves; it does not wait for the entire English site to finish.

**Wave E — closeout:** reconcile every current page, new addition, linked issue, PR, review, execution receipt, translation counterpart and deployed route. Do not close merely because a sample, dashboard, build, or model review is green.

Parallelism: one accountable lead, at most three independent worker packets at a time by default, with disjoint owned paths. A source reviewer does not author the text they are independently judging. Select live healthy providers and preserve the repository's cross-family rules. Do not duplicate an active PR or lease. If a review provider is unavailable, continue independent research or implementation and leave the affected merge blocked.

## Issue and PR contract

Every execution issue identifies: parent workstream; exact owned paths; observed defect or demonstrated coverage gap; required source authorities; concrete change; dependencies; acceptance checks; reviewer requirements; and excluded unrelated work. Split changes exceeding 200 net changed lines or approaching 20 files into coherent PRs unless a reviewed issue explicitly provides another bounded budget. A workstream spanning a track must create page/section execution packets before authoring; a broad issue is not permission for a giant rewrite.

Every PR states the reviewed base/head, why the changes improve the stated outcomes, external claims checked, snippets actually run, checks not run and why, cross-family review, translation impact, and deployment evidence when applicable. Do not mark source support or execution from an expected output. Do not merge with unresolved material findings or failing required checks.

## Definition of complete

- Every current page has a reviewed disposition and traceable evidence; no page is skipped because its heuristic score was high.
- Every required factual claim has suitable support or is explicitly qualified/removed through review; disputed historical claims remain qualified.
- Every promised practical outcome has aligned practice and verification; runnable examples have execution receipts for their documented environment or remain visibly incomplete.
- All demonstrated curricular gaps have been filled or explicitly resolved with evidence, including full route continuity and essential prerequisites.
- All 73 book chapters have coherent contracts, reader-visible sources, factual/source-fidelity review, and appropriate editorial review.
- The Ukrainian edition covers the agreed full English content scope with checked fidelity, terminology, navigation, assets, and current source revisions; file existence alone is insufficient.
- Required code/content, link, citation, build, review and rendered/deployed checks pass for the final revision, with no material unresolved issue.
- GitHub parent/child status matches delivered evidence. No blanket closure, synthetic review stamps, fabricated learner tests, or silent scope reduction.

Learner feedback is useful evidence, but unavailable readers must be reported as unavailable. Do not invent user observations or statistical improvement. Technical and editorial reviewers can establish their own scoped findings; they cannot stand in for a completed learner study.
