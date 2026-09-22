"""ClaudeAdapter — wraps ``npx @anthropic-ai/claude-code@latest`` for the runtime.

Third production adapter. Phase 5 of #1184. Claude is the LAST adapter
to land because it has the most special-case logic:

- **``--bare`` flag**: Skips hooks, LSP, plugin sync, skill walks. Faster
  for scripted calls. Only usable for stateless calls (no session) AND
  when ``ANTHROPIC_API_KEY`` is set (``--bare`` disables OAuth/keychain).

- **``--resume`` vs ``--session-id``**: Two distinct flags with different
  semantics. ``--resume <uuid>`` resumes an existing session (reuses warm
  prompt cache, cheap per call). ``--session-id <uuid>`` starts a NEW
  named session with the given UUID (so future calls can resume it).
  The caller decides which is appropriate; we encode the choice via
  ``tool_config={"is_new_session": bool}``.

- **``--exclude-dynamic-system-prompt-sections``**: CC 2.1.98+ feature
  that improves cross-call prompt caching. Version-gated via
  ``utils.claude_version``.

- **MCP tool restrictions**: ``--mcp-config <path> --allowedTools <list>``
  used by the pipeline reviewers to restrict which MCP tools are
  accessible. Critical for audit gate correctness.

- **``--output-format text``**: Forces plain-text output for machine
  parsing.

Mode handling:
- ``read-only``: No sandbox flag (Claude Code has no explicit sandbox
  for print mode — permissions come from the parent process context).
- ``workspace-write``: Same as read-only for Claude. The distinction
  is enforced by the CALLER deciding whether to pass write-capable
  ``tool_config``, not by a CLI flag.
- ``danger``: Appends ``--dangerously-skip-permissions``. Reserved for
  cases where the caller explicitly needs sandbox bypass.

Liveness paths:
- Returns the project-scoped Claude session JSONL file
  (``~/.claude/projects/<project>/<session>.jsonl``) if we can
  determine it. The runner's mtime poller catches Claude writing
  progress when stdout is buffered or quiet.

Issue: #1184
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from ..result import ParseResult
from .base import InvocationPlan

# Rate-limit patterns (Claude/Anthropic-specific + generic fallbacks)
_RATE_LIMIT_PATTERNS = (
    r"rate limit",
    r"rate_limit",
    r"usage limit",
    r"quota exceeded",
    r"too many requests",
    r"\bHTTP 429\b",
    r"\bstatus 429\b",
    r"\b429\b",
    r"anthropic-rate-limit",
)
_RATE_LIMIT_RE = re.compile("|".join(_RATE_LIMIT_PATTERNS), re.IGNORECASE)

# Anthropic session IDs are UUIDs — used to parse them from stdout if the
# CLI emits them. (Current Claude Code doesn't routinely emit session IDs
# to stdout; the caller passes them IN via tool_config. Parser kept for
# forward compat.)
_SESSION_ID_RE = re.compile(r"session[_-]?id[:=]\s*([0-9a-f-]{8,})", re.IGNORECASE)


class ClaudeAdapter:
    """Adapter for ``npx @anthropic-ai/claude-code@latest`` print mode."""

    name: str = "claude"
    default_model: str = os.environ.get("AB_CLAUDE_MODEL", "claude-opus-5-5")
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
        """Build the Claude Code invocation.

        ``tool_config`` keys honored:
            - ``is_new_session: bool`` — if True, use ``--session-id`` (new
              named session); if False or absent, use ``--resume`` (resume
              existing). Only meaningful when ``session_id`` is provided.
            - ``mcp_config_path: str`` — path to .mcp.json for tool restrictions
            - ``allowed_tools: str`` — comma-separated list passed to --allowedTools
            - ``output_format: str`` — defaults to "text"
            - ``use_bare: bool`` — explicit opt-out of --bare (default: auto-enable
              when no session + ANTHROPIC_API_KEY is set)
            - ``use_path_claude: bool`` — opt in to a PATH-resolved ``claude``
              binary when available; otherwise npx stays the default
        """
        tc: dict[str, Any] = tool_config or {}

        # Command prefix — default to the packaged npx invocation so we
        # avoid drift from stale PATH installs. PATH `claude` is only used
        # when callers explicitly opt in via ``use_path_claude`` or
        # ``KUBEDOJO_CLAUDE_USE_PATH=1``. Full prefix overrides still win via
        # ``tool_config={"cmd_prefix": [...]}``.
        cmd_prefix = tc.get("cmd_prefix")
        if cmd_prefix:
            prefix: list[str] = list(cmd_prefix)
        else:
            use_path_claude = bool(tc.get("use_path_claude")) or os.environ.get("KUBEDOJO_CLAUDE_USE_PATH") == "1"
            claude_bin = shutil.which("claude") if use_path_claude else None
            prefix = [claude_bin] if claude_bin else ["npx", "@anthropic-ai/claude-code@latest"]

        cmd: list[str] = list(prefix)

        cmd.append("-p")

        # --bare: fast path when stateless and API key is set.
        # Disabled if we're resuming/starting a named session (those need
        # full session plumbing).
        has_session = session_id is not None
        use_bare = tc.get("use_bare")
        if use_bare is None:
            # Auto-decide: enable if no session and API key is set
            use_bare = not has_session and bool(os.environ.get("ANTHROPIC_API_KEY"))
        if use_bare and not has_session:
            cmd.append("--bare")

        # Session handling — --session-id (new) vs --resume (existing)
        if has_session:
            is_new = bool(tc.get("is_new_session", False))
            if is_new:
                cmd.extend(["--session-id", session_id])
            else:
                cmd.extend(["--resume", session_id])

        # Explicit permission mode (bridge passes through bypassPermissions
        # to keep tool calls enabled while still allowing non-destructive
        # runs by default).
        permission_mode = tc.get("permission_mode")
        if isinstance(permission_mode, str) and permission_mode:
            cmd.extend(["--permission-mode", permission_mode])

        # Model override + reasoning effort (#2134). Effort can be supplied two
        # ways: an explicit ``tool_config["effort"]`` (mirrors the codex/qwen/
        # deepseek convention), or an effort SUFFIX on the model slug
        # (``claude-sonnet-5-high`` -> model ``claude-sonnet-5`` + effort
        # ``high``, mirroring the agy ``gemini-3.1-pro-high`` slug). Claude Code's
        # headless CLI accepts ``--effort <level>``. Real model ids
        # (claude-sonnet-4-6, claude-opus-4-8, ...) never end in a bare
        # -high/-medium/-low token, so the suffix strip is unambiguous.
        effort = tc.get("effort")
        if model:
            suffix_match = re.match(r"^(.*)-(high|medium|low)$", model)
            if suffix_match:
                # Always strip the effort suffix from the model id (it is not a
                # real API model id). The suffix supplies the effort ONLY when no
                # explicit tool_config["effort"] was given — explicit wins.
                model = suffix_match.group(1)
                if not effort:
                    effort = suffix_match.group(2)
            cmd.extend(["--model", model])
        if isinstance(effort, str) and effort and effort != "default":
            cmd.extend(["--effort", effort])

        # Output format
        cmd.extend(["--output-format", tc.get("output_format", "text")])

        # Mode-specific flags
        if mode == "danger":
            cmd.append("--dangerously-skip-permissions")
        # read-only and workspace-write use the same Claude invocation;
        # write permission is governed by the caller's tool_config, not
        # a distinct CLI mode flag.

        # MCP tool restrictions (pipeline reviewers)
        mcp_config_path = tc.get("mcp_config_path")
        allowed_tools = tc.get("allowed_tools")
        if mcp_config_path and allowed_tools:
            cmd.extend(["--mcp-config", str(mcp_config_path), "--allowedTools", allowed_tools])

        # Cache-warmth optimization (CC 2.1.98+)
        try:
            from utils.claude_version import supports_exclude_dynamic_system_prompt_sections
            # Probe the same prefix we're about to run so version gating
            # stays aligned with the selected command.
            probe_prefix = tuple(prefix)
            if supports_exclude_dynamic_system_prompt_sections(probe_prefix):
                cmd.append("--exclude-dynamic-system-prompt-sections")
        except ImportError:
            pass  # Graceful degradation if helper unavailable

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload=prompt,
            output_file=None,
            env_overrides={},
            liveness_paths=self._resolve_liveness_paths(cwd),
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
        """Parse Claude CLI output into a ParseResult.

        Claude Code writes the response to stdout. On success, stdout is
        the clean output; on failure, stderr carries the diagnostic.
        """
        # plan / call_start_time unused — Claude doesn't need session-file
        # recovery because the Claude CLI flushes stdout before exit.
        # Kept in the signature to match the uniform protocol (see
        # adapters/base.py).
        _ = output_file  # Unused — Claude doesn't use -o file
        _ = plan
        _ = call_start_time

        # Rate-limit detection across both streams
        combined = f"{stdout}\n{stderr}"
        pattern_hit = bool(_RATE_LIMIT_RE.search(combined))
        call_failed = returncode != 0 or not stdout.strip()
        rate_limited = pattern_hit and call_failed

        # Success classification
        ok = returncode == 0 and bool(stdout.strip()) and not rate_limited
        response = stdout.strip() if ok else ""

        # Stderr excerpt on failure
        stderr_excerpt: str | None = None
        if not ok:
            excerpt_source = stderr.strip() or stdout.strip() or ""
            stderr_excerpt = excerpt_source[:500] or None

        # Session ID extraction (rare — caller usually passes it IN)
        session_id: str | None = None
        sid_match = _SESSION_ID_RE.search(stdout or "")
        if sid_match:
            session_id = sid_match.group(1)

        return ParseResult(
            ok=ok,
            response=response,
            stderr_excerpt=stderr_excerpt,
            rate_limited=rate_limited,
            session_id=session_id,
            tokens=None,  # Claude CLI doesn't expose tokens in text output
        )

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        """Return the project-scoped Claude session JSONL dir for mtime polling.

        We can't know the exact session filename in advance (Claude Code
        creates it when the session starts), so we return the parent
        directory. The runner's mtime poller watches the dir itself, which
        bumps on any child file write — good enough for liveness signal.
        """
        # Caller provided cwd; use it to derive the Claude project dir.
        # The dir is ~/.claude/projects/<project-slug>/ where project-slug
        # is the cwd with special chars replaced.
        _ = plan  # Plan has no cwd; we stored it as env_overrides isn't enough
        # Fall back to the project-wide directory — any recent activity
        # across Claude sessions counts as liveness.
        claude_projects_dir = Path.home() / ".claude" / "projects"
        if claude_projects_dir.exists():
            # Find the most recent project subdir as a best-effort signal
            try:
                subdirs = [p for p in claude_projects_dir.iterdir() if p.is_dir()]
                if subdirs:
                    most_recent = max(subdirs, key=lambda p: p.stat().st_mtime)
                    return (most_recent,)
            except OSError:
                pass
        return ()

    def _resolve_liveness_paths(self, cwd: Path) -> tuple[Path, ...]:
        """Same as liveness_signal_paths but computable at build_invocation time."""
        _ = cwd
        claude_projects_dir = Path.home() / ".claude" / "projects"
        if claude_projects_dir.exists():
            try:
                subdirs = [p for p in claude_projects_dir.iterdir() if p.is_dir()]
                if subdirs:
                    most_recent = max(subdirs, key=lambda p: p.stat().st_mtime)
                    return (most_recent,)
            except OSError:
                pass
        return ()
