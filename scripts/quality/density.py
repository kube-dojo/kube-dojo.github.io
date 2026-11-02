"""Module density metric — detects pad-bombs and v3 punchy-bullet style.

Computes three signals over the prose paragraphs of a markdown module:

* **words** — total word count (excludes code blocks, frontmatter, tables,
  list items, callouts, blockquotes — anything that isn't a prose paragraph).
* **w_per_line** (``w/ln``) — words divided by non-blank lines. Below ~12
  signals one-sentence-per-paragraph padding (the Codex v2 pad-bomb signature).
* **w_per_para** (``wpp``) — words per prose paragraph. Below ~22 signals
  punchy-bullet v3 style or generic-essay LLM filler. Above ~50 with low
  paragraph count signals walls-of-text without scaffolding.

These numbers are **diagnostics**, not gates (#3744, operator balance rule
2026-11-02): ``attention()`` flags BOTH tails for the reviewer, and a flag never
rejects, routes, tiers or rewards a page. A page inside every bound is not
thereby accepted; outcome coverage is judged against the outcomes. The
conjunction below is the legacy descriptive band, kept for the triage report.

The pass-threshold is a **conjunction** of three checks. Any single signal is
gameable on its own; the triple is much harder to pad.

Calibration anchors (from `.calibration/teaching-rewrite/` outputs):

| Source                                  | words | w/ln | wpp  |
|-----------------------------------------|------:|-----:|-----:|
| original 9.1 GPU pad-bomb               | 10496 | 7.5  | 10.9 |
| original 1.1 v3 punchy-bullets          |  1729 | 7.5  | 15.6 |
| Gemini-3.1-pro × 1.1 rewrite (good)     |  2568 | 21.8 | 69.8 |
| Codex gpt-5.5 × 1.1 rewrite (good)      |  3604 | 23.7 | 60.3 |

The conservative ``passes_teaching_threshold`` defaults below are
``words >= 1500 AND w_per_line >= 18 AND w_per_para >= 22`` — clears all known
good rewrites in calibration and rejects every flagged module in the corpus
scan (validated 2026-04-25).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Threshold tuning notes:
#   words: 1500 lets short beginner modules through (e.g. ai/foundations/1.1
#          rewrites are 2,500–3,600 words). Modules under 1,500 prose words
#          either don't have enough subject matter to teach or got compressed
#          past the floor — both cases warrant human review.
#   w_per_line: 18 separates the pad-bomb regime (7-13) from real prose (20+).
#          Sits comfortably above the worst v4-Gemini-expansion module (13.6).
#   w_per_para: 22 separates v3 punchy-bullets (8-17) from teaching prose
#          (35-80). Pre-existing good modules average ~30-50.
WORDS_FLOOR = 1500
W_PER_LINE_FLOOR = 18.0
W_PER_PARA_FLOOR = 22.0

# Lower attention bounds (legacy ``*_REWRITE`` names kept for callers). Below
# these the shape is clearly choppy or thin; anchored against the corpus' worst
# pad-bomb (9.1 GPU at w/ln 7.5, wpp 10.9) and punchy-bullets (1.1 v3 at w/ln
# 7.5, wpp 15.6). Diagnostic only: ``attention()`` flags them, nothing rejects.
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


class DensityVerdict(str, Enum):
    """Descriptive density bands for the triage scan's report (#388 stage [1]).

    A label, not an action: ``merge_one`` no longer rejects or retries on a
    band (#3744). ``route_one`` and the triage scan still read it until their
    own changes land. Use :meth:`DensityMetrics.attention` for the both-tails
    reviewer flags.
    """

    PASS = "pass"
    REVIEW = "review"
    REWRITE = "rewrite"

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

    def passes_teaching_threshold(
        self,
        words_floor: int = WORDS_FLOOR,
        w_per_line_floor: float = W_PER_LINE_FLOOR,
        w_per_para_floor: float = W_PER_PARA_FLOOR,
    ) -> bool:
        return (
            self.prose_words >= words_floor
            and self.w_per_line >= w_per_line_floor
            and self.w_per_para >= w_per_para_floor
        )

    def classify(self) -> DensityVerdict:
        """Three-way verdict for #388 triage stage.

        Order of checks matters: REWRITE wins over REVIEW because the
        rewrite floors are strictly looser than the PASS floors. A
        module with ``wpp == 10`` simultaneously fails the PASS floor
        (22) and the rewrite floor (18); the REWRITE verdict is more
        actionable so we return that.
        """
        if (
            self.prose_words < WORDS_FLOOR_REWRITE
            or self.w_per_line < W_PER_LINE_FLOOR_REWRITE
            or self.w_per_para < W_PER_PARA_FLOOR_REWRITE
        ):
            return DensityVerdict.REWRITE
        if (
            self.prose_words >= WORDS_FLOOR
            and self.w_per_line >= W_PER_LINE_FLOOR
            and self.w_per_para >= W_PER_PARA_FLOOR
        ):
            return DensityVerdict.PASS
        return DensityVerdict.REVIEW

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

    def reasons_failed(
        self,
        words_floor: int = WORDS_FLOOR,
        w_per_line_floor: float = W_PER_LINE_FLOOR,
        w_per_para_floor: float = W_PER_PARA_FLOOR,
    ) -> list[str]:
        out: list[str] = []
        if self.prose_words < words_floor:
            out.append(f"prose_words {self.prose_words} < {words_floor} (subject too thin or compressed past floor)")
        if self.w_per_line < w_per_line_floor:
            out.append(f"w/ln {self.w_per_line:.1f} < {w_per_line_floor:.1f} (pad-bomb signature: one-sentence-per-paragraph)")
        if self.w_per_para < w_per_para_floor:
            out.append(f"wpp {self.w_per_para:.1f} < {w_per_para_floor:.1f} (punchy-bullets or essay-filler — paragraphs don't teach)")
        return out

    def reasons_failed_rewrite(self) -> list[str]:
        """Reasons against the REWRITE-tier floors specifically.

        Used by the post-merge density hard gate (#388 stage [6]) so the
        error message names the floor that actually fired the bounce —
        ``reasons_failed`` reports against the PASS floors, which would
        flag REVIEW-band signals as "violations" when only REWRITE-tier
        signals can bounce a merge.
        """
        return self.reasons_failed(
            words_floor=WORDS_FLOOR_REWRITE,
            w_per_line_floor=W_PER_LINE_FLOOR_REWRITE,
            w_per_para_floor=W_PER_PARA_FLOOR_REWRITE,
        )


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
        description="Score one or more modules against the teaching-density triple gate.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="module .md files (or dirs to scan)")
    parser.add_argument(
        "--min-prose",
        type=int,
        default=10,
        help="ignore files with fewer than N prose paragraphs (default: 10)",
    )
    parser.add_argument(
        "--fail-only",
        action="store_true",
        help="only print modules that fail the gate",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.md")))
        else:
            targets.append(p)

    fails = 0
    rows: list[tuple[Path, DensityMetrics]] = []
    for path in targets:
        if path.name == "index.md":
            continue
        m = evaluate_module(path)
        if m.prose_paragraphs < args.min_prose:
            continue
        rows.append((path, m))

    rows.sort(key=lambda r: (r[1].passes_teaching_threshold(), r[1].w_per_para))

    print(f"{'prose_w':>7} {'text_w':>7} {'w/ln':>5} {'wpp':>5} {'prose':>5}  verdict  path")
    for path, m in rows:
        ok = m.passes_teaching_threshold()
        if args.fail_only and ok:
            continue
        verdict = "PASS" if ok else "FAIL"
        if not ok:
            fails += 1
        print(
            f"{m.prose_words:>7} {m.textual_words:>7} {m.w_per_line:>5.1f} {m.w_per_para:>5.1f} "
            f"{m.prose_paragraphs:>5}  {verdict:>7}  {path}"
        )

    print(f"\nScanned {len(rows)} modules. Failed gate: {fails}.")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
