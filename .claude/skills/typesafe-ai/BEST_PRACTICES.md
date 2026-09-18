# Jev (TypeSafe System One) — agent best practices

**Audience:** every local fleet agent (Claude, Codex, Cursor, kimi, agy, grok, …).  
**Live docs (SSOT for API/primitives):** https://docs.typesafe.ai/llms.txt  
**Skill entry:** [[typesafe-ai]] / `agents_extensions/shared/skills/typesafe-ai/SKILL.md`  
**Model:** `jev-latest` (currently resolves to a `jev-1.x` build; pin only when debugging jaggedness).

Jev is a **decision model**, not a chat model. You send **state** + typed **questions**; you get **Choice / Score / Noul** answers with probabilities. **Your code (or your agent tool loop) owns control flow.** Jev does not write modules, CF comments, commits, or pick side effects by itself.

---

## 1. Setup (every host session)

```bash
export TYPESAFE_API_KEY="$(tr -d '\r\n' < ~/.secrets/typesafe-ai.key)"
# Host path is ~/.secrets/ (not repo .secrets/). Never print, commit, or paste the key.
```

Call shape:

```http
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
Content-Type: application/json
```

```json
{
  "state": { "...relevant facts only..." },
  "model": "jev-latest",
  "questions": {
    "q_id": { "type": "noul|choice|score", "instructions": "...", "criteria": "..." }
  }
}
```

**Receipt (always log):** `model` + `usage.input_tokens` / `usage.output_tokens`. Never log the key.

Python SDK (`typesafe_sdk`) is optional; raw HTTP is fine. Prefer `.venv/bin/python` in these repos.

---

## 2. When to reach for Jev

Use it when you need a **snap judgment over unstructured or semi-structured text** that code cannot decide with exact rules:

| Use | Primitive | Example |
| --- | --- | --- |
| Route / pick one seat | Choice | author vs CF agent family; next conveyor action |
| Yes/no gate | Noul | OCR junk? Russian-shadow? path-disjoint? merge-blocker fixed? |
| Degree on a rubric | Score | residual risk; D3 floor risk; follow-up priority |
| Dataset row labeling | Noul/Choice/Score fan-out | keep/drop, dialect, domain, OCR, priority |
| Pre-LLM triage | Choice + Noul | is this worth an expensive draft/review call? |
| Verification assist | Choice | does this source excerpt support the claim? |
| Skill suggestion | Choice over catalog + Noul “needs a skill?” | pick ≤1 skill |

**Batch.** Put every independent question about the same state in **one** call (speculative fan-out). Extra questions are cheap; round-trips are not.

---

## 3. How to ask (the important part)

Docs call this the core skill: **atomic questions**.

### Do

1. **One judgment per question.** “Is this OCR junk?” not “Analyze this row and decide what to do.”
2. **Explicit instructions + criteria.** Choice options and Score levels must be concrete situations a person could apply in one second.
3. **Minimal state.** JSON with named fields; reference with backtick paths (`candidates[2].text`). Filter in code first — Jev suffers context rot.
4. **Compose in code.** Weights, thresholds, “if A and B then C” live in Python/shell, not inside one mega-question.
5. **Escalate on uncertainty.** Choice/Score `confidence` low, or Noul near `0.5` → do not pretend certainty; call an LLM, VESUM/sources, or a human.
6. **Select, don’t generate.** Build candidate lists with regex/tools/LLMs; ask Jev to **pick**.

### Don’t (docs + jaggedness `jev-1.13`)

