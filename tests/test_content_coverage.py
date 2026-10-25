import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from quality.content_coverage import build_coverage
from quality.content_inventory import EVIDENCE_LAYERS, _digest


def setup_pages(root):
    docs = root / "src/content/docs"
    for rel in ("index.md", "linux/index.md", "prerequisites/module-one.md", "uk/linux/index.md"):
        page = docs / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("---\ntitle: Test\n---\nBody\n")
    evidence = root / "docs/content-upgrade/page-reviews.json"
    evidence.parent.mkdir(parents=True)
    receipt = {"path": "linux/index.md", "acceptance_refs": ["lead:accepted"],
               "page_digest": _digest((docs / "linux/index.md").read_bytes()),
               "disposition": "revise", "reviewer_refs": ["review:1"], "evidence_refs": ["evidence:1"],
               "independent_statuses": dict.fromkeys(EVIDENCE_LAYERS, "pass")}
    evidence.write_text(json.dumps({"pages": [receipt]}))
    return docs, evidence, receipt


def test_grouping_and_stale_new_removed(tmp_path):
    docs, _, _ = setup_pages(tmp_path)
    report = build_coverage(tmp_path)
    assert report["locales"]["en"]["total"] == 3
    assert report["locales"]["uk"]["total"] == 1
    assert report["tracks"]["en"]["shared"]["total"] == 1
    assert report["sections"]["en"]["linux"]["needs_revision"] == 1
    assert report["milestones"]["prerequisites_linux"]["total"] == 2
    (docs / "linux/index.md").write_text("changed")
    report = build_coverage(tmp_path)
    assert report["locales"]["en"]["stale"] == 1
    assert report["locales"]["en"]["acceptance_recorded"] == 0
    assert report["locales"]["en"]["review_recorded"] == 0
    (docs / "linux/index.md").unlink()
    (docs / "new.md").write_text("new")
    report = build_coverage(tmp_path)
    assert report["missing_pages"] == ["linux/index.md"]
    assert "new.md" in report["new_pages"]
    assert report["coverage_health"] == "unknown"


def test_no_automatic_acceptance(tmp_path):
    docs, evidence, receipt = setup_pages(tmp_path)
    (docs / "index.md").unlink()
    (docs / "prerequisites/module-one.md").unlink()
    receipt.update(disposition="retain", acceptance_refs=["lead:acceptance"])
    evidence.write_text(json.dumps({"pages": [receipt]}))
    report = build_coverage(tmp_path)
    assert report["locales"]["en"]["review_recorded"] == 1
    assert report["locales"]["en"]["acceptance_recorded"] == 0  # no bound source evidence
    assert report["locales"]["en"]["unreviewed"] == 0
    assert report["locales"]["en"]["needs_revision"] == 0
    assert report["status"] == "needs_attention"


def test_missing_and_malformed_input(tmp_path):
    _, evidence, _ = setup_pages(tmp_path)
    for value in ("{", '{"pages": false}'):
        evidence.write_text(value)
        report = build_coverage(tmp_path)
        assert report["status"] == "unavailable" and report["coverage_health"] == "unknown"
        assert report["receipt_errors"] and report["locales"]["en"]["review_recorded"] == 0
    evidence.unlink()
    assert build_coverage(tmp_path)["status"] == "unavailable"


def test_explicit_acceptance_gates(tmp_path, monkeypatch):
    from quality import content_coverage
    _, evidence, receipt = setup_pages(tmp_path)
    original = content_coverage.build_inventory

    def validated_inventory(*args, **kwargs):
        result = original(*args, **kwargs)
        for page in result["pages"]:
            if page["path"] == receipt["path"]:
                page["evidence"]["independent_statuses"]["technical_source"] = "pass"
        return result

    # Isolate the acceptance predicate; real source rejection is tested above.
    monkeypatch.setattr(content_coverage, "build_inventory", validated_inventory)
    receipt.update(disposition="retain")
    receipt["independent_statuses"].update(translation_fidelity="unknown", learner_data="unknown",
                                           lab_execution="not_applicable")
    for refs, expected in ((None, 0), ([], 0), ([" "], 0), (["lead:accepted"], 1)):
        receipt["acceptance_refs"] = refs
        evidence.write_text(json.dumps({"pages": [receipt]}))
        assert build_coverage(tmp_path)["locales"]["en"]["acceptance_recorded"] == expected
    receipt["independent_statuses"]["deployed_smoke"] = "unknown"
    evidence.write_text(json.dumps({"pages": [receipt]}))
    assert build_coverage(tmp_path)["locales"]["en"]["acceptance_recorded"] == 0
    receipt["independent_statuses"]["deployed_smoke"] = "pass"
    for disposition in ("revise", "expand"):
        receipt["disposition"] = disposition
        evidence.write_text(json.dumps({"pages": [receipt]}))
        assert build_coverage(tmp_path)["locales"]["en"]["acceptance_recorded"] == 0


def test_malformed_seed_is_unavailable(tmp_path, monkeypatch):
    from quality import content_coverage
    docs, evidence, _ = setup_pages(tmp_path)
    seed = tmp_path / "docs/citation-seeds/linux-index.json"
    seed.parent.mkdir(parents=True)
    seed.write_text('{"secret": "do-not-expose"}')
    report = build_coverage(tmp_path)
    assert report["locales"]["en"]["acceptance_recorded"] == 0 and "do-not-expose" not in json.dumps(report)
    assert report["status"] == "unavailable" or all(p["evidence"]["independent_statuses"]["technical_source"] == "unknown" for p in content_coverage.build_inventory(docs, evidence)["pages"])
    monkeypatch.setattr(content_coverage, "build_inventory", lambda *a, **kw: (_ for _ in ()).throw(TypeError("secret")))
    report = build_coverage(tmp_path)
    assert report["status"] == "unavailable" and report["coverage_health"] == "unknown"
    assert "inventory unavailable: TypeError" in report["errors"] and "secret" not in json.dumps(report)

def test_empty_english_is_unavailable(tmp_path):
    docs, evidence, _ = setup_pages(tmp_path)
    for rel in ("index.md", "linux/index.md", "prerequisites/module-one.md"):
        (docs / rel).unlink()
    evidence.write_text('{"pages": []}')
    report = build_coverage(tmp_path)
    assert report["status"] == "unavailable" and report["coverage_health"] == "unknown"
