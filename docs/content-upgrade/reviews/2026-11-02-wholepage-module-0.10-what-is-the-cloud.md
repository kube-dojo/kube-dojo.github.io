# Reviews of prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The lab was not run by either reviewer.

## kd-wp-10-r1: call 1 of 2, whole-page review

- reviewed head: `f6519ce9435e487921480f37e92f538d2f891438`
- run nonce: `280b9904c5b748c4ae4bb9cd2c251b33`
- verdict: `incorrect` (confidence 0.68)

### Explanation (verbatim)

DISPOSITION: revise (whole-page review, call 1 of 2). Two small BLOCKING findings. The D floors are not met. The lab floors are met on my reading.

DIGEST: sha256sum of src/content/docs/prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md = 0082e52179a6b8213d38848202cdfedf5a0a15a9a01c1fb568a3098d30837ca7. This matches the digest supplied. git HEAD = f6519ce9435e487921480f37e92f538d2f891438. The page is 529 lines (7,661 words) and I read all of it. Its last content commit is 88d7fba96.

SCORES. docs/review-contract.md does not define the D and L labels. I used the D1-D8 names from docs/quality-rubric.md (line 312). The L labels are my own reading.
- D1 Outcomes: 4. Four clear outcomes (explain, compare, map, diagnose). The 'diagnose why Kubernetes is useful' outcome is practised only by quiz item 5.
- D2 Scaffolding: 4. The kitchen and hotel analogies, the build-versus-rent walkthrough and the service-to-computer-part mapping build up in order. Module 0.1 (a listed prerequisite) defines node, cluster and container.
- D3 Active learning: 4. There are four predict/reveal blocks. The reveals are specific and cite sources.
- D4 Real-world: 4. The cost arithmetic is labelled fictional and checks out ($7.20, $1.76, $2.00). The dialogues are labelled synthetic. The shared-responsibility, cleanup and retained-charge material is practical.
- D5 Assessment: 3. The unguided classification checkpoint has no answers or hints. Its 'revisit after the quiz' instruction points at a quiz that does not contain those items. See BLOCKING 1.
- D6 Cognitive load / concision: 3. The same advice recurs across sections. See BLOCKING 2.
- D7 Engagement: 4. The scenarios are concrete and the tone is plain.
- D8 Practitioner depth: 4. Shared responsibility, retained resources after a stop, sticky versus reversible choices, and tags and budgets are all covered.
- D total: 30/40. All-at-least-4 is NOT met (D5 and D6 are 3). The total of 33 is NOT met. FLOORS NOT MET.
- L1 Objective clarity: 4. The reading-the-docs-critically goal is clear.
- L2 Executability: 4. The command block is a connected && chain that ends in nano and then cat. It is clear and safe.
- L3 Verification: 4. The file is verified with cat and a five-item checklist.
- L4 Safety / cleanup: 5. No account or payment details are entered, a fresh unused directory is used, and the page says to exit without saving if contents look unexpected. The directory is not removed afterwards, which is harmless.
- L5 Alignment: 4. It supports the compute/storage mapping and the time-sensitivity lesson. See NON-BLOCKING B and C.
- L total: 21/25. Floors met, with no margin.

SOURCE STATUS: supported (the claims I judged), with a few unverified. I judged 14 material claims. 11 are supported by sources I opened. 3 are UNKNOWN. 0 are contradicted.
- Supported by pages I opened:
  - Stopped EC2 instance: EBS volumes persist and are charged, and associated Elastic IPs are charged (AWS how-ec2-instance-stop-start-works page, 'Costs related to instance stop and start'). This supports the reveal at line 83.
  - NIST SP 800-145: September 2011, five essential characteristics and four deployment models (csrc.nist.gov final page). A private cloud 'may exist on or off premises' (csrc.nist.gov glossary quoting SP 800-145). This supports lines 41 and 373.
  - Kubernetes name from Greek (helmsman or pilot) and the K8s eight-letter abbreviation (kubernetes.io/docs/concepts/overview). Google open-sourced it in 2014 and it draws on Google's experience.
  - CNCF journey report: 'Initially created by Google engineers in 2014' and CNCF's first hosted project in March 2016. 'Vendor-neutral' is CNCF's self-description and is not stated in that report.
  - AWS shared responsibility: customer responsibilities vary by the services used (AWS risk-and-compliance whitepaper).
  - AWS overview: over 200 services, pay-as-you-go, servers in minutes, and AWS began offering services in 2006 (AWS overview whitepaper, dated 2026-06-02).
  - EC2 on-demand pricing is billed per hour or second with no long-term commitment.
  - Free-tier structure: GCP separates a $300/90-day trial credit from Free Tier monthly limits, with e2-micro and Cloud Storage restricted to US regions. Azure separates a $200 credit, 12-month services and always-free services. AWS has Free/Paid plans, credits and always-free services. The lab's hedging fits all three.
