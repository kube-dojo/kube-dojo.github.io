---
name: curriculum-writer
description: Create, expand, or rewrite KubeDojo curriculum modules, including their theory, exercises, and quizzes. Use for learner-facing module authoring, not general documentation or agent routing.
---

# Curriculum Writer

Write modules under `src/content/docs/` that teach the assigned topic and satisfy the repository's content contract. Provider selection and dispatch belong to the accountable lead and current repository policy.

## Content contract

- Read `docs/quality-rubric.md` from the repository root. Target all eight dimensions: sum ≥ 33/40 and every dimension ≥ 4.
- Preserve density gates enforced by `scripts/quality/verify_module.py`: median words per paragraph ≥ 28, mean ≥ 30, and paragraphs under 18 words ≤ 20%. Meet these through connected explanations, not padding.
- Include `title:` and `sidebar.order:` frontmatter. Filenames with dots require an explicit `slug:` preserving those dots.
- Use `module-X.Y-topic-name.md` filenames and add new modules to the parent `index.md` table. Internal learner links use published slugs ending in `/`, never `.md`; link prerequisites to specific modules.
- Include measurable learning outcomes, practical motivation, connected core sections, at least two inline active-learning prompts, four verified Did You Know facts, a 6–8-row Common Mistakes table, 6–8 scenario-based quiz questions with explanatory `<details>` answers, a hands-on exercise with success criteria and verification, and a Next Module link. These are the stricter shipping counts in [module-quality-reviewer](../module-quality-reviewer/SKILL.md).
- Include a `## Sources` section immediately before `## Next Module`, with at least three primary/vendor documentation citations. The verifier counts links in that section only; inline citations alone do not satisfy it.
- Mark complexity as `[QUICK]`, `[MEDIUM]`, or `[COMPLEX]`; state completion time and prerequisites. Scale practitioner depth to that complexity using D8 in the rubric.

## Evidence and teaching

Verify external facts against sources; remove unsupported claims. A real incident needs a citation or `Source:` line. Otherwise explicitly label a `Hypothetical scenario:` or `Simulation:` and state what is simulated. Do not invent incident details, dialogue, metrics, or outcomes. Analogies are optional: explain their mapping and limits when useful. Do not force mystery, gamification, or interview/job/role narratives.

Code examples must be complete and runnable, use realistic names, and include verification. Label output observed only after a recorded run; otherwise label it expected, illustrative, or simulated. Check equations and their assumptions. Verify version-dependent behavior and deprecations against official documentation.

Teach principles through connected prose and practical decisions. Use focused ASCII architecture diagrams and visuals for complex concepts. Quiz answers must explain why, rather than only name a command.

## Track guidance

Read [module-templates.md](module-templates.md) when drafting a new module or restructuring one; load only the applicable track section. Its templates illustrate layout, while the content contract above sets shipping counts.

- Certification modules align with the official CNCF curriculum and emphasize time-boxed hands-on practice; use [k8s-cert-expert](../k8s-cert-expert/SKILL.md) for exam alignment.
- Prerequisites assume no prior topic knowledge and build foundations for later certifications.
- Platform modules explain principles before tools across Foundations → Disciplines → Toolkits. Include Current Landscape, Best Practices, Anti-Patterns, and Further Reading; use [platform-expert](../platform-expert/SKILL.md) for track placement.

## Validation and references

Run `.venv/bin/python scripts/quality/verify_module.py <path>`. Test executable examples in an appropriate isolated environment; report unavailable dependencies rather than implying a run. Follow repository rules for `npm run build` (zero warnings) and `.venv/bin/python scripts/check_site_health.py` (zero errors), including the primary-checkout build constraint.

Read repository-root `docs/pedagogical-framework.md` for pedagogical detail and `scripts/prompts/module-writer.md` for the standard writing prompt when relevant. The lead owns cross-family review and publication under current repository policy; this skill does not authorize dispatch, PR creation, or merge.
