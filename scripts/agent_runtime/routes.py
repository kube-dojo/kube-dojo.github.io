"""Shared route identity helpers for agent runtime adapters and runner."""
from __future__ import annotations

import os
from typing import Any

DEEPSEEK_FIRST_PARTY_FORBIDDEN_MARKER = "DEEPSEEK_FIRST_PARTY_FORBIDDEN"

_CI_ENV_VARS = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "JENKINS_URL")


def normalize_route_part(value: Any) -> str:
    return str(value or "").strip()


def is_deepseek_first_party_forbidden_in_ci(provider: Any, model: Any) -> bool:
    """Return True for first-party DeepSeek (China-hosted, local-only) in CI/automation."""
    # Skip guard during pytest (even in CI) so unit tests can exercise the adapter.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    provider_text = normalize_route_part(provider).lower()
    # "deepseek-direct" is the first-party api.deepseek.com provider id used by
    # the OpenCode dispatch route; same China-egress rule as bare "deepseek".
    if provider_text in ("deepseek", "deepseek-direct"):
        return any(os.environ.get(v) for v in _CI_ENV_VARS)
    return False


def deepseek_first_party_error(
    *,
    provider: Any,
    model: Any,
    source: str,
) -> str:
    """Build the explicit hard-fail text for first-party DeepSeek in CI."""
    return (
        f"{DEEPSEEK_FIRST_PARTY_FORBIDDEN_MARKER}: automated run refused "
        f"China-hosted first-party DeepSeek (local-only, never CI) from {source}: "
        f"provider={normalize_route_part(provider)!r} "
        f"model={normalize_route_part(model)!r}"
    )
