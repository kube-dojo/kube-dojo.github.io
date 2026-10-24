# Persistent agent listeners — Tier-3 architecture

**Date:** 2026-05-07
**Status:** Draft (Tier-3 deferred; Tier-2 ships separately — see follow-up PR)
**Decision driver:** GH issue #983 + session-5 handoff. Cross-validated via `ab discuss persistent-agent-listeners --with claude,codex,gemini --max-rounds 3` (converged round 3, full [AGREE]).

## Context

Issue #983 converged on three tiers:

- **Tier 1 (today):** cold subprocess + cold prompt cache per round of `ab discuss`. Full Anthropic prompt-cache miss every time.
- **Tier 2 (ships separately):** switch `_handle_discuss` to `entrypoint="bridge"` + reuse the existing `sessions` table via `discuss:{correlation_id}` key + per-agent gate. Claude-only resume in practice; Gemini receives a `session_id` but the CLI adapter drops it and `parse_response` returns `None`, so nothing is persisted; Codex stays fresh.
- **Tier 3 (this ADR):** API-daemon listeners with claim/lease/keepalive — true active-active continuity.

The corrections from deliberation are part of the decision:

- Tier-2 is a Claude resume win, not a three-agent cache win.
- Tier-2 implementation size was inflated in the initial framing; it should reuse existing storage and bridge entrypoint behavior, not add new schema.
- D1: reuse the existing `sessions` table.
- D2: write this local ADR before Tier-3 daemon work.
- D3: accept the Codex `resume_policy="never"` ceiling.

Current code already has the right primitives:

- `scripts/ai_agent_bridge/_db.py:41-48` defines `sessions(task_id, claude_session_id, gemini_session_id, codex_session_id, created_at, updated_at)`.
- `scripts/ai_agent_bridge/_db.py:283-339` exposes `get_session()` and `set_session()`.
- `scripts/ai_agent_bridge/_channels_cli.py:856-859` says `ab discuss` should stay on existing channel primitives: no new schema, tables, or middleware.
- `scripts/ai_agent_bridge/_channels_cli.py:954-982` currently invokes every discuss participant with `entrypoint="delegate"`.
- `scripts/ai_agent_bridge/_inbox.py:444-477` already shows the floor pattern: derive a thread-scoped task key, load a session, invoke with `entrypoint="bridge"`, persist the returned session on success.

## Where Cold-Start IS Correct

Do not broaden persistent listeners into every agent path.

- `delegate.py` worktree code dispatches: state lives in the worktree and issue, not in model memory. Cold subprocess is correct.
- `ask-codex` / `ask-gemini` drive-by Q&A: no continuity is needed.
- `ab discuss` deliberation lane: state is the conversation. Tier-2 and Tier-3 are scoped here only.

Tier-3 may later serve the `/channels` chat UI and AFK-notify reply path, but only for conversation lanes where continuity is the user-visible behavior.

## Decision

Build dedicated daemon listeners that maintain warm Anthropic prompt-cache state for the deliberation lane. Each listener subscribes to the bridge inbox via SSE or polling, replies from warm context, and persists `session_id` per `(agent, discussion correlation_id)` via the existing `sessions` table.

Tier-3 daemons augment `ab discuss`; they do not replace the bridge transcript, CLI orchestration, or `sessions` table.

## Q1 — Identity (4-column key)

Each listener process has a four-column identity:

| Column | Meaning | Example |
|---|---|---|
| `agent_family` | Which model family | `claude` |
| `ui_surface` | Which UI lane | `cli` (`ab discuss`), `web` (chat UI) |
| `client_id` | Stable per-installation id | `kubedojo-laptop-01` |
| `instance_id` | Per-process uuid | random uuid v4 per daemon start |

This disambiguates simultaneous demand for the same family:

- two `ab discuss` threads both asking for `claude`
- `/channels` chat UI asking for `claude`
- a restarted listener process recovering an abandoned claim

The warm model state belongs to the daemon process, not the thread. The persisted `session_id` belongs to the `(agent_family, discussion correlation_id)` conversation. Both identities are required.

Implementation sketch for Tier-3:

- Listener identity key: `(agent_family, ui_surface, client_id, instance_id)`.
- Conversation session key: `discuss:{correlation_id}` in `sessions.task_id`.
- Claim key: `(agent_family, ui_surface, correlation_id)`, owned by one live listener instance at a time.

## Q3 — participant_scope (Claim Semantics)

Use **discussion-level family claims with explicit handoff**, not round-level claims.

For a given `(agent_family, ui_surface, correlation_id)`, exactly one listener owns replies until it releases the claim, loses the lease, or another listener seizes after missed keepalives. Claims are scoped to a single discussion, not to all work for a family and not to each round.

Why discussion-level:

- Round-level claims would let different Claude listener processes answer round 1 and round 2 for the same discussion. That defeats warm prompt-cache continuity, which is the point of Tier-3.
- Family-global claims would serialize unrelated discussions and turn one busy thread into a blocker for all Claude work.
- Discussion-level claims prevent correlated context contamination across discussions. A warm listener must not answer two unrelated `ab discuss` threads from one mixed context unless it has explicit per-discussion session isolation.

Handoff is explicit:

- Current owner writes `release` when it shuts down cleanly or drains a discussion.
- New owner may claim after release.
- New owner may seize only after lease expiry.
- A listener that loses a claim must stop replying to that discussion and record `lease_lost` as the fallback reason for the declined call.

## Q6 — Lease + Keepalive + Seize

Use a 30-second lease TTL and a 10-second keepalive cadence.

Rules:

- Claim insert succeeds only when no unexpired claim exists for `(agent_family, ui_surface, correlation_id)`.
- Owner extends `lease_expires_at = now + 30s` every 10 seconds while it is actively subscribed and able to answer.
- If `lease_expires_at < now`, another listener may seize the claim with a compare-and-swap update.
- The seizing listener must load the last persisted `session_id` from `sessions` before invoking.
- If the prior owner wakes up after losing the claim, it must not post a reply. It records `lease_lost` and drops the in-flight response.

The existing inbox path is the floor, not the full daemon design:

- `scripts/ai_agent_bridge/_inbox.py:444-447` derives a thread-scoped task key and loads a stored Claude session.
- `scripts/ai_agent_bridge/_inbox.py:460-470` invokes with `entrypoint="bridge"`.
- `scripts/ai_agent_bridge/_inbox.py:474-477` persists the successful session.

Tier-3 keeps that session pattern and adds ownership around it. The lease table can be new Tier-3 state; the session table is not replaced.

Minimum claim fields for Tier-3:

| Field | Purpose |
|---|---|
| `agent_family` | family being claimed |
| `ui_surface` | CLI or web lane |
| `correlation_id` | discussion/thread identity |
| `client_id` | stable installation |
| `instance_id` | owning daemon process |
| `lease_expires_at` | seize boundary |
| `updated_at` | operator/debug visibility |

## Q11 — Fallback Reasons (Recorded Per Call)

Every daemon attempt records one fallback reason next to `entrypoint` in the usage log when it cannot answer through a warm listener:

| Reason | Meaning |
|---|---|
| `rate_limited` | Listener declines because the family is in real quota exhaustion. |
| `model_unavailable` | CLI, provider, or configured model is unavailable. |
| `lease_lost` | Listener lost ownership before it could post the reply. |
| `agent_explicit_fresh` | Caller requested a fresh invocation for this agent or policy requires it. |

For Tier-2 verification, usage records should also expose `session_mode=new|resume|none`. Existing usage records can show `entrypoint` and `session_id`, but not the literal adapter flag. The reviewer check is still concrete: round-2 Claude calls must resume the same persisted uuid, and the actual Claude subprocess must include `--resume <uuid>` once Tier-2 instrumentation exposes that command path.

## Per-Agent Caveats

These caveats are locked from the issue #983 deliberation.

### Codex

**Superseded policy:** commit `6c31de20d` changed Codex to `bridge_only`
resume and added discussion continuity. The legacy message bridge now also
honors scoped resume: task, cwd, and mode must match; `discuss:` rows remain
owned by discussions. Delegate/dispatch/consult calls still start fresh. The
cold-only statements below, D3, and the later per-agent ceiling check describe
the original decision, not the current registry policy.

Codex is intentionally cold-only.

- `scripts/agent_runtime/registry.py:13-15` says Codex uses `resume_policy="never"` because its "quota is per-message" and "session-across-worktree contamination is the #1 footgun".
- `scripts/agent_runtime/registry.py:43-56` sets `"codex"` to `resume_policy="never"`.
- `scripts/agent_runtime/runner.py:161-167` raises `ValueError` if a `session_id` is passed to a `resume_policy="never"` agent.

Tier-3 daemons may save Codex process spawn cost, roughly 1-2 seconds. They do not create a Codex prompt-cache win. Re-litigating Codex resume is out of scope for this ADR.

### Gemini

Gemini has bridge-side session storage but no CLI resume.

- `scripts/agent_runtime/adapters/gemini.py:16-20` says Gemini CLI has no session IDs and no `--resume` equivalent.
- `scripts/agent_runtime/adapters/gemini.py:99-102` says `session_id` is defensively ignored.
- `scripts/agent_runtime/adapters/gemini.py:141-146` drops `session_id` with `_ = session_id`.

Tier-3 daemons may save Gemini process spawn cost. They do not create a Gemini prompt-cache win until Gemini CLI adds resume support.

### Claude

Claude is the full resume win.

- Claude uses `resume_policy="bridge_only"` in the registry.
- `scripts/agent_runtime/runner.py:169-175` allows session resume only from `entrypoint="bridge"` for bridge-only agents.
- Tier-2 must flip `ab discuss` from `entrypoint="delegate"` to `entrypoint="bridge"` before any Claude `session_id` is passed, because `_channels_cli.py:974-982` currently uses delegate mode.

Claude is the only current agent where Tier-2 and Tier-3 actually warm Anthropic's cache.

## Out of Scope

- Re-litigating Codex `resume_policy="never"`; open a separate issue if that policy changes.
- Replacing the `sessions` table.
- Replacing `ab discuss` orchestration.
- Adding Tier-3 daemon code in this PR.
- Claiming a three-agent prompt-cache win.

## Reviewer Protocol

Inherited from the L-series ADR pattern:

1. **Stale-content sweep.** Confirm no orphaned cold-start paths, duplicate session stores, or stale listener claim paths remain after Tier-3 lands.
2. **Live continuity check.** Round-2 prompts to Claude must include `--resume <uuid>` in the actual subprocess command. Verifiable via `agent_runtime/usage_log` using the Tier-2 `session_mode=new|resume` field and `entrypoint="bridge"`.
3. **Per-agent ceiling check.** Codex must not receive a `session_id`; Gemini may receive bridge-side context but still must not be described as CLI-resumed.

## Cross-Project Reference

The cross-project Multi-UI ADR referenced as `docs/decisions/pending/2026-05-06-multi-ui-channel-participation.md` in learn-ukrainian does not exist in this repo. Gemini verified that during deliberation. This ADR is the local artifact; do not rely on import-by-reference.

## Acceptance Criteria for This ADR

- All four Q-sections answered with specific values.
- Per-agent caveats included and tied to current code references.
- Reviewer protocol included.
- Status remains `Draft`.
- No Tier-3 implementation included.
