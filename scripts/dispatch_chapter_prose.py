"""Dispatch the prose pipeline for an AI History chapter (#394).

Per the 2026-04-29 prose pipeline pivot (TEAM_WORKFLOW.md § 5):

    Approved contract → Gemini first draft (~3k) →
        Codex expansion to cap (DEFAULT)
        Claude expansion (FALLBACK when Codex bandwidth exhausted)
        → Claude source-fidelity review
        → Gemini or Claude prose-quality review
        → merge

Both expansion paths obey the same strict-source rule: use only the
provided contract and claim matrix; if evidence is missing for a
scene, leave the scene thin rather than filling it. Do not add
sources, do not introduce page anchors, do not upgrade Yellow claims,
do not invent examples, do not expand beyond the approved Prose
Capacity Plan.

The 2026-04-28 → 2026-04-29 difference: previously the expansion role
went to Claude opus by default; now it goes to Codex (gpt-5.5,
reasoning=high) because gpt-5.5 has wider weekly bandwidth and
Codex's source-discipline instinct is the strongest of the three
families. Claude opus stays in the loop as the source-fidelity
reviewer (independent fresh session), and as the expansion fallback.

Approach: do NOT depend on the research PR being merged. Read the
contract files from the research branch via `git show` and embed them
in the dispatch prompt. Prose worktree branches off main, prose PR
opens against main with only the prose file diff.

Usage:
    .venv/bin/python scripts/dispatch_chapter_prose.py 6 \
        --slug ch-06-the-cybernetics-movement \
        --research-branch claude/394-ch06-research \
        --cap-words 5000 \
        --verdict-notes-pr 467 \
        --phases agy,codex               # default Codex pipeline

    .venv/bin/python scripts/dispatch_chapter_prose.py 6 \
        --slug ch-06-the-cybernetics-movement \
        --research-branch claude/394-ch06-research \
        --cap-words 5000 \
        --verdict-notes-pr 467 \
        --phases agy,claude              # Claude-fallback pipeline

Phases default to "agy,codex" (agy is the Google draft lane). Use
"agy" alone to fire just the draft, "codex" or "claude" alone to
expand a pre-drafted file.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import yaml

REPO = Path("/Users/krisztiankoos/projects/kubedojo")

CONTRACT_FILES = ["brief.md", "sources.md", "scene-sketches.md",
                  "timeline.md", "people.md", "infrastructure-log.md",
                  "open-questions.md", "status.yaml"]


def read_branch_file(branch: str, path: str) -> str:
    subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=REPO, capture_output=True, check=False,
    )
    r = subprocess.run(
        ["git", "show", f"origin/{branch}:{path}"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    return r.stdout if r.returncode == 0 else ""


def stage_contract_locally(*, worktree: Path,
                           research_branch: str, slug: str,
                           verdicts: str) -> dict[str, str]:
    """Materialize the 8 contract files + verdicts inside the worktree
    so the headless agent can read them via its file-read tools instead
    of receiving the full text inline in the prompt.

    Returns ``{"brief.md": "<worktree>/.dispatch-context/brief.md", ...,
    "verdicts.md": "..."}``.

    Why: the inline approach blew the Gemini per-window input quota
    (Ch06 first-draft hit 429 even on the OAuth path). Pointing the
    agent at staged files drops the prompt from ~10–15 k tokens to
    ~1 k.

    Why inside the worktree (not /tmp): Gemini's workspace-write
    sandbox rejects ``/tmp`` paths with "Path not in workspace" when a
    retry fires. Ch07 hit this. Staging inside the worktree at
    ``.dispatch-context/`` keeps everything within the sandbox while
    the agent prompts explicitly forbid committing the directory.
    """
    base = worktree / ".dispatch-context"
    base.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for fn in CONTRACT_FILES:
        body = read_branch_file(
            research_branch,
            f"docs/research/ai-history/chapters/{slug}/{fn}",
        )
        if not body:
            continue
        target = base / fn
        target.write_text(body)
        paths[fn] = str(target)
    if verdicts:
        target = base / "verdicts.md"
        target.write_text(verdicts)
        paths["verdicts.md"] = str(target)
    return paths


def fetch_pr_verdicts(pr_num: int) -> str:
    """Pull the codex+gemini verdict comments from a PR so the drafter
    sees the cap rationale."""
    out = subprocess.run(
        ["gh", "pr", "view", str(pr_num), "--json", "comments",
         "--jq", '.comments[] | select(.body | startswith("<!-- verdict")) | .body'],
        cwd=REPO, capture_output=True, text=True, check=False,
    ).stdout
    return out or "(no verdict comments retrieved)"


STRICT_SOURCE_RULE = """\
**Strict source rule.** Use only the provided contract and claim
matrix. If evidence is missing for a scene, leave the scene thin
rather than filling it. Do NOT:

- add sources or citations not in `sources.md`
- introduce new page anchors, DOIs, or URLs
- upgrade Yellow claims to Green tone
- invent examples, dialogue, institutional motives, or causal links
- expand beyond the approved Prose Capacity Plan

If you can't anchor a claim, weaken the claim — never invent a source.

**No production-process diction in reader-facing prose.** The contract
is your *input*, not your *topic*. Do NOT use any of these words in
the prose: `the contract`, `Yellow`, `Red`, `Green` (as a status),
`unsafe` (as a claim-status verdict), `paginated anchor`, `paginated
source`, `anchor` (as a research-process noun, e.g. "a primary-page
anchor"), `extraction` (e.g. "operator-manual page extraction"),
`safe claim`, `deliberately cautious`, `the chapter cannot claim`.
Convert hedges into natural historical-prose diction:
- ❌ "the contract has it anchored to McCarthy's retrospective"
  ✅ "the strongest available source is McCarthy's retrospective"
- ❌ "the contract keeps that anecdote Yellow because it lacks a
  paginated anchor"
  ✅ "that anecdote rests on McCarthy's reminiscence rather than a
  paginated contemporary source"
- ❌ "the broader priority claim is unsafe"
  ✅ "the broader priority claim does not survive scrutiny"
- ❌ "the chapter cannot claim X. The evidence does not support that"
  ✅ "no direct causal link between the two is established in the
  primary record"
The reader should never see your research-process scaffolding.
Pattern confirmed cross-family on Ch12/13/14 fix-passes 2026-04-28;
this rule prevents the next batch from needing the same fix.
"""


def agy_draft_prompt(*, slug: str, ch_num: int, cap_words: int,
                     staged_paths: dict[str, str], prose_path: str) -> str:
    contract_listing = "\n".join(
        f"           - `{fn}` → `{p}`"
        for fn, p in staged_paths.items()
        if fn != "verdicts.md"
    )
    verdicts_path = staged_paths.get(
        "verdicts.md", "(no verdict notes for this chapter)"
    )
    return dedent(f"""\
        # Task: First-draft prose for Chapter {ch_num} (`{slug}`) (#394)

        You have **workspace-write** in this worktree. Replace the
        existing short stub at `{prose_path}` with a fresh first-draft
        prose based on the anchored research contract whose files are
        listed below.

        ## Pipeline position (post-2026-04-29 prose pivot)

        You are the **first-draft writer** in a four-step pipeline:

        ```
        1. Approved contract        ← staged on disk, paths listed below
        2. Gemini first draft       ← THIS STEP, target ~3,000 words
        3. Codex expansion to cap   ← downstream, will tighten + lengthen
        4. Cross-family review      ← downstream
        ```

        Don't try to hit the final {cap_words}-word cap. Write a tight,
        evidence-backed ~3,000-word first draft that captures every
        scene from the contract; Codex will expand the technical and
        biographical layers from the same contract.

        ## Your whitelist (where you add value)

        - narrative flow and pacing
        - scene ordering
        - making dry source material readable
        - spotting where the chapter feels thin

        ## Your blacklist (the Issue #421 hallucination filter)

        {STRICT_SOURCE_RULE}

        ## Other hard rules

        1. **Cap: {cap_words} words HARD CEILING** for the final
           chapter. Your first draft should land at ~3,000 words —
           well under.
        2. **Use the Boundary Contract.** The brief defines what the
           chapter is NOT. Don't anticipate later chapters.
        3. **Yellow claims hedge; Red claims stay out.** Yellow needs
           hedge phrasing ("according to Hailperin", "is sometimes
           argued"). Red claims do not appear except as flagged open
           questions.
        4. **Frontmatter required.** First lines:
           ```
           ---
           title: "Chapter {ch_num}: <Title from brief>"
           description: "<one-sentence chapter hook>"
           sidebar:
             order: {ch_num}
           ---
           ```
        5. **No emoji.** No bullet-list "list of facts" sections —
           narrative prose only.

        ## Verdicts (with caveats — respect them)

        Read the verdict comments at: `{verdicts_path}`

        ## Research contract — read these files BEFORE you start drafting

        The 8 contract files are staged inside this worktree under
        `.dispatch-context/` by the orchestrator. Read each one with
        your file-read tool (don't skim — these are your only source
        of truth):

{contract_listing}

        These are absolute paths inside the worktree. Do NOT include
        `.dispatch-context/` in any `git add` — only commit
        `{prose_path}`.

        ## Workflow

        1. Read every staged contract file listed above plus the
           verdict notes. Internalize the brief's Prose Capacity Plan.
        2. Replace `{prose_path}` with your draft. Use the title
           from `brief.md`'s thesis. Use scene structure from
           `scene-sketches.md`.
        3. Self-check: word count ~3,000, every Green claim has a
           `sources.md`-traceable phrasing, Yellow claims hedged,
           Red claims absent, no fabricated anchors.
        4. `git add {prose_path}` and commit:
           ```
           docs(ch-{ch_num:02d}): draft prose against anchored contract (#394)
           ```
        5. Print word count and any claims you couldn't anchor.

        Do NOT push. Do NOT commit anything other than `{prose_path}`.
        The orchestrator handles PR creation after the expansion phase.
        """)


def _expansion_prompt(*, agent_label: str, slug: str, ch_num: int,
                      cap_words: int, staged_paths: dict[str, str],
                      prose_path: str) -> str:
    """Build the expansion prompt. Identical for Codex and Claude —
    same strict-source rule, same Prose Capacity Plan discipline.

    The contract files are staged on disk at the paths in
    ``staged_paths`` so we don't re-embed ~10 k tokens of contract text
    per call. The agent reads them via its file-read tool.
    """
    contract_listing = "\n".join(
        f"           - `{fn}` → `{p}`"
        for fn, p in staged_paths.items()
        if fn != "verdicts.md"
    )
    verdicts_path = staged_paths.get(
        "verdicts.md", "(no verdict notes for this chapter)"
    )
    return dedent(f"""\
        # Task: Expand and tighten Chapter {ch_num} prose (`{slug}`) (#394)

        You ({agent_label}) have **workspace-write** in this worktree.
        Gemini drafted prose at `{prose_path}` against the anchored
        research contract. Your job is to expand the draft from ~3k to
        {cap_words} words while sharpening anchor discipline and
        tightening narrative coherence.

        ## Pipeline position (post-2026-04-29 prose pivot)

        You are the **expansion writer** in a four-step pipeline:

        ```
        1. Approved contract        ← staged on disk, paths below
        2. Gemini first draft       ← already on disk at {prose_path}
        3. Expansion to cap         ← THIS STEP — you ({agent_label})
        4. Cross-family review      ← downstream (Claude source-fidelity, Gemini/Claude prose-quality)
        ```

        ## What "expand" means here (it's NOT padding)

        Per the contract's Prose Capacity Plan, each layer of the plan
        cites specific page anchors in `sources.md`. Gemini's draft
        likely covers the structural skeleton but under-uses the
        technical and biographical layers. Your expansion budget should
        go to:

        - **Technical density**: equations, system mechanics, what
          actually happened in the science, anchored to `sources.md`.
        - **Infrastructure detail**: from `infrastructure-log.md`.
        - **Anchored biographical scenes**: tight scenes citing
          specific page numbers from biographies/oral histories.
        - **Conflict notes**: where the historical record disagrees,
          show the disagreement instead of papering over it.

        DO NOT pad with:
        - Generic textbook explanation
        - Repeated summary
        - Modern hindsight
        - Unanchored deployment scale or business impact

        ## Strict source rule (the load-bearing rule)

        {STRICT_SOURCE_RULE}

        Concretely, **if a layer of the Prose Capacity Plan can't be
        expanded from the contract's existing anchors, leave it thin.**
        Cap-padding by inventing scenes is a worse failure than landing
        below cap.

        ## Other hard rules

        1. **Cap: {cap_words} words. Hard cap, not target.** If the
           verified evidence runs out, cap below.
        2. **Yellow → hedge; Red → out.** Same as the drafter's rules.
        3. **Preserve Gemini's good prose.** This is expansion, not
           rewrite. Surgical paragraph additions and targeted edits,
           not wholesale replacement. If a Gemini paragraph is good,
           leave it.
        4. **No emoji. No bullet-list facts.** Narrative prose only.

        ## Verdict caveats

        Read the verdict comments at: `{verdicts_path}`

        ## Research contract — read these files BEFORE editing

        Staged inside this worktree under `.dispatch-context/` by the
        orchestrator. Read each one with your file-read tool:

{contract_listing}

        Do NOT include `.dispatch-context/` in any `git add` — only
        commit `{prose_path}`.

        ## Workflow

        1. Read `{prose_path}` (Gemini's draft) and the staged contract
           files listed above.
        2. Identify under-developed Plan layers. Add anchored content
           targeted at those layers. Tighten any unanchored claims
           Gemini left in.
        3. Run `wc -w {prose_path}` after each substantial edit to
           stay under the cap.
        4. `git add {prose_path}` and commit:
           ```
           docs(ch-{ch_num:02d}): expand prose to verdict cap with anchored layers (#394)
           ```
        5. Print final word count and the layers you expanded. Note
           any layer you left thin because evidence ran out.
        """)


def codex_prompt(*, slug: str, ch_num: int, cap_words: int,
                 staged_paths: dict[str, str], prose_path: str) -> str:
    return _expansion_prompt(
        agent_label="Codex (gpt-5.5, default expander)",
        slug=slug, ch_num=ch_num, cap_words=cap_words,
        staged_paths=staged_paths, prose_path=prose_path,
    )


def claude_prompt(*, slug: str, ch_num: int, cap_words: int,
                  staged_paths: dict[str, str], prose_path: str) -> str:
    return _expansion_prompt(
        agent_label="Claude opus-4-7 (fallback expander when Codex bandwidth exhausted)",
        slug=slug, ch_num=ch_num, cap_words=cap_words,
        staged_paths=staged_paths, prose_path=prose_path,
    )


def setup_worktree(*, ch_num: int, slug: str) -> tuple[Path, str]:
    """Create or reuse `.worktrees/prose-394-chNN`."""
    branch = f"prose/394-ch{ch_num:02d}"
    worktree = REPO / f".worktrees/prose-394-ch{ch_num:02d}"
    if worktree.exists():
        print(f"[setup] worktree already exists: {worktree} — reusing")
        return worktree, branch
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(worktree), "main"],
        cwd=REPO, check=True,
    )
    return worktree, branch


def _prose_committed_on_branch(worktree: Path, prose_path: str) -> bool:
    """True if the worktree's branch has at least one commit ahead of
    main that touches ``prose_path``. Used to recover from agents that
    finish their file-write + commit work but then fail their final
    streaming response (Gemini's 429-on-summary pattern, observed on
    Ch07 2026-04-28). The work landed; the runner just couldn't tell."""
    r = subprocess.run(
        ["git", "log", "--oneline", "main..HEAD", "--", prose_path],
        cwd=worktree, capture_output=True, text=True, check=False,
    )
    return bool(r.stdout.strip())


def fire_phase(*, agent: str, prompt: str, worktree: Path, task_id: str,
               log_path: Path, prose_path: str) -> bool:
    sys.path.insert(0, str(REPO / "scripts"))
    from agent_runtime.errors import AgentTimeoutError, RateLimitedError
    from agent_runtime.runner import invoke

    if agent == "agy":
        # agy pro draft lane (replaced the retired gemini-cli, #2125/#2230).
        # Must be a valid agy model slug, NOT a gemini-cli model id. Override via
        # KUBEDOJO_AGY_DRAFT_MODEL. The legacy KUBEDOJO_GEMINI_DRAFT_MODEL is
        # intentionally NOT honored — it would inject a retired gemini-cli slug.
        # Sister var KUBEDOJO_AGY_REVIEW_MODEL in dispatch_prose_review.py.
        import os
        model = os.environ.get("KUBEDOJO_AGY_DRAFT_MODEL", "gemini-3.1-pro-high")
        timeout = 2400
        mode = "workspace-write"
    elif agent == "codex":
        # gpt-5.5 + model_reasoning_effort=high pinned in
        # ~/.codex/config.toml. Codex needs `danger` mode (not
        # workspace-write) so it can self-commit on the worktree
        # branch — workspace-write blocks
        # `.git/worktrees/<name>/index.lock` as documented in
        # `feedback_codex_workspace_write_default.md` and observed
        # again 2026-04-29 on the Ch03 fix-applier dispatch.
        model = "gpt-5.5"
        timeout = 3600
        mode = "danger"
    elif agent == "claude":
        model = "claude-opus-4-8"
        timeout = 3600
        mode = "workspace-write"
    else:
        raise ValueError(agent)

    print(f"[fire] {agent} ({model}, mode={mode}) on {task_id}")
    try:
        r = invoke(
            agent, prompt,
            mode=mode,
            cwd=worktree,
            model=model,
            task_id=task_id,
            entrypoint="delegate",
            hard_timeout=timeout,
        )
        ok = r.ok
        response = r.response or ""
        session_id = r.session_id
        stderr_excerpt = r.stderr_excerpt or ""
    except (RateLimitedError, AgentTimeoutError) as exc:
        # The runner raised before returning, but the agent may have
        # finished its file-write + commit work and only choked on the
        # final streaming response. Probe the worktree.
        ok = False
        response = ""
        session_id = None
        stderr_excerpt = f"{type(exc).__name__}: {exc}"
        if _prose_committed_on_branch(worktree, prose_path):
            print(f"[fire] {agent} runner classified failure but commit "
                  f"on {prose_path} is present — treating as success")
            ok = True

    log_path.write_text("\n".join([
        f"OK: {ok}",
        f"session_id: {session_id}",
        f"response chars: {len(response)}",
        "=" * 70,
        response or "(no response)",
        "=" * 70,
        f"stderr_excerpt: {stderr_excerpt or '(none)'}",
    ]))
    print(f"[fire] {agent} OK={ok}, log -> {log_path}")
    return ok


def _prose_within_cap(path: Path, cap: int) -> bool:
    """Count whitespace tokens in Markdown after leading YAML frontmatter.

    Headings, markup, code and references in the remaining body count; this
    conservative upper-bound check is not a narrative-only quality measure.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        print(f"[cap] {path}: unreadable ({type(exc).__name__}); count=unknown, cap={cap}", file=sys.stderr)
        return False
    if lines and lines[0].rstrip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
        if end is None:
            print(f"[cap] {path}: unterminated frontmatter; count=unknown, cap={cap}", file=sys.stderr)
            return False
        try:
            if not isinstance(yaml.safe_load("".join(lines[1:end])), dict):
                raise TypeError("frontmatter must be a mapping")
        except (yaml.YAMLError, TypeError):
            print(f"[cap] {path}: invalid frontmatter; count=unknown, cap={cap}", file=sys.stderr)
            return False
        lines = lines[end + 1:]
    body = "".join(lines)
    count = len(body.split())
    empty = not any(char.isalnum() for char in body)
    if empty or count > cap:
        print(f"[cap] {path}: {'empty body' if empty else 'over cap'}; count={count}, cap={cap}", file=sys.stderr)
        return False
    print(f"[cap] {path}: count={count}, cap={cap} (upper bound only)")
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ch_num", type=int)
    p.add_argument("--slug", required=True)
    p.add_argument("--research-branch", required=True)
    p.add_argument("--cap-words", type=int, required=True,
                   help="maximum whitespace tokens in the Markdown body, including markup and references")
    p.add_argument("--verdict-notes-pr", type=int, default=None,
                   help="PR number to fetch codex+gemini verdict notes from")
    p.add_argument("--phases", default="agy,codex",
                   help="comma-separated: agy,codex (default; agy is the Google draft lane) "
                        "or agy,claude (Claude-fallback) or any single phase")
    args = p.parse_args()
    if args.cap_words <= 0:
        p.error("--cap-words must be positive")
    phases = [s.strip() for s in args.phases.split(",") if s.strip()]
    if not phases:
        p.error("--phases must name at least one phase")

    verdicts = ""
    if args.verdict_notes_pr is not None:
        verdicts = fetch_pr_verdicts(args.verdict_notes_pr)

    worktree, branch = setup_worktree(ch_num=args.ch_num, slug=args.slug)
    prose_path = f"src/content/docs/ai-history/{args.slug}.md"

    # Stage contract + verdicts inside the worktree so every agent
    # reads via its file-read tool instead of receiving ~10 k tokens of
    # contract text inline. Inside the worktree (not /tmp) so Gemini's
    # workspace-write sandbox accepts the paths even on retry.
    staged_paths = stage_contract_locally(
        worktree=worktree,
        research_branch=args.research_branch,
        slug=args.slug, verdicts=verdicts,
    )
    if not any(fn != "verdicts.md" for fn in staged_paths):
        print(f"[err] no contract files found on branch {args.research_branch}",
              file=sys.stderr)
        return 1
    print(f"[stage] {len(staged_paths)} contract files at "
          f"{worktree}/.dispatch-context/")

    for phase in phases:
        if phase == "agy":
            prompt = agy_draft_prompt(
                slug=args.slug, ch_num=args.ch_num,
                cap_words=args.cap_words, staged_paths=staged_paths,
                prose_path=prose_path,
            )
            log = Path(f"/tmp/prose-ch{args.ch_num:02d}-agy.log")
            ok = fire_phase(
                agent="agy", prompt=prompt, worktree=worktree,
                task_id=f"prose-{args.slug}-agy", log_path=log,
                prose_path=prose_path,
            )
            if not ok:
                print("[main] agy phase FAILED, stopping pipeline")
                return 2
        elif phase == "codex":
            prompt = codex_prompt(
                slug=args.slug, ch_num=args.ch_num,
                cap_words=args.cap_words, staged_paths=staged_paths,
                prose_path=prose_path,
            )
            log = Path(f"/tmp/prose-ch{args.ch_num:02d}-codex.log")
            ok = fire_phase(
                agent="codex", prompt=prompt, worktree=worktree,
                task_id=f"prose-{args.slug}-codex", log_path=log,
                prose_path=prose_path,
            )
            if not ok:
                print("[main] Codex expansion FAILED")
                return 3
        elif phase == "claude":
            prompt = claude_prompt(
                slug=args.slug, ch_num=args.ch_num,
                cap_words=args.cap_words, staged_paths=staged_paths,
                prose_path=prose_path,
            )
            log = Path(f"/tmp/prose-ch{args.ch_num:02d}-claude.log")
            ok = fire_phase(
                agent="claude", prompt=prompt, worktree=worktree,
                task_id=f"prose-{args.slug}-claude", log_path=log,
                prose_path=prose_path,
            )
            if not ok:
                print("[main] Claude expansion FAILED")
                return 4
        else:
            print(f"[err] unknown phase: {phase}", file=sys.stderr)
            return 1

        if not _prose_within_cap(worktree / prose_path, args.cap_words):
            print(f"[main] {phase} output failed cap validation; preserved for correction", file=sys.stderr)
            return 5

    print(f"[done] worktree={worktree} branch={branch}")
    print(f"[next] cd {worktree} && git push -u origin {branch} "
          f"&& gh pr create --title 'Prose: Chapter {args.ch_num} ({args.slug}) (#394)' --body ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
