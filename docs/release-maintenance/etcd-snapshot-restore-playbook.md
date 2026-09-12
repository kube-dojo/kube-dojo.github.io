# Etcd snapshot restore — standing playbook (#2479)

AI-facing workflow. Human operators may follow the same steps. **No learner mutation recipe** until E2–E3 evidence is accepted on #2479.

## Pins

See [`docs/pins/etcd.yaml`](../pins/etcd.yaml). Reuse the disposable kind ownership pattern from the CKA certificate fixture (`scripts/cka_certificate_fixture.py`) unless a measured split requires a dedicated etcd fixture module.

## Packet order (≤200 LOC / PR)

| Packet | Deliverable |
|--------|-------------|
| **E0** | This playbook + pins (topology/tool contract) |
| **E1** | Fixture create/inspect/delete ownership for etcd work (reuse or thin wrapper) |
| **E2** | Snapshot + marker in snapshot + separately observed post-snapshot mutation |
| **E3** | Offline restore to clean dirs, verify marker + API/controller behavior; labelled interrupt/rollback |
| **E4** | ≤80-line lesson link on module-5.3 only after E2–E3 accepted |

## Acceptance rules

1. Unique private run directory; collision refusal; retain originals.
2. Authenticated baseline before snapshot; marker captured by the snapshot.
3. Post-snapshot mutation observed separately from restore success.
4. `endpoint health` is **not** proof of Kubernetes contents restored.
5. Interruptions leave fixture preserved until reconciliation.

## Sources

- [etcd 3.6 recovery](https://etcd.io/docs/v3.6/op-guide/recovery/) (confirm version against the owned node)
- Kubernetes kubeadm etcd backup notes for the exam pin minor in `docs/pins/kubernetes.yaml`
