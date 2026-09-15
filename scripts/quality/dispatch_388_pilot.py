#!/usr/bin/env python3
"""#388 volume-run dispatcher (originally Day 2 pilot, now generalized).

For each module path in --input (default scripts/quality/pilot-2026-05-02.txt):
  1. Worktree at .worktrees/codex-388-pilot-<slug> from origin/main
  2. Codex (gpt-5.5, mode=danger) rewrites per module-rewriter-388.md,
     runs verifier, commits, pushes, opens PR
  3. Cross-family review on the PR (agy — the Google lane — with claude/qwen fallback)
  4. APPROVE       -> retain PR/review and hold for a real source-acceptance receipt
     APPROVE_WITH_NITS -> log + post review; orchestrator triages (C3 fix-up lane)
     NEEDS CHANGES -> log + hold; orchestrator decides (re-dispatch vs inline)
  5. Brief pause; next module

Sequential per item. JSONL log under logs/.

The APPROVE hold is an interim containment measure: this dispatcher does not
merge or run post-merge citation backfill until a real source-acceptance gate
is integrated. It does not treat ordinary review, CI, or inherited metadata
as source evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Derive REPO from this file's location so the dispatcher works from any
# checkout (primary OR a worktree) without a hard-coded absolute path.
# scripts/quality/dispatch_388_pilot.py -> repo root is parents[2].
REPO = Path(__file__).resolve().parents[2]
PRIMARY_REPO = REPO.parent.parent if REPO.parent.name == ".worktrees" else REPO
PILOT_FILE = REPO / "scripts/quality/pilot-2026-05-02.txt"
LOG = REPO / "logs/388_pilot_2026-05-02.jsonl"
BRIEF = REPO / "scripts/prompts/module-rewriter-388.md"
WRITER_BRIEF = REPO / "scripts/prompts/module-writer.md"
VENV_PYTHON = PRIMARY_REPO / ".venv" / "bin" / "python"

sys.path.insert(0, str(REPO / "scripts"))
from agent_runtime.errors import (
    AgentTimeoutError,
    AgentUnavailableError,
    RateLimitedError,
)
from agent_runtime.runner import invoke
from lib.pr_merge import PrMergeError, merge_when_green


def module_slug_for_pipeline(module_path: str) -> str:
    module = Path(module_path)
    if not module.is_absolute():
        module = REPO / module
    try:
        relative = module.relative_to(PRIMARY_REPO / "src" / "content" / "docs")
    except ValueError:
        rel = module.as_posix()
        prefix_parts = rel.split("/src/content/docs/", 1)
        if len(prefix_parts) == 2:
            rel = prefix_parts[1]
        elif rel.startswith("src/content/docs/"):
            rel = rel[len("src/content/docs/"):]
        else:
            rel = rel.removeprefix(f"{REPO.as_posix().removesuffix('/')}/")
            rel = rel.removeprefix(f"{PRIMARY_REPO.as_posix().removesuffix('/')}/")
            rel = rel.removeprefix("/src/content/docs/")
        return rel.removesuffix(".md").replace("/", "-")
    return relative.as_posix().removesuffix(".md").replace("/", "-")


def _module_path_for_marker(module_path: str) -> str:
    module = Path(module_path)
    if module.is_absolute() and module.is_relative_to(PRIMARY_REPO):
        module = module.relative_to(PRIMARY_REPO)
    normalized = module.as_posix().replace("\\", "/")
    normalized = normalized.removeprefix("./")
    normalized = normalized.removeprefix("/")
    return normalized


def _module_budget_slug(module_path: str) -> str:
    module = Path(module_path)
    if not module.is_absolute():
        module = REPO / module
    try:
        relative = module.relative_to(PRIMARY_REPO / "src" / "content" / "docs")
        rel = relative.as_posix()
    except ValueError:
        rel = module.as_posix()
        if rel.startswith(f"{REPO.as_posix().removesuffix('/')}/"):
            rel = rel.removeprefix(f"{REPO.as_posix().removesuffix('/')}/")
        if rel.startswith("src/content/docs/"):
            rel = rel.removeprefix("src/content/docs/")
        rel = rel.removeprefix(f"{PRIMARY_REPO.as_posix().removesuffix('/')}/")
        rel = rel.removeprefix("src/content/docs/")
    return rel.replace("/", "__")


def _parse_yaml_queue(queue_text: str) -> list[dict[str, object]]:
    loaded = yaml.safe_load(queue_text) or {}
    entries = loaded.get("queue", loaded) if isinstance(loaded, dict) else loaded
    if not isinstance(entries, list):
        raise TypeError("YAML dispatch queue must be a dict with a 'queue' list or a list")
    normalized: list[dict[str, object]] = []
    for row in entries:
        if isinstance(row, str):
            normalized.append({"path": row})
            continue
        if not isinstance(row, dict):
            raise TypeError("YAML dispatch queue entries must be strings or mappings")
        if "path" not in row:
            raise ValueError("YAML dispatch queue entry missing required 'path'")
        normalized.append(row)
    return normalized


def _queue_from_file(input_file: Path) -> list[tuple[str, int | None]]:
    if input_file.suffix.lower() == ".yaml":
        entries = _parse_yaml_queue(input_file.read_text(encoding="utf-8"))
        loaded: list[tuple[str, int | None]] = []
        for row in entries:
            path = str(row["path"]).strip()
            budget_value = row.get("budget")
            if budget_value is None:
                loaded.append((path, None))
                continue
            loaded.append((path, int(budget_value)))
        return loaded
    return [
        (line.strip(), None)
        for line in input_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _write_budget_sidecar(module_path: str, body_words_min: int) -> Path:
    payload = {
        "body_words_min": int(body_words_min),
        "source_module": module_path,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    slug = _module_budget_slug(module_path)
    sidecar = REPO / ".pipeline" / "budgets" / f"{slug}.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return sidecar


def log(event: dict) -> None:
    event["ts"] = time.time()
    with open(LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(f"[{time.strftime('%H:%M:%S')}] {event.get('event')}: {event}", flush=True)


def slugify(path: str) -> str:
    return module_slug_for_pipeline(path)


def make_worktree(slug: str, module_path: str) -> Path:
    branch = f"codex/388-pilot-{slug}"
    wt = REPO / f".worktrees/codex-388-pilot-{slug}"
    if wt.exists():
        marker = wt / ".module_path"
        if not marker.exists():
            raise RuntimeError(f"cannot reuse worktree {wt}: marker file .module_path missing")
        expected = _module_path_for_marker(module_path)
        actual = marker.read_text(encoding="utf-8").strip()
        if actual != expected:
            raise RuntimeError(
                f"existing worktree {wt} was created for {actual!r}, not {expected!r}"
            )
        return wt
    wt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "fetch", "origin", "main"], cwd=REPO, check=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt), "origin/main"],
        cwd=REPO, check=True,
    )
    wt.mkdir(parents=True, exist_ok=True)
    marker = wt / ".module_path"
    marker.write_text(_module_path_for_marker(module_path), encoding="utf-8")
    return wt


def codex_prompt(module_path: str, body_words_target: int = 5000) -> str:
    brief = BRIEF.read_text().replace("{{BODY_WORDS_TARGET}}", str(body_words_target))
    writer = WRITER_BRIEF.read_text().replace("{{BODY_WORDS_TARGET}}", str(body_words_target))
    return f"""You are rewriting one KubeDojo module to clear all #388 verifier gates.

