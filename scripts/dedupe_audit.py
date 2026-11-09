#!/usr/bin/env python3
"""Deduplication audit: find content overlap between two tracks via Gemini.

For each module in source_track, find candidate overlaps in target_tracks
based on title/heading similarity, then ask Gemini to judge whether they
truly overlap and recommend a resolution (keep both / merge / cross-link).

Usage:
    python scripts/dedupe_audit.py --source ai-ml-engineering --against k8s,cloud,linux,prerequisites,platform
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
GEMINI_WRITER_MODEL = "gemini-3.1-pro-high"


def dispatch_agy(*_args, **_kwargs):
    raise RuntimeError("legacy dispatcher removed")


def extract_title_and_topics(path: Path) -> tuple[str, list[str]]:
    """Return (title, list of H2 headings) for a module."""
    content = path.read_text()
    title_match = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else path.stem
    h2s = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
    return title, h2s[:10]  # cap at 10 to keep prompts small


def find_candidates(source_topics: list[str], target_modules: list[Path], threshold: int = 2) -> list[Path]:
    """Find target modules with at least `threshold` overlapping H2 keywords."""
    source_words = set()
    for topic in source_topics:
        source_words.update(w.lower() for w in re.findall(r"\w+", topic) if len(w) > 3)

    candidates = []
    for tmod in target_modules:
        try:
            _, target_topics = extract_title_and_topics(tmod)
        except Exception:
            continue
        target_words = set()
        for topic in target_topics:
            target_words.update(w.lower() for w in re.findall(r"\w+", topic) if len(w) > 3)
        overlap = len(source_words & target_words)
        if overlap >= threshold:
            candidates.append((tmod, overlap))

    candidates.sort(key=lambda x: -x[1])
    return [c[0] for c in candidates[:5]]  # top 5


def ask_gemini(source_path: Path, candidates: list[Path]) -> dict:
    """Ask Gemini to judge overlap and recommend a resolution."""
    source_title, source_topics = extract_title_and_topics(source_path)
    candidates_summary = []
    for c in candidates:
        ctitle, ctopics = extract_title_and_topics(c)
        candidates_summary.append({
            "path": str(c.relative_to(CONTENT_ROOT)),
            "title": ctitle,
            "topics": ctopics,
        })

    prompt = f"""You are auditing a curriculum for content duplication.

SOURCE MODULE (newly migrated):
- Path: {source_path.relative_to(CONTENT_ROOT)}
- Title: {source_title}
- Sections: {', '.join(source_topics[:8])}

CANDIDATE OVERLAPS in existing curriculum:
{json.dumps(candidates_summary, indent=2)}

For each candidate, answer:
1. Does it genuinely cover the same material as the source? (yes/partial/no)
2. If yes/partial: what's the recommended resolution?
   - "keep_both" (different audiences/depth — explain)
   - "merge_into_source" (target is shallower, replace with cross-link to source)
   - "merge_into_target" (source is redundant, drop or fold into target)
   - "cross_reference" (light overlap, add see-also links)

Output ONLY JSON in this format:
{{"recommendations": [
  {{"candidate": "path", "overlap": "yes|partial|no", "action": "...", "rationale": "1-2 sentences"}},
  ...
]}}
"""

    ok, output = dispatch_agy(prompt, model=GEMINI_WRITER_MODEL, timeout=120)
    if not ok:
        return {"error": "dispatch_failed"}

    # Strip code fences
    output = output.strip()
    if output.startswith("```"):
        lines = output.split("\n")
        output = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        return {"error": f"parse_failed: {e}", "raw": output[:500]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Track to audit (e.g. ai-ml-engineering)")
    parser.add_argument("--against", required=True, help="Comma-separated tracks to compare against")
    parser.add_argument("--output", default="docs/migration-decisions.md")
    parser.add_argument("--limit", type=int, help="Max source modules to audit")
    args = parser.parse_args()

    source_root = CONTENT_ROOT / args.source
    if not source_root.exists():
        print(f"ERROR: {source_root} not found", file=sys.stderr)
        return 1

    target_tracks = [t.strip() for t in args.against.split(",")]
    target_modules = []
    for track in target_tracks:
        target_root = CONTENT_ROOT / track
        if target_root.exists():
            target_modules.extend(
                m for m in target_root.rglob("module-*.md")
                if "/uk/" not in str(m) and ".staging" not in str(m)
            )

    print(f"Source: {args.source} ({len(list(source_root.rglob('module-*.md')))} modules)")
    print(f"Comparing against: {target_tracks} ({len(target_modules)} modules)")
    print()

    source_modules = sorted(source_root.rglob("module-*.md"))
    if args.limit:
        source_modules = source_modules[:args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for i, src in enumerate(source_modules, 1):
        print(f"[{i}/{len(source_modules)}] {src.relative_to(CONTENT_ROOT)}")
        _, topics = extract_title_and_topics(src)
        candidates = find_candidates(topics, target_modules)
        if not candidates:
            print("    no candidates")
            continue
        print(f"    {len(candidates)} candidates → asking Gemini...")
        result = ask_gemini(src, candidates)
        results.append({"source": str(src.relative_to(CONTENT_ROOT)), "result": result})

    # Write report
    report = ["# Migration Deduplication Decisions\n",
              f"Source: `{args.source}`",
              f"Compared against: `{', '.join(target_tracks)}`",
              f"Modules audited: {len(results)}\n"]

    for r in results:
        report.append(f"\n## {r['source']}\n")
        rec = r["result"].get("recommendations", [])
        if not rec:
            report.append(f"- No recommendations ({r['result'].get('error', 'empty')})")
            continue
        for item in rec:
            report.append(
                f"- **{item.get('candidate', '?')}** — overlap: `{item.get('overlap', '?')}` → "
                f"action: `{item.get('action', '?')}`\n  - {item.get('rationale', '')}"
            )

    output_path.write_text("\n".join(report))
    print(f"\nReport written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
