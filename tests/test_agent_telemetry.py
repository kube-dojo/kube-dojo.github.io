"""Unit tests for the module-build telemetry CLI (scripts/agent_telemetry.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import agent_telemetry


def test_parse_participant_extracts_typed_fields() -> None:
    parsed = agent_telemetry._parse_participant(
        "role=author,agent=codex,model=gpt-6.2-sol,calls=2,prompt_tokens=1000,"
        "response_tokens=200,total_tokens=1200,cost_usd_est=0.05,token_source=actual"
    )
    assert parsed == {
        "role": "author",
        "agent": "codex",
        "model": "gpt-6.2-sol",
        "calls": 2,
        "prompt_tokens": 1000,
        "response_tokens": 200,
        "total_tokens": 1200,
        "cost_usd_est": 0.05,
        "token_source": "actual",
    }


def test_parse_participant_requires_role_and_agent() -> None:
    with pytest.raises(ValueError, match="role= and agent="):
        agent_telemetry._parse_participant("agent=codex")
    with pytest.raises(ValueError, match="role= and agent="):
        agent_telemetry._parse_participant("role=author")


def test_record_build_cli_persists_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import telemetry_store

    monkeypatch.setattr(agent_telemetry, "PRIMARY_REPO", tmp_path)
    monkeypatch.setattr(telemetry_store, "_db_path_override", None)

    rc = agent_telemetry.main(
        [
            "record-build",
            "--run-id",
            "mbt-test-1",
            "--track",
            "k8s/cka",
            "--slug",
            "module-1.1",
            "--source",
            "orchestrator",
            "--no-swarm",
            "--swarm-note",
            "solo expand",
            "--participant",
            "role=author,agent=codex,model=gpt-6.2-sol,total_tokens=1500,token_source=estimated",
        ]
    )
    assert rc == 0

    runs = telemetry_store.query_runs(tmp_path, track="k8s/cka", slug="module-1.1")
    assert len(runs) == 1
    assert runs[0]["run_id"] == "mbt-test-1"
    assert runs[0]["totals"]["total_tokens"] == 1500


def test_record_build_cli_rejects_invalid_participant_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import telemetry_store

    monkeypatch.setattr(agent_telemetry, "PRIMARY_REPO", tmp_path)
    monkeypatch.setattr(telemetry_store, "_db_path_override", None)

    rc = agent_telemetry.main(
        [
            "record-build",
            "--track",
            "k8s/cka",
            "--slug",
            "module-1.1",
            "--source",
            "orchestrator",
            "--no-swarm",
            "--swarm-note",
            "solo expand",
            "--participant",
            "role=author,agent=codex,total_tokens=not-a-number",
        ]
    )
    assert rc == 2
    assert "error:" in capsys.readouterr().out
