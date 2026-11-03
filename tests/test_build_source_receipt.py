"""Offline defect cases for receipt production and deployed-smoke refusal."""

import copy
import base64
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality import build_source_receipt as builder
from scripts.quality import record_deployed_smoke as smoke
from scripts.quality.source_acceptance import evaluate_source_acceptance

PAGE = "src/content/docs/prerequisites/pilot/index.md"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("tests must not access the network")
    monkeypatch.setattr(smoke.urllib.request, "urlopen", refuse)


@pytest.fixture
def bundle(tmp_path):
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True).stdout.decode().strip()
    git("init", "-q")
    page = tmp_path / PAGE
    page.parent.mkdir(parents=True)
    page.write_text('---\ntitle: Pilot\n---\nThis hub has one module.\n')
    reviews = tmp_path / "docs/content-upgrade/reviews"
    reviews.mkdir(parents=True)
    ledger = reviews.parent / "page-reviews.json"
    ledger.write_text(json.dumps({"pages": [{"path": "prerequisites/pilot/index.md", "page_digest": builder.digest(page.read_bytes())}]}))
    git("add", "src", "docs")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture")
    proposals = {
        "author": {"identity": "gpt-6.1-terra", "family": "openai", "evidence_ref": "work-record/pilot"},
        "claims": [{"claim_id": "C001", "claim_text": "This hub has one module.", "line_start": 4, "line_end": 4, "kind": "internal", "candidate_sources": [{"path": PAGE}]}],
    }
    seed = builder.seed(tmp_path, PAGE, proposals)
    seed_path = tmp_path / "seed.json"
    builder.write_json(seed_path, seed)
    packet = builder.packet(tmp_path, seed_path)
    packet_path = tmp_path / "packet.json"
    builder.write_json(packet_path, packet)
    source = next(iter(packet["sources"].values()))
    verdicts = {
        "schema": builder.VERIFIER_SCHEMA,
        "page_digest": packet["page_digest"], "seed_digest": packet["seed_digest"],
        "packet_digest": builder.digest(packet_path.read_bytes()),
        "coverage_complete": True,
        "verifier": {"identity": "claude-independent-run", "family": "anthropic"},
        "run": {"identity": "fixture-verification", "status": "complete"},
        "claims": [{"claim_id": "C001", "verdict": "SUPPORTED", "source": {
            "retrieval_uri": source["retrieval_uri"], "snapshot_digest": source["snapshot_digest"],
            "quote": "This hub has one module.", "locator": "line 4",
        }, "rationale": "Fixture judgment only; not actual source evidence."}],
    }
    return tmp_path, seed_path, packet_path, verdicts, proposals


def run_receipt(bundle, verdicts=None):
    root, seed_path, packet_path, original, _ = bundle
    verdict_path = root / "verdicts.json"
    verdict_path.write_text(json.dumps(original if verdicts is None else verdicts))
    output = root / "docs/content-upgrade/reviews/receipt.json"
    args = ["--repo-root", str(root), "receipt", "--seed", str(seed_path), "--packet", str(packet_path), "--verdicts", str(verdict_path), "--output", str(output)]
    return args, output


def test_supported_independent_output_writes_validator_accepted_receipt(bundle):
    args, output = run_receipt(bundle)
    assert builder.main(args) == 0
    receipt = json.loads(output.read_bytes())
    root, seed_path, _, verdicts, _ = bundle
    assert evaluate_source_acceptance(receipt, page_digest=verdicts["page_digest"], seed_digest=verdicts["seed_digest"], seed_claim_ids=["C001"]) == {
        "schema": "kubedojo.source_acceptance.v1", "accepted": True, "reasons": [],
    }
    ledger = root / "docs/content-upgrade/page-reviews.json"
    before = ledger.read_bytes()
    assert builder.check(root, seed_path, receipt)["accepted"] is True
    assert ledger.read_bytes() == before
    assert receipt["claims"] == verdicts["claims"]


@pytest.mark.parametrize("family", ["openai", "codex", "unknown", "", "invented"])
def test_equal_alias_or_unknown_verifier_family_refuses_without_file(bundle, family):
    verdicts = copy.deepcopy(bundle[3])
    verdicts["verifier"]["family"] = family
    args, output = run_receipt(bundle, verdicts)
    with pytest.raises(SystemExit) as error:
        builder.main(args)
    assert error.value.code == 1
    assert not output.exists()


