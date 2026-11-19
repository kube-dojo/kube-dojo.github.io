# Headroom — Shared Compression + Memory Layer

Convention for using Headroom, the shared compression and memory layer for local
agents. Ported from learn-ukrainian (#3534, 2026-06-18) — KubeDojo imports rather
than reinvents. Tracking issue: #2024.

> **STATUS 2026-07-07: PROXY ROUTING DISABLED (user, s181, 2026-06-24).** Pre-upstream
> compression tripped the 30s stream-idle timeout on large model outputs and made large
> Reads silently lossy (`feedback_never_translate_from_compressed_read`).
> `start-claude.sh` launches Claude DIRECT and force-unsets the routing env, and the
> `headroom` MCP entry is currently absent from `.mcp.json` — so `headroom_compress` /
> `headroom_retrieve` are unavailable in sessions. The sections below describe the
> re-enable TARGET state. Re-enable only when the buffered-read-timeout fix ships
> (memory: `feedback_headroom_disabled_reenable_when_readtimeout_fix_ships`; restore the
> routing-guard block from git history per the comments in `start-claude.sh`).

## Runtime (re-enable target state)

- Proxy health: `http://127.0.0.1:8787/health` · Stats: `http://127.0.0.1:8787/stats`
- MCP server name: `headroom` (stdio via `headroom mcp serve`); tools: `headroom_compress`, `headroom_retrieve`, `headroom_stats`.
- Start: `headroom install start --profile default`.
- HISTORICAL (routing era, ≤s181): `start-claude.sh` loaded the routing env and ensured the proxy via the "headroom routing guard" block; the session **and every `dispatch_smart` agent** routed through `127.0.0.1:8787` (≈22% token savings observed, s164). It now force-unsets `ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` and launches DIRECT.

## Usage rule — compress big context (INOPERATIVE while routing is disabled)

Once re-enabled: if content is roughly over **200 lines or 20 KB**, call `headroom_compress` FIRST,
reason over the returned **hash + a one-line summary**, and `headroom_retrieve`
only the exact detail you need. This is the single biggest context-saver on a long
orchestration session — **default to it instead of letting big outputs truncate.**
Targets:

- `npm run build` output (pipe to file anyway per [[feedback_never_read_build_logs]], then compress if you must reason over it)
- codex / cursor / deepseek review verdicts and dispatch responses
- search / grep result bundles, validation output, large diffs

Do **not** treat Headroom memory as factual authority for curriculum content —
retrieve the original or inspect the repo/source when exact claims matter (same as
the anti-fabrication conventions). Never run `headroom learn --apply` unless the
user explicitly asks — it can rewrite `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`.

## Handoffs — on-disk files stay SSOT

KubeDojo session handoffs (lean MD briefs at
`.agent/session-state/YYYY-MM-DD-session-NN-<topic>.md`, indexed in the live
`.agent/STATUS.md`, parsed by the briefing API at cold-start) **remain the durable
cross-session source of truth — as ON-DISK files.** (s196 convention: handoffs are
gitignored local agent state, never through git/PRs — user directives s190b + s196;
`docs/session-state/` holds only the tracked pre-s196 history.) The proxy's memory store is local-only with no MCP
write tool yet (`native_tool`/`bridge` off) — it auto-injects context but cannot
carry the handoff across sessions. So keep the on-disk files as the backstop and push bulky
evidence behind Headroom hashes rather than pasting it. **Migrate the handoff body
to Headroom (and cut git to a thin pointer) only once the durable memory-write tool
lands** — tracked in #2024. Do not drop the git handoff before the cold-start
read-path is proven across sessions, or every future cold-start goes blind.

## Git-tracked source of truth

- `.mcp.json` — the repo-level `headroom` stdio entry is currently REMOVED (disabled era); restore on re-enable (portable; don't rely on user-level `~/.claude.json`).
- `.claude/rules/headroom.md` — this rule.
- the `## Headroom` section in `agents_extensions/claude/skills/curriculum-orchestrator/SKILL.md` (deployed to `.claude/skills/` via `agents_extensions/deploy.sh`).
- `start-claude.sh` "headroom routing: DISABLED" block (re-enable instructions live in its comments).

Machine-local runtime dirs (`.claude/` runtime state, `.codex/`, `.gemini/`) are not the source of truth.
