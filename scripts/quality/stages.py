"""Per-stage orchestration: audit / route / write / verify / review / merge.

The state machine lives in :mod:`state` (durable states + leases + CAS).
This module drives state forward by calling dispatchers, running the
citation verify pass inside a per-module worktree, and calling the
worktree helpers to merge cleanly.

Directly closes the remaining Codex must-fixes:

* **#1** — :func:`review_one` reads the module from the writer's
  worktree, not from ``main``. The v1 bug was catastrophic: reviewer
  always approved because the worktree changes were invisible to it.
* **#4** — :func:`handle_review_changes` routes ``REVIEW_CHANGES`` back
  to ``WRITE_PENDING`` with the reviewer's ``must_fix`` list as
  retry context, bumping ``retry_count``. After ``RETRY_CAP`` retries,
  :func:`tiebreaker_one` calls Gemini to break the loop.

And the crash-resume correctness:

* **#5 (runtime half)** — :func:`recover_in_progress` reconciles
  ``WRITE_IN_PROGRESS`` / ``REVIEW_IN_PROGRESS`` state on startup. If
  the writer's branch has a commit, advance to ``WRITE_DONE`` (don't
  redo the work); else revert to ``WRITE_PENDING``. Pairs with the
  ``attempt_id`` stamping from :mod:`state.start_in_progress`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from scripts.pipeline_common.research_plan import load_research_plan
from scripts.pipeline_common.teaching_contract import validate_teaching_review

from . import density, gates, queue, state
from .citations import process_module_citations
from .dispatchers import (
    DispatcherUnavailable,
    DispatchResult,
    dispatch,
    tiebreaker_agent,
)
from .extractors import (
    JsonExtractError,
    ModuleExtractError,
    extract_last_json,
    extract_module_markdown,
)
from .prompts import (
    build_audit_context,
    review_prompt,
    rewrite_prompt,
    structural_prompt,
)
from .worktree import (
    WorktreeError,
    branch_name,
    create_worktree,
    current_branch,
    has_uncommitted,
    merge_ff_only,
    primary_checkout_root,
    rebase_onto_main,
    remove_worktree,
    worktree_dir,
)

_REPO_ROOT = primary_checkout_root(Path(__file__).resolve().parents[2])
_AUDIT_DIR = _REPO_ROOT / ".pipeline" / "teaching-audit"
_AUDIT_SCRIPT = _REPO_ROOT / "scripts" / "audit_teaching_quality.py"
_VENV_PYTHON = str(_REPO_ROOT / ".venv" / "bin" / "python")
logger = logging.getLogger(__name__)

RETRY_CAP = 2
"""Codex↔Claude retries before Gemini tiebreaks. Per #375 locked requirements."""

SCORE_SKIP_THRESHOLD = 4.0
"""Audit score at or above which the rewrite stage is skipped. Citation
verify still runs unconditionally."""

_HANG_RETRY_SLEEP_SEC = 90
"""Sleep before re-dispatching when the writer dispatch hangs (0 B stdout,
returns "timed out" in stderr). Smoke rounds 2 and 4 on argo-events both
exhibited this pattern within ~10 min of a prior heavy claude-code call —
hypothesis is an Anthropic-side rate window. ONE retry per call site,
both diags persisted to disk; if both hang we surface FAILED with both
filenames in ``failure_reason``. Tests monkeypatch this to 0."""


class StageError(RuntimeError):
    """Stage couldn't complete for non-retryable reasons (parse fail, git fail, etc.).

    Callers mark the module ``FAILED`` with ``str(exc)`` as the reason.
    """


# ---- helpers -----------------------------------------------------------


def _primary() -> Path:
    return _REPO_ROOT


def _module_path(st: dict[str, Any]) -> Path:
    return _REPO_ROOT / st["module_path"]


def _module_path_in_worktree(slug: str, module_relpath: str) -> Path:
    return worktree_dir(_primary(), slug) / module_relpath


def _review_inputs(wt: Path, module_rel: str) -> tuple[str, dict]:
    plan, errors = load_research_plan(wt, module_rel)
    if errors:
        raise ValueError("; ".join(errors))
    path = wt / module_rel
    if path.is_symlink() or not path.resolve().is_relative_to(wt.resolve()):
        raise ValueError("review candidate escapes worktree")
    return path.read_bytes().decode("utf-8"), plan


def _review_digests(text: str, plan: dict) -> tuple[str, str]:
    raw = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(text.encode()).hexdigest(), hashlib.sha256(raw).hexdigest()


def _defer_review_failure(st: dict[str, Any], reason: str, failure: dict) -> None:
    previous = st.get("review_failures") or ([st["review_failure"]] if st.get("review_failure") else [])
    state.transition(st, "REVIEW_IN_PROGRESS", "REVIEW_PENDING", review_blocked=reason,
                     review_failure=failure, review_failures=[*previous, failure], review_contract_paused=True,
                     review_contract_version=2)


def _merge_review_error(st: dict[str, Any]) -> str | None:
    """Fail closed on old, synthetic or structurally incomplete approvals."""
    review = st.get("review")
    if (not isinstance(review, dict) or review.get("auto_approved") or review.get("verdict") != "approve"
            or not isinstance(review.get("payload"), dict) or review["payload"].get("verdict") != "approve"
            or review["payload"].get("auto_approved")):
        return "review is missing or automatically approved"
    wt = worktree_dir(_primary(), st["slug"])
    try:
        text, plan = _review_inputs(wt, st["module_path"])
        if has_uncommitted(wt) or _review_digests(text, plan) != (review.get("candidate_sha256"), review.get("plan_sha256")):
            return "candidate or research plan changed since review"
    except (OSError, UnicodeError, ValueError, WorktreeError) as exc:
        return f"review input unavailable: {exc}"
    errors = validate_teaching_review(review["payload"], text, plan)
    return "; ".join(errors) if errors else None


def _audit_json_for(slug: str) -> Path:
    return _AUDIT_DIR / f"{slug}.json"


def _audit_score(audit: dict[str, Any]) -> float:
    """Extract the numeric teaching-score from an audit payload.

    The audit script's schema uses ``teaching_score`` (v3 script); older
    variants used ``score``. Return a conservative fallback (1.0) if
    neither is present so the pipeline treats unknown-schema modules as
    needing rewrite rather than skipping.
    """
    for key in ("teaching_score", "score", "rubric_score"):
        v = audit.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return 1.0


# ---- audit stage -------------------------------------------------------


def audit_one(slug: str, *, timeout: int = 600) -> None:
    """UNAUDITED → AUDITED. Reuses ``.pipeline/teaching-audit/<slug>.json``
    if already present; otherwise subprocesses ``audit_teaching_quality.py``
    to produce one.

    Kept as a subprocess (not an import) so one module's audit crash
    doesn't contaminate the in-process state.
    """
    audit_file = _audit_json_for(slug)
    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None:
            raise StageError(f"state missing for {slug}")
        if st["stage"] != "UNAUDITED":
            return  # another worker advanced it already

        if not audit_file.exists():
            module_rel = st["module_path"]
            cmd = [
                _VENV_PYTHON,
                str(_AUDIT_SCRIPT),
                "--module",
                module_rel,
            ]
            proc = subprocess.run(
                cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=timeout + 30, check=False
            )
            if proc.returncode != 0 or not audit_file.exists():
                _fail_and_cleanup(st, f"audit failed: {proc.stderr.strip()[:400]}")
                return

        audit = json.loads(audit_file.read_text(encoding="utf-8"))
        state.transition(st, "UNAUDITED", "AUDITED", audit=audit, note="audit promoted")


# ---- route stage -------------------------------------------------------


