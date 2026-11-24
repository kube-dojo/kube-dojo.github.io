#!/usr/bin/env python3
"""Rename AI/ML module filenames to local per-section numbering.

This migration preserves rendered URLs by keeping each module's explicit slug
set to its pre-rename value. It updates:
  - filenames under src/content/docs/ai-ml-engineering/<section>/
  - missing slug frontmatter (if any)
  - section index tables that link by source filename
  - relative markdown links that point at renamed source filenames
  - .pipeline/state.yaml module keys
  - textual file-path references that include the full .md path

Usage:
    python scripts/ai-ml/rename-phases-to-local.py --dry-run
    python scripts/ai-ml/rename-phases-to-local.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard for local envs
    raise SystemExit(
        "PyYAML is required. Install it with `uv sync --locked` "
        "or use a project virtualenv before running this script."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
TRACK_ROOT = DOCS_ROOT / "ai-ml-engineering"
STATE_PATH = REPO_ROOT / ".pipeline" / "state.yaml"
ASTRO_CONFIG = REPO_ROOT / "astro.config.mjs"
EXCLUDED_REWRITE_PATHS = {
    REPO_ROOT / "docs" / "ai-ml-modernization-plan.md",
}
MODULE_RE = re.compile(r"^module-(\d+)\.(\d+)-(.+)\.md$")
TITLE_RE = re.compile(r'^title:\s*(?:"([^"]+)"|(.+))\s*$', re.MULTILINE)
SLUG_RE = re.compile(r"^slug:\s*(.+)\s*$", re.MULTILINE)
RELATIVE_LINK_RE = re.compile(
    r"\((?P<prefix>(?:\./|\.\./)*)(?P<basename>module-\d+\.\d+-[^)/#\s]+)"
    r"(?P<suffix>(?:\.md)?/?(?:#[^)]+)?)\)"
)
RELATIVE_MD_LINK_RE = re.compile(
    r"\((?P<prefix>(?!https?://|mailto:|/)(?:\./|\.\./)*[^)#\s]+?)\.md(?P<suffix>(?:#[^)]+)?)\)"
)
MODULE_ROW_RE = re.compile(r"^\|\s*\d+\.\d+\s*\|")


@dataclass(frozen=True)
class ModuleRename:
    section: str
    old_path: Path
    new_path: Path
    old_basename: str
    new_basename: str
    old_slug: str
    title: str

    @property
    def old_key(self) -> str:
        return f"ai-ml-engineering/{self.section}/{self.old_basename}"

    @property
    def new_key(self) -> str:
        return f"ai-ml-engineering/{self.section}/{self.new_basename}"

    @property
    def old_repo_path(self) -> str:
        return str(self.old_path.relative_to(REPO_ROOT))

    @property
    def new_repo_path(self) -> str:
        return str(self.new_path.relative_to(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print planned changes only")
    mode.add_argument("--apply", action="store_true", help="Apply the migration")
    return parser.parse_args()


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent
    ) as tmp:
        tmp.write(content)
        temp_name = tmp.name
    Path(temp_name).replace(path)


def split_frontmatter(text: str) -> tuple[str, str] | tuple[None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    frontmatter = text[4:end]
    body = text[end + 5 :]
    return frontmatter, body


def merge_frontmatter(frontmatter: str, body: str) -> str:
    return f"---\n{frontmatter}\n---\n{body}"


def extract_title(text: str, fallback: str) -> str:
    match = TITLE_RE.search(text)
    if not match:
        return fallback
    return match.group(1) or match.group(2) or fallback


def ensure_explicit_slug(text: str, slug: str) -> tuple[str, bool]:
    frontmatter, body = split_frontmatter(text)
    if frontmatter is None:
        raise ValueError("Module is missing YAML frontmatter")
    if SLUG_RE.search(frontmatter):
        return text, False

    lines = frontmatter.splitlines()
    insert_at = 1 if lines and lines[0].startswith("title:") else 0
    lines.insert(insert_at, f"slug: {slug}")
    return merge_frontmatter("\n".join(lines), body), True


def discover_modules() -> list[ModuleRename]:
    renames: list[ModuleRename] = []
    for section_dir in sorted(p for p in TRACK_ROOT.iterdir() if p.is_dir()):
        modules = []
        for module_path in sorted(section_dir.glob("module-*.md")):
            match = MODULE_RE.match(module_path.name)
            if not match:
                continue
            major = int(match.group(1))
            minor = int(match.group(2))
            modules.append((major, minor, module_path, match.group(3)))

        modules.sort(key=lambda item: (item[0], item[1], item[2].name))
        for index, (_major, _minor, old_path, suffix) in enumerate(modules, start=1):
            old_basename = old_path.stem
            new_basename = f"module-1.{index}-{suffix}"
            new_path = old_path.with_name(f"{new_basename}.md")
            text = load_text(old_path)
            old_slug_match = SLUG_RE.search(text)
            old_slug = old_slug_match.group(1).strip() if old_slug_match else (
                f"ai-ml-engineering/{section_dir.name}/{old_basename}"
            )
            title = extract_title(text, fallback=suffix.replace("-", " "))
            renames.append(
                ModuleRename(
                    section=section_dir.name,
                    old_path=old_path,
                    new_path=new_path,
                    old_basename=old_basename,
                    new_basename=new_basename,
                    old_slug=old_slug,
                    title=title,
                )
            )
    return renames


def build_lookup(renames: list[ModuleRename]) -> dict[str, ModuleRename]:
    return {rename.old_basename: rename for rename in renames}


def rewrite_relative_links(text: str, lookup: dict[str, ModuleRename]) -> tuple[str, int]:
    replacements = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replacements
        basename = match.group("basename")
        rename = lookup.get(basename)
        if rename is None:
            return match.group(0)
        replacements += 1
        return f"({match.group('prefix')}{rename.new_basename}{match.group('suffix')})"

    return RELATIVE_LINK_RE.sub(replace, text), replacements


def replace_textual_path_references(text: str, renames: list[ModuleRename]) -> tuple[str, int]:
    replacements = 0
    for rename in renames:
        pairs = (
            (rename.old_repo_path, rename.new_repo_path),
            (f"{rename.old_key}.md", f"{rename.new_key}.md"),
        )
        for old, new in pairs:
            count = text.count(old)
            if count:
                text = text.replace(old, new)
                replacements += count
    return text, replacements


def strip_relative_md_extensions(text: str) -> tuple[str, int]:
    replacements = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return f"({match.group('prefix')}{match.group('suffix')})"

    return RELATIVE_MD_LINK_RE.sub(replace, text), replacements


def update_index_table(index_path: Path, section_renames: list[ModuleRename]) -> tuple[str, int]:
    text = load_text(index_path)
    lines = text.splitlines()
    header_idx = None
    separator_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "| # | Module |":
            header_idx = idx
            if idx + 1 < len(lines):
                separator_idx = idx + 1
            break

    if header_idx is None or separator_idx is None:
        return text, 0

    row_start = separator_idx + 1
    row_end = row_start
    while row_end < len(lines) and MODULE_ROW_RE.match(lines[row_end]):
        row_end += 1

    new_rows = [
        f"| 1.{index} | [{rename.title}](/{rename.old_slug}/) |"
        for index, rename in enumerate(section_renames, start=1)
    ]
    new_lines = lines[:row_start] + new_rows + lines[row_end:]
    replacements = len(section_renames)
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), replacements


def planned_text_rewrites(renames: list[ModuleRename]) -> dict[Path, dict[str, int]]:
    lookup = build_lookup(renames)
    rewrite_plan: dict[Path, dict[str, int]] = {}

    candidate_paths: list[Path] = []
    for base in (DOCS_ROOT, REPO_ROOT / "docs", REPO_ROOT / ".claude" / "rules"):
        if base.exists():
            candidate_paths.extend(
                path
                for path in base.rglob("*.md")
                if path.is_file() and not MODULE_RE.match(path.name)
            )
    candidate_paths.extend(path for path in TRACK_ROOT.glob("*/index.md") if path.is_file())

    seen: set[Path] = set()
    for path in candidate_paths:
        if path in seen or path in EXCLUDED_REWRITE_PATHS:
            continue
        seen.add(path)
        text = load_text(path)
        new_text, relative_count = rewrite_relative_links(text, lookup)
        newer_text, full_path_count = replace_textual_path_references(new_text, renames)
        if path.parent.parent == TRACK_ROOT and path.name == "index.md":
            section = path.parent.name
            section_renames = [rename for rename in renames if rename.section == section]
            newer_text, table_count = update_index_table(path, section_renames)
            if newer_text == text:
                table_count = 0
        else:
            table_count = 0

        if newer_text != text:
            rewrite_plan[path] = {
                "relative_links": relative_count,
                "full_paths": full_path_count,
                "index_rows": table_count,
            }
    return rewrite_plan


def migrate_state_data(renames: list[ModuleRename]) -> tuple[dict, int]:
    state = yaml.safe_load(load_text(STATE_PATH))
    modules = state.get("modules", {})
    rename_by_key = {rename.old_key: rename.new_key for rename in renames}

    updated_modules = {}
    migrated = 0
    for key, value in modules.items():
        new_key = rename_by_key.get(key, key)
        if new_key != key:
            migrated += 1
        updated_modules[new_key] = value

    state["modules"] = updated_modules
    return state, migrated


def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)


def check_for_sidebar_references(renames: list[ModuleRename]) -> int:
    text = load_text(ASTRO_CONFIG)
    count = 0
    for rename in renames:
        count += text.count(rename.old_key)
    return count


def apply_module_updates(renames: list[ModuleRename]) -> tuple[int, int]:
    slug_injections = 0
    renamed_files = 0
    lookup = build_lookup(renames)

    for rename in renames:
        text = load_text(rename.old_path)
        new_text, injected = ensure_explicit_slug(text, rename.old_slug)
        new_text, _ = rewrite_relative_links(new_text, lookup)
        new_text, _ = replace_textual_path_references(new_text, renames)
        new_text, _ = strip_relative_md_extensions(new_text)
        if injected:
            slug_injections += 1
        if rename.new_path == rename.old_path:
            if new_text != text:
                write_text(rename.old_path, new_text)
            continue

        write_text(rename.new_path, new_text)
        rename.old_path.unlink()
        renamed_files += 1

    return slug_injections, renamed_files


def apply_text_rewrites(rewrite_plan: dict[Path, dict[str, int]], renames: list[ModuleRename]) -> int:
    lookup = build_lookup(renames)
    rewritten = 0

    for path in sorted(rewrite_plan):
        text = load_text(path)
        new_text, _ = rewrite_relative_links(text, lookup)
        new_text, _ = replace_textual_path_references(new_text, renames)

        if path.parent.parent == TRACK_ROOT and path.name == "index.md":
            section = path.parent.name
            section_renames = [rename for rename in renames if rename.section == section]
            new_text, _ = update_index_table(path, section_renames)

        if new_text != text:
            write_text(path, new_text)
            rewritten += 1

    return rewritten


def apply_state_update(state: dict) -> None:
    write_text(STATE_PATH, dump_yaml(state))


def print_rename_table(renames: list[ModuleRename]) -> None:
    print("OLD -> NEW rename table")
    print("| Old | New |")
    print("|---|---|")
    for rename in renames:
        print(f"| `{rename.old_repo_path}` | `{rename.new_repo_path}` |")


def print_rewrite_summary(rewrite_plan: dict[Path, dict[str, int]]) -> None:
    print("\nPlanned text rewrites")
    if not rewrite_plan:
        print("(none)")
        return
    for path in sorted(rewrite_plan):
        stats = rewrite_plan[path]
        parts = []
        if stats["relative_links"]:
            parts.append(f"relative-links={stats['relative_links']}")
        if stats["full_paths"]:
            parts.append(f"full-paths={stats['full_paths']}")
        if stats["index_rows"]:
            parts.append(f"index-rows={stats['index_rows']}")
        detail = ", ".join(parts) if parts else "content rewrite"
        print(f"- {path.relative_to(REPO_ROOT)}: {detail}")


def main() -> int:
    args = parse_args()
    renames = discover_modules()
    rewrite_plan = planned_text_rewrites(renames)
    state, migrated_state_keys = migrate_state_data(renames)
    astro_hits = check_for_sidebar_references(renames)

    print(f"Discovered {len(renames)} AI/ML modules across 12 section directories.\n")
    print_rename_table(renames)
    print_rewrite_summary(rewrite_plan)
    print(f"\nPlanned state key migrations: {migrated_state_keys}")
    print(f"astro.config.mjs old AI/ML module slug references: {astro_hits}")

    if args.dry_run:
        return 0

    slug_injections, renamed_files = apply_module_updates(renames)
    rewritten_files = apply_text_rewrites(rewrite_plan, renames)
    apply_state_update(state)

    print("\nApplied changes")
    print(f"- files renamed: {renamed_files}")
    print(f"- modules with injected slug: {slug_injections}")
    print(f"- text files rewritten: {rewritten_files}")
    print(f"- state keys migrated: {migrated_state_keys}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
