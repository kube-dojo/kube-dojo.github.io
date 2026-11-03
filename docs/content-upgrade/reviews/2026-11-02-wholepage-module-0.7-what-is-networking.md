# Reviews of prerequisites/zero-to-terminal/module-0.7-what-is-networking.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for all three: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. Call 3 was a CTO-granted pinned verification round limited to the two-line outcome/criterion fix.

## kd-wp-07-r1: call 1 of 2, whole-page review

- reviewed head: `fd6d035455b5de30da45ab760e4050aefd85ea51`
- run nonce: `c4c0ddad1ee04fd8b6cb683279fab2cb`
- verdict: `incorrect` (confidence 0.82)

### Explanation (verbatim)

DIGEST: HEAD fd6d035455b5de30da45ab760e4050aefd85ea51; `sha256sum` of module-0.7-what-is-networking.md = 55bb1ab5ad89ef9a2a2d3d714c26b371831d81b699a37202cfbba899b4f840e4, matching the supplied digest. I read all 748 lines in bounded reads.

SCORES (module, docs/pipeline.md rubric): D1 4 (outcomes measurable, Bloom 3+; the Kubernetes outcome is thinly assessed, see B2). D2 3 (key vocabulary used before or without explanation: virtual host, NXDOMAIN, ICMP, TCP, firewall, reverse proxy, authoritative, HEAD; see B1). D3 4 (five predict-then-reveal prompts, seven scenario quizzes, nine tasks). D4 4 (hypothetical scenarios are labelled, plus a mistakes table). D5 3 (quiz stems 2 and 4 ask a question the answer declines to answer; there is no Kubernetes assessment item). D6 4 (chunked, diagrams, worked incidents). D7 3 (good analogies, but the same 'one response proves little' point recurs and some paragraphs are filler; see B4). D8 4 (patterns, anti-patterns, decision table). Sum 29/40. Floors NOT met (D2, D5, D7 are below 4; the total is below 33).

LAB (docs/quality-rubric.md): L1 4 (synthetic incidents with no recipe, though tasks 1-9 are prescriptive). L2 4 (guided commands, then a combined diagnosis). L3 4 (predict and explain; 'what remains unknown'). L4 3 (solution notes teach and give some 'if you see X' feedback, but there are no tiered hints anywhere; the incident reveals go straight to the full diagnosis). L5 3 (Kubernetes transfer is one sentence at line 706; no transfer task or worked answer). Sum 18/25. Floors NOT met (L4 and L5 are below 4; the total is below 21).

DISPOSITION: revise. Confidence 0.82.

SOURCE_STATUS: partly supported. Claims I judged: 10 ledger rows opened and confirmed against primary text (N001-N003 RFC 1918 s.3; N006 and N007 RFC 6335 s.6, with N007 supported only by the 'registries for all of these transport protocols' wording in the supplied excerpt; N008 and N010 Kubernetes 1.35 Service; N011 and N012 Kubernetes 1.35 DNS; N013 ports-and-protocols, which also says 'All default port numbers can be overridden'); 1 unledgered claim partly supported (line 404 causal clause, see NB3); 1 unledgered claim unsupported as written (line 380 'Endpoint changes', see NB4). UNKNOWN to me, taken from the author ledger only: the remaining ~30 rows. My fetches of RFC 9110 (.txt and .html) returned truncated text that did not reach s.7.2, 9.3.2, 15.3.1, 15.5.5 or 15.6.1, only the status and method tables and a HEAD cross-reference. A shell curl attempt returned no file. So the RFC 9110, RFC 1035, 3022, 5737, 1034, 883, 9293, IANA CSV, man7 ping, curl manual, Debian nslookup and controlling-access rows are UNKNOWN from my side, not passes. The seed JSON on disk is the old 10-claim v2 seed and does not match the current 41-row ledger.

LAB_EXECUTION: unknown. I could not find `exercise-run.log` in the checkout, so the Linux run (ping, hostname, curl, nslookup, redirect) is taken from the author's statement only and I did not rerun it. The macOS commands (`ipconfig getifaddr en0`) and the Kubernetes mapping were not run by anyone. Nothing on the page needs a cluster, container runtime or cloud account.

