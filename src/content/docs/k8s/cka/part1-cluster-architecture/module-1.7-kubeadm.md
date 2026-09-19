---
revision_pending: false
title: "Module 1.7: kubeadm Basics - Cluster Bootstrap"
slug: k8s/cka/part1-cluster-architecture/module-1.7-kubeadm
sidebar:
  order: 8
lab:
  id: cka-1.7-kubeadm
  url: https://killercoda.com/kubedojo/scenario/cka-1.7-kubeadm
  duration: "40 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Essential cluster management
>
> **Time to Complete**: 60-75 minutes
>
> **Prerequisites**: Module 1.1 (Control Plane), Module 1.2 (Extension Interfaces)

---

## What You'll Be Able to Do

After this module, you will be able to:
- **Design** a kubeadm bootstrap sequence that covers preflight checks, `kubeadm init`, CNI installation, and worker join tokens.
- **Diagnose** static pod and kubelet failures by using local logs, manifests, and container runtime tools when the API server is unavailable.
- **Evaluate** certificate and etcd maintenance risk by checking expiry, planning renewal, and protecting snapshots before disruptive work.
- **Implement** safe node maintenance with cordon, drain, uncordon, and kubeadm reset workflows.

---

## Why This Module Matters

Hypothetical scenario: you inherit a small kubeadm cluster that runs an internal platform team service, and the control plane is healthy until a routine node reboot exposes a forgotten bootstrap detail. New pods stop receiving IP addresses, a replacement worker cannot join, and `kubectl` works from one administrator laptop but not from another. Nothing about the incident requires exotic Kubernetes knowledge, yet the cluster remains stuck because the team only knows managed-cluster abstractions and has never looked at `/etc/kubernetes`, kubelet static pod manifests, bootstrap tokens, or the certificates kubeadm creates during initialization.

kubeadm matters because it is deliberately close to the machinery. Managed services hide most of this machinery until something underneath them leaks, but the CKA exam expects you to reason from first principles when a node will not join, a static pod keeps returning after deletion, a certificate is close to expiry, or a drained node remains unschedulable after maintenance. The point of this module is not to memorize every kubeadm subcommand. The point is to connect each file, certificate, token, and node operation to the control-plane behavior you already studied in earlier modules.

Think of kubeadm like a construction foreman with blueprints. When you run `kubeadm init`, it does not become the building, and it does not keep managing every brick after the cluster exists. It lays the foundation by generating certificates and kubeconfigs, places the control plane into static pod manifests, asks kubelet to keep those pods running, and prints a join instruction for future workers. Once that foundation exists, your operational job changes from "run the installer" to "protect the files and processes that installer created."

This module rewrites the old quick reference into a working mental model. You will first map the bootstrap sequence, then practice the commands that initialize a control plane, install networking, join nodes, inspect static pods, protect certificates and etcd data, and perform node maintenance. By the end, a kubeadm cluster should feel less like a magic script and more like a set of inspectable contracts between kubeadm, kubelet, the container runtime, the API server, and the files on disk.

---

## Bootstrap Anatomy: What kubeadm Builds

kubeadm is best understood as a bootstrap coordinator rather than a full cluster lifecycle platform. It validates the host, writes certificate material, creates kubeconfig files, renders static pod manifests, and arranges enough cluster add-ons for the API server to become usable. It does not install your container runtime, decide your cloud load balancer design, pick your CNI plugin, or keep editing your operating system after the cluster is initialized. That boundary is useful because it keeps kubeadm predictable, but it also means a broken prerequisite remains your responsibility.

The first practical lesson is that kubeadm creates a Kubernetes control plane by asking kubelet to run static pods. That design feels indirect at first: instead of starting `kube-apiserver` with systemd, kubeadm writes a YAML file into a watched directory, and kubelet starts the container from that manifest. This is why a kubeadm control plane can recover its API server container even when the API server itself is temporarily unavailable. The local kubelet is the supervisor for the control-plane containers, so file-level diagnosis remains possible when API-level diagnosis is not.

```text
┌────────────────────────────────────────────────────────────────┐
│                    kubeadm init Process                         │
│                                                                 │
│   1. Pre-flight Checks                                         │
│      └── Verify system requirements (CPU, memory, ports)       │
│                                                                 │
│   2. Generate Certificates                                     │
│      └── CA, API server, kubelet, etcd certificates           │
│      └── Stored in /etc/kubernetes/pki/                        │
│                                                                 │
│   3. Generate kubeconfig Files                                 │
│      └── admin.conf, kubelet.conf, controller-manager.conf     │
│      └── Stored in /etc/kubernetes/                            │
│                                                                 │
│   4. Generate Static Pod Manifests                             │
│      └── API server, controller-manager, scheduler, etcd       │
│      └── Stored in /etc/kubernetes/manifests/                  │
│                                                                 │
│   5. Start kubelet                                             │
│      └── kubelet reads manifests and starts control plane      │
│                                                                 │
│   6. Apply Cluster Configuration                               │
│      └── CoreDNS, kube-proxy DaemonSet                        │
│                                                                 │
│   7. Generate Join Token                                       │
│      └── For worker nodes to join                              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The sequence above gives you a reliable troubleshooting order. If `kubeadm init` fails before certificates are written, you look at preflight checks, swap, host identity, ports, and the container runtime. If certificates and kubeconfigs exist but the API server is unavailable, you inspect kubelet logs and static pod containers. If the API server is reachable but CoreDNS is pending, you check whether a CNI plugin was installed and whether its pod CIDR matches the cluster configuration. Each failure point narrows the search space because kubeadm leaves visible artifacts behind.

kubeadm also has deliberate non-goals, and those non-goals are exam-relevant. It does not install containerd, kubelet, kubeadm, or kubectl for you. It does not install a CNI plugin during `init`, because CNI choice depends on the networking model you want. It does not build an external load balancer for an HA control plane, because that belongs to your infrastructure layer. It can help add extra control-plane nodes, but a production HA design still needs a stable endpoint in front of the API servers.

Before running kubeadm on a fresh host, treat prerequisites as part of the bootstrap plan rather than as a footnote. A missing container runtime socket, enabled swap, duplicate host identity, or blocked API server port causes failures that look like "Kubernetes is broken" when the real problem is the node preparation contract.

**Pause and predict:** if kubelet is installed but the container runtime is stopped, which bootstrap step can still complete, and which must fail when kubelet tries to start static pod containers?

<details>
<summary>Check your prediction</summary>

The preflight phase can render local certificates, kubeconfig files, and static pod manifests onto the host filesystem. However, control plane bootstrap stalls completely when kubelet cannot communicate with the container runtime endpoint to create the underlying static pod sandboxes.

</details>

Verifying node preparation and runtime socket availability before running bootstrap commands prevents diagnosing control plane failures that stem entirely from missing underlying host services.

```bash
# Required on ALL nodes:
# 1. Container runtime (containerd)
# 2. kubelet
# 3. kubeadm
# 4. kubectl (at least on control plane)
# 5. Swap disabled
# 6. Required ports open
# 7. Unique hostname, MAC, product_uuid
```

The kubeadm phase model is useful when a failure lands in the middle of initialization. `kubeadm init` is not one opaque action; it is a sequence of phases that can be inspected, skipped, or rerun in controlled ways by experienced operators. For CKA work you rarely need custom phase execution, but knowing the phases exist helps you read error output. A failure during certificate generation, kubeconfig generation, static pod rendering, or add-on installation has a different repair path than a failure during host preflight checks.

You can see this design in the command output as kubeadm reports each major step. That output is evidence, so keep it when a lab or real cluster fails. If the preflight phase complains about swap, fix swap. If static pod manifest generation succeeds but the API server never becomes reachable, move down the stack to kubelet and the runtime. The discipline is similar to reading a compiler error: the first meaningful failure usually gives you a better lead than the cascade of later symptoms.

On the CKA exam, kubeadm questions are usually less about building a production cluster from an empty VM and more about recognizing where kubeadm placed the moving parts. Still, the bootstrap model pays off outside the exam as well. If you know that certificates live under `/etc/kubernetes/pki`, that control-plane pod manifests live under `/etc/kubernetes/manifests`, and that the kubelet is the local supervisor, you can diagnose failures even when the cluster API is temporarily unreachable.

---

## Initialize the Control Plane and Install Networking

The `kubeadm init` command starts the control plane, but the flags you choose encode assumptions that will keep affecting the cluster. A pod network CIDR must match the CNI plugin you plan to install. An API server advertise address must be reachable by the nodes that will join. A Kubernetes version pin controls the control-plane image versions and should line up with the packages you installed on the host. These are not decorative flags; they are the first durable decisions in the cluster.

```bash
# Initialize control plane
sudo kubeadm init

