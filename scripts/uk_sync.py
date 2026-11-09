#!/usr/bin/env python3
"""Ukrainian translation manager — detect, fix, translate, sync.

One tool for all Ukrainian translation work. Detects stale translations,
finds missing files, translates new modules, and fixes incomplete ones.
Uses agy (gemini-3.1-pro-high) for translation with Ukrainian quality verification.

Usage:
    .venv/bin/python scripts/uk_sync.py status                    # full report
    .venv/bin/python scripts/uk_sync.py status --section prereqs  # scoped
    .venv/bin/python scripts/uk_sync.py fix <uk-file>             # fix one stale file
    .venv/bin/python scripts/uk_sync.py fix-section <section>     # fix stale in section
    .venv/bin/python scripts/uk_sync.py translate <en-file>       # translate new module
    .venv/bin/python scripts/uk_sync.py translate-section <sect>  # translate all missing
    .venv/bin/python scripts/uk_sync.py e2e <section>             # full cycle
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path

os.environ["KUBEDOJO_QUIET"] = "1"  # suppress Gemini streaming to stdout

REPO_ROOT = Path(__file__).parent.parent
CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"
UK_ROOT = CONTENT_ROOT / "uk"
REPORT_FILE = REPO_ROOT / ".pipeline" / "uk-sync-report.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from checks import ukrainian


def dispatch_agy_translate(*_args, **_kwargs):
    raise RuntimeError("legacy dispatcher removed")

CHUNKED_THRESHOLD = 40_000  # chars — modules above this use section-by-section translation
BATCH_LIMIT = 15_000  # chars — pack adjacent sections into batches up to this size


# ---------------------------------------------------------------------------
# Content file discovery
# ---------------------------------------------------------------------------

def _find_content_files(root: Path, *, uk: bool = False) -> list[Path]:
    """Find module-*.md and index.md files, excluding top-level index and staging files."""
    files = set(root.glob("**/module-*.md")) | set(root.glob("**/index.md"))
    top = UK_ROOT / "index.md" if uk else CONTENT_ROOT / "index.md"
    files.discard(top)
    # Exclude staging files (e.g. module-1.2-foo.staging.md)
    files = {f for f in files if not f.name.endswith(".staging.md")}
    return sorted(files)


# ---------------------------------------------------------------------------
# Section-level hashing
# ---------------------------------------------------------------------------

def _split_sections(content: str) -> dict[str, str]:
    """Split markdown content into sections by H2 headers. Returns {heading: body}."""
    sections = {}
    current_heading = "__preamble__"
    current_lines = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_heading] = "\n".join(current_lines)

    return sections


def _hash_section(text: str) -> str:
    """Hash section content (normalized: stripped, lowered)."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _section_hashes(content: str) -> dict[str, str]:
    """Get {heading: hash} for all sections."""
    return {h: _hash_section(body) for h, body in _split_sections(content).items()}


# ---------------------------------------------------------------------------
# EN commit tracking
# ---------------------------------------------------------------------------

