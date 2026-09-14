"""Agent registry — catalog of all agents known to the runtime.

Each entry describes how to reach an agent's adapter, its default model, cost
tier (for budgeting), capability tags (informational only; benchmark harness
will populate real scores later), and its resume_policy.

Resume policy is data-driven (see docs/design/agent-runtime.md § 6.3):

- ``bridge_only`` — Session resume allowed ONLY when caller is the bridge
  (multi-turn task_id messaging). Forbidden for delegate/dispatch. Claude
  and Gemini use this policy because their providers charge per cache-read
  token; dropping resume would reproduce the March 20-21 cost fiasco.
- ``never`` — No resume ever. Codex uses this because (a) its quota is
  per-message so resume saves nothing, and (b) session-across-worktree
  contamination is the #1 footgun flagged in Codex's own consultation.
- The runner does NOT enforce resume policy — callers do. The policy is
  stored here for documentation and for delegate.py's assertion layer.

Issue: #1184
"""
from __future__ import annotations

import os
from typing import TypedDict

try:
    from dispatch import GEMINI_WRITER_MODEL
except ImportError:  # pragma: no cover - package import path variant
    GEMINI_WRITER_MODEL = os.environ.get("KUBEDOJO_WRITER_MODEL", "gemini-3.1-pro-preview")


class AgentEntry(TypedDict):
    """Registry row shape."""

    adapter: str               # fully-qualified "module:ClassName" import path
    default_model: str | None
    cost_tier: str             # "low" | "medium" | "high" | "unknown"
    capabilities: frozenset[str]
    cli_available: bool
    resume_policy: str         # "bridge_only" | "never"


AGENTS: dict[str, AgentEntry] = {
    "agy": {
        "adapter": "scripts.agent_runtime.adapters.agy:AgyAdapter",
        "default_model": os.environ.get("KUBEDOJO_AGY_MODEL", "gemini-3.5-flash-high"),
        "cost_tier": "low",
        "capabilities": frozenset({
            "content_writing",
            "content_review",
            "adversarial_review",
        }),
        "cli_available": True,
        "resume_policy": "bridge_only",
    },
    "codex": {
        "adapter": "scripts.agent_runtime.adapters.codex:CodexAdapter",
        "default_model": os.environ.get("AB_CODEX_MODEL", "gpt-5.5"),
        "cost_tier": "medium",
        "capabilities": frozenset({
            "code_writing",
            "code_review",
            "debugging",
            "adversarial_review",
        }),
        "cli_available": True,
        "resume_policy": "bridge_only",
    },
    "claude": {
        "adapter": "scripts.agent_runtime.adapters.claude:ClaudeAdapter",
        "default_model": os.environ.get("AB_CLAUDE_MODEL", "claude-opus-4-8"),
        "cost_tier": "high",
        "capabilities": frozenset({
            "architecture",
            "review",
            "content_a1",
            "planning",
        }),
        "cli_available": True,
        "resume_policy": "bridge_only",
    },
    "deepseek": {
        "adapter": "scripts.agent_runtime.adapters.deepseek:DeepSeekAdapter",
        "default_model": os.environ.get("AB_DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "cost_tier": "low",
        "capabilities": frozenset({
            "code_review",
            "content_review",
            "adversarial_review",
            "research",
            "deliberation",
            "architecture",
        }),
        "cli_available": True,
        "resume_policy": "never",
    },
    "gemini": {
        "adapter": "scripts.agent_runtime.adapters.gemini:GeminiAdapter",
        # Decoupled from GEMINI_WRITER_MODEL (which is now the agy slug
        # gemini-3.1-pro-high, #2125): the GeminiAdapter invokes the retired
        # gemini-cli, so its default must stay a gemini-cli model id, not an agy
        # display slug. This whole entry is dead residual pending removal (#2125
        # follow-up) — gemini-cli has no binary — but keep it internally coherent.
        "default_model": "gemini-3.1-pro-preview",
        "cost_tier": "low",
        "capabilities": frozenset({
            "content_writing",
            "content_review",
            "adversarial_review",
        }),
        "cli_available": True,
        "resume_policy": "bridge_only",
    },
    "qwen": {
        "adapter": "scripts.agent_runtime.adapters.qwen:QwenAdapter",
        "default_model": os.environ.get("AB_QWEN_MODEL", "qwen/qwen3.6-plus"),
        "cost_tier": "medium",
        "capabilities": frozenset({
            "code_review",
            "content_review",
            "adversarial_review",
            "debugging",
            "deliberation",
            "research",
        }),
        "cli_available": True,
        "resume_policy": "never",
    },
    "kimi": {
        "adapter": "scripts.agent_runtime.adapters.kimi:KimiAdapter",
        # Prefer k3-256k for normal EN work; use kimi-code/k3 (1M) only when needed.
        "default_model": os.environ.get("KUBEDOJO_KIMI_MODEL", "kimi-code/k3-256k"),
        "cost_tier": "medium",
        "capabilities": frozenset({
            "content_writing",
            "content_review",
            "code_writing",
            "adversarial_review",
        }),
        "cli_available": True,
        "resume_policy": "never",
    },
}


def get_agent_entry(name: str) -> AgentEntry:
    """Look up an agent entry by name.

    Raises:
        KeyError: If ``name`` is not in AGENTS. Runner catches this and
            converts to AgentUnavailableError with a friendlier message.
    """
    return AGENTS[name]


def available_agents() -> list[str]:
    """Return names of agents whose cli_available is True.

    Used by consult.py (future) and introspection / debugging. Does not
    check whether the CLI is actually installed on PATH — that's the
    adapter's responsibility at invocation time.
    """
    return [name for name, entry in AGENTS.items() if entry["cli_available"]]
