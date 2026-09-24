---
revision_pending: false
title: "Module 3.3: DNS & CoreDNS"
slug: k8s/cka/part3-services-networking/module-3.3-dns
sidebar:
  order: 4
lab:
  id: cka-3.3-dns
  url: https://killercoda.com/kubedojo/scenario/cka-3.3-dns
  duration: "45 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Critical infrastructure component
>
> **Time to Complete**: 40-50 minutes
>
> **Prerequisites**: Module 3.1 (Services), Module 3.2 (Endpoints)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Resolve** service and pod DNS names across namespaces using short names, fully qualified names, search domains, and SRV records.
- **Diagnose** DNS failures by comparing application symptoms, Pod `/etc/resolv.conf`, CoreDNS health, CoreDNS logs, and Service endpoints.
- **Configure** CoreDNS safely for hosts entries, upstream forwarding, cache behavior, and rollback.
- **Evaluate** DNS policies for `ClusterFirst`, `Default`, `ClusterFirstWithHostNet`, and `None` when designing Pods.

---

## Why This Module Matters

Hypothetical scenario: your team deploys a new API behind a Kubernetes Service, the readiness probes are green, and the Service has endpoints, but the frontend still reports `could not resolve host`. The application team asks for a firewall change because the symptom looks like connectivity, while the platform team sees healthy Pods and healthy Services. The fastest path out of that confusion is to separate three questions: did the name resolve, did it resolve to the expected address, and can packets reach the endpoint after resolution succeeds?

Kubernetes DNS is the naming layer that lets workloads use stable Service names instead of chasing Pod IPs that change whenever Pods are replaced. Every request to a name such as `web-svc`, `web-svc.default`, or `web-svc.default.svc.cluster.local` depends on kubelet-injected resolver settings, a ClusterIP Service named `kube-dns`, and CoreDNS Pods that answer Kubernetes-aware DNS queries. When this layer fails, many unrelated applications can appear broken at the same time because their first dependency lookup never reaches the network path you intended to test.

This module treats DNS as an operational system rather than a magic lookup table. You will trace how a Pod receives DNS settings, how CoreDNS turns Service and Pod objects into records, why search domains make short names convenient but occasionally surprising, and how CoreDNS forwards external queries to upstream resolvers. You will also practice the CKA-style debugging habit of proving where a failure sits before changing cluster-wide DNS configuration.

The phone book analogy is still useful if you keep its limits in mind. DNS is the cluster phone book, CoreDNS is the operator answering lookup calls, and the `kube-dns` Service is the stable phone number that Pods dial. Unlike a printed phone book, this one is rebuilt continuously from the Kubernetes API, cached for short periods, and affected by each Pod's resolver policy.

---

## DNS Architecture in Kubernetes

Kubernetes DNS begins before any application code runs. When kubelet creates a Pod sandbox, it writes resolver configuration into the Pod so normal libraries can call DNS without knowing anything about Kubernetes. Under the default `ClusterFirst` policy, that resolver configuration points to the cluster DNS Service and includes search domains that make short Service names expand into Kubernetes names. The application still calls `getaddrinfo`, `curl`, or a language runtime resolver, but the name lookup is steered into the cluster DNS path.

```text
┌────────────────────────────────────────────────────────────────┐
│                   Kubernetes DNS Architecture                   │
│                                                                 │
│   ┌────────────────┐                                           │
│   │     Pod        │                                           │
│   │                │                                           │
│   │ curl web-svc   │                                           │
│   │      │         │                                           │
│   │      ▼         │                                           │
│   │ /etc/resolv.conf                                           │
│   │ nameserver 10.96.0.10  ──────────────────────┐            │
│   │ search default.svc...                         │            │
│   └────────────────┘                              │            │
│                                                   │            │
│                                                   ▼            │
│   ┌──────────────────────────────────────────────────────────┐│
│   │              CoreDNS Service (10.96.0.10)                ││
│   │                                                           ││
│   │  ┌─────────┐ ┌─────────┐                                 ││
│   │  │CoreDNS  │ │CoreDNS  │  (commonly 2 replicas)          ││
│   │  │  Pod    │ │  Pod    │                                 ││
│   │  └────┬────┘ └────┬────┘                                 ││
│   │       │           │                                       ││
│   │       └─────┬─────┘                                       ││
│   │             ▼                                             ││
│   │    Query: web-svc.default.svc.cluster.local              ││
│   │             │                                             ││
│   │             ▼                                             ││
│   │    Response: 10.96.45.123 (Service ClusterIP)            ││
│   └──────────────────────────────────────────────────────────┘│
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

CoreDNS is usually deployed as a Deployment in the `kube-system` namespace, fronted by a Service named `kube-dns` for compatibility with the older kube-dns add-on. That compatibility name matters during troubleshooting because the running Pods are CoreDNS, but the Service clients use is commonly still called `kube-dns`. The Service provides a stable ClusterIP, and kubelet writes that IP as the `nameserver` for Pods that use cluster DNS.

| Component | Location | Purpose |
|-----------|----------|---------|
| CoreDNS Deployment | `kube-system` namespace | Runs CoreDNS Pods that answer DNS queries |
| CoreDNS Service | `kube-system` namespace | Provides a stable ClusterIP for DNS queries, commonly named `kube-dns` |
| Corefile ConfigMap | `kube-system` namespace | Stores CoreDNS plugin configuration |
| Pod `/etc/resolv.conf` | Every Pod | Points resolver libraries toward CoreDNS and defines search behavior |

The important operational detail is that DNS lookups are ordinary UDP or TCP requests to the CoreDNS Service IP, but CoreDNS answers Kubernetes names by watching the Kubernetes API. If the CoreDNS Pods are down, the Service has no useful backends. If the Pods are up but cannot talk to the API server, Kubernetes names may fail while external forwarding can look normal. If kubelet writes an unexpected `resolv.conf`, a single Pod can fail DNS even while the cluster DNS system is healthy for everyone else.

```bash
# Inside any Pod
cat /etc/resolv.conf

# Typical output:
nameserver 10.96.0.10
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

| Field | Purpose |
|-------|---------|
| `nameserver` | IP address of the CoreDNS Service |
| `search` | Domains the resolver appends when a process uses a short or relative name |
| `ndots:5` | Treats names with fewer than five dots as relative first, so search domains are tried before the final absolute query |

The `ndots:5` setting surprises people because a name like `api.example.com` has dots, but not enough dots to be tried as absolute first by many resolvers. The resolver may first query `api.example.com.default.svc.cluster.local`, then `api.example.com.svc.cluster.local`, then `api.example.com.cluster.local`, and only afterward try `api.example.com` itself. That behavior improves short-name ergonomics inside the cluster, but it can add latency for external names if the application performs many fresh DNS lookups.

**Pause and predict:** if a Pod can resolve `kubernetes.default.svc.cluster.local` but cannot resolve `example.com`, which part of the DNS path is already proven healthy, and which part still needs investigation? Decide where you would collect evidence before opening the explanation.

<details>
<summary>Check your prediction</summary>

The Kubernetes plugin path is working for at least one in-cluster Service, so your next checks should move toward the `forward` plugin, upstream resolver availability, network policy or firewall rules from CoreDNS to upstream DNS, and any CoreDNS log entries for external queries.

</details>

The next section is a troubleshooting path that turns this prediction into a sequence of checks, starting with the Pod resolver configuration and then comparing the DNS Service with its backing Pods.

For CKA troubleshooting, start by respecting the layers. A failed HTTP request by name may be a DNS failure, a Service selector failure, an endpoint readiness failure, a NetworkPolicy denial, an application port mismatch, or a timeout after resolution. DNS debugging is powerful because it can quickly remove the first layer from suspicion, but it does not prove the whole service path is healthy.

```bash
# Check the DNS Service and the CoreDNS Pods that back it.
kubectl get svc kube-dns -n kube-system
kubectl get endpoints kube-dns -n kube-system
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
```

