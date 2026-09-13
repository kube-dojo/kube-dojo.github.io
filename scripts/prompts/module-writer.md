# KubeDojo Module Writer Prompt

Use this prompt to write new curriculum modules. Replace the variables in {{BRACKETS}}.

---

## PROMPT

TASK: Write a complete KubeDojo educational module.

### Module Specification

- **Title**: {{MODULE_TITLE}}
- **File path**: {{FILE_PATH}}
- **Complexity**: {{[QUICK] | [MEDIUM] | [COMPLEX]}}
- **Time to Complete**: {{TIME}}
- **Prerequisites**: {{PREREQUISITES}}
- **Next Module**: {{NEXT_MODULE_LINK}}

### Topic Coverage

{{5-7 BULLET POINTS OF WHAT TO COVER}}

### Hands-On Exercise Concept

{{EXERCISE_DESCRIPTION}}

---

### Quality Standard: 10/10 on the Dojo Scale

**DEPTH AND LENGTH**: Set the module's substantive scope from its topic, measurable outcomes, exercise, assessment, and verified evidence. Line and word counts are planning signals for routing and review; they are not proof of factual support, learning quality, or acceptance. Do not add repeated prose, decorative structure, or unsupported facts to reach a number. If verified material cannot support the requested scope, report the shortfall in the requested output format instead of inventing detail or claiming completion. Visual aids supplement teaching; they do not replace explanation.

**REQUIRED SECTIONS** (in this exact order):

1. **Frontmatter and metadata blockquote** — frontmatter `title:` + `slug:` + `sidebar.order:` (Starlight renders the page H1 from `title:`, so do NOT add a source `# Module X.Y` heading after the frontmatter — this would render as a duplicate visible title). Then a blockquote with `> **Complexity**: ...`, `> **Time to Complete**: ...`, `> **Prerequisites**: ...`, separated by `>` blank-quote lines, terminated with `---`.
2. **Learning Outcomes** — 3-5 measurable outcomes using Bloom's Taxonomy Level 3+ action verbs: "debug", "design", "evaluate", "compare", "diagnose", "implement". NOT "understand" or "know". Each outcome must be testable by the quiz or exercise.
3. **Why This Module Matters** — Open with a clear explanation of why the topic matters and what the learner will build or diagnose. Use a sourced incident or explicitly labeled `Hypothetical scenario:`/`Exercise scenario:` only when it clarifies the outcome. Give the learner enough explanation to connect the stakes to the stated outcome; do not pad this section to meet a paragraph count.
4. **Core content sections** (3-6 sections) — Each section should include:
   - **Theory before practice** — explain WHY this approach exists, what problem it solves, and what tradeoffs it makes BEFORE showing the commands. Prose must explain concepts between code blocks — never stack 3 code blocks without explanation.
   - Clear explanations for a smart beginner; use an analogy only when it clarifies the outcome and state its limits
   - Runnable code blocks (bash, YAML, Go, Python — whatever fits)
   - ASCII diagrams where architecture or flow needs visualization
   - Tables for comparisons, decision matrices, or reference data
   - Sourced real incident or clearly labeled hypothetical practical example when it materially supports the section; omit it when evidence is insufficient
   - **At least 2 inline active learning prompts** across all sections: "Pause and predict: what do you think happens if...?", "Before running this, what output do you expect?", or "Which approach would you choose here and why?"
   - **Cost lens (cross-cutting)** — If the module covers any cloud service, infrastructure component, or operational practice with a measurable price tag, the core content MUST address the cost dimension. At minimum: (a) what does this cost in production at moderate scale, (b) which knobs reduce cost (rightsizing, scheduling, tiering, autoscaling), (c) what makes cost spike unexpectedly (cross-AZ traffic, idle resources, log volume, log-retention defaults). Treat "what does it cost" as a first-class engineering concern alongside "how does it work." Skip only for pure-theory modules (mental models, philosophy, prerequisite concepts) where no cost surface exists.
5. **Patterns & Anti-Patterns** — Required for `[MEDIUM]`, `[COMPLEX]`, `[ADVANCED]`, `[EXPERT]` modules. For `[QUICK]` introductory modules, this can be a single "When This Doesn't Apply" subsection instead of full patterns/anti-patterns.
   - **Patterns**: proven approaches with when to use, why it works, scaling considerations. Minimum 3 for MEDIUM+, 1 for QUICK.
   - **Anti-patterns**: what goes wrong, why teams fall into it, better alternative. Minimum 3 for MEDIUM+, 1 for QUICK.
   - Use tables or structured format.
6. **Decision Framework** — Required for `[MEDIUM]`+ modules. For `[QUICK]` modules, replace with a "When You'd Use This vs Alternatives" comparison.
   - MEDIUM+: flowchart, decision matrix, or structured guide for choosing between approaches. Include tradeoffs.
   - QUICK: simple "Use X when... Use Y when..." paragraph or table.
