"""Quality pipeline v2 CLI orchestrator.

Subcommands:

* ``bootstrap`` — scan ``src/content/docs/`` (excluding ``uk/`` and
  ``index.md``), assign permanent ``module_index`` by sorted path, and
  create one state file per module. Idempotent.
* ``status`` — counts by stage, useful for health-check and briefing.
* ``audit`` — drive every ``UNAUDITED`` module to ``AUDITED``.
* ``route`` — drive every ``AUDITED`` module to ``WRITE_PENDING`` (rewrite
  or structural track) or ``CITATION_CLEANUP_ONLY`` (score ≥ 4.0 +
  complete structure). ``SKIPPED`` is reached later by
  :func:`stages.citation_verify_one` on the cleanup-only path when
  nothing needed removal.
* ``run`` — drive a queue of modules through the full pipeline until
  a terminal state. Processes worst-score-first; writer alternation is
  determined by each module's permanent index (not processing order).
* ``run-module`` — drive a single slug. Used by smoke tests.
* ``reset-stage`` — admin tool; moves a module back to an earlier stage
  so a fix can be re-attempted without a full state-file hand edit.

Return codes: 0 on success, 1 on any module failing (so CI and shell
scripts can detect issues), 3 when aborted by dispatcher unavailability.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import density, stages, state
from .dispatchers import DispatcherUnavailable
from .prompts import assert_required_docs_exist
from .queue import set_citations_verified_frontmatter
from .worktree import has_uncommitted, primary_checkout_root

_REPO_ROOT = primary_checkout_root(Path(__file__).resolve().parents[2])
_CONTENT_ROOT = _REPO_ROOT / "src" / "content" / "docs"
logger = logging.getLogger(__name__)

WORKER_CAP = 3
"""Hard cap per project memory ``feedback_batch_worker_cap.md`` —
above 3, Gemini 429s and user's Mac lags."""


_MODULE_NUMBER_RE = re.compile(r"-module-(\d+)\.(\d+)-")
_CH_NUMBER_RE = re.compile(r"-ch-(\d+)-")
_LEGACY_MODULE_NUMBER_RE = re.compile(r"-module-(\d+)-")

# Flattened from astro.config.mjs sidebar entries and src/content/docs/.
# Unknown tracks/sections sort after the known learner path.
_READING_ORDER_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "prerequisites",
        (
            "prerequisites-zero-to-terminal",
            "linux-foundations-everyday-use",
            "prerequisites-cloud-native-101",
            "prerequisites-kubernetes-basics",
            "prerequisites-git-deep-dive",
            "prerequisites-philosophy-design",
            "prerequisites-modern-devops",
        ),
    ),
    (
        "linux",
        (
            "linux-foundations-system-essentials",
            "linux-foundations-container-primitives",
            "linux-foundations-networking",
            "linux-operations-shell-scripting",
            "linux-operations-performance",
            "linux-operations-troubleshooting",
            "linux-operations",
            "linux-security-hardening",
            "k8s-lfcs",
        ),
    ),
    (
        "ai",
        (
            "ai-foundations",
            "ai-ai-native-work",
            "ai-ai-building",
            "ai-open-models-local-inference",
            "ai-ai-for-kubernetes-platform-work",
            "ai-history",
        ),
    ),
    (
        "k8s",
        (
            "k8s-kcna",
            "k8s-kcsa",
            "k8s-cka",
            "k8s-ckad",
            "k8s-cks",
            "k8s-extending",
            "k8s-bridges",
            "k8s-pca",
            "k8s-ica",
            "k8s-cca",
            "k8s-cgoa",
            "k8s-cba",
            "k8s-otca",
            "k8s-kca",
            "k8s-capa",
            "k8s-cnpe",
            "k8s-cnpa",
            "k8s-finops",
        ),
    ),
    (
        "cloud",
        (
            "cloud-hyperscaler-rosetta-stone",
            "cloud-aws-essentials",
            "cloud-eks-deep-dive",
            "cloud-gcp-essentials",
            "cloud-gke-deep-dive",
            "cloud-azure-essentials",
            "cloud-aks-deep-dive",
            "cloud-architecture-patterns",
            "cloud-advanced-operations",
            "cloud-managed-services",
            "cloud-enterprise-hybrid",
        ),
    ),
    (
        "ai-ml-engineering",
        (
            "ai-ml-engineering-prerequisites",
            "ai-ml-engineering-ai-native-development",
            "ai-ml-engineering-generative-ai",
            "ai-ml-engineering-vector-rag",
            "ai-ml-engineering-frameworks-agents",
            "ai-ml-engineering-mlops",
            "ai-ml-engineering-ai-infrastructure",
            "ai-ml-engineering-advanced-genai",
            "ai-ml-engineering-multimodal-ai",
            "ai-ml-engineering-deep-learning",
            "ai-ml-engineering-machine-learning",
            "ai-ml-engineering-reinforcement-learning",
            "ai-ml-engineering-bridges",
            "ai-ml-engineering-history",
        ),
    ),
    (
        "on-premises",
        (
            "on-premises-planning",
            "on-premises-provisioning",
            "on-premises-networking",
            "on-premises-storage",
            "on-premises-multi-cluster",
            "on-premises-security",
            "on-premises-operations",
            "on-premises-resilience",
            "on-premises-ai-ml-infrastructure",
        ),
    ),
    (
        "platform",
        (
            "platform-foundations-advanced-networking",
            "platform-foundations-distributed-systems",
            "platform-foundations-engineering-leadership",
            "platform-foundations-observability-theory",
            "platform-foundations-reliability-engineering",
            "platform-foundations-security-principles",
            "platform-foundations-systems-thinking",
            "platform-foundations",
            "platform-disciplines-core-platform-sre",
            "platform-disciplines-core-platform-platform-engineering",
            "platform-disciplines-core-platform-leadership",
            "platform-disciplines-delivery-automation-release-engineering",
            "platform-disciplines-delivery-automation-gitops",
            "platform-disciplines-delivery-automation-iac",
            "platform-disciplines-reliability-security-networking",
            "platform-disciplines-reliability-security-chaos-engineering",
            "platform-disciplines-reliability-security-devsecops",
            "platform-disciplines-data-ai-data-engineering",
            "platform-disciplines-data-ai-mlops",
            "platform-disciplines-data-ai-aiops",
            "platform-disciplines-data-ai-ai-infrastructure",
            "platform-disciplines-business-value-finops",
            "platform-disciplines",
            "platform-toolkits-cicd-delivery-ci-cd-pipelines",
            "platform-toolkits-cicd-delivery-gitops-deployments",
            "platform-toolkits-cicd-delivery-source-control",
            "platform-toolkits-cicd-delivery-container-registries",
            "platform-toolkits-observability-intelligence-observability",
            "platform-toolkits-observability-intelligence-aiops-tools",
            "platform-toolkits-infrastructure-networking-iac-tools",
            "platform-toolkits-infrastructure-networking-k8s-distributions",
            "platform-toolkits-infrastructure-networking-networking",
            "platform-toolkits-infrastructure-networking-platforms",
            "platform-toolkits-infrastructure-networking-storage",
            "platform-toolkits-security-quality-security-tools",
            "platform-toolkits-security-quality-code-quality",
            "platform-toolkits-developer-experience-devex-tools",
            "platform-toolkits-developer-experience-scaling-reliability",
            "platform-toolkits-data-ai-platforms-ml-platforms",
            "platform-toolkits-data-ai-platforms-cloud-native-databases",
            "platform-toolkits",
        ),
    ),
)


