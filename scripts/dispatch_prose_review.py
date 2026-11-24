"""Dispatch a cross-family prose review on an AI History chapter PR (#394).

Mirrors `dispatch_research_verdict.py` but reads the prose file from the
prose branch instead of the research contract from the research branch,
and asks the reviewer for a source-fidelity (Claude) or prose-quality
(Codex / Gemini) check rather than an anchor-verification verdict.

The reviewer always reads the approved research contract on the chapter's
research branch, so that source-fidelity claims can be cross-checked
against the contract that gated the prose draft.

Per the 2026-04-29 prose pipeline pivot
(`docs/research/ai-history/TEAM_WORKFLOW.md` § 5b–7):

- Claude opus does **source-fidelity** review on Codex-expanded prose.
- Codex does **prose-quality** review on Claude-expanded prose
  (the Claude-default cohort, Ch01-05).
- Gemini does **prose-quality** review when Codex bandwidth is exhausted.

Usage:

    .venv/bin/python scripts/dispatch_prose_review.py 480 \\
        --reviewer claude

    .venv/bin/python scripts/dispatch_prose_review.py 483 \\
        --reviewer codex

Posts the review as a PR comment via `gh pr comment`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
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

CONTRACT_FILES = ["brief.md", "sources.md", "scene-sketches.md",
                  "open-questions.md", "people.md", "timeline.md",
                  "infrastructure-log.md", "status.yaml"]


def fetch_pr_meta(pr_num: int) -> dict:
    out = subprocess.run(
        ["gh", "pr", "view", str(pr_num), "--json",
         "headRefName,title,number"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def slug_from_pr(pr_num: int) -> str:
    """`prose/394-ch01` is too short for a slug. Pull the chapter file
    path from the PR diff."""
    out = subprocess.run(
        ["gh", "pr", "view", str(pr_num), "--json",
         "files", "--jq", ".files[].path"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    for path in out.splitlines():
        # src/content/docs/ai-history/ch-NN-slug.md
        if path.startswith("src/content/docs/ai-history/ch-"):
            return Path(path).stem
    raise ValueError(f"no chapter file found in PR #{pr_num}")


def research_branch_for(slug: str) -> str:
    """Determine the research branch that gated this prose. Claude owns
    research on Parts 1, 2, 3, 6, 7; Codex on Parts 4, 5, 8, 9. We don't
    need to enforce ownership here — just try claude/ then codex/ and
    use the one that exists. If neither is present (research already
    merged to main), fall back to main, since gather_contract just
    needs *some* ref where the contract lives."""
    chapnum = slug.split("-")[1]  # "ch-01-the-laws-of-thought" -> "01"
    candidates = [
        f"claude/394-ch{chapnum}-research",
        f"codex/394-ch{chapnum}-research",
    ]
    for branch in candidates:
        r = subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin", branch],
            cwd=REPO, capture_output=True,
        )
        if r.returncode == 0:
            return branch
    main_path = f"docs/research/ai-history/chapters/{slug}/brief.md"
    r = subprocess.run(
        ["git", "show", f"origin/main:{main_path}"],
        cwd=REPO, capture_output=True,
    )
    if r.returncode == 0:
        return "main"
    raise ValueError(f"no research branch found for {slug}")


def read_branch_file(branch: str, path: str) -> str:
    subprocess.run(["git", "fetch", "origin", branch], cwd=REPO,
                   capture_output=True, check=False)
    r = subprocess.run(
        ["git", "show", f"origin/{branch}:{path}"],
        cwd=REPO, capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else ""


def gather_contract(research_branch: str, slug: str) -> str:
    chunks = []
    for fn in CONTRACT_FILES:
        body = read_branch_file(
            research_branch,
            f"docs/research/ai-history/chapters/{slug}/{fn}",
        )
        if not body:
            chunks.append(f"### {fn}\n\n_(empty or absent)_\n")
            continue
        chunks.append(f"### {fn}\n\n```\n{body}\n```\n")
    return "\n".join(chunks)


def claude_source_fidelity_prompt(*, slug: str, pr_num: int,
                                   prose_path: str, prose: str,
                                   research_branch: str,
                                   contract: str) -> str:
    return dedent(f"""\
        # Claude Source-Fidelity Review — `{slug}` (PR #{pr_num})

        You are the cross-family Claude reviewer for Codex-expanded
        prose. Your lane is **source fidelity**: confirm that every
        load-bearing factual claim, quote, and named anchor in the
        prose can be located in the approved research contract below.

        ## The strict-source rule (load-bearing)

        Per the 2026-04-29 prose pipeline pivot (TEAM_WORKFLOW.md § 5b),
        the expander was instructed to use ONLY the provided contract
        and claim matrix — no source additions, no new page anchors,
        no Yellow→Green upgrades, no invented examples or
        institutional motives.

        Your job is to verify the expander honoured that rule, and to
        flag any prose claim that:
        - cites a source not present in `sources.md`
        - states a fact (date, name, place, quote, page anchor) absent
          from the contract
        - upgrades a Yellow/Red claim to Green confidence
        - introduces an interpretive or motive claim outside the
          boundary contract in `brief.md`
        - quotes material without an anchor in the contract
        - elides material from a quoted passage without marking the cut

        Also check basic source-fidelity hygiene:
        - quoted text matches the contract verbatim (or marks elisions)
        - named persons, dates, places, journals match the contract
        - "according to X" attributions match the contract's citation
        - hedges (Yellow) are preserved as hedges, not flattened

        ## Output (Markdown, ≤700 words)

        ```
        ## Claude Source-Fidelity Review — {slug}

        ### Sampled fidelity checks
        | Prose claim (line) | Contract anchor | Status | Notes |
        |---|---|:-:|---|
        | ... | sources.md row 3 / brief.md scene 2 | OK | matches |
        | ... | (none) | UNANCHORED | flag |

        ### Issues found
        - `<path>:<line>`: <issue>; remedy: <hedge / cite / cut>

        ### Strengths
        - <what the expander got right under strict-source>

        ### Verdict
        - READY_TO_MERGE | NEEDS_FIX_AND_MERGE | NEEDS_REWRITE
        - One sentence rationale.
        ```

        Do NOT propose stylistic rewrites. Source fidelity only.

        ## Prose under review

        File: `{prose_path}`

        ```
        {prose}
        ```

        ## Approved research contract

        Branch: `{research_branch}`

        {contract}
        """)


def codex_prose_quality_prompt(*, slug: str, pr_num: int,
                                prose_path: str, prose: str,
                                research_branch: str,
                                contract: str) -> str:
    return dedent(f"""\
        # Codex Prose Review — `{slug}` (PR #{pr_num})

        You are the cross-family Codex reviewer on a Claude-expanded
        prose chapter (or, for Part 2 forward, the prose-quality
        reviewer on a Codex-expanded chapter). Your lane is
        **prose-quality + factual-anchor verification** — combining
        Codex's anchor-discipline strength with structural prose
        review.

        You have shell access (curl, pdftotext, pdfgrep) and may
        verify primary sources directly. Pick up to 5 of the most
        load-bearing factual anchors and confirm them.

        ## The strict-source rule

        Per TEAM_WORKFLOW.md § 5b–7, the expander was instructed to
        use ONLY the approved contract — no source additions, no new
        page anchors, no Yellow→Green upgrades. Flag any prose claim
        that cannot be located in the contract.

        ## Your job

        Sample 5 high-leverage anchors. For each:
        - Confirm the URL/DOI resolves and the cited page contains
          the claimed text (✅ / PARTIAL / ❌).
        - Note the exact prose line and contract row.

        Then scan the prose for:
        - factual errors (dates, names, places, ages, journal titles)
        - anachronisms or backward-projection of later concepts
        - over-staged scene description ("the same room that…",
          motive claims without source)
        - over-tight hedges (Yellow flattened to Green)
        - over-loose hedges (Green over-hedged into vagueness)
        - boundary creep (claims belonging to a different chapter)

        ## Output (Markdown, ≤700 words)

        ```
        ## Codex Prose Review — {slug}

        ### Sampled anchor verifications
        | Claim | Status | Notes |
        |---|:-:|---|
        | ... | ✅ | matches contract row 3 + Hayes 2013 |
        | ... | ❌ | source paywalled OR quote doesn't match |

        ### Issues found
        - `<path>:<line>`: <issue>; remedy: <hedge / cite / cut>

        ### Strengths
        - <what the expander got right>

        ### Verdict
        - READY_TO_MERGE | NEEDS_FIX_AND_MERGE | NEEDS_REWRITE
        - One sentence rationale.
        ```

        ## Prose under review

        File: `{prose_path}`

        ```
        {prose}
        ```

        ## Approved research contract

        Branch: `{research_branch}`

        {contract}
        """)


def prose_quality_prompt(*, slug: str, pr_num: int,
                                 prose_path: str, prose: str,
                                 research_branch: str,
                                 contract: str) -> str:
    return dedent(f"""\
        # Prose Review — `{slug}` (PR #{pr_num})

        You are the cross-family reviewer (agy lane) on a Codex- or
        Claude-expanded prose chapter. Your lane is **contract-
        traceability sampling + readability + boundary discipline** —
        does the prose stay inside the approved contract, does it read
        well, does it stay inside the chapter's scope.

        **Lane closure (Issue #421):** Do NOT verify primary-source
        URLs or page anchors yourself. Gemini's anchor-fetching lane
        was closed on 2026-04-27 after a hallucinated-anchors audit.
        If a prose claim's correctness requires URL/page-number
        confirmation, flag it as `NEEDS_CODEX_OR_CLAUDE_VERIFY` and
        leave the verification to the Codex or Claude reviewer pass.

        ## The strict-source rule

        Per TEAM_WORKFLOW.md § 5b–7, the expander was instructed to
        use ONLY the approved contract — no source additions, no new
        page anchors, no Yellow→Green upgrades. Flag any prose claim
        that cannot be located in the staged contract files.

        ## Your job

        Sample 5 high-leverage prose claims. For each, locate the
        matching contract row (brief / sources / scene-sketches /
        timeline / people / infrastructure-log) and mark:
        - **TRACED** — claim is supported by an identifiable contract row
        - **GAP** — claim is not in the contract (likely fabrication)
        - **NEEDS_CODEX_OR_CLAUDE_VERIFY** — claim needs URL or
          page-anchor check that is out of your lane

        Then scan the prose for:
        - internal inconsistencies (dates / names / numbers that
          disagree across the chapter)
        - anachronisms or backward-projection of later concepts
        - over-staged scene description (motive claims without
          source row)
        - over-tight hedges (Yellow flattened to Green)
        - over-loose hedges (Green over-hedged into vagueness)
        - boundary creep (claims belonging to a different chapter)
        - structural / readability issues (paragraph length,
          transitions, signpost density, opening hook quality)

        ## Output (Markdown, ≤700 words)

        ```
        ## Prose Review — {slug}

        ### Sampled contract traces
        | Claim | Status | Contract row |
        |---|:-:|---|
        | ... | TRACED | sources.md row 3 |
        | ... | GAP | not in contract |
        | ... | NEEDS_CODEX_OR_CLAUDE_VERIFY | needs primary-source check |

        ### Issues found
        - `<path>:<line>`: <issue>; remedy: <hedge / cite / cut>

        ### Strengths
        - <what the expander got right>

        ### Verdict
        - READY_TO_MERGE | NEEDS_FIX_AND_MERGE | NEEDS_REWRITE
        - One sentence rationale.
        ```

        ## Prose under review

        File: `{prose_path}`

        ```
        {prose}
        ```

        ## Approved research contract

        Branch: `{research_branch}`

        {contract}
        """)


def fire(reviewer: str, *, prompt: str, slug: str) -> tuple[bool, str]:
    from lu_machinery.agent_runtime.errors import AgentTimeoutError, RateLimitedError
    from lu_machinery.agent_runtime.runner import invoke

    if reviewer == "claude":
        model = "claude-opus-5-5"
        timeout = 1500
    elif reviewer == "codex":
        # None takes the lu-machinery release's default Codex model.
        model = None
        timeout = 1500
    elif reviewer == "agy":
        # agy pro lane (replaced the retired gemini-cli, #2125/#2230). Pro
        # tier for prose review — drafting already uses pro; the flash lane
        # historically hit persistent 429 "No capacity available". Must be a
        # valid agy model slug, NOT a gemini-cli model id. Override via
        # KUBEDOJO_AGY_REVIEW_MODEL. The legacy KUBEDOJO_GEMINI_REVIEW_MODEL is
        # intentionally NOT honored — it would inject a retired gemini-cli slug.
        import os
        model = os.environ.get("KUBEDOJO_AGY_REVIEW_MODEL", "gemini-4-neon-high")
        timeout = 900
    else:
        raise ValueError(reviewer)

    try:
        r = invoke(
            reviewer, prompt,
            mode="read-only",
            cwd=REPO,
            model=model,
            task_id=f"prose-review-{slug}-{reviewer}",
            entrypoint="consult",
            hard_timeout=timeout,
            # No tool_config: the release provisions read-only AGY's bounded
            # route itself; a partial hand-built config is refused.
        )
        return r.ok, (r.response or "")
    except (RateLimitedError, AgentTimeoutError) as e:
        return False, f"_dispatch failed_: {type(e).__name__}: {e}"
    except Exception as e:
        return False, f"_dispatch crashed_: {type(e).__name__}: {e}"


def post_comment(pr_num: int, body: str) -> None:
    p = Path(f"/tmp/prose-review-{pr_num}.md")
    p.write_text(body)
    subprocess.run(
        ["gh", "pr", "comment", str(pr_num), "--body-file", str(p)],
        cwd=REPO, check=True,
    )
    print(f"[post] PR #{pr_num} comment posted ({len(body)} chars)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pr_num", type=int)
    p.add_argument("--reviewer", choices=["claude", "codex", "agy"],
                   required=True)
    p.add_argument("--no-post", action="store_true",
                   help="print review to stdout instead of posting")
    args = p.parse_args()
    import os
    override = os.environ.get("KUBEDOJO_AGY_REVIEW_MODEL")
    if args.reviewer == "agy" and override:
        from lu_machinery.review.model_catalog import retired_model_refusal
        if refusal := retired_model_refusal(override):
            p.error(f"KUBEDOJO_AGY_REVIEW_MODEL={override!r}: {refusal}")

    meta = fetch_pr_meta(args.pr_num)
    prose_branch = meta["headRefName"]
    slug = slug_from_pr(args.pr_num)
    research_branch = research_branch_for(slug)
    prose_path = f"src/content/docs/ai-history/{slug}.md"

    print(f"[start] PR #{args.pr_num} branch={prose_branch} slug={slug}")
    print(f"[start] research contract from {research_branch}")
    print(f"[start] reviewer={args.reviewer}")

    prose = read_branch_file(prose_branch, prose_path)
    if not prose:
        # Branch was deleted post-merge (common for backfill on already-merged PRs).
        # Fall back to main, where the prose lives now.
        print(f"[info] {prose_branch} unreadable; falling back to main")
        prose = read_branch_file("main", prose_path)
    if not prose:
        print(f"[fail] could not read {prose_path} from {prose_branch} or main")
        return 1
    print(f"[read] prose: {len(prose.split())} words")

    contract = gather_contract(research_branch, slug)
    print(f"[read] contract: {len(contract)} chars")

    if args.reviewer == "claude":
        prompt = claude_source_fidelity_prompt(
            slug=slug, pr_num=args.pr_num,
            prose_path=prose_path, prose=prose,
            research_branch=research_branch, contract=contract,
        )
        marker = "_Claude opus source-fidelity review (cross-family)_"
        header = "<!-- prose review claude (cross-family, source-fidelity) -->"
    elif args.reviewer == "codex":
        prompt = codex_prose_quality_prompt(
            slug=slug, pr_num=args.pr_num,
            prose_path=prose_path, prose=prose,
            research_branch=research_branch, contract=contract,
        )
        marker = "_Codex (gpt-5.5) prose review (cross-family)_"
        header = "<!-- prose review codex (cross-family, prose-quality) -->"
    else:
        # agy (the Google lane; reviewer=="agy")
        prompt = prose_quality_prompt(
            slug=slug, pr_num=args.pr_num,
            prose_path=prose_path, prose=prose,
            research_branch=research_branch, contract=contract,
        )
        # NOTE: the marker/header strings intentionally keep the "gemini"
        # token — audit_review_coverage.py matches `<!-- prose review gemini`
        # for coverage tracking. Renaming them is coupled to that matcher and
        # is deferred to the final #2230 marker-rename cleanup.
        marker = "_Gemini prose review (cross-family, lane-disciplined per #421)_"
        header = "<!-- prose review gemini (cross-family, prose-quality) -->"

    print(f"[prompt] {len(prompt)} chars")

    ok, body = fire(args.reviewer, prompt=prompt, slug=slug)
    if not ok:
        print(f"[fail] {body[:300]}")
        return 2
    print(f"[review] {len(body)} chars")

    full_body = f"{header}\n\n{marker}\n\n{body}"

    if args.no_post:
        print("\n========== REVIEW ==========\n")
        print(full_body)
        return 0

    post_comment(args.pr_num, full_body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
