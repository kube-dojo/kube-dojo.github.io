"""Deferred-review pass for KUBEDOJO_SKIP_REVIEW=1 batches (#388).

Historical skip-review batches marked ``review.auto_approved=True`` and wrote
``.pipeline/quality-pipeline/post-review-queue.txt``. New skipped reviews remain
pending. This script processes historical queue entries with researched coverage.

For each slug at ``stage=COMMITTED`` with ``review.auto_approved=True``:

* dispatch ``review_prompt`` against the on-disk (already-merged) module
* APPROVE  -> record verdict in ``state.review.deferred``, drop from queue
* CHANGES  -> record verdict, set ``revision_pending: true`` on module
              frontmatter, drop from queue
* reviewer unavailable -> stop the run, leave the queue intact

The queue file is rewritten atomically; un-processed slugs stay queued.
The script does NOT commit frontmatter changes — caller inspects ``git
status`` and commits the batch.

An editorial result does not replace factual-source, runtime or page acceptance.
"""
from __future__ import annotations

import argparse
import random
import signal
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality import state as qstate
from quality.dispatchers import Agent, DispatcherUnavailable, dispatch
from quality.prompts import build_audit_context, review_prompt
from quality.queue import (
    clear_qa_pending_frontmatter,
    set_revision_pending_frontmatter,
)
from quality.stages import _parse_review_verdict, _review_digests, _review_inputs

from scripts.pipeline_common.teaching_contract import validate_teaching_review

QUEUE_PATH = Path(".pipeline/quality-pipeline/post-review-queue.txt")


def read_queue() -> list[str]:
    if not QUEUE_PATH.exists():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in QUEUE_PATH.read_text(encoding="utf-8").splitlines():
        slug = raw.strip()
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def write_queue(slugs: list[str]) -> None:
    if not slugs:
        QUEUE_PATH.write_text("", encoding="utf-8")
        return
    QUEUE_PATH.write_text("\n".join(slugs) + "\n", encoding="utf-8")


def reviewable(st: dict) -> bool:
    if st.get("stage") != "COMMITTED":
        return False
    review = st.get("review") or {}
    return bool(review.get("auto_approved"))


