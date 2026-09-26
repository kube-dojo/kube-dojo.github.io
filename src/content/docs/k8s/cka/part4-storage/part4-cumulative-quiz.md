---
citations_verified: true
title: "Part 4 Cumulative Quiz: Storage"
sidebar:
  order: 7
---

> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 65-80 minutes
>
> **Prerequisites**: Module 4.1 Volumes, Module 4.2 PersistentVolumes and PersistentVolumeClaims, Module 4.3 StorageClasses and Dynamic Provisioning, Module 4.4 Volume Snapshots and Cloning, Module 4.5 Storage Troubleshooting
>
> **Assessment Format**: Scenario-based quiz plus a practical troubleshooting exercise
>
> **Target Kubernetes Version**: 1.35+

This cumulative module is not a memory test. It is a rehearsal for the kind of storage reasoning the CKA expects: reading symptoms, choosing the right abstraction, checking resource state in the right order, and explaining why one fix is safer than another.

Use `kubectl` for every command in these examples so each step stays pasteable in a new shell, with the verb, namespace, and resource written out before you change storage state.

---

## Learning Outcomes

- Diagnose pod startup failures caused by a missing claim, a failed mount, or a permission mismatch, tracing events from the workload to the storage object that broke the contract.
- Evaluate whether a workload should use emptyDir, a projected volume, a PVC, a clone, or a snapshot restore by judging lifecycle, durability, access, and recovery needs.
- Design a storage path that aligns the PersistentVolumeClaim, StorageClass, access mode, reclaim policy, and topology so the pod can be scheduled and mounted.
- Compare clone, snapshot restore, Retain reclaim, and manual salvage, and justify which option preserves the right data at the right point in time.
- Repair a broken storage scenario with kubectl commands, manifest edits, event inspection, and a verification step that proves the application can read and write the expected data.

---

## Why This Module Matters

Hypothetical scenario: A payment platform engineer ships a routine release late on a Friday. The Deployment rolls forward, but the replacement pods stay in `ContainerCreating`, customer checkouts start timing out, and the first event says only that a volume could not be mounted. The application team asks whether the database lost data, the infrastructure team asks which zone the volume lives in, and the incident commander needs a recovery path that does not make the outage worse.

Storage failures feel different from stateless workload failures because the data has a history. A bad image can usually be rolled back, but a badly handled persistent volume can strand a database, attach a disk to the wrong node, hide a stale configuration file, or delete the only copy of a directory the team assumed was durable. Kubernetes gives you clean abstractions, but those abstractions do not remove the need to reason about the real backing storage underneath them.

