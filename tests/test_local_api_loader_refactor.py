"""Regression guard for the local_api submodule-loader refactor (PR #1864).

PR #1864 collapsed near-identical ``_load_*_module()`` functions into one
generic ``_load_local_api_submodule()``. These tests pin that the wrappers still
load the real submodules (with their expected public API) and that loads are
cached.

``scripts/local_api/`` is a package, so a plain ``import local_api`` resolves to
the package, not ``local_api.py``. Load the module file explicitly (same pattern
as ``tests/test_local_api.py``).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def test_generic_loader_loads_each_submodule() -> None:
    ui = local_api._load_ui_fragments_module()
    assert hasattr(ui, "render_poll_stale_script")
    guard = local_api._load_repo_guard_module()
    assert hasattr(guard, "build_healthz_payload")


def test_loader_caches_modules() -> None:
    # stable sys.modules key -> repeated loads return the same object
    assert local_api._load_ui_fragments_module() is local_api._load_ui_fragments_module()
