# Reviews of prerequisites/zero-to-terminal/module-0.11-your-first-server.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The lab was not run by either reviewer.

## kd-wp-11-r1: call 1 of 2, whole-page review

- reviewed head: `8186da6afa92f9a003e81d1d05dd93fb8ea56193`
- run nonce: `22a3717a2c524dfab7c2b9c90194cccd`
- verdict: `incorrect` (confidence 0.75)

### Explanation (verbatim)

WHOLE-PAGE REVIEW, call 1 of 2, module 0.11 Your First Server. DISPOSITION: REVISE (confidence 0.75).

DIGEST: HEAD 8186da6afa92f9a003e81d1d05dd93fb8ea56193. sha256sum of the page = 1fd464c001b8152053457759c250f36bbcec3f60aeb0c0e0355b085e657d5ece, matching the supplied digest. I read all 590 lines.

SCORES (the contract does not name D1-D8/L1-L5, so these labels are mine). D1 outcome clarity 4: four stated outcomes. D2 outcome-to-teaching alignment 3: port checks and firewall checks are named in an outcome but never taught (B2). D3 accuracy and explanation 4: the Docker and Ubuntu facts I checked hold. D4 examples and illustration 3: no expected curl or docker ps output, no VM-creation walkthrough, and the Stop-and-think prompts at lines 143 and 319 are not answered outright. D5 practice and assessment 3: exercise sequencing breaks (B1), no tiered hints. D6 concision and flow 3: BLOAT from repeated hedge boilerplate (B3). D7 sources and evidence honesty 4: careful hedging, but the Sources list is padded with orphans (N2). D8 safety and learner support 4: strong authorization, loopback, cleanup and billing framing. TOTAL 28/40: the 33 total is NOT met and D2, D4, D5, D6 are below 4.
LAB: L1 executability 3 (teardown precedes the exercise, guards fail silently, Option B has no VM-creation steps); L2 verification 4; L3 cleanup 3 (cleanup placed before the exercise, none at its end); L4 feedback and hints 3 (solution guidance only, no tiered hints, no expected observations); L5 safety 4. TOTAL 17/25: the 21 total is NOT met and L1, L3, L4 are below 4.

source_status: PARTLY SUPPORTED. I judged 13 material claims. Of the 8 checked against sources I opened, 7 are supported and 1 is partly supported (see below). 5 were not checked by me. The citation seed is stale: it ledgers text no longer on the page (Netflix/Airbnb/Dropbox, Oracle most-generous free tier, Docker 24.x) and most of its dispositions are needs_allowlist_expansion or null, so I did not rely on it.
Supported by sources I opened: (1) Docker publishes to all host addresses by default; (2) Engines older than 28.0.0 let hosts on the same L2 segment reach localhost-published ports; (3) routed/nat caveat that published ports can be reached via direct routing unless the host firewall restricts it; (4) Ubuntu default page is placed in /var/www/html/; (5) the NeXT machine bore the handwritten warning 'This machine is a server. DO NOT POWER IT DOWN!!'; (6) nginx idea originated in 2002 and the C10K problem is defined as handling more than 10,000 concurrent connections; (7) a stopped EC2 instance still incurs EBS volume charges and charges for associated Elastic IPs. Partly supported: the official nginx image serving /usr/share/nginx/html. The Docker Hub page I opened shows the path only in usage examples, not as an explicit statement; this is widely true but not explicit there. NOT checked by me: Docker 28.0.0 release-note claim (a sibling review cites it, I did not re-open it); docker-group root-equivalence (post-install page); MDN or RFC 9110 port 80/443 defaults; nginx pronounced engine-X; info.cern.ch; and the ledger statement that snapshots are billable (the AWS page I opened covers EBS and Elastic IP only). I also could not confirm that https://kubedojo.dev (line 488) is the project's site; this is UNKNOWN, not a defect finding.

lab_execution: NOT RUN. No Docker, cloud VM, nginx or SSH exists on this host (no docker binary); I did not execute anything. Judged as prose and design only. Per the page's own record, no container, SSH or cloud step was run by anyone.

BLOCKING findings: B1 (lines 214-218, 325 versus 481-540) teardown instructed before the exercise that needs the running resource; test -n guard then silently no-ops; no cleanup at exercise end. B2 (line 22) outcome 3 promises port checks and firewall checks but no listener or firewall command is taught here or in 0.7-0.10, and no expected curl/docker ps output is shown. B3 (lines 75, 151, 212, 269, 317, 323, 337, 341, 345, 355, 363) BLOAT: the same hedge sentences repeat at least a dozen times and the Patterns, Decision Framework and Common Mistakes sections restate them. B4 (line 230) Option B gives no VM-creation steps; no module teaches it; the ubuntu login user is provider-specific; inbound SSH is opened with no source restriction advice.

