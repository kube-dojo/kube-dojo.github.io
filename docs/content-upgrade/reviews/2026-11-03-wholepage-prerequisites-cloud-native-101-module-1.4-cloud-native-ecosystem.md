# Reviews of prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for all three: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. No cluster lab was run by any reviewer. Call 3 was a CTO-granted pinned verification round limited to the one remaining blocker (three Success Criteria driven by no task) and the score margins.

## kd-wp-cn14-r1: call 1 of 2, whole-page review

- reviewed head: `a4c8c70616675badd76d13e4c7dbcbacd21e9a22`
- run nonce: `5940fb6e0b174ae892cc883287703592`
- verdict: `incorrect` (confidence 0.75)

### Explanation (verbatim)

DISPOSITION: revise (confidence about 0.75). Review kind: whole-page review, call 1 of 2. Provenance: reviewer is Claude Code, model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), run in the Claude Agent SDK harness with the sources MCP and web fetch available. Read-only; I edited, committed and commented on nothing.

DIGEST: `sha256sum` of module-1.4-cloud-native-ecosystem.md gave 93add807ae29565a2d108986d37d313602e9bb98a5393ee721af117eb13ec253, matching the supplied digest. HEAD is a4c8c70616675badd76d13e4c7dbcbacd21e9a22. I read all 577 lines. I also read docs/review-contract.md, docs/content-upgrade/page-completion-plan.md, the page's row and the superseded history in page-reviews.json, docs/content-upgrade/reviews/2026-10-27-orchestration-evidence-p06.md, and the catalog hits (the S012 entry in the 2026-10-31 prerequisites-entry catalog is only the path-level snapshot of this page). Prior dispositions are treated as void history. The prior p06 review was `revise`, with D1-D8 unassessed.

D1-D8 (rubric labels from docs/quality-rubric.md):
- D1 Outcomes 4: four measurable Bloom 3+ outcomes (navigate, match, evaluate, design), all taught and practised.
- D2 Scaffolding 4: layers, then fit, then maturity, then a worked stack, then adoption questions is a sound progression. Some tools appear unintroduced.
- D3 Active learning 4: pause-and-predict prompts, scenario quizzes and a design exercise.
- D4 Real-world 4: the startup versus bank framing and the adoption questions are practitioner-relevant.
- D5 Assessment 4: scenario quizzes align with the outcomes and agree with the lesson. Exercise criteria are weak (finding F6).
- D6 Cognitive load 3: repeated scenarios, canned meta-transitions, a dangling reference and unintroduced tools.
- D7 Engagement 3: the repeated cards and meta-narration ("It is not the count.") read as padding.
- D8 Practitioner depth 4: good rollback, ownership, upgrade and pilot content.
Total 30/40. The 33/40 floor is missed, and D6 and D7 are below 4.

L1-L5 (the exercise is a design review, so the lab rubric applies only partly): L1 objectives 4; L2 verifiable success criteria 3; L3 hints and feedback 3 (no tiered hints; solution guides are partly model answers); L4 environment safety and cleanup 4 (the only command is the optional read-only `kubectl get pods -A`, no cleanup needed); L5 alignment 3 (cards sit orphaned after Success Criteria and are not mapped to a task). Total 17/25. The 21/25 floor is missed, and three dimensions are below 4.

