#!/usr/bin/env python3
"""KubeDojo Quality Pipeline — Track 1 (rewrite) + Track 2 (structural).

Resumable per-module state machine that:

  1. AUDITS each module via Gemini (teaching quality vs pedagogical framework)
  2. ROUTES each module based on audit verdict + heuristic structural gaps:
       - needs_rewrite or "thin" → full rewrite by Codex
       - strong/adequate but missing quiz/exercise/diagram → targeted add by Codex
       - otherwise → skip (teaching solid, structure solid — move on)
  3. WRITES (Codex gpt-5.5 high) the rewrite or addition
  4. REVIEWS (Gemini) cross-family, must approve
  5. COMMITS to main with issue ref

State per module lives at .pipeline/quality-pipeline/<slug>.json. Every
transition is write-then-rename atomic. SIGKILL at any point is safe; re-run
picks up where it left off.

Track 3 (citations) is NOT handled here. Findings stay in
.pipeline/v3/human-review/<slug>.json until the citation track resumes.

Usage:
  .venv/bin/python scripts/quality_pipeline.py status
  .venv/bin/python scripts/quality_pipeline.py bootstrap
  .venv/bin/python scripts/quality_pipeline.py audit --workers 1
  .venv/bin/python scripts/quality_pipeline.py route
  .venv/bin/python scripts/quality_pipeline.py write --workers 1 --limit 1
  .venv/bin/python scripts/quality_pipeline.py review --workers 1 --limit 1
  .venv/bin/python scripts/quality_pipeline.py commit --limit 1
  .venv/bin/python scripts/quality_pipeline.py run --workers 1 --limit 5

Testing recipe (one module end-to-end):
  .venv/bin/python scripts/quality_pipeline.py bootstrap \\
      --module src/content/docs/k8s/capa/module-1.2-argo-events.md
  .venv/bin/python scripts/quality_pipeline.py run \\
      --workers 1 --limit 1 --only k8s-capa-module-1.2-argo-events
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"
AUDIT_DIR = REPO_ROOT / ".pipeline" / "teaching-audit"
STATE_DIR = REPO_ROOT / ".pipeline" / "quality-pipeline"
LOGS_DIR = STATE_DIR / "logs"
PROMPTS_DIR = REPO_ROOT / "scripts" / "prompts"

_VENV_PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
DISPATCH = str(REPO_ROOT / "scripts" / "dispatch.py")
AUDIT_SCRIPT = str(REPO_ROOT / "scripts" / "audit_teaching_quality.py")

WORKER_CAP = 3

STAGES = [
    "UNAUDITED",
    "AUDITED",
    "ROUTED",
    "WRITE_PENDING",
    "WRITE_DONE",
    "REVIEW_PENDING",
    "REVIEW_APPROVED",
    "REVIEW_CHANGES",
    "COMMITTED",
    "SKIPPED",
    "FAILED",
]

DEFAULT_WRITER = "gpt-5.5"
DEFAULT_REASONING = "high"
DEFAULT_REVIEWER = "gemini-3.1-pro-preview"


# ---- state management ----------------------------------------------------


def slug_for(path: Path) -> str:
    rel = path.resolve().relative_to(CONTENT_ROOT)
    return str(rel).replace("/", "-").removesuffix(".md")


def state_path_for(slug: str) -> Path:
    return STATE_DIR / f"{slug}.json"


def audit_path_for(slug: str) -> Path:
    return AUDIT_DIR / f"{slug}.json"


def log_path_for(slug: str, kind: str) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"{slug}.{kind}.log"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_state(slug: str) -> dict[str, Any] | None:
    p = state_path_for(slug)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    atomic_write_json(state_path_for(state["slug"]), state)


def new_state(module_path: Path) -> dict[str, Any]:
    slug = slug_for(module_path)
    return {
        "slug": slug,
        "module_path": module_path.resolve().relative_to(REPO_ROOT).as_posix(),
        "stage": "UNAUDITED",
        "track": None,
        "reasons": [],
        "branch": None,
        "audit": None,
        "write": None,
        "review": None,
        "commit": None,
        "retry_count": 0,
        "history": [{"at": now_iso(), "stage": "UNAUDITED", "note": "created"}],
        "failure_reason": None,
    }


def advance(state: dict[str, Any], to: str, **meta: Any) -> None:
    state["stage"] = to
    entry = {"at": now_iso(), "stage": to, **meta}
    state.setdefault("history", []).append(entry)
    save_state(state)


def record_failure(state: dict[str, Any], reason: str) -> None:
    state["stage"] = "FAILED"
    state["failure_reason"] = reason
    state.setdefault("history", []).append({"at": now_iso(), "stage": "FAILED", "reason": reason})
    save_state(state)


# ---- bootstrap -----------------------------------------------------------


def iter_all_modules() -> list[Path]:
    return [
        p
        for p in sorted(CONTENT_ROOT.glob("**/*.md"))
        if "/uk/" not in p.as_posix() and p.name != "index.md"
    ]


def cmd_bootstrap(args: argparse.Namespace) -> int:
    modules = (
        [Path(m).resolve() for m in args.module]
        if args.module
        else iter_all_modules()
    )
    created = existing = 0
    for p in modules:
        slug = slug_for(p)
        if state_path_for(slug).exists():
            existing += 1
            continue
        state = new_state(p)
        # If audit already ran outside the pipeline, promote to AUDITED.
        if audit_path_for(slug).exists():
            audit = json.loads(audit_path_for(slug).read_text(encoding="utf-8"))
            state["audit"] = audit
            state["stage"] = "AUDITED"
            state["history"].append({"at": now_iso(), "stage": "AUDITED", "note": "promoted from existing audit"})
        save_state(state)
        created += 1
    print(f"bootstrap: {created} new, {existing} already-tracked")
    return 0


# ---- status --------------------------------------------------------------


def iter_states(filter_slugs: set[str] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not STATE_DIR.exists():
        return out
    for p in sorted(STATE_DIR.glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        if filter_slugs and s["slug"] not in filter_slugs:
            continue
        out.append(s)
    return out


def cmd_status(args: argparse.Namespace) -> int:
    states = iter_states()
    counts: dict[str, int] = {}
    track_counts: dict[str, int] = {}
    for s in states:
        counts[s["stage"]] = counts.get(s["stage"], 0) + 1
        if s.get("track"):
            track_counts[s["track"]] = track_counts.get(s["track"], 0) + 1
    print(f"Total tracked: {len(states)}")
    print()
    print("By stage:")
    for stage in STAGES:
        if stage in counts:
            print(f"  {counts[stage]:5d}  {stage}")
    if track_counts:
        print()
        print("By track (for ROUTED+):")
        for track in sorted(track_counts):
            print(f"  {track_counts[track]:5d}  {track}")
    failed = [s for s in states if s["stage"] == "FAILED"]
    if failed and args.verbose:
        print()
        print("Failed modules:")
        for s in failed[:20]:
            print(f"  {s['slug']}  — {s.get('failure_reason','?')}")

    if args.verbose:
        print()
        print("Active modules in progress:")
        active = [s for s in states if s["stage"] not in ("COMMITTED", "SKIPPED", "FAILED", "UNAUDITED")]
        if not active:
            print("  (none)")
        for s in active:
            track = s.get('track', 'unknown')
            print(f"  {s['slug']:<40} {s['stage']:<15} {track}")
            
    return 0


# ---- audit stage ---------------------------------------------------------


def audit_one(state: dict[str, Any], timeout: int) -> None:
    """UNAUDITED → AUDITED (or FAILED). Shells to audit_teaching_quality.py."""
    slug = state["slug"]
    module_path = REPO_ROOT / state["module_path"]
    cmd = [_VENV_PYTHON, AUDIT_SCRIPT, "--module", str(module_path), "--workers", "1", "--timeout", str(timeout)]
    log = log_path_for(slug, "audit")
    t0 = time.time()
    try:
        with log.open("w", encoding="utf-8") as fh:
            result = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        record_failure(state, f"audit timeout after {timeout + 60}s")
        return
    if result.returncode != 0 or not audit_path_for(slug).exists():
        record_failure(state, f"audit rc={result.returncode} (see {log})")
        return
    state["audit"] = json.loads(audit_path_for(slug).read_text(encoding="utf-8"))
    advance(state, "AUDITED", elapsed=round(time.time() - t0, 1))


def run_stage(
    states: list[dict[str, Any]],
    input_stages: str | tuple[str, ...],
    fn: Callable[[dict[str, Any]], None],
    workers: int,
    label: str,
    limit: int | None = None,
) -> tuple[int, int]:
    if isinstance(input_stages, str):
        input_stages = (input_stages,)
    candidates = [s for s in states if s["stage"] in input_stages]
    if limit:
        candidates = candidates[:limit]
    if not candidates:
        print(f"{label}: no modules in {input_stages}")
        return 0, 0
    print(f"{label}: {len(candidates)} module(s) in {input_stages} (workers={workers})")
    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fn, s): s for s in candidates}
        for i, fut in enumerate(cf.as_completed(futures), 1):
            s = futures[fut]
            try:
                fut.result()
            except Exception as e:
                record_failure(s, f"{label}: unhandled {type(e).__name__}: {e}")
                fail += 1
                print(f"  [{i}/{len(candidates)}] FAIL  {s['slug']}  ({e})")
                continue
            after = load_state(s["slug"])
            if after and after["stage"] == "FAILED":
                fail += 1
                print(f"  [{i}/{len(candidates)}] FAIL  {s['slug']}  ({after.get('failure_reason','?')})")
            else:
                ok += 1
                new = after["stage"] if after else "?"
                track = after.get("track") if after else None
                extra = f" track={track}" if track else ""
                print(f"  [{i}/{len(candidates)}] ok    {s['slug']} → {new}{extra}")
    return ok, fail


def cmd_audit(args: argparse.Namespace) -> int:
    states = iter_states(set(args.only) if args.only else None)
    workers = min(args.workers, WORKER_CAP)
    ok, fail = run_stage(states, "UNAUDITED", lambda s: audit_one(s, args.timeout), workers, "audit", args.limit)
    print(f"audit: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


# ---- route stage ---------------------------------------------------------


def _module_has_section(module_text: str, patterns: list[str]) -> bool:
    import re
    for pat in patterns:
        if re.search(rf"^##+\s+({pat})\b", module_text, re.IGNORECASE | re.MULTILINE):
            return True
    return False


def route_one(state: dict[str, Any]) -> None:
    """AUDITED → ROUTED. Pure decision logic on audit + file content."""
    module_path = REPO_ROOT / state["module_path"]
    audit = state["audit"] or {}
    verdict = audit.get("verdict")
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    line_count = len(text.splitlines())

    has_quiz = _module_has_section(text, ["quiz", "quick quiz", "quiz yourself", "test yourself", "module quiz", "knowledge check"])
    has_exercise = _module_has_section(text, ["exercise", "hands-on", "practice", "lab"])
    has_diagram = "```mermaid" in text or "<details>" in text

    reasons: list[str] = []
    track: str | None = None

    if verdict == "needs_rewrite":
        track = "rewrite"
        reasons.append(f"audit verdict: needs_rewrite (score {audit.get('teaching_score')})")
    elif line_count < 220:
        track = "rewrite"
        reasons.append(f"thin: {line_count} lines")
    elif verdict in ("strong", "adequate"):
        missing: list[str] = []
        if not has_quiz:
            missing.append("quiz")
        if not has_exercise:
            missing.append("exercise")
        if not has_diagram:
            missing.append("diagram")
        if missing:
            track = "structural"
            reasons.append(f"teaching {verdict}, missing: {', '.join(missing)}")
            state["structural_missing"] = missing
        else:
            track = "skip"
            reasons.append(f"teaching {verdict}, all sections present (citations deferred to Track 3)")
    else:
        track = "skip"
        reasons.append(f"unexpected audit verdict: {verdict!r}")

    state["track"] = track
    state["reasons"] = reasons
    if track == "skip":
        advance(state, "SKIPPED", track=track, reasons=reasons)
    else:
        advance(state, "ROUTED", track=track, reasons=reasons)


def cmd_route(args: argparse.Namespace) -> int:
    states = iter_states(set(args.only) if args.only else None)
    ok, fail = run_stage(states, "AUDITED", route_one, 1, "route", args.limit)
    print(f"route: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


# ---- write stage ---------------------------------------------------------


def _rewrite_prompt(state: dict[str, Any], module_text: str) -> str:
    audit = state.get("audit") or {}
    gaps = audit.get("teaching_gaps") or []
    strengths = audit.get("strengths") or []
    bloom = audit.get("bloom_level_estimated")
    framework = (REPO_ROOT / "docs" / "pedagogical-framework.md").read_text(encoding="utf-8")
    rubric_rules = (REPO_ROOT / ".claude" / "rules" / "module-quality.md").read_text(encoding="utf-8")
    writer_prompt = ""
    wp = PROMPTS_DIR / "module-writer.md"
    if wp.exists():
        writer_prompt = wp.read_text(encoding="utf-8")
    return f"""You are rewriting a KubeDojo curriculum module to fix teaching-quality failures.

