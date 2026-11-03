# Reviews of prerequisites/zero-to-terminal/module-0.8-servers-and-ssh.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The lab was not run by either reviewer.

## kd-wp-08-r1: call 1 of 2, whole-page review

- reviewed head: `f75a01ab32fc866ee87d70042651859ea80f8b45`
- run nonce: `79bbc21134084ce1b42158f9dd2c0c9b`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DISPOSITION: revise (confidence 0.8). Whole-page review, call 1 of 2, of module-0.8-servers-and-ssh.md at f75a01ab32fc866ee87d70042651859ea80f8b45.

DIGEST: I ran sha256sum on the file and it matches sha256:4b4ec779e251bafaa6cb447aaf9e63dfe15f4501c33743976888a475c6983d57. I read all 727 lines in bounded reads.

SCORES (D1-D8 names from docs/quality-rubric.md):
- D1 Learning Outcomes 4: the four outcomes are measurable and mostly taught.
- D2 Scaffolding 3: host key, fingerprint and known_hosts are used before they are explained, and the Incident C answer is the first place known_hosts is described.
- D3 Active Learning 4: predict-then-reveal prompts are used throughout.
- D4 Real-World Connection 4: the incident scenarios are realistic.
- D5 Assessment Alignment 3: the localhost checklist omits the one command that separates a loopback SSH session from a local shell, and Incident C tests an untaught mechanism.
- D6 Cognitive Load 3: the same synthetic prompt and transcript appear twice, and the 'prompt is only a clue' point recurs.
- D7 Engagement 4.
- D8 Practitioner Depth 4: safety posture is good.
Module total 29/40, below the 33 floor. D2, D5 and D6 are below 4, so the floors are NOT met.

Lab scores (L1-L5):
- L1 Scenario-Based Design 4.
- L2 Progressive Difficulty 3: there is no path for a learner who has no SSH server.
- L3 Understanding Over Memorization 4.
- L4 Hint & Feedback Quality 3: hints exist only for Incident A, and no expected SSH_CONNECTION result is given.
- L5 Transfer Potential 4.
Lab total 18/25, below the 21 floor. L2 and L4 are below 4, so the floors are NOT met.

lab_execution: NOT RUN. There is no server on the host, and the Killercoda scenario lives outside this repo and is not inspectable. I judged the exercise as prose only. The page contains no execution receipts.

source_status: PARTLY SUPPORTED. I judged 12 material claims: 12 supported, 0 contradicted, 0 unsupported. The page's claims about SSH_CONNECTION, -i/-p/-v, the fingerprint prompt, known_hosts, ssh-keygen -R, authorized_keys location and permissions, port 22 as the sshd default, default Ed25519 filenames and the RFC 4251 description are all supported by the pages I opened. A few claims remain unverified because I did not open their sources (listed under limits). The citation seed is stale: its claims C001 to C008 refer to a previous page body (for example 'Nobody can listen in on your conversation' and 'Remote Kitchens', which the current page lacks), and its judgments are mostly 'cannot_be_salvaged' or 'needs_allowlist_expansion'. I treated the seed as history only. It is not evidence for the current text.

BLOCKING FINDINGS:
1. (UNDER-EXPLANATION, lines 259-267, 560, 685-695.) The page never teaches what a host key or fingerprint is. It never says that accepting a prompt stores the key in ~/.ssh/known_hosts, or that a later mismatch triggers the changed-key warning. It also gives no way to obtain the independent fingerprint that the lab step demands for localhost; ssh-keygen -l prints a key file's fingerprint. Incident C then tests this mechanism, and known_hosts and ssh-keygen -R first appear in the challenge text and its answer.
2. (Practice alignment and completability, lines 345-347, 555-563, 569-574.) The localhost checklist cannot show the learner anything, because hostname, whoami and pwd are identical inside and outside the loopback session. The page says SSH_CONNECTION is the distinguishing clue (line 347) but never tells the learner to run echo $SSH_CONNECTION, and the solution gives no expected result. The page also gives no usable server path for most learners: line 39 and the exercise say an authorized SSH server is required, the only setup is an optional disposable-VM procedure, and the body never mentions the Killercoda lab that the frontmatter and time header imply.
3. (BLOAT, lines 361-367 and 401-433.) The host-authenticity prompt block is repeated verbatim after it already appeared at 259-265. Two near-identical synthetic connect-and-run transcripts follow at 401-413 and 417-433. The 'prompt is only a clue' message recurs at lines 84, 92, 153, 442 and 469.

