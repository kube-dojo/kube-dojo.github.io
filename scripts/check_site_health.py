#!/usr/bin/env python3
"""KubeDojo Site Health Check — validates content integrity for Starlight (Astro).

Checks:
  1. Frontmatter (title, sidebar.order)
  2. Slug fields for dotted filenames
  3. Internal link targets exist
  4. No .md extension in internal links
  5. No README.md files
  6. Ukrainian file placement
  7. Module count vs STATUS.md
  8. Index files reference their child modules
  9. Module naming consistency (X.Y format)
  10. Empty directories
  11. Sidebar config references valid directories
  12. No orphaned modules (every module dir has index.md)
  13. Title matches filename numbering
  14. Static absolute internal link targets
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "src" / "content" / "docs"
PAGES_DIR = REPO_ROOT / "src" / "pages"
CONFIG_FILE = REPO_ROOT / "astro.config.mjs"
ABSOLUTE_INTERNAL_LINK_RE = re.compile(r'\]\((/[A-Za-z0-9\-_/\.]+/?)\)')


@dataclass
class _Results:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_files: int | None = None
    module_count: int | None = None
    links_checked: int | None = None


_results = _Results()


def _is_ignored_content_file(path: Path) -> bool:
    return path.name.endswith(".staging.md")


def _iter_markdown_files():
    for md in DOCS_DIR.rglob("*.md"):
        if not _is_ignored_content_file(md):
            yield md


def _iter_module_files():
    for md in DOCS_DIR.rglob("module-*.md"):
        if not _is_ignored_content_file(md):
            yield md


def error(msg: str) -> None:
    _results.errors.append(msg)


def warn(msg: str) -> None:
    _results.warnings.append(msg)


def _read_frontmatter(content: str) -> str | None:
    """Return the frontmatter block, or None if absent or malformed."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    return parts[1] if len(parts) >= 3 else None


def _iter_static_page_paths() -> list[str]:
    """Return normalized site paths for static Astro pages under src/pages/."""
    if not PAGES_DIR.is_dir():
        return []
    paths: list[str] = []
    for page in sorted(PAGES_DIR.rglob("*.astro")):
        rel = page.relative_to(PAGES_DIR)
        if any("[" in part for part in rel.parts):
            continue
        stem_path = str(rel.with_suffix("")).replace("\\", "/")
        if stem_path == "index":
            slug = ""
        elif stem_path.endswith("/index"):
            slug = stem_path.removesuffix("/index")
        else:
            slug = stem_path
        paths.append(_normalize_site_path(slug))
    return paths


def get_all_slugs() -> set:
    """Build a set of all known slugs/paths from content files and static pages."""
    slugs = set()
    for md in _iter_markdown_files():
        rel = md.relative_to(DOCS_DIR)
        if str(rel).startswith("uk/"):
            continue

        content = md.read_text(errors="replace")
        fm = _read_frontmatter(content) or ""

        slug_match = re.search(r'^slug:\s*(.+)$', fm, re.MULTILINE)
        if slug_match:
            slug = slug_match.group(1).strip().strip('"').strip("'")
        else:
            slug = str(rel.parent if md.name == "index.md" else rel.with_suffix(""))
            slug = slug.replace("\\", "/")

        slugs.add(slug.rstrip("/"))
        slugs.add(slug.rstrip("/") + "/")

    for page_path in _iter_static_page_paths():
        trimmed = page_path.strip("/")
        if trimmed:
            slugs.add(trimmed)
            slugs.add(trimmed + "/")

    return slugs


def _normalize_site_path(path: str) -> str:
    """Normalize a site path to /leading/and/trailing/slash/ form."""
    clean = path.strip().strip('"').strip("'").replace("\\", "/")
    clean = clean.strip("/")
    return f"/{clean}/" if clean else "/"


def _path_derived_slug(md: Path) -> str:
    """Return the docs-relative slug Astro derives from a markdown path."""
    slug = str(md.relative_to(DOCS_DIR).with_suffix("")).replace("\\", "/")
    if slug == "index":
        slug = ""
    elif slug.endswith("/index"):
        slug = slug.removesuffix("/index")
    return slug


