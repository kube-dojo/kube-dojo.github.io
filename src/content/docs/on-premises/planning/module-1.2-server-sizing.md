---
citations_verified: true
title: "Module 1.2: Server Sizing & Hardware Selection"
slug: on-premises/planning/module-1.2-server-sizing
sidebar:
  order: 3
---

> **Complexity**: `[COMPLEX]` | Time: 60 minutes
>
> **Prerequisites**: [Module 1.1: The Case for On-Premises K8s](../module-1.1-case-for-on-prem/), [Linux: Kernel Architecture](/linux/foundations/system-essentials/module-1.1-kernel-architecture/)

---

## What You'll Be Able to Do

After completing this module, you will be able to:

1. **Design** server configurations matched to specific workload profiles (CPU-bound, memory-bound, storage-bound, GPU-accelerated) and justify the CPU-to-RAM ratio you pick against the actual pod request distribution.
2. **Evaluate** hardware vendors and SKUs using benchmark data, fsync latency measurements, TCO projections, and three-to-five year growth assumptions, and reject configurations whose stranded capacity exceeds twenty percent.
3. **Configure** control-plane nodes with the NVMe storage, ECC RAM, dedicated CPU cores, and NUMA-aware topology that etcd needs to keep p99 commit latency under ten milliseconds at scale.
4. **Plan** a procurement order that sizes worker pools by workload profile, leaves N+2 failure headroom, and keeps the rack at sixty to seventy percent of its electrical and thermal budget so growth does not require a forklift upgrade.

---

## Why This Module Matters

**Hypothetical scenario (a composite of common on-prem sizing failures).** A logistics company orders twelve Dell PowerEdge R750xs-class servers for a new Kubernetes platform. Each server has dual 24-core Intel Xeon Gold 5317 processors, 256 GB of RAM, and four 1.92 TB SATA SSDs — roughly $216,000 of hardware. When the platform team deploys its first workloads — a real-time vehicle tracking system processing 50,000 GPS events per second — they discovered two critical mistakes that no amount of tuning could fix in software, because the constraints were physical.

First, the SATA SSDs could not keep up with etcd's fsync requirements. etcd commit latency exceeded 100 ms during peak hours, causing leader elections every few minutes. The API server became unreliable, deployments stalled mid-rollout, and the operations channel filled with `context deadline exceeded` errors that pointed at a healthy-looking control plane. They needed NVMe drives for the control-plane nodes — a $24,000 additional investment and two weeks of downtime for hardware replacement, plus a tense conversation with the procurement team about why "enterprise SSD" turned out not to be enough.

Second, the vehicle-tracking pods needed 2 GB of RAM each but only 0.5 vCPU — a 1:4 CPU-to-RAM ratio per pod. Their servers had a 1:2.7 ratio (96 vCPUs, 256 GB RAM), which is too CPU-heavy for this workload. They ran out of RAM with a third of CPU capacity unused. They had ordered compute-optimized servers for a memory-intensive workload, and the remaining CPU sat idle for the next three years while the procurement team explained to finance why they were buying additional RAM-heavy nodes when "the existing fleet has plenty of cores."

Hardware mistakes are expensive and permanent. You live with them for three to five years, every quarter, on every capacity-planning call, and they tend to compound: the wrong CPU-to-RAM ratio forces you to over-provision worker count, which forces you to over-provision the top-of-rack switch, which strands ports you cannot redeploy. This module teaches you how to size servers correctly the first time, by reasoning from the workload back to the silicon, not by picking a vendor reference design and hoping.

> **The Apartment Analogy**
>
> Buying servers is like signing a 3-year apartment lease. You cannot easily add rooms (RAM slots are finite), move walls (CPU sockets are fixed), or change the plumbing (storage bus is soldered to the motherboard). If you get it wrong, you either waste money on space you do not use or squeeze into space that is too small. Cloud is a hotel — daily rate, high markup, instant exit. On-prem is a lease, and the lease's commercial terms are set the day you sign the purchase order. Measure twice, buy once, and verify the measurement against a real workload trace before the requisition leaves your inbox.

---

## What You'll Learn