NON-BLOCKING FINDINGS:
- Incident B (line 625) shows git pull origin main changing production code ('Fast-forward', 'app.js'). The risk analysis (lines 656-657) discusses only the touch and says the transcript 'proves neither file creation nor an outage'. That omits the strongest evidenced mutation. The scenario ('intended to test ... locally') is also implausible, because the transcript begins with ssh to worker-prod-04. The closing 'Connection to 192.0.2.85 closed.' names an IP although the typed host was worker-prod-04.
- The Incident B and C transcripts (lines 617-636, 661-675) are labelled synthetic only inside the answers, not where they are presented. Incident A is labelled up front.
- Hints are given only for Incident A. Incidents B and C go straight to full answers.
- The Kubernetes transfer section (lines 436-438) is a single paragraph that names no concrete command, and it sits just before an unrelated section. Line 39 is a stray localhost paragraph that appears before host keys are taught. 'Security group' (lines 337, 603) and 'VPN' are used without explanation.
- The Apple, Microsoft and Kubernetes Nodes entries in Sources support nothing in the body.

OMITTED-CLAIM DISCOVERY: I found no unledgered false claim. All new claims I checked were true. Material claims not in the seed include the SSH_CONNECTION variable, the 'order of -p and -i does not matter' rule, the Ctrl+D disconnect, and the Debian/Ubuntu service name ssh with apt install openssh-server.

SAFETY: acceptable. The page warns against sharing private keys, against blind host-key acceptance and against deleting known_hosts entries without verification. It restricts setup to a disposable VM, uses RFC 5737 addresses, and does not tell learners to disable existing SSH services.

URLS ACTUALLY OPENED: https://man.openbsd.org/ssh, https://www.rfc-editor.org/rfc/rfc4251, https://man.openbsd.org/ssh-keygen, https://man.openbsd.org/sshd.

NOT OPENED (UNKNOWN, not passed): the GitHub Docs key-generation source, IANA ports, Ubuntu OpenSSH server docs, Apple and Microsoft pages, Kubernetes Nodes, Wikipedia, the RFC 5737 page and the ssh_config(5) page. The one claim that depends on RFC 5737 is that 192.0.2.24 is a reserved example address; I took it from the supplied page text.

VERIFIED VERSUS SUPPLIED: I verified the page text, the digest, the contract and rubric, the seed content, and the man-page and RFC claims listed above. I took the superseded page-reviews history and the older review files as unverified input. I made no use of earlier dispositions.

PROVENANCE: reviewer Claude Code on claude-sonnet-5-5 (Anthropic family), read-only harness with Sources MCP and WebFetch, outside the OpenAI/Codex author family. Review kind: whole-page review, call 1 of 2. Limits: the lab was not executed, the Killercoda scenario was not inspected, and the web fetches were summarized by a small model, so quotes taken from them are paraphrase-level.

### Findings (verbatim JSON)

