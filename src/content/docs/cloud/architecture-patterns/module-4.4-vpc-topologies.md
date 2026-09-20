---
title: "Module 4.4: Cloud-Native Networking and VPC Topologies"
slug: cloud/architecture-patterns/module-4.4-vpc-topologies
sidebar:
  order: 5
---

> **Complexity**: `[ADVANCED]`
>
> **Time to Complete**: 3-4 hours
>
> **Prerequisites**: [Module 4.1: Managed vs Self-Managed Kubernetes](../module-4.1-managed-vs-selfmanaged/), [Module 4.2: Multi-Cluster and Multi-Region Architectures](../module-4.2-multi-cluster/), VPC subnetting basics, Kubernetes Services, and route-table fundamentals.

---

## What You'll Be Able to Do

- **Design** cloud-native VPC and VNet topologies for Kubernetes clusters across availability zones, private subnets, ingress paths, and shared-service networks.
- **Diagnose** IP exhaustion by connecting pod density, node type, subnet CIDR size, service ranges, and future cluster growth.
- **Implement** private-cluster access patterns with private API endpoints, controlled administration paths, and VPC-native routing.
- **Compare** underlay and overlay CNI models by evaluating performance, IP consumption, observability, cloud integration, and portability.
- **Evaluate** egress cost and compliance tradeoffs using NAT gateways, VPC endpoints, private service access, proxies, and centralized routing.

## Why This Module Matters

Cloud networking failures rarely look like networking failures at first. A deployment may fail because Pods are stuck in `ContainerCreating`. An autoscaler may add nodes while new Pods still can not receive addresses. A private cluster may appear healthy until the release pipeline loses access to the API endpoint. A cost incident may begin as a normal-looking NAT gateway line item that grows every time a cluster pulls images, streams logs, or reads object storage. The visible symptom is usually application pain, but the root cause is often VPC topology.

Kubernetes changes the scale of IP planning. A virtual-machine application might need one address per server, while a VPC-native Kubernetes cluster can need one address per Pod, one address per node, additional addresses for load balancers, and reserved space for future expansion. That difference turns a comfortable `/24` into a production constraint. The cluster may have enough CPU and memory, but if the subnet has no remaining addresses, workloads still can not start. This is why cloud architects and platform engineers need to understand pod networking before they choose subnet sizes.

The security model also changes. In a traditional three-tier application, the main boundaries are often public subnet, private subnet, database subnet, firewall, and load balancer. In a Kubernetes platform, those boundaries still exist, but they are joined by cluster API endpoints, node pools, CNI behavior, NetworkPolicies, ingress controllers, service meshes, VPC endpoints, and cross-account or cross-project routing. A secure cluster is not only one with private nodes. It is one where administration, ingress, egress, service-to-service traffic, and cloud-service access all follow deliberate paths.

This module focuses on design reasoning rather than memorizing one provider's console. The examples use AWS terms such as VPC, EKS, NAT Gateway, VPC endpoints, and Transit Gateway, but the same design questions apply to Azure VNets and AKS, Google Cloud VPCs and GKE, and hybrid networks. The exact service names differ; the architecture questions do not. Where Kubernetes commands appear, assume Kubernetes 1.35 or newer and define the shortcut with `alias k=kubectl` before using `k`.

## Did You Know

- VPC-native pod networking can consume subnet IP addresses far faster than node-based planning suggests because every Pod may receive a routable VPC address.
- Overlay networking reduces cloud-subnet pressure, but it can move observability and enforcement away from native cloud routing, security groups, and flow logs.
- A private cluster API endpoint improves exposure posture only when administrators and CI/CD systems have a reliable private access path into the network.
- Egress design is both a security and cost decision; traffic that should stay on private cloud backbones can become expensive if it crosses NAT gateways unnecessarily.

## 1. Start With Address Space, Not Products

VPC topology starts with address space because every later decision depends on whether routes can be expressed unambiguously. A VPC CIDR must leave room for public entry points, private node subnets, load balancers, databases, endpoints, shared services, future clusters, and sometimes peering or transit routing. If the organization also has on-premises networks, partner networks, or other cloud environments, the VPC range must not overlap those networks. Overlap is not a cosmetic problem; routers can not reliably decide where to send traffic when two reachable networks claim the same destination range.

Kubernetes adds another layer to the address plan. In VPC-native designs, Pods consume addresses from node subnets or dedicated pod ranges. In overlay designs, Pods consume an internal cluster range that may not be visible to the VPC fabric. In both cases, Services consume a separate cluster range inside Kubernetes. A design document should state which address pools exist, who allocates them, how large they are, which systems route them, and what happens when the platform grows. "We will use `10.0.0.0/16`" is not a design; it is only the first number in the design.

```text
Example cloud platform address plan

Organization reserved cloud block: 10.64.0.0/12

production-vpc: 10.64.0.0/16
  public-ingress-a:       10.64.0.0/24
  public-ingress-b:       10.64.1.0/24
  private-nodes-a:        10.64.16.0/20
  private-nodes-b:        10.64.32.0/20
  private-nodes-c:        10.64.48.0/20
  endpoints-shared:       10.64.80.0/24

staging-vpc: 10.65.0.0/16
shared-services-vpc: 10.80.0.0/16
on-premises summary route: 10.0.0.0/12
```

The example deliberately leaves unused space between subnet groups. That gap is operationally useful because network designs almost always grow. Private endpoint subnets, additional node pools, regional expansion, dedicated ingress zones, inspection appliances, and shared services often appear after the first cluster succeeds. If the original VPC is packed tightly, every new requirement becomes a migration rather than a route-table change. Private RFC 1918 space is limited, but inside a properly allocated organizational plan, wasting a little local space is usually cheaper than renumbering a live platform.

## 2. Plan Kubernetes IP Consumption

**Pause and predict:** If worker nodes report healthy status and autoscaling continues adding compute capacity, why are new Pods still unable to schedule and failing due to address allocation errors?

<details>
<summary>Check your prediction</summary>

Adding CPU and node compute resources does not create Pod IP addresses when the underlying subnet or secondary CIDR range is fully exhausted. In VPC-native networking architectures, the Kubernetes scheduler can place Pods only when the Container Network Interface can allocate valid IP addresses. On AWS, Amazon VPC CNI in prefix delegation mode assigns contiguous `/28` IPv4 prefixes (16 IP addresses per prefix) to elastic network interface slots on Nitro instances, but every prefix still draws directly from the assigned VPC subnet. If the subnet lacks contiguous blocks of 16 unallocated addresses due to fragmentation, prefix allocation fails with an `InsufficientCidrBlocks` error, stalling pod scheduling despite available node memory and vCPU. Upstream Kubernetes specifies a default limit of 110 Pods per node, which can be configured higher or lower on managed node groups based on networking topology and workload density rather than a rigid hardware cap. Meanwhile, Google Kubernetes Engine Standard clusters default to 110 Pods per node by automatically reserving a dedicated `/24` CIDR block (256 addresses) per node from the cluster pod secondary range, meaning secondary subnet mask sizing dictates the maximum cluster node count. Azure CNI in pod-subnet mode similarly assigns VNet IPs directly to pods and exhausts delegated subnets quickly if sizing calculations only anticipate virtual machine counts.
</details>

