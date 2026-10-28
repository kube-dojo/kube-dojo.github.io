"""CodexAdapter — wraps ``codex exec`` for the agent runtime.

First real adapter. Proves the protocol shape works against a real CLI.
Lifted from the prior art in ``scripts/ai_agent_bridge/_codex.py`` and
``scripts/build/dispatch.py`` (Codex branch) — same flag semantics, now
routed through the unified runtime.

Key design points:

- **CLI resume support.** CodexAdapter follows the registry resume
  policy and accepts ``session_id`` for bridge sessions by invoking
  ``codex resume <id>`` when provided.
- **One mode: danger only.** read-only and workspace-write are forbidden —
  Codex needs network + filesystem to fact-check and to use the live web
  tool. See PR #981 (mode=danger mandatory) and this PR (workspace-write
  escape hatch removed).
- **Output file always used.** ``codex exec -o <tmpfile>`` writes the final
  agent message to a file; we read it in ``parse_response``. The file path
  goes into ``liveness_signal_paths`` so the runner's mtime poller catches
  Codex writing progress even when stdout is quiet.
- **Session ID comes only from the stderr startup banner.** Model output and
  shared rollout files cannot authorize a subsequent session resume.

Issue: #1184
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from ..result import ParseResult
from .base import InvocationPlan

_UUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


def _banner_session_id(text: str) -> str | None:
    """Read exactly one UUID from startup metadata before the echoed prompt."""
    banner = text.split("\n--------\n", 2)
    if len(banner) != 3 or not banner[0].startswith("OpenAI Codex v"):
        return None
    lines = [line for line in banner[1].splitlines() if line.lower().startswith("session id:")]
    if len(lines) != 1:
        return None
    match = re.fullmatch(rf"session id:[ \t]*({_UUID_RE.pattern})[ \t]*", lines[0], re.IGNORECASE)
    return match.group(1) if match else None

# Stderr phrases that indicate the provider rate-limited us. Ordered
# roughly by specificity — specific phrases first, generic last.
_RATE_LIMIT_PATTERNS = (
    r"usage limit reached",
    r"rate limit",
    r"rate_limit",
    r"quota exceeded",
    r"too many requests",
    r"\bHTTP 429\b",
    r"\bstatus 429\b",
    r"\b429\b",
)
_RATE_LIMIT_RE = re.compile("|".join(_RATE_LIMIT_PATTERNS), re.IGNORECASE)

# Matches a dashes-only line (at least 3 dashes, nothing else on the
# line). Used to split Codex's stderr into segments so we can isolate
# the post-prompt portion for rate-limit pattern matching. MULTILINE
# so ^/$ match at each line boundary.
_CODEX_DIVIDER_LINE_RE = re.compile(r"^-{3,}\s*$", re.MULTILINE)


def _strip_codex_prompt_echo(stderr: str) -> str:
    """Return only the portion of Codex stderr that is safe to
    pattern-match for rate-limit errors.

    Codex CLI (with -o <file>) lays out stderr as a sequence of
    sections separated by dashes-only lines::

        OpenAI Codex v0.118.0 ...       ← banner
        --------
        workdir: ...
        model: ...
        --------
        user                            ← echoed prompt starts
        <entire user prompt>
        --------
        codex                           ← Codex's own output
        <reasoning + final message>
        tokens used
        <n>

    On a rate-limit error, Codex exits non-zero and writes the error
    message AFTER the last divider — in the "codex" or equivalent
    section. The echoed user prompt can contain ANY text, including
    legitimate inline dashes-only lines (a code block showing a
    divider, a Markdown horizontal rule, a consultation prompt
    literally discussing rate limits). Any regex that tries to
    identify "the prompt block" by matching between two dividers can
    be defeated by a prompt containing its own dividers.

    Fix: don't try to strip the prompt at all. Instead, take the
    stderr body AFTER the LAST divider line — that region is
    guaranteed to be Codex's own output, never echoed prompt, because
    the prompt echo always appears before Codex's response section.
    If there are no dividers at all (degenerate cases: truncated
    output, early crash before banner), fall back to the whole
    stderr.

    See #1184 Gemini 2026-04-10 review for the incident that led here.
    """
    if not stderr:
        return stderr
    # Find the position right after the LAST divider line.
    last_divider = None
    for m in _CODEX_DIVIDER_LINE_RE.finditer(stderr):
        last_divider = m
    if last_divider is None:
        # No dividers — return as-is. Likely a very early crash.
        return stderr
    return stderr[last_divider.end():]


class CodexAdapter:
    """Adapter for ``codex exec`` (OpenAI ChatGPT Codex CLI)."""

    name: str = "codex"
    default_model: str = os.environ.get("AB_CODEX_MODEL", "gpt-6.1-terra")
    supported_modes: frozenset[str] = frozenset({"danger"})

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
        """Build the codex exec invocation.

        Uses ``session_id`` as ``codex resume <id>`` when present.
        Supports ``tool_config`` flags from bridge:

        - ``{"enable_search": True}`` enables web grounding in `codex`.
        - Any other keys are ignored.
        """
        tc = tool_config or {}

        # Resolve binary. shutil.which handles PATH lookup; fall back to
        # bare "codex" if not on PATH so subprocess.Popen can report the
        # error clearly.
        codex_bin = shutil.which("codex") or "codex"

        # Pick a unique output file inside /tmp.
        # Include task_id for human debuggability, but sanitize it:
        # arbitrary task_id strings (issue slugs, URLs, user input)
        # could contain slashes, nulls, or path separators that would
        # make NamedTemporaryFile create files in unintended locations
        # or fail entirely. Strip everything that isn't alphanumeric
        # or a safe punctuation char. Codex 2026-04-10 audit finding.
        safe_suffix = ""
        if task_id:
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in task_id)
            safe_suffix = f"-{safe[:60]}"  # cap length too
        with tempfile.NamedTemporaryFile(
            prefix=f"codex-runtime{safe_suffix}-",
            suffix=".txt",
            delete=False,
        ) as output_fd:
            output_path = Path(output_fd.name)

        # --search enables Codex's live web tool. Top-level flag, not an
        # exec subflag. Driven by KUBEDOJO_CODEX_SEARCH so dispatch_smart
        # can set it per task class.
        # Default OFF for non-bridge callers; explicit tool_config from
        # bridge enables web grounding for investigation.
        if "enable_search" in tc:
            use_search = bool(tc.get("enable_search"))
        else:
            use_search = os.environ.get("KUBEDOJO_CODEX_SEARCH", "0") == "1"
        cmd: list[str] = [codex_bin]
        effort = os.environ.get("KUBEDOJO_CODEX_EFFORT", "").strip()
        if effort:
            cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
        if session_id:
            if use_search:
                cmd.append("--search")
            cmd.extend(
                [
                    "exec",
                    "resume",
                    session_id,
                    "--skip-git-repo-check",
                    "-o", str(output_path),
                    "-m", model or self.default_model,
                ]
            )
            cmd.extend(self._mode_flags(mode))
            cmd.append("-")
            return InvocationPlan(
                cmd=cmd,
                cwd=cwd,
                stdin_payload=prompt,
                output_file=output_path,
                env_overrides={},
                liveness_paths=(output_path,),
            )

        if use_search:
            cmd.append("--search")
        cmd.extend(
            [
                "exec",
                "--skip-git-repo-check",
                "-C", str(cwd),
                "--color", "never",
                "-o", str(output_path),
                "-m", model or self.default_model,
            ]
        )
        cmd.extend(self._mode_flags(mode))
        cmd.append("-")  # Read prompt from stdin.

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload=prompt,
            output_file=output_path,
            env_overrides={},
            liveness_paths=(output_path,),
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
        """Read only this invocation's unique final-output file and CLI banner.

        Shared rollout files are not an ownership boundary: resumed calls append
        to an old file, and native child agents create new files of their own.
        Never recover an answer or a session ID by picking a global rollout.
        """
        _ = plan, call_start_time
        file_output = ""
        if output_file is not None:
            try:
                file_output = output_file.read_text("utf-8", errors="replace").strip()
            except OSError:
                file_output = ""

        # Successful final output cannot be a provider rate-limit failure.
        # Preserve signal-kill classification instead of matching prompt echoes.
        rate_limited = False
        if returncode >= 0 and (returncode != 0 or not file_output):
            diagnostic = "\n".join((stdout, _strip_codex_prompt_echo(stderr), file_output))
            rate_limited = bool(_RATE_LIMIT_RE.search(diagnostic))

        ok = bool(file_output) and not rate_limited
        return ParseResult(
            ok=ok,
            response=file_output if ok else "",
            stderr_excerpt=(stderr.strip() or file_output)[:500] or None if not ok else None,
            rate_limited=rate_limited,
            # stdout can be the model's final answer. Even a complete banner
            # quoted there is untrusted, so it never supplies a fresh session ID.
            session_id=_banner_session_id(stderr),
            tokens=None,
        )

    def check_early_reap(
        self, plan: InvocationPlan, *, call_start_time: float | None = None,
    ) -> bool:
        """Let the CLI exit or reach its timeout; never reap via shared files."""
        _ = plan, call_start_time
        return False

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        """Watch only the unique output file; the runner also watches stderr."""
        return (plan.output_file,) if plan.output_file is not None else ()

    @staticmethod
    def _mode_flags(mode: str) -> list[str]:
        """Map runtime mode → codex exec sandbox flags."""
        if mode == "danger":
            return ["--dangerously-bypass-approvals-and-sandbox"]
        raise ValueError(
            f"CodexAdapter: mode {mode!r} is not supported. "
            "Codex always runs in danger mode (sandbox bypass + live web). "
            f"Supported: {sorted(CodexAdapter.supported_modes)}"
        )
