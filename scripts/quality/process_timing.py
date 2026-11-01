"""Revision-bound elapsed process time; never changes acceptance decisions."""
import json
import re
from datetime import datetime, timezone

SCOPES = {
    "partial_since_timer_introduced": "Partial: measured since timing began",
    "complete_new_workflow_cycle_with_prepared_draft_input": "Cycle with earlier prepared draft input",
    "full_from_first_recorded_preparation": "From first recorded preparation; overlaps another page's queue",
}


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def process_times(lines, pages, receipts, now=None):
    """Use the latest recorded start; malformed records cannot promote a page."""
    now = now or datetime.now(timezone.utc)
    cycles = {}
    for line in lines:
        try:
            event = json.loads(line)
        except (ValueError, TypeError, RecursionError):
            continue
        if not isinstance(event, dict) or not isinstance(event.get("module"), str):
            continue
        module, kind = event["module"], event.get("event")
        if kind == "start":
            cycles[module] = {"start": event, "end": None, "binding": None}
        elif module in cycles and kind in ("end", "acceptance_binding"):
            cycles[module]["end" if kind == "end" else "binding"] = event

    result = {}
    for page in pages:
        path = page.get("path", "")
        module = path.rsplit(".", 1)[0]
        cycle = cycles.get(module)
        if not cycle:
            continue
        start = timestamp(cycle["start"].get("timestamp"))
        scope_key = cycle["start"].get("measurement_scope")
        scope = SCOPES.get(scope_key) if isinstance(scope_key, str) else None
        info = {"status": "not_measured", "elapsed_seconds": None, "scope": scope}
        result[path] = info
        if not start or start > now or not scope:
            continue
        end = timestamp((cycle["end"] or {}).get("timestamp")) if cycle["end"] else None
        if cycle["end"] and (not end or end < start or end > now):
            continue
        if page.get("acceptance_recorded") is not True:
            if not cycle["end"]:
                info.update(status="running", elapsed_seconds=int((now - start).total_seconds()))
            continue
        binding = cycle["binding"] or {}
        receipt = receipts.get(path, {})
        source = receipt.get("source_acceptance", {}) if isinstance(receipt, dict) else {}
        recorded = timestamp(binding.get("recorded_at"))
        if (page.get("receipt_status") == "current" and end and cycle["end"].get("result") == "canonically_accepted"
                and timestamp(binding.get("cycle_started_at")) == start and timestamp(binding.get("ended_at")) == end
                and recorded and end <= recorded <= now and isinstance(source, dict)
                and binding.get("page_digest") == source.get("page_digest") and binding.get("seed_digest") == source.get("seed_digest")
                and all(isinstance(binding.get(key), str) and re.fullmatch(r"sha256:[0-9a-f]{64}", binding[key])
                        for key in ("page_digest", "seed_digest"))):
            info.update(status="completed", elapsed_seconds=int((end - start).total_seconds()))
    return result


def add_process_times(report, repo_root, ledger_path, ledger_version):
    """Refresh additive timing without changing acceptance or trusting stale receipts."""
    try:
        lines = (repo_root / ".agent/module-timing.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        lines = []
    receipts = {}
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        stat = ledger_path.stat()
        if (stat.st_mtime_ns, stat.st_size) == ledger_version:
            receipts = {row["path"]: row for row in ledger["pages"] if isinstance(row, dict) and isinstance(row.get("path"), str)}
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        pass
    times = process_times(lines, report["pages"], receipts)
    report["pages"] = [{**page, "process_time": times.get(page["path"])} for page in report["pages"]]
    return report
