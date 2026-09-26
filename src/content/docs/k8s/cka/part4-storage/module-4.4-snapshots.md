---
revision_pending: false
title: "Module 4.4: Volume Snapshots & Cloning"
slug: k8s/cka/part4-storage/module-4.4-snapshots
sidebar:
  order: 5
lab:
  id: cka-4.4-snapshots
  url: https://killercoda.com/kubedojo/scenario/cka-4.4-snapshots
  duration: "30 min"
  difficulty: advanced
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Data protection and cloning
>
> **Time to Complete**: 30-40 minutes
>
> **Prerequisites**: Module 4.2 (PV & PVC), Module 4.3 (StorageClasses)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Create** VolumeSnapshots and restore PVCs from snapshots for backup and recovery.
- **Configure** VolumeSnapshotClasses and compare how they relate to StorageClasses, drivers, and deletion policies.
- **Implement** a snapshot-based backup and validation strategy for stateful workloads.
- **Debug** snapshot and clone failures by inspecting CSI driver support, snapshot controller behavior, restore size, and PVC events.

---

## Why This Module Matters

Hypothetical scenario: your team is about to apply a database migration that rewrites several tables, and the rollback plan says "restore from backup if needed." That sentence is only useful if the backup captures the right point in time, can be restored into a real PVC, and has been tested before the maintenance window. Kubernetes VolumeSnapshots and PVC cloning give you API-level tools for those workflows, but they are not magic safety buttons. They depend on CSI driver capabilities, snapshot controllers, storage backend behavior, and application consistency choices that you must evaluate before data is already damaged.

Volume snapshots provide point-in-time copies of persistent data for recovery, test environments, migration rehearsal, and forensic inspection. Volume cloning creates a new PVC from an existing PVC without first creating a reusable snapshot object. Both features use the same mental model you already learned for PVs, PVCs, and StorageClasses: Kubernetes stores a desired state object, controllers reconcile that object, and the storage backend performs the actual data operation. The exam angle is usually practical rather than theoretical, so you should be able to read a manifest, predict whether it can work, and diagnose where the chain broke when it does not.

Think of a VolumeSnapshot like taking a photo of a disk at a specific moment. The photo captures the disk layout that the storage system can later use to create another volume, but the photo is only as useful as the camera, the storage backend, and the discipline of the person taking it. A VolumeSnapshotClass is the camera setting: it chooses the CSI driver and deletion behavior. A PVC restore is the act of printing a new working copy from that photo. A clone is more like photocopying the current page directly, which is convenient when the source is healthy and nearby but useless when you need yesterday's state.

---

## Snapshot Architecture and Readiness

Snapshots in Kubernetes deliberately mirror the PV and PVC relationship, but the purpose is recovery state rather than live pod storage. A `VolumeSnapshotClass` is cluster-scoped and normally created by an administrator, just as a StorageClass is. A `VolumeSnapshot` is namespaced and created by an application team or backup tool to request a point-in-time copy of a specific PVC. A `VolumeSnapshotContent` is cluster-scoped and represents the actual snapshot handle that the CSI snapshotter and backend understand.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Snapshot Architecture                              │
│                                                                       │
│   Similar to PV/PVC model:                                           │
│                                                                       │
│   VolumeSnapshotClass         VolumeSnapshot        VolumeSnapshot   │
│   (cluster-scoped)            (namespaced)          Content          │
│   ┌─────────────────┐         ┌─────────────┐      (cluster-scoped)  │
│   │ Defines HOW     │         │ Request to  │      ┌─────────────┐  │
│   │ snapshots are   │         │ snapshot a  │      │ Actual      │  │
│   │ created         │◄────────│ specific PVC│─────►│ snapshot    │  │
│   │                 │         │             │      │ reference   │  │
│   │ - driver        │         │ - source    │      │             │  │
│   │ - deletionPolicy│         │ - class     │      │ - driver    │  │
│   └─────────────────┘         └─────────────┘      │ - handle    │  │
│                                                     └─────────────┘  │
│                                                                       │
│   Admin creates               Dev creates          Auto-created      │
│   (once per cluster)          (when needed)        (by controller)   │
└──────────────────────────────────────────────────────────────────────┘
```

The mapping is close enough to use as a memory aid, but the names are not interchangeable. A PVC asks for usable storage that a pod can mount, while a VolumeSnapshot asks for a recovery point that can later become storage. A PV points at a live backend volume, while a VolumeSnapshotContent points at a backend snapshot. A StorageClass describes how new live volumes are provisioned, while a VolumeSnapshotClass describes how new snapshots are created and what should happen to the backend snapshot when the Kubernetes snapshot object is deleted.

| Storage | Snapshots |
|---------|-----------|
| StorageClass | VolumeSnapshotClass |
| PersistentVolume | VolumeSnapshotContent |
| PersistentVolumeClaim | VolumeSnapshot |

Before you write snapshot YAML, verify the cluster has the required machinery. The API server must know the snapshot CRDs, a snapshot controller must reconcile `VolumeSnapshot` and `VolumeSnapshotContent`, and the relevant CSI driver must support snapshot operations. A cluster can accept PVCs from a CSI driver and still be unable to snapshot them if the external snapshotter pieces are missing or if the driver does not implement snapshot support. That distinction is a common reason a valid-looking manifest stays stuck.

```bash
# Check if snapshot CRDs are installed
kubectl get crd | grep snapshot
# volumesnapshotclasses.snapshot.storage.k8s.io
# volumesnapshotcontents.snapshot.storage.k8s.io
# volumesnapshots.snapshot.storage.k8s.io

# Check for snapshot controller
kubectl get pods -n kube-system | grep snapshot
```

**Pause and predict:** if `kubectl get crd | grep snapshot` returns nothing, will creating a `VolumeSnapshot` fail at admission time, or will it create an object that never becomes ready?

<details>
<summary>Reveal the prediction</summary>

Without the snapshot CRDs, the API server does not recognize the kind, so the object is not created. With the CRDs present but no controller, the object can be stored and stays unready because nothing reconciles it.

</details>

Write down which of those two outcomes you expect before you open the note, then carry that distinction into the class and driver contracts in the next section.

The snapshot controller is responsible for the Kubernetes lifecycle, but it is not the storage backend. The CSI snapshotter sidecar talks to the CSI driver, and the driver talks to the storage system. When a snapshot fails, separate these layers in your head: API recognition, controller reconciliation, driver capability, backend permissions, and source volume state. That layered model prevents random edits and gives you a short diagnostic path during the CKA exam.

## VolumeSnapshotClass and Driver Contracts

A `VolumeSnapshotClass` is a policy object. It names the CSI driver that will create snapshots and declares the `deletionPolicy` for the corresponding `VolumeSnapshotContent`. The `driver` value must match the CSI driver name used by the installed storage driver, not a friendly cloud product name you found in an unrelated example. The `parameters` map is driver-specific, so do not assume one provider's options work on another provider even when the Kubernetes kind is identical.

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: csi-snapclass
  annotations:
    snapshot.storage.kubernetes.io/is-default-class: "true"  # Optional
driver: ebs.csi.aws.com                    # Must match CSI driver
deletionPolicy: Delete                      # Delete or Retain
parameters:                                 # Driver-specific params
  # Example for some drivers:
  # csi.storage.k8s.io/snapshotter-secret-name: snap-secret
  # csi.storage.k8s.io/snapshotter-secret-namespace: default
```

