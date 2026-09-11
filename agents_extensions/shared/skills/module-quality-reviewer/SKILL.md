---
name: module-quality-reviewer
description: Evaluate KubeDojo curriculum modules against the eight-dimension pedagogical rubric and return evidence-backed scores and required fixes. Use for module quality reviews, not general code review.
---

# Module Quality Reviewer Skill

Review KubeDojo modules against repository-root `docs/quality-rubric.md`. The accountable lead owns reviewer routing and publication under current repository policy.

## How to Review

1. **Read the module fully** — line-by-line, not skim.
2. **Run the verifier first**: `.venv/bin/python scripts/quality/verify_module.py <path>`. Density gates failing (median_wpp < 28, mean_wpp < 30, short-para > 20%) = immediate NEEDS WORK; report the failing gates and leave rubric scores unassessed rather than inventing them.
3. **Score against ALL 8 rubric dimensions** (1-5 each).
4. **Be STRICT** — a 4 means genuinely good, a 5 is exceptional.
5. **Flag specific issues with line numbers**.
6. **Verify all external facts**. Burden of proof on keeping: if a citation `supports` the claim → keep; partial/no/fetch-fail/ambiguous → flag for removal.
7. **Test runnability** — actually run `bash`/`kubectl`/`yaml` snippets in a sandbox. A verifier pass does not establish runnability.

Before reporting a finding, verify the path and quote the actual reviewed file
at the cited line. Check the full file before claiming content is missing from
a diff. Verify schema, rule identifiers, version semantics, and shell behavior
against the relevant official documentation or executable check. State when an
example could not be run; never report an inferred result as observed. Apply
these checks to every reviewer regardless of model family, and challenge both
unsupported praise and unsupported criticism.

## Rubric Dimensions (1-5 each)

| Dimension | What to Check |
|-----------|--------------|
| **Learning Outcomes** | Are they stated? Measurable? Bloom's L3+? |
| **Scaffolding** | Does content build simple→complex? Narrative bridges between sections? |
| **Active Learning** | Are there inline prompts? Or is all practice back-loaded to the end? |
| **Real-World Connection** | Concrete, evidence-backed context, consequences, tradeoffs, or diagnosis? Or generic "in production" handwaving? |
| **Assessment Alignment** | Do quiz questions test understanding (scenarios) or recall (what is X?)? |
| **Cognitive Load** | Well-chunked? Diagrams integrated? Or information dump? |
| **Engagement** | Memorable tone? Would you recommend this to a colleague? Or dry/robotic? |
| **Practitioner Depth** (complexity-scaled) | Apply D8 in `docs/quality-rubric.md` for the module's complexity marker: purpose and honest tradeoffs for `[QUICK]`, patterns and decision guidance for `[MEDIUM]`, deeper failure analysis and architectural reasoning for advanced tiers. |

## Structure Checklist

- [ ] Learning Outcomes (Bloom's L3+ verbs: debug, design, evaluate)
- [ ] Why This Module Matters (clear motivation and practical relevance; any incident or scenario is cited or explicitly labeled `Hypothetical scenario:`/`Exercise scenario:`/`Simulation:`)
- [ ] Core content (3-6 sections with code, diagrams, tables)
- [ ] Inline active learning (at least 2 prediction/try-it prompts in the body)
- [ ] Did You Know? (4 facts with real numbers)
- [ ] Common Mistakes table (6-8 rows: Mistake | Why | Fix)
- [ ] Quiz (6-8 scenario-based questions with `<details>` answers)
- [ ] Hands-On Exercise (multi-step with success criteria)
- [ ] Next Module link

Do not penalize a module solely for omitting a story or analogy. When used, verify the incident's source, the hypothetical scenario's explicit label, and the analogy's mapping and limits. A labeled simulation illustrates a concept; it is not evidence that an incident occurred or a learner improved. Engagement scores are editorial judgments, not measured learner outcomes.

The author skill and this checklist share the shipping bar; illustrative templates do not lower it.

## Passing Criteria

Per the repository-root `docs/quality-rubric.md` (D1-D8), a module passes only when **both** hold:

- **Sum >= 33 out of 40** (8 dimensions, 1-5 each)
- **Every dimension >= 4** — a 3 anywhere is an automatic fail, regardless of sum

## Output Format

```markdown
## Module Review: [Name]
**File**: [path]
**Lines**: [count]

### Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Learning Outcomes | /5 | |
| Scaffolding | /5 | |
| Active Learning | /5 | |
| Real-World Connection | /5 | |
| Assessment Alignment | /5 | |
| Cognitive Load | /5 | |
| Engagement | /5 | |
| Practitioner Depth | /5 | (complexity-scaled) |
| **Sum** | **/40** | pass: sum >= 33 AND every dimension >= 4 |

### Structure Checklist
- [x] or [ ] for each required element

### Key Strengths
1. ...

### Must Fix
1. ...

### Verdict: PASS / NEEDS WORK / FAIL
```

## Reference Modules (Gold Standard)

> The listed five-point scores do not establish acceptance under the current eight-dimension contract. Verify current evidence before treating these modules as passing references.

- **Platform: What is Systems Thinking?** (4.6/5) — narrative voice, inline exercises, scenario-based assessment
- **On-Prem: The Case for On-Prem** (4.4/5) — balanced perspective, deliberate quiz traps, TCO exercise
- **Cloud: AWS Secrets Management** (4.0/5) — envelope encryption diagram, debugging quiz scenarios

## Anti-Patterns to Flag

- "List of facts" style (bullet points without connecting narrative)
- Quiz questions that test recall ("What is the command for X?")
- All active learning back-loaded to the end
- Diagrams with separate legends instead of inline labels
- "Refer to official documentation for details"
- Sections that could be rearranged in any order without losing coherence
- Unverified external citations (a hard-flag, not a soft-flag )
- Unsourced incidents presented as facts or anonymous “authentic” details treated as evidence
- Interview, job, or personal-role narratives unrelated to the module's learning task
- Listicle dumps without teaching arc

## References

- [curriculum-writer](../curriculum-writer/SKILL.md) — the author's content contract.
- Read `docs/quality-rubric.md` from the repository root for scoring definitions.
- Read `docs/pedagogical-framework.md` from the repository root for research backing the rubric.
- Read `docs/review-protocol.md` from the repository root for the review contract, subject to current repository policy.
