# Reviews of prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The only edit is one marked omission of a private file path in the call-2 explanation.

## kd-wp-02-r1: call 1 of 2, whole-page review

- reviewed head: `5ab2b6d319d0074bb03cb9dcd9fa020d109da4a7`
- run nonce: `e5ea5196dd484231a4a394de66698c93`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md gave 7815fad4828994da3a381b02dcb2c73c0b83f22c376f2bc65cff5a3d3477960a, which matches the supplied value. HEAD was 5ab2b6d319d0074bb03cb9dcd9fa020d109da4a7. The page is 682 lines and I read all of it. SCORES, whole page D1-D8 using docs/pipeline.md dimensions: D1 Learning Outcomes 4 (four clear, measurable outcomes at compare/diagnose/debug level, mostly aligned to practice). D2 Scaffolding 3 (no instruction for opening a terminal on Windows; the line-334 aside on aliases and kubectl is an abrupt transition; the quoting block at lines 274-288 is out of order). D3 Active Learning 5 (many predict-and-reveal prompts, a recovery drill, four diagnosis transcripts). D4 Real-World Connection 4 (clear hypothetical scenario and a good Common Mistakes table). D5 Assessment Alignment 4 (the 8 quiz answers agree with the lesson and explain why). D6 Cognitive Load 3 (jargon is used before it is explained: alias, script, PSReadLine, SIGINT/foreground process group, subcommand; the prompt-customization caveat is repeated at lines 102, 122, 209, 216, 288, 430 and 637). D7 Engagement 4. D8 Practitioner Depth 4 (patterns table, anti-patterns table, decision table). TOTAL 31/40, below the 33 threshold. Floors are NOT met: D2=3 and D6=3. LAB L1-L5 for the Hands-On Exercise: L1 4 (prescriptive, but step 6 recovery and the step 7 transcripts require decisions), L2 4, L3 5 (predict-run-compare with explaining differences), L4 4 (per-step solution guidance and an answer key, but no tiered hints), L5 4. TOTAL 21/25, so the lab floors are met on paper. The lab is only usable by a Windows learner once finding KD02-W1 is fixed. DISPOSITION: revise. Confidence 0.8. SOURCE_STATUS: partly supported to supported. I judged about 14 material claims myself: 12 supported, 0 contradicted, 2 taken from the supplied catalog and not opened (see below). LAB_EXECUTION: not run. There is no pwsh or zsh on this host and I ran none of the page's commands. The only local check was bash, which printed x for set -o histexpand; echo "x". Nobody's run of the page's exercises was supplied to me. I judged the exercise as prose and design: the commands are all read-only, the expected outputs are hedged, the unfinished-quote drill ends with Ctrl+C, and the page needs no cleanup. BLOCKING FINDINGS: (1) KD02-W1, line 87 (and the step 1 text at line 481). The page never tells a Windows learner how to open Windows Terminal, PowerShell or a WSL tab. It gives open instructions for macOS and Linux at line 85, but for Windows only a conceptual comparison. The outcome says 'Open a terminal on your chosen operating system', and exercise step 1 says 'Open your terminal using the instructions from this module'. The page also never says how to get Windows Terminal. This is UNDER-EXPLANATION on a primary-audience platform. Smallest fix: add one or two sentences, e.g. open the Start menu, type Terminal or PowerShell, and press Enter, and state which one to use if Terminal is missing, citing the Windows Terminal install doc. (2) KD02-J1, lines 53, 87, 122, 334, 359 and 407. 'alias', 'script' and 'PSReadLine' are used with no definition in an absolute-beginner module. The anti-pattern and mistake rows ask the learner to act on them ('Write full command names'). Line 334 jumps from kubectl to 'aliases do not reliably expand in non-interactive scripts' with no bridge. This is UNDER-EXPLANATION. Smallest fix: one-sentence glosses at first use: an alias is a saved shortcut name for a longer command; a script is a text file of commands; PSReadLine is the PowerShell component that edits the line you type. Also cut or bridge the line-334 sentence. NON-BLOCKING FINDINGS: (a) Lines 318 and 416 give 'SIGINT to the foreground process group' with no explanation, and the learner needs only 'Ctrl+C asks the running command to stop'. (b) Transcript D (line 624) repeats the line-211 training-vm scenario and the Q3 prompt-reading point, so it adds no new skill; the 'prompts are customizable, not proof' caveat is repeated seven times. (c) Did-You-Know item 3 (line 392, SSH/RFC 4251/OpenSSH) is off-topic background that the module never uses. (d) Lines 252-256 teach options only with date -u, which has no PowerShell example, so PowerShell learners get no worked option. (e) Line 29 'Kubernetes ... version 1.35' is an undated volatile version and can simply be dropped. (f) Line 329 'echoo: command not found' is an unlabeled synthetic output whose format matches neither Bash nor zsh, unlike Transcript C's zsh format. (g) Lines 274-288 interleave the unfinished-quote warning, the grouping comparison, the code, the recovery and the bare '>' block, and 'A command can interpret those argument lists differently' is vague. SAFETY: no unsafe advice. The rename loop is labeled illustration only and says do not run; wsl --install is labeled optional with 'do not run the installer'; every exercise command is read-only; admin PowerShell is mentioned only as Microsoft's documented step. OMITTED-CLAIM DISCOVERY (not in my reading of the supplied evidence): macOS Terminal defaults to zsh (line 106), Cmd+Space opens Spotlight (85), Ctrl+Alt+T opens a Linux terminal (85), `date -u` is UTC on macOS and GNU (252), and Bash PS2 is '>' (122) were read by me as plausible background knowledge and not verified against any source. `whoami` on Windows prints a DOMAIN\user form unlike the example 'yourname' (line 191); the 'output can differ' paragraph at line 220 covers this adequately. SOURCES I ACTUALLY OPENED AND CHECKED: https://learn.microsoft.com/en-us/windows/wsl/install (admin PowerShell, wsl --install, restart, Ubuntu default, 'only works if WSL is not installed at all', Start-menu launch - supported). https://devblogs.microsoft.com/commandline/windows-terminal-1-0/ (dated May 19 2020, 'Last year at Build 2019, we first announced' - supported; it does not name Command Prompt, though it does say profiles are created for WSL and PowerShell). https://vt100.net/docs/vt100-ug/chapter1.html (keyboard input sent to the computer, data from the computer shown on the screen - supported; I read only the first 100,000 of 335,564 characters). https://www.ibm.com/history/punched-card (holes encode characters; a separate reader loads data - supported). https://learn.microsoft.com/en-us/powershell/module/psreadline/set-psreadlineoption?view=powershell-7.5 (ContinuationPrompt default '>>' - supported). https://learn.microsoft.com/en-us/powershell/module/psreadline/about/about_psreadline_functions?view=powershell-7.5 (CopyOrCancelLine: copies if text is selected, otherwise cancels; AcceptLine shows the continuation prompt - supported). https://zsh.sourceforge.io/Doc/Release/Expansion.html (history expansion applies in double quotes in interactive shells and not in single quotes - supported; I read only the first 100,000 of 133,407 characters). TAKEN FROM SUPPLIED EVIDENCE AND NOT RE-OPENED: Apple termios INTR/SIGINT default ^C (lines 282, 318, 416), per the prior reviewer's catalog; GNU coreutils/inetutils/Bash manuals; RFC 4251/OpenSSH; kubectl quick reference; Microsoft Get-Date and about_Operators; MDN. I also read the repository's 2026-11-01 terminal-foundations source catalog (prior Grok verdict APPROVE, 77 claims) and the citation seed (an unjudged author inventory of 77 claims). I treated both as unverified inputs. I did not rejudge each of the 77 claims; my source verdict covers the material claims I listed. I did not open the superseded page-reviews.json history because it is void under the current workflow. PROVENANCE: reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family), run through the Claude Code harness. The page's author/maintainer family is OpenAI/Codex, so this review is outside that family. REVIEW KIND: whole-page review, call 1 of 2. The checks above were performed by me. Stream counters, bindings and prior verdicts were supplied by the task and not recomputed. LIMITS: no pwsh, zsh or Windows on the host, so Windows, PowerShell, WSL and zsh behavior is judged from documentation only. The rubric is stated in docs/pipeline.md and docs/quality-rubric.md, and I used the dimension names in docs/pipeline.md. Verdict rests on the two blocking under-explanation findings and the D2/D6 floor misses; the rest are fixable within one small PR.

