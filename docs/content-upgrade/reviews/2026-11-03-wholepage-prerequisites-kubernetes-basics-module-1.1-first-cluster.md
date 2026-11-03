# Reviews of prerequisites/kubernetes-basics/module-1.1-first-cluster.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for all three: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. No cluster lab was run by any reviewer (no Docker, kind or cluster exists on the review host). Call 3 was a CTO-granted pinned verification round limited to the one remaining blocker (lab expected outcomes and a reflection answer) and the score margins.

## kd-wp-kb11-r1: call 1 of 2, whole-page review

- reviewed head: `4447642c1183ff1ca96367265ae4f333cac23a9c`
- run nonce: `c091d0cd413745d5bff0a7af4fc05692`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DISPOSITION: revise (confidence 0.8). Digest check: sha256sum of the page gives e91070a7f3ce9258903accd574da3bd40737018f7e48524208757eec1e9d55a6, which matches the supplied digest. HEAD is 4447642c1183ff1ca96367265ae4f333cac23a9c. I read all 806 lines.

MODULE SCORES (D1-D8). Total is 30/40 and the 33/40 bar is missed. D6 and D7 are below the floor of 4.
- D1 Learning outcomes 4: five clear outcomes. LO1 says '1.35+' but the check script (line 286) rejects any client other than 1.35.x.
- D2 Scaffolding 4: the component model leads into kind, then kubeconfig, bootstrap and troubleshooting, and the order is sound. There are abrupt scaffold sentences (lines 131, 262, 377, 394).
- D3 Active learning 4: four predict-then-reveal boxes, a seven-question quiz and a lab.
- D4 Real-world connection 4: shared-cluster blast radius, context mistakes, leaked kubeconfig.
- D5 Assessment alignment 4: quizzes are tagged to LOs. LO2 and LO5 get one quiz item each, and nothing asks the learner to practice reading Docker logs for LO3.
- D6 Cognitive load 3: BLOAT. Lines 38 and 40 restate the same idea in two paragraphs. Orchestra, port and 'cultural lesson' paragraphs repeat one point. The four predict scenarios appear twice (the scheduler one three times). Four 'next section does not describe this' filler lines.
- D7 Engagement 3: padded intro and generic analogies. The 'frozen card' block is appended after Success Criteria and 'frozen' is never defined. The Did-You-Know items are weak (item 1 is not a fact).
- D8 Practitioner depth 4: skew, context safety, image loading and HA caveats are covered.

LAB SCORES (L1-L5). Total is 14/25 and the 21/25 bar is missed. L1, L3, L4 and L5 are below the floor of 4.
- L1 3: the tasks are prescriptive and the solutions are copy-paste.
- L2 4: easy to hard, plus an optional stretch task.
- L3 3: tasks 1-4 are run-and-observe. Only the Task 6 failure is a result to interpret, and nothing asks the learner to predict or explain.
- L4 2: no tiered hints. Solutions are bare answers in <details>, and there are no 'if you see X it means Y' notes.
- L5 2: no reflection or transfer prompt. The optional HA task has no teaching behind it.

source_status: PARTLY SUPPORTED. I judged about 9 claims against sources I opened.
- Supported (5): kubectl one-minor skew (policy and install page); the specific-version kubectl download and .sha256 procedure; kind --image and 'check the release notes for your kind version'; kind delete of an absent cluster succeeds; docker group is root-equivalent (relevant to the advice at line 474).
- Contradicted (2): the page's k3s 'stripped-down, modified' and reduced-parity framing, and the pinned image tags (finding 2 below).
- Unsupported (1): the minikube fixed-size-disk and slow-startup claims.
- OrbStack link: the page exists and is relevant.
I did not fetch the Kubernetes components or nodes pages, the kubeconfig page, the Docker Desktop and Ubuntu install pages, the etcd docs or the port-forward docs. The component descriptions in Section 1 (API server, etcd, scheduler, controller manager, kubelet, kube-proxy) and the kubeconfig description rest on my own knowledge and are not verified this turn.

lab_execution: NOT RUN. The host has no Docker, kind or cluster, and I executed nothing. I judged the bash helpers only as prose and design: guards, receipts, cleanup and the expected-output hedges. The prior p07a record says only stubbed macOS control-flow cases were run and the Docker probe failed.

