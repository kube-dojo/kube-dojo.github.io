---
title: "Are You Ready for On-Prem Kubernetes?"
sidebar:
  order: 1
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45–60 minutes
>
> **Prerequisites**: Kubernetes cluster administration fundamentals, basic Linux operations, and familiarity with networking concepts such as IP addresses, routes, and subnets. Review [Linux Deep Dive](/linux/) when host-level behavior is unfamiliar.

## Learning Outcomes

By the end of this readiness bridge, you will be able to:

- Map hardware fault domains such as hosts, racks, power feeds, and switches to Kubernetes placement and recovery decisions.
- Trace a PXE provisioning workflow from DHCP and boot services through operating-system installation and cluster enrollment.
- Distinguish BGP route advertisement, virtual IP ownership, and external load balancing when selecting a service-exposure design.
- Evaluate distributed-storage and etcd quorum placement against the actual rack and network failure domains.
- Select a sequenced study plan for Linux, planning, provisioning, networking, storage, and multi-cluster patterns.

## Why This Matters

Managed Kubernetes makes a useful boundary visible: you create workloads and services, while a provider owns much of the infrastructure needed to keep the control plane and worker fleet available. That boundary is a product feature, not evidence that hardware, networking, storage, or control-plane failure modes have disappeared. A managed service simply assigns responsibility for those layers to someone else and exposes a narrower operational interface.

When you own the machines, the boundary moves. A node is no longer an abstract instance that can be replaced by an API request; it is a server with firmware, disks, memory, network cards, cables, cooling, and a location in a rack. A cluster design must account for who can replace a failed component, how a replacement joins safely, which workloads can tolerate the event, and what must remain reachable while the repair is underway.

This bridge helps you decide what to study before treating an on-premises cluster as a larger version of a cloud cluster. It is a navigation and diagnostic page, not a complete build guide. Each section introduces a decision, a common failure in the reasoning process, and a specific destination where you can develop the skill further. Use it to find gaps, then follow the learning path in order.

The key shift is from asking only whether Kubernetes can reschedule a pod to asking whether the underlying failure domain still has power, a working network path, sufficient storage replicas, and a control plane able to make decisions. Kubernetes can react only when its own dependencies remain available enough to report state and perform recovery. Infrastructure ownership means you must make those dependencies explicit before an outage tests them.

Consider how much of a typical cloud workflow is hidden by convenient abstractions. A cloud load-balancer object can request provider integration, a volume claim can result in a managed disk, and a node group can replace an instance. On-premises, those outcomes require a designed path through switches, storage devices, physical inventory, provisioning systems, and operating procedures. The API objects may look similar while the failure and repair responsibilities differ substantially.

**Readiness check:** write down the infrastructure boundary for your current cluster. For each of compute, network, storage, control plane, and physical repair, name the team that owns the decision and the team that performs the recovery. If a line has no owner, mark it as a study or organizational gap rather than assuming another layer will absorb the work.

## Diagnostic — Are You Ready?

Use this checklist to locate topics for deeper study. A checked item means that you can explain the decision and its failure consequences, not merely recognize the vocabulary or point to a product name. Keep unchecked items visible; the purpose is to order learning, not to grade past experience.

- [ ] I can sketch a spine-leaf network and mark racks, top-of-rack switches, uplinks, routing boundaries, and paths between nodes.
- [ ] I can explain how DHCP, firmware network boot, PXE or iPXE, an installer, and host enrollment fit together in a repeatable provisioning flow.
- [ ] I can describe how failed disks, NICs, DIMMs, and complete hosts are identified, replaced, and returned to service without a hand-crafted rebuild.
- [ ] I can estimate CPU, memory, disk, network, and accelerator capacity for sustained workloads, while accounting for reservations and maintenance headroom.
- [ ] I can explain how BGP advertisements from a Kubernetes environment affect upstream routers and how policy limits the announced prefixes.
- [ ] I can distinguish a control-plane VIP, a service address, and an external load balancer, then identify which component owns each responsibility.
- [ ] I have operated or studied a distributed-storage system beyond its initial installation, including degraded state, replacement, recovery, and upgrade planning.
- [ ] I can map etcd members and storage replicas to physical racks and explain what quorum remains after a rack or network partition fails.
- [ ] I know how a loss of rack power, a switch restart, or a degrading storage backplane would be detected and which workloads would be affected.
- [ ] I can separate workload availability from infrastructure availability when the control plane and its dependencies are self-managed.
- [ ] I can explain the procurement, delivery, burn-in, spare-parts, and replacement lead times that constrain capacity recovery.
- [ ] I have a plan for hardware health monitoring, firmware drift, physical inventory, access control, and repair escalation.

If several boxes remain unchecked, begin with Linux and planning before selecting products. If the gaps are concentrated in a single layer, study that layer and return to the checklist with a concrete design artifact. The sections below describe what each gap means and how adjacent layers interact, so that study time follows the system's dependencies rather than a collection of vendor names.

## The Readiness Gap: From Managed Boundary to Owned System

Readiness is not a binary measure of whether someone is capable of operating Kubernetes. It is a description of which operational boundaries the team can own safely today. A team may have strong API and workload skills while needing additional practice in storage repair, switch routing, host replacement, or out-of-band management. Naming this difference lets the team sequence work honestly without dismissing existing Kubernetes experience.

