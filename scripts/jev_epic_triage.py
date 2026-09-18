#!/usr/bin/env python3
"""Jev pre-dispatch triage for KubeDojo epic / Gap Catcher waves.

Builds enriched state from gh CLI (or --state-file), asks a batched System One
fan-out, applies code-side policy (family exclusion, parallel thresholds,
confidence bands), prints a recommendation, and logs to
.agent/jev-experiment/.

Does NOT dispatch, merge, or post CF — the lead acts on the recommendation.

Friction fixes (2026-09-18):
  1. Richer PR state: author_family, auditor_family, cf_status, ci_green
  2. Receipts → primary .agent via typesafe_client gitdir resolution
  3. CF/author post-filter excludes author_family + auditor_family
  4. parallel_ok < PARALLEL_NO → serialize (do not parallel)
  5. Smarter escalate: seat floor lower; ambiguous = top-two probs close

Examples:
  .venv/bin/python scripts/jev_epic_triage.py --epic 2272 --lane G
  .venv/bin/python scripts/jev_epic_triage.py --state-file /tmp/triage-state.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from typesafe_client import (
    MIN_CHOICE_TOP_PROB,
    answers_only,
    choice_is_uncertain,
    choice_top_prob,
    experiment_dir,
    system_one,
)

# --- thresholds (tune from experiment receipts; see COOKBOOKS.md) ---
AMBIGUOUS_GAP = 0.15  # top-two Choice probs within this → escalate
PARALLEL_NO = 0.35  # below → serialize (honor Jev)
PARALLEL_YES = 0.65  # above → parallel OK
# 0.35–0.65 → uncertain; escalate note but lead may still parallel path-disjoint work

FAMILY_ALIASES = {
    "kimi": "kimi",
    "moonshot": "kimi",
    "agy": "agy",
    "gemini": "agy",
    "google": "agy",
    "grok": "grok",
    "xai": "grok",
    "cursor": "cursor",
    "composer": "cursor",
    "codex": "codex",
    "claude": "claude",
    "deepseek": "deepseek",
}

SEAT_ORDER = [
    "kimi",
    "agy",
    "grok",
    "cursor",
    "claude",
    "codex",
    "deepseek",
]  # prefer order when re-picking; never invent a seat outside this list


def _gh_json(args: list[str]) -> Any:
    r = subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _normalize_family(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    for key, fam in FAMILY_ALIASES.items():
        if key in s:
            return fam
    return s.split()[0] if s else None


def _infer_author_family(*texts: str) -> str | None:
    """Author only — do not treat 'audit #N (grok)' as the author family."""
    blob = "\n".join(t for t in texts if t)
    for pat in (
        r"(?i)author(?:\s+family)?\s*[:\-]\s*([a-z0-9/+.-]+)",
        r"(?i)\*\*author\*\*\s*[:\-]\s*([a-z0-9/+.-]+)",
        r"(?i)author\s+family\s*[:\-]\s*([a-z0-9/+.-]+)",
    ):
        m = re.search(pat, blob)
        if m:
            return _normalize_family(m.group(1))
    return None


def _infer_auditor_family(*texts: str) -> str | None:
    blob = "\n".join(t for t in texts if t)
    for pat in (
        r"(?i)auditor(?:\s+family)?\s*[:\-]\s*([a-z0-9/+.-]+)",
        r"(?i)audit(?:or)?\s+#?\d+\s*\(([a-z0-9/+.-]+)\)",
        r"(?i)disposition\s+from\s+audit\s+#?\d+\s*\(([a-z0-9/+.-]+)\)",
        r"(?i)audit:\s*#?\d+\s*\(([a-z0-9/+.-]+)\s+disposition",
    ):
        m = re.search(pat, blob)
        if m:
            return _normalize_family(m.group(1))
    return None


def _ci_status(rollup: list[dict[str, Any]] | None) -> tuple[bool, list[str]]:
    """Return (ci_green, pending_or_failing names).

    Unknown / empty conclusions never count as green (fail closed).
    """
    pending: list[str] = []
    if not rollup:
        return False, ["unknown"]
    for c in rollup:
        name = c.get("name") or "?"
        conclusion = (c.get("conclusion") or "").upper()
        status = (c.get("status") or "").upper()
        if conclusion in ("SUCCESS", "SKIPPED", "NEUTRAL"):
            continue
        if conclusion in ("FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"):
            pending.append(f"{name}:{conclusion.lower()}")
            continue
        if status in ("IN_PROGRESS", "QUEUED", "PENDING") or (
            not conclusion and status and status != "COMPLETED"
        ):
            pending.append(name)
            continue
        # COMPLETED with no conclusion, StatusContext, or anything else → not green
        pending.append(f"{name}:unknown")
    return (len(pending) == 0), pending[:8]


def _cf_status(pr_number: int, head_oid: str | None = None) -> str:
    """missing | pass | needs_changes | present_unknown — from issue comments.

    When ``head_oid`` is set, only comments that mention that SHA (full or
    short) count as exact-head CF. Stale CF on an older head → missing.
    """
    comments = _gh_json(
        [
            "api",
            f"repos/kube-dojo/kube-dojo.github.io/issues/{pr_number}/comments",
            "--jq",
            "[.[] | {body, createdAt}]",
        ]
    )
    if not isinstance(comments, list) or not comments:
        return "missing"
    head_short = (head_oid or "")[:7].lower()
    head_full = (head_oid or "").lower()
    # Prefer newest matching comments
    for item in reversed(comments):
        body = str(item.get("body") if isinstance(item, dict) else item)
        if head_short:
            lower = body.lower()
            if head_full and head_full not in lower and head_short not in lower:
                continue  # not exact-head
        # Verdict markers — line-anchored, not prose mentioning the opposite
        if re.search(
            r"(?im)^\s*(\*\*)?verdict(\*\*)?\s*:\s*needs[_\s-]?changes\b",
            body,
        ) or re.search(r"(?im)^\s*(\*\*)?verdict(\*\*)?\s*:\s*revise\b", body):
            return "needs_changes"
        if re.search(
            r"(?im)^\s*(\*\*)?verdict(\*\*)?\s*:\s*(pass|approve|lgtm|approve_with_nits)\b",
            body,
        ) or re.search(r"(?im)^\s*cf\s*:\s*pass\b", body):
            return "pass"
        if re.search(r"(?i)\b(cross-family|verdict)\b", body):
            return "present_unknown"
    return "missing"


def _enrich_pr(pr: dict[str, Any]) -> dict[str, Any]:
    num = pr.get("number")
    body = pr.get("body") or ""
    title = pr.get("title") or ""
    comments_tail = ""
    if num:
        # Last CF/author hint from comments (cheap: only last comment body via api)
        last = _gh_json(
            [
                "api",
                f"repos/kube-dojo/kube-dojo.github.io/issues/{num}/comments",
                "--jq",
                '.[-1].body // ""',
            ]
        )
        if isinstance(last, str):
            comments_tail = last[:1500]
    author_family = _infer_author_family(body, title, comments_tail)
    auditor_family = _infer_auditor_family(body, title, comments_tail)
    # Local ledger from dispatch lead (gitignored experiment dir)
    if not author_family and num:
        ledger = experiment_dir() / "known_authors.json"
        if ledger.is_file():
            try:
                known = json.loads(ledger.read_text(encoding="utf-8"))
                author_family = _normalize_family(
                    str(known.get(str(num)) or known.get(num) or "")
                )
            except (json.JSONDecodeError, OSError):
                pass
    ci_green, pending = _ci_status(pr.get("statusCheckRollup"))
    head_oid = pr.get("headRefOid") or ""
    cf_status = _cf_status(int(num), head_oid) if num else "missing"
    return {
        "number": num,
        "title": title[:120],
        "head": head_oid[:7],
        "author_family": author_family,
        "auditor_family": auditor_family,
        "cf_status": cf_status,
        "ci_green": ci_green,
        "pending_checks": pending,
        "merge_ready_hint": bool(
            ci_green and cf_status == "pass" and author_family
        ),
    }


def build_default_state(epic: int, lane: str) -> dict[str, Any]:
    open_prs = (
        _gh_json(
            [
                "pr",
                "list",
                "--repo",
                "kube-dojo/kube-dojo.github.io",
                "--state",
                "open",
                "--limit",
                "12",
                "--json",
                "number,title,body,headRefOid,statusCheckRollup,updatedAt",
            ]
        )
        or []
    )
    prs = [_enrich_pr(pr) for pr in open_prs]
    # Families to exclude for the next CF (from PRs needing CF)
    exclude_for_cf: list[str] = []
    for pr in prs:
        if pr.get("cf_status") == "missing":
            for key in ("author_family", "auditor_family"):
                fam = pr.get(key)
                if fam and fam not in exclude_for_cf:
                    exclude_for_cf.append(fam)
    return {
        "epic": epic,
        "lane": lane,
        "open_prs": prs,
        "exclude_families_for_cf": exclude_for_cf,
        "policy": {
            "cf_neq_author": True,
            "cf_neq_auditor": True,
            "exact_head_ci_required_to_merge": True,
            "jev_is_advisory_not_merge_authority": True,
            "parallel_no_below": PARALLEL_NO,
            "parallel_yes_above": PARALLEL_YES,
            "prefer_seats": SEAT_ORDER,
            "avoid_seats_when_hot": ["codex"],
            "no_hermes": True,
        },
        "goal": (
            "Keep Gap Catcher / epic conveyor moving without idle; "
            "path-disjoint packets; honor serialize when parallel_ok is low."
        ),
    }


def default_questions(state: dict[str, Any]) -> dict[str, Any]:
    exclude = state.get("exclude_families_for_cf") or []
    exclude_txt = ", ".join(exclude) if exclude else "none listed"
    return {
        "next_action": {
            "type": "choice",
            "instructions": (
                "Highest-leverage next action given `open_prs` (use cf_status, "
                "ci_green, merge_ready_hint) and `policy`. Prefer merge when "
                "merge_ready_hint is true. Prefer dispatch_cf when cf_status is missing "
                "and CI is green or nearly green."
            ),
            "criteria": {
                "merge_green_cf_done": (
                    "Merge an open PR with cf_status=pass and ci_green=true"
                ),
                "dispatch_cf": ("Dispatch CF on an open PR with cf_status=missing"),
                "dispatch_author": "File/dispatch an author packet from a revise audit",
                "dispatch_audit": "Dispatch the next disposition audit on the conveyor",
                "parallel_wave": (
                    "Launch CF and author/audit in parallel only if path-disjoint "
                    "and capacity allows"
                ),
                "wait_ci": "Wait — critical PR still has pending_checks",
                "unblock_human": "Needs human input; do not guess",
            },
        },
        "cf_agent": {
            "type": "choice",
            "instructions": (
                "Best CF agent family for the next review. MUST differ from "
                f"`exclude_families_for_cf` ({exclude_txt}) and from the PR "
                "`author_family` / `auditor_family`. Prefer a cool seat."
            ),
            "criteria": {
                "kimi": "Moonshot kimi — only if not excluded",
                "agy": "Google agy/Gemini — only if not excluded",
                "grok": "xAI grok — only if not excluded",
                "cursor": "Cursor agent — only if not excluded",
                "none": "No CF needed this wave",
            },
        },
        "author_agent": {
            "type": "choice",
            "instructions": (
                "Best author agent for the next revise packet. Prefer differing "
                "from the auditor family when known."
            ),
            "criteria": {
                "kimi": "Moonshot kimi",
                "agy": "Google agy/Gemini",
                "grok": "xAI grok",
                "cursor": "Cursor agent",
                "none": "No author needed this wave",
            },
        },
        "parallel_ok": {
            "type": "noul",
            "instructions": (
                "Is it safe to run CF and author/audit on the SAME critical path "
                "in parallel? Answer no if seats would contend or work shares a file. "
                "Path-disjoint work can still proceed even when this is low — "
                "code will serialize the contended pair."
            ),
        },
        "jev_confidence_note": {
            "type": "score",
            "instructions": (
                "How clear is the operational picture from enriched `open_prs` "
                "(cf_status, ci_green, families)?"
            ),
            "criteria": [
                "Too thin — need more gh detail",
                "Barely enough",
                "Adequate for a wave",
                "Very clear",
            ],
        },
    }


def _choice_ambiguous(ans: dict[str, Any]) -> bool:
    probs = ans.get("probabilities") or {}
    if len(probs) < 2:
        return False
    ordered = sorted(probs.values(), reverse=True)
    return (ordered[0] - ordered[1]) < AMBIGUOUS_GAP


def _choice_or_uncertain(ans: dict[str, Any]) -> tuple[str | None, float | None, bool]:
    """Return (label, top_prob, is_uncertain) per consistency_choice_cookbook."""
    label = ans.get("choice")
    top = choice_top_prob(ans)
    uncertain = choice_is_uncertain(ans)
    if top is None and ans.get("confidence") is not None:
        top = float(ans["confidence"])
    return label, top, uncertain


def _repick_seat(preferred: str | None, exclude: set[str]) -> str | None:
    """Pick a seat not in exclude. None = no clean seat (caller must escalate)."""
    if preferred and preferred not in exclude and preferred != "none":
        return preferred
    for seat in SEAT_ORDER:
        if seat not in exclude:
            return seat
    return None


def recommend(answers: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    next_a = answers.get("next_action") or {}
    cf = answers.get("cf_agent") or {}
    author = answers.get("author_agent") or {}
    parallel = answers.get("parallel_ok") or {}
    clarity = answers.get("jev_confidence_note") or {}

    exclude = set(state.get("exclude_families_for_cf") or [])
    for pr in state.get("open_prs") or []:
        if pr.get("cf_status") == "missing":
            for key in ("author_family", "auditor_family"):
                if pr.get(key):
                    exclude.add(pr[key])

    raw_cf = cf.get("choice")
    raw_author = author.get("choice")
    overrides: list[str] = []

    noul = parallel.get("noul")
    if isinstance(noul, (int, float)):
        if noul < PARALLEL_NO:
            parallel_policy = "serialize"
        elif noul > PARALLEL_YES:
            parallel_policy = "parallel_ok"
        else:
            parallel_policy = "uncertain"
    else:
        parallel_policy = "unknown"

    next_choice, next_top, next_uncertain = _choice_or_uncertain(next_a)
    next_choice = next_choice or next_a.get("choice")
    if next_choice == "parallel_wave" and parallel_policy == "serialize":
        next_choice = "dispatch_cf"
        overrides.append("next_action parallel_wave→dispatch_cf (parallel_no)")

    cf_label, cf_top, cf_uncertain = _choice_or_uncertain(cf)
    author_label, author_top, author_uncertain = _choice_or_uncertain(author)

    if cf_uncertain:
        escalate_cf = True
        raw_cf_eff = None
    else:
        escalate_cf = False
        raw_cf_eff = cf_label or raw_cf
    adj_cf = _repick_seat(raw_cf_eff, exclude)
    if adj_cf is None:
        escalate_cf = True
        overrides.append(
            f"cf_agent no clean seat (excluded={sorted(exclude)}); escalate"
        )
    elif raw_cf and raw_cf != adj_cf and raw_cf != "none":
        overrides.append(f"cf_agent {raw_cf}→{adj_cf} (family exclusion)")
    if cf_uncertain and adj_cf:
        overrides.append(
            f"cf_agent top_prob={cf_top} < {MIN_CHOICE_TOP_PROB} → uncertain; "
            f"repicked {adj_cf}"
        )

    adj_author = author_label or raw_author
    if author_uncertain:
        overrides.append(
            f"author_agent top_prob={author_top} < {MIN_CHOICE_TOP_PROB} → uncertain"
        )
        adj_author = _repick_seat(None, exclude | ({adj_cf} if adj_cf else set()))
        if adj_author:
            overrides.append(f"author_agent repicked → {adj_author}")
        else:
            overrides.append("author_agent no clean seat; escalate")
    if (
        adj_author
        and adj_cf
        and adj_author == adj_cf
        and adj_author not in (None, "none")
    ):
        adj_author = _repick_seat(None, exclude | {adj_cf})
        if adj_author:
            overrides.append(f"author_agent →{adj_author} (≠ cf seat)")
        else:
            overrides.append("author_agent collides with cf; no alternate seat")

    escalate: list[str] = []
    if adj_cf is None:
        escalate.append(
            f"no CF seat outside excluded families {sorted(exclude)}"
        )
    if adj_author is None and (author_uncertain or raw_author not in (None, "none")):
        escalate.append("no author seat available under exclusion")
    if next_uncertain:
        ready = any(p.get("merge_ready_hint") for p in (state.get("open_prs") or []))
        if next_choice == "merge_green_cf_done" and ready:
            overrides.append("suppressed next_action uncertain (merge_ready_hint)")
        else:
            escalate.append(
                f"next_action uncertain (top_prob={next_top} < {MIN_CHOICE_TOP_PROB})"
            )
    elif next_a.get("type") == "choice" and _choice_ambiguous(next_a):
        escalate.append("next_action ambiguous (top-two gap)")
    if escalate_cf or (cf_uncertain and raw_cf not in (None, "none")):
        escalate.append(
            f"cf_agent uncertain (top_prob={cf_top} < {MIN_CHOICE_TOP_PROB})"
        )
    elif (
        cf.get("type") == "choice"
        and raw_cf not in (None, "none")
        and _choice_ambiguous(cf)
    ):
        escalate.append("cf_agent ambiguous (top-two gap)")
    if author_uncertain and raw_author not in (None, "none"):
        escalate.append(
            f"author_agent uncertain (top_prob={author_top} < {MIN_CHOICE_TOP_PROB})"
        )
    if parallel_policy == "uncertain":
        escalate.append("parallel_ok uncertain band")
    for pr in state.get("open_prs") or []:
        if pr.get("cf_status") == "missing" and not pr.get("author_family"):
            escalate.append(
                f"author_family unknown on PR #{pr.get('number')} — confirm CF≠author"
            )
            break

    cf_out: str | None
    if adj_cf is None:
        cf_out = None
    elif raw_cf == "none":
        cf_out = "none"
    else:
        cf_out = adj_cf

    return {
        "next_action": next_choice,
        "next_action_confidence": next_a.get("confidence"),
        "next_action_top_prob": next_top,
        "next_action_uncertain": next_uncertain,
        "cf_agent": cf_out,
        "cf_agent_raw": raw_cf,
        "cf_agent_confidence": cf.get("confidence"),
        "cf_agent_top_prob": cf_top,
        "cf_agent_uncertain": cf_uncertain,
        "author_agent": adj_author,
        "author_agent_raw": raw_author,
        "author_agent_confidence": author.get("confidence"),
        "author_agent_top_prob": author_top,
        "author_agent_uncertain": author_uncertain,
        "parallel_ok_noul": noul,
        "parallel_policy": parallel_policy,
        "picture_clarity_score": clarity.get("score"),
        "exclude_families_for_cf": sorted(exclude),
        "min_choice_top_prob": MIN_CHOICE_TOP_PROB,
        "overrides": overrides,
        "escalate": escalate,
        "advisory_only": True,
        "note": (
            "Lead must still enforce CF≠author and exact-head CI before merge. "
            f"Choice auto-act only if top_prob>={MIN_CHOICE_TOP_PROB} "
            f"(consistency_choice_cookbook). "
            f"Honor parallel_policy={parallel_policy} "
            f"(serialize if <{PARALLEL_NO}, parallel if >{PARALLEL_YES}). "
            "If cf_agent is null, do not dispatch — escalate."
        ),
    }


def append_decision(rec: dict[str, Any], answers: dict[str, Any], tag: str) -> None:
    exp = experiment_dir()
    path = exp / "decisions.jsonl"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "recommendation": rec,
        "answers": {
            k: {
                "type": v.get("type"),
                **(
                    {"noul": v.get("noul")}
                    if v.get("type") == "noul"
                    else {
                        "choice": v.get("choice"),
                        "confidence": v.get("confidence"),
                    }
                    if v.get("type") == "choice"
                    else {
                        "score": v.get("score"),
                        "confidence": v.get("confidence"),
                    }
                ),
            }
            for k, v in answers.items()
            if isinstance(v, dict)
        },
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    log = exp / "RUNNING_LOG.md"
    if not log.exists():
        log.write_text(
            "# Jev experiment running log\n\n"
            "Lead fills **Outcome** after acting. Report tomorrow from this file + receipts/.\n\n",
            encoding="utf-8",
        )
    with log.open("a", encoding="utf-8") as f:
        f.write(
            f"## {row['ts']}\n"
            f"- tag: `{tag}`\n"
            f"- next: **{rec.get('next_action')}** "
            f"(conf={rec.get('next_action_confidence')})\n"
            f"- cf: {rec.get('cf_agent')} (raw={rec.get('cf_agent_raw')}) / "
            f"author: {rec.get('author_agent')}\n"
            f"- parallel_noul: {rec.get('parallel_ok_noul')} "
            f"→ **{rec.get('parallel_policy')}**\n"
            f"- overrides: {rec.get('overrides') or '—'}\n"
            f"- escalate: {rec.get('escalate') or '—'}\n"
            f"- Outcome: _(pending)_\n\n"
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epic", type=int, default=2272)
    p.add_argument("--lane", default="G")
    p.add_argument("--state-file", help="JSON file overriding auto state")
    p.add_argument("--tag", default="epic-triage")
    p.add_argument(
        "--dry-state",
        action="store_true",
        help="Print enriched state JSON and exit (no TypeSafe call)",
    )
    args = p.parse_args()

    if args.state_file:
        state = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
    else:
        state = build_default_state(args.epic, args.lane)

    if args.dry_state:
        json.dump(state, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    data = system_one(state, default_questions(state), tag=args.tag)
    ans = answers_only(data)
    rec = recommend(ans, state)
    append_decision(rec, ans, args.tag)
    json.dump(
        {
            "recommendation": rec,
            "state_summary": {
                "n_prs": len(state.get("open_prs") or []),
                "exclude_families_for_cf": state.get("exclude_families_for_cf"),
                "open_prs": state.get("open_prs"),
            },
            "answers": ans,
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
