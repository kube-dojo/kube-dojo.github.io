# KubeDojo Pedagogical Framework

**Purpose**: Actionable guidelines for writing technical curriculum that actually teaches — not just lists facts. Grounded in educational research, calibrated to our content.

---

## 1. Bloom's Taxonomy: What Level Are We Teaching At?

Bloom's Taxonomy classifies cognitive skills from simple recall to complex creation. Most bad technical content lives at Level 1 (Remember) — "here's a list of commands." Good content pushes learners up the ladder.

### The Six Levels Applied to KubeDojo

| Level | Verb Examples | KubeDojo Content Type | Example |
|-------|---------------|----------------------|---------|
| **1. Remember** | List, name, recall | Glossaries, command references | "List the Pod phases" |
| **2. Understand** | Explain, describe, summarize | Concept explanations, "Why This Matters" | "Explain why Pods are ephemeral" |
| **3. Apply** | Execute, implement, use | Hands-on exercises, labs | "Create a Deployment with 3 replicas" |
| **4. Analyze** | Compare, differentiate, debug | Troubleshooting scenarios, tradeoff tables | "Debug why a Pod is in CrashLoopBackOff" |
| **5. Evaluate** | Judge, recommend, justify | Architecture decisions, "which tool to use" | "Evaluate whether to use StatefulSets or Deployments for this workload" |
| **6. Create** | Design, build, architect | Design exercises, capstone projects | "Design a multi-tenant RBAC scheme for 5 teams" |

### The Rule

Every module MUST operate at Level 3 (Apply) or above. A module that only asks learners to remember and understand is a reference doc, not a lesson. The quiz and exercise sections are where we push to Level 4-6.

**Good example** (from CKA Module 2.2 — Deployments):
> Exercise: "Your team's deployment is stuck at 2/3 replicas. The new pods keep crashing. Diagnose the issue, fix it, and verify the rollout completes."
> — This is Level 4 (Analyze) + Level 3 (Apply). The learner must reason about what went wrong.

**Bad example** (from KCNA Module 3.7 — Community, 49 lines):
> "Start small: docs fixes, issue triage, test flake investigations."
> — This is Level 1 (Remember). It lists things to do but never asks the learner to actually do any of them, reason about them, or apply them to a scenario.

---

## 2. Constructive Alignment: Do Outcomes, Activities, and Assessment Match?

John Biggs' Constructive Alignment principle: **Learning outcomes, teaching activities, and assessment must all test the same thing.**

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Learning Outcome │────▶│ Teaching Activity │────▶│   Assessment     │
│                  │     │                  │     │                  │
│ "Learner can     │     │ Explanation +    │     │ Quiz question +  │
│  debug a failing │     │ worked example   │     │ hands-on exercise│
│  Deployment"     │     │ of debugging     │     │ that requires    │
│                  │     │                  │     │ debugging        │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Misalignment Examples

| Problem | What It Looks Like | Our Modules |
|---------|-------------------|-------------|
| **Outcome without activity** | "By the end you'll understand X" but the module never explains X in depth | Some KCNA "theory" modules state high-level goals then give bullet-point summaries |
| **Activity without assessment** | Module explains a concept deeply but the quiz asks unrelated questions | Rare in our content, but watch for quizzes that test memorization when the module teaches understanding |
| **Assessment beyond teaching** | Quiz asks about topics not covered in the module | Happens when quiz questions are written separately from content |

### The Rule

Before writing a quiz question, check: "Did the module actually teach this?" Before writing an exercise, check: "Does the module explain enough for the learner to attempt this?" If the answer is no, either add the teaching or remove the assessment.

---

## 3. Cognitive Load Theory: Don't Overwhelm, Don't Underwhelm

Working memory holds ~4-7 items. Technical content constantly risks overloading learners by introducing too many new concepts simultaneously.

### Three Types of Cognitive Load

| Type | Definition | Our Control | Strategy |
|------|-----------|-------------|----------|
| **Intrinsic** | Inherent complexity of the topic | Cannot reduce — etcd consensus IS hard | Break into prerequisites. Teach pieces in isolation before combining. |
| **Extraneous** | Load caused by bad presentation | Full control | Integrate labels into diagrams. Don't split attention between text and separate figures. Remove redundant repetition. |
| **Germane** | Productive load from building mental models | Maximize this | Use analogies, worked examples, scaffolding. This is the "good" load. |

### Practical Strategies for Module Writers

1. **Scaffolding**: Start with the simplest version of the concept, then add complexity. Don't dump the full picture first.
   - **Good**: CKA Module 0.1 starts with `kind create cluster`, then progressively adds kubeadm, then multi-node.
   - **Bad**: A module that opens with a 50-line YAML manifest before explaining what any field does.

2. **Worked Examples**: Show the solution to a problem step-by-step BEFORE asking the learner to solve a similar one.
   - **Good**: "Here's how we'd debug a CrashLoopBackOff → [worked example] → Now you try: this pod is also failing, but for a different reason."
   - **Bad**: "Debug this pod" with no prior demonstration of the debugging process.

3. **Chunking**: Group related concepts together. Don't interleave unrelated topics.
   - **Good**: Teaching RBAC as: Subjects → Verbs → Resources → Roles → Bindings (each builds on the last).
   - **Bad**: Teaching RBAC mixed with NetworkPolicies mixed with PodSecurity in one section.

4. **Integrated Diagrams**: Labels belong ON the diagram, not in a separate legend below.
   - **Good**: ASCII diagrams with labels inline: `[kubelet] ---> [API Server] ---> [etcd]`
   - **Bad**: A diagram with numbered boxes and a separate key mapping numbers to names.

