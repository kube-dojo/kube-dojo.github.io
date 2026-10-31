---
name: curriculum-writer
description: Create, expand, or rewrite KubeDojo curriculum modules, including their theory, exercises, and quizzes. Use for learner-facing module authoring, not general documentation or agent routing.
---

# Curriculum Writer

Write modules under `src/content/docs/` that teach the assigned topic and satisfy the repository's content contract. Provider selection and dispatch belong to the accountable lead and current repository policy.

## Content contract

- Read `docs/review-contract.md` and `docs/quality-rubric.md` from the repository root. Target all eight module dimensions: sum ≥ 33/40 and every dimension ≥ 4.
- Before writing, record the audience and prerequisites, intended scope, essential topics, relevant primary sources and deliberate exclusions. Compare the topic inventory with the source basis and audience needs, not only the proposed outcomes.
- Map each outcome to actual teaching and appropriate practice and assessment. Shared examples and activities are welcome. Explain mechanisms, decisions, misconceptions and failure recovery as appropriate; use worked examples where they help.
- Word, density, source and template counts are diagnostics, not proof of adequate coverage. Do not pad, manufacture facts or force a number of activities. Explicit page-specific workload limits need a recorded rationale. During migration, the existing verifier may still enforce legacy counts; report its actual result and the conflict separately until #3744 lands.
- Include `title:` and `sidebar.order:` frontmatter. Filenames with dots require an explicit `slug:` preserving those dots.
- Use `module-X.Y-topic-name.md` filenames and add new modules to the parent `index.md` table. Internal learner links use published slugs ending in `/`, never `.md`; link prerequisites to specific modules.
- Include observable learning outcomes, practical motivation, connected explanations, suitable practice and assessment with explanatory feedback, and a Next Module link. Choose prompts, examples, quizzes, tables and exercises for the learning need; hands-on work needs success criteria and verification.
- Cite primary or authoritative sources sufficient to support material claims and the researched scope; record exact evidence and check the applicable citation requirements. The verifier currently counts links in the `## Sources` section, so report that legacy result honestly.
- Mark complexity as `[QUICK]`, `[MEDIUM]`, or `[COMPLEX]`; state completion time and prerequisites. Scale practitioner depth to that complexity using D8 in the rubric.

## Evidence and teaching

Verify external facts against sources; remove unsupported claims. A real incident needs a citation or `Source:` line. Otherwise explicitly label a `Hypothetical scenario:` or `Simulation:` and state what is simulated. Do not invent incident details, dialogue, metrics, or outcomes. Analogies are optional: explain their mapping and limits when useful. Do not force mystery, gamification, or interview/job/role narratives.

Code examples must be complete and runnable, use realistic names, and include verification. Label output observed only after a recorded run; otherwise label it expected, illustrative, or simulated. Check equations and their assumptions. Verify version-dependent behavior and deprecations against official documentation.

Teach principles through connected prose and practical decisions. Use focused ASCII architecture diagrams and visuals for complex concepts. Quiz answers must explain why, rather than only name a command.

## Track guidance

Read [module-templates.md](module-templates.md) when drafting a new module or restructuring one; load only the applicable track section. Templates illustrate possible layouts, not required quantities.

- Certification modules align with the official CNCF curriculum and emphasize time-boxed hands-on practice; use [k8s-cert-expert](../k8s-cert-expert/SKILL.md) for exam alignment.
- Prerequisites assume no prior topic knowledge and build foundations for later certifications.
- Platform modules explain principles before tools across Foundations → Disciplines → Toolkits. Include Current Landscape, Best Practices, Anti-Patterns, and Further Reading; use [platform-expert](../platform-expert/SKILL.md) for track placement.

## Validation and references

Run `.venv/bin/python scripts/quality/verify_module.py <path>`. Test executable examples in an appropriate isolated environment; report unavailable dependencies rather than implying a run. Follow repository rules for `npm run build` (zero warnings) and `.venv/bin/python scripts/check_site_health.py` (zero errors), including the primary-checkout build constraint.

Read repository-root `docs/pedagogical-framework.md` for pedagogical detail and `scripts/prompts/module-writer.md` for the standard writing prompt when relevant. The lead owns cross-family review and publication under current repository policy; this skill does not authorize dispatch, PR creation, or merge.
