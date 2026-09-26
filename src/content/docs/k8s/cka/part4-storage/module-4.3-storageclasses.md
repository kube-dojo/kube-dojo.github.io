---
revision_pending: false
title: "Module 4.3: StorageClasses & Dynamic Provisioning"
slug: k8s/cka/part4-storage/module-4.3-storageclasses
sidebar:
  order: 4
lab:
  id: cka-4.3-storageclasses
  url: https://killercoda.com/kubedojo/scenario/cka-4.3-storageclasses
  duration: "35 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Automation of storage provisioning
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: [Module 4.2 (PV & PVC)](../module-4.2-pv-pvc/), [Module 1.2 (CSI)](../../part1-cluster-architecture/module-1.2-extension-interfaces/)

---

## What You'll Be Able to Do

After this module, you will be able to make and verify the following storage decisions in a cluster:

- **Design** StorageClasses for dynamic provisioning across local, AWS, GCP, and Azure-style clusters.
- **Configure** default behavior, explicit opt-out behavior, reclaim policies, binding modes, parameters, and expansion settings.
- **Evaluate** `Immediate` versus `WaitForFirstConsumer` binding for zonal, local, and networked storage backends.
- **Diagnose** pending PVCs, wrong-zone attachments, failed expansion, invalid parameters, and provisioner-controller failures.

---

## Why This Module Matters

Hypothetical scenario: a platform team has a cluster with three node pools, two availability zones, and several teams creating databases during release week. If every new database waits for an administrator to handcraft a PersistentVolume, the storage workflow becomes a ticket queue instead of a self-service platform. If dynamic provisioning is enabled without good defaults, the opposite problem appears: teams get volumes quickly, but they may land in the wrong zone, use the wrong disk class, delete data when a PVC is removed, or stay pending because the provisioner name does not match any controller.

StorageClasses are the policy layer between a developer's storage request and the system that creates real storage. In Module 4.2, you saw how a PersistentVolumeClaim can bind to an existing PersistentVolume. This module adds the automation step: a PVC can point at a StorageClass, and Kubernetes can ask a provisioner to create a matching PV on demand. That sounds simple, but the details decide whether a stateful workload starts cleanly, survives an accidental PVC deletion, and grows when data pressure arrives.

Think of static provisioning like ordering custom furniture: somebody measures the room, buys material, builds the shelf, and only then can the user put books on it. Dynamic provisioning is closer to a vending machine with several labeled buttons. The StorageClass is the machine configuration, the PVC is the selection, the provisioner is the mechanism behind the panel, and the resulting PV is the storage that drops into the slot. Your job on the CKA exam is to choose the right button, read the events when the machine jams, and know which settings prevent common operational surprises.

---

## StorageClasses Automate the PV Factory

Static provisioning and dynamic provisioning solve the same binding problem at different levels of automation. With static provisioning, an administrator creates PV objects first, often after manually creating a disk, file share, export, or local path outside Kubernetes. With dynamic provisioning, the administrator creates a StorageClass once, and ordinary PVCs become enough information for the cluster to create new backing storage. The CKA distinction matters because many troubleshooting questions start with a PVC in `Pending`, and your first task is to decide whether Kubernetes is waiting for an existing PV or waiting for a provisioner to create one.

```
+----------------------------------------------------------------------+
|               Static vs Dynamic Provisioning                         |
|                                                                      |
|   STATIC (Manual)                   DYNAMIC (Automatic)              |
|   ---------------                   -------------------              |
|                                                                      |
|   1. Admin creates PV               1. Admin creates StorageClass    |
|      |                                 |                             |
|      v                                 v                             |
|   2. Dev creates PVC                2. Dev creates PVC               |
|      |                                 |                             |
|      v                                 v                             |
|   3. Kubernetes binds               3. Provisioner creates PV        |
|      PVC to existing PV                |                             |
|                                        v                             |
|                                     4. Kubernetes binds PVC to new PV|
|                                                                      |
|   Pro: Full control                 Pro: Self-service, scalable      |
|   Con: Admin bottleneck             Con: Less control per volume     |
+----------------------------------------------------------------------+
```

The diagram hides one important implementation detail: Kubernetes itself does not know how to create every cloud disk or local directory. A StorageClass contains a `provisioner` string, and an external or in-tree-compatible controller watches for PVCs that reference that string. In modern Kubernetes, Container Storage Interface drivers are the normal path for production storage. Older in-tree provisioner names still appear in legacy material and older clusters, so you should recognize them, but new designs should prefer the CSI driver name that your platform actually installed.

The central object is intentionally small. It does not define a particular volume name or a particular node. Instead, it defines how a future PV should be created, what backend parameters to send, what reclaim policy to copy onto the dynamically created PV, when binding should happen, and whether PVCs may later request more space. Read this example as a contract, not as a generic template to paste into every cloud.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"  # Optional
provisioner: kubernetes.io/aws-ebs    # Legacy in-tree name; prefer CSI in new clusters
parameters:                            # Provisioner-specific settings
  type: gp3
  iopsPerGB: "10"
reclaimPolicy: Delete                  # What happens when PVC deleted
volumeBindingMode: WaitForFirstConsumer  # When to provision
allowVolumeExpansion: true             # Can resize later?
mountOptions:                          # Mount options for volumes
  - discard