## Target module path
{state['module_path']}

## Audit findings (Gemini, cross-family review)
Teaching score: {audit.get('teaching_score')}
Bloom level estimated: {bloom}
Narrative flow: {audit.get('narrative_flow')}
Verdict: {audit.get('verdict')}

Gaps to fix:
{chr(10).join(f'- {g}' for g in gaps)}

Existing strengths to preserve:
{chr(10).join(f'- {s}' for s in strengths)}

## Project-specific module quality standards
{rubric_rules}

## Pedagogical framework you must teach against
{framework}

## Writer prompt conventions (if any)
{writer_prompt or '(no writer prompt found; follow the module-quality.md standards above)'}

## Current module content (the baseline you are rewriting)
```markdown
{module_text}
```

## Your task

Rewrite this module to fix the audit gaps while preserving strengths. Output ONLY the new full module markdown (including frontmatter). No prose before or after. No code fence around the whole output. The output will be written directly to {state['module_path']} verbatim.

Hard requirements:
- Keep the frontmatter (title, slug, sidebar order) unchanged unless slug is wrong.
- Bloom's Level 3+ (Apply/Analyze/Evaluate/Create) — no pure recall.
- Active-learning prompts (predict, diagnose, compare) embedded in the content where they serve the outcomes, not only in the final quiz.
- A worked example for each key skill before asking the learner to practice a similar problem.
- Narrative flow: sections build on each other; no rearrangeable listicle.
- Balance both ways with equal weight: cut padding and repetition, and explain every term, step and reason the learner needs, with worked examples. Do not write to a line or word count; visual aids supplement explanation, they do not replace it.
- Required sections: Learning Outcomes, Why This Module Matters, core content, Did You Know (supported facts only), Common Mistakes (table), Quiz (outcome-aligned scenario questions), Hands-On Exercise, Next Module link.
- Do NOT repeat the number 47 (known LLM pattern).
- Do NOT use emojis.
- Preserve existing Mermaid/ASCII diagrams; improve them, don't remove.
- ## Sources section may be absent; citation work is handled separately. Do NOT invent citations.
"""


def _structural_prompt(state: dict[str, Any], module_text: str) -> str:
    missing = state.get("structural_missing") or []
    rubric_rules = (REPO_ROOT / ".claude" / "rules" / "module-quality.md").read_text(encoding="utf-8")
    return f"""You are adding missing structural sections to a KubeDojo module. The module teaches well; do NOT rewrite existing body.

