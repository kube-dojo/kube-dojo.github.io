# Reviews of prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for all three: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance.

## kd-wp-01-r1: call 1 of 2, whole-page review

- reviewed head: `fd6d035455b5de30da45ab760e4050aefd85ea51`
- run nonce: `5249a2c110224c93b15bd16b5ddef2a6`
- verdict: `incorrect` (confidence 0.75)

### Explanation (verbatim)

DIGEST: sha256sum of the page at HEAD fd6d035455b5de30da45ab760e4050aefd85ea51 is f12ea5bac233b74d1d0a72236290c888ab643c80b9fcaf231c4abb1bbebe3687, which matches the supplied digest.

SCORES (D1-D8):
- D1 outcomes = 4. Five clear outcomes. Outcome 3 (evaluate whether a Windows or macOS laptop can follow the Linux-based examples) gets only two thin paragraphs.
- D2 structure/progression = 4. The progression from analogy to parts to symptoms to practice is sound. The Kubernetes preview jumps in jargon.
- D3 active learning = 4. Prediction prompts with reveals, Task 3 hints and a transfer check are good. The monitor-reading skill is never worked.
- D4 consequences/tradeoffs = 4. Hedged and specific.
- D5 assessment = 4. Quiz answers agree with the lesson. Quiz 5 is leading, and Quiz 3 and Quiz 6 use untaught terms.
- D6 load management / no bloat = 3. The same worked diagnoses are restated four to six times, and the Patterns, Anti-Patterns and Common Mistakes tables duplicate each other. See BLOCKING B1.
- D7 voice/clarity = 4. Direct, but the 'does not by itself establish' hedge is repeated about 20 times.
- D8 completeness/fit = 4. Pattern, anti-pattern and when-to-use tables are present.
D total = 31/40. The floor (every score >=4) is MISSED on D6 and the total is below 33.

SCORES (L1-L5):
- L1 realistic scenario = 4. Safe, read-only, and a no-change result is allowed.
- L2 progression = 4.
- L3 reasoning over rote = 4.
- L4 hints/feedback/verification = 3. The hints are generic, no expected output is shown for any command, and the page never teaches where to read memory pressure or disk activity (BLOCKING B2).
- L5 transfer = 4. The transfer check is required.
L total = 19/25. The floor is MISSED on L4 and the total is below 21.

DISPOSITION: revise (confidence 0.75).

SOURCE_STATUS: partly supported, with no contradictions found.
- I opened 12 sources. 7 gave semantic support for their page claims:
  - K8s Windows intro: 'you can only run the control plane on Linux ... worker nodes running either Windows or Linux'.
  - K8s resource scheduling: 'the sum of the resource requests of the scheduled containers is less than the capacity of the node'.
  - K8s memory-limit OOM kill.
  - K8s volumes: ephemeral vs persistent lifetimes.
  - NIST: GiB = 1,073,741,824 bytes and GB = 10^9 bytes.
  - CHM: Whirlwind 1953, 'each donut was a bit'.
  - Microsoft Win32_ComputerSystem TotalPhysicalMemory: inaccurate if the BIOS uses some physical memory.
- 3 more were supported or partly supported:
  - Apple storage page: Ventura 13 System Settings > General > Storage; earlier About This Mac > Storage.
  - Apple Activity Monitor: describes the Memory Pressure graph and Swap Used.
  - Microsoft Task Manager page: Processes and Performance views.
- 2 were only partly checked. K8s node-pressure-eviction: conditions are mapped to taints by the control plane. The mapping is confirmed from the page text, but the specific taint names were not seen.
- 3 came back unverifiable or only indirectly supported:
  - Smithsonian record: HTTP 403 on both URLs. The moth and 'bug' prior-usage claims rest only on a web-search summary of the Smithsonian entry, so they are UNKNOWN directly.
  - NASA AGC PDF: too large to fetch. The 36,864 and 2,048 word counts rest only on secondary web-search results, so they are UNKNOWN against the cited PDF.
  - Sandisk SSD vs HDD: the fetch returned navigation text, and the search found only secondary sources. The NAND/platter/shock claim is plausible but UNKNOWN against the cited page.
