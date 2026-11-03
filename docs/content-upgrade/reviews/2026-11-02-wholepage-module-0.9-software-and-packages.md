# Reviews of prerequisites/zero-to-terminal/module-0.9-software-and-packages.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The lab was not run by either reviewer.

## kd-wp-09-r1: call 1 of 2, whole-page review

- reviewed head: `ca505f93c906f9ad5cf10b24ac995067855937ee`
- run nonce: `49426da9fdb047bbb22139a3970b9ceb`
- verdict: `incorrect` (confidence 0.72)

### Explanation (verbatim)

DISPOSITION: revise (whole-page review, call 1 of 2). Three small BLOCKING fixes, listed below. The D and L floors are not met.

DIGEST: sha256sum of src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md = d5373013bc25dcfbe010a359c01930730780ed17ba033028c86babe27966623d. This matches the digest supplied. git HEAD = ca505f93c906f9ad5cf10b24ac995067855937ee. The page is 733 lines and I read all of it. Its last content commit is cc299d282, authored by Codex.

SCORES. docs/review-contract.md names D1-D8 and L1-L5 but does not define their labels, so the labels below are my reading.
- D1 outcomes and scope: 4. Four clear outcomes. The 'removing' half of outcome 3 is not carried through.
- D2 technical accuracy: 3. Most claims are well hedged and sourced. One mechanism is stated wrongly (removal and dependencies, line 350).
- D3 explanation order and progression: 3. Homebrew terms (formula, cask, Cellar) are used from line 154, 322 and 334 but only defined at line 447. 'Installed' versus 'candidate' is mentioned without a command (line 356).
- D4 practice and lab design: 4. Tasks 1-6 are sensible and have solution notes. There is no removal or cleanup task, and no tiered hints.
- D5 assessment and feedback: 4. Six scenario quiz items with reasoned answers. None covers removal. Q3 and Q6 pre-answer Task 6A and Task 5.
- D6 concision, no bloat: 3. See BLOCKING finding 3.
- D7 examples and engagement: 4. Synthetic transcripts are labelled and hedged, and the predict/reveal blocks are good.
- D8 safety and trust framing: 5. The sudo, Homebrew-without-sudo, curl-pipe-bash and server-update cautions are sound. Nothing is destructive.
- D total: 30/40. All-at-least-4 is not met (D2, D3, D6 = 3). The total of 33 is not met. FLOORS NOT MET.
- L1 executable verification: 4. Each task has an observable success sign.
- L2 safety and cleanup: 3. The lab installs htop and tree but states no uninstall or cleanup step.
- L3 clarity of steps: 4. Ubuntu and macOS pairs are clear.
- L4 expected outputs hedged: 4. Outputs are hedged and synthetic ones are labelled. The apt stderr warning when piping is not mentioned (non-blocking).
- L5 alignment to outcomes: 3. Success criterion 3 ('Evaluate update and removal commands') has no task or quiz item.
- L total: 18/25. FLOORS NOT MET.

SOURCE STATUS: partly supported. I judged 18 material claims. 13 are supported by sources I opened. 5 are UNKNOWN because the fetch failed or I did not open the source (listed under 'Checks performed'). 0 are contradicted by a source I opened, but one (line 350) is a mechanism error confirmed against the apt manual. Details:
- Supported by pages I opened:
  - Homebrew formula install and updates need no sudo.
  - Homebrew's installer command is published on the project's homepage and its docs.
  - apt update downloads package information from configured sources.
  - apt upgrade never removes packages, so an upgrade that would need a removal is not performed.
  - apt list has installed/upgradable listing options.
  - apt show, apt search and apt remove behave as described.
  - brew search covers casks and formulae.
  - brew upgrade upgrades outdated, unpinned packages.
  - brew outdated, brew update, brew list and brew uninstall behave as described.
  - sudo runs a command as another user under the security policy, and logging depends on policy.
  - Tap, Cellar and formula definitions match Homebrew docs.
  - Typosquatting appears in the OWASP page.