### Findings (verbatim JSON)

```json
[
 {
  "id": "KD02-W1",
  "title": "Windows learners are never told how to open a terminal",
  "body": "The page gives concrete open steps for macOS and Linux but only a conceptual comparison for Windows. It never says how to open Windows Terminal or PowerShell, or what to do if Terminal is missing. The first outcome ('Open a terminal on your chosen operating system') and exercise step 1 ('Open your terminal using the instructions from this module') both depend on instructions that do not exist for Windows.",
  "priority": "P2",
  "confidence": 0.85,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 85,
   "end_line": 87,
   "claim_type": "missing"
  },
  "verbatim": "Windows has several valid options, and they serve different purposes. Windows Terminal is Microsoft's modern terminal application and is a good day-to-day container for shells.",
  "why_wrong": "UNDER-EXPLANATION (BLOCKING): a skipped step for a primary platform means a Windows beginner cannot complete outcome 1 or exercise step 1 from the page itself, and the 'instructions from this module' that step 1 points to do not exist.",
  "smallest_fix": "Add one or two sentences after line 87: on Windows, open the Start menu, type Terminal (or PowerShell), and press Enter; if Terminal is not listed, use Windows PowerShell. Cite the Windows Terminal install documentation for availability (I did not open it).",
  "sources": [
   "https://learn.microsoft.com/en-us/windows/wsl/install"
  ]
 },
 {
  "id": "KD02-J1",
  "title": "Alias, script and PSReadLine are used with no definition, and line 334 jumps in abruptly",
  "body": "'alias' first appears at line 87 and recurs at lines 173, 334, 359 and 407. 'script' appears at lines 53, 181, 359 and 372. 'PSReadLine' is used at lines 122, 318 and 404. None of these is defined for an absolute beginner. Anti-pattern and mistake rows tell the learner to act on them ('Write full command names in examples and scripts'). Line 334 jumps from kubectl get pods to a claim about aliases in non-interactive scripts with no bridge.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 334,
   "end_line": 334,
   "claim_type": "present"
  },
  "verbatim": "Later Kubernetes examples use full commands such as `kubectl get pods`; aliases do not reliably expand in non-interactive scripts.",
  "why_wrong": "UNDER-EXPLANATION (BLOCKING): a term is used before it is explained and the transition is unexplained, so the learner cannot act on the 'use full command names' advice.",
  "smallest_fix": "Gloss at first use: an alias is a saved short name for a longer command; a script is a text file of commands; PSReadLine is the part of PowerShell that edits the line you type. Cut or bridge the line-334 aside.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "KD02-N1",
  "title": "SIGINT and foreground process group are unexplained jargon",
  "body": "The learner needs only 'Ctrl+C asks the running command to stop'. 'SIGINT' and 'foreground process group' are never taught and are repeated in the quiz answer at line 416.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 318,
   "end_line": 318,
   "claim_type": "present"
  },
  "verbatim": "In Unix terminals it normally sends SIGINT to the foreground process group.",
  "why_wrong": "NON-BLOCKING: cognitive load beyond the stated outcome; the claim is correct per the prior catalog (termios) but not needed by an absolute beginner.",
  "smallest_fix": "Replace with 'In Unix terminals it normally asks the running command to stop' in both places, or define 'signal' in one clause.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "KD02-N2",
  "title": "Transcript D repeats the earlier training-vm exercise",
  "body": "Transcript D reuses the same laptop vs training-vm prompt pair and the same answer as the line-211 prediction, then Q3 repeats the point again. The 'prompts are customizable, not proof' caveat also recurs at lines 102, 122, 209, 216, 288, 430 and 637.",
  "priority": "P3",
  "confidence": 0.65,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 624,
   "end_line": 632,
   "claim_type": "present"
  },
  "verbatim": "Transcript D: two windows from the same practice lab, both waiting for input.",
  "why_wrong": "NON-BLOCKING BLOAT: duplicated practice adds no new skill to a task that is meant to be an unguided final diagnosis.",
  "smallest_fix": "Replace Transcript D with a different state (for example a PowerShell prompt ending in > that is NOT a continuation) or drop it, and trim the repeated caveat.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "KD02-N3",
  "title": "Did You Know item on SSH is off-topic background",
  "body": "The SSH item (RFC 4251, OpenSSH client and server) has no link to any outcome or taught content in this module.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 392,
   "end_line": 392,
   "claim_type": "present"
  },
  "verbatim": "RFC 4251 describes the Secure Shell architecture. OpenSSH provides SSH tools, including a client and a server.",
  "why_wrong": "NON-BLOCKING BLOAT: background the learner cannot use here, and the page does not explain SSH.",
  "smallest_fix": "Delete item 3, or tie it to the remote-access point in one sentence.",
  "sources": [
   "https://www.rfc-editor.org/info/rfc4251"
  ]
 },
 {
  "id": "KD02-N4",
  "title": "Options are taught with a command that has no PowerShell equivalent shown",
  "body": "The only option example is date -u, but the page directs PowerShell learners to Get-Date; no PowerShell option or parameter example is given, so those learners see no worked option.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 252,
   "end_line": 256,
   "claim_type": "present"
  },
  "verbatim": "The macOS and GNU versions of `date` use `-u` to request UTC rather than the configured local time.",
  "why_wrong": "NON-BLOCKING: the options concept has no PowerShell worked example, though the page promises branches for each shell.",
  "smallest_fix": "Add one sentence showing a PowerShell parameter such as Get-Date -AsUTC (PowerShell 7+), or state that this example is Unix-only.",
  "sources": [
   "https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-date?view=powershell-7.5"
  ]
 }
]
```

