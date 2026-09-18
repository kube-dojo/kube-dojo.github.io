#!/usr/bin/env python3
"""Thin TypeSafe / Jev System One client for local fleet agents.

Never logs or returns the API key. Receipts go to .agent/jev-experiment/receipts/
(JSONL) when log_receipt=True (default).

Usage:
  export TYPESAFE_API_KEY="$(tr -d '\\r\\n' < ~/.secrets/typesafe-ai.key)"
  .venv/bin/python scripts/typesafe_client.py \\
    --state '{"token":"тест"}' \\
    --questions '{"keep":{"type":"noul","instructions":"Keep as UA lexicon material?"}}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "jev-latest"
API_URL = "https://api.typesafe.ai/v1/systemone"
KEY_CANDIDATES = (
    Path.home() / ".secrets" / "typesafe-ai.key",
)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "AGENTS.md").exists() or (parent / "package.json").exists():
            return parent
    return Path.cwd()


def load_api_key() -> str:
    env = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if env:
        return env
    for path in KEY_CANDIDATES:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip().replace("\r", "")
    raise SystemExit(
        "TYPESAFE_API_KEY not set and no key file at ~/.secrets/typesafe-ai.key"
    )


def experiment_dir() -> Path:
    """Prefer primary-checkout .agent so worktree runs share one experiment log."""
    override = os.environ.get("KUBEDOJO_JEV_EXPERIMENT", "").strip()
    if override:
        d = Path(override)
    else:
        root = repo_root()
        git_path = root / ".git"
        # git worktree: .git is a file pointing at the main worktree
        if git_path.is_file():
            text = git_path.read_text(encoding="utf-8")
            # gitdir: /path/to/main/.git/worktrees/name
            for line in text.splitlines():
                if line.startswith("gitdir:"):
                    gitdir = Path(line.split(":", 1)[1].strip())
                    # main/.git/worktrees/X -> main
                    main = gitdir.parent.parent.parent
                    if (main / ".agent").exists() or (main / "AGENTS.md").exists():
                        root = main
                    break
        d = root / ".agent" / "jev-experiment"
    d.mkdir(parents=True, exist_ok=True)
    (d / "receipts").mkdir(exist_ok=True)
    return d


def system_one(
    state: Any,
    questions: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = 90.0,
    log_receipt: bool = True,
    tag: str = "",
) -> dict[str, Any]:
    """POST /v1/systemone. Returns full response dict (answers, model, usage)."""
    if not questions:
        raise ValueError("questions must be a non-empty dict")
    key = load_api_key()
    payload = {"state": state, "model": model, "questions": questions}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"TypeSafe HTTP {e.code}: {detail}") from e
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if log_receipt:
        _write_receipt(data, tag=tag, elapsed_ms=elapsed_ms, n_questions=len(questions))
    return data


def _write_receipt(
    data: dict[str, Any],
    *,
    tag: str,
    elapsed_ms: int,
    n_questions: int,
) -> Path:
    exp = experiment_dir()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = exp / "receipts" / f"{day}.jsonl"
    compact_answers: dict[str, Any] = {}
    for qid, ans in (data.get("answers") or {}).items():
        if not isinstance(ans, dict):
            compact_answers[qid] = ans
            continue
        t = ans.get("type")
        if t == "noul":
            compact_answers[qid] = {"type": "noul", "noul": ans.get("noul")}
        elif t == "choice":
            compact_answers[qid] = {
                "type": "choice",
                "choice": ans.get("choice"),
                "confidence": ans.get("confidence"),
            }
        elif t == "score":
            compact_answers[qid] = {
                "type": "score",
                "score": ans.get("score"),
                "confidence": ans.get("confidence"),
            }
        else:
            compact_answers[qid] = {"type": t}
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tag": tag or None,
        "model": data.get("model"),
        "usage": data.get("usage"),
        "elapsed_ms": elapsed_ms,
        "n_questions": n_questions,
        "answers": compact_answers,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # Never include key; print receipt line for agents
    usage = data.get("usage") or {}
    print(
        f"RECEIPT model={data.get('model')} "
        f"in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
        f"ms={elapsed_ms} qs={n_questions} tag={tag or '-'}",
        file=sys.stderr,
    )
    return path


def answers_only(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("answers") or {}


# --- Cookbook-backed helpers (see agents_extensions/.../COOKBOOKS.md) ---

# consistency_choice_cookbook: auto-act only when max(probabilities) >= this
MIN_CHOICE_TOP_PROB = 0.60
# citation_check: auto-accept relation verdict at or above this confidence
CITATION_AUTO_ACCEPT = 0.80

RELATION_TO_VERDICT = {
    "supports": "verified",
    "contradicts": "contradicted",
    "says_nothing": "unsupported",
}


def choice_top_prob(ans: dict[str, Any] | None) -> float | None:
    """max(probabilities) for a Choice answer, or None if missing."""
    if not ans:
        return None
    probs = ans.get("probabilities") or {}
    if not probs:
        return None
    return float(max(probs.values()))


def choice_is_uncertain(
    ans: dict[str, Any] | None,
    *,
    min_top: float = MIN_CHOICE_TOP_PROB,
) -> bool:
    """True when Choice should not auto-act (consistency_choice_cookbook)."""
    top = choice_top_prob(ans)
    if top is not None:
        return top < min_top
    if not ans:
        return True
    conf = ans.get("confidence")
    # Absent confidence = uncertain (fail closed for the auto-act gate)
    if conf is None:
        return True
    return float(conf) < min_top


def citation_relation_question() -> dict[str, Any]:
    """Choice question from citation_check cookbook."""
    return {
        "type": "choice",
        "instructions": "How does the section relate to the claim?",
        "criteria": {
            "supports": (
                "The section states the claim or directly implies that it is true"
            ),
            "contradicts": (
                "The section states the opposite of the claim or implies it is false"
            ),
            "says_nothing": (
                "The section does not address what the claim asserts, either way"
            ),
        },
    }


def check_claim_against_excerpt(
    claim: str,
    section: str,
    *,
    quote: str | None = None,
    model: str = DEFAULT_MODEL,
    auto_accept: float = CITATION_AUTO_ACCEPT,
    tag: str = "citation_check",
) -> dict[str, Any]:
    """Verify a claim against a source excerpt (citation_check pattern).

    If ``quote`` is provided and not found (whitespace-normalized) in ``section``,
    returns verdict ``fabricated`` without calling the API.
    """
    if quote is not None:
        needle = " ".join(quote.split())
        hay = " ".join(section.split())
        if needle and needle not in hay:
            return {
                "verdict": "fabricated",
                "confidence": None,
                "auto": True,
                "choice": None,
                "probabilities": None,
            }

    data = system_one(
        {"claim": claim, "section": section},
        {"relation": citation_relation_question()},
        model=model,
        tag=tag,
    )
    ans = (data.get("answers") or {}).get("relation") or {}
    choice = ans.get("choice")
    conf = ans.get("confidence")
    conf_f = float(conf) if isinstance(conf, (int, float)) else None
    verdict = RELATION_TO_VERDICT.get(choice or "", "unsupported")
    return {
        "verdict": verdict,
        "confidence": conf_f,
        "auto": conf_f is not None and conf_f >= auto_accept,
        "choice": choice,
        "probabilities": ans.get("probabilities"),
        "model": data.get("model"),
        "usage": data.get("usage"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", required=True, help="JSON state string or @file")
    p.add_argument("--questions", required=True, help="JSON questions map or @file")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--tag", default="cli")
    p.add_argument("--no-log", action="store_true")
    args = p.parse_args()

    def load_json(raw: str) -> Any:
        if raw.startswith("@"):
            return json.loads(Path(raw[1:]).read_text(encoding="utf-8"))
        return json.loads(raw)

    data = system_one(
        load_json(args.state),
        load_json(args.questions),
        model=args.model,
        log_receipt=not args.no_log,
        tag=args.tag,
    )
    json.dump(data.get("answers") or data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