MODULE TO REWRITE (relative to repo root): {module_path}

You are running in a fresh git worktree branched from origin/main. The full repo is checked out. You may read any file but must MODIFY ONLY the module path above.

PROCEDURE
1. Read the existing module to extract topic coverage, code blocks, ASCII/mermaid diagrams, tables, and source URLs. These are PROTECTED ASSETS — preserve them in the rewrite (you may rephrase surrounding prose).
2. Read scripts/prompts/module-rewriter-388.md (BELOW, BINDING) and scripts/prompts/module-writer.md (BELOW, structural baseline).
3. Rewrite the module IN PLACE at the path above.
4. Run the deterministic verifier:
     .venv/bin/python scripts/quality/verify_module.py --glob {module_path} --skip-source-check --summary --quiet
   Iterate until tier == T0 OR all density+structure+alignment+anti_leak+protected_assets gates pass. Sources gate may fail (we skip source check).
   Hard requirements: body_words >= {body_words_target}, mean_wpp >= 30, median_wpp >= 28, short_paragraph_rate <= 0.20, max_consecutive_short_run <= 2, exactly 4 Did You Know, 6-8 Common Mistakes, 6-8 Quiz with <details>, Hands-On with `- [ ]`. Section order per writer brief. No emojis. No number 47. K8s 1.35+. Never use `alias k=kubectl` or `k <subcommand>` in runnable bash/sh/shell/zsh code blocks; use full `kubectl`.
