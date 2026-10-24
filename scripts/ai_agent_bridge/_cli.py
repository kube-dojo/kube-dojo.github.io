"""CLI entry point: argument parsing, interactive mode, batch processing."""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_runtime import usage as runtime_usage

from ._agy import ask_agy
from ._broker import bridge_status, broker_cleanup
from ._claude import ask_claude, process_for_claude
from ._codex import (
    ask_codex,
    has_codex_headroom,
    process_all_codex,
    process_for_codex,
)
from ._config import GEMINI_DEFAULT_MODEL, GEMINI_REVIEW_MODEL
from ._cursor import ask_cursor
from ._db import get_db
from ._deepseek import ask_deepseek
from ._gemini import ask_gemini, converse_gemini, process_and_respond
from ._hermes import ask_hermes
from ._messaging import (
    acknowledge,
    acknowledge_all,
    check_inbox,
    get_conversation,
    read_message,
    send_message,
)
from ._model import check_model
from ._opencode import ask_opencode
from ._prompts import build_review_message
from ._qwen import ask_qwen

_LOGGER = logging.getLogger(__name__)

try:
    from dispatch import GEMINI_WRITER_MODEL
except ImportError:  # pragma: no cover - package import path variant
    GEMINI_WRITER_MODEL = "gemini-3.1-pro-preview"

AGENT_CHOICES = (
    "agy",
    "claude",
    "codex",
    "cursor",
    "deepseek",
    "gemini",
    "hermes",
    "opencode",
    "qwen",
)


def interactive_mode():
    """Interactive mode for testing."""
    print("🔄 AI Agent Bridge Interactive Mode")
    print("Commands: inbox [agent], read <id>, send <text> --to <agent>, ack <id>, conv <task_id>, process <id>, quit")
    print()

    while True:
        try:
            cmd = input("bridge> ").strip()
            if not cmd:
                continue

            if cmd.lower() in ["quit", "q", "exit"]:
                break

            parts = cmd.split()
            action = parts[0].lower()

            _dispatch_interactive(action, parts)

        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            _LOGGER.exception("Bridge interactive command failed")
            print(f"Error: {e}")


def _dispatch_interactive(action: str, parts: list[str]):
    """Dispatch a single interactive mode command."""
    if action == "inbox":
        agent = parts[1] if len(parts) > 1 else "gemini"
        check_inbox(agent)
    elif action == "read" and len(parts) > 1:
        read_message(int(parts[1]))
    elif action == "send" and len(parts) > 1:
        content = " ".join(parts[1:])
        send_message(content)
    elif action == "ack" and len(parts) > 1:
        ids = [int(x) for x in parts[1:]]
        acknowledge(ids)
    elif action == "conv" and len(parts) > 1:
        get_conversation(parts[1])
    elif action == "process" and len(parts) > 1:
        process_and_respond(int(parts[1]))
    else:
        print("Unknown command or missing arguments.")


def process_all_gemini(model: str = GEMINI_DEFAULT_MODEL):
    """Process ALL unread messages for Gemini in batch."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, task_id, from_llm, message_type, substr(content, 1, 50)
        FROM messages
        WHERE to_llm = 'gemini' AND acknowledged = 0
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("📭 No unread messages for Gemini to process")
        return

    print(f"📬 Processing {len(rows)} unread message(s) for Gemini...\n")

    success = 0
    failed = 0

    for row in rows:
        msg_id, _task_id, from_llm, _msg_type, preview = row
        preview = preview.replace('\n', ' ')[:40]
        print(f"━━━ Processing [{msg_id}] from {from_llm}: {preview}...")

        try:
            process_and_respond(msg_id, model)
            success += 1
            print("    ✅ Done\n")
        except Exception as e:
            _LOGGER.exception("Bridge Gemini batch message failed")
            failed += 1
            print(f"    ❌ Failed: {e}\n")

    print(f"\n{'═' * 50}")
    print(f"📊 Results: {success} succeeded, {failed} failed out of {len(rows)} total")


def process_all_claude(new_session: bool = False):
    """Process ALL unread messages for Claude in batch (headless)."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, task_id, from_llm, message_type, substr(content, 1, 50)
        FROM messages
        WHERE to_llm = 'claude' AND acknowledged = 0
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("📭 No unread messages for Claude to process")
        return

    print(f"📬 Processing {len(rows)} unread message(s) for Claude (headless)...\n")

    success = 0
    failed = 0

    for row in rows:
        msg_id, _task_id, from_llm, _msg_type, preview = row
        preview = preview.replace('\n', ' ')[:40]
        print(f"━━━ Processing [{msg_id}] from {from_llm}: {preview}...")

        try:
            process_for_claude(msg_id, new_session)
            success += 1
            print("    ✅ Done\n")
        except Exception as e:
            _LOGGER.exception("Bridge Claude batch message failed")
            failed += 1
            print(f"    ❌ Failed: {e}\n")

    print(f"\n{'═' * 50}")
    print(f"📊 Results: {success} succeeded, {failed} failed out of {len(rows)} total")