Platform teams transitioning from traditional virtualization to container platforms must establish rigorous network capacity models before rolling out production infrastructure. Translating workload sizing assumptions into concrete subnet allocations requires accounting for several interdependent variables across multiple availability zones and compute environments.

Capacity calculations require evaluating the relationship between cluster elasticity, worker node pools, and provider-managed network boundaries. When planning a multi-tenant platform, architects should calculate the peak concurrent pod footprint, interface reservations, and maintenance headroom rather than estimating average compute usage.

```text
Subnet sizing thought process

Target:
  24 worker nodes across three availability zones
  up to 40 Pods per node
  VPC-native pod addresses
  100 percent growth headroom

Rough demand:
  24 nodes * 40 Pod addresses = 960 Pod addresses
  24 node primary addresses    = 24 node addresses
  load balancers/endpoints     = reserve additional subnet space
  growth headroom             = roughly double the planned demand

Conclusion:
  Three tiny /24 private subnets are likely too small.
  Larger per-AZ private subnets or dedicated pod ranges are safer.
```

Subnet dimensioning must account for warm IP target buffers and rolling upgrade surges. When an autoscaling node pool initiates a rolling replacement, new nodes spin up and request network interfaces and address allocations before older nodes drain and terminate. If the subnet has zero remaining address headroom, replacement nodes cannot acquire necessary network attachments, causing node joins to fail and leaving the deployment partially updated. Reserving at least twenty-five to fifty percent additional address space above projected steady-state demand prevents rolling maintenance from triggering cascading scheduling failures.

Serverless and managed-node compute models change where the IP consumption bottleneck lives, which surprises teams that planned capacity using node-group arithmetic. On AWS, every EKS Fargate Pod receives its own elastic network interface with a primary private IP address from the subnet without sharing that ENI with any other Pod. The limiting factor shifts from "how many Pods fit on one node's ENI slots" to "how many available IP addresses remain in the subnet," because every new Pod directly draws one address regardless of cluster node count. This flips the capacity-planning equation: a Fargate-only workload can exhaust a subnet at Pod count alone, without any large node fleet to warn you. On GKE, Autopilot provisions and sizes nodes automatically in response to workload demand and manages the pod secondary IP range internally, so platform teams do not manually carve per-node Pod CIDR blocks the way they would in Standard mode. The tradeoff is that the maximum Pods per node is lower by default — 32 in Autopilot versus 110 in Standard — and Google controls node selection and subnet allocation, which means the platform team still needs to ensure the VPC subnet itself has enough headroom for the node scale that Autopilot may reach under load. In both serverless models, the subnet-math lesson intensifies: when you cannot control node count or Pod-per-node packing density precisely, you need subnet headroom sized for the workload's peak Pod footprint, not for a steady-state node estimate.

GKE and AKS use different implementation details, but the same design discipline applies. GKE VPC-native clusters use alias IP ranges for Pods and Services. Azure CNI options can assign VNet IPs to Pods or use overlay behavior depending on mode. The names differ, yet the review question is stable: where do Pod addresses come from, how many are available, how fast are they consumed, and can the architecture grow without renumbering?

## 3. Choose Underlay or Overlay Networking

**Pause and predict:** After selecting an overlay CNI architecture to conserve private VPC address space, will cloud VPC flow logs continue to display individual Pod IP addresses for network audit analysis?

<details>
<summary>Check your prediction</summary>

Overlay Pod IP addresses are allocated from an internal, cluster-managed CIDR block that is encapsulated across node-to-node tunnels (such as VXLAN or Geneve), meaning cloud VPC flow logs capture only the outer node IP addresses rather than discrete Pod identities. Conversely, underlay and VPC-native networking models allocate cloud-routable IP addresses directly to each container interface from VPC or VNet subnets. This direct allocation allows native cloud flow logs, cloud load balancers, and perimeter security groups to observe and filter individual Pod IP traffic directly, though at the expense of accelerated cloud address consumption.
</details>

Engineering teams evaluating network virtualization must balance perimeter visibility requirements against organizational infrastructure constraints. Deciding between direct routing and packet encapsulation establishes how operational teams inspect inter-service traffic and debug latency anomalies across production fleets.

Virtualization choices fundamentally alter the division of responsibility between cloud infrastructure and in-cluster networking layers. While underlay topologies bind pod lifecycles tightly to cloud provider fabric constructs, overlay architectures decouple container scheduling from physical network topology, introducing distinct considerations for encapsulation processing overhead and diagnostic tooling.

```mermaid
flowchart LR
    subgraph Underlay["Underlay: cloud-routable Pod addresses"]
        UClient[Client] --> ULB[Cloud load balancer]
        ULB --> UPod[Pod: VPC IP]
        UFlow[VPC Flow Logs] -. sees pod IP .-> UPod
    end

    subgraph Overlay["Overlay: cluster-routed Pod addresses"]
        OClient[Client] --> OLB[Cloud load balancer]
        OLB --> ONode[Node IP]
        ONode --> OPod[Pod: overlay IP]
        OFlow[VPC Flow Logs] -. sees node IP .-> ONode
    end
```

Neither model is universally superior. Underlay favors cloud integration and performance transparency. Overlay favors portability and address conservation. Some CNIs offer hybrid options, eBPF datapaths, native routing modes, or cloud-specific integrations that blur the line. The important architectural habit is to make the tradeoff explicit. If a team chooses overlay because private address space is constrained, it should also decide how it will observe pod-level traffic, enforce policy, and expose services. If a team chooses underlay, it should show the subnet math.

When a platform chooses underlay networking, packets stay closer to native cloud routing: GKE pod IPs are routable alias IPs in the VPC, AWS VPC CNI assigns routable secondary addresses or prefixes from the subnet, and Azure CNI Pod Subnet puts pod IPs in VNet space for direct reachability from peered networks or private endpoints. Overlay defaults invert that tradeoff: Azure CNI Overlay keeps pod traffic on an internal CIDR with SNAT at the node, and many portable CNIs encapsulate node-to-node traffic so VPC flow logs see node IPs rather than individual pod conversations. MTU is the hidden coupling between these models because encapsulation, VPN paths, and service-mesh sidecars shrink effective payload size; underlay designs that assume jumbo frames inside the VPC can silently fail when overlay tunnels or hybrid links sit downstream. Teams should document which model they chose, which provider default they inherited, and how they will observe pod-level traffic when the cloud fabric cannot see it directly.

| Factor | Underlay / VPC-native | Overlay / encapsulated |
|---|---|---|
| Pod address source | Cloud VPC/VNet ranges or provider-managed secondary ranges | Cluster-managed pod CIDR |
| Subnet pressure | Higher because Pods can consume cloud addresses | Lower because nodes consume cloud addresses |
| Cloud load balancer integration | Often direct to Pod IPs when supported | Often node or proxy based |
| Flow-log clarity | Cloud flow logs may show Pod addresses | Cloud flow logs usually show node tunnel traffic |
| Portability | More provider-specific | Often easier across clouds or constrained networks |
| Failure mode to watch | Subnet or prefix exhaustion | Encapsulation, MTU, CNI observability, tunnel health |

## 4. Design Private Cluster Access

**Pause and predict:** When worker nodes are deployed into private subnets without public IP addresses, can administrators continue running `kubectl` commands directly from an internet-connected laptop without establishing a dedicated private network transit route?

<details>
<summary>Check your prediction</summary>