BLOCKING FINDINGS (4; each fits a small PR):
1. BLOAT (lines 38 and 40, and lines 131, 262, 377, 394, 748-786). Duplicate intro paragraphs, scaffold filler, and predict scenarios repeated as cards.
2. Image pins vs kind version (lines 276, 339, 595). The kind version is never stated, and the two pinned tags do not come from one kind release.
3. Docker-group advice (lines 472-475). `sudo usermod -aG docker $USER` is given with no warning that it grants root-equivalent access.
4. Lab floors (lines 593-598 and 602-735). No tiered hints, no predict or explain prompts, no transfer question.

NON-BLOCKING FINDINGS:
- Tool-comparison table (lines 139-141): the minikube claim is unsupported and the k3s claim is contradicted by the k3s docs. I put this as a P2 finding in the findings list because LO2 relies on it.
- LO1 and the patterns table say '1.35+', but line 286 forces exactly v1.35.x. The page hard-codes a version that, per the kind release page, is now two minors behind kind's current default (1.37.0). Hedge this as time-dependent.
- Line 438 sample node table is not labelled illustrative. Ages and version are synthetic, and the same is true of the 'Your terminal output should now accurately reflect' wording.
- Line 460: kind chooses a random host port by default, so `lsof -i :6443` is rarely the right check. `netstat -tulpn` is Linux-only but is offered for macOS too.
- Lines 22-26: `kubectl version --client` sits in the opening block before any install step, with the alias paragraph, which is an unexplained transition.
- Frontmatter declares a Killercoda lab (prereq-k8s-1.1-first-cluster, 25 min), but the body never mentions it. I did not and could not verify that scenario.
- Lines 748-786: the Success Criteria checklist item and cards A-D sit under Success Criteria and the page ends on them.

OMITTED-CLAIM DISCOVERY: the page makes a version-compatibility claim implicitly (these tags work with whatever 'release binary' the learner downloads) that nobody sourced. Line 336 says the default cluster 'installs networking' and runs kube-proxy and CoreDNS, which I did not verify. The docker-group claim and 'kubectl supports one minor skew' were in the evidence; the kind-version claim was not.

URLS ACTUALLY OPENED (success): https://github.com/kubernetes-sigs/kind/releases; https://kubernetes.io/releases/version-skew-policy/; https://docs.docker.com/engine/install/linux-postinstall/; https://kind.sigs.k8s.io/docs/user/quick-start/; https://docs.k3s.io/; https://minikube.sigs.k8s.io/docs/drivers/; https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/ (first 100000 of 112429 characters); https://docs.orbstack.dev/docker/. FAILED, so UNKNOWN: https://github.com/kubernetes-sigs/kind/releases/tag/v0.30.0 (socket hang up). I therefore did not confirm that v1.34.0 comes from kind v0.30.0, and the claim in finding 2 is limited to what the v0.31.0 and v0.33.0 notes show. Not opened: Docker Desktop, Ubuntu install, kind known-issues and configuration pages, kubeconfig, components, nodes and etcd pages, port-forward.

