# T01-P01: clearer computer fundamentals and diagnosis practice

Owner #2278. Consolidated author correction, not whole-page acceptance.
Earlier [P01](2026-10-26-zero-to-terminal-p01.md), [P01c](2026-10-26-zero-to-terminal-p01c.md) and [P01d](2026-10-30-zero-to-terminal-p01d.md) evidence remains preserved.

Page: `prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md`.
Candidate SHA256: `de2071eb760c01e1e49a3a8e2fc97d5a776e4c07b7d5efdc3837d94c818c867b`.
Prior published SHA256: `324d301d718fc51ed3fd63e8dcd72188701de6617dc417174da88bb3aad2115f`.

## Teaching and factual changes

- Remove repeated kitchen restatements, canned operator rhetoric, unmeasured
  RAM tiers and invented photo dialogue. Preserve the diagram, worked diagnoses,
  four historical facts, six quizzes and six practice tasks.
- Explain demand-paged loading and conditional CPU performance; require
  confirming observations before recommending hardware or file deletion.
- Distinguish process memory, including sharing, from file permissions;
  qualify Windows-reported RAM and ephemeral/persistent volume lifetimes.
- Teach local-OS versus cluster-OS decisions using the Kubernetes control-plane
  requirement. Remove server-prevalence claims throughout prose and tables.
  Distinguish requests from limits and keep the Kubernetes preview optional.
- Add graduated diagnosis hints and transfer practice. Executable commands stay
  unchanged. Remove the unsourced sleep/wake explanation; six mistake rows remain.
- Add primary inventory-tool documentation and prune unrelated source entries.

## Review and execution limits

[Grok R1](https://github.com/kube-dojo/kube-dojo.github.io/pull/3764#issuecomment-6551102326) requested missing command evidence and narrower terminology.
[Grok R2](https://github.com/kube-dojo/kube-dojo.github.io/pull/3764#issuecomment-6551387288) cleared those gaps but found repeated prevalence and sleep claims.
This revision addresses them; exact-revision re-review is required.
Both reviews withheld scores and rejected current canonical adoption.

Native Mac About/Storage and Activity Monitor were observed; earlier Mac/Linux
stdout and receipts are retained. No fault was induced, process stopped or
setting changed. The earlier zero-memory UI reading remains unexplained.
R2 found the Mac choose-your-OS path adequate; Windows remains unexecuted.
The new Docker attempt stopped before creation because its socket was unavailable.

The legacy word-floor diagnostic conflicts with the natural-coverage rubric;
do not pad. Synthetic profiles are reasoning exercises, not reproduced incidents.
Actual CI, publication and canonical adoption remain separate gates.
This note does not close T01-P01 or the remaining module0.2.
