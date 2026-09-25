---
revision_pending: false
title: "Module 3.7: CNI & Cluster Networking"
slug: k8s/cka/part3-services-networking/module-3.7-cni
sidebar:
  order: 8
lab:
  id: cka-3.7-cni
  url: https://killercoda.com/kubedojo/scenario/cka-3.7-cni
  duration: "40-50 min"
  difficulty: advanced
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Understanding network infrastructure
>
> **Time to Complete**: 40-50 minutes
>
> **Prerequisites**: Module 1.2 (Extension Interfaces), Module 3.1 (Services)

---

## What You'll Be Able to Do

After this module, you will be able to:
- **Diagnose** pod networking failures by separating CNI installation, IPAM, node routing, DNS, kube-proxy, and NetworkPolicy symptoms.
- **Compare** Calico, Cilium, Flannel, Canal, and cloud-native plugins using policy support, routing model, operations cost, and performance tradeoffs.
- **Trace** same-node, cross-node, and service traffic through namespaces, veth pairs, bridges, overlays, routing tables, kube-proxy, and backend pods.
- **Implement** a repeatable CNI inspection workflow using `kubectl`, node-level CNI files, pod network commands, and service connectivity tests.
- **Evaluate** when to use host networking, host ports, kube-proxy modes, and CIDR changes without breaking cluster-level assumptions.

---

## Why This Module Matters

Hypothetical scenario: a team initializes a Kubernetes 1.35 cluster with `kubeadm`, joins two worker nodes, and immediately deploys a web application plus CoreDNS. The nodes look healthy at first glance, but every new workload stays in `ContainerCreating`, CoreDNS never becomes ready, and service names cannot resolve because the pods never receive network interfaces. Nothing is wrong with the Deployment YAML; the missing layer is the CNI plugin that kubelet expects to call whenever a sandbox needs pod networking.

CNI is easy to underestimate because Kubernetes exposes pods, Services, and NetworkPolicies as API objects, while the actual packet path is mostly implemented by node agents and Linux networking primitives. A Service can exist without useful endpoints, a NetworkPolicy can be accepted by the API server without being enforced by the installed plugin, and a pod can be `Running` while cross-node traffic silently disappears into a blocked overlay port. The CKA-level skill is not memorizing one plugin's command set; it is learning how to place each symptom on the correct part of the stack before you change configuration.

Think of CNI as the city planning department for pod traffic. Kubernetes says every building should have an address and every neighborhood should be reachable, but the CNI design decides whether the streets are simple local roads, tunnels between districts, routed highways, or routes announced with BGP. kube-proxy is a different city service: it watches Service and EndpointSlice changes and programs the rules that send traffic from a stable virtual address to changing backend pods. This module teaches you how those responsibilities meet, where they deliberately do not overlap, and how to inspect the system without guessing.

The practical payoff is confidence under ambiguity. When a workload owner reports that "the network is down," you should be able to ask for one pod name, one node name, one destination, and one failing command, then turn those details into a focused test plan. That is the difference between changing cluster infrastructure reactively and proving which contract has actually failed.

---

## Kubernetes Network Model and CNI Responsibilities

Kubernetes starts from a deceptively strict network model: every pod should be able to communicate with every other pod without NAT, nodes should be able to communicate with pods, and the IP a pod sees for itself should be the same IP other pods use to reach it. This model is the reason application manifests can move between nodes without embedding node addresses or port mappings. It also explains why installing Kubernetes without a working CNI leaves the cluster half-built; kubelet can create containers, but it cannot attach them to the network model the API promises.

The model is intentionally simpler than most physical networks. Kubernetes does not ask application teams to learn node subnets, rack boundaries, security group topology, or tunnel protocols before they deploy a Deployment. Instead, the cluster operator chooses a networking implementation that makes every pod IP appear reachable inside the cluster. That simplicity has a cost: when the implementation breaks, the API still shows high-level objects while the real failure lives in Linux interfaces, route tables, policy engines, or node-to-node reachability.

```
┌────────────────────────────────────────────────────────────────┐
│                Kubernetes Network Requirements                  │
│                                                                 │
│   1. Pod-to-Pod: All pods can communicate with all pods        │
│      without NAT                                                │
│      ┌─────┐      ┌─────┐                                      │
│      │Pod A│◄────►│Pod B│  (direct IP, no NAT)                │
│      └─────┘      └─────┘                                      │
│                                                                 │
│   2. Node-to-Pod: Nodes can communicate with all pods          │
│      without NAT                                                │
│      ┌─────┐      ┌─────┐                                      │
│      │Node │◄────►│ Pod │  (direct access)                    │
│      └─────┘      └─────┘                                      │
│                                                                 │
│   3. Pod IP = Seen IP: The IP a pod sees is the same IP        │
│      others see                                                 │
│      Pod thinks: "My IP is 10.244.1.5"                         │
│      Others see: "Pod's IP is 10.244.1.5"                      │
│                                                                 │
│   4. Pod-to-Service: Pods can reach services by ClusterIP      │
│      ┌─────┐      ┌───────────┐      ┌─────┐                  │
│      │ Pod │─────►│  Service  │─────►│ Pod │                  │
│      └─────┘      └───────────┘      └─────┘                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

CNI provides the pod side of that promise. When kubelet creates a pod sandbox, the kubelet/runtime handoff invokes the configured CNI plugin to attach the sandbox network namespace, allocate an IP address through IPAM, create the pod-facing interface, connect that interface to the node network, and install enough routes or dataplane state for traffic to leave the node when needed. kube-proxy handles the Service virtual IP path, CoreDNS handles name resolution, and the cloud or bare-metal network handles node reachability; confusing those boundaries is the fastest way to debug the wrong layer.

That division of labor is especially important during exams because the symptom often mentions the workload, not the component. "Pod cannot reach service" may mean the pod has no IP, the service has no endpoints, kube-proxy failed to program rules, CoreDNS returned no answer, or a NetworkPolicy blocks the connection. A disciplined responder asks which part of the packet path has been proven healthy. Until direct pod IP traffic works, a service or DNS test is carrying too many assumptions to be useful.

| Responsibility | Component |
|----------------|-----------|
| Pod IP allocation | CNI plugin (IPAM) |
| Pod-to-pod routing | CNI plugin |
| Cross-node networking | CNI plugin |
| Network Policy enforcement | CNI plugin (if supported) |
| Service ClusterIP routing | kube-proxy |

Network namespaces are the practical mechanism that lets each pod believe it owns an `eth0` interface, its own routes, and its own resolver configuration. On a common bridge-based setup, kubelet and the container runtime create a sandbox namespace, the CNI plugin creates a veth pair, one end appears as `eth0` inside the pod, and the other end joins a node-side bridge such as `cni0`. Other CNIs may use eBPF programs, routed interfaces, or cloud-native elastic network interfaces, but the mental model is still useful: pod networking is attached at sandbox creation time, not after the application container decides to listen.

The namespace boundary also explains why commands must be run from the right viewpoint. `ip addr` on the node shows the host namespace and any host-side veth or dataplane interfaces; `kubectl exec <pod> -- ip addr` shows the pod namespace and only the interfaces visible inside that pod. When those views disagree, they are not contradicting each other. They are showing two sides of the same attachment, much like looking at a patch cable from the server rack and from the machine plugged into it.

```
┌────────────────────────────────────────────────────────────────┐
│                   Network Namespaces                            │
│                                                                 │
│   Node                                                          │
│   ┌────────────────────────────────────────────────────────┐   │
│   │  Host Network Namespace                                 │   │
│   │  eth0: 192.168.1.10                                    │   │
│   │                                                         │   │
│   │     ┌─────────────────┐     ┌─────────────────┐        │   │
│   │     │ Pod A           │     │ Pod B           │        │   │
│   │     │ Network NS      │     │ Network NS      │        │   │
│   │     │                 │     │                 │        │   │
│   │     │ eth0:10.244.1.5 │     │ eth0:10.244.1.6 │        │   │
│   │     │                 │     │                 │        │   │
│   │     └────────┬────────┘     └────────┬────────┘        │   │
│   │              │                       │                  │   │
│   │              └───────────┬───────────┘                  │   │
│   │                          │                              │   │
│   │                    ┌─────┴─────┐                        │   │
│   │                    │   Bridge  │                        │   │
│   │                    │  (cni0)   │                        │   │
│   │                    └─────┬─────┘                        │   │
│   │                          │                              │   │
│   └──────────────────────────┼──────────────────────────────┘   │
│                              │                                   │
│                         To other nodes                           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

