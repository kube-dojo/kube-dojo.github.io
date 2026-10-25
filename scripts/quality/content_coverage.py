"""All-page receipt coverage; recorded review is not full-page clearance."""

from pathlib import Path

from .content_inventory import _load_receipts, build_inventory

FIELDS = ("total", "review_recorded", "unreviewed", "needs_revision", "acceptance_recorded", "stale", "invalid")
CAVEAT = (
    "Review recorded means a current schema/digest-valid supplied disposition, not exhaustive "
    "full-page clearance. Acceptance requires explicit lead acceptance references and applicable "
    "passing evidence. Program statuses are supplied assertions, not lifecycle or book unlocks."
)


def coverage_summary(repo_root: Path) -> dict:
    report = build_coverage(repo_root)
    return {"endpoint": "/api/content/coverage", **{key: report[key] for key in
            ("status", "coverage_health", "locales", "milestones", "caveat", "parked_locales")}}


def build_coverage(repo_root: Path) -> dict:
    """Aggregate the canonical inventory, preserving independent source validation."""
    evidence_path = repo_root / "docs/content-upgrade/page-reviews.json"
    errors = []
    try:
        inventory = build_inventory(repo_root / "src/content/docs", evidence_path=evidence_path)
    except (OSError, UnicodeError) as exc:
        inventory = {"pages": [], "errors": [f"inventory unavailable: {type(exc).__name__}"]}
    receipts, load_errors, unavailable = _load_receipts(evidence_path)
    errors.extend(inventory.get("errors", []))
    receipt_errors = sorted(set(inventory.get("receipt_errors", []) + load_errors))
    locales = {locale: dict.fromkeys(FIELDS, 0) for locale in ("en", "uk")}
    tracks = {locale: {} for locale in locales}
    sections = {locale: {} for locale in locales}
    milestone = dict.fromkeys(FIELDS, 0)
    for page in inventory["pages"]:
        locale, section, evidence = page["locale"], page["section"], page["evidence"]
        track = section.split("/")[0] if section else "shared"
        current = evidence["receipt_status"] == "current"
        receipt = receipts.get(page["path"]) or {}
        refs = receipt.get("acceptance_refs")
        explicit = isinstance(refs, list) and bool(refs) and all(isinstance(r, str) and r.strip() for r in refs)
        statuses = evidence["independent_statuses"]
        required = ["page_presence", "structural_checks", "technical_source", "editorial_review", "deployed_smoke"]
        if locale == "uk":
            required.append("translation_fidelity")
        accepted = (current and evidence["disposition"] == "retain" and explicit
                    and all(statuses[k] == "pass" for k in required)
                    and statuses["lab_execution"] in {"pass", "not_applicable"})
        values = dict(zip(FIELDS, (1, int(current), int(not current),
                      int(current and evidence["disposition"] in {"revise", "expand"}),
                      int(bool(accepted)), int(evidence["receipt_status"] == "stale"),
                      int(evidence["receipt_status"] == "invalid")), strict=True))
        buckets = [locales[locale], tracks[locale].setdefault(track, dict.fromkeys(FIELDS, 0)),
                   sections[locale].setdefault(section or "shared", dict.fromkeys(FIELDS, 0))]
        if locale == "en" and track in {"prerequisites", "linux"}:
            buckets.append(milestone)
        for bucket in buckets:
            for key, value in values.items():
                bucket[key] += value
    missing = inventory.get("missing_pages", [])
    unknown = bool(errors or receipt_errors or missing)
    attention = (unknown or locales["en"]["unreviewed"] or locales["en"]["needs_revision"]
                 or locales["en"]["acceptance_recorded"] < locales["en"]["total"])
    return {
        "schema": "kubedojo.content_coverage.v1", "caveat": CAVEAT,
        "status": "unavailable" if unavailable or errors else "needs_attention" if attention else "ok",
        "coverage_health": "unknown" if unknown else "known",
        "locales": locales, "tracks": tracks, "sections": sections,
        "milestones": {"prerequisites_linux": milestone}, "parked_locales": ["uk"],
        "errors": errors, "receipt_errors": receipt_errors, "missing_pages": missing,
        "new_pages": inventory.get("new_pages", []),
    }