If the Service has no endpoints, do not waste time changing application YAML. The Pod resolver can point at the right ClusterIP all day, but a Service without endpoints has nowhere useful to send the DNS packet. If the endpoints exist and CoreDNS Pods are ready, the next meaningful question is whether CoreDNS understands the name you asked for and whether the client Pod is asking the name you think it is asking.

CoreDNS also sits in a trust boundary that is easy to overlook. Application teams rarely have permission to edit the `kube-system` namespace, but every application depends on the results produced there. That means DNS incidents often require coordination between workload owners, cluster operators, and sometimes network administrators who manage upstream resolvers. Good evidence shortens that coordination: show the exact name, the client namespace, the resolver file, the DNS response type, and whether a known cluster name resolves.

The API watch behind CoreDNS is another reason to separate object state from DNS state. A Service object can exist while its selector matches no Pods, and CoreDNS can still return the Service ClusterIP because ClusterIP DNS records are tied to the Service, not to endpoint readiness. A headless Service behaves differently because its DNS answers depend directly on endpoint addresses. When you know which Service type you are testing, the DNS answer becomes a clue instead of a confusing surprise.

Remember that the `kube-dns` Service IP is not special because it is always `10.96.0.10`; that address is only a common default in many clusters. The stable fact is that kubelet writes the cluster DNS Service IP into Pod resolver configuration according to its cluster DNS settings and the Pod's DNS policy. In real environments, always read the Service and the Pod resolver file before assuming a numeric address from a tutorial or another cluster.

---

## Service Names, Search Domains, and Records

Kubernetes Service DNS names follow a predictable hierarchy: Service name, namespace, the fixed `svc` label, and the cluster domain. The default cluster domain is `cluster.local`, but clusters can be configured differently, so diagnostic habits should focus on reading the actual Pod search list and not memorizing one domain as universal. In most training clusters, `web-svc.production.svc.cluster.local` means the Service named `web-svc` in namespace `production`.

```text
┌────────────────────────────────────────────────────────────────┐
│                   Service DNS Naming                            │
│                                                                 │
│   Full format (FQDN):                                          │
│   <service>.<namespace>.svc.<cluster-domain>                   │
│                                                                 │
│   Example: web-svc.production.svc.cluster.local                │
│            ───────  ──────────  ───  ─────────────             │
│               │        │         │        │                    │
│           service  namespace   fixed   cluster domain          │
│                                 suffix  (default)              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The shortest name that works depends on the client Pod's namespace and search domains. From a Pod in `default`, `web-svc` expands first to `web-svc.default.svc.cluster.local`, so it reaches the `default` namespace if that Service exists. To reach a Service in another namespace, use `api.production` or the full name `api.production.svc.cluster.local`. Short names are convenient for same-namespace traffic, but explicit names are safer in shared libraries, Helm values, and cross-namespace integrations.

```bash
# From a Pod in the "default" namespace, reaching "web-svc" in "default":
curl web-svc
curl web-svc.default
curl web-svc.default.svc
curl web-svc.default.svc.cluster.local

# From a Pod in "default", reaching "api" in "production":
curl api
curl api.production
curl api.production.svc.cluster.local
```

The first cross-namespace command above is deliberately suspicious: `curl api` does not mean "find the API wherever it lives." It means "try this relative name through my search list," so `api.default.svc.cluster.local` is tried before anything else. If a local `api` Service exists, the request reaches that local Service. If none exists, the resolver keeps trying search suffixes and eventually may ask an external resolver for `api`, which is still not the same as `api.production`.

```text
┌────────────────────────────────────────────────────────────────┐
│                   Search Domain Resolution                      │
│                                                                 │
│   Pod in namespace "default" resolves "web-svc":               │
│                                                                 │
│   search default.svc.cluster.local svc.cluster.local ...       │
│                                                                 │
│   Step 1: Try web-svc.default.svc.cluster.local                │
│           └── Found! Returns IP                                │
│                                                                 │
│   If not found:                                                │
│   Step 2: Try web-svc.svc.cluster.local                        │
│   Step 3: Try web-svc.cluster.local                            │
│   Step 4: Try web-svc (external DNS)                           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

**Pause and predict:** a Pod in namespace `staging` runs `curl api-service`, and the cluster has an `api-service` in both `staging` and `production`. Which one does the Pod reach, and why? Decide before opening the explanation.

<details>
<summary>Check your prediction</summary>

The Pod reaches `api-service.staging.svc.cluster.local` because its namespace-specific search domain is tried first. That is useful isolation when teams own their own namespaces, but it becomes a risk when application configuration relies on ambiguous Service names.

</details>

The next section is a closer look at records for individual Pods and stable identities, which helps explain when a short Service name is useful and when a more explicit name matters.

Pod DNS records also exist, although Services should remain the normal stable target for most applications. A Pod IP such as `10.244.1.5` can be represented as `10-244-1-5.default.pod.cluster.local`, and StatefulSet Pods gain predictable DNS identities when paired with a headless Service. These forms are useful for systems that need stable peer identities, but they also couple clients more tightly to individual Pods than a ClusterIP Service does.

```text
┌────────────────────────────────────────────────────────────────┐
│                   Pod DNS Names                                 │
│                                                                 │
│   Pod IP: 10.244.1.5                                           │
│   DNS: 10-244-1-5.default.pod.cluster.local                    │
│        ──────────  ───────  ───  ─────────────                 │
│          IP with   namespace pod  cluster domain               │
│          dashes                                                 │
│                                                                 │
│   For StatefulSet Pods with headless Service:                  │
│   DNS: web-0.web-svc.default.svc.cluster.local                 │
│        ─────  ───────  ───────  ───                            │
│        pod    headless  namespace                              │
│        name   service                                          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Headless Services deserve special attention because they intentionally remove the single ClusterIP abstraction. When `clusterIP: None` is set, DNS can return the backing Pod IPs instead of a virtual Service IP, which is useful for peer discovery and StatefulSet workloads. The tradeoff is that clients now see more of the workload topology, so they must handle multiple returned addresses, endpoint churn, and connection behavior that a normal ClusterIP Service would usually hide.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  clusterIP: None
  selector:
    app: web
  ports:
  - name: http
    port: 80
    targetPort: 8080
```

SRV records add port information to the DNS answer, which is useful when clients discover both a name and a named port. Kubernetes creates SRV records for named Service ports using the shape `_<port-name>._<protocol>.<service>.<namespace>.svc.<cluster-domain>`. The named port matters because an unnamed port gives DNS no stable symbolic port label to publish in an SRV record.

```bash
# Query an SRV record for a named Service port.
# From a netshoot (or other dig-equipped) pod:
dig SRV _http._tcp.web-svc.default.svc.cluster.local

# Typical answer shape:
# _http._tcp.web-svc.default.svc.cluster.local. 30 IN SRV 0 100 80 web-svc.default.svc.cluster.local.
```

| Name Form | Example | Best Use | Operational Risk |
|-----------|---------|----------|------------------|
| Short Service name | `web-svc` | Same-namespace calls where names are unambiguous | Can resolve to the wrong namespace-local Service |
| Service plus namespace | `web-svc.default` | Cross-namespace calls in application config | Depends on the `svc.cluster.local` search suffix |
| Full Service FQDN | `web-svc.default.svc.cluster.local` | Debugging, shared config, and explicit dependencies | More verbose and cluster-domain specific |
| Headless Service name | `web-svc.default.svc.cluster.local` | Stateful peer discovery and direct endpoint answers | Clients must tolerate multiple changing IPs |
| SRV record | `_http._tcp.web-svc.default.svc.cluster.local` | Discovering a named port and target together | Only works when Service ports are named |

Before running this, what output do you expect from a headless Service with three ready Pods: one IP, multiple IPs, or no IP? The correct expectation is multiple endpoint IPs when the selector matches ready Pods and the DNS query asks for the Service name. If you see no answer, check the Service selector and endpoints before blaming CoreDNS.

Search domains are convenience features, but they are also a form of hidden context. The same application container image can resolve the same bare name differently when it runs in two namespaces, even if the command inside the container is identical. That is why production configuration should make ownership boundaries explicit. A library default of `db` may look harmless in a development namespace, then become dangerous in a cluster where each team owns a local `db` Service.

