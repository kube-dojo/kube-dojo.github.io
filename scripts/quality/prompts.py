"""Prompt builders for v2 quality pipeline.

Pure-string functions. Zero I/O, zero side effects. Each prompt is
tested as a string shape plus a small "contains key phrase" assertion,
not as semantic correctness (that's the LLM's job).

Design choice: keep the prompts in one file, not inline in ``stages.py``.
The v1 bug #8 where the review prompt bundled ``docs/quality-rubric.md``
text that penalized missing ``## Sources`` while also saying "ignore
missing Sources" came from the prompt being edited in-place. Centralizing
the builders here makes review-time inspection easier and makes it
possible to snapshot-test them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .worktree import primary_checkout_root

_REPO_ROOT = primary_checkout_root(Path(__file__).resolve().parents[2])
_RUBRIC_PATH = _REPO_ROOT / "docs" / "quality-rubric.md"
_RULES_PATH = _REPO_ROOT / ".claude" / "rules" / "module-quality.md"
_FRAMEWORK_PATH = _REPO_ROOT / "docs" / "pedagogical-framework.md"


def _read(path: Path) -> str:
    """Read a text file, returning an empty string if it's missing.

    Missing framework / rubric isn't a crash — the pipeline degrades
    to a leaner prompt. That said, these files should exist in the
    repo; :func:`assert_required_docs_exist` is called by ``pipeline.py``
    on startup to fail fast if they don't.
    """
    return path.read_text(encoding="utf-8") if path.exists() else ""


def assert_required_docs_exist() -> None:
    """Startup-time check — raise if any prompt-building doc is missing.

    Called from ``pipeline.py`` before any dispatch so a typo'd path
    doesn't send a content-less prompt through the whole rotation.
    """
    missing = [p for p in (_RUBRIC_PATH, _RULES_PATH, _FRAMEWORK_PATH) if not p.exists()]
    if missing:
        def _display(p: Path) -> str:
            try:
                return str(p.relative_to(_REPO_ROOT))
            except ValueError:
                return str(p)
        rel = [_display(p) for p in missing]
        raise FileNotFoundError(f"missing prompt docs: {', '.join(rel)}")


def rewrite_prompt(
    *,
    module_path: str,
    module_text: str,
    teaching_gaps: list[str],
) -> str:
    """Full-rewrite prompt — used when audit score < 4.0 AND the module is
    better rebuilt than patched.

    The writer is told to preserve existing visual aids (tables, ASCII
    diagrams, Mermaid) per ``.claude/rules/module-quality.md``, which
    treats them as protected assets.
    """
    rules = _read(_RULES_PATH)
    framework = _read(_FRAMEWORK_PATH)
    gaps = "\n".join(f"- {g}" for g in teaching_gaps) if teaching_gaps else "(no specific gaps)"
    return f"""You are rewriting a KubeDojo curriculum module. The previous version failed the teaching-quality audit. Your output will be reviewed by a different LLM family (cross-family review) before any merge.

## Module path
{module_path}

## Teaching gaps the audit identified (each MUST be addressed)
{gaps}

## Project quality rules
{rules}

## Pedagogical framework
{framework}

## Current module content
```markdown
{module_text}
```

## Your task

Produce a complete, replacement module that teaches the topic from beginner to senior level. For a complete module, output ONLY its markdown — no preamble, no code-fence wrap, starting with `---` frontmatter and ending with a newline. If verified material is insufficient, return a shortfall report instead of a replacement module; do not disguise that report as publishable lesson content.