```json
[
 {
  "id": "ZTT08-F1",
  "title": "Host key, fingerprint and known_hosts used before being taught; no way to verify the localhost fingerprint",
  "body": "The page requires 'independent' fingerprint verification (lines 267 and 560) but never defines a host key or fingerprint. It never says that accepting the prompt records the key in ~/.ssh/known_hosts, or that a later mismatch triggers the changed-key warning. known_hosts and ssh-keygen -R first appear in the Incident C challenge and its answer. For localhost the learner is told to verify out-of-band but is never shown how, although ssh-keygen -l prints a public key file's fingerprint.",
  "priority": "P1",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.8-servers-and-ssh.md",
   "start_line": 259,
   "end_line": 267,
   "claim_type": "present"
  },
  "verbatim": "Before accepting a host key, including for `localhost`, compare its fingerprint with a value obtained through a trusted, independent channel.",
  "why_wrong": "This is UNDER-EXPLANATION under the review contract: a term is used before it is explained and a reasoning step is skipped. The lab step 'accepting the first-time host key only after independently verifying its fingerprint' cannot be completed as written, and Incident C tests a mechanism the lesson never taught.",
  "smallest_fix": "Add 3-4 sentences after the host-key prompt. Say that the host key is the server's own key pair and the fingerprint is a short hash of its public key. Say that accepting stores it in ~/.ssh/known_hosts and that later connections compare against it, which is what the changed-key warning reports. For localhost, show `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` run on the server machine as the independent check. Add one sentence in the lab checklist pointing to it.",
  "sources": [
   "https://man.openbsd.org/ssh",
   "https://man.openbsd.org/ssh-keygen",
   "https://www.rfc-editor.org/rfc/rfc4251"
  ]
 },
 {
  "id": "ZTT08-F2",
  "title": "Localhost exercise cannot show the local/remote difference and gives no usable server path",
  "body": "On `ssh localhost`, hostname, whoami and pwd are identical inside and outside the session. The page says SSH_CONNECTION is the clue to use (line 347), but the checklist never includes `echo $SSH_CONNECTION` and the solution gives no expected result. The step 'use the session clues above' leaves the learner to guess. The page also says an authorized SSH server is needed, but the only provided setup is an optional disposable-VM procedure. The body never mentions the Killercoda lab that the frontmatter and the time header imply.",
  "priority": "P1",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.8-servers-and-ssh.md",
   "start_line": 559,
   "end_line": 563,
   "claim_type": "present"
  },
  "verbatim": "- [ ] Disconnect with `exit`, then use the session clues above and run `hostname` again to compare with your local notes.",
  "why_wrong": "The exercise's own learning goal is to make the remote-shell model concrete, but the prescribed commands give indistinguishable output. This is a practice-alignment gap, a skipped reasoning step and an unspecified execution path (L2, L4, D5).",
  "smallest_fix": "In the 'Inside the SSH session' step add `echo $SSH_CONNECTION` and state that it prints four values inside the session and is empty locally. Add that expected result to the solution. Add one sentence to the exercise intro naming the Killercoda Ubuntu lab as the environment that supplies an SSH server and saying what to do in it. If the lab's setup differs from this page, make the page match the lab.",
  "sources": [
   "https://man.openbsd.org/ssh"
  ]
 },
 {
  "id": "ZTT08-F3",
  "title": "Duplicated prompt block and near-duplicate synthetic transcripts",
  "body": "The host-authenticity prompt appears verbatim at lines 261-265 and again at 363-367. Two near-identical synthetic connect-and-run transcripts follow at 401-413 and 417-433. The 'prompt is only a clue' point recurs at lines 84, 92, 153, 442 and 469.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.8-servers-and-ssh.md",
   "start_line": 361,
   "end_line": 367,
   "claim_type": "present"
  },
  "verbatim": "The first connection to a new host record may display a host authenticity prompt. Verify the presented fingerprint independently before answering `yes`. The following prompt is synthetic, not a recording from a real host.",
  "why_wrong": "This is BLOAT under the review contract: repetition that adds no taught content and dilutes the key points. The learner reads the same block twice.",
  "smallest_fix": "Delete the second prompt block and refer back to the earlier one. Merge the two synthetic transcripts at 401-433 into one that keeps the ubuntu@192.0.2.24 example. Trim the repeated 'prompt is only a clue' sentences at lines 442 and 469.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "ZTT08-F4",
  "title": "Incident B analysis ignores the git pull shown in the transcript",
  "body": "The transcript shows `git pull origin main` fast-forwarding code in /var/www/site on a production host. The answer's risk section discusses only the touch of the flag file and concludes 'The transcript alone proves neither file creation nor an outage'. It omits the one change the transcript does evidence. The scenario also does not fit its premise: the engineer says they intended to test locally but the transcript begins with ssh to the production worker. The closing message names 192.0.2.85, while the host typed was worker-prod-04.",
  "priority": "P2",
  "confidence": 0.65,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.8-servers-and-ssh.md",
   "start_line": 625,
   "end_line": 636,
   "claim_type": "present"
  },
  "verbatim": "deployer@worker-prod-04:~$ git pull origin main",
  "why_wrong": "The operational-risk answer is incomplete and partly inconsistent with the transcript it analyses.",
  "smallest_fix": "In the Incident B answer, name the git pull as an evidenced production change alongside the unverified touch. Make the closing line read 'Connection to worker-prod-04 closed.', or add the IP to the ssh line.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "ZTT08-F5",
  "title": "Incidents B and C are not labelled synthetic where presented, and have no hints",
  "body": "Incident A is introduced as 'synthetic terminal transcripts'. The Incident B transcript and the Incident C warning, which uses a made-up fingerprint, are presented without that label. 'Illustrative' and 'synthetic' appear only inside the collapsed answers. Incidents B and C also have no tiered hints, unlike A.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.8-servers-and-ssh.md",
   "start_line": 677,
   "end_line": 677,
   "claim_type": "present"
  },
  "verbatim": "While investigating an alert on an API server, an engineer encounters the security warning displayed above.",
  "why_wrong": "Synthetic outputs must be labelled where the learner first meets them, and the practice rubric expects tiered hints.",
  "smallest_fix": "Add '(synthetic, not a real recording)' before the B and C code blocks. Add a one-line hint for each of B and C.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-08-r2: call 2 of 2, delta review

- reviewed head: `9fe0a17467c3456bcafdd10f63332fc4e5af7d6f`
- run nonce: `e79c07a2f92b43b6ae91d335aab33309`
- verdict: `correct` (confidence 0.8)

### Explanation (verbatim)

Delta review, call 2 of 2 (not acceptance). Reviewer: Claude Code, model claude-sonnet-5-5 (Anthropic family, outside the OpenAI/Codex author family), toolful, read-only.

Task 1: HEAD is 9fe0a17467c3456bcafdd10f63332fc4e5af7d6f. The diff against f75a01ab touches one file, the module page: 31 insertions, 42 deletions. The page sha256 at HEAD is ed2a59bdfc9f360c68e1da76d4e524c080fb9bce37a1215d88109408102a4579, which matches. I read the whole page.

F1 CLOSED. A paragraph at lines 267-271 defines host key (the server's own public/private key pair), fingerprint (a short hash of the public key), the ~/.ssh/known_hosts record on acceptance, comparison on later connections, and the changed-key warning. It gives ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub for the server's trusted console. All of this comes before the localhost step (line 365), the exercise (line 544) and Incident C (lines 649-687). The definitions match the sources I opened. The ssh man page says ssh keeps known_hosts, shows a fingerprint of the server's public key on first connection, and warns if a host's identification changes. It also lists the near-identical ssh-keygen -l -f /etc/ssh/ssh_host_ed25519_key.pub under FINGERPRINT. The sshd man page confirms /etc/ssh/ssh_host_ed25519_key.pub is the world-readable public half, so the command needs no sudo. RFC 4251 section 4.1 says each server host SHOULD have a host key and that fingerprints can be checked over an external channel. The page's wording is correct and needs no SHA-1 detail. The RFC excerpt in the PR body ('hexadecimal fingerprint derived from the SHA-1 hash') is only an example in a MAY clause. It supports 'a fingerprint is a hash of the public key' but not the SHA256 form OpenSSH prints, so it must not be cited for the algorithm. The localhost learner's trusted console is their own machine; the page says 'the server machine's trusted console' without saying so for localhost. This is clear enough and non-blocking. The ssh-keygen -R command is not introduced before Incident C. The challenge text and procedure step 4 explain it in place, which is enough. The command ssh-keygen -lf was not run against a server, as the PR admits; the man pages support it.

F2 CLOSED. echo $SSH_CONNECTION is taught before the session (line 543), inside it (line 545) and after it (line 546). The solution guidance (line 556) says it normally shows four values, client address and port then server address and port, and is normally empty outside an SSH session. The ssh man page ENVIRONMENT confirms the four values, as fetched. The hedge 'an existing SSH session or a modified environment can change that baseline' is correct. Line 539 states the honest paths: an authorized server, the disposable VM, or written checks without connecting. The body never claims the Killercoda lab exists or works. Line 16 still says 'read + Killercoda lab', and the lab:-driven LabBanner component (src/components/LabBanner.astro) appears to render it, which I did not verify further. The stray early localhost paragraph is removed. Its content survives in the Practicing section (line 349) and the host-key text. Nothing depends on the removed paragraph.

F3 CLOSED. Greps for 'following transcript', 'following prompt', 'shown earlier' and 'synthetic' found no dangling reference. Every 'following prompts/transcript is synthetic' sentence has its block directly after it (lines 151, 399; the first host-prompt block at lines 257-263 stays). Line 365 refers to the earlier prompt that does exist. The repeated prompt block and the two near-duplicate transcripts are gone. The 'prompt is only a clue' point still appears before the exercise: line 82 ('Prompts are customizable and can mislead'), line 90 ('names can be reused'), line 146 ('A configured shell may display a different prompt') and line 377. Removing it from the 'Reading Prompts, Paths, and Output Carefully' section and the closing sentence leaves no contradiction and does not weaken safety. That section is now thin on prompts relative to its heading, which is non-blocking.

F4 closed: Incident B's scenario is now coherent (the engineer connected to update the site and forgot to disconnect), the git pull / app.js change is in the risk analysis, and the closing line is 'Connection to worker-prod-04 closed.' F5 closed: Incidents B and C are labelled synthetic where presented, and Incident B and C now have hints.

Partial residuals. The Kubernetes transfer paragraph names no command, but it still states the two-sentence habit, so it is NON-BLOCKING. The citation seed is history, not evidence, and is not a defect. The unused Apple, Microsoft and Kubernetes Nodes sources are removed. No link into the page uses an anchor, and no heading was removed. Inbound links go from index.md, prerequisites/index.md, module 0.7 and the uk pages, and all resolve.

Non-blocking nits introduced or left: the word 'fingerprint' (line 265) and 'host-key verification' (line 90) appear a paragraph or more before the definition at line 267; the Practicing section tells the learner to use SSH_CONNECTION but its command blocks omit it; no example SSH_CONNECTION values are shown, such as 127.0.0.1 for loopback; the git hash 'e4f5g6h' in Incident B is not hex.

Scores from a full read, using the dimension labels in docs/quality-rubric.md. D1 Learning Outcomes 5, D2 Scaffolding 4, D3 Active Learning 4, D4 Real-World Connection 4, D5 Assessment Alignment 4, D6 Cognitive Load 4, D7 Engagement 4, D8 Practitioner Depth 4: total 33/40, every D at least 4, so exactly at the floor. L1 Scenario-Based Design 5, L2 Progressive Difficulty 4, L3 Understanding Over Memorization 4, L4 Hint & Feedback Quality 4, L5 Transfer Potential 4: total 21/25, every L at least 4, so exactly at the floor, and prose judgement only. I did not inflate. A weaker L5 or D2 would fall below the floors.

BLOCKING: none. NON-BLOCKING: the items above.

URLs actually opened: https://man.openbsd.org/ssh, https://man.openbsd.org/sshd and https://www.rfc-editor.org/rfc/rfc4251 (all through a summarising fetch, not raw pages). The ssh-keygen man page was not opened, so the claim that fingerprints print as SHA256 by default is UNKNOWN from this run; the page's own prompt shows SHA256 and the ssh man page uses the same command.

Checks performed by me: git rev-parse, diff stat, sha256sum, full diff, full page read, greps for dangling references and links, heading list. Checks supplied and not re-run: the author's claims about the PR body. Limits: the lab is not run and the Killercoda scenario is not inspected; no server exists, so the SSH_CONNECTION baseline and the fingerprint command were judged as prose and design only.

Verdict: F1, F2 and F3 are closed and no BLOCKING defect remains, so correct.

### Findings (verbatim JSON)

```json
[]
```
