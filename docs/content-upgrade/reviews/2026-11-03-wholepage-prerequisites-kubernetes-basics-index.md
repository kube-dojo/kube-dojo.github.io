# Reviews of prerequisites/kubernetes-basics/index.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). This is a scoped verdict, not lead acceptance. The page is a navigation hub without a lab of its own. Call 1 returned a correct/retain verdict with two non-blocking findings, so no fix and no second call were made.

## kd-wp-kbidx-r1: call 1 of 2, whole-page review

- reviewed head: `4447642c1183ff1ca96367265ae4f333cac23a9c`
- run nonce: `3618eaf9a5d847bdbd2c0475a5092e27`
- verdict: `correct` (confidence 0.8)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/kubernetes-basics/index.md = f93884b9b37d89e6d548905f9632a6bc913fe05fd84ca35937caff853821da7f, matching the supplied digest. HEAD = 4447642c1183ff1ca96367265ae4f333cac23a9c (git rev-parse). PAGE KIND: navigation hub (25 lines: three intro paragraphs, an 8-row module table, one time-estimate note). The review contract lets hubs omit theory, quizzes and labs but requires audience, route and link checks. L1-L5 are therefore not applicable and lab_execution = not applicable. The hub has no exercise; the modules' labs were not run or reviewed here, and the host has no container runtime or cluster. SCORES (the module rubric applied proportionately to a hub): D1 outcome clarity 4, because the closing outcome (lines 8-10) is concrete: practised deploying, inspecting, updating and cleaning up example workloads in a disposable cluster, and each row says what its module covers. D2 content accuracy 5, because every checkable claim held: 8 titles, 8 link targets, 8 times, the arithmetic, and the Secret and Deployment statements. D3 teaching depth/mechanisms 4, not applicable beyond routing, and the hub does not claim to teach. D4 examples/practice alignment 4, not applicable; the closing outcome claim is backed by exercises with cleanup sections in the modules (see checks). D5 coherence/sequence 4: table order 1.1-1.8 matches the sidebar order 2-9 and the module slugs. D6 audience fit/prerequisites 4: line 6 names two audiences, but the hub gives no entry prerequisites (see NB1). D7 concision/no bloat 4: line 6 and the opening of line 8 carry mild filler (see NB2), and nothing else is padded. D8 safety/honesty 5: line 10 explicitly warns that creating a Secret alone does not secure sensitive data, line 8 hedges Deployments and Services with readiness, node-health and capacity limits, and the time note says the numbers are planning estimates and not measured. TOTAL 35/40; all items are at least 4 and the total is at least 33, so the floors are met. DISPOSITION: retain, confidence 0.8. SOURCE_STATUS: supported. I judged 17 claims: 8 module titles against frontmatter, 8 link targets existing, 8 times against module headers (counted as one structural group, 24 checks), the aggregate arithmetic, 'Secrets require additional access controls and storage protections', 'Deployments maintain replicas', and 'practiced ... cleaning up ... in a disposable cluster'. Excluding the 24 individual structural checks, 3 external-facing claims were judged, all supported. Findings: none BLOCKING. NON-BLOCKING: NB1 and NB2 below. No unsupported or unverifiable claim was found. VERIFIED BY ME: (a) Arithmetic: minimums 80+100+80+90+80+60+50+60 = 600 and maximums 110+140+110+130+110+90+80+90 = 860 minutes; 600 min = 10 h and 860 min = 14 h 20 min, matching line 25. (b) Each of the 8 per-row time ranges matches the 'Time to Complete' line in the corresponding module header (grep of module-1.1..1.8). (c) All 8 module files exist and the slugs match the relative links. (d) The parent prerequisites/index.md lists the same 8 modules. (e) Every module has a Hands-On Exercise heading, and cleanup sections or steps exist in 1.1 (line 732 cluster removal), 1.2 (Step 7 Clean up), 1.3 (Task 6), 1.4 (Cleanup), 1.5 (Cleanup), 1.6 (Task 5), 1.7 (Task 6) and 1.8 (Success Checklist), so the 'cleaning up' outcome is taught. (f) Git history: the last page edits were 82e5f0ff1 and 17f0248b9; the latter produced the Secrets caveat and the 'disposable cluster' outcome. (g) The prior evidence in docs/content-upgrade/reviews and page-reviews.json was treated as unverified history. URLS ACTUALLY OPENED: https://kubernetes.io/docs/concepts/configuration/secret/ (the fetch tool returned the first 100,000 of 133,167 characters; it supports 'Kubernetes Secrets are, by default, stored unencrypted in the API server's underlying data store (etcd)' and 'Enable Encryption at Rest ... Enable or configure RBAC rules with least-privilege access to Secrets', which backs line 10). https://kubernetes.io/docs/concepts/workloads/controllers/deployment/ (the fetch tool returned the first 100,000 of 158,266 characters; it supports 'A Deployment provides declarative updates for Pods and ReplicaSets' and ReplicaSet-based replica maintenance, which backs 'maintain replicas'). The readiness/available-only-when-ready wording was not seen verbatim in the truncated excerpt; the hedge 'subject to readiness signals, healthy nodes, and available capacity' is conservative and the hub does not state a specific rule, so I treat it as unverified but not a defect. Fetch limits are UNKNOWN, not pass. NON-BLOCKING FINDINGS: NB1 (line 6 and lines 8-10): the hub never states what a learner needs to start, though the opening says 'We will start from the ground up'. Module 1.1's header requires 'Docker installed, Cloud Native 101 completed' and builds its cluster with kind on Docker. A learner landing here directly is not told that Docker and the Cloud Native 101 section come first. Smallest fix: add one sentence, e.g. 'Before starting, complete Cloud Native 101 and have Docker installed (Module 1.1 uses it to create a local kind cluster).' NB2 (line 6): 'you will dive into the foundational concepts and practical skills required to navigate and manage Kubernetes environments' and 'understanding these core primitives is essential for modern cloud-native deployment' are generic promotional filler that teaches nothing; line 6 could be trimmed to the audience statement. Neither is material. OMITTED-CLAIM DISCOVERY: the page contains no versions, prices, quotas or service names. The only material factual claims are line 8 (Deployments and Services hedging), line 10 (Secrets) and line 25 (times/arithmetic), all checked. A minor note on the table (not a finding): the row 1.6 description 'protecting sensitive data' is slightly stronger than line 10's own caveat, but the module teaches RBAC and etcd encryption boundaries, so it is consistent. No unsafe advice: the page contains no commands. Observation outside the scope of this page: modules 1.6, 1.7 and 1.8 headers say 'long-form read' though they have hands-on exercises, so the hub's 'copied from the eight module headers' remains accurate but the headers understate practice; this belongs to those modules' reviews. PROVENANCE: reviewer is Claude Code, actual model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), Claude Agent SDK CLI harness, read-only checkout. Review kind: whole-page review, call 1 of 2. LIMITS: no rendered-site build was run, so link resolution was inferred from file paths and slugs; no container or cluster commands were executed; the two Kubernetes docs fetches were truncated, so some of their sections were not read; no learner-effect claim is made.

