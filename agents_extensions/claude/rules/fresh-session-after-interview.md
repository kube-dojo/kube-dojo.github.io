# Fresh Session After Interview

Convention for `AskUserQuestion`-driven decisions. When you interview the user
to scope a non-trivial decision (architecture, multi-week initiative, contested
review, framework selection), the act of asking the questions can bias the
EXECUTION that follows: by the time the user has answered, you've already
committed mentally to a shape and stopped looking for alternatives.

The fix is a fresh session for execution.

## When to use

Use a fresh session after an interview when:

- The decision is **high-leverage** — affects 100+ modules, sets a contract, or
  changes a default behavior across the project.
- The interview surfaced **multiple plausible designs** and you picked one
  largely because it was the first one the user reacted positively to.
- You're about to **dispatch codex/sonnet** to implement, and the brief will be
  hard to walk back once written.
- The interview took **5+ AskUserQuestion turns** — at that point, the cache
  is warm with one specific path and stopping fresh costs less than dragging
  bias into the build.

A worked example: session 35 calibration-framework design — user asked 15
questions locking dimensions, then said "go" → first dispatch could have
encoded session-34's "25-cell + 4 anchors" priors. The fresh-session pattern
breaks that.

## When NOT to use

Do NOT use when:

- The work is **routine** — backlog drain, content rewrite, bug fix, test add.
- The interview was **1-2 questions** clarifying a small ambiguity.
- The execution is **bounded < 1 hour** — the cache-miss + re-orientation cost
  exceeds the bias reduction.
- The user is **AFK** and you're operating autonomously — splitting sessions
  loses the dispatch chain and the user can't approve mid-run.

## How to apply

1. Finish the interview, summarize the decision in chat with the rationale.
2. **Write the decision to durable storage** before closing the session:
   - In a `## DECISION REQUIRED` Card per `.claude/rules/decision-card.md`, OR
   - In a `docs/decisions/{date}-{slug}.md` ADR, OR
   - In a GitHub issue body.
3. Either:
   - **User online** → say "starting fresh session to execute decision X" and
     do `claude` (new) — load the durable artifact as the brief.
   - **User AFK / autonomous** → proceed in-session but explicitly enumerate
     2-3 alternative shapes against the chosen one before the first
     dispatch. If you cannot articulate a real second-best, that's a yellow
     flag (the interview may have over-narrowed).

## Why this works

LLM agents have correlated priors and short working memory for adversarial
self-critique. The interview process produces strong priming on a specific
solution shape; the same context window then writes the dispatch brief. A
fresh session forces re-reading the durable artifact with no live priming —
the cache-miss is precisely the point.

This is the small-scale analog of `feedback_no_yes_man.md` ("get 2 independent
opinions before framing user concerns") applied to the agent's own bias.

## References

- Issue: kube-dojo/kube-dojo.github.io#1381
- Zodchii post #2: https://x.com/zodchiii/status/2057071039314542668
- `.claude/rules/decision-card.md` — durable-decision convention
- Memory: `feedback_no_yes_man.md` — adjacent practice for user-facing bias