Fully qualified names are not always necessary, but they are excellent diagnostic tools. When a short name fails, ask for the full Service FQDN and compare the result. If the full name works and the short name fails, the Service probably exists and CoreDNS probably knows it, so the bug is in search behavior or client configuration. If both forms fail, move toward Service existence, namespace spelling, CoreDNS health, or client resolver settings.

The cluster domain is another place where assumptions can leak into manifests. Many examples use `cluster.local`, and most training clusters do too, but Kubernetes allows a different cluster domain. Application configuration that hardcodes a full `cluster.local` name is explicit, but it is also less portable than `service.namespace` when the search list is trustworthy. During exams and incident response, use the full FQDN to remove ambiguity; during product design, decide whether portability or explicitness matters more.

---

## CoreDNS Configuration and Customization

CoreDNS is configured through a ConfigMap named `coredns` in `kube-system`. The Corefile inside that ConfigMap defines a chain of plugins, and each plugin either handles, modifies, observes, caches, or forwards a query. This plugin model is why CoreDNS replaced the older kube-dns add-on in Kubernetes-era operations: it is compact, extensible, and easy to reason about when you read the Corefile from top to bottom.

```bash
# Check CoreDNS pods.
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check the CoreDNS Deployment.
kubectl get deployment coredns -n kube-system

# Check the DNS Service. The Service is commonly named "kube-dns" for compatibility.
kubectl get svc kube-dns -n kube-system

# View CoreDNS configuration.
kubectl get configmap coredns -n kube-system -o yaml
```

The default Corefile varies by distribution, but a Kubernetes cluster usually includes the same conceptual pieces: health endpoints for probes, readiness checks, the `kubernetes` plugin for Service and Pod records, Prometheus metrics, upstream forwarding, caching, loop detection, automatic reload, and load balancing. A syntax error or poorly placed plugin can affect every Pod in the cluster, so treat CoreDNS changes like infrastructure changes, not like editing one application's ConfigMap.

```yaml
# CoreDNS ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
            lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf {
            max_concurrent 1000
        }
        cache 30
        loop
        reload
        loadbalance
    }
```

| Plugin | Purpose | Troubleshooting Clue |
|--------|---------|----------------------|
| `kubernetes` | Resolves Kubernetes Service and Pod names | Cluster names fail when API access, cluster domain, or plugin settings are wrong |
| `forward` | Sends unresolved queries to upstream DNS | External names fail when upstream resolvers or egress paths are broken |
| `cache` | Caches responses to reduce load | Stale-looking answers may follow short TTL windows |
| `errors` | Logs DNS errors | CoreDNS logs become more useful during failures |
| `health` | Provides health check endpoint | Liveness behavior depends on this endpoint being reachable |
| `ready` | Provides readiness endpoint | Pods should not receive traffic until plugins are ready |
| `prometheus` | Exposes metrics | Query rates, errors, and latency can be scraped for observability |
| `loop` | Detects forwarding loops | Repeated self-forwarding can crash or disable CoreDNS |
| `reload` | Reloads changed Corefile content | ConfigMap changes can apply without manual Pod replacement in many setups |
| `loadbalance` | Randomizes DNS answer order | Clients avoid always choosing the first returned address |

The `kubernetes` plugin is the piece that makes a Service object appear as a DNS answer. It watches Kubernetes resources and responds for the configured zones, commonly `cluster.local`, `in-addr.arpa`, and `ip6.arpa`. The `fallthrough` line inside that plugin tells CoreDNS to pass reverse lookup misses to later plugins instead of stopping immediately, which is different from a successful Service lookup where the plugin answers directly.

Custom entries are sometimes needed for legacy systems, split-horizon names, or lab environments. The safest pattern is to add a narrow `hosts` entry or a specific forwarding rule while preserving normal Kubernetes resolution. The dangerous pattern is to insert a plugin that returns `NXDOMAIN` for every name it does not know, because then the rest of the plugin chain never gets a chance to answer cluster Service names.

```yaml
# Add custom DNS entries.
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
            lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        hosts {
            10.0.0.1 custom.example.com
            fallthrough
        }
        forward example.com 10.0.0.53
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

The `fallthrough` inside the `hosts` block is not decorative. Without it, a query that does not match `custom.example.com` can stop at the `hosts` plugin and return a negative answer instead of continuing to the Kubernetes plugin or the general forwarder. That one missing line can turn a small custom mapping into a cluster-wide Service discovery outage, which is why CoreDNS edits should be reviewed and rolled out with a quick rollback command ready.

```bash
# After editing, restart CoreDNS if your environment does not rely solely on reload.
kubectl rollout restart deployment coredns -n kube-system

# Watch replacement Pods become ready before declaring the change complete.
kubectl rollout status deployment coredns -n kube-system
```

Exercise scenario: you need `legacy-api.internal` to resolve to `10.0.5.100` for every Pod while ordinary Service names continue working. A `hosts` block can solve that requirement, but the cluster-wide blast radius means you should save the previous ConfigMap, change only the minimum Corefile lines, verify `kubernetes.default.svc.cluster.local`, verify the new legacy name, and check CoreDNS logs. If either verification fails, roll back the ConfigMap before troubleshooting application teams one by one.

```bash
# Capture the current Corefile before editing.
kubectl get configmap coredns -n kube-system -o yaml > coredns-before.yaml

# Open the live ConfigMap in your editor.
kubectl edit configmap coredns -n kube-system
```

Do not use CoreDNS customizations to hide poor Service naming. If a team keeps confusing `db` in multiple namespaces, adding a global DNS alias may make the next outage harder to diagnose because the name no longer reflects ownership or namespace. Prefer explicit application configuration, stable naming conventions, and namespace-qualified Service references before you reach for cluster-wide DNS rewrites.

Treat the Corefile like executable infrastructure code. A small indentation mistake may not matter to YAML if the block scalar still parses, but a malformed Corefile can prevent CoreDNS from serving correctly after reload. Before editing, capture the current ConfigMap, make one conceptual change, and verify both a known cluster name and the custom behavior you intended. If your environment has change control, include the exact rollback command in the change record.

Caching is another reason DNS changes can appear inconsistent for a short time. CoreDNS may cache responses according to its `cache` plugin settings, and client libraries or language runtimes can maintain their own caches as well. If you change a Service, CoreDNS, or upstream record and one process still sees the old answer briefly, check TTLs and client behavior before assuming the cluster ignored your change. For critical migrations, design a transition period rather than relying on instant DNS convergence.

Forwarding rules deserve the same narrowness as firewall rules. A broad `forward .` sends everything not handled earlier to upstream resolvers, while a domain-specific forward such as `forward example.com 10.0.0.53` affects only a chosen suffix. When a private corporate zone must resolve inside Pods, a narrow stub-style rule is usually easier to reason about than replacing every upstream resolver. It also makes failure isolation clearer when only one external suffix fails.

Observability turns CoreDNS from a black box into a debuggable service. Logs help during acute failures, but metrics are better for spotting rising query volume, error rates, and latency before users complain. Because every Pod depends on DNS, CoreDNS saturation can look like a random application slowdown across many namespaces. In production, alerting on CoreDNS availability and error patterns is a practical part of service discovery reliability, not an optional extra.

---

## Debugging DNS Failures

DNS debugging should start from a real client Pod or from a temporary Pod in the same namespace. Testing on your laptop proves almost nothing about cluster search domains, DNS policies, NetworkPolicy, or the CoreDNS Service IP injected by kubelet. A temporary BusyBox or netshoot Pod gives you the same resolver behavior an application gets, and that makes your evidence much more useful during an incident or an exam task.

```text
DNS Issue?
    │
    ├── Step 1: Test from inside a Pod
    │   kubectl run test --rm -it --image=busybox:1.36 --restart=Never -- nslookup <service>
    │       │
    │       ├── Works? -> DNS is fine, issue is elsewhere
    │       │
    │       └── Fails? -> Continue debugging
    │
    ├── Step 2: Check CoreDNS is running
    │   kubectl get pods -n kube-system -l k8s-app=kube-dns
    │       │
    │       └── Not running? -> Fix CoreDNS Deployment
    │
    ├── Step 3: Check CoreDNS logs
    │   kubectl logs -n kube-system -l k8s-app=kube-dns
    │       │
    │       └── Errors? -> Check Corefile config
    │
    ├── Step 4: Check Pod resolv.conf
    │   kubectl exec <pod-name> -- cat /etc/resolv.conf
    │       │
    │       └── Wrong nameserver? -> Check kubelet and Pod DNS policy
    │
    └── Step 5: Test external DNS
        kubectl run test --rm -it --image=busybox:1.36 --restart=Never -- nslookup example.com
            │
            └── Fails? -> Check forward config and upstream reachability
