---
revision_pending: false
title: "Module 1.2: Extension Interfaces - CNI, CSI, CRI"
slug: k8s/cka/part1-cluster-architecture/module-1.2-extension-interfaces
sidebar:
  order: 3
lab:
  id: cka-1.2-extension-interfaces
  url: https://killercoda.com/kubedojo/scenario/cka-1.2-extension-interfaces
  duration: "35 min"
  difficulty: intermediate
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Conceptual with practical diagnostics
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: Module 1.1 (Control Plane)

---

## Learning Outcomes

After this module, you will be able to:

- **Evaluate** why Kubernetes delegates container runtime, network, and storage work to CRI, CNI, and CSI interfaces instead of baking every implementation into core components.
- **Identify** the installed CRI runtime, CNI network plugin, and CSI storage drivers on a live Kubernetes 1.35+ cluster using node fields, cluster resources, plugin files, and system logs.
- **Diagnose** CNI sandbox failures, CRI runtime problems, and CSI mount or provisioning events by connecting Pod and PVC symptoms to the right evidence.
- **Compare** common implementations such as containerd, CRI-O, Calico, Cilium, Flannel, local volumes, and cloud CSI drivers so you can choose a troubleshooting path with the right trade-offs.

---

## Why This Module Matters

Hypothetical scenario: your team has just created a small kubeadm cluster for a release rehearsal. The API server answers, `kubectl get nodes` works, and the scheduler is placing Pods, but every application workload sits in `ContainerCreating` while CoreDNS never becomes ready. Nothing in the Deployment manifests looks unusual, so the failure feels like a Kubernetes problem even though the control plane is mostly doing its job. The missing piece is the extension layer: kubelet can ask for a Pod sandbox, but the node cannot make that sandbox useful until a runtime and a network plugin satisfy their contracts.

Kubernetes is not a single monolithic program that knows how to run every container engine, wire every network, and provision every disk. Its core is deliberately narrower: expose an API, store desired state, schedule work, and reconcile that desired state through controllers and kubelets. The moment the work touches host-level execution, packet forwarding, or durable storage, Kubernetes switches from owning the implementation to enforcing an interface. That design is why a cluster can run containerd on one distribution, CRI-O on another, Calico in a data center, Cilium in a security-heavy environment, and different CSI drivers for AWS, Azure, vSphere, Ceph, or local development.

This module teaches the extension interfaces as operational contracts rather than vocabulary terms. You will learn what kubelet expects from the Container Runtime Interface, what the Container Network Interface must provide before a Pod can communicate, and how the Container Storage Interface separates volume lifecycle from application scheduling. More importantly, you will practice reading the evidence trail: node runtime columns, CNI configuration directories, DaemonSet logs, `CSIDriver` resources, PVC events, kubelet logs, and node socket paths. The goal is not to memorize every plugin name; it is to know which layer owns the symptom you are seeing.

The easiest analogy is a laptop full of standard ports. The operating system does not need custom code for every keyboard, storage device, or network adapter ever made; it needs those devices to obey the port and protocol contract. Kubernetes extension interfaces play the same role. CRI, CNI, and CSI define where the core stops and where specialized software begins. That boundary lets vendors and open source projects innovate without forcing Kubernetes itself to release a new version every time a storage array, eBPF datapath, or runtime shim changes.

---

## Part 1: The Plugin Architecture

Kubernetes grew around a separation of concerns that is easy to miss when you first learn the platform. The API server, scheduler, controller manager, and kubelet make decisions about objects and desired state, but they are not the best place to embed every low-level implementation detail. Container execution depends on Linux namespaces, cgroups, image snapshotters, OCI runtimes, and host services. Pod networking depends on IP allocation, routes, bridges, overlays, BGP, eBPF programs, and policy enforcement. Persistent storage depends on cloud APIs, block devices, mount propagation, node attachment, and filesystem behavior. Putting all of that inside core Kubernetes would make releases slower, upgrades riskier, and platform choice much narrower.

```
┌────────────────────────────────────────────────────────────────┐
│                   The Kubernetes Philosophy                     │
│                                                                 │
│   "Do one thing well, let others do the rest"                  │
│                                                                 │
│   Kubernetes Core:                                             │
│   ✓ API and resource management                                │
│   ✓ Scheduling and orchestration                               │
│   ✓ Controller patterns                                        │
│   ✓ Desired state reconciliation                               │
│                                                                 │
│   NOT Kubernetes Core (delegated to plugins):                  │
│   ✗ Container runtime details                                   │
│   ✗ Network implementation                                      │
│   ✗ Storage provisioning                                        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

That delegation is not a lack of responsibility; it is a contract model. Kubernetes still owns the user-facing API and the sequence of operations, but it asks specialized components to perform work through well-known interfaces. The benefit is choice, because a cluster operator can select the runtime, networking model, and storage driver that fit the environment. The benefit is also innovation, because Cilium can advance an eBPF datapath or a CSI vendor can add snapshot support without putting that code into the kubelet binary. The trade-off is that troubleshooting requires you to follow the request across boundaries instead of staying inside one log file.

| Interface | Purpose | kubelet Talks To |
|-----------|---------|------------------|
| **CRI** (Container Runtime Interface) | Run containers | containerd, CRI-O |
| **CNI** (Container Network Interface) | Pod networking | Calico, Cilium, Flannel |
| **CSI** (Container Storage Interface) | Persistent storage | AWS EBS, GCP PD, Ceph |

The table looks simple, but the sequencing matters. Kubelet uses CRI to create a Pod sandbox and run containers. During sandbox creation the runtime invokes CNI plugins to place the sandbox in the cluster network. Separately, when a Pod needs a persistent volume, Kubernetes controllers and kubelet coordinate with CSI components so that a volume exists, is attached to the right node, and is mounted into the container. When one layer fails, higher layers often show only a generic waiting state, so the CKA skill is to connect the waiting state to the interface that should have advanced next.

**Pause and predict:** if the API server and scheduler are healthy, but no CNI configuration exists on a worker node, which Kubernetes objects will still appear normal and which Pod lifecycle phase will expose the problem?

<details>
<summary>Check your prediction</summary>

Node objects, Deployments, and scheduled Pod resources still appear completely normal in API responses. The failure manifests only when the worker node container runtime attempts sandbox creation, leaving Pods stuck in `ContainerCreating` with network plugin not ready errors.

</details>

Isolating control plane object acceptance from node-level sandbox network wiring prevents unnecessary control plane debugging when the underlying worker networking layer lacks configuration.

The extension architecture also protects workload portability. A Deployment that runs NGINX normally does not mention containerd, Calico, or an EBS CSI driver; it asks Kubernetes for a Pod, networking, and perhaps a volume claim. That means application manifests survive many infrastructure differences. The operational manifests do not disappear, however. Cluster add-ons, node configuration, StorageClasses, and plugin DaemonSets become part of the platform contract, and platform engineers must version, monitor, and debug them with the same care they give the control plane.

This distinction is especially important when you read exam tasks. A prompt may say that a Pod is not starting, but the correct answer could live in a node service, a missing CNI file, or a StorageClass mismatch. Kubernetes gives you a shared object model, not a guarantee that every failure is solved with another workload manifest. When you learn to ask "which contract should have completed next," the same small set of commands becomes much more powerful. You stop wandering through resources and start proving where the lifecycle crossed from core Kubernetes into an extension implementation.

Another practical consequence is that interface health is cluster health. A control plane can be reachable while the cluster is unusable for real workloads because no Pod network exists. A node can be registered while kubelet cannot create new containers because the runtime endpoint is broken. A storage driver can be installed while claims still fail because the external provider credentials are wrong. These are not edge cases; they are normal outcomes of a pluggable system. The price of choice is that operators must understand the chosen plugins well enough to verify them after installs, upgrades, and node replacements.

---

## Part 2: CRI - Container Runtime Interface

The Container Runtime Interface defines how kubelet asks a runtime to pull images, create Pod sandboxes, start containers, stop containers, collect status, and stream logs. Historically, many learners associated Kubernetes with Docker because Docker was common on developer laptops, but Kubernetes never needed the full Docker developer experience on every node. Kubelet needs a runtime service that speaks CRI over gRPC, and modern clusters commonly satisfy that contract with containerd or CRI-O. Docker images still run because the image format is standardized; the node-side control path changed.

```
┌────────────────────────────────────────────────────────────────┐
│                         CRI Flow                                │
│                                                                 │
│   kubelet                                                       │
│      │                                                          │
│      │  CRI (gRPC)                                             │
│      │  "Create container with image X"                        │
│      │  "Start container Y"                                    │
│      │  "Stop container Z"                                     │
│      ▼                                                          │
│   ┌─────────────────┐    or    ┌─────────────────┐             │
│   │   containerd    │          │     CRI-O       │             │
│   └────────┬────────┘          └────────┬────────┘             │
│            │                            │                       │
│            ▼                            ▼                       │
│       ┌─────────┐                  ┌─────────┐                 │
│       │  runc   │                  │  runc   │                 │
│       └─────────┘                  └─────────┘                 │
│            │                            │                       │
│            ▼                            ▼                       │
│       Linux containers              Linux containers            │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The indirection is valuable because kubelet can remain stable while runtimes improve independently. Containerd focuses on image management, snapshotters, container lifecycle, and integration with OCI runtimes such as `runc`. CRI-O intentionally narrows itself to Kubernetes use cases and is common in OpenShift-oriented environments. Both can satisfy kubelet without Kubernetes carrying runtime-specific branches for every operation. If a runtime socket disappears or the runtime service hangs, kubelet cannot create new containers even though the API server may continue accepting Pod objects.