# With specific pod network CIDR (required by some CNIs)
sudo kubeadm init --pod-network-cidr=10.244.0.0/16

# With specific API server address (for HA or custom networking)
sudo kubeadm init --apiserver-advertise-address=192.168.1.10

# With specific Kubernetes version
sudo kubeadm init --kubernetes-version=v1.35.0
```

The simplest command is useful in a lab, but real troubleshooting often begins with the more explicit variants. If a node joins but pods cannot communicate, the pod CIDR and CNI configuration are early suspects. If a worker receives a join command containing an address it cannot route to, the advertise address or control-plane endpoint choice is suspect. If packages and control-plane images are from different minor versions, version-skew rules matter before you assume the network is at fault.

For repeatable clusters, a kubeadm configuration file is safer than a long command line copied from a notes page. The file records cluster settings such as the Kubernetes version, pod subnet, service subnet, image repository, API server endpoint, and certificate subject alternative names in one reviewable artifact. That matters in teams because another operator can inspect the intended bootstrap values before the command runs. It also matters during rebuilds because the second control plane should not be initialized from someone's memory of the first one.

```bash
# Generate a starting point for a reviewed kubeadm configuration
kubeadm config print init-defaults
```

```yaml
apiVersion: kubeadm.k8s.io/v1beta4
kind: ClusterConfiguration
kubernetesVersion: v1.35.0
controlPlaneEndpoint: "192.168.1.10:6443"
networking:
  podSubnet: 10.244.0.0/16
```

When you use a configuration file, the command becomes simpler and the review becomes clearer. You can compare the chosen pod subnet to the CNI documentation, confirm the control-plane endpoint before workers join, and keep the file in an internal runbook without storing bootstrap tokens. The file does not eliminate the need to prepare hosts, but it reduces the chance that a critical bootstrap choice is hidden in a shell history entry.

```bash
# Initialize from a reviewed configuration file
sudo kubeadm init --config kubeadm-config.yaml
```

After initialization, kubeadm writes an admin kubeconfig, but it does not copy that file into every user's home directory. This is why a freshly initialized cluster can exist while `kubectl get nodes` fails for a normal shell user. The API server may be running, but `kubectl` still needs credentials and cluster connection data. Before running this, what output do you expect from `kubectl get nodes` before the kubeconfig copy, and what changes after `$HOME/.kube/config` points at `admin.conf`?

```bash
# For regular user (recommended)
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# For root user
export KUBECONFIG=/etc/kubernetes/admin.conf
```

The next step is CNI installation. Without a CNI plugin, kubelet can run the static control-plane pods, but ordinary pods cannot receive routable pod IPs, and CoreDNS commonly remains pending or not ready. That distinction is important: a kubeadm cluster can look partially alive before networking is installed. The API server may answer requests, yet workloads remain unable to communicate because the networking layer has not fulfilled its part of the cluster contract.

Before running any CNI install command, choose exactly one CNI and verify the current vendor documentation first. The Kubernetes version, kernel prerequisites, kube-proxy mode, pod CIDR, and installation method can all change across plugin releases, so stale one-line manifests are a poor teaching pattern for a Kubernetes 1.35 cluster. Use the commands from the current docs for the plugin you actually chose, and record the version or release channel in your lab notes so later troubleshooting has a factual starting point.

```bash
# Without CNI, pods won't get IPs and CoreDNS won't start

# Calico: read current Kubernetes support and install steps first.
# https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements
# https://docs.tigera.io/calico/latest/getting-started/kubernetes/quickstart
#
# Flannel: use the current release or Helm path from the upstream project.
# https://github.com/flannel-io/flannel
#
# Cilium: install the Cilium CLI first, then follow the current install docs.
# https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/
```

Those CNI pointers are lab-oriented guardrails, not a recommendation to copy a command without reading the chosen vendor's current installation guide. The protected lesson is the sequence: initialize the control plane, configure `kubectl`, install one CNI that matches the pod network choice, and then verify system pods. Mixing multiple CNIs because "more networking should help" creates conflicting agents that fight over pod networking and makes diagnosis harder.

```bash
# Check nodes
kubectl get nodes
# NAME           STATUS   ROLES           AGE   VERSION
# control-plane  Ready    control-plane   5m    v1.35.0

# Check system pods
kubectl get pods -n kube-system
# Should see: coredns, etcd, kube-apiserver, kube-controller-manager,
#             kube-proxy, kube-scheduler, CNI pods
```

Verification should be interpreted rather than treated as a pass-or-fail ritual. A single control-plane node can report `Ready` while CoreDNS is still starting, and a newly installed CNI may need a short window to create its DaemonSet pods. The pattern you want is convergence: the node becomes ready, kube-system pods stop crash-looping, CoreDNS gains running replicas, and the CNI pods land on the nodes that need pod networking. If the cluster stalls, map the symptom back to the bootstrap sequence instead of rerunning `kubeadm init` blindly.

A useful worked example is a control-plane host where `kubeadm init --pod-network-cidr=10.244.0.0/16` succeeds, `kubectl get nodes` works after copying the kubeconfig, but CoreDNS remains pending. The next command is not `kubeadm reset`; it is `kubectl get pods -n kube-system -o wide` to see whether a CNI DaemonSet exists and where pods are scheduled. If no CNI pods exist, install the intended CNI. If CNI pods exist but are crash-looping, inspect their logs and verify that the pod CIDR and kernel/network prerequisites match the plugin.

kubeadm also stores cluster configuration in the cluster after initialization, which gives you another way to inspect what was intended. The `kubeadm-config` ConfigMap in `kube-system` records settings that future kubeadm operations, especially upgrades, can consult. This is not a replacement for your runbook, because a broken API server can make the ConfigMap unreachable, but it is valuable when the cluster is healthy enough for API inspection. If the stored configuration and your assumptions disagree, trust the evidence and update the runbook.

```bash
# Inspect kubeadm's stored cluster configuration
kubectl -n kube-system get configmap kubeadm-config -o yaml
```

---

## Join Nodes and Protect Bootstrap Trust

Worker joins are easy to copy and easy to misunderstand. The join command contains a bootstrap token that authenticates the new node for its initial registration, and it contains a CA certificate hash that lets the node verify it is talking to the intended control plane. The token answers "am I allowed to start joining?" while the CA hash answers "am I joining the right cluster?" Both pieces matter because node bootstrap happens before the node has its long-lived kubelet client certificate.

```bash
# Example output from kubeadm init
kubeadm join 192.168.1.10:6443 --token abcdef.0123456789abcdef \
  --discovery-token-ca-cert-hash sha256:abc123...
```

Run the join command on a worker node after the runtime, kubelet, and kubeadm are installed there. The worker needs network reachability to the API server endpoint, matching time sufficiently for certificate validation, a working container runtime, and a token that has not expired. A failed join is often a local node preparation problem, not a control-plane problem, so the first logs to read are usually on the joining worker.

```bash
# On worker node (as root)
sudo kubeadm join 192.168.1.10:6443 \
  --token abcdef.0123456789abcdef \
  --discovery-token-ca-cert-hash sha256:abc123...
