"""Per-module body-word budget sidecars are reported diagnostics only (#3744)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quality import verify_module


def _make_module(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = " ".join("word" for _ in range(3500))
    text = f"""---
title: "Test Module"
slug: c1/module
sidebar:
  order: 1
---

{body}
"""
    path.write_text(text, encoding="utf-8")
    return path


def _module_slug_for_budgets(root: Path, module_path: Path) -> str:
    return module_path.relative_to(root / "src" / "content" / "docs").as_posix().replace("/", "__")


def test_verify_module_has_no_default_body_word_floor(tmp_path, monkeypatch) -> None:
    module = _make_module(tmp_path / "src/content/docs/c1/module.md")
    monkeypatch.setattr(verify_module, "REPO_ROOT", tmp_path)
    result = verify_module.verify(module, skip_source_check=True, max_workers=1)
    assert "body_words_floor_met" not in result["gates"]
    assert result["declared_body_budget"] == {"status": "none"}


def test_verify_module_reports_sidecar_3000_without_gating(tmp_path, monkeypatch) -> None:
    module = _make_module(tmp_path / "src/content/docs/c1/module.md")
    budgets = tmp_path / ".pipeline" / "budgets"
    budgets.mkdir(parents=True, exist_ok=True)
    budget = budgets / f"{_module_slug_for_budgets(tmp_path, module)}.json"
    budget.write_text(
        '{"body_words_min": 3000, "source_module": "src/content/docs/c1/module.md", "set_at": "2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_module, "REPO_ROOT", tmp_path)
    result = verify_module.verify(module, skip_source_check=True, max_workers=1)
    assert result["declared_body_budget"] == {"status": "declared", "body_words_min": 3000}
    assert "body_words_floor_met" not in result["gates"]


def test_verify_module_reports_sidecar_4000_without_gating(tmp_path, monkeypatch) -> None:
    module = _make_module(tmp_path / "src/content/docs/c1/module.md")
    budgets = tmp_path / ".pipeline" / "budgets"
    budgets.mkdir(parents=True, exist_ok=True)
    budget = budgets / f"{_module_slug_for_budgets(tmp_path, module)}.json"
    budget.write_text(
        '{"body_words_min": 4000, "source_module": "src/content/docs/c1/module.md", "set_at": "2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_module, "REPO_ROOT", tmp_path)
    result = verify_module.verify(module, skip_source_check=True, max_workers=1)
    assert result["declared_body_budget"] == {"status": "declared", "body_words_min": 4000}
    assert "body_words_floor_met" not in result["gates"]


@pytest.mark.parametrize("raw", ['{"body_words_min": 1000, "x": NaN}', '{"body_words_min": 1000, "x": -Infinity}', "too deep"])
def test_nonstandard_or_too_deep_sidecar_json_is_malformed(tmp_path, monkeypatch, raw) -> None:
    module = _make_module(tmp_path / "src/content/docs/c1/module.md")
    sidecar = tmp_path / ".pipeline" / "budgets" / f"{_module_slug_for_budgets(tmp_path, module)}.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text('{"body_words_min": 1000}' if raw == "too deep" else raw, encoding="utf-8")
    if raw == "too deep":  # decoder nesting limits differ by Python version, so force the failure
        monkeypatch.setattr(verify_module.json, "loads", lambda *a, **k: (_ for _ in ()).throw(RecursionError()))
    monkeypatch.setattr(verify_module, "REPO_ROOT", tmp_path)
    assert verify_module._declared_body_budget(module)["status"] == "malformed"


@pytest.mark.parametrize(
    "sidecar",
    ['{"body_words_min": true}', '{"body_words_min": "3000"}', '{"body_words_min": 3000.5}', '{"body_words_min": 0}',
     '{"body_words_min": -1}', '{"body_words_min": Infinity}', '{"other": 1}', "[3000]", "not json"],
)
def test_malformed_sidecar_is_reported_and_never_creates_acceptance(tmp_path, monkeypatch, sidecar) -> None:
    def run(root, text: str | None) -> dict[str, object]:
        module = _make_module(root / "src/content/docs/c1/module.md")
        if text is not None:
            budget = root / ".pipeline" / "budgets" / f"{_module_slug_for_budgets(root, module)}.json"
            budget.parent.mkdir(parents=True)
            budget.write_text(text, encoding="utf-8")
        monkeypatch.setattr(verify_module, "REPO_ROOT", root)
        return verify_module.verify(module, skip_source_check=True, max_workers=1)

    baseline, result = run(tmp_path / "base", None), run(tmp_path / "bad", sidecar)
    assert result["declared_body_budget"]["status"] == "malformed"
    assert any("budget sidecar ignored as malformed" in item for item in result["diagnostics"])
    for key in ("gates", "passed", "tier", "tier_reasons"):
        assert result[key] == baseline[key]
