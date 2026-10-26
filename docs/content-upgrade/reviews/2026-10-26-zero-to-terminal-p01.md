# T01-P01: first Fundamentals pages

Continuation: [prompt/recovery correction](2026-10-26-zero-to-terminal-p01b.md) reconciles R1/R2 below and one R3 release-history claim. The remaining full-page evidence gaps stay open.

The [source continuation](2026-10-26-zero-to-terminal-p01c.md) reconciles the other named R3 claims; it preserves incomplete whole-page source, editorial and practical gates.

Owner #2278; source base `17f0248b95df16b68098e9018326402cd3a92160`, reviewed 2026-10-26 by the accountable Codex lead. Read the entire Zero to Terminal hub and modules 0.1/0.2, including all explanations, examples, assessments, sources and navigation. Reused #2315/#2319/#2570/#2572/#2574 as bounded delivery history, not acceptance. Live state/reviews were inspected: no target leases or fact ledgers; module reviews are historical, hub review absent, Ukrainian counterparts stale and parked.

## Dispositions and findings

Paths below are relative to `src/content/docs/prerequisites/zero-to-terminal/`. Locations name the base text rather than unstable new line numbers.

| Page | Disposition | Retained strengths and limits |
|---|---|---|
| `index.md` | retain | Optional terminal preview, bounded optional analogy, 11 linked lessons, honest header-derived 940–1220 minute planning range and default Cloud Native route remain sound. No text change required. Retain is not lead acceptance; route and deployment checks remain separate evidence. |
| `module-0.1-what-is-a-computer.md` | revise | Preserve CPU/RAM/storage distinction, worked diagnoses, read-only spec inventory, patterns and explanations. Correct resource reasoning below; remaining source gaps prevent acceptance. |
| `module-0.2-what-is-a-terminal.md` | revise | Preserve GUI/terminal tradeoffs, native PowerShell branch, read-only practice, deliberate error recovery and simulated transcripts. Correct the executed zsh failure; prompt and editorial residuals remain below. |

| ID | Evidence and consequence | Disposition in this correction |
|---|---|---|
| F1 | 0.1 CPU scheduling says a physical core executes only one thread at an instant; SMT is a counterexample | Explain shared processing capacity and hardware threads; qualify the earlier chef analogy too |
| F2 | 0.1 RAM prediction guarantees slowdown from 8 GB plus named programs; Task 3 equates high memory use/swap with a bottleneck | Make behavior conditional; compare pressure/available memory and ongoing paging with symptoms |
| F3 | 0.1 Profile B infers total CPU saturation from one process at 100%; percentage scales vary | Label profiles synthetic; supply system-wide repeated busy/idle measurements and require comparison before hardware purchase |
| F4 | 0.1 scheduler prediction and Quiz 3 imply current free RAM directly determines placement | Distinguish requests/allocatable capacity from live use and pressure taints. Mark Kubernetes preview, matching assessment and task optional on first pass; retain the required Linux outcome/Quiz 6 |
| F5 | 0.1 references an “original module” and generalizes how “most beginners” learn | Replace editorial history and unsupported population claim with a bounded explanation |
| F6 | 0.2 literal `echo "Hello, World!"` fails in interactive zsh with history expansion enabled, producing a continuation prompt | Use single quotes consistently for fixed literal strings; retain double quotes for command composition; update solutions/transcript/success criterion. Remove name substitution, which could introduce an unescaped apostrophe |
| R1 | 0.2 says prompt hostname is “decisive evidence” of execution location, implies prompt symbols identify privilege, and under-explains normal PowerShell versus continuation prompts | Open at this first correction; reconciled in the linked P01b continuation across body and assessments |
| R2 | 0.2 repeats prompt-marked commands in Bash fences and retains rewrite/preserved-notes metadata | Open at this first correction; P01b keeps one recognition example and deliberate bad-paste diagnosis while removing duplicated practice |
| R3 | 0.1 phone/Apollo comparison, storage pricing and historical details lack complete primary claim mapping; 0.2 hardware/punch-card history and 2019 Terminal release wording need precise locators | P01b resolves the Terminal release distinction; P01c reconciles the other named claims. Smithsonian directly supports the moth/prior-terminology fact. Full-page evidence remains incomplete |

