"""DeepSeekAdapter — wraps ``hermes -z`` (deepseek provider) for the agent runtime.

Fourth production adapter. Brings deepseek-v4 Pro (and successors) online as a
peer to codex / claude / gemini for code review, deliberation, and fix lanes.

Key design points:

- **Transport:** ``hermes`` CLI in oneshot mode (``--oneshot=<prompt>``
  argv binding). Two provider lanes: ``deepseek`` (DEFAULT — first-party
  API, China-hosted, cheapest, local-only) and ``openrouter`` (opt-in —
  US-hosted proxy for residency / failover / CI-eligibility). Provider is
  resolved by ``_resolve_provider`` (tool_config > env > model slug).
- **Modes:** All three (read-only / workspace-write / danger) supported.
  Mode → hermes toolset mapping is conservative for read-only (no
  terminal/file tools), permissive for workspace-write and danger.
- **Project context:** hermes injects KubeDojo project state via its
  ``memory`` + ``skills`` toolsets unless suppressed. We keep this on for
  review/code work (gives DeepSeek situational awareness) but disable via
  ``--ignore-user-config --ignore-rules`` when the caller passes
  ``tool_config={"isolated": True}`` (used for benchmark / calibration).
- **No session resume.** ``resume_policy=never`` in the registry — hermes
  has session semantics but cross-worktree contamination would mirror the
  Codex footgun. Defensively ignored even if passed.
- **Liveness:** hermes streams output to stdout, so the runner's stdout
  watchdog handles liveness. ``liveness_signal_paths()`` returns ``()``.

Calibration (2026-05-17): Pro tied 5/5 with claude on content review; gold-tier
reviewer. Hallucination rate 3/4 on code — caller should not promote a DS Pro
claim to Green without independent verification (curl+pdftotext+grep) for
factual claims (mirrors gemini hallucination policy per
[[feedback_gemini_hallucinates_anchors]]). Flash is 3× faster than Pro;
suited for plan / architect / UK translation lanes.

In read-only mode, DeepSeek runs with a restricted Hermes toolset (web-only). If
the model emits unfulfilled tool-use intent (e.g. ``<bash>`` blocks), the returned
text is a non-executable stub and not a useful review. See
``feedback_ds_pro_review_needs_workspace_write.md``.

Status flagged for the user:
- DeepSeek adds a second cheap/fast lane (V4 Flash) while preserving Pro for
  high-value review roles.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from ..result import ParseResult
from .base import InvocationPlan

_logger = logging.getLogger(__name__)
_HERMES_CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"

# Rate-limit patterns. DeepSeek follows Hermes transport patterns, including
# standard 429 signaling.
_RATE_LIMIT_PATTERNS = (
    r"rate limit",
    r"rate_limit",
    r"usage limit",
    r"quota exceeded",
    r"too many requests",
    r"\bHTTP 429\b",
    r"\bstatus 429\b",
    r"\b429\b",
)
_RATE_LIMIT_RE = re.compile("|".join(_RATE_LIMIT_PATTERNS), re.IGNORECASE)
_TOOL_USE_INTENT_RE = re.compile(
    r"<\s*(bash|tool_use|tool|terminal|shell)\b[^>]*>",
    re.IGNORECASE,
)

# Hermes startup warnings we strip before declaring success.
_HERMES_BANNER_RE = re.compile(
    r"^(💡 Python project detected\..*|hermes -z:.*)$",
    re.MULTILINE,
)

# Toolsets per mode. Hermes built-in toolsets are documented under
# `hermes tools list`. We deliberately exclude memory / skills from
# read-only to keep calibration runs reproducible; they're great for
# real review/code work though.
# `browser` (headless browser automation) gives live web fact-checking WITHOUT
# Firecrawl — the `web` tool (web_search/web_extract) is Firecrawl-gated and
# fails closed when FIRECRAWL_API_KEY is unset, which silently starved reviews of
# fact-checking and drove hallucination (s121, #1827). `browser` works standalone.
_TOOLSETS_READ_ONLY = "web,browser"
_TOOLSETS_WORKSPACE = "web,browser,file,terminal,code_execution,todo"
_TOOLSETS_DANGER = "web,browser,file,terminal,code_execution,todo,memory,skills"


def _read_hermes_config(path: Path = _HERMES_CONFIG_PATH) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _sources_mcp_registered(config: dict[str, Any]) -> bool:
    servers = config.get("mcp_servers")
    if not isinstance(servers, dict):
        return False
    sources = servers.get("sources")
    if not isinstance(sources, dict):
        return False
    return bool(sources.get("enabled") is not False and sources.get("url"))


def translate_mcp_prefix_for_hermes(prompt: str) -> str:
    """Rewrite ``mcp__sources__X`` to ``mcp_sources_X`` for Hermes routing."""
    return prompt.replace("mcp__sources__", "mcp_sources_")


def _resolve_provider(tool_config: dict[str, Any], model: str) -> str:
    """Pick the Hermes provider for a DeepSeek dispatch.

    Two lanes share this adapter:

    1. ``deepseek`` (**default**) — DeepSeek's first-party API
       (``api.deepseek.com``, China-hosted). Cheapest path; local-only —
       never dispatched from CI (``feedback_no_china_apis_from_gh_actions``).
    2. ``openrouter`` — OpenRouter's US-hosted proxy. Opt-in, for residency /
       failover / CI-eligibility. NOTE: OpenRouter's default DeepSeek pool can
       still route to DeepSeek's own China API — pin non-China hosts on the
       OpenRouter side (``provider.only``/``ignore`` + ``data_collection: deny``)
       or you keep China residency plus an extra hop.

    Precedence (first match wins), mirroring
    ``dispatch_smart._hermes_provider_for_model``:

    1. explicit ``tool_config["provider"]`` — caller intent.
    2. ``KUBEDOJO_HERMES_PROVIDER`` env — operator override.
    3. model-slug — ONLY an explicit ``openrouter/…`` prefix routes via
       ``openrouter``; a bare first-party slug (``deepseek-v4-pro``) via
       ``deepseek``. Any other ``vendor/model`` form raises: the old "any
       slash means openrouter" inference silently billed the metered
       OpenRouter account (incident #2245, 2026-07-07).
    """
    explicit = tool_config.get("provider")
    if explicit:
        return str(explicit)
    env_override = os.environ.get("KUBEDOJO_HERMES_PROVIDER")
    if env_override:
        return env_override
    if model.startswith("openrouter/"):
        return "openrouter"
    if "/" in model:
        raise ValueError(
            f"Ambiguous DeepSeek model slug {model!r}: a vendor/model form no "
            "longer implies the OpenRouter proxy (silent-billing incident "
            "#2245). Opt in explicitly with an 'openrouter/…' slug, "
            "tool_config={'provider': 'openrouter'}, or "
            "KUBEDOJO_HERMES_PROVIDER."
        )
    return "deepseek"


class DeepSeekAdapter:
    """Adapter for ``hermes -z`` with the deepseek provider."""

    name: str = "deepseek"
    # deepseek-flash is the canonical DeepSeek-V4.1-Flash API id (first-party
    # hermes provider=deepseek). Legacy deepseek-v4-pro / deepseek-v4-flash
    # names still resolve upstream as temporary aliases.
    # Override via AB_DEEPSEEK_MODEL when needed.
    default_model: str = os.environ.get("AB_DEEPSEEK_MODEL", "deepseek-flash")
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
        """Build the hermes oneshot invocation.

        ``tool_config`` keys honored:
            - ``isolated: bool`` — if True, pass ``--ignore-user-config
              --ignore-rules`` to bypass hermes's project-context
              injection. Default False (project context is feature, not
              bug, for review/code work).
            - ``toolsets: str`` — comma-separated override for ``-t``.
              Wins over the mode-default mapping.
            - ``provider: str`` — override hermes provider. Default
              ``deepseek`` (first-party, China-hosted); pass ``openrouter``
              (US-hosted proxy) for residency / failover / CI-eligibility.
              Also selectable via ``KUBEDOJO_HERMES_PROVIDER`` or an
              OpenRouter model slug — see ``_resolve_provider``.
            - ``effort: str`` — reasoning effort label. Hermes does not
              expose this as a flag today; we forward it via prompt
              prefix when ``"xhigh"`` is requested. Tracking issue: see
              ``project_hermes_model_inventory.md``.
            - ``yolo: bool`` — pass ``--yolo`` (auto-accept tool calls).
              Default True for write modes, False for read-only.
            - ``accept_hooks: bool`` — pass ``--accept-hooks``. Default
              False; opt-in for callers that want project hooks to fire.
        """
        if mode not in self.supported_modes:
            raise ValueError(f"DeepSeekAdapter: unsupported mode {mode!r}")

        tc: dict[str, Any] = tool_config or {}

        binary = shutil.which("hermes") or "hermes"
        cmd: list[str] = [binary]

        # Reasoning effort hint applied first so the final prompt string is
        # bound via --oneshot= below.
        effort = tc.get("effort")
        final_prompt = prompt
        if effort and effort != "default":
            final_prompt = f"[Reasoning effort hint: {effort}]\n\n{prompt}"

        hermes_mcp_servers = tc.get("hermes_mcp_servers") or []
        if "sources" in hermes_mcp_servers:
            config = _read_hermes_config()
            if not _sources_mcp_registered(config):
                _logger.warning(
                    "Hermes DeepSeek did not find enabled mcp_servers.sources in "
                    "~/.hermes/config.yaml; MCP tool availability depends on Hermes config"
                )
            final_prompt = translate_mcp_prefix_for_hermes(final_prompt)

        # Model — resolve the provider from the RAW slug first (an explicit
        # ``openrouter/`` prefix is the opt-in marker, #2245), then strip that
        # prefix so hermes -m receives the provider-native model id
        # (OpenRouter's catalog uses ``vendor/model``).
        effective_model = model or self.default_model
        provider = _resolve_provider(tc, effective_model)
        if effective_model.startswith("openrouter/"):
            effective_model = effective_model.removeprefix("openrouter/")
        cmd.extend(["-m", effective_model])

        # Provider — first-party ``deepseek`` (China-hosted) is the default;
        # OpenRouter's US-hosted proxy is EXPLICIT-ONLY: tool_config, the
        # KUBEDOJO_HERMES_PROVIDER env, or an ``openrouter/…`` model slug.
        # Silent fallbacks removed after incident #2245. See
        # ``_resolve_provider``.
        cmd.extend(["--provider", provider])

        # Toolset selection — caller override wins, else mode default.
        toolsets = tc.get("toolsets")
        if not toolsets:
            if mode == "read-only":
                toolsets = _TOOLSETS_READ_ONLY
            elif mode == "workspace-write":
                toolsets = _TOOLSETS_WORKSPACE
            else:  # danger
                toolsets = _TOOLSETS_DANGER
        cmd.extend(["-t", toolsets])

        # Auto-accept tool calls. Required for non-interactive runs that
        # do file edits or shell ops. Read-only stays prompt-only by
        # default so we don't accidentally grant network egress through
        # the web tool's confirm step.
        yolo_default = mode in ("workspace-write", "danger")
        if bool(tc.get("yolo", yolo_default)):
            cmd.append("--yolo")

        if bool(tc.get("accept_hooks", False)):
            cmd.append("--accept-hooks")

        # Isolation: bypass user config + project rules. Used for
        # calibration / benchmark runs where deterministic output is
        # more important than context awareness.
        if bool(tc.get("isolated", False)):
            cmd.extend(["--ignore-user-config", "--ignore-rules"])

        # --oneshot (-z): one-shot mode; PROMPT must be a single argv token.
        # Use ``--oneshot=<prompt>`` so flag-like prompts (e.g. ``--provider``)
        # are bound as the flag value, not parsed as a separate CLI flag.
        # Do NOT use stdin (``hermes -z -``) — that is interpreted as
        # "no prompt, project-introspection mode".
        cmd.append(f"--oneshot={final_prompt}")

        # Defensively drop session_id — resume_policy=never.
        _ = session_id
        _ = task_id

        return InvocationPlan(
            cmd=cmd,
            cwd=cwd,
            stdin_payload="",  # prompt is in argv; stdin must be empty
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
        """Parse hermes -z output.

        Hermes prints the final assistant message to stdout. Diagnostic
        warnings ("💡 Python project detected.", argument errors) appear
        in stdout/stderr depending on how hermes was invoked.
        """
        _ = output_file
        _ = plan
        _ = call_start_time

        # Strip hermes banners that aren't part of the response.
        clean_stdout = _HERMES_BANNER_RE.sub("", stdout or "").strip()
        tool_use_unfulfilled = bool(_TOOL_USE_INTENT_RE.search(clean_stdout))

        if tool_use_unfulfilled and len(clean_stdout) < 1000:
            return ParseResult(
                ok=False,
                response="",
                stderr_excerpt=(
                    "DS Pro returned tool-use intent without execution "
                    f"({len(clean_stdout)} chars). The hermes toolset for this mode "
                    "doesn't include the requested tool. For DS Pro reviews, re-dispatch "
                    "with --mode workspace-write (grants terminal/file tools), or fall "
                    "back to qwen/claude. Raw stub: " + clean_stdout[:200]
                ),
                rate_limited=False,
                session_id=None,
                tokens=None,
            )

        combined = f"{clean_stdout}\n{stderr or ''}"
        pattern_hit = bool(_RATE_LIMIT_RE.search(combined))
        call_failed = returncode != 0 or not bool(clean_stdout)
        rate_limited = pattern_hit and call_failed

        ok = returncode == 0 and bool(clean_stdout) and not rate_limited
        response = clean_stdout if ok else ""

        stderr_excerpt: str | None = None
        if not ok:
            excerpt_source = (stderr or "").strip() or (stdout or "").strip()
            stderr_excerpt = excerpt_source[:500] or None

        return ParseResult(
            ok=ok,
            response=response,
            stderr_excerpt=stderr_excerpt,
            rate_limited=rate_limited,
            session_id=None,
            tokens=None,
        )

    def liveness_signal_paths(self, plan: InvocationPlan) -> tuple[Path, ...]:
        """Hermes streams to stdout; the runner's stdout watchdog covers liveness."""
        _ = plan
        return ()