PROVENANCE: reviewer is Claude Code running claude-sonnet-5-5 (Anthropic family), outside the OpenAI/Codex author family. Review kind: whole-page review, call 1 of 2 (fresh budget under OO-KD-REREVIEW-1102). Harness: Claude Code CLI with the Agent SDK, read-only checkout. Checks performed by me: sha256sum, full page read, review-contract and rubric read, page-reviews.json and p07a record read, and the web fetches above. Checks supplied and not re-run: the p07a record's stubbed shell tests and its kind v0.33.0 source citations. I did not read the entries under docs/content-upgrade/reviews/*source-catalog*.json beyond locating this page's entry, whose URL is a pinned old blob. Limits: no execution, and the kind v0.30.0 note could not be fetched.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1-bloat-duplicate-and-filler",
  "title": "BLOAT: duplicate intro paragraphs, 'does not describe' filler, repeated predict scenarios",
  "body": "Lines 38 and 40 say the same thing twice: a cluster is a distributed control system with an API, scheduler, controllers, runtime and state, and a mistake in a shared environment spreads. Lines 38-46 add a third and fourth paragraph restating the same blast-radius point. Lines 131, 262, 377 and 394 each close a predict block with a sentence saying what the next section does NOT cover, which teaches nothing. Lines 748-786 then repeat the same four predict scenarios (scheduler crash, leaked kubeconfig, docker ps count, port-forward tunnel) as cards A-D with the same answers. The scheduler case is also quiz item 1, so it appears three times. The cards sit after Success Criteria, and 'frozen' is never defined.",
  "priority": "P2",
  "confidence": 0.85,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 38,
   "end_line": 40,
   "claim_type": "present"
  },
  "verbatim": "A cluster is not just another command-line tool you install and forget.",
  "why_wrong": "The review contract treats padding, repetition and abrupt unexplained transitions as equally blocking with under-explanation. Nothing the learner needs is lost by removing the second paragraph, the filler sentences or the repeated cards.",
  "smallest_fix": "Delete line 40. Delete the four 'The next section/paragraph ... does not describe/answer ...' sentences at lines 131, 262, 377 and 394. Either remove cards A-D or turn them into new, different transfer scenarios, and move whatever remains above Success Criteria. Trim the lines 44-46 restatements so the goal and the cultural lesson are each stated once.",
  "sources": [
   "docs/review-contract.md: BLOAT and UNDER-EXPLANATION definitions (lines 117-121)"
  ]
 },
 {
  "id": "F2-kind-version-image-pins",
  "title": "kind version never stated; pinned node-image tags are not from one kind release and are not digest-pinned",
  "body": "The page says to install whatever kind release binary the Quick Start offers (line 276) and then pins `kindest/node:v1.35.0` (line 339) and `kindest/node:v1.34.0` (line 595) by bare tag. kind's release notes list pre-built images per kind release and say to use the `@sha256` digest to guarantee an image built for that release. The kind v0.31.0 notes (opened) list v1.35.0 but v1.34.3, not v1.34.0. The v0.33.0 notes, the current Latest, list v1.37.0, v1.36.4, v1.35.8 and v1.34.11, so neither pinned tag appears there. The v0.32.0 notes say full compatibility of node images across kind releases is not guaranteed. The quick-start says to check the release notes for your kind version. The page never tells the learner which kind version to use, so a learner on the current release is running tags built for older releases and the 'version-pinned, reproducible' claim is not backed. I could not fetch the v0.30.0 notes, so where v1.34.0 comes from is UNKNOWN.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 339,
   "end_line": 339,
   "claim_type": "present"
  },
  "verbatim": "lesson_create dojo-basics --image kindest/node:v1.35.0",
  "why_wrong": "Reproducibility and the 'pin to avoid drift' teaching depend on image and kind release matching. Today the stated pin pair is not published together by any single release I could verify, and the page gives no kind version to check against.",
  "smallest_fix": "State a specific kind release at the install step. Use node tags and digests from that release's notes for both clusters, for example the v0.33.0 images v1.35.8 and v1.34.11, which still satisfy the v1.35 client check. Or add a dated note that tags come from different kind releases and may behave differently. Update the references in lines 336, 425, 567, 595-597, 609, 643, 697 and 717 consistently.",
  "sources": [
   "https://github.com/kubernetes-sigs/kind/releases",
   "https://kind.sigs.k8s.io/docs/user/quick-start/"
  ]
 },
 {
  "id": "F3-docker-group-sudo-advice",
  "title": "Unqualified `sudo usermod -aG docker $USER` advice",
  "body": "The troubleshooting code block gives `sudo usermod -aG docker $USER` as a fix for a permission-denied Docker socket, with only a note that a new login is needed. Docker's own post-install page states that membership of the docker group grants root-level privileges. The page otherwise stresses authorized access, a private kubeconfig and no public exposure, and Ubuntu setup says to confirm the account has authorized access. This advice contradicts that, and an absolute beginner may run it on a shared or remote machine.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "security",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 470,
   "end_line": 475,
   "claim_type": "present"
  },
  "verbatim": "sudo usermod -aG docker $USER",
  "why_wrong": "It grants root-equivalent host access with no stated consequence, on a page whose lane rules require safe advice about sudo and trust.",
  "smallest_fix": "Keep `systemctl status docker`. Replace the usermod line with a sentence-level warning that the docker group is root-equivalent and the change should be made only on a machine you own, with a pointer to Docker's Linux post-install page for the rootless or group options. Also drop the line from the runnable code block.",
  "sources": [
   "https://docs.docker.com/engine/install/linux-postinstall/"
  ]
 },
 {
  "id": "F4-lab-floors-hints-prediction-transfer",
  "title": "Lab misses L1/L3/L4/L5 floors: no tiered hints, no predict/explain prompts, no transfer question",
  "body": "The six tasks are run-and-observe. The solutions section gives only the finished commands. There are no concept, narrowed and command-level hints, no 'if you see X it means Y' feedback, and no reflection or transfer question at the end. Task 6 does ask the learner to observe a failure. Nothing asks them to predict the result of `kubectl version` on the two clusters (Task 4) or of `kubectl get nodes` after the kill (Task 6), or to explain why the failure appears. Success Criteria also contains self-report items such as 'You identified and explained the structural components' that nothing in the tasks elicits. Scores: L1 3, L3 3, L4 2, L5 2; the total is 14/25 against 21/25.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "tests",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 593,
   "end_line": 598,
   "claim_type": "present"
  },
  "verbatim": "1. **The Baseline Cluster Initialization:** Create a standard single-node cluster named `primary-dojo`.",
  "why_wrong": "The rubric floor for an applicable lab is all of L1-L5 at 4 or above. Without hints, predictions and a transfer prompt the learner can follow the solutions without reasoning, and the stated LO3/LO4 diagnosis outcomes are practiced only by the quiz.",
  "smallest_fix": "Add a one-line 'predict before you run' to Tasks 4 and 6. Add 2-3 tiered hints (concept, then component, then command) to Tasks 1, 3 and 6, including common errors such as the name-collision refusal or a kubectl pointing at the wrong context. End with one reflection or transfer question, for example: which signals would tell you whether a refused connection is a dead container, a wrong context or a wrong port?",
  "sources": [
   "docs/quality-rubric.md: Lab Rubric L1-L5",
   "docs/review-contract.md: lab pass threshold (line 116)"
  ]
 },
 {
  "id": "F5-tool-comparison-unsupported",
  "title": "Tool-comparison table: minikube disk claim unsupported, k3s framing contradicted by k3s docs",
  "body": "The table says minikube VM mode 'uses fixed-size virtual disks, protecting host disk space', and that minikube is 'heavily resource intensive' with 'slower startup times'. The minikube drivers page I opened says nothing about fixed-size disks or startup speed. It lists the docker container driver as well as VM drivers. The k3d row says k3s is 'a stripped-down, modified Kubernetes distribution, which may lack 100% parity'. The k3s docs call it 'a fully compliant Kubernetes distribution' with lightweight enhancements. The sources list also has no minikube, k3s or k3d entry.",
  "priority": "P2",
  "confidence": 0.65,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 139,
   "end_line": 141,
   "claim_type": "present"
  },
  "verbatim": "Uses k3s (a stripped-down, modified Kubernetes distribution), which may lack 100% parity with cloud providers.",
  "why_wrong": "LO2 asks learners to choose between tools using this table. Specific claims without source support, one contradicted by the project's own docs, can lead to wrong choices.",
  "smallest_fix": "Remove the fixed-disk and startup-time claims, or source them with a minikube/k3d citation. Reword the k3s cell to say k3s is a lightweight, conformant distribution that bundles its own components (containerd, Flannel, Traefik), so behavior can differ from a plain kubeadm cluster. Add the minikube, k3s and k3d docs to Sources.",
  "sources": [
   "https://docs.k3s.io/",
   "https://minikube.sigs.k8s.io/docs/drivers/"
  ]
 }
]
```

## kd-wp-kb11-r2: call 2 of 2, delta review

- reviewed head: `876ee459c97c2036eef481b4f7d354642950a653`
- run nonce: `384a1bfed8ce4b9fb3fca6b08328734d`
- verdict: `incorrect` (confidence 0.68)

### Explanation (verbatim)

TASK 1. HEAD is 876ee459c97c2036eef481b4f7d354642950a653. The diff against 4447642c1 touches one file, with 48 insertions and 94 deletions (142 lines). The page sha256 is 88b12a36740d94913b0bfcf21c5bf8cecc3b30c6914af56161ccc38f974b6191, which matches. Word count fell from 9775 to 9181 (about -6%).

F1-F5 STATUS.
- F1 closed. The duplicate intro paragraphs, the 'does not describe' filler and the frozen card block are gone. A grep for frozen, card, 'the table', 'next section', usermod, above and earlier finds no dangling reference; the only 'above' hit is a legitimate use ('compared above'). The scheduler predict now appears once, and the Did-You-Know has three plain facts. Weak but not blocking.
- F2 closed. The page names kind v0.33.0 and uses digest-pinned v1.35.8 and v1.34.11 images from that one release. LO1 now says '1.35', which matches the forced v1.35.x kubectl check. kubectl v1.35.0 is within skew of both servers.
- F3 closed, with a minor gap. `usermod` is removed. Line 452 says the docker group grants root-level privileges, accept only on a machine you own, and links Docker's post-install guide. A working path exists: that link, plus the prerequisite module 1.2 (`prerequisites/cloud-native-101/module-1.2-docker-fundamentals.md` lines 49-56), which still contains `usermod` and the matching trade-off warning. The in-page route is thin. Section 4 only says 'confirm your account has authorized access to its socket', and `docker version || exit 1` is the first command a Linux learner hits.
- F4 partly closed. Tiered Nudge/Stronger hints exist for Tasks 1, 2, 3, 4 and 6; there is no hint 5, though optional Task 5 has a solution. Every task has a predict prefix. A reflection prompt was added at line 725. The gap is on the answer side: see the finding and the L4 score.
- F5 closed. The minikube cell now reads 'Multiple driver choices' and the k3s cell reads 'compliant Kubernetes distribution with bundled components and its own defaults'. The minikube drivers page says VM, container or bare-metal. The K3s docs say 'fully compliant Kubernetes distribution' and list bundled containerd, Flannel, CoreDNS and Traefik. Both cells match.

JUDGE POINTS.
(1) The kind claim is true. The release page, fetched with WebFetch, is titled v0.33.0 and lists v1.35.8@sha256:07b2536e...323c0 and v1.34.11@sha256:44e222ee...d67d, matching every digest on the page character for character. The release notes recommend a v1.37.0 default image, and the page rightly does not use it. A direct GitHub API fetch failed with a non-JSON response, so the digest match rests on the WebFetch summary only. The page's commands, version checks and LO1 are consistent.
(2) A working path to docker exists via the link and the prerequisite, and it is honest about the trade-off. It is not self-contained.
(3) Not yet. Hints and predict prefixes are present, so L3 is lifted. Expected outcomes are mostly implied by solution comments. Tasks 1 and 2 never state the expected node count or reference names explicitly. The reflection has no answer key. Nothing tells a learner who sees something unexpected what that means, apart from the single Task 4 wrong-context hint.
(4) Yes. Every LO is still taught with a worked example. The inbound anchor from module 1.2 (`#section-4-bootstrapping-and-verifying-the-first-cluster`) still resolves. No removed heading is linked from elsewhere.
(5) The minikube and k3s cells match the docs (see F5).