```

Bootstrap tokens expire by default, and that is a feature rather than an inconvenience. A join command pasted into a ticket, chat thread, or shell history should not authorize new nodes forever. The operational habit is to generate a fresh command when needed, use it during a controlled maintenance window, and delete or allow old tokens to expire. Which approach would you choose here and why: a long-lived token for convenience, or short-lived tokens generated as part of each node-addition runbook?

```bash
# On control plane - create new token
kubeadm token create --print-join-command

# Or manually:
# 1. Create token
kubeadm token create

# 2. Get CA cert hash
openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | \
  openssl rsa -pubin -outform der 2>/dev/null | \
  openssl dgst -sha256 -hex | sed 's/^.* //'

# 3. Construct join command
kubeadm join <control-plane-ip>:6443 --token <new-token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

The manual flow is worth learning even if `--print-join-command` is faster, because it exposes the trust model. The hash is derived from the cluster CA public key, not from the short-lived token. If the token expires, you create a new token; if the CA hash is wrong, the node should refuse to trust the endpoint. When a worker cannot join, reading the exact error matters because "token invalid", "x509", "connection refused", and "timed out" point to different layers.

```bash
# List existing tokens
kubeadm token list

# Delete a token
kubeadm token delete <token>

# Create token with custom TTL
kubeadm token create --ttl 2h
```

Treat token management as part of cluster hygiene. In a tiny lab cluster, expired tokens are mostly a speed bump. In a shared environment, forgotten bootstrap tokens become confusing operational state and may widen the window during which an unintended host can attempt to register. The fix is not elaborate: list tokens before a join, create a token with a sensible TTL, document which node used it, and remove tokens that are no longer needed.

Exercise scenario: a worker was provisioned from the same image as an existing node, but `kubeadm join` fails with an error about the node already existing. That is a signal to check host identity and old kubelet state before blaming the token. A cloned VM can carry stale `/var/lib/kubelet` data, duplicate machine identity, or a hostname that conflicts with an existing node object. Reset and clean the node, fix the hostname, and rerun join with a fresh command rather than forcing the API server to accept ambiguous identity.

---

## Static Pods, Files, Certificates, and etcd

Static pods are the key to kubeadm control-plane diagnosis. A normal Deployment is reconciled by controllers through the API server; a static pod is read directly from a file by kubelet. kubeadm uses static pods for `kube-apiserver`, `kube-controller-manager`, `kube-scheduler`, and local etcd because those components must exist before higher-level controllers can manage anything. This is the bootstrap loop: kubelet starts the API server, and only then can the API server expose mirror pods that make the static pods visible through `kubectl`.

```bash
# Static pod manifests location
ls /etc/kubernetes/manifests/
# etcd.yaml
# kube-apiserver.yaml
# kube-controller-manager.yaml
# kube-scheduler.yaml
```

The API server lists control-plane pods so operators can inspect them with ordinary `kubectl`, but listing is not the same as owning the restart path. Treat that distinction as a troubleshooting constraint rather than trivia, because the wrong next command wastes minutes during an outage.

**Pause and predict:** if you run `kubectl delete pod kube-apiserver-controlplane -n kube-system`, what changes (and what does not) at the container-runtime level, and what file decides?

<details>
<summary>Check your prediction</summary>

The mirror Pod object in the API server vanishes and is promptly recreated by kubelet, but the underlying container process running inside the container runtime does not restart. The host manifest file `/etc/kubernetes/manifests/kube-apiserver.yaml` remains the durable source of truth governing the running control plane process.

</details>

The next command after a control-plane symptom has to match the layer that actually owns restart, otherwise the outage clock keeps running while kubectl reports success.

```text
┌────────────────────────────────────────────────────────────────┐
│                    Static Pod Lifecycle                         │
│                                                                 │
│   /etc/kubernetes/manifests/                                   │
│           │                                                     │
│           │ kubelet watches this directory                     │
│           ▼                                                     │
│   ┌─────────────┐                                              │
│   │   kubelet   │                                              │
│   └──────┬──────┘                                              │
│          │                                                      │
│          │ For each YAML file:                                 │
│          │ 1. Start container                                  │
│          │ 2. Keep it running                                  │
│          │ 3. Restart if it crashes                            │
│          │ 4. Create mirror pod in API server                  │
│          ▼                                                      │
│   ┌─────────────────────────────────────────┐                  │
│   │ Control Plane Containers                 │                  │
│   │ • kube-apiserver                        │                  │
│   │ • kube-controller-manager               │                  │
│   │ • kube-scheduler                        │                  │
│   │ • etcd                                  │                  │
│   └─────────────────────────────────────────┘                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Editing static pod manifests is powerful and risky because kubelet applies the result automatically. A valid edit restarts the component with the new flags; an invalid edit can stop the API server, scheduler, controller manager, or etcd. The safest habit is to make a timestamped copy outside `/etc/kubernetes/manifests/`, change one thing, keep a root shell open on the control-plane node, and use local logs if the API disappears. Do not leave `kube-apiserver.yaml.bak` or any other backup file inside the watched manifest directory, because kubelet treats non-dot files there as candidate static pod manifests rather than harmless notes. For exam practice, the key distinction is simple: `kubectl` can show a static pod, but the manifest file controls it.

```bash
# Make a safe backup OUTSIDE the watched manifest directory
sudo mkdir -p /etc/kubernetes/backup
sudo cp /etc/kubernetes/manifests/kube-apiserver.yaml \
  /etc/kubernetes/backup/kube-apiserver.yaml.$(date -u +%Y%m%dT%H%M%SZ)

# View static pod manifests
sudo cat /etc/kubernetes/manifests/kube-apiserver.yaml

# Modify a static pod (edit the manifest)
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml
# kubelet automatically restarts the pod

# "Delete" a static pod (remove the manifest)
sudo mv /etc/kubernetes/manifests/kube-scheduler.yaml /tmp/
# kubelet stops the pod

# Restore it
sudo mv /tmp/kube-scheduler.yaml /etc/kubernetes/manifests/
# kubelet starts the pod again
```

The directory layout is the map you use when API-level tools stop working. `/etc/kubernetes/admin.conf` is the administrative kubeconfig. `/etc/kubernetes/manifests` holds static pod definitions. `/etc/kubernetes/pki` holds the cluster CA, API server certificates, service account signing keys, front-proxy material, and etcd certificates. When you know these paths, "control plane down" stops being a vague panic and becomes a file-and-process investigation.

```text
/etc/kubernetes/
├── admin.conf               # kubectl config for admin
├── controller-manager.conf  # kubeconfig for controller-manager
├── kubelet.conf             # kubeconfig for kubelet
├── scheduler.conf           # kubeconfig for scheduler
├── manifests/               # Static pod definitions
│   ├── etcd.yaml
│   ├── kube-apiserver.yaml
│   ├── kube-controller-manager.yaml
│   └── kube-scheduler.yaml
└── pki/                     # Certificates
    ├── ca.crt               # Cluster CA
    ├── ca.key
    ├── apiserver.crt        # API server cert
    ├── apiserver.key
    ├── apiserver-kubelet-client.crt
    ├── front-proxy-ca.crt
    ├── sa.key               # ServiceAccount signing key
    ├── sa.pub
    └── etcd/                # etcd certificates
        ├── ca.crt
        └── ...
```

The kubeconfig files in this directory are also worth naming carefully. `admin.conf` is for cluster administration, while `kubelet.conf`, `controller-manager.conf`, and `scheduler.conf` are client credentials for components that talk to the API server. If an administrator copies the wrong file into `$HOME/.kube/config`, the resulting authorization behavior may be confusing. If a component kubeconfig is stale or unreadable, the component may start but fail to authenticate to the API server, so certificate and kubeconfig diagnosis often happen together.

File permissions are part of the security model, not just a Linux housekeeping detail. The CA private key, service account signing key, and etcd private keys can authorize or sign highly sensitive cluster behavior. A good backup captures what is needed for recovery, but a careless copy into a shared directory creates a different incident. When you inspect these files, use the minimum necessary access, keep copies protected, and remove temporary diagnostic copies after the maintenance window.

Certificate management is where kubeadm's convenience and your responsibility meet. kubeadm can check certificate expiration and renew certificates it manages, but renewed files do not matter until the affected components reload them. Static pod components usually reload by being restarted, which can be done by moving manifests out and back, letting kubelet recreate containers, or by restarting kubelet in a planned maintenance window. You should also know which kubeconfig files need to be recopied after admin credentials are renewed.

```bash
# Cluster CA
/etc/kubernetes/pki/ca.crt
/etc/kubernetes/pki/ca.key