SOURCE STATUS: partly supported. I judged 11 material claims. 8 were supported by sources I opened, 1 was partly supported, 2 stayed unknown or unsupported.
- Supported: Argo CD self-heal is off by default ("By default, changes that are made to the live cluster will not trigger automated sync."). CNCF maturity definitions. Maturity levels for Kubernetes, Helm, Prometheus, Argo, Cilium, Falco and Flux (graduated); Backstage, Thanos and Litmus (incubating); Jaeger, Linkerd, Istio, cert-manager, containerd, CRI-O, Envoy, OPA, Kyverno, Fluentd and OpenTelemetry (graduated). Kubernetes accepted March 10, 2016 and graduated March 6, 2018. Prometheus graduated 2018 as the second project (web search results only; I did not open the announcement page, which 404'd at the guessed URL).
- Partly supported: graduation requires adoption, governance and security evidence. The cited graduation_criteria.md now says criteria moved to the graduation template. I confirmed the substance in the template (3+ adopters, maintainers from 2+ orgs, security review and OpenSSF badge), so the page's cited link no longer carries the claim.
- Unsupported or unknown: the CNCF trail map sequence (F2). "More than one thousand entries" in the landscape: the landscape fetch returned no count, so this is UNKNOWN.
- Not checked: Trivy, Velero, Loki and Tekton project maturity (the CNCF projects page did not list Trivy, Velero or Loki, and Tekton was not checked further). The page does not assert their maturity beyond the Solution guide's "mature" wording.

LAB EXECUTION: not run. No cluster is available. The exercise is a design review; the only command is the optional `kubectl get pods -A`. I judged it as prose only, and nothing is presented as verified.

BLOCKING FINDINGS (each a small fix):
- F1 (line 264): a dangling reference to a "resume-driven development war story from the opening". The opening is explicitly hypothetical (line 29) and never mentions résumé-driven development.
- F2 (line 229, diagram 233-238): an unsourced attribution of a six-step sequence to the CNCF trail map. The official map has ten steps (confirmed by search snippets only; I could not read the map image), so the six numbered steps present a summary as the map. No trail map link is in Sources.
- F3 (lines 85, 157, 166, 291): canned meta-narration that teaches nothing, for example "Count the moments before you read the tool table. The table is a menu of products. It is not the count." This is BLOAT/canned transitions under the plan's step 1.
- F4 (line 304): `| Security scanning | Trivy, Falco |` contradicts the page's own line 161 (Falco is runtime security monitoring) and the quiz/Card B logic that separates scanning from runtime detection.
- F5 (lines 515-549): Cards A-D re-run scenarios already taught or quizzed with near-identical answers. Card A repeats the line 76 prediction and quiz 1. Card B repeats lines 148-155 almost verbatim. Card C repeats lines 282-289 and the Istio quiz. These are retrieval repeats, not transfer, which the contract treats as BLOAT.
- F6 (lines 508 and 511-513): a success criterion that gives no verification method, and the cards are orphaned after the criteria list with no task mapping.

NON-BLOCKING FINDINGS:
- F7 (line 336): a stray `k` alias contradicts the page's own no-alias rule at line 214.
- F8 (lines 300-305, 401, 415, 470, 480): Tempo, Kyverno, Vault and Sealed Secrets are used without introduction, and "mature incubating" is used undefined. CNCF has no such tier.
- F9 (line 41): the landscape size claim is volatile, undated and unverified, and the category list does not match the landscape's actual top-level groupings.
- F10 (lines 214-221): the kubectl alias aside and the two-command block are off-topic filler that teaches no ecosystem outcome. The same `kubectl get pods -A` appears again at lines 318, 462 and 475, where the learner is not told how to recognise ecosystem controllers in the output. This is minor bloat.

OMITTED-CLAIM DISCOVERIES (none were in the supplied catalogs):
- The "Did You Know" claims on Kubernetes 2016 and Prometheus 2018 have no inline source.
- Falco listed as scanning (F4).
- The Vault entry carries no licensing or neutrality note, despite the page's own vendor-neutrality theme. This is optional.
- The "Security should include... runtime detection" answer in the line 148-155 reveal lists five controls for a three-problem scenario. Admission policy is introduced without being triggered by the scenario; I consider this minor.

SAFETY: no unsafe sudo, credential, public-exposure or destructive advice found.

URLS ACTUALLY OPENED: argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/; cncf.io/projects/; cncf.io/projects/kubernetes/; github.com/cncf/toc/.../graduation_criteria.md; raw.githubusercontent.com/cncf/toc/main/.github/ISSUE_TEMPLATE/template-graduation-application.md; landscape.cncf.io (no count shown); github.com/cncf/landscape README (no trail map content); github.com/cncf/trailmap (image only, no steps readable). The cncf.io 2018 Prometheus announcement returned 404. Prometheus and trail-map facts rest on web search snippets, and the exact trail map steps are UNKNOWN.

LIMITS: I did not open the Helm, Kustomize, containerd, Falco, Trivy or Velero docs, so descriptive tool-purpose claims rest on general knowledge and the unremarkable table entries. I did not run anything. If revised, one delta review is expected.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1-dangling-war-story",
  "title": "Reference to a non-existent 'resume-driven development war story from the opening'",
  "body": "BLOCKING. The opening is explicitly labelled hypothetical with no measured incident (lines 29-31) and never mentions résumé-driven development. The Maturity section calls it a 'war story' and uses a term the learner has never met.",
  "priority": "P2",
  "confidence": 0.9,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 264,
   "end_line": 264,
   "claim_type": "present"
  },
  "verbatim": "The resume-driven development war story from the opening is common because new tools feel like progress.",
  "why_wrong": "An undefined term plus a back-reference to content that does not exist. It also presents the deliberately hypothetical scenario as an actual war story, which contradicts the page's honesty framing and is an unexplained transition.",
  "smallest_fix": "Rewrite as: 'Adopting tools because they look like progress (sometimes called résumé-driven development) is common because ...' and drop the 'war story from the opening' reference.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "F2-trailmap-unsourced",
  "title": "Trail map sequence attributed to CNCF without a source; official map has ten steps",
  "body": "BLOCKING. The page attributes a six-step order to 'the CNCF trail map' and the diagram numbers the steps 1-6 with 'Distributed database' as step 6. No trail map link is in Sources. Search snippets say the official map has 10 steps. I could not read the map image to confirm the order, so the claim is unsupported or unknown.",
  "priority": "P2",
  "confidence": 0.6,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 229,
   "end_line": 229,
   "claim_type": "present"
  },
  "verbatim": "The CNCF trail map captures a common learning sequence: containerization, CI/CD, orchestration, observability, service mesh, and cloud native data management.",
  "why_wrong": "A material claim about a named authority is unsourced and is likely a simplified or renumbered version of a ten-step map. Learners could cite it as the official map.",
  "smallest_fix": "Add the cncf/trailmap repository to Sources and either state the diagram is a simplified subset of the map's ten steps or drop the numbering. Cite the map for the sequence or reword it as the author's own summary.",
  "sources": [
   "https://github.com/cncf/trailmap"
  ]
 },
 {
  "id": "F3-canned-meta-transitions",
  "title": "Canned meta-narration transitions add no teaching content",
  "body": "BLOCKING (BLOAT). Four recurring lines tell the learner what not to do with the next element and carry no concept: line 85 ('Name the risk before you read the habit below...'), line 157, line 166 ('The point of the question was the count, not a purchase...') and line 291 ('Name the category shift before you use the table as a shopping list...').",
  "priority": "P2",
  "confidence": 0.8,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 157,
   "end_line": 157,
   "claim_type": "present"
  },
  "verbatim": "Count the moments before you read the tool table. The table is a menu of products. It is not the count.",
  "why_wrong": "Contract BLOAT/canned transitions: padding that tells the learner how to read rather than teaching. Line 166 ('Do not collapse it into the security count you just made') is also confusing.",
  "smallest_fix": "Delete the sentences at lines 85, 157, 166 and 291. Where a bridge is needed, use one content-bearing sentence, for example 'The table below lists tools for each moment.'",
  "sources": [
   "none"
  ]
 },
 {
  "id": "F4-falco-scanning",
  "title": "Quick-reference table lists Falco as 'Security scanning', contradicting the layer table",
  "body": "BLOCKING (internal consistency). Line 161 correctly describes Falco as runtime security monitoring and the page teaches scanning and runtime detection as different moments (lines 150-155, Card B). The decision-aid table then lumps Falco under scanning.",
  "priority": "P2",
  "confidence": 0.9,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 304,
   "end_line": 304,
   "claim_type": "present"
  },
  "verbatim": "| Security scanning | Trivy, Falco |",
  "why_wrong": "It teaches the wrong category and undermines the page's own central point that these are distinct moments.",
  "smallest_fix": "Change to `| Image scanning | Trivy |` and add a separate row `| Runtime security | Falco |`.",
  "sources": [
   "https://falco.org/docs/"
  ]
 },
 {
  "id": "F5-cards-repeat-earlier-scenarios",
  "title": "Cards A-C re-run scenarios already taught and quizzed with near-identical answers",
  "body": "BLOCKING (BLOAT/repetition). Card A repeats the line 76 prediction and quiz 1. Card B repeats lines 148-155 almost word for word (vulnerable image, unexpected outbound connection, expired cert). Card C repeats lines 282-289 and the Istio quiz. The reveals state the same conclusions, so they test recall of the page, not transfer. Card D (restore drill) is a new angle, but its causal wording is circular ('fails because nobody has tested...').",
  "priority": "P2",
  "confidence": 0.7,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 524,
   "end_line": 524,
   "claim_type": "present"
  },
  "verbatim": "**Card B: Trivy is clean. The incident still happened.** CI scanning passed. The running container opened an unexpected outbound connection, and its certificate had already expired.",
  "why_wrong": "Duplicated practice adds length without a new skill. The contract asks for transfer, not repetition, and not one practice item per bullet.",
  "smallest_fix": "Remove Cards A-C (keep their points in the existing predictions and quizzes), or rewrite them as genuinely new scenarios that need the same reasoning applied differently. Keep Card D if its cause wording is fixed.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "F6-unverifiable-success-criterion",
  "title": "Success criterion has no verification method; cards orphaned from tasks",
  "body": "BLOCKING (L2/L5). A criterion requires the learner to verify maturity but the exercise never tells them where (the CNCF projects page) or how to check. The unlabeled checkbox plus four cards after Success Criteria are not mapped to any task or outcome. There are no tiered hints, and the solution guides give a near-complete model answer without a hint ladder.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 508,
   "end_line": 508,
   "claim_type": "present"
  },
  "verbatim": "You verified that at least three selected tools are graduated or mature enough for the fintech scenario.",
  "why_wrong": "The learner cannot complete or self-check the criterion as written, and 'mature enough' is undefined and subjective. The cards at lines 511-513 break the criteria list and are not tied to an outcome.",
  "smallest_fix": "Reword to: 'You checked each chosen tool's maturity level on https://www.cncf.io/projects/ and recorded it.' Add a one-line hint ladder to the exercise (category, then maturity check, then operating cost) before the full solution. Move any retained cards under Tasks with a task label.",
  "sources": [
   "https://www.cncf.io/projects/"
  ]
 },
 {
  "id": "F7-k-alias",
  "title": "Stray `k` alias contradicts the page's own no-alias rule",
  "body": "NON-BLOCKING. The page explains that it spells out `kubectl` and avoids aliases (line 214), then refers to '`k` inspection'.",
  "priority": "P3",
  "confidence": 0.9,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 336,
   "end_line": 336,
   "claim_type": "present"
  },
  "verbatim": "A local cluster lets you practice manifests, controllers, networking assumptions, and `k` inspection without waiting for a shared environment.",
  "why_wrong": "An undefined term in a page that has just said it avoids aliases.",
  "smallest_fix": "Replace '`k` inspection' with '`kubectl` inspection'.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "F8-unintroduced-tools",
  "title": "Tools and a tier name used without introduction",
  "body": "NON-BLOCKING (UNDER-EXPLANATION). Tempo, Kyverno, Vault and Sealed Secrets appear only in the quick-reference table and the solution guides with no explanation of what they are or how they differ from other tools (for example, secrets management is not a taught layer). 'Mature incubating' is used in the Common Mistakes table, quiz 1 and the exercise tasks, but CNCF has no such tier and the page never defines it.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 305,
   "end_line": 305,
   "claim_type": "present"
  },
  "verbatim": "| Secrets management | Vault, Sealed Secrets |",
  "why_wrong": "Terms are used before explanation, so the learner cannot evaluate a tool they were never introduced to. The undefined tier invites exactly the vagueness the page warns against.",
  "smallest_fix": "Add a one-clause gloss for each of these tools where first used, and define 'mature incubating' once (for example, 'an incubating project with broad production use') or replace it with 'graduated or well-established incubating'.",
  "sources": [
   "https://www.cncf.io/projects/"
  ]
 },
 {
  "id": "F9-landscape-count",
  "title": "Landscape size claim is volatile, undated and unverified",
  "body": "NON-BLOCKING. 'More than one thousand entries' (repeated in Did You Know, line 392) has no date or source locator. My fetch of landscape.cncf.io returned no count, so the claim is UNKNOWN. The category list also does not match the landscape's actual top-level groupings.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 41,
   "end_line": 41,
   "claim_type": "present"
  },
  "verbatim": "it contains more than one thousand entries across runtime, provisioning, orchestration, networking, observability, security, storage, database, streaming, and delivery categories",
  "why_wrong": "A volatile statistic without a date, source locator or hedge. The category list is presented as the landscape's structure but is unsourced.",
  "smallest_fix": "Reword to 'contains well over a thousand entries (as of November 2026; check the landscape for the current count)' or drop the number and the category enumeration.",
  "sources": [
   "https://landscape.cncf.io"
  ]
 },
 {
  "id": "F10-kubectl-aside",
  "title": "kubectl alias aside is filler; the kubectl command is never tied to an outcome",
  "body": "NON-BLOCKING (BLOAT, minor). The paragraph spends most of its length on shell-alias policy ('interactive shell, a script, and a training environment'). The two commands that follow are not used to teach any ecosystem outcome. Later, the exercise task asks the learner to run `kubectl get pods -A` and 'record whether any installed ecosystem controllers are already present' without saying which namespaces or names to look for.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 214,
   "end_line": 214,
   "claim_type": "present"
  },
  "verbatim": "Here is the first command habit to keep: this curriculum writes out `kubectl` in copy-paste examples",
  "why_wrong": "Off-topic background in an ecosystem-orientation module. The later exercise gives the learner no way to recognise ecosystem controllers in the command output.",
  "smallest_fix": "Cut the alias discussion to one sentence. In the final task, name the namespaces or pod-name prefixes to look for (for example argocd, cert-manager, cilium, kube-system) and say the expected output depends on the cluster and may show none.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn14-r2: call 2 of 2, delta review