BLOCKING FINDINGS
B1 (UNDER-EXPLANATION, line 233, also 341, 440, 629): 'virtual host' is the reason the page says a direct-IP 200 does not prove the named app works, yet it is never explained. It appears four times with no definition. Related terms are also used unexplained: NXDOMAIN (first appears in Q7 at 462 and in the Incident A transcript at 615; never defined), ICMP (189, 283; never glossed beyond 'echo'), TCP (163, 193), firewall (73, 173), reverse proxy (175), 'authoritative DNS' (464, 631), HEAD (only in the 577 solution note). Fix: add roughly 3-4 sentences at the first use, covering how one IP can serve several named sites chosen by the hostname in the request, NXDOMAIN as the resolver's 'this name does not exist' code, and one-line glosses for ICMP, TCP and firewall.
B2 (outcome to teaching to practice misalignment, line 706 and outcome at line 23): the outcome 'Evaluate how beginner networking ideas show up in Kubernetes Services, Pods, and the Kubernetes 1.35 API server' has scattered one-sentence teaching (31, 177-183, 239, 390). Its only practice is a single sentence at 706 and an unanswered success criterion at 721. There is no quiz item, task or solution, and nothing shows what a Service name looks like or what the learner should produce. Fix: add one worked mapping with a solution (for example a Service port 80 mapped to targetPort 8080 with a cluster DNS name, labelling name, address, port and protocol response) or add one Kubernetes quiz question; otherwise downgrade the outcome verb and remove the 721 criterion.
B3 (practice floor L4, lines 606-704): the four synthetic incidents give only full diagnoses behind a `<details>`; there are no tiered hints (concept, then narrowing, then specific). The rubric floor is 4 and the page scores 3. Fix: add two short hint tiers before each diagnosis, for example 'which of name, address, port or HTTP response does each command test?', then 'what does the other command's different result rule out or leave open?'.
B4 (BLOAT, lines 372, 392, 396; repeats at 63, 143-146, 359, 420): filler and repetition. Line 372 comments on its own section ('the "when this does not apply" section is intentionally modest'). Line 396 asks the learner to keep a 'decision framework' checklist that the page never supplies, then closes with generic wording. Line 392 restates 359 and the 420 table row ('change one thing at a time'). The 'one response does not prove the whole system' point is also restated at 33, 249, 251, 259, 345-347, 368 and 370. Fix: cut 372, 396 and 392 and merge the duplicate sentences; the learner loses nothing a stated outcome needs.