def route_one(slug: str) -> None:
    """AUDITED → ROUTED / SKIPPED / CITATION_CLEANUP_ONLY.

    Route rules (post-#388):

    * Density classifier runs first. ``REWRITE`` overrides the audit score
      and forces ``track="rewrite"`` — modules that game the audit rubric
      with pad-bombs / punchy-bullets / essay-filler still get rewritten.
    * If density is ``PASS`` AND audit score ≥ 4.0 AND no missing
      structural sections → ``CITATION_CLEANUP_ONLY`` (citation pass still
      runs — everything goes through verify).
    * If audit score ≥ 4.0 but structural sections are missing →
      ``ROUTED`` with track=structural.
    * Otherwise → ``ROUTED`` with track=rewrite.

    Writer assignment is queue-driven (per #388 routing rule): agy (the
    Google lane that replaced the retired gemini-cli, #2125) for beginner
    tracks, Codex for advanced, Claude as tertiary fallback. Reviewer is
    the universal cross-family default — Claude for any non-Claude writer,
    agy when the writer is Claude.
    """
    # Phase 1 (no lease): read state + density + missing-section list to
    # decide the cleanup-only short-circuit. We skip ``queue.ensure_queued``
    # at this point because it shouldn't pollute the queue with modules
    # that won't need a writer (Codex must #2). The lease block below
    # re-reads state under CAS so the cheap pre-lease check just lets
    # us skip leasing entirely on the no-write path.
    pre_st = state.load_state(slug)
    if pre_st is None:
        raise StageError(f"state missing for {slug}")
    if pre_st["stage"] != "AUDITED":
        return

    module_path = _module_path(pre_st)
    text = module_path.read_text(encoding="utf-8")
    missing = _missing_structural_sections(text)
    audit_pre = pre_st.get("audit") or {}
    score_pre = _audit_score(audit_pre)
    density_metrics = density.evaluate_text(text)
    density_verdict = density_metrics.classify()
    density_payload = {
        "verdict": density_verdict.value,
        "prose_words": density_metrics.prose_words,
        "w_per_line": round(density_metrics.w_per_line, 2),
        "w_per_para": round(density_metrics.w_per_para, 2),
    }

    needs_writer = _needs_writer(
        density_verdict=density_verdict,
        score=score_pre,
        missing=missing,
    )

    # Pre-lease queue setup ONLY when the module is actually heading to
    # a writer. ``ensure_queued`` acquires its own ``state_lease`` so it
    # must run outside the lease block below (fcntl.flock isn't
    # re-entrant per process). Codex must #2: skipping cleanup-only and
    # PASS+REVIEW-with-clean-structure paths keeps the queue scoped to
    # actual writer work.
    if needs_writer:
        # set_banner=False — banners are committed by ``triage --apply``
        # in their own user-visible PR; mutating frontmatter here would
        # dirty primary and break merge_one's pre-flight check.
        queue.ensure_queued(slug, module_path, set_banner=False)

    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None:
            raise StageError(f"state missing for {slug}")
        if st["stage"] != "AUDITED":
            return

        # Re-read inside the lease (cheap) so the transition uses the
        # canonical authoritative values.
        audit = st.get("audit") or {}
        score = _audit_score(audit)

        if not needs_writer:
            # PASS-tier or REVIEW-tier with no other concerns → cleanup
            # only. Codex must #1: REVIEW-tier with score≥4 + complete
            # structure routes here (NOT to a no-op structural prompt).
            # The teaching-judge LLM (deferred to Phase 2a) will be
            # responsible for sending REVIEW-tier modules to rewrite
            # when warranted.
            reason_bits = [f"score {score:.1f}", "structure complete"]
            if density_verdict == density.DensityVerdict.PASS:
                reason_bits.append("density PASS")
            else:
                reason_bits.append("density REVIEW (judge deferred)")
            state.transition(
                st, "AUDITED", "CITATION_CLEANUP_ONLY",
                route={
                    "reason": ", ".join(reason_bits),
                    "track": "cleanup_only",
                    "density": density_payload,
                },
                note=f"skip rewrite ({', '.join(reason_bits)})",
            )
            return

        if density_verdict == density.DensityVerdict.REWRITE:
            track = "rewrite"
            track_reason = (
                f"density REWRITE: {'; '.join(density_metrics.reasons_failed())}"
            )
        else:
            # density is PASS or REVIEW here AND needs_writer is True,
            # so either score<4 or missing!=[] forced us into this path.
            track = "rewrite" if score < SCORE_SKIP_THRESHOLD else "structural"
            track_reason = f"score {score:.1f}, missing={missing}"

        # claim() is a read-only peek (no lease needed). Returns None
        # when the queue's blocked_until is still in the future, which
        # leaves the slug at AUDITED so the run loop picks it up later.
        claim_result = queue.claim(slug)
        if claim_result.writer is None:
            return  # blocked, no transition; retry on next sweep
        agent, writer_model = queue.model_to_agent(claim_result.writer)
        # Cross-family reviewer: claude reviews non-claude authors; when the
        # author IS claude, route to agy (the Google lane that replaced the
        # retired gemini-cli, #2125) so the review stays cross-family.
        reviewer = "claude" if agent != "claude" else "agy"

        state.transition(
            st, "AUDITED", "ROUTED",
            route={
                "track": track,
                "score": score,
                "missing": missing,
                "density": density_payload,
                "reason": track_reason,
            },
            writer=agent,
            writer_model=writer_model,
            reviewer=reviewer,
            note=f"track={track} writer={agent}/{writer_model}",
        )
        # ROUTED → WRITE_PENDING in the same lease so the run-loop can
        # pick this up as a writable module immediately.
        state.transition(st, "ROUTED", "WRITE_PENDING", note="queued for write")


def _needs_writer(
    *,
    density_verdict: density.DensityVerdict,
    score: float,
    missing: list[str],
) -> bool:
    """True if the module must reach a writer (rewrite OR structural).

    Single source of truth for the route decision so the pre-lease
    short-circuit and the in-lease transition agree on whether to
    enqueue. Modules that don't need a writer go to CITATION_CLEANUP_ONLY.
    """
    if density_verdict == density.DensityVerdict.REWRITE:
        return True
    if score < SCORE_SKIP_THRESHOLD:
        return True
    return bool(missing)


def _missing_structural_sections(text: str) -> list[str]:
    """Detect missing required sections by heading pattern.

    Deliberately simple — matches on heading text rather than any
    structural parsing. The ``quiz_details_check`` is filtered out of
    the ``has_diagram`` false-positive class (v1 bug noted in Codex
    should-fix list: quiz ``<details>`` were mis-counted as diagrams).
    """
    lowered = text.lower()
    missing: list[str] = []
    if "## quiz" not in lowered and "## self-check" not in lowered:
        missing.append("quiz")
    if "## hands-on" not in lowered and "## lab" not in lowered and "## exercise" not in lowered:
        missing.append("hands-on-exercise")
    if "## common mistake" not in lowered:
        missing.append("common-mistakes")
    if "## did you know" not in lowered:
        missing.append("did-you-know")
    return missing


# ---- write stage -------------------------------------------------------


def write_one(slug: str, *, timeout: int = 900) -> None:
    """WRITE_PENDING → WRITE_IN_PROGRESS → WRITE_DONE.

    Holds the lease for the full subprocess duration. On SIGKILL the
    state stays at ``WRITE_IN_PROGRESS`` with the current ``attempt_id``;
    :func:`recover_in_progress` reconciles on the next run.

    If the dispatcher is unavailable (peak hours, budget), REVERTS the
    state to ``WRITE_PENDING`` and leaves the module for a later
    invocation — the module is not FAILED.
    """
    with state.state_lease(slug, timeout=5.0) as lease:
        st = lease.load()
        if st is None or st["stage"] != "WRITE_PENDING":
            return

        attempt_id = state.start_in_progress(st, "WRITE_PENDING", "WRITE_IN_PROGRESS")
        # Codex round-2 must #1: mutate ``st`` in place so the queue
        # increments survive the next ``state.transition`` (which saves
        # ``st`` back). The earlier ``_record_attempt_start_unlocked``
        # variant did its own load+mutate+save, then transition's save
        # of the stale in-memory ``st`` overwrote the queue updates.
        try:
            queue._record_attempt_start_in_state(st)
            state.save_state(st)  # persist the increment immediately
        except FileNotFoundError:
            pass  # not queue-tracked (e.g. legacy paths) — proceed
        try:
            wt, commit_sha = _write_in_worktree(st, timeout=timeout, attempt_id=attempt_id)
        except DispatcherUnavailable as exc:
            # Revert — module stays retryable, branch cleaned up.
            remove_worktree(_primary(), slug, delete_branch=True)
            # Codex round-2 must #1: record block in-place BEFORE the
            # transition so the next save (inside transition) carries
            # the blocked_until forward. Reverse order would lose the
            # block on the transition's save of the older queue subdoc.
            try:
                queue._record_block_in_state(st, f"dispatcher unavailable: {exc}")
            except FileNotFoundError:
                pass
            state.transition(
                st, "WRITE_IN_PROGRESS", "WRITE_PENDING",
                note="dispatcher unavailable; will retry",
            )
            raise
        except (ModuleExtractError, WorktreeError, StageError) as exc:
            # _write_in_worktree already calls remove_worktree in its
            # BaseException handler; call _fail_and_cleanup so any
            # residual branch metadata is also scrubbed.
            _fail_and_cleanup(st, f"write: {exc}")
            return

        state.transition(
            st, "WRITE_IN_PROGRESS", "WRITE_DONE",
            write={
                "agent": st["writer"],
                "attempt_id": attempt_id,
                "commit_sha": commit_sha,
                "worktree": str(wt.relative_to(_REPO_ROOT)),
            },
            note=f"{st['writer']} wrote {commit_sha[:8]}",
        )