The deletion policy is more than cleanup preference. With `Delete`, deleting the Kubernetes `VolumeSnapshot` normally leads to deletion of the `VolumeSnapshotContent` and the underlying backend snapshot when the driver can complete that operation. With `Retain`, the Kubernetes request object can go away while the snapshot content and backend snapshot remain for manual recovery or long-term retention. The right answer depends on whether the snapshot is a disposable test artifact or a recovery point with operational value.

| Policy | Behavior |
|--------|----------|
| Delete | VolumeSnapshotContent and underlying snapshot deleted when VolumeSnapshot deleted |
| Retain | VolumeSnapshotContent and snapshot retained after VolumeSnapshot deletion |

Provider examples are useful only when you treat them as shape examples. AWS EBS, Google Persistent Disk, and Azure Disk all expose CSI drivers, but the driver names and parameters differ. On a real cluster, inspect the installed StorageClasses, CSIDriver objects, and vendor documentation before creating the class. In an exam environment, prefer the driver name already visible in cluster resources instead of inventing a value from memory.

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: ebs-snapclass
driver: ebs.csi.aws.com
deletionPolicy: Delete
```

The AWS EBS example is intentionally small because many useful settings live outside the Kubernetes object, such as IAM permissions and the EBS CSI driver installation. If the class exists but snapshots fail, do not keep changing the class name. Check whether the EBS CSI driver is installed, whether its snapshot support is deployed, and whether the controller has permission to create and delete snapshots in the account.

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: gcp-snapclass
driver: pd.csi.storage.gke.io
deletionPolicy: Delete
parameters:
  storage-locations: us-central1
```

The Google Persistent Disk example includes a location parameter because provider-specific placement can matter. That does not make the same key portable. If you copy the parameter to another CSI driver, Kubernetes may accept the YAML while the driver rejects the request later. This is why snapshot troubleshooting often requires reading controller and driver events, not only checking syntax.

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: azure-snapclass
driver: disk.csi.azure.com
deletionPolicy: Delete
parameters:
  incremental: "true"
```

The Azure Disk example shows another backend-specific detail: incremental snapshots can affect cost and performance characteristics. The Kubernetes API does not promise that every backend stores snapshots the same way. Some systems use copy-on-write metadata, some materialize copies differently, and some impose limits on snapshot chains or regions. Your design should therefore state the recovery objective and retention rule, then verify that the chosen driver and backend actually support it.

## Creating and Reading VolumeSnapshots

A `VolumeSnapshot` is a namespaced request against an existing PVC in the same namespace. It names a `VolumeSnapshotClass` and a source PVC, then waits for controllers and the CSI backend to produce a `VolumeSnapshotContent`. The source PVC is not replaced, and the pod using the PVC is not automatically paused. That makes snapshots convenient, but it also means the object alone does not guarantee application-level consistency.

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: data-snapshot
  namespace: production
spec:
  volumeSnapshotClassName: csi-snapclass   # Reference to class
  source:
    persistentVolumeClaimName: data-pvc    # PVC to snapshot
```

The controller flow is short, but each step can fail for a different reason. The controller must see the request, validate the referenced PVC and class, ask the CSI driver to create the snapshot, create or bind the `VolumeSnapshotContent`, and update the status. If the status never becomes ready, do not jump straight to deleting and recreating the object. First determine whether the failure is input validation, missing driver support, backend rejection, or slow snapshot creation.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Snapshot Creation Flow                          │
│                                                                      │
│   1. Create VolumeSnapshot                                          │
│          │                                                          │
│          ▼                                                          │
│   2. Snapshot controller validates                                  │
│      - PVC exists                                                   │
│      - VolumeSnapshotClass exists                                   │
│      - CSI driver supports snapshots                                │
│          │                                                          │
│          ▼                                                          │
│   3. CSI driver creates snapshot on storage backend                 │
│          │                                                          │
│          ▼                                                          │
│   4. VolumeSnapshotContent created (auto)                          │
│          │                                                          │
│          ▼                                                          │
│   5. VolumeSnapshot status: readyToUse=true                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Status reading is a skill worth practicing because snapshot failures often look quiet at first. `READYTOUSE` tells you whether the snapshot can be used as a restore source. `RESTORESIZE` tells you the size Kubernetes expects a restored PVC to request. The bound content name tells you which cluster-scoped object represents the backend handle. Events and error fields tell you whether the controller saw a validation or driver problem.

```bash
# List snapshots
kubectl get volumesnapshot -n production
# NAME            READYTOUSE   SOURCEPVC   SOURCESNAPSHOTCONTENT   RESTORESIZE   SNAPSHOTCLASS
# data-snapshot   true         data-pvc                           10Gi          csi-snapclass

# Detailed status
kubectl describe volumesnapshot data-snapshot -n production

# Check the VolumeSnapshotContent
kubectl get volumesnapshotcontent
```

The status object below is small, but it contains the most exam-relevant clues. `readyToUse: true` means the snapshot can be referenced by a restore PVC. `restoreSize` is the minimum request size for the new claim in normal restore flows. `error` is where many driver or controller failures surface when the snapshot fails to complete.

```yaml
status:
  boundVolumeSnapshotContentName: snapcontent-xxxxx
  creationTime: "2024-01-15T10:30:00Z"
  readyToUse: true                        # Snapshot is ready
  restoreSize: 10Gi                       # Size when restored
  error:                                  # If failed, error message here
```

**Pause and predict:** you take a snapshot of a `50Gi` PVC that only has `2Gi` of data written. When you restore from this snapshot, must the new PVC request `50Gi`, or can it request just `2Gi`?

<details>
<summary>Reveal the prediction</summary>

The new PVC must satisfy `restoreSize`, not the amount of application data written in the volume. Storage systems restore the volume shape as well as the files, so a claim that only covers the written data can be rejected.

</details>

Decide which request you would submit before you open the note, then use that choice when you read the restore manifest and the pending claim events that follow.

Snapshot timing deserves the same care as status reading. For a simple file workload, a crash-consistent snapshot may be adequate because the filesystem can replay metadata and the application can tolerate the state. For a database, message queue, or object store, a snapshot taken while writes are in flight may require recovery, lose acknowledged-but-unflushed data, or fail application checks after restore. The Kubernetes object gives you a point in time; your workload procedures decide whether that point is safe.