[The CKA storage domain tests that reasoning under time pressure](https://www.cncf.io/training/certification/cka/). You are rarely asked to recite the name of a field in isolation; you are asked to make a broken pod run, explain why a PVC is pending, recover from a deleted claim, or choose a storage pattern for a workload that has actual durability and scheduling constraints. This module turns the earlier Part 4 lessons into an operator's mental model: start from the symptom, identify the storage contract, inspect the controller events, then change the smallest thing that restores the workload safely.

---

## Core Content

### 1. Build the Storage Decision Model Before Touching YAML

Kubernetes storage work begins with a simple question: does the data need to outlive the pod? If the answer is no, an ephemeral volume may be the simplest and safest choice. If the answer is yes, you need a claim, a backing volume, and a lifecycle decision for what happens when the claim goes away. This distinction matters because many broken designs come from using a durable abstraction for temporary scratch data or using a temporary abstraction for business data. Use that answer to pick the first object you inspect. Scratch data keeps the search inside the pod spec, including the volume type, the medium, and any size limit. Durable data moves you from the named claim to the bound volume and then to the class. That order avoids a retain policy on a temporary cache and avoids database bytes on a volume that disappears with the pod.

[An `emptyDir` volume is created for a pod and removed when that pod leaves the node](https://kubernetes.io/docs/concepts/storage/volumes/). It survives container restarts inside the same pod, which makes it useful for caches, shared scratch directories, and sidecar handoff patterns. It does not survive pod deletion, eviction, or node failure, so it is the wrong place for uploaded files, database state, or anything that must be recovered after rescheduling. A container restart keeps the same pod, so the directory is still there for the new process. Deletion, eviction, and node failure end that pod, and the replacement receives a new directory even when the name matches. Judge a resume requirement against that boundary before you leave partial files only in the pod.

**Pause and predict:** A worker writes unfinished job files to an emptyDir, and a node drain then removes that pod from the node. What do you expect those files to do when a replacement pod starts on another node? Decide before you open the explanation.

<details>
<summary>Reveal the prediction</summary>

The volume is removed when the pod leaves the node, so the replacement pod starts without those unfinished job files.

</details>

Use that prediction to decide whether the unfinished files belong in the same lifecycle as the worker process or in a claim the replacement workload can mount on another node.

A memory-backed `emptyDir` is faster, but it changes the resource risk. [The bytes stored in that volume count against memory usage](https://kubernetes.io/docs/concepts/storage/volumes/), and a cache that grows without a limit can push a container toward eviction or an out-of-memory kill. When you choose `medium: Memory`, also set a `sizeLimit` and make sure the pod's memory requests and limits reflect the possible cache size. Medium Memory does not leave the cache on node disk for a later pod, because those bytes count against memory usage. An unbounded cache can therefore evict the pod or trigger an out-of-memory kill while the process heap still looks modest. Set a sizeLimit, and set the memory request and limit high enough to cover the process plus the cache you allowed.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: cache-demo
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "date > /cache/started && sleep 3600"]
    volumeMounts:
    - name: cache
      mountPath: /cache
  volumes:
  - name: cache
    emptyDir:
      medium: Memory
      sizeLimit: 128Mi
```

Projected volumes solve a different problem. They let a pod see configuration, secrets, service account tokens, and selected pod metadata as files without baking those values into the image. This is powerful because it separates deployment-time identity and configuration from application code, but it also creates subtle update behavior. [A normal ConfigMap or Secret volume can update after the source object changes, while a `subPath` mount pins a specific file path and does not receive those live updates](https://kubernetes.io/docs/concepts/storage/volumes/). A directory mount can refresh after the source object changes, so a process that re-reads the files can observe the new values. A subPath mount pins one file and keeps the content captured when the pod started, for as long as that pod keeps running. Plan a recreate when the value must change, or choose a directory mount when live rotation is part of the design.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: projected-demo
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "ls -la /projected && cat /projected/pod-name && sleep 3600"]
    volumeMounts:
    - name: projected
      mountPath: /projected
      readOnly: true
  volumes:
  - name: projected
    projected:
      sources:
      - downwardAPI:
          items:
          - path: pod-name
            fieldRef:
              fieldPath: metadata.name
```

**Pause and predict:** An application mounts one key from a Secret through subPath, the Secret is rotated, and the pod stays healthy for several minutes. What is in the mounted file, and what must happen before the new value shows up there? Decide before you open the explanation.

<details>
<summary>Reveal the prediction</summary>

The mounted file does not update until the pod is recreated. The object can already hold the new value while that file still shows the previous one.

</details>

Connect that result to the rollout note you would leave for the team, including which object you would inspect first and which command would show the file the process is actually reading.

A `hostPath` volume should make you cautious. [It mounts part of the node filesystem into a pod, which can expose node secrets, break isolation](https://kubernetes.io/docs/concepts/storage/volumes/), and create workloads that only run on nodes with a particular local path. It is useful for tightly controlled node agents and some local labs, but it is not a general application storage pattern and [is usually blocked by stricter admission policies](https://kubernetes.io/docs/concepts/security/pod-security-standards/). The mount can expose node material the application should not see, and it can run only on nodes that contain the expected path. That combination fits a tightly controlled node agent or a lab. Ordinary application data should move with a claim instead of with one machine.

Persistent storage adds a contract. The pod does not ask for a specific cloud disk or storage array volume directly; it asks for a `PersistentVolumeClaim`, and Kubernetes binds that claim to a `PersistentVolume` or asks a provisioner to create one. [The claim is namespaced because it belongs to an application boundary, while the persistent volume is cluster-scoped because the underlying storage resource exists outside one namespace](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).

```ascii
+--------------------+        requests         +--------------------------+
| Pod in namespace   | ----------------------> | PersistentVolumeClaim    |
| app                |                         | namespace: app           |
+--------------------+                         +------------+-------------+
                                                           |
                                                           | binds to
                                                           v
                                                +--------------------------+
                                                | PersistentVolume         |
                                                | cluster-scoped resource  |
                                                +------------+-------------+
                                                           |
                                                           | represents
                                                           v
                                                +--------------------------+
                                                | real storage             |
                                                | disk, share, or CSI vol  |
                                                +--------------------------+
```

The diagram shows why debugging storage requires moving across scopes. A pod symptom appears in a namespace, the PVC is in that same namespace, the PV is cluster-scoped, and the actual disk or file share may live in a cloud zone or on a specific node. If you only inspect the pod, you may miss the binding decision. If you only inspect the PV, you may miss the workload event that tells you why the mount failed. Treat each hop as its own question. The namespace tells you which claim the pod can see, the claim tells you whether a volume bound, and the cluster-scoped volume tells you the reclaim policy and any old claim reference. The zone or node is where the disk or share actually lives. Stopping at the first familiar object is how a wrong claim name gets confused with a zonal mismatch.

Active learning prompt: before reading further, decide what storage you would choose for a log-processing pod that downloads a large input file, transforms it, uploads the result to object storage, and then exits. If you chose a PVC, explain what data needs to survive after the pod exits. If you chose `emptyDir`, explain how you would limit the risk of the scratch directory filling the node.

The decision model can be summarized as a set of tradeoffs rather than a list of resource names. Ephemeral volumes optimize for simplicity and pod-local lifecycle. Projected volumes optimize for configuration and identity injection. PVCs optimize for durable storage with a declared request. Snapshots and clones optimize for recovery, migration, and test data workflows. Troubleshooting connects all of these by asking which promise was broken. Name the promise before you name the object. Vanishing scratch points at emptyDir. Configuration or a token that should come from the cluster points at a projected volume, a ConfigMap, or a Secret. Bytes that must outlive the pod point at a claim, and only then do you choose access mode, size, topology, and reclaim. A clone or a snapshot is a copy or a recovery point, not the volume written on the first day.

| Situation | Better starting point | Reasoning question |
|---|---|---|
| Scratch files shared by containers in one pod | `emptyDir` | Should the data vanish when the pod is replaced? |
| Application config or token material | Projected or ConfigMap or Secret volume | Should the value come from cluster objects instead of the image? |
| Database or queue state | PVC backed by a suitable StorageClass | What access mode, size, topology, and reclaim behavior are required? |
| Test copy of existing data | PVC clone when supported | Does the source PVC live in the same namespace and need a direct copy? |
| Point-in-time recovery | VolumeSnapshot and restore PVC | Does the team need a reusable recovery point? |
| Node-local performance with scheduling constraints | Local PV with node affinity | Can the pod tolerate being tied to one node's storage? |

### 2. Understand Binding as a Contract, Not a Coincidence

A PVC describes what an application needs. It can request capacity, access modes, a specific `storageClassName`, and sometimes a data source such as a snapshot or another PVC. Kubernetes then tries to satisfy that request with an existing PV or through dynamic provisioning. When the PVC remains `Pending`, the cluster is telling you that the requested contract has not been fulfilled.

The access mode is part of that contract, but it is often misunderstood. [`ReadWriteOnce` means the volume can be mounted read-write by workloads on a single node, not necessarily by only one pod in all cases](https://kubernetes.io/docs/concepts/storage/persistent-volumes/). `ReadOnlyMany` and `ReadWriteMany` depend on backing storage that supports multi-node mounts. If your application requires active writers on several nodes, a block disk with `ReadWriteOnce` is the wrong primitive even if the YAML is accepted. Two pods on one node can still share a ReadWriteOnce volume, while a pod on a second node can fail with a multi-attach error. ReadOnlyMany and ReadWriteMany do not erase that error unless the backing storage can really mount on those nodes. If writers must run on several nodes at once, a single-node block disk is the wrong primitive. Choose the mode from the attachment behavior you need.

Capacity binding is also a contract, not an exact shopping order. A claim for `20Gi` can bind to a larger suitable volume, but it cannot bind to a smaller one. Static PV binding usually selects the smallest matching volume that satisfies the request, because using a much larger volume wastes capacity. In dynamic provisioning, the external provisioner creates storage that matches the requested size according to the StorageClass and driver behavior. A pending claim beside a static volume is often a failed match rather than an empty cluster. The volume must be at least as large as the request, and static binding prefers the smallest volume that fits so leftover capacity is not wasted. Compare the numbers, the mode, and the class before you delete the claim and try again at random.

StorageClass behavior changes when binding happens. With `volumeBindingMode: Immediate`, a dynamic volume may be provisioned as soon as the PVC is created. That is fine for storage available across the cluster, but risky for zonal disks because the volume may appear in one zone while the pod later schedules in another. [With `WaitForFirstConsumer`, Kubernetes waits until a pod needs the PVC, then considers the pod's scheduling constraints before provisioning or binding](https://kubernetes.io/docs/concepts/storage/storage-classes/). Immediate binding can place a zonal disk before the scheduler has chosen a node, so the pod may be unable to run where that disk exists. WaitForFirstConsumer keeps the claim Pending until a pod supplies those constraints, including the case where no pod exists yet.

**Pause and predict:** A PVC stays Pending, its StorageClass uses WaitForFirstConsumer, and no pod references the claim. What should you do next, and which edit would you refuse as the first move? Decide before you open the explanation.

<details>
<summary>Reveal the prediction</summary>

This wait is the class policy, and deleting the claim is the wrong first move. The claim can stay Pending until a pod exists and scheduling constraints are known.

</details>

Carry that reading into the pod spec and the node labels you would compare next, and note which scheduling constraint would still leave the claim unchanged while the workload has nowhere to land.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: zonal-safe
provisioner: example.csi.k8s.io
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
reclaimPolicy: Delete
```

The `reclaimPolicy` describes what happens to the backing PV after the claim is deleted. [`Delete` is convenient for disposable environments because the volume is removed by the provisioner](https://kubernetes.io/docs/concepts/storage/persistent-volumes/). [`Retain` preserves the PV and the underlying data, but it also leaves the PV in a `Released` state with its old claim reference](https://kubernetes.io/docs/concepts/storage/persistent-volumes/). That is a safety feature: Kubernetes should not silently hand possibly sensitive data to a new claim. Delete asks the provisioner to remove the backing volume with the claim, which is reasonable only when the data is disposable. Retain keeps the volume object and the data, then records Released instead of Available because the old claim reference is still set. The cluster will not silently give that data to a different claim.

A retained PV needs deliberate handling. An administrator may inspect or back up the data, clean the backing store if reuse is intended, and then remove the old `claimRef` or recreate the PV object with a clean specification. The important exam habit is to notice that `Released` does not mean `Available`. It means the claim is gone, but the PV still remembers the old binding. Clearing that reference makes the volume eligible for a new claim, and it does not by itself prove the new claim should see the old files. Confirm the volume identity, the owner, and any backup your environment requires before you patch. An exam prompt may compress the same judgment into one instruction to make the volume Available.

```bash
kubectl get pv
kubectl describe pv retained-pv
kubectl patch pv retained-pv -p '{"spec":{"claimRef": null}}'
```

Use the patch only when you are intentionally making that PV available again. In a real production environment, you would also confirm ownership, backup status, and data sanitization before rebinding. The CKA often compresses that context into a smaller task, but the professional habit is still to treat retained data as sensitive until proven otherwise. The patch is the step that allows reuse, not the step that decides ownership. Read the volume name, the old claim reference, and the reclaim policy first. If those fields do not match the volume you intend to keep, stop before you clear the reference.

Worked example: a team reports that a database pod is stuck in `Pending`, and the PVC is also `Pending`. The PVC requests `10Gi`, access mode `ReadWriteOnce`, and `storageClassName: fast-zonal`. You run `kubectl describe pvc db-data -n payments` and see an event that says waiting for first consumer. That event is not a failure by itself; it means the StorageClass delays provisioning until a pod is scheduled.

The next check is the pod that consumes the claim. If the pod has a node selector for a zone where no eligible nodes exist, the scheduler cannot choose a consumer location, so the PVC stays pending. If the pod has valid scheduling options, the eventual provisioner should create a volume in the selected topology. The repair may be a node selector fix, a toleration fix, or a StorageClass change, not a random deletion of the PVC.

```bash
kubectl describe pvc db-data -n payments
kubectl describe pod db-0 -n payments
kubectl get storageclass fast-zonal -o yaml
kubectl get nodes --show-labels
```

Active learning prompt: imagine the PVC is pending with no useful events, the StorageClass exists, and its binding mode is `WaitForFirstConsumer`. What would happen if you create only the PVC and never create a pod that references it? The answer should change how you interpret `Pending`: sometimes it is a waiting state created by design, not an error state caused by missing storage.

Binding also interacts with `storageClassName` in a way that trips up many operators. Omitting the field allows the default StorageClass to be used if the cluster has one. Setting `storageClassName: ""` explicitly opts out of dynamic provisioning and asks Kubernetes to bind only to a manually created PV with no class. Those two YAML shapes look similar to a tired human, but they express different intentions to the control plane. Leaving the field out may select the default class and provision a volume. Setting the field to an empty string opts out of dynamic provisioning and waits for a static volume with no class. Read the spec and the events before you call the cluster broken, because the empty string can be a choice rather than a typo.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: manual-only
spec:
  storageClassName: ""
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

The safest debugging posture is to read the PVC specification before assuming the cluster is broken. Check the requested class, capacity, access modes, data source, and events. Then check whether matching PVs exist or whether dynamic provisioning should have happened. Only after those checks should you decide whether to edit a manifest, create a missing resource, or investigate the external CSI driver.

### 3. Connect Pod Symptoms to Storage Events

Storage troubleshooting starts at the pod because users usually report a workload symptom, not a PV condition. A pod stuck in `ContainerCreating` often means the container image has not even started; Kubernetes may be blocked on attaching or mounting volumes. A pod that starts and then crashes may mean the volume mounted successfully, but the application cannot read, write, or find the expected files. ContainerCreating usually means attach or mount has not finished, so the application process has not started and a permission change will not help yet. A pod that reaches Running and then logs permission denied has already mounted the volume. From that moment you are debugging the user, the group, and the filesystem. Keep the phase and the event together so you edit the layer that actually failed.

The first command for a pod startup problem is usually `kubectl describe pod`. The `Events` section tells you whether the kubelet failed to mount a volume, whether the attach controller failed to attach a disk, whether the PVC is missing, or whether a secret or ConfigMap key could not be projected. This command gives you the bridge between workload state and storage state.

```bash
kubectl describe pod api-0 -n prod
```

If the event mentions a missing PVC, inspect the claim in the same namespace. PVC names are namespace-local, and a claim with the same name in another namespace does not help this pod. If the claim does not exist, create the intended PVC or fix the pod manifest to reference the correct one. If the claim exists but is pending, move to `kubectl describe pvc`.

```bash
kubectl get pvc -n prod
kubectl describe pvc api-data -n prod
```

If the event mentions `FailedMount` for a ConfigMap or Secret, check whether the referenced object and key exist in the pod namespace. A common mistake is updating a ConfigMap name but not the volume reference, or mounting a key with `items` and misspelling that key. Kubernetes will keep retrying, but the pod cannot start until the reference is valid.

```bash
kubectl get configmap app-config -n prod -o yaml
kubectl get secret app-secret -n prod -o yaml
```

If the event mentions a multi-attach error, identify whether the volume is attached to a different node through an old pod. This is common with `ReadWriteOnce` volumes after a node problem, a stuck terminating pod, or an aggressive rollout strategy. The repair is not to change the access mode on the claim. The repair is to stop the competing attachment path or wait for the storage driver to detach cleanly. The event means another attachment still exists, commonly from a pod stuck terminating on the previous node. Rewriting the access mode leaves that attachment in place and may ask for a mode the disk cannot provide. List the consumers, inspect VolumeAttachment when you need the node binding, and let the driver detach before you expect the replacement pod to mount.

```bash
kubectl get pod -A -o wide | grep api-data
kubectl get volumeattachment
```

Permission problems appear later in the sequence. The pod may be `Running`, but the logs show `permission denied` when the process writes to the mount path. In that case, the storage binding worked and the mount happened. Now you are debugging Linux ownership, group permissions, container user identity, and the pod security context.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: writer
spec:
  securityContext:
    fsGroup: 1000
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "echo ok > /data/probe && sleep 3600"]
    securityContext:
      runAsUser: 1000
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: writer-data
```

[The `fsGroup` setting asks Kubernetes to make mounted volume files accessible to the specified group when the volume type and driver support the behavior](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/). It is not a magic fix for every image, but it is a common CKA-level repair for pods that run as a non-root user and need to write to a mounted volume. Always verify the fix by writing an actual file, not merely by checking that the pod is running. The Running phase only shows that the mount call returned. The write test shows that the process identity can use the path. If the write still fails, the next check is still ownership and the driver, not a new claim.

A disciplined troubleshooting path keeps you from thrashing. Start with the pod event, then inspect the PVC, then the PV, then the StorageClass, then node or driver state. At each step, ask what promise the resource made and whether the next resource in the chain fulfilled that promise. This turns a noisy incident into a sequence of falsifiable checks.

```ascii
+---------------------+
| User symptom        |
| Pod not ready       |
+----------+----------+
           |
           v
+---------------------+
| describe pod        |
| Events: mount path  |
+----------+----------+
           |
           v
+---------------------+
| describe pvc        |
| Pending or Bound?   |
+----------+----------+
           |
           v
+---------------------+
| inspect pv and sc   |
| class, access, zone |
+----------+----------+
           |
           v
+---------------------+
| verify node/driver  |
| attach, permissions |
+---------------------+
```

The same path works for snapshots and clones, but with an extra data-source branch. If a PVC is supposed to restore from a snapshot, the claim may wait on snapshot readiness or driver support. [If a PVC is supposed to clone another PVC, the source claim must be in the same namespace, the driver must support cloning, and the destination request must satisfy the driver's size rules](https://kubernetes.io/docs/concepts/storage/volume-pvc-datasource/).

### 4. Use Snapshots and Clones as Recovery Tools, Not Decoration

Snapshots and clones are easy to describe and harder to use responsibly. A clone creates a new PVC from an existing PVC, usually within the same namespace. A snapshot captures a point-in-time view that can be restored later into one or more PVCs when the CSI driver and snapshot controller support it. Both features depend on CSI capabilities, and neither should be assumed to exist just because the Kubernetes API accepts a manifest. A clone is a new claim whose dataSource is another claim in the same namespace, and it does not create a snapshot object you can restore again later. A snapshot is a recovery point, and a restore creates another new volume rather than rewriting the original claim in place. The driver, and for snapshots the controller, must support the operation.

A clone is useful when you need a direct copy for testing, migration, or repair work close to the source workload. Because the clone uses another PVC as its `dataSource`, it avoids creating a reusable snapshot object. That simplicity is useful, but it also means the operation is not a backup strategy by itself. If the source data changes or disappears later, the clone is only whatever the driver produced at clone time.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data-copy
  namespace: app
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 5Gi
  dataSource:
    name: app-data
    kind: PersistentVolumeClaim
    apiGroup: ""
```

A snapshot is better when the recovery point matters. The `VolumeSnapshot` is namespaced, the `VolumeSnapshotClass` describes how the driver creates snapshots, and the `VolumeSnapshotContent` represents the actual snapshot handle. This pattern resembles PVC, StorageClass, and PV, but the purpose is recovery state rather than live pod storage.

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: app-data-before-upgrade
  namespace: app
spec:
  volumeSnapshotClassName: csi-snapshots
  source:
    persistentVolumeClaimName: app-data
```

Restoring from a snapshot creates a new PVC whose `dataSource` points at the `VolumeSnapshot`. The new claim still needs a compatible StorageClass, capacity request, access mode, and driver support. [A restore is not a command that mutates the old PVC in place; it creates a new volume from a recovery point](https://kubernetes.io/blog/2020/12/10/kubernetes-1.20-volume-snapshot-moves-to-ga/), which you can mount into a pod for validation before switching traffic.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data-restored
  namespace: app
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 5Gi
  dataSource:
    name: app-data-before-upgrade
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

The professional stake is consistency. [A snapshot taken while an application is actively writing may be crash-consistent but not necessarily application-consistent, depending on the application and storage system](https://kubernetes.io/blog/2020/12/10/kubernetes-1.20-volume-snapshot-moves-to-ga/). For databases, teams often coordinate snapshots with application-level flushing, backup tooling, or temporary write quiescence. The CKA will not usually ask you to design an enterprise backup program, but it can expect you to know that a snapshot resource is not the same as a verified restore. Crash-consistent describes a snapshot taken while the application is actively writing. Application-consistent is the stronger case, and it still depends on the application and the storage system. For a database, that is why teams coordinate the snapshot with application-level flushing, backup tooling, or temporary write quiescence. The proof remains a restore into a new claim, rather than the snapshot object by itself.

When you troubleshoot a failed snapshot or restore, [start by checking whether the CRDs exist, whether the snapshot controller is installed, whether the CSI driver supports snapshots, and whether the snapshot object is ready to use](https://kubernetes.io/docs/concepts/storage/volume-snapshots/). A PVC restore that stays pending may be a storage problem, a snapshot readiness problem, a class mismatch, or a capacity mismatch. The event stream is again the shortest path to the real issue.

```bash
kubectl get volumesnapshot -n app
kubectl describe volumesnapshot app-data-before-upgrade -n app
kubectl get volumesnapshotclass
kubectl describe pvc app-data-restored -n app
```

Clones and snapshots also matter during incident response because they let you separate investigation from live recovery. If a production volume contains suspicious state, a clone or snapshot restore can give you a copy to inspect without mounting the original into a debugging pod. That protects the evidence, lowers the risk of accidental writes, and gives the application team a safer way to compare expected and actual files.

### 5. Practice Exam-Style Storage Reasoning

A cumulative assessment should test decisions, not isolated vocabulary. In the CKA, the important question is not "what is a PVC?" but "why is this PVC pending, and what should you change so the pod can run without violating the storage requirement?" This section gives you the synthesis you need before the quiz. Say the layer before you edit anything. A ContainerCreating event is a missing claim, a missing key, a failed attach, or a failed mount that you can name from the event text. A Pending claim is a class problem, an empty storageClassName opt-out, a WaitForFirstConsumer wait, or a static volume that does not match size, mode, or selector. A Released volume under Retain still has its data. A multi-attach error is an old attachment, not a request for a new access mode.

When you see a pod in `ContainerCreating`, do not jump straight to editing YAML. Read the pod events first and classify the failure. Missing claim, missing ConfigMap, failed attach, failed mount, and permission denied all point to different layers. A fast operator moves quickly because the sequence is practiced, not because they skip observation.

When you see a `Pending` PVC, compare the request against the environment. Does the class exist? Is there a default class if the claim omitted `storageClassName`? Did the claim explicitly set `storageClassName: ""`, which disables dynamic provisioning? Is the binding mode waiting for a pod? Are there matching static PVs by size, access mode, class, selector, and volume mode?

When you see a `Released` PV, slow down. The claim is gone, but the old binding reference and the underlying data may remain. If the reclaim policy is `Retain`, Kubernetes is deliberately refusing to hand that data to a new claim automatically. For an exam task, you may patch away the claim reference when told to reuse the volume. For real work, you also confirm data ownership and sanitization.

When you see a multi-attach event, resist the temptation to rewrite access modes. A `ReadWriteOnce` volume may be stuck on a previous node or pod, and changing the claim does not detach a cloud disk. Find the old consumer, check termination state, and inspect `VolumeAttachment` objects when relevant. Only after the conflict is cleared should you expect the new pod to mount successfully.

When you see a permission error inside a running container, prove that the storage path exists and that the process identity can write to it. A pod-level `fsGroup` and container-level `runAsUser` may be enough for many volume types, but the exact result depends on driver behavior and filesystem ownership. The best verification is a command that writes a file to the mounted path and then reads it back.

The exam rewards small, reversible actions. Describing a resource is safer than deleting it. Creating a missing ConfigMap key is safer than replacing an entire pod spec under pressure. Patching a retained PV's claim reference is appropriate only when the task asks you to make it available and the data handling is understood. Good storage work is precise because storage mistakes can preserve the wrong data or delete the right data.

---

## Did You Know?

1. **A PVC without `storageClassName` and a PVC with `storageClassName: ""` are intentionally different**: [the first may use the cluster default StorageClass, while the second opts out of dynamic provisioning and waits for a manually matching PV](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).

2. **`WaitForFirstConsumer` is a scheduling feature as much as a storage feature**: it delays binding or provisioning so the selected node and storage topology can agree before a zonal volume is created.

3. **A `Released` PV is not automatically safe for reuse**: the retained data may belong to the previous claim owner, so Kubernetes requires an explicit administrative action before another claim can bind to it.

4. **A successful snapshot object is not the same as a tested recovery plan**: the only proof that backup-style storage works is restoring it into a PVC and validating the application can use the recovered data.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Treating `emptyDir` as durable storage | The data disappears when the pod is removed from the node, so a rescheduled workload can lose important files. | Use `emptyDir` only for scratch data, caches, and sidecar handoff patterns that tolerate pod replacement. |
| Assuming a pending PVC always means storage is broken | `WaitForFirstConsumer` can intentionally keep a PVC pending until a pod references it and scheduling constraints are known. | Describe the PVC, inspect the StorageClass binding mode, and check the consuming pod before changing resources. |
| Using `hostPath` for normal application persistence | The pod becomes tied to node filesystem layout and may gain dangerous access to node paths. | Prefer CSI-backed PVCs for application data, and reserve `hostPath` for controlled node-level agents or labs. |
| Forgetting that `subPath` blocks live ConfigMap or Secret updates | The mounted file does not update when the source object changes, which can leave applications using stale configuration. | Avoid `subPath` for config that must update live, or restart pods intentionally after changing the source object. |
| Reusing a retained PV without checking ownership | The next claim may see data from a previous workload, creating security and correctness risks. | Inspect, back up, sanitize, and only then clear `claimRef` or recreate the PV for a new claim. |
| Fixing multi-attach errors by changing access modes | The real issue is often an old attachment on another node, and changing YAML may not detach the volume. | Find the old pod or `VolumeAttachment`, resolve the competing attachment, and then verify the new pod mounts. |
| Declaring a snapshot but never testing restore | A snapshot that exists in the API may still be unusable for application recovery if restore assumptions are wrong. | Restore into a separate PVC, mount it in a validation pod, and confirm the expected files or database state. |

---

## Quiz

### Q1: The Cache That Became Critical

Your team runs an image-processing worker that writes intermediate files to `/work`. The pod uses `emptyDir`, and the application now expects unfinished jobs to resume after node maintenance. During a drain, several jobs lose their partial files. What storage change would you recommend, and what tradeoff should you explain to the team?

A) Keep the emptyDir and raise its sizeLimit, because a larger scratch directory remains after the node maintenance that removed the worker.
B) Move the resumable job state to a PVC, and explain the binding, access-mode, reclaim, and performance tradeoffs that durable storage adds.
C) Switch the worker to hostPath so the partial files stay on local disk no matter which node runs the replacement pod.
D) Set medium Memory on the same emptyDir so the cache stays available while the worker is drained and rescheduled.
<details>
<summary>Answer</summary>

B is correct because the partial files are now state that must outlive pod replacement, which is what a PVC provides. A is wrong because a larger sizeLimit still caps an emptyDir that is removed when the pod leaves the node. C is wrong because hostPath exposes a node path and stays on that node instead of following a rescheduled pod. D is wrong because medium Memory still disappears with the pod and also counts against memory.


Move the resumable job state to a PVC because the data now needs to survive pod deletion and rescheduling. `emptyDir` was reasonable while `/work` contained disposable scratch files, but the requirement changed when partial work became recoverable state.

The tradeoff is that durable storage adds binding, provisioning, access-mode, reclaim, and performance considerations. The team should decide whether each worker needs its own `ReadWriteOnce` claim, whether jobs can be retried from object storage instead, and how retained or deleted volumes should be handled after job completion. If the files are only an optimization and can be regenerated cheaply, keeping `emptyDir` with better retry logic may still be simpler.

</details>

### Q2: The PVC That Waits Without Failing

A namespace contains a PVC named `data` that has been `Pending` for several minutes. `kubectl describe pvc data -n app` shows an event indicating that the claim is waiting for the first consumer. The StorageClass uses `WaitForFirstConsumer`, and no pod currently references the claim. What should you do next, and why is deleting the PVC the wrong first move?

A) Delete the PVC and recreate it on another StorageClass so the waiting event disappears immediately.
B) Patch the access mode to ReadWriteMany, which forces the provisioner to ignore WaitForFirstConsumer.
C) Create or inspect the pod that should consume the claim, then check scheduling constraints before you change the claim.
D) Delete the StorageClass so the claim can bind to any static volume in the cluster.
<details>
<summary>Answer</summary>

C is correct because WaitForFirstConsumer delays provisioning until a pod exists and the scheduler can see topology. A is wrong because deleting the claim discards a wait that already matches the class policy. B is wrong because the access mode does not turn off the binding mode or create a consumer. D is wrong because removing the class does not schedule a pod, and the claim still needs a matching volume.


Create or inspect the pod that is supposed to consume the PVC. With `WaitForFirstConsumer`, the cluster may intentionally delay provisioning until a pod exists and scheduling constraints can be evaluated. Without a consuming pod, Kubernetes may not yet know the topology where the volume should be created.

Deleting the PVC is the wrong first move because the observed state matches the StorageClass policy. The next useful checks are the pod spec, node selectors, affinity rules, tolerations, and available nodes. If the pod cannot schedule, the storage will continue to wait because scheduling and provisioning are linked by design.

</details>

### Q3: The Retained Volume After an Accidental Claim Deletion

A developer deletes a PVC that was bound to a PV with `persistentVolumeReclaimPolicy: Retain`. The application is down, the PV is now `Released`, and the team wants to restore service without losing the data. What sequence should you follow before making the volume available again?

A) Delete the Released PV and let the application create a new empty volume, because Retain already removed the old data.
B) Confirm the retained volume and the owner, clear claimRef only when reuse is intended, recreate a matching PVC, and verify the mount.
C) Change the reclaim policy to Delete and wait for Kubernetes to attach the old data to the next claim automatically.
D) Scale the workload back up now, because Released means the volume is already Available for any new claim.
<details>
<summary>Answer</summary>

