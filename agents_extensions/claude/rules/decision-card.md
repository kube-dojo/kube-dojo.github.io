# Decision Card Pattern — Multi-Agent Deliberation

Convention for `scripts/ab discuss --with claude,codex,agy` (agy is the Google lane; gemini-cli is retired, #2125/#2230). Read this before participating in any `ab discuss` channel.

## Framing: distributed deliberation, NOT quorum

LLM agents have correlated priors. "Voting" is theater. Frame `ab discuss` as multi-perspective deliberation that surfaces *disagreement* and *option space*, not democratic consensus. Each agent argues from its own context, then orchestrator (claude) synthesizes.

## When to use ab discuss

**IN scope** (high-leverage decisions):
- Architecture choices (e.g., volume-run lane count, batch shape, coherence-review cadence)
- Threshold freezes (e.g., #388 verifier gate values)
- Contested NEEDS CHANGES — codex defends + agy blocks
- Strategic bets affecting 100+ modules
- Curriculum scope decisions

**OUT of scope**:
- Per-PR review (current codex → agy → merge pattern stays; would 3x latency)
- One-line fixes (typos, dead URLs, redundant code lines — orchestrator fixes inline)
- Single-module decisions
- Decisions where agents will obviously converge

## Agent participation rules

When you participate in an `ab discuss` channel:

1. **Read the question carefully**. If it's outside the IN-scope above, say so and decline to extend the discussion.
2. **Argue from your perspective**. Codex: implementation feasibility, code/build risks, sandbox/auth gotchas. Gemini: pedagogical accuracy, source verification, content quality. Claude: orchestration, cross-thread context, user constraints.
3. **Surface options, not just opinions**. If your view implies "do X," name X explicitly so the option enters the option-space.
4. **End your turn with one of**:
   - `[AGREE]` — you accept another agent's option as-is
   - `[OPTION X]` — you propose option X (label it; describe in 1-3 sentences)
   - `[DEFER]` — not your area; you defer to others
5. **Avoid rubber-stamping**. If you genuinely have no opinion, say `[DEFER]`. Empty `[AGREE]` votes pollute the deliberation.

## Decision Card — emit ONLY on disagreement

When `ab discuss` surfaces disagreement OR multi-option output, the orchestrator (claude) emits a Decision Card:

```markdown
## DECISION REQUIRED — {question}
**Agents:** claude, agy, codex (R rounds)
**Options:** A (proposed by ...), B (...), C (...)
**Votes:** claude→A {rationale}; agy→B {rationale}; codex→A {rationale}
**Disagreement:** {what they actually differ on}
**Orchestrator recommendation:** A — {rationale 1-3 lines}
**Awaiting:** user override or "go"
```

**When agents converge with [AGREE], NO card is emitted** — orchestrator just proceeds. Cards are for surfacing live disagreement, not stamping consensus.

## Surface protocol

- **User online** → emit Decision Card inline in chat (immediate visibility)
- **User AFK** → write Decision Card to `docs/decisions/pending/{date}-{slug}.md` (durable; user sees on session return)
- **Multi-week / architecture-level** → open a GH issue with the Card as the body
- **On user decision** → orchestrator moves `docs/decisions/pending/{date}-{slug}.md` → `docs/decisions/{date}-{slug}.md` with chosen option + date recorded

## Cold-start protocol

Future cold-start agents must scan `docs/decisions/pending/` for outstanding decisions. If anything is in `pending/`, surface it before starting other work.

## What NOT to build

- No quorum / tie-break / decision-record schema code (yet).
- The Card is a markdown convention + file-system layout. Add code only after 3-5 real discussions reveal where the convention fails. Premature voting machinery is the over-engineering trap.

## References

- Issue: kube-dojo/kube-dojo.github.io#740
- Memory key: `feedback_ab_discuss_for_decisions.md`
- Convention source: Claude on the learn-ukrainian project (2026-05-02). KubeDojo imports rather than reinvents.