def _get_en_file_commit(en_path: Path) -> str:
    """Get the latest git commit hash that modified the EN file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(en_path)],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _get_uk_synced_commit(uk_content: str) -> str:
    """Extract en_commit from UK file frontmatter."""
    match = re.search(r"^en_commit:\s*(.+)$", uk_content, re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else ""


# ---------------------------------------------------------------------------
# Sync issue detection
# ---------------------------------------------------------------------------

@dataclass
class SyncIssue:
    uk_path: str
    en_path: str
    issue_type: str  # MISSING_OUTCOMES, OUTCOMES_MISMATCH, PROMPTS_MISMATCH, etc.
    severity: str    # ERROR, WARNING, INFO
    message: str
    en_value: str = ""
    uk_value: str = ""

    def __str__(self):
        icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}.get(self.severity, "?")
        return f"  {icon} [{self.issue_type}] {self.message}"


@dataclass
class SyncReport:
    uk_path: str
    en_path: str
    status: str  # "synced", "stale", "partial"
    issues: list[SyncIssue] = field(default_factory=list)
    en_commit: str = ""
    uk_synced_commit: str = ""


def _count_pattern(content: str, pattern: str) -> int:
    return len(re.findall(pattern, content, re.MULTILINE))


def detect_sync(uk_path: Path, *, strict_commit: bool = False) -> SyncReport | None:
    """Compare a UK file against its EN counterpart."""
    # Find EN equivalent
    rel = uk_path.relative_to(UK_ROOT)
    en_path = CONTENT_ROOT / rel

    if not en_path.exists():
        return None  # No EN counterpart — orphan UK file

    en_content = en_path.read_text()
    uk_content = uk_path.read_text()

    en_commit = _get_en_file_commit(en_path)
    uk_synced = _get_uk_synced_commit(uk_content)

    report = SyncReport(
        uk_path=str(uk_path.relative_to(REPO_ROOT)),
        en_path=str(en_path.relative_to(REPO_ROOT)),
        status="synced",
        en_commit=en_commit,
        uk_synced_commit=uk_synced,
    )

    # 1. Commit-based staleness check
    commit_mismatch = bool(en_commit and uk_synced and en_commit != uk_synced)

    if commit_mismatch:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "STALE_COMMIT", "WARNING",
            f"EN updated since last sync (en_commit in UK: {uk_synced[:8]}, EN HEAD: {en_commit[:8]})",
        ))
    elif not uk_synced:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "NO_SYNC_TRACKING", "INFO",
            "UK file has no en_commit in frontmatter — cannot track sync state",
        ))

    # 2. Learning outcomes
    en_outcomes = _count_pattern(en_content, r"^-\s+\*\*\w+\*\*")
    uk_outcomes = _count_pattern(uk_content, r"^-\s+\*\*\w+\*\*")
    en_has_outcomes = bool(re.search(r"##\s+(Learning Outcomes|What You.ll)", en_content))
    uk_has_outcomes = bool(re.search(r"##\s+Що ви зможете", uk_content))

    if en_has_outcomes and not uk_has_outcomes:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "MISSING_OUTCOMES", "ERROR",
            "EN has Learning Outcomes section, UK does not",
            en_value=str(en_outcomes), uk_value="0",
        ))
    elif en_outcomes != uk_outcomes and abs(en_outcomes - uk_outcomes) > 1:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "OUTCOMES_MISMATCH", "WARNING",
            f"Outcome count differs: EN={en_outcomes}, UK={uk_outcomes}",
            en_value=str(en_outcomes), uk_value=str(uk_outcomes),
        ))

    # 3. Inline prompts
    en_prompts = _count_pattern(en_content, r">\s*\*\*(Pause and predict|Stop and think|What would happen)")
    uk_prompts = _count_pattern(uk_content, r">\s*\*\*(Зупиніться|Подумайте|Pause and predict|Stop and think)")

    if en_prompts > uk_prompts + 1:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "PROMPTS_MISMATCH", "WARNING",
            f"EN has more inline prompts: EN={en_prompts}, UK={uk_prompts}",
            en_value=str(en_prompts), uk_value=str(uk_prompts),
        ))

    # 4. Quiz questions
    en_quiz = en_content.count("<details>")
    uk_quiz = uk_content.count("<details>")

    if en_quiz > uk_quiz + 2:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "QUIZ_MISMATCH", "WARNING",
            f"Quiz question count differs: EN={en_quiz}, UK={uk_quiz}",
            en_value=str(en_quiz), uk_value=str(uk_quiz),
        ))

    # 5. Section-level hashing (detect content changes)
    en_sections = set(_split_sections(en_content).keys()) - {"__preamble__"}
    uk_sections = set(_split_sections(uk_content).keys()) - {"__preamble__"}

    # Sections in EN but not UK (by structure, not exact heading match)
    en_h2_count = en_content.count("\n## ")
    uk_h2_count = uk_content.count("\n## ")

    if en_h2_count > uk_h2_count + 2:
        report.issues.append(SyncIssue(
            report.uk_path, report.en_path,
            "SECTIONS_MISMATCH", "WARNING",
            f"EN has more sections: EN={en_h2_count} H2s, UK={uk_h2_count} H2s",
            en_value=str(en_h2_count), uk_value=str(uk_h2_count),
        ))

    # 6. Size ratio (Ukrainian is typically 95-130% of English)
    en_len = len(en_content)
    uk_len = len(uk_content)
    if en_len > 0:
        ratio = uk_len / en_len
        if ratio < 0.50:
            report.issues.append(SyncIssue(
                report.uk_path, report.en_path,
                "SIZE_DRIFT", "WARNING",
                f"UK is only {ratio:.0%} of EN size ({uk_len} vs {en_len} chars) — possibly partial translation",
                en_value=str(en_len), uk_value=str(uk_len),
            ))

    # Determine overall status
    # If en_commit matches, trust it — warnings are cosmetic, not stale
    errors = [i for i in report.issues if i.severity == "ERROR"]
    commits_match = en_commit and uk_synced and en_commit == uk_synced

    if strict_commit and commit_mismatch:
        report.status = "stale"
    elif commits_match:
        report.status = "synced"
    elif errors:
        report.status = "stale"
    elif not uk_synced:
        # No tracking — can't tell, flag as stale
        report.status = "stale"
    else:
        report.status = "synced"

    return report


# ---------------------------------------------------------------------------
# Fix — translate delta using Gemini + MCP
# ---------------------------------------------------------------------------


def fix_module(
    uk_path: Path,
    report: SyncReport | None = None,
    *,
    strict_commit: bool = False,
) -> bool:
    """Fix a stale UK module by re-translating from EN."""
    rel = uk_path.relative_to(UK_ROOT)
    en_path = CONTENT_ROOT / rel

    if not en_path.exists():
        print(f"  ✗ No EN counterpart for {uk_path}")
        return False

    if report is None:
        report = detect_sync(uk_path, strict_commit=strict_commit)

    if report is None or report.status == "synced":
        print(f"  ✓ Already synced: {uk_path.name}")
        return True

    # Full re-translate from EN — backup old UK, translate fresh, remove backup on success
    print(f"  Re-translating {uk_path.name} from scratch ({len(report.issues)} issues)...")
    backup = uk_path.with_suffix(".md.bak")
    uk_path.rename(backup)
    ok = translate_new_module(en_path)
    if ok:
        backup.unlink(missing_ok=True)
    else:
        # Restore from backup on failure
        backup.rename(uk_path)
        print(f"  Restored {uk_path.name} from backup")
    return ok


# ---------------------------------------------------------------------------
# Completeness detection (merged from check_uk_completeness.py)
# ---------------------------------------------------------------------------

def find_missing_translations(section: str | None = None) -> list[Path]:
    """Find EN modules that have no UK translation file."""
    root = CONTENT_ROOT / section if section else CONTENT_ROOT
    en_modules = _find_content_files(root)
    en_modules = [m for m in en_modules if "/uk/" not in str(m)]
    missing = []
    for en in en_modules:
        rel = en.relative_to(CONTENT_ROOT)
        uk = UK_ROOT / rel
        if not uk.exists():
            missing.append(en)
    return missing


def find_untranslated_paragraphs(section: str | None = None) -> dict[Path, list[tuple[int, str]]]:
    """Find UK files with English paragraphs that should be translated."""
    root = UK_ROOT / section if section and (UK_ROOT / section).exists() else UK_ROOT
    suspect: dict[Path, list[tuple[int, str]]] = {}

    for f in sorted(root.glob("**/*.md")):
        content = f.read_text()
        lines = content.split("\n")
        en_lines: list[tuple[int, str]] = []
        in_code = False
        in_frontmatter = False
        fm_count = 0

        for i, line in enumerate(lines, 1):
            if line.strip() == "---":
                fm_count += 1
                in_frontmatter = fm_count < 2
                continue
            if in_frontmatter or in_code:
                if line.strip().startswith("```"):
                    in_code = not in_code
                continue
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "|", "<", "[", "!", ">", "-")):
                continue
            if len(stripped) < 50:
                continue
            cyrillic = len(re.findall(r"[\u0400-\u04FF]", stripped))
            latin = len(re.findall(r"[a-zA-Z]", stripped))
            total = cyrillic + latin
            if total > 30 and latin > 0 and cyrillic / max(total, 1) < 0.1:
                en_lines.append((i, stripped[:120]))

        if en_lines:
            suspect[f] = en_lines

    return suspect


# ---------------------------------------------------------------------------
# Translate new — create UK file from scratch
# ---------------------------------------------------------------------------

TRANSLATE_NEW_PROMPT = """You are a native Ukrainian senior DevOps/SRE engineer and technical writer. You write fluent, natural Ukrainian — not translationese. You translate a KubeDojo module from English to Ukrainian.

