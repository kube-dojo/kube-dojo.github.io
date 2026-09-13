---
description: Checklist before committing new modules or content changes
---

# New Content Checklist

EVERY TIME new modules are added, do ALL of these BEFORE committing:

1. **Frontmatter** — every `.md` file needs `title:` and `sidebar.order:`
2. **Slug** — if filename contains dots (e.g. `module-1.1-foo.md`), add explicit `slug:` to preserve them
3. **Parent index.md** — add module to section's index table
4. **Internal links** — use slug format (`module-foo/`), never `.md` extension
5. **Build** — `npm run build` — verify no errors
6. **Health check** — `python scripts/check_site_health.py` — 0 errors
7. **changelog.md** — add entry for significant additions
8. **K8s dual-track** — cert modules stay on `docs/pins/kubernetes.yaml` → `exam_pin`. New upstream minors go under `src/content/docs/k8s/releases/` per `docs/release-maintenance/kubernetes-minor-release-playbook.md`. Do not rewrite CKA/CKAD/CKS because kubernetes.io GA'd a minor.
