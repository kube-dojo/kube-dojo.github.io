---
title: "Module 4.5: Storage Troubleshooting"
slug: k8s/cka/part4-storage/module-4.5-troubleshooting
revision_pending: false
sidebar:
  order: 6
lab:
  id: cka-4.5-troubleshooting
  url: https://killercoda.com/kubedojo/scenario/cka-4.5-troubleshooting
  duration: "40 min"
  difficulty: advanced
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Diagnosing and fixing storage issues
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: [Module 4.1](../module-4.1-volumes/), [Module 4.2](../module-4.2-pv-pvc/), [Module 4.3](../module-4.3-storageclasses/), and [Module 4.4](../module-4.4-snapshots/)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Diagnose** storage failures systematically across PVC Pending, mount errors, capacity issues, and permission denied symptoms.
- **Trace** the storage provisioning chain from Pod to PVC, StorageClass, provisioner, PV, node attach, and final mount.
- **Fix** common storage issues by choosing the least destructive correction for binding, access mode, quota, and ownership problems.
- **Design** a storage troubleshooting checklist that works in CKA exam scenarios and in production incident response.

---

## Why This Module Matters

Hypothetical scenario: a Deployment rollout looks routine until half the pods remain in `ContainerCreating` and the application starts serving stale data from the surviving replicas. The container image is healthy, the probes are ordinary, and the scheduler has placed the pods on nodes, yet the workload cannot open its data directory. At that point, restarting pods is mostly noise because the failure is not inside the application process; it is somewhere in the contract among the claim, the volume, the storage driver, the node, and the filesystem view inside the container.

Storage troubleshooting matters because Kubernetes intentionally splits responsibility across several controllers. The scheduler reasons about nodes, the persistent volume controller reasons about claims, the external CSI provisioner talks to the storage backend, the attach-detach controller coordinates node attachment, and the kubelet performs the mount that a container finally sees. That separation is powerful, but it means a visible symptom such as `Pending`, `FailedMount`, or `Permission denied` rarely names the whole root cause by itself.

The CKA exam rewards engineers who can narrow the failure path quickly without damaging state. In production, the same habit prevents risky fixes such as deleting a PVC before reading its reclaim policy or force-deleting an old pod before proving the failed node is not still writing to a ReadWriteOnce volume. This module teaches a repeatable path: start at the pod event, follow the storage object graph, inspect the controller or driver only when the evidence points there, and choose a fix that preserves data first.

The detective analogy from the original module still fits, but make it operational rather than theatrical. The pod event is the first witness, the PVC and PV are the paper trail, the StorageClass explains the policy, and CSI logs are the specialist interview you use only after the early evidence says the driver is involved. A good storage debugger does not memorize every possible error string; they know which layer owns each decision and which command will prove whether that layer has fulfilled its part of the contract.

---

## Start With the Storage Failure Model

Kubernetes storage is easiest to debug when you treat it as a pipeline instead of a single object. A Pod refers to a PVC by name inside its own namespace, the PVC asks for capacity and access semantics, the StorageClass selects a provisioner and binding policy, the PV records the actual volume, and the kubelet mounts that volume into the container. A failure at any stage can surface as a pod that will not start, so the first job is to identify the stage where the handoff stopped.

Use this path as your mental map before you run commands. It preserves the original module's troubleshooting diagram while replacing shorthand with the full command names you can copy into a shell or script. Notice that the flow does not begin with the CSI driver; most storage incidents are visible in object status and events before you need controller logs.

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Storage Troubleshooting Path                      │
│                                                                      │
│   Pod Issue                                                          │
│       │                                                              │
│       ▼                                                              │
│   1. kubectl describe pod <name>                                     │
│      └─► Check Events section                                        │
│      └─► Check volume mount errors                                   │
│          │                                                           │
│          ▼                                                           │
│   2. kubectl get pvc <name>                                          │
│      └─► Is STATUS "Bound"?                                          │
│      └─► If "Pending", check Events                                  │
│          │                                                           │
│          ▼                                                           │
│   3. kubectl get pv                                                  │
│      └─► Does matching PV exist?                                     │
│      └─► Is STATUS "Available" or "Bound"?                           │
│          │                                                           │
│          ▼                                                           │
│   4. kubectl get sc <storageclass>                                   │
│      └─► Does StorageClass exist?                                    │
│      └─► Is provisioner correct?                                     │
│          │                                                           │
│          ▼                                                           │
│   5. Check CSI driver                                                │
│      └─► Is driver installed?                                        │
│      └─► Check driver pod logs                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

The important habit is to read from the consumer toward the supplier. If a pod references the wrong claim name, the PV and StorageClass may be perfect and still irrelevant. If a PVC is unbound because the StorageClass does not exist, node mount logs only distract you. If the PVC is bound and the pod event says `FailedMount`, then the object contract has probably completed and you should shift attention to attach, mount, permissions, or node-local path behavior.

Keep one command set close while you work. The individual commands below are ordinary, but their order is the difference between a clean diagnosis and a long search through unrelated logs. In exam conditions, this order also protects your time because you can stop as soon as one layer proves the break.

```bash
# Pod-level debugging
kubectl describe pod <pod-name>
kubectl get pod <pod-name> -o yaml
kubectl logs <pod-name>
```

The pod is the correct entry point because it joins the scheduling, volume, and container views. `kubectl describe pod` is especially useful because the Events section often contains the exact message emitted by the attach or mount operation. `kubectl logs` helps only after the container has started; when the pod is still `ContainerCreating`, events usually matter more than application logs.

```bash
# PVC debugging
kubectl get pvc
kubectl describe pvc <pvc-name>
kubectl get pvc <pvc-name> -o yaml
```

The PVC tells you whether Kubernetes has satisfied the claim. A `Bound` claim means the control plane found or created a PV, while `Pending` means binding is still waiting or has failed. The YAML view is useful when you need exact fields such as `storageClassName`, requested capacity, access modes, selected node annotations, or condition messages.

```bash
# PV debugging
kubectl get pv
kubectl describe pv <pv-name>
kubectl get pv <pv-name> -o yaml
```

The PV is cluster-scoped, so it may outlive the namespace or workload that first used it. Read the PV when static binding is involved, when a claim appears to target an existing volume, or when reclaim policy affects the safety of deletion. A PV in `Released` or `Failed` state is not the same as an `Available` PV, even if the capacity and access modes look attractive at first glance.

```bash
# StorageClass debugging
kubectl get sc
kubectl describe sc <sc-name>
kubectl get sc <sc-name> -o yaml
```

The StorageClass records policy rather than a specific disk. It answers questions such as which provisioner is responsible, whether expansion is allowed, which binding mode is used, and which backend parameters are passed to the driver. Many Pending PVCs are explained by a misspelled class name, an unexpected default class, or `WaitForFirstConsumer` behavior that is normal rather than broken.