**Pause and predict:** if kubelet can start a sandbox but the CNI `ADD` call fails before an IP address is assigned, what would `kubectl get pod -o wide` show, and which events and logs would you inspect first?

<details>
<summary>Reveal the prediction and first checks</summary>

The pod should lack a `PodIP` because network attachment did not complete. Check pod events for kubelet messages about the network plugin, then inspect the CNI agent on the same node and its logs. This sequence separates attachment failure from later traffic failures.

</details>

Write down your prediction before expanding the explanation, then compare the observations with the creation sequence to choose a focused first diagnostic command. Record the observed event text so each follow-up check remains grounded in evidence.

The first inspection step is to discover which plugin is installed and whether kubelet can see a CNI configuration file. On many clusters, `/opt/cni/bin/` holds the executable plugins and `/etc/cni/net.d/` holds the ordered configuration or conflist files that the container runtime uses. These are node-level files, so `kubectl` can tell you which DaemonSet should be present, while direct node access tells you what kubelet actually has available.

Treat the node filesystem as evidence, not as an invitation to edit during first response. If the configuration file is missing, that is a strong clue that the plugin was never installed correctly or that node bootstrap failed. If the file exists but pods still fail, the next evidence should come from kubelet events and plugin logs. Editing a conflist without understanding how the plugin operator reconciles it can make your local change disappear or create a node that no longer matches the rest of the cluster.

```bash
# CNI binary location
ls /opt/cni/bin/

# CNI configuration location
ls /etc/cni/net.d/

# Example: View CNI config
cat /etc/cni/net.d/10-calico.conflist
```

```bash
# Check which CNI is installed
ls /etc/cni/net.d/

# Check CNI pods
kubectl get pods -n kube-system | grep -E "calico|flannel|cilium|canal|kindnet"

# Check CNI daemonset
kubectl get daemonset -n kube-system

# View CNI configuration
cat /etc/cni/net.d/*.conf* 2>/dev/null
```

In kind labs, `kindnet` is the expected default CNI, so include it in discovery greps before assuming the CNI is missing.

---

## Plugin Choices, IPAM, and Cross-Node Traffic

Popular CNI plugins share the same broad contract, but they make different tradeoffs about routing, encapsulation, policy, observability, and operational complexity. Flannel is intentionally simple and often uses VXLAN to make a pod network work quickly, but it does not enforce Kubernetes NetworkPolicy by itself. Calico can operate with overlays or routed BGP designs and is widely used when policy enforcement matters. Cilium uses eBPF for networking, policy, observability, and optional kube-proxy replacement, which can be powerful but requires the team to understand a different troubleshooting surface.

Those tradeoffs are not just platform architecture decisions; they shape the commands you use on a bad day. A Flannel VXLAN cluster sends you toward tunnel interfaces, subnet leases, and node-to-node UDP reachability. A Calico cluster may send you toward IP pools, Felix logs, BGP peers, or policy traces. A Cilium cluster may send you toward agent status, endpoint identity, eBPF maps, and Hubble flow data. The CKA does not require mastery of every plugin, but it does expect you to recognize that "CNI" is a family of implementations rather than one behavior.

| Plugin | Network Policy | Performance | Use Case |
|--------|----------------|-------------|----------|
| **Calico** | Yes | High | Enterprise, security-focused |
| **Cilium** | Yes (advanced) | Very high | eBPF, observability |
| **Flannel** | No | Medium | Simple clusters |
| **Canal** | Yes | Medium | Calico policy + Flannel networking |
| **AWS VPC CNI** | Via Calico | High | EKS native |

Choosing a plugin is less about finding the universally best dataplane and more about matching requirements to operational maturity. A bare-metal training cluster with no policy requirements may value Flannel's small surface area. A regulated environment that needs namespace isolation, audit-friendly policy, and explicit egress controls should not choose a plugin that silently ignores NetworkPolicy. A large platform team might choose Cilium because eBPF visibility and kube-proxy replacement reduce other bottlenecks, but that team also accepts a steeper learning curve when reading BPF maps, agent logs, and feature flags.

The easiest mistake is to choose for the installation day instead of the operating year. A plugin that is simple to install can become expensive if every security control has to be added later by a second component. A plugin with many advanced capabilities can become expensive if the on-call team cannot interpret its health output quickly. A good design document should say which features are intentionally enabled, which are deliberately left off, and which symptoms belong to the platform team rather than application owners.

```
┌────────────────────────────────────────────────────────────────┐
│                   CNI Plugin Flow                               │
│                                                                 │
│   1. Pod Created                                               │
│      │                                                          │
│      ▼                                                          │
│   2. Kubelet asks runtime for pod sandbox                      │
│      │                                                          │
│      ▼                                                          │
│   3. Runtime creates pod network namespace                     │
│      │                                                          │
│      ▼                                                          │
│   4. Runtime calls CNI plugin (ADD)                            │
│      │                                                          │
│      ▼                                                          │
│   5. CNI assigns IP address (IPAM)                             │
│      │                                                          │
│      ▼                                                          │
│   6. CNI sets up veth pair and routes                          │
│      │                                                          │
│      ▼                                                          │
│   7. Pod is network-ready                                      │
│                                                                 │
│   Pod Deleted:                                                  │
│      CNI plugin called with DEL → Cleanup                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

IP allocation is the first dataplane decision that shows up in everyday operations. In a kubeadm-style cluster, the cluster pod CIDR might be `10.244.0.0/16`, and each node may receive a smaller pod CIDR such as `10.244.1.0/24`. The exact mechanics depend on the plugin and controller configuration, but the troubleshooting implication is consistent: if a node's pod CIDR is absent, exhausted, or mismatched with the plugin configuration, new pods on that node fail before application code ever starts.

IPAM failures are often misread because the application container may not exist yet. The pod object exists, the scheduler chose a node, and kubelet tried to prepare the sandbox, but the networking step failed before the container started. That is why `kubectl logs` may have nothing useful for the workload. In this state, `kubectl describe pod` events, kubelet logs, and CNI logs are more valuable than application-level diagnostics, because the application never reached the point where it could bind a port or write logs.

```
┌────────────────────────────────────────────────────────────────┐
│                   IP Allocation                                 │
│                                                                 │
│   Cluster CIDR: 10.244.0.0/16                                  │
│                                                                 │
│   Node 1: 10.244.0.0/24        Node 2: 10.244.1.0/24          │
│   ┌──────────────────────┐     ┌──────────────────────┐        │
│   │ Pod: 10.244.0.5      │     │ Pod: 10.244.1.3      │        │
│   │ Pod: 10.244.0.6      │     │ Pod: 10.244.1.4      │        │
│   │ Pod: 10.244.0.7      │     │ Pod: 10.244.1.5      │        │
│   └──────────────────────┘     └──────────────────────┘        │
│                                                                 │
│   Node 3: 10.244.2.0/24                                        │
│   ┌──────────────────────┐                                     │
│   │ Pod: 10.244.2.2      │                                     │
│   │ Pod: 10.244.2.3      │                                     │
│   └──────────────────────┘                                     │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

