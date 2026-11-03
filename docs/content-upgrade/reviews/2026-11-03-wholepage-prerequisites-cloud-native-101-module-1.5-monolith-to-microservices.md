# Reviews of prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for all three: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. No cluster lab was run by any reviewer. Call 3 was a CTO-granted pinned verification round limited to the one remaining blocker (a leftover appended card section) and the coherence margin.

## kd-wp-cn15-r1: call 1 of 2, whole-page review

- reviewed head: `db9429f8c7df5f4027566c580b11da5daba12e05`
- run nonce: `8885123c53aa4a219c79e3cbf48c52e9`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md at HEAD db9429f8c7df5f4027566c580b11da5daba12e05 is 281ccc15f2b19736bf0c7c1c5092eedf704e5fce29eb45d696be7d0f026d5bdb, which matches the supplied digest. I read all 614 lines. No page-specific claim ledger exists for this page. The source catalogs only list frontmatter, hub-table spans and the hub's 1.5 row, so every body-claim judgment below is mine. DISPOSITION: revise, confidence 0.8.

D1-D8 (module rubric):
- D1 outcomes 4: four clear outcomes, each taught and quizzed.
- D2 accuracy 3: two cited-source overstatements (BLOCK-1, BLOCK-2).
- D3 teaching depth/mechanisms 3: the mechanisms are good, but key terms are used or only name-dropped without explanation (BLOCK-4).
- D4 examples/practice alignment 4: seven scenario quiz items, six tasks, four solution guides and four reveal cards align well, but Card D refers to a nonexistent diagram (BLOCK-3).
- D5 coherence/sequence 3: canned meta-transitions at lines 81, 134 and 149, a process note at 381, and a stray checkbox and appended cards at 556-558 (BLOCK-5).
- D6 audience fit 3: a prerequisite of Module 1.3 only, but the text uses idempotency, ACID, eventual consistency, bounded context, saga and outbox without definitions.
- D7 concision/no bloat 3: the same scenarios are restated up to five times (NB-2) and there is filler (BLOCK-5).
- D8 safety/honesty 4: the scenario is labelled hypothetical, the Kubernetes 1.35 version scope is hedged, and there is no unsafe advice. The two overstatements keep it from 5.
Total 27/40. The floors are not met: four dimensions are below 4 and the total is under 33.

L1-L5 (applied proportionately; the exercise is a design review, not an executable lab):
- L1 objective 4.
- L2 steps/clarity 4: six tasks, but no worked sample answer and no tiered hints.
- L3 verification/feedback 4: success criteria, four solution guides and four reveal cards. Tasks 2 (compare scaling pressure) and 6 (review the decision) have no guide. Card D is broken (BLOCK-3).
- L4 cleanup 5: nothing is created.
- L5 safety 5: the only command is the optional read-only `kubectl get pods -A`.
Total 23/25. The lab floors are met, but the module floors are not.

LAB_EXECUTION: not run. The host has no cluster. The only command is an optional, read-only `kubectl get pods -A`, which nobody ran, and the exercise needs no execution. Nothing is presented as verified.

SOURCE_STATUS: partly supported. I judged 13 claims. 8 are supported: the Venice workshop in May 2011, the 25 March 2014 Fowler/Lewis article date, Conway 1968, Segment's July 2018 consolidation story, Shopify as a modular monolith in a very large Rails codebase, kubelet container restarts versus controller Pod replacement, readiness failure removing the Pod from EndpointSlices, and Ingress needing a controller. 2 are unsupported or overstated (BLOCK-1, BLOCK-2). 1 is partly supported (Ingress, NB-1). 2 are not checked: Strangler Fig and Amazon Builders' Library. Those sources were not opened, so they are unknown, not a pass.