```

Each field has a different blast radius. `parameters` affect how the backend disk or share is created. `reclaimPolicy` becomes the deletion behavior of the PV, which can mean the difference between test cleanup and accidental production data loss. `volumeBindingMode` affects scheduling, especially when the storage can only attach to nodes in a particular zone. `allowVolumeExpansion` affects future recovery options, because a PVC can be expanded only when its class and driver support expansion.

| Provisioner | Cloud/Platform | Storage Type |
|-------------|---------------|--------------|
| kubernetes.io/aws-ebs | AWS | EBS volumes |
| kubernetes.io/gce-pd | GCP | Persistent Disk |
| kubernetes.io/azure-disk | Azure | Managed Disk |
| kubernetes.io/azure-file | Azure | Azure Files |
| ebs.csi.aws.com | AWS (CSI) | EBS via CSI |
| pd.csi.storage.gke.io | GCP (CSI) | PD via CSI |
| rancher.io/local-path | kind | Local path |
| k8s.io/minikube-hostpath | minikube | Host path |

This table is useful for recognition, but it is not a substitute for checking the cluster. The CKA exam environment may use a local provisioner, while production clusters usually have a cloud or storage-vendor CSI driver. Always inspect `kubectl get storageclass` and the CSI controller pods before assuming a provisioner name. A single character mismatch in the `provisioner` field is enough to leave every matching PVC waiting forever.

**Pause and predict:** a PVC requests `storageClassName: fast-ssd`, but no running component watches `ebs.csi.aws.com`. What status and event category should you expect, and what must happen before a PV appears?

<details>
<summary>Reveal the prediction</summary>

The PVC stays `Pending`, and its events typically report that it is waiting for external provisioning. Kubernetes records the request but cannot create the cloud disk itself; a matching external provisioner must perform the backend work. Inspect the class, PVC events, and provisioner deployment to find the missing link.

</details>

Compare your prediction with the claim status and event category, then trace each observation to the object that can confirm it during an exam.

---

## Designing Classes for Real Provisioners

A StorageClass should represent an operational choice that learners and application teams can understand. Names such as `fast`, `standard`, `encrypted-retain`, and `local-dev` are more useful than names that only repeat a driver string. The name is what a PVC author sees, so it should communicate cost, performance, durability, or intended use. Under the name, the platform team can hide the provider-specific settings that most developers should not need to memorize.

The following basic example preserves the old in-tree AWS provisioner pattern because you may still see it in legacy practice material. For Kubernetes 1.35-era production clusters, prefer the CSI class shown after it when the EBS CSI driver is installed. The conceptual fields are still the same: choose the backend, set the policy, delay binding for zonal storage, and decide whether expansion is allowed.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp2
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

For AWS EBS, the CSI driver provisioner is `ebs.csi.aws.com`. EBS volumes are zonal, so `WaitForFirstConsumer` is usually the safer binding mode because it lets the scheduler choose a node before the disk is created. The CSI example below uses `Retain` to protect data, but that choice is not universally correct. It is sensible for production databases and risky for throwaway environments because deleted PVCs can leave billable disks behind.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ebs
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iopsPerGB: "50"
  throughput: "125"
  encrypted: "true"
  kmsKeyId: "arn:aws:kms:us-east-1:123456789:key/abc-123"
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

For GCP Persistent Disk, the CSI provisioner name commonly used by GKE is `pd.csi.storage.gke.io`. The `replication-type` parameter changes the durability and topology model, so it should be chosen deliberately rather than copied from a lab. Regional disks can improve availability for some designs, but they also have cost and scheduling implications. The exam usually cares less about the cloud-specific parameter names and more about whether you understand that parameters belong to the provisioner, not to the PVC.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: pd.csi.storage.gke.io
parameters:
  type: pd-ssd
  replication-type: regional-pd    # For HA
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

For Azure Disk, the CSI provisioner name is `disk.csi.azure.com`. Managed disks are also topology-sensitive, so delayed binding avoids the same wrong-zone class of problem you saw with EBS and Persistent Disk. The parameter names are different because Azure has different storage product names. This is why a StorageClass copied from one cloud rarely works on another without changing both the provisioner string and the parameter keys.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: managed-premium
provisioner: disk.csi.azure.com
parameters:
  skuName: Premium_LRS          # Standard_LRS, Premium_LRS, StandardSSD_LRS
  kind: managed                 # managed, dedicated, shared
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

Local development clusters also have provisioners, but their behavior is closer to local filesystem allocation than durable cloud storage. A kind cluster often uses Rancher's local-path provisioner, and minikube commonly exposes a hostPath-style provisioner. These are excellent for learning dynamic provisioning mechanics. They should not teach you that a host directory has the same availability or mobility as a cloud disk, because local storage ties data to the node that hosts it.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-path
provisioner: rancher.io/local-path
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: k8s.io/minikube-hostpath
reclaimPolicy: Delete
volumeBindingMode: Immediate
```

The local examples are intentionally simple because they are usually used in one-node or small lab clusters. In a multi-node lab, local-path provisioning can still be useful, but it makes placement part of correctness. If the data lives on one node, a replacement pod must land where the data exists or the storage layer must recreate it elsewhere. That is not a Kubernetes bug; it is the natural consequence of local storage.

Before running this, what output do you expect from `kubectl get storageclass` on your own cluster? Predict the provisioner names first, then run the command and compare your mental model with the actual cluster. This habit prevents a common exam mistake: writing a perfectly shaped StorageClass that references a provisioner the environment does not have.

```bash
kubectl get storageclass
kubectl get storageclass -o custom-columns='NAME:.metadata.name,PROVISIONER:.provisioner,DEFAULT:.metadata.annotations.storageclass\.kubernetes\.io/is-default-class,VOLUME_BINDING:.volumeBindingMode'
```

---

## Defaults, Opt-Outs, and Binding Timing

A default StorageClass answers a specific question: what should happen when a PVC does not specify `storageClassName`? If exactly one default exists, Kubernetes can apply that class to a PVC that omits the field, and dynamic provisioning can begin. If no default exists, a PVC without a class cannot trigger default dynamic provisioning. If more than one default exists, Kubernetes uses the most recently created default class, which is deterministic but often surprising for operators.

Marking a class as default is done with an annotation. This makes default selection an administrative policy rather than a special object type. A class can be default for convenience, but it should be boring, broadly useful, and safe enough for most PVCs. A default class with aggressive cost settings or `Retain` behavior can create expensive cleanup work for every team that forgets to name a class explicitly.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"  # The default annotation
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
```

```bash
kubectl patch storageclass standard -p '{"metadata": {"annotations": {"storageclass.kubernetes.io/is-default-class": "true"}}}'
```

```bash
kubectl get storageclass
# NAME                 PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE
# standard (default)   kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer
# fast-ssd             kubernetes.io/aws-ebs   Delete          Immediate
```

The opposite of defaulting is explicit opt-out. If a PVC leaves `storageClassName` absent, Kubernetes may apply the default class. If a PVC sets `storageClassName: ""`, Kubernetes treats that as an intentional request for no class, so the claim only matches PVs that also have no class. This tiny distinction is a common source of exam questions because an omitted field and an empty string look similar but behave differently.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-claim
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  # No storageClassName specified - uses default if one exists
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: static-only-claim
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: ""    # Empty string means no dynamic provisioning
```

Binding mode controls when Kubernetes should bind or provision the PV. `Immediate` means the claim can bind or provision as soon as the PVC exists. `WaitForFirstConsumer` means Kubernetes delays binding or provisioning until a pod that uses the claim is scheduled. That delay is not just a performance detail; it gives the scheduler a chance to consider node topology, zone labels, pod constraints, and volume placement at the same time.

```
+----------------------------------------------------------------------+
|                    Volume Binding Modes                              |
|                                                                      |
|   IMMEDIATE                         WAITFORFIRSTCONSUMER             |
|   ---------                         --------------------             |
|                                                                      |
|   PVC Created                       PVC Created                      |
|       |                                 |                            |
|       v                                 v                            |
|   PV Provisioned                    PVC stays Pending                |
|   immediately                           |                            |
|       |                                 |                            |
|       |                             Pod scheduled                    |
|       |                                 |                            |
|       |                                 v                            |
|       |                             PV Provisioned                   |
|       |                             (on same zone as pod)            |
|       |                                 |                            |
|       v                                 v                            |
|   Pod scheduled                     Pod can use storage              |
|   (may fail if wrong zone)                                             |
|                                                                      |
+----------------------------------------------------------------------+
```