def _looks_like_dispatch_hang(result: DispatchResult) -> bool:
    """The "0 B stdout + 'timed out' stderr" signature observed on argo-events
    smoke rounds 2 and 4. We retry ONCE for this signature only — we don't
    retry generic non-zero exits (e.g., ``RuntimeError: kaboom``) because
    those signal a genuine writer crash, not a stuck rate window."""
    if result.ok:
        return False
    if result.stdout:  # any output at all means generation was happening
        return False
    return "timed out" in (result.stderr or "").lower()


def _save_write_diag(
    *,
    slug: str,
    writer: str,
    attempt_id: str,
    result: DispatchResult,
    prompt: str,
    error: str,
) -> Path:
    """Persist the writer's raw stdout/stderr after a write failure.

    The state file's ``failure_reason`` says WHAT failed (e.g.,
    ``no frontmatter delimiter found``); this artifact says WHY — what
    the writer actually returned. Without it, postmortem requires
    re-dispatching the same prompt, which is wasteful and may not
    reproduce when the dispatcher (Claude/Codex) is non-deterministic.

    Failure modes saved:
    * dispatcher non-zero exit (rc != 0) — typically a tool crash or
      refusal not detected as DispatcherUnavailable.
    * extractor rejected the output (``ModuleExtractError``) — output
      missing frontmatter, truncated, prose-only, etc.

    Returns the artifact path so the caller can include it in error
    messages for human follow-up.
    """
    out_dir = _REPO_ROOT / ".pipeline" / "quality-pipeline" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.write.{attempt_id}.failed.json"
    payload = {
        "slug": slug,
        "writer": writer,
        "attempt_id": attempt_id,
        "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error": error,
        "dispatch": {
            "ok": result.ok,
            "returncode": result.returncode,
            "duration_sec": round(result.duration_sec, 2),
            "agent": result.agent,
            "model": result.model,
        },
        "stdout": result.stdout,
        "stderr": result.stderr,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_len_chars": len(prompt),
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def _write_in_worktree(
    st: dict[str, Any], *, timeout: int, attempt_id: str
) -> tuple[Path, str]:
    """Dispatch the writer inside a worktree and commit. Returns ``(wt, sha)``.

    Must NOT commit the state transition — caller handles that under the
    lease so a lease-rejection doesn't leave a stale git commit.
    """
    slug = st["slug"]
    writer = st["writer"]
    writer_model = st.get("writer_model")  # set by route_one (queue-driven)
    track = (st.get("route") or {}).get("track", "rewrite")
    module_rel = st["module_path"]

    # Build prompt from the ORIGINAL module content, not the worktree's
    # copy — they start identical but this makes the prompt's "current
    # module content" unambiguous: it's what the audit scored.
    original_text = _module_path(st).read_text(encoding="utf-8")
    audit_gaps = build_audit_context(st.get("audit"))
    retry_must_fix = (st.get("review") or {}).get("must_fix") or []

    if track == "structural":
        missing = (st.get("route") or {}).get("missing") or []
        prompt = structural_prompt(
            module_path=module_rel,
            module_text=original_text,
            missing_sections=missing,
        )
    else:
        prompt = rewrite_prompt(
            module_path=module_rel,
            module_text=original_text,
            teaching_gaps=audit_gaps + [f"(retry) {x}" for x in retry_must_fix],
        )

    # Worktree PERSISTS through the whole module lifecycle (write → citation
    # verify → review → merge). Only teardown paths are:
    # 1. write_one() failure or DispatcherUnavailable → remove_worktree(
    #    delete_branch=True) so retry starts from a clean branch. The
    #    locked requirement says cleanup on success AND failure AND
    #    SIGKILL — so branches don't leak even for FAILED modules.
    # 2. merge_one() success → remove_worktree(delete_branch=True)
    # Using ``worktree_session`` here would destroy the worktree before
    # the reviewer (Codex must-fix #1) could read from it.
    wt = create_worktree(_primary(), slug)
    try:
        # tools_disabled=True forces stdout-only output. Without it,
        # Claude's print mode is agentic and will modify files in ``cwd``
        # (the worktree) directly, returning only a summary on stdout —
        # which the extractor then rejects as "no frontmatter delimiter
        # found" while the actual rewrite gets nuked with the worktree.
        result = dispatch(writer, prompt, timeout=timeout, cwd=wt, tools_disabled=True, model=writer_model)
        # Hang-retry path: the "0 B stdout + 'timed out' stderr" signature
        # observed on argo-events smoke rounds 2 and 4 — likely an
        # Anthropic-side stall on the second heavy claude-code call within
        # a rate window. ONE retry with a fresh dispatch; both raw outputs
        # persisted under distinct sub-IDs of the lease's ``attempt_id`` so
        # the postmortem keeps both. Generic dispatch failures (rc != 0
        # with stdout or non-timeout stderr) skip this branch and fall
        # through to the existing failure path.
        if _looks_like_dispatch_hang(result):
            hang_attempt_1 = f"{attempt_id}-r0"
            _save_write_diag(
                slug=slug, writer=writer, attempt_id=hang_attempt_1,
                result=result, prompt=prompt, error="dispatch_hang_attempt1",
            )
            time.sleep(_HANG_RETRY_SLEEP_SEC)
            result = dispatch(writer, prompt, timeout=timeout, cwd=wt, tools_disabled=True, model=writer_model)
            if _looks_like_dispatch_hang(result) or not result.ok:
                hang_attempt_2 = f"{attempt_id}-r1"
                diag2 = _save_write_diag(
                    slug=slug, writer=writer, attempt_id=hang_attempt_2,
                    result=result, prompt=prompt, error="dispatch_hang_attempt2",
                )
                raise StageError(
                    f"{writer} dispatch hung twice (rc={result.returncode}): "
                    f"{(result.stderr or '').strip()[:400]} — raw saved to "
                    f"{slug}.write.{hang_attempt_1}.failed.json and {diag2.name}"
                )
        if not result.ok:
            diag = _save_write_diag(
                slug=slug, writer=writer, attempt_id=attempt_id,
                result=result, prompt=prompt, error="dispatch_failed",
            )
            raise StageError(
                f"{writer} dispatch failed (rc={result.returncode}): "
                f"{result.stderr.strip()[:400]} — raw saved to {diag.name}"
            )
        try:
            extract = extract_module_markdown(result.stdout)
        except ModuleExtractError as exc:
            diag = _save_write_diag(
                slug=slug, writer=writer, attempt_id=attempt_id,
                result=result, prompt=prompt, error=f"extract_failed: {exc}",
            )
            raise ModuleExtractError(
                f"{exc} — raw saved to {diag.name}"
            ) from exc
        target = wt / module_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(extract.text, encoding="utf-8")
        commit_msg = (
            f"quality({track}): {writer} rewrite {slug} (attempt {attempt_id})\n"
            f"\nRefs #375."
        )
        subprocess.run(
            ["git", "add", module_rel], cwd=wt, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg], cwd=wt, check=True, capture_output=True
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=wt, check=True, capture_output=True, text=True
        ).stdout.strip()
        return wt, sha
    except BaseException:
        # Single broad cleanup handler — git add/commit/rev-parse,
        # file writes, and dispatch can all raise, and all must reach
        # remove_worktree(delete_branch=True) before re-raising. Codex
        # must-fix #6/#8 — v1 and earlier v2 only wrapped dispatch.
        remove_worktree(_primary(), slug, delete_branch=True)
        raise


