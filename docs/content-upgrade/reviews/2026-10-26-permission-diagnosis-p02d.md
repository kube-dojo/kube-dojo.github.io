# T01-P02: permission and diagnostic consolidation

Owner #2278; source/practice/assessment owners #2275/#2276/#2277. Checked 2026-10-26 against base `f79efd0782b9d9746f9e33971ae3669d57c338df`, reusing the completed full reads and #3550/#3552/#3553 execution evidence. Both changed pages remain **revise**; this is a scoped correction, not full-page acceptance or a new rubric score.

## Verified findings and corrections

| Finding | Correction and inspected primary support |
|---|---|
| Directory `w` implied adding/removing names without traversal | Explain `w` plus `x` on the parent, with other restrictions still possible. Linux [open(2), ERRORS/EACCES](https://man7.org/linux/man-pages/man2/open.2.html) covers search and creation permissions; [unlink(2), ERRORS/EACCES and sticky-bit restrictions](https://man7.org/linux/man-pages/man2/unlink.2.html) covers removal. |
| Mode `0600` described absolute lack of access for everyone else | Describe ordinary mode permissions and distinguish privileged access from encryption. [capabilities(7), CAP_DAC_OVERRIDE / CAP_DAC_READ_SEARCH / CAP_FOWNER](https://man7.org/linux/man-pages/man7/capabilities.7.html) supports bypass and administrator roles. [acl(5), mode-bit correspondence](https://man7.org/linux/man-pages/man5/acl.5.html) was also checked: do not invent an ACL exception despite a zero mask. |
| A reveal asserted `brushetta.txt` existed and called it a transposition | Task 3/4 source actually creates `bruschetta.txt`. Make the missing-`c` example conditional and hypothetical; inspect the listing before choosing a cause. |
| Shared-file reveal asserted an unshown mode and owner-only remedy | Make the mode a stated assumption, distinguish additional access rules, and escalate to the owner or an authorized administrator. |
| Default workspace names persisted in two solution notes | Refer to the learner's chosen workspace, preserving the existing substitution instruction and commands. |
| Module 0.5 alternatives row omitted the owner/owned-training scope | Align the row with the surrounding diagnostic instructions; existing real GNU nano and saved-buffer fixture receipts remain separate. |

## Evidence and remaining acceptance

The source locators above were retrieved and read; this does not verify every claim or historical fact on either page. The previous root read notes and cross-provider findings are retained. The correction adds no permission-changing learner commands or new platform assumptions.

Five local macOS ordinary-user checks passed: create/unlink denied with parent write but no search, both allowed with write plus search, file read denied without parent traversal, and unchanged content readable after restoring traversal. They do not execute Linux capabilities/ACL/sticky-bit behavior or prove hosted Ubuntu outcomes. All 176 pipeline tests pass. Module 0.4 passes the verifier including source reachability. Module 0.5's unchanged source list had four transient fetch failures; its enabled structural gates pass with reachability explicitly skipped. This is not a factual source clearance. No administrative access, user-file inspection or provider infrastructure was used.

P02 still needs the complete claim/source map, independent whole-page editorial/rubric review and assessment reconciliation; #2275/#2277 own those layers. Hosted scenario alignment/execution stays with #2276 and labs #96/#97. Existing deployment receipts are revision-bound; current delivery requires independent exact-head review/CI, a merged build and public smoke. Unknown layers remain unknown and D1–D8 unassessed. Preserve these blockers explicitly while advancing to the already-defined T01-P03 batch; do not reopen completed scoped deliveries.