The wrong-zone problem is easiest to understand with zonal disks. Suppose an EBS volume is created before a pod is scheduled. The provisioner chooses `us-east-1a`, then the scheduler later places the pod on a node in `us-east-1b`. The pod cannot attach that EBS volume because the volume and node are in different zones, so the workload stalls even though both the PVC and the pod specs look reasonable.

```
Node: us-east-1a          Node: us-east-1b
+-------------+           +-------------+
|             |           |    Pod      |  <- Scheduler puts pod here
|             |           |   (needs    |
|             |           |   storage)  |
+-------------+           +-------------+
      ^
      |
   EBS Volume             X Volume in wrong zone
   (provisioned           X Pod cannot start
    immediately in 1a)
```

`WaitForFirstConsumer` changes the order. The PVC can exist without a PV, the scheduler places the pod on a node that satisfies the pod constraints, and then provisioning happens in the correct topology. This mode is a strong default for zonal block storage and local storage. It is less important for truly networked storage, such as NFS-style backends, because the storage endpoint is reachable from many nodes without zone-specific attachment.

```
Node: us-east-1a          Node: us-east-1b
+-------------+           +-------------+
|             |           |    Pod      |  <- Scheduler puts pod here
|             |           |   (needs    |
|             |           |   storage)  |
+-------------+           +-------------+
                                ^
                                |
                          EBS Volume      OK Volume in correct zone
                          (provisioned    OK Pod starts successfully
                           in 1b AFTER
                           pod scheduled)
```

| Mode | Use Case |
|------|----------|
| Immediate | NFS, distributed storage, zone-less storage |
| WaitForFirstConsumer | Zone-specific storage (EBS, GCE PD, Azure Disk), local storage |

**Pause and predict:** a StorageClass uses `volumeBindingMode: Immediate` for AWS EBS, while the consuming pod requires a node in `us-east-1b`. Predict the PVC and pod states, then choose the first evidence you would inspect if the pod cannot start.

<details>
<summary>Reveal the prediction</summary>

Immediate binding can provision a zonal volume before the scheduler knows where the pod must run. The PVC may be `Bound` to a PV in another zone while the pod remains `Pending` because its required node cannot use that PV. Compare the PV node affinity with the pod's node constraints and events. `WaitForFirstConsumer` coordinates placement for future claims; changing the class later does not relocate an existing volume.

</details>

Compare the predicted claim and pod states with the events you would inspect, and decide which observation would justify changing the class for future requests.

One more defaulting detail is worth memorizing for the exam. The `reclaimPolicy` on a StorageClass is copied to dynamically created PVs at creation time. Changing or recreating the StorageClass later does not rewrite existing PVs. If a production class accidentally used `Delete`, fixing the class only protects future volumes; existing PVs need direct review and, if appropriate, a direct PV reclaim-policy patch.

```bash
kubectl get persistentvolumeclaim my-claim -o jsonpath='{.spec.volumeName}'
kubectl patch persistentvolume pv-001 -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

---

## Expansion, Parameters, and Mount Behavior

Volume expansion is a recovery feature as much as a convenience feature. Databases, build caches, artifact repositories, and logging components grow over time, and recreating a PVC during an incident is usually the last thing you want. A StorageClass with `allowVolumeExpansion: true` gives you the option to increase a PVC request later, as long as the driver and volume type support expansion. Kubernetes does not support shrinking PVCs, so capacity planning still matters.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: expandable
provisioner: kubernetes.io/aws-ebs
allowVolumeExpansion: true    # Must be true to resize PVCs
parameters:
  type: gp3
```

Expanding a PVC starts with increasing the requested storage. The request must move upward, not downward, and the StorageClass must allow expansion. The backend controller then resizes the real disk or share, and the node side may need to grow the filesystem when the volume is mounted. Different drivers vary in online expansion behavior, so do not assume every filesystem grows at the exact moment the PVC object changes.

```bash
# Original PVC with 10Gi
kubectl get persistentvolumeclaim my-claim
# NAME       STATUS   VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS
# my-claim   Bound    pv-001   10Gi       RWO            expandable

# Edit to request more space
kubectl patch persistentvolumeclaim my-claim -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'

# Or edit manually
kubectl edit persistentvolumeclaim my-claim
# Change spec.resources.requests.storage to 20Gi
```

```
+---------------------------------------------------------------------+
|                    PVC Expansion Process                            |
|                                                                     |
|   1. Edit PVC --> 2. Controller resizes      --> 3. Filesystem      |
|      (increase       underlying storage             expansion       |
|       size)          (for example, EBS volume)      (when mounted)  |
|                                                                     |
|   Status shows:                                                     |
|   - "Resizing" - storage backend being resized                      |
|   - "FileSystemResizePending" - waiting for pod to mount            |
|                                                                     |
|   Note: expansion may require remount or restart for some drivers   |
+---------------------------------------------------------------------+
```

When expansion appears stuck, read the PVC conditions before changing more objects. `Resizing` usually points at backend work, while `FileSystemResizePending` means the backend capacity has changed but the mounted filesystem still needs to grow. That second condition is not automatically a failure. It may clear when a pod mounts the volume, or it may require a restart depending on the driver and filesystem.

```bash
kubectl describe persistentvolumeclaim my-claim

# Look for conditions:
# Conditions:
#   Type                      Status
#   ----                      ------
#   FileSystemResizePending   True     # Waiting for filesystem resize
#   Resizing                  True     # Backend resize in progress
```

Parameters are where provider-specific behavior lives. The Kubernetes API stores them as strings and passes them to the provisioner; Kubernetes does not understand every storage product knob. That means invalid keys may fail only when the provisioner tries to act. When a PVC remains pending after a StorageClass change, compare the parameter names with the driver documentation and the controller logs rather than assuming YAML syntax is the problem.

```yaml
parameters:
  type: gp3                    # gp2, gp3, io1, io2, st1, sc1
  iopsPerGB: "50"              # For gp3/io1/io2
  throughput: "250"            # For gp3 (MiB/s)
  encrypted: "true"
  kmsKeyId: "arn:aws:kms:..."
  fsType: ext4                 # ext4, xfs
```

```yaml
parameters:
  type: pd-ssd                 # pd-standard, pd-ssd, pd-balanced
  replication-type: none       # none, regional-pd
  disk-encryption-kms-key: "projects/..."
  fsType: ext4
```

```yaml
parameters:
  skuName: Premium_LRS               # Standard_LRS, Premium_LRS, StandardSSD_LRS
  kind: managed                      # managed, dedicated, shared
  cachingMode: ReadOnly
  fsType: ext4
```

Mount options are copied into the resulting PV and used when the volume is mounted. They are powerful because they can affect filesystem semantics, performance, and debuggability. They are also easy to misuse because Kubernetes does not validate every option against every filesystem. Treat mount options as a storage-driver and operating-system decision, not as a harmless place to experiment in a shared class.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: with-mount-options
provisioner: kubernetes.io/aws-ebs
mountOptions:
  - discard
  - noatime
  - nodiratime
