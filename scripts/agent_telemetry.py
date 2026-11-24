"""Module-build token telemetry CLI (#1973).

Records curriculum module-build runs into ``scripts/telemetry_store.py``
(surfaced on the KubeDojo local API ``/telemetry`` dashboard).

Usage::

    .venv/bin/python scripts/agent_telemetry.py record-build \
        --track k8s/cka --slug module-1.1 --source orchestrator \
        --no-swarm --swarm-note "solo expand" \
        --participant "role=author,agent=codex,model=gpt-6.2-sol,total_tokens=120000"
"""
from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

PRIMARY_REPO = Path(__file__).resolve().parent.parent


def _parse_participant(raw: str) -> dict:
    parts: dict[str, str] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip()] = value.strip()
    if "role" not in parts or "agent" not in parts:
        raise ValueError("each --participant must include role= and agent=")
    participant: dict = {
        "role": parts["role"],
        "agent": parts["agent"],
        "token_source": parts.get("token_source", "unavailable"),
    }
    for key in ("model", "effort", "label", "notes"):
        if key in parts:
            participant[key] = parts[key]
    for key in ("calls", "prompt_tokens", "response_tokens", "total_tokens"):
        if key in parts:
            participant[key] = int(parts[key])
    if "cost_usd_est" in parts:
        participant["cost_usd_est"] = float(parts["cost_usd_est"])
    return participant


def record_build(args: argparse.Namespace) -> int:
    from telemetry_store import upsert_run

    try:
        participants = [_parse_participant(item) for item in args.participant]
    except ValueError as exc:
        print(f"error: {exc}")
        return 2

    payload = {
        "run_id": args.run_id or f"mbt-{uuid4().hex}",
        "track": args.track,
        "slug": args.slug,
        "module_title": args.module_title,
        "branch": args.branch,
        "commit_sha": args.commit,
        "pr_number": args.pr,
        "pr_url": args.pr_url,
        "status": args.status,
        "swarm_used": args.swarm,
        "swarm_label": args.swarm_label,
        "swarm_note": args.swarm_note,
        "wall_clock_minutes": args.wall_clock_min,
        "source": args.source,
        "notes": args.notes,
        "participants": participants,
    }
    try:
        run_id = upsert_run(PRIMARY_REPO, payload)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    print(f"recorded module build: {run_id} [{args.track}/{args.slug}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Module-build telemetry CLI (#1973).")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("record-build", help="record module-build token telemetry (#1973)")
    b.add_argument("--run-id", help="stable run id (default: generated mbt-…)")
    b.add_argument("--track", required=True)
    b.add_argument("--slug", required=True)
    b.add_argument("--module-title")
    b.add_argument("--branch")
    b.add_argument("--commit")
    b.add_argument("--pr", type=int)
    b.add_argument("--pr-url")
    b.add_argument("--status", default="recorded")
    swarm = b.add_mutually_exclusive_group()
    swarm.add_argument("--swarm", dest="swarm", action="store_true")
    swarm.add_argument("--no-swarm", dest="swarm", action="store_false")
    b.set_defaults(swarm=False)
    b.add_argument("--swarm-label", default="none")
    b.add_argument("--swarm-note", required=True)
    b.add_argument("--wall-clock-min", type=float)
    b.add_argument("--source", required=True)
    b.add_argument("--notes")
    b.add_argument(
        "--participant",
        action="append",
        default=[],
        help="role=...,agent=...,model=...,total_tokens=...,cost_usd_est=...,label=...,token_source=...",
    )
    b.set_defaults(func=record_build)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