Private worker nodes do not automatically make the Kubernetes control plane private. By default, newly created Amazon EKS clusters have public endpoint access enabled and private endpoint access disabled, meaning `kubectl` commands from the internet communicate directly with the public API server endpoint even when all compute nodes reside in isolated private subnets. When platform teams switch the cluster configuration by turning public access off and private access on, all `kubectl`, Helm, and API client requests must originate from within the VPC or from an attached network via VPN, direct link, transit gateway, or an in-VPC bastion host. If a team disables the public API endpoint before provisioning and validating a dedicated private transit path, human administrators and external CI/CD pipelines are immediately locked out of routine administration, even while worker nodes continue communicating with the private API server endpoint without interruption.
</details>

Platform architects designing zero-trust administrative boundaries must evaluate how operational workflows interact with decoupled network perimeters. Establishing automated delivery pipelines and maintenance procedures requires aligning credential distribution mechanisms with enterprise transit topologies before modifying cluster access settings.

```mermaid
flowchart TD
    Admin[Engineer laptop] --> VPN[VPN or private access]
    VPN --> PrivateAPI[Private Kubernetes API endpoint]
    Runner[CI runner in private subnet] --> PrivateAPI
    GitOps[GitOps controller inside cluster] --> PrivateAPI
    PrivateAPI --> Nodes[Private worker nodes]
```

Securing control-plane access requires evaluating the operational trade-offs of each private administration pattern. A dedicated bastion host or jump box deployed in a management subnet provides a straightforward administrative path, especially when secured via identity-aware session managers rather than open SSH ports, but it introduces an operational bottleneck that requires regular patching and access rotation. Alternatively, enterprise client VPNs allow operators to connect their local development workstations directly to the VPC CIDR, enabling familiar local tooling workflows at the cost of managing client VPN endpoints, client certificates, and split-tunnel routing configurations.

For continuous delivery pipelines, in-VPC build runners eliminate the need for external network ingress into the private cluster API by executing deployment jobs directly within the private network perimeter. GitOps controllers—such as ArgoCD or Flux running natively inside the cluster—further reduce attack surface by polling external source code repositories over outbound HTTPS connections, pulling desired state declarations into the cluster without requiring inbound firewall rules. As an interim hardening measure before fully disabling public access, teams frequently configure public endpoint CIDR allowlists to restrict internet reachability strictly to corporate egress IP addresses while engineering the long-term private transit architecture.

## 5. Build Ingress Paths Deliberately

Ingress design answers how external users reach services in the cluster. In cloud-native platforms, that usually means a public or internal load balancer, a Kubernetes Service, an ingress controller, Gateway API, or a service mesh gateway. The right design depends on protocol, source IP preservation, TLS termination, WAF needs, path routing, authentication, and whether the load balancer can target Pods directly. A simple `LoadBalancer` Service may be enough for an internal TCP service, while a public HTTP API usually needs stronger L7 controls.

Gateway API improves the old Ingress model by separating infrastructure ownership from application routing. Platform teams can own GatewayClasses, Gateways, listener policy, certificates, and shared load balancers. Application teams can own HTTPRoutes that attach to approved Gateways. That separation is useful in organizations where many teams publish services but only a smaller platform group should manage public edge configuration. The design is also easier to review because route attachment, listener scope, and namespace access are explicit.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: shared-public-gateway
  namespace: platform-ingress
spec:
  gatewayClassName: managed-l7
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      allowedRoutes:
        namespaces:
          from: Selector
          selector:
            matchLabels:
              allow-public-gateway: "true"
```

Ingress is also a security boundary. Public services should normally pass through TLS termination, WAF or equivalent filtering, rate limiting where appropriate, and clear ownership. Internal services should not accidentally become public because a manifest copied a `LoadBalancer` type from an example. In review, ask which clients should reach the service, whether the load balancer is public or internal, where TLS terminates, which route owns the hostname, and how source restrictions are enforced.

## 6. Control Egress Cost and Compliance

**Pause and predict:** When workloads running on private worker nodes route outbound traffic through a managed NAT gateway, do container registry pulls and cloud logging calls automatically stay off the NAT gateway?

<details>
<summary>Check your prediction</summary>

Outbound requests from private subnets to public cloud service endpoints cross the managed NAT gateway by default unless dedicated VPC endpoints are explicitly provisioned in the route table. High-volume provider dependencies—such as container image registries (Amazon ECR), object storage systems (Amazon S3), and cloud monitoring or logging endpoints (Amazon CloudWatch Logs)—must be architected endpoint-first to retain traffic on private cloud provider backbones. In contrast, external third-party SaaS APIs, open-source package repositories, and external license servers continue to require outbound internet transit through managed NAT gateways or egress proxy inspection layers.
</details>

Enterprise networking teams auditing cloud consumption must analyze how outbound data paths contribute to total infrastructure expenditure. Evaluating the volumetric flow of application egress allows engineers to structure subnet route tables and security boundaries around actual workload communication patterns.

Cloud provider networking provides specialized constructs to bypass public internet gateways for first-party managed services. VPC endpoints, AWS PrivateLink, Private Google Access, and Azure Private Endpoints route requests directly across provider backbone networks without traversing public IP routing tables. Gateway endpoints for Amazon S3 and DynamoDB operate via route-table prefixes without hourly surcharges, making them immediate architectural requirements for any cluster that pulls container layers from S3 or reads dataset buckets. Interface endpoints attach elastic network interfaces with private IP addresses directly into cluster subnets, providing private DNS resolution for services such as container registries, secret managers, and telemetry collectors.

```mermaid
flowchart LR
    Pod[Pod in private subnet] --> Route[Route table]
    Route --> NAT[NAT gateway to internet]
    Route --> S3Endpoint[S3 gateway endpoint]
    Route --> ECREndpoint[ECR interface endpoint]
    Route --> LogsEndpoint[Logs interface endpoint]
    NAT --> SaaS[External SaaS API]
```

Compliance-driven egress designs often add an explicit proxy or inspection layer. In that design, workloads may be denied general internet access and allowed to call only approved destinations through a proxy. NetworkPolicy can restrict Pods to the proxy, while cloud security groups and route tables restrict subnet-level paths. This is more complex than default NAT, but it gives security teams a place to log, filter, and review outbound traffic. The platform team should document exception processes because developers will eventually need new destinations.

NAT gateways are easy to deploy and expensive to leave unmanaged because billing combines hourly availability with per-gigabyte processing that applies even when the destination is another cloud service you could have reached privately. AWS NAT Gateway charges an hourly rate plus data processing per gigabyte, and traffic routed to a NAT in another availability zone adds cross-AZ transfer in both directions on top of NAT processing before internet egress rates apply. Google Cloud Cloud NAT uses a similar processing charge model with gateway hourly cost that scales with the number of instances using it. Azure NAT Gateway likewise bills hourly plus per-gigabyte processed data, and bandwidth out of Azure data centers is charged separately from NAT processing. Cross-region hub routing, registry mirror misses, verbose telemetry, and chatty health checks can spike bills because each gigabyte may pass through NAT processing plus regional or internet egress tiers. Endpoint-first designs for object storage, container registry, logging, and identity APIs usually reduce NAT volume more reliably than resizing NAT gateways after finance notices the line item.

## 7. Connect Multiple VPCs and Environments

Single-VPC platforms eventually grow into multi-environment networks. Development, staging, production, shared services, data platforms, security tooling, and on-premises networks may all need controlled communication. VPC peering is simple for a few networks, but it becomes hard to manage as the number of VPCs grows. Peering is also non-transitive in many clouds, which means routes do not automatically pass through one peered VPC to another. Transit routing services solve the hub-and-spoke problem but introduce cost, route-table design, and segmentation responsibilities.

```text
Number of pairwise peering connections