parameters:
  type: gp3
  fsType: ext4
```

Stop and think: a PVC was created from a StorageClass that has `allowVolumeExpansion: false`, and the database is running out of space. Can you change the StorageClass to `allowVolumeExpansion: true` and then expand that PVC? Your operational answer should mention immutability, existing PV behavior, and the safer migration path if the direct expansion path is blocked.

The practical recovery depends on the exact class and driver, but the design lesson is clear. Set `allowVolumeExpansion: true` for classes where future growth is plausible, especially database and stateful-service classes. Use quotas, admission controls, and cost review to control abuse. Do not remove expansion capability just because you want people to plan better; incidents often arrive after the original estimate stops being useful.

---

## Troubleshooting Dynamic Provisioning Failures

When dynamic provisioning fails, the PVC usually remains `Pending`. That is not enough information by itself because `Pending` can mean the PVC is intentionally waiting for the first consumer, waiting for a static PV, waiting for an external provisioner, or failing repeatedly because the backend rejected the request. Your first move should be to read events on the PVC, then inspect the StorageClass, then inspect the provisioner controller. That sequence follows the request path from claim to policy to actor.

```bash
kubectl describe persistentvolumeclaim dynamic-pvc
```

The events section often tells you whether the problem is structural or backend-specific. A message about waiting for the first consumer may be healthy when the class uses `WaitForFirstConsumer`. A message about an unknown provisioner points at the StorageClass or missing controller. A cloud API error, quota error, permission error, or invalid parameter points at the CSI controller logs and the provider-side configuration.

```bash
kubectl get storageclass fast -o yaml
kubectl get pods -n kube-system
```

If the PVC event lacks detail, check the controller logs for the relevant CSI driver. The namespace and deployment name vary by installation, so list the system pods rather than memorizing one deployment name. The command below preserves the original AWS EBS example, but the same method applies to other drivers. Look for failed create-volume calls, invalid parameters, permission denials, topology errors, and quota messages.

```bash
# Example for AWS EBS CSI driver
kubectl logs -n kube-system deploy/ebs-csi-controller -c csi-provisioner
```

You should also verify whether delayed binding is the expected state. With `WaitForFirstConsumer`, a PVC can remain pending until a pod uses it, and that may be correct. If a learner sees `Pending` and immediately changes the StorageClass to `Immediate`, they may create the wrong-zone problem the delayed mode was designed to prevent. Instead, create or inspect the consuming pod and read scheduler events together with PVC events.

```bash
kubectl describe pod dynamic-pod
kubectl get events --sort-by=.lastTimestamp
```

A compact diagnostic path keeps you from chasing noise. First, check whether the PVC names a class or relies on a default. Second, check whether that class exists and has the expected provisioner string. Third, check whether binding should wait for a consumer. Fourth, check whether a controller pod is running for that provisioner. Fifth, read controller logs only after you know which driver should be acting.

```bash
kubectl get persistentvolumeclaim dynamic-pvc -o jsonpath='{.spec.storageClassName}{"\n"}'
kubectl get storageclass
kubectl describe storageclass fast
kubectl get persistentvolume
```

Exercise scenario: a PVC has no `storageClassName`, the cluster has two default StorageClasses, and the resulting PV uses the slower backend. The fix is not to patch the PVC after provisioning and hope the disk changes. Review the default annotations, remove the unintended default, and create a new claim if the workload needs a different class. Dynamic provisioning chooses the class at claim time, not after the volume has already been created.

### Worked Failure Walkthroughs

The fastest way to diagnose StorageClass issues is to separate control-plane intent from backend execution. The PVC tells you what the workload requested, the StorageClass tells you which policy Kubernetes applied, and the provisioner logs tell you what happened when the backend was contacted. Those are three different layers, and mixing them together leads to bad fixes. For example, changing a pod spec cannot repair an invalid StorageClass parameter, and changing a StorageClass cannot move a volume that was already created in the wrong zone.

```
+-------+     +--------------+     +------------------+     +------+
| PVC   | --> | StorageClass | --> | CSI provisioner  | --> | PV   |
+-------+     +--------------+     +------------------+     +------+
```

Consider a PVC that remains pending in a class using `WaitForFirstConsumer`. If no pod references the claim, the pending state is evidence that the class is doing what it was told to do. If a pod does reference the claim and the pod cannot schedule, the issue may be node selectors, taints, resource pressure, or topology constraints. If the pod schedules and provisioning still fails, then the evidence moves toward the provisioner and backend. That progression keeps you from "fixing" delayed binding when the actual problem is scheduling.

The wrong-zone failure has a different signature. The PVC may already be bound, and the pod may be stuck during attach or mount instead of pure scheduling. In that case, read the PV node affinity and the pod's selected node, then compare zone labels. If the volume is already bound to a zone that cannot serve the pod, switching the StorageClass to `WaitForFirstConsumer` only protects future claims. The existing claim usually needs a new volume, a data migration, or a deliberate rescheduling strategy that places the pod where the volume can attach.

```
+----------+     +-------------+     +-----------------+
| PV zone  | --> | Node zone   | --> | Attach result   |
+----------+     +-------------+     +-----------------+
| 1a       |     | 1a          |     | attach succeeds |
| 1a       |     | 1b          |     | attach fails    |
+----------+     +-------------+     +-----------------+
```

Parameter failures often look like ordinary pending PVCs until you inspect events. A typo in a storage account type, disk type, encryption parameter, or filesystem option can pass Kubernetes API validation because the parameter map is mostly opaque to Kubernetes. The CSI driver is the component that knows whether the backend accepts the option. That is why a valid YAML file can still produce a failed provisioning event, and why vendor documentation belongs in the troubleshooting loop.

Default-class surprises are especially common during migrations. A platform team may introduce a new default class while the older one still has the default annotation, or a lab may patch a temporary class to default and forget to remove it. PVC authors who omit `storageClassName` have delegated the choice to the cluster. If that delegation is not intentional, write the class explicitly. If the claim must bind to a static PV, use the empty string, not omission.

```
+---------------------+     +-------------------------+
| PVC field           |     | Kubernetes behavior     |
+---------------------+     +-------------------------+
| omitted             | --> | may use default class   |
| storageClassName:"" | --> | no dynamic provisioning |
| storageClassName:X  | --> | request class X         |
+---------------------+     +-------------------------+
```

Expansion failures require a calm read of conditions. A claim that still reports the old capacity is not automatically broken after a resize patch. The backend may be resizing, or the filesystem may be waiting for a mount operation. Read `kubectl describe persistentvolumeclaim` before restarting workloads or replacing the claim. If the class did not allow expansion when the claim was created, plan a controlled migration rather than trying to shrink, mutate, or force an unsupported path.

Reclaim-policy mistakes demand a different kind of caution because they affect deletion. If a production class used `Delete`, the dangerous moment is not claim creation; it is claim deletion. A direct PV reclaim-policy patch can protect already created PVs, but it should be done after confirming which volumes contain data that must be retained. Conversely, a development class using `Retain` is not immediately dangerous to data, but it can quietly accumulate orphaned disks and cost.

```
+------------+     +----------------+     +--------------------+
| PVC action | --> | PV policy      | --> | Backend result     |
+------------+     +----------------+     +--------------------+
| delete     |     | Delete         |     | remove storage     |
| delete     |     | Retain         |     | keep storage       |
+------------+     +----------------+     +--------------------+
```

The CKA exam often rewards exact observation over broad theory. If you can show the claim's class, describe the class, inspect events, and read the right controller logs, you can usually locate the failing layer quickly. Avoid changing multiple objects at once during diagnosis. Make one change that corresponds to one hypothesis, then re-check events. This discipline matters because storage objects can create real backend resources, and careless retries can leave volumes behind.

There is also a design lesson hiding inside every failure. Pending PVCs teach you to name classes clearly and install the right provisioner. Wrong-zone volumes teach you to delay binding for topology-aware storage. Expansion incidents teach you to enable growth before pressure arrives. Reclaim-policy accidents teach you to separate disposable and protected data. A good module exercise is not just a way to pass the lab; it is a rehearsal for reading those production signals in order.

### Provider-Aware Design Notes

Cloud block storage is convenient because it feels like a disk, but that simplicity is scoped by topology and attachment rules. EBS, Persistent Disk, and Azure Disk classes should make zone behavior explicit through delayed binding unless your platform has a specific reason to choose otherwise. Their performance settings should be tied to workload expectations, not to a generic idea of "fast." A cache, a relational database, and a build workspace may all use block storage, yet they have different retention and expansion needs.

Network file storage has a different shape. It may be reachable from many nodes, and it may support access modes that block disks cannot. That can make `Immediate` acceptable because the storage is not created in a single attach zone, but it does not remove the need to understand backend limits. Shared filesystems can have their own quotas, permissions, latency patterns, and failure modes. The StorageClass still represents a policy contract, even when zone placement is less central.

Local-path and hostPath-style dynamic provisioning are excellent teaching tools because they make PV creation visible in a small cluster. They are also the easiest place to learn the wrong lesson. A local path is not magically replicated because Kubernetes created a PV object for it. If the node is lost, drained, or unavailable, the data path can be unavailable too. Use local provisioners for labs, edge cases, and deliberate local-storage designs, not as a casual substitute for durable storage.

CSI sidecars explain why StorageClass troubleshooting often requires more than one controller log. The external provisioner watches PVCs and creates volumes, the external resizer reacts to expansion requests, and other sidecars handle attachment, snapshots, or registration depending on the driver. You do not need to memorize every sidecar for the CKA exam, but you should know that a storage failure may occur after the PVC is accepted. Kubernetes stores desired state; CSI components reconcile that state with the backend.

For a production platform, class names should be part of the user interface. A developer should not need to know that `gp3` is a disk type just to choose safe default storage, but the platform team should document what `standard`, `database-retain`, or `shared-rwx` means. Good names reduce support tickets because they guide behavior before anyone writes YAML. Bad names force users to read provider parameters and guess which class protects their workload.

Admission policy can make StorageClasses safer without making them mysterious. A cluster can require explicit classes in production namespaces, restrict expensive classes to approved teams, or prevent `Retain` classes in disposable environments. Those policies sit outside the StorageClass object, but they reinforce the same design goals. The module focuses on Kubernetes objects because that is what the exam tests, while real platforms often add policy around those objects to keep choices consistent.

Monitoring completes the design. Dynamic provisioning hides manual disk creation, so operators need visibility into PVC counts, pending claims, orphaned retained volumes, expansion events, quota pressure, and provisioner errors. A class that works during a lab may still be operationally weak if nobody can see failed backend calls or abandoned volumes. When you design a class, also decide how you will notice that it is being misused or failing.

The practical rule is simple: treat StorageClasses as durable platform APIs. Once teams put them in manifests, changing semantics can break assumptions about cost, deletion, scheduling, and recovery. Create a small set, document them, test them with real PVCs and pods, and avoid changing existing classes casually. When semantics must change, create a new class name and migrate users deliberately instead of silently changing the meaning of an old name.

### Exam-Speed Command Reading

The CKA exam does not require you to remember every provider parameter, but it does require you to read Kubernetes state efficiently. Build the habit of pairing a short command with a question. `kubectl get storageclass` answers "what policies exist?" `kubectl describe persistentvolumeclaim` answers "what is Kubernetes waiting for?" `kubectl get persistentvolume` answers "what was created?" `kubectl logs` on the provisioner answers "what did the backend reject?"

When time is short, do not start by editing YAML. Observe first, because storage edits can create or delete backend resources. A single `kubectl describe` may show that the PVC is only waiting for a first consumer, which means the correct next step is to create the pod, not to change the class. Another describe may show a provisioner error, which means editing a pod would waste time. Observation protects both your score and your data.

The same command-reading habit applies to cleanup. If a class uses `Delete`, deleting the claim may remove the backing volume. If a class uses `Retain`, deleting the claim may leave a released PV and backend storage that needs manual handling. Before deleting storage objects in a shared environment, read the reclaim policy and confirm whether the data is disposable. In the exam lab, cleanup is usually safe, but the habit should still be deliberate.

Finally, remember that StorageClass problems are rarely solved by one universal command. The correct command depends on which layer is suspect. PVC events point at claim and provisioning status, StorageClass YAML points at policy, pod events point at scheduling and mounting, and controller logs point at backend calls. If you can explain which layer a command tests, you are already thinking like an operator rather than a command memorizer.

---

## Patterns & Anti-Patterns

Patterns for StorageClasses are mostly about making safe choices easy. A good platform exposes a small set of named classes that map to real workload needs, then documents which class to use for development, production databases, shared files, local labs, and high-performance workloads. Too many classes push provider-specific complexity back onto application teams. Too few classes force critical workloads and disposable workloads through the same policy.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Default general-purpose class | Most namespaces need ordinary RWO storage | Developers can omit `storageClassName` safely | Keep cost and reclaim behavior conservative |
| Retain class for production data | Databases and stateful systems with recovery needs | Accidental PVC deletion does not delete the backend volume | Requires cleanup process for retired volumes |
| WaitForFirstConsumer for topology-aware storage | Zonal cloud disks and local storage | Scheduler and provisioner agree on node or zone placement | Pair with node labels and pod scheduling constraints |
| Expandable classes for growing data | Logs, databases, registries, and caches | Operators can increase capacity without replacing the claim | Monitor quota and cost so growth remains visible |

Anti-patterns usually come from copying a StorageClass without understanding the environment. The YAML may be valid, but the cluster may lack the driver, the backend may reject a parameter, or the chosen policy may conflict with the data lifecycle. Treat StorageClasses like API-facing platform contracts. Once teams depend on them, changing semantics can affect many workloads even though the object itself looks small.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| One class named `fast` for every workload | Teams cannot tell cost, durability, or reclaim behavior from the name | Use names that describe intent, such as `standard-delete` or `prod-retain` |
| `Immediate` for zonal disks | Volumes can be created in a zone the consuming pod cannot use | Use `WaitForFirstConsumer` for topology-sensitive storage |
| Multiple default classes | PVCs without a class may use a surprising backend | Keep exactly one default and audit annotations after changes |
| `Retain` everywhere | Deleted test PVCs leave billable volumes behind | Use `Delete` for disposable classes and `Retain` for protected data |
| Provider parameters copied across clouds | Provisioning fails because driver keys differ | Read the installed driver docs and verify with a small PVC |
| Expansion disabled by habit | Incidents require migration instead of a simple PVC increase | Enable expansion where the driver supports it and control growth with quota |

The strongest pattern is to design StorageClasses from workload intent backward. Ask what the workload needs for availability, performance, deletion safety, expansion, topology, and cost. Then choose the driver and parameters that express that intent. This approach is slower than copying the first example from documentation, but it produces classes that survive real operational pressure.

---

## Decision Framework

Use the decision process below when you need to design or debug a class. Start with topology because the wrong binding mode can stop a pod before the application even runs. Then choose lifecycle behavior because deletion policy affects data safety. Finally choose provider parameters because they tune the storage product after the bigger operational choices are already correct.

```
+--------------------------------------------------------------+
|                 StorageClass Decision Path                   |
+--------------------------------------------------------------+
| Does storage attach only in one zone or on one node?          |
|   yes -> use WaitForFirstConsumer                            |
|   no  -> Immediate may be acceptable for network storage     |
|                                                              |
| Is the data disposable after PVC deletion?                    |
|   yes -> reclaimPolicy: Delete                               |
|   no  -> reclaimPolicy: Retain                               |
|                                                              |
| Can the workload grow over time?                             |
|   yes -> allowVolumeExpansion: true if the driver supports it|
|   no  -> document why expansion is intentionally disabled    |
|                                                              |
| Do teams need different cost or performance tiers?            |
|   yes -> create a small named set of classes                  |
|   no  -> keep one clear default class                        |
+--------------------------------------------------------------+
```

| Decision | Prefer This | Avoid This | Reason |
|----------|-------------|------------|--------|
| Unknown cluster provisioner | Inspect existing classes and CSI pods | Guessing a driver name | Provisioner names are installation-specific |
| Zonal block storage | `WaitForFirstConsumer` | `Immediate` | Delayed binding prevents wrong-zone volumes |
| Static PV binding | `storageClassName: ""` on PV and PVC | Omitting the field on the PVC | Omission may invoke the default class |
| Production data deletion | `Retain` plus cleanup runbook | `Delete` by habit | Human review protects data during mistakes |
| Lab or preview environments | `Delete` plus quotas | `Retain` everywhere | Automatic cleanup prevents leaked disks |
| Database growth | Expansion enabled and monitored | Recreating PVCs during pressure | Expansion is safer than migration during incidents |

Which approach would you choose here and why: a two-node local lab needs quick PVCs for exercises, while a multi-zone production cluster needs disks for databases. The lab can accept a local-path class with `Delete` because the data is disposable. The production cluster should use the installed CSI driver, delayed binding, expansion enabled, encryption if required, and a reclaim policy chosen by the data-retention standard.

The framework also helps during failure analysis. If a PVC is pending, classify the wait: defaulting, static binding, delayed binding, missing provisioner, invalid backend request, or scheduler conflict. Each category has a different next command. Good troubleshooting is not running every command you know; it is choosing the command that tests the next most likely link in the chain.

---

## Did You Know?

- Kubernetes has supported the `storage.k8s.io/v1` StorageClass API as the stable API for years, which is why modern examples should not use the old beta API group. The in-tree `kubernetes.io/aws-ebs` provisioner was removed in Kubernetes 1.27, so new clusters should use the EBS CSI driver (`ebs.csi.aws.com`) instead.
- The `storageclass.kubernetes.io/is-default-class` annotation can exist on more than one class, and Kubernetes chooses the most recently created default for a PVC that omits `storageClassName`.
- `WaitForFirstConsumer` became a stable StorageClass behavior so topology-aware provisioning could wait for a pod scheduling decision instead of guessing a zone too early.
- PVC expansion can increase requested storage, but Kubernetes does not support shrinking a PVC, so a mistaken oversized request needs a migration plan rather than a reverse patch.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Multiple default StorageClasses | Teams patch defaults during migrations and forget to remove the older annotation | Keep exactly one default and verify `kubectl get storageclass` after changes |
| Wrong provisioner for platform | Examples are copied from another cloud or from legacy in-tree documentation | Inspect installed CSI drivers and use the exact provisioner string they watch |
| `Immediate` mode with zonal storage | The class is copied from a network-storage example without considering topology | Use `WaitForFirstConsumer` for EBS, Persistent Disk, Azure Disk, and local storage |
| Forgetting `allowVolumeExpansion` | The first PVC works, so future growth is ignored until an incident | Enable expansion where the driver supports it and govern growth with quotas |
| Wrong parameters for the provisioner | Parameter names look portable but are driver-specific strings | Check vendor documentation and read provisioner logs for backend rejection messages |
| Trying to shrink a PVC | Operators assume storage requests behave like CPU and memory requests | Migrate data to a smaller PVC because Kubernetes supports expansion, not shrink |
| Omitting `storageClassName` for static binding | The empty field is confused with the empty string | Use `storageClassName: ""` on the PVC and matching static PV when opting out |

---

## Quiz

<details>
<summary>Q1: A developer creates a PVC in a cluster with a default StorageClass named `gp3-standard`, but they expected it to bind to a manually created PV. A new dynamic PV appears instead. What happened, and how should the claim be written?</summary>

When `storageClassName` is omitted, Kubernetes can apply the default StorageClass, so the PVC requested dynamic provisioning through `gp3-standard`. The manual PV was not ignored randomly; the claim asked for the default class by omission. To bind only to a classless static PV, set `storageClassName: ""` on the PVC and ensure the PV also has no class. This distinction is why omitted and empty are different in PVC specs.

</details>

<details>
<summary>Q2: A multi-zone AWS workload uses a class with `volumeBindingMode: Immediate`, then the pod lands in a different zone from the new EBS volume. What caused the attach failure, and what class setting prevents it?</summary>

`Immediate` allowed the provisioner to create the volume before the scheduler chose a node for the pod. EBS volumes are zonal, so a volume in one zone cannot attach to a node in another zone. `WaitForFirstConsumer` prevents the mismatch by delaying provisioning until the pod has a scheduling decision. Network storage such as NFS is different because it is not attached to one zone-specific node in the same way.

</details>

<details>
<summary>Q3: A database PVC is patched from `50Gi` to `100Gi`, and `kubectl describe` shows `FileSystemResizePending`. Should the operator recreate the PVC?</summary>

Recreating the PVC is the wrong first reaction because `FileSystemResizePending` can be part of a normal expansion flow. It means the backend capacity has been handled, but the filesystem inside the mounted volume still needs to grow. The operator should check whether the pod is running, whether the driver supports online filesystem expansion, and whether a remount or restart is needed. Recreate or migrate only if the driver cannot complete expansion or the class never allowed it.

</details>

<details>
<summary>Q4: An administrator finds two classes annotated as default, `gp3-fast` and `standard-hdd`. A PVC without `storageClassName` used the slower class. How should the admin fix the cluster policy?</summary>

Kubernetes resolves multiple defaults by choosing the most recently created default class, but that behavior is confusing for users. The admin should remove the default annotation from the unintended class and verify that only one class shows as default. Existing PVs already provisioned from the wrong class will not change just because the annotation is fixed. Workloads that need the other backend should receive new PVCs using the intended class.

</details>

<details>
<summary>Q5: A production StorageClass used `reclaimPolicy: Delete`, and several PVs were already created from it. Can recreating the StorageClass protect those existing PVs?</summary>

Recreating the StorageClass only changes behavior for future dynamically created PVs. Existing PVs keep the reclaim policy they received when they were created. To protect those volumes, the admin must inspect and patch the PVs directly if the organization decides they should be retained. This is why reclaim policy is a high-impact setting even though it is only one line in the class.

</details>

<details>
<summary>Q6: A PVC is pending, the class uses `WaitForFirstConsumer`, and no pod currently references the claim. Is the pending state a failure?</summary>

Not necessarily. With `WaitForFirstConsumer`, provisioning and binding can be intentionally delayed until a pod uses the claim. The next step is to create or inspect the consuming pod and read its scheduling events. If the pod exists and scheduling still cannot proceed, then investigate topology constraints, provisioner logs, and StorageClass parameters. Treating every pending PVC as a provisioner failure can lead to unnecessary class changes.

</details>

<details>
<summary>Q7: You need one class for disposable preview environments and one class for production databases. How would you compare the reclaim policy, binding mode, and expansion choices?</summary>

For previews, `Delete` is usually appropriate because the data is disposable and automatic cleanup prevents leaked volumes. For production databases, `Retain` is often safer because PVC deletion should not immediately delete the backend disk. Both classes should usually use `WaitForFirstConsumer` for zonal block storage, and the production class should enable expansion when the driver supports it. The preview class may also enable expansion, but quota and cost controls should keep temporary environments bounded.

</details>

---

## Hands-On Exercise: Dynamic Provisioning

Exercise scenario: you will create a StorageClass, create a PVC that uses it, attach that claim to a pod, and verify that a PV appears dynamically. The lab works best on a cluster with a local provisioner, such as kind with Rancher's local-path provisioner or minikube with its hostPath provisioner. If your cluster uses a different provisioner, adapt only the `provisioner` field and keep the diagnostic flow the same.

### Task 1: Check Existing StorageClasses

Start by reading the cluster rather than guessing. The first command shows the names users can request, and the second command exposes the provisioner string and default annotation. If there is already a default class, note it before the optional default task so you can restore the cluster to its original policy afterward.

```bash
# See what's available
kubectl get storageclass