```bash
# Events, often the highest-signal view
kubectl get events --sort-by='.lastTimestamp'
kubectl get events --field-selector involvedObject.name=<pvc-name>
kubectl get events --field-selector involvedObject.name=<pod-name>
```

Events are not a full audit log, but they are excellent breadcrumbs during active troubleshooting. Sort by timestamp when you need the newest failures, and use field selectors when a namespace is noisy. If you see the same event repeating, read both the reason and the message because the reason is often generic while the message contains the backend or object-specific detail.

```bash
# CSI debugging
kubectl get pods -n kube-system | grep csi
kubectl logs -n kube-system <csi-pod> -c <container>
kubectl get csidrivers
kubectl get csinode
```

CSI logs are powerful, but they are not the first stop for every issue. Go there when events mention external provisioning, driver names, attach failures, or backend API errors. In managed clusters, the CSI controller and node plugin may be installed outside your application namespace, so the namespace and container name matter when you fetch logs.

**Pause and predict:** if a pod is stuck in `ContainerCreating`, but the referenced PVC is already `Bound`, which two stages of the pipeline have probably completed, and which stage should you inspect next?

<details>
<summary>Reveal the prediction</summary>

Volume provisioning and claim binding have already succeeded, which confirms that the control plane satisfied the storage request. The next stage to investigate is the node level, specifically volume attachment to the host and filesystem mounting into the container runtime directory.
</details>

Commit your expected sequence to paper before expanding the explanation, then compare your diagnostic thinking with the step-by-step verification commands below.

Exercise scenario: a learner reports that `kubectl get pvc` shows `Pending` and immediately asks whether the CSI driver is down. Before checking driver logs, first ask whether a pod is already consuming the claim and whether the StorageClass uses delayed binding. That one question can separate a real provisioning failure from the intended `WaitForFirstConsumer` design.

---

## Diagnose PVC Binding Problems

A PVC stuck in `Pending` means the claim has not been matched with a PV yet. That could be a hard failure, such as a missing StorageClass, or it could be deliberate waiting, such as a class that uses `WaitForFirstConsumer`. Your job is to decide whether the controller is blocked, waiting for scheduling context, or unable to find a compatible volume.

```bash
kubectl get pvc
```

```text
NAME     STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS
my-pvc   Pending                                       fast-ssd
```

Do not treat `Pending` as a root cause. It is a status that says binding has not happened yet, and the reason lives in events, StorageClass policy, or the static PV inventory. Read the PVC details before changing anything because many fields on claims are effectively part of the binding contract and may require recreation rather than patching after a claim exists.

```bash
kubectl describe pvc my-pvc
```

When static provisioning is used, the most common failure is that no available PV satisfies the claim. Matching is stricter than "there is a volume somewhere with enough space." The PV must satisfy access modes, capacity, storage class, selector requirements, and other binding constraints before the controller can claim it.

```text
Events:
  Type     Reason              Message
  ----     ------              -------
  Normal   FailedBinding       no persistent volumes available for this claim
```

If you see this message, compare the PVC request against available PVs rather than creating a random new object. Capacity must be at least as large as the claim, access modes must cover what the claim requests, and storage class names must align. A PV with `Retain` reclaim policy may also carry old claim references or data, so do not blindly reuse it without checking whether it is truly safe.

```bash
kubectl get pvc my-pvc -o yaml | grep -A8 spec:
```

```bash
kubectl get pv
```

```bash
kubectl describe pv <pv-name>
```

A missing StorageClass is faster to diagnose because the event usually names the class. This often happens after copying YAML between clusters where class names differ, or after relying on a default class in one cluster and using an explicit class in another. In CKA practice clusters, class names are deliberately simple, but real clusters often use names that encode disk type, zone policy, replication, encryption, or performance tier.

```text
Events:
  Type     Reason              Message
  ----     ------              -------
  Warning  ProvisioningFailed  storageclass.storage.k8s.io "fast-ssd" not found
```

The quick correction is to list the available classes, delete the Pending claim, and recreate it with a valid `storageClassName`. After creation, PVC field changes are intentionally narrow: resize requests may be changed when expansion is allowed, but changing the storage class requires a new claim. Do not mutate or casually edit an already-bound claim; for an unbound practice claim, deletion and recreation with the correct class is usually the cleanest exam move.

```bash
kubectl get sc
```

```bash
kubectl delete pvc my-pvc
```

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
EOF
```

Dynamic provisioning failures are different because the StorageClass exists, but the external provisioner cannot create the volume. The PVC event may say that it is waiting for the external provisioner, or it may contain a backend-specific error returned by the driver. This is the point where CSI controller logs become appropriate because the provisioner sidecar owns the create request.

```text
Events:
  Type     Reason              Message
  ----     ------              -------
  Warning  ProvisioningFailed  failed to provision volume: no csi driver
```

```bash
kubectl get csidrivers
```

```bash
kubectl get pods -n kube-system | grep csi
```

Delayed binding is the exception that fools many learners. A PVC can remain `Pending` by design when the StorageClass uses `volumeBindingMode: WaitForFirstConsumer`, because the provisioner needs the scheduler's node choice before creating a zone-constrained volume. If the cluster created the volume immediately, the pod might later be scheduled to a node in a different zone and fail to attach.

```bash
kubectl get sc fast-ssd -o jsonpath='{.volumeBindingMode}'
```

```text
WaitForFirstConsumer
```

A delayed-binding PVC without an error event is not broken just because it is Pending. Create or inspect the pod that consumes it, then watch scheduling and binding together. If the pod also cannot schedule, the root cause may be node selectors, topology constraints, or resource pressure rather than the storage backend itself.

```bash
kubectl get pvc my-pvc
```

```text
STATUS: Pending
```

Access mode mismatches are another classic static provisioning failure. A PV that offers `ReadWriteOnce` cannot satisfy a PVC that asks for `ReadWriteMany`, because the claim is asking for a sharing semantic the volume does not provide. Kubernetes does not downgrade the request for you, and it should not, because doing so would silently change the application safety model.

```bash
kubectl get pv
```

```text
NAME   CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS
pv-1   100Gi      RWO            Retain           Available
```

```bash
kubectl get pvc
```

```text
NAME     STATUS    ACCESS MODES   STORAGECLASS
my-pvc   Pending   RWX            manual
```

The fix is to correct the architecture, not just the YAML. If the workload needs a single-writer disk, change the PVC to `ReadWriteOnce` and run the workload accordingly. If multiple nodes truly need shared writes, choose a backend that supports `ReadWriteMany`, such as a properly configured network filesystem or a cloud file service, and accept the different performance and consistency characteristics.

StorageClass mismatches look similar because both objects may appear valid in isolation. A PV with `storageClassName: manual` will not satisfy a claim asking for `fast`, even when the capacity and access mode match. The class is part of the binding identity, so compare it explicitly when a matching PV seems obvious but the controller refuses to bind.

```bash
kubectl get pv pv-1 -o jsonpath='{.spec.storageClassName}'
```

```text
manual
```

```bash
kubectl get pvc my-pvc -o jsonpath='{.spec.storageClassName}'
```

```text
fast
```

Before running this, what output do you expect if a claim has no explicit `storageClassName` and the cluster has a default StorageClass? Think through whether the PVC will ask for the default class, ask for no class, or wait for a manual PV, then verify the actual field in YAML rather than relying on the short table view.

```bash
kubectl get pvc my-pvc -o yaml | grep -E 'storageClassName:|volumeName:|accessModes:|storage:'
```

---

## Diagnose Volume Mount and Attach Errors

Once the PVC is `Bound`, the failure shifts from provisioning to node attachment and filesystem mount. A pod stuck in `ContainerCreating` often means the scheduler chose a node, but the kubelet cannot make the volume available inside the container. The pod event will usually say whether the claim is missing, the volume cannot attach, the mount timed out, a path check failed, or the filesystem permissions do not match the container's user.

```bash
kubectl get pods
```

```text
NAME     READY   STATUS              RESTARTS   AGE
my-pod   0/1     Pending             0          5m
```

The first debug command is still the pod describe, not the node log. The event stream connects the pod to the volume operation Kubernetes attempted, and it normally includes the claim name, volume name, node, or driver error. If the event names a missing PVC, the pod specification is pointing at an object that does not exist in that namespace; current clusters often report that as a scheduler-side `FailedScheduling` event before the pod ever reaches node-side mounting.

```bash
kubectl describe pod my-pod
```

```text
Events:
  Warning  FailedScheduling  0/3 nodes are available:
  persistentvolumeclaim "my-pvc" not found
