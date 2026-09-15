"""Tests for dispatch_388 backfill integration."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quality import dispatch_388_pilot as pilot


def _mock_run(returncode: int, stdout: str = "", stderr: str = ""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def test_dispatch_backfill_happy_path_runs_pipeline_and_push(tmp_path):
    module_path = "src/content/docs/k8s/cka/module-1.md"
    module_slug = pilot.module_slug_for_pipeline(module_path)

    with patch("scripts.quality.dispatch_388_pilot.subprocess.run", side_effect=[
        _mock_run(0, stdout="Already up to date."),
        _mock_run(0, stdout=f"[ok]    {module_slug}: deadbeef12"),
        _mock_run(0, stdout="To github.com:repo.git"),
    ]) as mock_run, patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        assert pilot.dispatch_backfill("my-slug", module_path)

    events = [c.args[0]["event"] for c in mock_log.call_args_list]
    assert "backfill_start" in events
    assert "backfill_done" in events
    done = next(c.args[0] for c in mock_log.call_args_list if c.args[0]["event"] == "backfill_done")
    assert done["slug"] == "my-slug"
    assert done["sha"] == "deadbeef12"
    assert mock_run.call_args_list[1].args[0] == [
        str(pilot.VENV_PYTHON),
        "-m", "scripts.quality.pipeline", "backfill-pending", "--module", module_slug,
    ]
    assert mock_run.call_args_list[2].args[0] == ["git", "push", "origin", "main"]


def test_dispatch_backfill_pull_failure_skips_backfill_and_push():
    module_path = "src/content/docs/k8s/cka/module-3.md"
    with patch("scripts.quality.dispatch_388_pilot.subprocess.run", side_effect=[
        _mock_run(1, stderr="network down"),
    ]) as mock_run, patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        assert pilot.dispatch_backfill("my-slug", module_path) is False

    events = [c.args[0]["event"] for c in mock_log.call_args_list]
    assert events == ["backfill_start", "backfill_failed"]
    failure = next(c.args[0] for c in mock_log.call_args_list if c.args[0]["event"] == "backfill_failed")
    assert failure["slug"] == "my-slug"
    assert failure["reason"] == "pull_failed"
    assert mock_run.call_count == 1


def test_dispatch_backfill_noop_skips_push(tmp_path):
    module_path = "src/content/docs/k8s/cka/module-4.md"
    with patch("scripts.quality.dispatch_388_pilot.subprocess.run", side_effect=[
        _mock_run(0, stdout="Already up to date."),
        _mock_run(0, stdout="[no-op]  module: nothing to inject"),
    ]) as mock_run, patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        assert pilot.dispatch_backfill("my-slug", module_path)

    events = [c.args[0]["event"] for c in mock_log.call_args_list]
    assert events == ["backfill_start", "backfill_skipped_noop"]
    assert not any(c.args[0]["event"] == "backfill_done" for c in mock_log.call_args_list)
    assert mock_run.call_count == 2


def test_dispatch_backfill_push_failure_logs_push_failed():
    module_path = "src/content/docs/k8s/cka/module-5.md"
    module_slug = pilot.module_slug_for_pipeline(module_path)
    with patch("scripts.quality.dispatch_388_pilot.subprocess.run", side_effect=[
        _mock_run(0, stdout="Already up to date."),
        _mock_run(0, stdout=f"[ok]    {module_slug}: deadbeef12"),
        _mock_run(1, stderr="push failed"),
    ]) as mock_run, patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        assert pilot.dispatch_backfill("my-slug", module_path) is False

    events = [call.args[0]["event"] for call in mock_log.call_args_list]
    assert events == ["backfill_start", "push_failed"]
    push_fail = next(
        call.args[0]
        for call in mock_log.call_args_list
        if call.args[0]["event"] == "push_failed"
    )
    assert push_fail["slug"] == "my-slug"
    assert push_fail["reason"] == "push_failed"
    assert mock_run.call_count == 3


def test_dispatch_backfill_backfill_failure_logs_and_continues():
    module_path = "src/content/docs/k8s/cka/module-2.md"
    with patch("scripts.quality.dispatch_388_pilot.subprocess.run", side_effect=[
        _mock_run(0, stdout="Already up to date."),
        _mock_run(1, stderr="pipeline failed"),
    ]) as _, patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        assert pilot.dispatch_backfill("my-slug", module_path) is False

    events = [c.args[0]["event"] for c in mock_log.call_args_list]
    assert "backfill_failed" in events
    failed = next(c.args[0] for c in mock_log.call_args_list if c.args[0]["event"] == "backfill_failed")
    assert failed["slug"] == "my-slug"
    assert failed["reason"] == "pipeline_failed"


def test_main_approve_holds_merge_and_backfill_for_all_queued_items(tmp_path, capsys):
    queue = tmp_path / "queue.txt"
    queue.write_text(
        "src/content/docs/k8s/cka/module-1.md\n"
        "src/content/docs/k8s/cka/module-2.md"
    )
    codex_result = MagicMock(ok=True, response="Opened PR: https://github.com/org/repo/pull/42")
    reviewer = MagicMock(return_value=("VERDICT: APPROVE", "APPROVE"))
    for name in ("module-1.md", "module-2.md"):
        module = tmp_path / "src/content/docs/k8s/cka" / name
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text("---\ncitations_verified: true\nrevision_pending: false\n---\nDraft\n")

    with patch.object(pilot, "REPO", tmp_path), \
         patch.object(pilot, "PILOT_FILE", queue), \
         patch.object(pilot, "LOG", tmp_path / "pilot.jsonl"), \
         patch.object(pilot, "invoke", side_effect=AssertionError("unexpected provider call")), \
         patch.object(pilot.subprocess, "run", side_effect=AssertionError("unexpected subprocess")), \
         patch("scripts.quality.dispatch_388_pilot.make_worktree", return_value=tmp_path), \
         patch("scripts.quality.dispatch_388_pilot.dispatch_codex", return_value=codex_result), \
         patch("scripts.quality.dispatch_388_pilot.build_reviewer_cascade", return_value=[("claude", reviewer)]), \
         patch("scripts.quality.dispatch_388_pilot.merge_pr", return_value="abc123") as mock_merge, \
         patch("scripts.quality.dispatch_388_pilot.dispatch_backfill", return_value=True) as mock_backfill, \
         patch("scripts.quality.dispatch_388_pilot.post_review_comment") as mock_post_review, \
         patch("scripts.quality.dispatch_388_pilot.time.sleep"), \
         patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        rc = pilot.main(["--input", str(queue)])

    assert rc == 0
    assert reviewer.call_count == 2
    assert mock_post_review.call_count == 2
    mock_merge.assert_not_called()
    mock_backfill.assert_not_called()
    events = [c.args[0]["event"] for c in mock_log.call_args_list]
    assert events.count("source_acceptance_unverified") == 2
    assert "merged" not in events
    held = [c.args[0] for c in mock_log.call_args_list if c.args[0]["event"] == "source_acceptance_unverified"]
    assert all(item["source_acceptance"]["accepted"] is False for item in held)
    assert capsys.readouterr().out.count("[source_acceptance_unverified]") == 2


def test_recheck_module_source_acceptance_rejects_stale_pr_head(tmp_path):
    import json
    from scripts.quality.source_acceptance import _digest
    from tests.test_source_acceptance import _valid

    module_path = "src/content/docs/k8s/cka/module-1.md"
    page = tmp_path / module_path
    page.parent.mkdir(parents=True)
    reviewed = b"---\ncitations_verified: true\n---\nreviewed\n"
    page.write_bytes(reviewed)
    seed = b'{"claims":[{"claim_id":"C001"}]}'
    (tmp_path / "docs/citation-seeds").mkdir(parents=True)
    (tmp_path / "docs/citation-seeds/k8s-cka-module-1.json").write_bytes(seed)
    ok = _valid(page_digest=_digest(reviewed), seed_digest=_digest(seed))
    ledger = tmp_path / "docs/content-upgrade/evidence.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"pages": [{"path": "k8s/cka/module-1.md", "source_acceptance": ok}]}))
    assert pilot.recheck_module_source_acceptance(tmp_path, module_path)["accepted"]
    page.write_bytes(reviewed + b"late head\n")
    stale = pilot.recheck_module_source_acceptance(tmp_path, module_path)
    assert stale["accepted"] is False
    assert "page_digest_stale" in stale["reasons"]


@pytest.mark.parametrize(
    ("verdict", "expected_event"),
    [
        ("APPROVE_WITH_NITS", "merge_held_nits"),
        ("NEEDS CHANGES", "merge_held"),
    ],
)
def test_main_nonapprove_verdicts_remain_held(tmp_path, verdict, expected_event):
    queue = tmp_path / "queue.txt"
    queue.write_text("src/content/docs/k8s/cka/module-1.md")
    codex_result = MagicMock(ok=True, response="Opened PR: https://github.com/org/repo/pull/42")
    reviewer = MagicMock(return_value=(f"VERDICT: {verdict}", verdict))

    with patch.object(pilot, "invoke", side_effect=AssertionError("unexpected provider call")), \
         patch.object(pilot.subprocess, "run", side_effect=AssertionError("unexpected subprocess")), \
         patch("scripts.quality.dispatch_388_pilot.make_worktree", return_value=tmp_path), \
         patch("scripts.quality.dispatch_388_pilot.dispatch_codex", return_value=codex_result), \
         patch("scripts.quality.dispatch_388_pilot.build_reviewer_cascade", return_value=[("claude", reviewer)]), \
         patch("scripts.quality.dispatch_388_pilot.merge_pr") as mock_merge, \
         patch("scripts.quality.dispatch_388_pilot.dispatch_backfill") as mock_backfill, \
         patch("scripts.quality.dispatch_388_pilot.post_review_comment"), \
         patch("scripts.quality.dispatch_388_pilot.time.sleep"), \
         patch("scripts.quality.dispatch_388_pilot.log") as mock_log:
        assert pilot.main(["--input", str(queue)]) == 0

    mock_merge.assert_not_called()
    mock_backfill.assert_not_called()
    events = [c.args[0]["event"] for c in mock_log.call_args_list]
    assert expected_event in events


def test_slugify_uses_repo_relative_path_not_stem():
    module_cka = "src/content/docs/k8s/cka/module-5.1-image-security.md"
    module_cks = "src/content/docs/k8s/cks/module-5.1-image-security.md"

    assert pilot.module_slug_for_pipeline(module_cka) == "k8s-cka-module-5.1-image-security"
    assert pilot.module_slug_for_pipeline(module_cks) == "k8s-cks-module-5.1-image-security"
    assert pilot.module_slug_for_pipeline(module_cka) != pilot.module_slug_for_pipeline(module_cks)


def test_make_worktree_rejects_existing_worktree_for_different_module(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "REPO", tmp_path)
    slug = "k8s-cka-module-1"
    worktree = tmp_path / ".worktrees" / f"codex-388-pilot-{slug}"
    worktree.mkdir(parents=True)
    (worktree / ".module_path").write_text("src/content/docs/k8s/cks/module-1.md", encoding="utf-8")

    with patch("scripts.quality.dispatch_388_pilot.subprocess.run"), pytest.raises(
        RuntimeError, match="existing worktree"
    ):
        pilot.make_worktree(slug, "src/content/docs/k8s/cka/module-1.md")


def test_make_worktree_reuses_existing_worktree_for_same_module_and_records_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "REPO", tmp_path)
    slug = "k8s-cka-module-1"
    worktree = tmp_path / ".worktrees" / f"codex-388-pilot-{slug}"
    worktree.mkdir(parents=True)
    expected_module_path = "src/content/docs/k8s/cka/module-1.md"
    (worktree / ".module_path").write_text(expected_module_path, encoding="utf-8")

    with patch("scripts.quality.dispatch_388_pilot.subprocess.run") as mock_run:
        reused = pilot.make_worktree(slug, expected_module_path)

    assert reused == worktree
    assert (worktree / ".module_path").read_text(encoding="utf-8").strip() == expected_module_path
    assert mock_run.call_count == 0


def test_make_worktree_writes_module_path_marker_for_new_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "REPO", tmp_path)
    slug = "k8s-cka-module-2"
    module_path = "src/content/docs/k8s/cka/module-2.md"
    worktree = tmp_path / ".worktrees" / f"codex-388-pilot-{slug}"
    (tmp_path / ".worktrees").mkdir(parents=True, exist_ok=True)

    with patch(
        "scripts.quality.dispatch_388_pilot.subprocess.run",
        side_effect=[_mock_run(0), _mock_run(0)],
    ) as mock_run:
        result = pilot.make_worktree(slug, module_path)

    assert result == worktree
    assert (worktree / ".module_path").read_text(encoding="utf-8").strip() == module_path
    assert mock_run.call_count == 2


def test_dispatch_backfill_sha_regex_parses_ok_line():
    output = (
        "[no-op] k8s-cka-module-9: already clean\n"
        "[ok]    k8s-cka-module-8: deadbeef12\n"
        "[ok]    k8s-cka-module-9: c0ffee99"
    )
    match = re.search(r"^\[ok\]\s+k8s-cka-module-8:\s+([0-9a-f]+)", output, re.MULTILINE)
    assert match is not None
    assert match.group(1) == "deadbeef12"


@pytest.mark.parametrize(
    ("primary", "expected"),
    [
        ("claude", ["claude", "agy", "qwen"]),
        ("qwen", ["qwen", "agy", "claude"]),
        ("deepseek", ["deepseek", "claude", "qwen"]),
        # gemini-cli is retired (#2125); a legacy "gemini" primary falls to the
        # default cascade, which is now the agy (Google) lane → claude → qwen.
        ("gemini", ["agy", "claude", "qwen"]),
        # agy is the Google lane (replaced gemini-cli, #2125) and a viable
        # primary reviewer; cascade falls to claude → qwen.
        ("agy", ["agy", "claude", "qwen"]),
    ],
)
def test_reviewer_cascade_selection(primary: str, expected: list[str]) -> None:
    cascade = pilot.build_reviewer_cascade(primary)
    assert [name for name, _fn in cascade] == expected


def test_dispatch_agy_review_uses_danger_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agy adapter requires mode='danger' in headless dispatch — verify
    dispatch_agy_review passes it and uses the correct agent_name."""
    from types import SimpleNamespace

    calls: list[dict] = []

    def fake_invoke(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            ok=True,
            response="VERDICT: APPROVE\nlooks good",
            stderr_excerpt=None,
        )

    monkeypatch.setattr(pilot, "invoke", fake_invoke)
    monkeypatch.setattr(pilot, "log", lambda _event: None)
    monkeypatch.setattr(pilot, "cross_family_review_prompt", lambda *_a, **_kw: "test prompt")

    text, verdict = pilot.dispatch_agy_review(pr_num=1234, module_path="x.md", slug="agy-test")

    assert verdict == "APPROVE"
    assert text == "VERDICT: APPROVE\nlooks good"
    assert len(calls) == 1
    assert calls[0]["agent_name"] == "agy"
    assert calls[0]["mode"] == "danger"
    assert calls[0]["entrypoint"] == "dispatch"
    assert "model" not in calls[0]  # agy uses TUI-picker, no model= arg