```

The workflow separates symptoms that sound similar. `NXDOMAIN` usually means the DNS server answered that the name does not exist, which points toward spelling, namespace, Service existence, or search behavior. A timeout usually means the query did not get an answer, which points toward CoreDNS reachability, NetworkPolicy, CNI problems, or upstream DNS failure. `SERVFAIL` tells you a DNS server responded but could not complete the lookup, which often sends you to CoreDNS logs or upstream resolver health.

```bash
# Test DNS from inside the cluster.
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup kubernetes

# Test a specific Service FQDN.
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup web-svc.default.svc.cluster.local

# Test with the DNS Service IP explicitly.
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup web-svc "$(kubectl get svc kube-dns -n kube-system -o jsonpath='{.spec.clusterIP}')"
```

Those three tests answer different questions. The first asks whether the default resolver path in the temporary Pod can resolve a known cluster Service. The second removes namespace ambiguity by using the full Service name. The third bypasses the Pod's `nameserver` setting and sends the query to the current DNS Service IP, which helps identify whether `/etc/resolv.conf` is wrong or CoreDNS itself is not answering correctly.

```bash
# Check resolver configuration in an existing Pod.
kubectl exec my-app-pod -- cat /etc/resolv.conf

# Check CoreDNS logs.
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50

# Verify CoreDNS is responding for the Kubernetes Service.
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup kubernetes.default.svc.cluster.local
```

Use a richer debug image when you need `dig`, `host`, packet tools, or repeated interactive tests. BusyBox is fast and enough for many exam tasks, but netshoot gives you more DNS detail and general networking tools. The tradeoff is image availability: in restricted environments, a small image that is already cached may be more reliable than a tool-heavy image that must be pulled during a failure.

```bash
# Create a debug Pod with more networking tools.
kubectl run dns-debug --image=nicolaka/netshoot --restart=Never -- sleep 3600

# Wait for the Pod to be ready.
kubectl wait --for=condition=ready pod/dns-debug --timeout=60s

# Use it for DNS debugging.
kubectl exec -it dns-debug -- dig web-svc.default.svc.cluster.local
kubectl exec -it dns-debug -- host web-svc
kubectl exec -it dns-debug -- nslookup web-svc

# Cleanup.
kubectl delete pod dns-debug
```

When DNS succeeds, keep going until you prove the next layer. A successful `nslookup web-svc.default.svc.cluster.local` only proves name resolution. It does not prove that the Service selects ready endpoints, that the target port is correct, that NetworkPolicy allows traffic, or that the application is listening. Follow DNS with `kubectl get endpointslices`, `kubectl describe service`, and an actual connection test when the reported symptom is an application timeout.

| Symptom | Likely Cause | How to Confirm | Better Next Step |
|---------|--------------|----------------|------------------|
| `NXDOMAIN` | Service name, namespace, or search path mismatch | Query the full FQDN and list Services in the namespace | Correct the name or use namespace-qualified config |
| Timeout | DNS packet is not answered | Query the CoreDNS Service IP directly and check network policy | Inspect CoreDNS reachability, CNI, and policy rules |
| `SERVFAIL` | CoreDNS or upstream resolver cannot complete the query | Check CoreDNS logs and query a known cluster name | Separate Kubernetes plugin failures from forwarding failures |
| Wrong IP returned | Unexpected Service, stale client cache, or headless endpoint behavior | Compare DNS answer to Service ClusterIP and EndpointSlices | Fix selectors or wait for TTL/client cache expiration |
| External domains fail | Forwarding path or upstream DNS is broken | Resolve cluster Service names and then test external names | Check Corefile `forward`, node DNS, and egress rules |

Stop and think: a Pod reports `connection timed out` when calling another Service by name. Is this necessarily a DNS problem? No. First resolve the name from the same namespace, then connect to the resolved target or Service name with the expected port, then inspect Service endpoints. DNS is only one layer, and changing CoreDNS before proving a name lookup failure can create a wider incident than the one you started with.

The exam-friendly habit is to write down the smallest fact each command proves. `kubectl get pods -n kube-system -l k8s-app=kube-dns` proves Pods exist, not that they answer correctly. `kubectl logs` proves whether CoreDNS saw or reported errors, not that every client can reach it. `cat /etc/resolv.conf` proves the client's configured resolver path, not that the resolver is healthy. That discipline prevents random command hopping under time pressure.

Namespace placement matters even for temporary debug Pods. If the affected application runs in `staging`, a debug Pod in `default` has a different first search domain and may miss the exact ambiguity causing the failure. Create the diagnostic Pod in the same namespace unless you are deliberately comparing namespaces. That one habit catches many mistakes where `api` means one Service to the application and another Service to the engineer running ad hoc commands.

Do not ignore negative evidence from successful lookups. If a full FQDN resolves and the returned IP matches the Service ClusterIP, DNS has done its job for that name at that moment. Continuing to restart CoreDNS after that point wastes time and can disrupt other workloads. Move to Service selectors, EndpointSlices, target ports, readiness, and policies. DNS troubleshooting is most valuable when it tells you when to stop troubleshooting DNS.

Client behavior can complicate clean laboratory reasoning. Some applications cache DNS answers longer than the DNS TTL, some retry with their own resolver libraries, and some connection pools keep using old addresses until connections are recycled. When command-line tools show a corrected answer but the application still fails, compare the application runtime's DNS behavior, connection reuse, and rollout timing. The cluster DNS layer may already be fixed while the workload process still needs a restart or configuration reload.

CoreDNS logs should be interpreted with query volume in mind. A quiet log is not proof that clients are not querying; the Corefile may not log successful requests. A noisy log during a failure can be useful, but repeated messages from one namespace may hide a broader pattern. Pair logs with targeted queries from a debug Pod and object inspection from the Kubernetes API so you are not reading isolated log lines as the whole story.

```bash
# Inspect Service and EndpointSlice state after DNS succeeds.
kubectl get svc web-svc -n default
kubectl get endpointslices -n default -l kubernetes.io/service-name=web-svc
kubectl describe svc web-svc -n default
```

---

## DNS Policies, Pod Records, and SRV Lookups

Pod DNS policy decides what kubelet writes into the Pod resolver file. Most Pods use `ClusterFirst`, which means cluster DNS is preferred and external names can still be forwarded by CoreDNS. `Default` means the Pod inherits the node's resolver settings, which is useful for rare host-like workloads but usually wrong for applications that need Service names. `None` means you supply the DNS configuration yourself through `dnsConfig`.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: dns-policy-demo
spec:
  dnsPolicy: ClusterFirst
  containers:
  - name: app
    image: nginx
```

| Policy | Behavior | Use Carefully When |
|--------|----------|--------------------|
| `ClusterFirst` | Uses cluster DNS for cluster names and forwards external names through CoreDNS | Default for ordinary Pods |
| `Default` | Uses the node's DNS settings | A Pod intentionally should behave like the node resolver |
| `ClusterFirstWithHostNet` | Uses cluster DNS even when `hostNetwork: true` | Host-networked Pods still need Service discovery |
| `None` | Uses only the DNS settings you provide in `dnsConfig` | You need custom nameservers, searches, or resolver options |

Host-networked Pods are a common DNS trap because they share the node network namespace. If you combine `hostNetwork: true` with the wrong DNS policy, external names may work through the node resolver while Kubernetes Service names fail. That asymmetry is a clue: the Pod can resolve public names, but it is not asking CoreDNS for `*.svc.cluster.local` names.