The underlying service still has the same broad layers: applications depend on Kubernetes objects, Kubernetes components depend on Linux hosts, hosts depend on physical resources, and communication crosses both virtual and physical networks. Managed environments often package many lower-layer responsibilities into service guarantees and provider APIs. An on-premises team must translate those same requirements into an architecture, ownership model, and operational runbook that its staff can execute.

The translation matters because symptoms cross boundaries. A service timeout may be caused by an application, a node route, a failed top-of-rack link, a misadvertised prefix, or an exhausted storage dependency. A pod restart may hide a host issue temporarily while doing nothing to restore a control-plane quorum. Strong operators move from symptom to dependency without assuming the Kubernetes object that reports the symptom is the layer that caused it.

This is also why a product list cannot substitute for a design. Choosing a CNI, storage operator, or provisioning framework does not establish that the rack layout is resilient, the upstream accepts the intended routes, the boot network is isolated, or the people on call can recover the service. Tools implement portions of a system; the team's work is to define their contracts and test what happens when one contract is unavailable.

### A layered ownership map

Start at the physical bottom and move upward. The facilities or data-center team may own electrical capacity and cooling; a hardware team may own server lifecycle; network engineering may own switching and routing; platform engineering may own host images, cluster lifecycle, and Kubernetes services. These boundaries vary by organization, so the diagram is a prompt for assignment, not a claim that every company uses identical teams.

```text
Application availability
        ↑ depends on
Kubernetes workloads, services, and control plane
        ↑ depends on
Linux hosts, container runtime, disks, and host networking
        ↑ depends on
Servers, NICs, racks, power, cooling, cables, and switches
        ↑ depends on
Facilities, inventory, procurement, access, and repair processes
```

Each upward dependency needs an observable health signal and a recovery owner. A hardware alert without a replacement path is only notification. A cluster alert without a way to tell whether a whole rack is unreachable may lead an operator to treat correlated failures as unrelated node events. A written map can expose these missing links before implementation begins.

An ownership map should include routine changes as well as emergencies. Firmware updates, switch configuration changes, disk replacement, route policy changes, and control-plane upgrades can each change availability even when no component has failed. Record who approves them, how the change is staged, which telemetry proves the result, and how the operator rolls back if the observed behavior differs from the plan.

## Hardware Fault Domains and Capacity

A fault domain is a group of components that can fail together because they share a dependency. Servers in one rack may share power distribution, cooling, cable trays, and a top-of-rack switch. Two nodes in separate racks may still share an upstream switch pair or a power room. A Kubernetes node label is useful only when it represents a real property that affects correlated failure or recovery.

Cloud infrastructure often presents zones or node pools as convenient placement labels. On-premises operators must discover what those labels mean physically. A zone could correspond to a room, a row, a set of racks, or merely an administrative grouping. Before relying on a topology label, verify its mapping with the infrastructure owners and document the smallest event that can take all members of that domain out of service together.

This distinction affects replicas and quorum. If three etcd members occupy three nodes but all nodes depend on one rack's power, those members do not provide three independent power failure domains. If storage replicas are spread across hosts that use the same switch, a switch outage can isolate all copies simultaneously. The count of replicas or nodes is less informative than the independence of their underlying paths and failure dependencies.

Capacity planning is part of the same reasoning. A cluster needs enough spare compute and storage capacity to tolerate a failure and still meet its workload objectives, but adding nominal capacity does not help when it is trapped behind the same failed resource. Reserve capacity by failure domain, account for workloads that cannot move freely, and include the capacity consumed during data recovery or hardware maintenance.

Hardware selection also shapes future operations. A server with locally replaceable drives, remote management, documented firmware, and predictable network interfaces may be easier to recover than a nominally faster system with scarce components or opaque management. Evaluate power draw, cooling, rack density, support arrangements, and spare availability alongside benchmark results. The best choice is the one that serves the workload and can be operated within the organization's support model.

An inventory is a technical dependency, not paperwork. Operators need to know which asset occupies a rack unit, which power feed and switch ports serve it, which firmware baseline applies, and which workloads depend on it. Serial numbers, component models, purchase dates, warranty state, and spare locations make a repair actionable. Without reliable inventory, even a correct alert may leave responders uncertain about which physical device to inspect.

**Predict:** three control-plane members are placed on separate hosts, but all three hosts share one rack and one top-of-rack switch. What outage can still remove quorum? The important answer is that physical separation between host names does not remove shared failure domains; the rack power or switch event can isolate every member at once.

The answer should lead to a topology review rather than an automatic conclusion that a particular number of racks is always correct. Consider which events are credible in the environment, what availability objective is required, and what independent network paths exist. A small lab may intentionally use one rack and accept that boundary. A production design must make the accepted correlated-failure risk visible and pair it with a recovery strategy.

For more detail on workload sizing, topology, and ownership economics, continue to [Planning & Economics](/on-premises/planning/). For host-level troubleshooting, device behavior, and the Linux networking foundation beneath Kubernetes, use [Linux Deep Dive](/linux/). These destinations complement each other: planning describes the intended capacity and failure boundaries, while Linux study helps explain the host behavior you observe during operations.

