import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from quality.content_coverage import build_coverage
from quality.content_inventory import EVIDENCE_LAYERS, _digest
from test_source_acceptance import _valid


def test_recorded_work_is_current_isolated_and_never_promotes(tmp_path):
    docs, evidence, receipt = setup_pages(tmp_path)
    record = {'path': receipt['path'], 'page_digest': receipt['page_digest'], 'state': 'reviewing',
              'updated_at': '2026-10-31T09:00:00Z', 'summary': 'Review running', 'next_action': 'Wait for result',
              'evidence_refs': ['issue:1'], 'review': {'spent': 4, 'ceiling': 5}}
    baseline = build_coverage(tmp_path)['locales']
    def report(rows):
        evidence.write_text(json.dumps({'pages': [receipt], 'work': rows}))
        return build_coverage(tmp_path)
    valid = report([record]); page = next(p for p in valid['pages'] if p['path'] == receipt['path'])
    assert page['work']['state'] == 'reviewing' and page['work']['review'] == {'spent': 4, 'ceiling': 5}
    assert valid['locales'] == baseline and not page['acceptance_recorded'] and valid['work_summary']['reviewing'] == 1
    assert next(p for p in valid['pages'] if p['path'] == 'index.md')['work']['state'] == 'unknown'
    assert next(p for p in valid['pages'] if p['locale'] == 'uk')['work']['state'] == 'parked'
    for bad in ({**record, 'state': 'accepted'}, {**record, 'page_digest': 'sha256:' + '0'*64},
                {**record, 'review': {'spent': True}}, {**record, 'updated_at': 'yesterday'}, {**record, 'summary': ''}):
        result = report([bad]); item = next(p for p in result['pages'] if p['path'] == receipt['path'])
        assert item['work']['state'] == 'unknown' and result['work_errors'] and result['locales'] == baseline
    result = report([record, record]); assert result['work_errors'] and result['work_summary']['unknown'] == 3
    result = report([{**record, 'path': 'no-such-page.md'}]); assert result['work_errors'] and result['locales'] == baseline
    result = report('not a list'); assert result['work_errors'] and result['locales'] == baseline
    (docs / receipt['path']).write_text('new bytes')
    assert next(p for p in report([record])['pages'] if p['path'] == receipt['path'])['work']['state'] == 'unknown'


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
    row = next(page for page in report["pages"] if page["path"] == "linux/index.md")
    assert row["acceptance_recorded"] is False and row["review_recorded"] is True
    assert row["layers"]["technical_source"] == "unknown"
    assert row["references"]["acceptance_refs"] == ["lead:acceptance"]
    assert "technical_source: unknown" in row["reasons"]


def test_missing_and_malformed_input(tmp_path):
    _, evidence, _ = setup_pages(tmp_path)
    for value in ("{", '{"pages": false}', '{"pages":' + "9" * 5000 + "}", "[" * 2000):
        evidence.write_text(value)
        report = build_coverage(tmp_path)
        assert report["status"] == "unavailable" and report["coverage_health"] == "unknown"
        assert (report["receipt_errors"] or report["errors"]) and report["locales"]["en"]["review_recorded"] == 0
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
        report = build_coverage(tmp_path)
        for locale, totals in report["locales"].items():
            rows = [page for page in report["pages"] if page["locale"] == locale]
            for key, count in totals.items():
                assert count == (len(rows) if key == "total" else sum(row[key] for row in rows))
        assert report["locales"]["en"]["acceptance_recorded"] == expected
        assert next(p for p in report['pages'] if p['path'] == receipt['path'])['work']['state'] == ('accepted' if expected else 'unknown')
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


def test_row_projection_stale_mdx_and_private_receipts(tmp_path):
    docs, evidence, receipt = setup_pages(tmp_path)
    (docs / "index.mdx").write_text("---\ntitle: Hub\n---\n")
    receipt.update(private_trace="secret", source_acceptance={"private": "secret"})
    evidence.write_text(json.dumps({"pages": [receipt]}))
    (docs / "linux/index.md").write_text("changed")
    report = build_coverage(tmp_path)
    rows = {page["path"]: page for page in report["pages"]}
    assert rows["index.mdx"]["type"] == "hub"
    assert rows["uk/linux/index.md"]["locale"] == "uk"
    stale = rows[receipt["path"]]
    assert stale["stale"] and not stale["acceptance_recorded"] and stale["unreviewed"]
    assert "receipt: stale" in stale["reasons"] and "secret" not in json.dumps(report)


def test_nested_source_run_reason_is_bounded_public_vocabulary(tmp_path):
    _, evidence, receipt = setup_pages(tmp_path)
    seed = b'{"claims":[{"claim_id":"C001"}]}'
    seeds = tmp_path / "docs/citation-seeds"
    seeds.mkdir()
    (seeds / "linux-index.json").write_bytes(seed)
    nested = _valid(page_digest=receipt["page_digest"], seed_digest=_digest(seed))
    receipt["source_acceptance"] = nested
    for status, reason in (("complete", None), ("failed", "source: run_status:failed"),
                           ("SYNTHETIC_SECRET" * 10000, "source: invalid_or_unknown"),
                           ({"trace": "SYNTHETIC_SECRET" * 10000}, "source: invalid_or_unknown")):
        nested["run"]["status"] = status
        evidence.write_text(json.dumps({"pages": [receipt]}))
        row = next(p for p in build_coverage(tmp_path)["pages"] if p["path"] == receipt["path"])
        assert row["receipt_status"] == "current"
        assert row["layers"]["technical_source"] == ("pass" if reason is None else "unknown")
        assert ([r for r in row["reasons"] if r.startswith("source: ")] == ([] if reason is None else [reason]))
        assert "SYNTHETIC_SECRET" not in json.dumps(row)
