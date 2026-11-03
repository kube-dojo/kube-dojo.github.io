"""Offline defect cases for receipt production and deployed-smoke refusal."""

import copy
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