## kd-wp-02-r2: call 2 of 2, delta review

- reviewed head: `148c26b1c65da2ce0e248a3536988770fc56481f`
- run nonce: `f0c71db5704243baa80cf874a2a104cb`
- verdict: `correct` (confidence 0.8)

### Explanation (verbatim)

TASK 1. HEAD is 148c26b1c65da2ce0e248a3536988770fc56481f. The diff against the base 5ab2b6d3 touches exactly one file, module-0.2-what-is-a-terminal.md (21 insertions, 32 deletions, matching the reported 53 changed lines). Page sha256 at HEAD is a4457de7df9ee828e12266fc7055d1e59e3a6557f0c482ef93e3800495ab5145. [One sentence about a driver-side file path was omitted from this public copy.]

KD02-W1: CLOSED. Line 87 now says to open the Start menu, type Windows PowerShell, select Windows PowerShell, and select Open. That matches Microsoft's wording exactly. Line 87 also links Windows Terminal (install page) and says to use the arrow next to the plus button to pick a WSL profile for an installed distribution. The install page says to select the arrow next to the + button to open the dropdown and pick a profile, and that profiles are created automatically for WSL distributions. Exercise step 1 (line 477) says to open the terminal using this module's instructions, and the Windows route now exists. The Setup text (line 473) still ties the WSL branch to a Windows Terminal WSL Ubuntu profile and the PowerShell branch to Get-Date, so a Windows learner has a runnable path. The macOS (Cmd+Space, Terminal) and Linux (Ctrl+Alt+T or the applications menu) instructions at line 85 are unchanged. The Windows paragraph is dense, but it is complete and ordered, and I do not treat that as blocking.