NON-BLOCKING ITEMS.
- The node table is now labelled 'Illustrative output': fixed.
- Host-port check: fixed. It uses `kubectl cluster-info` and `docker port`, and the netstat command is marked Linux-only.
- `kubectl version --client` in the opening: removed.
- The frontmatter still declares the Killercoda lab, which the body never mentions. This is unchanged and was a deliberate non-addition.
- The hint list skips 5.

NEW CLAIM VERIFICATION. URLs actually opened: github.com/kubernetes-sigs/kind/releases/tag/v0.33.0, minikube.sigs.k8s.io/docs/drivers/, docs.k3s.io/. All fetches succeeded and the content is as described above. I did not open the Docker post-install guide or the kind Quick Start; the 'checked 2026-11-03' claim and the added links are UNKNOWN beyond the three URLs fetched. I checked the repository's module 1.2 and inbound links locally.

SCORES. Call-1 labels were not supplied beyond D1-D8 and L1-L5, so I use those numbers.
D1 4, D2 4, D3 4, D4 4, D5 4, D6 4 (was 3; bloat removed, helper block still dense), D7 4 (was 3, borderline; the analogies are kept but the Did-You-Know is still bland), D8 5 (digest pinning, receipt-guarded deletion, skew, log export). Sum = 33/40. That meets the D floor with margin 0, and no D is below 4. It holds only because of the D8 5.
L1 4, L2 4, L3 4, L4 3, L5 4. Sum = 19/25, which is 2 below the 21 floor, and L4 is below 4. The cause is that predictions and the reflection have no stated expected outcome or key, and there is little diagnostic feedback.