def _static_absolute_link_targets() -> set[str]:
    """Build valid absolute targets from content slugs, static pages, and redirect sources."""
    targets: set[str] = set()

    for md in _iter_markdown_files():
        fm = _read_frontmatter(md.read_text(errors="replace")) or ""
        slug_match = re.search(r'^slug:\s*(.+)$', fm, re.MULTILINE)
        slug = slug_match.group(1) if slug_match else _path_derived_slug(md)
        targets.add(_normalize_site_path(slug))

    for page_path in _iter_static_page_paths():
        targets.add(page_path)

    if CONFIG_FILE.exists():
        config = CONFIG_FILE.read_text(errors="replace")
        for redirect_source in re.findall(r"'(/[^']+)'\s*:", config):
            targets.add(_normalize_site_path(redirect_source))

    return targets


def _is_file_like_site_path(path: str) -> bool:
    """Return True when the final URL segment looks like a file name."""
    last_segment = path.rstrip("/").rsplit("/", 1)[-1]
    return "." in last_segment


# ── Check 1: Frontmatter ─────────────────────────────────────────────────────

def check_frontmatter():
    """Check all .md files have valid Starlight frontmatter."""
    print("\n 1. Frontmatter validation...")
    missing_fm = missing_title = missing_order = 0
    _results.total_files = 0

    for md in sorted(_iter_markdown_files()):
        _results.total_files += 1
        rel = str(md.relative_to(DOCS_DIR))
        content = md.read_text(errors="replace")

        fm = _read_frontmatter(content)
        if fm is None:
            label = "Malformed frontmatter" if content.startswith("---") else "Missing frontmatter"
            error(f"{label}: {rel}")
            missing_fm += 1
            continue

        if "title:" not in fm:
            error(f"Missing title: {rel}")
            missing_title += 1
        if md.name.startswith("module-") and "order:" not in fm:
            warn(f"Missing sidebar.order: {rel}")
            missing_order += 1

    print(f"    {_results.total_files - missing_fm}/{_results.total_files} files have valid frontmatter")
    if missing_title:
        print(f"    {missing_title} missing title")
    if missing_order:
        print(f"    {missing_order} modules missing sidebar.order")


# ── Check 2: Slug fields for dotted filenames ────────────────────────────────

def check_slugs():
    """Files with dots in name (module-1.1-foo.md) MUST have slug: field."""
    print("\n 2. Slug fields for dotted filenames...")
    missing = 0

    for md in sorted(_iter_markdown_files()):
        if "." not in md.stem:
            continue
        rel = str(md.relative_to(DOCS_DIR))
        fm = _read_frontmatter(md.read_text(errors="replace")) or ""
        if "slug:" not in fm:
            error(f"Dotted filename without slug: {rel}")
            missing += 1

    if missing == 0:
        print("    All dotted filenames have slug fields")
    else:
        print(f"    {missing} files need slug fields")


# ── Check 3: Internal link targets exist ──────────────────────────────────────