RULES:
- Translate ALL content to Ukrainian
- Keep all technical terms in English: kubectl, Kubernetes, Pod, Deployment, Service, RBAC, YAML, etc.
- Follow the glossary: cluster=кластер, container=контейнер, namespace=простір імен, node=вузол
- Translate learning outcome verbs to bold infinitive: **Налаштувати**, **Створити**, **Діагностувати**
- Translate inline prompts: "Pause and predict" → "Зупиніться та подумайте"
- Translate section headings: "Learning Outcomes" → "Що ви зможете зробити", "Why This Module Matters" → "Чому це важливо", "Common Mistakes" → "Типові помилки", "Did You Know?" → "Чи знали ви?", "Quiz" → "Контрольні запитання", "Hands-On Exercise" → "Практична вправа", "Next Module" → "Наступний модуль"
- No Russicisms (no ы, ё, ъ, э)
- Keep code blocks, YAML, and bash commands UNCHANGED
- Output length should be 95-105% of the English original
- Output the COMPLETE Ukrainian file starting with --- frontmatter

FRONTMATTER RULES:
- Translate the title to Ukrainian
- CRITICAL: The slug MUST start with "uk/" prefix. If the English slug is "prerequisites/foo", the Ukrainian slug must be "uk/prerequisites/foo". Without this prefix, the Ukrainian page will overwrite the English sidebar.
- Keep sidebar.order exactly as in English
- Add en_commit and en_file fields (provided below)

Use your MCP tools to verify Ukrainian quality:
- verify_words for VESUM validation
- query_r2u to check for Russicisms
- search_style_guide for consistency

ENGLISH SOURCE FILE ({en_path}):
{en_content}

FRONTMATTER TO USE:
en_commit: "{en_commit}"
en_file: "{en_file}"
"""


TRANSLATE_SECTION_PROMPT = """You are a native Ukrainian senior DevOps/SRE engineer and technical writer. You write fluent, natural Ukrainian — not translationese. You are translating ONE SECTION of a KubeDojo module from English to Ukrainian.

MODULE: {module_title} ({en_path})