@pytest.mark.parametrize("verdict", ["UNSUPPORTED", "CONTRADICTED", "UNREADABLE"])
def test_negative_claim_verdict_refuses_without_partial_receipt(bundle, verdict):
    verdicts = copy.deepcopy(bundle[3])
    verdicts["claims"][0]["verdict"] = verdict
    args, output = run_receipt(bundle, verdicts)
    with pytest.raises(SystemExit) as error:
        builder.main(args)
    assert error.value.code == 1
    assert not output.exists()


def test_missing_claim_id_refuses_without_receipt(bundle):
    verdicts = copy.deepcopy(bundle[3])
    verdicts["claims"] = []
    args, output = run_receipt(bundle, verdicts)
    with pytest.raises(SystemExit) as error:
        builder.main(args)
    assert error.value.code == 1
    assert not output.exists()


@pytest.mark.parametrize("changed", ["page", "seed", "packet"])
def test_stale_page_seed_or_packet_bytes_refuse_without_receipt(bundle, changed):
    root, seed_path, packet_path, _, _ = bundle
    args, output = run_receipt(bundle)
    path = {"page": root / PAGE, "seed": seed_path, "packet": packet_path}[changed]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(SystemExit) as error:
        builder.main(args)
    assert error.value.code == 1
    assert not output.exists()


@pytest.mark.parametrize("defect", ["missing_quote", "wrong_source_digest", "uncaptured_additional_source", "omitted_material", "partial_run"])
def test_incomplete_or_unbound_verifier_evidence_refuses(bundle, defect):
    verdicts = copy.deepcopy(bundle[3])
    if defect == "missing_quote":
        verdicts["claims"][0]["source"]["quote"] = "Absent from source"
    elif defect == "wrong_source_digest":
        verdicts["claims"][0]["source"]["snapshot_digest"] = "sha256:" + "0" * 64
    elif defect == "uncaptured_additional_source":
        extra = copy.deepcopy(verdicts["claims"][0]["source"])
        extra["retrieval_uri"] = "git-object://" + "0" * 40
        verdicts["claims"][0]["additional_sources"] = [extra]
    elif defect == "omitted_material":
        verdicts["coverage_complete"] = False
    else:
        verdicts["run"]["status"] = "partial"
    args, output = run_receipt(bundle, verdicts)
    with pytest.raises(SystemExit):
        builder.main(args)
    assert not output.exists()


def test_internal_snapshot_uses_committed_object_bytes_and_bad_span_refuses(bundle):
    root, seed_path, _, _, proposals = bundle
    data = json.loads(seed_path.read_bytes())
    source = next(iter(data["sources"].values()))
    assert source["snapshot_digest"] == builder.digest((root / PAGE).read_bytes())
    blob = builder.git(root, "rev-parse", f"HEAD:{PAGE}").decode().strip()
    assert source["retrieval_uri"] == f"git-object://{blob}"
    proposals["claims"][0]["claim_text"] = "Not on page"
    with pytest.raises(ValueError, match="span"):
        builder.seed(root, PAGE, proposals)


def test_external_capture_uses_existing_fetcher_and_detects_snapshot_tampering(monkeypatch):
    raw = b"<html><p>Kubernetes source text</p></html>"
    fetch = MagicMock(return_value=({"status": 200, "truncated": False, "final_url": "https://kubernetes.io/docs/", "content_type": "text/html"}, raw))
    monkeypatch.setattr(builder.fetch_citation, "_fetch_once", fetch)
    captured = builder.capture("https://kubernetes.io/docs/")
    fetch.assert_called_once()
    assert captured["snapshot_digest"] == builder.digest(raw)
    assert builder.validate_capture(captured) == "Kubernetes source text"
    captured["text"] = "Invented source text"
    with pytest.raises(ValueError, match="differs"):
        builder.validate_capture(captured)


def test_off_allowlist_capture_requests_grant_before_fetch(monkeypatch):
    fetch = MagicMock()
    monkeypatch.setattr(builder.fetch_citation, "_fetch_once", fetch)
    with pytest.raises(ValueError, match="grant request"):
        builder.capture("https://untrusted.invalid/source")
    fetch.assert_not_called()


