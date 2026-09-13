"""Readiness consumes the #2310 receipt. Fixtures prove the gate, not real support."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.quality.source_acceptance import _digest
from tests.test_local_api import _init_repo, _seed_module, local_api
from tests.test_source_acceptance import _valid


def _ledger(repo: Path, rel: str, receipt: dict[str, object] | None) -> None:
    entry = {
        "path": f"{rel}.md", "page_digest": "0" * 64, "disposition": "retain",
        "reviewer_refs": ["r"], "evidence_refs": ["e"],
        "independent_statuses": {"technical_source": "pass"},
    }
    if receipt is not None:
        entry["source_acceptance"] = receipt
    path = repo / "docs/content-upgrade/evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pages": [entry]}), encoding="utf-8")


def test_readiness_source_accepted_fail_closed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _seed_module(tmp_path, "k8s/cka/module-1.1-alpha",
                 frontmatter={"revision_pending": False, "citations_verified": True})
    page = tmp_path / "src/content/docs/k8s/cka/module-1.1-alpha.md"
    seed = b'{"claims":[{"claim_id":"C001"}]}'
    (tmp_path / "docs/citation-seeds").mkdir(parents=True)
    (tmp_path / "docs/citation-seeds/k8s-cka-module-1.1-alpha.json").write_bytes(seed)
    cleared = local_api.build_tracks_readiness(tmp_path)
    assert cleared["totals"]["cleared"] == 1
    assert cleared["totals"]["source_accepted"] == 0

    _ledger(tmp_path, "k8s/cka/module-1.1-alpha", None)
    assert local_api.build_tracks_readiness(tmp_path)["totals"]["source_accepted"] == 0
    stale = _valid(page_digest=_digest(page.read_bytes()), seed_digest=_digest(seed))
    stale["page_digest"] = "sha256:" + "d" * 64
    _ledger(tmp_path, "k8s/cka/module-1.1-alpha", stale)
    assert local_api.build_tracks_readiness(tmp_path)["totals"]["source_accepted"] == 0
    _ledger(tmp_path, "k8s/cka/module-1.1-alpha",
            _valid(page_digest=_digest(page.read_bytes()), seed_digest=_digest(seed)))
    assert local_api.build_tracks_readiness(tmp_path)["totals"]["source_accepted"] == 1
    first = local_api._v_docs_frontmatter(tmp_path)
    _ledger(tmp_path, "k8s/cka/module-1.1-alpha", None)
    assert first != local_api._v_docs_frontmatter(tmp_path)
