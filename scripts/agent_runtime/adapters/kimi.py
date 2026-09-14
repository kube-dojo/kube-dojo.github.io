"""KimiAdapter — wraps Kimi Code via ACP oneshot (not ``kimi -p``).

``kimi -p`` is text-only and cannot edit files. Headless writes go through
``scripts/agent_runtime/kimi_acp_oneshot.py``, which speaks Agent Client
Protocol to ``kimi acp`` and services ``fs/read_text_file`` /
``fs/write_text_file``.

Default model: ``kimi-code/k3-256k`` (faster 256k). Prefer that over
``kimi-code/k3`` (1M) unless the task truly needs the long context window.
EN content OK; do not route Ukrainian translation here.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from ..result import ParseResult
from .base import InvocationPlan

_RATE_LIMIT_RE = re.compile(
    r"rate limit|rate_limit|usage limit|quota exceeded|too many requests|"
    r"\bHTTP 429\b|\bstatus 429\b|\b429\b",
    re.IGNORECASE,
)

_ONESHOT = Path(__file__).resolve().parent.parent / "kimi_acp_oneshot.py"
_DEFAULT_MODEL = os.environ.get("KUBEDOJO_KIMI_MODEL", "kimi-code/k3-256k")


class KimiAdapter:
    """Adapter for Kimi Code via ACP oneshot."""

    name: str = "kimi"
    default_model: str = _DEFAULT_MODEL
    supported_modes: frozenset[str] = frozenset(
        {"read-only", "workspace-write", "danger"}
    )
    # ACP client performs writes; still guard against no-op exits.
    require_file_change_on_write: bool = True

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
            raise ValueError(f"KimiAdapter: unsupported mode {mode!r}")
        _ = session_id
        _ = task_id

        resolved = model or self.default_model
        tc = tool_config or {}
        hard_timeout = tc.get("hard_timeout", 1800)
        try:
            timeout_s = int(hard_timeout)
        except (TypeError, ValueError):
            timeout_s = 1800

        python = sys.executable
        # Prefer repo .venv when the runner is not already using it.
        repo_venv = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "python"
        if repo_venv.is_file():
            python = str(repo_venv)

        # Prompt on stdin (runner stdin_payload) — argv would blow ARG_MAX on briefs.
        cmd = [
            python,
            str(_ONESHOT),
            "--cwd",
            str(cwd),
            "--model",
            resolved,
            "--timeout",
            str(timeout_s),
        ]

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload=prompt,
            output_file=None,
            env_overrides={},
            liveness_paths=(),
        )

    def parse_response(
        self,
        *,
        stdout: str,
        stderr: str,
        returncode: int,
        output_file: Path | None,
        plan: InvocationPlan | None = None,
        call_start_time: float | None = None,
    ) -> ParseResult:
        _ = output_file
        _ = plan
        _ = call_start_time
        text = (stdout or "").strip()
        err = (stderr or "").strip()
        combined = f"{text}\n{err}"
        hard_limit = bool(_RATE_LIMIT_RE.search(combined))
        ok = returncode == 0 and bool(text)
        return ParseResult(
            ok=ok,
            response=text if ok else "",
            session_id=None,
            tokens=None,
            rate_limited=hard_limit,
            stderr_excerpt=(err[:2000] if not ok else ""),
        )

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        _ = plan
        return ()