```bash
# Get pod IP
kubectl get pod <pod> -o wide
kubectl get pod <pod> -o jsonpath='{.status.podIP}'

# Get all pod IPs
kubectl get pods -o custom-columns='NAME:.metadata.name,IP:.status.podIP'

# Check which node a pod is on
kubectl get pod <pod> -o jsonpath='{.spec.nodeName}'

# View pod network namespace (from node)
# First, get container ID
crictl ps | grep <pod-name>
# Then inspect network
crictl inspect <container-id> | jq '.info.runtimeSpec.linux.namespaces'
```

Same-node traffic is the easiest path because the packet usually does not need the physical network. Pod A sends traffic through its `eth0`, the packet crosses the veth pair into the host namespace, and the bridge or dataplane sends it toward Pod B's veth. If this path fails while both pods have IPs on the same node, focus on the node-local dataplane, pod interfaces, route tables, NetworkPolicy, or host firewall behavior before investigating overlays.

This is why test placement matters. If you create two pods without checking which nodes they land on, a passing ping might only prove same-node networking, or a failing ping might involve cross-node routing earlier than you realize. Use `kubectl get pods -o wide` before interpreting the result. For deliberate testing, you can use node selectors, affinity, or repeated scheduling in a lab, but the important habit is to include node placement in the evidence you write down.

```
┌────────────────────────────────────────────────────────────────┐
│                   Same-Node Communication                       │
│                                                                 │
│   Node                                                          │
│   ┌────────────────────────────────────────────────────────┐   │
│   │                                                         │   │
│   │   Pod A                     Pod B                      │   │
│   │   10.244.1.5                10.244.1.6                 │   │
│   │   ┌─────────┐               ┌─────────┐                │   │
│   │   │  eth0   │               │  eth0   │                │   │
│   │   └────┬────┘               └────┬────┘                │   │
│   │        │ veth pair               │ veth pair           │   │
│   │        │                         │                      │   │
│   │   ┌────┴────┐               ┌────┴────┐                │   │
│   │   │ veth-a  │               │ veth-b  │                │   │
│   │   └────┬────┘               └────┬────┘                │   │
│   │        │                         │                      │   │
│   │        └───────────┬─────────────┘                      │   │
│   │                    │                                    │   │
│   │              ┌─────┴─────┐                              │   │
│   │              │  Bridge   │ (cni0 or cbr0)              │   │
│   │              │10.244.1.1 │                              │   │
│   │              └───────────┘                              │   │
│   │                                                         │   │
│   └────────────────────────────────────────────────────────┘   │
│                                                                 │
│   Traffic: Pod A → veth-a → bridge → veth-b → Pod B           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Cross-node traffic adds the node network and the plugin's routing model. VXLAN overlays wrap the pod packet in a node-to-node packet, IP-in-IP does a different encapsulation, BGP designs advertise pod CIDRs to routers or peer nodes, and cloud-native plugins may attach pod addresses directly to cloud networking constructs. The practical test is to compare same-node and different-node behavior: if same-node works but cross-node fails, the packet probably reaches the edge of the local node and then loses the path to the remote pod CIDR.

Each routing model creates a different failure signature. Encapsulation failures often look like healthy pods with no cross-node traffic because the underlay blocks the tunnel protocol. BGP failures often show missing or stale routes for remote pod CIDRs. Cloud-native failures may appear as address exhaustion, missing secondary addresses, or security group rules that allow node health checks but not pod-to-pod traffic. The common thread is that pod IP allocation succeeded, so the next question is whether other nodes know how to return traffic to that address.

```
┌────────────────────────────────────────────────────────────────┐
│                 Cross-Node Communication                        │
│                                                                 │
│   Node 1 (192.168.1.10)          Node 2 (192.168.1.11)        │
│   ┌───────────────────────┐      ┌───────────────────────┐    │
│   │                       │      │                       │    │
│   │  Pod A: 10.244.1.5    │      │  Pod B: 10.244.2.6    │    │
│   │  ┌─────────┐          │      │          ┌─────────┐  │    │
│   │  │  veth   │          │      │          │  veth   │  │    │
│   │  └────┬────┘          │      │          └────┬────┘  │    │
│   │       │               │      │               │       │    │
│   │  ┌────┴────┐          │      │          ┌────┴────┐  │    │
│   │  │ Bridge  │          │      │          │ Bridge  │  │    │
│   │  └────┬────┘          │      │          └────┬────┘  │    │
│   │       │               │      │               │       │    │
│   │  ┌────┴────┐          │      │          ┌────┴────┐  │    │
│   │  │  eth0   │          │      │          │  eth0   │  │    │
│   │  └────┬────┘          │      │          └────┬────┘  │    │
│   │       │               │      │               │       │    │
│   └───────┼───────────────┘      └───────────────┼───────┘    │
│           │                                      │             │
│           └──────────────────────────────────────┘             │
│                   Overlay or Routing                            │
│                (VXLAN, IPIP, BGP, etc.)                        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Before running this, what output do you expect from a healthy cluster when you compare pod IPs, node placement, and pod routes? A useful prediction is that each pod has a non-empty IP, pods on different nodes occupy different node pod CIDRs, and each pod has a default route pointing at a CNI-provided gateway or interface. When the observed output violates that prediction, you can classify the problem as IPAM, local attachment, or cross-node routing instead of treating it as a generic "network is broken" case.

---

## kube-proxy, Services, DNS, and Host Networking

CNI gets packets between pod IPs, but Kubernetes Services add a second abstraction: stable virtual IPs and DNS names that point at a moving set of endpoints. kube-proxy watches Services and EndpointSlices, then programs node-local dataplane rules so traffic for a ClusterIP reaches one of the backend pod IPs. This is why a pod can reach `web.default.svc.cluster.local` even though the actual nginx pod may be rescheduled to a different node later.

EndpointSlice is the bridge between the API abstraction and the service dataplane. A Service selector finds pods, the control plane records endpoint information, and kube-proxy consumes that information to update node rules. If a Service has no endpoints, kube-proxy can be perfectly healthy and still have nowhere useful to send traffic. That is why service troubleshooting should always include selectors and endpoints before node-level packet rules, especially when a new Deployment was just rolled out.

| Mode | Description | Performance | Use Case |
|------|-------------|-------------|----------|
| **nftables** | Uses nftables | Best | Recommended modern mode (GA 1.33+, kernel ≥5.13); enable explicitly |
| **iptables** | Uses iptables rules | Good | Default on Linux when mode is unspecified |
| **IPVS** | Uses kernel IPVS | Better | High pod count (has known edge cases) |
| **userspace** | Legacy, user-space proxy | Poor | Avoid using; deprecated |

The kube-proxy mode matters most when service churn or service count becomes large. iptables mode remains the Linux default when mode is not explicitly configured, which is why many clusters and lab environments still show iptables evidence. nftables is GA in Kubernetes 1.33+, is recommended as the modern mode when nodes run a supported kernel such as Linux 5.13 or newer, and should be enabled explicitly after you confirm compatibility. IPVS is still seen in older high-scale clusters, but it has edge cases and operational differences that make nftables the preferred modern answer unless your environment has a specific reason to choose otherwise.

For the CKA, you are unlikely to redesign kube-proxy mode during the exam, but recognizing the mode helps you read the right evidence. iptables mode points to `iptables-save`, NAT chains, and rule ordering. IPVS points to `ipvsadm` and virtual server tables. nftables points to the nftables ruleset and kube-proxy configuration. The higher-level troubleshooting sequence remains the same, but the node commands and performance expectations change with the mode.

