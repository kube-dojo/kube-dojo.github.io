"""Revision-bound source-acceptance receipt (#2310 packet 1).

Only a complete applicable positive receipt can accept. Frontmatter,
injection, and inventory pass strings are not inputs. Fixture-valid
receipts prove validator behavior, not real source support. Read-only:
no status store, no promotion/backfill.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .content_inventory import _normalise_digest

SCHEMA = "kubedojo.source_acceptance.v1"
SCHEMA_VERSION = 1
FAILING_VERDICTS = frozenset({"UNSUPPORTED", "CONTRADICTED", "UNREADABLE"})
UNKNOWN_FAMILIES = frozenset({"", "unknown"})


def _reject(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "accepted": False, "reasons": [reason]}


def _id_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(i, str) or not i.strip() for i in value):
        return None
    return [i.strip() for i in value]


def _family(block: Any) -> str:
    value = block.get("family") if isinstance(block, dict) else None
    return value.strip().lower() if isinstance(value, str) else ""


def _source_ok(source: Any) -> bool:
    uri = source.get("retrieval_uri") if isinstance(source, dict) else None
    digest = source.get("snapshot_digest") if isinstance(source, dict) else None
    return isinstance(uri, str) and bool(uri.strip()) and _normalise_digest(digest) is not None


def evaluate_source_acceptance(
    receipt: Any, *, page_digest: str, seed_digest: str, seed_claim_ids: Sequence[str],
) -> dict[str, Any]:
    """Fail closed unless the receipt is complete, applicable, and positive."""
    if receipt is None:
        return _reject("receipt_missing")
    if isinstance(receipt, (bytes, str)):
        try:
            receipt = json.loads(receipt)
        except (TypeError, UnicodeError, json.JSONDecodeError):
            return _reject("receipt_malformed")
    if not isinstance(receipt, dict):
        return _reject("receipt_not_object")
    if receipt.get("schema") != SCHEMA or receipt.get("schema_version") != SCHEMA_VERSION:
        return _reject("schema_invalid")
    if receipt.get("disposition") != "applicable":
        return _reject("disposition_not_applicable")

    want_page, got_page = _normalise_digest(page_digest), _normalise_digest(receipt.get("page_digest"))
    want_seed, got_seed = _normalise_digest(seed_digest), _normalise_digest(receipt.get("seed_digest"))
    if want_page is None or got_page is None:
        return _reject("page_digest_invalid")
    if got_page != want_page:
        return _reject("page_digest_stale")
    if want_seed is None or got_seed is None:
        return _reject("seed_digest_invalid")
    if got_seed != want_seed:
        return _reject("seed_digest_stale")

    coverage = receipt.get("coverage")
    material = _id_list(coverage.get("material_claim_ids")) if isinstance(coverage, dict) else None
    reviewed = _id_list(coverage.get("reviewed_claim_ids")) if isinstance(coverage, dict) else None
    uncovered = _id_list(coverage.get("uncovered_claim_ids")) if isinstance(coverage, dict) else None
    if material is None or reviewed is None or uncovered is None:
        return _reject("schema_invalid")
    if not material:
        return _reject("coverage_empty")
    if uncovered or set(reviewed) != set(material):
        return _reject("coverage_incomplete")
    expected = [c.strip() for c in seed_claim_ids if isinstance(c, str) and c.strip()]
    if set(expected) - set(material):
        return _reject("coverage_omitted")

    claims = receipt.get("claims")
    if not isinstance(claims, list) or not claims:
        return _reject("coverage_empty")
    seen: set[str] = set()
    for claim in claims:
        cid = claim.get("claim_id") if isinstance(claim, dict) else None
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            return _reject("schema_invalid")
        seen.add(cid)
        verdict = claim.get("verdict")
        if verdict in FAILING_VERDICTS:
            return _reject(f"claim_verdict:{verdict}")
        if verdict != "SUPPORTED" or not _source_ok(claim.get("source")):
            return _reject("schema_invalid")
    if set(material) - seen:
        return _reject("coverage_incomplete")

    run = receipt.get("run") if isinstance(receipt.get("run"), dict) else {}
    identity, status = run.get("identity"), run.get("status")
    if not isinstance(identity, str) or not identity.strip():
        return _reject("run_identity_missing")
    if status != "complete":
        return _reject(f"run_status:{status}")

    verifier = receipt.get("verifier")
    verifier_id = verifier.get("identity") if isinstance(verifier, dict) else None
    author_f, verifier_f = _family(receipt.get("author")), _family(verifier)
    if not isinstance(verifier_id, str) or not verifier_id.strip():
        return _reject("schema_invalid")
    if author_f in UNKNOWN_FAMILIES or verifier_f in UNKNOWN_FAMILIES or author_f == verifier_f:
        return _reject("reviewer_not_independent")
    return {"schema": SCHEMA, "accepted": True, "reasons": []}
