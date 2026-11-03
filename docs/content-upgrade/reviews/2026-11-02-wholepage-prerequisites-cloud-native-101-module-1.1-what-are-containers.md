# Reviews of prerequisites/cloud-native-101/module-1.1-what-are-containers.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The Docker lab was not run by either reviewer. ONE EDIT to the otherwise verbatim text: a host filesystem path inside the call-1 reviewer's PROVENANCE sentence was shortened to the repository-relative `schemas/code-review-findings.v1.schema.json` (public repository files carry no host paths); nothing else was changed.

## kd-wp-cn11-r1: call 1 of 2, whole-page review

- reviewed head: `3887f4726afcabd0dc46dad695392de27c626489`
- run nonce: `0d69c1bb3cf74438a07cc33541992155`
- verdict: `incorrect` (confidence 0.85)

### Explanation (verbatim)

WHOLE-PAGE REVIEW, call 1 of 2. Page: src/content/docs/prerequisites/cloud-native-101/module-1.1-what-are-containers.md at 3887f4726afcabd0dc46dad695392de27c626489. DIGEST: `sha256sum` gives 58ef87b5564fc782aa9c56b690aa0c6f32a34ea783690a51e0aaf973be44678f, which matches the supplied digest. I read all 608 lines.

SCORES. I used generic D1-D8 labels, because docs/review-contract.md gives the floors but not per-dimension definitions. (D1 objectives, D2 accuracy, D3 explanation depth, D4 examples, D5 practice/assessment alignment, D6 concision/engagement, D7 structure/flow, D8 safety/currency.)
D1=4: the five outcomes are clear and in scope.
D2=4: the core model is sound, but there is one factual error (CPU limit and scheduling), one internal inconsistency (`best for production`) and one imprecise claim (gcr.io `read-only`).
D3=3: `volume` is used throughout and never explained, and `requests` is used without a definition.
D4=4: the vendor-neutral scenarios and diagrams are good, and hypotheticals are labelled.
D5=3: outcome 5 (Design a persistence plan) and outcome 4 (Evaluate image names/tags) have no practice task, only a quiz item or a prescribed answer. Hints are not tiered.
D6=2: heavy BLOAT. See finding KD-CN11-BLOAT.
D7=3: canned bridge sentences, a Patterns section that duplicates Common Mistakes, and the cards are misframed as predictions.
D8=4: nothing unsafe. Cleanup is careful, there is no sudo/credential/public exposure advice, and there are no forced removals.
Module TOTAL=27/40 (floor 33). Floors missed: D3, D5, D6 and D7 are below 4, and the total is below 33.
Lab scores: L1 task clarity=3, L2 command/expected-output correctness=3, L3 verification/feedback=3, L4 cleanup/safety=4, L5 outcome alignment=3. TOTAL=16/25 (floor 21); L1, L2, L3 and L5 are below 4.

DISPOSITION: revise. Confidence 0.85.

SOURCE_STATUS: partly supported. I judged about 20 material claims: 15 supported or consistent with sources I opened, 3 partly supported or imprecise, 1 unsupported, and 1 internal inconsistency.
- Supported: nginx 1.31 and 1.31.1 tags exist on Docker Hub (the `1.31.1` tag was last updated 2026-06-12 per the Hub API); layers are immutable and reused, and a container gets its own layer over the image layers.
- Imprecise: gcr.io. Google says writing to Container Registry is unavailable since 2025-03-18, and gcr.io-hosted Artifact Registry repos keep working, so `read-only; migrated` is loose.
- Unsupported: line 198, `A CPU limit affects scheduling and throttling behavior`. The Kubernetes docs say the scheduler uses requests, and CPU limits are enforced by throttling. One exception: a limit with no request is copied into the request.
- The Docker Desktop caveat and the shared-kernel claims were taken as general knowledge and corroborated by the cited Docker pages. I did not open the cgroup, namespace or OCI pages.
- The 2013 date, the Moby Dock mascot name and the shipping-container history are unverified from memory. They are trivia, not outcome-critical.

LAB_EXECUTION: not run. There is no Docker on this host, and nothing was executed. The one exception is that I ran the host command `ps aux | grep "sleep 3600"`, with no sleep process present, to test the self-match behaviour. It printed the grep process itself, with a match count of 3 lines, including the sandbox wrapper. The Docker commands were judged as prose and design only.