### Findings (verbatim JSON)

```json
[
 {
  "id": "KBIDX-NB1",
  "title": "Hub says 'start from the ground up' but states no entry prerequisites",
  "body": "The hub opening promises to start from the ground up and never tells the learner what must come first. Module 1.1 requires 'Docker installed, Cloud Native 101 completed' and creates its cluster with kind, which runs on Docker. A learner who lands on this hub directly (search, sidebar) is not told about either prerequisite until inside Module 1.1. Non-blocking: the sidebar and the parent hub give the route, and Module 1.1 itself states the prerequisites.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/index.md",
   "start_line": 8,
   "end_line": 8,
   "claim_type": "missing"
  },
  "verbatim": "We will start from the ground up by setting up your first local cluster and learning how to interact with it using the standard command-line tool, kubectl.",
  "why_wrong": "The contract requires audience and route checks for hubs. The hub gives a route (module table) but no starting-skill or environment statement, while Module 1.1 requires Docker and Cloud Native 101.",
  "smallest_fix": "Add one sentence: 'Before starting, complete Cloud Native 101 and have Docker installed; Module 1.1 uses it to create a local kind cluster.'",
  "sources": [
   "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md:18"
  ]
 },
 {
  "id": "KBIDX-NB2",
  "title": "Opening paragraph is generic promotional filler",
  "body": "The first paragraph spends its words on 'dive into' and 'essential for modern cloud-native deployment' and adds no routing or outcome information beyond the audience sentence. Non-blocking: it is one paragraph and does no harm.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/index.md",
   "start_line": 6,
   "end_line": 6,
   "claim_type": "present"
  },
  "verbatim": "In this section, you will dive into the foundational concepts and practical skills required to navigate and manage Kubernetes environments.",
  "why_wrong": "The sentence gives the learner nothing they need that the table and the later paragraphs do not already state (D7 concision).",
  "smallest_fix": "Trim the paragraph to the audience sentence, e.g. 'This section is for people moving from traditional infrastructure or standalone containers to Kubernetes.'",
  "sources": [
   "none"
  ]
 }
]
```