## Repeatable Provisioning: PXE Is a Workflow

In managed infrastructure, a replacement node may appear through a provider's node-group workflow. A physical server instead moves through a lifecycle: it is inventoried, connected to power and management networks, configured to boot, assigned an operating-system image, hardened, enrolled, and eventually joined to a cluster. PXE is one way to begin that process over the network; it is not the complete provisioning system by itself.

A common network-boot sequence involves firmware selecting a network interface, obtaining boot parameters through DHCP, retrieving a boot program, and then loading an installer or provisioning environment. The exact mechanisms depend on firmware, network services, security policy, and the chosen installer. PXE and iPXE can participate in different parts of the flow, while an operating-system installer applies host-specific configuration and writes the system to disk.

The essential operational property is reproducibility. A node should be rebuildable from reviewed configuration and known images rather than a remembered sequence of interactive console actions. Host identity, disk layout, network configuration, certificates, cluster role, and enrollment credentials all need a controlled source. A successful boot that depends on a technician remembering which screen to select is not yet a dependable fleet process.

Provisioning also crosses network trust boundaries. The boot network may handle machine discovery and deliver operating-system material before the host has joined the normal production network. DHCP reservations, boot-file selection, image repositories, installer metadata, and management interfaces therefore deserve deliberate isolation and access control. An attacker or misconfiguration that redirects boot traffic can affect a host before the cluster's normal admission controls are active.

Credentials need lifecycle rules. Bootstrap tokens or enrollment credentials should be limited in scope and lifetime, distributed through a controlled mechanism, and rotated or invalidated after use as appropriate to the chosen system. Image provenance and integrity checks should be part of the workflow. Automated installation speeds recovery only when the installed image and configuration are the intended ones, not merely the most recent files reachable on a server.

Design the maintenance path together with the initial path. Firmware settings can change after a board replacement, a storage controller may enumerate devices differently, or the boot order may be reset. The workflow needs a way to detect these conditions, report them, and stop safely. Automated provisioning should not silently overwrite the wrong disk or enroll an unknown machine because its network port happens to be active.

**Try it:** draw the steps from a boxed replacement server to a Ready Kubernetes node, marking every handoff between hardware, DHCP or boot services, operating-system configuration, security enrollment, and cluster lifecycle automation. Then identify which step is repeatable, which has a manual exception, and what evidence shows the machine received the intended image.

The deeper pathway is [Bare Metal Provisioning](/on-premises/provisioning/). Its PXE module focuses on boot protocols and installer flow, while the datacenter and declarative-lifecycle modules cover management interfaces, inventory, and repeatable changes. Start with the boundary that is least familiar, but eventually connect all three so that physical replacement does not create an undocumented gap between a working server and a usable Kubernetes node.

## Networking: BGP, VIPs, and Service Exposure

In a cloud environment, a Service of type LoadBalancer may trigger an integration that allocates an address and arranges reachability. On-premises, Kubernetes cannot make an upstream router learn a route unless some component advertises it or the surrounding network is configured another way. The operator must understand both the cluster's service model and the physical routing domain through which clients reach the address.

BGP is a routing protocol through which networked systems exchange reachability information under policy. When a Kubernetes-adjacent speaker advertises a service prefix or address to an upstream router, the router can install a path and direct traffic toward the cluster. With MetalLB in BGP mode, the routing behavior upstream changes because routers learn advertised routes from the cluster's BGP peers. That change must be coordinated with network engineering, prefix filters, route policy, and the intended return path.

An advertisement is not simply a heartbeat that makes an address exist. Operators must decide which addresses may be announced, which peers may receive them, what path attributes or policies apply, and how withdrawal behaves when a node or speaker becomes unavailable. A route can be accepted by one router and rejected by another, or traffic can reach the cluster while return traffic takes an incompatible path. A healthy service object therefore does not prove end-to-end reachability.

Virtual IP ownership is a different concern. A VIP gives clients a stable address whose active owner can move or be advertised as components change. For example, a control-plane VIP can provide a stable endpoint for API servers. kube-vip can provide virtual IP functionality for Kubernetes control-plane or service-related use cases, depending on its configuration. It does not automatically replace every routing policy or every external traffic-management function required by an organization.

MetalLB addresses a different portion of the problem by providing external address allocation and advertisement for Kubernetes services on networks without a cloud load-balancer integration. In Layer 2 mode, the mechanism for attracting traffic differs from BGP mode. In BGP mode, peers receive routes and upstream routing state changes. Selecting a mode means selecting network behavior, not just toggling a deployment preference.

An external load balancer is a separate architecture option. A hardware appliance or software load-balancer tier outside the cluster can own a frontend address, health-check backends, terminate or pass through connections, and apply organization-specific policy. It may be preferred where network teams already operate a shared service, need features beyond Kubernetes service handling, or want a clear separation between cluster and perimeter responsibilities. It also becomes another system with capacity, configuration, and failure modes to operate.

These tools can coexist because their responsibilities differ. A cluster API endpoint may need a control-plane VIP; application services may use MetalLB announcements; an external load-balancer tier may provide shared ingress or security policy. They can also be alternatives for a specific responsibility. Before choosing, write down the client, destination address, protocol, route owner, health-check signal, failover mechanism, and team responsible for each hop.

