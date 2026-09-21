---
name: dispatch-router
description: Pick the right KubeDojo agent for a task across ALL activities — write / code / review / research / mechanical, not just review. Activity × lane matrix → agent → model → dispatch command. LIVE roster probed 2026-09-21 (agy gemini-3.8-flash-high, cursor auto, native grok-4.7, deepseek-flash via opencode, kimi-code/k3-256k). Hermes RETIRED. grok-4.7 replaces grok-4.6 and is frontier tier with Claude Fable and OpenAI Astra. Use before any dispatch. Triggers on "which agent", "dispatch", "route to", "who should do this".
last_calibrated: 2026-09-21
---

# Dispatch Router Skill

Pick the right agent + model + tier for a task before firing a dispatch. This skill is the orchestrator's pre-flight checklist. Caps and **model ids rotate** — never trust memory or dated rows below without a live probe.

**Hermes is RETIRED (2026-09-16).** `--agent hermes` fail-closes. xAI content/CF → `--agent grok --model grok-4.7`. DeepSeek → `--agent deepseek` (opencode `deepseek-direct/*`). Aligns with learn-ukrainian topology + live CodexBar / `grok models` / `opencode models`.

**Grok 4.7 replaces Grok 4.6 (probed 2026-09-21).** `grok models` default is `grok-4.7`. `grok-4.6` remains in the CLI catalog; do not route new work to it. **Tier:** `grok-4.7` is frontier judgment, the same class as Claude Fable and OpenAI Astra — quality-critical author and cross-family review, not a cheap offload.

## LIVE model discovery (do this; do not ask the operator to recite)

Probe CLIs before a wave or when anything looks stale. Canonical defaults also live in `scripts/dispatch_smart.py` → `TASK_CLASSES` and `scripts/agent_runtime/registry.py`.

| Lane | Probe | Current default (2026-09-16) |
|---|---|---|
| **agy** (Google) | `agy models` | `gemini-3.8-flash-high` |
| **cursor** | `agent --list-models` | `auto` (default; not composer-*) |
| **grok** (xAI) | `grok models` | `grok-4.7` (CLI default; replaces `grok-4.6`; frontier with Fable and Astra) |
| **deepseek** | `opencode models` \| grep deepseek-direct | `deepseek-flash` via opencode `deepseek-direct/*` (LOCAL only) |
| **kimi** | `~/.kimi-code/config.toml` `default_model` | `kimi-code/k3-256k` (ACP oneshot; not bare `kimi -p`) |
| **claude** | task-class / `AB_CLAUDE_MODEL` | sonnet/opus per class (`claude-sonnet-4-6` / `claude-opus-4-8`) |
| **codex** | `AB_CODEX_MODEL` / task class | class defaults (`gpt-5.5` draft/review; spark/mini cheaper) |
| ~~hermes~~ | — | **RETIRED** — do not route |

If a probe disagrees with this table or `TASK_CLASSES`, **trust the probe** and update the code — do not invent slugs.

## EN epic 5-lane balance (epic #2272 / paid seats — 2026-09-16)

Rotate **authors** and **cross-family CF** across these seats so none idle while another burns:

| Seat | Dispatch | Default model | Prefer for | Never |
|---|---|---|---|---|
| **agy** | `--agent agy` | `gemini-3.8-flash-high` | EN content drafts / CF | habit-only author lane; stale `gemini-3.5-*` |
| **codex** | `--agent codex` | task-class default | quality-critical author + CF | habit-route on weekly deficit |
| **kimi** | `--agent kimi` | `kimi-code/k3-256k` | EN drafts/edits (ACP tools) | UK translation; bare `kimi -p` |
| **claude** | `--agent claude` | sonnet/opus per class | author + strong CF | pile-on during Anthropic throttle |
| **grok-4.7** | `--agent grok --model grok-4.7` | `grok-4.7` | frontier author + CF (Fable / Astra tier) | `--agent hermes`; routing `grok-4.6`; inventing `grok-build` |
| **deepseek** | `--agent deepseek` | `deepseek-flash` | cheap CF / volume | China-host from CI; hermes transport |

