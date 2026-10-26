# T01-P02 continuation: module 0.4 workspace and paths

Owner #2278, source/lab/assessment owners #2275/#2276/#2277; base `e30fd794b1b3f3571bcf6d7cc9781472b3e9853f`, checked 2026-10-26. The full 919-line base page was read and prior review recovered. This is a bounded safety/runnability correction; module 0.4 remains **revise**, T01-P02 unchecked and D1–D8 unassessed.

## Findings and correction

- Navigation ended at `/`, followed later by unbounded relative creation examples. Introduce a new exclusive workspace before file-changing commands, with plain `mkdir`, manual error stops, ownership and location checks; home location alone does not establish disposable contents.
- The worked example assumed it was inside `kubedojo-practice` but created another `kubedojo-practice/recipes/desserts` underneath it. Use paths relative to the verified workspace consistently.
- Hands-on setup accepted an existing project before overwriting recipe files. Require this session's fresh workspace, distinguish full-walkthrough from hands-only state, and explain that `touch` preserves the earlier worked-example contents before deliberate replacement.
- Mark prerequisite-dependent and machine-specific path examples illustrative until their prerequisites exist. Preserve the existing non-secret kubeconfig inspection, outcomes, predictions, assessments and diagnostic teaching.

## Evidence and limits

The creation/worked-example/hands-on source fences were extracted and run under local macOS Bash in child processes with disposable HOME directories. Both full-progression and hands-only paths produced the expected three recipe files without a nested second project. Reruns and existing-directory/file/symlink collisions returned nonzero with existing contents preserved; failed-navigation cases did not continue to writes. Nine recorded cases passed. Bash `-e` in the harness models the instructed manual stop; learner commands do not automatically halt a pasted sequence. This is scoped source execution, not every command on the page or hosted Ubuntu acceptance.

Enabled structural checks pass, with source reachability skipped because the source list is unchanged; no whole-page claim/source clearance is supplied. The exact-path workspace behavior has direct execution evidence. Independent review, final-head CI, merged build and public smoke remain separate delivery gates. Ignored helper/receipts are retained locally, not committed.

Keep the 2026-05-30 review's kubeconfig and illustrative-placeholder safeguards. Sister-repo scenario alignment remains owned by `kube-dojo/kubedojo-labs#96`; do not expand this lesson into unrelated cp/mv/rm/chmod outcomes to fit that scenario. Whole-page source/editorial/permission-scope/assessment work remains incomplete. Linux/Windows/WSL/PowerShell/hosted-lab execution is unknown; no provider, paid infrastructure or real kubeconfig access was used.