- UNKNOWN (not opened or fetch failed):
  - The NIST PDF itself rendered as binary, so I relied on the csrc pages.
  - The AWS billing-free-tier docs page returned only a title, so I relied on aws.amazon.com/free instead.
  - The per-provider service-doc links for EC2, S3, VPC, RDS, Azure VM, Blob, VNet and SQL Database, GCE, Cloud Storage and Cloud SQL (lines 507-511), the Kubernetes v1.35 Deployments page, and the Azure and Google shared-responsibility pages were not opened. The service-name mappings are standard and low risk.
  - 'Kubernetes v1.35 is the exam-pinned target' (line 375) is checked only against repo docs/changelog-history.md ('exam pin stays 1.35 until LF moves'), not against Linux Foundation pages. It is hedged by 'check the version on a real cluster'.
  - 'Linode under Akamai' (line 139) is unsourced but low risk.
  Volatile figures: no prices, quotas or free-tier terms are asserted as fact. The lab sends the learner to the live pages.

LAB EXECUTION: not run. The lab is a documentation-reading exercise plus one local mkdir/ls/nano/cat chain. No cloud account is needed and none was created. I did not run the shell chain and nothing I saw shows the author running it. It is judged as prose and design. The command chain looks correct as written.

BLOCKING FINDINGS (each fits a small PR):
1. Lines 222-229, UNDER-EXPLANATION / no practice feedback. The classification checkpoint says 'This diagnostic has no answer key on purpose... revisit them after the quiz'. The quiz (lines 391-425) contains none of the four items and none of the Monday-outage sequence, so the revisit has nothing to check against. 'Your notes file' is also not defined yet, because the lab creates cloud-notes.txt later. Item 3 ('permission denied even for users who typed the correct password') is ambiguous and a beginner cannot self-check it. Fix: add one collapsed answer reveal with the category and a one-line why for items 1-4 and an example sequence for the outage story, and drop the 'after the quiz' wording.
2. Lines 249-255, 355 and 361 (plus the Common Mistakes table), BLOAT. The same cost/cleanup/ownership advice is restated several times without new content: the 'tags, budgets, alerts, cleanup, ownership' list at 249, 253, 355, 361 and the table rows; 'ask what should happen when nobody is using a resource' at 255 and 361. On-prem versus cloud fit is restated at 59-61, 351 and 365, and the provider-neutral advice at 139-143 and 367. Line 129 refers to 'cloud diagrams' that never appear. Fix: keep the cost-discipline explanation in one place (253-255), reduce 249, 355 and 361 to a single clause or cross-reference, merge or trim the repeated paragraph in 'When You'd Use This vs Alternatives', and drop the line 129 diagrams paragraph. Nothing a stated outcome needs is lost.

NON-BLOCKING FINDINGS:
A. Lines 43 vs 306: 'control plane' is introduced as the cloud provider's API layer and then reused for the Kubernetes control plane without saying they are different. Add one sentence at 306. Module 0.1 already uses 'Kubernetes control plane'.
B. Line 479: the Azure FAQ (as I read it) lists no Blob Storage allowance, yet the template says to record it. Add 'or write not listed on this page'. Success criterion 3 (map a provider service name to a category) has no matching step or note field.
C. Minor flow: line 39 mentions 'the kitchen analogy' before it is laid out at line 45. Line 88 ('A personal website may need only a small server...') is a non-sequitur. Line 74 uses 'VM' before it is defined at line 162. The roadmap tree (312-347) is navigation, not teaching.

OMITTED-CLAIM DISCOVERY: no material unledgered factual claim is unsupported. The citation seed (docs/citation-seeds/...0.10...json, run 2026-04-20) describes an OLD page (it ledgers the $50K, 2012 game and $85,000 anecdotes, which no longer exist on this page). It is stale and I did not rely on it. The current page's claims are instead covered by the Sources list. The unledgered items are: the NIST detail on private clouds, the 'Kubernetes v1.35 exam-pinned' statement, 'Linode under Akamai', and 'vendor-neutral'.

