"""Quality gates: visual-aid preservation, anti-gaming sampling, progress ledger.

Per ticket #377 (epic #376). Three concerns, one module:

* :func:`visual_aid_count` / :func:`visual_aid_diff_for_module` — block
  any rewrite that strips Mermaid blocks, ASCII diagrams, or tables.
  Hard gate: invoked from :func:`scripts.quality.stages.merge_one`
  before the ff-merge lands. Per ``.claude/rules/module-quality.md``:
  "NEVER remove or simplify existing visual aids during rewrites — they
  are protected assets."

* :func:`should_sample` / :func:`run_real_llm_rubric` — randomly sample
  ~20 % of rewrites for a real-LLM teaching-rubric check. Independent of
  the writer (codex) and the cross-family reviewer (claude). Gemini does
  the sampling so the spot-check is structurally independent of the
  writer/reviewer pair, matching :func:`tiebreaker_agent`'s rationale.
  Sampling is deterministic per slug: re-running the gate on the same
  slug always picks (or skips) the same modules so re-attempts don't
  silently re-sample.

* :func:`append_ledger` — append a row to ``docs/quality-progress.tsv``
  on every COMMITTED transition. Includes both the heuristic-rubric
  delta and the real-LLM sampled score (when applicable). Makes
  "shipped" auditable instead of gameable: the ledger is the source of
  truth, not the in-process counters.

Visual-aid detection is intentionally simple regex matching — false
positives in absolute counts don't matter; only the **delta** matters.
A rewrite that keeps the same Mermaid block count but renames identifiers
won't regress. A rewrite that drops a Mermaid block will.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import density
from .worktree import branch_name, primary_checkout_root


_REPO_ROOT = primary_checkout_root(Path(__file__).resolve().parents[2])
_VENV_PYTHON = str(_REPO_ROOT / ".venv" / "bin" / "python")
_AUDIT_SCRIPT = _REPO_ROOT / "scripts" / "audit_teaching_quality.py"
_AUDIT_DIR = _REPO_ROOT / ".pipeline" / "teaching-audit"

LEDGER_PATH = _REPO_ROOT / "docs" / "quality-progress.tsv"
LEDGER_HEADER = (
    "ts_utc\tslug\theuristic_before\theuristic_after\treal_llm_sampled\t"
    "real_llm_teaching_score\treal_llm_verdict\twriter\treviewer\t"
    "review_verdict\tnotes\n"
)

DEFAULT_SAMPLE_RATE = 0.20
"""Plan KPI: 20 % of rewrites get a real-LLM rubric delta sample.
Override with ``--sample-rate`` or by setting ``KUBEDOJO_GATES_SAMPLE_RATE``.
"""

REAL_LLM_MIN_TEACHING_SCORE = 4.0
"""Sampled rewrites must score ≥ this on the real-LLM rubric. Failures
do not auto-rollback the merge but pause the *batch* and surface in the
ledger as ``real_llm_verdict=below_threshold`` so the operator can
decide whether to revert or continue.
"""

DEFAULT_SAMPLER_MODEL = "gemini-3-flash-preview"
"""Independent of the writer (codex) and reviewer (claude). Per
``feedback_writer_reviewer_split.md`` and ``feedback_gemini_models.md``,
fall back to ``gemini-2.5-flash`` only when the dispatcher reports
``gemini-3-flash-preview`` is unavailable — the ``audit_teaching_quality.py``
subprocess handles that fallback path itself.
"""


# ---- visual-aid counting ----------------------------------------------


_MERMAID_OPEN = re.compile(r"^```\s*mermaid\b", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$", re.MULTILINE)
_ASCII_DIAGRAM_CHARS = set("─│┌┐└┘├┤┬┴┼━┃┏┓┗┛┣┫┳┻╋")


def _count_ascii_diagrams(text: str) -> int:
    """Count fenced code blocks that look like ASCII diagrams.

    Heuristic: any fenced block (no language tag OR ``text``) whose body
    contains ≥ 3 distinct box-drawing characters, OR ≥ 2 lines matching
    ``+--`` / ``|...|`` pipe-art patterns. Cheap and good enough for the
    delta — we don't need to identify the exact diagram, only detect the
    presence of one.
    """
    blocks = re.findall(r"^```([a-zA-Z0-9_-]*)\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    count = 0
    for lang, body in blocks:
        if lang.strip().lower() not in ("", "text", "ascii", "txt"):
            continue
        chars_used = {c for c in body if c in _ASCII_DIAGRAM_CHARS}
        if len(chars_used) >= 3:
            count += 1
            continue
        pipe_lines = sum(
            1 for line in body.splitlines()
            if (line.strip().startswith("+") and "+" in line.strip()[1:])
            or (line.strip().startswith("|") and line.strip().endswith("|") and "|" in line.strip()[1:-1])
        )
        if pipe_lines >= 3:
            count += 1
    return count


def visual_aid_count(text: str) -> dict[str, int]:
    """Count visual-aid blocks in ``text`` by type.

    Keys:
    * ``mermaid`` — fenced ``mermaid`` blocks.
    * ``ascii_diagram`` — fenced no-language / ``text`` blocks that look
      like ASCII art (box-drawing chars or pipe-art).
    * ``table`` — markdown tables (counted via the ``|---|---|`` separator
      row, which is unambiguous and exactly one per table).

    A rewrite is allowed to *increase* any of these. It is NEVER allowed
    to decrease any of them. ``visual_aid_diff`` enforces this.
    """
    return {
        "mermaid": len(_MERMAID_OPEN.findall(text)),
        "ascii_diagram": _count_ascii_diagrams(text),
        "table": len(_TABLE_SEP.findall(text)),
    }


def visual_aid_diff(before_text: str, after_text: str) -> dict[str, dict[str, int]]:
    """Compare visual-aid counts before/after a rewrite.

    Returns a mapping ``{metric: {"before": N, "after": M, "delta": M-N}}``
    suitable for both human inspection and machine gating. Use
    :func:`regressed_metrics` to get the boolean fail signal.
    """
    before = visual_aid_count(before_text)
    after = visual_aid_count(after_text)
    return {
        metric: {
            "before": before[metric],
            "after": after[metric],
            "delta": after[metric] - before[metric],
        }
        for metric in before
    }


def regressed_metrics(diff: dict[str, dict[str, int]]) -> list[str]:
    """Return the list of metrics whose count regressed. Empty = pass.

    A per-type decrease only counts as a regression if the **total**
    across all visual-aid types (mermaid + ascii + table) also dropped.

    Background: empirically Codex's rewrites sometimes substitute
    ASCII diagrams for clearer Markdown tables — net visual richness
    is preserved or grows even when one specific type's count drops.
    The original strict "any per-type decrease" rule rejected those
    fungible substitutions. The new rule still catches genuine visual
    destruction (drops with no compensation) but lets net-neutral or
    net-positive substitutions pass.
    """
    total_before = sum(d["before"] for d in diff.values())
    total_after = sum(d["after"] for d in diff.values())
    if total_after >= total_before:
        return []
    return [m for m, d in diff.items() if d["delta"] < 0]


def _git_show(repo: Path, ref: str, path: str) -> tuple[str, str | None, str | None]:
    """Read file contents at ``ref:path``.

    Returns ``(status, text, error)`` where ``status`` is one of:

    * ``"ok"`` — file existed at that ref; ``text`` is its contents.
    * ``"missing"`` — file genuinely absent at that ref (greenfield case).
      Detected by the standard git stderr signature
      ``"path '...' does not exist in '...'"`` or
      ``"exists on disk, but not in '...'"`` so we don't conflate with
      bad-ref / repo-error failures.
    * ``"error"`` — git itself failed (bad ref, missing repo, IO). Caller
      must treat as a hard fail, NOT as greenfield.
    """
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )
    if proc.returncode == 0:
        return ("ok", proc.stdout, None)
    stderr = (proc.stderr or "").strip()
    lowered = stderr.lower()
    if "does not exist in" in lowered or "exists on disk, but not in" in lowered:
        return ("missing", None, stderr)
    return ("error", None, stderr or f"git show rc={proc.returncode}")


def visual_aid_diff_for_module(
    primary: Path,
    slug: str,
    module_relpath: str,
    base_ref: str = "main",
) -> dict[str, Any]:
    """Diff visual aids between the rewrite branch tip and ``base_ref``.

    The "before" snapshot is the file as it exists on ``base_ref`` (main
    by default — the pre-rewrite version); the "after" snapshot is the
    file at the writer's branch tip. Returns ``{"diff": {...},
    "regressed": [...], "ok": bool}``.

    If the file doesn't exist on ``base_ref`` (greenfield module), the
    "before" counts default to zero and any "after" content trivially
    passes. If the branch is missing, returns ``ok=False`` with an
    ``error`` key — caller should treat as a hard fail.
    """
    branch = branch_name(slug)
    after_status, after_text, after_err = _git_show(primary, branch, module_relpath)
    if after_status != "ok" or after_text is None:
        return {
            "ok": False,
            "error": f"cannot read {module_relpath} at branch {branch}: {after_err or after_status}",
        }
    before_status, before_text, before_err = _git_show(primary, base_ref, module_relpath)
    if before_status == "error":
        return {
            "ok": False,
            "error": f"cannot read {module_relpath} at {base_ref}: {before_err}",
        }
    if before_status == "missing" or before_text is None:
        before_text = ""  # greenfield — nothing to regress against
    diff = visual_aid_diff(before_text, after_text)
    regs = regressed_metrics(diff)
    return {"ok": not regs, "diff": diff, "regressed": regs}


# ---- anti-gaming sampling ---------------------------------------------


def _resolved_sample_rate(rate: float | None) -> float:
    if rate is not None:
        return rate
    env = os.environ.get("KUBEDOJO_GATES_SAMPLE_RATE")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    return DEFAULT_SAMPLE_RATE


def should_sample(slug: str, rate: float | None = None) -> bool:
    """Deterministic sampling — same slug always returns the same answer
    for a given rate. Uses md5 truncated to a fixed-precision integer
    so the threshold is stable across Python versions / hash randomization.

    Why deterministic: re-running the gate on the same slug after a
    transient failure must NOT silently re-roll the dice and skip a
    module that should've been sampled. The ledger is the audit trail;
    sampling decisions must be reproducible.
    """
    r = _resolved_sample_rate(rate)
    if r <= 0:
        return False
    if r >= 1:
        return True
    digest = hashlib.md5(slug.encode("utf-8"), usedforsecurity=False).hexdigest()
    bucket = int(digest[:8], 16) / 0x100000000  # in [0, 1)
    return bucket < r


def run_real_llm_rubric(
    module_path: Path,
    model: str = DEFAULT_SAMPLER_MODEL,
    timeout: int = 300,
) -> dict[str, Any]:
    """Re-audit ``module_path`` via ``audit_teaching_quality.py``, returning
    the parsed JSON payload (or an error dict).

    Always runs with ``--force`` so the audit reflects the current
    rewrite, not a stale pre-rewrite cache. The audit JSON is also
    persisted to ``.pipeline/teaching-audit/<slug>.json`` by the script
    itself, which is the desired side effect — that file is what the
    pipeline routes off in subsequent runs.
    """
    if not module_path.exists():
        return {"ok": False, "error": f"module path missing: {module_path}"}
    cmd = [
        _VENV_PYTHON, str(_AUDIT_SCRIPT),
        "--module", str(module_path),
        "--model", model,
        "--timeout", str(timeout),
        "--force",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True,
            timeout=timeout + 60,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"audit subprocess timed out (>{timeout + 60}s)"}
    elapsed = round(time.time() - t0, 1)
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"audit subprocess rc={proc.returncode}",
            "stderr": (proc.stderr or "")[-2000:],
            "elapsed_seconds": elapsed,
        }
    try:
        slug = _slug_for_module_path(module_path)
    except ValueError as exc:
        return {
            "ok": False,
            "error": f"could not resolve slug for {module_path}: {exc}",
            "elapsed_seconds": elapsed,
        }
    audit_json_path = _AUDIT_DIR / f"{slug}.json"
    if not audit_json_path.exists():
        return {
            "ok": False,
            "error": f"audit subprocess succeeded but {audit_json_path} not written",
            "elapsed_seconds": elapsed,
        }
    try:
        payload = json.loads(audit_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": f"audit JSON unreadable at {audit_json_path}: {exc}",
            "elapsed_seconds": elapsed,
        }
    teaching_score = payload.get("teaching_score")
    verdict = payload.get("verdict")
    passed = (
        isinstance(teaching_score, (int, float))
        and float(teaching_score) >= REAL_LLM_MIN_TEACHING_SCORE
    )
    return {
        "ok": True,
        "passed": passed,
        "teaching_score": teaching_score,
        "verdict": verdict,
        "model": model,
        "elapsed_seconds": elapsed,
        "audit_json_path": str(audit_json_path.relative_to(_REPO_ROOT)),
    }


def _slug_for_module_path(module_path: Path) -> str:
    """Match :func:`scripts.audit_teaching_quality.slug_for`.

    Raises :class:`ValueError` if ``module_path`` is not under the
    expected content root — the caller (``run_real_llm_rubric``) wraps
    this in a try/except and returns a structured error dict so a
    misrouted slug surfaces as ``audit_error`` in the ledger instead of
    crashing the worker.
    """
    content_root = _REPO_ROOT / "src" / "content" / "docs"
    try:
        rel = module_path.resolve().relative_to(content_root)
    except ValueError as exc:
        raise ValueError(f"{module_path} is not under {content_root}") from exc
    return str(rel).replace("/", "-").removesuffix(".md")


# ---- progress ledger --------------------------------------------------


@dataclass
class LedgerRow:
    ts_utc: str
    slug: str
    heuristic_before: float | None
    heuristic_after: float | None
    real_llm_sampled: bool
    real_llm_teaching_score: float | None
    real_llm_verdict: str | None
    writer: str | None
    reviewer: str | None
    review_verdict: str | None
    notes: str = ""

    def to_tsv(self) -> str:
        def f(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, bool):
                return "1" if v else "0"
            if isinstance(v, float):
                return f"{v:.2f}"
            s = str(v).replace("\t", " ").replace("\n", " ")
            return s
        d = asdict(self)
        keys = [
            "ts_utc", "slug",
            "heuristic_before", "heuristic_after",
            "real_llm_sampled", "real_llm_teaching_score", "real_llm_verdict",
            "writer", "reviewer", "review_verdict", "notes",
        ]
        return "\t".join(f(d[k]) for k in keys) + "\n"


@contextlib.contextmanager
def _ledger_lock(path: Path):
    """Hold an advisory exclusive lock on ``<path>.lock`` for the
    duration of the block.

    Two pipeline workers can land on COMMITTED concurrently and both
    call :func:`append_ledger`. Without serialization the create-vs-
    header check races and either:

    * duplicates the header row (worker A sees missing, opens for
      append, writes header; worker B also sees missing in between,
      writes header again);
    * interleaves bytes mid-line on most filesystems' append semantics.

    We use ``fcntl.flock`` because the ledger lives in the working tree
    on developer machines and on the CI runner — both POSIX. The lock
    file is separate from the ledger file so the lock survives ledger
    truncation/rotation, and so we don't need write access to the
    ledger to take the lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise


