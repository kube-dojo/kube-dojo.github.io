# CKA application diagnostics: targets and container tools

Issue #2337; parent #2280; epic #2272. This card supports a separate correction to generic diagnostic examples and the probe-tool explanation in Module 5.2. It does not accept a new probe-failure exercise or expand the four guided labs.

## Sources inspected

Retrieved September 9, 2026; bodies and receipt retained under `.agent/cka-app-tools-sources/`.

| Body | Official locator | Bytes | SHA256 |
|---|---|---:|---|
| Kubernetes 1.35 kubectl exec | [Options and inherited options](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl_exec/#options) | 491565 | `0a34efa2ec91f7fad39f7ddd8e150e533a84a366f43b0835fe08f3d8bcf4c253` |
| Kubernetes 1.35 probe exercise | [HTTP liveness probe](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-a-liveness-http-request) | 527767 | `60eaf0c20f7008fc6f9ec6d6543767da7319534f681b41d6bb37ea4bf4b2d7ff` |
| Kubernetes API v0.35.0 | [HTTPGetAction fields](https://github.com/kubernetes/api/blob/v0.35.0/core/v1/types.go), `Host`, `Port`, `Path`, `Scheme`, `HTTPHeaders` | 445653 | `3ce00ec375ddbab52daf76d30421b1065fa9bcf34fe5e0ef94dc14b8475d1506` |

`kubectl exec` accepts a namespace and a named container. Without `-c`, its default-container annotation or first-container selection can target a different container from the one being diagnosed. The existing accepted methodology ownership card supplies explicit kubeconfig/context targeting. Generic placeholder examples still require deliberate substitution and are not executable lab fixtures.

The probe exercise describes kubelet making the HTTP request. `HTTPGetAction` defaults its connection host to the Pod IP and separately specifies path, port, scheme and headers. A successful container-local loopback request does not prove that kubelet can reach that target or reproduce its configured request and timing. Tool existence is another prerequisite; do not equate an exec failure caused by a missing binary with an application health failure.

## Bounded fixture observation

On the dedicated Kubernetes 1.35.0 arm64 fixture, the lead created one fresh owned namespace and a Pod using `nginx:1.25`, then explicitly selected its namespace and `tool-inventory` container for inspection. Receipt: `.agent/cka-app-tools-execution/55e5e57a1fef472e8a5ecd0aa0597fa7/receipt.json`, September 9, 2026, 21:50:12–21:50:25 UTC. Pulled image: `docker.io/library/nginx@sha256:a484819eb60211f5299034ac80f6a681b06f89e65866ce91f356ed7c72af059c`; nginx reported version 1.25.5.

`command -v` found `/usr/bin/sh`, `/usr/bin/cat` and `/usr/bin/curl`; `wget` was unavailable on PATH. Curl returned HTTP 200 for `http://127.0.0.1:80/`. The accepted lesson setup and UID-preconditioned cleanup completed without fallback; the namespace UID inventory was preserved. The private inventory harness is `.agent/check-cka-app-tools.py`.

This establishes neither a universal nginx image inventory nor a `/health` handler on port 8080, `/tmp/healthy`, a configured probe, probe failure/recovery, kubelet-to-Pod connectivity, other architectures, or future tag contents. The tool inventory and default listener check are separate from learner-fence execution. Preserve the accepted four guided exercises unchanged.

Proposed prose packet: qualify namespaced diagnostic examples and container selection, label placeholders and required tools, replace the universal image claim with the bounded observation, and explain loopback versus kubelet HTTP checks. Keep each packet below 200 aggregate lines, with independent review and source/render validation; do not claim the generic placeholders all executed.
