# English coverage execution plan

Owner: accountable content-upgrade lead; program #2272, reporting #3539, Prerequisites #2278, Linux #2279. User direction 2026-10-25: finish English first, prioritize its first two curriculum tracks, and report learner-visible changes in What's New without operational details. This supersedes the local Chapter 1-first scheduling pointer, not its outstanding findings or book gates.

Follow the [full-program ticket map](ticket-map.md): every English page has an exact issue batch; all Ukrainian scope stays owned. #2278 is now, #2279 next; supporting evidence work follows the selected batch. Ticket assignment never counts as review or acceptance.

## One durable progress record

The inventory supplies the denominator, including hubs and supporting pages. [page-reviews.json](page-reviews.json) stores revision-bound supplied dispositions; [review-status.md](review-status.md) preserves findings and scoped correction history. Update receipts after every completed review/correction, with the exact digest and stable report/review/delivery references. Never refresh a digest without reviewing the change and reconciling outstanding findings. Stale, missing and invalid records lose current coverage automatically.

Baseline at `6bbbd0c48`: 1,089 English pages, eight recorded revise dispositions, 1,081 without current records, zero recorded full-page acceptances; 562 Ukrainian pages remain inventoried and parked. Four Prerequisites and two Linux records were reconciled after scoped repairs; they do not claim exhaustive current-head clearance. The other two cover Chapter 1 and its hub. Historical repairs outside these records remain evidence to recover, not accepted pages to assume.

Report review coverage, findings/revision status and explicit acceptance separately. A current receipt proves schema/digest validity only. Acceptance records require explicit lead acceptance references and applicable passing evidence under [the existing contract](evidence-and-acceptance.md); source/book/editorial/human gates remain binding. English completion does not wait on Ukrainian; learner studies are needed for measured-improvement claims, not every correction. Unknown execution stays unknown. Never substitute metadata readiness or PR counts for coverage.

## Milestone 1: Prerequisites, then Linux (100 pages)

Six recorded revise dispositions / 100 pages; 94 pages lack a current review record; no full-page acceptances recorded. Finish the named #2278 editorial residuals, then proceed in learner order. Inspect each section's exact inventory paths before reserving a packet. Each table row covers every Markdown/MDX page directly in that directory; child directories have separate rows. Split reviews into two to four related pages, with smaller bounded correction PRs (<20 files, <=200 aggregate changed lines unless explicitly reviewed otherwise).

| Order | Directory under `src/content/docs/` | Pages | Current recorded dispositions |
|---|---|---:|---:|
| 1 | prerequisites/zero-to-terminal | 12 | 0 |
| 2 | prerequisites/cloud-native-101 | 6 | 2 revise |
| 3 | prerequisites/kubernetes-basics | 9 | 2 revise |
| 4 | prerequisites/philosophy-design | 5 | 0 |
| 5 | prerequisites/git-deep-dive | 11 | 0 |
| 6 | prerequisites/modern-devops | 7 | 0 |
| 7 | prerequisites | 1 | 0 |
| 8 | linux/foundations/everyday-use | 6 | 0 |
| 9 | linux/foundations/system-essentials | 5 | 0 |
| 10 | linux/foundations/container-primitives | 5 | 0 |
| 11 | linux/foundations/networking | 5 | 0 |
| 12 | linux/foundations | 1 | 0 |
| 13 | linux/security/hardening | 5 | 0 |
| 14 | linux/security | 1 | 0 |
| 15 | linux/operations | 5 | 0 |
| 16 | linux/operations/performance | 5 | 0 |
| 17 | linux/operations/troubleshooting | 5 | 2 revise |
| 18 | linux/operations/shell-scripting | 5 | 0 |
| 19 | linux | 1 | 0 |

Prerequisites follows its published Suggested Route. Linux Operations follows its hub's learner route: 8.x administration, performance, troubleshooting, then shell scripting. Its sidebar disagrees and omits the 8.x administration pages; preserve that navigation finding under #2279/#2293. This is a review queue, not a claim that navigation has been fixed.

First new review packet: `prerequisites/zero-to-terminal/{index.md,module-0.1-what-is-a-computer.md,module-0.2-what-is-a-terminal.md}`. Check novice assumptions, explanation, workload and outcomes against the full pages and actual source evidence; preserve supported material. Use existing rubric/source gates rather than a heading or word-count target. Then continue the remaining nine pages in that section. Record exact findings before changing prose.

For each packet: inspect live leases/state/existing reviews and PRs; review full pages and material claims; record retain/revise/expand and unknown layers; fix evidenced concerns; obtain independent review; run applicable checks/execution/render/deployment; reconcile the receipt and owning issue. A blocked lab does not prevent source/editorial work on the next packet, but its page stays incomplete. Avoid speculative completion dates until review throughput and execution prerequisites are established.

Milestone 1 closes only when all 100 pages have current review records, every material finding is resolved, and applicable English acceptance evidence is complete. Then schedule Kubernetes, Cloud, Platform, On-Premises, AI, AI/ML, the history book and shared pages from the still-visible whole-English inventory. Book Chapter 1/73, #2339/#2340, IAM and accessibility residuals stay open; do not clear them by changing scheduling. Preserve #2542 release-stub boundaries. Ukrainian starts after English readiness.

At each session boundary, refresh the tracked review record and owning issues for delivered work, plus the ignored local handoff/do-next pointers. Learner-facing What's New entries describe shipped improvements and useful lesson links; no model names, CI counts, SHAs, pipeline schemas or operational issue lists. Record operational evidence in the review reports instead.