- reviewed head: `e146031c3478bc6c4d6f27dcc06ee0b916cc311c`
- run nonce: `c1e15671964e49e881ab73d0be77a7d7`
- verdict: `incorrect` (confidence 0.7)

### Explanation (verbatim)

TASK 1. HEAD is e146031c3478bc6c4d6f27dcc06ee0b916cc311c. The diff against a4c8c70 touches one file, the module 1.4 page, with 39 added and 78 removed lines. The page sha256 at HEAD is 64f8a92d03bbbf8b478a6c78f2581b0d7a3b8799a10e5723b57f127b64b82ab4, which matches. Word count is 8284 against 8849 before, about 6% smaller. I read the whole page at the pinned head. I could not read the PR body: the gh call with --repo was refused by the review boundary. So the PR-body source table was NOT consulted. I checked the new claims against sources I opened myself.

TASK 2, F1-F6.
- F1 closed. grep for 'war story', 'resume' and 'the opening' returns nothing. The sentence now begins 'New tools can feel like progress before they solve a known problem.'
- F2 closed. The numbering is removed. The line reads 'The following is a lesson summary of possible adoption areas, not the sequence of the [CNCF trail map](https://github.com/cncf/trailmap)'. The trail map and graduation template links are now in Sources. Small blemishes: 'Adapt the order to your needs' sits oddly beside an ordered-looking box stack. 'The following' points at the sentences after it rather than the diagram below. The step-count question is UNKNOWN from my fetches: the README text lists no steps and the PNG could not be read. I only know from memory that the map has ten steps.
- F3 closed. grep for 'Count the moments', 'Name the risk before' and 'Name the category shift' returns nothing, and the check-your-prediction reveals now carry content.
- F4 closed. The table has separate 'Image scanning | Trivy' and 'Runtime security | Falco' rows. This matches the opened Falco docs ('runtime security') and Trivy docs (vulnerability scanner for container images).
- F5 closed on the three judge-points. (1) Removing Cards A-C costs little. The same scenarios are already taught and quizzed (policy engine, Trivy-plus-runtime-plus-certificate, mesh-before-contract). Eight scenario quiz items, four pause-and-predict items and the exercise remain, and these align with the four outcomes. The new 'Review recovery' task is answerable and no longer circular. The scenario is a backup that completes and a restore that fails. The answer is 'the schedule alone did not prove recovery; investigate the failed restore and repeat the drill'. It is thin: it names no concrete things to check. (2) The `~~~` chain renders as stacked boxes with no arrows. It reads as a list of areas, not a sequence, and the sentence is honest. The earlier `Graduated ~~~ Incubating` diagram already used `~~~` before this PR. (3) The maturity check is concrete: the task points to https://www.cncf.io/projects/ and says to record 'not listed' and assess production use separately. Hint 2 repeats this. My fetch of that page listed Velero, Trivy, Loki, Tempo, Vault and Sealed Secrets as not listed. The page shows only graduated and incubating projects, so I cannot say whether they are sandbox. Minor tension: the maturity solution guide says to prefer graduated or incubating projects but then picks unlisted Trivy, Velero, Loki and Grafana.
- F6 closed for the orphaned cards and the missing recovery criterion. The recovery criterion now maps to a task, has an answer and has three ordered hints. The hints are generic rather than escalating, but acceptable.