# Check if there's a default
kubectl get storageclass -o custom-columns='NAME:.metadata.name,PROVISIONER:.provisioner,DEFAULT:.metadata.annotations.storageclass\.kubernetes\.io/is-default-class'
```

<details>
<summary>Solution guidance</summary>

You should see at least one StorageClass if your cluster has dynamic provisioning configured. In kind, the provisioner is often `rancher.io/local-path`; in minikube, it is often `k8s.io/minikube-hostpath`. If the list is empty, you can still study the YAML, but the dynamic provisioning tasks will not succeed until a provisioner is installed.

</details>

### Task 2: Create a StorageClass

This example uses the local-path provisioner because it is common in kind-based practice clusters. Do not copy this provisioner string into a cloud cluster unless that driver is actually installed. The important behavior to observe is `WaitForFirstConsumer`: the PVC can exist before a PV is created, and the pod will trigger the final provisioning decision.

```bash
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: rancher.io/local-path    # For kind; change for your cluster
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
EOF
```

Volume expansion is primarily a cloud-CSI feature; on `rancher.io/local-path` installs the field may be accepted but silently ignored.

<details>
<summary>Solution guidance</summary>

`kubectl get storageclass fast -o yaml` should show the class with the provisioner, reclaim policy, binding mode, and expansion setting you applied. If the API rejects the object, check indentation and field names first. If the object is accepted but later claims do not bind, the next likely problem is that no controller is watching the provisioner string.

</details>

### Task 3: Create a PVC Using the StorageClass

Create a small PVC that names the class explicitly. Because the class uses `WaitForFirstConsumer`, a healthy claim may remain pending until a pod uses it. That pending state is the behavior you want to observe; it proves that the binding mode is influencing the workflow.

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: fast
EOF

# Check status - should be Pending when waiting for a consumer
kubectl get persistentvolumeclaim dynamic-pvc
```

