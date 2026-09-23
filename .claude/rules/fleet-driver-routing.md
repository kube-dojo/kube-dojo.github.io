# Fleet driver routing — GPT-6 roles (copied from learn-ukrainian, 2026-09-23)

Binding topology for KubeDojo drivers. Live model ids still come from
`scripts/dispatch_smart.py` `TASK_CLASSES` and a fresh probe. This file is the
role boundary, not a frozen roster.

## Codex roles

| Seat | Effort | Does | Does not |
| --- | --- | --- | --- |
| **GPT-6 Sol** | high | Accountable coding, content drafts that need the advanced seat, formal cross-family review | Scouting, lockfiles, routine bounded edits |
| **GPT-6 Luna** | high | Bounded repeatable work: search and edit. Default scout effort is high | Orchestrating, formal review, advisory |
| **GPT-6 Astra** | high | A really tough advisory problem only | Ordinary implementation, routine review, content CF, normal packets |

Do not dispatch Astra or Fable for a normal packet. Sol, Luna, Opus 5.5,
Sonnet 5, AGY, and native Grok cover coding, review, and content. Summon
Astra or Fable only when the problem is really tough: contested architecture,
a split review, or a judgment those seats cannot settle. Say why in the
routing card. Do not pick `gpt-5.6-*` for new work.

## Other seats

- **Claude Opus 5.5** — hard Claude-lane coding and the default review seat.
- **Claude Fable 5.1** — same reserve as Astra. Not routine track driving, not
  a default advisor, not a step before ordinary work.
- **Claude Sonnet 5** — routine edit and draft.
- **AGY `gemini-3.8-flash-high`** — well-defined implementation with a complete
  one-unit brief. Not a code or lab reviewer.
- **Cursor `grok-4.7-high`** — mechanical and ordinary implement when this
  driver is not itself the Cursor seat. Do not pass `auto`. Do not send
  Composer, Fast, `grok-4.6`, or `grok-4.5` for implement or review.
  KubeDojo search still resolves the Cursor search class to `composer-2.5`
  in `TASK_CLASSES`; that pin is search-only.
- **Native `grok-4.7`** — cross-family review and frontier authoring. Not a
  judge seat. A Cursor driver does not dispatch `--agent cursor`.

## Capacity

Probe with CodexBar on this repo (`codexbar usage --provider both`, plus
`cursor` and `antigravity`). Refuse a deficit or hot lane when a cooler fit
seat is free. Do not habit-route Codex while pace will not last to reset.

## Codex reset reserve (fail closed)

A valid operator assertion may temporarily admit Codex Sol despite a hot or
near-cap pace signal. It never overrides an exhausted or unknown weekly
allotment, a runtime block, stale usage, or an unhealthy route.

The operator records it at
`batch_state/routing_budget/operator_reset_reserve.json` in the primary
checkout. Exact fields: `schema_version` (`operator-reset-reserve.v1`),
`provider` (`codex`), positive integer `remaining_resets`, and UTC ISO-8601
`confirmed_at` / `expires_at`. Expiry is after confirmation and at most 24
hours later. `dispatch_smart` does not apply the reserve. A driver who wants to use it
calls `load_reset_reserve` and `codex_reset_reserve_eligible` from
`scripts.fleet.reset_reserve` and records the result on the routing card.
Passing a worktree path still reads the primary checkout's file. Missing,
malformed, expired, or extra fields leave the reserve unavailable. The helper
never decrements the count. No agent infers the count from usage data.

## Routing card

Before every implement `dispatch_smart` and every scarce-seat review:

```text
ROUTING_CARD_V1
task_id: <id>
tier: authority | practical | heap
model_x_harness: <agent>/<model>
why_this_tier: <one sentence>
advisor_packet: none | astra | fable
tough_problem: <required only when advisor_packet is astra or fable>
owned_paths: <paths>
acceptance_cmd: <command>
alternatives_considered:
  - <seat> — free/busy — why not
  - <seat> — free/busy — why not
```

`advisor_packet` stays `none` unless the card names a really tough problem.
After three implement dispatches in one session, use at least two agents and
two tiers, or write `NOTE: fleet_breadth` with a tool-backed blocker. The
same practical seat on a third consecutive implement dispatch needs that note.

Default shape: a qualified worker with no advisor call. Luna at high for
routine bounded Codex work. Sol at high for accountable coding and formal
review. Opus 5.5, Sonnet 5, AGY, or native Grok for the rest of ordinary
work. Astra and Fable are not that path.