TASK 3.
- F7 closed. grep finds no stray `k` alias, and `kubectl` is used.
- F8 closed. Tempo, Kyverno, Vault and Sealed Secrets are glossed in the table, and 'mature incubating' became 'well-established incubating'. The new phrase is still informal but defensible.
- F9 closed. The landscape-size claim is removed, along with its Did-You-Know bullet.
- F10 mostly closed. The alias aside is gone and the optional step says to look for argocd, cert-manager and cilium. Small residue: line 208 says 'In later modules, kubectl lets you inspect...' while the exercise asks for it in this module (P3, not blocking).

TASK 4, delta-introduced defects. Delta-introduced defects: none. A grep for 'card', 'frozen', 'earlier' and 'the opening' finds only the intended text. No dangling references. No inbound fragment links into this page: grep for 'cloud-native-ecosystem#' under src finds none. Other pages link to the page without fragments. One blank line splits the last Success Criteria item from the list and the Sources list has a stray blank line (cosmetic). The graduation-requirement sentence in 'Did You Know' is consistent with the opened template.

One alignment gap remains, not introduced by the delta but visible in this full read: Success Criteria items 1, 2 and 4 are not driven by any task. The tasks never ask for a container runtime, for a tracing include-or-defer decision, or for where the security tool acts in the workload lifecycle. That gap is why L5 sits below the lab floor, and it is the blocker below.