```
┌────────────────────────────────────────────────────────────────┐
│                   kube-proxy Flow                               │
│                                                                 │
│   Client Pod                                                   │
│       │                                                         │
│       │ Request to Service IP 10.96.45.123:80                  │
│       ▼                                                         │
│   ┌───────────────────────────────────────────────────────┐    │
│   │             kube-proxy dataplane                       │    │
│   │        (iptables / nftables / IPVS)                    │    │
│   │                                                        │    │
│   │  Virtual-IP rule/map:                                 │    │
│   │  10.96.45.123:80 → backend pod IP selection           │    │
│   │                                                        │    │
│   │  Selected: 10.244.1.5:8080                            │    │
│   └───────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼                                                         │
│   Backend Pod (10.244.1.5:8080)                                │
│                                                                 │
│   kube-proxy watches API server for Service/Endpoint changes  │
│   and updates service dataplane rules accordingly             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

When service traffic fails, separate name resolution from virtual IP routing. A pod that cannot resolve `web` may have a CoreDNS or resolver configuration issue. A pod that resolves `web` to a ClusterIP but cannot connect may have no endpoints, blocked NetworkPolicy, kube-proxy failure, or backend application problems. A pod that can reach the backend pod IP directly but not the ClusterIP points strongly toward kube-proxy or service dataplane rules rather than CNI cross-node routing.

This separation prevents a common false conclusion: "DNS is broken" whenever a URL fails. `wget http://web` includes name lookup, service virtual IP routing, backend selection, network policy, and application response. Replacing that single test with `nslookup web`, `kubectl get endpointslice`, direct pod IP access, and ClusterIP access gives you a chain of facts. The first failed link in that chain is where the next detailed inspection belongs.

```bash
# Check kube-proxy pods
kubectl get pods -n kube-system -l k8s-app=kube-proxy

# Check kube-proxy mode from configuration first
kubectl get configmap kube-proxy -n kube-system -o yaml | grep -A2 '^[[:space:]]*mode:'

# Recent logs can confirm the proxier that started
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=20 | grep -iE 'Using|Proxier|mode'

# View kube-proxy configmap
kubectl get configmap kube-proxy -n kube-system -o yaml

# Check iptables rules (on node)
iptables -t nat -L KUBE-SERVICES -n | head -20

# Check IPVS rules (if using IPVS mode, on node)
ipvsadm -Ln
```

Host networking is the exception path that bypasses a major part of pod isolation. With `hostNetwork: true`, a pod uses the node's network namespace, sees the node interfaces, and competes for the same listening ports as host processes and other host-networked pods on that node. This is appropriate for some node agents, CNI components, and low-level diagnostics, but it should be treated as a privileged design choice rather than a quick fix for broken pod networking.

The operational cost is not only port conflict. Host-networked pods are harder to reason about because their traffic may follow node firewall rules, node resolver configuration, and node identity assumptions instead of ordinary pod behavior. Monitoring and policy tools may also report them differently. If the workload needs to observe or modify node networking, host networking can be correct; if the workload merely needs to be reachable, a Service, DaemonSet design, or proper CNI repair is usually safer.

```yaml
# Pod using host network
apiVersion: v1
kind: Pod
metadata:
  name: host-network-pod
spec:
  hostNetwork: true         # Uses node's network namespace
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 80     # Binds to node's port 80!
```

`hostPort` is narrower: the pod still has its own pod network namespace, but the node maps a specific port to the container. Both features create scheduling constraints because two pods cannot bind the same host port on the same node. The DNS detail is easy to miss: host-networked pods should usually set `dnsPolicy: ClusterFirstWithHostNet`, otherwise they may inherit node resolver behavior and fail to resolve cluster service names even while external names work.

```yaml
# Pod with host port mapping
apiVersion: v1
kind: Pod
metadata:
  name: hostport-pod
spec:
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 8080
      hostPort: 80           # Node's port 80 → container 8080
```

**Pause and predict:** you set `hostNetwork: true` on a pod running nginx on port 80, and another host-networked pod already listens there on the same node. What failure do you expect, and where would you look for evidence?

<details>
<summary>Reveal the failure and its owner</summary>

Host networking makes both processes compete for the node's listening port rather than giving each pod an isolated port. The scheduler may avoid an impossible placement when ports are declared, but a runtime conflict prevents the container from binding its address and appears as an application start failure. Inspect container status and logs before changing the network configuration.

</details>

Before expanding the explanation, decide whether the observed failure belongs to placement or process startup; that distinction determines which evidence you collect first.

---

## CIDR Configuration and NetworkPolicy Reality

Pod CIDRs, service CIDRs, and node pod CIDRs are separate address-planning concepts that must not overlap. The pod CIDR is the address space assigned to pods, the service CIDR is the virtual address space assigned to ClusterIPs, and each node may receive a smaller pod CIDR for local allocation. If you change one side of that plan after cluster creation, you need to understand which controllers, CNI configuration, and existing objects still assume the old range.

Address planning also affects future scale. A small pod CIDR might work in a lab with two nodes and a handful of pods, then become a hard ceiling when each node needs hundreds of pod addresses or the platform expands to multiple environments. A service CIDR that overlaps with corporate routing can create confusing failures where some clients send traffic outside the cluster instead of to virtual service addresses. The safest time to find these conflicts is before cluster creation, not during a production migration.

| CIDR Type | Description | Example |
|-----------|-------------|---------|
| **Pod CIDR** | IP range for all pods | 10.244.0.0/16 |
| **Service CIDR** | IP range for services | 10.96.0.0/12 |
| **Node CIDR** | Pod range per node | 10.244.1.0/24 |

CIDR mismatches create failures that look unrelated until you inspect the allocation path. A cluster might initialize with `--pod-network-cidr=10.244.0.0/16`, while a plugin manifest expects a different pool; pods then receive no address, receive an address that other nodes do not route, or create traffic that disappears at the node boundary. On the CKA, you are more likely to diagnose the mismatch than redesign the entire address plan, so learn where to read the cluster and plugin views of the world.

The plugin view may not live in the same place for every CNI. Some plugins store IP pools in custom resources, some use ConfigMaps, and cloud-native plugins may depend on cloud APIs or node annotations. That variability is the reason the first question is "which CNI is this?" rather than "which file should I edit?" Once you identify the plugin, use its documented control surface and compare it with Kubernetes node pod CIDR evidence.

```bash
# Check pod CIDR (from kube-controller-manager)
kubectl get cm kubeadm-config -n kube-system -o yaml | grep -i cidr

# Check from nodes
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.podCIDR}{"\n"}{end}'

# Check service CIDR
kubectl cluster-info dump | grep -m 1 service-cluster-ip-range
```

```bash
# During cluster init
kubeadm init --pod-network-cidr=10.244.0.0/16 --service-cidr=10.96.0.0/12

# The CNI plugin must match this CIDR
# Example: Calico installation with matching CIDR
```

NetworkPolicy is another place where Kubernetes API acceptance does not guarantee dataplane enforcement. The API server can store a valid NetworkPolicy object even if the installed CNI does not implement policy. In a Flannel-only cluster, that means the YAML can look perfect and the isolation can still be nonexistent. In a Calico or Cilium cluster, enforcement also depends on selectors, namespaces, default-deny posture, and whether the traffic being tested is ingress, egress, or both.

Policy debugging should be framed as a selection problem before it becomes a packet problem. Does the policy select the pods you think it selects? Does it select the namespace you are testing from? Is the policy ingress-only while the failing requirement is egress? Are you testing traffic to a pod IP, a service IP, or an external address? Answering those questions in writing often exposes the bug before you need deeper plugin-specific tools.

Exercise scenario: a namespace owner creates a default-deny ingress policy and then allows only `app=frontend` to reach `app=api`, but tests from an unrelated namespace still succeed. The right first move is not to rewrite the policy blindly; first confirm that the plugin supports NetworkPolicy, then confirm the test pod labels and namespace labels match the policy selectors, and finally test direct pod IP traffic and service traffic separately. That order prevents the common mistake of debugging YAML while the installed plugin is incapable of enforcing it.

---

## Troubleshooting Workflow and Worked Example

A good network investigation moves from the closest observable symptom outward. Start with pod phase, events, pod IP, and node placement, then test same-node pod IP connectivity, cross-node pod IP connectivity, service ClusterIP connectivity, and DNS. Each step is designed to answer one question and eliminate one layer. If you jump directly to changing CNI manifests, you can easily convert a single-node failure into a cluster-wide outage.