- The rest of the 94 ledgered claims (the Kingston glossary, man pages, Intel pages, Microsoft Learn pages and others) were NOT independently opened and are taken from the supplied catalog. The catalog is an adoption of the old, void review. Every seed claim in the seed file has judgment null, so the seed is only an unjudged author inventory and no claim has a verdict of record.

LAB_EXECUTION: not run by me. This reviewer has no mac, Windows or terminal evidence. The supplied review note says the macOS and Linux inventory commands and the macOS GUI path were run by the author, that Windows is unexecuted, and that the Docker attempt was abandoned. I judged the exercises as prose. The commands are read-only, safe, and look correct as written. No expected-output samples are shown for them.

BLOCKING FINDINGS:
- B1 (BLOAT, lines 315-317, 392, 473, 494-506, 331-333 vs 362-367). The video-export/CPU-contention diagnosis and the window-switching/RAM-pressure diagnosis are each worked in the 'Reading Symptoms' scenarios, again in Task 4's solution, again as Profiles A/B with reveals, and again in Quiz 1 and Quiz 4. The three-row Anti-Patterns table (331-333) restates rows of Common Mistakes (362-367): 'Buy a bigger hard drive', 'Linux is only for experts' and 'just restart'. Fix: delete the two scenario paragraphs at 315-317, keeping Profiles A and B, and delete the Anti-Patterns table or the duplicated Common Mistakes rows.
- B2 (UNDER-EXPLANATION, lines 111-113, 447, 460). 'Memory pressure', 'available memory', 'storage activity' and 'I/O evidence' are the evidence terms the whole diagnosis relies on. They are never defined, and the page never says where to see them in Activity Monitor, Task Manager or `top`/`free`. Task 3 tells the learner not to call a machine disk-bound 'without relevant I/O evidence', yet disk activity is never shown. Fix: add roughly 4-6 sentences defining these terms and naming where to find them per OS, plus one short clearly labelled synthetic `free -h` and `top` excerpt.
- B3 (UNDER-EXPLANATION, lines 249 and 404). Outcome 3 depends on a one-sentence list that names 'Linux-like environments, remote shells, containers, or virtual machines'. Quiz 6 adds 'WSL' and 'cloud labs'. None of these is explained at that point, and 'container' is only defined later at line 271, in the optional preview. Fix: 3-4 sentences saying that a Windows or macOS laptop typically runs Linux tools via WSL, a virtual machine or a remote Linux machine, and that containers on these laptops commonly use a Linux VM underneath.
- B4 (UNDER-EXPLANATION, lines 267, 275, 292, 386). Quiz 3 and the reveal at 292 use 'Pod', 'node allocatable capacity', 'taints' and 'reconciliation layer' without definition, in an absolute-beginner module, and Quiz 3 sits in the scored quiz. Fix: define Pod, request and taint in one or two lines in the preview, or move Quiz 3 into the preview and simplify the reveal.