PROVENANCE: reviewer is Claude Code (Claude Agent SDK harness), actual model Claude Sonnet 5.5 (claude-sonnet-5-5), Anthropic family. The page's recent author is OpenAI/Codex (gpt-6.1-terra), so the reviewer is outside the author family. Review kind: whole-page review, call 1 of 2.

CHECKS PERFORMED BY ME: sha256 and HEAD check; full read of lines 1-529; review-contract and page-completion-plan; the citation seed; page-reviews.json and source-catalog rows for this module (frontmatter-only capture, no claim support); the sibling 0.9 review for format; module 0.1 grep for node/cluster/container/control-plane definitions.
URLS OPENED: AWS EC2 stop/start page; csrc.nist.gov SP 800-145 final page; csrc.nist.gov glossary 'private cloud' page; kubernetes.io/docs/concepts/overview; CNCF Kubernetes project journey report; AWS shared responsibility whitepaper page; AWS overview whitepaper; AWS EC2 on-demand pricing page; aws.amazon.com/free; docs.cloud.google.com/free/docs/free-cloud-features; Azure free-account FAQ.
SUPPLIED, NOT RE-VERIFIED: earlier review dispositions and old page-reviews history, which I treated as void.
LIMITS: the NIST PDF was unreadable; the AWS billing docs page returned only a title; I did not open the per-service doc links or run any command. Confidence is moderate (0.68) because blocking 2 is a judgement on repetition.

### Findings (verbatim JSON)

```json
[
 {
  "id": "WP10-B1",
  "title": "Classification checkpoint has no feedback and points to a quiz that does not cover it",
  "body": "The unguided classification checkpoint (four workloads plus a Monday-outage sequence) is the page's main practice for the 'map services to categories' outcome. It provides no answers, hints or rationale. It tells the learner to revisit their answers after the quiz, but the quiz (lines 391-425) contains none of these items. Item 3 is genuinely ambiguous for a beginner (an identity/permission problem versus an application or database problem). The 'notes file' it refers to is not created until the lab at line 454.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "tests",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md",
   "start_line": 222,
   "end_line": 222,
   "claim_type": "present"
  },
  "verbatim": "This diagnostic has no answer key on purpose. Write your answers in your notes file, then revisit them after the quiz to see how your reasoning held up.",
  "why_wrong": "Practice needs aligned tasks with feedback. A beginner cannot check their reasoning, and the instruction to revisit after the quiz is vacuous because the quiz does not cover these items. This is under-explanation in the assessment.",
  "smallest_fix": "Add one collapsed <details> answer reveal after the checkpoint. Give the category and a one-line why for items 1-4 (storage, compute, identity, identity) and an example outage sequence (networking, compute, storage, identity, observability). Remove the 'after the quiz' and 'notes file' wording, or say to use any scratch note.",
  "sources": [
   "docs/review-contract.md"
  ]
 },
 {
  "id": "WP10-B2",
  "title": "Cost, cleanup and tradeoff advice repeated across many sections",
  "body": "The cost-discipline list (tags, budgets, alerts, cleanup, ownership) and the 'ask who owns it / what happens when nobody is using it' habit are restated at lines 76, 249, 253, 255, 355 and 361 and again in the Common Mistakes table. The on-prem versus cloud fit appears at 59-61, 351 and 365. Provider-neutral advice appears at 139-143 and 367. Line 129 describes 'cloud diagrams' that never appear on the page. A learner gains no new mechanism from the repeats.",
  "priority": "P2",
  "confidence": 0.6,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md",
   "start_line": 361,
   "end_line": 361,
   "claim_type": "present"
  },
  "verbatim": "The beginner version of this habit is simple: every time you create a resource, ask who owns it, what it costs, what data it touches, and how it will be deleted.",
  "why_wrong": "This is BLOAT under docs/review-contract.md (repetition and duplication across sections). It restates lines 255 and 253 and the tags/budgets/alerts list at 249 and 355. It raises cognitive load on a long beginner page.",
  "smallest_fix": "Keep the cost/cleanup explanation once, in the pay-as-you-go section (253-255). Reduce 249, 355 and 361 to one clause or a cross-reference. Merge or trim the repeated on-prem and provider-neutral paragraphs in 'When You'd Use This vs Alternatives'. Drop the line 129 diagrams paragraph.",
  "sources": [
   "docs/review-contract.md"
  ]
 },
 {
  "id": "WP10-N1",
  "title": "'Control plane' used for two different things without distinction",
  "body": "'Control plane' is introduced at line 43 as the cloud provider's API layer for infrastructure. Line 306 then uses 'the Kubernetes control plane' (and quiz item 5 uses 'the control plane') without saying these are different systems. Module 0.1 already uses 'Kubernetes control plane'.",
  "priority": "P3",
  "confidence": 0.55,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md",
   "start_line": 306,
   "end_line": 306,
   "claim_type": "present"
  },
  "verbatim": "Providers can operate parts of the Kubernetes control plane for you",
  "why_wrong": "A beginner may conflate the provider's infrastructure API with Kubernetes' own scheduling and reconciling component.",
  "smallest_fix": "Add one sentence at line 306: the Kubernetes control plane is the cluster's own management software, which is separate from the cloud provider's infrastructure control plane described earlier.",
  "sources": [
   "https://kubernetes.io/docs/concepts/overview/"
  ]
 },
 {
  "id": "WP10-N2",
  "title": "Lab asks for a Blob Storage allowance the linked Azure FAQ does not list",
  "body": "Step 3's template says to record the Blob Storage allowance. The Azure Free Account FAQ, as I read it, lists no Blob Storage allowance (it lists the credit, 12-month services and always-free services, and VMs). Success criterion 3 (map a provider service name to a category) has no step or note field.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md",
   "start_line": 479,
   "end_line": 479,
   "claim_type": "present"
  },
  "verbatim": "- Storage: record the current Blob Storage allowance and whether it comes from credit, a limited-time offer, or an always-free limit",
  "why_wrong": "A learner may not be able to fill this field from the page they were sent to. That is confusing for a beginner, although the page says confusion is useful information.",
  "smallest_fix": "Add 'or write: not listed on this page'. Add one note line to the template: 'Service name mapped: <name> -> compute/storage/networking/database'.",
  "sources": [
   "https://azure.microsoft.com/en-us/free/free-account-faq/"
  ]
 }
]
```

