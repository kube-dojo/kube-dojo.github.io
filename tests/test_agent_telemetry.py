"""Unit tests for agent_telemetry aggregation + harness/model rollup (#1860)."""
from __future__ import annotations

import json

from agent_telemetry import _agent_stats, build_agent_telemetry, harness_of


def test_agent_stats_joins_dispatches_and_outcomes() -> None:
    dispatches = [
        {"task_id": "d1", "agent": "deepseek", "task_class": "review", "ok": True,
         "response_chars": 5000, "elapsed_s": 200.0},
        {"task_id": "d2", "agent": "deepseek", "task_class": "review", "ok": True,
         "response_chars": 6000, "elapsed_s": 100.0},
        {"task_id": "d3", "agent": "deepseek", "task_class": "draft", "ok": False,
         "response_chars": 0, "elapsed_s": 10.0},
        {"task_id": "c1", "agent": "codex", "task_class": "review", "ok": True,
         "response_chars": 3000, "elapsed_s": 300.0},
    ]
    outcomes = [
        {"task_id": "d1", "agent": "deepseek", "outcome": "fabrication"},
        {"task_id": "d2", "agent": "deepseek", "outcome": "clean"},
        {"task_id": "c1", "agent": "codex", "outcome": "clean"},
    ]
    stats = _agent_stats(dispatches, outcomes)

    ds = stats["deepseek"]
    assert ds["dispatches"] == 3
    assert ds["empty_or_failed"] == 1          # d3 (ok False + 0 chars)
    assert ds["annotated"] == 2
    assert ds["outcomes"]["fabrication"] == 1
    assert ds["outcomes"]["clean"] == 1
    assert ds["by_class"]["review"] == 2
    assert ds["by_class"]["draft"] == 1
    assert round(ds["elapsed_total"] / ds["elapsed_n"], 1) == 103.3

    cx = stats["codex"]
    assert cx["dispatches"] == 1
    assert cx["empty_or_failed"] == 0
    assert cx["outcomes"]["clean"] == 1


def test_agent_stats_handles_empty() -> None:
    assert _agent_stats([], []) == {}


def test_harness_of_mapping() -> None:
    assert harness_of("deepseek") == "opencode"  # deepseek-direct via opencode
    assert harness_of("qwen") == "hermes"         # residual hermes transport
    assert harness_of("opencode") == "opencode"
    assert harness_of("codex") == "codex"
    assert harness_of("agy") == "antigravity"
    assert harness_of("grok") == "grok-cli"
    assert harness_of("somethingnew") == "somethingnew"  # unknown lane == own harness
    assert harness_of(None) == "?"


def test_build_rolls_up_by_harness_and_model(tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    # deepseek → opencode harness; residual hermes lane stays hermes; cursor own
    dispatches = [
        {"task_id": "a", "agent": "deepseek", "model": "deepseek-flash", "ok": True,
         "response_chars": 9, "elapsed_s": 100, "task_class": "review"},
        {"task_id": "b", "agent": "hermes", "model": "claude-sonnet-4-6", "ok": True,
         "response_chars": 9, "elapsed_s": 50, "task_class": "review"},
        {"task_id": "c", "agent": "cursor", "model": "auto", "ok": True,
         "response_chars": 9, "elapsed_s": 30, "task_class": "draft"},
    ]
    outcomes = [{"task_id": "a", "agent": "deepseek", "model": "deepseek-flash",
                 "outcome": "fabrication"}]
    (logs / "smart_dispatch.jsonl").write_text(
        "\n".join(json.dumps(d) for d in dispatches), encoding="utf-8")
    (logs / "agent_outcomes.jsonl").write_text(
        "\n".join(json.dumps(o) for o in outcomes), encoding="utf-8")

    data = build_agent_telemetry(tmp_path)
    assert data["dispatch_total"] == 3
    by_h = {h["harness"]: h for h in data["by_harness"]}
    assert by_h["opencode"]["dispatches"] == 1
    assert by_h["opencode"]["annotated"] == 1
    assert by_h["opencode"]["miss_pct"] == 100.0
    assert by_h["hermes"]["dispatches"] == 1
    assert by_h["cursor"]["dispatches"] == 1
    lanes = {x["lane"]: x for x in data["lanes"]}
    assert lanes["deepseek"]["harness"] == "opencode"
    assert lanes["hermes"]["harness"] == "hermes"
    by_m = {m["model"]: m for m in data["by_model"]}
    assert by_m["deepseek-flash"]["dispatches"] == 1
    assert by_m["claude-sonnet-4-6"]["dispatches"] == 1