def _parse_usage_window(window: str) -> int:
    """Return the reporting window in seconds."""
    windows = {
        "5h": 5 * 60 * 60,
        "24h": 24 * 60 * 60,
        "7d": 7 * 24 * 60 * 60,
        "30d": 30 * 24 * 60 * 60,
    }
    return windows[window]


def _iter_codex_usage_records(window: str, entrypoint: str):
    """Yield Codex usage records within the reporting window."""
    cutoff_ts = datetime.now(UTC).timestamp() - _parse_usage_window(window)

    for path in runtime_usage._usage_dir().glob("usage_codex-*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff_ts:
                continue
        except OSError:
            continue

        try:
            with open(path, encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        record = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if entrypoint != "all" and record.get("entrypoint") != entrypoint:
                        continue
                    ts_str = record.get("ts")
                    if not ts_str:
                        continue
                    try:
                        record_ts = datetime.fromisoformat(
                            str(ts_str).replace("Z", "+00:00")
                        ).timestamp()
                    except (TypeError, ValueError):
                        continue
                    if record_ts < cutoff_ts:
                        continue
                    yield record
        except OSError:
            continue


def _build_codex_usage_report(window: str, entrypoint: str) -> dict:
    """Aggregate usage records into a printable report."""
    records = list(_iter_codex_usage_records(window, entrypoint))
    outcomes = ("ok", "error", "rate_limited", "timeout")
    by_outcome: dict[str, dict[str, object]] = {}
    by_entrypoint: dict[str, int] = {}
    recent_rate_limits: list[str] = []
    total_duration_s = 0.0

    for record in records:
        outcome = str(record.get("outcome") or "error")
        entry = str(record.get("entrypoint") or "unknown")
        duration = float(record.get("duration_s") or 0.0)
        total_duration_s += duration

        outcome_bucket = by_outcome.setdefault(
            outcome,
            {"count": 0, "total_duration_s": 0.0, "recent_events": []},
        )
        outcome_bucket["count"] = int(outcome_bucket["count"]) + 1
        outcome_bucket["total_duration_s"] = float(outcome_bucket["total_duration_s"]) + duration

        by_entrypoint[entry] = by_entrypoint.get(entry, 0) + 1

        if outcome == "rate_limited" and record.get("ts"):
            ts = str(record["ts"])
            recent_rate_limits.append(ts)
            cast_events = outcome_bucket["recent_events"]
            assert isinstance(cast_events, list)
            cast_events.append(ts)

    for outcome in outcomes:
        bucket = by_outcome.setdefault(
            outcome,
            {"count": 0, "total_duration_s": 0.0, "recent_events": []},
        )
        count = int(bucket["count"])
        bucket["avg_duration_s"] = round(
            float(bucket["total_duration_s"]) / count, 1
        ) if count else 0.0
        bucket["total_duration_s"] = round(float(bucket["total_duration_s"]), 1)

    has_room, headroom_reason = has_codex_headroom("gpt-5.4")
    return {
        "window": window,
        "entrypoint": entrypoint,
        "total_calls": len(records),
        "total_duration_s": round(total_duration_s, 1),
        "by_outcome": by_outcome,
        "by_entrypoint": dict(sorted(by_entrypoint.items())),
        "recent_rate_limits": sorted(recent_rate_limits),
        "headroom": {
            "model": "gpt-5.4",
            "has_headroom": has_room,
            "reason": headroom_reason,
        },
    }


def _print_codex_usage_report(report: dict) -> None:
    """Render a human-readable Codex usage report."""
    print(
        f"Codex usage report - window: {report['window']}, "
        f"entrypoint: {report['entrypoint']}"
    )
    print("-" * 48)
    print(f"Total calls: {report['total_calls']}")
    print(f"Total duration: {report['total_duration_s']:.1f}s")
    print("By outcome:")

    for outcome in ("ok", "error", "rate_limited", "timeout"):
        bucket = report["by_outcome"][outcome]
        count = int(bucket["count"])
        pct = ((count / report["total_calls"]) * 100.0) if report["total_calls"] else 0.0
        line = f"  {outcome:<12} {count:>3}   ({pct:>4.1f}%)"
        total_duration = float(bucket["total_duration_s"])
        avg_duration = float(bucket["avg_duration_s"])
        recent_events = bucket["recent_events"]
        if outcome == "rate_limited" and recent_events:
            joined = ", ".join(str(ts) for ts in recent_events)
            line += f"   at {joined}"
        elif count:
            line += f"   total {total_duration:>6.1f}s"
            if avg_duration:
                line += f"   avg {avg_duration:.1f}s"
        print(line)

    print("\nBy entrypoint:")
    if report["by_entrypoint"]:
        for name, count in report["by_entrypoint"].items():
            print(f"  {name:<10} {count}")
    else:
        print("  (none)")

    headroom = report["headroom"]
    symbol = "✓" if headroom["has_headroom"] else "✗"
    line = (
        f"\nHeadroom check: {headroom['model']} - "
        f"has headroom {symbol}"
    )
    if not headroom["has_headroom"] and headroom["reason"]:
        line += f" ({headroom['reason']})"
    print(line)


def _handle_codex_usage(args) -> None:
    """Handle codex-usage subcommand."""
    report = _build_codex_usage_report(args.window, args.entrypoint)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    _print_codex_usage_report(report)


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="AI Agent Bridge - Claude/Gemini/Codex Communication")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # inbox
    inbox_parser = subparsers.add_parser("inbox", help="Check inbox for messages")
    inbox_parser.add_argument("--for", dest="for_llm", default="gemini", choices=AGENT_CHOICES,
                             help="Check inbox for which agent (default: gemini)")

    # read
    read_parser = subparsers.add_parser("read", help="Read a specific message")
    read_parser.add_argument("message_id", type=int, help="Message ID to read")

    # send
    send_parser = subparsers.add_parser("send", help="Send message to another agent")
    send_parser.add_argument("content", help="Message content")
    send_parser.add_argument("--to", dest="to_llm", default="claude", choices=AGENT_CHOICES,
                            help="Target agent (default: claude)")
    send_parser.add_argument("--from", dest="from_llm", default="gemini",
                            help="Sender agent name (default: gemini)")
    send_parser.add_argument("--task-id", help="Task ID for grouping")
    send_parser.add_argument("--type", default="response", help="Message type")
    send_parser.add_argument("--data", help="Path to data file to attach")
    send_parser.add_argument("--from-model", dest="from_model", help="Specific model ID of sender")
    send_parser.add_argument("--to-model", dest="to_model", help="Specific model ID of receiver")

    # ack
    ack_parser = subparsers.add_parser("ack", help="Acknowledge message(s)")
    ack_parser.add_argument("message_ids", type=int, nargs='+', help="Message ID(s) to acknowledge")

    # ack-all
    ack_all_parser = subparsers.add_parser("ack-all", help="Acknowledge ALL unread messages for an agent")
    ack_all_parser.add_argument("agent", choices=AGENT_CHOICES, help="Agent whose inbox to clear")

    # conversation
    conv_parser = subparsers.add_parser("conversation", help="Get conversation history")
    conv_parser.add_argument("task_id", help="Task ID")

    # process (for Gemini)
    proc_parser = subparsers.add_parser("process", help="Process message with Gemini and respond")
    proc_parser.add_argument("message_id", type=int, help="Message ID to process")
    proc_parser.add_argument(
        "--model", default=GEMINI_DEFAULT_MODEL, help="Gemini model"
    )
    proc_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                             help="Run sync without timeout (used internally by fire-and-forget)")

    # process-claude
    proc_claude_parser = subparsers.add_parser("process-claude", help="Process message with Claude CLI (headless)")
    proc_claude_parser.add_argument("message_id", type=int, help="Message ID for Claude to process")
    proc_claude_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                    help="Force new session even if one exists for this task")
    proc_claude_parser.add_argument("--async", dest="fire_and_forget", action="store_true",
                                    help="Launch Claude in background (no timeout).")
    proc_claude_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                    help="Run sync without timeout (used internally by fire-and-forget)")

    # process-codex
    proc_codex_parser = subparsers.add_parser("process-codex", help="Process message with Codex CLI (headless)")
    proc_codex_parser.add_argument("message_id", type=int, help="Message ID for Codex to process")
    proc_codex_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                   help="Force new session even if one exists")
    proc_codex_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                   help="Run sync without timeout")
    proc_codex_parser.add_argument("--force", action="store_true",
                                   help="Reprocess an already acknowledged message")

    # ask-claude
    ask_claude_parser = subparsers.add_parser("ask-claude", help="Send message AND invoke Claude (one-step)")
    ask_claude_parser.add_argument("content", help="Message content")
    ask_claude_parser.add_argument("--task-id", required=True, help="Task ID (required for session tracking)")
    ask_claude_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_claude_parser.add_argument("--data", help="Path to data file to attach")
    ask_claude_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                   help="Force new session even if one exists")
    ask_claude_parser.add_argument("--from", dest="from_llm", default="gemini",
                                   help="Sender agent family (gemini, claude). Default: gemini")
    ask_claude_parser.add_argument("--from-model", dest="from_model",
                                   help="Exact sender model ID")
    ask_claude_parser.add_argument("--to-model", dest="to_model",
                                   help="Target model ID")
    ask_claude_parser.add_argument("--review", action="store_true",
                                   help="Prepend canonical review protocol to the message")

    # ask-codex
    ask_codex_parser = subparsers.add_parser("ask-codex", help="Send message AND invoke Codex (one-step; use '-' to read from stdin)")
    ask_codex_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_codex_parser.add_argument("--task-id", required=True, help="Task ID (required for session tracking)")
    ask_codex_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_codex_parser.add_argument("--data", help="Path to data file to attach")
    ask_codex_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                  help="Force new session even if one exists")
    ask_codex_parser.add_argument("--from", dest="from_llm", default="gemini",
                                  help="Sender agent family (gemini, claude, codex). Default: gemini")
    ask_codex_parser.add_argument("--from-model", dest="from_model",
                                  help="Exact sender model ID")
    ask_codex_parser.add_argument("--to-model", dest="to_model",
                                  help="Target model ID")
    ask_codex_parser.add_argument("--review", action="store_true",
                                  help="Prepend canonical review protocol to the message")

    # ask-gemini
    ask_gemini_parser = subparsers.add_parser("ask-gemini", help="Send message AND invoke Gemini (one-step)")
    ask_gemini_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_gemini_parser.add_argument("--task-id", required=True, help="Task ID (required for session tracking)")
    ask_gemini_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_gemini_parser.add_argument("--data", help="Path to data file to attach")
    ask_gemini_parser.add_argument(
        "--model", default=None,
        help=(
            "Gemini model to use "
            f"(default: {GEMINI_REVIEW_MODEL} for --review, "
            f"else {GEMINI_DEFAULT_MODEL})"
        )
    )
    ask_gemini_parser.add_argument("--from-model", dest="from_model",
                                   help="Exact sender model ID")
    ask_gemini_parser.add_argument("--async", dest="async_mode", action="store_true",
                                   help="Queue only, don't invoke Gemini CLI")
    ask_gemini_parser.add_argument("--stdout-only", dest="stdout_only", action="store_true",
                                   help="Don't route full response through broker.")
    ask_gemini_parser.add_argument("--output-path", dest="output_path",
                                   help="Gemini writes output to this file.")
    ask_gemini_parser.add_argument("--extract", nargs="*", metavar="TAG",
                                   help="Extract delimited content from output.")
    ask_gemini_parser.add_argument("--skip-model-check", dest="skip_model_check", action="store_true",
                                   help="Skip the model availability pre-flight check.")
    ask_gemini_parser.add_argument("--allow-write", dest="allow_write", action="store_true",
                                   help="Grant Gemini full bash + write access.")
    ask_gemini_parser.add_argument("--delimiters", dest="delimiters",
                                   help="Comma-separated delimiter names for --allow-write mode.")
    ask_gemini_parser.add_argument("--no-github", dest="no_github", action="store_true",
                                   help="Skip auto-posting review to GitHub issue")
    ask_gemini_parser.add_argument("--review", action="store_true",
                                   help="Prepend canonical review protocol to the message")

    # ask-agy
    ask_agy_parser = subparsers.add_parser("ask-agy", help="Send message AND invoke Agy (one-step)")
    ask_agy_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_agy_parser.add_argument("--task-id", help="Task ID for session tracking")
    ask_agy_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_agy_parser.add_argument("--data", help="Path to data file to attach")
    ask_agy_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                help="Force new session even if one exists")
    ask_agy_parser.add_argument("--from", dest="from_llm", default="gemini",
                                help="Sender agent family. Default: gemini")
    ask_agy_parser.add_argument("--from-model", dest="from_model",
                                help="Exact sender model ID")
    ask_agy_parser.add_argument("--to-model", dest="to_model",
                                help="Target model ID")
    ask_agy_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                help="Run sync without timeout")
    ask_agy_parser.add_argument("--review", action="store_true",
                                help="Prepend docs/review-protocol.md")

    # ask-qwen
    ask_qwen_parser = subparsers.add_parser("ask-qwen", help="Send message AND invoke Qwen (one-step)")
    ask_qwen_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_qwen_parser.add_argument("--task-id", help="Task ID for session tracking")
    ask_qwen_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_qwen_parser.add_argument("--data", help="Path to data file to attach")
    ask_qwen_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                 help="Force new session even if one exists")
    ask_qwen_parser.add_argument("--from", dest="from_llm", default="gemini",
                                 help="Sender agent family. Default: gemini")
    ask_qwen_parser.add_argument("--from-model", dest="from_model",
                                 help="Exact sender model ID")
    ask_qwen_parser.add_argument("--to-model", dest="to_model",
                                 help="Target model ID")
    ask_qwen_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                 help="Run sync without timeout")
    ask_qwen_parser.add_argument("--review", action="store_true",
                                 help="Prepend docs/review-protocol.md")

    # ask-deepseek
    ask_deepseek_parser = subparsers.add_parser("ask-deepseek", help="Send message AND invoke DeepSeek (one-step)")
    ask_deepseek_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_deepseek_parser.add_argument("--task-id", help="Task ID for session tracking")
    ask_deepseek_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_deepseek_parser.add_argument("--data", help="Path to data file to attach")
    ask_deepseek_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                     help="Force new session even if one exists")
    ask_deepseek_parser.add_argument("--from", dest="from_llm", default="gemini",
                                     help="Sender agent family. Default: gemini")
    ask_deepseek_parser.add_argument("--from-model", dest="from_model",
                                     help="Exact sender model ID")
    ask_deepseek_parser.add_argument("--to-model", dest="to_model",
                                     help="Target model ID")
    ask_deepseek_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                     help="Run sync without timeout")
    ask_deepseek_parser.add_argument("--review", action="store_true",
                                     help="Prepend docs/review-protocol.md")

    # ask-hermes
    ask_hermes_parser = subparsers.add_parser("ask-hermes", help="Send message AND invoke Hermes (one-step)")
    ask_hermes_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_hermes_parser.add_argument("--task-id", help="Task ID for session tracking")
    ask_hermes_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_hermes_parser.add_argument("--data", help="Path to data file to attach")
    ask_hermes_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                   help="Force new session even if one exists")
    ask_hermes_parser.add_argument("--from", dest="from_llm", default="gemini",
                                   help="Sender agent family. Default: gemini")
    ask_hermes_parser.add_argument("--from-model", dest="from_model",
                                   help="Exact sender model ID")
    ask_hermes_parser.add_argument("--to-model", dest="to_model",
                                   help="Target model ID")
    ask_hermes_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                   help="Run sync without timeout")
    ask_hermes_parser.add_argument("--review", action="store_true",
                                   help="Prepend docs/review-protocol.md")

    # ask-opencode
    ask_opencode_parser = subparsers.add_parser("ask-opencode", help="Send message AND invoke OpenCode (one-step)")
    ask_opencode_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_opencode_parser.add_argument("--task-id", help="Task ID for session tracking")
    ask_opencode_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_opencode_parser.add_argument("--data", help="Path to data file to attach")
    ask_opencode_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                     help="Force new session even if one exists")
    ask_opencode_parser.add_argument("--from", dest="from_llm", default="gemini",
                                     help="Sender agent family. Default: gemini")
    ask_opencode_parser.add_argument("--from-model", dest="from_model",
                                     help="Exact sender model ID")
    ask_opencode_parser.add_argument("--to-model", dest="to_model",
                                     help="Target model ID")
    ask_opencode_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                     help="Run sync without timeout")
    ask_opencode_parser.add_argument("--review", action="store_true",
                                     help="Prepend docs/review-protocol.md")

    # ask-cursor
    ask_cursor_parser = subparsers.add_parser("ask-cursor", help="Send message AND invoke Cursor (one-step)")
    ask_cursor_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    ask_cursor_parser.add_argument("--task-id", help="Task ID for session tracking")
    ask_cursor_parser.add_argument("--type", default="query", help="Message type (default: query)")
    ask_cursor_parser.add_argument("--data", help="Path to data file to attach")
    ask_cursor_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                  help="Force new session even if one exists")
    ask_cursor_parser.add_argument("--from", dest="from_llm", default="gemini",
                                  help="Sender agent family. Default: gemini")
    ask_cursor_parser.add_argument("--from-model", dest="from_model",
                                  help="Exact sender model ID")
    ask_cursor_parser.add_argument("--to-model", dest="to_model",
                                  help="Target model ID")
    ask_cursor_parser.add_argument("--no-timeout", dest="no_timeout", action="store_true",
                                  help="Run sync without timeout")
    ask_cursor_parser.add_argument("--review", action="store_true",
                                  help="Prepend docs/review-protocol.md")

    # converse — multi-turn conversation with Gemini
    converse_parser = subparsers.add_parser("converse", help="Multi-turn conversation with Gemini (includes history)")
    converse_parser.add_argument("content", help="Message content (use '-' to read from stdin)")
    converse_parser.add_argument("--task-id", required=True, help="Conversation thread ID (e.g., 'a1-1-planning')")
    converse_parser.add_argument("--model", default=GEMINI_WRITER_MODEL, help="Gemini model")
    converse_parser.add_argument("--no-github", dest="no_github", action="store_true",
                                 help="Skip auto-posting to GitHub")

    # process-all
    proc_all_parser = subparsers.add_parser("process-all", help="Process ALL unread messages with Gemini")
    proc_all_parser.add_argument(
        "--model", default=GEMINI_DEFAULT_MODEL, help="Gemini model"
    )

    # process-claude-all
    proc_claude_all_parser = subparsers.add_parser("process-claude-all", help="Process ALL unread messages with Claude")
    proc_claude_all_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                        help="Force new sessions for each message")

    # process-codex-all
    proc_codex_all_parser = subparsers.add_parser("process-codex-all", help="Process ALL unread messages with Codex")
    proc_codex_all_parser.add_argument("--new-session", dest="new_session", action="store_true",
                                       help="Force new sessions for each message")

    # codex-usage
    codex_usage_parser = subparsers.add_parser(
        "codex-usage",
        help="Summarize recent Codex runtime usage from batch_state/api_usage/",
    )
    codex_usage_parser.add_argument(
        "--window",
        default="5h",
        choices=["5h", "24h", "7d", "30d"],
        help="Reporting window (default: 5h)",
    )
    codex_usage_parser.add_argument(
        "--entrypoint",
        default="all",
        choices=["bridge", "dispatch", "delegate", "all"],
        help="Filter by Codex entrypoint (default: all)",
    )
    codex_usage_parser.add_argument(
        "--json",
        dest="json",
        action="store_true",
        help="Emit machine-readable JSON instead of text",
    )

    # check-model
    check_model_parser = subparsers.add_parser("check-model", help="Check if a Gemini model is available")
    check_model_parser.add_argument("model", help="Model name")

    # cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean stuck broker state")
    cleanup_parser.add_argument("--max-age", type=int, default=24, help="Force-ack messages older than N hours")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Report what would be cleaned")

    # status
    subparsers.add_parser("status", help="Show running bridge processes")

    # interactive
    subparsers.add_parser("interactive", help="Interactive mode")

    # send-codex-ui — drives a running Codex Desktop UI session via
    # `codex exec resume <UUID> --json -`. Port from learn-ukrainian #2285.
    send_codex_ui_parser = subparsers.add_parser(
        "send-codex-ui",
        help="Send a prompt to a running Codex Desktop UI session via `codex exec resume`",
    )
    send_codex_ui_parser.add_argument(
        "--thread", required=True,
        help="Codex thread UUID (find via `codex sessions list --last` or ~/.codex/sessions/)",
    )
    send_codex_ui_parser.add_argument(
        "--bridge-id", default=None,
        help="Correlation id (auto-generated if not given)",
    )
    send_codex_ui_parser.add_argument(
        "--cwd", default=None,
        help="Working directory for the codex subprocess (default: caller's cwd)",
    )
    send_codex_ui_parser.add_argument(
        "--timeout", type=int, default=1800,
        help="Max wall-clock seconds (default 1800 = 30min)",
    )
    send_codex_ui_parser.add_argument(
        "--from-file", default=None,
        help="Read message body from a file (use '-' for stdin)",
    )
    send_codex_ui_parser.add_argument(
        "--json", action="store_true",
        help="Print result as compact JSON (excludes verbose events list)",
    )
    send_codex_ui_parser.add_argument(
        "message", nargs="?",
        help="Inline message text. Mutually exclusive with --from-file.",
    )

    # send-cursor-ui — Cursor Desktop bridge via `cursor-agent --resume`.
    # New for kubedojo; learn-ukrainian deferred the cursor adapter in #2285.
    send_cursor_ui_parser = subparsers.add_parser(
        "send-cursor-ui",
        help="Send a prompt to a running Cursor Desktop chat via `cursor-agent --resume`",
    )
    send_cursor_ui_parser.add_argument(
        "--thread", default=None,
        help="Cursor chat id. Omit or pass 'new' to create a fresh chat via `cursor-agent create-chat`",
    )
    send_cursor_ui_parser.add_argument(
        "--bridge-id", default=None,
        help="Correlation id (auto-generated if not given)",
    )
    send_cursor_ui_parser.add_argument(
        "--cwd", default=None,
        help="Working directory for the cursor-agent subprocess (default: caller's cwd)",
    )
    send_cursor_ui_parser.add_argument(
        "--timeout", type=int, default=1800,
        help="Max wall-clock seconds (default 1800 = 30min)",
    )
    send_cursor_ui_parser.add_argument(
        "--model", default=None,
        help="Model override (default composer-2.5 or $AB_CURSOR_UI_MODEL)",
    )
    send_cursor_ui_parser.add_argument(
        "--from-file", default=None,
        help="Read message body from a file (use '-' for stdin)",
    )
    send_cursor_ui_parser.add_argument(
        "--json", action="store_true",
        help="Print result as compact JSON (excludes verbose events list)",
    )
    send_cursor_ui_parser.add_argument(
        "message", nargs="?",
        help="Inline message text. Mutually exclusive with --from-file.",
    )

    # send-agy-ui — Antigravity UI bridge via `agy --conversation ... --print`.
    send_agy_ui_parser = subparsers.add_parser(
        "send-agy-ui",
        help="Send a prompt to an Antigravity UI conversation via `agy --print`",
    )
    send_agy_ui_parser.add_argument(
        "--thread", default=None,
        help="Antigravity conversation id (omit or pass 'new' for a fresh conversation)",
    )
    send_agy_ui_parser.add_argument(
        "--bridge-id", default=None,
        help="Correlation id (auto-generated if not given)",
    )
    send_agy_ui_parser.add_argument(
        "--cwd", default=None,
        help="Working directory for the agy subprocess (default: caller's cwd)",
    )
    send_agy_ui_parser.add_argument(
        "--timeout", type=int, default=1800,
        help="Max wall-clock seconds (default 1800 = 30min)",
    )
    send_agy_ui_parser.add_argument(
        "--from-file", default=None,
        help="Read message body from a file (use '-' for stdin)",
    )
    send_agy_ui_parser.add_argument(
        "--json", action="store_true",
        help="Print result as compact JSON (excludes verbose events list)",
    )
    send_agy_ui_parser.add_argument(
        "message", nargs="?",
        help="Inline message text. Mutually exclusive with --from-file.",
    )

    # Channel bridge commands (#1190) — registered in _channels_cli
    from ._channels_cli import register_channel_commands
    register_channel_commands(subparsers)

    return parser


