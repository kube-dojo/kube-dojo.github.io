---
title: "Networking"
sidebar:
  order: 0
---
> **The network stack that powers container and Kubernetes networking.**

## Overview

Linux networking is the foundation for everything in Kubernetes—pod-to-pod communication, services, ingress, network policies. Understanding it helps you debug networking issues and understand how Kubernetes abstractions actually work.

## Modules

| # | Module | Description | Time |
|---|--------|-------------|------|
| 3.1 | [Module 3.1: TCP/IP Essentials](module-3.1-tcp-ip-essentials/) | OSI model, TCP vs UDP, subnetting, routing | 80–110 min |
| 3.2 | [Module 3.2: DNS in Linux](module-3.2-dns-linux/) | resolv.conf, dig, DNS debugging | 80–110 min |
| 3.3 | [Module 3.3: Network Namespaces & veth](module-3.3-network-namespaces/) | veth pairs, bridges, pod networking | 140–170 min |
| 3.4 | [Module 3.4: iptables & netfilter](module-3.4-iptables-netfilter/) | Packet filtering, NAT, kube-proxy internals | 80–110 min |

These are planning estimates copied from the four module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **380–500 minutes (about 6 hours 20 minutes–8 hours 20 minutes)**; individual setup, reading, and practice time will vary.

## Why This Section Matters

Almost every Kubernetes issue eventually involves networking:

- **Pod can't reach service?** Understand routing and iptables
- **DNS resolution failing?** Know how Linux resolves names
- **Network policy not working?** Understand how netfilter works
- **Performance issues?** Could be network namespace or iptables overhead

## Prerequisites

- [System Essentials](../system-essentials/) — Processes, filesystem
- [Container Primitives](../container-primitives/) — Namespaces concept

## Key Takeaways

After completing this section, you'll understand:

1. How TCP/IP works and how to troubleshoot connectivity
2. How Linux resolves DNS and why containers have DNS issues
3. How network namespaces create isolated network stacks (pod networking)
4. How iptables/netfilter powers Kubernetes services and policies

## Related Sections

- **Previous**: [Container Primitives](../container-primitives/)
- **Next**: [Security/Hardening](../../security/hardening/)
- **Applies to**: Every network-related Kubernetes concept