"""Passive verifier for review findings against branch or worktree files."""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path


def _norm(text: str) -> str:
    text = "\n".join(line.strip() for line in text.replace("`", "").splitlines()).strip()
    return re.sub(r"\s+", " ", text)


def _valid_path(path: object) -> bool:
    return isinstance(path, str) and bool(path.strip()) and not Path(path).is_absolute() and ".." not in Path(path).parts


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_findings(review: str) -> list[dict[str, object]]:
    if not review.strip():
        raise ValueError("empty review")
    if review.lstrip().startswith("{"):
        try:
            data = json.loads(review, object_pairs_hook=_unique_pairs)
        except json.JSONDecodeError as exc:
            raise ValueError("malformed structured review") from exc
        verdict = data.get("verdict") if isinstance(data, dict) else None
        findings = data.get("findings") if isinstance(data, dict) else None
        head = data.get("head") if isinstance(data, dict) else None
        if (not isinstance(verdict, str) or verdict not in {"APPROVE", "APPROVE_WITH_NITS", "NEEDS_CHANGES"} or not isinstance(findings, list)
                or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head)):
            raise ValueError("missing, unsupported or inconclusive structured review")
        if not findings and verdict not in {"APPROVE", "APPROVE_WITH_NITS"}:
            raise ValueError("non-approval without findings")
        result = []
        for item in findings:
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                                for k in ("id", "severity", "quote", "why", "fix")):
                raise ValueError("malformed structured finding")
            path, line, quote = item.get("path"), item.get("line"), item.get("quote")
            if not _valid_path(path) or type(line) is not int or line < 1 or any(r["id"] == item["id"] for r in result):
                raise ValueError("invalid finding path, line or duplicate id")
            result.append({"id": item["id"], "path": path, "line": line, "code": quote})
        return result
    section = re.search(r"^### Findings\s*$([\s\S]*?)(?=^### |\Z)", review, re.MULTILINE | re.IGNORECASE)
    if section:
        entries = re.findall(r"^-\s+\*\*(R\d+-[FN]\d+)\b[^\n]*", section.group(1), re.MULTILINE)
        bullets = re.findall(r"^-\s+.+", section.group(1), re.MULTILINE)
        if not entries or len(entries) != len(bullets) or not re.search(r"needs[ _-]changes|reject|approv", review, re.IGNORECASE):
            raise ValueError("unrecognized or incomplete findings section")
        return [{"id": item, "status": "unsupported_evidence"} for item in entries]
    starts = [m.start() for m in re.finditer(r"^FINDING:", review, re.MULTILINE)] + [len(review)]
    findings = []
    for start, end in itertools.pairwise(starts):
        block = review[start:end].strip()
        loc = re.search(r"^FILE:LINE:\s*(.+?):(\d+)\s*$", block, re.MULTILINE)
        code = re.search(r"^CURRENT CODE(?: .*)?:\s*$", block, re.MULTILINE)
        if not (loc and code):
            raise ValueError("malformed legacy finding")
        body = []
        for line in block[code.end():].splitlines():
            if re.match(r"^[A-Z][A-Z ]+:", line):
                break
            body.append(line.lstrip())
        quote = "\n".join(body).strip()
        if not _norm(quote) or int(loc.group(2)) < 1 or not _valid_path(loc.group(1)):
            raise ValueError("empty quote or invalid line")
        findings.append({"path": loc.group(1), "line": int(loc.group(2)), "code": quote})
    if not findings:
        raise ValueError("unrecognized review")
    return findings


def verify_review(review: str, reader) -> list[dict[str, object]]:
    results = []
    for finding in parse_findings(review):
        if finding.get("status") == "unsupported_evidence":
            results.append(finding)
            continue
        try:
            text = reader(finding["path"])
        except (OSError, subprocess.CalledProcessError):
            results.append({**finding, "status": "file_missing"})
            continue
        quote = str(finding["code"])
        lines = text.splitlines()
        span = max(1, str(finding["code"]).count("\n") + 1)
        start = max(0, int(finding["line"]) - 1)
        window = "\n".join(lines[start:start + span])
        if "id" not in finding:  # Preserve legacy whitespace/backtick normalization.
            quote, text, window = _norm(quote), _norm(text), _norm(window)
        status = "quote_missing" if quote not in text else "verified" if quote in window else "line_mismatch"
        results.append({**finding, "status": status})
    return results


def _read_target(path: str, branch: str | None) -> str:
    if branch:
        return subprocess.run(
            ["git", "show", f"{branch}:{path}"], check=True, text=True, capture_output=True
        ).stdout
    return Path(path).read_text("utf-8")


_SUMMARY_PREFIX = "Review verifier for PR"


def _read_review(args: argparse.Namespace) -> str:
    if not args.from_pr:
        return sys.stdin.read()
    jq = (
        f'[.comments[] | select(.body | startswith("{_SUMMARY_PREFIX}") | not)]'
        ' | last | .body // ""'
    )
    return subprocess.run(
        ["gh", "pr", "view", str(args.pr), "--json", "comments", "--jq", jq],
        check=True, text=True, capture_output=True,
    ).stdout


def _summary(pr: int, results: list[dict[str, object]]) -> str:
    counts = {name: sum(r["status"] == name for r in results) for name in ("verified", "line_mismatch", "quote_missing", "unsupported_evidence", "file_missing")}
    lines = [f"Review verifier for PR #{pr}: {counts['verified']} verified, {counts['line_mismatch']} line_mismatch, {counts['quote_missing']} quote_missing."]
    lines.extend(f"- `{r['status']}` {r.get('path', r.get('id'))}:{r.get('line', '?')}" for r in results)
    lines.append(f"Unsupported evidence: {counts['unsupported_evidence']}; missing files: {counts['file_missing']}.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--branch")
    parser.add_argument("--from-pr", action="store_true")
    parser.add_argument("--post-comment", action="store_true")
    args = parser.parse_args()
    try:
        review = _read_review(args)
        if review.lstrip().startswith("{"):
            if not args.branch:
                raise ValueError("structured review requires --branch at its recorded head")
            revision = subprocess.run(["git", "rev-parse", "--verify", f"{args.branch}^{{commit}}"],
                                      check=True, text=True, capture_output=True).stdout.strip()
            if json.loads(review).get("head") != revision:
                raise ValueError("review head does not match selected revision")
            args.branch = revision
        results = verify_review(review, lambda path: _read_target(path, args.branch))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Review verification failed: {exc}", file=sys.stderr)
        return 2
    body = _summary(args.pr, results) + ("\nRecognized approval with no findings." if not results else "")
    print(body)
    if args.post_comment:
        subprocess.run(["gh", "pr", "comment", str(args.pr), "-F", "-"], input=body, check=True, text=True)
    return 1 if any(r["status"] != "verified" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