| Runtime | Description | Used By |
|---------|-------------|---------|
| **containerd** | Industry standard, CNCF graduated | kubeadm default, GKE, EKS, AKS |
| **CRI-O** | Kubernetes-focused, lightweight | OpenShift, some enterprise |
| **Docker** | Deprecated as a direct kubelet runtime in Kubernetes 1.24 | Legacy clusters |

The important exam distinction is that image build tools and node runtimes are separate concerns. Docker can still build an OCI-compatible image, push it to a registry, and produce an artifact containerd can run. What Kubernetes removed in 1.24 was dockershim, the in-tree adapter that let kubelet talk to the Docker Engine as if it were a CRI runtime. If you SSH to a current node and `docker ps` is unavailable, that is not proof that workloads are gone. It usually means you should inspect the CRI runtime with `crictl`, kubelet status, and the runtime service manager.

```bash
# What runtime is kubelet using?
kubectl get nodes -o wide
# Look at CONTAINER-RUNTIME column

# On a node, check containerd
systemctl status containerd
crictl info

# List running containers
crictl ps

# List images
crictl images

# Inspect a container
crictl inspect <container-id>
```

Before running this, what output do you expect from the `CONTAINER-RUNTIME` column on a kubeadm-style Kubernetes 1.35+ cluster? If your answer includes `containerd://` followed by a version, you are thinking at the right layer. That field comes from kubelet node status and tells you which runtime endpoint the node is actually using. It is often faster and safer than guessing from installed packages, because a node may contain old binaries that are no longer on the active path.

```bash
# Container runtime not responding
systemctl status containerd
journalctl -u containerd -f

# kubelet can't talk to runtime
journalctl -u kubelet | grep -i "runtime"

# Check CRI socket
ls -la /var/run/containerd/containerd.sock

# Verify kubelet configuration
cat /var/lib/kubelet/config.yaml | grep -i container
```

CRI troubleshooting starts with the symptom. If the node is `NotReady` and kubelet events mention a container runtime problem, inspect the runtime service first. If Pods are stuck waiting for images, check image pull events, registry reachability, and runtime logs. If kubelet cannot connect to a socket, the service may be stopped, the endpoint path may be wrong, or a distribution-specific configuration may have changed. You do not need to debug kernel namespaces first; you need to prove kubelet can reach a healthy CRI service and that the service can perform the requested image and container lifecycle operations.

A useful habit is to read the node as a pipeline. The API object can exist while the scheduler has not placed it. The Pod can be scheduled while kubelet has not created a sandbox. The sandbox can exist while CNI has not configured networking. The container can be created while image pulling or startup fails. CRI evidence lives in the stages where kubelet and the runtime exchange container lifecycle information, so commands such as `crictl ps`, `crictl pods`, `crictl inspect`, `journalctl -u kubelet`, and `journalctl -u containerd` are the practical bridge between Kubernetes objects and node reality.

There is one subtle runtime trap that shows up in mixed environments. Package presence does not always equal active runtime. A node image might contain Docker tooling for image-building convenience, containerd because it is the active CRI runtime, and distribution-specific helper scripts from an older bootstrap path. If you choose commands based only on what happens to be installed, you can inspect a dead service while kubelet is using a different socket. The node status runtime column and kubelet configuration are better anchors because they reveal the path kubelet is actually following.

Runtime choice also affects failure blast radius. If containerd is unhealthy on one worker, Pods already running on other workers may continue without issue, and the scheduler can place replacement Pods elsewhere if capacity exists. If every node in a pool shares a broken runtime configuration, the cluster may accept new workloads but fail to start them across the pool. This is why node-pool rollouts should include runtime smoke tests, not just a successful boot. A simple `crictl info` and a small test Pod can catch a bad endpoint before real workloads depend on it.

---

## Part 3: CNI - Container Network Interface

The Container Network Interface handles the network setup that makes a Pod more than a process on a node. Kubernetes requires that every Pod receive its own IP address and that Pods can communicate with each other without the application needing to perform manual NAT. The kubelet does not implement that network fabric directly. During Pod sandbox creation, the runtime invokes CNI plugins using configuration from the node, and those plugins create interfaces, assign IP addresses, install routes, and often participate in policy enforcement or overlay routing.