# API Server
/etc/kubernetes/pki/apiserver.crt
/etc/kubernetes/pki/apiserver.key

# etcd CA (separate CA)
/etc/kubernetes/pki/etcd/ca.crt
/etc/kubernetes/pki/etcd/ca.key

# Check certificate expiration
kubeadm certs check-expiration
```

etcd deserves separate attention because it stores cluster state. Backing up etcd before disruptive control-plane maintenance is not optional in a serious environment, even when the exam only asks you to demonstrate the mechanics. A snapshot command must use the etcd endpoint and the correct client certificates, and a restore must be planned carefully because it replaces the state the API server will read. A backup you have never validated is closer to a hope than a recovery plan.

```bash
# Save an etcd snapshot on a stacked-control-plane kubeadm node
sudo ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  snapshot save /var/backups/etcd-snapshot.db

# Inspect the snapshot before trusting it
sudo ETCDCTL_API=3 etcdctl snapshot status /var/backups/etcd-snapshot.db --write-out=table
```

Restoring etcd is a disruptive recovery action, not a casual maintenance command. In a single-node stacked etcd lab, the restore pattern is to stop the control plane, restore the snapshot to a new data directory with `etcdutl`, update the etcd static pod manifest to point at that directory if needed, and then let kubelet restart etcd and the API server. The older `etcdctl snapshot restore` form is legacy guidance; current Kubernetes and etcd recovery docs use `etcdutl` for restore while `etcdctl` remains common for saving live snapshots. In a multi-member etcd topology, the procedure must respect quorum and member identity, so do not generalize a single-node lab recipe into a production runbook.

```bash
# Example lab restore target; plan production restores from the official etcd guidance
sudo etcdutl snapshot restore /var/backups/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-from-backup
```

Upgrades fit into the same risk model. kubeadm can plan and apply a control-plane upgrade, but you still drain nodes, respect version skew, upgrade kubelet and kubectl packages, and verify each step before moving on. The safe order is control plane first, then workers one at a time, with a rollback and backup plan that exists before you touch the first component. For CKA purposes, know the shape of the workflow and the commands you use to inspect the plan.

```bash
# Step 1: upgrade the kubeadm binary itself to the target version FIRST.
# `kubeadm upgrade apply` validates that the running kubeadm matches the
# target version, so skipping this step fails immediately. Exact package
# string varies by distro and repo (apt example shown).
sudo apt-get update && sudo apt-get install -y --allow-change-held-packages kubeadm=1.35.1-1.1

# Step 2: control-plane planning step (read-only, safe to re-run)
sudo kubeadm upgrade plan

# Step 3: control-plane apply for a patch release in the same minor line
sudo kubeadm upgrade apply v1.35.1

# Step 4: upgrade kubelet and kubectl packages, then restart kubelet
sudo apt-get install -y --allow-change-held-packages kubelet=1.35.1-1.1 kubectl=1.35.1-1.1
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

The important connection is that certificates, etcd snapshots, static pod manifests, and upgrades are not separate topics. They are all maintenance operations around the same set of kubeadm-created assets. If you can read the file layout and explain which local process consumes each file, you can reason about renewal, restore, restart, and upgrade behavior without relying on a memorized script.

---

## Node Maintenance, Reset, and Recovery

Node maintenance starts with scheduling intent. Cordon says "do not place new pods here"; drain says "evict the pods that can safely move away." That difference matters because a cordoned node can still be running existing workloads, and a reboot can still interrupt them. Drain uses the eviction API for managed pods, respects many availability controls, and leaves DaemonSet pods alone unless you use additional flags. The right command depends on whether you are preventing future placement or preparing for disruptive work.

```bash
# List nodes
kubectl get nodes

# Detailed info
kubectl get nodes -o wide

# Node details
kubectl describe node <node-name>
```

Good node diagnosis starts by separating desired scheduling state from health state. A node can be `Ready,SchedulingDisabled`, which means kubelet is healthy but the scheduler is not allowed to place new pods there. A node can be `NotReady`, which means the control plane has not received healthy status from kubelet or related components. Those states imply different next moves.

**Pause and predict:** if you only cordon a node before kernel maintenance, what risk remains that drain would have handled?

<details>
<summary>Check your prediction</summary>

Existing workloads continue running on the node because cordon only blocks new pod scheduling. When the host reboots for kernel updates, those unevicted pods terminate abruptly rather than being gracefully evicted and rescheduled onto healthy nodes.

</details>

Enforcing eviction workflows before initiating disruptive node maintenance ensures application availability contracts and graceful termination budgets are fully respected across the cluster.

```bash
# Drain node (evict pods, mark unschedulable)
kubectl drain <node-name> --ignore-daemonsets

# If there are pods with local storage:
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Force (for pods without controllers):
kubectl drain <node-name> --ignore-daemonsets --force
```

Drain flags should make you pause because each one encodes a tradeoff. `--ignore-daemonsets` is normal because DaemonSet pods are expected to live on the node and cannot be drained in the same way as Deployment pods. `--delete-emptydir-data` acknowledges that data in `emptyDir` volumes is node-local and will be removed with the pod. `--force` is a stronger statement: you are willing to remove pods that do not have a controller to recreate them. Use it deliberately, not as muscle memory.

```bash
# Mark node unschedulable (no new pods)
kubectl cordon <node-name>

# Mark node schedulable again
kubectl uncordon <node-name>

# Check node status
kubectl get nodes
# NAME    STATUS                     ROLES    AGE   VERSION
# node1   Ready                      worker   10d   v1.35.0
# node2   Ready,SchedulingDisabled   worker   10d   v1.35.0  # cordoned
```

Recovery after maintenance is not finished when the node reboots. You verify that kubelet is running, the node returns to `Ready`, critical DaemonSets are healthy, and the node is uncordoned if it should receive workloads. A common operational miss is to perform the maintenance correctly and then leave the node cordoned for days. The cluster keeps working, but capacity is lower, autoscaling signals become confusing, and future drains have less room to move pods.

```bash
# 1. Drain the node first
kubectl drain <node-name> --ignore-daemonsets --force

# 2. Delete from cluster
kubectl delete node <node-name>

# 3. On the node itself, reset kubeadm
sudo kubeadm reset

# 4. Optional post-reset cleanup after preserving evidence
sudo rm -rf /etc/cni/net.d/
rm -rf $HOME/.kube
# Clean kube-proxy rules with the documented kube-proxy --cleanup method.
```

Removing a node is more final than draining it. Deleting the Node object tells the cluster to stop tracking that host, while `kubeadm reset` performs best-effort local cleanup on the host. The cleanup commands are intentionally destructive, so they belong in a lab, a decommissioning runbook, or a controlled rebuild, not in a casual troubleshooting loop. If you only need to restart kubelet or fix a CNI config file, resetting the node throws away useful evidence and creates extra work.

```bash
# On the node to reset
sudo kubeadm reset

# kubeadm reset is best-effort LOCAL cleanup:
# 1. Removes kubeadm-managed local files and certificates.
# 2. Removes this node's local stacked etcd member data when applicable.
# 3. Does not remove generic cluster state from a surviving etcd cluster.
# 4. Does not clean CNI config, $HOME/.kube, or kube-proxy rules.

# Additional cleanup kubeadm reset does NOT do automatically:
sudo rm -rf /etc/cni/net.d/
rm -rf $HOME/.kube

# For kube-proxy network rules, follow the kubeadm reset reference:
# run kube-proxy --cleanup from the same kube-proxy image version/runtime
# your cluster used. Do not assume an iptables flush is complete, because
# kube-proxy may have programmed iptables, IPVS, or nftables state.
```