The workflow is also a communication tool. When you hand off an incident, "network is broken" is nearly useless, but "pods on node A have IPs, same-node ping works, cross-node pod IP traffic from node A to node B fails, and kube-proxy service tests were not reached" gives the next engineer a precise starting point. This style of reporting reduces repeated work and protects the cluster from speculative changes. It is the same discipline you should use in written exam notes.

```
Pod Network Issue?
    │
    ├── kubectl get pod -o wide (check pod IP, node)
    │
    ├── Pod has IP?
    │   ├── No → CNI issue
    │   │        Check: CNI pods, /etc/cni/net.d/, CNI logs
    │   │
    │   └── Yes → Continue
    │
    ├── Can reach other pods on same node?
    │   ├── No → Bridge/veth issue
    │   │
    │   └── Yes → Continue
    │
    ├── Can reach pods on other nodes?
    │   ├── No → Overlay/routing issue
    │   │        Check: CNI config, node routes, firewall
    │   │
    │   └── Yes → Continue
    │
    ├── Can reach services?
    │   ├── No → kube-proxy or DNS issue
    │   │        Check: kube-proxy mode (iptables/nftables/IPVS), CoreDNS
    │   │
    │   └── Yes → Network is fine, check app
    │
    └── Check NetworkPolicy
        kubectl get networkpolicy
```

Use commands that reveal state rather than commands that merely retry the failing request. `ip addr` shows whether the pod has the expected interface and address, `ip route` shows how the pod sends traffic out of its namespace, and `/etc/resolv.conf` shows whether the pod is configured to use cluster DNS. On the control plane side, CNI DaemonSet logs, kube-proxy logs, and CoreDNS logs help you decide whether a failure belongs to attachment, service routing, or name resolution.

Prefer short, paired tests over broad command dumps. For example, compare `kubectl exec pod1 -- ping <pod-ip>` with `kubectl exec pod1 -- wget --spider http://service-name`, then explain what changed between those two paths. If only the second fails, you added DNS, service routing, backend selection, or application protocol behavior. If both fail, the problem is probably lower in the path. This method keeps the investigation understandable even when the cluster has many moving parts.

```bash
# Check pod network
kubectl exec <pod> -- ip addr
kubectl exec <pod> -- ip route
kubectl exec <pod> -- cat /etc/resolv.conf

# Test connectivity
kubectl exec <pod> -- ping <other-pod-ip>
kubectl exec <pod> -- nc -zv <service> <port>
kubectl exec <pod> -- wget --spider --timeout=1 http://<service>

# Check CNI pods
kubectl get pods -n kube-system | grep -E "calico|flannel|cilium|canal|kindnet"
kubectl logs -n kube-system <cni-pod>

# Check kube-proxy
kubectl get pods -n kube-system -l k8s-app=kube-proxy
kubectl logs -n kube-system -l k8s-app=kube-proxy

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

| Symptom | Cause | Solution |
|---------|-------|----------|
| Pod stuck in ContainerCreating | CNI not installed or failing | Install/fix CNI plugin |
| Pod has no IP | IPAM exhausted or CNI error | Check CNI logs, expand CIDR |
| Can't reach pods on other nodes | Overlay misconfigured | Check CNI network config |
| Services unreachable | kube-proxy not running | Check kube-proxy pods |
| DNS not working | CoreDNS down | Check CoreDNS pods |
| NetworkPolicy not working | CNI doesn't support it | Use Calico or Cilium |

Worked example: suppose `pod1` can ping `pod2` when both run on the same node, but the ping fails after `pod2` is rescheduled to another node. That result proves IPAM and pod-local interfaces are working, and it makes a pure service or DNS explanation unlikely because you are testing pod IPs directly. The next checks are CNI agents on both nodes, node routes for the remote pod CIDR, overlay interfaces such as `flannel.1` or `tunl0`, and any firewall or security group rules that block encapsulation or BGP between nodes.

Now suppose the same two pods can ping each other by IP, but `wget http://web` fails after you create a Service for the server. The investigation moves upward because pod routing has already passed. Check that the Service selector matches the pod labels, that EndpointSlices contain the backend address, and that kube-proxy is healthy on the client node. If the Service has endpoints and kube-proxy is healthy, then policy or application listener behavior becomes more plausible than CNI attachment.

Stop and think: a new pod is stuck in `ContainerCreating`, and events say "network plugin is not ready." Before changing any CNI configuration, check whether the CNI DaemonSet pod is running on that node, whether `/etc/cni/net.d/` contains a config file, and whether other nodes can create pods successfully. Those three observations distinguish a cluster-wide missing install from a node-specific agent failure, which determines whether your next action is installation, log inspection, node repair, or capacity cleanup.

---

## Patterns & Anti-Patterns

The strongest CNI operations pattern is to debug by layer and stop when the evidence changes layers. A pod without an IP is an attachment or IPAM problem. A pod with an IP that cannot reach a same-node peer is a local dataplane or policy problem. A pod that can reach peer pod IPs but not a ClusterIP is more likely to involve kube-proxy, endpoints, or service rules. This discipline keeps the investigation small enough to finish under exam pressure and safe enough for production troubleshooting.

Another useful pattern is to keep a known-good network probe available in every cluster. A tiny BusyBox or netshoot-style pod can provide `ip`, `route`, `nslookup`, `wget`, and `nc` without changing application images. In locked-down production environments, the probe should be controlled and audited, but the principle remains valuable: you need a neutral client whose behavior is not tangled with the application you are diagnosing.

| Pattern | When to Use | Why It Works | Scaling Consideration |
|---------|-------------|--------------|-----------------------|
| Layered connectivity tests | Any pod, service, or DNS incident | Each test isolates CNI, kube-proxy, CoreDNS, or app behavior | Automate the sequence in runbooks so teams gather comparable evidence |
| Policy-capable CNI by default | Clusters with namespace isolation or compliance needs | NetworkPolicy is enforceable only when the dataplane implements it | Plan default-deny rollout gradually to avoid blocking shared services |
| CIDR planning before cluster creation | New clusters, lab rebuilds, or platform migrations | Pod and service ranges are hard to change cleanly after workloads exist | Reserve enough address space for node growth, dual-stack plans, and test clusters |
| Node-local evidence collection | Failures isolated to one node | CNI config files, routes, and agent state are node-specific | Keep node access audited and prefer read-only commands during triage |

The most common anti-pattern is treating CNI as a black box until something breaks. Teams install a plugin once, forget which mode it uses, and then assume every network symptom is an application problem. A better approach is to record the plugin, policy support, encapsulation or routing mode, pod CIDR, service CIDR, and kube-proxy mode as part of cluster documentation. That record makes incidents faster because the first responder starts with the actual design rather than rediscovering it during a failure.

Be careful with "fixes" that work by bypassing the model. Adding `hostNetwork: true`, exposing more NodePorts, or allowing all traffic in a NetworkPolicy may make one test pass while weakening the cluster's design. Those changes should be treated as temporary experiments unless they match the workload's requirements. The better alternative is to identify which layer failed and restore the intended contract: pods get routable IPs, services route to endpoints, DNS resolves service names, and policies express deliberate access.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Installing Flannel and assuming policies work | NetworkPolicy objects are accepted but not enforced | Choose Calico, Cilium, Canal, or another policy-capable design |
| Changing pod CIDRs after workloads exist | Existing routes, pools, and node allocations disagree | Rebuild or migrate deliberately with documented address planning |
| Debugging service DNS before pod IP connectivity | Name resolution hides lower-layer CNI failures | Prove pod IP connectivity first, then service IP, then DNS |
| Using host networking as a workaround | Pods lose normal network isolation and contend for node ports | Fix the CNI path unless the workload truly requires host namespace access |
| Reading one healthy CNI pod and declaring success | DaemonSet health can differ per node | Check node placement, affected-node logs, and per-node config files |

---

## Decision Framework

