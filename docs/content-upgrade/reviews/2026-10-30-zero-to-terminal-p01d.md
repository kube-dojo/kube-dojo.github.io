# T01-P01d: computer inventory and evidence-led diagnosis

This is a bounded author correction under #2278, not a whole-page source,
editorial, assessment or practice verdict. Module0.1 remains **revise**.
No numeric grade, source-acceptance receipt or lead acceptance is issued.

Candidate: `prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md`.
Page SHA-256: `324d301d718fc51ed3fd63e8dcd72188701de6617dc417174da88bb3aad2115f`.
Previous page SHA-256: `8bf989be5319347e1071d62226fb1db4a381c64b9cae8bcbc802c5fbec0b9be2`.

## Scope of the correction

- Inventory now separates OS identification, installed RAM and filesystem or
  volume capacity; GUI volume names or mount points identify the storage view.
  Linux guidance handles absent version fields honestly. Filesystem capacity
  alone does not identify a physical drive's type or full capacity.
- RAM and storage are identified by labels and roles, not their relative sizes.
  CPU/memory observations may leave insufficient evidence; fullness does not
  establish disk-I/O saturation. Task4 models confirming checks before actions.
- Synthetic ProfileC remains a leading hypothesis. GNU/Linux `PATH` templates
  explain an existing directory/file and failed creation's containing directory,
  and inode availability concerns file creation. The fictional profile supplies
  no real path: describe checks, and do not delete files for the exercise.
- Quiz5 explicitly supplies comparable machines, sufficient storage and a
  memory-demanding workload. Terminal/shell roles and normal saved-data retention
  have boundaries; the laptop/server OS model is no longer a universal claim.
- Existing history, conditional ProfilesA/B, substantive explanations,
  route/frontmatter and optional Kubernetes preview are preserved. Outcome1 is
  refined to identify missing evidence; the other outcomes remain unchanged.

## Author evidence and checks

Configured OpenAI Sol prepared the factual brief and read the complete author
draft for meaning; Terra authored the correction and resolved the beginner
instruction gaps. The Codex lead checked those fixes and the final source links.
This is same-family author QA, not independent approval.

Primary locators: GNU `df` DESCRIPTION/`-i`; systemd `os-release` PRETTY_NAME and
optional VERSION fields; Apple Storage's version-specific paths; Microsoft device
information and Storage; Get-PSDrive's logical-drive examples; POSIX.1-2024 Shell
Introduction and Microsoft's terminal FAQ; procps `top` memory/swap totals and
page-fault fields; `write(2)` NOTES. These documents are linked in Sources.
Minikube requirements informed Quiz5's assumptions but are research context,
not a module citation. Two unrelated/unavailable vendor links are replaced.
An unshipped author draft's archived AI Shell citation was replaced by
the complete primary POSIX chapter and maintained Microsoft terminal FAQ; its
fragment exists. POSIX supports the command-language-interpreter definition,
not terminal emulation or Bash extensions. A retrieved GNU topic was excluded
after two Chrome timeouts and inconsistent checker results; its capture remains.

Complete public response bodies, URI/status/time/hash metadata and safe headers
are retained locally. Relevant passages were inspected; this is not a claim that
all source bodies or every unchanged lesson claim were semantically audited.
NASA, Computer History Museum and Smithsonian originals remain outside this work.
The final source check recorded26 HTTP200s, three redirects and one reported404;
the earlier isolation identified the unchanged Smithsonian URL. Structural and
density gates passed, but overall verification remains T3/not passed because of
source reachability. That fetch failure does not establish historical truth or
falsity. Broader source coverage
and the historical whole-page invocation count remain unknown, not zero.

The lead actually ran `lscpu`, `free -h`, `df -h /`, `cat /etc/os-release`,
`df -h /tmp` and `df -i /tmp` in a cached-image, unprivileged read-only Linux
container with networking disabled, capabilities dropped and no added host
volume mounts: all six exited0. Every
owned container was removed on command exit. The three local macOS CLI examples
also exited0. Container accounting is not physical Mac hardware or a reproduced
ProfileC incident. Windows and GUI paths, live pressure diagnosis, learner timing
and full exercise completion were not tested.

The ledger refreshes only this page's digest/evidence reference and retains its
revise disposition and pending/unknown full-page gates. Historical reviewer refs
are context, not approvals rebound to these new bytes. All other rows, including
the newly accepted Prerequisites hub, are unchanged. Independent exact-head PR
review, CI and subsequent merged build/publication observations are separate
delivery gates; their eventual issue/PR comments do not grant full-page acceptance.