Reset also has an exam trap: it does not magically erase every possible networking, credential, or runtime artifact in every environment. CNI configuration files, `$HOME/.kube`, kube-proxy traffic rules, IPVS or nftables state, container images, and runtime data may need separate cleanup depending on how the node was prepared. That is why the kubeadm reset output and reference page tell you what it did and what you may still need to clean. Read the output instead of assuming reset means "factory new."

---

## Troubleshooting Without a Working API Server

The fastest kubeadm troubleshooting habit is to choose the tool that still works at the failed layer. If the API server is healthy, `kubectl` is convenient and expressive. If the API server is down, `kubectl` may hang, but kubelet logs, systemd status, container runtime tools, and static pod manifests are still available on the node. If kubelet itself is stopped, even static pod recovery depends on fixing the local service first. This layered approach prevents the common mistake of repeatedly running an API client against a dead API.

```bash
# Check kubelet status
systemctl status kubelet

# Check kubelet logs
journalctl -u kubelet -f

# Common issues:
# - Swap not disabled
# - Container runtime not running
# - Wrong container runtime socket
```

When you collect evidence, capture both the command and the node where you ran it. A kubelet log from a worker that cannot join tells a different story than a kubelet log from the control-plane node that cannot start the API server. Likewise, a `crictl ps` result from the wrong host can send you chasing missing containers that were never supposed to run there. Labeling evidence by node name, role, and time keeps a small incident from becoming a pile of disconnected snippets.

When kubelet is not starting, the investigation is local and mechanical. Check whether the service is enabled and running, whether its configuration file references a valid container runtime endpoint, and whether the runtime itself can start containers. Kubelet log messages usually name the missing socket, invalid flag, cgroup mismatch, or certificate issue. Do not start by deleting cluster objects; the node agent must be healthy before the control plane can receive useful status.

```bash
# Check container runtime
crictl ps

# Check static pod containers
crictl logs <container-id>

# Look for API server errors
sudo cat /var/log/pods/kube-system_kube-apiserver-*/kube-apiserver/*.log
```

When the control plane is not starting, the local container runtime becomes your window into the failure. `crictl ps` tells you whether static pod containers exist, whether they are restarting, and which container ID to inspect. Container logs can reveal an invalid API server flag, an unreadable certificate, an etcd connection failure, or a YAML syntax error in a manifest. If the API server is unavailable, the fix often happens in `/etc/kubernetes/manifests` rather than through `kubectl`.

```bash
# On the node, check logs
journalctl -u kubelet | tail -50

# Common issues:
# - Token expired
# - Wrong CA hash
# - Network connectivity to control plane
# - Firewall blocking port 6443
```

Node join failures require you to decide whether the worker cannot reach the API server, cannot trust it, or cannot complete local bootstrap. A timeout points toward routing, firewall, endpoint, or API server availability. A CA hash or x509 error points toward trust material. A kubelet or runtime error points back to node preparation. Those categories are more useful than memorizing one "node not joining" fix because the same symptom at the dashboard level can come from several different layers.

```bash
# Check expiration
kubeadm certs check-expiration

# Renew all certificates
kubeadm certs renew all

# Restart control plane components
# (just move manifests and wait)
```

Certificate failures are especially easy to misread because they often surface as generic connection errors. The renewal command writes new certificate files, but running it is not the same thing as proving the control plane has reloaded them. Check expiration before and after, restart or cycle the relevant static pods, and verify client kubeconfigs where necessary. If etcd certificates are involved, be careful to distinguish API server serving certificates from etcd peer and client certificates because they are consumed by different processes.

The exam-relevant command set is short enough to practice until it becomes fluent, but fluency should include context. `kubeadm token create --print-join-command` is for bootstrap trust, not for fixing a broken CNI. `kubectl drain` is for moving workloads before maintenance, not for removing the node's local kubeadm state. `kubeadm reset` is for teardown or rebuild, not for every kubelet warning. Use the command that matches the failed contract.

```bash
# Initialize cluster
kubeadm init --pod-network-cidr=10.244.0.0/16

# Get join command
kubeadm token create --print-join-command

# Join worker
kubeadm join <control-plane>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>

# Check certificates
kubeadm certs check-expiration

# Drain node for maintenance
kubectl drain <node> --ignore-daemonsets

# Make node schedulable again
kubectl uncordon <node>

# Reset node
kubeadm reset
```

Worked example: an administrator edits `/etc/kubernetes/manifests/kube-apiserver.yaml` to add an admission flag but leaves a YAML indentation error. `kubectl get nodes` now returns connection refused, which is expected because the API server container cannot start. The recovery path is to SSH to the control-plane node, inspect `journalctl -u kubelet`, inspect the failed API server container logs through `crictl`, fix the manifest with a local editor, and wait for kubelet to recreate the static pod. The lesson is concrete: when the API server is the broken component, local node tools replace API tools until the static pod is healthy again.

Another useful scenario is a worker that reports `NotReady` after a reboot even though the control plane is healthy. Start with `kubectl describe node` if the API is reachable, then move to the worker and inspect kubelet, the container runtime, CNI configuration, and recent logs. If kubelet cannot authenticate, compare `/etc/kubernetes/kubelet.conf` and certificates; if pods cannot create sandboxes, inspect the CNI files and runtime errors. The node object gives you the symptom, but the worker's local evidence usually gives you the cause.

---

## Patterns & Anti-Patterns

The patterns below are not generic "best practices"; they are decision habits that keep kubeadm operations reversible and diagnosable. A kubeadm cluster is transparent enough that you can inspect nearly every important artifact, but that transparency only helps if you make one change at a time and preserve evidence before destructive actions. In small labs, skipping that discipline costs minutes. In a shared cluster, it can turn an ordinary maintenance task into a recovery exercise.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Bootstrap with explicit inputs | Use when initializing or rebuilding a control plane | Pod CIDR, advertise address, and version pins make later symptoms easier to explain | Store the chosen values in a runbook or kubeadm config file for repeatability |
| Diagnose from the surviving layer | Use when `kubectl` hangs or the API server is unavailable | kubelet, systemd, crictl, and manifest files remain available locally | Train operators to SSH to the right node and collect local logs before resetting |
| Protect state before disruption | Use before upgrades, certificate rotations, or static pod edits | etcd snapshots and copied manifests provide rollback evidence | Automate backup validation and keep restore procedures separate for single-node and HA etcd |
| Drain before host maintenance | Use before rebooting, patching, or removing a node | Workloads move through the Kubernetes eviction path instead of dying abruptly | Capacity and PodDisruptionBudgets determine whether drain can complete quickly |

The matching anti-patterns are tempting because they appear faster in the moment. Rerunning `kubeadm init` feels decisive, forcing a drain seems to clear a blocker, and deleting a static pod through `kubectl` looks natural because the pod is visible through the API. Each shortcut ignores ownership. kubeadm owns bootstrap artifacts, kubelet owns static pod execution, the scheduler owns new placement, controllers own replacement pods, and etcd owns cluster state.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Rerunning `kubeadm init` on a half-working control plane | You risk overwriting evidence and creating conflicting local state | Read kubelet logs, static pod logs, and kubeadm output to identify the failed phase |
| Treating `kubectl delete pod` as static pod removal | kubelet recreates the mirror pod because the manifest still exists | Move, edit, or restore the manifest in `/etc/kubernetes/manifests/` |
| Keeping long-lived join tokens for convenience | Old tokens make node admission state harder to reason about | Generate short-lived tokens and delete unused ones after the join window |
| Using `kubeadm reset` as a first troubleshooting step | You remove local state before understanding the failure | Reset only for teardown, rebuild, or a documented rejoin procedure |

The scaling point is that kubeadm does not remove the need for operational design. A single-node lab can tolerate manual commands and brief outages, while a production-like cluster needs external API endpoints, tested backups, planned upgrade waves, and enough spare capacity for drains. The command names stay the same, but the risk surrounding each command changes with cluster size, workload criticality, and recovery requirements.

