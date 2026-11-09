#!/usr/bin/env python3
"""Citation backfill orchestrator — research → inject → verify → diff-lint.

Session 5 (2026-04-19): only the `research` subcommand is implemented.
Inject / verify / diff-lint ship in follow-up sessions once research is
calibrated on the 4 pilot modules.

Usage:
    # Research phase — dispatch Codex, validate URLs, write seed JSON.
    python scripts/citation_backfill.py research <module-key>
    python scripts/citation_backfill.py research --agent codex <module-key>
    python scripts/citation_backfill.py research --dry-run <module-key>
        # emits the Codex prompt to stdout, no dispatch, no writes

    # Other subcommands land later:
    #   inject <module-key>
    #   verify <module-key>
    #   run <module-key>       — all four phases in order
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Re-use the fetcher (sibling module; static tools may not see the path prepend).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_citation import allowlist_tier, fetch  # type: ignore[import-not-found]  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]


def _primary_checkout_root(repo_root: Path) -> Path:
    """Resolve the primary checkout root, even from a worktree.

    AGENTS.md §1 mandates a ``.worktrees/<name>/`` checkout inside the
    primary checkout. Nested dispatch worktrees sit deeper
    (``.worktrees/<agent>/<task>/``). Walk up until the parent
    directory is named ``.worktrees``, then step one more level to
    the primary checkout where ``.venv`` lives.

    Pure function kept testable so a regression can assert both the
    primary-case and the worktree-case without touching the filesystem.
    """
    cursor = repo_root
    for parent in (cursor, *cursor.parents):
        if parent.parent.name == ".worktrees":
            return parent.parent.parent
    return repo_root


#: Absolute path to the primary-checkout venv's Python. AGENTS.md §3
#: forbids sys.executable for subprocess.run because it misses
#: .venv-only deps. Derived from __file__ AND normalized for the
#: worktree layout so the interpreter resolves to the primary venv
#: whether the script is called from the primary checkout or a
#: worktree (worktrees share the primary .venv).
_VENV_PYTHON = str(_primary_checkout_root(REPO_ROOT) / ".venv" / "bin" / "python")
DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
SEED_DIR = REPO_ROOT / "docs" / "citation-seeds"
CITATION_POOL_DIR = REPO_ROOT / "docs" / "citation-pools"
SCHEMA_VERSION = 3  # v3: optional section source pools + source_id references.

CLAIM_CLASSES = {
    "war_story", "incident", "statistic", "standard",
    "vendor_capability", "pricing", "benchmark", "security_claim",
}
TIER_NAMES = {"standards", "upstream", "vendor", "incidents", "general"}
DISPOSITIONS = {
    "supported",
    "weak_anchor",
    "needs_allowlist_expansion",
    "soften_to_illustration",
    "cannot_be_salvaged",
}

# Audience-level calibration (derived from module path) shapes how strict
# the research prompt is about rough numbers, illustrative framings, and
# lesson_point URLs. Foundational beginner content should not demand NIST
# citations for "browsers use memory" — the pipeline stays in service of
# teaching, not over-rigor.
_AUDIENCE_RULES: list[tuple[str, str]] = [
    ("prerequisites/zero-to-terminal/", "absolute_beginner"),
    ("prerequisites/", "beginner"),
    ("linux/foundations/", "beginner"),
    ("k8s/kcna/", "beginner"),
    ("ai/foundations/", "beginner"),
    ("linux/operations/", "intermediate"),
    ("cloud/", "intermediate"),
    ("k8s/cka/", "intermediate"),
    ("k8s/ckad/", "intermediate"),
    ("platform/foundations/", "intermediate"),
    ("ai/", "intermediate"),
    ("linux/security/", "advanced"),
    ("k8s/cks/", "advanced"),
    ("platform/", "advanced"),
    ("on-premises/", "advanced"),
]


def audience_level(module_key: str) -> str:
    for prefix, level in _AUDIENCE_RULES:
        if module_key.startswith(prefix):
            return level
    return "intermediate"


_AUDIENCE_GUIDANCE = {
    "absolute_beginner": (
        "AUDIENCE: absolute beginner (no technical background).\n"
        "Calibration for this tier:\n"
        "- Prefer `soften_to_illustration` or `weak_anchor` for rough "
        "  numbers. Round numbers and order-of-magnitude claims stand "
        "  on their own when framed as illustration.\n"
        "- `cannot_be_salvaged` only for harmful precision (dated "
        "  specific prices, causal overclaims) — NOT for pedagogically "
        "  useful rough numbers.\n"
        "- `lesson_point_url` is OPTIONAL (may be null) when the "
        "  teaching prose is self-evident.\n"
        "- Analogies and connective teaching prose produce NO claim "
        "  entries. If the module says 'the CPU is a chef', that is "
        "  not a factual claim."
    ),
    "beginner": (
        "AUDIENCE: beginner with some exposure to computing.\n"
        "Calibration for this tier:\n"
        "- Mix of `supported` and `soften_to_illustration` is normal.\n"
        "- Primary sources preferred; Wikipedia and MDN acceptable for "
        "  foundational concepts.\n"
        "- `cannot_be_salvaged` only for false precision (dated prices, "
        "  fabricated benchmarks) and opinion-as-fact."
    ),
    "intermediate": (
        "AUDIENCE: practitioner with working knowledge.\n"
        "Calibration for this tier:\n"
        "- Apply the standard disposition rules.\n"
        "- Prefer primary sources; `weak_anchor` only for genuinely "
        "  loose claims."
    ),
    "advanced": (
        "AUDIENCE: senior / exam-track practitioner.\n"
        "Calibration for this tier:\n"
        "- Every dated-specific number, vendor pricing, version-specific "
        "  behavior, or CVE reference → `supported` with a live primary "
        "  source (upstream docs, KEPs, RFCs, CVE DB, vendor pages).\n"
        "- `weak_anchor` is rare at this tier — either you have the "
        "  primary source or you don't."
    ),
}
# Dispositions whose claims get inline citation wraps in the inject step.
CITED_DISPOSITIONS = {"supported", "weak_anchor"}
# Dispositions that drive a prose rewrite of the claim's sentence.
REWRITE_DISPOSITIONS = {"soften_to_illustration", "cannot_be_salvaged"}
# Dispositions that take no action in the current pipeline but surface
# in a review queue for allowlist expansion.
DEFERRED_DISPOSITIONS = {"needs_allowlist_expansion"}
# Claim classes where soften/salvage is never acceptable — these refer
# to real-world events/specs and MUST cite a primary source (or go to
# allowlist expansion). "cannot_be_salvaged" is only valid if the claim
# is demonstrably fabricated and the rewrite REMOVES the claim entirely.
HARD_CITE_CLASSES = {
    "war_story", "incident", "standard", "security_claim", "statistic",
}


SECTION_POOL_PREFERENCE_TEMPLATE = """
## Shared section source pool

This module belongs to a section with a pre-validated shared source pool.
PREFER these sources whenever they can honestly support a claim. Discover a
new URL ONLY if none of the pool entries covers the claim's specific facts.

Section pool reference: `{section_pool_ref}`

{section_pool_sources}

Per-claim pool rules:
- For each claim, prefer a `source_id` from the pool.
- Set `claims[].source_ids` to the pool entries you relied on.
- Only set `proposed_url` to a NEW URL if no pool entry covers that claim's
  specific facts.
- If a pool URL is merely topically adjacent, do not force it. Use
  `needs_allowlist_expansion`, `cannot_be_salvaged`, or a new `proposed_url`
  as appropriate.
"""


# ---- prompt --------------------------------------------------------------


RESEARCH_PROMPT_TEMPLATE = """You are the research step of the KubeDojo citation backfill pipeline.

Your job: read the module below and return a JSON seed file that identifies
every factual claim that requires an inline citation, plus a short Further
Reading list. You do NOT rewrite the module. You do NOT add citations. You
only produce the JSON seed.

## HARD RULE: factual claims about real events MUST be cited

This rule is NON-NEGOTIABLE and overrides every audience calibration
below. The following claim classes have only THREE legal dispositions:
`supported`, `needs_allowlist_expansion`, or `cannot_be_salvaged`.
**`soften_to_illustration` is FORBIDDEN for these classes — the
validator will reject the seed.** The reason: softening an unsourced
anecdote into "for instance, a team might..." preserves the false
specifics (dollar figures, durations, timestamps) under a thin
hedging veil — that's still lying with teaching flavor. The pipeline
exists to stop exactly that.

Pick `cannot_be_salvaged` and rewrite to REMOVE the false specifics
whenever the underlying anecdote is unattributed. Do NOT add
"imagine" / "for instance" framing to a war story with fake-precise
numbers — that's softening, which is forbidden here.

- `war_story` — any anecdote naming a company, person, date, or
  event with quantitative detail ($65,000, 6 hours, 120 seconds).
  - Real and citable → `supported` (allowlisted) or
    `needs_allowlist_expansion` (off-allowlist primary source).
  - Unsourced / fabricated / composite → `cannot_be_salvaged`. The
    rewrite removes the fake specifics: keep the operational lesson,
    drop the unverified numbers and named entities.
    Example: "Within 120 seconds, automated security bots found the
    exposed AWS key… the company had incurred a $65,000 cloud billing
    charge" → "Within minutes of being pushed to a public repo,
    automated scanners can find an exposed AWS key and run up
    significant cloud bills."
- `incident` — same rule. Real outages cite or go to allowlist
  expansion; unattributed incidents collapse the false specifics
  via `cannot_be_salvaged`.
