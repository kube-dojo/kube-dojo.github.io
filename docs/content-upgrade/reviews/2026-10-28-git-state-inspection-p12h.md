# T01-P12h: locate Git state across layouts

Owner #2278; source/editorial #2275, practice #2276 and assessment #2277. The selected row remains `revise`: this packet corrects index and HEAD location guidance, not the full source audit or whole-lab practice, which remain unknown.

Primary sources checked 2026-10-28 against Git 2.56.0: [`git rev-parse --git-path`](https://git-scm.com/docs/git-rev-parse), [`gitrepository-layout`](https://git-scm.com/docs/gitrepository-layout), [`git worktree` DETAILS](https://git-scm.com/docs/git-worktree#_details), and [`gitformat-index`](https://git-scm.com/docs/gitformat-index). The captured source is Git commit `a018953688f1b10bddf91bff8747068f5f4746a4`.

Corrected synthetic controls on local Git 2.56.0 checked symbolic, detached and newly committed detached HEAD locators in ordinary, linked, separate-Git-directory and nested-directory contexts, plus the alternate index environment case. The lead also ran the exact changed HEAD shell fence in all four layouts; its symbolic pointer and named `main` ref matched the configured training context. These checks do not cover every lesson example. An initial runner failed because fixtures shared state; that failure and the earlier locator-only success are retained separately and are not relabeled as the final run.

P12 remains unchecked, UK #2291 parked, and five accepted pages untouched. Exact-head independent review, CI and publication are distinct pending gates; none is claimed here.