Mandatory:
- Preserve the `title:` and `sidebar.order:` from existing frontmatter.
- Do NOT add a Markdown `# Module ...` heading after frontmatter. Starlight renders the visible page H1 from `title:` frontmatter, so a source H1 creates a duplicate title in the rendered page.
- Put top metadata immediately after frontmatter as blockquote lines: `> **Complexity**: ...`, `> **Time to Complete**: ...`, and `> **Prerequisites**: ...`; then add `---`; then use `## What You'll Be Able to Do` for the learning outcomes section.
- Do NOT preserve `revision_pending:` if present in input frontmatter — drop it from output. The banner is a queue marker that the merge step removes; carrying it through into a fresh rewrite would leave a "queued for revision" banner on a freshly-shipped module.
- **Visual-aid preservation is COUNT-BASED, not "best-effort"**: count the input's ` ```mermaid ` fenced blocks, ` ```ascii ` blocks, and `|---|` table rows. Your output MUST contain AT LEAST as many of each. Dropping any is a hard fail that bounces the module back to you.
- **NEVER replace an ` ```ascii ` or ` ```text ` block with a Markdown table.** If a table reads better in your judgment, **add the table next to the ASCII block** — do not remove the ASCII. The same applies to Mermaid: never replace ASCII with Mermaid; keep both. The visual-aid count is checked PER TYPE (mermaid count, ascii count, table count) — substituting one type for another is detected and rejected.
- Preserve any existing `## Sources` section verbatim (heading, ordering, citation lines, URLs). Do NOT modify, reorder, deduplicate, or "improve" entries. Do NOT add a NEW `## Sources` section if one isn't already present — citation insertion runs in a separate downstream stage.
- Address each gap from the audit explicitly.
- Plan enough substantive content to address the stated outcomes, exercise, assessment, sources, and topic. Counts can inform routing and review, but are not proof of factual support, learning, or acceptance. Do not pad with repeated prose, decorative structure, or unsupported facts. If verified material cannot support the requested scope, report the shortfall rather than inventing detail or claiming completion.
- All quiz questions scenario-based (Bloom L3+). No recall questions.
- Exactly 4 "Did You Know?" facts. 6-8 rows in "Common Mistakes". 6-8 quiz questions.
- Do NOT use emojis. Do NOT use the number 47.

**Prose density (v2 routing and pre-commit/merge behavior):**

The unchanged v2 classifier uses these tiers: REWRITE is below 1000 prose words, 12 words per non-blank line, or 18 words per prose paragraph; PASS is at least 1500 prose words, 18 words per non-blank line, and 22 words per prose paragraph; REVIEW is intermediate. REWRITE is the density rejection tier checked before commit/merge. PASS and REVIEW do not establish factual support, source verification, learning effectiveness, or acceptance; the other review and executable gates still apply. These figures are not a total line or word quota.

1. **Pad-bomb (one-sentence-per-paragraph)** — every sentence on its own line, single newlines between sentences. Looks "structured" but reads like a stack of bullets without the bullets. Fail signal: words-per-line < 12.
2. **Punchy-bullets / fragments** — short stubs, two-clause "headers" used as paragraphs, heavy bullet-only sections with no surrounding prose. Fail signal: words-per-paragraph < 18.
3. **Essay-filler** — paragraphs that look dense but say nothing concrete (corporate generality, no examples, no sequencing). Fail signal: w/ln passes but reviewer + audit both downgrade teaching.

**Required prose shape:**
- Prefer an average of 22 words per prose paragraph (target 25–60) and 18 words per non-blank line (target ≥20). A paragraph is text between blank lines, NOT counting code fences, lists, tables, or front-matter blocks.
- Treat 1500 prose words as the stronger PASS classifier tier, not a total-content quota. Prose words are outside code fences, frontmatter, and tables; a REVIEW result is intermediate and is not automatically blocked.
- If verified material cannot support the requested scope or an active gate, use the shortfall-report exception above rather than fabricating detail or claiming completion. This prompt instruction does not create a new machine-enforced publication guard.
- A teaching paragraph should typically be 3–6 sentences long, with the first sentence stating the claim and the rest grounding it with mechanism, example, or trade-off. Do not split that into 4 separate one-sentence paragraphs.
- Bullets are allowed for genuine lists (steps, options, anti-patterns, rules). They are NOT a substitute for explanation. A section that's 90% bullets fails. If you find yourself writing 5+ consecutive single-line bullets where each is essentially a sentence of an argument, merge them into a paragraph.

You are writing for a learner who reads the page top-to-bottom. Flowing multi-sentence paragraphs are how you teach mechanism, sequence, and nuance. Fragmented one-line "paragraphs" are how style guides for status pages are written, and that is the wrong genre.