NON-BLOCKING findings: N1 (lines 271, 277, 513-520) Ubuntu's package default is believed to be index.nginx-debian.html, so there is no default index.html to delete, and renaming index.html would fall back to the welcome page instead of breaking; I could not verify this (Ubuntu tutorial does not name the file; Debian source fetches returned 404), so it is hedged and the page's own caveat partly covers it. N2 (lines 99-104, 553-570) content-free tool table and orphan Sources entries (Oracle, Google, AWS free-tier, Docker Personal, Inside NGINX) that back no current page claim. N3 (lines 143, 319) two Stop-and-think questions are not answered; for the port-in-use case a failed docker run may leave a created container holding the name my-website, which the guard text forbids adopting; I could not verify that Docker behavior. N4 (lines 493-531) solution guidance has no tiered hints. N5 the citation seed is stale and should be regenerated or retired.

OMITTED-CLAIM DISCOVERY: unledgered material claims in the current page: Docker publishes on all addresses by default; the pre-28.0.0 L2 caveat; the docker-group root-equivalence claim; the Ubuntu and Docker web roots; the AWS retained-resource charge claim; the default ports 80/443. None is in the stale seed; the first three were verified by me or are marked above.

URLS ACTUALLY OPENED: docs.docker.com/engine/network/port-publishing/; hub.docker.com/_/nginx; ubuntu.com/tutorials/install-and-configure-nginx; home.cern/science/computing/the-birth-of-the-web/short-history-web/; blog.nginx.org/blog/celebrating-20-years-of-nginx; docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html; docs.docker.com/reference/cli/docker/container/run/ (no port-conflict statement). Fetch failures (UNKNOWN): salsa.debian.org and sources.debian.org default-site files (404).