## Restoring PVCs from Snapshots

Restoring from a snapshot creates a new PVC whose `dataSource` references the `VolumeSnapshot`. It does not roll an existing PVC backward in place. That design is safer because you can restore into a separate claim, mount it in a validation pod, confirm the data, and only then decide how to move the application. In a production recovery, this separation is valuable because it reduces the chance of overwriting the last available copy while you are still diagnosing the incident.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restored-data
  namespace: production
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd              # StorageClass for new PVC
  resources:
    requests:
      storage: 10Gi                       # Must be >= snapshot size
  dataSource:                             # The magic part!
    name: data-snapshot                   # Name of VolumeSnapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

The restore claim still has ordinary PVC requirements. It needs a compatible StorageClass, an access mode the driver can satisfy, enough requested capacity, and a provisioner that can create a volume from the snapshot source. If the PVC stays `Pending`, describe both the PVC and the snapshot. A restore can fail because the snapshot is not ready, because the class or driver does not support restore from that snapshot, because the requested size is too small, or because the consuming pod is waiting on topology.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Restore from Snapshot                           │
│                                                                      │
│   VolumeSnapshot                    New PVC                          │
│   ┌─────────────┐                   ┌─────────────┐                 │
│   │ data-snap   │                   │ restored    │                 │
│   │             │                   │             │                 │
│   │ restoreSize:│◄──dataSource──────│ storage:    │                 │
│   │ 10Gi        │                   │ 10Gi        │                 │
│   └──────┬──────┘                   └──────┬──────┘                 │
│          │                                 │                         │
│          ▼                                 ▼                         │
│   VolumeSnapshotContent             New PV (with data)              │
│   (contains snapshot                (provisioned from               │
│    handle)                           snapshot)                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Cross-namespace restore is more subtle than same-namespace restore. The `VolumeSnapshot` object is namespaced, and the `VolumeSnapshotContent` is cluster-scoped, so advanced restore patterns can reference a snapshot from another namespace through `dataSourceRef` when the cluster supports cross-namespace data sources and the source namespace grants that reference. Cross-namespace restore requires the `CrossNamespaceVolumeDataSource` feature gate (alpha since v1.26) plus the Gateway API `ReferenceGrant` CRDs. In Kubernetes 1.35-era clusters, treat this as a policy-controlled feature, not a permission bypass. The source namespace owner should intentionally allow the restore path.

```yaml
# In namespace "production" — grant dr-test permission to reference the snapshot
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-dr-restore
  namespace: production
spec:
  from:
    - group: ""
      kind: PersistentVolumeClaim
      namespace: dr-test
  to:
    - group: snapshot.storage.k8s.io
      kind: VolumeSnapshot
```

```yaml
# In namespace "dr-test"
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dr-restore
  namespace: dr-test              # Different namespace!
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 10Gi
  dataSourceRef:                  # Use dataSourceRef for cross-namespace
    name: data-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
    namespace: production         # Source namespace
```

The important design difference is ownership. Same-namespace restore is straightforward because the application team controls both the snapshot and the restored PVC. Cross-namespace restore crosses a boundary, so it must respect namespace-level policy and any required `ReferenceGrant`. If your attempt fails, inspect the PVC event stream and the source namespace permissions before blaming the storage backend. The backend may be perfectly capable of restoring while Kubernetes correctly refuses an unauthorized reference.

Before running this in a real recovery, what output do you expect from `kubectl describe pvc restored-data -n production` while the restore is pending? You should expect events that name the data source, class, provisioner, or capacity issue. If the events mention an invalid data source, inspect the `VolumeSnapshot` status first. If the events mention provisioning or topology, continue with normal PVC and StorageClass troubleshooting.

## Volume Cloning and Application-Consistent Backups

Cloning creates a new PVC from an existing PVC without creating a separate snapshot object first. From the API perspective, the destination PVC sets `dataSource.kind: PersistentVolumeClaim`, and the provisioner creates a new volume containing data from the source. This is convenient for same-namespace test copies, pre-upgrade experiments, and data analysis workloads. It is not a historical recovery mechanism because it copies from the source as it exists at clone time.

```
┌─────────────────────────────────────────────────────────────────────┐
│               Snapshot vs Clone                                      │
│                                                                      │
│   SNAPSHOT                          CLONE                            │
│   ────────                          ─────                            │
│   PVC → Snapshot → New PVC          PVC → New PVC (direct)          │
│                                                                      │
│   Two-step process                  One-step process                 │
│   Point-in-time backup              Immediate copy                   │
│   Can restore multiple times        Single copy operation            │
│   Snapshot persists                 No intermediate artifact         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: cloned-data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 10Gi                 # Must be >= source PVC
  dataSource:                       # Clone from existing PVC
    name: source-pvc                # Name of source PVC
    kind: PersistentVolumeClaim     # Different kind than snapshot!
```

The requirements are intentionally narrower than snapshot restore. The source and destination PVCs must be in the same namespace for normal CSI cloning, the storage backend must support cloning, the destination request must be at least as large as the source, and the StorageClass usually needs to be compatible with the source volume. If you need a test namespace from production data, a snapshot-and-restore workflow is usually the better starting point. If you need a quick copy inside one namespace for a migration rehearsal, cloning may be simpler.

| Use Case | Description |
|----------|-------------|
| Dev/Test environments | Clone production data for testing |
| Pre-upgrade backups | Clone before risky changes |
| Data analysis | Clone for analytics without affecting production |
| Parallel processing | Multiple clones for parallel workloads |

Stop and think: you need to create a test environment with a copy of production data. You have two options: snapshot the production PVC and restore in the test namespace, or clone the production PVC directly. Which approach works for cross-namespace scenarios, and which does not? The snapshot path can be designed for namespace boundaries when the cluster supports the required reference policy, while a direct clone is normally same-namespace only. The tradeoff is extra objects and policy checks versus a faster, simpler same-namespace copy.

Snapshots and clones also differ in backup strategy. A clone may be useful before a risky change, but it is not a retention plan because it does not preserve a catalog of recovery points. A scheduled snapshot creates an inventory that can be restored repeatedly, inspected, and managed with deletion policy. A backup system built on snapshots should record which PVC was protected, when the snapshot became ready, whether the application was quiesced, and whether a restore test succeeded.

```yaml
# Illustrative VolumeSnapshot shape — a real schedule wraps this spec in a CronJob or external backup tool
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: daily-backup-2024-01-15
  labels:
    backup-type: daily
    source-pvc: database-data
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: database-data
```

