# T01-P02 first slice: first-command workspace ownership

Owner #2278; full 725-line module 0.3 read at `9127745d62b6545e633fb3defc45c9fba2e98352` on 2026-10-26. Module 0.4 and 0.5 are not reviewed by this slice. T01-P02 stays unchecked; module 0.3 is **revise**, with D1–D8 unassessed and full-page evidence incomplete.

## Finding and scoped correction

The walkthrough created fixed names under home, and the hands-on exercise reused `restaurant` with `mkdir -p` before recursively removing it. A pre-existing `~/restaurant` could therefore be modified and deleted. Inspection alone did not establish ownership.

Create `kubedojo-first-commands` without `-p` before file-changing practice, stop on any creation error, enter it and verify location before continuing. Keep walkthrough and hands-on paths inside this newly created workspace, including the diagnostic failure and its solution. Cleanup inspects and removes only that practice tree; final workspace removal is conditional on ownership and disposable contents. This is an explicit learner stop boundary, not a claim that independent pasted commands automatically halt after an earlier error. The whole-root warning remains recognizable in a text fence rather than an executable Bash fence.

[GNU mkdir](https://www.gnu.org/s/coreutils/manual/html_node/mkdir-invocation.html), introductory behavior and `-p`: ordinary creation errors when the path exists; `-p` accepts an existing directory. The installed macOS mkdir manual agrees. This is why repeatable inner-directory creation does not establish ownership of a top-level workspace.

## Evidence and residuals

The enabled structural gates pass (source reachability skipped; the changed mkdir behavior checked separately). A local harness extracted and executed 75 source command lines in order under macOS Bash 3.2 and zsh 5.9 with disposable HOME directories, per-line exit checks and explicit handling of the intended missing-path and no-match results. Both runs relocated the misplaced file, removed the practice workspace and preserved an unrelated `~/restaurant/keep.txt`. Existing-directory, file and symlink collisions each returned nonzero and preserved existing contents. Interactive clear/history examples were excluded; no whole-root command was executed. This verifies the supervised command sequence, not automatic error stopping or hosted Ubuntu lab acceptance. Local script and receipts are preserved outside the tracked diff.

Historical 2026-05-30 module review records prior cross-family repairs to the Toy Story citation, recreation before the cat/grep example, sources and prerequisite chain. Preserve that work as revision-bound evidence. State API reports no fact ledger. No source/history claim is newly cleared merely because this safety correction ships.

Remaining whole-page work includes source/history mapping, editorial and assessment review, platform-specific claims and practical coverage. Observations needing official-manual verification include PowerShell flag generalizations, clear/scrollback behavior, history range and prompt labels. No fabricated historical replacement, learner study or rubric score is supplied. Linux/Windows/WSL/PowerShell/hosted-lab execution stays unknown; macOS shell checks, structural checks, independent review, exact-head CI and publication receipts are separate scoped evidence.
