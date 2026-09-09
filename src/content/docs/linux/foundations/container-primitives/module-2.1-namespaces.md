---
citations_verified: true
title: "Module 2.1: Linux Namespaces"
slug: linux/foundations/container-primitives/module-2.1-namespaces
sidebar:
  order: 2
lab:
  id: "linux-2.1-namespaces"
  url: "https://killercoda.com/kubedojo/scenario/linux-2.1-namespaces"
  duration: "35-45 min"
  difficulty: "intermediate"
  environment: "ubuntu"
revision_pending: false
---

> **Linux Foundations** | Complexity: `[MEDIUM]` | Time: 35-45 min. This medium-depth lesson focuses on inspecting real namespace boundaries instead of memorizing container vocabulary.

## Prerequisites

Before starting this module, you should be comfortable reading Linux process output, using `sudo` for administrative commands, and interpreting basic network terms such as interface, address, route, and port.

Required preparation includes [Module 1.1: Kernel & Architecture](/linux/foundations/system-essentials/module-1.1-kernel-architecture/) because namespaces are implemented by the kernel, not by Docker, Kubernetes, or a shell trick.

Required preparation also includes [Module 1.2: Processes & systemd](/linux/foundations/system-essentials/module-1.2-processes-systemd/) because PID namespaces only make sense when you already know that Linux organizes running programs as processes.

A helpful but not mandatory prerequisite is basic networking vocabulary, especially loopback, virtual interfaces, routing tables, and the difference between binding a port inside a network stack and publishing a port on a host.

## Learning Outcomes

After completing the module and lab, you should be able to use namespace evidence to diagnose container behavior, explain Kubernetes pod sharing choices, and choose safer debugging approaches under pressure.

- **Debug** container isolation problems by comparing namespace identities in `/proc/<pid>/ns` and choosing which namespace boundary is relevant to the symptom.
- **Create** isolated PID, mount, UTS, IPC, and network environments with `unshare`, `ip netns`, and `nsenter`, then verify the effect with Linux inspection commands.
- **Compare** host, container, and Kubernetes pod namespace layouts so you can explain why some resources are shared while others remain private.
- **Evaluate** when namespace sharing options such as `hostNetwork`, `hostPID`, shared process namespaces, or user namespaces improve an operation and when they weaken isolation.
- **Design** a practical troubleshooting workflow for a minimal container image by entering selected namespaces from the host without changing the running workload.

## Why This Module Matters

A platform engineer is called into an incident after a routine rollout turns messy. The application container is healthy according to Kubernetes, but it cannot connect to its database. The image is intentionally minimal, so it has no `ip`, no `ping`, no package manager, and no shell that feels useful. The team can see a process, a pod, a node, and a service, but nobody can tell which network view the failing process actually has.

Another engineer tries to help by running the same command on the node, but it succeeds there. That result is misleading because the node and the container are not using the same network namespace. A third engineer checks the application logs and sees only connection timeouts, which proves the symptom but not the boundary. The real question is not "does the node have networking?" but "what does this process see as its network stack?"

Namespaces are the kernel mechanism that makes this question precise. Containers are ordinary Linux processes with carefully selected namespace memberships, cgroups, capabilities, and filesystem setup. Kubernetes builds pods by deciding which of those views are shared between containers and which are separate. If you can inspect namespace boundaries directly, container behavior stops feeling magical and starts becoming debuggable.

The senior-level skill is not memorizing the eight namespace names. The useful skill is mapping a symptom to the namespace that can explain it, entering that namespace without damaging the workload, and knowing which isolation guarantees still hold after a runtime or Kubernetes option changes the default layout. This module teaches that workflow from first principles.

## What Namespaces Change

A namespace gives a process a particular view of a global kernel-managed resource. The resource still belongs to the same running kernel, but the process sees a scoped version of it. That scoped view might include a different hostname, a different process tree, a different mount table, a different network stack, or a different user ID mapping.

This distinction matters because a namespace is not a virtual machine. A virtual machine runs a separate guest kernel with its own hardware abstraction. A containerized process usually shares the host kernel while receiving isolated views of selected resources. That is why containers can start quickly, consume fewer resources than virtual machines, and still leak risk when the wrong boundary is assumed.

The easiest mental model is "same kernel, different windows." Two processes can sit on the same host and still look through different windows at process IDs, routes, mounted filesystems, or hostnames. Debugging begins by asking which window the process is looking through, then comparing that window to the host or to another process.

```mermaid
flowchart TD
    subgraph Host["Same Linux kernel on one host"]
        Kernel["Kernel manages global resources"]
        subgraph ProcessA["Process A namespace views"]
            A1["PID view: only its tree"]
            A2["Network view: eth0 and its routes"]
            A3["Mount view: container root filesystem"]
        end
        subgraph ProcessB["Process B namespace views"]
            B1["PID view: different tree"]
            B2["Network view: different eth0 and routes"]
            B3["Mount view: different root filesystem"]
        end
        Kernel --> A1
        Kernel --> A2
        Kernel --> A3
        Kernel --> B1
        Kernel --> B2
        Kernel --> B3
    end
```

A namespace boundary answers a very practical question: "would two processes see the same thing if they ran the same inspection command?" If two processes share a network namespace, `ip addr` and `ip route` describe the same network stack for both. If two processes use different mount namespaces, the path `/etc/passwd` can refer to different files even when the path string is identical.

> **Active learning prompt:** A container can resolve DNS but cannot connect to `127.0.0.1:5432`, while the database listens on `127.0.0.1:5432` on the node. Before reading further, decide which namespace boundary most likely explains the failure and why the loopback address is a clue.

Loopback is a strong clue because `127.0.0.1` always means "this network namespace," not "this physical machine." If the database listens on node loopback and the application runs inside a different network namespace, the application is connecting to itself, not to the node service. The fix might involve a service address, a host gateway, or `hostNetwork`, but the diagnosis starts by recognizing the namespace boundary.