RULES:
- Translate ALL content to Ukrainian
- Keep all technical terms in English: kubectl, Kubernetes, Pod, Deployment, Service, RBAC, YAML, etc.
- Follow the glossary: cluster=кластер, container=контейнер, namespace=простір імен, node=вузол
- Translate learning outcome verbs to bold infinitive: **Налаштувати**, **Створити**, **Діагностувати**
- Translate inline prompts: "Pause and predict" → "Зупиніться та подумайте"
- Translate section headings: "Learning Outcomes" → "Що ви зможете зробити", "Why This Module Matters" → "Чому це важливо", "Common Mistakes" → "Типові помилки", "Did You Know?" → "Чи знали ви?", "Quiz" → "Контрольні запитання", "Hands-On Exercise" → "Практична вправа", "Next Module" → "Наступний модуль"
- No Russicisms (no ы, ё, ъ, э)
- Keep code blocks, YAML, and bash commands UNCHANGED
- Output length should be 95-105% of the English original

OUTPUT FORMAT:
- Output ONLY the translated section heading (## ...) followed by the translated body
- Do NOT wrap in markdown fences
- Do NOT add frontmatter or extra sections

Use your MCP tools to verify Ukrainian quality:
- verify_words for VESUM validation
- query_r2u to check for Russicisms

SECTION TO TRANSLATE:
{section_heading}
{section_body}
"""


def _strip_markdown_fence(output: str) -> str:
    """Remove markdown code block wrapper if present."""
    if output.startswith("```"):
        lines = output.split("\n")
        if lines[-1].strip() == "```":
            return "\n".join(lines[1:-1])
    return output


def _build_batches(sections: dict[str, str]) -> list[list[str]]:
    """Pack H2 sections into batches up to BATCH_LIMIT chars. Skips __preamble__ and first H2."""
    keys = list(sections.keys())
    # Start from index 2 (skip preamble + first H2, which are handled separately)
    start = 2 if keys[0] == "__preamble__" else 1
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_size = 0

    for key in keys[start:]:
        section_size = len(key) + len(sections[key]) + 1
        if current_batch and current_size + section_size > BATCH_LIMIT:
            batches.append(current_batch)
            current_batch = [key]
            current_size = section_size
        else:
            current_batch.append(key)
            current_size += section_size

    if current_batch:
        batches.append(current_batch)

    return batches


def _translate_chunked(en_path: Path, en_content: str, en_commit: str, en_file: str) -> str | None:
    """Translate a large module in batches. Returns assembled output or None."""
    rel = en_path.relative_to(CONTENT_ROOT)
    sections = _split_sections(en_content)
    keys = list(sections.keys())

    if len(keys) < 2:
        return None

    # Extract module title from frontmatter for context
    import yaml
    fm_parts = en_content.split("---", 2)
    try:
        fm = yaml.safe_load(fm_parts[1]) if len(fm_parts) >= 3 else {}
        module_title = fm.get("title", rel.stem) if isinstance(fm, dict) else rel.stem
    except Exception:
        module_title = rel.stem

    # Build batches from remaining sections (after preamble + first H2)
    batches = _build_batches(sections)
    total_batches = 1 + len(batches)  # 1 for preamble batch
    print(f"  Chunked translation: {len(keys)} sections → {total_batches} batches")

    translated_parts: list[str] = []

    # --- Batch 1: Preamble + first H2 (handles frontmatter) ---
    preamble = sections.get("__preamble__", "")
    first_h2 = keys[1] if len(keys) > 1 and keys[0] == "__preamble__" else keys[0]
    merged_content = preamble + "\n\n" + first_h2 + "\n" + sections[first_h2]

    prompt = TRANSLATE_NEW_PROMPT.format(
        en_path=rel,
        en_content=merged_content,
        en_commit=en_commit,
        en_file=en_file,
    )
    print(f"    [1/{total_batches}] Preamble + {first_h2[:40]} ({len(merged_content)} chars)...")
    ok, output = dispatch_agy_translate(prompt, timeout=600)

    if not ok or not output.strip():
        print("    ✗ Preamble translation failed")
        return None

    output = _strip_markdown_fence(output)

    # Find frontmatter start
    if not output.startswith("---"):
        fm_start = output.find("---\n")
        if fm_start > 0 and fm_start < 2000:
            output = output[fm_start:]
        else:
            print("    ✗ Preamble output has no frontmatter")
            return None

    # Validate frontmatter
    parts = output.split("---", 2)
    if len(parts) < 3:
        print("    ✗ Malformed frontmatter — no closing ---")
        return None
    try:
        fm_parsed = yaml.safe_load(parts[1])
        if not isinstance(fm_parsed, dict) or "title" not in fm_parsed:
            print("    ✗ Frontmatter missing 'title' field")
            return None
    except Exception as e:
        print(f"    ✗ Broken YAML frontmatter: {e}")
        return None

    # Fix slug
    slug = fm_parsed.get("slug", "")
    if slug and not slug.startswith("uk/"):
        output = re.sub(r'^slug:\s*.+$', f'slug: uk/{slug}', output, count=1, flags=re.MULTILINE)

    # Ensure en_commit
    if en_commit and "en_commit:" not in output:
        output = output.replace("\n---\n", f'\nen_commit: "{en_commit}"\nen_file: "{en_file}"\n---\n', 1)

    # Truncation guard for preamble batch
    if len(output) < len(merged_content) * 0.70:
        print(f"    ✗ Preamble truncated: {len(output)} vs {len(merged_content)} EN")
        return None

    translated_parts.append(output)

    # --- Remaining batches ---
    for batch_idx, batch_keys in enumerate(batches, 2):
        # Assemble batch content: heading + body for each section
        batch_content = "\n\n".join(
            key + "\n" + sections[key] for key in batch_keys
        )
        batch_headings = " + ".join(k[:30] for k in batch_keys)
        print(f"    [{batch_idx}/{total_batches}] {batch_headings} ({len(batch_content)} chars)...")

        prompt = TRANSLATE_SECTION_PROMPT.format(
            module_title=module_title,
            en_path=rel,
            section_heading=batch_keys[0],  # first heading for context
            section_body=batch_content,  # full batch content
        )
        ok, output = dispatch_agy_translate(prompt, timeout=300)

        if not ok or not output.strip():
            print(f"    ✗ Batch failed: {batch_headings} — aborting module")
            return None

        output = _strip_markdown_fence(output)

        # Truncation guard per batch
        if len(output) < len(batch_content) * 0.70:
            print(f"    ⚠ Batch possibly truncated: {len(output)} vs {len(batch_content)} EN ({len(output)/max(len(batch_content),1):.0%})")

        translated_parts.append(output)

    return "\n\n".join(translated_parts)


def translate_new_module(en_path: Path) -> bool:
    """Create a new UK translation from an EN module."""
    rel = en_path.relative_to(CONTENT_ROOT)
    uk_path = UK_ROOT / rel

    if uk_path.exists():
        print(f"  ✗ UK file already exists: {uk_path}")
        print(f"    Use 'fix' to update it, or delete it first")
        return False

    en_content = en_path.read_text()
    en_commit = _get_en_file_commit(en_path)
    en_file = f"src/content/docs/{rel}"

    print(f"  Translating: {rel}")

    # Large modules: translate section-by-section
    if len(en_content) > CHUNKED_THRESHOLD:
        output = _translate_chunked(en_path, en_content, en_commit, en_file)
        if output is None:
            print("  ✗ Chunked translation failed")
            return False
    else:
        # Standard single-call translation
        prompt = TRANSLATE_NEW_PROMPT.format(
            en_path=rel,
            en_content=en_content,
            en_commit=en_commit,
            en_file=en_file,
        )

        ok, output = dispatch_agy_translate(prompt, timeout=600)

        if not ok or not output.strip():
            print(f"  ✗ Translation failed")
            return False

        # Strip markdown wrapper
        output = _strip_markdown_fence(output)

        # Check if output is actual markdown or just a summary
        if not output.startswith("---"):
            fm_start = output.find("---\n")
            if fm_start > 0 and fm_start < 2000:
                output = output[fm_start:]
            else:
                # Gemini may have written to the file directly via tool use
                if uk_path.exists():
                    uk_now = uk_path.read_text()
                    if uk_now.startswith("---"):
                        print(f"  ✓ Gemini wrote directly to {uk_path.name}")
                        output = uk_now
                    else:
                        print(f"  ✗ Output has no frontmatter")
                        return False
                else:
                    print(f"  ✗ Output has no frontmatter")
                    return False

        # Validate YAML frontmatter
        parts = output.split("---", 2)
        if len(parts) < 3:
            print(f"  ✗ Malformed frontmatter — no closing ---")
            return False
        try:
            import yaml
            fm = yaml.safe_load(parts[1])
            if not isinstance(fm, dict) or "title" not in fm:
                print(f"  ✗ Frontmatter missing 'title' field")
                return False
        except Exception as e:
            print(f"  ✗ Broken YAML frontmatter: {e}")
            return False

        # Fix slug: must have uk/ prefix
        slug = fm.get("slug", "")
        if slug and not slug.startswith("uk/"):
            output = re.sub(r'^slug:\s*.+$', f'slug: uk/{slug}', output, count=1, flags=re.MULTILINE)
            print(f"  Fixed slug: {slug} → uk/{slug}")

        # Ensure en_commit is present
        if en_commit and "en_commit:" not in output:
            output = output.replace("\n---\n", f'\nen_commit: "{en_commit}"\nen_file: "{en_file}"\n---\n', 1)

    # Truncation guard (applies to both paths)
    if len(output) < len(en_content) * 0.70:
        print(f"  ✗ Output truncated: {len(output)} chars vs {len(en_content)} EN ({len(output)/len(en_content):.0%})")
        return False

    # Verify Ukrainian quality
    check_results = ukrainian.run_all(output, uk_path)
    check_errors = [r for r in check_results if not r.passed and r.severity == "ERROR"]
    if check_errors:
        print(f"  ⚠ Ukrainian quality issues:")
        for r in check_errors:
            print(f"    {r}")

    # Create directory and write
    uk_path.parent.mkdir(parents=True, exist_ok=True)
    uk_path.write_text(output)
    print(f"  ✓ Created {uk_path} ({len(output)} chars, en_commit: {en_commit[:8]})")
    return True


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Combined status: stale translations + missing files + incomplete translations."""
    section = args.section

    # 1. Stale (existing UK files out of sync with EN)
    uk_dir = UK_ROOT / section if section and (UK_ROOT / section).exists() else UK_ROOT
    uk_files = _find_content_files(uk_dir, uk=True)
    stale_count = 0
    for uk_path in uk_files:
        report = detect_sync(uk_path, strict_commit=args.strict_commit)
        if report and report.status != "synced":
            stale_count += 1

    # 2. Missing (EN modules with no UK file)
    missing = find_missing_translations(section)

    # 3. Incomplete (UK files with English paragraphs)
    incomplete = find_untranslated_paragraphs(section)
    incomplete_lines = sum(len(v) for v in incomplete.values())

    # Group missing by track
    tracks: dict[str, int] = {}
    for en in missing:
        rel = str(en.relative_to(CONTENT_ROOT))
        track = rel.split("/")[0]
        tracks[track] = tracks.get(track, 0) + 1

    print(f"\n{'='*60}")
    print(f"  Ukrainian Translation Status{f' ({section})' if section else ''}")
    print(f"{'='*60}")
    print(f"  UK files: {len(uk_files)} | Stale: {stale_count} | Missing: {len(missing)} | Incomplete: {len(incomplete)} ({incomplete_lines} lines)")
    print()

    if missing:
        print(f"  Missing translations ({len(missing)} files):")
        for track, count in sorted(tracks.items()):
            print(f"    {track}: {count}")
        print()

    if incomplete:
        print(f"  Incomplete translations ({len(incomplete)} files, {incomplete_lines} English lines):")
        for f, lines in sorted(incomplete.items())[:10]:
            rel = str(f.relative_to(UK_ROOT))
            print(f"    {rel} ({len(lines)} lines)")
        if len(incomplete) > 10:
            print(f"    ... +{len(incomplete) - 10} more")
        print()

    if stale_count:
        print(f"  Stale translations: {stale_count} files (run 'detect' for details)")

    total_work = len(missing) + len(incomplete) + stale_count
    print(f"\n  Total work: {total_work} items")


def cmd_detect(args):
    """Detect out-of-sync Ukrainian modules."""
    if args.section:
        uk_dir = UK_ROOT / args.section
    else:
        uk_dir = UK_ROOT

    if not uk_dir.exists():
        print(f"Directory not found: {uk_dir}")
        sys.exit(1)

    uk_files = _find_content_files(uk_dir, uk=True)
    print(f"Checking {len(uk_files)} Ukrainian files...")

    reports = []
    synced = 0
    stale = 0
    errors_total = 0
    warnings_total = 0

    for uk_path in uk_files:
        report = detect_sync(uk_path, strict_commit=args.strict_commit)
        if report is None:
            continue

        reports.append(report)

        if report.status == "synced":
            synced += 1
        else:
            stale += 1
            errors = [i for i in report.issues if i.severity == "ERROR"]
            warnings = [i for i in report.issues if i.severity == "WARNING"]
            errors_total += len(errors)
            warnings_total += len(warnings)

            if not args.json:
                short_path = report.uk_path.replace("src/content/docs/uk/", "")
                print(f"\n  {short_path}:")
                for issue in report.issues:
                    print(f"  {issue}")

    # Summary
    if not args.json:
        print(f"\n{'='*60}")
        print(f"  Synced: {synced} | Stale: {stale} | Errors: {errors_total} | Warnings: {warnings_total}")
        print(f"{'='*60}")

    # Persist report
    report_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": {
            "total": len(reports),
            "synced": synced,
            "stale": stale,
            "errors": errors_total,
            "warnings": warnings_total,
        },
        "modules": {
            r.uk_path: {
                "status": r.status,
                "en_commit": r.en_commit,
                "uk_synced_commit": r.uk_synced_commit,
                "issues": [
                    {"type": i.issue_type, "severity": i.severity, "message": i.message,
                     "en_value": i.en_value, "uk_value": i.uk_value}
                    for i in r.issues
                ],
            }
            for r in reports if r.issues
        },
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    print(f"\nReport saved to {REPORT_FILE}")

    if args.json:
        print(json.dumps(report_data, indent=2, ensure_ascii=False))

    sys.exit(1 if errors_total > 0 else 0)