PROVENANCE: reviewer Claude Code, model claude-sonnet-5-5 (Anthropic family), Claude Agent SDK harness, read-only checkout. Author family OpenAI/Codex, so cross-family. Review kind: whole-page review, call 1 of 2, not approval. Checks performed by me: digest, full page read, review-contract, completion plan, citation seed, prior review index entries, grep of modules 0.7-0.10 for curl/ss/ufw/VM creation, and the URLs above. Supplied and not re-judged: prior review dispositions and the Docker 28.0.0 release-note claim.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B1-teardown-before-exercise",
  "title": "Teardown precedes the exercise that needs the running resource",
  "body": "Option A and Option B each end with a cleanup instruction, and the Hands-On Exercise follows. The exercise opens with 'you have deployed the template page' and Task 3 tells the learner to run the cleanup block then create again. A learner following the page in order runs cleanup at line 217, which clears lesson_container and removes the container, then reaches Task 1 'use the guarded copy block with your captured container ID'. The guard test -n on an empty variable fails silently, so the learner sees nothing happen, and Task 2 curl against 8080 is refused. For Option B, line 325 tells the learner to terminate/delete the VM before Task 3 and Task 4 which SSH into that VM. The exercise has no end-of-lab cleanup step and the success criteria do not include cleanup.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 214,
   "end_line": 218,
   "claim_type": "present"
  },
  "verbatim": "When done, stop and remove only the container you created for this lesson.",
  "why_wrong": "The page orders teardown before the hands-on exercise that depends on the resource, and the silent no-op gives the learner no feedback. This is an unexplained transition and a lab dead end on the main path; it also leaves no cleanup at the end of the lab.",
  "smallest_fix": "Mark both cleanup passages (lines 214-218 and 325-329) as 'do this after the Hands-On Exercise', and add one final cleanup task or success-criterion item at the end of the exercise for both paths. Optionally make the guard print a message when the variable is empty.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B2-port-firewall-checks-untaught",
  "title": "Outcome promises port checks and firewall checks that are never taught",
  "body": "Outcome 3 says the learner will diagnose failures with port checks and firewall checks. No section shows a command or console step for listing listeners on the VM or inspecting firewall or security-group rules, and modules 0.7-0.10 do not teach one either (grep for ss, netstat, ufw, nc and lsof found nothing). Quiz 3 and Quiz 6 then ask the learner to verify listener binding and access policy. The page also gives no sample output for curl failures, a refused connection, a timeout or an HTTP error, or for docker ps showing the published port, so the symptom-reading section cannot be mapped to anything the learner will actually see.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 22,
   "end_line": 22,
   "claim_type": "missing"
  },
  "verbatim": "port checks, firewall checks, and careful path inspection",
  "why_wrong": "UNDER-EXPLANATION: a stated outcome and its assessments have no teaching. The learner is told to check listener binding and firewall policy with no way to do it.",
  "smallest_fix": "Add one short worked step for each path: a listener check on the VM (for example ss -tln for port 80) and a pointer to where the provider firewall or security group rule is viewed. Show one clearly labelled synthetic sample each of docker ps (PORTS column) and a failed curl. Alternatively, drop 'port checks, firewall checks' from the outcome.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B3-repeated-hedge-boilerplate",
  "title": "Same hedge sentences repeated a dozen times across sections",
  "body": "The sentences 'Refusal suggests a missing listener or active rejection, possibly by an intermediary', 'Timeout leaves addressing, routing, filtering, and availability open', and 'a response alone does not identify the process or file' recur at lines 75, 151, 212, 269, 317, 323, 337, 341, 345, 355 and 363, with the same idea again in quiz answers. Patterns and Anti-Patterns, Decision Framework and Common Mistakes restate Options A and B and the diagnostic split. Lines 349-357 add a third metaphor and a closing paragraph about reducing fear and future tools.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 269,
   "end_line": 269,
   "claim_type": "present"
  },
  "verbatim": "Refusal suggests a missing listener or active rejection, possibly by an intermediary.",
  "why_wrong": "BLOAT per the review contract (repetition and duplication). The learner loses nothing a stated outcome needs if one consolidated explanation is kept.",
  "smallest_fix": "Keep one authoritative statement of what refusal, timeout, an HTTP error and a matching page each do and do not establish (the section at line 337), and reduce the other occurrences to a cross-reference or a single clause. Cut or merge the closing paragraphs at lines 349-357 and the restated content in Patterns and Decision Framework.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B4-option-b-no-vm-creation",
  "title": "Option B gives no VM-creation steps and no explanation of provider-specific assumptions",
  "body": "Option B reduces creating the VM to one sentence. No module in the track teaches provisioning a VM, downloading a key pair, or setting inbound rules (0.10 is conceptual). The login user ubuntu in the ssh command is specific to some providers' Ubuntu images and is not flagged. Inbound SSH is opened with no advice to limit the source address, though the page otherwise stresses safety.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 230,
   "end_line": 230,
   "claim_type": "present"
  },
  "verbatim": "Create the smallest free-eligible Ubuntu VM you can find, download the SSH private key when prompted, and allow inbound SSH on port 22 plus inbound HTTP on port 80.",
  "why_wrong": "UNDER-EXPLANATION: a skipped key skill for an absolute beginner who chooses Option B, plus an unexplained provider-specific username and an open SSH rule with no safety note.",
  "smallest_fix": "Add a short provider-neutral checklist (Ubuntu LTS image, download and protect the key, the default login user varies by provider and is shown in the console, restrict SSH source to your own IP where the console allows). Alternatively state that Option B requires an instructor-provisioned VM and is read-only otherwise.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N1-ubuntu-default-index-name",
  "title": "Default Ubuntu page may be index.nginx-debian.html, so the break task may not break",
  "body": "The page tells the learner to delete the default content of /var/www/html/index.html and later renames that file to break the site. Ubuntu's nginx package is believed to ship index.nginx-debian.html, so there may be no default index.html to delete, and renaming index.html would fall back to the welcome page instead of an error. I could not confirm this (the Ubuntu tutorial opened does not name the file; Debian source fetches returned 404), so this is unverified and non-blocking. The page does hedge that another index file can affect the result.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 277,
   "end_line": 277,
   "claim_type": "present"
  },
  "verbatim": "Delete the default content and paste the cloud version of your page.",
  "why_wrong": "If the default file has another name, the instruction is imprecise and Task 3's expected observation is unexplained.",
  "smallest_fix": "On a VM, list /var/www/html before editing, and name in Task 3 the default welcome file that may still be served after the rename.",
  "sources": [
   "https://ubuntu.com/tutorials/install-and-configure-nginx"
  ]
 },
 {
  "id": "N2-orphan-sources-and-thin-table",
  "title": "Content-free runtime table and orphan Sources entries",
  "body": "The runtime table gives no useful description or terms ('Docker environment', 'Container management', 'Check current terms' on every row). The Sources list contains entries that back no current page claim (Oracle, Google and AWS free-tier pages, Docker Personal, Inside NGINX), which pads the list and implies support the page does not claim.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 101,
   "end_line": 101,
   "claim_type": "present"
  },
  "verbatim": "| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Docker environment | Check current terms |",
  "why_wrong": "Volatile pricing is correctly deferred, but the table teaches nothing, and the orphan sources are not tied to page claims.",
  "smallest_fix": "Replace the table with one sentence linking the runtimes, and prune the Sources list to entries that back a page statement.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N3-unanswered-stop-and-think",
  "title": "Stop-and-think prompts not answered; port-in-use failure has no recovery",
  "body": "Line 143 asks what happens when Docker binds to a port already in use and never answers; line 319 asks which URL path requests /var/www/html/assets/logo.png and never states /assets/logo.png. For the port-in-use case a failed docker run may leave a created container holding the name my-website, which the guard text forbids adopting or removing. I could not verify that Docker behavior.",
  "priority": "P3",
  "confidence": 0.55,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 143,
   "end_line": 143,
   "claim_type": "missing"
  },
  "verbatim": "while another background application is already actively listening on that exact same port?",
  "why_wrong": "A key failure mode is posed but not taught, and the recovery path conflicts with the page's own collision rule.",
  "smallest_fix": "Add a one-line answer under each prompt (bind fails, choose another host port) and say what to do about a created-but-not-started container from your own failed run.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-11-r2: call 2 of 2, delta review

