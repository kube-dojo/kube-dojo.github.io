# Reviews of prerequisites/index.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The page is a navigation hub without a lab of its own.

## kd-wp-pidx-r1: call 1 of 2, whole-page review

- reviewed head: `51ca41ad43ca1dd35ad099fb5f1861dd9c4c0357`
- run nonce: `7ffcec697c344790ac1d203fe87afcb7`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/index.md = a7ff65157aa8e90412fa1cc2b9f240f890f5e316aa3cf4e573e2585df8409f87 (matches the stated digest); git rev-parse HEAD = 51ca41ad43ca1dd35ad099fb5f1861dd9c4c0357 (matches). I read all 187 lines of the page and docs/review-contract.md in full.

PAGE TYPE: navigation hub with no lab (route, audience and link checks; theory, quizzes and labs may be omitted). L1-L5 not applicable.

SCORES (D1-D8 labels were not defined in the files I read; I assumed this order: D1 audience fit, D2 outcomes/scope, D3 explanation/under-explanation, D4 route/link/outcome alignment, D5 factual accuracy/sources, D6 concision/non-repetition, D7 safety/consistency, D8 structure):
- D1=4: the beginner audience and the 'do not skip if' triggers are stated, and the Zero to Terminal route is clear.
- D2=4: scope (terminal, containers, Kubernetes basics, declarative thinking, Git, delivery) matches the six sections that exist.
- D3=4: the route rationale is mostly stated (Git Deep Dive is not required before Cloud Native 101 or Kubernetes Basics). Minor gap: 'the section's setup' at line 26 is unlinked and unnamed (non-blocking N1).
- D4=4: every internal link resolves, and so do both Module 0.2 anchors and the Platform Engineering '#do-not-start-here-yet' anchor. The six section module counts (11, 5, 8, 4, 10, 6) match the files on disk and sum to the page's '44 modules'. Link titles match the target module titles.
- D5=4: every checkable claim holds (see source_status).
- D6=3: BLOAT. The Git-preparation recommendation is stated three or four times, and the Linux, AI and AI/ML routes are listed in three overlapping sections (findings B1 and B2).
- D7=4: no unsafe sudo, credential or exposure advice. The cost caution is present at line 26. The Zero to Terminal blurb at line 33 is slightly misleading about 'deploying' (N2).
- D8=4: the structure is clear, but the tail repeats itself.
TOTAL=31/40. The 33 floor is missed and D6<4, so the floors are NOT met.

DISPOSITION: revise, confidence 0.8.

SOURCE_STATUS: supported. The page makes no external factual claims, only local-curriculum structure and route claims. I judged about 12 distinct material claims directly against the checkout, all supported: (1) 11/5/8/4/10/6 module counts per section, matched to directory contents; (2) '44 modules', 11+5+8+4+10+6=44; (3) all 6 section hub links and 54 module links resolve; (4) the module titles in the tables match target frontmatter; (5) the Module 0.2 anchors #opening-the-terminal-and-reading-the-prompt and #hands-on-exercise-your-first-terminal-session exist; (6) the Platform anchor #do-not-start-here-yet exists and platform/index.md's readiness list (Kubernetes, Linux troubleshooting, Git collaboration, cloud-native vocabulary) matches line 157; (7) the Linux, k8s, cloud, ai, ai-ml-engineering, on-premises and platform targets exist; (8) the route Zero to Terminal -> Cloud Native 101 -> Kubernetes Basics with Linux as a fork agrees with zero-to-terminal/index.md; (9) the Git Deep Dive-before-Modern-DevOps recommendation agrees with modern-devops/index.md; (10) philosophy-design/index.md says it follows Cloud Native 101 and Kubernetes Basics, consistent with the diagram order; (11) Module 0.6 Git Basics exists for the 'comfortable with basic Git' claim; (12) the 'Zero to Terminal ... 11 modules' description is broadly consistent with module 0.11's local-or-cloud capstone, with the caveat in N2. Partly supported: 0. Unsupported: 0. Unknown: 0. The 244-claim citation seed has all-null judgments and was treated as an author inventory only; I did not re-judge it row by row. The earlier page-reviews.json dispositions are void history.