```
┌────────────────────────────────────────────────────────────────┐
│                       CNI Flow                                  │
│                                                                 │
│   1. kubelet creates pod sandbox (pause container)             │
│   2. kubelet calls CNI plugin: "Configure network for pod X"   │
│   3. CNI plugin:                                               │
│      - Creates veth pair (virtual ethernet)                    │
│      - Assigns IP from pool                                    │
│      - Sets up routes                                          │
│      - Connects pod to cluster network                         │
│   4. Pod can now communicate with other pods                   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The exact implementation differs sharply across plugins. Flannel emphasizes a simple overlay network, which is helpful when you want fewer knobs and do not need rich policy behavior. Calico can use routing and policy features that fit many production clusters, including environments where BGP or policy enforcement matters. Cilium uses eBPF to implement networking, security, and observability features with a different datapath model. Cloud-native plugins such as the AWS VPC CNI integrate Pod addresses with the cloud provider network, which simplifies some traffic paths but ties behavior to that provider's address management limits.

| Plugin | Key Features | Complexity |
|--------|--------------|------------|
| **Calico** | NetworkPolicy, BGP routing, high performance | Medium |
| **Cilium** | eBPF-based, observability, security | Higher |
| **Flannel** | Simple overlay network | Low |
| **Weave** | Encryption, easy setup | Low |
| **AWS VPC CNI** | Native VPC networking | AWS-specific |

The operational contract is usually visible in three places on each node. CNI binaries live under `/opt/cni/bin/`, configuration files live under `/etc/cni/net.d/`, and plugin agents often run as DaemonSet Pods in `kube-system` or another platform namespace. The first matching configuration file can matter, which is why stale files from old installations cause surprising behavior after a migration. A cluster may have healthy Calico Pods, but if a node still selects an old Flannel configuration, kubelet and the runtime may invoke the wrong plugin chain.

```bash
# List CNI binaries
ls /opt/cni/bin/

# List CNI configurations (first file wins!)
ls /etc/cni/net.d/

# Check the active CNI config
cat /etc/cni/net.d/10-calico.conflist  # Example for Calico
```

**Pause and predict:** you just ran `kubeadm init`, the control plane started, and CoreDNS Pods remain stuck in Pending. What is missing from the cluster, and why does CoreDNS reveal this absence before any user applications are deployed?

<details>
<summary>Check your prediction</summary>

kubeadm intentionally does not install a CNI network plugin. CoreDNS is the first normal workload scheduled on the cluster, so it immediately exposes whether the node network is ready to allocate Pod IP addresses and sandboxes.

</details>

Recognizing that basic bootstrapping stops short of network provisioning directs your immediate focus toward cluster add-on installation rather than control plane daemon troubleshooting.

```bash
# What CNI is running?
kubectl get pods -n kube-system | grep -E "calico|cilium|flannel|weave"

# Check CNI pod logs
kubectl logs -n kube-system -l k8s-app=calico-node --tail=50

# Verify pod IP allocation
kubectl get pods -o wide  # Check IP column

# Test pod-to-pod connectivity
kubectl exec pod-a -- ping <pod-b-ip>
```

When diagnosing CNI, separate control symptoms from data-path symptoms. If Pods cannot leave `ContainerCreating`, the plugin may not be invoked successfully, a binary may be missing, a configuration file may be invalid, or the node agent may be unhealthy. If Pods are Running but cannot reach each other, the plugin may be assigning addresses but failing at routes, encapsulation, policy, or host firewall integration. If only cross-node traffic fails, suspect overlay, routing, BGP, cloud security groups, or eBPF program state before blaming application containers.

```bash
# Pods stuck in ContainerCreating
kubectl describe pod <pod-name>
# Look for: "failed to set up sandbox container network"

# Check CNI configuration exists
ls -la /etc/cni/net.d/

# Check CNI binary exists
ls -la /opt/cni/bin/

# Check CNI agent logs
kubectl logs -n kube-system -l k8s-app=calico-node -c calico-node

# Node network issues
ip addr show  # Check interfaces
ip route     # Check routes
```

Exercise scenario: a learner builds a kubeadm cluster, skips CNI installation, and sees every normal workload stay in `ContainerCreating` with `network not ready` events. The fix might be a single `kubectl apply -f ...` command for the chosen plugin, but the lesson is larger than that command. Kubeadm prepares Kubernetes control-plane components; it does not decide your Pod network implementation. In production, the equivalent failure may come from a bad DaemonSet rollout, stale CNI configuration, or a node image that omitted required binaries, so the same diagnostic sequence still applies.

NetworkPolicy adds another layer of responsibility. Kubernetes defines the `NetworkPolicy` API, but enforcement is provided by the network plugin. A cluster using a simple plugin without policy support may accept policy objects while not enforcing them, depending on the plugin behavior and environment. For CKA purposes, remember that a connectivity failure after a policy change can be perfectly healthy CNI behavior rather than a broken network. Read the selected plugin, the namespace labels, the Pod labels, and the policy rules before assuming the datapath is damaged.

CNI also has a timing relationship with cluster bootstrap that explains many first-cluster surprises. Control-plane static Pods can run on the host network, so the API server may be healthy before general Pod networking exists. CoreDNS and ordinary application Pods need the Pod network, so they expose the missing add-on quickly. That is why a kubeadm cluster can look half alive: `kubectl` works, nodes may register, but workloads wait because the sandbox network cannot be created. The fix is not to rewrite Deployments; it is to install and verify the network plugin chosen for the Pod CIDR and environment.

In production-like clusters, CNI evidence should be collected per node, not only at the cluster level. A DaemonSet can show most replicas ready while one worker has a stale configuration file, missing binary, or host firewall drift. A policy change can affect only Pods with a certain label or namespace selector. A cloud-native CNI can exhaust assignable Pod addresses on a subset of nodes even while the cluster still has CPU and memory. These partial failures are why `kubectl get pods -o wide`, node names, and per-node plugin logs matter during network diagnosis.

Finally, be careful with connectivity tests. A successful Service request proves a different path than a direct Pod-IP request, because kube-proxy or an alternative service implementation may be involved. A same-node Pod ping proves less than a cross-node request, because cross-node traffic needs routing, encapsulation, cloud rules, or eBPF programs to work beyond the local host. Good tests name the path they are validating. In the hands-on exercise, you will create two Pods and read their IPs explicitly so you can reason about the CNI layer rather than accidentally testing only DNS or Services.

---

## Part 4: CSI - Container Storage Interface

The Container Storage Interface moves persistent-volume implementation out of Kubernetes core and into storage drivers. A PersistentVolumeClaim is an application request, not a disk by itself. A StorageClass points that request at a provisioner, parameters, reclaim policy, binding behavior, and expansion rules. CSI controller components create or delete the backing volume, while CSI node components publish the volume on the node where the Pod runs. That split lets storage systems integrate with Kubernetes without requiring their provisioning code to live inside the Kubernetes tree.

```
┌────────────────────────────────────────────────────────────────┐
│                        CSI Flow                                 │
│                                                                 │
│   PersistentVolumeClaim created                                │
│            │                                                    │
│            ▼                                                    │
│   StorageClass defines CSI driver                              │
│            │                                                    │
│            ▼                                                    │
│   CSI Controller (Deployment in kube-system)                   │
│   "Provision 10Gi volume from AWS EBS"                         │
│            │                                                    │
│            ▼                                                    │
│   Cloud Provider: Creates actual disk                          │
│            │                                                    │
│            ▼                                                    │
│   PersistentVolume created and bound                           │
│            │                                                    │
│            ▼                                                    │
│   Pod scheduled to node                                        │
│            │                                                    │
│            ▼                                                    │
│   CSI Node plugin: Attaches & mounts disk                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

