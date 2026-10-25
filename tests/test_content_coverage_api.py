"""Coverage must not break orientation or reuse changed evidence."""
import json

from tests.test_content_coverage import setup_pages
from tests.test_local_api import local_api


def test_api_cache_invalidates_pages_ledger_and_seeds(tmp_path, monkeypatch):
    from quality import content_coverage
    docs, evidence, _ = setup_pages(tmp_path)
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