```yaml
# Pod using host network while still using cluster DNS.
apiVersion: v1
kind: Pod
metadata:
  name: host-network-pod
spec:
  hostNetwork: true
  dnsPolicy: ClusterFirstWithHostNet
  containers:
  - name: app
    image: nginx
```

Custom DNS settings are valid, but they should be narrow and intentional. Setting `dnsPolicy: None` with public nameservers such as `1.1.1.1` or `8.8.8.8` can make external DNS work while breaking Service discovery because those public resolvers do not know your Kubernetes cluster domain. If you need custom options such as a lower `ndots` value, consider whether you can preserve the cluster nameserver instead of replacing the whole resolver path.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: custom-dns
spec:
  dnsPolicy: "None"
  dnsConfig:
    nameservers:
    - 1.1.1.1
    - 8.8.8.8
    searches:
    - custom.local
    - svc.cluster.local
    options:
    - name: ndots
      value: "2"
  containers:
  - name: app
    image: nginx
```

What would happen if you set `dnsPolicy: Default` on a Pod and then tried to resolve `my-service.default.svc.cluster.local`? It depends on the node's resolver, but the safe expectation is failure unless the node resolver has been configured to forward cluster domains into CoreDNS. Ordinary nodes usually do not know Kubernetes Service records, so `Default` moves the Pod away from the cluster DNS path that makes Service discovery work.

Named ports and SRV records connect DNS to port discovery. A Service with `name: http` on a TCP port can produce an SRV answer under `_http._tcp.<service>.<namespace>.svc.cluster.local`. Many HTTP applications still use normal A or AAAA lookups plus configured ports, but SRV records are useful in systems that discover peers and ports dynamically. For the CKA, know how to recognize the record shape and why the named port is required.

```yaml
# Service with a named port.
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  selector:
    app: web
  ports:
  - name: http
    port: 80
    targetPort: 8080
```

```bash
# SRV record format:
# _<port-name>._<protocol>.<service>.<namespace>.svc.cluster.local
# From a netshoot (or other dig-equipped) pod:
dig SRV _http._tcp.web-svc.default.svc.cluster.local
```

There is a design tradeoff hiding behind every DNS policy change. Lowering `ndots` can reduce wasted search-domain attempts for external names, but it can also change lookup order for relative names that applications already rely on. Replacing nameservers can satisfy a special compliance or network requirement, but it can remove CoreDNS from the path. Using host networking can be necessary for node-level agents, but it forces you to choose `ClusterFirstWithHostNet` when the agent also needs Service discovery.

The safest default is to leave ordinary workloads on `ClusterFirst`. Most application Pods need Service discovery more than they need direct access to the node's resolver behavior, and CoreDNS can still forward external names. Reach for `Default` only when the workload intentionally behaves like software on the node, and document that cluster Service names may not resolve. Reach for `None` only when you can state every nameserver, search suffix, and option you are taking responsibility for.

DNS policy also interacts with security controls. A NetworkPolicy may allow application traffic but accidentally block UDP and TCP port 53 from Pods to CoreDNS, or it may block CoreDNS egress to upstream resolvers. The symptom changes depending on which leg is blocked: cluster names may time out from selected namespaces, or external names may fail while Service names work. When policies are in play, include DNS traffic in the allowed paths deliberately instead of assuming it is always exempt.

For StatefulSets, DNS identity is part of the workload contract. A database member or queue broker may need to know peer names such as `web-0` and `web-1`, and a headless Service gives those identities a stable DNS form. That does not mean every StatefulSet client should bypass Services completely. Use stable Pod names for peer protocols that require them, and use normal Services when clients simply need to reach any healthy instance.

SRV records are powerful precisely because they include more than an address, but many applications do not query them by default. If a system expects SRV discovery, ensure the Service port has a stable name and the client is actually asking the SRV record shape. If a system expects a normal A record, adding a named port will not magically teach the client to discover ports. DNS can publish information only in formats the client knows how to read.

---

## Patterns & Anti-Patterns

Use DNS names as part of an explicit service contract. A same-namespace application can use short names when the namespace is the ownership boundary, but shared platform components and cross-namespace clients should prefer namespace-qualified names. This pattern works because it makes the dependency visible in configuration, reduces accidental shadowing by same-name Services, and gives reviewers a clear place to evaluate whether namespace coupling is intentional.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Namespace-qualified Service names | Shared dependencies and cross-team calls | Avoids accidental same-namespace resolution | Document the owning namespace and lifecycle |
| Full FQDNs in diagnostics | Incident response and CKA tasks | Removes search-domain ambiguity | Adjust if the cluster domain is not `cluster.local` |
| Headless Service for stable peers | StatefulSets and peer discovery | Returns endpoint identities instead of one virtual IP | Clients must handle multiple addresses and churn |
| CoreDNS change with rollback | Cluster-wide DNS customization | Limits blast radius and improves recovery | Keep the previous ConfigMap and verify core names immediately |

Another strong pattern is to debug DNS from the namespace where the workload runs. Search domains are namespace-sensitive, so a lookup from `default` can prove the wrong thing for an application in `payments`, `staging`, or `team-a`. Create the temporary Pod in the target namespace, resolve the same name the application uses, and then resolve the full FQDN to compare ambiguity against explicit intent.

```bash
kubectl run dns-test -n staging --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup api-service

kubectl run dns-test -n staging --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup api-service.production.svc.cluster.local
```

Avoid treating CoreDNS as the first place to patch every connectivity problem. Teams fall into this anti-pattern because the error message mentions a host name, and DNS is easier to change centrally than application configuration. The better alternative is to classify the failure by response: `NXDOMAIN`, timeout, `SERVFAIL`, wrong IP, or post-resolution connection failure. That classification tells you whether to inspect names, CoreDNS, network reachability, upstream forwarding, Service selectors, or application ports.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Using `Default` DNS policy for ordinary Pods | Service names stop resolving because the node resolver is used | Keep `ClusterFirst` unless the Pod truly needs node DNS behavior |
| Relying on short names across namespaces | Clients can reach a same-name local Service unexpectedly | Use `service.namespace` or the full FQDN |
| Editing CoreDNS without rollback | One typo can break cluster-wide discovery | Export the ConfigMap first and verify immediately after change |
| Removing `fallthrough` from custom plugins | Unmatched names stop before Kubernetes or forwarding plugins answer | Preserve fallthrough where later plugins must handle misses |
| Debugging from the wrong namespace | Search-domain results do not match the affected workload | Run temporary debug Pods in the workload namespace |
| Assuming DNS success proves app connectivity | The request can still fail on Service selectors, ports, policy, or app health | Follow resolution with endpoint and connection checks |

The most reliable operating model is conservative: use Kubernetes-native Service names for normal discovery, keep custom CoreDNS rules small, monitor CoreDNS health and errors, and reserve DNS policy overrides for workloads that genuinely need them. That does not make DNS boring. It makes DNS predictable, which is exactly what you want from the system every microservice depends on before it can call anything else.

---

## Decision Framework

Choose the narrowest DNS change that solves the actual problem you proved. If the problem is an ambiguous name, change application configuration to a namespace-qualified name. If the problem is a missing Service record, fix the Service or namespace. If the problem is external forwarding, inspect the Corefile `forward` plugin and upstream reachability. If the problem is one Pod's resolver file, inspect `dnsPolicy`, `dnsConfig`, and whether host networking changed the expected behavior.

```text
Start with the failing name
    │
    ├── Does the full Service FQDN resolve from the affected namespace?
    │       │
    │       ├── Yes -> Short-name/search behavior or app config is suspect
    │       └── No  -> Check Service existence, namespace, endpoints, and CoreDNS
    │
    ├── Does kubernetes.default.svc.cluster.local resolve?
    │       │
    │       ├── Yes -> CoreDNS Kubernetes path works for at least one known Service
    │       └── No  -> Check CoreDNS Pods, Service endpoints, logs, and client resolv.conf
    │
    ├── Do external names fail while cluster names work?
    │       │
    │       ├── Yes -> Check CoreDNS forward plugin and upstream DNS egress
    │       └── No  -> Continue testing the application path after DNS
    │
    └── Is only one Pod affected?
            │
            ├── Yes -> Inspect dnsPolicy, dnsConfig, hostNetwork, and resolv.conf
            └── No  -> Treat CoreDNS, Service naming, or network policy as shared suspects
