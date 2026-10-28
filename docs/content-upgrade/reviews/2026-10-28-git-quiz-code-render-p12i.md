# T01-P12i: render Git quiz commands in summary headings

Owner #2278; source/editorial #2275, practice #2276 and assessment #2277. Actual native Chrome QA after Pages run 40650892181 succeeded at `20cf6f49ce19c88f22fcb4a6c84fd5c7cfbd113f` found literal Markdown backticks around the edited detached-hotfix command and HEAD in the quiz heading. The original failed observation is preserved; that publication was not marked fully ready.

Six quiz headings used Markdown code spans inside raw HTML summary elements. This repair uses explicit HTML code elements and one span wrapper per heading, matching the existing Advanced Merging question pattern. All seven question texts and answers, outcomes, and 24 fenced examples retain their decoded content. The page digest and scoped references change; its disposition remains `revise`, with full-page source and whole-lab status unknown and all other page rows and five accepted pages unchanged.

The installed Astro Markdown compiler renders all seven proposed headings with code spans and without literal backticks. This is a local compiler check, not a full Starlight layout, deployment or browser pass. Independent exact-head review/CI and merged build/Pages/HTTP/fresh actual Chrome remain distinct delivery gates. Full P12 acceptance, source/rubric/practice completion and UK #2291 remain open; no prior failed browser receipt is restamped.
