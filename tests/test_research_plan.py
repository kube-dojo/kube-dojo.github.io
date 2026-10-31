from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import scripts.pipeline_common.research_plan as research

PLAN = {
    "module_kind": "module",
    "outcomes": ["Sort apples", "Describe apples"],
    "essential_topics": ["sorting", "description"],
    "source_basis": [{"uri": "git:example", "locator": "line 1", "excerpt": "Apples vary."}],
}
SEED = {
    "module_path": "src/content/docs/demo/module-1.1-test.md",
    "module_key": "demo/module-1.1-test",
    "claims": [{"claim_id": "C1", "judgment": None}],
    "source_acceptance": None,
    "coverage_plan": PLAN,
}


def test_concise_plan_valid_without_word_or_uri_reachability_requirements():
    assert research.validate_research_plan(PLAN) == []


@pytest.mark.parametrize("plan", [
    None, {}, {**PLAN, "module_kind": "hub"}, {**PLAN, "outcomes": []},
    {**PLAN, "outcomes": ["x", " x "]}, {**PLAN, "essential_topics": [None]},
    {**PLAN, "source_basis": []}, {**PLAN, "source_basis": [{"uri": "u", "locator": " ", "excerpt": "e"}]},
])
def test_invalid_research_is_blocked(plan):
    errors = research.validate_research_plan(plan)
    assert errors and all("research input blocked" in error for error in errors)


@pytest.mark.parametrize("path", ["demo/module-1.1-test.md", "src/content/docs/demo/module-1.1-test.md"])
def test_load_nested_plan_from_existing_seed_resolver(monkeypatch, path):
    calls = []
    def loader(seeds, page):
        calls.append((seeds, page))
        return json.dumps(SEED).encode()
    monkeypatch.setattr(research, "load_seed_bytes", loader)
    plan, errors = research.load_research_plan(Path("/repo"), path)
    assert (plan, errors) == (PLAN, [])
    assert calls == [(Path("/repo/docs/citation-seeds"), "demo/module-1.1-test.md")]
    assert SEED["claims"][0]["judgment"] is None and SEED["source_acceptance"] is None


def test_real_seed_resolver_uses_existing_slug_convention(monkeypatch):
    calls = []
    def read_bytes(path):
        calls.append(path)
        return json.dumps(SEED).encode()
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    plan, errors = research.load_research_plan(Path("/repo"), "demo/module-1.1-test.md")
    assert (plan, errors) == (PLAN, [])
    assert calls == [Path("/repo/docs/citation-seeds/demo-module-1.1-test.json")]


@pytest.mark.parametrize("path", ["/etc/passwd.md", "../outside.md", "demo/../outside.md", "C:/outside.md",
                                  "demo\\outside.md", "demo/file.txt", "demo/\x00.md", ""])
def test_unsafe_path_rejected_before_any_seed_read(monkeypatch, path):
    def forbidden(*_args):
        pytest.fail("unsafe path must not trigger a seed read")
    monkeypatch.setattr(research, "load_seed_bytes", forbidden)
    plan, errors = research.load_research_plan(Path("/repo"), path)
    assert plan is None and errors and "research input blocked" in errors[0]


@pytest.mark.parametrize("raw", [None, b"{", b"\xff", b"[]", b'{"module_path":"a","module_path":"b"}',
                                 json.dumps({**SEED, "coverage_plan": None}).encode(),
                                 json.dumps({**SEED, "module_path": "src/content/docs/other.md"}).encode(),
                                 json.dumps({**SEED, "module_key": "demo/different"}).encode()])
def test_missing_malformed_stale_or_duplicate_seed_fails(monkeypatch, raw):
    monkeypatch.setattr(research, "load_seed_bytes", lambda *_: raw)
    plan, errors = research.load_research_plan(Path("/repo"), "demo/module-1.1-test.md")
    assert plan is None and errors and "research input blocked" in errors[0]


def test_nested_duplicate_key_and_read_error_are_blocked(monkeypatch):
    raw = json.dumps(SEED).replace('"module_kind": "module"', '"module_kind": "module", "module_kind": "module"')
    monkeypatch.setattr(research, "load_seed_bytes", lambda *_: raw.encode())
    assert research.load_research_plan(Path("/repo"), "demo/module-1.1-test.md")[0] is None
    def failure(*_args):
        raise PermissionError("denied")
    monkeypatch.setattr(research, "load_seed_bytes", failure)
    plan, errors = research.load_research_plan(Path("/repo"), "demo/module-1.1-test.md")
    assert plan is None and "cannot read citation seed" in errors[0]


def test_validation_does_not_mutate_plan():
    original = copy.deepcopy(PLAN)
    assert research.validate_research_plan(PLAN) == []
    assert PLAN == original