B is correct because Retain kept the data and Released only preserves the old claim reference until an administrator clears it. A is wrong because the data is not already gone, and deleting the PV would discard the recovery path. C is wrong because flipping the policy to Delete risks removing the volume instead of rebinding it. D is wrong because Released is not Available, so a new claim will not bind until the reference is handled.


First, inspect the PV and confirm it is the expected retained volume. Then confirm that the underlying data should be reused by the same application or owner. In a production setting, take or confirm a backup before changing binding state, because this is the point where human error can expose or overwrite important data.

After the data handling decision is clear, remove the old claim reference or recreate the PV object so it can become `Available` for a new matching PVC. A common exam command is `kubectl patch pv <pv-name> -p '{"spec":{"claimRef": null}}'`, but that command should be used only when reusing the retained data is the intended action. Finally, recreate a matching PVC and verify the pod mounts the data.

</details>

### Q4: The Rollout With a Multi-Attach Error

A Deployment update replaces pods that use a `ReadWriteOnce` PVC. The new pod lands on a different node and stays in `ContainerCreating` with a multi-attach error. An older pod using the same claim is stuck terminating on the previous node. What should you check and repair before changing the application manifest?

A) Change the claim to ReadWriteMany so the new pod and the terminating pod can mount the volume together.
B) Delete the PVC and create an empty replacement so the new node can attach a fresh disk.
C) Find the stuck pod and any VolumeAttachment that still holds the volume, let that attachment clear, and then confirm the new pod mounts.
D) Set storageClassName to an empty string on the live claim so the multi-attach error is ignored.
<details>
<summary>Answer</summary>

