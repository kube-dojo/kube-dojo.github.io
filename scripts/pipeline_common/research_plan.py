"""Load author research input from an existing citation seed, without promotion."""

from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

from scripts.quality.source_acceptance import SEEDS_DIR, load_seed_bytes


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_research_plan(plan: object) -> list[str]:
    """Validate plan shape only; this cannot establish coverage or source truth."""
    if not isinstance(plan, dict):
        return ["research input blocked: coverage_plan must be an object"]
    errors = []
    if plan.get("module_kind") != "module":
        errors.append("research input blocked: module_kind must be module")
    for key in ("outcomes", "essential_topics"):
        value = plan.get(key)
        if (not isinstance(value, list) or not value or any(not _text(item) for item in value)
                or len({item.strip() for item in value if isinstance(item, str)}) != len(value)):
            errors.append(f"research input blocked: {key} must be a nonempty list of unique strings")
    sources = plan.get("source_basis")
    if (not isinstance(sources, list) or not sources or any(
        not isinstance(source, dict) or any(not _text(source.get(key)) for key in ("uri", "locator", "excerpt"))
        for source in sources
    )):
        errors.append("research input blocked: source_basis must contain uri, locator and excerpt")
    return errors


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _page_relative(module_path: str | Path) -> str:
    if not isinstance(module_path, (str, Path)):
        raise TypeError("module path must be a relative Markdown path")
    raw = str(module_path)
    path = Path(raw)
    if (not raw or "\x00" in raw or "\\" in raw or path.is_absolute() or PureWindowsPath(raw).drive
            or ".." in path.parts or path.suffix != ".md"):
        raise ValueError("module path must be a safe relative Markdown path")
    parts = path.parts
    if parts[:3] == ("src", "content", "docs"):
        parts = parts[3:]
    if not parts:
        raise ValueError("module path must identify a page")
    return Path(*parts).as_posix()


def load_research_plan(repo_root: Path, module_path: str | Path) -> tuple[dict | None, list[str]]:
    """Load the matching seed's optional plan; errors mean research is blocked.

    No source is fetched or judged, and no score, receipt or acceptance is made.
    A seed's page digest binds its claims, not necessarily a later research plan.
    """
    try:
        page_rel = _page_relative(module_path)
    except (TypeError, ValueError) as exc:
        return None, [f"research input blocked: {exc}"]
    try:
        raw = load_seed_bytes(Path(repo_root) / SEEDS_DIR, page_rel)
    except OSError as exc:
        return None, [f"research input blocked: cannot read citation seed: {exc}"]
    if raw is None:
        return None, ["research input blocked: citation seed missing or unreadable"]
    try:
        seed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError) as exc:
        return None, [f"research input blocked: malformed citation seed: {exc}"]
    if (not isinstance(seed, dict) or seed.get("module_path") != f"src/content/docs/{page_rel}"
            or seed.get("module_key") != str(Path(page_rel).with_suffix(""))):
        return None, ["research input blocked: citation seed page identity mismatch"]
    plan = seed.get("coverage_plan")
    errors = validate_research_plan(plan)
    return (None, errors) if errors else (plan, [])
