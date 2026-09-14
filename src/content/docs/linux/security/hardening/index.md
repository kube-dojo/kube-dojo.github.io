---
title: "Security Hardening"
sidebar:
  order: 0
---
> **Protecting Linux systems and containers through kernel-level security.**

## Overview

Security isn't just firewalls—it's defense in depth. This section covers the Linux security mechanisms that protect containers and hosts: kernel tuning, mandatory access controls (AppArmor, SELinux), and system call filtering (seccomp).

## Modules

| # | Module | Description | Time |
|---|--------|-------------|------|
| 4.1 | [Kernel Hardening & sysctl](module-4.1-kernel-hardening/) | Network stack, memory protection, kernel parameters | 70–100 min |
| 4.2 | [AppArmor Profiles](module-4.2-apparmor/) | Mandatory access control, profile modes, K8s integration | 80–110 min |
| 4.3 | [SELinux Contexts](module-4.3-selinux/) | Policies, contexts, enforcing mode, troubleshooting | 80–110 min |
| 4.4 | [seccomp Profiles](module-4.4-seccomp/) | System call filtering, custom profiles | 80–110 min |

These are planning estimates copied from the four module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **310–430 minutes (about 5–7 hours)**; individual setup, reading, and practice time will vary.

## Why This Section Matters

Linux security features are directly used by Kubernetes:

- **sysctl** — Node hardening, network security
- **AppArmor** — Pod security profiles (Ubuntu/Debian)
- **SELinux** — Pod security profiles (RHEL/CentOS)
- **seccomp** — System call filtering for containers

CKS (Certified Kubernetes Security Specialist) specifically tests these topics.

## Prerequisites

- [Container Primitives](../../foundations/container-primitives/) — Especially capabilities & LSMs
- [Networking](../../foundations/networking/) — For network hardening

## Key Takeaways

After completing this section, you'll understand:

1. How to harden Linux kernels via sysctl
2. How AppArmor profiles restrict application behavior
3. How SELinux provides mandatory access control
4. How seccomp filters dangerous system calls

## Related Sections

- **Previous**: [Networking](../../foundations/networking/)
- **Next**: [System Administration](../../operations/module-8.1-storage-management/)
- **CKS**: Directly tested in System Hardening domain