C is correct because the ReadWriteOnce volume is still attached through the old pod, and the new pod cannot mount it on another node until that path is gone. A is wrong because changing the access mode does not detach the disk and may not match the backing storage. B is wrong because a new empty claim abandons the existing data and does not clear the attachment. D is wrong because an empty storageClassName opts out of dynamic provisioning and does not clear a VolumeAttachment.


Check which pod and node still hold the volume attachment by listing pods with wide output and inspecting related events or `VolumeAttachment` objects. The problem is that the same `ReadWriteOnce` volume is still attached through the old path, so the new pod cannot mount it on another node.

Repair the competing attachment by allowing the old pod to terminate cleanly or, if the task context allows it and the pod is truly stuck, force deleting the old pod. Then verify that the storage driver detaches the volume and the new pod can attach it. Changing the access mode in the manifest is not the correct first repair because the backing storage may not support multi-node writes and the current attachment conflict would remain.

</details>

### Q5: The Secret Update That Never Reaches the App

An application mounts a single key from a Secret into `/etc/app/password` using `subPath`. The Secret is rotated, but the application continues using the old value even after several minutes. The pod is otherwise healthy. What is the likely cause, and what operational fix should you apply?

A) Edit the Secret again and wait another minute, because the object did not store the rotated value.
B) Recreate the pod so the subPath file is mounted again, and avoid subPath when the file must rotate while the pod runs.
C) Drain the node, because the kubelet refreshes a subPath Secret mount only during a node reboot.
D) Copy the value into the image and mount an emptyDir, because Secret volumes never refresh at all.
<details>
<summary>Answer</summary>