BLOCKING findings:
- BLOCK-1 (line 447): 'hundreds of small services' versus the source's 'over 140 services'.
- BLOCK-2 (line 386): 'Shopify handles massive global e-commerce traffic' is not in the cited article, which gives no traffic figures.
- BLOCK-3 (line 587): Card D says 'The diagram shows four services', but no such diagram exists. The page's only microservice diagram shows three services.
- BLOCK-4, under-explanation (lines 138, 517, 527, 388, 391, 130, 252, 280, 290, 343): 'distributed monolith' is used in Task 1 and Card D, and is only defined inside a collapsed solution guide, after the task that needs it. 'Idempotency' is relied on repeatedly, including in the payment invariant, and is never defined. 'Eventual consistency', 'circuit breaker', 'bounded context', 'majestic monolith', 'sagas' and 'outbox tables' are used without definition. The page never states that sagas and outbox tables are names it does not teach.
- BLOCK-5, bloat/abrupt transitions (lines 81, 134, 149, 381, 556-558, 87): the meta-instructions 'Hold the user-facing effect before you read on...', 'Write that design change down before the schema discussion...' and 'List the operational work before you read...' are filler. Line 81 adds 'It does not describe what the saturated database did to login', which is confusing. Line 381, 'The original misconceptions are worth preserving...', leaks editing history to the learner. A stray checkbox at line 556 sits after Success Criteria and precedes unrelated cards. The kubectl-naming paragraph at line 87 is off-topic padding.

NON-BLOCKING findings:
- NB-1 (line 292, Ingress/Gateway API): the Kubernetes Ingress page now says Ingress is frozen and recommends Gateway API. The page and Task 4 steer learners to Ingress only, and Gateway API is never named. Fix: one sentence.
- NB-2 (lines 205/426/440/478/533, 322/428/496/389, 140/472/578): scenarios repeat across the lesson body, decision table, quiz and misconception table. Cards A and C near-verbatim repeat earlier predict prompts. Some retrieval is useful, so I did not block on it.
- NB-3 (line 309): 'share networking and lifecycle' is loose. Containers in a Pod share the network namespace and volumes, and the page itself says at line 349 that a sidecar 'can fail independently'. The restart doc exempts native sidecar containers from the Pod-level restartPolicy.
- NB-4 (line 599): the Amazon Builders' Library source is listed but no claim in the text uses it.
- NB-5 (lines 385, 389): 'Often a disastrous choice' and 'immense cognitive and operational load' are unsupported intensifiers.
- NB-6: Tasks 2 and 6 have no solution guide, and nothing offers tiered hints.

OMITTED-CLAIM DISCOVERY (beyond the two blockers above): 'Segment... then later consolidating' (line 266) is fine. 'Service mesh builds on the sidecar idea' (line 320) is time-dependent, since sidecarless mesh modes exist. It is acceptable, but a hedge would help. Volatile versions are limited to the hedged 'Kubernetes 1.35+', and there are no prices or quotas.

URLS ACTUALLY OPENED: https://www.twilio.com/en-us/blog/developers/best-practices/goodbye-microservices/ (via the 301 redirect from segment.com), https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity, https://martinfowler.com/articles/microservices.html, https://kubernetes.io/docs/concepts/services-networking/ingress/ (read through character 100000 of 129228), https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/ (two passes, both read through character 200000 of 155668). Each was read through a summarizing fetch tool, not raw. NOT OPENED: Strangler Fig, Monolith First, Amazon, and the Kubernetes Services, Deployments, probes, ConfigMaps and Secrets pages.

VERIFIED BY ME: the digest, the full page text, the review contract, the completion plan, grep checks for undefined terms and the nonexistent diagram, git log, and the source-catalog and page-reviews mentions. TAKEN FROM SUPPLIED EVIDENCE: nothing was relied on as correct. The old page-reviews history is void.

PROVENANCE: reviewer Claude Code, actual model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), Claude Agent SDK CLI harness, read-only checkout. Review kind: whole-page review, call 1 of 2. LIMITS: no rendered-site build, and no commands were executed beyond reads, sha256sum, git log and grep.

### Findings (verbatim JSON)

