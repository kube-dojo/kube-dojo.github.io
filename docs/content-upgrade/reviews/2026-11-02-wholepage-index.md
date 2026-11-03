# Reviews of prerequisites/zero-to-terminal/index.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The page is a navigation hub without a lab of its own.

## kd-wp-index-r1: call 1 of 2, whole-page review

- reviewed head: `c933f2a47f6bc1b272291b241bb0595a19110dac`
- run nonce: `432cccc6146e465ca7f24f49fae63a23`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/zero-to-terminal/index.md gives d027176eef7c73d76c21f381afa3a4d487df7c9871dfa5a9b2ef9c68f96cc807, matching the stated digest. git rev-parse HEAD gives c933f2a47f6bc1b272291b241bb0595a19110dac, as stated.

PAGE TYPE: navigation hub with no lab of its own (seed claim C704a586). Under the contract it needs audience, route, link and setup checks, and may omit theory, quizzes and labs. L1-L5 are not applicable; lab_execution is not applicable.

SCORES (the D1-D8 labels were not in the files I read; I assumed this order: D1 audience fit, D2 outcomes/scope, D3 explanation/under-explanation, D4 outcome-to-practice alignment/route, D5 factual accuracy/sources, D6 prose/concision, D7 safety/consistency, D8 structure/engagement):
- D1 = 4: beginner audience, fallback for learners without an environment, and the optional terminal preview are clearly stated.
- D2 = 4: outcomes match what modules 0.1-0.11 teach.
- D3 = 3: line 14 states setup requirements in terms a beginner cannot act on, and the Windows/WSL rule is vague (findings 1 and 2).
- D4 = 4: route, links, module table and aggregate arithmetic are correct; Kubernetes Basics is unlinked (non-blocking).
- D5 = 4: all checkable claims hold; one weak source (non-blocking).
- D6 = 3: time range appears twice and route advice is repeated (finding 3); generic filler in tips and closing lines (non-blocking).
- D7 = 4: authorized-environment, billing and do-not-provision framing is safe; no unsafe sudo, credential or exposure advice found.
- D8 = 4: structure is clear.
TOTAL = 30/40. The total floor of 33 is missed, and the all-scores-at-least-4 floor is missed on D3 and D6.

DISPOSITION: revise, confidence 0.8.

SOURCE_STATUS: supported for the claims I judged. I judged about 25 distinct material claims across the 124-claim seed; I did not independently re-judge every low-risk title/link row individually.
- Supported: the 11 module titles, relative links and time ranges against each module header (all 11 match); the 940-1220 min range and the 15 h 40 min-20 h 20 min conversions (6x120+5x100=1220; 940 likewise); Module 0.2 anchors #opening-the-terminal-and-reading-the-prompt and #hands-on-exercise-your-first-terminal-session exist; Cloud Native 101, Kubernetes Basics and Linux targets exist and the route is consistent with prerequisites/index.md; Module 0.11 contains the cloud-path billing, loopback binding and Docker Engine 28.0.0 caveat; the kitchen analogy is used in 0.1, 0.3, 0.4, 0.5, 0.7, 0.8, 0.10 and 0.11; Killercoda labs in 0.3, 0.8 and 0.9 justify the browser requirement.
- Partly supported: 'CPUs can have many cores' is backed only by a vendor press release (non-blocking).
- Unsupported: none. Unknown: none.

BLOCKING FINDINGS (each fits a small PR):
1. Line 14: the WSL instruction is vague and not tied to the modules that need it. The hub says 'Windows learners should use the modules' WSL guidance where required'. WSL/Windows guidance appears only in 0.2 and 0.3 (0.1, 0.10 and 0.11 mention it in passing); Modules 0.4-0.9 give none yet use Unix commands (mkdir, nano, git, ssh, apt). 0.2 also offers a PowerShell branch, so a Windows learner can finish 0.2 on PowerShell and fail silently from 0.4 on.
2. Line 14: the setup requirements use unexplained jargon and give a self-learner no way to act. 'Docker Engine 28.0.0 or newer', 'local context', 'authorized, preconfigured' and 'disposable VM' are used with no gloss; the only help offered is 'ask your instructor or lab owner', but the stated audience includes career-switchers who have neither. The page never says whether a learner's own laptop counts as 'authorized'.
3. Lines 120-122 (also 102): BLOAT through repetition. The 'Time Investment' section restates line 80's aggregate range and the 'planning estimate, not measured' caveat. Line 102 repeats lines 98-100.