5. **Expertise Reversal**: What helps beginners hurts experts. Prerequisites and Fundamentals modules need more scaffolding; CKS and Platform Engineering modules can assume more.

---

## 4. Active Learning: Reading Is Not Learning

Passive reading creates an illusion of understanding. Active learning techniques force the learner to construct knowledge.

### Techniques We Should Use

| Technique | How It Works | Where in Our Modules |
|-----------|-------------|---------------------|
| **Scenario-Based Learning** | Present a real situation, ask the learner to make decisions | "Why This Matters" openings + exercises |
| **Prediction** | Ask "what do you think will happen?" before showing the result | Could add before code examples: "Before running this, predict the output" |
| **Elaborative Interrogation** | Ask "why?" after every fact | Quiz questions that ask "why does this work?" not "what is the command?" |
| **Interleaving** | Mix problem types within practice | Cumulative quizzes already do this across parts |
| **Spaced Repetition** | Revisit concepts across modules | Cross-module references, cumulative quizzes |
| **Retrieval Practice** | Test recall before reviewing | Quiz sections serve this role |

### The Rule

Integrate active learning where it supports the outcomes rather than reserving it for a final exercise. Shared activities may cover several outcomes; justify scope and omissions through `docs/review-contract.md`. Useful forms include:
1. A prediction or reasoning question embedded in the content (not just at the end)
2. A "what would happen if..." scenario that tests understanding, not recall

**Good example** (from Linux Module 7.1 — Bash Fundamentals):
> "What happens if you forget to quote `$variable` inside a test? Try it — the error message tells you exactly what went wrong."
> — Learner predicts, tries, observes. Active learning.

**Bad example**:
> "Remember to always quote variables in tests."
> — Passive instruction. The learner reads it, nods, and forgets.

---

## 5. What Top Platforms Do (And What We Can Learn)

### KodeKloud
- **Strength**: Video → Lab → Quiz pipeline. Every concept immediately practiced.
- **Lesson for us**: We don't have video, so our written explanations need to be richer than KodeKloud's (their text is often thin because video carries the teaching). Our advantage: searchable, version-controlled, deeper reference value.

### Killercoda
- **Strength**: Zero-setup instant environments. Scenario-based challenges.
- **Lesson for us**: Our lab references to Killercoda are good, but the MODULE should provide enough context that the lab makes sense. The module teaches, the lab practices.

### Pluralsight / A Cloud Guru
- **Strength**: Structured learning paths with skill assessments.
- **Lesson for us**: Our track organization (Fundamentals → Certifications → Platform) already does this. We should strengthen cross-module references ("Remember from Module 1.3 where we...").

### Linux Academy (now A Cloud Guru)
- **Strength**: "Playground" environments with open-ended exploration.
- **Lesson for us**: Some exercises should be open-ended ("Set up X however you want, then compare your approach to ours"). Not every exercise needs to be prescriptive.

### Common Pattern Across All

All successful platforms follow: **Concept → Demonstration → Guided Practice → Independent Practice → Assessment**. This is essentially the "I do, We do, You do" scaffolding pattern. Our module structure already supports this — the key is execution quality.

---

## 6. The "List of Facts" Anti-Pattern

The single biggest quality problem in technical curriculum: **modules that list facts without building understanding.**

### How to Detect It

A module has this problem if:
- You could rearrange the sections in any order and it would make no difference (no narrative flow)
- Sections are just "Header → 3 bullets → Header → 3 bullets" with no connecting tissue
- Commands are listed without explaining WHEN or WHY you'd use them
- The learner could pass the quiz by Ctrl+F through the module (tests recall, not understanding)
- There's no scenario, no story, no "what would happen if"

### How to Fix It

1. **Add narrative flow**: Section N should build on Section N-1. Each section should end with a bridge to the next.
2. **Add "why" paragraphs**: Before every command or config block, explain what problem it solves and when you'd use it.
3. **Add decision points**: "You have options A and B. Here's when you'd choose each and why."
4. **Add worked examples**: Don't just show the syntax — show it solving a real problem.
5. **Add prediction prompts**: "What do you think happens if we delete this pod while a rolling update is in progress?"

### Severity Scale

| Severity | Description | Action |
|----------|------------|--------|
| **Critical** | Module is a stub (<100 lines) or pure outline | Full rewrite required |
| **High** | Module lists facts without explanation (300+ lines of bullets) | Major restructure — add narrative, scenarios, exercises |
| **Medium** | Module teaches but lacks active learning (no exercises, no scenarios) | Add exercises, prediction prompts, worked examples |
| **Low** | Module teaches well but missing polish (no "Did You Know?", thin quiz) | Add missing sections per template |

---

## 7. Summary: The 7 Non-Negotiable Quality Signals

Check these practices against the researched outcomes and audience. Material omissions require correction or an independently accepted scope justification; counting checklist items cannot establish acceptance:

1. **Clear learning outcomes** stated at the top (what will you be able to DO after this?)
2. **Narrative flow** — sections build on each other, not random order
3. **"Why" before "What"** — motivation precedes instruction
4. **Worked examples** — appropriate worked explanation before comparable independent practice
5. **Active learning** — opportunities to think, predict, decide or retrieve that serve the taught outcomes, with feedback
6. **Visual aids** — diagrams, tables, or ASCII art that explain architecture/flow (not decoration)
7. **Aligned assessment** — quiz and exercise test what was actually taught, at Level 3+ on Bloom's