def _slug_matches_prefix(slug: str, prefix: str) -> bool:
    return slug == prefix or slug.startswith(f"{prefix}-")


def _reading_order_position(slug: str) -> tuple[int, int]:
    unknown_track_idx = len(_READING_ORDER_SECTIONS)
    for track_idx, (track_prefix, sections) in enumerate(_READING_ORDER_SECTIONS):
        for section_idx, section_prefix in enumerate(sections):
            if _slug_matches_prefix(slug, section_prefix):
                return track_idx, section_idx

    fallback_matches = [
        (len(track_prefix), track_idx, len(sections))
        for track_idx, (track_prefix, sections) in enumerate(_READING_ORDER_SECTIONS)
        if _slug_matches_prefix(slug, track_prefix)
    ]
    if fallback_matches:
        _, track_idx, section_idx = max(fallback_matches, key=lambda item: item[0])
        return track_idx, section_idx
    return unknown_track_idx, 0


def _module_number_key(slug: str) -> tuple[int, int]:
    match = _MODULE_NUMBER_RE.search(slug)
    if match is not None:
        return int(match.group(1)), int(match.group(2))

    chapter_match = _CH_NUMBER_RE.search(slug)
    if chapter_match is not None:
        return int(chapter_match.group(1)), 0

    legacy_match = _LEGACY_MODULE_NUMBER_RE.search(slug)
    if legacy_match is not None:
        return int(legacy_match.group(1)), 0

    return 0, -1


def _reading_order_key(slug: str) -> tuple[int, int, int, int, str]:
    track_idx, section_idx = _reading_order_position(slug)
    major, minor = _module_number_key(slug)
    return track_idx, section_idx, major, minor, slug


# ---- bootstrap --------------------------------------------------------