def append_ledger(row: LedgerRow, path: Path | None = None) -> None:
    """Append ``row`` to the TSV ledger, creating the file with a header
    if it doesn't exist yet.

    ``path`` defaults to the module-level :data:`LEDGER_PATH`. The
    default is resolved at *call time*, not at function-definition time,
    so monkeypatching ``gates.LEDGER_PATH`` in tests routes writes to a
    fixture path. Without that, integration tests that exercise
    ``merge_one`` (which calls this via ``_post_merge_gates``) would
    pollute the real ``docs/quality-progress.tsv`` audit trail.

    Idempotency note: this is intentionally NOT idempotent on slug.
    A re-run that re-samples the same slug appends a new row — the
    timestamp distinguishes attempts. Querying tools should treat the
    last row per slug as authoritative.

    Concurrency-safe: the create / header-write / append sequence runs
    under :func:`_ledger_lock` so two workers landing on COMMITTED
    simultaneously don't duplicate the header or interleave bytes.
    """
    if path is None:
        path = LEDGER_PATH
    with _ledger_lock(path):
        # Re-check existence INSIDE the lock — outside-the-lock check is
        # the racy v1 bug we're fixing.
        new_file = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8") as fh:
            if new_file:
                fh.write(LEDGER_HEADER)
            fh.write(row.to_tsv())


