"""Read-only worktree and artifact lifecycle audit; never authorizes deletion."""

import argparse
import json
import subprocess
from pathlib import Path


def command(args, cwd):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=15, check=False)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inventory(repo):
    output = command(["git", "worktree", "list", "--porcelain"], repo)
    if not output:
        return None
    rows = []
    for block in output.strip().split("\n\n"):
        row = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            row[key] = value
        if not row.get("worktree"):
            return None
        rows.append(row)
    return rows


def audit(repo, registry_path=None, github=False):
    issues = []
    rows = inventory(repo)
    if not rows:
        return {"ok": False, "issues": ["worktree inventory unavailable"], "worktrees": [], "artifacts": []}
    path = Path(registry_path) if registry_path else Path(rows[0]["worktree"]) / ".agent/workspace-hygiene.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ("worktrees", "artifacts")):
            raise ValueError("invalid registry shape")
    except (OSError, ValueError) as exc:
        return {"ok": False, "issues": [f"registry unavailable or invalid: {exc}"], "worktrees": [], "artifacts": []}
    records = data["worktrees"]
    live = {row["worktree"]: row for row in rows[1:]}
    for name in sorted(live.keys() | records.keys()):
        row, record = live.get(name), records.get(name)
        if not isinstance(record, dict):
            issues.append(f"{name}: unregistered or invalid record")
            continue
        for field in ("owner", "purpose", "branch", "head", "next_action"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                issues.append(f"{name}: missing {field}")
        state = record.get("state")
        if state not in ("active", "blocked", "ready_to_retire", "archived"):
            issues.append(f"{name}: invalid state")
        if state == "blocked" and (not isinstance(record.get("reason"), str) or not record["reason"].strip()):
            issues.append(f"{name}: blocked without reason")
        if not Path(name).is_absolute():
            issues.append(f"{name}: path is not absolute")
        if row:
            branch = row.get("branch", "").removeprefix("refs/heads/")
            if branch != record.get("branch") or row.get("HEAD") != record.get("head"):
                issues.append(f"{name}: stale or unknown branch/head")
            if state in ("ready_to_retire", "archived"):
                issues.append(f"{name}: {state} worktree still live")
        elif state in ("active", "blocked"):
            issues.append(f"{name}: expected worktree missing")
        pr = record.get("pr")
        if "pr" not in record or (pr is not None and (type(pr) is not int or pr <= 0)):
            issues.append(f"{name}: invalid or missing pr")
        elif github and pr is not None:
            raw = command(["gh", "pr", "view", str(pr), "--json", "state,headRefOid,headRefName"], repo)
            try:
                info = json.loads(raw) if raw else None
                if not isinstance(info, dict) or any(not info.get(k) for k in ("state", "headRefOid", "headRefName")):
                    raise ValueError("incomplete PR evidence")
                if info["headRefOid"] != record.get("head") or info["headRefName"] != record.get("branch"):
                    issues.append(f"{name}: stale PR branch/head")
                if info["state"] not in ("OPEN", "MERGED", "CLOSED"):
                    raise ValueError("unknown PR state")
                if info["state"] != "OPEN" and state == "active":
                    issues.append(f"{name}: completed PR requires closeout")
            except (ValueError, TypeError):
                issues.append(f"{name}: GitHub evidence unavailable or invalid")
    for name, record in data["artifacts"].items():
        if not isinstance(record, dict):
            issues.append(f"{name}: invalid artifact record")
            continue
        for field in ("owner", "purpose", "next_action"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                issues.append(f"{name}: missing artifact {field}")
        if record.get("retention") not in ("retain", "archive", "discard"):
            issues.append(f"{name}: invalid artifact retention")
    return {"ok": not issues, "issues": issues, "worktrees": sorted(live), "artifacts": sorted(data["artifacts"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--github", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audit(args.repo, args.registry, args.github)
    print(json.dumps(report, indent=2))
    return int(args.check and not report["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