BLOCKING FINDINGS (details in `findings`):
1. KD-CN11-BLOAT (lines 32, 93, 97-99, 184, 301-303, 345, 355-369, 383-385, 389-392): substantial padding, repetition, duplication and off-topic text for an 80-110 minute beginner read.
2. KD-CN11-GREP-SELFMATCH (lines 487-496, 582-587): Task 3's `ps aux | grep` always matches its own grep line, so Card D's `The Mac prints nothing` is false and the learner is not told how to tell the grep line from the container's sleep.
3. KD-CN11-PERSISTENCE (lines 24, 349, 400, 549, 573-579): outcome 5 `Design a persistence plan` has no taught term (`volume` is never defined) and no worked or practised design task.
4. KD-CN11-CPU-LIMIT (line 198): a CPU limit is said to affect scheduling; the Kubernetes docs say requests drive scheduling and limits are enforced by throttling.
5. KD-CN11-LAB-REQS (lines 8-12, 454): the lab Requirements paragraph is dense and jargon-laden for an absolute beginner; the prerequisites line says the lab needs nothing beyond a terminal.

NON-BLOCKING:
- Line 292 labels `nginx:1.31.1` `best for production`, which contradicts line 287 (a digest is stronger and tags can move). Say `better; a digest is strongest`.
- Line 283 `read-only; migrated to Artifact Registry` is imprecise: say `Container Registry was shut down in 2025; gcr.io hostnames now served by Artifact Registry`.
- `docker stop` on a container whose PID 1 is `sleep` waits out the default 10 s grace period before SIGKILL, because PID 1 gets no default SIGTERM handler. This was taken from knowledge, and the Docker docs confirm only the SIGTERM-then-SIGKILL and 10 s default. Add `-t 1` or a one-line note so the learner does not think the lab hung. This links nicely to the PID 1 lesson.
- Lines 551-553: `frozen container-layer card` and the `Check your prediction` labels on the cards are odd jargon, and the checkbox sits mid-list.
- Card B (line 564): `Two of three servers cannot bind` with separate namespaces is only coherent under host networking. Say so, or note that `-p` host-port clashes are a different, more common failure.
- Lines 62 and 133-134: `10GB+` and `Minutes/Seconds` are unsourced rules of thumb. Hedge them as typical orders of magnitude.
- Lines 389-392 `Did You Know` bullets are low-value trivia, e.g. the mascot sentence `The mascot works because...`.
- No tiered hints exist for the lab, only solution notes.

OMITTED-CLAIM DISCOVERIES: The CPU-scheduling claim (line 198), `best for production` vs digest (292), gcr.io status (283) and the `Mac prints nothing` claim (582) were all absent from, or not caught by, the earlier source catalogs I saw. Those catalogs (the S009 entries) were frontmatter-only captures and are not semantic evidence for body claims. The earlier page-reviews.json history is VOID and was used as history only.

URLS ACTUALLY OPENED (via fetch): hub.docker.com/v2/repositories/library/nginx/tags?name=1.31 and .../tags/1.31.1; docs.cloud.google.com/artifact-registry/docs/transition/transition-from-gcr; kubernetes.io/docs/concepts/configuration/manage-resources-containers/; docs.docker.com/reference/cli/docker/container/stop/; docs.docker.com/get-started/docker-concepts/building-images/understanding-image-layers/. A fetch of docs.docker.com/engine/containers/start-containers-automatically/ was a connectivity probe only. I did not open the other Sources-list pages (man7 namespaces, kernel cgroup-v2, OCI, the other Docker CLI pages), so those claims are UNKNOWN-by-me, not passes.

PROVENANCE: reviewer Claude Sonnet 5.5 (claude-sonnet-5-5), Anthropic family, run via the Claude Agent SDK / Claude Code harness. Authors were OpenAI/Codex, so this is outside the author family. Review kind: whole-page review, call 1 of 2. Checks performed: the digest, a full page read, the web fetches above, and one local ps/grep test. Supplied and not independently relied on: the earlier review history and catalogs. LIMITS: the findings schema file at schemas/code-review-findings.v1.schema.json is not readable in this sandbox, so I followed the identical inline schema from the harness tool definition. Lab commands were not executed.

### Findings (verbatim JSON)

