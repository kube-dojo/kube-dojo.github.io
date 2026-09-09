# CKA application failures: owned Pods and OOM evidence

Issue #2337; parent #2280; epic #2272. Scope: Scenarios 1, 2 and 4 in `module-5.2-application-failures.md`. Scenario 3 was separately delivered in #2376 and must remain byte-identical. This card supports a proposed ownership packet and a later OOM workload packet; it does not accept execution or the whole module.

## Sources inspected

Retrieved September 9, 2026. Bodies and the retrieval receipt are retained privately under `.agent/cka-application-sources/`. The mutable image catalog is a retrieved snapshot; its architecture declarations are not fixture execution proof.

| Body | Official locator | Bytes | SHA256 |
|---|---|---:|---|
| Kubernetes 1.35 memory exercise | [Assign Memory Resources](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/#exceed-a-container-s-memory-limit), exceeding a limit and termination status | 519694 | `d556f450a1d14eff9f2103ee50630999dbfa9d3620beb46e635f72ed65f2fdb9` |
| Python 3.12 built-ins | [bytearray](https://docs.python.org/3.12/library/functions.html#func-bytearray), integer source argument | 298516 | `6fc45db13e6c5b1aa6c1116dd4d79e6deec71dd58e91fdced4dcb6d6cf16390e` |
| Official Python image catalog | [library/python](https://github.com/docker-library/official-images/blob/master/library/python), `3.12-alpine` tag group | 10263 | `d32af55168fbf58179b22f152f0927b67f832f472a9eabcc20a8930cac144fb4` |

The accepted [methodology ownership card](cka-methodology-ownership-evidence.md) supplies the already-inspected Kubernetes 1.35 CLI target flags and API UID/delete-precondition sources. Reusing that design requires module-specific names, fresh creation receipts and new integration tests; the earlier execution does not validate these scenarios.

## Supported claims and design limits

- Kubernetes documents a memory-limit exercise and checking the terminated container's `OOMKilled` reason. A sampled Running/Ready status can precede failure; exit code 137 alone does not establish OOM. The upstream example also uses `polinux/stress`, but that is not evidence that its image runs on this fixture's architecture.
- Python's `bytearray(integer)` produces a mutable array of that size initialized to zero. A candidate retained 500 MiB allocation with explicit writes at 4 KiB intervals is an experiment design, not a guarantee of Linux resident-memory accounting. Actual terminated state and corrected-workload observations remain required. Avoid a same-size temporary bytes object that would change the peak allocation.
- The retrieved catalog declares `3.12-alpine` for amd64 and arm64v8 among other architectures, with build source commit `688a0b86bb44289df16a363e9f41d90514c1a5f9` and directory `3.12/alpine3.24`. This does not prove registry availability, the pulled digest, successful allocation, or other-platform execution.
- Corrected Pods should be created under distinct names in the newly owned namespace, leaving the failed Pods available for comparison until explicit cleanup. Do not overwrite learner YAML or force-replace a Pod. This is a teaching design; it is not in-place repair of an immutable Pod field or a general production recommendation to raise limits.

## Proposed bounded sequence

1. Ownership and additive repairs: module-specific explicit-fixture helpers, successful-create UID receipt, target refusal, unique namespace, no local manifest rewrites, and UID-preconditioned cleanup for Scenarios 1/2/4. Keep Scenario 3 unchanged. Aim for at most 200 aggregate lines; split before exceeding the limit. Observe ownership/refusal/error/reconciliation behavior and identify any unverified workload outcomes explicitly.
2. OOM workload and evidence: independently review the exact candidate, then run it only on the dedicated Kubernetes 1.35 fixture. Require observed `OOMKilled` for the failing limit, an allocation-complete marker for the corrected Pod, and a bounded stable-running/restart observation. Record image digest, architecture, node capacity and cleanup. Retaining both Pods adds to capacity requirements. A brief successful run is not long-term stability or cross-runtime portability.

Neither source acceptance nor a configured manifest substitutes for actual fault, diagnostic, repair and cleanup evidence. Wider outcomes, timing, unqualified examples, probe tools, hosted companion fidelity and Ukrainian parity remain separate #2337/#2280 scope.