NON-BLOCKING FINDINGS:
- Line 60: the generic claim 'CPUs can have many cores' is sourced to an Apple M4 Pro/M4 Max press release. It verifies ('up to 14-core CPU', 'up to 16-core CPU') but is promotional; a neutral reference or no link would be better. The caveat paragraph is also one dense block.
- Lines 37, 96 and 111: 'Kubernetes Basics' is named in the route text and diagram but not linked, although ../kubernetes-basics/ exists.
- Lines 84-90 and 126: generic study tips ('Take breaks', 'Go at your own pace', 'Re-read if needed') and the closing 'Start with one action' say nothing track-specific. Line 41's 'the existing terminal opening and prompt guide' uses maintenance voice that means nothing to a learner.

OMITTED-CLAIM DISCOVERY: no unledgered material factual claim found. The WSL claim (C122313e) is ledgered but thinly supported (only 0.2 and 0.3 provide it; finding 1). The capstone needs Docker, which is not taught until Cloud Native 101 after the track; the hub does not say the capstone uses Docker commands. That is partly covered by finding 2 and is otherwise a Module 0.11 scope question, not a hub defect.

URLS ACTUALLY OPENED: https://www.apple.com/newsroom/2024/10/apple-introduces-m4-pro-and-m4-max/ (supports up-to-14/16-core CPUs). https://docs.docker.com/engine/release-notes/28/ (read the first 100000 of 108792 characters; 28.0.0 'Port publishing in bridge networks' security fixes found, consistent with the 28.0.0 floor in 0.11). Seed claims were not re-fetched.

VERIFIED BY ME vs SUPPLIED: verified by me: file digest and HEAD; the full 126-line page; module header times and arithmetic; link and anchor existence; the prerequisites/index.md route; the WSL/Windows grep across 0.1-0.11; analogy usage across modules; the Docker/loopback/billing text in 0.11; and the two URLs above. Taken as supplied and not re-judged: seed-level snapshot digests and prior review dispositions (treated as void history).

PROVENANCE: reviewer is Claude Code, actual model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), harness Claude Agent SDK CLI with the read-only checkout. Review kind: whole-page review, call 1 of 2.