NON-BLOCKING FINDINGS
NB1 (quiz stems vs answers, lines 432, 444): Q2 asks 'What layer is most likely still failing?' and Q4 asks 'Is the first suspect DNS, the customer's internet, or the server-side application path?', but both answers decline to name a cause. A learner cannot tell what a correct response looks like. Make each answer say what is proven, what is open and which check comes next, or reword the stems. Q2 also has a grammar slip ('A firewall or a service problem are possibilities').
NB2 (inference inconsistent with the page's thesis, lines 304 and 349): 'proves the server returned content' and 'the request reached an HTTP server that failed internally' read as backend inferences, against line 249 ('not proof of which backend handled it'). Use 'an HTTP responder returned content' and 'an HTTP responder returned 500'.
NB3 (line 404): 'RFC 6335 describes how service names and port numbers are managed, which is why familiar services ... have widely recognized default ports.' RFC 6335 defines IANA procedures and says only that 'it is common for many services to have a default port'; the causal 'which is why' is not supported. Reword to a plain statement of the registry. Line 405 ('beginner port reasoning applies directly when `kubectl` cannot reach a cluster') and the line 171 table row ('How `kubectl` talks to your cluster', unhedged) overstate: the Kubernetes ports page says 'All default port numbers can be overridden', and the line 177 text already hedges with 'commonly'.
NB4 (line 380): 'Kubernetes events can show Service and Endpoint changes' is unsupported. The Kubernetes 1.35 Service page labels Endpoints '(deprecated)' in its navigation, and I could not confirm what events show. Drop it or say 'EndpointSlice'.
NB5 (line 627): '**Failing Layer:** DNS name resolution.' contradicts the challenge instruction ('do not invent a single failing device, layer, or configuration') and the other incidents' 'Observed Layer'. Use 'Observed Layer: the queried resolver reported NXDOMAIN.'
NB6 (Sources, lines 725-744): the list still omits the controlling-access page (used for N038, kubectl over HTTPS) and the nslookup manual (N037), and the ledger cites both. Add them.
NB7 (exercise, lines 481-485 and 547-549): there is no cleanup step for `~/kubedojo-practice` and no fallback if `nslookup` is not installed. Debian packages it separately (bind9-dnsutils), per the Debian manpage the ledger cites. Add one line for each.
NB8 (labelling, lines 285-333): the synthetic-output label at 285 precedes the ping block. The curl and nslookup sample outputs that follow are not individually labelled (nslookup says only 'Output varies'). Extend the label to 'the following outputs in this section'.

OMITTED-CLAIM DISCOVERIES (not in the ledger): line 404 causal default-port claim (NB3); line 405 and the line 171 table row on kubectl and 6443 (NB3); line 380 Endpoint changes (NB4); line 296 'Without a count, ping on Linux and macOS commonly keeps running until you press Ctrl+C' (plausible; not verified by me); line 304 'proves the server returned content' (NB2).

SAFETY: no unsafe sudo, credential, destructive or public-exposure advice. The workspace setup refuses to overwrite existing names and avoids `mkdir -p`. Line 146 and the 'authorized route' wording on router forwarding (109, 416) are adequate; nothing is blocking.

VERIFIED VS SUPPLIED: I opened the page in full, docs/review-contract.md, page-completion-plan.md, docs/pipeline.md and quality-rubric.md rubric sections, the old seed JSON claim list and the 2026-10-26 P03 review. I opened these URLs: rfc-editor.org/rfc/rfc6335.txt, rfc1918.txt, rfc9110.txt and rfc9110.html (both truncated, UNKNOWN for the section text), v1-35.docs.kubernetes.io Service, DNS for Services and Pods, and Ports and Protocols pages. The Kubernetes Service and DNS pages were only partly read: the Service fetch was truncated, so it did not reach the headless-Service text or any Endpoints-deprecation wording beyond the navigation label. I did not open RFC 1035, 3022, 5737, 1034, 883, 9293, the IANA CSV, the man7 ping page, the curl manual, the nslookup manual or the controlling-access page; those rows are UNKNOWN, not passed.

PROVENANCE: reviewer Claude Code seat running Anthropic claude-sonnet-5-5 (outside the OpenAI/Codex author family), harness Claude Code CLI. Review kind: independent whole-page review, call 1 of 2, read-only. Limits: no shell network access, truncated RFC 9110 fetches and no run log in the checkout, so lab execution and many source rows are unknown.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B1-undefined-terms",
  "title": "Core vocabulary (virtual host, NXDOMAIN, ICMP, TCP, firewall) is used without explanation",
  "body": "The page's central caveat is that a direct-IP HTTP response may come from a different virtual host or intermediary. 'Virtual host' is never explained, although it carries the reasoning in the lesson (233), the prediction reveal (341), Quiz 3 (440) and Incident A (629). NXDOMAIN first appears in Quiz 7 and in the Incident A transcript without a gloss. ICMP, TCP, firewall, reverse proxy and 'authoritative' DNS are also used unexplained.",
  "priority": "P2",
  "confidence": 0.85,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 233,
   "end_line": 233,
   "claim_type": "present"
  },
  "verbatim": "It might be a different virtual host or intermediary, so it does not establish that the named application works.",
  "why_wrong": "An absolute beginner cannot follow why a 200 from the bare IP fails to vindicate the named application, so the key reasoning step is skipped. The contract treats a term used before explanation as UNDER-EXPLANATION, which is equally blocking.",
  "smallest_fix": "At the first use, add 3-4 sentences: one IP can serve several named sites chosen by the hostname in the request, so a bare-IP request may reach a default site; NXDOMAIN is the resolver's 'this name does not exist' answer; and one-line glosses for ICMP, TCP and firewall.",
  "sources": [
   "https://www.rfc-editor.org/rfc/rfc9110.txt (s.7.2, taken from the supplied ledger, not independently opened by me)"
  ]
 },
 {
  "id": "B2-k8s-outcome-unpracticed",
  "title": "Kubernetes outcome has no real practice, assessment or worked mapping",
  "body": "Outcome 4 (line 23) says 'Evaluate how beginner networking ideas show up in Kubernetes Services, Pods, and the Kubernetes 1.35 API server'. Teaching is scattered across one-sentence mentions (31, 177-183, 239, 390). Practice is a single sentence at 706 plus a success criterion at 721 with no task, solution or quiz item. L5 transfer scores 3 as a result.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "tests",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 706,
   "end_line": 706,
   "claim_type": "present"
  },
  "verbatim": "The same questions apply in Kubernetes: check a Service name, the path from a Pod, and the Service's target port.",
  "why_wrong": "The review contract requires every outcome to map to teaching and suitable practice or assessment, and says untaught or unsupported outcomes must not pass. The learner is asked to 'explain how Kubernetes Service names, Pod IPs, and API server port 6443 map to DNS, address, port, and protocol response' with nothing to check the answer against.",
  "smallest_fix": "Add one worked mapping with a solution (for example a Service port 80 mapped to targetPort 8080 with a cluster DNS name, labelling the name, address, port and protocol response), or one Kubernetes quiz question. Alternatively, lower the outcome verb and drop the line 721 criterion.",
  "sources": [
   "https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/service/ (opened; truncated)"
  ]
 },
 {
  "id": "B3-no-tiered-hints",
  "title": "Diagnostic challenge has no tiered hints (L4 below floor)",
  "body": "The four synthetic incidents go from a prompt directly to a full diagnosis behind a details block. The nine tasks have solution notes that give some corrective feedback, but there is no concept, then narrowing, then specific hint progression. The author self-scored L4 at 2-3 and the rubric floor is 4.",
  "priority": "P2",
  "confidence": 0.85,
  "category": "tests",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 608,
   "end_line": 608,
   "claim_type": "present"
  },
  "verbatim": "For each, distinguish the observed symptom from possible causes, identify which layers deserve investigation, and choose a justified next check.",
  "why_wrong": "A stuck novice must either guess or open the whole answer; lab L4 requires hints that teach, with a concept hint, then a narrowing hint, then specific guidance. The lab floor is not met (L4 3, total 18/25).",
  "smallest_fix": "Before each incident's full diagnosis, add two short hint tiers, for example 'which of name, address, port or HTTP response does each command test?', then 'what does the other command's different result rule out or leave open?'.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B4-bloat-filler-repetition",
  "title": "Filler and repeated passages inflate a 90-120 minute page",
  "body": "Line 372 comments on its own section ('For introductory modules, the \"when this does not apply\" section is intentionally modest, but the habit scales.'). Line 396 asks the learner to keep a 'decision framework' checklist that the page never supplies, and ends with generic wording. Line 392 restates 359 and the 420 table row ('change one thing at a time'). The 'one response does not prove the whole system' point recurs at 33, 249, 251, 259, 345-347, 368 and 370, and the diagram-restating paragraph at 63 duplicates the diagram itself.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 396,
   "end_line": 396,
   "claim_type": "present"
  },
  "verbatim": "That discipline is what turns beginner commands into professional troubleshooting evidence.",
  "why_wrong": "The contract treats padding, repetition and abrupt or meta transitions as blocking BLOAT. These passages teach nothing a stated outcome needs, and they push D7 to 3 (floor 4).",
  "smallest_fix": "Delete the paragraphs at 372, 392 and 396, and merge the near-duplicate sentences at 63 and 259 into the first statement.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB1-quiz-stem-answer-mismatch",
  "title": "Quiz 2 and Quiz 4 stems ask for a pick that the answers decline to give",
  "body": "Q2 asks 'What layer is most likely still failing?' and Q4 asks for the first suspect among DNS, the customer's internet or the server-side path; the answers say the cause is unknown without answering the question asked. Q2's answer also has a grammar slip ('A firewall or a service problem are possibilities').",
  "priority": "P3",
  "confidence": 0.7,
  "category": "tests",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 432,
   "end_line": 432,
   "claim_type": "present"
  },
  "verbatim": "What layer is most likely still failing?",
  "why_wrong": "A learner cannot tell what a correct response looks like, so the quiz weakly checks the lesson's claim.",
  "smallest_fix": "Reword the stems to 'What does each result prove, and what stays open?', or make each answer state what is proven, what is open and the next check.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB2-backend-inference",
  "title": "Handoff-note example infers a backend despite the page's own caveat",
  "body": "The model handoff note says the request 'reached an HTTP server that failed internally', and line 304 says the output 'proves the server returned content'. Line 249 states an HTTP response is not proof of which backend handled it.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 349,
   "end_line": 349,
   "claim_type": "present"
  },
  "verbatim": "so the request reached an HTTP server that failed internally",
  "why_wrong": "This is the note learners are told to copy, and it contradicts the page's central thesis.",
  "smallest_fix": "Use 'an HTTP responder returned 500' and 'an HTTP responder returned content'.",
  "sources": [
   "https://www.rfc-editor.org/rfc/rfc9110.txt (taken from the supplied ledger, not opened by me)"
  ]
 },
 {
  "id": "NB3-port-causal-and-kubectl-6443",
  "title": "Unsupported causal claim about default ports; 6443 overstated",
  "body": "RFC 6335 defines IANA registry procedures and says only that 'it is common for many services to have a default port'; it does not say the procedures are why those services have well-known ports. Line 405 and the table row at 171 imply kubectl reaches the cluster on 6443, while the Kubernetes ports page says all default port numbers can be overridden.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 404,
   "end_line": 404,
   "claim_type": "present"
  },
  "verbatim": "which is why familiar services such as HTTP, HTTPS, DNS, and SSH have widely recognized default ports.",
  "why_wrong": "The causal link is not in the source, and the unhedged kubectl statements can mislead learners on managed or custom endpoints.",
  "smallest_fix": "State the registry fact without 'which is why'; hedge 171 and 405 to 'commonly'.",
  "sources": [
   "https://www.rfc-editor.org/rfc/rfc6335.txt",
   "https://v1-35.docs.kubernetes.io/docs/reference/networking/ports-and-protocols/"
  ]
 },
 {
  "id": "NB4-endpoint-events",
  "title": "Kubernetes events and Endpoint changes claim is unsupported",
  "body": "No source in the ledger supports 'Kubernetes events can show Service and Endpoint changes'. The Kubernetes 1.35 Service page labels Endpoints '(deprecated)' in its navigation.",
  "priority": "P3",
  "confidence": 0.65,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 380,
   "end_line": 380,
   "claim_type": "present"
  },
  "verbatim": "Kubernetes events can show Service and Endpoint changes",
  "why_wrong": "It is an unledgered technical claim about an API that is deprecated in the version the page names.",
  "smallest_fix": "Remove the clause or replace it with 'Kubernetes events and Service/EndpointSlice objects', citing the Service page.",
  "sources": [
   "https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/service/"
  ]
 },
 {
  "id": "NB5-failing-layer-label",
  "title": "'Failing Layer' label contradicts the challenge's own instruction",
  "body": "The challenge says not to invent a single failing layer, and the other incidents use 'Observed Layer'. Incident A's reveal asserts a failing layer.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 627,
   "end_line": 627,
   "claim_type": "present"
  },
  "verbatim": "**Failing Layer:** DNS name resolution.",
  "why_wrong": "It models a conclusion the evidence does not support, since only one resolver's report is observed.",
  "smallest_fix": "Change to '**Observed Layer:** the queried resolver reported NXDOMAIN.'",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB6-sources-list-gaps",
  "title": "Sources list omits sources the page relies on",
  "body": "The controlling-access page (kubectl over HTTPS, N038) and the nslookup manual (N037) are cited in the ledger but absent from the Sources list.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 743,
   "end_line": 744,
   "claim_type": "missing"
  },
  "verbatim": "- [curl command line tool manual](https://curl.se/docs/manpage.html)",
  "why_wrong": "Learners cannot trace the kubectl-over-HTTPS and nslookup interpretation claims.",
  "smallest_fix": "Add the Kubernetes 1.35 controlling-access page and the nslookup manual to Sources.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "NB7-cleanup-and-nslookup-fallback",
  "title": "No cleanup step for the practice directory and no nslookup fallback",
  "body": "The exercise creates ~/kubedojo-practice and never tells the learner to remove it. Task 5 has no fallback if nslookup is missing (Debian packages it separately as bind9-dnsutils, per the manpage the ledger cites). Also, the curl and nslookup sample outputs are not individually labelled synthetic.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 481,
   "end_line": 481,
   "claim_type": "present"
  },
  "verbatim": "$ mkdir ~/kubedojo-practice",
  "why_wrong": "A learner is left without a stated way to clean up, and may hit 'command not found' with no guidance.",
  "smallest_fix": "Add 'cd ~ && rm -r ~/kubedojo-practice' once the new directory is confirmed disposable, and one line saying nslookup may need installing or can be replaced by `host`.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-07-r2: call 2 of 2, delta review