# ---- citation verify stage --------------------------------------------


def citation_verify_one(slug: str, *, verifier_fn=None, fetcher_fn=None) -> None:
    """Run the strict verify-or-remove citation pass for one module.

    Handles two entry paths + resume:

    * **Rewrite path** — entered at ``WRITE_DONE``. The writer's worktree
      already exists with the rewrite committed. Citation pass runs
      inside it; changes get amended into the writer's commit. Exit:
      ``REVIEW_PENDING``.
    * **Cleanup-only path** — entered at ``CITATION_CLEANUP_ONLY``
      (score ≥ 4.0 + structure complete). No worktree exists yet; we
      create one fresh from ``main`` so the primary checkout never
      mutates (Codex fatal #1). If nothing changes, we tear down the
      worktree and exit ``SKIPPED``. If something changes, we commit
      in the worktree and exit ``REVIEW_APPROVED`` — reviewer is
      skipped because the writer is the citation verifier itself.
    * **Resume** — if a SIGKILL landed after the stage entered
      ``CITATION_VERIFY``, the saved ``citation_origin`` field tells us
      which of the above paths to continue. The work is idempotent
      (re-fetching URLs + re-verifying produces the same verdicts) so
      re-running is safe. Closes Codex must #3.

    ``verifier_fn`` is injectable for testing; defaults to the live
    Gemini-flash verifier in :mod:`citations`.
    """
    from .citations import (  # local import avoids import-time side effects
        default_verifier,
        fetch_page,
    )

    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None:
            return
        current = st["stage"]
        if current == "CITATION_VERIFY":
            # Resume — origin was captured on first entry.
            from_stage = st.get("citation_origin") or "WRITE_DONE"
        elif current in ("WRITE_DONE", "CITATION_CLEANUP_ONLY"):
            from_stage = current
            state.transition(
                st, from_stage, "CITATION_VERIFY",
                citation_origin=from_stage,
                note=f"verifying citations (from {from_stage})",
            )
        else:
            return

    module_rel = st["module_path"]

    # Ownership invariants computed BEFORE any worktree mutation.
    # ``preexisting_worktree`` captures whether a worktree existed on
    # entry to this stage. Combined with ``from_stage`` it gives an
    # invariant predicate — "did THIS function create the throwaway
    # cleanup-only worktree?" — that does not depend on a flag flipped
    # AFTER ``create_worktree`` returns. Codex round 5: a
    # KeyboardInterrupt landing between ``wt = create_worktree(...)``
    # success and a post-call assignment would have leaked the physical
    # worktree under the prior flag-based scheme. The .exists() probe
    # in the BaseException handler is belt-and-braces — if
    # create_worktree raised before producing any state, the worktree
    # is absent and remove_worktree is skipped. ``worktree_owned_by_next_stage``
    # flips to True once a successful state transition durably hands
    # the worktree off (REVIEW_PENDING → review → merge cleans up, or
    # REVIEW_APPROVED → merge cleans up), OR when we've already
    # scrubbed the worktree ourselves inline (SKIPPED / missing-file /
    # st2-is-None).
    wt = worktree_dir(_primary(), slug)
    preexisting_worktree = wt.exists()
    we_own_throwaway = (from_stage == "CITATION_CLEANUP_ONLY") and not preexisting_worktree
    worktree_owned_by_next_stage = False

    try:
        if not preexisting_worktree:
            if from_stage != "CITATION_CLEANUP_ONLY":
                # A missing worktree on the rewrite path is unrecoverable.
                with state.state_lease(slug) as lease:
                    st2 = lease.load()
                    if st2 is not None:
                        _fail_and_cleanup(st2, f"citation_verify: worktree missing for {slug}")
                return
            try:
                wt = create_worktree(_primary(), slug)
            except WorktreeError as exc:
                # ``create_worktree`` cleans up its own partial state on
                # WorktreeError by contract — nothing for us to scrub.
                with state.state_lease(slug) as lease:
                    st2 = lease.load()
                    if st2 is not None:
                        _fail_and_cleanup(st2, f"citation_verify: {exc}")
                return

        module_file = wt / module_rel
        if not module_file.exists():
            if we_own_throwaway:
                remove_worktree(_primary(), slug, delete_branch=True)
            worktree_owned_by_next_stage = True
            with state.state_lease(slug) as lease:
                st2 = lease.load()
                if st2 is not None:
                    _fail_and_cleanup(st2, f"citation_verify: module file missing at {module_file}")
            return

        result = process_module_citations(
            module_file,
            verifier=verifier_fn or default_verifier,
            fetcher=fetcher_fn or fetch_page,
        )

        citations_meta = {
            "had_sources": result.had_sources_section,
            "kept": len(result.kept),
            "removed": len(result.removed),
            "section_dropped": result.section_dropped,
            "removed_details": [
                {"url": p.entry.url, "verdict": p.verdict.value, "reason": p.reasoning[:200]}
                for p in result.removed
            ],
        }

        # Apply changes + commit if needed. All file + git ops run inside
        # the worktree; primary is never touched.
        if result.changed:
            module_file.write_text(result.new_text, encoding="utf-8")
            if from_stage == "WRITE_DONE":
                subprocess.run(["git", "add", module_rel], cwd=wt, check=True, capture_output=True)
                subprocess.run(
                    ["git", "commit", "--amend", "--no-edit"],
                    cwd=wt, check=True, capture_output=True,
                )
            else:
                msg = (
                    f"quality(citations): verify-or-remove for {slug}\n\n"
                    f"Removed {citations_meta['removed']} unverifiable citation(s).\n"
                    f"Refs #375."
                )
                subprocess.run(["git", "add", module_rel], cwd=wt, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", msg], cwd=wt, check=True, capture_output=True)

        # Advance state. Cleanup-only with no citation change is a SKIP —
        # no branch to merge, tear down the throwaway worktree.
        if from_stage == "WRITE_DONE":
            # Worktree belongs to the writer's lifecycle (write → review
            # → merge). If the state file is missing we can't transition,
            # but the worktree is write_one's to manage — not ours.
            with state.state_lease(slug) as lease:
                st2 = lease.load()
                if st2 is None:
                    # No state to transition. We didn't create the
                    # worktree here (rewrite path), so let the writer's
                    # lifecycle handle it. Flag prevents the handler
                    # from double-cleaning.
                    worktree_owned_by_next_stage = True
                    return
                state.transition(
                    st2, "CITATION_VERIFY", "REVIEW_PENDING",
                    citations=citations_meta,
                    note=f"kept={len(result.kept)} removed={len(result.removed)}",
                )
            worktree_owned_by_next_stage = True
        elif result.changed:
            # Compute the new tip BEFORE acquiring the lease — if rev-parse
            # raises, we're still in the protected block and cleanup runs.
            new_tip = _branch_tip_sha(slug)
            with state.state_lease(slug) as lease:
                st2 = lease.load()
                if st2 is None:
                    # State file vanished between create_worktree and
                    # the final transition. Can't hand off to merge —
                    # scrub the throwaway worktree ourselves.
                    if we_own_throwaway:
                        remove_worktree(_primary(), slug, delete_branch=True)
                    worktree_owned_by_next_stage = True
                    return
                state.transition(
                    st2, "CITATION_VERIFY", "REVIEW_APPROVED",
                    citations=citations_meta,
                    write={
                        "agent": "citation-verify",
                        "commit_sha": new_tip,
                        "worktree": f".worktrees/quality-{slug}",
                    },
                    note=f"cleanup-only commit; kept={len(result.kept)} removed={len(result.removed)}",
                )
            # merge_one will tear down the worktree on success.
            worktree_owned_by_next_stage = True
        else:
            # No changes needed — skip merge entirely. Remove the throwaway
            # worktree BEFORE the lease so a lock-timeout failure below
            # still leaves the worktree scrubbed.
            remove_worktree(_primary(), slug, delete_branch=True)
            # We've already cleaned up — next-stage ownership doesn't
            # apply; don't leave the handler holding the bag.
            worktree_owned_by_next_stage = True
            with state.state_lease(slug) as lease:
                st2 = lease.load()
                if st2 is None:
                    return
                state.transition(
                    st2, "CITATION_VERIFY", "SKIPPED",
                    citations=citations_meta,
                    note="cleanup-only: all citations verified, no changes",
                )
    except BaseException:
        # We own the throwaway cleanup-only worktree iff we entered on
        # the cleanup-only path with no pre-existing worktree AND have
        # neither durably handed off nor scrubbed inline. The .exists()
        # probe is belt-and-braces — closes the round-5 race where a
        # post-create_worktree exception would otherwise have leaked.
        if (
            we_own_throwaway
            and not worktree_owned_by_next_stage
            and worktree_dir(_primary(), slug).exists()
        ):
            remove_worktree(_primary(), slug, delete_branch=True)
        raise


def _branch_tip_sha(slug: str) -> str:
    wt = worktree_dir(_primary(), slug)
    if not wt.exists():
        return ""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fail_and_cleanup(st: dict[str, Any], reason: str) -> None:
    """Mark a module FAILED and tear down its worktree + branch.

    Codex must #9: the locked handoff required worktree + branch
    cleanup on success, failure, AND SIGKILL recovery. v2 initially
    left branches behind for postmortem; Codex treated that as a
    must-fix on its own — we clean up both.
    """
    slug = st["slug"]
    remove_worktree(_primary(), slug, delete_branch=True)
    state.record_failure(st, reason)


# ---- review stage ------------------------------------------------------


def review_one(slug: str, *, timeout: int = 900) -> None:
    """REVIEW_PENDING → REVIEW_IN_PROGRESS → REVIEW_APPROVED / REVIEW_CHANGES.

    Critical: the reviewer reads the module from the WRITER'S WORKTREE.
    v1 bug was catastrophic here — reviewer read from primary (which
    was still on ``main``), always approved because the diff was
    invisible. Fix: ``_module_path_in_worktree``.

    KUBEDOJO_SKIP_REVIEW=1 defers review without creating an approval.
    """
    if os.environ.get("KUBEDOJO_SKIP_REVIEW") == "1":
        with state.state_lease(slug, timeout=5.0) as lease:
            st = lease.load()
            if st is None or st["stage"] != "REVIEW_PENDING":
                return
            state.transition(st, "REVIEW_PENDING", "REVIEW_PENDING",
                             review_blocked="review deferred by KUBEDOJO_SKIP_REVIEW")
        return

    with state.state_lease(slug, timeout=5.0) as lease:
        st = lease.load()
        if st is None or st["stage"] != "REVIEW_PENDING":
            return
        if st.get("review_contract_paused"):
            return
        wt, module_rel = worktree_dir(_primary(), slug), st["module_path"]
        try:
            if not isinstance(st.get("reviewer"), str) or not st["reviewer"].strip() or has_uncommitted(wt):
                raise ValueError("reviewer missing or worktree dirty")
            module_text, plan = _review_inputs(wt, module_rel)
            candidate_digest, plan_digest = _review_digests(module_text, plan)
        except (OSError, UnicodeError, ValueError, WorktreeError) as exc:
            state.transition(st, "REVIEW_PENDING", "REVIEW_PENDING", review_blocked=str(exc))
            return
        attempt_id = state.start_in_progress(st, "REVIEW_PENDING", "REVIEW_IN_PROGRESS")

        reviewer = st["reviewer"]
        track = (st.get("route") or {}).get("track", "rewrite")
        prompt = review_prompt(
            module_path=module_rel,
            module_text=module_text,
            writer_agent=st["writer"],
            track=track,
            original_gaps=build_audit_context(st.get("audit")),
            coverage_plan=plan,
        )

        try:
            # See writer-side note: agentic Claude will read+edit files in
            # cwd if tools are available. Reviewer cwd defaults to primary,
            # but tool-use would still pollute stdout with summaries
            # instead of the verdict JSON.
            result = dispatch(reviewer, prompt, timeout=timeout, tools_disabled=True)
        except DispatcherUnavailable:
            # Revert to REVIEW_PENDING so the next run can re-attempt.
            state.transition(
                st, "REVIEW_IN_PROGRESS", "REVIEW_PENDING",
                note="reviewer unavailable; will retry",
            )
            raise

        if not result.ok:
            _defer_review_failure(st, "review dispatch failed",
                                  {"attempt_id": attempt_id, "stdout": result.stdout, "stderr": result.stderr})
            return

        verdict = _parse_review_verdict(result)
        if verdict is None:
            _defer_review_failure(st, "review verdict malformed", {"attempt_id": attempt_id, "stdout": result.stdout})
            return

        raw = extract_last_json(result.stdout, required_keys={"verdict", "must_fix"})
        try:
            current_text, current_plan = _review_inputs(wt, module_rel)
            if _review_digests(current_text, current_plan) != (candidate_digest, plan_digest):
                raise ValueError("candidate or research plan changed during review")
            errors = validate_teaching_review(raw, module_text, plan) if verdict["verdict"] == "approve" else []
            if errors or (verdict["verdict"] == "approve" and raw.get("verdict") != "approve"):
                raise ValueError("; ".join(errors) or "review verdict mismatch")
        except (OSError, UnicodeError, ValueError) as exc:
            _defer_review_failure(st, str(exc), {"attempt_id": attempt_id, "payload": raw})
            return
        review_meta = {
            "agent": reviewer,
            "attempt_id": attempt_id,
            "verdict": verdict["verdict"], "must_fix": verdict["must_fix"], "payload": raw,
            "candidate_sha256": candidate_digest, "plan_sha256": plan_digest,
        }
        if st.get("review"):
            st["prior_reviews"] = [*(st.get("prior_reviews") or []), st["review"]]
        if verdict["verdict"] == "approve":
            state.transition(
                st, "REVIEW_IN_PROGRESS", "REVIEW_APPROVED",
                review=review_meta,
                review_contract_paused=False, review_blocked=None,
                note=f"{reviewer} APPROVE with researched coverage",
            )
        else:
            state.transition(
                st, "REVIEW_IN_PROGRESS", "REVIEW_CHANGES",
                review=review_meta,
                note=f"{reviewer} CHANGES ({len(verdict.get('must_fix') or [])} must-fix)",
            )


def _parse_review_verdict(result: DispatchResult) -> dict[str, Any] | None:
    """Parse only; approval requires separate candidate and plan validation."""
    try:
        payload = extract_last_json(
            result.stdout,
            required_keys={"verdict", "must_fix"},
        )
    except JsonExtractError:
        return None
    if payload.get("verdict") not in ("approve", "changes_requested") or not isinstance(payload.get("must_fix"), list):
        return None
    if payload["verdict"] == "changes_requested" and (not payload["must_fix"] or any(
            not isinstance(item, str) or not item.strip() for item in payload["must_fix"])):
        return None
    return payload


# ---- review-changes retry ---------------------------------------------


def handle_review_changes(slug: str) -> None:
    """REVIEW_CHANGES → WRITE_PENDING (retry) OR → tiebreaker OR → FAILED.

    Closes Codex must-fix #4: the v1 bug was that ``REVIEW_CHANGES`` was
    a state nothing consumed. Here we route it back to the writer with
    the reviewer's ``must_fix`` list, bump ``retry_count``, and cap at
    :data:`RETRY_CAP`. Beyond the cap, the tiebreaker (gemini) runs.

    If the tiebreaker ALSO returns CHANGES, mark the module FAILED —
    three independent agents disagreeing means the writer can't reach
    consensus and manual intervention is needed. Without this terminal
    branch, the previous code re-routed back to tiebreaker forever
    (only ``run_module``'s ``max_cycles`` guard eventually bailed,
    after wasting ~5 Gemini calls per module).
    """
    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None or st["stage"] != "REVIEW_CHANGES":
            return
        retry_count = st.get("retry_count", 0)
        if st.get("reviewer") == tiebreaker_agent():
            # Tiebreaker already ran and still wants changes — terminal.
            review = st.get("review") or {}
            must_fix = review.get("must_fix") or []
            preview = "; ".join(str(m)[:120] for m in must_fix[:3]) or "(no must_fix list)"
            _fail_and_cleanup(
                st,
                f"tiebreaker ({tiebreaker_agent()}) also returned CHANGES — "
                f"{len(must_fix)} must-fix item(s); manual review required. "
                f"First items: {preview}",
            )
            return
        if retry_count >= RETRY_CAP:
            # Hand off to Gemini tiebreaker.
            state.transition(
                st, "REVIEW_CHANGES", "REVIEW_PENDING",
                retry_count=retry_count,
                reviewer=tiebreaker_agent(),
                note="retry cap hit; Gemini tiebreaker",
            )
            return
        # Retry: back to WRITE_PENDING with must_fix context preserved.
        state.transition(
            st, "REVIEW_CHANGES", "WRITE_PENDING",
            retry_count=retry_count + 1,
            note=f"retry {retry_count + 1}/{RETRY_CAP}",
        )


def _clear_banner_and_complete_queue(
    primary: Path, slug: str, module_relpath: str, *, auto_approved: bool = False,
) -> None:
    """Post-merge cleanup: remove the ``revision_pending`` banner from the
    merged file and mark the queue entry completed.

    Runs under the merge lock so the brief dirty-primary window doesn't
    race with another module's merge pre-flight. ``clear_revision_pending``
    is idempotent — when the writer's output already dropped the banner,
    this is a no-op and no extra commit lands. When the writer preserved
    the banner verbatim from the input frontmatter (the inherit-by-default
    case), we strip it and commit a small ``quality(banner)`` cleanup
    commit so the rendered page no longer shows "queued for revision".

    When ``auto_approved=True`` the merge happened under
    ``KUBEDOJO_SKIP_REVIEW`` (LLM cross-family review deferred), so we
    additionally stamp ``qa_pending: true`` on the frontmatter so learners
    see a "final QA queued" banner instead of nothing — the module is
    technically shipped but hasn't been independently reviewed yet.
    ``scripts.quality_post_review`` clears that flag once a real APPROVE
    lands (or flips it back to ``revision_pending`` on CHANGES).

    The queue's ``record_completion`` is also called WITHOUT a path so
    it only updates the in-pipeline JSON state (no second frontmatter
    pass). Best-effort: failures here are logged but never re-raise,
    because the merge itself was successful and FAILING the slug after
    a successful COMMITTED transition would corrupt the audit trail.
    """
    module_file = primary / module_relpath
    banner_clean_succeeded = True
    commit_msg = (
        f"quality(banner): clear revision_pending + set qa_pending for {slug}"
        if auto_approved
        else f"quality(banner): clear revision_pending for {slug}"
    )
    # Acquire the merge lock for the dirty-primary window so another
    # slug's merge pre-flight (``has_uncommitted(primary)``) doesn't
    # see an in-progress banner edit and refuse its merge.
    try:
        with _merge_lock():
            try:
                cleared = queue.clear_revision_pending_frontmatter(module_file)
                qa_set = (
                    queue.set_qa_pending_frontmatter(module_file)
                    if auto_approved
                    else False
                )
                cleared = cleared or qa_set
            except Exception as exc:  # pragma: no cover — advisory cleanup
                # Codex round-3 must #1: a raise here means we don't know
                # whether the banner is gone, so the queue must NOT be
                # marked complete — a future sweep needs to retry.
                logger.exception("%s: banner clear failed (%s)", slug, type(exc).__name__,
                                 exc_info=(type(exc), Exception(type(exc).__name__), exc.__traceback__))
                cleared = False
                banner_clean_succeeded = False

            if cleared:
                try:
                    subprocess.run(
                        ["git", "add", module_relpath],
                        cwd=primary, check=True, capture_output=True,
                    )
                    subprocess.run(
                        ["git", "commit", "-m", commit_msg],
                        cwd=primary, check=True, capture_output=True,
                    )
                except subprocess.CalledProcessError as exc:
                    # Codex round-2 must #3: revert the working-tree
                    # mutation so primary is clean for the NEXT module's
                    # merge pre-flight, AND don't mark the queue
                    # completed — the banner is still on the rendered
                    # page and a follow-up cleanup pass is required.
                    subprocess.run(
                        ["git", "restore", "--staged", module_relpath],
                        cwd=primary, check=False, capture_output=True,
                    )
                    subprocess.run(
                        ["git", "restore", module_relpath],
                        cwd=primary, check=False, capture_output=True,
                    )
                    print(
                        f"[warn] {slug}: banner clear git commit failed "
                        f"(rc={exc.returncode}); reverted working-tree edit. "
                        f"Queue stays incomplete; banner will be cleared by "
                        f"the next sweep."
                    )
                    banner_clean_succeeded = False
    except TimeoutError as exc:  # pragma: no cover — lock contention path
        print(f"[warn] {slug}: banner cleanup skipped — merge lock unavailable: {exc}")
        banner_clean_succeeded = False

    if not banner_clean_succeeded:
        # Don't mark the queue complete — the banner is still showing on
        # the rendered page and a future sweep needs to retry. Returning
        # early here is safe: the merge already landed (state is
        # COMMITTED), only the queue's "completed_at" timestamp is
        # deferred.
        return

    try:
        # Pass module_path=None: the frontmatter clear above already ran
        # (with primary-side commit). queue.record_completion would do
        # the SAME clear if we passed the path, then leave an
        # uncommitted edit on primary — which would dirty subsequent
        # merges in the batch. Pass None to skip the redundant clear.
        queue.record_completion(slug, module_path=None)
    except FileNotFoundError:
        pass  # legacy slug without a queue doc
    except Exception as exc:  # pragma: no cover — advisory cleanup
        logger.exception("%s: queue completion failed (%s)", slug, type(exc).__name__,
                         exc_info=(type(exc), Exception(type(exc).__name__), exc.__traceback__))


def _handle_density_failure(st: dict[str, Any], reason: str) -> None:
    """REVIEW_APPROVED + density-fail → WRITE_PENDING (retry) OR → FAILED.

    Mirrors :func:`handle_review_changes` retry semantics. The writer's
    output cleared the cross-family review on teaching merits but failed
    the deterministic density triple gate — usually means the writer
    over-compressed or padded its way through the prose. Bounce to
    WRITE_PENDING with the reasons in retry context, capped at
    :data:`RETRY_CAP`. Beyond the cap, mark FAILED so a human queues
    the rewrite manually.

    Caller already holds the lease for ``st['slug']`` from inside
    :func:`merge_one`'s ``state_lease`` block; we pass through to
    ``state.transition`` which CAS-checks ``REVIEW_APPROVED`` on disk.
    """
    retry_count = st.get("retry_count", 0)
    primary = _primary()
    if retry_count >= RETRY_CAP:
        # _fail_and_cleanup transitions to FAILED and removes the
        # worktree+branch in one go. If the branch teardown fails it
        # leaves a stale branch but the FAILED state is durable, which
        # is the correct ordering: state truth first, cleanup advisory.
        _fail_and_cleanup(
            st,
            f"density gate failed after {RETRY_CAP} retries — manual rewrite required: {reason}",
        )
        return
    # Retry: back to WRITE_PENDING with the density failure as must_fix
    # context. The writer prompt builder already merges ``review.must_fix``
    # into the next attempt, so wedge our reason in there alongside any
    # prior reviewer notes (kept distinct by the ``[density]`` prefix).
    review = dict(st.get("review") or {})
    must_fix = list(review.get("must_fix") or [])
    must_fix.append(f"[density] {reason}")
    review["must_fix"] = must_fix
    # Codex must #5: transition FIRST, then tear down the worktree.
    # If teardown raises after the transition, the state is durably
    # WRITE_PENDING and ``create_worktree`` is idempotent (it prunes
    # stale checkouts via ``_worktree_registered``-or-``wt.exists()``
    # — see worktree.py). The reverse order would leave state stuck at
    # REVIEW_APPROVED with the branch already gone — the next merge
    # attempt would fail mysteriously.
    state.transition(
        st, "REVIEW_APPROVED", "WRITE_PENDING",
        retry_count=retry_count + 1,
        review=review,
        note=f"density retry {retry_count + 1}/{RETRY_CAP}: {reason[:120]}",
    )
    try:
        remove_worktree(primary, st["slug"], delete_branch=True)
    except Exception as exc:  # pragma: no cover — cleanup is advisory
        logger.exception("%s: density retry teardown failed (%s); next write retries pruning",
                         st["slug"], type(exc).__name__,
                         exc_info=(type(exc), Exception(type(exc).__name__), exc.__traceback__))


# ---- merge stage -------------------------------------------------------


MERGE_LOCK_PATH = None  # type: ignore[assignment]
"""Lazy-initialized; computed on first use so tests that monkey-patch
``_REPO_ROOT`` get the tmp-dir lock rather than the import-time one."""

_MERGE_RETRY_CAP = 3
"""Per-module merge retries when rebase/ff fails because of a race.

Codex must #5 noted that workers>1 would incorrectly mark a racing
module FAILED on the first conflict. With this cap, the module retries
after re-rebase — only persistent failure (real conflict, not a race)
reaches FAILED.
"""


def _merge_lock_path() -> Path:
    global MERGE_LOCK_PATH
    if MERGE_LOCK_PATH is None:
        MERGE_LOCK_PATH = _REPO_ROOT / ".pipeline" / "quality-pipeline" / ".merge.lock"
    MERGE_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    return MERGE_LOCK_PATH


@contextmanager
def _merge_lock(timeout: float = 120.0):
    """Global git-main lock. merge_one holds it for rebase + ff-merge so
    two workers can't clobber main concurrently (Codex must #5)."""
    import fcntl
    path = _merge_lock_path()
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"merge lock contended (>{timeout}s)")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def merge_one(slug: str) -> None:
    """REVIEW_APPROVED → COMMITTED. Rebase worktree branch, ff-merge, tear down.

    Holds a global ``_merge_lock`` for the rebase + ff-merge sequence so
    that when two workers land on ``merge_one`` concurrently, they
    serialize on the primary ``main`` mutation (Codex must #5). Retries
    on rebase/ff failure up to :data:`_MERGE_RETRY_CAP` — a lost race
    just means ``main`` advanced; re-rebase and try again.

    The rebase ensures successive modules in a batch can all merge
    ff-only even as ``main`` advances between them (Codex must-fix #3).
    """
    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None or st["stage"] != "REVIEW_APPROVED":
            return
        error = _merge_review_error(st)
        if error:
            state.transition(st, "REVIEW_APPROVED", "REVIEW_PENDING", review_blocked=error, review_contract_paused=True, review_contract_version=2)
            return
        primary = _primary()
        if current_branch(primary) != "main":
            _fail_and_cleanup(st, "merge: primary not on main — manual intervention")
            return

        # Hard gate (#377): visual-aid preservation. Run BEFORE merge so a
        # regression doesn't land on main; the worktree branch is rebased
        # onto current main, then we diff branch-tip vs main for this
        # module's path. Per ``.claude/rules/module-quality.md``: "NEVER
        # remove or simplify existing visual aids during rewrites — they
        # are protected assets."
        last_error: Exception | None = None
        merge_sha: str | None = None
        density_meta: dict[str, Any] | None = None
        density_failed = False
        dirty_primary = False
        for _attempt in range(_MERGE_RETRY_CAP):
            try:
                with _merge_lock():
                    # Codex round-2 must #2: dirty-primary check INSIDE
                    # the merge lock. The banner-cleanup commit (in
                    # ``_clear_banner_and_complete_queue``) holds the
                    # same lock during its briefly-dirty window, so
                    # checking outside the lock could mis-flag another
                    # slug's in-flight cleanup as a foreign edit.
                    # Inside the lock, dirty primary genuinely is a
                    # foreign edit and we should fail.
                    if has_uncommitted(primary):
                        last_error = StageError(
                            "primary has uncommitted changes inside merge lock — foreign edit"
                        )
                        dirty_primary = True
                        break
                    rebase_onto_main(primary, slug)
                    error = _merge_review_error(st)
                    if error:
                        state.transition(st, "REVIEW_APPROVED", "REVIEW_PENDING", review_blocked=error, review_contract_paused=True, review_contract_version=2)
                        return
                    try:
                        gates.assert_visual_aids_preserved(
                            primary, slug, st["module_path"], base_ref="main",
                        )
                    except gates.GateError as gate_exc:
                        last_error = gate_exc
                        break  # don't retry — regression is deterministic
                    # #388 stage [6]: density hard gate. A REWRITE-tier
                    # output must clear the triple gate before landing.
                    # Density signals are content-stable (rebase doesn't
                    # change them) so a single failure is terminal for
                    # this attempt. We bounce the slug back to
                    # WRITE_PENDING with the reason as retry context (up
                    # to RETRY_CAP) instead of FAILing it outright,
                    # because the writer may simply have over-compressed.
                    try:
                        density_meta = gates.assert_density_threshold(
                            primary, slug, st["module_path"],
                        )
                    except gates.GateError as gate_exc:
                        last_error = gate_exc
                        density_failed = True
                        break
                    merge_sha = merge_ff_only(primary, slug)
                break
            except WorktreeError as exc:
                last_error = exc
                continue  # likely race — retry after re-rebase
            except TimeoutError as exc:
                last_error = exc
                break  # contention timeout — don't spin
        if dirty_primary:
            _fail_and_cleanup(st, f"merge: {last_error}")
            return
        if density_failed:
            _handle_density_failure(st, str(last_error))
            return
        if merge_sha is None:
            _fail_and_cleanup(st, f"merge: {last_error}")
            return

        remove_worktree(primary, slug, delete_branch=True)
        commit_payload: dict[str, Any] = {"sha": merge_sha, "branch": branch_name(slug)}
        if density_meta is not None:
            commit_payload["density"] = density_meta
        state.transition(
            st, "REVIEW_APPROVED", "COMMITTED",
            commit=commit_payload,
            note=f"merged {merge_sha[:8]}",
        )
        # Capture for use AFTER the state_lease exits — the banner +
        # queue cleanup helper acquires its own state_lease via
        # ``record_completion``, so it MUST run outside this block to
        # avoid an fcntl re-entrancy deadlock.
        module_relpath = st["module_path"]
        auto_approved = bool((st.get("review") or {}).get("auto_approved"))

    # Codex must #3: clear the banner + close the queue entry so a
    # shipped module no longer renders the "queued for revision" banner
    # to learners. Runs OUTSIDE the state_lease above (lease re-entrancy)
    # but acquires its OWN ``_merge_lock`` so the brief dirty-primary
    # window for the banner-cleanup commit doesn't race with another
    # module's merge pre-flight check.
    _clear_banner_and_complete_queue(primary, slug, module_relpath, auto_approved=auto_approved)

    # #377 post-merge: anti-gaming sampler (20 % deterministic) + ledger
    # row. Runs AFTER the COMMITTED transition (no state_lease held) so
    # a sampler/ledger failure cannot block the merge — sampling is
    # advisory, the ledger is auditable. Failures surface as warnings on
    # stdout and are written into the ledger row's notes field where
    # applicable.
    _post_merge_gates(slug)