These residuals stay in T01-P01 under #2278, with source #2275 and assessment #2277. Do not check the full-page batch complete from this correction. D1–D8 remain **unassessed**: structural success does not satisfy the full citation gate. No learner study or measured reduction in cognitive load is asserted.

## Claim/source inventory checked on 2026-10-26

| Claim family | Exact primary locator and support | Remaining boundary |
|---|---|---|
| Memory pressure and caches | [Apple Memory Pressure](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac), Memory Pressure/Swap Used; [procps free](https://man7.org/linux/man-pages/man1/free.1.html), available/free/cache descriptions | Supports F2; no actual pressure workload or Windows measurement |
| CPU topology and percentages | [Intel Hyper-Threading](https://www.intel.com/content/www/us/en/gaming/resources/hyper-threading.html), What Is Hyper-Threading; [procps top](https://man7.org/linux/man-pages/man1/top.1.html), `%CPU` and Irix/Solaris modes | Supports F1/F3; synthetic profiles are not benchmarks |
| Kubernetes resources | [1.35 resource scheduling](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/manage-resources-containers/#how-pods-with-resource-requests-are-scheduled); [pressure conditions/taints](https://v1-35.docs.kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/#node-conditions) | Supports F4; no cluster execution |
| Literal quoting and composition | [zsh manual section 14.1.1](https://zsh.sourceforge.io/Doc/Release/Expansion.html#History-Expansion) documents interactive expansion inside double quotes and removal of `!"`; [PowerShell 7.5 quoting](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules?view=powershell-7.5) distinguishes literal versus expandable strings | Supports F6; PowerShell documentation is not Windows execution |
| Moth history | [Smithsonian artifact nmah_334663](https://americanhistory.si.edu/collections/object/nmah_334663), Description | Supports 1947 Mark II moth and older engineering use of “bug”; no invented origin story |
| Hub route/workload | All 11 local module headers and linked files, plus 0.2 opening/exercise anchors | 940–1220 minutes is arithmetic from planning estimates, not measured learner timing |

Other source families were read but are not cleared: generic computer/OS/storage behavior; OS-specific GUI/tool availability; all history/market-share assertions; cross-platform interrupt behavior; all full-page assessment claims. Existing linked documentation and historical receipts remain evidence to reconcile, not automatic passes.

## Execution and delivery evidence

- macOS 27.0.1: CPU-brand `sysctl`, RAM `sysctl`, and `df -h /` returned nonempty successful output. Local Bash and zsh present. No settings changed or hardware stress generated.
- Executed interactive `/bin/zsh -f -i`, zsh 5.9 with `BANG_HIST=on`: old double-quoted greeting entered `dquote>`; Ctrl+C recovered; corrected greeting and fixed practice message printed expected text. Composed date/user sentence also executed successfully. Interactive Bash 3.2 printed both corrected literals; unfinished-quote cancellation and composition passed too.
- No local `pwsh`; Docker CLI is installed but daemon socket unavailable. Linux/WSL/Windows execution remains **unknown**. No service startup, installation or billable provisioning occurred.
- Module structural gates, receipt consistency, pipeline/build/CI, independent review and published render checks are separate delivery gates; record their observed results in the PR/issue rather than pre-claiming them here. New digests remain partial review records with source/editorial/practical status incomplete.
- Ukrainian fidelity is deferred until English readiness. No accepted-page, track or program completion follows from these repairs.

[Independent R1](https://github.com/kube-dojo/kube-dojo.github.io/pull/3547#issuecomment-6419550921) found the optional Linux-outcome mismatch and apostrophe substitution issue. Both were corrected before re-review, along with the three clarity nits. This records resolution work, not the final independent verdict.