## Target module path
{state['module_path']}

## Sections to ADD
{', '.join(missing)}

## Project-specific module quality standards
{rubric_rules}

## Current module content
```markdown
{module_text}
```

## Your task

Output ONLY the new full module markdown (frontmatter + all existing content unchanged + the new sections appended in the canonical order). No prose before or after. No code fence around the whole output. The output will be written directly to {state['module_path']}.

Canonical section order (place the new section(s) accordingly):
1. Frontmatter (unchanged)
2. Learning Outcomes
3. Why This Module Matters
4. Core content (unchanged)
5. Did You Know (supported facts only, if adding)
6. Common Mistakes (table of the mistakes learners actually make, if adding)
7. Quiz (outcome-aligned scenario-based questions with <details> answers, if adding)
8. Hands-On Exercise (multi-step with - [ ] success criteria, if adding)
9. Next Module link

Hard requirements:
- Preserve ALL existing content verbatim — do not rewrite prose, code, diagrams, or tables.
- Quiz questions must be scenario-based (Bloom L3+), no recall-only.
- Exercise must be multi-step with success criteria checkboxes.
- Diagrams (if adding) must be Mermaid for flows/sequences or ASCII for static anatomy; must have labels integrated, not in separate legends.
- Do NOT repeat the number 47.
- Do NOT use emojis.
- Do NOT add a ## Sources section — citations are handled separately.
"""



def _section_prompt(state: dict[str, Any], args: argparse.Namespace, module_text: str) -> str:
    rubric_rules = (REPO_ROOT / ".claude" / "rules" / "module-quality.md").read_text(encoding="utf-8")
    return f"""You are rewriting ONLY a specific section of a KubeDojo module.