```text
Client → upstream route or external frontend → node or VIP owner
       → Kubernetes service dataplane → selected workload endpoint

Control-plane client → stable API VIP → available API server members
```

The drawing is intentionally generic: the actual packet path depends on the selected network plugin, service implementation, advertisement mode, and external devices. Use it to ask where state lives and what changes after a node, route speaker, or load-balancer member fails. A route that still points toward an unreachable next hop is not useful merely because the route remains present in a table.

**Predict:** a MetalLB BGP speaker advertises a service address, then the only node advertising that path loses its uplink. Which systems need to react? Consider route withdrawal or alternate announcements, the router's convergence, the service's available endpoints, and whether clients can use a remaining route. This is a cross-layer recovery question, not a single Kubernetes health check.

Network readiness also includes ordinary Linux operations. Operators need to understand interface state, routes, neighbor discovery, DNS resolution, MTU, firewall rules, and packet paths on the host. An overlay can obscure the physical source of a dropped packet, while a mismatch between underlay and overlay assumptions can cause symptoms that appear only for larger packets or cross-rack flows. Linux networking knowledge makes it easier to isolate the layer where a path stops working.

Follow [On-Premises Networking](/on-premises/networking/) for datacenter topology, BGP, and load-balancer patterns. Follow [Linux Deep Dive](/linux/) for the host-level tools and concepts that support packet-path diagnosis. When planning, do not record merely that the network team approved the design; capture which prefixes, peers, VLANs, and failure transitions they reviewed and what evidence would prove each is working.

## Storage: Data Placement and Repair

Cloud block storage often appears as a request for a volume, with the provider handling device placement and much of the underlying repair process. On-premises, a storage class may be backed by local disks, a network appliance, a software-defined storage cluster, or another design. Each option puts different responsibilities on the platform team and different dependencies into the workload's path to durable data.

Distributed storage uses multiple components and placement rules to keep data available or recoverable when devices fail. The exact guarantees depend on the system and configuration. Replication, erasure coding, failure-domain placement, network separation, and recovery behavior are choices with tradeoffs in capacity, latency, bandwidth, and operational complexity. A label such as “replicated” does not by itself prove that copies survive the failure the service objective cares about.

Placement must reflect physical reality. If replicas intended to survive a rack event are all placed on devices in that rack, the policy does not match the required failure domain. If clients, storage monitors, and data daemons share a congested or fragile network path, recovery traffic may compete with workload traffic. Operators should understand which physical and logical domains the storage system recognizes and how those labels are maintained when equipment moves.

Recovery is an active workload. Replacing a failed device can trigger data movement, integrity checks, or rebuild traffic, depending on the storage design. That work consumes network, disk, and compute resources while applications continue to run. An architecture should account for the performance impact, alerting thresholds, maintenance windows, and operator actions associated with degraded state. The team should know when to wait, when to replace hardware, and when an automated recovery needs human intervention.

Storage also reaches beyond the storage cluster. Kubernetes applications may depend on CSI drivers, volume attachment, filesystem behavior, node identity, and a compatible kernel. A volume that is healthy at the backend can still be unavailable to a pod if a host cannot attach or mount it. Conversely, an application-level write failure can originate in capacity pressure, latency, a path outage, or an unsafe filesystem assumption. Troubleshooting needs evidence from both the workload and storage layers.

Do not make a first stateful workload the test of whether the design is production-ready. Begin with a defined data-loss objective, recovery-time objective, expected workload profile, backup policy, and restore test. Replication is not a backup if a logical deletion or corrupted write is faithfully copied to every replica. A recovery plan should include an independently protected copy and a demonstrated method to restore it into a usable application state.

**Try it:** choose one stateful workload and write its volume path from application to physical device. Mark every component whose failure could prevent reads or writes, then mark where a second copy lives. If the answer depends on an undocumented default, record that as a question for the storage design rather than treating it as a guarantee.

The destination is [On-Premises Storage](/on-premises/storage/), where the modules compare architectural choices and develop Ceph, Rook, local-storage, object-storage, and database-operation skills. The right next module depends on the current design: someone deciding whether a local or distributed architecture fits should study the architecture decisions first, while an operator inheriting a Ceph cluster should focus on its health, data placement, and repair workflow.

## Control-Plane Quorum Across Racks

Kubernetes control-plane components rely on etcd for consistent storage of cluster state in common self-managed control-plane architectures. Etcd uses a quorum-based consensus protocol: a cluster must retain a majority of its members to commit changes. Adding members can increase the number of failures a cluster tolerates only in specific ways; it also adds communication and operational complexity, so member count alone is not a substitute for placement design.

For an odd-sized group, quorum is the majority of configured members. If a cluster has three members, it needs two participating members to retain quorum. If two members become unreachable together, the remaining member cannot independently continue committing state. This is why a three-member group placed in three racks can tolerate one isolated rack loss only if the surviving members still have their required network paths and the failure does not affect another shared dependency.

Rack placement is necessary but not sufficient. Members need reliable network connectivity and suitable storage performance, and the control plane needs a stable endpoint so clients can reach available API servers. Two racks may share an upstream switch, power subsystem, or room. A partition can also divide members into groups that cannot establish a majority. Document which single events the design is intended to tolerate and which events are accepted limitations.