def _dispatch_command(args):
    """Dispatch parsed CLI arguments to the appropriate handler."""
    if args.command == "inbox":
        if getattr(args, "inbox_command", None):
            from ._channels_cli import dispatch_channel_command
            rc = dispatch_channel_command(args)
            sys.exit(rc)
        check_inbox(args.for_llm)
    elif args.command == "read":
        read_message(args.message_id)
    elif args.command == "send":
        data = None
        if args.data:
            data = Path(args.data).read_text()
        send_message(args.content, args.task_id, args.type, data,
                     args.from_llm, args.to_llm, args.from_model, args.to_model)
    elif args.command == "ack":
        acknowledge(args.message_ids)
    elif args.command == "ack-all":
        acknowledge_all(args.agent)
    elif args.command == "conversation":
        get_conversation(args.task_id)
    elif args.command == "process":
        process_and_respond(args.message_id, args.model, no_timeout=args.no_timeout)
    elif args.command == "process-claude":
        process_for_claude(args.message_id, args.new_session, args.fire_and_forget, args.no_timeout)
    elif args.command == "process-codex":
        process_for_codex(args.message_id, args.new_session, args.no_timeout, force=args.force)
    elif args.command == "ask-claude":
        _handle_ask_claude(args)
    elif args.command == "ask-codex":
        _handle_ask_codex(args)
    elif args.command == "ask-gemini":
        _handle_ask_gemini(args)
    elif args.command == "ask-agy":
        _handle_ask_agy(args)
    elif args.command == "ask-qwen":
        _handle_ask_qwen(args)
    elif args.command == "ask-deepseek":
        _handle_ask_deepseek(args)
    elif args.command == "ask-hermes":
        _handle_ask_hermes(args)
    elif args.command == "ask-opencode":
        _handle_ask_opencode(args)
    elif args.command == "ask-cursor":
        _handle_ask_cursor(args)
    elif args.command == "converse":
        content = sys.stdin.read() if args.content == "-" else args.content
        converse_gemini(content, args.task_id, args.model,
                        getattr(args, 'no_github', False))
    elif args.command == "process-all":
        process_all_gemini(args.model)
    elif args.command == "process-claude-all":
        process_all_claude(args.new_session)
    elif args.command == "process-codex-all":
        process_all_codex(args.new_session)
    elif args.command == "codex-usage":
        _handle_codex_usage(args)
    elif args.command == "check-model":
        ok = check_model(args.model, force=True)
        sys.exit(0 if ok else 1)
    elif args.command == "cleanup":
        broker_cleanup(args.max_age, args.dry_run)
    elif args.command == "status":
        bridge_status()
    elif args.command == "interactive":
        interactive_mode()
    elif args.command == "send-codex-ui":
        from ._ui_codex import cli_main as _ui_codex_cli_main
        argv: list[str] = ["--thread", args.thread]
        if args.bridge_id:
            argv += ["--bridge-id", args.bridge_id]
        if args.cwd:
            argv += ["--cwd", args.cwd]
        if args.timeout != 1800:
            argv += ["--timeout", str(args.timeout)]
        if getattr(args, "json", False):
            argv += ["--json"]
        if args.from_file:
            argv += ["--from-file", args.from_file]
        if args.message:
            argv += [args.message]
        sys.exit(_ui_codex_cli_main(argv))
    elif args.command == "send-cursor-ui":
        from ._ui_cursor import cli_main as _ui_cursor_cli_main
        argv = []
        if args.thread:
            argv += ["--thread", args.thread]
        if args.bridge_id:
            argv += ["--bridge-id", args.bridge_id]
        if args.cwd:
            argv += ["--cwd", args.cwd]
        if args.timeout != 1800:
            argv += ["--timeout", str(args.timeout)]
        if args.model:
            argv += ["--model", args.model]
        if getattr(args, "json", False):
            argv += ["--json"]
        if args.from_file:
            argv += ["--from-file", args.from_file]
        if args.message is not None:
            argv += [args.message]
        sys.exit(_ui_cursor_cli_main(argv))
    elif args.command == "send-agy-ui":
        from ._ui_agy import cli_main as _ui_agy_cli_main
        argv = []
        if args.thread:
            argv += ["--thread", args.thread]
        if args.bridge_id:
            argv += ["--bridge-id", args.bridge_id]
        if args.cwd:
            argv += ["--cwd", args.cwd]
        if args.timeout != 1800:
            argv += ["--timeout", str(args.timeout)]
        if getattr(args, "json", False):
            argv += ["--json"]
        if args.from_file:
            argv += ["--from-file", args.from_file]
        if args.message is not None:
            argv += [args.message]
        sys.exit(_ui_agy_cli_main(argv))
    elif args.command in ("channel", "post", "p", "sync", "discuss"):
        # Channel bridge commands (#1190)
        from ._channels_cli import dispatch_channel_command
        rc = dispatch_channel_command(args)
        sys.exit(rc)
    else:
        return False
    return True