## Target module path
{state['module_path']}

## Target section to rewrite
{args.section}

## Project-specific module quality standards
{rubric_rules}

## Current module content
```markdown
{module_text}
```

## Your task
Rewrite ONLY the '{args.section}' section to improve its accuracy, explanation and formatting, while keeping ALL other sections of the file identical. Cut padding and repetition, and explain every term, step and reason the learner needs, with worked examples.
For example, if target is 'prereqs', update the prerequisites in the frontmatter or initial block.

Output ONLY the new full module markdown (including frontmatter). No prose before or after. No code fence around the whole output. The output will be written directly to {state['module_path']} verbatim.

Hard requirements:
- Keep the frontmatter (title, slug, sidebar order) unchanged.
- Preserve ALL existing content outside of the targeted section verbatim.
- Do NOT use emojis.
"""

def _git_current_branch() -> str:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()


def _git_has_uncommitted() -> bool:
    out = subprocess.check_output(["git", "-C", str(REPO_ROOT), "status", "--porcelain"], text=True).strip()
    return bool(out)


def _git_create_branch(name: str) -> None:
    subprocess.check_call(["git", "-C", str(REPO_ROOT), "checkout", "-b", name])


def _git_add_commit(message: str, paths: list[str]) -> str:
    subprocess.check_call(["git", "-C", str(REPO_ROOT), "add", "--"] + paths)
    subprocess.check_call(["git", "-C", str(REPO_ROOT), "commit", "-m", message])
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip()


def _git_checkout(ref: str) -> None:
    subprocess.check_call(["git", "-C", str(REPO_ROOT), "checkout", ref])


def write_one(state: dict[str, Any], args: argparse.Namespace) -> None:
    """ROUTED → WRITE_DONE. Dispatches Codex; writes output to module file on a branch."""
    slug = state["slug"]
    track = state["track"]
    module_path = REPO_ROOT / state["module_path"]
    if not module_path.exists():
        record_failure(state, "module file missing")
        return
    module_text = module_path.read_text(encoding="utf-8")

    if args.section:
        prompt = _section_prompt(state, args, module_text)
        track = f"section-{args.section}"
        state["track"] = track
    elif track == "rewrite":
        prompt = _rewrite_prompt(state, module_text)
    elif track == "structural":
        prompt = _structural_prompt(state, module_text)
    else:
        record_failure(state, f"write_one called for unhandled track {track!r}")
        return

    # Only dispatch if we're on main and clean. Per-module branch.
    branch = f"quality/{slug}"
    current = _git_current_branch()
    if _git_has_uncommitted():
        record_failure(state, f"refusing to dispatch with uncommitted changes in {current}")
        return

    existing_branches = subprocess.check_output(["git", "-C", str(REPO_ROOT), "branch", "--list", branch], text=True).strip()
    try:
        if existing_branches:
            subprocess.check_call(["git", "-C", str(REPO_ROOT), "checkout", branch])
        else:
            _git_create_branch(branch)
    except subprocess.CalledProcessError as e:
        record_failure(state, f"git branch setup failed: {e}")
        return

    log = log_path_for(slug, "write")
    t0 = time.time()
    try:
        if args.writer.startswith("gemini"):
            cmd = [
                _VENV_PYTHON, DISPATCH, "gemini", "-",
                "--model", args.writer,
                "--timeout", str(args.timeout)
            ]
            with log.open("w", encoding="utf-8") as fh:
                result = subprocess.run(cmd, input=prompt, stdout=fh, stderr=subprocess.STDOUT, text=True, timeout=args.timeout, cwd=str(REPO_ROOT))
        else:
            # Writer pipeline path: keep search + danger mode for live-corroborated module edits.
            cmd = [
                "codex", "--search", "exec", "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox",
                "-m", args.writer,
                "-c", f'model_reasoning_effort="{args.reasoning}"',
                prompt,
            ]
            with log.open("w", encoding="utf-8") as fh:
                result = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=args.timeout, cwd=str(REPO_ROOT))
    except subprocess.TimeoutExpired:
        _git_checkout(current)
        record_failure(state, f"codex timeout after {args.timeout}s")
        return
    except FileNotFoundError:
        _git_checkout(current)
        record_failure(state, "codex CLI not found on PATH")
        return
    elapsed = time.time() - t0
    if result.returncode != 0:
        _git_checkout(current)
        record_failure(state, f"codex rc={result.returncode} (see {log})")
        return

    # Codex exec output is in the log. Last contiguous block of markdown is the module body.
    raw = log.read_text(encoding="utf-8")
    module_md = _extract_module_markdown(raw)
    if module_md is None:
        _git_checkout(current)
        record_failure(state, "could not extract module markdown from codex output")
        return

    module_path.write_text(module_md, encoding="utf-8")
    try:
        commit_sha = _git_add_commit(
            f"quality({track}): {slug}\n\nTrack: {track}\nReasons: {'; '.join(state.get('reasons') or [])}",
            [state["module_path"]],
        )
    except subprocess.CalledProcessError as e:
        record_failure(state, f"git commit failed: {e}")
        _git_checkout(current)
        return

    diff_size = len(module_md) - len(module_text)
    state["branch"] = branch
    state["write"] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
        "ended_at": now_iso(),
        "elapsed_seconds": round(elapsed, 1),
        "commit_sha": commit_sha,
        "diff_size_bytes": diff_size,
        "log_path": str(log.relative_to(REPO_ROOT)),
    }
    advance(state, "WRITE_DONE")
    _git_checkout(current)


def _extract_module_markdown(raw: str) -> str | None:
    """Codex exec prints prose + the module. Extract the module (starts with ---frontmatter---)."""
    lines = raw.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == "---":
            # Check the next 3 lines for "title:" or "revision_pending:"
            next_lines = [next_line.strip() for next_line in lines[i+1:i+4]]
            if any(next_line.startswith("title:") or next_line.startswith("revision_pending:") for next_line in next_lines):
                start = i
                break
    if start < 0:
        return None
    body = "\n".join(lines[start:]).strip()
    if not body.endswith("\n"):
        body += "\n"
    return body


def cmd_write(args: argparse.Namespace) -> int:
    states = iter_states(set(args.only) if args.only else None)
    workers = min(args.workers, WORKER_CAP)
    if workers > 1:
        print("WARNING: write stage uses git branches; workers>1 is unsafe (branch contention). Forcing workers=1.", file=sys.stderr)
        workers = 1
    ok, fail = run_stage(states, ("ROUTED", "REVIEW_CHANGES"), lambda s: write_one(s, args), workers, "write", args.limit)
    print(f"write: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


# ---- review stage --------------------------------------------------------


def _review_prompt(state: dict[str, Any]) -> str:
    module_path = REPO_ROOT / state["module_path"]
    module_text = module_path.read_text(encoding="utf-8")
    rubric_rules = (REPO_ROOT / ".claude" / "rules" / "module-quality.md").read_text(encoding="utf-8")
    framework = (REPO_ROOT / "docs" / "pedagogical-framework.md").read_text(encoding="utf-8")
    original_gaps = (state.get("audit") or {}).get("teaching_gaps") or []
    track = state.get("track")
    return f"""You are reviewing a KubeDojo curriculum module that was just {track}-ed by Codex. This is a cross-family review (different model family from the writer).

