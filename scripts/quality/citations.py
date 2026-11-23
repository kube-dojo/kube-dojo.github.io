"""Citation verify-or-remove — strict "we don't publish lies" policy.

For every URL in a module's ``## Sources`` section:

1. Fetch the page with Lightpanda (``lightpanda fetch --dump markdown
   --strip-mode full``, 30s timeout).
2. Send the page + the claim to an LLM verifier (Gemini-flash by default).
3. **Keep** the entry ONLY on a clear ``supports`` verdict.
4. **Remove** on anything else — ``partial``, ``no``, fetch failed, 404,
   timeout, or verifier error. Burden of proof is on keeping.
5. If the ``## Sources`` section is empty after removal, drop the
   heading too.

See the policy memo at ``docs/sessions/2026-04-24-quality-pipeline-redesign.md``
(section "Citation verify-or-remove details") and the feedback memory
``feedback_citation_verify_or_remove.md``. The strict rule is
user-confirmed and applies uniformly: existing citations, writer-added
citations, and the 189 findings in ``.pipeline/v3/human-review/`` all
go through the same filter.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from .dispatchers import DispatchResult, dispatch
from .extractors import JsonExtractError, extract_last_json
from .prompts import citation_verify_prompt


LIGHTPANDA_BIN = "lightpanda"
"""Expected on ``PATH``. Homebrew installs at ``/opt/homebrew/bin/lightpanda``."""

LIGHTPANDA_FETCH_TIMEOUT = 30
"""Seconds. Tight because we're fetching ~40 URLs per module and bad
pages should fail fast, not stretch the pipeline."""


class CitationVerdict(str, Enum):
    """Verifier outcome. Only ``SUPPORTS`` keeps the entry."""

    SUPPORTS = "supports"
    PARTIAL = "partial"
    NO = "no"
    FETCH_FAILED = "fetch_failed"  # distinct from NO for logging / post-mortem
    VERIFIER_ERROR = "verifier_error"  # dispatch or JSON parse failed


@dataclass(frozen=True)
class SourceEntry:
    """One bullet from the ``## Sources`` section.

    Parsing handles ``- [Title](url) — claim description`` and the two
    no-description variants: ``- [Title](url)`` and ``- <url>``. When no
    trailing claim is present, :attr:`claim` falls back to the title (or
    the URL when even that is missing).
    """

    raw_line: str
    url: str
    title: str
    claim: str


@dataclass
class ProcessedCitation:
    """Per-URL outcome of the verify pass. ``reasoning`` is kept for logs."""

    entry: SourceEntry
    verdict: CitationVerdict
    reasoning: str = ""
    excerpt: str = ""


@dataclass
class CitationResult:
    """Result of processing a module's citations.

    ``new_text`` is always populated — when nothing changed it equals the
    input text exactly (lets callers no-op commit skip).
    """

    kept: list[ProcessedCitation] = field(default_factory=list)
    removed: list[ProcessedCitation] = field(default_factory=list)
    new_text: str = ""
    had_sources_section: bool = False
    section_dropped: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.removed) or self.section_dropped


# ---- Sources section parser --------------------------------------------


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_BULLET_RE = re.compile(
    r"""
    ^\s*(?:[-*]\s+|\d+\.\s+)  # bullet dash/asterisk or numbered list
    (?:
      \[(?P<text>[^\]]+)\]  # [Title]
      \(\s*<?(?P<url>https?://[^>\s)]+?)>?\s*\)  # (url), tolerate <url> wrap
      (?:\s*[—–-]\s*(?P<claim>.+))?  # — claim
      |
      <?(?P<bare>https?://[^>\s]+)>?  # bare url, no markdown link
      (?:\s*[—–-]\s*(?P<bareclaim>.+))?
    )
    \s*$
    """,
    re.VERBOSE,
)


def _is_sources_heading(line: str) -> bool:
    m = _HEADING_RE.match(line)
    if not m:
        return False
    return m.group(1).strip().lower() in ("sources", "references", "further reading")


def _is_any_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line))


def parse_sources_section(
    text: str,
) -> tuple[int, int, list[SourceEntry]] | None:
    """Return ``(start_line, end_line, entries)`` or ``None`` if no section.

    * ``start_line`` — index of the ``## Sources`` heading line
    * ``end_line`` — exclusive; index of the NEXT heading line or
      ``len(lines)`` if the section runs to EOF
    * ``entries`` — one :class:`SourceEntry` per parseable bullet; lines
      inside the section that don't match the bullet regex are preserved
      in the output unchanged (see :func:`rebuild_section`)
    """
    lines = text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if _is_sources_heading(line):
            start = i
            break
    if start < 0:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _is_any_heading(lines[j]):
            end = j
            break

    entries: list[SourceEntry] = []
    for line in lines[start + 1 : end]:
        entry = _parse_bullet(line)
        if entry:
            entries.append(entry)
    return start, end, entries


def _parse_bullet(line: str) -> SourceEntry | None:
    m = _BULLET_RE.match(line)
    if not m:
        return None
    url = m.group("url") or m.group("bare") or ""
    if not url:
        return None
    title = (m.group("text") or url).strip()
    claim = (m.group("claim") or m.group("bareclaim") or "").strip()
    if not claim:
        claim = title
    return SourceEntry(raw_line=line, url=url, title=title, claim=claim)


# ---- Lightpanda fetch ---------------------------------------------------


def fetch_page(url: str, *, timeout: int = LIGHTPANDA_FETCH_TIMEOUT) -> str | None:
    """Fetch ``url`` via Lightpanda and return the markdown dump.

    Returns ``None`` on any failure — network error, timeout, non-zero
    exit, missing binary. The strict-remove policy treats ``None`` as
    ``FETCH_FAILED`` which falls under "remove", so no need to
    distinguish failure reasons upstream beyond logs.
    """
    cmd = [
        LIGHTPANDA_BIN,
        "fetch",
        "--dump",
        "markdown",
        "--strip-mode",
        "full",
        url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    return out


# ---- LLM verify ---------------------------------------------------------


VerifierDispatch = Callable[[str], DispatchResult]
"""Callable that takes a prompt and returns a :class:`DispatchResult`.

Abstraction boundary exists so tests can inject a canned verifier
without spawning subprocesses. Production uses :func:`default_verifier`.
"""


def default_verifier(prompt: str) -> DispatchResult:
    """Production verifier — agy flash (Google lane), short per-URL timeout.

    gemini-cli is retired (#2125); the flash-tier review model on the agy lane
    is gemini-4-hydrogen-medium."""
    return dispatch("agy", prompt, timeout=60, model="gemini-4-hydrogen-medium")


def verify_citation(
    entry: SourceEntry,
    *,
    verifier: VerifierDispatch = default_verifier,
    fetcher: Callable[[str], str | None] = fetch_page,
) -> ProcessedCitation:
    """Fetch + verify a single source entry. Always returns a verdict.

    Never raises — any failure collapses to ``FETCH_FAILED`` or
    ``VERIFIER_ERROR``, both of which remove the entry. This keeps the
    caller loop simple: every entry gets a verdict, no exception
    handling.
    """
    page = fetcher(entry.url)
    if page is None:
        return ProcessedCitation(
            entry=entry,
            verdict=CitationVerdict.FETCH_FAILED,
            reasoning="lightpanda fetch failed or returned empty",
        )

    prompt = citation_verify_prompt(page_content=page, claim=entry.claim, url=entry.url)
    try:
        result = verifier(prompt)
    except Exception as exc:  # DispatcherUnavailable or unexpected — log as error
        return ProcessedCitation(
            entry=entry,
            verdict=CitationVerdict.VERIFIER_ERROR,
            reasoning=f"verifier dispatch raised: {exc}",
        )
    if not result.ok:
        return ProcessedCitation(
            entry=entry,
            verdict=CitationVerdict.VERIFIER_ERROR,
            reasoning=f"verifier returned non-zero: {result.stderr.strip()[:200]}",
        )

    try:
        payload = extract_last_json(result.stdout, required_keys={"verdict"})
    except JsonExtractError as exc:
        return ProcessedCitation(
            entry=entry,
            verdict=CitationVerdict.VERIFIER_ERROR,
            reasoning=f"no valid JSON verdict: {exc}",
        )

    raw_verdict = str(payload.get("verdict", "")).strip().lower()
    try:
        verdict = CitationVerdict(raw_verdict)
    except ValueError:
        return ProcessedCitation(
            entry=entry,
            verdict=CitationVerdict.VERIFIER_ERROR,
            reasoning=f"unknown verdict value: {raw_verdict!r}",
        )

    return ProcessedCitation(
        entry=entry,
        verdict=verdict,
        reasoning=str(payload.get("reasoning", "")).strip(),
        excerpt=str(payload.get("excerpt", "")).strip(),
    )


# ---- Module-level rewrite ----------------------------------------------


_URL_RE = re.compile(r"https?://\S+")


def rebuild_section(
    text: str,
    start: int,
    end: int,
    kept_entries: list[SourceEntry],
) -> tuple[str, bool]:
    """Return ``(new_text, section_dropped)`` after filtering entries.

    Strict-policy reconstruction (Codex must #6):

    * If ``kept_entries`` is empty, the whole ``## Sources`` section is
      removed — heading, content, and any leading blank-line padding.
      The section is also dropped when it contains zero bullets we
      could parse AND any URL is present somewhere — those URLs weren't
      verified, so they can't stay.
    * Non-bullet lines inside the section are preserved ONLY if they
      contain no URL. A line like "See https://... for details" that
      our parser missed is treated as a bypass attempt and removed —
      the strict policy says every URL in ``## Sources`` must be
      bullet-shaped AND verified, no exceptions.
    """
    lines = text.splitlines(keepends=True)

    if not kept_entries:
        # Drop the entire section and trim one leading blank line if it
        # existed as padding before the heading.
        cut_start = start
        if cut_start > 0 and lines[cut_start - 1].strip() == "":
            cut_start -= 1
        new_lines = lines[:cut_start] + lines[end:]
        return "".join(new_lines), True

    # Reconstruct with kept entries only. Drop ANY non-bullet line that
    # contains a URL — our parser missed it, so it's unverified.
    kept = Counter((entry.url, entry.claim, entry.raw_line) for entry in kept_entries)
    rebuilt: list[str] = [lines[start]]  # heading line
    for line in lines[start + 1 : end]:
        parsed = _parse_bullet(line.rstrip("\n"))
        if parsed is None:
            if _URL_RE.search(line):
                continue  # unverified URL in a non-bullet — drop
            rebuilt.append(line)  # pure prose / blank — preserve
            continue
        key = (parsed.url, parsed.claim, parsed.raw_line)
        if kept.get(key, 0) > 0:
            rebuilt.append(line)
            kept[key] -= 1
        # else: drop this bullet
    new_lines = lines[:start] + rebuilt + lines[end:]
    return "".join(new_lines), False


def process_module_citations(
    module_path: Path,
    *,
    verifier: VerifierDispatch = default_verifier,
    fetcher: Callable[[str], str | None] = fetch_page,
) -> CitationResult:
    """Run the full verify-or-remove pass against one module file.

    Does NOT write the module to disk — returns :attr:`CitationResult.new_text`
    and lets the caller decide the commit path (worktree write + commit
    with a dedicated ``citation-cleanup-only`` message).
    """
    text = module_path.read_text(encoding="utf-8")
    parsed = parse_sources_section(text)
    if parsed is None:
        return CitationResult(new_text=text, had_sources_section=False)

    start, end, entries = parsed
    result = CitationResult(had_sources_section=True)

    if not entries:
        # No parseable bullets found — either the section is pure prose
        # with no sources, or it contains URL lines our parser missed.
        # Strict policy (Codex must #6): any URL in the section that
        # wasn't parsed as a bullet is unverifiable, so the whole
        # section must go. Drop the section entirely.
        section_text = "\n".join(text.splitlines()[start:end])
        has_url = bool(_URL_RE.search(section_text))
        if has_url:
            new_text, dropped = rebuild_section(text, start, end, kept_entries=[])
            result.new_text = new_text
            result.section_dropped = dropped
        else:
            # Pure prose — a conservative no-op is fine. A later prompt
            # can remove empty Sources headings if we want to; for now
            # leave alone.
            result.new_text = text
        return result

    for entry in entries:
        processed = verify_citation(entry, verifier=verifier, fetcher=fetcher)
        if processed.verdict == CitationVerdict.SUPPORTS:
            result.kept.append(processed)
        else:
            result.removed.append(processed)

    kept_entries = [p.entry for p in result.kept]
    result.new_text, result.section_dropped = rebuild_section(text, start, end, kept_entries)
    return result