def review_slug(slug: str, *, reviewer_override: str | None, timeout: int, dry_run: bool):
    """Returns ('approve'|'changes'|'skip'|'stop'|'fail', detail)."""
    st = qstate.load_state(slug)
    if st is None:
        return "skip", "no state file"
    if not reviewable(st):
        return "skip", f"stage={st.get('stage')} auto_approved={(st.get('review') or {}).get('auto_approved')}"

    module_rel = st["module_path"]
    module_file = qstate.REPO_ROOT / module_rel
    try:
        module_text, plan = _review_inputs(qstate.REPO_ROOT, module_rel)
        candidate_digest, plan_digest = _review_digests(module_text, plan)
    except (OSError, UnicodeError, ValueError) as exc:
        return "fail", f"review input unavailable: {exc}"

    reviewer = reviewer_override or st["reviewer"]
    if not isinstance(reviewer, str) or not reviewer.strip():
        return "fail", "reviewer is not assigned"
    track = (st.get("route") or {}).get("track", "rewrite")

    if dry_run:
        return "skip", f"DRY-RUN: would dispatch {reviewer} against {module_file}"

    try:
        prompt = review_prompt(
            module_path=st["module_path"],
            module_text=module_text,
            writer_agent=st["writer"],
            track=track,
            original_gaps=build_audit_context(st.get("audit")),
            coverage_plan=plan,
        )
    except ValueError as exc:
        return "fail", str(exc)  # Historical post-review stays queued until its producer is upgraded.
    try:
        result = dispatch(cast(Agent, reviewer), prompt, timeout=timeout, tools_disabled=True)
    except DispatcherUnavailable as e:
        return "stop", str(e)
    if not result.ok:
        return "fail", f"dispatch rc={result.returncode}: {result.stderr.strip()[:300]}"

    verdict = _parse_review_verdict(result)
    if verdict is None:
        return "fail", "could not parse verdict JSON"
    if verdict["verdict"] == "approve":
        errors = validate_teaching_review(verdict, module_text, plan)
        if errors:
            return "fail", "; ".join(errors)

    # Update state under lease — preserve original auto-approved record in
    # review.deferred so the audit trail shows both the synthetic approve
    # and the real (post-rate-limit) verdict.
    with qstate.state_lease(slug, timeout=5.0) as lease:
        st = lease.load()
        if st is None or not reviewable(st):
            return "skip", "state changed under us"
        if st.get("module_path") != module_rel:
            return "fail", "module path changed during review"
        try:
            current_text, current_plan = _review_inputs(qstate.REPO_ROOT, module_rel)
            current_digests = _review_digests(current_text, current_plan)
        except (OSError, UnicodeError, ValueError):
            current_digests = None
        if current_digests != (candidate_digest, plan_digest):
            return "fail", "candidate or research plan changed during review"
        prior = dict(st["review"])
        if verdict["verdict"] == "approve":
            st["review"]["auto_approved"] = False
        st["review"]["deferred"] = {"agent": reviewer, "payload": verdict, "prior_review": prior,
                                    "candidate_sha256": candidate_digest, "plan_sha256": plan_digest}
        st.setdefault("history", []).append({
            "at": qstate.now_iso(),
            "stage": "COMMITTED",
            "note": f"deferred-review {verdict['verdict']} by {reviewer} "
                    f"(rubric={verdict.get('rubric_score')}, teaching={verdict.get('teaching_score')})",
        })
        lease.save(st)

    if verdict["verdict"] == "approve":
        clear_qa_pending_frontmatter(module_file)
        return "approve", "review passed on pre-banner-change candidate; source and acceptance remain separate"

    # CHANGES — flip qa_pending → revision_pending so learners see the rework
    # banner instead of the QA-pending banner.
    clear_qa_pending_frontmatter(module_file)
    if set_revision_pending_frontmatter(module_file):
        marked = "banner flipped to revision_pending"
    else:
        marked = "banner already revision_pending"
    must_fix = verdict.get("must_fix") or []
    return "changes", f"{marked}; {len(must_fix)} must-fix"


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="process at most N slugs (0 = all)")
    ap.add_argument("--shuffle", action="store_true", help="randomize order before applying --limit (for spot-sampling)")
    ap.add_argument("--reviewer", default=None, help="override reviewer agent (default: state.reviewer per slug)")
    ap.add_argument("--timeout", type=int, default=600, help="per-dispatch timeout in seconds")
    ap.add_argument("--dry-run", action="store_true", help="report what would happen, don't dispatch")
    args = ap.parse_args()

    queue = read_queue()
    if not queue:
        print("post-review-queue empty — nothing to do.")
        return 0

    work = list(queue)
    if args.shuffle:
        random.shuffle(work)
    if args.limit:
        work = work[: args.limit]

    print(f"queue size: {len(queue)} slugs; processing {len(work)} this run "
          f"({'dry-run' if args.dry_run else 'live'})")

    counts = {"approve": 0, "changes": 0, "skip": 0, "fail": 0, "stop": 0}
    drop_from_queue: set[str] = set()
    stopped = False

    for i, slug in enumerate(work, 1):
        try:
            outcome, detail = review_slug(
                slug,
                reviewer_override=args.reviewer,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            counts[outcome] += 1
            print(f"[{i}/{len(work)}] {outcome:8s} {slug}  -- {detail}")
            if outcome in ("approve", "changes", "skip"):
                # Drop "skip" too: stale queue entries (already reset/never made it
                # to COMMITTED+auto_approved) shouldn't linger forever. If they
                # ever reach the auto-approved state again, they get re-queued.
                drop_from_queue.add(slug)
            if outcome == "stop":
                stopped = True
                print(f"reviewer unavailable — halting run, leaving {len(queue) - len(drop_from_queue)} slugs queued.")
                break
        except BaseException as e:
            print(f"[{i}/{len(work)}] exception {slug}: {type(e).__name__}: {e}", file=sys.stderr)
            raise

    if not args.dry_run:
        remaining = [s for s in queue if s not in drop_from_queue]
        write_queue(remaining)

    print()
    print(f"summary: approve={counts['approve']} changes={counts['changes']} "
          f"skip={counts['skip']} fail={counts['fail']} stop={counts['stop']}")
    if not args.dry_run:
        print(f"queue after: {len(read_queue())} slug(s) remaining")
        if counts["changes"]:
            print("note: revision_pending banner re-set on module(s) — review `git status` and commit the batch.")
    return 1 if (counts["fail"] or stopped) else 0


if __name__ == "__main__":
    raise SystemExit(main())