## Target module path
{state['module_path']}

## Original audit gaps that should now be fixed
{chr(10).join(f'- {g}' for g in original_gaps) if original_gaps else '(no prior audit gaps)'}

## Project-specific quality standards
{rubric_rules}

## Pedagogical framework
{framework}

## Module content (after {track})
```markdown
{module_text}
```

## Your task

Return ONLY a JSON object with this exact shape (no preamble, no code fence):

```json
{{
  "verdict": "<approve|changes_requested>",
  "rubric_score": <float 1.0-5.0>,
  "teaching_score": <float 1.0-5.0>,
  "must_fix": [<list of specific, actionable issues — empty if approve>],
  "nits": [<list of 0-5 minor suggestions — not blocking>],
  "strengths": [<list of 1-4 things done well>],
  "reasoning": "<1-3 sentences explaining the verdict>"
}}
```

Rules:
- approve only if teaching_score >= 4.0 AND rubric_score >= 4.0 AND original gaps are genuinely addressed.
- must_fix entries must be specific — e.g., "Quiz question 3 tests recall (what is a Pod?), should be scenario-based".
- Ignore missing ## Sources section — citations are handled separately.
- For track=structural, verify: no existing content was rewritten (preservation check), new sections follow canonical order and Bloom L3+.
- For track=rewrite, verify: narrative flow not listicle, worked examples present, active-learning prompts embedded.
- For track starting with section-, verify ONLY that specific section was improved and everything else remains identical.
- Return ONLY the JSON object. No markdown code fence. No explanatory text before or after.
"""


def _extract_json(text: str) -> dict | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
        if stripped.startswith("json"):
            stripped = stripped[4:].lstrip("\n")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = -1
    return None


def review_one(state: dict[str, Any], args: argparse.Namespace) -> None:
    """WRITE_DONE → REVIEW_APPROVED or REVIEW_CHANGES. Gemini cross-family."""
    slug = state["slug"]
    prompt = _review_prompt(state)
    cmd = [_VENV_PYTHON, DISPATCH, "gemini", "-", "--model", args.reviewer, "--timeout", str(args.timeout)]
    log = log_path_for(slug, "review")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=args.timeout + 30)
    except subprocess.TimeoutExpired:
        record_failure(state, f"review timeout after {args.timeout + 30}s")
        return
    log.write_text((result.stdout or "") + "\n---STDERR---\n" + (result.stderr or ""), encoding="utf-8")
    if result.returncode != 0:
        record_failure(state, f"gemini review rc={result.returncode} (see {log})")
        return
    parsed = _extract_json(result.stdout)
    if parsed is None:
        record_failure(state, f"review parse_error (see {log})")
        return
    elapsed = time.time() - t0
    state["review"] = {
        "verdict": parsed.get("verdict"),
        "rubric_score": parsed.get("rubric_score"),
        "teaching_score": parsed.get("teaching_score"),
        "must_fix": parsed.get("must_fix") or [],
        "nits": parsed.get("nits") or [],
        "strengths": parsed.get("strengths") or [],
        "reasoning": parsed.get("reasoning"),
        "elapsed_seconds": round(elapsed, 1),
        "log_path": str(log.relative_to(REPO_ROOT)),
    }
    if parsed.get("verdict") == "approve":
        advance(state, "REVIEW_APPROVED")
    else:
        state["retry_count"] = state.get("retry_count", 0) + 1
        advance(state, "REVIEW_CHANGES", retry_count=state["retry_count"])


def cmd_review(args: argparse.Namespace) -> int:
    states = iter_states(set(args.only) if args.only else None)
    workers = min(args.workers, WORKER_CAP)
    ok, fail = run_stage(states, "WRITE_DONE", lambda s: review_one(s, args), workers, "review", args.limit)
    print(f"review: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


# ---- commit stage --------------------------------------------------------


def commit_one(state: dict[str, Any]) -> None:
    """REVIEW_APPROVED → COMMITTED. Merges the per-module branch to main."""
    branch = state.get("branch")
    if not branch:
        record_failure(state, "no branch recorded; cannot commit")
        return
    current = _git_current_branch()
    if _git_has_uncommitted():
        record_failure(state, f"refusing to merge with uncommitted changes in {current}")
        return
    try:
        subprocess.check_call(["git", "-C", str(REPO_ROOT), "merge", "--ff-only", branch])
    except subprocess.CalledProcessError as e:
        record_failure(state, f"ff-merge failed: {e} (likely main moved; needs rebase)")
        return
    sha = subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip()
    try:
        subprocess.check_call(["git", "-C", str(REPO_ROOT), "branch", "-d", branch])
    except subprocess.CalledProcessError:
        pass
    state["commit"] = {"sha": sha, "at": now_iso()}
    advance(state, "COMMITTED", sha=sha)


def cmd_commit(args: argparse.Namespace) -> int:
    states = iter_states(set(args.only) if args.only else None)
    ok, fail = run_stage(states, "REVIEW_APPROVED", commit_one, 1, "commit", args.limit)
    print(f"commit: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


# ---- run (cyclic) --------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """Repeat stage passes until no module advances in a full cycle."""
    iterations = 0
    while True:
        iterations += 1
        print(f"\n=== cycle {iterations} ===")
        a = argparse.Namespace(**vars(args))
        cmd_audit(a)
        cmd_route(a)
        cmd_write(a)
        if not args.skip_review:
            cmd_review(a)
            if not args.skip_commit:
                cmd_commit(a)
        # Check if anything is still pending.
        states = iter_states(set(args.only) if args.only else None)
        
        terminal = ["COMMITTED", "SKIPPED", "FAILED"]
        if args.skip_review:
            terminal.extend(["WRITE_DONE"])
        elif args.skip_commit:
            terminal.extend(["REVIEW_APPROVED"])
            
        pending = [s for s in states if s["stage"] not in terminal]
        if not pending:
            print(f"\nAll modules terminal (COMMITTED|SKIPPED|FAILED) after {iterations} cycle(s).")
            break
        if iterations >= args.max_cycles:
            print(f"\nHit max-cycles={args.max_cycles}; {len(pending)} still pending.")
            break
    return 0


# ---- main ----------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_boot = sub.add_parser("bootstrap", help="Create per-module state files (idempotent)")
    p_boot.add_argument("--module", action="append", default=[])
    p_boot.set_defaults(func=cmd_bootstrap)

    p_stat = sub.add_parser("status", help="Summary of pipeline state")
    p_stat.add_argument("--verbose", "-v", action="store_true")
    p_stat.set_defaults(func=cmd_status)

    def _shared(p: argparse.ArgumentParser, default_workers: int = 1, default_timeout: int = 900) -> None:
        p.add_argument("--workers", type=int, default=default_workers, help=f"Parallel workers (cap {WORKER_CAP})")
        p.add_argument("--timeout", type=int, default=default_timeout)
        p.add_argument("--limit", type=int, default=None, help="Process at most N modules")
        p.add_argument("--only", action="append", default=[], help="Restrict to specific slugs (may repeat)")
        p.add_argument("--writer", type=str, default=DEFAULT_WRITER, help="Model for writing (Codex)")
        p.add_argument("--reasoning", type=str, default=DEFAULT_REASONING, help="Reasoning effort for writing")
        p.add_argument("--reviewer", type=str, default=DEFAULT_REVIEWER, help="Model for reviewing (Gemini)")
        p.add_argument("--section", type=str, default=None, help="Target specific section to rewrite (e.g. 'prereqs')")

    p_audit = sub.add_parser("audit", help="UNAUDITED → AUDITED")
    _shared(p_audit, default_timeout=300)
    p_audit.set_defaults(func=cmd_audit)

    p_route = sub.add_parser("route", help="AUDITED → ROUTED | SKIPPED")
    _shared(p_route)
    p_route.set_defaults(func=cmd_route)

    p_write = sub.add_parser("write", help="ROUTED → WRITE_DONE (Codex)")
    _shared(p_write, default_timeout=1500)
    p_write.set_defaults(func=cmd_write)

    p_review = sub.add_parser("review", help="WRITE_DONE → REVIEW_APPROVED|REVIEW_CHANGES (Gemini)")
    _shared(p_review, default_timeout=600)
    p_review.set_defaults(func=cmd_review)

    p_commit = sub.add_parser("commit", help="REVIEW_APPROVED → COMMITTED (ff-merge)")
    _shared(p_commit)
    p_commit.set_defaults(func=cmd_commit)

    p_run = sub.add_parser("run", help="Cycle through all stages until no progress")
    _shared(p_run, default_timeout=1500)
    p_run.add_argument("--max-cycles", type=int, default=8)
    p_run.add_argument("--skip-review", action="store_true", help="Stop after writing, skip review & commit")
    p_run.add_argument("--skip-commit", action="store_true", help="Stop after review, skip commit")
    p_run.set_defaults(func=cmd_run)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
