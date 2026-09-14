---
name: dispatch-router
description: Pick the right KubeDojo agent for a task across ALL activities — write / code / review / research / mechanical, not just review. Activity × lane matrix → agent → model → dispatch command. Roster as of 2026-07-07 (cursor, codex, opus/claude-headless, agy[model-selectable, the Google lane — gemini-cli RETIRED], deepseek, grok via grok-CLI/hermes). Use before any dispatch. Triggers on "which agent", "dispatch", "route to", "who should do this".
last_calibrated: 2026-07-07
---

# Dispatch Router Skill

Pick the right agent + model + tier for a task before firing a dispatch. This skill is the orchestrator's pre-flight checklist. It encodes [[reference_provider_routing_economics]] and the rotation of caps as of `last_calibrated`.

**Always cross-check memory keys** below before relying on an agent — caps and prices rotate weekly.

## EN epic 5-lane balance (epic #2272 / paid seats — 2026-09-14)

Rotate **authors** and **cross-family CF** across these five seats so none idle while another burns:

| Seat | Dispatch | Default model | Prefer for | Never |
|---|---|---|---|---|
| **agy** | `--agent agy` | `gemini-3.1-pro-high` | EN content drafts | habit-only author lane |
| **codex** | `--agent codex` | task-class default | quality-critical author + CF | habit-route on weekly deficit |
| **kimi** | `--agent kimi` | `kimi-code/k3-256k` | EN drafts/edits (ACP tools) | UK translation; bare `kimi -p` |
| **claude** | `--agent claude` | sonnet/opus per class | author + strong CF | pile-on during Anthropic throttle |
| **grok-4.6** | `--agent hermes --model grok-4.6` | `grok-4.6` | EN content CF/draft | confuse with `--agent grok` (grok-build code only) |

**Rotation rule (wave of N packets):** author seats cycle `kimi → agy → claude → hermes/grok-4.6 → codex` (skip a seat only on live CodexBar throttle / auth fail). CF seat ≠ author family. Driver on Cursor → never `--agent cursor`. Prefer `kimi-code/k3-256k` over `kimi-code/k3` (1M) unless context demands it. Kimi headless writes go through ACP (`KimiAdapter` / `kimi_acp_oneshot.py`), not `-p`.

## Activity × lane matrix (2026-06-04) — route by ACTIVITY, not just review

Pick the row for the activity, then the **primary doer**; for any write/author row, send the output to a **cross-family reviewer** (a DIFFERENT model family than the doer). All lanes below are flat-rate/cheap.

> **The Claude/opus seat is a normal dispatch lane again — `claude -p` is FREELY USABLE (billing change CANCELLED; user reaffirmed s188 2026-07-01).** `dispatch_smart --agent claude --model claude-opus-4-8` (or `claude-sonnet-5`) works as **author** and **reviewer** on the normal subscription path — no separate capped pool, no raw-Anthropic-API adapter. **The cheapest DEFAULT for a Claude *review* is still the orchestrator working INLINE** (read → web-verify → verdict), ideally EARLY while context is light — an inline verdict costs no extra dispatch and no reload, and it caught the verifier-blind P1s. Reach for **headless `--agent claude`** when an independent Claude context is worth the reload (the hardest 1–2 reviews of a heavy-context wave) or for **author lanes** (opus-4.8 / sonnet-5 as a T0 or translation author). Avoid the Agent-tool *subagent* form for reviews — its ~2–3M project reload is ~50–150× the tokens of an inline verdict. Every other family dispatches normally. See [[feedback_claude_billing_reroute]].