@pytest.fixture
def external_bundle(bundle, monkeypatch):
    root, seed_path, packet_path, verdicts, proposals = bundle
    raw = b"<html><nav>Site navigation</nav><main><h1>Source</h1><p>This hub has one module.</p></main><footer>Site footer</footer></html>"
    monkeypatch.setattr(builder.fetch_citation, "_fetch_once", MagicMock(return_value=(
        {"status": 200, "truncated": False, "final_url": "https://kubernetes.io/docs/", "content_type": "text/html"}, raw,
    )))
    captured = builder.capture("https://kubernetes.io/docs/")
    capture_file = root / "capture.json"
    builder.write_json(capture_file, captured)
    proposals["claims"][0].update(kind="external", candidate_sources=[{"capture": str(capture_file)}])
    captures_dir = root / "verifier-evidence"
    data = builder.seed(root, PAGE, proposals, captures_dir)
    seed_path.write_text(json.dumps(data))
    packet = builder.packet(root, seed_path)
    packet_path.write_text(json.dumps(packet))
    verdicts.update(seed_digest=packet["seed_digest"], packet_digest=builder.digest(packet_path.read_bytes()))
    source = next(iter(packet["sources"].values()))
    verdicts["claims"][0]["source"].update(retrieval_uri=source["retrieval_uri"], snapshot_digest=source["snapshot_digest"])
    return bundle, captures_dir, captured


def test_committable_seed_excludes_raw_bytes_and_navigation_but_retains_full_main(external_bundle):
    bundle, captures_dir, captured = external_bundle
    root, seed_path, packet_path, verdicts, _ = bundle
    assert "body_base64" not in seed_path.read_text()
    source = next(iter(json.loads(seed_path.read_bytes())["sources"].values()))
    assert source["text"] == "Source\nThis hub has one module."
    assert source["text_extraction"] == "html-main-v1"
    assert {key: source[key] for key in builder.EXTERNAL_FIELDS} == {key: captured[key] for key in builder.EXTERNAL_FIELDS}
    retained = builder.read_json(builder.capture_path(captures_dir, source))
    assert retained == captured
    assert "body_base64" not in packet_path.read_text()
    receipt = builder.receipt(root, seed_path, packet_path, verdicts, captures_dir)
    assert builder.check(root, seed_path, receipt)["accepted"] is True
    assert "requires retained capture" in builder.check(root, seed_path, receipt)["raw_byte_verification"]


@pytest.mark.parametrize("primary", ["internal", "external"])
def test_mixed_claim_builds_seed_packet_and_unchanged_receipt(external_bundle, primary):
    bundle, captures_dir, captured = external_bundle
    root, seed_path, packet_path, verdicts, proposals = bundle
    proposals["claims"][0].update(kind="mixed", candidate_sources=[
        {"path": PAGE}, {"capture": str(root / "capture.json")},
    ])
    data = builder.seed(root, PAGE, proposals, captures_dir)
    seed_path.write_text(json.dumps(data))
    packet = builder.packet(root, seed_path)
    packet_path.write_text(json.dumps(packet))
    blob = builder.git(root, "rev-parse", f"HEAD:{PAGE}").decode().strip()
    refs = [f"git-object://{blob}", captured["retrieval_uri"]]
    assert data["claims"][0]["kind"] == "mixed"
    assert data["claims"][0]["candidate_source_refs"] == refs
    assert packet["claims"] == data["claims"]
    assert packet["sources"][refs[0]]["text"] == (root / PAGE).read_text()
    assert data["sources"][refs[0]]["snapshot_digest"] == builder.digest((root / PAGE).read_bytes())
    assert data["sources"][refs[1]] == builder.compact_source(captured)
    assert builder.read_json(builder.capture_path(captures_dir, data["sources"][refs[1]])) == captured
    verdicts.update(seed_digest=packet["seed_digest"], packet_digest=builder.digest(packet_path.read_bytes()))
    selected = [{
        "retrieval_uri": uri, "snapshot_digest": packet["sources"][uri]["snapshot_digest"],
        "quote": "This hub has one module.", "locator": "source text",
    } for uri in refs]
    if primary == "external":
        selected.reverse()
    verdicts["claims"][0].update(source=selected[0], additional_sources=selected[1:])
    receipt = builder.receipt(root, seed_path, packet_path, verdicts, captures_dir)
    assert receipt["claims"] == verdicts["claims"]
    assert receipt["schema"] == "kubedojo.source_acceptance.v1"
    assert builder.check(root, seed_path, receipt)["accepted"] is True


