"""Regression tests: dispatch_smart's Codex calls leave web search off.

The Codex adapter and its danger-mode guard live in the installed
``lu_machinery.agent_runtime``; their tests live with that package. These
tests cover the KubeDojo-side ``scripts/dispatch_smart.py`` wrapper only.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_dispatch_smart():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return importlib.import_module("dispatch_smart")


def test_dispatch_smart_codex_does_not_enable_search_for_draft():
    """Draft uses the shared runtime, which has no web-search switch."""
    dispatch_smart = _load_dispatch_smart()
    observed: dict[str, str] = {}

    def fake_invoke(*_args, **kwargs):
        import os

        observed["search"] = os.environ.get("KUBEDOJO_CODEX_SEARCH", "")
        observed["effort"] = kwargs.get("effort", "")
        return SimpleNamespace(
            ok=True,
            response="ok",
            session_id=None,
            stderr_excerpt="",
        )

    with patch("lu_machinery.agent_runtime.runner.invoke", side_effect=fake_invoke):
        dispatch_smart.fire(
            agent="codex",
            task_class="draft",
            prompt="x",
            mode="danger",
            model="gpt-6.1-sol",
            worktree=None,
            task_id="t1",
            timeout_s=1,
        )
    assert observed["search"] == ""
    assert observed["effort"] == "high"


def test_dispatch_smart_codex_leaves_caller_search_env_for_review(monkeypatch):
    """Review does not request Codex web search, and it restores nothing it did not set."""
    import os

    monkeypatch.setenv("KUBEDOJO_CODEX_SEARCH", "caller-search")
    monkeypatch.setenv("KUBEDOJO_CODEX_EFFORT", "caller-effort")
    dispatch_smart = _load_dispatch_smart()
    observed: dict[str, str] = {}

    def fake_invoke(*_args, **_kwargs):
        import os

        observed["search"] = os.environ.get("KUBEDOJO_CODEX_SEARCH", "")
        return SimpleNamespace(
            ok=True,
            response="ok",
            session_id=None,
            stderr_excerpt="",
        )

    with patch("lu_machinery.agent_runtime.runner.invoke", side_effect=fake_invoke):
        dispatch_smart.fire(
            agent="codex",
            task_class="review",
            prompt="x",
            mode="read-only",
            model="gpt-6.1-sol",
            worktree=None,
            task_id="t2",
            timeout_s=1,
        )
    assert observed["search"] == "caller-search"
    assert os.environ["KUBEDOJO_CODEX_SEARCH"] == "caller-search"
    assert os.environ["KUBEDOJO_CODEX_EFFORT"] == "caller-effort"