def _post_merge_gates(slug: str) -> None:
    """Run the post-merge sampler + ledger append for a freshly-merged slug.

    Failures here are non-fatal: a missing audit subprocess or unwritable
    ledger should not undo a green merge. The audit subprocess can take
    100+ seconds, so callers expecting fast turnaround on workers=1
    batches should be aware. To skip entirely, set
    ``KUBEDOJO_GATES_SAMPLE_RATE=0`` in the environment.
    """
    st = state.load_state(slug)
    if st is None:
        return
    real_llm: dict[str, Any] | None = None
    try:
        if gates.should_sample(slug):
            module_path = _module_path(st)
            real_llm = gates.run_real_llm_rubric(module_path)
            if not real_llm.get("ok"):
                print(f"[gate-warn] {slug}: sample failed — {real_llm.get('error')}")
            elif not real_llm.get("passed"):
                print(
                    f"[gate-warn] {slug}: real-LLM teaching score "
                    f"{real_llm.get('teaching_score')} below threshold "
                    f"{gates.REAL_LLM_MIN_TEACHING_SCORE} — batch should pause"
                )
    except Exception as exc:  # never let a sampler bug undo a merge
        logger.exception("%s: sampler failed (%s)", slug, type(exc).__name__,
                         exc_info=(type(exc), Exception(type(exc).__name__), exc.__traceback__))
        real_llm = {"ok": False, "error": f"sampler raised: {type(exc).__name__}"}

    try:
        with _merge_lock():
            row = gates.build_ledger_row(slug=slug, state_payload=st, real_llm_result=real_llm)
            gates.append_ledger(row)
            _commit_ledger_row(slug)
    except Exception as exc:
        logger.exception("%s: ledger append failed (%s)", slug, type(exc).__name__,
                         exc_info=(type(exc), Exception(type(exc).__name__), exc.__traceback__))