Return the complete module starting with `---`, or a shortfall report if the honesty exception applies.
"""


def structural_prompt(
    *,
    module_path: str,
    module_text: str,
    missing_sections: list[str],
) -> str:
    """Surgical-addition prompt — used when teaching is OK (score ≥ 4.0 in
    some cases) but structural bits are missing (quiz, exercise, etc.).

    Writer must NOT rewrite existing content — only add what's missing,
    in the canonical section order.
    """
    rules = _read(_RULES_PATH)
    missing = "\n".join(f"- {s}" for s in missing_sections) if missing_sections else "(none)"
    return f"""You are adding missing structural sections to a KubeDojo module. Teaching quality is already adequate — do NOT rewrite existing content. Only append the missing sections in the canonical order.

## Module path
{module_path}

## Sections to add
{missing}

## Project quality rules (for the NEW sections only)
{rules}

## Current module content
```markdown
{module_text}
```

## Your task

Return the COMPLETE module with the missing sections added in the correct positions. Preserve every existing line of the module verbatim. Output only the module markdown — no preamble, no fence wrap. Start with the `---` frontmatter line.

If a section to add is `quiz`: 6-8 scenario-based questions with `<details>` answers, placed after "Common Mistakes".
If `hands-on-exercise`: multi-step `- [ ]` checklist, placed after the quiz.
If `common-mistakes`: 6-8 row table, placed after "Did You Know?".
If `did-you-know`: exactly 4 facts, placed after the core content.

Preserve any existing `## Sources` section verbatim — do NOT modify or remove it. Do NOT add a NEW `## Sources` section if one isn't already present (citation insertion runs in a separate stage). Do NOT use emojis or the number 47.
"""


def review_prompt(
    *,
    module_path: str,
    module_text: str,
    writer_agent: str,
    track: str,
    original_gaps: list[str],
    coverage_plan: dict[str, Any] | None = None,
) -> str:
    """Cross-family review prompt.

    Bundles ``docs/quality-rubric.md`` so the reviewer has the scoring
    dimensions in context. v1 had the rubric implicit via
    ``.claude/rules/module-quality.md`` and reviewers would drift.
    """
    if coverage_plan is None:
        raise ValueError("research coverage plan required before review")
    rubric = _read(_RUBRIC_PATH)
    rules = _read(_RULES_PATH)
    framework = _read(_FRAMEWORK_PATH)
    gaps = (
        "\n".join(f"- {g}" for g in original_gaps)
        if original_gaps
        else "(no prior audit gaps)"
    )
    return f"""You are reviewing a KubeDojo module that was just {track}-ed by {writer_agent}. This is a cross-family review (you must be from a different LLM family than the writer).

## Module path
{module_path}

## Original audit gaps that should now be fixed
{gaps}

## Author research coverage plan (input, not acceptance or source support)
```json
{json.dumps(coverage_plan, ensure_ascii=False, indent=2)}
```

## Quality rubric (scoring dimensions)
{rubric}

## Project-specific quality rules
{rules}

## Pedagogical framework
{framework}

## Module content
```markdown
{module_text}
```

## Your task

Return ONLY a JSON object with this exact shape. No preamble, no reasoning prose before the JSON, no code fence. The JSON object must be the LAST thing in your output.

{{
  "verdict": "approve" | "changes_requested",
  "dimensions": {{"D1": <integer 1-5>, "D2": <integer 1-5>, "D3": <integer 1-5>, "D4": <integer 1-5>, "D5": <integer 1-5>, "D6": <integer 1-5>, "D7": <integer 1-5>, "D8": <integer 1-5>}},
  "dimension_evidence": {{"D1": "<exact candidate quote>", "D2": "<quote>", "D3": "<quote>", "D4": "<quote>", "D5": "<quote>", "D6": "<quote>", "D7": "<quote>", "D8": "<quote>"}},
  "coverage": {{"outcomes": [{{"outcome": "<exact planned outcome>", "teaching": "<candidate quote>", "practice": "<candidate quote>", "assessment": "<candidate quote>"}}], "topics": [{{"topic": "<exact planned topic>", "teaching": "<candidate quote>"}}]}},
  "scope_assessment": {{"basis_checked": <boolean>, "unjustified_omissions": [<items>], "rationale": "<judgment>"}},
  "must_fix": [<specific, actionable issues — empty list if approve>],
  "nits": [<0-5 minor suggestions — not blocking>],
  "strengths": [<1-4 things done well>],
  "reasoning": "<1-3 sentences explaining the verdict>"
}}