KD02-J1: CLOSED. First use of each term and where it is defined:
- script: first used at line 53 and defined in the next sentence ('A script is a text file containing commands'). It matches about_Scripts, which describes a plain text file containing PowerShell commands.
- alias: first used at line 87 and defined in the same paragraph ('An alias is an alternate name for a command'). It matches about_Aliases ('alternate name or nickname for a cmdlet or command element'). Later uses at lines 138, 357 and 403 come after the definition.
- PSReadLine: first used at line 122 and defined in the following sentence ('provides command-line editing in PowerShell'). It matches about_PSReadLine ('improved command-line editing experience in the PowerShell console').
The old kubectl-to-aliases jump is gone: line 332 now only says to use full commands and to check context, namespace and output, and the alias reasoning lives in the anti-pattern table (line 357), after the definition. 'subcommand', 'interrupt' and SIGINT no longer appear in the body. 'argument' is defined at line 157. 'foreground' survives only at line 401 and is explained by the sentence around it; I do not treat it as blocking for this audience.

NON-BLOCKING ledger.
- N1 closed: SIGINT and process group are replaced by 'asks the running command to stop' at lines 316 and 412.
- N2 closed: Transcript D is removed, and the customizable-prompt caveat drops to a few uses (lines 102, 209, 216, 426).
- N3 closed: the SSH and RFC 4251 item and their two source entries are removed, and Did-You-Know items renumber cleanly 1 to 3.
- N4 closed: line 252 now says PowerShell learners can read the date -u example without running it.
- Kubernetes 1.35: closed (removed).
- Quote block: closed. The order is now compare, unfinished quote, the code, the prompt, then recovery, and the vague sentence is gone.
- Synthetic output line: partly closed. It now reads 'zsh: command not found: echoo', which is the zsh format, but it is not labelled as sample zsh output, so Bash or PowerShell learners will see different text. This is recorded as one P3 finding.

