import importlib.util
import json
import subprocess
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("workspace_hygiene", Path(__file__).resolve().parents[1] / "scripts/ops/workspace_hygiene.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_lifecycle_audit(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    tree = str(tmp_path / "work")
    registry = tmp_path / "registry.json"
    rows = [{"worktree": str(repo)}, {"worktree": tree, "branch": "refs/heads/task", "HEAD": "abc"}]
    monkeypatch.setattr(audit, "inventory", lambda _: rows)
    calls = []
    evidence = {"state": "MERGED", "headRefName": "task", "headRefOid": "abc"}

    def command(args, cwd):
        calls.append(args)
        assert args == ["gh", "pr", "view", "42", "--json", "state,headRefOid,headRefName"]
        return json.dumps(evidence) if evidence else None

    monkeypatch.setattr(audit, "command", command)
    record = {"owner": "owner", "purpose": "task", "branch": "task", "head": "abc",
              "state": "active", "next_action": "close out", "pr": 42}
    data = {"worktrees": {}, "artifacts": {}}

    def check():
        registry.write_text(json.dumps(data))
        before = registry.read_bytes()
        result = audit.audit(repo, registry, github=True)
        assert registry.read_bytes() == before
        return result

    assert "unregistered" in check()["issues"][0]
    data["worktrees"][tree] = record
    record["owner"] = ""
    assert any("missing owner" in item for item in check()["issues"])
    record["owner"] = "owner"
    assert any("completed PR" in item for item in check()["issues"])
    record.update(state="blocked", reason="retain evidence")
    assert check()["ok"]
    record["state"] = "ready_to_retire"
    assert any("still live" in item for item in check()["issues"])
    record.update(state="active", head="wrong")
    assert any("stale" in item for item in check()["issues"])
    evidence.clear()
    assert any("GitHub evidence unavailable" in item for item in check()["issues"])
    data["artifacts"]["evidence"] = {"owner": "", "retention": "unknown"}
    assert any("artifact" in item for item in check()["issues"])
    assert calls


def test_cli_real_git_is_read_only(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout
    git("init", "-b", "main")
    (repo / "file").write_text("content")
    git("add", "file")
    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial")
    tree = tmp_path / "tree"
    git("worktree", "add", "-b", "task", str(tree), "main")
    head = git("rev-parse", "refs/heads/task").strip()
    registry = tmp_path / "registry.json"
    record = {"owner": "owner", "purpose": "task", "branch": "task", "head": head,
              "state": "active", "next_action": "finish", "pr": None}
    data = {"worktrees": {}, "artifacts": {}}
    command = [str(Path(sys.prefix).parent / ".venv/bin/python"), str(Path(audit.__file__)),
               "--repo", str(repo), "--registry", str(registry), "--check"]
    def run():
        registry.write_text(json.dumps(data))
        return subprocess.run(command, capture_output=True, text=True, check=False).returncode
    def snapshot():
        return (git("show-ref"), git("status", "--porcelain=v1"),
                git("worktree", "list", "--porcelain"), git("-C", str(tree), "status", "--porcelain=v1"))
    before = snapshot()
    assert run() == 1
    data["worktrees"][str(tree)] = record
    assert run() == 0
    record["state"] = "ready_to_retire"
    assert run() == 1
    assert snapshot() == before
