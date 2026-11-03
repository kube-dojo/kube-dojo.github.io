# Reviews of prerequisites/cloud-native-101/index.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The page is a navigation hub without a lab of its own. Call 1 returned a correct/retain verdict with three non-blocking findings; the fix and call 2 were made to give the page margin and close a learner-facing gap.

## kd-wp-cnidx-r1: call 1 of 2, whole-page review

- reviewed head: `0de5fb71917600d084a1c7059f01ab9ba01a59f2`
- run nonce: `f04d41c462e94a1a88a280afc572b4df`
- verdict: `correct` (confidence 0.72)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/cloud-native-101/index.md = b6f17e8296475ca8a49ebe891751f727be60e297753f9fe47b5abf60050f7051, matching the supplied digest; HEAD = 0de5fb71917600d084a1c7059f01ab9ba01a59f2 (git rev-parse). The page is 23 lines. PAGE KIND: navigation hub (intro, three paragraphs, five-row module table, one time-estimate note). Per docs/review-contract.md hubs may omit theory/quizzes/labs but need audience/route/link checks, so L1-L5 are not applicable; lab_execution = not applicable (the hub has no exercise; the modules' labs were not reviewed or run here, and no container runtime or cluster exists on the host). D1-D8 (module rubric applied proportionately to a hub): D1 outcome clarity 4 (the stated purpose is a mental model of containers, Docker, orchestration, CNCF and architecture trade-offs, and each row says what its module covers); D2 content accuracy 4 (the five titles, links and times match the module files; see checks below); D3 teaching depth/mechanisms 4 (not applicable beyond routing; the hub does not claim to teach); D4 examples/practice alignment 4 (not applicable to a hub; the modules carry practice); D5 coherence/sequence 4 (order 1.1-1.5 matches sidebar order 2-6 and the module Next Module sections, but see NB1 on the 1.3 setup dependency); D6 audience fit/prerequisites 4 (opening block names sysadmin and developer audiences and states the trade-off framing; no explicit starting-skill statement, see NB1); D7 concision/no bloat 4 (23 lines; paragraph 2 has mild marketing filler, see NB3, not material); D8 safety/honesty 5 (opening paragraph hedges against over-adoption; time note states the numbers are planning estimates, not measured). Total 33/40, with the two lowest items at 4 and none below 4, so the floors (all >=4, total >=33) are met. DISPOSITION: retain, confidence 0.72. SOURCE_STATUS: supported for 12 internal/structural claims checked (5 module titles vs frontmatter, 5 link targets existing, 5 times vs module headers, aggregate arithmetic); partly supported for 2 external-facing claims that I did not check against an external source (Docker 'popularized containerization'; Kubernetes 'became the industry standard'). Verified claims: the five link targets exist as files (module-1.1-what-are-containers.md through module-1.5-monolith-to-microservices.md); module header times are 80-110, 90-120, 90-120, 100-130 and 90-120 minutes, which match the table; sums are 80+90+90+100+90 = 450 and 110+120+120+130+120 = 600, i.e. 450-600 minutes = 7 h 30 min to 10 h, which matches line 23; the module count of five matches the parent prerequisites/index.md; the module order matches the order in which module prerequisites chain. BLOCKING FINDINGS: none. NON-BLOCKING FINDINGS: NB1 (lines 13-21 and 11) the hub presents a linear 1.1-1.5 path but never says what a learner needs to start (a working terminal, a machine that can install Docker for 1.2, per module 1.1's Prerequisites line and module 1.2's Installing Docker section) nor that module 1.3's hands-on Setup sends the learner to Kubernetes Basics 1.1 (a section that follows this one on the suggested route) to install kubectl and a disposable cluster; and it gives no next-step link to Kubernetes Basics even though the Zero to Terminal hub names the route 'Cloud Native 101 then Kubernetes Basics'. Smallest fix: one sentence under the module table stating the entry skills and environment, that 1.3's exercise uses a cluster from Kubernetes Basics 1.1, and a link to the next section. NB2 (line 19) '...why Kubernetes became the industry standard.' is an unsourced and unhedged market claim; it sits slightly against the hub's own opening hedge (line 7) and against module 1.3, which says only that Kubernetes 'became the common answer'. Smallest fix: align to the module wording, e.g. 'why Kubernetes became a common answer for orchestration'. NB3 (line 9) 'demystify the core concepts' and 'the infrastructure and architecture patterns that power modern technology companies' are promotional filler that teaches nothing; cut or tighten. Also line 11 'Docker, the tool that popularized containerization' is a widely accepted historical statement (module 1.3 line 349 repeats it as 'popularized the developer workflow'); I treated it as acceptable and unverified externally. OMITTED-CLAIM DISCOVERY: the page contains no versions, prices, quotas or service names. The only material external-facing claims are the two noted above; the only quantitative claims (module times and the aggregate) are verified. No unsafe advice (no commands). VERIFIED BY ME: the digest and HEAD; the full page text (lines 1-23); the review contract; the page-completion plan; all five link target files and their frontmatter/time lines; sidebar order of modules; Prerequisites lines of modules 1.1-1.5; module 1.3's hands-on Setup text; module 1.5's exercise intro (design review, no cluster needed); the parent prerequisites/index.md and zero-to-terminal/kubernetes-basics hubs' route wording; the aggregate arithmetic by hand; git log for the page. TAKEN FROM SUPPLIED EVIDENCE and not re-judged: page-reviews.json history (OLD-workflow dispositions treated as void), the older review files and source-catalog JSON, which I only grepped for mentions of this page and did not open in full. URLS ACTUALLY OPENED: none; the page cites no external URLs and I did not fetch any, so the two external-facing claims remain unchecked against an external source (unknown, not a pass). PROVENANCE: reviewer is Claude Code, actual model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), Claude Agent SDK CLI harness, read-only checkout. Review kind: whole-page review, call 1 of 2. LIMITS: a rendered-site build was not run; anchor/slug rendering was inferred from file paths; no commands were executed beyond reads, sha256sum, git log and grep.

### Findings (verbatim JSON)

```json
[
 {
  "id": "NB1-route-prereq-next",
  "title": "Hub gives no entry skills, environment note, or next-step link, and omits that module 1.3's lab depends on Kubernetes Basics 1.1",
  "body": "The hub lists five modules in a linear order but does not tell the learner what they need to start (terminal comfort; a machine that can install Docker for module 1.2), that module 1.3's hands-on setup requires installing kubectl and a disposable cluster by completing Kubernetes Basics module 1.1 (which comes after this section on the suggested route), or where to go next. Module 1.3 itself states this dependency, so a learner is not stranded, but the hub is the route page and omits it.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/index.md",
   "start_line": 13,
   "end_line": 23,
   "claim_type": "missing"
  },
  "verbatim": "These are planning estimates copied from the five module headers, not measured learner completion times.",
  "why_wrong": "A navigation hub is judged on audience and route accuracy. Following the hub's 1.1-1.5 order, a learner reaches module 1.3's lab needing a cluster from a later section, and the hub states no starting skills or next section. NON-BLOCKING because each module states its own prerequisites and the Zero to Terminal and parent prerequisites hubs carry the wider route.",
  "smallest_fix": "Add one or two sentences under the table: starting skills and environment (terminal; Docker install in 1.2), that 1.3's exercise uses a disposable cluster set up in Kubernetes Basics 1.1, and a link to Kubernetes Basics as the next section.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB2-industry-standard-unhedged",
  "title": "Unsourced, unhedged 'industry standard' claim in module 1.3 description",
  "body": "The 1.3 row asserts Kubernetes became the industry standard. No source is given, and the module body only says Kubernetes 'became the common answer'. It also sits against the hub's own opening hedge that simpler options remain valid. I did not fetch an external source (CNCF survey), so support is unknown rather than false; the claim is widely held.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/index.md",
   "start_line": 19,
   "end_line": 19,
   "claim_type": "present"
  },
  "verbatim": "The need for container orchestration and why Kubernetes became the industry standard.",
  "why_wrong": "Market-position claims are time-dependent and should be sourced or phrased as the module phrases them. NON-BLOCKING: low stakes, and the module teaches the actual reasons.",
  "smallest_fix": "Reword to match module 1.3, e.g. 'The need for container orchestration and why Kubernetes became a common answer to it.'",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB3-promotional-filler",
  "title": "Promotional filler sentences in the introduction",
  "body": "Two phrases in the second paragraph add no routing or teaching information and read as marketing: 'demystify the core concepts' and 'power modern technology companies'. The paragraph's useful content is the audience statement.",
  "priority": "P3",
  "confidence": 0.55,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/index.md",
   "start_line": 9,
   "end_line": 9,
   "claim_type": "present"
  },
  "verbatim": "You will build a strong mental model of the infrastructure and architecture patterns that power modern technology companies.",
  "why_wrong": "Mild BLOAT; the learner loses nothing a stated outcome needs if it is tightened. NON-BLOCKING nit; not a reason for another review round.",
  "smallest_fix": "Replace with a concrete outcome, e.g. 'You will be able to explain containers, Docker images, what Kubernetes adds, and when microservices are worth their cost.'",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cnidx-r2: call 2 of 2, delta review

- reviewed head: `34b13fc4d6578b4d8ad47cbd8633e56e55fce62d`
- run nonce: `d432daeb620246c18cc25707fecd5bad`
- verdict: `correct` (confidence 0.9)

### Explanation (verbatim)

Delta review (call 2 of 2), not acceptance. I found no blocking defect, and the three call-1 non-blocking items are closed.

Task 1. HEAD is 34b13fc4d6578b4d8ad47cbd8633e56e55fce62d. The diff from 0de5fb71 touches one file, src/content/docs/prerequisites/cloud-native-101/index.md (4 insertions, 2 deletions). The page sha256 at HEAD is 0bdcbc81381e7ab96bf1a3d19d79f082d86c4c50667a3f249bf33241cf46439f, which matches the expected value. I read the whole page.

NB1 (fixed). Module 1.3's header prerequisites line says to complete Your First Cluster to install kubectl and prepare a dedicated disposable cluster. Its Hands-On Setup says to complete Your First Cluster "if needed", then independently confirm that the selected context is a dedicated disposable cluster. The hub paragraph therefore matches module 1.3, including the "if needed" hedge. Kubernetes Basics 1.1 repeatedly stresses disposable local kind clusters, which is consistent with "dedicated and disposable". Module 1.2 has an "Installing Docker" section and a header line requiring Docker Engine or Docker Desktop plus a terminal, so the Docker/terminal prerequisite is supported. Link check: a script over all 7 markdown links on the page resolved each target to an existing file. These are the 5 module links, ../kubernetes-basics/module-1.1-first-cluster/ (module-1.1-first-cluster.md exists) and ../kubernetes-basics/ (index.md exists). No external URLs were opened or present.

The paragraph also fits the surrounding text. It does not contradict or duplicate the estimates note, which is only about time. The placement between the table and the estimates note reads acceptably. It slightly separates the note from the table it describes, but that is a preference. Two small beginner-readability points remain, both non-blocking: "selected cluster" is not defined on the hub, and "dedicated and disposable" is jargon. Module 1.3 and Kubernetes Basics 1.1 define both.

NB2 (fixed). The 1.3 row now says "a common answer". Module 1.3 line 56 says "Kubernetes became the common answer". Grep for "industry standard" in cloud-native-101/*.md returned nothing, so no unsourced market claim remains and the hub matches the module.

NB3 (fixed). The second paragraph now states a concrete audience and four outcomes. Module 1.5's outcomes cover monolith vs microservices trade-offs; modules 1.1-1.3 cover containers, Docker, and Kubernetes. Nothing promised is untaught. Module 1.4 (CNCF) is not in that sentence, but the unchanged third paragraph still covers CNCF and the 1.4 row is present, so no route information is lost. The removed sentence "foundational prerequisite for KubeDojo" is not needed: prerequisites/index.md describes the section ("Containers, Docker, Kubernetes, and the cloud-native ecosystem from first principles") and lists the route Cloud Native 101 then Kubernetes Basics, and the new paragraph adds that next step. No heading or anchor changed: the page has the same "## Modules" heading, and inbound links (prerequisites/index.md, cloud/*, philosophy-design/*, on-premises, uk/cloud/*) all target the page root without fragments.

Counts and times. There are 5 modules. Module headers say 80-110, 90-120, 90-120, 100-130 and 90-120 minutes, matching the table. The low sum is 80+90+90+100+90 = 450 and the high sum is 110+120+120+130+120 = 600, i.e. 7 h 30 min to 10 h, as the page states.

Scores (call-1 labels). D1 outcome clarity 4. D2 content accuracy 5, because every claim is now verified or hedged. D3 teaching depth 4. D4 examples/practice 4 (nav hub, no lab). D5 coherence/sequence 4. D6 audience fit/prerequisites 4 (the gap is closed, with the small jargon caveat above). D7 concision 4. D8 safety/honesty 5. Total 34/40, which is 1 above the 33 floor. Every D is at least 4. L is not applicable.

BLOCKING: none. NON-BLOCKING: "selected cluster" and "dedicated and disposable" are undefined on the hub; the added paragraph sits between the table and its estimates note; "Our journey begins" in the third paragraph is mildly rhetorical.

Provenance: reviewer Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family), Claude Code harness with the sources MCP available. The author is OpenAI gpt-6.1-terra, so the review is cross-family. I did not use the sources MCP, since the page has no Ukrainian content. Checks I performed: git diff and stat, sha256sum, a full read, greps of modules 1.2, 1.3 and 1.5, Kubernetes Basics 1.1 and prerequisites/index.md, an inbound-link grep, and a link-existence script. Supplied but not independently re-run: the call-1 ledger. Limits: I did not render the site or run the build, tests or scripts.

### Findings (verbatim JSON)

```json
[]
```
