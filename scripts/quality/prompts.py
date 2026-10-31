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
- Map researched outcomes to teaching, appropriate practice and assessment with explanatory feedback. Shared activities are allowed; topic scope must be checked against primary references and learner needs.
- Use supported facts, relevant misconceptions and questions that test the outcomes. Do not manufacture trivia or fill a fixed number of rows, questions or sections.
- Do NOT use emojis.

Before writing, use the lead-supplied researched coverage_plan from this page's existing docs/citation-seeds JSON (matching module_path/module_key; outcomes, essential_topics, source_basis). Scope and omission grounds belong in that non-published plan and require independent acceptance. If these inputs are unavailable, return the evidence-shortfall report; do not invent them or insert planning records into lesson prose.

Migration until #3744: legacy density rejection (1000 prose words / 12 words per line / 18 words per paragraph), the verifier's 5000-word default, short-page tiering and source-count gates may still disagree. Report that disagreement as a non-module shortfall for the lead instead of padding. The runner preserves extraction failures rather than publishing reports.

**Teaching prose:**
- Explain mechanisms, decisions, examples, tradeoffs and failure recovery in connected prose appropriate to the topic and audience. Lists are useful for genuine steps, options and comparisons.
- Length, density and section counts are diagnostics, not evidence of learning. Avoid fragments that omit reasoning, repeated filler and long paragraphs that obscure a simple point.
- If verified material cannot support the requested scope, report the evidence shortfall; never invent detail to satisfy a metric. Required source, execution, preservation and review gates remain separate.

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

Return the COMPLETE module with the applicable missing sections added in the correct positions. Preserve every existing line verbatim. Output only module markdown starting with `---`. If researched inputs or supported content are insufficient, instead return a non-module evidence-shortfall report; the runner records the failed extraction for the lead and preserves the existing lesson. Never manufacture a required section.

Use the lead-supplied coverage_plan from this page's existing docs/citation-seeds JSON; record scope/exclusion grounds there for independent acceptance, never in published lesson prose. If the plan is unavailable, use the shortfall path. Until #3744 lands, legacy density (1000/12/18), 5000-word, short-page and source-count checks may still reject concise work; report disagreements without padding.

If a section to add is `quiz`: outcome-aligned questions with explanatory `<details>` answers, after applicable concept and practice sections.
If `hands-on-exercise`: multi-step `- [ ]` checklist, placed after the quiz.
If `common-mistakes`: supported misconceptions with causes and fixes, after the relevant core content or applicable fact section.
If `did-you-know`: only supported facts that materially aid learning, placed after the core content; report a shortfall rather than manufacture trivia.

Preserve any existing `## Sources` section verbatim — do NOT modify or remove it. Do NOT add a NEW `## Sources` section if one isn't already present (citation insertion runs in a separate stage). Do NOT use emojis.
"""


def review_prompt(
    *,
    module_path: str,
    module_text: str,
    writer_agent: str,
    track: str,
    original_gaps: list[str],
) -> str:
    """Cross-family review prompt.

    Bundles ``docs/quality-rubric.md`` so the reviewer has the scoring
    dimensions in context. v1 had the rubric implicit via
    ``.claude/rules/module-quality.md`` and reviewers would drift.
    """
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
  "rubric_score": <float 1.0-5.0>,
  "teaching_score": <float 1.0-5.0>,
  "must_fix": [<specific, actionable issues — empty list if approve>],
  "nits": [<0-5 minor suggestions — not blocking>],
  "strengths": [<1-4 things done well>],
  "reasoning": "<1-3 sentences explaining the verdict>"
}}

Rules:
- Verdict is "approve" ONLY IF teaching_score >= 4.0 AND rubric_score >= 4.0 AND every original gap is genuinely addressed.
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