Retention should be explicit because snapshots can cost money and can also be the only recovery copy you have. A common policy keeps a short window of daily snapshots, a smaller set of weekly recovery points, and a smaller set of monthly archives, but the exact numbers should come from recovery objectives and backend limits. The Kubernetes object labels are useful for cleanup automation, but they do not replace testing. A retained snapshot that nobody can restore is an expensive false sense of safety.

```bash
# Clean up old snapshots (example script concept)
# Keep last 7 daily, 4 weekly, 12 monthly

# List snapshots older than 7 days with daily label
kubectl get volumesnapshot -l backup-type=daily --sort-by=.metadata.creationTimestamp
```

Application consistency is the part Kubernetes does not infer for you. If you snapshot a MySQL PVC while the database is actively processing transactions, the storage backend may produce a crash-consistent image, similar to what the database would see after sudden power loss. Many databases can recover from that state, but "can recover" is not the same as "meets the business recovery objective." For important data, coordinate with the application before taking the snapshot.

```text
# Conceptual sequence — one long-lived session holds the lock while the snapshot runs
mysql> FLUSH TABLES WITH READ LOCK;
# (same session stays open; create VolumeSnapshot and wait for readyToUse here)
mysql> UNLOCK TABLES;
```

For real MySQL consistency, prefer `mysqldump --single-transaction`, Percona XtraBackup, or CSI pre/post-snapshot hooks rather than a hand-held global read lock. The safer pattern is to pause or drain writes, flush buffers to disk, take the snapshot quickly, and then resume writes. Some teams automate this with backup tools that run pre-snapshot and post-snapshot hooks. Others take snapshots from a replica that can be paused without affecting live traffic. The exact mechanism varies by workload, but the principle is stable: the application must help define a meaningful point in time.

Designing a useful snapshot-based backup strategy starts with the restore question, not the snapshot command. Ask what data state the workload must recover to, how much data loss is acceptable, how quickly the application must return, and who is allowed to approve a restore. Those answers become the recovery point objective, recovery time objective, validation procedure, and access policy. Without those decisions, the team may create snapshots on a schedule while still lacking a dependable recovery path.

### Validation jobs

For stateful workloads, validation is the difference between a storage artifact and a recovery plan. A validation job can restore the newest snapshot into a temporary PVC, mount it in a small pod, and run workload-specific checks such as file presence, database startup, schema version, or checksum comparison. The job should record the snapshot name, restore claim, validation result, and cleanup status. That record tells operators which recovery point was last proven rather than merely which object exists.

Labeling is part of the strategy because operators need to find recovery points quickly during stress. A snapshot created by automation should include the source PVC, application name, namespace, backup type, schedule, and owner. Labels should be stable enough for cleanup and reporting, while annotations can hold richer details such as validation run identifiers or a link to a runbook. The goal is to make every snapshot answer three questions: what does it protect, why does it exist, and when should it be removed.

A restore rehearsal should avoid the production write path until validation succeeds. Restore into a separate namespace or isolated claim, mount the data read-only when possible, and run checks that would catch the failure mode you care about. For a database, a basic file listing is too weak; the service should start, open the data directory, and answer a meaningful query. For a file workload, checksums or known sentinel files may be enough. Match the test to the workload's actual recovery promise.

Capacity planning is part of restore design. The source PVC size, snapshot restore size, destination StorageClass quotas, and namespace ResourceQuota all affect whether a restore can bind during an incident. A team that stores `100Gi` database volumes but gives the recovery namespace only `20Gi` of storage quota has built a restore path that fails when invoked. Validation jobs should run in the same quota and class conditions that an emergency restore would use.

### Retention and deletion policy

Retention should be tested against deletion policy before it matters. If the class uses `Delete`, a cleanup job that removes old `VolumeSnapshot` objects may also remove backend snapshots, which is correct for disposable backups but dangerous for protected archives. If the class uses `Retain`, deleting the request object may leave backend data behind, which protects recovery points but creates inventory and cost obligations. Choose the policy intentionally, then rehearse both cleanup and emergency restore.

Backup timing should match application behavior. A nightly snapshot may be adequate for a content repository that changes slowly, while a busy transactional database may need frequent logical backups plus storage snapshots before risky operations. Snapshot frequency also interacts with backend limits and costs. More frequent snapshots can reduce data loss, but they may increase storage usage, snapshot chain complexity, or API rate pressure. Good strategy explains why the schedule exists, not only when it runs.

Operationally, snapshot automation should surface failures before humans need the backup. Alert on snapshots that fail to become ready, validation restores that remain pending, unexpected changes in restore size, and cleanup failures for retained content. Also alert on an empty schedule, because no failed objects may appear when the CronJob or backup controller stopped running. Silent absence is one of the easiest ways for a backup system to decay unnoticed.

### Security boundaries

Security boundaries matter because snapshots may contain the same sensitive data as the original PVC. Cross-namespace restore can be useful for disaster recovery drills, but it also creates a path for data movement between tenants or teams. Require explicit grants, restrict who can create restore PVCs from protected snapshots, and audit restore activity. A backup system that protects availability while bypassing data governance creates a different incident.

The most mature pattern combines storage snapshots with application-native backup where each covers the other's weaknesses. Storage snapshots are fast and integrate with PVC restore, which makes them excellent for pre-change recovery and quick rollback testing. Application-native backups understand logical state, transactions, and cross-volume consistency better, which makes them important for databases and distributed systems. Kubernetes gives you the storage primitive; the workload architecture decides whether that primitive is sufficient by itself.

## Debugging Snapshot and Clone Failures

Snapshot and clone debugging starts with the question "which controller is supposed to act next?" If the API server rejects the kind, the CRDs are missing. If the object exists but never changes status, the snapshot controller or sidecar may be absent. If the controller reports driver errors, inspect the CSI driver and backend permissions. If the restore PVC is pending, inspect both the source snapshot and the destination PVC because restore depends on both.

```bash
kubectl get csidriver
kubectl describe csidriver <driver-name>
```

The `CSIDriver` object does not prove that every optional feature works, but it tells you which drivers are registered and gives you a starting point for vendor documentation. Pair it with existing StorageClasses so you know which provisioner created the source PVC. If the snapshot class names a different driver than the source volume's driver, the controller may be unable to create a meaningful snapshot even though each individual object looks valid.

```bash
kubectl get pods -n kube-system | grep snapshot
kubectl logs -n kube-system deploy/snapshot-controller
```

Controller logs are most useful after you have narrowed the object involved. Describe the `VolumeSnapshot`, note the namespace and name, then search logs around that reconciliation. For restore failures, describe the destination PVC and read events before editing YAML. PVC events often mention invalid data source, insufficient requested size, missing source object, unsupported driver operation, or provisioning delays from `WaitForFirstConsumer`.