def check_link_targets():
    """Verify internal markdown link targets resolve to existing content."""
    print("\n 3. Internal link target resolution...")
    all_slugs = get_all_slugs()
    broken = 0
    checked = 0

    for md in sorted(_iter_markdown_files()):
        rel = str(md.relative_to(DOCS_DIR))
        if rel.startswith("uk/"):
            continue

        content = md.read_text(errors="replace")
        content_clean = re.sub(r'```[^`]*```', '', content, flags=re.DOTALL)

        for match in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', content_clean):
            link_text, link_path = match.group(1), match.group(2)

            if any(link_path.startswith(p) for p in ("http", "#", "mailto:", "/")):
                if link_path.startswith("/") and not link_path.startswith("//"):
                    abs_path = link_path.lstrip("/").split("#")[0].rstrip("/")
                    checked += 1
                    if abs_path and abs_path not in all_slugs and abs_path + "/" not in all_slugs:
                        dir_path = DOCS_DIR / abs_path
                        if not dir_path.exists() and not (dir_path.parent / "index.md").exists():
                            warn(f"Possibly broken absolute link in {rel}: {link_path}")
                            broken += 1
                continue

            checked += 1
            target = link_path.split("#")[0].rstrip("/")
            if not target:
                continue

            resolved = (md.parent / target).resolve()

            if resolved.is_dir():
                continue
            if resolved.exists():
                continue
            if (resolved / "index.md").exists():
                continue
            try:
                rel_from_docs = str(resolved.relative_to(DOCS_DIR.resolve())).replace("\\", "/")
            except ValueError:
                rel_from_docs = None
            if rel_from_docs and (rel_from_docs in all_slugs or rel_from_docs + "/" in all_slugs):
                continue
            if rel_from_docs:
                slug_guess = rel_from_docs.rstrip("/")
                if any(s.endswith(slug_guess) for s in all_slugs):
                    continue

            # Starlight URL model: non-index files are served as directories
            # (foo/bar.md → URL foo/bar/), so relative links resolve from
            # foo/bar/ not foo/. Try this as a fallback.
            if md.name != "index.md":
                starlight_resolved = (md.parent / md.stem / target).resolve()
                try:
                    starlight_rel = str(starlight_resolved.relative_to(DOCS_DIR.resolve())).replace("\\", "/")
                except ValueError:
                    starlight_rel = None
                if starlight_resolved.is_dir() or starlight_resolved.exists():
                    continue
                if (starlight_resolved / "index.md").exists():
                    continue
                if starlight_rel and (starlight_rel in all_slugs or starlight_rel + "/" in all_slugs):
                    continue
                if starlight_rel and any(s.endswith(starlight_rel.rstrip("/")) for s in all_slugs):
                    continue

            warn(f"Broken relative link in {rel}: [{link_text[:30]}]({link_path})")
            broken += 1

    _results.links_checked = checked
    print(f"    {checked} links checked, {broken} potentially broken")


# ── Check 4: No .md extension in internal links ──────────────────────────────

def check_no_md_links():
    """Internal links should use slug format, not .md extension."""
    print("\n 4. No .md extension in internal links...")
    found = 0

    for md in sorted(_iter_markdown_files()):
        rel = str(md.relative_to(DOCS_DIR))
        if rel.startswith("uk/"):
            continue

        content_clean = re.sub(r'```[^`]*```', '', md.read_text(errors="replace"), flags=re.DOTALL)

        for match in re.finditer(r'\[([^\]]*)\]\(([^)]+\.md(?:#[^)]*)?)\)', content_clean):
            link_path = match.group(2)
            if link_path.startswith("http"):
                continue
            error(f"Internal .md link in {rel}: {link_path}")
            found += 1

    if found == 0:
        print("    All internal links use slug format")
    else:
        print(f"    {found} links still use .md extension")


# ── Check 5: No README.md ────────────────────────────────────────────────────

def check_no_readme():
    """No README.md files should remain."""
    print("\n 5. No README.md files...")
    readmes = list(DOCS_DIR.rglob("README.md"))
    for readme in readmes:
        error(f"README.md not renamed: {readme.relative_to(DOCS_DIR)}")
    if not readmes:
        print("    All READMEs converted to index.md")


# ── Check 6: Ukrainian file placement ────────────────────────────────────────

def check_uk_placement():
    """Ukrainian files should be in uk/ subdirectory."""
    print("\n 6. Ukrainian file placement...")
    misplaced = [str(f.relative_to(DOCS_DIR)) for f in DOCS_DIR.rglob("*.uk.md")]
    for m in misplaced:
        error(f"Ukrainian file with .uk.md suffix: {m}")
    if not misplaced:
        print("    All Ukrainian files in uk/ directory")


# ── Check 7: Module count ────────────────────────────────────────────────────

def check_module_count():
    """Check STATUS.md module count matches reality."""
    print("\n 7. Module count consistency...")
    status_file = REPO_ROOT / "STATUS.md"
    if not status_file.exists():
        warn("STATUS.md not found")
        return

    status = status_file.read_text()
    m = re.search(r'\*\*(\d+)\*\*', status)
    if m:
        claimed = int(m.group(1))
        actual = sum(
            1 for f in _iter_module_files()
            if not str(f.relative_to(DOCS_DIR)).startswith("uk/")
        )
        _results.module_count = actual
        if claimed != actual:
            warn(f"STATUS.md claims {claimed} modules but found {actual}")
        else:
            print(f"    Module count matches: {actual}")
    else:
        warn("Could not parse module count from STATUS.md")