def _commit_ledger_row(slug: str) -> None:
    """Stage + commit the ledger TSV after a row append.

    Without this, the working tree is left dirty after every merge
    (the ledger file is tracked, not gitignored), which makes the
    NEXT module's ``merge_one`` refuse with "primary has uncommitted
    changes" — the exact #378 root-cause class. The merge commit
    already landed; this is a follow-up commit pinning the audit row.
    """
    primary = _primary()
    ledger_rel = "docs/quality-progress.tsv"
    if not (primary / ledger_rel).exists():
        return
    diff = subprocess.run(
        ["git", "diff", "--quiet", "--", ledger_rel],
        cwd=primary, check=False,
    )
    if diff.returncode == 0:
        # No changes (e.g. lock-only, or another worker already committed).
        return

    committed = False
    try:
        subprocess.run(["git", "add", ledger_rel], cwd=primary, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"quality(ledger): post-merge audit row for {slug}"],
            cwd=primary, check=True,
        )
        committed = True
    finally:
        if not committed:
            subprocess.run(
                ["git", "restore", "--staged", ledger_rel],
                cwd=primary, check=False, capture_output=True,
            )
            subprocess.run(
                ["git", "restore", ledger_rel],
                cwd=primary, check=False, capture_output=True,
            )


# ---- resume logic -----------------------------------------------------