| Don’t | Do instead |
| --- | --- |
| Ask Jev to write prose, code, CF text, commits | Use a generative agent |
| Treat Jev as an agent that chooses its own next tool loop | Code/agent owns the workflow; Jev is a primitive inside it |
| Hide several judgments in one broad question | Split; fan-out; combine in code |
| Ask for counts, arithmetic, date ordering | Compute in code; Jev only for semantic parts |
| Reconstruct exact magnitudes from Score interpolation | Threshold Scores; don’t invent “the number” |
| Dump huge irrelevant state | Retrieve/filter first |
| Contradict instructions vs criteria (e.g. Noul true=no) | Align wording |
| Rely on model weights for attested facts (stress, paradigms, live prices) | Your KB / VESUM / sources / fetched docs |
| Leak `TYPESAFE_API_KEY` | Env only; receipts without secrets |
| Rewrite human source / dataset Ukrainian | **Label / gate only** |
| Assert VESUM-grade stress or full paradigms as fact from Jev | Label first (`dialect?`, `needs_vesum?`); verify before teaching |
| Replace Fleet Comms, Monitor leases, formal CF, or merge gates | Jev may **advise**; CF comment + exact-head CI remain authoritative |
| Call from CI without an issue authorizing egress/spend | Session/host experiments and authorized scripts only |

---

## 4. Primitives cheat sheet

| Type | Returns | Read it as |
| --- | --- | --- |
| **Choice** | `choice`, `probabilities`, `confidence` | Best option; confidence = how peaked the distribution is |
| **Score** | `score`, `legend`, `probabilities`, `confidence` | Position on **your** ordered levels (may fall between) |
| **Noul** | `noul` ∈ [0,1] | P(yes). ~0.5 = uncertain — **not** “medium intensity” |

Noul has **no** separate confidence field. For multi-label “which properties hold?”, use **one Noul per property**, not one Choice.

Include a **`none` / `other` / `skip`** Choice option when the closed set might not cover the input.

---

## 5. Confidence policy (tune in code)

Start conservative; adjust from receipts + outcomes. **Adopted defaults** (see [COOKBOOKS.md](COOKBOOKS.md)):

| Signal | Rule (KubeDojo) | Cookbook |
| --- | --- | --- |
| Choice `max(probabilities)` | Auto-act only if **≥ 0.60**; else treat as **uncertain** | consistency_choice |
| Choice top-two gap | If gap **< 0.15** → escalate (ambiguous) | fleet |
| Noul `parallel_ok` | **< 0.35** serialize · **> 0.65** parallel · mid = uncertain | fleet |
| Citation relation conf | Auto-accept verdict if **≥ 0.80**; else human | citation_check |
| Noul near 0.5 | Undecided — **not** “medium intensity” | consistency_noul |

| Stakes | Guidance |
| --- | --- |
| Low (seat garnish) | Prefer `top_prob ≥ 0.60`; else safe default seat in code |
| Medium (dataset keep/drop) | Stronger peak or escalate language-lane LLM |
| High (merge advice, destructive ops) | Jev is advisory only; still need CF≠author + exact-head CI green |