<details>
<summary>Solution guidance</summary>

If the PVC is pending with an event about waiting for the first consumer, that is expected. If it binds immediately, your provisioner or cluster may implement different local behavior, or the class was not applied as expected. If it is pending with provisioning errors, read the events and verify that `fast` names a provisioner that exists in your cluster.

</details>

### Task 4: Create a Pod to Trigger Provisioning

The pod is the first consumer. When the scheduler places this pod, the storage system has enough topology context to provision the backing volume. The container writes a small message into the mounted path so you can verify that the mounted PVC is usable, not merely bound.

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: dynamic-pod
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sh', '-c', 'echo "Dynamically provisioned!" > /data/message; sleep 3600']
    volumeMounts:
    - name: storage
      mountPath: /data
  volumes:
  - name: storage
    persistentVolumeClaim:
      claimName: dynamic-pvc
EOF
```

<details>
<summary>Solution guidance</summary>

After the pod is created, the PVC should move toward `Bound`, and a PV with a generated name should appear. If the pod cannot schedule, describe the pod and check node, taint, and topology messages. If the pod schedules but the claim stays pending, describe the PVC and inspect the provisioner logs.

</details>

### Task 5: Verify Dynamic Provisioning

Verification should follow the object chain. Wait for the pod, check the PVC, identify the generated PV, confirm that the PV records the expected class, and then read the message from the mounted path. This sequence proves the class, claim, volume, and pod are connected.

```bash
# Wait for pod to trigger provisioning and become ready
kubectl wait --for=condition=Ready pod/dynamic-pod --timeout=60s