Quorum should be considered with workload placement, storage, and maintenance. Draining a rack for planned work can remove a member or interrupt communication just as an unplanned failure can. A sequence of maintenance actions that is safe one node at a time may become unsafe if two members are unavailable concurrently. The operational procedure must verify current membership and health before changing another member, and it must preserve an available recovery path if an upgrade or repair fails.

Control-plane availability is distinct from application availability. Existing workloads may continue running for some period when the API is unavailable, but operators may lose the ability to schedule, update, or inspect resources. Some controllers and automation depend on API access to react to changes. A design review should name the behavior the organization requires during control-plane loss instead of treating “pods are still running” as equivalent to a healthy cluster.

The same physical topology influences storage quorum and application replicas. Placing etcd, storage daemons, and critical workloads without a shared map can create conflicting assumptions: each subsystem may believe it has spread copies, while all copies depend on one network or power boundary. A placement review should overlay these systems on the racks and paths, then examine the combined effect of losing each relevant domain.

**Predict:** a three-member etcd group has one member per rack, but the racks use a shared pair of core switches and one upstream power system. Which failures are covered by the placement, and which are not? The placement improves isolation from a single rack event, but a shared core or power failure can still remove more than one member's communication or availability.

For broader topology, placement, and cluster-lifecycle choices, continue through [Planning & Economics](/on-premises/planning/) and [Multi-Cluster Patterns](/on-premises/multi-cluster/). A second cluster can reduce a particular blast radius or enable a recovery plan, but it does not automatically make data consistent, route traffic correctly, or restore an application. Multi-cluster readiness builds on sound single-cluster dependencies rather than replacing them.

## Turning Gaps Into a Readiness Plan

A checklist becomes actionable when an unchecked answer produces a bounded learning task and a piece of evidence. “Learn BGP” is too broad to guide a review. “Explain which service prefixes a cluster advertises, identify the peer policy that permits them, and describe what changes when the only advertising node fails” gives the learner a testable goal and gives a network reviewer a concrete point to confirm.

Use a similar standard for physical systems. “Understand hardware” can mean anything from knowing component names to coordinating safe replacement during business hours. A useful readiness task could be to trace one server from its inventory record to its rack position, management interface, switch ports, power feeds, and workload role. That exercise reveals missing records as well as missing technical skills, which may require different owners to resolve.

Prioritize gaps by dependency and consequence. A weakness in basic Linux networking can make later BGP troubleshooting much harder because the learner cannot yet distinguish a host route from an upstream route. An unclear storage recovery process can make a stateful workload unsafe even if application teams understand Kubernetes well. Sequence prerequisites first, then practice the cross-layer decision that makes each topic operationally meaningful.

Readiness is also organizational. A design may be technically sound while no team is authorized to change a route, replace a drive, rotate a bootstrap credential, or approve a maintenance window. Record the service owner, operational owner, escalation path, and decision authority for each critical dependency. If ownership is shared, define the handoff and the information required so that an incident does not begin with a search for the person who can act.

Avoid using course completion as the only measure of readiness. A learner may finish a module without having access to a representative environment, and an experienced operator may already demonstrate the skill through prior work. Prefer observable evidence: a reviewed topology diagram, a provisioning rehearsal, a route-policy walkthrough, a storage restore record, or a maintenance plan that preserves quorum. The evidence should be recent enough to match the systems the team actually operates.

Set a review point after each learning stage. Once Linux troubleshooting is stronger, revisit the provisioning path and test whether host configuration now makes sense. After networking study, revisit the service exposure map with the router owner. After storage study, ask whether a restore drill meets the workload's recovery objective. Returning to earlier questions is useful because the new understanding can reveal assumptions that were invisible during the first pass.

For a team, the map can become a small readiness backlog. Give each item an owner, a target artifact, a reviewer, and a condition for closure. Keep unknowns visible rather than translating them into optimistic defaults. When an item depends on a vendor or infrastructure team, write down the needed answer and who will obtain it. This preserves momentum while showing which decisions cannot be completed by the Kubernetes team alone.

### Decide what “ready” means for the first workload

The readiness bar should reflect the first workload's needs. A development cluster used for disposable experiments can accept more manual repair and a narrower availability objective than a cluster holding customer-facing state. That does not make the development design careless; it means the team should state its limits, prevent accidental use beyond them, and ensure that test data can be discarded or recreated.

For a production candidate, write measurable objectives before choosing a topology. Specify the expected restoration time, acceptable data loss, maintenance tolerance, external reachability requirements, and the events the cluster must survive. Objectives force tradeoffs into the open: stronger isolation can require more hardware, more capacity headroom can increase cost, and additional automation can improve repeatability while creating another component that itself needs monitoring and maintenance.

Then work backward from each objective to evidence. If a service must remain reachable after one rack is unavailable, show the route, endpoint, node placement, and workload capacity that support that claim. If stored data must be recoverable after a device failure, show the placement policy and the repair or restore process. If operators must make changes during control-plane disruption, state which actions remain possible and which must wait for quorum restoration.