| Symptom | Likely Layer | What to Check First |
|---------|--------------|---------------------|
| `the server doesn't have a resource type "volumesnapshot"` | API extension | Snapshot CRDs are not installed |
| Snapshot exists but `readyToUse` stays false | Controller or driver | Snapshot controller logs and VolumeSnapshot events |
| Restore PVC stays `Pending` | Source or destination PVC contract | Snapshot readiness, restore size, StorageClass, PVC events |
| Clone PVC fails immediately | Clone constraints | Same namespace, source size, driver clone support |
| Deleting snapshot removes backend copy | Deletion policy | VolumeSnapshotClass `deletionPolicy` and retention plan |

Which approach would you choose here and why: a restore PVC is pending, and the snapshot shows `readyToUse: true` with `restoreSize: 100Gi`, but the PVC requests `10Gi`. The fastest fix is not to recreate the snapshot. The source is ready; the destination request is too small. Create or patch a restore claim that requests at least the restore size, subject to the driver's expansion and provisioning rules.

For exam-speed troubleshooting, use a layered command sequence. Start with `kubectl get volumesnapshot -A` to identify readiness, then `kubectl describe volumesnapshot` for events, then `kubectl get volumesnapshotcontent` for binding, then `kubectl describe pvc` for restore or clone claims. Move to controller logs only after object status and events stop explaining the failure. This keeps you from spending precious time in logs when the event stream already names the problem.

Restore drills should include a negative case, not only a happy path. Create a restore PVC with too little storage in a disposable namespace and observe the event message, then delete it and create the correct claim. This teaches the difference between source readiness and destination validity. It also gives you confidence that your monitoring can detect restore failures before a real incident depends on the same path.

Clone drills should test namespace and size assumptions explicitly. A same-namespace clone with a destination request equal to the source size should be the baseline. A destination request that is too small should fail or remain pending depending on the provisioner behavior. A cross-namespace attempt should be rejected by normal clone rules. These small experiments build intuition faster than reading the feature summary repeatedly.

When debugging from events, pay attention to the subject of each message. A `VolumeSnapshot` event describes snapshot creation and binding. A `PersistentVolumeClaim` event describes restore, clone, provisioning, topology, quota, or access-mode decisions. A pod event describes scheduling and mount behavior. The same incident can produce messages on all three objects, but each object speaks about its own contract. Reading the right object prevents false conclusions.

Namespace cleanup after testing deserves care because snapshot objects and backend snapshots can have different lifetimes. In a `Delete` class, removing the namespace may trigger deletion of the namespaced `VolumeSnapshot`, which can in turn remove the associated content and backend snapshot. In a `Retain` class, cleanup may leave cluster-scoped content or external backend state that still needs ownership review. A lab can be simple, but the mental model should stay precise.

For production readiness, write the restore runbook in terms of objects and checks rather than individual people or one-off commands. The runbook should say which snapshot label selects the candidate, how to confirm readiness, how to size the restored PVC, which namespace receives the validation claim, which pod or job validates the data, and how the application cutover is approved. That structure makes the recovery repeatable even when the usual operator is unavailable.

Finally, separate backup confidence from backup comfort. It is comforting to see a list of successful snapshot objects, but confidence comes from a recent restore that exercised the same class, quota, namespace policy, and application checks you expect to use during recovery. The CKA exam will usually ask for a smaller version of that reasoning, but the habit transfers directly to real clusters: every data-protection object should have a tested path back to usable data, a named owner, a documented cleanup rule that matches the snapshot class policy, and enough operational context for another engineer to repeat the restore without guessing during a pressured maintenance window or exam lab under time pressure.

---

## Patterns & Anti-Patterns

Snapshot patterns work best when they separate recovery-point creation from recovery validation. The platform team provides classes and controllers, application teams decide when the data is safe to capture, and recovery drills prove that a snapshot can become a usable PVC. When those responsibilities are blurred, teams often create attractive dashboards of successful snapshot objects without knowing whether the restored application can boot, read its data, and serve correct results.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Snapshot before risky change | Schema migrations, major upgrades, destructive maintenance | Captures a named recovery point before state changes | Pair with application quiescing and restore rehearsal |
| Restore into validation PVC | Any important recovery workflow | Lets you inspect data before switching workloads | Automate cleanup so validation claims do not accumulate |
| Retained recovery class | Compliance or high-value data protection | Prevents snapshot deletion when request objects are removed | Requires manual retention and cost review |
| Clone for same-namespace copies | Test copy or migration rehearsal near the source | Avoids creating a reusable snapshot when history is not needed | Not a cross-namespace or historical backup strategy |

Anti-patterns often come from treating snapshot objects as proof of backup. A snapshot is only one part of a recovery system, and the Kubernetes API does not know whether your application flushed data, whether your recovery procedure points the application at the new PVC correctly, or whether a retained backend snapshot is still accessible months later. The better alternative is to make restore testing part of the design rather than a separate future project.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Snapshot every PVC without class review | Some drivers or classes may not support usable restore | Inventory drivers, classes, and restore behavior before scheduling |
| Use clones as backups | A clone captures current state and creates no reusable recovery point | Use VolumeSnapshots for named point-in-time recovery |
| Delete snapshots with unknown policy | Backend snapshots may disappear or linger unexpectedly | Read `deletionPolicy` and document retention ownership |
| Restore directly into production path | A bad restore can replace one incident with another | Restore into a separate PVC and validate before cutover |
| Ignore application consistency | Databases may restore to crash-consistent or corrupt state | Quiesce, flush, hook, or snapshot from a prepared replica |
| Copy provider YAML blindly | Driver names and parameters differ across clusters | Inspect installed CSI resources and vendor docs first |

The scaling concern is operational inventory. Once snapshots become routine, you need labels, owners, retention windows, restore test records, and cost visibility. A small lab can delete everything at the end. A production cluster needs a clear answer to who owns a retained snapshot, why it exists, when it expires, and when it was last restored successfully.

---

## Decision Framework

Choose between snapshot, clone, and ordinary PVC migration by asking what moment in time you need and where the copy must live. If you need the current data inside the same namespace, a clone is usually the simplest option when the driver supports it. If you need a historical recovery point, repeated restores, retention, or cross-namespace recovery, a snapshot is the better primitive. If the driver does not support either operation, fall back to application-native backup or file-level migration rather than pretending the Kubernetes object will do work the backend does not perform.

| Decision Question | Prefer Snapshot | Prefer Clone | Prefer Application-Native Backup |
|-------------------|-----------------|--------------|----------------------------------|
| Need a historical recovery point? | Yes, snapshots preserve a named point in time | No, clones copy current source state | Yes, especially for logical database recovery |
| Need same-namespace quick copy? | Works, but creates extra recovery objects | Yes, when driver supports cloning | Usually slower and more application-specific |
| Need cross-namespace recovery? | Possible with supported reference policy | Normal cloning is same-namespace | Often useful when platform policy blocks references |
| Need application-consistent database state? | Only with quiescing or hooks | Only with source consistency controls | Often best for transaction-level guarantees |
| Need long retention outside cluster lifecycle? | Use `Retain` and backend governance | Not a retention mechanism | Often required for compliance archives |

