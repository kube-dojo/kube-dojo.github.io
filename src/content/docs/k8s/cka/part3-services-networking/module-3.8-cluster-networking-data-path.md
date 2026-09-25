---
citations_verified: true
title: "Module 3.8: Cluster Networking Data Path"
slug: k8s/cka/part3-services-networking/module-3.8-cluster-networking-data-path
sidebar:
  order: 9
revision_pending: false
lab:
  id: cka-3.8-cluster-networking
  url: https://killercoda.com/kubedojo/scenario/cka-3.8-cluster-networking
  duration: "40 min"
  difficulty: advanced
  environment: kubernetes
---

> **Complexity**: `[MEDIUM]` - Core troubleshooting topic
>
> **Time to Complete**: ~40 minutes
>
> **Prerequisites**: [Module 3.1 (Services)](../module-3.1-services/), [Module 3.6 (Network Policies)](../module-3.6-network-policies/), [Module 3.7 (CNI)](../module-3.7-cni/)

---

## Learning Outcomes

- **Trace** a request from a client pod through DNS, Service translation, conntrack, routing, and CNI delivery until it reaches a backend pod.
- **Differentiate** kube-proxy responsibilities from CNI responsibilities, then use that boundary to choose the correct diagnostic command instead of debugging the wrong layer.
- **Debug** cross-node and Service connectivity failures by comparing DNS results, Endpoints or EndpointSlices, iptables or nftables state, routes, tunnel interfaces, and packet captures.
- **Evaluate** overlay and native routing designs by explaining how encapsulation, MTU, routing complexity, source NAT, and policy enforcement change the data path.
- **Apply** a repeatable troubleshooting mental model to a concrete production-style failure before solving a similar packet-tracing challenge in the hands-on exercise.

---

## Why This Module Matters

At 03:00, a platform engineer gets paged because checkout requests are timing out between two Kubernetes workloads that were healthy one hour earlier. The Deployments are running, the Service object still exists, CoreDNS is not crash-looping, and the application logs only show generic connection timeouts. Nothing in the first screen of `kubectl get pods` says whether the failure is DNS, kube-proxy, NetworkPolicy, conntrack, node routing, or a CNI tunnel problem.

That situation is exactly where Kubernetes networking changes from a set of definitions into an operational skill. A learner who only remembers that Services have ClusterIPs will keep trying random commands, while a learner who can follow the packet can divide the problem into smaller tests. The question becomes: did the name resolve, did the Service select endpoints, did the node rewrite the destination, did conntrack preserve the return path, and did the CNI deliver the packet across nodes?

This module teaches the data path as a sequence of decisions made by Linux and Kubernetes components. You will see the simple path first, then add Service load balancing, DNS, NodePort source NAT, hairpin flows, overlay encapsulation, and troubleshooting state. The goal is not to memorize every implementation detail of every CNI; the goal is to build a mental model strong enough to predict where evidence should appear when something breaks.

Hypothetical scenario: During a cluster migration, a team moves from native routed pod networking to an overlay CNI mode. Small health checks keep passing, readiness stays green, and short API calls work, but larger responses from one service to another stall until the client times out. The broken requests are not random; they are the ones large enough to exceed the real path MTU after encapsulation overhead is added, so the evidence sits below the application and below the Service abstraction.

In that scenario, the fix would not begin in DNS or in the Deployment manifest. The platform team would compare pod MTU, tunnel MTU, and underlay MTU, then verify the data path with packet captures and direct pod-to-pod tests before changing CNI settings. Kubernetes 1.35 still depends on the same fundamental Linux packet path, so the practical skill is learning where each abstraction stops and where the next layer starts.

---

## Part 1: Build the Packet-Walk Mental Model

A Kubernetes Service hides backend pod churn behind one stable virtual IP, but the packet still travels through ordinary kernel machinery. The important first insight is that most packets are not handled by a long-running userspace proxy process. kube-proxy watches the Kubernetes API and programs rules, while the Linux networking stack applies those rules to packets as they move through the node.

Start with a client pod calling a ClusterIP Service. The client thinks it is connecting to the Service IP, but the backend pod receives a packet addressed to its own pod IP. That rewrite is destination NAT, usually called DNAT, and the connection-tracking table remembers enough state to make the reply look correct from the client side.

```ascii
+----------------------------------------------------------------------------+
|                  ClusterIP Packet Walk: client pod to backend pod           |
|                                                                            |
|  Node A                                      Node B                         |
|  +-------------------+                      +-------------------+           |
|  | Pod A             |                      | Pod B             |           |
|  | 10.244.1.5        |                      | 10.244.2.8        |           |
|  | curl 10.96.0.50   |                      | nginx :80         |           |
|  +---------+---------+                      +---------^---------+           |
|            |                                          |                     |
|            v                                          |                     |
|  +-------------------+                                |                     |
|  | veth pair         |                                |                     |
|  | pod netns to host |                                |                     |
|  +---------+---------+                                |                     |
|            |                                          |                     |
|            v                                          |                     |
|  +-------------------+    PREROUTING / Service rules  |                     |
|  | kube-proxy rules  |    10.96.0.50:80               |                     |
|  | in kernel tables  | -> 10.244.2.8:80               |                     |
|  +---------+---------+                                |                     |
|            |                                          |                     |
|            v                                          |                     |
|  +-------------------+    NAT mapping saved so the    |                     |
|  | conntrack         |    reply can be translated     |                     |
|  | flow state        |    back for the client         |                     |
|  +---------+---------+                                |                     |
|            |                                          |                     |
|            v                                          |                     |
|  +-------------------+    same node: local veth       |                     |
|  | route lookup      |    other node: CNI path        |                     |
|  +---------+---------+                                |                     |
|            | remote node                              |                     |
|            v                                          |                     |
|  +-------------------+        overlay or routed       |  +----------------+ |
|  | CNI delivery      +------------------------------->+  | CNI receive    | |
|  | tunnel or route   |                                |  | and decap      | |
|  +-------------------+                                |  +-------+--------+ |
|                                                       |          |          |
|                                                       +----------v----------+
|                                                                  v          |
|                                                        Backend pod receives |
|                                                        traffic on port 80   |
+----------------------------------------------------------------------------+
```

The packet leaves Pod A through a virtual Ethernet pair, usually called a veth pair, that connects the pod network namespace to the node network namespace. From there, the packet hits kernel hooks where kube-proxy-managed rules can match the destination Service IP. In iptables mode, this commonly involves [chains such as `KUBE-SERVICES`, `KUBE-SVC-*`, and `KUBE-SEP-*`](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/), although exact names depend on mode and implementation.

After the destination is rewritten to a backend pod IP, the node performs a normal route lookup. If the backend pod is local, the packet can be delivered through another veth pair on the same node. If the backend pod is remote, the CNI-provided data path decides whether to encapsulate the packet into a tunnel, forward it with native routing, or hand it to an eBPF program that performs equivalent forwarding work.

Conntrack is the piece that prevents the reply from surprising the client. Pod B replies to Pod A because Pod B saw Pod A as the source, not the Service IP. When the reply returns, conntrack recognizes it as part of the existing NATed flow and reverses the translation, so Pod A's socket still sees a response associated with the Service connection it opened.

**Pause and predict:** If Pod A connects to `10.96.0.50:80`, but Pod B sees the packet as destined for `10.244.2.8:80`, what would break if conntrack forgot the mapping before the reply returned? Write down whether the client would see a clean refusal, a timeout, or an unexpected source address before you read further.

<details>
<summary>Check your prediction</summary>

The most useful answer is that the symptom depends on exactly which state disappeared and how the stack handles the returning packet. In practice, stale or missing conntrack state often appears as a hang, a reset, or asymmetric traffic that makes one side believe the connection exists while the other cannot complete the flow. That is why conntrack belongs in the troubleshooting model rather than in a footnote.

</details>

Record the client symptom you expect, then compare that note with the backend view the next section describes. Keep the program that writes node rules separate from the kernel path that forwards each individual packet.

### 1.1 What kube-proxy Actually Does

