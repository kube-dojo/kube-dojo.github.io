# T01-P02 continuation: module 0.5 editor practice

Owner #2278 with source/lab/assessment owners #2275/#2276/#2277; base `26db72cf9ef5ef4db62c74c5660e0c53689cf67a`, checked 2026-10-26. Full 648-line base read and prior review recovered. This bounded correction leaves module 0.5 **revise**, T01-P02 unchecked and D1–D8 unassessed.

## Findings and correction

- Fixed home-level filenames could be modified or removed even if they predated the lesson. Create an exclusive workspace with plain `mkdir` and manual ownership/navigation stop checks; keep editor practice, scripts and optional explicit-file cleanup there.
- A command named `nano` need not provide GNU nano. Require the banner check, preserve supported Ctrl+W practice and label simplified screens illustrative; align both GNU 9.0 search-menu examples with the observed Ctrl+F display. Mark script content as text to enter inside the editor.
- A permission error alone does not establish a missing execute bit. Inspect the owner's mode before the focused fix and escalate persistent access failures instead of blindly repeating chmod. [Linux execve(2), ERRORS/EACCES](https://man7.org/linux/man-pages/man2/execve.2.html) explicitly distinguishes path search, executable/interpreter permission and noexec restrictions; this source was read for the bounded correction.
- Align the two illustrative date samples with the calendar: 2026-03-23 was Monday, verified with the local calendar library. These remain example output, not recorded execution dates.
- Independent R1 identified the save-prompt wording and access-check gaps in the broken-script answer/patterns. Align those with GNU nano 9.0 and the mode-first diagnosis, plus the shortcut table and both illustrative menus. A separate real job-control check also corrected the version-specific suspension guidance.

## Evidence and limits

Fourteen source-script/ownership cases passed in disposable local macOS Bash environments: fresh setup, missing execute permission, first/report scripts, intentional missing-quote failure after granting permission, corrected output, repeat and file/directory/symlink collisions, failed navigation and owned explicit-file cleanup. Saved-editor-buffer fixtures were created synthetically; these runs prove those scripts and paths, not editor keystrokes. Harness `-e` models the instructed manual stop, which is not automatic shell behavior in the learner fences.

Separate real PTY evidence used official GNU nano 9.0 built only in an ignored local toolchain with user nanorc ignored. Save/reopen/search/Ctrl+K-Ctrl+U/edit and final four-line bytes were checked. A failed save to a missing parent retained the modified buffer; discarding it preserved the original file. The default menu displayed Ctrl+F and the Ctrl+W alias worked. In an interactive Bash session, Ctrl+Z displayed the hint to use Ctrl+T then Ctrl+Z; that sequence stopped the editor, `fg` resumed it and Ctrl+X exited without changing the file. Source archive/hash/build logs and PTY receipts are preserved locally. This is macOS GNU nano evidence, not hosted Ubuntu acceptance; the system's `/usr/bin/nano` separately launched UW Pico 5.09 and its observations are not substituted for GNU results.

Enabled structural gates pass; unchanged source-list reachability is skipped, with the changed permission claim separately source-checked. Independent review, final-head CI, merged build and publication remain delivery gates. Preserve the 2026-05-30 artifact/path corrections; sister-repo alignment remains `kube-dojo/kubedojo-labs#97`. Whole-page source/history/editorial/assessment, other-editor/version, other-platform and hosted-lab evidence remain incomplete. No global package/configuration change, paid resource or full-page acceptance is claimed.
