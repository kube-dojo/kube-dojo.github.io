# T01-P01: clearer computer fundamentals and diagnosis practice

Owner #2278. This records a consolidated author correction to module0.1,
not a whole-page source/editorial verdict, numeric score or lead acceptance.
Earlier [P01](2026-10-26-zero-to-terminal-p01.md),
[P01c](2026-10-26-zero-to-terminal-p01c.md) and
[P01d](2026-10-30-zero-to-terminal-p01d.md) findings and evidence remain preserved.

Page: `prerequisites/zero-to-terminal/module-0.1-what-is-a-computer.md`.
Candidate SHA-256: `c09a7001762d08d4efcb36eed484b1ddc184710e6fb54f640fae4776244f4da8`.
Prior published SHA-256: `324d301d718fc51ed3fd63e8dcd72188701de6617dc417174da88bb3aad2115f`.

## Teaching and factual changes

- Remove repeated kitchen explanations and generic engineer/operator rhetoric.
  Drop the unmeasured RAM-to-kitchen capacity tiers and invented photo dialogue.
  Preserve the diagram, worked diagnoses, four historical facts, six quizzes,
  six practice tasks and the optional Kubernetes boundary.
- Explain that needed program code and data can enter RAM in portions;
  opening an app need not load its entire program and every file at once.
- Compare CPU performance by workload and design; replace premature upgrade
  advice with hypotheses and confirming observations.
- Separate process memory boundaries and file permissions without attributing
  all browser-tab isolation to the operating system.
- Explain that Windows-reported physical memory can differ from installed RAM
  because of firmware reservations; preserve the executable PowerShell commands.
- Distinguish ephemeral-volume lifetime from persistent-volume lifetime.
- Narrow the Linux/Windows outcome to the local-versus-cluster setup decision
  actually taught and assessed, rather than an unsupported adoption explanation.
- Add graduated diagnosis hints, a decision context and a transfer question.
  Retain read-only practice, uncertainty and the instruction not to induce a fault.
- Replace duplicate/unversioned and unrelated source entries with primary
  support for the explanations above; retain the history citations.

Primary locators: Microsoft [Working Set](https://learn.microsoft.com/en-us/windows/win32/memory/working-set),
[Virtual Address Space](https://learn.microsoft.com/en-us/windows/win32/memory/virtual-address-space),
[File Security](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights),
[Win32_ComputerSystem.TotalPhysicalMemory](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-computersystem),
Intel [clock-speed comparison](https://www.intel.com/content/www/us/en/gaming/resources/cpu-clock-speed.html),
and Kubernetes1.35 [volume lifetimes](https://v1-35.docs.kubernetes.io/docs/concepts/storage/volumes/#how-volumes-work).
These are changed-claim author checks, not exhaustive independent source clearance.

## Execution and review limits

Native macOS About/Storage and Activity Monitor CPU/Memory screens were inspected.
The inventory fields and nonzero process CPU/memory readings were observable;
the initial zero-memory UI reading remains preserved as a limitation of that
earlier observation. No cause for it is asserted. The observations do not prove
a slowdown or justify an upgrade. Original Settings/Activity Monitor views were
restored; no process was stopped or system setting changed.

Earlier unchanged Mac and Linux command logs remain reusable execution evidence.
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