This module walks the silicon stack from the workload down. We start with what a modern two-socket server actually contains and why its NUMA topology matters more than most teams realize, then size the control plane (where etcd is the bottleneck and the API server is downstream of etcd's storage latency), then size worker pools by workload profile, then choose storage tiers and network speeds, and finally pull it all together in a procurement exercise. By the end you will be able to take a list of pod resource requests and produce a defensible bill of materials, including the spare capacity you intentionally leave behind.

- How to calculate CPU, memory, and storage requirements for Kubernetes nodes from real pod request data rather than vendor reference designs.
- NUMA architecture and why it can change in-memory database throughput by thirty to fifty percent on identical silicon.
- Control-plane sizing, with etcd's fsync behaviour as the binding constraint and the API server as a downstream consumer.
- Worker-node sizing strategies for the four workload profiles you will encounter in production: compute-heavy, balanced, memory-heavy, and storage-heavy.
- GPU node considerations for ML and AI workloads, including PCIe lane budgets and power envelopes that catch teams off guard.
- How to avoid the most common hardware mistakes, including the ones that pass procurement review because they look professional on a spec sheet.

---

## Server Architecture for Kubernetes

Before sizing anything, you need a clear mental model of what is physically inside a modern two-socket rack server and how the components are wired together, because Kubernetes scheduling decisions are ultimately constrained by that wiring. The CPU sockets do not share memory directly: each socket owns its DIMMs and reaches the other socket's DIMMs across an inter-socket interconnect that is roughly twice as slow as local memory. The PCIe lanes that connect NVMe drives and network cards are partitioned across sockets too, so a poorly placed NIC can force every storage request to cross the interconnect. These details look like trivia until you watch a Redis pod's p99 latency double because the kubelet placed it on the wrong socket.

### Anatomy of a Modern Server

The diagram below shows the layout of a typical 2U dual-socket server in the 2024–2026 generation: dual Intel Sapphire Rapids or AMD Genoa CPUs, eight DIMMs per socket on a DDR5 channel, four front-bay NVMe drives wired to PCIe Gen5, and two 25 GbE or 100 GbE network interfaces. Notice how the NVMe drives and NICs sit on a shared PCIe fabric rather than being dedicated to one socket — this is the detail that determines whether your storage I/O has to traverse the QPI/UPI interconnect.

```
┌─────────────────────────────────────────────────────────────┐
│                     2U RACK SERVER                           │
│                                                               │
│  ┌───────────────────┐    ┌───────────────────┐             │
│  │    CPU Socket 0    │    │    CPU Socket 1    │             │
│  │  (32 cores, 64 HT) │    │  (32 cores, 64 HT) │             │
│  │                    │    │                    │             │
│  │  L3 Cache: 48MB   │    │  L3 Cache: 48MB   │             │
│  └────────┬───────────┘    └────────┬───────────┘             │
│           │                         │                         │
│  ┌────────▼───────────┐    ┌────────▼───────────┐             │
│  │  NUMA Node 0       │    │  NUMA Node 1       │             │
│  │  RAM: 256GB DDR5  │    │  RAM: 256GB DDR5  │             │
│  │  (8x 32GB DIMMs)  │    │  (8x 32GB DIMMs)  │             │
│  └────────┬───────────┘    └────────┬───────────┘             │
│           │                         │                         │
│  ┌────────▼──────────────────────────▼───────────┐           │
│  │              PCIe Gen 5 Bus                    │           │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐         │           │
│  │  │NVMe 0│ │NVMe 1│ │NVMe 2│ │NVMe 3│         │           │
│  │  │3.84TB│ │3.84TB│ │3.84TB│ │3.84TB│         │           │
│  │  └──────┘ └──────┘ └──────┘ └──────┘         │           │
│  │                                                │           │
│  │  ┌──────┐ ┌──────┐                            │           │
│  │  │NIC 0 │ │NIC 1 │  (25GbE or 100GbE)        │           │
│  │  └──────┘ └──────┘                            │           │
│  └────────────────────────────────────────────────┘           │
│                                                               │
│  BMC / IPMI / iDRAC / iLO  (out-of-band management)         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

A few details from this layout shape every decision later in the module. Each socket pins eight DIMMs to its own integrated memory controller; if you populate fewer slots, you lose memory bandwidth in proportion, which is why DDR5 reference designs are unforgiving about asymmetric DIMM populations. The PCIe lanes are split between sockets in fixed allocations, so when you add a second 100 GbE NIC you may force the BIOS to bifurcate lanes that previously fed a fourth NVMe slot. And the BMC sits on its own out-of-band network, drawing standby power even when the host is off — a detail that the rack-power calculation must account for or the PDU will trip when you bring the row up.

### NUMA: Why CPU Topology Matters

Non-Uniform Memory Access (NUMA) means each CPU socket has "local" memory that is fast to access and "remote" memory on the other socket that is slower because every read or write has to traverse the inter-socket interconnect. On modern servers local DDR5 latency is roughly 80 nanoseconds and cross-socket latency is roughly 180 nanoseconds, a 2.25x penalty. For a workload that does a few cache-cold loads per request the difference disappears in noise, but for an in-memory database that issues hundreds of millions of loads per second, that 100 nanoseconds per access is enormous: it can cut throughput by a third or more on otherwise identical hardware.

```
┌─────────────────────────────────────────────────────────────┐
│                    NUMA TOPOLOGY                              │
│                                                               │
│   NUMA Node 0                    NUMA Node 1                 │
│   ┌──────────────┐              ┌──────────────┐            │
│   │   CPU 0      │              │   CPU 1      │            │
│   │  32 cores    │◄── QPI/UPI ──►│  32 cores    │            │
│   └──────┬───────┘    (~100ns)   └──────┬───────┘            │
│          │                              │                    │
│   ┌──────▼───────┐              ┌──────▼───────┐            │
│   │ Local RAM    │              │ Local RAM    │            │
│   │ 256GB        │              │ 256GB        │            │
│   │ (~80ns)      │              │ (~80ns)      │            │
│   └──────────────┘              └──────────────┘            │
│                                                               │
│   Pod A on CPU 0 accessing:                                  │
│     Local RAM (Node 0):  ~80ns  ← Fast                      │
│     Remote RAM (Node 1): ~180ns ← 2.25x slower              │
│                                                               │
│   Impact: in-memory DBs (Redis) on cross-NUMA = 30-50% slower│
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

The Linux kernel scheduler tries to keep a process and its memory on the same NUMA node, but Kubernetes complicates this. The kubelet's CPU manager and memory manager allocate resources per-pod, and unless you turn on the Topology Manager they can place a pod's CPU on socket 0 while the kernel allocates the pod's memory on socket 1, simply because the first-touch heuristic ran on the wrong core during pod start. The result is a pod that benchmarks fine in isolation, regresses by thirty to fifty percent under load, and confuses the team because the symptom looks like network congestion when it is actually memory traffic crossing the interconnect.

> **Pause and predict**: You are running Redis (an in-memory database) on a dual-socket server. The Redis process is scheduled on CPU socket 0, but half of its allocated memory lands on NUMA node 1. What performance impact would you expect, and how would you verify it? Sketch the test you would run before reading the answer below.

The expected impact is a thirty to fifty percent throughput reduction once Redis's working set exceeds the L3 cache, because every cache miss now pays the cross-socket penalty. To verify, run `numactl --hardware` to confirm both nodes are healthy, then `numastat -p $(pgrep redis-server)` to see how many pages are resident on each node. If the split is anywhere near fifty-fifty, the pod is cross-NUMA. The fix is a Topology Manager policy of `single-numa-node` in the kubelet config, combined with `static` CPU manager policy and guaranteed-QoS pods so the kubelet pins both CPU and memory to the same node at admission time.

The following kubelet configuration tells Kubernetes to pin all of a pod's resources to a single NUMA node. This is essential for latency-sensitive workloads like in-memory databases where cross-NUMA memory access would add 100 ns per access — enough to degrade throughput by thirty to fifty percent under realistic load:

```bash
# Check NUMA topology on a node
apt-get install -y numactl
numactl --hardware

# Kubernetes Topology Manager policies:
# - none: default, no NUMA alignment (fine for most workloads)
# - best-effort: try to align, don't fail if impossible
# - restricted: fail pods that can't be NUMA-aligned
# - single-numa-node: all resources from one NUMA node (latency-sensitive)

# Configure kubelet for NUMA-aware scheduling:
# /var/lib/kubelet/config.yaml
# topologyManagerPolicy: "single-numa-node"
# topologyManagerScope: "pod"
# cpuManagerPolicy: "static"
# memoryManagerPolicy: "Static"
```

The trade-off is admission failure: [under `single-numa-node`, a pod that requests more cores than fit on one socket cannot be scheduled at all](https://kubernetes.io/docs/tasks/administer-cluster/topology-manager), even if the cluster has plenty of free capacity in aggregate. That is the right behaviour for a Redis pod where cross-NUMA access would silently cost you a third of throughput, and the wrong behaviour for a stateless web service where the variance does not matter. Apply the policy at the node-pool level, not cluster-wide, and label the pool so workloads can opt in.

---

## Control Plane Sizing

The control plane is the brain of your cluster. Under-sizing it causes cascading failures that look like network problems but are actually storage problems; over-sizing wastes hardware that could have gone into the worker pool. The rule of thumb is that the control plane is etcd-bound, not CPU-bound: once etcd's fsync latency exceeds ten milliseconds at p99, every other control-plane symptom you will see is downstream of that one number. Size the storage first, then the RAM and CPU follow.

### etcd is the Bottleneck

etcd is the most resource-sensitive component in a Kubernetes control plane because it is a distributed consensus database that must commit every write to durable storage before acknowledging it, and the consensus protocol's heartbeat budget is measured in tens of milliseconds. The practical requirements are tight and non-negotiable.

- **Low-latency storage**: under ten milliseconds at p99 for fsync. NVMe is required at any meaningful cluster size; SATA SSDs spike past this threshold under load and trigger leader elections.
- **Consistent IOPS**: 500 to 1000 sustained writes per second for a hundred-node cluster, scaling roughly linearly with object count rather than node count.
- **RAM**: proportional to the number of objects, with a rough estimate of one gigabyte per ten thousand objects. CRDs and ConfigMaps dominate, not Pods.
- **CPU**: two to four dedicated cores. etcd writes are single-threaded but reads are parallelised, so heavy `kubectl get` traffic loads more cores than you might expect.

```
┌─────────────────────────────────────────────────────────────┐
│               CONTROL PLANE SIZING GUIDE                     │
│                                                               │
│  Cluster Size    │ CP Nodes │ CPU/Node │ RAM/Node │ Storage  │
│  ────────────────┼──────────┼──────────┼──────────┼──────────│
│  < 10 nodes      │    3     │  4 cores │   8 GB   │ 50GB NVMe│
│  10-100 nodes    │    3     │  8 cores │  16 GB   │ 100GB NVMe│
│  100-500 nodes   │    3     │ 16 cores │  32 GB   │ 200GB NVMe│
│  500-2000 nodes  │    5     │ 32 cores │  64 GB   │ 500GB NVMe│
│  2000+ nodes     │    5     │ 64 cores │ 128 GB   │ 1TB NVMe │
│                                                               │
│  CRITICAL: etcd storage MUST be NVMe with < 10ms p99 fsync  │
│  CRITICAL: 3 CP nodes = tolerate 1 failure                  │
│  CRITICAL: 5 CP nodes = tolerate 2 failures (recommended    │
│            for production clusters > 500 nodes)              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

The jump from three to five control-plane nodes at the 500-node mark is a function of failure domains, not CPU pressure. With three nodes you tolerate exactly one failure, which means a single rolling reboot during patching can leave you one disk failure away from a write-unavailable cluster. At five nodes you tolerate two failures simultaneously, which is the right posture once the cluster is large enough that a control-plane outage takes meaningful business workloads down with it. Five is also the point past which adding more members hurts: every additional voter increases write latency because the leader must replicate to a quorum, so seven-member clusters are slower than five-member clusters at the same hardware spec.

> **Stop and think**: Your team is debating whether to save $8,000 per control-plane node by using SATA SSDs instead of NVMe. The SATA SSDs have 80K IOPS and 2 ms p99 latency on a synthetic benchmark. Based on what you know about etcd's fsync requirements, would you approve this cost saving? What specific metric would you test before making the decision, and what is the failure mode if the test passes in isolation but fails under real cluster load?

The seductive part of the SATA proposal is the synthetic-benchmark number: 2 ms p99 latency looks safely under the 10 ms threshold. The trap is that synthetic benchmarks measure latency on an empty drive at moderate queue depth, while production etcd issues fsync after every WAL append in concurrent batches alongside snapshot writes, compaction reads, and operating-system journal traffic. The tail explodes under that mix. Always run the etcd-shaped benchmark below on the actual partition you intend to use, with the actual filesystem, and treat anything above 10 ms p99 as a hard reject.

The fio benchmark below simulates etcd's Write-Ahead Log pattern — small sequential writes with an fsync after each one. This is the single most important benchmark for control-plane hardware because etcd's performance directly determines API-server responsiveness, and the failure mode (leader elections under load) is invisible until you put the cluster under sustained pressure:

```bash
# Install fio for storage benchmarking
apt-get install -y fio

# Test sequential write latency (simulates etcd WAL writes)
mkdir -p /var/lib/etcd
fio --name=etcd-wal-test \
    --filename=/var/lib/etcd/fio-test \
    --rw=write \
    --bs=2300 \
    --fsync=1 \
    --size=22m \
    --runtime=60 \
    --time_based

# PASS: 99th percentile fsync < 10ms
# FAIL: 99th percentile fsync > 10ms → etcd will have leader elections

# Test random write IOPS (simulates etcd snapshot + compaction)
fio --name=etcd-iops-test \
    --filename=/var/lib/etcd/fio-test \
    --rw=randwrite \
    --bs=4k \
    --direct=1 \
    --numjobs=1 \
    --size=1g \
    --runtime=60 \
    --time_based

# Target: > 500 IOPS for clusters < 100 nodes
# Target: > 2000 IOPS for clusters > 500 nodes
```

Run this benchmark before you accept delivery of a server, not after the cluster is in production. Plenty of teams have signed off on a vendor SKU based on a "NVMe" line item on the bill of materials, only to discover that the vendor configured the drives behind a hardware RAID controller with a battery-backed write cache that adds two milliseconds of latency on every fsync. The fio numbers tell you the truth about the actual storage path the kernel will use, which is the only thing etcd cares about.

### Shared Control Planes: Multiple Clusters on Three Servers

For organizations running multiple small clusters — typical of platform teams supporting development, staging, and a few production environments — a dedicated three-node control plane per cluster is wasteful. Five clusters with dedicated control planes burn fifteen servers on control-plane work alone, which on a three-rack on-prem footprint is most of your hardware. Two architectural patterns let you share control-plane hardware across many clusters without giving up tenant isolation.

```
┌─────────────────────────────────────────────────────────────┐
│          SHARED CONTROL PLANE ARCHITECTURE                   │
│                                                               │
│  Option A: vCluster (virtual clusters)                       │
│  ┌────────────────────────────────────────┐                  │
│  │  Host Cluster (3 physical nodes)       │                  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐  │                  │
│  │  │vCluster │ │vCluster │ │vCluster │  │                  │
│  │  │  Dev    │ │ Staging │ │  Prod   │  │                  │
│  │  └─────────┘ └─────────┘ └─────────┘  │                  │
│  │  Each vCluster: own API server, etcd   │                  │
│  │  Shares: worker nodes, networking      │                  │
│  └────────────────────────────────────────┘                  │
│                                                               │
│  Option B: Kamaji (hosted control planes)                    │
│  ┌────────────────────────────────────────┐                  │
│  │  Management Cluster (3 nodes)          │                  │
│  │  ┌──────────────────────────────────┐  │                  │
│  │  │  Kamaji Operator                 │  │                  │
│  │  │  ┌────────┐ ┌────────┐ ┌──────┐ │  │                  │
│  │  │  │ TCP 1  │ │ TCP 2  │ │TCP 3 │ │  │                  │
│  │  │  │(Dev CP)│ │(Stg CP)│ │(Prd) │ │  │                  │
│  │  │  └────────┘ └────────┘ └──────┘ │  │                  │
│  │  └──────────────────────────────────┘  │                  │
│  └────────────────────────────────────────┘                  │
│  Worker nodes join remote — no CP hardware per cluster       │
│                                                               │
│  Savings: 3 servers host 10+ cluster control planes          │
│  vs 30+ servers for dedicated CPs                            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

vCluster runs each tenant's control plane as pods inside a host cluster, sharing the host's worker capacity but giving each tenant its own API server, scheduler, and either embedded SQLite or external etcd. The trade-off is that the host cluster's failure becomes everyone's failure, so the host cluster itself must be hardened to production standards. Kamaji takes a similar approach but runs each tenant control plane as a deployment in a management cluster while letting tenant workers join over the network as if they were attached to a dedicated control plane. Both let three physical servers host ten or more virtual control planes; both push the hardware decision toward fewer, larger servers because the management cluster's reliability now backs every tenant.

---

## Worker Node Sizing

### Workload Profiles

Different workloads need different server configurations, and the single most important signal is the ratio of CPU to RAM that the pods actually request. Sizing servers to match that ratio is the difference between a fleet that runs at sixty percent utilisation across both dimensions and a fleet that runs out of one dimension while leaving forty percent of the other stranded. The four profiles below cover the workloads you will encounter on a typical platform team; map your largest pod consumers to a profile before you pick a SKU.

| Profile | CPU:RAM Ratio | Example Workloads | Recommended Server |
|---------|--------------|--------------------|--------------------|
| **Compute-heavy** | 1:2 | CI/CD, compilation, encryption | High clock speed, fewer cores |
| **Balanced** | 1:4 | Web services, APIs, microservices | Standard dual-socket |
| **Memory-heavy** | 1:8 | Databases, caching, JVM apps | Max DIMM slots, lower-clock CPUs |
| **Storage-heavy** | N/A | Ceph OSDs, data pipelines | Many NVMe bays, high bandwidth |
| **GPU** | N/A | ML training, inference, rendering | PCIe Gen5 slots, high power |

The profile only tells you which server family to buy; the actual count comes from a sizing calculation that adds growth headroom and failure tolerance on top of the workload's steady-state requirement. The diagram below walks through that calculation step by step, ending with an explicit example so the arithmetic is concrete rather than implied.

### Sizing Formula

```
┌─────────────────────────────────────────────────────────────┐
│                WORKER NODE SIZING                            │
│                                                               │
│  Total cluster capacity needed:                              │
│    CPU = Sum of all pod CPU requests × 1.3 (30% headroom)   │
│    RAM = Sum of all pod RAM requests × 1.3 (30% headroom)   │
│                                                               │
│  Per-node calculation:                                       │
│    Allocatable CPU = Total cores - system reserved (2 cores) │
│    Allocatable RAM = Total RAM - system reserved (2-4 GB)    │
│    Allocatable RAM -= kubelet eviction threshold (100Mi)     │
│                                                               │
│  Number of nodes:                                            │
│    nodes = max(CPU_needed / allocatable_cpu_per_node,         │
│               RAM_needed / allocatable_ram_per_node)         │
│                                                               │
│  Add N+1 or N+2 for failure tolerance:                       │
│    Production: at least N+2 (survive 2 node failures)        │
│    Non-prod: N+1 is acceptable                               │
│                                                               │
│  Example:                                                    │
│    Workload: 200 pods, avg 1 CPU + 2GB RAM each             │
│    Cluster needs: 200 CPU, 400GB RAM (+ 30% = 260 CPU, 520GB)│
│    Server: 32-core (64 vCPUs with SMT), 256GB RAM            │
│    Allocatable: 62 vCPUs, 252GB RAM                          │
│    By CPU: 260/62 = 5 nodes                                 │
│    By RAM: 520/252 = 3 nodes                                │
│    Bottleneck: CPU (5 nodes)                                 │
│    With N+2: 7 nodes                                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

The thirty-percent headroom is not a fudge factor; it covers three real costs. Roughly ten percent goes to scheduling fragmentation: the bin-packing problem is NP-hard, and even a perfect scheduler leaves slivers of unallocatable capacity behind. Another ten percent absorbs request-versus-actual drift, because pod authors set requests conservatively and actual usage drifts upward over time as features are added. The last ten percent is your operational reserve for surge events: a Black Friday spike, a noisy neighbour, a node taken out for emergency patching. Without that reserve, the first abnormal day becomes a capacity incident.

### CPU: Intel vs AMD

The two-vendor question is more than a price comparison. The architectural choices each vendor has made over the last few generations push their silicon toward different workload profiles, and the right answer depends on whether your platform is throughput-bound or latency-bound. The table below summarises the current-generation comparison; the discussion that follows is where the trade-offs get decided.

| Factor | Intel Xeon (Sapphire Rapids) | AMD EPYC (Genoa) |
|--------|---------------------------|-------------------|
| Max cores/socket | 60 | 96 |
| Max RAM/socket | 4TB DDR5 | 6TB DDR5 |
| PCIe lanes | 80 (Gen5) | 128 (Gen5) |
| Price/core | Higher (~$30-50/core) | Lower (~$15-30/core) |
| Single-thread perf | Slightly higher | Slightly lower |
| Power efficiency | ~300W TDP | ~280W TDP |
| K8s recommendation | Good for latency-sensitive | Better for density |

For most Kubernetes platforms, AMD EPYC is the better default. The extra PCIe lanes matter more than the spec sheet suggests: a single Genoa socket has enough lanes to drive eight NVMe drives, two 100 GbE NICs, and a GPU without contention, which means you can build a denser server without the BIOS bifurcation games that two-socket Intel platforms force you into. The lower per-core price compounds with the higher core count to drop the per-pod hardware cost noticeably, and the modern infinity fabric closes most of the latency gap that earlier EPYC generations had against Intel. Intel still wins for workloads that are bottlenecked on per-core performance — single-threaded Java enterprise apps, certain database engines, any workload where AVX-512 throughput dominates — but those workloads are a minority of the modern Kubernetes platform.

> **Pause and predict**: You have two server options at the same price: (A) a single-socket AMD EPYC 9654 with 96 cores and 384 GB RAM, or (B) a dual-socket Intel Xeon 6430 with 64 total cores and 512 GB RAM. Your workload is 200 Java microservices averaging 0.5 CPU and 2 GB RAM each. Which server gives you better pod density, and why?

The answer turns on the workload's CPU-to-RAM ratio: 0.5 CPU and 2 GB RAM is a 1:4 ratio, which is balanced. Server A offers 96:384 (1:4 ratio, matched), so per node it can hold 192 pods CPU-bound or 192 pods RAM-bound — both dimensions saturate together. Server B offers 64:512 (1:8 ratio, RAM-heavy for this workload), so it caps at 128 pods CPU-bound while leaving 256 GB of RAM unused per node. On total cost, Option A delivers 192 pods per server and Option B delivers 128, a fifty-percent density advantage for Option A. The single-socket EPYC also avoids the cross-socket NUMA penalty entirely, which removes an entire class of variance from your latency budget.

### How Many Pods Per Node?

Kubernetes ships with a [default of 110 pods per node](https://kubernetes.io/docs/setup/best-practices/cluster-large/), but the practical limit is rarely set by that number. It is set by whichever of CPU, RAM, or CNI IP address pool runs out first. Calculate all three before you raise the limit, because raising `--max-pods` past the binding constraint just changes which symptom you see when the node fills up.

```bash
# Kubernetes default: 110 pods per node
# This is a soft limit configurable via kubelet:
# --max-pods=250

# Practical limits depend on:
# 1. CNI (some CNIs have per-node IP limits)
# 2. Available resources (CPU, RAM)
# 3. Pod density (many small pods vs few large pods)

# Calculate realistic pod density:
# If average pod = 0.5 CPU, 512Mi RAM
# Node = 64 cores, 256GB RAM
# By CPU: 64 / 0.5 = 128 pods
# By RAM: 256GB / 512Mi = 512 pods
# Practical limit: ~128 pods (CPU-bound)
# With overhead: ~100 pods (leave room for system pods)
```

The CNI ceiling is often invisible until you hit it. Calico in IPAM-per-block mode allocates a /26 block to each node by default, which gives you sixty-four addresses per block and a hard upper bound on pods regardless of CPU and RAM headroom. Cilium with cluster-pool IPAM has its own per-node ceilings tied to the cluster CIDR. Verify the CNI configuration before you provision a node-pool that targets two hundred pods per node, or you will discover the constraint in production when a deployment refuses to schedule.

### Few Large Nodes or Many Small Ones?

The procurement conversation often collapses into a false dichotomy: buy fewer, bigger servers to save rack space, or buy many smaller servers to spread risk. Both answers can be wrong for the same workload, because the trade-off is multidimensional and Kubernetes amplifies whichever dimension you neglect. Few large nodes maximize bin-packing efficiency in theory — one scheduler decision places hundreds of pods — but they also maximize blast radius, per-node DaemonSet overhead, and the cost of any single failure event. Many small nodes shrink blast radius and make incremental growth cheaper, but they multiply fixed per-node costs: kubelet CPU, CNI agents, observability sidecars, BMC management, switch ports, and licensing lines that charge per socket regardless of utilization.

Every worker node pays a tax before your first application pod schedules. The kubelet, container runtime, CNI plugin, node exporter, log shipper, and security agent collectively consume one to four vCPUs and two to eight gigabytes of RAM depending on pod density and policy stack. On a sixty-four-vCPU node that tax is noise; on a sixteen-vCPU node it can consume twenty percent of allocatable capacity before you account for system-reserved and kube-reserved settings. DaemonSets scale with node count, not node size, so a fleet of forty small nodes runs forty copies of every cluster-wide agent while a fleet of ten large nodes runs ten. The arithmetic favors larger nodes for DaemonSet-heavy platforms until blast radius and scheduling fragmentation push back.

Pod-density limits interact with node size in ways the default `--max-pods=110` obscures. Kubernetes chose 110 as a conservative default because early clusters broke etcd and the API server watch cache when single nodes hosted thousands of pods; the limit remains configurable but upstream guidance still treats very high pod counts as a scaling risk. Raising `--max-pods` on a large node without raising CNI IPAM pools, without verifying API server LIST throughput, and without confirming your average pod size still fits CPU and RAM guarantees is how teams end up with nodes that report healthy capacity while refusing new pods for unrelated reasons. Size nodes so the binding constraint is intentional — CPU, RAM, or pod count — not an accidental collision between three independent limits.

Licensing is the silent variable in the node-size decision on owned hardware. VMware, Windows Server Datacenter, Oracle Database, and several enterprise middleware stacks price per socket or per core regardless of how full the node runs. A dual-socket server with low utilization can cost more in license true-ups than two single-socket servers delivering the same pod capacity, even when the dual-socket machine wins on raw watts-per-core. Run the license model before you run the Kubernetes math, especially when JVM or Windows workloads dominate the fleet.

> **Stop and think**: Your cluster runs 400 pods averaging 0.25 CPU and 1 GB RAM. Option A is eight nodes at 64 vCPU / 256 GB each; Option B is sixteen nodes at 32 vCPU / 128 GB each. Total capacity is identical. Which option tolerates a single node failure with less rescheduling pressure, and which option wastes more capacity to DaemonSet overhead? Sketch the DaemonSet tax before reading on.

Option B spreads pods across more failure domains — losing one sixteen-node fleet member displaces twenty-five pods instead of fifty — but Option A runs half as many DaemonSet replicas and usually achieves better bin-packing because fewer scheduler boundaries exist. The right answer depends on your PodDisruptionBudget posture and spare headroom: if you size to sixty-five percent steady-state utilization, Option B survives one node loss with room to reschedule; if you size to eighty-five percent, Option B may cascade-evict while Option A still has slack. Neither SKU is universally correct; the decision framework later in this module turns these variables into a procurement checklist.

---

## GPU and Accelerator Node Considerations

GPU nodes break most of the rules above because the GPU itself dominates the cost and the surrounding silicon has to be sized to feed it. A modern training-class GPU (an NVIDIA H100 or B200) draws 700 to 1000 watts under load, consumes sixteen PCIe Gen5 lanes per device, and pairs with one to two CPU cores per GPU at most because the host's job is data movement, not compute. Filling a chassis with eight GPUs therefore demands a CPU and motherboard chosen to deliver lanes and power, not cores. AMD Genoa's 128-lane budget per socket is one of the reasons most reference designs for eight-GPU servers are single-socket EPYC — there are simply not enough Intel lanes to go around without bifurcation.

Sizing the host RAM for GPU nodes is counter-intuitive: you want roughly two to three times the aggregate GPU memory, which on an eight-H100 server (640 GB of HBM3 across the GPUs) means 1.5 to 2 TB of host RAM. The reason is that training pipelines stage data in host memory before pushing it to the GPU, and inference servers cache model shards and KV caches on the host between requests. Under-provisioning host RAM forces every batch through the storage subsystem and turns a GPU-bound workload into a storage-bound one, which is the worst kind of stranded capacity because GPUs are the most expensive silicon in the rack.

Kubernetes also forces you to think about scheduling: a single H100 cannot be split across pods without MIG (Multi-Instance GPU), and even with MIG the granularity is fixed by hardware. [The NVIDIA device plugin advertises GPUs as `nvidia.com/gpu: 1`, so two pods cannot share one device unless you opt into time-slicing or MIG](https://github.com/NVIDIA/k8s-device-plugin); both have throughput penalties relative to dedicated allocation. Plan capacity at the GPU-per-pod level, not the GPU-per-node level, and reserve at least one GPU per node as headroom because evicting a GPU pod is far slower than evicting a CPU pod (model load times dominate).

Dedicated accelerator pools — GPU for training and inference, DPU or SmartNIC for storage or security offload — should almost never share a node pool with general workloads. Taint accelerator nodes with a hardware-specific taint, size the CPU and RAM envelope to feed the accelerator rather than to run arbitrary microservices, and cable them to a network tier that matches the traffic pattern (100–400 GbE or InfiniBand for training, not the same 25 GbE top-of-rack pair that serves stateless APIs). Mixing accelerators into a homogeneous SKU catalog feels operationally convenient until a batch job schedules onto an inference node and evicts latency-sensitive model servers; separate pools cost more line items on the purchase order but eliminate an entire class of production incidents.

---

## Compute Sizing: vCPU, Physical Cores, and Oversubscription

Kubernetes exposes CPU in fractional units where **one CPU equals one hyperthread on typical x86 servers**, not one physical core. A dual-socket server with thirty-two cores per socket and simultaneous multithreading (SMT) advertises 128 `cpu` capacity to the scheduler even though only sixty-four physical cores exist. That distinction matters for CPU-bound workloads: two pods each requesting `2` CPU may land on the same physical core's two hyperthreads and contend for execution units, while the scheduler believes four CPUs are allocated. For latency-sensitive or HPC-style jobs, treat hyperthreads as a scheduling convenience, not as real isolated compute, and prefer whole-core requests with the [CPU Manager static policy](https://kubernetes.io/docs/tasks/administer-cluster/cpu-manager-policy/) on dedicated node pools.

The CPU Manager pairs with the Topology Manager and, for Guaranteed-QoS pods, can pin workloads to specific cores and NUMA nodes. Static policy reserves exclusive cores; the none policy (default) lets the Linux scheduler move pods freely. On-prem clusters running databases, low-latency queues, or telco NFVs on bare metal frequently enable static policy on labeled pools while leaving general microservices on the default path. The cost is reduced bin-packing efficiency: exclusive cores cannot be shared, so allocatable CPU on a pinned pool is lower than the raw `/proc/cpuinfo` count suggests.

CPU oversubscription — allowing sum(pod CPU requests) to exceed node capacity because average utilization stays low — is tempting on owned hardware where you pay for silicon whether it idles or not. Ratios of 2:1 or 3:1 request-to-capacity appear in internal private-cloud runbooks and can work when workloads are bursty and well-instrumented. The failure mode arrives on the first correlated spike: batch jobs, marketing events, or recovery after a node loss all raise utilization simultaneously, throttling every pod on the node through CFS shares without a clear owner. On-prem lacks cloud's infinite burst buffer; oversubscription without hard limits and without priority classes is how a "healthy" cluster enters CPU starvation. If you oversubscribe, cap it per node pool, enforce LimitRange defaults, and keep at least twenty percent physical core headroom for kubelet and DaemonSets.

Hyperthreading itself should usually stay **enabled** for mixed microservice fleets because it improves throughput on I/O-bound pods at minimal power cost. Disable SMT only when vendor guidance or regulatory baselines require deterministic core isolation, or when running latency-sensitive numerical workloads where sibling hyperthread contention measurably regresses p99 latency. Document the BIOS setting in your golden image; a drifted SMT flag between racks changes allocatable CPU and invalidates capacity spreadsheets silently.

---

## Memory Sizing: Working Set, Page Cache, and Eviction Headroom

Memory is the binding constraint on most on-prem Kubernetes fleets long before CPU saturates, because pod authors request RAM generously, JVM heaps are sized statically, and caches (Redis, Memcached, in-process) consume gigabytes that do not appear in CPU requests. The scheduler sums **requests**, not live working set, so a node can admit pods whose combined limits exceed physical RAM if limits are unset — and the kubelet will eventually evict pods when memory pressure crosses eviction thresholds. Sizing memory therefore starts from requested RAM plus explicit headroom for the operating system page cache when workloads depend on buffered I/O, not from `free -m` on an idle node.

The page cache accelerates container filesystem and volume reads but is reclaimable under pressure; databases and streaming pipelines often benefit from leaving ten to twenty percent of node RAM outside pod requests so the kernel can cache without triggering premature eviction. Hugepages reduce TLB pressure for DPDK, certain databases, and some JVM configurations, but require pre-allocation at boot or through the kubelet and reduce flexible RAM available for ordinary pods. Reserve hugepages only on dedicated pools with a documented consumer; otherwise they strand capacity.

Eviction thresholds — `memory.available` signals derived from `eviction-hard` and `eviction-soft` kubelet settings — define when the kubelet begins reclaiming pod memory. Defaults assume a general-purpose node; memory-heavy platforms often raise soft thresholds and pair them with PodDisruptionBudgets so evictions become controlled drains rather than random SIGKILLs. ECC RAM remains mandatory: silent bit flips in non-ECC DIMMs corrupt data without triggering reschedule, which is unacceptable on nodes running etcd members, databases, or long-lived caches.

When profiling, compare Prometheus `container_memory_working_set_bytes` against requests over a full business cycle before buying RAM-heavy SKUs. A fleet averaging seventy-eight percent RAM utilization with twenty-two percent CPU utilization (a pattern this module returns to in the quiz) is not "efficient" — it signals a CPU-to-RAM ratio mismatch that the next hardware generation should correct, not replicate.

---

## Reserved vs Allocatable: A Worked Example

Kubernetes never exposes 100% of hardware to pods. **Capacity** is what the node reports; **allocatable** is capacity minus kube-reserved, system-reserved, and eviction-threshold reservations. Procurement spreadsheets that divide total cluster RAM by pod requests without subtracting overhead systematically over-order nodes and under-order control-plane storage.

Consider a worker SKU with 128 logical CPUs (64 cores with SMT) and 512 GiB RAM installed. A typical production kubelet configuration might set:

```yaml
# /var/lib/kubelet/config.yaml (illustrative)
kubeReserved:
  cpu: "2"
  memory: "4Gi"
systemReserved:
  cpu: "2"
  memory: "4Gi"
evictionHard:
  memory.available: "500Mi"
  nodefs.available: "10%"
```

After reservation, allocatable CPU is roughly 124 logical CPUs and allocatable memory is roughly 503 GiB minus the 500 MiB eviction floor — call it **502 GiB** for planning. DaemonSets (monitoring, CNI, logging) consume another **3 vCPU and 6 GiB** before application pods schedule. Usable envelope for workloads: **121 vCPU and ~496 GiB**.

Your pod catalog sums to **95 vCPU requested** and **420 GiB requested** at steady state. With thirty-percent growth headroom you plan for **124 vCPU** and **546 GiB**. CPU fits one node (121 ≥ 124 is false — you need a second node for CPU headroom); RAM fits one node for steady state but not with growth (546 > 496). **RAM is the binding dimension** after reservations, not the raw 512 GiB sticker on the DIMMs. Two nodes deliver 242 allocatable vCPU and ~992 GiB — enough for growth with N+1 spare if you target sixty-five percent steady-state utilization on RAM (420 / (2 × 496) ≈ 42%, leaving room for one node loss).

Always run this arithmetic per node pool; GPU and control-plane SKUs use different reservation profiles. The upstream reference for reservation semantics is [Reserve compute resources on a node](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/) and the [Node allocatable](https://kubernetes.io/docs/concepts/architecture/nodes/#allocatable) documentation.

---

## Failure Domains, N+1 Headroom, and Disruption Budgets

Hardware sizing and failure tolerance are the same spreadsheet. **N+1** means the cluster continues operating if one node disappears; **N+2** means two simultaneous failures (rolling upgrade plus hardware fault) still leave schedulable capacity. Production on-prem fleets should default to N+2 for worker pools above a dozen nodes because maintenance and failure correlate — patching node A while node B throws a memory error is routine, not a black-swan.

PodDisruptionBudgets (PDBs) and pod anti-affinity rules translate application redundancy requirements into minimum node counts. An application with `replicas: 3` and `podAntiAffinity` requiring distinct hosts needs at least three workers available **after** reservations, not three workers total. If one node is cordoned for maintenance and another fails, anti-affinity plus PDB `minAvailable: 2` may block evictions and stall your upgrade. Size headroom so a single rack or PDU loss — map nodes to `topology.kubernetes.io/zone` labels matching physical layout — never drops available capacity below the sum of your tightest PDB budgets.

Control-plane sizing follows the same logic with different numbers: three etcd members tolerate one loss; five tolerate two. Never run four members — even counts do not increase quorum tolerance. Spread control-plane nodes across independent PDUs or racks; stacking three CP VMs on one hypervisor defeats the purpose of three-node etcd.

---

## Storage Selection

### Storage Tiers

Storage is the dimension where vendor terminology obscures the most. "Enterprise SSD" can mean a 3 DWPD NVMe drive that fsyncs in 100 microseconds, or a SATA drive that fsyncs in five milliseconds, and both will appear on the same line item of a vendor's bill of materials. Tier the storage by the latency it actually delivers, not the marketing label, and force every drive class into one of the four buckets below before you accept it.

| Tier | Technology | IOPS | Latency | Use Case | Cost/TB |
|------|-----------|------|---------|----------|---------|
| **Tier 0** | NVMe (PCIe Gen5) | 1M+ | <100us | etcd, databases | $150-300 |
| **Tier 1** | NVMe (PCIe Gen4) | 500K+ | <200us | Application data, Ceph OSD | $100-200 |
| **Tier 2** | SATA SSD | 50-100K | 1-5ms | Logs, bulk storage | $50-100 |
| **Tier 3** | HDD (SAS/SATA) | 100-200 | 5-15ms | Backups, cold data | $15-30 |

The critical rule is that etcd MUST run on Tier 0 or Tier 1 storage, full stop. SATA SSDs (Tier 2) will cause etcd leader elections under load because their fsync tail latency exceeds the 10 ms threshold the consensus protocol assumes. The same rule applies to any database whose write path goes through `fsync` on every commit — Postgres with `synchronous_commit=on`, Kafka with `acks=all`, MongoDB with `j:true` — because the storage tail will dominate their latency budget. Pick the tier from the workload's durability semantics, not from the price-per-terabyte column.

### Networking

Networking decisions have a similar structure: the speed line item on the bill of materials is the easy part, while the harder questions are about bisection bandwidth across the rack and the redundancy of the top-of-rack pair. The minimums below are the floor for a production Kubernetes cluster, not a target.

| Speed | Use Case | Cost per Port |
|-------|----------|---------------|
| 1GbE | Management/IPMI only | ~$20 |
| 10GbE | Small clusters (<20 nodes) | ~$50 |
| 25GbE | Standard production | ~$100 |
| 100GbE | High-throughput (storage, ML) | ~$300 |

Twenty-five gigabit Ethernet is the modern minimum for any production Kubernetes cluster because the east-west traffic patterns of a typical microservices fleet plus a software-defined storage layer (Ceph, Rook, Longhorn) saturate 10 GbE quickly, especially during a node failure when the storage layer has to rebuild. One-gigabit is fine for the management network and out-of-band traffic to the BMC, but it is insufficient for any pod-to-pod traffic. Plan for two NICs per server bonded LACP into two top-of-rack switches so that a switch failure takes out half the bandwidth, not all of it.

---

## Patterns & Anti-Patterns

| Pattern / Anti-Pattern | Description | Why It Happens / When to Use | Impact / Better Approach |
|--------------------------|-------------|------------------------------|---------------------------|
| **Pattern: Capacity buffer + scale-out** | Size steady-state utilization to 60–70% of allocatable CPU/RAM and add nodes when sustained utilization crosses a threshold for two weeks. | **When to use:** Any production fleet with seasonal traffic or batch windows. | Absorbs node loss and deployment surges without emergency procurement; trades capital efficiency for operational calm. |
| **Pattern: Profile-matched node pools** | Separate compute-heavy, memory-heavy, storage, and GPU pools sized to pod request ratios. | **When to use:** Workload mix spans JVM services, caches, CI, and ML. | Eliminates stranded CPU or RAM; increases SKU count but raises fleet-wide utilization. |
| **Pattern: Pre-delivery storage benchmark** | Run etcd-shaped fio on every control-plane drive before sign-off. | **When to use:** Always, for any self-managed control plane on owned hardware. | Catches RAID-cache latency and wrong drive tier before production leader elections. |
| **Pattern: NUMA-aware pools** | Label latency-sensitive pools; enable Topology Manager + CPU Manager static on those nodes only. | **When to use:** In-memory databases, low-latency APIs on bare metal. | Prevents silent 30–50% regressions from cross-socket memory traffic. |
| **Anti-Pattern: Peak-only sizing** | Buying exactly enough silicon for Black Friday peak with zero headroom. | **Why it happens:** Finance caps capital; teams confuse peak requests with steady state. | First node loss or upgrade triggers mass evictions; add N+2 and growth buffer explicitly. |
| **Anti-Pattern: Uniform mega-nodes** | Four 256-core / 2 TB servers instead of sixteen 64-core / 512 GB servers at equal aggregate capacity. | **Why it happens:** Rack-space savings and simpler BOM. | Single failure displaces hundreds of pods; image pulls and storage rebuilds thundering-herd the cluster. |
| **Anti-Pattern: SATA etcd** | Using Tier-2 SATA SSDs for control-plane data directories because the label says "enterprise SSD." | **Why it happens:** Procurement conflates interface with fsync tail latency. | Leader elections, read-only API windows, and unexplained `context deadline exceeded` during deploys. |
| **Anti-Pattern: Ignoring allocatable math** | Dividing total DIMMs by pod requests without kube/system reserved or DaemonSet tax. | **Why it happens:** Spreadsheet uses hardware specs, not `kubectl describe node` allocatable. | Systematic under-provisioning; RAM outages despite "plenty" of sticker capacity. |

---

## Decision Framework: How Many Nodes of What Size

Use this flow when translating pod requests into a purchase order. It assumes you already collected CPU and RAM **requests** (not limits) weighted by replica count.

```
START → Sum pod CPU/RAM requests × 1.3 growth headroom
      → Compute CPU:RAM ratio → pick matching worker SKU family
      → Subtract kube/system reserved + DaemonSet tax → allocatable per node
      → nodes = max( CPU_need / allocatable_cpu , RAM_need / allocatable_ram )
      → Add N+2 (production) or N+1 (non-prod)
      → Check pod-density + CNI IPAM + max-pods ceiling per node
      → If any PDB/anti-affinity needs > (nodes − maintenance − 1), increase nodes
      → Size CP separately: NVMe etcd benchmark + 3 or 5 members by cluster scale
      → Verify rack power + cooling at 65% of PDU budget → END
```

| Decision Factor | Favor Fewer, Larger Nodes | Favor More, Smaller Nodes | On-Prem Notes |
|-----------------|---------------------------|---------------------------|---------------|
| **DaemonSet / agent count** | Lower replica count of node agents | Higher overhead; more switch ports | CNI, observability, and security stacks tax small nodes harder |
| **Blast radius** | Single failure disrupts many pods | Failure displaces fewer workloads | Pair small nodes with strict PDBs and spare headroom |
| **Bin-packing efficiency** | Fewer scheduler boundaries | More fragmentation at scale | Re-run sizing if average pod < 0.25 CPU |
| **Licensing model** | May reduce per-socket fees if utilization high | Spreads per-socket licenses across more boxes | Oracle/Windows stacks may invert the economics |
| **Incremental growth** | Each addition is expensive | Add one node at a time | Leave 30–40% empty rack units and PDU headroom |
| **Pod density target** | Raise max-pods only with CNI + API headroom | Keep ≤110 unless measured otherwise | etcd/API watch load rises with object count, not just nodes |

---

## Did You Know?

- **A single modern server can replace twenty to thirty cloud instances.** A 2U server with dual 64-core AMD EPYC processors (128 cores, 256 threads), 1 TB of RAM, and eight NVMe drives provides more compute than a fleet of m6i.xlarge instances — at a fraction of the three-year cost. The break-even point on bare metal versus on-demand cloud is typically eight to fourteen months for steady-state workloads, and shrinks every generation as core counts climb faster than cloud per-core pricing falls.

- **ECC (Error-Correcting Code) memory is non-negotiable for servers.** Non-ECC RAM experiences approximately one bit error per 8 GB per 72 hours of runtime under normal cosmic-ray flux. In a 512 GB server, that is multiple undetected memory corruptions per day, any of which could land in an etcd page, a database B-tree node, or a filesystem journal entry. ECC costs roughly ten percent more but converts those silent corruptions into logged, recoverable events; it is the single cheapest reliability upgrade in the rack.

- **NUMA topology can cause a [2x performance difference](https://www.usenix.org/publications/login/oct15/lepers)** for the same workload on the same hardware. A database running entirely within one NUMA node can be twice as fast as one whose memory is split across two NUMA nodes, because every cache miss on the slow path has to traverse the inter-socket interconnect. Kubernetes Topology Manager was created specifically to solve this, but it is opt-in: clusters using the default `none` policy give up the entire benefit silently.

- **The most common server lifecycle is five years**, but most organizations refresh at three years because warranty, performance per watt, and parts availability all tilt against keeping older gear. After three years, maintenance contracts get expensive and newer hardware offers thirty to fifty percent better performance per watt, which on a fully populated rack pays for the refresh in electricity savings alone over the next two years.

---

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| SATA SSDs for etcd | Leader elections under load, cluster instability | NVMe only for control-plane storage; verify with the fio etcd-WAL benchmark |
| Wrong CPU:RAM ratio | Stranded resources (idle CPU or insufficient RAM) | Profile your workloads first, then buy hardware to match the ratio |
| Skipping NUMA planning | 30-50% latency increase for latency-sensitive pods | Enable Topology Manager `single-numa-node` for critical node pools |
| Buying consumer drives | No power-loss protection, shorter lifespan, surprise wear-out | Enterprise NVMe with PLP (Power Loss Protection) and at least 1 DWPD endurance |
| Uniform hardware | Every node identical regardless of workload needs | Different node pools: compute, memory, storage, GPU — each sized to its workload |
| Maxing out day one | No expansion room for growth, forklift upgrade in eighteen months | Fill 60-70% of rack capacity, leave room for the next generation |
| Ignoring power budget | Servers draw more power than the rack PDU supports, breaker trips on surge | Calculate sustained TDP per server times node count versus PDU capacity, with a safety margin |
| No spare nodes | A single failure causes capacity pressure and cascading evictions | Maintain N+2 spare capacity at minimum, more for clusters above 100 nodes |

---

## Quiz

### Question 1
You are building a Kubernetes cluster for a real-time analytics platform. The workload consists of 50 pods, each requiring 4 vCPU and 32 GB RAM. What server configuration would you choose, and how many nodes would you provision for production?

<details>
<summary>Answer</summary>

Total CPU needed is 50 multiplied by 4, which equals 200 vCPU, plus a thirty-percent headroom giving 260 vCPU. Total RAM needed is 50 multiplied by 32 GB, which equals 1,600 GB, plus thirty percent giving 2,080 GB. The CPU-to-RAM ratio of the workload is 1:8, which is memory-heavy.

Choose memory-optimized servers. A reasonable SKU is a single AMD EPYC 9354 (32 cores, 64 threads) paired with 512 GB of DDR5. Kubernetes counts one CPU as one hyperthread, so this server provides 64 allocatable vCPUs. After subtracting system reservations the allocatable values are roughly 62 vCPUs and 508 GB of RAM. Dividing 260 by 62 gives five nodes by CPU, and dividing 2,080 by 508 also gives five nodes by RAM, so the configuration is balanced. With N+2 failure tolerance the final count is seven nodes.

This is a well-balanced configuration because the vCPU-to-RAM ratio of the server (1:8) matches the workload profile. With compute-optimized servers using a 1:4 ratio (the configuration in the intro story), you would need nine or more nodes to satisfy the RAM requirement, wasting roughly half of the CPU capacity for the entire three-year lifecycle of the fleet.
</details>

### Question 2
A cluster admin notices the Kubernetes API server occasionally becomes read-only and unresponsive for brief periods during heavy deployment activity. The control-plane nodes are using SATA SSDs, and metrics show `fsync` latency frequently spiking to 80 ms. What is the architectural sequence of events causing this API outage?

<details>
<summary>Answer</summary>

etcd uses a Write-Ahead Log (WAL) that requires `fsync` on every write to guarantee data durability under power loss. The `fsync` latency directly determines how fast etcd can commit transactions, because the consensus protocol cannot acknowledge a write until the leader has synced it to disk and received acks from a quorum of followers who have also synced.

Typical fsync latency by storage class: NVMe sits at 0.1 to 1 ms at p99, SATA SSDs at 2 to 10 ms at p99, and HDDs at 10 to 50 ms. etcd's leader election timeout defaults to one second, which is ten times the heartbeat interval of 100 ms. If commit latency consistently exceeds 50 to 100 ms, the leader cannot send heartbeats fast enough and followers begin election attempts. During an election the cluster is read-only — every API server write returns an error or hangs until a new leader is established.

Under load with many concurrent kubectl commands, controller reconciliations, and webhook calls, SATA SSD latency spikes to ten milliseconds and beyond, which cascades into slow API responses, failed deployments, and visible cluster instability. This failure mode is one of the most common production issues in self-managed Kubernetes, and it is invisible in synthetic single-threaded benchmarks because the contention only emerges under realistic concurrent load.
</details>

### Question 3
Your company has 3 servers with 128 cores and 512 GB of RAM each. You want to run 5 Kubernetes clusters (dev, staging, three production environments). How would you architect this?

<details>
<summary>Answer</summary>

Do not run five separate clusters with dedicated control planes. That would require fifteen control-plane nodes (three per cluster), which exceeds the available hardware before any worker capacity is allocated. The architectural answer is a shared control-plane pattern.

Option A is vCluster. Run one host cluster across all three servers (three control-plane and three worker, possibly stacked) and provision five vClusters as pods inside the host. Each vCluster gets its own API server and either embedded SQLite or a small embedded etcd, while worker capacity is shared across all virtual clusters. Total control-plane overhead is roughly twenty cores and forty gigabytes of RAM in aggregate, instead of the 120 cores you would burn on dedicated control planes.

Option B is Kamaji. Run one management cluster of three nodes with stacked etcd, then provision five Tenant Control Planes (TCPs) that run as deployments inside the management cluster. Worker nodes for each tenant join their respective TCP over the network. The per-tenant overhead is even lighter than vCluster — each TCP runs as roughly two cores and four gigabytes of RAM — because Kamaji multiplexes control-plane components more aggressively.

The key insight is that with three servers you cannot afford to waste sixty percent or more of capacity on control planes. Shared control-plane architectures exist precisely for this constraint, and the trade-off they impose (the shared host or management cluster becomes a single failure domain for all tenants) is acceptable when the alternative is no platform at all.
</details>

### Question 4
Your procurement team suggests buying four massive 256-core / 2 TB servers instead of sixteen 64-core / 512 GB servers to save on rack space, since both options provide roughly the same total capacity. What operational risk does the four-server architecture introduce for Kubernetes?

<details>
<summary>Answer</summary>

The risk is blast radius. The bigger the server, the more pods run on it, and when it fails more workloads are disrupted simultaneously by a single hardware event.

A single server with 256 cores and 2 TB of RAM might run 500 or more pods. A single hardware failure (RAM error, PSU failure, NVMe death) takes 500 pods down at once. Rescheduling 500 pods to other nodes causes resource pressure on the remaining nodes that may not have headroom for that volume of evictions, a thundering herd of container image pulls across the cluster as every replacement pod fetches its image, and cascading failures if the remaining nodes are already near capacity and start tipping over under the redistributed load.

The better approach is medium-sized servers in the 64-to-96-core range with 256 to 512 GB of RAM, which provides a good balance of density and blast radius. You need enough nodes that losing one does not exceed your N+2 headroom, and that arithmetic gets harder to satisfy as nodes get larger. The exception is GPU servers, which are inherently large and expensive; for GPU workloads, accept the larger blast radius and compensate with redundancy at the application layer — checkpointing during training, model replica sets for inference.
</details>

### Question 5
A platform team is benchmarking a Redis cache pod on a freshly provisioned dual-socket EPYC server with 96 cores per socket. In isolation Redis hits its target throughput easily, but once the node fills up with other tenants the Redis p99 latency triples and `numastat -p $(pgrep redis-server)` shows the process's resident memory split roughly fifty-fifty across the two NUMA nodes. The kubelet is running with default settings. What is the diagnosis, and what is the minimum set of changes to fix it without overhauling the cluster?

<details>
<summary>Answer</summary>

The diagnosis is a NUMA misalignment. The Redis process is executing on one socket but half its working set is resident on the other socket, so every cache-cold load on the remote half pays an inter-socket interconnect penalty of roughly 100 nanoseconds. Once the working set exceeds the L3 cache, the cumulative penalty drives p99 latency up by exactly the proportion you would expect from a 30-to-50-percent throughput hit, which matches the threefold p99 inflation reported.

The default kubelet has `topologyManagerPolicy: none` and `cpuManagerPolicy: none`, so the scheduler placed the Redis pod's CPU on socket zero while the kernel's first-touch policy allocated memory on whichever socket happened to be active when each page was faulted in. Under contention from other tenants those allocations spread across both nodes.

The minimum fix is to label this node pool as latency-sensitive, then update the kubelet config on those nodes to set `cpuManagerPolicy: static`, `memoryManagerPolicy: Static`, `topologyManagerPolicy: single-numa-node`, and `topologyManagerScope: pod`. Restart the kubelet, drain and uncordon the nodes so existing pods get rescheduled with the new policies, and ensure the Redis pod requests integer CPU and is in the Guaranteed QoS class so the manager actually pins it. The trade-off is that pods exceeding a single socket's capacity will fail admission on these nodes, which is the intended behaviour for a latency-sensitive pool.
</details>

### Question 6
A finance team challenges your hardware proposal: "ECC RAM costs ten percent more. We're already buying redundant nodes for failure tolerance — why not save the money on memory and let Kubernetes reschedule any pod that hits a memory error?" Walk through why this trade-off does not work the way they expect, and what failure modes ECC actually prevents.

<details>
<summary>Answer</summary>

The trade-off does not work because the failure mode ECC prevents is not "the node crashes and Kubernetes reschedules." It is "the node keeps running but produces wrong answers." A non-ECC bit flip in a database row, an etcd page, or a filesystem journal entry is silently committed and replicated, and downstream systems treat the corrupted value as truth.

Cosmic-ray-induced bit flips happen at a rate of roughly one error per 8 GB of RAM per 72 hours of runtime under normal flux. In a 512 GB server that is multiple flips per day. Without ECC, none of those flips are detected: the corrupted byte is read back as if it were correct, and the application has no way to know its in-memory state diverged from what was written. With ECC, single-bit errors are corrected transparently and double-bit errors are logged as machine-check exceptions that the operating system can surface to monitoring.

For Kubernetes specifically, the most dangerous targets are etcd (where a flip in a Raft log entry can split-brain the cluster), container images cached in memory (where a flip during image verification gets baked into a running container), and any database or queue running on the node. Rescheduling a pod after a memory error requires the error to be detected, which is precisely what ECC enables — without it, the reschedule never happens because the node never knows anything is wrong. ECC is therefore not a redundancy duplicate of your N+2 node headroom; it is detection that makes the headroom reachable.
</details>

### Question 7
Your team operates a 60-node cluster on dual-socket Intel servers with 25 GbE bonded NICs and Tier-1 NVMe storage. A new internal customer wants to run an eight-GPU H100 training pool on the same physical fleet, sharing the existing top-of-rack switches and PDUs. List the three hardware constraints you must verify before agreeing, and explain what fails if you skip the check.

<details>
<summary>Answer</summary>

The three constraints are PCIe lane budget on the host, electrical power on the rack PDU, and network bandwidth across the top-of-rack pair. Skipping any of them produces a failure that surfaces only under load, which is exactly when a training run cannot afford it.

Eight H100s each consume sixteen PCIe Gen5 lanes for the GPU itself, plus more for NVLink switches and ConnectX NICs that almost always accompany them; the aggregate exceeds 128 lanes. A dual-socket Intel platform with eighty lanes per socket can supply this only with bifurcation gymnastics that compromise NVMe and NIC throughput. The right host is single-socket AMD EPYC with 128 lanes per socket, which is why most reference designs for eight-H100 servers are single-socket. If you skip this check the GPUs negotiate down to fewer lanes than spec, which is invisible to Kubernetes and silently caps training throughput.

H100 servers draw 6 to 10 kW under load between the GPUs themselves and the supporting CPU and NVMe. Standard 208 V / 30 A PDUs deliver around 5 kW per circuit, so a single H100 server can saturate or trip a circuit that previously hosted three traditional servers. Verify total sustained draw against the PDU rating with a margin, and understand whether the rack has the cooling capacity to remove that heat — a 6 kW server in a rack designed for 2 kW per slot will throttle.

Network bandwidth matters because training jobs do all-reduce or parameter-server traffic that scales with model size; 25 GbE is insufficient and these nodes typically need 100 or 200 GbE per port, often with a separate RDMA-capable fabric. If you join GPU nodes to a 25 GbE top-of-rack pair, the GPUs sit idle waiting on gradient synchronisation, which is the most expensive idle silicon in the rack.
</details>

### Question 8
You inherit a cluster where every node is a 96-core / 384 GB server bought eighteen months ago. The CPU utilization across the fleet averages 22 percent and RAM utilization averages 78 percent. The CTO asks why utilization is so unbalanced and whether the next refresh should buy "the same servers but more of them." What is your answer and your recommendation?

<details>
<summary>Answer</summary>

The diagnosis is a CPU-to-RAM ratio mismatch between the servers and the workload. The servers are 96:384, which is a 1:4 ratio. The workload is running close to RAM saturation while leaving most of the CPU stranded, which means the actual aggregate pod request profile sits closer to 1:8 — memory-heavy — and the cluster is RAM-bound. Adding more identical servers just adds proportionally more stranded CPU; the next refresh should rebalance the ratio, not multiply the imbalance.

The recommendation is to size the next generation around what the pods actually request. Pull the average CPU and RAM request across the running pod set (using the Vertical Pod Autoscaler recommender or a Prometheus query over `kube_pod_container_resource_requests`) and weight it by replica count. If the result is a 1:8 ratio, target servers in that ratio: a single-socket 64-core EPYC with 512 GB of DDR5 is one example, and the resulting fleet will run near the same utilisation on both dimensions instead of saturating one and wasting the other.

The financial argument is concrete: the existing fleet wastes 78 percent of the CPU it paid for, which on a 50-server cluster at \$15K per server is roughly \$585K of stranded silicon over a five-year lifecycle. A rebalanced refresh recovers most of that. The CTO's instinct to buy "the same servers but more of them" is the most expensive answer because it locks the imbalance in for another three to five years. The correct answer is to buy fewer, differently shaped servers, and to instrument the workload before the next purchase order so the procurement decision is driven by data rather than inertia.
</details>

---

## Hands-On Exercise: Size a Kubernetes Cluster

**Task**: Given a workload profile, calculate the hardware requirements for an on-premises Kubernetes cluster.

### Scenario
Your company is deploying a microservices platform with the following workloads:

- 120 API pods at 0.5 CPU and 1 GB RAM each.
- 30 worker pods at 2 CPU and 4 GB RAM each.
- 10 database pods at 4 CPU and 16 GB RAM each.
- 5 cache pods at 1 CPU and 8 GB RAM each (Redis).
- 15 monitoring pods at 0.25 CPU and 512 MB each (Prometheus, Grafana, exporters).

Requirements: production environment with high availability, thirty-percent headroom for growth, N+2 node failure tolerance, and etcd on dedicated NVMe.

### Steps

1. **Calculate total resource needs**. Sum each pod class's CPU and RAM requests, then add the thirty-percent headroom.

```bash
# CPU calculation
API:       120 x 0.5  = 60 cores
Workers:    30 x 2.0  = 60 cores
Databases:  10 x 4.0  = 40 cores
Cache:       5 x 1.0  =  5 cores
Monitoring: 15 x 0.25 =  3.75 cores
                Total = 168.75 cores
         + 30% headroom = 219 cores

# RAM calculation
API:       120 x 1GB   = 120 GB
Workers:    30 x 4GB   = 120 GB
Databases:  10 x 16GB  = 160 GB
Cache:       5 x 8GB   =  40 GB
Monitoring: 15 x 512MB =   7.5 GB
                 Total = 447.5 GB
          + 30% headroom = 582 GB
```

2. **Choose server configuration**. Compute the workload's CPU-to-RAM ratio (219:582, roughly 1:2.7, balanced and slightly memory-heavy), then pick a server SKU whose ratio is close.

```bash
# CPU:RAM ratio of workload: 219:582 ≈ 1:2.7 (balanced/slightly memory-heavy)
# Choose: Dual 32-core servers with 256GB RAM
# Note: K8s sees 1 CPU = 1 hyperthread (vCPU), so dual 32-core with SMT = 128 vCPUs

# Per node allocatable:
# CPU: 128 vCPUs - 2 system = 126 vCPUs
# RAM: 256GB - 4GB system = 252GB

# By CPU: 219 / 126 = 2 nodes (rounded up)
# By RAM: 582 / 252 = 3 nodes (rounded up)
# Bottleneck: RAM → need 3 worker nodes

# With N+2: 5 worker nodes
# Plus 3 control plane nodes (dedicated, smaller)

# TOTAL: 8 servers
# - 3x CP: 8 cores, 32GB RAM, 200GB NVMe each
# - 5x Worker: dual 32-core (128 vCPUs), 256GB RAM, 2x 3.84TB NVMe each
```

3. **Estimate costs and compare to cloud equivalent**, so the procurement conversation has a defensible TCO number rather than a vendor-quoted list price.

```bash
# Control plane servers: 3 x ~$6K = $18K
# Worker servers: 5 x ~$15K = $75K
# Networking (2 ToR + cabling): ~$20K
# Total hardware: ~$113K
#
# Compare to cloud (5 x m6i.8xlarge equivalent):
# 5 x $1,228/mo = $6,140/mo = $74K/year = $221K over 3 years
# On-prem 3-year TCO (incl ops): ~$113K + $150K ops = $263K
# On-prem slightly more expensive at this scale — wins at larger scale
```

The interesting result here is that on-prem and cloud are roughly comparable at this size, which is exactly the "should we be on-prem at all" question Module 1.1 introduced. Run this exercise twice — once at the size you have today, once at the size you expect in three years — and the answer often flips because on-prem operational costs scale sub-linearly while cloud spend scales linearly with footprint.

### Success Criteria
- [ ] Total CPU and RAM calculated with 30% headroom from the per-pod-class breakdown
- [ ] CPU:RAM ratio identified and matched to a specific server SKU
- [ ] Node count includes N+2 redundancy and is justified against the binding dimension (CPU or RAM)
- [ ] Control-plane and worker nodes sized separately with different SKUs
- [ ] etcd storage requirement identified as NVMe with a fio-verified fsync latency target
- [ ] Hardware cost estimated and compared to the equivalent cloud spend over a three-year horizon

---

## Next Module

Continue to [Module 1.3: Cluster Topology Planning](../module-1.3-cluster-topology/) to learn how to organize your clusters — how many, where, and what architecture pattern to use.

## Sources

- [Kubernetes Node Resource Managers](https://kubernetes.io/docs/concepts/policy/node-resource-managers/) — CPU, memory, and topology-aware allocation behavior that directly affects server-sizing decisions.
- [Reserve Compute Resources on a Node](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/) — Defines kube-reserved, system-reserved, and eviction thresholds used in allocatable capacity math.
- [Node Allocatable Resources](https://kubernetes.io/docs/concepts/architecture/nodes/#allocatable) — Explains capacity versus allocatable and what the scheduler actually consumes.
- [Configure the CPU Manager Policy](https://kubernetes.io/docs/tasks/administer-cluster/cpu-manager-policy/) — Static versus none policies for whole-core pinning on latency-sensitive pools.
- [Control Topology Management Policies on a Node](https://kubernetes.io/docs/tasks/administer-cluster/topology-manager/) — NUMA alignment policies including `single-numa-node` for databases and caches.
- [Memory Manager System Configuration](https://kubernetes.io/docs/tasks/administer-cluster/memory-manager/) — Static memory pinning paired with Topology Manager on bare-metal pools.
- [Assign Memory Resources to Containers and Pods](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/) — Request/limit semantics and OOM behavior that drive RAM sizing.
- [Considerations for Large Clusters](https://kubernetes.io/docs/setup/best-practices/cluster-large/) — Pods-per-node defaults, scaling limits, and control-plane pressure at scale.
- [Pod Disruption Budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#pod-disruption-budgets) — How `minAvailable` / `maxUnavailable` translate into minimum node headroom during maintenance.
- [etcd Hardware recommendations](https://etcd.io/docs/v3.6/op-guide/hardware/) — Disk latency, CPU, and memory guidance for quorum members on owned hardware.
- [Dell PowerEdge for Kubernetes reference architecture](https://infohub.delltechnologies.com/en-us/l/dell-poweredge-for-kubernetes-2-0/kubernetes-node-sizing-considerations/) — Vendor-neutral node sizing patterns for worker and control-plane roles (verify SKU against your workload profile).
- [Thread and Memory Placement on NUMA Systems: Asymmetry Matters](https://www.usenix.org/publications/login/oct15/lepers) — Authoritative NUMA placement performance data for dual-socket sizing decisions.