def cmd_fix(args):
    """Fix a single stale UK module."""
    uk_path = Path(args.file).resolve()
    if not uk_path.exists():
        uk_path = (UK_ROOT / args.file).resolve()
    if not uk_path.exists():
        uk_path = (UK_ROOT / f"{args.file}.md").resolve()
    if not uk_path.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    ok = fix_module(uk_path, strict_commit=args.strict_commit)
    sys.exit(0 if ok else 1)


def cmd_fix_section(args):
    """Fix all stale UK modules in a section."""
    uk_dir = UK_ROOT / args.section
    if not uk_dir.exists():
        print(f"Section not found: {args.section}")
        sys.exit(1)

    uk_files = _find_content_files(uk_dir, uk=True)
    print(f"Checking {len(uk_files)} files in {args.section}...")

    fixed = 0
    skipped = 0
    failed = 0

    for uk_path in uk_files:
        report = detect_sync(uk_path, strict_commit=args.strict_commit)
        if report is None or report.status == "synced":
            skipped += 1
            continue

        print(f"\n  Fixing: {uk_path.name} ({len(report.issues)} issues)")
        ok = fix_module(uk_path, report, strict_commit=args.strict_commit)
        if ok:
            fixed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Fixed: {fixed} | Skipped (synced): {skipped} | Failed: {failed}")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