- reviewed head: `0ad2c8e567d9612524583a49da4e10b0f938a872`
- run nonce: `a1da9c4e393642dfbfd2aa4cbe3de5ed`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DELTA REVIEW, call 2 of 2, not an acceptance review. The budget ending is not approval.

Task 1. The checkout HEAD is 0ad2c8e567d9612524583a49da4e10b0f938a872. The merge-base with origin/main is c933f2a47, which is also origin/main. The diff from the merge-base to HEAD lists exactly one file, module-0.7-what-is-networking.md. The page sha256 at HEAD is f51f9b946488078bce3e2d156bf930a7a76e84f9966e793cae7e25344939216a. The page is 798 lines. I read all of it at the pinned head.

B1: CLOSED. I grepped the first use of each term, with the line where it is explained:
- firewall: line 71, defined inline.
- TCP: line 161, glossed as an ordered byte stream.
- ICMP: line 187, expanded and glossed. Line 187 is inside a 'Check your prediction' details block; ping and ICMP are explained again at lines 279 and 281.
- reverse proxy: line 173, glossed as receives requests and forwards them to a server.
- NXDOMAIN: line 231, defined as a resolver's answer that the queried name does not exist.
- virtual host: line 231, defined as one IP serving several named sites, selected by the hostname in the request. It adds that a direct-IP request may reach a default site or intermediary.
- HEAD: line 310, explained as a request for headers without the body.
- authoritative DNS: line 454, glossed as the records held by the servers responsible for the zone. It appears again at line 635, after the gloss.
A beginner can follow all of these. Small residuals, all NON-BLOCKING: 'zone' and 'search suffix' (line 239) are unexplained at first use, 'UDP' (line 161) is unglossed, and the Pod-IP/namespace vocabulary in the Kubernetes transfer is thin.

