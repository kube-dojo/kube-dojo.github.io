"""Dispatch a fresh headless agent on per-chapter AI History research.

Originally the Claude-only dispatcher for the Parts 1/2/6/7 re-research
queue (Issue #394). Generalized 2026-04-28 evening so Parts 6/7 can flip
to Codex when Claude's weekly credit pool is throttled. Each call spins
up a fresh `<agent>/394-ch{N}-research` worktree off main, drops a
focused prompt that points the headless agent at the chapter slug
directory, and fires `lu_machinery.agent_runtime.runner.invoke` in danger
mode with the agent's right model + reasoning settings.

Usage:
    # Claude (default — Parts 1, 2, 3, 9 per the 2026-04-28 split)
    .venv/bin/python scripts/dispatch_chapter_research.py 1 \
        --slug ch-01-the-laws-of-thought \
        --supersede-pr 425

    # Codex (Parts 4, 5, 6, 7, 8 — 6/7 flipped 2026-04-28 evening
    # to spare Claude's weekly cap)
    .venv/bin/python scripts/dispatch_chapter_research.py 38 \
        --slug ch-38-the-eliza-illusion \
        --agent codex

The script prints the worktree path, branch, dispatch log path, and
runs the dispatch in the foreground (blocking). Caller decides whether
to background the whole script.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

_CHECKOUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_CHECKOUT / "scripts"))

from quality.writer_commit import produced, select_product_root, snapshot

# The primary checkout: dispatch worktrees live under <primary>/.worktrees/.
REPO = (
    Path(*_CHECKOUT.parts[: _CHECKOUT.parts.index(".worktrees")])
    if ".worktrees" in _CHECKOUT.parts
    else _CHECKOUT
)


AGENT_DEFAULTS: dict[str, dict[str, object]] = {
    "claude": {
        "model": "claude-opus-5-5",
        "owner_label": "Claude",
        # Keep claude-opus pegged at 60 min; mirrors prior behavior.
        "hard_timeout": 3600,
    },
    "codex": {
        # None takes the lu-machinery release's default Codex model, so a
        # catalog retirement never strands this dispatcher on a dead pin.
        "model": None,
        "owner_label": "Codex",
        "hard_timeout": 3600,
    },
}


def make_prompt(*, ch_num: int, slug: str, supersede_pr: int | None,
                staging_files: list[Path], part_num: int,
                agent: str) -> str:
    """Build the per-chapter dispatch prompt."""
    owner_label = str(AGENT_DEFAULTS[agent]["owner_label"])
    staging_section = ""
    if staging_files:
        rel = "\n".join(f"- `{f.name}`" for f in staging_files)
        staging_section = dedent(f"""

        ## Pre-staged scratch files (in worktree root)

        The orchestrator copied prior-session research artifacts into
        the worktree root. Read these BEFORE re-fetching anything —
        they may already contain extracted source text or partial
        anchor work. Delete them before commit; they are scratch, not
        artifacts.

        {rel}
        """)

    supersede_section = ""
    if supersede_pr is not None:
        supersede_section = dedent(f"""

        ## Superseding Gemini's prior PR

        Gemini opened PR #{supersede_pr} for this chapter before the
        2026-04-28 role split (when research duties were taken away
        from him after URL/anchor hallucination self-admission, epic
        commit `03640e20`, Issue #421). Do NOT merge or rebase that
        PR. Treat it as a reference — read it for what scenes Gemini
        outlined, but verify every page anchor independently. Many of
        Gemini's anchors are fabricated. The orchestrator will close
        #{supersede_pr} once your replacement PR lands.
        """)

    return dedent(f"""\
        # Task: Build the Chapter {ch_num} research contract for the AI History book (#394)

        You have **workspace-write** access to worktree
        `{REPO}/.worktrees/{agent}-394-ch{ch_num:02d}-research` on
        branch `{agent}/394-ch{ch_num:02d}-research` (forked off
        `main`). Edit and commit there. Do NOT touch the main
        checkout.

        ## Chapter {ch_num} — `{slug}`

        Per the research role split (effective 2026-04-28; Parts 6/7
        flipped from Claude to Codex on the evening of 2026-04-28 to
        spare Claude's weekly credit pool), {owner_label} owns Part
        {part_num} research. Build the 8-file chapter contract from
        verified primary and secondary sources.

        ## Required reading — in this exact order

        1. `docs/research/ai-history/TEAM_WORKFLOW.md` — the chapter
           lifecycle and contract structure. Pay attention to the
           **Prose Capacity Plan gate**: every layer must reference
           at least one anchored entry in `sources.md`.
        2. `docs/research/ai-history/chapters/ch-11-the-summer-ai-named-itself/brief.md`
           and `sources.md` — the gold-standard template for a
           Claude-owned anchored brief and the Green/Yellow/Red claim
           table format.
        3. `docs/research/ai-history/chapters/{slug}/` — current state
           (probably mostly empty stubs from the legacy Gemini work).
        4. `src/content/docs/ai-history/ch-{ch_num:02d}-*.md` (if it
           exists) — the legacy Gemini-drafted prose. **Do NOT trust
           its sources.** Read it only to understand what scenes are
           in scope; verify every claim independently.
        {staging_section}{supersede_section}

        ## Your output — eight files in `docs/research/ai-history/chapters/{slug}/`

        1. `brief.md` — Thesis, Scope, Boundary Contract, Scenes
           Outline (5 scenes typical), **anchored Prose Capacity
           Plan** (each layer cites specific page anchors from
           sources.md), Citation Bar, Conflict Notes, Honest
           Prose-Capacity Estimate.
        2. `sources.md` — Green/Yellow/Red claim table. Every Green
           claim has a verified anchor (page, section, or DOI+page).
           Yellow = source anchored but specific claim isn't
           page-located. Red = no verifiable anchor yet.
        3. `timeline.md` — chronology with key dated events.
        4. `people.md` — actors with verified facts.
        5. `infrastructure-log.md` — computing infrastructure each
           scene relied on.
        6. `scene-sketches.md` — 5 scenes mapped 1:1 to Prose
           Capacity Plan layers. Match Ch11's prose density.
        7. `open-questions.md` — what's still Yellow/Red, what
           archival access would help.
        8. `status.yaml` — set `status: capacity_plan_anchored` ONLY
           if every Prose Capacity Plan layer references a real
           sources.md page anchor; otherwise
           `capacity_plan_drafted`. Include green/yellow/red counts.

        ## Hard rules — non-negotiable

        - **NEVER fabricate URLs, page numbers, DOIs, or quotes.**
          This is the rule that took research duties off Gemini. If
          you can't anchor a claim, mark it Yellow or Red, never
          Green.
        - **Use the shell directly.** `curl`, `pdftotext`, `pdfgrep`,
          `ocrmypdf` are all available. For paywalled PDFs (JSTOR,
          Project Euclid behind Imperva), don't fight the paywall —
          fall back to open mirrors (arXiv historical mirrors,
          Project Gutenberg, Internet Archive, university repos like
          Stanford ISL, MIT DSpace, etc.) or accept Yellow on
          specific page anchors and Green on citation+intro.
        - **Boundary contract:** make it explicit. Say what the
          chapter is NOT. Forward-references are sparse pointers
          ("see Ch{ch_num + 1}"); don't anticipate later chapters'
          arguments.
        - **Honesty close in `brief.md`:** end the Prose Capacity
          Plan with "If the verified evidence runs out, cap the
          chapter."

        ## Workflow

        1. `cd {REPO}/.worktrees/{agent}-394-ch{ch_num:02d}-research`
        2. Read TEAM_WORKFLOW, the Ch11 templates, the existing
           legacy chapter dir and prose if any, the staged files if
           any.
        3. Identify primary sources for the chapter's scope. Fetch
           and extract anchors. For each Green claim, the row must
           cite a specific page or section.
        4. Build the 8 files.
        5. Self-check: count Green/Yellow/Red; verify every plan
           layer has at least one anchored citation; verify total
           range matches a Word Count Discipline label.
        6. Delete any scratch staging files in worktree root before
           commit.
        7. `git add docs/research/ai-history/chapters/{slug}/` and
           commit:
           ```
           docs(ai-history): build chapter {ch_num} research contract (#394)

           Anchored research contract for `{slug}` per the research
           role split ({owner_label} owns Part {part_num} research,
           effective 2026-04-28). All Green claims trace to verified
           primary or secondary anchors.

           Status: capacity_plan_anchored | capacity_plan_drafted.
           N Green / N Yellow / N Red claims.
           ```
        8. Do NOT push. The orchestrator will open the PR and run
           the cross-family verdict pass.

        ## When done — print summary

        Print at the end (≤300 words):
        - Thesis (one paragraph).
        - Total Green/Yellow/Red.
        - Per-layer Prose Capacity Plan word ranges and total.
        - Word Count Discipline label.
        - Claims you wanted Green but couldn't anchor (with reason).
        - Commit SHA.
        """)


def detect_part(ch_num: int) -> int:
    """Map chapter number to Part number per
    docs/research/ai-history/README.md ownership table."""
    if 1 <= ch_num <= 5:
        return 1
    if 6 <= ch_num <= 10:
        return 2
    if 11 <= ch_num <= 16:
        return 3
    if 17 <= ch_num <= 23:
        return 4
    if 24 <= ch_num <= 31:
        return 5
    if 32 <= ch_num <= 40:
        return 6
    if 41 <= ch_num <= 49:
        return 7
    if 50 <= ch_num <= 58:
        return 8
    if 59 <= ch_num <= 68:
        return 9
    raise ValueError(f"Chapter {ch_num} out of range 1-68")


def setup_worktree(ch_num: int, agent: str) -> tuple[Path, str]:
    """Create the .worktrees/{agent}-394-chNN-research worktree."""
    branch = f"{agent}/394-ch{ch_num:02d}-research"
    worktree = REPO / f".worktrees/{agent}-394-ch{ch_num:02d}-research"
    if worktree.exists():
        print(f"[setup] worktree already exists at {worktree} — reusing")
        return worktree, branch
    cmd = ["git", "worktree", "add", "-b", branch, str(worktree), "main"]
    subprocess.run(cmd, cwd=REPO, check=True)
    return worktree, branch


def stage_files(worktree: Path, files: list[Path]) -> list[Path]:
    """Copy staging files into the worktree root."""
    staged = []
    for src in files:
        if not src.exists():
            print(f"[stage] WARNING: {src} does not exist, skipping")
            continue
        dst = worktree / src.name
        shutil.copy2(src, dst)
        staged.append(dst)
        print(f"[stage] {src.name} -> {dst}")
    return staged


def fire_dispatch(*, worktree: Path, prompt: str, task_id: str,
                  log_path: Path, agent: str, artifact_dir: str, branch: str) -> int:
    """Run the dispatch in the current process, tee output to log."""
    from lu_machinery.agent_runtime.runner import invoke

    cfg = AGENT_DEFAULTS[agent]
    model = cfg["model"]
    timeout = int(cfg["hard_timeout"])  # type: ignore[arg-type]
    print(f"[dispatch] firing {agent} ({model}) on {task_id} ...")
    before = snapshot(worktree, f"refs/heads/{branch}")
    result = invoke(
        agent,
        prompt,
        mode="danger",
        cwd=worktree,
        model=model,
        task_id=task_id,
        entrypoint="delegate",
        hard_timeout=timeout,
    )

    log_path.write_text("\n".join([
        "=" * 70,
        f"OK: {result.ok}",
        f"session_id: {result.session_id}",
        f"response chars: {len(result.response or '')}",
        "=" * 70,
        result.response or "(no response)",
        "=" * 70,
        f"stderr_excerpt: {result.stderr_excerpt or '(none)'}",
    ]))
    print(f"[dispatch] OK={result.ok}, log -> {log_path}")
    if not result.ok:
        return 1
    # The release runner returns a parsed success without checking that a
    # write-mode run produced anything. The prompt's deliverable is a local
    # commit of the chapter's contract directory on the worktree branch; the
    # shared rule decides whether the branch tip holds new work there.
    _final, reason = produced(worktree, before, artifact_dir, f"refs/heads/{branch}", kind="dir")
    if reason is not None:
        print(f"[dispatch] {agent} reported success but {branch} holds no new "
              f"committed work under {artifact_dir} ({reason}); treating as failure")
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ch_num", type=int, help="Chapter number 1-68")
    p.add_argument("--slug", required=True,
                   help="Chapter slug, e.g. ch-01-the-laws-of-thought")
    p.add_argument("--agent", choices=sorted(AGENT_DEFAULTS),
                   default="claude",
                   help="Which research agent to dispatch. Parts 6/7 "
                        "flipped to codex 2026-04-28 evening.")
    p.add_argument("--supersede-pr", type=int, default=None,
                   help="Open Gemini PR number to supersede (#425, #426, ...)")
    p.add_argument("--stage", action="append", default=[],
                   help="Path to a scratch file to stage in the worktree "
                        "root. Repeatable.")
    args = p.parse_args()

    try:
        select_product_root(REPO)
    except ValueError as exc:
        p.error(str(exc))

    part_num = detect_part(args.ch_num)
    print(f"[main] Ch{args.ch_num:02d} `{args.slug}` "
          f"(Part {part_num}, agent={args.agent})")

    worktree, branch = setup_worktree(args.ch_num, args.agent)
    staging_files = stage_files(
        worktree,
        [Path(s) if Path(s).is_absolute() else (REPO / s) for s in args.stage],
    )

    prompt = make_prompt(
        ch_num=args.ch_num,
        slug=args.slug,
        supersede_pr=args.supersede_pr,
        staging_files=staging_files,
        part_num=part_num,
        agent=args.agent,
    )

    log_path = Path(
        f"/tmp/dispatch-out-{args.agent}-ch{args.ch_num:02d}-research.log"
    )
    return fire_dispatch(
        worktree=worktree,
        prompt=prompt,
        task_id=f"ch{args.ch_num:02d}-research-{args.agent}-2026-04-28",
        log_path=log_path,
        agent=args.agent,
        artifact_dir=f"docs/research/ai-history/chapters/{args.slug}/",
        branch=branch,
    )


if __name__ == "__main__":
    raise SystemExit(main())