def cmd_translate(args):
    """Translate a single EN module to Ukrainian."""
    en_path = Path(args.file).resolve()
    if not en_path.exists():
        en_path = (CONTENT_ROOT / args.file).resolve()
    if not en_path.exists():
        en_path = (CONTENT_ROOT / f"{args.file}.md").resolve()
    if not en_path.exists():
        print(f"EN file not found: {args.file}")
        sys.exit(1)

    ok = translate_new_module(en_path)
    sys.exit(0 if ok else 1)


def cmd_translate_section(args):
    """Translate all missing UK modules in a section."""
    missing = find_missing_translations(args.section)
    if not missing:
        print(f"  No missing translations in {args.section}")
        return

    print(f"  Translating {len(missing)} missing modules in {args.section}...")

    translated = 0
    failed = 0
    consecutive_failures = 0

    for en_path in missing:
        ok = translate_new_module(en_path)
        if ok:
            translated += 1
            consecutive_failures = 0
        else:
            failed += 1
            consecutive_failures += 1

        if consecutive_failures >= 3:
            print(f"\n  CIRCUIT BREAKER: 3 consecutive translation failures — halting")
            break

    print(f"\n  Translated: {translated} | Failed: {failed} | Remaining: {len(missing) - translated - failed}")
    sys.exit(0 if failed == 0 else 1)


