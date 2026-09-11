---
name: platform-expert
description: Shape and verify KubeDojo platform curriculum around practitioner decisions and the Foundations, Disciplines, and Toolkits tracks. Use for platform lesson content and curriculum placement, not incidental mentions of platform tools.
---

# Platform Curriculum Expert

Use alongside the module authoring or review contract when teaching platform engineering. Place the topic in `src/content/docs/platform/` and inspect the relevant index for current coverage; module counts and tool catalogs change.

## Three teaching layers

- **Foundations** explain principles such as systems thinking, reliability, observability, security, and distributed systems.
- **Disciplines** teach applied practices and decision-making: SRE, platform engineering, GitOps, DevSecOps, MLOps, AIOps, release engineering, chaos engineering, FinOps, data engineering, advanced networking, AI/GPU infrastructure, and engineering leadership.
- **Toolkits** teach a concrete implementation in the context of those principles. Verify current capabilities and examples against the tool's official documentation.

## Discipline-specific emphasis

| Discipline | Decisions and distinctions to teach |
|------------|------------------------------------|
| SRE | Distinguish SLIs, SLOs, and SLAs; define measurement windows and denominators for error budgets; connect toil, capacity, and incident practices to reliability decisions. |
| Platform engineering | Connect self-service and golden paths to developer needs; distinguish infrastructure, platform services, and developer interfaces; state assumptions behind maturity models and metrics such as SPACE. |
| GitOps | Explain declarative state, versioning, automatic pull, and continuous reconciliation; compare tools against the lesson's actual operating requirements. |
| DevSecOps | Connect source, build, test, deploy, and runtime controls; distinguish SBOM inventory, signing, provenance, admission, and runtime enforcement. |
| MLOps | Connect data, features, training, validation, serving, monitoring, and retraining; distinguish data, concept, and prediction drift. |

Explain principles before tools. Compare approaches through concrete tradeoffs and failure modes; avoid treating one architecture, SLA/SLO relationship, budget policy, or maturity ladder as universal. For numerical examples, state assumptions (including the time window) and verify calculations.

## Module contract

Platform modules include Current Landscape, Best Practices, Anti-Patterns, and Further Reading in addition to the shared requirements in [curriculum-writer](../curriculum-writer/SKILL.md). Use [module-quality-reviewer](../module-quality-reviewer/SKILL.md) for the eight-dimension scoring contract. Recommendations and version-dependent claims need current primary-source evidence; do not expand a curriculum assignment into production architecture changes.
