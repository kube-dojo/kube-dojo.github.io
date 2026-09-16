"""DeepSeekAdapter — wraps opencode CLI for first-party DeepSeek (deepseek-direct).

Hermes is retired for DeepSeek dispatch (KubeDojo + learn-ukrainian topology).
Default route: ``opencode run --format json -m deepseek-direct/<model>`` against
``api.deepseek.com``. Catalog default remains ``deepseek-flash`` (V4.1 Flash);
legacy ``deepseek-v4-*`` aliases still map to the first-party provider.

LOCAL-ONLY: prompt data egresses to China — forbidden in CI (see
``scripts.agent_runtime.routes`` and ``dispatch_smart.guard_no_china_provider_in_ci``).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from ..result import ParseResult
from ..routes import (
    deepseek_first_party_error,
    is_deepseek_first_party_forbidden_in_ci,
)
from .base import InvocationPlan

_logger = logging.getLogger(__name__)

# Bare catalog model id → first-party opencode provider route.
_OPENCODE_MODEL_ROUTES: dict[str, str] = {
    "deepseek-flash": "deepseek-direct/deepseek-flash",
    "deepseek-v4-flash": "deepseek-direct/deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek-direct/deepseek-v4-pro",
}

_RATE_LIMIT_RE = re.compile(
    r"rate limit|rate_limit|usage limit|quota exceeded|too many requests|resource_exhausted|\b429\b",
    re.IGNORECASE,
)

# Effort hint → opencode --variant (same mapping as LU Glm/DeepSeek adapters).
_EFFORT_TO_VARIANT: dict[str, str] = {
    "low": "minimal",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}


def _extract_text_from_stdout(stdout: str) -> str:
    """Prefer NDJSON ``--format json`` assistant text; fall back to plain stdout."""
    text = (stdout or "").strip()
    if not text:
        return ""

    # NDJSON event stream (opencode run --format json).
    if "\n" in text or text.startswith('{"type"'):
        parsed = _parse_opencode_json_events(text)
        if parsed:
            return parsed

    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "text" in data and isinstance(data["text"], str):
                    return data["text"].strip()
                if "response" in data and isinstance(data["response"], str):
                    return data["response"].strip()
        except ValueError:
            pass
    return text


def _parse_opencode_json_events(stdout: str) -> str:
    """Extract the final assistant message from opencode ``--format json`` NDJSON.

    Mirrors ``dispatch_smart._parse_opencode_json_events`` so the deepseek
    adapter and the direct opencode router share one schema contract.
    """
    texts_by_message: dict[str, list[str]] = {}
    message_order: list[str] = []
    final_message_id: str | None = None

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        event_type = event.get("type")
        part = event.get("part")
        if not isinstance(part, dict):
            part = {}

        if event_type == "text":
            chunk = part.get("text")
            if not isinstance(chunk, str) or not chunk:
                continue
            message_id = part.get("messageID")
            if not isinstance(message_id, str):
                message_id = ""
            if message_id not in texts_by_message:
                message_order.append(message_id)
            texts_by_message.setdefault(message_id, []).append(chunk)
        elif event_type == "step_finish" and part.get("reason") == "stop":
            message_id = part.get("messageID")
            if isinstance(message_id, str):
                final_message_id = message_id

    if final_message_id and final_message_id in texts_by_message:
        return "".join(texts_by_message[final_message_id]).strip()

    for message_id in reversed(message_order):
        chunks = texts_by_message.get(message_id)
        if chunks:
            return "".join(chunks).strip()
    return ""


class DeepSeekAdapter:
    """Adapter for the opencode CLI with first-party DeepSeek."""

    name: str = "deepseek"
    # Fleet MODEL identity (bare catalog id). The deepseek-direct provider pin
    # is an opencode INVOCATION detail — applied in build_invocation via
    # _OPENCODE_MODEL_ROUTES, not stored as identity.
    default_model: str = os.environ.get("AB_DEEPSEEK_MODEL", "deepseek-flash")
    # Omitted effort defaults to high (--variant high).
    default_effort: str = "high"
    supported_modes: frozenset[str] = frozenset({"read-only", "workspace-write", "danger"})

    def build_invocation(
        self,
        *,
        prompt: str,
        mode: str,
        cwd: Path,
        model: str | None,
        task_id: str | None,
        session_id: str | None,
        tool_config: dict | None,
    ) -> InvocationPlan:
        if mode not in self.supported_modes:
            raise ValueError(
                f"DeepSeekAdapter: unsupported mode {mode!r} "
                f"(supported: {sorted(self.supported_modes)})"
            )

        tc: dict[str, Any] = tool_config or {}
        max_budget_usd = tc.get("max_budget_usd")
        if max_budget_usd is not None:
            _logger.warning(
                "non-claude adapter %s ignoring max_budget_usd=%s; "
                "use hard-timeout/silence-timeout instead",
                self.name,
                max_budget_usd,
            )

        binary = shutil.which("opencode") or "opencode"
        target_model = model or self.default_model
        # Route bare catalog ids to the first-party opencode provider. Explicit
        # provider-prefixed ids (deepseek-direct/…, openrouter/…) pass through.
        invocation_model = _OPENCODE_MODEL_ROUTES.get(target_model, target_model)

        provider_for_guard = "deepseek-direct"
        if invocation_model.startswith("openrouter/"):
            provider_for_guard = "openrouter"
        elif "/" in invocation_model:
            provider_for_guard = invocation_model.split("/", 1)[0]

        if is_deepseek_first_party_forbidden_in_ci(provider_for_guard, invocation_model):
            raise ValueError(
                deepseek_first_party_error(
                    provider=provider_for_guard,
                    model=invocation_model,
                    source="opencode deepseek adapter",
                )
            )

        cmd: list[str] = [binary, "run", "--format", "json", "-m", invocation_model]

        if mode in ("workspace-write", "danger"):
            cmd.append("--auto")

        effort = tc.get("effort") or self.default_effort
        variant = _EFFORT_TO_VARIANT.get(str(effort), str(effort))
        if variant and variant != "default":
            cmd.extend(["--variant", variant])

        # Prompt on stdin (same contract as dispatch_smart opencode router).
        cmd.append("-")

        _logger.debug(
            "deepseek invocation: task=%s mode=%s model=%s effort=%s",
            task_id,
            mode,
            target_model,
            effort,
        )

        _ = session_id

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload=prompt,
            output_file=None,
            env_overrides={"OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX": "131072"},
            liveness_paths=self._liveness_paths(),
        )

    def parse_response(
        self,
        *,
        stdout: str,
        stderr: str,
        returncode: int,
        output_file: Path | None = None,
        plan: InvocationPlan | None = None,
        call_start_time: float | None = None,
    ) -> ParseResult:
        _ = (output_file, plan, call_start_time)
        text = _extract_text_from_stdout(stdout)
        combined = f"{stderr or ''}\n{stdout or ''}"
        pattern_hit = bool(_RATE_LIMIT_RE.search(combined))
        call_failed = returncode != 0 or not bool(text)
        # Only treat rate-limit phrasing as a rate-limit failure when the call
        # actually failed — success stdout may discuss "rate limit" policy.
        rate_limited = pattern_hit and call_failed

        ok = returncode == 0 and bool(text) and not rate_limited

        stderr_excerpt: str | None = None
        if not ok:
            source = (stderr or "").strip() or (stdout or "").strip() or ""
            stderr_excerpt = source[:500] if source else f"opencode exit code {returncode}"

        return ParseResult(
            ok=ok,
            response=text if ok else "",
            stderr_excerpt=stderr_excerpt,
            rate_limited=rate_limited,
            session_id=None,
            tokens=None,
        )

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        _ = plan
        return self._liveness_paths()

    def _liveness_paths(self) -> tuple[Path, ...]:
        opencode_dir = Path.home() / ".config" / "opencode"
        return (opencode_dir,) if opencode_dir.exists() else ()