## kd-wp-10-r2: call 2 of 2, delta review

- reviewed head: `24000b4e4a9d143e0bf778a781580c19748db562`
- run nonce: `fde66dad7cc84c2f98b5b59eca64047f`
- verdict: `correct` (confidence 0.8)

### Explanation (verbatim)

DELTA REVIEW, call 2 of 2, not acceptance. Task 1: HEAD is 24000b4e4a9d143e0bf778a781580c19748db562; the diff against f6519ce9 touches one file (the module-0.10 page); the page sha256 is f3165aa4b56f54cb8a0452b8533af86235dbde453f2e82f5a7f2f98db1cf0b25, which matches. The diff has no heading changes, so no anchor was removed. Pages that link to the page (0.9, 0.11, the track and prerequisites indexes, the uk mirrors) use page-level links only, so they still resolve.

B1 CLOSED. The collapsed reveal gives storage, compute, identity and identity, each with a one-line reason. Item 3's hedge (authorization first; application or database faults may also need investigation) is accurate and enough for a beginner. The example sequence (networking, compute, storage, identity, observability) follows the five prompts in the preceding paragraph in order and fits "move from what users observe toward the layer where the evidence lives". It closes by saying the evidence may send you back to an earlier layer. Grep results: "quiz" appears only in the "## Quiz" heading; "answer key" and "notes file" appear nowhere; "scratch note" appears once, at the checkpoint. The lab's cloud-notes.txt is unrelated and consistent. Nit: the heading still says "(unguided)" although a reveal now follows.

B2 CLOSED. The repeated cost/cleanup lists are trimmed, and no safety point is lost entirely. Tags, budgets, alerts and cleanup reviews still appear at line 262. "What should happen when nobody is using a resource" and the cleanup-rule-before-creation point are at line 264. The EBS and Elastic IP billing caveat is at lines 83 and 256. The Common Mistakes table is still consistent: the scaling row keeps tags, budgets, alerts and cleanup. The cross-references resolve: "described above" at line 370 points to lines 262-264, and "described earlier" at line 315 points to the control-plane text at lines 43 and 108. The "cloud diagrams" paragraph is gone, and grep for "diagram" in the page finds nothing. The shortened Benchmark scenario still carries the forgotten-environment lesson, because line 264 keeps the cleanup rule. On-prem fit is stated in full at lines 59-61 and 360. Provider choice by service category is at lines 131, 137 and 141. One minor gap remains, in the finding below: "hybrid" is now only named, at line 374, with no explanation anywhere. It is not blocking, because the outcomes do not require hybrid.