B2: PARTLY closed. The worked mapping at lines 740-748 is correct and consistent with the page's own earlier teaching. Cluster DNS names do follow the Service-name.namespace.svc.cluster-domain pattern. Service port 80 mapping to target port 8080 is supported by the Kubernetes 1.35 Service page: 'A Service can map any incoming port to a targetPort'. The selector wording ('a selected Pod') is consistent with 'usually determined by a selector'. The selector residual is therefore acceptable: nothing false is asserted, and a missing selector would not yield a 500. The solution is correct but its 'check next' advice is generic, and 'gateway logs' never appears in the scenario.
The outcome (line 23) and the success criterion (line 763) still name Pods, Pod IPs and the API server and 6443. The worked mapping covers only a Service, and no practice, quiz item or solution touches Pod IPs or 6443. The learner is asked to 'Explain how ... Pod IPs, and API server port 6443 map ...' with no worked path. This is the one remaining blocker; see the finding.

B3: CLOSED. Each of the four incidents has two tiers before its diagnosis. Tier 1 asks which evidence or protocol each probe tests. Tier 2 narrows the conclusion with a leading question. Neither gives the diagnosis away. Both match the transcripts: Incident A is NXDOMAIN plus a direct-IP 200, B is ping loss plus an HTTPS 200, C is a 404 with a Server header, D is a port-80 refusal plus ping replies. The reveal labels now read 'Observed Layer'. Note the incident prompts (for example line 617) still ask 'Which layer has failed', which sits awkwardly with line 602's instruction not to invent a single failing layer; this is NON-BLOCKING.