LAB_EXECUTION: not applicable. The page has no hands-on exercise; the Module 0.2 exercise it links to was not run by me.

BLOCKING FINDINGS:
B1 (lines 132-146, 155): BLOAT. The same recommendation (basic Git from Module 0.6, then Git Deep Dive, then Modern DevOps) is given three times in consecutive blocks: the paragraph at 132, the second ASCII diagram at 136-142, and the 'Recommended Git Preparation' section at 144-146. Line 155 then qualifies the Modern DevOps link with 'after the recommended Git preparation above'. Keep the one paragraph at 132 and drop the second diagram and the section.
B2 (lines 148-187): BLOAT. Next-step destinations are enumerated in three overlapping places: 'Common Next Routes' (148-155), 'Related Foundations' (163-171) and 'After Prerequisites' (175-187). Linux, AI and AI/ML Engineering each appear in all three, and Kubernetes Certifications and Cloud appear in two. The learner gains no information from the second and third lists. Merge into one list or table.

NON-BLOCKING FINDINGS:
N1 (line 26): 'read the section's setup and each module's platform and cost notes where applicable'. 'The section's setup' is unlinked and ambiguous. The hub never names Windows/WSL or Docker requirements, which Zero to Terminal's hub states. A link to the Zero to Terminal 'Who Is This Track For?' text would be cleaner.
N2 (line 33): 'From "what is a computer?" to deploying your first server from the command line.' This reads as a cloud deployment with its cost. The track hub and Module 0.11 offer a local-container path with no cloud account, and the track's own framing is 'serve a website and check it in a browser'. A hedged blurb would match.
N3 (line 24 vs line 159): 'Do Not Skip This If ... tempted to jump straight into advanced tracks' sits in mild tension with 'a suggestion, not a requirement'. Line 24 is hedged, so I treat it as a nit.
N4: module numbers 1.1-1.8 repeat across Cloud Native 101, Kubernetes Basics, Philosophy & Design and Modern DevOps tables. This matches the target module titles, so I did not require a change.

OMITTED-CLAIM DISCOVERY: no unledgered material external factual claim found. The page has no versions, prices or quotas. The only quantitative claim ('all 44 modules') is verified.

VERIFIED BY ME: the digest; HEAD; the full page; the link/anchor/title existence script across all internal links; the module counts per directory; the frontmatter titles; sibling hubs (zero-to-terminal, cloud-native-101, kubernetes-basics, philosophy-design, modern-devops, platform); module 0.11 text on local/cloud paths and billing; the review contract. TAKEN FROM SUPPLIED EVIDENCE and not re-judged: the citation seed's 244 null-judgment rows, historical page-reviews.json entries, the older catalog JSONs (not opened beyond top-level keys).

URLS ACTUALLY OPENED: none. The page cites no external URLs, and all verification was against repository files.

PROVENANCE: reviewer is Claude Code, actual model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), harness Claude Agent SDK CLI with a read-only checkout. Review kind: whole-page review, call 1 of 2.

