"""Read-only, fail-closed access to the operator's shared Codex reset reserve.

Ported from the learn-ukrainian fleet topology (operator reset reserve, 2026-09-23).
The assertion is never decremented and never inferred from usage data.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "operator-reset-reserve.v1"
MAX_RESERVE_AGE_SECONDS = 24 * 60 * 60
MAX_PROVIDER_AGE_SECONDS = 15 * 60
RESERVE_RELATIVE_PATH = Path("batch_state/routing_budget/operator_reset_reserve.json")


def main_checkout_root(repo_root: Path) -> Path:
    """Return the primary checkout that owns a linked worktree's git dir.

    Only a ``gitdir:`` target with Git's exact ``.git/worktrees/<name>`` shape
    redirects a path. Primary checkouts and every other root stay themselves.
    """
    git_path = repo_root / ".git"
    if git_path.is_dir():
        return repo_root
    if not git_path.is_file():
        return repo_root
    try:
        first_line = git_path.read_text().splitlines()[0]
    except (IndexError, OSError):
        return repo_root
    prefix = "gitdir:"
    if not first_line.startswith(prefix):
        return repo_root
    git_dir = Path(first_line[len(prefix) :].strip())
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    git_dir = git_dir.resolve()
    if git_dir.parent.name != "worktrees":
        return repo_root
    common_git_dir = git_dir.parent.parent
    if common_git_dir.name != ".git":
        return repo_root
    return common_git_dir.parent


def unavailable_reserve() -> dict[str, Any]:
    """Return the stable sanitized representation of an unavailable assertion."""
    return {
        "available": False,
        "provider": "codex",
        "remaining_resets": None,
        "confirmed_at": None,
        "expires_at": None,
    }


def _utc_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        return None
    return parsed.astimezone(UTC)


def load_reset_reserve(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Load the primary checkout assertion and expose only its safe fields.

    The assertion is never changed or consumed. Invalid, absent, expired, or
    over-age data all produce the same unavailable result.
    """
    path = main_checkout_root(Path(repo_root).resolve()) / RESERVE_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return unavailable_reserve()
    if not isinstance(payload, dict):
        return unavailable_reserve()
    expected = {"schema_version", "provider", "remaining_resets", "confirmed_at", "expires_at"}
    if set(payload) != expected:
        return unavailable_reserve()
    remaining = payload.get("remaining_resets")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("provider") != "codex"
        or isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or remaining <= 0
    ):
        return unavailable_reserve()
    confirmed_at = _utc_datetime(payload.get("confirmed_at"))
    expires_at = _utc_datetime(payload.get("expires_at"))
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if confirmed_at is None or expires_at is None:
        return unavailable_reserve()
    lifetime = (expires_at - confirmed_at).total_seconds()
    if (
        lifetime <= 0
        or lifetime > MAX_RESERVE_AGE_SECONDS
        or confirmed_at > current
        or expires_at <= current
    ):
        return unavailable_reserve()
    return {
        "available": True,
        "provider": "codex",
        "remaining_resets": remaining,
        "confirmed_at": confirmed_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }


def _reserve_window_open(reserve: dict[str, Any], now: datetime | None) -> bool:
    """Re-check assertion timestamps at eligibility time. Missing times fail closed."""
    confirmed_at = _utc_datetime(reserve.get("confirmed_at"))
    expires_at = _utc_datetime(reserve.get("expires_at"))
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if confirmed_at is None or expires_at is None:
        return False
    lifetime = (expires_at - confirmed_at).total_seconds()
    return 0 < lifetime <= MAX_RESERVE_AGE_SECONDS and confirmed_at <= current < expires_at


def _layer_is_fresh(layer: dict[str, Any]) -> bool | None:
    """None when this layer carries no freshness signal."""
    if "freshness" not in layer and "age_s" not in layer and "stale" not in layer:
        return None
    if layer.get("stale") is True or layer.get("freshness") != "fresh":
        return False
    age = layer.get("age_s")
    return (
        not isinstance(age, bool)
        and isinstance(age, (int, float))
        and math.isfinite(age)
        and 0 <= age < MAX_PROVIDER_AGE_SECONDS
    )


def _usage_is_fresh(info: dict[str, Any], codexbar: dict[str, Any]) -> bool:
    """A fresh enclosing snapshot must not hide stale CodexBar usage."""
    top = _layer_is_fresh(info)
    provider = _layer_is_fresh(codexbar)
    if top is False or provider is False:
        return False
    return top is True or provider is True


