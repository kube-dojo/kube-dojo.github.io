"""Rate-limit parser guard coverage for adapter dispatch responses."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from agent_runtime.adapters.claude import ClaudeAdapter
from agent_runtime.adapters.deepseek import DeepSeekAdapter

AdapterFactory = Callable[[], object]


def _parse_success_case(
    adapter_factory: AdapterFactory,
    *,
    stdout: str,
    stderr: str,
    returncode: int = 0,
) -> None:
    adapter = adapter_factory()
    result = adapter.parse_response(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        output_file=None,
    )
    assert result.ok is True
    assert result.rate_limited is False
    assert result.response == stdout.strip() or result.response


@pytest.mark.parametrize(
    ("adapter_factory", "stdout", "stderr"),
    [
        (ClaudeAdapter, "In this answer we discuss rate limit tradeoffs for APIs.", ""),
        (DeepSeekAdapter, "The response explains rate limit policy and mitigation patterns.", ""),
    ],
    ids=["claude", "deepseek"],
)
def test_adapter_parses_rate_limit_phrase_as_success_on_success_exit(
    adapter_factory: AdapterFactory,
    stdout: str,
    stderr: str,
) -> None:
    _parse_success_case(adapter_factory, stdout=stdout, stderr=stderr, returncode=0)


@pytest.mark.parametrize(
    ("adapter_factory", "stdout", "stderr"),
    [
        (ClaudeAdapter, "", "HTTP 429: too many requests"),
        (DeepSeekAdapter, "", "rate limit reached"),
    ],
    ids=["claude", "deepseek"],
)
def test_adapter_marks_rate_limited_when_call_fails(
    adapter_factory: AdapterFactory,
    stdout: str,
    stderr: str,
) -> None:
    adapter = adapter_factory()
    result = adapter.parse_response(
        stdout=stdout,
        stderr=stderr,
        returncode=1,
        output_file=None,
    )
    assert result.ok is False
    assert result.rate_limited is True
    assert result.response == ""
