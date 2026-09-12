---
description: Quality standards for writing KubeDojo curriculum modules
paths:
  - "docs/**/*.md"
---

# Module Quality Standards

## Required Sections (in order)
1. Title + metadata (complexity, time, prerequisites)
2. Learning Outcomes — 3-5 measurable outcomes using Bloom's L3+ verbs (debug, design, evaluate, compare)
3. Why This Module Matters — clear motivation and practical relevance; use a documented incident or explicitly labeled scenario only when it helps
4. Core content (3-6 sections with code, ASCII diagrams, tables, inline active learning prompts)
5. Did You Know? — exactly 4 facts
6. Common Mistakes — table with 6-8 rows
7. Quiz — 6-8 scenario-based questions with `<details>` answers (NO recall questions)
8. Hands-On Exercise — multi-step with `- [ ]` success criteria
9. Next Module link

## Pedagogical Requirements
- Bloom's Level 3+ minimum — no modules that only ask learners to remember/understand
- Constructive Alignment — outcomes, activities, and assessment must test the same thing
- Scaffold complexity — simple first, add layers progressively
- At least 2 inline active learning prompts distributed through core content
- At least 1 worked example before asking learner to solve a similar problem
- Quiz questions must be scenario-based ("Your team deployed X and Y happens — what do you check?")
- Reference rubric: `docs/quality-rubric.md` — all modules must score >= 33/40 sum AND every dimension >= 4 (8 dimensions including Practitioner Depth)

## Visual Aid Standards

### When to Use What
| Type | Use For | Example |
|------|---------|---------|
| **ASCII** | "What's in the box" — component anatomy, static architecture, simple hierarchies | Pod structure, node components, directory trees, comparison layouts |
| **Mermaid** | Logic and sequence — decision flows, request paths, state machines, timelines | Reconciliation loops, API request flow, CI/CD pipelines, pod lifecycle state diagram |
| **Tables** | Comparisons, decision matrices, reference data, feature grids | Tool comparison, Common Mistakes, version compatibility |
| **SVG** | Reserved for high-level topologies shared across multiple modules | Global architecture overview (rare — avoid unless truly needed) |

### Formatting Rules
- ASCII diagrams must be properly aligned — use consistent box widths, aligned columns, and uniform spacing
- Box borders must close properly (no missing corners or dangling lines)
- Labels must be integrated INTO diagrams, not in separate legends below
- All ASCII art must render correctly in monospace font (test column alignment)
- Tables must have consistent column widths and proper markdown alignment
- Mermaid diagrams: use consistent node naming, readable label lengths, and clear flow direction
- NEVER remove or simplify existing visual aids during rewrites — they are protected assets

## Content Rules
- Do NOT add a Markdown `# Module ...` heading after frontmatter. Starlight renders the page H1 from `title:` frontmatter, so a source H1 creates a duplicate visible title.
- The top-of-module metadata must be a blockquote immediately after frontmatter:
  `> **Complexity**: ...`, blank quoted line, `> **Time to Complete**: ...`, blank quoted line, `> **Prerequisites**: ...`, then `---`, then `## What You'll Be Able to Do`.
- Depth follows the topic scope, measurable outcomes, runnable examples, assessment alignment, and verified evidence. Length estimates may guide planning and routing, but are not evidence of factual support, learning effectiveness, or acceptance. Do not pad with repeated prose, decorative structure, or unsupported facts. If verified material is insufficient, state the shortfall for review rather than claiming completion; a concise module does not automatically pass. Visual aids supplement teaching and do not replace explanation.
- Explain "why" before "what"
- All code must be runnable (not pseudocode)
- Code blocks specify language (```bash, ```yaml, ```go)
- YAML: 2-space indentation
- kubectl alias: use `k` after explaining it once
- K8s version: 1.35+ for exam-pinned cert content; Release Radar covers supported upstream minors (see `docs/pins/kubernetes.yaml`)
- Do NOT repeat the number 47 (known LLM pattern)
- Do NOT use emojis
- Do NOT write "list of facts" modules — if sections are just bullets, it's a reference doc, not a lesson
- Stories and analogies are optional: real incidents require verifiable citations, hypothetical examples explicit labels, and analogies a clear mapping and limits. Do not manufacture mystery, clue hunts, or gamification to satisfy an engagement checklist.
