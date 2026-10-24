# Full-page re-review: beginner Kubernetes

Reviewed 2026-10-24 at `b61061d6385bd706557dbd1ddd78ba7055d1412c`; owner #2278, source/assessment #2275/#2277, correction #3534. Reviewer: read-only OpenAI Astra high red-team profile; this is same-provider dissent, not independent-provider acceptance. All four entire pages were read. Root verified the recorded digests and independently checked the rollout/Docker source counterexamples. All findings remain open at this reviewed revision.

Paths below are relative to `src/content/docs/`; line numbers refer only to that pinned revision.

| Alias | Page | SHA256 |
|---|---|---|
| D | `prerequisites/kubernetes-basics/module-1.4-deployments.md` | `d5977c04abb93c2eca97f2887ad0ddda6905fb4e4a8b88ed817eaf48780d9ab4` |
| DH | `prerequisites/kubernetes-basics/index.md` | `126657702c4edcdb57da5d271f5c8683c138f738afc5016a1b0377f0fb85a6e1` |
| K | `prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md` | `47285e0d3faec08625e2ce98e04cb062f140e6cc3f8498028e8077b4bd7ab49f` |
| KH | `prerequisites/cloud-native-101/index.md` | `20590bed564a3d4dee532682c5de6b2ba513494e93300e601f1c9ed22867e644` |

## Findings and required corrections

Unless qualified below, findings are P2/high confidence. These are current-page defects outside the earlier bounded repair, not a reversal of its recorded execution.

| ID / location | Current evidence and failure | Correction / source verdict |
|---|---|---|
| 1 · D33/64/359, D45 | A memory leak “kills that Pod”; naked-Pod “crash” needs manual recreation; Deployment retry/backoff is associated with application crashes | Distinguish kubelet container restart from controller Pod replacement; controller workqueue handles synchronization errors. Unsupported as stated: [Pod restarts](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-restarts), [v1.35 controller handleErr](https://github.com/kubernetes/kubernetes/blob/v1.35.0/pkg/controller/deployment/deployment_controller.go#L470-L488). |
| 2 · D58/279 | “zero downtime”, resources “for up to 13”, “at least 8 available Pods throughout” | Qualify rollout constraints, unrelated failures and terminating-Pod resource use. Partial: [updating a Deployment, terminating-Pod note](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/#updating-a-deployment). |
| 3 · D421 | “Every template update creates a new ReplicaSet” | A retained matching ReplicaSet can be reused; qualify paused updates. Unsupported universal: [getNewReplicaSet](https://github.com/kubernetes/kubernetes/blob/v1.35.0/pkg/controller/deployment/sync.go#L128-L177). |
| 4 · D294/404 | Recreate presented for single-writer safety / “never running two versions at once” | Limit the guarantee to upgrades; deletion/replacement can overlap termination. Partial: [Recreate note](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/#recreate-deployment). |
| 5 · D89/92/200/206; K530/555 | Duplicate ambient `nginx` creation and Pod deletion outside the guarded lab; `hello` deletion can follow failed creation of an existing object | Add explicit disposable context/namespace ownership, fail-closed setup and owned cleanup; distinguish alternative examples. Static counterexample, not an observed cluster failure. |
| 6 · K52/349/352 | Docker self-healing “No”, service discovery “Manual” | Docker restart policies and Compose DNS are counterexamples; distinguish local recovery from cross-node orchestration. Unsupported: [restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/#use-a-restart-policy), [Compose discovery](https://docs.docker.com/compose/how-tos/networking/#default-network-and-service-discovery). |
| 7 · K100–105 | Laptop cannot reach API; answer says fresh scheduling waits | Separate client isolation from actual control-plane unavailability. Partial: [component responsibilities](https://kubernetes.io/docs/concepts/overview/components/#control-plane-components). Preserve useful Card A distinction. |
| 8 · K84/314–325 | Control plane restarts failed containers; `deploy.yaml` request jumps directly to unassigned Pod | Assign restart to kubelet and depict Deployment/ReplicaSet reconciliation before scheduling. Partial: [components](https://kubernetes.io/docs/concepts/overview/components/), [Deployment sync](https://github.com/kubernetes/kubernetes/blob/v1.35.0/pkg/controller/deployment/sync.go#L183). |
| 9 · K452; D388 | Pending “usually means” no node assignment | Check node assignment/PodScheduled, then images, volumes and initialization. Pending includes assigned Pods. Partial: [Pod phase](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase). |
| 10 · K370/387 | Customers manage node pools and choose sizes | Scope by managed-service mode; Autopilot is a counterexample. Partial: [Autopilot overview](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview#what_is_autopilot). |
| 11 · K426/427 | CNCF “joined … in 2015”; unnamed “15,000 nodes and 300,000 or more pods” report | Reconcile donation/founding announcement versus hosted-project chronology; remove or source exact deployment/scale. Scale claim unknown, not disproven: [anniversary history](https://kubernetes.io/blog/2024/06/06/10-years-of-kubernetes/), [CNCF journey report](https://www.cncf.io/reports/kubernetes-project-journey-report/). |
| 12 · K12/483/575; D77/671–703; K258 | No-experience promise assumes a cluster; invented cards called “transcripts”; editorial annotations distract and cards disclose causes | Link bootstrap, label synthetic scenarios, replace metadata-like prose with direct prompts and use an unfamiliar mixed-symptom task. Editorial/source gap; P3/high confidence. |
| H1 · DH19 | “ensuring high availability” | Describe maintaining replicas/managing rollouts subject to readiness/capacity; bounded hub revision. |
| H2 · KH7/11 | “Gone are the days…” / orchestration “necessary at scale” | Preserve legitimate simpler deployment choices and the module's existing tradeoffs; bounded hub revision. |

All primary-source locators above were checked 2026-10-24 with Kubernetes implementation claims pinned to 1.35. These cover twelve load-bearing checks, not every material assertion. The 25% surge/unavailable defaults and 600-second progress deadline were supported by the versioned Deployment documentation; preserve those facts.

## Disposition and limits

**Revise D, DH, K and KH.** Both modules pass enabled structural gates with URL probes skipped (14/13 URLs). All 26 Bash fences syntax-check and seven YAML snippets parse; all thirteen hub module targets exist. Planning-time arithmetic is correct: 600–860 and 450–600 minutes. These checks do not establish runtime success or source completeness.

Retain the [#2306 lab repair](https://github.com/kube-dojo/kube-dojo.github.io/pull/2306) and [#2297 closure evidence](https://github.com/kube-dojo/kube-dojo.github.io/issues/2297#issuecomment-5547080489): dedicated kind/kubectl1.35 execution, actual failed-rollout diagnosis, rollback/readiness/cleanup, independent Gemini review and publication smoke for that revision. The surrounding claims and earlier unguarded examples were not thereby accepted.

D1–D8 remain **unassessed** because the full citation gate is unresolved. No current cluster execution, full-page rendered smoke, translation-fidelity review or learner study occurred in this review. Local coordination API `/api/module/{key}/state` snapshots for D/K report missing fact ledgers and stale Ukrainian counterparts; these are metadata diagnostics, not fidelity verdicts. Required next step: repair findings coherently in #3534, independently review the changed head, then record exact remaining source/lab/translation coverage instead of promoting the whole module from a green build.