@pytest.mark.parametrize("kind", ["internal", "external"])
def test_mixed_claim_requires_both_source_kinds_in_seed_and_packet(external_bundle, kind):
    bundle, captures_dir, _ = external_bundle
    root, seed_path, _, _, proposals = bundle
    candidate = {"path": PAGE} if kind == "internal" else {"capture": str(root / "capture.json")}
    proposals["claims"][0].update(kind="mixed", candidate_sources=[candidate])
    with pytest.raises(ValueError, match="mixed claim requires both"):
        builder.seed(root, PAGE, proposals, captures_dir)
    proposals["claims"][0]["kind"] = kind
    data = builder.seed(root, PAGE, proposals, captures_dir)
    data["claims"][0]["kind"] = "mixed"
    seed_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="mixed claim requires both"):
        builder.packet(root, seed_path)


@pytest.mark.parametrize("candidate", [None, {}, {"url": "https://kubernetes.io/docs/"},
                                      {"path": PAGE, "capture": "capture.json"},
                                      {"path": PAGE, "extra": True}])
def test_mixed_claim_refuses_other_candidate_shapes(bundle, candidate):
    root, _, _, _, proposals = bundle
    proposals["claims"][0].update(kind="mixed", candidate_sources=[candidate])
    with pytest.raises(ValueError, match="candidate must contain exactly"):
        builder.seed(root, PAGE, proposals)


@pytest.mark.parametrize("fixture,wrong_kind", [("bundle", "external"), ("external_bundle", "internal")])
def test_legacy_claim_kind_still_validates_and_refuses_mismatched_sources(request, fixture, wrong_kind):
    value = request.getfixturevalue(fixture)
    bundle = value[0] if fixture == "external_bundle" else value
    root, seed_path, packet_path, _, proposals = bundle
    assert builder.packet(root, seed_path) == builder.read_json(packet_path)
    data = builder.read_json(seed_path)
    data["claims"][0]["kind"] = wrong_kind
    seed_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="source kind mismatch"):
        builder.packet(root, seed_path)
    proposals["claims"][0]["kind"] = wrong_kind
    with pytest.raises(ValueError, match="source kind mismatch"):
        builder.seed(root, PAGE, proposals)


@pytest.mark.parametrize("defect", ["raw_bytes", "text", "status", "truncated", "missing_capture", "missing_directory"])
def test_receipt_reverifies_retained_capture_before_accepting(external_bundle, defect, capsys):
    bundle, captures_dir, captured = external_bundle
    root, seed_path, packet_path, verdicts, _ = bundle
    source = next(iter(builder.read_json(seed_path)["sources"].values()))
    retained = builder.capture_path(captures_dir, source)
    if defect == "raw_bytes":
        captured["body_base64"] = base64.b64encode(b"tampered raw response").decode()
    elif defect == "text":
        captured["text"] = "Invented text"
    elif defect == "status":
        captured["status"] = 503
    elif defect == "truncated":
        captured["truncated"] = True
    elif defect == "missing_capture":
        retained.unlink()
    else:
        captures_dir = None
    if defect not in {"missing_capture", "missing_directory"}:
        retained.write_text(json.dumps(captured))
    args, output = run_receipt(bundle, verdicts)
    if captures_dir is not None:
        args += ["--captures-dir", str(captures_dir)]
    with pytest.raises(SystemExit) as error:
        builder.main(args)
    assert error.value.code == 1
    if defect == "raw_bytes":
        assert "source snapshot digest is stale" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("defect", ["quote", "source_digest", "missing_claim", "family", "negative"])
def test_compact_check_preserves_source_and_judgment_refusals(external_bundle, defect):
    bundle, captures_dir, _ = external_bundle
    root, seed_path, packet_path, verdicts, _ = bundle
    receipt = builder.receipt(root, seed_path, packet_path, verdicts, captures_dir)
    if defect == "quote":
        receipt["claims"][0]["source"]["quote"] = "Site navigation"
    elif defect == "source_digest":
        receipt["claims"][0]["source"]["snapshot_digest"] = builder.digest(b"other")
    elif defect == "missing_claim":
        receipt["claims"] = []
    elif defect == "family":
        receipt["verifier"]["family"] = "codex"
    else:
        receipt["claims"][0]["verdict"] = "UNSUPPORTED"
    with pytest.raises(ValueError):
        builder.check(root, seed_path, receipt)


