# T01-P01: clearer computer fundamentals and diagnosis practice

Owner #2278. This records a consolidated author correction to module0.1,
not a whole-page source/editorial verdict, numeric score or lead acceptance.
Earlier [P01](2026-10-26-zero-to-terminal-p01.md),
[P01c](2026-10-26-zero-to-terminal-p01c.md) and
[P01d](2026-10-30-zero-to-terminal-p01d.md) findings and evidence remain preserved.

Page: `prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md`.
Candidate SHA-256: `1808bc2e682e20acf0d8a0489319ad9505f5465e675983c58fcffd13f2358b5f`.
Prior published SHA-256: `324d301d718fc51ed3fd63e8dcd72188701de6617dc417174da88bb3aad2115f`.

## Teaching and factual changes

- Remove repeated kitchen explanations and generic engineer/operator rhetoric.
  Drop the unmeasured RAM-to-kitchen capacity tiers and invented photo dialogue.
  Preserve the diagram, worked diagnoses, four historical facts, six quizzes,
  six practice tasks and the optional Kubernetes boundary.
- Explain demand-paged loading and conditional CPU performance; require
  confirming observations before recommending hardware or file deletion.
- Separate process memory, including sharing, from file permissions;
  qualify Windows-reported RAM and ephemeral/persistent volume lifetimes.
- Narrow the Linux/Windows outcome to the local-versus-cluster setup decision
  actually taught and assessed, rather than an unsupported adoption explanation.
- Add graduated diagnosis hints, a decision context and a transfer question.
  Retain read-only practice, uncertainty and the instruction not to induce a fault.
- Replace duplicate/unversioned and unrelated source entries with primary
  support for the explanations above; retain the history citations.

[Independent Grok 4.7 R1](https://github.com/kube-dojo/kube-dojo.github.io/pull/3764#issuecomment-6551102326)
requested missing Mac/Linux command evidence, Task Manager documentation and
removal of prevalence wording. This revision addresses those requests and the
three terminology/navigation nits; exact-revision re-review remains required.
R1 scores were withheld because the citation gate failed.

## Execution and review limits

Native Mac About/Storage and Activity Monitor CPU/Memory were inspected;
inventory and nonzero process readings were observable. The earlier zero-memory
UI reading remains preserved without an asserted cause. Original panes restored;
no process stopped, settings changed or slowdown induced.

Earlier unchanged Mac/Linux stdout and receipts remain reusable execution evidence.
A new Linux observation stopped before container creation because the Docker
socket was unavailable. Windows commands and GUI paths remain unexecuted;
documentation and a Mac walkthrough do not establish their runtime behavior.
Synthetic profiles remain reasoning exercises, not reproduced incidents.

The old verifier's 5,000-word check disagrees with the current rubric's natural
coverage policy; report that diagnostic without padding. Its heuristic alignment
map is not semantic assessment. Source-fetch errors remain separate from factual
truth: blocked direct requests and available primary web representations are
recorded with their different scopes.

Independent exact-revision review, candidate CI, publication and canonical
adoption require their actual evidence. This author note grants none of them.
Do not carry an old approval onto the new page digest or close T01-P01 from this
correction; the remaining page-level gates and module0.2 still belong to the batch.