BLOCKING: the lab feedback gap (finding below). NON-BLOCKING: the thin in-page docker-socket path, the hint-5 gap, the Killercoda frontmatter, the weak Did-You-Know. I have not claimed the lab reaches 21 after the fix; the fix should lift L4 and likely L5.

PROVENANCE. Reviewer: Claude Sonnet 5.5 (claude-sonnet-5-5), Anthropic family, via Claude Code (Agent SDK) with the sources MCP available and filesystem and web tools. The author is OpenAI/Codex gpt-6.1-terra, so this is outside the author's family. This is a delta review, call 2 of 2, not acceptance. CHECKS PERFORMED: HEAD, diffstat, sha256 and word counts; the full-page read; the diff read; greps for dangling references and inbound fragments; the WebFetch calls listed above; the module 1.2 read. SUPPLIED AND NOT INDEPENDENTLY VERIFIED: the PR body table beyond the three fetched pages. LIMITS: no Docker, kind or cluster exists on this host, so commands are judged as prose and design only. The GitHub API check failed, so digests are confirmed by WebFetch only.

### Findings (verbatim JSON)

```json
[
 {
  "id": "lab-answer-key",
  "title": "Lab predictions and the final reflection have no stated expected outcome or key, leaving L4 below 4 and the lab total at 19/25",
  "body": "The delta added predict prefixes to Tasks 1-4 and 6, tiered hints, and one closing reflection question. Nothing tells the learner what the correct prediction is, except implicitly through solution comments. Tasks 1 and 2 do not state the expected node count or reference names. The reflection at line 725 asks which signals separate a stopped node container from a wrong context or a wrong port, but gives no worked answer. Section 6 only supplies the ingredients. There is no 'if you see X, it means Y' feedback beyond the single Task 4 wrong-context hint.",
  "priority": "P2",
  "confidence": 0.65,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 725,
   "end_line": 725,
   "claim_type": "present"
  },
  "verbatim": "Before cleanup, reflect: which signals would distinguish a stopped node container from a wrong context or a wrong port?",
  "why_wrong": "A prediction or transfer prompt with no expected outcome gives the learner no self-check and no diagnostic feedback. That keeps L4 at about 3 and the lab total about 2 below the 21/25 floor after the fix round. This was the F4 ask: 'predict/explain prompts and a transfer question'.",
  "smallest_fix": "Add a collapsed answer under the reflection stating the three discriminating signals: `docker ps -a` shows the node exited, `kubectl config current-context` shows the wrong context, and `docker port <node>` differs from the server address in `kubectl cluster-info`. Add one expected-outcome line to each of the Task 1-4 solutions (one node, a 127.0.0.1 random port, contexts named kind-<name>, server versions v1.35.8 vs v1.34.11). Optionally add a one-line 'if you see X, it means Y' note for Task 4 and Task 6.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-kb11-r3: round 3, CTO-granted pinned verification of one blocker and the score margins

- reviewed head: `28a688ebf741dd4f952325e9c48adee0dd50bc00`
- run nonce: `e071e56e6c504c488f59913080722ccf`
- verdict: `correct` (confidence 0.78)

### Explanation (verbatim)

Pinned verification round, call 3 of the CTO grant. This is not an acceptance review.

Task 1 results (git and sha256 output from this turn):
- HEAD is 28a688ebf741dd4f952325e9c48adee0dd50bc00.
- The diff against 876ee459c is one file, 15 insertions and 0 deletions.
- The page sha256 is 57c7678b25011b8ff0883f7a2e03c06c8a4f6205621f199e9a732fe7edeff514, which matches the expected value.
- I read the full 15-line delta and all 775 lines of the page.

The delta adds:
- a Hint 5 for optional Task 5;
- expected-outcome lines under the Task 1, 2, 3 and 4 solutions;
- a collapsed Reflection answer.

lab-answer-key: CLOSED. I checked each added line against the page's own commands and pins.
- Task 1: one node and an API address on 127.0.0.1 with a random port. This matches the single-node `lesson_create`, the cluster-info example (127.0.0.1:42315) and the "kind maps a random high-numbered port" sentence.
- Task 2: cluster, user and context are all named kind-primary-dojo. This matches the page's `kind-<name>` convention.
- Task 3: legacy-dojo runs v1.34.11 and primary-dojo runs v1.35.8. This matches the pinned images, and the Task 3 predict ("same server version?") now has an answer.
- Task 4: kind-primary-dojo reports v1.35.8 and kind-legacy-dojo reports v1.34.11. This matches the use-context steps.
- Task 6: the existing solution text already answers the predict prompt (hang or connection refused).
- Reflection: the three signals are correct and consistent with the page. `docker ps -a` shows an exited container after `docker kill`. `kubectl config current-context` is taught in the anti-pattern table. `docker port` and `kubectl cluster-info` are both taught in Task 1.
- Hints: hints 1-6 are now complete.

I found no factual error or inconsistency. The only command the page has not taught is the `-a` flag in `docker ps -a`; the page only shows plain `docker ps`. That is trivial and non-blocking.

Delta-introduced defects: none.
- The `<details>` blocks are balanced.
- Blank lines around the summary and body follow the page's existing style.
- No block is empty.
- There is no contradiction.
- At 15 lines the delta adds no bloat, and F1-F3 and F5 were not touched.

Scores from a full read, summed by me.
- D: D1 4, D2 4, D3 4, D4 4, D5 4, D6 4, D7 4, D8 5. The sum is 33/40. Every D is at least 4. The margin is 0 over the 33 floor; only D8 is above its per-criterion floor, by 1. The delta did not raise D5 to 5 because Task 4's predict still lacks a client-version answer, and it neither raised nor lowered the other D scores.
- L: L1 4, L2 4, L3 5, L4 4, L5 4. The sum is 21/25. Every L is at least 4. The margin is 0 over the 21 floor. L3 is the swing criterion: it rises from 4 to 5 because every task now has an expected outcome and failure-meaning feedback. L4 rises from 3 to 4 because Task 5 now has its hint and every task has a nudge and a stronger hint. L5 stays at 4 because the reflection now has an answer but transfer beyond the lab is modest.

BLOCKING: none.

NON-BLOCKING:
- Task 4's predict asks for client and server versions, but the expected outcome gives only server versions. The client is v1.35.x per the setup check.
- The Task 2 predict ("which entries a context must connect") is answered only implicitly.
- The Killercoda lab in the frontmatter is not mentioned in the body.
- The Did-You-Know section is bland.
- Order nit: the Task 6 solution ends with `lesson_delete broken-dojo` before the "Before cleanup, reflect" paragraph, although the reflection answer's `docker port` check needs the cluster to still exist. This is pre-existing and not delta-introduced.

Provenance: reviewer Claude Code seat, actual model family Anthropic Claude (Sonnet 5.5, id claude-sonnet-5-5), harness Claude Agent SDK / Claude Code CLI. The author is OpenAI Codex gpt-6.1-terra, so this is a cross-family review.

Checks performed: git rev-parse, git diff --stat, sha256sum, the full diff, and a full read of the page. Supplied rather than checked: the call 1 and 2 history.

Limits: no Docker, kind or cluster exists on this host, so commands were judged as prose and design only. I did not re-verify the digests or the release-notes pins; I treated F2 as closed per the CTO ruling. I did not re-test whether a killed kind node restarts under its restart policy; this was not touched by the delta.

### Findings (verbatim JSON)

```json
[
 {
  "id": "task4-client-version-gap",
  "title": "Task 4 expected outcome omits the client version the predict asks for",
  "body": "Task 4's predict prompt asks which client and server versions each context will report. The new expected-outcome line states only the two server versions. The learner is not told that the client stays v1.35.x in both contexts, which is the point of the skew comparison.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/kubernetes-basics/module-1.1-first-cluster.md",
   "start_line": 671,
   "end_line": 671,
   "claim_type": "present"
  },
  "verbatim": "Expected outcome: `kind-primary-dojo` reports server v1.35.8 and `kind-legacy-dojo` reports server v1.34.11.",
  "why_wrong": "The predict asks for client and server versions, but the answer covers only the server side. This is a minor feedback gap and does not block acceptance.",
  "smallest_fix": "Append: the client reports v1.35.x in both contexts (within one minor of both servers).",
  "sources": [
   "none"
  ]
 }
]
```