LIMITS: no commands were executed; there are no labs on this page; the Docker release notes were only partly read; the D1-D8 labels were assumed.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1-wsl-routing",
  "title": "Hub's Windows/WSL instruction is vague and not tied to the modules that need it",
  "body": "The hub is the route-level place to tell Windows learners which shell to use. It says only 'where required'. WSL/Windows guidance exists in Modules 0.2 and 0.3 (0.1, 0.10 and 0.11 mention it in passing); Modules 0.4-0.9 give none and use Unix commands (mkdir, nano, git, ssh, apt). Module 0.2 also offers a PowerShell branch, so a Windows learner can finish 0.2 on PowerShell and silently break from 0.4 on. Module 0.2 itself says WSL is recommended for the rest of the curriculum.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/index.md",
   "start_line": 14,
   "end_line": 14,
   "claim_type": "present"
  },
  "verbatim": "Windows learners should use the modules' WSL guidance where required",
  "why_wrong": "Under-explanation: a beginner on Windows is not told that a Linux-style shell (WSL Ubuntu) is needed from Module 0.3 through the capstone, or where to set it up. Modules 0.4-0.9 contain no WSL guidance to follow, so 'where required' points at nothing.",
  "smallest_fix": "Replace with one concrete sentence: Windows learners should set up a WSL Ubuntu shell (Module 0.2 shows how) and use it for Modules 0.3-0.11. macOS and Linux learners use the built-in terminal.",
  "sources": [
   "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "src/content/docs/prerequisites/zero-to-terminal/module-0.3-first-commands.md"
  ]
 },
 {
  "id": "F2-setup-jargon",
  "title": "Capstone environment requirements stated in unexplained jargon, with no self-learner path",
  "body": "For an absolute-beginner hub, the paragraph uses 'Docker Engine 28.0.0 or newer', 'local context', 'authorized, preconfigured' and 'disposable VM' with no gloss, and its only help is to ask an instructor or lab owner. The hub's own audience list includes career-switchers and curious students who may have neither. It never says whether a learner's own laptop counts as 'authorized'. The version floor is supported (Docker 28.0.0 release notes and Module 0.11); the problem is that the reader cannot act on it.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/index.md",
   "start_line": 14,
   "end_line": 14,
   "claim_type": "present"
  },
  "verbatim": "an authorized, preconfigured local Docker Engine 28.0.0 or newer with a local context, or an authorized cloud account and disposable VM",
  "why_wrong": "Terms are used before explanation (UNDER-EXPLANATION is blocking per the review contract). A beginner cannot tell what 'Docker Engine' or a 'context' is, why a version matters, or what to do without an instructor.",
  "smallest_fix": "Add short glosses: Docker Engine is the program that runs containers; a 'local context' means Docker is talking to your own machine; a 'disposable VM' is a throwaway cloud computer you delete afterward. State that the learner's own personal computer counts as authorized, and that Module 0.11 explains both paths before they commit. Keep reading-only as the fallback.",
  "sources": [
   "https://docs.docker.com/engine/release-notes/28/",
   "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md"
  ]
 },
 {
  "id": "F3-repeated-time-and-route",
  "title": "Time range and route advice are stated twice",
  "body": "The aggregate planning range and the 'not measured' caveat are given at the end of the Modules section (line 80) and again in a separate 'Time Investment' section. Line 102 also repeats the advice of lines 98-100 (default to Cloud Native 101, Linux optional).",
  "priority": "P3",
  "confidence": 0.8,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/index.md",
   "start_line": 120,
   "end_line": 122,
   "claim_type": "present"
  },
  "verbatim": "It is an unmeasured estimate, not a completion promise; setup, reading, and practice can take longer.",
  "why_wrong": "BLOAT (repetition within the page): the reader loses nothing a stated outcome needs if either copy is removed.",
  "smallest_fix": "Delete the 'Time Investment' section (lines 120-122) and its preceding rule, keeping line 80. Delete line 102 ('If you are unsure where to go...').",
  "sources": [
   "none"
  ]
 },
 {
  "id": "F4-apple-source",
  "title": "Generic CPU-core claim sourced to a vendor press release",
  "body": "'CPUs can have many cores' is a generic fact linked to an Apple M4 Pro/M4 Max announcement. I opened it: it does say 'up to 14-core CPU' and 'up to 16-core CPU', so the claim is true, but the source is promotional and narrow. Non-blocking.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/index.md",
   "start_line": 60,
   "end_line": 60,
   "claim_type": "present"
  },
  "verbatim": "CPUs [can have many cores](https://www.apple.com/newsroom/2024/10/apple-introduces-m4-pro-and-m4-max/), not just one chef.",
  "why_wrong": "A vendor press release is a weak, product-specific source for a general concept in a vendor-neutral beginner hub.",
  "smallest_fix": "Link a neutral reference on multicore CPUs (or drop the link; the claim is common knowledge).",
  "sources": [
   "https://www.apple.com/newsroom/2024/10/apple-introduces-m4-pro-and-m4-max/"
  ]
 },
 {
  "id": "F5-k8s-unlinked",
  "title": "Kubernetes Basics named in the route but not linked",
  "body": "Cloud Native 101 and Linux are linked, but Kubernetes Basics (a real section at ../kubernetes-basics/) is only named in the text and the diagram. Non-blocking.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/index.md",
   "start_line": 96,
   "end_line": 96,
   "claim_type": "present"
  },
  "verbatim": "continue straight into Cloud Native 101 and then Kubernetes Basics—the linear spine from terminal skills to hands-on cluster work.",
  "why_wrong": "A route page should let the reader click each named stage; the route cannot be followed from the hub for the second stage.",
  "smallest_fix": "Link 'Kubernetes Basics' to ../kubernetes-basics/.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-index-r2: call 2 of 2, delta review

- reviewed head: `8ac611dc54ecb185eb3fe36c5b1676de36cdc458`
- run nonce: `0dc60d30f8264d4c9b0e3a9d705929f1`
- verdict: `correct` (confidence 0.88)

### Explanation (verbatim)

Delta review, call 2 of 2. This is not an acceptance sign-off and not a review of the whole PR.

Task 1. HEAD is 8ac611dc54ecb185eb3fe36c5b1676de36cdc458. The diff against c933f2a47 touches one file (the index page), +6/-12. The page sha256 at HEAD is 9a18867efb6da41757d7f4b4f2dbcc4de66e19a0ef9dcdcb45e53f97a366c54c. I read the whole page at HEAD.

F1 is closed.
- The claim 'Modules 0.3–0.11 use Unix-style commands' holds.
  - Unix-style command counts by module: 0.3=65, 0.4=51, 0.5=25, 0.6=60, 0.7=22, 0.8=28, 0.9=26, 0.10=6, 0.11=20.
  - Module 0.3 (line 45) says Windows learners should use WSL because 'native PowerShell has different commands'.
  - Module 0.10 (line 451) says 'Bash-compatible terminal, including an authorized WSL'.
  - Module 0.11 (line 124) says 'on Windows, use an authorized WSL or lab shell rather than pasting them into PowerShell'.
- 0.3 is the right first module.
  - Module 0.1 gives a bash and a PowerShell branch for the CPU, RAM and disk commands (lines 117-160) and only mentions WSL conceptually.
  - Module 0.2 offers bash, zsh, WSL and PowerShell branches. Its line 87 says 'WSL is recommended for the rest of this curriculum when later modules expect Unix command names'.