# ── Check 8: Index completeness ──────────────────────────────────────────────

def check_index_completeness():
    """Index files should reference their child modules."""
    print("\n 8. Index files reference child modules...")
    missing = 0

    for index in sorted(DOCS_DIR.rglob("index.md")):
        rel = str(index.relative_to(DOCS_DIR))
        if rel.startswith("uk/"):
            continue

        modules = sorted(f for f in index.parent.glob("module-*.md") if not _is_ignored_content_file(f))
        if not modules:
            continue

        content = index.read_text(errors="replace")
        for mod in modules:
            if mod.stem not in content and mod.name not in content:
                warn(f"{rel} doesn't mention {mod.name}")
                missing += 1

    if missing == 0:
        print("    All index files reference their modules")
    else:
        print(f"    {missing} missing module references in index files")


# ── Check 9: Module naming consistency ────────────────────────────────────────

def check_naming_consistency():
    """All modules should use module-X.Y-name.md format."""
    print("\n 9. Module naming consistency (X.Y format)...")
    inconsistent = 0

    old_pattern = re.compile(r'^module-(\d+)-[a-z]')
    new_pattern = re.compile(r'^module-(\d+\.\d+)-[a-z]')

    for md in sorted(_iter_module_files()):
        rel = str(md.relative_to(DOCS_DIR))
        if rel.startswith("uk/"):
            continue
        if rel.startswith("prerequisites/git-deep-dive/"):
            # Intentionally linear module-N numbering (single Git course, not X.Y tree)
            continue

        if old_pattern.match(md.stem) and not new_pattern.match(md.stem):
            warn(f"Old naming format (module-N, not X.Y): {rel}")
            inconsistent += 1

    if inconsistent == 0:
        print("    All modules use X.Y naming format")
    else:
        print(f"    {inconsistent} modules still use old naming")


# ── Check 10: Empty directories ──────────────────────────────────────────────

def check_empty_dirs():
    """No empty directories should exist in content."""
    print("\n10. Empty directories...")
    empty = 0

    for d in sorted(DOCS_DIR.rglob("*")):
        if d.is_dir() and not any(d.iterdir()):
            warn(f"Empty directory: {d.relative_to(DOCS_DIR)}")
            empty += 1

    if empty == 0:
        print("    No empty directories")
    else:
        print(f"    {empty} empty directories found")


# ── Check 11: Sidebar config references valid directories ─────────────────────

def check_sidebar_dirs():
    """All directory references in astro.config.mjs should exist."""
    print("\n11. Sidebar config directory references...")

    if not CONFIG_FILE.exists():
        warn("astro.config.mjs not found")
        return

    config = CONFIG_FILE.read_text()
    missing = 0

    for match in re.finditer(r"directory:\s*['\"]([^'\"]+)['\"]", config):
        dir_path = match.group(1)
        if not (DOCS_DIR / dir_path).is_dir():
            error(f"Sidebar references missing directory: {dir_path}")
            missing += 1

    if missing == 0:
        dirs_found = len(re.findall(r"directory:", config))
        print(f"    All {dirs_found} directory references valid")
    else:
        print(f"    {missing} missing directories")


# ── Check 12: Every module directory has index.md ─────────────────────────────

def check_dirs_have_index():
    """Every directory containing modules should have an index.md."""
    print("\n12. Module directories have index.md...")
    missing = 0

    for d in sorted(DOCS_DIR.rglob("*")):
        if not d.is_dir():
            continue
        rel = str(d.relative_to(DOCS_DIR))
        if rel.startswith("uk/"):
            continue

        modules = [f for f in d.glob("module-*.md") if not _is_ignored_content_file(f)]
        if modules and not (d / "index.md").exists():
            error(f"Directory has modules but no index.md: {rel}")
            missing += 1

    if missing == 0:
        print("    All module directories have index.md")
    else:
        print(f"    {missing} directories missing index.md")