```

PVC references are namespace-local. A claim named `my-pvc` in `default` does not satisfy a pod in `payments`, and a typo in the claim name is enough to hold the pod before scheduling. This is why you should always include the namespace in your checks when the pod is not in the default namespace.

```bash
kubectl get pvc my-pvc -n <namespace>
```

```bash
kubectl get pod my-pod -n <namespace> -o yaml | grep -A6 persistentVolumeClaim
```

Multi-attach errors are more dangerous because they often involve a real volume and real data. A `ReadWriteOnce` volume can be mounted read-write by only one node at a time, so a replacement pod on a different node may wait while the old node still owns the attachment. This frequently appears during node failures, slow termination, or manual pod movement.

```text
Events:
  Warning  FailedAttachVolume  Multi-Attach error for volume "pvc-abc":
  Volume is already attached to node "node-1"
```

The original module's quick fix was to force-delete the old pod, but that action needs context. First prove that the old pod is genuinely stuck, the old node is not healthy, and the application can tolerate abrupt termination. Force deletion removes the API object immediately; it does not guarantee that the process stopped cleanly or that the filesystem was unmounted cleanly on an unreachable node.

```bash
kubectl get pod <old-pod> -o wide
```

```bash
kubectl get node node-1
```

```bash
kubectl describe node node-1 | grep -A8 Conditions
```

If the old node is unreachable and the incident requires recovery, you may force-delete the old pod and inspect VolumeAttachment objects. The safer sequence is to gather evidence, take the least destructive action, and then run application-level integrity checks after the workload returns. For databases, message brokers, and write-heavy systems, storage attach success is not the same as data consistency.

```bash
kubectl delete pod <old-pod> --force --grace-period=0
```

```bash
kubectl get volumeattachment
```

Permission errors are a different category because the volume may attach and mount correctly while the process cannot write. This usually appears after moving from a root container to a non-root container, changing the image UID, or restoring data that was created with different ownership. The pod can be `Running`, but the application logs show write failures.

```text
Events:
  Warning  FailedMount  MountVolume.SetUp failed:
  mount failed: exit status 32, permission denied
```

The Kubernetes-native fix is to make the pod's security context match the filesystem ownership model. `fsGroup` asks the kubelet to make the mounted volume accessible to a group, while `runAsUser` makes the container process run as the intended user. This is not free on very large volumes because recursive ownership handling can slow the first mount, but it is usually better than returning the application to root.

```yaml
# Add securityContext to pod
spec:
  securityContext:
    fsGroup: 1000
  containers:
  - name: app
    securityContext:
      runAsUser: 1000
      runAsNonRoot: true
```

You should verify both the Kubernetes configuration and the filesystem view from inside the container. If the pod is running but the app cannot write, `kubectl exec` can show the numeric user, group, and mount permissions directly. Those facts tell you whether the security context was applied and whether the path is owned in a way the process can use.

```bash
kubectl exec my-pod -- id
```

```bash
kubectl exec my-pod -- ls -ld /data
```

`hostPath` errors are simpler but easy to overlook because they depend on node-local state. A `hostPath` volume with type `Directory` requires the path to exist on the selected node before the pod starts. If the path is missing, the kubelet correctly rejects the mount because the specification promised an existing directory.

```text
Events:
  Warning  FailedMount  hostPath type check failed:
  path /data/myapp does not exist
```

For labs and controlled node-local use cases, `DirectoryOrCreate` lets the kubelet create the path when it is missing. That is useful for practice scenarios, but it is not a general substitute for durable storage because `hostPath` ties the data to one node and bypasses many isolation guarantees. In production, use `hostPath` sparingly and usually only for node agents or system-level integrations.

```yaml
volumes:
- name: data
  hostPath:
    path: /data/myapp
    type: DirectoryOrCreate
```

Mount timeouts usually point to a driver, backend, or node problem rather than a YAML typo. The claim may be bound, but the node cannot attach or mount the underlying storage before the timeout expires. At that point, you need to correlate pod events with CSI controller logs, CSI node plugin logs, node health, and any provider-side limits.

```text
Events:
  Warning  FailedMount  Unable to attach or mount volumes:
  timeout expired waiting for volumes to attach
```

```bash
kubectl get pods -n kube-system | grep csi
```

```bash
kubectl logs -n kube-system <csi-controller-pod> -c csi-provisioner
```

```bash
kubectl describe node <node-name> | grep -A8 Conditions
```

**Stop and think:** a pod is stuck in `ContainerCreating` and the event says `Multi-Attach error`. You know the volume is `ReadWriteOnce`. Before force-deleting the old pod, what evidence would convince you that the old writer is gone, and what application-level check should run after recovery?

<details>
<summary>Reveal the prediction</summary>

You must prove the old writer has stopped before any force-deletion. A host that is only partitioned or unreachable can still have the filesystem open, and a Ready node is the dangerous case. Proceed only when the process has terminated, or the node is NotReady and has been fenced or powered down. After the workload recovers, run an application-level integrity check to verify that no half-written records remain.
</details>

Consider how you would defend this cautious operational sequence during an escalation before reading the next section on storage quotas.

---

## Diagnose Capacity, Expansion, and Quota Problems

Capacity failures show up in two different places. Provisioning capacity failures happen before the PV exists, when the backend or quota cannot satisfy the requested size. Filesystem-full failures happen after the workload has been running, when the mounted volume no longer has enough free space for the application. These problems need different commands because one is a control-plane binding issue and the other is an in-pod filesystem issue.

```bash
kubectl get pvc my-pvc
```

```text
NAME     STATUS   VOLUME                                     CAPACITY   ACCESS MODES
my-pvc   Bound    pvc-1a2b3c4d-1111-2222-3333-444455556666   10Gi       RWO
```

The PVC capacity is the requested or provisioned size, not the current filesystem usage. To see whether the application has filled the volume, inspect the mount from inside the pod. This distinction matters because Kubernetes can report a healthy, bound claim while the container process fails writes with ordinary `No space left on device` errors.

```bash
kubectl exec my-pod -- df -h /data
```

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/xvdf       9.8G  9.6G  120M  99% /data
```