```

| Situation | Prefer This | Avoid This | Reason |
|-----------|-------------|------------|--------|
| Same-namespace app-to-app call | Short Service name | Full domain everywhere by habit | Short names are readable when namespace ownership is clear |
| Cross-namespace dependency | `service.namespace` or full FQDN | Bare Service name | Search domains try the caller's namespace first |
| Host-networked agent needs Services | `ClusterFirstWithHostNet` | `Default` by accident | Host networking changes resolver inheritance |
| External name latency from many search attempts | Review `ndots` and trailing-dot behavior | Replacing CoreDNS wholesale | The issue may be lookup order, not DNS failure |
| Legacy internal name for all Pods | Small CoreDNS `hosts` or `forward` rule with rollback | Per-Pod hardcoded hacks | Cluster-wide rule is maintainable when narrowly scoped |
| Stateful peer identity | Headless Service plus StatefulSet naming | Random Pod IP references | Stable DNS identity matches workload semantics |

This framework is intentionally practical for Kubernetes 1.35 and the CKA style of troubleshooting. You are usually not asked to design a global enterprise DNS architecture during an exam; you are asked to prove why a Service name does or does not resolve and fix the smallest broken part. The same approach scales to production because it avoids broad changes until the evidence points at a shared DNS component.

When you are under time pressure, prefer questions that divide the problem space cleanly. "Can this Pod resolve `kubernetes.default.svc.cluster.local`?" separates the basic cluster DNS path from the application-specific name. "Can it resolve the full FQDN?" separates Service existence from search-domain behavior. "Does the Service have EndpointSlices?" separates DNS from traffic delivery. These questions are faster than memorizing long command sequences because each answer changes your next move.

For design reviews, write DNS decisions in the same language you use for ownership and failure domains. A short name says the dependency is local to the namespace. A namespace-qualified name says another namespace owns the dependency. A headless Service says clients are allowed to see individual endpoints. A CoreDNS customization says the platform owns a cluster-wide naming rule. Making those meanings explicit prevents DNS from becoming an accidental architecture diagram that nobody agreed to maintain.

---

## Did You Know?

- **CoreDNS became the default DNS add-on in the Kubernetes 1.11 timeframe**: kube-dns was the original cluster DNS add-on, while CoreDNS brought a smaller plugin-based architecture that is easier to extend and inspect through a Corefile.
- **The DNS Service is often still named `kube-dns` even when the Pods run CoreDNS**: that compatibility name keeps older assumptions working, so troubleshooting commands should check the Service name and the backing CoreDNS Pods together.
- **Kubernetes Pods commonly get `ndots:5` in `/etc/resolv.conf`**: names with fewer than five dots may be tried through cluster search domains before the final absolute query, which can affect external DNS latency.
- **SRV records require named Service ports**: a Service port named `http` can produce `_http._tcp.service.namespace.svc.cluster.local`, but an unnamed port gives DNS no stable port label to publish.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Using a bare Service name for a cross-namespace dependency | Search domains try the caller's namespace first, so a same-name local Service can shadow the intended target | Use `service.namespace` or the full FQDN in cross-namespace configuration |
| Assuming CoreDNS is healthy because Pods are running | A ready-looking Pod can still have Corefile errors, API watch issues, or no useful Service endpoints | Test a known cluster name, inspect `kube-dns` endpoints, and read CoreDNS logs |
| Setting `dnsPolicy: Default` on ordinary application Pods | The Pod inherits node resolver behavior and may stop resolving `*.svc.cluster.local` names | Keep `ClusterFirst` unless you intentionally need node DNS settings |
| Forgetting `ClusterFirstWithHostNet` for host-networked Pods | Host networking changes resolver inheritance, so external names may work while Service names fail | Set `dnsPolicy: ClusterFirstWithHostNet` when host-networked Pods still need cluster DNS |
| Editing the CoreDNS ConfigMap without preserving `fallthrough` | A custom plugin can return `NXDOMAIN` before later plugins handle normal cluster names | Keep `fallthrough` where unresolved names must continue through the plugin chain |
| Treating a timeout as proof of DNS failure | Timeouts can happen after DNS resolution due to selectors, ports, NetworkPolicy, or application health | Resolve the name first, then check EndpointSlices, Service ports, and actual connectivity |
| Replacing cluster nameservers in `dnsConfig` casually | Public or node resolvers do not know Kubernetes Service records | Preserve the CoreDNS path or document why the Pod must opt out of cluster discovery |

---

## Quiz

<details>
<summary>Question 1: Your team reports that `curl api` from namespace `team-a` reaches the wrong application after another team created an `api` Service locally. What should you check and change?</summary>

Start by confirming the caller namespace and the search domains in the affected Pod's `/etc/resolv.conf`, because `api` is a relative name. The resolver will try `api.team-a.svc.cluster.local` before any other namespace-qualified form, so the local Service can shadow the intended dependency. Change the application configuration to `api.shared` or `api.shared.svc.cluster.local`, then verify the resolved address from a debug Pod in `team-a`. Do not patch CoreDNS for this first, because the DNS system is behaving according to normal search-domain rules.

</details>

<details>
<summary>Question 2: After a cluster upgrade, applications cannot resolve Service names, but `kubectl get pods -n kube-system -l k8s-app=kube-dns` shows running CoreDNS Pods. What is your next diagnostic path?</summary>

Running Pods are only one fact, so test whether CoreDNS answers a known name such as `kubernetes.default.svc.cluster.local` from inside the cluster. Then inspect the `kube-dns` Service endpoints, CoreDNS logs, and a failing Pod's `/etc/resolv.conf` to verify the client is using the expected nameserver. If CoreDNS logs show Corefile or API watch errors, focus on configuration and control-plane access. If the known name resolves, move toward the specific Service name, namespace, and EndpointSlice state instead of restarting DNS blindly.

</details>

<details>
<summary>Question 3: You added a CoreDNS `hosts` entry for `legacy-api.internal`, and suddenly normal Service names return `NXDOMAIN`. What likely went wrong?</summary>

The custom `hosts` block probably lacks `fallthrough`, or it was placed in a way that stops unmatched queries before the `kubernetes` plugin can answer. A `hosts` plugin can answer the one name you added while returning negative responses for names it does not know. Restore the previous ConfigMap or add `fallthrough`, restart or wait for reload, and immediately verify both `legacy-api.internal` and `kubernetes.default.svc.cluster.local`. The key lesson is that a narrow custom rule still sits in the shared cluster DNS path.

</details>

<details>
<summary>Question 4: A host-networked monitoring agent resolves `example.com` but cannot resolve `kubernetes.default.svc.cluster.local`. Which DNS policy should you evaluate?</summary>

Evaluate whether the Pod uses `hostNetwork: true` without `dnsPolicy: ClusterFirstWithHostNet`. External DNS can work through the node resolver while cluster Service names fail because the node resolver does not normally know Kubernetes DNS records. Set `ClusterFirstWithHostNet` when the agent needs host networking and cluster service discovery. After changing it, inspect the Pod's `/etc/resolv.conf` to prove the CoreDNS Service IP is present.

</details>

<details>
<summary>Question 5: A Pod resolves `web.default.svc.cluster.local` successfully, but HTTP requests to `web:8080` time out. Why should you avoid changing CoreDNS first?</summary>

Successful resolution proves DNS is not the first broken layer for that name. The timeout may be caused by a Service targetPort mismatch, empty or unready endpoints, NetworkPolicy, or an application that is not listening on the expected port. Check the Service, EndpointSlices, selected Pods, and a direct connection test before touching CoreDNS. Changing DNS after a successful lookup risks adding a cluster-wide problem without addressing the actual network or application failure.

</details>

<details>
<summary>Question 6: External lookups such as `api.example.com` are slow from Pods, while cluster Service lookups are fast. What resolver behavior should you investigate?</summary>

Investigate search-domain expansion and the `ndots` option in the Pod's `/etc/resolv.conf`. With a common `ndots:5` setting, a name like `api.example.com` can be tried through cluster search domains before the final absolute query succeeds. Depending on the application and resolver library, using a trailing dot for absolute names or adjusting `dnsConfig.options.ndots` may reduce wasted lookups. Keep the fix scoped, because lowering `ndots` globally can change behavior for relative cluster names.

</details>

<details>
<summary>Question 7: A StatefulSet needs each replica to discover stable peer identities instead of one shared ClusterIP. Which DNS pattern fits, and what must clients handle?</summary>

Use a headless Service with the StatefulSet so each Pod receives a predictable DNS identity such as `web-0.web-svc.default.svc.cluster.local`. This pattern fits peer discovery because DNS can expose individual endpoint identities instead of one virtual Service IP. Clients must handle multiple addresses, endpoint changes, and the possibility that a peer is not ready yet. For ordinary stateless traffic, a normal ClusterIP Service is usually simpler because it hides those details.

</details>

---

## Hands-On Exercise

Exercise scenario: you are the on-call engineer for a training cluster, and a developer says Service names are unreliable. Your task is to prove the normal DNS path, create Services that show same-namespace and cross-namespace behavior, inspect CoreDNS, and then clean up without leaving test resources behind. Run the commands from a shell where `kubectl` already points at a disposable Kubernetes 1.35 or newer cluster.

> **Note:** Kubernetes DNS search domains can expand `service.namespace` to `service.namespace.svc.cluster.local`, but BusyBox `nslookup` in `busybox:1.36` does not apply that two-label expansion and may print `NXDOMAIN` for names like `web.default`. BusyBox `nslookup` also exits non-zero even when it printed a useful `Name:` and `Address:` answer for the intended record, so judge its success by the displayed record rather than only the Pod exit code. For namespace-qualified verification, use `wget -qO- --timeout=2 http://<name>.<ns>/`, query the full FQDN with `nslookup`, or run a netshoot pod with `host` or `dig`.

