"""Tests for per-module budget support in dispatch_388_pilot queue parsing."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quality import dispatch_388_pilot as pilot


@pytest.fixture(autouse=True)
def isolated_pilot(tmp_path, monkeypatch):
    """Mock current provider routes; guard invoke and subprocess.run/Popen."""
    reviewers = ("claude", "agy", "qwen", "deepseek")
    originals = {name: getattr(pilot, f"dispatch_{name}_review") for name in reviewers}
    originals["codex"] = pilot.dispatch_codex
    for name in ("make_worktree", "post_review_comment", "dispatch_backfill"):
        originals[name] = getattr(pilot, name)

    def forbidden(*args, **kwargs):
        # pytest.fail escapes the current wrappers' except Exception handlers.
        pytest.fail("unexpected provider or process dispatch", pytrace=False)

    monkeypatch.setattr(pilot, "invoke", forbidden)
    monkeypatch.setattr(pilot.subprocess, "run", forbidden)
    monkeypatch.setattr(pilot.subprocess, "Popen", forbidden)
    monkeypatch.delenv("KUBEDOJO_388_PRIMARY_REVIEWER", raising=False)
    monkeypatch.setattr(pilot, "REPO", tmp_path)
    monkeypatch.setattr(pilot, "PRIMARY_REPO", tmp_path)
    monkeypatch.setattr(pilot, "PILOT_FILE", tmp_path / "scripts/quality/pilot-2026-05-02.txt")
    monkeypatch.setattr(pilot, "LOG", tmp_path / "dispatch.log")
    for name in ("BRIEF", "WRITER_BRIEF"):
        prompt = tmp_path / f"{name}.md"
        prompt.write_text("Test brief: {{BODY_WORDS_TARGET}}\n", encoding="utf-8")
        monkeypatch.setattr(pilot, name, prompt)
    codex = MagicMock(return_value=MagicMock(ok=True, response="Opened PR: https://github.com/org/repo/pull/1"))
    monkeypatch.setattr(pilot, "dispatch_codex", codex)
    mocks = {name: MagicMock(return_value=("VERDICT: APPROVE", "APPROVE")) for name in reviewers}
    for name, mock in mocks.items():
        monkeypatch.setattr(pilot, f"dispatch_{name}_review", mock)
    monkeypatch.setattr(pilot, "merge_pr", MagicMock(return_value="abc123"))
    monkeypatch.setattr(pilot, "dispatch_backfill", MagicMock(return_value=True))
    monkeypatch.setattr(pilot, "make_worktree", MagicMock(return_value=tmp_path))
    monkeypatch.setattr(pilot, "post_review_comment", MagicMock())
    source_recheck = MagicMock(return_value={"status": "unverified"})
    monkeypatch.setattr(pilot, "recheck_module_source_acceptance", source_recheck)
    monkeypatch.setattr(pilot.time, "sleep", MagicMock())
    log = MagicMock()
    monkeypatch.setattr(pilot, "log", log)
    return {
        "reviewers": mocks, "codex": codex, "log": log,
        "originals": originals, "source_recheck": source_recheck,
    }


@pytest.fixture
def queue_file(tmp_path):
    queue = tmp_path / "pilot.yaml"
    queue.write_text(
        """queue:
  - path: src/content/docs/ai/module-a.md
    budget: 3000
  - path: src/content/docs/cloud/module-b.md
""",
        encoding="utf-8",
    )
    return queue


def test_yaml_queue_dispatch_writes_budget_sidecar_and_defaults_to_5000(
    tmp_path, isolated_pilot, queue_file,
) -> None:
    rc = pilot.main(["--input", str(queue_file), "--log", str(tmp_path / "dispatch.log")])

    assert rc == 0
    budget_path = tmp_path / ".pipeline" / "budgets" / "ai__module-a.md.json"
    sidecars = list((tmp_path / ".pipeline" / "budgets").glob("*.json"))
    assert len(sidecars) == 1
    data = json.loads(budget_path.read_text(encoding="utf-8"))
    assert data["body_words_min"] == 3000
    assert data["source_module"] == "src/content/docs/ai/module-a.md"
    assert any(
        call.args[0]["event"] == "budget_sidecar_written"
        for call in isolated_pilot["log"].call_args_list
    )
    assert isolated_pilot["codex"].call_args_list[0].args[3] == 3000
    assert isolated_pilot["codex"].call_args_list[1].args[3] == 5000
    assert isolated_pilot["source_recheck"].call_args_list == [
        call(tmp_path, "src/content/docs/ai/module-a.md"),
        call(tmp_path, "src/content/docs/cloud/module-b.md"),
    ]
    assert sum(
        call.args[0]["event"] == "source_acceptance_unverified"
        for call in isolated_pilot["log"].call_args_list
    ) == 2
    assert isolated_pilot["reviewers"]["claude"].call_count == 2
    for name in ("agy", "qwen", "deepseek"):
        isolated_pilot["reviewers"][name].assert_not_called()


@pytest.mark.parametrize(
    ("primary", "expected"),
    [
        (None, ["claude", "agy", "qwen"]),
        ("claude", ["claude", "agy", "qwen"]),
        ("agy", ["agy", "claude", "qwen"]),
        ("qwen", ["qwen", "agy", "claude"]),
        ("deepseek", ["deepseek", "claude", "qwen"]),
        ("unknown", ["agy", "claude", "qwen"]),
    ],
)
def test_yaml_queue_reviewer_fallbacks_are_isolated(
    tmp_path, monkeypatch, isolated_pilot, queue_file, primary, expected,
) -> None:
    if primary is not None:
        monkeypatch.setenv("KUBEDOJO_388_PRIMARY_REVIEWER", primary)
    manager = MagicMock()
    for name, mock in isolated_pilot["reviewers"].items():
        manager.attach_mock(mock, name)
        mock.return_value = (None, "ERROR")
    isolated_pilot["reviewers"][expected[-1]].return_value = ("VERDICT: APPROVE", "APPROVE")

    assert pilot.main(["--input", str(queue_file), "--log", str(tmp_path / "dispatch.log")]) == 0
    assert [call[0] for call in manager.mock_calls] == expected * 2
    assert isolated_pilot["codex"].call_count == 2


@pytest.mark.parametrize("name", ["codex", "claude", "agy", "qwen", "deepseek"])
def test_real_provider_wrappers_stop_at_invoke_guard(tmp_path, isolated_pilot, name) -> None:
    real_dispatch = isolated_pilot["originals"][name]
    with pytest.raises(pytest.fail.Exception, match="unexpected provider or process dispatch"):
        if name == "codex":
            real_dispatch("src/content/docs/ai/module-a.md", tmp_path, "module-a", 3000)
        else:
            real_dispatch(1, "src/content/docs/ai/module-a.md", "module-a")


@pytest.mark.parametrize("name", ["make_worktree", "post_review_comment", "dispatch_backfill"])
def test_real_process_paths_stop_at_subprocess_guard(isolated_pilot, name) -> None:
    real_call = isolated_pilot["originals"][name]
    with pytest.raises(pytest.fail.Exception, match="unexpected provider or process dispatch"):
        if name == "post_review_comment":
            real_call(1, "test review")
        else:
            real_call("module-a", "src/content/docs/ai/module-a.md")
