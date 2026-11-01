import json
from datetime import datetime, timezone

from quality.process_timing import add_process_times, process_times

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
PAGE = {"path": "a.md", "receipt_status": "current", "acceptance_recorded": False}
DIGEST = "sha256:" + "a" * 64
SEED = "sha256:" + "b" * 64
START = {"module": "a", "event": "start", "timestamp": "2026-01-01T10:00:00Z", "measurement_scope": "partial_since_timer_introduced"}
END = {"module": "a", "event": "end", "timestamp": "2026-01-01T11:00:00Z", "result": "canonically_accepted"}
BIND = {"module": "a", "event": "acceptance_binding", "cycle_started_at": START["timestamp"], "ended_at": END["timestamp"], "recorded_at": END["timestamp"], "page_digest": DIGEST, "seed_digest": SEED}
RECEIPTS = {"a.md": {"source_acceptance": {"page_digest": DIGEST, "seed_digest": SEED}}}


def timing(events, page=PAGE, receipts=RECEIPTS):
    return process_times([json.dumps(event) for event in events], [page], receipts, NOW)["a.md"]


def test_running_completion_requires_current_acceptance_and_exact_binding():
    assert timing([START])["elapsed_seconds"] == 7200
    assert timing([START, END, BIND])["status"] == "not_measured"
    accepted = {**PAGE, "acceptance_recorded": True}
    assert timing([START, END], accepted)["status"] == "not_measured"
    assert timing([START, END, BIND], accepted)["elapsed_seconds"] == 3600
    assert timing([START, END, BIND], {**accepted, "receipt_status": "stale"})["status"] == "not_measured"
    assert timing([START, END, {**BIND, "seed_digest": DIGEST}], accepted)["status"] == "not_measured"
    assert timing([START, END, {**BIND, "recorded_at": "2027-01-01T00:00:00Z"}], accepted)["status"] == "not_measured"
    assert timing([START, {**END, "timestamp": "bad"}, BIND], accepted)["status"] == "not_measured"


def test_latest_cycle_and_malformed_records_are_isolated():
    accepted = {**PAGE, "acceptance_recorded": True}
    assert timing([START, END, BIND, {**START, "timestamp": "2026-01-01T11:30:00Z"}], accepted)["status"] == "not_measured"
    assert timing([{**START, "timestamp": "2027-01-01T00:00:00Z"}])["status"] == "not_measured"
    assert timing([{**START, "measurement_scope": []}])["status"] == "not_measured"
    result = process_times(["{bad", json.dumps(START), json.dumps({**START, "module": "b", "timestamp": "bad"})], [PAGE, {**PAGE, "path": "b.md"}], {}, NOW)
    assert result["a.md"]["status"] == "running" and result["b.md"]["status"] == "not_measured"


def test_addition_does_not_mutate_cached_acceptance_and_handles_missing_files(tmp_path):
    report = {"pages": [PAGE], "locales": {"en": {"acceptance_recorded": 0}}}
    result = add_process_times(report, tmp_path, tmp_path / "missing", (None, None))
    assert result["pages"][0]["process_time"] is None
    assert result["locales"] == report["locales"] and "process_time" not in PAGE


def test_api_refresh_attaches_running_time_without_acceptance_promotion(tmp_path):
    from tests.test_content_coverage import setup_pages
    from tests.test_local_api import local_api

    _, _, receipt = setup_pages(tmp_path)
    before = local_api._content_coverage_report(tmp_path)
    counts = before["locales"]
    path = receipt["path"]
    previous = next(page for page in before["pages"] if page["path"] == path)["acceptance_recorded"]
    timing_dir = tmp_path / ".agent"
    timing_dir.mkdir()
    (timing_dir / "module-timing.jsonl").write_text(json.dumps({**START, "module": path.rsplit(".", 1)[0]}))
    after = local_api._content_coverage_report(tmp_path)
    page = next(page for page in after["pages"] if page["path"] == path)
    assert page["process_time"]["status"] == "running"
    assert page["acceptance_recorded"] == previous and after["locales"] == counts