- The page's description of 0.2 is accurate: it introduces WSL and also has a PowerShell option for that module only.
- A Windows learner can act on the instruction.
  - It gives the shell to set up, an install-guide link, and the module range where it is needed.
  - Module 0.2 (lines 89-92) shows 'wsl --install', and the page ties WSL to 0.3 onward.
  - Minor non-blocking gap: the page never says 'before Module 0.3'. The 0.3–0.11 range implies it.

F2 is closed.
- The rewritten capstone paragraph defines Docker Engine in plain words ('runs containers').
- It says 'such as your own laptop' counts as a computer you are allowed to use. This is consistent with Module 0.11 line 56 ('practice on your own machine') and quiz item 5 (line 460, 'on your laptop').
- It keeps the safety framing: authorized cloud account, a temporary machine you can delete, billing may apply, and 'the track does not set these up for you'.
- The reading-only fallback is preserved ('read the examples without starting resources').
- The 28.0.0 floor matches Module 0.11 lines 124 and 133 ('Server Engine is at least 28.0.0'). The page also correctly says the module teaches the check that Docker is connected to the local machine.

F3 is closed.
- The Time Investment section is gone, so the aggregate range and the 'not measured' caveat each appear once (line 82).
- The duplicated closing route sentence is also removed.
- A grep for 'time-investment' across src returned nothing, so no anchor or link pointed at the removed heading.
- The aggregate range is correct.
  - Header minutes sum to 940 at the low end and 1220 at the high end, matching 15h40m–20h20m.
  - Headers: 0.1 90–120, 0.2 90–120, 0.3 80–100, 0.4 90–120, 0.5 80–100, 0.6 90–120, 0.7 90–120, 0.8 80–100, 0.9 80–100, 0.10 80–100, 0.11 90–120.
  - The page table agrees with these.

F4 and F5 are closed. The Apple promotional link is removed and the cores claim is now unsourced generic prose. Kubernetes Basics is linked. The 'existing' maintenance wording is gone.

Link checks. The target ../kubernetes-basics/index.md exists, and so do cloud-native-101 and linux. Module 0.2 has the headings 'Opening the Terminal and Reading the Prompt' and 'Hands-On Exercise: Your First Terminal Session', so both anchors resolve. Module 0.11 exists. The only heading removed was Time Investment, which nothing linked to.

New-claim verification. I opened https://learn.microsoft.com/en-us/windows/wsl/install and https://docs.docker.com/engine/.
- Microsoft: 'wsl --install' needs administrator PowerShell, then a restart, and installs Ubuntu by default. It requires Windows 10 build 19041 or newer, or Windows 11.
- Docker: Docker Engine is a client-server application with a dockerd daemon that creates and manages containers, images, networks and volumes.
- Both support the page's wording.

New defects. None blocking. Non-blocking observations:
- Modules 0.3, 0.8 and 0.9 use browser Killercoda Ubuntu labs, so WSL strictly matters for reading and local practice, not for those labs. The page's unconditional wording slightly over-requires but is safe.
- Module 0.11 says 'preconfigured' Docker and gives no install guidance, so a self-learner without Docker falls back to the reading-only path. This is acceptable and stated.

Residuals the author declared: generic 'How to Use This Track' tips, the closing line 'Start with one action', and the dense analogy caveat paragraph. All are non-blocking and I did not turn them into blockers.

Scores from a full read (labels I chose, since the call-1 labels were not supplied): D1 audience fit 5, D2 route and navigation 4, D3 setup and explanation sufficiency 4, D4 factual accuracy and sourcing 4, D5 safety and honesty framing 5, D6 concision 4, D7 consistency with module content 4, D8 links, anchors and structure 5. Total 35/40. Every dimension is at or above 4 and the total is at or above 33. L1-L5 and lab execution are not applicable. The only scaffolding costs: generic study tips and the closing line (D6), and the dense analogy paragraph.

BLOCKING: none. NON-BLOCKING: the Killercoda over-requirement, the missing 'before Module 0.3' phrasing, generic study tips and closing line, and the dense analogy paragraph.

Provenance: reviewer Claude (Anthropic) Sonnet 5.5, model id claude-sonnet-5-5, Claude Code harness with local read and grep tools, a web fetch and the sources MCP available. The author is OpenAI Codex gpt-6.1-terra, so this is outside the author's family. Checks I performed: HEAD, diff, sha256, module grep for commands and WSL/PowerShell, header time arithmetic, anchor and link existence, and the two URL fetches. I ran no tests or scripts. Limit: I did not read all of every module body, only the command, WSL and PowerShell content and the capstone setup text.

### Findings (verbatim JSON)

```json
[]
```