When you choose or troubleshoot a CNI path, ask three questions in order: what guarantee do I need, where is the failure observed, and what component owns that layer? For a new cluster, "what guarantee" includes NetworkPolicy enforcement, cloud integration, observability, bare-metal routing, and team familiarity. For an incident, "where observed" means pod creation, pod IP connectivity, service IP connectivity, DNS, or policy behavior. The owner question then points to CNI, kube-proxy, CoreDNS, the application, or the underlying node network.

This framework keeps design and debugging connected. If your design requires enforced tenant isolation, the owner is not just the YAML author; it is the CNI dataplane that must enforce the policy. If your symptom is service update latency, the owner is probably kube-proxy mode or a replacement dataplane, not IPAM. If your symptom is node-specific pod creation failure, the owner may be the CNI agent on that node. The same ownership map helps you choose the right documentation and the right logs.

```
Choose or debug CNI path
    │
    ├── Need Kubernetes NetworkPolicy?
    │   ├── Yes → Choose policy-capable CNI (Calico, Cilium, Canal, cloud + policy)
    │   └── No  → Simpler CNI may be acceptable for labs or low-risk clusters
    │
    ├── Pod has no IP?
    │   ├── Yes → Inspect CNI install, IPAM, node CNI config, kubelet events
    │   └── No  → Continue to connectivity tests
    │
    ├── Pod IP works but Service IP fails?
    │   ├── Yes → Inspect endpoints, kube-proxy mode, service rules, backend readiness
    │   └── No  → Continue to DNS and policy checks
    │
    └── DNS name fails but ClusterIP works?
        ├── Yes → Inspect CoreDNS, resolver config, hostNetwork dnsPolicy
        └── No  → Re-check application listener, policy, and routes
```

| Requirement or Symptom | Prefer This Direction | Avoid This Direction |
|------------------------|-----------------------|----------------------|
| Need simple training cluster | Flannel or default lab CNI | Overbuilding with features the team cannot operate |
| Need namespace isolation | Calico, Cilium, Canal, or policy-capable cloud setup | Flannel alone with unenforced policies |
| Need deep flow visibility | Cilium or a plugin with strong observability tooling | Minimal plugin with no useful node-level diagnostics |
| Pod creation fails before IP assignment | CNI install, IPAM, config files, node agent logs | kube-proxy and CoreDNS first |
| ClusterIP fails while pod IP works | kube-proxy, endpoints, service selector, backend readiness | Reinstalling CNI without evidence |
| hostNetwork pod cannot resolve services | `dnsPolicy: ClusterFirstWithHostNet` and resolver inspection | Assuming external DNS success proves cluster DNS works |

Which approach would you choose here and why: a small bare-metal cluster needs NetworkPolicy enforcement, the team is comfortable with Kubernetes but not BGP, and the security team wants namespace-level default deny within the first month? A reasonable answer is to choose a policy-capable plugin with an overlay or simple routing mode, document the policy rollout, and avoid a BGP-heavy design until the team can operate it. The key is to connect the plugin choice to requirements and operational skill, not to rank plugins by popularity.

For migration decisions, add one more question: can you tolerate rebuilding nodes or clusters? CNI changes can affect pod addresses, policy semantics, node routes, and service dataplane assumptions. Some migrations are possible in place with vendor guidance, while others are safer as blue-green cluster migrations. On the exam you will not perform a complex migration, but in real platform work this risk is why CNI selection deserves early design attention.

---

## Did You Know?

- **CNI predates many Kubernetes networking conveniences**: the CNI specification defines the runtime-to-plugin contract with operations such as `ADD` and `DEL`, which is why kubelet can rely on different plugins without embedding one network implementation.

- **Kubernetes does not ship a default pod network**: after `kubeadm init`, you still need to install a compatible CNI plugin before normal pods and CoreDNS can become useful.

- **Flannel alone does not enforce NetworkPolicy**: NetworkPolicy is a Kubernetes API, but enforcement is delegated to the network implementation, so unsupported plugins can leave valid policy objects with no dataplane effect.

- **nftables is the modern kube-proxy mode to evaluate**: iptables remains the Linux default when kube-proxy mode is unspecified, but nftables is GA and recommended for modern clusters when nodes run a supported kernel, so Kubernetes 1.35 clusters should evaluate it explicitly before choosing IPVS or staying on iptables.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Installing Kubernetes and forgetting CNI | kubeadm creates control-plane components, so the cluster looks partially alive before pod networking works | Install a compatible CNI plugin and confirm CNI pods plus `/etc/cni/net.d/` are present |
| Using Flannel while relying on NetworkPolicy | The API server accepts policy objects even when the plugin does not enforce them | Choose Calico, Cilium, Canal, or another policy-capable implementation |
| Mixing pod CIDRs between kubeadm and the plugin | The cluster controller and plugin allocate or route different address ranges | Align `--pod-network-cidr`, plugin IP pools, and node pod CIDRs before creating workloads |
| Debugging DNS before checking pod IP connectivity | Service names fail for many reasons, including lower-layer pod networking failures | Test pod IP, then ClusterIP, then DNS, and record which boundary first fails |
| Forgetting `ClusterFirstWithHostNet` on host-networked pods | Host-networked pods can inherit node resolver behavior instead of cluster DNS | Set `dnsPolicy: ClusterFirstWithHostNet` when host-networked pods need service discovery |
| Assuming one healthy CNI pod proves all nodes are healthy | CNI runs as a DaemonSet, and a single failed node agent can break only pods placed there | Check `kubectl get pods -n kube-system -o wide` and compare affected workload nodes |
| Reinstalling CNI during every network incident | Network symptoms can belong to kube-proxy, endpoints, DNS, NetworkPolicy, or the app | Use a layered workflow and change the owning component only after evidence points there |

---

## Quiz

<details>
<summary>Question 1: After `kubeadm init`, CoreDNS and application pods stay in `ContainerCreating`, and events mention that the network plugin is not ready. What is the most likely root cause, and what should you verify before deploying workloads?</summary>

The most likely cause is that no working CNI plugin is installed or kubelet cannot read a valid CNI configuration on the node. Kubernetes can create core control-plane objects without providing pod networking, so CoreDNS is affected because it is itself a pod. Verify that the CNI DaemonSet is running, that `/etc/cni/net.d/` contains the expected configuration, and that the plugin CIDR matches the cluster pod CIDR. Do not debug CoreDNS first, because DNS depends on pod networking being ready.
</details>

<details>
<summary>Question 2: Your team uses Flannel and creates NetworkPolicies to isolate production, but cross-namespace traffic still succeeds. The policy selectors are correct. What failed in the design?</summary>

The design assumes that NetworkPolicy enforcement is handled by Kubernetes itself, but enforcement belongs to the network implementation. Flannel alone provides pod networking but does not enforce NetworkPolicy, so the API objects can exist without changing traffic behavior. The fix is to use a policy-capable plugin such as Calico or Cilium, or a combined approach such as Canal when appropriate. Rewriting the same selectors will not solve the problem because the dataplane lacks the enforcement feature.
</details>

<details>
<summary>Question 3: Pods on the same node can ping each other by pod IP, but pods on different nodes cannot. Both pods have IP addresses and both nodes are Ready. Which layer should you investigate next?</summary>

This points toward cross-node CNI routing or encapsulation rather than basic pod creation. Same-node success proves the local veth and bridge or local dataplane path is working, while cross-node failure adds the node network, overlay, BGP, or cloud routing layer. Check CNI agents on both nodes, routes to remote pod CIDRs, overlay interfaces, and firewall rules for the plugin's node-to-node protocol. kube-proxy is not the first suspect because the test uses pod IPs rather than Service ClusterIPs.
</details>

<details>
<summary>Question 4: A pod can connect directly to a backend pod IP, but connecting to the Service ClusterIP times out. DNS resolution returns the expected ClusterIP. What should you check before changing CNI?</summary>