**Cursor seat:** when dispatching *to* cursor (not when Cursor is the epic driver), use `--model auto`. Driver-on-Cursor → never `--agent cursor`.

**Rotation rule (wave of N packets):** author seats cycle `kimi → agy → claude → grok-4.7 → codex` (skip only on live CodexBar throttle / auth fail). CF seat ≠ author family. `grok-4.7` counts as a frontier seat in that rotation, same judgment class as Fable and Astra. Prefer `kimi-code/k3-256k` over `kimi-code/k3` (1M) unless context demands it. Kimi headless writes go through ACP (`KimiAdapter` / `kimi_acp_oneshot.py`), not `-p`.

## Activity × lane matrix — route by ACTIVITY (families stable; MODEL IDS in older rows may be stale)

Pick the row for the activity, then the **primary doer**; for any write/author row, send the output to a **cross-family reviewer** (a DIFFERENT model family than the doer). **When a row below names an old model (`grok-4.6`, `grok-4.20-*`, `gemini-3.5-*`, `composer-2.5`, `deepseek-v4-pro`), substitute the LIVE default from the discovery table / `TASK_CLASSES`.** `grok-4.6` substitutes to `grok-4.7`.

| Activity | Primary doer | Cross-family reviewer(s) | Off-load / candidates |
|---|---|---|---|
| **Curriculum content — WRITE** (prose modules, expand-to-floor) | **grok-4.7** (frontier, Fable/Astra tier) ‖ **cursor** `--model auto` ‖ **codex** gpt-5.5 (quality-critical first pass) | grok-4.7 or opus (frontier) + agy + deepseek — pick ≥1 of a different family than the author | agy (2nd writer), deepseek |
| **Curriculum content — REVIEW** | — | **grok-4.7** (frontier, Fable/Astra tier) / **opus** (strongest Claude) / **cursor** / **agy** / **deepseek** (cheap) | mix ≥2 families; ≤2 per OAuth; ground-check ALL. ~~gemini-cli~~ RETIRED → use agy. ~~hermes~~ RETIRED → use grok |
| **UK translation — TRANSLATE** (EN→uk modules; roster tested 2026-07-04) | **deepseek-flash** (V4.1 Flash via opencode; **LOCAL only**, China-host, never CI) ‖ **opus-4.8** (`--effort xhigh`) for highest-stakes/reference | **opus-4.8 + gpt-5.5** cross-family (≠ DeepSeek): routine→1 (gpt-5.5, cheaper), high-stakes→both | **Russicism/calque = deterministic `scripts/check_uk_changed.py` + `sources` MCP RAG** — NOT the model reviewers. See `feedback_uk_translation_roster_tested_2026_07` |
| **Code / tooling — WRITE & FIX** (scripts, adapters, pipeline) | **cursor** `--model auto` (strongest fixer) | **grok-4.7** (frontier) / **codex** (danger+worktree) / **opus** / **deepseek** | codex |
| **Code / tooling — REVIEW** | — | **grok-4.7** (frontier) / **codex** (danger+worktree) / **opus** / **deepseek** | feed COMPLETE diffs |
| **Code-heavy MODULE content** (extending-k8s, tool certs — modules WITH code that must build) | **codex** gpt-5.5 (factual/version/runnability best) | **grok-4.7** or **opus** (frontier; route ≥1 here) + **deepseek** | cursor, agy |
| **Research / gap-analysis / architecture** | **grok-4.7** (frontier) + **codex** (architect/consult) + **opus** (architect class) | `ab discuss --with claude,codex,agy` for high-leverage ([[.claude/rules/decision-card]]) | deep-research harness; chrome MCP for source fetch |
| **Mechanical / deterministic** (gate fixes, link fixes, batched edits, search) | **cursor** or **codex** (cheap tier: spark / mini) | self-verify (`verify_module.py`, build, health) | — |

