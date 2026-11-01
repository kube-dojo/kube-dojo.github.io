# KubeDojo content upgrade: evidence and acceptance contract

## Scope and authority

This contract applies to every existing KubeDojo content page in `src/content/docs/`: English and Ukrainian hubs, modules, labs, and AI-history chapters. It governs the upgrade program; it does not replace `docs/quality-rubric.md`, `.claude/rules/durable-vendor-content.md`, or `docs/research/ai-history/TEAM_WORKFLOW.md`. Those documents remain binding. The 2026-09-04 audit is a planning baseline, not proof that any page is technically correct, deployed, or historically verified.

Facts, real incidents, quotations, metrics, dates, provider behavior, and causal claims require evidence. A teaching story may be fictional only when marked `Hypothetical scenario:`; a simulation must say what is simulated. Do not manufacture mysteries, clues, dialogue, motives, gamification, or “observed” output. Equations must be checked and their assumptions stated. Analogies must state where they stop matching the system. Discovery, prediction, and diagnosis are welcome learning activities, but the learner must not be misled about what is real.

## Record and status rules

Create one inventory record per page with canonical path, locale, page kind, source revision, owner, disposition, and evidence links. Every evidence layer below gets its own `pending`, `pass`, `fail`, `unknown`, or justified `not-applicable` status. A missing log, unavailable reviewer, stale source, or unrun lab is `unknown`, never `pass`. A directory name, frontmatter flag, green heuristic score, review request, or completion click never upgrades another layer.

Workflow labels such as `capacity_plan_anchored`, `prose_ready`, or `accepted` are evidence-backed states within their workflow; they are not substitutes for this record or for deployed and learner evidence.

Every page starts as **unreviewed**. Once the relevant review establishes a disposition, record exactly one of:

- **retain**: the current scope is supported by review evidence and no evidenced defect requires a change. Retain does not claim that untested layers passed.
- **revise**: a named factual, source, audience, structure, route, accessibility, translation, or lab defect requires a bounded correction. Record the finding and the changed behavior.
- **expand**: a specific missing outcome, transition, practice opportunity, or supported coverage layer is evidenced by the audit, review, or learner observation. Name the evidence and the intended learner change.

There is no quota of rewrites or expansions, and no page must add a mystery or gamification layer to pass. Do not rewrite to satisfy line counts, headings, or a word floor. A review-backed retain decision can coexist with an unrun lab, but that page is not fully accepted; disposition and layer acceptance remain separate. Learner research is required only to support claims about measured learner improvement, not as an invented gate for every technical correction.

## Independent evidence layers

| Layer | What must be shown | Passing evidence and boundary |
|---|---|---|
| **Page presence** | The intended page and route exist. | A reproducible inventory (`rg --files` or equivalent), canonical path, frontmatter, and resolved source links. An exact EN/UK counterpart proves presence only; it proves neither fidelity nor freshness. |
| **Structural checks** | The source is parseable and follows repository conventions. | Deterministic checker/build output covering frontmatter, sidebar/order, headings, links, MDX/code fences, complexity marker, and accessible assets as applicable. A structural pass says nothing about truth, pedagogy, deployment, or runnable behavior. |
| **Technical and source verification** | Claims and examples are correct for their stated scope. | A claim-to-source record with page/section/figure/URL anchors, dates for volatile claims, and checked command/version assumptions. The rubric citation gate applies before a module can receive a 4/5 or 5/5; every real war story has an explicit citation or `Source:` line. Vendor facts live in dated snapshots/Rosetta tables and are web/browser-rechecked against current upstream documentation. A source list alone is insufficient. Record equation checks, analogy limits, and whether outputs are illustrative or actually observed. |
| **Editorial review** | The page teaches its stated outcomes at the target complexity. | A fresh review using the current module/lab rubric, including per-dimension floors and applicable sum thresholds, with text-level findings and a disposition. The reviewer must be independent of the author’s model family. Use the live catalog, routing, health, and quota signals; an unavailable family is an evidence gap. Do not close on a green heuristic or metadata readiness score. |
| **Lab execution** | A lab works and tests understanding. | From a clean, documented environment, record setup, exact commands, environment/fixture or provider identity, stdout/stderr, expected-versus-observed results, failure injection where promised, hints, and reset/cleanup. Validate behavior and reasoning, not object existence. Fixture-backed execution proves fixture behavior only; label provider simulations and never imply a real provider call. An unrun or partially run lab remains unverified. |
| **Translation fidelity** | The Ukrainian page serves the same learner and intent as its English source. | Pin both source revisions. A bilingual reviewer checks outcomes, terminology, prose meaning, commands/paths, diagrams, quiz explanations, lab steps, and fallback links. Record unresolved drift and intentional English fallback. File-count parity is presence evidence, not translation acceptance. |
| **Deployed smoke** | Published pages match the reviewed source and function for readers. | Record build commit, deployment environment, URL, timestamp, and smoke results for representative EN, UK, book, route, link, asset, and lab surfaces. A local source check or successful build does not prove deployment; an unreachable or mismatched deployment is `unknown`/`fail`. |
| **Learner data** | The claimed learner improvement is real and bounded. | With consent and privacy-safe records, report route/page revision, cohort and sample size, time to first success, setup failures, hint use, unfamiliar transfer, delayed explanation/recall, and confusion/boredom observations. Page views and completion clicks are not mastery. Small qualitative pilots support findings to test, not population effect sizes. |

## Closure sequence

For a choose-one-path exercise, execute the declared applicable learner path,
including its required verification and cleanup. Other supported OS/shell branches
may remain source-checked and explicitly unexecuted; do not claim observed behavior
there. A branch essential to the stated outcome still needs applicable execution.
A desktop-inspection tool restriction does not itself create a requirement for a
separate GUI demonstration. Missing evidence of an actual required action remains
unknown. Do not replace required exercise execution with source links alone.

For each wave, freeze the inventory and dispositions, run structural checks, verify technical/source claims, obtain independent editorial review, execute applicable labs, review translations, and then perform deployed smoke. Attach the evidence packet: inventory, command/checker logs, claim matrix, review verdicts, lab receipts, translation report, and deployment record. Add learner evidence when claiming an improvement in completion, understanding, transfer, or retention. Close only when every applicable layer is `pass` and no material finding is unresolved; otherwise retain the explicit status and blocker. A page’s content acceptance must not be represented as deployment or learner success.

## Word-floor harmonization

The verifier’s existing 5,000-word default and the AI-history workflow’s evidence-based `4k-7k`/natural-range discipline remain in force. This contract does not lower, bypass, or reinterpret either gate. Open a separately reviewed policy issue to reconcile track-specific floors, explicit budgets, exceptions, and migration evidence across the verifier, rubric, and history workflow. Until that issue is accepted, expand only when verified evidence and learner need support it; document a naturally shorter page rather than padding it.