2 VPCs  -> 1 connection
3 VPCs  -> 3 connections
5 VPCs  -> 10 connections
10 VPCs -> 45 connections
```

Transit gateways, cloud routers, and hub networks are powerful because they centralize attachments and route policy. They are also dangerous when treated as a flat network. Production should not automatically reach every development subnet. Shared observability services may need inbound traffic from many environments, while developer sandboxes should not reach production databases. The transit layer should have route tables and segmentation rules that match the organization's trust model, not merely the network diagram.

Hybrid connectivity adds latency, bandwidth, and ownership questions. VPN can be fast to establish and suitable for management or moderate traffic. Dedicated private circuits such as Direct Connect or ExpressRoute can provide more predictable throughput and latency, but they require longer lead time and operational coordination. Kubernetes does not remove these constraints. If a service in the cluster calls a database across a high-latency hybrid link, the application must tolerate that latency no matter how elegant the Pod network is.

## 8. Operate the Network With Evidence

Network debugging should follow the packet path rather than the organizational chart. Start with the symptom: is the Pod unscheduled, Running but not Ready, unreachable through a Service, unable to resolve DNS, unable to reach an external destination, or slow under load? Each symptom points to a different layer. Pod scheduling failures may be CNI or subnet address problems. Service failures may be selector or endpoint problems. External egress failures may be DNS, route table, NAT, endpoint policy, security group, proxy, or NetworkPolicy issues.

```bash
alias k=kubectl

k get pods -A -o wide
k describe pod <pod-name> -n <namespace>
k get svc,endpoints -n <namespace>
k get networkpolicy -A
k logs -n kube-system -l k8s-app=aws-node --tail=100
```

Cloud-side evidence is just as important as Kubernetes evidence. Route tables show whether a subnet has a path to NAT, endpoints, peering, or transit. Flow logs show whether traffic reached an interface and whether it was accepted or rejected at that layer. Load balancer target health shows whether the edge can reach backend Pods or nodes. Endpoint policies show whether a private service endpoint allows the requested action. When the platform team combines Kubernetes events with cloud network evidence, incidents become much easier to isolate.

Avoid the reflex of changing security rules first. Opening `0.0.0.0/0` or disabling NetworkPolicies may hide the immediate symptom while creating a larger exposure. A better approach is to prove which boundary denied or dropped traffic. If DNS resolution fails, route-table changes will not help. If the Service has no endpoints, adding a NAT gateway will not help. If a route table points to the wrong transit attachment, restarting Pods will not help. Evidence-driven debugging is slower for the first five minutes and faster for the next five hours.

## 9. Design for Availability Zones and Failure Domains

Availability-zone design is the quiet part of VPC topology. A cluster that spans three zones but places all NAT, endpoints, or load-balancer targets in one zone is not truly zonal. Kubernetes can reschedule Pods across nodes, but it can not compensate for a route table that sends every private subnet through a single-zone dependency. If the platform claims zone resilience, the network path for ingress, egress, service endpoints, and control-plane access needs to survive the loss or isolation of one zone.

Private node subnets should usually be created per zone with consistent sizing and route-table intent. If one zone has a much smaller subnet than the others, autoscaling may fail only in that zone, and topology spread constraints may become impossible to satisfy. This creates a confusing failure mode: the cluster has free capacity in aggregate, but the scheduler is constrained by zones, Pod topology rules, storage topology, or load-balancer target health. The network design should therefore reserve enough address space per zone, not only across the whole VPC.

NAT gateway placement is a common availability and cost trap. A single NAT gateway is cheaper, but every private subnet that depends on it loses outbound internet access if that zone or NAT gateway fails. A NAT gateway in every zone improves resilience and avoids cross-zone routing for egress, but it increases hourly cost. VPC endpoints have similar placement questions: interface endpoints are created in selected subnets, and workloads in other zones may cross zones to reach them if the design is incomplete. The architecture decision should explicitly state which dependencies are zonal and why.

Load balancer target behavior also depends on zone design. If a public load balancer spans three zones but healthy Pods exist in only one zone, the system may be more fragile than the diagram suggests. Some providers and load balancers can perform cross-zone load balancing, but that may change cost and failure behavior. When reviewing ingress, ask whether each zone has enough healthy targets, whether topology spread rules support that goal, and whether the load balancer health checks match the Service and Pod readiness contract.

Stateful dependencies complicate the picture further. A database, cache, file system, or message broker may have its own zone placement and failover rules. If an application Pod moves across zones but its dependency remains single-zone, latency and data-transfer costs may change. If a PersistentVolume is bound to one zone, a Pod that needs it may not be schedulable in another zone. Kubernetes exposes some of this through volume topology and scheduling events, but the network and storage design should anticipate it before an incident.

## 10. Separate Shared Services From Workload Networks

Shared services are tempting to put directly inside production because they are required by production workloads. Observability collectors, image caches, artifact repositories, identity proxies, DNS forwarders, and security tooling all feel foundational. The problem is that their network relationships differ from application services. Many environments may need to send telemetry to shared observability. Production may need to pull images from a shared registry. Development may need access to shared test services. Those patterns are easier to reason about when shared services live in a clearly defined network zone with explicit routes.

A shared-services VPC or hub namespace does not automatically make a design secure. It gives the platform team a place to attach route tables, endpoint policies, inspection controls, and service ownership. Production might route logs to shared observability but reject inbound connections from development. Development might reach a shared package mirror but not production databases. Security tooling might receive mirrored traffic or logs but not have general lateral reach. The topology should encode those differences instead of relying on human memory.

```mermaid
flowchart TD
    Prod[Production VPC] --> Obs[Shared observability]
    Staging[Staging VPC] --> Obs
    Dev[Development VPC] --> Obs
    Prod --> Registry[Shared registry cache]
    Staging --> Registry
    Dev --> Registry
    Dev -. denied .-> ProdDB[Production database subnet]