@pytest.mark.parametrize(
    ("ok", "response", "expected_verdict", "expected_text"),
    [
        # Quota-exhausted: invoke returns ok=False with empty body.
        (False, "", "UNCLEAR", ""),
        # OAuth-expired: invoke returns ok=True but body is the auth-prompt
        # URL plus a timed-out message; no VERDICT line present.
        (
            True,
            (
                "Authentication required. Please visit the URL to log in: "
                "https://accounts.google.com/o/oauth2/auth?...\n"
                "Error: authentication timed out."
            ),
            "UNCLEAR",
            (
                "Authentication required. Please visit the URL to log in: "
                "https://accounts.google.com/o/oauth2/auth?...\n"
                "Error: authentication timed out."
            ),
        ),
    ],
)
def test_dispatch_agy_review_failure_paths(
    monkeypatch: pytest.MonkeyPatch,
    ok: bool,
    response: str,
    expected_verdict: str,
    expected_text: str,
) -> None:
    """Sonnet PR #1395 review: confirm the two documented agy failure
    shapes (quota-exhaust + OAuth-expiry) surface as UNCLEAR — not ERROR —
    so the cascade falls through transparently."""
    from types import SimpleNamespace

    def fake_invoke(**_kwargs):
        return SimpleNamespace(ok=ok, response=response, stderr_excerpt=None)

    monkeypatch.setattr(pilot, "invoke", fake_invoke)
    monkeypatch.setattr(pilot, "log", lambda _event: None)
    monkeypatch.setattr(pilot, "cross_family_review_prompt", lambda *_a, **_kw: "test prompt")

    text, verdict = pilot.dispatch_agy_review(pr_num=1234, module_path="x.md", slug="agy-fail")

    assert verdict == expected_verdict
    assert text == expected_text


def test_dispatch_agy_review_invoke_exception_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exception inside invoke() should bubble up as (None, 'ERROR') —
    distinct from quota-exhaust (which is ok=False with empty body)."""

    def fake_invoke(**_kwargs):
        raise RuntimeError("transport failure")

    monkeypatch.setattr(pilot, "invoke", fake_invoke)
    monkeypatch.setattr(pilot, "log", lambda _event: None)
    monkeypatch.setattr(pilot, "cross_family_review_prompt", lambda *_a, **_kw: "test prompt")

    text, verdict = pilot.dispatch_agy_review(pr_num=1234, module_path="x.md", slug="agy-exc")

    assert text is None
    assert verdict == "ERROR"
