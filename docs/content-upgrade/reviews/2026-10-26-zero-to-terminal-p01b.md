# T01-P01 continuation: terminal prompts and recovery

Owner #2278; base `fef6f9eb4e45f02e2471a04e078b17ef8ccd9519`, checked 2026-10-26. This resolves the reported R1/R2 patterns from the [full-page review](2026-10-26-zero-to-terminal-p01.md) through scoped edits to module 0.2. Its disposition remains **revise**: remaining source, editorial, practical and assessment gates are incomplete. No D1–D8 score, full-page acceptance or learner outcome is asserted.

| Finding | Correction and retained teaching |
|---|---|
| R1: prompt label treated as decisive machine/user/privilege evidence | Treat labels as clues; compare the session opened with read-only user/hostname checks. Apply the same boundary to the prediction answer, Quiz 3, Common Mistakes and synthetic Transcript D |
| R1: normal versus continuation prompt conflated | Show normal PowerShell `PS C:\Users\Learner>` alongside Bash `>`, zsh `dquote>` and PowerShell `>>` continuation examples; diagnose the changed prompt and unfinished input together |
| R1: Ctrl+C described universally as SIGINT and never copy | Scope SIGINT to Unix terminals and foreground process groups; explain PSReadLine's selected-text copy behavior, configurable bindings and confirmation by a returned prompt |
| R2: redundant prompt-marked practice and rewrite metadata | Keep one text-fence notation example and the deliberate bad-paste transcript; remove duplicate copies from hands-on steps. All runnable exercise commands and recovery tasks remain |
| R3, one historical claim | Distinguish Microsoft's 2019 announcement from Windows Terminal 1.0 in May 2020, with direct release sources |

## Source and execution evidence

- [Microsoft prompts](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_prompts?view=powershell-7.5): built-in normal prompt and user-defined prompt functions; [PSReadLine](https://learn.microsoft.com/en-us/powershell/module/psreadline/about/about_psreadline_functions?view=powershell-7.5), AcceptLine/CopyOrCancelLine: incomplete input, continuation and selection-dependent copying/cancellation. These support text, not Windows execution.
- [zsh prompt expansion](https://zsh.sourceforge.io/Doc/Release/Prompt-Expansion.html), login information and parser-state escapes, supports configurable labels and continuation text. Executed in the existing isolated zsh 5.9 test shell: temporarily displayed `alex@training-vm /tmp $` while the read-only hostname check differed, then restored the original prompt. This demonstrates a misleading label without any remote connection.
- Installed macOS 27.0.1 `termios(4)` INTR entry supports SIGINT to the foreground process group. [Apple's source lines 466–478](https://github.com/apple-oss-distributions/xnu/blob/14e3d835ecf9736db9bf15b7bc859981275e1fc0/bsd/man/man4/termios.4#L466-L478) were checked via GitHub API: commit points to blob `e7fcc5ba0dc61b88d01c10619366e8cee61be0a9`, whose Git blob hash was verified. The POSIX web fetch returned403, so it is not the lesson's cited evidence.
- [Microsoft announcement](https://devblogs.microsoft.com/commandline/introducing-windows-terminal/) (May 6, 2019) and [1.0 release](https://devblogs.microsoft.com/commandline/windows-terminal-1-0/) (May 19, 2020) support the bounded historical correction.
- Prior interactive Bash/zsh literal printing, composition and Ctrl+C unfinished-input checks from #3547 remain applicable: this continuation introduces no new executable command. Linux/WSL/PowerShell/Windows execution remains unknown; no daemon, installation or paid resource started.

R3 phone/Apollo/core/storage and punched-card/hardware-terminal claim mapping remains open under #2278/#2275; the Terminal release distinction does not clear that family. Rendered first-terminal preview links were checked on the public site before this edit. Structural, receipt, pipeline, independent-review, final-head CI and publication checks remain separate delivery evidence to record in the PR/issue. Earlier reports are revision-bound history, not contradictory current acceptance.

Publication reconciliation: [#3546 smoke](https://github.com/kube-dojo/kube-dojo.github.io/issues/2278#issuecomment-6419306963) and [#3547 smoke](https://github.com/kube-dojo/kube-dojo.github.io/issues/2278#issuecomment-6420001065) justify `deployed_smoke: pass` only for their unchanged current digests (three Kubernetes pages, Zero to Terminal hub and module 0.1). This changed module 0.2 stays pending until its own deployment; all other incomplete evidence layers remain unchanged.