```

DNS becomes important in shared-service designs. A service name that resolves differently inside development and production can help isolate environments, but it can also hide mistakes. Private hosted zones, conditional forwarding, split-horizon DNS, and service discovery need ownership. If a production workload resolves a shared endpoint to the wrong VPC, the issue may look like an application timeout. DNS records should be reviewed with the same seriousness as route tables because names are part of the network control plane.

Identity should not be inferred from network location alone. A request from a production subnet may still come from the wrong workload or an over-privileged service account. Modern cloud platforms combine network controls with workload identity, IAM conditions, endpoint policies, and application authentication. Network topology reduces the blast radius, but it should not be the only gate for sensitive shared services. The review question is: if a route exists, what identity and policy still limit what can happen over that route?

## 11. Review MTU, DNS, and Service Discovery

Not every network incident is caused by a blocked route. Overlay encapsulation, VPN tunnels, service mesh sidecars, and hybrid links can all reduce the effective Maximum Transmission Unit. When packets exceed the path MTU and fragmentation or discovery fails, applications may see strange timeouts, partial responses, or protocol-specific failures. This is especially hard to diagnose because small health checks may pass while larger payloads fail. If the topology includes tunnels or overlays, the design should document MTU assumptions and test realistic payload sizes.

DNS failures are equally common. Kubernetes has cluster DNS for Services, cloud networks have private DNS for endpoints and internal load balancers, and hybrid environments may have conditional forwarding between on-premises and cloud resolvers. If one layer is misconfigured, applications may fail before routing begins. Debugging should include `nslookup` or equivalent checks from inside a Pod, from a node, and from an administrative network. The answer may differ at each point because each point uses a different resolver path.

Service discovery also changes during migrations. A workload that once called `database.internal.example.com` may move into Kubernetes and suddenly prefer a Kubernetes Service name, a private endpoint name, or a service mesh hostname. During transitions, teams sometimes maintain several names for the same dependency. That is acceptable only when ownership is clear. Stale DNS records can keep old paths alive long after the intended migration has finished, making traffic flows harder to audit.

The best topology reviews include packet-size and DNS test cases. For example, a review can ask the team to prove that a Pod can resolve the container registry endpoint, pull an image through the intended private endpoint, reach an internal API by private DNS name, and send a realistic payload over the hybrid path. Those checks are cheaper than discovering at launch that only the smallest requests survive a tunnel path.

## 12. Document the Topology as an Operations Contract

A VPC diagram is useful, but it is not sufficient. The operations contract should state the intended paths for administration, ingress, egress, cloud-service access, inter-environment traffic, and hybrid traffic. It should name the owner of each route table, endpoint, DNS zone, load balancer, proxy, and transit attachment. It should also record the negative spaces: development does not reach production databases, workloads do not bypass the egress proxy, and public clients do not reach private Services directly. Those denials are part of the design.

Good documentation includes capacity assumptions. Record maximum nodes, expected Pods per node, chosen CNI mode, subnet sizes, pod ranges, service ranges, and headroom. Without those numbers, future teams may add node pools or clusters that consume the remaining address space. The document should also state what metric warns before exhaustion. For VPC-native clusters, that may be subnet available IPs, CNI warm IP behavior, node ENI allocation, and Pod scheduling failures. For overlay clusters, it may be overlay CIDR capacity and CNI health.

The contract should be updated after incidents. If an egress outage was caused by a missing endpoint policy, update the egress section. If a private cluster locked out CI, update the administration path. If a route table allowed development to reach production unexpectedly, update segmentation rules and tests. Architecture documents decay when they only describe launch day. They stay useful when they reflect how the platform actually operates.

Finally, keep examples close to the design. A short command list for checking endpoints, routes, flow logs, and Kubernetes objects is more useful than a diagram alone during an incident. A reviewer should be able to read the topology document and understand both the intended steady state and the first evidence to collect when the steady state breaks. That is the difference between a network drawing and an operations-ready architecture.

## 13. Add Preventive Guardrails

The strongest network topology is not only reviewed by humans; it is protected by guardrails that catch predictable mistakes before resources land. Infrastructure-as-code policies can reject subnets that are too small for a production cluster, public cluster endpoints without an approved exception, public load balancers in namespaces that should be internal only, route tables that bypass inspection, or security groups that expose administrative ports broadly. These policies should encode the organization's known failure modes, not every theoretical preference.

Preventive guardrails work best when they explain the architectural reason behind the rejection. A policy that says "subnet too small" is less useful than one that says "production node subnets must provide enough addresses for target Pods, nodes, load balancer targets, and 100 percent growth headroom." A policy that blocks public API endpoints should point to the approved private-access pattern. Good guardrails teach the design standard while enforcing it. Bad guardrails become mysterious bureaucracy and are bypassed during incidents.

```text
Useful topology guardrail examples

