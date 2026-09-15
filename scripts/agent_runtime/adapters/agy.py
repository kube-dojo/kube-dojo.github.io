"""AgyAdapter - wraps Antigravity CLI (``agy``) for the agent runtime.

Phase 1 of the Antigravity migration keeps this adapter alongside the
existing Gemini CLI adapter. Antigravity 1.x added a per-session ``--model``
flag (``agy models`` lists the choices), so the runtime's model value is now
mapped to the matching CLI display string and passed through — it is no
longer audit-only.

Known behavioral facts as of issue #1350:

- Headless prompt mode is ``agy -p "<prompt>"``. Stdin prompts are ignored.
- Per-invocation model is ``--model "<Display Name>"`` where the display name
  is one of the strings printed by ``agy models`` (e.g. ``Gemini 3.1 Pro
  (High)``). The runtime model slug (``gemini-3.1-pro-high``) and the display
  string normalize to the same key, so callers may pass either form; an
  unrecognized or empty value falls back to ``default_model``.
- Resume/new conversation is ``--conversation=<uuid>``.
- Write-capable modes use ``--dangerously-skip-permissions``. In addition,
  ``dispatch_smart.py`` forces ``mode="danger"`` for ``--agent agy``
  unconditionally because read-only would otherwise hang on the CLI's
  interactive permission prompts (same protection as ``--agent codex``).
- No known on-disk session or liveness file exists, so stdout is canonical.

MCP / plugin configuration is a Phase-2 follow-up. ``agy plugin`` only
exposes ``import gemini|claude``, ``install <known-target>``, ``enable``,
and ``disable``. The CLI has no plugin-marketplace browse surface as of
1.0.0, and ``agy plugin import gemini`` is a no-op in a default install
because gemini-cli ships no extensions out of the box. The adapter
accepts ``tool_config["mcp_server_names"]`` for API parity with
``GeminiAdapter`` but does not act on it today — wire ``agy plugin
enable <name>`` here once we have concrete MCP servers to consume.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ..result import ParseResult
from .base import InvocationPlan


# Defensive defaults borrowed from Gemini CLI. Agy is new enough that these
# may need adjustment once we see real Antigravity rate-limit errors.
_RATE_LIMIT_PATTERNS = (
    r"RESOURCE_EXHAUSTED",
    r"usage limit reached",
    r"quota exceeded",
    r"daily.{0,10}limit.{0,10}exceeded",
)
_RATE_LIMIT_RE = re.compile("|".join(_RATE_LIMIT_PATTERNS), re.IGNORECASE)

# Outer runner hard_timeout default (``runner.invoke``). Used when callers do
# not pass ``tool_config["hard_timeout"]`` so agy still gets a print-timeout
# above the CLI's 5m default.
_DEFAULT_HARD_TIMEOUT_S = 3600

# Let agy's own --print-timeout fire slightly before the runner SIGKILL so
# long-form authoring fails with a clean CLI error instead of a mid-flush kill.
_PRINT_TIMEOUT_MARGIN_S = 10


# Canonical model display strings accepted by ``agy --model`` (verbatim from
# ``agy models``, refreshed 2026-09-14). The runtime passes a slug like
# ``gemini-3.8-flash-high``; ``_normalize_model`` collapses both that slug and
# the display string to the same key so either form maps here.
# Re-probe with ``agy models`` when Antigravity ships new ids — do not invent.
_AGY_MODEL_NAMES: tuple[str, ...] = (
    "Gemini 3.8 Flash (High)",
    "Gemini 3.8 Flash (Medium)",
    "Gemini 3.8 Flash (Low)",
    "Gemini 3.7 Flash (High)",
    "Gemini 3.7 Flash (Medium)",
    "Gemini 3.7 Flash (Low)",
    "Gemini 3.6 Flash (High)",
    "Gemini 3.6 Flash (Medium)",
    "Gemini 3.6 Flash (Low)",
    "Gemini 3.1 Pro (High)",
    "Gemini 3.1 Pro (Low)",
    "Claude Sonnet 4.6 (Thinking)",
    "Claude Opus 4.6 (Thinking)",
    "GPT-OSS 120B (Medium)",
)


def _normalize_model(value: str) -> str:
    """Collapse a model identifier to its alphanumeric-lowercase form so that a
    slug (``gemini-3.1-pro-high``) and the CLI display string
    (``Gemini 3.1 Pro (High)``) map to the same key."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


# normalized identifier -> canonical ``agy --model`` display string
_AGY_MODEL_BY_NORMALIZED: dict[str, str] = {
    _normalize_model(name): name for name in _AGY_MODEL_NAMES
}


def _agy_print_timeout_s(hard_timeout: int) -> int:
    """Derive ``agy --print-timeout`` from the outer dispatch hard timeout."""
    return max(1, hard_timeout - _PRINT_TIMEOUT_MARGIN_S)


