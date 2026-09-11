---
title: "\u0413\u043b\u043e\u0441\u0430\u0440\u0456\u0439 KubeDojo / KubeDojo Glossary"
---
Стандартизований переклад технічних термінів Kubernetes українською мовою.

## Правила / Rules

1. **Команди і YAML** — завжди англійською: `kubectl`, `Pod`, `Deployment` (в коді)
2. **Пояснювальний текст** — українською: Под, Деплоймент, кластер
3. **Інструменти** — завжди англійською: kubectl, kubeadm, helm, kustomize, argocd
4. **Якщо невпевнені** — `<!-- VERIFY: термін -->`

## Kubernetes API об'єкти / API Objects

| English | Українською (в тексті) | В коді/YAML |
|---------|----------------------|-------------|
| Pod | Под | Pod |
| Deployment | Деплоймент | Deployment |
| Service | Сервіс | Service |
| Node | Нода / Вузол | Node |
| Namespace | Простір імен | Namespace |
| ConfigMap | ConfigMap | ConfigMap |
| Secret | Secret | Secret |
| StatefulSet | StatefulSet | StatefulSet |
| DaemonSet | DaemonSet | DaemonSet |
| ReplicaSet | ReplicaSet | ReplicaSet |
| Job | Job | Job |
| CronJob | CronJob | CronJob |
| Ingress | Інгрес | Ingress |
| PersistentVolume | Персистентний том | PersistentVolume |
| PersistentVolumeClaim | PVC | PersistentVolumeClaim |
| StorageClass | StorageClass | StorageClass |
| NetworkPolicy | Мережева політика | NetworkPolicy |
| ServiceAccount | Сервісний акаунт | ServiceAccount |
| ClusterRole | ClusterRole | ClusterRole |
| Role | Роль | Role |
| CustomResourceDefinition | CRD | CustomResourceDefinition |
| HorizontalPodAutoscaler | HPA | HorizontalPodAutoscaler |
| Gateway | Gateway | Gateway |
| HTTPRoute | HTTPRoute | HTTPRoute |

## Концепції / Concepts

| English | Українською |
|---------|------------|
| cluster | кластер |
| container | контейнер |
| control plane | площина управління |
| worker node | робочий вузол |
| high availability | висока доступність |
| load balancer | балансувальник навантаження |
| rollback | відкат |
| rollout | розгортання |
| scaling | масштабування |
| autoscaling | автомасштабування |
| scheduling | планування |
| orchestration | оркестрація |
| declarative | декларативний |
| imperative | імперативний |
| reconciliation | узгодження |
| self-healing | самовідновлення |
| idempotent | ідемпотентний |
| immutable | незмінний |
| ephemeral | ефемерний |
| observability | спостережуваність |
| monitoring | моніторинг |
| logging | логування |
| tracing | трейсинг |
| metrics | метрики |
| alerting | оповіщення |
| incident | інцидент |
| SLO | SLO (ціль рівня обслуговування, вимірюється через SLI) |
| SLA | SLA (угода про рівень обслуговування з наслідками за порушення) |
| error budget | бюджет помилок |
| GitOps | GitOps |
| CI/CD | CI/CD |
| infrastructure as code | інфраструктура як код |
| drift | дрейф конфігурації |
| policy | політика |
| admission controller | контролер допуску |
| RBAC | RBAC (рольовий контроль доступу) |
| mTLS | mTLS (взаємний TLS) |
| certificate | сертифікат |
| encryption | шифрування |
| vulnerability | вразливість |
| supply chain | ланцюг постачання |
| image | образ |
| registry | реєстр |
| runtime | середовище виконання |
| CNI | CNI (інтерфейс мережі контейнерів) |
| CSI | CSI (інтерфейс зберігання контейнерів) |
| CRI | CRI (інтерфейс середовища виконання контейнерів) |
| overlay network | оверлейна мережа |
| eBPF | eBPF |

## Фрази / Common Phrases

| English | Українською |
|---------|------------|
| Why This Module Matters | Чому цей модуль важливий |
| What You'll Learn | Що ви вивчите |
| Did You Know? | Чи знали ви? |
| Common Mistakes | Типові помилки |
| Hands-On Exercise | Практична вправа |
| Success Criteria | Критерії успіху |
| Next Module | Наступний модуль |
| Prerequisites | Передумови |
| Complexity | Складність |
| Time to Complete | Час на виконання |
| War Story | Бойова історія |
| The Analogy | Аналогія |
| Quiz | Тест |

## Джерела / Authority Hierarchy

1. **VESUM** (vesum.nlp.net.ua) — морфологічний словник
2. **Правопис 2019** — офіційний правопис
3. **Горох** (goroh.pp.ua) — наголоси, частотність
4. **e2u** (e2u.org.ua) — англо-український словник (331К статей, є IT-словник)
5. **r2u** (r2u.org.ua) — російсько-український (тільки для виявлення русизмів)
