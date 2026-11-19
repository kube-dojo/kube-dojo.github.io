# Durable Content for Fast-Moving Topics

Convention for writing curriculum content about anything that **churns faster than the curriculum can be revised** — AI coding tools/harnesses, model names and pricing, CNCF project maturity, cloud service limits and prices, framework version features. Locked 2026-06-07 (issue #1835, session 116) after the AI-coding-tools sub-track was found to be vendor-anchored, fabrication-heavy, and already obsolete.

## 1. The principle: separate the durable spine from the volatile skin

Most fast-moving topics have two layers:

- **Durable spine** (changes on a multi-year timescale) — the *concepts, primitives, taxonomies, open standards, and tradeoffs*. This is ~80% of good content and is what the learner actually needs.
- **Volatile skin** (changes in weeks–months) — *which vendor ships which feature, exact prices, current version numbers, today's product roster, a project's current maturity level*.

**Teach the spine. Isolate the skin.** A module organized around the volatile skin ("Tool X Deep Dive", "Pricing of Service Y") is obsolete by the next quarter and forces a full rewrite. A module organized around the durable spine, with the volatile bits quarantined into a small dated table, stays ~80% correct through churn — and a refresh means editing one table, not rewriting the module.

### Decompose orthogonal axes that churn independently

Many fast-moving domains have **two or more axes that each change on their own schedule**. Fusing them into one list makes the content fragile to churn in *either*. Split them, teach each once, and teach the **pairing logic** — then a new entrant on one axis slots into the framework instead of forcing a rewrite.

- **AI coding tools: harness ⟂ model.** The *harness* (agentic scaffold — runtime/loop/tools/permissions/memory/UI: Claude Code, Hermes, OpenClaw, aider, Cline…) is independent of the *model* (the brain — Claude, GPT, Gemini, or local open-weights like Gemma/Llama/Qwen, or DeepSeek). A **model-agnostic** harness (Hermes, OpenClaw, aider, Cline, opencode) can run on a **local** model, which flips the cost/privacy/capability tradeoff (e.g. an always-on autonomous agent on a local model has ~zero marginal token cost vs a runaway frontier-API bill). A **model-locked** harness (Claude Code, Codex) couples the two — note the coupling, don't assume it. Teach "pick a harness" and "pick a model" as separate decisions plus how to pair them.
- **Cloud: service ⟂ region ⟂ price.** A feature can be GA in one region and not another, at a price that changes independently of both.
- Surface each axis as its own durable concept and its own column/row in the snapshot; never collapse two independently-churning axes into a single ranked list.

## 2. Quarantine the volatile skin into a dated, refreshable artifact

Volatile facts go in **one of two isolated, clearly-dated places**, never woven through the prose:

1. **A "snapshot" callout/table** — a single block holding the current-state facts (prices, limits, version, maturity), opened with a date and a verify-before-relying note. Example:

   > **Landscape snapshot — as of 2026-06. This changes fast; verify against vendor docs before relying on specifics.**

2. **A Rosetta-style cross-vendor table** — one row per durable *capability*, one column per *vendor/product*, so the spine (the capability) owns the structure and the vendors are just cells. This mirrors the Cloud track's AWS↔GCP↔Azure "Rosetta Stone". For AI coding tools it is the **"AI Coding Harness Rosetta Stone"** (rows: rules file, MCP support, headless mode, plan mode, sub-agents, hooks, checkpoint/rewind…; columns: Claude Code, Codex, Gemini/Antigravity, Cursor, Copilot, aider…).

The refresh contract: **updating for churn = editing the snapshot/Rosetta cells, not the surrounding teaching.** If a churn update forces a prose rewrite, the spine/skin split was done wrong — fix the structure.

## 3. Date-stamp and mark volatility explicitly

- Every snapshot/Rosetta artifact carries a visible **`as of YYYY-MM`** date and a one-line "verify before relying" note.
- Prefer **relative/structural claims** that survive churn ("the CLI form factor favors scripting and CI; the IDE form factor favors inline edit-and-review") over **absolute volatile claims** ("Tool X is the only one with feature Y", "Service Z costs $0.10/hr", "Project P is Incubating").
- When an absolute volatile claim is unavoidable, put it in the dated artifact and make sure it is web/browser-verified at authoring time (see §5).
- **No leadership / "best tool" / market-share claims — this is the MOST volatile fact of all.** "Tool X is the leader / the best / what everyone uses" bakes in bias and ages in weeks (the AI-coding-tool race reorders constantly; billing/policy changes shift share fast). Never assert it. Present tools as **peers**; compare on **capabilities and tradeoffs**, not ranking. If a market-position statement is genuinely needed, it goes in the dated snapshot as an **attributed, web-verified** claim ("as of YYYY-MM, per <source>, …"), never as curriculum voice.

## 4. Teach the durable spine

For any fast-moving topic, the spine to teach instead of a product tour:

- **The underlying primitives and the loop/lifecycle** (e.g. the agentic loop: read→plan→act→verify; autonomy levels).
- **Taxonomies and form factors** — the axes along which options differ (e.g. CLI · IDE-integrated · desktop · cloud/background · CI/headless), which outlast any product in a given cell.
- **Open standards** — these are the most durable anchor: MCP (cross-vendor tool protocol), `AGENTS.md` (cross-tool rules-file convention, alongside `CLAUDE.md`/`.cursorrules`/`copilot-instructions.md`). Standards change far slower than products.
- **The evaluation framework** — teach the learner to assess *any* new entrant (what to look for, how to adopt), so a tool that ships in 6 months slots into the mental model the learner already has.
- **Tool-as-worked-example, not tool-as-subject** — a deep hands-on walkthrough is valuable; do it by teaching a *concept* with one tool as the running example, plus explicit "the equivalent in the others is…" cross-references to the Rosetta.
- **Rotate the worked example; label it as illustrative, not an endorsement.** Don't anchor an entire module (or sub-track) on one vendor's product as "the hero" — when that vendor's position shifts, the content reads as stale advocacy. Pick the example that best *demonstrates the concept* per section, state plainly "we use X here to make it concrete; see the Rosetta for the equivalents," and vary which tool plays that role across the sub-track.

## 5. Authoring + review obligations (compounds the existing anti-fab rules)

- **No fabricated currency.** Invented metrics, fake "internal study" statistics, made-up origin stories/quotes, and unsourced "Tool X is fastest/best" claims are the #1 failure mode in fast-moving content. They are banned by the anti-fabrication policy; this rule restates it because volatile topics attract them. Any narrative carries a `Hypothetical scenario:` label.
- **Ground-check every retained volatile claim** against current vendor/upstream docs at authoring time, browser/web-verified, and date it. Author/reviewer training cutoffs lag reality in both directions (they invent removed features AND deny real new ones) — see `feedback_web_verify_cncf_maturity` and `feedback_cloud_expand_authoring_failure_modes`.
- **Fix the layer, not the symptom.** When you touch a vendor-anchored module during any wave, prefer restructuring it onto the spine over patching the stale fact in place.

## 6. Applies project-wide

This is not just an AI-track rule. Apply it to any volatile content as waves reach it:

- **Cloud track** — pricing/limits tables, regional feature availability → dated snapshot tables (already partly done; the Rosetta Stone exists).
- **Cert/CNCF tracks** — project maturity (sandbox/incubating/graduated), tool version features → dated, web-verified per `feedback_web_verify_cncf_maturity`.
- **AI/ML track** — coding tools/harnesses, model names + context windows + pricing, framework feature sets → concept spine + Harness Rosetta.
- **Model identifiers anywhere** — name them in a dated snapshot, teach the capability tier (frontier/balanced/fast) as the durable concept.

## References

- Issue: kube-dojo/kube-dojo.github.io#1835 (rule + ai-native-development restructure pilot).
- Cloud "Rosetta Stone" precedent: `src/content/docs/cloud/` rosetta-stone modules.
- `feedback_web_verify_cncf_maturity` (memory) — web-verify maturity/currency both directions.
- `feedback_cloud_expand_authoring_failure_modes` (memory) — authors fabricate currency under expand pressure.
- `.claude/rules/` anti-fabrication conventions (war-story / `Hypothetical scenario:` labeling).