B is correct because a subPath mount does not receive the live Secret update, so the running container keeps the old file until the pod is recreated. A is wrong because the Secret object can already hold the new value while the mount stays stale. C is wrong because a node drain is not the propagation step for this mount. D is wrong because a normal Secret volume can update, and baking the value into the image removes rotation.


The likely cause is the `subPath` mount. ConfigMap and Secret volume mounts can receive updates from the source object, but a file mounted through `subPath` does not update in the same way because the container sees a specific mounted path rather than the refreshed projected directory.

The operational fix is to restart or recreate the pod so the file is mounted again with the new Secret value. For future design, avoid `subPath` for configuration that must rotate live, or build an explicit rollout process that restarts pods when the Secret changes. The important reasoning is that the Secret object changed correctly, but the chosen mount pattern blocked the expected propagation.

</details>

### Q6: The Snapshot Restore That Stays Pending

A team creates a `VolumeSnapshot` before an upgrade and later creates a new PVC with `dataSource` pointing at that snapshot. The restore PVC remains `Pending`. What should you inspect to distinguish a snapshot readiness problem from a normal PVC provisioning problem?

A) Delete the source PVC, because a snapshot restore stays Pending until the original volume is removed.
B) Point dataSource at the source PVC instead of the VolumeSnapshot so the snapshot object can be ignored.
C) Inspect the VolumeSnapshot readiness, class, and controller support, then continue with ordinary PVC checks if the snapshot is ready.
D) Patch the snapshot readyToUse field to true, which creates the restored disk without a provisioner.
<details>
<summary>Answer</summary>