- Contradicted or misleading: the line 350 statement about removal leaving dependencies behind.
- UNKNOWN: password-prompt echo suppression (the sudo.man page does not state it), the 'apt installs Recommends by default' claim in the Q5 answer, the dnf and pacman command forms (Fedora and Arch fetches returned an Anubis access-denied page), and the choco, FHS, Debian Policy and Kubernetes-tools URLs, which I did not open. The first two are widely known but unverified by me.

LAB EXECUTION: not run. I did not run the apt and brew commands on this host. Nothing in the evidence shows the author or anyone else executing the lab tasks, so the lab is judged as design and prose only. The Killercoda scenario prereq-0.9-packages (frontmatter) was not opened or run, and the body never mentions it.

BLOCKING FINDINGS (each fits a small PR):
1. Removal is mis-explained and the removal outcome and cleanup are never practiced. Line 350: 'a removal can leave an automatically installed dependency behind because another package still needs it'. With apt, remove takes out only the named package. Its auto-installed dependencies stay behind because nothing removes them until `apt autoremove`; the apt manual says autoremove removes auto-installed packages that are no longer needed. The page never mentions autoremove or purge, never shows what remove leaves behind (the manual says user configuration files), and no task or quiz item covers removal. Line 707 success criterion 3 ('Evaluate update and removal commands...') is therefore unassessed. The lab installs two packages and states no cleanup. Fix: correct the sentence, add a short teach of `apt remove` vs `purge` vs `autoremove` (and `brew uninstall` / `brew autoremove` only if verified), and add a lab task or cleanup step plus one quiz item.
2. Terms used before explanation. 'formula' first appears at line 154 and 'Cellar' at line 322. 'cask' appears at line 334 and is never defined beyond 'a separate kind of definition' in Did You Know item 1 at line 447. A beginner meets them with no definition. Fix: define formula, cask and Cellar once at first use in 'Packages and Package Managers' and drop or shorten the Did You Know item.
3. BLOAT: duplication in lines 398-443 and 445-450. Each concept is stated in a prose paragraph and again in an adjacent table: three patterns (400-404 vs the table at 406-410), three anti-patterns (412-416 vs 418-422), four 'use this vs alternatives' situations (426-432 vs 434-439). 'Inspect package metadata before installing' is restated at about lines 133, 328, 340-346, 392, 402, 409 and 443. Did You Know items 2, 3 and 4 repeat lines 143, 214 and 194. The Q3 answer restates Task 6A and Q6 restates Task 5. Fix: keep one form per concept (prose or table), cut the repeated paragraphs and Did You Know items, and make Q3 or Task 6A distinct.

NON-BLOCKING FINDINGS:
A. Line 162 asks learners to predict the `apt install tree` error but no reveal or expected message follows. A short reveal is needed, such as a 'could not open lock file / are you root?' style permission error, hedged by release.
B. Line 356 says to 'use installed-package information as well' but names no command. `command -v htop` and `apt-cache policy htop` first appear only in the Task 6C solution (line 699). Teach them in the metadata section.
C. Windows learners have no stated path. Line 506 offers 'the Ubuntu/Debian path or the macOS path' only, while the table lists choco. Modules 0.10 and 0.11 point Windows learners at WSL or a lab shell, and the body never mentions the Killercoda lab named in the frontmatter and time chip. One sentence is enough.
D. 'Recommends' vs 'Depends' is unexplained, yet Task 5's `apt-cache depends` prints both and Q5's answer (line 494) says 'apt also installs recommended packages by default' for the first time. Task 4 piped `apt list` prints an 'apt does not have a stable CLI interface' stderr warning, and `-y` is described at line 530 but is not in the command.
E. The order at lines 281-298 lists upgradable packages (stale index) before `apt update`. Reorder to update first, then list.
F. The citation seed (docs/citation-seeds/prerequisites-zero-to-terminal-module-0.9-software-and-packages.json, research run 2026-04-19) describes the old page: Equifax, Homebrew 2009, 60,000 packages and sudo 1980 claims, 8 of 12 marked cannot_be_salvaged. I confirmed none of these remain on the current page, so the seed gives no ledger for the current claims and I checked them myself.

