# Per-minor Release Radar bundle template

Copy this structure into `src/content/docs/k8s/releases/v1.XX.md` for every new upstream minor (X06 / #2545).

```markdown
---
title: "Kubernetes 1.XX — <Theme>"
description: "Release Radar for Kubernetes 1.XX: Stable highlights, cert impact, and practice links."
sidebar:
  order: <newest=3, then increment>
  label: "1.XX <Theme>"
---

> **Cert impact:** `none` | `watch` | `bump-needed`
> **Upstream status:** Actively supported | Maintenance | EOL
> **GA:** YYYY-MM-DD · Theme: **Name**

## Who should read this
## Stable highlights (learner-visible)  # table: Theme | What | Why
## Removals / breaking                 # required if any
## Practice                            # kind image + 1–2 diff drills
## Agent checklist
## Sources                             # official blog, CHANGELOG, releases page; verification date
```

**Required:** official sources + verification date. **Forbidden:** rewriting cert tracks in the same PR; documenting every alpha as production guidance.