The practical decision path is to start with the failure or workflow. For bad data caused by a migration, restore from a snapshot taken before the migration; cloning the current PVC just copies the bad data. For a developer who needs a quick copy of a healthy PVC in the same namespace, clone if the driver supports it. For disaster recovery in a separate namespace or cluster, snapshot restore may help, but you must check reference policy, backend portability, and whether snapshots are region-bound. For databases with strict recovery requirements, combine storage snapshots with database-level backup and recovery procedures.

Treat the result as a plan you can test. A chosen snapshot class should be exercised with a real PVC, a real `VolumeSnapshot`, a restore PVC, and a validation pod. A chosen clone workflow should be tested with a same-namespace source PVC and a destination claim at the required size. A chosen retention policy should be tested by deleting the request object and confirming what happens to content and backend state. Decisions become reliable only when they survive a small rehearsal.

---

## Did You Know?

- Volume snapshot APIs reached GA in Kubernetes 1.20 (December 2020); the stable group is `snapshot.storage.k8s.io/v1`, and the snapshot controller is documented separately from the CSI driver sidecar because both are required.
- A `VolumeSnapshotClass` can be marked as the default with `snapshot.storage.kubernetes.io/is-default-class: "true"`, but the selected class must still match the CSI driver behind the source PVC.
- `dataSource` for a restore PVC can reference a `VolumeSnapshot`, while `dataSource` for a clone references a `PersistentVolumeClaim`; the kind value is the fastest way to tell which workflow the YAML requests.
- Cross-namespace `dataSourceRef.namespace` is alpha (v1.26+); requires the `CrossNamespaceVolumeDataSource` gate and a `ReferenceGrant` in the source namespace.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| No CSI driver with snapshot support | Teams assume all persistent storage can be snapshotted because PVCs work | Verify the installed CSI driver, snapshot sidecars, and vendor snapshot support before writing backup plans |
| Missing snapshot CRDs or controller | The API extension and controller are separate from ordinary PVC support | Install the snapshot CRDs and controller from the supported CSI external-snapshotter release path |
| Wrong driver in VolumeSnapshotClass | Provider examples are copied without matching the cluster's installed driver | Compare the class `driver` with StorageClass provisioners and CSIDriver names |
| Restore size too small | Operators confuse used filesystem data with the snapshot's required volume size | Read `.status.restoreSize` and request at least that much storage in the destination PVC |
| Clone across namespaces | Cloning feels like copying, so people expect namespace boundaries not to matter | Use snapshot restore with supported `dataSourceRef` policy, or keep clones in the same namespace |
| Deleting a source PVC too early | Teams assume a clone or snapshot completed because the object was created | Wait for clone binding or snapshot `readyToUse: true` before removing the source |
| Skipping application consistency | Storage snapshots are scheduled without coordinating with database writes | Use application hooks, read locks, replicas, or native backup tooling to create a safe capture point |

---

## Quiz

<details>
<summary>Question 1: Your production PostgreSQL database has corrupted data after a bad migration. You have a VolumeSnapshot from one hour before the migration and the original PVC is still running with corrupted data. Should you clone the PVC or restore from the snapshot?</summary>

Restore from the snapshot. A clone would copy the source PVC's current state, which is already corrupted, so it would produce another copy of the bad data. The snapshot represents a named point in time before the migration, so a new PVC with `dataSource.kind: VolumeSnapshot` gives you a recovery target. You should still restore into a separate PVC first, validate the database, and then plan the application cutover.

</details>

<details>
<summary>Question 2: A developer creates a VolumeSnapshot, but it stays at `readyToUse: false`. `kubectl get volumesnapshotclass` returns no resources, and the cluster uses the AWS EBS CSI driver for normal PVCs. What is missing?</summary>

The snapshot infrastructure is incomplete. Normal PVC provisioning through the EBS CSI driver does not automatically prove that snapshot CRDs, the snapshot controller, the CSI snapshotter sidecar, and a matching `VolumeSnapshotClass` are installed. The developer should verify the CRDs, deploy or inspect the snapshot controller, and create a class whose `driver` matches `ebs.csi.aws.com`. Recreating the same `VolumeSnapshot` without those pieces will not make it ready.

</details>

<details>
<summary>Question 3: You need a staging namespace with production-like data. A direct clone from the production PVC fails, but a production VolumeSnapshot exists. Why did the clone fail, and what restore design should you evaluate?</summary>

The clone failed because normal PVC cloning requires the source and destination PVCs to be in the same namespace. For a namespace boundary, evaluate a snapshot restore workflow using a `VolumeSnapshot` in the production namespace and a destination PVC that references it through supported `dataSourceRef` behavior. That design may also require a `ReferenceGrant` or equivalent policy so the source namespace explicitly permits the reference. If the cluster does not support that policy, use an application-native export or another approved migration path.

</details>

<details>
<summary>Question 4: A snapshot of a `100Gi` PVC contains only `5Gi` of files. A restore PVC requests `10Gi` and remains pending. What should you check and change?</summary>

Check the `VolumeSnapshot` status and read `.status.restoreSize`. The restore size reflects the volume size required by the snapshot restore path, not merely the amount of data that the filesystem currently stores. If the snapshot reports `100Gi`, the destination PVC must request at least `100Gi` or the provisioner can reject it. Increasing the request to the restore size addresses the destination contract; it does not require recreating the source snapshot.

</details>

<details>
<summary>Question 5: A team takes hourly snapshots of a MySQL PVC with a CronJob. After restore, MySQL reports recovery problems because the snapshot was taken during active writes. What went wrong, and how should the strategy change?</summary>

The snapshot was storage-level crash-consistent, not necessarily application-consistent. Kubernetes captured a point in time from the storage system, but it did not know whether MySQL had flushed buffers or paused writes. The strategy should add pre-snapshot and post-snapshot application hooks, use a read lock or other safe MySQL procedure, or snapshot a prepared replica. The team should also test restores regularly because a ready snapshot object does not prove the database can start correctly.

A stronger snapshot-based backup validation strategy for stateful workloads would restore a recent snapshot into a separate PVC, boot a validation instance or run database checks, and record the result. That makes the backup strategy measurable instead of relying on object creation alone. If validation fails, the team should treat the snapshot workflow as unhealthy even when the Kubernetes object reports ready.

</details>

<details>
<summary>Question 6: A restore PVC is pending. The snapshot is `readyToUse: true`, the class exists, and the PVC events mention the provisioner waiting for a first consumer. Is the snapshot broken?</summary>

