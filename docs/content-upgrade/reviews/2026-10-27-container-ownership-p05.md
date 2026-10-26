# T01-P05: container lifecycle and Docker practice

Owner #2278; source/practice/assessment #2275/#2276/#2277. Checked 2026-10-27 from base `f186030407274e2e6ba71e854a6de71c8155cf68`. Terra completed the original hub (23 lines), 1.1 (606 lines) and 1.2 (918 lines); Astra authored scoped fixes and the lead integrated control-flow corrections. Both modules remain **revise**, D1–D8 unassessed. The existing hub record remains revise: its historical H2 finding is resolved, and 450–600 minutes is header arithmetic, not measured completion. Closed #2578 timing evidence is not body acceptance.

## Checked corrections

| Finding | Correction and selective support |
|---|---|
| Collision and broad cleanup | Leave existing containers untouched. Capture successful creation IDs, guard later operations and clear on failure. Same-shell/local-context/ownership checks remain human prerequisites, not ownership proof. [Docker removal](https://docs.docker.com/reference/cli/docker/container/rm/), force-removal section: force kills the running container; [ancestor filter](https://docs.docker.com/reference/cli/docker/container/ls/#ancestor) matches shared-image containers, not this learner's ownership. |
| Publication and ambient cluster | Explicit IPv4 loopback publication, matching repair/examples/Compose; Server/context and routing caveats. Kubernetes apply is a conceptual preview awaiting an authorized cluster lab. [Port publishing](https://docs.docker.com/engine/network/port-publishing/), default binding and localhost caveats. |
| Files and failed builds | Fresh guarded directories prevent later levels overwriting an earlier Dockerfile. Failed builds do not launch an old tagged image in the three worked blocks. Broad image removal/pruning is reference text. Choose unused names/tags; Compose project verification and volume deletion remain explicit human steps. |
| Storage assessment | Removing/replacing a container loses its writable layer; restarting the same container preserves it. [Storage drivers](https://docs.docker.com/engine/storage/drivers/#container-and-layers), container layers: deletion discards that layer; volumes have a separate lifecycle. |

The lead fetched and read these primary passages (ports also checked in P04). This is selective support, not a whole-page claim map or source/history acceptance. Existing explanations and learning outcomes are retained without a rewrite quota.

Independent R1 found that failed removal could fall through to recreation and erase the original ID; both retry blocks now require successful removal and preserve the original ID on failure. The remaining name-conflict instruction and host-curl explanation now match the ownership and IPv4 requirements; force-removal and cleanup-table wording are also aligned. Optional image-tag/manual-workspace and unrelated wording evidence remains with #2275/#2277.

## Evidence and remaining work

Nineteen ordinary macOS Bash cases passed: eight fresh/file/directory/symlink workspace cases, three failed-create ID guards, three failed-build paths and five removal/retry success/failure cases. Docker/curl are explicit function stubs; Bash syntax checks cover the guarded fences. They establish shell control and file preservation only, not Docker behavior, actual ownership, images, ports, containers, storage, Compose, cluster or documented-platform execution. Enabled structural checks pass with source reachability explicitly skipped. No daemon, install, service or hosted lab ran.

Complete source/assessment/rubric and real execution proof stay with #2275/#2277/#2276; the batch remains unchecked. Ukrainian counterparts stay #2291 obligations under English-first scheduling, with no Ukrainian acceptance. Exact-head independent review/CI, merged primary build and scoped publication checks remain delivery gates. Continue to P06 after delivery; do not promote these records or the hub to accepted.
