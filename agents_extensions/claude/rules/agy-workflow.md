# agy (Google lane) Multi-Agent Workflow

> **agy** (Antigravity CLI) is the Google lane. It replaced the retired **gemini-cli**
> (no binary since #2125; residual cleanup #2230). Anywhere older docs/handoffs say
> "Gemini", read "the agy Google lane". Authoritative agent routing lives in the
> `dispatch-router` skill (`agents_extensions/shared/skills/dispatch-router/`).

## Agent Orientation (first call)

Before drafting or reviewing, pull the local-API briefing so agy's context is aligned with what's actually in flight:

```bash
curl -s http://127.0.0.1:8768/api/briefing/session?compact=1
curl -s http://127.0.0.1:8768/api/module/{module_key}/state   # diagnostics[] before fixing
curl -s http://127.0.0.1:8768/api/reviews?module={key}        # existing review log before re-reviewing
```

If the API is down, fall back to `STATUS.md` + `git log -20`. See [`scripts/agent_onboarding.md`](../../scripts/agent_onboarding.md) for the full recipe including lease checks and readiness/activity feeds.

## Dispatch Command

Prefer the task-class dispatcher (picks the model + mode per task class):

```bash
# Review (stdout) — cross-family review of a PR/module
.venv/bin/python scripts/dispatch_smart.py review - --agent agy

# Draft / edit content
.venv/bin/python scripts/dispatch_smart.py draft - --agent agy
```

Legacy direct subcommand (general prompt via the agy CLI, stdout capture):

```bash
# General prompt
.venv/bin/python scripts/dispatch.py agy "prompt"

# Post output to a GitHub issue
.venv/bin/python scripts/dispatch.py agy "prompt" --github 66

# Pick the model explicitly (else AGY_DEFAULT_MODEL)
.venv/bin/python scripts/dispatch.py agy "prompt" --model gemini-3.1-pro-high

# Read prompt from stdin
echo "prompt" | .venv/bin/python scripts/dispatch.py agy -

# Ukrainian translation (dedicated path; use agy-translate-file for long modules)
.venv/bin/python scripts/dispatch.py agy-translate "Translate this…"
```

agy model slugs: `gemini-3.5-flash-high` (flash) · `gemini-3.1-pro-high` (pro, `AGY_DEFAULT_MODEL`).

## Programmatic Usage (from Python)

```python
from scripts.dispatch import dispatch_agy, post_to_github

ok, output = dispatch_agy("Review this module…", model="gemini-3.1-pro-high")
if ok:
    post_to_github(66, output, "gemini-3.1-pro-high")

# Ukrainian translation
from scripts.dispatch import dispatch_agy_translate
ok, output = dispatch_agy_translate("Translate…")
```

## agy Roles

**1. Adversary Reviewer (one of the cross-family options)**

Per `docs/review-protocol.md`, every PR review must come from a different model family than the author. agy (Google family) is a cross-family reviewer for Codex- or Claude-authored work **when designated** — not a universal default. (For Claude-authored work, Codex has historically been the more rigorous reviewer on content batches; agy is lighter/faster and a valid alternative.)

When agy is the designated cross-family reviewer:
- Send completed work to agy for review BEFORE closing the issue.
- agy catches: version inaccuracies, missing ACs, scope gaps, technical errors, Russicisms in translations.
- If agy says NEEDS CHANGES, address feedback before closing.
- Post agy's review as a comment on the issue.

**2. Translator (Ukrainian) — the RAG-reviewer seat, NOT the volume author (roster tested 2026-07-04)**
- Volume UK translation is **deepseek-led** (`feedback_uk_translation_roster_tested_2026_07`); agy's UK seat is the **RAG reviewer** (`sources` MCP: russicism / lemma / quote checks).
- agy CAN author single-chunk translations; multi-chunk `agy -p` intermittently hangs (`feedback_agy_translation_authoring_blocked_by_dispatch_gaps`).
- Must follow glossary at `src/content/docs/glossary.md`

**3. Content Drafter (with expansion)**
- Writes first drafts — often needs Claude expansion to full depth
- Use `scripts/prompts/module-writer.md` as the prompt
- Workflow: agy drafts → Claude reads → Claude expands (adds tables, diagrams, code, depth)

**4. Curriculum Planner**
- Good at gap analysis and proposing structure
- Push back if suggestions duplicate existing content (agy sometimes misses what exists)
- Always cross-reference suggestions against actual `docs/` directory

**5. Deliberator (in `ab discuss` channels)**
- For high-leverage decisions, agy participates in `scripts/ab discuss <channel> --with claude,codex,agy` as one of three perspectives.
- Argue from agy's strengths: pedagogical accuracy, source verification, content quality, gap analysis.
- End each turn with `[AGREE]` / `[OPTION X]` / `[DEFER]` — see `.claude/rules/decision-card.md`.
- Don't rubber-stamp. Empty `[AGREE]` votes pollute the deliberation; if no opinion, say `[DEFER]`.
- Frame: distributed deliberation, NOT quorum. LLM priors correlate; the value is option-space + disagreement-surfacing, not democratic voting.

## Content Pipeline
1. **Plan** with agy (gap analysis, module specs, structure)
2. **Draft** — either agy drafts (needs expansion) or Claude writes directly (full quality)
3. **Expand** — if agy drafted, a Claude agent reads and expands to full depth
4. **Review** — cross-family adversary review (if agy drafted it, use Claude or Codex per `docs/review-protocol.md`; score, flag issues)
5. **Fix** — address reviewer feedback
6. **Commit** — with nav updates, READMEs, changelog

## agy Limitations
- Weaker than Claude/Codex at full-depth module authoring from scratch (drafts often need expansion)
- Sometimes flags existing content as "missing" — cross-check against the repo before acting
- Use `scripts/prompts/module-writer.md` when asking agy to draft
