"""Coverage must not break orientation or reuse changed evidence."""
import json

from tests.test_content_coverage import setup_pages
from tests.test_local_api import local_api


def test_worktree_ledger_override_refresh_and_static_boundary(tmp_path, monkeypatch):
    _, evidence, receipt = setup_pages(tmp_path)
    wt = tmp_path / '.worktrees/quality'; ledger = wt / 'docs/content-upgrade/page-reviews.json'
    ledger.parent.mkdir(parents=True); (wt / 'static').mkdir()
    (wt / 'static/quality-coverage.js').write_text('worktree asset')
    row = {'path': receipt['path'], 'page_digest': receipt['page_digest'], 'state': 'prepared',
           'updated_at': '2026-10-31T09:00:00Z', 'summary': 'Prepared', 'next_action': 'Review', 'evidence_refs': ['issue:1']}
    ledger.write_text(json.dumps({'pages': [receipt], 'work': [row]}))
    monkeypatch.setenv('KUBEDOJO_UPGRADE_LEDGER', str(ledger)); monkeypatch.setenv('KUBEDOJO_UI_ROOT', str(wt))
    first = local_api._content_coverage_report(tmp_path)
    assert next(p for p in first['pages'] if p['path'] == receipt['path'])['work']['state'] == 'prepared'
    row['state'] = 'review_failed'; ledger.write_text(json.dumps({'pages': [receipt], 'work': [row]}))
    second = local_api._content_coverage_report(tmp_path)
    assert next(p for p in second['pages'] if p['path'] == receipt['path'])['work']['state'] == 'review_failed'
    assert second['locales'] == first['locales'] and evidence.exists()
    assert local_api.serve_static_file(tmp_path, 'quality-coverage.js')[1] == b'worktree asset'
    assert local_api.serve_static_file(tmp_path, '../outside')[0] == 404
    monkeypatch.setenv('KUBEDOJO_UI_ROOT', str(tmp_path)); assert local_api.serve_static_file(tmp_path, 'quality-coverage.js')[0] == 404
    monkeypatch.setenv('KUBEDOJO_UPGRADE_LEDGER', str(evidence)); assert local_api._content_coverage_report(tmp_path)['status'] == 'unavailable'


def test_api_cache_invalidates_pages_ledger_and_seeds(tmp_path, monkeypatch):
    from quality import content_coverage
    docs, evidence, receipt = setup_pages(tmp_path)
    calls = []
    original = content_coverage.build_coverage

    def counted(root):
        calls.append(root)
        return original(root)

    monkeypatch.setattr(content_coverage, "build_coverage", counted)
    code, first, _ = local_api.route_request(tmp_path, "/api/content/coverage")
    assert code == 200 and first["locales"]["en"]["review_recorded"] == 1
    local_api._content_coverage_report(tmp_path, compact=True)
    assert len(calls) == 1
    (docs / "linux/index.md").write_text("changed")
    assert local_api._content_coverage_report(tmp_path)["locales"]["en"]["stale"] == 1
    evidence.write_text('{"pages": []}')
    assert local_api._content_coverage_report(tmp_path)["locales"]["en"]["stale"] == 0
    seed = tmp_path / "docs/citation-seeds/new.json"
    seed.parent.mkdir(parents=True)
    seed.write_text('{"claims": []}')
    local_api._content_coverage_report(tmp_path)
    assert len(calls) == 4
    seed.unlink()
    local_api._content_coverage_report(tmp_path)
    assert len(calls) == 5
    evidence.write_text(json.dumps({"pages": [receipt, receipt]}))
    duplicate = local_api._content_coverage_report(tmp_path)
    assert duplicate["locales"]["en"]["invalid"] == 1 and duplicate["coverage_health"] == "unknown"
    duplicate["receipt_errors"] = ["x" * 1000] * 12
    compact = local_api._content_coverage_report(tmp_path, compact=True)
    assert compact["receipt_error_count"] == 12 and len(compact["receipt_errors"]) == 5
    assert all(len(item) == 200 for item in compact["receipt_errors"])


def test_briefing_and_orient_isolate_coverage_failure(tmp_path, monkeypatch):
    from quality import content_coverage
    setup_pages(tmp_path)

    def broken(_root):
        raise TypeError("private source text must not escape")

    monkeypatch.setattr(content_coverage, "build_coverage", broken)
    briefing = local_api.build_session_briefing(tmp_path)
    result = briefing["content_coverage"]
    assert result["status"] == "unavailable" and result["coverage_health"] == "unknown"
    assert "TypeError" in result["errors"][0] and "private source" not in json.dumps(result)
    monkeypatch.setattr(local_api, "get_or_build_session_briefing", lambda _: (briefing, {}))
    assert local_api.build_orient(tmp_path)["version"] == 1
    ready = local_api.build_tracks_readiness(tmp_path)
    assert ready["readiness_pct_metric"] == "legacy_frontmatter_flags"
    assert ready["content_coverage"]["endpoint"] == "/api/content/coverage"