A readiness review should distinguish designed behavior from demonstrated behavior. A diagram can show that members are intended to be separated, but a controlled exercise can reveal that a shared switch or stale route defeats the separation. A runbook can list a restore command, but a drill can show that credentials, network access, or application consistency are missing. Use reviews and simulations to discover these gaps while the team can still change the design safely.

The first deployment is a chance to bound scope. Select a workload with representative but understood requirements, validate the entire operational path, and avoid adding unrelated complexity before the basic failure and recovery model is proven. The objective is not to eliminate every possible failure. It is to know which events are covered, which are not, what signal reveals the difference, and how the responsible team responds.

## Did You Know?

- **Quorum means a majority:** etcd documents that a cluster needs a majority of members to agree on updates; for three members, two must remain available for quorum. Use the etcd FAQ in Sources [1] when validating a topology calculation.
- **BGP is an upstream change:** MetalLB's BGP documentation describes peering with routers and advertising service IP reachability, so a BGP-mode deployment changes routing information beyond the Kubernetes API. See Sources [2], [3], and [4].
- **PXE relies on a chain:** the PXE DHCP options and UEFI network-boot specifications define pieces of a boot process, while the installer and host configuration remain separate steps. Review Sources [5] and [6] before designing a complete workflow.
- **Storage copies have placement semantics:** Ceph's CRUSH documentation describes rules for mapping data to devices and failure domains, which means copy count must be reviewed alongside placement topology. See Source [7].

## Skills Gap Map

| What you have | What you need | Where to study it |
|---|---|---|
| Kubernetes API fluency | Physical infrastructure ownership | [Planning & Economics](/on-premises/planning/) |
| CKA-style cluster operations | Linux host and kernel confidence | [Linux Deep Dive](/linux/) |
| Managed node groups | Bare-metal provisioning workflow | [Bare Metal Provisioning](/on-premises/provisioning/) |
| Cloud load balancers | BGP, VIPs, and bare-metal service exposure | [On-Premises Networking](/on-premises/networking/) |
| Cloud block storage | Ceph and distributed-storage operations | [On-Premises Storage](/on-premises/storage/) |
| Cloud failure domains | Rack, power, switch, and disk fault domains | [Planning & Economics](/on-premises/planning/) |
| Managed control-plane expectations | Self-managed control-plane lifecycle | [Bare Metal Provisioning](/on-premises/provisioning/) |
| Single-cluster administration | Multi-cluster recovery and placement patterns | [Multi-Cluster Patterns](/on-premises/multi-cluster/) |
| Application troubleshooting | Infrastructure troubleshooting below Kubernetes | [Linux Deep Dive](/linux/) |
| Cloud cost awareness | Capital expense, depreciation, spares, and utilization | [Planning & Economics](/on-premises/planning/) |

Use the map as a routing aid rather than a rigid curriculum. A platform engineer may already know Linux and need networking depth; a Kubernetes administrator may know service objects well but have no experience with upstream route policy. Record the reason behind each chosen destination so that you can tell when a learning goal has been met and when a deeper module is still needed.

## Common Mistakes

| Mistake | Problem | Better approach |
|---|---|---|
| Treating different hosts as independent without checking rack and switch placement | Shared power, cooling, or network failures can remove several nominally separate nodes together. | Map physical dependencies and use topology labels that correspond to verified failure domains. |
| Treating PXE as the whole provisioning system | A boot protocol does not define trusted images, host configuration, credentials, or cluster enrollment. | Document and automate the full path from inventory and firmware through installation and node readiness. |
| Assuming MetalLB BGP only changes an in-cluster setting | Upstream routers learn routes, so filters, policy, convergence, and return paths affect external reachability. | Review peer configuration and route policy with network owners, then test announcement and withdrawal behavior. |
| Using kube-vip, MetalLB, and an external load balancer as interchangeable names | They can provide different address, routing, health-check, and traffic-management responsibilities. | Write the traffic path and assign an owner to every address, route, frontend, and backend decision. |
| Counting storage replicas without checking failure-domain placement | Copies may share the rack, switch, or power source that the design intends to survive. | Inspect placement rules and prove that copies occupy independent domains for the target event. |
| Placing etcd members on separate node names but not across correlated dependencies | Host count does not ensure quorum survives a rack, power, or network event. | Map member reachability to racks and shared upstream components, then calculate quorum for each failure. |
| Assuming Kubernetes rescheduling repairs every physical outage | Rescheduling cannot restore missing power, routes, storage access, or a functioning API quorum. | Pair workload recovery with infrastructure alerting, spare capacity, ownership, and repair procedures. |
| Treating replication as a complete data-protection plan | Replication may reproduce deletion or corruption and may not provide a separate point-in-time restore. | Define backup retention and prove restoration into an application-consistent state. |

## Sequenced Path

Follow this sequence when the gaps span multiple infrastructure layers. The order begins with host understanding, then planning, then repeatable machine lifecycle, and only afterward combines networking, storage, and multiple clusters. That progression keeps later design questions grounded in the behavior and dependencies of the systems that support them.