| Activity | Primary doer | Cross-family reviewer(s) | Off-load / candidates |
|---|---|---|---|
| **Curriculum content — WRITE** (prose modules, expand-to-floor) | **cursor** `--model auto` ‖ **codex** gpt-5.5 (quality-critical first pass) | opus(≤1/wave) + agy(3.1-pro-high, the Google lane) + deepseek + grok-4.20-0309-reasoning — pick ≥1 of a different family than the author | agy (2nd writer), deepseek, grok-4.3 |
| **Curriculum content — REVIEW** | — | **opus** (strongest) / **cursor** / **agy** (the Google lane) / **deepseek** (cheap) / **grok-4.20-0309-reasoning** | mix ≥2 families; ≤2 per OAuth; ground-check ALL. ~~gemini-cli~~ RETIRED ~2026-06-15 → use agy |
| **UK translation — TRANSLATE** (EN→uk modules; roster tested 2026-07-04) | **deepseek-v4-pro** (best value; **LOCAL only**, China-host, never CI; volume-proven s195 — uk `ai` track 44/44) ‖ **opus-4.8** (`--effort xhigh`) for highest-stakes/reference (quality ceiling: full translation + English-in-parentheses) | **opus-4.8 + gpt-5.5** cross-family (≠ DeepSeek): routine→1 (gpt-5.5, cheaper), high-stakes→both (2-review rule) | **Russicism/calque = deterministic `scripts/check_uk_changed.py` + `sources` MCP RAG (agy the RAG reviewer, or orchestrator inline)** — NOT the model reviewers (opus/gpt lack the UK dictionaries). NOT pool/glm/cursor (cursor russicism «перекатні» on long text). See `feedback_uk_translation_roster_tested_2026_07` + `reference_ukrainian_translation` |
| **Code / tooling — WRITE & FIX** (scripts, adapters, pipeline) | **cursor** `--model auto` (strongest fixer, 3/3) | **codex** (danger+worktree) / **opus** / **grok-build-0.1** / **deepseek** | codex |
| **Code / tooling — REVIEW** | — | **codex** (danger+worktree) / **opus** (best code-correctness) / **grok-build-0.1** / **deepseek** | feed grok-build COMPLETE diffs |
| **Code-heavy MODULE content** (extending-k8s, tool certs — modules WITH code that must build) | **codex** gpt-5.5 (factual/version/runnability best) | **opus** (route ≥1 here — caught every extending-k8s P1) + **grok-build-0.1** (code) + **deepseek** | cursor, agy |
| **Research / gap-analysis / architecture** | **codex** (architect/consult) + **opus** (architect class) | `ab discuss --with claude,codex,agy` for high-leverage ([[.claude/rules/decision-card]]) | deep-research harness; chrome MCP for source fetch |
| **Mechanical / deterministic** (gate fixes, link fixes, batched edits, search) | **cursor** or **codex** (cheap tier: composer-fast / spark / mini) | self-verify (`verify_module.py`, build, health) | — |

