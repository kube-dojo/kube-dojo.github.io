# CKA control-plane recovery: evidence and split plan

Issue #2338; parent #2280; epic #2272. This proposed split contains the unvalidated certificate and etcd recipes in Module 5.3 while preserving its accepted scheduler experiment and diagrams. Source acceptance is not recovery execution evidence.

## Sources inspected

Retrieved September 9, 2026; bodies and receipt retained under `.agent/cka-control-recovery-sources/`.

| Body | Official locator | Bytes | SHA256 |
|---|---|---:|---|
| Kubernetes 1.35 certificate management | [Manual certificate renewal](https://v1-35.docs.kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-certs/#manual-certificate-renewal), externally managed certificates and component reload | 544854 | `cd8b88380c5d47adbbe71d2f37e762cdd430e7c3ba097e585304a783f10c86d8` |
| etcd 3.6 disaster recovery | [Recovery](https://etcd.io/docs/v3.6/op-guide/recovery/), snapshot status, integrity, revision difference and revision bump | 274096 | `32ec86f76d03307d0cb4dd8262ae0ad26bb85d3efd77792701cecb8b3a81e36e` |

The Kubernetes page documents kubeadm-managed certificate renewal and the need to restart consuming control-plane Pods afterward. Static Pod restart involves local manifest handling; deleting API mirror Pods is not the restart mechanism. Externally managed certificate renewal requires its own management process. These statements do not establish that a particular host is kubeadm-managed, has matching tools, or is safe to disrupt.

The etcd page uses `etcdutl snapshot status` and offline restore into a specified output directory. It distinguishes snapshots made with an integrity hash from copied backend files and explains that restore creates a new logical cluster. For Kubernetes, revisions moving backward can leave controller caches inconsistent; the documented revision bump and compaction options address that concern. A generic restore command or endpoint health response alone does not prove the intended Kubernetes state was recovered. The page does not establish the fixture's installed etcd version or compatibility.

## Observed lesson gaps

Read-only inspection at `5f1e54da2`: certificate and etcd recipes move host manifests to fixed hold paths, lack interruption restoration and use sleeps or unbounded process loops. The restore recipe deletes a fixed destination before use; adjacent backup/edit commands and learner-check examples repeat fixed paths. No certificate/etcd execution receipt establishes those recipes. Existing scheduler receipts cover scheduling restoration only.

## Proposed implementation sequence

1. **Contain unvalidated executable recovery**, one module, target 160–190 aggregate lines and never exceed 200 without a reviewed split. Replace the credential-renewal, destructive restore and adjacent fixed-backup mutation fences with inspection and assessable recovery-decision exercises. Do not retain unsafe commands behind a reference-only label. Learners identify evidence, a competing hypothesis, the observation that rejects it, and a proposed verification. Match outcomes and learner checks to certificate inspection, etcd recovery planning and the already exercised scheduler restoration. Preserve diagrams and the entire accepted scheduler fixture. Verify any retained or new inspection commands on the appropriate dedicated fixture before claiming execution.
2. **Certificate execution**, a separate owned disposable fixture instance and separate review. Limit the contract to a named kubeadm-managed certificate and its consumer. Preserve prior credentials/manifests, prove baseline health, changed certificate identity, process reload and recovered function; exercise interruptions at mutation boundaries. Renewal/reload is not expiry recovery without a demonstrated expiry fault. Do not change the host clock to manufacture one.
3. **Etcd execution**, another explicit disposable fixture contract. Declare topology and compatible tool versions; use unique snapshot/restore destinations and refuse pre-existing paths. Preserve original data. Record a marker object, take the snapshot, change the marker, then prove the intended restored contents and subsequent API/controller operation. Include membership, revision/compaction, interruption and rollback decisions. A complete safe contract may need its own bounded artifact or an explicitly reviewed larger budget.

The first packet deliberately defers executable certificate/etcd recovery. It cannot close their practical-validation requirements or establish whole-module acceptance. Shared/live infrastructure, hosted companion parity and Ukrainian parity are outside these experiments. No recovery command was executed for this card.