OMITTED-CLAIM DISCOVERY: the unsourced or weakly sourced items are the password-echo claim (line 152), apt Recommends (line 494), the dnf/pacman/choco command forms in the table (lines 125-129), the 'formula builds from source' wording (the Homebrew Formula Cookbook says a formula builds from upstream sources but may use pre-built bottles, so the wording is acceptable), and the 'Kubernetes 1.35+' mentions at lines 33, 414 and 470. The 1.35+ mentions are a version floor with no dated source on the page.

VOLATILE FACTS: no prices or quotas. The 'Kubernetes 1.35+' floor is the only version claim, and it is undated.

SAFETY: acceptable. The sudo, Homebrew installer, curl-pipe-bash and server-update advice is cautious and nothing is destructive.

CHECKS PERFORMED BY ME (tool output this turn): sha256sum; git rev-parse HEAD; git log on the page; full read of the page; reading docs/review-contract.md and docs/content-upgrade/page-completion-plan.md; the citation seed (inspected via Python); grep of page-reviews.json (state awaiting_review, review spent 0, ceiling 2); grep of modules 0.1-0.11 for PATH, WSL, kubedojo-practice and killercoda.

URLS ACTUALLY OPENED: https://docs.brew.sh/Installation, https://docs.brew.sh/Manpage (first 100,000 of 134,810 characters read), https://docs.brew.sh/Formula-Cookbook, https://brew.sh/, https://manpages.debian.org/bookworm/apt/apt.8.en.html (opened twice), https://www.sudo.ws/docs/man/sudo.man/, https://owasp.github.io/www-project-top-10-ci-cd-security-risks/CICD-SEC-03-Dependency-Chain-Abuse (reached after the owasp.org redirect).

URL FETCH FAILURES (UNKNOWN, not pass): https://docs.fedoraproject.org/en-US/quick-docs/dnf/ and https://wiki.archlinux.org/title/Pacman returned an access-denied (Anubis) page. Not opened: Ubuntu Server docs, the Ubuntu apt manpage, Debian Reference, apt-secure, FHS, Debian Policy, the Chocolatey docs and kubernetes.io/docs/tasks/tools.

TAKEN FROM SUPPLIED EVIDENCE, NOT RE-VERIFIED: history in page-reviews.json (old dispositions are void); the Codex authorship of recent commits (read from git log).

