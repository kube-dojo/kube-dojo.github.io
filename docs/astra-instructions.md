# Astra instruction refresh

This change applies the workflow guidance in OpenAI's
[Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).
It changes project instructions and skill packaging, not executable model routes.

## Design decisions

- Keep repository boundaries and required validation in `AGENTS.md`; replace
  duplicated rules and stale model tables with contextual references.
- Run cold-start for issue-driven and pipeline work. Self-contained edits do
  not require services or a full session handoff.
- Define completion as the requested outcome plus applicable validation and
  fixes. Preserve separate authorization for external actions and the
  independent-family review requirement before merge.
- Keep shared skills in `agents_extensions/shared/skills` and their tracked
  Claude mirrors synchronized. Load detailed authoring templates only when
  drafting or restructuring a module.
- Retain curriculum evidence, structure, scoring, and output contracts. A
  shorter instruction entrypoint does not lower the content acceptance bar.

## Review cases

Check these decision boundaries when evaluating the instructions in use:

| Request | Expected behavior |
|---|---|
| Fix a typo in an internal document | Status, isolated edit, relevant checks; no pipeline startup |
| Fix a named module | Inspect live module state, use authoring contract, verify the change |
| Review a module | Use the rubric and required review output; do not rewrite or publish it |
| Explain a code reference to ArgoCD | Do not load a curriculum skill solely for that keyword |
| Deliver a bridge-assigned issue | Continue to the verified PR; preserve organizer merge ownership |
| API is unavailable | Use sufficient local evidence or identify missing state; do not infer health |

Static checks establish valid skill metadata, resolvable references, and matching
mirrors. These cases are review criteria, not a claim of a measured model-quality
improvement or completed live behavioral benchmark.

## Activation boundaries

Review and integrate the branch before treating its instructions as main's
policy. Existing local `.agents/skills` copies are ignored by Git and may differ
from the canonical source. The current `deploy.sh --target codex` writes to
`.codex`, so it does not refresh that `.agents` discovery surface. Inspect and
reconcile those local copies separately before claiming desktop skill activation.

Headless defaults remain in `scripts/dispatch_smart.py`. Changing them to Astra
requires separate adapter, reasoning-setting, and representative invocation
validation; desktop model selection is not evidence of headless compatibility.