def iter_all_modules() -> list[Path]:
    """Every eligible English content module, sorted by path.

    Sorting is the basis for the permanent ``module_index`` — changing
    the sort order after bootstrap would silently re-assign every
    module's writer (even→Codex vs odd→Claude), so this must stay
    deterministic across runs.
    """
    out: list[Path] = []
    for p in sorted(_CONTENT_ROOT.rglob("*.md")):
        posix = p.as_posix()
        if "/uk/" in posix or p.name == "index.md":
            continue
        out.append(p)
    return out


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Create state files for every module that doesn't have one and
    migrate any pre-v2 state files that lack ``module_index``.

    Preserves existing state files — re-running bootstrap after adding
    new modules only creates new state, never overwrites. The
    ``module_index`` stays stable because it's re-derived from the
    sorted path list, and a new module appended at the end of the
    alphabetical list only grows the index space.

    Migration: v1 state files had no ``module_index`` field. v2 needs
    it for writer round-robin. Bootstrap fills it in for any existing
    state that's missing it — non-destructive, preserves the audit
    and history fields intact.
    """
    modules = iter_all_modules()
    state.STATE_DIR.mkdir(parents=True, exist_ok=True)
    created = migrated = 0
    for i, module_path in enumerate(modules):
        slug = state.slug_for(module_path)
        existing = state.load_state(slug)
        if existing is None:
            st = state.new_state(module_path, module_index=i)
            state.save_state(st)
            created += 1
            continue
        if existing.get("module_index") is None:
            existing["module_index"] = i
            state.save_state(existing)
            migrated += 1
    unchanged = len(modules) - created - migrated
    print(
        f"bootstrap: {created} new state(s); {migrated} v1→v2 migrated; "
        f"{unchanged} already complete; total {len(modules)}"
    )
    return 0


# ---- status -----------------------------------------------------------


def iter_states(slug_filter: Iterable[str] | None = None) -> list[dict[str, Any]]:
    all_slugs = state.iter_state_slugs()
    if slug_filter is not None:
        wanted = set(slug_filter)
        all_slugs = [s for s in all_slugs if s in wanted]
    out: list[dict[str, Any]] = []
    for slug in all_slugs:
        st = state.load_state(slug)
        if st is not None:
            out.append(st)
    return sorted(out, key=lambda st: _reading_order_key(st["slug"]))


def cmd_status(args: argparse.Namespace) -> int:
    states = iter_states(args.only or None)
    counts: Counter[str] = Counter(st["stage"] for st in states)
    print(f"total: {len(states)}")
    for stage in state.STAGES:
        n = counts.get(stage, 0)
        if n:
            print(f"  {stage}: {n}")
    if args.verbose:
        failed = [st for st in states if st["stage"] == "FAILED"]
        for st in failed[:20]:
            print(f"FAILED  {st['slug']}: {st.get('failure_reason') or '(no reason)'}")
    return 0


# ---- audit / route batch stages ---------------------------------------


def _process_batch(
    eligible_stages: set[str],
    fn,
    *,
    limit: int | None,
    only: Iterable[str] | None,
) -> tuple[int, int, bool]:
    slugs = [st["slug"] for st in iter_states(only) if st["stage"] in eligible_stages]
    if limit is not None:
        slugs = slugs[:limit]
    ok = fail = 0
    aborted = False
    for slug in slugs:
        try:
            fn(slug)
            ok += 1
        except DispatcherUnavailable as exc:
            print(f"[abort] dispatcher unavailable — {exc}")
            aborted = True
            return ok, fail, aborted
        except Exception as exc:  # pragma: no cover — unexpected failures logged
            logger.exception("quality batch item failed for %s", slug)
            print(f"[fail] {slug}: {exc}")
            fail += 1
    return ok, fail, aborted


def cmd_audit(args: argparse.Namespace) -> int:
    ok, fail, aborted = _process_batch({"UNAUDITED"}, stages.audit_one, limit=args.limit, only=args.only)
    print(f"audit: ok={ok} fail={fail}")
    if aborted:
        return 3
    return 0 if fail == 0 else 1


def cmd_route(args: argparse.Namespace) -> int:
    ok, fail, aborted = _process_batch({"AUDITED"}, stages.route_one, limit=args.limit, only=args.only)
    print(f"route: ok={ok} fail={fail}")
    if aborted:
        return 3
    return 0 if fail == 0 else 1


# ---- run (full pipeline per module, worst-first) ---------------------


def _order_worst_first(slugs: list[str]) -> list[str]:
    """Sort slugs by ascending audit teaching_score, tiebreak by module_index.

    Modules without a score (UNAUDITED / audit failed) are placed at the
    BEGINNING — they still need to be processed, and their eventual
    score is unknown until audited.
    """
    def key(slug: str) -> tuple[float, int]:
        st = state.load_state(slug)
        if st is None:
            return (0.0, 10**9)
        audit = st.get("audit") or {}
        score = stages._audit_score(audit) if audit else -1.0
        return (score, st.get("module_index", 10**9))
    return sorted(slugs, key=key)


def cmd_run(args: argparse.Namespace) -> int:
    """Drive modules through the full pipeline.

    Respects the strict ``--workers 1`` default per memory
    ``feedback_batch_worker_cap.md``. ``--workers > 3`` is clamped with
    a warning.
    """
    assert_required_docs_exist()

    # Pre-flight: refuse to start if primary has uncommitted changes.
    # Without this, every module in the batch reaches merge_one and is
    # rejected with "primary has uncommitted changes" — the #378 root
    # cause class. Fail fast so the operator commits/stashes once, not
    # discovers the dirty tree N modules in.
    if has_uncommitted(_REPO_ROOT):
        print(
            "[abort] primary checkout has uncommitted changes — "
            "merge_one would refuse every module in the batch.\n"
            "        Commit or stash first, then re-run.",
            file=sys.stderr,
        )
        return 2

    args.workers = max(args.workers, 1)
    if args.workers > WORKER_CAP:
        print(f"[warn] --workers clamped from {args.workers} to {WORKER_CAP}")
        args.workers = WORKER_CAP
    if args.workers > 1:
        print("[warn] multi-worker mode processes modules concurrently; git worktrees are per-slug so it's safe, but Gemini 429 risk rises.")

    # Identify queue: everything not in a terminal state.
    all_states = iter_states(args.only or None)
    pending = [
        st["slug"]
        for st in all_states
        if st["stage"] not in state.TERMINAL_STAGES
    ]
    pending = _order_worst_first(pending)
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"run: {len(pending)} module(s) in queue (workers={args.workers})")
    ok = fail = aborted = 0
    if args.workers == 1:
        for slug in pending:
            rc = _run_one_with_abort(slug)
            if rc == "abort":
                aborted = 1
                break
            if rc == "ok":
                ok += 1
            else:
                fail += 1
    else:
        import concurrent.futures as cf

        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(_run_one_with_abort, slug): slug for slug in pending}
            for fut in cf.as_completed(futures):
                rc = fut.result()
                if rc == "abort":
                    aborted = 1
                elif rc == "ok":
                    ok += 1
                else:
                    fail += 1

    print(f"run: ok={ok} fail={fail} aborted={aborted}")
    if aborted:
        return 3
    return 0 if fail == 0 else 1


def _run_one_with_abort(slug: str) -> str:
    """Return ``"ok"``, ``"fail"``, or ``"abort"``. Never raises."""
    try:
        terminal = stages.run_module(slug)
    except DispatcherUnavailable as exc:
        print(f"[abort] dispatcher unavailable at {slug}: {exc}")
        return "abort"
    except Exception as exc:
        logger.exception("quality module run failed for %s", slug)
        print(f"[fail] {slug}: {exc}")
        _print_failure_diagnostics(slug)
        return "fail"
    if terminal == "FAILED":
        print(f"[fail] {slug}: FAILED")
        _print_failure_diagnostics(slug)
        return "fail"
    return "ok"


def _print_failure_diagnostics(slug: str) -> None:
    """Emit recorded failure context (state.failure_reason, last history
    entry, latest write/review diagnostic JSON) so the operator can
    triage without having to manually open files. Best-effort — never
    raises into the run loop."""
    try:
        st = state.load_state(slug)
    except Exception as exc:  # pragma: no cover — display path
        logger.exception("could not load failure state for %s", slug)
        print(f"        (could not read state: {exc})")
        return
    if st is None:
        print(f"        (no state file for {slug})")
        return
    reason = st.get("failure_reason") or "(no failure_reason recorded)"
    print(f"        reason: {reason}")
    history = st.get("history") or []
    if history:
        last = history[-1]
        print(f"        last  : {last.get('stage')} @ {last.get('at')} — {last.get('note', '')}")
    diag_dir = _REPO_ROOT / ".pipeline" / "quality-pipeline" / "diagnostics"
    if diag_dir.is_dir():
        diags = sorted(
            (p for p in diag_dir.glob(f"{slug}.*.failed.json")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if diags:
            try:
                rel = diags[0].relative_to(_REPO_ROOT)
            except ValueError:
                rel = diags[0]
            print(f"        diag  : {rel}")


def cmd_run_module(args: argparse.Namespace) -> int:
    """Single-module smoke path — the primary vehicle for Phase D's
    ``k8s-capa-module-1.2-argo-events`` end-to-end test."""
    assert_required_docs_exist()
    slug = args.slug
    st = state.load_state(slug)
    if st is None:
        print(f"no state for slug {slug!r}; run bootstrap first")
        return 1
    try:
        terminal = stages.run_module(slug)
    except DispatcherUnavailable as exc:
        print(f"aborted: dispatcher unavailable — {exc}")
        return 3
    print(f"{slug}: {terminal}")
    return 0 if terminal not in ("FAILED",) else 1


# ---- backfill-pending (close the v2 → citation_backfill seam) ---------


_CITATION_BACKFILL_SCRIPT = _REPO_ROOT / "scripts" / "citation_backfill.py"
_VENV_PYTHON = str(_REPO_ROOT / ".venv" / "bin" / "python")

# The v2 backfill seam records processing completion, but it does not have a
# durable claim/source verification receipt.  Keep that readiness distinction
# explicit: an injection (or no-op) never earns the frontmatter bit.
_SOURCE_UNVERIFIED = {
    "source_acceptance": "unverified",
    "readiness_impact": "not_cleared_until_independent_source_evidence",
}


def _module_key_from_path(module_path: str) -> str:
    """Convert state.module_path to citation_backfill's module_key.

    e.g. ``src/content/docs/k8s/capa/module-1.2-argo-events.md`` →
    ``k8s/capa/module-1.2-argo-events``.
    """
    rel = module_path
    for prefix in ("src/content/docs/",):
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
            break
    return rel.removesuffix(".md")


def _git(repo: Path, *args: str, check: bool = True) -> tuple[int, str, str]:
    """Run ``git`` in ``repo`` and return ``(returncode, stdout, stderr)``."""
    import subprocess
    proc = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.returncode, proc.stdout, proc.stderr


def _run_citation_subcommand(module_key: str, sub: str, *, agent: str | None = None) -> dict[str, Any]:
    """Subprocess-invoke ``scripts/citation_backfill.py {research,inject}``.

    Returns a dict shaped ``{"ok": bool, "stdout": str, "stderr": str,
    "returncode": int}``. The script's own JSON output (when it has any)
    is forwarded as-is in ``stdout`` so callers can re-parse if they need
    structured fields.
    """
    import subprocess
    cmd = [_VENV_PYTHON, str(_CITATION_BACKFILL_SCRIPT), sub]
    if agent:
        cmd += ["--agent", agent]
    cmd.append(module_key)
    proc = subprocess.run(
        cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True, check=False,
        timeout=900,
    )
    return {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
    }


def _backfill_one(st: dict[str, Any], *, agent: str | None) -> dict[str, Any]:
    """Run research + inject for one COMMITTED module. Commit on success.

    Returns the outcome dict to be persisted to ``state.backfill``. On
    success, the working module file may have been edited and a new
    commit added on ``main``; this does not establish source acceptance.
    On failure, leaves the worktree clean (``git restore`` rolls back any
    partial inject write).
    """
    slug = st["slug"]
    module_key = _module_key_from_path(st["module_path"])
    repo = _REPO_ROOT
    seed_rel = f"docs/citation-seeds/{module_key.replace('/', '-')}.json"

    def _restore_seed_json() -> None:
        # Research writes the seed before inject runs. `restore` handles
        # tracked/staged seed edits; `clean` removes a brand-new untracked
        # seed and ignores tracked files after they have been restored.
        _git(repo, "restore", "--staged", seed_rel, check=False)
        _git(repo, "restore", seed_rel, check=False)
        _git(repo, "clean", "-f", "--", seed_rel, check=False)

    # Refuse to operate on a dirty primary — any pending edits must be
    # resolved before we mutate the same files. The pipeline never leaves
    # primary dirty between stages, but a human might.
    rc, stdout, _ = _git(repo, "status", "--porcelain", check=False)
    if rc != 0 or stdout.strip():
        return {
            "done": False, "ok": False,
            "error": "primary checkout has uncommitted changes — refusing to backfill",
            "module_key": module_key,
        }

    research = _run_citation_subcommand(module_key, "research", agent=agent)
    if not research["ok"]:
        _restore_seed_json()
        return {
            "done": False, "ok": False, "stage_failed": "research",
            "error": (research["stderr"] or research["stdout"])[-500:],
            "module_key": module_key,
        }

    inject = _run_citation_subcommand(module_key, "inject", agent=agent)
    if not inject["ok"]:
        # `nothing_to_do` means injection found no actionable citation
        # changes; for backfill, this remains a
        # processing-complete path, but it is not source acceptance.
        if inject.get("error") == "nothing_to_do" or "nothing_to_do" in (inject.get("stdout") or ""):
            # A pre-existing true bit is not evidence this run can inherit.
            # Remove it so readiness fails closed after this pipeline pass.
            set_citations_verified_frontmatter(_REPO_ROOT / st["module_path"], verified=False)
            rc, status_all, _ = _git(repo, "status", "--porcelain", check=False)
            if rc != 0:
                _git(repo, "restore", st["module_path"], check=False)
                _restore_seed_json()
                return {
                    "done": False, "ok": False, "stage_failed": "git_status",
                    "error": "git status failed after no-op inject",
                    "module_key": module_key,
                }
            changed_paths = {
                line[3:].strip() for line in status_all.splitlines()
                if line.strip()
            }
            backfill_paths = [p for p in (st["module_path"], seed_rel) if p in changed_paths]
            foreign_paths = changed_paths - set(backfill_paths)
            if foreign_paths:
                # Leave only scope-owned changes in the commit set. Roll
                # back no-op writes if someone else touched this checkout.
                for p in backfill_paths:
                    _git(repo, "restore", p, check=False)
                _restore_seed_json()
                return {
                    "done": False, "ok": False, "stage_failed": "concurrent_edit",
                    "error": f"unexpected working-tree changes outside backfill scope: {sorted(foreign_paths)[:5]}",
                    "module_key": module_key,
                }
            if not backfill_paths:
                return {
                    "done": True, "ok": True, "no_op": True,
                    "reason": "nothing_to_do", "module_key": module_key,
                    **_SOURCE_UNVERIFIED,
                }
            _git(repo, "add", *backfill_paths)
            msg = f"chore(citations): record {module_key} backfill no-op"
            rc, _, stderr = _git(repo, "commit", "-m", msg, check=False)
            if rc != 0:
                for p in backfill_paths:
                    _git(repo, "restore", "--staged", p, check=False)
                    _git(repo, "restore", p, check=False)
                _restore_seed_json()
                return {
                    "done": False, "ok": False, "stage_failed": "git_commit",
                    "error": stderr.strip()[-500:], "module_key": module_key,
                }
            _, sha, _ = _git(repo, "rev-parse", "HEAD")
            return {
                "done": True, "ok": True, "no_op": True,
                "reason": "nothing_to_do", "sha": (sha.strip() if sha else None),
                "module_key": module_key,
                **_SOURCE_UNVERIFIED,
            }
        # Best-effort: discard any partial write so primary stays clean.
        _git(repo, "restore", st["module_path"], check=False)
        _restore_seed_json()
        return {
            "done": False, "ok": False, "stage_failed": "inject",
            "error": (inject["stderr"] or inject["stdout"])[-500:],
            "module_key": module_key,
        }
    # Injection completion is not claim/source verification.  Remove any
    # inherited bit so this unsupported mutation cannot promote readiness.
    set_citations_verified_frontmatter(_REPO_ROOT / st["module_path"], verified=False)

    # The research step writes (or refreshes) the seed JSON; both
    # artifacts (module + seed) must land in the same commit so the
    # provenance is traceable in git history. ``git status --porcelain``
    # without a path lists every file we may need to stage.
    rc, status_all, _ = _git(repo, "status", "--porcelain", check=False)
    if rc != 0:
        _git(repo, "restore", st["module_path"], check=False)
        _restore_seed_json()
        return {
            "done": False, "ok": False, "stage_failed": "git_status",
            "error": "git status failed after inject",
            "module_key": module_key,
        }
    changed_paths = {
        line[3:].strip() for line in status_all.splitlines()
        if line.strip()
    }
    backfill_paths = [p for p in (st["module_path"], seed_rel) if p in changed_paths]
    foreign_paths = changed_paths - set(backfill_paths)
    if foreign_paths:
        # Some other process touched the working tree mid-backfill —
        # refuse to drag those files into our commit. Roll back what
        # citation_backfill wrote so primary stays clean for retry.
        for p in backfill_paths:
            _git(repo, "restore", p, check=False)
        _restore_seed_json()
        return {
            "done": False, "ok": False, "stage_failed": "concurrent_edit",
            "error": f"unexpected working-tree changes outside backfill scope: {sorted(foreign_paths)[:5]}",
            "module_key": module_key,
        }
    if not backfill_paths:
        # Inject succeeded with no diff (e.g. seed had no actionable claims).
        # Mark as done — backfill considered complete for this module.
        return {
            "done": True, "ok": True, "no_op": True,
            "module_key": module_key, **_SOURCE_UNVERIFIED,
        }

    _git(repo, "add", *backfill_paths)
    msg = (
        f"quality(backfill): citation backfill {slug}\n\n"
        f"Sources injected via scripts/citation_backfill.py for module_key "
        f"`{module_key}`. Refs #375."
    )
    rc, _, stderr = _git(repo, "commit", "-m", msg, check=False)
    if rc != 0:
        for p in backfill_paths:
            _git(repo, "restore", "--staged", p, check=False)
            _git(repo, "restore", p, check=False)
        _restore_seed_json()
        return {
            "done": False, "ok": False, "stage_failed": "git_commit",
            "error": stderr.strip()[-500:], "module_key": module_key,
        }

    _, sha, _ = _git(repo, "rev-parse", "HEAD")
    return {
        "done": True, "ok": True, "sha": sha.strip(),
        "module_key": module_key, **_SOURCE_UNVERIFIED,
    }


def cmd_backfill_pending(args: argparse.Namespace) -> int:
    """Run citation_backfill (research + inject) on every COMMITTED module
    that hasn't been backfilled yet. Closes the v2 → citation_backfill
    seam in one command.

    Two-pipeline note: v2 ships modules without ``## Sources`` because
    citation insertion is owned by ``scripts/citation_backfill.py``.
    Without this command, an operator would have to manually loop every
    COMMITTED slug through ``research`` + ``inject``. After this command
    each module's state file gains a ``backfill`` field with ``done``,
    ``ok``, and either a commit ``sha`` or an ``error`` string for retry.
    """
    if not _CITATION_BACKFILL_SCRIPT.exists():
        print(f"missing dependency: {_CITATION_BACKFILL_SCRIPT}")
        return 1

    filters = list(args.only or [])
    if args.module:
        filters.extend(args.module)
    candidates = iter_states(filters or None)
    pending = [
        st for st in candidates
        if st["stage"] == "COMMITTED" and not (st.get("backfill") or {}).get("done")
    ]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(
        f"backfill-pending: {len(pending)} of {len(candidates)} module(s) "
        f"need backfill (agent={args.agent or 'default'})"
    )
    ok = fail = noop = 0
    for st in pending:
        slug = st["slug"]
        outcome = _backfill_one(st, agent=args.agent)
        with state.state_lease(slug) as lease:
            current = lease.load()
            if current is None:
                continue
            current["backfill"] = outcome
            current.setdefault("history", []).append({
                "at": state.now_iso(),
                "stage": current["stage"],
                "note": (
                    "backfill done; source acceptance unverified"
                    if outcome.get("ok") and not outcome.get("no_op")
                    else "backfill no-op; source acceptance unverified"
                    if outcome.get("no_op") and outcome.get("source_acceptance") == "unverified"
                    else "backfill no-op" if outcome.get("no_op")
                    else f"backfill failed: {outcome.get('stage_failed') or 'unknown'}"
                ),
            })
            lease.save(current)
        if outcome.get("ok"):
            if outcome.get("no_op"):
                noop += 1
                print(f"[no-op] {slug}: nothing to inject")
            else:
                ok += 1
                print(f"[ok]    {slug}: {outcome.get('sha', '')[:8]}")
        else:
            fail += 1
            print(f"[fail]  {slug} at {outcome.get('stage_failed')}: {outcome.get('error', '')[:200]}")

    print(f"backfill-pending: ok={ok} no-op={noop} fail={fail}")
    return 0 if fail == 0 else 1


# ---- triage (#388 stage [1]) -----------------------------------------


def cmd_triage(args: argparse.Namespace) -> int:
    """Report which modules carry density attention flags. Read-only.

    This is **stage [1] of the #388 pipeline**: deterministic, free, no
    LLM calls. The scan walks ``CONTENT_ROOT`` (excluding ``uk/`` and
    ``index.md`` per :func:`iter_all_modules`) and lists the both-tail
    flags from :meth:`density.DensityMetrics.attention`.

    Density numbers are diagnostics for the reviewer, never a route
    (#3744, operator balance rule 2026-11-02): the scan writes no state,
    enqueues nothing and sets no ``revision_pending`` banner, because a
    short, long, choppy or walled page is judged against its outcomes,
    not rewritten for a number.
    """
    minimum_prose = args.min_prose

    examined = skipped_count = 0
    flagged: list[tuple[Path, list[str]]] = []

    modules = iter_all_modules() if not args.only else [
        p for p in iter_all_modules() if state.slug_for(p) in set(args.only)
    ]
    for module_path in modules:
        metrics = density.evaluate_module(module_path)
        # Prose-paragraph floor: skip stub/index-shaped files, whose
        # density numbers are noise. The default 10 matches the
        # density.py CLI.
        if metrics.prose_paragraphs < minimum_prose:
            skipped_count += 1
            continue
        examined += 1
        flags = metrics.attention()
        if flags:
            flagged.append((module_path, flags))

    print(
        f"triage scan: {examined} module(s) examined "
        f"(skipped {skipped_count} below --min-prose {minimum_prose})"
    )
    print(f"  flagged for reviewer attention: {len(flagged)}")
    print(f"  no flags:                       {examined - len(flagged)}")
    print()
    print("Diagnostic only — nothing is queued, bannered, rewritten or rejected.")
    if flagged and args.verbose:
        print()
        for path, flags in flagged:
            print(path.resolve().relative_to(_REPO_ROOT))
            for flag in flags:
                print(f"  - {flag}")
    return 0


# ---- reset-stage (admin) ---------------------------------------------


def cmd_reset_stage(args: argparse.Namespace) -> int:
    """Force a module's state to an earlier stage — without the CAS check.

    Used to unstick modules whose state diverged from the on-disk
    reality (e.g. the worktree was manually removed). Prefer
    :func:`stages.recover_in_progress` first.
    """
    slug = args.slug
    to_stage = args.to_stage
    if to_stage not in state.STAGES:
        print(f"unknown stage {to_stage!r}; expected one of {list(state.STAGES)}")
        return 2
    with state.state_lease(slug) as lease:
        st = lease.load()
        if st is None:
            print(f"no state for {slug}")
            return 1
        old = st["stage"]
        st["stage"] = to_stage
        st.setdefault("history", []).append(
            {"at": state.now_iso(), "stage": to_stage, "note": f"admin reset from {old}"}
        )
        lease.save(st)
        print(f"{slug}: {old} → {to_stage}")
    return 0


# ---- cleanup banners ---------------------------------------------------


def _cleanup_banner_for_module(
    primary: Path, slug: str, st: dict[str, Any]
) -> bool:
    """Clear a stranded COMMITTED module's banner and mark queue completion."""
    # The lease must remain external to this helper to avoid nested
    # state-lock re-entry during cleanup.
    is_auto_approved = any(
        h.get("note") == "auto-approved under KUBEDOJO_SKIP_REVIEW"
        for h in st.get("history", [])
    )
    try:
        stages._clear_banner_and_complete_queue(
            primary, slug, st["module_path"], auto_approved=is_auto_approved
        )
        return True
    except Exception:
        logger.exception("banner cleanup failed for %s", slug)
        return False


def cmd_cleanup_banners(args: argparse.Namespace) -> int:
    """Sweep for stranded COMMITTED modules (where completion/banner clear
    failed) and try to clear them again.
    """
    fixed = 0
    failed = 0
    primary = stages._primary()

    for module_path in iter_all_modules():
        if args.only and state.slug_for(module_path) not in args.only:
            continue
            
        slug = state.slug_for(module_path)
        with state.state_lease(slug, timeout=5) as lease:
            st = lease.load()
            if st is None or st["stage"] != "COMMITTED":
                continue
                
            q = st.get("queue")
            if not q or q.get("completed_at") is not None:
                continue
            module_state = dict(st)

        print(f"Cleaning stranded banner for {slug}...")
        if _cleanup_banner_for_module(primary, slug, module_state):
            fixed += 1
        else:
            print(f"Failed to clean banner for {slug}")
            failed += 1

    print(f"\nCleanup complete. Fixed: {fixed}, Failed: {failed}")
    return 0 if failed == 0 else 1


# ---- main -------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quality-pipeline", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bootstrap = sub.add_parser("bootstrap", help="create state files for every module")
    p_bootstrap.set_defaults(func=cmd_bootstrap)

    p_status = sub.add_parser("status", help="stage counts + FAILED summary")
    p_status.add_argument("--only", nargs="*", help="filter by slug(s)")
    p_status.add_argument("-v", "--verbose", action="store_true", help="list FAILED modules")
    p_status.set_defaults(func=cmd_status)

    p_audit = sub.add_parser("audit", help="drive UNAUDITED → AUDITED")
    p_audit.add_argument("--limit", type=int, default=None)
    p_audit.add_argument("--only", nargs="*")
    p_audit.set_defaults(func=cmd_audit)

    p_route = sub.add_parser("route", help="drive AUDITED → WRITE_PENDING or CITATION_CLEANUP_ONLY")
    p_route.add_argument("--limit", type=int, default=None)
    p_route.add_argument("--only", nargs="*")
    p_route.set_defaults(func=cmd_route)

    p_run = sub.add_parser("run", help="drive modules through the full pipeline, worst-first")
    p_run.add_argument("--workers", type=int, default=1)
    p_run.add_argument("--limit", type=int, default=None)
    p_run.add_argument("--only", nargs="*")
    p_run.set_defaults(func=cmd_run)

    p_one = sub.add_parser("run-module", help="drive a single slug end-to-end (smoke)")
    p_one.add_argument("slug")
    p_one.set_defaults(func=cmd_run_module)

    p_triage = sub.add_parser(
        "triage",
        help="#388 stage [1]: report density attention flags (both tails); read-only, never queues or banners",
    )
    p_triage.add_argument(
        "--only",
        nargs="*",
        help="limit scan to specific slug(s)",
    )
    p_triage.add_argument(
        "--min-prose",
        type=int,
        default=10,
        help="ignore modules with fewer than N prose paragraphs (default: 10)",
    )
    p_triage.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="list each flagged module and its attention flags",
    )
    p_triage.set_defaults(func=cmd_triage)

    p_reset = sub.add_parser("reset-stage", help="admin: force a module to a prior stage")
    p_reset.add_argument("slug")
    p_reset.add_argument("to_stage")
    p_reset.set_defaults(func=cmd_reset_stage)

    p_backfill = sub.add_parser(
        "backfill-pending",
        help="run citation_backfill (research+inject) on every COMMITTED module not yet backfilled",
    )
    p_backfill.add_argument("--limit", type=int, default=None)
    p_backfill.add_argument("--only", nargs="*", help="filter by slug(s)")
    p_backfill.add_argument("--module", action="append", default=[], help="filter by a single slug (repeatable)")
    p_backfill.add_argument(
        "--agent",
        choices=("codex", "agy"),
        default=None,
        help="override the agent used by citation_backfill",
    )
    p_backfill.set_defaults(func=cmd_backfill_pending)

    p_cleanup = sub.add_parser(
        "cleanup-banners",
        help="sweep for COMMITTED modules where banner clear failed, and retry",
    )
    p_cleanup.add_argument("--only", nargs="*", help="filter by slug(s)")
    p_cleanup.set_defaults(func=cmd_cleanup_banners)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