C is correct because a restore claim depends on a ready snapshot and on a satisfiable destination request, so those checks separate the two failure modes. A is wrong because restore creates a new volume and does not require deleting the source claim. B is wrong because swapping in the source PVC describes a clone, not a restore from the recovery point. D is wrong because patching a status field does not make the driver populate a disk.


Inspect the `VolumeSnapshot` first to confirm it exists in the same namespace, is ready to use, and references an appropriate `VolumeSnapshotClass`. Then describe the restore PVC to read events about the data source, StorageClass, capacity, and provisioner behavior. If the snapshot is not ready or the snapshot controller and CSI snapshot support are missing, the PVC cannot restore successfully even if the PVC spec looks reasonable.

If the snapshot is ready, continue with normal PVC checks: requested size, access mode, StorageClass name, default class behavior, and binding mode. The distinction matters because a restore claim has two dependencies: the recovery source must be valid, and the destination storage request must be satisfiable.

</details>

### Q7: The Running Pod That Cannot Write

A pod starts successfully and mounts its PVC at `/data`, but the application logs show `permission denied` when writing `/data/state.db`. The container runs as user ID `1000`. What should you change, and how would you prove the repair worked?

A) Delete the PVC and request a larger volume, because permission denied means the disk is out of space.
B) Change the access mode to ReadOnlyMany so user 1000 can write without a security context.
C) Set fsGroup and runAsUser to 1000 when the driver honors that ownership change, then write and read a file on the mount.
D) Restart the kubelet on the node, because a Running pod cannot be failing inside the mounted filesystem.
<details>
<summary>Answer</summary>