**Cross-family map** (reviewer ≠ author family): OpenAI = codex · Anthropic = claude/opus · Google = **agy** (gemini-cli RETIRED ~2026-06-15, user 2026-06-07) · DeepSeek = deepseek · **Zhipu = GLM** (via `opencode --model zai-coding-plan/glm-5.2`, #2171 — the cross-module **coherence-audit finder**; **LOCAL-ONLY**, China-hosted → hard-blocked from GH Actions/CI by `dispatch_smart.guard_no_china_provider_in_ci`; distinct family, a valid cross-family reviewer for OpenAI/Anthropic/Google authors, but Chinese-origin so prefer a Western-lab reviewer for top-stakes) · **Cursor Composer = cursor (composer-2.5, built on Kimi K2.5 / Moonshot — its OWN family, NOT xAI)** · xAI = grok-build / grok-4.x. ⚠️ cursor(composer-2.5) and `grok-composer-2.5` are the SAME model (xAI *serves* Cursor's Composer) — they cannot cross-review each other; grok-build / grok-4.x are a distinct xAI line (OK to review cursor-authored). Soft caution: cursor(Kimi) vs deepseek(DeepSeek) are different labs/bases (a valid pair) but both Chinese-origin → prefer a Western-lab reviewer for top-stakes cursor work. (Corrected s140; VentureBeat 2026 — see `feedback_cursor_composer_base_is_kimi_not_xai`.) ⚠️ **xAI and Cursor are now ONE COMPANY (merged, 2026-06) — user s167.** cursor↔grok therefore also carry a **soft shared-org caution** (prefer a different-org reviewer for top-stakes); the hard same-model exclusion (cursor Composer == `grok-composer-2.5-fast`) is unchanged. **The 4 clean independents: OpenAI / Google / Anthropic / DeepSeek.** Keep BOTH the cursor CLI and the grok CLI supported — unclear which becomes the mainstream CLI at the merged co.

**Cost order (use flat-rate first; deepseek is dirt-cheap, not avoided):** cursor (Pro+ 3×, the volume workhorse) · codex (weekly cap → quality-critical) · agy (the Google pool; gemini-cli RETIRED ~2026-06-15) · deepseek (≈free, the off-seat reviewer) · grok (xAI sub via hermes). **opus headless is the only genuinely metered lane post-2026-06-15 → ≤1–2 hardest reviews/wave; before then (Max 20× weekly) use it freely** ([[feedback_claude_billing_reroute]]).

## Roster details — 2026-06-04

> **What changed (2026-06-04, session 100):** agy `--model` now works (#1780) → agy is a Gemini-3.1-Pro-High **content/reviewer lane**; cursor review default fixed `gpt-5.5`→`auto` (#1782) — cursor uses **auto or composer-2.5 ONLY**; grok reachable via **hermes `--provider xai-oauth`** (#1783) — grok-4.20-reasoning (content) + grok-build-0.1 (code) both validated disciplined/no-fabrication; **deepseek is dirt-cheap** (use freely, NOT avoided). See [[feedback_cursor_proplus_3x_roster]], [[feedback_grok_cli_candidate_roster]].

| Agent | Access path | Strength | Constraint | Memory key |
|---|---|---|---|---|
| cursor (composer-2.5 / auto) | `dispatch_smart --agent cursor --model auto`; OR cursor IDE | **Volume workhorse** (Pro+ 3×): T0 content author, code/throughput, strongest bug-fixer, cross-family reviewer (in-cluster-verifying). | Use `auto` (preferred) or `composer-2.5` ONLY — never gpt-5.5 (review-class default fixed in #1782). composer-2.5 == grok-composer (same family). | [[feedback_cursor_proplus_3x_roster]], [[feedback_cursor_model_auto_not_composer]], [[feedback_cursor_is_strong_bug_fixer]] |
| codex (gpt-5.5 / spark / mini) | `dispatch_smart --agent codex` | Quality-critical author (factual/version/runnability), code review, architecture. gpt-5.5 top tier; spark=edit/draft; mini=search. | Weekly cap → reserve for quality-critical. Review ALWAYS `--mode danger --worktree X` (cwd mandatory for danger). Content fixes via `draft`+gpt-5.5+`--timeout 3600` (edit-class SIGKILLs). | [[feedback_codex_model_routing]], [[feedback_codex_review_danger_mode]] |
| claude / opus / sonnet-5 (`--agent claude`) | INLINE orchestrator (cheapest for reviews) **or** `dispatch_smart --agent claude --model claude-opus-4-8` (or `claude-sonnet-5`) | **STRONGEST reviewer** (content + code-correctness; caught the verifier-blind P1s) + viable author (opus / sonnet-5). Inline review = main quota, cheapest & immediate. | `claude -p` FREELY USABLE again — billing change CANCELLED, reaffirmed user s188 2026-07-01 (no capped pool, no raw-API adapter). Prefer INLINE for reviews; use headless for author lanes or an independent context on the 1–2 hardest reviews of a heavy wave; avoid the subagent form (~50–150× inline tokens). Heavy headless bursts hit the **5-hour rolling window** before the weekly cap (s195) — for sustained author volume prefer a deepseek-led author lane + claude review. | [[feedback_claude_billing_reroute]], [[feedback_opus_subagent_review_economics]] |
| **agy (Antigravity 1.0.6, model-selectable) — THE Google lane** | `dispatch_smart --agent agy --model gemini-3.1-pro-high` (Flash for review/search) | Gemini-class content writer + cross-family reviewer; independent Google pool. Replaces retired gemini-cli. **RAG-CAPABLE headless.** | `--model` works since #1780. RE-PROVE write on 3.1-pro before load-bearing (fabricated on Flash). **MCP/RAG works NOW (1.0.5+ `url` in `mcp_config.json`): the `sources` server (`:8766/mcp`, the RAG dictionaries) is pre-configured in `~/.gemini/config/mcp_config.json` + loads on startup; verified agy lists & calls `check_russian_shadow`/`query_sum20`/`verify_word` in `-p` (adapter's `--dangerously-skip-permissions` auto-approves). → agy = the flat-rate RAG reviewer for UK translation (#1829), no orchestrator/claude-budget bottleneck.** Confirm usable past the 2026-06-18 free-tier transition. | [[feedback_gemini_cli_sunset_pivot_to_agy]], [[reference_agy_antigravity_cli]] |
| ~~gemini-cli~~ **RETIRED ~2026-06-15** | — (do NOT route here) | _was_ the Google reviewer → **use agy** | Unusable from ~2026-06-15 (user 2026-06-07). Its `--mcp` was inert anyway (#1827 pilot). | [[feedback_gemini_cli_sunset_pivot_to_agy]] |
| deepseek-v4-pro | `dispatch_smart --agent deepseek` (via hermes provider=deepseek; review needs `--mode workspace-write`+`--worktree`) | **Dirt-cheap off-seat cross-family reviewer + 2nd fixer.** Use freely. | Hallucinates numbers/schemas → ground-check. NEVER from GH Actions (China-host 403). OpenRouter lane (#2241, US-hosted) is **EXPLICIT-ONLY after the 2026-07-07 drain incident (#2245)** — `openrouter/…` slug, tool_config provider, or `KUBEDOJO_HERMES_PROVIDER`; every silent fallback removed; hermes's machine-global default provider must stay `deepseek` (first-party). | [[feedback_deepseek_v4_pro_viable_for_t0_content]], [[feedback_deepseek_hallucinates_on_gh_schemas]] |
| **grok (native CLI) = grok-build** | `dispatch_smart --agent grok` (#2034, s167 — router-CLI path → `grok -p <prompt> -m grok-build --output-format plain`) | grok-build code reviewer/fixer (code ONLY; xAI). **The ONLY path to grok-build — hermes does NOT expose it.** | Needs grok CLI auth (`grok` login at grok.com — shows "not authenticated" until then). `-p` = inline content, no file tools → inline what you want reviewed; feed COMPLETE diffs. | [[feedback_grok_cli_candidate_roster]] |
| grok-4.* via hermes (xai-oauth) | `dispatch_smart --agent hermes --model grok-4.20-0309-reasoning` (content) — provider `xai-oauth` | grok-4.20-reasoning = content reviewer/writer (validated, disciplined). **grok-4.* is hermes-ONLY** (the grok CLI doesn't expose it). | Needs `hermes login --provider xai-oauth` (OAuth, re-login after a hermes rebuild — only deepseek survives). Keep ground-checking. | [[feedback_grok_cli_candidate_roster]] |
| grok-4.3 / grok-4.20-non-reasoning | `dispatch_smart --agent hermes --model grok-4.3` | Content candidates (smoke-pass; not yet quality-trialed). grok-4.20-multi-agent FAILS plain oneshot (needs agentic mode). | xai-oauth via hermes. | [[feedback_grok_cli_candidate_roster]] |
| hermes / opencode / qwen (metered) | `hermes -z --provider <p> -m <m>`; `dispatch_smart --agent {opencode,qwen}` | Multi-provider reach (hermes is also the deepseek + grok transport). | Pay-per-call beyond the subscription paths → only for x.com fetch (grok-4.3), grok-4.x content-candidate eval, or models no sub reaches. | [[feedback_grok_for_x_dot_com_links]], [[reference_qwen_hermes_openrouter]] |
| **GLM (Zhipu) via opencode — coherence-audit finder** | `dispatch_smart review --agent opencode --model zai-coding-plan/glm-5.2 --worktree X` (LOCAL only) | The **cross-module coherence lens** the per-module fleet lacks (found the KCNA/KCSA cert-fact contradictions, the cloud prerequisite cycle, the 'FOUNDATIONS COMPLETE' mislabel). Runs headless via the #2206 opencode `--format json` capture; depth-test passed (deep, zero-fabrication audits). Distinct Zhipu family → clean cross-family reviewer. | **China-hosted → NEVER from GH Actions/CI** (`guard_no_china_provider_in_ci` hard-refuses `zai-coding-plan`/`glm-`/`z.ai` in a CI context, #2171). Needs a local z.ai key + opencode configured for the `zai-coding-plan` provider. Findings still pass the two-gate fact check (evidence contract + orchestrator web-verify on volatile facts) — headless wiring does NOT remove the fact-gate. | [[feedback_no_china_apis_from_gh_actions]] |

## Task class → agent decision tree

> The **Activity × lane matrix above is the authoritative router** — use it first. The command-level detail below is reference for each `dispatch_smart` task class.

### Search / read-only research
1. **Cheapest first**: `dispatch_smart search --agent codex` (gpt-5.4-mini) OR `claude-haiku` inline.
2. Do NOT use Opus or gpt-5.5 for search — overkill ([[reference_dispatch_smart]]).
3. For browser-required source fetch: `mcp__claude-in-chrome__*` ([[feedback_chrome_for_primary_source_fetch]]).
4. For x.com links: hermes grok-4.3.

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
   don't apply to either. deepseek: `--provider deepseek` shows the first-party API
   balance (a spend check). grok: the roster lane is **grok-build on the SuperGrok
   SUBSCRIPTION** — CodexBar's `--provider grok` reads grok-web credits, which is NOT
   the grok-build lane's cap signal; treat grok like the other subscription lanes and
   keep the grok-CLI auth check.
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
