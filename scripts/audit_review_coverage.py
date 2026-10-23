"""Audit AI History review coverage for per-chapter status.yaml files.

The authoritative mode reads merged PRs and PR comments through ``gh``. When
GitHub is unavailable, coverage stays pending and cannot be written to contracts.
Rerun with network access to obtain marker-derived coverage, not approval.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = "kube-dojo/kube-dojo.github.io"
REPO_ROOT = Path(__file__).resolve().parents[1]
CHAPTER_ROOT = REPO_ROOT / "docs" / "research" / "ai-history" / "chapters"
AUDIT_DATE = datetime.datetime.now(datetime.UTC).astimezone().date().isoformat()

RESEARCH_FIELDS = ("claude_anchor", "gemini_gap", "codex_anchor")
PROSE_FIELDS = ("claude_source_fidelity", "gemini_prose_quality", "codex_prose_quality")


@dataclass
class ChapterCoverage:
    chapter_num: int
    chapter_key: str
    research_prs: list[int] = field(default_factory=list)
    prose_prs: list[int] = field(default_factory=list)
    research: dict[str, str] = field(
        default_factory=lambda: {name: "pending" for name in RESEARCH_FIELDS}
    )
    prose: dict[str, str] = field(default_factory=lambda: {name: "pending" for name in PROSE_FIELDS})
    source: str = "gh"


def _run_json(args: list[str]) -> Any:
    result = subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def _chapter_num_from_path(path: Path) -> int:
    match = re.match(r"ch-(\d+)-", path.parent.name)
    if not match:
        raise ValueError(f"cannot parse chapter number from {path}")
    return int(match.group(1))


def _chapter_num_from_pr(pr: dict[str, Any]) -> int | None:
    haystack = " ".join(str(pr.get(k) or "") for k in ("title", "headRefName"))
    match = re.search(r"\b(?:ch|chapter)[- _]?0?(\d{1,2})\b", haystack, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _lane_from_title(title: str) -> str | None:
    lowered = title.lower()
    if re.search(r"(?:^|[:\s])research(?:\s+phase)?\s*:", lowered):
        return "research"
    if re.search(r"(?:^|[:\s])prose(?:\s+phase)?\s*:", lowered):
        return "prose"
    return None


def _research_author_family(chapter_num: int) -> str:
    # Issue #559 ownership model plus the later Part 6 split:
    # Parts 1-2 and Part 3 through Ch15 were Claude-authored; Ch32-Ch37
    # were also Claude-authored research contracts after the 2026-04-28
    # role split. Other research contracts in this audit use Codex as the
    # author family.
    if chapter_num <= 15 or 32 <= chapter_num <= 37:
        return "claude"
    return "codex"


def _expected_lane_fields(chapter_num: int, lane: str) -> set[str]:
    """Markers expected to *possibly* fire on this lane (for research-side normalization).

    Research lane keeps the strict author-aware pair (Claude-authored research is
    cross-reviewed by Gemini gap-analysis + Codex anchor-verification; Codex-authored
    research is cross-reviewed by Gemini gap-analysis + Claude anchor-verification).

    Prose lane returns the full set of three families because the cross-family rule
    is "any two distinct families reviewed", not a specific pair. This reflects the
    post-2026-04-27 reality where Gemini was retired from source-bearing prose
    review (Issue #421); Ch04-Ch09 were reviewed by Claude+Codex (no Gemini),
    Ch10-Ch15 were reviewed by Claude+Gemini (pre-#421). Both patterns are valid
    cross-family coverage.
    """
    author = _research_author_family(chapter_num)
    if lane == "research":
        if author == "claude":
            return {"gemini_gap", "codex_anchor"}
        return {"gemini_gap", "claude_anchor"}
    return set(PROSE_FIELDS)


def _normalize_not_expected(
    values: dict[str, str],
    expected: set[str],
    marker_seen: set[str],
) -> dict[str, str]:
    out = dict(values)
    for field_name in out:
        if field_name not in expected and field_name not in marker_seen:
            out[field_name] = "n/a"
    return out


def _lane_satisfied(values: dict[str, str], chapter_num: int, lane: str) -> bool:
    if lane not in {"research", "prose"}:
        return False
    if lane == "prose":
        # Prose cross-family rule: any two distinct families reviewed.
        return sum(values.get(name) == "done" for name in PROSE_FIELDS) >= 2
    expected = _expected_lane_fields(chapter_num, lane)
    return all(values.get(field_name) == "done" for field_name in expected)


def _fetch_prs() -> list[dict[str, Any]]:
    searches = ("#394 in:title", "#402 in:title", "#403 in:title")
    seen: dict[int, dict[str, Any]] = {}
    for search in searches:
        prs = _run_json([
            "gh",
            "pr",
            "list",
            "--repo",
            REPO,
            "--search",
            search,
            "--state",
            "merged",
            "--limit",
            "200",
            "--json",
            "number,title,headRefName,mergedAt",
        ])
        for pr in prs:
            number = int(pr["number"])
            seen[number] = pr
    return list(seen.values())


def _fetch_comment_bodies(pr_number: int) -> list[str]:
    comments = _run_json([
        "gh",
        "api",
        "--paginate",
        f"repos/{REPO}/issues/{pr_number}/comments",
    ])
    if not isinstance(comments, list):
        return []
    return [str(comment.get("body") or "") for comment in comments if isinstance(comment, dict)]


def _apply_comment_markers(coverage: ChapterCoverage, lane: str, comments: list[str]) -> None:
    marker_seen: set[str] = set()
    for body in comments:
        lowered = body.lower()
        if "_failed_" in lowered:
            continue
        if lane == "research" and "<!-- verdict claude" in lowered:
            coverage.research["claude_anchor"] = "done"
            marker_seen.add("claude_anchor")
        if lane == "research" and "<!-- verdict gemini" in lowered:
            coverage.research["gemini_gap"] = "done"
            marker_seen.add("gemini_gap")
        if lane == "research" and "<!-- verdict codex" in lowered:
            coverage.research["codex_anchor"] = "done"
            marker_seen.add("codex_anchor")
        if lane == "prose" and "<!-- prose review claude" in lowered:
            coverage.prose["claude_source_fidelity"] = "done"
            marker_seen.add("claude_source_fidelity")
        if lane == "prose" and "<!-- prose review gemini" in lowered:
            coverage.prose["gemini_prose_quality"] = "done"
            marker_seen.add("gemini_prose_quality")
        if lane == "prose" and "<!-- prose review codex" in lowered:
            coverage.prose["codex_prose_quality"] = "done"
            marker_seen.add("codex_prose_quality")

    if lane == "research":
        expected = _expected_lane_fields(coverage.chapter_num, lane)
        coverage.research = _normalize_not_expected(coverage.research, expected, marker_seen)
    else:
        # Missing comments are not evidence; retain markers from earlier PRs.
        coverage.prose = {
            field_name: ("done" if coverage.prose[field_name] == "done" else "pending")
            for field_name in PROSE_FIELDS
        }


def _offline_seed(chapters: list[Path]) -> dict[int, ChapterCoverage]:
    """Unavailable comments leave coverage pending, regardless of status labels."""
    coverages: dict[int, ChapterCoverage] = {}
    for path in chapters:
        chapter_num = _chapter_num_from_path(path)
        coverage = ChapterCoverage(chapter_num, path.parent.name, source="offline")
        coverages[chapter_num] = coverage
    return coverages


def _build_coverage(strict_gh: bool) -> dict[int, ChapterCoverage]:
    chapters = sorted(CHAPTER_ROOT.glob("ch-*/status.yaml"))
    coverages = {
        _chapter_num_from_path(path): ChapterCoverage(_chapter_num_from_path(path), path.parent.name)
        for path in chapters
    }
    try:
        prs = _fetch_prs()
    except RuntimeError as exc:
        if strict_gh:
            raise
        print(f"warning: gh audit unavailable; using conservative local fallback: {exc}")
        return _offline_seed(chapters)

    for pr in prs:
        chapter_num = _chapter_num_from_pr(pr)
        lane = _lane_from_title(str(pr.get("title") or ""))
        if chapter_num is None or lane is None or chapter_num not in coverages:
            continue
        coverage = coverages[chapter_num]
        if lane == "research":
            coverage.research_prs.append(int(pr["number"]))
        else:
            coverage.prose_prs.append(int(pr["number"]))
        comments = _fetch_comment_bodies(int(pr["number"]))
        _apply_comment_markers(coverage, lane, comments)

    for coverage in coverages.values():
        if coverage.research_prs:
            coverage.research = _normalize_not_expected(
                coverage.research,
                _expected_lane_fields(coverage.chapter_num, "research"),
                {name for name, value in coverage.research.items() if value == "done"},
            )
        # Missing phase PRs retain the initial pending values.
    return coverages


def _coverage_block(coverage: ChapterCoverage) -> str:
    research_ok = _lane_satisfied(coverage.research, coverage.chapter_num, "research")
    prose_ok = _lane_satisfied(coverage.prose, coverage.chapter_num, "prose")
    overall_ok = research_ok and prose_ok
    bool_text = {True: "true", False: "false"}
    return "\n".join([
        "review_coverage:",
        "  research:",
        f"    claude_anchor: {coverage.research['claude_anchor']}",
        f"    gemini_gap: {coverage.research['gemini_gap']}",
        f"    codex_anchor: {coverage.research['codex_anchor']}",
        "  prose:",
        f"    claude_source_fidelity: {coverage.prose['claude_source_fidelity']}",
        f"    gemini_prose_quality: {coverage.prose['gemini_prose_quality']}",
        f"    codex_prose_quality: {coverage.prose['codex_prose_quality']}",
        "  cross_family_satisfied:",
        f"    research: {bool_text[research_ok]}",
        f"    prose: {bool_text[prose_ok]}",
        f"    overall: {bool_text[overall_ok]}",
        f"  backfill_pending: {bool_text[not overall_ok]}",
        f"  last_audited: {AUDIT_DATE}",
        "",
    ])


def _replace_top_level_block(text: str, block_name: str, replacement: str) -> str:
    lines = text.splitlines(keepends=True)
    start = None
    for idx, line in enumerate(lines):
        if line == f"{block_name}:\n" or line == f"{block_name}:":
            start = idx
            break
    if start is None:
        suffix = "" if text.endswith("\n") else "\n"
        return f"{text}{suffix}{replacement}"

    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.startswith((" ", "\t", "#")):
            break
        end += 1
    return "".join(lines[:start]) + replacement + "".join(lines[end:])


def _write_status_files(coverages: dict[int, ChapterCoverage]) -> None:
    if any(coverage.source == "offline" for coverage in coverages.values()):
        raise RuntimeError("Refusing to write offline coverage without observed reviews")
    for path in sorted(CHAPTER_ROOT.glob("ch-*/status.yaml")):
        chapter_num = _chapter_num_from_path(path)
        text = path.read_text(encoding="utf-8")
        updated = _replace_top_level_block(text, "review_coverage", _coverage_block(coverages[chapter_num]))
        path.write_text(updated, encoding="utf-8")


def _summary_rows(coverages: dict[int, ChapterCoverage]) -> list[tuple[str, bool, bool, bool, str]]:
    rows = []
    for chapter_num in sorted(coverages):
        coverage = coverages[chapter_num]
        research_ok = _lane_satisfied(coverage.research, coverage.chapter_num, "research")
        prose_ok = _lane_satisfied(coverage.prose, coverage.chapter_num, "prose")
        rows.append((coverage.chapter_key, research_ok, prose_ok, not (research_ok and prose_ok), coverage.source))
    return rows


def _print_summary(coverages: dict[int, ChapterCoverage]) -> None:
    print("| chapter | research | prose | backfill_pending | source |")
    print("|---|---:|---:|---:|---|")
    for chapter_key, research_ok, prose_ok, pending, source in _summary_rows(coverages):
        print(f"| {chapter_key} | {str(research_ok).lower()} | {str(prose_ok).lower()} | {str(pending).lower()} | {source} |")
    pending_count = sum(1 for _, _, _, pending, _ in _summary_rows(coverages) if pending)
    print(f"\nbackfill_pending_count: {pending_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-gh",
        action="store_true",
        help="fail instead of using the local fallback when gh cannot fetch PR comments",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write review_coverage blocks into chapter status.yaml files",
    )
    args = parser.parse_args()
    coverages = _build_coverage(strict_gh=args.strict_gh)
    if args.write:
        _write_status_files(coverages)
    else:
        print("dry_run: true (pass --write to update status.yaml files)")
    _print_summary(coverages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