**Never** equate “Jev said merge” with “merged.” Batch all independent questions about the same state in **one** call ([parallel_questions](https://docs.typesafe.ai/cookbooks/parallel_questions.md)).

---

## 6. Fleet playbooks (copy/paste shapes)

### A. Pre-dispatch triage (KubeDojo epic / LU harness)

**State:** open PRs, author/auditor families, CI, CodexBar/capacity blurb, path lists.  
**Questions (one call):** `next_action` Choice · `author_agent` Choice · `cf_agent` Choice · `parallel_ok` Noul · `path_disjoint` Noul · `difficulty` Score.  
**Code:** map choices → `dispatch_smart` argv; if conf low, pick a safe default seat yourself.

### B. Ukrainian / Cyrillic row qualification (open-model-data)

**State:** list of `{id, text, context}` only — no urge to “fix” the text.  
**Per row (fan-out):** `keep` Noul · `ocr_junk` Noul · `russian_shadow` Noul · `dialect` Noul · `domain` Choice · `priority` Score.  
**Code gate example:**

```text
if ocr > 0.7 or keep < 0.35 → DROP
elif russian_shadow > 0.7 → DROP_OR_FLAG_RU
elif dialect > 0.6 → KEEP_DIALECT_TAG (queue VESUM if teaching forms)
else → KEEP
```

**Forbidden:** inventing stress marks or paradigms; rewriting the human string.

### C. Curriculum smell assist (not a full Gap Catcher audit)

**State:** short module excerpt(s), not the whole book.  
**Questions:** `spoiled_predict` Noul · `cookbook_only_exercise` Noul · `d3_risk` Score.  
**Code:** if smells fire → file/dispatch a real auditor LLM with evidence requirements. Jev does **not** post the audit comment of record.

### D. Citation / claim check

**State:** `{claim, source_excerpt}` (string-match the quote first when you have one).  
**Question:** Choice `supports` | `contradicts` | `says_nothing` ([citation_check](https://docs.typesafe.ai/cookbooks/citation_check.md)).  
**Code:** `scripts/typesafe_client.check_claim_against_excerpt` — auto if conf ≥ 0.80; else review. Fabricated quotes never call the model.

### E. Cookbook map

Full 18-cookbook adopt/park inventory: [COOKBOOKS.md](COOKBOOKS.md). Next builds when a wave needs them: skill_suggestion, llm_guardrails, consistency_noul repeats, sde_cascade.

---

## 7. Anti-patterns we already hit

- **Waiting forever for CI inside a generative CF agent** while Jev could have answered “is the P1 fix present in this diff hunk?” — use Jev for the semantic sniff; still require green CI for merge.
- **One question per HTTP call** — docs show ~10× cost/latency win from batching.
- **Asking “what should I do with my life?”** as one Choice with vague options — decompose.
- **Treating Noul 0.5 as a medium Score** — it means undecided.
- **Using Jev to invent morphology** — label + VESUM.

---

## 8. Minimal working example

```python
import json, os, urllib.request

def system_one(state, questions, model="jev-latest"):
    key = os.environ["TYPESAFE_API_KEY"]
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
    req = urllib.request.Request(
        "https://api.typesafe.ai/v1/systemone",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    # receipt
    print(f"RECEIPT model={data.get('model')} usage={data.get('usage')}")
    return data["answers"]

answers = system_one(
    {"token": "незaлежність", "note": "Latin 'a' inside Cyrillic word"},
    {
        "ocr_junk": {
            "type": "noul",
            "instructions": "Is `token` OCR/homoglyph junk rather than a clean Ukrainian word?",
        },
        "keep": {
            "type": "noul",
            "instructions": "Should `token` be kept as lexicon training material without repair?",
        },
    },
)
# thresholds in CODE
drop = answers["ocr_junk"]["noul"] > 0.7 or answers["keep"]["noul"] < 0.35
```

---

## 9. Checklist before you ship a Jev call

- [ ] Key loaded from `~/.secrets/typesafe-ai.key`; not printed
- [ ] State is the minimum relevant JSON
- [ ] Every question is one atomic judgment with clear criteria
- [ ] Independent questions batched in one request
- [ ] Thresholds / weights in code
- [ ] Low confidence path defined (escalate)
- [ ] Not used as CF/Monitor/merge authority
- [ ] Not used to rewrite human text or invent attested morphology
- [ ] Receipt logged (model + tokens)

---

## 10. Where this lives

| Path | Role |
| --- | --- |
| `agents_extensions/shared/skills/typesafe-ai/SKILL.md` | Skill trigger + fleet overlay |
| `agents_extensions/shared/skills/typesafe-ai/BEST_PRACTICES.md` | **This guide** |
| `agents_extensions/shared/skills/typesafe-ai/COOKBOOKS.md` | All 18 cookbooks — adopt / next / park |
| `scripts/typesafe_client.py` | HTTP client + citation helper + top_prob gates |
| `scripts/jev_epic_triage.py` | Epic pre-dispatch triage (batched) |
| `.agent/jev-experiment/` | Local receipts / decisions (gitignored) |
| https://docs.typesafe.ai/llms.txt | Live API / primitives / jaggedness |

After editing the skill tree, run the repo’s agents deploy (`npm run agents:deploy` / `agents_extensions/deploy.sh`) so harness mirrors under `.claude/skills/` (and siblings) update. Prefer live docs when they disagree with any vendored snapshot.