The direct pod IP test suggests that CNI pod-to-pod connectivity works for that path, and successful DNS resolution means CoreDNS returned a service address. The remaining layer is service routing and backend selection, so check the Service selector, EndpointSlices or Endpoints, backend readiness, and kube-proxy health or mode. It is also reasonable to inspect node-local service rules if you have node access. Reinstalling CNI would be premature because the evidence points to the virtual IP path.
</details>

<details>
<summary>Question 5: A host-networked pod can resolve public domains but cannot resolve `kubernetes.default.svc`. What one-line pod spec change is usually required, and why?</summary>

Set `dnsPolicy: ClusterFirstWithHostNet` on the pod. A host-networked pod uses the node network namespace, and without the special DNS policy it may inherit resolver settings that point to infrastructure DNS instead of CoreDNS. Public DNS can still work because the node resolver knows external domains, which makes the symptom misleading. The policy tells kubelet to configure cluster DNS behavior even though the pod uses host networking.
</details>

<details>
<summary>Question 6: Your cluster has thousands of Services, kube-proxy CPU spikes during Service updates, and the cluster still uses iptables mode. What direction should you evaluate for Kubernetes 1.35?</summary>

Evaluate nftables mode first because it is the modern kube-proxy direction and is designed to handle service rules more efficiently than legacy iptables behavior. IPVS may also appear in older high-scale designs, but it has its own edge cases and is no longer the default recommendation for new clusters. Cilium's kube-proxy replacement can be a valid platform choice when the team is already operating Cilium. The important reasoning is that service update cost belongs to kube-proxy or service dataplane design, not to pod IP allocation.
</details>

<details>
<summary>Question 7: A node can no longer start new pods, but other nodes continue to schedule pods successfully. The failing pods have no pod IP. What evidence separates a node-local CNI failure from a cluster-wide CIDR design problem?</summary>

Compare the affected node with a healthy node instead of looking only at one failing pod. If other nodes still allocate pod IPs, the cluster CIDR is probably not globally exhausted, and the failing node may have a missing CNI config file, crashed CNI agent, invalid local state, or exhausted node-local allocation. Check CNI DaemonSet placement, node events, `/etc/cni/net.d/`, and plugin logs on the affected node. A global CIDR mismatch usually affects new pods across the cluster, especially after a fresh installation.
</details>

---

## Hands-On Exercise

Exercise scenario: you are given a Kubernetes 1.35 cluster and asked to prove that pod networking, service routing, DNS, and host-network behavior are healthy enough for application teams. Work through the tasks in order and write down the first layer that fails if your environment behaves differently. The goal is not to memorize output; the goal is to practice a repeatable inspection path that you can use during the CKA and during real operations.

### Task 1: Identify the Installed CNI

Start by discovering the plugin from both the Kubernetes API and the node filesystem. The API view tells you which node agents should exist, while the filesystem view tells you whether kubelet has a CNI configuration to call. If you do not have node shell access in your lab, record that limitation and rely on DaemonSet and pod logs for the Kubernetes-side evidence.

```bash
# Check CNI pods
kubectl get pods -n kube-system | grep -E "calico|flannel|cilium|canal|kindnet|cni"

# Check CNI daemonsets
kubectl get ds -n kube-system

# Check CNI configuration on a node
ls /etc/cni/net.d/ 2>/dev/null || echo "Run on a node with shell access"
```

<details>
<summary>Solution guidance</summary>

A healthy cluster should show one CNI node agent per schedulable node, usually through a DaemonSet in `kube-system`. If no CNI pods appear and `/etc/cni/net.d/` is empty, the cluster likely cannot attach normal pods to the network. If CNI pods exist but only one node fails workload creation, compare the CNI pod and config files on that specific node against a healthy node.
</details>

### Task 2: Inspect Pod and Service CIDRs

Next, inspect the address ranges that the control plane and nodes believe they should use. The pod CIDR and service CIDR must be separate, and the plugin must agree with the pod range it is expected to allocate or route. Record the node pod CIDRs because they make cross-node routing problems easier to reason about later.

```bash
# Get node CIDRs
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.podCIDR}{"\n"}{end}'

# Check pod CIDR from kubeadm config if available
kubectl get cm kubeadm-config -n kube-system -o yaml 2>/dev/null | grep -i cidr

# Check service CIDR from cluster dump if available
kubectl cluster-info dump | grep -m 1 service-cluster-ip-range
```

<details>
<summary>Solution guidance</summary>

You should see a pod CIDR per node in many kubeadm-style clusters, although some CNI and cloud-native designs represent allocation differently. A missing or unexpected node pod CIDR is a clue, not a final diagnosis. Confirm the plugin design before assuming every cluster must show the exact same fields.
</details>

### Task 3: Create Test Pods and Inspect Their Network View

Create two temporary pods and inspect their IP addresses, routes, and resolver configuration. This gives you a known client and server pair for later tests. If the pods fail to become ready, do not continue to service testing; inspect events and CNI logs because the attachment layer has already failed.

```bash
kubectl run pod1 --image=busybox:1.36 --command -- sleep 3600
kubectl run pod2 --image=busybox:1.36 --command -- sleep 3600

# Wait for ready
kubectl wait --for=condition=ready pod/pod1 pod/pod2 --timeout=60s

# Get pod IPs and node placement
kubectl get pods -o wide

# Check pod network interface and routes
kubectl exec pod1 -- ip addr
kubectl exec pod1 -- ip route

# Check DNS configuration
kubectl exec pod1 -- cat /etc/resolv.conf
```

<details>
<summary>Solution guidance</summary>

Both pods should have pod IPs, and `pod1` should show an interface and route configuration installed by the CNI. The resolver configuration should include cluster DNS behavior for normal pods. If `pod1` has no IP or the wait command times out, use `kubectl describe pod pod1` and CNI node logs before testing services.
</details>

### Task 4: Test Pod IP, Service, and DNS Connectivity

Now test the path in layers: direct pod IP first, then a Service, then DNS-backed service access. This order matters because a DNS failure can hide a perfectly healthy pod IP path, and a service failure can hide a healthy direct pod path. Keep the temporary resources small so cleanup is safe and quick.

```bash
# Test pod-to-pod connectivity
POD2_IP=$(kubectl get pod pod2 -o jsonpath='{.status.podIP}')
kubectl exec pod1 -- ping -c 3 "$POD2_IP"

# Create service-backed workload
kubectl create deployment web --image=nginx
kubectl expose deployment web --port=80

# Wait for deployment
kubectl wait --for=condition=available deployment/web --timeout=60s

# Test DNS and service connectivity
kubectl exec pod1 -- wget --spider --timeout=2 http://web
```

<details>
<summary>Solution guidance</summary>

If pod IP connectivity works but `http://web` fails, check whether the Service has endpoints before blaming CNI. `kubectl get endpointslice -l kubernetes.io/service-name=web` or `kubectl get endpoints web` can show whether the selector found the nginx pod. If endpoints exist, move to kube-proxy and NetworkPolicy checks.
</details>

### Task 5: Check kube-proxy, CoreDNS, and a Host-Network Edge Case

Finish by checking the components that are often confused with CNI. kube-proxy owns ClusterIP routing, CoreDNS owns service name resolution, and host-networked pods need explicit DNS policy when they should use cluster DNS. The host-network example also shows why bypassing normal pod networking should be a deliberate design choice.

```bash
# Check kube-proxy pods, mode config, and recent proxier logs
kubectl get pods -n kube-system -l k8s-app=kube-proxy
kubectl get configmap kube-proxy -n kube-system -o yaml | grep -A2 '^[[:space:]]*mode:'
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=20 | grep -iE 'Using|Proxier|mode'

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=20

# Create hostNetwork pod with cluster DNS behavior
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: host-net
spec:
  hostNetwork: true
  dnsPolicy: ClusterFirstWithHostNet
  containers:
  - name: test
    image: busybox:1.36
    command: ["sleep", "3600"]
EOF

kubectl wait --for=condition=ready pod/host-net --timeout=60s
kubectl get pod host-net -o wide
kubectl exec host-net -- nslookup kubernetes
```