- `standard` — named specifications, regulations, RFCs. Cite the spec.
- `security_claim` — claims about real vulnerabilities, real attacks,
  real defenses. Same three-option rule. An unsourced claim with
  fake-precise impact data → `cannot_be_salvaged` (rewrite to keep
  the security principle, drop the unverified numbers).
- `statistic` — specific statistics, even verifiable ones (RFC-defined
  constants, scientific facts, well-known numbers). Two paths:
  - Real and citable → `supported` with the primary source. The IPv6
    address-space size, RFC-defined ports, established scientific
    constants — these have authoritative URLs. PREFER this path.
  - Truly unciteable / illustrative-only → `cannot_be_salvaged` with
    a rewrite that removes the precise number ("IPv6 has an
    enormous 128-bit address space"). NEVER `soften_to_illustration`.

If you find yourself reaching for `soften_to_illustration` on one of
these classes, switch to `cannot_be_salvaged` (rewrite removing the
specifics) or `supported`/`needs_allowlist_expansion` (find the source).
The schema validator will block any soften on these classes.

Claims that MAY be softened (audience calibration applies):
- `vendor_capability` — IF presented as illustrative ("AWS
  instances can cost a few cents per hour"). SPECIFIC vendor
  behavior statements ("kubelet uses X by default since 1.27") must
  be cited.
- `benchmark`, `pricing` — IF illustrative teaching numbers. Dated
  specific quotes must cite or be removed.

## Universal citation discipline (NOT a prose-style mandate)

IMPORTANT: this section governs CITATION patterns only. It does NOT
tell you to rewrite the module's voice, pacing, or teaching style.
The module's voice is preserved by the inject step (which swaps only
specific sentences, never freely rewrites). Your job here is the
citation layer underneath whatever voice the author chose.

Citation discipline (applies at every audience tier):
- Target density: kubernetes.io/docs. They cite RFCs, KEPs, CVEs,
  upstream design docs — NOT every sentence. Worked examples and
  connective prose carry themselves.
- Cite specifics (dated numbers, CVEs, version-specific behavior,
  vendor capability statements). Do NOT cite teaching flow,
  analogies, or pedagogical framing.
- Prefer one authoritative reference over three adjacent weak anchors.
- Hedging prose ("may", "sometimes", "depending on") is a yellow flag:
  if load-bearing, the specific case should be citable or softened.

What this does NOT mean:
- Do NOT demand the module read like a k8s reference doc. Absolute-
  beginner modules legitimately use warm analogies, longer paragraphs,
  and slower pacing. That's correct for their audience.
- Do NOT flag analogies ("the CPU is a chef") as unciteable. Analogies
  are teaching tools, not factual claims. They produce NO seed entry.

{audience_guidance}

## What MUST be cited (inline in a later step)

- war stories, incident timelines, legal cases
- specific statistics, benchmarks, pricing
- standards, regulations, curricula references by name
- vendor capability claims ("X supports Y since version Z")
- security or safety claims tied to a real incident

## What must NOT produce a claim entry

- teaching analogies ("the CPU is like a chef")
- connective instructor prose ("this matters because...")
- questions, quiz items, exercise steps
- Mermaid diagrams, code blocks, tables (unless the table row is itself a
  factual vendor/statistic claim)

If the module is purely pedagogical with zero hard claims, return an empty
`claims` array and 2–3 Further Reading entries appropriate to the topic.
This is a legitimate, expected output for intro modules.

## CRITICAL: disposition per claim — 5 states, pick the right one

Every claim gets exactly one `disposition`. This is the most
important judgment you make. Do not force URLs that don't honestly
back the claim, but also do not dump teaching examples into an
unfixable bucket — good pedagogy uses grounded hypotheticals.

- **`supported`** — URL's page directly discusses THIS specific
  claim. K8s Windows-support → `kubernetes.io/docs/concepts/windows/`.
  Transformer paper → `arxiv.org/abs/1706.03762`. Primary source.

  **HARD TEST** before choosing `supported`: can you point at a
  specific passage in the URL that contains THIS claim's facts —
  the specific number, date, named entity, or quoted phrase? If
  you cannot honestly answer "yes, that exact passage is on that
  page," DO NOT use `supported`. A topically-adjacent URL is NOT
  support. Vendor homepages and "what is X" landing pages
  almost never back specific stat claims like "200+ services" or
  "10,000 customers" — those numbers float across marketing
  contexts and the homepage rarely repeats them verbatim.

  When in doubt, pick `cannot_be_salvaged` (rewrite to remove the
  specific) or `needs_allowlist_expansion` (the right primary
  source is off-allowlist). Removing a load-bearing number is
  better than citing a URL that doesn't actually back it — the
  semantic verifier WILL catch the mismatch and the seed will fail.

- **`weak_anchor`** — URL is a category/topic page that touches the
  subject but doesn't confirm the specific number/event. Acceptable
  ONLY for loose claims ("browsers use memory"); never for specific
  ones.

- **`needs_allowlist_expansion`** — the claim is REAL and
  VERIFIABLE, but its primary source is NOT on the allowlist.
  Set `proposed_url` to the URL you WOULD have used (the off-list
  primary source). Set `proposed_tier` to null. The claim stays in
  the module unchanged for now; a separate allowlist-review process
  decides whether to add that domain.
  Example: GitLab 2017 outage → `about.gitlab.com/.../postmortem/`.
  If that host is not in the allowlist below, this is the right
  disposition.

- **`soften_to_illustration`** — the module uses a SPECIFIC number
  or scenario as a TEACHING EXAMPLE for a real underlying principle.
  The number itself isn't citable (it's illustrative), but the
  LESSON POINT is. Supply TWO things:
  1. `suggested_rewrite`: the sentence rewritten with explicit
     framing: "for instance,", "imagine", "a typical case", or an
     approximate form ("roughly"). Keep the pedagogical force.
  2. `lesson_point_url`: an allowlisted URL citing the GENERAL
     principle the example teaches (e.g. over-provisioning is
     common, browser memory varies widely).
  `proposed_url` / `proposed_tier` null.
  Example: "a team might pay $400/month for a 32GB server when
  they only use 2GB" → rewrite as "a team might easily pay
  hundreds of dollars per month for a server they only use a
  fraction of" + lesson_point_url to a FinOps / right-sizing doc.

- **`cannot_be_salvaged`** — false precision, verbatim quotes
  without a source, or opinions dressed as measurements. Rewrite
  the sentence to remove the false claim while preserving the
  teaching intent. Supply `suggested_rewrite`; `proposed_url`,
  `proposed_tier`, `lesson_point_url` all null.
  Examples:
  - "AWS listed t2.large at $0.0928/hr on April 15 2026" →
    rewrite: "a small AWS VM typically costs a few cents per
    hour, depending on region and instance type."
  - "OrbStack is the fastest, lightest, best-UX option" →
    rewrite: "OrbStack is a popular option known for speed and
    polished UX."