### Task 1: Verify the Cluster DNS Baseline

Start by checking the shared DNS components before creating workload resources. This gives you a baseline for later failures and teaches you which objects are involved in the DNS path. If your environment uses different labels for CoreDNS, adapt the selector after inspecting Pods in `kube-system`.

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl get svc -n kube-system kube-dns
kubectl get endpoints kube-dns -n kube-system
kubectl get configmap coredns -n kube-system -o yaml
```

<details>
<summary>Solution notes</summary>

You should see at least one ready CoreDNS Pod, a `kube-dns` Service, and endpoints behind that Service. The ConfigMap should contain a Corefile with a `kubernetes` plugin for the cluster domain and a `forward` plugin for unresolved names. If the Service has no endpoints, fix CoreDNS availability before continuing because clients have no healthy DNS backend.

</details>

### Task 2: Create a Service and Resolve Its Names

Create a simple Deployment and expose it as a Service. Then query the short name, namespace-qualified name, and full FQDN from temporary Pods. The goal is not to test nginx content; the goal is to observe how different names resolve through the same Service record.

```bash
kubectl create deployment web --image=nginx
kubectl expose deployment web --port=80
kubectl get svc web
```

```bash
kubectl run test1 --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup web

kubectl run test2 --rm -it --image=busybox:1.36 --restart=Never -- \
  wget -qO- --timeout=2 http://web.default/

kubectl run test3 --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup web.default.svc.cluster.local
```

<details>
<summary>Solution notes</summary>

The short-name and full-FQDN `nslookup` commands should print the Service ClusterIP for a normal ClusterIP Service, and the `wget` command verifies that the namespace-qualified `web.default` form works through a resolver-backed client. The Kubernetes DNS spec expands `service.namespace`, but BusyBox `nslookup` reports `NXDOMAIN` for that two-label form, so verify it with a libc-style resolver such as `wget`, a full-FQDN `nslookup`, or a netshoot `host` or `dig` command before blaming CoreDNS. If only the full FQDN works, inspect the temporary Pod's resolver search list.

</details>

### Task 3: Inspect Pod Resolver Configuration

Use a temporary Pod to read the resolver settings that kubelet injects. This makes the search-domain behavior visible instead of treating it as a hidden resolver trick. Notice the nameserver, search list, and `ndots` option.

```bash
kubectl run test-resolv --rm -it --image=busybox:1.36 --restart=Never -- \
  cat /etc/resolv.conf
```

<details>
<summary>Solution notes</summary>

The nameserver should be the ClusterIP of the `kube-dns` Service, and the search list should include the current namespace's `svc` domain followed by broader cluster domains. If the nameserver is not the DNS Service IP, check whether a custom DNS policy or host networking is involved. This observation is often the fastest way to explain why one Pod behaves differently from another.

</details>

### Task 4: Test Cross-Namespace Resolution

Create a second namespace and a Service with a different name. Query it from the default namespace using the namespace-qualified form. This shows why cross-namespace dependencies should be explicit in configuration.

```bash
kubectl create namespace other
kubectl create deployment db -n other --image=nginx
kubectl expose deployment db -n other --port=80
kubectl get svc db -n other
```

```bash
kubectl run test4 --rm -it --image=busybox:1.36 --restart=Never -- \
  wget -qO- --timeout=2 http://db.other/
```

<details>
<summary>Solution notes</summary>

The namespace-qualified query should resolve because the Kubernetes DNS spec allows `db.other` to expand to `db.other.svc.cluster.local`, and the `wget` command verifies that behavior with an application-style lookup. BusyBox `nslookup db.other` will report `NXDOMAIN` for this two-label form, so use a libc-style resolver such as `wget`, the full FQDN, or a netshoot Pod when you need to prove namespace-qualified resolution. If `nslookup db` from `default` fails or reaches a different Service, that is expected search-domain behavior. The fix for real applications is explicit naming, not a CoreDNS patch.

</details>

### Task 5: Compare External DNS and CoreDNS Logs

Now test an external name and inspect CoreDNS logs. This separates Kubernetes plugin behavior from upstream forwarding behavior. Use a documentation-safe domain for examples instead of depending on a specific public service name.

```bash
kubectl run test5 --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup example.com

kubectl logs -n kube-system -l k8s-app=kube-dns --tail=20
```

<details>
<summary>Solution notes</summary>

If cluster Service names resolve but `example.com` fails, focus on the CoreDNS `forward` plugin and upstream DNS reachability. If both cluster names and external names fail, inspect CoreDNS health, endpoints, logs, and client resolver configuration first. Logs may be quiet in healthy clusters unless error logging is enabled or a failure occurs.

</details>

### Task 6: Practice Headless Service DNS

Create a small workload and a headless Service so DNS returns endpoint addresses rather than a single ClusterIP. This reinforces the difference between Service virtual IP discovery and direct endpoint discovery. Do not use this pattern for every application; it is most appropriate when clients understand peer identities.

```bash
kubectl create deployment headless-test --image=nginx --replicas=3
```

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: headless-svc
spec:
  clusterIP: None
  selector:
    app: headless-test
  ports:
  - port: 80
EOF
```

```bash
kubectl wait --for=condition=ready pod -l app=headless-test --timeout=60s

kubectl run test6 --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup headless-svc
```

<details>
<summary>Solution notes</summary>

The lookup should return endpoint IPs rather than one Service ClusterIP. If you receive no useful answer, check whether the Pods are ready and whether the Service selector matches their labels. Headless DNS depends on endpoints, so selector mistakes show up quickly.

</details>

### Task 7: Inspect a Custom DNS Policy

Create a Pod that opts out of the normal cluster DNS path. This is intentionally a contrast exercise: it shows why `dnsPolicy: None` can break Service discovery if you replace the nameserver with resolvers that do not know Kubernetes records.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: custom-dns-pod
spec:
  dnsPolicy: None
  dnsConfig:
    nameservers:
    - 8.8.8.8
    searches:
    - custom.local
    options:
    - name: ndots
      value: "2"
  containers:
  - name: app
    image: busybox:1.36
    command: ["sleep", "3600"]