---

## Decision Framework

Use the framework below when you face a kubeadm cluster symptom and need to choose the next action. The goal is to avoid jumping straight to the most dramatic command. Start by identifying which layer is still trustworthy, then pick the least destructive action that can prove or repair the suspected contract. This is the same mental move you practiced in earlier architecture modules: locate ownership before applying a fix.

```text
Symptom observed
      |
      v
Can kubectl reach the API server?
      |
      +-- yes --> Is this a scheduling or workload-placement issue?
      |              |
      |              +-- yes --> inspect nodes, cordon/drain/uncordon, events
      |              |
      |              +-- no  --> inspect kube-system pods, CNI, certificates, joins
      |
      +-- no  --> Can you SSH to the affected control-plane node?
                     |
                     +-- yes --> inspect kubelet, crictl, static pod manifests, local logs
                     |
                     +-- no  --> fix host/network access before Kubernetes diagnosis
```

| Situation | First Check | Likely Command Family | Avoid Until You Know More |
|-----------|-------------|-----------------------|---------------------------|
| Fresh cluster has `NotReady` node and pending CoreDNS | CNI pods and pod CIDR | `kubectl get pods -n kube-system`, CNI install command | `kubeadm reset` |
| Worker join fails immediately | Token, CA hash, API reachability, kubelet logs | `kubeadm token create --print-join-command`, `journalctl -u kubelet` | Reinitializing the control plane |
| API server unavailable after manifest edit | kubelet and static pod logs | `journalctl`, `crictl logs`, edit manifest | `kubectl delete pod` |
| Planned node reboot | Workload controllers and disruption policy | `kubectl cordon`, `kubectl drain`, `kubectl uncordon` | Power cycling without drain |
| Certificates near expiry | `kubeadm certs check-expiration` output | `kubeadm certs renew`, static pod restart | Assuming renewal reloads every process automatically |
| Disruptive control-plane maintenance | Recent etcd snapshot and restore plan | `etcdctl snapshot save`, `kubeadm upgrade plan` | Upgrading without state protection |

Two rules keep this framework practical. First, do not use a cluster-level command to fix a node-local prerequisite until the node-local evidence says Kubernetes is ready for that command. Second, do not use a destructive local command to fix a cluster-level scheduling condition until you have checked the API view. That separation is what prevents a simple cordon oversight from turning into a reset, and it prevents a dead API server from wasting your time with repeated `kubectl` calls.

---

## Did You Know?

- Bootstrap tokens created by kubeadm expire after 24 hours by default, which is why `kubeadm token create --print-join-command` is a normal operational command rather than a rare recovery trick.
- kubeadm control-plane components run as static pods, so kubelet watches `/etc/kubernetes/manifests/` and can restart the API server container even when the API server cannot answer `kubectl`.
- The default secure Kubernetes API server port is 6443, and a worker that cannot reach that endpoint cannot complete `kubeadm join` no matter how many times you regenerate the token.
- kubeadm-managed certificates can be checked with `kubeadm certs check-expiration`, but renewed certificate files must still be loaded by the relevant control-plane components before clients see the change.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Running init with swap enabled | kubeadm preflight checks reject a host that violates kubelet requirements | Disable swap with `swapoff -a`, remove persistent swap entries from `/etc/fstab`, and rerun preflight checks |
| Forgetting CNI after init | The API server works, so the cluster looks "installed" even though pod networking is missing | Install exactly one intended CNI plugin and verify CNI pods plus CoreDNS in `kube-system` |
| Token expired | The original join command was copied from old init output or stale notes | Run `kubeadm token create --print-join-command` and use the fresh command during the join window |
| Using kubectl delete on static pods | Mirror pods appear in the API, so they look like normal API-managed pods | Edit, move, or restore files in `/etc/kubernetes/manifests/` because kubelet owns static pod lifecycle |
| Not draining before maintenance | Cordon and drain are treated as interchangeable node commands | Cordon to stop new placement, drain to evict movable workloads, then uncordon after maintenance |
| Renewing certificates without restarting components | The command writes files, but running processes may still hold old certificate data | Restart or cycle the affected static pods and verify expiration again after reload |
| Resetting before collecting local evidence | Reset feels like a clean fix when kubelet or join behavior is confusing | Capture kubelet logs, `crictl` output, manifests, and kubeadm errors before using `kubeadm reset` |

---

## Quiz

<details>
<summary>Question 1: Your team initializes a control plane with `kubeadm init`, copies `admin.conf`, and sees the node, but CoreDNS remains pending. What do you check before rerunning kubeadm?</summary>

Check whether a CNI plugin has been installed and whether its configuration matches the pod CIDR used during `kubeadm init`. The API server can be reachable before pod networking is ready, so pending CoreDNS is often a networking bootstrap symptom rather than a failed control-plane install. Inspect `kubectl get pods -n kube-system -o wide`, look for CNI DaemonSet pods, and read their logs if they exist. Rerunning kubeadm would be the wrong first move because it ignores the missing or unhealthy networking layer.

</details>

<details>
<summary>Question 2: A worker join command from yesterday fails, and the error mentions bootstrap token validation. What should you do, and why is the CA hash still part of the command?</summary>

Generate a fresh join command on the control plane with `kubeadm token create --print-join-command`, then run that command on the prepared worker. The token is short-lived authentication material, so an old command can expire even though the cluster is healthy. The CA hash remains necessary because the worker must verify that the API server endpoint belongs to the intended cluster before trusting it. If the new token still fails, separate token errors from network reachability and kubelet preparation errors.

</details>

<details>
<summary>Question 3: You delete `kube-apiserver-controlplane` with `kubectl`, and it comes back almost immediately. What does that tell you about ownership?</summary>

It tells you the visible pod is a mirror of a static pod, not a normal pod owned by a Deployment or ReplicaSet. kubelet is watching `/etc/kubernetes/manifests/kube-apiserver.yaml`, so when you delete the mirror pod through the API, kubelet recreates the mirror pod object — but the underlying container is never restarted, because kubelet has not been instructed to remove the manifest. The static pod process keeps running across the `kubectl delete` operation. To intentionally stop or change that static pod, you must edit or move the manifest on the control-plane node. This is also why local node access matters when the API server is the component you are troubleshooting.

</details>

<details>
<summary>Question 4: During planned kernel maintenance, a junior admin suggests `kubectl cordon` and an immediate reboot. What safer workflow do you implement?</summary>

Cordon the node first to prevent new pods from landing there, then drain it with the appropriate flags so managed pods are evicted before the reboot. After maintenance, verify kubelet health, confirm the node returns to `Ready`, and uncordon it so scheduling can resume. Cordon alone does not move existing pods, so rebooting immediately can interrupt workloads that could have been gracefully rescheduled. The exact drain flags depend on DaemonSets, local `emptyDir` data, and unmanaged pods.

</details>

<details>
<summary>Question 5: You renew kubeadm certificates because the API server certificate is close to expiry, but clients still report the old date. What did you likely miss?</summary>

You likely wrote new certificate files but did not restart or cycle the component that loads them. kubeadm renewal changes files under `/etc/kubernetes/pki`, while static pod processes need to reload those files before clients observe the new certificate. Check expiration with `kubeadm certs check-expiration`, restart or cycle the relevant static pod, and verify with an openssl inspection of the serving certificate. If admin client credentials were renewed, also update the kubeconfig used by the administrator shell.

</details>

<details>
<summary>Question 6: After editing `kube-apiserver.yaml`, every `kubectl` command hangs. Which tools do you use next?</summary>

Switch to local node tools because the API server may be the broken component. SSH to the control-plane node, check `journalctl -u kubelet`, list containers with `crictl ps`, and inspect API server container logs with `crictl logs` or files under `/var/log/pods`. Then fix the manifest directly in `/etc/kubernetes/manifests/` and let kubelet restart the static pod. Repeated `kubectl` retries do not help when the API server cannot start.