- Production Kubernetes private subnets must be at least the approved size for the cluster class.
- Public API endpoints require an explicit exception and source allowlist.
- Public load balancers must carry owner, data-classification, and review labels.
- Private clusters must declare an administrator and CI/CD access path.
- High-volume provider services must use private endpoints when available.
- Transit routes between development and production require an approved shared-service path.
- Network diagrams must include DNS, egress, and route-table ownership, not only subnets.
```

Runtime guardrails are equally important. Subnet available-address metrics should alert before exhaustion, not after Pods fail. NAT gateway data processing should have cost anomaly alerts. Load balancer target health should page when an ingress path has no healthy backends. Private endpoint errors should be visible to platform teams because endpoint policies can deny requests in ways that look like application failures. NetworkPolicy default-deny adoption should be measured by namespace so teams know which workloads still rely on implicit trust.

The platform team should also run periodic topology drift reviews. Cloud networks are often changed by urgent tickets: one more route, one more security-group rule, one more peering connection, one more endpoint. Each change may be reasonable alone, but together they can erode segmentation. A monthly or quarterly review can compare intended topology with actual route tables, security groups, endpoints, load balancers, DNS zones, and transit attachments. Drift review is not glamorous, but it prevents the network from becoming an undocumented exception pile.

## 14. Use a Review Checklist Before Cluster Launch

Before launching a production cluster, run a topology review that forces specific answers. Start with address planning: What CIDR is allocated to the VPC? Which subnets are public, private, endpoint, and reserved? How many nodes and Pods are expected per zone? What CNI mode is used? What metric warns before IP exhaustion? Which team can allocate additional ranges? If any of those answers is missing, the cluster may work on day one and fail during the first scale event.

Next review exposure. Is the API endpoint public, private, or both? Which identities can administer the cluster? Where do CI/CD runners run? Which load balancers are public? Which services are internal only? Where does TLS terminate? Which WAF or rate-limit controls protect public routes? Which namespaces are allowed to attach routes to shared gateways? Exposure review should produce a list of allowed paths, not only a list of blocked paths.

Then review egress. Which destinations do workloads need? Which cloud-provider services have private endpoints? Which traffic still needs NAT? Which traffic must pass through an inspection proxy? How are proxy exceptions requested? How are egress costs monitored? Which namespaces have default-deny NetworkPolicies? Egress is often where cost, compliance, and developer experience collide, so the decision needs explicit ownership rather than default routes inherited from a sample VPC.

Finally review operations. What evidence should on-call collect during Pod IP assignment failures? Where are flow logs stored? Which dashboards show subnet address usage, NAT data processing, endpoint errors, load balancer target health, and DNS failures? Which team owns route tables and transit attachments after launch? Which change process updates the topology document? A cluster can be well designed technically and still be difficult to operate if no one knows where the evidence lives.

## 15. Apply the Pattern Across Cloud Providers

The examples in this module use AWS vocabulary because EKS, Amazon VPC CNI, NAT Gateway, VPC endpoints, and Transit Gateway make the tradeoffs concrete. The same review process applies elsewhere. In Google Cloud, the terms shift toward VPC-native clusters, alias IP ranges, Cloud NAT, Private Service Connect, Cloud Router, and VPC Network Peering. In Azure, the terms shift toward VNets, Azure CNI modes, Private Link, NAT Gateway, Route Server, and ExpressRoute. The provider names change, but the questions remain stable.

For every provider, ask where Pod addresses come from, how Services are exposed, how the cluster API endpoint is reached, how private workloads reach provider services, how external egress is controlled, and how multiple environments route to one another. If a provider offers a managed shortcut, still identify the underlying path. A managed private endpoint is easier to operate than a hand-built proxy, but it still has DNS, policy, subnet, cost, and ownership implications. Managed does not mean undesigned.

Multi-cloud platforms need extra restraint. It is tempting to design one abstract topology that hides provider differences, but the differences matter when incidents happen. A useful platform standard defines common concepts such as private nodes, endpoint access, egress policy, ingress ownership, and address planning, then maps those concepts to provider-specific implementations. That gives teams a shared architecture language without pretending every cloud network behaves identically.

The mature design habit is to separate principle from mechanism. The principle might be "production workloads do not use public egress for provider-native object storage." The AWS mechanism may be an S3 gateway endpoint. The Google Cloud mechanism may be private Google access or Private Service Connect depending on the service. The Azure mechanism may be a private endpoint. This separation lets architecture reviews stay portable while implementation remains precise enough to operate.

This is also how teams avoid cargo-cult diagrams. A copied reference architecture may show three zones, private subnets, ingress, NAT, and endpoints, yet still be wrong for the workload if address growth, egress destinations, compliance boundaries, or hybrid routes differ. The review should ask what the platform is trying to protect, what it is trying to optimize, and what failure it must survive. Once those answers are clear, provider-specific services become implementation choices instead of architecture by screenshot. That habit keeps the design explainable when cloud products, provider defaults, team ownership, compliance scope, workload traffic patterns, audit demands, incident lessons, regional constraints, business priorities, budget pressures, and organizational risk tolerance change over time.

## Patterns & Anti-Patterns

VPC topology decisions repeat across organizations, and the patterns that work are visible in the review checklist earlier in this module. Naming them explicitly helps teams recognize which category their design falls into and whether they are adopting a proven pattern or drifting into a known failure mode. The patterns below are not silver bullets; they succeed only when the operational practices around address planning, egress design, and segmentation follow the principles in the preceding sections.

### Patterns

| Pattern | What It Looks Like | Why It Works |
|---|---|---|
| Hub-and-spoke / transit VPC | A central transit gateway or hub VPC routes traffic between workload VPCs (production, staging, development, shared services). Each spoke VPC attaches once to the hub rather than peering pairwise. | Centralizes route policy, network inspection, and segmentation. Reduces connection count from O(n²) to O(n). Allows production to communicate with shared services while development remains isolated. |
| Shared-VPC with host/service projects | A host project or network account owns the VPC, subnets, and connectivity. Service projects or member accounts consume those shared subnets for their workloads. AWS RAM-shared subnets and GCP Shared VPC are the provider implementations. | Centralized network ownership by a platform or networking team. Application teams consume networking without creating or peering their own VPCs. Security, compliance, and address planning stay in one place. |
| Dedicated VPC-per-environment | Each environment (production, staging, development, sandbox) gets its own VPC with independent address space, subnets, and connectivity rules. Environments connect only through explicit routes or transit attachment. | Maximum blast-radius isolation. A misconfiguration in development cannot route into production because no route exists. Capacity planning stays independent per environment, and each environment can evolve its topology at its own pace. |

These three patterns are composable rather than mutually exclusive. A platform often runs hub-and-spoke connectivity across dedicated per-environment VPCs while using a shared-services VPC for observability and registry. The composability is why earlier sections treated address planning, ingress, egress, private access, availability zones, and shared-service isolation as independent design dimensions rather than forcing a single template.

### Anti-Patterns

| Anti-Pattern | Why It Happens | Why It Fails |
|---|---|---|
| Overlapping or reused CIDRs across VPCs | Teams pick the same convenient RFC 1918 range (frequently `10.0.0.0/16`) for every VPC because it fits and looks clean in isolation. | Routers cannot differentiate two reachable networks that claim the same destination range. Peering, transit routing, and hybrid connectivity break, and the fix is renumbering — one of the most expensive network migrations. |
| No IP-growth headroom | Subnets are sized tightly to launch-day node and Pod counts with zero padding. | Every new node pool, endpoint subnet, AZ expansion, or Pod-density increase becomes a migration. The silent scaling wall hits after the cluster succeeds, when the platform team is under the most pressure to grow. |
| Flat single-subnet "everything routable" | One large private subnet contains nodes, Pods, databases, and management interfaces, with no network segmentation between them. | Security controls that depend on subnet boundaries cannot be applied. NetworkPolicy and security groups can provide east-west controls, but subnet-level segmentation is a simpler, more auditable layer that catches mistakes before they reach workload policy. |
| Public API endpoint by default | A managed Kubernetes cluster is created with a public API endpoint because that is the provider default or the quickest path to `kubectl` access. | The control plane remains reachable from the internet even after worker nodes go private. Authentication and authorization may limit access, but exposure surface stays larger than it needs to be, and the public endpoint becomes the path of least resistance for administration. |

Each anti-pattern has a clear fix that maps to one of the preceding sections: allocate non-overlapping CIDRs from an organizational address plan, size subnets for peak Pod footprint plus headroom, separate subnets by trust zone, and design the private administration path before locking down the API endpoint. When these anti-patterns survive into production, they are usually not design choices — they are accidents of time pressure that no one revisited after the cluster launched.

## Decision Framework

The module covers four VPC topology decisions that interact. The table below captures each decision, the alternatives, the primary tradeoffs, and the section that provides depth. Use it as a guided summary when evaluating a new design or auditing an existing one.

| Decision | Alternatives | Primary Tradeoff | Depth |
|---|---|---|---|
| Overlay vs underlay (routable Pod IPs vs encapsulation) | **Underlay**: VPC-native (AWS VPC CNI, GKE alias IP, Azure CNI Pod Subnet). **Overlay**: encapsulated pod CIDR (Azure CNI Overlay, Calico, Cilium tunnel mode). | Underlay: cloud-native flow logs, direct load balancer integration, higher subnet IP consumption. Overlay: conserves subnet space, easier multi-cloud portability, cloud fabric sees node traffic only. | Section 3 |
| Shared vs dedicated VPC | **Shared**: host project or network account with shared subnets. **Dedicated**: per-environment VPC with independent address space. | Shared: centralized ownership, consistent policy, simpler inter-environment routing. Dedicated: stronger blast-radius isolation, independent capacity planning, harder to accidentally bridge environments. | Sections 7, 10 |
| Private vs public cluster endpoint | **Private**: API endpoint accessible only from inside the VPC or private connectivity. **Public**: endpoint reachable from the internet with source restrictions. | Private: reduced exposure surface, requires tested administration and CI/CD private access paths. Public: simpler initial access, larger attack surface, easier to lock yourself into before building private paths. | Section 4 |
| NAT vs no-egress (endpoint-first design) | **NAT**: default route through NAT gateway for all outbound traffic. **Endpoint-first**: private endpoints for cloud services, NAT reserved for true internet/SaaS destinations. | NAT: simple, expensive at scale, every gigabyte crosses billing tiers. Endpoint-first: cheaper for high-volume cloud services, requires deliberate endpoint and route-table design, NAT still needed for internet-bound traffic. | Section 6 |

The decisions are rarely independent. A team choosing underlay networking with a dedicated VPC-per-environment and a private endpoint will need more subnet address space per VPC than a team choosing overlay networking with shared-VPC networking and public endpoints. The framework works as a fast consistency check: pick one entry from each row and ask whether the combination holds together under the address-capacity, bandwidth-cost, blast-radius, and operations constraints the module describes. If the numbers do not sum, the topology is not yet ready for launch.

## Common Mistakes

| Mistake | Why It Happens | Better Move |
|---|---|---|
| Sizing subnets from node count only | Teams plan like virtual machines and forget Pod addresses, load balancers, endpoints, and future node pools. | Calculate Pod density, node limits, CNI behavior, growth headroom, and per-AZ subnet capacity. |
| Choosing overlay or underlay without naming the tradeoff | A default CNI is accepted as a product choice instead of an architecture choice. | Record how the model affects IP consumption, observability, load balancing, policy, and portability. |
| Making the API endpoint private before access paths exist | Security hardening is applied before VPN, bastion, CI, or GitOps access has been tested. | Build and test the private administration path, then switch endpoint exposure deliberately. |
| Letting every private subnet use NAT for cloud services | Default routes work, so teams miss endpoint options until the bill arrives. | Add provider-native endpoints for high-volume cloud services such as object storage, registry, logs, and identity. |
| Treating Transit Gateway as one flat network | Centralized routing is easier to connect than to segment. | Use route-table separation and explicit propagation rules for each trust zone. |
| Publishing Services with public load balancers by accident | Example manifests use `LoadBalancer` without explaining internal versus public schemes. | Require ingress review, internal annotations where appropriate, Gateway API policy, and ownership labels. |
| Debugging from application logs only | Network symptoms appear in app logs, but root cause lives in events, routes, endpoints, or flow logs. | Trace the path through Kubernetes objects and cloud network evidence before changing application code. |

## Knowledge Check

<details>
<summary>1. A cluster has plenty of CPU and memory, but new Pods fail with IP assignment errors. Diagnose the likely VPC topology issue.</summary>

The likely issue is subnet or pod-address exhaustion in a VPC-native CNI model. The scheduler may find node resources, but the CNI still needs an available address for each Pod. Check CNI events, node IP allocation, subnet free-address metrics, and whether prefix delegation or larger pod ranges are configured. Adding nodes can make the problem worse if each node consumes more addresses from the same exhausted subnet.
</details>

<details>
<summary>2. Design a safer private-cluster administration path before disabling the public API endpoint.</summary>

Provide at least one tested private access path, such as VPN or private connectivity for administrators, a hardened bastion, in-VPC CI runners, or a GitOps controller that operates from inside the network. Confirm `kubectl` access through the private route, document break-glass access, and verify worker-node control-plane communication before disabling public endpoint access.
</details>

<details>
<summary>3. Compare underlay and overlay networking for a Kubernetes platform that has limited RFC 1918 address space but needs strong cloud flow-log visibility.</summary>

Overlay networking reduces pressure on scarce cloud subnet space because Pods use cluster-managed addresses, but cloud flow logs usually show node tunnel traffic rather than individual Pod addresses. Underlay improves cloud-native visibility and direct Pod integration, but it consumes VPC addresses quickly. The decision requires choosing which constraint is more important and adding compensating controls for the weaker side.
</details>

<details>
<summary>4. Evaluate whether VPC endpoints can reduce NAT gateway cost for a private cluster that pulls images and writes logs frequently.</summary>

VPC endpoints are likely a strong fit for high-volume provider services such as container registry, object storage, logging, secrets, and identity APIs. Moving that traffic to private endpoints can reduce NAT data-processing charges and keep traffic on private provider paths. The team still needs NAT or an egress proxy for true internet and SaaS destinations.
</details>

<details>
<summary>5. Diagnose why a Service has no reachable backends even though Pods exist in the namespace.</summary>

First compare Service selectors with Pod labels and inspect endpoints. The Service may select the wrong labels, Pods may be failing readiness, or the Service may be in a different namespace. If the Service has endpoints but clients still fail, continue to NetworkPolicy, security groups, route tables, DNS, and load balancer target health.
</details>

<details>
<summary>6. Choose between VPC peering and a transit gateway for eight VPCs across development, staging, production, and shared services.</summary>

Eight VPCs would require many pairwise peering connections and route-table updates, so a hub-and-spoke transit design is usually easier to operate. The transit layer should not be flat; use route tables and propagation rules to segment production, development, shared services, and inspection paths. Cost and data-processing charges still need review.
</details>

<details>
<summary>7. Implement a debugging sequence for a Pod that can not call an external SaaS API from a private subnet.</summary>

Check DNS resolution from a test Pod, NetworkPolicy egress rules, Pod security context if a proxy is required, route table default routes, NAT gateway health, endpoint policies for provider services, security groups, and flow logs. If the organization requires proxy egress, verify the Pod has proxy environment variables and that policy allows traffic only to the proxy.
</details>

## Hands-On Exercise: Review a VPC Topology for Kubernetes

This exercise is a design review rather than a live cloud deployment. You will evaluate a proposed topology, identify risks, and write concrete changes. Use a scratch file or architecture decision record format. The goal is to practice the review questions before real cloud resources make mistakes expensive.

```text
Scenario

