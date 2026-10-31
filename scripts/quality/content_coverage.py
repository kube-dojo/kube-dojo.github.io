"""All-page receipt coverage; recorded review is not full-page clearance."""

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from .content_inventory import _load_receipts, build_inventory

FIELDS = ("total", "review_recorded", "unreviewed", "needs_revision", "acceptance_recorded", "stale", "invalid")
CAVEAT = (
    "Review recorded means a current schema/digest-valid supplied disposition, not exhaustive "
    "full-page clearance. acceptance_recorded is a supplied lead assertion; lead references must "
    "cover existing book/source/prose/multiple-family/human gates. This reporter grants none. "
    "Lead references must justify lab not_applicable assertions; other not_applicable layers are not counted. "
    "Program statuses are supplied assertions, not lifecycle or book unlocks."
)
SOURCE_REASONS = frozenset((
    "receipt_missing", "receipt_malformed", "receipt_not_object", "schema_invalid",
    "disposition_not_applicable", "page_digest_invalid", "page_digest_stale",
    "seed_digest_invalid", "seed_digest_stale", "seed_malformed", "coverage_empty",
    "coverage_incomplete", "coverage_omitted", "run_identity_missing", "reviewer_not_independent",
    "claim_verdict:UNSUPPORTED", "claim_verdict:CONTRADICTED", "claim_verdict:UNREADABLE",
    "run_status:failed", "run_status:partial",
))
WORK_STATES = ('preparing', 'prepared', 'awaiting_review', 'reviewing', 'review_failed', 'blocked')


def coverage_ledger(repo_root: Path) -> Path:
    override = os.environ.get('KUBEDOJO_UPGRADE_LEDGER')
    if not override:
        return repo_root / 'docs/content-upgrade/page-reviews.json'
    path = Path(override).resolve()
    relative = path.relative_to((repo_root / '.worktrees').resolve())
    if not Path(override).is_absolute() or len(relative.parts) != 4 or relative.parts[1:] != ('docs', 'content-upgrade', 'page-reviews.json'):
        raise ValueError('invalid worktree ledger path')
    return path


def recorded_work(path: Path, inventory: dict) -> tuple[dict, list]:
    """Validate operational assertions separately from canonical receipt health."""
    errors, records = [], {}
    try:
        data = json.loads(path.read_text(encoding='utf8')).get('work', [])
        if not isinstance(data, list): raise TypeError('work is not a list')
        digests = {page['path']: page['source_digest'] for page in inventory['pages']}
        counts = Counter(r['path'] for r in data if isinstance(r, dict) and isinstance(r.get('path'), str))
        duplicates = {key for key, count in counts.items() if count > 1}
        for row in data:
            key = row.get('path') if isinstance(row, dict) else None
            try:
                if not isinstance(key, str) or key not in digests or key in duplicates: raise ValueError('unknown or duplicate path')
                if set(row) - {'path', 'page_digest', 'state', 'updated_at', 'summary', 'next_action', 'evidence_refs', 'review'}:
                    raise ValueError('unexpected field')
                if row.get('page_digest') != digests[key] or row.get('state') not in WORK_STATES: raise ValueError('stale digest or invalid state')
                for field in ('summary', 'next_action'):
                    if not isinstance(row.get(field), str) or not row[field].strip() or len(row[field]) > 500: raise ValueError('invalid text')
                refs = row.get('evidence_refs')
                if not isinstance(refs, list) or not refs or len(refs) > 30 or any(not isinstance(x, str) or not x.strip() or len(x) > 1000 for x in refs): raise ValueError('invalid references')
                timestamp = datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                if timestamp.tzinfo is None: raise ValueError('timestamp lacks timezone')
                review = row.get('review', {})
                if not isinstance(review, dict) or set(review) - {'spent', 'ceiling'} or any(v is not None and (type(v) is not int or v < 0) for v in review.values()): raise ValueError('invalid review counts')
                records[key] = {k: row[k] for k in ('state', 'updated_at', 'summary', 'next_action', 'evidence_refs')}
                records[key]['review'] = {k: review.get(k) for k in ('spent', 'ceiling')}
            except (ValueError, KeyError, TypeError, AttributeError):
                errors.append(f'invalid or stale work record: {key[:200] if isinstance(key, str) else "unknown path"}')
    except (OSError, UnicodeError, ValueError, AttributeError, TypeError):
        errors.append('work records unavailable or malformed')
    return records, errors


