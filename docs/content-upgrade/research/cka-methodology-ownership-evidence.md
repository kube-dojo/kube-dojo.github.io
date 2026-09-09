# CKA methodology lab: ownership and command scope

Issue #2336; parent #2280; epic #2272. Scope: a first bounded repair to the hands-on exercise in `src/content/docs/k8s/cka/part5-troubleshooting/module-5.1-methodology.md`. This card supports command binding, namespace identity/deletion and the service-diagnosis locator. It does not accept the whole lesson, images, fault timing, source flags or learner outcomes.

## Inspected official sources

Retrieved September 9, 2026; retained bodies and a machine receipt are private execution artifacts. HTML byte identity records the retrieved snapshot, not a promise that the hosted page cannot change.

| Body | Versioned source and locator | Bytes | SHA256 |
|---|---|---:|---|
| kubectl reference | [Kubernetes 1.35 kubectl](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl/), Options: context, kubeconfig, namespace, request-timeout | 493233 | `24c96ba38dc0ea3c8787300a3408ba565e55f613526914207eeb531432d34229` |
| delete reference | [Kubernetes 1.35 kubectl delete](https://v1-35.docs.kubernetes.io/docs/reference/kubectl/generated/kubectl_delete/), Synopsis caveat and Options: raw, wait | 497105 | `5b12a8f0780f4d651d24163a69e5e5577bdd9d0e05afe29af2cef091addc26be` |
| API metadata types | [apimachinery v0.35.0 types.go](https://github.com/kubernetes/apimachinery/blob/v0.35.0/pkg/apis/meta/v1/types.go), ObjectMeta UID lines151–159; DeleteOptions Preconditions lines517–521; Preconditions lines748–755 | 84162 | `110ef0b67dda6c349a5c8abae421360ba0aa15702f2f0e04d320bfb2687785f2` |
| Service debugging | [Kubernetes 1.35 Debug Services](https://v1-35.docs.kubernetes.io/docs/tasks/debug/debug-application/debug-service/#does-the-service-have-any-endpointslices), selection, EndpointSlices and comparing Service selectors with Pod labels | 528480 | `6abb169545826bf63411e33283f51cd7fd52427b3fcadbe727334ec9daeb9e4b` |
| EndpointSlice label constant | [api v0.35.0 discovery/v1/well_known_labels.go](https://github.com/kubernetes/api/blob/v0.35.0/discovery/v1/well_known_labels.go), LabelServiceName | 1335 | `872c83e8d6818414fe0152f29159cbb382f7b67511000778cd12794c756fa9c7` |

## Claim dispositions

- `--kubeconfig`, `--context` and `--namespace` select the file, context and namespace scope for CLI requests. Explicit flags avoid reliance on a changing current-context setting. They do not establish that the selected cluster is disposable or make a mutable kubeconfig immutable. The fixture must be independently identified before mutation.
- Namespace ownership must come from the successful create response, never a later lookup of a pre-existing name. The API's object UID is server-generated identity that does not change through ordinary updates. Retaining that returned UID is an implementation design decision; the source does not provide a complete classroom helper or fault-tested workflow.
- `DeleteOptions.preconditions` must hold for deletion; an unmet condition produces HTTP409. `Preconditions.uid` selects target identity. Use it on cleanup rather than assuming an earlier name/UID comparison makes a later name-only delete safe. The kubectl delete reference documents raw DELETE transport and warns that ordinary deletion does not perform resource-version checks. The exact raw request body, wait, refusal and retry behavior must still be executed before release.
- The debugging guide describes EndpointSlice-backed Service selection and checking a Service's selector against Pod labels. Its example spells the filter `k8s.io/service-name`; that conflicts with the inspected API constant `kubernetes.io/service-name`. Retain the API spelling and verify actual EndpointSlice discovery. A label match alone is not proof of usable traffic or ready backends.

## Execution and release boundary

Use only the dedicated disposable Kubernetes 1.35 fixture and a unique namespace. Preserve existing resources, bind all exercise calls including nested and node reads, reject accidental helper target overrides, retain the creation UID for cleanup retries, and verify deletion without force-finalizer fallbacks. A small teaching helper is not a sandbox for arbitrary manifests or a defense against a privileged concurrent actor.

Required observed evidence: preflight refusal, missing/failed ownership receipt, setup retry/refusal, partial setup, ordinary target drift, helper overrides, namespace replacement, successful UID-guarded cleanup and cleanup failure/retry. Execute the exact learner command fences; record image identities, actual failure/diagnosis/repair/traffic observations and teardown. A lost create response means ownership is uncertain: report it for fixture-owner reconciliation rather than adopting or deleting by name. This card is source support, not execution proof, cross-runtime portability, whole-module acceptance or Ukrainian fidelity.
