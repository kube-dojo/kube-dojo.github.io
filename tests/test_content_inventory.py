from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "quality" / "content_inventory.py"
    spec = importlib.util.spec_from_file_location("content_inventory", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory = _load_module()


def _write(path: Path, *, slug: str | None = None, body: str = "body") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    route = f'\nslug: "{slug}"' if slug else ""
    path.write_text(f'---\ntitle: "Example"{route}\n---\n\n{body}\n', encoding="utf-8")


def _receipt(docs: Path, rel: str, **changes: object) -> dict[str, object]:
    path = docs / rel
    receipt: dict[str, object] = {
        "path": rel,
        "page_digest": inventory._digest(path.read_bytes()),
        "disposition": "retain",
        "reviewer_refs": ["review:one"],
        "evidence_refs": ["evidence:one"],
        "independent_statuses": {"technical_source": "pass"},
    }
    receipt.update(changes)
    return receipt


def _pages(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {page["path"]: page for page in report["pages"]}  # type: ignore[index]


def test_en_uk_mapping_and_source_fields(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _write(docs / "track/module-1.1-example.md", slug="track/module-1.1-example")
    _write(docs / "uk/track/module-1.1-example.md", slug="uk/track/module-1.1-example")
    _write(docs / "track/index.md")

    pages = _pages(inventory.build_inventory(docs))
    en = pages["track/module-1.1-example.md"]
    uk = pages["uk/track/module-1.1-example.md"]
    hub = pages["track/index.md"]
    assert en["locale"] == "en" and en["type"] == "module"
    assert en["section"] == "track"
    assert en["counterpart"] == "uk/track/module-1.1-example.md"
    assert uk["locale"] == "uk" and uk["counterpart"] == "track/module-1.1-example.md"
    assert en["source_route"] == "track/module-1.1-example"
    assert hub["source_route"] is None
    assert hub["route_validation"] == "not_checked"


def test_new_and_missing_pages_are_reported(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _write(docs / "old.md")
    _write(docs / "new.md")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps({"pages": [_receipt(docs, "old.md"), {
            "path": "removed.md",
            "page_digest": "0" * 64,
            "disposition": "revise",
        }]}),
        encoding="utf-8",
    )

    report = inventory.build_inventory(docs, evidence)
    assert report["new_pages"] == ["new.md"]
    assert report["missing_pages"] == ["removed.md"]
    assert _pages(report)["old.md"]["evidence"]["receipt_status"] == "current"
    assert _pages(report)["old.md"]["evidence"]["status_source"] == "supplied_receipt"
    assert _pages(report)["new.md"]["evidence"]["status_source"] == "unknown"


def test_changed_content_invalidates_receipt(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    page = docs / "module.md"
    _write(page)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"pages": [_receipt(docs, "module.md")]}), encoding="utf-8")
    page.write_text(page.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    record = _pages(inventory.build_inventory(docs, evidence))["module.md"]
    assert record["evidence"]["receipt_status"] == "stale"
    assert record["evidence"]["status_source"] == "unknown"
    assert set(record["evidence"]["independent_statuses"].values()) == {"unknown"}


def test_headings_and_presence_never_imply_pass(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    page = docs / "module.md"
    _write(page, body="## Learning Outcomes\n## Quiz\n## Lab")
    before = page.read_bytes()

    assert inventory.main(["--docs-root", str(docs)]) == 0
    report = json.loads(capsys.readouterr().out)
    record = _pages(report)["module.md"]
    assert record["evidence"]["receipt_status"] == "missing"
    assert set(record["evidence"]["independent_statuses"].values()) == {"unknown"}
    assert page.read_bytes() == before


def test_invalid_receipt_cannot_pass(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _write(docs / "module.md")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"pages": [_receipt(docs, "module.md", evidence_refs=[], independent_statuses={"technical_source": "pass"})]}), encoding="utf-8")

    record = _pages(inventory.build_inventory(docs, evidence))["module.md"]
    assert record["evidence"]["receipt_status"] == "invalid"
    assert set(record["evidence"]["independent_statuses"].values()) == {"unknown"}


def test_duplicate_and_malformed_status_receipts_are_invalid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _write(docs / "module.md")
    receipt = _receipt(docs, "module.md")
    malformed = _receipt(docs, "module.md", independent_statuses={"made_up": "pass"})
    malformed_value = _receipt(docs, "module.md", independent_statuses={"technical_source": []})
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"pages": [receipt, receipt]}), encoding="utf-8")
    duplicate_report = inventory.build_inventory(docs, evidence)
    duplicate = _pages(duplicate_report)["module.md"]
    assert duplicate["evidence"]["receipt_status"] == "invalid"
    assert duplicate_report["receipt_errors"].count("duplicate evidence receipt: module.md") == 1

    evidence.write_text(json.dumps({"pages": [malformed]}), encoding="utf-8")
    unknown_layer = _pages(inventory.build_inventory(docs, evidence))["module.md"]
    assert unknown_layer["evidence"]["receipt_status"] == "invalid"

    evidence.write_text(json.dumps({"pages": [malformed_value]}), encoding="utf-8")
    bad_value = _pages(inventory.build_inventory(docs, evidence))["module.md"]
    assert bad_value["evidence"]["receipt_status"] == "invalid"

    for bad_disposition in ([], {}):
        evidence.write_text(
            json.dumps({"pages": [_receipt(docs, "module.md", disposition=bad_disposition)]}),
            encoding="utf-8",
        )
        bad_receipt = _pages(inventory.build_inventory(docs, evidence))["module.md"]
        assert bad_receipt["evidence"]["receipt_status"] == "invalid"


