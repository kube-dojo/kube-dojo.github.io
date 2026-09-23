"""Tests for the read-only shared operator Codex reset reserve."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.fleet.reset_reserve import (
    SCHEMA_VERSION,
    codex_reset_reserve_eligible,
    load_reset_reserve,
    unavailable_reserve,
)


def _write_assertion(root: Path, value: object) -> Path:
    path = root / "batch_state" / "routing_budget" / "operator_reset_reserve.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _assertion(*, confirmed_at: str = "2026-09-23T10:00:00Z", expires_at: str = "2026-09-24T10:00:00Z") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "codex",
        "remaining_resets": 2,
        "confirmed_at": confirmed_at,
        "expires_at": expires_at,
    }


def test_missing_and_malformed_assertions_fail_closed(tmp_path):
    assert load_reset_reserve(tmp_path, now=datetime(2026, 9, 23, 12, tzinfo=UTC)) == unavailable_reserve()
    assert unavailable_reserve()["remaining_resets"] is None
    path = _write_assertion(tmp_path, {**_assertion(), "operator": "private"})
    assert load_reset_reserve(tmp_path, now=datetime(2026, 9, 23, 12, tzinfo=UTC)) == unavailable_reserve()
    path.write_text("{broken", encoding="utf-8")
    assert load_reset_reserve(tmp_path, now=datetime(2026, 9, 23, 12, tzinfo=UTC)) == unavailable_reserve()


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "unknown"},
        {"provider": "claude"},
        {"remaining_resets": 0},
        {"remaining_resets": True},
        {"confirmed_at": "2026-09-23T10:00:00"},
        {"confirmed_at": "2026-09-23T13:00:00Z"},
        {"expires_at": "2026-09-24T10:00:01Z"},
    ],
)
def test_invalid_expired_or_overlong_assertions_fail_closed(tmp_path, changes):
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    _write_assertion(tmp_path, {**_assertion(), **changes})
    assert load_reset_reserve(tmp_path, now=now) == unavailable_reserve()


def test_valid_assertion_is_sanitized_without_mutation(tmp_path):
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    path = _write_assertion(tmp_path, _assertion())
    original = path.read_bytes()
    reserve = load_reset_reserve(tmp_path, now=now)
    assert reserve == {
        "available": True,
        "provider": "codex",
        "remaining_resets": 2,
        "confirmed_at": "2026-09-23T10:00:00Z",
        "expires_at": "2026-09-24T10:00:00Z",
    }
    assert path.read_bytes() == original


def test_assertion_is_shared_with_dispatch_worktree_and_expires_on_next_read(tmp_path):
    primary = tmp_path / "primary"
    worktree = primary / ".worktrees" / "dispatch" / "codex" / "task"
    git_worktree_dir = primary / ".git" / "worktrees" / "task"
    git_worktree_dir.mkdir(parents=True)
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
    _write_assertion(primary, _assertion())

    assert load_reset_reserve(worktree, now=datetime(2026, 9, 23, 12, tzinfo=UTC))["remaining_resets"] == 2
    assert load_reset_reserve(worktree, now=datetime(2026, 9, 24, 10, tzinfo=UTC)) == unavailable_reserve()


def _eligible_codex() -> dict:
    return {
        "status": "hot",
        "eligible": True,
        "health": {"healthy": True},
        "freshness": "fresh",
        "age_s": 10,
        "codexbar": {
            "will_last_to_reset": False,
            "weekly_used_pct": 25.0,
            "windows": {"primary": {"remaining_pct": 12.0}},
        },
        "runtime": {
            "headroom_blocked": False,
            "rate_limited": 0,
            "last_rate_limited_at": None,
        },
    }


def _open_reserve() -> dict:
    return {
        "available": True,
        "remaining_resets": 1,
        "confirmed_at": "2026-09-23T10:00:00Z",
        "expires_at": "2026-09-24T10:00:00Z",
    }


_NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)


def test_eligibility_requires_provider_runtime_and_health_headroom():
    reserve = _open_reserve()
    assert codex_reset_reserve_eligible(reserve, _eligible_codex(), now=_NOW)
    for mutate in (
        lambda info: info["runtime"].update(headroom_blocked=True),
        lambda info: info["runtime"].update(rate_limited=1),
        lambda info: info["runtime"].update(summary_error="unavailable"),
        lambda info: info["health"].update(healthy=False),
        lambda info: info.update(eligible=False),
        lambda info: info.update(freshness="stale_last_good"),
        lambda info: info["codexbar"]["windows"]["primary"].update(remaining_pct=0),
        lambda info: info["codexbar"]["windows"].update(secondary={"remaining_pct": 0}),
        lambda info: info["codexbar"]["windows"].update(secondary={"used_pct": 100}),
        lambda info: info["codexbar"].update(weekly_used_pct=100, weekly_remaining_pct=None),
        lambda info: info["codexbar"].update(weekly_used_pct=None, weekly_remaining_pct=None),
        lambda info: info.update(
            notebook_report={
                "source": "notebook-report",
                "freshness": "fresh",
                "age_s": 5,
                "weekly_used_pct": 100,
                "weekly_remaining_pct": 0,
            }
        ),
        lambda info: info.update(
            notebook_report={
                "source": "notebook-report",
                "freshness": "stale_last_good",
                "age_s": 901,
                "weekly_used_pct": 20,
                "weekly_remaining_pct": 80,
            }
        ),
    ):
        info = _eligible_codex()
        mutate(info)
        assert not codex_reset_reserve_eligible(reserve, info, now=_NOW)


def test_fresh_notebook_weekly_report_can_supply_missing_codexbar_weekly_window():
    info = _eligible_codex()
    info["codexbar"]["weekly_used_pct"] = None
    info["notebook_report"] = {
        "source": "notebook-report",
        "freshness": "fresh",
        "age_s": 5,
        "weekly_used_pct": 40,
        "weekly_remaining_pct": 60,
    }
    assert codex_reset_reserve_eligible(_open_reserve(), info, now=_NOW)


def test_stale_routing_snapshot_cannot_use_reserve():
    assert not codex_reset_reserve_eligible(
        _open_reserve(),
        _eligible_codex(),
        now=_NOW,
        snapshot_stale=True,
    )


def test_expired_reserve_is_not_eligible_even_if_loaded_earlier():
    reserve = _open_reserve()
    reserve["expires_at"] = "2026-09-23T11:00:00Z"
    assert not codex_reset_reserve_eligible(reserve, _eligible_codex(), now=_NOW)


def test_stale_codexbar_is_not_hidden_by_a_fresh_snapshot():
    info = _eligible_codex()
    info["codexbar"]["freshness"] = "stale_last_good"
    info["codexbar"]["age_s"] = 901
    assert not codex_reset_reserve_eligible(_open_reserve(), info, now=_NOW)


def test_missing_eligible_flag_fails_closed():
    info = _eligible_codex()
    del info["eligible"]
    assert not codex_reset_reserve_eligible(_open_reserve(), info, now=_NOW)
