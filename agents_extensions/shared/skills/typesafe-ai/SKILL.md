---
name: typesafe-ai
license: MIT
description: >
  Build with TypeSafe System One (Jev): typed Choice / Score / Noul judgments
  with calibrated probabilities for routing, ranking, verification, dataset
  row labeling (UA/Cyrillic keep-drop/OCR/dialect/Russian-shadow), and cheap
  pre-LLM triage. Use when an agent needs a structured decision instead of a
  full generative call. Read BEST_PRACTICES.md in this skill folder before
  designing calls.
when-to-use: >
  typesafe; TypeSafe; Jev; system one; Choice; Score; Noul; confidence routing;
  cheap triage; pre-dispatch routing; dataset row triage; open-model-data;
  Ukrainian word qualification; OCR junk; dialect label; Russian-shadow;
  replace prompt-and-parse with structured judgment
effort: medium
upstream: https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md
upstream-docs: https://docs.typesafe.ai/llms.txt
---

# TypeSafe (System One / Jev)

**Agent best-practice guide (read this):** [BEST_PRACTICES.md](BEST_PRACTICES.md)  
**Cookbook inventory (all 18, KD adopt/park):** [COOKBOOKS.md](COOKBOOKS.md)

**Live docs SSOT:** https://docs.typesafe.ai/llms.txt  
Prefer live docs over any vendored upstream body when they disagree.

## Credentials

```bash
export TYPESAFE_API_KEY="$(tr -d '\r\n' < ~/.secrets/typesafe-ai.key)"
```

Never print, commit, or paste the key. Log only `model` + usage tokens on receipts.

## Fleet overlay (short)

**Use freely for structured decisions** — routing, ranking, gates, and especially
Cyrillic/Ukrainian **labeling** (keep/drop, OCR, dialect, Russian-shadow, domain,
priority). Batch many Choice/Score/Noul questions in one `system_one` call.
Thresholds live in **code**.

**Only don't:**

- Leak the API key
- Invent VESUM-grade stress/paradigms **as fact** (label first; verify with
  VESUM/sources when you need attested morphology)
- Rewrite human source text
- Pretend TypeSafe replaces CF / Monitor / merge

Jev is **AI-powered software**, not an agent: code owns control flow; Jev returns
typed snap judgments. See [BEST_PRACTICES.md](BEST_PRACTICES.md) for do/don't,
playbooks, jaggedness traps, and a minimal HTTP example.

## Deploy

Canonical path: `agents_extensions/shared/skills/typesafe-ai/`.  
Run `agents_extensions/deploy.sh` (or `npm run agents:deploy`) so harness mirrors
update. Do not hand-edit deployed `.claude/skills/` copies as source of truth.