# ---------------------------------------------------------------------------
# Track aliases (same pattern as v1_pipeline.py)
# ---------------------------------------------------------------------------

TRACK_ALIASES = {
    "prereqs": [
        "prerequisites/zero-to-terminal", "prerequisites/git-deep-dive",
        "prerequisites/cloud-native-101", "prerequisites/kubernetes-basics",
        "prerequisites/philosophy-design", "prerequisites/modern-devops",
    ],
    "certs": [
        "k8s/cka", "k8s/ckad", "k8s/cks", "k8s/kcna", "k8s/kcsa",
    ],
    "cloud": [
        "cloud/aws-essentials", "cloud/gcp-essentials", "cloud/azure-essentials",
        "cloud/architecture-patterns", "cloud/eks-deep-dive", "cloud/gke-deep-dive",
        "cloud/aks-deep-dive", "cloud/advanced-operations", "cloud/managed-services",
        "cloud/enterprise-hybrid",
    ],
    "linux": [
        "linux/foundations/container-primitives", "linux/foundations/networking",
        "linux/foundations/system-essentials", "linux/foundations/everyday-use",
        "linux/operations", "linux/security",
    ],
    "platform": [
        "platform/foundations", "platform/disciplines", "platform/toolkits",
    ],
    "on-prem": [
        "on-premises/planning", "on-premises/provisioning", "on-premises/networking",
        "on-premises/storage", "on-premises/multi-cluster", "on-premises/security",
        "on-premises/operations", "on-premises/resilience",
    ],
}


def _expand_sections(sections: list[str]) -> list[str]:
    """Expand track aliases to section paths."""
    expanded: list[str] = []
    for s in sections:
        if s in TRACK_ALIASES:
            expanded.extend(TRACK_ALIASES[s])
        else:
            expanded.append(s)
    return expanded


def _run_e2e_section(section: str, *, strict_commit: bool = False) -> tuple[int, int, int]:
    """Run e2e on one section. Returns (fixed, translated, failed)."""
    print(f"\n{'='*60}")
    print(f"  UK Translation: {section}")
    print(f"{'='*60}")

    fixed = 0
    translated = 0
    failed = 0
    consecutive_failures = 0

    # Phase 1: Fix stale (re-translate out-of-sync UK files)
    uk_dir = UK_ROOT / section if (UK_ROOT / section).exists() else None
    if uk_dir:
        uk_files = _find_content_files(uk_dir, uk=True)
        for uk_path in uk_files:
            report = detect_sync(uk_path, strict_commit=strict_commit)
            if report and report.status != "synced":
                print(f"\n  Re-translating stale: {uk_path.name}")
                if fix_module(uk_path, report, strict_commit=strict_commit):
                    fixed += 1
                    consecutive_failures = 0
                else:
                    failed += 1
                    consecutive_failures += 1
                if consecutive_failures >= 3:
                    print(f"\n  CIRCUIT BREAKER: 3 consecutive failures — halting section")
                    return fixed, translated, failed

    # Phase 2: Translate missing (EN modules with no UK file)
    missing = find_missing_translations(section)
    for en_path in missing:
        ok = translate_new_module(en_path)
        if ok:
            translated += 1
            consecutive_failures = 0
        else:
            failed += 1
            consecutive_failures += 1
        if consecutive_failures >= 3:
            print(f"\n  CIRCUIT BREAKER: 3 consecutive failures — halting section")
            break

    print(f"\n  {section}: {fixed} re-translated, {translated} new, {failed} failed")
    return fixed, translated, failed


