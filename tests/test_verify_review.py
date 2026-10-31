from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import verify_review as verifier
from verify_review import parse_findings, verify_review


def _review(path: str, line: int, code: str) -> str:
    return f"""FINDING: test
FILE:LINE: {path}:{line}
CURRENT CODE:
  {code}
WHY: reason
FIX: fix
"""


def test_verify_review_marks_verified_when_quote_matches_claimed_line():
    results = verify_review(_review("a.py", 2, "beta = 2"), lambda _path: "alpha = 1\nbeta = 2\ngamma = 3\n")
    assert results[0]["status"] == "verified"


def test_verify_review_marks_line_mismatch_when_quote_exists_elsewhere():
    results = verify_review(_review("a.py", 1, "beta = 2"), lambda _path: "alpha = 1\nbeta = 2\ngamma = 3\n")
    assert results[0]["status"] == "line_mismatch"


def test_verify_review_marks_quote_missing_for_hallucinated_code():
    results = verify_review(_review("a.py", 2, "delta = 4"), lambda _path: "alpha = 1\nbeta = 2\ngamma = 3\n")
    assert results[0]["status"] == "quote_missing"


def test_verify_review_handles_mixed_outcomes():
    review = "\n".join(
        [
            _review("a.py", 2, "beta = 2").strip(),
            _review("a.py", 1, "gamma = 3").strip(),
            _review("a.py", 4, "delta = 4").strip(),
        ]
    )
    results = verify_review(review, lambda _path: "alpha = 1\nbeta = 2\ngamma = 3\n")
    assert [result["status"] for result in results] == ["verified", "line_mismatch", "quote_missing"]


HEAD = "a" * 40

def structured(verdict="NEEDS_CHANGES", findings=None):
    if findings is None:
        findings = [{"id": "R1-F1", "severity": "material", "path": "a.py", "line": 2,
                     "quote": "beta = 2", "why": "wrong behavior", "fix": "correct it"}]
    return json.dumps({"head": HEAD, "verdict": verdict, "findings": findings})


def test_structured_and_empty_approval():
    assert verify_review(structured(), lambda _: "alpha = 1\nbeta = 2\n")[0]["status"] == "verified"
    assert verify_review(structured().replace("beta = 2", "beta  = 2"), lambda _: "beta = 2")[0]["status"] == "quote_missing"
    assert parse_findings(structured("APPROVE", [])) == []
    with pytest.raises(ValueError):
        parse_findings(structured("NEEDS_CHANGES", []))


@pytest.mark.parametrize("bad", ["", "not a review", '{"verdict":', '{"verdict":"APPROVE","findings":[]}',
                                 '{"head":"x","head":"y","verdict":"APPROVE","findings":[]}'])
def test_invalid_review_fails(bad):
    with pytest.raises(ValueError):
        parse_findings(bad)


@pytest.mark.parametrize("field,value", [("line", True), ("line", 0), ("path", "../secret"),
                                         ("path", "/tmp/file"), ("quote", ""), ("fix", None)])
def test_malformed_finding_fails(field, value):
    data = json.loads(structured())
    data["findings"][0][field] = value
    with pytest.raises(ValueError):
        parse_findings(json.dumps(data))


def test_markdown_findings_without_quotes_are_not_silently_accepted():
    body = "## PR: needs changes\n\n### Findings\n- **R1-F1 (material):** problem\n- **R1-F2 (nit):** issue\n"
    assert [r["status"] for r in verify_review(body, lambda _: "")] == ["unsupported_evidence"] * 2
    with pytest.raises(ValueError):
        parse_findings(body + "- Unknown finding\n")


def test_duplicate_nested_json_key_fails():
    review = structured().replace('"id": "R1-F1"', '"id": "R1-F1", "id": "R1-F2"')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_findings(review)


@pytest.mark.parametrize("head,expected", [(HEAD, 0), ("b" * 40, 2)])
def test_cli_structured_head_binding(monkeypatch, capsys, head, expected):
    monkeypatch.setattr(verifier.sys, "argv", ["verify_review.py", "--pr", "1", "--branch", "fixture"])
    monkeypatch.setattr(verifier.sys, "stdin", io.StringIO(structured("APPROVE", []).replace(HEAD, head)))
    monkeypatch.setattr(verifier.subprocess, "run", lambda *a, **k: type("Result", (), {"stdout": HEAD})())
    assert verifier.main() == expected
    output = capsys.readouterr()
    assert ("Recognized approval" in output.out) if expected == 0 else ("does not match" in output.err)


def test_missing_file_is_distinct_from_missing_quote():
    def reader(_):
        raise FileNotFoundError()
    assert verify_review(structured(), reader)[0]["status"] == "file_missing"