CSI has two operational personalities. The controller side is cluster-scoped and handles work such as provisioning, deleting, attaching, detaching, snapshotting, and resizing, depending on driver capability. The node side runs on each worker and handles publish, unpublish, mount, unmount, and driver registration for that node. Existing Pods with already mounted volumes may continue reading and writing for a while if the controller is down, but new PVC provisioning, attach operations, and some lifecycle changes will fail. That distinction prevents you from chasing the wrong logs during a storage incident.

```
┌────────────────────────────────────────────────────────────────┐
│                   CSI Architecture                              │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              CSI Controller (Deployment)                 │  │
│   │  - Runs as pods in kube-system                          │  │
│   │  - Handles provisioning, attach/detach                  │  │
│   │  - Usually 1-3 replicas                                 │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              CSI Node Plugin (DaemonSet)                 │  │
│   │  - Runs on every node                                   │  │
│   │  - Handles mount/unmount                                │  │
│   │  - Registers node with CSI driver                       │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

| Driver | Storage | Environment |
|--------|---------|-------------|
| **ebs.csi.aws.com** | AWS EBS | AWS EKS |
| **pd.csi.storage.gke.io** | GCP Persistent Disk | GKE |
| **disk.csi.azure.com** | Azure Disk | AKS |
| **csi.vsphere.vmware.com** | vSphere | VMware |
| **rook-ceph.rbd.csi.ceph.com** | Ceph RBD | On-premises |
| **hostpath.csi.k8s.io** | Local path | Development |

Local storage and remote storage trade different failure modes. A local volume can be fast because data sits on the node's own disk, but it ties the workload to that node and complicates recovery when the node fails. A remote CSI-backed block volume may add attach latency or cloud API dependency, but it can often move with a rescheduled Pod inside the driver's constraints. Distributed storage systems such as Ceph add another set of trade-offs: more moving pieces and operational complexity in exchange for storage independence from a single cloud provider or node.

```bash
# List CSI drivers in cluster
kubectl get csidrivers

# Check CSI pods
kubectl get pods -n kube-system | grep csi

# View StorageClasses (use CSI drivers)
kubectl get storageclasses
kubectl describe storageclass <name>

# Check PV provisioner
kubectl get pv -o jsonpath='{.items[*].spec.csi.driver}'
```

**Pause and predict:** what would happen if the CSI controller pod crashed while the CSI node plugins on each worker were still running? Which storage operations continue functioning, and which storage operations fail immediately?

<details>
<summary>Check your prediction</summary>

Existing mounted volumes keep functioning because the filesystem mounts already exist on the worker nodes. However, provisioning new PersistentVolumeClaims, attaching volumes to new nodes, and deleting unneeded storage volumes will fail immediately until the controller recovers.

</details>

Distinguishing centralized control-plane driver lifecycle duties from distributed node-level mount operations guides engineers to target the appropriate component logs during storage cluster outages.

```bash
# PVC stuck in Pending
kubectl describe pvc <pvc-name>
# Look for: Events showing provisioning errors

# Check CSI controller logs
kubectl logs -n kube-system -l app=ebs-csi-controller -c ebs-plugin

# Check CSI node logs
kubectl logs -n kube-system -l app=ebs-csi-node -c ebs-plugin

# Verify CSI driver registered
kubectl get csinodes
kubectl describe csinode <node-name>
```

PVC troubleshooting is event-driven. A Pending PVC with a missing StorageClass is a different problem from a StorageClass that names an uninstalled provisioner, and both differ from a driver that lacks cloud permissions. `kubectl describe pvc` tells you which controller tried to provision and what error it received. `kubectl get storageclasses` tells you which provisioners are available to claims. `kubectl get csidrivers` and `kubectl get csinodes` tell you whether Kubernetes sees the driver registration. The driver logs then show provider-specific details that Kubernetes events may summarize too broadly.

The migration from in-tree storage plugins to CSI is also a maintenance story. In-tree plugins forced Kubernetes releases to carry provider-specific storage code, which made storage evolution depend on core release timing. CSI lets storage projects ship independently, fix bugs on their own cadence, and expose driver-specific capabilities through sidecars and CRDs. The trade-off is that cluster operators must now own those add-ons explicitly. A storage driver is not a passive library; it is a set of workloads, RBAC, sockets, node registrations, and external API permissions that should be monitored and upgraded.

Storage failures are often slower to recognize than runtime or network failures because the object model has more intermediate states. A PVC may be Pending for a while before anyone notices, especially if the application Deployment was applied at the same time and is waiting for the claim. A PV can be Bound while the Pod still fails to mount it on a specific node. A volume can attach successfully but fail at filesystem mount because of node dependencies or permissions. Reading PVC events, Pod events, and driver logs together helps you locate which storage transition failed instead of treating all storage errors as identical.

Topology is another reason CSI diagnosis requires more than checking whether a driver exists. Some volumes are restricted to a zone, region, node, or storage pool, and the scheduler must respect those constraints when placing Pods. A StorageClass with delayed binding can intentionally wait for Pod scheduling before provisioning so that the volume appears in the right topology. That behavior is healthy, but it can look confusing if you expect every PVC to bind immediately. When you see `WaitForFirstConsumer` or topology terms, read them as scheduling coordination rather than automatic evidence of a broken driver.

---

## Part 5: Reading Extension Evidence End to End

The fastest way to debug extension interfaces is to avoid treating CRI, CNI, and CSI as disconnected acronyms. Start with the observed object and ask which contract must have succeeded immediately before the object could advance. A Pod that is unscheduled has not reached kubelet, so extension debugging is premature. A Pod assigned to a node but waiting on sandbox creation points toward runtime or network setup. A Running Pod with a failed mount points toward storage publication. A Pending PVC that has never bound points toward StorageClass, provisioner, permissions, or controller behavior rather than application code.

| Interface | Kubernetes Talks To | Plugin Provides | Config Location |
|-----------|--------------------|--------------------|-----------------|
| CRI | Container runtime | Container lifecycle | `/var/run/containerd/` |
| CNI | Network plugin | Pod IPs, routing, policies | `/etc/cni/net.d/` |
| CSI | Storage driver | Volume provisioning, mount | CSI Driver CRDs |

The interface summary is intentionally compact, but every cell points to evidence. For CRI, use node status, runtime service state, CRI socket paths, `crictl`, and kubelet runtime errors. For CNI, use the node's CNI directories, plugin DaemonSet logs, Pod events, IP allocation, and packet tests between Pods. For CSI, use StorageClasses, PVC events, `CSIDriver` and `CSINode` resources, controller logs, node plugin logs, and mount evidence from the target Pod. This is not a random checklist; it is a map from Kubernetes abstraction to the component that must fulfill it.

When you are under time pressure, write down the current lifecycle stage in plain language. "The Pod was scheduled but the sandbox network failed" is more useful than "the Pod is broken." "The claim has not been provisioned" is more useful than "storage is broken." "The runtime service is stopped" is more useful than "the node is bad." These short diagnoses force you to name the interface and the missing transition. They also produce cleaner fixes, because you can verify that the exact transition now succeeds after your change.

```bash
# ===== CRI Issues =====
# Symptom: Pods won't start, "container runtime not running"
systemctl status containerd
journalctl -u containerd
crictl info

