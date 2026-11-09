from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate_v1_to_v2 as migrate


def test_phase_normalizer_still_maps_write_to_pending() -> None:
    assert migrate._normalize_phase({"phase": "write"}) == "pending"
    assert migrate._normalize_phase({"phase": "review"}) == "review"


def test_control_plane_path_reports_removed_dispatcher() -> None:
    with pytest.raises(RuntimeError, match="legacy dispatcher removed"):
        migrate.ControlPlane(db_path=Path("/tmp/unused.db"))