</details>

<details>
<summary>Question 7: Before a kubeadm control-plane upgrade, what state protection do you want in place, and how does it change your risk?</summary>

You want a recent etcd snapshot that has been inspected, plus copied static pod manifests and a clear restore plan that matches the cluster topology. The snapshot protects cluster state, while manifest copies help reverse accidental flag or path changes. This does not make an upgrade risk-free, but it changes failure handling from improvisation to a practiced recovery path. You should still run `kubeadm upgrade plan`, respect version skew, and upgrade one node at a time.

</details>

---

## Hands-On Exercise

This exercise is designed for a lab kubeadm cluster with at least one worker node. If you are using kind or minikube, some static pod paths and node maintenance behaviors may differ because the "nodes" are containers or local VM abstractions rather than ordinary Linux hosts. The learning goal is still the same: connect each command to the layer it changes, then verify the result before moving to the next step.

Exercise scenario: you are preparing a kubeadm cluster for routine maintenance and need to prove that you can inspect bootstrap artifacts, generate a join command, protect state, drain a node, and recover scheduling afterward. Do not run destructive reset commands against a cluster you care about unless the lab explicitly gives you disposable nodes. When a task says "on the control plane," run it from a shell on the control-plane host rather than from a random workstation.

### Task 1: View and classify nodes

Run the node inspection commands, then write down which node is the control plane, which node is a worker, and whether any node is already cordoned. The output should let you distinguish health from scheduling state before you perform maintenance.

```bash
kubectl get nodes -o wide
```

```bash
kubectl describe node <node-name> | head -50
```

<details>
<summary>Solution notes</summary>

The first command gives a compact view of roles, versions, internal IPs, and readiness. The second command gives conditions, addresses, capacity, allocatable resources, taints, and recent node events. A node that shows `SchedulingDisabled` is cordoned, while a node that shows `NotReady` has a health or communication problem that should be diagnosed before maintenance.

</details>

### Task 2: Inspect control-plane static pod files

On the control-plane node, inspect the manifest directory and read the beginning of the API server manifest. Do not edit anything yet; the point is to locate the source files that kubelet watches.

```bash
# If you have SSH access to control plane
ls /etc/kubernetes/manifests/
cat /etc/kubernetes/manifests/kube-apiserver.yaml | head -30
```

<details>
<summary>Solution notes</summary>

You should see manifests such as `kube-apiserver.yaml`, `kube-controller-manager.yaml`, `kube-scheduler.yaml`, and often `etcd.yaml` on a stacked control-plane node. If those files are present, kubelet is the local supervisor for those components. If `kubectl` fails later because the API server is down, this directory remains one of your primary recovery locations.

</details>

### Task 3: Practice cordon and uncordon

Cordon a worker node, verify that scheduling is disabled, create a test pod, and check where it lands. Then uncordon the worker and verify that the scheduling state returns to normal.

```bash
# Cordon a worker node
kubectl cordon <worker-node>
kubectl get nodes
# Should show SchedulingDisabled

# Try to schedule a pod
kubectl run test-pod --image=nginx

# Check where it landed
kubectl get pods -o wide
# Won't be on cordoned node

# Uncordon
kubectl uncordon <worker-node>
kubectl get nodes
```

<details>
<summary>Solution notes</summary>

The cordoned node should show `SchedulingDisabled`, and the test pod should land on a different schedulable node if capacity exists. If you only have one worker, the pod may remain pending until the node is uncordoned. That result is still useful because it proves cordon changes scheduler placement without proving anything about kubelet health.

</details>

### Task 4: Practice drain with a disposable deployment

Create a small deployment, observe pod placement, drain a node that hosts one of the replicas, and verify that replacement pods move elsewhere. Use a lab cluster with enough capacity, and do not force production workloads unless your runbook explicitly allows it.

```bash
# Create a deployment first
kubectl create deployment drain-test --image=nginx --replicas=2

# Check pod locations
kubectl get pods -o wide

# Drain a node with pods
kubectl drain <node-with-pods> --ignore-daemonsets

# Check pods moved
kubectl get pods -o wide

# Uncordon the node
kubectl uncordon <node-name>
```

<details>
<summary>Solution notes</summary>

The deployment controller should create replacement pods on schedulable nodes after the drain evicts the originals. If the drain blocks, read the message instead of adding flags blindly; it may be warning you about unmanaged pods or local data. After the test, uncordon the node so it can receive workloads again.

</details>

### Task 5: Check certificates and generate a join command

On the control-plane node, inspect certificate expiration and generate a fresh join command. Do not run the join command unless you have a prepared worker node that should join the cluster.

```bash
# If you have access to control plane
kubeadm certs check-expiration
```

```bash
# On control plane
kubeadm token create --print-join-command
```

<details>
<summary>Solution notes</summary>

The certificate command should show expiration dates for kubeadm-managed certificates, which helps you plan renewal before an outage. The token command should print a complete `kubeadm join` command containing a token and CA hash. Treat that output as temporary bootstrap material and avoid storing it in long-lived shared notes.

</details>

### Task 6: Cleanup lab resources

Remove the disposable deployment and pod created during the exercise. Then recheck nodes to confirm that no lab node was left cordoned by mistake.

```bash
kubectl delete deployment drain-test
kubectl delete pod test-pod
```

<details>
<summary>Solution notes</summary>

Cleanup should remove the workload objects you created and leave nodes in the expected scheduling state. Run `kubectl get nodes` afterward and look for accidental `SchedulingDisabled` status. If you practiced drain, also confirm the drained node is uncordoned before ending the lab.

</details>

### Practice Drills

Use these timed drills after the guided tasks. They preserve the original command practice from this module, but treat the targets as approximate lab pacing rather than a reason to rush through output you do not understand.

#### Drill 1: Node Management Commands (Target: 3 minutes)

```bash
# List nodes with details
kubectl get nodes -o wide

# Get node labels
kubectl get nodes --show-labels

# Describe a node
kubectl describe node <node-name> | head -50

# Check node conditions
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'

# Check node resources
kubectl describe node <node-name> | grep -A10 "Allocated resources"
```

#### Drill 2: Cordon and Uncordon (Target: 5 minutes)

```bash
# Cordon a node (prevent new pods)
kubectl cordon <worker-node>

# Verify
kubectl get nodes  # Shows SchedulingDisabled

# Try to schedule a pod
kubectl run cordon-test --image=nginx
kubectl get pods -o wide  # Won't be on cordoned node

# Uncordon
kubectl uncordon <worker-node>
kubectl get nodes  # Back to Ready

# Cleanup
kubectl delete pod cordon-test
```

#### Drill 3: Drain and Recover (Target: 5 minutes)

```bash
# Create test deployment
kubectl create deployment drain-test --image=nginx --replicas=3

# Wait for pods
kubectl wait --for=condition=available deployment/drain-test --timeout=60s
kubectl get pods -o wide

# Drain a worker node
kubectl drain <worker-node> --ignore-daemonsets --delete-emptydir-data

# Watch pods move to other nodes
kubectl get pods -o wide

# Uncordon the node
kubectl uncordon <worker-node>

# Cleanup
kubectl delete deployment drain-test
```

#### Drill 4: kubeadm Token Management (Target: 3 minutes)

```bash
# List existing tokens
kubeadm token list

# Create a new token
kubeadm token create

# Create token with specific TTL
kubeadm token create --ttl 2h

# Generate full join command
kubeadm token create --print-join-command

# Delete a token
kubeadm token delete <token-id>
```

#### Drill 5: Static Pod Exploration (Target: 5 minutes)

```bash
# Find static pod manifest directory
cat /var/lib/kubelet/config.yaml | grep staticPodPath
# Usually: /etc/kubernetes/manifests

# List static pod manifests
ls -la /etc/kubernetes/manifests/

# View one manifest
cat /etc/kubernetes/manifests/kube-apiserver.yaml | head -30

# Create your own static pod
cat << 'EOF' | sudo tee /etc/kubernetes/manifests/my-static-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-static-pod
  namespace: default
spec:
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 80
EOF

# Wait and verify (will have node name suffix)
sleep 10
kubectl get pods | grep my-static-pod

# Remove static pod
sudo rm /etc/kubernetes/manifests/my-static-pod.yaml
```

