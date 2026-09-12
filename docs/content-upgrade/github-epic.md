## Objective

Deliver the complete KubeDojo content upgrade: all curriculum tracks, the complete Ukrainian edition, and all 73 AI/ML history chapters. Improve factual accuracy, explanation, learning progression, practical work, assessment, readability, accessibility, and ongoing maintenance. This is implementation work with verification, not a sample audit or a request to generate more pages indiscriminately.

Accountable lead: the Codex content-upgrade task. GitHub issues/PRs and their evidence are the authoritative progress record. Work proceeds in disjoint, bounded batches with cross-family review before merge.

## Non-negotiable evidence standard

- Every load-bearing factual claim, historical detail, quotation, incident, numerical result, benchmark, product/version assertion, and technical instruction must have suitable evidence. Record the exact source/locator, verification date, applicability, and uncertainties.
- Never fabricate dialogue, historical scenes, internal thoughts, sources, quotations, execution results, learner feedback, or production incidents. A source link is not proof that it supports a claim.
- Controlled teaching examples must be explicitly labeled as synthetic/simulated and technically reproducible. Do not frame them as real events. No forced mystery, role-play, gamification, or discovery gimmicks.
- State disagreement and limited evidence honestly. Unavailable verification stays incomplete. Do not upgrade uncertain research claims or review stamps.
- Preserve good content. Every page gets an evidence-backed retain/revise/expand disposition; no quota of rewritten words. Do not weaken existing gates to pass a batch. Any policy change is a separate reviewed deliverable.

## Full scope

Baseline: commit `8dd9bbd4cccffdef62b426cf987a0e4c5a8c92cb`, 2026-09-04. File presence is not a quality/fidelity verdict.

| Portfolio | English pages | Modules/chapters |
|---|---:|---:|
| Prerequisites | 51 | 44 |
| Linux | 49 | 37 |
| Kubernetes certifications and specialties | 261 | 195 |
| Cloud | 104 | 92 |
| Platform foundations, disciplines and toolkits | 286 | 242 |
| On-premises | 67 | 57 |
| AI | 44 | 37 |
| AI/ML Engineering | 142 | 124 |
| AI history book | 74 | 73 |
| Shared English pages | 5 | — |
| Ukrainian edition | 556 existing | Complete corresponding English scope required |

Total current Markdown/MDX pages: 1,639; English modules: 828. Regenerate the inventory throughout delivery, including newly added pages.

## Workstreams and dependencies

The linked child issues below own the full portfolios. Each track/part workstream must enumerate exact page/section execution packets before authoring; it cannot close after a representative sample.

1. Inventory every page and establish a revision-bound evidence ledger.
2. Align writing, sourcing, quality, word-budget and review standards without silently weakening enforcement.
3. Verify source support throughout the corpus and separate factual, structural, editorial, execution and deployment status.
4. Upgrade every curriculum section, starting with prerequisite continuity and the verified defects from the initial audit.
5. Align practical outcomes with reproducible labs, troubleshooting, assessment and explicit cost/setup/cleanup boundaries.
6. Complete book contract reconciliation, all-chapter factual/source verification, public references, and source-preserving editorial revision.
7. Complete Ukrainian missing-page and fidelity work under existing epic #1911; preserve #2086 review-gate and #2110 terminology ownership.
8. Integrate applied routes, accessibility/navigation, version/source freshness, and final deployed verification.

Initial audit found long beginner lessons, saturated structural scores, under-tested practical outcomes, a UK/EN audience mismatch, 61 book chapters without a Sources heading, 36 without main narrative headings, and a 73rd chapter absent from the 72-contract research map. These are starting findings, not the entirety of the program. Heading scans alone do not establish content absence.

## Delivery order

- **A:** ledger, evidence standards, concrete route/lab defects; source verification starts immediately.
- **B:** prerequisites/Linux/introductory AI, official certification mapping, book contract reconciliation.
- **C:** every remaining curriculum section and all nine book parts, in prerequisite-aware batches.
- **D:** applied routes, translations of stabilized sections, accessibility and cross-track integration. Translation can run as soon as individual EN sections stabilize.
- **E:** full inventory and issue reconciliation, final tests/reviews/deployed checks, maintenance ownership.

Each execution issue names owned paths, facts to verify, changes, dependencies, acceptance checks, review requirements, and scope limits. Default PR scope is under 20 files and at most 200 net changed lines; split larger work into coherent batches unless the issue explicitly sets another reviewed budget. No direct work on primary main, unrelated edits, unrequested deletion, duplicate leases, or merge with unresolved findings/failing checks.

Planning-deliverable exception: the seven source-controlled audit/program documents for this epic may total up to 550 added lines in one documentation-only PR. This records the complete reviewed scope and issue catalog; it does not authorize a larger curriculum/code rewrite. #2273 separately permits up to 500 lines across its three inventory/receipt/test files because they form one evidence-integrity boundary.

## Completion criteria