**Cross-family map** (reviewer ≠ author family): OpenAI = codex (Astra at the frontier) · Anthropic = claude/opus (Fable at the frontier) · Google = **agy** · DeepSeek = deepseek · **Zhipu = GLM** (via `opencode --model zai-coding-plan/glm-5.2`, #2171 — **LOCAL-ONLY**) · **Cursor Composer = cursor** · xAI = **grok-4.7** (native `--agent grok`; frontier with Fable and Astra; do not route `grok-4.6`). Soft caution: cursor↔grok share org post-merge. **The 4 clean independents: OpenAI / Google / Anthropic / DeepSeek.**

**Cost order (use flat-rate first; deepseek is dirt-cheap, not avoided):** cursor · codex · agy · deepseek · grok (xAI sub via native grok CLI). **opus headless is the only genuinely metered lane → ≤1–2 hardest reviews/wave.**

## Roster details — 2026-09-16 (Hermes retired)

| Agent | Access path | Strength | Constraint |
|---|---|---|---|
| cursor (auto) | `dispatch_smart --agent cursor --model auto` | Volume workhorse | `auto` or `composer-2.5` ONLY |
| codex | `dispatch_smart --agent codex` | Quality-critical author / CF | Weekly cap; review always danger |
| claude / opus | inline or `--agent claude` | Strongest reviewer | Prefer inline for reviews |
| agy | `--agent agy --model gemini-3.8-flash-high` | Google content + CF + RAG | Google pool |
| deepseek-flash | `--agent deepseek` → opencode `deepseek-direct/deepseek-flash` | Dirt-cheap CF / UK volume | **LOCAL only** — never CI; ground-check |
| **grok-4.7** | `--agent grok --model grok-4.7` | Frontier author + CF (Fable / Astra tier). Replaces grok-4.6 | Native grok CLI only; **NOT hermes**; do not route grok-4.6 |
| ~~hermes~~ | — | — | **RETIRED** — fail-closed redirect to grok / deepseek |
| qwen (residual) | prefer `--agent opencode --model openrouter/qwen/…`; residual `--agent qwen` still hermes-backed | Metered OpenRouter | Prefer opencode path |
| GLM | `--agent opencode --model zai-coding-plan/glm-5.2` | Coherence-audit finder | **LOCAL only** — never CI |

## Task class → agent decision tree

> The **Activity × lane matrix above is the authoritative router** — use it first. The command-level detail below is reference for each `dispatch_smart` task class.

### Search / read-only research
1. **Cheapest first**: `dispatch_smart search --agent codex` (gpt-5.4-mini) OR `claude-haiku` inline.
2. Do NOT use Opus or gpt-5.5 for search — overkill ([[reference_dispatch_smart]]).
3. For browser-required source fetch: `mcp__claude-in-chrome__*` ([[feedback_chrome_for_primary_source_fetch]]).
4. For x.com links: `--agent grok --model grok-4.7` (native default; hermes retired; do not use grok-4.6).

### Edit / sweep over many files
1. `dispatch_smart edit --agent <claude|codex>` (sonnet via subprocess for claude; spark for codex).
2. **NEVER use Agent-tool subagents for per-file sweeps** — 5x cost ([[feedback_dispatch_smart_for_sweeps]]).

### Draft (new content / module write)

T0 author primary is **codex-or-cursor** depending on codex weekly-cap state — quality-best lane per [[feedback_quality_over_budget_in_role_allocation]]:

1. **Codex cap healthy (default)** → `.venv/bin/python scripts/dispatch_smart.py draft --agent codex --mode danger --worktree X`. Stronger first-pass quality (factual/version/runnability). Codex `--search` is set automatically by the `draft` task class (`codex_search=True` at `scripts/dispatch_smart.py:168`); do NOT pass `--search` on the dispatch_smart CLI — it's a codex-CLI flag exported via `KUBEDOJO_CODEX_SEARCH=1`. The default codex model for `draft` is `gpt-5.3-codex-spark`; override with `--model gpt-5.5` for the top tier (higher per-call cost but cleaner first-pass). See [[feedback_codex_writer_needs_search]].
2. **Codex cap thin / throttle (or just high volume)** → cursor via `.venv/bin/python scripts/dispatch_smart.py draft --agent cursor --model auto` (headless) or cursor IDE. Use `auto` (preferred) or `composer-2.5` — never gpt-5.5. Verifier-pass ≠ runnability ([[feedback_composer_2_5_viable_for_t0_content]]); pair with a cross-family R1 review. Session 52 cursor-authored tooling/api/docs cohort measured 4/7 (57%) first-pass NEEDS_CHANGES — proxy signal that fix-pass is reliable but it's 2-3 rounds per PR. (No curriculum-T0 cohort yet at scale to measure directly.)
3. **Off-load (3+ codex authors in-flight)** → `dispatch_smart draft --agent deepseek`. Spread parallel-cap per [[feedback_parallel_rewrite_cap_three]].
4. **Bug fixes (any cap state)** → cursor composer-2.5. Proven 3/3 first-commit on session 51 bug PRs per [[feedback_cursor_is_strong_bug_fixer]]; different lane than T0 author.
5. See [[curriculum-writer]] for the author contract that binds every lane.

### Review (cross-family PR review)
1. Pick reviewer per Decision Card C routing — see [[cross-family-reviewer]].
2. Mix agents for 3+ parallel reviews ([[feedback_parallel_review_oauth_burst]]).
3. Always `--mode danger --worktree X` for codex review ([[feedback_codex_review_danger_mode]]).

### Architect / consult / decision
1. `dispatch_smart architect --agent codex` (gpt-5.5).
2. For high-leverage decisions: `scripts/ab discuss --with claude,codex,agy` ([[.claude/rules/decision-card]]).
3. Consult codex on non-trivial scope decisions ([[feedback_consult_codex_on_decisions]]).

## Live cap state — route on CodexBar when it's up (user directive 2026-07-07)

`codexbar` (Homebrew CLI + menu-bar app, `/opt/homebrew/bin/codexbar`) reports LIVE
per-lane quota windows. **When it's installed and running, base routing on ITS numbers**
instead of panel-checking rituals or guesses:

```bash
codexbar usage --provider both --no-color          # codex + claude in one call
codexbar usage --provider cursor --no-color        # Total / Auto / API pools
codexbar usage --provider antigravity --no-color   # agy — TWO pools (see rule 4)
codexbar usage --provider zai --no-color           # GLM (opencode zai-coding-plan)
# --format json for scripting; --provider all honors the in-app toggles
```

Routing rules on top of the numbers (verified output shape 2026-07-07):

1. **When to check**: before a wave (3+ dispatches), before any burst to a single lane,
   and at the start of a heavy orchestration session. Skip it for a one-off routine
   dispatch — each call takes seconds (web-dashboard fetch); don't tax every small call.
2. **Session window beats weekly.** `Session:` (the 5-hour rolling window) with its
   `Pace: … Projected empty in …` line is what heavy headless bursts actually exhaust
   (s195). If a lane's session window is projected empty before your batch would finish,
   route the batch to another family NOW — don't ride it into the throttle.
3. **Thresholds**: <20% left in the governing window → treat the lane as THROTTLED
   (route per the throttle section below). 20–40% → finish in-flight work but don't
   START a new multi-dispatch wave on that lane.
4. **agy has TWO pools** — `Gemini Models` vs `Claude and GPT` reset independently.
   Check the pool for the MODEL you're dispatching, not just the first line.
5. **deepseek and grok don't expose Session/Weekly windows** — window rules 2–3
   don't apply to either. deepseek: first-party API balance via opencode /
   deepseek-direct (a spend check; LOCAL only). grok: native `grok-4.7` on the
   SuperGrok subscription (CLI default; replaces `grok-4.6`) — treat like other
   subscription lanes and keep the `grok models` / auth check (`grok-build` is
   gone from the CLI catalog). Frontier tier with Fable and Astra; do not
   habit-route the retired `grok-4.6` slug.
6. **Fallback, never a blocker**: if `codexbar` is missing or errors (app not running,
   cookies stale), fall back to the manual pre-flight below and proceed.

## Pre-flight checklist (before EVERY dispatch)

1. **Is the agent's auth alive?**
   - Codex: `codex exec --help` should not 403. If it does, `codex login`.
   - Agy: open agy panel, verify Claude tier selected.
2. **Are caps healthy?** `codexbar usage` (section above) when available; else the
   panel/dashboard — before firing 3+ in parallel.
3. **Will this burn the cheap-tier first?** If the cheap tier (mini/spark/flash-lite) can do it, use it. Don't reflex-bump to gpt-5.5 ([[feedback_codex_model_routing]]).
4. **Will this fan out beyond the parallel cap?** Hard cap 3 parallel rewrites ([[feedback_parallel_rewrite_cap_three]]).
5. **Will this trip the OAuth burst limit?** Mix agents for 3+ parallel reviews ([[feedback_parallel_review_oauth_burst]]).
6. **Warn the user** before 3+ parallel OR 5+ sequential to any single agent in 10 min ([[feedback_warn_before_gemini_quota_burn]]).

## During Anthropic throttle (recurring constraint)

When the orchestrator's chat tier is throttled:
- **Preserve the opus orchestrator** (this terminal) on the main quota. A throttle is an Anthropic-side rate limit, so during one route NEW review/edit/draft work to **other families** (codex / agy / cursor / deepseek) rather than piling on more Claude load — headless `--agent claude` is allowed (billing is no longer a blocker) but pointless while Anthropic itself is throttled.
- Route review → codex / agy.
- Route edit → codex / agy.
- Route draft → composer-2.5 (cursor) / codex / deepseek.

The throttle window passes; resume normal routing post-reset. Default Claude weekly reset = Monday morning.

## After dispatch

1. Use `run_in_background: true`. Read `logs/dispatch_responses/<task-id>.txt` when notification fires.
2. **Do NOT spawn `until grep ... do sleep` watchers** — the wrapper notification IS the signal ([[feedback_no_separate_dispatch_watcher]]).
3. **Headless-claude liveness: check the session JSONL** (`~/.claude/projects/<worktree-path>/<uuid>.jsonl` mtime/size + `tail -1`), NOT `ps` — macOS `ps` grep is unreliable (s195: false “dying” diagnosis + duplicate re-dispatch races); trust the harness kill/complete notifications + real exit codes.
4. On finalize: check PR status, read produced reports, apply deltas, file follow-ups.

## Heredoc workaround for danger-mode briefs

After 2-3 consecutive `cat /tmp/brief.md | dispatch_smart --mode danger` calls, auto-mode classifier blocks the pattern. Workaround: inline heredoc so the brief is visible inline:

```bash
.venv/bin/python scripts/dispatch_smart.py draft --agent codex --mode danger \
  --worktree foo --prompt-file - <<'BRIEF'
... brief content ...
BRIEF
```

Heredoc satisfies the auditability intent; not for smuggling unreviewed content ([[feedback_heredoc_for_danger_dispatches]]).

## References

- [[reference_dispatch_smart]] — `scripts/dispatch_smart.py` task-class wrapper.
- [[reference_provider_routing_economics]] — provider vs agent vs model distinction.
- [[reference_agy_antigravity_cli]] — agy CLI details.
- [[reference_claude_i_billing_split]] — claude-i interactive-pool billing split.
- [[cross-family-reviewer]] — review-side routing protocol.
- [[curriculum-writer]] — author-side routing protocol.
- [[curriculum-orchestrator]] — the parent role that calls this skill.
- [`scripts/dispatch_smart.py`](../../../scripts/dispatch_smart.py) — the wrapper itself.
- [`scripts/ab`](../../../scripts/ab) — multi-agent bridge for `ab discuss`.