NON-BLOCKING:
- N1 (line 356; also line 350). The moth and Apollo Guidance Computer word-count bullets serve no stated outcome. The AGC bullet gives no word size, so it cannot be compared with modern RAM. Optionally cut them. The moth and AGC claims are also UNKNOWN against their cited pages (see source_status).
- N2 (lines 166-174). The HDD/SSD diagram has vague bullets ('Compare capacity and measured performance', 'Check your own device's storage type') with no how-to. Replace them with two concrete facts or remove the diagram.
- N3 (line 113). It lists 'a percentage of current usage' as a possible output, but `df -h` prints a Use% column. Clarify.
- N4 (line 177). Say which tools display binary units (`df -h` and `free -h` use powers of 1024) and which display decimal units.
- N5 (line 240). The text-editor example lists 'Word', which is a word processor.
- N6 (line 396). Quiz 5 states the answer in its stem.
- N7 (line 512). 'inode' is used without definition.

SAFETY: no unsafe sudo, credential, public-exposure or destructive advice found. Tasks and Profiles explicitly forbid changes and deletion.

OMITTED-CLAIM DISCOVERY (unledgered or weakly ledgered): none material beyond those above. Claims at line 249 ('Linux-like environments...' available on macOS/Windows) and line 233 (restart clears RAM) are general and plausible but not specifically sourced. The Windows `Get-PSDrive` output format is not described.

URLS ACTUALLY OPENED:
- v1-35.docs.kubernetes.io windows/intro, configuration/manage-resources-containers (two reads), scheduling-eviction/node-pressure-eviction (two reads), storage/volumes
- physics.nist.gov/cuu/Units/binary.html
- computerhistory.org core-memory page
- learn.microsoft.com Win32_ComputerSystem
- support.apple.com 102624 and Activity Monitor memory page
- support.microsoft.com Task Manager page
Failed or partial:
- americanhistory.si.edu and si.edu: 403
- ntrs.nasa.gov PDF: size error
- sandisk.com: navigation text only
Web searches were used for Smithsonian, AGC and SanDisk, and are secondary only.

PROVENANCE: reviewer is Claude Code with Sonnet 5.5 (claude-sonnet-5-5), Anthropic family, outside the OpenAI/Codex author family. Harness: Claude Agent SDK / Claude Code CLI, read-only checkout. Review kind: whole-page review, call 1 of 2. Checks I performed myself: sha256, a full read of the page, the contract and plan, the review note, the seed and catalog structure, and the source fetches listed above. Checks I took from the supplied evidence: the catalog's 94 SUPPORTED verdicts, the author's execution claims, and the old R4 scores, all of which I treated as history, not authority. Limits: I ran no commands and could not open the Smithsonian, NASA PDF or Sandisk bodies.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B1-repetition-bloat",
  "title": "Same worked diagnoses and caution tables repeated 4-6 times (BLOAT)",
  "body": "The video-export/CPU-contention and window-switching/RAM-pressure diagnoses are worked out in 'Reading Symptoms Like an Operator' (lines 315-317), again in Task 4's solution (line 473), again as Profiles A and B with reveals (lines 493-506), and again in Quiz 1 and Quiz 4. The three-row Anti-Patterns table (lines 329-333) repeats rows of Common Mistakes (lines 360-367), with 'Buy a bigger hard drive', 'Linux is only for experts' and 'just restart' each appearing twice. A hedge sentence of the form 'does not by itself establish the cause' recurs about 20 times.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 315,
   "end_line": 317,
   "claim_type": "present"
  },
  "verbatim": "Hypothetical scenario: your laptop has 16 GB of RAM and a large SSD, but becomes sluggish during a video export.",
  "why_wrong": "The review contract treats repetition and duplication as BLOAT, which is equally blocking with under-explanation. Learners meet the same two examples again and again with no new reasoning step, and the repeated hedging dilutes the one new point each time.",
  "smallest_fix": "Delete the two scenario paragraphs at lines 315-317, since Profiles A and B already teach them with reveals. Drop the Anti-Patterns table, or the matching duplicate Common Mistakes rows. Trim the repeated 'does not establish' sentences in sections that already state it.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "B2-monitor-terms-undefined",
  "title": "Evidence terms (memory pressure, available memory, disk activity/I/O) used but never defined or located",
  "body": "Diagnosis tasks depend on 'memory pressure or available memory', 'ongoing paging' and 'relevant I/O evidence'. The page never defines memory pressure or available memory, and never says where each OS shows them or how disk activity is observed. Task 3 forbids calling a machine disk-bound without I/O evidence but never shows I/O. The solution guidance (line 460) lists only 'Activity Monitor has CPU and Memory tabs', 'Task Manager has Processes and Performance views' and 'top shows CPU and memory'. Apple's own documentation, which the Sources list cites, explains Memory Pressure as free memory, swap rate, wired memory and cached memory, but that never reaches the learner.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 447,
   "end_line": 447,
   "claim_type": "missing"
  },
  "verbatim": "Do not label the machine disk-bound without relevant I/O evidence.",
  "why_wrong": "The key skill the lab assesses (reading resource monitors) lacks both a definition of its core terms and a worked example, so a beginner cannot complete Task 3 or confirm the result. The hints are generic and no expected-output sample exists. This is UNDER-EXPLANATION (a term used before explanation and a missing worked example for a key skill) and it lowers L4.",
  "smallest_fix": "Add roughly 4-6 sentences defining 'available memory', 'memory pressure', 'swap' and 'disk activity', and say where each appears (macOS Memory Pressure graph and Disk tab, Windows Task Manager Performance > Memory and Disk, Linux `free -h` 'available' column). Include one short excerpt labelled synthetic with its interpretation.",
  "sources": [
   "https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac",
   "https://support.microsoft.com/en-au/accessibility/windows/use-a-screen-reader-to-navigate-windows-support-tools"
  ]
 },
 {
  "id": "B3-local-vs-cluster-os-underexplained",
  "title": "Outcome 3 (laptop OS vs Linux examples) is taught in one sentence with undefined terms",
  "body": "The outcome 'Evaluate whether a Windows or macOS laptop can follow later Linux-based Kubernetes examples' is taught mainly through one unexplained list. 'Remote shells', 'virtual machines' and 'containers' are not defined here; 'container' is first defined later, at line 271 in the optional preview. Quiz 6's answer adds 'WSL' and 'cloud labs', which the page never explains.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 249,
   "end_line": 249,
   "claim_type": "present"
  },
  "verbatim": "You can learn from a macOS or Windows laptop using Linux-like environments, remote shells, containers, or virtual machines.",
  "why_wrong": "The learner is asked to evaluate a decision whose options they have not been taught, so the quiz answer must use new vocabulary. The module says it assumes no technical experience. This is UNDER-EXPLANATION (terms used before explanation).",
  "smallest_fix": "Add 3-4 sentences before line 249 explaining that Windows and macOS laptops typically get a Linux environment via WSL, a virtual machine or a remote Linux machine, and that containers on those laptops usually run inside a Linux VM. Define 'virtual machine' in one line, and spell out or define 'WSL' where Quiz 6 first mentions it.",
  "sources": [
   "https://v1-35.docs.kubernetes.io/docs/concepts/windows/intro/"
  ]
 },
 {
  "id": "B4-k8s-jargon-undefined",
  "title": "Quiz and preview use undefined Kubernetes jargon (Pod, taints, allocatable, reconciliation)",
  "body": "The optional preview, its reveal (line 292) and the scored Quiz 3 (line 386) use 'node allocatable capacity', 'node taints', 'Pod' and 'reconciliation layer' (line 267), none of which is defined for absolute beginners. The content is optional preview material, but Quiz 3 sits among the six quiz items. The K8s docs I opened support the facts: scheduling compares the sum of requests with node capacity, and the control plane maps node conditions to taints.",
  "priority": "P2",
  "confidence": 0.65,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 292,
   "end_line": 292,
   "claim_type": "present"
  },
  "verbatim": "Reported memory pressure also affects scheduling through node taints.",
  "why_wrong": "Terms used before explanation in a no-prerequisite module. The facts are correct but not teachable as written, so the reveal and Quiz 3 test vocabulary rather than the RAM-vs-scheduling idea.",
  "smallest_fix": "Define Pod, request and taint in one line each in the preview, or move Quiz 3 into the optional preview and replace 'allocatable' and 'taints' with plain wording ('Kubernetes compares what a workload asks for with what the node has left, and avoids nodes reporting memory pressure').",
  "sources": [
   "https://v1-35.docs.kubernetes.io/docs/concepts/configuration/manage-resources-containers/",
   "https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/"
  ]
 },
 {
  "id": "N1-trivia-moth",
  "title": "NON-BLOCKING: moth and AGC trivia serve no outcome; cited pages not fully verified",
  "body": "The Did You Know moth bullet is unrelated to CPU, RAM, disk or the OS. The AGC bullet gives word counts without the word size needed to compare them with modern RAM. The Smithsonian record returned 403, so its content is unknown; I saw only web-search summaries. The NASA PDF was too large to fetch, so the AGC word counts rest only on secondary sources.",
  "priority": "P3",
  "confidence": 0.55,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 356,
   "end_line": 356,
   "claim_type": "present"
  },
  "verbatim": "In 1947, engineers on the Harvard Mark II found a moth in the machine and taped it into the logbook.",
  "why_wrong": "Off-topic background is BLOAT under the contract, though this is a short labelled aside. The source status of both items is UNKNOWN for the cited pages.",
  "smallest_fix": "Cut the moth bullet and the AGC bullet, or give the AGC word size (16-bit) and tie it to the byte-based units discussion.",
  "sources": [
   "https://www.si.edu/object/log-book-computer-bug:nmah_334663"
  ]
 },
 {
  "id": "N2-hdd-ssd-vague",
  "title": "NON-BLOCKING: HDD/SSD diagram has content-free bullets",
  "body": "The diagram contains bullets such as 'Capacity and price depend on the model' and 'Compare capacity and measured performance', plus 'Check your own device's storage type' with no explanation of how to check the type. They add no knowledge, and the SSD-vs-HDD reasoning is made later, at line 185.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 174,
   "end_line": 174,
   "claim_type": "present"
  },
  "verbatim": "Compare capacity and measured performance",
  "why_wrong": "Instruction-like filler, not teaching content; a learner cannot act on 'check your device's storage type' without a method.",
  "smallest_fix": "Replace the vague bullets with two concrete facts (random-access time, mechanical shock) already supported at line 185, or delete the diagram.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-01-r2: call 2 of 2, delta review