def build_ledger_row(
    *,
    slug: str,
    state_payload: dict[str, Any],
    real_llm_result: dict[str, Any] | None,
    notes: str = "",
) -> LedgerRow:
    """Construct a :class:`LedgerRow` from the post-merge state + sample.

    ``state_payload`` is the lease-loaded module state dict (the same
    one stages.py reads). ``real_llm_result`` is the dict returned by
    :func:`run_real_llm_rubric`, or None if the slug wasn't sampled.
    """
    audit = state_payload.get("audit") or {}
    heuristic_before = audit.get("teaching_score") if isinstance(audit.get("teaching_score"), (int, float)) else None
    review = state_payload.get("review") or {}
    review_verdict = review.get("verdict")
    writer = state_payload.get("writer")
    reviewer = state_payload.get("reviewer")

    sampled = real_llm_result is not None
    real_score: float | None = None
    real_verdict: str | None = None
    if real_llm_result and real_llm_result.get("ok"):
        ts = real_llm_result.get("teaching_score")
        if isinstance(ts, (int, float)):
            real_score = float(ts)
        rv = real_llm_result.get("verdict")
        if isinstance(rv, str):
            real_verdict = rv
        if not real_llm_result.get("passed", True):
            real_verdict = (real_verdict or "below_threshold") + ":below_threshold"
    elif real_llm_result:
        real_verdict = "audit_error"

    # heuristic_after: not yet known at merge time (the heuristic-rubric
    # API is rebuilt on a refresh tick), so leave None — a periodic
    # backfill job can fill it in. The ledger row is still useful with
    # only ``heuristic_before`` populated because that captures the gap
    # the rewrite was supposed to close.
    return LedgerRow(
        ts_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        slug=slug,
        heuristic_before=heuristic_before,
        heuristic_after=None,
        real_llm_sampled=sampled,
        real_llm_teaching_score=real_score,
        real_llm_verdict=real_verdict,
        writer=writer,
        reviewer=reviewer,
        review_verdict=review_verdict,
        notes=notes,
    )


