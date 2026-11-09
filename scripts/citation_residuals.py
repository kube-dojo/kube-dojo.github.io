#!/usr/bin/env python3
"""Auto-resolver for citation residuals filed by pipeline_v4 Stage 4.

Reads `.pipeline/v3/human-review/<module>.json`, resolves the
`queued_findings.needs_citation[]` entries by asking a small LLM for
candidate URLs, validating each via `fetch_citation`, and appending the
accepted URL to the module's `## Sources` section. Unresolved findings
move to `unresolvable_findings[]` so re-runs are idempotent.

See GH #343/#344 for the staged resolver specs and #341 for the parent epic.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_citation  # noqa: E402
from citation_backfill import (  # noqa: E402
    DispatcherUnavailable,
    dispatch_agy,
    dispatch_claude,
    parse_agent_response,
)
from pipeline_common import module_lock  # noqa: E402


def dispatch_codex_cli(*_args, **_kwargs):
    raise RuntimeError("legacy dispatcher removed")

HUMAN_REVIEW_DIR = REPO_ROOT / ".pipeline" / "v3" / "human-review"
DEFAULT_MAX_CANDIDATES = 3
MIN_SIGNAL_ANCHORS_REQUIRED = 1
HEAD_CHECK_TIMEOUT_SECONDS = 5.0

#: Per-finding Gemini timeout. URL-candidate generation is a small prompt
#: with a structured JSON response; normal Flash/Pro responses are 1-30s.
#: The default dispatch_gemini timeout (900s, inherited from the write-
#: path pipeline) meant one stuck LLM call would block a 10-module pilot
#: for 15 min with no progress. Matches the precedent in
#: scripts/dedupe_audit.py, which does similar short-prompt work at 120s.
GEMINI_PER_FINDING_TIMEOUT = 120

#: Per-finding Claude timeout. Claude CLI is the alternate dispatcher
#: (see `--agent claude`) after the 2026-04-24 pilot confirmed that even
#: Category-A modules were hitting the 120s Gemini cap with zero
#: resolves, consistent with false-timeout-mid-thought. Claude tends to
#: respond faster for structured JSON prompts; 180s gives headroom over
#: observed 30-60s typical responses without inviting the same trap.
CLAUDE_PER_FINDING_TIMEOUT = 180
CODEX_RESIDUAL_MODEL = "gpt-5.5"
CODEX_RESIDUAL_TIMEOUT = 300

BUCKET_NEEDS_CITATION = "needs_citation"
BUCKET_OVERSTATED_UNFIXED = "overstated_unfixed"
BUCKET_OFF_TOPIC_UNFIXED = "off_topic_unfixed"
BUCKET_OVERSTATEMENT_QUEUED = "overstatement_queued"
BUCKET_OFF_TOPIC_DELETE_QUEUED = "off_topic_delete_queued"
QUEUED_BUCKETS = (BUCKET_OVERSTATEMENT_QUEUED, BUCKET_OFF_TOPIC_DELETE_QUEUED)
PHASE2_BUCKETS = (
    BUCKET_OVERSTATED_UNFIXED,
    BUCKET_OFF_TOPIC_UNFIXED,
    BUCKET_OVERSTATEMENT_QUEUED,
    BUCKET_OFF_TOPIC_DELETE_QUEUED,
)


def _dispatch_agy_for_candidate(prompt: str) -> tuple[bool, str]:
    """dispatch_agy wrapper with the short per-finding timeout.

    Kept as the default dispatcher for request_candidates /
    resolve_module so research/inject paths in citation_backfill are
    unaffected by the pilot's per-finding budget.
    """
    return dispatch_agy(prompt, timeout=GEMINI_PER_FINDING_TIMEOUT)


def _dispatch_claude_for_candidate(prompt: str) -> tuple[bool, str]:
    """dispatch_claude wrapper with the short per-finding timeout."""
    return dispatch_claude(prompt, timeout=CLAUDE_PER_FINDING_TIMEOUT)


def _dispatch_codex_for_residual(prompt: str) -> tuple[bool, str]:
    """Codex wrapper for phase-2 rewrite/delete residuals."""
    return dispatch_codex_cli(
        prompt,
        model=CODEX_RESIDUAL_MODEL,
        timeout=CODEX_RESIDUAL_TIMEOUT,
    )


CANDIDATE_DISPATCHERS = {
    "agy": _dispatch_agy_for_candidate,
    "claude": _dispatch_claude_for_candidate,
}
MIN_QUOTE_MATCH_LENGTH = 12
# Default lease is generous — a single module can take several minutes
# when the LLM dispatch stalls or the network is slow; a tight TTL would
# let another worker steal the lock mid-run and clobber writes. A stuck
# run can always be released manually via sweep_expired_locks after the
# operator is sure the holding process is dead.
DEFAULT_LOCK_LEASE_SECONDS = 1800


# ---- IO ------------------------------------------------------------------


def load_queue_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue_file(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def module_path_from_key(module_key: str) -> Path:
    return REPO_ROOT / "src" / "content" / "docs" / (module_key + ".md")


# ---- signal extraction ---------------------------------------------------


_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_PRICE_RE = re.compile(
    r"\$\s*[\d,.]+\s*(?:billion|million|thousand|[bmk])?",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")


def extract_anchors(excerpt: str, signals: list[str]) -> list[str]:
    """Pick concrete substrings from `excerpt` that a source page must
    contain to validate the citation.

    Mirrors the signal taxonomy emitted by citation_v3. Anchors are the
    *values* (e.g. "2014", "$6.5 billion") not the category names.
    """
    anchors: list[str] = []
    signal_set = set(signals)
    if "dated_year" in signal_set or "year_reference" in signal_set:
        anchors.extend(m.group(0) for m in _YEAR_RE.finditer(excerpt))
    if "price_usd" in signal_set or "dollar_amount" in signal_set:
        anchors.extend(m.group(0).strip() for m in _PRICE_RE.finditer(excerpt))
    if "percentage" in signal_set:
        anchors.extend(m.group(0).strip() for m in _PERCENT_RE.finditer(excerpt))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    result: list[str] = []
    for a in anchors:
        key = a.lower()
        if key not in seen:
            seen.add(key)
            result.append(a)
    return result


def anchors_present_in_text(anchors: list[str], text: str) -> list[str]:
    if not anchors:
        return []
    text_lower = text.lower()
    return [a for a in anchors if a.lower() in text_lower]


# ---- candidate discovery -------------------------------------------------


CANDIDATE_PROMPT = """You are helping cite a factual claim in a technical curriculum module.

The claim (from the module):
---
{excerpt}
---

Signals the fact-checker flagged: {signals}
Search hints prepared by the fact-checker:
{hints}