Decision rules (strict):
- Dated historical price with an exact amount (e.g. "$0.0928/hr on
  April 15 2026") → `cannot_be_salvaged` ALWAYS. Vendor pricing
  pages change; a URL for the instance family does NOT back the
  historical snapshot. Rewrite to "a few cents per hour, depending
  on region and instance type" or similar.
- Illustrative dollar amount in teaching prose ("a team might pay
  $400/month for a 32GB server") → `soften_to_illustration`.
- Specific percentage at a specific date (e.g. "60.8% in March
  2026") → `supported` ONLY if the live dashboard shows roughly
  that figure; else `soften_to_illustration` ("most common",
  "roughly X%").
- Real outage / incident with primary source off-allowlist →
  `needs_allowlist_expansion`.
- Superlative without benchmark ("fastest", "best UX") →
  `cannot_be_salvaged`.
- Exact quote / verbatim claim without interview source →
  `cannot_be_salvaged`.
- Back-of-envelope calculations presented as facts (e.g. "AGC had
  74 KB") → `soften_to_illustration` with the primary source as
  lesson_point, and a rewrite that rounds or qualifies the number.

Bias toward honesty. A truthful disposition is better than a
forced weak anchor.

## CRITICAL: `anchor_text` for rewrite dispositions

For EVERY `soften_to_illustration` or `cannot_be_salvaged` claim,
you MUST supply an `anchor_text` field. The orchestrator uses it
to do a deterministic substring swap: it finds `anchor_text` in
the module body and replaces it with your `suggested_rewrite`.

Rules (strict):
1. `anchor_text` MUST be a VERBATIM substring of the module body.
   Copy-paste from the module; do NOT paraphrase, do NOT drop
   backticks, do NOT change case, do NOT fix typos. If the body
   says "a Linux `t2.large` instance", the anchor must include
   the backticks. If the body says "30 tabs", not "Thirty tabs".
2. `anchor_text` MUST be on a single line. No newline characters.
3. `anchor_text` SHOULD be the smallest substring that captures
   the full claim — usually one sentence or one clause. Do NOT
   include trailing period+space+next-sentence.
4. `anchor_text` SHOULD appear in the body EXACTLY ONCE. If the
   same phrasing appears twice, make the anchor longer to
   disambiguate.
5. `suggested_rewrite` replaces `anchor_text` verbatim. After the
   swap, surrounding punctuation (commas, periods, spaces) will
   still be there, so write `suggested_rewrite` as a clean phrase
   that slots cleanly into the same position. If `anchor_text`
   ends with a period, `suggested_rewrite` should end with one too.
6. `claim_text` can still be a tight paraphrase (for humans to
   read the seed). `anchor_text` is the machine-readable anchor.

If you CANNOT locate a verbatim anchor (e.g., the claim is
distributed across multiple lines), change the disposition: use
`needs_allowlist_expansion` or drop the claim with a note in
`rationale`. Never emit a rewrite-disposition claim without an
anchor — the pipeline will fail the seed.

## Trusted-domain allowlist

URLs you propose MUST resolve to hosts on this allowlist (tiered by claim
class). Pick the tier that best matches the claim. Do NOT invent URL paths
you are unsure about — prefer a well-known top-level doc page over a
hallucinated deep link.

{allowlist_block}

{section_pool_block}

## Output schema

Emit ONE JSON object, no preamble, no markdown fences, no trailing commas.
Schema:

{schema_block}

Claim class enum: {claim_classes}
Tier enum: {tiers}

## Module to research

Module key: `{module_key}`
Module path: `{module_path}`

```markdown
{module_body}
```

Return ONLY the JSON object. Do not include any other text.
"""


def _format_allowlist_block(allowlist: dict[str, Any]) -> str:
    lines: list[str] = []
    for tier in ("standards", "upstream", "vendor", "incidents", "general"):
        domains = allowlist.get("tiers", {}).get(tier) or []
        if not domains:
            continue
        lines.append(f"- **{tier}**: {', '.join(str(d) for d in domains)}")
    return "\n".join(lines)


def _format_schema_block() -> str:
    return json.dumps(
        {
            "module_key": "<string>",
            "module_path": "<string>",
            "research_run_id": "<ISO-8601-UTC>-<agent>-<model>",
            "schema_version": SCHEMA_VERSION,
            "section_pool_ref": "docs/citation-pools/<flat-section>.json | null",
            "claims": [
                {
                    "claim_id": "C001",
                    "claim_text": "<verbatim-or-tight-paraphrase>",
                    "claim_class": "<one-of-enum>",
                    "span_hint": "<line N | section: X | paragraph after diagram 2>",
                    "disposition": "<one of 5 dispositions — see rules above>",
                    "source_ids": ["S001", "S004"],
                    "proposed_url": "https://... (ONLY for newly-discovered URLs not already covered by the shared pool; otherwise null)",
                    "proposed_tier": "<tier, or null if off-allowlist or rewrite disposition>",
                    "anchor_text": "<REQUIRED for soften_to_illustration and cannot_be_salvaged — a VERBATIM single-line substring of the module body that the orchestrator will substring-swap for suggested_rewrite. MUST appear exactly in the module body (no paraphrasing, keep backticks, asterisks, case). MUST NOT contain a newline. SHOULD appear in exactly one line. null otherwise.>",
                    "suggested_rewrite": "<rewritten sentence for soften/salvage; null otherwise>",
                    "lesson_point_url": "<allowlisted URL for lesson principle, soften only; null otherwise>",
                    "rationale": "<one sentence>",
                }
            ],
            "further_reading": [
                {
                    "url": "https://...",
                    "title": "<short title>",
                    "tier": "<one-of-enum>",
                    "why_relevant": "<one sentence>",
                }
            ],
            "notes": "<optional free text>",
        },
        indent=2,
    )


def _format_section_pool_block(
    section_pool_ref: str | None,
    section_pool: list[dict[str, Any]] | None,
) -> str:
    if not section_pool_ref or not section_pool:
        return ""
    lines = []
    for source in section_pool:
        source_id = str(source.get("source_id") or "?")
        url = str(source.get("url") or "").strip()
        title = str(source.get("title") or url or "Untitled source").strip()
        tier = str(source.get("tier") or "unknown").strip()
        scope_notes = str(source.get("scope_notes") or "").strip()
        line = f"- `{source_id}` — {title} ({tier})\n  URL: {url}"
        if scope_notes:
            line += f"\n  Scope: {scope_notes}"
        lines.append(line)
    return SECTION_POOL_PREFERENCE_TEMPLATE.format(
        section_pool_ref=section_pool_ref,
        section_pool_sources="\n".join(lines),
    ).strip()


def build_research_prompt(
    module_key: str,
    module_path: Path,
    module_body: str,
    *,
    section_pool_ref: str | None = None,
    section_pool: list[dict[str, Any]] | None = None,
) -> str:
    from fetch_citation import _load_allowlist  # type: ignore[import-not-found]
    allowlist = _load_allowlist()
    level = audience_level(module_key)
    guidance = _AUDIENCE_GUIDANCE.get(level, _AUDIENCE_GUIDANCE["intermediate"])
    return RESEARCH_PROMPT_TEMPLATE.format(
        audience_guidance=guidance,
        allowlist_block=_format_allowlist_block(allowlist),
        section_pool_block=_format_section_pool_block(section_pool_ref, section_pool),
        schema_block=_format_schema_block(),
        claim_classes=", ".join(sorted(CLAIM_CLASSES)),
        tiers=", ".join(sorted(TIER_NAMES)),
        module_key=module_key,
        module_path=str(module_path.relative_to(REPO_ROOT)),
        module_body=module_body,
    )


# ---- module lookup -------------------------------------------------------


def resolve_module_path(module_key: str) -> Path:
    """Accepts 'prereqs/.../module-0.1-...' or a bare filename stem."""
    rel = module_key.strip().removesuffix(".md")
    candidate = DOCS_ROOT / f"{rel}.md"
    if candidate.exists():
        return candidate
    # Fallback: search by stem (useful when user types just the stem).
    matches = list(DOCS_ROOT.glob(f"**/{rel}.md"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"No module found for key: {module_key}")
    raise ValueError(
        f"Ambiguous module key {module_key}; matched {len(matches)} files"
    )


def seed_path_for(module_key: str) -> Path:
    flat = module_key.replace("/", "-")
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    return SEED_DIR / f"{flat}.json"


def section_key_for_path(module_path: Path) -> str:
    return module_path.parent.relative_to(DOCS_ROOT).as_posix()


def flat_section_name(section_key: str) -> str:
    return section_key.strip("/").replace("/", "-")


def section_pool_path_for(section_key: str) -> Path:
    CITATION_POOL_DIR.mkdir(parents=True, exist_ok=True)
    return CITATION_POOL_DIR / f"{flat_section_name(section_key)}.json"


def load_section_pool(
    section_pool_ref: str | None,
    *,
    strict: bool = False,
) -> dict[str, Any] | None:
    if not section_pool_ref:
        return None
    pool_path = REPO_ROOT / section_pool_ref
    if not pool_path.exists():
        if strict:
            raise FileNotFoundError(f"section pool not found: {section_pool_ref}")
        return None
    return json.loads(pool_path.read_text(encoding="utf-8"))


def _pool_source_index(section_pool: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for source in (section_pool or {}).get("sources") or []:
        source_id = str(source.get("source_id") or "").strip()
        if source_id:
            out[source_id] = source
    return out


def _pool_source_by_url(section_pool: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for source in (section_pool or {}).get("sources") or []:
        url = str(source.get("url") or "").strip()
        if url:
            out[url] = source
    return out


def resolve_claim_source_urls(
    claim: dict[str, Any],
    *,
    section_pool: dict[str, Any] | None = None,
) -> list[str]:
    pool_by_id = _pool_source_index(section_pool)
    urls: list[str] = []
    for source_id in claim.get("source_ids") or []:
        source = pool_by_id.get(str(source_id))
        url = str((source or {}).get("url") or "").strip()
        if url and url not in urls:
            urls.append(url)
    proposed_url = str(claim.get("proposed_url") or "").strip()
    if proposed_url and proposed_url not in urls:
        urls.append(proposed_url)
    return urls


def resolve_primary_claim_url(
    claim: dict[str, Any],
    *,
    section_pool: dict[str, Any] | None = None,
) -> str | None:
    urls = resolve_claim_source_urls(claim, section_pool=section_pool)
    return urls[0] if urls else None


def _normalize_claim_pool_refs(
    claim: dict[str, Any],
    *,
    section_pool: dict[str, Any] | None = None,
) -> None:
    source_ids = claim.get("source_ids")
    if not isinstance(source_ids, list):
        claim["source_ids"] = []
    pool_by_url = _pool_source_by_url(section_pool)
    proposed_url = str(claim.get("proposed_url") or "").strip()
    if claim["source_ids"] or not proposed_url:
        return
    source = pool_by_url.get(proposed_url)
    if source:
        claim["source_ids"] = [str(source.get("source_id"))]
        claim["proposed_url"] = None
        claim["proposed_tier"] = None


# ---- dispatch ------------------------------------------------------------


def dispatch_codex(prompt: str, *, task_id: str) -> tuple[bool, str]:
    """Send the prompt through scripts/ab ask-codex; return (ok, response_text)."""
    cmd = [
        "scripts/ab", "ask-codex",
        "--task-id", task_id,
        "--from", "claude",
        "--new-session",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout_after_900s"
    if proc.returncode != 0:
        return False, proc.stderr or proc.stdout
    return _extract_bridge_response(proc.stdout)


_BRIDGE_MSG_RE = re.compile(r"Message sent to Claude \(ID: (\d+)\)")


def _extract_bridge_response(stdout: str) -> tuple[bool, str]:
    match = _BRIDGE_MSG_RE.search(stdout)
    if not match:
        return False, f"no_response_message_id_in_bridge_stdout:\n{stdout[-400:]}"
    msg_id = match.group(1)
    read = subprocess.run(
        ["scripts/ab", "read", msg_id],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if read.returncode != 0:
        return False, read.stderr
    body = read.stdout
    # Strip the bridge envelope header — everything before the 60-char rule.
    parts = body.split("=" * 60, 1)
    return True, (parts[1] if len(parts) == 2 else body).strip()


#: Default Gemini timeout, correct for whole-module research/inject
#: prompts invoked from run_research / run_inject. Per-finding callers
#: (URL-candidate generation) should pass a shorter value explicitly —
#: one stuck short call should never block a whole pilot for 15 min.
GEMINI_DEFAULT_TIMEOUT = 900


def dispatch_agy(prompt: str, *, timeout: int = GEMINI_DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Writer path of the removed kube-dojo dispatcher."""
    del prompt, timeout
    raise RuntimeError("legacy dispatcher removed")


CLAUDE_DEFAULT_TIMEOUT = 600


class DispatcherUnavailable(RuntimeError):
    """The dispatcher refused a call. Distinct from a real empty result."""


_CLAUDE_UNAVAILABLE_MARKERS = (
    "peak hours in effect",
    "claude peak hours",
    "call budget",
    "claude budget",
    "claude unavailable",
    "claudeunavailableerror",
)


def _looks_unavailable(stderr: str) -> bool:
    s = (stderr or "").lower()
    return any(marker in s for marker in _CLAUDE_UNAVAILABLE_MARKERS)


def dispatch_claude(prompt: str, *, timeout: int = CLAUDE_DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Claude path of the removed kube-dojo dispatcher."""
    del prompt, timeout
    raise RuntimeError("legacy dispatcher removed")


# ---- validation ----------------------------------------------------------


def _stable_claim_id(claim_text: str) -> str:
    return "C" + hashlib.sha1(claim_text.encode("utf-8")).hexdigest()[:7]


def parse_agent_response(raw: str) -> dict[str, Any]:
    """Strip common wrappers (code fences, preamble) and json.loads."""
    text = raw.strip()
    # Remove ```json fences if present.
    if text.startswith("```"):
        # drop first line
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    # Find the first { and last } to be robust to stray prose.
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise ValueError("no_json_object_in_response")
    return json.loads(text[first:last + 1])


def _looks_like_error_seed(seed: dict[str, Any]) -> bool:
    """Return True when the parsed agent response is likely a bridge/error payload."""
    model = str(seed.get("from_model") or "").lower()
    if model.startswith("codex-bridge-error"):
        return True
    claims = seed.get("claims")
    has_claims_array = isinstance(claims, list) and len(claims) > 0
    if not has_claims_array and "schema_version" not in seed:
        return True
    return False


def validate_seed(seed: dict[str, Any]) -> list[str]:
    """Schema-only validation (no network). Returns list of issues."""
    issues: list[str] = []
    section_pool_ref = seed.get("section_pool_ref")
    section_pool: dict[str, Any] | None = None
    pool_by_id: dict[str, dict[str, Any]] = {}
    if section_pool_ref is not None and not isinstance(section_pool_ref, str):
        issues.append("bad_section_pool_ref")
    if section_pool_ref:
        try:
            section_pool = load_section_pool(str(section_pool_ref), strict=True)
        except FileNotFoundError:
            issues.append(f"missing_section_pool:{section_pool_ref}")
        except json.JSONDecodeError as exc:
            issues.append(f"invalid_section_pool_json:{exc}")
        else:
            pool_by_id = _pool_source_index(section_pool)
    for field in ("module_key", "module_path", "claims", "further_reading"):
        if field not in seed:
            issues.append(f"missing_field:{field}")
    for i, claim in enumerate(seed.get("claims") or []):
        if not isinstance(claim, dict):
            issues.append(f"claim[{i}]:not_dict")
            continue
        for f in ("claim_text", "claim_class", "disposition"):
            if f not in claim:
                issues.append(f"claim[{i}]:missing_{f}")
        disp = claim.get("disposition")
        if disp and disp not in DISPOSITIONS:
            issues.append(f"claim[{i}]:bad_disposition:{disp}")
        source_ids = claim.get("source_ids")
        if source_ids is None:
            source_ids = []
        if not isinstance(source_ids, list):
            issues.append(f"claim[{i}]:source_ids_not_list")
            source_ids = []
        bad_source_ids = [
            str(source_id) for source_id in source_ids
            if not isinstance(source_id, str)
        ]
        if bad_source_ids:
            issues.append(f"claim[{i}]:source_ids_not_strings")
        for source_id in source_ids:
            if pool_by_id and str(source_id) not in pool_by_id:
                issues.append(f"claim[{i}]:unknown_source_id:{source_id}")
            elif section_pool_ref and not pool_by_id:
                issues.append(f"claim[{i}]:section_pool_unavailable_for_source_id:{source_id}")
        # Per-disposition field requirements.
        if disp in CITED_DISPOSITIONS:
            has_pool_source = bool(source_ids)
            if not has_pool_source and not claim.get("proposed_url"):
                issues.append(f"claim[{i}]:missing_source_ref_for_{disp}")
            if claim.get("proposed_url") and not claim.get("proposed_tier"):
                issues.append(f"claim[{i}]:missing_proposed_tier_for_{disp}")
        elif disp == "needs_allowlist_expansion":
            # URL optional but if present MUST be off-allowlist (that's
            # the whole point — we're asking for expansion).
            url = claim.get("proposed_url")
            if url and allowlist_tier(url) is not None:
                issues.append(f"claim[{i}]:needs_allowlist_expansion_but_url_is_already_allowlisted")
        elif disp in REWRITE_DISPOSITIONS:
            if claim.get("proposed_url"):
                issues.append(f"claim[{i}]:{disp}_must_have_null_proposed_url")
            if not claim.get("suggested_rewrite"):
                issues.append(f"claim[{i}]:missing_suggested_rewrite_for_{disp}")
            anchor = claim.get("anchor_text")
            if not anchor:
                issues.append(f"claim[{i}]:missing_anchor_text_for_{disp}")
            elif "\n" in str(anchor):
                issues.append(f"claim[{i}]:anchor_text_contains_newline")
            if disp == "soften_to_illustration" and not claim.get("lesson_point_url"):
                issues.append(f"claim[{i}]:missing_lesson_point_url_for_soften")
        cc = claim.get("claim_class")
        if cc and cc not in CLAIM_CLASSES:
            issues.append(f"claim[{i}]:bad_class:{cc}")
        tier = claim.get("proposed_tier")
        if tier and tier not in TIER_NAMES:
            issues.append(f"claim[{i}]:bad_tier:{tier}")
        # HARD RULE: war stories, incidents, standards, security claims,
        # and statistics cannot be softened. They must cite or defer.
        if cc in HARD_CITE_CLASSES and disp == "soften_to_illustration":
            issues.append(
                f"claim[{i}]:hard_cite_class_cannot_soften:"
                f"{cc}/{disp} — must be supported, weak_anchor, or needs_allowlist_expansion"
            )
    for i, link in enumerate(seed.get("further_reading") or []):
        if not isinstance(link, dict):
            issues.append(f"further_reading[{i}]:not_dict")
            continue
        for f in ("url", "tier"):
            if f not in link:
                issues.append(f"further_reading[{i}]:missing_{f}")
    return issues


def validate_anchors_against_body(seed: dict[str, Any], body: str) -> list[str]:
    """For each rewrite-disposition claim, check that anchor_text is a
    verbatim substring of the module body (and ideally unique)."""
    issues: list[str] = []
    for i, claim in enumerate(seed.get("claims") or []):
        if not isinstance(claim, dict):
            continue
        if claim.get("disposition") not in REWRITE_DISPOSITIONS:
            continue
        anchor = claim.get("anchor_text")
        if not anchor:
            continue  # missing-anchor issue already surfaced by validate_seed
        anchor_s = str(anchor)
        if anchor_s not in body:
            issues.append(
                f"claim[{i}]:anchor_text_not_in_body:{claim.get('claim_id')}"
            )
            continue
        if body.count(anchor_s) > 1:
            issues.append(
                f"claim[{i}]:anchor_text_ambiguous_{body.count(anchor_s)}_matches:"
                f"{claim.get('claim_id')}"
            )
    return issues


def validate_urls(seed: dict[str, Any]) -> dict[str, Any]:
    """Network pass: fetch every URL, move rejects into rejected_urls."""
    section_pool = load_section_pool(seed.get("section_pool_ref"))
    rejected: list[dict[str, Any]] = list(seed.get("rejected_urls") or [])
    kept_claims: list[dict[str, Any]] = []
    for claim in seed.get("claims") or []:
        disp = claim.get("disposition")
        _normalize_claim_pool_refs(claim, section_pool=section_pool)

        # Rewrite-bucket claims: no URL fetch needed; they carry a
        # suggested_rewrite and possibly a lesson_point_url. The
        # lesson_point_url MUST be on-allowlist and reachable.
        if disp in REWRITE_DISPOSITIONS:
            claim["proposed_url"] = None
            claim["proposed_tier"] = None
            lp_url = (claim.get("lesson_point_url") or "").strip() or None
            if lp_url:
                lp_tier = allowlist_tier(lp_url)
                if lp_tier is None:
                    rejected.append({
                        "url": lp_url, "reason": "lesson_point_off_allowlist",
                        "at_step": "research_validation",
                        "claim_id": claim.get("claim_id"),
                    })
                    claim["lesson_point_url"] = None
                else:
                    result = fetch(lp_url)
                    status = int(result.get("status") or 0)
                    if not (status and status < 400):
                        rejected.append({
                            "url": lp_url,
                            "reason": f"lesson_point_http_{status}" if status else "lesson_point_network_failure",
                            "at_step": "research_validation",
                            "claim_id": claim.get("claim_id"),
                        })
                        claim["lesson_point_url"] = None
            kept_claims.append(claim)
            continue

        # Allowlist-expansion-request claims: URL is optional CONTEXT
        # (the off-list source we'd use if allowlist grew). Don't
        # fetch — we're deliberately pointing at unknown hosts.
        if disp == "needs_allowlist_expansion":
            claim["proposed_tier"] = None  # by definition
            kept_claims.append(claim)
            continue

        # Cited dispositions backed by pool source_ids rely on the
        # section_source_discovery validation pass. Only newly-discovered
        # proposed_url values need a fresh allowlist+HTTP check here.
        if claim.get("source_ids"):
            kept_claims.append(claim)
            continue

        # Cited dispositions: URL must be on-allowlist AND reachable.
        url = (claim.get("proposed_url") or "").strip()
        if not url:
            rejected.append({
                "url": "", "reason": "empty_url", "at_step": "research_validation",
                "agent_proposed_tier": claim.get("proposed_tier"),
            })
            continue
        tier = allowlist_tier(url)
        if tier is None:
            rejected.append({
                "url": url, "reason": "off_allowlist",
                "at_step": "research_validation",
                "agent_proposed_tier": claim.get("proposed_tier"),
            })
            continue
        result = fetch(url)
        status = int(result.get("status") or 0)
        issues = result.get("issues") or []
        if status and status < 400 and "pdf_needs_adapter" not in issues:
            claim["proposed_tier"] = tier
            kept_claims.append(claim)
        else:
            reason = "pdf_no_adapter" if "pdf_needs_adapter" in issues else \
                     "network_failure" if not status else f"http_{status}"
            rejected.append({
                "url": url, "reason": reason, "at_step": "research_validation",
                "agent_proposed_tier": claim.get("proposed_tier"),
            })

    kept_fr: list[dict[str, Any]] = []
    for link in seed.get("further_reading") or []:
        url = (link.get("url") or "").strip()
        if not url:
            continue
        tier = allowlist_tier(url)
        if tier is None:
            rejected.append({
                "url": url, "reason": "off_allowlist",
                "at_step": "research_validation", "agent_proposed_tier": link.get("tier"),
            })
            continue
        result = fetch(url)
        status = int(result.get("status") or 0)
        if status and status < 400:
            link["tier"] = tier
            kept_fr.append(link)
        else:
            rejected.append({
                "url": url, "reason": f"http_{status}" if status else "network_failure",
                "at_step": "research_validation", "agent_proposed_tier": link.get("tier"),
            })

    seed["claims"] = kept_claims
    seed["further_reading"] = kept_fr
    seed["rejected_urls"] = rejected
    return seed


# ---- research orchestration ---------------------------------------------


def _iso_utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")


def run_research(
    module_key: str,
    *,
    agent: str = "codex",
    dry_run: bool = False,
    section_pool_ref: str | None = None,
) -> dict[str, Any]:
    module_path = resolve_module_path(module_key)
    module_body = module_path.read_text(encoding="utf-8")
    normalized_key = module_path.relative_to(DOCS_ROOT).with_suffix("").as_posix()
    section_pool = load_section_pool(section_pool_ref, strict=False)
    prompt = build_research_prompt(
        normalized_key,
        module_path,
        module_body,
        section_pool_ref=section_pool_ref,
        section_pool=(section_pool or {}).get("sources"),
    )

    if dry_run:
        return {
            "module_key": normalized_key,
            "dry_run": True,
            "section_pool_ref": section_pool_ref,
            "prompt_bytes": len(prompt),
            "prompt_preview": prompt[:600],
            "prompt_tail": prompt[-400:],
        }

    task_id = f"citation-research-{normalized_key.replace('/', '-')}-{_dt.datetime.now(_dt.UTC).strftime('%Y%m%dT%H%M%SZ')}"
    if agent == "codex":
        ok, raw = dispatch_codex(prompt, task_id=task_id)
        model = "gpt-5.3-codex-spark"  # codex default; bridge may override
    elif agent == "agy":
        ok, raw = dispatch_agy(prompt)
        model = "gemini-3.1-pro-high"
    else:
        raise ValueError(f"unknown agent: {agent}")

    if not ok:
        return {
            "module_key": normalized_key, "ok": False,
            "error": "dispatch_failed", "detail": raw[-600:],
        }

    try:
        seed = parse_agent_response(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "module_key": normalized_key, "ok": False,
            "error": "parse_failed", "detail": str(exc),
            "raw_head": raw[:400], "raw_tail": raw[-400:],
        }
    if _looks_like_error_seed(seed):
        return {
            "module_key": normalized_key,
            "ok": False,
            "error": "agent_response_invalid",
            "detail": "agent response missing claims/schema_version or bridge error payload",
            "raw_head": raw[:400],
            "raw_tail": raw[-400:],
        }

    seed.setdefault("module_key", normalized_key)
    seed.setdefault("module_path", str(module_path.relative_to(REPO_ROOT)))
    seed.setdefault("section_pool_ref", section_pool_ref)
    seed["schema_version"] = SCHEMA_VERSION
    seed["research_run_id"] = f"{_iso_utc_now()}-{agent}-{model}"
    # Stabilize claim IDs.
    for claim in seed.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        claim.setdefault("source_ids", [])
        _normalize_claim_pool_refs(claim, section_pool=section_pool)
        if claim.get("claim_text") and not claim.get("claim_id"):
            claim["claim_id"] = _stable_claim_id(str(claim["claim_text"]))

    schema_issues = validate_seed(seed)
    schema_issues.extend(validate_anchors_against_body(seed, module_body))
    seed["_schema_issues"] = schema_issues
    seed = validate_urls(seed)

    out_path = seed_path_for(normalized_key)
    out_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "module_key": normalized_key, "ok": True,
        "seed_path": str(out_path.relative_to(REPO_ROOT)),
        "claims_kept": len(seed.get("claims") or []),
        "further_reading_kept": len(seed.get("further_reading") or []),
        "rejected": len(seed.get("rejected_urls") or []),
        "schema_issues": schema_issues,
    }


# ---- inject step ---------------------------------------------------------


INJECT_PROMPT_TEMPLATE = """You are the inject step of the KubeDojo citation
backfill pipeline. Given the module body and the already-validated citation
seed (with dispositions), produce a STRUCTURED EDIT PLAN the orchestrator
will apply mechanically. You do NOT rewrite the module freely — every edit
is an inline citation wrap of an existing phrase, tied to a specific claim_id.
The orchestrator builds the final `## Sources` section deterministically.

## Division of responsibility

Two kinds of edits land in the module:

1. **Inline citation wraps** (YOUR JOB) — for every `supported` and
   `weak_anchor` claim, emit one `inline_insertion` that wraps an
   existing phrase in `[phrase](url)` using the seed's `citation_url`.
2. **Prose rewrites** (ORCHESTRATOR'S JOB, not yours) — for every
   `soften_to_illustration` or `cannot_be_salvaged` claim, the
   orchestrator will substring-swap the seed's `anchor_text` for the
   seed's `suggested_rewrite` automatically. You must NOT emit
   `prose_rewrites` entries. They are handled deterministically from
   the seed; your participation would only introduce error.
3. **Sources section** (ORCHESTRATOR'S JOB, not yours) — the
   orchestrator resolves pool `source_id`s, deduplicates URLs, and
   appends the final `## Sources` block. Leave `sources_section` empty.

## MANDATORY per-disposition actions

- `supported` | `weak_anchor` → REQUIRED: one `inline_insertion` (pure
  wrap of an existing phrase in `[phrase](url)`). The URL is the
  claim's `citation_url` in the seed. If a supported-claim's span_hint
  points at a mermaid/code block/table row that cannot carry a markdown
  link, record the skip in `skipped_claims` with reason
  `span_not_wrappable`.

- `soften_to_illustration` | `cannot_be_salvaged` → DO NOT EMIT a
  `prose_rewrite`. The orchestrator handles these via the seed's
  `anchor_text` + `suggested_rewrite`.

- `needs_allowlist_expansion` → DO NOTHING. Add the claim_id to
  `skipped_claims` with reason `awaiting_allowlist_review`. Do not
  edit the module; do not add a citation.

## Completeness contract (CRITICAL)

Every cited-disposition claim (supported, weak_anchor) from the seed
MUST appear in EXACTLY ONE of:

- `inline_insertions[]` with a valid wrap, OR
- `skipped_claims[]` with a reason like `span_in_code_block`,
  `span_not_wrappable`, `inside_quoted_block`, or `claim_text_not_found_in_body`.

Omitting a cited claim from BOTH arrays is a CONTRACT VIOLATION. The
orchestrator will detect this and soft-skip the missing claim — your
hard work on the other claims still lands, but the dropped claim
becomes a manual-review item in the sidecar log. Aim for zero
contract violations.

## Edit discipline

1. `target_line` MUST be a verbatim single line copied from the module
   body — the WHOLE line, untrimmed, exactly as it appears. Line
   boundaries are \\n. Copy once, don't edit.
2. For `inline_insertion`: `original_phrase` must appear verbatim in
   `target_line`; `replace_with` must equal `[original_phrase](url)`.
3. Never modify frontmatter, Mermaid blocks, code blocks, quiz answers,
   or exercise steps. If a claim's span_hint points into one of those,
   skip it (add to `skipped_claims` with a reason).
3a. **Never edit content INSIDE blockquote-quoted strings.** Lines
   like `> "...quoted text..."` are verbatim examples — typically
   what an AI reviewer / agent / user said. They are content the
   author chose to quote literally. Any rewrite there will fail
   the diff lint as `unauthorized_prose_change`. If a claim's
   span_hint points into a `> "..."` block, skip it with reason
   `inside_quoted_block`. (Plain blockquotes WITHOUT enclosing
   double-quotes — e.g. `> **Pause and predict**: ...` — are
   editable; the rule is specifically about quoted-string content.)
4. `sources_section` MUST be the empty string. The orchestrator owns it.

## Output schema

Emit ONE JSON object. No preamble, no markdown fences.

{schema_block}

## Module to edit

Module key: `{module_key}`

```markdown
{module_body}
```

## Seed (already-validated)

```json
{seed_json}
```

Return ONLY the JSON object.
"""


INJECT_SCHEMA_EXAMPLE = json.dumps(
    {
        "module_key": "<string>",
        "inline_insertions": [
            {
                "claim_id": "C001",
                "target_line": "<verbatim single line from module body>",
                "original_phrase": "<substring of target_line to be wrapped>",
                "replace_with": "[<original_phrase>](<url>)",
            }
        ],
        "sources_section": "",
        "skipped_claims": [
            {"claim_id": "C003", "reason": "awaiting_allowlist_review | span_in_code_block | ..."}
        ],
    },
    indent=2,
)


def build_inject_prompt(module_key: str, module_body: str, seed: dict[str, Any]) -> str:
    section_pool = load_section_pool(seed.get("section_pool_ref"))
    # Trim seed to the fields the inject step cares about (keep bytes down).
    # Rewrite-disposition claims still included so Codex understands the
    # module has them (for sources_section lesson_point_urls), but Codex
    # is instructed NOT to emit prose_rewrites for them.
    compact_seed = {
        "module_key": seed.get("module_key"),
        "claims": [
            {
                "claim_id": c.get("claim_id"),
                "claim_text": c.get("claim_text"),
                "span_hint": c.get("span_hint"),
                "disposition": c.get("disposition"),
                "source_ids": c.get("source_ids") or [],
                "citation_url": resolve_primary_claim_url(c, section_pool=section_pool),
                "lesson_point_url": c.get("lesson_point_url"),
            }
            for c in (seed.get("claims") or [])
        ],
        "further_reading": seed.get("further_reading") or [],
    }
    return INJECT_PROMPT_TEMPLATE.format(
        schema_block=INJECT_SCHEMA_EXAMPLE,
        module_key=module_key,
        module_body=module_body,
        seed_json=json.dumps(compact_seed, indent=2, ensure_ascii=False),
    )


def _safe_markdown_url(url: str) -> str:
    """Percent-encode parens in URLs so Wikipedia-style disambiguator
    paths (`Shebang_(Unix)`) don't break the `[phrase](url)` markdown
    link syntax. CommonMark would otherwise close the link at the
    first `)` inside the URL, leaving a stray `)` in the document."""
    return url.replace("(", "%28").replace(")", "%29")


def _validate_inline_insertion(ins: dict[str, Any]) -> str | None:
    """Shape-only validation: required fields, phrase-in-target,
    wrap format, URL allowlist. Existence of target_line in
    current new_body is checked by the apply loop so it can retry
    with the phrase-uniqueness fallback."""
    for f in ("target_line", "original_phrase", "replace_with"):
        if not ins.get(f):
            return f"missing_{f}"
    target = ins["target_line"]
    phrase = ins["original_phrase"]
    replace = ins["replace_with"]
    # phrase must appear in target_line.
    if phrase not in target:
        return "phrase_not_in_target_line"
    # replace_with must wrap original_phrase in a link: [phrase](url)
    expected_prefix = f"[{phrase}]("
    if not (replace.startswith(expected_prefix) and replace.endswith(")")):
        return "replace_with_not_pure_wrap"
    url = replace[len(expected_prefix):-1]
    if not url.startswith(("http://", "https://")):
        return "replace_with_url_not_http"
    if allowlist_tier(url) is None:
        return "replace_with_url_off_allowlist"
    return None


_QUOTED_BLOCKQUOTE_RE = re.compile(r'^>\s*[“"”]')


def _anchor_inside_quoted_blockquote(anchor: str, body: str) -> bool:
    """Return True iff every occurrence of `anchor` in `body` lives on a
    line that begins with a `> "..."` blockquote-quoted string. Such
    content is verbatim author-quoted material (AI reviewer output, user
    statements, model excerpts) and must not be rewritten by the
    orchestrator — the diff lint won't authorize the change and the
    edit corrupts the author's intent."""
    if not anchor:
        return False
    matched_any = False
    for line in body.splitlines():
        if anchor in line:
            matched_any = True
            if not _QUOTED_BLOCKQUOTE_RE.match(line.lstrip()):
                return False
    return matched_any


def _authorized_rewrites(seed: dict[str, Any], body: str | None = None
                         ) -> dict[str, dict[str, str]]:
    """Map claim_id → {anchor_text, suggested_rewrite} for each rewrite-
    disposition claim in the seed. Schema v2: anchor_text is a verbatim
    substring of the module body. The orchestrator substring-swaps
    anchor_text for suggested_rewrite deterministically; Codex does not
    participate in rewrites.

    When `body` is supplied, claims whose anchor lives inside a
    `> "..."` blockquote-quoted line are excluded — those lines are
    verbatim author-quoted content (AI reviewer output, etc.) and must
    not be rewritten.
    """
    out: dict[str, dict[str, str]] = {}
    for c in seed.get("claims") or []:
        if c.get("disposition") not in REWRITE_DISPOSITIONS:
            continue
        anchor = c.get("anchor_text")
        suggested = c.get("suggested_rewrite")
        if not anchor or not suggested:
            continue
        if body is not None and _anchor_inside_quoted_blockquote(str(anchor), body):
            continue
        out[str(c.get("claim_id") or "")] = {
            "anchor_text": str(anchor),
            "suggested_rewrite": str(suggested),
        }
    return out


def _authorized_replacement_lines(seed: dict[str, Any], body: str) -> set[str]:
    """Precompute the SET of replacement lines that will exist after
    orchestrator rewrites are applied. One per rewrite-disposition claim
    whose anchor_text is found in the body. Used by the diff linter to
    recognize authorized line changes.

    The diff linter compares inline-link-unwrapped strings, so lines
    with pre-existing links must be added in both wrapped and unwrapped
    forms for the match to succeed when a rewrite lands on a line that
    already carries a citation.
    """
    out: set[str] = set()
    for info in _authorized_rewrites(seed, body).values():
        anchor = info["anchor_text"]
        suggested = info["suggested_rewrite"]
        for line in body.splitlines():
            if anchor in line:
                new_line = line.replace(anchor, suggested, 1)
                out.add(new_line.strip())
                out.add(_INLINE_LINK_RE.sub(r"\1", new_line).strip())
    return out


def apply_inject_plan(body: str, plan: dict[str, Any], seed: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Apply Codex-emitted inline insertions and merge sources.
    Returns (new_body, applied).
    """
    new_body = body
    applied: list[dict[str, Any]] = []

    # Inline insertions are the only prose mutation allowed in this
    # phase; rewrite-disposition claims are recorded below for later
    # human review.
    for ins in plan.get("inline_insertions") or []:
        reason = _validate_inline_insertion(ins)
        if reason:
            applied.append({"claim_id": ins.get("claim_id"), "kind": "inline",
                            "status": "rejected", "reason": reason})
            continue
        target = ins["target_line"]
        phrase = ins["original_phrase"]
        replace = ins["replace_with"]
        # Percent-encode parens in the URL so Wikipedia-style disambiguator
        # paths don't break the markdown link. Validation already confirmed
        # the wrap shape; now we canonicalize the URL before insertion.
        expected_prefix = f"[{phrase}]("
        url_raw = replace[len(expected_prefix):-1]
        replace = f"{expected_prefix}{_safe_markdown_url(url_raw)})"
        idx = new_body.find(target)
        note: str | None = None
        if idx < 0:
            # Fallback: an earlier inline wrap on the same line may have
            # mutated target_line. If `phrase` still appears uniquely in
            # new_body, wrap it there directly.
            occurrences = []
            start = 0
            while True:
                k = new_body.find(phrase, start)
                if k < 0:
                    break
                occurrences.append(k)
                start = k + 1
            if len(occurrences) != 1:
                applied.append({"claim_id": ins.get("claim_id"), "kind": "inline",
                                "status": "rejected",
                                "reason": f"target_disappeared_phrase_has_{len(occurrences)}_matches"})
                continue
            abs_phrase_idx = occurrences[0]
            note = "fallback_phrase_match"
        else:
            phrase_idx_in_target = target.find(phrase)
            abs_phrase_idx = idx + phrase_idx_in_target
        if _is_inside_existing_markdown_link(new_body, abs_phrase_idx):
            applied.append({"claim_id": ins.get("claim_id"), "kind": "inline",
                            "status": "applied",
                            "note": "already_cited_in_body"})
            continue
        new_body = new_body[:abs_phrase_idx] + replace + new_body[abs_phrase_idx + len(phrase):]
        applied.append({"claim_id": ins.get("claim_id"), "kind": "inline",
                        "status": "applied",
                        **({"note": note} if note else {})})

    for c in seed.get("claims") or []:
        if c.get("disposition") not in REWRITE_DISPOSITIONS:
            continue
        claim_id = str(c.get("claim_id") or "")
        applied.append({"claim_id": claim_id, "kind": "prose_rewrite",
                        "status": "skipped",
                        "reason": "rewrites_disabled_pending_redesign"})

    sources = _build_sources_section_from_seed(seed).strip()
    if sources:
        sources = _sanitize_sources_section_urls(sources)
        new_body = _merge_sources_section(new_body, sources)
    return new_body, applied


def _is_inside_existing_markdown_link(body: str, idx: int) -> bool:
    """Return True when ``idx`` falls inside a markdown link in ``body``."""
    if idx < 0:
        return False

    i = 0
    n = len(body)
    while i < n:
        lb = body.find("](", i)
        if lb < 0:
            return False
        lbr = body.rfind("[", i, lb)
        if lbr < 0:
            i = lb + 2
            continue
        # Parse URL: balance-aware until the matching ")" at depth 0.
        url_start = lb + 2
        depth = 0
        j = url_start
        while j < n:
            ch = body[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch.isspace():
                break
            j += 1
        if j >= n or body[j] != ")":
            i = lb + 2
            continue
        if lbr <= idx <= j:
            return True
        i = j + 1
    return False


def _sanitize_sources_section_urls(text: str) -> str:
    """Percent-encode parens inside markdown links so Wikipedia-style
    URLs (e.g. `/wiki/Ed_(text_editor)`) don't produce broken markdown.
    Walks the text once, balancing parens at each `](` to find the
    URL's true end, then encodes."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        lb = text.find("](", i)
        if lb < 0:
            out.append(text[i:])
            break
        # Must be preceded by `[label]` — find the matching `[`.
        lbr = text.rfind("[", i, lb)
        if lbr < 0:
            out.append(text[i:lb + 2])
            i = lb + 2
            continue
        # Parse URL: balance-aware until we hit a `)` with depth 0.
        url_start = lb + 2
        depth = 0
        j = url_start
        while j < n:
            ch = text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch.isspace():
                break
            j += 1
        if j >= n or text[j] != ")":
            out.append(text[i:lb + 2])
            i = lb + 2
            continue
        url = text[url_start:j]
        label = text[lbr + 1:lb]
        out.append(text[i:lbr])
        out.append(f"[{label}]({_safe_markdown_url(url)})")
        i = j + 1
    return "".join(out)


_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)")


def _extract_markdown_link_urls(text: str) -> list[str]:
    """Return markdown link URLs, including URLs with balanced parens."""
    urls: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        lb = text.find("](", i)
        if lb < 0:
            break
        lbr = text.rfind("[", i, lb)
        if lbr < 0:
            i = lb + 2
            continue
        url_start = lb + 2
        depth = 0
        j = url_start
        while j < n:
            ch = text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch.isspace():
                break
            j += 1
        if j < n and text[j] == ")":
            urls.append(text[url_start:j])
            i = j + 1
        else:
            i = lb + 2
    return urls


_SOURCES_HEADING_RE = re.compile(r"(?m)^## Sources[ \t]*$")
_NEXT_H2_RE = re.compile(r"(?m)^## ")


def _merge_sources_section(existing_body: str, seed_sources_block: str) -> str:
    """Merge seed-derived source bullets into an existing Sources section.

    Existing source bullets and any content after Sources are preserved.
    New bullets are appended only when their markdown-link URL is absent.
    """
    seed_entries: list[tuple[str, str]] = []
    for line in seed_sources_block.splitlines():
        bullet = line.strip()
        if not bullet.startswith("- "):
            continue
        urls = _extract_markdown_link_urls(bullet)
        if urls:
            seed_entries.append((urls[0], bullet))
    if not seed_entries:
        return existing_body

    heading = _SOURCES_HEADING_RE.search(existing_body)
    if not heading:
        body = existing_body.rstrip()
        if not body.endswith("\n"):
            body += "\n"
        return body + "\n" + seed_sources_block.rstrip() + "\n"

    section_start = heading.end()
    next_h2 = _NEXT_H2_RE.search(existing_body, section_start)
    section_end = next_h2.start() if next_h2 else len(existing_body)
    existing_section = existing_body[heading.start():section_end]
    seen_urls = set(_extract_markdown_link_urls(existing_section))
    additions: list[str] = []
    for url, bullet in seed_entries:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        additions.append(bullet)
    if not additions:
        return existing_body

    insert_at = section_end
    while insert_at > heading.start() and existing_body[insert_at - 1].isspace():
        insert_at -= 1
    insertion_prefix = "\n\n" if insert_at == heading.end() else "\n"
    return (
        existing_body[:insert_at]
        + insertion_prefix
        + "\n".join(additions)
        + existing_body[insert_at:]
    )


def _strip_sources_section(body: str) -> str:
    """Drop a trailing `## Sources` block, if present."""
    if "## Sources" not in body:
        return body
    pre, _, _ = body.rpartition("## Sources")
    return pre.rstrip()


def _derive_title_from_url(url: str) -> str:
    """Derive a readable title from a URL when no human-written one is available.

    Turning `https://argo-cd.readthedocs.io/en/release-3.1/` into
    `argo-cd.readthedocs.io: release 3.1` beats the default (URL repeated
    as both link text and href) for rendered module Sources sections.
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return url
    host = (parsed.hostname or "").removeprefix("www.")
    path_segments = [seg for seg in parsed.path.split("/") if seg]
    tail = path_segments[-1] if path_segments else ""
    readable_tail = tail.replace("-", " ").replace("_", " ").strip()
    if host and readable_tail:
        return f"{host}: {readable_tail}"
    return host or url


def _build_sources_section_from_seed(seed: dict[str, Any]) -> str:
    section_pool = load_section_pool(seed.get("section_pool_ref"))
    pool_by_id = _pool_source_index(section_pool)
    pool_by_url = _pool_source_by_url(section_pool)
    entries: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()

    def add_entry(url: str | None, title: str | None, note: str | None) -> None:
        normalized_url = str(url or "").strip()
        if not normalized_url or normalized_url in seen_urls:
            return
        seen_urls.add(normalized_url)
        title_clean = str(title or "").strip()
        resolved_title = title_clean or _derive_title_from_url(normalized_url)
        resolved_note = str(note or "").strip()
        entries.append((resolved_title, normalized_url, resolved_note))

    for claim in seed.get("claims") or []:
        disposition = claim.get("disposition")
        source_ids = [str(source_id) for source_id in claim.get("source_ids") or []]
        # Pool sources are pre-validated but still disposition-scoped:
        # source_ids on a needs_allowlist_expansion / cannot_be_salvaged
        # claim indicate schema drift (model hallucination) and must
        # not reach a rendered Sources block.
        if disposition in CITED_DISPOSITIONS:
            for source_id in source_ids:
                source = pool_by_id.get(source_id) or {}
                add_entry(
                    str(source.get("url") or "").strip() or None,
                    str(source.get("title") or "").strip() or None,
                    str(source.get("scope_notes") or "").strip()
                    or str(claim.get("rationale") or "").strip()
                    or str(claim.get("claim_text") or "").strip(),
                )
            # Pool-less proposed_url fallback (still CITED-gated).
            if not source_ids:
                add_entry(
                    claim.get("proposed_url"),
                    None,
                    str(claim.get("rationale") or "").strip()
                    or str(claim.get("claim_text") or "").strip(),
                )
        # lesson_point_url is semantically the illustrative-rewrite source
        # for soften_to_illustration ONLY. On any other disposition it is
        # schema drift; refuse to surface it.
        if disposition == "soften_to_illustration":
            lesson_point_url = str(claim.get("lesson_point_url") or "").strip()
            if lesson_point_url:
                pool_source = pool_by_url.get(lesson_point_url) or {}
                add_entry(
                    lesson_point_url,
                    str(pool_source.get("title") or "").strip() or None,
                    "General lesson point for an illustrative rewrite.",
                )

    for link in seed.get("further_reading") or []:
        add_entry(
            link.get("url"),
            link.get("title"),
            link.get("why_relevant"),
        )

    if not entries:
        return ""
    lines = ["## Sources", ""]
    for title, url, note in entries:
        if note:
            lines.append(f"- [{title}]({url}) — {note}")
        else:
            lines.append(f"- [{title}]({url})")
    return "\n".join(lines)


def _verify_diff_is_additive(original: str, modified: str,
                             authorized_rewrites: dict[str, str] | None = None) -> list[str]:
    """Sanity-check that `modified` differs from `original` only by
    (a) new inline [phrase](url) wraps, (b) authorized prose rewrites
    (each full-line replacement must match a seed-authorized target),
    and (c) an appended Sources section.

    Strategy: unwrap inline links on both sides, strip the new Sources
    block, then diff line-by-line. Any changed line must appear as a
    value in `authorized_rewrites` (the seed's suggested_rewrite set).
    """
    issues: list[str] = []
    authorized_values = set((authorized_rewrites or {}).values())
    modified_pre = _strip_sources_section(modified)
    original_pre = _strip_sources_section(original)
    orig_unwrapped = _INLINE_LINK_RE.sub(r"\1", original_pre).rstrip()
    mod_unwrapped = _INLINE_LINK_RE.sub(r"\1", modified_pre).rstrip()
    if mod_unwrapped == orig_unwrapped:
        return issues

    # Not identical; find which lines changed and check each against the
    # authorized-rewrite set.
    import difflib
    orig_lines = orig_unwrapped.splitlines()
    mod_lines = mod_unwrapped.splitlines()
    matcher = difflib.SequenceMatcher(a=orig_lines, b=mod_lines, autojunk=False)
    unauthorized: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # replace / insert / delete hunks
        removed = orig_lines[i1:i2]
        added = mod_lines[j1:j2]
        # 1-to-1 substitutions are the only allowed form (paired rewrite).
        if len(removed) == len(added):
            for old_line, new_line in zip(removed, added, strict=False):
                if new_line.strip() not in authorized_values:
                    unauthorized.append((old_line, new_line))
        else:
            # Asymmetric change — never allowed outside of Sources.
            unauthorized.append(("\n".join(removed)[:200], "\n".join(added)[:200]))
    if unauthorized:
        sample_lines: list[str] = []
        for old_line, new_line in unauthorized[:5]:
            sample_lines.append(f"-{old_line[:800]}")
            sample_lines.append(f"+{new_line[:800]}")
        issues.append("unauthorized_prose_change:\n" + "\n".join(sample_lines))
    return issues


def run_inject(module_key: str, *, agent: str = "codex", dry_run: bool = False) -> dict[str, Any]:
    module_path = resolve_module_path(module_key)
    normalized_key = module_path.relative_to(DOCS_ROOT).with_suffix("").as_posix()
    seed_path = seed_path_for(normalized_key)
    if not seed_path.exists():
        return {"module_key": normalized_key, "ok": False,
                "error": "no_seed_file", "detail": f"run research first: {seed_path}"}
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    claims = seed.get("claims") or []
    cited = [c for c in claims if c.get("disposition") in CITED_DISPOSITIONS]
    rewrites = [c for c in claims if c.get("disposition") in REWRITE_DISPOSITIONS]
    deferred = [c for c in claims if c.get("disposition") in DEFERRED_DISPOSITIONS]
    has_fr = bool(seed.get("further_reading") or [])
    if not cited and not rewrites and not has_fr:
        return {"module_key": normalized_key, "ok": False,
                "error": "nothing_to_do",
                "detail": "seed has no cited, rewrite, or further_reading actions"}

    module_body = module_path.read_text(encoding="utf-8")

    # Pre-dispatch: validate anchors exist in body. Fail fast before
    # burning a Codex call on a broken seed.
    anchor_issues = validate_anchors_against_body(seed, module_body)
    if anchor_issues:
        return {"module_key": normalized_key, "ok": False,
                "error": "seed_anchor_validation_failed",
                "detail": anchor_issues,
                "fix": "re-run research to regenerate anchor_text "
                       "(schema v2 required for rewrite claims)"}

    prompt = build_inject_prompt(normalized_key, module_body, seed)

    if dry_run:
        return {"module_key": normalized_key, "dry_run": True,
                "cited_count": len(cited),
                "rewrite_count": len(rewrites),
                "deferred_count": len(deferred),
                "further_reading_count": len(seed.get("further_reading") or []),
                "prompt_bytes": len(prompt)}

    task_id = f"citation-inject-{normalized_key.replace('/', '-')}-{_dt.datetime.now(_dt.UTC).strftime('%Y%m%dT%H%M%SZ')}"
    if agent == "codex":
        ok, raw = dispatch_codex(prompt, task_id=task_id)
    elif agent == "agy":
        ok, raw = dispatch_agy(prompt)
    else:
        raise ValueError(f"unknown agent: {agent}")
    if not ok:
        return {"module_key": normalized_key, "ok": False,
                "error": "dispatch_failed", "detail": raw[-500:]}
    try:
        plan = parse_agent_response(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"module_key": normalized_key, "ok": False,
                "error": "parse_failed", "detail": str(exc),
                "raw_head": raw[:400], "raw_tail": raw[-400:]}

    new_body, applied = apply_inject_plan(module_body, plan, seed)
    diff_issues = _verify_diff_is_additive(
        module_body, new_body,
        authorized_rewrites={k: v for k, v in (
            (line_key, line_key) for line_key in _authorized_replacement_lines(seed, module_body)
        )},
    )
    # Coverage gate — every rewrite-disposition claim must appear in
    # either the applied rewrites set OR the skipped_claims list.
    expected_rewrite_ids = {
        str(c.get("claim_id")) for c in (seed.get("claims") or [])
        if c.get("disposition") in REWRITE_DISPOSITIONS
    }
    applied_rewrite_ids = {
        str(a.get("claim_id")) for a in applied
        if a.get("kind") == "prose_rewrite"
        and a.get("status") in ("applied", "skipped")
    }
    skipped_ids = {str(s.get("claim_id")) for s in (plan.get("skipped_claims") or [])}
    missing = expected_rewrite_ids - applied_rewrite_ids - skipped_ids
    if missing:
        diff_issues.append(
            f"rewrite_dispositions_not_addressed: {sorted(missing)[:5]}"
        )
    # Coverage gate — every cited-disposition claim must appear in
    # applied inlines OR skipped_claims. (supported+weak_anchor)
    expected_cited_ids = {
        str(c.get("claim_id")) for c in (seed.get("claims") or [])
        if c.get("disposition") in CITED_DISPOSITIONS
    }
    applied_inline_ids = {
        str(a.get("claim_id")) for a in applied
        if a.get("kind") == "inline" and a.get("status") == "applied"
    }
    missing_cited = expected_cited_ids - applied_inline_ids - skipped_ids
    if missing_cited:
        for cid in sorted(missing_cited):
            applied.append({
                "claim_id": cid,
                "kind": "inline",
                "status": "skipped",
                "reason": "not_addressed_by_agent",
            })
    codex_dropped_count = len(missing_cited)

    # Only write to disk on a clean diff. A failed diff lint means
    # Codex made an unauthorized prose change or skipped required
    # actions — either way, leaving the original file untouched lets
    # the batch wrapper move on without polluting other modules' diffs.
    if not diff_issues:
        module_path.write_text(new_body, encoding="utf-8")

    # Write a deferred-claims record so allowlist-expansion review has
    # the full list. Rewrites are applied in-place; no revision record
    # needed for them any more.
    deferred_record_path = None
    if deferred or missing_cited:
        rp = REPO_ROOT / ".pipeline" / "citation-revisions" / f"{normalized_key.replace('/', '-')}.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        missing_lookup = set(str(cid) for cid in missing_cited)
        rp.write_text(
            json.dumps({
                "module_key": normalized_key,
                "module_path": str(module_path.relative_to(REPO_ROOT)),
                "recorded_at": _iso_utc_now(),
                "needs_allowlist_expansion": [
                    {
                        "claim_id": c.get("claim_id"),
                        "claim_text": c.get("claim_text"),
                        "span_hint": c.get("span_hint"),
                        "off_allowlist_url": c.get("proposed_url"),
                        "rationale": c.get("rationale"),
                    }
                    for c in deferred
                ],
                "codex_dropped": [
                    {
                        "claim_id": c.get("claim_id"),
                        "claim_text": c.get("claim_text"),
                        "span_hint": c.get("span_hint"),
                        "proposed_url": c.get("proposed_url"),
                        "disposition": c.get("disposition"),
                    }
                    for c in seed.get("claims") or []
                    if str(c.get("claim_id")) in missing_lookup
                ],
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        deferred_record_path = str(rp.relative_to(REPO_ROOT))

    return {
        "module_key": normalized_key, "ok": len(diff_issues) == 0,
        "module_path": str(module_path.relative_to(REPO_ROOT)),
        "codex_dropped_count": codex_dropped_count,
        "inline_applied": sum(1 for a in applied if a.get("kind") == "inline" and a.get("status") == "applied"),
        "rewrite_applied": sum(1 for a in applied if a.get("kind") == "prose_rewrite" and a.get("status") == "applied"),
        "rejected_count": sum(1 for a in applied if a.get("status") == "rejected"),
        "applied": applied,
        "diff_issues": diff_issues,
        "deferred_count": len(deferred),
        "deferred_record": deferred_record_path,
    }


# ---- CLI -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Citation backfill orchestrator")
    subs = parser.add_subparsers(dest="command", required=True)

    rp = subs.add_parser("research", help="Run the research step on one module")
    rp.add_argument("module_key", help="Module key under src/content/docs/")
    rp.add_argument("--agent", default="codex", choices=["codex", "agy"])
    rp.add_argument(
        "--section-pool-ref",
        help="Optional docs/citation-pools/<section>.json reference for shared sources",
    )
    rp.add_argument("--dry-run", action="store_true",
                    help="Print prompt + exit; no dispatch, no writes")

    ip = subs.add_parser("inject", help="Apply already-validated seed to one module")
    ip.add_argument("module_key", help="Module key under src/content/docs/")
    ip.add_argument("--agent", default="codex", choices=["codex", "agy"])
    ip.add_argument("--dry-run", action="store_true",
                    help="Print prompt + exit; no dispatch, no writes")

    args = parser.parse_args(argv)

    if args.command == "research":
        result = run_research(
            args.module_key,
            agent=args.agent,
            dry_run=args.dry_run,
            section_pool_ref=args.section_pool_ref,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") or result.get("dry_run") else 1

    if args.command == "inject":
        result = run_inject(args.module_key, agent=args.agent, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") or result.get("dry_run") else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