def _handle_ask_claude(args):
    """Handle ask-claude subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = build_review_message(args.content) if args.review else args.content
    ask_claude(content, args.task_id, args.type, data,
               args.new_session, args.from_llm, args.from_model, args.to_model)


def _handle_ask_codex(args):
    """Handle ask-codex subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    content = build_review_message(content) if args.review else content
    ask_codex(content, args.task_id, "review" if args.review else args.type, data,
              args.new_session or args.review, args.from_llm, args.from_model, args.to_model)


def _handle_ask_gemini(args):
    """Handle ask-gemini subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    content = build_review_message(content) if args.review else content
    model = args.model or (GEMINI_REVIEW_MODEL if args.review else GEMINI_DEFAULT_MODEL)
    result = ask_gemini(content, args.task_id, args.type, data, model,
                        getattr(args, 'from_model', None),
                        getattr(args, 'async_mode', False),
                        getattr(args, 'stdout_only', False),
                        getattr(args, 'output_path', None),
                        getattr(args, 'extract', None),
                        getattr(args, 'skip_model_check', False),
                        getattr(args, 'allow_write', False),
                        getattr(args, 'delimiters', None),
                        getattr(args, 'no_github', False),
                        not args.review)
    if result is None:
        sys.exit(1)


def _handle_ask_agy(args):
    """Handle ask-agy subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    ask_agy(content, args.task_id, args.type, data,
            args.new_session, args.from_llm, args.from_model,
            args.to_model, args.no_timeout, args.review)


