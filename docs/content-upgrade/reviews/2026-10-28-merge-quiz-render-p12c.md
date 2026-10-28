# T01-P12c: render quiz command placeholders literally

Owner #2278; source/editorial #2275 and assessment #2277. Desktop browser verification of merged #3599 found quiz answers rendered as raw HTML text: backticks stayed visible and `<merge-commit-hash>` became an element rather than visible command text. A successful site build and HTTP check had not established correct rendering.

The correction adds Markdown boundaries inside all six quiz disclosures and uses HTML code elements for inline code in their HTML summaries. The installed Astro Markdown processor reproduces the old failure and verifies six disclosures, code-styled commands, a literal command placeholder and no custom placeholder element in the corrected quiz. This is a scoped processor check, not a full site/browser result. All43fenced bodies and normalized quiz wording remain unchanged; no lesson Git command was executed.

The module remains revise. Earlier scoped source judgments keep their original run/head identities; no source receipt, numeric rubric, whole-page acceptance, Ukrainian fidelity or learner effect is inferred. Exact-head independent review/CI and merged publication verification remain gates. The original negative browser observation is preserved alongside the successful deployment record, rather than being recast as a passing check.