5. Set frontmatter `revision_pending: false` (it is currently `true` — clear it as part of the rewrite). Then commit (sign-off optional, no --no-verify):
     git add {module_path}
     git commit -m "feat(388): density+structure rewrite of <module title> (#388 pilot)"
6. Push branch:
     git push -u origin HEAD
7. Open the PR:
     gh pr create --base main --title "feat(388): rewrite <slug> (#388 pilot)" --body "<body>"
   Body must include: verifier summary line (tiers + key metrics body_words/mean_wpp/median_wpp/short_rate/max_run), confirmation that protected assets were preserved with counts, and the commit SHA.
8. Reply with the PR URL on the last line.

DO NOT modify any file outside {module_path}. DO NOT change scripts/, docs/, sibling modules, or the verifier.

=== module-rewriter-388.md (BINDING) ===
{brief}

=== module-writer.md (structural baseline) ===
{writer}
"""


def dispatch_codex(module_path: str, wt: Path, slug: str, body_words_target: int = 5000):
    log({"event": "codex_dispatch_start", "module": module_path, "slug": slug, "wt": str(wt)})
    try:
        result = invoke(
            agent_name="codex",
            prompt=codex_prompt(module_path, body_words_target),
            mode="danger",
            cwd=wt,
            model="gpt-5.5",
            task_id=f"388-pilot-{slug}",
            entrypoint="dispatch",
            hard_timeout=5400,  # 90 min
        )
    except (AgentTimeoutError, RateLimitedError, AgentUnavailableError) as e:
        log({"event": "codex_error", "module": module_path, "error": repr(e)})
        return None
    log({
        "event": "codex_done",
        "module": module_path,
        "ok": result.ok,
        "elapsed_s": getattr(result, "elapsed_s", None),
        "response_excerpt": (result.response or "")[-2000:],
    })
    return result


def find_pr_number(text: str) -> int | None:
    m = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", text or "")
    return int(m.group(1)) if m else None


def orchestrator_open_pr(slug: str, module_path: str, codex_response: str) -> int | None:
    """Fallback: orchestrator opens PR when codex sandbox lacked GH_TOKEN.

    Codex's response (when ok=True) typically includes the branch name,
    word counts, and verifier metrics. We construct a minimal PR body
    from the last N chars of the response; the cross-family review
    will look at the actual diff anyway.
    """
    branch = f"codex/388-pilot-{slug}"
    # Verify the branch is on origin (codex pushes before responding)
    ls = subprocess.run(
        ["git", "ls-remote", "origin", branch],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    if ls.returncode != 0 or not ls.stdout.strip():
        log({"event": "orchestrator_pr_branch_missing", "slug": slug, "branch": branch})
        return None
    title = f"feat(388): rewrite {module_path}"
    body = (
        f"## Summary\n\n"
        f"#388 sweep — rewrite of `{module_path}` for rubric-critical score.\n\n"
        f"## Codex response excerpt\n\n"
        f"```\n{(codex_response or '')[-1500:]}\n```\n\n"
        f"## Test plan\n\n"
        f"- [ ] Cross-family review per `docs/review-protocol.md`\n"
        f"- [ ] Verify rubric score >=4.0 post-merge\n\n"
        f"PR opened by orchestrator (codex sandbox lacks GH_TOKEN by design).\n"
    )
    create = subprocess.run(
        ["gh", "pr", "create", "--base", "main", "--head", branch,
         "--title", title, "--body", body],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    if create.returncode != 0:
        log({
            "event": "orchestrator_pr_create_failed",
            "slug": slug, "branch": branch,
            "stderr": create.stderr[-500:],
        })
        return None
    pr_num = find_pr_number(create.stdout or "")
    if pr_num is None:
        log({"event": "orchestrator_pr_no_url", "slug": slug, "stdout": create.stdout[-500:]})
        return None
    log({"event": "orchestrator_pr_opened", "slug": slug, "pr": pr_num, "branch": branch})
    return pr_num


def cross_family_review_prompt(pr_num: int, module_path: str) -> str:
    return f"""Adversary cross-family review of PR #{pr_num} on KubeDojo.

