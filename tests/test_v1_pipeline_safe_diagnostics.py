from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import v1_pipeline as pipeline
from checks.structural import CheckResult

builtins.print = pipeline._original_print

MESSAGE = "SYNTHETIC_PRIVATE_MESSAGE_3479"
UNKNOWN_CHECK = "FRONTMATTER_SYNTHETIC_PRIVATE_CHECK_3479"
UNKNOWN_SEVERITY = "ERROR_SYNTHETIC_PRIVATE_SEVERITY_3479"
CONTENT = "---\ntitle: Synthetic test\n---\n# Test\n"


@pytest.fixture
def diagnostic_env(tmp_path, monkeypatch):
    module = tmp_path / "module-1.1-test.md"
    module.write_text(CONTENT, encoding="utf-8")
    log = tmp_path / "pipeline.log"
    report = tmp_path / "audit.json"
    monkeypatch.setattr(pipeline, "CONTENT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "LOG_FILE", log)
    monkeypatch.setattr(pipeline, "REPORT_FILE", report)
    monkeypatch.setattr(pipeline, "_quiet", False)
    # Exercise the real persistent print wrapper without changing pytest's print.
    monkeypatch.setattr(pipeline, "print", pipeline._logged_print, raising=False)
    return module, log, report


def synthetic_results(include_errors=True):
    results = [
        CheckResult("LINE_COUNT", False, MESSAGE, "WARNING"),
        CheckResult("CODE_LANG", False, MESSAGE, "INFO"),
        CheckResult(UNKNOWN_CHECK, False, MESSAGE, UNKNOWN_SEVERITY),
        CheckResult("QUIZ_DEPTH", True, MESSAGE),
    ]
    if include_errors:
        results += [
            CheckResult("FRONTMATTER", False, MESSAGE),
            CheckResult(UNKNOWN_CHECK, False, MESSAGE),
        ]
    return results


def assert_safe(text):
    for sentinel in (MESSAGE, UNKNOWN_CHECK, UNKNOWN_SEVERITY):
        assert sentinel not in text
    assert "UNKNOWN" in text


@pytest.mark.parametrize("surface", ["console", "log"])
@pytest.mark.parametrize("include_errors", [True, False])
def test_step_check_keeps_results_without_persisting_diagnostics(
    diagnostic_env, monkeypatch, capsys, surface, include_errors,
):
    module, log, _ = diagnostic_env
    results = synthetic_results(include_errors)
    monkeypatch.setattr(pipeline.structural, "run_all", lambda *_: results)

    passed, returned = pipeline.step_check(CONTENT, module)

    assert passed is (not include_errors)
    assert returned is results
    console = capsys.readouterr().out
    assert f"{2 if include_errors else 0} errors, 1 warnings" in console
    text = console if surface == "console" else log.read_text(encoding="utf-8")
    assert_safe(text)
    assert "LINE_COUNT" in text and "WARNING" in text
    assert "CODE_LANG" in text and "INFO" in text
    assert "QUIZ_DEPTH" not in text
    if include_errors:
        assert "FRONTMATTER" in text and "ERROR" in text


@pytest.mark.parametrize("surface", ["console", "log", "report"])
def test_audit_all_keeps_counts_without_persisting_diagnostics(
    diagnostic_env, monkeypatch, capsys, surface,
):
    _, log, report_file = diagnostic_env
    monkeypatch.setattr(pipeline.structural, "run_all", lambda *_: synthetic_results())

    pipeline.cmd_audit_all(SimpleNamespace(section=None))

    console = capsys.readouterr().out
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert set(report) == {"timestamp", "modules"}
    assert len(report["modules"]) == 1
    entry = next(iter(report["modules"].values()))
    assert set(entry) == {"errors", "error_details"}
    assert entry["errors"] == 2
    assert len(entry["error_details"]) == 2
    assert all(isinstance(detail, str) for detail in entry["error_details"])
    assert "0/1 modules pass deterministic checks" in console
    text = {
        "console": console,
        "log": log.read_text(encoding="utf-8"),
        "report": report_file.read_text(encoding="utf-8"),
    }[surface]
    assert_safe(text)
    assert "FRONTMATTER" in text and "ERROR" in text


def test_check_fail_markdown_does_not_persist_diagnostics(diagnostic_env, monkeypatch):
    module, _, report_file = diagnostic_env
    audit_file = report_file.with_suffix(".md")
    monkeypatch.setattr(pipeline, "review_audit_path_for_key", lambda _: audit_file)
    monkeypatch.setattr(pipeline, "load_state", lambda: {"modules": {}})
    details = pipeline._render_check_failures(synthetic_results())
    assert len(details) == 5

    pipeline.append_review_audit(module, "CHECK_FAIL", failed_checks=details, duration=1)

    text = audit_file.read_text(encoding="utf-8")
    assert_safe(text)
    assert "FRONTMATTER" in text and "ERROR" in text
    assert "LINE_COUNT" in text and "WARNING" in text
    assert "QUIZ_DEPTH" not in text
