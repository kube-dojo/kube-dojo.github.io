"""Module density metric — detects pad-bombs and v3 punchy-bullet style.

Computes three signals over the prose paragraphs of a markdown module:

* **words** — total word count (excludes code blocks, frontmatter, tables,
  list items, callouts, blockquotes — anything that isn't a prose paragraph).
* **w_per_line** (``w/ln``) — words divided by non-blank lines. Below ~12
  signals one-sentence-per-paragraph padding (the Codex v2 pad-bomb signature).
* **w_per_para** (``wpp``) — words per prose paragraph. Below ~18 signals
  punchy-bullet v3 style or generic-essay LLM filler. Very high values signal
  walls-of-text without scaffolding.

These numbers are **diagnostics**, not gates (#3744, operator balance rule
2026-11-02): ``attention()`` flags BOTH tails for the reviewer, and a flag never
rejects, routes, tiers, enqueues or rewards a page. A page inside every bound is
not thereby accepted; outcome coverage is judged against the outcomes. Any
single signal is gameable on its own, which is one more reason none of them
decides anything.

Calibration anchors (from `.calibration/teaching-rewrite/` outputs):

| Source                                  | words | w/ln | wpp  |
|-----------------------------------------|------:|-----:|-----:|
| original 9.1 GPU pad-bomb               | 10496 | 7.5  | 10.9 |
| original 1.1 v3 punchy-bullets          |  1729 | 7.5  | 15.6 |
| Gemini-3.1-pro × 1.1 rewrite (good)     |  2568 | 21.8 | 69.8 |
| Codex gpt-5.5 × 1.1 rewrite (good)      |  3604 | 23.7 | 60.3 |
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

# Lower attention bounds (legacy ``*_REWRITE`` names; ``attention()`` is their
# only reader). Below these the shape is clearly choppy or thin; anchored
# against the corpus' worst pad-bomb (9.1 GPU at w/ln 7.5, wpp 10.9) and
# punchy-bullets (1.1 v3 at w/ln 7.5, wpp 15.6). Diagnostic only:
# ``attention()`` flags them, nothing rejects.
WORDS_FLOOR_REWRITE = 1000
W_PER_LINE_FLOOR_REWRITE = 12.0
W_PER_PARA_FLOOR_REWRITE = 18.0

# Upper attention bounds, so the long tail is flagged as visibly as the short
# one. Measured 2026-11-02 over 917 English modules with >=10 prose
# paragraphs: prose_words p99 8137 / max 9688, wpp p99 108 / max 132 (the
# known pad-bomb anchor is 10496 words). That corpus was shaped by the old
# 5000-word floor, so percentile cuts would re-encode that norm; the bounds sit
# beyond p99 and are reviewer-attention flags, never targets.
WORDS_CEILING_ATTENTION = 9000
W_PER_PARA_CEILING_ATTENTION = 120.0


_FRONTMATTER_FENCE = re.compile(r"^---\s*\n.*?\n---\s*\n", flags=re.DOTALL)
_FENCED_CODE = re.compile(r"```.*?```", flags=re.DOTALL)
_DETAILS_TAG = re.compile(r"</?(details|summary)[^>]*>")


@dataclass(frozen=True)
class DensityMetrics:
    """Density signals for a module.

    Two word-counts are tracked separately because they answer different
    questions:

    * ``prose_words``     — words inside prose paragraphs only (excludes
      headings, tables, list items, callouts). Measures the teaching budget.
    * ``textual_words``   — all words after stripping frontmatter + fenced
      code + ``<details>`` tags. Used for ``w_per_line`` because a
      structurally rich module (lots of tables and callouts) inflates the
      nonblank-line denominator without inflating the prose word count.
      Mixing the two penalizes table-heavy teaching modules unfairly.
    """

    prose_words: int
    textual_words: int
    nonblank_lines: int
    total_paragraphs: int
    prose_paragraphs: int
    w_per_line: float
    w_per_para: float

    def attention(self) -> list[str]:
        """Reviewer-attention flags for BOTH tails. Diagnostic only.

        Never an input to routing, rejection, tiering or acceptance (#3744).
        Short, choppy, long and walled pages are each flagged for the
        reviewer to judge against the page's outcomes; an empty list does
        not mean the page teaches its outcomes.
        """
        out: list[str] = []
        if self.prose_words < WORDS_FLOOR_REWRITE:
            out.append(f"prose_words {self.prose_words} < {WORDS_FLOOR_REWRITE}: unusually short; check every outcome is fully explained")
        elif self.prose_words > WORDS_CEILING_ATTENTION:
            out.append(f"prose_words {self.prose_words} > {WORDS_CEILING_ATTENTION}: unusually long; check for padding, repetition or off-topic background")
        if self.w_per_line < W_PER_LINE_FLOOR_REWRITE:
            out.append(f"w/ln {_toward_flag(self.w_per_line, up=False)} < {W_PER_LINE_FLOOR_REWRITE:g}: one-sentence paragraphs; check for padding or skipped explanation")
        if self.w_per_para < W_PER_PARA_FLOOR_REWRITE:
            out.append(f"wpp {_toward_flag(self.w_per_para, up=False)} < {W_PER_PARA_FLOOR_REWRITE:g}: choppy paragraphs; check terms, steps and reasons are explained")
        elif self.w_per_para > W_PER_PARA_CEILING_ATTENTION:
            out.append(f"wpp {_toward_flag(self.w_per_para, up=True)} > {W_PER_PARA_CEILING_ATTENTION:g}: wall of text; check for steps, examples and breaks the learner needs")
        return out


def _toward_flag(x: float, *, up: bool) -> str:
    """Two decimals rounded toward the flagged side, so "11.99 < 12" and
    "120.05 > 120" always hold when printed (plain rounding could print the
    bound itself)."""
    return f"{(math.ceil if up else math.floor)(x * 100) / 100:.2f}"


def _strip_non_prose(text: str) -> str:
    text = _FRONTMATTER_FENCE.sub("", text, count=1)
    text = _FENCED_CODE.sub("", text)
    text = _DETAILS_TAG.sub("", text)
    return text


def _is_prose_paragraph(p: str) -> bool:
    """A prose paragraph is one not starting with markdown structure markers."""
    first = p.lstrip()
    if not first:
        return False
    if first.startswith(("#", "-", "*", "+", "|", ">", ":", "<")):
        return False
    if re.match(r"^\d+\.\s", first):
        return False
    return True


def evaluate_text(text: str) -> DensityMetrics:
    stripped = _strip_non_prose(text)
    nonblank_lines = sum(1 for line in stripped.splitlines() if line.strip())
    textual_words = len(stripped.split())
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    prose = [p for p in paragraphs if _is_prose_paragraph(p)]
    prose_words = sum(len(p.split()) for p in prose)
    return DensityMetrics(
        prose_words=prose_words,
        textual_words=textual_words,
        nonblank_lines=nonblank_lines,
        total_paragraphs=len(paragraphs),
        prose_paragraphs=len(prose),
        w_per_line=(textual_words / nonblank_lines) if nonblank_lines else 0.0,
        w_per_para=(prose_words / len(prose)) if prose else 0.0,
    )


def evaluate_module(path: Path) -> DensityMetrics:
    return evaluate_text(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m scripts.quality.density",
        description="Report density diagnostics and both-tail attention flags for one or more modules (never a gate).",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="module .md files (or dirs to scan)")
    parser.add_argument(
        "--min-prose",
        type=int,
        default=10,
        help="ignore files with fewer than N prose paragraphs (default: 10)",
    )
    parser.add_argument(
        "--flagged-only",
        action="store_true",
        help="only print modules with at least one attention flag",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.md")))
        else:
            targets.append(p)

    flagged = 0
    rows: list[tuple[Path, DensityMetrics]] = []
    for path in targets:
        if path.name == "index.md":
            continue
        m = evaluate_module(path)
        if m.prose_paragraphs < args.min_prose:
            continue
        rows.append((path, m))

    rows.sort(key=lambda r: (not r[1].attention(), r[1].w_per_para))

    print(f"{'prose_w':>7} {'text_w':>7} {'w/ln':>5} {'wpp':>5} {'prose':>5}  path / attention flags")
    for path, m in rows:
        flags = m.attention()
        if args.flagged_only and not flags:
            continue
        flagged += bool(flags)
        print(
            f"{m.prose_words:>7} {m.textual_words:>7} {m.w_per_line:>5.1f} {m.w_per_para:>5.1f} "
            f"{m.prose_paragraphs:>5}  {path}"
        )
        for flag in flags:
            print(f"{'':>34}  - {flag}")

    print(f"\nScanned {len(rows)} modules. Flagged for reviewer attention: {flagged} (diagnostic only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