def build_coverage(repo_root: Path) -> dict:
    """Aggregate the canonical inventory, preserving independent source validation."""
    evidence_path = coverage_ledger(repo_root)
    errors = []
    try:
        inventory = build_inventory(repo_root / "src/content/docs", evidence_path=evidence_path)
        receipts, load_errors, unavailable = _load_receipts(evidence_path)
    except (OSError, UnicodeError, TypeError, ValueError, AttributeError, KeyError, ImportError, RuntimeError) as exc:
        inventory = {"pages": [], "errors": [f"inventory unavailable: {type(exc).__name__}"]}
        receipts, load_errors, unavailable = {}, [], True
    errors.extend(inventory.get("errors", []))
    receipt_errors = sorted(set(inventory.get("receipt_errors", []) + load_errors))
    work, work_errors = recorded_work(evidence_path, inventory)
    work_summary = dict.fromkeys((*WORK_STATES, 'accepted', 'parked', 'unknown'), 0)
    locales = {locale: dict.fromkeys(FIELDS, 0) for locale in ("en", "uk")}
    tracks = {locale: {} for locale in locales}
    sections = {locale: {} for locale in locales}
    milestone = dict.fromkeys(FIELDS, 0)
    pages = []
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
        item = work.get(page['path'], {'state': 'unknown', 'summary': None, 'next_action': None,
                                     'evidence_refs': [], 'updated_at': None, 'review': {'spent': None, 'ceiling': None}})
        item = {**item, 'state': 'accepted' if accepted else 'parked' if locale == 'uk' else item['state']}
        work_summary[item['state']] += 1
        values = dict(zip(FIELDS, (1, int(current), int(not current),
                      int(current and evidence["disposition"] in {"revise", "expand"}),
                      int(bool(accepted)), int(evidence["receipt_status"] == "stale"),
                      int(evidence["receipt_status"] == "invalid")), strict=True))
        reasons = [f"{key}: {statuses[key]}" for key in required if statuses[key] != "pass"]
        reasons += [f"source: {reason if reason in SOURCE_REASONS else 'invalid_or_unknown'}"
                    for reason in evidence["source_acceptance"].get("reasons", [])]
        if not current:
            reasons.append(f"receipt: {evidence['receipt_status']}")
        if evidence["disposition"] != "retain":
            reasons.append(f"disposition: {evidence['disposition'] or 'unknown'}")
        if not explicit:
            reasons.append("no valid lead acceptance references")
        if statuses["lab_execution"] not in {"pass", "not_applicable"}:
            reasons.append(f"lab_execution: {statuses['lab_execution']}")
        pages.append({
            "path": page["path"], "locale": locale, "type": page["type"],
            "receipt_status": evidence["receipt_status"], "disposition": evidence["disposition"],
            **{key: bool(values[key]) for key in FIELDS[1:]},
            "layers": statuses, "reasons": reasons,
            "work": item,
            "references": {key: [ref[:1000] for ref in receipt.get(key, []) if isinstance(ref, str)][:30]
                           if isinstance(receipt.get(key), list) else []
                           for key in ("reviewer_refs", "evidence_refs", "acceptance_refs")},
        })
        buckets = [locales[locale], tracks[locale].setdefault(track, dict.fromkeys(FIELDS, 0)),
                   sections[locale].setdefault(section or "shared", dict.fromkeys(FIELDS, 0))]
        if locale == "en" and track in {"prerequisites", "linux"}:
            buckets.append(milestone)
        for bucket in buckets:
            for key, value in values.items():
                bucket[key] += value
    missing = inventory.get("missing_pages", [])
    if not locales["en"]["total"]:
        errors.append("English corpus unavailable or empty")
    unknown = bool(errors or receipt_errors or missing)
    attention = (unknown or locales["en"]["unreviewed"] or locales["en"]["needs_revision"]
                 or locales["en"]["acceptance_recorded"] < locales["en"]["total"])
    return {
        "schema": "kubedojo.content_coverage.v1", "caveat": CAVEAT,
        "status": "unavailable" if unavailable or errors else "needs_attention" if attention else "ok",
        "coverage_health": "unknown" if unknown else "known",
        "locales": locales, "tracks": tracks, "sections": sections, "pages": pages,
        "milestones": {"prerequisites_linux": milestone}, "parked_locales": ["uk"],
        "errors": errors, "receipt_errors": receipt_errors, "missing_pages": missing,
        "new_pages": inventory.get("new_pages", []),
        "work_summary": work_summary, "work_errors": work_errors,
    }