# ===== CNI Issues =====
# Symptom: Pods stuck in ContainerCreating, "network not ready"
ls /etc/cni/net.d/
kubectl get pods -n kube-system | grep -E "calico|cilium|flannel"
kubectl logs -n kube-system <cni-pod>

# ===== CSI Issues =====
# Symptom: PVC stuck in Pending, "provisioning failed"
kubectl get csidrivers
kubectl describe pvc <name>
kubectl logs -n kube-system <csi-controller-pod>
```

Which approach would you choose here and why: starting from node services, starting from Pod events, or starting from plugin Pods? In an exam, start from Kubernetes events when you have an object symptom, because they tell you what the control plane and kubelet already tried. Move to node services when the event mentions runtime, sandbox, or mount failures. Move to plugin Pods when the event names a plugin or provisioner. This order keeps you from spending precious time in low-level commands before you know which interface owns the failure.

---

## Patterns & Anti-Patterns

Good platform teams treat extension interfaces as first-class cluster components. They do not merely apply a CNI YAML once, install a runtime package once, and forget the system exists. They version node images, plugin manifests, RBAC, StorageClasses, and upgrade procedures together, because those pieces form the invisible floor beneath every workload. The patterns below are useful because they reduce ambiguity during failures: each one makes the active implementation discoverable, testable, and replaceable without relying on memory.

| Pattern | When to Use It | Why It Works | Scaling Considerations |
|---------|----------------|--------------|------------------------|
| Declare one active CNI configuration per node | Any kubeadm or self-managed cluster | Kubelet and the runtime invoke a predictable plugin chain | Enforce with image build checks or node bootstrap validation |
| Standardize runtime inspection with `crictl` | Kubernetes 1.35+ nodes using CRI runtimes | The tool speaks the same interface kubelet uses | Configure endpoints consistently across node pools |
| Treat StorageClasses as platform APIs | Multi-team clusters with dynamic provisioning | App teams request capabilities without embedding provider details | Document defaults, reclaim policy, expansion, and topology behavior |
| Monitor controller and node plugin Pods separately | CSI and advanced CNI deployments | Controller failures and node failures produce different symptoms | Alert on DaemonSet coverage, controller availability, and registration resources |

Anti-patterns usually come from assuming that Kubernetes core owns more than it actually owns. A team sees a Pod stuck in `ContainerCreating` and restarts the API server, even though the event says CNI setup failed on a worker. Another team changes application YAML to work around a Pending PVC, even though the StorageClass points at a missing driver. These responses waste time because they fight the wrong layer. The better alternative is to follow the contract boundary and ask which external component failed to deliver its part of the lifecycle.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Installing multiple CNIs and leaving old config files | Nodes may select stale configuration before the intended plugin | Remove stale files and validate `/etc/cni/net.d/` during bootstrap |
| Using `docker` commands as the only runtime diagnostic | Modern nodes may not run Docker Engine at all | Use `kubectl get nodes -o wide` and `crictl` against the CRI endpoint |
| Creating PVCs before installing a matching CSI driver | Claims stay Pending with provisioner errors | Install and verify the driver, then define StorageClasses and claims |
| Treating NetworkPolicy as always enforced | Some plugins do not implement policy enforcement | Confirm plugin capability and test allowed and denied paths |
| Ignoring plugin namespace health | Add-on Pods can fail while core components appear healthy | Include CNI and CSI DaemonSets, Deployments, and logs in triage |

The pattern you should internalize is evidence before action. Restarting kubelet, deleting Pods, or reinstalling a plugin may appear to fix a symptom temporarily, but it can also erase the evidence that would have identified the real contract breach. On a practice cluster you can experiment freely, but in a production-style mindset you first capture events, logs, selected configuration, and resource state. Then you change the smallest layer that explains the symptom. That discipline is exactly what the CKA exam rewards when a task gives you a broken node or storage claim.

For teams running many clusters, these patterns become automation requirements. Node conformance checks can verify the runtime socket, CNI binaries, CNI configuration, and plugin DaemonSet readiness before a node joins the schedulable pool. Storage smoke tests can create a small claim, mount it, write a file, and delete it after upgrades. Network smoke tests can run same-node and cross-node Pod connectivity checks. None of these tests replace monitoring, but they catch the most damaging interface regressions at the moment they are introduced, when rollback is still simple.

---

## Decision Framework

Use the interface decision framework when a workload does not reach the state you expect. The first branch is whether the object has been scheduled, because unscheduled Pods are scheduler or resource-placement problems rather than CRI, CNI, or CSI problems. The second branch is whether kubelet can create the sandbox and containers. The third branch is whether the Pod has network or storage dependencies that fail after container start. This keeps your troubleshooting path aligned with the lifecycle instead of with whichever plugin name you remember first.

| Symptom | First Interface to Suspect | Evidence to Gather | Likely Next Move |
|---------|----------------------------|--------------------|------------------|
| Node `NotReady` with runtime messages | CRI | `journalctl -u kubelet`, `systemctl status containerd`, `crictl info` | Restore runtime service or fix kubelet runtime endpoint |
| Pod stuck in `ContainerCreating` with sandbox network error | CNI | Pod events, `/etc/cni/net.d/`, `/opt/cni/bin/`, CNI DaemonSet logs | Repair CNI config, binaries, or node agent |
| Pod Running but cross-node traffic fails | CNI | Pod IPs, routes, plugin logs, policy objects, node firewalls | Diagnose routing, overlay, policy, or cloud security rules |
| PVC Pending with provisioning event | CSI | PVC events, StorageClass provisioner, CSI controller logs | Fix StorageClass, driver installation, or external permissions |
| Pod fails to mount a bound PVC | CSI | Pod events, `CSINode`, node plugin logs, mount paths | Inspect node plugin and volume publish operations |
| Container image pulled but process will not start | CRI and workload config | `crictl inspect`, container logs, Pod events | Separate runtime failure from application command failure |

When choosing between implementations, begin with environment constraints rather than popularity. Containerd is a strong default for many clusters because it is common, mature, and well supported by Kubernetes distributions. CRI-O may be preferable where the platform stack standardizes around it. Calico is often a practical network choice when policy and routing flexibility matter. Cilium is compelling when eBPF observability and security features justify the additional learning curve. Flannel can still be useful in simple labs where policy and advanced visibility are not the goal. CSI choice is usually dictated by where your data lives and what recovery behavior the workload requires.

There is also a migration decision hiding in this framework. Swapping a CNI or CSI driver is not like changing an application label, because existing node state, IP allocation, routes, volume attachments, and plugin-specific CRDs may exist. The interface gives Kubernetes a standard way to call the implementation, but it does not magically translate one provider's operational state into another provider's state. Plan migrations with compatibility notes, maintenance windows, rollback steps, and tests that prove new Pods, existing Pods, new PVCs, and existing volumes behave as expected.

Use defaults deliberately. A default StorageClass is convenient because developers can create PVCs without naming a class, but it is also a platform promise about cost, performance, topology, reclaim behavior, and expansion. A default CNI choice is convenient because every workload gets networking without thinking about the implementation, but it also defines your NetworkPolicy behavior and observability options. A default runtime reduces node variance, but it should still be documented in node build standards. Defaults are useful when they are explicit; they are dangerous when nobody remembers who chose them or how to verify them.

The same framework helps you communicate during incidents. Instead of saying "Kubernetes networking is down," say "new Pod sandboxes on node pool A fail CNI setup, while existing Pods continue passing traffic." Instead of saying "storage is down," say "new PVC provisioning through the EBS CSI controller fails with an authorization error, while already mounted volumes remain healthy." That level of precision changes the repair path and the people you involve. It also keeps application teams from changing code when the platform contract is the real failing component.

---

## Did You Know?

- Docker images continued to work after Kubernetes 1.24 removed dockershim because the image format and the kubelet runtime adapter are different concerns; OCI-compatible images can be pulled and run by containerd or CRI-O.
- CNI configuration file order can matter because runtimes select configuration from `/etc/cni/net.d/`; numeric prefixes such as `10-calico.conflist` are commonly used to make selection predictable.
- CSI was introduced so storage vendors could ship drivers outside the Kubernetes core release cycle, replacing the older in-tree plugin model with a standardized external driver interface.
- Cilium relies on eBPF capabilities in the Linux kernel, which is why kernel version and distribution support are part of the operational decision rather than just plugin preference.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Forgetting to install CNI after kubeadm initialization | kubeadm creates the control plane but intentionally leaves the Pod network choice to the operator | Install one supported CNI plugin, then confirm node readiness, CoreDNS readiness, and Pod IP allocation |
| Leaving multiple CNI configuration files on a node | Old plugin files remain after migration or lab experimentation | Keep one intended configuration chain in `/etc/cni/net.d/` and remove stale files during node bootstrap |
| Using `docker ps` as the runtime source of truth | Learners remember older Docker-based nodes and miss the CRI change | Check the node runtime column and use `crictl` against the active CRI endpoint |
| Debugging PVC Pending from the application Pod first | The claim has not been provisioned, so no Pod-level mount exists yet | Read PVC events, StorageClass provisioner names, and CSI controller logs before changing the workload |
| Checking only CSI controller logs for mount failures | Volume publishing happens on the node where the Pod runs | Inspect `CSINode`, node plugin logs, and Pod events for attach and mount evidence |
| Assuming every CNI enforces NetworkPolicy | The API object is standard, but enforcement depends on plugin capability | Verify plugin support and test both allowed and denied traffic paths |
| Restarting kubelet before collecting evidence | Restarting can clear timing, socket, or event clues needed for diagnosis | Capture Pod events, kubelet logs, plugin logs, and selected config before applying a fix |

---

## Quiz

<details>
<summary>1. Your team migrated a lab cluster from Flannel to Cilium. A developer asks whether every Deployment manifest must be rewritten because the network plugin changed. What do you answer?</summary>

No application manifest rewrite is normally required just because the CNI implementation changed. Kubernetes asks the selected plugin to provide Pod networking through the CNI contract, so Pods still receive IP addresses, Services still target Pods, and DNS still resolves names through the same Kubernetes abstractions. The operational behavior can change, especially around NetworkPolicy, observability, routing, and kernel requirements, so you validate connectivity and policy behavior after the migration. The correct action is to test the platform layer, not to edit every workload spec.

</details>

<details>
<summary>2. After a node reboot, Pods on that node stay in `ContainerCreating`. The node contains both `10-calico.conflist` and `05-flannel.conflist` under `/etc/cni/net.d/`. What is the likely problem and fix?</summary>

The likely problem is stale CNI configuration selection. If the runtime reads the earlier Flannel configuration while the cluster is intended to use Calico, sandbox network setup can fail because the chosen plugin chain does not match the installed agents and binaries. The fix is to remove the stale configuration, confirm only the intended CNI config remains, and recreate or restart the affected Pods after kubelet can invoke the correct plugin. You should also check node bootstrap or image-building steps so the same stale file does not return on replacement nodes.

</details>

<details>
<summary>3. A PersistentVolumeClaim has been Pending for several minutes. `kubectl get csidrivers` lists the expected driver and the controller Pods are Running. Where do you look next?</summary>

Start with `kubectl describe pvc <name>` because the Events section tells you which provisioner handled the claim and what error it reported. Then compare the PVC's requested StorageClass with `kubectl get storageclasses` and inspect the CSI controller logs for provider-specific errors. Common causes include a StorageClass that names a different provisioner, missing external cloud permissions, unsupported parameters, or topology constraints that prevent provisioning. The fact that `CSIDriver` exists proves registration, not successful volume creation.

</details>

<details>
<summary>4. A colleague upgrades from Kubernetes 1.23 to a newer release and panics because `docker ps` no longer works on nodes, even though Pods are still Running. What do you tell them?</summary>

Tell them that losing the Docker CLI path does not mean containers or images disappeared. Kubernetes removed dockershim in 1.24, so kubelet no longer needs to talk to Docker Engine as its runtime adapter. Modern nodes commonly use containerd or CRI-O through CRI, and `crictl ps` is the right node-side inspection tool. Docker-built images still work when they are OCI-compatible, because the image artifact and the kubelet runtime interface are separate concerns.

</details>

<details>
<summary>5. A Pod is Running, but traffic to a Pod on another node times out while traffic to a same-node Pod succeeds. Which interface owns the first investigation path?</summary>

This points first toward CNI data-path behavior, not CRI, because the containers are already running and same-node communication narrows the failure to network routing or policy between nodes. Check Pod IPs, routes, the CNI DaemonSet logs, NetworkPolicy objects, node firewalls, cloud security groups, and plugin-specific status. The exact next command depends on the plugin, but the reasoning is stable: cross-node communication requires the network implementation to route, encapsulate, or program the datapath correctly. CRI would be more likely if containers failed to start at all.

</details>

<details>
<summary>6. A Pod using a bound PVC fails with a mount error on only one worker node. The PVC and PV look healthy. Which CSI component should you inspect first?</summary>

Inspect the CSI node plugin on the worker where the Pod was scheduled, along with the Pod events and `CSINode` information. A bound PVC and PV show that provisioning succeeded, so the controller side has likely done its job. Mounting and publishing the volume into the Pod are node-side responsibilities, and a single-node failure usually points to node plugin health, host mount dependencies, device attachment, permissions, or node-specific driver registration. Controller logs can still help later, but they are not the first place for a node-local mount failure.

</details>

---

## Hands-On Exercise

This exercise asks you to inspect the extension interfaces on a live practice cluster. Use a disposable cluster or the linked lab environment rather than a shared production system, because a few drills intentionally explore failure modes. The main path is read-only, and the optional break-fix drills are clearly marked. Your goal is to build a repeatable diagnostic notebook: identify the runtime, identify the network plugin, inspect CNI node files, prove Pod-to-Pod connectivity, and find storage drivers if the cluster includes CSI.

**Task**: Explore your cluster's CRI, CNI, and CSI configuration from Kubernetes objects down to node-level evidence, then explain which interface each observation proves.

### Task 1: Identify your container runtime

```bash
kubectl get nodes -o wide
# Note the CONTAINER-RUNTIME column
```

<details>
<summary>Solution notes</summary>

Look for a value such as `containerd://...` or `cri-o://...` in the `CONTAINER-RUNTIME` column. That value is reported through node status and is a better first answer than guessing from packages installed on the host. If the node is NotReady, combine this with kubelet logs and runtime service status before moving to CNI or CSI.