# ---- pre-merge gate ---------------------------------------------------


class GateError(RuntimeError):
    """A hard gate failed — caller (merge_one) must abort the merge."""


def assert_visual_aids_preserved(
    primary: Path,
    slug: str,
    module_relpath: str,
    base_ref: str = "main",
) -> dict[str, Any]:
    """Hard gate. Raises :class:`GateError` with a human-readable summary
    if any visual-aid metric regressed. Returns the diff dict on success.
    """
    result = visual_aid_diff_for_module(primary, slug, module_relpath, base_ref)
    if not result.get("ok"):
        if result.get("regressed"):
            regs = result["regressed"]
            diff = result["diff"]
            details = ", ".join(f"{m}: {diff[m]['before']}→{diff[m]['after']}" for m in regs)
            raise GateError(f"visual-aid regression on {slug} ({details})")
        if "error" in result:
            raise GateError(f"visual-aid gate could not evaluate {slug}: {result['error']}")
    return result


def density_diagnostics(
    primary: Path,
    slug: str,
    module_relpath: str,
) -> dict[str, Any]:
    """Diagnostics only (#3744): never rejects a module on a density value.

    Reads the file at the writer's branch tip (same snapshot as
    :func:`assert_visual_aids_preserved`'s ``after``) and returns the raw
    signals plus the both-tails ``attention`` flags for the reviewer; a short,
    choppy, long or walled page is flagged, not bounced. Raises
    :class:`GateError` only when the file cannot be read, because then there
    is nothing to measure (the same fail-closed case as the visual-aid gate).
    """
    branch = branch_name(slug)
    status, text, err = _git_show(primary, branch, module_relpath)
    if status != "ok" or text is None:
        raise GateError(
            f"density diagnostics could not read {module_relpath} at {branch}: {err or status}"
        )
    metrics = density.evaluate_text(text)
    return {
        "prose_words": metrics.prose_words,
        "w_per_line": round(metrics.w_per_line, 2),
        "w_per_para": round(metrics.w_per_para, 2),
        "attention": metrics.attention(),
    }