PROVENANCE: reviewer = Claude Code (claude-sonnet-5-5, family Anthropic), harness Claude Agent SDK / Claude Code CLI, cross-family from the OpenAI/Codex author. Review kind: whole-page review, call 1 of 2 (fresh, under OO-KD-REREVIEW-1102). Limits: no execution of any command or lab, one Homebrew Manpage chunk unread, several source URLs unopened, and the sudo manual does not address echo behavior.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1-removal",
  "title": "Removal is mis-explained and neither the removal outcome nor lab cleanup is practiced",
  "body": "The page says a removal can leave an auto-installed dependency behind because another package still needs it. For apt, `remove` takes out only the named package. Its auto-installed dependencies are left because nothing removes them until `autoremove`. The apt manual says autoremove removes auto-installed packages that are no longer needed, and that remove leaves user configuration files behind (purge removes those too). The page never teaches autoremove or purge. Success criterion 3 ('Evaluate update and removal commands') at line 707 has no task and no quiz item for removal. The lab installs htop and tree and states no cleanup or uninstall step.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 350,
   "end_line": 350,
   "claim_type": "present"
  },
  "verbatim": "and a removal can leave an automatically installed dependency behind because another package still needs it",
  "why_wrong": "Gives the wrong mechanism for a stated outcome and leaves that outcome untaught and unpracticed. The lab also has no cleanup, which the contract requires of labs.",
  "smallest_fix": "Correct the sentence. Add 3-4 sentences on apt remove vs purge vs autoremove (and brew uninstall). Add a short lab task or cleanup step (for example `sudo apt remove tree` / `brew uninstall tree`) and one quiz item on removal.",
  "sources": [
   "https://manpages.debian.org/bookworm/apt/apt.8.en.html"
  ]
 },
 {
  "id": "F2-terms-before-definition",
  "title": "Homebrew terms formula, cask and Cellar are used long before they are defined",
  "body": "'formula' is used from line 154, 'Cellar' at line 322 and 'cask' at line 334. The only definitions are in Did You Know item 1 at line 447, near the end of the page. 'cask' is never really defined. Homebrew docs define a formula as a package definition that builds from upstream sources (with optional pre-built bottles) and the Cellar as the directory of installed versions.",
  "priority": "P2",
  "confidence": 0.75,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 322,
   "end_line": 322,
   "claim_type": "present"
  },
  "verbatim": "If you installed a formula with Homebrew, uninstall it with Homebrew so the Cellar, links, and package records are handled consistently.",
  "why_wrong": "A beginner meets undefined jargon in the teaching sections. The contract treats a term used before its explanation as blocking under-explanation.",
  "smallest_fix": "Define formula, cask and Cellar in one or two sentences at first use in 'Packages and Package Managers' and remove or shorten Did You Know item 1.",
  "sources": [
   "https://docs.brew.sh/Formula-Cookbook",
   "https://docs.brew.sh/Manpage"
  ]
 },
 {
  "id": "F3-bloat-duplication",
  "title": "BLOAT: patterns, anti-patterns and alternatives are each stated twice, and Did You Know repeats earlier text",
  "body": "The 'Patterns & Anti-Patterns' and 'When You'd Use This vs Alternatives' sections give each idea in a prose paragraph and again in an adjacent table (three patterns at lines 400-410, three anti-patterns at 412-422, four situations at 426-439). 'Inspect metadata before installing' recurs at about lines 133, 328, 340-346, 392, 402, 409 and 443. Did You Know items 2-4 (lines 448-450) repeat lines 143, 214 and 194. Q3 duplicates Task 6A and Q6 duplicates Task 5.",
  "priority": "P2",
  "confidence": 0.7,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 400,
   "end_line": 443,
   "claim_type": "present"
  },
  "verbatim": "The strongest beginner pattern is to use the operating system's package manager first for system tools.",
  "why_wrong": "Duplication is blocking BLOAT under docs/review-contract.md. The learner loses nothing by dropping the second statement of each idea.",
  "smallest_fix": "Keep one form per concept (prose or table) in lines 398-443. Delete Did You Know items 2-4 or replace them with new content. Make Q3 and Task 6A distinct.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N1-unrevealed-prediction",
  "title": "Predict-the-error prompt has no reveal",
  "body": "The learner is asked to predict the `apt install tree` error without sudo. No expected message or reveal follows anywhere in the page.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 162,
   "end_line": 162,
   "claim_type": "present"
  },
  "verbatim": "Before running this, what output do you expect from `apt install tree` without `sudo` on a Linux system?",
  "why_wrong": "A prediction prompt without feedback does not complete the retrieval and feedback loop.",
  "smallest_fix": "Add a collapsible reveal with a hedged permission-denied / 'are you root?' style message.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N2-installed-vs-candidate-command",
  "title": "Installed vs candidate version is mentioned but the checking command is only in a Task 6 solution",
  "body": "Line 356 tells learners to use installed-package information but names no command. `command -v htop` and `apt-cache policy htop` appear first in the Task 6C solution note (line 699).",
  "priority": "P3",
  "confidence": 0.65,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 356,
   "end_line": 356,
   "claim_type": "present"
  },
  "verbatim": "The displayed candidate need not be the installed version; use installed-package information as well when checking what is on the machine.",
  "why_wrong": "Skips a reasoning step. The 'diagnose installed software' outcome relies on commands taught only in a hidden solution.",
  "smallest_fix": "Name and briefly show `apt-cache policy htop` and `command -v htop` in the metadata section.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N3-windows-path",
  "title": "No path stated for Windows learners and the Killercoda lab is not mentioned in the body",
  "body": "The lab offers only Ubuntu/Debian or macOS paths, and the table lists choco with no teaching. Modules 0.10 and 0.11 tell Windows learners to use WSL or a lab shell. The body never mentions the Killercoda lab named in the frontmatter and time chip.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 506,
   "end_line": 506,
   "claim_type": "present"
  },
  "verbatim": "Use either the Ubuntu/Debian path or the macOS path depending on your machine.",
  "why_wrong": "Absolute beginners on Windows have no stated route to complete the lab.",
  "smallest_fix": "Add one sentence: Windows users should use an authorized WSL Ubuntu shell or the linked Killercoda lab.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N4-recommends-unexplained",
  "title": "Apt 'Recommends' appears only in a quiz answer",
  "body": "Q5's answer says apt installs recommended packages by default. The lesson never explains Depends vs Recommends, although Task 5's `apt-cache depends` output shows both. I could not verify the default behavior from a fetched source.",
  "priority": "P3",
  "confidence": 0.55,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/zero-to-terminal/module-0.9-software-and-packages.md",
   "start_line": 494,
   "end_line": 494,
   "claim_type": "present"
  },
  "verbatim": "`apt` also installs recommended packages by default",
  "why_wrong": "New material introduced only in an answer reveal and unsourced in the evidence I could open.",
  "smallest_fix": "Add one sentence in the dependencies section on required vs recommended packages, sourced to the apt documentation, or remove the clause.",
  "sources": [
   "https://manpages.debian.org/bookworm/apt/apt.8.en.html"
  ]
 }
]
```

## kd-wp-09-r2: call 2 of 2, delta review

- reviewed head: `9c5f2f7a1845299ccf33bfbae44b92c34b636d47`
- run nonce: `a75724b02eab4be986deb996afe0dbfa`
- verdict: `correct` (confidence 0.82)

### Explanation (verbatim)

Delta review, call 2 of 2, not acceptance. Reviewer: Claude Code (Sonnet 5.5, claude-sonnet-5-5, Anthropic family, outside the OpenAI/Codex author family), Claude Agent SDK harness, read-only, no package manager run (lab judged as prose and design only).

Task 1: HEAD is 9c5f2f7a1845299ccf33bfbae44b92c34b636d47. Diffstat shows one file changed, 26 insertions and 36 deletions, matching the PR. The page sha256 at HEAD is 28cb8847916f65f32f58ba4a47148258bcd917306803ad395349e226460c884a, as required. I read the whole page.

F1 (removal): CLOSED. Grep for "left behind", "leave an automatically", "dependency behind" returns nothing; the only 'leave ... behind' wording left is the pre-existing line about manually deleting binaries, which is accurate. The new paragraph (line 331) matches the Debian bookworm apt manual I opened: remove keeps usually small modified configuration files, purge removes those leftovers, neither touches the home directory, and autoremove removes automatically installed dependencies no longer needed. 'Read its proposed list' is sound advice. 'Automatically installed dependencies can remain after removal' is now correct. Practice and assessment exist: a Cleanup step (line 572) and Quiz Question 3 (remove/purge/autoremove, check the removal list and other users). Success criterion 3 ('Evaluate update and removal commands') now maps to both. Cleanup placement is acceptable: Tasks 4-6 and their solutions use only htop, apt/brew list, search, show and depends, and Task 6 transcripts are synthetic, so nothing later needs tree. The cleanup is conditional, says 'Otherwise leave it installed', and htop is untouched. Minor wording issue: 'After completing the tasks' sits before Task 4, so it can be read as meaning after Task 3. It does not mislead into harm. brew uninstall is supported: the Homebrew Manpage lists 'uninstall, remove, rm: Uninstall a formula or cask'. The Cellar/links sentence at line 333 is consistent with the Cellar definition. Non-blocking: the macOS path has no analogue to purge/autoremove (brew autoremove exists in the manpage but is unmentioned), and 'check the package list to verify the result' names no command.

F2 (terms before definition): CLOSED. Grep shows formula/Cellar/cask/bottle first defined together at line 116. The first Homebrew command (brew install htop) is at line 120, and the other uses are at lines 156, 228, 234, 333, 345, 377, 389, 548 and 584. Accuracy against https://docs.brew.sh/Formula-Cookbook (Homebrew terminology): formula is a package definition that builds from upstream sources; cask installs pre-compiled binaries; bottle is a pre-built keg poured into the Cellar; Cellar is the directory containing named racks (kegs hold versions). The page's 'directory containing installed formula versions' is a fair beginner simplification, and 'prebuilt bottles' is accurate though bottle is not elaborated.

F3 (bloat): CLOSED. The prose duplicates of Patterns, Anti-Patterns and Alternatives are gone and the three tables stand alone. The Did You Know section is deleted with no dangling reference: grep for did-you-know/'did you know' in the page and for inbound anchors to the module found none; the only repo mentions are citation-seed and page-review indexes, route-level and not anchored. No needed fact was lost: the sudo logging point survives at line 145 ('may log the command'), and the stale-index point is made at line 222 (apt update refreshes the local catalog) and the Common Mistakes row at line 442. The dependency-conflict item survives at lines 202-214.

N1: closed, a reveal was added at line 166 and 'permission or lock-file error, wording varies' is hedged correctly for non-root apt install. N2: closed, apt-cache policy htop and command -v htop were added at lines 371-375, with accurate descriptions (policy shows installed and candidate versions; command -v shows what the shell resolves). N3: mostly closed, line 492 offers an Ubuntu WSL shell or an Ubuntu lab shell and the Killercoda scenario only as 'an additional option', claiming nothing about its content; the URL equals frontmatter lab.url and fetching it shows a page titled Software and Packages | KubeDojo | Killercoda (body not inspectable, so the scenario steps are UNKNOWN). 'Authorized Ubuntu WSL shell' gives no setup path, which is thin but not blocking. The 'read + Killercoda lab' time header still makes sense. N4: closed, the 'recommended packages' clause was removed from Question 5.

sudo apt update before apt list --upgradable (line 289-293) is consistent with the rewritten lead-in; it is repeated in the next block (lines 305-307), a small redundancy, not a defect.

New-claim verification, URLs opened: https://manpages.debian.org/bookworm/apt/apt.8.en.html, https://docs.brew.sh/Formula-Cookbook, https://docs.brew.sh/Manpage (first 100000 of 134810 chars read, which covered uninstall and autoremove), https://killercoda.com/kubedojo/scenario/prereq-0.9-packages (title only). Not re-verified: the earlier UNKNOWN claims about dnf/pacman forms and the choco/FHS/Debian Policy/Kubernetes-tools URLs, unchanged by the delta.

Pre-existing, non-blocking, outside the delta: line 516 says the -y flag auto-answers yes but the shown command has no -y; the apt stderr warning when piping is still unmentioned; the Sources list is unchanged and the citation seed is stale.

Scores (full read). D1 outcomes and scope 4; D2 technical accuracy 4; D3 explanation order 4; D4 practice and lab design 4; D5 assessment 4; D6 concision 4; D7 examples and engagement 4; D8 safety and trust framing 5; D total 33/40, floors met (every D >= 4, total >= 33). L1 executable verification 4; L2 safety and cleanup 4; L3 clarity of steps 4; L4 expected outputs hedged 4; L5 alignment to outcomes 5; L total 21/25, floors met. Prose judgement only; the lab was not run.

BLOCKING: none. NON-BLOCKING: cleanup has no explicit verification command and no macOS analogue for purge/autoremove, and its 'After completing the tasks' wording sits before Task 4; Windows path is a pointer without setup steps; stale -y sentence in Task 2; the repeated sudo apt update. Residual owner: the author or CTO if any of these is later wanted; none required for merge.

### Findings (verbatim JSON)

```json
[]
```
