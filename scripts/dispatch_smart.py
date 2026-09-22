"""Smart-routing headless dispatcher.

Single CLI for dispatching work to a headless agent that picks an
appropriate model based on the task class — instead of always burning
the top-tier model from the orchestrator session.

Why: the orchestrator runs on claude-opus-4-8. Routine search/edit work
shouldn't burn opus (or gpt-5.5) when a smaller model would do fine.
This wrapper lets the orchestrator say "do this kind of work, pick the
right model" without manually choosing model + mode + worktree every
time. Mirrors the economical multi-agent policy in AGENTS.md (PR #870)
so cross-agent dispatches follow the same tiering as Codex's internal
subagents.

Usage:
    # Cheap search (haiku, read-only) — default agent=claude
    .venv/bin/python scripts/dispatch_smart.py search \
        "Find every place that imports agent_runtime.runner.invoke."

    # Same task class, routed to codex (gpt-5.4-mini)
    .venv/bin/python scripts/dispatch_smart.py search --agent codex \
        "Find every place that imports agent_runtime.runner.invoke."

    # Mid-tier edit — codex picks gpt-5.3-codex-spark (separate counter)
    .venv/bin/python scripts/dispatch_smart.py edit --agent codex \
        --worktree .worktrees/codex-fix-issue-500 \
        --new-branch codex/fix-issue-500 \
        "Fix the off-by-one in scripts/foo.py:142, add a regression test."

    # Heavy work — judgment / integration (opus or gpt-5.5)
    .venv/bin/python scripts/dispatch_smart.py architect \
        --worktree .worktrees/claude-redesign-pipeline \
        --new-branch claude/redesign-pipeline \
        "Redesign the quality pipeline so phase ordering is data-driven."

Skill auto-loading:
    Role-specific shared skills are prepended to dispatched prompts by task
    class. ``draft`` and ``edit`` load ``curriculum-writer``; ``review``
    loads ``cross-family-reviewer``; ``architect`` and ``search`` do not
    load a skill. Override with ``--skill <name>`` or disable with
    ``--no-skill`` for narrow mechanical dispatches where the brief is
    already self-contained::

        .venv/bin/python scripts/dispatch_smart.py review \
            --agent codex --skill k8s-cert-expert \
            "Review this Kubernetes certification module."

Task classes — model mapping per agent:

    class       claude                       codex            cursor
    -------     --------------------------   --------------   --------------
    search      claude-haiku-4-5-20251001    gpt-5.6-luna     composer-2.5
    edit        claude-sonnet-5              gpt-6-astra      grok-4.7-high
    draft       claude-sonnet-5        gpt-6-astra     grok-4.7-high
    review      claude-fable-5-1       gpt-6-astra     grok-4.7-high
    architect   claude-fable-5-1       gpt-6-astra     grok-4.7-high

Each dispatch is recorded to ``logs/smart_dispatch.jsonl`` for usage
auditing. The FULL response body is also persisted to
``logs/dispatch_responses/<task_id>.txt`` so callers that pipe stdout
through ``tail``/``head`` (e.g. background bash tasks) can recover the
body even if the live stream was truncated. The JSONL row's
``response_path`` field is the canonical pointer. Pattern::

    python scripts/dispatch_smart.py review --task-id review-foo ... | tail -N
    # body may be truncated in stdout; recover from disk:
    cat "$(jq -r 'select(.task_id == "review-foo") | .response_path' logs/smart_dispatch.jsonl)"

Reuse with --dry-run to print the chosen plan without firing.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _primary_checkout_root(repo_root: Path) -> Path:
    """Resolve the primary checkout root when this script runs in a worktree."""
    if repo_root.parent.name == ".worktrees":
        return repo_root.parent.parent
    return repo_root


PRIMARY_REPO = _primary_checkout_root(REPO)
# Anchor logs to the primary checkout so worktree dispatches do not
# fragment the audit trail across .worktrees/*/logs/.
LOG_PATH = PRIMARY_REPO / "logs" / "smart_dispatch.jsonl"
RESPONSE_DIR = PRIMARY_REPO / "logs" / "dispatch_responses"
MCP_CONFIG_PATH = PRIMARY_REPO / ".mcp.json"
# gemini-cli RETIRED 2026-07-01 (no gemini-cli; the Google lane is now agy).
# Hermes RETIRED for dispatch (2026-09-16): deepseek → opencode deepseek-direct;
# grok-4.7 → native grok CLI (replaces grok-4.6; frontier tier with
# Claude Fable and OpenAI Astra). Claude gates MCP on repo .mcp.json. agy loads MCP
# natively from ~/.gemini/config/mcp_config.json (no --mcp flag). qwen still
# rides the residual hermes adapter but is NOT advertised as --mcp-capable
# (#2131) — it lacks the mcp__sources__ → mcp_sources_ prompt rewrite.
MCP_SUPPORTED_AGENTS = frozenset({"claude"})
HERMES_MCP_AGENTS = frozenset()  # hermes dispatch retired; empty by design
HERMES_MCP_TASK_CLASSES = frozenset({"draft", "edit"})
# review/search -> read-only sources tools; draft/edit -> write-capable author
# tools (both curated in scripts/dispatch.py). See _import_dispatch_mcp_constants.
CLAUDE_MCP_TASK_CLASSES = frozenset({"review", "search", "draft", "edit"})
CLAUDE_MCP_AUTHOR_TASK_CLASSES = frozenset({"draft", "edit"})

# Skill auto-loading — R2 follow-up to PR #1575 and the agents_extensions/
# layout introduced there.
SKILL_FOR_TASK_CLASS: dict[str, str] = {
    "draft": "curriculum-writer",
    "edit": "curriculum-writer",
    "review": "cross-family-reviewer",
    # architect, search -> no skill
}

SHARED_SKILLS_DIR = PRIMARY_REPO / "agents_extensions" / "shared" / "skills"
CLAUDE_SKILLS_DIR = PRIMARY_REPO / "agents_extensions" / "claude" / "skills"


SUPPORTED_AGENTS = (
    "agy",
    "claude",
    "codex",
    "cursor",
    "deepseek",
    # "gemini" RETIRED 2026-07-01 — no gemini-cli; use "agy" for the Google
    # lane (agy has its own `--model` display names, e.g. gemini-3.1-pro-high).
    "grok",
    # "hermes" RETIRED 2026-09-16 — kept in argparse only to fail closed with
    # a redirect message; not a live dispatch seat.
    "hermes",
    "kimi",  # ACP oneshot (kimi -p is text-only; prefer kimi-code/k3-256k)
    "opencode",
    "qwen",
)

HERMES_RETIRED_MESSAGE = (
    "[smart] REFUSED: --agent hermes is retired. "
    "Use --agent grok --model grok-4.7 for xAI content/CF "
    "(native grok CLI; replaces grok-4.6; frontier tier with Fable and Astra; "
    "grok-build is gone). "
    "Use --agent deepseek --model deepseek-flash for DeepSeek V4.1 Flash "
    "(first-party, local-only). "
    "OpenCode and Qwen are not routing seats."
)

OPENCODE_QWEN_RETIRED_MESSAGE = (
    "[smart] REFUSED: --agent opencode and --agent qwen are not routing seats. "
    "DeepSeek V4.1 Flash is --agent deepseek --model deepseek-flash "
    "(local-only). Cursor is --agent cursor --model grok-4.7-high. "
    "Do not route Qwen or OpenCode."
)


@dataclass(frozen=True)
class TaskClassConfig:
    models: dict[str, str]  # agent -> model
    default_mode: str  # "read-only" | "workspace-write" | "danger"
    default_timeout_s: int
    description: str
    codex_search: bool = False  # opt-in per class
    grok_reasoning_effort: str | None = None  # native grok --reasoning-effort


# Model slugs below are LIVE defaults as of 2026-09-22. Re-probe before trusting
# memory. Override per call with `--model`.
# Claude catalog: architect/review = claude-fable-5-1 (Fable 5.1);
# search/edit/draft = claude-sonnet-5 (Sonnet 5).
# Codex config model is gpt-6-astra (the GPT-6 seat; there is no gpt-6.0 slug).
# Cursor catalog has no bare grok-4.7; Grok 4.7 High is grok-4.7-high.
# DeepSeek V4.1 Flash is deepseek-flash (first-party). OpenCode and Qwen are
# not routing seats. Native grok remains grok-4.7.
TASK_CLASSES: dict[str, TaskClassConfig] = {
    "search": TaskClassConfig(
        models={
            "agy": "gemini-3.8-flash-high",
            "claude": "claude-haiku-4-5-20251001",
            "codex": "gpt-5.6-luna",
            "deepseek": "deepseek-flash",  # V4.1 Flash, first-party, local-only
            "grok": "grok-4.7",
            "cursor": "composer-2.5",
            "kimi": "kimi-code/k3-256k",
        },
        default_mode="read-only",
        default_timeout_s=600,
        description="cheap codebase scans, file lookups, factual Q&A",
        codex_search=False,
        grok_reasoning_effort="low",
    ),
    "edit": TaskClassConfig(
        models={
            "agy": "gemini-3.8-flash-high",
            "claude": "claude-sonnet-5",
            "codex": "gpt-6-astra",
            "deepseek": "deepseek-flash",
            "grok": "grok-4.7",
            "cursor": "grok-4.7-high",
            "kimi": "kimi-code/k3-256k",
        },
        default_mode="workspace-write",
        default_timeout_s=1800,
        description="small/medium code edits, single-file fixes",
        codex_search=False,
    ),
    "draft": TaskClassConfig(
        models={
            "agy": "gemini-3.8-flash-high",
            "claude": "claude-sonnet-5",
            "codex": "gpt-6-astra",
            "deepseek": "deepseek-flash",
            "grok": "grok-4.7",
            "cursor": "grok-4.7-high",
            "kimi": "kimi-code/k3-256k",
        },
        default_mode="workspace-write",
        default_timeout_s=3600,
        description="prose/content drafting and expansion",
        codex_search=True,
    ),
    "review": TaskClassConfig(
        models={
            "agy": "gemini-3.8-flash-high",
            "claude": "claude-fable-5-1",
            "codex": "gpt-6-astra",
            "deepseek": "deepseek-flash",
            "grok": "grok-4.7",
            "cursor": "grok-4.7-high",
            "kimi": "kimi-code/k3-256k",
        },
        default_mode="read-only",
        default_timeout_s=1800,
        description="cross-family review of authored work (judgment)",
        codex_search=True,  # reviewers MUST be able to web-verify volatile facts (#1827)
    ),
    "architect": TaskClassConfig(
        models={
            "agy": "gemini-3.8-flash-high",
            "claude": "claude-fable-5-1",
            "codex": "gpt-6-astra",
            "deepseek": "deepseek-flash",
            "grok": "grok-4.7",
            "cursor": "grok-4.7-high",
            "kimi": "kimi-code/k3",
        },
        default_mode="workspace-write",
        default_timeout_s=3600,
        description="deep reasoning, multi-file refactors, design",
        codex_search=True,
    ),
}


def _resolve_skill_path(skill_name: str) -> Path | None:
    """Resolve a skill name to its SKILL.md path. Searches shared/ then claude/.

    Returns None if neither location has the skill.
    """
    for parent in (SHARED_SKILLS_DIR, CLAUDE_SKILLS_DIR):
        candidate = parent / skill_name / "SKILL.md"
        if candidate.is_file():
            return candidate
    return None


def _load_skill_body(skill_name: str) -> tuple[str, Path] | None:
    """Read a skill body. Returns (body_text, source_path) or None if missing."""
    path = _resolve_skill_path(skill_name)
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8"), path
    except OSError:
        return None


def _wrap_prompt_with_skill(prompt: str, skill_body: str, skill_name: str) -> str:
    """Prepend the skill body to the prompt with a clear marker."""
    return (
        f'<auto-loaded-skill name="{skill_name}">\n'
        f"{skill_body.rstrip()}\n"
        f"</auto-loaded-skill>\n\n"
        f"{prompt}"
    )


def _skill_to_load_for_dispatch(
    *,
    task_class: str,
    explicit_skill: str | None,
    no_skill: bool,
) -> str | None:
    """Return the explicit or task-class-mapped skill name, if enabled."""
    if explicit_skill is not None:
        return explicit_skill
    if no_skill:
        return None
    return SKILL_FOR_TASK_CLASS.get(task_class)


def _display_path(path: Path) -> Path:
    """Return a primary-relative path when possible, else the original path."""
    try:
        return path.relative_to(PRIMARY_REPO)
    except ValueError:
        return path


def make_task_id(task_class: str, agent: str) -> str:
    return f"smart-{agent}-{task_class}-{int(time.time())}"


# China-hosted AI providers that must NEVER be called from GH Actions / CI
# (.claude/rules + feedback_no_china_apis_from_gh_actions). The GLM coherence-audit
# lane (`--agent opencode --model zai-coding-plan/glm-5.2`, #2171) is LOCAL-ONLY.
# First-party DeepSeek (``--agent deepseek`` / ``deepseek-direct/*``) is also
# LOCAL-ONLY. NOTE: `openrouter/*` is a US-hosted proxy, so openrouter-routed
# qwen/deepseek model ids are intentionally NOT matched here — only DIRECT China
# endpoints / agent lanes are blocked.
_CI_BLOCKED_PROVIDER_MARKERS = (
    "zai-coding-plan",
    "z.ai",
    "zai/",
    "glm-",
    "bigmodel",
    "zhipu",
    "deepseek-direct",
)


def _running_in_ci() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
        or os.environ.get("CI", "").lower() in ("1", "true")
    )


def guard_no_china_provider_in_ci(agent: str, model: str) -> None:
    """Refuse to dispatch a China-hosted provider from a CI / GH Actions context.

    Defense-in-depth: no LLM dispatch runs in CI today (feedback_no_llm_review_in_ci),
    so this can never break a legitimate CI path — it only hard-blocks the local-only
    GLM/z.ai and first-party DeepSeek lanes if they are ever wired into an Actions
    workflow by mistake.
    """
    if not _running_in_ci():
        return
    # Bare --agent deepseek always hits api.deepseek.com via opencode.
    if agent == "deepseek":
        raise SystemExit(
            f"[smart] REFUSED: agent={agent!r} model={model!r} is first-party "
            f"DeepSeek (China-hosted, local-only) and must never be called from "
            f"GH Actions / CI (feedback_no_china_apis_from_gh_actions)."
        )
    haystack = f"{agent} {model}".lower()
    for marker in _CI_BLOCKED_PROVIDER_MARKERS:
        if marker in haystack:
            raise SystemExit(
                f"[smart] REFUSED: '{marker}' (agent={agent!r} model={model!r}) is a "
                f"China-hosted AI provider and must never be called from GH Actions / CI "
                f"(.claude/rules + feedback_no_china_apis_from_gh_actions). The GLM "
                f"coherence-audit / DeepSeek lanes are local-only."
            )


def _available_mcp_servers() -> list[str]:
    """Return sorted MCP server names from the repo-root ``.mcp.json``."""
    if not MCP_CONFIG_PATH.is_file():
        return []
    try:
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return []
    return sorted(servers.keys())


def _available_hermes_mcp_servers() -> list[str]:
    """Residual helper: Hermes MCP discovery is retired with --agent hermes.

    Returns ``[]`` always. Kept so older tests/call sites importing the name
    do not explode; new code must not rely on Hermes MCP.
    """
    return []


def _load_dispatch_str_constant(name: str) -> str:
    """Read a module-level string constant from ``scripts/dispatch.py`` without
    importing it (dispatch.py is a CLI with import-time side effects). The named
    constant must be a plain string literal (read via ast.literal_eval)."""
    dispatch_path = REPO / "scripts" / "dispatch.py"
    tree = ast.parse(dispatch_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                value = ast.literal_eval(node.value)
                if isinstance(value, str):
                    return value
                raise ValueError(f"{name} must be a string")
    raise ValueError(f"{name} not found in scripts/dispatch.py")


def _import_dispatch_mcp_constants(task_class: str) -> tuple[str, str]:
    """Return (mcp_config_path, allowed_tools) for a claude MCP dispatch.

    Authoring classes (draft/edit) get the write-capable
    ``CLAUDE_MCP_AUTHOR_TOOLS``; read classes (review/search) get the read-only
    ``CLAUDE_TRANSLATION_TOOLS``. Both are curated in scripts/dispatch.py (#2134).
    """
    constant = (
        "CLAUDE_MCP_AUTHOR_TOOLS"
        if task_class in CLAUDE_MCP_AUTHOR_TASK_CLASSES
        else "CLAUDE_TRANSLATION_TOOLS"
    )
    return str(MCP_CONFIG_PATH), _load_dispatch_str_constant(constant)


def _build_mcp_tool_config(agent: str, mcp_server: str, task_class: str) -> dict | None:
    """Build adapter ``tool_config`` for MCP tool access."""
    sys.path.insert(0, str(REPO / "scripts"))
    from agent_runtime.tool_config import build_mcp_tool_config

    if agent == "claude":
        mcp_config_path, allowed_tools = _import_dispatch_mcp_constants(task_class)
        tool_config, _diagnostics = build_mcp_tool_config(
            agent,
            mcp_servers=[mcp_server],
            allowed_tools=allowed_tools,
            mcp_config_path=Path(mcp_config_path),
        )
        return tool_config

    tool_config, _diagnostics = build_mcp_tool_config(
        agent,
        mcp_servers=[mcp_server],
        mcp_config_path=MCP_CONFIG_PATH,
    )
    return tool_config


def _allowed_tools_count(allowed_tools: str) -> int:
    return len([tool for tool in allowed_tools.split(",") if tool.strip()])


def _dry_run_runtime_argv(
    *,
    agent: str,
    prompt: str,
    mode: str,
    model: str,
    worktree: Path | None,
    task_id: str,
    tool_config: dict | None,
) -> list[str]:
    """Resolve the runtime adapter argv for dry-run verification."""
    sys.path.insert(0, str(REPO / "scripts"))
    from agent_runtime.delegate_config import merge_delegate_claude_tool_config
    from agent_runtime.runner import _load_adapter

    adapter = _load_adapter(agent)
    effective_tool_config = merge_delegate_claude_tool_config(
        agent,
        "delegate",
        tool_config,
    )
    plan = adapter.build_invocation(
        prompt=prompt,
        mode=mode,
        cwd=worktree or Path.cwd(),
        model=model,
        task_id=task_id,
        session_id=None,
        tool_config=effective_tool_config,
    )
    return plan.cmd


def _print_dry_run_mcp(agent: str, tool_config: dict) -> None:
    """Print resolved MCP wiring for ``--dry-run`` verification."""
    if agent == "claude":
        mcp_config_path = tool_config.get("mcp_config_path")
        allowed_tools = tool_config.get("allowed_tools") or ""
        count = _allowed_tools_count(allowed_tools)
        print(
            f"[dry-run] mcp_config={mcp_config_path} "
            f"allowed_tools_count={count}"
        )
        if mcp_config_path and allowed_tools:
            print(
                f"[dry-run] mcp_flags=--mcp-config {mcp_config_path} "
                f"--allowedTools <{count} tools>"
            )
        return

    if agent in HERMES_MCP_AGENTS:
        servers = tool_config.get("hermes_mcp_servers") or []
        print(f"[dry-run] hermes_mcp_servers={servers}")
        print(
            "[dry-run] hermes_config=~/.hermes/config.yaml "
            "(MCP servers discovered natively by Hermes)"
        )


def ensure_worktree(worktree: Path, new_branch: str | None, base: str = "main") -> None:
    """Create a worktree if it doesn't exist; reuse if it does.

    Caller is responsible for picking a sensible path under .worktrees/.
    """
    if worktree.exists():
        return
    if new_branch is None:
        raise SystemExit(
            f"[smart] worktree {worktree} does not exist and no "
            f"--new-branch was given; refusing to invent a branch name"
        )
    cmd = ["git", "worktree", "add", "-b", new_branch, str(worktree), base]
    subprocess.run(cmd, cwd=PRIMARY_REPO, check=True)
    primary_venv = PRIMARY_REPO / ".venv"
    worktree_venv = worktree / ".venv"
    if primary_venv.exists() and not (
        worktree_venv.exists() or worktree_venv.is_symlink()
    ):
        worktree_venv.symlink_to(primary_venv)
    primary_node_modules = PRIMARY_REPO / "node_modules"
    worktree_node_modules = worktree / "node_modules"
    if primary_node_modules.exists() and not (
        worktree_node_modules.exists() or worktree_node_modules.is_symlink()
    ):
        worktree_node_modules.symlink_to(primary_node_modules)


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as fp:
        fp.write(json.dumps(entry) + "\n")


def persist_response(task_id: str, response: str, stderr_excerpt: str) -> Path:
    """Write the full response body (and stderr excerpt) to disk.

    Returns the path of the response file. Callers that pipe dispatch output
    through ``tail`` or similar truncation can still recover the full body
    from this file. Prior to this, only ``response_chars`` was captured in
    the JSONL row and the body lived solely in stdout, which got silently
    dropped on ~3 of session-31's review dispatches.
    """
    RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
    response_path = RESPONSE_DIR / f"{task_id}.txt"
    response_path.write_text(response or "", encoding="utf-8")
    if stderr_excerpt:
        stderr_path = RESPONSE_DIR / f"{task_id}.stderr.txt"
        stderr_path.write_text(stderr_excerpt, encoding="utf-8")
    return response_path


def _opencode_binary() -> str:
    """Resolve the opencode CLI path with an env override for local installs."""
    return (
        os.environ.get("KUBEDOJO_OPENCODE_CMD")
        or shutil.which("opencode")
        or "/opt/homebrew/bin/opencode"
    )


def _parse_opencode_json_events(stdout: str) -> str:
    """Extract the final assistant message from opencode ``--format json`` NDJSON.

  Empirical schema (opencode run --format json, one JSON object per line):

  - ``step_start``: agent turn begins; ``part.messageID`` identifies the turn.
  - ``tool_use``: tool invocation; ignore for response capture.
  - ``text``: assistant output chunk; final text is in ``part.text``.
  - ``step_finish``: turn ends; ``part.reason`` is ``stop`` (final reply) or
    ``tool-calls`` (intermediate turn).

  Concatenate all ``text`` chunks for the message whose ``step_finish`` has
  ``reason=stop``. Fall back to the last message that emitted text.
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
            text = part.get("text")
            if not isinstance(text, str) or not text:
                continue
            message_id = part.get("messageID")
            if not isinstance(message_id, str):
                message_id = ""
            if message_id not in texts_by_message:
                message_order.append(message_id)
            texts_by_message.setdefault(message_id, []).append(text)
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


def _hermes_binary() -> str:
    """Resolve the hermes CLI path with an env override for local installs."""
    return (
        os.environ.get("KUBEDOJO_HERMES_CMD")
        or shutil.which("hermes")
        or str(Path.home() / ".local" / "bin" / "hermes")
    )


def _cursor_binary() -> str:
    """Resolve the cursor-agent CLI path with an env override for local installs."""
    return (
        os.environ.get("KUBEDOJO_CURSOR_CMD")
        or shutil.which("cursor-agent")
        or str(Path.home() / ".local" / "bin" / "cursor-agent")
    )


def _grok_binary() -> str:
    """Resolve the grok CLI path with an env override for local installs."""
    return (
        os.environ.get("KUBEDOJO_GROK_CMD")
        or shutil.which("grok")
        or str(Path.home() / ".local" / "bin" / "grok")
    )


def _hermes_provider_for_model(model: str) -> str:
    """Pick a Hermes provider from the model name, unless env overrides it.

    NO silent metered fallback: the old catch-all returned ``openrouter``,
    which billed the OpenRouter account for any model without an explicit
    branch — ``deepseek-v4-*`` had no branch, so deepseek-via-hermes
    dispatches silently drained OpenRouter instead of hitting the first-party
    DeepSeek API (incident #2245, 2026-07-07). Unknown models now raise.
    """
    override = os.environ.get("KUBEDOJO_HERMES_PROVIDER")
    if override:
        return override
    if model.startswith("openrouter/"):
        return "openrouter"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("grok-"):
        # xAI is accessed via the OAuth subscription (`hermes login --provider
        # xai-oauth`), NOT the metered XAI_API_KEY "xai" provider. Override with
        # KUBEDOJO_HERMES_PROVIDER=xai if you have an API key instead.
        return "xai-oauth"
    if model.startswith("deepseek"):
        # First-party DeepSeek API (api.deepseek.com) — NEVER the OpenRouter
        # proxy unless the caller opts in explicitly (#2245).
        return "deepseek"
    if model.startswith("qwen"):
        # The documented metered qwen lane rides OpenRouter deliberately
        # ([[reference_qwen_hermes_openrouter]]) — an explicit branch, not a
        # fallback.
        return "openrouter"
    raise ValueError(
        f"No Hermes provider mapping for model {model!r} — refusing to fall "
        "back to a metered proxy (incident #2245). Set "
        "KUBEDOJO_HERMES_PROVIDER or use an explicit 'openrouter/<vendor>/"
        "<model>' slug."
    )


def _hermes_cli_model(model: str) -> str:
    """Map KubeDojo's route labels to Hermes v0.14 CLI model IDs."""
    if model.startswith("openrouter/"):
        # The ``openrouter/`` prefix is only the explicit provider opt-in
        # marker (#2245); OpenRouter's own catalog ids are ``vendor/model``.
        return model.removeprefix("openrouter/")
    if model.startswith("qwen-"):
        return f"qwen/qwen{model.removeprefix('qwen-')}"
    return model


def _router_command(
    agent: str,
    model: str,
    prompt: str,
    *,
    grok_effort: str | None = None,
) -> list[str]:
    """Build the subprocess command for direct router CLIs."""
    if agent == "opencode":
        # ``--format json`` emits NDJSON events instead of ANSI TUI output.
        # Reasoning effort can be overridden via opencode's ``--variant`` flag
        # (e.g. high, max, minimal); plumb with dispatch_smart ``--variant``
        # or ``KUBEDOJO_OPENCODE_VARIANT`` when we need per-task effort control.
        cmd = [_opencode_binary(), "run", "--format", "json"]
        variant = os.environ.get("KUBEDOJO_OPENCODE_VARIANT", "").strip()
        if variant:
            cmd.extend(["--variant", variant])
        cmd.extend(["-m", model, "-"])
        return cmd
    if agent == "cursor":
        return [
            _cursor_binary(),
            "--print",
            "--force",
            "--trust",
            "--model",
            model,
            "--output-format",
            "text",
            prompt,
        ]
    if agent == "grok":
        cmd = [_grok_binary(), "-p", prompt, "-m", model, "--output-format", "plain"]
        if grok_effort:
            cmd.extend(["--reasoning-effort", grok_effort])
        return cmd
    if agent == "hermes":
        raise ValueError(HERMES_RETIRED_MESSAGE)
    raise ValueError(f"unsupported direct router agent: {agent}")


def _router_subprocess_env(agent: str) -> dict[str, str]:
    """Return env overrides for direct router CLIs."""
    env = os.environ.copy()
    if agent == "opencode":
        # Prevent git tool calls from paging or blocking on credentials.
        env.setdefault("GIT_PAGER", "cat")
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env


def _run_router_agent(
    *,
    agent: str,
    prompt: str,
    model: str,
    cwd: Path,
    timeout_s: int,
    grok_effort: str | None = None,
) -> tuple[bool, str, str]:
    """Invoke a session-less router CLI and return (ok, stdout, stderr)."""
    cmd = _router_command(agent, model, prompt, grok_effort=grok_effort)
    stdin_payload = prompt if agent == "opencode" else ""
    if agent == "cursor":
        stdin_payload = ""
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_payload,
            cwd=cwd,
            env=_router_subprocess_env(agent),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return False, stdout, f"{agent} timed out after {timeout_s}s\n{stderr}".strip()
    except OSError as exc:
        return False, "", f"{type(exc).__name__}: {exc}"

    raw_stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if agent == "opencode":
        response = _parse_opencode_json_events(raw_stdout)
    else:
        response = raw_stdout.strip()
    ok = proc.returncode == 0 and bool(response.strip())
    if not ok and not stderr.strip():
        stderr = f"{agent} exited {proc.returncode} with no stdout"
    return ok, response.strip(), stderr.strip()


def fire(
    *,
    agent: str,
    task_class: str,
    prompt: str,
    mode: str,
    model: str,
    worktree: Path | None,
    task_id: str,
    timeout_s: int,
    tool_config: dict | None = None,
) -> int:
    print(
        f"[smart] agent={agent} task_class={task_class} model={model} "
        f"mode={mode} timeout={timeout_s}s"
    )
    if worktree:
        print(f"[smart] cwd={worktree}")
    print(f"[smart] task_id={task_id}")
    if agent in {"cursor", "opencode", "grok"}:
        print("[smart] mode is advisory for this router CLI")

    started = time.time()
    previous_search: str | None = None
    previous_dispatched: str | None = None
    try:
        previous_search = os.environ.get("KUBEDOJO_CODEX_SEARCH")
        previous_dispatched = os.environ.get("KUBEDOJO_DISPATCHED")
        if agent == "codex":
            cfg = TASK_CLASSES[task_class]
            os.environ["KUBEDOJO_CODEX_SEARCH"] = "1" if cfg.codex_search else "0"
        env = os.environ.copy()
        env["KUBEDOJO_DISPATCHED"] = "1"
        os.environ.update(env)
        if agent in {"cursor", "opencode", "grok"}:
            ok, response, stderr_excerpt = _run_router_agent(
                agent=agent,
                prompt=prompt,
                model=model,
                cwd=worktree or Path.cwd(),
                timeout_s=timeout_s,
                grok_effort=TASK_CLASSES[task_class].grok_reasoning_effort,
            )
            session_id = None
        else:
            sys.path.insert(0, str(REPO / "scripts"))
            from agent_runtime.errors import (
                AgentStalledError,
                AgentTimeoutError,
                AgentUnavailableError,
                RateLimitedError,
            )
            from agent_runtime.runner import invoke

            max_retries = 3 if agent in {"agy", "kimi"} else 1
            base_delay = 10
            
            for attempt in range(max_retries):
                try:
                    result = invoke(
                        agent,
                        prompt,
                        mode=mode,
                        cwd=worktree,
                        model=model,
                        task_id=task_id,
                        tool_config=tool_config,
                        entrypoint="delegate",
                        hard_timeout=timeout_s,
                    )
                    ok = bool(result.ok)
                    response = result.response or ""
                    session_id = result.session_id
                    stderr_excerpt = result.stderr_excerpt or ""
                    
                    if ok:
                        break
                        
                    if attempt < max_retries - 1:
                        err_text = stderr_excerpt or "no final message"
                        print(f"⚠️  {agent} failed ({err_text}), retrying {attempt+1}/{max_retries}...")
                        time.sleep(base_delay * (2 ** attempt))
                        continue
                        
                except (RateLimitedError, AgentStalledError, AgentTimeoutError, AgentUnavailableError) as exc:
                    if attempt < max_retries - 1:
                        print(f"⚠️  {agent} error ({exc}), retrying {attempt+1}/{max_retries}...")
                        time.sleep(base_delay * (2 ** attempt))
                        continue
                    ok = False
                    response = ""
                    session_id = None
                    stderr_excerpt = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # surface the failure but still log it
        ok = False
        response = ""
        session_id = None
        stderr_excerpt = f"{type(exc).__name__}: {exc}"
    finally:
        if agent == "codex":
            if previous_search is None:
                os.environ.pop("KUBEDOJO_CODEX_SEARCH", None)
            else:
                os.environ["KUBEDOJO_CODEX_SEARCH"] = previous_search
        if previous_dispatched is None:
            os.environ.pop("KUBEDOJO_DISPATCHED", None)
        else:
            os.environ["KUBEDOJO_DISPATCHED"] = previous_dispatched

    elapsed = time.time() - started
    response_path = persist_response(task_id, response, stderr_excerpt)
    rel_response_path = str(response_path.relative_to(PRIMARY_REPO))
    append_log(
        {
            "ts": int(started),
            "elapsed_s": round(elapsed, 1),
            "task_id": task_id,
            "agent": agent,
            "task_class": task_class,
            "model": model,
            "mode": mode,
            "cwd": str(worktree) if worktree else None,
            "ok": ok,
            "session_id": session_id,
            "response_chars": len(response),
            "response_path": rel_response_path,
            "stderr_excerpt": stderr_excerpt[:400] if stderr_excerpt else None,
        }
    )

    # Print response_path BEFORE the body so callers that truncate stdout
    # (tail -N, head -N) still see the path and can `cat` the full file.
    print("=" * 70)
    print(f"OK: {ok}  |  elapsed: {elapsed:.0f}s  |  resp_chars: {len(response)}")
    print(f"response_path: {rel_response_path}")
    print("=" * 70)
    if response:
        print(response)
    if stderr_excerpt:
        print("---- stderr ----")
        print(stderr_excerpt[:400])
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description="Dispatch a headless agent with a "
        "task-class-based model choice. Mirrors the AGENTS.md "
        "economical multi-agent policy across agents.",
    )
    p.add_argument(
        "task_class",
        choices=sorted(TASK_CLASSES),
        help="Picks the model + default mode.",
    )
    p.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Prompt text. Pass `-` to read from stdin.",
    )
    p.add_argument(
        "--agent",
        choices=SUPPORTED_AGENTS,
        default="claude",
        help="Which agent to dispatch (default: claude).",
    )
    p.add_argument(
        "--worktree",
        help="Path to a git worktree under .worktrees/. Required for write modes.",
    )
    p.add_argument(
        "--new-branch",
        help="If --worktree doesn't exist, create it on this branch off main.",
    )
    p.add_argument(
        "--mode",
        choices=["read-only", "workspace-write", "danger"],
        help="Override task-class default mode. For opencode, "
        "grok, and cursor this is advisory; their CLIs "
        "enforce their own sandbox behavior.",
    )
    p.add_argument(
        "--model",
        help="Override task-class default model "
        "(rarely needed — let the class+agent pick).",
    )
    p.add_argument(
        "--timeout", type=int, help="Override task-class default hard timeout (s)."
    )
    p.add_argument("--task-id", help="Override auto-generated task_id.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved plan and exit without firing.",
    )
    p.add_argument(
        "--skill",
        default=None,
        help=(
            "Override the auto-mapped skill for the task class. Looks up "
            "agents_extensions/shared/skills/<name>/SKILL.md first, then "
            "agents_extensions/claude/skills/<name>/SKILL.md. Fails if not found."
        ),
    )
    p.add_argument(
        "--no-skill",
        action="store_true",
        help="Disable skill auto-loading entirely.",
    )
    p.add_argument(
        "--mcp",
        metavar="SERVER",
        default=None,
        help=(
            "Enable a named MCP server for this dispatch "
            "(e.g. --mcp sources for Ukrainian corpus verification). "
            "Claude: review/search/draft/edit task classes. "
            "agy loads MCP natively. Hermes MCP is retired."
        ),
    )
    args = p.parse_args()

    if args.agent == "hermes":
        raise SystemExit(HERMES_RETIRED_MESSAGE)
    if args.agent in {"opencode", "qwen"}:
        raise SystemExit(OPENCODE_QWEN_RETIRED_MESSAGE)

    cfg = TASK_CLASSES[args.task_class]
    model = args.model or cfg.models[args.agent]
    guard_no_china_provider_in_ci(args.agent, model)  # #2171: GLM/z.ai / DeepSeek local-only
    mode = args.mode or cfg.default_mode
    timeout_s = args.timeout or cfg.default_timeout_s
    task_id = args.task_id or make_task_id(args.task_class, args.agent)

    if args.mcp is not None:
        if args.agent == "claude":
            if args.task_class not in CLAUDE_MCP_TASK_CLASSES:
                p.error(
                    f"--mcp on claude is supported for "
                    f"{', '.join(sorted(CLAUDE_MCP_TASK_CLASSES))} task classes "
                    f"(review/search use the read-only sources allowlist; "
                    f"draft/edit use the write-capable author allowlist, #2134); "
                    f"got task_class={args.task_class!r}."
                )
        elif args.agent in HERMES_MCP_AGENTS:
            if args.task_class not in HERMES_MCP_TASK_CLASSES:
                p.error(
                    f"--mcp for Hermes lanes is only supported for write task "
                    f"classes ({', '.join(sorted(HERMES_MCP_TASK_CLASSES))}); "
                    f"got agent={args.agent!r} task_class={args.task_class!r}"
                )
        elif args.agent not in MCP_SUPPORTED_AGENTS:
            p.error(
                f"--mcp tool access is only supported for agents "
                f"{', '.join(sorted(MCP_SUPPORTED_AGENTS))} "
                f"(got agent={args.agent!r}); agy loads MCP natively, no flag needed"
            )
        available = (
            _available_hermes_mcp_servers()
            if args.agent in HERMES_MCP_AGENTS
            else _available_mcp_servers()
        )
        if args.mcp not in available:
            source = (
                "~/.hermes/config.yaml"
                if args.agent in HERMES_MCP_AGENTS
                else ".mcp.json"
            )
            p.error(
                f"unknown MCP server {args.mcp!r} for agent {args.agent!r}; "
                f"available in {source}: {', '.join(available) or '(none)'}"
            )

    tool_config = (
        _build_mcp_tool_config(args.agent, args.mcp, args.task_class)
        if args.mcp
        else None
    )

    # Codex always runs in danger mode — read-only starves it of
    # network/filesystem and produces garbage (rc=-9 stale-rollout salvage).
    if args.agent == "codex" and mode != "danger":
        if args.mode is not None and args.mode != "danger":
            p.error(
                f"--agent codex always runs in danger mode (you passed "
                f"--mode {args.mode!r}). Codex needs network + filesystem "
                f"to fact-check; read-only/workspace-write break it. "
                f"Drop --mode to use the default."
            )
        mode = "danger"

    # Agy always runs in danger mode for write classes — read-only would cause
    # tool-permission prompts to hang waiting for human input in a headless
    # dispatch, since the runtime cannot answer the prompt.
    # `--dangerously-skip-permissions` is the equivalent of codex's danger
    # sandbox: auto-approve all tool calls. User direction 2026-05-19.
    if (
        args.agent == "agy"
        and args.task_class not in ("review", "search")
        and mode != "danger"
    ):
        if args.mode is not None and args.mode != "danger":
            p.error(
                f"--agent agy always runs in danger mode (you passed "
                f"--mode {args.mode!r}). agy in headless dispatch needs "
                f"--dangerously-skip-permissions to avoid hanging on "
                f"interactive permission prompts. Drop --mode to use the default."
            )
        mode = "danger"

    # Read-only task classes for codex run in danger mode, but they do not
    # require a worktree.
    codex_readonly_class = args.agent == "codex" and args.task_class in {
        "review",
        "search",
    }

    if args.prompt is None:
        sys.stderr.write("[smart] no prompt — pass as arg or `-` for stdin\n")
        return 2
    prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
    if not prompt.strip():
        sys.stderr.write("[smart] prompt is empty\n")
        return 2

    skill_to_load = _skill_to_load_for_dispatch(
        task_class=args.task_class,
        explicit_skill=args.skill,
        no_skill=args.no_skill,
    )
    if skill_to_load is not None:
        loaded = _load_skill_body(skill_to_load)
        if loaded is None:
            if args.skill is not None:
                print(
                    f"[dispatch_smart] error: skill '{skill_to_load}' not found in "
                    "agents_extensions/shared/skills/ or "
                    "agents_extensions/claude/skills/",
                    file=sys.stderr,
                )
                return 2
            print(
                f"[dispatch_smart] warning: auto-mapped skill '{skill_to_load}' "
                "not found; proceeding without skill context",
                file=sys.stderr,
            )
        else:
            skill_body, source_path = loaded
            prompt = _wrap_prompt_with_skill(prompt, skill_body, skill_to_load)
            rel = _display_path(source_path)
            print(
                f"[dispatch_smart] auto-loaded skill: {skill_to_load} (from {rel})",
                file=sys.stderr,
            )

    if mode == "danger" and not args.worktree and not args.dry_run:
        # agy carve-out: agy under danger mode only suppresses interactive
        # permission prompts (--dangerously-skip-permissions); it does not
        # write files. Review-class agy dispatches don't need a worktree.
        # codex review/search carve-out: read-only task classes; no worktree.
        if args.agent != "agy" and not codex_readonly_class:
            p.error("--mode danger requires --worktree (no override)")

    worktree: Path | None = None
    if args.worktree:
        worktree = Path(args.worktree)
        if not worktree.is_absolute():
            worktree = PRIMARY_REPO / worktree
    elif (
        mode != "read-only"
        and not args.dry_run
        and args.agent != "agy"
        and not codex_readonly_class
    ):
        sys.stderr.write(
            f"[smart] mode={mode} requires --worktree to avoid trampling "
            "the main checkout\n"
        )
        return 2

    if args.dry_run:
        print(
            f"[dry-run] agent={args.agent} task_class={args.task_class} "
            f"model={model} mode={mode} timeout={timeout_s}s"
        )
        _wt_label = worktree or f"(none — {mode})"
        print(f"[dry-run] worktree={_wt_label}")
        print(f"[dry-run] task_id={task_id}")
        if tool_config:
            _print_dry_run_mcp(args.agent, tool_config)
        print(f"[dry-run] prompt_chars={len(prompt)}")
        print("[dry-run] prompt_begin")
        print(prompt)
        print("[dry-run] prompt_end")
        if args.agent in {"cursor", "opencode", "grok"}:
            print(f"[dry-run] argv={_router_command(args.agent, model, prompt)!r}")
        elif tool_config and args.agent in MCP_SUPPORTED_AGENTS:
            print(
                f"[dry-run] argv="
                f"{_dry_run_runtime_argv(agent=args.agent, prompt=prompt, mode=mode, model=model, worktree=worktree, task_id=task_id, tool_config=tool_config)!r}"
            )
        return 0

    if worktree and mode != "read-only":
        ensure_worktree(worktree, args.new_branch)

    return fire(
        agent=args.agent,
        task_class=args.task_class,
        prompt=prompt,
        mode=mode,
        model=model,
        worktree=worktree,
        task_id=task_id,
        timeout_s=timeout_s,
        tool_config=tool_config,
    )


if __name__ == "__main__":
    raise SystemExit(main())
