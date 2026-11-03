# Reviews of prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md under OO-KD-REREVIEW-1102

Verbatim reviewer output with ONE disclosed edit. Reviewer for all three: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The Docker lab was not run by any reviewer. Call 3 was a CTO-granted pinned verification round limited to two remaining findings (the volume practice's unused-name check and guards, and the checklist, the lab-owner definition and a stale sentence). ONE EDIT to the otherwise verbatim text: a host filesystem path inside the call-1 reviewer's PROVENANCE sentence was shortened to the repository-relative `schemas/code-review-findings.v1.schema.json` (public repository files carry no host paths); nothing else was changed.

## kd-wp-cn12-r1: call 1 of 2, whole-page review

- reviewed head: `376dab1b63bdc1d3bb143e97ff977534690cba87`
- run nonce: `42d27dc2b2f04d9dbfb3cc4dfadbf710`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

WHOLE-PAGE REVIEW, call 1 of 2, of src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md.

DIGEST: I ran sha256sum on the page and got 5b7d6bbeddb457900b2e518ded4f8763402f3a1d3a56d1d889bbb992bac918af, which matches the supplied digest. The checkout HEAD is 376dab1b6, not 42987ea6b. A git diff 42987ea6b..HEAD --stat shows only page-reviews.json and a module 1.1 review file changed, so the page bytes are identical.

SCORES (D1-D8):
- D1 outcome-to-teaching alignment: 3. The 'persistent volume mounts' and 'combine logs, process inspection, exec, configuration checks' outcomes are never practised.
- D2 accuracy: 3. The base-image size table is inverted against Docker Hub. The BAD/GOOD Dockerfiles carry inline # comments that Docker parses as arguments.
- D3 explanation clarity: 3. The opening protocol uses unexplained jargon ('same-L2', docker context, 'authorized local Docker endpoint'). The recovery path for a port conflict may be a dead end.
- D4 worked examples: 4. The Flask build-run-env example, the cache-ordering example and the non-root example are good.
- D5 practice and assessment: 3. The levels are aligned except for the two gaps above. Compose has no verification. There are no tiered hints, only a single solution reveal.
- D6 prediction and retrieval design: 4. The predict/reveal blocks and failure-layer cards are good, though several have filler lead-ins.
- D7 safety: 4. ID-captured cleanup, loopback publishing and the warning about the docker group are strong. The nits are `sudo sh` on an unread script and `down -v`.
- D8 concision and coherence: 3. The kubectl paragraph is off-topic. There is an 'original module' meta leak and repeated filler lines. The Equifax hook claims more than it can support.
Total 27/40. The floor of all >=4 is NOT met, and 27 is below 33.

SCORES (L1-L5, three-level lab):
- L1 objectives: 4.
- L2 executability as written: 4. Commands are guarded and coherent.
- L3 verification and feedback: 3. There are no hints, and Compose and volumes are unverified.
- L4 cleanup: 3. Containers are cleaned up, but images (dojo-web:v1, hello-flask:v1, my-ubuntu-curl) and the Compose stack are only mentioned as having 'separate lifecycles', with no command.
- L5 safety and design: 4.
Total 18/25. The L floor is NOT met, and 18 is below 21.

DISPOSITION: revise. Confidence 0.8.

SOURCE_STATUS: partly supported.
Claims judged (15):
- Supported (9): the Engine 28.0.0 L2 caveat; the Dockerfile '#-mid-line is an argument' rule; the convenience script not being recommended for production; the BuildKit default in 23.0; the dockershim removal in 1.24; the Ubuntu 24.04 --break-system-packages claim; the ENTRYPOINT/CMD, EXPOSE and COPY semantics; the postgres:16 password-exit behaviour; the Postgres data path.
- Partly supported / stale (3): the Equifax figure; the Homebrew cask name; the build-context 'exhaust memory' claim.
- Unsupported or contradicted (3): the base-image sizes; the Equifax 'too much privilege' framing; 'BETTER: Alpine'.
I took the BuildKit 23.0, dockershim 1.24 and Ubuntu PEP 668 items from my own knowledge, not from fetched sources.

LAB_EXECUTION: not run. No container runtime is available on this host and I did not execute anything. All Docker commands are judged as prose and design only.

BLOCKING FINDINGS (each fits a small PR):
B1 lines 38-42: off-topic kubectl paragraph.
B2 lines 111-113: unexplained jargon in the opening protocol.
B3 lines 409-419 and 566: Dockerfile snippets with inline # comments.
B4 lines 124 and 899-904: the port-conflict recovery path may lead to a name conflict (behaviour UNKNOWN until reproduced).
B5 lines 509-516: the base-image size table is inverted.
B6 lines 22-24 and 177: the volume and debug outcomes have no practice.

NON-BLOCKING FINDINGS:
N1 line 218 vs 216: debugging order contradicts the preceding paragraph.
N2 lines 61-62: sudo sh on an unread script.
N3 line 30: Equifax figure and framing.
N4 lines 48, 78, 105, 128, 505, 552: meta leak and filler lead-ins.
N5 line 54: Homebrew cask name may be stale.
Also non-blocking: line 351 'exhaust memory' overstates the cost; line 534 '# BETTER: Alpine' contradicts line 507; lines 132, 309, 780 use floating tags; Level 3 is titled 'Optimization' but has no optimisation task; no image or Compose cleanup commands; compose_project is not shown being set; the lab has no tiered hints.

OMITTED-CLAIM DISCOVERIES: the Equifax attribution (line 30); the Engine >= 28.0.0 requirement with no action if older (line 111); the build-context cost claim (line 351); the invented 2-minute / 1-second timings (line 403, hedged by 'might'); the unsourced sizes in the base-image table.

URLS ACTUALLY OPENED:
- https://docs.docker.com/engine/network/port-publishing/ (confirmed the 28.0.0 L2 caveat; says nothing about host-port-in-use behaviour).
- https://docs.docker.com/reference/dockerfile/ (read the first 100k characters; the '#' argument rule is confirmed).
- https://docs.docker.com/engine/install/ubuntu/ (convenience-script warning confirmed; it does not say the docker group grants root).
- https://hub.docker.com/v2/repositories/library/python/tags/3.12-slim (43.27 MB compressed amd64).
- https://hub.docker.com/v2/repositories/library/ubuntu/tags/24.04 (29.77 MB compressed amd64).
- https://formulae.brew.sh/cask/docker-desktop (docker-desktop exists; the former token is docker).
- https://www.ftc.gov/enforcement/refunds/equifax-data-breach-settlement (147 million; no cause stated).
Fetch failure: https://formulae.brew.sh/api/cask/docker.json returned 404, so the status of the old cask is UNKNOWN. I did not open any of the other URLs in the page's Sources section.

TAKEN FROM SUPPLIED EVIDENCE / NOT VERIFIED: I did not read the docs/content-upgrade/reviews/*source-catalog*.json files or the superseded history in page-reviews.json. I read docs/review-contract.md and the page fully. I relied on my own knowledge, not a fetched source, for the claim that a failed port bind leaves a Created container (B4).

PROVENANCE: independent cross-family reviewer (Anthropic family), model claude-sonnet-5-5, Claude Code harness. Review kind: whole-page review, call 1 of 2. The schema file at schemas/code-review-findings.v1.schema.json was outside the read-only sandbox, so findings follow the shape given in the task's output-format definition.

LIMITS: nothing was executed. No lab commands were run. The page's other Sources links were not opened. Source catalogs were not reviewed.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B1",
  "title": "Off-topic kubectl instruction embedded in the Docker module intro",
  "body": "The 'Why This Module Matters' section ends with a paragraph telling learners to verify the full kubectl client, plus a discussion of shell aliases. kubectl is absent from the module's declared Environment and is used by nothing later in the page: the YAML and kubectl block is explicitly 'do not execute'. It reads as a leftover from another module. A beginner who has no kubectl installed will stall or be confused.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 38,
   "end_line": 42,
   "claim_type": "present"
  },
  "verbatim": "Before you touch Kubernetes commands in this course, verify that the full `kubectl` client works on your machine.",
  "why_wrong": "BLOAT / abrupt unexplained transition: the learner needs nothing from this paragraph for the Docker outcomes. It adds a tool requirement that the Environment line does not list.",
  "smallest_fix": "Delete the paragraph and the `kubectl version --client` block, or move it to the module that first uses kubectl and add kubectl to that module's Environment.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B2",
  "title": "Opening protocol uses unexplained jargon before the first container is run",
  "body": "The first run section tells learners to check docker context show/inspect and confirm the Server Engine is >= 28.0.0, citing a 'same-L2 localhost-publication caveat'. The terms Docker context, 'local endpoint' and 'same-L2' are never defined. No action is given if the Engine is older. Lines 113 and 165 add dense 'ownership proof' language that a beginner cannot interpret. The Engine 28.0.0 caveat itself is correct: the Docker port-publishing doc says 'In releases older than 28.0.0, hosts within the same L2 segment ... can reach ports published to localhost'.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 111,
   "end_line": 113,
   "claim_type": "present"
  },
  "verbatim": "Older Engines have a documented same-L2 localhost-publication caveat.",
  "why_wrong": "UNDER-EXPLANATION: terms are used before they are explained, with no action stated (upgrade, or accept the risk). The jargon stands in the way of the first hands-on step for the Zero to Terminal audience.",
  "smallest_fix": "In one or two plain sentences, define 'Docker context' and say what a local endpoint looks like (for example the default context). Replace 'same-L2' with 'other machines on your network can reach the published port'. State to upgrade Docker or avoid untrusted networks if the Engine is older.",
  "sources": [
   "https://docs.docker.com/engine/network/port-publishing/"
  ]
 },
 {
  "id": "B3",
  "title": "Teaching Dockerfiles put # comments after instructions, which Docker treats as arguments",
  "body": "The BAD/GOOD cache-ordering blocks (for example `COPY . .   # Any change busts cache`) and the root example (`CMD [\"python\", \"app.py\"]  # Runs as root!`) put comments after the instruction. The Dockerfile reference says: 'A # marker anywhere else in a line is treated as an argument.' Copied as written, COPY receives extra sources, and the exec-form CMD is no longer valid JSON, so it falls back to shell form. The module is teaching Dockerfile authoring, and the blocks are fenced as dockerfile.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 409,
   "end_line": 419,
   "claim_type": "present"
  },
  "verbatim": "CMD [\"python\", \"app.py\"]  # Runs as root!",
  "why_wrong": "The snippets misteach comment syntax in a Dockerfile and fail or misbehave if a learner pastes them.",
  "smallest_fix": "Move every inline # comment (lines 409, 410, 416-418, 566) onto its own preceding line.",
  "sources": [
   "https://docs.docker.com/reference/dockerfile/"
  ]
 },
 {
  "id": "B4",
  "title": "Recommended port-conflict recovery re-uses the same container name and may lead to a name conflict",
  "body": "Both the port-conflict prediction answer and Card B say to retry with a free loopback port. The retry still uses `--name my-nginx`. I believe, from my own knowledge and not from a source I opened, that a failed port bind leaves a container in the Created state, so the retry would hit a name conflict. Line 165 then says to stop on a name conflict, and Card B says not to delete by name. The learner is left with no way forward. The nginx_id variable is empty after the failed run, so the ID-based cleanup cannot remove the leftover. The port-publishing doc I opened does not describe the in-use behaviour, so this behaviour is UNKNOWN until reproduced.",
  "priority": "P2",
  "confidence": 0.6,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 124,
   "end_line": 124,
   "claim_type": "present"
  },
  "verbatim": "Choose a free loopback host port such as `-p 127.0.0.1:8081:80`, retaining container port 80.",
  "why_wrong": "UNDER-EXPLANATION of failure recovery: the answer never says that creation fails or what a leftover failed attempt looks like, and the retry path as written may be a dead end.",
  "smallest_fix": "Say the run fails with a bind error. Say that a failed attempt may leave a Created container. Say to retry with both a new port and an unused name (for example my-nginx-2), and to list leftovers with `docker ps -a --filter name=my-nginx` for the learner to judge as theirs. Apply the same fix to Card B (lines 899-904).",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B5",
  "title": "Base-image size table is inverted relative to published image sizes",
  "body": "The table gives ubuntu:24.04 ~70MB and python:3.12-slim ~40MB, and the surrounding text, a predict block and Card C all use 'a full OS image is bigger'. Docker Hub (opened) shows ubuntu:24.04 at 29.77 MB compressed and python:3.12-slim at 43.27 MB compressed for amd64. Bare ubuntu is smaller than python slim in compressed terms, so the numbers mix measurements and the message is wrong as stated. Ubuntu with Python installed is larger, which is the real comparison. The table states no date or measurement basis for these volatile values.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 509,
   "end_line": 516,
   "claim_type": "present"
  },
  "verbatim": "| Full OS | `ubuntu:24.04` | ~70MB | Large (contains full utilities) | Complex legacy apps needing many system dependencies |",
  "why_wrong": "Unsupported specificity that contradicts a source, and it feeds the module's misleading claim that a full OS base is larger than slim. Volatile sizes are unsourced and undated.",
  "smallest_fix": "Remove the numeric Size column, or give one consistent measure with a date (for example compressed sizes from Docker Hub as of 2026-11), and compare ubuntu-with-python against python:slim. Change the 'BETTER: Alpine' label at line 534 to a neutral label.",
  "sources": [
   "https://hub.docker.com/v2/repositories/library/python/tags/3.12-slim",
   "https://hub.docker.com/v2/repositories/library/ubuntu/tags/24.04"
  ]
 },
 {
  "id": "B6",
  "title": "Two stated outcomes have no worked example or practice: persistent volumes and combined debugging",
  "body": "Outcome 2 promises 'persistent volume mounts' and outcome 3 promises 'combining logs, process inspection, exec sessions, and configuration checks'. The cheat sheet shows only a bind mount, labelled 'Volume mount'. Named volumes appear only inside the Compose file, which is not verified. No step shows data surviving `docker rm`, and `docker volume` is never taught. The three lab levels use logs (Level 2) and exec on a healthy container (Level 3). `docker inspect` and `docker top` appear only in a command list. The bind-versus-named-volume difference is never explained.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 177,
   "end_line": 177,
   "claim_type": "missing"
  },
  "verbatim": "docker run -v /host/path:/container/path nginx  # Volume mount",
  "why_wrong": "UNDER-EXPLANATION / outcome-to-practice gap: a key skill and a stated outcome have no worked example, and the quiz answer on volumes (`-v db_data:/var/lib/postgresql/data`) relies on a syntax the page never showed. Compose, the other place where volumes appear, ends without a verification step.",
  "smallest_fix": "Add a short Level 2 step: run postgres with `-v <unused_name>:/var/lib/postgresql/data` plus a note on bind versus named volumes. Show data surviving `docker rm` or a re-created container, then list and remove that named volume with `docker volume ls` and `docker volume rm`. Add one `docker inspect` or `docker top` step to the failing-container flow. Add a Compose verification step (`docker compose ps`, `curl`, and a service-name DNS check) and note that `logs -f` needs Ctrl-C.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N1",
  "title": "Debugging order contradicts the preceding paragraph",
  "body": "The paragraph above says exec should come after the non-invasive checks, which include inspect. The Stop-and-think then lists logs, exec, inspect in that order, and the quiz follows the later order.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 218,
   "end_line": 218,
   "claim_type": "present"
  },
  "verbatim": "`docker logs` asks what happened, `docker exec -it ... bash` lets you look inside, and `docker inspect` shows the full configuration",
  "why_wrong": "Internal inconsistency between lines 216 and 218 about debugging order.",
  "smallest_fix": "Reorder to logs, then inspect/top, then exec, and align the quiz answer on the 500-error scenario.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N2",
  "title": "Convenience script run with sudo without telling the learner to read it",
  "body": "The install block downloads get-docker.sh and runs it with sudo sh. Docker's install page says to always examine scripts downloaded from the internet before running them and suggests --dry-run. The page notes production caution but not this.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "security",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 61,
   "end_line": 62,
   "claim_type": "present"
  },
  "verbatim": "curl -fsSL https://get.docker.com -o get-docker.sh\nsudo sh get-docker.sh",
  "why_wrong": "Running an unread remote script as root is the habit this module is meant to warn against.",
  "smallest_fix": "Add one sentence and a comment line, such as 'read get-docker.sh (or run with --dry-run) before the sudo line', and say the script is for development and testing.",
  "sources": [
   "https://docs.docker.com/engine/install/ubuntu/"
  ]
 },
 {
  "id": "N3",
  "title": "Equifax hook is more specific than its evidence, and the figure is out of date",
  "body": "The FTC page I opened states 147 million people. The page says roughly 143 million, which was the initial figure. The sentence also attributes excess privilege and surface area to Equifax, which the sources I opened do not state. The page itself concedes the incident was 'not a Docker story'.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 30,
   "end_line": 30,
   "claim_type": "present"
  },
  "verbatim": "In 2017, Equifax disclosed a breach that exposed sensitive data for roughly 143 million people",
  "why_wrong": "Unsupported specificity, and an outdated figure used as a motivating hook for an unrelated technology.",
  "smallest_fix": "Cut the Equifax hook, or restate it as 'an unpatched component' and use the later figure of 147 million with a source link.",
  "sources": [
   "https://www.ftc.gov/enforcement/refunds/equifax-data-breach-settlement"
  ]
 },
 {
  "id": "N4",
  "title": "Editing-history meta text and repeated filler lines in learner prose",
  "body": "Line 48 refers to 'the original module', which means nothing to a learner. Lines 78, 105, 128, 505 and 552 are short 'name X before you read Y' lead-ins that repeat the instruction of the preceding predict block without adding teaching content.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 48,
   "end_line": 48,
   "claim_type": "present"
  },
  "verbatim": "The original module linked the Docker Desktop product page",
  "why_wrong": "BLOAT: history leakage and repetition that the learner loses nothing without.",
  "smallest_fix": "Reword line 48 to 'See the Docker Desktop page for licensing', and delete the filler lead-ins at lines 78, 128, 505 and 552.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N5",
  "title": "Homebrew cask name may be stale",
  "body": "I could not confirm the status of the `docker` cask. The cask page for `docker-desktop` lists `docker` as a former token, so the page's install command uses the older name.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 54,
   "end_line": 54,
   "claim_type": "present"
  },
  "verbatim": "brew install --cask docker",
  "why_wrong": "Volatile tooling name that may be deprecated; unverified.",
  "smallest_fix": "Use `brew install --cask docker-desktop` or hedge with 'the cask name may change'.",
  "sources": [
   "https://formulae.brew.sh/cask/docker-desktop"
  ]
 }
]
```

## kd-wp-cn12-r2: call 2 of 2, delta review

- reviewed head: `df543b74f27b13d64f4b196dc0c0845886d1fd51`
- run nonce: `2edfb3236c2b4a44beedc3f06cf2f6b9`
- verdict: `incorrect` (confidence 0.6)

### Explanation (verbatim)

TASK 1. HEAD is df543b74f27b13d64f4b196dc0c0845886d1fd51. The diff against 376dab1b6 touches one file (module-1.2-docker-fundamentals.md), 76 insertions and 46 deletions. The page sha256 at HEAD is 10b9c78e26b7274076ed2539c95aa0befe34637f2e1318f0032d556d398c6a36, which matches the expected value. Word count (wc -w) is 10007 against 10101 before, down 94. The delta is not padding.

BLOCKING LEDGER. All six call-1 blockers are closed as written. The residual gaps in fix quality are listed with each.
B1 closed: the kubectl paragraph and its code block are gone.
B2 closed in substance: a Docker context is now defined in plain words, and the action for an Engine older than 28.0.0 is given (upgrade, or avoid untrusted networks). The port-publishing page says that in releases older than 28.0.0, hosts in the same L2 segment can reach ports published to localhost, so the claim is consistent. Gap: the page never says what a local context looks like in the output. The contexts page says the default context uses the local Unix socket, and a beginner is not told to look for that.
B3 closed: a Python scan of every fenced dockerfile block found no instruction line with a trailing hash comment. The comments now sit on their own lines, and the shell blocks keep theirs.
B4 closed as a workable way forward: a new name plus a new loopback port needs nobody's help, and the ps -a filter lists leftovers. Stating the leftover as a possibility is acceptable and honest. The container create and port-publishing pages say nothing about it, so the exact state is UNKNOWN. Weakness: the phrase 'lab owner' now appears 5 times (the old page had 2) and is never defined. A solo learner is left with a leftover container they are told not to remove. This does not block progress and is non-blocking.
B5 closed. The size sentence is dated 2026-11-03 and gives about 30 MB for ubuntu:24.04 and about 43 MB for python:3.12-slim. The Docker Hub tag JSON gives full_size 29767612 for ubuntu (amd64 linux) and 43267206 for python slim, both matching. The table labels are neutral, and the predict answer matches the new framing. Stale reference: the sentence ending the workflow diagram section still says the next section asks the reader to name that cost before the comparison table, but the predict block no longer does that.
B6 closed in intent. A worked volume practice exists. It shows data surviving container removal, and its volume cleanup is limited to a name-filtered volume. Level 2 step 7 adds the combined debugging practice (logs, top, exec, inspect) with an answer for the exited case. The commands look right: the chaining, docker wait and quoting hold up. The Level 2 additions come after db_id is set, and the later cleanup still relies on a valid db_id. The bind-mount label is fixed. The remaining problems are in the new volume practice and are described in the findings.

NON-BLOCKING ITEMS.
N1 closed (logs, then inspect, then exec). N2 closed (read the script first). N3 closed by removing the Equifax hook; the Kubernetes mapping of logs, exec and describe survives at the Pod paragraph. N4 closed. N5 closed (cask docker-desktop; the Homebrew page lists former token docker). Build-context sentence closed. Invented timings removed. Alpine label closed. Compose project assignment and the follow-log exit note are added. The Level 3 heading is now 'Build and Exec' but its prose still opens with 'Optimize a build', which is a minor mismatch. Floating tags and tiered lab hints are partly open, as the author declared. The PostgreSQL docker run still leaves an anonymous data volume after docker rm, and the page never teaches this.

SOURCES OPENED. I fetched and read: the port-publishing page, the contexts page, the Docker Hub tag JSON for ubuntu 24.04 and python 3.12-slim, the volume create reference, the Homebrew docker-desktop cask page, the volumes page, the container create reference, the compose down reference and the Compose networking page. I did not open the build-context page or the Docker install page, so claims resting only on them are UNKNOWN. The links I fetched resolve. Inbound fragment links: only the #installing-docker heading is used from another page, and it is kept.

SCORES, call-1 labels, from a full read. D1 4, D2 5, D3 4, D4 4, D5 4, D6 4, D7 4, D8 4, total 33/40. Margin over the 33 floor is zero, and every D is at or above 4. L1 4, L2 4, L3 4, L4 4, L5 4, total 20/25. That is one point below the 21 floor, so the lab total fails. The cause is that the new practice has no pre-create ownership check, its success checklist is not updated for it, and the placeholder variables weaken the guards (see the findings).

BLOCKING: the lab total of 20/25 is below the 21 floor. The fixes are two small edits (P2 finding: volume check and guards; P3 finding: checklist, lab owner, stale cross-reference). NON-BLOCKING: the items above.

PROVENANCE. Reviewer is claude-sonnet-5-5 (Anthropic family, outside the OpenAI author family) run through Claude Code. Review kind: delta review, call 2 of 2, not acceptance. I read the full page. I did not run Docker, so the lab was judged as prose and design only.

### Findings (verbatim JSON)

```json
[
 {
  "id": "V1",
  "title": "Volume practice creates the volume before any ownership check and removes it afterwards",
  "body": "The new volume practice runs docker volume create on a placeholder name with no preceding check that the name is unused. docker volume create reuses an existing volume of the same name without an error, so the practice can write a marker into someone else's volume. The only listing command appears in the cleanup block after the create, and cleanup then runs docker volume rm on the same name. The shipped placeholder values (your-unused-volume, your-unused-project) are pre-set, so the Compose guard that follows can no longer refuse an unset project name.",
  "priority": "P2",
  "confidence": 0.6,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 833,
   "end_line": 834,
   "claim_type": "present"
  },
  "verbatim": "volume_name=your-unused-volume\ndocker volume create \"$volume_name\" &&",
  "why_wrong": "The page requires verifying unused names before acting, but the volume has no pre-create check and creation is idempotent. After create, the later 'confirm it belongs to this exercise' step cannot distinguish a pre-existing volume from a new one. Pre-setting the placeholders also removes the unset-variable refusal for the Compose project name.",
  "smallest_fix": "Run docker volume ls with a name filter before the create and stop if the name is listed. Leave the volume and compose_project variables unset, or set them from a read prompt, so the :? guard refuses until the learner substitutes a verified name.",
  "sources": [
   "https://docs.docker.com/reference/cli/docker/volume/create/",
   "https://docs.docker.com/engine/storage/volumes/"
  ]
 },
 {
  "id": "V2",
  "title": "Success checklist omits the new practices; lab owner undefined; stale cross-reference",
  "body": "The Success Criteria checklist was not updated for the new volume practice or Level 2 step 7 (combined debugging), the two outcomes B6 asked to have practised. The undefined role 'lab owner' is now relied on in five places, including the recovery for a failed port bind, and a solo learner has no one to ask. One sentence at the end of the workflow diagram section still refers to naming a cost before the comparison table, but the predict block no longer does that.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 905,
   "end_line": 911,
   "claim_type": "missing"
  },
  "verbatim": "- [ ] You cleaned up containers you created during the lab.",
  "why_wrong": "Verification does not cover the volume practice or the logs, top, exec and inspect practice. Unchecked outcomes keep the L3 and L1 dimensions below the floor. 'Lab owner' is undefined for a learner working alone, and the stale sentence points at a step that no longer exists.",
  "smallest_fix": "Add two checklist lines (volume marker survives container removal and only the exercise volume was removed; logs, top, exec and inspect were used on the running PostgreSQL container). Define 'lab owner' as the person who manages the machine, usually the learner, or drop it. Delete the stale 'name that cost' sentence.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn12-r3: round 3, CTO-granted pinned verification of two remaining findings only

- reviewed head: `5d9d73f2c37deebe6ea2782a93322ec9085767b9`
- run nonce: `58463701fa384112a5b7ee2df6fba40e`
- verdict: `correct` (confidence 0.72)

### Explanation (verbatim)

Pinned verification round 3 (not acceptance). Reviewer: Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family, outside the OpenAI/Codex author family), Claude Code harness, toolful, read-only. Nothing was edited, committed, pushed or commented.

Task 1. HEAD is 5d9d73f2c37deebe6ea2782a93322ec9085767b9. The working tree is clean. The page sha256 is b3b1e4a36e135fb983a3ae5c4991aa24dc6ce9843cd3662271c4919ddacc2257, which matches the expected value. The delta from df543b74f to HEAD touches one file, module-1.2-docker-fundamentals.md, with 16 insertions and 15 deletions. I read the full diff and it matches the author's description.

Task 2, V1: CLOSED, with one non-blocking residual (P3).
- The two pre-set placeholder lines are gone. A grep of the page finds no assignment to compose_project or volume_name anywhere. Both variables are only read, never set, so an earlier block cannot leave them set.
- Every use of compose_project (page lines 458, 461, 462, 464, 467, 470, 902) carries the colon-question-mark guard. Line 429 only describes setting it.
- Every use of volume_name (lines 831, 833, 834, 836, 843, 845) carries the guard. This includes the cleanup paragraph at line 902 and the volume rm. An unset name now makes each command refuse.
- The unused-name check is real and in the right place. The docker volume ls with a name filter (line 831) comes before docker volume create (line 833).
- It is not mechanically enforced. The ls prints and exits 0 whether or not a name is listed, so the stop at line 832 is only a comment. A learner who pastes the whole worked-answer block will still run create on a listed name. The Docker reference says create reuses an existing volume of that name without an error. The marker file would then be written into that volume.
- Damage is bounded. The paragraph at line 825 tells the learner in prose to run the check and stop if a name is listed. The later volume rm is behind a prose ownership confirmation. The Compose project check is also prose-only (line 429). So the stop is consistent with the page's ownership-judgement conventions, but weaker than its own captured-ID and guard conventions elsewhere. I rate this P3, non-blocking. The smallest fix is to replace the bare ls line with a mechanical gate, joined to the create by &&: test -z "$(docker volume ls -q --filter "name=${volume_name:?...}")".
- Substring match: per the Docker volume ls reference the name filter matches all or part of a volume name. A different volume that merely contains the chosen name causes a spurious stop, which is the safe direction. I found no way for the substring match to produce a wrong go, because every exact match is also a substring match. Acceptable.
- Where the names get set: line 456 says to choose and export your own verified project name. Line 825 says to choose and export your own unused volume name. Line 429 covers setting compose_project. No example assignment is shown, so a true beginner must already know shell variable syntax. That is a minor clarity limit, not a blocker.

Task 3, V2: CLOSED.
- The checklist now has the line on logs, top, exec and inspect on the running PostgreSQL container (line 908). It matches Level 2 step 7 and the solution lines 817-820.
- It also has the line on the volume marker surviving container removal and removing only the exercise volume (line 909). It matches the volume practice.
- Lab owner is defined at first use (line 115) as the person who manages the machine, usually you. The grep finds five occurrences, at lines 115, 429, 825, 840 and 932, all consistent with that definition. Line 932 is the Card B repeat of the line 115 prediction and does not redefine it.
- The grep for name that cost, name a cost and comparison table finds nothing. The stale sentence is gone, and no dangling reference to the removed predict remains.

Task 4, new defects from the delta: none blocking. The Compose block lists down and then down -v sequentially (lines 467-470); this was already closed in call 2 and I did not reopen it. The residual in V1 is the only delta-introduced weakness.

Task 5, scores from a full read of the sections I opened (header, install and first-run, Compose, Quiz and Hands-On, Success Criteria and cards). I did not re-read the middle image-quality and security sections in full; their scores carry over from call 2.
Documentation D1-D8: D1 4, D2 5, D3 4, D4 4, D5 4, D6 4, D7 4, D8 4. Total 33/40, margin 0 over the 33 floor, and every D is at least 4. D5 and D7 stay at 4 because the volume stop is advisory.
Lab L1-L5: L1 5, L2 4, L3 4, L4 4, L5 4. Total 21/25, margin 0 over the 21 floor, and every L is at least 4.
- L1 moves to 5 because the checklist now covers every lab activity and matches the stated objectives to run with volumes and to debug by combining tools.
- L2 stays 4 because no example assignment shows how to set the two variables.
- L5 stays 4 because the unused-name stop is advisory.
- The lab floor is met only through L1, and the margin is zero. This is a prose judgement; the Docker lab was not run (no Docker on this host).

BLOCKING: none. NON-BLOCKING: the P3 finding below (advisory stop on a listed volume name), plus the minor note that no example assignment is shown for the two variables.

Checks performed by me: HEAD, status and sha256; git diff and diff stat between the two heads; grep of the page for compose_project, volume_name, lab owner, name that cost and comparison table; a read of the Compose, Hands-On, Success Criteria and card sections. Opened sources: the Docker docs pages for docker volume create (reuses an existing volume of that name without an error) and docker volume ls (the name filter matches all or part of a name; the exit status is undocumented, so I treat it as UNKNOWN). Not run: any Docker command. Limits: the lab was judged as prose and design only.

### Findings (verbatim JSON)

```json
[
 {
  "id": "V1-advisory-stop",
  "title": "Unused-volume-name check is advisory; the block runs on after a name is listed",
  "body": "The worked answer runs docker volume ls with a name filter, then a comment says to stop if any name is listed, then immediately chains docker volume create. The ls exits normally whether or not it lists a name, so a learner who pastes the whole block continues into create. Docker's reference says create on an existing name reuses that volume without an error. The marker file is then written into a volume the learner may not own. Damage is limited (one small file, and the later volume rm is behind a prose ownership confirmation), and the paragraph before the block tells the learner in prose to stop on a listed name. That is why this is non-blocking.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md",
   "start_line": 831,
   "end_line": 833,
   "claim_type": "present"
  },
  "verbatim": "# Stop if any name is listed or the check fails; otherwise run the rest.",
  "why_wrong": "The page uses captured IDs and colon-question-mark guards elsewhere so that unsafe continuation is mechanically refused. Here a comment is the only barrier before a command that silently reuses an existing volume.",
  "smallest_fix": "Replace the bare ls line with a gate chained to the create, for example: test -z \"$(docker volume ls -q --filter \"name=${volume_name:?Set the unused volume name first}\")\" && docker volume create ... (the substring filter only over-stops, which is the safe direction).",
  "sources": [
   "https://docs.docker.com/reference/cli/docker/volume/create/",
   "https://docs.docker.com/reference/cli/docker/volume/ls/"
  ]
 }
]
```