B4: CLOSED for the named passages. Removed: the comment-on-itself paragraph, the promised 'decision framework' checklist, the later-modules recap, the 'one thing at a time' paragraph, and the Kubernetes-events claim. Residual repetition remains, because the 'ping/404/one response is not proof' points recur in about 10 places, and lines 138-146, 195-197 and 345-347 are untouched. This is NON-BLOCKING, not something that stops a beginner following the page, but it caps the concision score.

Dangling-reference check. I grepped for 'see above', 'checklist', 'decision framework', 'below', 'earlier', 'previous section', anchors of the form '#...)', 'restaurant', and the first-use lines for the terms above. No dangling references. The Did You Know items 1-4, quiz Q1-Q7 and tasks 1-9 are still numbered consistently. The 'restaurant analogy' is still defined at line 43. One new defect: the firewall definition at line 71 was spliced into a paragraph whose motivating sentence was cut, so the 'Describe the path in pieces' sentence now reads abruptly (P3, NON-BLOCKING).

NB status:
- NB1: closed. Q2 and Q4 stems now match their answers.
- NB2: closed. 'An HTTP responder' wording is used throughout.
- NB3: closed. The RFC 6335 causal sentence is cut, and 'the configured port can differ' is supported (see Source checks).
- NB4: closed. The Kubernetes-events claim is removed.
- NB5: mostly closed. The 'Observed Layer' label is used throughout; the prompt wording at line 617 remains slightly in tension.
- NB6: closed. The Sources list now includes the Kubernetes controlling-access page, the nslookup manual, Apache virtual hosts, RFC 9499, RFC 792, NIST firewall, MDN proxy and MDN HEAD. Every claim I checked has an entry in the list.
- NB7: closed. A cleanup step and a `host` fallback were added; the fallback ends in 'otherwise skip', which is acceptable.

