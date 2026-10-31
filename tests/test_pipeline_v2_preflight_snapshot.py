"""Preflight must inspect the same bytes as the model, not a replacement file."""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from scripts.pipeline_v2.preflight import run_preflight

VALID = "---\ntitle: Snapshot\nslug: snapshot\nsidebar:\n  order: 1\n---\n\nTeaching text.\n"


@pytest.mark.parametrize("snapshot", [VALID, "", None])
def test_preflight_uses_explicit_snapshot_even_if_path_has_changed(tmp_path, snapshot):
    path = tmp_path / "module.md"
    path.write_text("replacement without frontmatter")
    calls = []
    def lint(command, **kwargs):
        calls.append((command, kwargs.get("input")))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    with patch("scripts.pipeline_v2.preflight.subprocess.run", side_effect=lint):
        result = run_preflight(path, repo_root=tmp_path, content=snapshot)
    assert calls[0][0] == ["npx", "markdownlint-cli2", str(path) if snapshot is None else "-"]
    assert calls[0][1] == snapshot
    assert any(f.id == "FRONTMATTER" and not f.passed for f in result.findings) is (snapshot != VALID)
    assert path.read_text() == "replacement without frontmatter"
