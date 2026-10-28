from __future__ import annotations

import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = runpy.run_path(str(ROOT / "scripts/check_incident_reuse.py"))
GATE = runpy.run_path(str(ROOT / "scripts/quality/incident_dedup_gate.py"))
OLD = "GitHub October 2018 split-brain"
NEW = "GitHub August 2021 MySQL degradation"
CANONICAL = "src/content/docs/prerequisites/git-deep-dive/module-2-advanced-merging.md"
OTHER = "src/content/docs/other/module.md"

EXCERPT = (
    "In its [October 2018 incident report](https://github.blog/news-insights/company-news/"
    "oct21-post-incident-analysis/), GitHub describes a 43-second network interruption "
    "followed by database failover, divergent writes across sites, and 24 hours and 11 "
    "minutes of degraded service. Recovery used backup restoration and replica "
    "synchronization; manual reconciliation of some writes was still in progress when "
    "the report was published. About 200,000 webhook payloads were dropped after their "
    "internal time-to-live expired. This illustrates the need to reconcile divergent "
    "state, but database replication is not a Git merge: its mechanisms and recovery "
    "constraints differ."
)


def scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, text: str) -> list[dict]:
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    scanner = CHECK["scan_for_violations"]
    monkeypatch.setitem(scanner.__globals__, "REPO", tmp_path)
    monkeypatch.setitem(scanner.__globals__, "SCOPE", tmp_path / "src/content/docs")
    return scanner()[0]


def test_actual_2018_excerpt_respects_its_canonical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert scan(tmp_path, monkeypatch, CANONICAL, EXCERPT) == []


def test_actual_2018_excerpt_is_detected_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    violations = scan(tmp_path, monkeypatch, OTHER, EXCERPT)
    assert {v["incident"] for v in violations} == {OLD}
    assert violations[0]["canonical"] == CANONICAL


@pytest.mark.parametrize("text", [
    "GitHub experienced degraded service during a database failover.",
    "Degraded service affected the database before GitHub recovered.",
])
def test_generic_degradation_is_not_a_specific_incident(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    assert scan(tmp_path, monkeypatch, OTHER, text) == []


@pytest.mark.parametrize("text", [
    "GitHub experienced an outage in August 2021.",
    "GitHub experienced a 77-minute outage.",
    "GitHub had a service discovery misconfiguration.",
    "The MySQL primary failed during the GitHub outage.",
    "The dashboards were down too during the GitHub incident.",
])
def test_2021_identifiers_still_trigger_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    violations = scan(tmp_path, monkeypatch, OTHER, text)
    gate = GATE["run_absolute_gate"]
    monkeypatch.setitem(gate.__globals__, "_run_check", lambda _root: violations)
    ok, result = gate(tmp_path)
    assert not ok
    assert ["duplicate", NEW, OTHER] in result["after"]


def test_absolute_gate_scans_canonical_and_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("audit_incident_reuse.py", "check_incident_reuse.py"):
        shutil.copy(ROOT / "scripts" / name, scripts / name)
    python = ROOT / ".venv/bin/python"
    if not python.exists():
        python = ROOT.parents[1] / ".venv/bin/python"
    monkeypatch.setenv("KUBEDOJO_INCIDENT_GATE_PYTHON", str(python))
    target = tmp_path / CANONICAL
    target.parent.mkdir(parents=True)
    target.write_text(EXCERPT, encoding="utf-8")
    gate = GATE["run_absolute_gate"]
    ok, result = gate(tmp_path)
    assert ok and result["after"] == []
    target.write_text(EXCERPT + "\nGitHub had an outage in August 2021.", encoding="utf-8")
    ok, result = gate(tmp_path)
    assert not ok
    assert result["after"] == [["duplicate", NEW, CANONICAL]]