Rules:
- Verdict is "approve" ONLY IF every dimension is >=4, total >=33, every planned outcome and topic is covered with exact candidate quotes, scope has no unjustified omissions, and every original gap is addressed. Shared quotes can support multiple outcomes; never invent evidence.
- must_fix entries must be specific — "Quiz Q3 tests recall (what is a Pod?); rewrite as scenario" NOT "improve quiz".
- Ignore the `## Sources` section for scoring — citation insertion runs in a SEPARATE downstream stage (`scripts/citation_backfill.py`), so neither the rubric's "Citation Gate" nor the absence of a Sources section should reduce the score here. The writer was instructed to preserve any pre-existing Sources verbatim and not add a new one; verify that instruction was honored (do not flag absence as a must-fix).
- For track=structural: verify existing content was PRESERVED verbatim (zero edits to pre-existing lines). If any existing line was modified, verdict must be changes_requested.
- For track=rewrite: verify narrative flow (not a bullet list), worked examples present before learner is asked to solve similar, at least 2 inline active-learning prompts.
- Verify the top-of-module format: no source-level `# Module ...` heading after frontmatter, blockquote metadata for complexity/time/prerequisites, separator, then `## What You'll Be Able to Do`. Flag duplicate H1 or inline metadata as a must-fix.
- Preserved visual aids (ASCII, Mermaid, tables): must be present and not removed.

Return the JSON object at the END of your response. Nothing after it.
"""


def citation_verify_prompt(*, page_content: str, claim: str, url: str) -> str:
    """Per-URL citation verification — strict "keep only on supports" policy.

    Critical wording: the LLM must ONLY return ``supports`` when the page
    CLEARLY AND EXPLICITLY backs the claim. The whole point of v2's
    citation pass is to publish zero lies — wishy-washy pages that "kind
    of relate" to the claim must verdict as ``partial``, which the
    pipeline treats as remove.

    Page content is truncated to ~12k chars so the prompt fits the
    smallest Gemini-flash context without cost blow-up on giant docs.
    """
    truncated = page_content[:12000]
    if len(page_content) > 12000:
        truncated += "\n\n[... page truncated for prompt size; verify on what's above ...]"
    return f"""You are a strict fact-checker verifying that a cited web page supports a claim in a curriculum module. The KubeDojo project does not publish unverifiable citations — if you cannot prove the page backs the claim, the verdict is NOT "supports".

## URL
{url}

## Claim being cited
{claim}

## Page content (markdown-ish dump, may be imperfect)
```
{truncated}
```

## Verdict rules (STRICT)

- "supports" — the page CLEARLY AND EXPLICITLY states or demonstrates the claim. The excerpt you return can be pointed to as direct evidence.
- "partial" — the page touches on the topic, implies the claim, is tangentially related, or only partially matches. This is NOT enough — use partial.
- "no" — the page does not back the claim, is off-topic, is behind a login wall, is a 404 / error page, or the content is irrelevant.

## Output

Return ONLY this JSON object. No preamble, no code fence. The JSON must be the LAST thing in your output.

{{
  "verdict": "supports" | "partial" | "no",
  "excerpt": "<up-to-60-word direct quote from the page that supports the claim — empty string if verdict is not 'supports'>",
  "reasoning": "<one sentence why this verdict>"
}}
"""


def build_audit_context(audit: dict[str, Any] | None) -> list[str]:
    """Extract ``teaching_gaps`` from an audit payload for prompt injection.

    Kept here (not in stages) so prompt inputs have a single shape
    contract. If the audit schema evolves, every prompt builder updates
    through this one helper.
    """
    if not audit:
        return []
    gaps = audit.get("teaching_gaps") or audit.get("gaps") or []
    return [str(g) for g in gaps if g]