# PVC should now be Bound
kubectl get persistentvolumeclaim dynamic-pvc
# STATUS: Bound

# A PV was automatically created
kubectl get persistentvolume
# Should see a dynamically named PV like pvc-xxxxx

# Check the PV details accurately
PV_NAME=$(kubectl get persistentvolumeclaim dynamic-pvc -o jsonpath='{.spec.volumeName}')
kubectl get persistentvolume "$PV_NAME" -o jsonpath='{.spec.storageClassName}{"\n"}'
# Should show: fast

# Verify pod can read the dynamically provisioned storage
kubectl exec dynamic-pod -- cat /data/message
```

<details>
<summary>Solution guidance</summary>

The PVC should be `Bound`, the PV should name the `fast` StorageClass, and the pod should print `Dynamically provisioned!`. If the `PV_NAME` variable is empty, the claim has not bound yet. Use `kubectl describe persistentvolumeclaim dynamic-pvc` and `kubectl describe pod dynamic-pod` to decide whether the delay is scheduler-related, provisioner-related, or backend-related.

</details>

### Task 6: Test Default StorageClass

This step is optional because changing defaults affects other PVCs in the cluster. In a disposable lab, mark the `fast` class as default, create a PVC without `storageClassName`, and confirm that Kubernetes applies the default class. In a shared cluster, skip this task or restore the original default immediately after testing.

```bash
# Make our StorageClass the default
kubectl patch storageclass fast -p '{"metadata": {"annotations": {"storageclass.kubernetes.io/is-default-class": "true"}}}'