- reviewed head: `fce6dd8379541358d135c4df47556457d0c066c8`
- run nonce: `47953dcd28c9465aa85fa0e3b7c477d0`
- verdict: `correct` (confidence 0.74)

### Explanation (verbatim)

Delta review, call 2 of 2 (not acceptance). Verdict: B1-B4 are closed and no blocking defect remains, with residual non-blocking items below.

Task 1: HEAD is fce6dd8379541358d135c4df47556457d0c066c8. The diff against 8186da6 touches one file, with 64 insertions and 40 deletions. The page sha256 is 87ebc6a0f8177ee6e224d7730a9b8a8d61de5867d80112971a819109c36140ab, which matches the expected value. I read the whole page (614 lines).

B1 closed. Option A trace: the container is created and the page copied in the body. The cleanup text says to keep the container running for the exercise and to use the cleanup block when Task 3 requests it and after the exercise. In Task 3 the cleanup block empties the variable and frees the name my-website. The guarded 9090 create then re-sets the variable to the new ID. Task 4 runs cleanup, the 8080 create and the guarded copy, which works because the host index.html persists. Task 5 and a new success criterion add cleanup at the end. The cleanup text now says an empty variable means the guard does nothing, and to stop and recover the creation evidence with the instructor. The cloud teardown now opens with 'After the Hands-On Exercise'. Residual: the bare exit code block directly follows that sentence with no lead-in, so a top-to-bottom reader could disconnect before Tasks 1-4, which use SSH. This is non-blocking (finding F1).

B2 closed. Outcome 3 now reads curl, docker ps, systemctl and careful path inspection. Grep for port check and firewall finds no remaining promise of port or firewall checks. 'Firewall' survives only as a provider concept, and 'listener binding' is named in several places with no command taught (non-blocking). The docker ps PORTS sample and the curl (7) line are both labelled synthetic with 'wording and timing vary'. The PORTS format 127.0.0.1:port->port/tcp matches the Docker container ls reference. The curl line matches Daniel Stenberg's 2017 mailing-list reply to the cited curl.se thread. Newer curl versions word this message differently, and the label covers that.

B3 mostly closed, accepted as closed. The anchor #reading-server-symptoms-like-an-operator exists as the H2 'Reading Server Symptoms Like an Operator'. Line 343 carries the full statement: refusal suggests a missing listener or active rejection, possibly by an intermediary; timeout leaves routing, filtering, availability and addressing as hypotheses; an HTTP error establishes an exchange. The prediction-reveal and cloud-result pointers go to that anchor. The prose duplicates in Patterns, Anti-Patterns, Decision Framework and the symptom-section closings are removed. No safety protection was lost: authorization, loopback publication, key protection, billing and cleanup warnings are all intact. The 'a response alone does not identify the process or file' hedge still appears in about six distinct contexts (lines 148, 216, 321, 329, 357, 369 plus quiz answers). That is dense but no longer verbatim boilerplate, and I left it non-blocking; it keeps D6 at 4.

B4 closed. The Option B paragraph requires an instructor-provisioned disposable Ubuntu VM or one created with the provider's official quickstart. It links the EC2 getting-started guide, which I opened, and otherwise says to read without executing. It restricts SSH to a trusted source address where the provider allows it. It does not claim the module teaches VM creation. YOUR_USER is used consistently: the grep finds no 'ubuntu@' and YOUR_USER appears in the ssh line and the replace note. I opened the AWS connection-prerequisites page and confirmed 'Ubuntu – ubuntu' in its default-username list. Caveat: the getting-started guide recommends Amazon Linux and a default security group that does not open port 80. The page does say Ubuntu and HTTP 80, so this is non-blocking.

