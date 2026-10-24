"""Agent runtime — universal adapter + runner for Claude, Gemini, Codex, and future agents.

ARCHITECTURAL OVERVIEW (read this first):

    caller (bridge / dispatch / delegate / consult)
        │
        ▼
    runner.invoke(agent_name, prompt, *, mode, cwd, ...) → Result
        │  1. Look up adapter in registry
        │  2. Validate mode, cwd, has_headroom
        │  3. Ask adapter to build InvocationPlan
        │  4. Spawn subprocess via Popen + watchdog
        │  5. Stall detection (stdout streamer + liveness file mtime)
        │  6. Ask adapter to parse response → ParseResult
        │  7. Write usage record atomically to batch_state/api_usage/
        │  8. Return Result
        │
        ├── adapters/codex.py     → wraps `codex exec`
        ├── adapters/claude.py    → wraps `npx @anthropic-ai/claude-code -p`
        ├── adapters/gemini.py    → wraps `gemini -m ... -y`
        └── adapters/qwen.py      — Hermes + openrouter adapter

DESIGN PRINCIPLES:

- Single source of truth for subprocess logic. Adapters describe the CLI,
  runner handles execution. No duplicated Popen loops across the codebase.
- Stall detection is universal. `_gemini.py` had a `_stream_with_watchdog`
  prior art; this runtime lifts it into a shared layer so every agent
  benefits from "kill only on genuine inactivity, not naive wall-clock."
- Usage tracking is universal. Every invocation writes one JSONL record
  to batch_state/api_usage/ so the existing /api/batch/usage endpoint
  surfaces per-agent + per-entrypoint cost data automatically.
- Resume policy is data-driven. See docs/design/agent-runtime.md § 6.3.
  Claude/Gemini bridge paths keep resume for cache warmth (cost economics);
  Codex bridge paths may resume with matching cwd/mode; delegate/dispatch
  always fresh (worktree is the isolation boundary).

HOW TO ADD A NEW AGENT:

1. Create scripts/agent_runtime/adapters/myagent.py. Copy _template.py as a
   starting point. Implement the three AgentAdapter protocol methods:
   build_invocation, parse_response, liveness_signal_paths.
2. Add an entry to registry.AGENTS with default_model, supported_modes,
   capabilities, and resume_policy.
3. Write adapter unit tests (flag building, parse_response for ok/rate-limit/
   error cases, liveness path detection).
4. Run `.venv/bin/python -m pytest tests/test_agent_runtime.py` — the existing
   runner tests should work for any conforming adapter.

See docs/agent-runtime-guide.md for the full mental model + common mistakes.

Issue: #1184
"""
from __future__ import annotations
