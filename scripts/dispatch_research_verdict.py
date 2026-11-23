"""Dispatch cross-family verdict pass on AI History chapter-research PRs (#394).

For each PR:
1. Read brief.md, sources.md, open-questions.md, scene-sketches.md from
   the PR branch (`git show <branch>:<path>`).
2. Fire the cross-family **anchor verifier** (route on PR branch prefix):
   - `claude/394-chNN-research` -> Codex (release default model)
   - `codex/394-chNN-research`  -> Claude (claude-opus-5-5)
   Both have shell access and can curl/pdftotext/grep page anchors.
3. Fire an agy (Google lane) structural gap-audit on both (lane-disciplined
   per feedback_gemini_hallucinates_anchors.md — NO URL citations from the
   Google lane; structural gaps only). agy replaced the retired gemini-cli
   (#2125/#2230).
4. Post both reviews as PR comments.

Codex/Claude and the agy (Google) lane run on different families, so an
anchor queue and a structural-gap queue can run in parallel. Within a
family, dispatches are sequential per feedback_codex_dispatch_sequential.md
and reference_gemini_collab.md.

Usage:
    .venv/bin/python scripts/dispatch_research_verdict.py 456 459 460 ...
    .venv/bin/python scripts/dispatch_research_verdict.py --only codex 456
    .venv/bin/python scripts/dispatch_research_verdict.py --only claude 456
    .venv/bin/python scripts/dispatch_research_verdict.py --only agy 456

Posts comments via `gh pr comment <pr> --body-file ...`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path
from textwrap import dedent

_CHECKOUT = Path(__file__).resolve().parents[1]
# The primary checkout: dispatch worktrees live under <primary>/.worktrees/.
REPO = (
    Path(*_CHECKOUT.parts[: _CHECKOUT.parts.index(".worktrees")])
    if ".worktrees" in _CHECKOUT.parts
    else _CHECKOUT
)
sys.path.insert(0, str(REPO / "scripts"))


CONTRACT_FILES = ["brief.md", "sources.md", "open-questions.md",
                  "scene-sketches.md", "timeline.md", "people.md",
                  "infrastructure-log.md", "status.yaml"]


def slug_from_branch(branch: str) -> str:
    """`claude/394-ch01-research` → `ch-01-the-laws-of-thought`. We can't
    derive the slug from the branch alone — fetch the file paths from
    the PR diff and pull the slug out."""
    out = subprocess.run(
        ["gh", "pr", "view", _pr_for_branch(branch), "--json",
         "files", "--jq", ".files[0].path"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    # path is docs/research/ai-history/chapters/ch-NN-slug/file.md
    parts = out.split("/")
    if len(parts) < 5 or parts[3] != "chapters":
        raise ValueError(f"unexpected path {out!r} on branch {branch!r}")
    return parts[4]


def _pr_for_branch(branch: str) -> str:
    out = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--json", "number",
         "--jq", ".[0].number"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        raise ValueError(f"no PR for branch {branch!r}")
    return out


def fetch_pr_meta(pr_num: int) -> dict:
    out = subprocess.run(
        ["gh", "pr", "view", str(pr_num), "--json",
         "headRefName,title,number"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def read_branch_file(branch: str, path: str) -> str:
    subprocess.run(["git", "fetch", "origin", branch], cwd=REPO,
                   capture_output=True, check=False)
    r = subprocess.run(
        ["git", "show", f"origin/{branch}:{path}"],
        cwd=REPO, capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else ""


def gather_contract(branch: str, slug: str) -> str:
    """Concatenate every contract file with a header so the reviewer sees
    the whole thing."""
    chunks = []
    for fn in CONTRACT_FILES:
        body = read_branch_file(
            branch, f"docs/research/ai-history/chapters/{slug}/{fn}",
        )
        if not body:
            chunks.append(f"### {fn}\n\n_(empty or absent)_\n")
            continue
        chunks.append(f"### {fn}\n\n```\n{body}\n```\n")
    return "\n".join(chunks)


def codex_prompt(*, slug: str, contract: str) -> str:
    return dedent(f"""\
        # Verdict Pass — Codex Anchor Verification (`{slug}`)

        You are the cross-family Codex reviewer for an AI History
        chapter research contract. Your lane is **anchor verification**:
        confirm that primary-source URLs, page numbers, DOIs, and quoted
        passages actually exist and say what the contract claims.

        ## Background

        Chapter contracts are the gating artifact between research and
        prose. Per `docs/research/ai-history/TEAM_WORKFLOW.md`, drafting
        does not unlock until the contract gets `READY_TO_DRAFT` or
        `READY_TO_DRAFT_WITH_CAP` from a cross-family reviewer.

        Gemini was removed from research duties in April 2026 after URL
        and page-anchor hallucinations (Issue #421, commit 03640e20).
        That makes anchor verification YOUR specialty — you have shell
        access (curl, pdftotext, pdfgrep, ocrmypdf) and can hit primary
        sources directly.

        ## Your job

        Review the contract below. For up to **8 of the most
        load-bearing Green claims** in `sources.md`, attempt to verify:
        - the URL or DOI resolves
        - the cited page or section actually contains the quoted text
          or the claim it's said to support
        - the bibliographic identifier matches the work cited

        For each claim you check, classify the result:
        - `ANCHOR_VERIFIED` — fetched and confirmed
        - `ANCHOR_PARTIAL` — source resolves but page/quote does not match
        - `ANCHOR_BROKEN` — URL is dead, paywalled, or the quote is wrong
        - `UNREACHABLE` — paywall / auth / region blocked you

        Don't try to verify all claims; pick the highest-leverage ones.
        Skip claims already marked Yellow or Red.

        ## Output (Markdown, ≤700 words)

        ```
        ## Codex Anchor Verification — `{slug}`

        Claims sampled: N

        | Claim (short) | sources.md row | Status | Notes |
        |---|---|:-:|---|
        | ... | ... | ANCHOR_VERIFIED | page 47 confirms |
        ...

        ### Cross-cutting issues
        - <e.g. JSTOR paywalls block 4/8 anchors; suggest open mirrors>
        - <e.g. one DOI mismatched the cited author>

        ### Verdict
        - READY_TO_DRAFT | READY_TO_DRAFT_WITH_CAP | NEEDS_ANCHORS | NEEDS_RESEARCH | SCOPE_DOWN
        - One sentence rationale.
        ```

        ## Contract

        {contract}
        """)


def claude_anchor_prompt(*, slug: str, contract: str) -> str:
    return dedent(f"""\
        # Verdict Pass — Claude Anchor Verification (`{slug}`)

        You are the cross-family Claude reviewer for an AI History
        chapter research contract. Your lane is **anchor verification**:
        confirm that primary-source URLs, page numbers, DOIs, and quoted
        passages actually exist and say what the contract claims.

        ## Background

        Chapter contracts are the gating artifact between research and
        prose. Per `docs/research/ai-history/TEAM_WORKFLOW.md`, drafting
        does not unlock until the contract gets `READY_TO_DRAFT` or
        `READY_TO_DRAFT_WITH_CAP` from a cross-family reviewer.

        Gemini was removed from research duties in April 2026 after URL
        and page-anchor hallucinations (Issue #421, commit 03640e20).
        Codex authored the contract you are reviewing, so the
        cross-family rule routes anchor verification to Claude. You have
        shell access (curl, pdftotext, pdfgrep, ocrmypdf) and can hit
        primary sources directly.

        ## Your job

        Review the contract below. For up to **8 of the most
        load-bearing Green claims** in `sources.md`, attempt to verify:
        - the URL or DOI resolves
        - the cited page or section actually contains the quoted text
          or the claim it's said to support
        - the bibliographic identifier matches the work cited

        For each claim you check, classify the result:
        - `ANCHOR_VERIFIED` — fetched and confirmed
        - `ANCHOR_PARTIAL` — source resolves but page/quote does not match
        - `ANCHOR_BROKEN` — URL is dead, paywalled, or the quote is wrong
        - `UNREACHABLE` — paywall / auth / region blocked you

        Don't try to verify all claims; pick the highest-leverage ones.
        Skip claims already marked Yellow or Red.

        ## Output (Markdown, ≤700 words)

        ```
        ## Claude Anchor Verification — `{slug}`

        Claims sampled: N

        | Claim (short) | sources.md row | Status | Notes |
        |---|---|:-:|---|
        | ... | ... | ANCHOR_VERIFIED | page 47 confirms |
        ...

        ### Cross-cutting issues
        - <e.g. JSTOR paywalls block 4/8 anchors; suggest open mirrors>
        - <e.g. one DOI mismatched the cited author>

        ### Verdict
        - READY_TO_DRAFT | READY_TO_DRAFT_WITH_CAP | NEEDS_ANCHORS | NEEDS_RESEARCH | SCOPE_DOWN
        - One sentence rationale.
        ```

        ## Contract

        {contract}
        """)


def agy_verdict_prompt(*, slug: str, contract: str) -> str:
    return dedent(f"""\
        # Verdict Pass — Structural Gap Audit (`{slug}`)

        You are the cross-family reviewer (agy lane) for an AI History
        chapter research contract. Your lane is **structural gap
        analysis** — what scenes are thin, what arguments lack
        scaffolding, where the contract over- or under-claims relative
        to its sources.

        ## CRITICAL LANE DISCIPLINE — read this first

        **Do not cite URLs, page numbers, or DOIs in your review.**
        After repeated URL and page-anchor hallucinations (Issue #421,
        commit 03640e20), Gemini was removed from anchor-verification
        duty. Codex handles that lane. Your job is structural and
        narrative — you may quote the contract back to itself, but you
        may NOT introduce new sources, URLs, or page anchors. If you
        catch yourself about to write a URL or "page N", STOP and
        rephrase the gap structurally.

        ## Your job

        Review the contract below. Focus on:

        1. **Scene structure** — Are the 5 scenes coherent and
           differentiated, or do two of them collapse into one?
        2. **Prose Capacity Plan layers** — Does each layer have a
           plausible narrative shape, or are some layers thin
           padding?
        3. **Boundary contract** — Does the chapter say clearly what
           it is NOT? Are forward-references properly sparse?
        4. **People coverage** — Are the named protagonists actually
           necessary for the chapter's argument, or are some included
           for completeness without scenes?
        5. **Open questions** — Are the named gaps the *right* gaps?
           Are there obvious holes the contract doesn't acknowledge?
        6. **Word-count discipline label** — Does the label match what
           the Prose Capacity Plan can actually carry?

        Avoid commenting on anchor accuracy — that's Codex's job. If
        you suspect an anchor is wrong, flag it as
        "Codex-please-verify" without naming a specific URL or page.

        ## Output (Markdown, ≤700 words)

        ```
        ## Structural Gap Audit — `{slug}`

        ### Scenes
        - <gap or strength, no URLs>

        ### Prose Capacity Plan
        - <layer-by-layer assessment>

        ### Boundary contract
        - <strength or weakness>

        ### Coverage gaps
        - <people / scenes / open-questions>

        ### For Codex to verify (no URLs from me)
        - <the X claim looks load-bearing — Codex please confirm anchor>

        ### Verdict
        - READY_TO_DRAFT | READY_TO_DRAFT_WITH_CAP | NEEDS_ANCHORS | NEEDS_RESEARCH | SCOPE_DOWN
        - One sentence rationale (no URLs).
        ```

        ## Contract

        {contract}
        """)


def fire(agent: str, *, prompt: str, slug: str) -> tuple[bool, str]:
    from lu_machinery.agent_runtime.errors import AgentTimeoutError, RateLimitedError
    from lu_machinery.agent_runtime.runner import invoke

    if agent == "codex":
        # None takes the lu-machinery release's default Codex model.
        model = None
        timeout = 1500
    elif agent == "claude":
        model = "claude-opus-5-5"
        timeout = 1500
    elif agent == "agy":
        # agy flash-tier lane (replaced the retired gemini-cli, #2125/#2230).
        # None takes the release's default AGY model, which is the flash tier.
        model = None
        timeout = 900
    else:
        raise ValueError(agent)

    try:
        r = invoke(
            agent, prompt,
            mode="read-only",
            cwd=REPO,
            model=model,
            task_id=f"verdict-{slug}-{agent}",
            entrypoint="consult",
            hard_timeout=timeout,
            # AGY runs read-only only on its bounded reviewer route.
            tool_config={"reviewer_tools": True} if agent == "agy" else None,
        )
        return r.ok, (r.response or "")
    except (RateLimitedError, AgentTimeoutError) as e:
        return False, f"_dispatch failed_: {type(e).__name__}: {e}"
    except Exception as e:
        return False, f"_dispatch crashed_: {type(e).__name__}: {e}"


def verdict_marker_agent(agent: str) -> str:
    """Marker token for the ``<!-- verdict {token} -->`` comment.

    The agy (Google) lane keeps the legacy ``gemini`` token so that
    ``audit_review_coverage.py`` (which maps ``<!-- verdict gemini -->`` →
    ``gemini_gap``, matching existing chapter status files) still recognizes
    agy-lane research verdicts. Renaming the marker/schema is a coupled cleanup
    deferred to the final #2230 slice. codex/claude keep their own tokens.
    """
    return "gemini" if agent == "agy" else agent


def post_comment(pr_num: int, body: str) -> None:
    """Post a single PR comment via gh."""
    p = Path(f"/tmp/verdict-comment-{pr_num}.md")
    p.write_text(body)
    subprocess.run(
        ["gh", "pr", "comment", str(pr_num), "--body-file", str(p)],
        cwd=REPO, check=True,
    )
    print(f"[post] PR #{pr_num} comment posted ({len(body)} chars)")


def _anchor_agent_for_branch(branch: str) -> str:
    """Pick the cross-family anchor verifier from the PR branch prefix.

    Cross-family rule (`docs/review-protocol.md`): the anchor reviewer
    must be a different model family than the contract author.
    """
    if branch.startswith("codex/"):
        return "claude"
    if branch.startswith("claude/"):
        return "codex"
    # Defensive fallback for unusual branch prefixes (e.g. user-pushed
    # feature branches). Preserve historical behaviour: Codex anchors.
    print(f"[warn] unrecognised branch prefix on {branch!r}; "
          "defaulting anchor verifier to codex", file=sys.stderr)
    return "codex"


def _prompt_for(agent: str, *, slug: str, contract: str) -> str:
    if agent == "codex":
        return codex_prompt(slug=slug, contract=contract)
    if agent == "claude":
        return claude_anchor_prompt(slug=slug, contract=contract)
    if agent == "agy":
        return agy_verdict_prompt(slug=slug, contract=contract)
    raise ValueError(agent)


def process_one(pr_num: int, *, only: str | None) -> None:
    meta = fetch_pr_meta(pr_num)
    branch = meta["headRefName"]
    slug = slug_from_branch(branch)
    anchor_agent = _anchor_agent_for_branch(branch)
    print(f"[run] PR #{pr_num} branch={branch} slug={slug} "
          f"anchor={anchor_agent}")
    contract = gather_contract(branch, slug)

    if only is None:
        agents = [anchor_agent, "agy"]
    else:
        agents = [only]

    out: dict[str, tuple[bool, str]] = {}

    def run_one(agent: str):
        ok, body = fire(agent, prompt=_prompt_for(
            agent, slug=slug, contract=contract), slug=slug)
        out[agent] = (ok, body)

    threads = []
    for agent in agents:
        t = threading.Thread(target=run_one, args=(agent,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    for agent, (ok, body) in out.items():
        marker = "OK" if ok else "FAILED"
        # verdict_marker_agent keeps the "gemini" token for the agy lane so
        # audit_review_coverage.py keeps matching gemini_gap (see #2230).
        comment_agent = verdict_marker_agent(agent)
        post_comment(pr_num, f"<!-- verdict {comment_agent} -->\n\n_{marker}_\n\n{body}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("prs", type=int, nargs="+",
                   help="PR numbers to verdict-pass")
    p.add_argument("--only", choices=["codex", "claude", "agy"],
                   default=None,
                   help="Run only one reviewer family (overrides "
                        "branch-based anchor routing)")
    args = p.parse_args()

    for pr in args.prs:
        try:
            process_one(pr, only=args.only)
        except Exception as e:
            print(f"[err] PR #{pr}: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