HARD CONSTRAINT — the pipeline's deterministic gate ONLY accepts URLs whose
host is on this exact allowlist:

{allowlist}

Any URL whose host is not on that list will be rejected before the content is
even checked. Press domains like reuters.com, bbc.com, theverge.com,
theguardian.com, wired.com are NOT on the allowlist — do not suggest them.

For this type of claim, the most commonly useful hosts are:
  - en.wikipedia.org for named incidents, acquisitions, public events where
    no primary source is available.
  - the vendor's own .com for vendor-published claims about their own
    product/outage/acquisition.
  - standards/upstream docs for capability claims about specific tools.

Return 1-3 candidate URLs that (a) are on the allowlist above AND (b) you have
high confidence actually discuss the specific claim — same year, same dollar
figure, same named incident/company. Do not invent URLs. If no allowlist URL
plausibly covers the claim, return an empty list.

For every candidate you MUST include an `expected_quote` — a specific
sentence or phrase (minimum 12 characters, case-insensitive) that the page
actually contains and that supports the claim. The resolver fetches the page
and rejects any candidate whose expected_quote is not a substring of the
page body. Do not paraphrase or invent quotes — copy from the page you are
citing. If you cannot commit to a specific quote, do not include the URL.

Respond with strict JSON, no prose, no code fences:
{{
  "candidates": [
    {{"url": "https://...", "tier": "standards|upstream|vendor|incidents|general", "why": "one sentence", "expected_quote": "A sentence or phrase from the page that supports the claim."}},
    ...
  ]
}}
"""


def _format_allowlist_for_prompt() -> str:
    """Render the yaml allowlist as a flat, prompt-friendly list so the LLM
    can actually comply with the constraint."""
    import yaml

    try:
        raw = yaml.safe_load(
            (REPO_ROOT / "docs" / "citation-trusted-domains.yaml").read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError):
        return "  (allowlist unreadable; reject everything)"
    tiers = raw.get("tiers") or {}
    lines: list[str] = []
    for tier_name, domains in tiers.items():
        clean = [str(d).split("#", 1)[0].strip() for d in (domains or [])]
        clean = [d for d in clean if d]
        if clean:
            lines.append(f"  {tier_name}: {', '.join(clean)}")
    return "\n".join(lines)


def build_candidate_prompt(finding: dict[str, Any]) -> str:
    hints = finding.get("search_hint") or []
    hint_lines = "\n".join(f"  - {h}" for h in hints) if hints else "  (none)"
    return CANDIDATE_PROMPT.format(
        excerpt=finding.get("excerpt", "").strip(),
        signals=", ".join(finding.get("signals") or []) or "(none)",
        hints=hint_lines,
        allowlist=_format_allowlist_for_prompt(),
    )


def head_check(
    url: str,
    *,
    timeout: float = HEAD_CHECK_TIMEOUT_SECONDS,
) -> bool:
    """Return True if ``url`` resolves to a live 2xx/3xx response.

    Escalation ladder:
        1. HEAD — cheapest probe.
        2. On 405 Method Not Allowed, zero-byte range GET.
        3. On Range-specific rejection (403 / 416 / 501 — WAFs that
           reject Range but would serve a normal GET), plain GET.

    Expected transport failures (DNS, connection reset, timeout,
    malformed URL) return False. Unexpected exceptions bubble up so
    coding regressions don't silently convert into "dead URL" drops
    (#357 Codex review, nit #2).

    This is the deterministic gate for URL-existence hallucinations.
    See GH #356 Part 1.
    """
    import http.client
    import socket
    import urllib.error
    import urllib.request

    _transport_errors: tuple[type[BaseException], ...] = (
        urllib.error.URLError,
        http.client.HTTPException,
        socket.timeout,
        socket.gaierror,
        ConnectionError,
        TimeoutError,
    )

    def _try(method: str, extra_headers: dict[str, str] | None = None) -> int | None:
        req = urllib.request.Request(
            url,
            method=method,
            headers={
                "User-Agent": fetch_citation.DEFAULT_UA,
                "Accept": fetch_citation.DEFAULT_ACCEPT,
                **(extra_headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status)
        except urllib.error.HTTPError as exc:
            return int(exc.code)
        except _transport_errors:
            return None

    status = _try("HEAD")
    if status is None:
        return False
    if 200 <= status < 400:
        return True
    if status == 405:
        # Server rejects HEAD but may accept a range-limited GET.
        range_status = _try("GET", extra_headers={"Range": "bytes=0-0"})
        if range_status is not None and 200 <= range_status < 400:
            return True
        # WAFs/CDNs sometimes reject Range with 403 / 416 / 501 where
        # a plain GET would return 200. Fall through to a final GET
        # as the last escalation step (#357 Codex review, nit #1).
        if range_status in (403, 416, 501):
            get_status = _try("GET")
            if get_status is None:
                return False
            return 200 <= get_status < 400
        return False
    return False


def request_candidates(
    finding: dict[str, Any],
    *,
    dispatcher=_dispatch_agy_for_candidate,
    allowlist_tier=fetch_citation.allowlist_tier,
    head_checker=None,
) -> list[dict[str, Any]]:
    """Ask the LLM for candidate URLs. Returns a list of dicts with
    ``url``, ``tier``, ``why``. Empty list on any failure (the caller
    marks the finding unresolvable).

    Pre-filters hallucinations deterministically:
      1. URL must be on ``docs/citation-trusted-domains.yaml`` allowlist.
         LLMs reliably suggest off-allowlist URLs despite the prompt's
         hard constraint — this filter is advisory's enforcement.
      2. URL must respond to HEAD (or range-GET fallback) with a 2xx/3xx.
         Eliminates the "LLM confidently fabricated a 404 URL" class
         before downstream fetch + anchor work.

    Both filters are injectable for testing. ``head_checker`` defaults
    to the module-level ``head_check`` but is resolved at call time so
    tests can swap it in via parameter.
    """
    if head_checker is None:
        head_checker = head_check
    prompt = build_candidate_prompt(finding)
    ok, raw = dispatcher(prompt)
    if not ok:
        return []
    try:
        parsed = parse_agent_response(raw)
    except (ValueError, json.JSONDecodeError):
        return []
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list):
        return []
    valid: list[dict[str, Any]] = []
    for c in candidates[:DEFAULT_MAX_CANDIDATES]:
        if not isinstance(c, dict):
            continue
        url = str(c.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        if not allowlist_tier(url):
            continue
        if not head_checker(url):
            continue
        quote = str(c.get("expected_quote") or "").strip()
        valid.append(
            {
                "url": url,
                "tier": str(c.get("tier") or "unknown"),
                "why": str(c.get("why") or "").strip(),
                "expected_quote": quote,
            }
        )
    return valid


def normalize_quote(text: str) -> str:
    """Collapse whitespace, strip, lowercase — makes substring match
    tolerant of the LLM's minor transcription drift (line breaks,
    double spaces, casing)."""
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_present_in_text(quote: str, body: str) -> bool:
    """Check whether ``quote`` is present in ``body`` after whitespace +
    case normalization.

    Primary path: the full normalized quote must be a substring of the
    body. Drift-tolerance fallback: BOTH a start window AND an end
    window (each ≥ ``MIN_QUOTE_MATCH_LENGTH`` chars, word-boundary-
    aligned) must appear in the body in order. This rejects generic
    lead-ins like "According to the article..." where only the prefix
    matches but the claim-specific tail differs (#360 Codex review,
    must-fix #2).

    Returns False when the normalized quote is too short to be
    meaningful — that's the LLM hedging, not evidence.
    """
    norm_quote = normalize_quote(quote)
    if len(norm_quote) < MIN_QUOTE_MATCH_LENGTH:
        return False
    norm_body = normalize_quote(body)
    if norm_quote in norm_body:
        return True
    # Drift-tolerance fallback: require the quote's start AND end
    # windows to both appear in the body, in order. The quote must be
    # roughly 2× MIN + small gap so the start and end windows don't
    # overlap.
    if len(norm_quote) < 2 * MIN_QUOTE_MATCH_LENGTH + 4:
        return False
    start_window = _trim_to_trailing_word_boundary(
        norm_quote[: MIN_QUOTE_MATCH_LENGTH + 4]
    )
    end_window = _trim_to_leading_word_boundary(
        norm_quote[-(MIN_QUOTE_MATCH_LENGTH + 4):]
    )
    if (
        len(start_window) < MIN_QUOTE_MATCH_LENGTH
        or len(end_window) < MIN_QUOTE_MATCH_LENGTH
    ):
        return False
    start_idx = norm_body.find(start_window)
    if start_idx < 0:
        return False
    return end_window in norm_body[start_idx + len(start_window):]


def _trim_to_trailing_word_boundary(text: str) -> str:
    """Drop a trailing partial word so a window ends on a clean
    whitespace boundary. Returns the original string when no space
    exists to trim against."""
    if " " not in text:
        return text
    return text.rsplit(" ", 1)[0]


def _trim_to_leading_word_boundary(text: str) -> str:
    """Mirror of _trim_to_trailing_word_boundary for the start of a
    window: drop a leading partial word."""
    if " " not in text:
        return text
    return text.split(" ", 1)[1]


# ---- validation ----------------------------------------------------------


def validate_candidate(
    candidate: dict[str, Any],
    finding: dict[str, Any],
    *,
    fetcher=fetch_citation.fetch,
    cached_text_path=fetch_citation.cached_text_path,
    allowlist_tier=fetch_citation.allowlist_tier,
) -> dict[str, Any]:
    """Validate a candidate URL for a finding.

    Returns a dict with either ``ok: True`` (and page metadata) or
    ``ok: False`` with a ``reason`` string.

    The allowlist check runs BEFORE ``fetcher()`` so off-allowlist hosts
    don't incur a network round-trip. The LLM's allowlist-constraint is
    advisory only — this is the real gate (#355 Codex review, must-fix).
    """
    url = candidate["url"]
    expected_quote = str(candidate.get("expected_quote") or "").strip()

    # Phase 1: host allowlist (pre-network, deterministic).
    prechecked_tier = allowlist_tier(url)
    if not prechecked_tier:
        return {"ok": False, "url": url, "reason": "off_allowlist"}

    # Phase 2: require some way to verify the page actually discusses
    # the claim. Two paths:
    #   A. The finding has deterministic anchors (year/price/percent).
    #   B. The LLM committed to a specific expected_quote substring.
    # At least one must be present, otherwise we'd accept "any 200
    # allowlisted page" regardless of topical relevance. Phase 3 runs
    # whichever path was populated (or both).
    anchors = extract_anchors(
        finding.get("excerpt", ""),
        finding.get("signals") or [],
    )
    has_anchors = bool(anchors)
    has_quote = bool(expected_quote)
    if not has_anchors and not has_quote:
        return {
            "ok": False,
            "url": url,
            "reason": "no_verification_signal",
            "signals": finding.get("signals") or [],
        }

    # Phase 3: fetch + content match.
    try:
        meta = fetcher(url)
    except Exception as exc:  # noqa: BLE001 — network errors are expected
        return {"ok": False, "url": url, "reason": f"fetch_raised:{type(exc).__name__}"}
    status = int(meta.get("status") or 0)
    if status != 200:
        return {"ok": False, "url": url, "reason": f"http_{status}"}
    post_fetch_tier = meta.get("allowlist_tier")
    if not post_fetch_tier:
        # Redirected to an off-allowlist host.
        return {"ok": False, "url": url, "reason": "off_allowlist_after_redirect"}
    text_path = cached_text_path(url)
    try:
        body = text_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"ok": False, "url": url, "reason": "cache_read_failed"}

    matched_anchors = anchors_present_in_text(anchors, body) if has_anchors else []
    quote_matched = quote_present_in_text(expected_quote, body) if has_quote else False

    # When anchors exist, they are authoritative: a claim containing
    # "2018" must land on a page that says "2018". A matching
    # expected_quote cannot override an anchor mismatch, because a
    # generic quote can appear on pages that don't match the
    # claim-specific value (#360 Codex review, must-fix #1). The
    # quote-only acceptance path is therefore limited to anchorless
    # findings.
    anchors_ok = has_anchors and len(matched_anchors) >= MIN_SIGNAL_ANCHORS_REQUIRED
    if has_anchors and not anchors_ok:
        return {
            "ok": False,
            "url": url,
            "reason": "no_anchor_match",
            "anchors_expected": anchors,
            "anchors_matched": matched_anchors,
            "quote_matched": quote_matched,
        }
    if anchors_ok or quote_matched:
        return {
            "ok": True,
            "url": url,
            "final_url": meta.get("final_url", url),
            "tier": post_fetch_tier,
            "anchors_matched": matched_anchors,
            "quote_matched": quote_matched,
            "verified_via": "anchors" if anchors_ok else "expected_quote",
            "page_bytes": meta.get("bytes", 0),
        }

    # Anchorless and quote didn't match.
    return {
        "ok": False,
        "url": url,
        "reason": "quote_not_in_page",
        "expected_quote": expected_quote,
    }


# ---- injection into module --------------------------------------------------


_SOURCES_HEADER_RE = re.compile(r"^## Sources\s*$", re.MULTILINE)


def short_id_for(url: str) -> str:
    return "res-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]


def build_source_line(url: str, finding: dict[str, Any], *, title: str | None = None) -> str:
    """Render one ``- [title](url)`` bullet for the Sources list.

    ``finding`` is retained in the signature for call-site compatibility
    but is intentionally unused: earlier versions appended a "description"
    derived from the finding's excerpt, which was the *claim being cited*
    rather than a description of what the source actually says (see #364).
    A URL-derived title is sufficient provenance; richer per-source
    descriptions — if wanted — should come from the cited page itself
    (``<title>``, ``<meta description>``) or an LLM summary of the page
    body, never from the module text.
    """
    del finding  # intentionally unused; see docstring
    display_title = title or _derive_title_from_url(url)
    safe_title = display_title.replace("[", r"\[").replace("]", r"\]")
    return f"- [{safe_title}]({url})"


def _derive_title_from_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = (parsed.hostname or "").removeprefix("www.")
    path_segments = [seg for seg in parsed.path.split("/") if seg]
    tail = path_segments[-1] if path_segments else ""
    # Strip the document extension (.html/.htm) so the title reads as a
    # page name rather than a filename. Non-doc extensions (.pdf, .json)
    # are preserved because they carry meaningful format signal.
    for ext in (".html", ".htm"):
        if tail.lower().endswith(ext):
            tail = tail[: -len(ext)]
            break
    readable = tail.replace("-", " ").replace("_", " ").strip()
    if host and readable:
        return f"{host}: {readable}"
    return host or url


def inject_source(module_text: str, source_line: str) -> tuple[str, bool]:
    """Append ``source_line`` inside the module's ``## Sources`` section.

    Inserts just before the next ``## `` header (or at EOF if none), so
    any content that follows the Sources block is preserved. Creates the
    section at EOF if missing. Idempotent: if the exact line is already
    present, returns ``(original, False)``.
    """
    if source_line in module_text:
        return module_text, False
    header_match = _SOURCES_HEADER_RE.search(module_text)
    if header_match:
        # Find the start of the next H2 header (if any) after the Sources header.
        after_header = module_text[header_match.end():]
        next_h2 = re.search(r"^## ", after_header, re.MULTILINE)
        if next_h2:
            insert_pos = header_match.end() + next_h2.start()
            # Walk backwards to strip trailing blank lines between the last
            # Sources bullet and the next H2 so we don't append into whitespace.
            prefix = module_text[:insert_pos].rstrip("\n")
            suffix = module_text[insert_pos:]
            return prefix + "\n" + source_line + "\n\n" + suffix, True
        # No following section — append at EOF, same as before.
        trimmed = module_text.rstrip("\n")
        return trimmed + "\n" + source_line + "\n", True
    # No Sources section yet — create one.
    trimmed = module_text.rstrip("\n")
    return trimmed + "\n\n## Sources\n\n" + source_line + "\n", True


# ---- per-module resolver -------------------------------------------------


def resolve_module(
    queue_path: Path,
    *,
    dry_run: bool = False,
    dispatcher=_dispatch_agy_for_candidate,
    fetcher=fetch_citation.fetch,
    cached_text_path=fetch_citation.cached_text_path,
    allowlist_tier=fetch_citation.allowlist_tier,
    head_checker=None,
) -> dict[str, Any]:
    """Resolve all `needs_citation` findings for one module.

    Returns a stats dict:
        {
          "module_key": str,
          "considered": int,
          "resolved": int,
          "unresolvable": int,
          "skipped_already_resolved": int,
          "module_edited": bool,
        }
    """
    data = load_queue_file(queue_path)
    module_key = data.get("module_key") or queue_path.stem
    queued = data.setdefault("queued_findings", {})
    needs_citation: list[dict[str, Any]] = list(queued.get("needs_citation") or [])
    resolved_list: list[dict[str, Any]] = list(data.setdefault("resolved_findings", []))
    unresolvable_list: list[dict[str, Any]] = list(
        data.setdefault("unresolvable_findings", [])
    )

    module_path = module_path_from_key(module_key)
    if not module_path.exists():
        return {
            "module_key": module_key,
            "considered": 0,
            "resolved": 0,
            "unresolvable": 0,
            "skipped_already_resolved": 0,
            "module_edited": False,
            "error": "module_not_found",
        }

    module_text = module_path.read_text(encoding="utf-8")
    module_dirty = False

    still_pending: list[dict[str, Any]] = []
    stats = {
        "module_key": module_key,
        "considered": len(needs_citation),
        "resolved": 0,
        "unresolvable": 0,
        "skipped_already_resolved": 0,
        "module_edited": False,
    }

    for finding in needs_citation:
        candidates = request_candidates(
            finding,
            dispatcher=dispatcher,
            allowlist_tier=allowlist_tier,
            head_checker=head_checker,
        )
        if not candidates:
            finding_record = dict(finding)
            finding_record["unresolvable_reason"] = "no_candidates_returned"
            finding_record["resolved_at"] = _now_iso()
            unresolvable_list.append(finding_record)
            stats["unresolvable"] += 1
            continue

        accepted: dict[str, Any] | None = None
        attempts: list[dict[str, Any]] = []
        for candidate in candidates:
            validation = validate_candidate(
                candidate,
                finding,
                fetcher=fetcher,
                cached_text_path=cached_text_path,
                allowlist_tier=allowlist_tier,
            )
            attempts.append({"candidate": candidate, "validation": validation})
            if validation.get("ok"):
                accepted = {"candidate": candidate, "validation": validation}
                break

        if accepted is None:
            finding_record = dict(finding)
            finding_record["unresolvable_reason"] = "all_candidates_failed"
            finding_record["attempts"] = attempts
            finding_record["resolved_at"] = _now_iso()
            unresolvable_list.append(finding_record)
            stats["unresolvable"] += 1
            continue

        url = accepted["validation"]["final_url"]
        source_line = build_source_line(url, finding)
        if dry_run:
            _, injected = inject_source(module_text, source_line)
            stats["resolved"] += 1
            still_pending.append(
                {
                    **finding,
                    "_dry_run_proposed": {
                        "url": url,
                        "source_line": source_line,
                        "injected": injected,
                    },
                }
            )
            continue

        module_text, injected = inject_source(module_text, source_line)
        if not injected:
            stats["skipped_already_resolved"] += 1
        else:
            module_dirty = True

        resolved_list.append(
            {
                **finding,
                "resolved_at": _now_iso(),
                "url": url,
                "tier": accepted["validation"]["tier"],
                "short_id": short_id_for(url),
                "anchors_matched": accepted["validation"].get("anchors_matched", []),
            }
        )
        stats["resolved"] += 1

    if module_dirty:
        module_path.write_text(module_text, encoding="utf-8")
        stats["module_edited"] = True

    if not dry_run:
        queued["needs_citation"] = still_pending
        data["resolved_findings"] = resolved_list
        data["unresolvable_findings"] = unresolvable_list
        save_queue_file(queue_path, data)

    return stats


OVERSTATEMENT_PROMPT = """You are editing one sentence in a Kubernetes/cloud curriculum module.

The auditor flagged the sentence as overstated because it uses an absolute or
over-broad claim. Propose a drop-in replacement that softens the claim while
preserving the technical meaning.

Rules:
- Return exactly one replacement sentence.
- Do not add citations.
- Do not add new facts.
- Keep product names, commands, versions, and exam terminology unchanged.
- Prefer words like "often", "typically", "can", "may", "in many cases" when accurate.

Trigger: {trigger}
Original sentence:
{sentence}

Auditor's suggested rewrite, if present:
{suggested_rewrite}

Respond with strict JSON only:
{{"suggested_rewrite": "replacement sentence"}}
"""

OFF_TOPIC_PROMPT = """You are editing a Kubernetes/cloud curriculum module.

The auditor flagged this paragraph as off-topic. Decide whether the paragraph
should be deleted from the module. Only approve deletion when the excerpt is
clearly unrelated to the surrounding curriculum topic or is obvious filler.

Section: {section}
Reason: {reason}
Suggested action: {suggested_action}
Paragraph excerpt:
{excerpt}

Respond with strict JSON only:
{{"action": "delete" | "keep", "reason": "one concise reason"}}
"""


def _normalize_overstatement_finding(finding: dict[str, Any]) -> dict[str, Any]:
    verdict = finding.get("verdict") or {}
    rewrite = (
        finding.get("suggested_rewrite")
        or finding.get("new")
        or verdict.get("suggested_rewrite")
    )
    return {
        **finding,
        "sentence": finding.get("sentence") or finding.get("old"),
        "verdict": {"verdict": "overstated", "suggested_rewrite": rewrite},
    }


def _normalize_off_topic_finding(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        **finding,
        "verdict": "off_topic",
        "suggested_action": finding.get("suggested_action") or "delete paragraph",
    }


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?=\s|$)", text)) or (1 if text.strip() else 0)


def _swap_overstatement(
    body: str,
    finding: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    normalized = _normalize_overstatement_finding(finding)
    sentence = str(normalized.get("sentence") or "")
    rewrite = str((normalized.get("verdict") or {}).get("suggested_rewrite") or "")
    if not sentence or not rewrite:
        return body, None, {**finding, "queue_reason": "missing_rewrite_or_sentence"}
    count = body.count(sentence)
    if count != 1:
        return body, None, {
            **finding,
            "queue_reason": f"sentence_match_count:{count}",
        }
    if _sentence_count(rewrite) > _sentence_count(sentence):
        return body, None, {
            **finding,
            "queue_reason": "rewrite_sentence_count_grew",
        }
    updated = body.replace(sentence, rewrite, 1)
    return updated, {
        "bucket": finding.get("_bucket", BUCKET_OVERSTATEMENT_QUEUED),
        "action": "softened",
        "line": finding.get("line"),
        "trigger": finding.get("trigger"),
        "old": sentence,
        "new": rewrite,
        "resolved_at": _now_iso(),
    }, None


def _paragraph_records(body: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    lines = body.splitlines(keepends=True)
    start: int | None = None
    chunk: list[str] = []
    in_code = False

    def flush(end_index: int) -> None:
        nonlocal start, chunk
        if start is not None and chunk:
            text = "".join(chunk)
            kind = "code" if "```" in text else "prose"
            records.append(
                {
                    "start": start,
                    "end": end_index,
                    "text": text,
                    "kind": kind,
                }
            )
        start = None
        chunk = []

    for idx, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
        if not line.strip() and not in_code:
            flush(idx)
            continue
        if start is None:
            start = idx
        chunk.append(line)
    flush(len(lines))
    return records


def _delete_off_topic(
    body: str,
    finding: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    normalized = _normalize_off_topic_finding(finding)
    action = str(normalized.get("suggested_action") or "")
    if not action.startswith("delete"):
        return body, None, {**finding, "queue_reason": f"action_not_delete:{action}"}
    excerpt = str(normalized.get("excerpt") or "").strip().rstrip("…").rstrip()
    anchor = " ".join(excerpt.split()[:6])
    if not anchor:
        return body, None, {**finding, "queue_reason": "missing_excerpt"}

    matches = [
        p
        for p in _paragraph_records(body)
        if anchor in " ".join(p["text"].split())
    ]
    if len(matches) != 1:
        return body, None, {
            **finding,
            "queue_reason": f"paragraph_match_count:{len(matches)}",
        }
    match = matches[0]
    if match["kind"] != "prose":
        return body, None, {**finding, "queue_reason": f"paragraph_kind:{match['kind']}"}

    lines = body.splitlines(keepends=True)
    end = match["end"]
    if end < len(lines) and not lines[end].strip():
        end += 1
    updated = "".join(lines[: match["start"]] + lines[end:])
    return updated, {
        "bucket": finding.get("_bucket", BUCKET_OFF_TOPIC_DELETE_QUEUED),
        "action": "deleted",
        "section": finding.get("section"),
        "excerpt": excerpt[:160],
        "removed_lines": end - match["start"],
        "resolved_at": _now_iso(),
    }, None


def request_overstatement_rewrite(
    finding: dict[str, Any],
    *,
    dispatcher=_dispatch_codex_for_residual,
) -> str | None:
    prompt = OVERSTATEMENT_PROMPT.format(
        trigger=finding.get("trigger") or "",
        sentence=finding.get("sentence") or "",
        suggested_rewrite=finding.get("suggested_rewrite") or "",
    )
    ok, raw = dispatcher(prompt)
    if not ok:
        return None
    try:
        parsed = parse_agent_response(raw)
    except (ValueError, json.JSONDecodeError):
        return None
    rewrite = str(parsed.get("suggested_rewrite") or "").strip()
    return rewrite or None


def request_offtopic_action(
    finding: dict[str, Any],
    *,
    dispatcher=_dispatch_codex_for_residual,
) -> str | None:
    prompt = OFF_TOPIC_PROMPT.format(
        section=finding.get("section") or "",
        reason=finding.get("reason") or "",
        suggested_action=finding.get("suggested_action") or "",
        excerpt=finding.get("excerpt") or "",
    )
    ok, raw = dispatcher(prompt)
    if not ok:
        return None
    try:
        parsed = parse_agent_response(raw)
    except (ValueError, json.JSONDecodeError):
        return None
    action = str(parsed.get("action") or "").strip().lower()
    return action or None


def _apply_phase2_finding(
    body: str,
    bucket: str,
    finding: dict[str, Any],
    *,
    dispatcher=_dispatch_codex_for_residual,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    working = {**finding, "_bucket": bucket}
    if bucket == BUCKET_OVERSTATEMENT_QUEUED:
        return _swap_overstatement(body, working)
    if bucket == BUCKET_OFF_TOPIC_DELETE_QUEUED:
        return _delete_off_topic(body, working)
    if bucket == BUCKET_OVERSTATED_UNFIXED:
        rewrite = request_overstatement_rewrite(working, dispatcher=dispatcher)
        if not rewrite:
            return body, None, {**finding, "queue_reason": "llm_no_rewrite"}
        working["suggested_rewrite"] = rewrite
        return _swap_overstatement(body, working)
    if bucket == BUCKET_OFF_TOPIC_UNFIXED:
        action = request_offtopic_action(working, dispatcher=dispatcher)
        if action != "delete":
            return body, None, {**finding, "queue_reason": f"llm_action:{action}"}
        working["suggested_action"] = "delete paragraph"
        return _delete_off_topic(body, working)
    return body, None, {**finding, "queue_reason": f"unsupported_bucket:{bucket}"}


def resolve_phase2_module(
    queue_path: Path,
    *,
    fix_overstatements: bool = False,
    fix_offtopic: bool = False,
    apply_queued: bool = False,
    dry_run: bool = False,
    dispatcher=_dispatch_codex_for_residual,
) -> dict[str, Any]:
    """Resolve #344 phase-2 residual buckets for one module."""
    data = load_queue_file(queue_path)
    module_key = data.get("module_key") or queue_path.stem
    queued = data.setdefault("queued_findings", {})
    buckets: list[str] = []
    if fix_overstatements:
        buckets.append(BUCKET_OVERSTATED_UNFIXED)
    if fix_offtopic:
        buckets.append(BUCKET_OFF_TOPIC_UNFIXED)
    if apply_queued:
        buckets.extend(QUEUED_BUCKETS)

    module_path = module_path_from_key(module_key)
    stats = {
        "module_key": module_key,
        "considered": 0,
        "resolved": 0,
        "unresolvable": 0,
        "skipped_already_resolved": 0,
        "module_edited": False,
    }
    if not module_path.exists():
        stats["error"] = "module_not_found"
        return stats

    module_text = module_path.read_text(encoding="utf-8")
    resolved_list: list[dict[str, Any]] = list(data.setdefault("resolved_findings", []))

    for bucket in buckets:
        findings = list(queued.get(bucket) or [])
        if not findings:
            continue
        pending: list[dict[str, Any]] = []
        for finding in findings:
            stats["considered"] += 1
            module_text, applied, leftover = _apply_phase2_finding(
                module_text,
                bucket,
                finding,
                dispatcher=dispatcher,
            )
            if applied is not None:
                stats["resolved"] += 1
                resolved_list.append(applied)
            else:
                stats["unresolvable"] += 1
                pending.append(leftover or finding)
        if not dry_run:
            queued[bucket] = pending

    if not dry_run:
        original_text = module_path.read_text(encoding="utf-8")
        if module_text != original_text:
            module_path.write_text(module_text, encoding="utf-8")
            stats["module_edited"] = True
        data["resolved_findings"] = resolved_list
        save_queue_file(queue_path, data)
    else:
        stats["module_edited"] = module_text != module_path.read_text(encoding="utf-8")

    return stats


def _selected_buckets(args: argparse.Namespace) -> list[str]:
    phase2_selected = args.fix_overstatements or args.fix_offtopic or args.apply_queued
    buckets: list[str] = []
    if args.fix_citations or not phase2_selected:
        buckets.append(BUCKET_NEEDS_CITATION)
    if args.fix_overstatements:
        buckets.append(BUCKET_OVERSTATED_UNFIXED)
    if args.fix_offtopic:
        buckets.append(BUCKET_OFF_TOPIC_UNFIXED)
    if args.apply_queued:
        buckets.extend(QUEUED_BUCKETS)
    return buckets


def _has_selected_findings(queue_path: Path, buckets: list[str]) -> bool:
    try:
        data = load_queue_file(queue_path)
    except Exception:  # noqa: BLE001
        return False
    qf = data.get("queued_findings") or {}
    return any(qf.get(bucket) for bucket in buckets)


def _sample_findings(
    targets: list[Path],
    buckets: list[str],
    sample_size: int,
) -> list[tuple[Path, str, int, dict[str, Any]]]:
    candidates: list[tuple[Path, str, int, dict[str, Any]]] = []
    for queue_path in targets:
        try:
            data = load_queue_file(queue_path)
        except Exception:  # noqa: BLE001
            continue
        qf = data.get("queued_findings") or {}
        for bucket in buckets:
            if bucket == BUCKET_NEEDS_CITATION:
                continue
            for idx, finding in enumerate(qf.get(bucket) or []):
                candidates.append((queue_path, bucket, idx, finding))
    if sample_size >= len(candidates):
        return candidates
    return random.sample(candidates, sample_size)


def run_sample(
    targets: list[Path],
    buckets: list[str],
    sample_size: int,
    *,
    dispatcher=_dispatch_codex_for_residual,
) -> int:
    samples = _sample_findings(targets, buckets, sample_size)
    if not samples:
        print("No sampleable phase-2 findings for the selected flags.")
        return 0
    for sample_idx, (queue_path, bucket, finding_idx, finding) in enumerate(samples, 1):
        data = load_queue_file(queue_path)
        module_key = data.get("module_key") or queue_path.stem
        module_path = module_path_from_key(module_key)
        if not module_path.exists():
            print(f"[sample {sample_idx}] {module_key}: module_not_found")
            continue
        before = module_path.read_text(encoding="utf-8")
        after, applied, leftover = _apply_phase2_finding(
            before,
            bucket,
            finding,
            dispatcher=dispatcher,
        )
        print(f"[sample {sample_idx}] {module_key} {bucket}[{finding_idx}]")
        print(json.dumps(finding, indent=2, ensure_ascii=False))
        if applied is None:
            print(f"not applied: {json.dumps(leftover, ensure_ascii=False)}")
        diff = difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"{module_key}.before",
            tofile=f"{module_key}.after",
            lineterm="",
        )
        print("\n".join(diff) or "(no text change)")
    return 0


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---- bulk + report -------------------------------------------------------


def iter_queue_files() -> list[Path]:
    if not HUMAN_REVIEW_DIR.is_dir():
        return []
    return sorted(
        p for p in HUMAN_REVIEW_DIR.glob("*.json") if not p.name.endswith(".staging.json")
    )


def build_report() -> dict[str, Any]:
    files = iter_queue_files()
    totals: dict[str, int] = {
        "files": 0,
        "needs_citation": 0,
        "overstated_unfixed": 0,
        "off_topic_unfixed": 0,
        "overstatement_queued": 0,
        "off_topic_delete_queued": 0,
        "resolved_findings": 0,
        "unresolvable_findings": 0,
    }
    per_file = []
    for f in files:
        try:
            data = load_queue_file(f)
        except Exception:  # noqa: BLE001 — skip malformed
            continue
        qf = data.get("queued_findings") or {}
        nc = len(qf.get("needs_citation") or [])
        ou = len(qf.get("overstated_unfixed") or [])
        ot = len(qf.get("off_topic_unfixed") or [])
        oq = len(qf.get("overstatement_queued") or [])
        odq = len(qf.get("off_topic_delete_queued") or [])
        res = len(data.get("resolved_findings") or [])
        unres = len(data.get("unresolvable_findings") or [])
        totals["files"] += 1
        totals["needs_citation"] += nc
        totals["overstated_unfixed"] += ou
        totals["off_topic_unfixed"] += ot
        totals["overstatement_queued"] += oq
        totals["off_topic_delete_queued"] += odq
        totals["resolved_findings"] += res
        totals["unresolvable_findings"] += unres
        per_file.append(
            {
                "file": f.name,
                "needs_citation": nc,
                "overstated_unfixed": ou,
                "off_topic_unfixed": ot,
                "overstatement_queued": oq,
                "off_topic_delete_queued": odq,
                "resolved": res,
                "unresolvable": unres,
            }
        )
    return {"totals": totals, "files": per_file}


# ---- CLI ------------------------------------------------------------------


def _queue_path_for(module_key: str) -> Path:
    # Turn "ai-ml-engineering/advanced-genai/module-1.1" style into the
    # flat slash-free filename used in .pipeline/v3/human-review/.
    slug = module_key.replace("/", "-")
    direct = HUMAN_REVIEW_DIR / f"{slug}.json"
    if direct.exists():
        return direct
    # Fallback: substring match.
    matches = [p for p in iter_queue_files() if slug in p.stem]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"No queue file found for module_key={module_key!r}")
    raise SystemExit(
        f"Ambiguous module_key={module_key!r}; matches: {[p.name for p in matches]}"
    )


def main(argv: list[str] | None = None) -> int:
    # Line-buffer so heartbeat prints survive pipes (tee/>log) — block-buffered
    # stdout hid a 16 min hang in the 2026-04-24 pilot run.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(line_buffering=True)
        except (io.UnsupportedOperation, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="Summarize the residuals queue")
    p_report.add_argument("--json", action="store_true", help="Emit JSON to stdout")

    p_resolve = sub.add_parser("resolve", help="Resolve queued residual findings")
    p_resolve.add_argument(
        "module_key",
        nargs="?",
        help="Module key or slug. Use --all instead to process every queued file.",
    )
    p_resolve.add_argument("--all", action="store_true", help="Process every queue file")

    def _positive_int(raw: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"--limit-modules must be a positive integer, got {raw!r}"
            ) from exc
        if value <= 0:
            raise argparse.ArgumentTypeError(
                f"--limit-modules must be >= 1 (got {value}); "
                "silently treating 0 or negative as 'no limit' would let a "
                "typo unleash the full bulk run"
            )
        return value

    p_resolve.add_argument(
        "--limit-modules",
        type=_positive_int,
        default=None,
        metavar="N",
        help=(
            "Cap the number of modules processed in an --all run to N (>=1). "
            "Useful for gradual rollout / pilot runs before a full bulk "
            "batch — see the 2026-04-23 postmortem. Applied AFTER the "
            "empty-queue filter, so N=10 means 10 modules with actual "
            "needs_citation findings, not 10 scanned files. Has no effect "
            "when a specific module_key is given instead of --all. "
            "0 or negative is rejected up front — an invalid cap must not "
            "silently degrade to 'no limit'."
        ),
    )
    p_resolve.add_argument(
        "--dry-run",
        action="store_true",
        help="Propose resolutions but do not write to modules or queue JSON",
    )
    p_resolve.add_argument(
        "--fix-citations",
        action="store_true",
        help=(
            "Resolve queued needs_citation findings. This remains the default "
            "when no phase-2 flags are supplied."
        ),
    )
    p_resolve.add_argument(
        "--fix-overstatements",
        action="store_true",
        help="Use Codex to soften overstated_unfixed findings and apply them.",
    )
    p_resolve.add_argument(
        "--fix-offtopic",
        action="store_true",
        help="Use Codex to confirm/delete off_topic_unfixed findings.",
    )
    p_resolve.add_argument(
        "--apply-queued",
        action="store_true",
        help=(
            "Apply pre-composed overstatement_queued swaps and "
            "off_topic_delete_queued deletions."
        ),
    )
    p_resolve.add_argument(
        "--sample",
        type=_positive_int,
        metavar="N",
        help=(
            "Pick N random phase-2 findings from the selected buckets, print "
            "before/after diffs, and exit without writing files."
        ),
    )
    p_resolve.add_argument(
        "--worker-id",
        default=None,
        help=(
            "Identifier recorded on the per-module write lock. Defaults "
            "to '<pid>@<hostname>'. Use a stable value (e.g. 'resolver-01') "
            "when running parallel batches so operators can see who "
            "holds what."
        ),
    )
    p_resolve.add_argument(
        "--lease-seconds",
        type=int,
        default=DEFAULT_LOCK_LEASE_SECONDS,
        help=(
            "Lock TTL. An abandoned run's lock is considered stealable "
            f"after this many seconds (default {DEFAULT_LOCK_LEASE_SECONDS})."
        ),
    )
    p_resolve.add_argument(
        "--no-lock",
        action="store_true",
        help=(
            "Skip per-module write locking. Only use for --dry-run or "
            "in tests; concurrent runs without the lock can clobber "
            "each other's writes to the same module."
        ),
    )
    p_resolve.add_argument(
        "--agent",
        choices=sorted(CANDIDATE_DISPATCHERS),
        default="agy",
        help=(
            "LLM backend for per-finding URL-candidate generation. "
            "Default is agy (historical). Use claude when agy is "
            "producing high false-timeout rates — see #373. The default "
            "budget differs per agent; both are short-prompt scoped and "
            "do not affect the research/inject write-path callers."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "report":
        report = build_report()
        if args.json:
            print(json.dumps(report, indent=2))
            return 0
        t = report["totals"]
        print(f"Files: {t['files']}")
        print(f"needs_citation open:   {t['needs_citation']}")
        print(f"overstated_unfixed:    {t['overstated_unfixed']}")
        print(f"off_topic_unfixed:     {t['off_topic_unfixed']}")
        print(f"overstatement_queued:  {t['overstatement_queued']}")
        print(f"off_topic_delete_queued: {t['off_topic_delete_queued']}")
        print(f"resolved_findings:     {t['resolved_findings']}")
        print(f"unresolvable_findings: {t['unresolvable_findings']}")
        return 0

    if args.command == "resolve":
        if args.all:
            targets = iter_queue_files()
        else:
            if not args.module_key:
                parser.error("resolve requires either <module_key> or --all")
            targets = [_queue_path_for(args.module_key)]

        selected_buckets = _selected_buckets(args)
        if args.sample is not None:
            return run_sample(targets, selected_buckets, args.sample)

        # Filter out files with no selected entries — cheap early exit.
        useful_targets = [t for t in targets if _has_selected_findings(t, selected_buckets)]

        if not useful_targets:
            print("No residuals with selected findings.")
            return 0

        if args.all and args.limit_modules is not None:
            # argparse type=_positive_int already rejected 0/negative.
            total_before = len(useful_targets)
            useful_targets = useful_targets[: args.limit_modules]
            print(
                f"--limit-modules {args.limit_modules}: "
                f"processing {len(useful_targets)} of {total_before} useful modules"
            )

        totals = {
            "considered": 0,
            "resolved": 0,
            "unresolvable": 0,
            "modules_edited": 0,
            "skipped_locked": 0,
        }
        worker_id = args.worker_id or module_lock.default_holder()
        # --dry-run does not mutate files; lock not required. --no-lock is
        # an explicit operator opt-out (use only in tests).
        use_lock = not (args.dry_run or args.no_lock)
        total_modules = len(useful_targets)
        for i, qp in enumerate(useful_targets, 1):
            t0 = time.time()
            # Lock on the CANONICAL module key (e.g. "ai/foo/module-1.1"),
            # not the flattened queue filename (e.g. "ai-foo-module-1.1").
            # Queue filenames are slash-flattened slugs, but other writers
            # (pipeline_v4, future callers of the shared primitive) will
            # use the real module_key for their locks. Keying on the stem
            # would miss those writers and could alias two distinct real
            # keys whose slugs happen to collide. Falls back to stem only
            # if the JSON is missing the field (legacy files).
            try:
                _queue_data = load_queue_file(qp)
                canonical_key = _queue_data.get("module_key") or qp.stem
            except Exception:  # noqa: BLE001
                canonical_key = qp.stem
            print(f"[{i}/{total_modules}] {canonical_key}: start")
            if use_lock:
                conflict = module_lock.acquire_module_lock(
                    canonical_key,
                    holder=worker_id,
                    lease_seconds=args.lease_seconds,
                )
                if conflict is not None:
                    totals["skipped_locked"] += 1
                    print(
                        f"{canonical_key}: SKIPPED — locked by "
                        f"{conflict.holder!r} until epoch "
                        f"{conflict.expires_at}"
                    )
                    continue
            outcome = "ok"
            print(
                f"[{i}/{total_modules}] {canonical_key}: resolving "
                f"({', '.join(selected_buckets)})"
            )
            try:
                stats = {
                    "module_key": canonical_key,
                    "considered": 0,
                    "resolved": 0,
                    "unresolvable": 0,
                    "module_edited": False,
                }
                if BUCKET_NEEDS_CITATION in selected_buckets:
                    stats = resolve_module(
                        qp,
                        dry_run=args.dry_run,
                        dispatcher=CANDIDATE_DISPATCHERS[args.agent],
                    )
                if any(bucket in PHASE2_BUCKETS for bucket in selected_buckets):
                    phase2_stats = resolve_phase2_module(
                        qp,
                        fix_overstatements=args.fix_overstatements,
                        fix_offtopic=args.fix_offtopic,
                        apply_queued=args.apply_queued,
                        dry_run=args.dry_run,
                    )
                    stats["considered"] += phase2_stats["considered"]
                    stats["resolved"] += phase2_stats["resolved"]
                    stats["unresolvable"] += phase2_stats["unresolvable"]
                    stats["module_edited"] = bool(
                        stats.get("module_edited") or phase2_stats.get("module_edited")
                    )
            except DispatcherUnavailable as exc:
                # Peak-hours guard / budget exhaustion / terminal rate
                # limit. resolve_module writes the queue file only on
                # clean exit, so the in-flight finding stays in
                # needs_citation for a retry — nothing gets flipped to
                # unresolvable. Release the lock, print a clear
                # operator-visible message, and abort the whole run
                # instead of silently grinding through N more modules
                # with the same refusal.
                if use_lock:
                    module_lock.release_module_lock(
                        canonical_key, holder=worker_id
                    )
                print(
                    f"{canonical_key}: ABORT — dispatcher unavailable: {exc}",
                    file=sys.stderr,
                )
                print(
                    "In-flight findings remain in needs_citation; "
                    "re-run after the refusal clears "
                    "(peak hours end / budget reset / rate limit cools).",
                    file=sys.stderr,
                )
                return 3
            except BaseException:
                outcome = "error"
                if use_lock:
                    # Release so a follow-up run is not blocked on our
                    # crash. An abandoned lock would auto-expire after
                    # lease_seconds but we can be precise here.
                    module_lock.release_module_lock(
                        canonical_key, holder=worker_id
                    )
                raise
            else:
                if use_lock:
                    module_lock.complete_module_lock(
                        canonical_key, holder=worker_id, outcome=outcome
                    )
            totals["considered"] += stats["considered"]
            totals["resolved"] += stats["resolved"]
            totals["unresolvable"] += stats["unresolvable"]
            if stats.get("module_edited"):
                totals["modules_edited"] += 1
            print(
                f"{stats['module_key']}: "
                f"considered={stats['considered']} "
                f"resolved={stats['resolved']} "
                f"unresolvable={stats['unresolvable']} "
                f"edited={stats.get('module_edited')} "
                f"({time.time() - t0:.1f}s)"
            )
        print()
        print(
            f"TOTAL: considered={totals['considered']} "
            f"resolved={totals['resolved']} "
            f"unresolvable={totals['unresolvable']} "
            f"modules_edited={totals['modules_edited']} "
            f"skipped_locked={totals['skipped_locked']}"
        )
        if totals["considered"]:
            rate = totals["resolved"] / totals["considered"] * 100
            print(f"Auto-resolve rate: {rate:.1f}%")
        return 0

    parser.error(f"Unknown command: {args.command}")  # unreachable; argparse exits above
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
