---
title: "Container Primitives"
sidebar:
  order: 0
---
> **The Linux features that make containers possible.**

## Overview

Containers aren't magic—they're built on Linux kernel features that have existed for years. This section demystifies container technology by teaching you the primitives: namespaces, cgroups, capabilities, and union filesystems.

After this section, you'll understand that a "container" is just a process with:
- **Namespaces** — Isolated view of system resources
- **Cgroups** — Resource limits (CPU, memory)
- **Capabilities** — Fine-grained privileges
- **Union filesystem** — Layered filesystem (image + container layer)

## Modules

| # | Module | Description | Time |
|---|--------|-------------|------|
| 2.1 | [Module 2.1: Linux Namespaces](module-2.1-namespaces/) | PID, network, mount, UTS, user isolation | 120–150 min |
| 2.2 | [Module 2.2: Control Groups (cgroups)](module-2.2-cgroups/) | CPU/memory limits, v1 vs v2, systemd integration | 80–110 min |
| 2.3 | [Module 2.3: Capabilities & Linux Security Modules](module-2.3-capabilities-lsms/) | CAP_*, AppArmor, SELinux, seccomp overview | 70–100 min |
| 2.4 | [Module 2.4: Union Filesystems](module-2.4-union-filesystems/) | OverlayFS, layers, storage drivers | 70–100 min |

These are planning estimates copied from the four module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **340–460 minutes (about 5 hours 40 minutes–7 hours 40 minutes)**; individual setup, reading, and practice time will vary.

## Why This Section Matters

Understanding container primitives lets you:

- **Debug container issues** — Is it a namespace issue? A cgroup limit? Missing capabilities?
- **Write secure containers** — Know which capabilities to drop, which syscalls to block
- **Optimize images** — Understand layers and copy-on-write
- **Understand Kubernetes** — Pod security, resource requests/limits, storage

## Prerequisites

- [System Essentials](../system-essentials/) — Kernel, processes, filesystem, permissions

## Key Takeaways

After completing this section, you'll understand:

1. How namespaces create isolated environments (the "container" illusion)
2. How cgroups enforce resource limits (what happens when memory is exceeded)
3. Why containers don't need root (capabilities breakdown)
4. How container images share layers efficiently (OverlayFS)

## Related Sections

- **Previous**: [System Essentials](../system-essentials/)
- **Next**: [Networking](../networking/)
- **Applies to**: Every container and Kubernetes concept
