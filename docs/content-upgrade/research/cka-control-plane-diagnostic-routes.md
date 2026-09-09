# CKA control-plane diagnostics: API and local runtime routes

Issue #2338; parent #2280; epic #2272. Source draft for a bounded Module 5.3 diagnostic-routing packet. This does not accept runtime execution, certificate renewal or etcd restore.

## Inspected official sources

Retrieved 2026-09-09 at 22:32:53 UTC; retained bodies and receipt are under `.agent/cka-control-diagnostics-sources/`. HTML hashes identify the retrieved versioned documentation snapshot.

| Source and locator | Bytes | SHA256 |
|---|---:|---|
| [Kubernetes 1.35 crictl guide](https://v1-35.docs.kubernetes.io/docs/tasks/debug/debug-cluster/crictl/): Before you begin, Installing crictl, General usage, List containers, Get a container's logs | 495591 | `51481e918fbacf7b451eb541f77906380e8abc5506feb2acf2a4f51d69bc35cf` |
| [Kubernetes 1.35 API health endpoints](https://v1-35.docs.kubernetes.io/docs/reference/using-api/health-checks/#api-endpoints-for-health): endpoint meaning, HTTP status and verbose output | 490249 | `c5315a96780929ed56532e48f770d481fb04460f84cb463a26544ce7755a4421` |
| [cri-tools v1.35.0 crictl documentation](https://github.com/kubernetes-sigs/cri-tools/blob/v1.35.0/docs/crictl.md): Usage, endpoint configuration and Additional options | 20453 | `8527062eec094287c7a28b611e4b8590960c7d59d222ce8f6bb5def04d5ee86d` |

## Supported interpretation and design boundary

- `/livez` concerns API-server liveness; `/readyz` concerns readiness to accept traffic. HTTP 200 indicates success for the requested endpoint. Readiness failure can reflect initialization or an unavailable dependency; it is not interchangeable with liveness failure or proof that restart is the right intervention.
- Machines should use HTTP status; `?verbose` and individual check details are human diagnostic aids, not a stable machine-parsing contract. Failure to connect or authenticate is not itself an observed failing health-check response. API health does not prove scheduler, controller or workload recovery.
- The Kubernetes guide requires Linux with a CRI runtime and recommends a crictl release corresponding to Kubernetes. Bind the known runtime endpoint explicitly rather than relying on fallback socket probing. The tagged cri-tools document distinguishes `--version` (client information) from `version` (runtime information) and documents endpoint and connection-timeout flags.
- `ps` lists containers and `logs` reads a selected container's logs. A proposed helper must refuse an empty or malformed listing, empty/malformed selected ID, and an ID absent from the validated component-specific listing before requesting logs. Selection must be explicit and tied to the intended component and incident evidence. These refusal rules are implementation design, not a complete algorithm supplied by these sources.
- Do not infer that the last `ps` row is the newest attempt. This packet establishes no exact timestamp-ordering algorithm, universal container-ID format, or guarantee that a listed container remains available for the subsequent log request; failures must remain visible.

## Execution and follow-up boundary

The lead reports Kubernetes 1.35 on the existing pinned kind fixture but installed crictl 1.33. No version-matched runtime execution is accepted here; the mismatch does not itself prove incompatibility. Verify the actual client, runtime endpoint and fixture identity before a dedicated execution packet.

The lead has retained an official crictl v1.35.0 Linux arm64 archive and reports checking its published SHA256; it has not been executed or installed. Proposed provisioning stages that tool in a unique owned temporary node directory and removes only that directory afterward, preserving the installed 1.33 binary, manifests, certificates and namespace identities. Provisioning and cleanup still require execution evidence.

The later prose packet must remain within 200 aggregate changed lines, preserve all ten diagrams and the entire accepted scheduler Task 4, and distinguish API requests from local Linux runtime inspection. Require a real positive container-list/selection/log path plus separately labelled synthetic empty-list, malformed-response and wrong-ID refusal cases. Synthetic responses demonstrate guards, not actual runtime outages or recovery.

Root owns independent review and release. Certificate and etcd practical recovery, broader module acceptance, hosted companion fidelity and Ukrainian parity remain separate. Source support and the existing scheduler experiment cannot substitute for the new diagnostic route's execution evidence.