If the StorageClass supports expansion, increasing the PVC request is often the cleanest fix. Expansion is a policy choice on the StorageClass, and the exact filesystem resize behavior depends on the driver and volume mode. Always confirm `allowVolumeExpansion` before patching, then watch PVC conditions and pod behavior until the filesystem reflects the new size.

```bash
kubectl get sc <storageclass> -o jsonpath='{.allowVolumeExpansion}'
```

```text
true
```

```bash
kubectl patch pvc my-pvc -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

```bash
kubectl describe pvc my-pvc | grep -A8 Conditions
```

Cleaning data is also a valid fix when the data is disposable, but treat `rm -rf` as an application decision rather than a generic storage cure. Temporary files, caches, and build artifacts can often be removed safely; database files, queue segments, and user uploads cannot. In a real runbook, the cleanup command should name the directory and retention rule precisely.

```bash
kubectl exec my-pod -- rm -rf /data/tmp/*
```

Provisioning capacity failures appear before the volume is created. The event may say `insufficient capacity`, or the CSI logs may carry a provider-specific message about quota, topology, volume type, or backend availability. In namespaces with ResourceQuota, the Kubernetes API may reject or delay requests even when the storage backend has space.

```text
Events:
  Warning  ProvisioningFailed  insufficient capacity
```

```bash
kubectl get resourcequota -n <namespace>
```

```bash
kubectl get limitrange -n <namespace>
```

Quotas are especially important in exam and training clusters because they can make a correct YAML file fail for environmental reasons. A claim that asks for more storage than the namespace quota allows will not bind, and increasing the request later may hit the same policy. When the object looks valid but the event mentions quota, solve the policy mismatch rather than chasing the CSI driver.

```bash
kubectl describe resourcequota -n <namespace>
```

The correct production answer may be to change storage tier, reduce the request, expand backend capacity, or move the workload to a topology where capacity exists. Cloud block storage can have regional, zonal, account, and per-volume constraints, and the Kubernetes event may expose only part of that chain. Use Kubernetes evidence to identify which backend API call failed, then use provider tooling or documentation to validate the underlying limit.

Which approach would you choose here and why: expand the PVC, clean old data, lower the requested capacity, or move to another StorageClass? The best answer depends on whether the failure is current usage, namespace policy, backend quota, or topology capacity, so name the layer before naming the fix.

---

## Diagnose CSI Driver and Cloud Permission Issues

The Container Storage Interface lets Kubernetes use many storage backends through a common integration model, but it also adds moving parts. A typical CSI deployment has controller components that provision and attach volumes, node components that publish volumes on each node, and sidecars such as the external provisioner, attacher, resizer, and snapshotter. When object events point to the driver, you need to know which component owns the failed action.

```bash
kubectl describe pvc my-pvc
```

```text
Events:
  Warning  ProvisioningFailed  error getting CSI driver name
```

Start by confirming the driver is registered. `CSIDriver` objects describe installed drivers at the cluster level, while `CSINode` objects show driver information associated with individual nodes. If the driver is missing from both views, the StorageClass may reference a provisioner that is not installed in the cluster.

```bash
kubectl get csidrivers
```

```bash
kubectl get csinode
```

Then inspect the pods that run the driver. Managed distributions vary, but CSI components commonly live in `kube-system` or another platform namespace. Look at both the controller deployment and the node DaemonSet because provisioning and mounting failures can live in different components.

```bash
kubectl get pods -n kube-system | grep csi
```

```text
NAME                          READY   STATUS             RESTARTS
ebs-csi-controller-abc        0/6     CrashLoopBackOff   5
```

For a crashlooping controller, logs from each relevant sidecar matter. The external provisioner handles PVC-to-volume creation, the attacher handles attach operations for attachable volumes, and the driver container talks to the backend API. A single pod can contain several containers, so include `-c` rather than assuming the default container is the one with useful logs.

```bash
kubectl logs -n kube-system ebs-csi-controller-abc -c csi-provisioner
```

```bash
kubectl logs -n kube-system ebs-csi-controller-abc -c csi-attacher
```

Cloud permissions are a common CSI failure source because the driver usually needs identity outside the Kubernetes API. On AWS, the EBS CSI controller commonly uses IAM permissions through a service account annotation in EKS-style clusters. On GCP, Workload Identity or node service accounts may provide permissions. On Azure, managed identity or a service principal may authorize disk operations.

```bash
kubectl get sa -n kube-system ebs-csi-controller-sa -o yaml
```

```text
metadata:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/example-ebs-csi-role
```

Treat provider identity as configuration that can drift. A CSI driver that worked yesterday can fail today if a service account annotation was removed, a role policy was changed, a node pool identity changed, or a driver upgrade altered required permissions. Kubernetes events may only say provisioning failed, while the driver log names the failed API action.

```bash
kubectl describe sc <storageclass>
```

```bash
kubectl get sc <storageclass> -o yaml
```

StorageClass parameters also deserve inspection when one class fails and another works. A typo in a volume type, encryption key, filesystem type, topology parameter, or performance option can make only a specific class fail. The driver log is usually more precise than the PVC event because it includes the backend rejection.

```bash
kubectl describe pvc my-pvc
```

```bash
kubectl logs -n kube-system <csi-controller-pod> -c <driver-container>
```

**Pause and predict:** a CSI controller pod is in `CrashLoopBackOff`, and logs say it failed to assume an IAM role. The StorageClass and PVC YAML did not change. Which Kubernetes object would you inspect first, and which external configuration would you verify after that?

<details>
<summary>Reveal the prediction</summary>

You should inspect the driver controller's ServiceAccount first to verify that its identity metadata and workload identity annotations are intact. After validating the cluster configuration, check the external cloud IAM role, trust policy, and attached permission policies to confirm that credential issuance and trust relationships remain valid.
</details>

Reflect on how cloud authentication connects cluster identity to provider infrastructure permissions before proceeding to the error classification table below.

---

## Build a Quick Reference Without Skipping the Diagnosis

Quick references are useful only when they preserve the reasoning path. The table below keeps the original module's error-message cheatsheet, but each row should be read as a starting hypothesis rather than a final answer. A missing claim often appears as `FailedScheduling`, while `FailedMount` can point to a driver timeout, a node path problem, or a permission problem, so always pair the message with the object and layer that produced it.

| Error Message | Likely Cause | Quick Fix |
|---------------|--------------|-----------|
| `persistentvolumeclaim "..." not found` | Pod references a missing claim, often reported as `FailedScheduling` before mount | Correct the pod `claimName` or create the named claim in the pod namespace |
| `no persistent volumes available` | No matching PV for static provisioning | Create or repair a matching PV |
| `storageclass not found` | Wrong StorageClass name | Check available classes and delete + recreate the PVC with a valid class |
| `waiting for first consumer` | `WaitForFirstConsumer` binding mode | Create or inspect the pod using the PVC |
| `Multi-Attach error` | RWO volume requested on multiple nodes | Verify old writer, then delete old pod or adjust scheduling |
| `permission denied` | Filesystem ownership or security context mismatch | Set `fsGroup`, `runAsUser`, and verify ownership |
| `path does not exist` | Strict `hostPath` type with missing node path | Create the path or use `DirectoryOrCreate` in lab scenarios |
| `timeout waiting for volumes` | CSI driver, backend, or node attach issue | Check CSI pods, logs, node health, and backend limits |
| `insufficient capacity` | Namespace quota or backend capacity exhausted | Inspect quota, request size, topology, and provider capacity |
| `volume is already attached` | Stale or active attachment to another node | Inspect old pod, node state, and VolumeAttachment objects |

The one-liner below preserves the original quick debug intent, but it is better as a snapshot than a diagnosis. Use it to orient yourself, then return to object-specific `describe` output for the actual failure message. A wall of resources is less useful than a short chain of facts that proves where the storage contract broke.

```bash
echo "=== PVCs ===" && kubectl get pvc && \
echo "=== PVs ===" && kubectl get pv && \
echo "=== StorageClasses ===" && kubectl get sc && \
echo "=== Recent Events ===" && kubectl get events --sort-by='.lastTimestamp' | tail -20
```

```bash
kubectl describe pod <pod-name>
```

```bash
kubectl describe pvc <pvc-name>
```

```bash
kubectl describe sc <storageclass>
```

```bash
kubectl get volumeattachment
```

---

## Patterns & Anti-Patterns

Troubleshooting patterns are reusable because they reduce the number of guesses you make under pressure. The goal is not to run every command in every incident; it is to move from symptom to owning layer with minimal risk. Good storage debugging keeps stateful data in mind even when the immediate exam task looks like a simple pod startup problem.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Consumer-to-supplier tracing | Any pod or PVC storage failure | Starts from the visible symptom and follows the actual object reference chain | Works well in large namespaces because each step narrows the object set |
| Event-first diagnosis | `Pending`, `ContainerCreating`, attach, or mount failures | Events usually contain the controller's latest reason and message | Event retention is limited, so capture useful messages during active incidents |
| Policy before mutation | Before deleting PVCs, PVs, or old pods | Reclaim policy, access mode, and binding mode determine data risk | Requires runbooks that name safe deletion conditions for each workload class |
| Driver escalation by evidence | When events name external provisioning, attach, or backend API errors | CSI logs are high signal after object-level facts point to the driver | Platform teams should document driver namespaces, container names, and identities |

Anti-patterns usually come from treating storage like a stateless restart problem. A pod can be recreated cheaply, but the volume it references may hold the only copy of important state. The better alternative is to prove whether the failure is a reference, policy, driver, node, or filesystem problem before choosing a mutation.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Deleting the PVC before reading the PV and reclaim policy | The backing volume may be deleted or released unexpectedly | Inspect PVC, PV, reclaim policy, and snapshots before removing claims |
| Chasing CSI logs before reading pod and PVC events | You spend time in noisy controller logs while the YAML typo is obvious | Start with `describe pod` and `describe pvc`, then escalate only when events point there |
| Treating every Pending PVC as broken | Delayed binding can be normal with topology-aware storage | Check `volumeBindingMode` and whether a consuming pod exists |
| Forcing old pods during Multi-Attach without node evidence | A still-running writer can corrupt application data | Confirm node state, pod termination, and workload safety before force deletion |
| Solving permission denied by running as root | The app starts but the security posture regresses | Use `fsGroup`, `runAsUser`, and ownership verification |
| Scaling a Deployment that shares one RWO claim | Extra replicas fail or fight for the same node-attached volume | Use one replica, per-replica PVCs through StatefulSet, or RWX storage |

---

## Decision Framework

The fastest decision framework is to classify the failure by the first object that proves something wrong. If the pod references a missing PVC, fix the pod or claim name. If the PVC is Pending, inspect binding inputs. If the PVC is Bound but the pod cannot mount, inspect attach, node, path, permissions, and driver behavior. If the pod runs but the application cannot write, inspect filesystem usage and ownership from inside the container.

```text
Storage symptom
  |
  +-- Pod says PVC not found?
  |     |
  |     +-- Verify namespace and claimName, then correct the pod spec or create the claim.
  |
  +-- PVC is Pending?
  |     |
  |     +-- Check StorageClass, binding mode, access modes, capacity, selectors, and quota.
  |
  +-- PVC is Bound but pod is ContainerCreating?
  |     |
  |     +-- Check FailedMount, FailedAttach, Multi-Attach, hostPath, node, and CSI events.
  |
  +-- Pod runs but app cannot write?
        |
        +-- Check df, ownership, runAsUser, fsGroup, and application retention policy.
```

Use this decision matrix when you need to choose a fix under time pressure. It deliberately separates safe read-only checks from mutations because storage recovery often has irreversible steps. In CKA practice, you may be expected to delete and recreate a broken test object; in production, the same deletion could remove the only binding to real data.

| Evidence | Primary Layer | Read-Only Checks | Candidate Fix |
|----------|---------------|------------------|---------------|
| PVC event says class not found | StorageClass selection | `kubectl get sc`, `kubectl describe pvc` | Delete + recreate the unbound PVC with an existing class |
| PVC event says waiting for first consumer | Scheduler and topology | `kubectl get sc -o yaml`, inspect consuming pod | Create the pod or fix scheduling constraints |
| Existing PV will not bind | PV/PVC contract | Compare capacity, access modes, class, selectors, and claimRef | Align claim or create a compatible PV |
| Pod event says claim not found | Pod volume reference | Inspect pod namespace and `claimName` | Correct pod spec or create the named claim in the namespace |
| Multi-Attach error | Node attachment | Inspect old pod, node health, and VolumeAttachment | Wait, move workload, or force-delete only after risk review |
| Permission denied after mount | Filesystem ownership | `kubectl exec` with `id`, `ls -ld`, and app logs | Set `fsGroup`, `runAsUser`, or repair ownership through an approved job |
| Filesystem full | Runtime capacity | `df -h`, PVC size, app data layout | Expand claim if allowed or clean safe disposable data |

Design your troubleshooting checklist as a sequence of facts, not a bag of commands. Each line should answer one question: Does the pod reference the correct claim, is the claim bound, did the class choose the intended provisioner, did the node attach the volume, did the mount succeed, and can the process write? When the checklist is written that way, it becomes useful across static PVs, dynamic CSI provisioning, local lab storage, and cloud block volumes.

### Worked Example: Reading the Evidence in Order

Suppose an exercise gives you a pod named `api-0` that will not start, a PVC named `api-data`, and a StorageClass named `fast-block`. The tempting move is to inspect all three objects immediately, but the cleaner move is to ask what the pod already knows. If the pod event says the claim is missing, the class and driver are not yet relevant; if the event says the mount timed out, the claim name has already been resolved and you can move deeper.

Now imagine the pod event says `persistentvolumeclaim "api-data" not found`, but `kubectl get pvc` in your current shell shows a healthy claim with that name. The next question is not whether Kubernetes is inconsistent; it is whether your command used the pod's namespace. A namespaced claim in `default` does not satisfy a pod in `backend`, so the evidence pushes you toward namespace correction rather than provisioning repair.

If the pod event names a claim and the claim is `Pending`, shift to the PVC's event stream. A message about `storageclass not found` points to a configuration mismatch that you can fix by choosing an existing class or creating the intended class. A message about waiting for the first consumer points to scheduler topology context, so creating or fixing the consuming pod is the right next move. The same status word therefore leads to different actions depending on the event message.

If the PVC is `Bound`, resist the urge to edit it just because the pod is still unhealthy. Binding means the control plane has already associated the claim with a PV, and random edits can make the situation harder to reason about. At this stage, pod events about `FailedAttachVolume`, `FailedMount`, `hostPath type check failed`, or permission problems are more useful than changes to the claim. The owning layer has moved from binding to node attachment, mount setup, or process access.

For Multi-Attach, the evidence order protects data. First find the old pod and node, then decide whether the old writer is gone or merely unreachable from the API server. If the old node is still Ready, forcing deletion is a bad habit because the original process might still have the filesystem open. If the node is NotReady and recovery is required, document the risk, remove the stale API object, and plan an application integrity check after the replacement pod starts.

For permission denied, the evidence order prevents a security regression. A running pod with application logs complaining about `/data` is different from a pod that cannot mount the volume at all. Check `id`, group membership, and directory ownership from inside the container, then repair the pod security context or data ownership. Reverting to root is usually a sign that the diagnosis stopped at the symptom instead of explaining why the process lacked write permission.

For capacity, separate requested capacity from used capacity. A bound 20Gi PVC can still be full from the application's perspective, and a Pending 20Gi PVC can fail before any filesystem exists because quota or backend capacity blocks provisioning. The fix for the first case might be expansion or cleanup; the fix for the second might be quota adjustment, smaller requests, topology changes, or provider-side capacity. The command output should tell you which world you are in before you choose.

This worked example is the habit you want on exam day: read the closest event, identify the owner of the next decision, and avoid destructive mutations until the evidence supports them. Storage troubleshooting feels large because the system has many layers, but most incidents become small once you can say, "the pod reference failed," "the claim did not bind," "the driver could not provision," "the node could not attach," or "the process cannot write." That sentence is the bridge between diagnosis and a safe fix.

---

## Learner check

> After creation, PVC field changes are intentionally narrow: resize requests may be changed when expansion is allowed, but changing the storage class requires a new claim.

Your PVC is still `Pending`, its event says `storageclass.storage.k8s.io "fast-ssd" not found`, and `kubectl get sc` shows only `standard`. What action changes the class safely without trying an immutable-field patch?

---

## Did You Know?

- Kubernetes introduced CSI support as stable in the 1.13 release cycle, which helped move storage integrations out of the core tree and into independently maintained drivers.
- `volumeBindingMode: WaitForFirstConsumer` exists because topology-aware storage must know the selected node or zone before provisioning a volume safely.
- PVC expansion is controlled by the StorageClass `allowVolumeExpansion` field, so two claims in the same cluster can have different expansion behavior.
- `ReadWriteOnce` is about node-level attachment semantics for many block volumes; it does not mean every replica in a Deployment automatically gets a private disk.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Not checking Events first | The short `get` table hides the actual controller message | Run `kubectl describe pod` or `kubectl describe pvc` and read the Events section |
| Ignoring namespace | PVC names are namespace-local, but PVs and StorageClasses are cluster-scoped | Verify pod and PVC namespace before debugging the backend |
| Forgetting `WaitForFirstConsumer` | A Pending PVC looks broken when it is actually waiting for a consuming pod | Check the StorageClass binding mode and inspect the pod that uses the claim |
| Deleting PVC before checking reclaim policy | The delete may release or remove the backing storage | Inspect PV, reclaim policy, snapshots, and data ownership before deletion |
| Skipping CSI logs when events name the provisioner | Generic PVC events can hide backend API details | Check the specific CSI controller or node plugin container named by the failure |
| Fixing permissions by running as root | It masks the symptom while weakening isolation | Use `fsGroup`, `runAsUser`, and explicit ownership checks |
| Scaling replicas that share one RWO claim | The second pod lands on another node and cannot attach the volume | Use one replica, a StatefulSet with per-replica claims, or RWX-capable storage |

---

## Quiz

<details>
<summary>Question 1: A developer says a pod has been stuck in `ContainerCreating` for ten minutes and recreating it did not help. Which storage troubleshooting sequence do you run, and why?</summary>

Start with `kubectl describe pod <name>` because the pod event tells you whether the failure is a missing claim, an attach problem, or a mount problem. If the event names a PVC, check `kubectl get pvc <name>` and `kubectl describe pvc <name>` to prove whether the claim is bound or Pending. If the claim is Pending, inspect StorageClass, PV compatibility, quota, and delayed binding; if the claim is Bound, inspect attach, node, CSI, hostPath, and permission evidence. This sequence works because it follows the actual reference chain instead of jumping to unrelated driver logs.

</details>

<details>
<summary>Question 2: A PVC has been Pending for two hours, but `kubectl describe pvc` only says it is waiting for the first consumer. Another team member wants to reinstall the CSI driver. What do you do?</summary>

Do not reinstall the driver based on that message alone. Check the StorageClass and confirm whether `volumeBindingMode` is `WaitForFirstConsumer`, because a Pending claim can be expected until a pod that uses it is scheduled. The next useful action is to create or inspect the consuming pod and verify whether scheduling constraints prevent node selection. Reinstalling the driver would add risk while ignoring the evidence that Kubernetes is waiting for topology context.

</details>

<details>
<summary>Question 3: A StatefulSet pod on a failed node used an RWO volume, and the replacement pod reports a Multi-Attach error on another node. What recovery path balances speed and data safety?</summary>

First confirm the old node and old pod state with `kubectl get pod -o wide`, `kubectl get node`, and node conditions, because a still-running writer is the dangerous case. If the node is truly unreachable and the workload requires recovery, force-delete the old pod only after accepting the application risk, then inspect VolumeAttachment objects if the attachment remains stale. Once the new pod mounts the volume, run application-level integrity checks because Kubernetes attach success does not prove the previous writer exited cleanly. The safe reasoning is to prove ownership before breaking the old attachment.

</details>

<details>
<summary>Question 4: A new image runs as UID 1000, the PVC mounts successfully, but the application logs say it cannot write `/data/app.log`. What is the root cause and Kubernetes-native fix?</summary>

The likely root cause is filesystem ownership created by the old root-running container or by a restore process with different numeric ownership. The PVC and mount are healthy, so pod events may not show a storage failure. Add a pod security context with `fsGroup: 1000` and a container security context such as `runAsUser: 1000` and `runAsNonRoot: true`, then verify with `kubectl exec -- id` and `ls -ld /data`. Running the app as root would make the symptom disappear but would weaken the security model.

</details>

<details>
<summary>Question 5: A PVC using `premium-ssd` stays Pending, the StorageClass exists, and the event says the external provisioner has not created a volume. Where do you look next?</summary>

Look at the CSI controller pods and logs because the claim reached the dynamic provisioning layer. Use `kubectl get pods -n kube-system | grep csi`, then fetch logs from containers such as `csi-provisioner`, `csi-attacher`, or the driver container. The likely causes are a crashlooping controller, missing cloud permissions, invalid StorageClass parameters, backend quota, or topology capacity. Checking another default StorageClass can also tell you whether the failure is class-specific or cluster-wide.

</details>

<details>
<summary>Question 6: A Deployment has two replicas that both mount the same Bound PVC. One pod is Running on node-a, the other is stuck on node-b, and the PV access mode is RWO. What is the exam fix and the production fix?</summary>

The immediate problem is that a single RWO-backed claim is being used by pods on different nodes. In an exam, the fastest safe fix is usually to scale the Deployment to one replica or constrain scheduling so only one node needs the attachment, depending on the task wording. The production fix is to redesign the storage shape: use a StatefulSet with `volumeClaimTemplates` so each replica receives its own claim, or move to RWX-capable storage if the application truly needs shared writes. The answer should mention the access mode because changing replicas without changing storage semantics only hides the design problem.

</details>

<details>
<summary>Question 7: A namespace quota allows 10Gi of storage, and a learner creates a 20Gi PVC that never binds. The StorageClass and CSI driver are healthy. How do you prove and fix the issue?</summary>

Inspect `kubectl describe pvc` for quota-related events, then run `kubectl get resourcequota -n <namespace>` and `kubectl describe resourcequota -n <namespace>` to compare requested storage against policy. The fix is to reduce the request, request a quota change, or use a namespace intended for larger claims. Driver restarts are not relevant because the API policy rejects or blocks the request before the backend capacity question matters. This answer aligns the evidence with the layer that owns the denial.

</details>

---

## Hands-On Exercise: Storage Troubleshooting Scenarios

This exercise preserves the original module's three broken configurations and turns them into a progressive troubleshooting lab. Use a disposable cluster or lab environment because you will create claims and pods that are intentionally wrong before fixing them. The goal is not to memorize the final YAML; it is to practice reading the event, naming the broken layer, and applying the smallest correction that makes the workload healthy.

### Setup

```bash
kubectl create ns storage-debug
```

### Scenario 1: PVC Won't Bind Because the StorageClass Is Wrong

Create the broken claim exactly as written. The StorageClass name is intentionally invalid for most clusters, so the claim should remain Pending and the PVC events should name the missing class. If your cluster happens to have a class with this exact name, change it to another clearly absent name before applying the object.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: broken-pvc-1
  namespace: storage-debug
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: nonexistent-class
EOF
```

```bash
kubectl get pvc -n storage-debug broken-pvc-1
```

```bash
kubectl describe pvc -n storage-debug broken-pvc-1
```

```bash
kubectl get sc
```

The fix is to recreate the claim with a real StorageClass for your cluster. If your lab cluster has no dynamic provisioner, this scenario still teaches the right diagnosis: the claim asks for a class that the cluster cannot satisfy. In that case, record the evidence and skip the replacement claim, or create a static PV if your instructor expects manual provisioning.

```bash
kubectl delete pvc -n storage-debug broken-pvc-1
```

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: broken-pvc-1
  namespace: storage-debug
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
EOF
```

If the class uses `WaitForFirstConsumer`, the PVC staying `Pending` with no error events is expected until a pod references the claim.

<details>
<summary>Scenario 1 solution notes</summary>

The expected evidence is an event similar to `storageclass.storage.k8s.io "nonexistent-class" not found`. The correct fix is not to restart pods or inspect CSI logs first; it is to make the claim ask for a class that exists or to provide a matching static PV. If `standard` is not present in your cluster, substitute the actual class name shown by `kubectl get sc`.

</details>

### Scenario 2: Pod Can't Mount Because the Claim Name Is Wrong

This scenario starts with a valid claim and then creates a pod that references a different name. The expected failure is at the pod volume reference layer, not the provisioning layer. That means the PVC can be healthy while the pod still cannot mount anything.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: correct-pvc
  namespace: storage-debug
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF
```

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: broken-pod-1
  namespace: storage-debug
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sleep', '3600']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: wrong-pvc-name
EOF
```

```bash
kubectl get pod -n storage-debug broken-pod-1
```

```bash
kubectl describe pod -n storage-debug broken-pod-1
```

The repair is to recreate the pod with the correct `claimName`. For a real Deployment, you would patch or update the controller template rather than editing a naked pod, because controllers recreate pods from their templates. In this lab, deleting and recreating the pod keeps the focus on the storage reference.

```bash
kubectl delete pod -n storage-debug broken-pod-1
```

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: broken-pod-1
  namespace: storage-debug
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sleep', '3600']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: correct-pvc
EOF
```

<details>
<summary>Scenario 2 solution notes</summary>

The pod event should mention that `persistentvolumeclaim "wrong-pvc-name" not found`. The important detail is namespace-local naming: Kubernetes is not searching other namespaces for a claim with that name, and a healthy claim with a different name does not satisfy the pod spec. The smallest correction is to make the pod reference `correct-pvc`.

</details>

### Scenario 3: hostPath Type Error

The third scenario uses `hostPath` because it produces a clear node-local mount error without requiring a cloud provider. The path is intentionally absent and the type is `Directory`, which requires the directory to exist before the pod starts. This is useful for learning, but remember that `hostPath` is rarely the right abstraction for application data in production.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: broken-pod-2
  namespace: storage-debug
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sleep', '3600']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    hostPath:
      path: /tmp/nonexistent-path-xyz
      type: Directory
EOF
```

```bash
kubectl describe pod -n storage-debug broken-pod-2
```

Fix the pod by using `DirectoryOrCreate`, which asks the kubelet to create the directory on the selected node if it does not exist. This is appropriate for the lab because the path is disposable. In a production design, you would usually replace `hostPath` with a PV, a CSI-backed volume, or a node-agent-specific pattern.

```bash
kubectl delete pod -n storage-debug broken-pod-2
```

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: broken-pod-2
  namespace: storage-debug
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ['sleep', '3600']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    hostPath:
      path: /tmp/nonexistent-path-xyz
      type: DirectoryOrCreate
EOF
```

<details>
<summary>Scenario 3 solution notes</summary>

The expected event is a hostPath type-check failure. The fix changes the hostPath type rather than changing PVCs, StorageClasses, or CSI drivers because this volume is node-local and does not use the persistent volume controller. That distinction is the main lesson: the correct fix follows the volume type that actually appears in the pod spec.

</details>

### Practice Drills

The following drills preserve the original quick checks as short repetitions. Run them after the scenarios, then explain what each command proves in one sentence. If you cannot name the layer each command checks, repeat the earlier sections until the command has a purpose instead of feeling like a memorized spell.

```bash
kubectl get pvc -n <namespace>
```

```bash
kubectl describe pvc <pvc-name> | grep -A20 Events
```

```bash
kubectl exec <pod> -- df -h
```

```bash
kubectl exec <pod> -- ls -la /data
```

```bash
kubectl describe pod <pod-name>
```

```bash
kubectl get pods -n kube-system | grep csi
```

```bash
kubectl get csidrivers
```

```bash
kubectl get pvc <pvc-name> -o yaml | grep -E 'storage:|accessModes:|storageClassName:'
```

```bash
kubectl get pv <pv-name> -o yaml | grep -E 'storage:|accessModes:|storageClassName:'
```

```bash
kubectl get volumeattachment
```

```bash
kubectl get events --field-selector reason=FailedBinding
```

```bash
kubectl get events --field-selector reason=ProvisioningFailed
```

```bash
kubectl get events --sort-by='.lastTimestamp' | tail -20
```

```bash
kubectl get pod <pod-name> -o wide
```

```bash
kubectl get sc <storageclass> -o yaml
```

```bash
kubectl describe node <node-name> | grep -A8 Conditions
```

```bash
kubectl logs -n kube-system <csi-controller-pod> -c csi-provisioner
```

```bash
kubectl logs -n kube-system <csi-controller-pod> -c csi-attacher
```

```bash
kubectl get resourcequota -n <namespace>
```

```bash
kubectl describe resourcequota -n <namespace>
```

### Storage Troubleshooting Checklist

Use this checklist as the final artifact from the lab. It is intentionally written as evidence to collect, not as commands to run blindly. In a real incident, attach the event messages and command outputs to the ticket so the next engineer can see why you chose the fix.

```text
□ Pod stuck? → kubectl describe pod → check Events
□ PVC Pending? → kubectl describe pvc → check Events
□ StorageClass exists? → kubectl get sc
□ PV available? → kubectl get pv
□ Access modes match? → Compare PVC and PV
□ StorageClassName match? → Compare PVC and PV
□ CSI driver running? → kubectl get pods -n kube-system | grep csi
□ Permissions issue? → Check securityContext fsGroup
□ Capacity issue? → Check quotas and storage backend
```

### Card A — A Bound PVC with the pod in ContainerCreating means provisioning has not started, so recreate the StorageClass.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** a `Bound` PVC proves provisioning and control-plane binding have already finished; the issue is downstream during node attachment or container volume mounting. Recreating the StorageClass cannot alter a claim that has already bound. **Next action:** describe the pod to inspect attach and mount events, and verify whether the volume is already attached elsewhere or waiting on the node plugin.

</details>

### Card B — A ReadWriteOnce Multi-Attach error is fixed by immediately force-deleting the old pod.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** force-deleting a pod does not detach the underlying disk from the original node, creating severe risk of simultaneous multi-node writes and filesystem corruption if that host is merely partitioned. **Next action:** check the old node and pod state, confirm the writer process has terminated, gracefully drain or detach through normal control-plane reconciliation, and verify data consistency after recovery.

</details>

### Card C — An IAM assume-role crash is diagnosed by editing the StorageClass, because that YAML must have changed.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** an IAM assume-role crash affects the CSI controller's identity and cloud credentials, not the StorageClass schema or parameters. Modifying the StorageClass cannot resolve driver authentication or permission failures. **Next action:** inspect the CSI controller's ServiceAccount annotations and verify the external cloud IAM role trust relationships and permission policies.

</details>

### Card D — CSI controller logs are the first stop for every storage failure, including a Pending PVC.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** checking driver logs first skips fundamental Kubernetes state and events, such as normal `WaitForFirstConsumer` delayed binding, namespace quotas, or mistyped claim parameters. **Next action:** describe the PVC and pod first to read the emitted events and status reasons; proceed to CSI controller logs only when events indicate external provisioner or driver communication errors.

</details>

**Success Criteria**: Verify each troubleshooting resolution using cluster events and state observations before concluding your exercise, ensuring you understand the diagnostic path across every storage layer.

- [ ] Identified a StorageClass error from PVC events and corrected the claim to use a valid class for your cluster.
- [ ] Identified a wrong PVC name from pod events and corrected the pod volume reference.
- [ ] Identified a hostPath type requirement from pod events and fixed the type safely for a lab.
- [ ] Explained whether each failure belonged to the pod reference, PVC binding, node mount, or storage driver layer.
- [ ] Wrote a short storage troubleshooting checklist that starts with events and avoids destructive deletion as the first move.

### Cleanup

```bash
kubectl delete ns storage-debug
```

---

## Sources

- [Kubernetes documentation: Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Kubernetes documentation: Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Kubernetes documentation: Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Kubernetes documentation: Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/)
- [Kubernetes documentation: Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
- [Kubernetes documentation: CSI Drivers](https://kubernetes.io/docs/concepts/storage/volumes/#csi)
- [Kubernetes documentation: Configure a Security Context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Kubernetes documentation: Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes documentation: Debug Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)
- [Kubernetes documentation: Finalizers](https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/)
- [Kubernetes CSI external-provisioner](https://github.com/kubernetes-csi/external-provisioner)
- [Kubernetes CSI external-attacher](https://github.com/kubernetes-csi/external-attacher)

---

## Next Module

Continue to the [Part 4 Cumulative Quiz](../part4-cumulative-quiz/) to test your storage knowledge before moving into broader Kubernetes troubleshooting.