<details>
<summary>Solution guidance</summary>

The host-networked pod should show the node network identity rather than an ordinary isolated pod address, and it should still resolve the `kubernetes` service because `ClusterFirstWithHostNet` is set. If service DNS fails only for this pod, compare its resolver configuration against `pod1`. If service routing fails for all pods, return to kube-proxy and endpoint checks.
</details>

### Optional Timed Drills

These drills preserve the same investigation moves in shorter repetitions. Use them after the main exercise if you want exam-speed practice, and keep the same rule: predict what each command should prove before you run it. The target times are not important for production work, but they are useful in a CKA setting because they force you to gather the highest-value facts first.

```bash
# Drill: Identify CNI from kube-system pods
kubectl get pods -n kube-system | grep -E "calico|flannel|cilium|canal|kindnet"

# Check CNI daemonsets
kubectl get ds -n kube-system
```

```bash
# Drill: Check node annotations for CNI hints
kubectl get nodes -o jsonpath='{.items[0].metadata.annotations}' | jq 'keys'
```

```bash
# Drill: Check Pod CIDR from nodes
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.podCIDR}{"\n"}{end}'

# Check kubeadm config if available
kubectl get cm kubeadm-config -n kube-system -o yaml 2>/dev/null | grep -i cidr
```

```bash
# Drill: Check controller-manager flags if static pods expose them
kubectl get pods -n kube-system -l component=kube-controller-manager -o yaml | grep cluster-cidr
```

```bash
# Drill: Pod network information
kubectl run net-test --image=busybox:1.36 --command -- sleep 3600
kubectl wait --for=condition=ready pod/net-test --timeout=60s
kubectl exec net-test -- ip addr
kubectl exec net-test -- ip route
kubectl exec net-test -- cat /etc/resolv.conf
kubectl delete pod net-test
```

```bash
# Drill: kube-proxy mode
kubectl get configmap kube-proxy -n kube-system -o yaml | grep -A2 '^[[:space:]]*mode:'
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=20 | grep -iE 'Using|Proxier|mode'
kubectl get pods -n kube-system -l k8s-app=kube-proxy -o wide
```

```bash
# Drill: Pod-to-pod and HTTP connectivity
kubectl run client --image=busybox:1.36 --command -- sleep 3600
kubectl run server --image=nginx
kubectl wait --for=condition=ready pod/client pod/server --timeout=60s
SERVER_IP=$(kubectl get pod server -o jsonpath='{.status.podIP}')
kubectl exec client -- ping -c 2 "$SERVER_IP"
kubectl exec client -- wget --spider --timeout=2 "http://$SERVER_IP"
kubectl delete pod client server
```

```bash
# Drill: Service routing with ClusterIP
kubectl create deployment svc-test --image=nginx
kubectl expose deployment svc-test --port=80
kubectl wait --for=condition=available deployment/svc-test --timeout=60s
CLUSTER_IP=$(kubectl get svc svc-test -o jsonpath='{.spec.clusterIP}')
kubectl run test --rm -i --image=busybox:1.36 --restart=Never -- \
  wget --spider --timeout=2 "http://$CLUSTER_IP"
kubectl delete deployment svc-test
kubectl delete svc svc-test
```

```bash
# Drill: hostNetwork pod with cluster DNS
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: host-net-drill
spec:
  hostNetwork: true
  dnsPolicy: ClusterFirstWithHostNet
  containers:
  - name: test
    image: busybox:1.36
    command: ["sleep", "3600"]
EOF

kubectl wait --for=condition=ready pod/host-net-drill --timeout=60s
kubectl get pod host-net-drill -o wide
kubectl exec host-net-drill -- nslookup kubernetes
kubectl delete pod host-net-drill
```

```bash
# Challenge starter: complete without looking at the solution
# 1. Create client and server pods
# 2. Get both pod IPs and node placement
# 3. Test ping from client to server
# 4. Create a service for server
# 5. Test DNS resolution and HTTP connectivity
# 6. Identify the installed CNI
# 7. Clean up everything you created
```

<details>
<summary>Challenge solution</summary>

```bash
kubectl run client --image=busybox:1.36 --command -- sleep 3600
kubectl run server --image=nginx
kubectl wait --for=condition=ready pod/client pod/server --timeout=60s

kubectl get pods -o wide
SERVER_IP=$(kubectl get pod server -o jsonpath='{.status.podIP}')
kubectl exec client -- ping -c 2 "$SERVER_IP"

kubectl expose pod server --port=80 --name=server-svc
kubectl exec client -- nslookup server-svc
kubectl exec client -- wget --spider --timeout=2 http://server-svc

kubectl get pods -n kube-system | grep -E "calico|flannel|cilium|canal|kindnet"

kubectl delete pod client server
kubectl delete svc server-svc
```

</details>

### Task 6: Cleanup and Success Criteria

Clean up every object you created and confirm the namespace is back to its original shape. Cleanup is part of the exercise because networking labs often leave test pods and services that confuse later troubleshooting. When you are done, use the checklist to verify that you actually practiced each target skill rather than only running the commands.

```bash
kubectl delete pod pod1 pod2 host-net --ignore-not-found
kubectl delete deployment web --ignore-not-found
kubectl delete svc web --ignore-not-found
```

### Card A — A pod whose CNI ADD fails still shows a PodIP.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** CNI attachment failed before the pod received an address. **Next action:** Inspect pod events and the CNI agent logs on the affected node before testing traffic.

</details>

### Card B — Two hostNetwork pods can both listen on port 80 on the same node.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** Both processes share the node network namespace, so one cannot bind an address and port already in use. **Next action:** Inspect container status and logs, then change placement or the listening port.

</details>

### Card C — kube-proxy assigns Pod IPs.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** Pod address allocation belongs to the CNI and its IPAM path; kube-proxy handles Service traffic. **Next action:** Inspect pod events, CNI configuration, and IPAM evidence for the affected node.

</details>

### Card D — A NetworkPolicy is enforced even when the installed CNI does not implement it.

<details>
<summary>Reveal the failure layer and next action</summary>

**False. Failure layer:** The API can accept the policy while the dataplane provides no enforcement. **Next action:** Identify the installed CNI and verify policy support before relying on isolation or changing selectors.

</details>

**Success Criteria**:
- [ ] Can identify the installed CNI plugin and whether it runs as a DaemonSet.
- [ ] Can read pod CIDR, service CIDR, and node pod CIDR evidence without mixing their roles.
- [ ] Can verify pod-to-pod connectivity before testing service DNS.
- [ ] Can distinguish kube-proxy, CoreDNS, and CNI symptoms using targeted commands.
- [ ] Can explain why `hostNetwork: true` changes port ownership and DNS policy requirements.

---

## Learner check

> CNI provides the pod side of that promise.

---

## Sources

- [Kubernetes Cluster Networking](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [Kubernetes Virtual IPs and Service Proxies](https://kubernetes.io/docs/reference/networking/virtual-ips/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes Pod Hostnames and DNS Policy](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-s-dns-policy)
- [Kubernetes kube-proxy Configuration API](https://kubernetes.io/docs/reference/config-api/kube-proxy-config.v1alpha1/)
- [Kubernetes Blog: NFTables mode for kube-proxy](https://kubernetes.io/blog/2025/02/28/nftables-kube-proxy/)
- [Kubernetes kubeadm init](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-init/)
- [CNI Specification](https://github.com/containernetworking/cni/blob/main/SPEC.md)
- [Calico Kubernetes Networking Documentation](https://docs.tigera.io/calico/latest/networking/)
- [Cilium Kubernetes Networking Documentation](https://docs.cilium.io/en/stable/network/kubernetes/)
- [Flannel Documentation](https://github.com/flannel-io/flannel/blob/master/Documentation/kubernetes.md)

## Next Module

Continue to [Module 3.8: Cluster Networking Data Path](../module-3.8-cluster-networking-data-path/) to connect CNI behavior with packet flow, routing, NAT, and node-level forwarding.