class AgyAdapter:
    """Adapter for the ``agy`` Antigravity CLI."""

    name: str = "agy"
    default_model: str = (
        os.environ.get("KUBEDOJO_AGY_MODEL") or "gemini-3.8-flash-high"
    )
    supported_modes: frozenset[str] = frozenset(
        {"read-only", "workspace-write", "danger"}
    )
    # agy `-p` can exit 0 having called tools but written NO file (the
    # intermittent headless no-write flake, #2099). Without this, an empty
    # authoring run parses ok and passes the runner's HEAD-only danger guard
    # trivially (agy writes files WITHOUT committing, so HEAD never moves),
    # producing a silent false-success that an overnight run would trust and
    # drop the module. Setting this makes the runner flip a write-mode run
    # that left the worktree byte-identical to outcome=error (retryable).
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
        """Build the ``agy`` print-mode invocation.

        ``model`` is mapped to the matching ``agy --model "<Display Name>"``
        flag (see :func:`_normalize_model`). An unrecognized or empty value
        falls back to ``default_model``; if even that is unmappable the flag
        is omitted and agy uses its TUI-selected model.
        """
        if mode not in self.supported_modes:
            raise ValueError(f"AgyAdapter: unsupported mode {mode!r}")

        agy_bin = shutil.which("agy") or str(Path.home() / ".local/bin/agy")
        # `--dangerously-skip-permissions` is unconditional: any tool-using
        # prompt (file read, shell call) triggers an interactive permission
        # prompt that would hang a headless dispatch waiting for human input.
        # The `mode` field is retained for runtime accounting + adapter-API
        # parity, but agy has no finer-grained permission model than this
        # single flag. dispatch_smart.py separately forces mode=danger for
        # --agent agy so callers can't accidentally route around this.
        cmd: list[str] = [agy_bin, "-p", prompt, "--dangerously-skip-permissions"]

        # Add the dispatch working dir (worktree / repo) to agy's workspace.
        # Antigravity sandboxes file ops to ~/.gemini/antigravity-cli/scratch/
        # and IGNORES the process cwd, so without --add-dir agy can neither READ
        # the file under review (-> s117 "reviewed a file it never read"
        # confabulation) nor WRITE authored output into the repo (-> s115
        # "no file written"; it went to the sandbox). One missing flag caused
        # both past "agy fabrication" verdicts. (#1827)
        cmd += ["--add-dir", str(cwd)]

        # ``agy -p`` / ``agy --print`` default to --print-timeout 5m0s. The
        # runner's hard_timeout only bounds the outer process; without this
        # flag long-form authoring dies at ~300s before writing output (#2099).
        tc = tool_config or {}
        hard_timeout = tc.get("hard_timeout", _DEFAULT_HARD_TIMEOUT_S)
        if isinstance(hard_timeout, (int, float)) and hard_timeout > 0:
            print_timeout_s = _agy_print_timeout_s(int(hard_timeout))
            cmd += ["--print-timeout", f"{print_timeout_s}s"]

        resolved_model = self._resolve_model_flag(model)
        if resolved_model:
            cmd += ["--model", resolved_model]

        if session_id:
            cmd.append(f"--conversation={session_id}")

        # Phase 2 follow-up: agy uses `agy plugin` for MCP configuration,
        # not a per-invocation CLI flag like gemini-cli. ``mcp_server_names``
        # is accepted for GeminiAdapter API parity but not acted on yet.
        _ = task_id

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload="",
            output_file=None,
            env_overrides={},
            liveness_paths=(),
        )

    def _resolve_model_flag(self, model: str | None) -> str | None:
        """Map a runtime model slug (or display string) to the canonical
        ``agy --model`` value.

        Tries the caller's ``model`` first, then ``default_model``, so a stale
        placeholder (e.g. the legacy ``"tui-controlled"``) or an empty value
        degrades to the adapter default rather than passing an invalid flag.
        Returns ``None`` only when neither maps, leaving the model unset so
        agy uses its TUI-selected one.
        """
        for candidate in (model, self.default_model):
            if candidate:
                resolved = _AGY_MODEL_BY_NORMALIZED.get(_normalize_model(candidate))
                if resolved:
                    return resolved
        return None

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
        """Parse ``agy -p`` output.

        Stdout is the only known canonical response source. We deliberately do
        not attempt Gemini-style session-file recovery because no Antigravity
        on-disk session location is known yet.
        """
        _ = output_file
        _ = call_start_time
        _ = plan

        stdout_response = (stdout or "").strip()
        stderr_text = (stderr or "").strip()
        combined = f"{stdout_response}\n{stderr_text}"
        hard_limit_hit = bool(_RATE_LIMIT_RE.search(combined))
        call_failed = returncode != 0 or not bool(stdout_response)
        rate_limited = hard_limit_hit and call_failed

        ok = returncode == 0 and bool(stdout_response) and not rate_limited
        response = stdout_response if ok else ""

        # `stderr_excerpt` follows the documented convention in result.py:
        # populated only when there's diagnostic stderr or the call failed.
        # The model hint is informational and lives in the JSONL audit row
        # via env_overrides, not in stderr_excerpt (which is also used as
        # an error-presence signal by some callers).
        stderr_excerpt: str | None = None
        if not ok:
            excerpt_source = stderr_text or stdout_response
            stderr_excerpt = excerpt_source[:500] or None
        elif stderr_text:
            stderr_excerpt = stderr_text[:500]

        return ParseResult(
            ok=ok,
            response=response,
            stderr_excerpt=stderr_excerpt,
            rate_limited=rate_limited,
            session_id=None,
            tokens=None,
        )

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        """Agy has no known on-disk liveness signal; stdout is canonical."""
        _ = plan
        return ()