# ---- CLI --------------------------------------------------------------


def _cmd_check_visual(args: argparse.Namespace) -> int:
    primary = _REPO_ROOT
    result = visual_aid_diff_for_module(primary, args.slug, args.module_path, args.base_ref)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def _cmd_should_sample(args: argparse.Namespace) -> int:
    sampled = should_sample(args.slug, args.sample_rate)
    print(json.dumps({"slug": args.slug, "sampled": sampled, "rate": _resolved_sample_rate(args.sample_rate)}))
    return 0 if sampled else 2  # exit 2 means "not sampled" (caller treats as skip)


def _cmd_sample(args: argparse.Namespace) -> int:
    if not args.force and not should_sample(args.slug, args.sample_rate):
        print(json.dumps({"slug": args.slug, "sampled": False}))
        return 0
    module_path = _REPO_ROOT / args.module_path
    result = run_real_llm_rubric(module_path, args.model, args.timeout)
    result["slug"] = args.slug
    print(json.dumps(result, indent=2))
    if not result.get("ok"):
        return 1
    return 0 if result.get("passed") else 2


def _cmd_ledger_append(args: argparse.Namespace) -> int:
    state_payload = json.loads(Path(args.state_json).read_text(encoding="utf-8"))
    real_llm: dict[str, Any] | None = None
    if args.real_llm_json:
        real_llm = json.loads(Path(args.real_llm_json).read_text(encoding="utf-8"))
    row = build_ledger_row(
        slug=args.slug,
        state_payload=state_payload,
        real_llm_result=real_llm,
        notes=args.notes or "",
    )
    append_ledger(row, Path(args.ledger_path) if args.ledger_path else LEDGER_PATH)
    print(json.dumps(asdict(row), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_visual = sub.add_parser("check-visual", help="Visual-aid preservation diff (hard gate)")
    p_visual.add_argument("--slug", required=True)
    p_visual.add_argument("--module-path", required=True, help="Repo-relative path, e.g. src/content/docs/...")
    p_visual.add_argument("--base-ref", default="main")
    p_visual.set_defaults(func=_cmd_check_visual)

    p_should = sub.add_parser("should-sample", help="Deterministic sampling decision for a slug")
    p_should.add_argument("--slug", required=True)
    p_should.add_argument("--sample-rate", type=float, default=None)
    p_should.set_defaults(func=_cmd_should_sample)

    p_sample = sub.add_parser("sample", help="Run real-LLM teaching rubric on a slug if sampled")
    p_sample.add_argument("--slug", required=True)
    p_sample.add_argument("--module-path", required=True)
    p_sample.add_argument("--model", default=DEFAULT_SAMPLER_MODEL)
    p_sample.add_argument("--timeout", type=int, default=300)
    p_sample.add_argument("--sample-rate", type=float, default=None)
    p_sample.add_argument("--force", action="store_true", help="Run even if not sampled")
    p_sample.set_defaults(func=_cmd_sample)

    p_ledger = sub.add_parser("ledger-append", help="Append a row to the progress ledger")
    p_ledger.add_argument("--slug", required=True)
    p_ledger.add_argument("--state-json", required=True, help="Path to the lease-loaded state JSON")
    p_ledger.add_argument("--real-llm-json", help="Path to the run_real_llm_rubric output JSON (omit if not sampled)")
    p_ledger.add_argument("--ledger-path", help="Override ledger path (default: docs/quality-progress.tsv)")
    p_ledger.add_argument("--notes", default="")
    p_ledger.set_defaults(func=_cmd_ledger_append)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