LIMITS: no commands were executed beyond reads and a static link-check script; the rendered site/anchor slugs were inferred from heading text, not from a built site; D1-D8 label order was assumed; seed rows were not individually re-judged.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B1-git-prep-triple-restatement",
  "title": "Git-preparation recommendation restated three times in consecutive blocks (BLOAT)",
  "body": "Line 132 gives the recommendation that Git Deep Dive is not required before Cloud Native 101 or Kubernetes Basics but is recommended before Modern DevOps. Lines 134-142 repeat the Git Basics -> Git Deep Dive -> Modern DevOps sequence as a second ASCII diagram. Lines 144-146 restate it as a standalone section, and line 155 refers back to 'the recommended Git preparation above'.",
  "priority": "P2",
  "confidence": 0.85,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/index.md",
   "start_line": 132,
   "end_line": 146,
   "claim_type": "present"
  },
  "verbatim": "## Recommended Git Preparation for Modern DevOps\n\nStart with [Git Basics](zero-to-terminal/module-0.6-git-basics/), then use [Git Deep Dive](git-deep-dive/) to practice repository history, collaboration, and recovery before continuing to [Modern DevOps](modern-devops/).",
  "why_wrong": "The review contract treats BLOAT (padding and repetition) as equally blocking with under-explanation. The learner needs the Git-prep advice once; the second diagram and the dedicated section add no information, and the third restatement forces a back-reference at line 155.",
  "smallest_fix": "Keep the paragraph at line 132, delete the second diagram (134-142) and the 'Recommended Git Preparation' section (144-146), and drop 'after the recommended Git preparation above' from line 155, or fold the Git Basics link into line 132.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B2-next-routes-triple-list",
  "title": "Next-step destinations listed in three overlapping sections (BLOAT)",
  "body": "'Common Next Routes' (148-155), 'Related Foundations' (163-171) and 'After Prerequisites' (175-187) each list Linux, AI and AI/ML Engineering with near-identical one-line rationales. Kubernetes Certifications and Cloud appear in two of the lists, and Platform Engineering appears in several places. The three sections serve the same purpose, to say where to go after the prerequisites.",
  "priority": "P2",
  "confidence": 0.85,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/index.md",
   "start_line": 148,
   "end_line": 187,
   "claim_type": "present"
  },
  "verbatim": "## Related Foundations\n\nThese are not inside the `prerequisites/` section, but they are common next steps:",
  "why_wrong": "Duplicated destination lists are padding, so the page fails the D6 concision floor. They also create three places to keep in sync when a track's entry guidance changes.",
  "smallest_fix": "Merge the three sections into a single 'Where to go next' list or table (Linux, Kubernetes Certifications, Cloud, On-Premises, Platform Engineering, AI, AI/ML Engineering) and keep the Platform readiness and 'suggestion, not requirement' sentences once.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N2-first-server-blurb",
  "title": "Zero to Terminal blurb implies a cloud 'deployment' (non-blocking)",
  "body": "The hub says the track ends with 'deploying your first server from the command line'. Module 0.11 and the track hub offer a local container path that needs no cloud account, and frame the goal as serving a website and checking it in a browser. The cloud path involves billing and a public endpoint. The blurb overstates the cloud framing for a beginner hub, although line 26 does mention cost notes.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/index.md",
   "start_line": 33,
   "end_line": 33,
   "claim_type": "present"
  },
  "verbatim": "For absolute beginners. From \"what is a computer?\" to deploying your first server from the command line.",
  "why_wrong": "The wording suggests a cloud deployment is required and slightly mismatches the track's own local-or-cloud description.",
  "smallest_fix": "Use the track hub's framing, e.g. 'to serving a website from the command line, locally or on an authorized cloud VM'.",
  "sources": [
   "src/content/docs/prerequisites/zero-to-terminal/index.md",
   "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md"
  ]
 }
]
```

## kd-wp-pidx-r2: call 2 of 2, delta review

- reviewed head: `55035d6c27ada188cd81f5e9cf25195d472144c1`
- run nonce: `b98eb9d3cb014a199b16f9b0bc32cdfe`
- verdict: `correct` (confidence 0.9)

### Explanation (verbatim)

Task 1: HEAD is 55035d6c27ada188cd81f5e9cf25195d472144c1. The diff against 51ca41ad is one file, src/content/docs/prerequisites/index.md, 5 insertions and 47 deletions. The page sha256 at HEAD is 2de49e8931e3c72ddd837908a9f71c5b184a3b4f76d8ac3b384ba9108a473995, which matches the expected value. I read the whole page at HEAD and the full delta.

B1 is closed. The only remaining Git-preparation statement is the paragraph at line 132: basic Git from Zero to Terminal, then Git Deep Dive, recommended before Modern DevOps and its IaC, GitOps and CI/CD topics. Grepping the page for 'above', 'recommended Git' and 'Git Basics' returns only the Module 0.6 table row at line 42. Nothing points at the deleted diagram, section or 'above' text. The route diagram already orders Zero to Terminal, Git Deep Dive and Modern DevOps, so there is no restatement.

B2 is closed. There is one 'Where to go next' list at lines 134-141 with Linux, Kubernetes Certifications, Cloud, On-Premises Kubernetes, AI and AI/ML Engineering, each with a one-line reason. All six targets exist (linux, k8s, cloud, on-premises, ai and ai-ml-engineering index.md). Every other destination the old lists linked is still linked: Platform Engineering in line 143 and module 1.5 of the Modern DevOps table; Modern DevOps in its section heading, table and the route diagram; Git Deep Dive in its section and line 132; Cloud Native 101, Kubernetes Basics and Philosophy & Design in their section headings. The Platform readiness sentence with the '../platform/#do-not-start-here-yet' link survives. The anchor resolves to '## Do Not Start Here Yet' at platform/index.md:9. Two old per-link rationales were dropped: Platform Engineering's 'go deeper into platform practices' and Modern DevOps's trailing hint. Platform's rationale is replaced by the prerequisites sentence, and the Modern DevOps route is explained at line 132. The merged list is at least as clear as the three it replaced, and the On-Premises item is a new but accurate gloss. No learner-needed rationale was lost.

Anchors: I grepped src (English and the uk mirror), docs, the astro config and scripts for links into prerequisites with fragments, and for the removed slugs do-not-skip-this-if, recommended-git-preparation, common-next-routes, related-foundations and after-prerequisites. There are no inbound links to this page's anchors, so nothing dangles. The relative '../#planned-modules' matches found are in ai/ pages, not this hub. The new link zero-to-terminal/#who-is-this-track-for resolves to the heading '## Who Is This Track For?' at zero-to-terminal/index.md:10, and that section does state the WSL and Docker requirements. I did not open or re-verify the uk/prerequisites/index.md mirror, which is outside this PR's scope.

N1 is closed: the setup sentence now links the Zero to Terminal 'Who Is This Track For?' section, which holds the Windows/WSL and Docker requirements.
N2 is closed. The blurb 'serve a website from the command line locally or on an authorized cloud VM' matches the Module 0.11 objective (a local container or a cloud VM) and its 'authorized environment' wording, and no longer implies a cloud-only deployment.
N3 is mostly closed. 'Start Here If' fits bullets 1 and 2 well and removes the tension with 'a suggestion, not a requirement' at line 145. Bullet 3, 'you are tempted to jump straight into advanced tracks', reads slightly oddly under 'Start Here If'. The line 24 sentence 'use it when these topics are unfamiliar' keeps the guidance intact, so a learner who should not skip the layer is still told to use it. The rename is a mild improvement, and the bullet 3 wording is not a blocker.
N4 is unchanged; no change was required.

Counts and links: I ran a script over all 65 markdown links, resolving each to a file or directory index and checking fragments against slugified headings. There were 0 missing files and 0 bad anchors. The section module counts are 11, 5, 8, 4, 10 and 6, which sum to 44 and match the table row counts parsed from the page and the '44 modules' claim. No external URLs were opened, because the page has none.

New defects from the delta: none blocking. Two trivial nits remain. 'Where to go next' uses sentence case while sibling headings use Title Case. The third 'Start Here If' bullet is slightly off-key. Neither blocks.

Scores from a full read, with the call-1 labels. D1 audience fit 4, D2 outcomes/scope 4, D3 explanation 4, D4 route/link/outcome alignment 5, D5 factual accuracy/sources 5, D6 concision/non-repetition 4 (up from 3), D7 safety/consistency 5, D8 structure 4. The total is 35/40 and every dimension is at or above 4, so the floors are met (every D at least 4, total at least 33). L is not applicable. BLOCKING: none. NON-BLOCKING: the two nits above.

Provenance: reviewer is Claude Code running claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), toolful, in a read-only checkout of the PR head. Review kind: delta review, call 2 of 2, not acceptance. Checks performed by me: git rev-parse, diff and stat, sha256, whole-page read, greps, the link, anchor and count script, and the existence checks on destination pages and headings. Checks supplied and not re-derived: the call-1 ledger text and score labels. Limits: I did not render the site or run the Astro build, I did not review the uk mirror, and I ran no tests, per the instructions.

### Findings (verbatim JSON)

```json
[]
```