Not necessarily. The snapshot source may be valid while the destination PVC is delayed by normal provisioning behavior, especially when the StorageClass uses `WaitForFirstConsumer`. The next step is to create or inspect the pod that will consume the restored claim and then read scheduling and PVC events together. If the pod appears and provisioning still fails, continue with destination class, topology, and driver logs. Do not recreate a good snapshot just because the restore PVC is waiting on a separate condition.

</details>

<details>
<summary>Question 7: A platform team wants to keep monthly recovery points for databases but automatically clean up short-lived test snapshots. How should they use VolumeSnapshotClasses and labels?</summary>

Use separate snapshot classes or clearly documented policies so protected database snapshots use `Retain` where appropriate, while disposable test snapshots use `Delete`. Add labels such as `backup-type`, `source-pvc`, and owner metadata so cleanup automation can find the right objects without guessing. Retained snapshots need a manual or automated inventory process because deleting the request object may not delete the backend snapshot. The team should also run restore validation, since retention without tested recovery is only storage accumulation.

</details>

---

## Hands-On Exercise: Snapshot and Restore

Exercise scenario: you will create test data in a PVC, take a snapshot, simulate data corruption, and restore the original data into a new PVC. The commands assume a cluster with a CSI driver that supports snapshots, the snapshot CRDs, and the snapshot controller. If you use kind or minikube, you may need to install snapshot components and use a CSI driver that supports the operations; a local-path provisioner alone may not be enough for real snapshots.

### Prerequisites

This exercise requires a cluster with:

- CSI driver that supports snapshots
- Snapshot controller and CRDs installed
- A StorageClass whose provisioner can create volumes from snapshots
- Permission to create a `VolumeSnapshotClass` or access to an existing one

Local environment setup can be done from the official external-snapshotter manifests when your practice cluster needs the CRDs and controller. Use manifests that match the external-snapshotter release supported by your Kubernetes version and storage driver. Installing the CRDs alone teaches the API shape, but a complete lab still needs a snapshot-capable CSI driver.

```bash
# Install Snapshot CRDs
kubectl kustomize https://github.com/kubernetes-csi/external-snapshotter/client/config/crd | kubectl create -f -

# Install Snapshot Controller
kubectl -n kube-system kustomize https://github.com/kubernetes-csi/external-snapshotter/deploy/kubernetes/snapshot-controller | kubectl create -f -
```

### Task 1: Check Snapshot Support

Start by proving the API and class layer exist. If these commands fail, do not continue to restore testing yet; the later manifests depend on these resources. If no `VolumeSnapshotClass` exists, you will create one from the installed CSI driver's provisioner name in a later task.

```bash
# Verify CRDs exist
kubectl get crd | grep snapshot

# Check for VolumeSnapshotClass
kubectl get volumesnapshotclass

# If none exists, you'll need to create one based on your CSI driver
```

<details>
<summary>Solution guidance</summary>

You should see the three snapshot CRDs and at least one snapshot class in a prepared cluster. If the CRDs are missing, the API server does not store `VolumeSnapshot` resources. If the classes are missing, a snapshot can still be possible after you create a class with the correct driver, but you need to know which CSI provisioner backs the source PVC.

</details>

### Task 2: Create Test Data

Create a namespace, a PVC, and a pod that writes a file. The file gives you a simple signal that restore worked later. The `DEFAULT_SC` line chooses the current default StorageClass, which is convenient for a lab, but in production you would choose the class deliberately based on driver, topology, expansion, reclaim policy, and snapshot support.

```bash
# Create namespace
kubectl create ns snapshot-lab

# Get default StorageClass
DEFAULT_SC=$(kubectl get sc | awk '/\(default\)/ {print $1}')

# Create a PVC
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: source-data
  namespace: snapshot-lab
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: ${DEFAULT_SC}
EOF

# Create pod to write data
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: data-writer
  namespace: snapshot-lab
spec:
  containers:
  - name: writer
    image: busybox:1.36
    command: ['sh', '-c', 'echo "Important data created at $(date)" > /data/important.txt; sleep 3600']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: source-data
EOF

# Wait for pod to be ready and data to be written
kubectl wait --for=condition=Ready pod/data-writer -n snapshot-lab --timeout=60s
kubectl exec -n snapshot-lab data-writer -- cat /data/important.txt
```

<details>
<summary>Solution guidance</summary>

The final command should print a line beginning with `Important data created at`. If the pod is pending, inspect the PVC and pod events before continuing. A snapshot lab proves restore behavior only after the original PVC is actually bound and mounted by a pod.

</details>

### Task 3: Create VolumeSnapshotClass (if needed)

Create this class only if your cluster does not already provide an appropriate default class. The driver name comes from the StorageClass provisioner so the snapshot class matches the storage that created the source PVC. If your storage vendor documents a different snapshot driver name or required parameters, use the vendor-supported value instead of blindly copying this lab class.

```bash
# Get the CSI driver of the default StorageClass
CSI_DRIVER=$(kubectl get sc ${DEFAULT_SC} -o jsonpath='{.provisioner}')

cat <<EOF | kubectl apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: csi-snapclass
driver: ${CSI_DRIVER}
deletionPolicy: Delete
EOF
```

<details>
<summary>Solution guidance</summary>

Run `kubectl get volumesnapshotclass csi-snapclass -o yaml` and confirm the `driver` field is populated. If `CSI_DRIVER` is empty, the default class lookup failed or there is no default StorageClass. In that case, select a StorageClass explicitly and repeat the driver extraction with that class name.

</details>

### Task 4: Create Snapshot

Create the snapshot while the file exists in the source PVC, then wait for `readyToUse`. The wait command is important because a created object is not the same as a usable recovery point. If the wait times out, describe the snapshot and check the controller logs before moving to corruption and restore.

```bash
cat <<EOF | kubectl apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: source-snapshot
  namespace: snapshot-lab
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: source-data
EOF

# Wait for snapshot to be ready
kubectl wait --for=jsonpath='{.status.readyToUse}'=true volumesnapshot/source-snapshot -n snapshot-lab --timeout=120s
# Verify snapshot status
kubectl get volumesnapshot source-snapshot -n snapshot-lab
```

<details>
<summary>Solution guidance</summary>

The snapshot should report ready status and a restore size. If it does not, run `kubectl describe volumesnapshot source-snapshot -n snapshot-lab` and read the events. Common causes include a missing snapshot controller, a wrong class driver, a source PVC that is not bound, or a storage driver that does not support snapshots.

</details>

### Task 5: "Corrupt" the Original Data

Now overwrite the file in the original PVC. This simulates a bad migration or accidental write after the snapshot was taken. You are not repairing the original claim in place; you are creating a controlled difference so the restored PVC can prove it came from the earlier recovery point.

```bash
# Simulate data loss
kubectl exec -n snapshot-lab data-writer -- sh -c 'echo "Corrupted!" > /data/important.txt'
kubectl exec -n snapshot-lab data-writer -- cat /data/important.txt
# Shows: Corrupted!
```

