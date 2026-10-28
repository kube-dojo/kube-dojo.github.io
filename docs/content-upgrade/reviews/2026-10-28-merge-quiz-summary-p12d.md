# T01-P12d: keep quiz summary content in one flex item

Owner #2278; source/editorial #2275 and assessment #2277. Browser verification of #3600 confirmed restored answer placeholders but caught a layout regression introduced by code elements directly inside flex summaries: questions4–6 split their text into separate columns. The prior rendering check did not cover the site's CSS layout.

One span now groups each code-bearing summary's content, so inline code flows with the sentence. Only three wrappers change; teaching words, commands and all43fenced bodies remain unchanged. Before submission, a native Chrome preview combined the new quiz HTML with the primary generated page and actual site stylesheet URLs, with scripts stripped and a fixed dark fixture. Questions4–6 rendered as readable paragraphs, and question6 opened with its literal answer placeholder preserved. This preview is separate from deployed verification and changes no browser preference.

The page remains revise; no source/rubric/practical acceptance, Ukrainian fidelity or learner effect is asserted. Original failed browser observations and prior source-review identities are preserved. Exact-head review/CI and merged build/Pages/Chrome remain delivery gates.