- reviewed head: `453867542714c8142fb4ef282213b06e90cd2dd0`
- run nonce: `23a034483e0944729b6b70f7d6bc9cf7`
- verdict: `incorrect` (confidence 0.6)

### Explanation (verbatim)

DELTA REVIEW, call 2 of 2, not acceptance. TASK 1: HEAD is 453867542714c8142fb4ef282213b06e90cd2dd0. The diff against the PR base touches one file, module-0.1-what-is-a-computer.md (32 insertions, 44 deletions), and the working tree is clean. Page sha256 is 64eb3617faee2c604bf496998b8131d1014735779753beaba31918345ce0cbdd (549 lines). I read the whole page and the call-1 to HEAD diff. B1 CLOSED: the two repeated worked scenarios and the Anti-Patterns table are gone. A 3-row Patterns table stays; Profiles A and B in Task 6 still cover both removed scenarios, and the restart point is made at line 218. Grep finds no remaining Patterns & Anti-Patterns, Smithsonian, NASA, Apollo or moth text, and no inbound anchor to the removed heading anywhere in src. Nothing the quizzes or tasks rely on was removed. B2 PARTLY closed (the one blocking finding): the new definitions of available memory, memory pressure, swap and disk activity, the per-OS locations and the synthetic excerpt are good, but they live only inside the collapsed Task 3 solution (line 431). 'Memory pressure' is used undefined at lines 108, 111 and 172, then in the table at line 294, Quiz 1 and 4, and in the Task 3 checklist and hints, before that definition appears. 'Available memory' is first used at line 111. 'I/O' is never expanded. The synthetic excerpt is internally consistent: 6.0+0.5+1.5=8.0 GiB, swap 0.5+1.5=2.0, and CPU 20+5+75=100. It is labelled synthetic and the interpretation sentence matches it (available 1.2 GiB, swap 0.5 allocated, 75.0 id). B3 CLOSED: line 234 now explains WSL, VM (software-based computer with its own OS), remote Linux machine and container, with Docker Desktop as an example. Quiz 6 (line 375) reuses those terms; 'cloud labs' there is a small unexplained leftover, non-blocking. B4 CLOSED: reconciliation, node allocatable and taints are removed, and Pod is defined at line 260. 'Scheduler' (lines 272, 277) is still not glossed, but line 258 already says Kubernetes uses requests when choosing a node, so this is non-blocking in an optional preview. N1-N7 are all closed: N1 trivia and its sources removed with no dangling link; N2 diagram removed; N3 line 113 notes the df -h percentage; N4 line 162 gives binary vs decimal for free -h and df -h/-H; N5 Word removed; N6 Quiz 5 stem no longer leaks the answer; N7 inodes are glossed as the filesystem's file records (thin but acceptable). NEW-CLAIM VERIFICATION (pages I actually opened): man7 free(1) supports 'available' (estimate for starting new applications without swapping) and the Gi/Mi units; the base-1024 reading for -h is inferred from the unit names, and --si is documented as powers of 1000. man7 df(1) supports -h as powers of 1024, -H as powers of 1000, and -i as inode info. man7 iostat(1) supports device input/output statistics. Apple Activity Monitor memory page supports the Memory Pressure graph and Swap Used in the Memory tab. Apple disk page supports the Disk tab showing reads and writes. Docker FAQ supports 'runs all containers inside a customized Linux VM' (WSL 2 or Hyper-V); it names only Windows, so macOS and Linux hosts are UNKNOWN from that page, but the page's wording is not contradicted. Microsoft linux/install supports WSL, VM and cloud/local VM options (it calls a VM a 'digital version of a physical computer'). Kubernetes 1.35 Pods page supports the Pod definition. The Kubernetes node-pressure page supports the MemoryPressure condition and 'control plane also maps these node conditions to taints' (the taint effect itself was not on the fetched text, so UNKNOWN beyond that). The Kubernetes resource-requests page supports 'sum of requests less than node capacity'. The Microsoft Task Manager support page only mentions memory and disk activity in the Performance tab, not separate Memory and Disk sections, so that wording is UNKNOWN from the cited source; I judge it accurate from general knowledge but cannot say a source I opened supports it. I did not open Microsoft's WSL docs page or the Kubernetes taints page. Minor non-blocking notes: the Windows analog of swap (paging file/committed) is not located, 'wa' in the top excerpt is unexplained, and the 'restrictions on which workloads may be placed' wording is vague but not false. D/L SCORES (information): D roughly 4,4,4,4,4,3,4,4 = 31/40 with the 3 on the evidence-reading/diagnosis dimension, since the key terms are gated behind a solution block. L roughly 4,4,4,4,4 = 20/25 (floor 21, not met). Floors not met overall (D 33/40, L 21/25). BLOCKING: one (F1). NON-BLOCKING: scheduler gloss, I/O expansion, Windows paging file, cloud labs, 'wa'. PROVENANCE: reviewer Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family, outside the OpenAI author family), Claude Code harness with sources MCP available, toolful review at the exact head. CHECKS PERFORMED: git HEAD/diff/status, sha256, grep for stale anchors and terms, whole-page read, source fetches listed above. SUPPLIED, NOT CHECKED: author-reported build, pipeline suite and Linux command runs. Limits: prose factual review only; no GUI or other-OS steps executed.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1-b2-terms-gated-in-solution",
  "title": "Evidence terms are first defined only inside the collapsed Task 3 solution, after many earlier uses",
  "body": "The new definitions of available memory, memory pressure, swap and disk activity, the per-OS locations and the synthetic free/top excerpt are accurate and well built. But they appear only in 'Solution guidance for Task 3', a collapsed block read after attempting the task. Before that point the page uses 'memory pressure' (lines 108, 111, 172, 294, 298), 'available memory' (111) and Quiz 1 and 4 as if known. The Task 3 checklist (lines 415-418) tells the learner to find CPU or memory pressure and mentions 'I/O evidence' with no visible definition or location. 'I/O' is never expanded. A beginner doing the task cannot find the evidence without opening the answer.",
  "priority": "P2",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md",
   "start_line": 431,
   "end_line": 431,
   "claim_type": "present"
  },
  "verbatim": "Available memory estimates RAM that applications can use without swapping; memory pressure describes how well memory is serving current work.",
  "why_wrong": "The call-1 blocker B2 asked that evidence terms be defined and located per OS before learners are asked to use them. The definitions exist but are hidden in an answer block, so the body text and the task itself still use the terms undefined.",
  "smallest_fix": "Move the 2-3 sentence definition of available memory, memory pressure, swap and disk activity (and the per-OS locations, with 'I/O' written as input/output) into visible prose just before the first use (near line 111) or into the visible Task 3 intro. Keep the synthetic excerpt and its worked reading in the solution block.",
  "sources": [
   "https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac",
   "https://man7.org/linux/man-pages/man1/free.1.html"
  ]
 }
]
```

## kd-wp-01-r3: round 3, CTO-granted pinned verification of the B2 fix only

- reviewed head: `8385f06d8df3350b1183026f7f5f30052e314923`
- run nonce: `2ca09c75eff442419fad242655c27fa4`
- verdict: `correct` (confidence 0.88)

### Explanation (verbatim)

Task 1. HEAD is 8385f06d8df3350b1183026f7f5f30052e314923 and the worktree is clean. The diff from 453867542714c8142fb4ef282213b06e90cd2dd0 is exactly one commit (8385f06d8), one file (module-0.1-what-is-a-computer.md), +3/-1. The delta is the new paragraph at line 103 plus the trimmed first paragraph of the Task 3 solution block. Page sha256: 954b4c88301175062fcbb3e58a7085451d3524f1b2e1c7ffd95826ddf297f1bd.

F1 is CLOSED. The new visible paragraph is at line 103, right after the swapping/paging paragraph (line 101). "Available memory" and "memory pressure" are first used in that paragraph at line 103, which is where they are defined. Every later use comes after it, at lines 110, 113, 174, 286, 288, 296 and 300. "Input/output (I/O)" is written out at line 103, before the checklist uses "I/O" at line 420 and the solution block uses it at line 433. The definitions are accurate:
- Available memory estimates RAM usable without swapping, which matches man7 free(1).
- Memory pressure describes how well memory is serving current work, which matches Apple's wording that the graph shows how efficiently memory is serving processing needs.
- Swap is disk space used to move less active data out of RAM, which matches Apple's Swap Used wording.
- Disk activity as I/O reads and writes, not free space, is accurate.

Task 3 reads correctly. The checklist's "relevant I/O evidence" and the hints' "memory pressure and available memory" now point to visible definitions. The trimmed solution block references no removed text. Its first paragraph is self-contained. The synthetic free/top excerpt and its worked reading (available is about 1.2 GiB without swapping, 0.5 GiB of swap allocated but one snapshot cannot show paging, top shows 75% idle) are intact and consistent with the line-103 definitions. The worked reading has no explicit back-pointer to line 103, which is cosmetic only.

Source verification. Opened and read: https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac, which describes the Memory Pressure graph and Swap Used. https://support.apple.com/guide/activity-monitor/view-disk-activity-actmntr1005/mac states to click Disk and that it tracks disk reads and writes. https://man7.org/linux/man-pages/man1/free.1.html defines "available" as an estimate of memory for new applications without swapping, and says free reports physical and swap memory. The swap row layout is implied rather than quoted, and the page's own synthetic excerpt shows it. https://man7.org/linux/man-pages/man1/top.1.html confirms a summary area with CPU lines and memory/swap lines. I read only the first 100,000 of about 126,000 characters, which was enough. https://man7.org/linux/man-pages/man1/iostat.1.html describes system input/output device loading and per-device statistics. Microsoft: my guessed support.microsoft.com URL returned 404. A search found no current official Microsoft page and returned only third-party guides and legacy docs that describe Performance-tab graphs for CPU, memory, disk and network. So the Windows Performance > Memory/Disk sections claim is UNKNOWN against an official source. As prose it is accurate and modest, it does not over-claim, and it is NON-BLOCKING.

New-defect check on the delta. I found no contradiction with other text, no new undefined term, no duplication (the definitions were moved out of the solution block, not copied), no wrong or unsafe statement, and no unhedged volatile fact. The UI locations are named by section and the iostat availability is hedged with "if already available". Residual nit, NON-BLOCKING: the "top shows CPU and memory summaries" clause is accurate but terse.

Scores, for information. D1-D8 total about 34/40, with every D >= 4. L total about 22/25, with every L >= 4. No floor miss attributable to this delta. These scores are my judgement of the delta in its page context and were not compared against call 1's scoring sheet.

BLOCKING: none. NON-BLOCKING: the Windows Task Manager claim lacks an official source (UNKNOWN, accurate prose). The page's Sources list does not contain a Microsoft Task Manager page for this claim.

Provenance: independent reviewer, Anthropic Claude Sonnet 5.5 (claude-sonnet-5-5), Claude Code harness. The author was OpenAI/Codex gpt-6.1-terra, so the reviewer is outside the author's family. Review kind: pinned verification round 3 of the delta only, not an acceptance review. Checks I ran myself: git rev-parse, git diff --stat, git log, the full delta diff, sha256sum, grep for first-use lines, reads of the Task 3 section, and the source fetches above. Supplied by the task and not re-derived: the closure of B1-B4 and N1-N7 from call 2. Limits: no site build or test run, and nothing outside the delta was re-audited.

### Findings (verbatim JSON)

```json
[]
```