<details>
<summary>Solution guidance</summary>

The output should now show `Corrupted!` from the original PVC. This is the point where a clone would be the wrong recovery tool because it would copy the current corrupted state. The snapshot is valuable because it captured the earlier file contents.

</details>

### Task 6: Restore from Snapshot

Delete the writer pod so the original claim is not actively mounted, then create a new PVC from the snapshot and a reader pod that mounts the restored claim. This restore path validates the essential contract: the snapshot becomes a new PVC with the original data. In a production recovery, you would add application validation before moving traffic.

```bash
# Delete the pod (to release PVC)
kubectl delete pod -n snapshot-lab data-writer

# Create new PVC from snapshot
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restored-data
  namespace: snapshot-lab
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${DEFAULT_SC}
  resources:
    requests:
      storage: 1Gi
  dataSource:
    name: source-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
EOF

# Create pod to verify restored data
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: data-reader
  namespace: snapshot-lab
spec:
  containers:
  - name: reader
    image: busybox:1.36
    command: ['sh', '-c', 'cat /data/important.txt; sleep 3600']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: restored-data
EOF

# Wait for reader pod to be ready
kubectl wait --for=condition=Ready pod/data-reader -n snapshot-lab --timeout=60s

# Verify original data is restored
kubectl logs -n snapshot-lab data-reader
# Should show: Important data created at <original timestamp>
```

<details>
<summary>Solution guidance</summary>

The reader pod should print the original `Important data created at` line, not `Corrupted!`. If the restored PVC is pending, describe it and compare the requested size with the snapshot restore size. If the pod is pending after the PVC binds, inspect normal scheduling and mount events because the snapshot may already have done its part.

</details>

### Card A — Without snapshot CRDs, a VolumeSnapshot object is created and stays unready.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** missing snapshot CRDs mean the API server does not recognize the kind, so the object is not created and cannot stay unready. An unready object appears only after the kind is accepted and no controller finishes it. **Next action:** if apply reports an unknown kind, install the snapshot CRDs; if the object already exists, inspect the snapshot controller and the CSI driver.

</details>

### Card B — A 50Gi snapshot that holds 2Gi of data can be restored into a 2Gi PVC.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** the written application data is not the restore requirement. The new PVC must satisfy `restoreSize`, which reports the volume that was snapshotted, so a 2Gi claim does not satisfy a 50Gi snapshot. **Next action:** read `.status.restoreSize` and request at least that much storage on the new claim.

</details>

### Card C — restoreSize is the amount of application data written in the volume.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** `restoreSize` is the capacity the restored volume must request, not the number of bytes the application wrote. **Next action:** read `.status.restoreSize` and size the new PVC to that value rather than to filesystem usage.

</details>

### Card D — Installing the snapshot CRDs is enough for readyToUse to become true.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** installing the snapshot CRDs only lets the API server store the object. `readyToUse` becomes true only after a snapshot controller and a capable CSI driver finish the snapshot. **Next action:** confirm the controller is running and the VolumeSnapshotClass driver matches the source volume, then describe the snapshot.

</details>

**Success Criteria**: Confirm the snapshot class, the usable snapshot, the bound restore claim, the original file, and why a clone would not repair this corruption.

- [ ] VolumeSnapshotClass created or confirmed with the correct CSI driver.
- [ ] VolumeSnapshot shows `readyToUse: true`.
- [ ] New PVC created from the snapshot and bound successfully.
- [ ] Restored data matches the original file rather than the corrupted version.
- [ ] You can explain why a clone would not have fixed this corruption scenario.
- [ ] You can describe a snapshot-based backup validation strategy for stateful workloads.

### Cleanup

```bash
kubectl delete ns snapshot-lab
kubectl delete volumesnapshotclass csi-snapclass
```

### Practice Drills

Use these drills to build command fluency after the main lab. Each drill is small enough to repeat until you can type it from memory, but do not treat the commands as magic strings. For each one, say which layer it checks: API discovery, class policy, snapshot readiness, restore PVC shape, clone PVC shape, size requirement, or content binding.

```bash
# Task: Find all snapshot-related resources
kubectl api-resources | grep snapshot
```

```bash
# Task: Create SnapshotClass for your CSI driver with Delete policy
cat <<EOF | kubectl apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: practice-snapclass
driver: ${CSI_DRIVER} # Use driver found in lab
deletionPolicy: Delete
EOF
```

```bash
# Task: Verify a snapshot is ready to use
kubectl get volumesnapshot <name> -o jsonpath='{.status.readyToUse}'
```

```bash
# Task: Create PVC from snapshot "backup-snap"
# Key: dataSource with kind: VolumeSnapshot
# Add -n <namespace> and a storageClassName for your cluster
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restored-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  dataSource:
    name: backup-snap
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
EOF
```

```bash
# Task: Clone PVC "source-pvc" to "clone-pvc"
# Key: dataSource with kind: PersistentVolumeClaim
# Add -n <namespace> and a storageClassName for your cluster
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: clone-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  dataSource:
    name: source-pvc
    kind: PersistentVolumeClaim
EOF
```

```bash
# Task: Get the restore size of a snapshot
kubectl get volumesnapshot <name> -o jsonpath='{.status.restoreSize}'
```

```bash
# Task: Find the VolumeSnapshotContent for a VolumeSnapshot
kubectl get volumesnapshot <name> -o jsonpath='{.status.boundVolumeSnapshotContentName}'
```

---

## Learner check

> Cross-namespace restore requires the `CrossNamespaceVolumeDataSource` feature gate (alpha since v1.26) plus the Gateway API `ReferenceGrant` CRDs.

Before restoring a snapshot into another namespace, what object must exist in the source namespace, and which feature gate must be enabled?

---

## Sources

- https://kubernetes.io/docs/concepts/storage/volume-snapshots/
- https://kubernetes.io/docs/concepts/storage/volume-snapshot-classes/
- https://kubernetes.io/docs/concepts/storage/volume-pvc-datasource/
- https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- https://github.com/kubernetes-csi/external-snapshotter
- https://github.com/kubernetes-csi/external-snapshotter/tree/master/client/config/crd
- https://github.com/kubernetes-csi/external-snapshotter/tree/master/deploy/kubernetes/snapshot-controller
- https://github.com/kubernetes-sigs/aws-ebs-csi-driver
- https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-cloning
- https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver
- https://learn.microsoft.com/en-us/azure/aks/azure-csi-disk-storage-provision
- https://learn.microsoft.com/en-us/azure/aks/azure-disk-csi

## Next Module

Continue to [Module 4.5: Storage Troubleshooting](../module-4.5-troubleshooting/) to learn how to diagnose and fix common storage problems.