def recover_in_progress(slug: str) -> None:
    """Reconcile a state stuck at an in-progress stage.

    Handles ``WRITE_IN_PROGRESS`` and ``REVIEW_IN_PROGRESS`` on startup.
    Idempotent — safe to call on any state. ``CITATION_VERIFY`` doesn't
    need explicit recovery because the citation work itself is
    idempotent (re-fetching URLs + re-verifying is safe) and is
    registered in :data:`_STAGE_FN` so the run loop picks it up.
    """
    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None:
            return
        stage = st["stage"]
        if stage == "WRITE_IN_PROGRESS":
            _recover_write_in_progress(st)
        elif stage == "REVIEW_IN_PROGRESS":
            # No durable side effect from a half-done review; just revert.
            state.transition(
                st, "REVIEW_IN_PROGRESS", "REVIEW_PENDING",
                note="recovered from REVIEW_IN_PROGRESS SIGKILL",
            )


def _recover_write_in_progress(st: dict[str, Any]) -> None:
    """If the worktree's branch has a commit AHEAD of main, advance to
    WRITE_DONE. Otherwise scrub and revert to WRITE_PENDING.

    Codex must #4: the v1-v2 "sha != main" check was too loose. A branch
    that was cut from an old main tip but never got a commit appended
    still has a SHA different from the current main (which advanced via
    other merges) — and that would falsely count as a completed write.

    Correct check: ``git rev-list --count main..<branch>``. A value ≥ 1
    means the branch has at least one commit AHEAD of main, which only
    happens if the writer actually committed.
    """
    slug = st["slug"]
    primary = _primary()
    branch = branch_name(slug)
    branch_exists = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch],
        cwd=primary, capture_output=True, check=False,
    ).returncode == 0
    ahead = 0
    if branch_exists:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"main..{branch}"],
            cwd=primary, capture_output=True, text=True, check=False,
        )
        try:
            ahead = int((result.stdout or "0").strip())
        except ValueError:
            ahead = 0

    if ahead >= 1:
        # Branch has genuine writer commit(s) ahead of main — trust them.
        tip = subprocess.run(
            ["git", "rev-parse", branch], cwd=primary, capture_output=True, text=True, check=False,
        ).stdout.strip()
        state.transition(
            st, "WRITE_IN_PROGRESS", "WRITE_DONE",
            write={
                "agent": st.get("writer"),
                "attempt_id": st.get("attempt_id"),
                "commit_sha": tip,
                "worktree": f".worktrees/quality-{slug}",
                "recovered": True,
            },
            note=f"recovered WRITE_IN_PROGRESS: branch {ahead} commit(s) ahead",
        )
    else:
        # No real progress — scrub worktree and branch, retry from scratch.
        remove_worktree(primary, slug, delete_branch=True)
        state.transition(
            st, "WRITE_IN_PROGRESS", "WRITE_PENDING",
            note="recovered WRITE_IN_PROGRESS: no commits ahead of main, requeued",
        )