EOF
```

```bash
kubectl wait --for=condition=ready pod/custom-dns-pod --timeout=60s
kubectl exec custom-dns-pod -- cat /etc/resolv.conf
kubectl exec custom-dns-pod -- nslookup kubernetes
```

<details>
<summary>Solution notes</summary>

The resolver file should show the custom nameserver and search domain. The lookup for `kubernetes` is expected to fail in many clusters because the public resolver does not know the cluster DNS zone. This is why custom DNS policy should be deliberate and documented.

</details>

### Task 8: Clean Up

Remove the resources created during the exercise. Cleanup matters because DNS tests create Services, namespaces, and Pods that can shadow future names if they are left behind. Run the commands even if one earlier task failed, and ignore not-found errors only after confirming the resource is already gone.

```bash
kubectl delete pod custom-dns-pod
kubectl delete deployment headless-test
kubectl delete svc headless-svc
kubectl delete deployment web
kubectl delete svc web
kubectl delete namespace other
```

**Card A: Resolving `kubernetes.default.svc.cluster.local` proves that `example.com` will resolve.** A learner sees one successful cluster lookup and assumes every external name must follow the same working DNS path.

<details>
<summary>Check your prediction</summary>

Failure layer: cluster name resolution versus external forwarding. Next action: test the external name separately, then inspect CoreDNS forwarding configuration, upstream resolver reachability, and relevant logs; a working Kubernetes Service lookup proves only that part of the path.

</details>

**Card B: From namespace `staging`, `curl api-service` reaches the `production` Service when both exist.** A learner expects the shared short name to select the production endpoint despite a same-named local Service.

<details>
<summary>Check your prediction</summary>

Failure layer: short-name expansion in the caller's namespace. Next action: inspect the Pod's `/etc/resolv.conf` and resolve the namespace-qualified names separately; the local `api-service.staging.svc.cluster.local` is selected first when both Services exist.

</details>

**Card C: Under `ndots:5`, `api.example.com` is queried as an absolute name first.** A learner sees dots in the name and assumes the resolver skips the configured suffixes.

<details>
<summary>Check your prediction</summary>

Failure layer: resolver search order versus the name's dot count. Next action: inspect `/etc/resolv.conf` and compare the expanded queries with a trailing-dot absolute lookup; with fewer than five dots, the resolver normally tries search suffixes first.

</details>

**Card D: `dnsPolicy: Default` still sends Service names to CoreDNS.** A learner changes the policy and assumes the Pod retains cluster DNS even when the node uses another resolver.

<details>
<summary>Check your prediction</summary>

Failure layer: Pod DNS policy versus resolver destination. Next action: read the Pod's `/etc/resolv.conf` and compare it with the node resolver settings; `Default` inherits the node configuration and does not guarantee queries reach CoreDNS.

</details>

**Success Criteria**:

- [ ] Resolve service and pod DNS names using short names, namespace-qualified names, FQDNs, headless Service answers, and SRV-style record reasoning.
- [ ] Diagnose DNS failures by comparing CoreDNS Pods, `kube-dns` endpoints, CoreDNS logs, Pod `/etc/resolv.conf`, Service objects, and EndpointSlices.
- [ ] Configure CoreDNS safely in a written plan that includes `hosts`, `forward`, `fallthrough`, verification, and rollback.
- [ ] Evaluate `ClusterFirst`, `Default`, `ClusterFirstWithHostNet`, and `None` DNS policies for ordinary Pods, host-networked Pods, and custom resolver cases.
- [ ] Explain when DNS has been proven healthy and when the remaining failure belongs to Service selectors, ports, NetworkPolicy, or application behavior.

### Optional Speed Drills

These drills are optional, but they preserve the fast command practice from the original module. Run them only in a disposable namespace or training cluster. The goal is to build muscle memory without replacing the reasoning workflow above.

```bash
# Drill 1: DNS basics.
kubectl create deployment dns-test --image=nginx
kubectl expose deployment dns-test --port=80
kubectl run test --rm -it --image=busybox:1.36 --restart=Never -- \
  sh -c 'nslookup dns-test; wget -qO- --timeout=2 http://dns-test.default/; nslookup dns-test.default.svc.cluster.local'
kubectl delete deployment dns-test
kubectl delete svc dns-test
```

```bash
# Drill 2: CoreDNS health.
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl get svc kube-dns -n kube-system
kubectl get deployment coredns -n kube-system
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=10
```

```bash
# Drill 3: Cross-namespace resolution.
kubectl create namespace ns1
kubectl create namespace ns2
kubectl create deployment app1 -n ns1 --image=nginx
kubectl create deployment app2 -n ns2 --image=nginx
kubectl expose deployment app1 -n ns1 --port=80
kubectl expose deployment app2 -n ns2 --port=80
kubectl run test -n ns1 --rm -it --image=busybox:1.36 --restart=Never -- \
  wget -qO- --timeout=2 http://app2.ns2/
kubectl run test -n ns2 --rm -it --image=busybox:1.36 --restart=Never -- \
  wget -qO- --timeout=2 http://app1.ns1/
kubectl delete namespace ns1 ns2
```

```bash
# Drill 4: Inspect Pod DNS config.
kubectl run dns-check --image=busybox:1.36 --command -- sleep 3600
kubectl wait --for=condition=ready pod/dns-check --timeout=60s
kubectl exec dns-check -- cat /etc/resolv.conf
kubectl get svc kube-dns -n kube-system -o jsonpath='{.spec.clusterIP}'
kubectl delete pod dns-check
```

```bash
# Drill 5: CoreDNS ConfigMap.
kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}'
kubectl describe configmap coredns -n kube-system
kubectl get configmap coredns -n kube-system -o yaml | grep -E "kubernetes|forward|cache"
```

```bash
# Drill 6: Debug DNS failure workflow.
kubectl create deployment web --image=nginx
kubectl expose deployment web --port=80
kubectl run debug1 --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup web
kubectl run debug2 --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup web.default.svc.cluster.local
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=5
kubectl delete deployment web
kubectl delete svc web
```

```bash
# Drill 7: Complete DNS workflow challenge.
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl create deployment challenge --image=nginx
kubectl expose deployment challenge --port=80
kubectl run test --rm -it --image=busybox:1.36 --restart=Never -- \
  sh -c 'nslookup challenge; wget -qO- --timeout=2 http://challenge.default/; nslookup challenge.default.svc.cluster.local'
kubectl create namespace dns-demo
kubectl create deployment challenge -n dns-demo --image=nginx
kubectl expose deployment challenge -n dns-demo --port=80
kubectl run test --rm -it --image=busybox:1.36 --restart=Never -- \
  wget -qO- --timeout=2 http://challenge.dns-demo/
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=10
kubectl delete deployment challenge
kubectl delete svc challenge
kubectl delete namespace dns-demo
```

---

## Sources

- [DNS for Services and Pods | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Customizing DNS Service | Kubernetes](https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/)
- [Using CoreDNS for Service Discovery | Kubernetes](https://kubernetes.io/docs/tasks/administer-cluster/coredns/)
- [Service | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Debug Services | Kubernetes](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)
- [StatefulSet | Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Network Policies | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [PodSpec v1 core | Kubernetes API Reference 1.35](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.35/#podspec-v1-core)
- [PodDNSConfig v1 core | Kubernetes API Reference 1.35](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.35/#poddnsconfig-v1-core)
- [CoreDNS kubernetes plugin](https://coredns.io/plugins/kubernetes/)
- [CoreDNS forward plugin](https://coredns.io/plugins/forward/)
- [CoreDNS cache plugin](https://coredns.io/plugins/cache/)
- [CoreDNS hosts plugin](https://coredns.io/plugins/hosts/)
- [BusyBox Bug 14671: nslookup not working in Kubernetes](https://lists.busybox.net/pipermail/busybox-cvs/2022-March/041133.html)

---

## Next Module

[Module 3.4: Ingress](../module-3.4-ingress/) - HTTP routing and external access to services.

---

## Learner check

> DNS debugging should start from a real client Pod or from a temporary Pod in the same namespace.