The three self-declared residuals:
(a) The dashboard scenario is explicitly labelled 'Hypothetical scenario'. The page states the failure as a stipulated fact of the scenario, not as a general causal rule. The scenario is a little muddled, because a reverse proxy would normally front 443. This is acceptable and non-blocking.
(b) 'The configured port can differ' is not unsourced. The Kubernetes 1.35 controlling-access page, which I opened, says the API server listens on 6443 by default, 'the port can be changed with --secure-port', and it is in the Sources list. Closed.
(c) The selector assumption is acceptable, as above.
The missing firewall row in the PR's source table is not a page defect. The page's firewall gloss is consistent with NIST's glossary. The first definition on the NIST page I opened reads 'A gateway that limits access between networks...', while the page's wording ('device or program ... between hosts or networks') corresponds to another NIST entry that I could not display. That is partly UNKNOWN, with low risk.

Source checks, pages actually opened:
- RFC 9499: NXDOMAIN means 'the domain name referenced in the query does not exist'. Supported.
- Apache name-based vhosts: many hosts share one IP, the hostname selects the host, and the first-listed vhost is the default. Supported.
- Kubernetes 1.35 Service page: port/targetPort and selector supported. The DNS-name section was beyond the portion I could read; the cluster DNS name format is covered by the DNS page already in the Sources list, which I did not open.
- Kubernetes 1.35 controlling-access page: 6443 and `--secure-port`. Supported.
- NIST firewall glossary: partly supported, see above.
- MDN Proxy server: reverse proxy takes requests and forwards them to servers. Supported.
- RFC 9293: 'reliable, in-order, byte-stream service'. Supported.
- curl manual: `-I` fetches the headers only using HEAD. Supported.
- Not opened: RFC 792, the MDN HEAD page, the ping manual and the nslookup manual. The ICMP, HEAD and nslookup statements are standard and consistent with the supporting pages I did open, but I did not verify them against those pages, so they are UNKNOWN.
- Harmless commands in a temp dir: `nslookup` failed with a local-resolver communications error, and `curl -I` to example.com returned no output. This host has no usable DNS or egress, so no command output was obtained to confirm or refute the page's output claims. All of those claims are UNKNOWN from execution and rest on the documents.

Scores from a full read. D 33/40: D2 vocabulary is now 4, hints are fixed, and concision is 4 (repetition remains). The outcome/practice-alignment dimension is 3, below the floor of 4, caused only by the open B2 residual. L 21/25: L4 hints are now 4, and all L dimensions are at or above their floors. D is below its floor, so the page is not accepted.

BLOCKING: one item, the outcome and success criterion exceeding the practice (see the finding). NON-BLOCKING: the unexplained zone/search suffix/UDP; the leftover repetition; the abrupt firewall splice; the incident prompt wording at line 617; 'gateway logs' in the Kubernetes answer.