# ---- driver (single module through all stages) ------------------------


_STAGE_FN = {
    "UNAUDITED": audit_one,
    "AUDITED": route_one,
    "ROUTED": route_one,  # double-checked by route_one itself
    "WRITE_PENDING": write_one,
    "WRITE_DONE": citation_verify_one,
    "CITATION_CLEANUP_ONLY": citation_verify_one,
    # Codex must #3: CITATION_VERIFY is crash-resumable. process_module_citations
    # is idempotent — re-fetching URLs and re-verifying produces the same
    # kept/removed set, so re-running after a SIGKILL mid-stage completes
    # correctly.
    "CITATION_VERIFY": citation_verify_one,
    "REVIEW_PENDING": review_one,
    "REVIEW_CHANGES": handle_review_changes,
    "REVIEW_APPROVED": merge_one,
}


def run_module(slug: str, *, max_cycles: int = 20) -> str:
    """Drive a single slug through stages until it reaches a terminal state
    or stops making progress.

    Returns the final stage name. ``max_cycles`` guards against a buggy
    state machine looping; in practice the pipeline needs at most
    ``1 + RETRY_CAP + 1`` cycles per module (audit → route → write →
    verify → review → [changes → write → verify → review] × RETRY_CAP →
    merge).

    Raises :class:`DispatcherUnavailable` unwrapped — the caller (pipeline
    run-loop) uses it as the signal to stop the whole batch rather than
    crashing one module at a time.
    """
    recover_in_progress(slug)
    for _ in range(max_cycles):
        st = state.load_state(slug)
        if st is None:
            raise StageError(f"state missing for {slug}")
        stage = st["stage"]
        if stage in state.TERMINAL_STAGES:
            return stage
        fn = _STAGE_FN.get(stage)
        if fn is None:
            # In-progress states should have been reconciled above. If
            # we still see one, something is wrong — fail rather than spin.
            raise StageError(f"no stage function for {stage!r} (slug={slug!r})")
        fn(slug)
        st_after = state.load_state(slug)
        new_stage = st_after["stage"] if st_after else stage
        if new_stage == stage:
            # No progress — give up to avoid an infinite loop.
            return stage
    return state.load_state(slug)["stage"] if state.load_state(slug) else "FAILED"  # type: ignore[index]