This is a #388 Day 2 pilot rewrite of: {module_path}

Per docs/review-protocol.md, you are the cross-family reviewer.

Inspect with `gh pr view {pr_num}` and `gh pr diff {pr_num}`. Then evaluate:

1. PEDAGOGY — Does it TEACH (Bloom's L3+)? Is the learning arc scaffolded? Are quiz questions scenario-based with reasoning explanations? Is there constructive alignment between Learning Outcomes, core sections, and the quiz/lab?
2. ACCURACY — All commands runnable? K8s 1.35+ surfaces? No hallucinated flags/APIs? Versions reasonable?
3. DENSITY DOES NOT EQUAL TEACHING — The deterministic verifier already gates on density. You must judge whether the prose is genuinely teaching or just padded to clear gates. Flag any padded paragraphs you find.
4. PROTECTED ASSETS — Code blocks, ASCII/mermaid diagrams, tables, source URLs preserved across the rewrite (counts in PR body should match).
5. SOURCES — Each source actually reaches a primary/vendor doc, not marketing fluff. Flag dead/redirect URLs if you can spot any.
6. LAB RUNNABILITY — Walk every lab step and drill in order. For each `kubectl exec`, `kubectl run`, `kubectl edit`, `kubectl delete`, or container-shell command the lab tells the learner to run, check:
   (a) Container binaries — citation-forced check. For EACH `kubectl exec POD -- BIN [args]` in the module:
       (i)   Quote the line that establishes POD's image. This is either a `kubectl run POD --image=IMAGE` line earlier in the module, or an inline YAML manifest `name: POD` followed by `image: IMAGE`. Include the line as-is in your review.
       (ii)  State the EXACT image tag from (i), including the tag suffix. `nginx` is debian-slim (no wget, no curl). `nginx:alpine` is alpine + busybox (has wget). `busybox` has wget. `curlimages/curl` has curl. Do NOT confuse `nginx` with `nginx:alpine` — they are different images with different binary inventories.
       (iii) Cite a primary source for the binary presence: the Docker Hub image overview page, the upstream Dockerfile, or a known reference (e.g. "alpine busybox ships wget by default" — link the busybox project page). A confident assertion without a citation is NOT acceptable — flag NEEDS CHANGES on any uncited binary claim.
       (iv)  If the binary is NOT in the image and there is no alternative path (an init container that installs it, a sidecar with the binary, a `kubectl cp` of a static binary), this is a blocking LAB RUNNABILITY failure. Cite #1229 and #1257 as precedents — both shipped because this check was performed without citation.
   (b) Role / ClusterRole verbs vs operations: does the Role grant ALL the verbs the lab actually exercises? `kubectl edit` needs `get,list,update`; `kubectl delete` needs `get,list,delete`; `kubectl exec` needs `get` on pods + `create` on pods/exec. Cross-reference every `--verb=...` line in the YAML against every operation the lab/drill performs.
   (c) Resource scope mismatch: namespaced operations attempted with cluster-scoped permissions (or vice versa).
   (d) Order of operations: lab steps that reference prior state (a pod, secret, configmap) that wasn't actually created in an earlier step.

   (e) Hallucination self-check. After completing (a)-(d), re-read your own LAB RUNNABILITY paragraph. For every factual claim about an image's binary inventory, ensure you quoted the image tag verbatim from the module AND cited a source. Claims like "nginx ships wget" without a paired image-tag quote and source citation are exactly the pattern that produced the #1257 false-approval. Strike any uncited claim from your review.

   This dimension catches the bug class that lets lab-breaking PRs through content review (#1229 shipped with nginx-image-vs-kubectl and missing-verb bugs because no review dimension explicitly probed it).

End your review with EXACTLY ONE of:
  VERDICT: APPROVE
  VERDICT: APPROVE WITH NITS
  VERDICT: NEEDS CHANGES

Keep the review under 700 words. If any LAB RUNNABILITY check fails, the floor is NEEDS CHANGES — lab bugs are blocking, not nits.
"""


def dispatch_claude_review(pr_num: int, module_path: str, slug: str):
    """Fallback when the primary reviewer fails. Headless Claude (sonnet) cross-family review."""
    log({"event": "claude_review_start", "pr": pr_num, "module": module_path})
    try:
        result = invoke(
            agent_name="claude",
            prompt=cross_family_review_prompt(pr_num, module_path),  # reuse same prompt
            mode="read-only",
            cwd=REPO,
            model="claude-sonnet-4-6",
            task_id=f"388-pilot-review-claude-{slug}",
            entrypoint="dispatch",
            hard_timeout=300,
        )
    except Exception as e:  # noqa: BLE001
        log({"event": "claude_review_error", "pr": pr_num, "error": repr(e)})
        return None, "ERROR"
    text = result.response or ""
    log({"event": "claude_review_done", "pr": pr_num, "ok": result.ok, "response_excerpt": text[-2000:]})
    return text, classify_verdict(text)


def dispatch_qwen_review(pr_num: int, module_path: str, slug: str):
    """Cross-family review via Qwen 3.6 (hermes openrouter).

    Qwen is a peer cross-family reviewer alongside agy and claude-sonnet.
    Uses the same prompt (cross_family_review_prompt). Qwen's strengths: independent
    family and hermes terminal/file toolsets so it can curl URLs and inspect
    the diff itself.

    Selection:
        - Primary: set ``KUBEDOJO_388_PRIMARY_REVIEWER=qwen`` to make this the
          first-pass reviewer in the cascade.
        - Tertiary: if agy and claude both return ERROR/UNCLEAR, qwen is
          the third-line reviewer.
        - Manual: callable directly from one-off review scripts (mirrors
          dispatch_agy_review / dispatch_claude_review shape).
    """
    log({"event": "qwen_review_start", "pr": pr_num, "module": module_path})
    try:
        result = invoke(
            agent_name="qwen",
            prompt=cross_family_review_prompt(pr_num, module_path),  # reuse same prompt
            mode="workspace-write",  # qwen benefits from terminal+file tools (curl, gh pr diff)
            cwd=REPO,
            task_id=f"388-pilot-review-qwen-{slug}",
            entrypoint="dispatch",
            hard_timeout=600,
            tool_config={
                "toolsets": "web,file,terminal,code_execution,todo",
                "yolo": True,
            },
        )
    except Exception as e:  # noqa: BLE001
        log({"event": "qwen_review_error", "pr": pr_num, "error": repr(e)})
        return None, "ERROR"
    text = result.response or ""
    log({"event": "qwen_review_done", "pr": pr_num, "ok": result.ok, "response_excerpt": text[-2000:]})
    return text, classify_verdict(text)


def dispatch_deepseek_review(pr_num: int, module_path: str, slug: str):
    """Cross-family review via DeepSeek.

    Calibration 2026-05-19 (session 30) showed DS Pro/Flash hallucinate on GH
    Actions / Dependabot schemas during diff review. Use as primary only for
    content-module review where its strong text recall outweighs the
    schema-hallucination risk. NOT recommended as a default reviewer.
    """
    log({"event": "deepseek_review_start", "pr": pr_num, "module": module_path})
    try:
        result = invoke(
            agent_name="deepseek",
            prompt=cross_family_review_prompt(pr_num, module_path),  # reuse same prompt
            mode="workspace-write",  # deepseek benefits from terminal+file access
            cwd=REPO,
            model="deepseek-v4-pro",
            task_id=f"388-pilot-review-deepseek-{slug}",
            entrypoint="dispatch",
            hard_timeout=600,
        )
    except Exception as e:  # noqa: BLE001
        log({"event": "deepseek_review_error", "pr": pr_num, "error": repr(e)})
        return None, "ERROR"
    text = result.response or ""
    log({"event": "deepseek_review_done", "pr": pr_num, "ok": result.ok, "response_excerpt": text[-2000:]})
    return text, classify_verdict(text)


def dispatch_agy_review(pr_num: int, module_path: str, slug: str):
    """Cross-family review via Agy (Antigravity CLI — Google).

    Agy is the Google lane (it replaced the retired gemini-cli per #1350/#2125)
    for the Google One / unpaid tier. Run-time:
    - mode=danger required (dispatch_smart enforces this for agy)
    - no `model=` arg — agy picks model via its TUI panel (env override:
      KUBEDOJO_AGY_MODEL; adapter default gemini-3.5-flash-high)

    Failure shapes and how they surface to the cascade:
    - Quota-exhausted: invoke returns ok=False, response="" — this function
      returns ("", "UNCLEAR") (classify_verdict on the empty string).
    - OAuth-expired: invoke returns ok=True with body containing the
      auth-prompt URL and "authentication timed out" — classify_verdict
      finds no VERDICT line, returns "UNCLEAR".
    - Exception inside invoke (network/transport failure, adapter crash):
      caught below, returns (None, "ERROR").
    All three cases let the cascade fall to the next reviewer; the
    distinction matters only when reading dispatch logs after a failure.
    """
    log({"event": "agy_review_start", "pr": pr_num, "module": module_path})
    try:
        result = invoke(
            agent_name="agy",
            prompt=cross_family_review_prompt(pr_num, module_path),  # reuse same prompt
            mode="danger",  # required for agy in headless dispatch
            cwd=REPO,
            task_id=f"388-pilot-review-agy-{slug}",
            entrypoint="dispatch",
            hard_timeout=900,
        )
    except Exception as e:  # noqa: BLE001
        log({"event": "agy_review_error", "pr": pr_num, "error": repr(e)})
        return None, "ERROR"
    text = result.response or ""
    log({"event": "agy_review_done", "pr": pr_num, "ok": result.ok, "response_excerpt": text[-2000:]})
    return text, classify_verdict(text)


def classify_verdict(text: str) -> str:
    """Classify a reviewer's verdict into APPROVE / APPROVE_WITH_NITS / NEEDS CHANGES / UNCLEAR.

    Order matters: must check APPROVE WITH NITS BEFORE APPROVE so the
    longer phrase wins (otherwise nits silently auto-merge — see #388
    Day 2 pilot ab-discuss day3-388 deliberation, 2026-05-02).
    """
    upper = (text or "").upper()
    tail = upper.split("VERDICT:")[-1]
    if "VERDICT: NEEDS CHANGES" in upper or "NEEDS CHANGES" in tail:
        return "NEEDS CHANGES"
    if "VERDICT: APPROVE WITH NITS" in upper or "APPROVE WITH NITS" in tail:
        return "APPROVE_WITH_NITS"
    if "VERDICT: APPROVE" in upper:
        return "APPROVE"
    return "UNCLEAR"


def post_review_comment(pr_num: int, body: str) -> None:
    subprocess.run(
        ["gh", "pr", "comment", str(pr_num), "--body",
         f"## Cross-family review (#388 pilot)\n\n{body}"],
        cwd=REPO, check=False,
    )


def merge_pr(pr_num: int) -> str | None:
    try:
        return merge_when_green(pr_num, repo=REPO)
    except PrMergeError as exc:
        log({"event": "merge_failed", "pr": pr_num, "error": str(exc)})
    return None


def recheck_module_source_acceptance(worktree: Path, module_path: str) -> dict[str, object]:
    """Fail-closed PR-head recheck. Does not unlock merge or backfill."""
    rel = module_path.replace("\\", "/")
    prefix = "src/content/docs/"
    idx = rel.find(prefix)
    if idx >= 0:
        rel = rel[idx + len(prefix) :]
    try:
        head_bytes = (Path(worktree) / module_path).read_bytes()
    except OSError:
        head_bytes = None
    from quality.source_acceptance import recheck_held_publication
    return recheck_held_publication(Path(worktree), rel, pr_head_page_bytes=head_bytes)


def build_reviewer_cascade(primary_reviewer: str) -> list[tuple[str, Callable]]:
    if primary_reviewer == "claude":
        return [
            ("claude", dispatch_claude_review),
            ("agy", dispatch_agy_review),
            ("qwen", dispatch_qwen_review),
        ]
    if primary_reviewer == "deepseek":
        return [
            ("deepseek", dispatch_deepseek_review),
            ("claude", dispatch_claude_review),
            ("qwen", dispatch_qwen_review),
        ]
    if primary_reviewer == "qwen":
        # qwen → agy → claude
        return [
            ("qwen", dispatch_qwen_review),
            ("agy", dispatch_agy_review),
            ("claude", dispatch_claude_review),
        ]
    # default (also handles the retired "gemini" value): agy → claude → qwen.
    # agy is the Google lane (gemini-cli retired, #2125); fall to claude first.
    return [
        ("agy", dispatch_agy_review),
        ("claude", dispatch_claude_review),
        ("qwen", dispatch_qwen_review),
    ]


def dispatch_backfill(slug: str, module_path: str) -> bool:
    log({"event": "backfill_start", "slug": slug, "module_path": module_path})
    pipeline_slug = module_slug_for_pipeline(module_path)
    pull = subprocess.run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=PRIMARY_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if pull.returncode != 0:
        log({
            "event": "backfill_failed",
            "slug": slug,
            "reason": "pull_failed",
            "detail": f"{pull.stderr or pull.stdout}".strip()[-500:],
        })
        return False
    backfill = subprocess.run(
        [str(VENV_PYTHON), "-m", "scripts.quality.pipeline", "backfill-pending", "--module", pipeline_slug],
        cwd=PRIMARY_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if backfill.returncode != 0:
        log({
            "event": "backfill_failed",
            "slug": slug,
            "reason": "pipeline_failed",
            "detail": f"{backfill.stderr or backfill.stdout}".strip()[-500:],
        })
        return False

    made_commit = any(line.startswith("[ok]") for line in backfill.stdout.splitlines())
    if not made_commit:
        log({"event": "backfill_skipped_noop", "slug": slug})
        return True

    push = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=PRIMARY_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if push.returncode != 0:
        log({
            "event": "push_failed",
            "slug": slug,
            "reason": "push_failed",
            "rc": push.returncode,
            "detail": f"{push.stderr or push.stdout}".strip()[-500:],
        })
        return False

    match = re.search(rf"^\[ok\]\s+{re.escape(pipeline_slug)}:\s+([0-9a-f]+)", backfill.stdout, re.MULTILINE)
    sha = match.group(1) if match else None
    log({"event": "backfill_done", "slug": slug, "sha": sha})
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="#388 volume-run dispatcher")
    p.add_argument(
        "--input", "-i", type=Path, default=None,
        help=f"Path to module queue (.txt or .yaml). Default: {PILOT_FILE.relative_to(REPO)}",
    )
    p.add_argument(
        "--max", "-n", type=int, default=0,
        help="Stop after this many modules (0 = unlimited).",
    )
    p.add_argument(
        "--log", type=Path, default=None,
        help=f"Override log path. Default: {LOG.relative_to(REPO)}",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global LOG
    args = parse_args(argv)
    input_file = args.input or PILOT_FILE
    if args.log is not None:
        LOG = args.log
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not input_file.exists():
        print(f"❌ input file not found: {input_file}", file=sys.stderr)
        return 1
    try:
        queue = _queue_from_file(input_file)
    except (ValueError, TypeError, yaml.YAMLError, OSError) as exc:
        print(f"❌ failed to read queue: {exc}", file=sys.stderr)
        return 1
    if args.max and args.max > 0:
        queue = queue[: args.max]
    log({"event": "pilot_start", "count": len(queue), "input": str(input_file), "repo": str(REPO)})
    for module_path, requested_budget in queue:
        body_words_target = requested_budget if requested_budget is not None else 5000
        if requested_budget is not None:
            _write_budget_sidecar(module_path, body_words_target)
            log({"event": "budget_sidecar_written", "module": module_path, "body_words_min": body_words_target})
        slug = module_slug_for_pipeline(module_path)
        log({"event": "module_start", "module": module_path, "slug": slug})
        try:
            wt = make_worktree(slug, module_path)
        except Exception as e:  # noqa: BLE001
            log({"event": "worktree_error", "module": module_path, "error": repr(e)})
            continue
        codex_result = dispatch_codex(module_path, wt, slug, body_words_target)
        if codex_result is None or not codex_result.ok:
            log({"event": "module_skip", "module": module_path, "reason": "codex_failed"})
            continue
        pr_num = find_pr_number(codex_result.response or "")
        if pr_num is None:
            # Codex sandbox lacks GH_TOKEN by design — fall back to orchestrator.
            pr_num = orchestrator_open_pr(slug, module_path, codex_result.response or "")
            if pr_num is None:
                log({"event": "module_skip", "module": module_path, "reason": "pr_creation_failed"})
                continue
        # Reviewer cascade. Primary defaults to claude; override via
        # KUBEDOJO_388_PRIMARY_REVIEWER (claude | agy | qwen | deepseek).
        # Cascade order is always primary → claude → qwen/deepseek fallback
        # depending on the configured primary.
        primary = os.environ.get("KUBEDOJO_388_PRIMARY_REVIEWER", "claude").lower()
        cascade = build_reviewer_cascade(primary)

        review_text, verdict = (None, "ERROR")
        for tier_name, tier_fn in cascade:
            if review_text is not None and verdict not in ("ERROR", "UNCLEAR"):
                break
            if cascade.index((tier_name, tier_fn)) > 0:
                log({"event": f"review_fallback_to_{tier_name}", "pr": pr_num, "module": module_path})
            review_text, verdict = tier_fn(pr_num, module_path, slug)

        if review_text:
            post_review_comment(pr_num, review_text)
        if verdict == "APPROVE":
            sa = recheck_module_source_acceptance(Path(wt), module_path)
            log({
                "event": "source_acceptance_unverified",
                "pr": pr_num,
                "module": module_path,
                "verdict": verdict,
                "action": "merge_held",
                "source_acceptance": sa,
            })
            print(
                f"[source_acceptance_unverified] holding PR #{pr_num} for {module_path}; "
                "a real source-acceptance receipt gate is required before merge or backfill.",
                flush=True,
            )
        elif verdict == "APPROVE_WITH_NITS":
            # C3 fix-up lane: orchestrator triages inline (trivial nits) or
            # re-dispatches codex (semantic). Do NOT auto-merge — the
            # original collapse of APPROVE_WITH_NITS into APPROVE was the
            # bug that motivated this distinction (ab discuss day3-388 2026-05-02).
            log({
                "event": "merge_held_nits",
                "pr": pr_num,
                "module": module_path,
                "verdict": verdict,
                "review_excerpt": (review_text or "")[-1500:],
            })
        else:  # NEEDS CHANGES or UNCLEAR
            log({"event": "merge_held", "pr": pr_num, "module": module_path, "verdict": verdict})
        time.sleep(5)
    log({"event": "pilot_done"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