</details>

### Task 2: Explore CRI from a node

```bash
# On a node (SSH or kubectl debug node)
crictl info
crictl ps
crictl images | head -10
```

<details>
<summary>Solution notes</summary>

`crictl info` confirms the CRI endpoint is responding. `crictl ps` shows containers known to the runtime, and `crictl images` shows images cached on the node. If these commands cannot connect, check the runtime socket path and the runtime service before assuming Kubernetes objects are wrong.

</details>

### Task 3: Identify your CNI plugin

```bash
kubectl get pods -n kube-system | grep -E "calico|cilium|flannel|weave"
```

<details>
<summary>Solution notes</summary>

The output usually shows a DaemonSet-style agent for the active network plugin. Some managed clusters use provider-specific names, so absence of these exact strings is not proof that no CNI exists. Combine this check with node CNI files and Pod IP allocation.

</details>

### Task 4: Check CNI configuration on a node

```bash
# On a node
ls -la /etc/cni/net.d/
cat /etc/cni/net.d/*.conflist | head -30
```

<details>
<summary>Solution notes</summary>

You should see configuration for the intended plugin and not a pile of stale files from previous experiments. If multiple files exist, inspect ordering and content. A mismatch between the running plugin DaemonSet and the selected node configuration is a classic cause of sandbox network errors.