Provenance: reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5), Anthropic family, run in Claude Code (Agent SDK) with the sources MCP present but not used for this prose review; author family is OpenAI, so the review is cross-family. The sources MCP was not needed for this English-prose and Kubernetes-fact page. Checks performed: the git diff and HEAD checks, a full read, greps, and the web fetches named above. Supplied and not independently reproduced: the PR body, the NIST row removal, the author's residual descriptions, and the call-1 ledger and scores.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B2-residual-outcome-practice-gap",
  "title": "Success criterion (and outcome) names Pod IPs and API server 6443, which no worked item or practice covers",
  "body": "The new Kubernetes transfer example is correct and teaches Service port 80 -> targetPort 8080 with the cluster DNS name web.shop.svc.cluster.local. But the outcome at line 23 ('Evaluate how beginner networking ideas show up in Kubernetes Services, Pods, and the Kubernetes 1.35 API server') and the closing success criterion at line 763 still require the learner to explain Pod IPs and API server port 6443. Nothing in the practice, the quiz, the diagnostic incidents or the worked answer exercises Pod IPs or 6443; they only appear as one-line statements in the prose, a table row and a Did You Know item. A learner cannot show they met that criterion from anything the exercise gives them.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.7-what-is-networking.md",
   "start_line": 763,
   "end_line": 763,
   "claim_type": "present"
  },
  "verbatim": "- [ ] Explain how Kubernetes Service names, Pod IPs, and API server port 6443 map to DNS, address, port, and protocol response.",
  "why_wrong": "The frozen B2 ledger required either real practice for the Kubernetes outcome or a downgraded outcome and criterion. The worked mapping covers only the Service half, so the stated assessed outcome still exceeds what the module teaches and checks, and a beginner is told they can do something the page never had them do.",
  "smallest_fix": "Either narrow line 763 to what the worked item practices (for example, 'Identify the name, address, Service port, target port and response in a Kubernetes Service request') and soften the line 23 outcome to Services and the API server port, or add one short sub-question to the Kubernetes transfer that has the learner map a Pod IP and the API server address on 6443 to name, address, port and response, with a solution line.",
  "sources": [
   "https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/service/",
   "https://v1-35.docs.kubernetes.io/docs/concepts/security/controlling-access/"
  ]
 }
]
```

## kd-wp-07-r3: round 3, CTO-granted pinned verification of the outcome/criterion alignment fix only

- reviewed head: `bf63061f0bee350d68b14c2ac4e186968ab89e10`
- run nonce: `52783e9a234d45d3b6423dde31031d14`
- verdict: `correct` (confidence 0.9)

### Explanation (verbatim)

Pinned verification round 3 (not acceptance). Task 1: HEAD is bf63061f0bee350d68b14c2ac4e186968ab89e10 and the worktree is clean. The delta from 0ad2c8e56 is exactly one commit (bf63061f0), one file (module-0.7-what-is-networking.md), +2/-2, at lines 23 and 763. Page sha256 is 203fb164064ebe6f066bdf07798fee3db3d84fc36d002cb5f2460c9a366a7f5a. Task 2: the B2 residual is CLOSED. Outcome (line 23) and success criterion (line 763) both now read: Identify the name, address, ports, and protocol response in a Kubernetes Service example. The worked Kubernetes transfer item (lines 740-746) asks the learner to identify the name, address, Service port, target port and response in a Service example, and its worked answer supplies web.shop.svc.cluster.local, 10.96.0.10, port 80 to 8080 and the 500 response. Identify is an assessable verb and the practice covers every element it names. Grep hits for Pod, 6443 and API server, none a learning-goal promise: line 31 intro prose; lines 50, 52, 140, 144 teaching prose; line 169 port table row; lines 175, 178, 197 teaching on Service port mapping and the API port; line 237 DNS teaching; lines 351, 359, 364 limits and anti-pattern prose; line 382 troubleshooting table row; line 384 sentence on applying the same logic; line 395 a did-you-know style fact; line 440 a non-Kubernetes quiz question mentioning an API server; lines 742-746 the Service-only worked item; lines 773-775 and 787 source links. No outcome, quiz, task, summary or next-module text promises practice with Pod IPs, port 6443 or the API server. The Next Module text (line 798) points to 0.8 Servers and SSH and states no 0.7 outcome. Task 3: front matter has no description or outcomes field. The zero-to-terminal index row for 0.7 says IPs, ports, DNS and how computers talk to each other, and module 0.6 next-link says to understand how computers talk to each other across networks. The shorter outcome drops nothing those promise and contradicts nothing in the page. Scores: I did not re-judge the D and L dimensions from a full read of the whole page, because this round is scope-pinned to the 2-line delta and I read only the header, the delta, the Kubernetes practice and success criteria, and grep context. I therefore give no D or L numbers and invent none. BLOCKING: none. NON-BLOCKING: none introduced by the delta. Provenance: reviewer Claude Sonnet 5.5 (claude-sonnet-5-5), Anthropic family, Claude Code harness with shell and file tools; author is OpenAI Codex gpt-6.1-terra, so the review is cross-family. Checks I performed: git rev-parse, git status, git diff --stat and -U0 for the delta, sha256sum, grep of the page, and reads of the front matter, outcomes, practice, success criteria, and neighbouring-module next text. Supplied and not re-verified: the call 2 closures of B1, B3, B4, NB1-NB7 and the three accepted residuals. Limits: I ran no build or link check and did no full-page read.

### Findings (verbatim JSON)

```json
[]
```