Despite the name, kube-proxy usually does not sit in the middle of every Service packet as a userspace proxy. Its main job is to [watch Services and EndpointSlices, then program the node so the kernel can translate virtual Service traffic to real backend pod traffic](https://kubernetes.io/docs/reference/networking/virtual-ips/). The packet path is fast because the data packet stays in kernel space, but the correctness of that path depends on kube-proxy keeping rules synchronized with the API.

When a Service has two ready backend pods, kube-proxy creates rules or equivalent state that can choose either backend. In iptables mode, endpoint selection can be represented with probability matches and per-endpoint DNAT chains. In nftables mode, the representation changes, but the conceptual job remains the same: match the virtual Service destination, select an endpoint, rewrite the destination, and rely on conntrack for the return path.

```bash
# Check the kube-proxy mode configured for this cluster.
kubectl get configmap kube-proxy -n kube-system -o yaml | grep -E "mode:|strictARP|clusterCIDR"

# Inspect kube-proxy health and recent logs.
kubectl get pods -n kube-system -l k8s-app=kube-proxy -o wide
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=40
```

The command output is most useful when you connect it back to the symptom. If pod-to-pod traffic works by direct pod IP but Service traffic fails, kube-proxy state becomes a prime suspect. If both direct pod IP and Service traffic fail, kube-proxy might still be healthy, and the failure may sit lower in the CNI, policy, node firewall, or routing path.

### 1.2 NodePort Adds Source-NAT Decisions

NodePort begins outside the cluster, so the first packet arrives at a node IP and a high port rather than at a pod or ClusterIP directly. kube-proxy rules match the NodePort, translate it toward the Service and then a backend endpoint, and may also source-NAT the packet depending on the Service traffic policy. That source-NAT decision changes what the backend pod can see and how the reply returns.

```ascii
+----------------------------------------------------------------------------+
|                         NodePort Packet Walk                                |
|                                                                            |
|  External client                                                           |
|  +-------------------+                                                     |
|  | curl node:30080   |                                                     |
|  +---------+---------+                                                     |
|            |                                                               |
|            v                                                               |
|  +-------------------+       Node receives packet on node IP and NodePort   |
|  | node interface    |       before Kubernetes Service translation occurs   |
|  +---------+---------+                                                     |
|            |                                                               |
|            v                                                               |
|  +-------------------+       NodePort rule maps port to Service backend     |
|  | kube-proxy rules  |       and chooses one ready endpoint                 |
|  +---------+---------+                                                     |
|            |                                                               |
|            v                                                               |
|  +-------------------+       externalTrafficPolicy: Cluster may SNAT        |
|  | source NAT choice |       externalTrafficPolicy: Local preserves source  |
|  +---------+---------+                                                     |
|            |                                                               |
|            v                                                               |
|  +-------------------+       packet now follows the ClusterIP-style path    |
|  | CNI or local veth |       toward the chosen backend pod                  |
|  +-------------------+                                                     |
+----------------------------------------------------------------------------+
```

With `externalTrafficPolicy: Cluster`, Kubernetes can send the request to any ready endpoint in the cluster. The trade-off is that the backend commonly sees the node IP as the source because SNAT keeps the return path symmetric through the receiving node. This is simple and highly available, but it hides the original client IP unless another layer preserves it through headers or proxy protocol.

With `externalTrafficPolicy: Local`, Kubernetes [preserves the original client IP by only sending traffic to local endpoints on the node that received the packet](https://kubernetes.io/docs/tutorials/services/source-ip/). This is valuable for audit logs and client-aware applications, but it creates an operational condition: nodes without a local ready endpoint should not receive traffic for that Service. Cloud load balancer health checks and endpoint distribution therefore become part of the design.

| NodePort choice | What the backend sees | Operational trade-off | When it is usually chosen |
|---|---|---|---|
| `externalTrafficPolicy: Cluster` | Often the node IP because SNAT is used | More flexible backend selection but source IP may be hidden | General services that do not need client IP at the pod |
| `externalTrafficPolicy: Local` | The real external client IP | Requires local endpoints on receiving nodes | Ingress controllers, audit-sensitive apps, and source-aware workloads |
| LoadBalancer using NodePort | Depends on traffic policy and provider behavior | Adds cloud health checks and provider routing rules | Managed clusters where external traffic enters through cloud infrastructure |
| HostNetwork listener | The pod uses the node network namespace | Bypasses normal pod isolation assumptions | Specialized agents and low-level networking components |

### 1.3 Hairpin Traffic Is a Loop Back Through the Node

Hairpin traffic happens when a pod sends traffic to a Service and kube-proxy selects that same pod as the backend. From the application's perspective, this looks like a pod calling its own stable Service name. From the network perspective, the packet may need to leave the pod namespace, be DNATed, and then return through the same bridge or veth path back into the same pod.

```ascii
+----------------------------------------------------------------------------+
|                              Hairpin Flow                                  |
|                                                                            |
|  +----------------------+                                                  |
|  | Pod A                |                                                  |
|  | app curls web-svc    |                                                  |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | node Service rules   |  Service chooses Pod A itself as the endpoint     |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | bridge or veth path  |  hairpin mode must allow the frame to return      |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | Pod A receives the   |  successful loopback through the Service path      |
|  | request on app port  |                                                  |
|  +----------------------+                                                  |
+----------------------------------------------------------------------------+
```

Hairpin failures are confusing because the Service can work from other pods, and the application can work when called directly by pod IP. The broken case is specifically the loop where the selected endpoint is the caller. If your application calls itself through its Service name, a failing hairpin path can look like a Service outage even though most other clients are fine.

```bash
# Inspect the pod's network devices and routes from inside the pod.
kubectl exec <pod-name> -- ip link show
kubectl exec <pod-name> -- ip route

# On a node, hairpin settings are usually inspected through the veth or bridge path.
# The exact interface name depends on the CNI and runtime, so find it before reading.
cat /sys/devices/virtual/net/<veth-name>/brport/hairpin_mode
```

You should not start a troubleshooting session by assuming hairpin is the problem. Use it as a targeted branch when the symptom is narrow: a pod cannot reach its own Service, but other pods can reach the same Service, and direct access to the pod's application port works. That pattern gives you enough evidence to inspect bridge, veth, CNI, and [kubelet hairpin settings](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/).

---

## Part 2: Separate CNI, kube-proxy, DNS, and Policy Responsibilities

The fastest way to lose time in Kubernetes networking is to blame the wrong layer. kube-proxy does not create pod interfaces, CoreDNS does not choose Service endpoints, and [most CNIs do not implement the basic Service virtual IP rules unless they intentionally replace kube-proxy](https://kubernetes.io/docs/concepts/services-networking/). Your first diagnostic move should be to identify which responsibility is implicated by the symptom.

```ascii
+----------------------------------------------------------------------------+
|                    Responsibility Boundaries in the Data Path               |
|                                                                            |
|  +----------------------------+      +----------------------------+         |
|  | CNI plugin                 |      | kube-proxy or replacement   |         |
|  |                            |      |                            |         |
|  | Creates pod network path   |      | Implements Service VIPs    |         |
|  | Assigns and routes pod IPs |      | Chooses Service endpoints  |         |
|  | Builds veth and tunnels    |      | Programs DNAT and NodePort |         |
|  | May enforce NetworkPolicy  |      | Handles session affinity   |         |
|  | May use BGP, VXLAN, eBPF   |      | May use iptables/nft/eBPF  |         |
|  +----------------------------+      +----------------------------+         |
|                                                                            |
|  +----------------------------+      +----------------------------+         |
|  | CoreDNS                    |      | NetworkPolicy controller    |         |
|  |                            |      | and CNI enforcement         |         |
|  | Answers Service names      |      | Allows or denies pod flows  |         |
|  | Uses Service for its own IP|      | Often enforced by the CNI   |         |
|  | Forwards external queries  |      | Does not create endpoints   |         |
|  +----------------------------+      +----------------------------+         |
+----------------------------------------------------------------------------+
```

A good diagnostic question is not "is networking broken?" but "which promise is broken?" Kubernetes promises that pods can communicate with pods without NAT, Services can route to ready endpoints, pods can resolve Service DNS records, and policies can restrict selected traffic. Those are related promises, but they are not the same promise, and each one points to different evidence.

| Symptom observed from a client pod | Direct next test | Layer most implicated if the test fails | Why that layer becomes suspicious |
|---|---|---|---|
| Service name does not resolve | `kubectl exec client -- nslookup service` | DNS or CoreDNS reachability | The client cannot even obtain the virtual Service IP |
| Service name resolves but curl to Service fails | `kubectl get endpoints service` | Service selection or kube-proxy | DNS succeeded, so the failure moved past name resolution |
| ClusterIP fails but endpoint pod IP works | Check kube-proxy rules and logs | kube-proxy or Service state | Pod routing works while virtual IP translation does not |
| Endpoint pod IP fails across nodes | `kubectl exec client -- curl http://pod-ip` | CNI, policy, route, MTU, or node firewall | The Service abstraction is no longer involved |
| Same-node pod IP works but cross-node fails | Compare node placement and routes | CNI tunnel, BGP, firewall, or MTU | Local veth delivery works while inter-node delivery fails |
| DNS works but external names are slow | Inspect `/etc/resolv.conf` and query timing | resolver search behavior or CoreDNS upstreams | The network may work while name expansion causes latency |

### 2.1 Pod-to-Pod Traffic Is the CNI's Promise

The Kubernetes networking model [requires every pod to be able to reach every other pod without application-visible NAT](https://kubernetes.io/docs/concepts/services-networking/). Kubernetes itself does not configure that entire network. [The container runtime invokes CNI plugins when pods are created](https://kubernetes.io/docs/concepts/services-networking/), and the CNI plugin attaches interfaces, assigns addresses, installs routes, and prepares whatever node-level forwarding mechanism the implementation uses.

A direct pod-IP test is the cleanest way to ask whether the pod network itself works. If Pod A can reach Pod B by pod IP and port, the CNI has carried the flow far enough for the application to respond. If Pod A cannot reach Pod B by pod IP, debugging Service objects first usually wastes time because the failure is underneath the Service layer.

```bash
# Get backend pod IPs and node placement so you know whether the test crosses nodes.
kubectl get pods -o wide

# Test direct pod-to-pod connectivity from a client pod.
kubectl exec <client-pod> -- wget -qO- --timeout=5 http://<backend-pod-ip>:<port>

# Compare the direct test with the Service test.
kubectl exec <client-pod> -- wget -qO- --timeout=5 http://<service-name>:<port>
```

You should also check whether NetworkPolicy is intentionally changing the answer. [A policy-capable CNI may drop the direct pod-IP test because policy denies the flow](https://kubernetes.io/docs/concepts/services-networking/network-policies/), not because routing is broken. The symptom still lives in the CNI and policy layer, but the fix is different from changing tunnels or node routes.

### 2.2 Service Traffic Is the kube-proxy Promise

A Service object is only useful if it selects ready endpoints and every node has the rules needed to translate the Service virtual IP. Empty endpoints mean kube-proxy has nothing valid to route to, even when the Service object exists. Stale or missing node rules mean the Service may have endpoints in the API, while individual nodes cannot translate traffic correctly.

```bash
# Check whether the Service has a ClusterIP and which selector it uses.
kubectl get svc <service-name> -o wide
kubectl describe svc <service-name>

# Check [EndpointSlices because modern clusters use them as the scalable endpoint source](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/).
kubectl get endpointslice -l kubernetes.io/service-name=<service-name> -o wide

# The legacy Endpoints object is still a quick exam-friendly view in many clusters.
kubectl get endpoints <service-name>
```

If endpoints are empty, stay at the Kubernetes API level before inspecting iptables. Confirm the Service selector matches pod labels, the pods are in the same namespace as the Service, and the pods are Ready. [A pod can be Running and still excluded from endpoints because readiness failed](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/), which is one of the most common Service troubleshooting traps.

If endpoints are correct, move to node-level Service translation. On a kind node, you can inspect rules from the host through the node container. On a real node, you need node shell access with privileges appropriate to the cluster. The command changes with kube-proxy mode, but the question stays the same: did this node receive and program Service state?

```bash
# kind example: inspect Service-related kernel rules inside the control-plane node.
docker exec kind-control-plane iptables-save | grep <service-name>

# A generic node example when iptables mode is in use.
iptables-save | grep -E "KUBE-SVC|KUBE-SEP|<service-name>"

# For nftables mode, inspect the Kubernetes-related ruleset instead.
nft list ruleset | grep -i <service-name>
```

### 2.3 Overlay and Native Routing Change the Failure Modes

Overlay networking wraps the original pod packet inside another packet so the existing underlay network only needs to route between node IPs. This is convenient because it avoids teaching the physical network about pod CIDRs, but encapsulation adds overhead and creates tunnel-specific firewall and MTU concerns. VXLAN, Geneve, and IP-in-IP differ in details, yet they share the same operational theme: a packet can be healthy before encapsulation and too large or blocked after encapsulation.

Native routing avoids the overlay wrapper by making the network route pod CIDRs directly. That can improve performance and simplify MTU behavior, but it requires the node network, cloud routes, host gateways, or BGP peers to know how to reach pod CIDRs. Native routing failures therefore often look like ordinary routing failures rather than tunnel failures.

| Routing design | What the node sends across the network | Strength | Common failure mode |
|---|---|---|---|
| VXLAN overlay | UDP-encapsulated packet between node IPs | Works over many existing networks | MTU mismatch or blocked tunnel traffic |
| Geneve overlay | UDP-encapsulated packet with extensible metadata | Flexible for advanced data planes | Same encapsulation and firewall concerns as other overlays |
| IP-in-IP overlay | Pod IP packet wrapped in an outer IP packet | Simple routing over node IP reachability | Protocol filtering or MTU overhead |
| Native routing with BGP | Plain pod IP packet routed by the network | Strong performance and no tunnel overhead | Missing routes or broken BGP peering |
| Host-gateway routing | Plain pod IP packet through node gateways | Simple in flat L2 environments | Fails when nodes are not on a compatible network |
| eBPF data path | Program-dependent forwarding and translation | Can replace multiple kernel rule systems | Requires implementation-specific tools and observability |

Do not treat CNI names as complete explanations. [Calico can run in different modes](https://github.com/projectcalico/calico), [Cilium can use overlay or native routing and may replace kube-proxy](https://github.com/cilium/cilium), and [Flannel behavior depends on backend choice](https://github.com/flannel-io/flannel). Always inspect the actual configured mode before deciding which failure mode is plausible.

```bash
# Look at CNI pods and node placement.
kubectl get pods -n kube-system -o wide | grep -E "calico|cilium|flannel|weave|antrea"

# Inspect common tunnel interfaces on a node when your CNI uses overlays.
ip link show | grep -E "vxlan|flannel|cilium|geneve|tunl"

# Inspect pod and node routes when native routing or host-gateway behavior is expected.
ip route
```

> **Stop and decide**: A backend Service fails only when the client pod and backend pod are on different nodes. The same Service works when both pods land on the same node. Which layer should you investigate first, and what evidence would distinguish an MTU problem from a blocked tunnel or missing route?

The key is that same-node success proves the application, readiness, and local veth delivery can work. Cross-node failure moves suspicion to the inter-node path: encapsulation, native routes, cloud security rules, node firewall rules, or policy that differs by node placement. MTU problems often affect larger packets more than tiny probes, while blocked tunnel traffic or missing routes usually break even small cross-node requests.

---

## Part 3: DNS Is a Service Client Too

DNS in Kubernetes feels separate because users type names, but the DNS path is itself a Service path. A pod sends a DNS packet to the cluster DNS Service IP, kube-proxy or its replacement translates that packet to a CoreDNS endpoint, and CoreDNS returns a record. If the cluster Service data path is broken, DNS can fail even when CoreDNS pods are running.

```ascii
+----------------------------------------------------------------------------+
|                         DNS Resolution Path                                |
|                                                                            |
|  +----------------------+                                                  |
|  | Client pod           |                                                  |
|  | curl http://web-svc  |                                                  |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | /etc/resolv.conf     |  nameserver points at the CoreDNS ClusterIP       |
|  | search domains       |  search list expands short names                  |
|  | options ndots:5      |  resolver decides query order                     |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | DNS packet to        |  usually UDP or TCP port 53 toward Service IP     |
|  | kube-dns ClusterIP   |                                                  |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | Service translation  |  kube-proxy chooses a CoreDNS backend pod         |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  +----------------------+                                                  |
|  | CoreDNS pod          |  kubernetes plugin answers Service records        |
|  | returns A or AAAA    |  forward plugin handles external names            |
|  +----------+-----------+                                                  |
|             |                                                              |
|             v                                                              |
|  Client connects to the returned Service IP, then Part 1 begins again       |
+----------------------------------------------------------------------------+
```

The most important DNS troubleshooting split is between "the name did not resolve" and "the name resolved but the connection failed." If `nslookup trace-svc` returns the correct ClusterIP, DNS has done its job for that name. A later `curl` failure must be tested through Service endpoints, kube-proxy translation, policy, CNI routing, or the application.

```bash
# Inspect the resolver configuration as the pod actually sees it.
kubectl exec <client-pod> -- cat /etc/resolv.conf

# Resolve a short Service name from inside the pod.
kubectl exec <client-pod> -- nslookup <service-name>

# Resolve the fully qualified Service name to remove namespace ambiguity.
kubectl exec <client-pod> -- nslookup <service-name>.<namespace>.svc.cluster.local

# Check CoreDNS pods and logs if resolution itself fails.
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=60
```

### 3.1 Search Domains and ndots Can Create Latency

Kubernetes pods commonly [receive a search list and `ndots:5`](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/), which means a name with fewer than five dots is tried through search domains before the absolute name is queried. This is helpful for short in-cluster names such as `web`, but it can hurt workloads that mostly call external domains. A name like `api.example.com` may generate several failed cluster-local queries before the real absolute query succeeds.

```bash
# Observe resolver configuration inside a pod.
kubectl exec <client-pod> -- cat /etc/resolv.conf

# Compare an external name without and with a trailing dot.
kubectl exec <client-pod> -- nslookup api.example.com
kubectl exec <client-pod> -- nslookup api.example.com.
```

[A trailing dot tells the resolver that the name is absolute](https://www.rfc-editor.org/rfc/rfc1034), so it should not be expanded through the search list. For application configuration that repeatedly calls external services, a trailing dot or a lower `ndots` value can remove avoidable DNS work. The right choice depends on whether the workload primarily calls cluster-local Services, external names, or both.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: dns-optimized-client
spec:
  dnsConfig:
    options:
    - name: ndots
      value: "2"
  containers:
  - name: client
    image: busybox:1.36
    command:
    - sleep
    - "3600"
```

| DNS symptom | Evidence to collect | Likely cause | Next action |
|---|---|---|---|
| All Service names fail | `nslookup kubernetes.default` fails | CoreDNS unavailable or DNS Service path broken | Check CoreDNS pods, kube-dns Service, and kube-proxy rules |
| External names fail but Service names work | Cluster-local lookup succeeds, external lookup fails | CoreDNS upstream forwarding or node DNS issue | Inspect CoreDNS ConfigMap and upstream reachability |
| Short external names are slow | Multiple search-domain attempts appear before success | `ndots` and search expansion overhead | Use trailing dots or tune `dnsConfig` for that workload |
| Cross-namespace Service name fails | FQDN works but short name does not | Namespace search list mismatch | Use `service.namespace.svc.cluster.local` |
| DNS succeeds but curl fails | `nslookup` returns expected ClusterIP | Service, policy, CNI, or app issue | Move to endpoint and data-path checks |
| Intermittent DNS timeouts | CoreDNS logs show delays or timeouts | overload, policy, or upstream instability | Check CoreDNS resources, policies, and upstream DNS |

### 3.2 DNS Depends on NetworkPolicy Too

CoreDNS is just another set of pods behind a Service, so policies can block DNS traffic if they select clients too broadly. A default-deny egress policy that forgets to allow UDP and TCP DNS traffic to kube-system can make applications appear broken even though their Service and pod network paths are otherwise healthy. This is why DNS checks belong at the top of the troubleshooting model.

When DNS is blocked by policy, direct pod-IP tests may still work if the policy allows those flows or if the test bypasses the denied DNS step. That can mislead teams into saying "networking works" while applications still fail because they use names. Always separate name resolution from transport connectivity when policy is involved.

```bash
# Look for policies in both the client namespace and kube-system.
kubectl get networkpolicy -A

# Test DNS and direct connectivity separately.
kubectl exec <client-pod> -- nslookup kubernetes.default
kubectl exec <client-pod> -- wget -qO- --timeout=5 http://<backend-pod-ip>:<port>
```

---

## Part 4: A Troubleshooting Mental Model You Can Apply

A useful troubleshooting model must reduce guessing, not add ceremony. The model in this module starts at the name, moves to the Service, then moves to direct endpoint reachability, and finally inspects node-level state when the simple tests isolate the failing layer. You should be able to stop early when evidence identifies the problem, and you should be able to go deeper when the symptom remains ambiguous.

```ascii
+----------------------------------------------------------------------------+
|                  Three-Layer Diagnosis for Service Failures                |
|                                                                            |
|  Symptom: client pod cannot reach a Service by name                         |
|            |                                                               |
|            v                                                               |
|  +-------------------------------+                                         |
|  | Layer 1: DNS                  |                                         |
|  | Does the name resolve?        |                                         |
|  | nslookup service.namespace    |                                         |
|  +-----------+-------------------+                                         |
|      no      | yes                                                         |
|      v       v                                                             |
|  Check CoreDNS, resolver,        +-------------------------------------+   |
|  DNS policy, and kube-dns        | Layer 2: Service selection          |   |
|  Service translation             | Does the Service have ready endpoints? |
|                                  | endpointslice or endpoints          |   |
|                                  +-----------+-------------------------+   |
|                                      no      | yes                         |
|                                      v       v                             |
|                         Check selector,     +--------------------------+   |
|                         namespace, labels,  | Layer 3: Endpoint reach  |   |
|                         readiness probes    | Can client reach pod IP? |   |
|                                             | curl endpoint IP and port|   |
|                                             +-----------+--------------+   |
|                                                 no      | yes              |
|                                                 v       v                  |
|                                      CNI, policy,       Service translation,|
|                                      route, MTU,        app listener, or    |
|                                      node firewall      conntrack branch    |
+----------------------------------------------------------------------------+
```

The model begins with DNS because applications usually use names, and a failed name lookup prevents the rest of the connection from starting. The next branch checks whether the Service has valid ready endpoints, because an empty endpoint set is not a packet-forwarding mystery. Only after those tests pass should you invest time in iptables, nftables, eBPF tooling, conntrack, route tables, MTU, or packet captures.

This approach also protects you from exam-time command thrashing. On the CKA, you rarely have unlimited time to inspect every layer. A short sequence of discriminating tests is better than a long list of commands, because each result tells you what to do next and what to ignore.

### 4.1 The Minimum Useful Command Sequence

The minimum sequence gathers one fact per layer. You can run it from a debug pod or from an existing client pod, depending on what the scenario allows. The key is to record each answer before moving deeper, because skipped observations are how teams end up debugging CoreDNS for a Service selector problem.

```bash
# Layer 1: Does the client resolve the intended Service name?
kubectl exec <client-pod> -- nslookup <service-name>.<namespace>.svc.cluster.local

# Layer 2: Does the Service point to ready endpoints?
kubectl get svc <service-name> -n <namespace> -o wide
kubectl get endpointslice -n <namespace> -l kubernetes.io/service-name=<service-name> -o wide

# Layer 3: Can the client reach a selected endpoint by pod IP?
kubectl exec <client-pod> -- wget -qO- --timeout=5 http://<endpoint-pod-ip>:<port>

# Node state: inspect translation and connection state only after the layer tests justify it.
iptables-save | grep -E "KUBE-SVC|KUBE-SEP|<service-name>"
conntrack -L -d <service-cluster-ip> 2>/dev/null
```

If the direct endpoint test succeeds but the ClusterIP test fails, the evidence points toward Service translation or connection state. If the direct endpoint test fails and the endpoint pod is on another node, inspect CNI health, policy, routes, tunnels, and node firewalls. If the direct endpoint test fails on the same node, policy or the application listener becomes more likely than an inter-node tunnel issue.

### 4.2 Worked Example: Checkout Cannot Reach Inventory

A worked example makes the mental model concrete before you solve a similar problem yourself. Imagine a production namespace called `shop` with a `checkout` client and an `inventory` backend. Developers report that `checkout` times out when calling `http://inventory:8080`, but only after a rollout that changed readiness probes and added a NetworkPolicy.

The wrong approach is to start by changing the CNI or restarting CoreDNS. The disciplined approach is to follow the path. First, test DNS from the client. If DNS returns the Service IP, name resolution is not the current blocker. If DNS fails, stop and inspect CoreDNS, resolver configuration, and DNS egress policy before touching endpoints.

```bash
# Step 1: Test name resolution from the failing client context.
kubectl exec -n shop deploy/checkout -- nslookup inventory.shop.svc.cluster.local
```

Assume the lookup returns `10.96.88.20`. That means the client can resolve the Service name, and CoreDNS plus the DNS Service path worked for this query. The next question is whether the Service has ready endpoints. A Service with no endpoints will accept a name lookup but has no backend destination for kube-proxy to choose.

```bash
# Step 2: Inspect Service selection and ready endpoints.
kubectl get svc -n shop inventory -o wide
kubectl get endpointslice -n shop -l kubernetes.io/service-name=inventory -o wide
kubectl get pods -n shop -l app=inventory -o wide
```

Assume the EndpointSlice shows no ready endpoints, while `kubectl get pods` shows two `inventory` pods in Running state with `0/1 READY`. That evidence changes the diagnosis. The failure is not a CNI tunnel, not kube-proxy, and not DNS; the Service has no ready backends because readiness is failing. You would inspect the readiness probe, pod logs, and application port rather than node packet forwarding.

```bash
# Step 3: Confirm why the pods are excluded from endpoints.
kubectl describe pod -n shop -l app=inventory
kubectl logs -n shop -l app=inventory --tail=80
```

Now change the scenario slightly. Assume the EndpointSlice shows two ready endpoints, and one endpoint IP is `10.244.3.22`. The Service has backends, so the next test is direct endpoint reachability from the client. This removes Service translation from the test and asks whether the pod network and policy allow the flow.

```bash
# Step 4: Test direct endpoint reachability.
kubectl exec -n shop deploy/checkout -- wget -qO- --timeout=5 http://10.244.3.22:8080
```

If direct pod-IP access fails, inspect NetworkPolicy before assuming routing is broken, because the rollout added policy. A default-deny ingress policy selecting `inventory` may allow traffic from an old label such as `role=frontend`, while the `checkout` pods now use `app=checkout` and no longer match the allow rule. That is a data-path failure, but the fix is policy alignment rather than CNI repair.

```bash
# Step 5: Inspect policies that select either side of the flow.
kubectl get networkpolicy -n shop
kubectl describe networkpolicy -n shop
kubectl get pods -n shop --show-labels
```

If direct pod-IP access succeeds but the Service still times out, inspect Service translation and conntrack. The endpoint can respond, so the lower pod network is capable of carrying the flow. The remaining suspects are kube-proxy rules, stale conntrack state, a mismatch between Service port and targetPort, or a local node-specific programming issue.

```bash
# Step 6: Compare Service port configuration with the backend container port.
kubectl describe svc -n shop inventory
kubectl get pods -n shop -l app=inventory -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.podIP}{"\n"}{end}'

# Step 7: On the node, inspect translation and connection state when justified.
iptables-save | grep inventory
conntrack -L -d 10.96.88.20 2>/dev/null
```

This example demonstrates the habit you should copy in the exercise. Each command answers one question and narrows the branch. The method works because it respects the packet path: name resolution, Service selection, Service translation, endpoint reachability, policy, and node state are related but separable.

> **What would happen if** the `inventory` Service selected the right pods, but its `targetPort` pointed to `9090` while the application listened on `8080`? Decide whether DNS, EndpointSlices, direct pod-IP access to `8080`, and Service access to `8080` would each succeed or fail.

The expected pattern is subtle. DNS can succeed because the Service exists. EndpointSlices can show ready endpoints because readiness may test a different path or port. Direct pod-IP access to `8080` can succeed because the application listens there. Service access to the Service port can fail because kube-proxy DNATs to the wrong target port, which is why Service port and targetPort deserve inspection when endpoint reachability and Service reachability disagree.

### 4.3 Conntrack Is Hidden State, Not Magic

Conntrack records flow state so NAT can be reversed correctly and packets can be recognized as part of an existing connection. That state is essential, but it can create confusing failures during backend churn, policy changes, or node pressure. New connections may work while old connections hang because they are attached to different conntrack entries.

```bash
# Count current conntrack entries on a node.
conntrack -C

# Inspect entries for a specific Service IP when debugging NAT behavior.
conntrack -L -d <service-cluster-ip> 2>/dev/null

# Delete only targeted stale entries when you understand the impact.
conntrack -D -d <service-cluster-ip> -p tcp --dport <service-port>
```

Be careful with broad conntrack deletion in production. Clearing too much state can break active connections for unrelated workloads and create a new incident while you are trying to solve the old one. In a learning environment, targeted deletion is useful because it shows how Service NAT depends on state, but in production it should be paired with incident context and change control.

### 4.4 Packet Captures Confirm the Story

Packet captures are not the first command you run, but they are excellent when layer tests disagree or when you need proof. A capture can show whether the SYN leaves the client pod, whether the node rewrites the destination, whether a packet crosses a tunnel, and whether a reply returns. The trick is to capture at a point that matches your question.

If you capture only inside the client pod, you see what the application sees before Service DNAT. If you capture on the node with `-i any`, you may see both pre-translation and post-translation views, depending on hook and interface timing. If you capture on a tunnel interface, you can test whether traffic enters the overlay path. None of these views is universally best; each answers a different question.

```bash
# From a debug pod, generate a request with a short timeout.
kubectl exec <client-pod> -- curl -sS --connect-timeout 5 http://<service-name>:<port>

# On a node, capture packets related to a client and backend test.
tcpdump -i any -nn host <client-pod-ip> and port <port>

# For DNS specifically, capture DNS packets rather than app packets.
tcpdump -i any -nn port 53 and host <client-pod-ip>
```

A capture is strongest when paired with a prediction. Before starting tcpdump, write down what you expect to see if DNS is broken, if Service DNAT is broken, if policy drops the endpoint flow, or if the backend application is not listening. Then compare the capture to your prediction. That habit turns tcpdump from a wall of packets into evidence.

---

## Part 5: Cross-Node Failures, MTU, and Source Identity

Cross-node failures deserve their own section because they often pass basic same-node tests. Kubernetes scheduling can hide these failures until a rollout moves pods onto different nodes. A Service may appear flaky only because some client-backend pairs are local and others cross the node network.

The first cross-node question is whether the failure is size-dependent. If tiny requests work and larger responses hang, suspect MTU before suspecting random application behavior. Encapsulation consumes bytes for outer headers, so the pod interface MTU must account for the smaller effective path. If the packet cannot be fragmented or fragmentation is blocked, large packets can disappear in ways that look like timeouts.

```bash
# Check pod interface MTU from inside a pod.
kubectl exec <pod-name> -- ip link show eth0

# Check common node interfaces and tunnel devices.
ip link show
ip link show | grep -E "mtu|vxlan|geneve|tunl|flannel|cilium"
```

The second question is whether the underlay network permits the CNI traffic. Overlay modes need node-to-node traffic for the encapsulation protocol, while native routing needs the network to know pod CIDR routes. Cloud security groups, node firewalls, host firewalls, and physical network ACLs can all break an otherwise correct Kubernetes configuration.

The third question is whether source identity changed. NodePort and LoadBalancer traffic may be source-NATed, and NetworkPolicy matches pod labels and namespaces rather than external client identity. A backend that suddenly sees node IPs instead of client IPs may not have a routing failure at all; it may have a traffic policy or ingress design issue.

| Cross-node clue | Most useful next check | Why it matters | Common repair direction |
|---|---|---|---|
| Same-node works, cross-node fails | Compare pod node placement with `kubectl get pods -o wide` | Confirms the node boundary is the variable | Inspect CNI health, routes, firewalls, and tunnels |
| Small responses work, large responses fail | Compare MTU on pod and tunnel interfaces | Encapsulation can reduce usable packet size | Tune CNI MTU and restart networking agents safely |
| NodePort backend sees node IP | Inspect `externalTrafficPolicy` | SNAT may be expected behavior | Use `Local` only when endpoint placement supports it |
| Only one node fails Service traffic | Inspect kube-proxy and CNI agent on that node | Node-local rule programming may be stale | Restart or repair the affected node agent after diagnosis |
| Direct pod IP fails only one way | Capture both directions and inspect policy | Asymmetric policy or routes can break replies | Fix return path, policy selection, or route advertisement |
| DNS times out only on some nodes | Check CoreDNS endpoint placement and node path | DNS is also a Service flow | Compare kube-dns Service translation and pod reachability |

You should now have a complete enough model to troubleshoot without memorizing every plugin implementation. Start by proving where the packet path stops matching expectation. Then choose the tool that sees that part of the path, whether it is `nslookup`, EndpointSlices, kube-proxy rules, `conntrack`, routes, interface MTU, CNI-specific status commands, or packet captures.

---

## Patterns & Anti-Patterns

Good Kubernetes network troubleshooting looks disciplined because each test removes a branch from the search tree. The strongest pattern is to keep the control-plane promise separate from the data-plane evidence: DNS answers names, Services select ready endpoints, kube-proxy or an eBPF replacement translates virtual IPs, and the CNI moves pod packets. When those responsibilities stay separate in your notes, you are less likely to restart CoreDNS for a Service selector problem or change CNI settings for an empty EndpointSlice.

The second useful pattern is to compare two paths that differ by exactly one layer. A Service call and a direct endpoint-pod call differ mainly by Service translation; a same-node direct pod call and a cross-node direct pod call differ mainly by the inter-node CNI path; a short external DNS query and the same name with a trailing dot differ by resolver search expansion. This kind of paired comparison is how experienced engineers turn a vague timeout into a specific next command.

| Pattern | When to use it | Why it works | Scaling consideration |
|---|---|---|---|
| Layered packet walk | Any Service or pod connectivity incident | It separates DNS, Service selection, translation, policy, CNI, and application behavior | Standardize the sequence in runbooks so teams collect comparable evidence |
| Paired path comparison | Symptoms differ by node placement, name form, or Service versus pod IP | It isolates the one layer that changed between tests | Record pod IPs, node names, and endpoint readiness so comparisons are reproducible |
| Endpoint-first Service debugging | A Service exists but traffic fails | It proves whether kube-proxy has real backends to translate toward | Prefer EndpointSlices in large clusters because they are the scalable endpoint API |
| Targeted node-state inspection | Evidence points to one node or one Service VIP | It avoids broad packet captures and broad conntrack deletion | Scope inspection to one node, one Service IP, and one port before changing state |

Anti-patterns usually come from treating "networking" as one large component. Restarting every networking pod may briefly hide the symptom, but it destroys evidence and can create a wider outage. A better response is to use the smallest test that can disprove a hypothesis, then move one layer deeper only when the previous layer behaves as expected.

| Anti-pattern | What goes wrong | Better alternative |
|---|---|---|
| Restarting CoreDNS whenever a Service name fails | DNS may be healthy while kube-dns Service translation, egress policy, or the backend Service path is broken | Test `nslookup`, kube-dns endpoints, and DNS egress policy separately before restarting anything |
| Treating direct pod-IP failure as a kube-proxy bug | kube-proxy is not responsible for creating pod interfaces or inter-node pod routing | Debug CNI health, NetworkPolicy, routes, MTU, and node firewalls when direct endpoint reachability fails |
| Clearing all conntrack entries to "unstick" a Service | Active unrelated flows can be interrupted, and the original cause remains unknown | Inspect targeted entries for the Service IP and delete only scoped entries in controlled situations |
| Assuming overlay and native routed clusters fail the same way | Encapsulation, MTU, firewall rules, route distribution, and observability tools differ | Evaluate the configured CNI mode before choosing MTU, route, or tunnel checks |

## Decision Framework

Use this framework when a client pod cannot reach a backend by Service name. Read it from top to bottom and stop as soon as the evidence identifies a layer. If a later command seems tempting, ask whether the earlier layer has already been proven healthy; that habit keeps the workflow fast during an exam and defensible during an incident.

```ascii
+----------------------------------------------------------------------------+
|                    Service Connectivity Decision Framework                  |
|                                                                            |
|  1. Resolve name from client pod                                            |
|     fails -> inspect resolver config, DNS policy, kube-dns Service, CoreDNS |
|     works -> record the returned ClusterIP and continue                     |
|                                                                            |
|  2. Inspect Service and EndpointSlices                                      |
|     empty -> fix selector, namespace, readiness, or target workload health  |
|     ready -> compare Service access with direct endpoint access             |
|                                                                            |
|  3. Compare Service call with endpoint pod-IP call                          |
|     endpoint fails -> inspect NetworkPolicy, CNI, routes, MTU, node path    |
|     endpoint works -> inspect Service port, kube-proxy or eBPF translation  |
|                                                                            |
|  4. Add node context only after the layer tests justify it                  |
|     one node bad -> inspect that node's agent, rules, routes, conntrack     |
|     cross-node bad -> inspect tunnel, BGP, firewall, or MTU evidence        |
+----------------------------------------------------------------------------+
```

| Decision point | Evidence that moves you forward | Most likely next tool | What not to do yet |
|---|---|---|---|
| DNS resolution fails | The client cannot obtain the expected ClusterIP | `kubectl exec -- nslookup`, CoreDNS logs, DNS policy review | Do not inspect application logs as the primary path evidence |
| EndpointSlices are empty | Service has no ready backend addresses | `kubectl describe svc`, `kubectl get pods --show-labels`, readiness events | Do not debug iptables for a Service with no endpoints |
| Direct endpoint access fails | Pod network path or policy fails without Service translation | NetworkPolicy review, CNI status, route and MTU checks, packet capture | Do not assume kube-proxy is broken |
| Direct endpoint works but Service fails | Lower pod reachability is proven, but virtual IP translation is suspicious | Service port review, kube-proxy logs, nftables or iptables, conntrack | Do not change CNI MTU before proving cross-node size symptoms |
| Only larger cross-node payloads fail | Tiny probes succeed while larger flows time out | MTU comparison and controlled packet-size tests | Do not treat the application timeout as random without size evidence |

## Did You Know?

- **kube-proxy usually programs the data path rather than carrying data packets itself.** In common Linux modes, kube-proxy watches Services and EndpointSlices, writes kernel rules or equivalent state, and lets the kernel forward matching packets.

- **DNS lookups for Kubernetes Services are themselves Service traffic.** A pod usually sends DNS queries to the kube-dns ClusterIP, which means broken Service translation can appear as a DNS outage even when CoreDNS pods are healthy.

- **Overlay encapsulation changes the usable packet size.** A path that worked with native routing can start dropping larger payloads after overlay mode is enabled if pod MTU and tunnel overhead are not planned together.

- **A Running pod is not automatically a Service endpoint.** Services route only to ready endpoints, so a readiness probe failure can create an empty endpoint set even when every selected pod appears to be alive.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Starting with tcpdump before checking DNS and endpoints | Packet captures become noisy when the failing layer has not been narrowed | First test name resolution, Service endpoints, and direct pod-IP reachability |
| Treating kube-proxy as the component that creates pod networking | The wrong owner gets investigated when direct pod IP traffic fails | Use direct pod-IP tests to separate CNI reachability from Service translation |
| Assuming a Running backend pod is eligible for Service traffic | Readiness failures remove pods from EndpointSlices even while containers run | Check EndpointSlices, readiness state, and Service selectors together |
| Ignoring NetworkPolicy during direct pod-IP tests | A denied flow can look like a broken route or tunnel | Inspect policies selecting the client namespace and backend pods before changing CNI settings |
| Forgetting that DNS uses the Service path | CoreDNS pods may be healthy while the kube-dns ClusterIP cannot be reached | Test CoreDNS pod health and kube-dns Service translation separately |
| Missing MTU after enabling overlay networking | Small probes pass while larger responses stall or time out | Compare pod MTU, tunnel MTU, and underlay MTU whenever encapsulation changes |
| Clearing all conntrack state during an incident | Broad deletion disrupts unrelated active connections | Inspect and delete only targeted entries when stale NAT state is strongly indicated |
| Using `externalTrafficPolicy: Local` without endpoint-aware load balancing | Nodes with no local ready endpoint drop traffic while preserving source IP | Pair `Local` with health checks and scheduling that keep endpoints on receiving nodes |

---

## Quiz

**1. Your team reports that `checkout` cannot call `http://inventory`, but `kubectl exec checkout -- nslookup inventory` returns the expected ClusterIP. The Service has two ready EndpointSlices, and direct `wget` to one endpoint pod IP succeeds from the checkout pod. What layer is now most suspicious, and what would you inspect next?**

<details>
<summary>Answer</summary>

The strongest suspicion is the Service translation path or Service port configuration, not DNS and not basic CNI reachability. DNS resolved the name, EndpointSlices contain ready backends, and direct pod-IP access from the client proves the pod network can reach at least one backend. Inspect the Service port and `targetPort`, kube-proxy health on the client node, node Service rules such as iptables or nftables, and targeted conntrack entries for the Service ClusterIP.

</details>

**2. A cluster moves from native routed pod networking to an overlay mode. Same-node requests still work, cross-node requests with small payloads work, but cross-node requests with larger JSON responses time out. What is the likely mechanism, and how should the platform team validate it before changing configuration?**

<details>
<summary>Answer</summary>

The likely mechanism is an MTU mismatch caused by encapsulation overhead. Same-node traffic does not use the inter-node tunnel, and small packets may fit even when the effective path MTU is too high for larger responses. The team should compare pod interface MTU, tunnel interface MTU, and underlay MTU, then use controlled packet-size tests or packet captures to confirm large packets disappear on the cross-node path. After confirmation, tune the CNI MTU according to the chosen overlay mode and roll the networking agents in a controlled way.

</details>

**3. A developer creates a Service for `reports`, and DNS returns a ClusterIP, but `kubectl get endpoints reports` shows no addresses. The selected pods are Running and have the expected labels. What should you evaluate before inspecting kube-proxy rules?**

<details>
<summary>Answer</summary>

Evaluate readiness and namespace alignment before inspecting kube-proxy rules. Running pods are not added to EndpointSlices unless they are Ready, so a failing readiness probe can leave the Service with no usable backends. Also confirm the Service and pods are in the same namespace, and compare the exact selector with `kubectl describe svc reports` and `kubectl get pods --show-labels`. kube-proxy cannot route a Service to endpoints that the Kubernetes API does not mark ready.

</details>

**4. An ingress controller Service uses `externalTrafficPolicy: Local` to preserve client IPs. After a rollout, some nodes still receive load balancer traffic but have no local ingress pods, and clients see intermittent failures. Why does this happen, and what design change would you recommend?**

<details>
<summary>Answer</summary>

With `externalTrafficPolicy: Local`, a node should only forward external traffic to local ready endpoints. If a load balancer sends traffic to a node without a local endpoint, the node cannot preserve source IP and forward to a remote backend in the normal `Local` model, so the connection can fail. The design should pair `Local` with load balancer health checks that only target nodes with local endpoints, or schedule ingress pods so every receiving node has a ready local endpoint. If client IP preservation is not required, `Cluster` may be simpler.

</details>

**5. A namespace has a default-deny egress NetworkPolicy. Applications can connect to backend pod IPs allowed by policy, but all calls using Service names fail before the TCP connection starts. What specific dependency did the policy probably forget, and how would you prove it?**

<details>
<summary>Answer</summary>

The policy probably forgot to allow DNS egress to CoreDNS, usually UDP and TCP port 53 toward the kube-system DNS pods or kube-dns Service path, depending on how the policy is written. Prove it by running `nslookup kubernetes.default` or a Service FQDN from an affected pod, checking `/etc/resolv.conf` for the nameserver, and reviewing policies that select the client pod. If direct pod-IP connectivity works but name resolution fails, the failure is in DNS reachability rather than the backend Service itself.

</details>

**6. A Service works from pods on Node A but fails from pods on Node B. The EndpointSlices are correct, and direct pod-IP tests from Node B clients to remote backends fail, while direct tests to same-node backends succeed. What evidence would you collect next, and why?**

<details>
<summary>Answer</summary>

Collect node placement, CNI agent health on Node B, routes, tunnel interfaces, node firewall rules, and packet captures at the node boundary. Same-node success proves local pod networking and the application can work, while remote direct pod-IP failure points below kube-proxy toward the inter-node CNI path or policy. The useful evidence is whether packets leave Node B, whether they enter the expected tunnel or route, whether return traffic arrives, and whether any policy or firewall denies the cross-node flow.

</details>

**7. After a backend rollout, new connections through a Service succeed, but a subset of long-lived client connections hang until they reconnect. The pods are ready, DNS is fine, and the Service has endpoints. What hidden state might explain the difference between new and old connections?**

<details>
<summary>Answer</summary>

Conntrack state may explain the difference. Existing flows can remain attached to old NAT mappings while new flows receive fresh endpoint selection and fresh connection-tracking entries. The right investigation is to inspect targeted conntrack entries for the Service ClusterIP and port, correlate the affected clients with rollout timing, and use graceful termination or connection draining to reduce stale-flow impact. Targeted conntrack deletion can help in a lab or controlled incident, but broad deletion can disrupt unrelated connections.

</details>

---

## Hands-On Exercise: Packet Trace Challenge

**Objective**: Trace a request from a client pod through DNS, Service selection, Service translation, conntrack, and pod delivery. You will use the troubleshooting model from Part 4 before using lower-level tools, so the exercise practices the same sequence the module teaches.

**Environment**: A kind or minikube cluster is enough for the main exercise. A multi-node cluster is better for the optional cross-node observations, but the required steps work on a single-node development cluster.

### Setup

Create a backend Deployment, expose it with a Service, and create a long-running debug pod. The debug image includes tools that are more convenient than a minimal application image, which keeps the exercise focused on the data path rather than package installation.

```bash
# Create a backend deployment and expose it with a ClusterIP Service.
kubectl create deployment trace-backend --image=nginx --replicas=2
kubectl expose deployment trace-backend --port=80 --name=trace-svc

# Wait until both backend pods are ready and therefore eligible as endpoints.
kubectl wait --for=condition=ready pod -l app=trace-backend --timeout=90s

# Create a debug client with networking tools.
kubectl run trace-client --image=nicolaka/netshoot --restart=Never -- sleep 3600
kubectl wait --for=condition=ready pod/trace-client --timeout=90s

# Capture the objects you will inspect throughout the exercise.
kubectl get pods -o wide
kubectl get svc trace-svc -o wide
kubectl get endpointslice -l kubernetes.io/service-name=trace-svc -o wide
```

### Step 1: Test DNS Before Transport

Start at the name because real applications usually start there. Resolve the short name, then resolve the fully qualified name, and compare the result with the Service ClusterIP. If these values disagree, stop and fix the DNS or namespace issue before continuing.

```bash
# Inspect resolver settings inside the client pod.
kubectl exec trace-client -- cat /etc/resolv.conf

# Resolve the short Service name from the default namespace.
kubectl exec trace-client -- nslookup trace-svc

# Resolve the fully qualified name to remove search-domain ambiguity.
kubectl exec trace-client -- nslookup trace-svc.default.svc.cluster.local

# Compare against the Service ClusterIP.
kubectl get svc trace-svc -o jsonpath='{.spec.clusterIP}{"\n"}'
```

Record the Service ClusterIP and write one sentence explaining whether DNS succeeded. A correct answer should separate DNS resolution from application connectivity, because a successful lookup does not prove the Service path or backend application works.

### Step 2: Verify Service Selection

Now check whether the Service has ready endpoints. The number of endpoint addresses should match the number of ready backend pods, not merely the number of created replicas. If the Service has no endpoints, inspect labels and readiness before touching kube-proxy or CNI configuration.

```bash
# Show Service selector and ports.
kubectl describe svc trace-svc

# Show endpoint addresses selected by the Service.
kubectl get endpoints trace-svc
kubectl get endpointslice -l kubernetes.io/service-name=trace-svc -o wide

# Show backend readiness, labels, pod IPs, and node placement.
kubectl get pods -l app=trace-backend -o wide --show-labels
```

Record how many endpoint addresses exist and which backend pod IPs they represent. Then explain whether a request through the Service should have a valid backend target according to the Kubernetes API state.

### Step 3: Compare Service Access With Direct Endpoint Access

This step isolates Service translation from direct pod reachability. First call the Service by name, then call one endpoint pod IP directly. If both work, the basic path is healthy. If direct endpoint access works but Service access fails, inspect Service translation. If direct endpoint access fails, inspect policy, CNI, route, or the backend application.

```bash
# Call the Service by name from the client pod.
kubectl exec trace-client -- curl -sS --connect-timeout 5 http://trace-svc

# Pick one endpoint IP and call it directly.
ENDPOINT_IP="$(kubectl get pod -l app=trace-backend -o jsonpath='{.items[0].status.podIP}')"
kubectl exec trace-client -- curl -sS --connect-timeout 5 "http://${ENDPOINT_IP}"
```

Write down the result of both calls. Your explanation should identify which layer would be most suspicious if the Service call failed while the endpoint call succeeded, and which layer would be most suspicious if both calls failed.

### Step 4: Inspect Service Translation on the Node

Use node-level inspection only after you have proven the Service and endpoints exist. In kind, the node is a Docker container, so `docker exec` lets you inspect the node's network state. In minikube, use `minikube ssh` for the equivalent node view.

```bash
# kind: inspect Service-related iptables rules on the control-plane node.
docker exec kind-control-plane iptables-save | grep -E "trace-svc|KUBE-SVC|KUBE-SEP" | head -60

# minikube alternative:
# minikube ssh "sudo iptables-save | grep -E 'trace-svc|KUBE-SVC|KUBE-SEP' | head -60"
```

Look for rules that connect the Service path to backend endpoint addresses. You do not need to memorize every generated chain name; you need to recognize that Service traffic is translated to endpoint pod IPs and ports.

### Step 5: Observe a Packet Capture

Run a packet capture on the node while generating one request from the client pod. Capturing on `any` is broad, but it is useful for learning because you can see packets at several interfaces. In a production incident, you would narrow the capture after deciding which interface answers your question.

```bash
# In one terminal, start a capture filtered to the client pod and HTTP port.
CLIENT_IP="$(kubectl get pod trace-client -o jsonpath='{.status.podIP}')"
docker exec kind-control-plane tcpdump -i any -nn "host ${CLIENT_IP} and port 80"

# In another terminal, generate one request.
kubectl exec trace-client -- curl -sS --connect-timeout 5 http://trace-svc
```

Before you stop the capture, identify whether you see the client pod IP, the Service IP, and a backend pod IP. Depending on timing and interface, you may not see every perspective in one capture, but you should be able to connect what you see to the packet walk from Part 1.

### Step 6: Inspect Conntrack for the Service Flow

Conntrack inspection is easiest immediately after generating traffic. The exact output varies by kernel and cluster image, but you are looking for flow state related to the Service ClusterIP, client pod IP, backend pod IP, and destination port.

```bash
# Get the ClusterIP and inspect matching conntrack entries on a kind node.
SVC_IP="$(kubectl get svc trace-svc -o jsonpath='{.spec.clusterIP}')"
docker exec kind-control-plane conntrack -L -d "${SVC_IP}" 2>/dev/null || true

# If no entries appear, generate several requests and try again.
for i in 1 2 3 4 5; do
  kubectl exec trace-client -- curl -sS --connect-timeout 5 http://trace-svc >/dev/null
done
docker exec kind-control-plane conntrack -L -d "${SVC_IP}" 2>/dev/null || true
```

Explain what conntrack is doing for this flow. A strong answer mentions that the Service destination is rewritten to a backend endpoint, and conntrack remembers the NAT mapping so reply traffic can be associated with the original client connection.

### Step 7: Introduce a NetworkPolicy Failure

Now create a controlled failure that blocks ingress to the backend pods. This lets you practice distinguishing DNS success from transport failure. The Service name should still resolve because the policy selects backend pods, not CoreDNS, but the HTTP request should fail because ingress to the backend is denied.

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-trace-backend
spec:
  podSelector:
    matchLabels:
      app: trace-backend
  policyTypes:
  - Ingress
  ingress: []
EOF

# DNS should still resolve the Service name.
kubectl exec trace-client -- nslookup trace-svc

# HTTP should fail or time out because backend ingress is denied.
kubectl exec trace-client -- curl -sS --connect-timeout 5 http://trace-svc || true

# Direct endpoint access should also fail because the policy blocks backend ingress.
ENDPOINT_IP="$(kubectl get pod -l app=trace-backend -o jsonpath='{.items[0].status.podIP}')"
kubectl exec trace-client -- curl -sS --connect-timeout 5 "http://${ENDPOINT_IP}" || true
```

Use the three-layer model to explain the failure. DNS still works, the Service still has endpoints, and the direct endpoint test fails, so the evidence points toward policy or CNI enforcement rather than kube-proxy.

### Step 8: Restore Connectivity and Clean Up

Remove the policy, verify the Service works again, and delete the exercise resources. Cleanup matters because leftover policies and debug pods can change future networking tests in surprising ways.

```bash
# Remove the controlled failure.
kubectl delete networkpolicy deny-trace-backend

# Verify connectivity is restored.
kubectl exec trace-client -- curl -sS --connect-timeout 5 http://trace-svc

# Cleanup exercise resources.
kubectl delete pod trace-client --force --grace-period=0
kubectl delete deployment trace-backend
kubectl delete svc trace-svc
```

**Card A: kube-proxy userspace-proxies every Service packet.** A learner sees the process name on the node and assumes every Service packet is copied into that process before a backend Pod can receive it. They restart the process and skip the programmed rules that actually select an endpoint.

<details>
<summary>Check your prediction</summary>

Failure layer: treating the control program as a userspace relay for every Service packet. Next action: inspect the configured mode and the node rules, because the usual path keeps the data packet in the kernel while that process watches Services and EndpointSlices.

</details>

**Card B: If conntrack drops the mapping, the client always receives a clean refusal.** A learner removes the return mapping in a lab and expects the client socket to fail immediately with connection refused. They treat any other client symptom as proof that a different layer must be responsible.

<details>
<summary>Check your prediction</summary>

Failure layer: expecting one clean refusal whenever the return mapping disappears. Next action: compare the client symptom with the backend view of the same flow, because the visible result depends on which state disappeared and can look like a stall, a reset, or traffic that only one side can complete.

</details>

**Card C: The Pod CIDR and the Service CIDR are the same address pool.** A learner sees a Pod address and a ClusterIP in the same packet walk and treats both numbers as members of one allocatable pool. They then search for the virtual Service address on a Pod interface, where that address is not assigned.

<details>
<summary>Check your prediction</summary>

Failure layer: collapsing the Pod address range and the virtual Service range into one pool. Next action: compare the ClusterIP from the Service with the Pod IP on the chosen endpoint, and keep those ranges distinct when you read routes and translation rules.

</details>

**Card D: A DNS failure means the CNI plugin is down.** A learner sees a name lookup time out and restarts the CNI agent before testing the DNS Service path. They skip the resolver file, CoreDNS, and DNS policy because they treat every name failure as a plugin outage.

<details>
<summary>Check your prediction</summary>

Failure layer: collapsing a name lookup failure into a CNI plugin outage. Next action: test a known Service name from the client, then a direct Pod IP, so you can separate a resolver or DNS Service problem from a path that never needed a name.

</details>

**Success Criteria**:
- [ ] You can identify the Service ClusterIP returned by DNS and explain why DNS success does not prove HTTP success.
- [ ] You can verify that the Service has ready endpoints by inspecting EndpointSlices or Endpoints.
- [ ] You can compare a Service request with a direct endpoint pod-IP request and identify which layer the comparison isolates.
- [ ] You can find node-level Service translation evidence for the exercise Service in iptables or the equivalent ruleset for your cluster mode.
- [ ] You can observe packet evidence with tcpdump and connect the capture to the packet walk from Part 1.
- [ ] You can inspect or reason about conntrack entries for a Service flow without treating conntrack as a black box.
- [ ] You can explain why the NetworkPolicy failure blocks backend traffic while DNS resolution still works.
- [ ] You can apply a repeatable troubleshooting mental model to the concrete packet-tracing challenge instead of jumping between unrelated commands.
- [ ] You can articulate the troubleshooting order: DNS, Service selection, direct endpoint reachability, policy or CNI, then node-level state.

---

## Sources

- [Virtual IPs and Service Proxies](https://kubernetes.io/docs/reference/networking/virtual-ips) — Backs kube-proxy responsibilities, Service ClusterIP implementation, EndpointSlice watching, and data-path claims about packet rewriting in kube-proxy-managed service networking.
- [Virtual IPs and Service Proxies](https://kubernetes.io/docs/reference/networking/virtual-ips/) — Canonical reference for kube-proxy behavior, Service VIPs, traffic policies, and Linux proxy modes.
- [Cluster Networking](https://kubernetes.io/docs/concepts/cluster-administration/networking/) — Explains the Kubernetes network model and the pod, service, and node IP responsibilities behind the cluster data path.
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) — Covers Service DNS records, pod resolver configuration, search domains, and the DNS behavior discussed in the module.
- [Using Source IP](https://kubernetes.io/docs/tutorials/services/source-ip/) — Shows how source NAT and `externalTrafficPolicy` affect NodePort and LoadBalancer traffic in practice.
- [Services, Load Balancing, and Networking](https://kubernetes.io/docs/concepts/services-networking/service/) — Defines Service types, selectors, ports, virtual IP behavior, and traffic policies used throughout the packet walk.
- [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) — Documents the scalable endpoint API that kube-proxy and replacements watch for Service backend state.
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — Explains how policy-capable CNIs enforce ingress and egress decisions that can block direct pod or DNS traffic.
- [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/) — Provides Kubernetes troubleshooting guidance for Services, selectors, endpoints, DNS, and proxy rules.
- [CNI Specification](https://www.cni.dev/docs/spec/) — Defines the container network interface contract used by plugins to attach pod network interfaces and configure addresses.
- [Cilium Kubernetes Without kube-proxy](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/) — Vendor documentation for an eBPF Service data path that replaces kube-proxy behavior.
- [Calico IP autodetection and node addressing](https://docs.tigera.io/calico/latest/networking/ipam/ip-autodetection) — Vendor documentation relevant to routed pod networking and node address selection in Calico clusters.

## Next Module

Continue to the [Part 3 Cumulative Quiz](../part3-cumulative-quiz/) to test the full Services and Networking stack, including Services, DNS, Ingress, Gateway API, NetworkPolicy, CNI, and the cluster networking data path.