</details>

### Task 5: Check Pod networking

```bash
# Create two pods
kubectl run test1 --image=nginx:alpine
kubectl run test2 --image=nginx:alpine

# Wait for pods to be ready
kubectl wait --for=condition=Ready pod/test1 pod/test2 --timeout=60s

# Get their IPs
kubectl get pods -o wide

# Test connectivity
TEST2_IP=$(kubectl get pod test2 -o jsonpath='{.status.podIP}')
kubectl exec test1 -- wget -qO- $TEST2_IP:80
```

<details>
<summary>Solution notes</summary>

Successful output from NGINX proves basic Pod-to-Pod traffic to the target Pod IP. If the Pods never become Ready, go back to events and CNI setup. If they are Running but the connection fails, inspect policies, routes, plugin logs, and whether the Pods landed on the same or different nodes.

</details>

### Task 6: Check CSI drivers

```bash
kubectl get csidrivers
kubectl get storageclasses
```

<details>
<summary>Solution notes</summary>

Some lab clusters may not include dynamic CSI provisioning, while managed clusters usually do. `CSIDriver` tells you which drivers are registered, and StorageClasses tell you which provisioners application teams can request. A StorageClass without a matching healthy driver is a broken platform API.

</details>

**Card A: Missing CNI means the control plane is down.** An administrator notices newly scheduled Pods stuck in the ContainerCreating state across several worker nodes and immediately concludes that the control plane API server has failed. Assuming that the management layer has collapsed, they initiate a reboot of all control plane nodes rather than checking node network configuration. This misdiagnosis wastes valuable recovery time while leaving the true network plugin deficit untouched.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing control plane object scheduling with worker node sandbox networking. Next action: run `kubectl describe pod` to inspect network events and verify configuration files under `/etc/cni/net.d/` on the affected worker node.

</details>

**Card B: Empty `docker ps` means all cluster containers are gone.** A troubleshooter logs into a modern Kubernetes worker node and executes `docker ps` to inspect active container processes across the system. When the command prints an empty table with no active workloads, they assume all cluster Pods running on the host have crashed simultaneously. They begin an emergency escalation for container recovery without realizing the node uses containerd or CRI-O as its underlying runtime.

<details>
<summary>Check your prediction</summary>

Failure layer: querying the wrong container runtime daemon on nodes managed by CRI. Next action: inspect the node container runtime using `kubectl get nodes -o wide` and execute `crictl ps` to inspect active containers through the CRI endpoint.

</details>

**Card C: Pending PVC always means the node disk is full.** An engineer observes that a PersistentVolumeClaim remains stuck in the Pending state indefinitely after being submitted to the cluster. Convinced that the local physical disk storage on the target worker node has reached maximum capacity, they log into the machine to purge container images and delete log files. They spend hours freeing disk space while the volume claim continues waiting for a non-existent StorageClass provisioner.

<details>
<summary>Check your prediction</summary>

Failure layer: mistaking control-plane storage volume provisioning and driver binding for local disk exhaustion. Next action: run `kubectl describe pvc <name>` to inspect controller events and verify that the specified StorageClass references a valid CSI driver.

</details>

**Card D: kubeadm init installed a CNI, so CoreDNS Pending is a scheduler bug.** An operator finishes bootstrapping a new single-node control plane with `kubeadm init` and discovers that CoreDNS Pods stay in the Pending state indefinitely. Believing that the bootstrap process automatically installed an operational networking plugin, they conclude that the kube-scheduler daemon has encountered an internal bug. They repeatedly restart the scheduler static pod while the cluster continues waiting for a Pod network provider.

<details>
<summary>Check your prediction</summary>

Failure layer: assuming cluster bootstrapping tools provision Pod network plugins automatically. Next action: install a compatible CNI plugin such as Calico or Cilium so worker nodes transition to Ready and schedule CoreDNS Pods.

</details>

**Success Criteria**: You are done when you can support each claim with command output rather than memory or plugin-name guessing.

- [ ] Can identify container runtime in use from node status and CRI tooling.
- [ ] Can use `crictl` to inspect containers, images, and runtime responsiveness.
- [ ] Can identify the CNI plugin and compare running add-on Pods with node CNI configuration.
- [ ] Can explain the Pod-to-Pod networking path from Pod sandbox creation to IP connectivity.
- [ ] Can identify installed CSI drivers and StorageClasses, or explain why none are present in a lab cluster.
- [ ] Can choose the first diagnostic layer for CRI, CNI, and CSI symptoms without guessing.

**Cleanup**: Remove only the temporary Pods created by this exercise so the cluster returns to its previous workload state.

```bash
kubectl delete pod test1 test2
```

### Drill 1: Interface Identification

Match each tool or plugin to its interface before opening the answer. This looks simple, but it builds the reflex you need under exam timing: name the contract first, then select the evidence.

| Tool/Plugin | Interface (CRI/CNI/CSI) |
|-------------|-------------------------|
| containerd | ___ |
| Calico | ___ |
| AWS EBS driver | ___ |
| CRI-O | ___ |
| Cilium | ___ |
| Rook-Ceph | ___ |

<details>
<summary>Answers</summary>

1. CRI - Container Runtime Interface
2. CNI - Container Network Interface
3. CSI - Container Storage Interface
4. CRI - Container Runtime Interface
5. CNI - Container Network Interface
6. CSI - Container Storage Interface

</details>

### Drill 2: CRI Troubleshooting - Container Runtime Down

Only run this on a disposable practice node you can recover. The point is to observe that a stopped runtime produces node and Pod symptoms even when the API server continues to answer.