1. Start with [Linux Deep Dive](/linux/). Build confidence in processes, storage, networking, security, and troubleshooting on the hosts beneath the control plane. You do not need to finish every Linux module before continuing, but you should know how to inspect a host and reason about its network and devices.
2. Read [Planning & Economics](/on-premises/planning/). Convert workload needs into capacity, topology, lifecycle, and ownership choices before hardware selection. Include rack boundaries, maintenance headroom, spares, and the cost of operating the platform over its service life.
3. Work through [Bare Metal Provisioning](/on-premises/provisioning/). Learn how inventory, network boot, operating-system installation, and declarative lifecycle management turn a replacement machine into a known and recoverable node.
4. Study [On-Premises Networking](/on-premises/networking/). Connect physical topology to Linux interfaces, BGP advertisements, VIPs, service exposure, DNS, and the routing decisions made by external devices.
5. Study [On-Premises Storage](/on-premises/storage/). Compare storage models and learn the placement, monitoring, recovery, and maintenance work required to support stateful workloads.
6. Move to [Multi-Cluster Patterns](/on-premises/multi-cluster/). Extend lifecycle, routing, data-protection, and operational boundaries across clusters only after the single-cluster assumptions are explicit.

At each transition, produce an artifact that can be reviewed: a host troubleshooting note, a capacity model, a provisioning sequence, a packet-path diagram, a storage recovery plan, or a multi-cluster failure analysis. These artifacts make progress measurable and give network, facilities, storage, and platform teams a shared object to discuss. A course checklist becomes more useful when its answers point to design evidence instead of confidence alone.

## Quiz

Use each situation to check whether you can reason across the physical and Kubernetes boundaries. Select an answer before opening its explanation, then compare the choice with the failure domain or ownership detail that makes it correct. If two answers seem plausible, identify the assumption each one makes and decide which fact the design review must verify.

1. A team places three etcd members on three hosts in one rack and claims that it can tolerate losing one member. Which review response is strongest?

A) Accept the design because each host runs a different etcd process.
B) Check whether a rack or shared-switch failure can remove multiple members together.
C) Add more Kubernetes worker nodes so etcd can find replacement members automatically.
D) Disable persistence so a lost member can restart without checking quorum.

<details>
<summary>Answer</summary>

Correct answer: **B**. A is wrong because separate hosts can share rack power and network dependencies; C is wrong because worker capacity does not automatically replace etcd membership; D is wrong because persistence and quorum are central to control-plane state. The design must be evaluated against correlated physical failures, not host count alone.
</details>

2. A replacement server should join a cluster with minimal manual work. Which evidence best demonstrates a repeatable PXE-based provisioning process?

A) A technician can select the correct boot menu after consulting an informal chat message.
B) The machine receives an approved image and host configuration from a reviewed, traceable workflow.
C) DHCP is enabled on every production subnet so any new host can boot somewhere.
D) The first successful operating-system boot is treated as proof that enrollment is complete.

<details>
<summary>Answer</summary>

Correct answer: **B**. A is wrong because informal steps are difficult to reproduce and audit; C is wrong because broad boot access expands the trust boundary without proving correct provisioning; D is wrong because installation and Kubernetes enrollment are separate stages. A good workflow can identify the host, deliver known inputs, apply configuration, and verify readiness.
</details>

3. A platform team enables MetalLB in BGP mode for a new service range. Which change should the team expect to review outside the cluster?

A) Upstream routers may learn advertised routes for service addresses from BGP peers.
B) The Kubernetes API server changes every physical switch's VLAN configuration automatically.
C) The service IP becomes reachable from every network without route policy.
D) BGP advertisements replace application endpoint health checks and storage replication.

<details>
<summary>Answer</summary>

Correct answer: **A**. B is wrong because BGP route exchange does not configure VLANs; C is wrong because routers and filters still determine which paths are accepted; D is wrong because routing reachability does not establish application health or data durability. MetalLB BGP mode changes upstream routing information and must be designed with its peers and policies.
</details>

4. An architecture review proposes using kube-vip for the API endpoint, MetalLB for service addresses, and an existing external appliance for shared ingress. What is the best next step?

A) Reject the design because only one load-balancing product can exist in a cluster environment.
B) Document the responsibility and failure behavior of each address, route, frontend, and backend.
C) Assume all three systems perform the same function and choose whichever is installed first.
D) Move all service traffic through the API VIP because it already has a stable address.

<details>
<summary>Answer</summary>

Correct answer: **B**. A is wrong because distinct layers can coexist when their responsibilities are clear; C is wrong because the tools do not have identical roles; D is wrong because a control-plane endpoint is not a general application ingress design. A traffic-path diagram exposes overlap, missing ownership, and failover assumptions.
</details>

5. A distributed-storage system reports three copies of a volume, but all three devices are in one rack. Which conclusion follows?

A) The volume is guaranteed to survive any single infrastructure failure because it has three copies.
B) The copy count alone does not prove survival of a rack-level failure.
C) The cluster scheduler will move the data to another rack during a power outage.
D) Backups are unnecessary because storage replication exists.

<details>
<summary>Answer</summary>

Correct answer: **B**. A is wrong because the shared rack may remove access to every copy; C is wrong because data placement and repair require a functioning system and may not complete during an outage; D is wrong because replication can reproduce logical deletion or corruption. Verify the storage placement rule and test an independent restore process.
</details>

6. A team needs to maintain a rack that contains one member of a three-member etcd group. Which practice best reduces the chance of losing quorum during the work?

