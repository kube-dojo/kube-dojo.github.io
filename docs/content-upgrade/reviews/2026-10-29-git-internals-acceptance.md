# Git Internals: scoped acceptance evidence

This record applies to the English Git Internals page at SHA-256
`13c452febb9b558340c7feb3667f9a2514602261c481eaa8dd12884341e3dc94`
and its source seed at SHA-256
`f1dd53f306e97744f679ddd97e598459e5bfcaf61968de739e29b3e1f1f3ce87`.
It supersedes the pending deployment and acceptance checkpoints in the earlier
[full-source record](2026-10-28-git-internals-full-source-p12j.md); it does not
rewrite earlier failed or partial results.

The bound R7 independent source and editorial review covers 156 claims against
73 source snapshots; its full receipt is in the ledger. Its module score was
35/40 and its lab score was 21/25, with every dimension at least 4. The content packet
received independent review and CI in [PR 3640](https://github.com/kube-dojo/kube-dojo.github.io/pull/3640),
and the source binding received independent review in [PR 3659](https://github.com/kube-dojo/kube-dojo.github.io/pull/3659).

The applicable hands-on work is local Git practice, not a required cluster lab.
The frozen practice run bound all 15 Bash fences to the page. The first starts
the child shell; the runner sent the other 14 literal blocks sequentially to
that subprocess and observed each completion marker. Between blocks, the harness
set the prose identity and performed Tasks 3–5 with synthetic edits, hash checks,
commits, a detached commit and its protective branch. This was local macOS Git
2.56 practice; the all-fence receipt does not record its resolved Bash version.
Controls covered 12 setup and selector cases, two current-page CDPATH cases
across Bash 3.2 and 5.3 plus two historical R6 escape reproductions, two real
macOS parent/child PTY cases, five recovery cases, six ref/pack/reset cases,
prose controls, and a synthetic transfer solution. Expected failure cases were
retained; init and some setup faults were simulated. The PTY run did not capture
child status separately. The two optional ConfigMap YAML bodies match historical
cluster fixtures byte for byte; this is not a new cluster or service-behavior run.
Detailed gitignored local receipts are under `.agent/session228/internals-takeover/`.

The primary build passed at `e7b73f6`; [Pages run 40785784418](https://github.com/kube-dojo/kube-dojo.github.io/actions/runs/40785784418)
deployed the unchanged page and seed with the dark diagram readability repair.
Desktop native checks covered the expanded Auto/dark body, diagram inline and
modal, targeted Light rendering, and complete setup-code copy. Navigation checks
were reused from Pages run 40776803484 at `4fa49d7`, with unchanged target bytes. The
full trace and scoped limits are in `.agent/session229/m1-native-fixed/receipt.md`
and the preceding navigation receipt in `.agent/session229/m1-native/receipt.md`.
This is not a claim of full Light or mobile coverage, exhaustive accessibility,
a human learner study, measured learning outcomes, or Ukrainian acceptance.

## Lead acceptance

The lead records **retain** for this exact English page and seed identified above,
subject to independent approval and passing CI at the final metadata head before
merge. Applicable layers pass within these boundaries: page presence and structural
checks cover the current source; technical source and editorial review use the
unchanged genuine R7 receipt (module 35/40, lab exactly 21/25, every dimension at
least 4); lab execution covers the local Git practice and disclosed controls;
deployed smoke covers the completed publication and desktop checks above.
The local evidence does not establish unrestricted paste behavior or new cluster
execution. Learner data and Ukrainian fidelity remain unknown. This acceptance
does not close parent #2278, program #2272, Git P12, or translation work.