def test_legacy_embedded_capture_seed_requires_regeneration(external_bundle):
    bundle, _, captured = external_bundle
    root, seed_path, _, _, _ = bundle
    data = builder.read_json(seed_path)
    data["sources"][captured["retrieval_uri"]] = captured
    seed_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="legacy seed contains body_base64; regenerate"):
        builder.packet(root, seed_path)


@pytest.mark.parametrize("content_type,raw,expected", [
    ("text/plain", b"Complete plain text", "Complete plain text"),
    ("text/html", b"<html><p>Complete HTML without main</p></html>", "Complete HTML without main"),
])
def test_compact_text_falls_back_to_full_extraction(monkeypatch, content_type, raw, expected):
    monkeypatch.setattr(builder.fetch_citation, "_fetch_once", MagicMock(return_value=(
        {"status": 200, "truncated": False, "final_url": "https://kubernetes.io/docs/", "content_type": content_type}, raw,
    )))
    compact = builder.compact_source(builder.capture("https://kubernetes.io/docs/"))
    assert compact["text"] == expected
    assert compact["text_extraction"] == "full-v1"


@pytest.mark.parametrize("status,truncated", [(503, False), (200, True)])
def test_capture_refuses_non_200_or_truncated_response(monkeypatch, status, truncated):
    monkeypatch.setattr(builder.fetch_citation, "_fetch_once", MagicMock(return_value=(
        {"status": status, "truncated": truncated}, b"unusable capture",
    )))
    with pytest.raises(ValueError, match="failed or truncated"):
        builder.capture("https://kubernetes.io/docs/")


@pytest.fixture
def deployed(bundle, monkeypatch):
    root = bundle[0]
    head = builder.git(root, "rev-parse", "HEAD").decode().strip()
    state = {"head": head, "conclusion": "success", "state": "success"}
    def gh(*args):
        if args[0] == "run":
            return {"headSha": state["head"], "conclusion": state["conclusion"], "status": "completed", "url": "https://github.com/fixture/site/actions/runs/123"}
        endpoint = args[1]
        if "deployments?" in endpoint:
            return [{"id": 1, "sha": state["head"]}]
        if endpoint.endswith("statuses"):
            return [{"state": state["state"], "log_url": "https://github.com/fixture/site/actions/runs/123/job/4", "environment_url": "https://fixture.github.io/"}]
        if endpoint.endswith("pages"):
            return {"html_url": "https://fixture.github.io/"}
        raise AssertionError(args)
    monkeypatch.setattr(smoke, "gh_json", gh)
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.geturl.return_value = "https://fixture.github.io/prerequisites/pilot/"
    response.headers = {"Content-Type": "text/html"}
    response.read.return_value = b"<html>Pilot</html>"
    monkeypatch.setattr(smoke.urllib.request, "urlopen", MagicMock(return_value=response))
    return root, state, response


@pytest.mark.parametrize("defect", ["non_200", "deploy_head_mismatch", "failed_run", "missing_string", "redirect"])
def test_smoke_refuses_non_200_head_mismatch_failed_run_or_html_mismatch(deployed, monkeypatch, defect):
    root, state, response = deployed
    if defect == "non_200":
        response.status = 503
    elif defect == "deploy_head_mismatch":
        original = smoke.git
        monkeypatch.setattr(smoke, "git", lambda *args: b"Different deployed page" if args[1] == "show" else original(*args))
    elif defect == "failed_run":
        state["conclusion"] = "failure"
    elif defect == "missing_string":
        response.read.return_value = b"<html>Other page</html>"
    else:
        response.geturl.return_value = "https://fixture.github.io/"
    output = root / "docs/content-upgrade/reviews/smoke.json"
    with pytest.raises(SystemExit) as error:
        smoke.main(["--repo-root", str(root), "--repository", "fixture/site", "--page", PAGE, "--expect", "Pilot", "--output", str(output)])
    assert error.value.code == 1
    assert not output.exists()


def test_smoke_records_exact_html_and_successful_live_deployment(deployed):
    root, state, _ = deployed
    value = smoke.record(root, PAGE, ["Pilot"], "fixture/site")
    http = value["publication"]["http"]
    assert http["checks"] == {"Pilot": True}
    assert http["status"] == 200
    assert http["html_sha256"] == builder.digest(b"<html>Pilot</html>").removeprefix("sha256:")
    assert http["deployment"]["headSha"] == state["head"]
    assert value["page_digest"] == builder.digest((root / PAGE).read_bytes())