```json
[
 {
  "id": "KD-CN11-BLOAT",
  "title": "BLOAT: repeated, off-topic and duplicated passages in an 80-110 minute beginner read",
  "body": "Several paragraphs restate points already made, or carry meta text that teaches nothing. (a) Lines 95-99 make the same 'artifact instead of checklist' point three times: the paragraph 'This contract is especially useful...', then 'Another way to say this is...', then 'That machine-readable artifact also changes how teams investigate failures.' (b) Lines 301-303: 'Image naming also becomes a supply-chain control' and 'There is a social benefit too' re-argue the shared-artifact point again. (c) Line 32 tells the learner about the Kubernetes 1.35 version and the full-kubectl convention in a module with no kubectl command. (d) Canned bridge sentences at lines 93, 184 and 345 narrate the reading process ('Name the boundary before you read on...', 'Hold that prediction before the cgroup section...', 'Write the prediction down before you read the replacement rule below...'). (e) The 'Patterns & Anti-Patterns' section (lines 355-369) re-teaches the same points as the 'Common Mistakes' table (pets/exec, latest, root, limits, writable-layer state, 'not secure by default') and the earlier sections. (f) Lines 383-385 add 'The same vocabulary check helps during reviews of learning labs', which is off-topic. (g) The 'Did You Know' mascot bullet (line 392) is trivia with a non-sequitur justification.",
  "priority": "P1",
  "confidence": 0.85,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.1-what-are-containers.md",
   "start_line": 97,
   "end_line": 99,
   "claim_type": "present"
  },
  "verbatim": "Another way to say this is that containers move deployment knowledge from a human checklist into a machine-readable artifact.",
  "why_wrong": "The review contract treats padding, repetition, duplication across pages and off-topic background as equally blocking. The passages above give the learner nothing a stated outcome needs, so the page is much longer than its outcomes require. Cutting them also helps beginners finish the module.",
  "smallest_fix": "Cut or merge lines 97-99 into line 95; cut 301-303 (keep one sentence on digest/ownership); delete the line 32 kubectl/version sentence, the bridge sentences at 93/184/345, the 383-385 lab-review paragraph and the 392 mascot bullet; fold Patterns & Anti-Patterns into the Common Mistakes table or drop whichever points duplicate it (keep only 'build once, promote the same artifact' and 'one primary process' if not elsewhere).",
  "sources": [
   "none"
  ]
 },
 {
  "id": "KD-CN11-GREP-SELFMATCH",
  "title": "Task 3 and Card D: `ps aux | grep` matches itself, so 'The Mac prints nothing' is false",
  "body": "Task 3 asks the learner to run `ps aux | grep \"sleep 3600\"` on the host. The grep command line itself contains `sleep 3600`, so the pipeline always prints at least a line for the grep process, even when no container is running. I reproduced this: on this host, with no sleep process, it printed `grep sleep 3600`. On native Linux the learner sees two lines (the container's sleep and the grep), and the solution notes do not say which to look at. Card D then says 'The Mac prints nothing', which is wrong: on Docker Desktop the learner still sees a grep line. The learner is likely to read the grep line as the container's process, which undermines the point of Task 3 (the host PID differs from the in-container PID 1).",
  "priority": "P1",
  "confidence": 0.9,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.1-what-are-containers.md",
   "start_line": 489,
   "end_line": 491,
   "claim_type": "present"
  },
  "verbatim": "ps aux | grep \"sleep 3600\"",
  "why_wrong": "The command's output always contains its own grep process, so the Task 3 solution notes and Card D ('The Mac prints nothing', line 582) describe output the learner will not see. The lab then teaches the wrong observation on the key host-versus-container comparison.",
  "smallest_fix": "Use a bracket pattern, `ps aux | grep '[s]leep 3600'` (or `pgrep -af 'sleep 3600'`), and state in the solution notes how to read the PID column versus the in-container PID 1. Change Card D to 'The Mac shows no sleep 3600 process'.",
  "sources": [
   "local execution of ps aux | grep on the review host (grep self-match reproduced)"
  ]
 },
 {
  "id": "KD-CN11-PERSISTENCE",
  "title": "UNDER-EXPLANATION: persistence-plan outcome has no taught volume concept and no practice task",
  "body": "Outcome 5 says 'Design a simple persistence plan' (line 24) and a success criterion says 'You designed a simple persistence plan' (line 549), but the lab has no task that designs or tests one. The page repeatedly says 'Mount a volume' (line 400), 'a volume or an external store' (line 578) and 'mounted volume' (line 341) but never defines a volume, never distinguishes it from the writable layer beyond 'external', and never shows a bind mount or named volume. Line 349 does classify data by replacement tolerance, which is a good start, but the learner never practises a design: Card C and quiz item 6 tell them the answer is 'a volume' and Card C asks them to name 'a next action' only. Outcome 4 (Evaluate image names, registries and tags) is practised only by one quiz item about `latest`.",
  "priority": "P1",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.1-what-are-containers.md",
   "start_line": 549,
   "end_line": 549,
   "claim_type": "present"
  },
  "verbatim": "- [ ] You designed a simple persistence plan for data that must avoid losing state when a container is replaced.",
  "why_wrong": "An outcome and a success criterion promise a skill that the page neither fully teaches (volume is an undefined term) nor practises. Under the contract, untaught or unpractised outcomes must not pass.",
  "smallest_fix": "Add 3-5 sentences defining a volume (storage managed outside the container's writable layer; named volume vs bind mount, names only, with the next module owning commands) plus a small worked table: for an app with binaries, a cache, uploads and a DB file, say where each goes and why. Make the criterion a task: 'List three data items from a service you know and say where each lives'. Optionally add one image-reference evaluation exercise: spot the risk in three references.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "KD-CN11-CPU-LIMIT",
  "title": "Factual: CPU limits are said to affect scheduling",
  "body": "Line 198 says 'A CPU limit affects scheduling and throttling behavior.' Per the Kubernetes resource-management docs, the kube-scheduler uses resource requests to place a Pod; CPU limits are enforced at runtime by the kernel through CPU throttling. (The only scheduling effect of a limit is when no request is set and Kubernetes copies the limit into the request.) The sentence also uses 'requests' without defining them anywhere in this module.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.1-what-are-containers.md",
   "start_line": 198,
   "end_line": 198,
   "claim_type": "present"
  },
  "verbatim": "A CPU limit affects scheduling and throttling behavior.",
  "why_wrong": "It conflates requests (scheduling) with limits (runtime enforcement), a classic beginner misconception that the later Kubernetes modules will have to unlearn.",
  "smallest_fix": "Rewrite as: 'A request is what the scheduler uses to place the workload; a CPU limit is enforced by throttling; a memory limit is enforced by killing the container if it exceeds the limit.' Define 'request' in one clause.",
  "sources": [
   "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/"
  ]
 },
 {
  "id": "KD-CN11-LAB-REQS",
  "title": "Lab Requirements paragraph is dense and jargon-heavy for an absolute beginner; prerequisites contradict the lab",
  "body": "The prerequisites say 'none beyond a terminal for the optional Docker lab' (line 12), but the lab needs Docker installed, with no pointer to install it or a way to check it. The Requirements paragraph (line 454) then packs a Bash/WSL requirement, 'Docker in an authorized local context', 'Keep the same shell and context throughout', an ID-assignment explanation ('captures your successful creation result and clears it on failure; never populate it with an existing container's ID'), a name-collision rule and a Docker Desktop caveat into one block. The 'authorized local context' and 'ID assignment' language is unexplained for a Zero-to-Terminal route learner.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.1-what-are-containers.md",
   "start_line": 454,
   "end_line": 454,
   "claim_type": "present"
  },
  "verbatim": "Requirements: use a Bash-compatible terminal (WSL or the lab shell on Windows) and Docker in an authorized local context.",
  "why_wrong": "A beginner cannot tell what to check before starting (is Docker installed? what is a 'context'?), and the safety rules are stated abstractly rather than as steps. Lab clarity (L1) falls below the floor.",
  "smallest_fix": "Split into a short checklist: 'docker version works; you own this machine; the name isolation-test is unused (`docker ps -a` shows no such container)'. Add a one-line link to Docker install docs, correct the prerequisites line to mention Docker, and explain the ID variable in one plain sentence ('we store the new container's ID so cleanup only touches what this lab created').",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn11-r2: call 2 of 2, delta review