- [ ] Every current page has an evidence-backed reviewed disposition, including additions made during this program.
- [ ] Every demonstrated coverage gap is filled or explicitly resolved with evidence; all eight curriculum portfolios and their hubs are accounted for.
- [ ] Factual/source and editorial checks are recorded separately from structural scores; unsupported claims are corrected, qualified, or removed through review.
- [ ] Practical outcomes have aligned exercises and actual execution/verification receipts for their documented environments; unexecuted labs remain incomplete.
- [ ] All 73 book chapters have coherent research contracts/status, reader-visible sources, source-fidelity review, and appropriate editorial review.
- [ ] The full Ukrainian edition has current source revisions, checked factual/pedagogical fidelity, natural language/terminology review, and working routes/assets under the required reviewer-family gates.
- [ ] Applied routes, accessibility, links, citations, required tests/builds and deployed smoke checks pass at the final delivered revision.
- [ ] Existing translation issues and every child issue/PR reconcile with delivery evidence; no blanket closure or silent reduction to a pilot.
- [ ] Freshness and maintenance checks are documented and operational, with unknowns and blockers explicit.

The closed original book epic #394 is historical context; this is the follow-on upgrade program, not a new claim that the existing book is unwritten.

## Child issues

- [ ] #2273 — [Content upgrade G01] Build a complete revision-bound content inventory and evidence ledger
- [ ] #2274 — [Content upgrade G02] Align factual, editorial, workload and completion standards across writer/reviewer tooling
- [ ] #2275 — [Content upgrade G03] Verify factual claims and source support across all curriculum pages
- [ ] #2276 — [Content upgrade G04] Establish reproducible lab validation and receipts for every practical route
- [ ] #2277 — [Content upgrade G05] Align learning outcomes, worked examples and assessments throughout the curriculum
- [ ] #2278 — [Content upgrade T01] Upgrade every Prerequisites section and beginner route
- [ ] #2279 — [Content upgrade T02] Upgrade every Linux section with verified system behavior and practical diagnosis
- [ ] #2280 — [Content upgrade T03] Upgrade all Kubernetes certification and specialty routes against verified objectives
- [ ] #2281 — [Content upgrade T04] Upgrade every Cloud section and provider-specific learning route
- [ ] #2282 — [Content upgrade T05] Upgrade all Platform Foundations with accurate mental models and applied reasoning
- [ ] #2283 — [Content upgrade T06] Upgrade all Platform Disciplines and operational decision workflows
- [ ] #2284 — [Content upgrade T07] Upgrade all Platform Toolkits with versioned runnable examples
- [ ] #2285 — [Content upgrade T08] Upgrade every On-Premises section and infrastructure readiness path
- [ ] #2286 — [Content upgrade T09] Upgrade the entire AI literacy and practical-use curriculum
- [ ] #2287 — [Content upgrade T10] Upgrade all AI/ML Engineering phases from prerequisites to production
- [ ] #2288 — [Content upgrade B01] Reconcile all 73 history chapter contracts, review states and roadmap
- [ ] #2289 — [Content upgrade B02] Fact-check every history chapter and expose reader-visible source provenance
- [ ] #2290 — [Content upgrade B03] Revise the complete history book for coherent, accurate and readable narrative
- [ ] #2291 — [Content upgrade L01] Rebaseline Ukrainian fidelity, freshness and route coverage under the existing translation epic
- [ ] #2292 — [Content upgrade X01] Deliver coherent cross-track applied routes with verified outcomes
- [ ] #2293 — [Content upgrade X02] Verify and improve reader navigation, accessibility and rendered content across the site
- [ ] #2294 — [Content upgrade X03] Operationalize content freshness, source rechecks and EN-to-UK drift maintenance
- [ ] #2295 — [Content upgrade X04] Complete whole-program release verification and evidence-based closeout
- [ ] #2296 — [Content upgrade F01] Restore beginner-audience fidelity in Ukrainian What Is AI
- [ ] #2297 — [Content upgrade F02] Make the Deployments lab actually diagnose and repair a failed rollout
- [ ] #2298 — [Content upgrade F03] Repair AWS VPC lab preflight, flow-log prerequisites and behavioral verification
- [ ] #2299 — [Content upgrade F04] Add verified public source references to History Chapter 1
- [ ] #2300 — [Content upgrade X05] Upgrade all shared reference pages and landing-page editorial content
- [ ] #2542 — [Content upgrade X06] Standing Kubernetes release onboarding (exam-pin + latest-stable)
- [ ] #1911 — existing complete Ukrainian translation epic (retained ownership)
- [ ] #2086 — existing translation review gate
- [ ] #2110 — existing Ukrainian terminology normalization

This epic remains open until all completion criteria are proven. Dependency gates apply per affected page/section; first fixes can proceed without waiting for the entire parent workstream to finish.

## Independent planning review

An initial Google-family review requested explicit shared-page editorial ownership and stronger dependency coverage. #2300 owns shared-page/landing text; #2292 now coordinates every integrated infrastructure portfolio; #2295 explicitly depends on all first-fix issues and shared-page work. #2274 now explicitly reconciles the inherited v2 citation-backfill seam: no final factual acceptance or publication before claim support and source-fidelity review with sources available. The existing rubric is not silently edited by this planning change. The Google-family second review approved the revised structural plan and tracking documents on 2026-09-04; this is not content, source, lab, or deployment clearance.