TASK 5, sources opened (WebFetch, plus one WebSearch for the Prometheus claim).
- https://github.com/cncf/trailmap: exists and is the CNCF Trail Map; step count not readable.
- https://www.cncf.io/projects/: Kubernetes, Prometheus, Helm, Argo, Flux, Cilium, Falco, cert-manager, Jaeger, OPA, Kyverno, Rook, Fluentd, OpenTelemetry, Linkerd, containerd, CRI-O and Envoy are graduated. Backstage, Thanos, Litmus, Longhorn and Tekton are incubating. This supports the diagram labels for Falco, Cilium, Argo, Backstage, Thanos and Litmus.
- https://grafana.com/docs/tempo/latest/: 'distributed tracing backend'. Confirmed.
- https://kyverno.io/docs/introduction/: 'cloud native policy engine'. Confirmed.
- https://developer.hashicorp.com/vault/docs/about-vault/what-is-vault: centralizes secret management. Confirmed.
- https://github.com/bitnami/sealed-secrets: one-way encrypted Kubernetes Secrets, so the gloss is accurate. No archive notice seen.
- https://github.com/cncf/toc/blob/main/.github/ISSUE_TEMPLATE/template-graduation-application.md: resolves; covers adoption, governance and security evidence. This carries the graduation claim.
- https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/: self-heal is off by default. Confirmed.
- https://trivy.dev/docs and https://falco.org/docs/ resolve.
- Prometheus second graduate, 9 Aug 2018: confirmed via WebSearch result titles and snippets (linuxfoundation.org press release and sdtimes). Kubernetes graduated in March 2018 per one snippet.
- The CNCF announcement URL I guessed returned 404, so that fetch is UNKNOWN. Not every link was opened: I did not open the pages for Cilium, cert-manager, Helm, Kustomize, containerd, CRI-O, Flux, OpenTelemetry, Velero, the CNCF Landscape, Grafana docs, Kubernetes docs, the Prometheus docs, or the Kyverno/Vault/Sealed Secrets pages beyond what is reported above. Added links I did open resolved.