# ── Check 13: Title matches filename numbering ───────────────────────────────

def check_title_numbering():
    """Module title number should match filename number."""
    print("\n13. Title-filename number consistency...")
    mismatches = 0

    for md in sorted(_iter_module_files()):
        rel = str(md.relative_to(DOCS_DIR))
        if rel.startswith("uk/"):
            continue

        fn_match = re.match(r'module-(\d+\.?\d*)', md.stem)
        if not fn_match:
            continue
        fn_num = fn_match.group(1)

        fm = _read_frontmatter(md.read_text(errors="replace")) or ""
        title_match = re.search(r'title:\s*["\']?(?:Module\s+)?(\d+\.?\d*)', fm)
        if title_match:
            title_num = title_match.group(1)
            if fn_num != title_num:
                warn(f"Number mismatch in {rel}: filename={fn_num}, title={title_num}")
                mismatches += 1

    if mismatches == 0:
        print("    All titles match filenames")
    else:
        print(f"    {mismatches} title-filename mismatches")


# ── Check 14: Static absolute internal link targets ──────────────────────────

def check_static_absolute_internal_links():
    """Verify absolute internal markdown links resolve to slugs or redirects."""
    print("\n14. Static absolute internal link targets...")
    targets = _static_absolute_link_targets()
    broken = 0
    checked = 0

    for md in sorted(_iter_markdown_files()):
        rel = f"src/content/docs/{md.relative_to(DOCS_DIR)}"
        for line_no, line in enumerate(md.read_text(errors="replace").splitlines(), start=1):
            for link_path in ABSOLUTE_INTERNAL_LINK_RE.findall(line):
                if (
                    link_path.startswith(("http://", "https://", "mailto:", "#"))
                    or _is_file_like_site_path(link_path)
                ):
                    continue

                checked += 1
                target = _normalize_site_path(link_path)
                if target not in targets:
                    error(f"{rel}:{line_no} -> {target}")
                    broken += 1

    if broken == 0:
        print(f"    {checked} absolute internal links resolve")
    else:
        print(f"    {broken}/{checked} absolute internal links are unresolved")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("KubeDojo Site Health Check (Comprehensive)")
    print("=" * 60)

    if not DOCS_DIR.exists():
        print(f"\nERROR: Content directory not found: {DOCS_DIR}")
        sys.exit(1)

    check_frontmatter()
    check_slugs()
    check_link_targets()
    check_no_md_links()
    check_no_readme()
    check_uk_placement()
    check_module_count()
    check_index_completeness()
    check_naming_consistency()
    check_empty_dirs()
    check_sidebar_dirs()
    check_dirs_have_index()
    check_title_numbering()
    check_static_absolute_internal_links()

    print("\n" + "=" * 60)
    e_count = len(_results.errors)
    w_count = len(_results.warnings)
    print(f"RESULTS: {e_count} errors, {w_count} warnings")

    parts = []
    if _results.total_files is not None:
        parts.append(f"{_results.total_files} files")
    if _results.module_count is not None:
        parts.append(f"{_results.module_count} modules")
    if _results.links_checked is not None:
        parts.append(f"{_results.links_checked} links checked")
    if parts:
        print(f"STATS:   {', '.join(parts)}")

    print("=" * 60)

    if _results.errors:
        print(f"\nERRORS ({e_count}):")
        for e in _results.errors[:30]:
            print(f"  ✗ {e}")
        if e_count > 30:
            print(f"  ... and {e_count - 30} more")

    if _results.warnings:
        print(f"\nWARNINGS ({w_count}):")
        for w in _results.warnings[:50]:
            print(f"  ⚠ {w}")
        if w_count > 50:
            print(f"  ... and {w_count - 50} more")

    if not _results.errors and not _results.warnings:
        print("\nAll checks passed.")
    elif not _results.errors:
        print("\nNo errors. Warnings are non-blocking.")
    else:
        print("\nFix errors before pushing.")

    sys.exit(1 if _results.errors else 0)


if __name__ == "__main__":
    main()