def test_inventory_source_acceptance_fail_closed(tmp_path: Path) -> None:
    from scripts.quality.source_acceptance import _digest
    from tests.test_source_acceptance import _valid

    docs = tmp_path / "docs"
    page = docs / "k8s/cka/module-1.1-foo.md"
    _write(page)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"pages": [_receipt(docs, "k8s/cka/module-1.1-foo.md")]}), encoding="utf-8")
    missing = _pages(inventory.build_inventory(docs, evidence))["k8s/cka/module-1.1-foo.md"]
    assert missing["evidence"]["receipt_status"] == "current"
    assert missing["evidence"]["independent_statuses"]["technical_source"] == "unknown"
    assert missing["evidence"]["source_acceptance"]["accepted"] is False

    seed = b'{"claims":[{"claim_id":"C001"}]}'
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    (seeds / "k8s-cka-module-1.1-foo.json").write_bytes(seed)
    stale = _valid(page_digest=_digest(page.read_bytes()), seed_digest=_digest(seed))
    stale["page_digest"] = "sha256:" + "d" * 64
    rel = "k8s/cka/module-1.1-foo.md"
    evidence.write_text(json.dumps({"pages": [_receipt(docs, rel, source_acceptance=stale)]}), encoding="utf-8")
    stale_rec = _pages(inventory.build_inventory(docs, evidence, seeds_dir=seeds))[rel]
    assert stale_rec["evidence"]["source_acceptance"]["accepted"] is False
    assert stale_rec["evidence"]["independent_statuses"]["technical_source"] == "unknown"

    ok_receipt = _valid(page_digest=_digest(page.read_bytes()), seed_digest=_digest(seed))
    evidence.write_text(json.dumps({"pages": [_receipt(docs, rel, source_acceptance=ok_receipt)]}), encoding="utf-8")
    ok = _pages(inventory.build_inventory(docs, evidence, seeds_dir=seeds))[rel]
    assert ok["evidence"]["source_acceptance"]["accepted"] is True
    assert ok["evidence"]["independent_statuses"]["technical_source"] == "pass"


def test_missing_docs_root_is_an_explicit_cli_error(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does-not-exist"
    assert inventory.main(["--docs-root", str(missing)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["errors"] == ["docs_root does not exist or is not a directory"]
    assert report["pages"] == []