def cmd_e2e(args):
    """Full translation cycle: fix stale → translate missing → verify."""
    sections = _expand_sections(args.sections) if args.sections else _expand_sections(["prereqs", "certs", "cloud", "linux", "platform", "on-prem"])

    total_fixed = 0
    total_translated = 0
    total_failed = 0

    for section in sections:
        if not (CONTENT_ROOT / section).exists():
            continue
        fixed, translated, failed = _run_e2e_section(section, strict_commit=args.strict_commit)
        total_fixed += fixed
        total_translated += translated
        total_failed += failed

    # Verify
    print(f"\n{'='*60}")
    print(f"  VERIFY")
    print(f"{'='*60}")
    for section in sections:
        incomplete = find_untranslated_paragraphs(section)
        if incomplete:
            print(f"  {section}: {len(incomplete)} files with English content")
        else:
            print(f"  {section}: clean")

    print(f"\n{'='*60}")
    print(f"  E2E COMPLETE: {total_fixed} re-translated, {total_translated} new, {total_failed} failed")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Ukrainian translation manager — detect, fix, translate, sync",
        epilog="""commands:
  status                           combined report: missing + stale + incomplete
  detect                           detailed stale detection with section hashing
  fix <uk-file>                    fix one stale UK file via Gemini+MCP
  fix-section <section>            fix all stale in section
  translate <en-file>              create new UK translation from EN module
  translate-section <section>      translate all missing UK files in section
  e2e <section>                    full cycle: fix stale → translate new → verify

examples:
  uk_sync.py status --section prerequisites
  uk_sync.py fix-section k8s/cka
  uk_sync.py translate src/content/docs/prerequisites/zero-to-terminal/module-0.6-git-basics.md
  uk_sync.py translate-section prerequisites
  uk_sync.py e2e prerequisites
""", formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # status
    stp = subparsers.add_parser("status", help="Combined translation status report")
    stp.add_argument("--section", help="Limit to section (e.g., prerequisites, k8s/cka)")
    stp.add_argument("--strict-commit", action="store_true", help="Treat en_commit mismatch as stale")

    # detect
    dp = subparsers.add_parser("detect", help="Detailed stale detection with section hashing")
    dp.add_argument("--section", help="Limit to section (e.g., k8s/cka)")
    dp.add_argument("--json", action="store_true", help="Output as JSON")
    dp.add_argument("--strict-commit", action="store_true", help="Treat en_commit mismatch as stale")

    # fix
    fp = subparsers.add_parser("fix", help="Fix a single stale UK module")
    fp.add_argument("file", help="UK file path")
    fp.add_argument("--strict-commit", action="store_true", help="Treat en_commit mismatch as stale")

    # fix-section
    fsp = subparsers.add_parser("fix-section", help="Fix all stale UK modules in a section")
    fsp.add_argument("section", help="Section path (e.g., k8s/cka)")
    fsp.add_argument("--strict-commit", action="store_true", help="Treat en_commit mismatch as stale")

    # translate
    tp = subparsers.add_parser("translate", help="Create new UK translation from EN module")
    tp.add_argument("file", help="EN file path")

    # translate-section
    tsp = subparsers.add_parser("translate-section", help="Translate all missing UK files in section")
    tsp.add_argument("section", help="Section path (e.g., prerequisites)")

    # e2e
    ep = subparsers.add_parser("e2e", help="Full cycle: fix stale → translate new → verify",
        epilog="""track aliases:
  prereqs    zero-to-terminal, git-deep-dive, cloud-native-101, k8s-basics, philosophy, modern-devops
  certs      cka, ckad, cks, kcna, kcsa
  cloud      aws, gcp, azure, etc.
  linux      container-primitives, networking, system-essentials, everyday-use, operations, security
  platform   foundations, disciplines, toolkits
  on-prem    planning, provisioning, networking, storage, etc.

examples:
  e2e prereqs                      all prerequisites
  e2e prereqs certs                prereqs + certs
  e2e prerequisites/kubernetes-basics  single section
  e2e                              everything

safe to re-run: skips synced files, skips existing UK files
""", formatter_class=argparse.RawDescriptionHelpFormatter)
    ep.add_argument("sections", nargs="*", help="track aliases or section paths (default: all)")
    ep.add_argument("--strict-commit", action="store_true", help="Treat en_commit mismatch as stale")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        "status": cmd_status,
        "detect": cmd_detect,
        "fix": cmd_fix,
        "fix-section": cmd_fix_section,
        "translate": cmd_translate,
        "translate-section": cmd_translate_section,
        "e2e": cmd_e2e,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