N1 fixed: the sentence at line 315 separates the Kubernetes control plane from the provider's infrastructure control plane and reads correctly in the managed-Kubernetes paragraph. N2 fixed: the Azure Free Account FAQ does not list Blob Storage, so "not listed on this page" is accurate, and the "Service name mapped" note line gives success criterion 3 a step. Small edits: VM is spelled out at line 74, its first use. The kitchen-analogy mention is removed from line 39, and the analogy is now laid out at line 45 before it is used. The personal-website sentence is gone. Left unchanged and non-blocking: the repo-only claim that v1.35 is the exam-pinned target, "Linode under Akamai", "vendor-neutral", and the roadmap tree. This delta added no price, quota or free-tier term; the page's figures are still labelled hypothetical or hedged.

URLs opened: the Azure free-account FAQ (it lists Always and 12-month items such as SQL Database, Cosmos DB and Cloud Shell storage, and no Blob Storage); the AWS EC2 stop/start page (it confirms EBS storage charges continue while stopped, and Elastic IP charges apply while stopped); and csrc.nist.gov SP 800-145 (it confirms September 2011 publication). The csrc.nist.gov page summary did not name the characteristics or the on-or-off-premises private cloud, so those two claims are UNKNOWN from this fetch. Both predate the delta, and the PDF was not opened. The AWS shared-responsibility page was not opened, and the delta did not touch that text.

Scores, with the call-1 labels. D: D1 outcomes 4, D2 scaffolding 4, D3 active learning 5, D4 real-world connection 4, D5 assessment 4 (was 3; the reveal fixes the call-1 gap), D6 cognitive load/concision 4 (was 3; the repeats are trimmed, though the page is still long), D7 engagement 4, D8 practitioner depth 4. D total 33/40, so the floor of 33 is met by a single point and every D is at least 4. L: L1 objective clarity 4, L2 executability 4, L3 verification 4, L4 safety/cleanup 5, L5 alignment 4. L total 21/25, with every L at least 4. The lab is not run and is judged as prose and design only.

BLOCKING: none. NON-BLOCKING: the hybrid-undefined point (P3); the "(unguided)" heading nit; and the unchanged unverified or unledgered claims (v1.35, Akamai, CNCF self-description, stale citation seed).

Provenance: reviewer is Claude Code, Anthropic family, model claude-sonnet-5-5, harness Claude Agent SDK with Sources MCP and web fetch; the author is OpenAI/Codex, which is outside the reviewer's family. Checks I did myself: HEAD and sha256, the full diff, a read of the whole page, the greps above, repo link checks, and three source fetches. Limits: no command was executed and no cloud account was used; the NIST PDF and the AWS shared-responsibility page were not opened; the Ukrainian mirror was not reviewed.

### Findings (verbatim JSON)

```json
[
 {
  "id": "WP10-R2-N1",
  "title": "\"Hybrid\" is named but never explained after the merge",
  "body": "The merged paragraph in \"When You'd Use This vs Alternatives\" says on-premises and hybrid models fit different workloads and points at \"the earlier tradeoffs\". The earlier text covers cloud versus on-premises only. Hybrid was explained only in the removed paragraph, so the term is now undefined and the section gives no concrete guidance. Non-blocking: the outcomes do not require hybrid, and on-prem fit is still stated at lines 59-61 and 360.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud.md",
   "start_line": 374,
   "end_line": 374,
   "claim_type": "present"
  },
  "verbatim": "As the earlier tradeoffs show, cloud, on-premises, and hybrid models fit different workloads.",
  "why_wrong": "The earlier tradeoffs never discuss hybrid, so the cross-reference overstates what the page already taught and leaves a beginner with an undefined term.",
  "smallest_fix": "Add one clause defining hybrid, for example keeping some systems on premises while using cloud capacity for burst or development work, or drop \"and hybrid\".",
  "sources": [
   "none"
  ]
 }
]
```
