# Module layout examples

Read the relevant track section only. These examples show layout, not reduced acceptance criteria: the content contract in [SKILL.md](SKILL.md) and repository rubric set the shipping bar.

## Track-Specific Guidelines

These examples illustrate different track focuses:

### Kubernetes Certifications (src/content/docs/k8s/)
- Exam-focused content
- Aligned with official CNCF curriculum
- Time-boxed complexity (exam speed matters)
- kubectl commands emphasized

### Prerequisites (src/content/docs/prerequisites/)
- Beginner-friendly fundamentals
- No assumed knowledge
- Build foundation for certifications

### Platform Engineering (src/content/docs/platform/)
- Post-certification, practitioner content
- Theory-first approach (principles over tools)
- Three layers: Foundations → Disciplines → Toolkits

---

## Platform Track Structure

Platform modules have **three tiers**:

### Foundations (src/content/docs/platform/foundations/)
Timeless theory that doesn't change:
- Systems Thinking
- Reliability Engineering
- Observability Theory
- Security Principles
- Distributed Systems

### Disciplines (src/content/docs/platform/disciplines/)
Applied practices and mental models:
- SRE
- Platform Engineering
- GitOps
- DevSecOps
- MLOps

### Toolkits (src/content/docs/platform/toolkits/)
Current tools (will evolve over time):
- Observability (Prometheus, OTel, Grafana)
- GitOps Tools (ArgoCD, Flux)
- Security Tools (Vault, OPA, Falco)
- Platforms (Backstage, Crossplane)
- ML Platforms (Kubeflow, MLflow)

---

## Module Template (Certification Track)

````markdown
---
title: "Module X.Y: [Topic Name]"
sidebar:
  order: 1 # Replace with the module's navigation order.
slug: "module-X.Y-topic-name" # Set the published path; preserve filename dots.
---

# Module X.Y: [Topic Name]

> **Complexity**: `[QUICK]` | `[MEDIUM]` | `[COMPLEX]`
>
> **Time to Complete**: X-Y minutes
>
> **Prerequisites**: [List required modules or knowledge]

---

## Why This Module Matters

[2-3 paragraphs explaining WHY this topic matters]

> **Optional analogy: [Topic]**
>
> [Use only when it clarifies the concept; state the mapping and its limits.]

---

## What You'll Learn

[Clear learning objectives]

---

## Part 1: [Theory/Concepts]

### 1.1 [Subsection]

[Content with diagrams/examples]

> **Predict:** [Ask the learner to predict an outcome before revealing the explanation.]

> **Did You Know?**
>
> [Interesting fact]

---

## Part 2: [Practical Application]

[Hands-on content]

> **Try it:** [Give a short task here in the body, with a way to check the result.]

> **Optional documented case or labeled scenario**
>
> [Use a cited real incident, or label `Hypothetical scenario:`/`Simulation:` and state what is simulated.]

---

## Did You Know?

- **[Fact 1]**: [Verified detail with real numbers and supporting source]
- **[Fact 2]**: [Verified detail with real numbers and supporting source]
- **[Fact 3]**: [Verified detail with real numbers and supporting source]
- **[Fact 4]**: [Verified detail with real numbers and supporting source]

---

## Common Mistakes

[Complete this table with 6–8 distinct mistakes and concrete fixes.]

| Mistake | Problem | Solution |
|---------|---------|----------|
| [Mistake 1] | [What goes wrong] | [How to fix] |
| [Mistake 2] | [What goes wrong] | [How to fix] |

---

## Quiz

1. **[Question]**
   <details>
   <summary>Answer</summary>
   [Detailed answer explaining why]
   </details>

[6–8 scenario-based questions total]

---

## Hands-On Exercise

**Task**: [What to do]

**Steps**:
1. [Step 1]
2. [Step 2]

**Success Criteria**:
- [ ] [Verifiable outcome]

**Verification**:
```bash
[Commands to verify]
```

---

## Sources

[Replace all three placeholders with verified primary/vendor documentation citations; inline citations elsewhere do not replace this section.]

- [Primary/vendor source 1 title](PRIMARY_VENDOR_URL_1)
- [Primary/vendor source 2 title](PRIMARY_VENDOR_URL_2)
- [Primary/vendor source 3 title](PRIMARY_VENDOR_URL_3)

## Next Module

[Link to next module]
````

---

## Module Template (Platform Track)

Platform modules include additional sections:

````markdown
---
title: "Module X.Y: [Topic Name]"
sidebar:
  order: 1 # Replace with the module's navigation order.
slug: "module-X.Y-topic-name" # Set the published path; preserve filename dots.
---

# Module X.Y: [Topic Name]

> **Complexity**: `[QUICK]` | `[MEDIUM]` | `[COMPLEX]`
>
> **Time to Complete**: X-Y minutes
>
> **Prerequisites**: [List required modules]
>
> **Track**: Foundations | Disciplines | Toolkits

---

## Why This Module Matters

[Real-world motivation - not exam-focused]

> **Optional analogy: [Topic]**
>
> [If useful, connect the concept to something familiar and state where the analogy stops matching.]

---

## What You'll Learn

[Learning objectives]

---

## Key Concepts

### [Concept 1]

[Theory explanation with diagrams]

> **Predict:** [Ask the learner to predict a tradeoff or outcome, then explain why.]

### [Concept 2]

[More theory]

> **Try it:** [Ask the learner to apply the concept here, with a way to check the result.]

---

## Current Landscape

How this concept is implemented in practice:

| Tool/Approach | Description | When to Use |
|---------------|-------------|-------------|
| [Tool 1] | [What it does] | [Use case] |
| [Tool 2] | [What it does] | [Use case] |

---

## Best Practices

What good looks like:

1. **[Practice 1]** - [Explanation]
2. **[Practice 2]** - [Explanation]
3. **[Practice 3]** - [Explanation]

---

## Anti-Patterns

What to avoid:

| Anti-Pattern | Why It's Bad | Better Approach |
|--------------|--------------|-----------------|
| [Pattern 1] | [Problem] | [Solution] |
| [Pattern 2] | [Problem] | [Solution] |

---

## Did You Know?

- **[Fact 1]**: [Verified detail with real numbers and supporting source]
- **[Fact 2]**: [Verified detail with real numbers and supporting source]
- **[Fact 3]**: [Verified detail with real numbers and supporting source]
- **[Fact 4]**: [Verified detail with real numbers and supporting source]

---

## Common Mistakes

[Complete this table with 6–8 distinct mistakes and concrete fixes.]

| Mistake | Problem | Solution |
|---------|---------|----------|
| [Mistake 1] | [Impact] | [Fix] |

---

## Quiz

[6–8 scenario-based questions with explanatory hidden answers]

---

## Hands-On Exercise

[Practical exercise with verification]

---

## Further Reading

Books, talks, and papers for deeper understanding:

- **[Book/Resource]** - [Why it's valuable]
- **[Talk/Video]** - [Key takeaway]
- **[Paper/Article]** - [What you'll learn]

---

## Sources

[Replace all three placeholders with verified primary/vendor documentation citations; inline citations elsewhere do not replace this section.]

- [Primary/vendor source 1 title](PRIMARY_VENDOR_URL_1)
- [Primary/vendor source 2 title](PRIMARY_VENDOR_URL_2)
- [Primary/vendor source 3 title](PRIMARY_VENDOR_URL_3)

## Next Module

[Link to next module]
````

---