C is correct because the pod is already running and the volume is mounted, so the failure is the process identity on that filesystem. A is wrong because permission denied is not evidence that capacity is exhausted. B is wrong because ReadOnlyMany would forbid writes and does not change the user id. D is wrong because the kubelet already completed the mount, and the proof is a write inside the container.


Add or correct the pod security context so the mounted volume is accessible to the process identity. A common fix is setting pod-level `fsGroup: 1000` and container-level `runAsUser: 1000`, assuming the volume type and driver honor group ownership handling. The key is that this is not a binding failure because the pod is already running and the volume is mounted.

Prove the repair by executing a write and read test against the mounted path, such as `kubectl exec <pod> -- sh -c 'echo ok > /data/probe && cat /data/probe'`. A running pod alone is not proof because the original failure happened inside the filesystem permission boundary.

</details>

---

## Hands-On Exercise

In this exercise, you will create a namespace with several storage patterns, diagnose an intentionally broken pod, repair the claim reference, and verify that a workload can write to mounted storage. The goal is not to memorize commands; the goal is to practice moving from pod symptom to PVC state to manifest repair.

### Scenario

Your team is deploying a small report generator. It needs a temporary cache, a projected pod-name file for diagnostics, and a persistent output directory. A teammate created the pod manifest quickly, but the pod is stuck because the claim name is wrong. Your task is to identify the broken storage reference, fix it, and prove that the container can write to the persistent mount.

### Step 1: Create the namespace and the working PVC

Apply the namespace and a PVC. This PVC uses the cluster's default StorageClass when one exists. If your lab cluster has no default StorageClass, the PVC may remain `Pending`; that is still useful because you can practice reading the event and explaining the missing provisioning path.

```bash
kubectl create namespace storage-review
kubectl apply -n storage-review -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: report-output
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF
```

Check whether the PVC binds. If it remains pending, describe it and decide whether the reason is missing default StorageClass, `WaitForFirstConsumer`, or another provisioning issue.

```bash
kubectl get pvc -n storage-review
kubectl describe pvc report-output -n storage-review
```

### Step 2: Create a broken pod that references the wrong claim

The following pod intentionally references `report-output-wrong`, which does not exist. The pod also uses an `emptyDir` cache and a projected downward API file so you can see multiple volume types in one workload.

```bash
kubectl apply -n storage-review -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: report-generator
spec:
  securityContext:
    fsGroup: 1000
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      echo "pod=$(cat /meta/pod-name)" > /cache/report.txt
      cp /cache/report.txt /output/report.txt
      cat /output/report.txt
      sleep 3600
    securityContext:
      runAsUser: 1000
    volumeMounts:
    - name: cache
      mountPath: /cache
    - name: output
      mountPath: /output
    - name: pod-meta
      mountPath: /meta
      readOnly: true
  volumes:
  - name: cache
    emptyDir:
      sizeLimit: 64Mi
  - name: output
    persistentVolumeClaim:
      claimName: report-output-wrong
  - name: pod-meta
    downwardAPI:
      items:
      - path: pod-name
        fieldRef:
          fieldPath: metadata.name
EOF
```

Describe the pod and find the storage event. Do not fix the manifest until you can state which volume failed and which Kubernetes object is missing.

```bash
kubectl get pod report-generator -n storage-review
kubectl describe pod report-generator -n storage-review
```

### Step 3: Repair the claim reference

