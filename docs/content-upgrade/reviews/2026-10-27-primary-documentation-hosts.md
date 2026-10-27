# Primary documentation hosts for source verification

Supports #2275/#2278 under #2272. Existing source research rejected official Bash, OpenSSH and Git manuals and Google Research records because their hosts were absent from the deterministic allowlist. A reachable citation does not prove support; this change makes those primary hosts eligible for normal claim-level review.

GNU (`gnu.org`), OpenBSD (`openbsd.org`) and Git (`git-scm.com`) enter the upstream tier for their own manuals and release material. Existing suffix matching also covers `ftp.gnu.org` and `man.openbsd.org`. The [OpenSSH manual index](https://www.openssh.org/manual.html) explicitly links its command manuals to OpenBSD; the [Git project](https://github.com/git/git) and its [command manual](https://git-scm.com/docs/git-log) identify the Git documentation route. The [GNU Bash builtins manual](https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html) and release archive provide current and historical language references.

Google's [Borg, Omega, and Kubernetes research record](https://research.google/pubs/borg-omega-and-kubernetes/) enters the vendor tier. It may support Google's own system or publication facts; vendor evidence remains unsuitable as independent corroboration of competitors or a universal causal result. No neutral-research tier or blanket claim approval is granted.

No fetch/matching logic, wildcard behavior, byte limit, runtime permission or source verdict changes. Negative suffix/lookalike cases remain rejected. Actual source bodies, host classification and proposed tier boundaries are independently reviewed; page/seed digests, complete semantic coverage and publication remain separate gates. No curriculum acceptance, measured benefit or issue closure is asserted.
