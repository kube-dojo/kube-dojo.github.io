# GPT-6.1 Terra: scoped KubeDojo suitability check

Checked 2026-10-26 for #2272. This is a task-level evaluation, not durable provider policy or a global configuration migration.

## Verified availability and scope

[Official release notes](https://learn.chatgpt.com/docs/whats-new/october-26-30-2026) announce Terra in Work/Codex and emphasize image understanding, computer use and clear writing. The [model page](https://developers.openai.com/api/docs/models/gpt-6.1-terra) documents text/image input, text output and relevant tools. These are product capabilities, not measured KubeDojo quality or latency.

The live native catalog and local `codex debug models` both exposed `gpt-6.1-terra`. A real bounded medium-reasoning invocation completed; no substitution was used. The local CLI catalog reported 500,000 context tokens at 95% effective context, while the API page documents 1,050,000. Do not assume API limits apply to this client or change context settings from that comparison. Reasoning options likewise follow each surface's actual schema. Subscription usage is not inferred from API token prices.

## Small pilots and what they establish

| Pilot | Observed result | Limit |
|---|---|---|
| Read-only extraction/editorial suggestion from module 0.5 | Located existing-file modification/cleanup risk and the assumption that a diagnostic file starts non-executable, with path/line references | Scoped sections only; no factual or full-page review |
| Lead challenge to proposed fix | Initial prose used `mkdir -p`, which could reuse an existing directory. Lead rejected that ownership shortcut; Terra corrected it to plain `mkdir` with an explicit stop on error | Shows why suggested edits need judgment; not an authoring benchmark or automatic acceptance |
| Read-only browser pilot on published module 0.4 | Reported permission diagram/table and worked relative/absolute path views readable in the existing desktop dark appearance; closed its own fresh verification tab | Reported observation only; no other viewport/theme, assistive-technology, source or lab clearance |

The lead owns disposition. These pilots did not compare models on identical blinded tasks or establish speed, quota savings, reliability rates or superiority. Pilot notes and sanitized catalog/quota evidence are retained locally, not committed as runtime artifacts.

## Proposed use for this program

- **Try now, bounded and reviewed:** source/claim extraction from supplied material, short editorial suggestions preserving outcomes, page/diagram/table readability checks, and browser smoke with exact screenshots/DOM scope. Every factual claim still needs its own source support.
- **Pilot before routine routing:** small content/code edits with explicit owned paths and deterministic checks. The initial ownership mistake means it should not receive unsupervised safety-sensitive rewrites on this evidence.
- **Retain current ownership:** Astra lead judgment, complex technical/source disputes, acceptance decisions and merge disposition; independent non-OpenAI review before merge. Terra and other OpenAI models are the same provider family for this boundary.

Use a live exposed model/effort and bounded context; no new global default, installed profile, headless-dispatch route, or context configuration was changed or proven by the native canary. Recheck health/quota and client routing before a new lane, preserve existing fallback rules, and do not duplicate healthy work merely to compare models.