# Create PVC without storageClassName
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: default-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
  # No storageClassName - uses default
EOF

# Check it uses the default class
kubectl get persistentvolumeclaim default-pvc -o jsonpath='{.spec.storageClassName}{"\n"}'
# Should show: fast
```

<details>
<summary>Solution guidance</summary>

The PVC should show `fast` as its storage class after defaulting. If it does not, check whether another default class exists and whether your annotation patch succeeded. Remember that multiple defaults can produce surprising results, so use `kubectl get storageclass` before and after the test.

</details>

### Card A — Kubernetes creates the cloud disk itself when no provisioner is running.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** the API records the claim, but an external provisioner must create the backing disk; without one, the PVC remains pending. **Next action:** describe the PVC and check that its StorageClass provisioner matches a running CSI controller.

</details>

### Card B — volumeBindingMode Immediate is safe for a zonal disk because the scheduler can move the volume later.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** Immediate provisioning can select a zone before the pod's placement is known, and the scheduler cannot move an existing disk between zones. **Next action:** compare PV node affinity with pod constraints and use `WaitForFirstConsumer` for future zonal claims.

</details>

### Card C — A missing provisioner means the API server rejected the PVC.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** an accepted PVC can remain `Pending` because no matching external provisioner completes the storage request. **Next action:** inspect PVC events, the StorageClass provisioner string, and the corresponding controller pods.

</details>

### Card D — Changing the binding mode after the volume exists moves it to the pod's zone.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** a StorageClass change does not relocate a previously provisioned PV or rewrite its node affinity. **Next action:** place the pod where the volume can attach, or create a suitable new volume and migrate the data deliberately.

</details>

**Success Criteria**: Confirm each result with cluster state before considering the exercise complete, especially the transition from a pending claim to usable storage.

- [ ] StorageClass created successfully.
- [ ] PVC stays pending until pod creation when `WaitForFirstConsumer` is active.
- [ ] PV is automatically created when the pod is scheduled.
- [ ] Pod can write to and read from dynamically provisioned storage.
- [ ] Default StorageClass behavior is verified or intentionally skipped in a shared cluster.
- [ ] Diagnose pending PVCs, wrong-zone attachments, failed expansion, invalid parameters, and provisioner-controller failures using events and logs.
- [ ] You can explain the link between StorageClass, PVC, PV, provisioner, and pod scheduling.

### Cleanup

Cleanup should remove the pod before the PVC so the volume is not mounted while the claim is deleted. With `reclaimPolicy: Delete`, deleting the PVC should also remove the dynamically provisioned PV and its backend storage. If you changed a shared cluster default, restore the original default annotation as part of your cleanup.

```bash
kubectl delete pod dynamic-pod
kubectl delete persistentvolumeclaim dynamic-pvc default-pvc
kubectl delete storageclass fast
```

### Practice Drills

Use these short drills after the main lab to build speed. They preserve the same actions from the original module, but the commands are written with full `kubectl` so they work when copied into a non-interactive shell. For each drill, say the expected result before running the command.

```bash
# Drill 1: List all StorageClasses and identify the default
kubectl get storageclass
```

```bash
# Drill 2: Create StorageClass "slow" with provisioner rancher.io/local-path
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: slow
provisioner: rancher.io/local-path
reclaimPolicy: Retain
EOF
```

```bash
# Drill 3: Make StorageClass "standard" the default
# Use annotation: storageclass.kubernetes.io/is-default-class: "true"
```

```bash
# Drill 4: Create PVC "data-pvc" requesting 5Gi with StorageClass "fast"
```

```bash
# Drill 5: Create PVC that will not use any StorageClass
# Hint: storageClassName: ""
```

```bash
# Drill 6: Diagnose why a PVC is stuck in Pending
kubectl describe persistentvolumeclaim <name>
# Check Events section for errors
```

```bash
# Drill 7: Create StorageClass with volume expansion enabled
# Key field: allowVolumeExpansion: true
```

```bash
# Drill 8: Check the volumeBindingMode of StorageClass "standard"
kubectl get storageclass standard -o jsonpath='{.volumeBindingMode}{"\n"}'
```

---

## Sources

- https://kubernetes.io/docs/concepts/storage/storage-classes/
- https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/
- https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- https://kubernetes.io/docs/concepts/storage/volumes/
- https://kubernetes.io/docs/tasks/administer-cluster/change-default-storage-class/
- https://kubernetes-csi.github.io/docs/
- https://kubernetes-csi.github.io/docs/external-provisioner.html
- https://kubernetes-csi.github.io/docs/external-resizer.html
- https://docs.aws.amazon.com/eks/latest/userguide/create-storage-class.html
- https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver
- https://learn.microsoft.com/en-us/azure/aks/azure-disk-csi
- https://minikube.sigs.k8s.io/docs/handbook/persistent_volumes/
- https://github.com/rancher/local-path-provisioner

## Learner check

> Volume expansion is primarily a cloud-CSI feature; on `rancher.io/local-path` installs the field may be accepted but silently ignored.

Why should you verify expansion behavior on your cluster instead of trusting `allowVolumeExpansion: true` alone? Which observable result confirms that the backend volume and filesystem actually grew?

## Next Module

Continue to [Module 4.4: Volume Snapshots & Cloning](../module-4.4-snapshots/) to learn about backup and data protection features for Kubernetes storage.