N1 partly closed. The broken.html task now says the goal is to observe whether custom content disappears, not to guarantee an HTTP error, and tells the learner to record a welcome page. This is honest. Whether Ubuntu's package default file is index.nginx-debian.html is UNKNOWN to me from sources opened; the Ubuntu tutorial does not name it. The hedging suffices, and 'serves files from /var/www/html/' is supported by the Ubuntu tutorial: 'Default page is placed in /var/www/html/ location'.
N2 closed: the tool table became one sentence and the five orphan sources were removed.
N3 closed: the answers are correct. The Docker troubleshooting page confirms the 'port is already allocated' bind failure, and /assets/logo.png is correct. The leftover-container advice is safe: stop, have the lab owner verify, do not adopt an unverified container. It is heavy for a solo learner.
N4 mostly closed: Socratic hint blocks were added to the tasks, but they are not tiered concrete hints.
N5 UNKNOWN or partly: the Sources list was rebuilt. The page itself carries no citation-seed history.

New-claim verification, URLs actually opened: https://docs.docker.com/reference/cli/docker/container/ls/ ; https://curl.se/libcurl/c/libcurl-errors.html (CURLE_COULDNT_CONNECT 7 is 'Failed to connect() to host or proxy'); https://curl.se/mail/lib-2017-02/0075.html ; https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connection-prereqs-general.html ; https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html ; https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/ (the section exists; the exact fragment id was not verified) ; https://hub.docker.com/_/nginx (shows /usr/share/nginx/html in examples; it does not state 'default' outright) ; https://ubuntu.com/tutorials/install-and-configure-nginx (the /var/www/html default). The curl man-page exit code 7 fetch was truncated, so that wording is UNKNOWN. The new Sources entries support page claims, except that 'AWS: security group rules' backs only the generic 'arrange inbound HTTP and SSH' sentence (weak, not an orphan). Internal links resolve: the cloud-native-101, kubernetes-basics, module-0.10 and linux index files exist. No heading was removed by the delta; the only heading change is the added Task 5. Not verified: the Docker 28.0.0 release note, docker-group root-equivalence, the kubedojo.dev sample link and snapshot billing. These are unchanged by the delta.

Scores from a full read, using the call-1 labels. D1 outcome clarity 5; D2 outcome-to-teaching alignment 4; D3 accuracy and explanation 4; D4 examples and illustration 4; D5 practice and assessment 4; D6 concision and flow 4; D7 sources and evidence honesty 4; D8 safety and learner support 5. D total 34/40, which meets the 33 floor with every D at 4 or above. L1 executability 4; L2 verification 4; L3 cleanup 4; L4 feedback and hints 4; L5 safety 5. L total 21/25, which meets the 21 floor with every L at 4 or above. Scores are borderline on D6, L1 and L4.

BLOCKING: none. NON-BLOCKING: F1 (exit block placement), the quickstart defaulting to Amazon Linux and not opening HTTP, untaught 'listener binding' checks, hint tiers, residual repeated hedges.

Provenance: reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family), run in Claude Code, outside the author's OpenAI family. Checks performed by me: git, sha256, whole-page read, greps and the source fetches listed above. Supplied but not independently run: the PR body claims beyond the diff. Limits: no Docker, VM, nginx or cloud account exists on this run, so the lab is not run and is judged as prose and design only.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1-exit-block-after-teardown-sentence",
  "title": "Bare exit block follows the post-exercise teardown sentence without a lead-in",
  "body": "The Option B closing paragraph now says teardown happens after the Hands-On Exercise, but the unlabelled exit code block sits directly under it. A learner reading top-to-bottom may run exit before Tasks 1-4, which edit and test over the SSH session. Recovery is easy (ssh again), so this is minor.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.11-your-first-server.md",
   "start_line": 331,
   "end_line": 335,
   "claim_type": "present"
  },
  "verbatim": "After the Hands-On Exercise, disconnect and inventory the resources created specifically for this authorized disposable lab.",
  "why_wrong": "The exit command is presented without saying it is to be run only once the exercise is finished, which re-creates a small ordering ambiguity for Option B.",
  "smallest_fix": "Add a lead-in such as 'When the exercise is finished, leave the SSH session:' before the exit code block, or move the block into Task 5.",
  "sources": [
   "none"
  ]
 }
]
```