TASK 6, scores (call-1 labels).
D1 outcomes 4. D2 scaffolding 4. D3 active learning 4. D4 real-world 4. D5 assessment 4. D6 cognitive load 4 (the meta-narration is gone, but the page is still about 8.3k words of prose). D7 engagement 4 (up from 3, but still prose-heavy). D8 practitioner depth 4. D total 32/40: the floors are every D >= 4 (met) and total >= 33 (missed by 1). No dimension reaches 5 on an honest read, so I did not inflate.
L1 objectives 4. L2 verifiable success criteria 4. L3 hints and feedback 4. L4 environment safety and cleanup 5 (optional read-only command, no cluster changes). L5 alignment 3 (three criteria with no task). L total 20/25: the floors are every L >= 4 (L5 misses) and total >= 21 (missed by 1).

BLOCKING: success criteria for runtime, tracing and lifecycle placement are unmapped to tasks (finding below). Because of this and the D total shortfall, I cannot call it correct.
NON-BLOCKING: the recovery answer is thin; the generic hints; the trail-map step count and the Falco/Cilium dates are unverified here; the 'In later modules' kubectl line; the cosmetic blank lines.

PROVENANCE: reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic) via Claude Code harness, outside the OpenAI/Codex author family. REVIEW KIND: delta review, call 2 of 2, not acceptance. CHECKS PERFORMED: git diff and stat, sha256, word counts, greps, full page read, and the web fetches listed above. Not run: any build or render of the mermaid diagrams (I judged them from the source only), and no cluster exists. SUPPLIED but unverified: the PR body table (gh refused).

