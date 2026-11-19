---
description: Rules for Ukrainian translation of KubeDojo modules
paths:
  - "src/content/docs/uk/**/*.md"
---

# Ukrainian Translation Rules

## File Convention
- Directory-based: translations live in `src/content/docs/uk/` mirroring the English structure
- English: `src/content/docs/k8s/cka/part1/module-1.1-foo.md`
- Ukrainian: `src/content/docs/uk/k8s/cka/part1/module-1.1-foo.md`
- Starlight i18n with `defaultLocale: 'root'`, Ukrainian at `/uk/` URLs

## Frontmatter
- Must include `title:` in Ukrainian
- Copy `slug:` and `sidebar.order` from English version
- Starlight falls back to English for untranslated pages automatically

## What to Translate
- All prose, explanations, section headers, table headers
- Quiz questions and answers
- ASCII diagram labels

## What to Keep in English
- All code blocks, YAML, bash commands
- Tool names: kubectl, Helm, ArgoCD, Terraform, etc.
- Comments inside code blocks

## Glossary (src/content/docs/glossary.md)
- Pod = Под, Deployment = Деплоймент, Service = Сервіс
- Namespace = Простір імен, cluster = кластер, container = контейнер
- control plane = площина управління, worker node = робочий вузол

## Quality Checks
- No Russicisms (ы, ё, ъ, э)
- Links: use same relative paths as English (Starlight resolves locale automatically)