7. **Did You Know?** — Exactly 4 interesting facts. Include real numbers, dates, or surprising details. Each fact should teach something the reader won't forget.
8. **Common Mistakes** — Table with 6-8 rows. Columns: Mistake | Why It Happens | How to Fix It. Be specific — not generic advice.
9. **Quiz** — 6-8 questions using `<details><summary>Question</summary>Answer</details>` format. **At least 4 must be scenario-based** ("Your team just deployed X and Y happens — what do you check?"). Do NOT write recall questions ("What is the command for X?"). Answers should be thorough (3-5 sentences explaining WHY).
10. **Hands-On Exercise** — Multi-step practical exercise with:
    - Setup instructions (if needed)
    - 4-6 progressive tasks (easy → challenging)
    - Solutions in `<details>` tags
    - Clear success criteria checklist using `- [ ]` format
11. **Sources** — Required final module section before `## Next Module`, with at least 3 citations to primary/vendor docs.
    - Each citation is either a bare URL (`- https://...`) or `[title](url)` markdown link.
    - At least 3 entries are required.
    - The deterministic verifier counts links inside the Sources section only — citations elsewhere don't count.
12. **Next Module** — Link to the next module with a one-line teaser

**TONE**:
- Conversational but authoritative — like a senior engineer mentoring you
- Explain "why" before "what" — motivation before instruction
- Use familiar analogies only when they clarify abstract concepts; state where the mapping stops
- Be direct and practical — no filler, no corporate-speak
- When discussing tools, be honest about trade-offs (no marketing language)

**VISUAL AID STANDARDS**:
- **ASCII**: Use for component anatomy, static architecture, hierarchies ("what's in the box")
- **Mermaid**: Use for logic flows, sequences, state machines, request paths ("how it works")
- **Tables**: Use for comparisons, decision matrices, reference data
- ASCII diagrams must be properly aligned — consistent box widths, aligned columns, uniform spacing
- Box borders must close properly (no missing corners, no dangling lines)
- Labels must be integrated INTO diagrams, not in separate legends
- Test that ASCII art renders correctly in monospace — count characters for column alignment
- Tables must have consistent column widths and proper markdown alignment

**TECHNICAL STANDARDS**:
- All commands must be complete and runnable (not pseudocode)
- YAML: 2-space indentation, valid syntax
- Code blocks must specify the language (```bash, ```yaml, ```go, etc.)
- Do NOT rely on shell aliases in runnable Bash examples. Do not define a short alias for `kubectl`, and do not use the `k` shorthand for get/describe/apply-style commands inside fenced ```bash / ```sh / ```shell / ```zsh blocks. Aliases do not expand in non-interactive shells, so use the full `kubectl` binary name in copy-paste examples. Prose like "many engineers use a short kubectl alias interactively" is fine.
- Kubernetes version: 1.35+ for exam-pinned cert modules; use Release Radar (`/k8s/releases/`) for 1.36/1.37+ deltas. Standing trigger for a new minor: `docs/release-maintenance/kubernetes-minor-release-playbook.md`. Do not rewrite cert tracks on upstream GA.

**PEDAGOGICAL REQUIREMENTS** (from `docs/pedagogical-framework.md`):
- Every module must operate at Bloom's Taxonomy Level 3 (Apply) or above
- Constructive Alignment: learning outcomes, teaching activities, and assessment must test the same thing
- Scaffold complexity: start simple, add layers. Don't dump the full picture first.
- Include at least one worked example before asking the learner to solve a similar problem
- Integrate labels directly into diagrams (no separate legends)
- Active learning must be distributed throughout, not just at the end

**SECRETS & CREDENTIALS IN EXAMPLES**:
- NEVER use realistic-looking secrets, tokens, or webhook URLs in code examples
- Slack webhooks: use `https://hooks.slack.com/services/YOUR/WEBHOOK/HERE` (not `T00000000/B00000000/XXX`)
- AWS keys: use `AKIAIOSFODNN7EXAMPLE` (the official AWS example key)
- API tokens: use `your-api-token-here` or `<TOKEN>`
- URLs with auth: use `https://example.com/webhook` or `https://httpbin.org/post`
- GitHub tokens: use `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- Any value that matches a known secret pattern (Slack, AWS, GitHub, GCP, Azure) WILL be blocked by GitHub push protection

**WHAT TO AVOID**:
- Do NOT repeat the number 47 in timestamps, durations, or counts (this is a known LLM pattern — vary your numbers)
- Do NOT invent business incidents, client stories, anonymized companies, or anecdotal incident claims. Use sourced real incidents or clearly labeled hypothetical/exercise scenarios.
- Do NOT add a mystery, clue hunt, or gamification layer solely to make a module engaging.
- Do NOT write thin outlines — every section needs depth, examples, and explanation
- Do NOT skip the exercise — it's the most important part for learning
- Do NOT use emojis
- Do NOT write quiz questions that test recall ("What is X?") — write scenario-based questions
- Do NOT create "list of facts" modules — if sections are just "Header → 3 bullets", you're writing a reference doc, not a lesson
- Do NOT back-load all active learning to the end — distribute prediction prompts and "try it" moments throughout

**REFERENCE**: Study the structure and depth of existing KubeDojo modules for calibration. Each module should feel like a chapter in a technical book, not a blog post.