def _handle_ask_qwen(args):
    """Handle ask-qwen subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    ask_qwen(content, args.task_id, args.type, data,
             args.new_session, args.from_llm, args.from_model,
             args.to_model, args.no_timeout, args.review)


def _handle_ask_deepseek(args):
    """Handle ask-deepseek subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    ask_deepseek(content, args.task_id, args.type, data,
                 args.new_session, args.from_llm, args.from_model,
                 args.to_model, args.no_timeout, args.review)


def _handle_ask_hermes(args):
    """Handle ask-hermes subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    ask_hermes(content, args.task_id, args.type, data,
               args.new_session, args.from_llm, args.from_model,
               args.to_model, args.no_timeout, args.review)


def _handle_ask_opencode(args):
    """Handle ask-opencode subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    ask_opencode(content, args.task_id, args.type, data,
                 args.new_session, args.from_llm, args.from_model,
                 args.to_model, args.no_timeout, args.review)


def _handle_ask_cursor(args):
    """Handle ask-cursor subcommand."""
    data = None
    if args.data:
        data = Path(args.data).read_text()
    content = sys.stdin.read() if args.content == "-" else args.content
    ask_cursor(content, args.task_id, args.type, data,
               args.new_session, args.from_llm, args.from_model,
               args.to_model, args.no_timeout, args.review)


def main():
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    if args.command is not None:
        from ._channels_cli import _maybe_print_backlog_warnings
        _maybe_print_backlog_warnings()
    if not _dispatch_command(args):
        parser.print_help()