- reviewed head: `60d843a59cfeb113b293adb2ebe156b76659ea8c`
- run nonce: `c2c9a2c660bc4a6f93bff17b9ba6850d`
- verdict: `correct` (confidence 0.72)

### Explanation (verbatim)

DELTA REVIEW, call 2 of 2 (not acceptance of anything beyond the frozen ledger). Reviewer: Claude Code, model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author), toolful harness with file read, shell and web fetch; no Sources MCP calls were needed (no Ukrainian text in scope).

TASK 1. HEAD is 60d843a59cfeb113b293adb2ebe156b76659ea8c. The diff against 3887f4726 touches one file, the module page: 71 added, 49 removed lines. Page sha256 at HEAD is c6041449aeefc71eb8af982b57c2af9997df565f9d71f94711801f389ac5f354, which matches the expected value. Word count went from 8059 to 7580 (about 6% shorter).

THE FIVE BLOCKING FINDINGS.
1. KD-CN11-GREP-SELFMATCH: CLOSED. I ran the same `ps aux | grep` pipeline on this Linux host. It returned a `grep sleep 3600` line (the grep matching itself) plus the shell wrapper line. That confirms the self-match. Task 3's notes now say the output includes the grep line and must not be mistaken for sleep, and tell the learner to find the separate `sleep 3600` line and read its PID in column 2. They also say Docker Desktop on macOS or Windows may not show the container process because the Linux kernel is inside a VM. Card D now says the grep line shows but no separate sleep process, so 'prints nothing' is gone. The task notes and Card D agree. Weakness (non-blocking): the page never says in words that the grep line reads 'grep sleep 3600' versus a bare 'sleep 3600'.
2. KD-CN11-CPU-LIMIT: CLOSED. The corrected sentence says a request is what the scheduler uses to pick a node, a CPU limit is enforced by throttling, and a limit with no request or admission default is copied into the request. The Kubernetes manage-resources page I opened says: the kube-scheduler uses requests to place the Pod; 'cpu limits are enforced by CPU throttling'; and 'copies the limit you specified and uses it as the requested value' when no request and no admission default exist. The memory sentence ('may be killed under memory pressure') matches the page's 'reactive' wording.
3. KD-CN11-PERSISTENCE: CLOSED. Before use the page now defines a Docker volume (storage managed by Docker outside the writable layer) and a bind mount (host file or directory mounted into the container). Both match the Docker volumes page ('persistent data stores for containers, created and managed by Docker') and the bind-mounts page ('a file or directory on the host machine is mounted from the host into a container'). A four-row worked table covers binaries, cache, uploads and the database file. Task 6 is a practice task with two tiered hints and an example answer. The success criterion was reworded to 'listed three data items and chose where each lives', and outcome 5 ('Design a simple persistence plan') now matches what is taught and practised. Residual (non-blocking): nothing tells the learner that a bind mount is writable from inside the container, so the host files can be changed; the Docker bind-mounts page flags this as a caveat.
4. KD-CN11-LAB-REQS: CLOSED, with residuals. The prerequisites line now reads 'no prior container knowledge. The optional lab needs Docker and a Bash-compatible terminal.' The dense Requirements paragraph became three bullets with an install link (https://docs.docker.com/get-docker/, which resolves to the Docker install page) plus one plain paragraph. The prerequisites line, the bullets and the steps agree. Residuals (non-blocking): 'Docker context', 'WSL' and 'the ID variable' are still unexplained jargon for an absolute beginner; 'choose a different unused name below' does not say that the name is the isolation_name variable in Task 1; and the page never says outright that Task 6 and Cards A to D need no Docker, so the read-only path is only implicit (the lab is called optional and every task has solution notes).
5. KD-CN11-BLOAT: CLOSED, borderline. Every passage the ledger named is gone. Removed: the 'Name the boundary' bridge, the two machine-readable-artifact paragraphs, the 'Hold that prediction' and 'Write the prediction down' bridges, the supply-chain and social-benefit image-naming paragraphs, three of the four Patterns paragraphs (the immutable-artifacts pattern, the one-process pattern, and the container-like-VM anti-pattern), the defaults and Linux-knowledge anti-patterns, two further Patterns paragraphs (the scheduler-multiplication and the lab-vocabulary-check ones), and the Moby Dock trivia. Patterns now holds two short patterns, so it no longer duplicates Common Mistakes. Nothing the lesson needs was lost: explanations, the worked examples, the quiz, cleanup, targeted removal with no forced delete, and no sudo or public-exposure advice all remain. Greps: no fragment links into this page anywhere in src (all inbound links are plain paths: the Cloud Native 101 index, the prerequisites index, Zero to Terminal pages, and the uk mirrors), so no removed heading breaks a link. 'above' appears only in Task 6 Hint 2 ('the table above'), which resolves to the new storage table; there are no 'earlier', 'as we saw' or 'the following' hits. Remaining mild padding (the VM-versus-container decision text at about lines 139-143 and 373-381) is non-blocking. The 6% trim is modest, but the reader load of about 7.6k words is still plausible for 80-110 minutes of reading plus a lab.

NON-BLOCKING ITEMS. (a) The `best for production` label: closed; the line now reads 'Patch version tag (better; a digest is stronger)', consistent with the digest statement. (b) The gcr.io wording: closed; 'Google shut down Container Registry on March 18, 2025; Artifact Registry can host gcr.io repositories' matches the Google transition page (effective March 18, 2025; gcr.io repositories hosted on Artifact Registry are not affected). The sentence sits slightly awkwardly between a paragraph and its code block. (c) `docker stop` grace period: closed; Task 4 now says stopping may take the default 10 seconds for a Linux container, which matches the docker container stop page (SIGTERM, 10 s Linux default, then SIGKILL). It does not say why a bare `sleep` as PID 1 waits out the timeout; fine. (d) Card labels: closed; 'Answer' replaced 'Check your prediction' on the cards and 'frozen container-layer card' was removed. (e) Card B host networking: closed; the card now says the containers share the host network, which is coherent with the Docker host-network page ('the container shares the host's networking namespace'; published ports are discarded). (f) Hedged size and startup comparisons: closed; the table rows say 'Often gigabytes', 'Often megabytes; varies by image', and 'Often faster'. (g) Unverified trivia and general-knowledge claims: partly open; the 2013 date and the Alpine 'few megabytes' claim remain, and nginx:1.31.1 as an existing tag was not verified by me; none is blocking.

NEW-CLAIM VERIFICATION. URLs actually opened: kubernetes.io/docs/concepts/configuration/manage-resources-containers/ (read only the first 100000 of 133457 characters, which covered the cited passages), docs.docker.com/engine/storage/volumes/, docs.docker.com/engine/storage/bind-mounts/, docs.docker.com/reference/cli/docker/container/stop/, docs.docker.com/engine/network/drivers/host/, docs.docker.com/get-started/docker-concepts/building-images/understanding-image-layers/, docs.docker.com/get-docker/, and docs.cloud.google.com/artifact-registry/docs/transition/transition-from-gcr (after the 301 from the cloud.google.com URL). I did not open a separate Docker 'validate images' page; the digest-versus-tag point rests on the page's own text and general knowledge, so that part is UNKNOWN. Internal links: the Next Module link and the index entries are intact; no new internal link was added. Of the external links added or kept in Sources, I fetched the Docker volumes, bind-mounts and stop pages (they resolve); I did not fetch the others.

SCORES from a full read, with the call-1 labels. D1 objectives 5, D2 accuracy 4, D3 explanation depth 4, D4 examples 5, D5 practice/assessment alignment 4, D6 concision/engagement 4, D7 structure/flow 4, D8 safety/currency 4. D total 34/40. Floor 33, so the margin is 1; every D is at least 4. D6 and D7 sit exactly on their floor. L1 task clarity 4, L2 command/expected-output correctness 4, L3 verification/feedback 4, L4 cleanup/safety 5, L5 outcome alignment 4. L total 21/25. Floor 21, so the margin is 0; every L is at least 4. L3 is the weakest because Tasks 2 to 5 describe expected results in prose only (no sample outputs, no check that cleanup worked), and L1 is held down by the jargon and the implicit read-only path. The Docker lab was not run (no Docker on this host); the lab is judged as prose and design only.

BLOCKING: none. NON-BLOCKING: the residual jargon and the implicit read-only path in the lab Requirements; the missing bind-mount write-access warning; the unexplained distinction between the grep line and the sleep line; the remaining VM/container decision padding; unverified trivia, including whether nginx:1.31.1 exists. Because the margins are zero to one point, a stricter grader could score L3 or a D dimension lower; I judge the five ledger blockers closed and no new blocking defect introduced.

Checks performed by me: git HEAD, diff stat, sha256, word counts, full-page read, repo greps for inbound fragment links and dangling references, a local ps/grep self-match run, and the source fetches above. Supplied and not independently verified: the author's PR-body table of excerpts beyond the pages I opened. Limits: no lab execution; WebFetch summaries are model-condensed, so quotes are as returned by that tool.

### Findings (verbatim JSON)

```json
[]
```