The kernel exposes namespace membership through [symbolic links under `/proc/<pid>/ns`](https://en.wikipedia.org/wiki/Linux_namespaces). Each link points to a namespace object with a stable identity while it exists. Two processes are in the same namespace of a given type when the corresponding links point to the same object. That check is more reliable than guessing from container names or Kubernetes labels.

```bash
ls -l /proc/$$/ns
```

A typical output includes entries such as `mnt`, `uts`, `ipc`, `pid`, `net`, `user`, `cgroup`, and sometimes `time`, depending on the kernel and tool versions. The exact numeric identifiers vary across systems, so treat them as identities to compare, not values to memorize.

The namespace types you will meet most often in container troubleshooting are summarized below. The table is a map for diagnosis: start with the symptom, then choose the namespace type that controls the resource involved.

| Namespace | Resource view it isolates | Practical symptom it can explain | Common inspection command |
|-----------|---------------------------|-----------------------------------|---------------------------|
| Mount (`mnt`) | Mount points and visible filesystem tree | A file exists in one container but not another | `findmnt`, `mount`, `ls` |
| UTS (`uts`) | Hostname and NIS domain name | A process reports a container hostname instead of the node name | `hostname` |
| IPC (`ipc`) | System V IPC and POSIX message queues | Shared memory or semaphores are visible unexpectedly | `ipcs` |
| PID (`pid`) | Process ID tree and process visibility | A container sees its app as PID 1 and cannot see node processes | `ps`, `/proc` |
| Network (`net`) | Interfaces, addresses, routes, firewall view, and port space | A port works in one container but not from the node | `ip addr`, `ip route`, `ss` |
| User (`user`) | UID and GID mappings plus capability ownership | Root inside a container is not root on the host | `id`, `/proc/<pid>/uid_map` |
| Cgroup (`cgroup`) | Cgroup root path visibility | A process sees a scoped resource-control hierarchy | `/proc/self/cgroup` |
| Time (`time`) | Selected monotonic and boot-time clock offsets | A containerized process sees adjusted monotonic time | `/proc/self/timens_offsets` |

Namespaces are only one part of container isolation. Capabilities control which privileged operations a process can perform. Seccomp filters system calls. Linux Security Modules such as AppArmor or SELinux enforce policy. Cgroups limit and account for resource usage. You should think of namespaces as "what the process can see," not as a complete answer to "what the process can do."

## Inspecting Namespace Membership

The fastest safe inspection technique is comparing namespace links for two processes. You do not need to enter the namespace, restart the container, or install tools in the image. You only need the host PID of the target process and permission to inspect `/proc`.

Start with your current shell because it gives you a baseline. The shell variable `$$` expands to the current shell process ID. When you list `/proc/$$/ns`, Linux shows namespace links for that process. The link target includes the namespace type and an identifier, which can be compared against another process.

```bash
ls -l /proc/$$/ns
```

Now compare your shell to PID 1 on the host. On a normal node, PID 1 is the system init process, often `systemd`. A regular shell usually shares many namespaces with PID 1 unless it is already running inside a container, a user namespace, or a special service sandbox.

```bash
sudo ls -l /proc/1/ns
ls -l /proc/$$/ns
```

The command `lsns` provides a summarized view of namespace objects known to the system. It is useful when you want to see which process owns a namespace or when several containers are running and you need a broad map before focusing on one target.

```bash
lsns
lsns -t net
lsns -t pid
```

A strong troubleshooting habit is to record the target process first, then inspect only the relevant namespace type. For a network symptom, compare `net`. For a process visibility symptom, compare `pid`. For a file visibility symptom, compare `mnt`. This keeps the investigation narrow enough to avoid chasing unrelated isolation mechanisms.

```bash
target_pid=1
readlink /proc/$$/ns/net
sudo readlink /proc/${target_pid}/ns/net
```

If the link targets differ, the two processes do not share that network namespace. If they match, a network difference is probably not caused by namespace separation between those two processes, and you should move to routes, firewall rules, DNS, or service configuration.

> **Active learning prompt:** Your teammate says, "The container cannot be isolated because I can see its process from the host with `ps`." Decide whether that statement proves the container lacks a PID namespace. What would you compare in `/proc/<pid>/ns` to make the claim precise?

Seeing a container process from the host does not prove the container lacks a PID namespace. The host PID namespace is the parent view and can usually see descendant processes. The more important question is what the process sees from inside its own PID namespace. Compare `/proc/<host-pid>/ns/pid` with `/proc/1/ns/pid`, then enter the target PID namespace or inspect from inside the container if you need to verify the internal process view.

The following small diagnostic pattern is safe on a lab machine because it only reads namespace identities. It compares the current shell with a target PID and prints the namespace types that differ. Use it as a reading exercise before copying it into your own notes.

```bash
target_pid=1

for ns in cgroup ipc mnt net pid user uts; do
  mine=$(readlink "/proc/$$/ns/${ns}")
  target=$(sudo readlink "/proc/${target_pid}/ns/${ns}")
  if [ "$mine" = "$target" ]; then
    printf "%-8s shared    %s\n" "$ns" "$mine"
  else
    printf "%-8s different mine=%s target=%s\n" "$ns" "$mine" "$target"
  fi
done
```

This pattern also teaches the senior workflow: compare first, enter second. Entering a namespace is powerful, but it changes your perspective and can lead to accidental commands in the wrong context. A read-only comparison gives you a map before you step through any boundary.

## PID Namespaces: Process Trees and PID 1

A PID namespace isolates process ID numbers and process visibility. [The host can usually see processes in child PID namespaces, but a process inside a child namespace sees only processes in its own namespace and descendants.](https://en.wikipedia.org/wiki/Linux_namespaces) That asymmetric visibility is the source of many container debugging misunderstandings.

Without a PID namespace, every process participates in the same host process tree. A process listing from a regular shell can show system services, runtime processes, and application processes together. The process IDs are unique within that shared view.

```mermaid
flowchart LR
    systemd["PID 1 on host: systemd"] --> sshd["PID 108: sshd"]
    systemd --> runtime["PID 320: container runtime"]
    systemd --> app["PID 850: application process"]
    app --> worker["PID 851: worker child"]
```

With a PID namespace, the same application can have one PID from the host perspective and a different PID inside the namespace. The first process inside the namespace becomes PID 1 in that namespace, even though the host sees it as an ordinary process with a different number. Both views are correct because they are views from different namespaces.

```mermaid
flowchart LR
    subgraph HostView["Host PID namespace"]
        hostInit["PID 1: systemd"] --> hostRuntime["PID 320: container runtime"]
        hostRuntime --> hostApp["PID 850: app process"]
        hostApp --> hostWorker["PID 851: worker child"]
    end
    subgraph ContainerView["Container PID namespace"]
        contApp["PID 1: app process"] --> contWorker["PID 2: worker child"]
    end
```

PID 1 has special responsibilities. It receives orphaned child processes, must reap zombies, and has special default signal behavior. A program that works well as a normal process can behave poorly as PID 1 if it does not forward signals or reap children. [That is why production containers often use a tiny init process such as `tini` or `dumb-init`.](https://docs.docker.com/reference/cli/docker/container/run)

The worked example below creates a new PID namespace and mounts a matching `/proc` view. The `--fork` flag matters because `unshare --pid` creates a new PID namespace for child processes, not for the already-running `unshare` process itself. The `--mount-proc` flag makes `ps` and `/proc` reflect the new PID namespace instead of the host process view.

```bash
sudo unshare --pid --fork --mount-proc bash
```

Inside the new shell, run these commands. You should see a small process list and a low PID for the shell because this namespace has its own process numbering. The output will vary, but the pattern should be clear.

```bash
ps -ef
echo "namespace shell PID is $$"
ls /proc | head
exit
```

If you omit `--mount-proc`, many learners get confused because `ps` may still read the old `/proc` mount and appear to show host processes. That does not mean the PID namespace failed. It means your filesystem view still points tools at a `/proc` mount that does not match your new PID view. This is the first place where PID and mount namespaces interact.

A senior debugger watches for this kind of cross-namespace mismatch. Tools are just processes reading files and making system calls. If the tool's mount namespace points at one `/proc` view while the process runs in another PID namespace, the output can mislead you. Good debugging means checking both the tool's namespace and the data source it reads.

## Network Namespaces: Interfaces, Routes, and Port Space

A network namespace isolates the network stack. [Each network namespace has its own interfaces, addresses, loopback device, routing tables, neighbor table, firewall view, and listening port space.](https://en.wikipedia.org/wiki/Linux_namespaces) Two processes can both listen on TCP port `80` when they are in different network namespaces because each namespace has its own port table.

A newly created network namespace is intentionally lonely. It normally contains only a loopback interface, and that loopback interface may be down until you bring it up. There is no default route, no `eth0`, and no automatic path to the internet. Container runtimes add connectivity by creating virtual Ethernet pairs, moving one end into the container namespace, and connecting the host end to a bridge, overlay, or other network backend.

```mermaid
flowchart TD
    subgraph Host["Host network namespace"]
        Bridge["bridge or CNI device"]
        HostVethA["veth host end A"]
        HostVethB["veth host end B"]
        Bridge --- HostVethA
        Bridge --- HostVethB
    end
    subgraph ContainerA["Container A network namespace"]
        EthA["eth0: address for app A"]
        LoA["lo: container A loopback"]
    end
    subgraph ContainerB["Container B network namespace"]
        EthB["eth0: address for app B"]
        LoB["lo: container B loopback"]
    end
    HostVethA --- EthA
    HostVethB --- EthB
```

Create a named network namespace with `ip netns`. Named namespaces are convenient for learning because the `ip` tool stores bind mounts under `/var/run/netns`, making the namespace easy to list, enter, and delete. This is not exactly how every container runtime manages namespaces, but it teaches the same kernel mechanism. [Part 3 of the hands-on exercise](#part-3-create-a-network-namespace) combines these observations with ownership checks and cleanup traps.

In the exercise's test run, the fresh namespace showed only a loopback interface, initially down. Bringing `lo` up configured loopback addresses; the exercise did not add an interface connecting this namespace to another network. Loopback is local delivery, not an external connection.

The route table deserves one precise distinction. Linux keeps several routing tables: per [ip-route(8)](https://man7.org/linux/man-pages/man8/ip-route.8.html), normal routes go into the `main` table (ID 254), while routes for local and broadcast addresses live in the `local` table (ID 255), which the kernel maintains automatically. `ip route show` displays table `main` by default. When you bring `lo` up, the kernel places the loopback routes in the `local` table, so the IPv4 `main` table stays empty. An empty `main` table is therefore not the same as "no routes at all": the namespace can still deliver to its own loopback addresses, it just has no route toward anything beyond itself.

Deleting the name is also more subtle than it looks. Per [ip-netns(8)](https://man7.org/linux/man-pages/man8/ip-netns.8.html), `ip netns delete` unmounts and removes the named entry under `/var/run/netns`, but the namespace itself is freed only when its last user goes away. A running process or an open file descriptor can keep the namespace alive after its name is gone, so a missing entry in `ip netns list` does not by itself prove the namespace ceased to exist.

> **Active learning prompt:** Two containers in the same pod can both reach an application on `localhost`, but two containers in different pods cannot use `localhost` to reach each other. Decide which namespace sharing decision explains the difference before reading the Kubernetes section.

The answer is network namespace sharing. Containers in the same Kubernetes pod share one network namespace by default, so `localhost` refers to the same network stack for those containers. Containers in different pods have different network namespaces, so each pod has its own loopback device and port space. They must communicate through pod IPs, Services, or another network path.

The network namespace is also why host-level checks can be false reassurance. A successful `curl` from the node proves the node namespace has connectivity. It does not prove the target container namespace has the same route, DNS configuration, firewall behavior, or source address. When the symptom is network-specific, run the network inspection from the target namespace.

## Mount Namespaces: Filesystem Views Without Separate Kernels

A mount namespace isolates the set of mount points a process sees. It does not magically copy every file, and it does not require a separate disk. Instead, it lets the kernel present a different mounted filesystem tree to different processes. Container runtimes combine mount namespaces with image layers, writable container layers, bind mounts, and special filesystems such as `/proc`.

The key debugging question is whether two processes see the same mount table. If they do not, the same path can mean different things. The path `/etc/hosts` inside a container may be a runtime-generated file. The path `/var/log/app.log` inside one container may not exist in a sidecar unless a shared volume is mounted into both containers.

```mermaid
flowchart LR
    subgraph HostMounts["Host mount namespace"]
        HostRoot["/ host root filesystem"] --> HostEtc["/etc/passwd host file"]
        HostRoot --> HostVar["/var host data"]
        HostRoot --> HostProc["/proc host process view"]
    end
    subgraph ContainerMounts["Container mount namespace"]
        ContRoot["/ image plus writable layer"] --> ContEtc["/etc/passwd image file"]
        ContRoot --> ContWork["/work app directory"]
        ContRoot --> ContProc["/proc matched to container view"]
    end
```

The [mount exercise in Part 4](#part-4-create-a-mount-namespace) makes this distinction observable: a child mounts a tmpfs at a newly created directory, writes a file through that mount, and exits. The parent then checks its own mount table and filesystem view. Predict what remains: the directory, the mount, or the file? A directory in the underlying filesystem is different from a mount attached to that path in one namespace.

Mount namespaces interact heavily with security. Accidentally bind-mounting sensitive host paths into a container can defeat filesystem isolation even when the container has its own mount namespace. The namespace controls the view; the mounts placed into that view determine what data is exposed. A private view containing `/var/run/docker.sock` is still dangerous because the socket grants control over the container runtime.

Mount propagation is the senior-level wrinkle. [Some mounts can propagate between namespaces when configured as shared, slave, or private.](https://kubernetes.io/docs/concepts/storage/volumes/) Kubernetes volume behavior and privileged storage agents sometimes depend on propagation settings. When a mount appears or disappears unexpectedly, inspect `findmnt -o TARGET,PROPAGATION` instead of assuming mount namespaces are absolute walls.

```bash
findmnt -o TARGET,PROPAGATION /
findmnt -o TARGET,PROPAGATION /tmp
```

## UTS and IPC Namespaces: Small Boundaries With Big Effects

The UTS namespace isolates the hostname and domain name visible to a process. It is simple compared with network or mount namespaces, but it matters because many applications report host identity in logs, metrics, prompts, and cluster membership. A container can have a hostname that matches its pod name without changing the node hostname.

Try a UTS namespace by changing the hostname inside an isolated shell. The hostname change should not affect the host after you exit. This is a safe example because it demonstrates the namespace boundary without altering networking or filesystems.

```bash
sudo unshare --uts bash
hostname namespace-lab
hostname
exit
hostname
```

IPC namespaces isolate inter-process communication objects such as System V shared memory, semaphores, message queues, and POSIX message queues. Most web workloads do not expose IPC details directly, but databases, legacy applications, and high-performance local systems sometimes rely on shared memory. Isolation prevents unrelated containers from reading or interfering with each other's IPC objects.

```bash
ipcs
sudo unshare --ipc bash
ipcs
exit
```

In ordinary Linux pods, [Kubernetes 1.35 documents same-pod network sharing and communication through OS-level IPC](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/#pod-networking). Containers share the pod's IPC namespace; this is not an optional per-container runtime choice. [`hostIPC: true` instead shares the host's IPC namespace](https://v1-35.docs.kubernetes.io/docs/concepts/security/pod-security-standards/#baseline), removing that pod boundary. Same-pod IPC can help tightly coupled sidecars, but it also exposes IPC objects to other containers in that pod; it does not promise unrestricted IPC between separate pods.

A useful decision rule is to treat UTS and IPC as "small surface, sharp edge" namespaces. UTS rarely causes deep incidents by itself, but wrong host identity can confuse observability and clustering. IPC is invisible until an application depends on it, and then it can become either a required coupling mechanism or an unexpected security risk.

## User Namespaces: Root Inside Is Not Always Root Outside

A user namespace isolates user and group ID mappings. Inside the namespace, [a process may believe it is UID `0`, but the kernel maps that identity to a different unprivileged UID outside the namespace](https://kubernetes.io/docs/concepts/workloads/pods/user-namespaces/). This is the core idea behind rootless containers and an important mitigation when a process is compromised inside a container.

Without a user namespace, UID `0` inside a container is also UID `0` from the host kernel's perspective, although capabilities and other controls may still limit what it can do. With a user namespace, UID `0` inside can map to a high unprivileged host UID. Permission checks against host files then use the mapped outside identity.

```mermaid
flowchart LR
    subgraph NoUserNs["Without user namespace"]
        ContRootA["Container UID 0"] --> HostRootA["Host UID 0"]
        HostRootA --> RiskA["Host-root permission risk if other controls fail"]
    end
    subgraph WithUserNs["With user namespace"]
        ContRootB["Container UID 0"] --> HostUserB["Host UID 100000 or another unprivileged ID"]
        HostUserB --> RiskB["Host permission checks use mapped ID"]
    end
```

You can inspect mapping files through `/proc`. The current process mapping may be simple on a normal host shell. In a rootless container or user namespace, these files show how inside IDs map to outside IDs. The columns represent inside ID start, outside ID start, and length.

```bash
cat /proc/self/uid_map
cat /proc/self/gid_map
```

A typical subordinate ID configuration grants a user a range of host IDs that can be used for mappings. The exact values are system-specific. The important idea is that a runtime can map many container IDs to a controlled host range instead of granting real host root.

```bash
grep "^$(id -un):" /etc/subuid /etc/subgid 2>/dev/null || true
```

The mapping below shows the concept without requiring your system to use the same numbers. UID `0` inside maps to an unprivileged host UID. UID `1` inside maps to the next host UID in the range. Application users inside the container also map into the same outside range.

```mermaid
flowchart LR
    subgraph Mapping["Example user namespace mapping"]
        In0["Inside UID 0"] --> Out0["Outside UID 100000"]
        In1["Inside UID 1"] --> Out1["Outside UID 100001"]
        InApp["Inside UID 1000"] --> OutApp["Outside UID 101000"]
    end
```

User namespaces improve the blast-radius story, but they do not make every container safe. A process still shares the host kernel, can still consume resources unless cgroups limit it, and can still access any host path deliberately mounted with compatible permissions. Security comes from layered controls, not from one namespace type.

The operational trade-off is compatibility. Some workloads, volume permissions, device access patterns, and older tooling assume that container UID values match host UID values. Rootless designs may require explicit ownership planning for persistent volumes and build caches. The senior decision is not "always use user namespaces" but "use them where the permission model and operational tooling can support them."

## Cgroup and Time Namespaces: Less Visible, Still Relevant

The cgroup namespace isolates the view of cgroup paths. It does not create resource limits by itself; cgroups do that. The namespace controls what a process sees as the root of its cgroup hierarchy. This matters when software reads `/proc/self/cgroup` or cgroup filesystem paths and assumes it understands its place on the host.

```bash
cat /proc/self/cgroup
readlink /proc/$$/ns/cgroup
```

In containers, cgroup namespaces reduce information leakage about the host's full cgroup layout. They also make the process's environment look more self-contained. When debugging CPU or memory limits, remember that the cgroup namespace affects visibility while the cgroup controllers enforce limits and accounting. The next module covers cgroups in depth.

[The time namespace can offset certain clocks, especially monotonic and boot-time clocks, for processes inside the namespace.](https://en.wikipedia.org/wiki/Linux_namespaces) It is less common in day-to-day Kubernetes debugging than network, PID, or mount namespaces. It matters for checkpoint and restore workflows, tests that need controlled time views, and specialized runtime behavior.

```bash
readlink /proc/$$/ns/time 2>/dev/null || true
cat /proc/self/timens_offsets 2>/dev/null || true
```

The senior takeaway is to avoid overfitting your mental model to the most famous namespaces. Network, PID, and mount boundaries explain many incidents, but cgroup, user, IPC, UTS, and time namespaces can still appear in edge cases. When a symptom involves identity, clocks, resource visibility, shared memory, or hostnames, inspect the corresponding namespace before assuming the runtime is broken.

## Worked Example: Debug a Minimal Container Without Installing Tools

This worked example demonstrates the core practitioner workflow: find the target process, compare namespace membership, enter only the namespace you need, and run host tools from that perspective. The example uses Docker commands where available, but the Linux concept is the same for containerd, CRI-O, and Kubernetes after you identify the target PID.

Imagine a container named `web-app` cannot connect to a dependency. The image has no `ip`, no `ss`, and no `tcpdump`. Rebuilding the image during an incident would be slow and would change the thing you are trying to observe. Entering the network namespace lets you keep the workload unchanged while borrowing host tools.

First, find the host PID of the container's main process. Docker exposes it through `docker inspect`. In Kubernetes environments, you might obtain a container ID through `crictl ps` and inspect it with `crictl inspect`, but the goal is the same: get the host PID that anchors the namespaces.

```bash
PID=$(docker inspect --format '{{.State.Pid}}' web-app)
echo "Container host PID: ${PID}"
sudo readlink "/proc/${PID}/ns/net"
readlink /proc/$$/ns/net
```

If the network namespace differs from your shell, use `nsenter` to run a host binary inside that namespace. The `-t` option selects the target process, and `-n` means enter its network namespace. This command does not use the container filesystem unless you ask for the mount namespace too, so it can run the host's `ip` binary against the container's network stack.

```bash
sudo nsenter -t "${PID}" -n ip addr
sudo nsenter -t "${PID}" -n ip route
sudo nsenter -t "${PID}" -n ss -lntp
```

If you need packet capture and the host has `tcpdump`, run it the same way. This observes the target network namespace without installing anything in the image. Choose a narrow filter so the capture answers a specific question instead of producing noise.

```bash
sudo nsenter -t "${PID}" -n tcpdump -i any -nn 'tcp port 5432'
```

Now reason about the result. If the route table has no default route, the problem is namespace-local network configuration. If DNS fails but raw IP connectivity works, the next boundary may be resolver configuration in the mount namespace, such as `/etc/resolv.conf`. If the container listens on `127.0.0.1`, the service is local to the pod or container network namespace unless a proxy or port mapping exposes it elsewhere.

This example also shows why `nsenter` is safer when used selectively. Entering every namespace with `--all` can put you into the target filesystem, PID view, UTS name, IPC view, and user mapping at once. That can be useful, but it also increases confusion and risk. Enter the smallest set of namespaces that explains the symptom.

| Symptom | Namespace to inspect first | Useful host-side command | What a mismatch suggests |
|---------|----------------------------|---------------------------|--------------------------|
| Container cannot reach dependency | Network | `nsenter -t "$PID" -n ip route` | Different route, interface, or firewall view |
| Sidecar cannot read app file | Mount | `nsenter -t "$PID" -m findmnt` | Missing shared volume or wrong mount path |
| App ignores termination | PID | `nsenter -t "$PID" -p ps -ef` | App is PID 1 and lacks init behavior |
| Hostname in logs is surprising | UTS | `nsenter -t "$PID" -u hostname` | Container hostname differs from node |
| Shared memory appears missing | IPC | `nsenter -t "$PID" -i ipcs` | Processes do not share IPC namespace |
| Root cannot read host-mounted file | User | `cat /proc/"$PID"/uid_map` | Container root maps to unprivileged host UID |

After the incident, translate the observation into a durable fix. Do not leave a workload depending on a manual namespace entry. A missing route belongs in the CNI or pod network configuration. A missing file belongs in a Kubernetes volume mount. A PID 1 signal problem belongs in the image entrypoint or pod spec. Namespace debugging should shorten the path to the real configuration change.

## Kubernetes Pod Namespace Layout

Kubernetes uses namespaces to make a pod feel like one deployable unit while still running one or more containers. In ordinary Linux pods, [containers in the same pod share a network namespace](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/#pod-networking). This is why they have the same pod IP and can communicate through `localhost`. It is also why two containers in the same pod cannot both bind the same TCP port on the same address. They see the same configured pod hostname; that observable behavior does not require us to assume a shared UTS namespace in every runtime.

```mermaid
flowchart TD
    subgraph Pod["One Kubernetes pod"]
        NetNs["Shared network namespace\none pod IP, one loopback, one port space"]
        PodHostname["Same configured pod hostname\nUTS implementation not assumed"]
        IpcNs["Shared pod IPC namespace\nordinary Linux pod"]
        subgraph AppContainer["app container"]
            AppMnt["app mount namespace\napp image filesystem"]
            AppPid["app PID namespace by default"]
        end
        subgraph SidecarContainer["sidecar container"]
            SideMnt["sidecar mount namespace\nsidecar image filesystem"]
            SidePid["sidecar PID namespace by default"]
        end
        NetNs --> AppContainer
        NetNs --> SidecarContainer
        PodHostname --> AppContainer
        PodHostname --> SidecarContainer
        IpcNs --> AppContainer
        IpcNs --> SidecarContainer
    end
```

The mount namespace story is different. Containers in a pod usually have separate root filesystems because each container comes from its own image. [A shared volume gives both containers an explicit common file location.](https://kubernetes.io/docs/tasks/access-application-cluster/communicate-containers-same-pod-shared-volume/) Merely being in the same pod does not make an application's log path appear in the sidecar's filesystem. With process namespace sharing enabled, however, [another container's filesystem can be accessed through `/proc/<pid>/root`, subject to filesystem permissions](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/#understanding-process-namespace-sharing). Separate root filesystems therefore do not guarantee that files are inaccessible across containers. The logging example below uses a shared volume mounted at agreed paths.

The pod-sharing explanation here is checked against Kubernetes 1.35 documentation. Linux namespace inspection commands still run as host commands.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: shared-volume-demo
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "while true; do date >> /var/log/app/app.log; sleep 5; done"]
    volumeMounts:
    - name: app-logs
      mountPath: /var/log/app
  - name: sidecar
    image: busybox:1.36
    command: ["sh", "-c", "tail -F /logs/app.log"]
    volumeMounts:
    - name: app-logs
      mountPath: /logs
  volumes:
  - name: app-logs
    emptyDir: {}
```

In this BusyBox example, `-F` keeps retrying if `app.log` does not exist yet. An initial `can't open` message can therefore precede the log output when the writer creates the file. Retrying does not order the containers or establish application health: check that the sidecar actually prints the writer's lines. The shared volume supplies the common file location; the reader still needs to handle a file that has not appeared yet.

Ordinary Linux pods have separate container PID namespaces by default, as distinguished from the lower-level CRI default in the [Kubernetes v1.35.0 namespace API comments](https://github.com/kubernetes/kubernetes/blob/v1.35.0/staging/src/k8s.io/cri-api/pkg/apis/runtime/v1/api.proto). Setting [`spec.shareProcessNamespace: true` shares the process namespace inside the pod](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/). Containers can then see each other's processes, which can help sidecars send signals or collect diagnostics when permissions allow. It also weakens process isolation inside the pod, so it should be an explicit design decision rather than a default assumption.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: process-share-demo
spec:
  shareProcessNamespace: true
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
  - name: inspector
    image: busybox:1.36
    command: ["sh", "-c", "ps -ef; sleep 3600"]
```

Host namespace options are stronger exceptions. [`hostNetwork: true` places the pod in the node's network namespace. `hostPID: true` gives the pod visibility into node processes. `hostIPC: true` shares host IPC.](https://v1-35.docs.kubernetes.io/docs/concepts/security/pod-security-standards/#baseline) These options are legitimate for some system agents, but they are dangerous defaults for application workloads because they remove important boundaries.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: host-namespace-debug
spec:
  hostNetwork: true
  hostPID: true
  hostIPC: true
  containers:
  - name: debug
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    securityContext:
      privileged: true
```

A careful reviewer asks what problem each host namespace option solves. Node network agents may need `hostNetwork` because they configure or observe node-level networking. Process inspectors may need `hostPID` during controlled debugging. General application pods usually do not need either. If the reason is "it made the error go away," the team has hidden the boundary rather than understood it.

> **Active learning prompt:** A sidecar needs to scrape an admin endpoint from the main container. The team proposes `hostNetwork: true` because `localhost` worked during a node test. Evaluate that proposal and choose a safer pod-level design.

The safer design is usually to keep the shared pod network namespace and have the sidecar call `localhost:<admin-port>` inside the pod. `hostNetwork` is unnecessary for container-to-container communication within one pod because they already share the pod network namespace. Enabling host networking would expose the pod to node port conflicts and reduce isolation without solving a real namespace problem.

## Patterns & Anti-Patterns

The strongest namespace pattern is targeted inspection before intervention. Start with the symptom, identify the resource view involved, compare namespace links, and only then enter a namespace or change a pod specification. This works because namespace identity is objective evidence: two processes either share the same `net`, `mnt`, `pid`, `ipc`, `uts`, or `user` object, or they do not. The pattern scales well from a laptop lab to a production node because it avoids image changes and keeps the first diagnostic step read-only.

A second reliable pattern is deliberate pod-level sharing. Kubernetes already shares the network namespace inside a pod, so sidecars that need to scrape `localhost` endpoints can usually stay inside normal pod networking. File sharing, process sharing, and host namespace access should be added explicitly when the workload needs them, with the pod spec documenting the reason. That approach keeps the pod understandable: shared network for tight cooperation, shared volumes for files, optional process sharing for diagnostics, and host namespaces only for trusted node agents.

The third pattern is layered isolation. Namespaces answer what a process can see, while cgroups, capabilities, seccomp, and Linux Security Modules answer different parts of what the process can consume or do. A production design should not treat any one mechanism as the whole security story. User namespaces can reduce the meaning of container root, but a sensitive host bind mount or an excessive capability set can still turn a private view into a dangerous one.

The common anti-pattern is using host namespace options as a shortcut when the team has not found the real boundary. `hostNetwork: true` can make a connection test pass by moving the pod into the node network namespace, but it also imports node port conflicts and exposes a wider surface. Mounting host paths to "just get the file" can bypass the mount namespace design that kept application data scoped. Entering every namespace with `nsenter --all` can be useful for a controlled debug shell, but it is a poor first move because it hides which boundary explained the symptom.

Another anti-pattern is assuming that same-pod means same-everything. Ordinary Linux pod containers share the pod IP, loopback, and IPC namespace, but have separate PID namespaces by default and normally keep separate root filesystems. Use a shared volume for the logging sidecar's agreed file path. Enable `shareProcessNamespace: true` only when shared process visibility is needed, remembering that it also permits filesystem access through `/proc/<pid>/root` subject to permissions.

The last anti-pattern is trusting tool output without checking the namespace behind the tool. `ps`, `ip`, `ss`, `findmnt`, and `hostname` all report the world visible to the process that runs them. If you run the command from the host, you get the host view. If you run the host binary through `nsenter -t "$PID" -n`, you get the target network view while still using host tooling. The difference is not cosmetic; it decides whether the evidence belongs to the failing workload.

## Decision Framework

Namespace debugging becomes faster when you classify the symptom first. A file problem is rarely solved by staring at routes. A port conflict is rarely explained by UID mapping. The table below is intentionally practical: it connects the observed failure to the first boundary worth checking.

| Observed failure | First namespace hypothesis | Verification step | Likely configuration fix |
|------------------|----------------------------|-------------------|--------------------------|
| App can reach `localhost` in one container but not another pod | Network namespace differs across pods | Compare pod IPs and run `ip addr` in each pod | Use a Service, pod IP, or sidecar pattern |
| Sidecar cannot see app log file | Mount namespaces are separate | Inspect volume mounts and `findmnt` in each container | Mount the same volume into both containers |
| Container exits slowly during rollout | PID 1 is not handling signals | Check process tree inside PID namespace | Add an init process or signal handling |
| Container root cannot modify a host-mounted path | User namespace remaps UID | Inspect `uid_map` and host file ownership | Align ownership, permissions, or runtime mapping |
| Debug command works on node but fails in container | Command ran in wrong namespace | Run inspection through `nsenter` or `kubectl exec` | Fix namespace-local route, DNS, or mount |
| Host port reports already in use with `hostNetwork` | Pod uses host network port space | Check `ss -lntp` on the node | Use pod networking or choose a free host port |
| Process monitor misses app children | PID namespace hides process tree | Compare PID namespaces and `shareProcessNamespace` | Enable process sharing only when justified |

A disciplined sequence prevents accidental changes. First, identify the target process or pod. Second, choose the namespace type based on the symptom. Third, compare namespace identities. Fourth, enter only the required namespace if you need live inspection. Fifth, map the observation back to a runtime, image, Kubernetes, or node configuration change.

This sequence is slower than guessing for the first five minutes and faster for the rest of the incident. It also produces evidence that another engineer can review. "The app has no default route inside its network namespace" is more actionable than "networking seems broken." "The sidecar has a different mount namespace and no shared volume at `/logs`" is more actionable than "the file disappeared."

## Did You Know?

- **Namespaces existed before modern container platforms.** [The mount namespace appeared years before Docker popularized containers](https://en.wikipedia.org/wiki/Linux_namespaces), and later namespace types filled in process, network, user, cgroup, and time isolation needs.

- **A Kubernetes pod is not a tiny virtual machine.** It is a coordinated set of containers where Kubernetes and the runtime decide which namespace views are shared and which remain per-container.

- **`nsenter` can combine perspectives deliberately.** You can use the target process's network namespace while keeping the host filesystem and host debugging binaries, which is valuable for minimal or distroless images.

- **User namespaces change permission meaning.** UID `0` inside a namespace can map to an unprivileged UID outside, so "root in the container" and "root on the host" are not always the same identity.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------------|-----------------|
| Treating namespaces as complete security isolation | Namespaces isolate views, but the kernel is still shared and other controls still matter | Combine namespaces with cgroups, capabilities, seccomp, and LSM policy |
| Running host commands and assuming they reflect the container | The host shell may use different network, mount, PID, or user namespaces | Run inspections through `kubectl exec`, `crictl`, or `nsenter` against the target process |
| Forgetting that PID 1 behaves differently | Applications may ignore signals, fail to reap children, or delay shutdown | Use a minimal init process or implement correct signal and child handling |
| Assuming pod containers share files automatically | Same-pod containers share networking but usually have separate mount namespaces | Use Kubernetes volumes such as `emptyDir` for intentional file sharing |
| Enabling `hostNetwork` to fix unknown network failures | It removes network isolation and introduces node-level port conflicts | Diagnose routes, DNS, and Services before choosing host networking |
| Confusing container root with host root | User namespace mappings and capabilities change what UID `0` can actually do | Inspect `uid_map`, capabilities, and mounted host paths before judging privilege |
| Entering every namespace at once during debugging | A full namespace entry can hide which boundary mattered and increases accidental change risk | Enter the smallest namespace set needed for the symptom |
| Leaving lab network namespaces or mounts behind | Persistent named namespaces and mounts can pollute later tests | Clean up only names and paths created by your run; investigate failed cleanup instead of deleting unrelated resources |

## Quiz

### Question 1

Your team deploys a web container that normally shuts down cleanly on a developer laptop. In Kubernetes, rolling updates wait for the grace period and then kill the container. Inside the container, `ps` shows the application process as PID 1. What namespace-related behavior should you investigate, and what change would you recommend?

<details>
<summary>Show answer</summary>

The process is running as PID 1 inside its PID namespace, so it has init-like responsibilities and special signal behavior. The investigation should check whether the application handles `SIGTERM` and reaps child processes correctly when it is PID 1. A practical fix is to add a minimal init such as `tini` or `dumb-init`, or to update the application entrypoint so it handles termination and children correctly. This recommendation aligns the Kubernetes shutdown path with Linux PID namespace behavior instead of simply increasing the grace period.

</details>

### Question 2

A database listens on `127.0.0.1:5432` on a node. A container on that node tries to connect to `127.0.0.1:5432` and gets connection refused. A teammate says the node firewall must be blocking loopback traffic. What namespace concept should you apply before changing firewall rules?

<details>
<summary>Show answer</summary>

Apply the network namespace concept. `127.0.0.1` refers to loopback inside the caller's current network namespace, not to the physical node in every context. If the container is in its own network namespace, it is connecting to its own loopback interface, not the node's loopback listener. You should inspect the container's network namespace with `nsenter -t <pid> -n` or a container exec command, then choose a real reachable address, Service, host gateway pattern, or deliberate `hostNetwork` design if justified.

</details>

### Question 3

An application container writes `/var/log/app/current.log`. A sidecar in the same pod tails `/var/log/app/current.log` but reports that the file does not exist. Both containers share the same pod IP. Which assumption is wrong, and how would you fix the pod design?

<details>
<summary>Show answer</summary>

The wrong assumption is that same-pod containers automatically share their filesystem view. They share the pod network namespace, but they usually have separate mount namespaces and separate image filesystems. The fix is to define a Kubernetes volume, such as `emptyDir`, mount it into the application at the path where logs are written, and mount the same volume into the sidecar at the path it tails. That makes file sharing explicit instead of relying on network namespace sharing.

</details>

### Question 4

A minimal production image has no `ip`, `ss`, `tcpdump`, package manager, or useful shell. The service cannot connect to an upstream endpoint, and rebuilding the image would take too long. How can you inspect the container's routes and sockets without modifying the image?

<details>
<summary>Show answer</summary>

Find the host PID of the container's main process, then use `nsenter` to enter only its network namespace while running host-installed tools. For example, `sudo nsenter -t "$PID" -n ip route` and `sudo nsenter -t "$PID" -n ss -lntp` use the host binaries against the target network namespace. This preserves the running workload and avoids installing packages in the image. If the route table or socket state differs from the host, you have evidence that the issue is namespace-local.

</details>

### Question 5

A security review finds that a compromised process is UID `0` inside a container. However, when it tries to read a host-mounted file owned by real host root, the kernel denies access. What should the reviewer inspect before concluding the denial is accidental?

<details>
<summary>Show answer</summary>

The reviewer should inspect the container process's user namespace mapping, especially `/proc/<pid>/uid_map` and `/proc/<pid>/gid_map`. With user namespaces, UID `0` inside the container can map to an unprivileged host UID outside the container. Host filesystem permission checks use the mapped outside identity, so access to files owned by host root can be denied even though the process appears as root inside. The reviewer should also check capabilities and mount configuration before making a complete security judgment.

</details>

### Question 6

A node-level monitoring agent needs to see host processes and network interfaces. An engineer suggests running it as a normal pod and mounting `/proc` from the host. Another engineer suggests enabling both `hostPID` and `hostNetwork`. How would you evaluate these options?

<details>
<summary>Show answer</summary>

The requirement maps to PID and network namespace visibility, so `hostPID` and possibly `hostNetwork` may be justified for a node-level agent. Mounting host `/proc` alone can create a misleading or partial view if the process namespace and `/proc` mount do not match the tool's expectations. However, host namespace sharing weakens isolation and should be limited to trusted system agents with appropriate security controls. The evaluation should state the exact observations the agent needs, enable only the required host namespaces, and document the security trade-off.

</details>

### Question 7

You run `unshare --pid bash` expecting the shell to become PID 1, but the process view does not look isolated. A teammate says PID namespaces are disabled on the machine. What should you check about the command before accepting that conclusion?

<details>
<summary>Show answer</summary>

Check whether the command used `--fork` and whether `/proc` was remounted for the new PID namespace. With `unshare --pid`, the new PID namespace applies to child processes, so `--fork` is needed for the shell to start inside it as the first process. Tools such as `ps` also read `/proc`, so `--mount-proc` is often needed to make the process listing match the new PID namespace. A better test is `sudo unshare --pid --fork --mount-proc bash`, followed by `ps -ef` and `echo $$`.

</details>

### Question 8

A team enables `hostNetwork: true` on an application pod because it fixes a connection problem during a deadline. The next deployment fails because another pod on the same node already uses the required port. What namespace lesson should guide the rollback and permanent fix?

<details>
<summary>Show answer</summary>

`hostNetwork: true` moved the pod into the node's network namespace, so the pod now shares the node's port space instead of getting an isolated pod network namespace. The port conflict is an expected consequence of removing network isolation. The rollback should restore normal pod networking if the application does not truly need host networking. The permanent fix should diagnose the original connection problem inside the pod network namespace, then correct DNS, routing, NetworkPolicy, Service configuration, or application target addresses.

</details>

## Hands-On Exercise

### Objective

Create and inspect several namespace types, then use the observations to explain a realistic container troubleshooting workflow. This exercise is designed for a Linux lab machine where you have `sudo`. Do not run it on a production node.

### Part 1: Build a Namespace Baseline

Begin by inspecting your current shell. The goal is not to memorize identifiers, but to learn how namespace identities are represented and compared. Save the output mentally or in a scratch note so later differences are easy to recognize.

```bash
ls -l /proc/$$/ns
readlink /proc/$$/ns/net
readlink /proc/$$/ns/pid
readlink /proc/$$/ns/mnt
lsns | head
```

Now compare your shell with PID 1. Some namespace links may match, and some may differ depending on whether your shell is already inside a container, terminal sandbox, or service environment. Treat the comparison itself as the skill.

```bash
sudo ls -l /proc/1/ns
for ns in mnt uts ipc pid net user cgroup; do
  printf "%s\n" "namespace: ${ns}"
  printf "  shell: "
  readlink "/proc/$$/ns/${ns}"
  printf "  pid1 : "
  sudo readlink "/proc/1/ns/${ns}"
done
```

#### Success Criteria for Part 1

- [ ] You can identify where Linux exposes namespace membership for a process.
- [ ] You can compare two processes and decide whether a namespace type is shared.
- [ ] You can explain why matching network namespace links matter more than matching process names during network debugging.

### Part 2: Create a PID Namespace

Create a PID namespace with a matching `/proc` view. The flags are part of the lesson: `--pid` creates the namespace for children, `--fork` starts the child inside it, and `--mount-proc` gives process tools a matching `/proc`.

```bash
sudo unshare --pid --fork --mount-proc bash
```

Inside the namespace, inspect the process tree. You should see a small process view. The shell should have a low PID because it is at the root of this namespace's process tree.

```bash
ps -ef
echo "inside PID namespace, shell PID is $$"
ls /proc | head
exit
```

#### Success Criteria for Part 2

- [ ] You created a PID namespace using `--pid --fork --mount-proc`.
- [ ] You verified that the process view inside the namespace is smaller than the host view.
- [ ] You can explain why PID 1 behavior matters for container shutdown.

### Part 3: Create a Network Namespace

Use a **root shell on a disposable Linux lab machine** with `iproute2`, `mktemp`, and `rmdir` available. The block below was exercised as root (UID 0) with iproute2-6.1.0 on kernel 7.0.14-orbstack. It does not test your machine's `sudo` policy, and its observations are not proof of identical behavior on other kernels, distributions, or `iproute2` versions.

Before running it, predict what will change when loopback comes up. Which output would show a local address, and which would show a route beyond the namespace? Compare your prediction with the address and route-table observations below. This exercise inspects configuration; it does not send a ping or test external connectivity.

Paste the complete block into the root shell. `bash` is explicit because the script uses Bash syntax, and the quoted `<<'LAB'` delimiter matters: without the quotes, your interactive shell would expand variables such as `$lab_dir` before the script ever runs. Do not paste the inner commands directly into your session, because `set -eu` and the exit trap are meant for a lab shell that exits when the block ends.

```bash
bash <<'LAB'
set -eu
for tool in ip mktemp rmdir; do
    command -v "$tool" >/dev/null || { printf 'Missing tool: %s\n' "$tool" >&2; exit 1; }
done
lab_dir=''
lab_name=''
created=0
cleanup() {
    status=$?
    trap - EXIT
    trap '' INT TERM
    if [ "$created" -eq 1 ]; then
        if ! ip netns delete "$lab_name"; then
            printf 'Namespace cleanup failed: %s\n' "$lab_name" >&2
            if [ "$status" -eq 0 ]; then status=1; fi
        fi
    fi
    if [ -n "$lab_dir" ] && ! rmdir -- "$lab_dir"; then
        printf 'Directory cleanup refused: %s\n' "$lab_dir" >&2
        if [ "$status" -eq 0 ]; then status=1; fi
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
lab_dir=$(mktemp -d /tmp/kd-netns.XXXXXX)
lab_name=${lab_dir##*/}
printf 'Reserved directory: %s\nNamespace name: %s\n' "$lab_dir" "$lab_name"
ip netns add "$lab_name"
created=1
ip -n "$lab_name" -brief address show
ip -n "$lab_name" link set lo up
ip -n "$lab_name" -brief address show lo
routes=$(ip -n "$lab_name" -4 route show table main)
if [ -n "$routes" ]; then
    printf 'FAIL: unexpected IPv4 main routes:\n%s\n' "$routes" >&2
    exit 1
fi
printf 'PASS: loopback is configured; the IPv4 main route table is empty\n'
LAB
```

The name comes from a temporary directory on purpose. `mktemp -d` creates a fresh, uniquely named directory, and its basename is only a *candidate* string for the namespace name. The name is actually reserved by `ip netns add`, which per [ip-netns(8)](https://man7.org/linux/man-pages/man8/ip-netns.8.html) creates the namespace only if the name is available in `/var/run/netns` and fails on a collision. The `created=1` flag is set only *after* `ip netns add` succeeds, so if the add fails because the name is already taken, cleanup will not delete a namespace that this run did not create.

Cleanup is deliberately narrow. The exit trap deletes only the one named namespace this run successfully created and removes only the one empty directory this run created, with every variable quoted. `rmdir` refuses a non-empty directory, so a stray file left by something else produces a reported refusal instead of a recursive deletion. Remember also what deletion proves: as the theory section noted, removing the name does not by itself prove the namespace ceased to exist, because other users can keep it alive.

The route check is precise about what it asserts. The script inspects the IPv4 `main` table explicitly with `ip -4 route show table main`. Per [ip-route(8)](https://man7.org/linux/man-pages/man8/ip-route.8.html), `main` (ID 254) holds normal routes while loopback's local and broadcast routes live in the kernel-maintained `local` table (ID 255). An empty IPv4 `main` table alongside a configured loopback is the expected, healthy state — not a claim that the namespace has no routes at all.

After the block exits, run `ip netns list` and check that the printed namespace name is absent. The `PASS` line describes the route observation before cleanup; a later cleanup error still requires investigation. Do not treat that line alone as completion.

This exercise starts no background processes and moves no physical devices into the namespace. SIGKILL cannot run the trap, so a killed shell may leave resources for inspection. Interruption during creation or before `created=1` can also leave an entry that the trap does not remove. Cleanup attempts are not a guarantee against every interruption; use the printed name to investigate, and do not delete another run's namespace. Running through `sudo` and arbitrary terminal-interruption behavior were not tested.

#### Success Criteria for Part 3

- [ ] You created a named network namespace and confirmed its printed name was absent after cleanup.
- [ ] You observed a configured loopback and an empty IPv4 `main` route table; you can explain why neither adds an external connection.
- [ ] You can explain why the `created` flag is set only after `ip netns add` succeeds.
- [ ] You can explain why `localhost` changes meaning across network namespaces.

### Part 4: Create a Mount Namespace

Use a **root Bash session on a disposable Linux lab machine** with util-linux and GNU coreutils installed. The block below was exercised as root in a kind node with util-linux 2.38.1; it does not test your machine's `sudo` policy. Here, “parent” means that Linux shell's mount namespace, not the Mac hosting a Linux VM.

Before running it, predict why removing an empty directory should succeed even though the child wrote a file at that path. The block creates its own directory with `mktemp -d`, rather than adopting a fixed name. Cleanup uses `rmdir`, which refuses to remove a non-empty directory; see the installed `mktemp --help` and `rmdir --help`.

Paste the complete block. `bash` is explicit because the script uses Bash syntax. `set -eu` stops on failed commands or unset variables inside this lab shell. The exit trap attempts to remove only the directory created by this run.

```bash
bash <<'LAB'
set -eu
for tool in unshare mount findmnt mktemp rmdir readlink; do
    command -v "$tool" >/dev/null
done
lab_dir=$(mktemp -d /tmp/kd-mnt-lab.XXXXXX)
printf 'Owned directory: %s\n' "$lab_dir"
cleanup() {
    status=$?
    trap - EXIT
    if ! rmdir -- "$lab_dir"; then
        printf 'Cleanup refused; inspect this exact directory: %s\n' "$lab_dir" >&2
        exit 1
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf 'Parent namespace: '; readlink /proc/self/ns/mnt
unshare --mount --propagation private bash -eu -s -- "$lab_dir" <<'CHILD'
lab_dir=$1
printf 'Child namespace: '; readlink /proc/self/ns/mnt
mount -t tmpfs -o size=1m tmpfs "$lab_dir"
printf 'namespace mount data\n' > "$lab_dir/data.txt"
findmnt --mountpoint "$lab_dir" -o TARGET,FSTYPE,PROPAGATION
cat "$lab_dir/data.txt"
CHILD
parent_mounts=$(findmnt --kernel --noheadings --raw --output TARGET)
while IFS= read -r target; do
    if [ "$target" = "$lab_dir" ]; then
        printf 'FAIL: unexpected parent mount\n' >&2
        exit 1
    fi
done <<< "$parent_mounts"
test ! -e "$lab_dir/data.txt"
printf 'PASS: parent has neither the mount nor its file\n'
LAB
```

Compare the two namespace identifiers and the child's `tmpfs`/`private` output. The final message checks the parent's view after the child exits; it is not a simultaneous observation from two shells. The directory survives until the exit trap removes it, while the file was written into the child's tmpfs. [Private propagation prevents mount events from propagating to other namespaces](https://man7.org/linux/man-pages/man7/mount_namespaces.7.html); [unshare has selected it by default since util-linux 2.27](https://man7.org/linux/man-pages/man1/unshare.1.html). The flag makes that choice explicit.

Why read the whole parent mount table? [`findmnt` returns 1 for errors as well as no match](https://man7.org/linux/man-pages/man8/findmnt.8.html). Treating every nonzero result as proof of absence could hide a broken check. Here the table read must succeed before the script searches its output.

If setup fails, the exit trap still attempts cleanup and preserves the failure status unless cleanup itself fails. If cleanup refuses, inspect the exact printed path; do not replace `rmdir` with recursive deletion. Do not start background processes or persist this namespace: its lifetime can extend beyond the script if another process or reference holds it. SIGKILL cannot run the shell's trap, so an abrupt termination may leave the owned directory for manual inspection. The checks above do not certify arbitrary interruption or privilege configurations.

#### Success Criteria for Part 4

- [ ] You created a mount namespace and mounted a tmpfs inside it.
- [ ] You observed that mount visibility depends on the mount namespace.
- [ ] The owned directory was removed, or cleanup reported a failure that you investigated without deleting unrelated data.
- [ ] You can explain why same-pod containers need shared volumes for shared files.

### Part 5: Create UTS and IPC Namespaces

Create a UTS namespace and change the hostname inside it. The host hostname should remain unchanged after you exit.

```bash
sudo unshare --uts bash
hostname kd-namespace-lab
hostname
exit
hostname
```

Create an IPC namespace and compare IPC object visibility. Many lab systems have few IPC objects, so the important observation is that `ipcs` runs against a scoped IPC view.

```bash
ipcs
sudo unshare --ipc bash
ipcs
exit
```

#### Success Criteria for Part 5

- [ ] You changed a hostname inside a UTS namespace without changing the host hostname.
- [ ] You ran `ipcs` inside an IPC namespace.
- [ ] You can describe when UTS and IPC namespaces matter in Kubernetes troubleshooting.

### Part 6: Practice a Targeted Debugging Decision

Choose one of the scenarios below and write a three-step debugging plan in your own notes. You do not need to run Kubernetes for this part. The goal is to align symptom, namespace, and inspection method.

Scenario A: A pod sidecar cannot read a file written by the app container, but both containers share the same pod IP.

Scenario B: A container can connect to a dependency by pod IP but not through `localhost`, even though a node-level test to `localhost` succeeds.

Scenario C: An application runs as root inside a container but cannot write to a host-mounted directory owned by root.

Scenario D: A minimal image has no network tools, but you need to inspect its route table during an incident.

#### Success Criteria for Part 6

- [ ] Your plan names the first namespace type you would inspect.
- [ ] Your plan includes one concrete Linux command or Kubernetes inspection step.
- [ ] Your plan separates observation from configuration change.
- [ ] Your plan explains why the chosen namespace boundary fits the symptom.

### Final Exercise Success Criteria

- [ ] You inspected namespace membership through `/proc/<pid>/ns`.
- [ ] You created PID, network, mount, UTS, and IPC namespaces in a lab.
- [ ] You cleaned up the named network namespace after use, or confirmed the lab script's exit trap removed it.
- [ ] You explained at least one interaction between two namespace types.
- [ ] You designed a targeted debugging plan for a realistic container symptom.

## Sources

- [Linux namespaces overview, man7.org](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [Linux pid_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)
- [Linux network_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/network_namespaces.7.html)
- [Linux mount_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/mount_namespaces.7.html)
- [util-linux unshare: namespace lifetime and explicit propagation](https://man7.org/linux/man-pages/man1/unshare.1.html)
- [util-linux findmnt: mount-table queries and exit status](https://man7.org/linux/man-pages/man8/findmnt.8.html)
- [iproute2 ip-netns: named namespace creation, deletion, and name lifetime](https://man7.org/linux/man-pages/man8/ip-netns.8.html)
- [iproute2 ip-route: main and local routing tables](https://man7.org/linux/man-pages/man8/ip-route.8.html)
- [Linux user_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)
- [Linux ipc_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/ipc_namespaces.7.html)
- [Linux uts_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/uts_namespaces.7.html)
- [Linux time_namespaces documentation, man7.org](https://man7.org/linux/man-pages/man7/time_namespaces.7.html)
- [Kubernetes pod share process namespace task](https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/)
- [Kubernetes pod host namespaces reference](https://kubernetes.io/docs/concepts/security/pod-security-standards/#host-namespaces)
- [en.wikipedia.org: Linux namespaces](https://en.wikipedia.org/wiki/Linux_namespaces) — This is a specific kernel interface claim and the allowlisted Linux namespaces article directly describes `/proc/pid/ns/*` symlinks and namespace identity comparison.
- [kubernetes.io: pods](https://kubernetes.io/docs/concepts/workloads/pods/) — The Kubernetes Pods concept page directly states that pod containers share the network namespace, IP address, ports, and `localhost`.
- [kubernetes.io: communicate containers same pod shared volume](https://kubernetes.io/docs/tasks/access-application-cluster/communicate-containers-same-pod-shared-volume/) — Kubernetes documentation directly teaches shared-volume communication as the mechanism for file sharing between containers in one pod.
- [docs.docker.com: run](https://docs.docker.com/reference/cli/docker/container/run) — Docker's CLI reference directly documents PID 1 special treatment and the purpose of `--init` for signal forwarding and zombie reaping.
- [kubernetes.io: user namespaces](https://kubernetes.io/docs/concepts/workloads/pods/user-namespaces/) — The Kubernetes user namespaces page directly states that root in the container can run as a different non-root user on the host and explains the mitigation value.
- [kubernetes.io: volumes](https://kubernetes.io/docs/concepts/storage/volumes/) — The Kubernetes volumes documentation directly covers mount propagation behavior and the `mountPropagation` field.
- [kubernetes.io: pod security standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — The Pod Security Standards page explicitly lists host namespace sharing as disallowed in Baseline and Restricted policies.

## Next Module

Continue to [Module 2.2: Control Groups (cgroups)](/linux/foundations/container-primitives/module-2.2-cgroups/) to learn how Linux limits, accounts for, and reports resource usage for the same containerized processes that namespaces isolate.
