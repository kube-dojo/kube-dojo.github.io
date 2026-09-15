---
citations_verified: true
title: "Module 5.1: Cilium - The Kernel-Powered Network Revolution"
slug: platform/toolkits/infrastructure-networking/networking/module-5.1-cilium
sidebar:
  order: 2
---
> **Toolkit Track** | Complexity: `[COMPLEX]` | Time: 60-75 minutes

> **Landscape snapshot — as of 2026-09-15.** This changes fast; verify against [docs.cilium.io](https://docs.cilium.io/) and the CNCF project page before relying on specifics. Cilium is a CNCF Graduated project (accepted at Incubating on 2021-10-13, Graduated on 2023-10-11) and was the first graduated project in the cloud-native networking category.
>
> The current stable line is 1.20.x (for example 1.20.1); the community maintains the most recent three minor releases. kube-proxy replacement is enabled with the Helm value `kubeProxyReplacement=true`; the Gateway API data plane additionally needs the L7 proxy enabled and the Gateway API v1.5.1 CRDs pre-installed. A reference stack as of 2026-09-15 is Kubernetes 1.35, Cilium 1.20.1, Hubble Relay 1.20.1 (ships with Cilium), and Hubble CLI v1.19.4 (Hubble `stable.txt`).

**Prerequisites**:
- Kubernetes networking basics (Services, Pods)
- [eBPF Fundamentals](/platform/foundations/ebpf/module-1.1-ebpf-fundamentals/) for programs, maps, helpers, and verifier vocabulary
- [Security Principles Foundations](/platform/foundations/security-principles/)

---

## Learning Outcomes

After completing this module, you will be able to:

- **Explain how eBPF datapaths replace iptables-based kube-proxy** and what operational tradeoffs that shift introduces at cluster scale
- **Design identity-based network policies** using CiliumNetworkPolicy and cluster-wide rules at L3, L4, and L7
- **Use Hubble to observe flows** and troubleshoot DNS-aware policy drops without sidecar instrumentation
- **Evaluate kube-proxy replacement modes** including socket balancing, Direct Server Return, Maglev hashing, and XDP
- **Plan Cilium migration, encryption, Gateway API, and ClusterMesh** adoption with realistic validation checkpoints

---

## Why This Module Matters

Kubernetes networking was designed around IP addresses that change constantly. Pods restart, Deployments roll, autoscaling adds replicas, and node drains move workloads across the fleet. Standard NetworkPolicy translates label selectors into IP allow lists that must be refreshed on every change. kube-proxy programs those same ephemeral endpoints into iptables or nftables chains that grow with every Service and EndpointSlice update. At modest scale the model works; at larger scale the rule sets become expensive to reconcile and painful to debug when a packet disappears with no explanation.

Cilium addresses both problems at the layer where packets are actually handled: the Linux kernel. Instead of maintaining thousands of iptables rules per node, Cilium compiles Kubernetes intent into eBPF programs attached at TC, XDP, and socket hooks. Policy decisions use stable workload identities derived from labels, not transient pod IPs. Service load balancing happens in eBPF maps with constant-time lookups rather than linear chain walks. Hubble reads the same datapath events, so when traffic is dropped you can see the source identity, destination identity, protocol details, and the policy verdict without deploying tcpdump across dozens of pods.

Peer CNIs such as Calico and Flannel solve overlapping problems with different architectural bets. Calico offers mature BGP routing and a choice of iptables, nftables, or eBPF dataplanes. Flannel prioritizes simplicity with overlay networking. Cilium's distinguishing combination is kernel-native eBPF for networking, security, load balancing, and observability in one agent, plus optional Gateway API and mesh features without a per-pod sidecar. None of these choices is universally correct; the durable skill is understanding the tradeoffs well enough to match a datapath to your cluster's scale, compliance requirements, and operational maturity.

When connectivity breaks in a policy-heavy cluster, the cost is measured in engineer attention and customer-visible latency, not in abstract architecture debates. A platform team that can answer "which policy dropped this flow, and which identity was on each side?" in seconds instead of hours has a fundamentally different incident response posture. That visibility is the practical reason Cilium has become a default evaluation target for teams outgrowing iptables-only CNIs.

Adoption is also a staffing question. eBPF expertise is not required for day-one Cilium operations—the project ships compiled datapaths and a CLI—but advanced tuning, custom policy, and kernel interaction debugging benefit from engineers who have completed foundational eBPF material linked in the prerequisites. Budget training time the same way you budget cert-manager or ingress migrations: the tool reduces toil once the team trusts the observability signals.

---

## 1. The Problem Cilium Solves

### 1.1 iptables, kube-proxy, and rule-set growth

Every Kubernetes cluster that uses kube-proxy in iptables mode shares the same underlying mechanism. When you create a Service, kube-proxy installs NAT and forwarding rules so traffic to a virtual IP reaches healthy backend pods. Each Service and each backend endpoint contributes rules to chains that the kernel evaluates for every relevant packet. On a modest cluster with hundreds of Services, `iptables-save` output can already reach tens of thousands of lines. On larger fleets the counts climb into six figures, and the Kubernetes project has documented that iptables-mode kube-proxy can become an operational bottleneck as rule sets grow.

The debugging experience matches the scaling curve. When a packet is dropped or mis-routed, tracing it through nested kube-proxy chains across PREROUTING, KUBE-SERVICES, per-Service chains, and POSTROUTING is slow and error-prone. Adding LOG rules everywhere produces noisy logs and its own performance cost. Service updates trigger full rule rewrites rather than surgical edits, which can stall reconciliation for seconds on busy nodes and coincide with connection churn during rollouts. The Kubernetes community has been moving toward nftables-based kube-proxy and eBPF replacements precisely because the iptables model does not scale gracefully with Service cardinality.

Cilium's kube-proxy replacement moves Service handling into eBPF programs and maps. Backend selection becomes a hash lookup keyed by Service IP and port rather than a walk through iptables chains. Updates touch only the entries that changed, which reduces reconciliation blast radius during EndpointSlice churn. The tradeoff is explicit configuration: Cilium must know which network devices receive NodePort and external traffic, whereas iptables hooks applied broadly by accident on every interface. Teams that remove kube-proxy without validating device bindings sometimes discover intermittent NodePort failures that pod-to-pod traffic masks.

The Kubernetes project has documented nftables as a successor mode for kube-proxy because both iptables and nftables still scale with rule cardinality even when individual operations improve. eBPF-based replacements attack the problem from a different angle: fewer rules, more maps, and programs that encode Kubernetes semantics directly. That does not make Cilium free to operate; it shifts complexity from rule-list maintenance to agent configuration, kernel version requirements, and observability discipline. Operators who understand both sides can explain to security auditors why a cluster no longer carries six-figure iptables dumps while still enforcing default-deny policy.

When comparing CNIs for a greenfield cluster, ask how each option handles three growth axes: Service count, policy density, and observability requirements. Flannel optimizes for getting clusters online quickly with overlays. Calico offers flexible routing and multiple dataplane modes including eBPF. Cilium bets that one eBPF datapath can unify CNI, kube-proxy replacement, policy, encryption, and flow visibility. Your environment's kernel baseline, hardware NIC capabilities, and team familiarity with eBPF should drive the final choice more than headline features alone.

### 1.2 IP-based NetworkPolicy and ephemeral endpoints

Standard Kubernetes NetworkPolicy expresses intent with label selectors, but many CNIs implement enforcement with IP sets. A policy that allows `app: frontend` to reach `app: backend` becomes a list of current frontend pod IPs attached to backend endpoints. When a frontend pod restarts and receives a new IP, the CNI must detect the change, recompute affected policies, and distribute updates to every node before enforcement converges. During that window, legitimate traffic can fail or stale allow rules can linger.

This mismatch between semantic policy and IP enforcement is structural. Kubernetes assigns pod IPs from CNI-managed pools precisely so workloads can be scheduled freely; IPs are not stable identities. Security expressed as "this labeled workload may talk to that labeled workload" is durable; security expressed as "these thirty-two addresses may talk to those eighteen addresses" is not. Cilium's response is to assign each unique label set a cluster-wide numeric identity and evaluate policy on identities at the point of enforcement, while still using IPs for routing.

NetworkPolicy defaults in many clusters remain allow-all because teams fear locking themselves out during early development. That posture is understandable on day one and expensive on day three hundred when a compromised workload can reach every Service in every namespace. Moving to identity-aware default deny is a cultural change as much as a technical one. Platform teams publish baseline cluster policies, document required DNS and API exceptions, and give application teams templates for tier-to-tier allows. Cilium's entity shortcuts reduce the boilerplate that makes default deny feel unapproachable on other implementations.

East-west traffic inside a namespace is not automatically safe just because it shares a network boundary. Compliance frameworks increasingly expect segmentation between application tiers even when Kubernetes places them in the same namespace for convenience. Identity-based rules let you express tier boundaries with labels such as `tier: frontend` and `tier: data` without renumbering IPs every time Helm upgrades rename Deployments. The same model extends to batch jobs that spin up briefly: a CronJob pod receives an identity for its label set for the duration of the run, then disappears from endpoint lists without leaving stale IP rules behind.

**Hypothetical scenario:** A payment service fails health checks even though direct curl tests from an ops pod succeed. Hubble shows `DROPPED` flows from the health-checker identity to the payment service identity with a policy reference pointing at an older ingress rule that only allowlisted the previous Deployment's label value. The fix is a one-line label or policy selector update, not a tcpdump marathon across nodes. The scenario is common enough that identity-aware visibility pays for itself the first time it shortens a sev-2 bridge.

---

## 2. eBPF as Cilium's Datapath Foundation

### 2.1 What eBPF changes about packet handling

eBPF began as an extended Berkeley Packet Filter and has grown into a general-purpose in-kernel virtual machine. Programs are loaded dynamically, verified for safety, and JIT-compiled to native instructions. They can attach to tracepoints, kprobes, cgroup hooks, TC classifiers, XDP drivers, and socket operations. For networking, the important property is that decision logic runs in kernel context without copying every packet to userspace.

Traditional service proxying often follows a path where the kernel receives a packet, traverses multiple iptables chains, copies the payload to a userspace proxy, and copies it back after processing. Each userspace transition costs CPU cycles and cache locality. eBPF programs can perform forwarding, NAT, policy checks, and load-balancing backend selection while the packet remains in kernel buffers. Cilium generates and loads these programs from Kubernetes state; you do not write raw eBPF bytecode for routine cluster operations.

The mental model that helps many operators is "JavaScript for the kernel," with a strict verifier playing the role of a static analyzer that rejects programs with unbounded loops, illegal memory access, or unreachable paths. Before any eBPF program runs on a production node, the verifier proves it terminates and accesses only allowed memory regions. Invalid programs fail at load time rather than panicking the kernel at runtime, which is why distributions ship eBPF tooling for observability and networking alongside their kernel packages.

The mental model that helps many operators is "JavaScript for the kernel," with a strict verifier playing the role of a static analyzer that rejects programs with unbounded loops, illegal memory access, or unreachable paths. Before any eBPF program runs on a production node, the verifier proves it terminates and accesses only allowed memory regions. Invalid programs fail at load time rather than panicking the kernel at runtime.

### 2.2 Verifier constraints and why they matter to Cilium

The eBPF verifier enforces complexity limits, including a bounded instruction count analyzed during static verification. Programs cannot contain unbounded loops or unverifiable pointer arithmetic. These constraints occasionally reject programs that a human reviewer would consider safe, which is why Cilium maintains a compiler pipeline that splits logic across multiple programs and maps while staying under verifier limits.

Cilium contributors have upstreamed kernel changes over many release cycles to expand verifier expressiveness without sacrificing safety. From an operator perspective, the takeaway is that eBPF is not arbitrary kernel patching; it is a governed execution environment. When Cilium upgrades require a newer minimum kernel version, the reason is often a verifier or helper capability needed for a datapath feature rather than cosmetic churn.

Programs attach at well-defined hook points with explicit context. A TC classifier sees packets after the kernel has allocated sk_buff structures; XDP sees frames earlier when drivers support native XDP offload or generic XDP fallback. Cilium chooses hooks based on whether traffic is north-south from a physical NIC, east-west between pods on the same host, or destined for a Service VIP handled at the socket layer. Misunderstanding which hook handles your symptom leads to debugging the wrong program slice; Hubble metadata that names the observation point helps narrow the search.

Because eBPF maps are the shared state between programs, policy and forwarding read consistent backend and identity tables. That coherence is harder to achieve when iptables rules, ipvs tables, and a separate policy firewall evolve independently on the same node. The tradeoff is that map pressure and verifier complexity become your scaling variables instead of raw rule count. Large clusters with dense policies still require capacity planning, but the failure modes look different: map fullness, identity churn storms, and agent reconcile lag rather than multi-second iptables restore windows.

### 2.3 Where Cilium attaches in the stack

Cilium's datapath uses multiple hook points depending on feature and traffic direction. TC programs handle pod egress and ingress on veth pairs. XDP can accelerate north-south traffic at the NIC driver layer when supported. Socket-level load balancing hooks into `connect()` and `sendmsg()` for in-cluster Service access without extra NAT hops in some modes. Hubble observers attach alongside policy and forwarding programs so flow records reflect the same decisions applications experience.

Understanding hook placement explains feature interactions. Transparent encryption wraps payloads on the wire between nodes; policy checks typically evaluate identities before encryption on egress and after decryption on ingress. kube-proxy replacement programs share backend maps with policy enforcement so a drop verdict and a forwarding decision come from one coherent datapath state rather than competing subsystems.

---

## 3. Cilium Architecture

### 3.1 Control plane and per-node agents

Cilium splits responsibilities between cluster-level coordination and per-node datapath programming. The Cilium Operator handles cluster-wide tasks such as IP address management modes, CRD-related housekeeping, and features that require a single leader. Each node runs a Cilium Agent as a DaemonSet pod that watches Kubernetes API objects, computes desired state, compiles eBPF programs, and loads them into the kernel.

The agent also maintains the identity catalog, publishes endpoint state, and hosts the local Hubble observer. When a pod is scheduled to a node, the agent creates an endpoint representing that pod's networking identity, assigns or inherits an IP according to the configured IPAM mode, and installs routes and policy programs for the pod's veth pair. Deletion reverses the process and garbage-collects map entries so identities and IPs do not leak across rapid churn.

```
CILIUM CONTROL AND DATA PLANE (SIMPLIFIED)
═══════════════════════════════════════════════════════════════════

              ┌─────────────────────────────────────┐
              │         Kubernetes API Server        │
              │   Pods, Services, Policies, CRDs     │
              └──────────────────┬──────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
  ┌──────▼──────┐        ┌───────▼───────┐       ┌───────▼───────┐
  │   Cilium    │        │ Hubble Relay  │       │  Hubble UI    │
  │  Operator   │        │ (aggregation) │       │ (optional)    │
  └─────────────┘        └───────┬───────┘       └───────────────┘
                                 │
    ═════════════════════════════╧════════════════════════════════
                         PER NODE
    ═════════════════════════════════════════════════════════════

    ┌────────────────────────────────────────────────────────────┐
    │ Cilium Agent                                                │
    │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
    │  │  Identity   │  │ Policy engine │  │ Service LB / encrypt │ │
    │  │  manager    │  │ (eBPF maps)   │  │ (eBPF maps)          │ │
    │  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘ │
    │         └────────────────┴─────────────────────┘            │
    │                            │                                  │
    │                     ┌──────▼──────┐                           │
    │                     │ eBPF datapath│                           │
    │                     └──────┬──────┘                           │
    │              ┌─────────────┴─────────────┐                    │
    │         ┌────▼────┐                 ┌────▼────┐               │
    │         │ Pod A   │                 │ Pod B   │               │
    │         │ id=48291│                 │ id=73842│               │
    │         └─────────┘                 └─────────┘               │
    └────────────────────────────────────────────────────────────┘
```

### 3.2 Installation baseline for labs and greenfield clusters

The Cilium CLI wraps Helm installs with sensible defaults for quick starts. A typical greenfield install enables kube-proxy replacement and Hubble together so you can validate forwarding and observability in one pass.

```bash
# Install Cilium CLI (check upstream releases for your architecture)
CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)
curl -L --fail -o cilium-linux-amd64.tar.gz \
  "https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-amd64.tar.gz"
sudo tar xzvfC cilium-linux-amd64.tar.gz /usr/local/bin
rm cilium-linux-amd64.tar.gz

# Install with kube-proxy replacement and Hubble
cilium install \
  --set kubeProxyReplacement=true \
  --set hubble.enabled=true \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true

cilium status --wait
cilium connectivity test
```

The connectivity test deploys short-lived workloads and checks pod-to-pod, pod-to-Service, policy, DNS, and Hubble visibility. Treat a passing run as a necessary but not sufficient gate; your application namespaces still need policy and MTU validation under real traffic patterns.

IPAM mode selection affects operations more than newcomers expect. Kubernetes host-scope routing, cluster-pool CIDR allocation, and cloud-specific ENI modes each interact with overlay versus native routing choices. The operator configures the default mode; the agent implements it per node. Document your CIDR plan before install so ClusterMesh and external firewall rules do not collide later. When nodes join the cluster, the operator ensures new capacity receives consistent configuration without manual per-node edits for standard fields.

The agent exposes a local API and metrics useful during incidents. Prometheus scrape targets on agents surface reconcile errors, endpoint regeneration counts, and BPF map pressure indicators depending on version. Pair agent metrics with Hubble drop counters to distinguish "policy is denying traffic" from "datapath failed to program." That distinction saves hours when multiple teams join a bridge and each assumes a different layer is at fault.

---

## 4. Identity-Based Security and Network Policy

### 4.1 How Cilium identities work

When a pod starts with a label set, Cilium allocates or reuses a numeric security identity for that set cluster-wide. All pods with identical relevant labels share one identity regardless of how many replicas run or which nodes host them. Reserved identities cover special cases: the host, external world, health probes, and kube-dns, among others. Identity numbers below a configured threshold are reserved; workload identities begin above that range.

Policy enforcement asks whether source identity S may reach destination identity D on a given port and protocol, optionally with L7 constraints. The check is a map lookup in eBPF, not a scan of IP lists. When a frontend Deployment scales from two to two hundred replicas, the identity seen by backends remains unchanged if labels are stable. When a pod restarts with the same labels, policies continue to apply without waiting for IP set recomputation across the fleet.

Inspect identities with the CLI during incidents and policy design reviews:

```bash
cilium identity list
cilium identity get 48291
```

### 4.2 Standard NetworkPolicy and CiliumNetworkPolicy

Cilium implements standard Kubernetes NetworkPolicy resources, so existing policies continue to work during migration. CiliumNetworkPolicy adds CRD fields for identity-aware selectors, port rules with HTTP and Kafka matchers, DNS-based egress controls, and entity shortcuts such as `kube-apiserver`, `dns`, `health`, and `world`.

An L7 HTTP policy can allow only specific methods and paths to an API pod. Requests outside the allow list are denied at the network layer before the application handles them. That is powerful for limiting lateral movement after a compromise, but it also surfaces traffic you may not have noticed—metrics scrapes, admin paths, or legacy cron calls—that previously returned application-level 404 responses instead of explicit drops.

DNS-aware egress uses `toFQDNs` rules. Cilium's DNS proxy observes allowed queries, learns resolved IPs, and inserts them into ephemeral allow map entries with TTL awareness. This avoids hard-coding cloud provider IP ranges that change, but it requires explicit DNS egress allow rules in default-deny environments. Forgetting DNS is the most common reason a freshly locked-down namespace cannot resolve external APIs.

Cluster-wide policies apply with `CiliumClusterwideNetworkPolicy` when namespace boundaries are too narrow for platform baselines such as default deny with shared exceptions for DNS and the Kubernetes API. Layer cluster policies carefully; a broad selector can unintentionally constrain namespaces owned by other teams.

Kafka and DNS matchers in CiliumNetworkPolicy extend the same identity machinery to protocols beyond HTTP. A Kafka rule can allow particular API keys or topics between identities; DNS rules govern which names a workload may resolve before FQDN egress even enters the picture. These features reward teams that treat policy as product documentation: the allowed paths are explicit, reviewable in Git, and testable in CI with policy validation tools.

Standard Kubernetes NetworkPolicy remains valuable during migration because security teams can stage Cilium without rewriting every manifest on day one. Run dual validation in staging: apply the same traffic tests against standard policies and enhanced Cilium policies to see where behavior diverges. Divergence usually appears at L7, DNS egress, or entity shortcuts—not at basic podSelector ingress. Document those gaps in your migration runbook so application owners know which manifests they must upgrade for parity.

### 4.3 Policy design practices that survive churn

Start from explicit allow lists rather than implicit open defaults unless you have a documented reason to defer hardening. Document which identities each tier requires: frontends, APIs, data stores, batch workers, and operators. When introducing a new Deployment, compare its labels to existing `fromEndpoints` selectors before rollout; identity mismatches are a frequent cause of "the old version worked" connectivity reports.

Use Hubble dry runs in staging by applying policies while watching `--verdict DROPPED` flows under synthetic load. Production change windows benefit from the same command pair: apply policy, watch drops for five minutes, then promote or rollback. Calico and other CNIs offer overlapping policy models with different CRDs; the durable pattern—label-stable identities, default deny, explicit DNS—is portable even when the implementation details differ.

Policy audit questions should be identity-centric: which identities may reach the database identity, on which ports, with which L7 constraints, and which identities are explicitly denied by default. Export Hubble flows to your SIEM if retention requirements exceed local Relay buffers. Flow logs complement Kubernetes audit logs: audit logs show who changed a policy object; Hubble shows which flows that policy affected afterward.

---

## 5. Hubble Observability

### 5.1 Flow visibility without sidecars

Hubble consumes events from the same eBPF hooks that enforce policy and forward packets. Each flow record can include L3/L4 tuples, identities, namespaces, pod names, DNS names, HTTP metadata when L7 parsing is enabled, and a verdict such as FORWARDED, DROPPED, or ERROR. Because collection happens in the kernel, you do not deploy per-pod tracing sidecars or modify application code to gain baseline network visibility.

Hubble Relay aggregates flows from all nodes; the CLI and UI talk to Relay rather than individual agents in multi-node clusters. Enable Relay and optionally the UI during install, or upgrade an existing deployment with Helm values that turn on metrics exporters when you integrate with Prometheus.

```bash
# Hubble CLI install (architecture-specific artifacts upstream)
HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/main/stable.txt)
curl -L --fail -o hubble-linux-amd64.tar.gz \
  "https://github.com/cilium/hubble/releases/download/${HUBBLE_VERSION}/hubble-linux-amd64.tar.gz"
sudo tar xzvfC hubble-linux-amd64.tar.gz /usr/local/bin
rm hubble-linux-amd64.tar.gz

cilium hubble port-forward &
hubble observe --verdict DROPPED
```

### 5.2 Troubleshooting patterns operators reuse

Filter dropped traffic between two workloads to see policy verdicts immediately:

```bash
hubble observe \
  --from-pod production/checkout-worker \
  --to-pod production/orders-api \
  --verdict DROPPED -o dict
```

DNS problems show up as dropped UDP/53 flows or successful queries with unexpected answers. External API failures often split into "DNS never resolved" versus "resolved but egress denied." HTTP filters help distinguish L7 denials from TCP-level blocks.

Service map visualizations in the UI summarize dependency edges between identities over time. They are useful for onboarding and audits, not only incidents. Prometheus metrics such as `hubble_drop_total` and DNS response counters support alerting when drop reasons change after a policy rollout. Correlate rising policy drops with application error rates before deciding whether the policy is wrong or correctly blocking stale callers.

Hubble's DNS visibility is underused during egress lockdown projects. Teams enable FQDN rules, forget to watch resolver paths, and blame application timeouts on code regressions. A five-minute DNS-only observe window after each egress change surfaces misconfigured CoreDNS allowances, search domain oddities, and pods that bypass the cluster resolver with hard-coded public resolvers. Fixing resolver policy first prevents endless iterations on application-level timeouts.

Flow records include verdict reasons detailed enough to separate policy drops from forwarding errors. Teach on-call engineers to capture a short Hubble slice before rolling back policy changes; rollback restores service but erases evidence that explains which dependency was missing. Stored slices become regression fixtures for the next policy review.

---

## 6. kube-proxy Replacement and Load Balancing

### 6.1 Socket-level balancing and backend maps

With `kubeProxyReplacement=true`, Cilium programs Service IPs into eBPF maps that point to healthy backends selected from EndpointSlices. In-cluster clients using cluster IPs benefit from socket-level load balancing on supported paths, reducing extra NAT hops compared with legacy iptables-only flows. Verify replacement mode with `cilium status` and inspect programmed services via the agent's service list command.

Removal of the kube-proxy DaemonSet should be deliberate. Confirm that NodePort, HostPort, externalIPs, and sessionAffinity cases you rely on are supported in your chosen Cilium version and configuration. The upstream kube-proxy-free documentation lists feature matrices that change between releases.

SessionAffinity and local traffic policy interact with eBPF backend selection differently than with iptables probabilistic balancing. Applications that assumed kube-proxy stickiness may see different distribution until you configure affinity-aware maps or accept resharding behavior. Load tests after migration should include connection reuse patterns, not only stateless single-request probes.

ExternalTrafficPolicy Local preserves client source IP on some paths at the cost of uneven backend utilization. Cilium honors Kubernetes semantics but implements them through its own service tables. Review cloud load balancer health checks when switching datapaths; probes that succeeded against kube-proxy programmed rules may need recalibration when NodePort handling moves to eBPF.

### 6.2 Direct Server Return and Maglev hashing

Direct Server Return allows reply traffic from backend pods to return directly to clients when topology permits, instead of hairpinning through the node that performed initial load balancing. DSR can reduce latency and node CPU for large responses, but it requires correct L2/L3 knowledge and compatible network fabrics. Asymmetric paths break silently when return routes bypass expected security or NAT points.

Maglev consistent hashing provides stable backend selection that minimizes reshuffling when backend sets change size. That stability matters for long-lived connections and caches keyed by backend identity. Cilium exposes load balancer mode settings through Helm values; choose modes based on your underlay—overlay versus routed—and on whether external traffic enters through a bounded set of interfaces.

### 6.3 XDP for north-south acceleration

XDP attaches programs at the earliest driver hook, before sk_buff allocation, which can accelerate NodePort and external entry processing on supported NICs and drivers. Not every cloud instance type or kernel driver exposes the same XDP capabilities, so treat XDP as an optimization to validate in your environment rather than a universal default. When XDP is unavailable, TC programs still provide the core datapath; you trade some peak throughput for broader compatibility.

Maglev consistent hashing deserves explicit testing when your workloads maintain long-lived TCP connections to specific backends. Change backend cardinality in a staging cluster while running connection churn tests and compare reset rates across Maglev and alternative modes documented for your Cilium version. Document the chosen mode in your platform runbook so future node pool upgrades do not silently change balancing behavior.

North-south acceleration features never replace correct underlay design. If routing between nodes and load balancer subnets is asymmetric, eBPF optimisations cannot fix fundamental L3 mistakes. Validate return paths with traceroute and Hubble simultaneously when enabling DSR or XDP so you separate datapath tuning from fabric misconfiguration.

**Hypothetical scenario:** After enabling kube-proxy replacement, internal Services are fast but NodePort 30080 is intermittently unreachable from CI runners outside the cluster. `cilium status` shows kube-proxy replacement bound only to the primary eth0 interface while runners reach nodes via a secondary interface. Widening the `devices` Helm list to include every interface that receives NodePort traffic resolves the asymmetry. The lesson is that explicit device binding replaces iptables' accidental global coverage.

---

## 7. Gateway API and the Sidecar-Free Mesh Data Plane

### 7.1 Gateway API as the north-south contract

The Kubernetes Gateway API separates role-oriented resources—GatewayClass, Gateway, HTTPRoute—from implementation details. Cilium can act as a Gateway API data plane when the L7 proxy is enabled and the Gateway API CRDs are installed at a supported version. This lets platform teams publish ingress contracts that application teams consume without sharing cloud-specific annotations scattered across Ingress resources.

Enablement is more than flipping a single boolean. You need compatible CRD versions, Cilium's Envoy-based L7 proxy components, and RBAC that allows Gateways in the namespaces your model expects. Validate TLS termination, timeouts, retries, and traffic splitting in staging because Gateway API resources express richer routing than legacy Ingress.

Sidecar-free mesh features still require operational ownership of certificates and L7 policy objects. Schedule the same review cadence you would for any ingress controller upgrade, because Gateway API CRD bumps can arrive on independent timelines from Cilium agent releases.

### 7.2 Mesh features without per-pod sidecars

Traditional service meshes inject sidecar proxies next to every pod. Cilium's mesh direction attaches L7 policy and mutual TLS at the node datapath where possible, avoiding duplicate memory and CPU per replica. Mutual TLS identity still ties back to workload labels and certificates managed by Cilium components rather than application libraries.

Compare approaches on dimensions you actually operate: certificate rotation, L7 match expressiveness, multi-cluster routing, and blast radius when the datapath misconfigures. Istio and Linkerd provide mature control planes with different operational profiles. Cilium appeals when you want policy, load balancing, encryption, and observability to share one agent already present for CNI duties.

Gateway API route attachment rules determine which namespaces may publish hostnames and which Gateway objects accept them. Platform teams usually own GatewayClasses and shared Gateways; application teams own HTTPRoutes. Document RBAC accordingly before enabling the Cilium Gateway controller in production. TLS certificate sourcing—Secrets, cert-manager integrations, or external KMS-wrapped keys—should match how you already operate ingress elsewhere to avoid two competing certificate pipelines.

HTTPRoute filters for redirects, header mutations, and timeouts express ingress behavior that previously lived in cloud-specific annotations. That portability helps multi-cloud teams standardize edge behavior. It also means misconfigured routes can break clients before traffic reaches application pods, so staging validation with synthetic checks and Hubble HTTP metadata catches bad paths early.

---

## 8. Transparent Encryption

### 8.1 WireGuard between nodes

WireGuard encryption protects pod traffic crossing node boundaries with kernel-native cryptography. Enable it during install or upgrade with Helm values that turn on encryption and select WireGuard as the type. Applications do not need code changes; the agent wraps packets on egress and unwraps on ingress.

Encryption reduces effective MTU because tunnel headers consume bytes. Small API requests may work while large bulk transfers fail if pod MTU is not adjusted. When large transfers fail after enabling encryption, compare WireGuard interface MTU to pod interface MTU and test path MTU with bounded ping sizes before blaming application timeouts.

```bash
cilium install \
  --set encryption.enabled=true \
  --set encryption.type=wireguard

cilium status | grep Encryption
kubectl exec -n kube-system ds/cilium -- cilium encrypt status
```

### 8.2 IPsec as an alternative

Some environments standardize on IPsec for compliance or hardware integration reasons. Cilium supports IPsec-based transparent encryption as an alternative to WireGuard. The configuration surface differs: key rotation, SA management, and interoperability with existing IPsec gateways matter more in IPsec modes. Choose WireGuard for greenfield simplicity when security standards permit; choose IPsec when policy mandates it or existing tooling expects IKEv2 workflows.

Node encryption modes extend protection beyond pod-to-pod traffic on the wire between nodes. Review CPU overhead and key distribution when every node must encrypt all cluster traffic by default. Regulatory narratives often care about encryption in transit even when workloads already speak TLS; transparent encryption satisfies auditors who ask about east-west coverage without requiring every application to implement mTLS libraries.

Rotation drills should include encryption keys and identity certificates used by mesh features. A network outage during rotation is worse than a controlled maintenance window with documented steps. Practice disabling encryption in a staging cluster only if your compliance regime allows it; otherwise rehearse forward-only rotation with dual-key acceptance windows.

---

## 9. ClusterMesh for Multi-Cluster Connectivity

ClusterMesh connects multiple Kubernetes clusters so pods in different clusters receive global identities and can reach each other with policy enforcement consistent with single-cluster rules. A clustermesh-apiserver component coordinates identity and service information across clusters. Operators must align pod CIDR allocations so networks do not overlap, and they must secure the etcd-backed synchronization paths ClusterMesh relies on.

Multi-cluster policy extends the identity model: a service in cluster A can be allowlisted by label in cluster B when both run Cilium with ClusterMesh configured. This is attractive for active-active application tiers and for administrative domains that outgrow a single control plane. The cost is operational complexity—failure domains now span clusters, and DNS plus Service discovery semantics require explicit design.

Test failover by simulating cluster partition and observing whether identities resync without manual intervention. Document which teams may create global services and which policies are allowed to reference remote clusters. Calico offers its own multi-cluster patterns; compare synchronization models and firewall integration when choosing a multi-cluster strategy.

Global services in ClusterMesh expose backends across cluster boundaries with consistent identities. Clients resolve names through multicluster DNS conventions documented upstream. Misconfigured service exports look like intermittent 503 responses when only some clusters have backends healthy. Export only services that must be global; over-exporting increases policy and DNS complexity without benefit.

Latency-sensitive workloads need placement policy alongside ClusterMesh. Cross-region ClusterMesh is technically feasible but not a substitute for regional affinity. Measure round-trip times and failure detection intervals before promising active-active semantics to application teams.

---

## 10. Migration and Adoption Considerations

### 10.1 Replacing an existing CNI

Migration is not a flag flip. Most teams provision a parallel environment first: install Cilium on a greenfield cluster, run connectivity tests, replay representative workloads, and validate policy equivalents before touching production. In-place migration requires cordoning nodes, removing the old CNI DaemonSet, installing Cilium, and rebooting or recreating pods so networking reattaches cleanly. Mixed CNI states on one node break catastrophically.

Inventory dependencies before cutover: NetworkPolicy resources, custom egress controls, service mesh sidecars, host networking pods, and DaemonSets that assume specific interface names. MetalLB, external DNS, and ingress controllers may need coordination when kube-proxy disappears. Maintain a rollback path—keep the previous CNI manifests and a documented node rebuild procedure until Cilium has survived at least one full application rollout.

Application owners should receive a migration checklist: label conventions for identities, required ports for policies, external dependencies that need FQDN rules, and health-check paths that L7 policies must allow. Platform teams that publish this checklist before cutover see fewer emergency policy holes punched during launch week. Treat migration as a joint exercise between networking and application squads, not a silent DaemonSet swap executed overnight.

### 10.2 kube-proxy removal checklist

Confirm EndpointSlice handling, NodePort exposure paths, hostNetwork pods, and sessionAffinity requirements. Compare `iptables-save` line counts before and after only as a sanity check, not a performance scorecard. Validate external traffic on every interface CI and customers use. Run Hubble drop baselines so you recognize normal versus abnormal policy denials after migration week.

### 10.3 Operating Cilium long term

Upgrade Cilium on a schedule aligned with Kubernetes minor releases. Read release notes for datapath defaults, minimum kernel versions, and CRD schema changes. Keep the Cilium CLI version roughly aligned with the agent image. Participate in community slack and GitHub discussions when you adopt bleeding-edge features such as Gateway API or BPF-based L7 load balancing—the surface evolves quickly, which is why the landscape snapshot at the top of this module includes a date.

Brownfield migration benefits from a written rollback criterion: error rate thresholds, failed connectivity test suites, or inability to program NodePort on canary nodes. Run canary nodes or canary clusters before fleet-wide kube-proxy removal. Some teams keep kube-proxy in partial mode during transition; understand whether your target version supports the hybrid state you plan and for how long.

Training platform engineers on Hubble and identity semantics pays dividends before migration week. Engineers accustomed to tcpdump-centric debugging may distrust flow summaries until they correlate one Hubble drop line with a policy object name. A short internal workshop with staged policy mistakes builds confidence faster than learning during a production sev.

---

## Did You Know?

- **[Cilium graduated from the CNCF in October 2023](https://www.cncf.io/announcements/2023/10/11/cloud-native-computing-foundation-announces-cilium-graduation/)**, becoming the first graduated project in the cloud native networking category. Graduation signals sustained community governance, security review, and adoption across vendors—not a guarantee that every feature fits your cluster without evaluation.
- **WireGuard entered the mainline Linux kernel in version 5.6**, which is why Cilium can enable transparent encryption without out-of-tree modules on supported nodes. Kernel integration shifts operational burden from DKMS packaging to standard distribution kernels.
- **The eBPF verifier enforces bounded program complexity**, including instruction limits analyzed statically before load. Cilium's compiler splits datapath logic to stay within those limits across kernel versions.
- **Hubble was open-sourced in 2019 as an observability layer on Cilium's datapath**, capturing flow records from the same hooks that enforce policy. That shared origin is why drop verdicts in Hubble align with enforcement decisions applications experience.

---

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| **Skipping `cilium connectivity test` after install** | Silent misconfigurations surface only under real workloads | Run the test on every new cluster and after major upgrades |
| **Installing Cilium atop another active CNI** | Duplicate routing and policy hooks break pod networking | Remove or disable the previous CNI per migration docs, or use a fresh cluster |
| **Default-allow posture in regulated environments** | Compromised pods lateralize freely | Adopt documented default-deny baselines with explicit DNS and API exceptions |
| **Forgetting DNS egress in locked-down namespaces** | External FQDN policies never resolve | Allow `toEntities: [dns]` or equivalent before tightening egress |
| **Over-broad FQDN patterns** | `*.com`-style rules defeat egress control intent | Prefer `matchName` for known APIs; document exceptions |
| **Disabling Hubble to save resources** | Policy drops become guesswork during incidents | Keep Hubble enabled in production; tune metrics cardinality instead |
| **Removing kube-proxy without validating NodePort devices** | External traffic paths miss programmed interfaces | Align `devices` with every NIC that receives NodePort traffic |
| **Enabling WireGuard without MTU planning** | Large transfers fail while small requests succeed | Lower pod MTU or tune tunnel MTU; verify with path MTU tests |

---

## Quiz

<details>
<summary><strong>Question 1</strong>: Why does an eBPF datapath replace iptables-based kube-proxy at scale, and what tradeoff appears after kube-proxy removal?</summary>

eBPF maps replace linear iptables chain walks with constant-time Service and policy lookups, and they update incrementally when EndpointSlices change instead of rewriting huge rule sets. The tradeoff is explicit device configuration for NodePort and external traffic—Cilium must know which interfaces receive north-south flows, whereas iptables hooks often appeared global by default.

</details>

<details>
<summary><strong>Question 2</strong>: A pod cannot reach `api.stripe.com`. Which Hubble filters separate DNS failure from egress denial?</summary>

Run `hubble observe --from-pod <pod> --protocol dns` to see whether queries reach CoreDNS and return answers. Then run `hubble observe --from-pod <pod> --verdict DROPPED` to see whether TCP/443 to resolved IPs is denied. DNS success with TCP drops indicates missing or overly narrow `toFQDNs` rules; DNS drops indicate missing DNS egress allowances.

</details>

<details>
<summary><strong>Question 3</strong>: Why does Cilium enforce identity-based network policies instead of pod IP lists?</summary>

Pod IPs change on restart, scale events, and rescheduling. Identities are derived from label sets and remain stable for all pods sharing those labels cluster-wide. CiliumNetworkPolicy rules expressed as identity pairs survive churn without pushing IP list updates to every node on every EndpointSlice change.

</details>

<details>
<summary><strong>Question 4</strong>: A new Deployment cannot reach an API that older pods still reach. Identities differ. What is the likely root cause?</summary>

The new Deployment's labels no longer match `fromEndpoints` selectors in the API's ingress policy, so Cilium assigned a new identity that is not allowlisted. Fix labels to match the intended identity or update the policy selectors. Hubble `--verdict DROPPED` output showing `policy-verdict:none` confirms a missing allow rule rather than a Service routing bug.

</details>

<details>
<summary><strong>Question 5</strong>: After kube-proxy replacement, in-cluster traffic is healthy but NodePort access is intermittent. What kube-proxy replacement mode settings should you check first?</summary>

Inspect which network devices Cilium programs for NodePort handling via `cilium status` and Helm `devices` values. Traffic arriving on an unbound interface is a common cause when external clients use a different path than in-cluster tests. Direct Server Return mode can add return-path requirements; validate symmetry if DSR is enabled, and confirm whether Maglev or XDP settings affect the external entry path you use.

</details>

<details>
<summary><strong>Question 6</strong>: An L7 CiliumNetworkPolicy allows only `GET /api/v1/products.*` but `hubble_drop_total` rises while application error rates stay flat. What might be happening?</summary>

Traffic that previously reached the app and returned 404 may now be dropped at L7 without hitting application metrics—health checks, metrics scrapes, or internal jobs calling unlisted paths. Use `hubble observe --verdict DROPPED --protocol http` to read denied methods and URLs, then either extend the policy for legitimate paths or confirm the drops are desirable security signal.

</details>

<details>
<summary><strong>Question 7</strong>: During Cilium migration you enable WireGuard encryption. Large pod-to-pod transfers fail while small requests succeed. What is a prime suspect?</summary>

MTU mismatch from tunnel overhead. WireGuard headers shrink usable payload per frame. Compare pod and tunnel interface MTUs and run path MTU discovery tests between nodes. Recreate pods after agent-side MTU adjustments so workloads inherit updated settings before you declare the migration complete.

</details>

<details>
<summary><strong>Question 8</strong>: When does ClusterMesh adoption justify its complexity compared with single-cluster Gateway API ingress?</summary>

When workloads in separate clusters must communicate with consistent identity-aware policy, global services, or active-active placement—and when you can allocate non-overlapping pod CIDRs and operate the clustermesh-apiserver control path securely. Gateway API solves north-south ingress per cluster; ClusterMesh extends identity and service semantics across clusters. It is not a default for every platform.

</details>

---

## Hands-On Exercise

**Task:** Deploy a three-tier application on a kind cluster with Cilium, implement default-deny networking with explicit allows, and verify behavior with Hubble.

### Setup

```bash
cat > kind-config.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  kubeProxyMode: none
nodes:
- role: control-plane
- role: worker
EOF

kind create cluster --config kind-config.yaml --name cilium-lab

cilium install \
  --set kubeProxyReplacement=true \
  --set hubble.enabled=true \
  --set hubble.relay.enabled=true

cilium status --wait
cilium connectivity test
```

### Deploy workloads

```bash
kubectl create namespace demo

kubectl -n demo apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: database
  labels:
    app: database
spec:
  containers:
  - name: postgres
    image: postgres:15
    env:
    - name: POSTGRES_PASSWORD
      value: secret
    ports:
    - containerPort: 5432
---
apiVersion: v1
kind: Service
metadata:
  name: database
spec:
  selector:
    app: database
  ports:
  - port: 5432
---
apiVersion: v1
kind: Pod
metadata:
  name: api
  labels:
    app: api
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    ports:
    - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
  - port: 80
---
apiVersion: v1
kind: Pod
metadata:
  name: frontend
  labels:
    app: frontend
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    ports:
    - containerPort: 80
EOF
```

### Apply policies

```bash
kubectl -n demo apply -f - << 'EOF'
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: default-deny
spec:
  endpointSelector: {}
  ingress: []
  egress: []
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-dns
spec:
  endpointSelector: {}
  egress:
  - toEntities:
    - dns
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: frontend-to-api
spec:
  endpointSelector:
    matchLabels:
      app: api
  ingress:
  - fromEndpoints:
    - matchLabels:
        app: frontend
    toPorts:
    - ports:
      - port: "80"
        protocol: TCP
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: frontend-egress-api
spec:
  endpointSelector:
    matchLabels:
      app: frontend
  egress:
  - toEndpoints:
    - matchLabels:
        app: api
    toPorts:
    - ports:
      - port: "80"
        protocol: TCP
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: api-to-database
spec:
  endpointSelector:
    matchLabels:
      app: database
  ingress:
  - fromEndpoints:
    - matchLabels:
        app: api
    toPorts:
    - ports:
      - port: "5432"
        protocol: TCP
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: api-egress-database
spec:
  endpointSelector:
    matchLabels:
      app: api
  egress:
  - toEndpoints:
    - matchLabels:
        app: database
    toPorts:
    - ports:
      - port: "5432"
        protocol: TCP
EOF
```

### Verification

```bash
cilium hubble port-forward &
sleep 3

kubectl -n demo exec frontend -- curl -s --max-time 5 http://api
kubectl -n demo exec api -- bash -c 'apt-get update -qq && apt-get install -y -qq netcat-openbsd > /dev/null && nc -zv database 5432'
kubectl -n demo exec frontend -- bash -c 'apt-get update -qq && apt-get install -y -qq netcat-openbsd > /dev/null && nc -zv -w 2 database 5432; test $? -ne 0'

hubble observe --namespace demo --verdict DROPPED
```

### Success Criteria

- [ ] Cilium installs and `cilium connectivity test` passes
- [ ] Default-deny blocks traffic before explicit allows are applied
- [ ] Frontend reaches API on port 80 after policies are applied
- [ ] API reaches database on port 5432
- [ ] Frontend cannot reach database directly
- [ ] Hubble shows `DROPPED` for denied frontend-to-database attempts
- [ ] Hubble shows `FORWARDED` for allowed paths

### Cleanup

```bash
kind delete cluster --name cilium-lab
```

---

## Sources

- [Cilium Documentation](https://docs.cilium.io/) — Official guides for install, policy, kube-proxy replacement, encryption, and Gateway API.
- [Cilium GitHub Repository](https://github.com/cilium/cilium) — Source code, issue tracker, and component overview documentation.
- [Cilium CLI Repository](https://github.com/cilium/cilium-cli) — Install and connectivity test tooling reference.
- [Hubble Documentation](https://docs.cilium.io/en/stable/observability/hubble/) — Flow visibility, Relay, UI, and metrics setup.
- [Hubble GitHub Repository](https://github.com/cilium/hubble) — Observability layer architecture and CLI releases.
- [CNCF Cilium Graduation Announcement](https://www.cncf.io/announcements/2023/10/11/cloud-native-computing-foundation-announces-cilium-graduation/) — Graduation date and cloud-native networking context.
- [Cilium Component Overview](https://github.com/cilium/cilium/blob/main/Documentation/overview/component-overview.rst) — Agent, operator, and datapath relationships.
- [Cilium Terminology: Security Identity](https://github.com/cilium/cilium/blob/main/Documentation/gettingstarted/terminology.rst) — Identity allocation and label mapping rules.
- [Kubernetes NetworkPolicy in Cilium](https://github.com/cilium/cilium/blob/main/Documentation/network/kubernetes/policy.rst) — Supported policy kinds and scope.
- [Cilium L7 Policy](https://github.com/cilium/cilium/blob/main/Documentation/security/policy/layer7.rst) — HTTP and protocol-aware enforcement.
- [Cilium DNS-Based Egress Policy](https://github.com/cilium/cilium/blob/main/Documentation/security/policy/layer3.rst) — FQDN rules and DNS proxy behavior.
- [kube-proxy Replacement](https://github.com/cilium/cilium/blob/main/Documentation/network/kubernetes/kubeproxy-free.rst) — Service types, modes, and device configuration.
- [WireGuard Transparent Encryption](https://github.com/cilium/cilium/blob/main/Documentation/security/network/encryption-wireguard.rst) — Enablement and operational notes.
- [IPsec Transparent Encryption](https://github.com/cilium/cilium/blob/main/Documentation/security/network/encryption-ipsec.rst) — Alternative encryption mode.
- [ClusterMesh Documentation](https://docs.cilium.io/en/stable/network/clustermesh/clustermesh/) — Multi-cluster identity and service synchronization.
- [Gateway API in Cilium](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/gateway-api/) — L7 proxy and CRD requirements.
- [Linux eBPF Verifier Documentation](https://www.kernel.org/doc/html/latest/bpf/verifier.html) — Kernel safety checks for loaded programs.
- [Kubernetes Blog: nftables kube-proxy](https://kubernetes.io/blog/2025/02/28/nftables-kube-proxy/) — kube-proxy scaling context and iptables limitations.

---

## Next Module

Continue to [Module 5.2: Service Mesh](../module-5.2-service-mesh/) to learn about service mesh patterns with Istio, and when sidecar-free approaches make sense.