### Findings (verbatim JSON)

```json
[
 {
  "id": "CN14-R2-F1",
  "title": "Success Criteria 1, 2 and 4 map to no task",
  "body": "The exercise Success Criteria require a container runtime selection, a tracing included-or-deferred explanation, and an explanation of where the security tool acts in the workload lifecycle. No task asks for these. The design task lists packaging, deployment workflow, metrics, logs, image scanning, policy, certificates and backup only. The category task asks one problem sentence per category. A learner who does every task still cannot show the three criteria. This was not introduced by the delta, but the delta removed the cards and left these criteria as the only alignment gap.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.4-cloud-native-ecosystem.md",
   "start_line": 501,
   "end_line": 504,
   "claim_type": "present"
  },
  "verbatim": "- [ ] You selected a Container Runtime or documented the managed runtime used by the provider.",
  "why_wrong": "A success criterion that no task requests cannot be verified as completed. This lowers lab alignment (L5) below the floor.",
  "smallest_fix": "Add 'container runtime (or the managed runtime)' and 'tracing included or deferred' to the 'Design a minimal first production stack' task, and 'where it acts in the workload lifecycle' to the security sentence in the category-matching task. Or delete the three unmapped criteria.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn14-r3: round 3, CTO-granted pinned verification of one blocker and the score margins

- reviewed head: `cb61e7519737754251d6166efe4971973a6d373d`
- run nonce: `9d6d1ee0c02245e8ada2d13140280120`
- verdict: `correct` (confidence 0.78)

### Explanation (verbatim)

TASK 1. HEAD is cb61e7519737754251d6166efe4971973a6d373d. The delta from e146031c3 is one file, module-1.4-cloud-native-ecosystem.md, with 10 insertions and 12 deletions. The page sha256 is 30b1de3259883fc72090735aa32be4020cb9bebb5e8460b535337b1567a0940e, which matches the required value. Word count goes from 8284 to 8397 (+113). I read the whole delta and the exercise, hints, solution guides and Success Criteria sections in full. I read the rest of the page via grep and spot reads. TASK 2, CN14-R2-F1 (previously unmapped criteria 1, 2 and 4) is CLOSED. (a) Criterion 1, 'You selected a Container Runtime or documented the managed runtime used by the provider.' The stack task now says 'Include the container runtime (or the managed runtime), packaging, deployment workflow…'. The minimal-stack guide says 'Use the managed node runtime, such as containerd, and document which runtime the provider supplies.' (b) Criterion 2, 'explained whether tracing is included or deferred.' The stack task now says 'State whether tracing is included or deferred, with the reason.' The minimal-stack guide says 'Defer tracing until request paths cross enough services to justify it.' (c) Criterion 4, 'explained where it acts in the workload lifecycle.' The category task now says 'For security, explain where the tool acts in the workload lifecycle (build, admission, or runtime).' The category guide says 'Security should include image scanning, admission policy, runtime detection…' and 'Trivy scans the image during the build workflow before it reaches the registry.' The other criteria stay mapped. Criterion 3 (GitOps/CI-CD, how desired state reaches the cluster) maps to the stack task's 'deployment workflow' and the CI/CD category sentence; the guide says 'code becomes desired cluster state'. Criterion 5 (storage backup or restore) maps to 'backup or restore planning', the Storage category task and the guide. Criterion 6 (CNCF maturity recorded, or noted as not listed) maps to the Navigate task and the maturity guide. Criterion 7 (one-sentence justifications) maps to the category task, the evaluate task and the guide's 'reasoning should explain maturity and operations risk'. Criterion 8 (recovery gap and next action) maps to the Review recovery task and its answer. I found no new unmapped or contradictory item. Criterion 4 asks about a security 'or policy enforcement tool', and the guide gives only the Trivy build example plus the list of admission and runtime categories; that is answerable, though it is the thinnest of the three. TASK 3, non-blocking points. (1) Recovery answer: CLOSED. It now names the scratch namespace, snapshot class and driver, and restore permissions, then says to repeat the drill and record the result. (2) Hints: CLOSED. They are now escalating questions (which category, what to check for production or recovery readiness, what upgrade, monitoring and recovery work it costs). They are sensible for a beginner. Hint 2 is somewhat abstract but acceptable. (3) Maturity guide: CLOSED. It adds 'Tools not listed on the CNCF projects page need separate production-use and support evidence', which resolves the Trivy, Velero, Loki and Grafana inconsistency. (4) kubectl sentence: CLOSED. It now says 'in the optional exercise below and in later modules', which is consistent with the optional task. (5) Stray blank lines: CLOSED, both removed. Source checks. I opened https://kubernetes.io/docs/setup/production-environment/container-runtimes/. It says a runtime must be installed on each node and lists containerd and CRI-O among the CRI runtimes. That supports the runtime sentence; it said nothing on managed services, so 'such as containerd' is supported only by the page's own line 261. I opened https://trivy.dev/latest/docs/target/container_image/. It confirms container-image vulnerability scanning and that Trivy can scan local images and registries. I opened https://github.com/aquasecurity/trivy, whose README lists a GitHub Actions integration. The specific claim 'during the build workflow before it reaches the registry' is not stated verbatim on any page I could open (two trivy.dev CI URLs returned 404). It is a reasonable illustration, and the page already makes the same statement at lines 265 and 430. I did not treat that as a defect. TASK 4, delta-introduced defects: none blocking. Minor: the tracing sentence in the minimal-stack guide partly duplicates the deferral guide, a small redundancy. There is no contradiction, no dangling reference, and no new unsupported tool claim (Trivy and containerd were already on the page). The +113 words are proportionate. TASK 5, scores from the full read. D1 outcomes 5 (objectives, tasks and criteria now line up). D2 scaffolding 4. D3 active learning 4. D4 real-world 4. D5 assessment 5 (every criterion is task-driven and answerable from a guide, and the recovery answer is concrete). D6 cognitive load 4. D7 engagement 4. D8 practitioner depth 4. D total is 34/40, with every D >= 4 and a margin of +1 over the 33 floor. The 5s on D1 and D5 rest on the CN14-R2-F1 closure. D2, D3, D6 and D7 stay at 4 because the page is long (about 8.4k words) and the hands-on part is a design review, not a lab; these are not defects a small change would fix. L1 objectives 4. L2 verifiable success criteria 4 (self-assessment 'you did X' statements, but each is checkable against a guide). L3 hints and feedback 4. L4 environment safety and cleanup 5 (the only cluster command is optional and read-only). L5 alignment 4 (fixed). L total is 21/25, every L >= 4, exactly at the 21 floor (margin 0). BLOCKING: none. NON-BLOCKING: the Trivy build-stage statement is not verbatim in the docs I could open; the criterion 4 guide example covers only Trivy. Provenance: reviewer is Claude (Anthropic family, outside the OpenAI/Codex author family), model claude-sonnet-5-5, run in the Claude Code harness with tool access. Review kind: pinned verification round 3, not an acceptance or merge approval. Checks I ran myself: git HEAD, diff stat, sha256, word counts, the full diff, section reads, grep mapping, and the four fetches above (two returned 404). Supplied but not independently verified: the call-1 and call-2 history. No cluster was available, so the optional kubectl task was judged as prose only. Limits: the Kubernetes docs fetch truncated the last 8.8k characters, and I did not render the page in a browser.

### Findings (verbatim JSON)

```json
[]
```
