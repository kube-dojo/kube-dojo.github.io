"""Fail-closed fixtures for #2310. Prove the validator, not real source support."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.quality.source_acceptance import SCHEMA, SCHEMA_VERSION, evaluate_source_acceptance

PAGE, SEED, SNAP = "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64


def _valid(**changes: object) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema": SCHEMA, "schema_version": SCHEMA_VERSION,
        "page_digest": PAGE, "seed_digest": SEED, "disposition": "applicable",
        "coverage": {"material_claim_ids": ["C001"], "reviewed_claim_ids": ["C001"], "uncovered_claim_ids": []},
        "claims": [{"claim_id": "C001", "verdict": "SUPPORTED",
                    "source": {"retrieval_uri": "https://example.test/src", "snapshot_digest": SNAP}}],
        "author": {"family": "openai"}, "verifier": {"identity": "agy", "family": "google"},
        "run": {"status": "complete", "identity": "verify-example-C001-000000Z"},
    }
    receipt.update(changes)
    return receipt


def _eval(receipt: object, **kwargs: object) -> dict[str, object]:
    args: dict[str, object] = {"page_digest": PAGE, "seed_digest": SEED, "seed_claim_ids": ("C001",)}
    args.update(kwargs)
    return evaluate_source_acceptance(receipt, **args)  # type: ignore[arg-type]


def _verdict(verdict: str) -> dict[str, object]:
    receipt = _valid()
    receipt["claims"][0]["verdict"] = verdict  # type: ignore[index]
    return receipt


def test_valid_complete_path_is_not_real_source_proof() -> None:
    assert _eval(_valid()) == {"schema": SCHEMA, "accepted": True, "reasons": []}


def test_frontmatter_and_injection_cannot_bypass() -> None:
    assert not _eval({"citations_verified": True, "source_acceptance": "accepted"})["accepted"]
    assert _eval(_valid(citations_verified=False))["accepted"]


@pytest.mark.parametrize(("receipt", "kwargs", "needle"), [
    (None, {}, "receipt_missing"),
    ("{", {}, "receipt_malformed"),
    ([], {}, "receipt_not_object"),
    (_valid(schema="other.v1"), {}, "schema_invalid"),
    (_valid(schema_version=2), {}, "schema_invalid"),
    (_valid(page_digest="sha256:" + "d" * 64), {}, "page_digest_stale"),
    (_valid(seed_digest="sha256:" + "d" * 64), {}, "seed_digest_stale"),
    (_valid(coverage={"material_claim_ids": [], "reviewed_claim_ids": [], "uncovered_claim_ids": []}), {}, "coverage_empty"),
    (_valid(claims=[]), {}, "coverage_empty"),
    (_valid(coverage={"material_claim_ids": ["C001"], "reviewed_claim_ids": [], "uncovered_claim_ids": ["C001"]}), {}, "coverage_incomplete"),
    (_verdict("UNSUPPORTED"), {}, "claim_verdict:UNSUPPORTED"),
    (_verdict("CONTRADICTED"), {}, "claim_verdict:CONTRADICTED"),
    (_verdict("UNREADABLE"), {}, "claim_verdict:UNREADABLE"),
    (_valid(run={"status": "failed", "identity": "run-1"}), {}, "run_status:failed"),
    (_valid(run={"status": "partial", "identity": "run-1"}), {}, "run_status:partial"),
    (_valid(author={"family": "google"}, verifier={"identity": "agy", "family": "google"}), {}, "reviewer_not_independent"),
    (_valid(verifier={"identity": "agy", "family": "unknown"}), {}, "reviewer_not_independent"),
    (_valid(disposition="not_applicable"), {}, "disposition_not_applicable"),
    (_valid(), {"seed_claim_ids": ("C001", "C002")}, "coverage_omitted"),
    ({"page_digest": PAGE, "disposition": "retain", "independent_statuses": {"technical_source": "pass"}}, {}, "schema_invalid"),
])
def test_fail_closed_adversarial_receipts(receipt: object, kwargs: dict[str, object], needle: str) -> None:
    result = _eval(receipt, **kwargs)
    assert result["accepted"] is False
    assert needle in result["reasons"]