Because pod volume references are part of the pod spec, the practical repair is to delete and recreate the pod with the correct claim name. In controller-managed workloads, you would update the Deployment, StatefulSet, or Job template instead of hand-editing a standalone pod.

```bash
kubectl delete pod report-generator -n storage-review
kubectl apply -n storage-review -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: report-generator
spec:
  securityContext:
    fsGroup: 1000
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      echo "pod=$(cat /meta/pod-name)" > /cache/report.txt
      cp /cache/report.txt /output/report.txt
      cat /output/report.txt
      sleep 3600
    securityContext:
      runAsUser: 1000
    volumeMounts:
    - name: cache
      mountPath: /cache
    - name: output
      mountPath: /output
    - name: pod-meta
      mountPath: /meta
      readOnly: true
  volumes:
  - name: cache
    emptyDir:
      sizeLimit: 64Mi
  - name: output
    persistentVolumeClaim:
      claimName: report-output
  - name: pod-meta
    downwardAPI:
      items:
      - path: pod-name
        fieldRef:
          fieldPath: metadata.name
EOF
```

Wait for the pod to run. If the PVC is still pending because your cluster lacks dynamic provisioning, describe the PVC and write down the missing storage condition instead of forcing unrelated changes.

```bash
kubectl get pod report-generator -n storage-review -w
```

### Step 4: Verify read and write behavior

Once the pod is running, prove that the application wrote the expected file to the persistent mount. This verification checks the storage path, the projected metadata path, and the security context in one small test.

```bash
kubectl exec -n storage-review report-generator -- cat /output/report.txt
kubectl exec -n storage-review report-generator -- sh -c 'echo verified >> /output/report.txt && cat /output/report.txt'
```

### Step 5: Clean up the lab resources

Clean up the namespace when you are finished. If your cluster created a dynamically provisioned volume with a `Delete` reclaim policy, the backing storage should be removed by the provisioner. If your environment uses a different reclaim policy, inspect the PV after cleanup.

```bash
kubectl delete namespace storage-review
kubectl get pv
```

### Card A — A memory-backed emptyDir survives node drain because the cache is stored on the node disk.

<details>
<summary>Reveal the failure layer and next action</summary>

**False.** Failure layer: medium Memory counts those bytes against memory, and the volume is removed when the pod leaves the node, so a drain does not leave the cache on node disk. Next action: put files that must be recovered after rescheduling on a PersistentVolumeClaim, and keep a sizeLimit only for scratch that may disappear with the pod.

</details>

### Card B — A PVC waiting for its first consumer should be deleted and recreated with a different StorageClass.

<details>
<summary>Reveal the failure layer and next action</summary>

**False.** Failure layer: WaitForFirstConsumer is the class policy, so a claim with no pod can stay Pending until a consumer is scheduled. Next action: inspect the pod spec, selectors, taints, and nodes before you delete the claim or change its class.

</details>

### Card C — After a Retain PV becomes Released, the data is already gone, so the only recovery is a new empty volume.

<details>
<summary>Reveal the failure layer and next action</summary>

**False.** Failure layer: Retain keeps the PersistentVolume and the underlying data, and Released means the old claim reference is still recorded. Next action: confirm the owner and any required backup, then clear claimRef or recreate the PV and bind a matching claim.

</details>

### Card D — A Secret file mounted with subPath updates in place within a minute of the Secret change.

<details>
<summary>Reveal the failure layer and next action</summary>

**False.** Failure layer: a subPath mount does not receive the live update, so the file stays stale while the pod keeps running. Next action: recreate the pod so the file is mounted again, and avoid subPath when the value must change without a new pod.

</details>

**Success Criteria**: You can trace the stuck pod to the missing claim, separate each volume lifecycle in the repaired spec, read a pending claim against its class, prove a non-root write on the mounted path, and contrast Delete with Retain after cleanup.

- [ ] You can explain why the first pod stayed in `ContainerCreating` and identify the exact missing claim reference from the pod events.

- [ ] You can distinguish the `emptyDir`, downward API, and PVC-backed volumes in the pod spec and explain what lifecycle each one has.

- [ ] You can describe the PVC state and decide whether `Pending` means a real provisioning problem or expected `WaitForFirstConsumer` behavior.

- [ ] You can recreate the pod with the correct `claimName` and verify that the mounted output path accepts writes from the non-root container user.

- [ ] You can explain what would happen to the persistent data if the PVC's bound PV used `Delete` versus `Retain` as its reclaim policy.

---

## Next Module

Proceed to [Part 5: Troubleshooting](/k8s/cka/part5-troubleshooting/) to build a broader diagnostic workflow for Kubernetes cluster and workload failures beyond this storage rehearsal.

## Sources

- [cncf.io: cka](https://www.cncf.io/training/certification/cka/) — The CNCF CKA page explicitly describes the exam as performance-based, command-line, and lists Storage at 10%.
- [kubernetes.io: volumes](https://kubernetes.io/docs/concepts/storage/volumes/) — The Volumes doc directly states the `emptyDir` lifecycle and its behavior across container crashes.
- [kubernetes.io: pod security standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — The Pod Security Standards page explicitly lists `hostPath` volumes as forbidden in the Baseline policy.
- [kubernetes.io: persistent volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) — The Persistent Volumes doc states that PVs are cluster resources and claims must exist in the same namespace as the Pod using them.
- [kubernetes.io: storage classes](https://kubernetes.io/docs/concepts/storage/storage-classes/) — The StorageClass doc directly explains `WaitForFirstConsumer` and its topology-aware scheduling behavior.
- [kubernetes.io: volume pvc datasource](https://kubernetes.io/docs/concepts/storage/volume-pvc-datasource/) — The CSI Volume Cloning doc directly states the `dataSource` model, CSI dependency, and same-namespace requirement.
- [kubernetes.io: volume snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/) — The Volume Snapshots doc explicitly says the API objects are CRDs, snapshot support is CSI-only, and controller-side components are required.
- [kubernetes.io: kubernetes 1.20 volume snapshot moves to ga](https://kubernetes.io/blog/2020/12/10/kubernetes-1.20-volume-snapshot-moves-to-ga/) — The official Kubernetes snapshot GA post explicitly says snapshot restore provisions a new volume and does not support reverting an existing PVC.
- [kubernetes.io: security context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/) — The Security Context task page documents `fsGroup` effects and notes CSI-driver-specific support for ownership and permission handling.
- [Kubernetes documentation: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/) — verified 2026-09-26: a container using a Secret as a subPath volume mount does not receive automated Secret updates.