The platform team is designing a production Kubernetes VPC.

Inputs:
  - Three availability zones
  - One managed Kubernetes cluster
  - Maximum 36 worker nodes
  - Target 45 Pods per node
  - VPC-native Pod networking
  - Private worker nodes
  - Private cluster API endpoint desired
  - Heavy image pulls from the cloud container registry
  - Logs shipped to the provider logging service
  - Occasional calls to external SaaS APIs
  - Production must reach shared observability services
  - Development must not reach production databases

Initial proposal:
  - VPC CIDR: 10.20.0.0/20
  - Three private node subnets: /24 each
  - Three public ingress subnets: /27 each
  - NAT gateway in every AZ
  - No VPC endpoints
  - Public and private Kubernetes API endpoint
  - VPC peering to development and shared services
```

Your first review should focus on address capacity. Thirty-six nodes times forty-five Pods is 1,620 Pod addresses before node addresses, load balancers, endpoints, and headroom. Three `/24` private subnets provide far less usable room than a comfortable VPC-native design needs. Recommend larger private subnets, dedicated pod ranges where the provider supports them, prefix delegation where appropriate, or an overlay model if address space can not be expanded.

Your second review should focus on egress. Heavy registry pulls and provider logging are strong candidates for private endpoints. NAT may still be needed for SaaS APIs, but provider-service traffic should not blindly cross NAT gateways if private endpoints are available. Document endpoint subnets, security groups, endpoint policies, and route-table changes so the design is auditable.

Your third review should focus on operations. If the team wants a private API endpoint, it needs private administrator and CI/CD paths before the public endpoint is removed. If peering connects development, production, and shared services, document why peering is still manageable and how routes prevent development from reaching production databases. If that policy is hard to express with peering at current scale, recommend transit routing with separate route tables.

```bash
alias k=kubectl

