"""Build a deterministic, read-only inventory of KubeDojo content pages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
DISPOSITIONS = {"retain", "revise", "expand"}
STATUS_VALUES = {"pending", "pass", "fail", "unknown", "not_applicable"}
EVIDENCE_LAYERS = (
    "page_presence",
    "structural_checks",
    "technical_source",
    "editorial_review",
    "lab_execution",
    "translation_fidelity",
    "deployed_smoke",
    "learner_data",
)


def _frontmatter(text: str) -> tuple[dict[str, Any], list[str]]:
    """Parse leading YAML without inferring a route from the file path."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["missing frontmatter"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["unterminated frontmatter"]
    try:
        value = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        return {}, [f"invalid frontmatter: {exc.__class__.__name__}"]
    if not isinstance(value, dict):
        return {}, ["frontmatter is not a mapping"]
    return value, []


def _locale(rel: Path) -> str:
    return "uk" if rel.parts and rel.parts[0] == "uk" else "en"


def _source_section(rel: Path, locale: str) -> str:
    parts = rel.parts[1:] if locale == "uk" else rel.parts
    return Path(*parts[:-1]).as_posix() if len(parts) > 1 else ""


def _page_type(rel: Path) -> str:
    if rel.name in {"index.md", "index.mdx"}:
        return "hub"
    if rel.stem.startswith("module-"):
        return "module"
    if rel.stem.startswith("ch-") and "ai-history" in rel.parts:
        return "chapter"
    if "lab" in rel.parts or rel.stem.startswith("lab-"):
        return "lab"
    return "page"


def _expected_counterpart(rel: Path, locale: str) -> str:
    if locale == "uk":
        return Path(*rel.parts[1:]).as_posix()
    return Path("uk", rel).as_posix()


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _unknown_evidence(receipt_status: str) -> dict[str, Any]:
    return {
        "receipt_status": receipt_status,
        "status_source": "unknown",
        "disposition": None,
        "reviewer_refs": [],
        "evidence_refs": [],
        "independent_statuses": {layer: "unknown" for layer in EVIDENCE_LAYERS},
    }


def _normalise_digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if len(value) == 64:
        value = f"sha256:{value}"
    if len(value) != 71 or not value.startswith("sha256:"):
        return None
    return value if all(char in "0123456789abcdef" for char in value[7:]) else None


def _receipt_evidence(receipt: Any, page_digest: str) -> tuple[dict[str, Any], str]:
    """Validate one receipt; invalid input can never retain a passing status."""
    if not isinstance(receipt, dict):
        return _unknown_evidence("invalid"), "receipt is not an object"
    supplied_value = receipt.get("page_digest", receipt.get("source_digest", receipt.get("digest")))
    if _normalise_digest(supplied_value) != page_digest:
        supplied = _normalise_digest(supplied_value)
        if supplied is None:
            return _unknown_evidence("invalid"), "missing or invalid page_digest"
        return _unknown_evidence("stale"), "page_digest does not match source"

    disposition = receipt.get("disposition")
    if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
        return _unknown_evidence("invalid"), "disposition must be retain, revise, or expand"
    statuses = receipt.get("independent_statuses", receipt.get("statuses"))
    if not isinstance(statuses, dict):
        return _unknown_evidence("invalid"), "independent_statuses must be an object"
    if any(not isinstance(key, str) or key not in EVIDENCE_LAYERS for key in statuses):
        return _unknown_evidence("invalid"), "independent statuses contain an unknown layer"
    if any(not isinstance(value, str) or value not in STATUS_VALUES for value in statuses.values()):
        return _unknown_evidence("invalid"), "independent statuses contain an invalid value"
    refs = {}
    for key in ("reviewer_refs", "evidence_refs"):
        value = receipt.get(key, [])
        if not isinstance(value, list) or not value or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            return _unknown_evidence("invalid"), f"{key} must be a list of non-empty strings"
        refs[key] = value
    merged_statuses = {layer: "unknown" for layer in EVIDENCE_LAYERS}
    merged_statuses.update(statuses)
    return {
        "receipt_status": "current",
        "status_source": "supplied_receipt",
        "disposition": disposition,
        "reviewer_refs": refs["reviewer_refs"],
        "evidence_refs": refs["evidence_refs"],
        "independent_statuses": merged_statuses,
    }, ""


def _load_receipts(path: Path | None) -> tuple[dict[str, Any], list[str], bool]:
    if path is None:
        return {}, [], False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"evidence input unavailable or invalid: {exc.__class__.__name__}"], True
    records = payload.get("pages") if isinstance(payload, dict) else None
    if isinstance(records, list):
        entries = records
    elif isinstance(records, dict):
        entries = [dict(value, path=key) if isinstance(value, dict) else value for key, value in records.items()]
    else:
        return {}, ["evidence input must contain pages as a list or object"], True
    receipts: dict[str, Any] = {}
    errors: list[str] = []
    for entry in entries:
        key = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(key, str) or not key or Path(key).is_absolute() or ".." in Path(key).parts:
            errors.append("evidence input contains an invalid page path")
            continue
        if key in receipts:
            errors.append(f"duplicate evidence receipt: {key}")
            receipts[key] = None
        else:
            receipts[key] = entry
    return receipts, errors, False