```json
[
 {
  "id": "BLOCK-1",
  "title": "Segment 'hundreds of services' contradicts the cited source",
  "body": "The Did You Know says Segment moved away from 'hundreds' of small services. The cited Segment post says 'over 140 services' (published July 10, 2018).",
  "priority": "P2",
  "confidence": 0.85,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 447,
   "end_line": 447,
   "claim_type": "present"
  },
  "verbatim": "In 2018, Segment described moving away from hundreds of small services because operational overhead and duplicated work were hurting engineering velocity.",
  "why_wrong": "The source gives over 140 services, not hundreds. This is unsupported inflation of a cited number.",
  "smallest_fix": "Change 'hundreds of small services' to 'more than 140 services' (or 'well over a hundred services').",
  "sources": [
   "https://www.twilio.com/en-us/blog/developers/best-practices/goodbye-microservices/"
  ]
 },
 {
  "id": "BLOCK-2",
  "title": "Shopify 'massive global traffic' not supported by the cited article",
  "body": "The misconceptions table says Shopify handles massive global e-commerce traffic with a monolithic Rails app. The cited Shopify Engineering article gives no traffic or request-volume figures. It says Shopify is 'one of the largest Ruby on Rails codebases', worked on by more than a thousand developers. It also says Shopify chose to evolve into a modular monolith because the codebase had become hard to work in. The article is dated 2019.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 386,
   "end_line": 386,
   "claim_type": "present"
  },
  "verbatim": "Shopify handles massive global e-commerce traffic with a monolithic Ruby on Rails application.",
  "why_wrong": "Unsupported specificity attributed to a source. It also omits that the cited article describes Shopify moving to a deliberately modular monolith, and it is an undated, time-dependent claim.",
  "smallest_fix": "Rewrite as: 'Shopify (2019 engineering post) describes one of the largest Rails codebases and deliberately evolved it into a modular monolith.'",
  "sources": [
   "https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity"
  ]
 },
 {
  "id": "BLOCK-3",
  "title": "Card D refers to a diagram that does not exist",
  "body": "Card D says 'The diagram shows four services', but the page has no four-service diagram. The only microservice diagram (lines 93-117) shows three services. The learner cannot find the referenced diagram, and the scenario is internally inconsistent.",
  "priority": "P2",
  "confidence": 0.9,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 587,
   "end_line": 587,
   "claim_type": "present"
  },
  "verbatim": "The diagram shows four services.",
  "why_wrong": "The reference is to a nonexistent artifact, so the card is internally inconsistent and confuses a retrieval exercise.",
  "smallest_fix": "Replace with 'A team runs four services.' (or 'Imagine four services').",
  "sources": [
   "none"
  ]
 },
 {
  "id": "BLOCK-4",
  "title": "Key terms used without definition (under-explanation)",
  "body": "'Distributed monolith' is used in Task 1 and Card D, and is defined only in a collapsed solution guide (line 527) after the task that needs it. 'Idempotency' is repeatedly relied on (lines 130, 252, 343, 369, 458, 492) and is never defined. 'Eventual consistency' (290, 492), 'circuit breakers' (280, 343), 'bounded context' (388), 'majestic monolith' (391), 'sagas' and 'outbox tables' (138) are used or name-dropped without explanation. The audience prerequisite is Module 1.3 only. The contract treats a term used before explanation as blocking.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 517,
   "end_line": 517,
   "claim_type": "present"
  },
  "verbatim": "Decide whether the application is a monolith, modular monolith, distributed monolith, or microservice system, and justify",
  "why_wrong": "The outcomes and payment-invariant example depend on these concepts, but a beginner cannot act on them. The page never says which names are taught and which are only signposts.",
  "smallest_fix": "Add a short body definition of 'distributed monolith', one plain sentence each for idempotency (repeating a request has the same effect as doing it once) and eventual consistency, and gloss or drop bounded context and majestic monolith. Either gloss sagas and outbox tables in a clause or mark them as 'names to look up later'.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "BLOCK-5",
  "title": "Filler meta-transitions, process note and stray checkbox (bloat and abrupt transitions)",
  "body": "Meta-lines (81, 134, 149) tell the learner to 'hold', 'write down' or 'list' something before reading on. They add no teaching, and line 81 adds a confusing sentence ('It does not describe what the saturated database did to login'). Line 381 ('The original misconceptions are worth preserving...') leaks editing history. Line 556 puts a stray checkbox after Success Criteria, followed by unrelated cards (558-594) with no task structure. The kubectl-naming paragraph (87) is tangential padding.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 81,
   "end_line": 81,
   "claim_type": "present"
  },
  "verbatim": "Hold the user-facing effect before you read on.",
  "why_wrong": "These are canned transitions and authoring-process text, which the contract counts as bloat and abrupt transitions. The learner loses nothing a stated outcome needs if they are cut.",
  "smallest_fix": "Delete lines 81, 134, 149, 381 and 87's kubectl paragraph. Move the line-556 checkbox into Success Criteria, or drop it, and give the cards a one-line intro as part of the exercise.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB-1",
  "title": "Ingress taught as the gateway mechanism without mentioning Gateway API",
  "body": "The Kubernetes Ingress documentation now notes that the Ingress API is frozen and that the project recommends Gateway API. The page names Ingress and a vague 'dedicated gateway implementation' for a 1.35+ target and never names Gateway API. Task 4 and the solution guide also say Ingress. This is not a blocker: Ingress remains GA with no removal planned.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 292,
   "end_line": 292,
   "claim_type": "present"
  },
  "verbatim": "In Kubernetes, an Ingress controller or a dedicated gateway implementation often plays this role",
  "why_wrong": "The page omits the Kubernetes project's current recommendation, which affects a time-dependent infrastructure fact.",
  "smallest_fix": "Add: 'The Kubernetes project now recommends Gateway API over the frozen Ingress API.' and cite the Ingress page note.",
  "sources": [
   "https://kubernetes.io/docs/concepts/services-networking/ingress/"
  ]
 },
 {
  "id": "NB-2",
  "title": "Cards and scenarios repeat earlier prompts",
  "body": "Card C repeats the startup scenario of the third Pause-and-predict (lines 140 and 472). Card A repeats the first Pause-and-predict (line 72). The image-processing and mTLS scenarios are restated in the callout, decision table, quiz and misconception table. Some spaced retrieval is useful, so this is not blocking.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 578,
   "end_line": 578,
   "claim_type": "present"
  },
  "verbatim": "**Card C: Five services in week one.** Five people split user, billing, catalog, recommendation, and notification into separate deployables.",
  "why_wrong": "It duplicates the lesson-body prompt almost verbatim, adding length without new practice.",
  "smallest_fix": "Replace Cards A and C with distinct scenarios, or cut them.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB-3",
  "title": "Sidecar 'share ... lifecycle' is loose",
  "body": "Containers in a Pod share the network namespace and volumes and are co-scheduled, but they have separate container restarts. The page itself says at line 349 that a sidecar 'can fail independently'. The Pod lifecycle doc exempts native sidecar containers from the Pod-level restartPolicy.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 309,
   "end_line": 309,
   "claim_type": "present"
  },
  "verbatim": "a Pod can contain multiple containers that share networking and lifecycle",
  "why_wrong": "Imprecise and in tension with line 349.",
  "smallest_fix": "Say 'share networking and storage and are scheduled together'.",
  "sources": [
   "https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/"
  ]
 },
 {
  "id": "NB-4",
  "title": "Listed source supports no claim in the text",
  "body": "The Amazon Builders' Library article is listed under Sources, but no sentence in the page uses or attributes anything to it. I did not open it. A sources list should match the page's claims.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 599,
   "end_line": 599,
   "claim_type": "present"
  },
  "verbatim": "- [Amazon Builders' Library - Going faster with continuous delivery](https://aws.amazon.com/builders-library/going-faster-with-continuous-delivery/)",
  "why_wrong": "An orphan citation implies support that the page does not use.",
  "smallest_fix": "Remove it or add the claim it supports.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB-5",
  "title": "Unsupported intensifiers in misconceptions table",
  "body": "'Often a disastrous choice' and 'add immense cognitive and operational load' (line 389) are unsourced rhetoric. The page elsewhere hedges the trade-off, which is the better register.",
  "priority": "P3",
  "confidence": 0.55,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 385,
   "end_line": 385,
   "claim_type": "present"
  },
  "verbatim": "They add massive operational complexity. Often a disastrous choice for startups or small teams searching for product-market fit.",
  "why_wrong": "It overstates the case beyond the sources and the page's own hedged position.",
  "smallest_fix": "Use 'add significant operational complexity, which can outweigh the benefits for small teams still finding product-market fit'.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB-6",
  "title": "Two tasks lack a solution guide, and no tiered hints",
  "body": "Tasks 2 (compare scaling pressure) and 6 (review the decision) have no solution guide, and no task has a tiered hint. A learner who gets stuck on Task 3 (design one service extraction) has only the shallow narrative payment example.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "tests",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 518,
   "end_line": 522,
   "claim_type": "present"
  },
  "verbatim": "- [ ] **Compare scaling pressure**: Identify one workflow that might need more replicas, CPU, queue capacity, or isolation than the rest of the application.",
  "why_wrong": "Feedback is incomplete for part of the exercise.",
  "smallest_fix": "Add a one-line self-check or hint for Tasks 2 and 6.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn15-r2: call 2 of 2, delta review

- reviewed head: `83a9c194459539f2aeff439cddddc00b1959638a`
- run nonce: `d9b4e95e74554c6ca4e3a96e1aecbfce`
- verdict: `incorrect` (confidence 0.7)

### Explanation (verbatim)

Delta review, call 2 of 2, not acceptance. TASK 1: HEAD is 83a9c194459539f2aeff439cddddc00b1959638a. The diff against db9429f8c is one file, +21/-46 (67 changed lines). The page sha256 at HEAD is 014dcfd37f04e5b475aef442416949847e91f93e0e2cde4ac5ace4c74ed0ba3e, which matches. Word count fell from 8366 to 8132 (-234).

BLOCK-1 CLOSED. Line 439 now reads 'consolidating more than 140 services'. The Segment article, opened at the twilio.com URL that segment.com redirects to, says 'consolidate the now over 140 services into a single service', dated July 10, 2018. Line 260's narrative (few services, then many, then consolidation) is consistent with it ('the architecture was simple' at launch).

BLOCK-2 CLOSED. Line 378 now says Shopify's 2019 post describes a large Rails codebase evolved into a modular monolith. I opened the Shopify article: it is dated Feb 21, 2019, says 'one of the largest Ruby on Rails codebases', and says 'evolve Shopify into a modular monolith'. It says nothing about traffic. The unchanged line 81 ('can serve very large businesses') is only loosely supported, since the article speaks of codebase and team size, not traffic. That is non-blocking.

BLOCK-3 CLOSED. The grep for 'diagram shows' finds only line 115, which describes the three-service diagram. Card D (line 563) now says 'A team runs four services' and no longer refers to a diagram.

BLOCK-4 CLOSED. Glosses sit at first use, and I found no earlier use of any of the six terms:
- ACID at line 70, glossed as atomic, consistent, isolated and durable. This is accurate.
- Idempotency at line 128: same effect as performing it once.
- Saga and outbox at line 134.
- Eventual consistency at line 284.
- Bounded context at line 380.
- Circuit breaker at line 274 and distributed monolith at line 119 are also glossed.
Terms not in the ledger (reconciliation, dead-letter, jitter, poison messages, dual-write) remain unglossed. That is non-blocking.

BLOCK-5 PARTLY CLOSED. The canned transitions at old lines 81, 134 and 149 are gone, as are the 'original misconceptions' process note, the stray checkbox and cards A and C (grep for 'next paragraph', 'before you read' and 'original' finds nothing). The two remaining cards are still appended after Success Criteria. See the finding below.

JUDGE-POINTS:
(1) The fixes fit in 67 lines because each gloss is a short inline clause and the deletions were meta-filler and duplicate cards. Every objective is still taught and has aligned practice: compare maps to tasks 1 and 2, design to 3, diagnose Kubernetes mapping to 4, evaluate patterns to 5, and the decision review is task 6. I found no under-explanation and no new padding. The page is still about 8,100 words, and lines 203-219 and 337-351 stay repetitive, so concision improved only modestly.
(2) The glosses are accurate and sit at first use.
(3) Cards: partly consistent. Only Card B and Card D remain, so there is no A or C, which is a dangling reference to removed text. The block is titled 'Task:' but is not in the numbered Tasks list and maps to no Success Criterion. The five Success Criteria map to tasks 1-6 (the 'debugging impact' wording is thin, which predates the PR). Card B restates the network-call prediction at lines 123-128. Card D restates the distributed-monolith definition at lines 119 and 521. Line 119 and line 521 are the same sentence repeated verbatim.
(4) The date-hedged sentence at line 286 is supported. kubernetes.io/docs/concepts/services-networking/ingress/, opened today, says 'The Kubernetes project recommends using Gateway instead of Ingress. The Ingress API has been frozen.' It also says there are no plans to remove Ingress, and the page claims no removal.

NB-1 fixed (Gateway API clause added). NB-2 partly open: cards A and C removed, but B and D still repeat earlier prompts. NB-3 fixed: line 303 now says 'share networking and storage and are scheduled together', which matches the Pod docs ('shared storage and network resources', 'co-located and co-scheduled'). NB-4 fixed: the Amazon source is removed and no claim depended on it. NB-5 fixed: the intensifiers are gone from the misconceptions table. NB-6 mostly fixed: a two-sentence hint now covers tasks 2 and 6, though the hints are not tiered and there is no collapsible solution guide for those two tasks.

DELTA-INTRODUCED CHECKS: A grep for card, frozen, above, earlier, the table and the opening finds no dangling reference except the card lettering. No heading was removed. Every inbound link to this page (indexes, module 1.4, modern-devops, uk mirror) is page-level with no fragment. The added link is the Ingress docs page, which was already in Sources and resolved. No new contradiction. The service mesh sentence ('can build on') is consistent with the quiz and diagrams.

NEW-CLAIM VERIFICATION. URLs I opened:
- kubernetes.io/docs/concepts/services-networking/ingress/
- twilio.com/en-us/blog/developers/best-practices/goodbye-microservices/ (via the segment.com 301)
- shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity
- kubernetes.io/docs/concepts/workloads/pods/
- martinfowler.com/bliki/StranglerFigApplication.html
- martinfowler.com/bliki/BoundedContext.html
- martinfowler.com/articles/microservices.html

Results: Segment, Shopify, Ingress and Pod claims verified as above. The Strangler Fig page supports gradual replacement, so the page's Strangler Fig sentence (line 223) holds. The Fowler microservices article confirms 25 March 2014 and the May 2011 Venice workshop. Fowler's BoundedContext page says Bounded Contexts 'can have a unified model', which supports the page's 'consistent meaning' gloss.

UNKNOWN (not opened): the PostgreSQL transactions PDF, the microservices.io saga and outbox pages, the Microsoft Learn pages, the Istio dataplane page and the extra Fowler articles. The author's quoted excerpts for these are unverified by me. The glosses match standard definitions, so the risk is low.

SCORES (call-1 labels). D1 outcomes 4, D2 accuracy 4, D3 teaching depth 4, D4 examples/practice alignment 4, D5 coherence 3, D6 audience fit 4, D7 concision 4, D8 safety/honesty 5. D total is 32/40, which is 1 below the 33 floor. D5 is the one dimension below its floor of 4, because of the orphaned card labels and the unmapped appended block. Fixing it would give 33, exactly at the floor with no margin. L1 objective 4, L2 steps 4, L3 verification/feedback 4, L4 cleanup 5, L5 safety 5. L total is 22/25, 1 above the 21 floor, with every L at least 4.

BLOCKING: BLOCK-5 remainder only (one P2 finding). NON-BLOCKING: untiered hints for tasks 2 and 6; line 119 duplicating line 521; undefined reconciliation, dead-letter and jitter; line 81 'very large businesses' wording; cards B and D restating earlier prompts.

PROVENANCE: reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family), Claude Code harness, read-only. The author is OpenAI/Codex gpt-6.1-terra, so the reviewer is outside the author's family. CHECKS PERFORMED: git HEAD, diff stat, sha256 and word counts; a full read of the page at HEAD; greps for dangling references, term first-use and inbound links; web fetches of the seven URLs above. SUPPLIED, not independently verified: the PR-body excerpts for the unopened sources, and the author's claim that pipeline tests passed. LIMITS: no cluster, so the optional kubectl command is judged as prose only; no site build or CI was run; the Kubernetes docs pages were truncated after 100000 characters, but the relevant notes sit at the top.

### Findings (verbatim JSON)

```json
[
 {
  "id": "BLOCK-5-residual",
  "title": "Orphaned, unmapped appended cards (B and D with no A/C) remain after Success Criteria",
  "body": "The delta removed Cards A and C and the process-note and checkbox filler, but kept Cards B and D. They are appended after the Success Criteria under a heading that says 'Task:' while the numbered Tasks list has only six tasks, and no Success Criterion maps to them. The labels now read as B and D with no A or C, which is a dangling reference to removed text. Card B restates the network-call prediction (lines 123-128). Card D restates the distributed-monolith definition (lines 119 and 521). This is the 'appended cards' part of call-1 BLOCK-5, only partly fixed.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.5-monolith-to-microservices.md",
   "start_line": 550,
   "end_line": 563,
   "claim_type": "present"
  },
  "verbatim": "### Task: Diagnose failure boundaries",
  "why_wrong": "A learner sees 'Card B' and 'Card D' with no other cards, so the lettering points at text that no longer exists. The block sits outside the numbered Tasks and outside the Success Criteria, so it is neither a graded task nor a mapped practice item. Its content duplicates prompts and reveals already given earlier, which adds padding without a new objective.",
  "smallest_fix": "Either delete the section, since it duplicates the earlier prompts and the classification solution guide. Or relabel the cards 'Card 1' and 'Card 2', add the section to the Tasks list as task 7, and add one matching Success Criterion.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn15-r3: round 3, CTO-granted pinned verification of one blocker and the coherence margin

- reviewed head: `7c3d157c95831a645b8b55056319d2251d88cbd8`
- run nonce: `af7f56a831da4dda84f9371c90edfcc6`
- verdict: `correct` (confidence 0.8)

### Explanation (verbatim)

PASS on the pinned scope. BLOCK-5-residual is closed. The floors are met, but only just: D is exactly 33/40, with no margin above the floor.

TASK 1 (one Bash call, output as returned). HEAD is 7c3d157c95831a645b8b55056319d2251d88cbd8, as required. `git diff --stat` from 83a9c194 to HEAD shows one file changed, 6 insertions and 22 deletions, matching the stated 28 lines. The page sha256 is 2b30041aa5564a8aded090655c6dfd495e4ab2d490a985c64bf705256023d95b, as required. The full diff does three things: it adds a 'Nudge for Tasks 2 and 6' line, wraps the existing scaling and decision-review hint in a details block titled 'More help with Tasks 2 and 6', and deletes the whole 'Task: Diagnose failure boundaries' section with Card B and Card D. The greps give these results:
- `Card` or `card` (case-insensitive): no matches.
- `reveal`: one match, at line 246, in the ordinary sentence 'These rules reveal where transactions...'.
- `Diagnose failure boundaries`: no matches.
- `distributed monolith` (case-insensitive): 3 lines, 119, 509 and 527.

BLOCK-5-residual: CLOSED. I read the whole page. No Card, A or C label remains, and no orphan section follows the Success Criteria; the page now goes straight from Success Criteria to Sources. The five Success Criteria map to the six tasks as follows:
- Criterion 1 (compare trade-offs) maps to Tasks 1 and 2.
- Criterion 2 maps to Task 3.
- Criterion 3 maps to Task 4.
- Criterion 4 maps to Task 5.
- Criterion 5 maps to Task 6.
The help text for Tasks 2 and 6 is real and correct. It tells the learner to compare workload peaks of one workflow with the rest, to name the operating cost of each proposed service, and to name what remains uncertain about each boundary. The nudge line is consistent with it.

Judge-points. Removing the section cost no practice the objectives need. The page keeps four Pause-and-predict blocks, one Stop-and-think, one Which-approach-would-you-choose prompt, seven scenario quizzes and six hands-on tasks. Those cover retrieval and transfer for all four objectives: compare, design, diagnose Kubernetes mapping, and evaluate communication patterns.

Delta-introduced defects: none. The details and summary blocks are well formed, closed and non-empty, and they match the pattern of the neighbouring solution-guide blocks. The new text does not contradict the page. I introduced no new claims.

Scores. D1 outcomes 4, D2 accuracy 4, D3 teaching depth 5, D4 examples and practice alignment 4, D5 coherence 4 (up from 3: the orphan section and its dangling labels are gone), D6 audience fit 4, D7 concision 4, D8 safety and honesty 4. D total is 33/40, which is exactly the floor, so the margin is 0. Every D is at least 4, so that floor has a margin of 0 as well. Lab scores: L1 objective 4, L2 steps 4, L3 verification and feedback 4, L4 cleanup 5 (a design review leaves nothing to clean), L5 safety 5. L total is 22/25, a margin of 1 above 21, and every L is at least 4.

NON-BLOCKING (no findings filed):
- The distributed-monolith sentence still appears verbatim at line 119 as a standalone one-sentence paragraph and again at line 527 in the solution guide. This is mild duplication and the main reason D5 is not higher.
- Success Criterion 1 mentions debugging impact, but no task asks for it explicitly.
- The Task 2 and Task 6 help is a single level, not tiered.
I found no BLOCKING defects.

PROVENANCE: reviewer is the independent cross-family review seat, Anthropic Claude Sonnet 5.5 (model id claude-sonnet-5-5), in Claude Code (Agent SDK harness). The author was OpenAI/Codex gpt-6.1-terra, which is outside this family. REVIEW KIND: pinned verification round, call 3 of 3 under the CTO grant. It is not acceptance and not an exact-head full re-review of BLOCK-1..4, which I treated as closed per the CTO ruling.

CHECKS PERFORMED: one Bash call (HEAD, diff stat, sha256, diff, greps) and a full read of the page at the head. NOT RUN: build or MDX render, link checks, tests. I did not re-verify external sources for BLOCK-1..4.

### Findings (verbatim JSON)

```json
[]
```
