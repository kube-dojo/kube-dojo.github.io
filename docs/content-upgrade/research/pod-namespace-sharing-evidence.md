# Linux Pod namespace sharing: source contract

Scope: English namespace lesson under #2418; IPC wording and the Kubernetes layout diagram. Inspected 2026-09-09. This is source evidence, not an executed lab or acceptance of the whole lesson. Ukrainian authoring is deferred under the English-first sequence.

## Inspected primary sources

| Source and locator | Supported claim | Boundary |
|---|---|---|
| [Kubernetes v1.35 Pods, Pod networking](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/#pod-networking) | Same-Pod containers share network/IP/ports and can communicate through OS-level IPC; they see the same configured Pod hostname. | Same hostname is an observable promise, not proof of a particular UTS implementation. Do not infer unrestricted cross-Pod IPC. |
| [Kubernetes v1.35 process-sharing task, Configure a Pod and Understanding process namespace sharing](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/) | `spec.shareProcessNamespace: true` enables cross-container process visibility within the Pod. | Shared visibility has security consequences; it does not imply shared root filesystems. The sample's additional debugging capability is not needed merely to compare namespace identities. |
| [Kubernetes v1.35 Pod Security Standards, Baseline table: Host Namespaces](https://v1-35.docs.kubernetes.io/docs/concepts/security/pod-security-standards/#baseline) | `hostNetwork`, `hostPID`, and `hostIPC` are host-namespace controls; the Baseline policy permits only unset/false values. | A policy restriction is not a lab result or proof that a particular cluster enforces it. No host-namespace test is authorized or needed by this packet. |
| [Kubernetes v1.35.0 CRI API, NamespaceOption](https://github.com/kubernetes/kubernetes/blob/v1.35.0/staging/src/k8s.io/cri-api/pkg/apis/runtime/v1/api.proto) | Linux namespace options describe network and IPC as POD/NODE, with no Kubernetes container-scoped API mode. The PID comment explicitly distinguishes CRI's POD default from v1.PodSpec's CONTAINER default. | Inspect this release tag, not moving `master`. There is no UTS option in this message; that absence alone is not a universal statement about all runtimes. |

## Retained source bytes

The full bodies were fetched before accepting the claims above; only the named sections were used. Versioned documentation is a retrieved snapshot, not an immutable release artifact. SHA256 receipts:

- Pods HTML: `de03b817567b2bfc3e0a3344aef711f027e51af1771136ec7589f3a67d782ff1` (528778 bytes).
- Process-sharing HTML: `57af9a0c0e16c6366bbbe41dad3b563e1c2c07c54291a1479d118102f7ca80b6` (495632 bytes).
- Security Standards HTML: `803e7b2a07587faf118df51950a6112e26df0f2c03cff8a5a7679da7c69c133a` (508206 bytes).
- CRI proto: `a1ac3e1b238569cee4f5e65cbd826c6fe316fe4721d1d45a8b6c1fbe435de7aa` (86324 bytes).

## Implementation and execution boundary

After independent SOURCE review, replace the vague IPC caveat with ordinary Linux Pod sharing and explicit host-namespace exceptions. Label the diagram's hostname behavior without promising a UTS implementation. Preserve default separate PID namespaces and the explicit sharing option. Scope any runtime observation to the measured environment.

Validate two owned two-container Pods, default and `shareProcessNamespace: true`, on a disposable Linux Kubernetes environment. Record versions, image identities, namespace identities and hostnames from both containers; compare expected network/IPC sharing and default-versus-shared PID behavior. Record UTS identities only as observations. Do not use host namespace overrides, privileged containers, or the user's unrelated namespaces. UID-bound cleanup and confirmed namespace absence are required. These checks do not exercise every IPC primitive or establish cross-runtime portability.

Independent PROSE review, applicable tests/build/render/CI, and deployed verification remain separate from this source contract. Existing mount/network/shared-volume receipts must not be promoted into IPC/PID evidence.