#### Drill 6: Certificate Inspection (Target: 5 minutes)

```bash
# Check certificate expiration (on control plane)
kubeadm certs check-expiration

# View certificate details
openssl x509 -in /etc/kubernetes/pki/apiserver.crt -text -noout | head -30

# Check all certificates
ls -la /etc/kubernetes/pki/

# Check CA certificate
openssl x509 -in /etc/kubernetes/pki/ca.crt -text -noout | grep -E "Subject:|Issuer:|Not"
```

#### Drill 7: Troubleshooting - Node NotReady (Target: 5 minutes)

```bash
# Simulate: Stop kubelet on a worker
# (Run on worker node)
sudo systemctl stop kubelet

# On control plane, diagnose
kubectl get nodes  # Shows NotReady
kubectl describe node <worker> | grep -A10 Conditions

# Check what's happening
kubectl get events --field-selector involvedObject.kind=Node

# Fix: Restart kubelet (on worker)
sudo systemctl start kubelet

# Verify recovery
kubectl get nodes -w
```

#### Drill 8: Challenge - Node Maintenance Workflow

Perform a complete maintenance workflow:

1. Cordon the node
2. Drain all workloads
3. Simulate maintenance by waiting 30 seconds
4. Uncordon the node
5. Verify pods can be scheduled again

```bash
# YOUR TASK: Complete this without looking at solution
NODE_NAME=<your-worker-node>
kubectl create deployment maint-test --image=nginx --replicas=2

# Start timer - Target: 3 minutes total
```

<details>
<summary>Solution</summary>

```bash
NODE_NAME=worker-01  # Replace with your node

# 1. Cordon
kubectl cordon $NODE_NAME

# 2. Drain
kubectl drain $NODE_NAME --ignore-daemonsets --delete-emptydir-data

# 3. Verify pods moved
kubectl get pods -o wide

# 4. Simulate maintenance
echo "Performing maintenance..."
sleep 30

# 5. Uncordon
kubectl uncordon $NODE_NAME

# 6. Verify scheduling works
kubectl scale deployment maint-test --replicas=4
kubectl get pods -o wide  # Some should land on $NODE_NAME

# Cleanup
kubectl delete deployment maint-test
```

</details>

**Card A: `kubeadm init` also installs a CNI plugin.** An engineer runs `kubeadm init` on a fresh virtual machine, observes that the control plane components start up, and immediately deploys customer applications. When CoreDNS and workload pods remain indefinitely in the `Pending` or `ContainerCreating` status, they assume the cluster scheduler or API server has encountered an internal software bug. They spend hours investigating control plane logs and restarting system services without realizing the cluster still lacks a networking provider.

<details>
<summary>Check your prediction</summary>

Failure layer: assuming cluster bootstrapping tools provision Pod network plugins automatically. Next action: apply an appropriate CNI plugin manifest such as Calico, Flannel, or Cilium and confirm that node status transitions to Ready.

</details>

**Card B: Deleting the API server Pod in kube-system restarts a stuck control plane.** An operator notices that the API server is responding slowly and attempts to restart it by executing `kubectl delete pod kube-apiserver-controlplane -n kube-system`. When the command completes and a new pod immediately appears in the output, they assume the control plane binary process was fully recycled and reloaded its flags. They conclude the troubleshooting step is finished, unaware that the underlying container runtime never restarted the static pod process.

<details>
<summary>Check your prediction</summary>

Failure layer: mistaking an API server mirror pod deletion for a host-level static pod container restart. Next action: modify or touch the static pod manifest in `/etc/kubernetes/manifests/kube-apiserver.yaml` or restart the local container process directly through the container runtime using `crictl`.

</details>

**Card C: Cordon is enough before kernel maintenance.** A system administrator prepares a worker node for operating system kernel patching by marking it unschedulable with `kubectl cordon`. Because the node status shows `SchedulingDisabled`, they assume the machine is completely safe to reboot without interrupting existing platform traffic. They proceed immediately with the host reboot, accidentally severing active user connections and causing unhandled downtime for unevicted workloads.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing scheduling prevention with workload eviction and graceful shutdown. Next action: execute `kubectl drain <node> --ignore-daemonsets` to gracefully evict running pods to other nodes before powering down or rebooting the host.

</details>

**Card D: `kubeadm reset` is the first fix for a failed join.** A junior engineer encounters a certificate verification error while joining a new worker node to an existing cluster and immediately executes `kubeadm reset -f`. Convinced that clearing the node state is the fastest way to resolve any bootstrapping mismatch, they rerun the command without diagnosing why the bootstrap token failed validation. They repeat this cycle multiple times, destroying local diagnostic logs and missing an expired join token or an incorrect discovery token hash.

<details>
<summary>Check your prediction</summary>

Failure layer: treating destructive state teardown as a substitute for root-cause diagnosis. Next action: inspect join logs, verify the control plane endpoint and firewall rules, check token validity with `kubeadm token list`, and regenerate a fresh join token if necessary before resetting node state.

</details>

**Success Criteria**:

- [ ] Design a kubeadm bootstrap sequence that includes preflight checks, `kubeadm init`, kubeconfig setup, CNI installation, and worker join tokens.
- [ ] Diagnose static pod and kubelet failures with `/etc/kubernetes/manifests/`, `journalctl`, `crictl`, and local control-plane logs.
- [ ] Evaluate certificate and etcd maintenance risk by checking expiry, explaining when and how to save an etcd snapshot, and planning component restarts.
- [ ] Implement safe node maintenance with `kubectl cordon`, `kubectl drain`, `kubectl uncordon`, and a clear cleanup step.
- [ ] Explain when `kubeadm reset` is appropriate and why it should not be the first response to every kubeadm problem.

---

## Sources

- [Creating a cluster with kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/)
- [kubeadm reference](https://kubernetes.io/docs/reference/setup-tools/kubeadm/)
- [kubeadm init reference](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-init/)
- [kubeadm join reference](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-join/)
- [kubeadm reset reference](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-reset/)
- [kubeadm token reference](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-token/)
- [Certificate management with kubeadm](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-certs/)
- [Upgrading kubeadm clusters](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/)
- [Safely drain a node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [Static Pods](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/)
- [Operating etcd clusters for Kubernetes](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/)
- [etcd disaster recovery](https://etcd.io/docs/v3.6/op-guide/recovery/)
- [Calico Kubernetes requirements](https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements)
- [Calico quickstart guide](https://docs.tigera.io/calico/latest/getting-started/kubernetes/quickstart)
- [flannel project documentation](https://github.com/flannel-io/flannel)
- [Cilium quick installation](https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/)

---

## Next Module

Continue to [Part 2: Workloads & Scheduling](/k8s/cka/part2-workloads-scheduling/) to learn how Kubernetes places and runs application workloads after the cluster foundation exists.

### Part 1 Module Index

Quick links for review:

| Module | Topic | Key Skills |
|--------|-------|------------|
| [1.1](../module-1.1-control-plane/) | Control Plane Deep-Dive | Component roles, troubleshooting, static pods |
| [1.2](../module-1.2-extension-interfaces/) | Extension Interfaces | CNI/CSI/CRI, crictl, plugin troubleshooting |
| [1.3](../module-1.3-helm/) | Helm | Install, upgrade, rollback, values |
| [1.4](../module-1.4-kustomize/) | Kustomize | Base/overlay, patches, `kubectl -k` |
| [1.5](../module-1.5-crds-operators/) | CRDs & Operators | Create CRDs, manage custom resources |
| [1.6](../module-1.6-rbac/) | RBAC | Roles, bindings, ServiceAccounts, `can-i` |
| [1.7](../module-1.7-kubeadm/) | kubeadm Basics | Init, join, cordon, drain, tokens |