A) Start the maintenance without checking the other members because the rack is only one fault domain.
B) Verify membership and health, preserve two participating members, and avoid concurrent changes that remove another member.
C) Scale application replicas until their total equals the etcd member count.
D) Stop all etcd members so that none can become temporarily inconsistent.

<details>
<summary>Answer</summary>

Correct answer: **B**. A is wrong because the remaining members and their communication must actually be healthy; C is wrong because application replicas do not provide etcd quorum; D is wrong because stopping every member removes the majority needed to commit state. Safe maintenance checks the current state before taking another member or its network path offline.
</details>

7. An engineer identifies gaps in Linux troubleshooting, host installation, BGP service exposure, storage recovery, and multi-cluster operations. Which study plan best follows the dependencies in this bridge?

A) Begin with multi-cluster federation, then learn Linux only if a later error occurs.
B) Study Linux, planning, provisioning, networking, storage, then multi-cluster patterns.
C) Configure every tool in parallel and use the first workload failure to choose a learning order.
D) Skip planning and provisioning because Kubernetes objects describe physical machines completely.

<details>
<summary>Answer</summary>

Correct answer: **B**. This selects the sequenced study plan for Linux, planning, provisioning, networking, storage, and multi-cluster patterns. A is wrong because later fleet decisions depend on sound host and infrastructure understanding; C is wrong because parallel tool setup obscures dependencies and creates avoidable rework; D is wrong because Kubernetes objects do not define procurement, boot, routing, or physical repair. The sequence builds from Linux foundations through capacity and lifecycle before combining higher-level network, storage, and multi-cluster decisions.
</details>

## Hands-On Exercise

**Task:** Create a one-page readiness map for a hypothetical on-premises Kubernetes design. This is a design simulation, not a report of a real deployment or incident. Assume a small cluster spans multiple racks, uses PXE or a comparable network boot path, advertises some service addresses, runs stateful workloads, and operates its own control plane. Choose details only as needed to make the failure analysis concrete.

**Steps:**

1. Sketch hosts, racks, power feeds, top-of-rack switches, shared uplinks, control-plane members, storage components, and the route toward a client.
2. Write the host provisioning chain from inventory through operating-system installation and Kubernetes readiness; label credential, image, and approval boundaries.
3. Trace one client request from its network to a workload endpoint, identifying whether a VIP, BGP route, MetalLB, kube-vip, or external load balancer owns each step.
4. Select a single-rack loss and a single-storage-device loss. For each, state what becomes unavailable, what should continue, and which signal or operator action proves the system is recovering.
5. Compare the design to the checklist and choose the next learning destination for every unanswered question.

**Success Criteria:**

- [ ] Every host and stateful copy is associated with a named physical failure domain, and shared power or switch dependencies are visible.
- [ ] The provisioning path includes boot, trusted image or installer, host configuration, enrollment, and a readiness check.
- [ ] Each address and routing responsibility has a named owner, including the upstream behavior expected from BGP or an external load balancer.
- [ ] The etcd quorum calculation states which members remain reachable after the selected rack loss and names any shared dependency that could invalidate the calculation.
- [ ] The storage section distinguishes replica placement from backup and describes one restore or repair verification step.
- [ ] Each unresolved design assumption points to a relevant destination in the sequenced path.

**Verification:** review the map with someone who owns a different layer, such as networking, Linux operations, storage, or facilities. Ask that reviewer to choose one failure not already analyzed and trace its effects through the diagram. Revise any step where the owner, observable signal, route, or recovery action is unclear; then compare the revised map to the diagnostic checklist again.

## Sources

The following primary and vendor documentation links are copied from the linked on-premises and Linux curriculum pages. Use them to verify protocol behavior and product responsibilities before turning a readiness sketch into an implementation plan.

1. [etcd FAQ](https://etcd.io/docs/v3.5/faq/)
2. [MetalLB BGP Concepts](https://metallb.universe.tf/concepts/bgp/)
3. [MetalLB Configuration](https://metallb.universe.tf/configuration/)
4. [RFC 4271: Border Gateway Protocol 4](https://datatracker.ietf.org/doc/html/rfc4271)
5. [RFC 4578: DHCP Options for PXE](https://www.rfc-editor.org/rfc/rfc4578)
6. [UEFI Network Protocols, PXE, and HTTP Boot](https://uefi.org/specs/UEFI/2.11/24_Network_Protocols_SNP_PXE_BIS.html)
7. [Ceph CRUSH Map](https://docs.ceph.com/en/latest/rados/operations/crush-map/)
8. [kube-vip static pod installation](https://kube-vip.io/docs/installation/static/)
9. [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
10. [Ubuntu autoinstall reference](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html)
11. [Cluster API](https://cluster-api.sigs.k8s.io/)
12. [Linux `ip route` manual](https://man7.org/linux/man-pages/man8/ip-route.8.html)
13. [Linux `ss` manual](https://man7.org/linux/man-pages/man8/ss.8.html)
14. [Kubernetes topology spread constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)

## Next Module

Start with [Planning & Economics](/on-premises/planning/) if the physical failure domains, workload capacity, or ownership model are not yet clear. If those decisions are already documented and the biggest gap is operating the Linux hosts, begin with [Linux Deep Dive](/linux/) and return to the sequenced path afterward.
