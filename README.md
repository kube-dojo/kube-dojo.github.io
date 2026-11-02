# KubeDojo

**Free, comprehensive cloud native education — from Zero to Production.**

Terminal basics → Linux → Kubernetes certifications → Cloud → Platform engineering → On-prem → AI & AI/ML engineering.

No paywalls. No upsells. Theory-first, hands-on always.

**🌐 Live site: [kube-dojo.github.io](https://kube-dojo.github.io/)** · [What's New / Changelog](https://kube-dojo.github.io/changelog/)

---

## 🇺🇦 Присвята

*Цей проєкт присвячується українським ІТ-інженерам, які віддали своє життя, захищаючи Батьківщину.*

*Вони були розробниками, DevOps-інженерами, системними адміністраторами. Вони будували системи, писали код, підтримували інфраструктуру. Коли прийшла війна, вони залишили клавіатури й взяли зброю.*

*Їхній код живе. Їхня жертва — вічна. Слава Україні.*

### Заповіт
*Тарас Шевченко, 1845*

> Як умру, то поховайте  
> Мене на могилі,  
> Серед степу широкого,  
> На Вкраїні милій,  
> Щоб лани широкополі,  
> І Дніпро, і кручі  
> Було видно, було чути,  
> Як реве ревучий.
>
> Як понесе з України  
> У синєє море  
> Кров ворожу... отойді я  
> І лани і гори —  
> Все покину і полину  
> До самого Бога  
> Молитися... а до того  
> Я не знаю Бога.
>
> Поховайте та вставайте,  
> Кайдани порвіте  
> І вражою злою кров'ю  
> Волю окропіте.  
> І мене в сем'ї великій,  
> В сем'ї вольній, новій,  
> Не забудьте пом'янути  
> Незлим тихим словом.

---

## Learning Tracks

Eight structured tracks — **824 modules** — from absolute beginner to production systems, AI literacy, private infrastructure, and AI/ML engineering.

| Track | Modules | Est. time | What it covers |
|-------|--------:|-----------|----------------|
| [Fundamentals](https://kube-dojo.github.io/prerequisites/) | 44 | ~55h | Zero to Terminal, Cloud Native 101, Kubernetes Basics. **Start here if you're new.** |
| [Linux](https://kube-dojo.github.io/linux/) | 37 | ~50h | Everyday Use + Deep Dive — basic commands to kernel internals. |
| [Cloud](https://kube-dojo.github.io/cloud/) | 92 | ~130h | AWS / GCP / Azure essentials, EKS/GKE/AKS deep dives, architecture patterns. |
| [Certifications](https://kube-dojo.github.io/k8s/) | 195 | ~250h | CKA, CKAD, CKS, KCNA, KCSA + specialist & platform learning paths. |
| [Platform Engineering](https://kube-dojo.github.io/platform/) | 241 | ~320h | SRE, GitOps, DevSecOps, MLOps, FinOps, Chaos Engineering + toolkits. |
| [On-Premises](https://kube-dojo.github.io/on-premises/) | 57 | ~80h | Bare-metal Kubernetes from rack to cluster — networking, storage, ops. |
| [AI](https://kube-dojo.github.io/ai/) | 37 | ~80h | AI foundations, prompting, verification, privacy, AI-native work from zero. |
| [AI/ML Engineering](https://kube-dojo.github.io/ai-ml-engineering/) | 121 | ~160h | Local-first AI, RAG, MLOps, inference, fine-tuning, AI platform paths. |

> **🌐 Translations — work in progress.** A Ukrainian translation exists for part of the curriculum (~40%: Prerequisites, CKA, CKAD), but it is **incomplete and currently lags the English content** — recent English module rewrites have not yet been re-translated. Treat the English curriculum as the source of truth; the Ukrainian pages are deferred until the English is production-ready. Browse what exists at [kube-dojo.github.io/uk/](https://kube-dojo.github.io/uk/).

---

## Recommended Path

Not sure where to start? Follow this progression:

```
  Fundamentals  ─▶  CKA  ─▶  CKAD + CKS  ─▶  Cloud / AI / AI-ML  ─▶  Platform Eng  ─▶  On-Prem / Specialize
   (44 mods)       (41)       (54)            (92 / 37 / 121)          (241)              (57+)
```

---

## Where to Start

| You are... | Start here |
|------------|------------|
| Never used a terminal before | [Zero to Terminal](https://kube-dojo.github.io/prerequisites/zero-to-terminal/) |
| New to containers / K8s | [Prerequisites](https://kube-dojo.github.io/prerequisites/) |
| Want K8s admin certification | [CKA](https://kube-dojo.github.io/k8s/cka/) |
| Want K8s developer certification | [CKAD](https://kube-dojo.github.io/k8s/ckad/) |
| Want K8s security certification | [CKS](https://kube-dojo.github.io/k8s/cks/) |
| Entry-level K8s cert | [KCNA](https://kube-dojo.github.io/k8s/kcna/) or [KCSA](https://kube-dojo.github.io/k8s/kcsa/) |
| Platform engineer | [CNPE Learning Path](https://kube-dojo.github.io/k8s/cnpe/) |
| Multi-cloud Kubernetes | [Cloud Track](https://kube-dojo.github.io/cloud/) |
| Need AI literacy from zero | [AI](https://kube-dojo.github.io/ai/) |
| Building AI systems / local-first ML | [AI/ML Engineering](https://kube-dojo.github.io/ai-ml-engineering/) |
| Running K8s on bare metal | [On-Premises](https://kube-dojo.github.io/on-premises/) |
| Already certified, want depth | [Platform Engineering](https://kube-dojo.github.io/platform/) |

---

## Why This Exists

A free, text-based curriculum for learning Kubernetes, cloud native, and platform engineering.

- **Free** — No paywalls, open source.
- **Theory-first** — Understand principles before tools. You can't troubleshoot what you don't understand.
- **Text-based** — Searchable, version-controlled, no videos.

**What we are not:** a replacement for paid courses like KodeKloud or Udemy. We don't ship video lessons. For realistic exam simulation, use [killer.sh](https://killer.sh). For interactive in-browser labs, use [killercoda.com](https://killercoda.com).

---

## Philosophy

**Theory before hands-on.** You can't troubleshoot what you don't understand.

**No memorization.** K8s docs are available during exams — we teach navigation, not YAML memorization.

**Principles over tools.** Tools change. Foundations don't. Learn both, in that order.

---

## Tech Stack

The site is built with [Astro](https://astro.build/) + [Starlight](https://starlight.astro.build/) and deployed to GitHub Pages. Content is authored in Markdown under `src/content/docs/`.

```bash
npm install
npm run build      # build the static site to dist/
npx astro dev      # local dev server with hot reload
```

---

## Contributing

**What we welcome:**
- **Hands-on exercises** — real scenarios, not toy examples.
- **War stories** — production incidents that teach a lesson (must cite a real, verifiable source; each incident is told once across the curriculum).
- **Tool expertise** — deep-dives on ArgoCD, Prometheus, Vault, Cilium, etc.
- **Error fixes** — typos, outdated commands, broken YAML, dead links.

**What we don't build:**
- Exam simulators — use [killer.sh](https://killer.sh).
- Video content — text-first, searchable, version-controlled.

**How to contribute:**
- Open an issue to discuss before large PRs.
- Follow the existing module structure.
- Test all commands and YAML before submitting. For markdown-only content PRs the required CI job "Astro build (render + schema)" is the build gate, so no local full-site build is needed; run `npm run build` locally only for code, configuration, schema or Astro-layer changes.

---

## License

MIT License. Free to use, share, and modify.

---

*"In the dojo, everyone starts as a white belt. What matters is showing up to train."*