def codex_reset_reserve_eligible(
    reserve: dict[str, Any],
    codex_info: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    snapshot_stale: bool = False,
) -> bool:
    """Whether a valid reserve may relax an otherwise threatened Codex lane.

    Requires fresh authoritative provider windows, positive headroom, healthy
    and eligible lane state, no explicit auth failure, and clean runtime
    headroom diagnostics. Unknown or missing signals fail closed. A reserve
    never overrides an exhausted or unknown weekly allotment.
    """
    if snapshot_stale or not isinstance(reserve, dict) or reserve.get("available") is not True:
        return False
    if not _reserve_window_open(reserve, now):
        return False
    remaining_resets = reserve.get("remaining_resets")
    if isinstance(remaining_resets, bool) or not isinstance(remaining_resets, int) or remaining_resets <= 0:
        return False
    info = codex_info if isinstance(codex_info, dict) else {}
    health = info.get("health")
    if not isinstance(health, dict) or health.get("healthy") is not True:
        return False
    if info.get("eligible") is not True:
        return False

    cb = info.get("codexbar") if isinstance(info.get("codexbar"), dict) else {}
    if any(
        str(value or "").upper() == "NEED_LOGIN"
        for value in (info.get("login_state"), cb.get("login_state"), info.get("probe_state"), cb.get("probe_state"))
    ):
        return False
    if not _usage_is_fresh(info, cb):
        return False
    probe_state = str(info.get("probe_state", cb.get("probe_state", ""))).upper()
    if probe_state in {"NEED_LOGIN", "NEED_PROBE", "ERROR", "UNAVAILABLE"}:
        return False

    runtime = info.get("runtime")
    if (
        not isinstance(runtime, dict)
        or runtime.get("headroom_blocked") is not False
        or runtime.get("summary_error")
        or isinstance(runtime.get("rate_limited"), bool)
        or not isinstance(runtime.get("rate_limited"), int)
        or runtime.get("rate_limited") != 0
        or runtime.get("last_rate_limited_at") is not None
    ):
        return False

    windows: list[object] = []
    weekly_windows: list[object] = []
    for source in (info.get("windows"), cb.get("windows"), info.get("provider_windows"), cb.get("provider_windows")):
        if isinstance(source, dict):
            windows.extend(source.values())
            weekly_windows.extend(block for name, block in source.items() if name == "weekly")
    for name in ("primary", "secondary", "tertiary", "weekly"):
        block = {"remaining_pct": cb.get(f"{name}_remaining_pct"), "used_pct": cb.get(f"{name}_used_pct")}
        windows.append(block)
        if name == "weekly":
            weekly_windows.append(block)
    notebook = info.get("notebook_report")
    if notebook is not None:
        if not isinstance(notebook, dict) or notebook.get("source") != "notebook-report":
            return False
        notebook_age = notebook.get("age_s")
        if (
            notebook.get("freshness") != "fresh"
            or isinstance(notebook_age, bool)
            or not isinstance(notebook_age, (int, float))
            or not math.isfinite(notebook_age)
            or not 0 <= notebook_age < MAX_PROVIDER_AGE_SECONDS
        ):
            return False
        weekly_block = {
            "remaining_pct": notebook.get("weekly_remaining_pct"),
            "used_pct": notebook.get("weekly_used_pct"),
        }
        windows.append(weekly_block)
        weekly_windows.append(weekly_block)
    has_positive_window = False
    has_positive_weekly = False
    weekly_ids = {id(block) for block in weekly_windows}
    for block in windows:
        if not isinstance(block, dict):
            continue
        remaining = next(
            (
                block.get(key)
                for key in ("remaining_pct", "remaining_percent", "remainingPercent")
                if block.get(key) is not None
            ),
            None,
        )
        used = next(
            (block.get(key) for key in ("used_pct", "used_percent", "usedPercent") if block.get(key) is not None),
            None,
        )
        if isinstance(remaining, (int, float)) and not isinstance(remaining, bool) and math.isfinite(remaining):
            if remaining <= 0:
                return False
            if remaining <= 100:
                has_positive_window = True
                if id(block) in weekly_ids:
                    has_positive_weekly = True
        if isinstance(used, (int, float)) and not isinstance(used, bool) and math.isfinite(used):
            if used >= 100:
                return False
            if 0 <= used < 100:
                has_positive_window = True
                if id(block) in weekly_ids:
                    has_positive_weekly = True
    return has_positive_window and has_positive_weekly


def codex_is_threatened(info: dict[str, Any] | None) -> bool:
    """True when status or pace would normally block or avoid Codex."""
    info = info if isinstance(info, dict) else {}
    status = str(info.get("status") or "")
    cb = info.get("codexbar") if isinstance(info.get("codexbar"), dict) else {}
    return status in {"hot", "near_cap"} or cb.get("will_last_to_reset") is False