```bash
# Setup: Stop containerd (WARNING: breaks cluster temporarily!)
# Only do on practice nodes you can restart!
sudo systemctl stop containerd

# Observe the damage
kubectl get nodes  # Node becomes NotReady
NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl describe node $NODE_NAME | grep -A5 Conditions

# YOUR TASK: Restore containerd and verify recovery
```

<details>
<summary>Solution</summary>

```bash
sudo systemctl start containerd
sudo systemctl status containerd

# Wait for node to recover
kubectl wait --for=condition=Ready node --all --timeout=120s

# Verify containers running
sudo crictl ps
```

</details>

### Drill 3: CNI Troubleshooting - Pods Stuck in ContainerCreating

Only run this on a disposable practice node. Removing CNI configuration blocks new sandbox networking on that node, which is exactly why this failure mode is so recognizable in kubeadm labs.

```bash
# Setup: Temporarily break CNI config
sudo mkdir -p /tmp/cni-backup
sudo mv /etc/cni/net.d/* /tmp/cni-backup/

# Create a test pod
kubectl run cni-broken --image=nginx

# Observe
kubectl get pods  # ContainerCreating forever
kubectl describe pod cni-broken | grep -A10 Events

# YOUR TASK: Diagnose and fix
```

<details>
<summary>Solution</summary>

```bash
# Check CNI config directory
ls /etc/cni/net.d/  # Empty!

# Restore CNI config
sudo mv /tmp/cni-backup/* /etc/cni/net.d/

# Delete stuck pod and recreate
kubectl delete pod cni-broken --force --grace-period=0
kubectl run cni-fixed --image=nginx
kubectl get pods  # Running!

# Cleanup
kubectl delete pod cni-fixed
```

</details>

### Drill 4: crictl Mastery

Practice using `crictl` until it feels as normal as `kubectl` for node-level runtime inspection. The commands below are intentionally read-only except for whatever logs the running containers already produce.

```bash
# 1. List all running containers
sudo crictl ps

# 2. List all pods (sandbox containers)
sudo crictl pods

# 3. Get container logs
CONT_ID=$(sudo crictl ps -q | head -n 1)
sudo crictl logs $CONT_ID

# 4. Inspect a container
sudo crictl inspect $CONT_ID | head -50

# 5. List images
sudo crictl images

# 6. Get runtime info
sudo crictl info
```

### Drill 5: CSI Driver Investigation

Explore CSI resources in your cluster and connect each resource to the lifecycle stage it supports. If your lab has no CSI drivers, write that down explicitly; recognizing absence is still useful evidence.

```bash
# List all CSI drivers
kubectl get csidrivers

# Get details on a driver
DRIVER_NAME=$(kubectl get csidrivers -o jsonpath='{.items[0].metadata.name}')
kubectl describe csidriver $DRIVER_NAME

# Check CSI nodes
kubectl get csinodes
NODE_NAME=$(kubectl get csinodes -o jsonpath='{.items[0].metadata.name}')
kubectl describe csinode $NODE_NAME

# View StorageClasses using CSI
kubectl get sc -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.provisioner}{"\n"}{end}'
```

### Drill 6: CSI Provisioning - Create PVC with StorageClass

Practice the full CSI workflow from PVC to mounted volume. This drill requires a cluster with a working default StorageClass, so skip it on labs that intentionally omit dynamic storage.

```bash
# Check available StorageClasses
kubectl get sc

# Create a PVC using the default StorageClass
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: csi-test-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  # storageClassName: standard  # Uncomment to use specific class
EOF

# Watch the PVC get bound (CSI provisioner creates PV)
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/csi-test-pvc --timeout=60s

# Check the dynamically provisioned PV
kubectl get pv

# Create a pod that uses the PVC
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: csi-test-pod
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: csi-test-pvc
EOF

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/csi-test-pod --timeout=60s

# Verify the volume is mounted
kubectl exec csi-test-pod -- df -h /data

# Write test data
kubectl exec csi-test-pod -- sh -c "echo 'CSI works!' > /data/test.txt"
kubectl exec csi-test-pod -- cat /data/test.txt

# Cleanup
kubectl delete pod csi-test-pod
kubectl delete pvc csi-test-pvc
```

### Drill 7: Network Connectivity Test

Verify CNI behavior across nodes when your cluster has more than one worker. On a single-node lab, this still verifies Pod IP allocation and same-node connectivity, but it will not prove cross-node routing.

```bash
# Create pods on different nodes
NODE1=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
NODE2=$(kubectl get nodes -o jsonpath='{.items[1].metadata.name}' 2>/dev/null)
NODE2=${NODE2:-$NODE1}  # single-node clusters fall back to NODE1
kubectl run net-test-1 --image=nginx:alpine --overrides='{"spec":{"nodeName":"'"$NODE1"'"}}'
kubectl run net-test-2 --image=nginx:alpine --overrides='{"spec":{"nodeName":"'"$NODE2"'"}}'

# Wait for running
kubectl wait --for=condition=Ready pod/net-test-1 pod/net-test-2 --timeout=60s

# Get IPs
POD1_IP=$(kubectl get pod net-test-1 -o jsonpath='{.status.podIP}')
POD2_IP=$(kubectl get pod net-test-2 -o jsonpath='{.status.podIP}')

# Test cross-node connectivity
kubectl exec net-test-1 -- wget -qO- --timeout=5 $POD2_IP:80
kubectl exec net-test-2 -- wget -qO- --timeout=5 $POD1_IP:80

# Cleanup
kubectl delete pod net-test-1 net-test-2
```

### Drill 8: Challenge - Identify All Plugins

Without opening documentation, identify all three extension layers in your cluster and write down the evidence that supports each answer. This is the closest drill to exam behavior because it forces you to classify symptoms and evidence quickly.

```bash
# 1. Find container runtime
kubectl get nodes -o wide | awk '{print $NF}'

# 2. Find CNI plugin
ls /etc/cni/net.d/
kubectl get pods -n kube-system | grep -E "calico|cilium|flannel|weave"

# 3. Find CSI drivers
kubectl get csidrivers
kubectl get sc

# Write down what you found - this is exam knowledge!
```

---

## Sources

- [Kubernetes Container Runtimes](https://kubernetes.io/docs/setup/production-environment/container-runtimes/)
- [Kubernetes CRI API](https://kubernetes.io/docs/concepts/architecture/cri/)
- [Kubernetes Network Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
- [Kubernetes Cluster Networking](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Kubernetes CSI Drivers](https://kubernetes.io/docs/concepts/storage/volumes/#csi)
- [Kubernetes CSIDriver API](https://kubernetes.io/docs/reference/kubernetes-api/config-and-storage-resources/csi-driver-v1/)
- [Kubernetes Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [containerd documentation](https://containerd.io/docs/)
- [CRI-O project](https://cri-o.io/)
- [CNI specification](https://www.cni.dev/docs/spec/)
- [CSI specification](https://github.com/container-storage-interface/spec)
- [KubeDojo lab: CKA 1.2 Extension Interfaces](https://killercoda.com/kubedojo/scenario/cka-1.2-extension-interfaces)

## Next Module

[Module 1.3: Helm](../module-1.3-helm/) - Next you will move from node extension interfaces to packaging repeatable Kubernetes applications with charts, releases, values, and upgrade workflows.