# Evidence you would collect during a real incident
k get pods -A -o wide
k describe pod <pending-pod> -n <namespace>
k get svc,endpoints -n <namespace>
k get networkpolicy -A
k logs -n kube-system -l k8s-app=aws-node --tail=100
```

Before committing to a production VPC topology or cluster network architecture, platform architects must systematically evaluate common cognitive traps regarding subnet sizing, encapsulation boundaries, private control-plane reachability, and egress data paths. Auditing these failure layers ensures engineering teams build resilient cloud networking baselines while avoiding dangerous assumptions about address allocation, network observability, administrative access, and data-processing charges.

**Card A: Adding worker nodes (or turning on prefix delegation) fixes IP exhaustion even when the subnet has no contiguous addresses left.** A platform engineering team observes that newly deployed application Pods remain in Pending states during a high-traffic scaling event. Noticing that existing worker nodes have high CPU utilization, the on-call engineer triggers the cluster autoscaler to provision additional EC2 worker instances and enables Amazon VPC CNI prefix delegation to expand Pod density. The engineer assumes that bringing up new compute capacity and enabling prefix delegation will immediately supply fresh IP addresses for the stalled workloads.

<details>
<summary>Check your prediction</summary>

Failure layer: Subnet address allocation mechanics and contiguous CIDR block fragmentation in cloud VPC subnets. Next action: calculate available contiguous `/28` blocks within existing subnets before turning on prefix delegation, provision larger dedicated secondary subnets for Pods, or migrate workloads to non-fragmented subnets where the CNI can allocate contiguous blocks without encountering `InsufficientCidrBlocks` errors.
</details>

**Card B: Overlay Pods remain directly visible in VPC flow logs as individual Pod IPs.** A security and compliance team requires full audit logging of all inter-service network conversations at the individual container level. To conserve limited RFC 1918 private address space, the platform architects deploy an encapsulated overlay CNI where Pods receive internal, cluster-managed IP addresses. The security team configures cloud VPC flow logs on the worker node subnets, expecting the VPC flow logs to record the individual Pod source and destination IP addresses for every microservice request.

<details>
<summary>Check your prediction</summary>

Failure layer: Network packet encapsulation boundaries and cloud network visibility limits of overlay CNIs. Next action: deploy eBPF-based in-cluster observability tooling (such as Cilium Hubble or Tetragon) or service mesh telemetry to capture pod-level network flows, or implement an underlay/VPC-native CNI model if cloud VPC flow logs and cloud security groups must natively inspect individual Pod IP addresses.
</details>

**Card C: Private worker nodes keep the Kubernetes API reachable from an internet laptop without a private admin path.** A security architect hardens an EKS cluster by deploying all worker nodes into private subnets without public IP addresses. To minimize external attack surface, the operations team also sets the cluster endpoint configuration to private-only access, turning off the public API server endpoint. An operator working remotely from an internet-connected laptop prepares to run scheduled `kubectl` deployment updates against the cluster without connecting to an enterprise VPN, private bastion, or direct connectivity circuit.

<details>
<summary>Check your prediction</summary>

Failure layer: Control-plane endpoint exposure modes versus worker-node subnet placement. Next action: establish a validated private administrative access path—such as an AWS Client VPN, an in-VPC bastion host with SSM Session Manager, or in-VPC CI/CD runners and GitOps agents—before disabling public API server endpoint access, or configure public endpoint CIDR restrictions to limit internet access while preserving private node-to-control-plane communication.
</details>

**Card D: A NAT gateway means registry pulls and provider logging from private nodes never need VPC endpoints.** A financial platform deploys worker nodes in private subnets and provisions a managed NAT gateway in each availability zone to provide outbound internet connectivity. Because all outbound traffic—including container image pulls from Amazon ECR, object storage access in Amazon S3, and telemetry shipping to Amazon CloudWatch—successfully reaches its destination through the NAT gateways, the infrastructure team concludes that deploying AWS VPC endpoints would be redundant and unnecessary.

<details>
<summary>Check your prediction</summary>

Failure layer: Cloud egress traffic routing topology and data-processing cost structures of managed NAT gateways. Next action: provision VPC gateway endpoints for S3 and interface endpoints (AWS PrivateLink) for ECR, CloudWatch Logs, and STS, routing high-volume cloud provider traffic over private backbones to eliminate recurring per-gigabyte NAT data-processing charges and cross-AZ transit costs.
</details>

**Success Criteria**:
- [ ] Calculate whether the proposed private subnets can support the target node and Pod density with growth headroom.
- [ ] Decide whether underlay or overlay networking better fits the stated constraints, and document the tradeoff.
- [ ] Define the private API endpoint access path for administrators and CI/CD.
- [ ] Identify which high-volume provider services should use private endpoints instead of NAT.
- [ ] Choose a multi-VPC routing model and state the segmentation rule for production versus non-production networks.
- [ ] Write the first five debugging commands or evidence sources you would use during an IP assignment or egress incident.

## Next Module

Continue to [Advanced Operations](../../advanced-operations/) to scale these architectural decisions beyond a single cluster — multi-account strategies, transit-hub networking, cross-cluster service discovery, and disaster recovery at enterprise scale.

## Sources

- [Amazon EKS: Amazon VPC CNI plugin](https://docs.aws.amazon.com/eks/latest/userguide/pod-networking.html) — Explains VPC-native Pod networking behavior and Amazon VPC CNI concepts.
- [Amazon EKS: Increase available IP addresses for Pods](https://docs.aws.amazon.com/eks/latest/userguide/cni-increase-ip-addresses.html) — Documents prefix delegation and approaches for increasing Pod IP capacity.
- [Amazon EKS: Prefix mode for Linux](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html) — Explains `/28` prefix delegation behavior and ENI slot limits on Nitro instances.
- [Google Kubernetes Engine: VPC-native clusters](https://cloud.google.com/kubernetes-engine/docs/concepts/alias-ips) — Describes alias IP ranges for GKE Pods and Services.
- [Google Kubernetes Engine: Configure maximum Pods per node](https://cloud.google.com/kubernetes-engine/docs/how-to/flexible-pod-cidr) — Documents per-node pod CIDR sizing and secondary range planning.
- [Azure Kubernetes Service: Azure CNI networking](https://learn.microsoft.com/en-us/azure/aks/concepts-network-azure-cni-pod-subnet) — Covers Azure CNI behavior and Pod subnet planning.
- [Azure Kubernetes Service: Azure CNI Overlay](https://learn.microsoft.com/en-us/azure/aks/concepts-network-azure-cni-overlay) — Compares overlay pod CIDR allocation with flat VNet pod addressing.
- [Google Cloud: Cloud NAT overview](https://cloud.google.com/nat/docs/overview) — Describes Cloud NAT gateway billing components and outbound SNAT behavior.
- [Azure NAT Gateway overview](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview) — Documents Azure NAT Gateway outbound connectivity and data-processing charges.
- [Kubernetes: Services](https://kubernetes.io/docs/concepts/services-networking/service/) — Defines Service routing, selectors, and stable networking for Pods.
- [Kubernetes: Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — Explains Kubernetes-native traffic policy controls.
- [Gateway API documentation](https://gateway-api.sigs.k8s.io/) — Provides the upstream Gateway API model for role-oriented ingress and routing.
- [Amazon EKS: Cluster endpoint access control](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html) — Documents public and private Kubernetes API endpoint options.
- [AWS: VPC endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints.html) — Explains endpoint types for private access to AWS services and endpoint services.
- [AWS: NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html) — Documents NAT gateway behavior for private subnet internet egress.
- [AWS Transit Gateway documentation](https://docs.aws.amazon.com/vpc/latest/tgw/what-is-transit-gateway.html) — Covers hub-and-spoke routing between VPCs and networks.
- [AWS Direct Connect documentation](https://docs.aws.amazon.com/directconnect/latest/UserGuide/Welcome.html) — Describes dedicated private connectivity for hybrid cloud designs.