Transcript D removal is clean. The only transcripts left are A, B and C. The task 7 text, the answer key and the success criteria say 'each transcript' or 'each frozen transcript', with no count and no mention of D. The training-vm scenario still has its own prompt and answer at lines 211 to 216. Quiz questions 1 to 8 are consistent with the new Ctrl+C wording.

NEW CLAIM VERIFICATION. I opened these pages myself: learn.microsoft.com/en-us/powershell/scripting/windows-powershell/starting-windows-powershell, /en-us/windows/terminal/install, /en-us/powershell/module/microsoft.powershell.core/about/about_scripts, .../about/about_aliases and /en-us/powershell/module/psreadline/about/about_psreadline. All five fetched and support the page's wording. The Windows Terminal link at line 87 and its sources entry both point to the install page; the in-text announcement and 1.0 release links in Did-You-Know were not re-fetched. No dangling in-text link or removed-source mismatch was found; the RFC and OpenSSH entries are gone from both text and sources. Not verified: current Windows 11 Start-menu appearance, which I only confirmed against Microsoft's wording, because there is no Windows host.

NEW DEFECTS. No contradiction: 'asks the running command to stop' is consistent with 'a program may ignore the cancellation request' and with 'may still be running until it responds'. No new undefined term of consequence, no new repetition, no unsafe lab step. The exercise commands are unchanged. The Windows PowerShell route opens 5.1 while the linked docs are 7.5; this is trivial and Get-Date and Write-Output exist in both.

SCORES. D2 Scaffolding 4 (was 3) and D6 Cognitive Load 4 (was 3). The brief does not name the other D and L dimensions, so I scored them from the call-1 total (31 minus 6 leaves 25 for the other six). My D scores are 4, 4, 4, 4, 4, 4, 4 and 5 for D1 to D8 in order, total 33/40, every D at least 4. L scores are 4, 4, 4, 4 and 5 for L1 to L5, total 21/25, every L at least 4. No dimension is below its floor.

BLOCKING: none. NON-BLOCKING: the unlabelled zsh sample line (P3, finding below), the dense Windows paragraph, and 'foreground' and 'functions' used without a definition.

PROVENANCE AND LIMITS. Reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family) in Claude Code via the Agent SDK. The author is OpenAI Codex, which is outside this family. This is a delta review, call 2 of 2, and is not an acceptance of the PR. Checks performed: git HEAD and diff, sha256, a full read of the page, grep for terms and dangling references, and five Microsoft documentation fetches. Supplied but not independently re-run: the author's build, pipeline and diff-check results and the exercise commands. No Windows, PowerShell or zsh environment exists on the review host, so those parts were judged as prose only.

### Findings (verbatim JSON)

```json
[
 {
  "id": "KD02-D1",
  "title": "Sample 'command not found' line is zsh output but not labelled as such",
  "body": "The error sample was changed to zsh's exact format, but the surrounding text speaks of 'the shell' generally and never says the line is sample zsh output. A Bash user would see 'bash: echoo: command not found' and a PowerShell user would see a different error. This is non-blocking because the prose already says the message is the shell saying it cannot find a program.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal.md",
   "start_line": 326,
   "end_line": 328,
   "claim_type": "present"
  },
  "verbatim": "zsh: command not found: echoo",
  "why_wrong": "The unlabelled shell-specific sample may make a Bash or PowerShell learner think their different message is wrong. The lesson's own rule is to compare with your shell rather than trust one string.",
  "smallest_fix": "Precede the block with a clause such as 'In zsh, a misspelled command looks like this (your shell's wording may differ):'.",
  "sources": [
   "none"
  ]
 }
]
```