def _infer_seeds_dir(docs_root: Path) -> Path | None:
    root = docs_root.resolve()
    if root.parts[-3:] == ("src", "content", "docs"):
        return root.parents[2] / "docs" / "citation-seeds"
    return None


def _bind_source_acceptance():
    try:
        from . import source_acceptance as sa
    except ImportError:
        import importlib
        import sys
        import types

        quality_dir = Path(__file__).resolve().parent
        pkg = sys.modules.setdefault("quality", types.ModuleType("quality"))
        pkg.__path__ = [str(quality_dir)]
        sa = importlib.import_module("quality.source_acceptance")
    return sa.apply_source_acceptance, sa.bind_source_acceptance, sa.load_seed_bytes, sa.nested_source_receipt


def build_inventory(
    docs_root: Path,
    evidence_path: Path | None = None,
    *,
    seeds_dir: Path | None = None,
) -> dict[str, Any]:
    """Return inventory JSON data without writing files or changing runtime state."""
    docs_root = docs_root.resolve()
    if not docs_root.is_dir():
        return {
            "schema": "kubedojo.content_inventory.v1",
            "docs_root": str(docs_root),
            "page_count": 0,
            "pages": [],
            "new_pages": [],
            "missing_pages": [],
            "stale_receipts": [],
            "invalid_receipts": [],
            "receipt_errors": [],
            "errors": ["docs_root does not exist or is not a directory"],
        }
    source_paths = sorted(
        (path for path in docs_root.rglob("*") if path.is_file() and path.suffix in {".md", ".mdx"}),
        key=lambda path: path.relative_to(docs_root).as_posix(),
    )
    rel_paths = {path.relative_to(docs_root).as_posix() for path in source_paths}
    receipts, receipt_errors, invalid_input = _load_receipts(evidence_path)
    apply_sa, bind_sa, load_seed, nested_receipt = _bind_source_acceptance()
    seed_root = seeds_dir if seeds_dir is not None else _infer_seeds_dir(docs_root)
    pages: list[dict[str, Any]] = []

    for path in source_paths:
        rel = path.relative_to(docs_root)
        locale = _locale(rel)
        expected = _expected_counterpart(rel, locale)
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
        frontmatter, source_warnings = _frontmatter(text)
        route = frontmatter.get("slug")
        route = route.strip() if isinstance(route, str) and route.strip() else None
        page = {
            "path": rel.as_posix(),
            "locale": locale,
            "type": _page_type(rel),
            "section": _source_section(rel, locale),
            "source_digest": _digest(raw),
            "counterpart": expected if expected in rel_paths else None,
            "counterpart_expected": expected,
            "counterpart_present": expected in rel_paths,
            "source_route": route,
            "route_source": "frontmatter.slug" if route is not None else None,
            "route_validation": "not_checked",
            "source_warnings": source_warnings,
        }
        if invalid_input:
            page["evidence"] = _unknown_evidence("invalid")
        elif evidence_path is None or rel.as_posix() not in receipts:
            page["evidence"] = _unknown_evidence("missing")
        elif receipts[rel.as_posix()] is None:
            page["evidence"] = _unknown_evidence("invalid")
        else:
            evidence, error = _receipt_evidence(receipts[rel.as_posix()], page["source_digest"])
            page["evidence"] = evidence
            if error:
                receipt_errors.append(f"{rel.as_posix()}: {error}")
        entry = None if invalid_input else receipts.get(rel.as_posix())
        apply_sa(
            page["evidence"],
            bind_sa(
                nested_receipt(entry),
                page_bytes=raw,
                seed_bytes=load_seed(seed_root, rel.as_posix()),
            ),
        )
        pages.append(page)

    receipt_paths = set(receipts)
    return {
        "schema": "kubedojo.content_inventory.v1",
        "docs_root": str(docs_root),
        "page_count": len(pages),
        "pages": pages,
        "new_pages": sorted(rel_paths - receipt_paths) if evidence_path is not None and not invalid_input else [],
        "missing_pages": sorted(receipt_paths - rel_paths) if evidence_path is not None and not invalid_input else [],
        "stale_receipts": sorted(
            page["path"] for page in pages if page["evidence"]["receipt_status"] == "stale"
        ),
        "invalid_receipts": sorted(
            page["path"] for page in pages if page["evidence"]["receipt_status"] == "invalid"
        ),
        "receipt_errors": sorted(receipt_errors),
        "errors": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-root", type=Path, default=DEFAULT_DOCS_ROOT)
    parser.add_argument("--evidence", "--evidence-json", type=Path)
    args = parser.parse_args(argv)
    report = build_inventory(args.docs_root, args.evidence)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
