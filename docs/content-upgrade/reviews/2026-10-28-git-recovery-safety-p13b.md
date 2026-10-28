# T01-P13b: Undo and Recovery safety boundaries

Owner #3610; parent #2278/#2272. This repair preserves the historical scoped deliveries #2924/#2925/#2926 and #2584/#2585. Their completed prediction-card and time-band work is not a current whole-page source or practice acceptance. No other module, Ukrainian page, or batch is accepted here.

The English page digest is `sha256:12f8bd8ac7f077fc74fbeb9f61fd1466b7e3e5ac76756cc9420c0c57d72a3586`. The new 27-candidate citation seed supplies starting claims, not an author's semantic approval; a separate independent verifier must inspect the complete page and discover omissions.

Primary sources checked 2026-10-28: Git 2.56.0 commit `a018953688f1b10bddf91bff8747068f5f4746a4`, with original byte hashes and review-text hashes in `.agent/session228/recovery-full-send/source-catalog.json`. The source set includes the manuals, their relevant revision/sequencer fragments, the faulty-merge guide, historical Git 2.28 init documentation, Kubernetes apply documentation, and Atlassian's incident review.

| Corrected claim | Primary locator and applicability |
|---|---|
| Hard reset can overwrite obstructing untracked paths | [git-reset, DESCRIPTION and `--hard`](https://git-scm.com/docs/git-reset); unrelated untracked files surviving does not protect an obstruction. |
| Default restore reads the index; staged restore reads HEAD | [git-restore, DESCRIPTION/`--source`](https://git-scm.com/docs/git-restore); explicit `--source=HEAD` changes the working file while preserving staged content. |
| Historical checkout updates both index and working file | [git-checkout, path form](https://git-scm.com/docs/git-checkout); the worked contrast and quiz distinguish its destination from restore. |
| Reflog and rescue references do not preserve working edits | [git-reflog, DESCRIPTION](https://git-scm.com/docs/git-reflog), [git-branch, deletion](https://git-scm.com/docs/git-branch), [git-gc, NOTES](https://git-scm.com/docs/git-gc); branch deletion removes its own reflog and recovery depends on surviving evidence/objects. |
| A merge revert does not erase ancestry | [git-revert, `--mainline`](https://git-scm.com/docs/git-revert); distinguish an unchanged merged tip from new fixes on the source branch. |
| Atlassian's site and customer counts differ | [Incident review, Executive summary/What happened](https://www.atlassian.com/blog/how-we-build/post-incident-review-april-2022-outage): 883 sites represented 775 customers; restoration took up to 14 days. |

Local Git 2.56.0 practice ran in newly created temporary repositories with global/system Git configuration excluded and synthetic local identity. `practice-baseline.json` preserves the original-page run; `practice-proposed.json` binds this revised digest. Its 35 assertions compare branch, index and working files for all three reset modes, obstructing versus unrelated untracked files, default/explicit restore, historical checkout, and revert/cherry-pick conflicts with abort and continuation. The actual four hands-on source fences ran unchanged, including both HPA picks; the source branch tip was recovered and preserved, and main excluded the unapproved replica line.

`practice-body-r2.json` records all 14 conceptual Git fences in separate disclosed fixtures. Real object IDs replace illustrative hashes, and editor resolution is supplied where the prose requires it; this is contextual execution, not reproduction of the illustrative log output. `practice-body-r1.json` preserves an initial runner assertion failure caused by stripping Git status's leading space, separate from the corrected successful run.

The YAML files are expressly incomplete Git-history fixtures. The separate `kubectl apply --dry-run=client` illustration remains **unrun**: no real cluster/context or complete manifest was supplied for this stream. Its environment and execution stay unknown. No HPA behavior, production restoration, hosted environment, measured learner time, or learner improvement is asserted.

Structural verification passes all applicable gates, including all 12 Sources URLs returning 200, with 5,074 body words. The pipeline suite passes 176 tests. These checks do not establish semantic source support or independent pedagogical judgment. Primary baseline build `20cf6f49c` passed at the parent lead; it does not validate this unmerged page. Branch CI, exact-head independent PR review, merged build, deployment and actual public browser checks remain separate delivery gates.

The canonical row remains `revise`, with technical source unknown, editorial review pending, whole-page lab execution unknown and deployed smoke pending. A genuine full-page source/rubric audit is a distinct pending activity; no supplied acceptance reference or source receipt is invented here. The issue stays open until all applicable acceptance evidence is resolved, with the optional environment explicitly accounted for.
